"""Selection-only partial integer classes with full-dimensional nuisance search.

The subset is a geometry/precision heuristic conditional on fixing its integers;
it is not an integer-success probability or a calibrated acceptance rule. Only
selection epochs, exact explicit SD-arc labels, B and full Q enter selection.
Unselected integers remain INTEGER nuisance variables in the original CILS
search. Future validation withholds their phase rows and retains every code row.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Sequence

import numpy as np

from .admission import FrozenCandidate
from .multignss import MultiGnssEpoch, group_key, signal_spec, raw
from .solver import TemporalResult, checked_integer_vector, solve_temporal
from .temporal import TemporalModelError, TemporalProblem, assemble_epochs, positive_definite


@dataclass(frozen=True)
class PartialPolicy:
    selection_epochs: int = 5
    min_ambiguities: int = 4
    max_ambiguities: int = 8
    epoch_interval_s: float = .2
    time_tolerance_s: float = .01

    def __post_init__(self):
        counts = (self.selection_epochs, self.min_ambiguities, self.max_ambiguities)
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in counts):
            raise TemporalModelError("partial counts must be positive integers")
        if self.min_ambiguities > self.max_ambiguities:
            raise TemporalModelError("partial minimum exceeds maximum")
        if (not math.isfinite(self.epoch_interval_s) or self.epoch_interval_s <= 0
                or not math.isfinite(self.time_tolerance_s)
                or not 0 < self.time_tolerance_s < self.epoch_interval_s / 2):
            raise TemporalModelError("invalid partial selection time slots")


@dataclass(frozen=True)
class PartialSupport:
    rows_retained: tuple[int, ...]
    rows_withheld: tuple[int, ...]
    missing_selected_labels: tuple[str, ...]
    unknown_labels: tuple[str, ...]
    phase_rows_retained: tuple[int, ...]


def partial_support_rows(model, selected_labels: Sequence[str]) -> PartialSupport:
    """Original row indices: all code + phase depending only on known labels.

    This helper does not assert continuity when a selected label disappears.
    missing_selected_labels must block complete-subset admission, as in the
    existing CausalAdmissionSession. Never use a conditional covariance here:
    observation subsetting uses Q[np.ix_(rows_retained, rows_retained)].
    """
    selected = tuple(selected_labels)
    if not selected or len(set(selected)) != len(selected):
        raise TemporalModelError("partial selected labels must be nonempty and unique")
    labels = tuple(model.ambiguity_labels)
    a = np.asarray(model.A, float)
    if (a.ndim != 2 or a.shape[1] != len(labels)
            or len(set(labels)) != len(labels) or not np.isfinite(a).all()):
        raise TemporalModelError("invalid ambiguity design or labels")
    unknown_columns = [i for i, label in enumerate(labels) if label not in selected]
    withheld = np.any(a[:, unknown_columns] != 0, axis=1) if unknown_columns else np.zeros(len(a), bool)
    phase = np.any(a != 0, axis=1)
    return PartialSupport(tuple(int(x) for x in np.flatnonzero(~withheld)),
                          tuple(int(x) for x in np.flatnonzero(withheld)),
                          tuple(s for s in selected if s not in labels),
                          tuple(labels[i] for i in unknown_columns),
                          tuple(int(x) for x in np.flatnonzero(phase & ~withheld)))


@dataclass(frozen=True)
class PartialStep:
    added_label: str
    minimum_phase_rank: int
    minimum_phase_rows: int
    worst_epoch_logdet_information: float | None


@dataclass(frozen=True)
class PartialSelection:
    status: str
    selected_at: float
    selection_times: tuple[float, ...]
    selected_labels: tuple[str, ...]
    stable_labels: tuple[str, ...]
    unstable_labels: tuple[str, ...]
    selected_group_counts: tuple[tuple[tuple[int, int, int], int], ...]
    steps: tuple[PartialStep, ...]
    policy: PartialPolicy
    score_description: str = (
        "greedy lexicographic: maximize worst-epoch selected phase B rank, "
        "then worst-epoch logdet(Bret.T Qret^-1 Bret); all code rows retained"
    )
    integer_success_probability: None = None

    @property
    def ready(self):
        return self.status == "READY"


@dataclass(frozen=True)
class PartialSearchPlan:
    problem: TemporalProblem
    selection: PartialSelection


def _registered_geometry(model: MultiGnssEpoch):
    """Validate native code/phase DD identity without inspecting y values."""
    labels = tuple(model.ambiguity_labels)
    m = len(labels)
    a, b = np.asarray(model.A, float), np.asarray(model.B, float)
    if (not m or len(set(labels)) != m or a.shape != (2*m, m)
            or b.shape != (2*m, 3) or not np.isfinite(a).all()
            or not np.isfinite(b).all()):
        raise TemporalModelError("partial selection needs native finite code/phase DD geometry")
    q = positive_definite(model.Q, "partial Q")
    if q.shape != (2*m, 2*m):
        raise TemporalModelError("partial covariance dimension mismatch")
    if model.metadata.get("arc_label_policy") != "EXPLICIT_SD_ARCS":
        raise TemporalModelError("partial temporal sharing requires explicit SD arc labels")
    if model.metadata.get("baseline_frame") != "ECEF":
        raise TemporalModelError("partial baseline geometry must be ECEF")
    expected_a = np.zeros_like(a)
    seen_columns, seen_rows, identities = set(), set(), {}
    for group in model.groups:
        size = len(group.satellites)
        columns, rows = tuple(group.ambiguity_indices), tuple(group.row_indices)
        if (size == 0 or len(columns) != size or len(set(columns)) != size
                or len(rows) != 2*size or len(set(rows)) != 2*size
                or any(not isinstance(i, (int, np.integer)) or i < 0 or i >= m for i in columns)
                or any(not isinstance(i, (int, np.integer)) or i < 0 or i >= 2*m for i in rows)
                or seen_columns.intersection(columns) or seen_rows.intersection(rows)
                or tuple(labels[i] for i in columns) != tuple(group.ambiguity_labels)
                or len(set(group.satellites)) != size):
            raise TemporalModelError("partial group row/column identity mismatch")
        if tuple(group.key) != group_key(group.pivot):
            raise TemporalModelError("partial pivot group mismatch")
        seen_columns.update(columns)
        seen_rows.update(rows)
        for k, (column, target) in enumerate(zip(columns, group.satellites)):
            if target == group.pivot or group_key(target) != tuple(group.key):
                raise TemporalModelError("partial target group mismatch")
            try:
                value = json.loads(labels[column])
            except (TypeError, ValueError) as exc:
                raise TemporalModelError("invalid explicit DD arc label") from exc
            if (not isinstance(value, list) or len(value) != 4
                    or value[0] != raw.identity_text(target)
                    or value[2] != raw.identity_text(group.pivot)
                    or any(not isinstance(value[j], str) or not value[j] for j in (1, 3))):
                raise TemporalModelError("DD label does not bind target/pivot SD arcs")
            expected_a[rows[size+k], column] = signal_spec(target).wavelength_m
            identities[labels[column]] = tuple(group.key)
    if seen_columns != set(range(m)) or seen_rows != set(range(2*m)):
        raise TemporalModelError("partial groups must cover all native rows and labels")
    if not np.allclose(a, expected_a, rtol=1e-12, atol=0):
        raise TemporalModelError("partial native phase wavelength or row placement mismatch")
    return b, q, identities


def _score(models, geometries, selected):
    ranks, counts, logdets = [], [], []
    for model, (b, q, _) in zip(models, geometries):
        support = partial_support_rows(model, selected)
        phase = b[list(support.phase_rows_retained)]
        ranks.append(int(np.linalg.matrix_rank(phase)) if len(phase) else 0)
        counts.append(len(phase))
        rows = list(support.rows_retained)
        whitened = np.linalg.solve(np.linalg.cholesky(q[np.ix_(rows, rows)]), b[rows])
        singular = np.linalg.svd(whitened, compute_uv=False)
        tolerance = np.finfo(float).eps * max(whitened.shape) * singular[0]
        logdets.append(float(2*np.log(singular).sum())
                       if len(singular) == 3 and singular[-1] > tolerance else -math.inf)
    return min(ranks), min(counts), min(logdets)


def preselect_partial_labels(models: Sequence[MultiGnssEpoch],
                             policy: PartialPolicy = PartialPolicy()) -> PartialSelection:
    """Use exactly registered selection slots; no y, residual, N or future data.

    Exact DD label intersection is conservative: a reset of either SD arc or a
    pivot change is never treated as continuation. Arc-token validity is the
    input tracker's responsibility. Finite selection samples cannot prove
    absence of undetected slips. No post-selection removal is implemented.
    """
    models = tuple(models)
    if len(models) != policy.selection_epochs:
        raise TemporalModelError("partial selection requires exactly the registered epoch count")
    times = tuple(float(m.time_s) for m in models)
    if (not np.isfinite(times).all()
            or any(abs(t-(times[0]+k*policy.epoch_interval_s)) > policy.time_tolerance_s
                   for k, t in enumerate(times))
            or any(right <= left for left, right in zip(times, times[1:]))):
        raise TemporalModelError("partial selection epochs do not match fixed ordered time slots")
    geometries = tuple(_registered_geometry(model) for model in models)
    stable = tuple(sorted(set.intersection(*(set(m.ambiguity_labels) for m in models))))
    all_labels = set.union(*(set(m.ambiguity_labels) for m in models))
    unstable = tuple(sorted(all_labels - set(stable)))
    selected, steps = [], []
    if len(stable) >= policy.min_ambiguities:
        available = list(stable)
        for _ in range(min(policy.max_ambiguities, len(stable))):
            ranked = []
            for label in available:
                rank, count, info = _score(models, geometries, (*selected, label))
                # Identity tie-break is deterministic and independent of y.
                ranked.append((-rank, -info, label, count))
            neg_rank, neg_info, label, count = min(ranked)
            selected.append(label)
            available.remove(label)
            info = -neg_info
            steps.append(PartialStep(label, -neg_rank, count, info if math.isfinite(info) else None))
    if len(stable) < policy.min_ambiguities:
        status = "UNAVAILABLE_INSUFFICIENT_CONTINUOUS_ARCS"
    elif steps[-1].minimum_phase_rows < policy.min_ambiguities:
        status = "UNAVAILABLE_INSUFFICIENT_PHASE_ROWS"
    elif steps[-1].minimum_phase_rank != 3 or steps[-1].worst_epoch_logdet_information is None:
        status = "UNAVAILABLE_PHASE_GEOMETRY"
    else:
        status = "READY"
    counts = {}
    for label in selected:
        group = geometries[0][2][label]
        counts[group] = counts.get(group, 0) + 1
    return PartialSelection(status, times[-1], times, tuple(selected), stable, unstable,
                            tuple(sorted(counts.items())), tuple(steps), policy)


def prepare_partial_search(models: Sequence[MultiGnssEpoch], *, length_m: float,
                           policy: PartialPolicy = PartialPolicy()) -> PartialSearchPlan:
    """Keep every original row, covariance term and nuisance integer in CILS."""
    models = tuple(models)
    selection = preselect_partial_labels(models, policy)
    problem = assemble_epochs(models, length_m=length_m)
    return PartialSearchPlan(problem, selection)


def solve_partial(plan: PartialSearchPlan, lambda_library, *, initial_candidates: int = 8,
                  node_limit: int = 100000, timeout_s: float = 60.) -> TemporalResult:
    """Profile unselected INTEGER coordinates via full original-dimensional search."""
    if not plan.selection.ready:
        raise TemporalModelError(f"partial subset unavailable: {plan.selection.status}")
    return solve_temporal(plan.problem, lambda_library, initial_candidates=initial_candidates,
                          node_limit=node_limit, timeout_s=timeout_s,
                          distinct_ambiguity_labels=plan.selection.selected_labels)


def freeze_partial_candidates(plan: PartialSearchPlan, result: TemporalResult, *,
                              source_id: str) -> tuple[FrozenCandidate, FrozenCandidate]:
    """Freeze two certified selected classes, exposing no nuisance integers.

    Projecting old full-vector top-two candidates is invalid: both can represent
    one selected class and omit its best distinct competitor. This function
    requires the selected-class certificate with exactly this subset.
    """
    selected = plan.selection.selected_labels
    certificate = result.certificate
    if (not plan.selection.ready or not certificate.global_optimum_certified
            or certificate.certificate_scope != "two_best_selected_integer_classes"
            or tuple(certificate.distinct_ambiguity_labels) != selected
            or certificate.distinct_ambiguity_classes < 2
            or result.best is None or result.second is None):
        raise TemporalModelError("partial freeze requires the exact certified selected-class search")
    indices = [plan.problem.ambiguity_labels.index(s) for s in selected]
    mappings = []
    for candidate in (result.best, result.second):
        n = checked_integer_vector(candidate.ambiguity)
        if n.shape != (plan.problem.ambiguity_count,):
            raise TemporalModelError("partial result must retain the complete nuisance integer vector")
        mappings.append({s: int(n[i]) for s, i in zip(selected, indices)})
    if mappings[0] == mappings[1]:
        raise TemporalModelError("partial candidate classes must differ on the selected integers")
    return tuple(FrozenCandidate.from_mapping(name, plan.selection.selected_at, mapping,
                                              selected, source_id)
                 for name, mapping in zip(("partial_primary", "partial_competitor"), mappings))
