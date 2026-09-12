"""Single-baseline constrained wrapped least squares (C-WLS).

This is a clean-room implementation of the mathematical specification in
Liu et al., *IEEE Transactions on Instrumentation and Measurement*, 2022,
DOI 10.1109/TIM.2022.3193412 (arXiv:2112.14813).  The equation map is:

* :func:`build_double_difference_design` implements (5)--(8);
* :class:`SingleBaselineCWLSModel` stores the single-baseline form (54)--(56);
* :func:`integer_ambiguity_interval` and :func:`build_search_circles`
  implement (57)--(61), including the exact inclusive bounds in (58);
* :func:`intersect_sphere_circles` implements the full-sphere geometry of
  Algorithm 1 and (62)--(72), with the paper's ``delta_Delta = 0.05``;
* :func:`wrapped_objective` is the original objective (54)/(73); and
* :func:`solve_single_baseline_cwls` implements Algorithm 2 and (74)--(75).

All observations and design rows are expressed in carrier cycles.  Stacked
vectors and covariances are always ordered ``[phase, code]``.  In particular,
``design_cycles_per_m`` is one S-by-3 copy of H from (8), in cycles/metre;
the implementation duplicates it internally for the phase and code blocks.
The supplied sign of H is authoritative and is never selected or changed.

Unlike the paper's optional best-K heuristic, the Phase 2 contract requires
every unique Algorithm-1 candidate to be refined.  Deduplication therefore
uses only a small multiple of binary64 machine precision and no scientific
or metric-derived tolerance.  A solution is returned only when that complete
unique-candidate pool converges with finite objectives; candidate-local errors
are recorded, the remaining candidates are still attempted, and the epoch is
then rejected.  No trace/reference-pose input is accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

DELTA_DELTA = 0.05
REFINEMENT_TOL = 1.0e-10
REFINEMENT_MAX_ITERATIONS = 20

_EPS = np.finfo(np.float64).eps
_GEOMETRY_EPS = 64.0 * _EPS
_DEDUP_EPS = 32.0 * _EPS


class CWLSError(ValueError):
    """Base exception for malformed inputs or an unusable C-WLS problem."""

    def __init__(self, message: str, *, code: str = "NUMERICAL_FAILURE") -> None:
        super().__init__(message)
        self.code = code


class CWLSGeometryError(CWLSError):
    """Raised when Algorithm 1 cannot produce a finite direction candidate."""


class CWLSNumericalError(CWLSError):
    """Raised when a numerical subproblem cannot be globally certified."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "NUMERICAL_FAILURE",
        candidate_diagnostics: tuple[object, ...] = (),
        candidate_pool: object | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.candidate_diagnostics = candidate_diagnostics
        self.candidate_pool = candidate_pool


def _readonly_float_array(value: ArrayLike, shape: tuple[int, ...] | None = None) -> FloatArray:
    array = np.array(value, dtype=np.float64, copy=True)
    if shape is not None and array.shape != shape:
        raise CWLSError(f"expected shape {shape}, got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise CWLSError("all numeric inputs must be finite")
    array.setflags(write=False)
    return array


def _as_scalar_or_array(original: ArrayLike, value: np.ndarray) -> float | int | np.ndarray:
    if np.asarray(original).ndim == 0:
        return value.reshape(()).item()
    return value


def round_half_down(value: ArrayLike) -> int | IntArray:
    """Apply the paper's special rounding rule exactly.

    The definition is ``ceil(x - 0.5)``.  Thus every half-integer ``n + 0.5``
    maps to ``n`` rather than using NumPy/Python's ties-to-even convention.
    This is the rounding operation in (24) and (75).
    """

    original = np.asarray(value)
    numeric = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(numeric)):
        raise CWLSError("rounding input must be finite")
    rounded = np.ceil(numeric - 0.5).astype(np.int64)
    return _as_scalar_or_array(original, rounded)  # type: ignore[return-value]


def wrap_half_cycles(value: ArrayLike) -> float | FloatArray:
    """Wrap cycles into the exact half-open interval ``(-0.5, 0.5]``.

    This is ``x - round_half_down(x)`` from (26), including ``wrap(-0.5) =
    wrap(+0.5) = +0.5``.
    """

    original = np.asarray(value)
    numeric = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(numeric)):
        raise CWLSError("wrapping input must be finite")
    wrapped = numeric - np.asarray(round_half_down(numeric), dtype=np.float64)
    return _as_scalar_or_array(original, wrapped)  # type: ignore[return-value]


def stack_phase_code(phase_cycles: ArrayLike, code_cycles: ArrayLike) -> FloatArray:
    """Stack equal-length observation blocks in the required ``[phase, code]`` order."""

    phase = np.asarray(phase_cycles, dtype=np.float64)
    code = np.asarray(code_cycles, dtype=np.float64)
    if phase.ndim != 1 or code.shape != phase.shape:
        raise CWLSError("phase and code must be equal-length one-dimensional arrays")
    if not np.all(np.isfinite(phase)) or not np.all(np.isfinite(code)):
        raise CWLSError("phase and code must be finite")
    return np.concatenate((phase, code)).astype(np.float64, copy=False)


@dataclass(frozen=True)
class DoubleDifferenceDesign:
    """Paper (5)--(8) H matrix and the satellite/pivot ordering used to build it."""

    design_cycles_per_m: FloatArray
    pivot_index: int
    satellite_indices: tuple[int, ...]
    wavelength_m: float


