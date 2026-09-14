"""Join completed P-13 evidence, aggregate, and build the separately pinned ZIP.

This entrypoint contains no provider, native, or evaluator invocation. Original
P05 consistency and frozen V-CHK/robustness functions are diagnostics only.
Outputs are exclusive (or exact sealed resume) below a caller-owned directory.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
import yaml

from ..clean5_degradation.common import registry, resolve, read_csv
from ..manifest import sha256_file
from . import aggregate, diagnostics, downstream, pack

STAGE = '<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21'
CAL = '<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL'
OLD_PACKAGE_SHA256 = '79e75f7d867a4930dc80c0f906173b48aab1bec6a5caac44b63bae993a848dd3'
# Exact P06 tables assigned for formal F01 reuse, never other-method fallback.
F01_TABLES = {
    ('v2', 'segment_rows'): ('08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv', 'b795772038ed1e8ca8116a2fd9ec5d7d9e2c95abce37c66cd1c5c44130c4ce6d'),
    ('v3', 'segment_rows'): ('08_AGGREGATE/v3/WINDOW_SEGMENT_SUMMARY.csv', '68f1f4f31be5012def2ff6dca7c65d7354c9cc90c65a53bbbd6865ebbfe29055'),
    ('v2', 'body_rows'): ('08_AGGREGATE/BODY_FRAME_BIAS.csv', '9f31209bac3a8db88ffaed72a7d5cd62926fb1d5c50d4c4abfe12718dcb565e5'),
    ('v3', 'body_rows'): ('08_AGGREGATE/v3/BODY_FRAME_BIAS.csv', '9976c5af16e24a548c95b9ef3c290dde4dbf8a558ca45081814486650bb64cde'),
}


class Pins:
    def __init__(self):
        self.values, self.roles = {}, {}

    def _record(self, path, expected, role):
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Invalid source SHA256 pin')
        key = str(path)
        if key in self.values and self.values[key] != expected:
            raise ValueError('Conflicting independently sealed source pins: '+key)
        self.values[key] = expected
        self.roles.setdefault(key, set()).add(role)
        return path

    def add(self, path, expected, role, *, verify=True):
        path = pack.safe_file(path)
        if verify and sha256_file(path) != expected:
            raise ValueError('Pinned finalization input changed: '+str(path))
        return self._record(path, expected, role)

    def capture_metadata(self, path, role):
        """Record new producer metadata after its contents/identities are checked."""
        path = pack.safe_file(path)
        return self._record(path, sha256_file(path), role)

    def register_retained(self, receipt_path, relative, expected):
        """Register a sealed reference; validate file safety/hash when consumed.

        This does not claim that an unconsumed retained payload was reopened.
        The receipt itself must already have passed its source/identity gate.
        ``check`` and the package reader still verify every consumed file.
        """
        receipt_path = Path(receipt_path)
        roles = self.roles.get(str(receipt_path), set())
        if not roles.intersection({'resolved_archive_receipt', 'receipt_referenced_by_hash_pinned_v2_final_index'}):
            raise ValueError('Retained pin requires a verified producer receipt')
        path = receipt_path.parent / pack.safe_member(relative)
        return self._record(path, expected, 'retained_file_producer_seal')

    def check(self, path):
        path = pack.safe_file(path)
        if str(path) not in self.values:
            raise ValueError('No producer/source-seal pin: '+str(path))
        return self.add(path, self.values[str(path)], 'verified_consumed_input')

    def rows(self):
        return [{'path': p, 'sha256': sha, 'roles': sorted(self.roles[p])} for p, sha in sorted(self.values.items())]


def _json(path):
    return json.loads(pack.safe_file(path).read_text())


def write_once(path, value, pins):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or '..' in path.parts or not path.is_absolute():
        raise ValueError('Unsafe finalization output')
    content = value if isinstance(value, bytes) else pack._json_bytes(value)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('Existing finalization output differs: '+str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(content)
    pins.capture_metadata(path, 'new_finalization_producer_output')
    return path


def closure_gate(main, down, records, evaluations, down_records, down_evaluations):
    if (main.get('status') != 'PASS' or main.get('native_terminals') != 5880 or
            main.get('evaluator_terminals') != 11760 or main.get('verified_receipts') != 5880 or main.get('pending') != 0):
        raise ValueError('Main archive closure is not PASS 5880/11760 with zero pending')
    if (down.get('status') != 'PASS' or down.get('native_calls') != 21 or down.get('evaluator_terminals') != 42 or
            down.get('verified_archives') != 21 or down.get('archive', {}).get('pending_run_ids') != []):
        raise ValueError('Downstream archive closure is not PASS 21/42 with zero pending')
    for runs, rows, expected in ((records, evaluations, 5880), (down_records, down_evaluations, 21)):
        native = {r['run_id']: r for r in runs}
        if len(runs) != expected or len(native) != expected or len(rows) != expected*2:
            raise ValueError('Final native/evaluation counts differ from their closure')
        pairs = {(r['run_id'], r['evaluator_version']) for r in rows}
        if len(pairs) != len(rows) or pairs != {(key, v) for key in native for v in pack.VERSIONS}:
            raise ValueError('Final evaluator slots do not bijectively cover native runs')
        for row in rows:
            record = native[row['run_id']]
            if record['terminal_status'] not in ('COMPLETED', pack.FAILURE):
                raise ValueError('Unsupported native terminal in finalization')
            wanted = 'COMPLETED' if record['terminal_status'] == 'COMPLETED' else 'NOT_RUN_ALGORITHM_FAILURE'
            if row['evaluation_status'] != wanted or (wanted == 'COMPLETED' and str(row.get('finite_output')).lower() != 'true'):
                raise ValueError('Failed or nonfinite evaluator terminal in finalization')
            if (row['case_id'], row['method_id'], row.get('dataset_id')) != (record['case_id'], record['method_id'], record.get('dataset_id')):
                raise ValueError('Final native/evaluation cell mismatch')
    return {'status': 'PASS', 'main_native': len(records), 'main_evaluations': len(evaluations),
            'downstream_native': len(down_records), 'downstream_evaluations': len(down_evaluations),
            'grid_origin_gate_status': down.get('grid_origin_gate_status', 'UNAVAILABLE')}


def receipt_catalog(records, pins, *, resolved_root=None):
    """Use retained-file pins from completed producer receipts, without bulk rehash."""
    receipts = {}
    for ordinal, row in enumerate(records, 1):
        path = pack.safe_file(row['archive_receipt'])
        if resolved_root is not None:
            reference = _json(Path(resolved_root)/row['run_id']/'RECEIPT_REFERENCE.json')
            if reference['path'] != str(path):
                raise ValueError('Resolved receipt reference points to a different archive')
            pins.add(path, reference['sha256'], 'resolved_archive_receipt')
        else:
            # Baseline rows were loaded using published full-index SHA pins.
            pins.capture_metadata(path, 'receipt_referenced_by_hash_pinned_v2_final_index')
        receipt = _json(path)
        if receipt.get('status') != 'ARCHIVE_VERIFIED' or receipt.get('run_id') != row['run_id']:
            raise ValueError('Archive receipt is not a completed matching run')
        root = path.parent
        for relative, identity in receipt['retained_files'].items():
            pins.register_retained(path, relative, identity['sha256'])
        receipts[row['run_id']] = (root, receipt)
        if ordinal % 256 == 0 or ordinal == len(records):
            print(json.dumps({'phase': 'RECEIPT_CATALOG', 'completed': ordinal, 'total': len(records),
                'retained_reference_policy': 'producer_seal_registration_then_consumption_verification'}), flush=True)
    return receipts


def verify_resolved_indices(records, evaluations, resolved_root, pins):
    """Bind every FINAL field to the controller's original producer records.

    Canonical JSON comparison ignores object-key order only; it retains list
    order and scalar types (including bool versus int), without tolerances.
    No source row is enriched, normalized, or replaced during this check.
    """
    root = Path(resolved_root)
    native = {r['run_id']: r for r in records}
    slots = {(r['run_id'], r['evaluator_version']): r for r in evaluations}
    if len(native) != len(records) or len(slots) != len(evaluations):
        raise ValueError('Duplicate FINAL identity in resolved-record comparison')
    if set(slots) != {(run, version) for run in native for version in pack.VERSIONS}:
        raise ValueError('FINAL evaluator coverage differs from resolved native identities')
    def same(left, right):
        return pack._json_bytes(left) == pack._json_bytes(right)
    for ordinal, (run_id, final) in enumerate(native.items(), 1):
        pack.safe_member(run_id)
        if len(Path(run_id).parts) != 1:
            raise ValueError('Resolved run identifier cannot contain a directory')
        run_path = root/run_id/'RUN_RECORD.json'
        evaluation_path = root/run_id/'EVALUATION_RECORDS.json'
        if not same(_json(run_path), final):
            raise ValueError('FINAL native row differs from controller producer: '+run_id)
        own = _json(evaluation_path)
        if not isinstance(own, list) or len(own) != 2:
            raise ValueError('Controller producer must retain exactly two evaluator rows')
        seen = set()
        for row in own:
            key = row['run_id'], row['evaluator_version']
            if key[0] != run_id or key in seen or key not in slots or not same(row, slots[key]):
                raise ValueError('FINAL evaluation row differs from controller producer: '+run_id)
            seen.add(key)
        for path in (run_path, evaluation_path):
            pins.capture_metadata(path, 'controller_original_resolved_record_compared_exactly')
        if ordinal % 256 == 0 or ordinal == len(native):
            print(json.dumps({'phase': 'FINAL_VS_RESOLVED', 'completed': ordinal, 'total': len(native)}), flush=True)
    return {'status': 'PASS', 'native_rows': len(native), 'evaluation_rows': len(slots),
            'comparison': 'all fields; canonical JSON exact equality; no numerical tolerance',
            'source_rows_modified': False}


def load_new_diagnostics(stage, records, receipts, pins):
    result = {name: [] for name in ('evaluations', 'consistency_rows', 'segment_rows', 'body_rows')}
    selected = [r for r in records if diagnostics._natural(r)]
    if len(selected) != 30:
        raise ValueError('New diagnostic identities must be 3 datasets x 10 profiles')
    for record in selected:
        path = Path(stage)/'DIAGNOSTICS'/f"{record['run_id']}.json"
        payload = _json(path)
        root, receipt = receipts[record['run_id']]
        for version in pack.VERSIONS:
            prefix = version+'/P13_DIAGNOSTICS/'
            match = [rel for rel in receipt['retained_files'] if rel.startswith(prefix) and rel.endswith('/DIAGNOSTIC_ROWS.json')]
            if not match:
                match = [rel for rel in receipt['retained_files'] if rel.startswith(version+'/') and rel.endswith('/P13_DIAGNOSTICS/DIAGNOSTIC_ROWS.json')]
            if len(match) != 1:
                raise ValueError('Archived diagnostic payload absent or ambiguous')
            archived = _json(pins.check(root/match[0]))
            own = [r for r in payload['evaluations'] if r['evaluator_version'] == version]
            if own != [archived['evaluation']]:
                raise ValueError('Main DIAGNOSTICS evaluation differs from archived sidecar')
            for key in ('consistency_rows', 'segment_rows', 'body_rows'):
                own_rows = [r for r in payload[key] if r['evaluator_version'] == version]
                if own_rows != archived[key]:
                    raise ValueError('Main diagnostic table differs from archived sidecar: '+key)
        pins.capture_metadata(path, 'new_diagnostics_compared_to_archived_seals')
        for key in result:
            result[key].extend(payload[key])
    for version in pack.VERSIONS:
        for key, count in (('evaluations', 30), ('segment_rows', 280), ('body_rows', 30), ('consistency_rows', 120)):
            if sum(r['evaluator_version'] == version for r in result[key]) != count:
                raise ValueError('New diagnostic count mismatch: '+version+'/'+key)
    return result


def frozen_f01_diagnostics(reg, baseline_records, pins):
    selected = [r for r in baseline_records if r['method_id'] == 'F01' and diagnostics._natural(r)]
    if len(selected) != 3:
        raise ValueError('Exactly three formal v2 F01 natural records required')
    by_dataset = {r['dataset_id']: r for r in selected}
    root = resolve(CAL, reg)
    for dataset, record in by_dataset.items():
        native = root/'03_CALIBRATED_RUNS'/('CLEAN5_CALIBRATED_'+dataset+'_F01')
        for name in ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt'):
            pins.add(native/name, record['output_seal'][name]['sha256'], 'F01_CAL_full_output_matches_formal_v2')
    result = {'segment_rows': [], 'body_rows': [], 'table_pins': []}
    for (version, role), (relative, digest) in F01_TABLES.items():
        path = pins.add(root/relative, digest, 'frozen_P06_F01_only_diagnostic_table')
        rows = [r for r in read_csv(path) if r['method_id'] == 'F01']
        if len(rows) != (28 if role == 'segment_rows' else 3):
            raise ValueError('Frozen F01 diagnostic table coverage differs')
        for row in rows:
            record = by_dataset[row['dataset_id']]
            result[role].append({**row, 'run_id': record['run_id'], 'case_id': record['case_id'],
                'effective_configuration_id': pack.effective_configuration(record), 'evaluator_version': version,
                'formal_F01_reused': True, 'source_protocol': pack.F01_PROTOCOL,
                'source_table': str(path), 'source_table_sha256': digest,
                'data_mode': record['data_mode'], 'synthetic_data_used': False,
                'semisynthetic_data_used': False, 'trace_used_online': False})
        result['table_pins'].append({'path': str(path), 'sha256': digest, 'role': role, 'evaluator_version': version})
    return result


def baseline_consistency(stage, reg, baseline_records, baseline_evaluations, receipts, pins):
    result = diagnostics.old_h7_rows(baseline_records, baseline_evaluations, calibrated_root=resolve(CAL, reg))
    for item in result['source_pins']:
        pins.add(item['path'], item['sha256'], 'exact_frozen_P05_H7_input')
    native = {r['run_id']: r for r in baseline_records}
    gate = _json(Path(stage)/'01_BINARY_BRIDGE/BINARY_BRIDGE_RESULT.json')
    if gate.get('status') != 'PASS' or gate.get('passed_comparisons') != 44:
        raise ValueError('BY2 H7 bridge STD requires the completed binary bridge')
    replacements = {}
    for row in result['evaluations']:
        if row.get('h7_reference_status') != 'INCOMPLETE' or row['dataset_id'] != 'BY2':
            continue
        record = native[row['run_id']]
        old = Path(stage)/'01_BINARY_BRIDGE'/row['method_id']/'old'
        terminal = _json(old/'BRIDGE_RUN_TERMINAL.json')
        expected = record['output_seal']['KF_GINS_STD.txt']['sha256']
        if terminal.get('terminal_status') != 'COMPLETED' or terminal['files']['KF_GINS_STD.txt']['sha256'] != expected:
            raise ValueError('BY2 bridge old STD does not match the formal v2 full-output seal')
        source = pins.add(old/'KF_GINS_STD.txt', expected, 'BY2_original_STD_bridge_matches_formal_v2')
        result['source_pins'].append({'path': str(source), 'sha256': expected,
            'native_uncompressed_sha256': expected, 'full_STD_verified_against_v2_seal': True,
            'source_scope': 'previously completed OLD binary bridge'})
        errors = pack._series_path(row)
        pins.check(errors)
        std = diagnostics.canonical._read_numeric_table(source).to_numpy(float)
        values = diagnostics.consistency(pd.read_csv(errors), std)
        enriched = {**row, **values, 'h7_reference_status': 'AVAILABLE_EXACT_V2_FULL_STD',
                    'h7_reference_definition': diagnostics.DEFINITION, 'old_solver_rerun': False,
                    'source_scope': 'already executed binary bridge OLD STD; SHA equals formal v2 output'}
        replacements[(row['run_id'], row['evaluator_version'])] = enriched
    result['evaluations'] = [replacements.get((r['run_id'], r['evaluator_version']), r) for r in result['evaluations']]
    result['missing'] = [r for r in result['missing'] if (r['run_id'], r['evaluator_version']) not in replacements]
    result['consistency_rows'] = [r for r in result['consistency_rows'] if (r['run_id'], r['evaluator_version']) not in replacements]
    for row in replacements.values():
        result['consistency_rows'].extend(diagnostics.consistency_rows(row, diagnostics._identity(native[row['run_id']], row)))
    result['status'] = 'COMPLETE' if not result['missing'] else 'INCOMPLETE'
    result['missing_hypotheses_reported_without_substitution'] = True
    return result


def residual_rows(p11b, p12, validations, *, input_pins):
    """Expose audited scalar values without pooling RP windows or fitting signs."""
    rows = []
    def stats(dataset, sensor, correction, values, *, path, sha256, window='matched_P11b', interval=None):
        for axis, fields in values.items():
            for name, value in fields.items():
                if isinstance(value, bool) or value is None:
                    continue
                if not isinstance(value, (int, float)):
                    continue
                if not math.isfinite(value):
                    raise ValueError('Nonfinite scalar in frozen sensor residual audit')
                rows.append({'dataset_id': dataset, 'sensor': sensor, 'axis': axis,
                    'correction_stage': 'before' if correction == 'before' else 'v21_final',
                    'correction_detail': correction, 'statistic': name, 'value': value,
                    'unit': 'count' if name == 'n' else ('m/s' if sensor == 'HV' else 'deg'),
                    'window_id': window, 'window_start_s': interval[0] if interval else None,
                    'window_end_s': interval[1] if interval else None, 'n': fields.get('n'),
                    'source_path': path, 'source_sha256': sha256, 'source_statistic': name})
    if set(validations) != set(diagnostics.DATASETS):
        raise ValueError('Three new provider residual validations are required')
    for dataset in diagnostics.DATASETS:
        validation = validations[dataset]
        difference = validation.get('maximum_absolute_difference', math.inf)
        if validation.get('passed') is not True or not math.isfinite(difference) or difference > 1e-6:
            raise ValueError('HV/RP reproduction gate must pass before finalization')
        before = p11b['sequences'][dataset]['hypotheses']['H-C']
        stats(dataset, 'HV', 'before', before['axes_mps'], **input_pins['p11b'])
        stats(dataset, 'HV', 'v21_scaled', validation['HV_final_scaled']['axes_mps'], **input_pins[dataset])
        for correction, values, source in (('before', before, input_pins['p11b']),
                ('v21_scaled', validation['HV_final_scaled'], input_pins[dataset])):
            stats(dataset, 'HV', correction, {'horizontal': {k: values[k] for k in
                ('n', 'sigma_HV_mps', 'mean_NE_norm_mps') if k in values}}, **source)
        old = p12['sequences'][dataset]['static_windows']
        new = {r['name']: r for r in validation['RP_static']}
        if len(new) != len(validation['RP_static']) or set(new) != {r['name'] for r in old}:
            raise ValueError('RP old/new static-window identities differ')
        for window in old:
            current = new[window['name']]
            if current.get('interval_s') != window.get('interval_s') or current.get('n') != window.get('n'):
                raise ValueError('RP old/new window support differs')
            if window.get('interval_s') is None:
                continue
            kwargs = {'window': window['name'], 'interval': window['interval_s']}
            stats(dataset, 'RP', 'before', window['RP_frozen_minus_gravity_deg'], **input_pins['p12'], **kwargs)
            stats(dataset, 'RP', 'v21', current['residual_deg'], **input_pins[dataset], **kwargs)
    return rows


def quality_rows(path):
    """GNSS observation metadata projection; no evaluator or truth input."""
    rows = []
    with Path(path).open() as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            tokens = line.split()
            if len(tokens) != 18 or tokens[17] not in ('0', '1') or tokens[14] != '2.933193':
                raise ValueError('Sequence-quality source must be the nominal corrected GNSS18')
            rows.append({'time': tokens[0], 'yaw_deg': tokens[13], 'yaw_std_deg': tokens[14],
                         'valid': tokens[17], 'source_row': number})
    if not rows:
        raise ValueError('Sequence quality projection is empty')
    return rows


def downstream_tables(rows):
    tables = {}
    for version in pack.VERSIONS:
        own = [r for r in rows if r['evaluator_version'] == version]
        ladder = [dict(r) for r in own if r['diagnostic_family'] == 'LADDER']
        grid = [dict(r) for r in own if r['diagnostic_family'] == 'NOISE_GRID']
        expected = {(variant, method) for variant in downstream.LADDER for method in downstream.METHODS}
        if len(ladder) != 12 or {(r['variant_id'], r['method_id']) for r in ladder} != expected:
            raise ValueError('Downstream ladder coverage must be six variants x two methods')
        if len(grid) != 9 or len({r['variant_id'] for r in grid}) != 9 or {r['method_id'] for r in grid} != {'A04'}:
            raise ValueError('Downstream grid coverage must be nine original A04 cells')
        for row in (*ladder, *grid):
            row.setdefault('effective_configuration_id', pack.effective_configuration(row))
            row.update(protocol_id=pack.PROTOCOL, source_protocol=pack.PROTOCOL)
        for row in grid:
            cell = row['grid_cell']
            for field in ('abstd_mGal', 'vrw_mps_sqrt_hour'):
                if field not in cell:
                    raise ValueError('Downstream grid missing its registered noise parameter')
                row[field] = cell[field]
            row['cell_id'] = cell.get('cell_id', row['variant_id'])
        tables[version] = {'ladder': ladder, 'grid': grid}
    return tables


def _retained(record, name, pins):
    root = Path(record['output_root'])
    found = [path for path in (root/name, root/(name+'.gz')) if path.is_file()]
    if len(found) != 1:
        raise ValueError('Expected exactly one retained native source: '+name)
    return str(pins.check(found[0]))


def vchk_inputs(reg, records, evaluations, pins):
    root = resolve(downstream.VCHK_ROOT, reg)
    for name, digest in downstream.VCHK_PINS.items():
        pins.add(root/name, digest, 'frozen_VCHK_definition')
    catalog = _json(root/'INPUT_CATALOG.json')
    ledger = {str(resolve(row['path'], reg)): row['sha256'] for row in read_csv(root/'INPUT_HASH_LEDGER.csv')}
    for source in catalog['diagnostics'].values():
        path = resolve(source, reg)
        pins.add(path, ledger[str(path)], 'frozen_VCHK_input_diagnostics')
    new = {}
    for dataset in diagnostics.DATASETS:
        record = next(r for r in records if diagnostics._natural(r) and r['dataset_id'] == dataset and r['method_id'] == 'A04')
        row = next(r for r in evaluations if r['run_id'] == record['run_id'] and r['evaluator_version'] == 'v3')
        entry = dict(next(r for r in catalog['runs'] if (r['sequence'], r['method'], r['chain']) == (dataset, 'A04', 'CAL')))
        entry.update(error_series=str(pins.check(pack._series_path(row))),
                     manifest=_retained(record, 'RUN_MANIFEST.json', pins),
                     gnss_update_trace=_retained(record, 'PORT_GNSS_UPDATE_TRACE.csv', pins),
                     evaluator_version='v3', original_catalog_evaluator_version='v2')
        new[dataset] = entry
    return new


def _bundle_pin(stage, dataset, pins):
    path = Path(stage)/'02_BASE_PROVIDERS'/dataset/'PROVIDER_BUNDLE.json'
    if not path.is_file():
        path = Path(stage)/'02_BASE_PROVIDERS'/dataset/'BASE_PROVIDER_BUNDLE.json'
    sealpath = path.parent/'PROVIDER_SEAL.json'
    seal = _json(sealpath)
    if seal.get('status') != 'SEALED':
        raise ValueError('Base provider seal is incomplete')
    pins.capture_metadata(sealpath, 'v21_completed_provider_seal')
    pins.add(path, seal['files_sha256'][path.name], 'sealed_v21_provider_bundle')
    bundle = _json(path)
    return bundle


def emit_diagnostics(stage, output, reg, v21, records, evaluations, down_evaluations,
                     new_sidecars, f01, old_h7, pins):
    output = Path(output)
    members = []
    def emit(member, payload, role):
        path = write_once(output/member, pack._csv_bytes(payload) if member.endswith('.csv') else payload, pins)
        members.append({'member': member, 'source': str(path), 'sha256': pins.values[str(path)], 'role': role})
        return path
    tables = downstream_tables(down_evaluations)
    segments = new_sidecars['segment_rows']+f01['segment_rows']
    body = new_sidecars['body_rows']+f01['body_rows']
    for version in pack.VERSIONS:
        if sum(r['evaluator_version'] == version for r in segments) != 308 or sum(r['evaluator_version'] == version for r in body) != 33:
            raise ValueError('Formal sequence diagnostics do not close to 308 segments/33 body rows')
        prefix = 'supplemental/V21/'
        emit(prefix+'LADDER/'+version+'/UNIQUE_EVALUATION_RESULTS.csv', tables[version]['ladder'], 'ladder')
        emit(prefix+'NOISE_GRID/'+version+'/SENSITIVITY_GRID.csv', tables[version]['grid'], 'nine_grid')
        emit(prefix+'SEQUENCES/'+version+'/BODY_FRAME_BIAS.csv', [r for r in body if r['evaluator_version'] == version], 'body_frame_bias')
        emit(prefix+'SEQUENCES/'+version+'/WINDOW_SEGMENT_SUMMARY.csv', [r for r in segments if r['evaluator_version'] == version], 'sequence_segments')
        emit(prefix+'SEQUENCES/'+version+'/CONSISTENCY_ROWS.csv',
             [r for r in new_sidecars['consistency_rows'] if r['evaluator_version'] == version], 'sequence_consistency')
    emit('supplemental/V21/OLD_H7_REFERENCE_STATUS.json', old_h7, 'sequence_consistency')
    validations, input_pins = {}, {}
    for label in ('p11b', 'p12'):
        spec = v21['frozen_identities'][label]
        source = pins.add(resolve(spec['path'], reg), spec['sha256'], 'frozen_residual_audit')
        input_pins[label] = {'path': str(source), 'sha256': spec['sha256']}
    for dataset in diagnostics.DATASETS:
        bundle = _bundle_pin(stage, dataset, pins)
        if bundle['dataset_id'] != dataset or bundle['sensor_model_group_hash'] != v21['sensor_model_group_hash']:
            raise ValueError('Provider diagnostic dataset or SENSOR_MODEL_V21 group differs')
        source = Path(stage)/'02_BASE_PROVIDERS'/dataset/'PROVIDER_VALIDATION.json'
        # The base bundle gate has the validation identity where available;
        # otherwise the per-sequence BASE_PROVIDER_SEAL locks it explicitly.
        seals = [Path(stage)/'02_BASE_PROVIDERS'/dataset/name for name in ('BASE_PROVIDER_SEAL.json', 'PROVIDER_SEAL.json')]
        sealpath = next((p for p in seals if p.is_file()), None)
        if sealpath is not None:
            seal = _json(sealpath)
            filepins = seal.get('files_sha256', seal.get('files', {}))
            entry = filepins.get('PROVIDER_VALIDATION.json')
            digest = entry.get('sha256') if isinstance(entry, dict) else entry
        else:
            digest = bundle.get('validation_sha256')
        if not digest:
            raise ValueError('Provider validation lacks an independent producer seal')
        pins.add(source, digest, 'provider_reproduction_gate')
        validations[dataset] = _json(source)
        input_pins[dataset] = {'path': str(source), 'sha256': digest}
        spec = bundle['providers']['gnsspath']
        gnss = pins.add(spec['path'], spec['sha256'], 'new_nominal_GNSS18_quality_projection')
        emit('supplemental/SEQUENCE_QUALITY/'+dataset+'.csv', quality_rows(gnss), 'sequence_quality')
    residuals = residual_rows(_json(input_pins['p11b']['path']), _json(input_pins['p12']['path']), validations, input_pins=input_pins)
    emit('supplemental/V21/SENSOR_RESIDUALS.csv', residuals, 'sensor_residual_validation')
    vchk = downstream.vchk_a04(reg, vchk_inputs(reg, records, evaluations, pins))
    vchk.update(new_evaluator_version='v3', old_catalog_evaluator_version='v2',
                yaw_definition='Unchanged wrapped yaw error; v3 position lever transform does not alter yaw')
    emit('supplemental/V21/VCHK/A04_CHECK.json', vchk, 'vchk_a04')
    for name, rows in vchk['tables'].items():
        emit('supplemental/V21/VCHK/'+name+'.csv', rows, 'vchk_a04')
    contract = yaml.safe_load((reg.code_root/'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml').read_text())
    spec = contract['robustness']
    for role in ('rule', 'old_decision_inputs'):
        pins.add(resolve(spec[role]['path'], reg), spec[role]['sha256'], 'frozen_robustness_'+role)
    robust = downstream.robustness({v: [r for r in segments if r['evaluator_version'] == v] for v in pack.VERSIONS},
        rule=spec['rule'], old=_json(resolve(spec['old_decision_inputs']['path'], reg)))
    emit('supplemental/V21/ROBUSTNESS/CHECK.json', robust, 'robustness')
    emit('supplemental/V21/ROBUSTNESS/CHECK.csv', robust['rows'], 'robustness')
    return {'members': members, 'segment_rows': segments, 'body_rows': body, 'residual_rows': residuals}


def _contract(reg, path, pins, expected=None):
    path = Path(path)
    if expected is None:
        pins.capture_metadata(path, 'current_preregistered_contract')
    else:
        pins.add(path, expected, 'frozen_contract_identity')
    return yaml.safe_load(path.read_text())


def frozen_v21_contract(reg, stage, pins):
    path = Path(stage)/'00_PREREGISTRATION/EXECUTION_FREEZE.json'
    freeze = _json(path)
    if freeze.get('status') != 'COMMITTED_PUSHED_EXECUTION_FREEZE':
        raise ValueError('Main execution contract freeze is not completed')
    pins.capture_metadata(path, 'main_producer_execution_freeze')
    contract = _contract(reg, reg.code_root/'configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml',
                         pins, freeze['contract_hash'])
    if contract['sensor_model_group_hash'] != freeze['sensor_model_group_hash']:
        raise ValueError('Frozen execution SENSOR_MODEL_V21 group differs')
    return contract


def run_finalize(*, reg, stage, output_root, handoff_zip, immutable_package,
                 code_commit, immutable_package_sha256=OLD_PACKAGE_SHA256,
                 build_package=True):
    """Run only after both producer closures pass; no scientific-stage restart.

    ``output_root`` is normally stage/20_FINALIZE. ``build_package=False``
    completes/seals all tables for review without constructing an archive.
    An existing aggregate is reused only after its source-row hashes and full
    file seal match this exact invocation. Existing differing outputs are kept.
    """
    stage, output = Path(stage).absolute(), Path(output_root).absolute()
    if stage != resolve(STAGE, reg) or not output.is_relative_to(stage) or output == stage:
        raise ValueError('Finalization requires the registered stage and its own child output root')
    if any(p.is_symlink() for p in (stage, output, *output.parents)) or '..' in output.parts:
        raise ValueError('Unsafe finalization root')
    pins = Pins()
    main_path = stage/'MAIN_ARCHIVE_CLOSURE.json'
    down_path = stage/'DOWNSTREAM/NATIVE_DIAGNOSTICS_CLOSURE.json'
    main, down = _json(main_path), _json(down_path)
    index_paths = [stage/'FINAL_RUN_RECORDS.json', stage/'FINAL_EVALUATION_RECORDS.json',
                   stage/'DOWNSTREAM/FINAL_RUN_RECORDS.json', stage/'DOWNSTREAM/FINAL_EVALUATION_RECORDS.json']
    records, evaluations, down_records, down_evaluations = map(_json, index_paths)
    closure = closure_gate(main, down, records, evaluations, down_records, down_evaluations)
    pins.add(immutable_package, immutable_package_sha256, 'immutable_combined_v2_package_identity')
    if set(down.get('final_index_pins', {})) != {'FINAL_RUN_RECORDS.json', 'FINAL_EVALUATION_RECORDS.json'}:
        raise ValueError('Downstream closure lacks the two producer final-index pins')
    for name, digest in down['final_index_pins'].items():
        pins.add(stage/'DOWNSTREAM'/name, digest, 'downstream_final_index_producer_seal')
    for path in (main_path, down_path, *index_paths):
        pins.capture_metadata(path, 'completed_native_evaluator_index_or_closure')
    resolved_check = verify_resolved_indices(records, evaluations, stage/'CONTROLLER/RESOLVED_RUNS', pins)
    closure['main_FINAL_matches_controller_producer'] = resolved_check
    contract_path = reg.code_root/'configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml'
    v21 = frozen_v21_contract(reg, stage, pins)
    contracts = {}
    for name in ('core_contract', 'addendum_contract'):
        spec = v21['frozen_identities'][name]
        contracts[name] = _contract(reg, reg.code_root/spec['path'], pins, spec['sha256'])
    v2, addendum = contracts['core_contract'], contracts['addendum_contract']
    baseline = aggregate.load_baseline_indices(v2, addendum, reg)
    for item in baseline['input_pins']:
        pins.add(item['path'], item['sha256'], 'published_v2_baseline_index')
    old_records, old_evaluations = baseline['records'], baseline['evaluations']
    formal_records = [*records, *[dict(r, formal_F01_reused=True) for r in old_records if r['method_id'] == 'F01']]
    formal_evaluations = [*evaluations, *[dict(r, formal_F01_reused=True) for r in old_evaluations if r['method_id'] == 'F01']]
    pack.terminal_identity(formal_records, formal_evaluations)
    receipts = receipt_catalog(records, pins, resolved_root=stage/'CONTROLLER/RESOLVED_RUNS')
    # The downstream controller publishes the same independent receipt references.
    down_resolved = stage/'DOWNSTREAM/CONTROLLER/RESOLVED_RUNS'
    receipt_catalog(down_records, pins, resolved_root=down_resolved)
    baseline_receipts = receipt_catalog(old_records, pins)
    new_sidecars = load_new_diagnostics(stage, records, receipts, pins)
    f01 = frozen_f01_diagnostics(reg, old_records, pins)
    old_h7 = baseline_consistency(stage, reg, old_records, old_evaluations, baseline_receipts, pins)
    emitted = emit_diagnostics(stage, output, reg, v21, records, evaluations, down_evaluations,
                               new_sidecars, f01, old_h7, pins)
    case_spec = v2['sources']['case_registry']
    case_path = pins.add(resolve(case_spec['path'], reg), case_spec['sha256'], 'frozen_541_case_registry')
    aggregate_seal = output/'P13_MACHINE_REPORT/AGGREGATE_SEAL.json'
    if aggregate_seal.exists():
        seal = _json(aggregate_seal)
        if seal.get('status') != 'SEALED':
            raise ValueError('Existing aggregation is not sealed; preserve partial outputs')
        for relative, digest in seal['files_sha256'].items():
            pack.safe_member(relative)
            pins.add(output/relative, digest, 'new_aggregate_producer_seal')
        summary = _json(output/'P13_MACHINE_REPORT/AGGREGATION_SUMMARY.json')
        expected = {'new_evaluations': aggregate._hash_rows(evaluations), 'new_native': aggregate._hash_rows(records),
                    'baseline_evaluations': aggregate._hash_rows(old_evaluations), 'baseline_native': aggregate._hash_rows(old_records)}
        if summary['source_index_hashes'] != expected:
            raise ValueError('Existing aggregation belongs to different input rows')
    else:
        summary = aggregate.aggregate_all(evaluations, records, v21, v2, addendum, output, code_commit,
            baseline_evaluations=old_evaluations, baseline_records=old_records, case_rows=read_csv(case_path),
            consistency_rows=new_sidecars['evaluations'], baseline_consistency_rows=old_h7['evaluations'],
            segment_rows=emitted['segment_rows'])
    seal = _json(aggregate_seal)
    for relative, digest in seal['files_sha256'].items():
        pins.add(output/relative, digest, 'new_aggregate_producer_seal')
    pins.capture_metadata(aggregate_seal, 'new_complete_aggregate_seal')
    write_once(output/'FINALIZATION_CLOSURE_GATE.json', closure, pins)
    write_once(output/'F01_DIAGNOSTIC_REUSE.json', f01['table_pins'], pins)
    write_once(output/'H7_REFERENCE_AVAILABILITY.json', {'status': old_h7['status'], 'missing': old_h7['missing'],
        'no_full_STD_substitution': True}, pins)
    write_once(output/'FINALIZATION_INPUT_PINS.json', pins.rows(), pins)
    evidence = []
    # Contracts, calibration residual audits, producer closure/gates, and the
    # complete source-pin ledger accompany the science without replacing it.
    for label, path in [('SENSOR_MODEL_V21_CONTRACT.yaml', contract_path),
                        ('MAIN_ARCHIVE_CLOSURE.json', main_path),
                        ('DOWNSTREAM_ARCHIVE_CLOSURE.json', down_path),
                        ('FINALIZATION_INPUT_PINS.json', output/'FINALIZATION_INPUT_PINS.json'),
                        ('F01_DIAGNOSTIC_REUSE.json', output/'F01_DIAGNOSTIC_REUSE.json'),
                        ('H7_REFERENCE_AVAILABILITY.json', output/'H7_REFERENCE_AVAILABILITY.json')]:
        evidence.append({'member': 'evidence/'+label, 'source': str(path), 'sha256': pins.values[str(path)]})
    for label in ('p11b', 'p12'):
        source = resolve(v21['frozen_identities'][label]['path'], reg)
        evidence.append({'member': 'evidence/'+label+'.json', 'source': str(source), 'sha256': pins.values[str(source)]})
    for dataset in diagnostics.DATASETS:
        source = stage/'02_BASE_PROVIDERS'/dataset/'PROVIDER_VALIDATION.json'
        evidence.append({'member': 'evidence/'+dataset+'_PROVIDER_VALIDATION.json', 'source': str(source), 'sha256': pins.values[str(source)]})
    result = {'status': 'PASS_FINALIZED_TABLES_PENDING_PACKAGE', 'protocol_id': pack.PROTOCOL,
        'code_commit': code_commit, 'output_root': str(output), 'closure': closure,
        'aggregate_status': summary['status'], 'H7_reference_status': old_h7['status'],
        'outcome_changed': False, 'new_outcome_created': False, 'provider_calls': 0,
        'native_calls': 0, 'evaluator_calls': 0, 'reference_trace_payload_reads': 0,
        'data_mode': 'real_and_controlled_degradation', 'synthetic_data_used': False,
        'semisynthetic_data_used': True, 'trace_used_online': False}
    if build_package:
        complete = output/'FINALIZE_COMPLETE.json'
        if complete.exists():
            previous = _json(complete)
            validation = pack.validate_archive(handoff_zip)
            if previous.get('package', {}).get('sha256') != validation['sha256']:
                raise ValueError('Existing package differs from completed finalize record')
            return previous
        package = pack.build_handoff(stage, handoff_zip, formal_records, formal_evaluations,
            aggregate_root=output, source_pins=pins.values, immutable_package=immutable_package,
            immutable_package_sha256=immutable_package_sha256, diagnostic_members=emitted['members'],
            evidence_members=evidence, evidence_roots=(stage, reg.code_root, resolve(CAL, reg).parent/'CLEAN6_HV_PRIOR_CALIBRATION'),
            code_commit=code_commit)
        result.update(status='PASS_FINALIZED_V21_HANDOFF', package=package)
        write_once(complete, result, pins)
    else:
        write_once(output/'FINALIZE_TABLES_COMPLETE.json', result, pins)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--stage', default=STAGE)
    parser.add_argument('--output-root', default=STAGE+'/20_FINALIZE')
    parser.add_argument('--handoff-zip', required=True)
    parser.add_argument('--immutable-package', required=True)
    parser.add_argument('--immutable-package-sha256', default=OLD_PACKAGE_SHA256)
    parser.add_argument('--code-commit', required=True)
    parser.add_argument('--tables-only', action='store_true')
    args = parser.parse_args(argv)
    reg = registry(args.local_config)
    paths = yaml.safe_load(Path(args.local_config).read_text())['paths']
    def cli_path(value):
        for key, path in paths.items():
            if isinstance(path, str):
                value = value.replace('<'+key.upper()+'>', path)
        return resolve(value, reg)
    result = run_finalize(reg=reg, stage=cli_path(args.stage), output_root=cli_path(args.output_root),
        handoff_zip=cli_path(args.handoff_zip), immutable_package=cli_path(args.immutable_package),
        immutable_package_sha256=args.immutable_package_sha256, code_commit=args.code_commit,
        build_package=not args.tables_only)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
