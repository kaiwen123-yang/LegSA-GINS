"""Wu et al. (2025) Section II-A constrained FAR/PAR heading module.

Only the paper's dual-antenna GNSS heading module, Eqs. (1)--(4), is
implemented here.  The accelerometer, GNSS/INS filter, and misalignment
compensation systems in Eqs. (5)--(24) are deliberately outside this API.

The exact constrained integer mathematics reuses the audited EXT01 strict
C-LAMBDA core.  The paper does not disclose a complete numerical PAR/QC
policy, so the deterministic policy objects below are explicitly identified
as ``PAPER_DERIVED_POLICY_BASELINE`` rather than paper-exact reproduction.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from typing import Mapping, Sequence

import numpy as np
from scipy.stats import chi2

from . import ext01_clambda as _ext01_core
from .ext01_clambda import (
    CLambdaError,
    Candidate,
    FloatSolution,
    GLOBAL_BOUND_CERTIFIED,
    RTKLIBLambdaBridge,
    SearchCertificate,
    conditional_float_baseline,
    joint_gls,
    search_exact,
    search_strict_lambda,
    wrap_degrees,
)


BASELINE_LENGTH_M = 0.350
POLICY_IDENTITY = "EXT04_PAR_DECLARED_POLICY_V1"
REPRODUCTION_LEVEL = "PAPER_DERIVED_POLICY_BASELINE"
FAR_POLICY_IDENTITY = "FAR_ALL_AMBIGUITIES"
RATIO_CONVENTION = "SECOND_OVER_BEST_GE_THRESHOLD"
SEARCH_BUDGET_CLOCK = "PARENT_PROCESS_CPU_TIME"


class Wu2025Error(ValueError):
    """Stable validation/numerical error for the isolated EXT04 core."""

    def __init__(self, message: str, *, code: str = "EXT04_NUMERICAL_FAILURE") -> None:
        super().__init__(message)
        self.code = code


class _ProcessCpuClock:
    """Clock proxy used only while the frozen EXT01 strict search executes.

    EXT01 remains byte-for-byte frozen.  Rebinding its module-local ``time``
    name avoids changing Python's process-wide time module while making a
    one-second search budget independent of other workers being descheduled.
    Every worker is single-threaded by the Phase-4 execution contract.
    """

    @staticmethod
    def perf_counter() -> float:
        return time.process_time()


def _strict_search_process_cpu_budget(
    floating: FloatSolution,
    bridge: RTKLIBLambdaBridge,
    baseline_length_m: float,
    timeout_seconds: float,
):
    original_clock = _ext01_core.time
    _ext01_core.time = _ProcessCpuClock
    try:
        return search_strict_lambda(
            floating, bridge, baseline_length_m,
            initial_candidate_count=8,
            node_limit=None,
            timeout_seconds=timeout_seconds,
        )
    finally:
        _ext01_core.time = original_clock


@dataclass(frozen=True, order=True)
class AmbiguityIdentity:
    constellation: str
    satellite: str
    frequency: str
    pivot: str
    receiver_order: str = "GNSS2_MINUS_GNSS1"

    def __post_init__(self) -> None:
        constellation = self.constellation.upper()
        if constellation not in {"GPS", "BDS"}:
            raise Wu2025Error("EXT04 ambiguity must belong to GPS or BDS")
        prefix = "G" if constellation == "GPS" else "C"
        if not self.satellite.startswith(prefix) or not self.pivot.startswith(prefix):
            raise Wu2025Error("cross-system ambiguity/pivot identity", code="CROSS_SYSTEM_DD_FORBIDDEN")
        if self.satellite == self.pivot or not self.frequency:
            raise Wu2025Error("incomplete DD ambiguity identity")
        if self.receiver_order != "GNSS2_MINUS_GNSS1":
            raise Wu2025Error("receiver order violates frozen physical contract")
        object.__setattr__(self, "constellation", constellation)

    @property
    def text(self) -> str:
        return (
            f"{self.constellation}:{self.satellite}:{self.frequency}:"
            f"pivot={self.pivot}:{self.receiver_order}"
        )


def _finite_vector(value: Sequence[float], size: int, *, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (size,) or np.any(~np.isfinite(result)):
        raise Wu2025Error(f"{name} must be a finite length-{size} vector")
    return np.array(result, copy=True)


def _positive_definite(value: Sequence[Sequence[float]], size: int, *, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (size, size) or np.any(~np.isfinite(result)):
        raise Wu2025Error(f"{name} must be a finite {size}-square matrix")
    scale = max(1.0, float(np.linalg.norm(result, ord=np.inf)))
    if np.max(np.abs(result - result.T)) > 128.0 * np.finfo(float).eps * scale:
        raise Wu2025Error(f"{name} must be symmetric")
    result = 0.5 * (result + result.T)
    try:
        np.linalg.cholesky(result)
    except np.linalg.LinAlgError as exc:
        raise Wu2025Error(f"{name} must be positive definite") from exc
    return np.array(result, copy=True)


@dataclass(frozen=True)
class DDObservationBlock:
    """One within-constellation/frequency DD block ordered code then phase."""

    constellation: str
    frequency: str
    pivot: str
    satellites: tuple[str, ...]
    wavelength_m: float
    los_ned: Mapping[str, Sequence[float]]
    code_dd_m: Sequence[float]
    phase_dd_m: Sequence[float]
    covariance_code_phase_m2: Sequence[Sequence[float]]
    minimum_two_receiver_cno_dbhz: Mapping[str, float]
    elevation_rad: Mapping[str, float]
    signal_identity: Mapping[str, str]
    receiver_order: str = "GNSS2_MINUS_GNSS1"

    def __post_init__(self) -> None:
        constellation = self.constellation.upper()
        if constellation not in {"GPS", "BDS"}:
            raise Wu2025Error("DD block must be GPS or BDS")
        prefix = "G" if constellation == "GPS" else "C"
        if not self.frequency or not self.pivot.startswith(prefix) or not self.satellites:
            raise Wu2025Error("DD block identity is incomplete")
        if len(set(self.satellites)) != len(self.satellites) or self.pivot in self.satellites:
            raise Wu2025Error("DD satellites must be unique non-pivots")
        if any(not satellite.startswith(prefix) for satellite in self.satellites):
            raise Wu2025Error("cross-system DD block", code="CROSS_SYSTEM_DD_FORBIDDEN")
        if self.receiver_order != "GNSS2_MINUS_GNSS1":
            raise Wu2025Error("receiver order violates frozen physical contract")
        if not math.isfinite(self.wavelength_m) or self.wavelength_m <= 0.0:
            raise Wu2025Error("wavelength must be positive")
        count = len(self.satellites)
        _finite_vector(self.code_dd_m, count, name="code DD")
        _finite_vector(self.phase_dd_m, count, name="phase DD")
        _positive_definite(self.covariance_code_phase_m2, 2 * count, name="DD covariance")
        for satellite in (self.pivot,) + tuple(self.satellites):
            los = _finite_vector(self.los_ned[satellite], 3, name=f"LOS {satellite}")
            if not math.isclose(float(np.linalg.norm(los)), 1.0, abs_tol=1e-10):
                raise Wu2025Error("LOS vector is not unit length")
        for satellite in self.satellites:
            cno = float(self.minimum_two_receiver_cno_dbhz[satellite])
            elevation = float(self.elevation_rad[satellite])
            if not math.isfinite(cno) or not math.isfinite(elevation):
                raise Wu2025Error("non-finite PAR quality input")
            if not self.signal_identity.get(satellite):
                raise Wu2025Error("missing explicit raw signal identity")
        object.__setattr__(self, "constellation", constellation)
        object.__setattr__(self, "satellites", tuple(self.satellites))


@dataclass(frozen=True)
class ObservationModel:
    """Paper Eq. (1) in EXT01's ``y=A*N+B*b+epsilon`` column order."""

    observation_m: np.ndarray
    ambiguity_design_m: np.ndarray
    baseline_design: np.ndarray
    covariance_m2: np.ndarray
    ambiguity_identities: tuple[AmbiguityIdentity, ...]
    minimum_two_receiver_cno_dbhz: np.ndarray
    elevation_rad: np.ndarray
    raw_signal_identities: tuple[str, ...]
    row_kinds: tuple[str, ...]
    row_ambiguity_indices: tuple[int, ...]
    source_ambiguity_indices: tuple[int, ...]
    block_identities: tuple[tuple[str, str, str], ...]

    @property
    def ambiguity_count(self) -> int:
        return len(self.ambiguity_identities)

    @property
    def code_row_count(self) -> int:
        return sum(kind == "CODE" for kind in self.row_kinds)

    @property
    def phase_row_count(self) -> int:
        return sum(kind == "PHASE" for kind in self.row_kinds)


