"""Synthetic D4 verification only; no real-data output or execution."""
import json
import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext.t5a_diagnostics import GRAVITY_MPS2, diagnose


def motion(times=None, *, rate_deg_s=0., accel_x=0., roll=0., pitch=0.):
    t = np.arange(0, 3.01, .01) if times is None else np.asarray(times)
    dt = np.r_[.01, np.diff(t)]
    imu = np.zeros((len(t), 7)); imu[:, 0] = t
    # Body rate for constant Euler yaw rate at fixed roll/pitch.
    rate = np.deg2rad(rate_deg_s)
    imu[:, 1:4] = dt[:, None] * np.array([-np.sin(pitch), np.cos(pitch)*np.sin(roll), np.cos(pitch)*np.cos(roll)]) * rate
    gravity = GRAVITY_MPS2*np.array([-np.sin(pitch), np.cos(pitch)*np.sin(roll), np.cos(pitch)*np.cos(roll)])
    imu[:, 4:7] = dt[:, None] * (-gravity + [accel_x, 0., 0.])
    rp = np.column_stack((t, np.full(len(t), roll-np.deg2rad(1.)), np.full(len(t), pitch)))
    return imu, rp


def rows(times=(.25, 1.25, 2.25), *, rate=0., delta=2., qualities=None):
    qualities = qualities or [2]*len(times)
    return [dict(time_s=t, itow_ms=round(t*1000), a1_valid=1,
                 yaw_raw_unrounded_deg=(t*rate)%360, yaw_a1_deg=(t*rate-delta)%360,
                 delta_raw_minus_a1_deg=delta, receiver1_carrSoln=2, receiver2_carrSoln=q)
            for t,q in zip(times,qualities)]


def result_row(result, **selector):
    found = [r for r in result['source_consistency_rows'] if all(r.get(k)==v for k,v in selector.items())]
    assert len(found)==1
    return found[0]


def test_installed_gravity_vector_and_acceleration_bins_without_double_transform():
    roll,pitch=.3,-.2
    for acceleration, label in ((0.,'lt_0p3'),(.5,'from_0p3_to_1'),(1.5,'gt_1')):
        imu,rp=motion(accel_x=acceleration,roll=roll,pitch=pitch)
        r=diagnose('BY2',(0,3),rows(),imu,rp,[],[])
        assert all(e['acceleration_mps2']==pytest.approx(acceleration,abs=1e-12) for e in r['per_epoch'])
        assert {e['acceleration_bin'] for e in r['per_epoch']}=={label}
    imu,rp=motion()
    r=diagnose('BY2',(0,3),rows(times=(-.1,.25,3.1)),imu,rp,[],[])
    assert [e['acceleration_bin'] for e in r['per_epoch']]==['unavailable','lt_0p3','unavailable']


def test_p12_projection_preserves_frozen_bias_and_reports_sigma_only():
    imu,rp=motion(rate_deg_s=10.,roll=.3,pitch=-.2)
    r=diagnose('BY2',(0,3),rows(rate=10.),imu,rp,[],[])
    pairs=r['sigma_pairs']
    assert len(pairs)==2
    assert all(p['euler_yaw_rate_residual_deg']==pytest.approx(0.,abs=1e-11) for p in pairs)
    assert all(abs(p['installed_z_residual_deg'])>.1 for p in pairs)
    summary=result_row(r,category='sigma',scope='evaluation_window',quality='all',projection='euler_yaw_rate')
    assert summary['effective_sigma_deg']==pytest.approx(0.,abs=1e-11)
    assert summary['report_only'] is True
    assert {p['start_quality'] for p in pairs}=={'both_fixed'}
    json.dumps(r,allow_nan=False)
    assert np.max(imu[:,3])>0  # caller arrays were not changed/debiased


