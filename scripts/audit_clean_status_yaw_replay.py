#!/usr/bin/env python3
"""Audit N4H2G clean status-yaw replay tooling.

中文说明：该审计只用 toy summary/input contract 检查 clean/noisy provenance
边界；不运行外部 KF-GINS，不读取真实 raw data。
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.clean_status_yaw_replay import DEFAULT_CLEAN_POLICY  # noqa: E402
from legsa_gins.evaluation.clean_vs_noisy_replay_comparison import (  # noqa: E402
    classify_clean_replay_parity,
    compare_clean_vs_noisy_replay,
)
from legsa_gins.source_audit.clean_input_provenance_policy import (  # noqa: E402
    make_clean_input_provenance_policy_report,
)


REQUIRED_FILES = [
    "src/legsa_gins/evaluation/clean_status_yaw_replay.py",
    "src/legsa_gins/evaluation/clean_vs_noisy_replay_comparison.py",
    "src/legsa_gins/source_audit/clean_input_provenance_policy.py",
    "scripts/experiments/run_clean_status_yaw_replay.py",
    "docs/experiments/clean_status_yaw_replay.md",
    "docs/experiments/clean_vs_noisy_replay_comparison.md",
    "docs/experiments/clean_input_provenance_policy.md",
    "docs/experiments/n4h2g_clean_replay_decision.md",
    "docs/codex_prompts/N4H2G_clean_status_yaw_replay.md",
]


def _assert_boundary(report: dict, name: str) -> None:
    for key in ["trace_solver_input", "output_only_correction", "numerical_performance_claim"]:
        if report.get(key) is not False:
            raise AssertionError(f"{name} {key} must be false")


def audit(root: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")

    if DEFAULT_CLEAN_POLICY["yaw_noise_std_deg"] != 0.0:
        raise AssertionError("clean yaw noise must be zero")
    if DEFAULT_CLEAN_POLICY["outlier_mode"] != "none":
        raise AssertionError("clean outlier mode must be none")
    if DEFAULT_CLEAN_POLICY["enable_outage"] is not False:
        raise AssertionError("clean outage must be false")

    clean = {
        "horizontal_rmse_m": 0.35,
        "up_rmse_m": 0.8,
        "yaw_rmse_deg": 1.9,
        "roll_rmse_deg": 1.02,
        "pitch_rmse_deg": 1.52,
    }
    noisy = {
        "horizontal_rmse_m": 0.346,
        "up_rmse_m": 0.794,
        "yaw_rmse_deg": 1.979,
        "roll_rmse_deg": 1.02,
        "pitch_rmse_deg": 1.522,
    }
    comparison = compare_clean_vs_noisy_replay(clean_summary=clean, noisy_summary=noisy)
    if comparison["clean_replay_parity_status"] != "passed":
        raise AssertionError("toy clean summary should pass")
    if comparison["noisy_artifact_clean_nominal_claim_allowed"] is not False:
        raise AssertionError("noisy actual must not be called clean")
    _assert_boundary(comparison, "comparison")

    near = dict(clean, yaw_rmse_deg=2.06)
    if classify_clean_replay_parity(near) != "near_gate":
        raise AssertionError("yaw 2.06 should be near_gate, not pass")
    fail = dict(clean, yaw_rmse_deg=2.3)
    if classify_clean_replay_parity(fail) != "failed_yaw":
        raise AssertionError("yaw 2.3 should fail yaw")

    manifest = {
        "clean_input_policy": DEFAULT_CLEAN_POLICY,
        "yaw_noise_std_deg": 0.0,
        "outlier_mode": "none",
        "enable_outage": False,
    }
    policy = make_clean_input_provenance_policy_report(manifest, comparison)
    if policy["paper_should_not_call_noisy_actual_clean_nominal"] is not True:
        raise AssertionError("policy must reject noisy-as-clean wording")
    _assert_boundary(policy, "policy")

    docs = [root / path for path in REQUIRED_FILES if path.startswith("docs/")]
    forbidden = [str(Path("/home") / "kaiwen") + "/", str(Path("/mnt") / "c" / "Users") + "/", "C:" + "\\Users"]
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                raise AssertionError(f"tracked doc contains local absolute path: {doc}")


def main() -> int:
    try:
        audit(REPO_ROOT)
    except AssertionError as exc:
        print(f"N4H2G clean status-yaw replay audit failed: {exc}")
        return 1
    print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