def build_observation_model(blocks: Sequence[DDObservationBlock]) -> ObservationModel:
    """Build Eqs. (1)-(2), retaining full shared-pivot block covariance."""

    if not blocks:
        raise Wu2025Error("at least one DD block is required", code="NO_DD_BLOCK")
    keys = tuple((block.constellation, block.frequency) for block in blocks)
    if len(set(keys)) != len(keys):
        raise Wu2025Error("constellation/frequency DD block is duplicated")
    identities = tuple(
        AmbiguityIdentity(
            block.constellation, satellite, block.frequency, block.pivot,
            block.receiver_order,
        )
        for block in blocks for satellite in block.satellites
    )
    if len(set(identities)) != len(identities):
        raise Wu2025Error("ambiguity identities are not unique")
    ambiguity_index = {identity: index for index, identity in enumerate(identities)}
    row_count = sum(2 * len(block.satellites) for block in blocks)
    observation = np.empty(row_count, dtype=float)
    a_design = np.zeros((row_count, len(identities)), dtype=float)
    b_design = np.zeros((row_count, 3), dtype=float)
    covariance = np.zeros((row_count, row_count), dtype=float)
    cno = np.empty(len(identities), dtype=float)
    elevation = np.empty(len(identities), dtype=float)
    raw_signals: list[str | None] = [None] * len(identities)
    row_kinds: list[str] = []
    row_ambiguities: list[int] = []
    cursor = 0
    for block in blocks:
        count = len(block.satellites)
        block_slice = slice(cursor, cursor + 2 * count)
        observation[block_slice] = np.concatenate((
            _finite_vector(block.code_dd_m, count, name="code DD"),
            _finite_vector(block.phase_dd_m, count, name="phase DD"),
        ))
        pivot_los = np.asarray(block.los_ned[block.pivot], dtype=float)
        rows = np.asarray([
            -(np.asarray(block.los_ned[satellite], dtype=float) - pivot_los)
            for satellite in block.satellites
        ])
        b_design[cursor:cursor + count] = rows
        b_design[cursor + count:cursor + 2 * count] = rows
        for offset, satellite in enumerate(block.satellites):
            identity = AmbiguityIdentity(
                block.constellation, satellite, block.frequency, block.pivot,
                block.receiver_order,
            )
            index = ambiguity_index[identity]
            a_design[cursor + count + offset, index] = block.wavelength_m
            cno[index] = float(block.minimum_two_receiver_cno_dbhz[satellite])
            elevation[index] = float(block.elevation_rad[satellite])
            raw_signals[index] = str(block.signal_identity[satellite])
        covariance[block_slice, block_slice] = _positive_definite(
            block.covariance_code_phase_m2, 2 * count, name="DD covariance"
        )
        row_kinds.extend(["CODE"] * count)
        row_ambiguities.extend([-1] * count)
        row_kinds.extend(["PHASE"] * count)
        row_ambiguities.extend(
            ambiguity_index[AmbiguityIdentity(
                block.constellation, satellite, block.frequency, block.pivot,
                block.receiver_order,
            )]
            for satellite in block.satellites
        )
        cursor += 2 * count
    if any(item is None for item in raw_signals):
        raise Wu2025Error("raw signal identity alignment is incomplete")
    model = ObservationModel(
        observation,
        a_design,
        b_design,
        _positive_definite(covariance, row_count, name="stacked covariance"),
        identities,
        cno,
        elevation,
        tuple(str(item) for item in raw_signals),
        tuple(row_kinds),
        tuple(row_ambiguities),
        tuple(range(len(identities))),
        tuple((block.constellation, block.frequency, block.pivot) for block in blocks),
    )
    validate_model(model)
    return model


