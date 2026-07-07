"""Synthetic DA01R2B C-LAMBDA/DD/yaw-frame validation."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .common import percentile, rmse, wrap180, wrap360
from .lambda_solver import solve_integer_least_squares
from .synthetic_dd_generator import GPS_L1_WAVELENGTH_M, SyntheticDDCase, generate_synthetic_suite
from .yaw_frame_contract import baseline_heading_from_enu, body_yaw_from_lateral_baseline


def _weighted_lstsq(h: np.ndarray, y: np.ndarray, weights: np.ndarray) -> np.ndarray:
    sqrt_w = np.sqrt(np.maximum(weights, 1.0e-9))
    hw = h * sqrt_w[:, None]
    yw = y * sqrt_w
    return np.linalg.pinv(hw.T @ hw) @ hw.T @ yw


def vector_angle_deg(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    av = np.asarray(a, dtype=float)
    bv = np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom <= 0.0:
        return math.nan
    cosine = max(-1.0, min(1.0, float(av @ bv) / denom))
    return math.degrees(math.acos(cosine))


def solve_fixed_integer_baseline(case: SyntheticDDCase) -> dict[str, Any]:
    rows = list(case.rows)
    h = np.asarray([[row["h_east"], row["h_north"], row["h_up"]] for row in rows], dtype=float)
    y = np.asarray(
        [float(row["dd_carrier_m"]) - float(row["wavelength_m"]) * float(row["known_integer_ambiguity"]) for row in rows],
        dtype=float,
    )
    weights = np.asarray([row.get("weight", 1.0) for row in rows], dtype=float)
    estimate = _weighted_lstsq(h, y, weights)
    true_baseline = case.baseline_enu
    est_tuple = (float(estimate[0]), float(estimate[1]), float(estimate[2]))
    true_length = float(np.linalg.norm(np.asarray(true_baseline, dtype=float)))
    est_length = float(np.linalg.norm(estimate))
    heading = baseline_heading_from_enu(est_tuple[0], est_tuple[1])
    yaw = body_yaw_from_lateral_baseline(heading, offset_deg=90.0)
    yaw_residual = wrap180(yaw - case.body_yaw_deg)
    direction_error = vector_angle_deg(est_tuple, true_baseline)
    residuals = y - h @ estimate
    float_ambiguity = np.asarray(
        [
            (float(row["dd_carrier_m"]) - float(np.asarray([row["h_east"], row["h_north"], row["h_up"]], dtype=float) @ estimate))
            / float(row["wavelength_m"])
            for row in rows
        ],
        dtype=float,
    )
    covariance = np.eye(len(float_ambiguity)) * (0.04 if case.noise_std_m else 0.0001)
    lambda_result = solve_integer_least_squares(float_ambiguity, covariance, search_radius=1, max_candidates=64)
    known = tuple(int(row["known_integer_ambiguity"]) for row in rows)
    swapped_heading = baseline_heading_from_enu(-est_tuple[0], -est_tuple[1])
    swapped_yaw = body_yaw_from_lateral_baseline(swapped_heading, offset_deg=90.0)
    plus90_yaw = yaw
    minus90_yaw = body_yaw_from_lateral_baseline(heading, offset_deg=-90.0)
    return {
        "case_id": case.case_id,
        "body_yaw_deg": case.body_yaw_deg,
        "noise_std_m": case.noise_std_m,
        "satellite_count": len(rows) + 1,
        "dd_count": len(rows),
        "baseline_length_true_m": true_length,
        "baseline_length_est_m": est_length,
        "baseline_length_error_m": abs(est_length - true_length),
        "baseline_direction_error_deg": direction_error,
        "body_yaw_est_deg": yaw,
        "body_yaw_error_deg": yaw_residual,
        "body_yaw_abs_error_deg": abs(yaw_residual),
        "wrap_safe": abs(yaw_residual) <= 180.0,
        "swap_body_yaw_deg": swapped_yaw,
        "swap_delta_deg": abs(wrap180(swapped_yaw - yaw)),
        "swap_expected_180_pass": abs(abs(wrap180(swapped_yaw - yaw)) - 180.0) < 1.0e-9,
        "plus90_lateral_yaw_deg": plus90_yaw,
        "minus90_lateral_yaw_deg": minus90_yaw,
        "plus90_lateral_relation_pass": abs(wrap180(plus90_yaw - case.body_yaw_deg)) < 1.0,
        "minus90_relation_expected_180_deg": abs(abs(wrap180(minus90_yaw - plus90_yaw)) - 180.0) < 1.0e-9,
        "residual_rms_m": math.sqrt(float(np.mean(residuals * residuals))),
        "integer_solution": " ".join(str(v) for v in lambda_result.fixed),
        "known_integer_solution": " ".join(str(v) for v in known),
        "integer_solution_matches_known": lambda_result.fixed == known,
        "ambiguity_ratio": lambda_result.ratio,
        "trace_used": False,
    }


def validate_synthetic_suite(cases: list[SyntheticDDCase] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    suite = cases if cases is not None else generate_synthetic_suite()
    rows = [solve_fixed_integer_baseline(case) for case in suite]
    noise_free = [row for row in rows if float(row["noise_std_m"]) == 0.0]
    length_errors = [float(row["baseline_length_error_m"]) for row in rows]
    direction_errors_nf = [float(row["baseline_direction_error_deg"]) for row in noise_free]
    yaw_errors_nf = [float(row["body_yaw_abs_error_deg"]) for row in noise_free]
    wrap179 = [
        row
        for row in noise_free
        if float(row["body_yaw_deg"]) in (179.0, -179.0) and float(row["body_yaw_abs_error_deg"]) < 1.0
    ]
    summary = {
        "case_count": len(rows),
        "noise_free_case_count": len(noise_free),
        "max_length_error_m": max(length_errors) if length_errors else None,
        "max_noise_free_direction_error_deg": max(direction_errors_nf) if direction_errors_nf else None,
        "noise_free_yaw_rmse_deg": rmse([float(row["body_yaw_error_deg"]) for row in noise_free]),
        "max_noise_free_yaw_abs_error_deg": max(yaw_errors_nf) if yaw_errors_nf else None,
        "wrap_179_minus179_pass": len(wrap179) == 2,
        "swap_180_pass": all(row["swap_expected_180_pass"] for row in rows),
        "lateral_plus90_pass": all(row["plus90_lateral_relation_pass"] for row in noise_free),
        "integer_solution_matches_known": all(row["integer_solution_matches_known"] for row in noise_free),
        "trace_used": False,
    }
    max_length_error = summary["max_length_error_m"] if summary["max_length_error_m"] is not None else 999.0
    max_direction_error = (
        summary["max_noise_free_direction_error_deg"] if summary["max_noise_free_direction_error_deg"] is not None else 999.0
    )
    max_yaw_error = summary["max_noise_free_yaw_abs_error_deg"] if summary["max_noise_free_yaw_abs_error_deg"] is not None else 999.0
    summary["synthetic_validation_pass"] = bool(
        rows
        and max_length_error < 0.02
        and max_direction_error < 1.0
        and max_yaw_error < 1.0
        and summary["wrap_179_minus179_pass"]
        and summary["swap_180_pass"]
        and summary["lateral_plus90_pass"]
        and summary["integer_solution_matches_known"]
        and not summary["trace_used"]
    )
    summary["median_length_error_m"] = percentile(length_errors, 0.50)
    return rows, summary
