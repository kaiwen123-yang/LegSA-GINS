"""Strict constrained integer least-squares implementation.

Small synthetic problems retain a complete finite enumeration oracle.  The
production path uses standard RTKLIB LAMBDA decorrelation and ordinary-ILS
candidates only to seed a finite incumbent.  An exact best-first
branch-and-bound then evaluates the full fixed-length conditional-baseline
objective until its frontier bound certifies the global first and second
solutions.  Any explicit resource limit fails closed without a certificate.
"""

from __future__ import annotations

import itertools
import ctypes
import heapq
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np


class CLambdaError(ValueError):
    pass


class SearchIncomplete(CLambdaError):
    code = "SEARCH_INCOMPLETE"


class SearchTimeout(SearchIncomplete):
    code = "SEARCH_TIMEOUT"


class LambdaBridgeError(CLambdaError):
    code = "LAMBDA_BRIDGE_ERROR"


@dataclass(frozen=True)
class FloatSolution:
    ambiguity: np.ndarray
    baseline: np.ndarray
    covariance: np.ndarray
    covariance_aa: np.ndarray
    covariance_ba: np.ndarray
    conditional_covariance_b: np.ndarray
    residual_objective: float


@dataclass(frozen=True)
class ConditionalBaseline:
    baseline: np.ndarray
    objective: float
    lagrange_multiplier: float
    constraint_error_m: float
    hard_case: bool


@dataclass(frozen=True)
class Candidate:
    ambiguity: np.ndarray
    baseline: np.ndarray
    objective: float
    ambiguity_objective: float
    baseline_objective: float
    constraint_error_m: float

    @property
    def ambiguity_quadratic_term(self) -> float:
        """The integer-only term in P01 Eq. (22)."""
        return self.ambiguity_objective

    @property
    def conditional_baseline_constraint_term(self) -> float:
        """The fixed-length conditional-baseline term in P01 Eq. (22)."""
        return self.baseline_objective

    @property
    def total_constrained_objective(self) -> float:
        """Full C-LAMBDA objective, excluding the common float residual."""
        return self.objective


@dataclass(frozen=True)
class ProductionObjectiveEvaluation:
    """Exact production-objective and observation-residual decomposition.

    The candidate objective is the increase relative to the joint float
    least-squares minimum.  ``whitened_total_residual_squared`` evaluates the
    same integer/baseline candidate directly in observation space.  Their
    difference, after adding ``float_residual_objective``, is retained as a
    numerical audit rather than silently assumed to be zero.
    """

    candidate: Candidate
    float_residual_objective: float
    whitened_code_residual_norm: float
    whitened_phase_residual_norm: float
    whitened_total_residual_norm: float
    whitened_total_residual_squared: float
    objective_identity_error: float
    code_phase_cross_covariance_zero: bool

    @property
    def ambiguity_quadratic_term(self) -> float:
        return self.candidate.ambiguity_quadratic_term

    @property
    def conditional_baseline_constraint_term(self) -> float:
        return self.candidate.conditional_baseline_constraint_term

    @property
    def total_constrained_objective(self) -> float:
        return self.candidate.total_constrained_objective


GLOBAL_BOUND_CERTIFIED = "GLOBAL_BOUND_CERTIFIED"
NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
NO_FEASIBLE_MODEL = "NO_FEASIBLE_MODEL"


@dataclass(frozen=True)
class SearchCertificate:
    """Machine-auditable certificate for the strict integer search.

    ``lambda_seed_count_*`` describes only RTKLIB incumbent seeding.  It is
    deliberately separate from tree nodes and integer leaves: the seed count
    is never an enumeration cap.  A configured protective node limit can only
    terminate with ``NUMERICAL_FAILURE`` and can never produce a global
    certificate.
    """

    lambda_seed_count_requested: int
    lambda_seed_count_returned: int
    branch_and_bound_nodes_expanded: int
    integer_leaves_evaluated: int
    unique_integer_candidates_evaluated: int
    frontier_lower_bound_at_termination: float | None
    best_total_objective: float | None
    second_total_objective: float | None
    termination_reason: str
    global_optimum_certified: bool
    runtime_budget_exhausted: bool
    configured_node_limit: int | None
    node_limit_exhausted: bool
    candidate_cap_applied: bool = False


@dataclass(frozen=True)
class StrictSearchOutcome:
    best: Candidate | None
    second: Candidate | None
    certificate: SearchCertificate
    failure_code: str | None = None

    def _legacy_tuple(self) -> tuple[
            Candidate | None, Candidate | None, int, int, bool,
            str | None, float | None]:
        """Keep the Phase-1 seven-value interface while callers migrate."""
        return (
            self.best,
            self.second,
            self.certificate.branch_and_bound_nodes_expanded,
            self.certificate.unique_integer_candidates_evaluated,
            self.certificate.global_optimum_certified,
            self.failure_code,
            self.certificate.frontier_lower_bound_at_termination,
        )

    def __iter__(self):
        return iter(self._legacy_tuple())

    def __len__(self) -> int:
        return 7

    def __getitem__(self, index):
        return self._legacy_tuple()[index]


