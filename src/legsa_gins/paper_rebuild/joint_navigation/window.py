"""Checkpointable fixed-lag graph for the joint support/carrier estimator.

GTSAM performs both nonlinear optimization and partial Gaussian elimination.
Only factors incident on expired variables are marginalized.  Other nonlinear
factors remain available for relinearization; the separator prior retains its
linearization anchor and all cross blocks in a LinearContainerFactor.
"""

from dataclasses import dataclass
from typing import Iterable

import gtsam
import numpy as np


def key_ordering(keys):
    ordering = gtsam.Ordering()
    for key in keys:
        ordering.push_back(int(key))
    return ordering


def eliminate_qr(linear: gtsam.GaussianFactorGraph, eliminated_keys):
    """Sparse local QR with a Jacobian separator throughout.

    Forming a Hessian Schur complement can lose positive semidefiniteness when
    millisecond IMU bias transitions coexist with much weaker PV/contact rows.
    The square-root representation preserves these scales without adding a
    prior or modifying the source noise. Exact linear coordinates stay exact.
    """
    factors = {j: linear.at(j) for j in range(linear.size())}
    incident = {}
    for j, factor in factors.items():
        for key in factor.keys():
            incident.setdefault(key, set()).add(j)
    next_id = linear.size()
    conditionals = gtsam.GaussianBayesNet()
    for key in eliminated_keys:
        local = gtsam.GaussianFactorGraph()
        for j in sorted(incident[key]):
            factor = factors.pop(j)
            local.push_back(factor)
            for neighbor in factor.keys():
                incident[neighbor].remove(j)
        neighbors = sorted({neighbor for j in range(local.size())
                            for neighbor in local.at(j).keys()} - {key})
        jacobian = gtsam.JacobianFactor(local, key_ordering([key, *neighbors]))
        conditional, remainder = jacobian.eliminate(key_ordering([key]))
        conditionals.push_back(conditional)
        if remainder.keys():
            factors[next_id] = remainder
            for neighbor in remainder.keys():
                incident.setdefault(neighbor, set()).add(next_id)
            next_id += 1
    remaining = gtsam.GaussianFactorGraph()
    for factor in factors.values():
        remaining.push_back(factor)
    return conditionals, remaining


@dataclass(frozen=True)
class WindowSnapshot:
    """In-memory checkpoint; referenced factors must remain immutable."""

    factors: tuple
    values: gtsam.Values
    times: dict[int, float]
    time_s: float
    marginalized_total: int
    objective_offset: float
    linearization_values: gtsam.Values | None = None
    linear_factors: tuple | None = None
    conditional_delta: gtsam.VectorValues | None = None


