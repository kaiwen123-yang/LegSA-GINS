"""Carrier and correlated support measurements on the shared navigation states."""
from __future__ import annotations

import gtsam
import numpy as np

from ..carrier_phase.temporal import EpochBlock


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = vector
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def carrier_factor(
    pose_key: int,
    ambiguity_key: int,
    block: EpochBlock,
    baseline_body: np.ndarray,
) -> gtsam.CustomFactor:
    """Use the full code/carrier covariance with b_world = R * b_body.

    The ambiguity vector uses exactly ``block.ambiguity_labels`` ordering.
    Pose3 local coordinates are rotation followed by body-frame translation.
    """
    baseline = np.asarray(baseline_body, dtype=float).copy()
    A = np.asarray(block.A, dtype=float).copy()
    B = np.asarray(block.B, dtype=float).copy()
    y = np.asarray(block.y, dtype=float).copy()
    noise = gtsam.noiseModel.Gaussian.Covariance(np.asarray(block.Q, dtype=float))

    def error(_factor, values, jacobians):
        rotation = values.atPose3(pose_key).rotation()
        if jacobians is not None:
            pose_jacobian = np.zeros((len(y), 6), order="F")
            pose_jacobian[:, :3] = -B @ rotation.matrix() @ _skew(baseline)
            jacobians[0] = pose_jacobian
            jacobians[1] = np.asfortranarray(A)
        return B @ rotation.rotate(baseline) + A @ values.atVector(ambiguity_key) - y

    return gtsam.CustomFactor(noise, [pose_key, ambiguity_key], error)


def foot_factor(
    pose_key: int,
    contact_key: int,
    measured_body: np.ndarray,
    sigma_m: float,
    *,
    previous_pose_key: int | None = None,
    previous_measured_body: np.ndarray | None = None,
    rho: float = 0.0,
) -> gtsam.CustomFactor:
    """Measure one shared world contact with stationary body-frame AR(1) noise.

    For q_k = R_k.T * (c - p_k) - r_k, the first observation contributes
    q_0 / sigma and each following observation contributes
    (q_k - rho*q_previous) / (sigma*sqrt(1-rho**2)). The contact is a shared
    unknown, not a prior observation or a per-epoch slip/offset state.
    """
    measured = np.asarray(measured_body, dtype=float).copy()
    correlated = previous_pose_key is not None
    previous_measured = (
        np.asarray(previous_measured_body, dtype=float).copy() if correlated else None
    )
    keys = [pose_key, contact_key]
    if correlated:
        keys.append(previous_pose_key)
    innovation_sigma = sigma_m * np.sqrt(1.0 - rho * rho) if correlated else sigma_m
    noise = gtsam.noiseModel.Isotropic.Sigma(3, innovation_sigma)

    def error(_factor, values, jacobians):
        contact = values.atPoint3(contact_key)
        pose = values.atPose3(pose_key)
        if jacobians is None:
            residual = pose.transformTo(contact) - measured
            if correlated:
                previous = values.atPose3(previous_pose_key)
                residual -= rho * (previous.transformTo(contact) - previous_measured)
            return residual

        H_pose = np.empty((3, 6), order="F")
        H_contact = np.empty((3, 3), order="F")
        residual = pose.transformTo(contact, H_pose, H_contact) - measured
        jacobians[0] = H_pose
        if correlated:
            previous = values.atPose3(previous_pose_key)
            H_previous = np.empty((3, 6), order="F")
            H_previous_contact = np.empty((3, 3), order="F")
            residual -= rho * (
                previous.transformTo(contact, H_previous, H_previous_contact)
                - previous_measured
            )
            H_contact -= rho * H_previous_contact
            jacobians[2] = np.asfortranarray(-rho * H_previous)
        jacobians[1] = H_contact
        return residual

    return gtsam.CustomFactor(noise, keys, error)


def carrier_relation_factor(
    pose_key: int,
    ambiguity_keys: list[int],
    block: EpochBlock,
    baseline_body: np.ndarray,
) -> gtsam.CustomFactor:
    """Carrier model with one scalar-vector key per physical ambiguity relation.

    Keys follow ``block.ambiguity_labels``. A relation key can survive loss of
    other rows; a new physical arc gets a new key. With no ambiguity columns the
    same factor supplies the code-only pose observation.
    """
    baseline = np.asarray(baseline_body, dtype=float).copy()
    A = np.asarray(block.A, dtype=float).copy()
    B = np.asarray(block.B, dtype=float).copy()
    y = np.asarray(block.y, dtype=float).copy()
    ambiguity_keys = tuple(ambiguity_keys)
    noise = gtsam.noiseModel.Gaussian.Covariance(np.asarray(block.Q, dtype=float))

    def error(_factor, values, jacobians):
        rotation = values.atPose3(pose_key).rotation()
        residual = B @ rotation.rotate(baseline) - y
        for j, key in enumerate(ambiguity_keys):
            residual += A[:, j] * values.atVector(key)[0]
        if jacobians is not None:
            H_pose = np.zeros((len(y), 6), order="F")
            H_pose[:, :3] = -B @ rotation.matrix() @ _skew(baseline)
            jacobians[0] = H_pose
            for j in range(len(ambiguity_keys)):
                jacobians[j + 1] = np.asfortranarray(A[:, j:j+1])
        return residual

    return gtsam.CustomFactor(noise, [pose_key, *ambiguity_keys], error)


