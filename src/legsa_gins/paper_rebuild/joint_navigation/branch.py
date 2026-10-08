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
from gtsam.symbol_shorthand import X, V, B

from .factors import (carrier_relation_factor, foot_factor, ar1_error_factor,
                      foot_error_coordinate_factor, point3_coordinate_factor, projected_foot_factor,
                      gnss_position_velocity_factor, gnss_antenna_factor, gnss_antenna_prediction)
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
    When both bias random walks are exactly zero, one persistent bias variable
    represents b_k = b_0. This is the equality-constrained model with redundant
    copies eliminated algebraically, not a noise floor or additional prior.
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
        self.constant_bias = bool(np.all(self.bias_rw == 0.0))
        self.bias_key: int | None = None
        self.foot_sigma = float(metadata.get("foot_sigma", .01))
        self.foot_tau = float(metadata.get("foot_correlation_tau_s", .08))
        self.ambiguity_keys: dict[str, int] = {}
        self.contact_keys: dict[str, int] = {}
        self.direction_keys: dict[tuple, int] = {}
        self.foot_history: dict[str, tuple] = {}
        self.direction_history: dict[tuple, tuple] = {}
        # Last latent body-error is keyed by original arc, never by foot subset.
        self.foot_noise_history: dict[str, tuple[int, float]] = {}
        self.support_geometry: dict[str, dict[str, tuple[str, int | None]]] = {}
        self._support_serial = 0
        self._support_retain: set[int] = set()
        self.fixed: dict[str, int] = {}
        self._conditioned_labels: set[str] = set()
        self.time = 0.0
        self.index: int | None = None
        self.pose: gtsam.Pose3 | None = None
        self.velocity: np.ndarray | None = None
        self.bias = gtsam.imuBias.ConstantBias()
        self.last_gnss_innovation: dict = {}
        self.last_factor_counts: dict = {}
        # Controller-owned cumulative predictive support for one actual integer
        # lineage. Values travel with checkpoints; they are never added factors.
        self.predictive_score = 0.0  # -2 log predictive density, including log|S|
        self.predictive_row_count = 0
        self.predictive_frontier = -1
        self.integer_lineage = ()

    @staticmethod
    def _sigmas(value, dimension=3):
        return np.broadcast_to(np.asarray(value, float), (dimension,)).copy()

    def _retained_keys(self) -> set[int]:
        retained = set(self.ambiguity_keys.values()) | self._support_retain
        if self.constant_bias:
            retained.add(B(0))
        return retained

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

    def _support_key(self, symbol):
        key = gtsam.symbol(symbol, self._support_serial)
        self._support_serial += 1
        return key

    def _point(self, key, values):
        return values.atPoint3(key) if values.exists(key) else self.window.values.atPoint3(key)

    def _foot_noise(self, arc, measured, pose, values, times, factors):
        """Expose the original AR error without scoring its previous value twice."""
        history = self.foot_noise_history.get(arc)
        if history is None and arc in self.foot_history:
            old_pose_key, old_measured, old_time = self.foot_history[arc]
            contact_key = self.contact_keys[arc]
            old_key = self._support_key("e")
            old_pose = self.window.values.atPose3(old_pose_key)
            values.insert_point3(old_key, old_pose.transformTo(self._point(contact_key, values))-old_measured)
            factors.append(foot_error_coordinate_factor(old_key, old_pose_key, contact_key, old_measured))
            times[old_key] = old_time
            history = (old_key, old_time)
        key = self._support_key("e")
        if history is None:
            initial = np.zeros(3)
            factors.append(gtsam.PriorFactorPoint3(
                key, initial, gtsam.noiseModel.Isotropic.Sigma(3, self.foot_sigma)))
        else:
            previous_key, previous_time = history
            rho = math.exp(-(self.time-previous_time)/self.foot_tau)
            initial = rho*self._point(previous_key, values)
            factors.append(ar1_error_factor(previous_key, key, rho, self.foot_sigma))
        values.insert_point3(key, initial)
        times[key] = self.time
        self.foot_noise_history[arc] = (key, self.time)
        return key

    def _common_geometry(self, group_id, observed, pose, values, times, factors):
        """Persistent world geometry, with one translation gauge per component.

        Observing a new subset does not create independent directions. Components
        only join when a simultaneous observation genuinely bridges their arcs.
        Existing fixed contacts retain their previous joint posterior; newly
        released groups have no artificial world-position anchor.
        """
        geometry = self.support_geometry.setdefault(group_id, {})
        arcs = [foot["arc_id"] for foot in observed]
        points = {foot["arc_id"]: np.asarray(foot["point_body"], float) for foot in observed}
        for arc in arcs:
            if arc not in geometry and arc in self.contact_keys:
                geometry[arc] = ("world", self.contact_keys[arc])
        known = [arc for arc in arcs if arc in geometry]
        if not known:
            anchor = arcs[0]
            geometry[anchor] = (anchor, None)
            known = [anchor]
        # Prefer a physically anchored component; otherwise keep one existing
        # local gauge. An offset joining another component is inferred solely by
        # the current cross-component observation, never assigned a noise prior.
        anchor = next((arc for arc in known if geometry[arc][0] == "world"), known[0])
        component, anchor_key = geometry[anchor]
        anchor_point = np.zeros(3) if anchor_key is None else self._point(anchor_key, values)
        for other_component in dict.fromkeys(geometry[arc][0] for arc in known):
            if other_component == component:
                continue
            bridge = next(arc for arc in known if geometry[arc][0] == other_component)
            bridge_key = geometry[bridge][1]
            bridge_point = np.zeros(3) if bridge_key is None else self._point(bridge_key, values)
            offset = self._support_key("d")
            initial_offset = anchor_point + pose.rotation().rotate(points[bridge]-points[anchor])-bridge_point
            values.insert_point3(offset, initial_offset)
            times[offset] = self.time
            for arc, (old_component, old_key) in list(geometry.items()):
                if old_component != other_component:
                    continue
                if old_key is None:
                    geometry[arc] = (component, offset)
                else:
                    transformed = self._support_key("d")
                    values.insert_point3(transformed, self._point(old_key, values)+initial_offset)
                    factors.append(point3_coordinate_factor(transformed, {old_key: 1., offset: 1.}))
                    times[transformed] = self.time
                    geometry[arc] = (component, transformed)
        for arc in arcs:
            if arc not in geometry:
                key = self._support_key("d")
                values.insert_point3(key, anchor_point+pose.rotation().rotate(points[arc]-points[anchor]))
                times[key] = self.time
                geometry[arc] = (component, key)
        return [geometry[arc][1] for arc in arcs]

    def _support(self, feet, revoked_arcs, support_models, pose, pose_key, values, times, factors):
        threshold = float(self.metadata.get("force_support_threshold", 60.))
        observed = sorted((f for f in feet if (bool(f["support_eligible"]) if "support_eligible" in f
                                             else float(f["force"]) >= threshold)), key=lambda f: f["foot_id"])
        models = [] if support_models is None else list(support_models)
        if revoked_arcs:
            models.append(dict(group_id="legacy_common_release", arc_ids=tuple(sorted(revoked_arcs)),
                               mode="common_translation_release"))
        assigned = {}
        for model in models:
            mode = model["mode"]
            if mode not in ("fixed", "common_translation_release", "relative_release"):
                raise ValueError(f"unknown contact model {mode}")
            for arc in model["arc_ids"]:
                if arc in assigned:
                    raise ValueError(f"overlapping support model groups for {arc}")
                assigned[arc] = model
        self._support_retain = set()
        added, contrasts = 0, 0
        for foot in observed:
            arc = foot["arc_id"]
            model = assigned.get(arc)
            if model is not None and model["mode"] != "fixed":
                continue
            measured = np.asarray(foot["point_body"], float)
            if arc not in self.contact_keys:
                key = self._support_key("c")
                self.contact_keys[arc] = key
                values.insert_point3(key, pose.transformFrom(measured))
            key = self.contact_keys[arc]
            if arc in self.foot_noise_history:
                noise_key = self._foot_noise(arc, measured, pose, values, times, factors)
                factors.append(foot_error_coordinate_factor(noise_key, pose_key, key, measured))
            else:
                factors.append(foot_factor(pose_key, key, measured, self.foot_sigma,
                                           **self._correlated_options(self.foot_history.get(arc))))
            self.foot_history[arc] = (pose_key, measured.copy(), self.time)
            times[key] = self.time
            added += 1
        for model in models:
            if model["mode"] != "common_translation_release":
                continue
            members = [foot for foot in observed if foot["arc_id"] in model["arc_ids"]]
            # A singleton provides no relative direction. It neither resets the
            # original AR chain nor creates a fresh geometry anchor.
            if len(members) < 2:
                continue
            geometry = self._common_geometry(str(model["group_id"]), members, pose, values, times, factors)
            noise = [self._foot_noise(f["arc_id"], f["point_body"], pose, values, times, factors) for f in members]
            factors.append(projected_foot_factor(pose_key, geometry, noise,
                                                np.array([f["point_body"] for f in members])))
            contrasts += len(members)-1
        # Declared groups outlive temporary visibility/normal departure: their
        # posterior and per-arc error remain available to subsequent evidence.
        live_arcs = set(assigned) | {foot["arc_id"] for foot in observed}
        for arc in live_arcs:
            if arc in self.contact_keys:
                self._support_retain.add(self.contact_keys[arc])
            if arc in self.foot_noise_history:
                self._support_retain.add(self.foot_noise_history[arc][0])
            elif arc in self.foot_history:
                self._support_retain.add(self.foot_history[arc][0])
        for group in self.support_geometry.values():
            self._support_retain.update(key for _, key in group.values() if key is not None)
        return added, contrasts

    def _correlated_options(self, history):
        if history is None:
            return {}
        previous_pose_key, previous_measured, previous_time = history
        return dict(previous_pose_key=previous_pose_key,
                    previous_measured_body=previous_measured,
                    rho=math.exp(-(self.time-previous_time)/self.foot_tau))

    def _preintegrate(self, event, bias):
        preintegrated = gtsam.PreintegratedImuMeasurements(self.imu_params, bias)
        for row in np.asarray(event["imu"], float):
            preintegrated.integrateMeasurement(row[1:4], row[4:7], float(row[0]))
        return preintegrated

    @staticmethod
    def _ordering(keys):
        ordering = gtsam.Ordering()
        for key in keys:
            ordering.push_back(int(key))
        return ordering

    def joint_covariance(self, keys: list[int]) -> np.ndarray:
        """Actual joint marginal, retaining the exact foot-coordinate identities.

        The graph's default elimination can choose Cholesky at an unconstrained
        local clique even when another clique contains exact coordinates. After
        lag marginalization this fails on the strongly scaled bias/integer
        system. Explicit local Jacobian QR avoids forming normal equations;
        COLAMD keeps the query variables last without densifying the whole graph.
        Fixed-contact branches keep their original marginal operation.
        """
        if not self.foot_noise_history:
            joint = gtsam.Marginals(self.window.graph, self.window.values).jointMarginalCovariance(
                gtsam.KeyVector(keys))
            return np.block([[joint.at(a, b) for b in keys] for a in keys])
        linear = self.window.graph.linearize(self.window.values)
        ordering = gtsam.Ordering.ColamdConstrainedLastGaussianFactorGraph(linear, keys, True)
        factors = {j: linear.at(j) for j in range(linear.size())}
        incident = {}
        for j, factor in factors.items():
            for key in factor.keys():
                incident.setdefault(key, set()).add(j)
        next_id = linear.size()
        query = set(keys)
        for index in range(ordering.size()):
            key = ordering.at(index)
            if key in query:
                continue
            local = gtsam.GaussianFactorGraph()
            for j in sorted(incident[key]):
                factor = factors.pop(j)
                local.push_back(factor)
                for neighbor in factor.keys():
                    incident[neighbor].remove(j)
            neighbors = sorted({neighbor for j in range(local.size())
                                for neighbor in local.at(j).keys()} - {key})
            jacobian = gtsam.JacobianFactor(local, self._ordering([key, *neighbors]))
            _, remainder = jacobian.eliminate(self._ordering([key]))
            if remainder.keys():
                factors[next_id] = remainder
                for neighbor in remainder.keys():
                    incident.setdefault(neighbor, set()).add(next_id)
                next_id += 1
        remaining = gtsam.GaussianFactorGraph()
        for factor in factors.values():
            remaining.push_back(factor)
        # Solve the square root directly. The conditional's row sigmas include
        # exact zero rows where applicable; none are replaced by a noise floor.
        jacobian = gtsam.JacobianFactor(remaining, self._ordering(keys))
        conditional, _ = jacobian.eliminate(self._ordering(keys))
        covariance_root = np.linalg.solve(conditional.R(), np.diag(conditional.get_model().sigmas()))
        return covariance_root @ covariance_root.T

    @staticmethod
    def _skew(vector):
        x, y, z = vector
        return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])

    def _gnss_inputs(self, event, predicted_pose):
        """Physical antenna input and working source covariance, shared by both paths.

        The gyro-rate variance is retained. Its reuse in IMU propagation and
        across asynchronous packets is explicitly an unmodelled cross covariance
        in this first field-data interface, not an independent high-precision rate.
        """
        present = [name for name in ("gnss_position", "gnss_velocity") if event.get(name) is not None]
        position_lever = np.asarray(event.get("gnss_position_leverarm_body_m",
                                   self.metadata.get("gnss_leverarm_body_m", np.zeros(3))), float)
        velocity_lever = np.asarray(event.get("gnss_velocity_leverarm_body_m",
                                   self.metadata.get("gnss_leverarm_body_m", np.zeros(3))), float)
        angular_rate = np.zeros(3)
        gyro_covariance = np.zeros((3, 3))
        angular_source_time = None
        angular_source_interval = None
        uses_gyro = "gnss_velocity" in present and np.any(velocity_lever != 0.)
        if uses_gyro:
            if event.get("gnss_angular_rate_body_rad_s") is not None:
                angular_rate = np.asarray(event["gnss_angular_rate_body_rad_s"], float)
                angular_source_time = event["gnss_angular_rate_source_time_s"]
            else:
                if len(event["imu"]) == 0:
                    raise ValueError("antenna velocity requires a causal observed angular-rate sample")
                angular_rate = np.asarray(event["imu"][-1, 4:7], float)
                sources = event.get("imu_interval_sources")
                angular_source_time = float(sources[-1, 2]) if sources is not None and len(sources) else event["time_s"]
            if angular_source_time > event["time_s"]:
                raise ValueError("antenna angular rate is not yet available at the measurement event")
            angular_source_interval = event.get("last_gyro_source_noise_interval_s")
            if angular_source_interval is None:
                angular_source_interval = event.get("source_noise_interval_s")
            if angular_source_interval is None:
                sources = event.get("imu_interval_sources")
                if sources is not None and len(sources) and np.shape(sources)[1] >= 4:
                    angular_source_interval = float(sources[-1, 3])
            if angular_source_interval is None or angular_source_interval <= 0.:
                raise ValueError("antenna gyro variance requires the original source sample interval")
            density = self._sigmas(self.metadata.get("gyro_noise_density", .001))
            gyro_covariance = np.diag(density**2/float(angular_source_interval))
        covariance = np.zeros((3*len(present), 3*len(present)))
        slices = {name: slice(3*i, 3*i+3) for i, name in enumerate(present)}
        has_event_covariance = any(event.get(name+"_covariance") is not None for name in present)
        joint = event.get("gnss_position_velocity_covariance")
        if joint is None and not has_event_covariance:
            joint = self.metadata.get("gnss_position_velocity_covariance")
        if len(present) == 2 and joint is not None:
            covariance[:] = np.asarray(joint, float)
        else:
            for name in present:
                source = event.get(name+"_covariance")
                default = .05 if name == "gnss_position" else .03
                if source is None:
                    source = np.diag(self._sigmas(self.metadata.get(name+"_sigma", default))**2)
                covariance[slices[name], slices[name]] = source
        if uses_gyro:
            gyro_map = -predicted_pose.rotation().matrix()@self._skew(velocity_lever)
            covariance[slices["gnss_velocity"], slices["gnss_velocity"]] += gyro_map@gyro_covariance@gyro_map.T
        return dict(position_lever=position_lever, velocity_lever=velocity_lever,
                    angular_rate=angular_rate, covariance=covariance, slices=slices,
                    uses_gyro=uses_gyro, angular_source_time_s=angular_source_time,
                    angular_source_noise_interval_s=angular_source_interval,
                    gyro_covariance=gyro_covariance,
                    source_covariance_assumption=(
                        "gyro_sample_variance_retained;shared_IMU_and_cross_packet_gyro_cross_unmodelled"
                        if uses_gyro else "no_angular_rate_noise_in_zero_velocity_lever_model"),
                    custom=(has_event_covariance or event.get("gnss_position_velocity_covariance") is not None or
                            ("gnss_position" in present and np.any(position_lever != 0.)) or uses_gyro))

    def predict_gnss_position(self, event: dict) -> tuple[np.ndarray, np.ndarray]:
        """Legacy position-only view of the same not-yet-consumed joint model."""
        prediction = self.predict_external(dict(event, gnss_velocity=None, carrier=None))
        return prediction["innovation"], prediction["covariance"]

    def predict_external(self, event: dict) -> dict:
        """Joint predictive density ingredients before consuming this event.

        Include observed GNSS position/velocity and raw code/carrier rows whose
        ambiguity labels already have posterior variables. Rows depending on a
        new unknown ambiguity are omitted, never initialized using the row being
        scored. Shared state, ambiguity and preintegration cross covariance is
        retained. Synthetic GNSS product/raw-row independence is the declared
        working source model, not an assertion about receiver products in field
        data. No likelihood or state mutation is performed by this method.
        """
        timestamp = float(event["time_s"])
        pose = self.window.values.atPose3(X(self.index))
        velocity = self.window.values.atVector(V(self.index))
        bias = self.window.values.atConstantBias(self.bias_key)
        preintegrated = self._preintegrate(event, bias)
        predicted_state = preintegrated.predict(gtsam.NavState(pose, velocity), bias)
        gnss_inputs = self._gnss_inputs(event, predicted_state.pose())
        block = event.get("carrier")
        known_labels, selected_rows, excluded_rows = [], np.empty(0, int), []
        if block is not None:
            labels = tuple(block.ambiguity_labels)
            unknown_columns = [j for j, label in enumerate(labels) if label not in self.ambiguity_keys]
            used = np.ones(len(block.y), bool)
            if unknown_columns:
                used &= np.all(np.asarray(block.A)[:, unknown_columns] == 0., axis=1)
            selected_rows = np.flatnonzero(used)
            excluded_rows = np.flatnonzero(~used).tolist()
            known_labels = [label for j, label in enumerate(labels)
                            if label in self.ambiguity_keys and
                            np.any(np.asarray(block.A)[selected_rows, j] != 0.)]
        keys = [X(self.index), V(self.index), self.bias_key,
                *[self.ambiguity_keys[label] for label in known_labels]]
        prior_covariance = self.joint_covariance(keys)
        n0 = np.array([self.window.values.atVector(self.ambiguity_keys[label])[0]
                       for label in known_labels])
        observations, noise_blocks, identities, row_identities, slices = [], [], [], [], {}
        dimension = 0
        for name, metadata_name, default in (
            ("gnss_position", "gnss_position_sigma", .05),
            ("gnss_velocity", "gnss_velocity_sigma", .03),
        ):
            if event.get(name) is not None:
                observations.append(np.asarray(event[name], float))
                noise_blocks.append(np.diag(self._sigmas(self.metadata.get(metadata_name, default)) ** 2))
                slices[name] = slice(dimension, dimension+3)
                dimension += 3
                identity = f"{name}:{timestamp:.9f}"
                identities.append(identity)
                row_identities.extend(f"{identity}:{axis}" for axis in range(3))
        if len(selected_rows):
            observations.append(np.asarray(block.y)[selected_rows])
            noise_blocks.append(np.asarray(block.Q)[np.ix_(selected_rows, selected_rows)])
            slices["carrier"] = slice(dimension, dimension+len(selected_rows))
            dimension += len(selected_rows)
            identities.append(f"raw_code_carrier:{timestamp:.9f}")
            row_identities.extend(f"raw_code_carrier:{timestamp:.9f}:row{row}" for row in selected_rows)
            columns = [tuple(block.ambiguity_labels).index(label) for label in known_labels]
            carrier_A = np.asarray(block.A)[np.ix_(selected_rows, columns)]
            carrier_B = np.asarray(block.B)[selected_rows]

        def measurement(rotation, position, speed, integers, gyro_bias):
            antenna_position, antenna_velocity = gnss_antenna_prediction(
                gtsam.Pose3(rotation, position), speed, gyro_bias,
                gnss_inputs["position_lever"], gnss_inputs["velocity_lever"], gnss_inputs["angular_rate"])
            parts = []
            if "gnss_position" in slices:
                parts.append(antenna_position)
            if "gnss_velocity" in slices:
                parts.append(antenna_velocity)
            if "carrier" in slices:
                parts.append(carrier_B @ rotation.rotate(self.baseline_body) + carrier_A @ integers)
            return np.concatenate(parts) if parts else np.empty(0)

        def prediction_at(delta):
            shifted_bias = gtsam.imuBias.ConstantBias(
                bias.accelerometer()+delta[9:12], bias.gyroscope()+delta[12:15])
            state = preintegrated.predict(
                gtsam.NavState(pose.retract(delta[:6]), velocity+delta[6:9]), shifted_bias)
            return measurement(state.attitude(), state.position(), state.velocity(), n0+delta[15:], shifted_bias.gyroscope())

        predicted = prediction_at(np.zeros(15+len(known_labels)))
        state_jacobian = np.empty((dimension, 15+len(known_labels)))
        epsilon = 1e-6
        for column in range(state_jacobian.shape[1]):
            delta = np.zeros(state_jacobian.shape[1])
            delta[column] = epsilon
            state_jacobian[:, column] = (prediction_at(delta)-prediction_at(-delta))/(2*epsilon)

        # Use the actual ImuFactor residual coordinates. PIM covariance is not
        # generally a block of independent end-rotation/start-frame p/v errors;
        # hand-rotating its blocks loses process cross terms during rotation.
        # E maps predicted end-state tangent [Pose3 local(6), world velocity(3)]
        # to the factor's 9D residual, so H E^-1 maps its full Q to observations.
        predicted_pose = predicted_state.pose()
        predicted_velocity = predicted_state.velocity()
        imu_factor = gtsam.ImuFactor(X(self.index), V(self.index), X(self.index+1),
                                     V(self.index+1), self.bias_key, preintegrated)

        def process_at(delta):
            shifted_pose = predicted_pose.retract(delta[:6])
            shifted_velocity = predicted_velocity+delta[6:9]
            predicted = measurement(shifted_pose.rotation(), shifted_pose.translation(), shifted_velocity, n0, bias.gyroscope())
            residual = imu_factor.evaluateError(pose, velocity, shifted_pose, shifted_velocity, bias)
            return predicted, residual

        observation_end_jacobian = np.empty((dimension, 9))
        error_end_jacobian = np.empty((9, 9))
        for column in range(9):
            delta = np.zeros(9)
            delta[column] = epsilon
            plus_measurement, plus_error = process_at(delta)
            minus_measurement, minus_error = process_at(-delta)
            observation_end_jacobian[:, column] = (plus_measurement-minus_measurement)/(2*epsilon)
            error_end_jacobian[:, column] = (plus_error-minus_error)/(2*epsilon)
        process_jacobian = np.linalg.solve(error_end_jacobian.T, observation_end_jacobian.T).T
        sensor_covariance = np.zeros((dimension, dimension))
        offset = 0
        for noise in noise_blocks:
            size = len(noise)
            sensor_covariance[offset:offset+size, offset:offset+size] = noise
            offset += size
        gnss_dimension = len(gnss_inputs["covariance"])
        sensor_covariance[:gnss_dimension, :gnss_dimension] = gnss_inputs["covariance"]
        # The mean new bias equals the old bias; its independent interval random
        # walk also enters the antenna velocity likelihood through current b_g.
        bias_process_covariance = np.zeros((dimension, dimension))
        if gnss_inputs["uses_gyro"] and not self.constant_bias:
            bg_map = predicted_state.attitude().matrix()@self._skew(gnss_inputs["velocity_lever"])
            bg_cov = np.diag(self.bias_rw[3:]**2*(timestamp-self.time))
            target = slices["gnss_velocity"]
            bias_process_covariance[target, target] = bg_map@bg_cov@bg_map.T
        covariance = (state_jacobian@prior_covariance@state_jacobian.T +
                      process_jacobian@preintegrated.preintMeasCov()@process_jacobian.T +
                      sensor_covariance + bias_process_covariance)
        covariance = .5*(covariance+covariance.T)
        observed = np.concatenate(observations) if observations else np.empty(0)
        return dict(
            innovation=observed-predicted, covariance=covariance,
            observed=observed, predicted=predicted,
            event_id=f"independent:{timestamp:.9f}", observation_ids=tuple(identities),
            row_ids=tuple(row_identities), existing_ambiguity_labels=tuple(known_labels),
            excluded_unknown_ambiguity_rows=excluded_rows,
            prior_time_s=self.time, measurement_time_s=timestamp,
            source_noise_assumption=self.metadata.get("source_noise_assumption",
                "working_independent_GNSS_product_and_raw_blocks_except_declared_covariances"),
            conditional_on_branch=True,
            source_covariance_assumption=gnss_inputs["source_covariance_assumption"],
            angular_rate_source_time_s=gnss_inputs["angular_source_time_s"],
            angular_rate_source_noise_interval_s=gnss_inputs["angular_source_noise_interval_s"],
        )

    # Compatibility with the interrupted implementation's provisional API.
    predict_independent = predict_external

    def step(self, event: dict, index: int, revoked_arcs: set[str] | None = None,
             *, support_models: list[dict] | None = None):
        """Consume one causal event and return pose, velocity, bias, cost."""
        revoked_arcs = set() if revoked_arcs is None else revoked_arcs
        previous_index, previous_time = self.index, self.time
        self.time = float(event["time_s"])
        self.index = int(index)
        pose_key, velocity_key = X(index), V(index)
        bias_key = B(0) if self.constant_bias else B(index)
        self.bias_key = bias_key
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
            preintegrated = self._preintegrate(event, self.bias)
            prediction = preintegrated.predict(gtsam.NavState(self.pose, self.velocity), self.bias)
            predicted_pose, predicted_velocity = prediction.pose(), prediction.velocity()
            factors.append(gtsam.ImuFactor(
                X(previous_index), V(previous_index), pose_key, velocity_key,
                B(0) if self.constant_bias else B(previous_index), preintegrated))
            if not self.constant_bias:
                factors.append(gtsam.BetweenFactorConstantBias(
                    B(previous_index), bias_key, gtsam.imuBias.ConstantBias(),
                    gtsam.noiseModel.Diagonal.Sigmas(self.bias_rw * math.sqrt(self.time-previous_time))))
        values.insert(pose_key, predicted_pose)
        values.insert(velocity_key, predicted_velocity)
        if previous_index is None or not self.constant_bias:
            values.insert(bias_key, self.bias)

        position, velocity = event.get("gnss_position"), event.get("gnss_velocity")
        gnss_inputs = self._gnss_inputs(event, predicted_pose)
        antenna_position, antenna_velocity = gnss_antenna_prediction(
            predicted_pose, predicted_velocity, self.bias.gyroscope(),
            gnss_inputs["position_lever"], gnss_inputs["velocity_lever"], gnss_inputs["angular_rate"])
        if position is not None:
            self.last_gnss_innovation["position"] = np.asarray(position)-antenna_position
        if velocity is not None:
            self.last_gnss_innovation["velocity"] = np.asarray(velocity)-antenna_velocity
        if gnss_inputs["custom"] and (position is not None or velocity is not None):
            factors.append(gnss_antenna_factor(
                pose_key, velocity_key, bias_key, position, velocity, gnss_inputs["covariance"],
                gnss_inputs["position_lever"], gnss_inputs["velocity_lever"], gnss_inputs["angular_rate"]))
            self.last_gnss_innovation["source_covariance_assumption"] = gnss_inputs["source_covariance_assumption"]
        elif position is not None and velocity is not None and "gnss_position_velocity_covariance" in self.metadata:
            factors.append(gnss_position_velocity_factor(
                pose_key, velocity_key, position, velocity,
                np.asarray(self.metadata["gnss_position_velocity_covariance"], float)))
        else:
            # Preserve the original zero-lever synthetic numerical path.
            if position is not None:
                factors.append(gtsam.GPSFactor(
                    pose_key, np.asarray(position, float), gtsam.noiseModel.Diagonal.Sigmas(
                        self._sigmas(self.metadata.get("gnss_position_sigma", .05)))))
            if velocity is not None:
                factors.append(gtsam.PriorFactorVector(
                    velocity_key, np.asarray(velocity, float), gtsam.noiseModel.Diagonal.Sigmas(
                        self._sigmas(self.metadata.get("gnss_velocity_sigma", .03)))))
        block = event.get("carrier")
        if block is not None:
            self._carrier(block, predicted_pose, pose_key, values, times, factors)
        nfoot, ndifference = (0, 0)
        if self.use_foot:
            nfoot, ndifference = self._support(
                event.get("feet", []), revoked_arcs, support_models, predicted_pose, pose_key, values, times, factors)
        self.window.update(factors, values, times, self.time,
                           retain_keys=self._retained_keys())
        self.last_factor_counts = dict(
            foot=nfoot, differential=ndifference,
            carrier_rows=0 if block is None else len(block.y),
            total=len(factors), imu_intervals=len(event["imu"]))
        return self._current()

    def _current(self):
        self.pose = self.window.values.atPose3(X(self.index))
        self.velocity = self.window.values.atVector(V(self.index)).copy()
        self.bias = self.window.values.atConstantBias(self.bias_key)
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
                               retain_keys=self._retained_keys())
        return self._current()

    def snapshot(self) -> BranchSnapshot:
        names = ("ambiguity_keys", "contact_keys", "direction_keys", "foot_history",
                 "direction_history", "fixed", "_conditioned_labels", "time", "index",
                 "last_gnss_innovation", "last_factor_counts", "constant_bias", "bias_key",
                 "foot_noise_history", "support_geometry", "_support_serial", "_support_retain",
                 "predictive_score", "predictive_row_count", "predictive_frontier", "integer_lineage")
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
