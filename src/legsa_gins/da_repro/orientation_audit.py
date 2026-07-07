"""Orientation audit helpers for DA01R2A."""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import percentile, read_csv_rows, rmse, wrap180, wrap360


@dataclass(frozen=True)
class BaselineVector:
    time: float
    east_m: float
    north_m: float
    up_m: float
    source: str

    @property
    def length_m(self) -> float:
        return math.sqrt(self.east_m**2 + self.north_m**2 + self.up_m**2)

    @property
    def heading_enu_deg(self) -> float:
        return wrap360(math.degrees(math.atan2(self.east_m, self.north_m)))

    def reversed(self, *, source: str | None = None) -> "BaselineVector":
        return BaselineVector(
            time=self.time,
            east_m=-self.east_m,
            north_m=-self.north_m,
            up_m=-self.up_m,
            source=source or f"reversed_{self.source}",
        )


def heading_from_vector(east_m: float, north_m: float, *, coordinate_variant: str = "ENU") -> float:
    """Return heading degrees clockwise from north for deterministic variants."""

    if coordinate_variant == "ENU":
        return wrap360(math.degrees(math.atan2(east_m, north_m)))
    if coordinate_variant == "NED_NE":
        return wrap360(math.degrees(math.atan2(east_m, north_m)))
    if coordinate_variant == "AXIS_SWAPPED_EN":
        return wrap360(math.degrees(math.atan2(north_m, east_m)))
    if coordinate_variant == "NED_SIGN_FLIPPED":
        return wrap360(math.degrees(math.atan2(-east_m, north_m)))
    raise ValueError(f"unsupported coordinate_variant={coordinate_variant}")


def body_yaw_candidate(east_m: float, north_m: float, *, coordinate_variant: str, lateral_offset_deg: float) -> float:
    return wrap360(heading_from_vector(east_m, north_m, coordinate_variant=coordinate_variant) + lateral_offset_deg)


