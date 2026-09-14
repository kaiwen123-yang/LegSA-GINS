"""Build a new P-13 package from sealed inputs, never extend an old science ZIP.

Only the exact immutable-member whitelist is read from the v2 package. Tables
retain every column and row. Display curves retain original CSV tokens at the
first existing epoch in each 0.1-second bin, with an exact source-row map; all
metrics continue to refer to the full frozen evaluator output.
"""
from __future__ import annotations

from collections import Counter
import csv
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from ..manifest import sha256_file

PROTOCOL = 'SENSOR_MODEL_V2_1'
F01_PROTOCOL = 'F01_V2_BYTE_REUSE'
C00 = 'C00_clean_normal'
FAILURE = 'ALGORITHM_FAILURE_ALL_YAW_REJECTED'
VERSIONS = ('v3', 'v2')
PROFILES = frozenset(('F01', 'F02', 'F03', 'F04', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09'))
CONFIG = {'F01': 'single_antenna_EKF', 'F02': 'basic_dual_yaw_EKF', 'F03': 'AB0000',
          'F04': 'AB1111', 'A03': 'AB0111', 'A04': 'AB1011', 'A05': 'AB1101',
          'A06': 'AB1110', 'A07': 'AB1100', 'A08': 'AB1000', 'A09': 'AB0100'}
COUNTS = {'new_native': 5880, 'new_evaluation': 11760, 'formal_native': 6468,
          'formal_evaluation': 12936, 'F01_native': 588, 'core_unique': 5951,
          'core_logical': 7033, 'addendum_unique': 495, 'addendum_logical': 585,
          'sequence_unique': 33, 'sequence_logical': 39}
IMMUTABLE_MEMBERS = frozenset((
    'PLOT_GEOMETRY_CONTRACT.json', 'found/CANONICAL541_CASE_MANIFEST.csv',
    'found/ADDENDUM_CASE_MANIFEST.csv',
    'supplemental/SEQUENCE_QUALITY/OCCLUSION_WINDOW.json',
    'supplemental/CALIBRATED/00_CALIBRATION/LAG_VARIANCE_FIT.csv',
    'supplemental/CALIBRATED/00_CALIBRATION/CALIBRATED_PARAMETERS.csv',
    'supplemental/CALIBRATED/08_AGGREGATE/FROZEN_SENSOR_MODEL.csv',
    'supplemental/CALIBRATED/08_AGGREGATE/v3/EXTERNAL_BY2_V3_REFERENCE.csv',
    *('supplemental/HORIZONTAL/'+name+'.csv' for name in (
        'FINAL_METHOD_REGISTRY_V2', 'OUTPUT_AND_METRIC_COMPATIBILITY',
        'RAW_PRIMARY_METHOD_C00_SUMMARY', 'RAW_AVAILABILITY_AND_STATE_SUMMARY',
        'RAW_BASELINE_AND_HEADING_SUMMARY', 'RAW_RUNTIME_AND_FAILURE_SUMMARY',
        'HARTLEY_OBSERVABILITY_SUMMARY', 'HARTLEY_GAUGE_EQUIVALENCE_SUMMARY',
        'OBSERVABILITY_SINGULAR_VALUES_R1'))))
DIAGNOSTIC_ROLES = frozenset(('ladder', 'nine_grid', 'vchk_a04', 'robustness',
    'sequence_consistency', 'sequence_segments', 'body_frame_bias', 'sensor_residual_validation'))


def safe_member(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('Unsafe ZIP member')
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or p.as_posix() != name or ':' in p.parts[0]:
        raise ValueError('Unsafe ZIP member: '+name)
    return name


def safe_file(path):
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts or any(x.is_symlink() for x in (p, *p.parents)) or not p.is_file():
        raise ValueError('Source must be an absolute regular file without symlink ancestors: '+str(p))
    return p


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)+'\n').encode()


def _csv_bytes(rows, fields=()):
    keys = list(dict.fromkeys((*fields, *(k for row in rows for k in row))))
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def _digest_stream(stream):
    digest, size = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024*1024), b''):
        digest.update(block)
        size += len(block)
    return {'sha256': digest.hexdigest(), 'size_bytes': size}


