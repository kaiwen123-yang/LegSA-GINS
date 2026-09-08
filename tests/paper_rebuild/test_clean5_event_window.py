"""Synthetic event-window fixtures; no real provider or raw input reads."""
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean5_sequence import event_window as event


def make_input(dataset="BY2H", *, start=10.0, end=49.3):
    times = np.arange(0.0,50.01,0.1).round(8).tolist()
    return {"dataset_id":dataset,"gnss_times":list(range(50)),
            "gnss_speeds":[0.3 if t>=start else 0.0 for t in range(50)],
            "body_times":times,"body_speeds":[0.3 if t>=start else 0.0 for t in times],
            "common_coverage":{"first":1.0,"last":end},
            "kick_report":{"status":"NOT_DETECTED","kick_time_R1":None},
            "v1_window":{"t_start":11.0,"t_end":40.0}}


def test_fixed_constants_and_human_statement():
    rules=event.constants()
    assert rules["speed_threshold_mps"]==0.15
    assert rules["gnss_consecutive_epochs"]==3
    assert rules["body_mean_window_seconds"]==1.0
    assert rules["body_persistence_seconds"]==3.0
    assert rules["max_onset_difference_seconds"]==1.0
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
    args["gnss_times"]=[float(t)+56 for t in args["gnss_times"]]
    args["body_times"]=[t+56 for t in args["body_times"]]
    args["common_coverage"]={"first":55.20679450035095,"last":349.20453906059265}
    args["kick_report"]={"status":"DETECTED","kick_time_R1":62.579067}
    result=event.compute_event_window(**args)
    assert result["ready_for_v2_contract"] and result["v2_window"]=={"t_start":66.0,"t_end":340.0}
    args["body_times"]=[t+10 for t in args["body_times"]]
    args["gnss_times"]=[t+10 for t in args["gnss_times"]]
    result=event.compute_event_window(**args)
    assert result["status"]=="CONTROL_GATE_FAILED" and result["v2_window"] is None


def test_by2o_occlusion_windows_are_preserved_verbatim():
    args=make_input("BY2O")
    args["gnss_times"]=[float(t)+3140 for t in args["gnss_times"]]
    args["body_times"]=[t+3140 for t in args["body_times"]]
    args["common_coverage"]={"first":3143.211548805237,"last":3572.2081441879272}
    args["occlusion_window"]={"main_window":{"t0":event.OCCLUSION_INTERVALS[0][0],"t1":event.OCCLUSION_INTERVALS[0][1]},
                               "secondary_runs":[{"t0":event.OCCLUSION_INTERVALS[1][0],"t1":event.OCCLUSION_INTERVALS[1][1]}]}
    result=event.compute_event_window(**args)
    assert result["ready_for_v2_contract"]
    assert result["occlusion_preservation"]["wholly_within_v2_window"]
    assert result["occlusion_preservation"]["before_main_seconds"]==event.OCCLUSION_INTERVALS[0][0]-3150
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
