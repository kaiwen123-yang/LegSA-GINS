"""HX-03 injection and relative-only math checks, no reference or real solves."""
from copy import deepcopy
from pathlib import Path
import csv
import json
import math

import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext.hx03_injection import (
    transform, read_spec_inputs, BASE_TIME, CLASSIC, IGNORED, HEADING, POSITION,
)
from legsa_gins.paper_rebuild.hext.hx03_relative_update import scheduled_update, relative_update
from legsa_gins.paper_rebuild.horizontal_literature.ext05_pavlasek import PavlasekIEKF, ExtendedPose, so3_exp
from legsa_gins.paper_rebuild.horizontal_literature.phase5_runner import _load_cache

W = Path(__file__).resolve().parents[2]
STAGES = Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages')
ROOTS = {'W': W, 'STAGES': STAGES, 'V3': STAGES / 'CLEAN8_PROTOCOL_V3'}
CONFIG = W / 'configs/paper_rebuild/hext/HX03'
CACHE = STAGES / 'CLEAN7_HEXT_EXTERNAL_SEQUENCES/02_BY2_IDENTITY/PROVIDER_CACHE'


@pytest.fixture(scope='module')
def data():
    arrays, manifest = _load_cache(CACHE)
    return arrays, manifest, json.loads((CONFIG / 'CASES.json').read_text())


@pytest.mark.parametrize('kind', ('C00', *CLASSIC, 'D62_10s', 'D62_20s'))
@pytest.mark.parametrize('method', ('LC01', 'EXT05C', 'LC01-BR'))
def test_realized_seed00_arrays(data, kind, method):
    if method == 'LC01-BR' and kind not in ('C00', 'D62_10s', 'D62_20s'):
        pytest.skip('BR only A2 and identity')
    a, manifest, cases = data
    spec = cases['C00' if kind == 'C00' else kind + '_seed_00']
    paths = read_spec_inputs(spec, ROOTS)
    b, relative, report = transform(a, manifest, spec, method, paths)
    for key in ('gyro', 'accel', 'imu_times', 'pacc1', 'pacc2'):
        assert np.array_equal(a[key], b[key])
    t = a['solution_times'] - BASE_TIME
    if kind == 'C00' or kind in IGNORED:
        assert all(np.array_equal(a[k], b[k]) for k in a)
        assert not relative.any()
    elif kind in POSITION:
        np.testing.assert_allclose(b['p2'] - b['p1'], a['p2'] - a['p1'], atol=1e-13, rtol=0)
        assert np.any(b['p1'] != a['p1'])
        assert all(np.array_equal(a[k], b[k]) for k in ('valid1', 'valid2', 'solution_times'))
        # Independent projection of the published LLH differences, centimeter
        # tolerance accounts for the linear versus WGS84 ECEF projection.
        base, case = np.loadtxt(paths['base_gnss']), np.loadtxt(paths['case_gnss'])
        R = 6378137.0
        approximate = np.column_stack((np.deg2rad(case[:, 1] - base[:, 1]) * R,
            np.deg2rad(case[:, 2] - base[:, 2]) * R * np.cos(np.deg2rad(base[:, 1])),
            -(case[:, 3] - base[:, 3])))
        np.testing.assert_allclose(b['p1'] - a['p1'], approximate, atol=.08, rtol=.01)
    elif kind in HEADING:
        old, new = a['p2'] - a['p1'], b['p2'] - b['p1']
        np.testing.assert_allclose(np.linalg.norm(new, axis=1), np.linalg.norm(old, axis=1), atol=5e-14, rtol=0)
        assert np.array_equal(b['p1'], a['p1'])
        assert np.array_equal(b['valid1'], a['valid1']) and np.array_equal(b['valid2'], a['valid2'])
        clean = np.loadtxt(paths['base_gnss']); clean = clean[clean[:, 17] == 1]
        with paths['heading_audit'].open() as f:
            fault = list(csv.DictReader(f))
        actual = np.rad2deg(np.arctan2(new[:, 1], new[:, 0]) - np.arctan2(old[:, 1], old[:, 0]))
        for i, tm in enumerate(t):
            cell = [j for j, row in enumerate(clean) if row[0] <= tm < row[0] + 1]
            expected = (float(fault[cell[0]]['yaw_deg']) - clean[cell[0], 13]) if cell else 0
            assert abs((actual[i] - expected + 180) % 360 - 180) < 1e-9
    elif kind == 'D57':
        table = np.loadtxt(paths['case_gnss']); rows = table[table[:, 15] == 1]
        np.testing.assert_allclose(b['solution_times'] - BASE_TIME, rows[:, 0], rtol=0, atol=2.4e-7)
        assert np.all(np.diff(b['solution_times']) > 0)
        assert all(np.array_equal(a[k], b[k]) for k in ('p1', 'p2', 'valid1', 'valid2'))
        assert report['latency_s'] == 0.10401432335291612
        assert report['jitter_max_s'] == 0.025616545567535644
    else:
        duration = 10 if kind in ('D03', 'D05', 'D62_10s') else 20
        mask = (t >= 206.2 - duration / 2) & (t < 206.2 + duration / 2)
        assert report['interval_epochs'] == duration * 5
        assert all(np.array_equal(a[k], b[k]) for k in ('p1', 'p2', 'solution_times'))
        if kind.startswith('D62') and method == 'LC01-BR':
            assert np.array_equal(relative, mask)
            assert np.array_equal(a['valid1'], b['valid1'])
        elif kind == 'D31':
            assert np.array_equal(a['valid1'], b['valid1'])
            assert np.array_equal(b['valid2'], a['valid2'] & ~mask)
        else:
            assert np.array_equal(b['valid1'], a['valid1'] & ~mask)
            expected = a['valid2'] & ~mask if method != 'EXT05C' or kind == 'D06' else a['valid2']
            assert np.array_equal(b['valid2'], expected)