class PackageWriter:
    """Exclusive ZIP writer with per-member source pins and streamed hashing."""

    def __init__(self, path, *, protocol=PROTOCOL, synthetic=False):
        self.path = Path(path)
        if not self.path.is_absolute() or '..' in self.path.parts or any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise ValueError('Unsafe package destination')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.archive = zipfile.ZipFile(self.path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True)
        self.members, self.sources = {}, []
        self.protocol, self.synthetic = protocol, synthetic
        self.f01_archive = None
        self.f01_curves = {}

    def _write(self, member, reader, *, source_protocol, source, source_sha256, policy, **extra):
        safe_member(member)
        if member in self.members or member == 'PACKAGE_MANIFEST.json':
            raise ValueError('Duplicate or reserved ZIP member: '+member)
        if not source_protocol:
            raise ValueError('Every member requires source_protocol')
        digest, size = hashlib.sha256(), 0
        info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED if member.endswith('.gz') else zipfile.ZIP_DEFLATED
        with self.archive.open(info, 'w', force_zip64=True) as target:
            for block in iter(lambda: reader.read(1024*1024), b''):
                target.write(block)
                digest.update(block)
                size += len(block)
        self.members[member] = {'sha256': digest.hexdigest(), 'size_bytes': size, 'source_protocol': source_protocol}
        self.sources.append({'member': member, 'source': source, 'source_sha256': source_sha256,
                             'member_sha256': digest.hexdigest(), 'policy': policy,
                             'source_protocol': source_protocol, **extra})

    def generated(self, member, payload, **extra):
        if isinstance(payload, (dict, list)):
            payload = _json_bytes(payload)
        self._write(member, io.BytesIO(payload), source_protocol=PROTOCOL,
                    source='generated from pinned inputs', source_sha256=hashlib.sha256(payload).hexdigest(),
                    policy='package bookkeeping; no scientific metric recomputation', **extra)

    def generated_json_gzip(self, member, payload):
        # The formal frozen indices can exceed hundreds of MB; encode incrementally.
        with tempfile.TemporaryFile() as temporary:
            with gzip.GzipFile(filename='', mode='wb', fileobj=temporary, mtime=0) as compressed:
                for piece in json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True).iterencode(payload):
                    compressed.write(piece.encode())
                compressed.write(b'\n')
            temporary.seek(0)
            identity = _digest_stream(temporary)
            temporary.seek(0)
            self._write(member, temporary, source_protocol=PROTOCOL, source='supplied sealed formal index rows',
                source_sha256=identity['sha256'], policy='complete supplied index; JSON encoding and lossless gzip only')

    def file(self, source, member, expected_sha256, *, source_protocol, compress_csv=False, **extra):
        source = safe_file(source)
        if not expected_sha256 or sha256_file(source) != expected_sha256:
            raise ValueError('Source SHA mismatch or missing frozen pin: '+str(source))
        if source.name.endswith('.gz'):
            with gzip.open(source, 'rb') as stream:
                _digest_stream(stream)  # A .gz suffix alone is not valid compressed content.
        if compress_csv:
            if source.suffix != '.csv' or not member.endswith('.csv.gz'):
                raise ValueError('Lossless CSV gzip requires .csv source and .csv.gz member')
            with tempfile.TemporaryFile() as temporary:
                with gzip.GzipFile(filename='', mode='wb', fileobj=temporary, mtime=0) as packed:
                    with source.open('rb') as stream:
                        shutil.copyfileobj(stream, packed)
                temporary.seek(0)
                self._write(member, temporary, source_protocol=source_protocol, source=str(source),
                    source_sha256=expected_sha256, policy='lossless gzip; every source row and column retained', **extra)
        else:
            with source.open('rb') as stream:
                self._write(member, stream, source_protocol=source_protocol, source=str(source),
                            source_sha256=expected_sha256, policy='byte-identical', **extra)
        if sha256_file(source) != expected_sha256:
            raise ValueError('Source changed during packaging: '+str(source))

    def immutable(self, source, expected_sha256, members=IMMUTABLE_MEMBERS):
        source = safe_file(source)
        if sha256_file(source) != expected_sha256 or not set(members) <= IMMUTABLE_MEMBERS:
            raise ValueError('Immutable package identity or member whitelist violation')
        with zipfile.ZipFile(source) as old:
            names = old.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate member in immutable package')
            for name in names:
                safe_member(name)
            manifest = json.loads(old.read('PACKAGE_MANIFEST.json'))['members']
            for name in sorted(members):
                if name not in manifest:
                    raise ValueError('Required immutable member missing: '+name)
                with old.open(name) as stream:
                    identity = _digest_stream(stream)
                if any(identity[k] != manifest[name][k] for k in ('sha256', 'size_bytes')):
                    raise ValueError('Immutable member identity mismatch: '+name)
                with old.open(name) as stream:
                    self._write(name, stream, source_protocol='IMMUTABLE_PHYSICAL_EXTERNAL_OR_IMU_CALIBRATION',
                        source=str(source)+'::'+name, source_sha256=identity['sha256'],
                        policy='explicit immutable whitelist; byte-identical', source_package_sha256=expected_sha256)
        # Selected formal F01 displays have separate authorization from the
        # immutable physical whitelist. Index only manifests, never other science.
        self.f01_archive = zipfile.ZipFile(source)
        old_sources = json.loads(self.f01_archive.read('SUPPLEMENT_SOURCE_MANIFEST.json'))
        self.f01_sources = {r['member']: r for r in old_sources}
        self.f01_identities = json.loads(self.f01_archive.read('PACKAGE_MANIFEST.json'))['members']
        self.f01_package_sha256 = expected_sha256
        for name in ('error_series_subset/SUBSET_MANIFEST.csv', 'CORE_SUPPLEMENT_SERIES_MANIFEST.csv',
                     'addendum_error_series_subset/SUBSET_MANIFEST.csv',
                     'supplemental/CALIBRATED/error_series/SERIES_MANIFEST.csv'):
            if name not in self.f01_archive.namelist():
                continue
            payload = self.f01_archive.read(name)
            identity = self.f01_identities[name]
            if hashlib.sha256(payload).hexdigest() != identity['sha256'] or len(payload) != identity['size_bytes']:
                raise ValueError('Frozen F01 display manifest identity mismatch')
            for row in csv.DictReader(io.StringIO(payload.decode())):
                if row.get('status', 'OK') not in ('OK', 'AVAILABLE', 'COMPLETED'):
                    continue
                version = row.get('evaluator_version') or 'v3'
                key = (row.get('run_id'), version)
                # A key is consumed only when a caller presents a formal F01 row.
                if key[0]:
                    row['_frozen_manifest_member'] = name
                    self.f01_curves.setdefault(key, row)

    def frozen_f01_curve(self, row, member, full_source_sha256):
        old = self.f01_curves.get((row['run_id'], row['evaluator_version']))
        if not old:
            return None
        if row['method_id'] != 'F01' or row.get('formal_F01_reused') is not True:
            raise ValueError('Frozen projection reuse is restricted to formal F01')
        oldmember = old.get('member') or old.get('package_member')
        if not oldmember:
            prefix = old['_frozen_manifest_member'].rsplit('/', 1)[0]
            oldmember = prefix+'/'+row['evaluator_version']+'/'+row['run_id']+'.csv.gz'
        safe_member(oldmember)
        identity = self.f01_identities.get(oldmember)
        if not identity:
            raise ValueError('Frozen F01 projection identity missing')
        with self.f01_archive.open(oldmember) as stream:
            actual = _digest_stream(stream)
        if any(actual[k] != identity[k] for k in actual):
            raise ValueError('Frozen F01 projection SHA mismatch')
        # Original core subset members predate SUPPLEMENT_SOURCE_MANIFEST;
        # their SUBSET_MANIFEST row is the frozen source/projection record.
        original = self.f01_sources.get(oldmember, dict(old))
        # Keep the old source-row convention; do not label every-20th as new 10Hz.
        extra = {k: original[k] for k in ('source_row_first', 'source_row_stride', 'rows_full', 'rows_kept') if k in original}
        if original.get('sample_policy') == 'every 20th existing row; no interpolation':
            extra.update(source_row_first=2, source_row_stride=20)
        with self.f01_archive.open(oldmember) as stream:
            self._write(member, stream, source_protocol=F01_PROTOCOL,
                source=self.f01_archive.filename+'::'+oldmember, source_sha256=identity['sha256'],
                policy='byte-identical frozen F01 display; original projection/row semantics preserved',
                source_package_sha256=self.f01_package_sha256, original_source_manifest=original,
                full_metrics_source_sha256=full_source_sha256, run_id=row['run_id'],
                display_projection='FROZEN_V2_BYTES', **extra)
        return {'source_sha256': identity['sha256'], 'source_protocol': F01_PROTOCOL,
                'display_projection': 'FROZEN_V2_BYTES', 'frozen_member': oldmember,
                'full_metrics_source_sha256': full_source_sha256, **extra}

    def close(self, probe):
        self.generated('IDENTITY_PROBE.json', probe)
        self.generated('SUPPLEMENT_SOURCE_MANIFEST.json', list(self.sources))
        manifest = {'protocol_id': self.protocol, 'data_mode': 'synthetic_test' if self.synthetic else 'real_and_controlled_degradation',
            'synthetic_data_used': self.synthetic, 'semisynthetic_data_used': not self.synthetic,
            'trace_used_online': False, 'metrics_recomputed': False, 'members': self.members}
        self.archive.writestr('PACKAGE_MANIFEST.json', _json_bytes(manifest))
        self.archive.close()
        if self.f01_archive is not None:
            self.f01_archive.close()
        return validate_archive(self.path)


