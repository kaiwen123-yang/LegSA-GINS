"""Wen, Zhang and Hsu (TVT 2022), pseudorange/Doppler FGO-GNC.

This is an independent implementation, not the authors' GraphGNSSLib.  The
paper's Eqs. (4)-(5) give the corrected, undifferenced pseudorange factor;
Eqs. (12)-(13) give a Doppler-derived velocity between consecutive positions.
Only variables actually constrained by those factors are allocated: ECEF
position and a clock bias in metres for each system observed at that epoch.
Although Eq. (2) lists velocity, the published factors do not constrain a
separate velocity variable.  No IMU, attitude or clock-transition prior is
introduced.  Doppler velocity/covariance must come from raw Doppler WLS.

The GNC continuation follows Algorithm 1 and Eqs. (17)-(21), with c_GM=2
from PDF p. 7.  There is an explicit typographical inconsistency: printed
Eq. (22) omits a square.  Setting Eq. (21) to zero gives

    r**2 + a * (1 - 1/sqrt(w)) = 0,
    w = (a / (a + r**2))**2,   a = theta*c_GM**2.

This squared expression is the unique minimizer of Eq. (19) with the
Eq. (20) penalty, and recovers exactly the GM objective in Eq. (18).
Algorithm 1 Step 3 explicitly refers to Eq. (21); this implementation uses
that internally consistent interpretation rather than the unsquared typo.
Residual r is whitened (dimensionless), not an unscaled metre residual.

Engineering choices disclosed for this adaptation: full-batch sparse
Gauss-Newton with backtracking; independent GPS/BDS receiver clocks; raw-WLS
initialization; Doppler-only propagation of missing *initial guesses* inside
an anchored connected component; theta clamped to 1 for its last stage; and
alternating minimization at theta=1 until numerical convergence.  Propagated
initial guesses add no factor/prior and are never output as a fallback.
Unanchored or rank-deficient components remain unavailable.  This module
does not open any files, evaluate references, or select any parameter.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu


DEFAULTS: dict[str, Any] = {
    "c_gm": 2.0,
    "theta_divisor": 1.4,
    "cost_relative_tolerance": 1e-8,
    "step_tolerance_m": 1e-5,
    "gradient_tolerance": 1e-8,
    "weight_tolerance": 1e-6,
    "rank_relative_tolerance": 1e-10,
    "max_inner_iterations": 100,
    "max_final_alternations": 200,
    "max_backtracking_steps": 30,
}


def gnc_weight(residual: np.ndarray, theta: float, c_gm: float) -> np.ndarray:
    """Eq. (21) stationary weights; see the Eq. (22) discrepancy above."""
    a = float(theta) * float(c_gm) ** 2
    if not np.isfinite(a) or a <= 0:
        raise ValueError("theta and c_gm must be positive and finite")
    return np.square(a / (a + np.square(np.asarray(residual, dtype=float))))


def gm_loss(residual: np.ndarray, theta: float, c_gm: float) -> np.ndarray:
    """Eq. (18), for a whitened pseudorange residual."""
    a = float(theta) * float(c_gm) ** 2
    rr = np.square(np.asarray(residual, dtype=float))
    return a * rr / (a + rr)


@dataclass
class _Graph:
    """One Doppler-connected component, with analytic sparse Jacobians."""

    epochs: np.ndarray
    observation_indices: np.ndarray
    observation_epoch: np.ndarray
    satellites: np.ndarray
    pseudorange: np.ndarray
    sigma: np.ndarray
    systems: np.ndarray
    clock_columns: np.ndarray
    clocks_for_observation: np.ndarray
    origin: np.ndarray
    initial_state: np.ndarray
    dt: np.ndarray
    doppler: np.ndarray
    whitening: np.ndarray

    @property
    def n_position(self) -> int:
        return len(self.epochs)

    @property
    def n_observation(self) -> int:
        return len(self.pseudorange)

    def residual_jacobian(self, state: np.ndarray) -> tuple[np.ndarray, sparse.csr_matrix]:
        """Eqs. (5), (13), with residual sign observed-minus-predicted."""
        p = state[: 3 * self.n_position].reshape(-1, 3)
        base = self.satellites - self.origin
        observation_position = p[self.observation_epoch]
        difference = base - observation_position
        distance = np.linalg.norm(difference, axis=1)
        if np.any(distance <= 0) or not np.all(np.isfinite(distance)):
            raise FloatingPointError("nonfinite/zero satellite-receiver range")
        los = difference / distance[:, None]
        # Algebraically identical to ||base-p|| - ||base||, but its changes
        # do not suffer nanometre-scale quantization of a 20,000 km range.
        # That quantization can otherwise defeat an inner line search close
        # to convergence after summing thousands of whitened residuals.
        base_distance = np.linalg.norm(base, axis=1)
        range_change = (
            -2 * np.einsum("ij,ij->i", base, observation_position)
            + np.einsum("ij,ij->i", observation_position, observation_position)
        ) / (distance + base_distance)
        pr_residual = (
            (self.pseudorange - base_distance) - state[self.clocks_for_observation] - range_change
        ) / self.sigma
        pr_rows = np.repeat(np.arange(self.n_observation), 4)
        pr_cols = np.column_stack(
            (3 * self.observation_epoch[:, None] + np.arange(3), self.clocks_for_observation)
        ).ravel()
        pr_values = np.column_stack((los / self.sigma[:, None], -1 / self.sigma)).ravel()
        n_edges = len(self.dt)
        if n_edges:
            dv = self.doppler - np.diff(p, axis=0) / self.dt[:, None]
            dv_residual = np.einsum("nij,nj->ni", self.whitening, dv).ravel()
            block = self.whitening / self.dt[:, None, None]
            base_rows = self.n_observation + 3 * np.arange(n_edges)
            rows = np.broadcast_to(base_rows[:, None, None] + np.arange(3)[None, :, None], (n_edges, 3, 3)).ravel()
            cols = np.broadcast_to(3 * np.arange(n_edges)[:, None, None] + np.arange(3)[None, None, :], (n_edges, 3, 3)).ravel()
            all_rows = np.concatenate((pr_rows, rows, rows))
            all_cols = np.concatenate((pr_cols, cols, cols + 3))
            all_values = np.concatenate((pr_values, block.ravel(), -block.ravel()))
            residual = np.concatenate((pr_residual, dv_residual))
        else:
            all_rows, all_cols, all_values = pr_rows, pr_cols, pr_values
            residual = pr_residual
        jacobian = sparse.coo_matrix(
            (all_values, (all_rows, all_cols)), shape=(len(residual), len(state))
        ).tocsr()
        return residual, jacobian

    def translation_information(self, state: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Eliminate epoch/system clocks and inspect the remaining translation.

        Full-rank Doppler edges constrain all position differences in this
        connected component.  Its only possible gauge is a common translation
        (with corresponding clock changes).  Each clock group contributes
        weighted, mean-centred line-of-sight vectors.  Forming these centred
        vectors directly avoids cancellation incorrectly declaring a singleton
        pseudorange group informative.  This is a rank check, never a prior.
        """
        p = state[: 3 * self.n_position].reshape(-1, 3) + self.origin
        delta = self.satellites - p[self.observation_epoch]
        los = delta / np.linalg.norm(delta, axis=1)[:, None]
        group = self.clocks_for_observation - 3 * self.n_position
        inverse_variance = weights / np.square(self.sigma)
        group_weight = np.bincount(group, weights=inverse_variance)
        mean = np.column_stack(
            [np.bincount(group, weights=inverse_variance * los[:, j]) / group_weight for j in range(3)]
        )
        centred = los - mean[group]
        return centred.T @ (inverse_variance[:, None] * centred)


