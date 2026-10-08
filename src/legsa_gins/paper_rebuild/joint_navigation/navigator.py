"""Causal joint navigation, conditional directions, and support-history replay.

One entry consumes the same physical event stream for U0--U3. It never receives
simulation truth. Profile costs express conditional support, not probabilities.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import math
import time

import numpy as np
from gtsam.symbol_shorthand import X

from ..carrier_phase.temporal import EpochBlock
from .branch import NavigationBranch
from .candidate import propose_candidates


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


@dataclass
class SupportTrack:
    identity: str
    group_id: str
    arc_ids: tuple[str, ...]
    model: str
    first_use: float
    origin: Checkpoint
    navigator: object
    processed_events: int = 0


def code_only(block: EpochBlock) -> EpochBlock:
    """The full-only comparator keeps code on the identical interrupted stream."""
    rows = np.flatnonzero(np.all(block.A == 0, axis=1))
    return EpochBlock(block.time_s, block.y[rows], np.zeros((len(rows), 0)),
                      block.B[rows], block.Q[np.ix_(rows, rows)], (), dict(block.metadata))


class JointNavigator:
    def __init__(self, metadata: dict, mode: str = "U3", *,
                 monitor_support: bool = True, support_models: list[dict] | None = None):
        self.metadata = copy.deepcopy(metadata)
        self.mode = mode
        self.use_foot = mode != "U0"
        self.use_partial = mode in ("U2", "U3")
        self.rebuild_history = mode == "U3"
        self.branches = [NavigationBranch(self.metadata, use_foot=self.use_foot)]
        self.history_s = 30.0
        self.active_limit = 4
        self.profile_support_delta = 25.0
        self.proposal_times = {}
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
        self.support_models = copy.deepcopy(support_models or [])
        # Fixed engineering decision costs, not calibrated model probabilities.
        # Both releases have the same cost; geometry is not presumed valid merely
        # because common translation failed. Unresolved models remain separate.
        self.model_edit_cost = 2. * math.log(100.)
        self.model_support_delta = 2. * math.log(20.)
        self.support_groups = {}
        self.support_tracks = {}
        self.reference_rows = {}
        self.last_support_signature = None
        self.last_supported_tracks = set()
        self.model_generation = 0
        self.model_replay_events = 0
        self.expired_unresolved_groups = 0
        self.rescan_support_history = False
        self.checkpoints.append(Checkpoint(
            -1, -1e-9, [b.snapshot() for b in self.branches],
            {}, False, False, [], {},
        ))

    def _filter(self, event: dict, replay: bool = False) -> dict:
        packet = dict(event)
        block = packet.get("carrier")
        # The source declares measurement counts, not truth failure labels.
        full_count = int(self.metadata.get("full_phase_relations", 5))
        if block is not None and not self.use_partial and len(block.ambiguity_labels) < full_count:
            packet["carrier"] = code_only(block)
        # U2 stops future use at discovery, U3 rebuilds the past with the same
        # physically restricted common-translation model.
        return packet

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
        Scores are conditional external predictive evidence, not the normalized
        joint likelihood of all foot measurements and not model probabilities.
        """
        if self.branches[0].index is None or all(
                packet.get(name) is None for name in ("carrier", "gnss_position", "gnss_velocity")):
            return (), 0.
        predictions = [branch.predict_external(packet) for branch in self.branches]
        common = set(predictions[0]["row_ids"])
        for prediction in predictions[1:]:
            common.intersection_update(prediction["row_ids"])
        rows = tuple(row for row in predictions[0]["row_ids"] if row in common)
        if expected_rows is not None:
            if not set(expected_rows).issubset(common):
                raise ValueError("support models do not share the reference prediction rows")
            rows = tuple(expected_rows)
        position_nis = 0.
        for branch, prediction in zip(self.branches, predictions):
            if index <= branch.predictive_frontier:
                raise ValueError("an external event was scored twice in one integer lineage")
            branch.predictive_frontier = index
            if not rows:
                continue
            positions = [prediction["row_ids"].index(row) for row in rows]
            residual = prediction["innovation"][positions]
            covariance = prediction["covariance"][np.ix_(positions, positions)]
            chol = np.linalg.cholesky(covariance)
            whitened = np.linalg.solve(chol, residual)
            branch.predictive_score += float(
                whitened @ whitened + 2.*np.log(np.diag(chol)).sum()
                + len(rows)*math.log(2.*math.pi))
            branch.predictive_row_count += len(rows)
            if packet.get("gnss_position") is not None:
                p = [j for j, row in enumerate(rows) if row.startswith("gnss_position:")]
                r = residual[p]
                position_nis = float(r @ np.linalg.solve(covariance[np.ix_(p, p)], r))
        return rows, position_nis

    def _advance(self, packet: dict, index: int, expected_rows=None):
        for foot in packet.get("feet", []):
            self.arc_first_use.setdefault(foot["arc_id"], packet["time_s"])
        rows, nis = self._score_prediction(packet, index, expected_rows)
        for branch in self.branches:
            branch.step(packet, index, support_models=self._models_at(packet["time_s"]))
        self._propose(index, packet)
        return rows, nis

    def _restore(self, checkpoint: Checkpoint):
        self.branches = []
        for snapshot in checkpoint.branches:
            branch = NavigationBranch(self.metadata, use_foot=self.use_foot)
            branch.restore(snapshot)
            self.branches.append(branch)
        self.proposal_times = dict(checkpoint.proposal_times)
        self.proposal_complete = checkpoint.proposal_complete
        self.support_incomplete = checkpoint.support_incomplete
        self.dormant_candidates = copy.deepcopy(checkpoint.candidates)
        self.arc_first_use = dict(checkpoint.arc_first_use)

    def _candidate_policy(self, arc_ids, model, group_id):
        """A competing source model replaces overlapping components, never adds them."""
        affected = set(arc_ids)
        result = []
        for old in self.support_models:
            remainder = set(old["arc_ids"]) - affected
            if remainder:
                result.append({**old, "arc_ids": tuple(sorted(remainder))})
        result.append(dict(group_id=group_id, arc_ids=tuple(arc_ids), mode=model,
                           effective_from=-math.inf))
        return result

    def _register_support_group(self, packet: dict):
        t = float(packet["time_s"])
        observed = packet.get("active_support_arcs")
        if observed is None:
            observed = [foot["arc_id"] for foot in packet.get("feet", [])]
        ids = tuple(sorted(observed))
        if len(ids) >= 2 and ids not in self.support_groups:
            first = min(self.arc_first_use[arc] for arc in ids)
            prior = [c for c in self.checkpoints if c.time_s < first]
            group_id = "support:" + "|".join(ids)
            self.support_groups[ids] = dict(first_use=first, group_id=group_id,
                                             status="PENDING", last_observed=t)
            if prior:
                origin = prior[-1]
                for model in ("common_translation_release", "relative_release"):
                    # Do not propose reinstating a component already withdrawn.
                    severity = {arc: old["mode"] for old in self.support_models for arc in old["arc_ids"]}
                    if model == "common_translation_release" and any(
                            severity.get(arc) == "relative_release" for arc in ids):
                        continue
                    if all(severity.get(arc) == model for arc in ids):
                        continue
                    shadow = JointNavigator(self.metadata, self.mode, monitor_support=False,
                        support_models=self._candidate_policy(ids, model, group_id))
                    shadow._restore(origin)
                    identity = f"g{self.model_generation}:{group_id}:{model}"
                    self.support_tracks[identity] = SupportTrack(
                        identity, group_id, ids, model, first, origin, shadow)
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
        expired = []
        for identity, track in self.support_tracks.items():
            if (t-track.first_use > self.history_s and
                    not set(track.arc_ids).intersection(ids) and
                    identity not in self.last_supported_tracks):
                expired.append(identity)
                if self.support_groups[track.arc_ids]["status"] != "UNRESOLVED_HISTORY_EXPIRED":
                    self.expired_unresolved_groups += 1
                self.support_groups[track.arc_ids]["status"] = "UNRESOLVED_HISTORY_EXPIRED"
                continue
            shadow = track.navigator
            shadow.events = self.events
            after = shadow.branches[0].index
            after = -1 if after is None else after
            for event_index, event in self.events:
                if after < event_index <= index:
                    try:
                        shadow._advance(shadow._filter(event), event_index,
                                        self.reference_rows[event_index])
                    except RuntimeError:
                        print(f"FAILED_SUPPORT_MODEL identity={identity} time={event['time_s']} "
                              f"index={event_index} origin={track.origin.time_s}", flush=True)
                        raise
                    track.processed_events += 1
                    self.model_replay_events += 1
        for identity in expired:
            del self.support_tracks[identity]
        return self._contact_support(packet)

    def _contact_support(self, packet: dict):
        alternatives = [("fixed", branch, 0., None) for branch in self.branches]
        for identity, track in self.support_tracks.items():
            alternatives.extend((identity, branch, self.model_edit_cost, track)
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
                fixed_contact_in_support="fixed" in identities,
                working_edit_cost=self.model_edit_cost,
                working_support_delta=self.model_support_delta,
                fixed_minus_best_score=float(min(b.predictive_score for b in self.branches)-costs[winner]),
                compared_groups=len(self.support_groups), evaluated_models=len(self.support_tracks),
                integer_lineage_scores=True, probability_calibrated=False,
            ))
            self.last_support_signature = signature
        selected = alternatives[winner][3]
        complete = self.proposal_complete and all(
            track.navigator.proposal_complete for track in self.support_tracks.values())
        # Only a unique source explanation commits a model change. Otherwise
        # U3 retains the separate clean conditional states and their directions.
        accepted = selected if (len(identities) == 1 and "fixed" not in identities and complete) else None
        return alternatives, costs, supported, winner, accepted

    def _save(self, index: int, time_s: float):
        if time_s - self.last_checkpoint_time < 0.95:
            return
        self.checkpoints.append(Checkpoint(
            index, time_s, [b.snapshot() for b in self.branches],
            dict(self.proposal_times), self.proposal_complete,
            self.support_incomplete,
            copy.deepcopy(self.dormant_candidates), dict(self.arc_first_use),
        ))
        self.checkpoints = [c for c in self.checkpoints if c.time_s >= time_s - self.history_s]
        self.last_checkpoint_time = time_s

    def _propose(self, index: int, packet: dict):
        block = packet.get("carrier")
        if block is None or not block.ambiguity_labels:
            return
        labels = tuple(block.ambiguity_labels)
        if all(all(label in branch.fixed for label in labels) for branch in self.branches):
            return
        # Reuse a physical-label cohort's proposal; no overlapping-window
        # likelihood multiplication and no gyro/RP-based preselection.
        if labels in self.proposal_times:
            return
        recent = []
        for _, raw in self.events:
            if raw["time_s"] < packet["time_s"] - 0.8 or raw["time_s"] > packet["time_s"]:
                continue
            candidate_block = self._filter(raw).get("carrier")
            if candidate_block is not None and tuple(candidate_block.ambiguity_labels) == labels:
                recent.append(candidate_block)
        if len(recent) < 4:
            return
        common_fixed = {label: value for label, value in self.branches[0].fixed.items()
                        if all(branch.fixed.get(label) == value for branch in self.branches)}
        proposal = propose_candidates(recent, np.asarray(self.metadata["baseline_body"]), self.active_limit,
                                      conditioned_integer_by_label=common_fixed)
        self.proposal_attempts += 1
        self.proposal_times[labels] = packet["time_s"]
        self.support_incomplete |= not proposal.metadata["active_support_complete"]
        self.proposal_complete = not self.support_incomplete
        for candidate in proposal.dormant:
            self.dormant_candidates.append(dict(
                integer_by_label=candidate.integer_by_label, raw_cost=candidate.raw_cost,
                reason="COMPUTATION_BUDGET_NOT_SCIENTIFIC_EXCLUSION",
                proposal_time_s=packet["time_s"],
            ))
        if not proposal.active:
            self.proposal_complete = False
            self.support_incomplete = True
            self.decisions.append(dict(time_s=packet["time_s"], kind="RAW_SUPPORT_UNRESOLVED",
                                       proposal=proposal.metadata))
            return

        expanded = []
        for parent in self.branches:
            for candidate in proposal.active:
                if any(label in parent.fixed and parent.fixed[label] != value
                       for label, value in candidate.integer_by_label.items()):
                    continue
                child = NavigationBranch(self.metadata, use_foot=self.use_foot)
                child.restore(parent.snapshot())
                child.integer_lineage += ((float(packet["time_s"]),
                    tuple(sorted(candidate.integer_by_label.items()))),)
                child.condition(candidate.integer_by_label)
                expanded.append(child)
        if expanded:
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
                copy.deepcopy(shadow.dormant_candidates), dict(shadow.arc_first_use)))
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
                self.reference_rows[event_index], _ = self._advance(packet, event_index)
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
        attitude_covariance = branch.joint_covariance([X(index)])[:3, :3]
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
        for axis in range(3):
            delta = np.eye(3)[axis]*1e-6
            plus, minus = rotation.retract(delta).yaw(), rotation.retract(-delta).yaw()
            yaw_gradient[axis] = math.atan2(math.sin(plus-minus), math.cos(plus-minus))/(2e-6)
        return dict(
            baseline_direction_n=direction.tolist(),
            baseline_tangent_basis_n=basis.tolist(),
            baseline_tangent_covariance_rad2=(basis.T @ covariance @ basis).tolist(),
            yaw_conditional_std_rad=math.sqrt(max(0., float(yaw_gradient @ attitude_covariance @ yaw_gradient))),
            direction_uncertainty_kind="LOCAL_GAUSSIAN_CONDITIONAL_ON_INTEGER_AND_SUPPORT_MODEL",
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
            dormant_candidates=len(self.dormant_candidates), active_support_complete=self.proposal_complete,
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
            # Keep one event just before the 30s boundary for timing, and the
            # oldest retained checkpoint's entire future input stream.
            oldest = self.checkpoints[0].time_s if self.checkpoints else max(0.0, t-self.history_s)
            self.events = [(i, e) for i, e in self.events if e["time_s"] >= oldest]
            retained_indices = {i for i, _ in self.events}
            self.reference_rows = {i: rows for i, rows in self.reference_rows.items() if i in retained_indices}
            packet = self._filter(event)
            if packet.get("carrier") is not None:
                self.last_phase_relation_count = len(packet["carrier"].ambiguity_labels)
            self.reference_rows[index], nis = self._advance(packet, index)
            affected = set()
            support_result = self._update_support_tracks(packet, index) if self.monitor_support else None
            accepted = support_result[4] if support_result is not None else None
            if accepted is not None:
                affected = set(accepted.arc_ids)
                self.support_models = copy.deepcopy(accepted.navigator.support_models)
                if not self.rebuild_history:
                    for model in self.support_models:
                        if model["group_id"] == accepted.group_id:
                            model["effective_from"] = t
                self.stop_from.update({arc: t for arc in affected})
                self.decisions.append(dict(time_s=t, kind="PREDICTIVE_SUPPORT_MODEL_SELECTED",
                    affected=sorted(affected), support_model=accepted.model,
                    first_use_s=accepted.first_use, discovered_at_s=t,
                    evidence_conditioned_on_integer_lineages=True,
                    relative_geometry_retained=accepted.model == "common_translation_release"))
                if self.rebuild_history:
                    self.revoked_arcs.update(affected)
                    self._rebuild(affected, index, t, accepted)
                self.model_generation += 1
                self.support_groups.clear()
                self.support_tracks.clear()
                self.last_supported_tracks.clear()
                self.last_support_signature = None
                self.rescan_support_history = True
                support_result = None
            output_models = [("fixed", branch, 0., None) for branch in self.branches]
            output_costs = np.array([b.predictive_score if self.mode in ("U2", "U3") else b.window.error()
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
            output = best.current_output()
            local_directions = [self._direction_summary(item[1], index) for item in output_models]
            output.update(local_directions[selected_index])
            output["candidate_local_directions"] = [
                dict(support_model=item[0], integer_lineage=item[1].integer_lineage, **direction)
                for item, direction in zip(output_models, local_directions)]
            candidate_rpy = [item[1].current_output()["rpy_rad"] for item in output_models]
            predictive_costs = self.mode in ("U2", "U3")
            delta = (1. if predictive_costs else 2.) * (costs - costs.min())
            supported = delta <= (self.model_support_delta if predictive_costs else self.profile_support_delta)
            comparison_complete = self.proposal_complete and all(
                track.navigator.proposal_complete for track in self.support_tracks.values())
            status = "CONDITIONAL_SUPPORT" if comparison_complete else "UNRESOLVED_ENUMERATION_OR_BRANCH_BUDGET"
            if sum(supported) > 1:
                status = "MULTIPLE_CONDITIONAL_DIRECTIONS_" + status
            phase_context = ("FULL_PHASE" if self.last_phase_relation_count >= 5 else
                             "PARTIAL_PHASE" if self.last_phase_relation_count else
                             "PHASE_ABSENT_CODE_AND_MOTION")
            status = phase_context + "_" + status
            output.update(
                time_s=t, candidate_yaws_rad=[float(r[2]) for r in candidate_rpy],
                candidate_costs=costs.tolist(), candidate_supported=supported.tolist(),
                support_ids=[f["arc_id"] for f in packet.get("feet", [])],
                direction_status=status, gnss_innovation_nis=nis,
                candidate_support_complete=comparison_complete,
                consumed_phase_relations=self.last_phase_relation_count,
                selected_branch=selected_index, branch_conditional_navigation=True,
                selected_support_model=output_models[selected_index][0],
                support_model_status=model_status,
                supported_contact_models=sorted({item[0] for item in output_models}),
                contact_model_family="ONE_ADDITIONAL_OBSERVED_COSUPPORT_GROUP_PER_GENERATION",
                contact_model_probability_calibrated=False,
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
            replayed_events=self.replayed_events, proposal_attempts=self.proposal_attempts,
            dormant_candidates=len(self.dormant_candidates), active_support_complete=self.proposal_complete,
            revoked_arcs=sorted(self.revoked_arcs),
            support_model_replayed_events=self.model_replay_events,
            live_support_models=len(self.support_tracks),
            expired_unresolved_groups=self.expired_unresolved_groups,
            model_edit_cost=self.model_edit_cost, model_support_delta=self.model_support_delta,
            marginalized_variables=sum(b.window.marginalized_total for b in self.branches),
            truth_used_online=False, probability_calibrated=False,
            complete_research_goal=False,
        ))
