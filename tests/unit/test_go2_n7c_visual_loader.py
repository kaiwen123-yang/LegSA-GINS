"""N7C1 visual loader unit tests.

中文说明：单测只使用 synthetic runtime 目录，验证 loader 能识别 N7C 报告、
time-series、Go2 prior CSV 和 vertical-disabled 边界。
"""

from scripts.audit_n7c1_go2_horizontal_velocity_visual_validation import _prepare_n7c_runtime
from legsa_gins.go2_prior.go2_n7c_visual_loader import load_n7c1_visual_inputs


def test_n7c1_visual_loader_finds_reports_and_timeseries(tmp_path):
    n7c, n7b5, n5b, n6b, dual = _prepare_n7c_runtime(tmp_path)
    inputs = load_n7c1_visual_inputs(
        n7c_root=n7c,
        n7b5_root=n7b5,
        n5b_root=n5b,
        n6b_root=n6b,
        dual_root=dual,
    )
    manifest = inputs["manifest"]
    assert all(manifest["n7c_reports_found"].values())
    assert manifest["prior_build_report_found"] is True
    assert manifest["baseline_timeseries_found"] is True
    assert manifest["main_prior_timeseries_found"] is True
    assert manifest["stress_timeseries_found"] is True
    assert manifest["go2_prior_csv_found"] is True
    assert manifest["vertical_disabled_confirmed"] is True
    assert inputs["final_v23_output_solver_input"] is False
    assert inputs["trace_solver_input"] is False
