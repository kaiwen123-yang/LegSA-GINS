"""Append separately registered addendum and display sources to a frozen core ZIP.

No solver, evaluator, provider generation, or metric recomputation is performed.
The original core members (including its identity probe) remain byte-identical.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

import pandas as pd
import yaml

from ..manifest import sha256_file
from .pack import SERIES_COLS, _gz_frame, _json, _safe_file, validate_archive

BASE_PACKAGE_SHA256 = '30e6e263922ed317db0bc6e1cabe4b38d576bd0ec501e1f8f7b45fffa94beefb'


def safe_member(name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name:
        raise ValueError('Unsafe package member: ' + name)
    return p


class Sources:
    def __init__(self, target, clean_root):
        self.target = Path(target)
        self.clean_root = Path(clean_root).resolve()
        self.rows = []

    def record(self, source, member, policy='byte-identical', **extra):
        source = _safe_file(source, self.clean_root)
        dest = self.target / safe_member(member)
        self.rows.append(dict(source='<CLEAN_ROOT>/' + source.relative_to(self.clean_root).as_posix(),
                              source_sha256=sha256_file(source), member=member,
                              member_sha256=sha256_file(dest), policy=policy, **extra))

    def copy(self, source, member):
        source = _safe_file(source, self.clean_root)
        dest = self.target / safe_member(member)
        if dest.exists():
            if sha256_file(dest) != sha256_file(source):
                raise ValueError('Refuse package member overwrite: ' + member)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as src, dest.open('xb') as out:
                shutil.copyfileobj(src, out)
        self.record(source, member)

    def series(self, source, member):
        source = Path(source)
        if source.is_dir():
            options = [source / 'FROZEN_EVALUATOR/error_series.csv.gz',
                       source / 'FROZEN_EVALUATOR/error_series.csv',
                       source / 'error_series.csv.gz', source / 'error_series.csv']
            source = next((p for p in options if p.is_file()), source)
        source = _safe_file(source, self.clean_root)
        frame = pd.read_csv(source, usecols=SERIES_COLS)
        selected = frame.iloc[::20]
        _gz_frame(selected, self.target / safe_member(member))
        self.record(source, member, 'every 20th existing row; display only; no interpolation',
                    rows_full=len(frame), rows_kept=len(selected), source_row_first=2,
                    source_row_stride=20)
        return {'source_sha256': self.rows[-1]['source_sha256'],
                'rows_full': len(frame), 'rows_kept': len(selected)}


def _csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)


def _manifest(target, relative, rows):
    dest = target / safe_member(relative)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(dest)
    pd.DataFrame(rows).to_csv(dest, index=False)


def append_core_display(sources, stage):
    """Add missing module/D05 curves without replacing the original subset."""
    unique_path = stage / '12_OFFLINE_EVALUATION/v3/UNIQUE_EVALUATION_RESULTS.csv'
    unique = _csv(unique_path)
    selected = unique[unique.degradation_id.isin(['D04', 'D05', 'D12', 'D27', 'D58', 'D60'])]
    rows = []
    for ix, row in selected.iterrows():
        item = {k: row[k] for k in ('run_id', 'case_id', 'degradation_id', 'seed_id',
                                    'method_id', 'effective_configuration_id')}
        item.update(evaluator_version='v3', source_table_row=int(ix)+2,
                    status=row['evaluation_status'])
        if row['evaluation_status'] == 'COMPLETED':
            member = f'core_supplement_error_series/v3/{row["run_id"]}.csv.gz'
            item.update(member=member, **sources.series(row['error_series_source'], member))
            item['status'] = 'OK'
        rows.append(item)
    _manifest(sources.target, 'CORE_SUPPLEMENT_SERIES_MANIFEST.csv', rows)
    failed_cases = set(unique.loc[unique.evaluation_status == 'NOT_RUN_ALGORITHM_FAILURE', 'case_id'])
    timelines = unique[(unique.evaluation_status == 'NOT_RUN_ALGORITHM_FAILURE')
                       | (unique.case_id.isin(failed_cases) & (unique.method_id == 'F02'))
                       | (unique.case_id == 'C00_clean_normal')]
    timeline_rows = []
    for ix, row in timelines.iterrows():
        source = Path(row['output_root']) / 'PORT_GNSS_UPDATE_TRACE.csv.gz'
        item = {k: row[k] for k in ('run_id', 'case_id', 'method_id', 'evaluation_status')}
        item['source_table_row'] = int(ix)+2
        if source.is_file():
            member = f'supplemental/FAILURE_SERIES/{row["run_id"]}.csv.gz'
            sources.copy(source, member)
            item.update(status='OK', member=member)
        else:
            item['status'] = 'UNAVAILABLE_NATIVE_TIMELINE'
        timeline_rows.append(item)
    _manifest(sources.target, 'supplemental/FAILURE_SERIES/SERIES_MANIFEST.csv', timeline_rows)


def append_addendum(sources, stage):
    terminal = json.loads(_safe_file(stage/'FINAL_STATUS.json', sources.clean_root).read_text())
    if (terminal.get('terminal_status') != 'PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE'
            or terminal.get('native_terminal_count') != 495
            or terminal.get('evaluation_terminal_count') != 990
            or terminal.get('archive_pending') != 0
            or terminal.get('native_retry_count') != 0
            or terminal.get('evaluator_retry_count') != 0):
        raise ValueError('Addendum must have complete, sealed, zero-pending terminals')
    seal = json.loads(_safe_file(stage/'FINAL_RECORD_SEAL.json', sources.clean_root).read_text())
    if seal.get('status') != 'SEALED':
        raise ValueError('Addendum final record seal missing')
    for relative, identity in seal['files'].items():
        source = _safe_file(stage/safe_member(relative), stage)
        if source.stat().st_size != identity['size_bytes'] or sha256_file(source) != identity['sha256']:
            raise ValueError('Addendum sealed record changed: ' + relative)
    probes, all_series = {}, []
    for version in ('v3', 'v2'):
        aggregate = stage / '13_AGGREGATE_ADDENDUM' / version
        unique = _csv(aggregate / 'UNIQUE_EVALUATION_RESULTS.csv')
        logical = _csv(aggregate / 'LOGICAL_EVALUATION_RESULTS.csv')
        if (len(unique) != 495 or len(logical) != 585 or unique.case_id.nunique() != 45
                or unique.duplicated(['case_id', 'effective_configuration_id']).any()
                or unique.effective_configuration_id.nunique() != 11):
            raise ValueError('Addendum identity counts/uniqueness differ')
        for column in ('outage_end_horizontal_error_m', 'max_horizontal_error_in_window_m'):
            if column not in unique:
                raise ValueError('Missing preregistered addendum metric: ' + column)
        if set(unique.semisynthetic_data_used.str.lower()) - {'true'}:
            raise ValueError('Injected addendum rows must disclose semisynthetic data')
        for source in sorted(aggregate.iterdir()):
            if source.is_file() and source.suffix in ('.csv', '.json', '.md'):
                sources.copy(source, '13_AGGREGATE_ADDENDUM/' + version + '/' + source.name)
        series = []
        for ix, row in unique.iterrows():
            item = {k: row.get(k, '') for k in ('run_id', 'case_id', 'case_family', 'degradation_id',
                        'degradation_type_id', 'seed_id', 'seed_index', 'method_id',
                        'effective_configuration_id', 'duration_s', 'outage_start_s', 'outage_end_s')}
            item.update(evaluator_version=version, status=row['evaluation_status'], source_table_row=int(ix)+2)
            if row['evaluation_status'] == 'COMPLETED':
                member = f'addendum_error_series_subset/{version}/{row["run_id"]}.csv.gz'
                item.update(member=member, **sources.series(row['error_series_source'], member), status='OK')
            series.append(item)
        _manifest(sources.target, f'addendum_error_series_subset/{version}/SUBSET_MANIFEST.csv', series)
        all_series.extend(series)
        probes[version] = dict(unique_rows=len(unique), logical_rows=len(logical), cases=45,
                               configurations=11, statuses=unique.evaluation_status.value_counts().to_dict())
    # Only small provenance records, never provider payloads or raw/NAV/STD files.
    names = {'PROVIDER_BUNDLE.json', 'SEMANTIC_EVIDENCE.json', 'SEMANTIC_VALIDATION.json',
             'PROTOCOL_V2_EFFECT_VALIDATION.json', 'PROVIDER_EFFECT.json', 'BATCH_RESULT.json',
             'BATCH_ARCHIVE_GATE.json', 'CLEANUP_COMPLETE.json', 'CHECKPOINT_RESULT.json',
             'CHECKPOINT_STRACE_AUDIT.json', 'EXECUTION_COMPLETE.json', 'ADDENDUM_TERMINAL.json',
             'CODE_FREEZE.json', 'PREREGISTRATION.json', 'BATCH_LEDGER.jsonl',
             'CASE_MATRIX.csv', 'CASE_MANIFEST.csv', 'SOURCE_MAPPING.csv', 'FAILURE_COUNTS.csv',
             'FINAL_STATUS.json', 'FINAL_RECORD_SEAL.json', 'EXECUTION_FREEZE.json',
             'CASE_REGISTRY.csv', 'UNIQUE_RUN_REGISTRY.csv', 'PROVIDER_AUDIT.json',
             'PROVIDER_OUTPUT_SEAL.json', 'BATCH_COMPLETE.json', 'RESOURCE_SUMMARY.json',
             'PROVIDER_DIFF_SUMMARY.json', 'EXACT_CLEANUP_LEDGER.jsonl',
             'SOLVER_RECORDS.json', 'EVALUATION_RECORDS.json', 'ARCHIVE_RECEIPT.json',
             'RESOLVED_RUN_RECORDS.json', 'RESOLVED_EVALUATION_RECORDS.json',
             'PROVIDER_MAPPING.csv', 'NATIVE_IDENTITY_MAPPING.csv',
             'ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml', 'ADDENDUM_NATIVE_IDENTITY_TRANSPORT.md',
             'ADDENDUM_METRIC_WORDING_ERRATUM.md',
             'ADDENDUM_ARCHIVE_IO_CONTINUATION.md',
             'ARCHIVE_IO_INTERRUPT_REQUEST.json', 'ARCHIVE_IO_INTERRUPT_TERMINAL.json',
             'INTERRUPT_SCENE_SNAPSHOT.json', 'REUSED_SCIENCE_RECORDS.json',
             'STOPPED.json', 'CURRENT_POST_STOP_EVALUATION_SNAPSHOT.json',
             'RECOVERED_FIRST_EVALUATION.json', 'UNSTARTED_EVALUATION_IDENTITIES.json',
             'OWNED_STORAGE_LEDGER.jsonl',
             'ADDENDUM_EVALUATION_RESULT.json', 'ADDENDUM_DERIVED_METRICS.json',
             'EVALUATION_OUTPUT_SEAL.json'}
    metadata_roots = {'00_PREREGISTRATION', '01_CHECKPOINTS', '01_PROVIDER_AUDIT',
                      '01_EVALUATION_CALLS', 'BATCHES', 'CONTINUATIONS'}
    for source in sorted(stage.rglob('*')):
        relative = source.relative_to(stage)
        is_small_record = (relative.parts[0] in metadata_roots
                           and source.suffix in {'.json', '.jsonl', '.csv', '.yaml', '.md'})
        if source.is_file() and (source.name in names or source.name.startswith('CLEANUP_LEDGER') or is_small_record):
            if source.stat().st_size > 20_000_000:
                raise ValueError('Unexpectedly large provenance member')
            sources.copy(source, 'addendum_provenance/' + source.relative_to(stage).as_posix())
    sources.copy(stage/'00_PREREGISTRATION/CASE_REGISTRY.csv', 'found/ADDENDUM_CASE_MANIFEST.csv')
    _manifest(sources.target, 'addendum_error_series_subset/SUBSET_MANIFEST.csv', all_series)
    _json(sources.target / 'ADDENDUM_IDENTITY_PROBE.json', dict(passed=True, versions=probes,
          core_aggregate_members_changed=0, metric_recomputation_performed=False,
          data_mode='semisynthetic', synthetic_data_used=False, semisynthetic_data_used=True,
          label='ADDENDUM_FAMILIES_A1_A2 — pre-registered 2026-09-13, added after the 541-core results were seen, to cover a scenario absent from the library'))


def append_supplements(sources, code_root):
    clean = sources.clean_root
    stages = clean / 'stages'
    aliases = {'CALIBRATED': stages / 'CLEAN5_CALIBRATED_SENSOR_MODEL',
               'PARITY': stages / 'CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF'}
    required = {
        'CALIBRATED': ['08_AGGREGATE/v3/UNIQUE_EVALUATION_RESULTS.csv',
                      '08_AGGREGATE/v3/BODY_FRAME_BIAS.csv',
                      '08_AGGREGATE/v3/EXTERNAL_BY2_V3_REFERENCE.csv',
                      '08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.csv',
                      '08_AGGREGATE/FROZEN_SENSOR_MODEL.csv',
                      '00_CALIBRATION/LAG_VARIANCE_FIT.csv', '00_CALIBRATION/CALIBRATED_PARAMETERS.csv'],
        'PARITY': ['12_PARITY_GENERALIZATION/08_AGGREGATE/PARITY_DECOMPOSITION_BY_VERSION.csv',
                   '12_PARITY_GENERALIZATION/08_AGGREGATE/v3/UNIQUE_EVALUATION_RESULTS.csv',
                   '13_NOISE_MODEL_SENSITIVITY/08_AGGREGATE/v3/SENSITIVITY_GRID.csv']}
    missing = []
    for alias, files in required.items():
        for rel in files:
            source = aliases[alias] / rel
            if source.is_file():
                sources.copy(source, f'supplemental/{alias}/{rel}')
            else:
                missing.append(dict(source=f'<{alias}>/{rel}', status='UNAVAILABLE_SOURCE_FILE'))
    cal = aliases['CALIBRATED']
    unique = _csv(cal / '08_AGGREGATE/v3/UNIQUE_EVALUATION_RESULTS.csv')
    series = []
    for ix, row in unique.iterrows():
        member = f'supplemental/CALIBRATED/error_series/{row["run_id"]}.csv.gz'
        item = {k: row[k] for k in ('dataset_id', 'method_id', 'run_id', 'effective_configuration_id')}
        item.update(member=member, evaluator_version='v3', source_table_row=int(ix)+2,
                    **sources.series(row['error_series_source'], member), status='OK')
        series.append(item)
    _manifest(sources.target, 'supplemental/CALIBRATED/SERIES_MANIFEST.csv', series)
    _manifest(sources.target, 'supplemental/CALIBRATED/error_series/SERIES_MANIFEST.csv', series)
    for dataset in ('BY2', 'BY2H', 'BY2O'):
        source = _safe_file(cal / f'02_CALIBRATED_PROVIDERS/{dataset}/CALIBRATED_GNSS.gnss', clean)
        frame = pd.read_csv(source, sep=r'\s+', header=None, usecols=[0,13,14,17], dtype=str)
        frame.columns = ['time', 'yaw_deg', 'yaw_std_deg', 'valid']
        frame['source_row'] = range(1, len(frame)+1)
        member = f'supplemental/SEQUENCE_QUALITY/{dataset}.csv'
        dest = sources.target / member; dest.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(dest, index=False)
        sources.record(source, member, 'unchanged columns 0/13/14/17 from GNSS18; all rows', rows_full=len(frame))
    contract = yaml.safe_load((Path(code_root) / 'configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml').read_text())
    core = yaml.safe_load((Path(code_root) / 'configs/paper_rebuild/clean6/CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml').read_text())
    pin = core['sources']['case_registry']
    source = Path(pin['path'].replace('<CLEAN_ROOT>', str(clean)))
    if sha256_file(source) != pin['sha256']:
        raise ValueError('Core case registry pin changed')
    sources.copy(source, 'found/CANONICAL541_CASE_MANIFEST.csv')
    for name in ('OCCLUSION_WINDOW.json', 'EVENT_WINDOW_V2.json'):
        source = stages / 'CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE' / '01_SEQUENCE_CONTRACT' / name
        if source.is_file():
            sources.copy(source, 'supplemental/SEQUENCE_QUALITY/' + name)
        else:
            missing.append(dict(source='<CLEAN5_BY2O_ROOT>/01_SEQUENCE_CONTRACT/' + name, status='UNAVAILABLE_SOURCE_FILE'))
    horizontal = stages/'CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/13_HORIZONTAL_CROSS_LAYER_SYNTHESIS'
    for rel in ('00_METHOD_REGISTRY/FINAL_METHOD_REGISTRY_V2.csv',
                '06_CROSS_LAYER_COMPARABILITY/OUTPUT_AND_METRIC_COMPATIBILITY.csv',
                '02_RAW_DUAL_ANTENNA/RAW_PRIMARY_METHOD_C00_SUMMARY.csv',
                '02_RAW_DUAL_ANTENNA/RAW_AVAILABILITY_AND_STATE_SUMMARY.csv',
                '02_RAW_DUAL_ANTENNA/RAW_BASELINE_AND_HEADING_SUMMARY.csv',
                '02_RAW_DUAL_ANTENNA/RAW_RUNTIME_AND_FAILURE_SUMMARY.csv',
                '04_PROPRIOCEPTIVE_OBSERVABILITY/HARTLEY_OBSERVABILITY_SUMMARY.csv',
                '04_PROPRIOCEPTIVE_OBSERVABILITY/HARTLEY_GAUGE_EQUIVALENCE_SUMMARY.csv'):
        source = horizontal/rel
        sources.copy(source, 'supplemental/HORIZONTAL/' + source.name)
    source = horizontal.parent/'07_LSE01_HARTLEY_CONTACT_INEKF/10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_SINGULAR_VALUES_R1.csv'
    sources.copy(source, 'supplemental/HORIZONTAL/' + source.name)
    geometry_path = Path(code_root)/'configs/paper_rebuild/publication/PROTOCOL_V2_FIGURE_GEOMETRY.yaml'
    geometry = yaml.safe_load(geometry_path.read_text())
    physical_source = Path(geometry['source_alias'].replace('<CODE_ROOT>', str(code_root)))
    if sha256_file(physical_source) != geometry['source_sha256']:
        raise ValueError('Frozen physical geometry source changed')
    _json(sources.target / 'PLOT_GEOMETRY_CONTRACT.json', dict(evaluation=contract['evaluation'],
          source_contract_sha256=sha256_file(Path(code_root) / 'configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml'),
          physical_geometry=geometry, plotting_geometry_config_sha256=sha256_file(geometry_path)))
    _json(sources.target / 'SUPPLEMENT_UNAVAILABLE.json', missing)


def pack_combined(base_package, addendum_root, clean_root, code_root, output, *, package_dir=None):
    base_package, output = Path(base_package).resolve(), Path(output).absolute()
    if sha256_file(base_package) != BASE_PACKAGE_SHA256:
        raise ValueError('Base package differs from the frozen P-09c handoff identity')
    validate_archive(base_package)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    target = Path(package_dir).absolute() if package_dir else output.with_suffix('')
    if target.exists() or target.is_symlink() or target == output.parent:
        raise FileExistsError(target)
    target.mkdir(parents=True, exist_ok=False)
    base_identities = {}
    with zipfile.ZipFile(base_package) as base:
        for name in base.namelist():
            if name.endswith('/'):
                continue
            member = 'base_provenance/BASE_PACKAGE_MANIFEST.json' if name == 'PACKAGE_MANIFEST.json' else name
            dest = target / safe_member(member); dest.parent.mkdir(parents=True, exist_ok=True)
            with base.open(name) as src, dest.open('xb') as out:
                shutil.copyfileobj(src, out)
            base_identities[member] = sha256_file(dest)
    sources = Sources(target, clean_root)
    append_addendum(sources, Path(addendum_root).resolve())
    append_core_display(sources, Path(clean_root) / 'stages/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2')
    append_supplements(sources, code_root)
    _json(target / 'SUPPLEMENT_SOURCE_MANIFEST.json', sources.rows)
    _json(target / 'BASE_PACKAGE_IDENTITY.json', dict(sha256=sha256_file(base_package),
          size_bytes=base_package.stat().st_size, preserved_member_sha256=base_identities))
    for member, expected in base_identities.items():
        if sha256_file(target / member) != expected:
            raise ValueError('Core package member changed: ' + member)
    members = {p.relative_to(target).as_posix(): dict(sha256=sha256_file(p), size_bytes=p.stat().st_size)
               for p in sorted(target.rglob('*')) if p.is_file()}
    _json(target / 'PACKAGE_MANIFEST.json', dict(schema_version='canonical541_handoff_v3_with_addendum',
          members=members, core_and_addendum_tables_separate=True, raw_payload_included=False,
          data_mode='mixed_real_base_and_semisynthetic_controlled_degradation',
          synthetic_data_used=False, semisynthetic_data_used=True,
          metric_recomputation_performed=False))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for member in sorted(members):
            archive.write(target/member, member)
        archive.write(target/'PACKAGE_MANIFEST.json', 'PACKAGE_MANIFEST.json')
    result = validate_archive(output)
    result.update(archive=str(output), package_dir=str(target), addendum_identity_pass=True,
                  core_preserved_members=len(base_identities))
    _json(output.with_suffix('.validation.json'), result)
    return result
