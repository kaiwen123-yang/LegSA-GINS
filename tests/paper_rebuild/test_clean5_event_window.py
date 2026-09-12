"""Synthetic event-window fixtures; no real provider or raw input reads."""
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean5_sequence import event_window as event


def make_input(dataset="BY2H", *, start=10.0, end=49.3):
    times = np.arange(0.0,50.01,0.1).round(8).tolist()
    dense = np.arange(0.0,50.001,0.01).round(8).tolist()
    return {"dataset_id":dataset,"gnss_times":list(range(50)),
            "gnss_speeds":[0.3 if t>=start else 0.0 for t in range(50)],
            "body_times":times,"body_speeds":[0.3 if t>=start else 0.0 for t in times],
            "common_coverage":{"first":1.0,"last":end},
            "kick_report":{"status":"NOT_DETECTED","kick_time_R1":None},
            "raw_body_times":dense,"imu_times":dense,
            "xcorr":{"status":"AVAILABLE","peak":{"lag_seconds":0.0,"coefficient":1.0}},
            "v1_window":{"t_start":11.0,"t_end":40.0}}


def shift_times(args,offset):
    for key in ("gnss_times","body_times","raw_body_times","imu_times"):
        args[key]=[float(value)+offset for value in args[key]]


def test_fixed_constants_and_human_statement():
    rules=event.constants()
    assert rules["speed_threshold_mps"]==0.15
    assert rules["gnss_consecutive_epochs"]==3
    assert rules["body_mean_window_seconds"]==1.0
    assert rules["body_persistence_seconds"]==3.0
    assert rules["max_onset_difference_seconds"]==1.0
    assert rules["onset_censoring"]["lookback_seconds"]==3.0
    assert rules["by2_control"]["required_start"]==66.0
    assert event.HUMAN_STATEMENT=="无 PTP 跨设备对时；启动时蹬一脚；算法起点 = 蹬脚后 GNSS 与机身 IMU 同时出现运动的时刻；结束 = 去掉末尾若干秒。"


def test_event_rule_and_not_detected_kick_is_report_only():
    result=event.compute_event_window(**make_input(),first_imu_hole_end=22.0)
    assert result["ready_for_v2_contract"]
    assert result["t_on_g"]==10.0
    assert 10.0<=result["t_on_b"]<=11.0
    assert result["v2_window"]=={"t_start":10.0,"t_end":40.0}
    assert result["first_imu_hole_end_comparison"]["candidate_start_at_or_after_hole_end"] is False
    assert result["first_imu_hole_end_comparison"]["used_to_select_window"] is False


def test_first_hole_end_comparison_includes_equal_boundary_report_only():
    result=event.compute_event_window(**make_input(),first_imu_hole_end=10.0)
    assert result["first_imu_hole_end_comparison"]["candidate_start_at_or_after_hole_end"] is True
    assert result["ready_for_v2_contract"]


def test_gnss_requires_three_consecutive_and_returns_first_epoch():
    result=event._gnss_onset([1,2,3,4,5,6],[0.15,0.2,0.14,0.15,0.15,0.15],0,10,None)
    assert result["onset"]==4
    assert result["confirmed_at"]==6
    assert result["provider_row_indices_zero_based"]==[3,4,5]


def test_gnss_coverage_and_strictly_post_kick():
    result=event._gnss_onset([1,2,3,4,5,6],[1]*6,2,6,3)
    assert result["onset"]==4
    assert event._gnss_onset([1,2,3],[1]*3,2,3,None)["onset"] is None


def test_body_mean_is_causal_full_support_and_open_left_boundary():
    means,counts=event.causal_body_means([0,.25,.5,.75,1,1.25],[100,0,0,0,4,100])
    assert means[:4]==[None]*4
    assert means[4]==1.0 and counts[4]==4
    assert means[5]==26.0


def test_body_persistence_requires_full_three_observed_seconds():
    times=[0,.5,1,1.5,2,2.5,3,3.5,4]
    result=event._body_onset(times,[0.3]*len(times),0,4,None)
    assert result["onset"]==1
    assert result["confirmed_at"]==4
    assert event._body_onset(times[:-1],[.3]*(len(times)-1),0,4,None)["onset"] is None


