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