@dataclass(frozen=True)
class CLambdaResult:
    best: Candidate | None
    second: Candidate | None
    ratio: float | None
    ratio_valid: bool
    search_complete: bool
    nodes_visited: int
    candidates_evaluated: int
    runtime_seconds: float
    float_solution: FloatSolution
    status: str = "fixed"
    failure_code: str | None = None
    completion_bound: float | None = None
    lambda_seed_count_requested: int = 0
    lambda_seed_count_returned: int = 0
    branch_and_bound_nodes_expanded: int = 0
    integer_leaves_evaluated: int = 0
    unique_integer_candidates_evaluated: int = 0
    frontier_lower_bound_at_termination: float | None = None
    termination_reason: str = GLOBAL_BOUND_CERTIFIED
    global_optimum_certified: bool = False
    runtime_budget_exhausted: bool = False
    configured_node_limit: int | None = None
    node_limit_exhausted: bool = False
    candidate_cap_applied: bool = False
    best_total_objective: float | None = None
    second_total_objective: float | None = None
    integer_solution_returned: bool = False
    ambiguity_acceptance_test_defined: bool = False
    ambiguity_accepted: bool | None = None


@dataclass(frozen=True)
class LambdaIntegerCandidate:
    ambiguity: np.ndarray
    ambiguity_objective: float


@dataclass(frozen=True)
class LambdaReduction:
    transformation: np.ndarray
    float_ambiguity: np.ndarray
    covariance: np.ndarray


class RTKLIBLambdaBridge:
    """Thin wrapper for RTKLIB ``lambda`` using its column-major C ABI."""

    def __init__(self, library_path: str | Path):
        path = Path(library_path).expanduser()
        if not path.is_file():
            raise LambdaBridgeError(f"RTKLIB LAMBDA bridge does not exist: {path}")
        try:
            library = ctypes.CDLL(str(path.resolve()))
            function = getattr(library, "lambda")
            reduction = getattr(library, "lambda_reduction")
        except (OSError, AttributeError) as exc:
            raise LambdaBridgeError(
                f"unable to load RTKLIB lambda()/lambda_reduction() from {path}"
            ) from exc
        pointer = ctypes.POINTER(ctypes.c_double)
        function.argtypes = [ctypes.c_int, ctypes.c_int, pointer, pointer, pointer, pointer]
        function.restype = ctypes.c_int
        reduction.argtypes = [ctypes.c_int, pointer, pointer]
        reduction.restype = ctypes.c_int
        self._library = library
        self._function = function
        self._reduction = reduction
        self.path = path.resolve()

    def candidates(self, ambiguity: Sequence[float], covariance: np.ndarray,
                   count: int) -> list[LambdaIntegerCandidate]:
        floating = np.asarray(ambiguity, dtype=np.float64)
        qaa = _positive_definite(covariance, "ambiguity covariance")
        if floating.ndim != 1 or floating.size == 0 or np.any(~np.isfinite(floating)):
            raise LambdaBridgeError("float ambiguities must be a finite nonempty vector")
        if qaa.shape != (floating.size, floating.size) or count < 1:
            raise LambdaBridgeError("invalid RTKLIB LAMBDA dimensions")

        # RTKLIB documents Q and F as Fortran-convention matrices.  Do not
        # pass NumPy's default row-major storage, even though Q is symmetric.
        a_buffer = np.ascontiguousarray(floating)
        q_buffer = np.asfortranarray(qaa)
        fixed = np.empty((floating.size, count), dtype=np.float64, order="F")
        norms = np.empty(count, dtype=np.float64)
        pointer = ctypes.POINTER(ctypes.c_double)
        status = self._function(
            int(floating.size), int(count),
            a_buffer.ctypes.data_as(pointer), q_buffer.ctypes.data_as(pointer),
            fixed.ctypes.data_as(pointer), norms.ctypes.data_as(pointer),
        )
        if status != 0:
            raise LambdaBridgeError(f"RTKLIB lambda() returned {status}")
        if np.any(~np.isfinite(fixed)) or np.any(~np.isfinite(norms)):
            raise LambdaBridgeError("RTKLIB lambda() returned non-finite output")
        rounded = np.rint(fixed)
        if not np.allclose(fixed, rounded, rtol=0.0, atol=1e-7):
            raise LambdaBridgeError("RTKLIB lambda() returned a non-integer candidate")

        weight = np.linalg.inv(qaa)
        result: list[LambdaIntegerCandidate] = []
        for index in range(count):
            integer = rounded[:, index].astype(np.int64)
            delta = floating - integer
            recomputed = float(delta @ weight @ delta)
            if not math.isclose(float(norms[index]), recomputed, rel_tol=2e-6, abs_tol=2e-6):
                raise LambdaBridgeError("RTKLIB ambiguity norm does not match Qaa")
            result.append(LambdaIntegerCandidate(integer, recomputed))
        if any(result[index].ambiguity_objective > result[index + 1].ambiguity_objective + 1e-10
               for index in range(len(result) - 1)):
            raise LambdaBridgeError("RTKLIB candidates are not globally norm ordered")
        if len({tuple(item.ambiguity.tolist()) for item in result}) != len(result):
            raise LambdaBridgeError("RTKLIB lambda() returned duplicate candidates")
        return result

    def decorrelate(self, ambiguity: Sequence[float], covariance: np.ndarray) -> LambdaReduction:
        """Return RTKLIB's integer Z, ``z=Z' a`` and ``Qz=Z' Q Z``."""
        floating = np.asarray(ambiguity, dtype=np.float64)
        qaa = _positive_definite(covariance, "ambiguity covariance")
        if floating.ndim != 1 or floating.size == 0 or qaa.shape != (floating.size, floating.size):
            raise LambdaBridgeError("invalid RTKLIB reduction dimensions")
        q_buffer = np.asfortranarray(qaa)
        transformation = np.empty(qaa.shape, dtype=np.float64, order="F")
        pointer = ctypes.POINTER(ctypes.c_double)
        status = self._reduction(
            int(floating.size), q_buffer.ctypes.data_as(pointer),
            transformation.ctypes.data_as(pointer),
        )
        if status != 0 or np.any(~np.isfinite(transformation)):
            raise LambdaBridgeError(f"RTKLIB lambda_reduction() returned {status}")
        integer_z = np.rint(transformation)
        if not np.allclose(transformation, integer_z, rtol=0.0, atol=1e-8):
            raise LambdaBridgeError("RTKLIB reduction matrix is not integer")
        integer_z = integer_z.astype(np.int64)
        determinant = int(round(float(np.linalg.det(integer_z.astype(float)))))
        if abs(determinant) != 1:
            raise LambdaBridgeError("RTKLIB reduction matrix is not unimodular")
        transformed_covariance = integer_z.T @ qaa @ integer_z
        transformed_covariance = _positive_definite(
            transformed_covariance, "decorrelated ambiguity covariance"
        )
        return LambdaReduction(
            integer_z,
            integer_z.T @ floating,
            transformed_covariance,
        )


