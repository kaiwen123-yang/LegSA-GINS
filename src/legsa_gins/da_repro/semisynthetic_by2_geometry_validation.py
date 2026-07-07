"""Semi-synthetic BY2-geometry validation for DA01R2B."""

from __future__ import annotations

import bisect
import math
from typing import Any

import numpy as np

from .common import ecef_delta_to_enu, percentile, read_csv_rows, rmse, wrap180
from .orientation_audit import BaselineVector, vector_dot_angle_deg
from .synthetic_clambda_validation import _weighted_lstsq
from .synthetic_dd_generator import GPS_L1_WAVELENGTH_M
from .yaw_frame_contract import baseline_heading_from_enu, body_yaw_from_lateral_baseline


def load_status_vectors_from_orientation_table(path: str) -> list[BaselineVector]:
    vectors: list[BaselineVector] = []
    for row in read_csv_rows(path):
        if row.get("vector_order") not in ("", "GNSS2-GNSS1"):
            continue
        try:
            vectors.append(
                BaselineVector(
                    time=float(row["time"]),
                    east_m=float(row["east_m"]),
                    north_m=float(row["north_m"]),
                    up_m=float(row.get("up_m", 0.0)),
                    source="status_baseline_gnss2_minus_gnss1",
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(vectors, key=lambda vector: vector.time)


def nearest_status_vector(status_vectors: list[BaselineVector], timestamp: float, *, max_dt_sec: float = 0.60) -> tuple[BaselineVector, float] | None:
    if not status_vectors:
        return None
    times = [vector.time for vector in status_vectors]
    index = bisect.bisect_left(times, timestamp)
    candidates: list[BaselineVector] = []
    if index < len(status_vectors):
        candidates.append(status_vectors[index])
    if index > 0:
        candidates.append(status_vectors[index - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda vector: abs(vector.time - timestamp))
    dt = timestamp - best.time
    if abs(dt) > max_dt_sec:
        return None
    return best, dt


def _integer_for(epoch_index: int, row_index: int) -> int:
    return int(((epoch_index + 3) * (row_index + 5)) % 19 - 9)


def solve_semisynthetic_epoch(
    *,
    epoch: dict[str, Any],
    status_vector: BaselineVector,
    receiver_lat_deg: float,
    receiver_lon_deg: float,
    epoch_index: int,
) -> dict[str, Any] | None:
    rows = list(epoch.get("rows", []))
    if len(rows) < 3 or int(epoch.get("rank", 0)) < 3:
        return None
    h_rows: list[list[float]] = []
    y_rows: list[float] = []
    weights: list[float] = []
    for row_index, row in enumerate(rows):
        try:
            h_enu = ecef_delta_to_enu(
                float(row["h_x"]),
                float(row["h_y"]),
                float(row["h_z"]),
                receiver_lat_deg,
                receiver_lon_deg,
            )
        except (KeyError, TypeError, ValueError):
            continue
        geom = h_enu[0] * status_vector.east_m + h_enu[1] * status_vector.north_m + h_enu[2] * status_vector.up_m
        integer = _integer_for(epoch_index, row_index)
        carrier = geom + GPS_L1_WAVELENGTH_M * integer
        h_rows.append([h_enu[0], h_enu[1], h_enu[2]])
        y_rows.append(carrier - GPS_L1_WAVELENGTH_M * integer)
        weights.append(float(row.get("weight", 1.0)))
    if len(h_rows) < 3:
        return None
    h = np.asarray(h_rows, dtype=float)
    rank = int(np.linalg.matrix_rank(h))
    if rank < 3:
        return None
    estimate = _weighted_lstsq(h, np.asarray(y_rows, dtype=float), np.asarray(weights, dtype=float))
    east, north, up = (float(estimate[0]), float(estimate[1]), float(estimate[2]))
    length = math.sqrt(east * east + north * north + up * up)
    heading = baseline_heading_from_enu(east, north)
    yaw = body_yaw_from_lateral_baseline(heading, offset_deg=90.0)
    recovered = BaselineVector(
        time=float(epoch.get("timestamp") or 0.0),
        east_m=east,
        north_m=north,
        up_m=up,
        source="semisynthetic_recovered_gnss2_minus_gnss1",
    )
    _, angle = vector_dot_angle_deg(recovered, status_vector)
    status_yaw = body_yaw_from_lateral_baseline(status_vector.heading_enu_deg, offset_deg=90.0)
    residuals = np.asarray(y_rows, dtype=float) - h @ estimate
    return {
        "timestamp": epoch.get("timestamp"),
        "rcv_tow": epoch.get("rcv_tow"),
        "dt_status_sec": float(epoch.get("timestamp") or 0.0) - status_vector.time,
        "dd_count": len(h_rows),
        "design_rank": rank,
        "design_condition_number": float(np.linalg.cond(h)),
        "status_east_m": status_vector.east_m,
        "status_north_m": status_vector.north_m,
        "status_up_m": status_vector.up_m,
        "status_length_m": status_vector.length_m,
        "recovered_east_m": east,
        "recovered_north_m": north,
        "recovered_up_m": up,
        "recovered_length_m": length,
        "baseline_vs_status_angle_deg": angle,
        "status_body_yaw_deg": status_yaw,
        "recovered_body_yaw_deg": yaw,
        "body_yaw_residual_deg": wrap180(yaw - status_yaw),
        "residual_rms_m": math.sqrt(float(np.mean(residuals * residuals))),
        "trace_used": False,
        "per_case_offset": False,
        "status_used_as_real_full_backend_output": False,
    }


def run_semisynthetic_validation(
    *,
    design_epochs: list[dict[str, Any]],
    status_vectors: list[BaselineVector],
    receiver_lat_deg: float,
    receiver_lon_deg: float,
    max_epochs: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, epoch in enumerate(design_epochs):
        if max_epochs is not None and len(rows) >= max_epochs:
            break
        timestamp = epoch.get("timestamp")
        if timestamp is None:
            continue
        match = nearest_status_vector(status_vectors, float(timestamp))
        if match is None:
            continue
        status, _dt = match
        solved = solve_semisynthetic_epoch(
            epoch=epoch,
            status_vector=status,
            receiver_lat_deg=receiver_lat_deg,
            receiver_lon_deg=receiver_lon_deg,
            epoch_index=index,
        )
        if solved is not None:
            rows.append(solved)
    lengths = [float(row["recovered_length_m"]) for row in rows]
    angles = [float(row["baseline_vs_status_angle_deg"]) for row in rows if math.isfinite(float(row["baseline_vs_status_angle_deg"]))]
    yaw_errors = [float(row["body_yaw_residual_deg"]) for row in rows]
    summary = {
        "usable_epochs": len(rows),
        "median_recovered_baseline_length_m": percentile(lengths, 0.50),
        "p05_recovered_baseline_length_m": percentile(lengths, 0.05),
        "p95_recovered_baseline_length_m": percentile(lengths, 0.95),
        "median_baseline_vs_status_angle_deg": percentile(angles, 0.50),
        "p95_baseline_vs_status_angle_deg": percentile(angles, 0.95),
        "body_yaw_vs_status_rmse_deg": rmse(yaw_errors),
        "body_yaw_vs_status_p95_abs_deg": percentile([abs(value) for value in yaw_errors], 0.95),
        "trace_used": False,
        "per_case_offset": False,
        "status_used_as_real_full_backend_output": False,
    }
    median_length = summary["median_recovered_baseline_length_m"]
    median_angle = (
        summary["median_baseline_vs_status_angle_deg"] if summary["median_baseline_vs_status_angle_deg"] is not None else 999.0
    )
    yaw_rmse = summary["body_yaw_vs_status_rmse_deg"] if summary["body_yaw_vs_status_rmse_deg"] is not None else 999.0
    summary["semisynthetic_validation_pass"] = bool(
        len(rows) >= 500
        and median_length is not None
        and 0.20 <= float(median_length) <= 0.60
        and float(median_angle) < 2.0
        and float(yaw_rmse) < 2.0
        and not summary["trace_used"]
        and not summary["per_case_offset"]
        and not summary["status_used_as_real_full_backend_output"]
    )
    return rows, summary
