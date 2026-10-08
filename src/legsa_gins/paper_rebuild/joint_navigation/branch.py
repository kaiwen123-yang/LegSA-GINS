"""One conditional shared navigation trajectory in the joint arc estimator.

The controller supplies causal events, chooses integer relations and restores
checkpoints when a source is withdrawn. This class never receives simulation
truth, chooses a candidate, or rewrites an already published trajectory.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math

import gtsam
import numpy as np
from scipy.linalg import helmert
from gtsam.symbol_shorthand import X, V, B

from .factors import carrier_relation_factor, differential_foot_factor, foot_factor
from .window import JointWindow, WindowSnapshot


@dataclass(frozen=True)
class BranchSnapshot:
    window: WindowSnapshot
    state: dict


class NavigationBranch:
    """Conditional R/p/v/b/contact/ambiguity state with a five-second lag.

    Working defaults, when absent from source metadata: accelerometer/gyro
    noise densities 0.02 and 0.001, bias random walks 1e-4 and 1e-5,
    position/velocity sigma 0.05/0.03 m(/s), foot sigma 0.01 m and tau 0.08 s.
    Explicit zero bias random walk means an exact constant-bias constraint.
    """

    def __init__(self, metadata: dict, use_foot: bool = True):
        self.metadata = deepcopy(metadata)
        self.use_foot = bool(use_foot)
        self.window = JointWindow(float(metadata.get("lag_s", 5.0)))
        self.baseline_body = np.asarray(metadata["baseline_body"], float).copy()
        gravity = np.asarray(metadata.get("gravity_n", [0., 0., 9.81]), float)
        self.imu_params = gtsam.PreintegrationParams(gravity)
        self.imu_params.setAccelerometerCovariance(
            np.eye(3) * float(metadata.get("accel_noise_density", .02)) ** 2)
        self.imu_params.setGyroscopeCovariance(
            np.eye(3) * float(metadata.get("gyro_noise_density", .001)) ** 2)
        self.imu_params.setIntegrationCovariance(np.eye(3) * 1e-10)
        self.bias_rw = np.r_[
            np.full(3, float(metadata.get("accel_bias_random_walk", 1e-4))),
            np.full(3, float(metadata.get("gyro_bias_random_walk", 1e-5))),
        ]
        self.foot_sigma = float(metadata.get("foot_sigma", .01))
        self.foot_tau = float(metadata.get("foot_correlation_tau_s", .08))
        self.ambiguity_keys: dict[str, int] = {}
        self.contact_keys: dict[str, int] = {}
        self.direction_keys: dict[tuple, int] = {}
        self.foot_history: dict[str, tuple] = {}
        self.direction_history: dict[tuple, tuple] = {}
        self.fixed: dict[str, int] = {}
        self._conditioned_labels: set[str] = set()
        self.time = 0.0
        self.index: int | None = None
        self.pose: gtsam.Pose3 | None = None
        self.velocity: np.ndarray | None = None
        self.bias = gtsam.imuBias.ConstantBias()
        self.last_gnss_innovation: dict = {}
        self.last_factor_counts: dict = {}

    @staticmethod
    def _sigmas(value, dimension=3):
        return np.broadcast_to(np.asarray(value, float), (dimension,)).copy()

    def _initial_pose(self, event: dict) -> gtsam.Pose3:
        block = event["carrier"]
        if block is None:
            raise ValueError("initial direction needs observed code geometry")
        rows = np.flatnonzero(np.all(np.asarray(block.A) == 0., axis=1))
        chol = np.linalg.cholesky(np.asarray(block.Q)[np.ix_(rows, rows)])
        design = np.linalg.solve(chol, np.asarray(block.B)[rows])
        measured = np.linalg.solve(chol, np.asarray(block.y)[rows])
        baseline, _, _, _ = np.linalg.lstsq(design, measured, rcond=None)
        yaw = math.atan2(float(baseline[0]), float(-baseline[1]))
        return gtsam.Pose3(gtsam.Rot3.Ypr(yaw, 0., 0.),
                          np.asarray(event["gnss_position"], float))

    def _fixed_factor(self, label: str):
        self._conditioned_labels.add(label)
        return gtsam.PriorFactorVector(
            self.ambiguity_keys[label], np.array([float(self.fixed[label])]),
            gtsam.noiseModel.Isotropic.Sigma(1, 1e-5))

    @staticmethod
    def _contrast_coordinates(direction_key, contact_keys, coefficients):
        """Define d = H*c exactly when changing an existing contact model.

        This is a coordinate relation on existing unknowns, not a new sensor
        likelihood. It carries their previous covariance into the contrast.
        """
        contact_keys = tuple(contact_keys)
        coefficients = np.asarray(coefficients, float).copy()

        def error(_factor, values, jacobians):
            residual = values.atPoint3(direction_key).copy()
            if jacobians is not None:
                jacobians[0] = np.eye(3, order="F")
            for j, (key, coefficient) in enumerate(zip(contact_keys, coefficients)):
                residual -= coefficient * values.atPoint3(key)
                if jacobians is not None:
                    jacobians[j+1] = np.asfortranarray(-coefficient * np.eye(3))
            return residual

        return gtsam.CustomFactor(gtsam.noiseModel.Constrained.All(3),
                                  [direction_key, *contact_keys], error)

    def _carrier(self, block, pose, pose_key, values, times, factors):
        labels = tuple(block.ambiguity_labels)
        unknown = [label for label in labels if label not in self.ambiguity_keys]
        residual = np.asarray(block.y, float) - np.asarray(block.B) @ pose.rotation().rotate(self.baseline_body)
        for j, label in enumerate(labels):
            if label not in unknown:
                residual -= np.asarray(block.A)[:, j] * self.window.values.atVector(self.ambiguity_keys[label])[0]
        if unknown:
            columns = [labels.index(label) for label in unknown]
            chol = np.linalg.cholesky(np.asarray(block.Q))
            whitened_design = np.linalg.solve(chol, np.asarray(block.A)[:, columns])
            initial, _, _, _ = np.linalg.lstsq(
                whitened_design, np.linalg.solve(chol, residual), rcond=None)
            for label, estimate in zip(unknown, initial):
                key = gtsam.symbol("a", len(self.ambiguity_keys))
                self.ambiguity_keys[label] = key
                values.insert_vector(key, np.array([float(estimate)]))
                if label in self.fixed:
                    factors.append(self._fixed_factor(label))
        keys = [self.ambiguity_keys[label] for label in labels]
        times.update({key: self.time for key in keys})
        factors.append(carrier_relation_factor(pose_key, keys, block, self.baseline_body))

    def _support(self, feet, revoked_arcs, pose, pose_key, values, times, factors):
        observed = sorted(feet, key=lambda foot: foot["foot_id"])
        force_threshold = float(self.metadata.get("force_support_threshold", 60.))
        observed = [foot for foot in observed if float(foot["force"]) >= force_threshold]
        arcs = tuple(foot["arc_id"] for foot in observed)
        # Revocation here means the observed common-translation model failed;
        # the controller must not use this mode for relative-geometry failure.
        common_withdrawn = len(observed) == 4 and any(arc in revoked_arcs for arc in arcs)
        if common_withdrawn:
            transform = helmert(4)
            contrasts = transform @ np.vstack([foot["point_body"] for foot in observed])
            for contrast_index, measured in enumerate(contrasts):
                identity = (arcs, contrast_index)
                if identity not in self.direction_keys:
                    key = gtsam.symbol("d", len(self.direction_keys))
                    self.direction_keys[identity] = key
                    existing_contacts = all(
                        arc in self.contact_keys and self.window.values.exists(self.contact_keys[arc])
                        for arc in arcs)
                    if existing_contacts:
                        contact_keys = [self.contact_keys[arc] for arc in arcs]
                        prior_points = np.vstack([self.window.values.atPoint3(k) for k in contact_keys])
                        values.insert_point3(key, transform[contrast_index] @ prior_points)
                        factors.append(self._contrast_coordinates(
                            key, contact_keys, transform[contrast_index]))
                        histories = [self.foot_history[arc] for arc in arcs]
                        if len({history[0] for history in histories}) == 1:
                            self.direction_history[identity] = (
                                histories[0][0],
                                transform[contrast_index] @ np.vstack([h[1] for h in histories]),
                                histories[0][2])
                    else:
                        values.insert_point3(key, pose.rotation().rotate(measured))
                key = self.direction_keys[identity]
                history = self.direction_history.get(identity)
                options = self._correlated_options(history)
                factors.append(differential_foot_factor(
                    pose_key, key, measured, self.foot_sigma, **options))
                self.direction_history[identity] = (pose_key, np.asarray(measured).copy(), self.time)
                times[key] = self.time
            return 0, len(contrasts)

        added = 0
        for foot in observed:
            arc = foot["arc_id"]
            if arc in revoked_arcs:
                continue
            measured = np.asarray(foot["point_body"], float)
            if arc not in self.contact_keys:
                key = gtsam.symbol("c", len(self.contact_keys))
                self.contact_keys[arc] = key
                values.insert_point3(key, pose.transformFrom(measured))
            key = self.contact_keys[arc]
            options = self._correlated_options(self.foot_history.get(arc))
            factors.append(foot_factor(pose_key, key, measured, self.foot_sigma, **options))
            self.foot_history[arc] = (pose_key, measured.copy(), self.time)
            times[key] = self.time
            added += 1
        return added, 0

    def _correlated_options(self, history):
        if history is None:
            return {}
        previous_pose_key, previous_measured, previous_time = history
        return dict(previous_pose_key=previous_pose_key,
                    previous_measured_body=previous_measured,
                    rho=math.exp(-(self.time-previous_time)/self.foot_tau))

    def step(self, event: dict, index: int, revoked_arcs: set[str] | None = None):
        """Consume one causal event and return pose, velocity, bias, cost."""
        revoked_arcs = set() if revoked_arcs is None else revoked_arcs
        previous_index, previous_time = self.index, self.time
        self.time = float(event["time_s"])
        self.index = int(index)
        pose_key, velocity_key, bias_key = X(index), V(index), B(index)
        values, factors = gtsam.Values(), []
        times = {pose_key: self.time, velocity_key: self.time, bias_key: self.time}
        self.last_gnss_innovation = {}
        if previous_index is None:
            predicted_pose = self._initial_pose(event)
            predicted_velocity = np.asarray(event["gnss_velocity"], float).copy()
            # Code-derived yaw is an optimizer initial value, not another yaw
            # observation. The effectively free yaw/position prior only leaves
            # the declared broad upright roll/pitch initialization informative.
            rotation_sigmas = [math.radians(20.), math.radians(20.), 1e6]
            factors.append(gtsam.PriorFactorPose3(
                pose_key, predicted_pose,
                gtsam.noiseModel.Diagonal.Sigmas(np.r_[rotation_sigmas, [1e6]*3])))
            bias_sigma = np.r_[
                np.full(3, float(self.metadata.get("accel_bias_prior_sigma", .03))),
                np.full(3, float(self.metadata.get("gyro_bias_prior_sigma", .003)))]
            factors.append(gtsam.PriorFactorConstantBias(
                bias_key, self.bias, gtsam.noiseModel.Diagonal.Sigmas(bias_sigma)))
        else:
            preintegrated = gtsam.PreintegratedImuMeasurements(self.imu_params, self.bias)
            for row in np.asarray(event["imu"], float):
                preintegrated.integrateMeasurement(row[1:4], row[4:7], float(row[0]))
            prediction = preintegrated.predict(gtsam.NavState(self.pose, self.velocity), self.bias)
            predicted_pose, predicted_velocity = prediction.pose(), prediction.velocity()
            factors.append(gtsam.ImuFactor(
                X(previous_index), V(previous_index), pose_key, velocity_key,
                B(previous_index), preintegrated))
            factors.append(gtsam.BetweenFactorConstantBias(
                B(previous_index), bias_key, gtsam.imuBias.ConstantBias(),
                gtsam.noiseModel.Diagonal.Sigmas(self.bias_rw * math.sqrt(self.time-previous_time))))
        values.insert(pose_key, predicted_pose)
        values.insert(velocity_key, predicted_velocity)
        values.insert(bias_key, self.bias)

        position, velocity = event.get("gnss_position"), event.get("gnss_velocity")
        if position is not None:
            self.last_gnss_innovation["position"] = np.asarray(position)-predicted_pose.translation()
            factors.append(gtsam.GPSFactor(
                pose_key, np.asarray(position, float), gtsam.noiseModel.Diagonal.Sigmas(
                    self._sigmas(self.metadata.get("gnss_position_sigma", .05)))))
        if velocity is not None:
            self.last_gnss_innovation["velocity"] = np.asarray(velocity)-predicted_velocity
            factors.append(gtsam.PriorFactorVector(
                velocity_key, np.asarray(velocity, float), gtsam.noiseModel.Diagonal.Sigmas(
                    self._sigmas(self.metadata.get("gnss_velocity_sigma", .03)))))
        block = event.get("carrier")
        if block is not None:
            self._carrier(block, predicted_pose, pose_key, values, times, factors)
        nfoot, ndifference = (0, 0)
        if self.use_foot:
            nfoot, ndifference = self._support(
                event.get("feet", []), revoked_arcs, predicted_pose, pose_key, values, times, factors)
        self.window.update(factors, values, times, self.time,
                           retain_keys=set(self.ambiguity_keys.values()))
        self.last_factor_counts = dict(
            foot=nfoot, differential=ndifference,
            carrier_rows=0 if block is None else len(block.y),
            total=len(factors), imu_intervals=len(event["imu"]))
        return self._current()

    def _current(self):
        self.pose = self.window.values.atPose3(X(self.index))
        self.velocity = self.window.values.atVector(V(self.index)).copy()
        self.bias = self.window.values.atConstantBias(B(self.index))
        return self.pose, self.velocity.copy(), self.bias, self.window.error()

    def current_output(self) -> dict:
        """Current conditional navigation state, with no truth/evaluation data."""
        self._current()
        return dict(
            p=self.pose.translation().copy(), v=self.velocity.copy(),
            rpy_rad=self.pose.rotation().rpy().copy(),
            bias=np.r_[self.bias.accelerometer(), self.bias.gyroscope()],
        )

    def condition(self, integer_by_label: dict[str, int]):
        """Add explicit scalar integer relations once; leave other labels float."""
        factors = []
        for label, integer in integer_by_label.items():
            integer = int(integer)
            if label in self.fixed and self.fixed[label] != integer:
                raise ValueError(f"conflicting condition for physical relation {label}")
            self.fixed[label] = integer
            if label in self.ambiguity_keys and label not in self._conditioned_labels:
                factors.append(self._fixed_factor(label))
        if factors:
            self.window.update(factors, gtsam.Values(), {}, self.time,
                               retain_keys=set(self.ambiguity_keys.values()))
        return self._current()

    def snapshot(self) -> BranchSnapshot:
        names = ("ambiguity_keys", "contact_keys", "direction_keys", "foot_history",
                 "direction_history", "fixed", "_conditioned_labels", "time", "index",
                 "last_gnss_innovation", "last_factor_counts")
        return BranchSnapshot(self.window.snapshot(),
                              {name: deepcopy(getattr(self, name)) for name in names})

    def restore(self, snapshot: BranchSnapshot):
        self.window.restore(snapshot.window)
        for name, value in snapshot.state.items():
            setattr(self, name, deepcopy(value))
        if self.index is None:
            self.pose, self.velocity = None, None
            self.bias = gtsam.imuBias.ConstantBias()
            return None
        return self._current()
