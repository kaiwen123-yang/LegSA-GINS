"""One conditional shared navigation trajectory in the joint arc estimator.

The controller supplies causal events, chooses integer relations and restores
checkpoints when a source is withdrawn. This class never receives simulation
truth, chooses a candidate, or rewrites an already published trajectory.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
import math

import gtsam
import numpy as np
from gtsam.symbol_shorthand import X, V, B

from .factors import (carrier_relation_factor, source_ou_factor, foot_factor, ar1_error_factor,
                      foot_error_coordinate_factor, point3_coordinate_factor, projected_foot_factor,
                      gnss_position_velocity_factor, gnss_antenna_factor, gnss_antenna_prediction, gravity_tilt_factor,
                      FootErrorExpression, algebraic_foot_error_factor)
from .window import JointWindow, WindowSnapshot, eliminate_qr
from .carrier_relations import CarrierRelationTracker
from .source_noise_likelihood import physical_source_incidence, PhysicalSourceIncidence


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
        self._ambiguity_serial = 0
        self.phase_noise_model = deepcopy(metadata.get("phase_noise_model"))
        if self.phase_noise_model is not None:
            white = float(self.phase_noise_model["white_sd_sigma_m"])
            beta = float(self.phase_noise_model["beta_sd_sigma_m"])
            tau = float(self.phase_noise_model["tau_s"])
            if not all(math.isfinite(v) for v in (white, beta, tau)) or min(white, beta) < 0. or tau <= 0.:
                raise ValueError("phase source model needs finite nonnegative SD sigmas and positive tau")
        self.phase_beta_keys: dict[str, int] = {}
        self.phase_beta_times: dict[str, float] = {}
        self.phase_beta_coordinates: dict[tuple[str, float], int] = {}
        self._phase_beta_serial = 0
        self._carrier_relation_tracker = CarrierRelationTracker(
            label_mode=metadata.get("carrier_label_mode", "synthetic_scalar"))
        self._carrier_coordinate_constraints: set[tuple] = set()
        self.last_carrier_relations: dict = {}
        self.contact_keys: dict[str, int] = {}
        self.direction_keys: dict[tuple, int] = {}
        self.foot_history: dict[str, tuple] = {}
        self.direction_history: dict[tuple, tuple] = {}
        # The original per-arc body error is an exact expression in R/p/d/q.
        # It is never an independently optimized redundant equality coordinate.
        self.foot_error_history: dict[str, tuple[FootErrorExpression, float]] = {}
        self.support_geometry: dict[str, dict[str, tuple[str, int | None]]] = {}
        self._support_serial = 0
        self._support_retain: set[int] = set()
        # Only the explicit separator mode consumes lifecycle evidence. Missing
        # foot measurements alone never close a source arc.
        self._support_arc_foot: dict[str, int] = {}
        self._support_pending_closed: set[str] = set()
        self._support_state_time: float | None = None
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
        self.bootstrap_status = "NOT_REQUESTED"
        self.bootstrap_diagnostics = {}
        self.linearization_scope = {"kind": "FULL_NONLINEAR_CONDITIONAL"}
        if self.phase_noise_model is not None:
            self.linearization_scope["phase_source_scope"] = self._phase_noise_scope()
        self._factor_seed_values = None
        self.background_chart_id = ("SYNTHETIC_CODE_INITIALIZATION",)

    def export_linearization_anchor(self) -> dict:
        """Copy a background chart with physical, rather than local-key, identity.

        A controller can store this before startup marginalization and at each
        history frontier. An exported conditional Gaussian mean is explicitly
        identified and must not be mistaken for a nonlinear background solve.
        """
        return dict(values=gtsam.Values(self.window.values),
                    ambiguity_keys=dict(self.ambiguity_keys), contact_keys=dict(self.contact_keys),
                    phase_beta_coordinates={identity: key for identity, key in self.phase_beta_coordinates.items()
                                            if self.window.values.exists(key)},
                    index=self.index, time_s=self.time, integer_lineage=deepcopy(self.integer_lineage),
                    background_chart_id=deepcopy(self.background_chart_id),
                    scope=("GAUSSIAN_CONDITIONAL_MEAN" if self.window.gaussian_only else
                           "BACKGROUND_NONLINEAR_ANCHOR"))

    @staticmethod
    def _copy_chart_value(target, key, source, source_key):
        symbol = chr(gtsam.Symbol(key).chr())
        if symbol == "x":
            value = source.atPose3(source_key)
        elif symbol == "b":
            value = source.atConstantBias(source_key)
        elif symbol in ("c", "d"):
            value = source.atPoint3(source_key)
        else:
            value = source.atVector(source_key)
        if target.exists(key):
            target.erase(key)
        if symbol in ("c", "d"):
            target.insert_point3(key, value)
        elif symbol in ("x", "b"):
            target.insert(key, value)
        else:
            target.insert_vector(key, value)

    def _model_linearization_values(self, anchor: dict, new_values=None):
        """Map common physical variables; retain each nuisance's own old chart.

        Contact/direction/common-error serial keys differ between support models.
        Numeric equality of their keys therefore never implies shared identity.
        Historical common variables absent from a later background lag retain
        their last common chart, supplied by checkpoint/replay, not a new chart
        at the conditional shadow mean.
        """
        source = anchor["values"]
        parent = tuple(anchor["integer_lineage"])
        lineage = tuple(self.integer_lineage)
        if lineage[:len(parent)] != parent:
            raise ValueError("background anchor is not this integer lineage or an ancestor")
        previous = self.window.linearization_values if self.window.gaussian_only else self.window.values
        result = gtsam.Values(previous)
        if new_values is not None:
            for key in new_values.keys():
                self._copy_chart_value(result, key, new_values, key)
        required = set(self.window.values.keys()) | (set() if new_values is None else set(new_values.keys()))
        for key in list(result.keys()):
            if key not in required:
                result.erase(key)
        matched, frozen = [], []
        for key in required:
            if chr(gtsam.Symbol(key).chr()) not in ("x", "v", "b"):
                continue
            if source.exists(key):
                self._copy_chart_value(result, key, source, key)
                matched.append(key)
            else:
                # A fresh event key needs a real common background chart.
                if new_values is not None and new_values.exists(key):
                    raise ValueError("shared linearization anchor lacks current navigation state")
                frozen.append(key)
        unmapped = {}
        for mapping_name in ("ambiguity_keys", "contact_keys", "phase_beta_coordinates"):
            unmapped[mapping_name] = []
            target_mapping = getattr(self, mapping_name)
            source_mapping = anchor.get(mapping_name, {})
            for identity, key in target_mapping.items():
                other = source_mapping.get(identity)
                if key in required and other is not None and source.exists(other):
                    self._copy_chart_value(result, key, source, other)
                    matched.append(key)
                elif key in required:
                    unmapped[mapping_name].append(identity)
        self.linearization_scope = dict(
            kind="COMMON_LINEARIZATION_GAUSSIAN_CONDITIONAL", qualification_scope="COMMON_LINEARIZATION_ONLY",
            reference_scope=anchor["scope"], reference_index=anchor["index"],
            reference_time_s=anchor["time_s"], reference_integer_lineage=deepcopy(parent),
            reference_support_identity=anchor.get("reference_support_identity", "fixed"),
            lineage_relation="EXACT" if lineage == parent else "ANCESTOR_CONDITIONED",
            shared_variable_count=len(matched), shared_variable_keys=tuple(sorted(matched)),
            frozen_history_keys=tuple(sorted(frozen)),
            unmapped_ambiguity_labels=tuple(unmapped["ambiguity_keys"]),
            unmapped_contact_arcs=tuple(unmapped["contact_keys"]),
            unmapped_phase_beta_coordinates=tuple(unmapped["phase_beta_coordinates"]),
            background_chart_id=deepcopy(anchor.get("background_chart_id")),
            model_specific_nuisance_charts=True, strict_nonlinear_model_exclusion=False)
        if self.metadata.get("gaussian_future_separator", False):
            self.linearization_scope.update(history_elimination="SOURCE_FUTURE_SEPARATOR",
                eliminated_history_jacobians="FROZEN", five_second_reanchoring_equivalent=False)
        if self.phase_noise_model is not None:
            self.linearization_scope["phase_source_scope"] = self._phase_noise_scope()
        return result

    def _seed_source(self, values, key):
        if values.exists(key):
            return values
        return self.window.values if self._factor_seed_values is None else self._factor_seed_values

    @staticmethod
    def _sigmas(value, dimension=3):
        return np.broadcast_to(np.asarray(value, float), (dimension,)).copy()

    def _retained_keys(self, *, gaussian: bool | None = None) -> set[int]:
        retained = set(self.ambiguity_keys.values()) | set(self.phase_beta_keys.values()) | self._support_retain
        if self.constant_bias:
            retained.add(B(0))
        mode = self.window.gaussian_only if gaussian is None else gaussian
        if mode and self.metadata.get("gaussian_future_separator", False):
            # step's ordinary lag elimination runs before controller compression.
            # Preserve every future source reference, including an unobserved
            # singleton's older AR expression, until lifecycle cleanup below.
            retained.update(self._future_separator_keys())
        return retained

    def _future_separator_keys(self) -> set[int]:
        retained = set(self.ambiguity_keys.values()) | set(self.phase_beta_keys.values()) | set(self.contact_keys.values())
        if self.index is not None:
            retained.update((X(self.index), V(self.index), self.bias_key))
        for arc in set(self.foot_history) | set(self.foot_error_history):
            if arc in self.foot_error_history:
                retained.update(self.foot_error_history[arc][0].keys)
            else:
                retained.add(self.foot_history[arc][0])
                retained.add(self.contact_keys[arc])
        # Component joins read all mapped points, not just currently seen feet.
        for geometry in self.support_geometry.values():
            retained.update(key for _, key in geometry.values() if key is not None)
        return retained

    def _observe_support_lifecycle(self, event: dict) -> None:
        if not self.metadata.get("gaussian_future_separator", False):
            return
        state_time = float(event.get("support_state_source_time_s", event["time_s"]))
        states = event.get("support_states", ())
        if self._support_state_time is None or state_time >= self._support_state_time:
            # Each supplied state is an actual source report for that foot.
            # active_support_arcs, when supplied, is the complete active set.
            reported = {int(state["foot_id"]): state.get("arc_id") for state in states}
            for arc, foot in self._support_arc_foot.items():
                if foot in reported and reported[foot] != arc:
                    self._support_pending_closed.add(arc)
            if "active_support_arcs" in event:
                known = set(self._support_arc_foot) | set(self.contact_keys) | set(self.foot_history) | set(self.foot_error_history)
                known.update(arc for geometry in self.support_geometry.values() for arc in geometry)
                self._support_pending_closed.update(known-set(event["active_support_arcs"]))
            for foot, arc in reported.items():
                if arc is not None:
                    self._support_arc_foot[arc] = foot
            if states or "active_support_arcs" in event:
                self._support_state_time = state_time
        for observation in event.get("feet", ()):
            arc, foot = observation["arc_id"], int(observation["foot_id"])
            # A new token for the same physical foot proves the old arc ended;
            # a missing packet, ineligible singleton or empty list does not.
            self._support_pending_closed.update(
                old for old, identity in self._support_arc_foot.items()
                if identity == foot and old != arc)
            self._support_arc_foot[arc] = foot

    def compress_gaussian_history(self, event: dict) -> dict:
        """Eliminate consumed history after step/condition and accepted startup.

        Exact marginalization of the currently stored Gaussian rows. Eliminated
        history cannot later follow the nonlinear root's changing chart: this is
        a frozen-history approximation, not the ordinary five-second model.
        Source policies, integer lineage, predictive evidence and replay logs
        remain controller-owned and are not retired by this operation.
        """
        if not self.window.gaussian_only or not self.metadata.get("gaussian_future_separator", False):
            return dict(status="NOT_ENABLED", eliminated_key_count=0)
        if self.bootstrap_status == "NO_INIT":
            raise ValueError("Gaussian startup must be accepted before history compression")
        self._observe_support_lifecycle(event)
        closed = tuple(sorted(self._support_pending_closed))
        for arc in closed:
            self.contact_keys.pop(arc, None)
            self.foot_history.pop(arc, None)
            self.foot_error_history.pop(arc, None)
            self._support_arc_foot.pop(arc, None)
            for geometry in self.support_geometry.values():
                geometry.pop(arc, None)
        self.support_geometry = {group: geometry for group, geometry in self.support_geometry.items() if geometry}
        self._support_pending_closed.clear()
        before_keys = set(self.window.values.keys())
        before_dimension = int(self.window.values.dim())
        retained = self._future_separator_keys()
        expired = sorted(before_keys-retained, key=lambda key: (self.window.times[key], key))
        self.window.last_marginalized = tuple(expired)
        if expired:
            self.window._marginalize(expired)
        self._prune_phase_coordinates()
        self._support_retain = retained-set(self.ambiguity_keys.values())
        self._current()
        return dict(status="COMPRESSED", scope="FROZEN_HISTORY_GAUSSIAN_SEPARATOR",
                    equivalence="EXACT_FOR_CONSUMED_FIXED_JACOBIANS_ONLY",
                    historical_relinearization=False, hypothesis_count_bounded=False,
                    closed_support_arcs=closed, before_key_count=len(before_keys),
                    retained_key_count=len(self.window.values.keys()), eliminated_key_count=len(expired),
                    before_dimension=before_dimension, retained_dimension=int(self.window.values.dim()),
                    separator_dimension=int(self.window.values.dim()),
                    retained_ambiguity_count=len(self.ambiguity_keys),
                    retained_phase_source_count=len(self.phase_beta_keys),
                    phase_source_scope=self._phase_noise_scope(),
                    open_support_arc_count=len(self._support_arc_foot),
                    retained_factor_count=len(self.window.factors))

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

    def _phase_noise_scope(self):
        if self.phase_noise_model is None:
            return None
        return dict(model=deepcopy(self.phase_noise_model), units="m", identity="PHYSICAL_SIGNAL_NOT_INTEGER_ARC",
                    inference="JOINT_NAVIGATION_GRAPH", unseen_signal_prior="INDEPENDENT_STATIONARY_ZERO_MEAN",
                    source_parameters_qualification="CONDITIONAL_ON_SUPPLIED_NOISE_PARAMETERS",
                    integer_slip_resets_beta=False, missing_signal_restarts_beta=False)

    def _phase_observation_model(self, block):
        if self.phase_noise_model is None:
            return None
        incidence = (physical_source_incidence(block) if block.ambiguity_labels else
                     PhysicalSourceIncidence((), np.zeros((len(block.y), 0))))
        white = float(self.phase_noise_model["white_sd_sigma_m"])
        covariance = np.asarray(block.Q)+white*white*(incidence.D@incidence.D.T)
        return incidence, covariance

    def _phase_beta_transition(self, signal, timestamp):
        sigma = float(self.phase_noise_model["beta_sd_sigma_m"])
        previous = self.phase_beta_keys.get(signal)
        if previous is None:
            return None, 0., sigma*sigma
        elapsed = float(timestamp)-self.phase_beta_times[signal]
        if elapsed < 0.:
            raise ValueError("phase beta cannot propagate backwards across source epochs")
        tau = float(self.phase_noise_model["tau_s"])
        rho = math.exp(-elapsed/tau)
        return previous, rho, sigma*sigma*(-math.expm1(-2.*elapsed/tau))

    def _prune_phase_coordinates(self):
        self.phase_beta_coordinates = {identity: key for identity, key in self.phase_beta_coordinates.items()
                                       if self.window.values.exists(key)}

    def _carrier(self, block, pose, pose_key, values, times, factors):
        phase_model = self._phase_observation_model(block)
        beta_keys, beta_seeds = [], []
        if phase_model is not None and float(self.phase_noise_model["beta_sd_sigma_m"]) > 0.:
            for signal in phase_model[0].source_signals:
                previous, rho, process_variance = self._phase_beta_transition(signal, block.time_s)
                seed = (0. if previous is None else
                        rho*float(self._seed_source(values, previous).atVector(previous)[0]))
                key = gtsam.symbol("e", self._phase_beta_serial)
                self._phase_beta_serial += 1
                values.insert_vector(key, np.array([seed]))
                times[key] = float(block.time_s)
                if previous is None:
                    factors.append(gtsam.PriorFactorVector(key, np.zeros(1),
                        gtsam.noiseModel.Isotropic.Sigma(1, math.sqrt(process_variance))))
                else:
                    factors.append(source_ou_factor(previous, key, rho, math.sqrt(process_variance)))
                self.phase_beta_keys[signal] = key
                self.phase_beta_times[signal] = float(block.time_s)
                self.phase_beta_coordinates[(signal, float(block.time_s))] = key
                beta_keys.append(key)
                beta_seeds.append(seed)
        labels = tuple(block.ambiguity_labels)
        # Coordinate constraints can only name variables still present in the
        # common graph. Retired keys are not resurrected by a label dictionary.
        stale = [label for label, key in self.ambiguity_keys.items()
                 if not values.exists(key) and not self.window.values.exists(key)]
        for label in stale:
            del self.ambiguity_keys[label]
            self._conditioned_labels.discard(label)
        live_keys = set(self.ambiguity_keys.values())
        self._carrier_coordinate_constraints = {
            identity for identity in self._carrier_coordinate_constraints
            if all(key in live_keys for key, _ in identity)}
        history_labels = tuple(self.ambiguity_keys)
        transition = self._carrier_relation_tracker.advance(
            labels, time_s=self.time, history_labels=history_labels)
        unknown = [label for label in labels if label not in self.ambiguity_keys]
        residual = np.asarray(block.y, float) - np.asarray(block.B) @ pose.rotation().rotate(self.baseline_body)
        if beta_keys:
            residual -= phase_model[0].D@np.asarray(beta_seeds)
        for j, label in enumerate(labels):
            if label not in unknown:
                key = self.ambiguity_keys[label]
                source = self._seed_source(values, key)
                residual -= np.asarray(block.A)[:, j] * source.atVector(key)[0]
        if unknown:
            columns = [labels.index(label) for label in unknown]
            chol = np.linalg.cholesky(np.asarray(block.Q) if phase_model is None else phase_model[1])
            whitened_design = np.linalg.solve(chol, np.asarray(block.A)[:, columns])
            initial, _, _, _ = np.linalg.lstsq(
                whitened_design, np.linalg.solve(chol, residual), rcond=None)
            for label, estimate in zip(unknown, initial):
                key = gtsam.symbol("a", self._ambiguity_serial)
                self._ambiguity_serial += 1
                self.ambiguity_keys[label] = key
                values.insert_vector(key, np.array([float(estimate)]))
                if label in self.fixed:
                    factors.append(self._fixed_factor(label))
        coordinate_count = 0
        new_coordinate_basis = {}
        added_coordinates = []
        for relation in transition.graph_constraints():
            coefficients = dict(relation["coefficients"])
            row = [Fraction(coefficients.get(label, 0)) for label in unknown]
            # The old variables already obey their coordinate identities.
            # Keep only independent extensions on the newly created variables;
            # repeated old combinations add no equation or sensor information.
            for pivot, basis in sorted(new_coordinate_basis.items()):
                if row[pivot]:
                    scale = row[pivot]
                    row = [value-scale*entry for value, entry in zip(row, basis)]
            pivot = next((j for j, value in enumerate(row) if value), None)
            if pivot is None:
                continue
            scale = row[pivot]
            new_coordinate_basis[pivot] = [value/scale for value in row]
            identity = tuple(sorted((self.ambiguity_keys[label], int(coefficient))
                                    for label, coefficient in relation["coefficients"]))
            if identity[0][1] < 0:
                identity = tuple((key, -coefficient) for key, coefficient in identity)
            if identity in self._carrier_coordinate_constraints:
                continue
            factors.append(self._carrier_coordinate_factor(identity))
            self._carrier_coordinate_constraints.add(identity)
            added_coordinates.append(dict(identity))
            coordinate_count += 1
        if added_coordinates:
            # Begin on the exact coordinate manifold, as for the foot latent
            # coordinates. This only changes Values: the raw observation and
            # its Q are untouched, and unconstrained float directions remain.
            new_keys = [self.ambiguity_keys[label] for label in unknown]
            new_set = set(new_keys)
            design = np.array([[relation.get(key, 0) for key in new_keys]
                               for relation in added_coordinates], dtype=float)
            target = np.array([-sum(coefficient*self._seed_source(values, key).atVector(key)[0]
                for key, coefficient in relation.items() if key not in new_set)
                for relation in added_coordinates])
            initial = np.array([values.atVector(key)[0] for key in new_keys])
            initial += np.linalg.lstsq(design, target-design @ initial, rcond=None)[0]
            replacement = gtsam.Values()
            for key, estimate in zip(new_keys, initial):
                replacement.insert_vector(key, np.array([estimate]))
            values.update(replacement)
        self._carrier_relation_tracker.remember(labels)
        self.last_carrier_relations = dict(
            history_relation_rank=transition.history_relation_rank,
            current_relation_rank=transition.current_relation_rank,
            intersection_rank=transition.intersection_rank,
            new_relation_rank=transition.new_relation_rank,
            continuation_status=transition.continuation_status,
            pivot_only_change=transition.pivot_only_change,
            new_coordinate_factors=coordinate_count,
            history_scope="ACTUALLY_PRESENT_SHARED_GRAPH_AMBIGUITY_VARIABLES",
            expired_variable_labels=tuple(stale),
            coordinate_identity_is_integer_fix=False,
            observation_transport_applied=False, covariance_transformed=False)
        keys = [self.ambiguity_keys[label] for label in labels]
        times.update({key: self.time for key in keys})
        if phase_model is None:
            factors.append(carrier_relation_factor(pose_key, keys, block, self.baseline_body))
        else:
            factors.append(carrier_relation_factor(pose_key, keys, block, self.baseline_body,
                beta_keys=tuple(beta_keys), source_design=phase_model[0].D, covariance=phase_model[1]))

    @staticmethod
    def _carrier_coordinate_factor(identity):
        """Exact new/old DD coordinate relation; no additional sensor evidence."""
        identity = tuple(identity)

        def error(_factor, values, jacobians):
            residual = 0.0
            for index, (key, coefficient) in enumerate(identity):
                residual += coefficient*float(values.atVector(key)[0])
                if jacobians is not None:
                    jacobians[index] = np.array([[float(coefficient)]], order="F")
            return np.array([residual])

        return gtsam.CustomFactor(gtsam.noiseModel.Constrained.All(1),
                                  [key for key, _ in identity], error)

    def _support_key(self, symbol):
        key = gtsam.symbol(symbol, self._support_serial)
        self._support_serial += 1
        return key

    def _point(self, key, values):
        return self._seed_source(values, key).atPoint3(key)

    def _previous_foot_error(self, arc):
        if arc in self.foot_error_history:
            return self.foot_error_history[arc]
        if arc in self.foot_history:
            pose_key, measured, timestamp = self.foot_history[arc]
            return FootErrorExpression(pose_key, self.contact_keys[arc], tuple(measured)), timestamp
        return None

    def _add_foot_error(self, arc, expression, factors):
        history = self._previous_foot_error(arc)
        previous, rho = (None, 0.) if history is None else (
            history[0], math.exp(-(self.time-history[1])/self.foot_tau))
        factors.append(algebraic_foot_error_factor(expression, self.foot_sigma, previous=previous, rho=rho))
        self.foot_error_history[arc] = (expression, self.time)

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
            if arc in self.foot_error_history:
                expression = FootErrorExpression(pose_key, key, tuple(measured))
                self._add_foot_error(arc, expression, factors)
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
            common_key = self._support_key("q")
            seeds = []
            for foot, point_key in zip(members, geometry):
                point = np.zeros(3) if point_key is None else self._point(point_key, values)
                history = self._previous_foot_error(foot["arc_id"])
                previous_error = (np.zeros(3) if history is None else
                    math.exp(-(self.time-history[1])/self.foot_tau)*history[0].evaluate(
                         self.window.values if self._factor_seed_values is None else self._factor_seed_values))
                seeds.append(pose.rotation().unrotate(point)-np.asarray(foot["point_body"])-previous_error)
            values.insert_vector(common_key, np.mean(seeds, axis=0))
            times[common_key] = self.time
            for foot, point_key in zip(members, geometry):
                expression = FootErrorExpression(pose_key, point_key, tuple(foot["point_body"]), common_key)
                self._add_foot_error(foot["arc_id"], expression, factors)
            contrasts += len(members)-1
        # Declared groups outlive temporary visibility/normal departure: their
        # posterior and per-arc error remain available to subsequent evidence.
        live_arcs = set(assigned) | {foot["arc_id"] for foot in observed}
        for arc in live_arcs:
            if arc in self.contact_keys:
                self._support_retain.add(self.contact_keys[arc])
            if arc in self.foot_error_history:
                self._support_retain.update(self.foot_error_history[arc][0].keys)
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
        """Actual joint marginal, retaining exact foot/carrier coordinates.

        The graph's default elimination can choose Cholesky at an unconstrained
        local clique even when another clique contains exact coordinates. After
        lag marginalization this fails on the strongly scaled bias/integer
        system. Explicit local Jacobian QR avoids forming normal equations;
        COLAMD keeps the query variables last without densifying the whole graph.
        Fixed-contact branches keep their original marginal operation.
        """
        if self.window.gaussian_only:
            covariance = self.window.joint_covariance(keys)
            sizes = [len(self.window.linearization_delta.at(key)) for key in keys]
            transport = np.eye(sum(sizes))
            offset, epsilon = 0, 1e-6
            for key, size in zip(keys, sizes):
                if chr(gtsam.Symbol(key).chr()) == "x":
                    origin = self.window.linearization_values.atPose3(key)
                    mean = self.window.values.atPose3(key)
                    delta = self.window.linearization_delta.at(key)
                    for column in range(size):
                        perturbation = np.zeros(size)
                        perturbation[column] = epsilon
                        transport[offset:offset+size, offset+column] = (
                            mean.localCoordinates(origin.retract(delta+perturbation))-
                            mean.localCoordinates(origin.retract(delta-perturbation)))/(2*epsilon)
                offset += size
            return transport @ covariance @ transport.T
        if not self.foot_error_history and not self._carrier_coordinate_constraints:
            joint = gtsam.Marginals(self.window.graph, self.window.values).jointMarginalCovariance(
                gtsam.KeyVector(keys))
            return np.block([[joint.at(a, b) for b in keys] for a in keys])
        linear = self.window.graph.linearize(self.window.values)
        ordering = gtsam.Ordering.ColamdConstrainedLastGaussianFactorGraph(linear, keys, True)
        query = set(keys)
        eliminated = [ordering.at(index) for index in range(ordering.size()) if ordering.at(index) not in query]
        _, remaining = eliminate_qr(linear, eliminated)
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
        retained. Physical SD beta means, OU innovations and their complete
        joint cross covariance enter these same original rows before consumption;
        a previously unseen source contributes its independent stationary prior.
        Synthetic GNSS product/raw-row independence is the declared
        working source model, not an assertion about receiver products in field
        data. No likelihood or state mutation is performed by this method.
        """
        timestamp = float(event["time_s"])
        gaussian = self.window.gaussian_only
        chart = self.window.linearization_values if gaussian else self.window.values
        pose = chart.atPose3(X(self.index))
        velocity = chart.atVector(V(self.index))
        bias = chart.atConstantBias(self.bias_key)
        preintegrated = self._preintegrate(event, bias)
        predicted_state = preintegrated.predict(gtsam.NavState(pose, velocity), bias)
        gnss_inputs = self._gnss_inputs(event, predicted_state.pose())
        block = event.get("carrier")
        phase_model = None if block is None else self._phase_observation_model(block)
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
        known_beta_signals, new_beta_signals, beta_columns, beta_rhos = [], [], [], []
        phase_process_covariance = np.zeros((len(selected_rows), len(selected_rows)))
        if phase_model is not None and float(self.phase_noise_model["beta_sd_sigma_m"]) > 0.:
            incidence = phase_model[0]
            selected_D = incidence.D[selected_rows]
            for column, signal in enumerate(incidence.source_signals):
                direction = selected_D[:, column]
                if not np.any(direction):
                    continue
                previous, rho, process_variance = self._phase_beta_transition(signal, block.time_s)
                phase_process_covariance += process_variance*np.outer(direction, direction)
                if previous is None:
                    new_beta_signals.append(signal)
                else:
                    known_beta_signals.append(signal)
                    beta_columns.append(direction)
                    beta_rhos.append(rho)
        carrier_beta_design = (np.column_stack(beta_columns)*np.asarray(beta_rhos)
                               if beta_columns else np.empty((len(selected_rows), 0)))
        keys = [X(self.index), V(self.index), self.bias_key,
                *[self.ambiguity_keys[label] for label in known_labels],
                *[self.phase_beta_keys[signal] for signal in known_beta_signals]]
        prior_covariance = (self.window.joint_covariance(keys) if gaussian else self.joint_covariance(keys))
        n0 = np.array([chart.atVector(self.ambiguity_keys[label])[0]
                       for label in known_labels])
        beta0 = np.array([chart.atVector(self.phase_beta_keys[signal])[0]
                          for signal in known_beta_signals])
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
            measurement_q = np.asarray(block.Q) if phase_model is None else phase_model[1]
            noise_blocks.append(measurement_q[np.ix_(selected_rows, selected_rows)])
            slices["carrier"] = slice(dimension, dimension+len(selected_rows))
            dimension += len(selected_rows)
            identities.append(f"raw_code_carrier:{timestamp:.9f}")
            row_identities.extend(f"raw_code_carrier:{timestamp:.9f}:row{row}" for row in selected_rows)
            columns = [tuple(block.ambiguity_labels).index(label) for label in known_labels]
            carrier_A = np.asarray(block.A)[np.ix_(selected_rows, columns)]
            carrier_B = np.asarray(block.B)[selected_rows]

        def measurement(rotation, position, speed, integers, gyro_bias, beta_values):
            antenna_position, antenna_velocity = gnss_antenna_prediction(
                gtsam.Pose3(rotation, position), speed, gyro_bias,
                gnss_inputs["position_lever"], gnss_inputs["velocity_lever"], gnss_inputs["angular_rate"])
            parts = []
            if "gnss_position" in slices:
                parts.append(antenna_position)
            if "gnss_velocity" in slices:
                parts.append(antenna_velocity)
            if "carrier" in slices:
                raw_prediction = carrier_B @ rotation.rotate(self.baseline_body) + carrier_A @ integers
                if known_beta_signals:
                    raw_prediction += carrier_beta_design@beta_values
                parts.append(raw_prediction)
            return np.concatenate(parts) if parts else np.empty(0)

        def prediction_at(delta):
            shifted_bias = gtsam.imuBias.ConstantBias(
                bias.accelerometer()+delta[9:12], bias.gyroscope()+delta[12:15])
            state = preintegrated.predict(
                gtsam.NavState(pose.retract(delta[:6]), velocity+delta[6:9]), shifted_bias)
            nend = 15+len(known_labels)
            return measurement(state.attitude(), state.position(), state.velocity(),
                               n0+delta[15:nend], shifted_bias.gyroscope(), beta0+delta[nend:])

        prior_dimension = 15+len(known_labels)+len(known_beta_signals)
        predicted = prediction_at(np.zeros(prior_dimension))
        state_jacobian = np.empty((dimension, prior_dimension))
        epsilon = 1e-6
        for column in range(state_jacobian.shape[1]):
            delta = np.zeros(state_jacobian.shape[1])
            delta[column] = epsilon
            state_jacobian[:, column] = (prediction_at(delta)-prediction_at(-delta))/(2*epsilon)

        if gaussian:
            delta_mean = np.concatenate([self.window.linearization_delta.at(key) for key in keys])
            predicted = predicted + state_jacobian @ delta_mean

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
            predicted = measurement(shifted_pose.rotation(), shifted_pose.translation(), shifted_velocity,
                                    n0, bias.gyroscope(), beta0)
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
        if "carrier" in slices and phase_model is not None:
            target = slices["carrier"]
            sensor_covariance[target, target] += phase_process_covariance
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
            inference_scope=deepcopy(self.linearization_scope),
            prediction_linearization=("COMMON_ANCHOR_AFFINE_GAUSSIAN" if gaussian else "CONDITIONAL_NONLINEAR_MEAN"),
            source_covariance_assumption=gnss_inputs["source_covariance_assumption"],
            angular_rate_source_time_s=gnss_inputs["angular_source_time_s"],
            angular_rate_source_noise_interval_s=gnss_inputs["angular_source_noise_interval_s"],
            phase_source_scope=self._phase_noise_scope(),
            existing_phase_beta_signals=tuple(known_beta_signals),
            new_phase_beta_signals=tuple(new_beta_signals),
        )

    # Compatibility with the interrupted implementation's provisional API.
    predict_independent = predict_external

    def step(self, event: dict, index: int, revoked_arcs: set[str] | None = None,
             *, support_models: list[dict] | None = None, defer_optimize: bool = False,
             initial_rotation: gtsam.Rot3 | None = None, gravity_tilt: dict | None = None,
             linearization_anchor: dict | None = None):
        """Consume factors at their actual event time.

        Deferred construction is used only for an uninitialized asynchronous
        batch. Initial rotation is a Values seed; it never becomes a yaw prior.
        """
        if self.bootstrap_status == "NO_INIT" and not defer_optimize:
            raise ValueError("bootstrap must be qualified before normal step")
        if self.window.gaussian_only and linearization_anchor is None:
            raise ValueError("a Gaussian support step requires its matched background anchor")
        self._factor_seed_values = (None if linearization_anchor is None else
                                   self._model_linearization_values(linearization_anchor))
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
        self._observe_support_lifecycle(event)
        if previous_index is None:
            if initial_rotation is None:
                # Keep the historical synthetic initialization for reproducible
                # existing runs. The real asynchronous bootstrap does not use it.
                predicted_pose = self._initial_pose(event)
                predicted_velocity = np.asarray(event["gnss_velocity"], float).copy()
                rotation_sigmas = [math.radians(20.), math.radians(20.), 1e6]
                factors.append(gtsam.PriorFactorPose3(
                    pose_key, predicted_pose,
                    gtsam.noiseModel.Diagonal.Sigmas(np.r_[rotation_sigmas, [1e6]*3])))
            else:
                rotation = initial_rotation
                position = event.get("gnss_position")
                lever = np.asarray(event.get("gnss_position_leverarm_body_m",
                                   self.metadata.get("gnss_leverarm_body_m", np.zeros(3))), float)
                seed_position = (np.zeros(3) if position is None else
                                 np.asarray(position, float)-rotation.rotate(lever))
                predicted_pose = gtsam.Pose3(rotation, seed_position)
                velocity = event.get("gnss_velocity")
                predicted_velocity = np.zeros(3) if velocity is None else np.asarray(velocity, float).copy()
                if velocity is not None:
                    inputs = self._gnss_inputs(event, predicted_pose)
                    predicted_velocity -= rotation.rotate(np.cross(
                        inputs["angular_rate"]-self.bias.gyroscope(), inputs["velocity_lever"]))
                if gravity_tilt is not None:
                    factors.append(gravity_tilt_factor(
                        pose_key, gravity_tilt["direction_body"],
                        self.metadata.get("gravity_n", [0., 0., 9.81]), gravity_tilt["sigma_rad"]))
            bias_sigma = np.r_[
                np.full(3, float(self.metadata.get("accel_bias_prior_sigma", .03))),
                np.full(3, float(self.metadata.get("gyro_bias_prior_sigma", .003)))]
            factors.append(gtsam.PriorFactorConstantBias(
                bias_key, self.bias, gtsam.noiseModel.Diagonal.Sigmas(bias_sigma)))
        else:
            factor_bias = (self.bias if self._factor_seed_values is None else
                           self._factor_seed_values.atConstantBias(B(0) if self.constant_bias else B(previous_index)))
            preintegrated = self._preintegrate(event, factor_bias)
            prediction = preintegrated.predict(gtsam.NavState(self.pose, self.velocity), factor_bias)
            predicted_pose, predicted_velocity = prediction.pose(), prediction.velocity()
            factors.append(gtsam.ImuFactor(
                X(previous_index), V(previous_index), pose_key, velocity_key,
                B(0) if self.constant_bias else B(previous_index), preintegrated))
            if not self.constant_bias:
                factors.append(gtsam.BetweenFactorConstantBias(
                    B(previous_index), bias_key, gtsam.imuBias.ConstantBias(),
                    gtsam.noiseModel.Diagonal.Sigmas(self.bias_rw * math.sqrt(self.time-previous_time))))
        predicted_bias = self.bias
        if linearization_anchor is not None:
            common = linearization_anchor["values"]
            predicted_pose = common.atPose3(pose_key)
            predicted_velocity = common.atVector(velocity_key)
            predicted_bias = common.atConstantBias(bias_key)
        values.insert(pose_key, predicted_pose)
        values.insert(velocity_key, predicted_velocity)
        if previous_index is None or not self.constant_bias:
            values.insert(bias_key, predicted_bias)

        position, velocity = event.get("gnss_position"), event.get("gnss_velocity")
        gnss_inputs = self._gnss_inputs(event, predicted_pose)
        antenna_position, antenna_velocity = gnss_antenna_prediction(
            predicted_pose, predicted_velocity, predicted_bias.gyroscope(),
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
        model_anchor = (None if linearization_anchor is None else
                        self._model_linearization_values(linearization_anchor, values))
        if defer_optimize:
            self.window.values.insert(values)
            if model_anchor is not None:
                self.window.values.update(model_anchor)
            self.window.times.update(times)
            self.window.factors.extend(factors)
            self.window.time_s = self.time
        else:
            self.window.update(factors, values, times, self.time,
                               retain_keys=self._retained_keys(gaussian=model_anchor is not None),
                               linearization_values=model_anchor, gaussian_only=model_anchor is not None)
            self._prune_phase_coordinates()
        self._factor_seed_values = None
        self.last_factor_counts = dict(
            foot=nfoot, differential=ndifference,
            carrier_rows=0 if block is None else len(block.y),
            total=len(factors), imu_intervals=len(event["imu"]))
        return self._current()

    def bootstrap(self, events: list[dict], seed_rotation: gtsam.Rot3, *, start_index: int = 0,
                  gravity_tilt: dict | None = None, support_models: list[dict] | None = None,
                  linearization_anchor: dict | None = None) -> dict:
        """Build one causal asynchronous startup graph before any marginalization.

        Every PV, IMU, code/carrier and support factor is constructed by step at
        its original time. The caller chooses the buffered interval and performs
        the multi-seed/nonlinear direction qualification; local rank alone never
        authorizes initialization. No observations are moved to the first raw
        carrier time and no synthetic attitude or position prior is introduced.
        """
        if self.index is not None:
            raise ValueError("bootstrap requires an empty branch")
        if not events:
            return dict(status="NO_INIT", reason="NO_BUFFERED_OBSERVATIONS",
                        nonlinear_support="UNRESOLVED")
        self.bootstrap_status = "NO_INIT"
        self.background_chart_id = (deepcopy(linearization_anchor["background_chart_id"])
            if linearization_anchor is not None else
            ("ASYNC_BOOTSTRAP", start_index, float(events[-1]["time_s"]),
             tuple(float(v).hex() for v in seed_rotation.rpy())))
        for offset, event in enumerate(events):
            self.step(event, start_index+offset, support_models=support_models, defer_optimize=True,
                      initial_rotation=seed_rotation if offset == 0 else None,
                      gravity_tilt=gravity_tilt if offset == 0 else None,
                      linearization_anchor=linearization_anchor)
        if linearization_anchor is not None:
            # All observations retain their own epoch.  Solve the completed
            # startup graph in the supplied background chart before any lag
            # elimination; this establishes only conditional Gaussian support.
            chart = self._model_linearization_values(linearization_anchor)
            self.window.optimize(gaussian_only=True, linearization_values=chart)
            self._current()
            dimension = int(self.window.values.dim())
            self.bootstrap_diagnostics = dict(
                status="NO_INIT", nonlinear_support="UNRESOLVED", cost=float(self.window.error()),
                seed_rpy_rad=seed_rotation.rpy().tolist(),
                solution_rpy_rad=self.pose.rotation().rpy().tolist(),
                first_time_s=float(events[0]["time_s"]), last_time_s=self.time,
                event_count=len(events), marginalized_state_count=self.window.marginalized_total,
                initial_tilt_source=deepcopy(gravity_tilt),
                qualification_scope="COMMON_LINEARIZATION_ONLY", solver_status="GAUSSIAN_QR_SOLVED",
                solver_converged=True, local_full_rank=True, state_dimension=dimension,
                numerical_rank=dimension,
                rank_evidence="FULL_RANK_QR_SOLVE_NO_PSEUDOINVERSE_OR_ADDED_PRIOR",
                nonlinear_solver_iterations=0, solver_iterations=1, solver_budget_exhausted=False,
                directional_global_coverage_certified=False,
                inference_scope=deepcopy(self.linearization_scope))
            return deepcopy(self.bootstrap_diagnostics)
        # LM damping is only the numerical step model; it is not stored as a
        # prior and is absent from the subsequent likelihood/rank calculation.
        params = gtsam.LevenbergMarquardtParams()
        params.setMaxIterations(int(self.metadata.get("bootstrap_max_iterations", 200)))
        params.setRelativeErrorTol(self.window.params.getRelativeErrorTol())
        params.setAbsoluteErrorTol(self.window.params.getAbsoluteErrorTol())
        initial_cost = float(self.window.error())
        optimizer = gtsam.LevenbergMarquardtOptimizer(self.window.graph, self.window.values, params)
        self.window.values = optimizer.optimize()
        self._current()
        self.bootstrap_diagnostics = dict(
            status="NO_INIT", nonlinear_support="UNRESOLVED", cost=float(self.window.error()),
            seed_rpy_rad=seed_rotation.rpy().tolist(), solution_rpy_rad=self.pose.rotation().rpy().tolist(),
            first_time_s=float(events[0]["time_s"]), last_time_s=self.time,
            event_count=len(events), marginalized_state_count=self.window.marginalized_total,
            initial_tilt_source=deepcopy(gravity_tilt),
            bias_prior_source="inherited_joint_prototype_engineering_prior",
            solver_iterations=int(optimizer.iterations()), solver_max_iterations=params.getMaxIterations(),
            solver_initial_cost=initial_cost, solver_final_cost=float(self.window.error()),
            solver_lambda=float(optimizer.lambda_()),
            solver_budget_exhausted=optimizer.iterations() >= params.getMaxIterations(),
        )
        return self.bootstrap_qualification()

    def bootstrap_qualification(self) -> dict:
        """Local likelihood/rank readout; global directional support stays external."""
        if self.window.gaussian_only:
            self.bootstrap_diagnostics.update(cost=float(self.window.error()),
                solution_rpy_rad=self.pose.rotation().rpy().tolist(),
                qualification_scope="COMMON_LINEARIZATION_ONLY", solver_status="GAUSSIAN_QR_SOLVED",
                solver_converged=True, local_full_rank=True, nonlinear_solver_iterations=0,
                directional_global_coverage_certified=False)
            return deepcopy(self.bootstrap_diagnostics)
        linear = self.window.graph.linearize(self.window.values)
        combined = gtsam.JacobianFactor(linear)
        matrix, rhs = combined.jacobianUnweighted()
        noise = combined.get_model()
        sigmas = np.ones(len(rhs)) if noise is None else noise.sigmas()
        stochastic = sigmas > 0.
        whitened = matrix.copy()
        whitened[stochastic] /= sigmas[stochastic, None]
        rhs_white = rhs[stochastic]/sigmas[stochastic]
        # Column equilibration changes coordinates, not rank or information.
        # The tolerance is the standard floating-point rank tolerance, not a
        # stochastic noise floor. Exact constraint rows remain exact graph rows.
        norms = np.linalg.norm(whitened, axis=0)
        scaled = whitened.copy()
        nonzero = norms > 0.
        scaled[:, nonzero] /= norms[nonzero]
        singular = np.linalg.svd(scaled, compute_uv=False)
        tolerance = np.finfo(float).eps*max(scaled.shape)*singular[0] if len(singular) else 0.
        rank = int(np.count_nonzero(singular > tolerance))
        dimension = int(self.window.values.dim())
        gradient = -scaled[stochastic].T @ rhs_white
        constraints = scaled[~stochastic]
        if len(constraints):
            _, constraint_singular, row_basis = np.linalg.svd(constraints, full_matrices=False)
            constraint_tolerance = np.finfo(float).eps*max(constraints.shape)*constraint_singular[0]
            row_basis = row_basis[constraint_singular > constraint_tolerance]
            gradient -= row_basis.T @ (row_basis @ gradient)
        gradient_norm = float(np.linalg.norm(gradient, ord=np.inf))
        gradient_relative = gradient_norm/max(1., float(np.linalg.norm(rhs_white)))
        gradient_tolerance = float(self.metadata.get("bootstrap_gradient_tolerance", 1e-6))
        converged = gradient_relative <= gradient_tolerance
        budget_exhausted = self.bootstrap_diagnostics.get("solver_budget_exhausted", False)
        self.bootstrap_diagnostics.update(
            local_full_rank=rank == dimension, numerical_rank=rank, state_dimension=dimension,
            rank_tolerance=float(tolerance),
            minimum_scaled_singular_value=float(singular[-1]) if len(singular) else 0.,
            cost=float(self.window.error()), solution_rpy_rad=self.pose.rotation().rpy().tolist(),
            projected_gradient_inf=gradient_norm, projected_gradient_relative_inf=gradient_relative,
            projected_gradient_tolerance=gradient_tolerance,
            max_exact_constraint_residual=float(np.max(np.abs(rhs[~stochastic]))) if len(constraints) else 0.,
            solver_converged=converged,
            solver_status=("FIRST_ORDER_STATIONARY" if converged else
                           "ITERATION_BUDGET_EXHAUSTED" if budget_exhausted else
                           "LM_STOPPED_WITH_UNRESOLVED_STATIONARITY"))
        return deepcopy(self.bootstrap_diagnostics)

    def accept_bootstrap(self, nonlinear_support: dict):
        """Release the jointly optimized startup only after controller qualification."""
        if not self.bootstrap_diagnostics.get("local_full_rank", False):
            raise ValueError("rank-deficient bootstrap remains NO_INIT")
        if nonlinear_support.get("qualified") is not True:
            raise ValueError("nonlinear direction support remains unresolved")
        self.bootstrap_diagnostics["nonlinear_support"] = deepcopy(nonlinear_support)
        self.bootstrap_diagnostics["status"] = "INITIALIZED"
        self.bootstrap_status = "INITIALIZED"
        retained = self._retained_keys()
        expired = sorted((key for key, stamp in self.window.times.items()
                          if stamp < self.time-self.window.lag_s and key not in retained),
                         key=lambda key: (self.window.times[key], key))
        self.window.last_marginalized = tuple(expired)
        if expired:
            self.window._marginalize(expired)
        self._prune_phase_coordinates()
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

    def condition(self, integer_by_label: dict[str, int], *, linearization_anchor: dict | None = None):
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
            if self.window.gaussian_only or linearization_anchor is not None:
                chart = (self.window.linearization_values if linearization_anchor is None else
                         self._model_linearization_values(linearization_anchor))
                self.window.factors.extend(factors)
                self.window.optimize(gaussian_only=True, linearization_values=chart)
                self._current()
                if self.bootstrap_status == "NO_INIT":
                    self.bootstrap_qualification()
            elif self.bootstrap_status == "NO_INIT":
                self.window.factors.extend(factors)
                self.window.values = gtsam.LevenbergMarquardtOptimizer(
                    self.window.graph, self.window.values, self.window.params).optimize()
                self._current()
                self.bootstrap_qualification()
            else:
                self.window.update(factors, gtsam.Values(), {}, self.time,
                                   retain_keys=self._retained_keys())
        return self._current()

    def snapshot(self) -> BranchSnapshot:
        names = ("ambiguity_keys", "_ambiguity_serial", "_carrier_relation_tracker",
                 "phase_beta_keys", "phase_beta_times", "phase_beta_coordinates", "_phase_beta_serial",
                 "_carrier_coordinate_constraints", "last_carrier_relations",
                 "contact_keys", "direction_keys", "foot_history",
                 "direction_history", "fixed", "_conditioned_labels", "time", "index",
                 "last_gnss_innovation", "last_factor_counts", "constant_bias", "bias_key",
                 "foot_error_history", "support_geometry", "_support_serial", "_support_retain",
                 "_support_arc_foot", "_support_pending_closed", "_support_state_time",
                 "predictive_score", "predictive_row_count", "predictive_frontier", "integer_lineage",
                 "bootstrap_status", "bootstrap_diagnostics", "linearization_scope", "background_chart_id")
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
