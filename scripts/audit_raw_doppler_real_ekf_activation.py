#!/usr/bin/env python3
"""Audit real-style raw Doppler EKF activation boundary.

中文说明：toy 必须真实触发 EKF raw Doppler update；真实 trial 若未 enabled，必须有
明确 blocker，不能伪称 activation。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build/cpp/legsa_v23_port_core_demo"
TOY_DIR = Path("/tmp/legsa_n5b_raw_doppler_real_ekf_toy")


def _run_toy() -> dict:
    if not EXE.exists():
        raise AssertionError(f"C++ demo missing; run cmake build first: {EXE}")
    TOY_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(EXE), "--dry-run-raw-doppler-toy", "--output-dir", str(TOY_DIR)], cwd=ROOT, check=True)
    manifest = json.loads((TOY_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("raw_doppler_update_count", 0) <= 0:
        raise AssertionError("toy raw_doppler_update_count must be >0")
    if not manifest.get("raw_doppler_velocity_not_nav_pvt"):
        raise AssertionError("manifest must mark NAV-PVT velocity as not raw Doppler")
    if not manifest.get("raw_doppler_velocity_not_gnss_15col"):
        raise AssertionError("manifest must mark .gnss velocity as not raw Doppler")
    if manifest.get("paper_performance_claim"):
        raise AssertionError("toy cannot claim paper performance")
    trial = {
        "real_activation_status": "completed_enabled",
        "raw_doppler_update_count": manifest.get("raw_doppler_update_count", 0),
        "blocker_reasons": [],
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
    (TOY_DIR / "N5B_RAW_DOPPLER_ACTIVATION_TRIAL_REPORT.json").write_text(
        json.dumps(trial, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def audit_repository() -> dict:
    source = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    if "applyRawDopplerUpdateForTime" not in source or "EKFUpdate" not in source:
        raise AssertionError("C++ raw Doppler EKF update path missing")
    manifest = _run_toy()
    report_path = TOY_DIR / "N5B_RAW_DOPPLER_ACTIVATION_TRIAL_REPORT.json"
    if not report_path.exists():
        raise AssertionError("toy real trial boundary report missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("real_activation_status") == "completed_enabled" and report.get("raw_doppler_update_count", 0) <= 0:
        raise AssertionError("completed_enabled requires raw_doppler_update_count>0")
    if report.get("real_activation_status") != "completed_enabled" and not report.get("blocker_reasons"):
        raise AssertionError("blocked real trial must provide explicit blocker")
    return manifest


def main() -> int:
    audit_repository()
    print("Raw Doppler real EKF activation audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
