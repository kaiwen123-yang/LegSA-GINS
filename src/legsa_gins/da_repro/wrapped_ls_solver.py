"""Wrapped least-squares baseline solver for Liu C-WLS DA03.

The implementation is intentionally scoped to the single-baseline BY2 setup.
It minimizes the carrier-phase wrapped residual on the known baseline-length
sphere, with code residuals used as an auxiliary weak term.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class WrappedLSSolution:
    baseline_vector_m: tuple[float, float, float]
    objective: float
    wrapped_phase_rms_cycles: float
    code_residual_rms_m: float
    integer_ambiguities: tuple[int, ...]
    candidate_count: int
    refinement_steps: int
    converged: bool


def special_round_half_down(values: np.ndarray) -> np.ndarray:
    """Round so that N + 0.5 maps to N, matching the C-WLS paper convention."""

    return np.ceil(values - 0.5)


def wrap_cycles(values: np.ndarray) -> np.ndarray:
    """Return residuals in (-0.5, 0.5] cycles."""

    return values - special_round_half_down(values)


def _weighted_lstsq(h: np.ndarray, y: np.ndarray, weights: np.ndarray) -> np.ndarray:
    sqrt_w = np.sqrt(np.maximum(weights, 1.0e-9))
    hw = h * sqrt_w[:, None]
    yw = y * sqrt_w
    return np.linalg.pinv(hw.T @ hw) @ hw.T @ yw


def _unit(vector: np.ndarray) -> np.ndarray | None:
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 1.0e-12:
        return None
    return vector / norm


def _project_to_length(vector: np.ndarray, baseline_length_m: float) -> np.ndarray | None:
    direction = _unit(vector)
    if direction is None:
        return None
    return direction * float(baseline_length_m)


def _fibonacci_directions(count: int) -> list[np.ndarray]:
    if count <= 0:
        return []
    directions: list[np.ndarray] = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for index in range(count):
        z = 1.0 - 2.0 * (index + 0.5) / count
        radius = math.sqrt(max(0.0, 1.0 - z * z))
        theta = golden * index
        directions.append(np.asarray([radius * math.cos(theta), radius * math.sin(theta), z], dtype=float))
    return directions


def _basis(direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ref = np.asarray([0.0, 0.0, 1.0], dtype=float)
    if abs(float(direction @ ref)) > 0.90:
        ref = np.asarray([0.0, 1.0, 0.0], dtype=float)
    u = np.cross(direction, ref)
    u = u / np.linalg.norm(u)
    v = np.cross(direction, u)
    v = v / np.linalg.norm(v)
    return u, v


def cwls_objective(
    *,
    baseline: np.ndarray,
    h: np.ndarray,
    carrier_m: np.ndarray,
    code_m: np.ndarray,
    wavelengths_m: np.ndarray,
    weights: np.ndarray,
    code_sigma_m: float = 1.0,
) -> tuple[float, np.ndarray, np.ndarray]:
    pred = h @ baseline
    phase_residual_cycles = wrap_cycles((carrier_m - pred) / wavelengths_m)
    code_residual_m = code_m - pred
    phase_term = np.sum(weights * phase_residual_cycles * phase_residual_cycles)
    code_term = np.sum(weights * (code_residual_m / float(code_sigma_m)) ** 2)
    return float(phase_term + code_term), phase_residual_cycles, code_residual_m


def solve_cwls_baseline(
    *,
    h_rows: list[list[float]] | np.ndarray,
    carrier_m: list[float] | np.ndarray,
    code_m: list[float] | np.ndarray,
    wavelengths_m: list[float] | np.ndarray,
    baseline_length_m: float,
    weights: list[float] | np.ndarray | None = None,
    grid_count: int = 384,
    refine_angles: int = 16,
    code_sigma_m: float = 1.0,
) -> WrappedLSSolution | None:
    h = np.asarray(h_rows, dtype=float)
    carrier = np.asarray(carrier_m, dtype=float)
    code = np.asarray(code_m, dtype=float)
    wavelengths = np.asarray(wavelengths_m, dtype=float)
    if weights is None:
        w = np.ones(len(carrier), dtype=float)
    else:
        w = np.asarray(weights, dtype=float)
    if h.ndim != 2 or h.shape[1] != 3 or h.shape[0] < 3:
        return None
    if not (len(carrier) == len(code) == len(wavelengths) == len(w) == h.shape[0]):
        return None
    if int(np.linalg.matrix_rank(h)) < 3:
        return None
    if not np.all(np.isfinite(h)) or not np.all(np.isfinite(carrier)) or not np.all(np.isfinite(code)):
        return None
    if not np.all(wavelengths > 0.0):
        return None

    candidates: list[np.ndarray] = []
    code_float = _weighted_lstsq(h, code, w)
    projected_code = _project_to_length(code_float, baseline_length_m)
    if projected_code is not None:
        candidates.extend([projected_code, -projected_code])
    candidates.extend(direction * float(baseline_length_m) for direction in _fibonacci_directions(grid_count))

    best: np.ndarray | None = None
    best_score = math.inf
    best_phase = np.asarray([], dtype=float)
    best_code = np.asarray([], dtype=float)
    evaluated = 0
    for candidate in candidates:
        score, phase_residual, code_residual = cwls_objective(
            baseline=candidate,
            h=h,
            carrier_m=carrier,
            code_m=code,
            wavelengths_m=wavelengths,
            weights=w,
            code_sigma_m=code_sigma_m,
        )
        evaluated += 1
        if score < best_score:
            best = candidate
            best_score = score
            best_phase = phase_residual
            best_code = code_residual
    if best is None:
        return None

    steps = (0.20, 0.10, 0.050, 0.020, 0.010, 0.005, 0.002)
    refinements = 0
    for step in steps:
        direction = _unit(best)
        if direction is None:
            break
        u, v = _basis(direction)
        improved = False
        for angle_index in range(refine_angles):
            angle = 2.0 * math.pi * angle_index / refine_angles
            perturbed_direction = direction + step * (math.cos(angle) * u + math.sin(angle) * v)
            perturbed_direction = _unit(perturbed_direction)
            if perturbed_direction is None:
                continue
            candidate = perturbed_direction * float(baseline_length_m)
            score, phase_residual, code_residual = cwls_objective(
                baseline=candidate,
                h=h,
                carrier_m=carrier,
                code_m=code,
                wavelengths_m=wavelengths,
                weights=w,
                code_sigma_m=code_sigma_m,
            )
            evaluated += 1
            if score + 1.0e-15 < best_score:
                best = candidate
                best_score = score
                best_phase = phase_residual
                best_code = code_residual
                improved = True
        refinements += 1
        if not improved and step <= 0.005:
            break

    pred = h @ best
    integer_ambiguities = tuple(int(value) for value in special_round_half_down((carrier - pred) / wavelengths))
    return WrappedLSSolution(
        baseline_vector_m=(float(best[0]), float(best[1]), float(best[2])),
        objective=best_score,
        wrapped_phase_rms_cycles=math.sqrt(float(np.mean(best_phase * best_phase))),
        code_residual_rms_m=math.sqrt(float(np.mean(best_code * best_code))),
        integer_ambiguities=integer_ambiguities,
        candidate_count=evaluated,
        refinement_steps=refinements,
        converged=True,
    )


def solution_to_row(solution: WrappedLSSolution) -> dict[str, Any]:
    return {
        "baseline_x_m": solution.baseline_vector_m[0],
        "baseline_y_m": solution.baseline_vector_m[1],
        "baseline_z_m": solution.baseline_vector_m[2],
        "cwls_objective": solution.objective,
        "wrapped_phase_rms_cycles": solution.wrapped_phase_rms_cycles,
        "code_residual_rms_m": solution.code_residual_rms_m,
        "ambiguity_count": len(solution.integer_ambiguities),
        "candidate_count": solution.candidate_count,
        "refinement_steps": solution.refinement_steps,
        "converged": solution.converged,
    }