def validate_model(model: ObservationModel) -> None:
    m = model.ambiguity_count
    n = model.observation_m.size
    if m < 1 or model.ambiguity_design_m.shape != (n, m):
        raise Wu2025Error("observation/ambiguity dimensions are inconsistent")
    if model.baseline_design.shape != (n, 3) or model.covariance_m2.shape != (n, n):
        raise Wu2025Error("observation/baseline/covariance dimensions are inconsistent")
    if len(model.row_kinds) != n or len(model.row_ambiguity_indices) != n:
        raise Wu2025Error("row identity alignment is incomplete")
    if len(model.source_ambiguity_indices) != m or len(set(model.source_ambiguity_indices)) != m:
        raise Wu2025Error("source ambiguity identity alignment is incomplete")
    if any(index >= m for index in model.row_ambiguity_indices):
        raise Wu2025Error("phase row ambiguity alignment is invalid")
    _positive_definite(model.covariance_m2, n, name="observation covariance")


def subset_observation_model(
    model: ObservationModel,
    active_source_indices: Sequence[int],
) -> ObservationModel:
    """Rebuild the PAR float model after dropping non-active phase rows.

    All DD code rows remain available to the baseline.  A removed ambiguity's
    carrier row and ambiguity column are removed together, so no unmodelled
    float ambiguity is silently treated as a known integer.
    """

    active = tuple(int(index) for index in active_source_indices)
    if not active or len(set(active)) != len(active):
        raise Wu2025Error("active ambiguity subset must be unique and nonempty")
    source_to_local = {source: local for local, source in enumerate(model.source_ambiguity_indices)}
    if any(source not in source_to_local for source in active):
        raise Wu2025Error("active ambiguity source identity is unavailable")
    local_indices = tuple(source_to_local[source] for source in active)
    selected_rows = tuple(
        row for row, (kind, ambiguity) in enumerate(
            zip(model.row_kinds, model.row_ambiguity_indices)
        )
        if kind == "CODE" or (
            kind == "PHASE" and model.source_ambiguity_indices[ambiguity] in active
        )
    )
    a_design = np.zeros((len(selected_rows), len(active)), dtype=float)
    row_ambiguities: list[int] = []
    row_kinds: list[str] = []
    for new_row, old_row in enumerate(selected_rows):
        kind = model.row_kinds[old_row]
        old_ambiguity = model.row_ambiguity_indices[old_row]
        row_kinds.append(kind)
        if kind == "CODE":
            row_ambiguities.append(-1)
        else:
            source = model.source_ambiguity_indices[old_ambiguity]
            local = active.index(source)
            a_design[new_row, local] = model.ambiguity_design_m[old_row, old_ambiguity]
            row_ambiguities.append(local)
    rows = np.asarray(selected_rows, dtype=int)
    subset = ObservationModel(
        np.asarray(model.observation_m[rows], dtype=float),
        a_design,
        np.asarray(model.baseline_design[rows], dtype=float),
        np.asarray(model.covariance_m2[np.ix_(rows, rows)], dtype=float),
        tuple(model.ambiguity_identities[index] for index in local_indices),
        np.asarray(model.minimum_two_receiver_cno_dbhz[list(local_indices)], dtype=float),
        np.asarray(model.elevation_rad[list(local_indices)], dtype=float),
        tuple(model.raw_signal_identities[index] for index in local_indices),
        tuple(row_kinds),
        tuple(row_ambiguities),
        active,
        tuple(
            item for item in model.block_identities
            if any(
                identity.constellation == item[0] and identity.frequency == item[1]
                for identity in (model.ambiguity_identities[index] for index in local_indices)
            )
        ),
    )
    validate_model(subset)
    return subset