def test_gap_rejects_whole_pair_and_does_not_synthesize_zero_residual():
    imu,rp=motion(times=np.r_[np.arange(0,.91,.01),np.arange(1.2,3.01,.01)],rate_deg_s=3.)
    r=diagnose('BY2',(0,3),rows(rate=3.),imu,rp,[],[])
    assert r['sigma_pairs'][0]['imu_supported'] is False
    assert r['sigma_pairs'][0]['installed_z_residual_deg'] is None
    assert r['sigma_pairs'][1]['imu_supported'] is True
    summary=result_row(r,category='sigma',scope='evaluation_window',quality='all',projection='installed_z')
    assert summary['candidate_pair_count']==2 and summary['unsupported_pair_count']==1
    assert summary['effective_sigma_deg'] is None


def test_float_epochs_retained_and_closed_regions_exactly_partition():
    times=(3369.94,3411.95,3412.,3495.,3495.94,3508.94,3509.)
    imu,rp=motion(times=np.arange(3369.,3510.,.02))
    r=diagnose('BY2O',(3186,3563),rows(times,qualities=[1]*7),imu,rp,[],[])
    inside=result_row(r,category='delta',scope='inside_union',quality='float_involved',acceleration_bin='all')
    outside=result_row(r,category='delta',scope='outside',quality='float_involved',acceleration_bin='all')
    assert inside['count']==4 and outside['count']==3
    assert inside['mean_deg']==2 and inside['std_population_deg']==0
    hist=[x for x in r['histograms'] if x['scope']=='evaluation_window' and x['quality']=='float_involved']
    assert sum(x['count'] for x in hist)==7
    fixed=result_row(r,category='delta',scope='evaluation_window',quality='both_fixed',acceleration_bin='all')
    assert fixed['count']==0 and fixed['mean_deg'] is None


def status(tow,header,system):
    return dict(time_gps_tow=tow,time_gps_wno=2408,Time=header,
                **{'sys_stamp.secs':system,'sys_stamp.nsecs':0},
                rel_pos_n=1.,rel_pos_e=0.,rel_pos_d=0.,rel_acc_n=.01,rel_acc_e=.01,rel_acc_d=.01,
                rel_valid=True,ant_valid=True,ant_state=2)


def test_status_header_interpolation_is_not_replaced_by_zero_gps_time_difference():
    imu,rp=motion()
    d=rows(times=(1.,))
    first=[status(1.,101.,201.)]
    second=[status(0.,100.2,200.2),status(1.,101.2,201.2),status(2.,102.2,202.2)]
    r=diagnose('BY2',(0,3),d,imu,rp,first,second)
    row=r['timing_rows'][0]
    assert row['gps_delta_s']==0.
    assert row['header_delta_s']==pytest.approx(.2)
    assert row['sys_delta_s']==pytest.approx(.2)
    assert row['interpolation_left_offset_s']==pytest.approx(-.8)
    assert row['interpolation_right_offset_s']==pytest.approx(.2)
    assert row['interpolation_weight']==pytest.approx(.8)
    assert row['nearest_header_offset_s']==pytest.approx(.2)
    summary=result_row(r,category='timing',scope='evaluation_window',quality='all',timing_field='header_delta_s')
    assert summary['mean_s']==pytest.approx(.2) and summary['unmatched_count']==0


def test_input_invalidity_fails_without_epoch_deletion():
    imu,rp=motion();imu[4,3]=np.nan
    with pytest.raises(ValueError,match='finite'):diagnose('BY2',(0,3),rows(),imu,rp,[],[])