def _positive_definite(matrix: np.ndarray, name: str) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.ndim != 2 or value.shape[0] != value.shape[1] or np.any(~np.isfinite(value)):
        raise CLambdaError(f"{name} must be a finite square matrix")
    value = (value + value.T) * 0.5
    try:
        np.linalg.cholesky(value)
    except np.linalg.LinAlgError as exc:
        raise CLambdaError(f"{name} must be positive definite") from exc
    return value


def joint_gls(y: Sequence[float], ambiguity_design: np.ndarray,
              baseline_design: np.ndarray, observation_covariance: np.ndarray) -> FloatSolution:
    yv = np.asarray(y, dtype=float)
    a_design = np.asarray(ambiguity_design, dtype=float)
    b_design = np.asarray(baseline_design, dtype=float)
    covariance_y = _positive_definite(observation_covariance, "observation covariance")
    if yv.ndim != 1 or a_design.ndim != 2 or b_design.ndim != 2:
        raise CLambdaError("invalid GLS dimensions")
    if a_design.shape[0] != yv.size or b_design.shape != (yv.size, 3) or covariance_y.shape != (yv.size, yv.size):
        raise CLambdaError("incompatible GLS dimensions")
    design = np.column_stack((a_design, b_design))
    if design.shape[0] < design.shape[1]:
        raise CLambdaError("GLS design matrix is underdetermined")

    # Whiten once with Qyy=L L' and solve min ||L^-1(y-Xx)|| by SVD.  Forming
    # X'Qyy^-1X and inverting it squares the design condition number; on the
    # real short-baseline DD scaling this was large enough to measurably break
    # the observation-space versus parameter-space objective identity.
    whitening_factor = np.linalg.cholesky(covariance_y)
    whitened_design = np.linalg.solve(whitening_factor, design)
    whitened_observation = np.linalg.solve(whitening_factor, yv)
    left, singular_values, right_transpose = np.linalg.svd(
        whitened_design, full_matrices=False
    )
    if singular_values.size != design.shape[1] or np.any(~np.isfinite(singular_values)):
        raise CLambdaError("GLS SVD did not return a finite full parameter spectrum")
    rank_tolerance = (
        np.finfo(float).eps * max(whitened_design.shape) * singular_values[0]
    )
    numerical_rank = int(np.count_nonzero(singular_values > rank_tolerance))
    if numerical_rank != design.shape[1]:
        raise CLambdaError(
            f"GLS design matrix rank deficient: rank={numerical_rank}, "
            f"parameters={design.shape[1]}"
        )
    right = right_transpose.T
    estimate = right @ ((left.T @ whitened_observation) / singular_values)
    inverse_singular_squared = 1.0 / np.square(singular_values)
    covariance = (right * inverse_singular_squared) @ right.T
    covariance = _positive_definite(covariance, "GLS parameter covariance")
    n = a_design.shape[1]
    qaa = covariance[:n, :n]
    qba = covariance[n:, :n]
    conditional = covariance[n:, n:] - qba @ np.linalg.solve(qaa, qba.T)
    conditional = _positive_definite(conditional, "conditional baseline covariance")
    whitened_residual = whitened_observation - whitened_design @ estimate
    return FloatSolution(estimate[:n], estimate[n:], covariance, qaa, qba,
                         conditional, float(whitened_residual @ whitened_residual))


def conditional_float_baseline(solution: FloatSolution, ambiguity: Sequence[int]) -> np.ndarray:
    candidate = np.asarray(ambiguity, dtype=float)
    if candidate.shape != solution.ambiguity.shape:
        raise CLambdaError("ambiguity candidate dimension mismatch")
    return solution.baseline - solution.covariance_ba @ np.linalg.solve(
        solution.covariance_aa, solution.ambiguity - candidate)