def build_double_difference_design(
    los_unit_vectors: ArrayLike,
    pivot_index: int,
    wavelength_m: float,
) -> DoubleDifferenceDesign:
    """Build H = ``(h_sat - h_pivot)^T / wavelength`` from paper (5)--(8).

    Input LOS rows must already use one common reference frame and must be unit
    vectors.  Non-pivot rows retain their input order.  This helper implements
    the paper sign; callers adapting a frozen backend should instead pass that
    backend's authoritative H directly to :class:`SingleBaselineCWLSModel`.
    """

    los = np.asarray(los_unit_vectors, dtype=np.float64)
    if los.ndim != 2 or los.shape[1] != 3 or los.shape[0] < 3:
        raise CWLSError("los_unit_vectors must have shape (satellites >= 3, 3)")
    if not np.all(np.isfinite(los)):
        raise CWLSError("LOS vectors must be finite")
    if not isinstance(pivot_index, (int, np.integer)) or not 0 <= int(pivot_index) < los.shape[0]:
        raise CWLSError("pivot_index is out of range")
    if not np.isfinite(wavelength_m) or wavelength_m <= 0.0:
        raise CWLSError("wavelength_m must be positive and finite")
    norms = np.linalg.norm(los, axis=1)
    unit_tolerance = 128.0 * _EPS
    if np.any(np.abs(norms - 1.0) > unit_tolerance):
        raise CWLSError("LOS rows must be unit vectors")
    pivot = int(pivot_index)
    indices = tuple(index for index in range(los.shape[0]) if index != pivot)
    design = (los[np.asarray(indices)] - los[pivot]) / float(wavelength_m)
    design = _readonly_float_array(design)
    return DoubleDifferenceDesign(design, pivot, indices, float(wavelength_m))


@dataclass(frozen=True)
class SingleBaselineCWLSModel:
    """Single-baseline C-WLS inputs for (54), in carrier-cycle units.

    ``phase_cycles`` and ``code_cycles`` each have S entries.
    ``design_cycles_per_m`` is S-by-3 and retains the caller's physical sign.
    ``covariance_phase_code_cycles2`` is the complete 2S-by-2S covariance in
    ``[phase, code]`` order.  It may contain non-diagonal phase, code, and
    cross-block terms, but must be symmetric positive definite.
    """

    phase_cycles: FloatArray
    code_cycles: FloatArray
    design_cycles_per_m: FloatArray
    covariance_phase_code_cycles2: FloatArray
    baseline_length_m: float
    _precision: FloatArray = field(init=False, repr=False, compare=False)
    _stacked_design: FloatArray = field(init=False, repr=False, compare=False)
    _quadratic_matrix: FloatArray = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        phase = np.asarray(self.phase_cycles, dtype=np.float64)
        if phase.ndim != 1 or phase.size < 2:
            raise CWLSError("at least two double-difference observations are required")
        count = int(phase.size)
        phase = _readonly_float_array(phase, (count,))
        code = _readonly_float_array(self.code_cycles, (count,))
        design = _readonly_float_array(self.design_cycles_per_m, (count, 3))
        covariance = _readonly_float_array(
            self.covariance_phase_code_cycles2, (2 * count, 2 * count)
        )
        if not np.isfinite(self.baseline_length_m) or self.baseline_length_m <= 0.0:
            raise CWLSError("baseline_length_m must be positive and finite")
        if np.any(np.linalg.norm(design, axis=1) == 0.0):
            raise CWLSError("every H row must have nonzero norm")
        symmetry_scale = max(1.0, float(np.linalg.norm(covariance, ord=np.inf)))
        if np.max(np.abs(covariance - covariance.T)) > 64.0 * _EPS * symmetry_scale:
            raise CWLSError("covariance must be symmetric")
        covariance = _readonly_float_array(0.5 * (covariance + covariance.T))
        try:
            np.linalg.cholesky(covariance)
        except np.linalg.LinAlgError as exc:
            raise CWLSError("covariance must be positive definite") from exc
        precision = np.linalg.solve(covariance, np.eye(2 * count, dtype=np.float64))
        precision = 0.5 * (precision + precision.T)
        repeated_h = float(self.baseline_length_m) * np.vstack((design, design))
        quadratic = repeated_h.T @ precision @ repeated_h
        quadratic = 0.5 * (quadratic + quadratic.T)

        object.__setattr__(self, "phase_cycles", phase)
        object.__setattr__(self, "code_cycles", code)
        object.__setattr__(self, "design_cycles_per_m", design)
        object.__setattr__(self, "covariance_phase_code_cycles2", covariance)
        object.__setattr__(self, "baseline_length_m", float(self.baseline_length_m))
        object.__setattr__(self, "_precision", _readonly_float_array(precision))
        object.__setattr__(self, "_stacked_design", _readonly_float_array(repeated_h))
        object.__setattr__(self, "_quadratic_matrix", _readonly_float_array(quadratic))

    @property
    def observation_count(self) -> int:
        return int(self.phase_cycles.size)


def adapt_metric_double_differences(
    *,
    code_m: ArrayLike,
    phase_m: ArrayLike,
    design_m_per_m: ArrayLike,
    covariance_code_phase_m2: ArrayLike,
    wavelength_m: float,
    baseline_length_m: float,
) -> SingleBaselineCWLSModel:
    """Adapt a metric ``[code, phase]`` backend to the paper's cycle model.

    Observations and H are divided by ``wavelength_m`` and covariance by its
    square.  The covariance is permuted from backend ``[code, phase]`` order to
    required ``[phase, code]`` order, retaining *all* off-diagonal entries.
    ``design_m_per_m`` may be S-by-3 or a duplicated 2S-by-3 ``[code, phase]``
    design; duplicated blocks must agree to binary64 roundoff.  No sign change
    is performed.
    """

    code = np.asarray(code_m, dtype=np.float64)
    phase = np.asarray(phase_m, dtype=np.float64)
    if code.ndim != 1 or phase.shape != code.shape:
        raise CWLSError("metric code and phase must be equal-length vectors")
    count = int(code.size)
    design = np.asarray(design_m_per_m, dtype=np.float64)
    if design.shape == (2 * count, 3):
        scale = max(1.0, float(np.linalg.norm(design, ord=np.inf)))
        if np.max(np.abs(design[:count] - design[count:])) > 64.0 * _EPS * scale:
            raise CWLSError("duplicated code/phase design blocks do not agree")
        design = design[:count]
    elif design.shape != (count, 3):
        raise CWLSError("design_m_per_m must have shape (S,3) or (2S,3)")
    covariance = np.asarray(covariance_code_phase_m2, dtype=np.float64)
    if covariance.shape != (2 * count, 2 * count):
        raise CWLSError("metric covariance must have shape (2S,2S)")
    if not np.isfinite(wavelength_m) or wavelength_m <= 0.0:
        raise CWLSError("wavelength_m must be positive and finite")
    permutation = np.concatenate((np.arange(count, 2 * count), np.arange(count)))
    covariance_phase_code = covariance[np.ix_(permutation, permutation)] / wavelength_m**2
    return SingleBaselineCWLSModel(
        phase_cycles=phase / wavelength_m,
        code_cycles=code / wavelength_m,
        design_cycles_per_m=design / wavelength_m,
        covariance_phase_code_cycles2=covariance_phase_code,
        baseline_length_m=baseline_length_m,
    )


