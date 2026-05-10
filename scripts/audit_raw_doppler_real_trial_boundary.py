#!/usr/bin/env python3
"""Audit N5A real-trial blocker boundaries.

中文说明：真实 trial 必须在 provider 缺失或 update_count 为 0 时保留 blocker。
"""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOY_TRIAL = Path("/tmp/legsa_n5a_raw_doppler_audit_toy/N5A_RAW_DOPPLER_FACTOR_TRIAL_REPORT.json")


def _trial_report_path() -> Path:
    env = os.environ.get("N5A_REPORT_OUTPUT_DIR")
    if env:
        candidate = Path(env) / "N5A_RAW_DOPPLER_FACTOR_TRIAL_REPORT.json"
        if candidate.exists():
            return candidate
    if TOY_TRIAL.exists():
        return TOY_TRIAL
    raise AssertionError("N5A trial report missing; run readiness/trial or audit_n5a first")


def audit_report(path: Path) -> None:
    report = json.loads(path.read_text(encoding="utf-8"))
    rawx = report.get("rawx_found", False)
    eph = report.get("ephemeris_available", False)
    rtklib = report.get("rtklib_found", False)
    solver = report.get("solver_enabled", False)
    if rawx and eph and rtklib and not solver and not report.get("blocking_issue"):
        raise AssertionError("RAWX+ephemeris+RTKLIB with solver disabled must have blocking_issue")
    if solver and report.get("raw_doppler_update_count", 0) <= 0:
        raise AssertionError("solver_enabled=true requires raw_doppler_update_count > 0")
    for key in ("trace_solver_input", "final_v23_output_solver_input", "paper_performance_claim"):
        if report.get(key, False):
            raise AssertionError(f"{key} must be false")


def audit_static_boundaries() -> None:
    for path in [
        "CLAIM_BOUNDARY.md",
        "docs/experiments/n5a_trial_decision.md",
        "docs/experiments/n5a_satellite_state_provider_boundary.md",
    ]:
        text = (ROOT / path).read_text(encoding="utf-8")
        for needle in ["No trace solver input", "No final_v23 output solver input", "No paper performance claim"]:
            if needle not in text:
                raise AssertionError(f"{path} missing boundary: {needle}")


def main() -> int:
    audit_static_boundaries()
    audit_report(_trial_report_path())
    print("Raw Doppler real trial boundary audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
