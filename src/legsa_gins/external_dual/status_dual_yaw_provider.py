"""BY2 status-based dual-antenna yaw provider."""

from __future__ import annotations

import csv
import math
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

from .yaw_frame_adapter import baseline_heading_ned_deg, baseline_heading_to_body_yaw_ned_deg


@dataclass(frozen=True)
class DualYawEpoch:
    time: float
    gnss2_time: float
    dt_s: float
    baseline_n_m: float
    baseline_e_m: float
    baseline_d_m: float
    baseline_length_m: float
    rel_acc_m: float
    baseline_heading_deg: float
    body_yaw_deg: float
    valid: bool


def build_status_dual_yaw_provider(gnss1_status_path: Path, gnss2_status_path: Path, *, max_time_delta_s: float = 0.75) -> list[DualYawEpoch]:
    gnss1_rows = _read_status(gnss1_status_path)
    gnss2_rows = _read_status(gnss2_status_path)
    gnss2_times = [_as_float(row, "Time") for row in gnss2_rows]
    epochs: list[DualYawEpoch] = []
    for row1 in gnss1_rows:
        time1 = _as_float(row1, "Time")
        if math.isnan(time1):
            continue
        pos = bisect_left(gnss2_times, time1)
        candidates = []
        if pos < len(gnss2_rows):
            candidates.append(gnss2_rows[pos])
        if pos:
            candidates.append(gnss2_rows[pos - 1])
        if not candidates:
            continue
        row2 = min(candidates, key=lambda row: abs(_as_float(row, "Time") - time1))
        time2 = _as_float(row2, "Time")
        baseline_n = _as_float(row2, "rel_pos_n") - _as_float(row1, "rel_pos_n")
        baseline_e = _as_float(row2, "rel_pos_e") - _as_float(row1, "rel_pos_e")
        baseline_d = _as_float(row2, "rel_pos_d") - _as_float(row1, "rel_pos_d")
        length = math.sqrt(baseline_n**2 + baseline_e**2 + baseline_d**2)
        rel_acc = math.sqrt(
            sum(
                _as_float(row, key, 0.0) ** 2
                for row in (row1, row2)
                for key in ("rel_acc_n", "rel_acc_e", "rel_acc_d")
            )
        )
        heading = baseline_heading_ned_deg(baseline_n, baseline_e)
        valid = abs(time2 - time1) <= max_time_delta_s and _as_bool(row1, "rel_valid") and _as_bool(row2, "rel_valid") and _as_bool(row1, "fix_ok") and _as_bool(row2, "fix_ok") and length > 0.05
        epochs.append(
            DualYawEpoch(
                time=time1,
                gnss2_time=time2,
                dt_s=time2 - time1,
                baseline_n_m=baseline_n,
                baseline_e_m=baseline_e,
                baseline_d_m=baseline_d,
                baseline_length_m=length,
                rel_acc_m=rel_acc,
                baseline_heading_deg=heading,
                body_yaw_deg=baseline_heading_to_body_yaw_ned_deg(heading),
                valid=valid,
            )
        )
    return epochs


def summarize_status_provider(epochs: list[DualYawEpoch]) -> dict[str, str]:
    valid = [epoch for epoch in epochs if epoch.valid]
    lengths = [epoch.baseline_length_m for epoch in valid]
    rel_acc = [epoch.rel_acc_m for epoch in valid]
    return {
        "epoch_count": str(len(epochs)),
        "valid_epoch_count": str(len(valid)),
        "median_baseline_length_m": f"{_median(lengths):.6f}" if lengths else "not_available",
        "median_rel_acc_m": f"{_median(rel_acc):.6f}" if rel_acc else "not_available",
        "gnss2_minus_gnss1_convention": "true",
        "single_status_relpos_used_as_heading": "false",
        "lateral_plus90_policy": "true",
        "wrap_safe_residual": "true",
    }


def _read_status(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _as_float(row: dict[str, str], key: str, default: float = math.nan) -> float:
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return default


def _as_bool(row: dict[str, str], key: str) -> bool:
    return str(row.get(key, "")).strip().lower() in {"true", "1", "yes"}


def _median(values: list[float]) -> float:
    values = sorted(values)
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else 0.5 * (values[mid - 1] + values[mid])