def differential_foot_factor(
    pose_key: int,
    direction_key: int,
    measured_body: np.ndarray,
    sigma_m: float,
    *,
    previous_pose_key: int | None = None,
    previous_measured_body: np.ndarray | None = None,
    rho: float = 0.0,
) -> gtsam.CustomFactor:
    """Keep a shared foot-geometry contrast after common translation is withdrawn.

    ``measured_body`` is an orthonormal contrast of simultaneous foot positions;
    ``direction_key`` holds the corresponding world vector. A unit-norm Helmert
    contrast preserves each original coordinate's sigma. Unlike a contact point,
    this vector predicts R.T*d and never constrains body translation.
    """
    measured = np.asarray(measured_body, dtype=float).copy()
    correlated = previous_pose_key is not None
    previous_measured = (
        np.asarray(previous_measured_body, dtype=float).copy() if correlated else None
    )
    keys = [pose_key, direction_key]
    if correlated:
        keys.append(previous_pose_key)
    innovation_sigma = sigma_m * np.sqrt(1.0 - rho * rho) if correlated else sigma_m
    noise = gtsam.noiseModel.Isotropic.Sigma(3, innovation_sigma)

    def error(_factor, values, jacobians):
        direction = values.atPoint3(direction_key)
        rotation = values.atPose3(pose_key).rotation()
        prediction = rotation.unrotate(direction)
        residual = prediction - measured
        if correlated:
            previous_rotation = values.atPose3(previous_pose_key).rotation()
            previous_prediction = previous_rotation.unrotate(direction)
            residual -= rho * (previous_prediction - previous_measured)
        if jacobians is not None:
            H_pose = np.zeros((3, 6), order="F")
            H_pose[:, :3] = _skew(prediction)
            jacobians[0] = H_pose
            H_direction = rotation.matrix().T.copy(order="F")
            if correlated:
                H_previous = np.zeros((3, 6), order="F")
                H_previous[:, :3] = -rho * _skew(previous_prediction)
                H_direction -= rho * previous_rotation.matrix().T
                jacobians[2] = H_previous
            jacobians[1] = H_direction
        return residual

    return gtsam.CustomFactor(noise, keys, error)


def ar1_error_factor(
    previous_noise_key: int,
    current_noise_key: int,
    rho: float,
    sigma_m: float,
) -> gtsam.CustomFactor:
    """Carry the declared body-frame foot error across an observation-mode change."""
    noise = gtsam.noiseModel.Isotropic.Sigma(3, sigma_m * np.sqrt(1. - rho * rho))

    def error(_factor, values, jacobians):
        if jacobians is not None:
            jacobians[0] = np.asfortranarray(-rho * np.eye(3))
            jacobians[1] = np.eye(3, order="F")
        return values.atPoint3(current_noise_key) - rho * values.atPoint3(previous_noise_key)

    return gtsam.CustomFactor(noise, [previous_noise_key, current_noise_key], error)


def foot_error_coordinate_factor(
    noise_key: int,
    pose_key: int,
    contact_key: int,
    measured_body: np.ndarray,
) -> gtsam.CustomFactor:
    """Define n = R.T(c-p)-r exactly; stochastic uncertainty lives in n's AR chain.

    A constrained coordinate identity is not a zero-noise foot measurement.
    Keeping n explicit preserves its posterior when common translation is later
    released, without introducing a second noise prior at that transition.
    """
    measured = np.asarray(measured_body, dtype=float).copy()

    def error(_factor, values, jacobians):
        pose, contact = values.atPose3(pose_key), values.atPoint3(contact_key)
        if jacobians is None:
            prediction = pose.transformTo(contact)
        else:
            H_pose = np.empty((3, 6), order="F")
            H_contact = np.empty((3, 3), order="F")
            prediction = pose.transformTo(contact, H_pose, H_contact)
            jacobians[0] = np.eye(3, order="F")
            jacobians[1] = np.asfortranarray(-H_pose)
            jacobians[2] = np.asfortranarray(-H_contact)
        return values.atPoint3(noise_key) - prediction + measured

    return gtsam.CustomFactor(gtsam.noiseModel.Constrained.All(3), [noise_key, pose_key, contact_key], error)