def test_body_hole_remains_diagnostic_and_not_new_event_gate():
    times=[0,.5,1,1.5,4]
    result=event._body_onset(times,[.3]*len(times),0,5,None)
    assert result["onset"]==1 and result["confirmed_at"]==4
    assert result["maximum_adjacent_interval_in_confirmation_seconds"]==2.5


def test_clock_offset_suspected_emits_report_without_v2_contract():
    args=make_input()
    args["body_speeds"]=[.3 if t>=15 else 0.0 for t in args["body_times"]]
    result=event.compute_event_window(**args)
    assert result["status"]=="CLOCK_OFFSET_SUSPECTED"
    assert result["v2_window"] is None and not result["ready_for_v2_contract"]
    assert result["candidate_v2_window"] is not None
    assert result["imu_gnss_time_offset"]==0.0


def test_no_onset_is_explicit_and_no_fabricated_time():
    args=make_input()
    args["gnss_speeds"]=[0.0]*50
    result=event.compute_event_window(**args)
    assert result["status"]=="EVENT_WINDOW_NOT_DETECTED"
    assert result["t_on_g"] is None and result["delta_t_onset_ms"] is None


def test_floor_start_must_still_be_after_detected_kick():
    args=make_input()
    args["kick_report"]={"status":"DETECTED","kick_time_R1":10.8}
    args["gnss_times"]=[float(t)+.9 for t in range(50)]
    result=event.compute_event_window(**args)
    assert result["candidate_v2_window"]["t_start"]==10
    assert result["status"]=="WINDOW_GATE_FAILED"


def test_by2_control_gate_pass_and_fail_without_parameter_adjustment():
    args=make_input("BY2")
    shift_times(args,56)
    args["common_coverage"]={"first":55.20679450035095,"last":349.20453906059265}
    args["kick_report"]={"status":"DETECTED","kick_time_R1":62.579067}
    result=event.compute_event_window(**args)
    assert result["ready_for_v2_contract"] and result["v2_window"]=={"t_start":66.0,"t_end":340.0}
    shift_times(args,1)
    result=event.compute_event_window(**args)
    assert result["status"]=="CONTROL_GATE_FAILED" and result["v2_window"] is None


def test_by2o_occlusion_windows_are_preserved_verbatim():
    args=make_input("BY2O",start=16)
    shift_times(args,3140)
    args["kick_report"]={"status":"DETECTED","kick_time_R1":3154.351049}
    args["common_coverage"]={"first":3143.211548805237,"last":3572.2081441879272}
    args["occlusion_window"]={"main_window":{"t0":event.OCCLUSION_INTERVALS[0][0],"t1":event.OCCLUSION_INTERVALS[0][1]},
                               "secondary_runs":[{"t0":event.OCCLUSION_INTERVALS[1][0],"t1":event.OCCLUSION_INTERVALS[1][1]}]}
    result=event.compute_event_window(**args)
    assert result["ready_for_v2_contract"]
    assert result["occlusion_preservation"]["wholly_within_v2_window"]
    assert result["occlusion_preservation"]["before_main_seconds"]==event.OCCLUSION_INTERVALS[0][0]-3156
    args["occlusion_window"]["main_window"]["t0"]+=.001
    result=event.compute_event_window(**args)
    assert not result["ready_for_v2_contract"]


def test_speed_loader_uses_frozen_schema_columns_and_preserves_rows(tmp_path):
    gnss,hv=tmp_path/"frozen.gnss",tmp_path/"frozen.csv"
    rows=[]
    for t in (1,2,3):
        row=[0.0]*15
        row[0]=t;row[7]=3;row[8]=4
        rows.append(" ".join(map(str,row)))
    gnss.write_text("\n".join(rows)+"\n")
    hv.write_text("time,vn,ve\n1,5,12\n2,5,12\n3,5,12\n")
    result=event.load_speed_inputs(gnss,hv)
    assert result["gnss_speeds"]==[5.0]*3
    assert result["body_speeds"]==[13.0]*3
    with pytest.raises(Exception,match="forbids opening"):
        event.load_speed_inputs(tmp_path/"trace_fake.csv",hv)


