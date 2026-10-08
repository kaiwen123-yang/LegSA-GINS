"""Raw-only candidate proposals and partial integer-relation coordinates.

Proposals are possible interpretations of a Gaussian relaxation. A limited active
set is an allocation of computation, never an ambiguity acceptance declaration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import chi2

from ..carrier_phase.candidate_envelope import enumerate_candidate_envelope
from ..carrier_phase.temporal import EpochBlock, assemble_epochs


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
) -> CandidateProposal:
    """Enumerate raw GLS support, retaining every enumerated dormant candidate.

    The fixed chi-square quantile only sets a working Gaussian raw-cost budget.
    It is not a calibrated physical coverage or a false-fix probability. Body
    geometry supplies its length; neither body attitude nor foot/IMU evidence is
    admitted here. Reduced per-epoch ambiguity columns are assembled by label.
    """
    blocks = tuple(blocks)
    if not blocks:
        return CandidateProposal((), (), dict(
            status="NO_CARRIER_BLOCKS", enumeration_complete=False,
            active_support_complete=False, enumerated_count=0, active_count=0,
            dormant_count=0, remaining_count=None, remaining_count_lower_bound=0,
            integer_acceptance_defined=False,
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
    candidates = tuple(
        IntegerCandidate(
            dict(zip(envelope.ambiguity_labels, item.integer)),
            float(envelope.float_residual_cost + item.gaussian_integer_cost),
            item.baseline_center_m,
        )
        for item in sorted(envelope.candidates, key=lambda c: (c.gaussian_integer_cost, c.integer))
    )
    # Numerically unqualified leaves remain recorded, but cannot seed an active
    # claim about support. Incomplete resource-bounded enumeration can seed work.
    active_count = min(max_active, len(candidates)) if envelope.status != "UNQUALIFIED_NUMERICS" else 0
    active, dormant = candidates[:active_count], candidates[active_count:]
    complete = envelope.numerical_support_complete
    metadata = dict(
        status=envelope.status,
        termination_reason=envelope.termination_reason,
        enumeration_complete=complete,
        active_support_complete=complete and len(dormant) == 0,
        enumerated_count=len(candidates), active_count=len(active), dormant_count=len(dormant),
        remaining_count=len(dormant) if complete else None,
        remaining_count_lower_bound=len(dormant),
        ambiguity_labels=envelope.ambiguity_labels,
        raw_cost_threshold=threshold,
        raw_working_quantile=RAW_WORKING_QUANTILE,
        threshold_degrees_of_freedom=len(problem.y),
        expanded_nodes=envelope.expanded_nodes,
        integer_leaves=envelope.integer_leaves,
        elapsed_s=envelope.elapsed_s,
        node_limit=ENUMERATION_NODE_LIMIT,
        candidate_limit=ENUMERATION_CANDIDATE_LIMIT,
        timeout_s=ENUMERATION_TIMEOUT_S,
        integer_acceptance_defined=False,
        coverage_scope=envelope.coverage_scope,
        sphere_feasibility="NOT_TESTED_LENGTH_CONSTRAINT_RELAXED",
        physical_coverage_probability=None,
        false_fix_probability=None,
        proposal_sources=("raw_code", "raw_carrier"),
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
