"""Causal coarse raw-code anchors; no position/velocity navigation observation.

The default hold policy is an explicitly declared development assumption, not
an estimated confidence region. It may release a DD-model construction blocker;
it does not certify an integer, calibrate Q, or relax any downstream gate.

For fixed original pseudoranges/broadcast states, pair_geometry uses
g(a)=rho2(a)-rho1(a)-c*(dt_sat2-dt_sat1) and h(a,b)=g(a)-u2(a).T b.
Thus its DD anchor Jacobian is
    J_h_DD = J_g_target - J_g_pivot
             - b.T @ (J_u2_target - J_u2_pivot).
The J_g term includes the two receivers' distinct transmit states and cannot
in general be replaced by a baseline-length/range bound. Satellite clock terms
are independent of anchor for fixed raw-code transmit-state queries.

The functions below differentiate the SAME four geometric Earth-rotation
iterations as pair_geometry, including each iteration's anchor dependence.
The returned first-order coefficient is local sensitivity, not a rigorous
finite-radius error bound, calibrated uncertainty, or a covariance correction.
Atmosphere, code bias, ephemeris error, physical receiver-time misalignment,
and higher-order anchor terms remain outside this derivative.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

_C = 299792458.0
_OMEGA = 7.2921151467e-5
_ROT_GENERATOR = np.array([[0., 1., 0.], [-1., 0., 0.], [0., 0., 0.]])


@dataclass(frozen=True)
class AnchorPolicy:
    max_hold_age_s: float = 20.0
    initial_error_radius_m: float = 100.0
    motion_bound_mps: float = 5.0

    def __post_init__(self):
        values = (self.max_hold_age_s, self.initial_error_radius_m, self.motion_bound_mps)
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("ANCHOR_POLICY_REQUIRES_FINITE_NONNEGATIVE_VALUES")


@dataclass(frozen=True)
class AnchorDecision:
    time_s: float
    status: str
    position_ecef_m: tuple[float, float, float] | None
    source_time_s: float | None
    age_s: float | None
    assumed_error_radius_m: float | None
    spp_failure: str | None
    assumption_label: str = "ENGINEERING_RADIUS_NOT_CALIBRATED_CONFIDENCE"
    navigation_measurement: bool = False

    @property
    def available(self) -> bool:
        return self.position_ecef_m is not None

    @property
    def held(self) -> bool:
        return self.status == "HELD_RAW_CODE_ANCHOR"


class CausalRawCodeAnchor:
    """Strictly ordered state of successful receiver-1 raw-code SPP anchors.

    Call exactly once per epoch AFTER that epoch's SPP attempt; supplying a
    position asserts that the caller's current raw-code solver accepted it.
    Missing anchors never use a future position, interpolation, velocity,
    reference, GNSS PVT, or a second receiver's position difference.

    Invalid advertised current positions fail closed for that epoch and do
    not overwrite the last usable anchor. Subsequent calls may still hold the
    last usable anchor subject to its original age.
    """
    def __init__(self, policy: AnchorPolicy = AnchorPolicy()):
        if not isinstance(policy, AnchorPolicy):
            raise ValueError("ANCHOR_POLICY_TYPE")
        self.policy = policy
        self._last_call_time: float | None = None
        self._source_time: float | None = None
        self._position: tuple[float, float, float] | None = None

    def resolve(self, time_s: float, position_ecef_m: Sequence[float] | None = None,
                *, failure: str | None = None) -> AnchorDecision:
        if not math.isfinite(time_s) or (
            self._last_call_time is not None and time_s <= self._last_call_time
        ):
            raise ValueError("ANCHOR_EPOCHS_MUST_BE_FINITE_STRICTLY_INCREASING")
        if position_ecef_m is not None and failure is not None:
            raise ValueError("ANCHOR_SUCCESS_AND_FAILURE_CONFLICT")
        if failure is not None and (not isinstance(failure, str) or not failure):
            raise ValueError("ANCHOR_FAILURE_MUST_BE_NONEMPTY_TEXT")
        self._last_call_time = float(time_s)
        invalid_current = False
        if position_ecef_m is not None:
            try:
                point = np.asarray(position_ecef_m, dtype=float)
                invalid_current = point.shape != (3,) or not np.isfinite(point).all()
            except (ValueError, TypeError):
                invalid_current = True
            if not invalid_current:
                self._source_time = float(time_s)
                self._position = tuple(float(v) for v in point)
                return AnchorDecision(float(time_s), "CURRENT_RAW_CODE_ANCHOR",
                                      self._position, self._source_time, 0.,
                                      self.policy.initial_error_radius_m, None)
            failure = "INVALID_CURRENT_RAW_CODE_ANCHOR"
        elif failure is None:
            failure = "CURRENT_RAW_CODE_ANCHOR_UNAVAILABLE"
        age = None if self._source_time is None else float(time_s - self._source_time)
        radius = None if age is None else (
            self.policy.initial_error_radius_m + self.policy.motion_bound_mps * age
        )
        if invalid_current:
            status = "UNAVAILABLE_INVALID_CURRENT_ANCHOR"
        elif self._position is None:
            status = "UNAVAILABLE_NO_PRIOR_ANCHOR"
        elif age > self.policy.max_hold_age_s:
            status = "UNAVAILABLE_HOLD_TOO_OLD"
        else:
            return AnchorDecision(float(time_s), "HELD_RAW_CODE_ANCHOR",
                                  self._position, self._source_time, age, radius, failure)
        return AnchorDecision(float(time_s), status, None, self._source_time,
                              age, radius, failure)


@dataclass(frozen=True)
class PairAnchorJacobian:
    known_sd_gradient: np.ndarray
    los2_jacobian: np.ndarray
    los1: np.ndarray
    los2: np.ndarray


def _rotation_geometry_jacobian(satellite, anchor):
    """Differentiate four geometric-flight iterations without a fixed-point shortcut."""
    original = np.asarray(satellite, dtype=float)
    point = np.asarray(anchor, dtype=float)
    if (original.shape != (3,) or point.shape != (3,)
            or not np.isfinite(original).all() or not np.isfinite(point).all()):
        raise ValueError("INVALID_ANCHOR_GEOMETRY")
    corrected = original.copy()
    jacobian = np.zeros((3, 3))
    identity = np.eye(3)
    for _ in range(4):
        delta = corrected - point
        distance = float(np.linalg.norm(delta))
        flight = distance / _C
        if not 0 < flight < 1:
            raise ValueError("INVALID_GEOMETRIC_FLIGHT_TIME")
        unit = delta / distance
        flight_gradient = unit @ (jacobian - identity) / _C
        angle = _OMEGA * flight
        co, si = math.cos(angle), math.sin(angle)
        rotation = np.array([[co, si, 0.], [-si, co, 0.], [0., 0., 1.]])
        corrected = rotation @ original
        jacobian = np.outer(_OMEGA * (_ROT_GENERATOR @ corrected), flight_gradient)
    delta = corrected - point
    distance = float(np.linalg.norm(delta))
    unit = delta / distance
    range_gradient = unit @ (jacobian - identity)
    los_jacobian = (identity - np.outer(unit, unit)) @ (jacobian - identity) / distance
    return unit, range_gradient, los_jacobian


def pair_geometry_anchor_jacobian(
    satellite1_transmit_ecef_m: Sequence[float],
    satellite2_transmit_ecef_m: Sequence[float],
    anchor_ecef_m: Sequence[float],
) -> PairAnchorJacobian:
    """Fixed own-code states in, derivative of the implemented pair geometry out.

    Inputs are unrotated provider.state positions for each receiver's own
    pseudorange, not already Sagnac-rotated positions.
    """
    one, grad1, _ = _rotation_geometry_jacobian(satellite1_transmit_ecef_m, anchor_ecef_m)
    two, grad2, ju2 = _rotation_geometry_jacobian(satellite2_transmit_ecef_m, anchor_ecef_m)
    return PairAnchorJacobian(grad2 - grad1, ju2, one, two)


@dataclass(frozen=True)
class DDAnchorSensitivity:
    known_sd_gradient: np.ndarray
    los2_jacobian_difference: np.ndarray
    known_sd_coefficient: float
    baseline_coefficient: float
    first_order_coefficient: float
    approximation: str = "LOCAL_FIRST_ORDER_NOT_GLOBAL_ERROR_BOUND"

    def gradient_at_baseline(self, baseline_ecef_m: Sequence[float]) -> np.ndarray:
        baseline = np.asarray(baseline_ecef_m, dtype=float)
        if baseline.shape != (3,) or not np.isfinite(baseline).all():
            raise ValueError("INVALID_BASELINE")
        return self.known_sd_gradient - baseline @ self.los2_jacobian_difference


def dd_anchor_sensitivity(target: PairAnchorJacobian, pivot: PairAnchorJacobian,
                          *, length_m: float) -> DDAnchorSensitivity:
    """Triangle bound on local gradient over ||b||=L, in metres/metre.

    For an assumed anchor radius E the quantity E*first_order_coefficient
    estimates a conservative linearized magnitude. No finite-radius, noise,
    integer-validity, or navigation-integrity guarantee follows.
    """
    if not math.isfinite(length_m) or length_m <= 0:
        raise ValueError("POSITIVE_FINITE_BASELINE_LENGTH_REQUIRED")
    gradient = np.asarray(target.known_sd_gradient) - np.asarray(pivot.known_sd_gradient)
    difference = np.asarray(target.los2_jacobian) - np.asarray(pivot.los2_jacobian)
    if (gradient.shape != (3,) or difference.shape != (3, 3)
            or not np.isfinite(gradient).all() or not np.isfinite(difference).all()):
        raise ValueError("INVALID_PAIR_ANCHOR_JACOBIAN")
    known = float(np.linalg.norm(gradient))
    baseline = length_m * float(np.linalg.norm(difference, ord=2))
    return DDAnchorSensitivity(gradient.copy(), difference.copy(), known, baseline, known + baseline)