def test_kick_failure_is_not_detected_without_retry_or_replacement(tmp_path,monkeypatch):
    calls=[]
    def fake_detector(*args,**kwargs):
        calls.append(1)
        raise event.kick_alignment.KickAlignmentError("synthetic no initial segment")
    monkeypatch.setattr(event.kick_alignment,"detect_frozen_go2_kick",fake_detector)
    report=event.detect_kick_report(tmp_path/"synthetic.txt",base_time=0,diagnostic_dir=tmp_path/"new")
    assert calls==[1]
    assert report["status"]=="NOT_DETECTED" and report["kick_time_R1"] is None
    assert report["retry_count"]==0
    assert report["maintained_candidate_path"] is None


def test_censoring_uses_full_hole_even_when_left_endpoint_precedes_lookback():
    result=event.onset_censoring([400,400.05,407,413.041069,413.05],413.041069,
        gap_threshold_seconds=.1,source="synthetic")
    assert result["first_sample_after_hole"]
    assert result["censored"]
    assert result["onset_interval_R1"]==[407,413.041069]
    assert result["triggering_holes"][0]["t_start"]<result["lookback_interval_R1"][0]


def test_censoring_lookback_includes_prior_hole_without_first_sample_match():
    result=event.onset_censoring([0,.05,2,2.05,2.1,2.15],2.15,
        gap_threshold_seconds=.1,source="synthetic")
    assert result["censored"] and not result["first_sample_after_hole"]
    assert result["onset_interval_R1"]==[.05,2.15]


def test_first_raw_sample_matches_exact_frozen_hv_serialization_without_tolerance():
    raw_time,hv_time=411.7570643424988,411.7570643425
    assert raw_time!=hv_time
    assert event._encoded_hv_time(raw_time,28800.0)==hv_time
    values=[407.0,raw_time,411.76]
    result=event.onset_censoring(values,hv_time,gap_threshold_seconds=.1,source="raw Go2 synthetic timestamps",
                                hv_auxiliary_offset_seconds=28800.0)
    assert result["first_sample_after_hole"] and result["censored"]
    assert result["sample_identity_comparison"]=="exact frozen HV encoded timestamp"
    adjacent=event.onset_censoring(values,hv_time+1e-10,gap_threshold_seconds=.1,source="raw Go2 synthetic timestamps",
                                  hv_auxiliary_offset_seconds=28800.0)
    assert not adjacent["first_sample_after_hole"]
    assert result["gap_threshold_seconds"]==.1


def test_censoring_hole_threshold_is_strict_and_future_holes_do_not_censor():
    assert not event.onset_censoring([0,.1],.1,gap_threshold_seconds=.1,source="test")["censored"]
    result=event.onset_censoring([0,.05,.1,5],.1,gap_threshold_seconds=.1,source="test")
    assert not result["censored"] and result["onset_interval_R1"]==[.1,.1]


def test_censored_onset_uses_xcorr_and_reports_only_delta_interval():
    args=make_input()
    args["body_speeds"]=[.3 if t>=15 else 0.0 for t in args["body_times"]]
    args["raw_body_times"]=[t for t in args["raw_body_times"] if not 13<t<15]
    result=event.compute_event_window(**args)
    assert result["ready_for_v2_contract"] and result["onset_censored_b"]
    assert not result["onset_censored_g"]
    assert result["delta_t_onset_ms"] is None
    assert "observed_onset_difference_ms" not in result
    assert result["body_onset_interval_R1"]==[13.,result["t_on_b"]]
    assert result["gnss_onset_interval_R1"]==[10.,10.]
    assert result["delta_t_onset_interval_ms"]==pytest.approx([
        1000*(10-result["t_on_b"]),-3000.])
    assert result["clock_consistency_gate"]["basis"]=="full_coverage_xcorr"


@pytest.mark.parametrize("lag,passed",[(-1.0,True),(1.0,True),(-1.05,False),(1.05,False),(None,False)])
def test_censored_xcorr_gate_is_available_and_inclusive_one_second(lag,passed):
    args=make_input()
    args["raw_body_times"]=[t for t in args["raw_body_times"] if not 9<t<10]
    args["xcorr"]={"status":"UNAVAILABLE","peak":None} if lag is None else {
        "status":"AVAILABLE","peak":{"lag_seconds":lag,"coefficient":.9}}
    result=event.compute_event_window(**args)
    assert result["onset_censored_b"]
    assert result["ready_for_v2_contract"] is passed
    assert result["xcorr_gate"]["passed"] is passed
    if not passed:
        assert result["status"]=="CLOCK_OFFSET_SUSPECTED" and result["v2_window"] is None


