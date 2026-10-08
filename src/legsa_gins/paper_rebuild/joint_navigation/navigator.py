"""Causal joint navigation, conditional directions, and support-history replay.

One entry consumes the same physical event stream for U0--U3. It never receives
simulation truth. Profile costs express conditional support, not probabilities.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
import math
import time

import numpy as np
import gtsam
from scipy.stats import chi2
from gtsam.symbol_shorthand import X

from ..carrier_phase.temporal import EpochBlock
from .branch import NavigationBranch
from .candidate import propose_candidates
from .source_noise_likelihood import NoiseParameters, assemble_source_noise_covariance
from .carrier_relations import analyze_relation_transition, reparameterize_epoch_blocks
from .support_policy import canonical_policy, policy_identity, policy_readout, replace_group


@dataclass
class Checkpoint:
    index: int
    time_s: float
    branches: list
    proposal_times: dict
    proposal_complete: bool
    support_incomplete: bool
    candidates: list
    arc_first_use: dict
    bootstrap_last_attempt: float = -math.inf
    bootstrap_diagnostic: dict | None = None
    predictive_rows_fingerprint: str = ""
    proposal_retry_after: dict | None = None
    pending_proposals: dict | None = None


@dataclass
class SupportTrack:
    identity: str
    group_id: str
    arc_ids: tuple[str, ...]
    model: str
    first_use: float
    origin: Checkpoint
    navigator: object
    policy: tuple[dict, ...] = ()
    parent_ids: set[str] = field(default_factory=set)
    edit_count: int = 0
    created_index: int = -1
    processed_events: int = 0
    nonlinear_expanded: bool = False
    unresolved_reason: str | None = None


def code_only(block: EpochBlock) -> EpochBlock:
    """The full-only comparator keeps code on the identical interrupted stream."""
    rows = np.flatnonzero(np.all(block.A == 0, axis=1))
    return EpochBlock(block.time_s, block.y[rows], np.zeros((len(rows), 0)),
                      block.B[rows], block.Q[np.ix_(rows, rows)], (), dict(block.metadata))


class JointNavigator:
    def __init__(self, metadata: dict, mode: str = "U3", *,
                 monitor_support: bool = True, support_models: list[dict] | None = None):
        self.metadata = copy.deepcopy(metadata)
        self.support_prediction = metadata.get("support_prediction", "external")
        proper_support_prediction = self.support_prediction == "foot_external"
        self.support_alternative_models = (("finite_common_motion",) if proper_support_prediction
                                           else ("common_translation_release", "relative_release"))
        self.support_policy_search = metadata.get("support_policy_search",
            "observed_groups" if proper_support_prediction else "combined_paths")
        self.expand_support_policy_paths = self.support_policy_search == "combined_paths"
        self.metadata["support_policy_search"] = self.support_policy_search
        if proper_support_prediction and any(item["mode"] not in ("fixed", "finite_common_motion")
                                             for item in (support_models or [])):
            raise ValueError("joint foot density compares fixed and proper finite-motion models on the same rows")
        self.gaussian_future_separator = metadata.get("support_inference") == "shared_separator"
        if self.gaussian_future_separator:
            self.metadata["gaussian_future_separator"] = True
        self.gaussian_compressed_key_count = 0
        self.maximum_gaussian_separator_dimension = 0
        self.mode = mode
        self.use_foot = mode != "U0"
        self.use_partial = mode in ("U2", "U3")
        self.rebuild_history = mode == "U3"
        self.branches = [NavigationBranch(self.metadata, use_foot=self.use_foot)]
        self.asynchronous_start = metadata.get("data_mode") == "real_by2_raw"
        self.bootstrap_window_s = float(metadata.get("bootstrap_window_s", 5.))
        self.bootstrap_last_attempt = -math.inf
        self.bootstrap_diagnostic = dict(status="NO_INIT", reason="WAITING_FOR_CAUSAL_RAW_AND_PV_BUFFER")
        self.history_s = 30.0
        self.active_limit = 4
        self.profile_support_delta = 25.0
        self.proposal_times = {}
        self.proposal_retry_after = {}
        self.pending_proposals = {}
        self.proposal_complete = False
        self.support_incomplete = False
        self.dormant_candidates = []
        self.arc_first_use = {}
        self.revoked_arcs = set()
        self.stop_from = {}
        self.checkpoints = []
        self.events = []
        self.decisions = []
        self.rows = []
        self.last_checkpoint_time = -math.inf
        self.replayed_events = 0
        self.proposal_attempts = 0
        self.last_phase_relation_count = 0
        self.monitor_support = monitor_support and mode in ("U2", "U3")
        self.shared_support = (self.monitor_support and
            metadata.get("support_inference", "full_nonlinear") in ("shared_linearization", "shared_separator"))
        self.anchor_history = {}
        # The last published nonlinear conditional supplies the next common
        # chart. Choosing a chart does not adopt or discard a source model.
        self.linearization_reference_identity = None
        self.linearization_reference_used = None
        self.linearization_reference_switches = 0
        # Finite-run recovery archive. This makes old-source nonlinear replay
        # possible; its memory is explicitly not a bounded online log claim.
        self.recovery_events = []
        self.recovery_rows = {}
        self.nonlinear_support_expansions = 0
        self.gaussian_support_step_events = 0
        self.nonlinear_support_step_events = 0
        self.support_models = list(canonical_policy(support_models or []))
        # Proper joint predictive densities already integrate finite motion and
        # include their normalization. Do not add the legacy release family's
        # unsupported 1:100 edit odds to that likelihood comparison.
        # The retained 1:20 working support band affects publication; it is not
        # a calibrated confidence set or a multiple-search error guarantee.
        self.model_edit_cost = 0. if proper_support_prediction else 2. * math.log(100.)
        self.model_support_delta = 2. * math.log(20.)
        self.support_groups = {}
        self.support_tracks = {}
        # One cursor and FIFO ticket per policy, not a materialized Cartesian
        # product. Low-scoring ancestors retain their continuation opportunity.
        self.support_group_order = []
        self.policy_parent_cursors = {}
        self.policy_queue_tickets = {}
        self.policy_ticket_serial = 0
        self.policy_extension_items = 0
        self.policy_extension_nodes = 0
        self.policy_last_extension_frontier = -1
        self.policy_exploration_started = False
        self.policy_exploration_tail_probability = float(metadata.get("policy_exploration_tail_probability", 1e-4))
        self.last_external_prediction_nis = None
        self.last_external_prediction_dimension = 0
        self.last_prediction_blocks = []
        self.reference_rows = {}
        self.predictive_rows_fingerprint = ""
        self.last_support_signature = None
        self.last_supported_tracks = set()
        self.model_generation = 0
        self.model_replay_events = 0
        self.expired_unresolved_groups = 0
        self.rescan_support_history = False
        self.checkpoints.append(Checkpoint(
            -1, float(metadata.get("window_s", [0.])[0])-1e-9, [b.snapshot() for b in self.branches],
            {}, False, False, [], {},
        ))

    def _filter(self, event: dict, replay: bool = False) -> dict:
        packet = dict(event)
        block = packet.get("carrier")
        # The source declares measurement counts, not truth failure labels.
        # Real DD sets have changing dimension and pivot. Their physical partial
        # relation comparison is emitted separately; a five-relation synthetic
        # rule must never erase a real observation block.
        full_count = self.metadata.get("full_phase_relations", None if self.asynchronous_start else 5)
        if (block is not None and not self.use_partial and full_count is not None
                and len(block.ambiguity_labels) < int(full_count)):
            packet["carrier"] = code_only(block)
        # U2 stops future use at discovery, U3 rebuilds the past with the same
        # physically restricted common-translation model.
        return packet

    def _initialized(self):
        return self.branches[0].index is not None and self.branches[0].bootstrap_status != "NO_INIT"

    def _try_bootstrap(self, packet: dict, index: int, common_anchors=None, *, record_anchors=False):
        """Use only arrived observations in one finite asynchronous startup graph.

        Finite yaw seeds locate conditional modes. Their convergence is neither
        global directional coverage nor an integer-fix or trust declaration.
        """
        t = float(packet["time_s"])
        # A fresh external observation may make the buffered joint graph
        # identifiable. Foot/IMU/PV can supply direction before any carrier;
        # the existing rank and nonlinear stationarity checks decide locally.
        fresh_external = any(packet.get(name) is not None for name in
                             ("carrier", "gnss_position", "gnss_velocity"))
        if not fresh_external or t-self.bootstrap_last_attempt < 1.:
            return False
        if common_anchors is not None and not common_anchors:
            self.bootstrap_diagnostic = dict(status="NO_INIT", reason="WAITING_FOR_COMMON_BOOTSTRAP_ANCHOR")
            return False
        buffered = [(i, self._filter(e)) for i, e in self.events
                    if i <= index and t-self.bootstrap_window_s <= e["time_s"] <= t]
        positions = [j for j, (_, e) in enumerate(buffered) if e.get("gnss_position") is not None]
        if not positions:
            self.bootstrap_diagnostic = dict(status="NO_INIT", reason="NO_POSITION_IN_CAUSAL_BUFFER")
            return False
        buffered = buffered[positions[0]:]
        if not any(e.get("gnss_velocity") is not None for _, e in buffered):
            self.bootstrap_diagnostic = dict(status="NO_INIT", reason="NO_VELOCITY_IN_CAUSAL_BUFFER")
            return False
        self.bootstrap_last_attempt = t
        # IMU tilt supplies Values only. No static-body assumption is inserted
        # as a measurement and no artificial yaw prior is used.
        seed_imu = [e["imu"] for _, e in buffered
                    if e["time_s"] <= buffered[0][1]["time_s"]+.2 and len(e["imu"])]
        roll = pitch = 0.
        if seed_imu:
            rates = np.concatenate(seed_imu)
            gravity_body = -np.average(rates[:, 1:4], axis=0, weights=rates[:, 0])
            roll = math.atan2(gravity_body[1], gravity_body[2])
            pitch = math.atan2(-gravity_body[0], math.hypot(gravity_body[1], gravity_body[2]))
        solutions, reports = [], []
        seeds = [(gtsam.Rot3.RzRyRx(roll, pitch, yaw), None)
                 for yaw in (0., math.pi/2., math.pi, -math.pi/2.)]
        if common_anchors is not None:
            seeds = [(anchor["values"].atPose3(X(buffered[0][0])).rotation(), anchor)
                     for anchor in common_anchors]
        for seed_rotation, anchor in seeds:
            branch = NavigationBranch(self.metadata, use_foot=self.use_foot)
            diagnostic = branch.bootstrap([e for _, e in buffered], seed_rotation,
                start_index=buffered[0][0], support_models=self._models_at(t),
                linearization_anchor=anchor)
            reports.append(diagnostic)
            if diagnostic["local_full_rank"] and diagnostic["solver_converged"]:
                solutions.append(branch)
        self.bootstrap_diagnostic = dict(
            status="NO_INIT", first_time_s=buffered[0][1]["time_s"], last_time_s=t,
            first_index=buffered[0][0], frontier_index=index, conditional_seed_reports=reports,
            locally_identifiable_converged_modes=len(solutions),
            computationally_unresolved_seeds=sum(not report["solver_converged"] for report in reports),
            yaw_seeds_rad=[float(seed.yaw()) for seed, _ in seeds],
            qualification_scope=("COMMON_LINEARIZATION_ONLY" if common_anchors is not None else
                                 "LOCAL_NONLINEAR_STATIONARITY"),
            directional_global_coverage_certified=False, gravity_observation_added=False,
            future_observations_used=False, already_published_rows_revised=0)
        if not solutions:
            self.bootstrap_diagnostic["reason"] = "BUFFERED_GRAPH_NOT_LOCALLY_IDENTIFIABLE"
            self.decisions.append(dict(time_s=t, kind="ASYNCHRONOUS_BOOTSTRAP_UNRESOLVED",
                                       **self.bootstrap_diagnostic))
            return False
        costs = np.array([b.window.error() for b in solutions])
        supported = [b for b, cost in zip(solutions, costs) if 2.*(cost-costs.min()) <= self.profile_support_delta]
        # Duplicate numerical starts at the same local solution carry no extra
        # evidence. Distinct solutions remain distinct conditional states.
        modes = []
        for branch in sorted(supported, key=lambda b: b.window.error()):
            if any(np.linalg.norm(gtsam.Rot3.Logmap(other.pose.rotation().between(branch.pose.rotation()))) < 1e-5
                   and np.linalg.norm(other.velocity-branch.velocity) < 1e-5
                   and np.linalg.norm(other.pose.translation()-branch.pose.translation()) < 1e-5
                   and all(abs(other.window.values.atVector(other.ambiguity_keys[label])[0]
                               -branch.window.values.atVector(key)[0]) < 1e-4
                           for label, key in branch.ambiguity_keys.items()) for other in modes):
                continue
            modes.append(branch)
        qualification = dict(qualified=True, scope="LOCAL_FULL_RANK_CONDITIONAL_STATE_ONLY",
            globally_certified=False, finite_seed_search=True, modes_retained=len(modes),
            initial_direction_status="FLOAT_INIT_DIRECTION_UNRESOLVED")
        if common_anchors is not None:
            qualification["scope"] = "COMMON_LINEARIZATION_ONLY"
        if self.shared_support or record_anchors:
            self.anchor_history.setdefault(index, {})["bootstrap"] = [
                branch.export_linearization_anchor() for branch in modes]
        for branch in modes:
            branch.accept_bootstrap(qualification)
            branch.predictive_frontier = index
        self.branches = modes
        # An unfinished local solve is not a scientifically excluded direction.
        self.support_incomplete |= any(not report["solver_converged"] for report in reports)
        self.bootstrap_diagnostic.update(status="FLOAT_INIT_DIRECTION_UNRESOLVED", retained_modes=len(modes))
        # Recover from before the first actually consumed support, not from an
        # arbitrary time zero or a state contaminated by the startup factors.
        empty = NavigationBranch(self.metadata, use_foot=self.use_foot)
        self.checkpoints = [Checkpoint(buffered[0][0]-1, buffered[0][1]["time_s"]-1e-9,
            [empty.snapshot()], {}, False, False, [], {})]
        self.last_checkpoint_time = -math.inf
        self.arc_first_use = {}
        for _, event in buffered:
            for foot in event.get("feet", []):
                self.arc_first_use.setdefault(foot["arc_id"], event["time_s"])
        self.decisions.append(dict(time_s=t, kind="ASYNCHRONOUS_FLOAT_STATE_INITIALIZED",
                                   **self.bootstrap_diagnostic))
        return True

    def _no_init_output(self, t):
        return dict(time_s=t, p=np.full(3, np.nan), v=np.full(3, np.nan),
            rpy_rad=np.full(3, np.nan), bias=np.full(6, np.nan),
            direction_status="NO_INIT", initialization_status="NO_INIT",
            initialization_diagnostic=copy.deepcopy(self.bootstrap_diagnostic),
            candidate_yaws_rad=[], candidate_costs=[], candidate_local_directions=[],
            candidate_supported=[], candidate_support_complete=False,
            support_ids=[], gnss_innovation_nis=None, branch_conditional_navigation=False,
            revocation=False, replay_performed=False)

    def _released(self, time_s: float) -> set[str]:
        if self.rebuild_history:
            return set(self.revoked_arcs)
        return {arc for arc, discovered in self.stop_from.items() if time_s >= discovered}

    def _models_at(self, time_s: float) -> list[dict]:
        return [model for model in self.support_models
                if time_s >= model.get("effective_from", -math.inf)]

    def _score_prediction(self, packet: dict, index: int, expected_rows=None):
        """Score each real integer lineage before this event is consumed.

        Different models compare marginal blocks of identical physical rows.
        With foot_external, fixed and finite-motion models compare a proper
        joint prediction of existing-foot and external rows, conditional on IMU.
        The legacy mode compares external rows only. Neither is a calibrated
        model probability, and neither re-scores already consumed measurements.
        """
        self.last_external_prediction_nis = None
        self.last_external_prediction_dimension = 0
        self.last_prediction_blocks = []
        has_external = any(packet.get(name) is not None for name in ("carrier", "gnss_position", "gnss_velocity"))
        has_foot = self.support_prediction == "foot_external" and self.use_foot and bool(packet.get("feet"))
        if self.branches[0].index is None or not (has_external or has_foot):
            return (), 0.
        predictions = [branch.predict_external(packet, support_models=self._models_at(packet["time_s"]))
                       for branch in self.branches]
        common = set(predictions[0]["row_ids"])
        for prediction in predictions[1:]:
            common.intersection_update(prediction["row_ids"])
        rows = tuple(row for row in predictions[0]["row_ids"] if row in common)
        if expected_rows is not None:
            if not set(expected_rows).issubset(common):
                raise ValueError("support models do not share the reference prediction rows")
            rows = tuple(expected_rows)
        if rows:
            self.predictive_rows_fingerprint = hashlib.sha256(
                (self.predictive_rows_fingerprint+repr((index, rows))).encode()).hexdigest()
        position_nis, external_nis = 0., []
        for branch, prediction in zip(self.branches, predictions):
            if index <= branch.predictive_frontier:
                raise ValueError("a prediction event was scored twice in one integer lineage")
            branch.predictive_frontier = index
            foot_prediction_scope = dict(
                predicted_foot_arcs=prediction.get("predicted_foot_arcs", []),
                excluded_contact_birth_arcs=prediction.get("excluded_contact_birth_arcs", []))
            if not rows:
                self.last_prediction_blocks.append(dict(
                    integer_lineage=branch.integer_lineage, joint_dimension=0,
                    external_dimension=0, conditional_foot_dimension=0,
                    score_accumulations=0, scope=self.support_prediction,
                    **foot_prediction_scope))
                continue
            positions = [prediction["row_ids"].index(row) for row in rows]
            residual = prediction["innovation"][positions]
            covariance = prediction["covariance"][np.ix_(positions, positions)]
            chol = np.linalg.cholesky(covariance)
            whitened = np.linalg.solve(chol, residual)
            joint_nis = float(whitened@whitened)
            external_nis.append(joint_nis)
            joint_score = float(
                whitened @ whitened + 2.*np.log(np.diag(chol)).sum()
                + len(rows)*math.log(2.*math.pi))
            branch.predictive_score += joint_score
            branch.predictive_row_count += len(rows)
            external = [j for j, row in enumerate(rows) if not row.startswith("foot:")]
            external_score, external_block_nis = 0., 0.
            if external:
                external_chol = np.linalg.cholesky(covariance[np.ix_(external, external)])
                external_white = np.linalg.solve(external_chol, residual[external])
                external_block_nis = float(external_white@external_white)
                external_score = float(external_block_nis + 2.*np.log(np.diag(external_chol)).sum()
                                       + len(external)*math.log(2.*math.pi))
            self.last_prediction_blocks.append(dict(
                integer_lineage=branch.integer_lineage, joint_dimension=len(rows),
                external_dimension=len(external), conditional_foot_dimension=len(rows)-len(external),
                joint_nis=joint_nis, external_marginal_nis=external_block_nis,
                conditional_foot_nis=joint_nis-external_block_nis,
                joint_negative_twice_log_density=joint_score,
                external_marginal_negative_twice_log_density=external_score,
                conditional_foot_negative_twice_log_density=joint_score-external_score,
                score_accumulations=1, scope=self.support_prediction,
                **foot_prediction_scope))
            if packet.get("gnss_position") is not None:
                p = [j for j, row in enumerate(rows) if row.startswith("gnss_position:")]
                r = residual[p]
                position_nis = float(r @ np.linalg.solve(covariance[np.ix_(p, p)], r))
        if external_nis:
            self.last_external_prediction_nis = min(external_nis)
            self.last_external_prediction_dimension = len(rows)
        return rows, position_nis

    @staticmethod
    def _matching_anchor(branch, anchors):
        anchors = [anchor for anchor in anchors if
                   anchor["background_chart_id"] == branch.background_chart_id]
        exact = [anchor for anchor in anchors if anchor["integer_lineage"] == branch.integer_lineage]
        if len(exact) == 1:
            return exact[0]
        # A unique parent chart may be conditioned by newly introduced integer
        # relations. Multiple different parent/child charts are not averaged.
        parents = [anchor for anchor in anchors if
                   branch.integer_lineage[:len(anchor["integer_lineage"])] == anchor["integer_lineage"]]
        return parents[0] if len(parents) == 1 else None

    def _advance(self, packet: dict, index: int, expected_rows=None, shared_anchors=None, *, record_anchors=False):
        if self.asynchronous_start and not self._initialized():
            self._try_bootstrap(packet, index,
                None if shared_anchors is None else shared_anchors.get("bootstrap", []),
                record_anchors=record_anchors)
            if self._initialized():
                if self.shared_support or record_anchors:
                    self.anchor_history.setdefault(index, {})["step"] = [b.export_linearization_anchor() for b in self.branches]
                self._propose(index, packet, None if shared_anchors is None else shared_anchors.get("conditioned", []))
                if self.shared_support or record_anchors:
                    self.anchor_history.setdefault(index, {})["conditioned"] = [b.export_linearization_anchor() for b in self.branches]
                self._compress_gaussian_histories(packet)
            return (), 0.
        anchors = [None]*len(self.branches) if shared_anchors is None else [
            self._matching_anchor(branch, shared_anchors.get("step", [])) for branch in self.branches]
        if shared_anchors is not None and any(anchor is None for anchor in anchors):
            return None
        for foot in packet.get("feet", []):
            self.arc_first_use.setdefault(foot["arc_id"], packet["time_s"])
        rows, nis = self._score_prediction(packet, index, expected_rows)
        for branch, anchor in zip(self.branches, anchors):
            branch.step(packet, index, support_models=self._models_at(packet["time_s"]),
                        linearization_anchor=anchor)
        if self.shared_support or record_anchors:
            self.anchor_history.setdefault(index, {})["step"] = [b.export_linearization_anchor() for b in self.branches]
        self._propose(index, packet, None if shared_anchors is None else shared_anchors.get("conditioned", []))
        if self.shared_support or record_anchors:
            self.anchor_history.setdefault(index, {})["conditioned"] = [b.export_linearization_anchor() for b in self.branches]
        self._compress_gaussian_histories(packet)
        return rows, nis

    def _compress_gaussian_histories(self, packet):
        """Eliminate only coordinates outside the future measurement separator.

        Consumed Gaussian history is frozen; source models and their scores are
        retained. The nonlinear reference continues its original fixed lag.
        """
        if self.gaussian_future_separator:
            for branch in self.branches:
                if branch.window.gaussian_only:
                    report = branch.compress_gaussian_history(packet)
                    self.gaussian_compressed_key_count += report["eliminated_key_count"]
                    self.maximum_gaussian_separator_dimension = max(
                        self.maximum_gaussian_separator_dimension, report["separator_dimension"])

    def _restore(self, checkpoint: Checkpoint):
        self.branches = []
        for snapshot in checkpoint.branches:
            branch = NavigationBranch(self.metadata, use_foot=self.use_foot)
            branch.restore(snapshot)
            self.branches.append(branch)
        self.proposal_times = dict(checkpoint.proposal_times)
        self.proposal_retry_after = dict(checkpoint.proposal_retry_after or {})
        self.pending_proposals = dict(checkpoint.pending_proposals or {})
        self.proposal_complete = checkpoint.proposal_complete
        self.support_incomplete = checkpoint.support_incomplete
        self.dormant_candidates = copy.deepcopy(checkpoint.candidates)
        self.arc_first_use = dict(checkpoint.arc_first_use)
        self.bootstrap_last_attempt = checkpoint.bootstrap_last_attempt
        self.predictive_rows_fingerprint = checkpoint.predictive_rows_fingerprint
        self.bootstrap_diagnostic = copy.deepcopy(checkpoint.bootstrap_diagnostic or
            dict(status="NO_INIT", reason="RECONSTRUCT_FROM_PRE_USE_CHECKPOINT"))

    def _candidate_policy(self, arc_ids, model, group_id, *, base_policy=None):
        """Replacement preserves disjoint old components, never duplicates an arc."""
        return replace_group(self.support_models if base_policy is None else base_policy,
                             arc_ids, model, group_id)

    def _create_policy_track(self, policy, parent_id, ids, model, group_id, index):
        policy = canonical_policy(policy)
        identity = policy_identity(policy)
        if identity == policy_identity(self.support_models) or identity == parent_id:
            return None
        if identity in self.support_tracks:
            self.support_tracks[identity].parent_ids.add(parent_id)
            return None
        first = min(self.arc_first_use[arc] for part in policy for arc in part["arc_ids"])
        origins = [*self.checkpoints, *(track.origin for track in self.support_tracks.values()),
                   *(group["origin"] for group in self.support_groups.values() if group.get("origin") is not None)]
        prior = [origin for origin in origins if origin.time_s < first]
        if not prior:
            self.support_groups[ids]["status"] = "UNRESOLVED_HISTORY_EXPIRED"
            return None
        # Before every edited source's first use the full policy and root
        # policy coincide. No parent score or contaminated posterior is spliced.
        origin = max(prior, key=lambda checkpoint: (checkpoint.time_s, checkpoint.index))
        shadow = JointNavigator(self.metadata, self.mode, monitor_support=False, support_models=list(policy))
        shadow._restore(origin)
        track = SupportTrack(identity, group_id, ids, model, first, origin, shadow,
                             policy=policy, parent_ids={parent_id}, edit_count=len(policy), created_index=index)
        self.support_tracks[identity] = track
        if self.shared_support and self.expand_support_policy_paths:
            self.policy_parent_cursors[identity] = 0
            self._queue_policy_parent(identity)
        return track

    def _queue_policy_parent(self, identity):
        if (self.policy_parent_cursors[identity] < len(self.support_group_order)
                and identity not in self.policy_queue_tickets):
            self.policy_queue_tickets[identity] = self.policy_ticket_serial
            self.policy_ticket_serial += 1

    def _policy_search_readout(self):
        pending = sum(len(self.support_group_order)-cursor for cursor in self.policy_parent_cursors.values())
        expired = sum(group["status"] == "UNRESOLVED_HISTORY_EXPIRED" for group in self.support_groups.values())
        unresolved_frontiers = sum(track.unresolved_reason is not None or not self._same_predictive_rows(track.navigator)
                                   for track in self.support_tracks.values())
        return dict(scope=("OBSERVED_GROUP_REPLACEMENT_POLICY_PATHS" if self.expand_support_policy_paths
                           else "OBSERVED_SINGLE_GROUP_PROPER_CONDITIONAL_MODELS"),
            alternative_models=list(self.support_alternative_models),
            multigroup_policy_combinations_searched=self.expand_support_policy_paths,
            exploration_started=self.policy_exploration_started,
            exploration_tail_probability=self.policy_exploration_tail_probability,
            exploration_threshold_role="WORKING_COMPUTE_SCHEDULER_NOT_TRUST_OR_ACCEPTANCE_GATE",
            pending_parent_group_items=pending, queued_parent_count=len(self.policy_queue_tickets),
            unresolved_history_groups=expired, unresolved_policy_frontiers=unresolved_frontiers,
            extension_items_processed=self.policy_extension_items,
            continuation_nodes_created=self.policy_extension_nodes,
            registered_policy_count=len(self.support_tracks), registered_group_count=len(self.support_group_order),
            evaluated_policy_coverage_complete=pending == 0 and expired == 0 and unresolved_frontiers == 0,
            construction="ONE_EVIDENCE_PRIORITY_AND_ONE_FIFO_ITEM_PER_EXTERNAL_EPOCH_AFTER_ACTIVATION",
            unsupported_parent_cursors_retained=True, depth_limit=None,
            overlap_semantics="REPLACE_OVERLAPPING_ARCS_NOT_INDEPENDENT_OVERLAPPING_FAULTS",
            fairness="FINITE_QUEUE_PREFIX_WITH_CONTINUED_COMPUTE;NO_BOUNDED_DELAY_ON_INFINITE_STREAM",
            policy_state_storage_bounded=False)

    def _policy_descriptor(self, track):
        policy = self.support_models if track is None else track.policy
        return dict(source_policy=policy_readout(policy), source_policy_id=policy_identity(policy),
                    parent_policy_ids=[] if track is None else sorted(track.parent_ids),
                    policy_edit_count=len(policy))

    def _extend_policy_paths(self, packet, index):
        if (not self.shared_support or not self.expand_support_policy_paths
                or not self.reference_rows.get(index) or index <= self.policy_last_extension_frontier):
            return
        self.policy_last_extension_frontier = index
        threshold = (float(chi2.isf(self.policy_exploration_tail_probability, self.last_external_prediction_dimension))
                     if self.last_external_prediction_dimension else None)
        incompatible = (threshold is not None and self.last_external_prediction_nis is not None
                        and self.last_external_prediction_nis > threshold)
        if not self.policy_exploration_started and (self.last_supported_tracks or incompatible):
            self.policy_exploration_started = True
            self.decisions.append(dict(time_s=packet["time_s"], kind="POLICY_PATH_EXPLORATION_ACTIVATED",
                reason="NONFIXED_POLICY_SUPPORTED" if self.last_supported_tracks else "NOMINAL_EXTERNAL_PREDICTION_INCOMPATIBLE",
                nominal_best_integer_lineage_nis=self.last_external_prediction_nis,
                observed_row_dimension=self.last_external_prediction_dimension, working_chi_square_threshold=threshold,
                working_tail_probability=self.policy_exploration_tail_probability,
                threshold_is_acceptance_gate=False))
        if not self.policy_exploration_started:
            return
        for route in ("EVIDENCE_PRIORITY", "FIFO_FAIR_EXPLORATION"):
            eligible = [identity for identity in self.policy_queue_tickets
                        if self.support_tracks[identity].created_index < index
                        and self.support_tracks[identity].unresolved_reason is None
                        and self._same_predictive_rows(self.support_tracks[identity].navigator)]
            if not eligible:
                break
            if route == "EVIDENCE_PRIORITY":
                identity = min(eligible, key=lambda item: (item not in self.last_supported_tracks,
                    min(branch.predictive_score for branch in self.support_tracks[item].navigator.branches)
                    + self.model_edit_cost*self.support_tracks[item].edit_count,
                    self.policy_queue_tickets[item]))
            else:
                identity = min(eligible, key=self.policy_queue_tickets.get)
            parent = self.support_tracks[identity]
            ids = self.support_group_order[self.policy_parent_cursors[identity]]
            group = self.support_groups[ids]
            del self.policy_queue_tickets[identity]
            self.policy_parent_cursors[identity] += 1
            self._queue_policy_parent(identity)
            created = []
            for model in self.support_alternative_models:
                policy = self._candidate_policy(ids, model, group["group_id"], base_policy=parent.policy)
                track = self._create_policy_track(policy, identity, ids, model, group["group_id"], index)
                if track is not None:
                    self._advance_support_track(track, index)
                    created.append(track.identity)
            self.policy_extension_items += 1
            self.policy_extension_nodes += len(created)
            self.decisions.append(dict(time_s=packet["time_s"], kind="SOURCE_POLICY_PATH_ITEM_EXPLORED",
                route=route, parent_policy_id=identity, observed_group_id=group["group_id"],
                parent_was_supported=identity in self.last_supported_tracks,
                created_policy_ids=created, parent_score_is_not_descendant_bound=True))

    def _register_support_group(self, packet: dict):
        t = float(packet["time_s"])
        observed = packet.get("active_support_arcs")
        if observed is None:
            observed = [foot["arc_id"] for foot in packet.get("feet", [])]
        ids = tuple(sorted(arc for arc in observed if arc in self.arc_first_use))
        if len(ids) >= 2 and ids not in self.support_groups:
            first = min(self.arc_first_use[arc] for arc in ids)
            prior = [c for c in self.checkpoints if c.time_s < first]
            group_id = "support:" + "|".join(ids)
            self.support_groups[ids] = dict(first_use=first, group_id=group_id,
                                             status="PENDING", last_observed=t,
                                             origin=prior[-1] if prior else None)
            self.support_group_order.append(ids)
            for identity in self.policy_parent_cursors:
                self._queue_policy_parent(identity)
            if prior:
                for model in self.support_alternative_models:
                    self._create_policy_track(self._candidate_policy(ids, model, group_id),
                        "fixed", ids, model, group_id, self.branches[0].index)
            else:
                self.support_groups[ids]["status"] = "UNRESOLVED_HISTORY_EXPIRED"
                self.expired_unresolved_groups += 1
        if ids in self.support_groups:
            self.support_groups[ids]["last_observed"] = t
        return ids

    def _update_support_tracks(self, packet: dict, index: int):
        """Compare competing observed groups at one common evidence frontier."""
        t = float(packet["time_s"])
        if self.rescan_support_history:
            for _, old in self.events:
                self._register_support_group(old)
            self.rescan_support_history = False
        ids = self._register_support_group(packet)
        self.linearization_reference_used = "fixed" if self.shared_support else None
        expired = []
        tracks = list(self.support_tracks.items())
        reference = self.linearization_reference_identity if self.shared_support else None
        # Advance the previously published nonlinear conditional first. Its
        # posterior at this event is then a shared chart, not a new factor or a
        # substitute for any model's predictive evidence accumulated so far.
        tracks.sort(key=lambda item: item[0] != reference)
        for identity, track in tracks:
            supplies_reference = identity == reference and track.nonlinear_expanded
            if (not self.shared_support and t-track.first_use > self.history_s and
                    not set(track.arc_ids).intersection(ids) and
                    identity not in self.last_supported_tracks):
                expired.append(identity)
                if self.support_groups[track.arc_ids]["status"] != "UNRESOLVED_HISTORY_EXPIRED":
                    self.expired_unresolved_groups += 1
                self.support_groups[track.arc_ids]["status"] = "UNRESOLVED_HISTORY_EXPIRED"
                continue
            self._advance_support_track(track, index, supplies_reference=supplies_reference)
        for identity in expired:
            del self.support_tracks[identity]
        result = self._contact_support(packet)
        if self.shared_support:
            self._extend_policy_paths(packet, index)
            result = self._contact_support(packet)
        while self.shared_support:
            alternatives, costs, in_support, winner, _ = result
            fixed_supported = any(in_support[j] and item[0] == "fixed" for j, item in enumerate(alternatives))
            track = alternatives[winner][3]
            if not fixed_supported and track is not None and not track.nonlinear_expanded:
                self._expand_support_history(track, index, t)
                result = self._contact_support(packet)
            else:
                break
        return result

    def _advance_support_track(self, track, index, *, supplies_reference=False):
        shadow = track.navigator
        replay_events = self.recovery_events if self.shared_support else self.events
        replay_rows = self.recovery_rows if self.shared_support else self.reference_rows
        shadow.events = replay_events
        after = shadow.branches[0].index
        after = -1 if after is None else after
        for event_index, event in replay_events:
            if after < event_index <= index:
                try:
                    outcome = shadow._advance(shadow._filter(event), event_index, replay_rows[event_index],
                        self.anchor_history.get(event_index, {})
                        if self.shared_support and not track.nonlinear_expanded else None,
                        record_anchors=supplies_reference)
                    if outcome is None:
                        track.unresolved_reason = "UNRESOLVED_COMMON_INTEGER_LINEAGE_ANCHOR"
                        break
                    track.unresolved_reason = None
                except RuntimeError:
                    print(f"FAILED_SUPPORT_MODEL identity={track.identity} time={event['time_s']} "
                          f"index={event_index} origin={track.origin.time_s}", flush=True)
                    raise
                track.processed_events += 1
                self.model_replay_events += 1
                if self.shared_support and not track.nonlinear_expanded:
                    self.gaussian_support_step_events += 1
                else:
                    self.nonlinear_support_step_events += 1
        if supplies_reference and self._same_predictive_rows(shadow):
            charts = shadow.anchor_history.pop(index, None)
            if charts is not None:
                for anchors in charts.values():
                    for anchor in anchors:
                        anchor["reference_support_identity"] = track.identity
                self.anchor_history[index] = charts
                self.linearization_reference_used = track.identity

    def _expand_support_history(self, track, index, time_s):
        """Reconstruct an actual nonlinear conditional history, not just future R."""
        rebuilt = JointNavigator(self.metadata, self.mode, monitor_support=False,
            support_models=list(track.policy))
        rebuilt._restore(track.origin)
        rebuilt.events = self.recovery_events
        count = 0
        for event_index, event in self.recovery_events:
            if track.origin.index < event_index <= index:
                rebuilt._advance(rebuilt._filter(event), event_index, self.recovery_rows[event_index])
                count += 1
        old_score = min(branch.predictive_score for branch in track.navigator.branches)
        track.navigator = rebuilt
        track.nonlinear_expanded = True
        track.processed_events = count
        self.nonlinear_support_expansions += 1
        self.model_replay_events += count
        self.decisions.append(dict(time_s=time_s, kind="NONLINEAR_CONDITIONAL_HISTORY_EXPANDED",
            support_identity=track.identity, first_use_s=track.first_use,
            source_policy=policy_readout(track.policy), parent_policy_ids=sorted(track.parent_ids),
            policy_edit_count=track.edit_count,
            checkpoint_time_s=track.origin.time_s, replayed_events=count,
            common_linearization_score_before=old_score,
            nonlinear_predictive_score=min(branch.predictive_score for branch in rebuilt.branches),
            globally_unique_explanation=False, historical_online_rows_rewritten=0))

    def _same_predictive_rows(self, other):
        return (other._initialized()
                and {(b.index, b.time) for b in other.branches} == {(b.index, b.time) for b in self.branches}
                and other.predictive_rows_fingerprint == self.predictive_rows_fingerprint
                and {b.predictive_frontier for b in other.branches} == {b.predictive_frontier for b in self.branches}
                and {b.predictive_row_count for b in other.branches} == {b.predictive_row_count for b in self.branches})

    def _contact_support(self, packet: dict):
        alternatives = [("fixed", branch, self.model_edit_cost*len(self.support_models), None) for branch in self.branches]
        for identity, track in self.support_tracks.items():
            if track.unresolved_reason is None and self._same_predictive_rows(track.navigator):
                alternatives.extend((identity, branch, self.model_edit_cost*track.edit_count, track)
                                    for branch in track.navigator.branches)
        costs = np.array([branch.predictive_score+penalty for _, branch, penalty, _ in alternatives])
        winner = int(np.argmin(costs))
        supported = costs-costs[winner] <= self.model_support_delta
        identities = {alternatives[j][0] for j in np.flatnonzero(supported)}
        self.last_supported_tracks = identities - {"fixed"}
        signature = (alternatives[winner][0], tuple(sorted(identities)))
        if signature != self.last_support_signature:
            self.decisions.append(dict(
                time_s=packet["time_s"], kind="CONTACT_MODEL_PREDICTIVE_SUPPORT",
                selected=signature[0], supported_models=list(signature[1]),
                selected_source_policy=policy_readout(self.support_models if alternatives[winner][3] is None
                                                      else alternatives[winner][3].policy),
                fixed_contact_in_support="fixed" in identities,
                working_edit_cost=self.model_edit_cost,
                working_support_delta=self.model_support_delta,
                fixed_minus_best_score=float(min(b.predictive_score for b in self.branches)
                                            +self.model_edit_cost*len(self.support_models)-costs[winner]),
                compared_groups=len(self.support_groups), evaluated_models=len(self.support_tracks),
                integer_lineage_scores=True, probability_calibrated=False,
                policy_selection_scope="BEST_AMONG_EVALUATED_POLICIES",
                policy_search=self._policy_search_readout(),
                comparison_scope=("MIXED_NONLINEAR_AND_COMMON_LINEARIZATION_CONDITIONAL_MODELS"
                                  if self.shared_support else "FULL_NONLINEAR_CONDITIONAL_MODELS"),
            ))
            self.last_support_signature = signature
        selected = alternatives[winner][3]
        complete = self.proposal_complete and all(
            track.navigator.proposal_complete and self._same_predictive_rows(track.navigator)
            for track in self.support_tracks.values())
        if self.shared_support:
            complete = complete and all(track.nonlinear_expanded for track in self.support_tracks.values())
            complete = complete and self._policy_search_readout()["evaluated_policy_coverage_complete"]
        # Only a unique source explanation commits a model change. Otherwise
        # U3 retains the separate clean conditional states and their directions.
        accepted = selected if (not self.shared_support and len(identities) == 1
                                and "fixed" not in identities and complete) else None
        # Shared-chart selection is a reversible conditional reference choice.
        # It must not enter the legacy adopt/clear path, which discards the old
        # fixed model and prevents reinstating a released source component.
        return alternatives, costs, supported, winner, accepted

    def _save(self, index: int, time_s: float):
        if time_s - self.last_checkpoint_time < 0.95:
            return
        self.checkpoints.append(Checkpoint(
            index, time_s, [b.snapshot() for b in self.branches],
            dict(self.proposal_times), self.proposal_complete,
            self.support_incomplete,
            copy.deepcopy(self.dormant_candidates), dict(self.arc_first_use),
            self.bootstrap_last_attempt, copy.deepcopy(self.bootstrap_diagnostic),
            self.predictive_rows_fingerprint, dict(self.proposal_retry_after), dict(self.pending_proposals),
        ))
        self.checkpoints = [c for c in self.checkpoints if c.time_s >= time_s - self.history_s]
        self.last_checkpoint_time = time_s

    def _physical_integer_conditions(self, fixed, labels):
        if not self.asynchronous_start or not fixed:
            return []
        history = tuple(fixed)
        transition = analyze_relation_transition(history, labels, label_mode="physical_sd_arcs")
        values = np.array([fixed[label] for label in history], dtype=np.int64)
        return [dict(coefficients=tuple((label, int(value)) for label, value in zip(labels, row) if value),
                     rhs_integer=int(rhs), source="INHERITED_CONDITIONAL_PHYSICAL_ARC_RELATION")
                for row, rhs in zip(transition.current_transform, transition.history_transform@values)]

    def _propose(self, index: int, packet: dict, conditioned_anchors=None):
        block = packet.get("carrier")
        if block is None or not block.ambiguity_labels:
            return
        current_labels = tuple(block.ambiguity_labels)
        if all(all(label in branch.fixed for label in current_labels) for branch in self.branches):
            return
        recent = []
        for event_index, raw in self.events:
            if event_index > index or raw["time_s"] < packet["time_s"]-0.8:
                continue
            candidate_block = self._filter(raw).get("carrier")
            if candidate_block is not None and candidate_block.ambiguity_labels and (
                    self.asynchronous_start or tuple(candidate_block.ambiguity_labels) == current_labels):
                recent.append(candidate_block)
        if len(recent) < 4:
            return
        coordinate_metadata = None
        temporal_covariance = None
        noise_parameters = self.metadata.get("phase_noise_model")
        if noise_parameters is not None:
            parameters = NoiseParameters(**{name: noise_parameters[name] for name in
                ("white_sd_sigma_m", "beta_sd_sigma_m", "tau_s")})
            noise = assemble_source_noise_covariance(recent, parameters)
            temporal_covariance = noise.total
            # The graph keeps explicit beta states. The raw-only proposal
            # integrates the same stationary beta process out, including its
            # cross-time covariance. These are proposal copies, not new data.
            recent = [EpochBlock(block.time_s, block.y, block.A, block.B,
                temporal_covariance[section, section], block.ambiguity_labels,
                dict(block.metadata, phase_noise_model_scope="MARGINAL_PHYSICAL_SD_SOURCE_PROCESS"))
                for block, section in zip(recent, noise.row_slices)]
        if self.asynchronous_start:
            physical = reparameterize_epoch_blocks(recent, label_mode="physical_sd_arcs",
                                                   available_time_s=packet["time_s"])
            recent, labels = physical.blocks, physical.basis_labels
            coordinate_metadata = physical.basis_metadata
        else:
            labels = current_labels
        # A cohort is identified by physical integer coordinates, independent
        # of transient DD pivots. Raw rows and complete Q are not projected.
        if labels in self.proposal_times:
            retry_at = self.proposal_retry_after.get(labels)
            if retry_at is None or packet["time_s"] < retry_at:
                return
        common_fixed = {label: value for label, value in self.branches[0].fixed.items()
                        if all(branch.fixed.get(label) == value for branch in self.branches)}
        linear_conditions = self._physical_integer_conditions(common_fixed, labels)
        proposal = propose_candidates(recent, np.asarray(self.metadata["baseline_body"]), self.active_limit,
            conditioned_integer_by_label=common_fixed, conditioned_linear_relations=linear_conditions,
            temporal_covariance=temporal_covariance)
        if coordinate_metadata is not None:
            proposal.metadata["physical_window_coordinates"] = coordinate_metadata
        if noise_parameters is not None:
            proposal.metadata["phase_noise_model"] = copy.deepcopy(noise_parameters)
            proposal.metadata["source_noise_covariance_scope"] = "FULL_TEMPORAL_STATIONARY_SD_OU_MARGINAL"
            proposal.metadata["source_noise_probability_calibrated"] = False
        self.proposal_attempts += 1
        self.proposal_times[labels] = packet["time_s"]
        if self.asynchronous_start and (not proposal.active or not proposal.metadata["active_support_complete"]):
            # Reconsider only when the whole finite raw window has advanced.
            # A failed first window must not permanently close a physical arc;
            # neither its cost nor subsequent overlapping costs become factors.
            self.proposal_retry_after[labels] = packet["time_s"]+.8
        else:
            self.proposal_retry_after.pop(labels, None)
        proposal.metadata["raw_window_time_s"] = [recent[0].time_s, recent[-1].time_s]
        proposal.metadata["next_attempt_not_before_s"] = self.proposal_retry_after.get(labels)
        # Empty proposals have not discarded a float branch. They are a
        # retryable unresolved work window, distinct from omitted active modes.
        if proposal.active:
            self.support_incomplete |= not proposal.metadata["active_support_complete"]
        self.proposal_complete = not self.support_incomplete and not self.pending_proposals
        for candidate in proposal.dormant:
            self.dormant_candidates.append(dict(
                integer_by_label=candidate.integer_by_label, raw_cost=candidate.raw_cost,
                reason="COMPUTATION_BUDGET_NOT_SCIENTIFIC_EXCLUSION",
                proposal_time_s=packet["time_s"],
            ))
        if not proposal.active:
            self.pending_proposals[labels] = dict(time_s=packet["time_s"], status=proposal.metadata["status"])
            self.proposal_complete = False
            self.decisions.append(dict(time_s=packet["time_s"], kind="RAW_SUPPORT_UNRESOLVED",
                                       proposal=proposal.metadata))
            return

        expanded = []
        for parent in self.branches:
            for candidate in proposal.active:
                if any(label in parent.fixed and parent.fixed[label] != value
                       for label, value in candidate.integer_by_label.items()):
                    continue
                conditions = self._physical_integer_conditions(parent.fixed, tuple(candidate.integer_by_label))
                if any(sum(coefficient*candidate.integer_by_label[label]
                           for label, coefficient in relation["coefficients"]) != relation["rhs_integer"]
                       for relation in conditions):
                    continue
                child = NavigationBranch(self.metadata, use_foot=self.use_foot)
                child.restore(parent.snapshot())
                child.integer_lineage += ((float(packet["time_s"]),
                    tuple(sorted(candidate.integer_by_label.items()))),)
                anchor = None if conditioned_anchors is None else self._matching_anchor(child, conditioned_anchors)
                child.condition(candidate.integer_by_label, linearization_anchor=anchor)
                expanded.append(child)
        if not expanded:
            self.pending_proposals[labels] = dict(time_s=packet["time_s"], status="NO_COMPATIBLE_PARENT_CANDIDATE")
            self.proposal_complete = False
            self.proposal_retry_after[labels] = packet["time_s"]+.8
            self.decisions.append(dict(time_s=packet["time_s"], kind="NO_COMPATIBLE_PARENT_CANDIDATE",
                                       proposal=proposal.metadata))
            return
        if expanded:
            self.pending_proposals.pop(labels, None)
            if self.asynchronous_start:
                for old in list(self.pending_proposals):
                    if analyze_relation_transition(old, labels, label_mode="physical_sd_arcs").history_preserved_by_current:
                        self.pending_proposals.pop(old)
            self.proposal_complete = not self.support_incomplete and not self.pending_proposals
            expanded.sort(key=lambda b: b.window.error())
            for omitted in expanded[self.active_limit:]:
                self.dormant_candidates.append(dict(
                    integer_by_label=dict(omitted.fixed),
                    joint_cost=omitted.window.error(),
                    support_dependencies=sorted(self.arc_first_use) if self.use_foot else [],
                    proposal_time_s=packet["time_s"],
                    reason="JOINT_COMPUTATION_LIMIT_REGENERATABLE",
                ))
            if len(expanded) > self.active_limit:
                self.support_incomplete = True
                self.proposal_complete = False
            self.branches = expanded[:self.active_limit]
        self.decisions.append(dict(
            time_s=packet["time_s"], kind="JOINT_CONDITIONAL_DIRECTIONS",
            proposal=proposal.metadata, active_count=len(self.branches),
            joint_costs=[b.window.error() for b in self.branches],
            support_dependencies=sorted(self.arc_first_use) if self.use_foot else [],
            probability_calibrated=False,
        ))

    def _rebuild(self, affected: set[str], index: int, time_s: float, accepted: SupportTrack):
        first_use = min(self.arc_first_use[arc] for arc in affected)
        prior = [c for c in self.checkpoints if c.time_s < first_use]
        if not prior:
            # This alternative was forked while its original checkpoint existed
            # and has consumed every subsequent event. Its current separator
            # already excludes the withdrawn component; adopting it is exact
            # conditional-history transfer, not a pretend replay from lost data.
            shadow = accepted.navigator
            self._restore(Checkpoint(index, time_s,
                [b.snapshot() for b in shadow.branches], dict(shadow.proposal_times),
                shadow.proposal_complete, shadow.support_incomplete,
                copy.deepcopy(shadow.dormant_candidates), dict(shadow.arc_first_use),
                shadow.bootstrap_last_attempt, copy.deepcopy(shadow.bootstrap_diagnostic),
                shadow.predictive_rows_fingerprint, dict(shadow.proposal_retry_after), dict(shadow.pending_proposals)))
            self.checkpoints.clear()
            self.last_checkpoint_time = -math.inf
            self.decisions.append(dict(time_s=time_s,
                kind="ADOPT_CONTINUOUSLY_RECOMPUTED_CONDITIONAL_HISTORY",
                affected=sorted(affected), first_use_s=first_use,
                original_checkpoint_time_s=accepted.origin.time_s,
                previously_recomputed_events=accepted.processed_events,
                historical_online_rows_rewritten=0))
            return
        checkpoint = prior[-1]
        self._restore(checkpoint)
        self.checkpoints = [c for c in self.checkpoints if c.index <= checkpoint.index]
        self.last_checkpoint_time = checkpoint.time_s
        count = 0
        for event_index, event in self.events:
            if checkpoint.index < event_index <= index:
                packet = self._filter(event, replay=True)
                self.reference_rows[event_index], _ = self._advance(packet, event_index,
                    self.recovery_rows[event_index] if self.shared_support else None)
                self._save(event_index, packet["time_s"])
                count += 1
        self.replayed_events += count
        self.decisions.append(dict(
            time_s=time_s, kind="REBUILD_SHARED_STATE_AND_DIRECTION_SUPPORT",
            affected=sorted(affected), first_use_s=first_use,
            checkpoint_time_s=checkpoint.time_s, replayed_events=count,
            retained_carrier_labels=sorted(self.branches[0].ambiguity_keys),
            historical_online_rows_rewritten=0,
        ))

    def _direction_summary(self, branch: NavigationBranch, index: int):
        """Local physical direction for one joint source/integer hypothesis."""
        attitude_covariance = (branch.window.joint_covariance([X(index)]) if branch.window.gaussian_only
                               else branch.joint_covariance([X(index)]))[:3, :3]
        rotation = branch.pose.rotation()
        body_unit = np.asarray(self.metadata["baseline_body"], float)
        body_unit = body_unit / np.linalg.norm(body_unit)
        direction = rotation.rotate(body_unit)
        bx, by, bz = body_unit
        body_cross = np.array([[0., -bz, by], [bz, 0., -bx], [-by, bx, 0.]])
        jacobian = -rotation.matrix() @ body_cross
        covariance = jacobian @ attitude_covariance @ jacobian.T
        first = np.cross(direction, np.eye(3)[np.argmin(np.abs(direction))])
        first /= np.linalg.norm(first)
        basis = np.column_stack((first, np.cross(direction, first)))
        yaw_gradient = np.zeros(3)
        if branch.window.gaussian_only:
            chart_rotation = branch.window.linearization_values.atPose3(X(index)).rotation()
            chart_mean = branch.window.linearization_delta.at(X(index))[:3]
            jacobian = np.empty((3, 3))
        for axis in range(3):
            delta = np.eye(3)[axis]*1e-6
            if branch.window.gaussian_only:
                plus_rotation = chart_rotation.retract(chart_mean+delta)
                minus_rotation = chart_rotation.retract(chart_mean-delta)
                jacobian[:, axis] = (plus_rotation.rotate(body_unit)-minus_rotation.rotate(body_unit))/(2e-6)
            else:
                plus_rotation, minus_rotation = rotation.retract(delta), rotation.retract(-delta)
            plus, minus = plus_rotation.yaw(), minus_rotation.yaw()
            yaw_gradient[axis] = math.atan2(math.sin(plus-minus), math.cos(plus-minus))/(2e-6)
        covariance = jacobian @ attitude_covariance @ jacobian.T
        return dict(
            baseline_direction_n=direction.tolist(),
            baseline_tangent_basis_n=basis.tolist(),
            baseline_tangent_covariance_rad2=(basis.T @ covariance @ basis).tolist(),
            yaw_conditional_std_rad=math.sqrt(max(0., float(yaw_gradient @ attitude_covariance @ yaw_gradient))),
            direction_uncertainty_kind=("PUSHFORWARD_OF_COMMON_CHART_GAUSSIAN_CONDITIONAL" if branch.window.gaussian_only
                                        else "LOCAL_GAUSSIAN_CONDITIONAL_ON_INTEGER_AND_SUPPORT_MODEL"),
            direction_domain_coverage_certified=False,
        )

    def _run_future_only(self, events: list[dict]) -> dict:
        """U2 reuses the causal diagnosis and only applies its future factors.

        The controller and U3 use the same clean conditional histories. U2's
        execution state is never restored, so a second source decision cannot
        mistake unrepaired old translation for a new relative-geometry failure.
        The callback runs at each controller output, not after a future-data
        trajectory has been made available to the execution estimator.
        """
        started = time.monotonic()
        controller = JointNavigator(self.metadata, "U3")
        self.monitor_support = False
        policy_changes = 0
        last_policy = ()

        def consume(index, event, diagnostic, policy, integers):
            nonlocal policy_changes, last_policy
            t = float(event["time_s"])
            self.events.append((index, event))
            self.events = [(i, e) for i, e in self.events if e["time_s"] >= t-self.history_s]
            # Changing the supplied factors does not remove any existing factor
            # or separator information in this execution trajectory.
            self.support_models = copy.deepcopy(policy)
            packet = self._filter(event)
            _, nis = self._advance(packet, index)
            if not self._initialized():
                output = self._no_init_output(t)
                output.update(measurement_time_s=t,
                              available_time_s=float(event.get("available_time_s", t)))
                self.rows.append(output)
                return
            matches = [(j, b) for j, b in enumerate(self.branches)
                       if all(b.fixed.get(label) == value for label, value in integers.items())]
            if not matches:
                raise ValueError("future-only execution lost the controller's integer support")
            selected_index, best = min(matches, key=lambda item: item[1].predictive_score)
            signature = tuple(sorted((m["group_id"], m["mode"], tuple(m["arc_ids"])) for m in policy))
            changed = signature != last_policy
            policy_changes += int(changed)
            last_policy = signature
            output = copy.deepcopy(diagnostic)
            output.update(best.current_output())
            output.update(self._direction_summary(best, index))
            output.update(
                controller_candidate_local_directions=diagnostic["candidate_local_directions"],
                candidate_local_directions=[dict(support_model=diagnostic["selected_support_model"],
                    integer_lineage=best.integer_lineage, **self._direction_summary(best, index))],
                candidate_yaws_rad=[float(best.pose.rotation().yaw())],
                candidate_costs=[float(best.predictive_score)], candidate_supported=[True],
                selected_branch=0, execution_branch_index=selected_index,
                gnss_innovation_nis=nis, revocation=changed,
                replay_performed=False, conditional_history_recomputed=False,
                support_model_status="SAME_CAUSAL_CONTROLLER_FUTURE_FACTORS_ONLY",
                diagnostic_and_execution_histories_separate=True,
            )
            self.rows.append(output)

        result = controller.run(events, output_callback=consume)
        return dict(rows=self.rows, decisions=result["decisions"], summary=dict(
            mode="U2", causal_output_rows=len(self.rows), elapsed_s=time.monotonic()-started,
            replayed_events=0, proposal_attempts=self.proposal_attempts,
            dormant_candidates=len(self.dormant_candidates), active_support_complete=result["summary"]["active_support_complete"],
            active_integer_support_complete=self.proposal_complete,
            unresolved_raw_cohorts=len(self.pending_proposals),
            future_policy_changes=policy_changes,
            diagnostic_controller_summary=result["summary"],
            marginalized_variables=sum(b.window.marginalized_total for b in self.branches),
            same_causal_decisions_as_U3=True, truth_used_online=False,
            probability_calibrated=False, complete_research_goal=False,
        ))

    def run(self, events: list[dict], *, output_callback=None) -> dict:
        if self.mode == "U2" and self.monitor_support:
            return self._run_future_only(events)
        started = time.monotonic()
        for index, event in enumerate(events):
            t = float(event["time_s"])
            self.events.append((index, event))
            if self.shared_support:
                self.recovery_events.append((index, event))
            # Keep one event just before the 30s boundary for timing, and the
            # oldest retained checkpoint's entire future input stream.
            oldest = self.checkpoints[0].time_s if self.checkpoints else max(0.0, t-self.history_s)
            self.events = [(i, e) for i, e in self.events if e["time_s"] >= oldest]
            retained_indices = {i for i, _ in self.events}
            self.reference_rows = {i: rows for i, rows in self.reference_rows.items() if i in retained_indices}
            packet = self._filter(event)
            if packet.get("carrier") is not None:
                self.last_phase_relation_count = len(packet["carrier"].ambiguity_labels)
            elif self.asynchronous_start and packet.get("carrier_source") is not None:
                self.last_phase_relation_count = 0
            self.reference_rows[index], nis = self._advance(packet, index)
            if self.shared_support:
                self.recovery_rows[index] = self.reference_rows[index]
            if self.asynchronous_start and not self._initialized():
                output = self._no_init_output(t)
                output.update(measurement_time_s=t,
                              available_time_s=float(event.get("available_time_s", t)))
                self.rows.append(output)
                if output_callback is not None:
                    output_callback(index, event, output, self.support_models, {})
                continue
            affected = set()
            support_result = self._update_support_tracks(packet, index) if self.monitor_support else None
            accepted = support_result[4] if support_result is not None else None
            if accepted is not None:
                affected = set(accepted.arc_ids)
                self.support_models = copy.deepcopy(accepted.navigator.support_models)
                if not self.rebuild_history:
                    for model in self.support_models:
                        if set(model["arc_ids"]) == set(accepted.arc_ids) and model["mode"] == accepted.model:
                            model["effective_from"] = t
                self.stop_from.update({arc: t for arc in affected})
                self.decisions.append(dict(time_s=t, kind="PREDICTIVE_SUPPORT_MODEL_SELECTED",
                    affected=sorted(affected), support_model=accepted.model,
                    first_use_s=accepted.first_use, discovered_at_s=t,
                    evidence_conditioned_on_integer_lineages=True,
                    relative_geometry_retained=accepted.model in ("common_translation_release", "finite_common_motion")))
                if self.rebuild_history:
                    self.revoked_arcs.update(affected)
                    self._rebuild(affected, index, t, accepted)
                self.model_generation += 1
                self.support_groups.clear()
                self.support_tracks.clear()
                self.support_group_order.clear()
                self.policy_parent_cursors.clear()
                self.policy_queue_tickets.clear()
                self.last_supported_tracks.clear()
                self.last_support_signature = None
                self.rescan_support_history = True
                support_result = None
            base_penalty = self.model_edit_cost*len(self.support_models)
            output_models = [("fixed", branch, base_penalty, None) for branch in self.branches]
            output_costs = np.array([b.predictive_score+base_penalty if self.mode in ("U2", "U3") else b.window.error()
                                    for b in self.branches])
            model_status = "BACKGROUND_CONTACT_MODEL"
            if support_result is not None and self.rebuild_history:
                alternatives, all_costs, in_support, winner, _ = support_result
                output_models = [alternative for j, alternative in enumerate(alternatives) if in_support[j]]
                output_costs = all_costs[in_support]
                # Keep nominal navigation while it remains supported. Once it
                # is excluded, publish an explicit conditional clean-history
                # branch; other source explanations stay in the direction set.
                model_status = "CONDITIONAL_CONTACT_MODEL_SUPPORT"
            costs = output_costs
            order = np.argsort(costs)
            selected_index = int(order[0])
            nominal = [j for j, item in enumerate(output_models) if item[0] == "fixed"]
            if nominal and support_result is not None and self.rebuild_history:
                selected_index = min(nominal, key=lambda j: costs[j])
            best = output_models[selected_index][1]
            if self.shared_support:
                chosen_track = output_models[selected_index][3]
                reference = (chosen_track.identity if chosen_track is not None
                             and chosen_track.nonlinear_expanded else None)
                if reference != self.linearization_reference_identity:
                    self.decisions.append(dict(time_s=t, kind="COMMON_LINEARIZATION_REFERENCE_CHANGED",
                        previous_reference=self.linearization_reference_identity or "fixed",
                        selected_reference=reference or "fixed", effective_after_time_s=t,
                        source_models_discarded=0, historical_scores_rewritten=0,
                        historical_online_rows_rewritten=0, new_observation_added=False))
                    self.linearization_reference_identity = reference
                    self.linearization_reference_switches += 1
            output = best.current_output()
            local_directions = [self._direction_summary(item[1], index) for item in output_models]
            output.update(local_directions[selected_index])
            output["candidate_local_directions"] = [
                dict(support_model=item[0], integer_lineage=item[1].integer_lineage,
                     conditional_state=item[1].current_output(), factor_counts=dict(item[1].last_factor_counts),
                     **self._policy_descriptor(item[3]),
                     **direction)
                for item, direction in zip(output_models, local_directions)]
            candidate_rpy = [item[1].current_output()["rpy_rad"] for item in output_models]
            predictive_costs = self.mode in ("U2", "U3")
            delta = (1. if predictive_costs else 2.) * (costs - costs.min())
            supported = delta <= (self.model_support_delta if predictive_costs else self.profile_support_delta)
            comparison_complete = self.proposal_complete and all(
                track.navigator.proposal_complete and self._same_predictive_rows(track.navigator)
            for track in self.support_tracks.values())
            evaluated_frontier_complete = comparison_complete
            policy_search = self._policy_search_readout()
            if self.shared_support:
                comparison_complete = comparison_complete and policy_search["evaluated_policy_coverage_complete"]
            nonlinear_comparison_complete = comparison_complete and (
                not self.shared_support or all(track.nonlinear_expanded for track in self.support_tracks.values()))
            status = "CONDITIONAL_SUPPORT" if comparison_complete else "UNRESOLVED_ENUMERATION_OR_BRANCH_BUDGET"
            if self.shared_support and not nonlinear_comparison_complete:
                status = "COMMON_LINEARIZATION_ONLY_NONLINEAR_EXPLANATIONS_UNRESOLVED_"+status
            if sum(supported) > 1:
                status = "MULTIPLE_CONDITIONAL_DIRECTIONS_" + status
            if self.asynchronous_start:
                phase_context = ("RAW_PHASE_RELATIONS" if self.last_phase_relation_count else
                                 "NO_CURRENT_PHASE_RELATIONS")
            else:
                phase_context = ("FULL_PHASE" if self.last_phase_relation_count >= 5 else
                                 "PARTIAL_PHASE" if self.last_phase_relation_count else
                                 "PHASE_ABSENT_CODE_AND_MOTION")
            status = phase_context + "_" + status
            output.update(
                time_s=t, measurement_time_s=t,
                available_time_s=float(event.get("available_time_s", t)),
                initialization_status=(self.bootstrap_diagnostic["status"]
                    if self.asynchronous_start else "SYNTHETIC_LEGACY_START"),
                candidate_yaws_rad=[float(r[2]) for r in candidate_rpy],
                candidate_costs=costs.tolist(), candidate_supported=supported.tolist(),
                support_ids=[f["arc_id"] for f in packet.get("feet", [])],
                direction_status=status, gnss_innovation_nis=nis,
                predictive_evidence_scope=self.support_prediction,
                background_predictive_blocks=copy.deepcopy(self.last_prediction_blocks),
                candidate_support_complete=nonlinear_comparison_complete,
                conditional_model_evidence_frontier_complete=comparison_complete,
                evaluated_policy_evidence_frontier_complete=evaluated_frontier_complete,
                nonlinear_contact_support_complete=nonlinear_comparison_complete,
                common_linearization_reference_used=self.linearization_reference_used,
                next_common_linearization_reference=(self.linearization_reference_identity or "fixed"
                    if self.shared_support else None),
                support_gaussian_history_policy=("FROZEN_HISTORY_FUTURE_SEPARATOR"
                    if self.gaussian_future_separator else "FIXED_LAG_SHARED_RELINEARIZATION"),
                contact_inference_scope=("CONDITIONAL_COMMON_LINEARIZATION_WITH_ON_DEMAND_NONLINEAR_REPLAY"
                    if self.shared_support else "FULL_NONLINEAR_CONDITIONAL_MODELS"),
                unexpanded_nonlinear_explanations=(sum(not track.nonlinear_expanded for track in self.support_tracks.values())
                    if self.shared_support else 0),
                unique_within_evaluated_nonlinear_source_family=bool(nonlinear_comparison_complete and sum(supported) == 1),
                unexpanded_source_identities=([identity for identity, track in self.support_tracks.items()
                    if not track.nonlinear_expanded] if self.shared_support else []),
                consumed_phase_relations=self.last_phase_relation_count,
                selected_branch=selected_index, branch_conditional_navigation=True,
                selected_support_model=output_models[selected_index][0],
                selected_support_policy=self._policy_descriptor(output_models[selected_index][3]),
                policy_search=policy_search, policy_selection_scope="BEST_AMONG_EVALUATED_POLICIES",
                support_model_status=model_status,
                supported_contact_models=sorted({item[0] for item in output_models}),
                contact_model_family=("OBSERVED_GROUP_REPLACEMENT_POLICY_PATHS" if self.shared_support else
                                      "ONE_ADDITIONAL_OBSERVED_COSUPPORT_GROUP_PER_GENERATION"),
                contact_model_probability_calibrated=False,
                unresolved_predictive_frontier_models=sum(not self._same_predictive_rows(track.navigator)
                    for track in self.support_tracks.values()),
                carrier_relation_state=copy.deepcopy(best.last_carrier_relations),
                carrier_event_status=("OBSERVED_RAW_BLOCK" if packet.get("carrier") is not None else
                    packet["carrier_source"]["status"] if packet.get("carrier_source") is not None else
                    "NO_NEW_CARRIER_PACKET"),
                candidate_cost_kind="CONDITIONAL_PREQUENTIAL_NEGATIVE_TWICE_LOG_DENSITY" if predictive_costs else "JOINT_GRAPH_HALF_SQUARED_ERROR",
                conditional_history_recomputed=output_models[selected_index][3] is not None,
                revocation=bool(affected and self.mode in ("U2", "U3")),
                revoked_support_ids=sorted(self.stop_from),
                replay_performed=bool(affected and self.rebuild_history),
            )
            self.rows.append(output)
            self._save(index, t)
            if output_callback is not None:
                chosen_track = output_models[selected_index][3]
                chosen_policy = self.support_models if chosen_track is None else chosen_track.navigator.support_models
                output_callback(index, event, output, chosen_policy, dict(best.fixed))
            if index % 100 == 0:
                print(f"{self.mode} t={t:.1f}/{events[-1]['time_s']:.1f}s branches={len(self.branches)} models={len(self.support_tracks)} replayed={self.replayed_events}", flush=True)
        return dict(rows=self.rows, decisions=self.decisions, summary=dict(
            mode=self.mode, causal_output_rows=len(self.rows), elapsed_s=time.monotonic()-started,
            initialization=copy.deepcopy(self.bootstrap_diagnostic) if self.asynchronous_start else None,
            no_init_rows=sum(row["direction_status"] == "NO_INIT" for row in self.rows),
            replayed_events=self.replayed_events, proposal_attempts=self.proposal_attempts,
            dormant_candidates=len(self.dormant_candidates), active_support_complete=(self.proposal_complete and
                (not self.shared_support or (self._policy_search_readout()["evaluated_policy_coverage_complete"]
                    and all(track.nonlinear_expanded and self._same_predictive_rows(track.navigator)
                    for track in self.support_tracks.values())))),
            active_integer_support_complete=self.proposal_complete,
            unresolved_raw_cohorts=len(self.pending_proposals),
            revoked_arcs=sorted(self.revoked_arcs),
            support_model_replayed_events=self.model_replay_events,
            live_support_models=len(self.support_tracks),
            policy_search=self._policy_search_readout(),
            expired_unresolved_groups=self.expired_unresolved_groups,
            model_edit_cost=self.model_edit_cost, model_support_delta=self.model_support_delta,
            predictive_evidence_scope=self.support_prediction,
            support_motion_model=copy.deepcopy(self.metadata.get("support_motion_model")),
            marginalized_variables=sum(b.window.marginalized_total for b in self.branches),
            truth_used_online=False, probability_calibrated=False,
            complete_research_goal=False,
            support_inference=self.metadata.get("support_inference", "full_nonlinear"),
            nonlinear_support_expansions=self.nonlinear_support_expansions,
            gaussian_support_step_events=self.gaussian_support_step_events,
            nonlinear_support_step_events=self.nonlinear_support_step_events,
            recovery_archive_events=len(self.recovery_events),
            anchor_history_epochs=len(self.anchor_history),
            support_gaussian_history_policy=("FROZEN_HISTORY_FUTURE_SEPARATOR"
                if self.gaussian_future_separator else "FIXED_LAG_SHARED_RELINEARIZATION"),
            gaussian_support_compressed_key_count=sum(track.navigator.gaussian_compressed_key_count
                for track in self.support_tracks.values()),
            maximum_gaussian_separator_dimension=max((track.navigator.maximum_gaussian_separator_dimension
                for track in self.support_tracks.values()), default=0),
            linearization_reference_switches=self.linearization_reference_switches,
            last_common_linearization_reference_used=self.linearization_reference_used,
            next_common_linearization_reference=self.linearization_reference_identity or "fixed",
            recovery_storage_bounded=False if self.shared_support else None,
        ))