def test_missing_raw_or_pvt_preserves_epochs_and_counts_unavailable_without_zero_fill():
    imu,rp=motion()
    data=rows()
    data[1].update(receiver2_carrSoln=None,yaw_raw_unrounded_deg=None,delta_raw_minus_a1_deg=None)
    # A non-E intermediate raw/PVT gap also invalidates a sigma interval.
    intermediate=rows(times=(.75,))[0]
    intermediate.update(a1_valid=0,receiver1_carrSoln=None,yaw_raw_unrounded_deg=None)
    r=diagnose('BY2',(0,3),data+[intermediate],imu,rp,[],[])
    assert len(r['per_epoch'])==3
    missing=r['per_epoch'][1]
    assert missing['raw_fixed_float_label']=='unknown'
    assert missing['source_delta_status']=='UNAVAILABLE_RAW_OR_A1_HEADING'
    assert missing['delta_raw_minus_a1_deg'] is None
    summary=result_row(r,category='delta',scope='evaluation_window',quality='all',acceleration_bin='all')
    assert (summary['total_count'],summary['available_count'],summary['unavailable_count'])==(3,2,1)
    assert summary['mean_deg']==2. and summary['status']=='AVAILABLE_PARTIAL_SUPPORT'
    assert all(p['installed_z_residual_deg'] is None for p in r['sigma_pairs'])
    assert all(p['source_supported'] is False for p in r['sigma_pairs'])
    assert r['sigma_pairs'][0]['missing_raw_interval_count']==2
    assert r['sigma_pairs'][0]['unknown_pvt_interval_count']==2
    unknown=result_row(r,category='delta',scope='evaluation_window',quality='unknown',acceleration_bin='all')
    assert unknown['count']==0 and unknown['total_count']==1 and unknown['mean_deg'] is None
    hist=[h for h in r['histograms'] if h['scope']=='evaluation_window' and h['quality']=='all']
    assert sum(h['count'] for h in hist)==2
    assert all(h['unavailable_count']==1 for h in hist)
    json.dumps(r,allow_nan=False)


def test_missing_pvt_alone_is_unknown_while_available_source_difference_is_retained():
    imu,rp=motion();data=rows();data[0]['receiver1_carrSoln']=None
    r=diagnose('BY2',(0,3),data,imu,rp,[],[])
    unknown=result_row(r,category='delta',scope='evaluation_window',quality='unknown',acceleration_bin='all')
    assert unknown['count']==1 and unknown['mean_deg']==2
    assert r['sigma_pairs'][0]['source_supported'] is False
    assert r['sigma_pairs'][1]['source_supported'] is True


def test_nearest_header_pair_with_offset_gps_identity_is_separate_from_same_itow():
    imu,rp=motion()
    first=[status(1.,101.,201.)]
    second=[status(.025,100.05,200.15),status(1.025,101.05,201.15),status(2.025,102.05,202.15)]
    r=diagnose('BY2',(0,3),rows(times=(1.,)),imu,rp,first,second)
    row=r['timing_rows'][0]
    assert row['status']=='UNAVAILABLE_STATUS_ITOW_MATCH'
    assert row['gnss2_same_itow_count']==0
    assert row['header_delta_s'] is row['sys_delta_s'] is row['gps_delta_s'] is None
    assert row['nearest_header_pair_status']=='AVAILABLE'
    assert row['nearest_header_pair_week_status']=='VERIFIED_2408'
    assert row['nearest_header_pair_gnss2_week']==2408
    assert row['nearest_header_pair_gnss2_itow_ms']==1025
    assert row['nearest_header_pair_header_delta_s']==pytest.approx(.05)
    assert row['nearest_header_pair_sys_delta_s']==pytest.approx(.15)
    assert row['nearest_header_pair_gps_delta_s']==pytest.approx(.025,abs=1e-6)
    assert row['nearest_header_pair_target_bracketed'] is True
    assert row['fitted_offset_used'] is False
    original=result_row(r,category='timing',scope='evaluation_window',quality='all',timing_field='header_delta_s')
    assert original['pairing']=='EXACT_ITOW' and original['count']==0 and original['mean_s'] is None
    new=result_row(r,category='timing',scope='evaluation_window',quality='all',timing_field='nearest_header_pair_header_delta_s')
    assert new['pairing']=='NEAREST_HEADER_NO_FITTED_OFFSET' and new['count']==1
    assert new['mean_s']==pytest.approx(.05) and new['fitted_offset_used'] is False
    assert row['interpolation_left_offset_s']==pytest.approx(-.95)
    assert row['interpolation_right_offset_s']==pytest.approx(.05)
    assert row['interpolation_weight']==pytest.approx(.95)
    json.dumps(r,allow_nan=False)