@dataclass(frozen=True, order=True)
class IntegerInterval:
    """Inclusive integer interval dictated exactly by paper (58)."""

    lower: int
    upper: int

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise CWLSError("integer interval cannot be empty")

    def values(self) -> range:
        return range(self.lower, self.upper + 1)

    def __len__(self) -> int:
        return self.upper - self.lower + 1


def integer_ambiguity_interval(
    phase_cycle: float,
    design_row_cycles_per_m: ArrayLike,
    baseline_length_m: float,
) -> IntegerInterval:
    """Return all integers N satisfying (58), with exact inclusive endpoints."""

    row = np.asarray(design_row_cycles_per_m, dtype=np.float64)
    if row.shape != (3,) or not np.all(np.isfinite(row)):
        raise CWLSError("design row must be a finite three-vector")
    if not np.isfinite(phase_cycle) or not np.isfinite(baseline_length_m):
        raise CWLSError("phase and baseline length must be finite")
    if baseline_length_m <= 0.0 or np.linalg.norm(row) == 0.0:
        raise CWLSError("baseline length and design-row norm must be positive")
    span = float(baseline_length_m) * float(np.linalg.norm(row))
    lower = int(np.ceil(float(phase_cycle) - span))
    upper = int(np.floor(float(phase_cycle) + span))
    if lower > upper:
        # Mathematically impossible for a physically admissible phase, but the
        # explicit failure makes malformed/unit-mismatched inputs visible.
        raise CWLSGeometryError(
            "Eq. (58) yields an empty ambiguity interval",
            code="NO_VALID_INTEGER_INTERVAL",
        )
    return IntegerInterval(lower, upper)


@dataclass(frozen=True)
class SphereCircle:
    """A full-sphere small circle ``normal dot r = offset``, ``||r|| = 1``.

    ``normal`` is unit length.  ``offset = cos(theta)`` follows (57), and the
    center/radius properties correspond to (63).  Radius zero is an explicit
    degenerate point circle rather than a planar or hemisphere approximation.
    """

    normal: FloatArray
    offset: float
    observation_index: int = -1
    ambiguity: int = 0

    def __post_init__(self) -> None:
        normal = _readonly_float_array(self.normal, (3,))
        norm = float(np.linalg.norm(normal))
        if norm == 0.0:
            raise CWLSGeometryError("circle normal cannot be zero")
        normal = normal / norm
        offset = float(self.offset) / norm
        bound_tolerance = _GEOMETRY_EPS * max(1.0, abs(offset))
        if offset < -1.0 - bound_tolerance or offset > 1.0 + bound_tolerance:
            raise CWLSGeometryError("circle offset lies outside the unit sphere")
        offset = float(np.clip(offset, -1.0, 1.0))
        object.__setattr__(self, "normal", _readonly_float_array(normal))
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "observation_index", int(self.observation_index))
        object.__setattr__(self, "ambiguity", int(self.ambiguity))

    @property
    def center(self) -> FloatArray:
        return self.offset * self.normal

    @property
    def radius(self) -> float:
        return float(np.sqrt(max(0.0, 1.0 - self.offset**2)))

    @property
    def is_point(self) -> bool:
        return self.radius <= _GEOMETRY_EPS


def build_search_circles(model: SingleBaselineCWLSModel) -> tuple[SphereCircle, ...]:
    """Enumerate every (57)--(58) circle for every phase observation."""

    circles: list[SphereCircle] = []
    for index, (phase, row) in enumerate(
        zip(model.phase_cycles, model.design_cycles_per_m, strict=True)
    ):
        row_norm = float(np.linalg.norm(row))
        interval = integer_ambiguity_interval(phase, row, model.baseline_length_m)
        for ambiguity in interval.values():
            offset = (float(phase) - ambiguity) / (model.baseline_length_m * row_norm)
            circles.append(SphereCircle(row / row_norm, offset, index, ambiguity))
    return tuple(circles)


@dataclass(frozen=True)
class CirclePairGeometry:
    """Algorithm-1 result and diagnostics for one pair of sphere circles."""

    kind: str
    candidates: tuple[FloatArray, ...]
    delta_1: float | None
    delta_2: float | None
    parallel_relation: str | None = None


def _canonical_unit(direction: ArrayLike) -> FloatArray:
    vector = np.asarray(direction, dtype=np.float64)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise CWLSGeometryError("direction candidate must be a finite three-vector")
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise CWLSGeometryError("direction candidate cannot be zero")
    result = np.array(vector / norm, dtype=np.float64, copy=True)
    result[result == 0.0] = 0.0  # canonicalize negative zero only
    result.setflags(write=False)
    return result