def constrained_baseline(center: Sequence[float], covariance: np.ndarray,
                         length_m: float, tolerance: float = 1e-13) -> ConditionalBaseline:
    """Globally minimize (b-center)'Q^-1(b-center) on ||b||=length_m."""
    start = np.asarray(center, dtype=float)
    q = _positive_definite(covariance, "baseline covariance")
    if start.shape != (3,) or np.any(~np.isfinite(start)) or not math.isfinite(length_m) or length_m <= 0:
        raise CLambdaError("invalid constrained-baseline inputs")
    weight = np.linalg.inv(q)
    eigenvalues, vectors = np.linalg.eigh(weight)
    coordinates = vectors.T @ start
    minimum = eigenvalues[0]
    # Work with the eigensystem actually returned by the numerical kernel.  A
    # merely close eigenvalue is not part of the exact minimum eigenspace and
    # must not enter the trust-region hard case.
    min_mask = eigenvalues == minimum

    def b_at(lam: float) -> np.ndarray:
        return eigenvalues * coordinates / (eigenvalues + lam)

    # The global trust-region equality solution has lambda >= -lambda_min.
    lower = -minimum
    # Only an exactly zero projection onto the minimum-eigenvalue eigenspace is
    # the trust-region hard case.  Treating a merely tiny projection as zero can
    # choose the opposite orientation and is not globally minimizing.
    hard_case = bool(np.all(coordinates[min_mask] == 0.0))
    if hard_case:
        lam = lower
        denom = eigenvalues[~min_mask] + lam
        fixed = np.zeros(3)
        if np.any(~min_mask):
            fixed[~min_mask] = eigenvalues[~min_mask] * coordinates[~min_mask] / denom
        remaining = length_m * length_m - float(fixed @ fixed)
        if remaining >= -tolerance:
            fixed[min_mask] = 0.0
            first = int(np.flatnonzero(min_mask)[0])
            fixed[first] = math.sqrt(max(0.0, remaining))
            baseline = vectors @ fixed
            delta = baseline - start
            objective = float(delta @ weight @ delta)
            return ConditionalBaseline(baseline, objective, lam,
                                       abs(float(np.linalg.norm(baseline)) - length_m), True)

    # Solve in delta=lambda+lambda_min, avoiding cancellation when a tiny but
    # nonzero minimum-eigenspace projection places the root close to the pole.
    def b_at_delta(delta: float) -> np.ndarray:
        return eigenvalues * coordinates / (eigenvalues - minimum + delta)

    def secular_delta(delta: float) -> float:
        value = b_at_delta(delta)
        return float(value @ value - length_m * length_m)

    minimum_numerator_scale = float(np.max(np.abs(
        eigenvalues[min_mask] * coordinates[min_mask]
    )))
    lo_delta = minimum_numerator_scale / (2.0 * length_m)
    if lo_delta == 0.0:
        # Exact hard-case projection can still require the regular root when
        # the fixed nonminimum-eigenspace component already exceeds the sphere.
        lo_delta = np.finfo(float).tiny
    hi_delta = max(1.0, minimum)
    while secular_delta(hi_delta) > 0:
        hi_delta *= 2.0
        if not math.isfinite(hi_delta):
            raise CLambdaError("failed to bracket sphere multiplier")
    if secular_delta(lo_delta) < 0:
        raise CLambdaError("unresolved constrained-baseline degeneracy")
    for _ in range(300):
        mid_delta = (lo_delta + hi_delta) * 0.5
        if secular_delta(mid_delta) > 0:
            lo_delta = mid_delta
        else:
            hi_delta = mid_delta
        if hi_delta - lo_delta <= 1e-14 * max(np.finfo(float).tiny, mid_delta):
            break
    delta = (lo_delta + hi_delta) * 0.5
    lam = lower + delta
    baseline = vectors @ b_at_delta(delta)
    # Remove only scalar root-solver drift, not an unconstrained solution gate.
    norm = float(np.linalg.norm(baseline))
    if abs(norm - length_m) > 1e-9:
        raise CLambdaError("sphere root failed constraint tolerance")
    delta = baseline - start
    return ConditionalBaseline(baseline, float(delta @ weight @ delta), lam,
                               abs(norm - length_m), False)


def evaluate_candidate(solution: FloatSolution, ambiguity: Sequence[int], length_m: float) -> Candidate:
    supplied = np.asarray(ambiguity)
    if supplied.shape != solution.ambiguity.shape or np.any(~np.isfinite(supplied.astype(float))):
        raise CLambdaError("ambiguity candidate dimension mismatch or non-finite value")
    rounded = np.rint(supplied.astype(float))
    if not np.allclose(supplied.astype(float), rounded, rtol=0.0, atol=1e-10):
        raise CLambdaError("ambiguity candidate must be integer valued")
    integer = rounded.astype(np.int64)
    delta = solution.ambiguity - integer
    ambiguity_objective = float(delta @ np.linalg.solve(solution.covariance_aa, delta))
    conditional_center = conditional_float_baseline(solution, integer)
    constrained = constrained_baseline(conditional_center, solution.conditional_covariance_b, length_m)
    return Candidate(integer, constrained.baseline,
                     ambiguity_objective + constrained.objective,
                     ambiguity_objective, constrained.objective,
                     constrained.constraint_error_m)


def _whitened_norm(residual: np.ndarray, covariance: np.ndarray,
                   name: str) -> float:
    covariance = _positive_definite(covariance, name)
    value = np.asarray(residual, dtype=float)
    if value.ndim != 1 or value.size != covariance.shape[0] or np.any(~np.isfinite(value)):
        raise CLambdaError(f"{name} residual has incompatible dimensions")
    # Q=L L' and ||L^-1 r|| is exactly sqrt(r'Q^-1 r).  Avoid explicitly
    # forming Q^-1 so the diagnostic uses the production covariance scaling.
    whitened = np.linalg.solve(np.linalg.cholesky(covariance), value)
    return float(np.linalg.norm(whitened))


