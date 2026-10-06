"""Experimental two-epoch relative-motion integer search with bound intervals.

Same integer/observation likelihood as the temporal model; no absolute attitude,
reference or navigation state input. A certified integer ordering is conditional
on this model, not acceptance, true integers, or a calibrated false-fix risk.
Only independent epochs, equal fixed length and two baseline vectors are supported.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
import time
import numpy as np

from ..horizontal_literature.ext01_clambda import (
    BaselineSphereMetric, RTKLIBLambdaBridge)
from .native_sphere import NativeSphereBackend
from .solver import _require_separable, checked_integer_vector, MAX_EXACT_INTEGER
from .temporal import TemporalModelError, joint_float, conditional_baselines

def vector_angle(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != (3,) or b.shape != (3,) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise TemporalModelError("finite three-vector required")
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na <= 0 or nb <= 0:
        raise TemporalModelError("nonzero vector required")
    a, b = a / na, b / nb
    return math.atan2(float(np.linalg.norm(np.cross(a, b))), float(a @ b))

@dataclass(frozen=True)
class PairMotionConstraint:
    beta_lower_rad: float
    beta_upper_rad: float
    source_id: str
    rotation_error_interpretation: str = "REGISTERED_MODEL_BOUND_NOT_PHYSICAL_CERTAINTY"

    def __post_init__(self):
        lo, hi = self.beta_lower_rad, self.beta_upper_rad
        if not (math.isfinite(lo) and math.isfinite(hi) and 0 <= lo <= hi <= math.pi):
            raise TemporalModelError("invalid relative-baseline angle interval")
        if not isinstance(self.source_id, str) or not self.source_id:
            raise TemporalModelError("relative-motion source identity required")

    @classmethod
    def from_relative_rotation(cls, body_baseline, relative_rotation, epsilon_rad, *, source_id):
        r = np.asarray(body_baseline, float)
        rot = np.asarray(relative_rotation, float)
        if rot.shape != (3, 3) or not np.isfinite(rot).all():
            raise TemporalModelError("finite relative rotation required")
        if (np.max(abs(rot.T @ rot - np.eye(3))) > 1e-10
                or abs(np.linalg.det(rot) - 1) > 1e-10):
            raise TemporalModelError("relative rotation must be SO(3)")
        if not math.isfinite(epsilon_rad) or not 0 <= epsilon_rad <= math.pi:
            raise TemporalModelError("geodesic rotation error must lie in [0,pi]")
        beta = vector_angle(r, rot @ r)
        return cls(max(0., beta-epsilon_rad), min(math.pi, beta+epsilon_rad), source_id)

    def discrepancy(self, angle):
        return max(self.beta_lower_rad-angle, angle-self.beta_upper_rad, 0.)

def angle_motion_increment(mu1, mu2, length, delta):
    """Necessary cost increment, stable at equal large curvatures/small angle."""
    if (not all(math.isfinite(v) for v in (mu1, mu2, length, delta))
            or mu1 < 0 or mu2 < 0 or length <= 0 or not 0 <= delta <= math.pi):
        raise TemporalModelError("invalid angular-bound input")
    if mu1 == 0 or mu2 == 0 or delta == 0:
        return 0.
    scale = max(mu1, mu2)
    a, b = mu1 / scale, mu2 / scale
    denominator = a+b+math.hypot(a-b, 2*math.sqrt(a*b)*math.cos(delta/2))
    return 8*length*length*scale*a*b*math.sin(delta/2)**2/denominator

def feasible_pair(first, second, length, beta, mu1=1., mu2=1.):
    """Construct a pair on both spheres with the requested angle; no minimizer claim."""
    u = np.asarray(first, float) / np.linalg.norm(first)
    v = np.asarray(second, float) / np.linalg.norm(second)
    gamma = vector_angle(u, v)
    tangent = v-float(u @ v)*u
    if np.linalg.norm(tangent) < 1e-10:
        axis = np.eye(3)[int(np.argmin(abs(u)))]
        tangent = axis-float(axis @ u)*u
    tangent /= np.linalg.norm(tangent)
    delta = abs(gamma-beta)
    if delta == 0:
        shift = 0.
    elif mu1+mu2 == 0:
        shift = delta/2
    else:
        # Maximizer of mu1*cos(d1)+mu2*cos(delta-d1), constrained to [0,delta].
        shift = min(delta, max(0., math.atan2(mu2*math.sin(delta), mu1+mu2*math.cos(delta))))
    start = math.copysign(shift, gamma-beta)
    b1 = length*(math.cos(start)*u+math.sin(start)*tangent)
    b2 = length*(math.cos(start+beta)*u+math.sin(start+beta)*tangent)
    return np.array([b1, b2])

@dataclass(frozen=True)
class PairCandidate:
    ambiguity: np.ndarray
    baselines: np.ndarray
    independent_baselines: np.ndarray
    independent_reduced_cost: float
    lower_reduced_cost: float
    upper_reduced_cost: float
    raw_upper_cost: float
    extra_motion_lower_bound: float
    independent_angle_rad: float
    feasible_angle_rad: float
    curvature: tuple[float, float]
    numerical_margin: float
    maximum_length_error_m: float
    profile_closed_numerically: bool
    local_refinement_used: bool

class PairEvaluator:
    """Full-N interval evaluation; lower bounds are not valid for partial N."""
    def __init__(self, problem, constraint, *, sphere_library=None):
        if problem.epoch_count != 2 or not np.all(problem.lengths == problem.lengths[0]):
            raise TemporalModelError("exactly two equal-length baseline epochs required")
        self.problem, self.constraint = problem, constraint
        self.floating = joint_float(problem)
        _require_separable(problem, self.floating)
        self.length = float(problem.lengths[0])
        self.backend = None if sphere_library is None else NativeSphereBackend(sphere_library)
        self.metrics = []
        self.weights = []
        for part in problem.baseline_slices:
            metric = BaselineSphereMetric.from_covariance(self.floating.conditional_covariance_b[part, part])
            self.weights.append(metric.weight)
            self.metrics.append(metric if self.backend is None else self.backend.from_covariance(
                self.floating.conditional_covariance_b[part, part]))
        self.integer_weight = np.linalg.solve(self.floating.covariance_aa,
                                             np.eye(problem.ambiguity_count))

    def __call__(self, integer, *, refine_iterations=0):
        n = checked_integer_vector(integer)
        if n.shape != self.floating.ambiguity.shape:
            raise TemporalModelError("wrong integer dimension")
        d = n-self.floating.ambiguity
        ambiguity_cost = float(d @ self.integer_weight @ d)
        centers = conditional_baselines(self.floating, n)
        spheres = [metric.solve(center, self.length)
                   for metric, center in zip(self.metrics, centers)]
        # Normalize the numerical solution, then bound any stationarity defect.
        points = np.array([s.baseline*self.length/np.linalg.norm(s.baseline) for s in spheres])
        costs, mu, margins = [], [], []
        for center, s, point, weight in zip(centers, spheres, points, self.weights):
            delta = point-center
            costs.append(float(delta @ weight @ delta))
            h = weight+s.lagrange_multiplier*np.eye(3)
            spectral_guard = 128*np.finfo(float).eps*max(1., float(np.linalg.norm(h, 2)))
            low = float(np.linalg.eigvalsh(h)[0])-spectral_guard
            mu.append(max(0., low))
            residual = h @ point-weight @ center
            margins.append(4*self.length*np.linalg.norm(residual)
                           +4*self.length**2*max(0., -low))
        independent = ambiguity_cost+sum(costs)
        gamma = vector_angle(*points)
        delta = self.constraint.discrepancy(gamma)
        increment = angle_motion_increment(*mu, self.length, delta)
        beta = min(self.constraint.beta_upper_rad, max(self.constraint.beta_lower_rad, gamma))
        pair = feasible_pair(*points, self.length, beta, *mu)
        def cost(pair_):
            return ambiguity_cost+sum(float((v-c) @ w @ (v-c))
                                      for v, c, w in zip(pair_, centers, self.weights))
        upper = cost(pair)
        used = False
        if refine_iterations > 0 and delta > 0:
            from scipy.optimize import minimize
            from scipy.spatial.transform import Rotation
            u = pair[0]/self.length
            t = pair[1]/self.length-math.cos(beta)*u
            if np.linalg.norm(t) < 1e-10:
                axis = np.eye(3)[int(np.argmin(abs(u)))]
                t = axis-float(axis @ u)*u
            t /= np.linalg.norm(t)
            def decode(x):
                rotation = Rotation.from_rotvec(x[:3]).as_matrix()
                return self.length*np.array([rotation @ u,
                    rotation @ (math.cos(x[3])*u+math.sin(x[3])*t)])
            result = minimize(lambda x:cost(decode(x)), np.r_[np.zeros(3), beta],
                method="L-BFGS-B", bounds=[(None,None)]*3+
                    [(self.constraint.beta_lower_rad,self.constraint.beta_upper_rad)],
                options={"maxiter":int(refine_iterations), "ftol":1e-12, "maxls":20})
            used = True
            if np.isfinite(result.x).all():
                proposed = decode(result.x)
                proposed_cost = cost(proposed)
                if (proposed_cost < upper and self.constraint.discrepancy(vector_angle(*proposed)) <= 1e-10):
                    pair, upper = proposed, proposed_cost
        raw_residual = (self.floating.whitened_y-self.floating.whitened_A @ n
                        -self.floating.whitened_B @ pair.reshape(-1))
        raw = float(raw_residual @ raw_residual)
        identity_error = abs(raw-self.floating.residual_objective-upper)
        if identity_error > 2e-6+2e-8*max(raw, upper):
            raise TemporalModelError("motion candidate objective completion mismatch")
        margin = float(sum(margins)+identity_error+
                       1e-10*(1+abs(independent)+abs(increment)+abs(upper)))
        lower = max(0., independent+increment-margin)
        scalars = [ambiguity_cost, independent, increment, upper, raw, margin, lower,
                   *mu, *(v.lagrange_multiplier for v in spheres)]
        if not all(math.isfinite(float(v)) for v in scalars):
            raise TemporalModelError("nonfinite motion candidate interval")
        if lower > upper+margin:
            raise TemporalModelError("motion lower bound exceeds feasible upper")
        # Preserve ordered intervals when the mismatch lies within the numerical guard.
        lower = min(lower, upper)
        angle = vector_angle(*pair)
        length_error = float(np.max(abs(np.linalg.norm(pair,axis=1)-self.length)))
        if length_error > 1e-10 or self.constraint.discrepancy(angle) > 1e-10:
            raise TemporalModelError("motion upper point is not feasible")
        return PairCandidate(n, pair, points, independent, lower, upper, raw,
            increment, gamma, angle, tuple(mu), margin, length_error,
            upper-lower <= max(2e-7,2e-8*(1+abs(upper))), used)

@dataclass(frozen=True)
class PairSearchResult:
    best: PairCandidate | None
    second: PairCandidate | None
    candidates: tuple[PairCandidate, ...]
    search_complete: bool
    integer_winner_separated: bool
    integer_top_two_separated: bool
    termination_reason: str
    nodes: int
    leaves: int
    remaining_frontier_lower_bound: float | None
    elapsed_s: float
    integer_acceptance_defined: bool = False
    integer_truth_known: bool = False
    certificate_scope: str = "NUMERICAL_INTEGER_ORDERING_FROM_FEASIBLE_UPPER_AND_ADMISSIBLE_LOWER"
    continuous_profile_global_optimum_certified: bool = False

def solve_motion_pair(problem, constraint, lambda_library, *, sphere_library=None,
        initial_candidates=8, node_limit=100000, timeout_s=60., refine_iterations=0):
    """Full-dimensional search, never just reordering independent-model top-two.

    Numerical interval separation may establish integer ordering while leaving
    the nonlinear continuous optimum open. Search/time failures stay unresolved.
    """
    if (initial_candidates < 2 or node_limit < 1 or not math.isfinite(timeout_s)
            or timeout_s <= 0 or refine_iterations < 0):
        raise TemporalModelError("invalid bounded motion search settings")
    start = time.monotonic()
    evaluator = PairEvaluator(problem, constraint, sphere_library=sphere_library)
    floating = evaluator.floating
    bridge = RTKLIBLambdaBridge(lambda_library)
    reduced = bridge.decorrelate(floating.ambiguity, floating.covariance_aa)
    checked_integer_vector(reduced.transformation, name="LAMBDA transformation")
    candidates = {}
    nodes = leaves = 0
    frontier_floor = None
    def ordered():
        return sorted(candidates.values(), key=lambda c:(c.upper_reduced_cost,tuple(c.ambiguity)))
    def finish(reason, complete):
        values = ordered()
        best = values[0] if values else None
        second = values[1] if len(values)>1 else None
        guard = 1e-8*(1+(0. if second is None else second.upper_reduced_cost))
        winner = (complete and second is not None
                  and best.upper_reduced_cost+guard < min(c.lower_reduced_cost for c in values[1:]))
        top_two = (winner and (len(values)<3 or second.upper_reduced_cost+guard <
                               min(c.lower_reduced_cost for c in values[2:])))
        return PairSearchResult(best, second, tuple(values), complete, winner, top_two,
            reason, nodes, leaves, frontier_floor, time.monotonic()-start)
    def evaluate(n):
        key = tuple(map(int, n))
        if key not in candidates:
            candidates[key] = evaluator(n, refine_iterations=refine_iterations)
    for seed in bridge.candidates(floating.ambiguity, floating.covariance_aa, initial_candidates):
        evaluate(seed.ambiguity)
        if time.monotonic()-start >= timeout_s:
            return finish("TIMEOUT_DURING_SEEDS", False)
    if len(candidates)<2:
        return finish("INSUFFICIENT_DISTINCT_SEEDS", False)
    incumbent = ordered()[1].upper_reduced_cost
    dimension = problem.ambiguity_count
    weight = np.linalg.solve(reduced.covariance, np.eye(dimension))
    upper = np.linalg.cholesky((weight+weight.T)*.5).T
    serial = 0
    # Integer Gaussian metric only: no numerical sphere objective used as a node bound.
    frontier = [(0.,serial,dimension-1,(),0.)]
    while frontier:
        frontier_floor = float(frontier[0][0])
        tolerance = 1e-8*(1+incumbent)
        if frontier_floor > incumbent+tolerance:
            return finish("GLOBAL_INTEGER_BRANCH_BOUND_CLOSED", True)
        if time.monotonic()-start >= timeout_s:
            return finish("SEARCH_TIMEOUT", False)
        if nodes >= node_limit:
            return finish("NODE_LIMIT", False)
        lower, _, index, suffix, metric = heapq.heappop(frontier)
        nodes += 1
        if index < 0:
            leaves += 1
            original = np.linalg.solve(reduced.transformation.T.astype(float), np.asarray(suffix,float))
            rounded = np.rint(original)
            if not np.allclose(original,rounded,rtol=0,atol=1e-7):
                raise TemporalModelError("integer back-transform mismatch")
            integer = checked_integer_vector(rounded)
            key = tuple(map(int,integer))
            if key not in candidates:
                candidate = evaluator(integer, refine_iterations=refine_iterations)
                delta = integer-floating.ambiguity
                actual_metric = float(delta @ evaluator.integer_weight @ delta)
                if not math.isclose(actual_metric, metric, rel_tol=2e-7, abs_tol=2e-7):
                    raise TemporalModelError("motion tree integer metric mismatch")
                candidates[key] = candidate
                incumbent = ordered()[1].upper_reduced_cost
            continue
        assigned = np.asarray(suffix,float)
        cross = float(upper[index,index+1:] @ (reduced.float_ambiguity[index+1:]-assigned)) if len(assigned) else 0.
        diagonal = float(upper[index,index])
        center = float(reduced.float_ambiguity[index]+cross/diagonal)
        radius = math.sqrt(max(0.,incumbent-metric+tolerance))/abs(diagonal)
        low, high = math.ceil(center-radius), math.floor(center+radius)
        if low < -MAX_EXACT_INTEGER or high > MAX_EXACT_INTEGER:
            return finish("INTEGER_REPRESENTATION_DOMAIN_EXCEEDED", False)
        left, right = math.floor(center), math.floor(center)+1
        while left >= low or right <= high:
            if time.monotonic()-start >= timeout_s:
                # A popped node has ungenerated children: no certificate.
                frontier_floor = min(lower, frontier[0][0] if frontier else math.inf)
                return finish("TIMEOUT_DURING_CHILD_GENERATION", False)
            if left >= low and (right > high or abs(left-center)<=abs(right-center)):
                z = left; left -= 1
            else:
                z = right; right += 1
            child_metric = float(metric+(diagonal*(center-z))**2)
            if child_metric > incumbent+tolerance:
                continue
            child_suffix = (z,)+suffix
            bound = child_metric
            if bound <= incumbent+tolerance:
                serial += 1
                heapq.heappush(frontier,(bound,serial,index-1,child_suffix,child_metric))
    frontier_floor = None
    return finish("GLOBAL_INTEGER_ENUMERATION_EXHAUSTED", True)
