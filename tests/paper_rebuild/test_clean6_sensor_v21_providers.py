"""Scientific frame, dependency, token, and immutable-resume regression checks."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21 import providers as p
from legsa_gins.paper_rebuild.canonical541 import provider_generator as canonical
from test_clean5_degradation_providers import inputs, case


def table(times):
    rows = [{'time': repr(float(t)), 'vn': '7.0', 've': '8.0', 'vd': '0.0',
             'std_vn': '1.5', 'std_ve': '1.5', 'std_vd': '999', 'update_flag': 'True',
             'source_status': 'active', 'reason_codes': '', 'frame_candidate': '', 'prior_policy': ''} for t in times]
    return canonical.ProviderTable(tuple(rows[0]), rows)


def body(times):
    return np.column_stack((times, np.zeros((len(times), 2)), np.tile([1., 0., 0.], (len(times), 1))))


def yaw(times, degrees):
    return [{'time': repr(float(t)), 'yaw_deg': repr(float(y)), 'valid': '1'} for t, y in zip(times, degrees)]


def test_a1_wrap_safe_gap_endpoints_no_extrapolation_and_empty():
    times = np.array([-.1, 0, .5, 1, 1.1, 2, 3, 3.1])
    angle, valid = p.interpolate_a1(times, [0, 1, 3], [179, -179, -170])
    assert valid.tolist() == [False, True, True, True, False, False, True, False]
    assert abs(np.rad2deg(angle[2])-180) < 1e-12
    angle, valid = p.interpolate_a1(times, [], [])
    assert angle is None and not valid.any()


def test_flu_frd_rotation_scale_and_noise_with_independent_matrix():
    v = np.array([[2., 3., 4.]])
    r, q, z = .3, -.2, 1.1
    rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
    ry = np.array([[np.cos(-q), 0, np.sin(-q)], [0, 1, 0], [-np.sin(-q), 0, np.cos(-q)]])
    rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    expected = (rz @ ry @ rx @ np.diag([1, -1, -1]) @ v[0])[:2]
    assert np.allclose(p.rotate_flu_to_ned(v, np.array([r]), np.array([q]), np.array([z]))[0], expected, atol=1e-14)
    b = np.array([[0., r, q, *v[0]]])
    result = p.correct_hv(table([0]), b, yaw([0], [np.rad2deg(z)]))
    assert np.allclose([float(result.rows[0][a]) for a in ('vn', 've')], expected*p.K_HV)
    assert result.rows[0]['std_vn'] == result.rows[0]['std_ve'] == '0.132838'


def test_a1_outage_invalidates_hv_without_zero_payload_or_reenabling_raw_invalid():
    times = np.arange(7)/2
    original = table(times)
    original.rows[0]['update_flag'] = 'False'
    result = p.correct_hv(original, body(times), yaw([0, 1, 3], [0, 90, 90]))
    assert [p.old._valid(r) for r in result.rows] == [False, True, True, False, False, False, True]
    assert float(result.rows[1]['ve']) > .7
    absent = p.correct_hv(result, body(times), [])
    assert not any(p.old._valid(r) for r in absent.rows)
    assert [(r['vn'], r['ve']) for r in absent.rows] == [(r['vn'], r['ve']) for r in result.rows]
    assert original.rows[1]['vn'] == '7.0'


def test_d57_reordered_rows_use_original_body_identity_and_shifted_a1():
    times = np.array([0., 1., 2.])
    b = body(times)
    b[:, 3] = [1, 2, 3]
    h = table([.2, .4, .6])
    for row, index in zip(h.rows, [2, 0, 1]):
        row[canonical.D57_ORIGINAL_ROW_ID] = str(index)
    result = p.correct_hv(h, b, yaw([.2, .6], [0, 90]), timing_fault=True)
    assert np.allclose([[float(r['vn']), float(r['ve'])] for r in result.rows],
                       p.K_HV*np.array([[3, 0], [2**-.5, 2**-.5], [0, 2]]))
    assert [r[canonical.D57_ORIGINAL_ROW_ID] for r in result.rows] == ['2', '0', '1']


def test_rp_sign_and_std_preserve_raw_and_reject_wrong_source_identity():
    std = repr(float(np.deg2rad(1.6)))
    rows = [{'time': '1', 'roll_rad': '.2', 'pitch_rad': '.3', 'std_roll_rad': std, 'std_pitch_rad': std}]
    rp = canonical.ProviderTable(tuple(rows[0]), rows)
    raw = np.array([[1., .2, .3]])
    result = p.correct_rp(rp, raw)
    assert result.rows[0]['roll_rad'] == '.2' and result.rows[0]['pitch_rad'] == '-0.3'
    assert result.rows[0]['std_roll_rad'] == std and rp.rows[0]['pitch_rad'] == '.3'
    with pytest.raises(ValueError, match='source frame'):
        p.correct_rp(rp, np.array([[1., .2, .4]]))


@pytest.mark.parametrize('columns', [15, 18])
def test_gnss_token_gate_all_rows_even_invalid_and_preserves_injected_std_multiplier(columns):
    old = [[str(k) for k in range(columns)] for _ in range(3)]
    new = p.yaw_std_tokens(old)
    p.compare_gnss_tokens(old, new, nominal=True)
    for row in new:
        row[14] = str(float(row[14])*3)
    p.compare_gnss_tokens(old, new)
    with pytest.raises(ValueError, match='Nominal yaw'):
        p.compare_gnss_tokens(old, new, nominal=True)
    new[1][3] = 'different'
    with pytest.raises(ValueError, match='non-yaw-std'):
        p.compare_gnss_tokens(old, new)


def test_residual_gate_reports_deltas_and_stops_nonfinite_or_numerical_failure():
    expected = {'n': 2, 'mean': .123456, 'bin': {'status': 'UNAVAILABLE_EMPTY_BIN'}}
    actual = copy.deepcopy(expected)
    actual['mean'] += 1e-8
    assert max(d['absolute_difference'] for d in p._compare(expected, actual)) < 1e-6
    actual['mean'] += 2e-6
    with pytest.raises(p.ReproductionGateFailure):
        p._compare(expected, actual)
    actual['mean'] = float('nan')
    with pytest.raises(p.ReproductionGateFailure):
        p._compare(expected, actual)


def test_exclusive_seal_resume_detects_mutation_and_never_overwrites(tmp_path):
    root = tmp_path/'case'
    root.mkdir()
    pin = p._write(root/'synthetic.csv', b'time,valid\n1,1\n')
    result = {'code_commit': 'a'*40, 'config_hash': 'b'*64, 'providers': {'test': pin}}
    p._seal(root, result)
    assert p._resume(root, 'b'*64, 'a'*40) == result
    with pytest.raises(FileExistsError):
        p._write(root/'synthetic.csv', b'changed')
    (root/'synthetic.csv').write_bytes(b'changed')
    with pytest.raises(ValueError, match='seal mismatch'):
        p._resume(root, 'b'*64, 'a'*40)


@pytest.mark.parametrize('tid,factor', [('D36', 1.5), ('D37', 3), ('D38', .25)])
def test_yaw_std_injections_retain_multiplier_on_new_nominal(inputs, tid, factor):
    base = inputs[0]
    for row in base.bundle.tables['dual_yaw'].rows:
        row['yaw_std_deg'] = str(p.SIGMA_YAW)
    result, _, _ = p._inject(base, case(tid), {})
    assert all(abs(float(r['yaw_std_deg'])-p.SIGMA_YAW*factor) < 1e-9 for r in result.tables['dual_yaw'].rows)


@pytest.mark.parametrize('tid', ['D61', 'D62'])
def test_all_gnss_outage_rebuilds_hv_only_when_a1_removed(inputs, tid):
    base = inputs[0]
    h = base.bundle.tables['go2_hv']
    times = np.array([float(r['time']) for r in h.rows])
    base.bundle.tables['go2_hv'] = p.correct_hv(h, body(times), base.bundle.tables['dual_yaw'].rows)
    c = dict(case(tid), duration_s=20)
    generated, _, _ = p._inject(base, c, {})
    generated.tables['go2_hv'] = p.correct_hv(generated.tables['go2_hv'], body(times), generated.tables['dual_yaw'].rows)
    middle = (times > 81)&(times < 99)
    assert all(p.old._valid(r) == (tid == 'D62') for r, selected in zip(generated.tables['go2_hv'].rows, middle) if selected)
    for source in ('gnss_position', 'receiver_velocity', 'raw_doppler'):
        assert all(not p.old._valid(r) for r in generated.tables[source].rows if 80 <= float(r['time']) < 100)


@pytest.mark.parametrize('seed', [0, 4, 8])
def test_direct_hv_scale_dropout_uses_new_base_and_original_seed_branches(inputs, seed):
    base = inputs[0]
    h = base.bundle.tables['go2_hv']
    times = np.array([float(r['time']) for r in h.rows])
    base.bundle.tables['go2_hv'] = p.correct_hv(h, body(times), base.bundle.tables['dual_yaw'].rows)
    c = dict(case('D54'), seed_index=f'seed_{seed:02d}')
    generated, _, _ = p._inject(base, c, {})
    expected, _, _ = canonical.apply_degradation(base.bundle, c)
    assert generated.tables['go2_hv'].canonical_bytes() == expected.tables['go2_hv'].canonical_bytes()
    scale = 1.5 if seed in (0, 8) else 1.
    for left, right in zip(base.bundle.tables['go2_hv'].rows, generated.tables['go2_hv'].rows):
        assert abs(float(right['vn'])-float(left['vn'])*scale) <= 5.1e-10
        assert right['std_vn'] == '0.132838'
        assert not p.old._valid(right) or p.old._valid(left)
