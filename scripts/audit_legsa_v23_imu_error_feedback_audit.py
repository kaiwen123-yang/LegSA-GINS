#!/usr/bin/env python3
"""Audit N4H4D6 IMU error feedback / compensation diagnostics."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

MODULES = [
    "src/legsa_gins/evaluation/legsa_v23_imu_error_feedback_audit.py",
    "src/legsa_gins/evaluation/legsa_v23_imu_compensation_timing.py",
    "src/legsa_gins/evaluation/legsa_v23_covariance_unit_parity.py",
    "src/legsa_gins/evaluation/legsa_v23_bias_scale_variant_matrix.py",
    "src/legsa_gins/evaluation/legsa_v23_d6_decision.py",
    "scripts/experiments/run_legsa_v23_imu_error_feedback_audit.py",
]

DOCS = [
    "docs/experiments/n4h4d6_imu_error_feedback_audit.md",
    "docs/experiments/n4h4d6_imu_compensation_timing.md",
    "docs/experiments/n4h4d6_covariance_unit_parity.md",
    "docs/experiments/n4h4d6_bias_scale_variant_matrix.md",
    "docs/experiments/n4h4d6_decision.md",
    "docs/codex_prompts/N4H4D6_imu_error_feedback_audit.md",
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_toy_inputs(root: Path) -> None:
    """中文说明：写 runtime-only toy clean 输入，不提交。"""

    root.mkdir(parents=True, exist_ok=True)
    imu_lines = []
    for index in range(80):
        time = index * 0.01
        imu_lines.append(f"{time:.2f} 0 0 0 0 0 -0.0980665")
    (root / "CLEAN_STATUS_YAW.imu").write_text("\n".join(imu_lines) + "\n", encoding="utf-8")
    gnss_lines = []
    for time in [0.01, 0.20, 0.40, 0.60]:
        gnss_lines.append(
            f"{time:.2f} 39.98482973 116.34312609 41.80208107 1 1 1 0 0 0 0.1 0.1 0.1 0.688505 1.5"
        )
    (root / "CLEAN_STATUS_YAW.gnss").write_text("\n".join(gnss_lines) + "\n", encoding="utf-8")
    rows = ["time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg"]
    for index in range(80):
        time = index * 0.01
        rows.append(f"{time:.2f},39.98482973,116.34312609,41.80208107,0,0,0,0,0,0.688505")
    (root / "EXTERNAL_EVAL_NAV.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _check_forbidden_flags(report_path: Path) -> None:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    for key in [
        "trace_solver_input",
        "final_v23_output_substitution",
        "output_only_correction",
        "bad_epoch_deletion_for_metric",
        "numerical_performance_claim",
    ]:
        _assert(data.get(key) is False, f"{report_path.name} must contain {key}=false")
    _assert(data.get("diagnostic_only") is True, f"{report_path.name} must be diagnostic_only")


def main() -> int:
    for rel in MODULES:
        _assert((REPO_ROOT / rel).exists(), f"missing module {rel}")
    for rel in DOCS:
        _assert((REPO_ROOT / rel).exists(), f"missing doc {rel}")
    demo = (REPO_ROOT / "cpp/legsa_v23_core/src/legsa_v23_core_demo.cpp").read_text(encoding="utf-8")
    for flag in [
        "--debug-imu-error-feedback",
        "--debug-imu-compensation",
        "--debug-cross-covariance",
        "--diagnostic-feedback-mode",
        "--diagnostic-covariance-mode",
    ]:
        _assert(flag in demo, f"missing C++ D6 flag {flag}")
    engine = (REPO_ROOT / "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp").read_text(encoding="utf-8")
    for name in ["recordDiagnosticImuCompensation", "recordDiagnosticImuErrorFeedback", "recordDiagnosticCrossCovariance"]:
        _assert(name in engine, f"missing C++ D6 diagnostic hook {name}")
    state_feedback = (REPO_ROOT / "cpp/legsa_v23_core/src/filter/state_feedback.cpp").read_text(encoding="utf-8")
    for mode in ["no_bias_feedback", "no_scale_feedback", "no_imu_error_feedback", "pos_vel_attitude_only"]:
        _assert(mode in state_feedback, f"missing D6 feedback mode {mode}")

    tmp = Path(tempfile.mkdtemp(prefix="legsa_n4h4d6_audit_"))
    try:
        clean = tmp / "clean"
        out = tmp / "out"
        _write_toy_inputs(clean)
        command = [
            sys.executable,
            "scripts/experiments/run_legsa_v23_imu_error_feedback_audit.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(clean),
            "--d5-root",
            str(tmp),
            "--output-dir",
            str(out),
            "--build-dir",
            str(tmp / "build"),
            "--exe",
            str(tmp / "build" / "legsa_v23_core_demo"),
            "--allow-run",
            "--run-bias-scale-variant-matrix",
            "--variant-timeout-s",
            "30",
            "--variant-workers",
            "2",
        ]
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        _assert(completed.returncode == 0, completed.stderr[-2000:] + completed.stdout[-2000:])
        for name in [
            "IMU_ERROR_FEEDBACK_AUDIT_REPORT.json",
            "IMU_COMPENSATION_TIMING_REPORT.json",
            "COVARIANCE_UNIT_PARITY_REPORT.json",
            "BIAS_SCALE_VARIANT_MATRIX_REPORT.json",
            "N4H4D6_DECISION_REPORT.json",
            "N4H4D6_IMU_ERROR_FEEDBACK_AUDIT_REPORT.json",
        ]:
            _assert((out / name).exists(), f"missing toy report {name}")
        for name in [
            "IMU_ERROR_FEEDBACK_TRACE.csv",
            "IMU_COMPENSATION_TRACE.csv",
            "CROSS_COVARIANCE_TRACE.csv",
            "IMU_ERROR_UNIT_SNAPSHOT.json",
        ]:
            _assert((out / "debug" / name).exists(), f"missing toy debug output {name}")
        _check_forbidden_flags(out / "N4H4D6_IMU_ERROR_FEEDBACK_AUDIT_REPORT.json")
        _check_forbidden_flags(out / "N4H4D6_DECISION_REPORT.json")
        matrix = json.loads((out / "BIAS_SCALE_VARIANT_MATRIX_REPORT.json").read_text(encoding="utf-8"))
        _assert(matrix.get("diagnostic_only") is True, "bias-scale matrix must be diagnostic_only")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tracked = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, check=True, capture_output=True, text=True).stdout
    forbidden_suffixes = ("input.gnss", ".imu", "summary.json", "error_series.csv", ".png", ".pdf", ".svg")
    offenders = [line for line in tracked.splitlines() if line.endswith(forbidden_suffixes)]
    _assert(not offenders, "generated artifact tracked: " + ", ".join(offenders[:5]))
    local_runtime_path = str(Path.home() / "legsa_" "n4h4d6_imu_error_feedback")
    grep = subprocess.run(
        ["git", "grep", "-n", local_runtime_path, "--", "."],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(grep.returncode != 0, "tracked local D6 runtime path leak")
    print("audit_legsa_v23_imu_error_feedback_audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

