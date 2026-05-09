#!/usr/bin/env python3
"""Audit N4H4D4 trace parity and shadow measurement diagnostics.

中文说明：该审计只检查 D4 诊断模块、toy runtime 和 forbidden flags，
不提交 runtime artifact，也不把 shadow trace 当作 solver 输入。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

MODULES = [
    "src/legsa_gins/evaluation/legsa_v23_external_trace_parity.py",
    "src/legsa_gins/evaluation/legsa_v23_runtime_loop_parity.py",
    "src/legsa_gins/evaluation/legsa_v23_shadow_measurement_audit.py",
    "src/legsa_gins/evaluation/legsa_v23_gain_feedback_audit.py",
    "src/legsa_gins/evaluation/legsa_v23_first_divergence_locator.py",
    "src/legsa_gins/evaluation/legsa_v23_d4_decision.py",
    "scripts/experiments/run_legsa_v23_trace_parity_audit.py",
]

DOCS = [
    "docs/experiments/n4h4d4_external_trace_parity.md",
    "docs/experiments/n4h4d4_runtime_loop_parity.md",
    "docs/experiments/n4h4d4_shadow_measurement_audit.md",
    "docs/experiments/n4h4d4_gain_feedback_audit.md",
    "docs/experiments/n4h4d4_decision.md",
    "docs/codex_prompts/N4H4D4_trace_parity_shadow_audit.md",
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_toy_inputs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    imu_lines = []
    for index in range(30):
        time = index * 0.01
        imu_lines.append(f"{time:.2f} 0 0 0 0 0 -0.0980665")
    (root / "CLEAN_STATUS_YAW.imu").write_text("\n".join(imu_lines) + "\n", encoding="utf-8")
    gnss_lines = []
    for index, time in enumerate([0.01, 0.10, 0.20]):
        yaw = 0.688505
        gnss_lines.append(
            f"{time:.2f} 39.98482973 116.34312609 41.80208107 1 1 1 0 0 0 0.1 0.1 0.1 {yaw} 1.5"
        )
    (root / "CLEAN_STATUS_YAW.gnss").write_text("\n".join(gnss_lines) + "\n", encoding="utf-8")
    rows = ["time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg"]
    for index in range(30):
        time = index * 0.01
        rows.append(f"{time:.2f},39.98482973,116.34312609,41.80208107,0,0,0,0,0,0.688505")
    (root / "EXTERNAL_EVAL_NAV.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _check_flags(report_path: Path) -> None:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    for key in [
        "trace_solver_input",
        "final_v23_output_substitution",
        "output_only_correction",
        "bad_epoch_deletion_for_metric",
        "numerical_performance_claim",
        "shadow_external_nav_solver_input",
    ]:
        _assert(data.get(key) is False, f"{report_path.name} must contain {key}=false")


def main() -> int:
    for rel in MODULES:
        _assert((REPO_ROOT / rel).exists(), f"missing module {rel}")
    for rel in DOCS:
        _assert((REPO_ROOT / rel).exists(), f"missing doc {rel}")
    demo = (REPO_ROOT / "cpp/legsa_v23_core/src/legsa_v23_core_demo.cpp").read_text(encoding="utf-8")
    for flag in [
        "--debug-full-update-trace",
        "--debug-full-state-trace",
        "--debug-measurement-matrix-trace",
        "--debug-gain-trace",
        "--debug-max-rows",
    ]:
        _assert(flag in demo, f"missing C++ debug flag {flag}")

    tmp = Path(tempfile.mkdtemp(prefix="legsa_n4h4d4_audit_"))
    try:
        clean = tmp / "clean"
        out = tmp / "out"
        _write_toy_inputs(clean)
        command = [
            sys.executable,
            "scripts/experiments/run_legsa_v23_trace_parity_audit.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(clean),
            "--d1-root",
            str(tmp),
            "--d2-root",
            str(tmp),
            "--d3-root",
            str(tmp),
            "--output-dir",
            str(out),
            "--build-dir",
            str(tmp / "build"),
            "--exe",
            str(tmp / "build" / "legsa_v23_core_demo"),
            "--allow-run",
        ]
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        _assert(completed.returncode == 0, completed.stderr[-2000:] + completed.stdout[-2000:])
        for name in [
            "EXTERNAL_TRACE_PARITY_REPORT.json",
            "FIRST_DIVERGENCE_REPORT.json",
            "RUNTIME_LOOP_PARITY_REPORT.json",
            "SHADOW_MEASUREMENT_AUDIT_REPORT.json",
            "GAIN_FEEDBACK_AUDIT_REPORT.json",
            "N4H4D4_DECISION_REPORT.json",
        ]:
            _assert((out / name).exists(), f"missing toy report {name}")
        _check_flags(out / "N4H4D4_TRACE_PARITY_AUDIT_REPORT.json")
        _check_flags(out / "N4H4D4_DECISION_REPORT.json")
        debug = out / "debug"
        for name in [
            "ALL_UPDATES.csv",
            "ALL_STATES_1HZ.csv",
            "FIRST_DIVERGENCE_MARKERS.json",
            "RUNTIME_LOOP_PARITY_TRACE.json",
        ]:
            _assert((debug / name).exists(), f"missing C++ debug output {name}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tracked = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, check=True, capture_output=True, text=True).stdout
    forbidden_suffixes = ("input.gnss", ".imu", "summary.json", "error_series.csv", ".png", ".pdf", ".svg")
    offenders = [line for line in tracked.splitlines() if line.endswith(forbidden_suffixes)]
    _assert(not offenders, "generated artifact tracked: " + ", ".join(offenders[:5]))
    grep = subprocess.run(
        ["git", "grep", "-n", "/home/kaiwen/legsa_n4h4d4_trace_parity", "--", "."],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(grep.returncode != 0, "tracked local D4 runtime path leak")
    print("audit_legsa_v23_trace_parity_audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
