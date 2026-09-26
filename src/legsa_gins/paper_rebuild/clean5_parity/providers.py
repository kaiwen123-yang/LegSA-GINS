"""Exclusive CLEAN5_PARITY providers, derived from pinned observations and V0 bytes.

No solver/evaluator calls. Caller must bracket generation with raw checkpoints
and strace, and run only from a committed detached code snapshot.
"""
from __future__ import annotations
import json
import math
import re
from collections import Counter
from pathlib import Path
import numpy as np
from ..clean5_sequence.provider_chain import _copy_exclusive, _provider_entry, _write_json_exclusive
from ..horizontal_literature.shared_raw_backend import ecef_to_geodetic
from ..manifest import sha256_file, sha256_text
from .input_audit import (accuracy_audit, csv_rows, decode_receiver, epoch_key,
                          stamp, stats, static_acceleration_audit, verify_raw)


class ParityProviderError(ValueError):
    pass


def resolve_alias(registry, value):
    text = str(value)
    for alias, path in (('<CLEAN_ROOT>', registry.clean_root), ('<RAW_ROOT>', registry.raw_root), ('<CODE_ROOT>', registry.code_root)):
        text = text.replace(alias, str(path))
    path = Path(text)
    if '<' in text or not path.is_absolute():
        raise ParityProviderError('Unresolved input alias')
    return path


def checked_source(registry, spec):
    path = resolve_alias(registry, spec['path'])
    if sha256_file(path) != spec['sha256']:
        raise ParityProviderError(f'Frozen source hash mismatch: {path.name}')
    return path


def append_validity(line, flags=(1, 1, 1)):
    """Preserve all original fifteen-field bytes before the newline."""
    content = line.rstrip(b'\r\n')
    if len(content.split()) != 15 or any(x not in (0, 1) for x in flags):
        raise ParityProviderError('Expected fifteen columns and binary validity')
    if not all(math.isfinite(float(x)) for x in content.split()):
        raise ParityProviderError('Nonfinite GNSS input')
    return content + b' ' + (' '.join(map(str, flags))).encode() + b'\n'


def replace_time(line, time):
    if not math.isfinite(time):
        raise ParityProviderError('Nonfinite epoch')
    return re.sub(rb'^\s*\S+', f'{time:.9f}'.encode(), line, count=1)