def display_series(writer, source, member, expected_sha256, *, source_protocol, run_id):
    """Token-preserving 10 Hz view, independent of source sample frequency."""
    source = safe_file(source)
    if sha256_file(source) != expected_sha256:
        raise ValueError('Error series frozen SHA mismatch')
    opener = gzip.open if source.name.endswith('.gz') else open
    with tempfile.TemporaryFile() as selected, tempfile.TemporaryFile() as mapping:
        with gzip.GzipFile(filename='', mode='wb', fileobj=selected, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding='utf-8', newline='') as out:
                with opener(source, 'rt', encoding='utf-8', newline='') as stream:
                    reader = csv.reader(stream)
                    header = next(reader)
                    if len(header) != len(set(header)) or 'time' not in header:
                        raise ValueError('Error CSV requires unique columns including time')
                    index = header.index('time')
                    csvout = csv.writer(out)
                    csvout.writerow(header)
                    kept, total, previous, last_bin = 0, 0, None, None
                    maprows = io.TextIOWrapper(mapping, encoding='utf-8', newline='', write_through=True)
                    mapout = csv.writer(maprows)
                    mapout.writerow(('member_csv_row', 'source_csv_row'))
                    for number, tokens in enumerate(reader, 2):
                        if len(tokens) != len(header):
                            raise ValueError('Error CSV row width changed')
                        time = Decimal(tokens[index])
                        if not time.is_finite() or (previous is not None and time <= previous):
                            raise ValueError('Error-series times must be finite and strictly increasing')
                        previous, total = time, total+1
                        time_bin = int((time*10).to_integral_value(rounding='ROUND_FLOOR'))
                        if time_bin != last_bin:
                            kept += 1
                            csvout.writerow(tokens)
                            mapout.writerow((kept+1, number))
                            last_bin = time_bin
                    maprows.flush()
                    maprows.detach()
        if total == 0:
            raise ValueError('Completed error series is empty')
        rowmap_member = member.removesuffix('.csv.gz')+'.source_rows.csv.gz'
        with tempfile.TemporaryFile() as zipped_map:
            mapping.seek(0)
            with gzip.GzipFile(filename='', mode='wb', fileobj=zipped_map, mtime=0) as packed:
                shutil.copyfileobj(mapping, packed)
            zipped_map.seek(0)
            writer._write(rowmap_member, zipped_map, source_protocol=source_protocol, source=str(source),
                          source_sha256=expected_sha256, policy='exact display-to-full-source CSV row mapping', run_id=run_id)
        selected.seek(0)
        writer._write(member, selected, source_protocol=source_protocol, source=str(source), source_sha256=expected_sha256,
            policy='first existing epoch per floor(time*10) bin; original tokens; display only; no interpolation',
            run_id=run_id, rows_full=total, rows_kept=kept, source_row_map_member=rowmap_member,
            full_metrics_source_sha256=expected_sha256, source_columns_retained='ALL')
    if sha256_file(source) != expected_sha256:
        raise ValueError('Error series changed during packaging')
    return {'rows_full': total, 'rows_kept': kept, 'source_sha256': expected_sha256,
            'source_row_map_member': rowmap_member, 'source_protocol': source_protocol}