def evaluate_production_objective(
        solution: FloatSolution,
        ambiguity: Sequence[int],
        length_m: float,
        observation: Sequence[float],
        ambiguity_design: np.ndarray,
        baseline_design: np.ndarray,
        observation_covariance: np.ndarray,
        *,
        code_observation_count: int | None = None,
        cross_covariance_tolerance: float = 1e-12,
) -> ProductionObjectiveEvaluation:
    """Evaluate an integer candidate with the exact production objective.

    The helper is intentionally independent of candidate provenance.  It can
    therefore compare a production winner and a diagnostic proxy-derived
    integer vector without changing either the model or search.  The Phase-1
    DD builder orders code rows before carrier rows; callers must pass the code
    row count explicitly when that layout is not an equal split.
    """
    y = np.asarray(observation, dtype=float)
    a_design = np.asarray(ambiguity_design, dtype=float)
    b_design = np.asarray(baseline_design, dtype=float)
    covariance = _positive_definite(observation_covariance, "observation covariance")
    if y.ndim != 1 or np.any(~np.isfinite(y)):
        raise CLambdaError("observation must be a finite vector")
    if a_design.shape != (y.size, solution.ambiguity.size):
        raise CLambdaError("ambiguity design has incompatible dimensions")
    if b_design.shape != (y.size, 3) or covariance.shape != (y.size, y.size):
        raise CLambdaError("baseline design or covariance has incompatible dimensions")
    if code_observation_count is None:
        if y.size % 2:
            raise CLambdaError("code_observation_count is required for an odd row count")
        code_observation_count = y.size // 2
    if not 0 < code_observation_count < y.size:
        raise CLambdaError("code_observation_count must split code and phase rows")

    candidate = evaluate_candidate(solution, ambiguity, length_m)
    residual = y - a_design @ candidate.ambiguity - b_design @ candidate.baseline
    code_slice = slice(0, code_observation_count)
    phase_slice = slice(code_observation_count, y.size)
    code_covariance = covariance[code_slice, code_slice]
    phase_covariance = covariance[phase_slice, phase_slice]
    cross_covariance = covariance[code_slice, phase_slice]
    covariance_scale = max(1.0, float(np.max(np.abs(covariance))))
    cross_zero = bool(np.all(
        np.abs(cross_covariance) <= cross_covariance_tolerance * covariance_scale
    ))
    code_norm = _whitened_norm(
        residual[code_slice], code_covariance, "code covariance"
    )
    phase_norm = _whitened_norm(
        residual[phase_slice], phase_covariance, "phase covariance"
    )
    total_norm = _whitened_norm(residual, covariance, "observation covariance")
    total_squared = total_norm * total_norm
    expected_total = solution.residual_objective + candidate.objective
    return ProductionObjectiveEvaluation(
        candidate=candidate,
        float_residual_objective=solution.residual_objective,
        whitened_code_residual_norm=code_norm,
        whitened_phase_residual_norm=phase_norm,
        whitened_total_residual_norm=total_norm,
        whitened_total_residual_squared=total_squared,
        objective_identity_error=float(total_squared - expected_total),
        code_phase_cross_covariance_zero=cross_zero,
    )


def search_exact(solution: FloatSolution, length_m: float = 0.350,
                 node_limit: int = 1_000_000) -> tuple[Candidate, Candidate | None, int, int]:
    """Complete enumeration using a P01-F1-compatible ambiguity outer bound."""
    if node_limit <= 0:
        raise SearchIncomplete(SearchIncomplete.code)
    center = np.rint(solution.ambiguity).astype(int)
    seed_offsets = [np.zeros(center.size, dtype=int)]
    for axis in range(center.size):
        for direction in (-1, 1):
            offset = np.zeros(center.size, dtype=int)
            offset[axis] = direction
            seed_offsets.append(offset)
    ranked: dict[tuple[int, ...], Candidate] = {}
    for offset in seed_offsets:
        candidate = evaluate_candidate(solution, center + offset, length_m)
        ranked[tuple(candidate.ambiguity.tolist())] = candidate
    ordered = sorted(ranked.values(), key=lambda item: (item.objective, tuple(item.ambiguity)))
    incumbent = ordered[1].objective if len(ordered) > 1 else ordered[0].objective
    # x'Qaa^-1 x <= incumbent implies |x_i| <= sqrt(incumbent*Qaa_ii).
    ranges = []
    for index, variance in enumerate(np.diag(solution.covariance_aa)):
        radius = math.sqrt(max(0.0, incumbent * float(variance))) + 1e-12
        ranges.append(range(math.ceil(solution.ambiguity[index] - radius),
                            math.floor(solution.ambiguity[index] + radius) + 1))
    nodes = candidates = 0
    weight_b = np.linalg.inv(solution.conditional_covariance_b)
    lambda_min = float(np.linalg.eigvalsh(weight_b)[0])
    for integer_tuple in itertools.product(*ranges):
        nodes += 1
        if nodes > node_limit:
            raise SearchIncomplete(SearchIncomplete.code)
        integer = np.asarray(integer_tuple, dtype=int)
        delta = solution.ambiguity - integer
        base = float(delta @ np.linalg.solve(solution.covariance_aa, delta))
        conditional_center = conditional_float_baseline(solution, integer)
        # P01 Eq34 lower bound F1.
        lower_bound = base + lambda_min * (float(np.linalg.norm(conditional_center)) - length_m) ** 2
        if lower_bound > incumbent + 1e-12:
            continue
        candidate = evaluate_candidate(solution, integer, length_m)
        candidates += 1
        ranked[integer_tuple] = candidate
        ordered = sorted(ranked.values(), key=lambda item: (item.objective, tuple(item.ambiguity)))
        if len(ordered) > 1:
            incumbent = ordered[1].objective
    ordered = sorted(ranked.values(), key=lambda item: (item.objective, tuple(item.ambiguity)))
    return ordered[0], ordered[1] if len(ordered) > 1 else None, nodes, candidates


