"""Pavlasek--Walsh--Forbes two-position-receiver IEKF.

This module implements the paper's bias-free :math:`SE_2(3)` model in
Eqs. (15)--(43).  The state convention is ``C_nb`` (body FRD to navigation
NED), navigation-frame velocity, and navigation-frame IMU-point position.
The left-invariant error is ``X_true^-1 X_hat``.  Consequently the correction
is applied on the right as ``X_hat <- X_check Exp(-(K z)^)``.

Appendix-A's MEKF is deliberately absent.  Its Eqs. (45), (46), (47), and
(50) do not define one internally consistent error/noise/update convention.
The authorized status for that baseline is
``NOT_IMPLEMENTED_DUE_TO_INTERNAL_APPENDIX_INCONSISTENCY``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from scipy.linalg import expm


METHOD_IEKF = "EXT05A_PAVLASEK_TWO_RECEIVER_IEKF"
METHOD_MEKF = "EXT05B_PAVLASEK_TWO_RECEIVER_MEKF_APPENDIX_EXACT"
METHOD_SINGLE = "EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF"
MEKF_STATUS = "NOT_IMPLEMENTED_DUE_TO_INTERNAL_APPENDIX_INCONSISTENCY"


class PavlasekFilterError(ValueError):
    """The paper/filter contract was violated."""


def _vec3(value: Sequence[float], label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (3,) or np.any(~np.isfinite(result)):
        raise PavlasekFilterError(f"{label} must be a finite three-vector")
    return result


def _matrix(value: Sequence[Sequence[float]], shape: tuple[int, int], label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != shape or np.any(~np.isfinite(result)):
        raise PavlasekFilterError(f"{label} must be a finite {shape} matrix")
    return result


def _covariance(
    value: Sequence[Sequence[float]], shape: tuple[int, int], label: str
) -> np.ndarray:
    result = _matrix(value, shape, label)
    symmetry_error = float(np.max(np.abs(result - result.T)))
    if symmetry_error > 1.0e-10:
        raise PavlasekFilterError(f"{label} must be symmetric")
    result = 0.5 * (result + result.T)
    if float(np.min(np.linalg.eigvalsh(result))) < -1.0e-10:
        raise PavlasekFilterError(f"{label} must be positive semidefinite")
    return result


def skew(value: Sequence[float]) -> np.ndarray:
    """Return the cross-product matrix used throughout the paper."""

    x, y, z = _vec3(value, "cross-product operand")
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def so3_exp(phi: Sequence[float]) -> np.ndarray:
    """Rodrigues exponential with stable small-angle coefficients."""

    vector = _vec3(phi, "SO(3) tangent")
    angle = float(np.linalg.norm(vector))
    cross = skew(vector)
    if angle < 1.0e-8:
        return np.eye(3) + cross + 0.5 * cross @ cross
    a = math.sin(angle) / angle
    b = (1.0 - math.cos(angle)) / (angle * angle)
    return np.eye(3) + a * cross + b * cross @ cross


def so3_left_jacobian(phi: Sequence[float]) -> np.ndarray:
    """SO(3) left Jacobian used by the actual SE_2(3) exponential."""

    vector = _vec3(phi, "SO(3) tangent")
    angle = float(np.linalg.norm(vector))
    cross = skew(vector)
    if angle < 1.0e-8:
        return np.eye(3) + 0.5 * cross + (1.0 / 6.0) * cross @ cross
    a = (1.0 - math.cos(angle)) / (angle * angle)
    b = (angle - math.sin(angle)) / (angle**3)
    return np.eye(3) + a * cross + b * cross @ cross


def so3_log(rotation: Sequence[Sequence[float]]) -> np.ndarray:
    """Principal SO(3) logarithm, used only for diagnostics/tests."""

    matrix = _matrix(rotation, (3, 3), "rotation")
    cosine = float(np.clip((np.trace(matrix) - 1.0) * 0.5, -1.0, 1.0))
    angle = math.acos(cosine)
    vee = np.array([
        matrix[2, 1] - matrix[1, 2],
        matrix[0, 2] - matrix[2, 0],
        matrix[1, 0] - matrix[0, 1],
    ])
    if angle < 1.0e-8:
        return 0.5 * vee
    if math.pi - angle < 1.0e-6:
        # Eigenvector recovery avoids division by sin(pi).
        values, vectors = np.linalg.eigh((matrix + np.eye(3)) * 0.5)
        axis = vectors[:, int(np.argmax(values))]
        return angle * axis
    return angle * vee / (2.0 * math.sin(angle))


def project_so3(rotation: Sequence[Sequence[float]]) -> np.ndarray:
    """Remove roundoff drift without changing the represented attitude."""

    matrix = _matrix(rotation, (3, 3), "rotation")
    left, _singular, right = np.linalg.svd(matrix)
    projected = left @ right
    if np.linalg.det(projected) < 0.0:
        left[:, -1] *= -1.0
        projected = left @ right
    return projected


def se23_exp(tangent: Sequence[float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(C, v, r)`` for the paper's actual SE_2(3) exponential."""

    value = np.asarray(tangent, dtype=float)
    if value.shape != (9,) or np.any(~np.isfinite(value)):
        raise PavlasekFilterError("SE_2(3) tangent must be a finite nine-vector")
    phi, velocity, position = value[:3], value[3:6], value[6:9]
    jacobian = so3_left_jacobian(phi)
    return so3_exp(phi), jacobian @ velocity, jacobian @ position