def _domain(row):
    if row.get('domain') in ('CORE', 'ADDENDUM', 'SEQUENCE'):
        return row['domain']
    if row.get('dataset_id', 'BY2') != 'BY2':
        return 'SEQUENCE'
    return 'ADDENDUM' if str(row.get('degradation_id', row.get('degradation_type_id', ''))).startswith(('D61', 'D62')) or row['case_id'].startswith(('D61', 'D62')) else 'CORE'


def effective_configuration(row):
    """Read the native/evaluator spelling without changing a sealed source row."""
    expected = CONFIG[row['method_id']]
    values = [row[key] for key in ('effective_configuration_id', 'effective_profile') if row.get(key)]
    if not values or any(value != expected for value in values):
        raise ValueError('Effective configuration disagrees with the frozen method registry')
    return expected


def terminal_identity(records, evaluations):
    """Reject unfinished, duplicate or scientifically unsupported final rows."""
    native = {r['run_id']: r for r in records}
    cellkeys = {(r.get('dataset_id', 'BY2'), r['case_id'], r['method_id']) for r in records}
    pairs = {(r['run_id'], r['evaluator_version']) for r in evaluations}
    if len(native) != len(records) or len(cellkeys) != len(records) or len(pairs) != len(evaluations):
        raise ValueError('Duplicate native or evaluation terminal identity')
    if pairs != {(key, version) for key in native for version in VERSIONS}:
        raise ValueError('Native/evaluator terminal coverage mismatch')
    for row in records:
        if row.get('terminal_status') not in ('COMPLETED', FAILURE):
            raise ValueError('Unsupported or unfinished native terminal')
        if row['method_id'] == 'F01' and row.get('formal_F01_reused') is not True:
            raise ValueError('Every F01 row must identify formal v2 reuse')
    for row in evaluations:
        run = native[row['run_id']]
        if (row.get('dataset_id', 'BY2'), row['case_id'], row['method_id']) != (run.get('dataset_id', 'BY2'), run['case_id'], run['method_id']):
            raise ValueError('Evaluation cell does not match native identity')
        wanted = 'COMPLETED' if run['terminal_status'] == 'COMPLETED' else 'NOT_RUN_ALGORITHM_FAILURE'
        if row.get('evaluation_status') != wanted:
            raise ValueError('Evaluation failure or nonterminal input')
        if wanted == 'COMPLETED' and str(row.get('finite_output', '')).lower() != 'true':
            raise ValueError('Nonfinite or unverified completed evaluator output')
        if row['method_id'] == 'F01' and row.get('formal_F01_reused') is not True:
            raise ValueError('Every F01 evaluator row must identify formal v2 reuse')
    counts = {'formal_native': len(records), 'formal_evaluation': len(evaluations),
              'F01_native': sum(r['method_id'] == 'F01' for r in records),
              'new_native': sum(r['method_id'] != 'F01' for r in records),
              'new_evaluation': sum(r['method_id'] != 'F01' for r in evaluations)}
    if any(counts[k] != COUNTS[k] for k in counts):
        raise ValueError('P-13 formal/new/F01 counts differ: '+str(counts))
    for row in (*records, *evaluations):
        if not row.get('data_mode') or any(str(row.get(key, '')).lower() != 'false' for key in ('synthetic_data_used', 'trace_used_online')):
            raise ValueError('Missing or forbidden real-data provenance flag')
        if str(row.get('semisynthetic_data_used', '')).lower() not in ('true', 'false'):
            raise ValueError('Missing semisynthetic data disclosure')
    case_methods = {}
    for row in records:
        case_methods.setdefault((row.get('dataset_id', 'BY2'), row['case_id']), set()).add(row['method_id'])
    if any(methods != PROFILES for methods in case_methods.values()):
        raise ValueError('Every formal case requires exactly eleven registered profiles')
    if {r.get('dataset_id') for r in records} != {'BY2', 'BY2H', 'BY2O'}:
        raise ValueError('Formal package requires the three registered datasets')
    for name, expected in (('CORE', 5951), ('ADDENDUM', 495), ('SEQUENCE', 22)):
        if sum(_domain(r) == name for r in records) != expected:
            raise ValueError('P-13 domain coverage differs: '+name)
    return {'passed': True, 'protocol_id': PROTOCOL, 'counts': dict(COUNTS),
            'native_status_counts': dict(Counter(r['terminal_status'] for r in records)),
            'evaluation_status_counts': dict(Counter(r['evaluation_status'] for r in evaluations)),
            'full_metrics_recomputed': False, 'F01_policy': 'formal v2 source bytes reused',
            'data_mode': 'real_and_controlled_degradation', 'synthetic_data_used': False,
            'semisynthetic_data_used': True, 'trace_used_online': False}


