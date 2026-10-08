"""Lower/feasible-upper bounds for fixed integers with cross-epoch covariance.

The product of baseline spheres is nonconvex. A local feasible solution is an
upper bound, never an infeasibility certificate or an exact global profile.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares

from ..carrier_phase.temporal import TemporalProblem, TemporalFloat, conditional_baselines
from ..carrier_phase.solver import checked_integer_vector
from ..horizontal_literature.ext01_clambda import BaselineSphereMetric


@dataclass(frozen=True)
class CoupledLengthProfile:
    baselines: np.ndarray
    relaxed_raw_cost: float
    marginal_sphere_costs: tuple[float, ...]
    conditional_cost_lower_bound: float
    conditional_cost_upper_bound: float
    raw_cost_lower_bound: float
    raw_cost_upper_bound: float
    objective_identity_error: float
    relaxed_objective_identity_error: float
    maximum_length_error_m: float
    local_optimizations: tuple[dict, ...]


def _angles(baselines):
    return np.column_stack((np.arctan2(baselines[:,1], baselines[:,0]),
        np.arctan2(baselines[:,2], np.linalg.norm(baselines[:,:2],axis=1)))).reshape(-1)


def _sphere_points_and_jacobian(angles, lengths):
    angles=np.asarray(angles).reshape(-1,2)
    azimuth,elevation=angles.T
    ca,sa,ce,se=np.cos(azimuth),np.sin(azimuth),np.cos(elevation),np.sin(elevation)
    points=lengths[:,None]*np.column_stack((ce*ca,ce*sa,se))
    jacobian=np.zeros((3*len(lengths),2*len(lengths)))
    for k,length in enumerate(lengths):
        jacobian[3*k:3*k+3,2*k]=length*np.array([-ce[k]*sa[k],ce[k]*ca[k],0.0])
        jacobian[3*k:3*k+3,2*k+1]=length*np.array([-se[k]*ca[k],-se[k]*sa[k],ce[k]])
    return points,jacobian


def coupled_length_profile(problem: TemporalProblem, floating: TemporalFloat,
                           integer, *, max_nfev: int = 100) -> CoupledLengthProfile:
    """Use full Q throughout and retain both the lower and feasible upper bound.

    For fixed N, the unconstrained raw cost plus the conditional baseline
    quadratic is the original full whitened objective. Each marginal covariance
    gives a necessary single-sphere lower bound; their maximum is valid, while
    their sum would double-count correlated information. Every optimizer point
    is parametrized on each exact-length sphere. Budget exhaustion still leaves
    a feasible upper bound and never excludes the integer identity.
    """
    integer=checked_integer_vector(integer,name="coupled profile integer")
    centers=conditional_baselines(floating,integer)
    delta=integer-floating.ambiguity
    ambiguity_cost=float(delta@np.linalg.solve(floating.covariance_aa,delta))
    relaxed=float(floating.residual_objective+ambiguity_cost)
    raw_constant=floating.whitened_y-floating.whitened_A@integer
    center_residual=raw_constant-floating.whitened_B@centers.reshape(-1)
    relaxed_identity=float(center_residual@center_residual)-relaxed
    marginal_solutions=[BaselineSphereMetric.from_covariance(
        floating.conditional_covariance_b[section,section]).solve(centers[k],float(problem.lengths[k]))
        for k,section in enumerate(problem.baseline_slices)]
    marginal_costs=tuple(float(item.objective) for item in marginal_solutions)
    lower=max(marginal_costs)
    independent_points=np.array([item.baseline for item in marginal_solutions])
    best_cost=float("inf");best_points=None

    def residual(angles):
        nonlocal best_cost,best_points
        points,_=_sphere_points_and_jacobian(angles,problem.lengths)
        value=raw_constant-floating.whitened_B@points.reshape(-1)
        cost=float(value@value)
        if cost<best_cost:
            best_cost,best_points=cost,points.copy()
        return value

    def jacobian(angles):
        _,derivative=_sphere_points_and_jacobian(angles,problem.lengths)
        return -floating.whitened_B@derivative

    attempts=[]
    for name,points in (("MARGINAL_SPHERE_SEED",independent_points),
                        ("ANTIPODAL_MARGINAL_SEED",-independent_points)):
        initial=_angles(points)
        initial_residual=residual(initial)
        result=least_squares(residual,initial,jac=jacobian,max_nfev=max_nfev,
                             ftol=1e-10,xtol=1e-10,gtol=1e-10)
        residual(result.x)
        attempts.append(dict(seed=name,seed_raw_cost=float(initial_residual@initial_residual),
            returned_raw_cost=float(result.fun@result.fun),success=bool(result.success),
            status=int(result.status),message=str(result.message),nfev=int(result.nfev),
            max_nfev=max_nfev))
    offset=best_points.reshape(-1)-centers.reshape(-1)
    conditional=floating.whitened_B@offset
    upper_conditional=float(conditional@conditional)
    error=best_cost-(relaxed+upper_conditional)
    length_error=float(np.max(np.abs(np.linalg.norm(best_points,axis=1)-problem.lengths)))
    return CoupledLengthProfile(best_points,relaxed,marginal_costs,lower,upper_conditional,
        relaxed+lower,best_cost,error,relaxed_identity,length_error,tuple(attempts))
