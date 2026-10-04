"""Actual Ceres 2.2 relinearization via cvg/pyceres (Apache-2.0 bindings).

The OiSAM incremental solver is elsewhere and is not replaced by Ceres. This
module implements only Algorithm2's explicit nonlinear relinearization branch.
GTSAM supplies whitened sensor residuals/analytic local Jacobians. Ceres owns
the nonlinear trust-region iterations and sparse normal Cholesky solves.
"""
from __future__ import annotations

import numpy as np
import gtsam
import pyceres


def node_keys(index):
    return tuple(gtsam.symbol(prefix, index) for prefix in ("x", "v", "b"))


def apply_increment(anchors, indices, increments):
    vector = gtsam.VectorValues()
    for index, delta in zip(indices, increments):
        x, v, b = node_keys(index)
        vector.insert(x, np.asarray(delta[:6]))
        vector.insert(v, np.asarray(delta[6:9]))
        vector.insert(b, np.asarray(delta[9:15]))
    # Values.update(vector3) selects the Point3 overload in GTSAM 4.2. Retract
    # preserves the stored dynamic-vector velocity type and the bias manifold.
    return anchors.retract(vector)


def pose_chart_derivative(anchor, delta):
    """d Local(current, Retract(anchor,delta+d)) / dd at d=0.

    This six-dimensional chart transport is differentiated numerically so it
    follows the exact Pose3 retraction chosen by the installed GTSAM build.
    The IMU/bias/lever derivatives themselves remain the tested analytic ones.
    """
    if np.all(delta == 0):
        return np.eye(6)
    current = anchor.retract(delta)
    derivative = np.zeros((6, 6))
    for j in range(6):
        step = np.zeros(6)
        step[j] = 1e-6
        derivative[:, j] = (current.localCoordinates(anchor.retract(delta + step)) -
                             current.localCoordinates(anchor.retract(delta - step))) / 2e-6
    return derivative


class GTSAMCost(pyceres.CostFunction):
    """One sensor/prior factor, with one or two 15D local parameter blocks."""
    def __init__(self, factor, anchors):
        super().__init__()
        self.factor = factor
        self.indices = sorted({int(gtsam.Symbol(key).index()) for key in factor.keys()})
        self.anchors = gtsam.Values()
        self.layout = {}
        for block, index in enumerate(self.indices):
            x, v, b = node_keys(index)
            self.anchors.insert(x, anchors.atPose3(x))
            self.anchors.insert(v, anchors.atVector(v))
            self.anchors.insert(b, anchors.atConstantBias(b))
            for key, start, width in ((x, 0, 6), (v, 6, 3), (b, 9, 6)):
                self.layout[key] = (block, start, width)
        self.dimension = len(factor.linearize(self.anchors).jacobian()[1])
        self.set_num_residuals(self.dimension)
        self.set_parameter_block_sizes([15] * len(self.indices))
        self.evaluation_count = 0

    def Evaluate(self, parameters, residuals, jacobians):
        values = apply_increment(self.anchors, self.indices, parameters)
        linear = self.factor.linearize(values)
        a, b = linear.jacobian()
        residuals[:] = -b
        self.evaluation_count += 1
        if jacobians is not None:
            derivatives = [np.zeros((self.dimension, 15)) for _ in self.indices]
            cursor = 0
            for key in linear.keys():
                block, start, width = self.layout[key]
                derivatives[block][:, start:start + width] = a[:, cursor:cursor + width]
                cursor += width
            for block, index in enumerate(self.indices):
                if jacobians[block] is None:
                    continue
                derivatives[block][:, :6] = derivatives[block][:, :6] @ pose_chart_derivative(
                    self.anchors.atPose3(node_keys(index)[0]), parameters[block][:6])
                jacobians[block][:] = derivatives[block].ravel()
        return bool(np.isfinite(residuals).all())


def optimize(factors, initial, indices, config):
    anchors = gtsam.Values(initial)
    parameters = {index: np.zeros(15, dtype=np.float64) for index in indices}
    problem = pyceres.Problem()
    costs = [GTSAMCost(factor, anchors) for factor in factors]
    for cost in costs:
        problem.add_residual_block(cost, None, [parameters[i] for i in cost.indices])
    options = pyceres.SolverOptions()
    options.max_num_iterations = int(config["nonlinear_max_iterations"])
    options.num_threads = 1
    options.minimizer_progress_to_stdout = False
    options.linear_solver_type = pyceres.LinearSolverType.SPARSE_NORMAL_CHOLESKY
    options.trust_region_strategy_type = pyceres.TrustRegionStrategyType.LEVENBERG_MARQUARDT
    options.function_tolerance = float(config["nonlinear_relative_cost_tolerance"])
    options.parameter_tolerance = float(config["nonlinear_scaled_step_tolerance"])
    summary = pyceres.SolverSummary()
    pyceres.solve(options, problem, summary)
    if not summary.IsSolutionUsable():
        raise np.linalg.LinAlgError("CERES_UNUSABLE_SOLUTION:" + summary.BriefReport())
    values = apply_increment(anchors, indices, [parameters[i] for i in indices])
    # Ceres counts its initial evaluation as a successful step; subtract that
    # non-iteration when reporting the paper's maximum-20 iteration budget.
    iterations = max(0, int(summary.num_successful_steps + summary.num_unsuccessful_steps) - 1)
    report = {"backend": "Ceres", "ceres_version": pyceres.__ceres_version__,
              "pyceres_version": pyceres.__version__, "iterations": iterations,
              "accepted_steps": max(0, int(summary.num_successful_steps) - 1),
              "initial_cost": summary.initial_cost, "final_cost": summary.final_cost,
              "termination": str(summary.termination_type), "brief_report": summary.BriefReport(),
              "converged": summary.termination_type == pyceres.TerminationType.CONVERGENCE,
              "solution_usable": bool(summary.IsSolutionUsable()),
              "givens_rotations": 0, "cost_evaluations": sum(c.evaluation_count for c in costs),
              "linear_solver": str(summary.linear_solver_type_used), "threads": summary.num_threads_used}
    return values, report