def _series_path(row):
    p = Path(row['error_series_source'])
    if p.is_dir():
        options = [p/'FROZEN_EVALUATOR/error_series.csv.gz', p/'FROZEN_EVALUATOR/error_series.csv',
                   p/'error_series.csv.gz', p/'error_series.csv']
        found = [v for v in options if v.is_file()]
        if len(found) != 1:
            raise ValueError('Error-series directory must resolve to exactly one retained source')
        p = found[0]
    return safe_file(p)


def default_curve_selector(row):
    return (_domain(row) != 'CORE' or row['case_id'] == C00 or
            row.get('degradation_id', row.get('degradation_type_id', row['case_id'][:3])) in
            {'D04', 'D05', 'D12', 'D27', 'D58', 'D60'})


def package_failure_series(writer, stage, records, source_pins):
    """All-domain failure inventory with exact native identities and no fallback.

    MFIG14 separately selects its CORE F04/F02 pair from this complete list.
    Missing native traces stay explicit UNAVAILABLE rows, never borrowed files.
    """
    stage = Path(stage).absolute()
    failed_cases = {(r.get('dataset_id', 'BY2'), r['case_id']) for r in records if r['terminal_status'] == FAILURE}
    traces = []
    for row in records:
        key = row.get('dataset_id', 'BY2'), row['case_id']
        if key not in failed_cases or not (row['terminal_status'] == FAILURE or row['method_id'] == 'F02'):
            continue
        evaluation_status = {'COMPLETED': 'COMPLETED', FAILURE: 'NOT_RUN_ALGORITHM_FAILURE'}.get(row['terminal_status'])
        if evaluation_status is None:
            raise ValueError('Failure-series input has an unsupported native terminal')
        protocol = F01_PROTOCOL if row['method_id'] == 'F01' else PROTOCOL
        item = {k: row.get(k, '') for k in ('run_id', 'case_id', 'dataset_id', 'method_id')}
        item.update(effective_configuration_id=effective_configuration(row), terminal_status=row['terminal_status'],
                    evaluation_status=evaluation_status, evaluator_version='v3', domain=_domain(row),
                    source_protocol=protocol, formal_F01_reused=row.get('formal_F01_reused', False))
        source = Path(row['output_root'])/'PORT_GNSS_UPDATE_TRACE.csv.gz'
        if protocol == PROTOCOL and not source.is_relative_to(stage):
            raise ValueError('New failure timeline source lies outside the v2.1 stage')
        if not source.is_file():
            item.update(status='UNAVAILABLE', reason='required retained native trace unavailable; no substitute timeline')
        else:
            source = safe_file(source)
            digest = source_pins.get(str(source))
            if not digest:
                raise ValueError('Failure timeline has no retained-file producer pin')
            member = 'supplemental/FAILURE_SERIES/'+row['run_id']+'.csv.gz'
            writer.file(source, member, digest, source_protocol=protocol, run_id=row['run_id'])
            item.update(member=member, status='OK', source_sha256=digest)
        traces.append(item)
    writer.generated('supplemental/FAILURE_SERIES/SERIES_MANIFEST.csv', _csv_bytes(traces,
        ('run_id', 'case_id', 'dataset_id', 'method_id', 'effective_configuration_id', 'terminal_status',
         'evaluation_status', 'evaluator_version', 'domain', 'source_protocol', 'formal_F01_reused', 'member', 'status')))
    writer.generated('supplemental/FAILURE_SERIES/STATUS.json', {
        'failure_count': sum(r['terminal_status'] == FAILURE for r in records),
        'failed_case_count': len(failed_cases), 'timeline_rows': len(traces),
        'zero_is_observed_count': not failed_cases, 'inventory_scope': 'ALL_FORMAL_DOMAINS',
        'MFIG14_scope': 'CORE; first new F04 failure plus exact same-dataset/case new F02 control'})
    return traces