@dataclass
class ExtendedPose:
    """Paper Eq. (24), with body-to-NED attitude convention."""

    C_nb: np.ndarray
    velocity_ned_mps: np.ndarray
    position_ned_m: np.ndarray

    def __post_init__(self) -> None:
        self.C_nb = project_so3(self.C_nb)
        self.velocity_ned_mps = _vec3(self.velocity_ned_mps, "velocity")
        self.position_ned_m = _vec3(self.position_ned_m, "position")

    def matrix(self) -> np.ndarray:
        value = np.eye(5)
        value[:3, :3] = self.C_nb
        value[:3, 3] = self.velocity_ned_mps
        value[:3, 4] = self.position_ned_m
        return value

    def right_correct(self, error_estimate: Sequence[float]) -> None:
        """Apply paper update ``X <- X Exp(-delta^)`` on the correct side."""

        delta = np.asarray(error_estimate, dtype=float)
        correction_rotation, correction_velocity, correction_position = se23_exp(-delta)
        prior_rotation = self.C_nb.copy()
        self.velocity_ned_mps = self.velocity_ned_mps + prior_rotation @ correction_velocity
        self.position_ned_m = self.position_ned_m + prior_rotation @ correction_position
        self.C_nb = project_so3(prior_rotation @ correction_rotation)


