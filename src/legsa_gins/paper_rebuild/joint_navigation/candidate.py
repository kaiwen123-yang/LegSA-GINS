"""Raw-only candidate proposals and partial integer-relation coordinates.

Proposals are possible interpretations of a Gaussian relaxation. A limited active
set is an allocation of computation, never an ambiguity acceptance declaration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np
from scipy.stats import chi2

from ..carrier_phase.candidate_envelope import (
    enumerate_candidate_envelope, filter_length_necessary_support,
)
from ..carrier_phase.solver import evaluate_integer
from ..carrier_phase.temporal import EpochBlock, assemble_epochs, joint_float, has_cross_epoch_covariance
from .coupled_length_profile import coupled_length_profile


RAW_WORKING_QUANTILE = 0.999
ENUMERATION_NODE_LIMIT = 20000
ENUMERATION_CANDIDATE_LIMIT = 1024
ENUMERATION_TIMEOUT_S = 0.5


@dataclass(frozen=True)
class IntegerCandidate:
    integer_by_label: dict[str, int]
    raw_cost: float
    baseline_center_m: tuple[float, float, float]
    support_status: str = "EXACT_EPOCH_LENGTH_PROFILE"
    raw_cost_lower_bound: float | None = None
    raw_cost_upper_bound: float | None = None


@dataclass(frozen=True)
class CandidateProposal:
    active: tuple[IntegerCandidate, ...]
    dormant: tuple[IntegerCandidate, ...]
    metadata: dict


def propose_candidates(
    blocks: Sequence[EpochBlock],
    baseline_body: np.ndarray,
    max_active: int = 4,
    *,
    conditioned_integer_by_label: dict[str, int] | None = None,
    conditioned_linear_relations: Sequence[dict] | None = None,
    temporal_covariance: np.ndarray | None = None,
) -> CandidateProposal:
    """Qualify every enumerated raw candidate before allocating active branches.

    The fixed chi-square quantile sets a working Gaussian raw-cost budget, not
    a physical coverage or false-fix probability. A whole-ellipsoid radial bound
    first excludes impossible lengths. Each survivor then receives the exact
    epoch-separable fixed-length profile when Q separates by epoch. Cross-epoch
    Q instead receives necessary lower and feasible upper bounds; straddling
    candidates remain unresolved and retained. Body attitude and foot/IMU
    evidence are absent here; R*b_body in the shared graph supplies those links.
    These costs allocate interpretations, never become additional observations.
    Existing physical relations can condition the candidate domain before its
    active/dormant allocation; the controller retains their source dependencies.
    """
    conditioned = dict(conditioned_integer_by_label or {})
    linear_relations = tuple(conditioned_linear_relations or ())
    blocks = tuple(blocks)
    if not blocks:
        return CandidateProposal((), (), dict(
            status="NO_CARRIER_BLOCKS", enumeration_complete=False,
            active_support_complete=False, enumerated_count=0, active_count=0,
            dormant_count=0, remaining_count=None, remaining_count_lower_bound=0,
            integer_acceptance_defined=False, conditioned_on=conditioned,
        ))
    problem = assemble_epochs(blocks, length_m=float(np.linalg.norm(baseline_body)),
                              temporal_covariance=temporal_covariance)
    coupled = has_cross_epoch_covariance(problem)
    threshold = float(chi2.ppf(RAW_WORKING_QUANTILE, len(problem.y)))
    envelope = enumerate_candidate_envelope(
        problem, threshold, lambda_library=None,
        horizontal_axes=np.array([[1., 0., 0.], [0., 1., 0.]]),
        node_limit=ENUMERATION_NODE_LIMIT,
        candidate_limit=ENUMERATION_CANDIDATE_LIMIT,
        timeout_s=ENUMERATION_TIMEOUT_S,
    )
    length_support = filter_length_necessary_support(problem, envelope)
    length_checks = {item.integer: item for item in length_support.items}
    floating = (joint_float(problem) if envelope.candidates and
                envelope.status != "UNQUALIFIED_NUMERICS" else None)
    threshold_expanded = envelope.expanded_working_threshold
    qualified, qualifications = [], []
    for item in envelope.candidates:
        raw_relaxed_cost = float(envelope.float_residual_cost + item.gaussian_integer_cost)
        record = dict(
            integer_by_label=dict(zip(envelope.ambiguity_labels, item.integer)),
            relaxed_raw_cost=raw_relaxed_cost,
            relaxed_target_center_m=item.baseline_center_m,
            remaining_raw_budget=item.remaining_raw_budget,
        )
        if envelope.status == "UNQUALIFIED_NUMERICS":
            record.update(
                retained=None, reason="UNQUALIFIED_NUMERICS_NOT_SCIENTIFIC_EXCLUSION",
                constrained_raw_cost=None, joint_raw_cost_lower_bound=None,
            )
            qualifications.append(record)
            continue
        radial = length_checks[item.integer]
        record["radial_checks"] = [asdict(check) for check in radial.checks]
        # The projected conditional ellipsoid is enclosed by this ball. If it
        # misses any required sphere, no trajectory R_k*b_body can fit the same
        # raw support budget, regardless of its IMU or foot observations.
        if not radial.retained:
            radial_penalty = max(
                (check.center_norm_m-check.exact_model_length_m)**2 /
                float(np.linalg.eigvalsh(
                    floating.conditional_covariance_b[section, section])[-1])
                for check, section in zip(radial.checks, problem.baseline_slices))
            bound = raw_relaxed_cost + radial_penalty
            guard = (float(envelope.floating_cost_guard) +
                     envelope.relative_numerical_guard * max(1.0, abs(bound)))
            record.update(
                retained=False, reason="WHOLE_ELLIPSOID_MISSES_BASELINE_LENGTH",
                rejection_witness="RADIAL_SEPARATION_EXCEEDS_OUTER_RADIUS",
                constrained_raw_cost=None, joint_raw_cost_lower_bound=bound-guard,
                comparison_cost_guard=guard,
            )
            qualifications.append(record)
            continue

        if coupled:
            profile = coupled_length_profile(problem, floating, item.integer)
            cost_guard = (2e-6 + 2e-8 * max(abs(profile.raw_cost_upper_bound),
                                          abs(profile.relaxed_raw_cost + profile.conditional_cost_upper_bound))
                          + float(envelope.floating_cost_guard))
            lower_bound = float(profile.raw_cost_lower_bound - cost_guard)
            upper_bound = float(profile.raw_cost_upper_bound + cost_guard)
            identity_qualified = (abs(profile.objective_identity_error) <= cost_guard and
                                  abs(profile.relaxed_objective_identity_error) <= cost_guard and
                                  profile.maximum_length_error_m <= 1e-8)
            if not identity_qualified:
                length_qualified, support_status = None, "NUMERICAL_PROFILE_UNRESOLVED"
            elif upper_bound <= threshold_expanded:
                length_qualified, support_status = True, "FEASIBLE_UPPER_WITHIN_BUDGET"
            elif lower_bound > threshold_expanded:
                length_qualified, support_status = False, "LOWER_BOUND_EXCEEDS_BUDGET"
            else:
                length_qualified, support_status = None, "LOWER_UPPER_STRADDLE"
            allocation_cost = float(profile.raw_cost_upper_bound)
            record.update(
                coupled_length_profile=True, support_status=support_status,
                length_support_decided=length_qualified is not None,
                constrained_raw_cost=allocation_cost,
                constrained_raw_cost_semantics="FEASIBLE_UPPER_BOUND_NOT_GLOBAL_PROFILE_MINIMUM",
                joint_raw_cost_lower_bound=lower_bound,
                joint_raw_cost_upper_bound=upper_bound,
                unguarded_raw_cost_lower_bound=profile.raw_cost_lower_bound,
                unguarded_raw_cost_upper_bound=profile.raw_cost_upper_bound,
                conditional_cost_lower_bound=profile.conditional_cost_lower_bound,
                conditional_cost_upper_bound=profile.conditional_cost_upper_bound,
                marginal_sphere_costs=list(profile.marginal_sphere_costs),
                marginal_bound_combination="MAX_NOT_SUM",
                comparison_cost_guard=cost_guard,
                maximum_length_error_m=profile.maximum_length_error_m,
                objective_identity_error=profile.objective_identity_error,
                relaxed_objective_identity_error=profile.relaxed_objective_identity_error,
                objective_identity_qualified=identity_qualified,
                constrained_baselines_m=profile.baselines.tolist(),
                local_optimizations=list(profile.local_optimizations),
                global_profile_optimum_certified=False,
            )
        else:
            # Keep the existing independent-Q numerical path unchanged.
            exact = evaluate_integer(problem, floating, item.integer)
            cost_guard = (2e-6 + 2e-8 * max(abs(exact.full_residual_cost),
                                          abs(exact.reduced_cost))
                          + float(envelope.floating_cost_guard))
            lower_bound = float(exact.full_residual_cost - cost_guard)
            upper_bound = float(exact.full_residual_cost + cost_guard)
            length_qualified = lower_bound <= threshold_expanded
            support_status = "EXACT_EPOCH_LENGTH_PROFILE"
            allocation_cost = float(exact.full_residual_cost)
            record.update(
                constrained_raw_cost=allocation_cost,
                joint_raw_cost_lower_bound=lower_bound,
                comparison_cost_guard=cost_guard,
                maximum_length_error_m=float(exact.maximum_length_error_m),
                objective_identity_error=float(exact.objective_identity_error),
                constrained_baselines_m=exact.baselines.tolist(),
            )
        integer_by_label = dict(zip(envelope.ambiguity_labels, item.integer))
        incompatible = {
            label: dict(candidate_value=integer_by_label[label], history_value=value)
            for label, value in conditioned.items()
            if label in integer_by_label and integer_by_label[label] != value
        }
        linear_conflicts = []
        for relation in linear_relations:
            value = sum(int(coefficient)*integer_by_label[label]
                        for label, coefficient in relation["coefficients"])
            if value != relation["rhs_integer"]:
                linear_conflicts.append(dict(relation=relation, candidate_value=value))
        # An unresolved product-sphere profile remains a possible interpretation.
        # A local optimizer's budget or upper cost cannot exclude that integer.
        retained = length_qualified is not False and not incompatible and not linear_conflicts
        record.update(
            retained=retained,
            length_qualified=length_qualified,
            history_relation_compatible=not incompatible and not linear_conflicts,
            history_relation_conflicts=incompatible,
            history_linear_relation_conflicts=linear_conflicts,
            reason=("HISTORY_RELATION_CONDITION" if length_qualified is not False and (incompatible or linear_conflicts) else
                    "COUPLED_LENGTH_PROFILE_UNRESOLVED" if retained and length_qualified is None else
                    "WITHIN_FIXED_LENGTH_RAW_SUPPORT" if retained else
                    "COUPLED_LENGTH_LOWER_BOUND_EXCEEDS_BUDGET" if coupled else
                    "FIXED_LENGTH_RAW_PROFILE_EXCEEDS_BUDGET"),
        )
        qualifications.append(record)
        if retained:
            qualified.append(IntegerCandidate(
                integer_by_label, allocation_cost, item.baseline_center_m,
                support_status, lower_bound, upper_bound,
            ))

    candidates = tuple(sorted(
        qualified, key=lambda candidate: (candidate.raw_cost,
                                          tuple(candidate.integer_by_label.values()))))
    active_count = min(max_active, len(candidates))
    active, dormant = candidates[:active_count], candidates[active_count:]
    complete = envelope.numerical_support_complete
    length_complete = (envelope.status != "UNQUALIFIED_NUMERICS" and not any(
        record["retained"] is None or record.get("length_support_decided") is False
        for record in qualifications))
    metadata = dict(
        status=envelope.status,
        termination_reason=envelope.termination_reason,
        enumeration_complete=complete,
        length_support_complete=length_complete,
        has_cross_epoch_covariance=coupled,
        active_support_complete=complete and length_complete and len(dormant) == 0,
        enumerated_count=len(envelope.candidates),
        length_qualified_count=sum(record.get("length_qualified") is True for record in qualifications),
        length_rejected_count=sum(record["reason"] in (
            "WHOLE_ELLIPSOID_MISSES_BASELINE_LENGTH",
            "FIXED_LENGTH_RAW_PROFILE_EXCEEDS_BUDGET",
            "COUPLED_LENGTH_LOWER_BOUND_EXCEEDS_BUDGET") for record in qualifications),
        length_unqualified_count=sum(record["retained"] is None or
            record.get("length_support_decided") is False for record in qualifications),
        length_unresolved_count=sum(record.get("length_support_decided") is False for record in qualifications),
        history_condition_excluded_count=sum(
            record["reason"] == "HISTORY_RELATION_CONDITION" for record in qualifications),
        history_compatible_candidate_count=len(candidates),
        conditioned_on=conditioned, conditioned_linear_relations=linear_relations,
        active_count=len(active), dormant_count=len(dormant),
        remaining_count=len(dormant) if complete else None,
        remaining_count_lower_bound=len(dormant),
        ambiguity_labels=envelope.ambiguity_labels,
        raw_cost_threshold=threshold,
        expanded_working_threshold=threshold_expanded,
        raw_working_quantile=RAW_WORKING_QUANTILE,
        threshold_degrees_of_freedom=len(problem.y),
        expanded_nodes=envelope.expanded_nodes,
        integer_leaves=envelope.integer_leaves,
        elapsed_s=envelope.elapsed_s,
        node_limit=ENUMERATION_NODE_LIMIT,
        candidate_limit=ENUMERATION_CANDIDATE_LIMIT,
        timeout_s=ENUMERATION_TIMEOUT_S,
        integer_acceptance_defined=False,
        raw_coverage_scope=envelope.coverage_scope,
        coverage_scope=("NUMERICAL_RAW_COUPLED_LENGTH_BOUNDS_WITH_UNRESOLVED_IDENTITIES" if coupled else
                        "NUMERICAL_RAW_LENGTH_SUPPORT_CONDITIONED_ON_HISTORY_RELATIONS"
                        if conditioned or linear_relations else
                        "NUMERICAL_RAW_SUPPORT_WITH_EPOCH_SEPARABLE_EXACT_BASELINE_LENGTH"),
        sphere_feasibility=("RADIAL_THEN_MARGINAL_MAX_LOWER_AND_FEASIBLE_JOINT_UPPER" if coupled else
                            "RADIAL_NECESSARY_FILTER_THEN_EXACT_EPOCH_LENGTH_PROFILE"),
        length_qualification_status=(("COUPLED_LENGTH_SUPPORT_DECIDED" if length_complete else
                                      "INCOMPLETE_COUPLED_LENGTH_SUPPORT") if coupled else length_support.status),
        candidate_qualifications=qualifications,
        rigorous_interval_certificate=False,
        physical_coverage_probability=None,
        false_fix_probability=None,
        proposal_sources=("raw_code", "raw_carrier", "rigid_baseline_length"),
        qualification_added_to_navigation_likelihood=False,
    )
    return CandidateProposal(active, dormant, metadata)


def relation_parameterization(C: np.ndarray, m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return n0, Z for N = n0 + Z*z satisfying C*N = m.

    Z spans every remaining continuous freedom. This coordinate transformation
    never rounds or fixes z; a candidate's claimed integer relations are supplied
    explicitly by the caller and their validity is decided by the joint model.
    """
    C = np.asarray(C, dtype=float)
    m = np.asarray(m, dtype=float)
    U, singular, Vt = np.linalg.svd(C, full_matrices=True)
    tolerance = np.finfo(float).eps * max(C.shape) * singular[0] if singular.size else 0.
    rank = int(np.sum(singular > tolerance))
    n0 = Vt[:rank].T @ ((U[:, :rank].T @ m) / singular[:rank])
    if not np.allclose(C @ n0, m, atol=1e-10, rtol=1e-10):
        raise ValueError("integer relations are mutually inconsistent")
    return n0, Vt[rank:].T.copy()