def test_gnss_gap_censors_with_twice_its_median_interval():
    args=make_input()
    selected=[index for index,t in enumerate(args["gnss_times"]) if t not in (9,10)]
    for key in ("gnss_times","gnss_speeds"):
        args[key]=[args[key][index] for index in selected]
    result=event.compute_event_window(**args)
    assert result["onset_censored_g"] and not result["onset_censored_b"]
    assert result["censor_g"]["gap_threshold_seconds"]==2
    assert result["gnss_onset_interval_R1"]==[8,11]
    assert result["delta_t_onset_ms"] is None
    assert result["clock_consistency_gate"]["xcorr_used_as_hard_gate"]


@pytest.mark.parametrize("lag",[3.0,None])
def test_uncensored_point_gate_does_not_add_xcorr_hard_gate(lag):
    args=make_input()
    args["xcorr"]={"status":"UNAVAILABLE","peak":None} if lag is None else {
        "status":"AVAILABLE","peak":{"lag_seconds":lag,"coefficient":.8}}
    result=event.compute_event_window(**args)
    assert result["ready_for_v2_contract"]
    assert not result["xcorr_gate"]["passed"]
    assert result["clock_consistency_gate"]["basis"]=="uncensored_onset_point_difference"
    assert not result["clock_consistency_gate"]["xcorr_used_as_hard_gate"]


@pytest.mark.parametrize("first_imu,adjusted,start",[(11.0,False,10.0),(11.0001,True,11.0)])
def test_propagation_start_advances_only_when_delay_exceeds_one(first_imu,adjusted,start):
    args=make_input()
    args["imu_times"]=[t for t in args["imu_times"] if t<10 or t>first_imu]
    args["imu_times"].append(first_imu)
    args["imu_times"].sort()
    result=event.compute_event_window(**args)
    shift=result["propagation_start_adjustment"]
    assert shift["unadjusted_start"]==10
    assert shift["first_imu_time_at_or_after_start"]==first_imu
    assert shift["adjusted"] is adjusted
    assert result["adjusted_for_imu_dropout"] is adjusted
    assert result["v2_window"]["t_start"]==start


def test_h_411_start_advances_to_413_and_retains_internal_dropout():
    args=make_input()
    shift_times(args,401)
    args["common_coverage"]={"first":400.20381903648376,"last":692.2076218128204}
    for key in ("imu_times","raw_body_times"):
        args[key]=[t for t in args[key] if not 407<t<413.041069 and not 430<t<431]
        args[key].append(413.041069)
        args[key].sort()
    result=event.compute_event_window(**args)
    assert result["propagation_start_adjustment"]["unadjusted_start"]==411
    assert result["propagation_start_adjustment"]["adjusted"]
    assert result["v2_window"]=={"t_start":413.0,"t_end":683.0}
    assert any(item["t_start"]==430 and item["t_end"]==431 for item in result["preserve_internal_dropout"])
    assert result["kick"]["status"]=="NOT_DETECTED"
    assert result["kick_dropout_hypothesis"]["status"]=="HYPOTHESIS_ONLY"
    assert not result["kick_dropout_hypothesis"]["kick_time_assigned"]


def test_missing_propagation_support_fails_without_invented_initialization():
    args=make_input()
    args["imu_times"]=[0,.01,.02]
    result=event.compute_event_window(**args)
    assert not result["ready_for_v2_contract"]
    assert result["propagation_start_adjustment"]["first_imu_time_at_or_after_start"] is None


def test_o_requires_fixed_post_kick_bound_even_if_detector_absent():
    args=make_input("BY2O")
    shift_times(args,3140)
    args["common_coverage"]={"first":3143.211548805237,"last":3572.2081441879272}
    args["occlusion_window"]={"main_window":{"t0":a,"t1":b} for a,b in [event.OCCLUSION_INTERVALS[0]]}
    args["occlusion_window"]["secondary_runs"]=[dict(zip(("t0","t1"),event.OCCLUSION_INTERVALS[1]))]
    result=event.compute_event_window(**args)
    assert result["candidate_v2_window"]["t_start"]==3150
    assert result["status"]=="WINDOW_GATE_FAILED"
    assert any("3154.351049" in failure for failure in result["failures"])
