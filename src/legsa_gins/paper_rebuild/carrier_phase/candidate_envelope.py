"""Complete numerical Gaussian-relaxation support and continuous azimuth covers.

One fixed raw residual-cost threshold is supplied externally, never a ratio or
best/second gap. Length constraints are relaxed, not solved: all returned integer
vectors are POSSIBLE support of the relaxation, not accepted fixed ambiguities.
For each vector the entire conditional baseline ellipsoid is covered, not only
its center. No sphere objective is used for pruning.

The certificate is for a floating-point working model with an explicitly reported
expanded threshold and guards. It is NOT rigorous interval arithmetic, physical
coverage calibration or a real-world false-fix probability. Ill conditioning,
resource limits and representation failures fail closed. Input likelihood and
all historical nuisance integer columns must already be the intended model.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time
import numpy as np

from ..horizontal_literature.ext01_clambda import RTKLIBLambdaBridge
from .temporal import TemporalProblem, TemporalModelError, joint_float, conditional_baselines
from .solver import checked_integer_vector, MAX_EXACT_INTEGER


@dataclass(frozen=True)
class CircularArc:
    start_rad: float                  # canonical [-pi, pi)
    width_rad: float                  # counterclockwise, in [0, 2pi]

    @property
    def full_circle(self):
        return self.width_rad >= 2*math.pi

    @property
    def center_rad(self):
        return _wrap(self.start_rad + self.width_rad/2)


def _wrap(angle):
    return (float(angle)+math.pi) % (2*math.pi)-math.pi


def enclosing_arc(arcs) -> CircularArc | None:
    """Smallest circular arc enclosing all input arcs; no angle averaging."""
    arcs = tuple(arcs)
    if not arcs:
        return None
    tau = 2*math.pi
    pieces = []
    for arc in arcs:
        if (not math.isfinite(arc.start_rad) or not math.isfinite(arc.width_rad)
                or not 0 <= arc.width_rad <= tau):
            raise TemporalModelError('invalid circular arc')
        if arc.full_circle:
            return CircularArc(-math.pi, tau)
        start = arc.start_rad % tau
        end = start + arc.width_rad
        if end <= tau:
            pieces.append((start, end))
        else:
            pieces.extend(((start, tau), (0., end-tau)))
    merged = []
    for lo, hi in sorted(pieces):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    gaps = [(merged[i+1][0]-merged[i][1], merged[i+1][0])
            for i in range(len(merged)-1)]
    gaps.append((merged[0][0]+tau-merged[-1][1], merged[0][0]))
    gap, start = max(gaps, key=lambda x:(x[0], -x[1]))
    # Outward angular rounding: never remove an input endpoint through subtraction.
    guard = 64*np.finfo(float).eps
    if gap <= 2*guard:
        return CircularArc(-math.pi, tau)
    return CircularArc(_wrap(start-guard), min(tau, tau-gap+2*guard))


@dataclass(frozen=True)
class IntegerDirectionEnvelope:
    integer: tuple[int, ...]
    gaussian_integer_cost: float
    remaining_raw_budget: float
    baseline_center_m: tuple[float, float, float]
    baseline_outer_radius_m: float
    horizontal_center_m: tuple[float, float]
    horizontal_outer_radius_m: float
    azimuth_outer_arc: CircularArc
    horizontal_origin_included: bool
    sphere_feasibility: str = 'NOT_TESTED_LENGTH_CONSTRAINT_RELAXED'


@dataclass(frozen=True)
class CandidateEnvelopeResult:
    status: str
    termination_reason: str
    numerical_support_complete: bool
    candidates: tuple[IntegerDirectionEnvelope, ...]
    azimuth_outer_arc: CircularArc | None
    raw_cost_threshold: float
    expanded_working_threshold: float | None
    floating_cost_guard: float | None
    float_residual_cost: float | None
    target_epoch: int
    target_time_s: float | None
    ambiguity_labels: tuple[str, ...]
    expanded_nodes: int
    integer_leaves: int
    elapsed_s: float
    condition_number: float | None
    maximum_objective_identity_error: float
    decorrelation_used: bool
    coverage_scope: str = 'NUMERICAL_OUTER_COVER_OF_FULL_GAUSSIAN_RELAXED_INTEGER_SUPPORT'
    rigorous_interval_certificate: bool = False
    integer_acceptance_defined: bool = False
    physical_coverage_probability: None = None
    false_fix_probability: None = None


def _det_integer(matrix):
    """Bareiss determinant over Python integers, used only for transform identity."""
    a = [[int(x) for x in row] for row in matrix]
    n, sign, previous = len(a), 1, 1
    if n == 1:
        return a[0][0]
    for k in range(n-1):
        pivot = next((j for j in range(k, n) if a[j][k]), None)
        if pivot is None:
            return 0
        if pivot != k:
            a[k], a[pivot] = a[pivot], a[k]
            sign = -sign
        value = a[k][k]
        for i in range(k+1, n):
            for j in range(k+1, n):
                numerator = a[i][j]*value-a[i][k]*a[k][j]
                if numerator % previous:
                    raise TemporalModelError('nonexact integer determinant elimination')
                a[i][j] = numerator//previous
            a[i][k] = 0
        previous = value
    return sign*a[-1][-1]


def _nearest_integers(center, low, high):
    left = math.floor(center)
    right = left+1
    while left >= low or right <= high:
        if left >= low and (right > high or abs(left-center) <= abs(right-center)):
            yield left
            left -= 1
        else:
            yield right
            right += 1


def enumerate_candidate_envelope(problem: TemporalProblem, raw_cost_threshold: float, *,
        lambda_library: str | Path | None, horizontal_axes,
        target_epoch: int = -1, node_limit: int = 100000,
        candidate_limit: int = 10000, timeout_s: float = 30.,
        max_condition_number: float = 1e12,
        absolute_cost_guard: float = 1e-9,
        relative_numerical_guard: float = 1e-10) -> CandidateEnvelopeResult:
    """Numerically enumerate a finite relaxed support and cover target azimuth.

    horizontal_axes has orthonormal rows [north/east] (or another explicitly
    declared horizontal coordinate pair) expressed in the baseline frame. The
    output is baseline azimuth, NOT robot yaw absent mounting/tilt qualification.
    None for lambda_library explicitly uses original integer coordinates, useful
    for low-dimensional local tests; otherwise only LAMBDA decorrelation is used.
    There is no best-two call, candidate preselection, reference or native nav.

    All resource-limit results keep partial diagnostics but publish NO union
    envelope. A COMPLETE result is still a conditional numerical relaxation, not
    proof of exact real arithmetic or a physically calibrated confidence set.
    """
    if not math.isfinite(raw_cost_threshold) or raw_cost_threshold < 0:
        raise TemporalModelError('fixed finite nonnegative raw cost threshold required')
    if (type(node_limit) is not int or node_limit < 1 or type(candidate_limit) is not int
            or candidate_limit < 1 or not math.isfinite(timeout_s) or timeout_s <= 0):
        raise TemporalModelError('positive finite enumeration budgets required')
    if (not math.isfinite(max_condition_number) or max_condition_number <= 1
            or not math.isfinite(absolute_cost_guard) or absolute_cost_guard <= 0
            or not math.isfinite(relative_numerical_guard) or not 0 < relative_numerical_guard < 1e-3):
        raise TemporalModelError('explicit positive numerical guards required')
    axes = np.array(horizontal_axes, float, copy=True)
    if (axes.shape != (2,3) or not np.isfinite(axes).all()
            or np.max(abs(axes@axes.T-np.eye(2))) > 1e-12):
        raise TemporalModelError('orthonormal explicit horizontal axes required')
    if type(target_epoch) is not int or not -problem.epoch_count <= target_epoch < problem.epoch_count:
        raise TemporalModelError('invalid target epoch')
    target_epoch %= problem.epoch_count
    started = time.monotonic()
    found, nodes, leaves = [], 0, 0
    floating = None
    guard = threshold = None
    identity_error = 0.
    used_decorrelation = lambda_library is not None

    def finish(reason, complete=False, numerical=False):
        items = tuple(sorted(found, key=lambda c:c.integer))
        status = ('COMPLETE_RELAXED_SUPPORT' if items else 'EMPTY_RELAXED_SUPPORT') if complete else (
            'UNQUALIFIED_NUMERICS' if numerical else 'INCOMPLETE_RELAXED_SUPPORT')
        return CandidateEnvelopeResult(status, reason, complete, items,
            enclosing_arc(c.azimuth_outer_arc for c in items) if complete else None,
            float(raw_cost_threshold), threshold, guard,
            None if floating is None else float(floating.residual_objective), target_epoch,
            float(problem.times[target_epoch]), tuple(problem.ambiguity_labels), nodes, leaves,
            time.monotonic()-started, None if floating is None else float(floating.condition_number),
            identity_error, used_decorrelation)

    try:
        floating = joint_float(problem)
        if (not math.isfinite(floating.condition_number)
                or floating.condition_number > max_condition_number):
            return finish('FLOAT_CONDITION_NUMBER', numerical=True)
        guard = absolute_cost_guard + relative_numerical_guard*max(
            1., float(raw_cost_threshold), abs(float(floating.residual_objective)))
        threshold = float(raw_cost_threshold)+guard
        radius2 = threshold-floating.residual_objective
        if radius2 < 0:
            return finish('FLOAT_RESIDUAL_EXCEEDS_EXPANDED_THRESHOLD', complete=True)
        m = problem.ambiguity_count
        if m < 1:
            raise TemporalModelError('at least one integer required')
        if lambda_library is None:
            transform = np.eye(m, dtype=np.int64)
        else:
            reduced = RTKLIBLambdaBridge(lambda_library).decorrelate(
                floating.ambiguity, floating.covariance_aa)
            transform = checked_integer_vector(reduced.transformation, name='decorrelation matrix')
        if transform.shape != (m,m) or abs(_det_integer(transform)) != 1:
            return finish('TRANSFORM_NOT_EXACT_UNIMODULAR', numerical=True)
        mean = transform.T@floating.ambiguity
        covariance = transform.T@floating.covariance_aa@transform
        covariance = (covariance+covariance.T)*.5
        if not np.isfinite(covariance).all() or np.linalg.cond(covariance) > max_condition_number:
            return finish('INTEGER_METRIC_CONDITION_NUMBER', numerical=True)
        weight = np.linalg.solve(covariance, np.eye(m))
        upper = np.linalg.cholesky((weight+weight.T)*.5).T
        if not np.isfinite(upper).all() or np.any(np.diag(upper) <= 0):
            return finish('NONFINITE_INTEGER_FACTOR', numerical=True)
        ss = problem.baseline_slices[target_epoch]
        cb = floating.conditional_covariance_b[ss,ss]
        cxy = axes@cb@axes.T
        # Outward engineering guards, not verified interval eigenvalue bounds.
        eig3 = float(np.linalg.eigvalsh(cb)[-1])*(1+relative_numerical_guard)
        eig2 = float(np.linalg.eigvalsh(cxy)[-1])*(1+relative_numerical_guard)
        if not math.isfinite(eig3+eig2) or eig3 <= 0 or eig2 <= 0:
            return finish('INVALID_CONTINUOUS_ENVELOPE_COVARIANCE', numerical=True)
        # Stack alternates nodes and lazy sibling iterators; huge ranges are not allocated.
        stack = [('node', m-1, (), 0.)]
        while stack:
            if time.monotonic()-started >= timeout_s:
                return finish('TIMEOUT')
            entry = stack.pop()
            if entry[0] == 'children':
                _, index, suffix, parent_cost, center, diagonal, iterator = entry
                z = next(iterator, None)
                if z is None:
                    continue
                stack.append(entry)
                cost = float(parent_cost+(diagonal*(center-z))**2)
                if cost <= radius2+guard:
                    stack.append(('node', index-1, (z,)+suffix, cost))
                continue
            _, index, suffix, cost = entry
            if nodes >= node_limit:
                return finish('NODE_LIMIT')
            nodes += 1
            if index >= 0:
                assigned = np.asarray(suffix, float)
                cross = float(upper[index,index+1:]@(mean[index+1:]-assigned)) if suffix else 0.
                diagonal = float(upper[index,index])
                center = float(mean[index]+cross/diagonal)
                rad = math.sqrt(max(0., radius2-cost+guard))/diagonal
                lo = math.ceil(np.nextafter(center-rad, -math.inf))
                hi = math.floor(np.nextafter(center+rad, math.inf))
                if lo < -MAX_EXACT_INTEGER or hi > MAX_EXACT_INTEGER:
                    return finish('INTEGER_REPRESENTATION_DOMAIN_EXCEEDED', numerical=True)
                if lo <= hi:
                    stack.append(('children', index, suffix, cost, center, diagonal,
                                  _nearest_integers(center,lo,hi)))
                continue
            leaves += 1
            original = np.linalg.solve(transform.T.astype(float), np.asarray(suffix,float))
            integer = checked_integer_vector(np.rint(original), name='enumerated integer')
            if (not np.allclose(original, integer, atol=1e-7, rtol=0.)
                    or any(sum(int(transform[j,i])*int(integer[j]) for j in range(m)) != suffix[i]
                           for i in range(m))):
                return finish('INTEGER_BACK_TRANSFORM_FAILED', numerical=True)
            delta = integer-floating.ambiguity
            metric = float(delta@np.linalg.solve(floating.covariance_aa,delta))
            if not math.isfinite(metric) or abs(metric-cost) > guard*(1+abs(metric)):
                return finish('INTEGER_METRIC_RECONSTRUCTION_FAILED', numerical=True)
            if metric > radius2:
                continue
            centers = conditional_baselines(floating,integer)
            residual = floating.whitened_y-floating.whitened_A@integer-floating.whitened_B@centers.reshape(-1)
            full = float(residual@residual)
            error = abs(full-(floating.residual_objective+metric))
            identity_error = max(identity_error,error)
            if not np.isfinite(centers).all() or not math.isfinite(full) or error > guard*(1+abs(full)):
                return finish('RAW_OBJECTIVE_RECONSTRUCTION_FAILED', numerical=True)
            if len(found) >= candidate_limit:
                return finish('CANDIDATE_LIMIT')
            budget = max(0.,threshold-floating.residual_objective-metric)
            center3 = centers[target_epoch]
            center2 = axes@center3
            r3, r2 = math.sqrt(budget*eig3), math.sqrt(budget*eig2)
            h = float(np.linalg.norm(center2))
            position_guard = relative_numerical_guard*max(float(np.linalg.norm(center3)), r3,
                                                        float(problem.lengths[target_epoch]),np.finfo(float).tiny)
            r3 += position_guard
            r2 += position_guard
            origin = h <= r2
            if origin:
                arc = CircularArc(-math.pi,2*math.pi)
            else:
                alpha = math.asin(min(1.,r2/h))
                arc = CircularArc(_wrap(math.atan2(center2[1],center2[0])-alpha),2*alpha)
            found.append(IntegerDirectionEnvelope(tuple(map(int,integer)),metric,budget,
                tuple(map(float,center3)),r3,tuple(map(float,center2)),r2,arc,origin))
        return finish('GAUSSIAN_RELAXED_DOMAIN_EXHAUSTED',complete=True)
    except (TemporalModelError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
        return finish(type(exc).__name__+': '+str(exc),numerical=True)
