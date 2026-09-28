"""Synthetic integration, circular-angle and support tests; no scientific I/O."""
import math

import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext.t5bc_calibration import (scalar_pair_calibration,
    vector_pair_calibration, calibration_bin_report)


def fixture():
    times = np.arange(151) * .02
    rate = math.radians(450.)
    imu = np.zeros((len(times), 7))
    imu[:, 0] = times
    imu[1:, 3] = .02 * rate / math.cos(math.radians(1.))
    rp = np.column_stack((times, np.zeros((len(times), 2))))
    rawtimes = np.arange(16)*.2
    noise = .2*np.sin(np.arange(16))
    keys = [i*200 for i in range(16)]
    raw = [dict(itow_ms=key, aligned_time=float(t), yaw_ned_deg=float((170.+450*t+n)%360))
           for key, t, n in zip(keys, rawtimes, noise)]
    return dict(raw_yaw_rows=raw, pacc1_m={key: .002+key*1e-6 for key in keys},
                pacc2_m=dict.fromkeys(keys, .004), pvt_flags1=dict.fromkeys(keys, 128),
                pvt_flags2=dict.fromkeys(keys, 128), baseline_m=.35,
                imu=imu, rp=rp, window=(0., 3.),
                nominal_variance_policy='PAIR_ENDPOINTS_WITH_MULTIPLICITY'), noise


def test_fast_rotation_unwrap_gyro_projection_and_pair_weighted_denominator():
    data, noise = fixture()
    result = scalar_pair_calibration(**data)
    report = result['reports'][0]
    expected = np.deg2rad(noise[5:] - noise[:-5])
    assert report['supported_pair_count'] == 11
    assert report['euler']['residual_variance_rad2'] == pytest.approx(np.var(expected, ddof=1), rel=1e-10)
    assert report['euler']['sigma_deg'] == pytest.approx(np.std(noise[5:]-noise[:-5], ddof=1)/math.sqrt(2), rel=1e-10)
    q = [(data['pacc1_m'][i*200]**2+.004**2)/.35**2 for i in range(16)]
    denominator = sum(q[i]+q[i+5] for i in range(11))/11
    assert report['twice_mean_nominal_variance_rad2'] == pytest.approx(denominator)
    assert report['euler']['k_squared'] == pytest.approx(np.var(expected, ddof=1)/denominator, rel=1e-10)
    assert result['reports'][1]['supported_pair_count'] == 15
    assert result['pairs'][0]['delta_yaw_rad'] > 2*math.pi  # No endpoint wrap or residual wrap.


def test_float_interval_is_not_bridged_at_either_lag():
    data, _ = fixture()
    data['pvt_flags2'][1200] = 64
    result = scalar_pair_calibration(**data)
    assert [r['supported_pair_count'] for r in result['reports']] == [5, 13]
    assert [r['unsupported_reasons']['INTERVAL_NOT_BOTH_FIXED'] for r in result['reports']] == [6, 2]


def test_missing_raw_epoch_never_interpolated_or_hidden():
    data, _ = fixture()
    data['raw_yaw_rows'] = [row for row in data['raw_yaw_rows'] if row['itow_ms'] != 1200]
    result = scalar_pair_calibration(**data)
    assert result['reports'][0]['supported_pair_count'] == 5
    assert result['reports'][0]['unsupported_reasons']['MISSING_EXACT_200MS_RAW_EPOCH'] == 5


def test_exact_time_identity_and_explicit_denominator_are_required():
    data, _ = fixture()
    with pytest.raises(ValueError, match='explicit supported'):
        scalar_pair_calibration(**{**data, 'nominal_variance_policy': None})
    data['raw_yaw_rows'][6]['aligned_time'] += .001
    with pytest.raises(ValueError, match='timestamps disagree'):
        scalar_pair_calibration(**data)


def test_excluded_euler_singularity_cannot_pollute_later_supported_pairs():
    data, noise = fixture()
    data['rp'][20:31, 2] = math.pi / 2
    result = scalar_pair_calibration(**data)
    pairs = [row for row in result['pairs'] if row['status'] == 'SUPPORTED']
    later = [row for row in pairs if row['first_time_s'] >= .8]
    assert later
    assert result['reports'][0]['supported_pair_count'] == 11
    assert any(row.get('euler_status') == 'UNAVAILABLE_IMU_RP_INTERVAL' for row in pairs)
    assert result['reports'][0]['primary_method'] == 'INSTALLED_GYRO_Z'
    for row in later:
        first, second = row['first_itow_ms']//200, row['second_itow_ms']//200
        expected = math.radians(noise[second]-noise[first])
        assert row['euler_residual_rad'] == pytest.approx(expected, abs=1e-12)


def vector_fixture(rate=.3, offset=.03):
    times = np.arange(162)*.02
    imu = np.zeros((len(times), 7)); imu[:, 0] = times
    imu[1:, 3] = rate*.02
    rp = np.column_stack((times, np.full(len(times), -math.radians(1)), np.zeros(len(times))))
    keys = [int(round(offset*1000))+i*200 for i in range(16)]
    raw = [dict(itow_ms=k, aligned_time=k*.001, yaw_ned_deg=math.degrees(rate*k*.001),
        rel_n=.35*math.sin(rate*k*.001), rel_e=-.35*math.cos(rate*k*.001), rel_d=0.) for k in keys]
    return dict(raw_yaw_rows=raw, pacc1_m={k:.002+i*.0001 for i,k in enumerate(keys)},
        pacc2_m=dict.fromkeys(keys,.003), pvt_flags1=dict.fromkeys(keys,128),
        pvt_flags2=dict.fromkeys(keys,128), baseline_m=.35, imu=imu, rp=rp,
        window=(offset,offset+3))