def test_nearest_header_never_pairs_known_wrong_week_and_missing_week_is_explicit():
    imu,rp=motion()
    first=[status(1.,101.,201.)]
    wrong=status(1.,101.001,201.001);wrong['time_gps_wno']=2409
    current=status(1.025,101.3,201.4)
    r=diagnose('BY2',(0,3),rows(times=(1.,)),imu,rp,first,[wrong,current])
    row=r['timing_rows'][0]
    assert row['gnss2_same_itow_count']==0 and row['gnss2_same_itow_rejected_week_count']==1
    assert row['gnss2_header_candidates_rejected_week_count']==1
    assert row['nearest_header_pair_gnss2_week']==2408
    assert row['nearest_header_pair_gnss2_itow_ms']==1025
    assert row['nearest_header_pair_header_delta_s']==pytest.approx(.3)
    assert row['nearest_header_pair_target_bracketed'] is False
    first[0]['time_gps_wno']=2409
    bad=diagnose('BY2',(0,3),rows(times=(1.,)),imu,rp,first,[current])['timing_rows'][0]
    assert bad['gnss1_same_itow_rejected_week_count']==1
    assert bad['nearest_header_pair_header_delta_s'] is None
    first[0]['time_gps_wno']=2408
    current.pop('time_gps_wno')
    missing=diagnose('BY2',(0,3),rows(times=(1.,)),imu,rp,first,[current])['timing_rows'][0]
    assert missing['nearest_header_pair_week_status']=='UNAVAILABLE_WEEK_IDENTITY'
    assert missing['nearest_header_pair_header_delta_s']==pytest.approx(.3)
    assert missing['nearest_header_pair_gps_delta_s'] is None


def test_nearest_header_equal_distance_uses_earlier_actual_header_without_fitting():
    imu,rp=motion()
    first=[status(1.,101.,201.)]
    second=[status(1.1,101.25,201.25),status(.9,100.75,200.75)]
    row=diagnose('BY2',(0,3),rows(times=(1.,)),imu,rp,first,second)['timing_rows'][0]
    assert row['nearest_header_pair_tie_count']==2
    assert row['nearest_header_pair_gnss2_itow_ms']==900
    assert row['nearest_header_pair_header_delta_s']==-.25
    assert row['nearest_header_pair_sys_delta_s']==-.25
    assert row['nearest_header_pair_gps_delta_s']==pytest.approx(-.1,abs=1e-6)
    assert row['fitted_offset_used'] is False


def test_by2o_378_a1_epochs_keep_all_58_float_epochs_and_explicit_42_13_3_overlap_counts():
    # Synthetic 1 Hz E reproduces the declared interval arithmetic; no files or
    # real provider evidence are used. IMU/RP unsupported here is independent.
    times=tuple(range(3186,3564))
    float_times=set(range(3370,3413))|set(range(3495,3510))
    data=rows(times,qualities=[1 if time in float_times else 2 for time in times])
    imu,rp=motion(times=[3185.,3564.])
    r=diagnose('BY2O',(3186,3563),data,imu,rp,[],[])
    assert len(r['per_epoch'])==378
    assert sum(row['raw_fixed_float_label']=='float_involved' for row in r['per_epoch'])==58
    overlaps={row['scope']:row for row in r['source_consistency_rows'] if row['category']=='float_epoch_overlap'}
    assert {scope:row['count'] for scope,row in overlaps.items()}=={
        'evaluation_window':58,'occlusion_primary':42,'occlusion_secondary':13,'inside_union':55,'outside':3}
    assert all(row['observed_equals_preregistered_expected'] for row in overlaps.values())
    assert all(row['report_only'] and row['decision_rule']=='NONE' for row in overlaps.values())
    assert overlaps['evaluation_window']['total_a1_epochs']==378
    floats=result_row(r,category='delta',scope='evaluation_window',quality='float_involved',acceleration_bin='all')
    assert floats['count']==58 and floats['mean_deg']==2.
    json.dumps(r,allow_nan=False)
