import tempfile
from pathlib import Path

from scripts.audit_n6b1_source_aware_visual_validation import _write_reference, _write_reports
from legsa_gins.source_aware.source_aware_n6b_visual_loader import load_n6b1_visual_inputs


def test_n6b1_loader_finds_reports_trace_and_timeseries():
    # 中文说明：loader 只读取 runtime 输出和 evaluation reference，不回灌 solver。
    with tempfile.TemporaryDirectory(prefix="legsa_n6b1_loader_") as tmp_value:
        tmp = Path(tmp_value)
        n6b = tmp / "n6b"
        dual = tmp / "dual"
        n5d1 = tmp / "n5d1"
        n6b.mkdir()
        n5d1.mkdir()
        _write_reference(dual / "KF_GINS_Navresult.nav")
        _write_reports(n6b)
        data = load_n6b1_visual_inputs(n6b_root=n6b, n5d1_root=n5d1, dual_root=dual)
        manifest = data["manifest"]
        assert all(manifest["n6b_reports_found"].values())
        assert manifest["source_aware_trace_found"] is True
        assert manifest["clean_time_series_found"] is True
        assert manifest["stress_time_series_found"] is True
        assert manifest["final_v23_output_solver_input"] is False
        assert manifest["trace_solver_input"] is False


def test_n6b1_loader_detects_missing_timeseries():
    with tempfile.TemporaryDirectory(prefix="legsa_n6b1_loader_missing_") as tmp_value:
        tmp = Path(tmp_value)
        n6b = tmp / "n6b"
        dual = tmp / "dual"
        n6b.mkdir()
        _write_reference(dual / "KF_GINS_Navresult.nav")
        data = load_n6b1_visual_inputs(n6b_root=n6b, n5d1_root=None, dual_root=dual)
        assert data["manifest"]["clean_time_series_found"] is False
        assert data["manifest"]["stress_time_series_found"] is False