def point3_coordinate_factor(target_key: int, terms: dict[int, float]) -> gtsam.CustomFactor:
    """Exact coordinate identity target = sum(coefficient * source).

    For example, d_global = d_local + component_offset joins two contact
    components without measuring or tightly regularizing that offset.
    """
    coefficients = {target_key: 1.}
    for key, coefficient in terms.items():
        coefficients[key] = coefficients.get(key, 0.) - coefficient
    coefficients = {key: value for key, value in coefficients.items() if value != 0.}
    keys = tuple(coefficients)

    def error(_factor, values, jacobians):
        residual = np.zeros(3)
        for i, key in enumerate(keys):
            residual += coefficients[key] * values.atPoint3(key)
            if jacobians is not None:
                jacobians[i] = np.asfortranarray(coefficients[key] * np.eye(3))
        return residual

    return gtsam.CustomFactor(gtsam.noiseModel.Constrained.All(3), list(keys), error)


def relative_geometry_coordinate_factor(
    direction_key: int,
    contact_key: int,
    anchor_contact_key: int,
) -> gtsam.CustomFactor:
    """Define d = c-c_anchor exactly, retaining its existing joint posterior."""
    terms = {contact_key: 1.}
    terms[anchor_contact_key] = terms.get(anchor_contact_key, 0.) - 1.
    return point3_coordinate_factor(direction_key, terms)


def projected_foot_factor(
    pose_key: int,
    geometry_keys: list[int | None],
    noise_keys: list[int],
    measured_body: np.ndarray,
) -> gtsam.CustomFactor:
    """Retain observable simultaneous-foot contrasts, for at least two feet.

    Residual = vec(H [R.T*d_i-r_i-n_i]), where H is the orthonormal Helmert
    contrast matrix and None denotes the chosen component's zero geometry gauge.
    No body translation or new independent measurement noise enters this factor.
    Each n_i retains its original working prior and temporal noise chain.
    """
    from scipy.linalg import helmert

    geometry_keys, noise_keys = tuple(geometry_keys), tuple(noise_keys)
    measured = np.asarray(measured_body, dtype=float).copy()
    count = len(geometry_keys)
    contrasts = helmert(count)
    projection = np.kron(contrasts, np.eye(3))
    keys = tuple(dict.fromkeys([pose_key, *[key for key in geometry_keys if key is not None], *noise_keys]))
    key_indices = {key: i for i, key in enumerate(keys)}

    def error(_factor, values, jacobians):
        rotation = values.atPose3(pose_key).rotation()
        predictions = np.array([rotation.unrotate(values.atPoint3(key)) if key is not None else np.zeros(3)
                                for key in geometry_keys])
        errors = predictions - measured - np.array([values.atPoint3(key) for key in noise_keys])
        if jacobians is not None:
            matrices = [np.zeros((3*(count-1), 6 if key == pose_key else 3), order="F") for key in keys]
            pose_rows = np.zeros((3*count, 6))
            for i, prediction in enumerate(predictions):
                pose_rows[3*i:3*i+3, :3] = _skew(prediction)
                weights = contrasts[:, i:i+1]
                if geometry_keys[i] is not None:
                    matrices[key_indices[geometry_keys[i]]] += np.kron(weights, rotation.matrix().T)
                matrices[key_indices[noise_keys[i]]] -= np.kron(weights, np.eye(3))
            matrices[0] = np.asfortranarray(projection @ pose_rows)
            for i, matrix in enumerate(matrices):
                jacobians[i] = matrix
        return (contrasts @ errors).reshape(-1)

    return gtsam.CustomFactor(gtsam.noiseModel.Constrained.All(3*(count-1)), list(keys), error)


def gnss_position_velocity_factor(pose_key, velocity_key, position, velocity, covariance):
    """Consume the same declared joint GNSS product covariance used in prediction."""
    measured = np.r_[np.asarray(position, float), np.asarray(velocity, float)]
    noise = gtsam.noiseModel.Gaussian.Covariance(np.asarray(covariance, float))

    def error(_factor, values, jacobians):
        pose = values.atPose3(pose_key)
        if jacobians is not None:
            h_pose = np.zeros((6, 6), order="F")
            h_pose[:3, 3:] = pose.rotation().matrix()
            jacobians[0] = h_pose
            h_velocity = np.zeros((6, 3), order="F")
            h_velocity[3:] = np.eye(3)
            jacobians[1] = h_velocity
        return np.r_[pose.translation(), values.atVector(velocity_key)]-measured

    return gtsam.CustomFactor(noise, [pose_key, velocity_key], error)
