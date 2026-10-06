"""Conditional fixed-integer phase-fault diagnostics; no phase or integer repair.

Fault amplitudes are cycles in one receiver single-difference signal. A pivot
fault enters every phase DD in its exact signal group. GLS uses the full
retained covariance and unconstrained baseline nuisance columns. For a true,
fixed N, known Gaussian Q, correctly specified linear mean, and observations
independent of candidate selection, J0 is chi-square(n-rank(B)); a specified
estimable scalar-fault improvement is chi-square(1) under its null. These are
conditional model statements, not false-fix probabilities or measured noise
calibration. Holm controls familywise rejection under the shared fault-free
null, given those assumptions. Under an actual fault, correlated templates
can all reject: this does not control misidentification of the physical source.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Mapping, Sequence
import math
import json
import numpy as np
from scipy.special import gammaincc

from .multignss import MultiGnssEpoch, SignalIdentity, group_key, signal_spec
from .temporal import TemporalModelError, positive_definite
from ..horizontal_literature import shared_raw_backend as raw


@dataclass(frozen=True)
class PhaseFaultHypothesis:
    key: str
    signal: SignalIdentity
    group: tuple[int, int, int]
    pivot: SignalIdentity | None
    is_pivot: bool | None
    receiver: str
    wavelength_m: float
    affected_ambiguity_labels: tuple[str, ...]
    sd_arc_token: str | None = None


@dataclass(frozen=True)
class PhaseFaultMap:
    """Columns multiply cycle bias; matrix entries are metres/cycle.

    row_indices refer to the unmodified original model, including after subset.
    Receiver attribution is not identifiable from SD alone: receiver1 and
    receiver2 designs differ only by sign when fault amplitude is unrestricted.
    """
    matrix: np.ndarray
    hypotheses: tuple[PhaseFaultHypothesis, ...]
    row_indices: tuple[int, ...]
    original_row_count: int

    def subset(self, rows: Sequence[int]) -> "PhaseFaultMap":
        selected = _rows(rows, self.original_row_count)
        lookup = {r: i for i, r in enumerate(self.row_indices)}
        if not set(selected) <= set(lookup):
            raise TemporalModelError("fault map lacks requested original rows")
        return PhaseFaultMap(self.matrix[[lookup[r] for r in selected]].copy(),
                             self.hypotheses, selected, self.original_row_count)


@dataclass(frozen=True)
class FixedIntegerGLS:
    rows_retained: tuple[int, ...]
    rows_withheld: tuple[int, ...]
    unknown_labels: tuple[str, ...]
    nuisance_estimate: np.ndarray
    nuisance_covariance: np.ndarray
    baseline_rank: int
    nuisance_dimension: int
    residual_df: int
    residual_cost: float
    nominal_p_value: float | None
    whitened_residual: np.ndarray
    whitened_design: np.ndarray
    nuisance_basis: np.ndarray
    cholesky: np.ndarray
    original_row_count: int
    accepted_integer_measurement: bool = False

    @property
    def bhat(self) -> np.ndarray:
        return self.nuisance_estimate

    @property
    def Cb(self) -> np.ndarray:
        """GLS covariance only if full rank; otherwise a labelled pseudoinverse."""
        return self.nuisance_covariance


@dataclass(frozen=True)
class SingleFaultScore:
    key: str
    status: str
    information_cycles_inverse2: float
    bias_cycles: float | None
    bias_standard_error_cycles: float | None
    improvement: float | None
    residual_cost: float | None
    incremental_df: int
    nominal_p_value: float | None
    holm_p_value: float | None
    nominal_reject_null: bool
    equivalent_hypotheses: tuple[str, ...]


@dataclass(frozen=True)
class FaultDiagnosis:
    scores: tuple[SingleFaultScore, ...]
    ranked_ties: tuple[tuple[str, ...], ...]
    best_hypotheses: tuple[str, ...]
    tested_hypotheses: int
    family_alpha: float
    unobservable_hypotheses: tuple[str, ...]
    policy: str = "CONDITIONAL_GAUSSIAN_SINGLE_FAULT_HOLM_NOT_CAUSE_CERTIFICATION"
    accepted_integer_measurement: bool = False


def _rows(rows, count):
    if rows is None:
        return tuple(range(count))
    result = tuple(rows)
    if (any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer))
            or x < 0 or x >= count for x in result)
            or len(set(result)) != len(result)):
        raise TemporalModelError("rows must be unique original integer indices")
    return tuple(map(int, result))


def build_phase_fault_map(epoch: MultiGnssEpoch, *, rows=None,
                          receiver: str = "sd") -> PhaseFaultMap:
    """Build exact group SD-to-DD phase design without inferring per-DD faults.

    Positive sd bias follows the registered receiver difference. receiver1/receiver2 specify
    a positive error in that receiver's original phase. Observation reversal
    is supported only when explicitly recorded as GNSS1_MINUS_GNSS2 metadata.
    """
    if receiver not in ("sd", "receiver1", "receiver2"):
        raise TemporalModelError("receiver must be sd, receiver1 or receiver2")
    order = epoch.metadata.get("receiver_order")
    if order not in ("GNSS2_MINUS_GNSS1", "GNSS1_MINUS_GNSS2"):
        raise TemporalModelError("explicit receiver difference order required")
    orientation = 1. if order == "GNSS2_MINUS_GNSS1" else -1.
    sign = 1. if receiver == "sd" else orientation * (-1. if receiver == "receiver1" else 1.)
    count = len(epoch.y)
    a = np.asarray(epoch.A, float)
    labels = tuple(epoch.ambiguity_labels)
    if a.shape != (count, len(labels)) or not np.isfinite(a).all():
        raise TemporalModelError("invalid epoch ambiguity dimensions")
    selected = _rows(rows, count)
    columns, hypotheses, occupied = [], [], set()
    for group in epoch.groups:
        m = len(group.satellites)
        rr = tuple(group.row_indices)
        cc = tuple(group.ambiguity_indices)
        if (m < 1 or len(rr) != 2*m or len(cc) != m or len(set(rr)) != len(rr)
                or len(set(cc)) != len(cc) or any(r < 0 or r >= count for r in rr)
                or any(c < 0 or c >= len(labels) for c in cc)
                or occupied.intersection(rr)):
            raise TemporalModelError("invalid or overlapping group row mapping")
        occupied.update(rr)
        identities = (group.pivot, *group.satellites)
        if len(set(identities)) != m+1 or any(group_key(i) != group.key for i in identities):
            raise TemporalModelError("group signal identities mismatch")
        if tuple(labels[c] for c in cc) != tuple(group.ambiguity_labels):
            raise TemporalModelError("group ambiguity labels mismatch")
        wave = signal_spec(group.pivot).wavelength_m
        expected = np.zeros((2*m, len(labels)))
        expected[np.arange(m, 2*m), cc] = wave
        if not np.allclose(a[list(rr)], expected, rtol=1e-12, atol=1e-14):
            raise TemporalModelError("group A differs from registered code/phase DD rows")
        for identity in identities:
            vector = np.zeros(count)
            pivot = identity == group.pivot
            if pivot:
                vector[list(rr[m:])] = -sign*wave
                affected = tuple(group.ambiguity_labels)
            else:
                j = group.satellites.index(identity)
                vector[rr[m+j]] = sign*wave
                affected = (group.ambiguity_labels[j],)
            columns.append(vector)
            hypotheses.append(PhaseFaultHypothesis(
                f"{receiver}:{raw.identity_text(identity)}", identity, group.key,
                group.pivot, pivot, receiver, wave, affected,
                _signal_arc_token(identity, group)))
    if not columns:
        raise TemporalModelError("at least one DD group is required")
    if len({h.key for h in hypotheses}) != len(hypotheses):
        raise TemporalModelError("duplicate fault signal hypothesis")
    if np.any(a[[i for i in range(count) if i not in occupied]]):
        raise TemporalModelError("carrier row has no registered group")
    matrix = np.column_stack(columns)[list(selected)]
    return PhaseFaultMap(matrix, tuple(hypotheses), selected, count)



def _signal_arc_token(identity, group):
    """Recover only explicit target/pivot tokens from the registered JSON labels."""
    tokens = []
    for target, label in zip(group.satellites, group.ambiguity_labels):
        try:
            parts = json.loads(label)
        except (TypeError, ValueError):
            return None
        if (not isinstance(parts, list) or len(parts) != 4
                or not all(isinstance(v, str) and v for v in parts)
                or parts[0] != raw.identity_text(target)
                or parts[2] != raw.identity_text(group.pivot)):
            return None
        if identity == target:
            tokens.append(parts[1])
        if identity == group.pivot:
            tokens.append(parts[3])
    if not tokens:
        return None
    if len(set(tokens)) != 1:
        raise TemporalModelError("inconsistent signal arc tokens inside group")
    return tokens[0]


def stack_phase_fault_maps(maps: Sequence[PhaseFaultMap], *,
                           persistent: bool = False) -> PhaseFaultMap:
    """Align maps to concatenated original epoch rows, like assemble_epochs.

    By default each epoch has separate scalar-fault hypotheses. persistent=True
    is an explicit constant-cycle-amplitude alternative and merges only the
    same receiver/full signal/explicit SD-arc token. No continuity is inferred
    from satellite ID alone. A changed pivot changes row directions; changing
    either receiver arc creates a new column. An absent epoch contributes no
    observation and no evidence of physical persistence.
    """
    maps = tuple(maps)
    if not maps:
        raise TemporalModelError("cannot stack empty fault maps")
    specs, column, entries, all_rows = [], {}, [], []
    original_offset = 0
    for k, mapping in enumerate(maps):
        matrix = np.asarray(mapping.matrix, float)
        local_rows = _rows(mapping.row_indices, mapping.original_row_count)
        if matrix.shape != (len(local_rows), len(mapping.hypotheses)) or not np.isfinite(matrix).all():
            raise TemporalModelError("invalid stacked fault map")
        seen = set()
        for j, h in enumerate(mapping.hypotheses):
            if persistent and (not isinstance(h.sd_arc_token, str) or not h.sd_arc_token):
                raise TemporalModelError("persistent fault requires explicit SD arc token")
            identity = [h.receiver, raw.identity_text(h.signal), h.sd_arc_token]
            key = json.dumps(identity if persistent else [k, *identity], separators=(",", ":"))
            if key in seen:
                raise TemporalModelError("duplicate local fault identity")
            seen.add(key)
            if key not in column:
                column[key] = len(specs)
                specs.append(replace(h, key=key))
            else:
                old = specs[column[key]]
                if old.group != h.group or old.wavelength_m != h.wavelength_m:
                    raise TemporalModelError("inconsistent persistent fault signal model")
                specs[column[key]] = replace(old,
                    pivot=old.pivot if old.pivot == h.pivot else None,
                    is_pivot=old.is_pivot if old.is_pivot == h.is_pivot else None,
                    affected_ambiguity_labels=tuple(dict.fromkeys(
                        (*old.affected_ambiguity_labels, *h.affected_ambiguity_labels))))
            entries.append((len(all_rows), len(local_rows), column[key], matrix[:,j]))
        all_rows.extend(original_offset+r for r in local_rows)
        original_offset += mapping.original_row_count
    combined = np.zeros((len(all_rows), len(specs)))
    for start, count, col, vector in entries:
        combined[start:start+count, col] = vector
    return PhaseFaultMap(combined, tuple(specs), tuple(all_rows), original_offset)

def fixed_integer_gls(model, integers, *, rows=None) -> FixedIntegerGLS:
    """Fit free nuisance B for fixed exact integers, retaining the full Q.

    Works with one epoch or an already assembled temporal model whose B has
    independent per-epoch columns. Unknown arc integers withhold every dependent
    selected row. Code rows can remain. No zero substitution is scored.
    Rank-deficient B is allowed for diagnostic projection; its covariance is a
    pseudoinverse and must not be used as a full-rank baseline covariance.
    """
    y = np.asarray(model.y, float)
    a, b = np.asarray(model.A, float), np.asarray(model.B, float)
    labels = tuple(model.ambiguity_labels)
    q = positive_definite(model.Q, "fixed integer Q")
    if (y.ndim != 1 or len(y) == 0 or a.shape != (len(y), len(labels))
            or b.ndim != 2 or b.shape[0] != len(y) or b.shape[1] == 0
            or q.shape != (len(y), len(y))
            or len(set(labels)) != len(labels) or any(not isinstance(s, str) or not s for s in labels)
            or not all(np.isfinite(x).all() for x in (y, a, b))):
        raise TemporalModelError("invalid fixed integer model")
    if isinstance(integers, Mapping):
        known = np.array([label in integers for label in labels], dtype=bool)
        values = [integers[label] if known[i] else 0 for i, label in enumerate(labels)]
    else:
        if np.asarray(integers).shape != (len(labels),):
            raise TemporalModelError("fixed integer vector has wrong dimensions")
        values = list(integers)
        known = np.ones(len(labels), dtype=bool)
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer))
           or abs(int(v)) > 2**53-1 for v in values):
        raise TemporalModelError("fixed N must contain exactly represented integers")
    requested = _rows(rows, len(y))
    dependent = np.any(a[:, ~known] != 0, axis=1)
    kept = tuple(r for r in requested if not dependent[r])
    if not kept:
        raise TemporalModelError("no known-integer observation rows remain")
    withheld = tuple(i for i in range(len(y)) if i not in set(kept))
    chol = np.linalg.cholesky(q[np.ix_(kept, kept)])
    target = np.linalg.solve(chol, (y-a @ np.asarray(values, float))[list(kept)])
    design = np.linalg.solve(chol, b[list(kept)])
    u, s, vt = np.linalg.svd(design, full_matrices=False)
    tolerance = np.finfo(float).eps * max(design.shape) * (s[0] if len(s) else 0.)
    rank = int(np.sum(s > tolerance))
    basis = u[:, :rank]
    right = vt[:rank].T
    estimate = right @ ((basis.T @ target)/s[:rank])
    covariance = (right/(s[:rank]*s[:rank])) @ right.T
    residual = target-basis @ (basis.T @ target)
    cost = float(residual @ residual)
    df = len(kept)-rank
    p = float(gammaincc(df/2, cost/2)) if df > 0 else None
    return FixedIntegerGLS(kept, withheld, tuple(label for label,k in zip(labels,known) if not k),
                          estimate, (covariance+covariance.T)*.5, rank, b.shape[1],
                          df, cost, p, residual, design, basis, chol, len(y))


def single_fault_glrt(fit: FixedIntegerGLS, fault_map: PhaseFaultMap, *,
                      family_alpha: float = .01, alias_tolerance: float = 1e-10) -> FaultDiagnosis:
    """Test each specified scalar fault against fixed-N/free-B null, without editing.

    Residualized collinear designs (including sign reversals) are observational
    aliases. Equal likelihood improvements are returned as ties, never broken
    into a purported unique physical cause. Holm adjusts all estimable supplied
    hypotheses, even aliases; its scope does not include unseen search families,
    additional epochs, candidate selection or covariance tuning.
    """
    if not np.isfinite(family_alpha) or not 0 < family_alpha < 1:
        raise TemporalModelError("family alpha must be between zero and one")
    if not np.isfinite(alias_tolerance) or not 0 < alias_tolerance < .01:
        raise TemporalModelError("invalid alias tolerance")
    if fit.original_row_count != fault_map.original_row_count:
        raise TemporalModelError("fault and fit original row counts differ")
    matrix = np.asarray(fault_map.matrix, float)
    if (matrix.shape != (len(fault_map.row_indices), len(fault_map.hypotheses))
            or not np.isfinite(matrix).all() or not fault_map.hypotheses
            or len({h.key for h in fault_map.hypotheses}) != len(fault_map.hypotheses)):
        raise TemporalModelError("invalid fault map dimensions or hypotheses")
    _rows(fault_map.row_indices, fault_map.original_row_count)
    selected = fault_map.subset(fit.rows_retained).matrix
    white = np.linalg.solve(fit.cholesky, selected)
    projected = white-fit.nuisance_basis @ (fit.nuisance_basis.T @ white)
    norms = np.linalg.norm(projected, axis=0)
    original_norms = np.linalg.norm(white, axis=0)
    # Relative rank test: a whitened column fully absorbed by B is unobservable.
    estimable = (norms > alias_tolerance*original_norms) & (original_norms > 0)
    if fit.residual_df == 0:
        estimable[:] = False
    keys = tuple(h.key for h in fault_map.hypotheses)
    information = norms*norms
    indices = np.flatnonzero(estimable)
    raw_p, delta, bias, reduced, aliases = {}, {}, {}, {}, {}
    unit = np.zeros_like(projected)
    unit[:, indices] = projected[:, indices]/norms[indices]
    for i in indices:
        score = float(unit[:,i] @ fit.whitened_residual)
        delta[i] = score*score
        bias[i] = score/norms[i]
        resid = fit.whitened_residual-unit[:,i]*score
        reduced[i] = float(resid @ resid)
        raw_p[i] = math.erfc(abs(score)/math.sqrt(2.))
        aliases[i] = tuple(keys[j] for j in indices
                           if min(np.linalg.norm(unit[:,i]-unit[:,j]),
                                  np.linalg.norm(unit[:,i]+unit[:,j])) <= alias_tolerance)
    # Holm adjusted p-values are monotone in sorted raw p; aliases are not pruned.
    adjusted, running = {}, 0.
    for k, i in enumerate(sorted(indices, key=lambda j: raw_p[j])):
        running = max(running, (len(indices)-k)*raw_p[i])
        adjusted[i] = min(1., running)
    scores = []
    for i, key in enumerate(keys):
        if not estimable[i]:
            scores.append(SingleFaultScore(key, "UNOBSERVABLE_AFTER_NUISANCE",
                float(information[i]), None, None, None, None, 0, None, None, False, ()))
        else:
            status = "ALIASED" if len(aliases[i]) > 1 else "ESTIMABLE"
            scores.append(SingleFaultScore(key, status, float(information[i]),
                bias[i], 1./norms[i], delta[i], reduced[i], 1, raw_p[i],
                adjusted[i], adjusted[i] <= family_alpha, aliases[i]))
    # Treat numerical likelihood ties and projected-design aliases as tied.
    # Unioning prevents a roundoff-sized cost difference from splitting an alias.
    parent = {int(i): int(i) for i in indices}
    def leader(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for pos, i in enumerate(indices):
        for j in indices[pos+1:]:
            if keys[j] in aliases[i] or np.isclose(delta[i], delta[j],
                    rtol=alias_tolerance, atol=alias_tolerance):
                parent[leader(int(j))] = leader(int(i))
    groups = {}
    for i in indices:
        groups.setdefault(leader(int(i)), []).append(int(i))
    ranked = sorted(groups.values(), key=lambda group: (-max(delta[i] for i in group),
                    min(keys[i] for i in group)))
    ties = tuple(tuple(keys[i] for i in sorted(group, key=lambda j: keys[j])) for group in ranked)
    return FaultDiagnosis(tuple(scores), ties, ties[0] if ties else (), len(indices),
                          float(family_alpha), tuple(keys[i] for i in range(len(keys)) if not estimable[i]))
