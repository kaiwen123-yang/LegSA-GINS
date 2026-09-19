"""Synthetic unit tests only; no real audit output or numerical evidence."""
import math
import pytest
from legsa_gins.paper_rebuild.clean5_imu_parity.input_audit import (
    gravity_model,dt_audit,sliding_windows,scale_from_frames,noise_audit,temperature_audit)


def frames(times):
    return [{'timestamp_ns':round(t*1e9),'time':t,'norm_mps2':9+t*.001,
             'imu_state.temperature':20.,'gyro_norm_radps':0.} for t in times]


def test_gravity_equator_and_pinned_latitude():
    g=gravity_model([0,0,0]);assert g['g_local_mps2']==9.7803253359
    low=gravity_model([39.98482973,116.34312609,41.80208107])
    assert 9.801<low['g_local_mps2']<9.802
    assert low['g_local_mps2']<low['g_ellipsoid_surface_mps2']
    assert low['height_definition'].startswith('ellipsoidal')


def test_jitter_is_centered_time_proxy_and_keeps_zero_dt():
    data=frames([0,.01,.02,.033,.033])
    a=dt_audit(data,10.)
    assert a['median_dt_seconds']==pytest.approx(.01)
    assert a['nonpositive_dt_count']==1
    assert a['absolute_deviation_gt_1ms_fraction']==.5
    assert a['equivalent_dv_signed_mps']['mean']==pytest.approx(10*((.01+.01+.013+0)/4-.01))
    assert 'not independent physical' in a['interpretation']


def test_window_schedule_reports_partial_and_missing_temperature():
    data=frames([i*.5 for i in range(25)])
    data[0]['imu_state.temperature']=None
    windows=sliding_windows(data)
    assert len(windows)==13
    assert sum(r['window_status']=='FULL' for r in windows)==3
    assert windows[0]['frame_count']==20
    assert windows[0]['temperature_unavailable_n']==1
    assert windows[-1]['window_status']=='PARTIAL_TERMINAL'
    assert temperature_audit(data)['correlation_status']=='UNAVAILABLE_CONSTANT_OR_MISSING'


def test_scale_is_mean_of_norms_and_first_1000_only():
    data=frames(range(1001))
    for i,r in enumerate(data):r['norm_mps2']=9. if i%2==0 else 11.
    data[-1]['norm_mps2']=1000000
    assert scale_from_frames(data,9.8)['s']==pytest.approx(.98)
    with pytest.raises(ValueError):scale_from_frames(data[:999],9.8)


def test_frozen_units_ou_and_unfiltered_integrals(tmp_path):
    p=tmp_path/'synthetic.yaml'
    p.write_text('arw: [0.985, 0.985, 0.985]\nvrw: [0.077, 0.077, 0.077]\ngbstd: [9.38, 9.38, 9.38]\nabstd: [77.8, 77.8, 77.8]\ngsstd: [0, 0, 0]\nasstd: [0, 0, 0]\ncorrtime: 1.0\n')
    a=noise_audit(p)
    assert a['corrtime_seconds']==3600
    assert a['ab_stationary_sigma_mps2']==pytest.approx(.000778)
    assert a['bias_0p3_over_ab_sigma']==pytest.approx(.3/.000778)
    assert a['theory_times'][-1]['free_delta_p_m']==pytest.approx(.15*274**2)
    assert a['theory_times'][-1]['OU_mean_decay']==pytest.approx(math.exp(-274/3600))


def test_existing_temperature_parser_matches_maintained_all_frames(tmp_path):
    from legsa_gins.paper_rebuild.clean5_imu_parity.input_audit import parse_with_temperature
    p=tmp_path/'synthetic_body.txt'
    p.write_text(''.join(f'stamp:\n  sec: {i//100}\n  nanosec: {(i%100)*10000000}\nimu_state:\n  quaternion: [1, 0, 0, 0]\n  rpy: [0, 0, 0]\n  gyroscope: [0, 0, 0]\n  accelerometer: [0, 0, 9.8]\n  temperature: 30\n---\n' for i in range(1000)))
    rows,audit=parse_with_temperature(p)
    assert audit['parser_identity_exact']
    assert len(rows)==1000
    assert rows[-1]['time']==pytest.approx(9.99)
    assert all(r['imu_state.temperature']==30 for r in rows)
