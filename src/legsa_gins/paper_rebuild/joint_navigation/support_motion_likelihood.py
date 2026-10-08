"""Source-only restricted likelihood for a shared finite contact-motion process.

The input Gaussian graph is the complete, once-linearized, no-foot conditional
navigation model. Its sparse factors retain all cross-time and cross-group
state uncertainty. Contact coordinates have Lebesgue measure (REML nuisance),
not a fitted pseudo-prior. Foot AR noise is included once in body coordinates.
This is a local Gaussian calibration likelihood, not a slip-truth detector.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import math

import gtsam
import numpy as np
from scipy import linalg
from gtsam.symbol_shorthand import X

from .window import eliminate_qr
from .support_motion import support_motion_transition


@dataclass(frozen=True)
class MotionParameters:
    velocity_sigma_mps: float
    tau_s: float


@dataclass(frozen=True)
class SupportMotionProblem:
    navigation_conditionals: object
    navigation_log_normalizer: float
    foot_rows: tuple
    contact_origins: dict
    arc_groups: dict
    policy: tuple
    foot_sigma_m: float
    foot_tau_s: float
    source_scope: dict


def _skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def _qr(graph):
    ordering = gtsam.Ordering.ColamdGaussianFactorGraph(graph)
    keys = [ordering.at(i) for i in range(ordering.size())]
    net, _ = eliminate_qr(graph, keys)
    # A singular conditional is an identifiability failure, never regularized.
    normalizer = 0.
    for i in range(net.size()):
        conditional = net.at(i)
        diagonal = np.abs(np.diag(conditional.R()))
        model = conditional.get_model()
        sigmas = np.ones(len(diagonal)) if model is None else model.sigmas()
        if np.any(diagonal == 0) or np.any(sigmas <= 0):
            raise ValueError("improper or constrained source chart has no ordinary Gaussian density")
        # GTSAM 4.2 logNormalizationConstant takes log(R_ii), and QR may
        # legitimately return negative R_ii. Density uses log|det R|.
        normalizer += float(np.log(diagonal).sum()-np.log(sigmas).sum()
                            -.5*len(diagonal)*math.log(2*math.pi))
    if not math.isfinite(normalizer):
        raise ValueError("nonfinite Gaussian normalization: source or nuisance rank unresolved")
    return net, normalizer


def source_partition(events):
    """First common observed, still-unassigned arcs; every arc belongs once.

    This is a declared calibration partition of measured sources, not a label
    of true common sliding. Later missing/subset observations never split it.
    """
    assigned, result = set(), []
    for event in events:
        arcs = tuple(sorted({str(f["arc_id"]) for f in event.get("feet", [])
                             if f.get("support_eligible", True)} - assigned))
        if arcs:
            result.append(dict(group_id="support:" + "|".join(arcs), arc_ids=arcs,
                               mode="finite_common_motion"))
            assigned.update(arcs)
    return tuple(result)


def prepare_support_motion_likelihood(navigation_graph, navigation_values, events,
                                      *, foot_sigma_m=.01, foot_tau_s=.08,
                                      policy=None, source_scope=None):
    """Freeze one full no-foot Gaussian chart and parameter-independent origins.

    Caller must supply original factors without an additional marginalized
    prior covering those same factors. Every measured pose must still exist.
    Foot points set only contact linearization origins, never navigation means.
    """
    if foot_sigma_m <= 0. or foot_tau_s <= 0.:
        raise ValueError("original foot AR sigma and tau must be positive")
    scope = dict(source_scope or {})
    if scope.get("foot_factors_consumed") != 0 or scope.get("reference_reads") != 0:
        raise ValueError("calibration requires an explicitly no-foot, reference-free state graph")
    if scope.get("original_factors_only") is not True:
        raise ValueError("full original-factor graph is required; do not duplicate marginalized priors")
    selected_policy = tuple(source_partition(events) if policy is None else policy)
    arc_groups = {}
    for part in selected_policy:
        for arc in part["arc_ids"]:
            if arc in arc_groups:
                raise ValueError("one source arc cannot appear in overlapping calibration groups")
            arc_groups[arc] = str(part["group_id"])
    rows, sums, counts = [], {}, Counter()
    for index, event in enumerate(events):
        key = X(index)
        if event.get("feet") and not navigation_values.exists(key):
            raise ValueError("full no-foot graph lacks a measured historical pose")
        pose = navigation_values.atPose3(key)
        rotation, position = pose.rotation().matrix(), pose.translation()
        for foot in event.get("feet", []):
            if not foot.get("support_eligible", True):
                continue
            arc = str(foot["arc_id"])
            measured = np.asarray(foot["point_body"], float)
            rows.append(dict(time_s=float(event["time_s"]), pose_key=key, arc=arc,
                             rotation=rotation, position=position, measured=measured,
                             source_row=foot.get("source_row"), foot_id=foot.get("foot_id")))
            sums[arc] = sums.get(arc, np.zeros(3)) + position + rotation @ measured
            counts[arc] += 1
    if not rows:
        raise ValueError("no eligible observed foot rows in the source interval")
    origins = {arc: sums[arc]/counts[arc] for arc in sums}
    linear = navigation_graph.linearize(navigation_values)
    for j in range(linear.size()):
        if linear.at(j).isConstrained():
            raise ValueError("calibration source requires a proper unconstrained navigation chart")
    net, lognorm = _qr(linear)
    scope.update(foot_observations=len(rows), foot_scalar_rows=3*len(rows),
                 contact_nuisance_dimension=3*len(origins), group_count=len(selected_policy),
                 group_size_histogram=dict(Counter(len(p["arc_ids"]) for p in selected_policy)),
                 unassigned_foot_observations=sum(r["arc"] not in arc_groups for r in rows),
                 navigation_conditional_count=net.size(),
                 cross_time_covariance="COMPLETE_SPARSE_GAUSSIAN_GRAPH",
                 cross_group_navigation_covariance="PRESERVED_JOINTLY",
                 partition_scope="MEASURED_SOURCE_PARTITION_NOT_SLIP_LABELS",
                 approximation="ONE_FIXED_NONLINEAR_NAVIGATION_AND_CONTACT_CHART")
    return SupportMotionProblem(net, lognorm, tuple(rows), origins, arc_groups,
                                selected_policy, float(foot_sigma_m), float(foot_tau_s), scope)


def integrated_ou_transition(dt, tau, sigma):
    """Argument-order adapter to the navigator's same exact OU process."""
    return support_motion_transition(dt, sigma, tau)


