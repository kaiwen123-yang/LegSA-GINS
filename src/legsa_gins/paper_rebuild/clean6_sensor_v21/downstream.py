"""P-13 downstream input variants, fixed noise grid and read-only diagnostics.

``build_jobs`` materializes yaw-std-only GNSS derivatives and returns 21 jobs;
it never calls a solver/evaluator. Existing variant IMU and RD are pinned, not
replaced by CAL. V-CHK and robustness functions consume completed new outputs.
"""
from __future__ import annotations

import copy
import filecmp
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import yaml
import numpy as np

from ..clean5_calibrated.robustness import compare_segments, comparison_csv_rows
from ..clean5_degradation.common import FLAGS, pinned, read_csv, resolve, write_json
from ..clean5_parity.runtime import bind_config
from ..clean5_parity_p05.runtime import grid_cells, patch_noise
from ..clean5_sequence.runtime_config import NATIVE_IDENTITY
from ..manifest import sha256_file

LADDER = ('V0', 'V1', 'V2', 'V2i', 'V2s', 'V2is')
METHODS = ('F03', 'A04')
PARITY_ROOT = '<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF'
VCHK_ROOT = '<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/09_YAW_CHANGE_CHECK'
VCHK_PINS = {
    'analysis.py': 'd2055b44e9b015456c18e336a42daaeec96ef53fb331a62234e50937066cd40d',
    'INPUT_CATALOG.json': 'f1d7b28bc35cac6549801aed6b3b1a6bdf67f51c6d3021a2d879a527f2a2a888',
    'INPUT_HASH_LEDGER.csv': 'e884da275bcecf3cb41c6e90fd05f421775d5de685cde982d331b9936d8d48a7',
    'ANALYSIS_DEFINITIONS.json': '5a635a33e3c91d69d3b4ce18c42825df510287820aeb79d5ab9fdc5a3fde33b6',
}


def correct_gnss_text(original):
    """Replace only token 15, preserving every other byte and validity flag."""
    lines = []
    widths = set()
    count = 0
    for line in original.splitlines(keepends=True):
        if not line.strip() or line.lstrip().startswith('#'):
            lines.append(line)
            continue
        tokens = list(re.finditer(r'\S+', line))
        if len(tokens) not in (15, 18):
            raise ValueError('Downstream GNSS requires exactly 15 or 18 fields')
        widths.add(len(tokens))
        if len(tokens) == 18 and any(m.group() not in ('0', '1') for m in tokens[15:]):
            raise ValueError('Explicit GNSS validity is not boolean')
        field = tokens[14]
        lines.append(line[:field.start()] + '2.933193' + line[field.end():])
        count += 1
    if len(widths) != 1 or not count:
        raise ValueError('Empty or mixed-width GNSS input')
    return ''.join(lines), {'row_count': count, 'columns': next(iter(widths)),
                            'changed_column_1based': 15, 'yaw_std_deg': 2.933193,
                            'all_other_bytes_equal': True, 'validity_unchanged': True}


def _contract(reg, name):
    return yaml.safe_load((reg.code_root / 'configs/paper_rebuild/clean5' / name).read_text())


def _checked(entry, reg, cache):
    path = resolve(entry['path'], reg)
    key = (str(path), entry['sha256'])
    if key not in cache:
        pinned(entry, reg)
        cache[key] = True
    return {**entry, 'path': str(path)}


def inspect_inputs(reg):
    """Read/hash the exact retained six-variant input chain; write nothing."""
    contract = _contract(reg, 'CLEAN5_PARITY_CONTRACT.yaml')
    grid = _contract(reg, 'CLEAN5_PARITY_P05_CONTRACT.yaml')
    p02_path = resolve(PARITY_ROOT + '/02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json', reg)
    p03_path = resolve(grid['p05']['provider_bundle']['path'], reg)
    if sha256_file(p02_path) != contract['p03']['reference_provider_bundle_sha256']:
        raise ValueError('Frozen P02 provider bundle changed')
    if sha256_file(p03_path) != grid['p05']['provider_bundle']['sha256']:
        raise ValueError('Frozen P03 provider bundle changed')
    p02, p03 = json.loads(p02_path.read_text()), json.loads(p03_path.read_text())
    variants = {}
    cache = {}
    for variant in LADDER:
        parent = p02 if variant in ('V0', 'V1', 'V2') else p03
        source_variant = 'V0-18' if variant == 'V0' else variant
        inputs = {key: _checked(entry, reg, cache)
                  for key, entry in parent['variants'][source_variant]['providers'].items()}
        variants[variant] = {'providers': inputs, 'raw_source_hashes': parent['raw_source_hashes'],
                             'source_variant': source_variant,
                             'source_bundle': str(p02_path if parent is p02 else p03_path)}
    configs = {}
    for method in METHODS:
        spec = contract['frozen_runtime']['original_configs'][method]
        configs[method] = _checked({'path': spec['runtime_config'],
                                    'sha256': spec['runtime_config_sha256']}, reg, cache)
    return {'status': 'PASS', 'variants': variants, 'configs': configs,
            'parity_contract': contract, 'grid_contract': grid,
            'verified_unique_input_count': len(cache), 'provider_generation_count': 0}


