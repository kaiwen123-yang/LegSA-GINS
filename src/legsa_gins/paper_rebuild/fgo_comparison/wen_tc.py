"""Wen et al., NAVIGATION 68(2), 2021, DOI 10.1002/navi.421, TC-FGO.

Paper mapping: Eq. (10) p/v/body-accelerometer-bias/clock state; Eqs. (21-23)
constant-velocity position and bias-between factors; Eqs. (3), (25-27) external
AHRS acceleration/velocity factor; Eq. (30) *undifferenced raw pseudorange*;
Eq. (32) full-batch Levenberg-Marquardt. Attitude is an input, never an estimated
state or an output score. This is deliberately not a 15-state IMU-preintegration
graph, an EKF-NAV smoother, or the GNC implementation.

The caller supplies source-corrected code, satellite states, and sensor-only WLS
initial guesses. GPS/BDS have independent epoch clock biases in metres (an
explicit multi-constellation adaptation); absent clocks are not variables and
remain NaN in the output. No Doppler velocity, commercial reference, previous
method trajectory, pose prior, robust loss, or hidden failure fallback is used.
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import MatrixRankWarning, spsolve


DEFAULT_CONFIG = {
    "motion_sigma_m": 0.3,
    "bias_between_sigma_mps2": 0.01,
    "velocity_link_sigma_mps": 0.15,
    "max_iterations": 100,
    "max_linear_solves": 250,
    "initial_damping": 1e-3,
    "gradient_tolerance": 1e-7,
    "relative_cost_tolerance": 1e-10,
    "step_tolerance": 1e-8,
    "rank_relative_tolerance": 1e-10,
}


class WenInputError(ValueError):
    """A required sensor/model field is absent or inconsistent."""


def _array(value, shape, label, *, finite=True):
    result = np.asarray(value, dtype=float)
    if result.shape != shape or (finite and not np.isfinite(result).all()):
        raise WenInputError(f"invalid {label}: expected {shape}, got {result.shape}")
    return result


class WenProblem:
    """Sparse analytic residual/Jacobian, with local position increments in x.

    Each first block is [p_ECEF-origin (m), v_ECEF (m/s), b_body (m/s2)].
    An epoch/constellation clock follows only if at least one code observes it.
    Missing AHRS intervals remove only their INS factor; no output row is removed.
    Motion and bias factors retain all consecutive declared graph nodes.
    """

    def __init__(self, data: dict, ahrs: dict, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.times = np.asarray(data["time_rel_s"], dtype=float)
        self.n = len(self.times)
        if self.times.shape != (self.n,) or self.n < 3 or not np.isfinite(self.times).all() or np.any(np.diff(self.times) <= 0):
            raise WenInputError("at least three chronological graph nodes are required")
        if not np.array_equal(self.times, np.asarray(ahrs["time_rel_s"], float)):
            raise WenInputError("raw-code and AHRS graph node times disagree")
        index = np.asarray(data["epoch_index"])
        if index.ndim != 1 or not np.equal(index, np.asarray(index, dtype=int)).all():
            raise WenInputError("integer observation epoch indices required")
        self.epoch = index.astype(int)
        self.m = len(self.epoch)
        if self.m < 4 or np.any((self.epoch < 0) | (self.epoch >= self.n)):
            raise WenInputError("insufficient code or invalid epoch index")
        system = np.asarray(data["system"])
        if system.shape != (self.m,) or not np.isin(system, [0, 1]).all():
            raise WenInputError("system must be 0=GPS or 1=BDS")
        self.system = system.astype(int)
        self.satellite = _array(data["sat_pos_ecef_m"], (self.m, 3), "satellite ECEF")
        self.code = _array(data["pseudorange_m"], (self.m,), "corrected raw pseudorange")
        self.code_sigma = _array(data["pr_sigma_m"], (self.m,), "code sigma")
        if np.any(self.code_sigma <= 0):
            raise WenInputError("strictly positive code standard deviations required")
        self.dv = _array(ahrs["delta_velocity_ecef_mps"], (self.n - 1, 3), "AHRS delta velocity")
        self.bint = _array(ahrs["bias_integral_ecef_s"], (self.n - 1, 3, 3), "body-bias integral")
        self.lever_dv = _array(ahrs["lever_velocity_delta_ecef_mps"], (self.n - 1, 3), "lever velocity change")
        valid = np.asarray(ahrs["interval_valid"])
        if valid.shape != (self.n - 1,) or not np.isin(valid, [0, 1]).all():
            raise WenInputError("AHRS interval validity shape/value mismatch")
        self.ins_index = np.flatnonzero(valid.astype(bool))
        self.ins_valid = valid.astype(bool)
        if not len(self.ins_index):
            raise WenInputError("no complete AHRS/IMU interval: Wen INS core cannot be instantiated")
        self.clock_map = np.full((self.n, 2), -1, dtype=int)
        clocks = sorted(set(zip(self.epoch.tolist(), self.system.tolist())))
        for j, (i, system_id) in enumerate(clocks):
            self.clock_map[i, system_id] = 9 * self.n + j
        self.size = 9 * self.n + len(clocks)
        self.clock_column = self.clock_map[self.epoch, self.system]
        for key in ("motion_sigma_m", "bias_between_sigma_mps2", "velocity_link_sigma_mps", "rank_relative_tolerance"):
            if not np.isfinite(float(self.config[key])) or float(self.config[key]) <= 0:
                raise WenInputError(f"positive finite {key} required")
        initial = _array(data["initial_position_ecef_m"], (self.n, 3), "raw WLS initialization", finite=False)
        available = np.isfinite(initial).all(axis=1)
        if not available.any():
            raise WenInputError("no sensor-only raw-code WLS position for initialization")
        # This interpolation initializes unknowns only. It neither fills outputs
        # nor adds a trajectory prior; the objective below contains raw factors.
        initial = np.column_stack([np.interp(self.times, self.times[available], initial[available, k]) for k in range(3)])
        self.origin = initial[available][0].copy()
        self.range_anchor = self.origin - self.satellite
        self.anchor_distance = np.linalg.norm(self.range_anchor, axis=1)
        self.code_minus_anchor_distance = self.code - self.anchor_distance
        seed = np.zeros((self.n, 9))
        seed[:, :3] = initial - self.origin
        seed[:, 3:6] = np.gradient(initial, self.times, axis=0)
        self.x0 = np.zeros(self.size)
        self.x0[:9 * self.n] = seed.ravel()
        provided_clock = np.asarray(data.get("initial_clock_m", np.full((self.n, 2), np.nan)), dtype=float)
        if provided_clock.shape != (self.n, 2):
            raise WenInputError("initial_clock_m must have two system columns")
        for i, system_id in clocks:
            value = provided_clock[i, system_id]
            if not np.isfinite(value):
                mask = (self.epoch == i) & (self.system == system_id)
                value = float(np.median(self.code[mask] - np.linalg.norm(initial[i] - self.satellite[mask], axis=1)))
            self.x0[self.clock_map[i, system_id]] = value
        self.row_count = self.m + 6 * (self.n - 1) + 3 * len(self.ins_index)
        # With an unsupported final INS interval, the last v has neither an
        # outgoing motion factor nor an incoming INS link. Remove such strict
        # zero columns from the optimization, and report that velocity as NaN.
        _, initial_jacobian = self.residual_jacobian(self.x0)
        column_norm2 = np.asarray(initial_jacobian.power(2).sum(axis=0)).ravel()
        self.active_columns = np.flatnonzero(column_norm2 > 0)
        self.unconstrained_columns = np.flatnonzero(column_norm2 == 0)
        self.velocity_constrained = np.all(
            column_norm2[(np.arange(self.n)[:, None] * 9 + np.arange(3, 6))] > 0, axis=1)

    def observability(self, x, tolerance):
        """Check the undamped factor Jacobian through its exact chain nullspace.

        Bias-between makes a homogeneous perturbation b_i=b_0. Motion and each
        available INS link then parameterize all positions/velocities by p_0,
        v_0, b_0 and one free velocity jump per missing *internal* INS link.
        An unsupported terminal velocity is already removed as a zero column.
        Eliminate each epoch/system code clock by weighted LOS centering and
        check the resulting much smaller design (normally only nine columns).
        Thus LM damping cannot hide drift gauges or manufacture observability.
        This is a numerical rank test, never an added prior or pseudo-factor.
        """
        internal_gaps = np.flatnonzero(~self.ins_valid[:-1])
        dimension = 9 + 3 * len(internal_gaps)
        gap_columns = {int(k): 9 + 3 * j for j, k in enumerate(internal_gaps)}
        pmap = np.zeros((3, dimension)); pmap[:, :3] = np.eye(3)
        vmap = np.zeros((3, dimension)); vmap[:, 3:6] = np.eye(3)
        position_maps = []
        for k in range(self.n):
            position_maps.append(pmap.copy())
            if k == self.n - 1:
                break
            pmap = pmap + np.diff(self.times)[k] * vmap
            if self.ins_valid[k]:
                vmap[:, 6:9] -= self.bint[k]
            elif k in gap_columns:
                j = gap_columns[k]
                vmap[:, j:j+3] += np.eye(3)
        state = np.asarray(x)[:9 * self.n].reshape(self.n, 9)
        delta = self.range_anchor + state[self.epoch, :3]
        los = delta / np.linalg.norm(delta, axis=1)[:, None]
        blocks = []
        for epoch, system in zip(*np.nonzero(self.clock_map >= 0)):
            selected = (self.epoch == epoch) & (self.system == system)
            if np.count_nonzero(selected) < 2:
                continue  # A single code is absorbed exactly by its clock.
            inv_variance = 1. / self.code_sigma[selected] ** 2
            directions = los[selected]
            # Center differences from the first LOS, so identical LOS cannot
            # acquire fictitious information through weighted-mean roundoff.
            offset = directions - directions[0]
            mean = np.sum(offset * inv_variance[:, None], axis=0) / inv_variance.sum()
            centred = (offset - mean) / self.code_sigma[selected, None]
            blocks.append(centred @ position_maps[epoch])
        design = np.vstack(blocks) if blocks else np.zeros((0, dimension))
        scales = np.linalg.norm(design, axis=0)
        scaled = design / np.where(scales > 0, scales, 1.)
        try:
            singular = np.linalg.svd(scaled, compute_uv=False)
        except np.linalg.LinAlgError:
            return {"verified": False, "full_rank": False, "dimension": dimension,
                    "rank": None, "mode": "REDUCED_CHAIN_NULLSPACE_SVD_FAILED"}
        rank = int(np.sum(singular > tolerance * singular[0])) if len(singular) and singular[0] > 0 else 0
        return {"verified": True, "full_rank": rank == dimension, "dimension": dimension,
                "rank": rank, "mode": "CLOCK_ELIMINATED_CHAIN_NULLSPACE_SVD",
                "relative_tolerance": float(tolerance), "singular_values": singular.tolist(),
                "internal_missing_ins_links": internal_gaps.tolist(),
                "removed_zero_column_count": len(self.unconstrained_columns)}

    def residual_jacobian(self, x, *, jacobian=True):
        x = _array(x, (self.size,), "optimization state")
        state = x[:9 * self.n].reshape(self.n, 9)
        displacement = state[self.epoch, :3]
        delta = self.range_anchor + displacement
        distance = np.linalg.norm(delta, axis=1)
        if np.any(distance < 1):
            raise WenInputError("receiver/satellite geometry is singular")
        # ||a+u||-||a|| = (2*a.u+u.u)/(||a+u||+||a||). This stable
        # algebraic range change preserves the same raw-code objective without
        # repeatedly cancelling two ~20,000 km numbers in LM trial costs.
        range_change = (2 * np.einsum("ij,ij->i", self.range_anchor, displacement)
                        + np.einsum("ij,ij->i", displacement, displacement)) / (distance + self.anchor_distance)
        code_r = (range_change + x[self.clock_column] - self.code_minus_anchor_distance) / self.code_sigma
        dt = np.diff(self.times)
        motion_r = (state[1:, :3] - state[:-1, :3] - state[:-1, 3:6] * dt[:, None]) / self.config["motion_sigma_m"]
        bias_r = (state[1:, 6:9] - state[:-1, 6:9]) / self.config["bias_between_sigma_mps2"]
        ii = self.ins_index
        ins_r = (state[ii + 1, 3:6] - state[ii, 3:6] - self.dv[ii] - self.lever_dv[ii]
                 + np.einsum("nij,nj->ni", self.bint[ii], state[ii, 6:9])) / self.config["velocity_link_sigma_mps"]
        residual = np.concatenate((code_r, motion_r.ravel(), bias_r.ravel(), ins_r.ravel()))
        if not jacobian:
            return residual
        rows, cols, vals = [], [], []

        def add(row, col, value):
            a, b, c = np.broadcast_arrays(row, col, value)
            rows.extend(a.ravel().tolist()); cols.extend(b.ravel().tolist()); vals.extend(c.ravel().tolist())

        add(np.arange(self.m)[:, None], self.epoch[:, None] * 9 + np.arange(3),
            delta / distance[:, None] / self.code_sigma[:, None])
        add(np.arange(self.m), self.clock_column, 1 / self.code_sigma)
        for axis in range(3):
            j = np.arange(self.n - 1)
            row = self.m + j * 3 + axis
            add(row, (j + 1) * 9 + axis, 1 / self.config["motion_sigma_m"])
            add(row, j * 9 + axis, -1 / self.config["motion_sigma_m"])
            add(row, j * 9 + 3 + axis, -dt / self.config["motion_sigma_m"])
            row = self.m + 3 * (self.n - 1) + j * 3 + axis
            add(row, (j + 1) * 9 + 6 + axis, 1 / self.config["bias_between_sigma_mps2"])
            add(row, j * 9 + 6 + axis, -1 / self.config["bias_between_sigma_mps2"])
            row = self.m + 6 * (self.n - 1) + np.arange(len(ii)) * 3 + axis
            add(row, (ii + 1) * 9 + 3 + axis, 1 / self.config["velocity_link_sigma_mps"])
            add(row, ii * 9 + 3 + axis, -1 / self.config["velocity_link_sigma_mps"])
            for body_axis in range(3):
                add(row, ii * 9 + 6 + body_axis,
                    self.bint[ii, axis, body_axis] / self.config["velocity_link_sigma_mps"])
        matrix = sparse.coo_matrix((vals, (rows, cols)), shape=(self.row_count, self.size)).tocsr()
        return residual, matrix


def solve(data: dict, ahrs: dict, config: dict | None = None) -> dict[str, Any]:
    """Solve the paper's non-robust full-batch TC objective with sparse LM.

    A bounded optimizer stop keeps its last iterate only in provisional_*;
    the formal output remains NaN and invalid if optimization did not converge.
    Damping regularizes the step only; it is not an added measurement/prior.
    """
    problem = WenProblem(data, ahrs, config)
    cfg = problem.config
    x = problem.x0.copy()
    damping = float(cfg["initial_damping"])
    if damping <= 0 or not np.isfinite(damping):
        raise WenInputError("positive LM damping required")
    logs = []
    status, converged = "MAX_ITERATIONS_REACHED", False
    accepted = 0
    rejected_multiplier = 2.0
    residual, full_jac = problem.residual_jacobian(x)
    jac = full_jac[:, problem.active_columns]
    cost = float(residual @ residual / 2)
    initial_cost = cost
    initial_observability = problem.observability(x, cfg["rank_relative_tolerance"])
    observable = initial_observability["verified"] and initial_observability["full_rank"]
    linear_solve_limit = int(cfg["max_linear_solves"]) if observable else 0
    for iteration in range(linear_solve_limit):
        gradient = np.asarray(jac.T @ residual).ravel()
        gradient_norm = float(np.linalg.norm(gradient, ord=np.inf))
        if gradient_norm <= cfg["gradient_tolerance"]:
            status, converged = "GRADIENT_TOLERANCE", True
            break
        if accepted >= int(cfg["max_iterations"]):
            break
        normal = (jac.T @ jac).tocsc()
        diagonal = np.maximum(normal.diagonal(), 1e-12)
        with warnings.catch_warnings():
            warnings.simplefilter("error", MatrixRankWarning)
            try:
                step = spsolve(normal + sparse.diags(damping * diagonal), -gradient)
            except (MatrixRankWarning, RuntimeError) as exc:
                status = "LINEAR_SOLVE_FAILED:" + type(exc).__name__
                break
        if not np.isfinite(step).all():
            status = "NONFINITE_LM_STEP"
            break
        candidate = x.copy()
        candidate[problem.active_columns] += step
        trial = problem.residual_jacobian(candidate, jacobian=False)
        trial_cost = float(trial @ trial / 2)
        predicted = float(-gradient @ step - 0.5 * step @ (normal @ step))
        reduction = cost - trial_cost
        rho = reduction / predicted if predicted > 0 else -np.inf
        good = bool(np.isfinite(trial_cost) and reduction > 0 and rho > 0)
        logs.append({"linear_solve": iteration + 1, "accepted": good, "cost_before": cost,
                     "trial_cost": trial_cost, "damping": damping, "gain_ratio": float(rho),
                     "gradient_inf": gradient_norm, "step_inf": float(np.max(np.abs(step)))})
        if good:
            old_cost = cost
            x, cost = candidate, trial_cost
            accepted += 1
            damping *= max(1 / 3, 1 - (2 * rho - 1) ** 3)
            rejected_multiplier = 2.0
            residual, full_jac = problem.residual_jacobian(x)
            jac = full_jac[:, problem.active_columns]
            if reduction <= cfg["relative_cost_tolerance"] * max(1.0, old_cost):
                status, converged = "COST_TOLERANCE", True
                break
            if np.max(np.abs(step)) <= cfg["step_tolerance"]:
                status, converged = "STEP_TOLERANCE", True
                break
        else:
            # A sub-ULP range change can make the trial cost exactly equal near
            # convergence. An over-damped tiny step must not claim convergence.
            if float(np.max(np.abs(step))) <= cfg["step_tolerance"]:
                converged = damping <= float(cfg["initial_damping"])
                status = "STEP_TOLERANCE" if converged else "LM_STEP_STALLED"
                break
            damping *= rejected_multiplier
            rejected_multiplier *= 2
            if not np.isfinite(damping) or damping > 1e18:
                status = "LM_NO_DESCENT"
                break
    else:
        status = "MAX_LINEAR_SOLVES_REACHED"
    if not observable:
        status = ("RANK_DEFICIENT_UNDAMPED_GRAPH" if initial_observability["verified"]
                  else "OBSERVABILITY_NOT_VERIFIED")
        converged = False
    final_observability = problem.observability(x, cfg["rank_relative_tolerance"]) if accepted else initial_observability
    if not final_observability["verified"] or not final_observability["full_rank"]:
        status = ("RANK_DEFICIENT_UNDAMPED_GRAPH" if final_observability["verified"]
                  else "OBSERVABILITY_NOT_VERIFIED")
        converged = False
    state = x[:9 * problem.n].reshape(problem.n, 9)
    clocks = np.full((problem.n, 2), np.nan)
    present = problem.clock_map >= 0
    clocks[present] = x[problem.clock_map[present]]
    position = state[:, :3] + problem.origin
    finite = np.isfinite(position).all(axis=1)
    valid = finite & converged
    velocity = state[:, 3:6].copy()
    velocity[~problem.velocity_constrained] = np.nan
    result = {
        "time_rel_s": problem.times.copy(), "position_ecef_m": position,
        "velocity_ecef_mps": velocity, "velocity_valid": valid & problem.velocity_constrained,
        "accel_bias_body_mps2": state[:, 6:9].copy(),
        "clock_m": clocks, "valid": valid,
        "status": np.full(problem.n, "COMPLETED" if converged else status, dtype="U64"),
        "terminal_status": "COMPLETED" if valid.all() else "FAILED",
        "expected_epoch_count": problem.n, "valid_epoch_count": int(valid.sum()),
        "optimizer_stop": status, "converged": converged, "initial_cost": initial_cost,
        "final_cost": cost, "accepted_steps": accepted, "iteration_logs": logs,
        "initial_observability": initial_observability, "final_observability": final_observability,
        "optimized_parameter_count": len(problem.active_columns),
        "unconstrained_parameter_columns": problem.unconstrained_columns.tolist(),
        "pseudorange_factor_count": problem.m, "motion_factor_count": problem.n - 1,
        "bias_factor_count": problem.n - 1, "ins_factor_count": len(problem.ins_index),
        "missing_ins_interval_count": problem.n - 1 - len(problem.ins_index),
        "ahrs_interval_valid": np.asarray(ahrs["interval_valid"], bool),
        "attitude_output": False, "doppler_factor_count": 0, "dual_yaw_factor_count": 0,
        "output_point": "GNSS1_ANTENNA", "solve_mode": "OFFLINE_FULL_BATCH_LM",
        "future_observations_used": True, "initialization_only_interpolated_wls_count":
            int(np.sum(~np.isfinite(np.asarray(data["initial_position_ecef_m"], float)).all(axis=1))),
    }
    if not converged:
        for name in ("position_ecef_m", "velocity_ecef_mps", "accel_bias_body_mps2", "clock_m"):
            result["provisional_" + name] = result[name].copy()
            result[name] = np.full_like(result[name], np.nan)
    return result