@dataclass(frozen=True)
class QualityMetrics:
    best_objective: float
    second_objective: float
    second_over_best: float
    best_over_second: float
    ratio_convention: str
    unconstrained_conditional_baseline_ned_m: np.ndarray
    unconstrained_conditional_baseline_norm_m: float
    baseline_validation_residual_m: float
    constrained_baseline_ned_m: np.ndarray
    constrained_baseline_length_m: float
    residual_vector_m: np.ndarray
    whitened_squared_residual: float
    degrees_of_freedom: int
    chi_square_p_value: float
    code_residual_rms_m: float
    phase_residual_rms_m: float
    ambiguity_dimension: int
    ambiguity_log_determinant: float
    adop_cycles: float


@dataclass(frozen=True)
class AmbiguityQuality:
    source_index: int
    identity: AmbiguityIdentity
    raw_signal_identity: str
    minimum_two_receiver_cno_dbhz: float
    satellite_elevation_rad: float
    marginal_float_variance_cycles2: float
    absolute_normalized_phase_residual: float

    @property
    def worst_first_key(self) -> tuple[float, float, float, float, str, str, str]:
        return (
            self.minimum_two_receiver_cno_dbhz,
            self.satellite_elevation_rad,
            -self.marginal_float_variance_cycles2,
            -self.absolute_normalized_phase_residual,
            self.identity.constellation,
            self.identity.satellite,
            self.raw_signal_identity,
        )