def _point_circle_geometry(point_circle: SphereCircle, other: SphereCircle) -> CirclePairGeometry:
    point = _canonical_unit(np.copysign(1.0, point_circle.offset) * point_circle.normal)
    error = float(np.dot(other.normal, point) - other.offset)
    scale = max(1.0, abs(other.offset))
    if abs(error) <= _GEOMETRY_EPS * scale:
        return CirclePairGeometry("point_intersection", (point,), error, error)
    if abs(error) < DELTA_DELTA:
        return CirclePairGeometry("point_near_tangent", (point,), error, error)
    return CirclePairGeometry("point_disjoint", (), error, error)


def intersect_sphere_circles(
    first: SphereCircle,
    second: SphereCircle,
) -> CirclePairGeometry:
    """Compute Algorithm-1 candidates for a pair of full-sphere circles.

    For ordinary pairs, ``delta_1`` and ``delta_2`` are exactly the directed
    peak distances in (64)--(65).  Intersections are computed through the
    algebraically equivalent intersection-line form of (66)--(72); unlike the
    printed (68), this remains finite when the circle normals are orthogonal.
    Exact/numerical tangency and the paper's near-tangent ``0.05`` rule are
    explicit.  Parallel, antiparallel, coincident, and point-circle cases have
    named outcomes rather than divisions by a vanishing cross product.
    """

    if first.is_point:
        result = _point_circle_geometry(first, second)
        if second.is_point and result.kind == "point_disjoint":
            return CirclePairGeometry("point_pair_disjoint", (), result.delta_1, result.delta_2)
        return result
    if second.is_point:
        return _point_circle_geometry(second, first)

    n1 = first.normal
    n2 = second.normal
    dot = float(np.clip(np.dot(n1, n2), -1.0, 1.0))
    cross = np.cross(n1, n2)
    cross_norm = float(np.linalg.norm(cross))
    if cross_norm <= _GEOMETRY_EPS:
        relation = "parallel" if dot >= 0.0 else "antiparallel"
        aligned_offset = second.offset if dot >= 0.0 else -second.offset
        offset_scale = max(1.0, abs(first.offset), abs(aligned_offset))
        if abs(first.offset - aligned_offset) <= _GEOMETRY_EPS * offset_scale:
            return CirclePairGeometry(
                f"coincident_{relation}", (), None, None, relation
            )
        return CirclePairGeometry(f"disjoint_{relation}", (), None, None, relation)

    v1 = cross / cross_norm
    # Paper (62): v2 is in circle m's plane and points along its peak axis.
    v2 = np.cross(v1, n2)
    v2 /= np.linalg.norm(v2)
    center_1 = first.center
    center_2 = second.center
    peak_1 = center_2 - second.radius * v2
    peak_2 = center_2 + second.radius * v2
    delta_1 = float(np.dot(peak_1 - center_1, n1))
    delta_2 = float(np.dot(peak_2 - center_1, n1))

    determinant = 1.0 - dot**2
    line_center = (
        (first.offset - dot * second.offset) * n1
        + (second.offset - dot * first.offset) * n2
    ) / determinant
    radial_squared = 1.0 - float(np.dot(line_center, line_center))
    radial_scale = max(1.0, abs(radial_squared), float(np.dot(line_center, line_center)))
    tangent_tolerance = _GEOMETRY_EPS * radial_scale

    if radial_squared > tangent_tolerance:
        radial = float(np.sqrt(radial_squared))
        candidates = deduplicate_directions_machine_precision(
            (_canonical_unit(line_center - radial * v1), _canonical_unit(line_center + radial * v1))
        )
        return CirclePairGeometry("two_intersections", candidates, delta_1, delta_2)
    if abs(radial_squared) <= tangent_tolerance:
        tangent = _canonical_unit(line_center)
        return CirclePairGeometry("tangent", (tangent,), delta_1, delta_2)

    near: list[FloatArray] = []
    if abs(delta_1) < DELTA_DELTA:
        near.append(_canonical_unit(peak_1))
    if abs(delta_2) < DELTA_DELTA:
        near.append(_canonical_unit(peak_2))
    candidates = deduplicate_directions_machine_precision(near)
    kind = "near_tangent" if candidates else "separate"
    return CirclePairGeometry(kind, candidates, delta_1, delta_2)


def deduplicate_directions_machine_precision(
    directions: Iterable[ArrayLike],
) -> tuple[FloatArray, ...]:
    """Deduplicate unit directions using only a binary64-roundoff tolerance.

    The deterministic lexicographic output order makes exact objective ties
    independent of pair enumeration.  No geometry/noise/metric tolerance is
    used, so scientifically distinct near-tangent candidates are retained.
    """

    unique: list[FloatArray] = []
    for direction in directions:
        candidate = _canonical_unit(direction)
        if any(np.max(np.abs(candidate - prior)) <= _DEDUP_EPS for prior in unique):
            continue
        unique.append(candidate)
    unique.sort(key=lambda item: (float(item[0]), float(item[1]), float(item[2])))
    return tuple(unique)


@dataclass(frozen=True)
class CandidatePool:
    """Complete, untruncated Algorithm-1 circle and direction pool."""

    circles: tuple[SphereCircle, ...]
    pair_geometries: tuple[CirclePairGeometry, ...]
    directions: tuple[FloatArray, ...]
    pair_count: int
    raw_candidate_count: int
    phase_row_count: int
    integer_option_count_per_row: tuple[int, ...]
    intersecting_pair_count: int
    near_tangent_candidate_count: int
    degenerate_pair_count: int