def _check_aggregate_coverage(stage, seal, records):
    for version in VERSIONS:
        for folder, unique, logical in (('13_AGGREGATE', 5951, 7033),
                ('13_AGGREGATE_ADDENDUM', 495, 585), ('13_AGGREGATE_SEQUENCES', 33, 39)):
            for table, count in (('UNIQUE_EVALUATION_RESULTS', unique), ('LOGICAL_EVALUATION_RESULTS', logical)):
                relative = folder+'/'+version+'/'+table+'.csv'
                if relative not in seal['files_sha256']:
                    raise ValueError('Required sealed aggregate table missing: '+relative)
                with (stage/relative).open(newline='') as stream:
                    reader = csv.DictReader(stream)
                    cells = [(r.get('dataset_id', 'BY2'), r['case_id'], r['method_id']) for r in reader]
                if len(cells) != count:
                    raise ValueError('Aggregate table count differs: '+relative)
                if table == 'UNIQUE_EVALUATION_RESULTS':
                    domain = {'13_AGGREGATE': 'CORE', '13_AGGREGATE_ADDENDUM': 'ADDENDUM',
                              '13_AGGREGATE_SEQUENCES': 'SEQUENCE'}[folder]
                    selected = [r for r in records if _domain(r) == domain or
                                (domain == 'SEQUENCE' and r['case_id'] == C00)]
                    wanted = {(r.get('dataset_id', 'BY2'), r['case_id'], r['method_id']) for r in selected}
                    if len(cells) != len(set(cells)) or set(cells) != wanted:
                        raise ValueError('Aggregate cells do not match formal native index: '+relative)