def build_variants(v0_bytes, status, hp, pvt, *, base_time, window, a1_source_times):
    lines = v0_bytes.splitlines(keepends=True)
    if len(lines) != len(status):
        raise ParityProviderError('V0/status row count mismatch')
    weeks = {int(float(s['time_gps_wno'])) for s in status}
    if len(weeks) != 1:
        raise ParityProviderError('Week rollover requires explicit contract')
    week = weeks.pop()
    utc = lambda key: 315964800 + week * 604800 + key / 1000 - 18 - base_time
    status_map, yaw_map = {}, {}
    # Match frozen physical A1 timestamps to their status message identities;
    # source timestamp double representation differs at submicrosecond scale.
    source_a1 = {round(t * 1000) for t in a1_source_times}
    outputs = {'V0-18': [], 'V1': [], 'V2': [], 'V2e': []}
    missing_rv, header_residual, rv_receipt_offset = [], [], []
    for index, (line, s) in enumerate(zip(lines, status)):
        f = line.split(); key = epoch_key(s)
        header = stamp(s, 'header.stamp.') - base_time
        if abs(float(f[0]) - (stamp(s, 'sys_stamp.') - base_time)) > 1e-6:
            raise ParityProviderError('V0/status sys-stamp lineage mismatch')
        if key in status_map:
            raise ParityProviderError('Duplicate status epoch identity')
        status_map[key] = s
        if round(stamp(s, 'header.stamp.') * 1000) in source_a1:
            yaw_map[key] = f[13:15]
        rv_valid = int(key in pvt)
        if rv_valid:
            values = [f'{v:.6f}'.encode() for v in pvt[key]['velocity_mps']]
            if f[7:10] != values:
                raise ParityProviderError(f'V1 frozen RV token mismatch row {index}')
            header_residual.append(header - utc(key))
            rv_receipt_offset.append(pvt[key]['receipt_stamp'] - base_time - utc(key))
        else:
            missing_rv.append({'row_index': index, 'itow_ms': key, 'header_time': header})
            if window[0] <= header <= window[1]:
                raise ParityProviderError('Missing exact-epoch V1 RV inside runtime window')
        v1 = append_validity(replace_time(line, header), (1, rv_valid, 1))
        if v1.split()[1:15] != f[1:15]:
            raise ParityProviderError('V1 measurement token mutation')
        outputs['V0-18'].append(append_validity(line))
        outputs['V1'].append(v1)
    position_diffs = []
    for key in sorted(hp):
        h, p = hp[key], pvt[key]
        lat, lon, height = ecef_to_geodetic(h['ecef_m'])
        position = [math.degrees(lat), math.degrees(lon), height]
        yaw = yaw_map.get(key, [b'0.000000', b'1.500000'])
        fields = [f'{utc(key):.9f}', f'{position[0]:.12f}', f'{position[1]:.12f}', f'{height:.9f}',
                  *[f'{v:.6f}' for v in (p['hAcc_m'], p['hAcc_m'], p['vAcc_m'])],
                  *[f'{v:.6f}' for v in p['velocity_mps']], '0.050000', '0.050000', '0.050000',
                  *[v.decode() for v in yaw]]
        line = ' '.join(fields).encode() + b'\n'
        outputs['V2'].append(append_validity(line, (1, 1, int(key in yaw_map))))
        e = fields[:]
        e[4:7] = [f"{h['pAcc_m']:.9f}"] * 3
        e[7:10] = ['0.000000'] * 3
        e[13:15] = ['0.000000', '1.500000']
        outputs['V2e'].append(append_validity(' '.join(e).encode(), (1, 0, 0)))
        if key in status_map:
            s = status_map[key]
            # Source comparison in metres via local geodetic differential, not
            # provider rounding (V0 latitude/longitude only have six decimals).
            latitude = math.radians(float(s['pos_lat']))
            a, e2 = 6378137., 6.6943799901413165e-3
            n = a / math.sqrt(1-e2*math.sin(latitude)**2)
            m = a*(1-e2)/(1-e2*math.sin(latitude)**2)**1.5
            north = (lat-latitude)*(m+float(s['pos_height']))
            east = (lon-math.radians(float(s['pos_lon'])))*(n+float(s['pos_height']))*math.cos(latitude)
            up = height-float(s['pos_height'])
            position_diffs.append({'itow_ms': key, 'north_m': north, 'east_m': east, 'up_m': up,
                                   'norm_m': math.sqrt(north*north+east*east+up*up)})
    audit = {'v1_non_time_measurement_tokens_byte_equal': True,
             'v1_exact_epoch_rv_matched_count': len(status)-len(missing_rv),
             'v1_missing_rv_outside_window': missing_rv,
             'v1_header_minus_same_identity_itow_s': stats(header_residual),
             'frozen_pvt_receipt_minus_itow_s': stats(rv_receipt_offset),
             'a1_frozen_source_epoch_count': len(source_a1), 'a1_status_mapped_count': len(yaw_map),
             'a1_hp_mapped_count': len(set(yaw_map)&set(hp)),
             'a1_missing_hp_itow_ms': sorted(set(yaw_map)-set(hp)),
             'status_not_frozen_a1_itow_ms': sorted(set(status_map)-set(yaw_map)),
             'a1_runtime_start_exclusive_hp_count': sum(window[0] < utc(k) <= window[1] for k in set(yaw_map)&set(hp)),
             'status_accuracy': accuracy_audit(status, pvt),
             'hpposecef_minus_status_common_epochs': position_diffs,
             'hpposecef_minus_status_norm_m': stats([r['norm_m'] for r in position_diffs]),
             'same_source_within_5mm': bool(position_diffs) and max(r['norm_m'] for r in position_diffs) <= .005,
             'RV_std_policy': 'frozen 0.050000 tokens; PVT sAcc not substituted',
             'auxiliary_scheduling': 'RD/RP/HV evaluated at every GNSS row; copied payload bytes unchanged; row timing/rate changes selections and counters'}
    if not audit['status_accuracy']['all_equal_at_status_float32_precision']:
        raise ParityProviderError('Status/PVT position accuracy semantic gate failed')
    return {k: b''.join(v) for k, v in outputs.items()}, audit