def generate_candidate_pool(model: SingleBaselineCWLSModel) -> CandidatePool:
    """Run Algorithm 1 over all different-observation circle pairs, without K."""

    circles = build_search_circles(model)
    pair_results: list[CirclePairGeometry] = []
    raw_directions: list[FloatArray] = []
    pair_count = 0
    for first, second in combinations(circles, 2):
        if first.observation_index == second.observation_index:
            continue
        pair_count += 1
        geometry = intersect_sphere_circles(first, second)
        pair_results.append(geometry)
        raw_directions.extend(geometry.candidates)
    unique = deduplicate_directions_machine_precision(raw_directions)
    if not unique:
        raise CWLSGeometryError(
            "Algorithm 1 produced no finite direction candidates",
            code="NO_CIRCLE_PAIR_CANDIDATE",
        )
    integer_counts = tuple(
        sum(circle.observation_index == row for circle in circles)
        for row in range(model.observation_count)
    )
    intersecting_kinds = {"two_intersections", "tangent", "point_intersection"}
    near_tangent_kinds = {"near_tangent", "point_near_tangent"}
    intersecting_count = sum(result.kind in intersecting_kinds for result in pair_results)
    near_tangent_count = sum(
        len(result.candidates)
        for result in pair_results
        if result.kind in near_tangent_kinds
    )
    degenerate_count = sum(
        result.parallel_relation is not None or result.kind.startswith("point_")
        for result in pair_results
    )
    return CandidatePool(
        circles=circles,
        pair_geometries=tuple(pair_results),
        directions=unique,
        pair_count=pair_count,
        raw_candidate_count=len(raw_directions),
        phase_row_count=model.observation_count,
        integer_option_count_per_row=integer_counts,
        intersecting_pair_count=intersecting_count,
        near_tangent_candidate_count=near_tangent_count,
        degenerate_pair_count=degenerate_count,
    )


def wrapped_objective(model: SingleBaselineCWLSModel, direction: ArrayLike) -> float:
    """Evaluate the original wrapped phase + code objective (54)/(73).

    The complete supplied covariance inverse is applied to the stacked
    residual; neither block diagonalization nor per-observation weighting is
    introduced.
    """

    unit = _canonical_unit(direction)
    prediction = model.baseline_length_m * (model.design_cycles_per_m @ unit)
    phase_residual = np.asarray(wrap_half_cycles(model.phase_cycles - prediction))
    code_residual = model.code_cycles - prediction
    residual = stack_phase_code(phase_residual, code_residual)
    return float(residual @ model._precision @ residual)


@dataclass(frozen=True)
class SphereQuadraticSolution:
    """Globally certified solution of a quadratic on the unit sphere."""

    direction: FloatArray
    lagrange_multiplier: float
    objective: float
    hard_case: bool
    global_certified: bool
    stationarity_residual: float
    unit_norm_residual: float
    psd_margin: float
    duality_gap: float
    secular_iterations: int


def _deterministic_eigenspace_direction(eigenvectors: FloatArray) -> FloatArray:
    projector = eigenvectors @ eigenvectors.T
    diagonal = np.diag(projector)
    index = int(np.argmax(diagonal))
    direction = projector[:, index]
    norm = float(np.linalg.norm(direction))
    if norm <= _GEOMETRY_EPS:
        raise CWLSNumericalError(
            "could not select a deterministic hard-case direction",
            code="SPHERE_SOLVER_FAILURE",
        )
    direction = direction / norm
    # P[j,j] is nonnegative, but this also handles a signed-zero/eigensolver edge.
    significant = np.flatnonzero(np.abs(direction) > _GEOMETRY_EPS)
    if significant.size and direction[int(significant[0])] < 0.0:
        direction = -direction
    return _readonly_float_array(direction)


