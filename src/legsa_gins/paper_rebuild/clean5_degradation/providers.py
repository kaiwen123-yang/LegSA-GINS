"""Apply the frozen Canonical laws to pinned CLEAN5 GNSS18 observations.

This adapter never builds observations from raw logs and never invokes a solver
or evaluator.  A1 has its own sparse effective table; missing observations use
validity flags.  D57 intentionally creates the union of independently shifted
source epochs.  The five C00 solver inputs remain byte-identical pointers.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..canonical541 import provider_generator as canonical
from ..canonical541.matrix_spec import CLEAN_CASE_ID, load_type_registry
from ..canonical541.seed_anchor import stable_component_rngs


INPUT_ROLES = (
    'imupath', 'gnsspath', 'raw_doppler_factor_path',
    'go2_attitude_prior_path', 'go2_horizontal_velocity_prior_path',
)
AUXILIARY_ROLES = ('dual_yaw_audit', 'source_quality_metadata')
SOURCE_TO_ROLE = {
    'raw_doppler': 'raw_doppler_factor_path',
    'go2_rp': 'go2_attitude_prior_path',
    'go2_hv': 'go2_horizontal_velocity_prior_path',
}
FILENAMES = {
    'gnsspath': 'GNSS18.gnss',
    'raw_doppler_factor_path': 'RAW_DOPPLER.csv',
    'go2_attitude_prior_path': 'GO2_ATTITUDE_PRIOR.csv',
    'go2_horizontal_velocity_prior_path': 'GO2_HORIZONTAL_VELOCITY_PRIOR.csv',
}
GNSS_SOURCES = ('gnss_position', 'receiver_velocity', 'dual_yaw')


class DegradationProviderError(ValueError):
    pass


def _hash(path: Path) -> str:
    return canonical.sha256_file(path)


def _checked_pin(pin: Mapping[str, Any]) -> Path:
    path = Path(pin['path']).expanduser()
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise DegradationProviderError('Pinned input must be absolute and contain no symlink')
    name = path.name.lower()
    if any(s.lower() in {'.bag', '.fpl', '.trace'} for s in path.suffixes) or name.startswith(('trace_', 'trace.')):
        raise DegradationProviderError('Forbidden provider input path')
    if not path.is_file() or _hash(path) != pin['sha256']:
        raise DegradationProviderError('Pinned provider hash mismatch: ' + path.name)
    return path


def _csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        rows = list(reader)
    if not fields:
        raise DegradationProviderError('Missing provider CSV header: ' + path.name)
    return fields, rows


def _finite(value: Any) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise DegradationProviderError('Nonfinite provider value')
    return out


def _valid(row: Mapping[str, Any]) -> bool:
    value = str(row.get('valid', row.get('update_flag', '1'))).lower()
    if value not in {'1', 'true', 'yes', '0', 'false', 'no'}:
        raise DegradationProviderError('Unknown validity token: ' + value)
    return value in {'1', 'true', 'yes'}


def _wrap(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _strict_times(rows: list[dict[str, Any]], label: str) -> None:
    times = [_finite(row['time']) for row in rows]
    if not times or any(a >= b for a, b in zip(times, times[1:])):
        raise DegradationProviderError('Empty or non-increasing provider times: ' + label)


@dataclass
class BaseInputs:
    bundle: canonical.ProviderBundle
    providers: dict[str, dict[str, Any]]
    auxiliary_roles: dict[str, dict[str, Any]]
    gnss_tokens: list[list[str]]
    gnss_lines: list[str]
    gnss_data_line_indices: list[int]
    data_mode: str
    synthetic_data_used: bool
    semisynthetic_data_used: bool
    a1_audit: dict[str, Any]


def build_base(
    provider_roles: Mapping[str, Mapping[str, Any]], *,
    auxiliary_roles: Mapping[str, Mapping[str, Any]], base_time_s: float,
    raw_input_hashes: Mapping[str, str] | None = None,
    data_mode: str = 'real_clean', synthetic_data_used: bool = False,
    semisynthetic_data_used: bool = False,
) -> BaseInputs:
    """Read exact pinned inputs, including real baseline and quality audit rows.

    A1 association is unique millisecond identity after subtracting base_time_s.
    The original A1 yaw must agree with the GNSS18 token within 1e-6 degree.
    Synthetic fixtures must explicitly select data_mode='synthetic_test'.
    """
    if set(provider_roles) != set(INPUT_ROLES) or set(auxiliary_roles) != set(AUXILIARY_ROLES):
        raise DegradationProviderError('Exact five solver and two auxiliary roles required')
    if (synthetic_data_used or semisynthetic_data_used) and data_mode != 'synthetic_test':
        raise DegradationProviderError('Synthetic inputs cannot receive a real-data mode')
    if data_mode not in {'real_clean', 'synthetic_test'}:
        raise DegradationProviderError('Unsupported base data mode')
    if data_mode == 'synthetic_test' and not synthetic_data_used:
        raise DegradationProviderError('Synthetic test mode requires synthetic_data_used=true')
    paths = {role: _checked_pin(pin) for role, pin in provider_roles.items()}
    aux_paths = {role: _checked_pin(pin) for role, pin in auxiliary_roles.items()}
    text = paths['gnsspath'].read_bytes().decode('utf-8-sig')
    lines = text.splitlines(keepends=True)
    tokens, line_indices = [], []
    for index, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        row = line.split()
        if len(row) != 18:
            raise DegradationProviderError('CLEAN5 GNSS input must have exactly 18 columns')
        values = [_finite(value) for value in row]
        if any(value not in (0, 1) for value in values[15:]):
            raise DegradationProviderError('GNSS18 validity flags must be 0 or 1')
        tokens.append(row)
        line_indices.append(index)
    if not tokens:
        raise DegradationProviderError('Empty GNSS18 input')
    position, velocity = [], []
    for row in tokens:
        position.append(dict(zip(
            ('time', 'lat_deg', 'lon_deg', 'height_m', 'std_n_m', 'std_e_m', 'std_d_m', 'valid'),
            row[:7] + [row[15]],
        ), status='clean_active'))
        velocity.append(dict(zip(
            ('time', 'vn', 've', 'vd', 'std_vn', 'std_ve', 'std_vd', 'valid'),
            [row[0]] + row[7:13] + [row[16]],
        ), status='clean_active'))
    _, a1_rows = _csv(aux_paths['dual_yaw_audit'])
    a1_by_ms = {}
    for row in a1_rows:
        key = int(round((_finite(row['source_timestamp']) - base_time_s) * 1000))
        if key in a1_by_ms:
            raise DegradationProviderError('Duplicate A1 millisecond identity')
        a1_by_ms[key] = row
    yaw, used_a1 = [], set()
    for row in tokens:
        if int(row[17]) != 1:
            continue
        key = int(round(_finite(row[0]) * 1000))
        if key not in a1_by_ms or key in used_a1:
            raise DegradationProviderError('Effective A1 row has missing or repeated physical identity')
        audit = a1_by_ms[key]
        if abs(_wrap(_finite(row[13]) - _finite(audit['body_yaw_ned_deg']))) > 1e-6:
            raise DegradationProviderError('A1 original yaw mismatch')
        for field in ('baseline_n_m', 'baseline_e_m', 'baseline_d_m', 'baseline_length_m'):
            _finite(audit[field])
        if audit.get('gnss_order') != 'GNSS2-GNSS1':
            raise DegradationProviderError('A1 physical antenna order mismatch')
        if str(audit.get('trace_sign_or_offset_selection', '')).lower() != 'false':
            raise DegradationProviderError('A1 trace-selection flag must be false')
        yaw.append({
            'time': row[0], 'yaw_deg': row[13], 'yaw_std_deg': row[14], 'valid': row[17],
            **{field: audit[field] for field in (
                'baseline_n_m', 'baseline_e_m', 'baseline_d_m', 'baseline_length_m',
                'physical_in_band', 'source_status', 'gnss_order',
                'lateral_to_body_offset_deg', 'wrap_safe_residual', 'trace_sign_or_offset_selection')},
        })
        used_a1.add(key)
    if not yaw:
        raise DegradationProviderError('No effective A1 epochs')
    tables = {name: canonical.ProviderTable(tuple(rows[0]), rows) for name, rows in (
        ('gnss_position', position), ('receiver_velocity', velocity), ('dual_yaw', yaw))}
    for source, role in SOURCE_TO_ROLE.items():
        fields, rows = _csv(paths[role])
        if not rows:
            raise DegradationProviderError('Empty auxiliary observation provider: ' + source)
        tables[source] = canonical.ProviderTable(fields, rows)
    fields, rows = _csv(aux_paths['source_quality_metadata'])
    if not rows:
        raise DegradationProviderError('Empty source-quality metadata')
    tables['source_quality_metadata'] = canonical.ProviderTable(fields, rows)
    for source, table in tables.items():
        if source != 'source_quality_metadata':
            _strict_times(table.rows, source)
        else:
            # Audit rows can describe multiple sources at a common epoch.
            for row in table.rows:
                _finite(row['time'])
    hashes = {role: pin['sha256'] for role, pin in provider_roles.items()}
    bundle = canonical.ProviderBundle(
        imu_path=paths['imupath'], tables=tables,
        raw_input_hashes=dict(raw_input_hashes or {}), base_provider_hashes=hashes,
        dual_yaw_audit_rows=a1_rows,
        original_provider_paths={'combined_gnss': paths['gnsspath'],
                                 **{source: paths[role] for source, role in SOURCE_TO_ROLE.items()}},
    )
    return BaseInputs(
        bundle, {r: dict(pin) for r, pin in provider_roles.items()},
        {r: dict(pin) for r, pin in auxiliary_roles.items()}, tokens, lines, line_indices,
        data_mode, synthetic_data_used, semisynthetic_data_used,
        {'physical_a1_row_count': len(a1_rows), 'effective_a1_row_count': len(yaw),
         'unmapped_physical_a1_count': len(a1_rows)-len(used_a1),
         'association': 'unique rounded millisecond source_timestamp-minus-base_time identity',
         'original_yaw_tolerance_deg': 1e-6, 'base_time_s': base_time_s},
    )


def _apply_count_intervals(base: canonical.ProviderBundle, case: Mapping[str, Any], mapping: Mapping[str, Any]):
    type_id = str(case['degradation_type_id'])
    bundle = base.clone()
    source = 'gnss_position' if type_id == 'D22' else 'dual_yaw'
    intervals = mapping.get('intervals', [])
    if len(intervals) != (1 if type_id == 'D22' else 3):
        raise DegradationProviderError('Frozen count-to-duration intervals are missing')
    selected, seen = [], set()
    table = bundle.tables[source]
    for interval in intervals:
        if list(interval['source_ids']) != [source]:
            raise DegradationProviderError('Count interval source mismatch')
        start, end = _finite(interval['start_s']), _finite(interval['end_s'])
        if end <= start:
            raise DegradationProviderError('Invalid count-to-duration interval')
        ids = [i for i, row in enumerate(table.rows) if _valid(row) and start <= _finite(row['time']) < end]
        if seen.intersection(ids):
            raise DegradationProviderError('Count-to-duration intervals overlap')
        selected.extend(ids)
        seen.update(ids)
    rngs = stable_component_rngs(int(case['seed_value']), canonical.COMPONENT_RNG_NAMES)
    if type_id == 'D22':
        theta = float(rngs['direction'].uniform(0, 2*math.pi))
        sign = float(rngs['direction'].choice((-1, 1)))
        for index in selected:
            canonical._add_position(table.rows[index], 8*math.cos(theta), 8*math.sin(theta), sign*4)
        details = {'horizontal_m': 8.0, 'vertical_m': 4.0, 'direction_rad': theta, 'vertical_sign': sign}
        name = 'position_burst_spike'
    else:
        for index in selected:
            table.rows[index]['valid'] = '0'
            table.rows[index]['source_status'] = 'quality_unavailable'
        details = {'burst_count': 3}
        name = 'baseline_quality_dropout'
    component_source = source if type_id == 'D22' else 'dual_yaw_quality'
    components = [{'component': name, 'affected_source': component_source, 'affected_epoch_count': len(selected),
                   'details': {**details, 'intervals': list(intervals), 'count_to_duration_seconds': True},
                   'status': 'PASS'}]
    return bundle, components, {'no_active_path': False, 'degradation_type_id': type_id,
                                'seed_replay': int(case['seed_value']), 'trace_read_count': 0,
                                'count_interval_override': True}


def _pairs(before: canonical.ProviderTable, after: canonical.ProviderTable, type_id: str):
    if len(before.rows) != len(after.rows):
        raise DegradationProviderError('Deletion is forbidden in the formal validity-bit implementation')
    if type_id == 'D57' and after.rows and canonical.D57_ORIGINAL_ROW_ID in after.rows[0]:
        identities = {int(row[canonical.D57_ORIGINAL_ROW_ID]): row for row in after.rows}
        if set(identities) != set(range(len(before.rows))):
            raise DegradationProviderError('D57 original-row identity mismatch')
        return [(left, identities[i]) for i, left in enumerate(before.rows)]
    return list(zip(before.rows, after.rows))


def _diff_source(before: canonical.ProviderTable, after: canonical.ProviderTable, type_id: str) -> dict[str, Any]:
    changed, times, generated_times, numeric, fields = [], [], [], {}, Counter()
    for index, (left, right) in enumerate(_pairs(before, after, type_id)):
        names = sorted(field for field in set(before.fields) | set(after.fields)
                       if field != canonical.D57_ORIGINAL_ROW_ID and str(left.get(field, '')) != str(right.get(field, '')))
        if not names:
            continue
        changed.append(index)
        times.append(_finite(left['time']))
        generated_times.append(_finite(right['time']))
        fields.update(names)
        for field in names:
            try:
                old, new = _finite(left[field]), _finite(right[field])
            except (ValueError, TypeError, KeyError):
                continue
            delta = _wrap(new-old) if field == 'yaw_deg' else new-old
            numeric.setdefault(field, []).append(delta)
        if {'lat_deg', 'lon_deg', 'height_m'}.issubset(before.fields):
            old_ecef = np.asarray(canonical._ecef(*(_finite(left[k]) for k in ('lat_deg', 'lon_deg', 'height_m'))))
            new_ecef = np.asarray(canonical._ecef(*(_finite(right[k]) for k in ('lat_deg', 'lon_deg', 'height_m'))))
            dx, dy, dz = new_ecef-old_ecef
            phi, lam = math.radians(_finite(left['lat_deg'])), math.radians(_finite(left['lon_deg']))
            north = -math.sin(phi)*math.cos(lam)*dx-math.sin(phi)*math.sin(lam)*dy+math.cos(phi)*dz
            east = -math.sin(lam)*dx+math.cos(lam)*dy
            up = math.cos(phi)*math.cos(lam)*dx+math.cos(phi)*math.sin(lam)*dy+math.sin(phi)*dz
            for field, value in (('position_delta_n_m', north), ('position_delta_e_m', east),
                                 ('position_delta_u_m', up), ('position_delta_h_m', math.hypot(north, east)),
                                 ('position_delta_3d_m', math.sqrt(north*north+east*east+up*up))):
                numeric.setdefault(field, []).append(float(value))
        if {'vn', 've', 'vd'}.issubset(before.fields):
            norm = math.sqrt(sum((_finite(right[field])-_finite(left[field]))**2 for field in ('vn', 've', 'vd')))
            numeric.setdefault('velocity_delta_norm_mps', []).append(norm)
    pairs = _pairs(before, after, type_id)
    return {
        'row_count_before': len(before.rows), 'row_count_after': len(after.rows),
        'affected_row_count': len(changed),
        'affected_previously_valid_count': sum(_valid(pairs[i][0]) for i in changed),
        'valid_count_before': sum(_valid(r) for r in before.rows),
        'valid_count_after': sum(_valid(r) for r in after.rows),
        'affected_base_time_min_s': min(times) if times else None,
        'affected_base_time_max_s': max(times) if times else None,
        'affected_generated_time_min_s': min(generated_times) if generated_times else None,
        'affected_generated_time_max_s': max(generated_times) if generated_times else None,
        'actual_time_start_s': min(generated_times) if generated_times else None,
        'actual_time_end_s': max(generated_times) if generated_times else None,
        'actual_time_endpoint_policy': 'minimum and maximum affected measurement times; registered half-open intervals reported separately',
        'changed_field_counts': dict(fields),
        'numeric_field_delta': {field: {'min': min(values), 'max': max(values),
                                      'min_abs': min(abs(v) for v in values), 'max_abs': max(abs(v) for v in values),
                                      'mean': float(np.mean(values)),
                                      'population_std': float(np.std(values)),
                                      'count': len(values)} for field, values in numeric.items()},
        'time_and_row_identity_preserved': all(left['time'] == right['time'] for left, right in pairs),
    }


def _frozen_source_tables(mapping: Mapping[str, Any], case_id: str):
    base_path = _checked_pin(mapping['frozen_base_provider_index'])
    case_path = _checked_pin(mapping['frozen_case_provider_index'])
    base_index, case_index = json.loads(base_path.read_text()), json.loads(case_path.read_text())
    if base_index.get('case_id') != CLEAN_CASE_ID or case_index.get('case_id') != case_id:
        raise DegradationProviderError('Frozen provider index case identity mismatch')
    if 'frozen_clean_root' in mapping:
        clean_root = Path(mapping['frozen_clean_root'])
    else:
        stages = next((parent for parent in base_path.parents if parent.name == 'stages'), None)
        if stages is None:
            raise DegradationProviderError('Frozen input root is required for pointer confinement')
        clean_root = stages.parent
    if not clean_root.is_absolute() or '..' in clean_root.parts or any(p.is_symlink() for p in (clean_root, *clean_root.parents)):
        raise DegradationProviderError('Invalid frozen clean input root')
    if not base_path.is_relative_to(clean_root) or not case_path.is_relative_to(clean_root):
        raise DegradationProviderError('Frozen provider index outside clean input root')
    base_entries = {entry['source']: entry for entry in base_index['provider_files']}
    case_entries = {entry['source']: entry for entry in case_index['provider_files']}
    sources = (*canonical.SOLVER_SOURCE_IDS, 'source_quality_metadata')
    member_evidence = {}

    def load(source, entry, index_path, *, allow_base_pointer):
        storage = entry['storage_mode']
        if storage == 'manifest_pointer':
            if (not allow_base_pointer or entry.get('pointer_case_id') != CLEAN_CASE_ID
                    or entry.get('pointer_source') != source):
                raise DegradationProviderError('Unapproved frozen provider pointer')
            table, evidence = load(source, base_entries[source], base_path, allow_base_pointer=False)
            if entry.get('semantic_sha256') and table.sha256() != entry['semantic_sha256']:
                raise DegradationProviderError('Frozen pointer semantic hash mismatch')
            return table, evidence
        if storage == 'materialized':
            relative = Path(entry['relative_path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise DegradationProviderError('Frozen provider relative path escapes its index')
            path = index_path.parent/relative
        elif storage == 'base_provider_pointer':
            path = Path(entry['pointer_target'])
        else:
            raise DegradationProviderError('Unsupported frozen provider storage mode')
        if not path.is_relative_to(clean_root):
            raise DegradationProviderError('Frozen provider pointer outside clean root')
        path = _checked_pin({'path': str(path), 'sha256': entry['sha256']})
        fields, rows = _csv(path)
        table = canonical.ProviderTable(fields, rows)
        if entry.get('semantic_sha256') and table.sha256() != entry['semantic_sha256']:
            raise DegradationProviderError('Frozen source table semantic hash mismatch')
        return table, {'path': str(path), 'sha256': entry['sha256'], 'semantic_sha256': table.sha256()}

    before, after = {}, {}
    for source in sources:
        if source not in base_entries or source not in case_entries:
            raise DegradationProviderError('Frozen index lacks required source: '+source)
        before[source], left = load(source, base_entries[source], base_path, allow_base_pointer=False)
        after[source], right = load(source, case_entries[source], case_path, allow_base_pointer=True)
        member_evidence[source] = {'before': left, 'after': right}
    return before, after, member_evidence


def _frozen_summary(mapping: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    """Read pinned frozen descriptions, ledgers and before/after provider tables."""
    pins = ('frozen_case_manifest', 'frozen_perturbation_ledger',
            'frozen_base_provider_index', 'frozen_case_provider_index')
    if not all(key in mapping for key in pins):
        raise DegradationProviderError('Frozen same-case manifest and perturbation ledger required')
    manifest_path = _checked_pin(mapping['frozen_case_manifest'])
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('case_id', case_id) != case_id:
        raise DegradationProviderError('Frozen case identity mismatch')
    generation = manifest
    if 'frozen_provider_generation_log' in mapping:
        generation = json.loads(_checked_pin(mapping['frozen_provider_generation_log']).read_text())
    _, ledger = _csv(_checked_pin(mapping['frozen_perturbation_ledger']))
    by_source = {}
    for row in ledger:
        by_source.setdefault(row['source'], []).append(row)
    ledger_summary = {}
    for source, rows in by_source.items():
        base_times = [_finite(row['base_time']) for row in rows]
        generated_times = [_finite(row['generated_time']) for row in rows]
        fields = Counter(field for row in rows for field in row['changed_fields'].split(';') if field)
        ledger_summary[source] = {'affected_row_count': len(rows),
                          'affected_base_time_min_s': min(base_times), 'affected_base_time_max_s': max(base_times),
                          'affected_generated_time_min_s': min(generated_times), 'affected_generated_time_max_s': max(generated_times),
                          'changed_field_counts': dict(fields)}
    before, after, members = _frozen_source_tables(mapping, case_id)
    type_id = mapping['degradation_type_id']
    if type_id == 'D57':
        for source in canonical.D57_TIMING_SOURCE_IDS:
            by_time = {_finite(row['time']): row for row in after[source].rows}
            if len(by_time) != len(after[source].rows):
                raise DegradationProviderError('D57 frozen generated timestamps are duplicated')
            for row in by_source.get(source, []):
                stamp = _finite(row['generated_time'])
                if stamp not in by_time:
                    raise DegradationProviderError('D57 frozen ledger timestamp not present in source table')
                by_time[stamp][canonical.D57_ORIGINAL_ROW_ID] = row['row_index']
            if any(canonical.D57_ORIGINAL_ROW_ID not in row for row in after[source].rows):
                raise DegradationProviderError('D57 frozen ledger does not close all source identities')
    result = {source: _diff_source(before[source], after[source], type_id) for source in before}
    return {'case_id': case_id, 'source_diff': result, 'ledger_summary': ledger_summary,
            'source_member_pins': members, 'empirical_amplitude_status': 'AVAILABLE_FROM_PINNED_SOURCE_TABLES',
            'components': generation.get('components', []),
            'parameter_law': manifest.get('degradation_parameters_json'),
            'input_pins': {key: dict(value) if isinstance(value, Mapping) else value
                           for key, value in mapping.items() if key.startswith('frozen_')},
            'metrics_opened': False}


def _gnss_rows(base: BaseInputs, generated: canonical.ProviderBundle, type_id: str) -> list[list[str]]:
    if type_id == 'D57':
        rows = canonical.compose_solver_gnss18(generated)
        # Every valid independent source event must survive the union composition.
        for column, source in ((15, 'gnss_position'), (16, 'receiver_velocity'), (17, 'dual_yaw')):
            if sum(int(row[column]) for row in rows) != sum(_valid(r) for r in generated.tables[source].rows):
                raise DegradationProviderError('D57 union lost or duplicated a valid source event')
        return rows
    rows = [list(row) for row in base.gnss_tokens]
    by_time = {float(row[0]): i for i, row in enumerate(rows)}
    for source, field_columns in (
        ('gnss_position', [('lat_deg', 1), ('lon_deg', 2), ('height_m', 3), ('std_n_m', 4), ('std_e_m', 5), ('std_d_m', 6), ('valid', 15)]),
        ('receiver_velocity', [('vn', 7), ('ve', 8), ('vd', 9), ('std_vn', 10), ('std_ve', 11), ('std_vd', 12), ('valid', 16)]),
        ('dual_yaw', [('yaw_deg', 13), ('yaw_std_deg', 14), ('valid', 17)]),
    ):
        for row in generated.tables[source].rows:
            time = float(row['time'])
            if time not in by_time:
                raise DegradationProviderError('Non-timing handler changed a provider timestamp')
            for field, col in field_columns:
                rows[by_time[time]][col] = str(row[field])
    return rows


def _write_json(path: Path, payload: Any) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def _semantic_equivalence(base: BaseInputs, generated: canonical.ProviderBundle,
                          case: Mapping[str, Any], mapping: Mapping[str, Any],
                          components: list[dict[str, Any]], semantics: Mapping[str, Any],
                          source_diff: Mapping[str, Any], frozen: Mapping[str, Any],
                          gnss_rows: list[list[str]]) -> dict[str, Any]:
    """Fail closed on laws, scope and deterministic amplitudes, not noise draws."""
    checks = []

    def check(name, passed, detail):
        row = {'check': name, 'passed': bool(passed), 'detail': detail}
        checks.append(row)
        if not passed:
            raise DegradationProviderError('Semantic equivalence failed: '+name+'; '+str(detail))

    def normalized(value):
        return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))

    type_id = case['degradation_type_id']
    specs = {spec.type_id: spec for spec in load_type_registry()}
    check('registered_equivalence_rule', bool(mapping.get('equivalence_rule')),
          mapping.get('equivalence_rule'))
    check('frozen_component_registration', 'frozen_components' in mapping and
          normalized(mapping['frozen_components']) == normalized(frozen['components']),
          'preregistered components must equal pinned frozen generation log')
    expected = frozen['components']
    check('component_identity', [(r['component'], r['affected_source']) for r in components] ==
          [(r['component'], r['affected_source']) for r in expected],
          'component names, sources and order preserved')
    if type_id != 'CLEAN':
        check('seed_replay', semantics.get('seed_replay') == int(case['seed_value']),
              'same case seed; unchanged components use original named substreams')
        if case.get('degradation_parameters_json'):
            registered = json.loads(case['degradation_parameters_json']) if isinstance(case['degradation_parameters_json'], str) else case['degradation_parameters_json']
            check('case_parameter_law', normalized(registered) == normalized(specs[type_id].parameters),
                  'exact sixty-type registry parameters; no fitted amplitude')
    varying = {'D08': {'idempotent'}, 'D09': {'idempotent'}, 'D10': {'idempotent'},
               'D22': {'burst_length'}, 'D39': {'burst_lengths'}, 'D54': {'dropout_count'}}
    for i, (new, old) in enumerate(zip(components, expected)):
        skipped = varying.get(type_id, set())
        for key, value in old.get('details', {}).items():
            if key in skipped:
                continue
            check(f'component_{i}_law_{key}', key in new.get('details', {}) and
                  normalized(new['details'][key]) == normalized(value),
                  'frozen law, physical time/recovery interval or named-substream parameter')
    if type_id in {'D22', 'D39'}:
        intervals = mapping['intervals']
        check('registered_seconds', normalized(components[0]['details']['intervals']) == normalized(intervals),
              'exact registered count-to-duration seconds, no relocation')
        for i, interval in enumerate(intervals):
            duration = float(interval['end_s'])-float(interval['start_s'])
            check(f'count_duration_{i}', math.isclose(duration, float(interval['frozen_affected_count']), abs_tol=1e-8),
                  'frozen one-Hz valid epochs converted to equal seconds')
        check('frozen_count_interval_coverage', sum(int(r['frozen_affected_count']) for r in intervals) ==
              int(expected[0]['affected_epoch_count']), 'all frozen burst epochs represented once')
        source = 'gnss_position' if type_id == 'D22' else 'dual_yaw'
        affected = [left for left, right in _pairs(base.bundle.tables[source], generated.tables[source], type_id)
                    if any(str(left.get(k, '')) != str(right.get(k, '')) for k in left)]
        check('count_interval_affected_scope', all(any(float(v['start_s']) <= float(row['time']) < float(v['end_s'])
                                                      for v in intervals) for row in affected),
              'all affected measurements stay inside registered intervals')
    aliases = {'gnss_position_std': 'gnss_position', 'gnss_status_quality_flags': 'source_quality_metadata',
               'receiver_velocity_std': 'receiver_velocity', 'dual_yaw_std': 'dual_yaw',
               'dual_yaw_quality': 'dual_yaw', 'raw_doppler_velocity': 'raw_doppler',
               'raw_doppler_std': 'raw_doppler', 'go2_roll_pitch_weak_prior': 'go2_rp',
               'go2_horizontal_velocity_weak_prior': 'go2_hv', 'go2_source_metadata': 'source_quality_metadata'}
    allowed = {aliases.get(source, source) for source in specs[type_id].affected_sources} if type_id != 'CLEAN' else set()
    changed = {source for source, diff in source_diff.items() if diff['affected_row_count']}
    check('changed_source_scope', changed <= allowed, {'changed': sorted(changed), 'allowed': sorted(allowed)})
    validity = {'valid', 'status', 'source_status', 'provider_status', 'update_flag'}
    position_fields = {'lat_deg', 'lon_deg', 'height_m'}
    position_std = {'std_n_m', 'std_e_m', 'std_d_m'}
    velocity_fields = {'vn', 've', 'vd'}
    velocity_std = {'std_vn', 'std_ve', 'std_vd'}
    field_scope = {f'D{i:02d}': validity for i in range(1, 13)}
    field_scope.update({f'D{i:02d}': position_fields for i in range(13, 23)})
    field_scope.update({f'D{i:02d}': position_std for i in [23, 24, 25, 26, 28]})
    field_scope.update({
        'D27': position_fields | position_std, 'D29': {'audit_gnss_quality'},
        'D30': validity, 'D31': validity, 'D32': {'yaw_deg'}, 'D33': {'yaw_deg'},
        'D34': {'yaw_deg'}, 'D35': {'yaw_deg'}, 'D36': {'yaw_std_deg'}, 'D37': {'yaw_std_deg'},
        'D38': {'yaw_deg', 'yaw_std_deg'}, 'D39': validity, 'D40': {'baseline_length_m'},
        'D41': {'baseline_n_m', 'baseline_e_m', 'baseline_d_m', 'baseline_length_m', 'yaw_deg'},
        'D42': validity, 'D43': velocity_fields, 'D44': velocity_fields,
        'D45': velocity_fields | velocity_std, 'D46': validity, 'D47': velocity_fields,
        'D48': velocity_fields, 'D49': velocity_fields | velocity_std, 'D50': velocity_fields,
        'D51': {'roll_rad', 'pitch_rad'} | validity, 'D52': {'roll_rad', 'pitch_rad'},
        'D53': {'vn', 've'}, 'D54': {'vn', 've'} | validity,
        'D55': {'audit_go2_metadata'}, 'D56': {'audit_go2_metadata'}, 'D57': {'time'},
        'D58': validity | {'yaw_deg'}, 'D59': position_fields | velocity_fields,
        'D60': position_fields | position_std | velocity_fields | velocity_std | {'yaw_deg', 'yaw_std_deg'},
        'CLEAN': set(),
    })
    for source, diff in source_diff.items():
        check('changed_field_scope_'+source, set(diff['changed_field_counts']) <= field_scope[type_id],
              {'changed': sorted(diff['changed_field_counts']), 'allowed': sorted(field_scope[type_id])})
    window_types = {*(f'D{i:02d}' for i in range(1, 8)), 'D30', 'D31', 'D42', 'D46', 'D58', 'D60'}
    if type_id in window_types:
        windows = []
        for component in components:
            if component['component'] == 'clean_recovery_interval':
                continue
            detail = component['details']
            windows.extend(detail.get('intervals', []))
            if 'interval' in detail:
                windows.append(detail['interval'])
        for source in changed:
            table = base.bundle.tables[source]
            affected_times = [float(left['time']) for left, right in _pairs(table, generated.tables[source], type_id)
                              if any(str(left.get(k, '')) != str(right.get(k, '')) for k in table.fields)]
            check('actual_time_window_'+source,
                  bool(windows) and all(any(float(a) <= t < float(b) for a, b in windows) for t in affected_times),
                  'actual changed rows stay inside unchanged frozen fault intervals; recovery stays clean')
    for source, diff in source_diff.items():
        check('no_row_deletion_'+source, diff['row_count_before'] == diff['row_count_after'],
              'missingness uses valid/update flags, not deleted rows')
        check('no_invalid_observation_reenabled_'+source,
              all(_valid(left) or not _valid(right) for left, right in _pairs(base.bundle.tables[source], generated.tables[source], type_id)),
              'fault injection cannot create a new valid observation')
        if type_id != 'D57':
            check('timestamp_invariant_'+source, diff['time_and_row_identity_preserved'],
                  'only D57 can change source timestamps')
        check('finite_empirical_deltas_'+source,
              all(math.isfinite(float(v)) for field in diff['numeric_field_delta'].values()
                  for key, v in field.items() if key != 'count'),
              'empirical source delta summary contains finite amplitudes')
    if type_id != 'D57':
        check('a1_invalid_grid_values_preserved',
              all(old[13:15] == new[13:15] and new[17] == '0'
                  for old, new in zip(base.gnss_tokens, gnss_rows) if old[17] == '0'),
              'heading faults act only on original effective A1 rows')
    if type_id in {'D29', 'D40', 'D55', 'D56'}:
        unchanged = gnss_rows == base.gnss_tokens and all(
            generated.tables[source].canonical_bytes() == base.bundle.tables[source].canonical_bytes()
            for source in SOURCE_TO_ROLE)
        check('metadata_only_runtime_identity', unchanged and semantics.get('no_active_path') is True,
              'all five solver inputs invariant; audit perturbation retained')
    magnitude_laws = {
        'D16': ('gnss_position', 'position_delta_h_m', 1.5),
        'D17': ('gnss_position', 'position_delta_h_m', 3.0),
        'D19': ('gnss_position', 'position_delta_h_m', 2.0),
        'D20': ('gnss_position', 'position_delta_h_m', 2.0),
        'D21': ('gnss_position', 'position_delta_h_m', 4.0),
        'D22': ('gnss_position', 'position_delta_h_m', 8.0),
        'D44': ('receiver_velocity', 'velocity_delta_norm_mps', 2.0),
        'D48': ('raw_doppler', 'velocity_delta_norm_mps', 1.5),
        'D50': ('raw_doppler', 'velocity_delta_norm_mps', 1.0),
    }
    if type_id in magnitude_laws:
        source, field, target = magnitude_laws[type_id]
        actual = source_diff[source]['numeric_field_delta'].get(field)
        passed = actual is None or (abs(actual['min']-target) < 1e-4 and abs(actual['max']-target) < 1e-4)
        check('deterministic_vector_magnitude', passed, {'field': field, 'target': target, 'empirical': actual})
    if type_id in {'D16', 'D17', 'D20', 'D21', 'D22'}:
        target = {'D16': .5, 'D17': 1.0, 'D20': 1.0, 'D21': 2.0, 'D22': 4.0}[type_id]
        actual = source_diff['gnss_position']['numeric_field_delta'].get('position_delta_u_m')
        check('deterministic_vertical_magnitude', actual is None or
              (abs(actual['min_abs']-target) < 1e-4 and abs(actual['max_abs']-target) < 1e-4),
              {'target_abs_up_m': target, 'empirical': actual})
    if type_id in {'D34', 'D35', 'D58'}:
        values = [abs(_wrap(_finite(right['yaw_deg'])-_finite(left['yaw_deg'])))
                  for left, right in _pairs(base.bundle.tables['dual_yaw'], generated.tables['dual_yaw'], type_id)
                  if left['yaw_deg'] != right['yaw_deg']]
        check('ten_degree_yaw_spikes', all(abs(value-10.0) <= 1e-6 for value in values),
              {'changed_count': len(values), 'signed_magnitude_deg': 10.0})
    if type_id == 'D57':
        for component in components:
            source = component['affected_source']
            params = component['details']
            delta = source_diff[source]['numeric_field_delta']['time']
            check('d57_time_range_'+source,
                  delta['min'] >= params['latency_s']-params['jitter_max_s']-1e-8 and
                  delta['max'] <= params['latency_s']+params['jitter_max_s']+1e-8,
                  'unchanged registered latency and uniform jitter bounds')
    return {'passed': True, 'status': 'PASS_SEMANTIC_EQUIVALENCE', 'checks': checks,
            'equivalence_rule': mapping['equivalence_rule'],
            'canonical_injection_source_sha256': _hash(Path(canonical.__file__)),
            'adapter_source_sha256': _hash(Path(__file__)),
            'stochastic_equality_policy': 'same registered per-measurement distribution and named RNG substreams; cross-cadence numeric realization equality is not required',
            'empirical_check_scope': 'finite deltas, declared source/time support, deterministic amplitudes; Gaussian empirical extrema are not bounded post hoc',
            'count_override_policy': 'D22/D39 selection replaced by preregistered seconds; unchanged amplitude/direction substreams retained'}


def generate_case(base: BaseInputs, case_row: Mapping[str, Any], mapping: Mapping[str, Any], output_root: str | Path,
                  *, code_commit: str | None = None, config_hash: str | None = None) -> dict[str, Any]:
    """Create exactly output_root/case_id once, returning five solver input pins.

    Caller owns preregistration, permitted-root resolution, raw-lock checkpoints,
    source freezing and execution.  This function fails before writing on a
    nontransferable mapping, forbidden path, case mismatch or missing evidence.
    """
    case = dict(case_row)
    case_id, type_id = str(case['case_id']), str(case['degradation_type_id'])
    if base.data_mode != 'synthetic_test' and (
        not re.fullmatch(r'[0-9a-f]{40}', code_commit or '')
        or not re.fullmatch(r'[0-9a-f]{64}', config_hash or '')
    ):
        raise DegradationProviderError('Real provider generation requires full code_commit and config_hash')
    registry = {spec.type_id: spec for spec in load_type_registry()}
    if not ((type_id == 'CLEAN' and case_id == CLEAN_CASE_ID)
            or (type_id in registry and re.fullmatch(re.escape(type_id)+r'_seed_\d{2}', case_id))):
        raise DegradationProviderError('Case identity is outside the frozen registry')
    if mapping.get('degradation_type_id') != type_id or mapping.get('status') not in {'TRANSFERABLE', 'CLEAN_REFERENCE'}:
        raise DegradationProviderError('Case transfer mapping is not admitted')
    for pin in (*base.providers.values(), *base.auxiliary_roles.values()):
        _checked_pin(pin)
    frozen = _frozen_summary(mapping, case_id)
    root = Path(output_root).expanduser()
    if not root.is_absolute() or '..' in root.parts or any(path.is_symlink() for path in (root, *root.parents)):
        raise DegradationProviderError('Output root must be absolute without symlinks')
    if base.data_mode != 'synthetic_test' and not any(part.startswith('CLEAN5_DEGSUBSET_') for part in root.parts):
        raise DegradationProviderError('Real provider output requires CLEAN5_DEGSUBSET_* family')
    for pin in (*base.providers.values(), *base.auxiliary_roles.values()):
        source = Path(pin['path'])
        if root == source.parent or root.is_relative_to(source.parent) or source.is_relative_to(root):
            raise DegradationProviderError('Output root overlaps an immutable input directory')
    case_root = root/case_id
    if case_root.exists():
        raise DegradationProviderError('Case output already exists; no overwrite or retry')
    if type_id in {'D22', 'D39'}:
        generated, components, semantics = _apply_count_intervals(base.bundle, case, mapping)
    else:
        generated, components, semantics = canonical.apply_degradation(base.bundle, case)
    source_diff = {source: _diff_source(base.bundle.tables[source], table, type_id)
                   for source, table in generated.tables.items()}
    rows = _gnss_rows(base, generated, type_id)
    if any(len(row) != 18 or any(_finite(v) not in (0, 1) for v in row[15:]) for row in rows):
        raise DegradationProviderError('Generated GNSS18 validity contract failed')
    if any(_finite(a[0]) >= _finite(b[0]) for a, b in zip(rows, rows[1:])):
        raise DegradationProviderError('Generated GNSS time is not strictly increasing')
    equivalence = _semantic_equivalence(base, generated, case, mapping, components,
                                        semantics, source_diff, frozen, rows)
    case_root.mkdir(parents=True, exist_ok=False)
    providers = {role: {**pin, 'storage_mode': 'pinned_unchanged_pointer'} for role, pin in base.providers.items()}
    if rows != base.gnss_tokens:
        destination = case_root/FILENAMES['gnsspath']
        if type_id == 'D57':
            payload = ''.join(' '.join(row)+'\n' for row in rows)
        else:
            lines = list(base.gnss_lines)
            for index, row in enumerate(rows):
                if row != base.gnss_tokens[index]:
                    lines[base.gnss_data_line_indices[index]] = ' '.join(row)+'\n'
            payload = ''.join(lines)
        with destination.open('xb') as stream:
            stream.write(payload.encode('utf-8'))
        providers['gnsspath'] = {'path': str(destination), 'sha256': _hash(destination), 'storage_mode': 'materialized'}
    for source, role in SOURCE_TO_ROLE.items():
        table = generated.tables[source]
        if table.canonical_bytes() == base.bundle.tables[source].canonical_bytes():
            continue
        destination = case_root/FILENAMES[role]
        with destination.open('xb') as stream:
            stream.write(table.canonical_bytes())
        providers[role] = {'path': str(destination), 'sha256': _hash(destination), 'storage_mode': 'materialized'}
    audit_sources = ('source_quality_metadata', 'dual_yaw')
    audit_payloads = {}
    for source in audit_sources:
        if not source_diff[source]['affected_row_count']:
            continue
        destination = case_root/(source+'_AUDIT.csv')
        with destination.open('xb') as stream:
            stream.write(generated.tables[source].canonical_bytes())
        audit_payloads[source] = {'path': str(destination), 'sha256': _hash(destination), 'solver_input': False}
    data_mode = ('synthetic_test' if base.data_mode == 'synthetic_test' else
                 'real_clean' if type_id == 'CLEAN' else 'real_base_controlled_degradation')
    result = {
        'schema_version': 'clean5.degradation_provider.v1', 'case_id': case_id,
        'degradation_type_id': type_id, 'provider_family': 'CLEAN5_DEGSUBSET_'+case_id,
        'case_root': str(case_root), 'data_mode': data_mode,
        'synthetic_data_used': base.synthetic_data_used,
        'semisynthetic_data_used': base.semisynthetic_data_used,
        'controlled_degradation_applied': type_id != 'CLEAN',
        'controlled_degradation_flag_policy': 'frozen Canonical semantics; deliberate perturbation distinguished from synthetic raw input',
        'trace_used_online': False, 'raw_trace_open_count': 0, 'metric_used': False,
        'receiver_imu_as_body_imu': False, 'final_v23_output_solver_input': False,
        'LegSA_output_solver_input': False, 'output_only_correction': False,
        'epoch_deleted_for_metric': False, 'old_runtime_input_count': 0,
        'per_case_tuning': False, 'raw_mutation': False, 'solver_execution_count': 0,
        'evaluator_execution_count': 0, 'providers': providers, 'audit_payloads': audit_payloads,
        'code_commit': code_commit or 'SYNTHETIC_TEST_NOT_FORMAL',
        'config_hash': config_hash or 'SYNTHETIC_TEST_NOT_FORMAL',
        'base_provider_pins': base.providers, 'auxiliary_source_pins': base.auxiliary_roles,
        'raw_input_hashes': dict(base.bundle.raw_input_hashes), 'a1_association': base.a1_audit,
        'components': components, 'semantics': semantics, 'semantic_equivalence': equivalence,
        'runtime_contract': {
            'gnss_columns': 18, 'gnss_row_count': len(rows),
            'position_valid_count': sum(int(row[15]) for row in rows),
            'rv_valid_count': sum(int(row[16]) for row in rows),
            'a1_valid_count': sum(int(row[17]) for row in rows),
            'nominal_input_cadence': '5Hz GNSS/RV with effective 1Hz A1',
            'faulted_timing_union': type_id == 'D57',
            'missing_implementation': 'validity flags; no row deletion',
            'delete_row_control': 'NOT_APPLICABLE_frozen_library_already_uses_validity_flags',
            'C00_solver_input_byte_identity': type_id == 'CLEAN' and all(providers[r]['sha256'] == base.providers[r]['sha256'] for r in INPUT_ROLES),
        },
        'diff_summary': {'new_chain': source_diff, 'frozen_same_case': frozen,
                         'mapping': dict(mapping),
                         'amplitude_policy': 'unchanged frozen per-measurement parameters; cadence changes realization count',
                         'cross_cadence_count_equality_required': False},
    }
    _write_json(case_root/'PROVIDER_DIFF_SUMMARY.json', result['diff_summary'])
    _write_json(case_root/'DEGRADATION_PROVIDER_MANIFEST.json', result)
    return result