@pytest.mark.parametrize('rate', [0., .3])
def test_vector_stationary_rotation_installation_and_partial_interval(rate):
    data = vector_fixture(rate)
    result = vector_pair_calibration(**data)
    assert [r['supported_pair_count'] for r in result['reports']] == [11,15]
    for row in result['pairs']:
        assert row['residual_ned_m'] == pytest.approx([0.,0.,0.],abs=1e-15)
        assert row['installed_body_gyro_increment_rad'] == pytest.approx([0.,0.,rate*row['lag_ms']*.001],abs=1e-15)
    assert result['reports'][0]['k_b'] == pytest.approx(0.,abs=1e-12)


def test_exact_vector_factor_six_and_scalar_z_primary_formula():
    data = vector_fixture(0.)
    for i,row in enumerate(data['raw_yaw_rows']):
        row['rel_n'] += .01*math.sin(i)
        row['rel_e'] += .02*math.cos(i)
        row['yaw_ned_deg'] += .3*math.sin(i)
    vector = vector_pair_calibration(**data)
    pairs = [r for r in vector['pairs'] if r['lag_ms']==1000 and r['status']=='SUPPORTED']
    residual = np.array([r['residual_ned_m'] for r in pairs])
    mean_s = np.mean([r['S_first_m2']+r['S_second_m2'] for r in pairs])
    assert vector['reports'][0]['k_b_squared'] == pytest.approx(np.trace(np.cov(residual,rowvar=False,ddof=1))/(6*mean_s))
    data['rp'][:,2] = .4
    data['rp'][:,1] = .3
    data['imu'][1:,2] = .01*np.sin(np.arange(len(data['imu'])-1))
    scalar = scalar_pair_calibration(**data)
    pairs = [r for r in scalar['pairs'] if r['lag_ms']==1000 and r['status']=='SUPPORTED']
    expected = np.var([r['delta_yaw_rad']-r['z_gyro_integral_rad'] for r in pairs],ddof=1)
    assert scalar['reports'][0]['z']['k_squared'] == pytest.approx(expected*.35**2/mean_s)
    assert scalar['reports'][0]['z']['sigma_rad'] == pytest.approx(math.sqrt(expected/2))
    assert scalar['reports'][0]['z']['residual_variance_rad2'] != pytest.approx(scalar['reports'][0]['euler']['residual_variance_rad2'],rel=1e-5)


def test_bins_are_fixed_by_by2_pair_mean_s_and_keep_empty_bins():
    data=vector_fixture()
    scalar={s:scalar_pair_calibration(**data) for s in ('BY2','BY2H','BY2O')}
    vector={s:vector_pair_calibration(**data) for s in scalar}
    for row in scalar['BY2H']['pairs']:
        row['pair_mean_S_m2'] *= 100
    result=calibration_bin_report(scalar,vector)
    expected=np.quantile([r['pair_mean_S_m2'] for r in scalar['BY2']['pairs'] if r['lag_ms']==1000],[1/3,2/3])
    assert result['edges_m2'] == pytest.approx(expected)
    assert len(result['rows']) == 18
    empty=[r for r in result['rows'] if r['sequence_id']=='BY2H' and r['family']=='scalar' and r['bin_id']=='S1'][0]
    assert empty['pair_count']==0 and empty['status']=='UNAVAILABLE_INSUFFICIENT_PAIRS'
    assert empty['mean_S_bin_m2'] is None and empty['predicted_heading_sigma_deg'] is None


def test_bins_predict_with_fixed_by2_one_second_scales_not_refitted_bin_scales():
    data=vector_fixture(0.)
    for i,row in enumerate(data['raw_yaw_rows']):
        row['yaw_ned_deg'] = .3*math.sin(i)
        row['rel_n'] += .02*math.cos(i)
    scalar={s:scalar_pair_calibration(**data) for s in ('BY2','BY2H','BY2O')}
    vector={s:vector_pair_calibration(**data) for s in scalar}
    k=scalar['BY2']['reports'][0]['z']['k'];kb=vector['BY2']['reports'][0]['k_b']
    for lag in (1000,200):
        result=calibration_bin_report(scalar,vector,lag_ms=lag)
        for row in result['rows']:
            assert row['applied_k']==k and row['applied_k_b']==kb and row['applied_lag_ms']==1000
            assert row['mean_S_bin_m2']==pytest.approx(np.mean(row['pair_mean_S_m2']))
            root_s=math.sqrt(row['mean_S_bin_m2'])
            assert row['predicted_heading_sigma_deg']==pytest.approx(math.degrees(k*root_s/.35))
            assert row['predicted_vector_component_sigma_m']==pytest.approx(kb*root_s)
            if row['family']=='vector':
                assert row['empirical_vector_component_sigma_m']==pytest.approx(math.sqrt(row['sample_covariance_trace_m2']/6))
            else:
                assert row['empirical_heading_sigma_deg']==row['sigma_deg']
