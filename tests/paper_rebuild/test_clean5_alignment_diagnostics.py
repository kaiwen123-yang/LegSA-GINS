"""Synthetic C-04b diagnostic time axes and lag signals only."""
import json

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean5_sequence import alignment_diagnostics as diag


def test_holes_preserve_source_order_and_mark_v2_overlap():
    result=diag.summarize_time_holes([0,.05,.1,.6,.65,.6,None,1,1.05],v2_window={"t_start":.2,"t_end":.5})
    assert result["hole_count"]==1
    gap=result["holes"][0]
    assert gap["t_start"]==.1 and gap["t_end"]==.6 and gap["duration_seconds"]==.5
    assert gap["overlaps_v2_window"] and gap["overlap_seconds"]==pytest.approx(.3)
    assert gap["inferred_missing_sample_count"] is None
    assert len(result["nonpositive_intervals"])==1
    assert result["invalid_timestamp_row_indices_zero_based"]==[6]
    assert result["source_rows_sorted_or_deleted"] is False


def test_hole_start_at_window_end_has_no_interval_overlap():
    result=diag.summarize_time_holes([0,.05,.8],v2_window={"t_start":.8,"t_end":2})
    assert result["holes"][0]["overlaps_v2_window"] is False


def signal_fixture(delay=.5):
    times=np.arange(0,40.001,.05).round(8)
    speed=lambda t: 2+np.sin(.71*t)+.4*np.sin(1.89*t)+.1*np.cos(3.1*t)
    return {"gnss_times":times,"gnss_speeds":speed(times),
            "body_times":times,"body_speeds":speed(times-delay),
            "common_coverage":{"first":1.,"last":39.}}


def test_xcorr_lag_sign_peak_grid_and_no_offset_application():
    result=diag.normalized_speed_xcorr(**signal_fixture(.5))
    assert result["status"]=="AVAILABLE"
    assert result["peak"]["lag_seconds"]==pytest.approx(.5)
    assert result["peak"]["coefficient"]==pytest.approx(1.)
    assert len(result["lag_profile"])==201
    assert result["lag_profile"][0]["lag_seconds"]==-5.
    assert result["lag_profile"][-1]["lag_seconds"]==5.
    assert result["imu_gnss_time_offset"]==0.0 and result["offset_applied"] is False
    json.dumps(result,allow_nan=False)


def test_zero_variance_is_unavailable_not_zero_coefficient():
    result=diag.normalized_speed_xcorr(gnss_times=[0,1,2,3],gnss_speeds=[1]*4,
                                      body_times=[0,1,2,3],body_speeds=[2]*4,
                                      common_coverage={"first":0,"last":3})
    assert result["status"]=="UNAVAILABLE" and result["peak"] is None
    assert all(row["coefficient"] is None for row in result["lag_profile"])


def test_resampling_does_not_fill_source_holes_with_artificial_values():
    args=signal_fixture()
    keep=(args["body_times"]<10)|(args["body_times"]>15)
    args["body_times"]=args["body_times"][keep]
    args["body_speeds"]=args["body_speeds"][keep]
    result=diag.normalized_speed_xcorr(**args)
    assert result["body_unavailable_grid_sample_count"]>=50
    assert result["peak"]["overlap_pair_count"]<result["common_grid_sample_count"]


def test_secondary_peak_is_distinct_local_maximum():
    times=np.arange(0,40.001,.1).round(8)
    values=2+np.cos(np.pi*times)
    result=diag.normalized_speed_xcorr(gnss_times=times,gnss_speeds=values,
                                      body_times=times,body_speeds=values,
                                      common_coverage={"first":1,"last":39})
    assert result["secondary_peak"] is not None
    assert abs(result["secondary_peak"]["lag_seconds"]-result["peak"]["lag_seconds"])>.1


def test_report_first_line_and_holes_when_event_gate_failed():
    report=diag.diagnose(dataset_id="BY2",imu_times=[0,.01,.02,.5],raw_body_times=[0,.01,.5],
                         v2_window=None,**signal_fixture())
    text=diag.markdown_report(report)
    assert text.splitlines()[0]=="DIAGNOSTIC ONLY — imu_gnss_time_offset stays 0.0"
    assert report["imu_increment_holes"]["holes"][0]["overlaps_v2_window"] is None
    assert report["offset_selected_for_solver"] is False


def test_imu_loader_requires_exact_columns(tmp_path):
    path=tmp_path/"fixture.imu"
    path.write_text("0 0 0 0 0 0 0\n1 0 0 0 0 0 0\n")
    assert diag.read_imu_increment_times(path)==[0.,1.]
    path.write_text("0 1 2\n")
    with pytest.raises(Exception,match="seven columns"):
        diag.read_imu_increment_times(path)


def test_diagnostics_reuse_frozen_xcorr_and_report_by2_difference_only(monkeypatch):
    correlation=diag.normalized_speed_xcorr(**signal_fixture(.5))
    monkeypatch.setattr(diag,"normalized_speed_xcorr",lambda **_:pytest.fail("Do not recompute supplied full-coverage xcorr"))
    report=diag.diagnose(dataset_id="BY2H",imu_times=[0,.01,.02],raw_body_times=[0,.01,.02],
                         xcorr=correlation,by2_peak_lag_seconds=-.1,**signal_fixture())
    assert report["xcorr"] is correlation
    assert report["xcorr_gate"]["passed"]
    assert report["xcorr_gate"]["difference_from_by2_primary_lag_seconds"]==pytest.approx(.6)
    assert report["xcorr_gate"]["by2_difference_report_only"]
    assert report["xcorr_gate"]["offset_applied_seconds"]==0.0


def test_censored_diagnostic_markdown_reports_interval_and_hypothesis():
    correlation=diag.normalized_speed_xcorr(**signal_fixture(.5))
    event={"onset_censored_b":True,"onset_censored_g":False,
           "body_onset_interval_R1":[7.,11.],"gnss_onset_interval_R1":[10.,10.],
           "delta_t_onset_ms":None,"delta_t_onset_interval_ms":[-1000.,3000.],
           "clock_consistency_gate":{"basis":"full_coverage_xcorr","passed":True},
           "propagation_start_adjustment":{"unadjusted_start":11.,"first_imu_time_at_or_after_start":13.04,
               "initialization_delay_seconds":2.04,"adjusted":True,"adjusted_start":13.},
           "preserve_internal_dropout":[],"kick_dropout_hypothesis":{"statement":"Synthetic hypothesis only."}}
    report=diag.diagnose(dataset_id="BY2H",imu_times=[0,.01,.02],raw_body_times=[0,.01,.02],
                         xcorr=correlation,event_report=event,**signal_fixture())
    text=diag.markdown_report(report)
    assert text.splitlines()[0]==diag.REPORT_FIRST_LINE
    assert "Onset difference interval only (ms): [-1000.0, 3000.0]" in text
    assert "Uncensored onset difference" not in text
    assert "HYPOTHESIS ONLY: Synthetic hypothesis only." in text
    assert "original=11.0; t_init=13.04" in text
