"""Carrier and correlated support measurements on the shared navigation states."""
from __future__ import annotations

from dataclasses import dataclass

import gtsam
import numpy as np

from ..carrier_phase.temporal import EpochBlock


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = vector
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


@dataclass(frozen=True)
class FootErrorExpression:
    """Original body foot error with redundant equality coordinates eliminated.

    Fixed: e=R.T(c-p)-r. Common translation released: e=R.T(d)-r-q,
    with one unconstrained q shared by the simultaneously observed group.
    """
    pose_key: int
    point_key: int | None
    measured_body: tuple[float, float, float]
    common_key: int | None = None

    @property
    def keys(self):
        return (self.pose_key, *(() if self.point_key is None else (self.point_key,)),
                *(() if self.common_key is None else (self.common_key,)))

    def evaluate(self, values, derivatives=False):
        pose = values.atPose3(self.pose_key)
        point = np.zeros(3) if self.point_key is None else values.atPoint3(self.point_key)
        relative = pose.rotation().unrotate(point if self.common_key is not None else point-pose.translation())
        error = relative-np.asarray(self.measured_body)
        if self.common_key is not None:
            error -= values.atVector(self.common_key)
        if not derivatives:
            return error
        pose_jacobian = np.zeros((3, 6))
        pose_jacobian[:, :3] = _skew(relative)
        if self.common_key is None:
            pose_jacobian[:, 3:] = -np.eye(3)
        jacobians = {self.pose_key: pose_jacobian}
        if self.point_key is not None:
            jacobians[self.point_key] = pose.rotation().matrix().T
        if self.common_key is not None:
            jacobians[self.common_key] = -np.eye(3)
        return error, jacobians


def algebraic_foot_error_factor(current: FootErrorExpression, sigma: float, *,
                                previous: FootErrorExpression | None = None, rho: float = 0.):
    """Original per-arc AR likelihood, evaluated exactly on the contact manifold.

    No new noise or pseudo measurement is introduced by q. Eliminating each
    unconstrained common q gives the same projected directional likelihood,
    including all cross-time correlations from each original arc's AR error.
    """
    keys = tuple(dict.fromkeys((*current.keys, *(() if previous is None else previous.keys))))
    innovation_sigma = sigma if previous is None else sigma*np.sqrt(1.-rho*rho)

    def error(_factor, values, jacobians):
        residual, blocks = current.evaluate(values, True)
        if previous is not None:
            old, old_blocks = previous.evaluate(values, True)
            residual -= rho*old
            for key, block in old_blocks.items():
                blocks[key] = blocks.get(key, np.zeros_like(block))-rho*block
        if jacobians is not None:
            for index, key in enumerate(keys):
                jacobians[index] = np.asfortranarray(blocks[key])
        return residual

    return gtsam.CustomFactor(gtsam.noiseModel.Isotropic.Sigma(3, innovation_sigma), list(keys), error)


def gravity_tilt_factor(pose_key: int, direction_body, gravity_world, sigma_rad):
    """Two-dimensional S2 log residual with no world-gravity yaw information.

    The body direction and angular uncertainty require an eligible source. A
    raw accelerometer sample is not silently treated as gravity. The spherical
    log chart has its usual undefined antipode; it is not a second zero-error
    gravity solution as it would be for a tangent-projection residual.
    """
    measured = gtsam.Unit3(np.asarray(direction_body, float))
    body = measured.point3()
    basis = measured.basis().T
    gravity = gtsam.Unit3(np.asarray(gravity_world, float)).point3()

    def error(_factor, values, jacobians):
        predicted = values.atPose3(pose_key).rotation().unrotate(gravity)
        tangent = basis @ predicted
        sine, cosine = np.linalg.norm(tangent), float(body @ predicted)
        if sine < 1e-8 and cosine < 0.:
            raise ValueError("gravity tilt tangent chart is undefined at the antipodal prediction")
        angle = np.arctan2(sine, cosine)
        if sine < 1e-5:
            scale, derivative = 1.+sine*sine/6., -1./3.
        else:
            scale = angle/sine
            derivative = (angle*cosine-sine)/sine**3
        if jacobians is not None:
            jacobian = np.zeros((2, 6), order="F")
            jacobian[:, :3] = (scale*basis+derivative*np.outer(tangent, body)) @ _skew(predicted)
            jacobians[0] = jacobian
        return scale*tangent

    return gtsam.CustomFactor(gtsam.noiseModel.Diagonal.Sigmas(
        np.broadcast_to(np.asarray(sigma_rad, float), (2,)).copy()), [pose_key], error)


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
    *,
    beta_keys: tuple[int, ...] = (),
    source_design: np.ndarray | None = None,
    covariance: np.ndarray | None = None,
) -> gtsam.CustomFactor:
    """Carrier model with one scalar-vector key per physical ambiguity relation.

    Keys follow ``block.ambiguity_labels``. A relation key can survive loss of
    other rows; a new physical arc gets a new key. With no ambiguity columns the
    same factor supplies the code-only pose observation. Optional meter-valued
    physical SD beta coordinates enter through D; their OU process lives in the
    same graph. ``covariance`` contains original Q and the added white term only.
    """
    baseline = np.asarray(baseline_body, dtype=float).copy()
    A = np.asarray(block.A, dtype=float).copy()
    B = np.asarray(block.B, dtype=float).copy()
    y = np.asarray(block.y, dtype=float).copy()
    ambiguity_keys = tuple(ambiguity_keys)
    beta_keys = tuple(beta_keys)
    D = None if source_design is None else np.asarray(source_design, dtype=float).copy()
    noise = gtsam.noiseModel.Gaussian.Covariance(np.asarray(block.Q if covariance is None else covariance, dtype=float))

    def error(_factor, values, jacobians):
        rotation = values.atPose3(pose_key).rotation()
        residual = B @ rotation.rotate(baseline) - y
        for j, key in enumerate(ambiguity_keys):
            residual += A[:, j] * values.atVector(key)[0]
        for j, key in enumerate(beta_keys):
            residual += D[:, j] * values.atVector(key)[0]
        if jacobians is not None:
            H_pose = np.zeros((len(y), 6), order="F")
            H_pose[:, :3] = -B @ rotation.matrix() @ _skew(baseline)
            jacobians[0] = H_pose
            for j in range(len(ambiguity_keys)):
                jacobians[j + 1] = np.asfortranarray(A[:, j:j+1])
            for j in range(len(beta_keys)):
                jacobians[1 + len(ambiguity_keys) + j] = np.asfortranarray(D[:, j:j+1])
        return residual

    return gtsam.CustomFactor(noise, [pose_key, *ambiguity_keys, *beta_keys], error)


