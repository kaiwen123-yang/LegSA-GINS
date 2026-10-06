"""Exact temporal fixed-length integer search for epoch-independent observation Q.

Each epoch has a free 3D baseline; only labeled integers are shared. A certificate
concerns the registered likelihood/length objective, never integer acceptance.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import heapq,math,time
import numpy as np
from ..horizontal_literature.ext01_clambda import RTKLIBLambdaBridge,constrained_baseline,BaselineSphereMetric,LambdaBridgeError
from .temporal import TemporalProblem,TemporalFloat,TemporalModelError,joint_float,conditional_baselines,has_cross_epoch_covariance,positive_definite

@dataclass(frozen=True)
class TemporalCandidate:
    ambiguity: np.ndarray
    baselines: np.ndarray
    reduced_cost: float
    ambiguity_cost: float
    length_constraint_cost: float
    full_residual_cost: float
    float_residual_cost: float
    objective_identity_error: float
    maximum_length_error_m: float

@dataclass(frozen=True)
class TemporalCertificate:
    global_optimum_certified: bool
    termination_reason: str
    seed_candidates_requested: int
    seed_candidates_returned: int
    expanded_nodes: int
    integer_leaves: int
    unique_candidates: int
    frontier_lower_bound: float|None
    best_reduced_cost: float|None
    second_reduced_cost: float|None
    elapsed_s: float
    candidate_cap_applied: bool
    integer_acceptance_test_defined: bool=False
    distinct_ambiguity_labels: tuple[str,...]=()
    distinct_ambiguity_classes: int=0
    certificate_scope: str="two_best_full_integer_vectors"
    conditional_seed_ils_calls: int=0
    conditional_seed_candidates_evaluated: int=0
    conditional_seed_failures: int=0
    bound_cache_depths: int=0
    bound_evaluations: int=0
    cheap_bound_prunes: int=0
    bound_sphere_evaluations: int=0
    candidate_sphere_evaluations: int=0
    sphere_metric_factorizations: int=0

@dataclass(frozen=True)
class TemporalResult:
    best: TemporalCandidate|None
    second: TemporalCandidate|None
    certificate: TemporalCertificate
    float_solution: TemporalFloat
    @property
    def candidate_available(self):
        return self.certificate.global_optimum_certified and self.best is not None
    @property
    def global_optimum_certified(self):
        return self.certificate.global_optimum_certified

def _require_separable(problem,floating):
    if has_cross_epoch_covariance(problem):
        raise TemporalModelError("cross-epoch covariance: joint float is supported, coupled length constraints are not globally solved")
    cb=floating.conditional_covariance_b
    scale=max(float(np.max(np.abs(np.diag(cb)))),np.finfo(float).tiny)
    for k,a in enumerate(problem.baseline_slices):
        for b in problem.baseline_slices[k+1:]:
            if np.max(np.abs(cb[a,b]))>1e-8*scale+1e-14:
                raise TemporalModelError("conditional baseline covariance is not epoch-separable")

MAX_EXACT_INTEGER=2**53-1

def checked_integer_vector(value, *, name="integer vector"):
    """Reject values outside the exactly represented binary64 integer domain.

    This solver uses floating LAMBDA transforms; int64 storage is not a claim
    of exact arithmetic over the whole int64 domain.
    """
    try:
        n=np.asarray(value,float)
    except (TypeError,ValueError,OverflowError) as exc:
        raise TemporalModelError(f"{name}: unsupported integer representation") from exc
    if (not np.isfinite(n).all() or np.any(np.abs(n)>MAX_EXACT_INTEGER)
            or not np.array_equal(n,np.rint(n))):
        raise TemporalModelError(f"{name}: requires exact integers with absolute value <= 2**53-1")
    return n.astype(np.int64)

class _IntegerEvaluator:
    """Per-solve leaf factors; each candidate retains the full residual check."""
    def __init__(self, problem, floating):
        _require_separable(problem,floating)
        self.problem,self.floating=problem,floating
        self.metrics=tuple(BaselineSphereMetric.from_covariance(
            floating.conditional_covariance_b[bb,bb]) for bb in problem.baseline_slices)
        self.sphere_evaluations=0

    def __call__(self, integer):
        problem,floating=self.problem,self.floating
        n=checked_integer_vector(integer,name="candidate")
        if n.shape!=floating.ambiguity.shape:
            raise TemporalModelError("candidate must have the registered integer vector shape")
        delta=n-floating.ambiguity
        ambiguity_cost=float(delta@np.linalg.solve(floating.covariance_aa,delta))
        centers=conditional_baselines(floating,n)
        baselines=[];sphere_cost=0.;length_error=0.
        for k,bb in enumerate(problem.baseline_slices):
            sphere=self.metrics[k].solve(centers[k],float(problem.lengths[k]))
            self.sphere_evaluations+=1
            baselines.append(sphere.baseline);sphere_cost+=sphere.objective
            length_error=max(length_error,abs(float(np.linalg.norm(sphere.baseline))-problem.lengths[k]))
        baselines=np.asarray(baselines)
        residual=floating.whitened_y-floating.whitened_A@n-floating.whitened_B@baselines.reshape(-1)
        full=float(residual@residual);reduced=ambiguity_cost+sphere_cost
        error=full-(floating.residual_objective+reduced)
        if abs(error)>2e-6+2e-8*max(abs(full),abs(reduced)):
            raise TemporalModelError(f"temporal residual/objective identity failed: {error}")
        if length_error>1e-8:raise TemporalModelError("sphere subproblem violated baseline length")
        return TemporalCandidate(n,baselines,reduced,ambiguity_cost,sphere_cost,full,floating.residual_objective,error,length_error)


def evaluate_integer(problem:TemporalProblem,floating:TemporalFloat,integer)->TemporalCandidate:
    return _IntegerEvaluator(problem,floating)(integer)

def _condition_integer_coordinate(floating, index, value):
    """Gaussian conditioning for FEASIBLE seed generation, never a certificate.

    All other coordinates, including unselected/historical N, remain free here.
    Their conditional integer seeds are lifted back to the original dimension
    and scored by evaluate_integer with the exact registered sphere objective.
    """
    mean, q = floating.ambiguity, floating.covariance_aa
    free = np.array([j for j in range(len(mean)) if j != index], dtype=int)
    cross = q[free, index]
    conditioned_mean = mean[free] + cross / q[index, index] * (value-mean[index])
    conditioned_q = q[np.ix_(free, free)] - np.outer(cross, cross)/q[index, index]
    return free, conditioned_mean, positive_definite(conditioned_q, "conditional seed Q")


class _BaselineBoundCache:
    """Cache depth-only Gaussian factors; each node still uses its own center.

    The lower bound remains max(single-epoch marginal sphere bounds), never
    their sum. Relaxed cross-epoch correlation is not discarded.
    """
    def __init__(self, problem, floating, reduced):
        self.problem, self.floating, self.reduced = problem, floating, reduced
        self.m = problem.ambiguity_count
        self.qbb = floating.covariance[self.m:, self.m:]
        self.qbz = floating.covariance_ba @ reduced.transformation
        self.depths = {}
        self.sphere_metrics = {}
        self.evaluations = self.cheap_prunes = self.sphere_evaluations = 0

    def parameters(self, depth):
        if depth not in self.depths:
            indices = np.arange(self.m-depth, self.m)
            if depth:
                qss = self.reduced.covariance[np.ix_(indices, indices)]
                qbs = self.qbz[:, indices]
                solved = np.linalg.solve(qss, qbs.T)
                gain = solved.T
                cov = self.qbb - qbs @ solved
            else:
                gain = np.zeros((len(self.floating.baseline), 0))
                cov = self.qbb
            cov = (cov+cov.T)*.5
            maximum_eigenvalues = []
            for ss in self.problem.baseline_slices:
                q = positive_definite(cov[ss, ss], "relaxed baseline marginal")
                maximum_eigenvalues.append(float(np.linalg.eigvalsh(q)[-1]))
            self.depths[depth] = (indices, gain, cov, np.asarray(maximum_eigenvalues))
        return self.depths[depth]

    def __call__(self, suffix, ambiguity_bound, *, cutoff=math.inf):
        self.evaluations += 1
        indices, gain, cov, maximum_eigenvalues = self.parameters(len(suffix))
        delta = np.asarray(suffix, float)-self.reduced.float_ambiguity[indices]
        center = self.floating.baseline + gain @ delta
        cheap = np.asarray([(float(np.linalg.norm(center[ss]))-self.problem.lengths[k])**2
                            for k,ss in enumerate(self.problem.baseline_slices)]) / maximum_eigenvalues
        maximum_cheap = float(np.max(cheap))
        cheap_bound = float(ambiguity_bound+maximum_cheap)
        # The original bound already contains maximum_cheap. A node rejected
        # here would also be rejected after the exact sphere calculation. Use
        # the caller's SAME incumbent+tolerance; equality is not pruned early.
        if cheap_bound > cutoff:
            self.cheap_prunes += 1
            return cheap_bound
        k = int(np.argmax(cheap))
        ss = self.problem.baseline_slices[k]
        key = (len(suffix), k)
        if key not in self.sphere_metrics:
            self.sphere_metrics[key] = BaselineSphereMetric.from_covariance(cov[ss,ss])
        exact = self.sphere_metrics[key].solve(center[ss], float(self.problem.lengths[k])).objective
        self.sphere_evaluations += 1
        return float(ambiguity_bound+max(maximum_cheap, exact))


def solve_temporal(problem:TemporalProblem,lambda_library:str|Path,*,initial_candidates:int=8,
                   node_limit:int=100000,timeout_s:float=60.,
                   distinct_ambiguity_labels:tuple[str,...]|None=None)->TemporalResult:
    """Find two best integer classes, retaining all historical nuisance integers.

    With selected labels, vectors with equal selected coordinates form one class;
    its score is the minimum FULL objective over all historical integer values.
    The complete original-dimensional search remains in place.
    """
    if initial_candidates<2 or node_limit<1 or not math.isfinite(timeout_s) or timeout_s<=0:
        raise TemporalModelError("invalid search budget")
    started=time.monotonic();floating=joint_float(problem);_require_separable(problem,floating)
    labels=tuple(problem.ambiguity_labels if distinct_ambiguity_labels is None else distinct_ambiguity_labels)
    if not labels or len(set(labels))!=len(labels) or any(x not in problem.ambiguity_labels for x in labels):
        raise TemporalModelError("distinct ambiguity labels must be nonempty, unique, and present in the problem")
    distinct_indices=tuple(problem.ambiguity_labels.index(x) for x in labels)
    evaluated={};nodes=leaves=returned=0;frontier_bound=None
    conditional_calls=conditional_evaluated=conditional_failures=0
    bound_cache=None
    integer_evaluator=_IntegerEvaluator(problem,floating)
    def ordered_classes():
        classes={}
        for candidate in evaluated.values():
            key=tuple(int(candidate.ambiguity[i]) for i in distinct_indices)
            previous=classes.get(key)
            if previous is None or (candidate.reduced_cost,tuple(candidate.ambiguity)) < (previous.reduced_cost,tuple(previous.ambiguity)):
                classes[key]=candidate
        return sorted(classes.values(),key=lambda x:(x.reduced_cost,tuple(x.ambiguity)))
    def finish(reason,certified):
        ordered=ordered_classes()
        best=ordered[0] if ordered else None;second=ordered[1] if len(ordered)>1 else None
        certificate=TemporalCertificate(certified,reason,initial_candidates,returned,nodes,leaves,len(evaluated),
            frontier_bound,None if best is None else best.reduced_cost,None if second is None else second.reduced_cost,
            time.monotonic()-started,False,False,labels,len(ordered),
            "two_best_full_integer_vectors" if distinct_ambiguity_labels is None else "two_best_selected_integer_classes",
            conditional_seed_ils_calls=conditional_calls,
            conditional_seed_candidates_evaluated=conditional_evaluated,
            conditional_seed_failures=conditional_failures,
            bound_cache_depths=0 if bound_cache is None else len(bound_cache.depths),
            bound_evaluations=0 if bound_cache is None else bound_cache.evaluations,
            cheap_bound_prunes=0 if bound_cache is None else bound_cache.cheap_prunes,
            bound_sphere_evaluations=0 if bound_cache is None else bound_cache.sphere_evaluations,
            candidate_sphere_evaluations=integer_evaluator.sphere_evaluations,
            sphere_metric_factorizations=len(integer_evaluator.metrics)+(
                0 if bound_cache is None else len(bound_cache.sphere_metrics)))
        return TemporalResult(best,second,certificate,floating)
    bridge=RTKLIBLambdaBridge(lambda_library)
    seeds=bridge.candidates(floating.ambiguity,floating.covariance_aa,initial_candidates);returned=len(seeds)
    reduced=bridge.decorrelate(floating.ambiguity,floating.covariance_aa)
    checked_integer_vector(reduced.transformation,name="LAMBDA transformation")
    for seed in seeds:
        seed_integer=checked_integer_vector(seed.ambiguity,name="LAMBDA seed")
        key=tuple(int(x) for x in seed_integer)
        evaluated[key]=integer_evaluator(seed_integer)
        if time.monotonic()-started>=timeout_s:return finish("TIMEOUT_DURING_SEED_EVALUATION",False)
    if len(distinct_indices) < problem.ambiguity_count:
        # Coarse classes can make the first LAMBDA seeds all equivalent. A
        # one-coordinate change with every other integer held unchanged is a
        # poor upper bound under strong ambiguity correlation. Instead condition
        # on each selected coordinate's base +/- 1 and generate two integer
        # candidates over ALL remaining coordinates. Only feasibility is used.
        base=min(evaluated.values(),key=lambda x:x.reduced_cost).ambiguity.copy()
        for index in distinct_indices:
            for sign in (-1,1):
                if time.monotonic()-started>=timeout_s:
                    return finish("TIMEOUT_DURING_CONDITIONAL_SEED_EVALUATION",False)
                value=int(base[index])+sign
                if abs(value)>MAX_EXACT_INTEGER:continue
                try:
                    free,mean,covariance=_condition_integer_coordinate(floating,index,value)
                    conditional_calls+=1
                    seeds=bridge.candidates(mean,covariance,2)
                except (LambdaBridgeError,np.linalg.LinAlgError,TemporalModelError):
                    # An optional conditioning/ILS seed failure does not narrow
                    # the exact search or manufacture a successful certificate.
                    conditional_failures+=1
                    continue
                for seed in seeds:
                    integer=checked_integer_vector(seed.ambiguity,name="conditional LAMBDA seed")
                    if integer.shape!=(len(free),):
                        raise TemporalModelError("conditional seed dimension mismatch")
                    extra=base.copy();extra[index]=value;extra[free]=integer
                    key=tuple(int(x) for x in extra)
                    if key not in evaluated:
                        evaluated[key]=integer_evaluator(extra)
                        conditional_evaluated+=1
                    if time.monotonic()-started>=timeout_s:
                        return finish("TIMEOUT_DURING_CONDITIONAL_SEED_EVALUATION",False)
    if len(ordered_classes())<2:
        # A finite upper bound needs two DISTINCT classes. Perturb an active
        # original integer coordinate, never restrict the search to these seeds.
        base=min(evaluated.values(),key=lambda x:x.reduced_cost).ambiguity.copy()
        for sign in (-1,1):
            extra=base.copy()
            value=int(extra[distinct_indices[0]])+sign
            if abs(value)>MAX_EXACT_INTEGER:continue
            extra[distinct_indices[0]]=value
            key=tuple(int(x) for x in extra)
            if key not in evaluated:evaluated[key]=integer_evaluator(extra)
            if time.monotonic()-started>=timeout_s:return finish("TIMEOUT_DURING_CLASS_SEED_EVALUATION",False)
            if len(ordered_classes())>=2:break
    if len(ordered_classes())<2:return finish("INSUFFICIENT_DISTINCT_CLASSES",False)
    incumbent=ordered_classes()[1].reduced_cost
    m=problem.ambiguity_count
    bound_cache=_BaselineBoundCache(problem,floating,reduced)
    node_bound=bound_cache

    weight=np.linalg.solve(reduced.covariance,np.eye(m));weight=(weight+weight.T)*.5
    upper=np.linalg.cholesky(weight).T
    serial=0;frontier=[]
    root=node_bound((),0.)
    heapq.heappush(frontier,(root,serial,m-1,(),0.))
    tolerance=1e-10
    while frontier:
        frontier_bound=float(frontier[0][0])
        if frontier_bound>=incumbent:
            return finish("GLOBAL_BOUND_CERTIFIED",True)
        if time.monotonic()-started>=timeout_s:return finish("SEARCH_TIMEOUT",False)
        if nodes>=node_limit:return finish("NODE_LIMIT",False)
        lower,_,index,suffix,ambiguity_bound=heapq.heappop(frontier);nodes+=1
        if index<0:
            leaves+=1
            original=np.linalg.solve(reduced.transformation.T.astype(float),np.asarray(suffix,float))
            rounded=np.rint(original)
            if not np.allclose(original,rounded,rtol=0.,atol=1e-7):raise TemporalModelError("unimodular integer transform failed")
            rounded=checked_integer_vector(rounded,name="LAMBDA back-transformed candidate")
            key=tuple(int(v) for v in rounded)
            if key not in evaluated:
                candidate=integer_evaluator(rounded)
                if not math.isclose(candidate.ambiguity_cost,ambiguity_bound,rel_tol=2e-7,abs_tol=2e-7):
                    raise TemporalModelError("tree integer metric mismatch")
                evaluated[key]=candidate
                incumbent=ordered_classes()[1].reduced_cost
            continue
        assigned=np.asarray(suffix,float)
        cross=float(upper[index,index+1:]@(reduced.float_ambiguity[index+1:]-assigned)) if len(assigned) else 0.
        diagonal=float(upper[index,index]);center=float(reduced.float_ambiguity[index]+cross/diagonal)
        radius=math.sqrt(max(0.,incumbent-ambiguity_bound+tolerance))/abs(diagonal)
        low=math.ceil(center-radius);high=math.floor(center+radius)
        if low < -MAX_EXACT_INTEGER or high > MAX_EXACT_INTEGER:
            return finish("INTEGER_REPRESENTATION_DOMAIN_EXCEEDED",False)
        # Lazy Schnorr-Euchner traversal; do not materialize an unbounded range.
        left=math.floor(center);right=left+1
        while left>=low or right<=high:
            if time.monotonic()-started>=timeout_s:return finish("SEARCH_TIMEOUT_CHILD_GENERATION",False)
            if left>=low and (right>high or abs(left-center)<=abs(right-center)):
                z=left;left-=1
            else:z=right;right+=1
            child_metric=float(ambiguity_bound+(diagonal*(center-z))**2)
            if child_metric>incumbent+tolerance:continue
            child_suffix=(z,)+suffix;bound=node_bound(child_suffix,child_metric,cutoff=incumbent+tolerance)
            if bound<=incumbent+tolerance:
                serial+=1;heapq.heappush(frontier,(bound,serial,index-1,child_suffix,child_metric))
    frontier_bound=None
    return finish("GLOBAL_ENUMERATION_EXHAUSTED",True)