class JointWindow:
    def __init__(self, lag_s: float = 5.0):
        self.lag_s = float(lag_s)
        self.values = gtsam.Values()
        self.factors: list = []
        self.times: dict[int, float] = {}
        self.time_s = 0.0
        self.marginalized_total = 0
        self.objective_offset = 0.0
        self.last_marginalized: tuple[int, ...] = ()
        self.gaussian_only = False
        self.linearization_values: gtsam.Values | None = None
        self._linear_factors: tuple | None = None
        self._conditional_delta: gtsam.VectorValues | None = None
        self.params = gtsam.LevenbergMarquardtParams()
        self.params.setMaxIterations(40)
        self.params.setRelativeErrorTol(1e-8)
        self.params.setAbsoluteErrorTol(1e-8)

    @staticmethod
    def _graph(factors: Iterable) -> gtsam.NonlinearFactorGraph:
        graph = gtsam.NonlinearFactorGraph()
        for factor in factors:
            graph.push_back(factor)
        return graph

    @property
    def graph(self) -> gtsam.NonlinearFactorGraph:
        """Fresh graph container; its immutable factors may be shared."""
        return self._graph(self.factors)

    @staticmethod
    def _linear_graph(factors) -> gtsam.GaussianFactorGraph:
        graph = gtsam.GaussianFactorGraph()
        for factor in factors:
            graph.push_back(factor)
        return graph

    @property
    def linearization_delta(self):
        """Actual QR mean; retract/Log would wrap rotations beyond pi."""
        return self._conditional_delta

    def optimize(self, *, gaussian_only: bool | None = None,
                 linearization_values: gtsam.Values | None = None) -> gtsam.Values:
        """Solve either the original nonlinear graph or one declared linearization.

        The caller maps physical variables into the shared anchor. Model-private
        nuisance keys retain their previous anchor or their initial seed. A
        Gaussian solve never relinearizes at its own conditional solution.
        """
        mode = self.gaussian_only if gaussian_only is None else bool(gaussian_only)
        if not mode:
            self.values = gtsam.LevenbergMarquardtOptimizer(
                self.graph, self.values, self.params).optimize()
            self.gaussian_only = False
            self.linearization_values = None
            self._linear_factors = None
            self._conditional_delta = None
            return self.values
        if linearization_values is None and self.linearization_values is None:
            raise ValueError("a Gaussian conditional needs an explicit linearization anchor")
        anchor = gtsam.Values(self.values)
        for source in (self.linearization_values, linearization_values):
            if source is not None:
                selected = gtsam.Values(source)
                for key in list(selected.keys()):
                    if not anchor.exists(key):
                        selected.erase(key)
                anchor.update(selected)
        linear = self.graph.linearize(anchor)
        ordering = gtsam.Ordering.ColamdGaussianFactorGraph(linear)
        keys = [ordering.at(i) for i in range(ordering.size())]
        conditionals, _ = eliminate_qr(linear, keys)
        self._conditional_delta = conditionals.optimize()
        self.values = anchor.retract(self._conditional_delta)
        self.gaussian_only = True
        self.linearization_values = anchor
        self._linear_factors = tuple(linear.at(i) for i in range(linear.size()))
        return self.values

    def update(
        self,
        new_factors: Iterable,
        new_values: gtsam.Values,
        timestamps: dict[int, float],
        time_s: float,
        retain_keys: set[int] | None = None,
        *,
        gaussian_only: bool = False,
        linearization_values: gtsam.Values | None = None,
    ) -> gtsam.Values:
        """Add events, jointly optimize, then marginalize expired states.

        ``new_values`` contains only new keys.  Timestamps may also refresh
        existing keys.  ``retain_keys`` explicitly keeps live contact/carrier
        variables even when their last observation predates the pose window.
        The caller owns source dependencies and checkpoints before first use.
        """
        self.values.insert(new_values)
        self.times.update({int(k): float(t) for k, t in timestamps.items()})
        self.factors.extend(new_factors)
        self.time_s = float(time_s)
        self.optimize(gaussian_only=gaussian_only, linearization_values=linearization_values)
        retained = set() if retain_keys is None else set(retain_keys)
        expired = sorted(
            (
                key
                for key, stamp in self.times.items()
                if stamp < self.time_s - self.lag_s and key not in retained
            ),
            key=lambda key: (self.times[key], key),
        )
        self.last_marginalized = tuple(expired)
        if expired:
            self._marginalize(expired)
        return self.values

    def _marginalize(self, expired: list[int]) -> None:
        expired_set = set(expired)
        incident, unchanged = [], []
        incident_linear, unchanged_linear = [], []
        for index, factor in enumerate(self.factors):
            target = incident if expired_set.intersection(factor.keys()) else unchanged
            target.append(factor)
            if self.gaussian_only:
                linear_target = incident_linear if target is incident else unchanged_linear
                linear_target.append(self._linear_factors[index])

        # This is the Gaussian Schur complement at the optimized state. Do not
        # rebuild it from diagonal marginals or add the incident factors again.
        # Constrained QR can omit constant residual rows from its remainder;
        # retain that conditional cost explicitly for comparing hypotheses.
        linear = (self._linear_graph(incident_linear) if self.gaussian_only
                  else self._graph(incident).linearize(self.values))
        eliminated, remainder = eliminate_qr(linear, expired)

        separator = {key for factor in incident for key in factor.keys()} - expired_set
        anchor = gtsam.Values(self.linearization_values if self.gaussian_only else self.values)
        for key in list(anchor.keys()):
            if key not in separator:
                anchor.erase(key)
        zero_separator = anchor.zeroVectors()
        # Optimize the eliminated conditional exactly with separator delta=0.
        # Unlike evaluating the original graph at all-zero deltas, this remains
        # exact even if the nonlinear LM iterate is not a stationary point.
        conditional_optimum = eliminated.optimize(zero_separator)
        self.objective_offset += float(
            linear.error(conditional_optimum) - remainder.error(zero_separator))
        prior = gtsam.LinearContainerFactor.ConvertLinearGraph(remainder, anchor)
        self.factors = unchanged + [prior.at(i) for i in range(prior.size())]
        if self.gaussian_only:
            self._linear_factors = tuple(unchanged_linear) + tuple(
                remainder.at(i) for i in range(remainder.size()))
        for key in expired:
            self.values.erase(key)
            del self.times[key]
            if self.gaussian_only:
                self.linearization_values.erase(key)
        if self.gaussian_only:
            retained_delta = gtsam.VectorValues()
            for key in self.values.keys():
                retained_delta.insert(key, self._conditional_delta.at(key))
            self._conditional_delta = retained_delta
        self.marginalized_total += len(expired)

    def snapshot(self) -> WindowSnapshot:
        """Copy mutable state; factors are shared without ever mutating them."""
        return WindowSnapshot(
            tuple(self.factors),
            gtsam.Values(self.values),
            dict(self.times),
            self.time_s,
            self.marginalized_total,
            self.objective_offset,
            None if self.linearization_values is None else gtsam.Values(self.linearization_values),
            self._linear_factors,
            None if self._conditional_delta is None else gtsam.VectorValues(self._conditional_delta),
        )

    def restore(self, snapshot: WindowSnapshot) -> gtsam.Values:
        self.factors = list(snapshot.factors)
        self.values = gtsam.Values(snapshot.values)
        self.times = dict(snapshot.times)
        self.time_s = snapshot.time_s
        self.marginalized_total = snapshot.marginalized_total
        self.objective_offset = snapshot.objective_offset
        self.last_marginalized = ()
        self.linearization_values = (None if snapshot.linearization_values is None
                                     else gtsam.Values(snapshot.linearization_values))
        self._linear_factors = snapshot.linear_factors
        self._conditional_delta = (None if snapshot.conditional_delta is None
                                   else gtsam.VectorValues(snapshot.conditional_delta))
        self.gaussian_only = self.linearization_values is not None
        return self.values

    def error(self) -> float:
        """Current conditional objective, not a normalized branch probability."""
        if self.gaussian_only:
            return float(self._linear_graph(self._linear_factors).error(
                self.linearization_delta)) + self.objective_offset
        return float(self.graph.error(self.values)) + self.objective_offset

    def joint_covariance(self, keys: list[int]) -> np.ndarray:
        """Joint Gaussian marginal in the declared anchor's tangent coordinates.

        For a nonlinear window the anchor is its current Values. A Gaussian
        conditional keeps its external anchor; callers querying a different
        manifold chart must transport this covariance explicitly.
        """
        linear = (self._linear_graph(self._linear_factors) if self.gaussian_only
                  else self.graph.linearize(self.values))
        ordering = gtsam.Ordering.ColamdConstrainedLastGaussianFactorGraph(linear, keys, True)
        query = set(keys)
        eliminated = [ordering.at(i) for i in range(ordering.size()) if ordering.at(i) not in query]
        _, remaining = eliminate_qr(linear, eliminated)
        jacobian = gtsam.JacobianFactor(remaining, key_ordering(keys))
        conditional, _ = jacobian.eliminate(key_ordering(keys))
        covariance_root = np.linalg.solve(conditional.R(), np.diag(conditional.get_model().sigmas()))
        return covariance_root @ covariance_root.T

    def covariance(self, key: int) -> np.ndarray:
        if self.gaussian_only:
            return self.joint_covariance([key])
        return gtsam.Marginals(self.graph, self.values).marginalCovariance(key)