def _full_translation_rank(graph: _Graph, state: np.ndarray, weights: np.ndarray, tolerance: float) -> tuple[bool, list[float]]:
    information = graph.translation_information(state, weights)
    eigenvalues = np.linalg.eigvalsh(information)
    full = bool(np.all(np.isfinite(eigenvalues)) and eigenvalues[-1] > 0 and eigenvalues[0] > tolerance * eigenvalues[-1])
    return full, eigenvalues.tolist()


def _fixed_weight_solve(graph: _Graph, state: np.ndarray, weights: np.ndarray, config: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Sparse Gauss-Newton; no artificial anchor or regularization factor."""
    scale = np.ones(graph.n_observation + 3 * len(graph.dt))
    scale[: graph.n_observation] = np.sqrt(weights)
    state = state.copy()
    reason = "MAX_INNER_ITERATIONS"
    converged = False
    cost = float("nan")
    gradient_norm = float("nan")
    step_norm = float("nan")
    backtracking_total = 0
    accepted_steps = 0
    for iteration in range(int(config["max_inner_iterations"])):
        residual, jacobian = graph.residual_jacobian(state)
        weighted_residual = residual * scale
        weighted_jacobian = jacobian.multiply(scale[:, None]).tocsr()
        cost = float(weighted_residual @ weighted_residual)
        gradient = np.asarray(weighted_jacobian.T @ weighted_residual)
        gradient_norm = float(np.max(np.abs(gradient)))
        if gradient_norm <= config["gradient_tolerance"]:
            reason, converged = "GRADIENT_TOLERANCE", True
            break
        hessian = (weighted_jacobian.T @ weighted_jacobian).tocsc()
        try:
            step = splu(hessian).solve(-gradient)
        except RuntimeError:
            reason = "SINGULAR_NORMAL_MATRIX"
            break
        if not np.all(np.isfinite(step)):
            reason = "NONFINITE_STEP"
            break
        step_norm = float(np.max(np.abs(step)))
        # Test the full undamped step.  A tiny backtracking multiplier alone
        # must not masquerade as a converged state update.
        if step_norm <= config["step_tolerance_m"]:
            reason, converged = "STEP_TOLERANCE", True
            break
        descent = float(gradient @ step)
        accepted = False
        for line_iteration in range(int(config["max_backtracking_steps"])):
            alpha = 0.5**line_iteration
            candidate = state + alpha * step
            new_residual, _ = graph.residual_jacobian(candidate)
            new_cost = float(np.sum(np.square(new_residual * scale)))
            # Armijo decrease on the squared-residual objective.
            if np.isfinite(new_cost) and new_cost <= cost + 2e-4 * alpha * descent:
                state = candidate
                accepted = True
                accepted_steps += 1
                backtracking_total += line_iteration
                break
        if not accepted:
            reason = "LINE_SEARCH_FAILED"
            break
        previous_cost = cost
        cost = new_cost
        if abs(previous_cost - cost) <= config["cost_relative_tolerance"] * max(1.0, previous_cost) and alpha == 1.0:
            reason, converged = "COST_TOLERANCE", True
            break
    final_residual, final_jacobian = graph.residual_jacobian(state)
    cost = float(np.sum(np.square(final_residual * scale)))
    gradient_norm = float(np.max(np.abs(final_jacobian.T @ (final_residual * scale**2))))
    return state, {
        "inner_iterations": iteration + 1,
        "accepted_steps": accepted_steps,
        "backtracking_steps": backtracking_total,
        "converged": converged,
        "termination": reason,
        "weighted_cost": cost,
        "gradient_inf_norm": gradient_norm,
        "full_step_inf_norm_m": step_norm,
    }


def _validate_input(data: dict[str, Any]) -> dict[str, np.ndarray]:
    d = {key: np.asarray(value) for key, value in data.items()}
    required = (
        "time_rel_s", "epoch_index", "sat_pos_ecef_m", "pseudorange_m",
        "pr_sigma_m", "system", "initial_position_ecef_m", "initial_clock_m",
        "doppler_velocity_ecef_mps", "doppler_covariance", "spp_valid",
    )
    missing = [key for key in required if key not in d]
    if missing:
        raise ValueError(f"missing GNC input fields: {missing}")
    n = len(d["time_rel_s"])
    m = len(d["epoch_index"])
    shapes = {
        "time_rel_s": (n,), "epoch_index": (m,), "sat_pos_ecef_m": (m, 3),
        "pseudorange_m": (m,), "pr_sigma_m": (m,), "system": (m,),
        "initial_position_ecef_m": (n, 3), "initial_clock_m": (n, 2),
        "doppler_velocity_ecef_mps": (n, 3), "doppler_covariance": (n, 3, 3),
        "spp_valid": (n,),
    }
    for key, shape in shapes.items():
        if d[key].shape != shape:
            raise ValueError(f"{key}: expected {shape}, got {d[key].shape}")
    if not np.all(np.isfinite(d["time_rel_s"])) or np.any(np.diff(d["time_rel_s"]) <= 0):
        raise ValueError("time_rel_s must be finite and strictly increasing")
    for key in ("epoch_index", "system"):
        if not np.all(np.isfinite(d[key])) or not np.all(d[key] == d[key].astype(np.int64)):
            raise ValueError(f"{key} must contain finite integers")
        d[key] = d[key].astype(np.int64)
    if np.any((d["epoch_index"] < 0) | (d["epoch_index"] >= n)):
        raise ValueError("epoch_index is outside the preserved epoch array")
    if np.any((d["system"] < 0) | (d["system"] > 1)):
        raise ValueError("only declared GPS=0/BDS=1 systems are supported")
    return d


def _prepare_graph(data: dict[str, np.ndarray], epochs: np.ndarray, usable: np.ndarray, whitening: np.ndarray) -> _Graph | None:
    """Prepare a component solely from raw-WLS and Doppler initial guesses."""
    anchors = np.asarray(data["spp_valid"][epochs], dtype=bool) & np.all(np.isfinite(data["initial_position_ecef_m"][epochs]), axis=1)
    if not np.any(anchors):
        return None
    n = len(epochs)
    position = np.asarray(data["initial_position_ecef_m"][epochs], dtype=float).copy()
    dt = np.diff(data["time_rel_s"][epochs])
    doppler = np.asarray(data["doppler_velocity_ecef_mps"][epochs[:-1]], dtype=float)
    first = int(np.flatnonzero(anchors)[0])
    for k in range(first - 1, -1, -1):
        position[k] = position[k + 1] - dt[k] * doppler[k]
    for k in range(first + 1, n):
        if not anchors[k]:
            position[k] = position[k - 1] + dt[k - 1] * doppler[k - 1]
    observation_indices = np.flatnonzero(usable & (data["epoch_index"] >= epochs[0]) & (data["epoch_index"] <= epochs[-1]))
    local_epoch = data["epoch_index"][observation_indices] - epochs[0]
    systems = data["system"][observation_indices]
    clocks = np.full((n, 2), -1, dtype=np.int64)
    if len(observation_indices):
        active = np.unique(np.column_stack((local_epoch, systems)), axis=0)
        clocks[active[:, 0], active[:, 1]] = np.arange(3 * n, 3 * n + len(active))
    else:
        active = np.empty((0, 2), dtype=np.int64)
    origin = position[first].copy()
    x = np.zeros(3 * n + len(active))
    x[: 3 * n] = (position - origin).ravel()
    pr = data["pseudorange_m"][observation_indices]
    satellites = data["sat_pos_ecef_m"][observation_indices]
    sigma = data["pr_sigma_m"][observation_indices]
    distance = np.linalg.norm(satellites - position[local_epoch], axis=1)
    for epoch, system in active:
        initial_clock = data["initial_clock_m"][epochs[epoch], system]
        if not anchors[epoch] or not np.isfinite(initial_clock):
            select = (local_epoch == epoch) & (systems == system)
            inverse_variance = 1.0 / np.square(sigma[select])
            initial_clock = float(np.sum((pr[select] - distance[select]) * inverse_variance) / np.sum(inverse_variance))
        x[clocks[epoch, system]] = initial_clock
    return _Graph(
        epochs=epochs, observation_indices=observation_indices, observation_epoch=local_epoch,
        satellites=satellites, pseudorange=pr, sigma=sigma, systems=systems,
        clock_columns=clocks, clocks_for_observation=clocks[local_epoch, systems],
        origin=origin, initial_state=x, dt=dt, doppler=doppler,
        whitening=whitening[epochs[:-1]],
    )


def solve(data: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Solve one full sequence and preserve every supplied epoch/observation.

    ``sat_pos_ecef_m`` has the Earth-rotation correction applied exactly once
    upstream; ``pseudorange_m`` has satellite-clock, atmosphere and TGD
    corrections applied upstream.  ``pr_sigma_m`` is a standard deviation,
    and ``doppler_covariance`` is a full covariance in (m/s)^2.  No correction
    or extra noise tuning is performed here.  Missing Doppler breaks the graph
    edge; a missing pseudorange does not remove an epoch.  No input is mutated.

    Output ``residuals`` is whitened; ``residuals_m`` is in metres.  ``valid``
    requires initialized, full-rank, converged optimization.  Unavailable
    positions/clocks are NaN and status/denominators remain explicit.  The
    ``weight_history`` records actual weight updates per component, including
    the all-one initialization.  It is diagnostic runtime data, not a table
    of independently executed methods.
    """
    start = perf_counter()
    cfg = dict(DEFAULTS)
    if config is not None:
        cfg.update(config)
    for key in DEFAULTS:
        if not np.isfinite(cfg[key]) or cfg[key] <= 0:
            raise ValueError(f"{key} must be finite and positive")
    if cfg["theta_divisor"] <= 1:
        raise ValueError("theta_divisor must exceed one")
    for key in ("max_inner_iterations", "max_final_alternations", "max_backtracking_steps"):
        if int(cfg[key]) != cfg[key]:
            raise ValueError(f"{key} must be an integer")
    d = _validate_input(data)
    n, m = len(d["time_rel_s"]), len(d["epoch_index"])
    position = np.full((n, 3), np.nan)
    clocks = np.full((n, 2), np.nan)
    valid = np.zeros(n, dtype=bool)
    status = np.full(n, "UNPROCESSED", dtype="U64")
    weights = np.full(m, np.nan)
    residuals = np.full(m, np.nan)
    usable = np.all(np.isfinite(d["sat_pos_ecef_m"]), axis=1) & np.isfinite(d["pseudorange_m"]) & np.isfinite(d["pr_sigma_m"]) & (d["pr_sigma_m"] > 0)
    observation_status = np.where(usable, "UNPROCESSED", "INVALID_RAW_OBSERVATION").astype("U64")
    edge_valid = np.zeros(max(0, n - 1), dtype=bool)
    whitening = np.full((max(0, n - 1), 3, 3), np.nan)
    for k in range(n - 1):
        covariance = np.asarray(d["doppler_covariance"][k], dtype=float)
        if not np.all(np.isfinite(d["doppler_velocity_ecef_mps"][k])) or not np.all(np.isfinite(covariance)):
            continue
        if not np.allclose(covariance, covariance.T, atol=1e-12, rtol=1e-10):
            continue
        try:
            whitening[k] = np.linalg.solve(np.linalg.cholesky(covariance), np.eye(3))
        except np.linalg.LinAlgError:
            continue
        edge_valid[k] = True
    boundaries = np.concatenate(([0], np.flatnonzero(~edge_valid) + 1, [n])) if n else np.array([0])
    iterations: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    weight_history: list[dict[str, Any]] = []
    for component_id, (lower, upper) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        epochs = np.arange(lower, upper)
        graph = _prepare_graph(d, epochs, usable, whitening)
        component: dict[str, Any] = {
            "component_id": component_id, "first_epoch": int(lower), "last_epoch": int(upper - 1),
            "epoch_count": len(epochs), "doppler_edge_count": max(0, len(epochs) - 1),
            "pseudorange_count": int(np.count_nonzero(usable & (d["epoch_index"] >= lower) & (d["epoch_index"] < upper))),
            "status": "UNPROCESSED",
        }
        components.append(component)
        if graph is None:
            status[epochs] = component["status"] = "NO_RAW_WLS_INITIALIZATION_IN_COMPONENT"
            observation_status[usable & (d["epoch_index"] >= lower) & (d["epoch_index"] < upper)] = component["status"]
            continue
        state = graph.initial_state.copy()
        local_weights = np.ones(graph.n_observation)
        component["variable_count"] = len(state)
        component["clock_variable_count"] = int(np.count_nonzero(graph.clock_columns >= 0))
        full_rank, eigenvalues = _full_translation_rank(graph, state, local_weights, cfg["rank_relative_tolerance"])
        component["initial_translation_information_eigenvalues"] = eigenvalues
        if not full_rank:
            status[epochs] = component["status"] = "RANK_DEFICIENT_GNSS_COMPONENT"
            observation_status[graph.observation_indices] = component["status"]
            continue
        initial_residual, _ = graph.residual_jacobian(state)
        theta = max(1.0, 3.0 * float(np.max(np.square(initial_residual[: graph.n_observation]))) / cfg["c_gm"]**2)
        component["theta_initial"] = theta
        component["initialization"] = "RAW_WLS_WITH_DOPPLER_PROPAGATION_FOR_MISSING_INITIAL_GUESSES"
        weight_history.append({"component_id": component_id, "outer_iteration": -1, "theta": theta, "phase": "INITIAL_ALL_ONE", "observation_indices": graph.observation_indices.copy(), "weights": local_weights.copy()})
        outer_iteration = 0
        final_alternations = 0
        previous_final_cost = None
        success = False
        failure = "MAX_FINAL_ALTERNATIONS"
        while True:
            state, inner = _fixed_weight_solve(graph, state, local_weights, cfg)
            r, _ = graph.residual_jacobian(state)
            updated_weights = gnc_weight(r[: graph.n_observation], theta, cfg["c_gm"])
            weight_change = float(np.max(np.abs(updated_weights - local_weights)))
            surrogate_cost = float(np.sum(gm_loss(r[: graph.n_observation], theta, cfg["c_gm"])) + np.sum(np.square(r[graph.n_observation :])))
            record = {
                "component_id": component_id, "outer_iteration": outer_iteration, "theta": theta,
                "phase": "GNC_CONTINUATION" if theta > 1 else "FINAL_THETA_ONE_ALTERNATION",
                **inner, "surrogate_cost": surrogate_cost, "maximum_weight_change": weight_change,
                "weight_min": float(updated_weights.min()), "weight_median": float(np.median(updated_weights)),
                "weight_max": float(updated_weights.max()),
            }
            iterations.append(record)
            local_weights = updated_weights
            weight_history.append({"component_id": component_id, "outer_iteration": outer_iteration, "theta": theta, "phase": record["phase"], "observation_indices": graph.observation_indices.copy(), "weights": local_weights.copy()})
            if not inner["converged"]:
                failure = "NUMERICAL_" + inner["termination"]
                break
            if theta <= 1:
                final_alternations += 1
                cost_converged = previous_final_cost is not None and abs(previous_final_cost - surrogate_cost) <= cfg["cost_relative_tolerance"] * max(1.0, previous_final_cost)
                if weight_change <= cfg["weight_tolerance"] and (cost_converged or final_alternations == 1):
                    success = True
                    break
                previous_final_cost = surrogate_cost
                if final_alternations >= cfg["max_final_alternations"]:
                    break
            theta = max(1.0, theta / cfg["theta_divisor"])
            outer_iteration += 1
        weights[graph.observation_indices] = local_weights
        residuals[graph.observation_indices] = r[: graph.n_observation]
        component["outer_iterations"] = outer_iteration + 1
        component["final_alternations"] = final_alternations
        component["theta_final"] = theta
        component["final_weight_consistency_max_abs"] = weight_change
        full_rank, eigenvalues = _full_translation_rank(graph, state, local_weights, cfg["rank_relative_tolerance"])
        component["final_translation_information_eigenvalues"] = eigenvalues
        if not full_rank:
            success, failure = False, "RANK_DEFICIENT_AFTER_ROBUST_WEIGHTING"
        if success:
            position[epochs] = state[: 3 * graph.n_position].reshape(-1, 3) + graph.origin
            active = graph.clock_columns >= 0
            local_clocks = np.full((len(epochs), 2), np.nan)
            local_clocks[active] = state[graph.clock_columns[active]]
            clocks[epochs] = local_clocks
            valid[epochs] = True
            status[epochs] = component["status"] = "COMPLETED"
        else:
            status[epochs] = component["status"] = failure
        observation_status[graph.observation_indices] = component["status"]
    # These velocities are explicit differences of the optimized positions,
    # not additional state variables or a claimed independently estimated INS.
    velocity = np.full((n, 3), np.nan)
    doppler_residual = np.full((max(0, n - 1), 3), np.nan)
    if n > 1:
        pairs = edge_valid & valid[:-1] & valid[1:]
        velocity[:-1][pairs] = np.diff(position, axis=0)[pairs] / np.diff(d["time_rel_s"])[pairs, None]
        doppler_residual[pairs] = d["doppler_velocity_ecef_mps"][:-1][pairs] - velocity[:-1][pairs]
    return {
        "position_ecef_m": position, "clock_m": clocks, "valid": valid, "status": status,
        "weights": weights, "residuals": residuals, "residuals_m": residuals * d["pr_sigma_m"],
        "observation_status": observation_status, "doppler_edge_valid": edge_valid,
        "doppler_residuals_mps": doppler_residual, "velocity_ecef_mps": velocity,
        "velocity_role": "FINITE_DIFFERENCE_OF_ESTIMATED_POSITIONS_NOT_A_GRAPH_STATE",
        "iterations": iterations, "components": components, "weight_history": weight_history,
        "runtime_s": perf_counter() - start, "expected_epoch_count": n,
        "valid_epoch_count": int(np.count_nonzero(valid)), "raw_observation_count": m,
        "usable_raw_observation_count": int(np.count_nonzero(usable)),
        "terminal_status": "COMPLETED" if n and np.all(valid) else "PARTIAL" if np.any(valid) else "FAILED",
        "solve_mode": "FULL_BATCH_SPARSE_GAUSS_NEWTON_GM_GNC_FUTURE_OBSERVATIONS_USED",
        "weight_equation": "EQ_21_STATIONARY_SQUARED_WEIGHT_EQ_22_TYPO_DISCLOSED",
    }