def source_ou_factor(previous_key: int, current_key: int, rho: float,
                     innovation_sigma_m: float) -> gtsam.CustomFactor:
    """Meter-valued physical SD error transition; zero interval is exact."""
    noise = (gtsam.noiseModel.Constrained.All(1) if innovation_sigma_m == 0. else
             gtsam.noiseModel.Isotropic.Sigma(1, innovation_sigma_m))

    def error(_factor, values, jacobians):
        if jacobians is not None:
            jacobians[0] = np.array([[-rho]], order="F")
            jacobians[1] = np.ones((1, 1), order="F")
        return values.atVector(current_key)-rho*values.atVector(previous_key)

    return gtsam.CustomFactor(noise, [previous_key, current_key], error)


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


def gnss_antenna_prediction(pose, velocity, gyro_bias, position_lever, velocity_lever, angular_rate):
    """Predict original antenna observations in the navigation frame."""
    rotation = pose.rotation().matrix()
    relative_velocity = np.cross(np.asarray(angular_rate)-np.asarray(gyro_bias), velocity_lever)
    return (pose.translation()+rotation@position_lever,
            np.asarray(velocity)+rotation@relative_velocity)


def gnss_antenna_factor(pose_key, velocity_key, bias_key, position, velocity, covariance,
                        position_lever, velocity_lever, angular_rate):
    """Original antenna p/v likelihood; angular-rate noise is in supplied covariance.

    Bias is estimated jointly; the measured angular rate is a causal source
    sample, never a truth rate or a GNSS-precorrected independent observation.
    The caller owns its measurement-noise covariance and shared-IMU dependence.
    """
    has_position, has_velocity = position is not None, velocity is not None
    position_lever = np.asarray(position_lever, float).copy()
    velocity_lever = np.asarray(velocity_lever, float).copy()
    angular_rate = np.asarray(angular_rate, float).copy()
    bias_used = has_velocity and np.any(velocity_lever != 0.)
    keys = [pose_key]
    if has_velocity:
        keys.append(velocity_key)
    if bias_used:
        keys.append(bias_key)
    measured = np.concatenate([np.asarray(z, float) for z in (position, velocity) if z is not None])
    dimension = len(measured)
    noise = gtsam.noiseModel.Gaussian.Covariance(np.asarray(covariance, float))

    def error(_factor, values, jacobians):
        pose = values.atPose3(pose_key)
        speed = values.atVector(velocity_key) if has_velocity else np.zeros(3)
        gyro_bias = values.atConstantBias(bias_key).gyroscope() if bias_used else np.zeros(3)
        p, v = gnss_antenna_prediction(pose, speed, gyro_bias, position_lever, velocity_lever, angular_rate)
        if jacobians is not None:
            rotation = pose.rotation().matrix()
            h_pose = np.zeros((dimension, 6), order="F")
            offset = 0
            if has_position:
                h_pose[:3, :3] = -rotation@_skew(position_lever)
                h_pose[:3, 3:] = rotation
                offset = 3
            if has_velocity:
                relative_velocity = np.cross(angular_rate-gyro_bias, velocity_lever)
                h_pose[offset:, :3] = -rotation@_skew(relative_velocity)
                h_velocity = np.zeros((dimension, 3), order="F")
                h_velocity[offset:] = np.eye(3)
                jacobians[1] = h_velocity
                if bias_used:
                    h_bias = np.zeros((dimension, 6), order="F")
                    h_bias[offset:, 3:] = rotation@_skew(velocity_lever)
                    jacobians[2] = h_bias
            jacobians[0] = h_pose
        return np.concatenate([z for z, used in ((p, has_position), (v, has_velocity)) if used])-measured

    return gtsam.CustomFactor(noise, keys, error)
