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


def code_only(block: EpochBlock) -> EpochBlock:
    """The full-only comparator keeps code on the identical interrupted stream."""
    rows = np.flatnonzero(np.all(block.A == 0, axis=1))
    return EpochBlock(block.time_s, block.y[rows], np.zeros((len(rows), 0)),
                      block.B[rows], block.Q[np.ix_(rows, rows)], (), dict(block.metadata))


class JointNavigator:
    def __init__(self, metadata: dict, mode: str = "U3"):
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

    def _gnss_conflict(self, packet: dict):
        """Working source-model diagnosis from current observations, never truth.

        Long simultaneous support and preserved pair geometry permit testing the
        common-translation hypothesis. GNSS supplies a new absolute-motion check.
        This is a declared synthetic working detector, not integrity certification.
        """
        feet = packet.get("feet", [])
        if not self.use_foot or packet.get("gnss_position") is None or len(feet) != 4:
            return 0.0, set()
        ids = {f["arc_id"] for f in feet}
        if ids & set(self.stop_from) or len(self.rows) < 2:
            return 0.0, set()
        if min(packet["time_s"] - self.arc_first_use.get(arc, packet["time_s"]) for arc in ids) <= 5.0:
            return 0.0, set()
        prior_branch = min(self.branches, key=lambda branch: branch.window.error())
        innovation, prediction_covariance = prior_branch.predict_gnss_position(packet)
        nis = float(innovation @ np.linalg.solve(prediction_covariance, innovation))
        early = next((e for _, e in self.events
                      if {f["arc_id"] for f in e.get("feet", [])} == ids), None)
        if early is None:
            return nis, set()
        current_points = np.array([f["point_body"] for f in sorted(feet, key=lambda f: f["foot_id"])])
        early_points = np.array([f["point_body"] for f in sorted(early["feet"], key=lambda f: f["foot_id"])])
        # Pair distances are rotation invariant; they cannot certify no common
        # slide, but they can support preserving relative geometry after release.
        ii, jj = np.triu_indices(4, 1)
        pair_change = np.linalg.norm(current_points[ii]-current_points[jj], axis=1) - np.linalg.norm(early_points[ii]-early_points[jj], axis=1)
        relative_compatible = float(np.sqrt(np.mean(pair_change**2))) < 4 * float(self.metadata.get("foot_sigma", 0.01))
        return nis, ids if nis > 12.84 and relative_compatible else set()

    def _rebuild(self, affected: set[str], index: int, time_s: float):
        first_use = min(self.arc_first_use[arc] for arc in affected)
        prior = [c for c in self.checkpoints if c.time_s < first_use]
        if not prior:
            self.decisions.append(dict(time_s=time_s, kind="OUTSIDE_RECOVERABLE_HISTORY",
                                       affected=sorted(affected), first_use_s=first_use))
            return
        checkpoint = prior[-1]
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
        self.checkpoints = [c for c in self.checkpoints if c.index <= checkpoint.index]
        self.last_checkpoint_time = checkpoint.time_s
        count = 0
        for event_index, event in self.events:
            if checkpoint.index < event_index <= index:
                packet = self._filter(event, replay=True)
                for foot in packet.get("feet", []):
                    self.arc_first_use.setdefault(foot["arc_id"], packet["time_s"])
                for branch in self.branches:
                    branch.step(packet, event_index, self._released(packet["time_s"]))
                self._propose(event_index, packet)
                count += 1
        self.replayed_events += count
        self.decisions.append(dict(
            time_s=time_s, kind="REBUILD_SHARED_STATE_AND_DIRECTION_SUPPORT",
            affected=sorted(affected), first_use_s=first_use,
            checkpoint_time_s=checkpoint.time_s, replayed_events=count,
            retained_carrier_labels=sorted(self.branches[0].ambiguity_keys),
            historical_online_rows_rewritten=0,
        ))

    def run(self, events: list[dict]) -> dict:
        started = time.monotonic()
        for index, event in enumerate(events):
            t = float(event["time_s"])
            self.events.append((index, event))
            # Keep one event just before the 30s boundary for timing, and the
            # oldest retained checkpoint's entire future input stream.
            oldest = self.checkpoints[0].time_s if self.checkpoints else max(0.0, t-self.history_s)
            self.events = [(i, e) for i, e in self.events if e["time_s"] >= oldest]
            packet = self._filter(event)
            if packet.get("carrier") is not None:
                self.last_phase_relation_count = len(packet["carrier"].ambiguity_labels)
            for foot in packet.get("feet", []):
                self.arc_first_use.setdefault(foot["arc_id"], t)
            nis, affected = self._gnss_conflict(packet)
            for branch in self.branches:
                branch.step(packet, index, self._released(t))
            self._propose(index, packet)
            if affected and self.mode in ("U2", "U3"):
                self.stop_from.update({arc: t for arc in affected})
                self.decisions.append(dict(time_s=t, kind="COMMON_TRANSLATION_MODEL_RELEASE",
                                           affected=sorted(affected), gnss_innovation_nis=nis,
                                           relative_geometry_retained=True))
                if self.rebuild_history:
                    self.revoked_arcs.update(affected)
                    self._rebuild(affected, index, t)
            costs = np.array([b.window.error() for b in self.branches])
            order = np.argsort(costs)
            best = self.branches[int(order[0])]
            output = best.current_output()
            attitude_covariance = best.joint_covariance([X(index)])[:3, :3]
            rotation = best.pose.rotation()
            # Read physical short-baseline direction from the same joint state.
            # This local covariance is conditional on the selected integer and
            # support model; it is not the coverage of the complete direction set
            # and must never be fused back as another heading measurement.
            body_unit = np.asarray(self.metadata["baseline_body"], float)
            body_unit = body_unit / np.linalg.norm(body_unit)
            direction = rotation.rotate(body_unit)
            bx, by, bz = body_unit
            body_cross = np.array([[0., -bz, by], [bz, 0., -bx], [-by, bx, 0.]])
            direction_jacobian = -rotation.matrix() @ body_cross
            direction_covariance = direction_jacobian @ attitude_covariance @ direction_jacobian.T
            tangent_first = np.cross(direction, np.eye(3)[np.argmin(np.abs(direction))])
            tangent_first /= np.linalg.norm(tangent_first)
            tangent_basis = np.column_stack((tangent_first, np.cross(direction, tangent_first)))
            output.update(
                baseline_direction_n=direction.tolist(),
                baseline_tangent_basis_n=tangent_basis.tolist(),
                baseline_tangent_covariance_rad2=(tangent_basis.T @ direction_covariance @ tangent_basis).tolist(),
                direction_uncertainty_kind="LOCAL_GAUSSIAN_CONDITIONAL_ON_INTEGER_AND_SUPPORT_MODEL",
                direction_domain_coverage_certified=False,
            )
            yaw_gradient = np.zeros(3)
            for axis in range(3):
                perturbation = np.eye(3)[axis] * 1e-6
                plus = rotation.retract(perturbation).yaw()
                minus = rotation.retract(-perturbation).yaw()
                yaw_gradient[axis] = math.atan2(math.sin(plus-minus), math.cos(plus-minus)) / 2e-6
            output["yaw_conditional_std_rad"] = math.sqrt(max(0.0, float(yaw_gradient @ attitude_covariance @ yaw_gradient)))
            candidate_rpy = [b.current_output()["rpy_rad"] for b in self.branches]
            delta = 2.0 * (costs - costs.min())
            supported = delta <= self.profile_support_delta
            status = "CONDITIONAL_SUPPORT" if self.proposal_complete else "UNRESOLVED_ENUMERATION_OR_BRANCH_BUDGET"
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
                candidate_support_complete=self.proposal_complete,
                consumed_phase_relations=self.last_phase_relation_count,
                selected_branch=int(order[0]), branch_conditional_navigation=True,
                revocation=bool(affected and self.mode in ("U2", "U3")),
                revoked_support_ids=sorted(self.stop_from),
                replay_performed=bool(affected and self.rebuild_history and self.decisions[-1]["kind"] == "REBUILD_SHARED_STATE_AND_DIRECTION_SUPPORT"),
            )
            self.rows.append(output)
            self._save(index, t)
            if index % 100 == 0:
                print(f"{self.mode} t={t:.1f}/{events[-1]['time_s']:.1f}s branches={len(self.branches)} replayed={self.replayed_events}", flush=True)
        return dict(rows=self.rows, decisions=self.decisions, summary=dict(
            mode=self.mode, causal_output_rows=len(self.rows), elapsed_s=time.monotonic()-started,
            replayed_events=self.replayed_events, proposal_attempts=self.proposal_attempts,
            dormant_candidates=len(self.dormant_candidates), active_support_complete=self.proposal_complete,
            revoked_arcs=sorted(self.revoked_arcs),
            marginalized_variables=sum(b.window.marginalized_total for b in self.branches),
            truth_used_online=False, probability_calibrated=False,
            complete_research_goal=False,
        ))