def build_handoff(stage, output_zip, records, evaluations, *, source_pins,
                  immutable_package, immutable_package_sha256, diagnostic_members,
                  evidence_members=(), evidence_roots=(), code_commit,
                  curve_selector=default_curve_selector, aggregate_root=None):
    """Package formal 6468/12936 supplied rows plus new sealed aggregates.

    ``source_pins`` maps absolute paths to hashes from existing receipts/seals.
    Diagnostic entries contain member/source/sha256/role; every required role
    must occur, and their scientific source must reside inside ``stage``.
    Evidence entries are pinned preregistrations/audits under explicitly given
    evidence_roots and are stored exclusively beneath evidence/. They cannot
    replace any current scientific table. No method uses old package fallback.
    """
    stage = Path(stage).absolute()
    if any(p.is_symlink() for p in (stage, *stage.parents)) or '..' in stage.parts:
        raise ValueError('Unsafe stage root')
    aggregate_root = stage if aggregate_root is None else Path(aggregate_root).absolute()
    if not aggregate_root.is_relative_to(stage) or any(p.is_symlink() for p in (aggregate_root, *aggregate_root.parents)):
        raise ValueError('Aggregate root must be inside the current v2.1 stage')
    probe = terminal_identity(records, evaluations)
    for row in (*records, *evaluations):
        effective_configuration(row)
    if not DIAGNOSTIC_ROLES <= {r['role'] for r in diagnostic_members}:
        raise ValueError('Required new downstream diagnostic roles missing')
    pins = {str(Path(p).absolute()): sha for p, sha in source_pins.items()}
    def pin(path):
        p = safe_file(path)
        digest = pins.get(str(p))
        if not digest:
            raise ValueError('No independently sealed source pin: '+str(p))
        return digest
    def source_protocol(path, row):
        if row['method_id'] == 'F01':
            return F01_PROTOCOL
        if not Path(path).is_relative_to(stage):
            raise ValueError('New scientific source lies outside v2.1 stage')
        return PROTOCOL
    seal_path = aggregate_root/'P13_MACHINE_REPORT/AGGREGATE_SEAL.json'
    if sha256_file(safe_file(seal_path)) != pin(seal_path):
        raise ValueError('Aggregate seal changed')
    seal = json.loads(seal_path.read_text())
    if seal.get('status') != 'SEALED':
        raise ValueError('Aggregate seal is unfinished')
    for relative, digest in seal['files_sha256'].items():
        safe_member(relative)
        if sha256_file(safe_file(aggregate_root/relative)) != digest:
            raise ValueError('Aggregate member differs from seal: '+relative)
    _check_aggregate_coverage(aggregate_root, seal, records)
    writer = PackageWriter(output_zip)
    try:
        writer.immutable(immutable_package, immutable_package_sha256)
        for relative, digest in sorted(seal['files_sha256'].items()):
            if PurePosixPath(relative).parts[0] not in ('13_AGGREGATE', '13_AGGREGATE_ADDENDUM', '13_AGGREGATE_SEQUENCES', 'P13_MACHINE_REPORT'):
                raise ValueError('Aggregate seal contains unapproved member root')
            source = aggregate_root/relative
            gz = source.suffix == '.csv'
            writer.file(source, relative+('.gz' if gz else ''), digest, source_protocol=PROTOCOL, compress_csv=gz)
            parts = PurePosixPath(relative).parts
            if parts[0] == '13_AGGREGATE' and parts[-1] in ('UNIQUE_EVALUATION_RESULTS.csv', 'LOGICAL_EVALUATION_RESULTS.csv'):
                alias = '12_OFFLINE_EVALUATION/'+'/'.join(parts[1:])+'.gz'
                writer.file(source, alias, digest, source_protocol=PROTOCOL, compress_csv=True)
        writer.file(seal_path, 'P13_MACHINE_REPORT/AGGREGATE_SEAL.json', pin(seal_path), source_protocol=PROTOCOL)
        for row in diagnostic_members:
            source = safe_file(row['source'])
            if not source.is_relative_to(stage) or row['member'] in IMMUTABLE_MEMBERS:
                raise ValueError('New diagnostics must originate in v2.1 stage')
            if pin(source) != row['sha256']:
                raise ValueError('Diagnostic input pin disagrees with catalog')
            writer.file(source, row['member'], row['sha256'], source_protocol=PROTOCOL,
                        diagnostic_role=row['role'], compress_csv=bool(row.get('compress_csv')))
        for row in evidence_members:
            source = safe_file(row['source'])
            if not row['member'].startswith('evidence/') or not any(source.is_relative_to(Path(root)) for root in evidence_roots):
                raise ValueError('Frozen preregistration evidence source/member scope violation')
            if pin(source) != row['sha256']:
                raise ValueError('Evidence pin disagrees with catalog')
            writer.file(source, row['member'], row['sha256'], source_protocol='IMMUTABLE_PREREGISTRATION_OR_RESIDUAL_AUDIT')
        manifests = {'error_series_subset': [], 'addendum_error_series_subset': [], 'sequence_error_series_subset': []}
        for row in sorted(evaluations, key=lambda r: (r['evaluator_version'], r['run_id'])):
            if not curve_selector(row):
                continue
            domain = _domain(row)
            prefixes = ['addendum_error_series_subset' if domain == 'ADDENDUM' else 'error_series_subset']
            if domain == 'SEQUENCE':
                prefixes = ['sequence_error_series_subset']
            elif row['case_id'] == C00:
                prefixes.append('sequence_error_series_subset')
            base = {k: row.get(k, '') for k in ('run_id', 'case_id', 'dataset_id', 'method_id', 'effective_configuration_id',
                    'evaluator_version', 'outage_start_s', 'outage_end_s', 'data_mode', 'synthetic_data_used', 'semisynthetic_data_used')}
            base['effective_configuration_id'] = effective_configuration(row)
            status = row['evaluation_status']
            item = {**base, 'status': 'OK' if status == 'COMPLETED' else status,
                    'source_protocol': F01_PROTOCOL if row['method_id'] == 'F01' else PROTOCOL}
            if status == 'COMPLETED':
                source = _series_path(row)
                member = prefixes[0]+'/'+row['evaluator_version']+'/'+row['run_id']+'.csv.gz'
                digest = pin(source)
                if row['method_id'] == 'F01' and sha256_file(source) != digest:
                    raise ValueError('Frozen F01 full error source SHA mismatch')
                reused = writer.frozen_f01_curve(row, member, digest) if row['method_id'] == 'F01' else None
                if reused is not None:
                    item.update(member=member, **reused)
                else:
                    item.update(member=member, display_projection='NEW_DISPLAY_FROM_FROZEN_V2_SCIENCE' if row['method_id'] == 'F01' else 'V21_10HZ',
                        **display_series(writer, source, member, digest,
                            source_protocol=source_protocol(source, row), run_id=row['run_id']))
            for prefix in prefixes:
                manifests[prefix].append(dict(item))
        for prefix, rows in manifests.items():
            writer.generated(prefix+'/SUBSET_MANIFEST.csv', _csv_bytes(rows))
            for version in VERSIONS:
                writer.generated(prefix+'/'+version+'/SUBSET_MANIFEST.csv', _csv_bytes([r for r in rows if r['evaluator_version'] == version]))
        writer.generated('CORE_SUPPLEMENT_SERIES_MANIFEST.csv', _csv_bytes(manifests['error_series_subset']))
        for row in records:
            if row['case_id'] == C00 and row['terminal_status'] == 'COMPLETED':
                source = Path(row['output_root'])/'NAV_10HZ.csv.gz'
                writer.file(source, 'C00_NAV_'+effective_configuration(row)+'.csv.gz', pin(source),
                    source_protocol=source_protocol(source, row), run_id=row['run_id'],
                    display_policy='retained native 10Hz file; original tokens; no interpolation')
        package_failure_series(writer, stage, records, pins)
        writer.generated('ADDENDUM_IDENTITY_PROBE.json', {'passed': True, 'protocol_id': PROTOCOL, 'unique_rows': 495,
            'logical_rows': 585, 'case_count': 45, 'source_protocol': PROTOCOL})
        # Full rows remain untouched inside compressed provenance indices; no old KEEP_COL filter.
        for label, rows in (('FORMAL_RUN_RECORDS', records), ('FORMAL_EVALUATION_RECORDS', evaluations)):
            writer.generated_json_gzip('provenance/'+label+'.json.gz', rows)
        probe.update(code_commit=code_commit, required_diagnostic_roles=sorted(DIAGNOSTIC_ROLES),
                     aggregate_seal_sha256=pin(seal_path), immutable_package_sha256=immutable_package_sha256)
        return writer.close(probe)
    except BaseException:
        writer.archive.close()
        if writer.f01_archive is not None:
            writer.f01_archive.close()
        raise  # Preserve any incomplete ZIP; never overwrite/delete a failed attempt.


