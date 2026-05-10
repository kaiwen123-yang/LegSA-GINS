import json

from legsa_gins.source_aware.source_aware_n6b_spike_response import evaluate_n6b_spike_response


def test_n6b_spike_response_is_after_run_audit(tmp_path):
    # 中文说明：spike report 只和已生成 trace 做事后匹配。
    spike = tmp_path / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json"
    spike.write_text(json.dumps({"spike_epochs": [{"time": 1.0}]}), encoding="utf-8")
    trace = tmp_path / "SOURCE_AWARE_WEIGHT_TRACE.csv"
    trace.write_text(
        "\n".join(
            [
                "time,source_id,combined_R_scale,oim_R_scale,lsim_R_scale,normalized_innovation,reason_codes",
                "0.0,raw_doppler_velocity,1.0,1.0,1.0,0.5,nominal",
                "1.0,raw_doppler_velocity,3.0,3.0,1.0,4.5,oim_strong_normalized_innovation",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = evaluate_n6b_spike_response(spike_report_path=spike, source_aware_trace_path=trace, tolerance_sec=0.1)
    assert report["hardcoded_spike_time_weighting"] is False
    assert report["nearest_rows_found"] == 1
    assert report["response_status"] in {"increased_strongly", "increased_mildly"}
