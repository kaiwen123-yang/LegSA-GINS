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
from ..carrier_phase.temporal import EpochBlock, assemble_epochs, joint_float


RAW_WORKING_QUANTILE = 0.999
ENUMERATION_NODE_LIMIT = 20000
ENUMERATION_CANDIDATE_LIMIT = 1024
ENUMERATION_TIMEOUT_S = 0.5


@dataclass(frozen=True)
class IntegerCandidate:
    integer_by_label: dict[str, int]
    raw_cost: float
    baseline_center_m: tuple[float, float, float]


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
) -> CandidateProposal:
    """Qualify every enumerated raw candidate before allocating active branches.

    The fixed chi-square quantile sets a working Gaussian raw-cost budget, not
    a physical coverage or false-fix probability. A whole-ellipsoid radial bound
    first excludes impossible lengths. Each survivor then receives the exact
    epoch-separable fixed-length raw profile cost. Body attitude and foot/IMU
    evidence are absent here; R*b_body in the shared graph supplies those links.
    These costs allocate interpretations, never become additional observations.
    Existing physical relations can condition the candidate domain before its
    active/dormant allocation; the controller retains their source dependencies.
    """
    conditioned = dict(conditioned_integer_by_label or {})
    blocks = tuple(blocks)
    if not blocks:
        return CandidateProposal((), (), dict(
            status="NO_CARRIER_BLOCKS", enumeration_complete=False,
            active_support_complete=False, enumerated_count=0, active_count=0,
            dormant_count=0, remaining_count=None, remaining_count_lower_bound=0,
            integer_acceptance_defined=False, conditioned_on=conditioned,
        ))
    problem = assemble_epochs(blocks, length_m=float(np.linalg.norm(baseline_body)))
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

        exact = evaluate_integer(problem, floating, item.integer)
        # The existing solver checks the raw/reduced identity at this tolerance.
        # Retain the numerical boundary; these are floating-point working-model
        # bounds, not interval-arithmetic certificates.
        cost_guard = (2e-6 + 2e-8 * max(abs(exact.full_residual_cost),
                                      abs(exact.reduced_cost))
                      + float(envelope.floating_cost_guard))
        lower_bound = float(exact.full_residual_cost - cost_guard)
        retained = lower_bound <= threshold_expanded
        integer_by_label = dict(zip(envelope.ambiguity_labels, item.integer))
        incompatible = {
            label: dict(candidate_value=integer_by_label[label], history_value=value)
            for label, value in conditioned.items()
            if label in integer_by_label and integer_by_label[label] != value
        }
        length_qualified = retained
        retained = retained and not incompatible
        record.update(
            retained=retained,
            length_qualified=length_qualified,
            history_relation_compatible=not incompatible,
            history_relation_conflicts=incompatible,
            reason=("HISTORY_RELATION_CONDITION" if length_qualified and incompatible else
                    "WITHIN_FIXED_LENGTH_RAW_SUPPORT" if retained else
                    "FIXED_LENGTH_RAW_PROFILE_EXCEEDS_BUDGET"),
            constrained_raw_cost=float(exact.full_residual_cost),
            joint_raw_cost_lower_bound=lower_bound,
            comparison_cost_guard=cost_guard,
            maximum_length_error_m=float(exact.maximum_length_error_m),
            objective_identity_error=float(exact.objective_identity_error),
            constrained_baselines_m=exact.baselines.tolist(),
        )
        qualifications.append(record)
        if retained:
            qualified.append(IntegerCandidate(
                integer_by_label,
                float(exact.full_residual_cost), item.baseline_center_m,
            ))

    candidates = tuple(sorted(
        qualified, key=lambda candidate: (candidate.raw_cost,
                                          tuple(candidate.integer_by_label.values()))))
    active_count = min(max_active, len(candidates))
    active, dormant = candidates[:active_count], candidates[active_count:]
    complete = envelope.numerical_support_complete
    metadata = dict(
        status=envelope.status,
        termination_reason=envelope.termination_reason,
        enumeration_complete=complete,
        active_support_complete=complete and len(dormant) == 0,
        enumerated_count=len(envelope.candidates),
        length_qualified_count=sum(record.get("length_qualified", False) for record in qualifications),
        length_rejected_count=sum(record["reason"] in (
            "WHOLE_ELLIPSOID_MISSES_BASELINE_LENGTH",
            "FIXED_LENGTH_RAW_PROFILE_EXCEEDS_BUDGET") for record in qualifications),
        length_unqualified_count=sum(record["retained"] is None for record in qualifications),
        history_condition_excluded_count=sum(
            record["reason"] == "HISTORY_RELATION_CONDITION" for record in qualifications),
        history_compatible_candidate_count=len(candidates),
        conditioned_on=conditioned,
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
        coverage_scope=("NUMERICAL_RAW_LENGTH_SUPPORT_CONDITIONED_ON_HISTORY_RELATIONS"
                        if conditioned else
                        "NUMERICAL_RAW_SUPPORT_WITH_EPOCH_SEPARABLE_EXACT_BASELINE_LENGTH"),
        sphere_feasibility="RADIAL_NECESSARY_FILTER_THEN_EXACT_EPOCH_LENGTH_PROFILE",
        length_qualification_status=length_support.status,
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
