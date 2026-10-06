"""One-shot fixed-candidate shadow gates with an explicit full future covariance.

For true fixed N and a specified zero-mean Gaussian future model, joint free-B
GLS gives S ~ chi2(n-rank(B)). With full rank 3K, each marginal estimator
bhat_k has covariance Cb[k,k]. Its distance D_k to the known-length sphere is
bounded above by the Mahalanobis error to the true b_k, hence by chi2(3).
Residual alpha/2 and K length tests alpha/(2K) give a Bonferroni rejection
bound without independence between future epochs or between the tests.

This is NOT a product-of-spheres likelihood minimization. The sum of marginal
D_k values is diagnostic, not a joint sphere objective. Supplying a marginal
future Q also does NOT remove dependence on observations that selected N.
Selection independence (or an independently qualified conditional model) is
an explicit working assumption; false-fix probability is never produced.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import numpy as np
from scipy.stats import chi2

from .admission import FrozenCandidate, AdmissionConfig
from .faults import fixed_integer_gls
from .temporal import EpochBlock, TemporalModelError, assemble_epochs, positive_definite
from ..horizontal_literature.ext01_clambda import constrained_baseline


@dataclass(frozen=True)
class JointAdmissionConfig:
    validation_epochs: int = 5
    epoch_interval_s: float = .2
    time_tolerance_s: float = .01
    minimum_phase_rows: int = 3
    length_m: float = .350
    alpha_total: float = .01
    selection_independent_working_model: bool = False

    def __post_init__(self):
        # Reuse the established validation-slot and physical-config validation.
        AdmissionConfig(self.validation_epochs, self.epoch_interval_s,
                        self.time_tolerance_s, self.minimum_phase_rows,
                        self.length_m, self.alpha_total)
        if not isinstance(self.selection_independent_working_model, bool):
            raise TemporalModelError("selection independence flag must be boolean")


@dataclass(frozen=True)
class JointEpochSupport:
    time_s: float
    slot_index: int
    rows_retained: tuple[int, ...]
    rows_withheld: tuple[int, ...]
    validated_active_labels: tuple[str, ...]
    unknown_labels: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class JointLengthGate:
    time_s: float
    penalty: float
    df: int
    threshold: float
    conservative_nominal_p_value: float
    nominal_alpha: float
    passes: bool
    baseline_center_m: tuple[float, ...]
    baseline_covariance_m2: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class JointCandidateGate:
    candidate_id: str
    residual_cost: float
    residual_df: int
    residual_threshold: float
    residual_nominal_p_value: float
    residual_pass: bool
    length_gates: tuple[JointLengthGate, ...]
    length_pass: bool
    length_penalty_sum: float
    joint_baseline_center_m: tuple[float, ...]
    joint_baseline_covariance_m2: tuple[tuple[float, ...], ...]
    baseline_rank: int
    retained_global_rows: tuple[int, ...]
    full_joint_sphere_cost_computed: bool = False

    @property
    def passes(self):
        return self.residual_pass and self.length_pass


@dataclass(frozen=True)
class JointAdmissionDecision:
    status: str
    shadow_accepted: bool
    shadow_candidate_id: str | None
    selected_at: float
    expected_future_times: tuple[float, ...]
    observed_future_times: tuple[float, ...]
    complete_future_support: bool
    validated_labels: tuple[str, ...]
    unvalidated_selected_labels: tuple[str, ...]
    primary: JointCandidateGate | None
    competitor: JointCandidateGate | None
    epochs: tuple[JointEpochSupport, ...]
    reasons: tuple[str, ...]
    primary_fingerprint: str
    competitor_fingerprint: str
    covariance_source_id: str
    covariance_sha256: str | None
    full_future_covariance_provided: bool
    selection_independent_working_model: bool
    alpha_total_registered: float
    alpha_correct_candidate_nominal_type_i: float | None
    assumptions: tuple[str, ...]
    false_fix_probability: None = None
    accepted_integer_measurement: bool = False
    production_measurement: bool = False
    all_integer_alternatives_tested: bool = False


class JointCausalAdmissionSession:
    """Freeze Q and candidates before consuming fixed future slots exactly once.

    Q is for ALL original rows, epoch-major, and its diagonal epoch blocks must
    equal each registered EpochBlock.Q. Common known-integer row masks select a
    covariance principal submatrix only after assembling that full matrix.
    Q is copied, never inferred, inflated, fitted or diagonalized by this class.
    """
    def __init__(self, primary: FrozenCandidate, competitor: FrozenCandidate, *,
                 future_covariance, covariance_source_id: str,
                 config: JointAdmissionConfig = JointAdmissionConfig()):
        if primary.selected_at != competitor.selected_at:
            raise TemporalModelError("both candidates must have the same selection time")
        if primary.active_labels != competitor.active_labels:
            raise TemporalModelError("competitors must use identical active-label support")
        if primary.candidate_id == competitor.candidate_id:
            raise TemporalModelError("candidate identifiers must differ")
        if not isinstance(covariance_source_id, str) or not covariance_source_id:
            raise TemporalModelError("explicit covariance provenance identifier required")
        self._covariance = None
        self._covariance_sha256 = None
        if future_covariance is not None:
            self._covariance = positive_definite(future_covariance, "full future Q").copy()
            self._covariance_sha256 = hashlib.sha256(
                np.asarray(self._covariance, dtype="<f8").tobytes()).hexdigest()
            self._covariance.setflags(write=False)
        self._source = covariance_source_id
        self._primary, self._competitor, self._config = primary, competitor, config
        self._times = tuple(primary.selected_at+(k+1)*config.epoch_interval_s
                            for k in range(config.validation_epochs))
        self._records, self._blocks = {}, {}
        self._last_time, self._closed = primary.selected_at, False
        left, right = primary.integers, competitor.integers
        self._same_active_class = all(left[label] == right[label] for label in primary.active_labels)

    @property
    def state(self):
        return "FINALIZED" if self._closed else "COLLECTING"

    @property
    def expected_future_times(self):
        return self._times

    def observe(self, block: EpochBlock) -> JointEpochSupport:
        if self._closed:
            raise TemporalModelError("joint admission session already finalized")
        time_s = float(block.time_s)
        if (not math.isfinite(time_s) or time_s <= self._primary.selected_at
                or time_s <= self._last_time):
            raise TemporalModelError("validation must be strictly future and time ordered")
        slot = int(np.argmin(np.abs(np.asarray(self._times)-time_s)))
        if abs(self._times[slot]-time_s) > self._config.time_tolerance_s:
            raise TemporalModelError("observation outside registered future slots")
        if slot in self._records:
            raise TemporalModelError("duplicate validation slot")
        labels = tuple(block.ambiguity_labels)
        y, a, b = (np.asarray(x, float) for x in (block.y, block.A, block.B))
        q = positive_definite(block.Q, "epoch marginal Q")
        if (y.ndim != 1 or len(y) == 0 or a.shape != (len(y), len(labels))
                or b.shape != (len(y), 3) or q.shape != (len(y), len(y))
                or not labels or len(set(labels)) != len(labels)
                or any(not isinstance(label, str) or not label for label in labels)
                or not all(np.isfinite(x).all() for x in (y, a, b))):
            raise TemporalModelError("invalid future observation model")
        left, right = self._primary.integers, self._competitor.integers
        known = np.array([label in left and label in right for label in labels])
        withheld = np.any(a[:, ~known] != 0, axis=1)
        rows = tuple(map(int, np.flatnonzero(~withheld)))
        phase_count = int(np.sum(np.any(a[list(rows)] != 0, axis=1)))
        observed = {labels[i] for i in range(len(labels)) if np.any(a[list(rows), i] != 0)}
        validated = tuple(label for label in self._primary.active_labels if label in observed)
        unknown = tuple(label for label, present in zip(labels, known) if not present)
        reason = None
        if len(validated) != len(self._primary.active_labels):
            reason = "UNRESOLVED_ACTIVE_ARC_CHANGED"
        if phase_count < self._config.minimum_phase_rows:
            reason = reason or "UNRESOLVED_INSUFFICIENT_PHASE_SUPPORT"
        record = JointEpochSupport(time_s, slot, rows, tuple(map(int, np.flatnonzero(withheld))),
                                   validated, unknown, reason)
        # Freeze observation arrays too: mutating caller-owned buffers cannot
        # rewrite the evidence consumed by an in-progress session.
        saved = EpochBlock(time_s, y.copy(), a.copy(), b.copy(), q.copy(), labels,
                           dict(getattr(block, "metadata", {})))
        self._records[slot], self._blocks[slot] = record, saved
        self._last_time = time_s
        return record

    def _gate(self, candidate, problem, rows, records):
        fit = fixed_integer_gls(problem, candidate.integers, rows=rows)
        k = len(records)
        if fit.baseline_rank != 3*k or fit.residual_df != len(rows)-3*k or fit.residual_df <= 0:
            raise TemporalModelError("joint free baseline rank or residual dimension unsupported")
        if fit.rows_retained != rows:
            raise TemporalModelError("candidate common support changed in joint GLS")
        alpha = self._config.alpha_total
        residual_threshold = float(chi2.isf(alpha/2, fit.residual_df))
        length_alpha = alpha/(2*k)
        length_threshold = float(chi2.isf(length_alpha, 3))
        length_gates = []
        for j, record in enumerate(records):
            sl = slice(3*j, 3*j+3)
            center = fit.bhat[sl]
            marginal = fit.Cb[sl, sl]
            # This is a marginal covariance, not an epoch-only fit covariance
            # or a conditional covariance obtained by a Schur complement.
            sphere = constrained_baseline(center, marginal, self._config.length_m)
            penalty = float(sphere.objective)
            length_gates.append(JointLengthGate(record.time_s, penalty, 3,
                length_threshold, float(chi2.sf(penalty, 3)), length_alpha,
                penalty <= length_threshold, tuple(map(float, center)),
                tuple(tuple(map(float, row)) for row in marginal)))
        return JointCandidateGate(candidate.candidate_id, fit.residual_cost, fit.residual_df,
            residual_threshold, float(chi2.sf(fit.residual_cost, fit.residual_df)),
            fit.residual_cost <= residual_threshold, tuple(length_gates),
            all(g.passes for g in length_gates), sum(g.penalty for g in length_gates),
            tuple(map(float, fit.bhat)), tuple(tuple(map(float, row)) for row in fit.Cb),
            fit.baseline_rank, fit.rows_retained)

    def finalize(self) -> JointAdmissionDecision:
        if self._closed:
            raise TemporalModelError("joint admission session already finalized")
        self._closed = True
        records = tuple(self._records[k] for k in sorted(self._records))
        blocks = tuple(self._blocks[k] for k in sorted(self._blocks))
        complete = len(records) == self._config.validation_epochs
        validated = set(self._primary.active_labels) if complete else set()
        for record in records:
            validated.intersection_update(record.validated_active_labels)
        valid = tuple(label for label in self._primary.active_labels if label in validated)
        missing = tuple(label for label in self._primary.active_labels if label not in validated)
        reasons = list(dict.fromkeys(record.reason for record in records if record.reason))
        primary = competitor = None
        if complete and self._covariance is not None:
            try:
                problem = assemble_epochs(blocks, self._config.length_m,
                                          temporal_covariance=self._covariance)
                rows = tuple(rr.start+local for rr, record in zip(problem.row_slices, records)
                             for local in record.rows_retained)
                primary = self._gate(self._primary, problem, rows, records)
                competitor = self._gate(self._competitor, problem, rows, records)
            except (ValueError, np.linalg.LinAlgError) as exc:
                primary = competitor = None
                reasons.append("UNRESOLVED_JOINT_GEOMETRY_OR_MODEL: "+str(exc))
        if self._covariance is None:
            status = "UNRESOLVED_COVARIANCE_UNAVAILABLE"
        elif not complete:
            status = "UNRESOLVED_MISSING_FUTURE_SUPPORT"
        elif not self._config.selection_independent_working_model:
            status = "UNRESOLVED_SELECTION_DEPENDENCE"
        elif self._same_active_class:
            status = "UNRESOLVED_SAME_ACTIVE_CLASS"
        elif missing:
            status = "UNRESOLVED_ACTIVE_ARC_CHANGED"
        elif reasons or primary is None or competitor is None:
            status = "UNRESOLVED_INSUFFICIENT_VALIDATION"
        elif not primary.residual_pass and not primary.length_pass:
            status = "REJECTED_RESIDUAL_AND_LENGTH"
        elif not primary.residual_pass:
            status = "REJECTED_RESIDUAL"
        elif not primary.length_pass:
            status = "REJECTED_LENGTH"
        elif competitor.passes:
            status = "UNRESOLVED_COMPETITION"
        else:
            status = "JOINT_SHADOW_ACCEPTED"
        accepted = status == "JOINT_SHADOW_ACCEPTED"
        return JointAdmissionDecision(status, accepted,
            self._primary.candidate_id if accepted else None, self._primary.selected_at,
            self._times, tuple(r.time_s for r in records), complete, valid, missing,
            primary, competitor, records, tuple(dict.fromkeys(reasons)),
            self._primary.fingerprint, self._competitor.fingerprint, self._source,
            self._covariance_sha256, self._covariance is not None,
            self._config.selection_independent_working_model, self._config.alpha_total,
            self._config.alpha_total if (self._config.selection_independent_working_model
                and complete and primary is not None and competitor is not None) else None,
            ("registered full future Q and zero-mean Gaussian observation model are correct",
             "validation noise is independent of candidate selection, or an explicit conditional model is qualified",
             "retained support is pre-specified or its conditional Gaussian law is qualified",
             "geometry and the registered true baseline length are correct",
             "future epochs may be correlated; no independence between length tests is required",
             "the fixed registered future horizon is used exactly once",
             "only the frozen competitor is tested; no bound on omitted integer alternatives"))
