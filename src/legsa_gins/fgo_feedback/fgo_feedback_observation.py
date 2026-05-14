"""Build FGO terminal-state feedback observations for N8G."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .feedback_state_types import (
    FEEDBACK_OBSERVATION_COLUMNS,
    FeedbackObservation,
    NavStateSample,
    SlidingWindow,
    angle_delta_deg,
    norm,
    stats,
    wrap_degrees,
)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def local_ned_from_sample(sample: NavStateSample, origin: NavStateSample) -> tuple[float, float, float]:
    lat0 = math.radians(origin.lat_deg)
    meters_per_lat = 6378137.0
    meters_per_lon = 6378137.0 * math.cos(lat0)
    north = math.radians(sample.lat_deg - origin.lat_deg) * meters_per_lat
    east = math.radians(sample.lon_deg - origin.lon_deg) * meters_per_lon
    down = origin.height_m - sample.height_m
    return north, east, down


def _smoothed_terminal(window_samples: list[NavStateSample], terminal: NavStateSample) -> dict[str, float]:
    # 中文说明：foundation smoother 只做窗口内 terminal state 的保守弱平滑；
    # 它不是 output substitution，后续必须进入 EKF pseudo-measurement update。
    mean_vn = _mean([sample.vn_mps for sample in window_samples])
    mean_ve = _mean([sample.ve_mps for sample in window_samples])
    mean_vd = _mean([sample.vd_mps for sample in window_samples])
    mean_roll = terminal.roll_deg + _mean([angle_delta_deg(sample.roll_deg, terminal.roll_deg) for sample in window_samples])
    mean_pitch = terminal.pitch_deg + _mean([angle_delta_deg(sample.pitch_deg, terminal.pitch_deg) for sample in window_samples])
    mean_yaw = terminal.yaw_deg + _mean([angle_delta_deg(sample.yaw_deg, terminal.yaw_deg) for sample in window_samples])
    return {
        "vn": terminal.vn_mps + _clamp(0.35 * (mean_vn - terminal.vn_mps), 0.45),
        "ve": terminal.ve_mps + _clamp(0.35 * (mean_ve - terminal.ve_mps), 0.45),
        "vd": terminal.vd_mps + _clamp(0.20 * (mean_vd - terminal.vd_mps), 0.25),
        "roll": terminal.roll_deg + _clamp(0.30 * angle_delta_deg(mean_roll, terminal.roll_deg), 3.0),
        "pitch": terminal.pitch_deg + _clamp(0.30 * angle_delta_deg(mean_pitch, terminal.pitch_deg), 3.0),
        "yaw": wrap_degrees(terminal.yaw_deg + _clamp(0.25 * angle_delta_deg(mean_yaw, terminal.yaw_deg), 4.0)),
    }


def build_feedback_observations(
    samples: list[NavStateSample],
    windows: list[SlidingWindow],
    *,
    mode: str = "horizontal_velocity_attitude_feedback",
    origin: NavStateSample | None = None,
    residual_proxy_p95: float = 1.0,
) -> tuple[list[FeedbackObservation], dict[str, object]]:
    if not samples:
        raise ValueError("samples required")
    origin_sample = origin or samples[0]
    observations: list[FeedbackObservation] = []
    correction_norms: list[float] = []
    for window in windows:
        terminal = samples[window.sample_indices[-1]]
        window_samples = [samples[index] for index in window.sample_indices]
        smoothed = _smoothed_terminal(window_samples, terminal)
        pN, pE, pD = local_ned_from_sample(terminal, origin_sample)
        if "position" in mode:
            # Position feedback remains diagnostic in N8G and is deliberately tiny.
            mean_ned = [local_ned_from_sample(sample, origin_sample) for sample in window_samples]
            pN += _clamp(0.05 * (_mean([row[0] for row in mean_ned]) - pN), 1.0)
            pE += _clamp(0.05 * (_mean([row[1] for row in mean_ned]) - pE), 1.0)
            pD += _clamp(0.05 * (_mean([row[2] for row in mean_ned]) - pD), 0.6)
        vN = smoothed["vn"] if "velocity" in mode else terminal.vn_mps
        vE = smoothed["ve"] if "velocity" in mode else terminal.ve_mps
        vD = terminal.vd_mps if "horizontal_velocity" in mode else (smoothed["vd"] if "velocity" in mode else terminal.vd_mps)
        roll = smoothed["roll"] if "attitude" in mode else terminal.roll_deg
        pitch = smoothed["pitch"] if "attitude" in mode else terminal.pitch_deg
        yaw = smoothed["yaw"] if "attitude" in mode else terminal.yaw_deg
        inflation = max(1.0, min(6.0, 1.0 + 0.15 * float(residual_proxy_p95)))
        obs = FeedbackObservation(
            time=window.feedback_time,
            pN=pN,
            pE=pE,
            pD=pD,
            vN=vN,
            vE=vE,
            vD=vD,
            roll=roll,
            pitch=pitch,
            yaw=yaw,
            std_pN=3.0 * inflation,
            std_pE=3.0 * inflation,
            std_pD=4.0 * inflation,
            std_vN=0.45 * inflation,
            std_vE=0.45 * inflation,
            std_vD=0.80 * inflation,
            std_roll=2.5 * inflation,
            std_pitch=2.5 * inflation,
            std_yaw=3.5 * inflation,
            source_window_start=window.window_start,
            source_window_end=window.window_end,
            feedback_valid=window.no_future_data_verified,
            window_epoch_count=window.window_epoch_count,
            feedback_mode=mode,
        )
        correction_norms.append(
            norm(
                [
                    vN - terminal.vn_mps,
                    vE - terminal.ve_mps,
                    vD - terminal.vd_mps,
                    angle_delta_deg(roll, terminal.roll_deg),
                    angle_delta_deg(pitch, terminal.pitch_deg),
                    angle_delta_deg(yaw, terminal.yaw_deg),
                ]
            )
        )
        observations.append(obs)
    report: dict[str, object] = {
        "stage": "N8G",
        "feedback_rows": len(observations),
        "feedback_mode": mode,
        "state_blocks_included": {
            "position": "position" in mode,
            "velocity": "velocity" in mode,
            "attitude": "attitude" in mode,
            "horizontal_velocity_only": "horizontal_velocity" in mode,
        },
        "terminal_state_source": "sliding_window_no_feedback_fgo_terminal_state",
        "n8f_factor_stack_role": "activated_no_feedback_factor_stack",
        "no_output_substitution": True,
        "direct_nav_override": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "correction_norm_proxy": stats(correction_norms),
    }
    return observations, report


def write_feedback_observations(path: str | Path, observations: list[FeedbackObservation]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FEEDBACK_OBSERVATION_COLUMNS)
        writer.writeheader()
        for obs in observations:
            writer.writerow(obs.to_csv_row())


def write_observation_report(path: str | Path, report: dict[str, object]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
