import json

from legsa_gins.source_aware.source_aware_spike_response import evaluate_spike_response


def test_spike_response_is_evaluation_only(tmp_path):
    # 中文说明：spike response 只匹配运行后 trace，不反馈调权策略。
    spike = tmp_path / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json"
    spike.write_text(json.dumps({"spike_epochs": [{"time": 1.0}], "spike_count": 1}), encoding="utf-8")
    trace = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    trace.write_text(
        "time,update_index,source_id,mode,lsim_score,oim_score,lsim_R_scale,oim_R_scale,combined_R_scale,residual_norm,normalized_innovation,base_R_trace,scaled_R_trace,accepted,rejected,reason_codes,metadata_summary\n"
        "1.000,1,raw_doppler_velocity,lsim_oim,1,0.5,1,4,4,3,4,1,4,1,0,oim_high,meta\n",
        encoding="utf-8",
    )
    report = evaluate_spike_response(spike_report_path=spike, source_aware_trace_path=trace)
    assert report["raw_doppler_R_scale_increased_near_spikes"] is True
    assert report["hardcoded_spike_time_weighting"] is False
    assert report["evaluation_only_sentinel"] is True
