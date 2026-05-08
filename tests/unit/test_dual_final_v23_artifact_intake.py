"""中文说明：N4R3 artifact intake 单元测试只使用 toy artifact。"""

import json
from pathlib import Path

from legsa_gins.source_audit.dual_final_v23_artifact_intake import (
    classify_dual_summary,
    run_dual_artifact_intake,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_root(root: Path, horizontal: float, up: float, yaw: float) -> Path:
    _write(root / "input.gnss", "gnss\n")
    _write(root / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 0\n")
    _write(root / "KF_GINS_STD.txt", "std\n")
    _write(root / "error_series.csv", "time,yaw_err_deg\n0,0\n")
    _write(
        root / "summary.json",
        json.dumps(
            {
                "position": {"horizontal_rmse_m": horizontal, "up_rmse_m": up},
                "attitude": {"yaw_rmse_deg": yaw, "roll_rmse_deg": 1.025, "pitch_rmse_deg": 1.524},
            }
        )
        + "\n",
    )
    return root


def test_confirmed_dual_classification() -> None:
    report = classify_dual_summary({"horizontal_rmse_m": 0.353, "up_rmse_m": 0.818, "yaw_rmse_deg": 1.814})
    assert report["dual_final_v23_confirmed"] is True
    assert report["single_like"] is False


def test_single_like_classification() -> None:
    report = classify_dual_summary({"horizontal_rmse_m": 38.947, "up_rmse_m": 1.1, "yaw_rmse_deg": 41.375})
    assert report["dual_final_v23_confirmed"] is False
    assert report["single_like"] is True


def test_missing_artifact_requires_manual_root(tmp_path) -> None:
    report = run_dual_artifact_intake(tmp_path / "missing", output_dir=tmp_path / "out")
    assert report["manual_artifact_required"] is True
    assert report["evidence_status"] == "evidence_missing"
    assert report["trace_solver_input"] is False
    assert report["output_only_correction"] is False


def test_intake_report_confirmed(tmp_path) -> None:
    report = run_dual_artifact_intake(_make_root(tmp_path / "dual", 0.353, 0.818, 1.814), output_dir=tmp_path / "out")
    assert report["dual_final_v23_confirmed"] is True
    assert report["dual_artifact_intake_status"] == "dual_final_v23_confirmed"
    assert report["validation"]["required_files_complete"] is True
