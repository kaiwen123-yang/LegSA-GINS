"""HX-05 input reference: the unchanged HX-02D C4 kinematic definition."""
from __future__ import annotations
import csv
import json
import numpy as np
from scipy.spatial.transform import Rotation

from .hx02d_reference_free import integrate, load_cache, load_raw
from .hx05_common import dump, sha


def kinematic_velocity(gyro, feet, foot_speed, contacts):
    count = contacts.sum(axis=1)
    per_foot = -(np.cross(gyro[:, None, :], feet) + foot_speed)
    return np.divide((per_foot * contacts[:, :, None]).sum(axis=1), count[:, None],
                     out=np.full((len(gyro), 3), np.nan), where=count[:, None] > 0)


def compute(roots, seq, sequence, out):
    provider = roots['HX02']/'01_INPUT_PINS/HARTLEY'/seq
    manifest = json.loads((provider/'H5_INPUT_CACHE_MANIFEST.json').read_text())
    assert sha(provider/'H5_INPUT_CACHE.bin') == sequence['cache_sha256']
    cache = load_cache(provider/'H5_INPUT_CACHE.bin', manifest)
    pins = json.loads((roots['HX02']/'01_INPUT_PINS/INPUT_PINS.json').read_text())['go2'][seq]
    raw = load_raw(manifest['source_identity']['source'], {
        'raw_sha256': pins['raw']['sha256'], 'prefix_interval': [0, pins['prefix_end_exclusive']],
        'prefix_sha256': pins['prefix_sha256'], 'record_count': pins['record_separator_count']})
    index = np.searchsorted(raw['time_ns'], cache['t'])
    assert (index < len(raw['time_ns'])).all()
    assert np.array_equal(raw['time_ns'][index], cache['t'])
    raw = {key: value[index] for key, value in raw.items()}
    order = [1, 0, 3, 2]
    correction = Rotation.from_euler('x', -1, degrees=True).as_matrix()
    gyro = raw['gyroscope'] @ correction.T
    feet = raw['foot_position_body'].reshape(-1, 4, 3)[:, order]
    speed = raw['foot_speed_body'].reshape(-1, 4, 3)[:, order]
    assert np.max(np.abs(gyro - cache['v'][:, :3])) < 1e-14
    assert np.array_equal(feet.reshape(-1, 12), cache['v'][:, 10:22])
    assert np.array_equal(raw['foot_force'][:, order], cache['v'][:, 6:10])
    contacts = (cache['mask'][:, None] & (1 << np.arange(4))) != 0
    body_velocity = kinematic_velocity(gyro, feet, speed, contacts)
    rotation = Rotation.from_euler('xyz', raw['rpy']).as_matrix()
    velocity = np.einsum('nij,nj->ni', rotation, body_velocity)
    time = (cache['t'] - cache['t'][0]).astype(float) * 1e-9
    position, gaps = integrate(time, velocity)
    arrays = {'time_ns': cache['t'], 'go2_rotation': rotation, 'go2_rpy_rad': raw['rpy'],
              'leg_body_velocity': body_velocity, 'leg_go2_position': position,
              'contact_mask': cache['mask'], 'source_start_line': raw['source_start_line']}
    np.savez_compressed(out/'ARRAYS.npz', **arrays)
    receipt = {'sequence': seq, 'epochs': len(cache), 'cache_sha256': sequence['cache_sha256'],
               'raw_sha256': pins['raw']['sha256'], 'integer_ns_match': True,
               'integration_gaps': gaps, 'zero_contact_epochs': int((contacts.sum(axis=1) == 0).sum()),
               'NAV_placeholder_policy': 'Velocity is serialized as zero where unobserved; integration retains NaN gaps. Bias and state_dimension zero mean not estimated.'}
    if seq == 'BY2':
        target = roots['HX02D']/'EXECUTION_V2/B_REFERENCE_FREE/BY2/OUTPUT/B_ARRAYS.npz'
        differences = {}
        with np.load(target) as archived:
            for key, value in arrays.items():
                expected = archived[key]
                assert value.shape == expected.shape and np.array_equal(np.isnan(value), np.isnan(expected))
                differences[key] = float(np.nanmax(np.abs(value.astype(float) - expected.astype(float))))
        receipt['C4_array_gate'] = {'source_sha256': sha(target), 'max_absolute_differences': differences,
                                    'tolerance': 1e-6, 'passed': all(v <= 1e-6 for v in differences.values())}
        dump(out/'INTEGRATION_RECEIPT.json', receipt)
        assert receipt['C4_array_gate']['passed'], 'HARD_STOP_LEG_DR_C4_ARRAY_MISMATCH'
    else:
        dump(out/'INTEGRATION_RECEIPT.json', receipt)
    header = ['timestamp_ns', 'row_index', *(f'r{i}{j}' for i in range(3) for j in range(3)),
              'vx', 'vy', 'vz', 'px', 'py', 'pz', 'roll_deg', 'pitch_deg', 'yaw_deg',
              'bgx', 'bgy', 'bgz', 'bax', 'bay', 'baz', 'active_contact_count', 'state_dimension']
    with (out/'NAV.csv').open('x', newline='') as f:
        writer = csv.writer(f, lineterminator='\n'); writer.writerow(header)
        for i, stamp in enumerate(cache['t']):
            values = [*rotation[i].ravel(), *np.nan_to_num(velocity[i], nan=0),
                      *position[i], *np.degrees(raw['rpy'][i]), *np.zeros(6)]
            writer.writerow([int(stamp), i, *(format(float(v), '.17g') for v in values),
                             int(contacts[i].sum()), 0])
    return receipt


def compare_c4_metrics(roots, metrics):
    source = roots['HX02D']/'EXECUTION_V2/C_REFERENCE/BY2/OUTPUT/C_TABLES.json'
    expected = json.loads(source.read_text())['C4']['foot_speed_body']
    keys = ('horizontal_rmse_m', 'yaw_rmse_deg', 'position_drift_m_per_100m', 'heading_drift_deg_per_min')
    delta = {key: abs(metrics[key] - expected[key]) for key in keys}
    return {'source_sha256': sha(source), 'tolerance': 1e-6, 'absolute_differences': delta,
            'passed': all(v <= 1e-6 for v in delta.values())}
