"""Frozen realized input perturbations applied after the EXT05 cache."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from ..horizontal_literature.phase5_runner import _load_cache

BASE_TIME = 1772784000.0
CLASSIC = ('D14', 'D21', 'D16', 'D18', 'D03', 'D04', 'D43', 'D42', 'D05',
           'D33', 'D35', 'D32', 'D31', 'D06', 'D46', 'D47', 'D50', 'D57')
IGNORED = {'D43', 'D42', 'D46', 'D47', 'D50'}
POSITION = {'D14', 'D21', 'D16', 'D18'}
HEADING = {'D33', 'D35', 'D32'}
OUTAGE = {'D03', 'D04', 'D05', 'D06', 'D31', 'D62'}
FAMILIES = {
    'D14': '位置噪声', 'D21': '位置噪声', 'D16': '位置偏差', 'D18': '位置偏差',
    'D03': '位置中断', 'D04': '位置中断', 'D43': '速度噪声', 'D42': '速度中断',
    'D05': '速度中断', 'D33': '航向噪声', 'D35': '航向噪声', 'D32': '航向噪声',
    'D31': '航向中断', 'D06': '航向中断', 'D46': '多普勒', 'D47': '多普勒',
    'D50': '多普勒', 'D57': '时间戳', 'D62': 'A2', 'D61': 'A1等价报告', 'C00': '身份门',
}
SOLUTION_KEYS = ('solution_times', 'solution_itow', 'p1', 'p2', 'pacc1', 'pacc2', 'valid1', 'valid2')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + '\n')


def resolve(text, roots):
    for key, value in roots.items():
        text = text.replace('$' + key, str(value))
    return Path(text)


def llh_to_ecef(rows):
    lat, lon = np.deg2rad(rows[:, 1]), np.deg2rad(rows[:, 2])
    h = rows[:, 3]
    a = 6378137.0
    e2 = (1 / 298.257223563) * (2 - 1 / 298.257223563)
    N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    return np.column_stack(((N + h) * np.cos(lat) * np.cos(lon),
                            (N + h) * np.cos(lat) * np.sin(lon),
                            (N * (1 - e2) + h) * np.sin(lat)))


def read_spec_inputs(spec, roots):
    for item in spec['sources']:
        if sha(resolve(item['path'], roots)) != item['sha256']:
            raise ValueError('HARD_STOP_INPUT_PIN: ' + item['path'])
    return {item['role']: resolve(item['path'], roots) for item in spec['sources']}


def base_indices(base, arrays):
    """Convert base-relative UTC millisecond keys to the cache iTOW keys."""
    utc_ms = np.rint((arrays['solution_times'] - BASE_TIME) * 1000).astype(np.int64)
    offset = np.asarray(arrays['solution_itow'], dtype=np.int64) - utc_ms
    if not np.all(offset == offset[0]):
        raise ValueError('HARD_STOP_ITOW_UTC_OFFSET')
    keys = np.rint(base[:, 0] * 1000).astype(np.int64) + offset[0]
    if len(set(keys.tolist())) != len(keys):
        raise ValueError('HARD_STOP_DUPLICATE_BASE_ITOW')
    mapping = dict(zip(keys.tolist(), range(len(keys))))
    return np.asarray([mapping[int(k)] for k in arrays['solution_itow']])


def transform(arrays, manifest, spec, method, paths):
    """No RNG; original IMU and receiver accuracy arrays stay unchanged."""
    a = {key: np.asarray(value).copy() for key, value in arrays.items()}
    t = a['solution_times'] - BASE_TIME
    relative_only = np.zeros(len(t), dtype=bool)
    kind = spec['type']
    report = {'type': kind, 'method': method, 'operations': [], 'relative_only_epochs': 0}
    if kind == 'C00' or kind in IGNORED:
        return a, relative_only, report
    bundle = json.loads(paths['bundle'].read_text())
    if kind in POSITION:
        base, case = np.loadtxt(paths['base_gnss']), np.loadtxt(paths['case_gnss'])
        base_keys = np.rint(base[:, 0] * 1000).astype(np.int64)
        case_keys = np.rint(case[:, 0] * 1000).astype(np.int64)
        if not np.array_equal(base_keys, case_keys):
            raise ValueError('HARD_STOP_POSITION_ITOW')
        # Both receiver vectors are in the original cache fixed NED frame.
        delta = (llh_to_ecef(case) - llh_to_ecef(base)) @ np.asarray(manifest['ecef_to_ned']).T
        indices = base_indices(base, arrays)
        a['p1'] += delta[indices]
        a['p2'] += delta[indices]
        report['operations'].append('same_NED_translation_to_p1_and_p2')
    elif kind in HEADING:
        base = np.loadtxt(paths['base_gnss'])
        clean = base[base[:, 17] == 1]
        with paths['heading_audit'].open(newline='') as f:
            fault = list(csv.DictReader(f))
        if len(clean) != len(fault):
            raise ValueError('HARD_STOP_HEADING_CELL_COUNT')
        starts = clean[:, 0]
        if not np.allclose(np.diff(starts), 1, rtol=0, atol=1e-6):
            raise ValueError('HARD_STOP_HEADING_CELL_SCHEDULE')
        if not np.allclose([float(row['time']) for row in fault], starts, rtol=0, atol=1e-6):
            raise ValueError('HARD_STOP_HEADING_CELL_TIME')
        deltas = (np.asarray([float(row['yaw_deg']) for row in fault]) - clean[:, 13] + 180) % 360 - 180
        cell = np.searchsorted(starts, t, side='right') - 1
        active = (cell >= 0) & (t < starts[-1] + 1)
        angle = np.zeros(len(t))
        angle[active] = np.deg2rad(deltas[cell[active]])
        baseline = a['p2'] - a['p1']
        rotated = baseline.copy()
        c, s = np.cos(angle), np.sin(angle)
        rotated[:, 0] = c * baseline[:, 0] - s * baseline[:, 1]
        rotated[:, 1] = s * baseline[:, 0] + c * baseline[:, 1]
        # Preserve exact input bytes where delta is zero.
        changed = angle != 0
        a['p2'][changed] = a['p1'][changed] + rotated[changed]
        report['operations'].append('NED_positive_yaw_rotation_p2_about_p1_1s_cells')
    elif kind in OUTAGE:
        wanted = 'dual_yaw' if kind == 'D31' else 'gnss_position'
        intervals = []
        for component in bundle['components']:
            if component['affected_source'] == wanted:
                details = component['details']
                intervals += [details['interval']] if 'interval' in details else details.get('intervals', [])
        if not intervals:
            raise ValueError('HARD_STOP_MISSING_OUTAGE_INTERVAL')
        mask = np.zeros(len(t), dtype=bool)
        for left, right in intervals:
            mask |= (t >= left) & (t < right)
        if kind == 'D62' and method == 'LC01-BR':
            relative_only = mask & a['valid1'] & a['valid2']
        elif kind == 'D31':
            a['valid2'][mask] = False
        else:
            a['valid1'][mask] = False
            if method != 'EXT05C' or kind == 'D06':
                a['valid2'][mask] = False
        report.update(intervals=intervals, interval_epochs=int(mask.sum()))
    elif kind == 'D57':
        base, case = np.loadtxt(paths['base_gnss']), np.loadtxt(paths['case_gnss'])
        positions = case[case[:, 15] == 1]
        # Positive delay+jitter never crosses adjacent 0.2 s position epochs.
        if len(positions) != len(base) or not np.array_equal(positions[:, 1:7], base[:, 1:7]):
            raise ValueError('HARD_STOP_D57_POSITION_ROW_ASSOCIATION')
        component = next(c for c in bundle['components'] if c['affected_source'] == 'gnss_position')
        latency, jitter = component['details']['latency_s'], component['details']['jitter_max_s']
        offsets = positions[:, 0] - base[:, 0]
        if np.max(np.abs(offsets - latency)) > jitter + 2e-9:
            raise ValueError('HARD_STOP_D57_OFFSET_BOUNDS')
        indices = base_indices(base, arrays)
        a['solution_times'] += offsets[indices]
        order = np.argsort(a['solution_times'], kind='stable')
        for key in SOLUTION_KEYS:
            a[key] = a[key][order]
        report.update(latency_s=latency, jitter_max_s=jitter, realized_offsets_min_max_s=[float(offsets.min()), float(offsets.max())])
    else:
        raise ValueError('HARD_STOP_UNREGISTERED_TYPE: ' + kind)
    report['relative_only_epochs'] = int(relative_only.sum())
    for key in ('imu_times', 'gyro', 'accel', 'pacc1', 'pacc2'):
        if not np.array_equal(a[key], arrays[key]):
            raise ValueError('HARD_STOP_UNEXPECTED_ARRAY_CHANGE: ' + key)
    return a, relative_only, report


def materialize(base_cache, destination, spec, method, roots):
    paths = read_spec_inputs(spec, roots)
    arrays, metadata = _load_cache(Path(base_cache))
    arrays, relative, report = transform(arrays, metadata, spec, method, paths)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, array in {**arrays, 'relative_only': relative}.items():
        p = destination / (name + '.npy')
        np.save(p, array, allow_pickle=False)
        hashes[p.name] = sha(p)
    specification_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    write_json(destination / 'CACHE_MANIFEST.json', {
        'schema_version': 'hx03.injected_cache.v1', 'array_hashes': hashes,
        'calibration': metadata['calibration'], 'origin_ecef_m': metadata['origin_ecef_m'],
        'ecef_to_ned': metadata['ecef_to_ned'],
        'base_cache_manifest_sha256': sha(Path(base_cache) / 'CACHE_MANIFEST.json'),
        'injection_spec_sha256': specification_hash, 'injection_report': report,
    })
    return {'spec_sha256': specification_hash, 'arrays': hashes, 'report': report,
            'cache_manifest_sha256': sha(destination / 'CACHE_MANIFEST.json')}
