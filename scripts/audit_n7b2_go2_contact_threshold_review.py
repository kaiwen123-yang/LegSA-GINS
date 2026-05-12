#!/usr/bin/env python3
"""Audit N7B2 Go2 contact threshold review.

中文说明：审计使用 synthetic runtime-only toy 验证 N7B2 输出、figures 和边界；
不提交 runtime artifacts。
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
    "src/legsa_gins/go2_prior/go2_contact_distribution.py",
    "src/legsa_gins/go2_prior/go2_contact_threshold_review.py",
    "src/legsa_gins/go2_prior/go2_contact_state_v2.py",
    "src/legsa_gins/go2_prior/go2_contact_window_smoother.py",
    "src/legsa_gins/go2_prior/go2_contact_velocity_segment_review.py",
    "src/legsa_gins/go2_prior/go2_n7b2_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7b2_decision.py",
    "scripts/experiments/run_n7b2_go2_contact_threshold_review.py",
    "scripts/audit_go2_contact_threshold_no_trace_tuning.py",
    "scripts/audit_go2_contact_v2_no_solver_activation.py",
    "docs/experiments/n7b2_go2_contact_threshold_review.md",
    "docs/experiments/n7b2_contact_state_v2_definition.md",
    "docs/experiments/n7b2_contact_velocity_segment_review.md",
    "docs/experiments/n7b2_decision.md",
    "docs/experiments/n7b2_next_stage_plan.md",
    "docs/codex_prompts/N7B2_go2_contact_threshold_review.md",
]

REQUIRED_OUTPUTS = [
    "GO2_CONTACT_DISTRIBUTION_REPORT.json",
    "GO2_CONTACT_THRESHOLD_REVIEW_REPORT.json",
    "GO2_CONTACT_STATE_V2_REPORT.json",
    "GO2_CONTACT_STATE_V2_TIMESERIES.csv",
    "GO2_CONTACT_SMOOTHING_REPORT.json",
    "GO2_CONTACT_VELOCITY_SEGMENT_REVIEW.json",
    "N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json",
    "N7B2_FIGURE_MANIFEST.json",
    "n7b2_contact_threshold_case_review.md",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7b2_go2_contact_threshold_review failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def _write_go2_csv(path: Path) -> None:
    fields = [
        "time",
        "aligned_time",
        "mode",
        "gait_type",
        "body_height",
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        *[f"foot_force_{i}" for i in range(4)],
        *[f"foot_speed_body_{i}" for i in range(12)],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(48):
            moving = index >= 16
            row = {
                "time": index * 0.1,
                "aligned_time": index * 0.1,
                "mode": "walk" if moving else "stand",
                "gait_type": 1 if moving else 0,
                "body_height": 0.32,
                "go2_velocity_0": 0.45 if moving else 0.03,
                "go2_velocity_1": 0.02,
                "go2_velocity_2": 0.0,
                "yaw_speed_radps": 0.1 if moving else 0.0,
            }
            for foot in range(4):
                row[f"foot_force_{foot}"] = 34.0 if (not moving or foot % 2 == index % 2) else 5.0
            for axis in range(12):
                row[f"foot_speed_body_{axis}"] = 0.04 if not moving else 0.20
            writer.writerow(row)


def _write_clean(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{i * 0.1} 0 0 0 0 0 0 {0.45 if i >= 16 else 0.03} 0.02 0 0.1 0.1 0.1 1 1" for i in range(48)) + "\n", encoding="utf-8")


def _write_raw(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"])
        writer.writeheader()
        for index in range(48):
            writer.writerow({"time": index * 0.1, "vn": 0.45 if index >= 16 else 0.03, "ve": 0.02, "vd": 0.0, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 10, "provider_status": "ok", "quality_flag": "usable"})


def _write_n7b_contact(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row_index", "time", "contact_label", "contact_count"])
        writer.writeheader()
        for index in range(48):
            writer.writerow({"row_index": index, "time": index * 0.1, "contact_label": "swing_or_uncertain", "contact_count": 0})


def _check_no_forbidden_artifacts() -> None:
    proc = _run(["git", "ls-files"])
    for line in proc.stdout.splitlines():
        lower = line.lower()
        if any(token in line for token in ["by2.txt", "GO2_BODY_STATE_STANDARDIZED.csv", "GO2_CONTACT_STATE_V2_TIMESERIES.csv"]):
            _fail(f"forbidden tracked artifact: {line}")
        if lower.endswith((".ubx", ".obs", ".nav", ".sp3", ".clk", ".gnss", ".imu", ".png", ".pdf", ".svg", ".jpg", ".jpeg")):
            _fail(f"forbidden tracked artifact: {line}")


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            _fail(f"required file missing: {rel}")
    code = "\n".join((ROOT / rel).read_text(encoding="utf-8", errors="ignore") for rel in REQUIRED_FILES if rel.endswith((".py", ".md")))
    for token in [
        "go2_field_distribution_only",
        "Go2 velocity is not truth",
        "Contact-conditioned velocity comparison is not truth error",
        "go2_velocity_prior_enabled",
        "go2_yaw_prior_enabled",
        "paper_performance_claim",
        "fgo",
    ]:
        if token not in code:
            _fail(f"required boundary token missing: {token}")
    if "go2_velocity_prior_enabled\": True" in code or "go2_yaw_prior_enabled\": True" in code:
        _fail("forbidden prior activation token present")
    with tempfile.TemporaryDirectory(prefix="legsa_n7b2_toy_") as tmp:
        root = Path(tmp)
        _write_go2_csv(root / "n7a/GO2_BODY_STATE_STANDARDIZED.csv")
        _write_n7b_contact(root / "n7b/GO2_CONTACT_STATE_TIMESERIES.csv")
        (root / "n7b/GO2_CONTACT_STATE_REPORT.json").write_text('{"recommended_contact_quality_status": "review"}\n', encoding="utf-8")
        (root / "n7b/GO2_VELOCITY_QUALITY_REPORT.json").write_text('{"consistency_status": "acceptable_for_future_review"}\n', encoding="utf-8")
        (root / "n7b/N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json").write_text('{"status": "contact_not_ready"}\n', encoding="utf-8")
        _write_clean(root / "clean/input.gnss")
        _write_raw(root / "n5b/RAW_DOPPLER_VELOCITY_FACTORS.csv")
        (root / "n6b").mkdir()
        proc = _run(
            [
                sys.executable,
                "scripts/experiments/run_n7b2_go2_contact_threshold_review.py",
                "--n7a-root",
                str(root / "n7a"),
                "--n7b-root",
                str(root / "n7b"),
                "--n5b-root",
                str(root / "n5b"),
                "--n6b-root",
                str(root / "n6b"),
                "--clean-root",
                str(root / "clean"),
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
        decision = json.loads((root / "out/N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("go2_velocity_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("fgo"):
            _fail("N7B2 decision enabled forbidden solver path")
        manifest = json.loads((root / "out/N7B2_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if not manifest.get("required_figures_generated") or not manifest.get("required_figures_nonempty"):
            _fail("N7B2 required figures missing/nonempty false")
    _check_no_forbidden_artifacts()
    print("audit_n7b2_go2_contact_threshold_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
