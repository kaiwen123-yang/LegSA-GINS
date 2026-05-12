#!/usr/bin/env python3
"""Audit N7B Go2 velocity/contact readiness.

中文说明：审计只跑 synthetic/runtime-only toy，不提交输出；同时检查 N7B 没有
启用 Go2 velocity/yaw prior、没有 FGO、没有 path leak。
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
    "src/legsa_gins/go2_prior/__init__.py",
    "src/legsa_gins/go2_prior/go2_contact_state.py",
    "src/legsa_gins/go2_prior/go2_velocity_quality.py",
    "src/legsa_gins/go2_prior/go2_motion_state.py",
    "src/legsa_gins/go2_prior/go2_yaw_rate_readiness.py",
    "src/legsa_gins/go2_prior/go2_contact_velocity_readiness.py",
    "src/legsa_gins/go2_prior/go2_n7b_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7b_decision.py",
    "scripts/experiments/run_n7b_go2_velocity_contact_readiness.py",
    "scripts/audit_go2_velocity_not_truth.py",
    "scripts/audit_go2_contact_readiness_boundaries.py",
    "docs/experiments/n7b_go2_velocity_contact_readiness.md",
    "docs/experiments/n7b_go2_contact_state_definition.md",
    "docs/experiments/n7b_go2_velocity_quality.md",
    "docs/experiments/n7b_go2_yaw_rate_readiness.md",
    "docs/experiments/n7b_decision.md",
    "docs/experiments/n7b_next_stage_plan.md",
    "docs/codex_prompts/N7B_go2_velocity_contact_readiness.md",
]

REQUIRED_OUTPUTS = [
    "GO2_CONTACT_STATE_REPORT.json",
    "GO2_CONTACT_STATE_TIMESERIES.csv",
    "GO2_VELOCITY_QUALITY_REPORT.json",
    "GO2_VELOCITY_QUALITY_TIMESERIES.csv",
    "GO2_MOTION_STATE_REPORT.json",
    "GO2_YAW_RATE_READINESS_REPORT.json",
    "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json",
    "N7B_FIGURE_MANIFEST.json",
    "n7b_go2_velocity_contact_case_review.md",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7b_go2_velocity_contact_readiness failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def _write_go2_csv(path: Path) -> None:
    fieldnames = [
        "time",
        "aligned_time",
        "roll_rad",
        "pitch_rad",
        "yaw_rad",
        "mode",
        "gait_type",
        "body_height",
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        *[f"foot_force_{index}" for index in range(4)],
        *[f"foot_position_body_{index}" for index in range(12)],
        *[f"foot_speed_body_{index}" for index in range(12)],
        "not_truth",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        yaw = 0.0
        for index in range(40):
            moving = index >= 15
            yaw += 0.03 if moving else 0.0
            speed = 0.45 if moving else 0.03
            row = {
                "time": index * 0.1,
                "aligned_time": index * 0.1,
                "roll_rad": 0.01,
                "pitch_rad": -0.02,
                "yaw_rad": yaw,
                "mode": "walk" if moving else "stand",
                "gait_type": 1 if moving else 0,
                "body_height": 0.32,
                "go2_velocity_0": speed,
                "go2_velocity_1": 0.02,
                "go2_velocity_2": 0.0,
                "yaw_speed_radps": 0.30 if moving else 0.0,
                "not_truth": True,
            }
            for foot in range(4):
                row[f"foot_force_{foot}"] = 28.0 if (not moving or foot % 2 == index % 2) else 4.0
            for item in range(12):
                row[f"foot_position_body_{item}"] = 0.0
                row[f"foot_speed_body_{item}"] = 0.02 if not moving else 0.10
            writer.writerow(row)


def _write_clean_gnss(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for index in range(40):
        time = index * 0.1
        speed = 0.45 if index >= 15 else 0.03
        cells = [time, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, speed, 0.02, 0.0, 0.1, 0.1, 0.1, 1.0, 1.0]
        lines.append(" ".join(str(value) for value in cells))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_raw_factor(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"],
        )
        writer.writeheader()
        for index in range(40):
            speed = 0.45 if index >= 15 else 0.03
            writer.writerow(
                {
                    "time": index * 0.1,
                    "vn": speed,
                    "ve": 0.02,
                    "vd": 0.0,
                    "std_vn": 0.2,
                    "std_ve": 0.2,
                    "std_vd": 0.2,
                    "sat_count": 12,
                    "provider_status": "ok",
                    "quality_flag": "usable",
                }
            )


def _check_no_path_leak() -> None:
    for token in [
        "/mnt/c/Users" + "/ykw/Desktop",
        "/mnt/c/Users" + "/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/" + "kaiwen/legsa_external_artifacts",
    ]:
        proc = _run(["git", "grep", "-n", token, "--", "."])
        if proc.returncode == 0:
            _fail(f"local path leak: {token}")


def _check_no_forbidden_artifacts() -> None:
    proc = _run(["git", "ls-files"])
    forbidden = [
        "by2.txt",
        "GO2_BODY_STATE_STANDARDIZED.csv",
        "GO2_ATTITUDE_WEAK_PRIORS.csv",
        "GO2_CONTACT_STATE_TIMESERIES.csv",
        "GO2_VELOCITY_QUALITY_TIMESERIES.csv",
    ]
    for line in proc.stdout.splitlines():
        lower = line.lower()
        if any(token in line for token in forbidden):
            _fail(f"forbidden tracked artifact: {line}")
        if lower.endswith((".ubx", ".obs", ".nav", ".sp3", ".clk", ".gnss", ".imu", ".png", ".pdf", ".svg", ".jpg", ".jpeg")):
            _fail(f"forbidden tracked artifact: {line}")


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            _fail(f"required file missing: {rel}")
    code = "\n".join((ROOT / rel).read_text(encoding="utf-8", errors="ignore") for rel in REQUIRED_FILES if rel.endswith((".py", ".md")))
    for token in [
        "Go2 velocity is not truth",
        "Cross-source velocity comparison is not truth error",
        "go2_velocity_prior_enabled",
        "go2_yaw_prior_enabled",
        "paper_performance_claim",
        "fgo",
    ]:
        if token not in code:
            _fail(f"boundary token missing: {token}")
    if "go2_velocity_prior_enabled\": True" in code or "go2_yaw_prior_enabled\": True" in code:
        _fail("N7B code enables forbidden Go2 velocity/yaw prior")
    with tempfile.TemporaryDirectory(prefix="legsa_n7b_toy_") as tmp:
        root = Path(tmp)
        _write_go2_csv(root / "n7a/GO2_BODY_STATE_STANDARDIZED.csv")
        (root / "n7a/GO2_WEAK_PRIOR_BUILD_REPORT.json").write_text('{"activation_allowed": true}\n', encoding="utf-8")
        _write_clean_gnss(root / "clean/input.gnss")
        _write_raw_factor(root / "n5b/RAW_DOPPLER_VELOCITY_FACTORS.csv")
        for folder in ["n5c", "n6b"]:
            (root / folder).mkdir(parents=True, exist_ok=True)
        proc = _run(
            [
                sys.executable,
                "scripts/experiments/run_n7b_go2_velocity_contact_readiness.py",
                "--n7a-root",
                str(root / "n7a"),
                "--n5b-root",
                str(root / "n5b"),
                "--n5c-root",
                str(root / "n5c"),
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
        decision = json.loads((root / "out/N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("go2_velocity_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("fgo"):
            _fail("decision enables forbidden N7B path")
        manifest = json.loads((root / "out/N7B_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if not manifest.get("required_figures_generated") or not manifest.get("required_figures_nonempty"):
            _fail("required N7B figures were not generated/nonempty")
    _check_no_path_leak()
    _check_no_forbidden_artifacts()
    print("audit_n7b_go2_velocity_contact_readiness passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
