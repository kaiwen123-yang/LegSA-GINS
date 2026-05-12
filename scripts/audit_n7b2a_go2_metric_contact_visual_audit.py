#!/usr/bin/env python3
"""Audit N7B2A Go2 metric namespace/contact visual sanity runner.

中文说明：本脚本用合成数据验证 N7B2A runner，不使用 trace 或 final_v23 输出调阈值。
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "src/legsa_gins/go2_prior/go2_attitude_prior_std_review.py",
    "src/legsa_gins/go2_prior/go2_metric_namespace_guard.py",
    "src/legsa_gins/go2_prior/go2_contact_v2_physical_sanity.py",
    "src/legsa_gins/go2_prior/go2_n7b2a_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7b2a_decision.py",
    "scripts/experiments/run_n7b2a_go2_metric_contact_visual_audit.py",
    "scripts/audit_go2_metric_namespace_guard.py",
    "scripts/audit_go2_contact_v2_physical_sanity.py",
    "docs/experiments/n7b2a_go2_attitude_std_policy.md",
    "docs/experiments/n7b2a_metric_namespace_guard.md",
    "docs/experiments/n7b2a_contact_v2_physical_sanity.md",
    "docs/experiments/n7b2a_decision.md",
    "docs/codex_prompts/N7B2A_go2_metric_contact_visual_audit.md",
]

REQUIRED_OUTPUTS = [
    "GO2_ATTITUDE_PRIOR_STD_POLICY_REVIEW.json",
    "GO2_METRIC_NAMESPACE_GUARD_REPORT.json",
    "GO2_CONTACT_V2_PHYSICAL_SANITY_REPORT.json",
    "N7B2A_GO2_METRIC_CONTACT_DECISION_REPORT.json",
    "N7B2A_FIGURE_MANIFEST.json",
    "n7b2a_metric_contact_case_review.md",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7b2a_go2_metric_contact_visual_audit failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_contact_v2(path: Path) -> None:
    fields = [
        "time",
        "contact_label_v2",
        "contact_count_v2",
        *[f"foot_{foot}_contact_v2" for foot in range(4)],
        *[f"foot_{foot}_force" for foot in range(4)],
        *[f"foot_{foot}_speed_norm" for foot in range(4)],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(40):
            row = {"time": index * 0.1, "contact_label_v2": "walking_contact", "contact_count_v2": 4}
            for foot in range(4):
                row[f"foot_{foot}_contact_v2"] = 1
                row[f"foot_{foot}_force"] = 30.0 + foot
                row[f"foot_{foot}_speed_norm"] = 1.4
            writer.writerow(row)


def _prepare_runtime(root: Path) -> None:
    n7a = root / "n7a"
    n7b = root / "n7b"
    n7b2 = root / "n7b2"
    _write_json(n7a / "GO2_WEAK_PRIOR_BUILD_REPORT.json", {"std_policy": {"std_roll_deg": 5.0, "std_pitch_deg": 5.0}, "activation_allowed": True})
    _write_json(n7a / "GO2_QUATERNION_RPY_CHECK_REPORT.json", {"rpy_consistency_status": "passed", "activation_allowed_for_attitude_prior": True, "max_quat_rpy_delta_rad": 0.01})
    _write_json(n7a / "N7A_GO2_WEAK_PRIOR_COMPARISON_REPORT.json", {"std_screen_summaries": [{"std_deg": 5.0, "summary": {"roll_rmse_deg": 0.04, "pitch_rmse_deg": 0.03}}], "go2_attitude_weak_prior_minus_no_go2": {"delta": {"roll_rmse_deg": 0.04, "pitch_rmse_deg": 0.03}}})
    _write_json(n7a / "N7A_GO2_WEAK_PRIOR_DECISION_REPORT.json", {"status": "ready_with_weak_go2_evidence", "paper_performance_claim": False})
    _write_json(n7b / "GO2_VELOCITY_QUALITY_REPORT.json", {"velocity_diff_rmse_to_receiver": 1.0, "consistency_status": "acceptable_for_future_review", "not_truth": True})
    _write_json(n7b / "GO2_CONTACT_STATE_REPORT.json", {"uncertain_ratio": 0.9, "recommended_contact_quality_status": "review"})
    _write_json(n7b / "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json", {"status": "contact_not_ready"})
    _write_contact_v2(n7b2 / "GO2_CONTACT_STATE_V2_TIMESERIES.csv")
    _write_json(n7b2 / "GO2_CONTACT_DISTRIBUTION_REPORT.json", {"field_quality_status": "usable"})
    _write_json(n7b2 / "GO2_CONTACT_STATE_V2_REPORT.json", {"walking_contact_ratio": 1.0, "uncertain_ratio": 0.0, "physical_plausibility_status": "review"})
    _write_json(n7b2 / "GO2_CONTACT_SMOOTHING_REPORT.json", {"uncertain_ratio_before": 0.0, "uncertain_ratio_after": 0.0})
    _write_json(n7b2 / "GO2_CONTACT_VELOCITY_SEGMENT_REVIEW.json", {"readiness_status": "acceptable", "velocity_consistency_by_contact_state": {"walking_contact": {"count": 40, "velocity_diff_rmse_to_receiver": 1.0}}})
    _write_json(n7b2 / "N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json", {"status": "contact_still_not_ready"})


def _check_no_forbidden_artifacts() -> None:
    proc = _run(["git", "ls-files"])
    for line in proc.stdout.splitlines():
        lower = line.lower()
        if any(token in line for token in ["by2.txt", "GO2_BODY_STATE_STANDARDIZED.csv", "GO2_CONTACT_STATE_V2_TIMESERIES.csv"]):
            _fail(f"forbidden tracked artifact: {line}")
        if lower.endswith((".png", ".pdf", ".svg", ".jpg", ".jpeg")):
            _fail(f"forbidden tracked figure: {line}")


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            _fail(f"required file missing: {rel}")
    text = "\n".join((ROOT / rel).read_text(encoding="utf-8", errors="ignore") for rel in REQUIRED_FILES)
    for token in [
        "current_roll_pitch_std_deg",
        "parity_to_final_v23",
        "cross_source_consistency",
        "all_contact_suspect",
        "contact_v2_not_ready",
        "go2_velocity_prior_enabled",
        "go2_yaw_prior_enabled",
        "paper_performance_claim",
        "fgo",
    ]:
        if token not in text:
            _fail(f"required N7B2A token missing: {token}")
    with tempfile.TemporaryDirectory(prefix="legsa_n7b2a_toy_") as tmp:
        root = Path(tmp)
        _prepare_runtime(root)
        proc = _run(
            [
                sys.executable,
                "scripts/experiments/run_n7b2a_go2_metric_contact_visual_audit.py",
                "--n7a-root",
                str(root / "n7a"),
                "--n7b-root",
                str(root / "n7b"),
                "--n7b2-root",
                str(root / "n7b2"),
                "--output-dir",
                str(root / "out"),
                "--figure-output-dir",
                str(root / "fig"),
                "--allow-run",
            ],
            timeout=60,
        )
        if proc.returncode != 0:
            _fail(proc.stdout + proc.stderr)
        for name in REQUIRED_OUTPUTS:
            if not (root / "out" / name).exists():
                _fail(f"runtime output missing: {name}")
        decision = json.loads((root / "out/N7B2A_GO2_METRIC_CONTACT_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("status") != "contact_v2_not_ready":
            _fail(f"unexpected decision status: {decision.get('status')}")
        if decision.get("go2_velocity_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("fgo"):
            _fail("forbidden solver activation in decision")
        manifest = json.loads((root / "out/N7B2A_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if not manifest.get("required_figures_generated") or not manifest.get("required_figures_nonempty"):
            _fail("required N7B2A figures missing/nonempty false")
    _check_no_forbidden_artifacts()
    print("audit_n7b2a_go2_metric_contact_visual_audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
