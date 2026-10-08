"""Reference-free restricted likelihood for physical SD phase-noise calibration.

This is an offline measurement-model calculation, not navigation or integer
acceptance. Fixed contrasts eliminate per-epoch geometry; physical integer
coordinates are relaxed and integrated out only in this calibration likelihood.
The beta process follows a source signal across integer slips, with no arbitrary
constant bias and no change to the caller's original observation covariance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import math
import numpy as np
from scipy import linalg

from ..carrier_phase.arc_relations import DdArcRelation
from ..carrier_phase.temporal import EpochBlock
from .carrier_relations import reparameterize_epoch_blocks


@dataclass(frozen=True)
class NoiseParameters:
    white_sd_sigma_m: float = 0.0
    beta_sd_sigma_m: float = 0.0
    tau_s: float = 0.8


@dataclass(frozen=True)
class ContrastEpoch:
    time_s: float
    rhs: np.ndarray  # fixed contrasts of [y, all physical forest N columns]
    source_design: np.ndarray  # meters of phase error per physical SD signal


@dataclass(frozen=True)
class NoiseLikelihoodProblem:
    epochs: tuple[ContrastEpoch, ...]
    integer_basis_labels: tuple[str, ...]
    physical_source_signals: tuple[str, ...]
    original_rows: int
    geometry_rank: int
    contrast_rows: int
    integer_rank: int
    degrees_of_freedom: int


@dataclass(frozen=True)
class RestrictedLikelihood:
    residual_cost: float
    covariance_log_determinant: float
    integer_information_log_determinant: float
    restricted_objective: float  # twice negative log likelihood minus fixed constants
    degrees_of_freedom: int
    integer_rank: int
    float_integer_solution: np.ndarray
    projected_innovation_residual: np.ndarray


def _finish(whitened_rhs: np.ndarray, logdet: float,
            problem: NoiseLikelihoodProblem) -> RestrictedLikelihood:
    y, design = whitened_rhs[:, 0], whitened_rhs[:, 1:]
    # The physical forest has a fixed full-rank coordinate set chosen once.
    # No parameter-dependent rank truncation, noise floor or pseudoinverse.
    q, r = linalg.qr(design, mode="economic")
    solution = linalg.solve_triangular(r, q.T @ y)
    residual = y - q @ (q.T @ y)
    cost = float(residual @ residual)
    information_logdet = float(2 * np.log(np.abs(np.diag(r))).sum())
    return RestrictedLikelihood(cost, float(logdet), information_logdet,
        cost + float(logdet) + information_logdet, problem.degrees_of_freedom,
        problem.integer_rank, solution, residual)


def prepare_source_noise_likelihood(blocks: Sequence[EpochBlock]) -> NoiseLikelihoodProblem:
    """Create parameter-independent geometry contrasts and fixed integer basis.

    Both receiver contributions enter one SD source. Without distinguishable
    covariance structures only their variance sum is identifiable from DD.
    Thus the process state is one coordinate per signal identity, with integer
    arc tokens deliberately absent from beta identity.
    """
    blocks = tuple(blocks)
    forest = reparameterize_epoch_blocks(blocks, label_mode="physical_sd_arcs",
                                        available_time_s=blocks[-1].time_s)
    signals = tuple(sorted({node.signal for b in blocks for label in b.ambiguity_labels
                            for node in (DdArcRelation.from_label(label).target,
                                         DdArcRelation.from_label(label).pivot)}))
    signal_index = {signal: i for i, signal in enumerate(signals)}
    epochs, total_rows, geometry_rank = [], 0, 0
    for original, mapped in zip(blocks, forest.blocks):
        m = len(original.ambiguity_labels)
        if len(original.y) != 2 * m:
            raise ValueError("physical source model requires raw code-then-phase DD rows")
        source = np.zeros((2 * m, len(signals)))
        for j, label in enumerate(original.ambiguity_labels):
            relation = DdArcRelation.from_label(label)
            source[m+j, signal_index[relation.target.signal]] = 1.0
            source[m+j, signal_index[relation.pivot.signal]] = -1.0
        chol = linalg.cholesky(original.Q, lower=True)
        bw = linalg.solve_triangular(chol, original.B, lower=True)
        if np.linalg.matrix_rank(bw) != original.B.shape[1]:
            raise ValueError("free per-epoch baseline is not full rank in original Q")
        q, _ = linalg.qr(bw, mode="full")
        null = q[:, original.B.shape[1]:].T
        rhs = null @ linalg.solve_triangular(chol,
            np.column_stack((original.y, mapped.A)), lower=True)
        h = null @ linalg.solve_triangular(chol, source, lower=True)
        epochs.append(ContrastEpoch(float(original.time_s), rhs, h))
        total_rows += len(original.y)
        geometry_rank += original.B.shape[1]
    all_rhs = np.vstack([e.rhs for e in epochs])
    integer_rank = len(forest.basis_labels)
    if np.linalg.matrix_rank(all_rhs[:, 1:]) != integer_rank:
        raise ValueError("physical forest integers are not full rank after fixed geometry contrasts")
    rows = len(all_rhs)
    return NoiseLikelihoodProblem(tuple(epochs), forest.basis_labels, signals,
        total_rows, geometry_rank, rows, integer_rank, rows-integer_rank)


def evaluate_source_noise_likelihood(problem: NoiseLikelihoodProblem,
                                     parameters: NoiseParameters) -> RestrictedLikelihood:
    """Exact linear Kalman innovations for y and every float-N column together.

    All matrices are at most one epoch or source-state dimension, except the
    tall matrix of whitened RHS used by the final QR. No all-observation dense
    covariance is formed. Missing signals keep their physical beta identity.
    """
    white, beta, tau = (parameters.white_sd_sigma_m,
                        parameters.beta_sd_sigma_m, parameters.tau_s)
    if not all(math.isfinite(v) for v in (white, beta, tau)) or min(white, beta) < 0 or tau <= 0:
        raise ValueError("finite nonnegative SD scales and positive finite tau required")
    count = len(problem.physical_source_signals)
    identity = np.eye(count)
    covariance = beta * beta * identity
    means = np.zeros((count, 1 + problem.integer_rank))
    previous_time = problem.epochs[0].time_s
    chunks, logdet = [], 0.0
    for epoch in problem.epochs:
        rho = math.exp(-(epoch.time_s-previous_time)/tau)
        covariance = rho*rho*covariance + (1-rho*rho)*beta*beta*identity
        means = rho*means
        h = epoch.source_design
        measurement_q = np.eye(len(epoch.rhs)) + white*white*(h @ h.T)
        cross = covariance @ h.T
        innovation_q = measurement_q + h @ cross
        chol = linalg.cholesky(innovation_q, lower=True)
        innovation = epoch.rhs - h @ means
        chunks.append(linalg.solve_triangular(chol, innovation, lower=True))
        logdet += float(2*np.log(np.diag(chol)).sum())
        gain = linalg.cho_solve((chol, True), cross.T).T
        means += gain @ innovation
        # Joseph covariance uses actual Q, not a diagonal approximation/floor.
        transition = identity - gain @ h
        covariance = transition @ covariance @ transition.T + gain @ measurement_q @ gain.T
        covariance = (covariance + covariance.T)*0.5
        previous_time = epoch.time_s
    return _finish(np.vstack(chunks), logdet, problem)


def dense_source_noise_likelihood(problem: NoiseLikelihoodProblem,
                                  parameters: NoiseParameters) -> RestrictedLikelihood:
    """Small-window equivalence oracle; do not use for long calibration windows."""
    h = np.vstack([e.source_design for e in problem.epochs])
    rhs = np.vstack([e.rhs for e in problem.epochs])
    times = np.concatenate([np.full(len(e.rhs), e.time_s) for e in problem.epochs])
    white, beta, tau = (parameters.white_sd_sigma_m,
                        parameters.beta_sd_sigma_m, parameters.tau_s)
    covariance = linalg.block_diag(*[
        np.eye(len(e.rhs)) + white*white*(e.source_design @ e.source_design.T)
        for e in problem.epochs])
    covariance += beta*beta*np.exp(-np.abs(times[:, None]-times[None, :])/tau)*(h @ h.T)
    chol = linalg.cholesky(covariance, lower=True)
    return _finish(linalg.solve_triangular(chol, rhs, lower=True),
                   float(2*np.log(np.diag(chol)).sum()), problem)


@dataclass(frozen=True)
class PhysicalSourceIncidence:
    source_signals: tuple[str, ...]
    D: np.ndarray  # code rows zero; phase rows target(+1)-pivot(-1)


@dataclass(frozen=True)
class SourceNoiseCovariance:
    source_signals: tuple[str, ...]
    source_incidence: tuple[np.ndarray, ...]
    row_slices: tuple[slice, ...]
    times_s: np.ndarray
    original: np.ndarray
    white: np.ndarray
    beta: np.ndarray
    total: np.ndarray


def physical_source_incidence(block: EpochBlock,
                              source_signals: Sequence[str] | None = None) -> PhysicalSourceIncidence:
    """Raw DD incidence for meter-valued physical SD source error.

    Unlike the integer forest, identity is the physical signal string alone:
    integer slips change N coordinates without inventing a new beta source.
    The supplied common order lets a graph and candidate window share keys.
    """
    relations = tuple(DdArcRelation.from_label(label) for label in block.ambiguity_labels)
    signals = tuple(source_signals) if source_signals is not None else tuple(sorted({
        node.signal for relation in relations for node in (relation.target,relation.pivot)}))
    m = len(relations)
    if len(block.y) != 2*m:
        raise ValueError("source incidence requires original code-then-phase DD rows")
    positions = {signal:i for i,signal in enumerate(signals)}
    incidence = np.zeros((len(block.y),len(signals)))
    for row,relation in enumerate(relations):
        incidence[m+row,positions[relation.target.signal]] = 1.0
        incidence[m+row,positions[relation.pivot.signal]] = -1.0
    return PhysicalSourceIncidence(signals,incidence)


def assemble_source_noise_covariance(
        blocks: Sequence[EpochBlock], parameters: NoiseParameters,
        source_signals: Sequence[str] | None = None) -> SourceNoiseCovariance:
    """Exact components for a short raw proposal window, without changing Q.

    Original source Q is block diagonal across original epochs. Added white
    terms are independent physical SD errors, not independent DD inflation.
    Beta is stationary with Cov(beta_s(t),beta_v(u)) =
    sigma_beta^2 * exp(-abs(t-u)/tau) * I[s=v]. The full cross-epoch DD blocks
    preserve shared targets and changing pivots. For long calibration windows
    use evaluate_source_noise_likelihood instead of forming this dense matrix.
    """
    blocks = tuple(blocks)
    signals = tuple(source_signals) if source_signals is not None else tuple(sorted({
        signal for block in blocks for signal in physical_source_incidence(block).source_signals}))
    incidences = tuple(physical_source_incidence(block,signals).D for block in blocks)
    counts = np.r_[0,np.cumsum([len(block.y) for block in blocks])]
    slices = tuple(slice(int(a),int(b)) for a,b in zip(counts[:-1],counts[1:]))
    times = np.array([block.time_s for block in blocks])
    original = linalg.block_diag(*[block.Q for block in blocks])
    white = linalg.block_diag(*[parameters.white_sd_sigma_m**2*(d@d.T) for d in incidences])
    beta = np.zeros_like(original)
    for i,(d,left) in enumerate(zip(incidences,slices)):
        for j in range(i+1):
            right=slices[j]
            covariance=parameters.beta_sd_sigma_m**2*math.exp(-abs(times[i]-times[j])/parameters.tau_s)*(d@incidences[j].T)
            beta[left,right]=covariance
            if i != j: beta[right,left]=covariance.T
    return SourceNoiseCovariance(signals,incidences,slices,times,
                                  original,white,beta,original+white+beta)