def solve_unit_sphere_quadratic(matrix: ArrayLike, linear: ArrayLike) -> SphereQuadraticSolution:
    """Globally minimize ``r.T @ matrix @ r - 2 linear.T @ r``, ``||r||=1``.

    A symmetric eigendecomposition reduces the KKT system to
    ``(A + lambda I) r = b`` and its secular equation.  The regular root is
    bracketed above ``-lambda_min(A)``.  If the forcing is orthogonal to the
    minimum eigenspace, the boundary hard case is solved using a deterministic
    projector-based direction.  Global certification uses stationarity, unit
    norm, positive semidefiniteness of ``A + lambda I``, and the primal/dual
    gap; it does not rely on a local optimizer or initial direction.
    """

    a = np.asarray(matrix, dtype=np.float64)
    b = np.asarray(linear, dtype=np.float64)
    if a.shape != (3, 3) or b.shape != (3,):
        raise CWLSError("sphere quadratic requires a 3x3 matrix and a three-vector")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise CWLSError("sphere quadratic inputs must be finite")
    scale_a = max(1.0, float(np.linalg.norm(a, ord=2)))
    if np.max(np.abs(a - a.T)) > 64.0 * _EPS * scale_a:
        raise CWLSError("sphere quadratic matrix must be symmetric")
    a = 0.5 * (a + a.T)
    eigenvalues, eigenvectors = np.linalg.eigh(a)
    minimum = float(eigenvalues[0])
    eig_tolerance = 64.0 * _EPS * scale_a
    minimum_mask = eigenvalues - minimum <= eig_tolerance
    beta = eigenvectors.T @ b
    beta_scale = max(1.0, float(np.linalg.norm(b)))
    beta_tolerance = 64.0 * _EPS * beta_scale
    beta_minimum_norm = float(np.linalg.norm(beta[minimum_mask]))
    boundary = -minimum

    x0_eigen = np.zeros(3, dtype=np.float64)
    nonminimum = ~minimum_mask
    x0_eigen[nonminimum] = beta[nonminimum] / (eigenvalues[nonminimum] - minimum)
    x0 = eigenvectors @ x0_eigen
    x0_norm_squared = float(np.dot(x0, x0))
    hard_tolerance = 128.0 * _EPS * max(1.0, x0_norm_squared)
    hard_case = beta_minimum_norm <= beta_tolerance and x0_norm_squared <= 1.0 + hard_tolerance
    secular_iterations = 0

    if hard_case:
        remaining = max(0.0, 1.0 - x0_norm_squared)
        if remaining > hard_tolerance:
            hard_direction = _deterministic_eigenspace_direction(eigenvectors[:, minimum_mask])
            direction = x0 + np.sqrt(remaining) * hard_direction
        else:
            direction = x0
        if np.linalg.norm(direction) == 0.0:
            direction = _deterministic_eigenspace_direction(eigenvectors[:, minimum_mask])
        lagrange = boundary
    else:
        def secular(lagrange: float) -> float:
            denominator = eigenvalues + lagrange
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                quotient = beta / denominator
                value = float(np.dot(quotient, quotient) - 1.0)
            if np.isnan(value):
                return float("inf")
            return value

        low = float(np.nextafter(boundary, np.inf))
        high = boundary + max(1.0, float(np.linalg.norm(b)), scale_a)
        for _ in range(256):
            if secular(high) <= 0.0:
                break
            high = boundary + 2.0 * (high - boundary)
        else:
            raise CWLSNumericalError(
                "failed to bracket the sphere secular root",
                code="SPHERE_SOLVER_FAILURE",
            )
        low_value = secular(low)
        if low_value <= 0.0:
            # This can occur only when the hard-case boundary test was separated
            # by binary64 roundoff; retain the certified boundary construction.
            direction = x0
            lagrange = boundary
            hard_case = True
        else:
            for iteration in range(1, 257):
                midpoint = low + 0.5 * (high - low)
                if midpoint == low or midpoint == high:
                    secular_iterations = iteration
                    break
                value = secular(midpoint)
                if value > 0.0:
                    low = midpoint
                else:
                    high = midpoint
                secular_iterations = iteration
            candidates = (low, high, low + 0.5 * (high - low))
            lagrange = min(candidates, key=lambda item: abs(secular(item)))
            denominator = eigenvalues + lagrange
            direction = eigenvectors @ (beta / denominator)

    direction = _canonical_unit(direction)
    lagrange = float(lagrange)
    stationarity_vector = (a + lagrange * np.eye(3)) @ direction - b
    stationarity = float(np.linalg.norm(stationarity_vector))
    unit_residual = abs(float(np.linalg.norm(direction)) - 1.0)
    psd_margin = float(np.min(np.linalg.eigvalsh(a + lagrange * np.eye(3))))
    objective = float(direction @ a @ direction - 2.0 * b @ direction)

    denominators = eigenvalues + lagrange
    dual_sum = 0.0
    range_failure = False
    denominator_tolerance = 128.0 * _EPS * max(1.0, scale_a, abs(lagrange))
    for coefficient, denominator in zip(beta, denominators, strict=True):
        if abs(denominator) <= denominator_tolerance:
            if abs(coefficient) > beta_tolerance:
                range_failure = True
            continue
        dual_sum += float(coefficient**2 / denominator)
    dual_value = -dual_sum - lagrange
    duality_gap = abs(objective - dual_value) if not range_failure else float("inf")

    certificate_scale = max(1.0, abs(objective), scale_a, float(np.linalg.norm(b)))
    global_certified = bool(
        unit_residual <= 1.0e-12
        and stationarity <= 1.0e-9 * certificate_scale
        and psd_margin >= -1.0e-10 * certificate_scale
        and duality_gap <= 1.0e-8 * certificate_scale
        and not range_failure
    )
    return SphereQuadraticSolution(
        direction=direction,
        lagrange_multiplier=lagrange,
        objective=objective,
        hard_case=hard_case,
        global_certified=global_certified,
        stationarity_residual=stationarity,
        unit_norm_residual=unit_residual,
        psd_margin=psd_margin,
        duality_gap=duality_gap,
        secular_iterations=secular_iterations,
    )


@dataclass(frozen=True)
class RefinementIteration:
    """One (74)--(75) integer-assignment and sphere-solve iteration."""

    iteration: int
    integer_corrections: tuple[int, ...]
    direction_change: float
    integer_stable: bool
    sphere_solution: SphereQuadraticSolution


@dataclass(frozen=True)
class CandidateDiagnostic:
    """Complete Algorithm-2 diagnostic for one untruncated coarse candidate."""

    coarse_index: int
    coarse_direction: FloatArray
    coarse_objective: float | None
    refined_direction: FloatArray
    objective: float | None
    converged: bool
    iterations: tuple[RefinementIteration, ...]
    integer_corrections: tuple[int, ...]
    integer_ambiguities: tuple[int, ...]
    wrapped_phase_residual_cycles: tuple[float, ...]
    wrapped_phase_rms_cycles: float
    wrapped_phase_max_abs_cycles: float
    refined_unwrapped_objective: float | None
    iteration_count: int
    integer_vector_stable: bool
    unit_norm_error: float
    convergence_state: str
    failure_code: str | None


def _integer_corrections(model: SingleBaselineCWLSModel, direction: FloatArray) -> IntArray:
    prediction = model.baseline_length_m * (model.design_cycles_per_m @ direction)
    return np.asarray(round_half_down(prediction - model.phase_cycles), dtype=np.int64)