def _write_text_once(path, text):
    path = Path(path)
    if path.exists():
        if path.read_text() != text:
            raise ValueError('Existing downstream derivative differs: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as stream:
            stream.write(text)
    return {'path': str(path), 'sha256': sha256_file(path)}


def build_jobs(v21, v2, reg, bases, output, code_commit):
    """Return 12 BY2 ladder + 9 grid native jobs, preserving variant noise.

    Each entry contains ``source``, ``bundle``, ``original_text``, ``run_root``
    and ``run_kwargs`` for ``runtime.run_one``. Call with
    ``**job['run_kwargs']``; in particular, ``apply_calibration=False`` is
    required. The original ladder/grid deliberately retain their own vrw/abstd.
    """
    snapshot = inspect_inputs(reg)
    base = bases.get('bundles', bases)['BY2']
    output = Path(output)
    if reg.clean_root not in output.resolve().parents:
        raise ValueError('Downstream output must be below CLEAN_ROOT')
    if base['sensor_model_group_hash'] != v21['sensor_model_group_hash']:
        raise ValueError('Downstream SENSOR_MODEL_V21 lock differs')
    input_bundles = {}
    for variant, old in snapshot['variants'].items():
        providers = copy.deepcopy(old['providers'])
        text, gnss_audit = correct_gnss_text(Path(providers['gnsspath']['path']).read_text())
        providers['gnsspath'] = _write_text_once(output / '02_PROVIDERS' / variant / 'GNSS.gnss', text)
        for role in ('go2_attitude_prior_path', 'go2_horizontal_velocity_prior_path'):
            providers[role] = _checked(base['providers'][role], reg, {})
        if any(providers[key] != old['providers'][key] for key in ('imupath', 'raw_doppler_factor_path')):
            raise ValueError('Downstream variant IMU/RD changed')
        input_bundles[variant] = {**FLAGS, 'data_mode': 'real_by2_raw',
            'dataset_id': 'BY2', 'case_id': 'C00_clean_normal', 'variant_id': variant,
            'providers': providers, 'raw_source_hashes': old['raw_source_hashes'],
            'raw_input_hashes': old['raw_source_hashes'], 'code_commit': code_commit,
            'sensor_model_group_hash': v21['sensor_model_group_hash'],
            'input_variant_immutable': True, 'source_bundle': old['source_bundle'],
            'source_variant': old['source_variant'], 'gnss_audit': gnss_audit,
            'preserved_IMU_RD': {key: old['providers'][key]['sha256']
                                 for key in ('imupath', 'raw_doppler_factor_path')}}
    registry_rows = read_csv(pinned(v2['sources']['unique_run_registry'], reg))
    profiles = {row['method_id']: row for row in registry_rows
                if row['case_id'] == 'C00_clean_normal' and row['method_id'] in METHODS}
    if set(profiles) != set(METHODS):
        raise ValueError('Downstream source profile registry incomplete')
    sequence_spec = v2['sequences']['BY2']
    if sequence_spec['window_seconds'] != snapshot['parity_contract']['frozen_runtime']['window_seconds']:
        raise ValueError('Downstream BY2 frozen window differs')
    jobs = []
    cells = grid_cells(snapshot['grid_contract'])
    identities = [('LADDER', variant, method, None) for variant in LADDER for method in METHODS]
    identities += [('NOISE_GRID', 'V2is', 'A04', cell) for cell in cells]
    for family, variant, method, cell in identities:
        item = variant if cell is None else cell['cell_id']
        run_id = 'P13_' + family + '_' + item + '_' + method
        root = output / '03_RUNS' / run_id
        original = Path(snapshot['configs'][method]['path']).read_text()
        text, _ = bind_config(original, {**NATIVE_IDENTITY, 'run_id': run_id,
                                         'run_label': run_id, 'outputpath': str(root)})
        grid_audit = None
        if cell:
            text, grid_audit = patch_noise(text, cell['abstd_mGal'], cell['vrw_mps_sqrt_hour'])
        cfg = yaml.safe_load(text)
        source = {**profiles[method], 'run_id': run_id, 'case_id': cfg['case_id'],
                  'case_family': family, 'degradation_type_id': 'CLEAN',
                  'runtime_config_path': snapshot['configs'][method]['path'],
                  'runtime_config_file_hash': snapshot['configs'][method]['sha256']}
        jobs.append({'job_kind': 'native', 'diagnostic_family': family,
            'variant_id': item, 'input_variant': variant, 'source': source,
            'bundle': input_bundles[variant], 'original_text': text, 'run_root': str(root),
            'dataset': 'BY2', 'method_id': method, 'sequence_spec': sequence_spec,
            'run_kwargs': {'original_text': text, 'dataset': 'BY2',
                           'sequence_spec': sequence_spec, 'apply_calibration': False,
                           'sensor_corrections': True},
            'grid_cell': cell, 'grid_audit': grid_audit, 'code_commit': code_commit,
            'sensor_model_group_hash': v21['sensor_model_group_hash'],
            'frozen_window_seconds': sequence_spec['window_seconds'],
            'calibrated_vrw_abstd_substitution': False,
            'outcome_changed': False, 'new_outcome_created': False})
    if len(jobs) != 21 or len({job['source']['run_id'] for job in jobs}) != 21:
        raise ValueError('Downstream native job identity closure failed')
    notes = [
        {'id': 'P13-D01', 'resolution': 'V0 names the exact existing V0-18 provider; original fifteen tokens plus existing three validity fields are preserved except yaw_std.'},
        {'id': 'P13-D02', 'resolution': 'The old V0-18 byte gate cannot compare sensor-corrected outputs to pre-correction outputs. Native identity is covered by P13 binary bridge; variant input identity is checked here.'},
        {'id': 'P13-D03', 'resolution': 'The nine-grid N00 reference is new V2is A04 with the same sensor corrections, not the old uncorrected NAV/STD. All nine original grid cells remain reportable.'},
        {'id': 'P13-D04', 'resolution': 'Ladder and grid preserve original per-variant vrw/abstd and IMU. CAL noise is not imposed on these diagnostics.'},
    ]
    registry = {'status': 'READY_FOR_NATIVE', 'native_jobs': jobs,
                'native_count': 21, 'evaluator_terminal_slots': 42,
                'VCHK_A04': {'native_count': 0, 'sequences': ['BY2', 'BY2H', 'BY2O'],
                             'comparisons': ['V21_MINUS_FROZEN', 'V21_MINUS_CAL']},
                'robustness': {'native_count': 0, 'new_outcome_created': False},
                'notes': notes, 'code_commit': code_commit}
    ledger_path = output / 'DOWNSTREAM_JOB_REGISTRY.json'
    if not ledger_path.exists():
        write_json(ledger_path, registry)
    return jobs


def resolve_error_series(path, expected_uncompressed_sha256):
    """Accept lossless CSV.gz storage only after original payload hash equality."""
    path = Path(path)
    actual = path if path.is_file() else path.with_suffix(path.suffix + '.gz')
    if actual.is_symlink() or not actual.is_file():
        raise FileNotFoundError('Frozen error series unavailable: ' + str(path))
    if path.is_file():
        if sha256_file(path) != expected_uncompressed_sha256:
            raise ValueError('Frozen error-series file identity mismatch')
        return str(path)
    opener = gzip.open if actual.suffix == '.gz' else open
    digest = hashlib.sha256()
    with opener(actual, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected_uncompressed_sha256:
        raise ValueError('Lossless error-series content identity mismatch')
    return str(actual)


def grid_origin_gate(ladder_v2is_a04_root, grid_n00_root):
    """Original grid-origin tolerance against the new corrected V2is control."""
    checks = {}
    for name in ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt'):
        reference = Path(ladder_v2is_a04_root) / name
        actual = Path(grid_n00_root) / name
        if reference.is_symlink() or actual.is_symlink():
            raise ValueError('Symlink in downstream origin gate')
        same_bytes = filecmp.cmp(reference, actual, shallow=False)
        left, right = np.loadtxt(reference, ndmin=2), np.loadtxt(actual, ndmin=2)
        finite = bool(np.isfinite(left).all() and np.isfinite(right).all())
        same_shape = left.shape == right.shape
        delta = float(np.max(abs(left - right))) if same_shape and finite and left.size else None
        checks[name] = {'byte_identical': same_bytes, 'same_shape': same_shape,
                        'finite': finite, 'maximum_absolute_difference': delta,
                        'passed': delta is not None and delta <= 1e-9,
                        'reference_sha256': sha256_file(reference), 'actual_sha256': sha256_file(actual)}
    return {'status': 'PASS' if all(v['passed'] for v in checks.values()) else 'FAIL',
            'checks': checks, 'numeric_tolerance': 1e-9,
            'reference': 'P13_LADDER_V2is_A04', 'origin': 'P13_NOISE_GRID_N00_A04',
            'pre_correction_output_used': False}


def _vchk_sources(reg):
    root = resolve(VCHK_ROOT, reg)
    for name, digest in VCHK_PINS.items():
        pinned({'path': str(root / name), 'sha256': digest}, reg)
    spec = importlib.util.spec_from_file_location('p13_frozen_vchk_math', root / 'analysis.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    catalog = json.loads((root / 'INPUT_CATALOG.json').read_text())
    ledger = {str(resolve(row['path'], reg)): row['sha256']
              for row in read_csv(root / 'INPUT_HASH_LEDGER.csv')}
    return module, catalog, ledger


def vchk_a04(reg, new_entries):
    """Rerun only A04 V1/V2/V3 statistics from sealed v2.1 error/NAV traces.

    ``new_entries`` maps each dataset to an explicit catalog entry with
    error_series, manifest, gnss_update_trace and optional column/time offsets.
    Historical FROZEN/CAL inputs retain their source hashes and definitions.
    """
    math, catalog, ledger = _vchk_sources(reg)
    if set(new_entries) != set(catalog['windows']):
        raise ValueError('VCHK requires exactly all three sequence entries')
    result = {'status': 'COMPLETED', 'classification': 'P13_A04_DIAGNOSTIC_ONLY',
              'V1': [], 'V2': [], 'V3': [], 'tables': {'10s': [], '1s': [], 'first30': []},
              'outcome_changed': False, 'new_outcome_created': False,
              'solver_count': 0, 'evaluator_count': 0, 'provider_generation_count': 0,
              'reference_trace_open_count': 0, 'source_analysis_sha256': VCHK_PINS['analysis.py']}
    for dataset, window in catalog['windows'].items():
        new = {**new_entries[dataset], 'sequence': dataset, 'method': 'A04', 'chain': 'V21'}
        new_counts = math.counts(new, catalog['counter_fields'])
        diagnostics = math.read_csv(catalog['diagnostics'][dataset])
        for old_chain in ('FROZEN', 'CAL'):
            old = copy.deepcopy(next(row for row in catalog['runs']
                if (row['sequence'], row['method'], row['chain']) == (dataset, 'A04', old_chain)))
            original_path = old['error_series']
            old['error_series'] = resolve_error_series(original_path, ledger[original_path])
            for key in ('manifest', 'gnss_update_trace'):
                pinned({'path': old[key], 'sha256': ledger[old[key]]}, reg)
            old_counts = math.counts(old, catalog['counter_fields'])
            result['V1'].append({'sequence': dataset, 'method': 'A04',
                'comparison': 'V21_MINUS_' + old_chain, 'old': old_counts, 'new': new_counts,
                'relative_reject_plus_downweight_count_change': math.relative_count_change(
                    old_counts['yaw_reject_plus_downweight'], new_counts['yaw_reject_plus_downweight'])})
            table, summary, _, _ = math.pair_entries(old, new, window, 10, diagnostics)
            result['V2'].append(summary)
            result['tables']['10s'].extend(table)
            table, summary, old_errors, new_errors = math.pair_entries(old, new, window, 1)
            early = [row for row in table if row['bin_start_s'] < window[0] + 30]
            early_mass = sum(row['signed_delta_sample_mass_deg'] for row in early)
            summary.update(first30_signed_mass_deg=early_mass,
                first30_signed_fraction=math.ratio(early_mass, summary['signed_delta_sample_mass_deg']),
                first30_absolute_fraction=math.ratio(sum(abs(row['signed_delta_sample_mass_deg'])
                    for row in early), summary['absolute_bin_delta_sample_mass_deg']),
                first30_contribution_to_total_mae_delta_deg=early_mass / summary['matched_finite_count'],
                old_first_entry=math.first_entry(old_errors, window, table, 'old'),
                new_first_entry=math.first_entry(new_errors, window, table, 'new'))
            result['V3'].append(summary)
            result['tables']['1s'].extend(table)
            result['tables']['first30'].extend(early)
    return result


def robustness(rows_by_version, *, rule, old):
    """Apply the unchanged eight Decimal formula checks, never choose a method."""
    if set(rows_by_version) != {'v2', 'v3'}:
        raise ValueError('Robustness requires both frozen evaluator versions')
    result = {'classification': 'NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL',
              'protocol_id': 'SENSOR_MODEL_V2_1', 'outcome_changed': False,
              'new_outcome_created': False, 'rule_source': rule,
              'versions': {version: compare_segments(rows, rule=rule, old=old)
                           for version, rows in rows_by_version.items()}}
    result['rows'] = comparison_csv_rows(result)
    return result
