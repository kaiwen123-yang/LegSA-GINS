"""Read-only, hash-locked parity input audits; never opens an evaluation trace."""
from __future__ import annotations
import csv
import math
import struct
from collections import Counter
from pathlib import Path
import numpy as np
from ...raw_gnss.ubx_raw_binary_rebuilder import iter_ubx_frames, parse_bytes_cell
from ...input_generation.imu_txt_builder import parse_sportmodestate_text
from ..horizontal_literature.shared_raw_backend import decode_nav_hpposecef
from ..manifest import sha256_file


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def stats(values):
    arr = np.asarray(values, dtype=float)
    if not len(arr):
        return {'status': 'UNAVAILABLE', 'n': 0}
    if not np.isfinite(arr).all():
        raise ValueError('Nonfinite audit data')
    return {'n': len(arr), 'min': float(arr.min()), 'max': float(arr.max()),
            'mean': float(arr.mean()), 'std_population': float(arr.std()),
            'median': float(np.median(arr)), 'p05': float(np.quantile(arr, .05)),
            'p95': float(np.quantile(arr, .95))}


def stamp(row, prefix):
    return int(row[prefix + 'secs']) + int(row[prefix + 'nsecs']) * 1e-9


def epoch_key(row):
    """Identity rounding to UBX integer milliseconds, never timestamp fitting."""
    return round(float(row['time_gps_tow']) * 1000)


def decode_receiver(path):
    hp, pvt = {}, {}
    for line, row in enumerate(csv_rows(path), 2):
        name = row.get('name')
        if name not in ('UBX-NAV-HPPOSECEF', 'UBX-NAV-PVT'):
            continue
        frames = list(iter_ubx_frames(parse_bytes_cell(row['data'])))
        if len(frames) != 1:
            raise ValueError(f'Invalid UBX record {line}')
        frame = frames[0]
        payload = frame[6:-2]
        if name == 'UBX-NAV-HPPOSECEF':
            decoded = decode_nav_hpposecef(payload)
            key = decoded.itow_ms
            target = hp
            entry = {'ecef_m': decoded.position_ecef_m.tolist(), 'pAcc_m': decoded.position_accuracy_m}
        else:
            if frame[2:4] != bytes((1, 7)) or len(payload) != 92:
                raise ValueError('PVT class/length mismatch')
            key = struct.unpack_from('<I', payload)[0]
            target = pvt
            entry = {'velocity_mps': [v * .001 for v in struct.unpack_from('<iii', payload, 48)],
                     'hAcc_m': struct.unpack_from('<I', payload, 40)[0] * .001,
                     'vAcc_m': struct.unpack_from('<I', payload, 44)[0] * .001,
                     'receipt_stamp': stamp(row, 'stamp.')}
        if key in target:
            raise ValueError('Duplicate UBX epoch')
        target[key] = {**entry, 'itow_ms': key, 'csv_line': line}
    if not hp or set(hp) != set(pvt):
        raise ValueError('HP/PVT exact epoch coverage mismatch')
    return hp, pvt


def verify_raw(registry, sequence, paths):
    lock = registry.clean_root / '01_RAW_HASH_LOCK' / ('RAW_FILE_HASH_LOCK.csv' if sequence.dataset_id == 'BY2' else 'RAW_FILE_HASH_LOCK_CLEAN5.csv')
    locked = {r['relative_path']: r['sha256'] for r in csv_rows(lock)}
    result = []
    for path in paths:
        path = Path(path)
        relative = path.resolve().relative_to(registry.raw_root.resolve()).as_posix()
        if path.suffix in ('.bag', '.fpl') or path.name.startswith('trace_'):
            raise ValueError('Forbidden online raw role')
        actual = sha256_file(path)
        if actual != locked.get(relative):
            raise ValueError(f'Raw lock mismatch: {relative}')
        result.append({'path': str(path), 'sha256': actual, 'lock': str(lock), 'lock_sha256': sha256_file(lock)})
    return result


def accuracy_audit(status, pvt):
    errors_h, errors_v, float32_equal = [], [], []
    missing = []
    for index, row in enumerate(status):
        key = epoch_key(row)
        if key not in pvt:
            missing.append(index)
            continue
        p = pvt[key]
        h, v = float(row['pos_acc_h']), float(row['pos_acc_v'])
        errors_h.append(h - p['hAcc_m']); errors_v.append(v - p['vAcc_m'])
        float32_equal.append(h == float(np.float32(p['hAcc_m'])) and v == float(np.float32(p['vAcc_m'])))
    return {'matched_count': len(errors_h), 'missing_status_indices': missing,
            'status_minus_pvt_h_m': stats(errors_h), 'status_minus_pvt_v_m': stats(errors_v),
            'float64_exact_equal_count': sum(h == 0 and v == 0 for h, v in zip(errors_h, errors_v)),
            'float32_serialization_equal_count': sum(float32_equal),
            'all_equal_at_status_float32_precision': bool(float32_equal) and all(float32_equal),
            'semantics': 'status float32 versus UBX integer millimetres; no fit'}


def static_acceleration_audit(registry, frozen_config):
    result = {'report_only': True, 'parameter_tokens': {}, 'sequences': {}}
    for line in Path(frozen_config).read_text().splitlines():
        key = line.split(':', 1)[0].strip()
        if key in ('abstd', 'asstd', 'corrtime'):
            result['parameter_tokens'][key] = line
    for name, sequence in registry.sequences.items():
        source = verify_raw(registry, sequence, [sequence.body_path])
        frames = parse_sportmodestate_text(sequence.body_path, max_messages=1000)
        result['sequences'][name] = {'source': source, 'first_frame_count': len(frames),
            'accelerometer_norm_mps2': stats([math.sqrt(sum(v*v for v in f['accelerometer'])) for f in frames]),
            'selection': 'first 1000 parsed messages, no stationarity-based reselection'}
    return result