@dataclass(frozen=True)
class SubsetEvaluation:
    active_source_indices: tuple[int, ...]
    active_identities: tuple[AmbiguityIdentity, ...]
    removed_identities: tuple[AmbiguityIdentity, ...]
    float_solution: FloatSolution
    ambiguity_quality: tuple[AmbiguityQuality, ...]
    best: Candidate | None
    second: Candidate | None
    search_certificate: SearchCertificate
    quality_metrics: QualityMetrics | None
    failure_code: str | None
    runtime_seconds: float

    @property
    def search_certified(self) -> bool:
        return bool(
            self.search_certificate.global_optimum_certified
            and self.best is not None and self.second is not None
            and self.quality_metrics is not None
        )


def _ratio(best: float, second: float) -> tuple[float, float]:
    if best < 0.0 or second < best or not (math.isfinite(best) and math.isfinite(second)):
        raise Wu2025Error("constrained objective ordering is invalid")
    if best == 0.0:
        second_over_best = math.inf if second > 0.0 else 1.0
    else:
        second_over_best = second / best
    best_over_second = 1.0 if second == 0.0 else best / second
    return float(second_over_best), float(best_over_second)


def _ambiguity_quality(model: ObservationModel, floating: FloatSolution) -> tuple[AmbiguityQuality, ...]:
    residual = (
        model.observation_m
        - model.ambiguity_design_m @ floating.ambiguity
        - model.baseline_design @ floating.baseline
    )
    phase_residual_by_ambiguity: dict[int, float] = {}
    for row, (kind, ambiguity) in enumerate(zip(model.row_kinds, model.row_ambiguity_indices)):
        if kind == "PHASE":
            sigma = math.sqrt(float(model.covariance_m2[row, row]))
            phase_residual_by_ambiguity[ambiguity] = abs(float(residual[row])) / sigma
    if set(phase_residual_by_ambiguity) != set(range(model.ambiguity_count)):
        raise Wu2025Error("phase residual identity alignment is incomplete")
    return tuple(
        AmbiguityQuality(
            source_index=model.source_ambiguity_indices[index],
            identity=model.ambiguity_identities[index],
            raw_signal_identity=model.raw_signal_identities[index],
            minimum_two_receiver_cno_dbhz=float(model.minimum_two_receiver_cno_dbhz[index]),
            satellite_elevation_rad=float(model.elevation_rad[index]),
            marginal_float_variance_cycles2=float(floating.covariance_aa[index, index]),
            absolute_normalized_phase_residual=phase_residual_by_ambiguity[index],
        )
        for index in range(model.ambiguity_count)
    )


def _quality_metrics(
    model: ObservationModel,
    floating: FloatSolution,
    best: Candidate,
    second: Candidate,
    baseline_length_m: float,
) -> QualityMetrics:
    second_over_best, best_over_second = _ratio(best.objective, second.objective)
    # Paper Eq. (3): check-b(N) is the ordinary conditional fixed baseline.
    # Candidate.baseline is breve-b(N), its exact Q-weighted projection onto
    # the known ||b||=l sphere.  Keeping both prevents a tautological length
    # validation of the already constrained breve-b(N).
    unconstrained = conditional_float_baseline(floating, best.ambiguity)
    residual = (
        model.observation_m
        - model.ambiguity_design_m @ best.ambiguity
        - model.baseline_design @ best.baseline
    )
    cholesky = np.linalg.cholesky(model.covariance_m2)
    whitened = np.linalg.solve(cholesky, residual)
    statistic = float(whitened @ whitened)
    # Once the integer vector is fixed, the hard sphere leaves two continuous
    # baseline degrees of freedom.  Integer selection is not counted as a
    # fitted continuous parameter in this postfit chi-square diagnostic.
    degrees_of_freedom = int(model.observation_m.size - 2)
    if degrees_of_freedom <= 0:
        raise Wu2025Error("posterior residual degrees of freedom are non-positive")
    code = np.asarray([
        residual[index] for index, kind in enumerate(model.row_kinds) if kind == "CODE"
    ])
    phase = np.asarray([
        residual[index] for index, kind in enumerate(model.row_kinds) if kind == "PHASE"
    ])
    sign, logdet = np.linalg.slogdet(floating.covariance_aa)
    if sign <= 0 or not math.isfinite(float(logdet)):
        raise Wu2025Error("ambiguity covariance log determinant is invalid")
    ambiguity_dimension = model.ambiguity_count
    adop = math.exp(float(logdet) / (2.0 * ambiguity_dimension))
    return QualityMetrics(
        best_objective=float(best.objective),
        second_objective=float(second.objective),
        second_over_best=second_over_best,
        best_over_second=best_over_second,
        ratio_convention=RATIO_CONVENTION,
        unconstrained_conditional_baseline_ned_m=np.asarray(unconstrained, dtype=float),
        unconstrained_conditional_baseline_norm_m=float(np.linalg.norm(unconstrained)),
        baseline_validation_residual_m=float(np.linalg.norm(unconstrained) - baseline_length_m),
        constrained_baseline_ned_m=np.asarray(best.baseline, dtype=float),
        constrained_baseline_length_m=float(np.linalg.norm(best.baseline)),
        residual_vector_m=np.asarray(residual, dtype=float),
        whitened_squared_residual=statistic,
        degrees_of_freedom=degrees_of_freedom,
        chi_square_p_value=float(chi2.sf(statistic, degrees_of_freedom)),
        code_residual_rms_m=float(np.sqrt(np.mean(code * code))),
        phase_residual_rms_m=float(np.sqrt(np.mean(phase * phase))),
        ambiguity_dimension=ambiguity_dimension,
        ambiguity_log_determinant=float(logdet),
        adop_cycles=float(adop),
    )