def _affine_factor(blocks, rhs, covariance):
    """Arbitrary sparse affine row, whitened once with its full covariance."""
    chol = linalg.cholesky(covariance, lower=True)
    arrays = {k: linalg.solve_triangular(chol, a, lower=True) for k, a in blocks.items()}
    target = linalg.solve_triangular(chol, np.asarray(rhs, float), lower=True)
    keys = tuple(arrays)
    zeros = gtsam.Values()
    for key, a in arrays.items():
        zeros.insert_vector(key, np.zeros(a.shape[1]))
    def error(_factor, values, jacobians):
        residual = -target.copy()
        for j, key in enumerate(keys):
            residual += arrays[key] @ values.atVector(key)
            if jacobians is not None:
                jacobians[j] = np.asfortranarray(arrays[key])
        return residual
    nonlinear = gtsam.CustomFactor(gtsam.noiseModel.Unit.Create(len(target)), list(keys), error)
    lognorm = -.5*(len(target)*math.log(2*math.pi) + 2*np.log(np.diag(chol)).sum())
    return nonlinear.linearize(zeros), float(lognorm)


def assemble_support_motion_graph(problem, parameters):
    """Return normalized-factor graph; c has no prior and is integrated out."""
    sigma, tau = parameters.velocity_sigma_mps, parameters.tau_s
    if not (math.isfinite(sigma) and math.isfinite(tau) and sigma >= 0 and tau > 0):
        raise ValueError("finite nonnegative velocity sigma and positive tau required")
    graph = gtsam.GaussianFactorGraph()
    for j in range(problem.navigation_conditionals.size()):
        graph.push_back(problem.navigation_conditionals.at(j))
    normalizer = problem.navigation_log_normalizer
    contacts = {arc: gtsam.symbol('c', i) for i, arc in enumerate(sorted(problem.contact_origins))}
    existing = set(graph.keyVector())
    if existing.intersection(contacts.values()):
        raise ValueError("no-foot navigation graph already contains contact keys")
    process_at, process_previous, next_motion = {}, {}, 0
    for row in problem.foot_rows:
        group = problem.arc_groups.get(row["arc"])
        identity = (group, row["time_s"])
        if sigma == 0 or group is None or identity in process_at:
            continue
        key = gtsam.symbol('s', next_motion)
        next_motion += 1
        if key in existing:
            raise ValueError("source graph key collides with common-motion state")
        previous = process_previous.get(group)
        if previous is None:
            # s(t0)=0 is a coordinate origin, not a noisy observation.
            factor, ln = _affine_factor({key: np.eye(3)}, np.zeros(3), np.eye(3)*sigma*sigma)
            process_at[identity] = (key, 3)
        else:
            oldtime, oldkey, olddim = previous
            transition, covariance = integrated_ou_transition(row["time_s"]-oldtime, tau, sigma)
            oldblock = -transition if olddim == 6 else -transition[:, 3:]
            factor, ln = _affine_factor({key: np.eye(6), oldkey: oldblock}, np.zeros(6), covariance)
            process_at[identity] = (key, 6)
        graph.push_back(factor)
        normalizer += ln
        process_previous[group] = (row["time_s"], key, process_at[identity][1])
    previous_rows = {}
    for row in problem.foot_rows:
        arc, rotation = row["arc"], row["rotation"]
        relative = rotation.T @ (problem.contact_origins[arc]-row["position"])
        residual = relative-row["measured"]
        blocks = {row["pose_key"]: np.column_stack((_skew(relative), -np.eye(3))),
                  contacts[arc]: rotation.T}
        process = process_at.get((problem.arc_groups.get(arc), row["time_s"]))
        if process is not None and process[1] == 6:
            blocks[process[0]] = np.column_stack((rotation.T, np.zeros((3, 3))))
        old = previous_rows.get(arc)
        covariance = np.eye(3)*problem.foot_sigma_m**2
        original_blocks, original_residual = dict(blocks), residual.copy()
        if old is not None:
            oldtime, oldblocks, oldresidual = old
            dt = row["time_s"]-oldtime
            if dt <= 0:
                raise ValueError("each foot arc needs strictly increasing actual observation times")
            rho = math.exp(-dt/problem.foot_tau_s)
            residual -= rho*oldresidual
            for key, block in oldblocks.items():
                blocks[key] = blocks.get(key, np.zeros_like(block))-rho*block
            covariance *= -math.expm1(-2*dt/problem.foot_tau_s)
        factor, ln = _affine_factor(blocks, -residual, covariance)
        graph.push_back(factor)
        normalizer += ln
        previous_rows[arc] = (row["time_s"], original_blocks, original_residual)
    return graph, normalizer