def search_strict_lambda(solution: FloatSolution, bridge: RTKLIBLambdaBridge,
                         length_m: float = 0.350, initial_candidate_count: int = 8,
                         node_limit: int | None = None,
                         timeout_seconds: float = 1.0) -> StrictSearchOutcome:
    """Search the exact C-LAMBDA objective with a proven stopping bound.

    Standard RTKLIB LAMBDA supplies initial candidates and its standard integer
    decorrelation matrix.  A best-first Schnorr--Euchner tree then enumerates
    the reduced integer lattice.  Each frontier priority is the exact assigned
    suffix contribution and hence a lower bound on every descendant's
    ambiguity objective.  Because the sphere contribution is nonnegative, the
    search is complete once the smallest frontier bound is no smaller than the
    current second-best full objective.  This is search-and-shrink, not an
    ordinary-LAMBDA fix followed by a baseline-length gate.
    """
    if initial_candidate_count < 2 or (node_limit is not None and node_limit < 1):
        raise CLambdaError("invalid strict LAMBDA candidate bounds")

    def outcome(
            evaluated: dict[tuple[int, ...], Candidate], *,
            seed_count_returned: int,
            nodes: int,
            leaves: int,
            frontier_bound: float | None,
            termination_reason: str,
            certified: bool,
            failure_code: str | None,
            runtime_budget_exhausted: bool = False,
            node_limit_exhausted: bool = False,
    ) -> StrictSearchOutcome:
        ordered_candidates = sorted(
            evaluated.values(), key=lambda item: (item.objective, tuple(item.ambiguity))
        )
        best = ordered_candidates[0] if ordered_candidates else None
        second = ordered_candidates[1] if len(ordered_candidates) > 1 else None
        certificate = SearchCertificate(
            lambda_seed_count_requested=initial_candidate_count,
            lambda_seed_count_returned=seed_count_returned,
            branch_and_bound_nodes_expanded=nodes,
            integer_leaves_evaluated=leaves,
            unique_integer_candidates_evaluated=len(evaluated),
            frontier_lower_bound_at_termination=frontier_bound,
            best_total_objective=(None if best is None else best.objective),
            second_total_objective=(None if second is None else second.objective),
            termination_reason=termination_reason,
            global_optimum_certified=certified,
            runtime_budget_exhausted=runtime_budget_exhausted,
            configured_node_limit=node_limit,
            node_limit_exhausted=node_limit_exhausted,
            candidate_cap_applied=False,
        )
        return StrictSearchOutcome(best, second, certificate, failure_code)

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        return outcome(
            {}, seed_count_returned=0, nodes=0, leaves=0,
            frontier_bound=None, termination_reason=SearchTimeout.code,
            certified=False, failure_code=SearchTimeout.code,
            runtime_budget_exhausted=True,
        )

    started = time.perf_counter()
    evaluated: dict[tuple[int, ...], Candidate] = {}
    seeds: list[LambdaIntegerCandidate] = []
    try:
        seeds = bridge.candidates(
            solution.ambiguity, solution.covariance_aa, initial_candidate_count
        )
        reduced = bridge.decorrelate(solution.ambiguity, solution.covariance_aa)
        for item in seeds:
            key = tuple(int(value) for value in item.ambiguity)
            evaluated[key] = evaluate_candidate(solution, item.ambiguity, length_m)
    except LambdaBridgeError:
        return outcome(
            evaluated, seed_count_returned=len(seeds), nodes=0, leaves=0,
            frontier_bound=None, termination_reason=NUMERICAL_FAILURE,
            certified=False, failure_code=LambdaBridgeError.code,
        )
    except (CLambdaError, np.linalg.LinAlgError):
        return outcome(
            evaluated, seed_count_returned=len(seeds), nodes=0, leaves=0,
            frontier_bound=None, termination_reason=NUMERICAL_FAILURE,
            certified=False, failure_code=NUMERICAL_FAILURE,
        )
    ordered = sorted(evaluated.values(), key=lambda item: (item.objective, tuple(item.ambiguity)))
    if len(ordered) < 2:
        return outcome(
            evaluated, seed_count_returned=len(seeds), nodes=0, leaves=0,
            frontier_bound=None, termination_reason=NO_FEASIBLE_MODEL,
            certified=False, failure_code=SearchIncomplete.code,
        )
    incumbent = float(ordered[1].objective)

    qbb = solution.covariance[-3:, -3:]
    qbz = solution.covariance_ba @ reduced.transformation

    def partial_objective_lower_bound(suffix: tuple[int, ...],
                                      ambiguity_bound: float) -> float:
        """P01 F1 lower bound after fixing a reduced-ambiguity suffix.

        The unfixed reduced ambiguities are relaxed to real values.  Gaussian
        conditioning then gives the exact conditional baseline centre and
        covariance for the fixed suffix.  Solving that three-dimensional
        sphere problem gives the exact continuous-relaxation lower bound for
        every integer descendant, rather than the weaker ordinary ambiguity
        metric alone.
        """
        count = len(suffix)
        if count == 0:
            center = solution.baseline
            covariance_b = qbb
        else:
            first = reduced.float_ambiguity.size - count
            indices = np.arange(first, reduced.float_ambiguity.size)
            qss = reduced.covariance[np.ix_(indices, indices)]
            qbs = qbz[:, indices]
            delta = np.asarray(suffix, dtype=float) - reduced.float_ambiguity[indices]
            solved_delta = np.linalg.solve(qss, delta)
            center = solution.baseline + qbs @ solved_delta
            covariance_b = qbb - qbs @ np.linalg.solve(qss, qbs.T)
        covariance_b = (covariance_b + covariance_b.T) * 0.5
        # With the remaining ambiguities relaxed to real values, this
        # three-dimensional sphere problem is the exact continuous-relaxation
        # contribution for the node (P01 search-and-shrink).  It is therefore
        # a valid descendant bound and substantially tighter than using only
        # the smallest eigenvalue inequality.
        sphere_bound = constrained_baseline(center, covariance_b, length_m).objective
        return float(ambiguity_bound + sphere_bound)

    # Qz^-1=R'R with R upper triangular.  Assign z from n-1 down to 0;
    # rows k..n-1 then form an exact suffix cost and a descendant lower bound.
    weight = np.linalg.inv(reduced.covariance)
    upper = np.linalg.cholesky(weight).T
    dimension = reduced.float_ambiguity.size
    frontier: list[tuple[float, int, int, tuple[int, ...], float]] = []
    serial = 0
    root_bound = partial_objective_lower_bound((), 0.0)
    heapq.heappush(frontier, (root_bound, serial, dimension - 1, (), 0.0))
    nodes = 0
    leaves = 0
    completion_bound: float | None = None
    tolerance = 1e-11

    while frontier:
        # Certification is a bound comparison, not an expanded tree node.
        completion_bound = float(frontier[0][0])
        if completion_bound + tolerance >= incumbent:
            return outcome(
                evaluated, seed_count_returned=len(seeds), nodes=nodes,
                leaves=leaves, frontier_bound=completion_bound,
                termination_reason=GLOBAL_BOUND_CERTIFIED, certified=True,
                failure_code=None,
            )
        if time.perf_counter() - started >= timeout_seconds:
            return outcome(
                evaluated, seed_count_returned=len(seeds), nodes=nodes,
                leaves=leaves, frontier_bound=completion_bound,
                termination_reason=SearchTimeout.code, certified=False,
                failure_code=SearchTimeout.code, runtime_budget_exhausted=True,
            )
        if node_limit is not None and nodes >= node_limit:
            return outcome(
                evaluated, seed_count_returned=len(seeds), nodes=nodes,
                leaves=leaves, frontier_bound=completion_bound,
                termination_reason=NUMERICAL_FAILURE, certified=False,
                failure_code=SearchIncomplete.code, node_limit_exhausted=True,
            )
        full_lower_bound, _, index, suffix, ambiguity_bound = heapq.heappop(frontier)
        nodes += 1
        completion_bound = float(full_lower_bound)
        if index < 0:
            leaves += 1
            reduced_integer = np.asarray(suffix, dtype=float)
            original = np.linalg.solve(reduced.transformation.T.astype(float), reduced_integer)
            integer = np.rint(original).astype(np.int64)
            if not np.allclose(original, integer, rtol=0.0, atol=1e-7):
                return outcome(
                    evaluated, seed_count_returned=len(seeds), nodes=nodes,
                    leaves=leaves, frontier_bound=completion_bound,
                    termination_reason=NUMERICAL_FAILURE, certified=False,
                    failure_code=LambdaBridgeError.code,
                )
            key = tuple(int(value) for value in integer)
            if key not in evaluated:
                candidate = evaluate_candidate(solution, integer, length_m)
                # Verify both the unimodular back-transform and the tree metric.
                if not math.isclose(candidate.ambiguity_objective, ambiguity_bound,
                                    rel_tol=2e-7, abs_tol=2e-7):
                    return outcome(
                        evaluated, seed_count_returned=len(seeds), nodes=nodes,
                        leaves=leaves, frontier_bound=completion_bound,
                        termination_reason=NUMERICAL_FAILURE, certified=False,
                        failure_code=LambdaBridgeError.code,
                    )
                evaluated[key] = candidate
                ordered = sorted(
                    evaluated.values(), key=lambda item: (item.objective, tuple(item.ambiguity))
                )
                incumbent = float(ordered[1].objective)
            continue

        assigned = np.asarray(suffix, dtype=float)
        if assigned.size:
            float_suffix = reduced.float_ambiguity[index + 1:]
            cross = float(upper[index, index + 1:] @ (float_suffix - assigned))
        else:
            cross = 0.0
        diagonal = float(upper[index, index])
        center = float(reduced.float_ambiguity[index] + cross / diagonal)
        radius = math.sqrt(max(0.0, incumbent - ambiguity_bound + tolerance)) / abs(diagonal)
        first = math.ceil(center - radius)
        last = math.floor(center + radius)
        schnorr_euchner = sorted(range(first, last + 1), key=lambda value: (abs(value - center), value))
        for integer_value in schnorr_euchner:
            row_residual = diagonal * (center - integer_value)
            child_ambiguity_bound = float(ambiguity_bound + row_residual * row_residual)
            if child_ambiguity_bound <= incumbent + tolerance:
                child_suffix = (integer_value,) + suffix
                child_bound = partial_objective_lower_bound(
                    child_suffix, child_ambiguity_bound
                )
            else:
                continue
            if child_bound <= incumbent + tolerance:
                serial += 1
                heapq.heappush(
                    frontier, (child_bound, serial, index - 1, child_suffix,
                               child_ambiguity_bound)
                )

    return outcome(
        evaluated, seed_count_returned=len(seeds), nodes=nodes, leaves=leaves,
        frontier_bound=math.inf, termination_reason=GLOBAL_BOUND_CERTIFIED,
        certified=True, failure_code=None,
    )


