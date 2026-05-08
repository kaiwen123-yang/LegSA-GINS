"""中文说明：N4R3 official parity lock 单元测试只使用 toy artifact。"""

import json
from pathlib import Path

from legsa_gins.evaluation.dual_final_v23_official_parity_lock import lock_dual_final_v23_official_parity


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_dual(root: Path, yaw_error: float = 1.814) -> Path:
    _write(
        root / "KF_GINS_Navresult.nav",
        "0 0 40 116 10 0 0 0 0 0 0\n0 1 40 116 10 0 0 0 0 0 0\n",
    )
    _write(root / "KF_GINS_STD.txt", "std\n")
    _write(root / "input.gnss", "gnss\n")
    _write(
        root / "summary.json",
        json.dumps(
            {
                "position": {"horizontal_rmse_m": 0.353, "up_rmse_m": 0.818},
                "attitude": {"roll_rmse_deg": 1.025, "pitch_rmse_deg": 1.524, "yaw_rmse_deg": yaw_error},
            }
        )
        + "\n",
    )
    _write(
        root / "error_series.csv",
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n"
        f"0,0.353,0,0.818,1.025,1.524,{yaw_error}\n"
        f"1,0.353,0,0.818,1.025,1.524,{yaw_error}\n",
    )
    return root


def test_profile_confirmation_needs_dual_official_summary(tmp_path) -> None:
    missing = lock_dual_final_v23_official_parity(tmp_path / "missing", output_dir=tmp_path / "missing_out")
    assert missing["evaluator_profile_confirmed"] is False
    assert missing["recommended_next_stage"] == "N4R_manual_dual_artifact_required"


def test_direct_profile_locks_against_official_error_series(tmp_path) -> None:
    report = lock_dual_final_v23_official_parity(_make_dual(tmp_path / "dual"), output_dir=tmp_path / "out")
    assert report["evaluator_profile_confirmed"] is True
    assert report["confirmed_profile_name"] == "direct_identity"
    assert report["profile_results"]["direct_identity"]["summary_lock_passed"] is True
    assert report["profile_results"]["direct_identity"]["error_series_lock_passed"] is True
    assert report["trace_solver_input"] is False
    assert report["output_only_correction"] is False
