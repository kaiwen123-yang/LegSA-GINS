"""Solver-visible N8G feedback gate.

中文说明：gate 只使用 solver 可见 residual、窗口和时间信息，不读取评价真值调参。
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

from .feedback_state_types import (
    FeedbackGateThresholds,
    FeedbackObservation,
    NavStateSample,
    angle_delta_deg,
    finite_float,
    norm,
    stats,
)
from .fgo_feedback_observation import local_ned_from_sample


def _nearest_sample(samples: list[NavStateSample], time: float) -> NavStateSample:
    return min(samples, key=lambda sample: abs(sample.time - time))


def apply_feedback_gate(
    observations: list[FeedbackObservation],
    baseline_samples: list[NavStateSample],
    *,
    origin: NavStateSample | None = None,
    thresholds: FeedbackGateThresholds | None = None,
    position_enabled: bool = False,
    velocity_enabled: bool = True,
    attitude_enabled: bool = True,
    reject_all: bool = False,
) -> tuple[list[FeedbackObservation], dict[str, object]]:
    limits = thresholds or FeedbackGateThresholds()
    origin_sample = origin or baseline_samples[0]
    gated: list[FeedbackObservation] = []
    reasons: Counter[str] = Counter()
    pos_norms: list[float] = []
    vel_norms: list[float] = []
    att_norms: list[float] = []
    last_accept: float | None = None
    for obs in observations:
        sample = _nearest_sample(baseline_samples, obs.time)
        current_ned = local_ned_from_sample(sample, origin_sample)
        pos_norm = norm([obs.pN - current_ned[0], obs.pE - current_ned[1], obs.pD - current_ned[2]])
        vel_norm = norm([obs.vN - sample.vn_mps, obs.vE - sample.ve_mps, obs.vD - sample.vd_mps])
        att_norm = norm(
            [
                angle_delta_deg(obs.roll, sample.roll_deg),
                angle_delta_deg(obs.pitch, sample.pitch_deg),
                angle_delta_deg(obs.yaw, sample.yaw_deg),
            ]
        )
        yaw_abs = abs(angle_delta_deg(obs.yaw, sample.yaw_deg))
        pos_norms.append(pos_norm)
        vel_norms.append(vel_norm)
        att_norms.append(att_norm)
        reject_reason = ""
        finite = all(finite_float(getattr(obs, name)) for name in ["pN", "pE", "pD", "vN", "vE", "vD", "roll", "pitch", "yaw"])
        if reject_all:
            reject_reason = "reject_all_sanity"
        elif not obs.feedback_valid:
            reject_reason = "feedback_valid_false"
        elif not finite:
            reject_reason = "non_finite_observation"
        elif obs.source_window_end > obs.time + 1.0e-9:
            reject_reason = "future_data"
        elif obs.window_epoch_count < limits.min_window_epoch_count:
            reject_reason = "window_epoch_count_low"
        elif last_accept is not None and obs.time - last_accept < limits.min_interval_s - 1.0e-9:
            reject_reason = "min_interval"
        elif position_enabled and pos_norm > limits.max_position_correction_m:
            reject_reason = "position_correction_gate"
        elif velocity_enabled and vel_norm > limits.max_velocity_correction_mps:
            reject_reason = "velocity_correction_gate"
        elif attitude_enabled and att_norm > limits.max_attitude_correction_deg:
            reject_reason = "attitude_correction_gate"
        elif attitude_enabled and yaw_abs > limits.max_yaw_correction_deg:
            reject_reason = "yaw_correction_gate"
        accepted = reject_reason == ""
        if accepted:
            last_accept = obs.time
        else:
            reasons[reject_reason] += 1
        gated.append(replace(obs, feedback_valid=accepted))
    accept_count = sum(1 for obs in gated if obs.feedback_valid)
    reject_count = len(gated) - accept_count
    report: dict[str, object] = {
        "stage": "N8G",
        "feedback_count": len(gated),
        "accept_count": accept_count,
        "reject_count": reject_count,
        "reject_reasons": dict(reasons),
        "correction_norm_stats": {
            "position_m": stats(pos_norms),
            "velocity_mps": stats(vel_norms),
            "attitude_deg": stats(att_norms),
        },
        "gate_thresholds": {
            "max_position_correction_m": limits.max_position_correction_m,
            "max_velocity_correction_mps": limits.max_velocity_correction_mps,
            "max_attitude_correction_deg": limits.max_attitude_correction_deg,
            "max_yaw_correction_deg": limits.max_yaw_correction_deg,
            "min_interval_s": limits.min_interval_s,
            "min_window_epoch_count": limits.min_window_epoch_count,
        },
        "no_future_data": all(obs.source_window_end <= obs.time + 1.0e-9 for obs in gated),
        "no_trace_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return gated, report


def write_gate_report(path: str | Path, report: dict[str, object]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