def solve_clambda(y: Sequence[float], ambiguity_design: np.ndarray,
                  baseline_design: np.ndarray, observation_covariance: np.ndarray,
                  length_m: float = 0.350, node_limit: int = 1_000_000, *,
                  lambda_bridge_path: str | Path | None = None,
                  strict: bool | None = None,
                  initial_candidate_count: int = 8,
                  strict_node_limit: int | None = None,
                  timeout_seconds: float = 1.0,
                  synthetic_max_dimension: int = 4) -> CLambdaResult:
    started = time.perf_counter()
    floating = joint_gls(y, ambiguity_design, baseline_design, observation_covariance)
    strict_mode = lambda_bridge_path is not None if strict is None else strict
    if strict_mode:
        if lambda_bridge_path is None:
            return CLambdaResult(None, None, None, False, False, 0, 0,
                                 time.perf_counter() - started, floating, "invalid",
                                 "LAMBDA_BRIDGE_UNAVAILABLE",
                                 termination_reason=NUMERICAL_FAILURE,
                                 configured_node_limit=strict_node_limit)
        try:
            bridge = RTKLIBLambdaBridge(lambda_bridge_path)
        except LambdaBridgeError:
            return CLambdaResult(None, None, None, False, False, 0, 0,
                                 time.perf_counter() - started, floating, "invalid",
                                 LambdaBridgeError.code,
                                 termination_reason=NUMERICAL_FAILURE,
                                 configured_node_limit=strict_node_limit)
        strict_outcome = search_strict_lambda(
            floating, bridge, length_m, initial_candidate_count,
            strict_node_limit, timeout_seconds,
        )
        certificate = strict_outcome.certificate
        if not certificate.global_optimum_certified:
            return CLambdaResult(
                None, None, None, False, False,
                certificate.branch_and_bound_nodes_expanded,
                certificate.unique_integer_candidates_evaluated,
                time.perf_counter() - started, floating, "invalid",
                strict_outcome.failure_code,
                certificate.frontier_lower_bound_at_termination,
                lambda_seed_count_requested=certificate.lambda_seed_count_requested,
                lambda_seed_count_returned=certificate.lambda_seed_count_returned,
                branch_and_bound_nodes_expanded=certificate.branch_and_bound_nodes_expanded,
                integer_leaves_evaluated=certificate.integer_leaves_evaluated,
                unique_integer_candidates_evaluated=(
                    certificate.unique_integer_candidates_evaluated
                ),
                frontier_lower_bound_at_termination=(
                    certificate.frontier_lower_bound_at_termination
                ),
                termination_reason=certificate.termination_reason,
                global_optimum_certified=False,
                runtime_budget_exhausted=certificate.runtime_budget_exhausted,
                configured_node_limit=certificate.configured_node_limit,
                node_limit_exhausted=certificate.node_limit_exhausted,
                candidate_cap_applied=certificate.candidate_cap_applied,
                best_total_objective=certificate.best_total_objective,
                second_total_objective=certificate.second_total_objective,
                integer_solution_returned=False,
                ambiguity_acceptance_test_defined=False,
                ambiguity_accepted=None,
            )
        best, second = strict_outcome.best, strict_outcome.second
        if best is None or second is None:
            raise CLambdaError("certified strict search did not return two candidates")
        nodes = certificate.branch_and_bound_nodes_expanded
        candidates = certificate.unique_integer_candidates_evaluated
        bound = certificate.frontier_lower_bound_at_termination
    else:
        if floating.ambiguity.size > synthetic_max_dimension:
            raise SearchIncomplete("finite enumeration is restricted to small synthetic tests")
        best, second, nodes, candidates = search_exact(floating, length_m, node_limit)
        bound = None
        certificate = SearchCertificate(
            lambda_seed_count_requested=0,
            lambda_seed_count_returned=0,
            branch_and_bound_nodes_expanded=nodes,
            integer_leaves_evaluated=candidates,
            unique_integer_candidates_evaluated=candidates,
            frontier_lower_bound_at_termination=None,
            best_total_objective=best.objective,
            second_total_objective=(None if second is None else second.objective),
            termination_reason=GLOBAL_BOUND_CERTIFIED,
            global_optimum_certified=True,
            runtime_budget_exhausted=False,
            configured_node_limit=node_limit,
            node_limit_exhausted=False,
            candidate_cap_applied=False,
        )
    ratio_valid = second is not None and best.objective > 0 and math.isfinite(second.objective)
    ratio = second.objective / best.objective if ratio_valid else None
    return CLambdaResult(
        best, second, ratio, ratio_valid, True, nodes, candidates,
        time.perf_counter() - started, floating, "fixed", None, bound,
        lambda_seed_count_requested=certificate.lambda_seed_count_requested,
        lambda_seed_count_returned=certificate.lambda_seed_count_returned,
        branch_and_bound_nodes_expanded=certificate.branch_and_bound_nodes_expanded,
        integer_leaves_evaluated=certificate.integer_leaves_evaluated,
        unique_integer_candidates_evaluated=(
            certificate.unique_integer_candidates_evaluated
        ),
        frontier_lower_bound_at_termination=(
            certificate.frontier_lower_bound_at_termination
        ),
        termination_reason=certificate.termination_reason,
        global_optimum_certified=certificate.global_optimum_certified,
        runtime_budget_exhausted=certificate.runtime_budget_exhausted,
        configured_node_limit=certificate.configured_node_limit,
        node_limit_exhausted=certificate.node_limit_exhausted,
        candidate_cap_applied=certificate.candidate_cap_applied,
        best_total_objective=certificate.best_total_objective,
        second_total_objective=certificate.second_total_objective,
        integer_solution_returned=True,
        ambiguity_acceptance_test_defined=False,
        ambiguity_accepted=None,
    )


def wrap_degrees(angle: float) -> float:
    return (float(angle) + 180.0) % 360.0 - 180.0


def body_yaw_from_ned_baseline(baseline_ned_m: Sequence[float]) -> float:
    baseline = np.asarray(baseline_ned_m, dtype=float)
    if baseline.shape != (3,) or np.any(~np.isfinite(baseline)):
        raise CLambdaError("baseline must be a finite NED vector")
    beta = math.degrees(math.atan2(baseline[1], baseline[0]))
    return wrap_degrees(beta + 90.0)


def wrap_safe_residual_degrees(measured: float, predicted: float) -> float:
    return wrap_degrees(measured - predicted)