def evaluate_subset(
    full_model: ObservationModel,
    active_source_indices: Sequence[int],
    *,
    bridge: RTKLIBLambdaBridge | None,
    baseline_length_m: float = BASELINE_LENGTH_M,
    timeout_seconds: float = 1.0,
    strict: bool = True,
) -> SubsetEvaluation:
    """Fit one active ambiguity subset and run the complete Eq. (3) search."""

    active = tuple(int(item) for item in active_source_indices)
    model = subset_observation_model(full_model, active)
    started = time.perf_counter()
    try:
        floating = joint_gls(
            model.observation_m, model.ambiguity_design_m,
            model.baseline_design, model.covariance_m2,
        )
    except (CLambdaError, np.linalg.LinAlgError) as exc:
        raise Wu2025Error(str(exc), code="FLOAT_GLS_FAILURE") from exc
    quality = _ambiguity_quality(model, floating)
    all_sources = tuple(full_model.source_ambiguity_indices)
    removed = tuple(
        full_model.ambiguity_identities[all_sources.index(source)]
        for source in all_sources if source not in active
    )
    if strict:
        if bridge is None:
            raise Wu2025Error("strict search requires RTKLIB bridge", code="LAMBDA_BRIDGE_UNAVAILABLE")
        outcome = _strict_search_process_cpu_budget(
            floating, bridge, baseline_length_m, timeout_seconds,
        )
        best, second, certificate = outcome.best, outcome.second, outcome.certificate
        failure_code = outcome.failure_code
    else:
        if model.ambiguity_count > 4:
            raise Wu2025Error("brute-force oracle is limited to four ambiguities")
        try:
            best, second, nodes, leaves = search_exact(
                floating, baseline_length_m, node_limit=1_000_000,
            )
            certificate = SearchCertificate(
                lambda_seed_count_requested=0,
                lambda_seed_count_returned=0,
                branch_and_bound_nodes_expanded=nodes,
                integer_leaves_evaluated=leaves,
                unique_integer_candidates_evaluated=leaves,
                frontier_lower_bound_at_termination=None,
                best_total_objective=float(best.objective),
                second_total_objective=None if second is None else float(second.objective),
                termination_reason=GLOBAL_BOUND_CERTIFIED,
                global_optimum_certified=True,
                runtime_budget_exhausted=False,
                configured_node_limit=1_000_000,
                node_limit_exhausted=False,
                candidate_cap_applied=False,
            )
            failure_code = None
        except (CLambdaError, np.linalg.LinAlgError) as exc:
            raise Wu2025Error(str(exc), code="STRICT_SEARCH_FAILURE") from exc
    metrics = None
    if certificate.global_optimum_certified and best is not None and second is not None:
        metrics = _quality_metrics(model, floating, best, second, baseline_length_m)
    return SubsetEvaluation(
        active,
        model.ambiguity_identities,
        removed,
        floating,
        quality,
        best,
        second,
        certificate,
        metrics,
        failure_code,
        time.perf_counter() - started,
    )


def deterministic_removal_order(evaluation: SubsetEvaluation) -> tuple[AmbiguityQuality, ...]:
    """Return the declared lexicographic worst-to-best ordering."""

    return tuple(sorted(evaluation.ambiguity_quality, key=lambda item: item.worst_first_key))