def _fixed_integer_sphere_solution(
    model: SingleBaselineCWLSModel,
    integer_corrections: IntArray,
) -> SphereQuadraticSolution:
    unambiguous_phase = model.phase_cycles + integer_corrections
    observations = stack_phase_code(unambiguous_phase, model.code_cycles)
    linear = model._stacked_design.T @ model._precision @ observations
    if not np.all(np.isfinite(linear)):
        raise CWLSNumericalError(
            "nonfinite fixed-integer quadratic", code="SPHERE_SOLVER_FAILURE"
        )
    try:
        solution = solve_unit_sphere_quadratic(model._quadratic_matrix, linear)
    except CWLSNumericalError as exc:
        if exc.code == "SPHERE_SOLVER_FAILURE":
            raise
        raise CWLSNumericalError(
            str(exc), code="SPHERE_SOLVER_FAILURE"
        ) from exc
    except (CWLSError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
        raise CWLSNumericalError(
            "unit-sphere quadratic numerical failure",
            code="SPHERE_SOLVER_FAILURE",
        ) from exc
    if not solution.global_certified:
        raise CWLSNumericalError(
            "unit-sphere quadratic did not pass its global certificate",
            code="SPHERE_SOLVER_FAILURE",
        )
    return solution


def _refine_candidate(
    model: SingleBaselineCWLSModel,
    coarse_index: int,
    coarse_direction: FloatArray,
    cache: dict[tuple[int, ...], SphereQuadraticSolution],
) -> CandidateDiagnostic:
    current = coarse_direction
    coarse_objective = wrapped_objective(model, current)
    if not np.isfinite(coarse_objective):
        raise CWLSNumericalError(
            "nonfinite coarse wrapped objective", code="NONFINITE_OBJECTIVE"
        )
    iterations: list[RefinementIteration] = []
    converged = False
    for iteration in range(1, REFINEMENT_MAX_ITERATIONS + 1):
        corrections = _integer_corrections(model, current)
        key = tuple(int(value) for value in corrections)
        sphere_solution = cache.get(key)
        if sphere_solution is None:
            sphere_solution = _fixed_integer_sphere_solution(model, corrections)
            cache[key] = sphere_solution
        updated = sphere_solution.direction
        updated_corrections = _integer_corrections(model, updated)
        integer_stable = bool(np.array_equal(corrections, updated_corrections))
        direction_change = float(np.linalg.norm(updated - current))
        iterations.append(
            RefinementIteration(
                iteration,
                key,
                direction_change,
                integer_stable,
                sphere_solution,
            )
        )
        current = updated
        if integer_stable and direction_change <= REFINEMENT_TOL:
            converged = True
            break

    final_corrections = _integer_corrections(model, current)
    prediction = model.baseline_length_m * (model.design_cycles_per_m @ current)
    phase_residual = np.asarray(
        wrap_half_cycles(model.phase_cycles - prediction), dtype=np.float64
    )
    objective = wrapped_objective(model, current)
    unwrapped_residual = stack_phase_code(
        model.phase_cycles + final_corrections - prediction,
        model.code_cycles - prediction,
    )
    unwrapped_objective = float(unwrapped_residual @ model._precision @ unwrapped_residual)
    if not np.isfinite(objective) or not np.isfinite(unwrapped_objective):
        raise CWLSNumericalError(
            "nonfinite refined objective", code="NONFINITE_OBJECTIVE"
        )
    integer_vector_stable = bool(
        iterations
        and iterations[-1].integer_stable
        and iterations[-1].integer_corrections
        == tuple(int(value) for value in final_corrections)
    )
    direction_converged = bool(
        iterations and iterations[-1].direction_change <= REFINEMENT_TOL
    )
    if converged:
        convergence_state = "CONVERGED_INTEGER_STABLE_DIRECTION"
    elif not integer_vector_stable and not direction_converged:
        convergence_state = "MAX_ITERATIONS_INTEGER_UNSTABLE_AND_DIRECTION_NOT_CONVERGED"
    elif not integer_vector_stable:
        convergence_state = "MAX_ITERATIONS_INTEGER_UNSTABLE"
    else:
        convergence_state = "MAX_ITERATIONS_DIRECTION_NOT_CONVERGED"
    return CandidateDiagnostic(
        coarse_index=coarse_index,
        coarse_direction=coarse_direction,
        coarse_objective=coarse_objective,
        refined_direction=current,
        objective=objective,
        converged=converged,
        iterations=tuple(iterations),
        integer_corrections=tuple(int(value) for value in final_corrections),
        integer_ambiguities=tuple(int(-value) for value in final_corrections),
        wrapped_phase_residual_cycles=tuple(float(value) for value in phase_residual),
        wrapped_phase_rms_cycles=float(np.sqrt(np.mean(phase_residual**2))),
        wrapped_phase_max_abs_cycles=float(np.max(np.abs(phase_residual))),
        refined_unwrapped_objective=unwrapped_objective,
        iteration_count=len(iterations),
        integer_vector_stable=integer_vector_stable,
        unit_norm_error=abs(float(np.linalg.norm(current)) - 1.0),
        convergence_state=convergence_state,
        failure_code=None,
    )


def _failed_candidate_diagnostic(
    model: SingleBaselineCWLSModel,
    coarse_index: int,
    coarse_direction: FloatArray,
    failure_code: str,
) -> CandidateDiagnostic:
    """Create a serializable candidate-local failure without fabricating convergence."""

    try:
        coarse_objective = wrapped_objective(model, coarse_direction)
    except (CWLSError, FloatingPointError):
        coarse_objective = None
    if coarse_objective is not None and not np.isfinite(coarse_objective):
        coarse_objective = None
    corrections = _integer_corrections(model, coarse_direction)
    prediction = model.baseline_length_m * (
        model.design_cycles_per_m @ coarse_direction
    )
    phase_residual = np.asarray(
        wrap_half_cycles(model.phase_cycles - prediction), dtype=np.float64
    )
    correction_tuple = tuple(int(value) for value in corrections)
    return CandidateDiagnostic(
        coarse_index=coarse_index,
        coarse_direction=coarse_direction,
        coarse_objective=coarse_objective,
        refined_direction=coarse_direction,
        objective=None,
        converged=False,
        iterations=(),
        integer_corrections=correction_tuple,
        integer_ambiguities=tuple(-value for value in correction_tuple),
        wrapped_phase_residual_cycles=tuple(float(value) for value in phase_residual),
        wrapped_phase_rms_cycles=float(np.sqrt(np.mean(phase_residual**2))),
        wrapped_phase_max_abs_cycles=float(np.max(np.abs(phase_residual))),
        refined_unwrapped_objective=None,
        iteration_count=0,
        integer_vector_stable=False,
        unit_norm_error=abs(float(np.linalg.norm(coarse_direction)) - 1.0),
        convergence_state=f"FAILED_{failure_code}",
        failure_code=failure_code,
    )


@dataclass(frozen=True)
class CWLSSolution:
    """Minimum-(54) result after every unique Algorithm-1 candidate converges."""

    direction: FloatArray
    baseline_vector_m: FloatArray
    objective: float
    integer_corrections: tuple[int, ...]
    integer_ambiguities: tuple[int, ...]
    selected_candidate_index: int
    exact_objective_tie_count: int
    circle_count: int
    circle_pair_count: int
    raw_candidate_count: int
    candidate_count: int
    phase_row_count: int
    integer_option_count_per_row: tuple[int, ...]
    intersecting_pair_count: int
    near_tangent_candidate_count: int
    degenerate_pair_count: int
    diagnostics: tuple[CandidateDiagnostic, ...]


def solve_single_baseline_cwls(model: SingleBaselineCWLSModel) -> CWLSSolution:
    """Solve single-baseline C-WLS by Algorithm 1 and (74)--(75).

    ``delta_Delta`` is fixed at 0.05, refinement uses simultaneous integer
    stability and direction convergence at tolerance ``1e-10`` with at most 20
    iterations, and every unique coarse candidate is refined.  Selection is by
    the original wrapped objective (54), not the fixed-integer surrogate.  The
    exact-float tie key is deterministic and uses no reference/trace data.
    Candidate-local numerical failures do not stop the pool sweep, but any
    failed, nonconverged, or nonfinite candidate rejects the epoch afterward;
    consequently every diagnostic on a returned solution is complete.
    """

    pool = generate_candidate_pool(model)
    cache: dict[tuple[int, ...], SphereQuadraticSolution] = {}
    diagnostic_list: list[CandidateDiagnostic] = []
    for index, direction in enumerate(pool.directions):
        try:
            diagnostic = _refine_candidate(model, index, direction, cache)
        except CWLSNumericalError as exc:
            failure_code = (
                exc.code
                if exc.code in {"SPHERE_SOLVER_FAILURE", "NONFINITE_OBJECTIVE"}
                else "SPHERE_SOLVER_FAILURE"
            )
            diagnostic = _failed_candidate_diagnostic(
                model, index, direction, failure_code
            )
        diagnostic_list.append(diagnostic)
    diagnostics = tuple(diagnostic_list)
    converged_diagnostics = tuple(item for item in diagnostics if item.converged)
    if not converged_diagnostics:
        failure_codes = sorted(
            {item.failure_code for item in diagnostics if item.failure_code is not None}
        )
        suffix = ",".join(failure_codes) if failure_codes else "NONCONVERGENCE"
        raise CWLSNumericalError(
            f"ALL_REFINEMENTS_FAILED: {suffix}",
            code="ALL_REFINEMENTS_FAILED",
            candidate_diagnostics=diagnostics,
            candidate_pool=pool,
        )
    incomplete_diagnostics = tuple(
        item
        for item in diagnostics
        if (
            not item.converged
            or item.failure_code is not None
            or item.objective is None
            or not np.isfinite(item.objective)
        )
    )
    if incomplete_diagnostics:
        has_sphere_failure = any(
            item.failure_code == "SPHERE_SOLVER_FAILURE"
            for item in incomplete_diagnostics
        )
        terminal_code = (
            "SPHERE_SOLVER_FAILURE" if has_sphere_failure else "NUMERICAL_FAILURE"
        )
        failure_codes = sorted(
            {
                item.failure_code or item.convergence_state
                for item in incomplete_diagnostics
            }
        )
        raise CWLSNumericalError(
            "INCOMPLETE_CANDIDATE_REFINEMENT_POOL: "
            f"{len(incomplete_diagnostics)}/{len(diagnostics)}; "
            + ",".join(failure_codes),
            code=terminal_code,
            candidate_diagnostics=diagnostics,
            candidate_pool=pool,
        )
    selected = min(
        converged_diagnostics,
        key=lambda item: (
            float(item.objective),
            float(item.refined_direction[0]),
            float(item.refined_direction[1]),
            float(item.refined_direction[2]),
            item.integer_ambiguities,
            item.coarse_index,
        ),
    )
    tie_count = sum(item.objective == selected.objective for item in converged_diagnostics)
    direction = selected.refined_direction
    return CWLSSolution(
        direction=direction,
        baseline_vector_m=_readonly_float_array(model.baseline_length_m * direction),
        objective=float(selected.objective),
        integer_corrections=selected.integer_corrections,
        integer_ambiguities=selected.integer_ambiguities,
        selected_candidate_index=selected.coarse_index,
        exact_objective_tie_count=tie_count,
        circle_count=len(pool.circles),
        circle_pair_count=pool.pair_count,
        raw_candidate_count=pool.raw_candidate_count,
        candidate_count=len(pool.directions),
        phase_row_count=pool.phase_row_count,
        integer_option_count_per_row=pool.integer_option_count_per_row,
        intersecting_pair_count=pool.intersecting_pair_count,
        near_tangent_candidate_count=pool.near_tangent_candidate_count,
        degenerate_pair_count=pool.degenerate_pair_count,
        diagnostics=diagnostics,
    )


__all__ = [
    "DELTA_DELTA",
    "REFINEMENT_MAX_ITERATIONS",
    "REFINEMENT_TOL",
    "CWLSGeometryError",
    "CWLSNumericalError",
    "CWLSError",
    "CWLSSolution",
    "CandidateDiagnostic",
    "CandidatePool",
    "CirclePairGeometry",
    "DoubleDifferenceDesign",
    "IntegerInterval",
    "RefinementIteration",
    "SingleBaselineCWLSModel",
    "SphereCircle",
    "SphereQuadraticSolution",
    "adapt_metric_double_differences",
    "build_double_difference_design",
    "build_search_circles",
    "deduplicate_directions_machine_precision",
    "generate_candidate_pool",
    "integer_ambiguity_interval",
    "intersect_sphere_circles",
    "round_half_down",
    "solve_single_baseline_cwls",
    "solve_unit_sphere_quadratic",
    "stack_phase_code",
    "wrap_half_cycles",
    "wrapped_objective",
]
