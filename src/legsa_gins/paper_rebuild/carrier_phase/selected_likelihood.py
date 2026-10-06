"""Selected-observation Gaussian likelihood with principal marginal covariance.

This removes observations depending on unselected integers before solving. It
is a different likelihood from profiling those integer nuisances in all rows.
Selection uses only the existing selection-window geometry/Q/arc rule. Future
admission must still use the original models and the unchanged frozen subset.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Sequence

import numpy as np

from .partial import (PartialPolicy, PartialSelection, PartialSearchPlan,
    preselect_partial_labels, partial_support_rows, solve_partial, freeze_partial_candidates)
from .solver import TemporalResult
from .temporal import (EpochBlock, TemporalModelError, assemble_epochs,
    has_cross_epoch_covariance, positive_definite)

LIKELIHOOD_KIND = "SELECTED_OBSERVATION_MARGINAL_Q_V1"


@dataclass(frozen=True)
class SelectedLikelihoodSupport:
    time_s: float
    source_rows: int
    source_ambiguities: int
    source_code_rows: int
    source_phase_rows: int
    rows_retained: tuple[int, ...]
    rows_withheld: tuple[int, ...]
    selected_source_columns: tuple[int, ...]
    retained_code_rows: int
    retained_phase_rows: int


def restrict_selected_observations(model, selected_labels: Sequence[str]):
    """Return an independent EpochBlock and source-row map in ORIGINAL row order.

    Retain iff every unselected A entry is exactly zero. Q is the retained
    principal submatrix, not a Schur complement or diagonal approximation.
    Columns follow selected_labels order, regardless of source column ordering.
    """
    selected = tuple(selected_labels)
    support = partial_support_rows(model, selected)
    if support.missing_selected_labels:
        raise TemporalModelError("selected likelihood cannot inherit missing/reset labels")
    y, a, b = (np.asarray(getattr(model, name), float) for name in ("y", "A", "B"))
    q = positive_definite(model.Q, "selected likelihood source Q")
    if (y.ndim != 1 or a.shape[0] != len(y) or b.shape != (len(y), 3)
            or q.shape != (len(y), len(y)) or not np.isfinite(y).all()
            or not np.isfinite(b).all()):
        raise TemporalModelError("invalid selected likelihood source dimensions or values")
    labels = tuple(model.ambiguity_labels)
    columns = tuple(labels.index(label) for label in selected)
    rows = support.rows_retained
    phase = np.any(a != 0, axis=1)
    metadata = deepcopy(model.metadata)
    metadata.update(likelihood_kind=LIKELIHOOD_KIND, source_row_indices=rows,
                    selected_source_columns=columns)
    reduced = EpochBlock(float(model.time_s), y[list(rows)].copy(),
        a[np.ix_(rows, columns)].copy(), b[list(rows)].copy(),
        q[np.ix_(rows, rows)].copy(), selected, metadata)
    counts = SelectedLikelihoodSupport(float(model.time_s), len(y), len(labels),
        int(np.count_nonzero(~phase)), int(np.count_nonzero(phase)), rows,
        support.rows_withheld, columns, int(np.count_nonzero(~phase[list(rows)])),
        int(np.count_nonzero(phase[list(rows)])))
    return reduced, counts


@dataclass(frozen=True)
class SelectedLikelihoodPlan:
    selection: PartialSelection
    search_plan: PartialSearchPlan | None
    epochs: tuple[EpochBlock, ...]
    supports: tuple[SelectedLikelihoodSupport, ...]
    likelihood_kind: str = LIKELIHOOD_KIND

    @property
    def ready(self):
        return self.selection.ready and self.search_plan is not None

    @property
    def problem(self):
        if not self.ready:
            raise TemporalModelError("selected likelihood unavailable: " + self.selection.status)
        return self.search_plan.problem

    @property
    def fingerprint(self):
        """Bind the actual reduced solver arrays and source-row identity, not discarded y."""
        problem = self.problem
        if (self.likelihood_kind != LIKELIHOOD_KIND
                or self.search_plan.selection != self.selection
                or problem.ambiguity_labels != self.selection.selected_labels
                or has_cross_epoch_covariance(problem)):
            raise TemporalModelError("selected likelihood plan identity or independence mismatch")
        header = dict(kind=self.likelihood_kind, selected_at=self.selection.selected_at,
            labels=problem.ambiguity_labels, supports=[asdict(s) for s in self.supports])
        digest = hashlib.sha256(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
        for name in ("times", "lengths", "y", "A", "B", "Q"):
            value = np.asarray(getattr(problem, name), dtype="<f8", order="C")
            if not np.isfinite(value).all():
                raise TemporalModelError("nonfinite selected likelihood array: " + name)
            digest.update(json.dumps((name, value.shape), separators=(",", ":")).encode())
            digest.update(value.tobytes(order="C"))
        return digest.hexdigest()


def prepare_selected_likelihood(models, *, length_m: float,
        policy: PartialPolicy = PartialPolicy(max_ambiguities=6)) -> SelectedLikelihoodPlan:
    models = tuple(models)
    if not np.isfinite(length_m) or length_m <= 0:
        raise TemporalModelError("selected likelihood requires positive finite baseline length")
    selection = preselect_partial_labels(models, policy)
    if not selection.ready:
        return SelectedLikelihoodPlan(selection, None, (), ())
    reduced = tuple(restrict_selected_observations(model, selection.selected_labels) for model in models)
    epochs, supports = tuple(x[0] for x in reduced), tuple(x[1] for x in reduced)
    problem = assemble_epochs(epochs, length_m=length_m)
    plan = SelectedLikelihoodPlan(selection, PartialSearchPlan(problem, selection), epochs, supports)
    plan.fingerprint  # Validate the constructed problem identity before returning.
    return plan


@dataclass(frozen=True)
class SelectedLikelihoodResult:
    result: TemporalResult
    plan_fingerprint: str
    likelihood_kind: str = LIKELIHOOD_KIND
    certificate_scope: str = "two_best_classes_of_selected_observation_likelihood"


def solve_selected_likelihood(plan: SelectedLikelihoodPlan, lambda_library, *,
        initial_candidates: int = 8, node_limit: int = 100000, timeout_s: float = 60.,
        sphere_library=None) -> SelectedLikelihoodResult:
    fingerprint = plan.fingerprint
    options = dict(initial_candidates=initial_candidates, node_limit=node_limit, timeout_s=timeout_s)
    if sphere_library is not None:
        options["sphere_library"] = sphere_library
    result = solve_partial(plan.search_plan, lambda_library, **options)
    if plan.fingerprint != fingerprint:
        raise TemporalModelError("selected likelihood changed while solving")
    return SelectedLikelihoodResult(result, fingerprint)


def freeze_selected_likelihood_candidates(plan: SelectedLikelihoodPlan,
        result: SelectedLikelihoodResult, *, source_id: str):
    if (not isinstance(result, SelectedLikelihoodResult)
            or result.likelihood_kind != LIKELIHOOD_KIND
            or result.certificate_scope != "two_best_classes_of_selected_observation_likelihood"
            or result.plan_fingerprint != plan.fingerprint):
        raise TemporalModelError("result is not bound to this selected-observation likelihood")
    if not isinstance(source_id, str) or not source_id.strip():
        raise TemporalModelError("selected likelihood requires a nonempty source identity")
    return freeze_partial_candidates(plan.search_plan, result.result,
        source_id=LIKELIHOOD_KIND + ":" + result.plan_fingerprint + ":" + source_id)
