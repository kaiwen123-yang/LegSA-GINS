#!/usr/bin/env python3
"""Audit N4R3 dual_final_v23 artifact intake and parity lock.

中文说明：只使用 toy artifacts；不读取真实 raw data，不修改 solver，不提交 artifact。
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.dual_final_v23_official_parity_lock import lock_dual_final_v23_official_parity  # noqa: E402
from legsa_gins.evaluation.n4h2_replay_profile_revaluation import reevaluate_n4h2_replay_profiles  # noqa: E402
from legsa_gins.source_audit.dual_final_v23_artifact_intake import (  # noqa: E402
    classify_dual_summary,
    run_dual_artifact_intake,
)


REQUIRED_FILES = [
    "src/legsa_gins/source_audit/dual_final_v23_artifact_intake.py",
    "scripts/experiments/run_dual_final_v23_artifact_intake.py",
    "src/legsa_gins/evaluation/dual_final_v23_official_parity_lock.py",
    "scripts/experiments/run_dual_final_v23_official_parity_lock.py",
    "docs/experiments/n4r3_dual_artifact_intake_decision.md",
    "docs/experiments/dual_final_v23_artifact_intake_contract.md",
    "docs/experiments/dual_final_v23_official_parity_lock.md",
    "docs/codex_prompts/N4R3_dual_final_v23_artifact_intake.md",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_dual_root(root: Path, *, yaw_error: float = 1.814) -> Path:
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


def _make_n4h2_near_gate(root: Path) -> Path:
    _write(
        root / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv",
        "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        "0,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "1,40,116,10,0,0,0,0,0,0,baseline,baseline\n",
    )
    _write(
        root / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv",
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        "0,0,0,0,0,0,0,0,0,-92.06058\n"
        "1,1,0,0,0,0,0,0,0,-92.06058\n",
    )
    return root


def _assert_boundary(report: dict, name: str) -> None:
    for key in ["trace_solver_input", "output_only_correction", "numerical_performance_claim"]:
        if report.get(key) is not False:
            raise AssertionError(f"{name} {key} must be false")


def audit(root: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")
    if not classify_dual_summary({"horizontal_rmse_m": 0.353, "up_rmse_m": 0.818, "yaw_rmse_deg": 1.814})[
        "dual_final_v23_confirmed"
    ]:
        raise AssertionError("dual summary should confirm")
    if not classify_dual_summary({"horizontal_rmse_m": 38.0, "up_rmse_m": 1.0, "yaw_rmse_deg": 41.0})["single_like"]:
        raise AssertionError("single-like summary should be rejected")

    with tempfile.TemporaryDirectory(prefix="legsa_n4r3_audit_") as tmp_name:
        tmp = Path(tmp_name)
        missing_report = run_dual_artifact_intake(tmp / "missing", output_dir=tmp / "missing_out")
        if missing_report["manual_artifact_required"] is not True:
            raise AssertionError("missing artifact must require manual artifact")
        _assert_boundary(missing_report, "missing_report")

        dual_root = _make_dual_root(tmp / "dual")
        intake = run_dual_artifact_intake(dual_root, output_dir=tmp / "intake")
        if intake["dual_final_v23_confirmed"] is not True:
            raise AssertionError("toy dual intake did not confirm")
        _assert_boundary(intake, "intake_report")

        lock_missing = lock_dual_final_v23_official_parity(tmp / "missing", output_dir=tmp / "lock_missing")
        if lock_missing["evaluator_profile_confirmed"] is not False:
            raise AssertionError("profile confirmation must require dual artifact")

        lock = lock_dual_final_v23_official_parity(dual_root, output_dir=tmp / "lock")
        if lock["evaluator_profile_confirmed"] is not True:
            raise AssertionError("toy dual official parity did not lock")
        _assert_boundary(lock, "lock_report")

        replay = reevaluate_n4h2_replay_profiles(_make_n4h2_near_gate(tmp / "n4h2"), output_dir=tmp / "replay")
        if replay["yaw_gate_pass_for_each_profile"]["official_candidate_ref_heading_to_math"] is not False:
            raise AssertionError("yaw=2.06058 must not pass strict gate")
        if replay["near_gate_status"]["official_candidate_ref_heading_to_math"] is not True:
            raise AssertionError("yaw=2.06058 should be near-gate")
        _assert_boundary(replay, "replay_report")

    tracked_docs = [
        root / "docs/experiments/n4r3_dual_artifact_intake_decision.md",
        root / "docs/experiments/dual_final_v23_artifact_intake_contract.md",
        root / "docs/experiments/dual_final_v23_official_parity_lock.md",
        root / "docs/experiments/n4h2_replay_profile_revaluation.md",
        root / "docs/codex_prompts/N4R3_dual_final_v23_artifact_intake.md",
    ]
    forbidden = [
        str(Path("/home") / "kaiwen") + "/",
        str(Path("/mnt") / "c" / "Users") + "/",
        "C:" + "\\Users",
    ]
    for doc in tracked_docs:
        text = doc.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                raise AssertionError(f"tracked doc contains local absolute path: {doc}")


def main() -> int:
    try:
        audit(REPO_ROOT)
    except AssertionError as exc:
        print(f"N4R3 dual artifact intake audit failed: {exc}")
        return 1
    print("N4R3 dual artifact intake audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