def _subset_is_structurally_valid(model: ObservationModel, active: Sequence[int]) -> bool:
    if len(active) < 3:
        return False
    try:
        subset = subset_observation_model(model, active)
    except Wu2025Error:
        return False
    if np.linalg.matrix_rank(subset.baseline_design) < 3:
        return False
    if not subset.block_identities:
        return False
    design = np.column_stack((subset.ambiguity_design_m, subset.baseline_design))
    try:
        whitened = np.linalg.solve(np.linalg.cholesky(subset.covariance_m2), design)
    except np.linalg.LinAlgError:
        return False
    return int(np.linalg.matrix_rank(whitened)) == design.shape[1]


def build_search_chain(
    model: ObservationModel,
    *,
    bridge: RTKLIBLambdaBridge | None,
    baseline_length_m: float = BASELINE_LENGTH_M,
    timeout_seconds: float = 1.0,
    strict: bool = True,
) -> tuple[SubsetEvaluation, ...]:
    """Evaluate FAR then remove one declared worst ambiguity at a time."""

    active = tuple(model.source_ambiguity_indices)
    if not _subset_is_structurally_valid(model, active):
        raise Wu2025Error("FAR model lacks rank-three identifiable geometry", code="FLOAT_MODEL_RANK_DEFICIENT")
    chain: list[SubsetEvaluation] = []
    while True:
        evaluation = evaluate_subset(
            model, active, bridge=bridge, baseline_length_m=baseline_length_m,
            timeout_seconds=timeout_seconds, strict=strict,
        )
        chain.append(evaluation)
        if len(active) <= 3:
            break
        next_active: tuple[int, ...] | None = None
        for candidate in deterministic_removal_order(evaluation):
            proposed = tuple(index for index in active if index != candidate.source_index)
            if _subset_is_structurally_valid(model, proposed):
                next_active = proposed
                break
        if next_active is None:
            break
        active = next_active
    return tuple(chain)


@dataclass(frozen=True)
class PolicyParameters:
    policy_identity: str
    ratio_threshold: float = 3.0
    baseline_tolerance_m: float = 0.050
    posterior_alpha: float = 0.01
    adop_threshold_cycles: float = 0.12
    reproduction_level: str = REPRODUCTION_LEVEL
    primary_or_sensitivity: str = "PRIMARY"
    changed_parameter: str = "NONE"

    def __post_init__(self) -> None:
        values = (
            self.ratio_threshold, self.baseline_tolerance_m,
            self.posterior_alpha, self.adop_threshold_cycles,
        )
        if any(not math.isfinite(item) or item <= 0.0 for item in values):
            raise Wu2025Error("policy thresholds must be finite and positive")
        if self.posterior_alpha >= 1.0:
            raise Wu2025Error("posterior alpha must be below one")


PRIMARY_POLICY = PolicyParameters(POLICY_IDENTITY)
SENSITIVITY_POLICIES = (
    PolicyParameters(f"{POLICY_IDENTITY}_RATIO_2P0", ratio_threshold=2.0,
                     primary_or_sensitivity="SENSITIVITY", changed_parameter="ratio"),
    PolicyParameters(f"{POLICY_IDENTITY}_RATIO_5P0", ratio_threshold=5.0,
                     primary_or_sensitivity="SENSITIVITY", changed_parameter="ratio"),
    PolicyParameters(f"{POLICY_IDENTITY}_BASELINE_0P020M", baseline_tolerance_m=0.020,
                     primary_or_sensitivity="SENSITIVITY", changed_parameter="baseline_tolerance"),
    PolicyParameters(f"{POLICY_IDENTITY}_BASELINE_0P100M", baseline_tolerance_m=0.100,
                     primary_or_sensitivity="SENSITIVITY", changed_parameter="baseline_tolerance"),
    PolicyParameters(f"{POLICY_IDENTITY}_POSTERIOR_ALPHA_0P001", posterior_alpha=0.001,
                     primary_or_sensitivity="SENSITIVITY", changed_parameter="posterior_alpha"),
    PolicyParameters(f"{POLICY_IDENTITY}_ADOP_0P10", adop_threshold_cycles=0.10,
                     primary_or_sensitivity="SENSITIVITY", changed_parameter="ADOP"),
    PolicyParameters(f"{POLICY_IDENTITY}_ADOP_0P15", adop_threshold_cycles=0.15,
                     primary_or_sensitivity="SENSITIVITY", changed_parameter="ADOP"),
)


@dataclass(frozen=True)
class GateResult:
    objective_equivalence_pass: bool
    baseline_validation_pass: bool
    posterior_residual_pass: bool
    adop_pass: bool
    accepted: bool