def left_invariant_error_components(
    true_pose: ExtendedPose, estimate_pose: ExtendedPose
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Paper Eqs. (27)--(29): components of ``X_true^-1 X_hat``."""

    attitude = true_pose.C_nb.T @ estimate_pose.C_nb
    velocity = true_pose.C_nb.T @ (
        estimate_pose.velocity_ned_mps - true_pose.velocity_ned_mps
    )
    position = true_pose.C_nb.T @ (
        estimate_pose.position_ned_m - true_pose.position_ned_m
    )
    return attitude, velocity, position


def process_drift_matrix(
    pose: ExtendedPose,
    angular_rate_body_radps: Sequence[float],
    specific_force_body_mps2: Sequence[float],
    gravity_ned_mps2: Sequence[float],
) -> np.ndarray:
    """Paper Eq. (26), embedded as a 5x5 matrix derivative."""

    omega = _vec3(angular_rate_body_radps, "angular rate")
    force = _vec3(specific_force_body_mps2, "specific force")
    gravity = _vec3(gravity_ned_mps2, "gravity")
    result = np.zeros((5, 5))
    result[:3, :3] = pose.C_nb @ skew(omega)
    result[:3, 3] = pose.C_nb @ force + gravity
    result[:3, 4] = pose.velocity_ned_mps
    return result


def continuous_error_matrices(
    angular_rate_body_radps: Sequence[float],
    specific_force_body_mps2: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    """State-estimate-independent paper Jacobians, Eqs. (31)--(32)."""

    omega_cross = skew(angular_rate_body_radps)
    force_cross = skew(specific_force_body_mps2)
    A = np.zeros((9, 9))
    A[0:3, 0:3] = -omega_cross
    A[3:6, 0:3] = -force_cross
    A[3:6, 3:6] = -omega_cross
    A[6:9, 3:6] = np.eye(3)
    A[6:9, 6:9] = -omega_cross
    L = np.zeros((9, 6))
    L[0:3, 0:3] = -np.eye(3)
    L[3:6, 3:6] = -np.eye(3)
    return A, L


def van_loan_discretize(
    A: Sequence[Sequence[float]],
    L: Sequence[Sequence[float]],
    continuous_noise: Sequence[Sequence[float]],
    dt_seconds: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Exact zero-order-hold covariance discretization (Van Loan)."""

    system = _matrix(A, (9, 9), "continuous error Jacobian")
    injection = _matrix(L, (9, 6), "continuous noise Jacobian")
    spectral = _covariance(continuous_noise, (6, 6), "continuous noise PSD")
    if not math.isfinite(dt_seconds) or dt_seconds <= 0.0:
        raise PavlasekFilterError("covariance propagation dt must be positive")
    driving = injection @ spectral @ injection.T
    block = np.zeros((18, 18))
    block[:9, :9] = system
    block[:9, 9:] = driving
    block[9:, 9:] = -system.T
    exponential = expm(block * dt_seconds)
    transition = exponential[:9, :9]
    discrete_noise = exponential[:9, 9:] @ transition.T
    discrete_noise = 0.5 * (discrete_noise + discrete_noise.T)
    return transition, discrete_noise


def stacked_position_covariance(
    receiver1_covariance_ned_m2: Sequence[Sequence[float]],
    receiver2_covariance_ned_m2: Sequence[Sequence[float]],
) -> np.ndarray:
    """Covariance of ``[p1, p2-p1]`` including its mandatory correlation."""

    first = _covariance(receiver1_covariance_ned_m2, (3, 3), "receiver-1 covariance")
    second = _covariance(receiver2_covariance_ned_m2, (3, 3), "receiver-2 covariance")
    result = np.block([[first, -first], [-first, first + second]])
    if np.min(np.linalg.eigvalsh(0.5 * (result + result.T))) < -1.0e-10:
        raise PavlasekFilterError("stacked two-position covariance is not PSD")
    return result


def measurement_jacobian(
    receiver1_from_imu_body_m: Sequence[float],
    receiver2_from_receiver1_body_m: Sequence[float],
    *,
    two_receiver: bool,
) -> np.ndarray:
    """Paper Eq. (37), with its state-estimate-independent blocks."""

    first = _vec3(receiver1_from_imu_body_m, "IMU-to-receiver-1 lever arm")
    baseline = _vec3(receiver2_from_receiver1_body_m, "receiver baseline")
    rows = 6 if two_receiver else 3
    H = np.zeros((rows, 9))
    H[:3, :3] = skew(first)
    H[:3, 6:9] = -np.eye(3)
    if two_receiver:
        H[3:6, :3] = skew(baseline)
    return H


@dataclass(frozen=True)
class UpdateDiagnostics:
    innovation: np.ndarray
    predicted_receiver1_ned_m: np.ndarray
    predicted_relative_ned_m: np.ndarray | None
    receiver1_residual_ned_m: np.ndarray
    relative_residual_ned_m: np.ndarray | None
    innovation_covariance: np.ndarray
    gain: np.ndarray
    nis: float
    correction: np.ndarray


class PavlasekIEKF:
    """Bias-free paper IEKF with identical dual/single receiver machinery."""

    def __init__(
        self,
        pose: ExtendedPose,
        covariance: Sequence[Sequence[float]],
        *,
        receiver1_from_imu_body_m: Sequence[float],
        receiver2_from_receiver1_body_m: Sequence[float],
        gyro_psd: Sequence[float],
        accelerometer_psd: Sequence[float],
        gravity_ned_mps2: Sequence[float],
        two_receiver: bool,
    ) -> None:
        self.pose = pose
        self.covariance = _covariance(covariance, (9, 9), "initial covariance")
        self.lever = _vec3(receiver1_from_imu_body_m, "lever arm")
        self.baseline = _vec3(receiver2_from_receiver1_body_m, "baseline")
        gyro = _vec3(gyro_psd, "gyro PSD")
        accel = _vec3(accelerometer_psd, "accelerometer PSD")
        if np.any(gyro <= 0.0) or np.any(accel <= 0.0):
            raise PavlasekFilterError("process PSD entries must be positive")
        self.continuous_noise = np.diag(np.concatenate((gyro, accel)))
        self.gravity = _vec3(gravity_ned_mps2, "gravity")
        self.two_receiver = bool(two_receiver)
        self.H = measurement_jacobian(self.lever, self.baseline, two_receiver=self.two_receiver)
        self.propagation_count = 0
        self.update_count = 0

    def propagate(
        self,
        angular_rate_body_radps: Sequence[float],
        specific_force_body_mps2: Sequence[float],
        dt_seconds: float,
    ) -> None:
        """Integrate Eqs. (17)--(19) and propagate Eq. (31) covariance."""

        omega = _vec3(angular_rate_body_radps, "angular rate")
        force = _vec3(specific_force_body_mps2, "specific force")
        if not math.isfinite(dt_seconds) or not 0.0 < dt_seconds <= 0.1:
            raise PavlasekFilterError("IMU propagation dt outside (0,0.1] seconds")
        A, L = continuous_error_matrices(omega, force)
        transition, process_noise = van_loan_discretize(
            A, L, self.continuous_noise, dt_seconds
        )
        half_rotation = so3_exp(0.5 * dt_seconds * omega)
        acceleration = self.pose.C_nb @ half_rotation @ force + self.gravity
        self.pose.position_ned_m = (
            self.pose.position_ned_m
            + self.pose.velocity_ned_mps * dt_seconds
            + 0.5 * acceleration * dt_seconds * dt_seconds
        )
        self.pose.velocity_ned_mps = self.pose.velocity_ned_mps + acceleration * dt_seconds
        self.pose.C_nb = project_so3(self.pose.C_nb @ so3_exp(dt_seconds * omega))
        self.covariance = transition @ self.covariance @ transition.T + process_noise
        self.covariance = 0.5 * (self.covariance + self.covariance.T)
        self.covariance = _covariance(self.covariance, (9, 9), "propagated covariance")
        self.propagation_count += 1

    def update(
        self,
        receiver1_position_ned_m: Sequence[float],
        receiver1_covariance_ned_m2: Sequence[Sequence[float]],
        *,
        receiver2_position_ned_m: Sequence[float] | None = None,
        receiver2_covariance_ned_m2: Sequence[Sequence[float]] | None = None,
    ) -> UpdateDiagnostics:
        """Apply Eqs. (33)--(37) and ``X <- X Exp(-(Kz)^)``."""

        p1 = _vec3(receiver1_position_ned_m, "receiver-1 position")
        R1 = _covariance(receiver1_covariance_ned_m2, (3, 3), "receiver-1 covariance")
        rotation_before = self.pose.C_nb.copy()
        predicted_p1 = self.pose.position_ned_m + rotation_before @ self.lever
        residual1 = p1 - predicted_p1
        innovation_parts = [rotation_before.T @ residual1]
        predicted_relative: np.ndarray | None = None
        residual_relative: np.ndarray | None = None
        if self.two_receiver:
            if receiver2_position_ned_m is None or receiver2_covariance_ned_m2 is None:
                raise PavlasekFilterError("two-receiver update requires receiver 2 and R2")
            p2 = _vec3(receiver2_position_ned_m, "receiver-2 position")
            R2 = _covariance(receiver2_covariance_ned_m2, (3, 3), "receiver-2 covariance")
            predicted_relative = rotation_before @ self.baseline
            residual_relative = (p2 - p1) - predicted_relative
            innovation_parts.append(rotation_before.T @ residual_relative)
            measurement_covariance = stacked_position_covariance(R1, R2)
            transform = np.zeros((6, 6))
            transform[:3, :3] = rotation_before.T
            transform[3:6, 3:6] = rotation_before.T
            invariant_covariance = transform @ measurement_covariance @ transform.T
        else:
            invariant_covariance = rotation_before.T @ R1 @ rotation_before
        innovation = np.concatenate(innovation_parts)
        S = self.H @ self.covariance @ self.H.T + invariant_covariance
        S = 0.5 * (S + S.T)
        try:
            gain = np.linalg.solve(S, self.H @ self.covariance).T
            solved_innovation = np.linalg.solve(S, innovation)
        except np.linalg.LinAlgError as exc:
            raise PavlasekFilterError("innovation covariance is singular") from exc
        correction = gain @ innovation
        identity = np.eye(9)
        joseph = identity - gain @ self.H
        posterior = (
            joseph @ self.covariance @ joseph.T
            + gain @ invariant_covariance @ gain.T
        )
        self.pose.right_correct(correction)
        self.covariance = _covariance(
            0.5 * (posterior + posterior.T), (9, 9), "posterior covariance"
        )
        self.update_count += 1
        return UpdateDiagnostics(
            innovation=innovation,
            predicted_receiver1_ned_m=predicted_p1,
            predicted_relative_ned_m=predicted_relative,
            receiver1_residual_ned_m=residual1,
            relative_residual_ned_m=residual_relative,
            innovation_covariance=S,
            gain=gain,
            nis=float(innovation @ solved_innovation),
            correction=correction,
        )


def rotation_to_rpy_ned_frd_deg(rotation: Sequence[Sequence[float]]) -> tuple[float, float, float]:
    """Extract NED/FRD roll, pitch, and wrapped yaw for NAV output."""

    C = project_so3(rotation)
    roll = math.atan2(C[2, 1], C[2, 2])
    pitch = math.asin(float(np.clip(-C[2, 0], -1.0, 1.0)))
    yaw = math.atan2(C[1, 0], C[0, 0])
    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw) % 360.0


def finite_filter_snapshot(filter_: PavlasekIEKF) -> dict[str, Any]:
    """Fail-closed finite/rotation/covariance audit payload."""

    pose = filter_.pose
    rotation_error = float(np.linalg.norm(pose.C_nb.T @ pose.C_nb - np.eye(3)))
    minimum_covariance_eigenvalue = float(np.min(np.linalg.eigvalsh(filter_.covariance)))
    finite = bool(
        np.all(np.isfinite(pose.C_nb))
        and np.all(np.isfinite(pose.velocity_ned_mps))
        and np.all(np.isfinite(pose.position_ned_m))
        and np.all(np.isfinite(filter_.covariance))
    )
    return {
        "finite": finite,
        "rotation_orthogonality_error": rotation_error,
        "rotation_determinant": float(np.linalg.det(pose.C_nb)),
        "minimum_covariance_eigenvalue": minimum_covariance_eigenvalue,
        "propagation_count": filter_.propagation_count,
        "update_count": filter_.update_count,
    }
