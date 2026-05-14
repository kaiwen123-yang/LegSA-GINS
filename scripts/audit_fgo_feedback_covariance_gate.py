#!/usr/bin/env python3
"""Audit N8G conservative covariance and gate policy.

中文说明：审计 covariance/gate 只用 solver 可见量，不用 trace/final_v23 调参。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.fgo_feedback_covariance_policy import apply_conservative_covariance_policy
from legsa_gins.fgo_feedback.fgo_feedback_gate import apply_feedback_gate
from legsa_gins.fgo_feedback.fgo_feedback_observation import build_feedback_observations
from legsa_gins.fgo_feedback.sliding_window_manager import build_sliding_windows
from legsa_gins.fgo_feedback.feedback_state_types import NavStateSample


def _fail(message: str) -> None:
    raise SystemExit(f"audit_fgo_feedback_covariance_gate failed: {message}")


def main() -> int:
    root = Path(os.environ["N8G_REPORT_OUTPUT_DIR"]) if os.environ.get("N8G_REPORT_OUTPUT_DIR") else None
    if root and (root / "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json").exists():
        cov = json.loads((root / "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json").read_text(encoding="utf-8"))
        gate = json.loads((root / "FGO_FEEDBACK_GATE_REPORT.json").read_text(encoding="utf-8"))
        if cov.get("no_R_shrink") is not True or cov.get("no_trace_tuning") is not True:
            _fail("runtime covariance report boundary failed")
        if int(gate.get("accept_count", 0) or 0) + int(gate.get("reject_count", 0) or 0) <= 0:
            _fail("runtime gate did not evaluate observations")
    else:
        samples = [
            NavStateSample(float(i), 30.0, 120.0, 10.0, 1.0 + i * 0.01, 0.0, 0.0, 0.0, 0.0, 1.0 + i * 0.1)
            for i in range(8)
        ]
        windows, _ = build_sliding_windows(samples, candidate_feedback_times=[s.time for s in samples], window_duration_s=2.0)
        obs, _ = build_feedback_observations(samples, windows)
        obs, cov = apply_conservative_covariance_policy(obs)
        _, gate = apply_feedback_gate(obs, samples)
        if cov["conservative_inflation_factor"] < 1.0 or gate["accept_count"] <= 0:
            _fail("toy covariance/gate failed")
    print("audit_fgo_feedback_covariance_gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
