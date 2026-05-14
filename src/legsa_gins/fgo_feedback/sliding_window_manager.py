"""Sliding-window selection for N8G FGO feedback.

中文说明：窗口只使用 `time <= feedback_time` 的 EKF state stream，不删 epoch，
不读取 trace/final_v23 作为 solver 输入。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .feedback_state_types import NavStateSample, SlidingWindow


def read_eval_nav_csv(path: str | Path) -> list[NavStateSample]:
    rows: list[NavStateSample] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                NavStateSample(
                    time=float(row["time"]),
                    lat_deg=float(row["lat_deg"]),
                    lon_deg=float(row["lon_deg"]),
                    height_m=float(row["height_m"]),
                    vn_mps=float(row["vn"]),
                    ve_mps=float(row["ve"]),
                    vd_mps=float(row["vd"]),
                    roll_deg=float(row["roll_deg"]),
                    pitch_deg=float(row["pitch_deg"]),
                    yaw_deg=float(row["yaw_deg"]),
                )
            )
    if not rows:
        raise ValueError(f"EVAL_NAV has no rows: {path}")
    return rows


def read_first_column_times(path: str | Path) -> list[float]:
    times: list[float] = []
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                times.append(float(stripped.replace(",", " ").split()[0]))
            except (IndexError, ValueError):
                continue
    return times


def build_sliding_windows(
    samples: list[NavStateSample],
    *,
    candidate_feedback_times: Iterable[float] | None = None,
    window_duration_s: float = 5.0,
    feedback_stride_s: float = 1.0,
    min_epoch_count: int = 3,
) -> tuple[list[SlidingWindow], dict[str, object]]:
    if window_duration_s <= 0.0:
        raise ValueError("window_duration_s must be positive")
    if feedback_stride_s <= 0.0:
        raise ValueError("feedback_stride_s must be positive")
    sample_times = [sample.time for sample in samples]
    source_times = sorted(candidate_feedback_times or sample_times)
    windows: list[SlidingWindow] = []
    skipped: list[dict[str, object]] = []
    last_feedback_time: float | None = None
    for feedback_time in source_times:
        if feedback_time < sample_times[0] or feedback_time > sample_times[-1]:
            skipped.append({"feedback_time": feedback_time, "reason": "outside_state_stream"})
            continue
        if last_feedback_time is not None and feedback_time - last_feedback_time < feedback_stride_s - 1.0e-9:
            skipped.append({"feedback_time": feedback_time, "reason": "stride_hold"})
            continue
        window_start = feedback_time - window_duration_s
        indices = tuple(
            index for index, sample in enumerate(samples) if window_start <= sample.time <= feedback_time
        )
        if len(indices) < min_epoch_count:
            skipped.append({"feedback_time": feedback_time, "reason": "insufficient_epoch_count", "epoch_count": len(indices)})
            continue
        no_future = all(samples[index].time <= feedback_time + 1.0e-9 for index in indices)
        windows.append(
            SlidingWindow(
                feedback_time=feedback_time,
                window_start=max(window_start, sample_times[0]),
                window_end=feedback_time,
                sample_indices=indices,
                no_future_data_verified=no_future,
            )
        )
        last_feedback_time = feedback_time
    epoch_counts = [window.window_epoch_count for window in windows]
    report: dict[str, object] = {
        "stage": "N8G",
        "window_count": len(windows),
        "feedback_time": [window.feedback_time for window in windows],
        "window_start": [window.window_start for window in windows],
        "window_end": [window.window_end for window in windows],
        "window_epoch_count": epoch_counts,
        "window_duration_s": window_duration_s,
        "feedback_stride_s": feedback_stride_s,
        "no_future_data_verified": bool(windows) and all(window.no_future_data_verified for window in windows),
        "overlap_stats": {
            "min_epoch_count": min(epoch_counts) if epoch_counts else 0,
            "max_epoch_count": max(epoch_counts) if epoch_counts else 0,
            "candidate_feedback_time_count": len(source_times),
        },
        "skipped_windows": skipped,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return windows, report


def write_sliding_window_report(path: str | Path, report: dict[str, object]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
