"""Six-dimensional two-pose WORKING information diagnostics, never a filter.

No residual, raw data, reference, integer search or navigation state is consumed.
P includes both endpoint marginals AND their cross at one conditioning set.
Endpoint-noise cross (inside R) and state/noise cross C are distinct contracts.
All objectives and error/source assumptions must be frozen before seeing phase
residuals. Finite proper P is not a representation of an unbounded gauge prior.
"""
from __future__ import annotations

import math
from functools import wraps
import numpy as np

ZERO_CROSS = "WORKING_ZERO_CROSS_ASSUMPTION"
SUPPLIED_CROSS = "SUPPLIED_CROSS"
UNKNOWN_CROSS = "UNKNOWN_CROSS_BOUND"
EPSILON_GRID = (1/64, 1/16, 1/4, 1., 4.)
MACHINE = np.finfo(float).eps


class InformationError(ValueError):
    pass


def _finite(value, name):
    if not np.isfinite(value).all():
        raise InformationError("UNRESOLVED_"+name+"_NONFINITE")
    return value


def _numeric_domain(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                return function(*args, **kwargs)
        except FloatingPointError as exc:
            raise InformationError("UNRESOLVED_FINITE_ARITHMETIC_DOMAIN") from exc
    return guarded


def _score(w, p):
    value = float(np.trace(w@p))
    _finite(value, "OBJECTIVE")
    if value < 0.:
        raise InformationError("UNRESOLVED_NEGATIVE_OBJECTIVE")
    return value


def _identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise InformationError(name + ": explicit identity or qualification required")
    return value


def _array(value, shape, name):
    if np.iscomplexobj(value):
        raise InformationError(name + ": real values required")
    a = np.asarray(value, dtype=float)
    if a.shape != shape or not np.isfinite(a).all():
        raise InformationError(name + ": finite complete matrix of required shape")
    return a


def _psd(value, n, name):
    """Diagonal-normalized qualification, never a covariance repair.

All positive diagonal scales are retained. Exact zero diagonal rows must be
zero; no jitter, eigenvalue clipping or positive-mode deletion is performed.
Small signed eigenvalues are reported only as numerical PSD qualification.
"""
    a = _array(value, (n, n), name)
    d = np.diag(a)
    if np.any(d < 0.):
        raise InformationError(name + ": negative diagonal")
    positive = d > 0.
    if np.any(a[~positive, :] != 0.) or np.any(a[:, ~positive] != 0.):
        raise InformationError(name + ": zero diagonal with nonzero cross")
    if np.any(positive):
        scales = np.sqrt(d[positive])
        normalized = a[np.ix_(positive, positive)] / scales[:, None] / scales[None, :]
        _finite(normalized, name+"_NORMALIZED")
        norm = float(np.linalg.norm(normalized, 2))
        _finite(norm, name+"_NORMALIZED_NORM")
        tol = 128*MACHINE*n*max(1., norm)
        if np.max(np.abs(normalized-normalized.T)) > tol:
            raise InformationError(name + ": nonsymmetric")
        if np.linalg.eigvalsh((normalized+normalized.T)*.5)[0] < -tol:
            raise InformationError(name + ": not PSD")
    return (a+a.T)*.5


def _spd_solve(a, rhs, name):
    _finite(a, name+"_MATRIX")
    _finite(rhs, name+"_RHS")
    symmetric = (a+a.T)*.5
    _finite(symmetric, name+"_SYMMETRIC")
    try:
        chol = np.linalg.cholesky(symmetric)
        result = np.linalg.solve(chol.T, np.linalg.solve(chol, rhs))
    except np.linalg.LinAlgError as exc:
        raise InformationError("UNRESOLVED_"+name+"_NOT_SPD_NO_LOADING") from exc
    if not np.isfinite(result).all():
        raise InformationError("UNRESOLVED_"+name+"_NONFINITE_SOLVE")
    return result


def _skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


@_numeric_domain
def linearize_geometry(G0, G1, C0, C1, baseline_body_m):
    """Historical local algebra in ECEF left-error coordinates, no release."""
    g0 = np.asarray(G0)
    if g0.ndim != 2 or g0.shape[1] != 3 or g0.shape[0] < 1:
        raise InformationError("G0 requires nonempty m by 3 geometry")
    g0 = _array(g0, g0.shape, "G0")
    g1 = _array(G1, g0.shape, "G1")
    rotations = []
    for value in (C0, C1):
        c = _array(value, (3, 3), "body-to-ECEF rotation")
        if not np.allclose(c.T@c, np.eye(3), atol=1e-10, rtol=0.) or abs(np.linalg.det(c)-1.) > 1e-10:
            raise InformationError("SO(3) required; no normalization")
        rotations.append(c)
    baseline = _array(baseline_body_m, (3,), "physical body baseline")
    length = float(np.linalg.norm(baseline))
    if not math.isfinite(length) or length <= 0.:
        raise InformationError("nonzero baseline required")
    b0, b1 = (c@baseline for c in rotations)
    h = np.hstack((g0@_skew(b0), -g1@_skew(b1)))
    gauge = np.zeros((6, 2))
    gauge[:3, 0] = b0/length
    gauge[3:, 1] = b1/length
    return dict(prediction_m=g1@b1-g0@b0, H=h, baseline_spin_gauge=gauge,
                b0_ecef_m=b0, b1_ecef_m=b1,
                scope="LOCAL_GEOMETRY_NOT_ABSOLUTE_HEADING_QUALIFICATION")


def _projected_traces(p):
    common = np.hstack((np.eye(3), np.eye(3)))/math.sqrt(2.)
    relative = np.hstack((-np.eye(3), np.eye(3)))/math.sqrt(2.)
    return dict(joint=_score(np.eye(6), p),
                current=_score(np.diag([0., 0., 0., 1., 1., 1.]), p),
                common_ecef=_score(common.T@common, p),
                relative_ecef=_score(relative.T@relative, p))


def _covariance_error(a, b, prior):
    # Compare in the supplied prior's natural scales, including tiny variances.
    d = np.sqrt(np.diag(prior))
    active = d > 0.
    if np.any((a-b)[~active, :] != 0.) or np.any((a-b)[:, ~active] != 0.):
        return math.inf
    if not np.any(active):
        return 0.
    return float(np.max(np.abs((a-b)[np.ix_(active, active)] / d[active, None] / d[None, active])))


def _young_objective(p, h, r, w):
    t = _score(w, p)
    ph = p@h.T
    j = float(np.trace(w@ph@_spd_solve(r, ph.T, "R")))
    if not math.isfinite(t) or not math.isfinite(j) or t < 0. or j < 0.:
        raise InformationError("UNRESOLVED_TRACE_DOMAIN")
    margin = 512*MACHINE*6*max(abs(t), abs(j), np.finfo(float).tiny)
    if t == 0.:
        condition, exists = "ZERO_PRIOR_OBJECTIVE", False
    elif abs(j-t) <= margin:
        condition, exists = "CONTINUOUS_BOUNDARY_UNRESOLVED", None
    elif j > t:
        condition, exists = "CONTINUOUS_IMPROVEMENT_EXISTS", True
    else:
        condition, exists = "CONTINUOUS_NO_IMPROVEMENT", False
    grid, best, epsilon = [], t, 0.
    for eps in EPSILON_GRID:
        gain = _spd_solve(h@ph+r/eps, ph.T, "YOUNG_INNOVATION").T
        f = np.eye(6)-gain@h
        bound = (1+eps)*(f@p@f.T+gain@r@gain.T/eps)
        bound = (bound+bound.T)*.5
        _finite(bound, "YOUNG_BOUND")
        score = _score(w, bound)
        tie = 64*MACHINE*max(1., abs(score), abs(best))
        if not math.isfinite(score):
            raise InformationError("UNRESOLVED_YOUNG_SCORE")
        selected = score < best-tie
        grid.append(dict(epsilon=eps, bound=bound.tolist(), score=score,
                         comparison_score=best, tie=tie, selected=bool(selected)))
        if selected:
            best, epsilon = score, eps
    return dict(T=t, J=j, J_over_T=j/t if t > 0. else None, criterion_margin=margin,
                continuous_condition=condition, continuous_improvement_exists=exists,
                omega_zero_score=t, grid=grid, grid_best_score=best,
                grid_selected_epsilon=epsilon, no_continuous_optimizer=True)


@_numeric_domain
def diagnose(P6, H, R, *, mode, covariance_kind, error_model, conditioning_information_id,
             prior_source_id, measurement_source_id, cross_source_id, qualification_note,
             objective_weights, objective_source_id, endpoint_times_s,
             C_en=None, gauge_basis=None, actual_available_time_s=None):
    """Pure diagnostic with explicitly frozen source/error/objective contracts.

Known-C formulas assume residual=H*e+n and centered zero-mean e,n conditioned
on the SAME declared information set. Supplied cross plus joint PSD proves
algebraic consistency only, not real source cross validity. UNKNOWN_CROSS uses
second moments about the nominal; those bounds must include any biases.
"""
    for name, value in dict(conditioning_information_id=conditioning_information_id,
                            prior_source_id=prior_source_id, measurement_source_id=measurement_source_id,
                            cross_source_id=cross_source_id, qualification_note=qualification_note,
                            objective_source_id=objective_source_id).items():
        _identity(value, name)
    if mode not in (ZERO_CROSS, SUPPLIED_CROSS, UNKNOWN_CROSS):
        raise InformationError("explicit correlation mode required")
    expected = (("SECOND_MOMENT_UPPER_BOUND", "SECOND_MOMENT_ABOUT_NOMINAL") if mode == UNKNOWN_CROSS else
                ("WORKING_COVARIANCE", "CENTERED_ZERO_MEAN_GIVEN_INFORMATION"))
    if (covariance_kind, error_model) != expected:
        raise InformationError("covariance/error kind inconsistent with correlation mode")
    times = _array(endpoint_times_s, (2,), "endpoint times")
    if times[1] <= times[0]:
        raise InformationError("two strictly ordered endpoint times required")
    if actual_available_time_s is not None and (not math.isfinite(actual_available_time_s) or actual_available_time_s < times[1]):
        raise InformationError("actual availability invalid; unknown must remain None")
    p = _psd(P6, 6, "complete P6 with P01")
    raw_h = np.asarray(H)
    if raw_h.ndim != 2 or raw_h.shape[0] < 1 or raw_h.shape[1] != 6:
        raise InformationError("full m by 6 H required")
    h = _array(H, raw_h.shape, "H")
    r = _psd(R, len(h), "R")
    w = _psd(objective_weights, 6, "frozen objective W")
    if mode != SUPPLIED_CROSS and C_en is not None:
        raise InformationError("supplied C may not be discarded by zero/unknown mode")
    result = dict(mode=mode, covariance_kind=covariance_kind, error_model=error_model,
                  conditioning_information_id=conditioning_information_id,
                  prior_source_id=prior_source_id, measurement_source_id=measurement_source_id,
                  cross_source_id=cross_source_id, qualification_note=qualification_note,
                  objective_source_id=objective_source_id, objective_weights=w.tolist(),
                  endpoint_times_s=times.tolist(), actual_available_time_s=actual_available_time_s,
                  P_prior=p.tolist(), prior_projected_traces=_projected_traces(p),
                  navigation_admitted=False, state_updated=False, physical_independence_proven=False,
                  physical_cross_qualification_proven=False, physical_covariance_calibrated=False,
                  no_residual_used=True, estimator_scope="SECOND_ORDER_LINEAR_ESTIMATOR_NOT_FULL_BAYES_POSTERIOR",
                  gauge_interpretation="projected variance reduction can be prior/cross mediated")
    if gauge_basis is not None:
        n = np.asarray(gauge_basis)
        if n.ndim != 2 or n.shape[0] != 6 or n.shape[1] < 1:
            raise InformationError("explicit gauge basis shape")
        n = _array(n, n.shape, "gauge basis")
        if not np.allclose(n.T@n, np.eye(n.shape[1]), atol=1e-10, rtol=0.):
            raise InformationError("orthonormal gauge basis required")
        residual_norm = float(np.linalg.norm(h@n))
        _finite(residual_norm, "GAUGE_RESIDUAL_NORM")
        result.update(geometry_gauge_residual_norm=residual_norm,
                      gauge_prior_trace=_score(n@n.T, p))
    else:
        n = None
        result.update(geometry_gauge_residual_norm=None, gauge_prior_trace=None)
    # Full measurement-space whitening needs no factorization/truncation of P.
    try:
        chol = np.linalg.cholesky(r)
    except np.linalg.LinAlgError as exc:
        raise InformationError("UNRESOLVED_R_NOT_SPD_NO_LOADING") from exc
    projected = h@p@h.T
    _finite(projected, "HPHT")
    a = np.linalg.solve(chol, projected)
    a = np.linalg.solve(chol, a.T).T
    a = (a+a.T)*.5
    _finite(a, "WHITENED_INFORMATION")
    eigenvalues = np.linalg.eigvalsh(a)
    _finite(eigenvalues, "INFORMATION_EIGENVALUES")
    result.update(working_information_eigenvalues=eigenvalues.tolist(),
                  spectrum_scope="R-whitened HPHt; numerical only, no exact rank or zero-noise cap claim",
                  Gmax_certified=None)
    if mode == UNKNOWN_CROSS:
        result.update(unknown_objectives={
            "joint":_young_objective(p, h, r, np.eye(6)),
            "current":_young_objective(p, h, r, np.diag([0., 0., 0., 1., 1., 1.])),
            "declared":_young_objective(p, h, r, w)}, P_posterior=None,
            conditional_independence_result=None, status="CONDITIONAL_WORKING_UNKNOWN_CROSS_BOUND")
        return result
    c = (np.zeros((6, len(h))) if mode == ZERO_CROSS else _array(C_en, (6, len(h)), "complete C_en"))
    _psd(np.block([[p, c], [c.T, r]]), 6+len(h), "joint state-noise covariance")
    s = h@p@h.T+h@c+c.T@h.T+r
    s = (s+s.T)*.5
    phc = p@h.T+c
    k = _spd_solve(s, phc.T, "INNOVATION").T
    f = np.eye(6)-k@h
    joseph = f@p@f.T+k@r@k.T-f@c@k.T-k@c.T@f.T
    joseph = (joseph+joseph.T)*.5
    reduction = k@phc.T
    reduction = (reduction+reduction.T)*.5
    _psd(joseph, 6, "UNRESOLVED_POSTERIOR_PSD")
    _psd(reduction, 6, "UNRESOLVED_REDUCTION_PSD")
    error = _covariance_error(joseph, p-reduction, p)
    if not math.isfinite(error) or error > 2e-10:
        raise InformationError("UNRESOLVED_POSTERIOR_FORMULA_INCONSISTENCY")
    result.update(status="CONDITIONAL_WORKING_COVARIANCE", C_en=c.tolist(), innovation_covariance=s.tolist(),
                  gain=k.tolist(), P_posterior=joseph.tolist(), covariance_reduction=reduction.tolist(),
                  posterior_projected_traces=_projected_traces(joseph),
                  declared_objective_prior=_score(w, p),
                  declared_objective_posterior=_score(w, joseph),
                  formula_error_in_prior_scales=error,
                  gauge_posterior_trace=_score(n@n.T, joseph) if n is not None else None,
                  direct_geometry_information=_finite(h.T@_spd_solve(r, h, "R"), "DIRECT_GEOMETRY_INFORMATION").tolist() if mode == ZERO_CROSS else None,
                  direct_geometry_scope="only under explicitly declared zero state/noise cross")
    return result
