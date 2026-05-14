#!/usr/bin/env python3
"""Audit N8G FGO feedback EKF foundation.

中文说明：若 runtime 报告存在则审计真实输出；否则运行内存 toy pipeline，
保证单元/集成测试不依赖本机 runtime 绝对路径。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo_feedback.feedback_state_types import FeedbackGateThresholds, NavStateSample
from legsa_gins.fgo_feedback.fgo_feedback_covariance_policy import apply_conservative_covariance_policy
from legsa_gins.fgo_feedback.fgo_feedback_decision import build_n8g_decision_report
from legsa_gins.fgo_feedback.fgo_feedback_gate import apply_feedback_gate
from legsa_gins.fgo_feedback.fgo_feedback_observation import build_feedback_observations
from legsa_gins.fgo_feedback.sliding_window_manager import build_sliding_windows


REQUIRED_REPORTS = [
    "SLIDING_WINDOW_MANAGER_REPORT.json",
    "FGO_FEEDBACK_OBSERVATION_BUILD_REPORT.json",
    "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json",
    "FGO_FEEDBACK_GATE_REPORT.json",
    "N8G_FGO_FEEDBACK_VARIANT_SUMMARIES.json",
    "N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8g_fgo_feedback_ekf_foundation failed: {message}")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def report_root() -> Path | None:
    value = os.environ.get("N8G_REPORT_OUTPUT_DIR")
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _audit_runtime(root: Path) -> None:
    for name in REQUIRED_REPORTS:
        if not (root / name).exists():
            _fail(f"missing runtime report {name}")
    decision = _json(root / "N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json")
    variant = _json(root / "N8G_FGO_FEEDBACK_VARIANT_SUMMARIES.json")
    window = _json(root / "SLIDING_WINDOW_MANAGER_REPORT.json")
    observation = _json(root / "FGO_FEEDBACK_OBSERVATION_BUILD_REPORT.json")
    if not window.get("no_future_data_verified"):
        _fail("sliding window no_future_data_verified is false")
    if int(observation.get("feedback_rows", 0) or 0) <= 0:
        _fail("no feedback observations generated")
    if int(variant.get("feedback_update_count_total", 0) or 0) <= 0:
        _fail("feedback did not enter EKF update according to variant report")
    for flag in ["fgo_feedback_output_substitution", "fgo_feedback_direct_nav_override", "trace_solver_input", "final_v23_output_solver_input", "paper_performance_claim"]:
        if decision.get(flag) is not False:
            _fail(f"decision boundary flag is not false: {flag}")


def _toy_samples() -> list[NavStateSample]:
    return [
        NavStateSample(
            time=float(index),
            lat_deg=30.0 + index * 1.0e-6,
            lon_deg=120.0 + index * 1.0e-6,
            height_m=10.0,
            vn_mps=1.0 + 0.02 * index,
            ve_mps=0.1,
            vd_mps=0.0,
            roll_deg=0.1 * index,
            pitch_deg=0.05 * index,
            yaw_deg=5.0 + 0.2 * index,
        )
        for index in range(12)
    ]


def _audit_toy() -> None:
    samples = _toy_samples()
    windows, window_report = build_sliding_windows(samples, candidate_feedback_times=[s.time for s in samples], window_duration_s=3.0, feedback_stride_s=1.0)
    observations, observation_report = build_feedback_observations(samples, windows, mode="horizontal_velocity_attitude_feedback")
    observations, covariance_report = apply_conservative_covariance_policy(observations)
    observations, gate_report = apply_feedback_gate(observations, samples, thresholds=FeedbackGateThresholds())
    variant_report = {
        "feedback_update_count_total": gate_report["accept_count"],
        "feedback_accept_count_total": gate_report["accept_count"],
        "feedback_reject_count_total": gate_report["reject_count"],
    }
    evaluation_report = {"gross_degradation_status": "absent"}
    decision = build_n8g_decision_report(observation_report=observation_report, variant_report=variant_report, evaluation_report=evaluation_report)
    if not window_report["no_future_data_verified"]:
        _fail("toy no_future_data failed")
    if not observations or gate_report["accept_count"] <= 0:
        _fail("toy feedback gate accepted no observations")
    if covariance_report["no_R_shrink"] is not True:
        _fail("covariance policy allowed R shrink")
    if decision["status"] != "fgo_feedback_ekf_foundation_ready":
        _fail(f"unexpected toy decision {decision['status']}")
    gi_engine = (ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp").read_text(encoding="utf-8")
    if "applyFgoFeedbackForTime" not in gi_engine or "EKFUpdate(dz, H, R)" not in gi_engine:
        _fail("C++ feedback EKFUpdate hook missing")


def main() -> int:
    root = report_root()
    if root is not None:
        _audit_runtime(root)
    else:
        _audit_toy()
    print("audit_n8g_fgo_feedback_ekf_foundation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
