"""Tests for N8D raw/receiver balance report.

中文说明：Raw Doppler 低边际价值只能作为工程诊断。
"""

from legsa_gins.fgo.fgo_raw_receiver_weight_balance import build_raw_receiver_weight_balance_report


def test_raw_receiver_balance_report_has_no_claim() -> None:
    report = build_raw_receiver_weight_balance_report(
        {"variants": [{"variant": "receiver_vel_x1_raw_x1", "finite_output": True, "raw_doppler_share": 0.02, "diagnostic_only": False}]}
    )
    assert report["raw_doppler_remains_low_marginal_value"]
    assert report["no_paper_claim"]
    assert not report["trace_weight_tuning"]