def load_raw_baseline_vectors(epoch_output: str | Path, *, source: str = "raw_full_backend_gnss2_minus_gnss1") -> list[BaselineVector]:
    vectors: list[BaselineVector] = []
    for row in read_csv_rows(epoch_output):
        try:
            vectors.append(
                BaselineVector(
                    time=float(row["timestamp"]),
                    east_m=float(row["baseline_east_m"]),
                    north_m=float(row["baseline_north_m"]),
                    up_m=float(row.get("baseline_up_m", 0.0)),
                    source=source,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return vectors


def _nearest(vectors: list[BaselineVector], t: float) -> tuple[BaselineVector, float] | None:
    if not vectors:
        return None
    times = [vector.time for vector in vectors]
    index = bisect.bisect_left(times, t)
    candidates: list[BaselineVector] = []
    if index < len(vectors):
        candidates.append(vectors[index])
    if index > 0:
        candidates.append(vectors[index - 1])
    if not candidates:
        return None
    best = min(candidates, key=lambda vector: abs(vector.time - t))
    return best, t - best.time


def vector_dot_angle_deg(a: BaselineVector, b: BaselineVector) -> tuple[float, float]:
    dot = a.east_m * b.east_m + a.north_m * b.north_m + a.up_m * b.up_m
    denom = a.length_m * b.length_m
    if denom <= 0.0:
        return math.nan, math.nan
    cosine = max(-1.0, min(1.0, dot / denom))
    return cosine, math.degrees(math.acos(cosine))


def compare_raw_to_status(
    raw_vectors: list[BaselineVector],
    status_vectors: list[BaselineVector],
    *,
    max_dt_sec: float = 0.60,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status_sorted = sorted(status_vectors, key=lambda vector: vector.time)
    rows: list[dict[str, Any]] = []
    for raw in sorted(raw_vectors, key=lambda vector: vector.time):
        match = _nearest(status_sorted, raw.time)
        if match is None:
            continue
        status, dt = match
        if abs(dt) > max_dt_sec:
            continue
        dot, angle = vector_dot_angle_deg(raw, status)
        heading_residual = wrap180(raw.heading_enu_deg - status.heading_enu_deg)
        rows.append(
            {
                "time": raw.time,
                "dt_sec": dt,
                "raw_heading_enu_deg": raw.heading_enu_deg,
                "status_heading_enu_deg": status.heading_enu_deg,
                "heading_residual_raw_minus_status_deg": heading_residual,
                "abs_heading_residual_deg": abs(heading_residual),
                "raw_length_m": raw.length_m,
                "status_length_m": status.length_m,
                "dot_product_unit": dot,
                "vector_angle_diff_deg": angle,
                "raw_east_m": raw.east_m,
                "raw_north_m": raw.north_m,
                "raw_up_m": raw.up_m,
                "status_east_m": status.east_m,
                "status_north_m": status.north_m,
                "status_up_m": status.up_m,
            }
        )
    angle_values = [float(row["vector_angle_diff_deg"]) for row in rows if math.isfinite(float(row["vector_angle_diff_deg"]))]
    residual_values = [float(row["abs_heading_residual_deg"]) for row in rows]
    dot_values = [float(row["dot_product_unit"]) for row in rows if math.isfinite(float(row["dot_product_unit"]))]
    summary = {
        "aligned_epoch_count": len(rows),
        "median_abs_heading_residual_deg": percentile(residual_values, 0.50),
        "p95_abs_heading_residual_deg": percentile(residual_values, 0.95),
        "median_vector_angle_diff_deg": percentile(angle_values, 0.50),
        "p95_vector_angle_diff_deg": percentile(angle_values, 0.95),
        "median_unit_dot_product": percentile(dot_values, 0.50),
        "direction_stable_against_status": bool(rows)
        and (percentile(residual_values, 0.95) or 999.0) < 30.0
        and (percentile(angle_values, 0.95) or 999.0) < 30.0,
    }
    return rows, summary


def baseline_summary(vectors: list[BaselineVector], *, label: str) -> dict[str, Any]:
    lengths = [vector.length_m for vector in vectors]
    headings = [vector.heading_enu_deg for vector in vectors]
    east = [vector.east_m for vector in vectors]
    north = [vector.north_m for vector in vectors]
    up = [vector.up_m for vector in vectors]
    return {
        "baseline_label": label,
        "epoch_count": len(vectors),
        "median_east_m": percentile(east, 0.50),
        "median_north_m": percentile(north, 0.50),
        "median_up_m": percentile(up, 0.50),
        "median_length_m": percentile(lengths, 0.50),
        "p05_length_m": percentile(lengths, 0.05),
        "p95_length_m": percentile(lengths, 0.95),
        "median_heading_enu_deg": percentile(headings, 0.50),
        "p05_heading_enu_deg": percentile(headings, 0.05),
        "p95_heading_enu_deg": percentile(headings, 0.95),
    }


def load_trace_yaw(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(path):
        try:
            rows.append({"time": float(row["time"]), "yaw_deg": float(row["yaw"])})
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda row: row["time"])
    return rows


def evaluate_candidates_against_trace(
    vectors: list[BaselineVector],
    trace_rows: list[dict[str, float]],
    *,
    vector_order: str,
    coordinate_variant: str,
    lateral_offset_deg: float,
    max_dt_sec: float = 0.10,
) -> dict[str, Any]:
    trace_times = [row["time"] for row in trace_rows]
    errors: list[float] = []
    for vector in vectors:
        east, north = vector.east_m, vector.north_m
        if vector_order == "GNSS1-GNSS2":
            east, north = -east, -north
        yaw = body_yaw_candidate(east, north, coordinate_variant=coordinate_variant, lateral_offset_deg=lateral_offset_deg)
        index = bisect.bisect_left(trace_times, vector.time)
        candidates: list[dict[str, float]] = []
        if index < len(trace_rows):
            candidates.append(trace_rows[index])
        if index > 0:
            candidates.append(trace_rows[index - 1])
        if not candidates:
            continue
        best = min(candidates, key=lambda row: abs(row["time"] - vector.time))
        if abs(best["time"] - vector.time) <= max_dt_sec:
            errors.append(wrap180(yaw - best["yaw_deg"]))
    abs_errors = [abs(error) for error in errors]
    return {
        "vector_order": vector_order,
        "coordinate_variant": coordinate_variant,
        "lateral_offset_deg": lateral_offset_deg,
        "trace_aligned_count": len(errors),
        "trace_yaw_rmse_deg": rmse(errors),
        "trace_yaw_p95_abs_deg": percentile(abs_errors, 0.95),
        "trace_yaw_max_abs_deg": max(abs_errors) if abs_errors else None,
        "trace_used_for_selection": False,
    }


def transform_candidate_rows(raw_vectors: list[BaselineVector], status_vectors: list[BaselineVector]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status_heading = percentile([vector.heading_enu_deg for vector in status_vectors], 0.50)
    status_body_plus90 = wrap360((status_heading or 0.0) + 90.0)
    for vector_order in ("GNSS2-GNSS1", "GNSS1-GNSS2"):
        for coordinate_variant in ("ENU", "NED_NE", "AXIS_SWAPPED_EN", "NED_SIGN_FLIPPED"):
            transformed_headings: list[float] = []
            transformed_body_yaws: dict[float, list[float]] = {90.0: [], -90.0: [], 0.0: [], 180.0: []}
            for raw in raw_vectors:
                east, north = raw.east_m, raw.north_m
                if vector_order == "GNSS1-GNSS2":
                    east, north = -east, -north
                heading = heading_from_vector(east, north, coordinate_variant=coordinate_variant)
                transformed_headings.append(heading)
                for offset in transformed_body_yaws:
                    transformed_body_yaws[offset].append(wrap360(heading + offset))
            median_heading = percentile(transformed_headings, 0.50)
            heading_residual = wrap180((median_heading or 0.0) - (status_heading or 0.0))
            for offset, yaws in transformed_body_yaws.items():
                median_body = percentile(yaws, 0.50)
                rows.append(
                    {
                        "vector_order": vector_order,
                        "coordinate_variant": coordinate_variant,
                        "lateral_offset_deg": offset,
                        "raw_candidate_median_heading_deg": median_heading,
                        "status_median_heading_deg": status_heading,
                        "raw_vs_status_heading_residual_deg": heading_residual,
                        "abs_raw_vs_status_heading_residual_deg": abs(heading_residual),
                        "raw_candidate_median_body_yaw_deg": median_body,
                        "status_body_yaw_plus90_deg": status_body_plus90,
                        "body_yaw_residual_vs_status_plus90_deg": wrap180((median_body or 0.0) - status_body_plus90),
                        "selection_source": "physical_status_raw_consistency_not_trace",
                        "trace_used_for_selection": False,
                    }
                )
    return rows