def validate_archive(path):
    """Publication-compatible manifest validation plus v2.1 identity checks."""
    path = safe_file(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('ZIP duplicate member or CRC failure')
        for name in names:
            safe_member(name)
        manifest = json.loads(archive.read('PACKAGE_MANIFEST.json'))
        if set(names) != set(manifest['members']) | {'PACKAGE_MANIFEST.json'}:
            raise ValueError('ZIP manifest member coverage differs')
        for name, identity in manifest['members'].items():
            with archive.open(name) as stream:
                actual = _digest_stream(stream)
            if not identity.get('source_protocol') or any(actual[k] != identity[k] for k in actual):
                raise ValueError('ZIP member identity mismatch: '+name)
            if name.endswith('.gz'):
                with archive.open(name) as raw, gzip.GzipFile(fileobj=raw) as stream:
                    _digest_stream(stream)
        probe = json.loads(archive.read('IDENTITY_PROBE.json'))
        if probe.get('passed') is not True or probe.get('protocol_id') != PROTOCOL:
            raise ValueError('P-13 identity probe failed')
        if not manifest.get('synthetic_data_used') and probe.get('counts') != COUNTS:
            raise ValueError('P-13 formal identity counts changed')
        sources = json.loads(archive.read('SUPPLEMENT_SOURCE_MANIFEST.json'))
        source_map = {r['member']: r for r in sources}
        if len(source_map) != len(sources) or set(source_map) != set(names)-{'PACKAGE_MANIFEST.json', 'SUPPLEMENT_SOURCE_MANIFEST.json'}:
            raise ValueError('Supplement source manifest coverage differs')
        for name, row in source_map.items():
            if row['member_sha256'] != manifest['members'][name]['sha256'] or row['source_protocol'] != manifest['members'][name]['source_protocol']:
                raise ValueError('Supplement source identity mismatch')
    return {'passed': True, 'member_count': len(names), 'size_bytes': path.stat().st_size,
            'sha256': sha256_file(path), 'identity_probe': probe}