def make_filter():
    return PavlasekIEKF(ExtendedPose(so3_exp([.1, -.2, .3]), np.zeros(3), np.array([1., 2., 3.])),
        np.diag(np.arange(1, 10) / 10), receiver1_from_imu_body_m=[.03, .03, -.30],
        receiver2_from_receiver1_body_m=[0, -.35, 0], gyro_psd=[.01] * 3,
        accelerometer_psd=[.1] * 3, gravity_ned_mps2=[0, 0, 9.81], two_receiver=True)


def state_bytes(f):
    return tuple(a.tobytes() for a in (f.pose.C_nb, f.pose.velocity_ned_mps, f.pose.position_ned_m, f.covariance))


def test_br_outside_fault_is_exact_original_update():
    a = make_filter(); b = deepcopy(a)
    kw = dict(receiver2_position_ned_m=[1., 1.65, 3.], receiver2_covariance_ned_m2=np.eye(3) * .02)
    a.update([1., 2., 3.], np.eye(3) * .01, **kw)
    scheduled_update(b, [1., 2., 3.], np.eye(3) * .01, relative_only=False, **kw)
    assert state_bytes(a) == state_bytes(b)


def test_relative_update_ignores_common_position_translation():
    a = make_filter(); b = deepcopy(a)
    p1 = np.array([1., 2., 3.]); p2 = np.array([1.1, 1.75, 3.05]); shift = np.array([20., -5., 4.])
    x = relative_update(a, p1, np.eye(3) * .01, receiver2_position_ned_m=p2,
                        receiver2_covariance_ned_m2=np.eye(3) * .02)
    y = relative_update(b, p1 + shift, np.eye(3) * .01, receiver2_position_ned_m=p2 + shift,
                        receiver2_covariance_ned_m2=np.eye(3) * .02)
    np.testing.assert_allclose(x.innovation, y.innovation, atol=3e-15, rtol=0)
    np.testing.assert_allclose(a.pose.C_nb, b.pose.C_nb, atol=1e-14, rtol=0)
    assert np.linalg.eigvalsh(a.covariance).min() >= 0
    # With no prior cross covariance, the relative measurement has no direct
    # velocity or position correction.
    assert np.array_equal(x.gain[3:], np.zeros((6, 3)))


@pytest.mark.parametrize('seed', range(9))
def test_d05_d03_realized_windows_identical(data, seed):
    a, manifest, cases = data
    for method in ('LC01', 'EXT05C'):
        outputs = []
        for kind in ('D03', 'D05'):
            spec = cases[f'{kind}_seed_{seed:02d}']
            output, _, _ = transform(a, manifest, spec, method, read_spec_inputs(spec, ROOTS))
            outputs.append(output)
        assert all(np.array_equal(outputs[0][k], outputs[1][k]) for k in a)


@pytest.mark.parametrize('duration', (10, 20))
@pytest.mark.parametrize('seed', range(9))
def test_lc01_a2_and_a1_windows_identical(data, duration, seed):
    _, _, cases = data
    key = f'D62_{duration}s_seed_{seed:02d}'
    a2 = json.loads(read_spec_inputs(cases[key], ROOTS)['bundle'].read_text())
    a1 = json.loads((STAGES / 'CLEAN6_SENSOR_MODEL_V21/02_CASE_PROVIDERS' /
                    key.replace('D62_', 'D61_') / 'PROVIDER_BUNDLE.json').read_text())
    def interval(bundle):
        return next(c['details']['interval'] for c in bundle['components'] if c['affected_source'] == 'gnss_position')
    assert interval(a1) == interval(a2)