def evaluate_gates(evaluation: SubsetEvaluation, policy: PolicyParameters) -> GateResult:
    metrics = evaluation.quality_metrics
    if not evaluation.search_certified or metrics is None:
        return GateResult(False, False, False, False, False)
    ratio = bool(metrics.second_over_best >= policy.ratio_threshold)
    baseline = bool(abs(metrics.baseline_validation_residual_m) <= policy.baseline_tolerance_m)
    posterior = bool(metrics.chi_square_p_value >= policy.posterior_alpha)
    adop = bool(metrics.adop_cycles <= policy.adop_threshold_cycles)
    return GateResult(ratio, baseline, posterior, adop, ratio and baseline and posterior and adop)


@dataclass(frozen=True)
class PolicyDecision:
    policy: PolicyParameters
    solution_state: str
    selected: SubsetEvaluation
    gates: GateResult
    ambiguity_correctness_known: bool = False

    @property
    def accepted(self) -> bool:
        return self.solution_state in {"FAR_ACCEPTED", "PAR_ACCEPTED"}


def decide_far(chain: Sequence[SubsetEvaluation], policy: PolicyParameters = PRIMARY_POLICY) -> PolicyDecision:
    if not chain:
        raise Wu2025Error("FAR decision requires a search chain")
    evaluation = chain[0]
    gates = evaluate_gates(evaluation, policy)
    if not evaluation.search_certified:
        state = "INVALID"
    else:
        state = "FAR_ACCEPTED" if gates.accepted else "FAR_REJECTED"
    far_policy = replace(
        policy, policy_identity=FAR_POLICY_IDENTITY,
        reproduction_level="FAITHFUL_MODULE_MATHEMATICAL_CORE_WITH_DECLARED_QC_GATES",
        primary_or_sensitivity="FAR",
    )
    return PolicyDecision(far_policy, state, evaluation, gates)


def decide_par(chain: Sequence[SubsetEvaluation], policy: PolicyParameters) -> PolicyDecision:
    if not chain:
        raise Wu2025Error("PAR decision requires a search chain")
    last_certified: tuple[SubsetEvaluation, GateResult] | None = None
    for index, evaluation in enumerate(chain):
        gates = evaluate_gates(evaluation, policy)
        if evaluation.search_certified:
            last_certified = evaluation, gates
        if gates.accepted:
            return PolicyDecision(
                policy,
                "FAR_ACCEPTED" if index == 0 else "PAR_ACCEPTED",
                evaluation,
                gates,
            )
    if last_certified is None:
        gates = evaluate_gates(chain[-1], policy)
        return PolicyDecision(policy, "INVALID", chain[-1], gates)
    evaluation, gates = last_certified
    return PolicyDecision(policy, "PAR_EXHAUSTED", evaluation, gates)


def all_policy_decisions(chain: Sequence[SubsetEvaluation]) -> tuple[PolicyDecision, ...]:
    """Return FAR, declared primary PAR, then seven OAT sensitivities."""

    return (
        decide_far(chain, PRIMARY_POLICY),
        decide_par(chain, PRIMARY_POLICY),
        *(decide_par(chain, policy) for policy in SENSITIVITY_POLICIES),
    )


@dataclass(frozen=True)
class AttitudeSolution:
    baseline_yaw_deg: float
    body_yaw_deg: float
    pitch_deg: float


def attitude_from_ned_baseline(baseline_ned_m: Sequence[float]) -> AttitudeSolution:
    """Paper Eq. (4), followed by the frozen BY2 lateral +90-degree map."""

    baseline = _finite_vector(baseline_ned_m, 3, name="NED baseline")
    north, east, down = map(float, baseline)
    horizontal = math.hypot(north, east)
    if horizontal == 0.0:
        raise Wu2025Error("vertical baseline has undefined yaw")
    yaw = wrap_degrees(math.degrees(math.atan2(east, north)))
    pitch = math.degrees(math.atan2(-down, horizontal))
    return AttitudeSolution(yaw, wrap_degrees(yaw + 90.0), pitch)


EQUATION_CODE_MAP = {
    "Eq. (1)": "DDObservationBlock and build_observation_model",
    "Eq. (2)": "ObservationModel covariance/domain validation and exact baseline sphere",
    "Eq. (3)": "EXT01 joint_gls/search_strict_lambda via evaluate_subset/build_search_chain",
    "Eq. (4)": "attitude_from_ned_baseline",
    "FAR": "decide_far",
    "PAR": "deterministic_removal_order/build_search_chain/decide_par",
    "QC": "_quality_metrics/evaluate_gates",
}