def generate_providers(*, registry, stage_root, contract, code_commit):
    root = Path(stage_root).resolve()
    expected = registry.clean_root / 'stages' / contract['stage_id']
    if root != expected.resolve() or not contract['stage_id'].startswith('CLEAN5_BY2_C00_INPUT_PARITY_'):
        raise ParityProviderError('Provider output outside authorized parity stage')
    spec = contract['frozen_runtime']['original_configs']['A04']
    sources = {role: checked_source(registry, value) for role, value in spec['provider_inputs'].items()}
    config = checked_source(registry, {'path': spec['runtime_config'], 'sha256': spec['runtime_config_sha256']})
    a1_spec = contract['frozen_a1_provider']
    a1 = checked_source(registry, a1_spec)
    a1_rows = csv_rows(a1)
    baseline_column = a1_spec['baseline_column']
    baseline = stats([float(r[baseline_column]) for r in a1_rows])
    sequence = registry.sequences['BY2']
    raw_paths = [sequence.fix_root / 'gnss1-status.csv', sequence.fix_root / 'gnss1-raw.csv']
    raw = verify_raw(registry, sequence, raw_paths)
    status = csv_rows(raw_paths[0]); hp, pvt = decode_receiver(raw_paths[1])
    window = contract['frozen_runtime']['window_seconds']
    payloads, audit = build_variants(sources['gnsspath'].read_bytes(), status, hp, pvt,
        base_time=contract['frozen_runtime']['base_time'], window=window,
        a1_source_times=[float(r['source_timestamp']) for r in a1_rows])
    if len(status) != 303 or len(hp) != 1510:
        raise ParityProviderError('Frozen BY2 row count mismatch')
    audit['raw_sources'] = raw
    audit['frozen_a1_provider'] = {'path': str(a1), 'sha256': a1_spec['sha256'], 'baseline_column': baseline_column,
        'requested_semantic_name': 'baseline_len_m', 'row_count': len(a1_rows), 'baseline_length_m': baseline,
        'baseline_median_m': baseline['median']}
    audit['static_acceleration'] = static_acceleration_audit(registry, config)
    target = root / '02_PARITY_PROVIDERS'
    target.mkdir(exist_ok=False)
    common = {'schema_version': 'paper_rebuild.clean5.parity_provider.v2', 'data_mode': 'real_by2_raw',
        'synthetic_data_used': False, 'semisynthetic_data_used': False, 'trace_used_online': False,
        'receiver_imu_as_body_imu': False, 'final_v23_output_solver_input': False, 'LegSA_output_solver_input': False,
        'per_case_tuning': False, 'output_only_correction': False, 'epoch_deleted_for_metric': False,
        'old_runtime_input_count': 0, 'code_commit': code_commit, 'stage_id': contract['stage_id'],
        'config_hash': sha256_text(json.dumps(contract, sort_keys=True)), 'raw_source_hashes': raw,
        'frozen_input_hashes': spec['provider_inputs']}
    result = {**common, 'variants': {}, 'audit': audit,
              'baseline_median_m': baseline['median'], 'frozen_a1_provider': audit['frozen_a1_provider']}
    for variant, payload in payloads.items():
        directory = target / variant
        directory.mkdir()
        gnss = directory / 'PARITY.gnss'
        with gnss.open('xb') as stream:
            stream.write(payload)
        providers = {'gnsspath': _provider_entry(gnss, window, time_origin='frozen_BY2_R1')}
        for role, source in sources.items():
            if role == 'gnsspath':
                continue
            destination = _copy_exclusive(source, directory / source.name)
            providers[role] = {'path': str(destination), 'sha256': sha256_file(destination), 'frozen_source': str(source)}
            if providers[role]['sha256'] != spec['provider_inputs'][role]['sha256']:
                raise ParityProviderError('Copied auxiliary hash mismatch')
        rows = [[float(v) for v in line.split()] for line in payload.splitlines()]
        counts = {}
        for scope, selected in [('full', rows), ('closed_window', [r for r in rows if window[0] <= r[0] <= window[1]]),
                                ('runtime_start_exclusive', [r for r in rows if window[0] < r[0] <= window[1]])]:
            counts[scope] = {'rows': len(selected), **{name: sum(int(r[col]) for r in selected)
                for name, col in [('position_valid',15),('velocity_valid',16),('yaw_valid',17)]}}
        manifest = {**common, 'variant': variant, 'provider_family': 'CLEAN5_PARITY_'+variant.replace('-', '_'),
            'providers': providers, 'counts': counts,
            'fractional_second_distribution': dict(Counter(f'{r[0]%1:.6f}' for r in rows)),
            'runtime_input_columns': 18, 'audit_path': str(target/'INPUT_AUDIT.json')}
        _write_json_exclusive(directory / 'PROVIDER_MANIFEST.json', manifest)
        result['variants'][variant] = manifest
    _write_json_exclusive(target / 'INPUT_AUDIT.json', audit)
    _write_json_exclusive(target / 'PROVIDER_MANIFEST.json', result)
    return result