def evaluate_support_motion_likelihood(problem, parameters):
    graph, factor_log_normalizer = assemble_support_motion_graph(problem, parameters)
    posterior, posterior_log_normalizer = _qr(graph)
    solution = posterior.optimize()
    cost = 2*float(graph.error(solution))
    objective = cost + 2*(posterior_log_normalizer-factor_log_normalizer)
    return dict(velocity_sigma_mps=parameters.velocity_sigma_mps, tau_s=parameters.tau_s,
                restricted_objective=objective, residual_cost=cost,
                integrated_log_normalization=2*(posterior_log_normalizer-factor_log_normalizer),
                degrees_of_freedom=3*(len(problem.foot_rows)-len(problem.contact_origins)),
                parameter_scope="LOCAL_GAUSSIAN_RESTRICTED_LIKELIHOOD_NOT_PROBABILITY_CALIBRATION")


def profile_support_motion(problem, sigma_grid, tau_grid, *, deviance_width=5.991464547107982):
    sigmas, taus = sorted(set(map(float, sigma_grid))), sorted(set(map(float, tau_grid)))
    if not sigmas or not taus:
        raise ValueError("nonempty declared sigma/tau grid required")
    rows = [evaluate_support_motion_likelihood(problem, MotionParameters(s, t))
            for s in sigmas for t in (taus[:1] if s == 0 else taus)]
    best = min(rows, key=lambda r: r["restricted_objective"])
    for row in rows:
        row["relative_deviance"] = row["restricted_objective"]-best["restricted_objective"]
    support = [r for r in rows if r["relative_deviance"] <= deviance_width]
    zero_supported = any(r["velocity_sigma_mps"] == 0 for r in support)
    sigma_range = [min(r["velocity_sigma_mps"] for r in support), max(r["velocity_sigma_mps"] for r in support)]
    positive = [r for r in support if r["velocity_sigma_mps"] > 0]
    tau_range = ([min(r["tau_s"] for r in positive), max(r["tau_s"] for r in positive)] if positive else None)
    boundary = (sigma_range[-1] == max(sigmas) or
                bool(positive) and (tau_range[0] == min(taus) or tau_range[1] == max(taus)))
    identifiable = [2*r["velocity_sigma_mps"]**2/r["tau_s"] for r in support]
    return dict(rows=rows, grid_minimum=best, relative_deviance_width=deviance_width,
                contour_scope="DECLARED_PROFILE_WIDTH_NOT_CALIBRATED_CONFIDENCE_REGION",
                velocity_sigma_range_mps=sigma_range, positive_sigma_tau_range_s=tau_range,
                diffusion_combination_range_m2ps3=[min(identifiable), max(identifiable)],
                fixed_model_supported=zero_supported, tau_identified=False,
                tau_bounded_on_evaluated_grid=bool(positive) and not zero_supported and not boundary,
                profile_touches_grid_boundary=boundary,
                identification_status=("ZERO_OR_BOUNDARY_UNRESOLVED" if zero_supported or boundary else
                                       "BOUNDED_ON_EVALUATED_GRID_CONTINUOUS_IDENTIFICATION_NOT_PROVEN"),
                probability_calibration_complete=False,
                support_motion_model={"velocity_sigma_mps":best["velocity_sigma_mps"], "tau_s":best["tau_s"]},
                working_value_selection="MINIMUM_OF_PREDECLARED_SOURCE_ONLY_GRID_NOT_NAVIGATION_ERROR",
                automatic_parameter_freeze=False, scope=problem.source_scope,
                policy=list(problem.policy))
