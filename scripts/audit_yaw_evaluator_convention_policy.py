#!/usr/bin/env python3
"""Audit N4R2 yaw evaluator convention policy and dual artifact verification.

中文说明：本 audit 只使用 toy artifacts；不读取真实 raw data，不修改 solver，
不把 trace/reference 作为 solver input。
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

from legsa_gins.evaluation.dual_final_v23_evaluator_parity import evaluate_dual_final_v23_evaluator_parity  # noqa: E402
from legsa_gins.evaluation.n4h2_replay_profile_revaluation import reevaluate_n4h2_replay_profiles  # noqa: E402
from legsa_gins.evaluation.yaw_evaluator_convention_policy import (  # noqa: E402
    default_yaw_convention_profiles,
    evaluate_with_yaw_profile,
    get_profile,
    write_yaw_convention_policy_report,
)
from legsa_gins.source_audit.dual_final_v23_artifact_recovery import recover_dual_final_v23_artifacts  # noqa: E402


REQUIRED_FILES = [
    "src/legsa_gins/evaluation/yaw_evaluator_convention_policy.py",
    "src/legsa_gins/source_audit/dual_final_v23_artifact_recovery.py",
    "scripts/experiments/run_dual_final_v23_artifact_recovery.py",
    "src/legsa_gins/evaluation/dual_final_v23_evaluator_parity.py",
    "scripts/experiments/run_dual_final_v23_evaluator_parity.py",
    "src/legsa_gins/evaluation/n4h2_replay_profile_revaluation.py",
    "scripts/experiments/run_n4h2_replay_profile_revaluation.py",
    "scripts/audit_yaw_evaluator_convention_policy.py",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_dual_toy(root: Path) -> tuple[Path, Path]:
    dual = root / "external" / "extended_degradation_results" / "final_v23" / "dual" / "E001_single_nominal_none"
    _write(
        dual / "KF_GINS_Navresult.nav",
        "0 0 40 116 10 0 0 0 0 0 0\n0 1 40 116 10 0 0 0 0 0 0\n",
    )
    _write(dual / "KF_GINS_STD.txt", "std\n")
    _write(dual / "input.gnss", "gnss\n")
    _write(
        dual / "summary.json",
        json.dumps(
            {
                "position": {"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0},
                "attitude": {"roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0, "yaw_rmse_deg": 0.0},
            }
        )
        + "\n",
    )
    _write(
        dual / "error_series.csv",
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n"
        "0,0,0,0,0,0,0\n1,0,0,0,0,0,0\n",
    )
    n4h2 = root / "n4h2"
    _write(
        n4h2 / "replay" / "standardized" / "FINAL_V23_EVAL_NAV.csv",
        "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        "0,40,116,10,0,0,0,0,0,0,baseline,baseline\n"
        "1,40,116,10,0,0,0,0,0,0,baseline,baseline\n",
    )
    _write(
        n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_ERROR_SERIES.csv",
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        "0,0,0,0,0,0,0,0,0,-90\n"
        "1,1,0,0,0,0,0,0,0,-90\n",
    )
    return dual, n4h2


def _assert_boundaries(report: dict, name: str) -> None:
    expected = {
        "solver_output_changed": False,
        "evaluator_only": True,
        "trace_solver_input": False,
        "output_only_correction": False,
    }
    for key, value in expected.items():
        if report.get(key) is not value:
            raise AssertionError(f"{name} {key} is not {value}")


def audit(root: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")

    profiles = {profile["name"]: profile for profile in default_yaw_convention_profiles()}
    if profiles["official_candidate_ref_heading_to_math"]["formal_allowed"] is not False:
        raise AssertionError("official candidate must remain formal_allowed=false before dual confirmation")

    with tempfile.TemporaryDirectory(prefix="legsa_n4r2_audit_") as tmp_name:
        tmp = Path(tmp_name)
        nav = [{"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 0.0}]
        ref = [{"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 90.0}]
        direct = evaluate_with_yaw_profile(nav, ref, get_profile("direct_identity"), tmp / "direct")
        candidate = evaluate_with_yaw_profile(nav, ref, get_profile("official_candidate_ref_heading_to_math"), tmp / "candidate")
        if not (direct["summary"]["yaw_rmse_deg"] > 80.0 and candidate["summary"]["yaw_rmse_deg"] < 0.1):
            raise AssertionError("toy single-like case did not suggest official_candidate")
        _assert_boundaries(candidate, "candidate_profile_report")

        policy = write_yaw_convention_policy_report(tmp)
        _assert_boundaries(policy, "policy_report")

        dual, n4h2 = _make_dual_toy(tmp)
        recovery_dual = tmp / "external" / "extended_degradation_results" / "final_v23" / "dual" / "recovery_E001_single_nominal_none"
        _write(recovery_dual / "KF_GINS_Navresult.nav", "0 0 40 116 10 0 0 0 0 0 0\n")
        _write(recovery_dual / "KF_GINS_STD.txt", "std\n")
        _write(recovery_dual / "input.gnss", "gnss\n")
        _write(
            recovery_dual / "summary.json",
            json.dumps(
                {
                    "position": {"horizontal_rmse_m": 0.353, "up_rmse_m": 0.818},
                    "attitude": {"roll_rmse_deg": 0.2, "pitch_rmse_deg": 0.3, "yaw_rmse_deg": 1.814},
                }
            )
            + "\n",
        )
        recovery = recover_dual_final_v23_artifacts({"TOY_ROOT": tmp / "external"}, max_depth=8)
        if recovery["dual_artifact_found"] is not True:
            raise AssertionError("toy dual artifact was not recovered")
        group = {
            "group_id": "TOY_DUAL:0",
            "role_alias": "DUAL_FINAL_V23_CANDIDATE:0",
            "artifacts": {
                "KF_GINS_Navresult.nav": str(dual / "KF_GINS_Navresult.nav"),
                "summary.json": str(dual / "summary.json"),
                "error_series.csv": str(dual / "error_series.csv"),
            },
        }
        missing_dual = evaluate_dual_final_v23_evaluator_parity(
            None,
            external_source_root=tmp / "external",
            n4h2_artifacts_root=n4h2,
            output_dir=tmp / "missing_dual",
        )
        if missing_dual["dual_evaluator_profile_confirmed"] is not False:
            raise AssertionError("dual confirmation should require a dual candidate")
        dual_report = evaluate_dual_final_v23_evaluator_parity(
            group,
            external_source_root=tmp / "external",
            n4h2_artifacts_root=n4h2,
            output_dir=tmp / "dual_parity",
        )
        if dual_report["dual_evaluator_profile_confirmed"] is not True:
            raise AssertionError("toy dual candidate did not confirm official candidate")
        _assert_boundaries(dual_report, "dual_report")

        replay = reevaluate_n4h2_replay_profiles(n4h2, output_dir=tmp / "replay")
        _assert_boundaries(replay, "replay_report")

    tracked_docs = [
        root / "docs/experiments/n4r_yaw_evaluator_decision.md",
        root / "docs/experiments/yaw_evaluator_convention_policy.md",
        root / "docs/experiments/dual_final_v23_artifact_recovery.md",
        root / "docs/experiments/n4h2_replay_profile_revaluation.md",
    ]
    forbidden = [
        str(Path("/home") / "kaiwen") + "/",
        str(Path("/mnt") / "c" / "Users") + "/",
        "C:" + "\\Users",
    ]
    for doc in tracked_docs:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                raise AssertionError(f"tracked doc contains local absolute path: {doc}")


def main() -> int:
    try:
        audit(REPO_ROOT)
    except AssertionError as exc:
        print(f"N4R2 yaw evaluator convention policy audit failed: {exc}")
        return 1
    print("N4R2 yaw evaluator convention policy audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
