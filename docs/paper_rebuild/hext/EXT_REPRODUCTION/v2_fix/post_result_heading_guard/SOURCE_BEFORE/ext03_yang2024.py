"""Transparent Yang et al. (2024) baseline-constrained DD Kalman filter.

This module is deliberately backend-neutral.  A raw-observation adapter must
provide within-constellation double-difference blocks, including their full
shared-pivot covariance.  The implementation maps the paper as follows:

* :func:`build_dd_observation` implements Eqs. (1)--(3) and (8)--(9);
* :func:`ned_attitude` implements Eq. (4) and the project's fixed lateral
  antenna conversion;
* :func:`baseline_constraint_linearization` and :func:`constraint_update`
  implement Eqs. (5)--(7);
* :func:`process_epoch` performs the sequential prediction, DD measurement
  update, optional length update, and MLAMBDA ratio decision.

No reference trajectory, status baseline, HPPOSECEF, inertial observation, or
other method output is accepted by this API.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .ext01_clambda import LambdaBridgeError, RTKLIBLambdaBridge


FloatArray = NDArray[np.float64]

BASELINE_LENGTH_M = 0.350
RATIO_THRESHOLD = 3.0
PRIMARY_BASELINE_SIGMA_M = 0.010
SENSITIVITY_BASELINE_SIGMAS_M = (0.001, 0.005, 0.010, 0.020, 0.050)
INITIAL_BASELINE_VARIANCE_M2 = 900.0
INITIAL_AMBIGUITY_VARIANCE_CYCLES2 = 900.0
RTKLIB_COMMIT = "180043ee24b6d2b168f98b64be15f69d50046b1a"
RTKLIB_MOVING_BASE_POSITION_VARIANCE_M2 = 900.0

# The raw adapter owns elevation-dependent code/phase covariance construction.
# It must append these exact parameter names to the runner-side stochastic CSV;
# the core registry below owns every other stochastic value used by this file.
ADAPTER_STOCHASTIC_REGISTRY_REQUIRED_PARAMETERS = (
    "code_measurement_sigma_model",
    "phase_measurement_sigma_model",
    "gps_system_weight",
    "bds_system_weight",
    "shared_pivot_covariance_model",
)

# RTKLIB's official default at the pinned commit (prcopt_default.thresslip).
GEOMETRY_FREE_SLIP_THRESHOLD_M = 0.05
# The paper requires MW and prior-DD checks but publishes no thresholds and the
# pinned relative path has no active MW detector.  The pinned PPP source does
# publish a 10 m MW jump gate; the remaining prior-DD cycle gate is a
# pre-registered physical instantiation, never selected from reference data.
MELBOURNE_WUBBENA_SLIP_THRESHOLD_M = 10.0
PRIOR_DD_AMBIGUITY_SLIP_THRESHOLD_CYCLES = 0.25

EQUATION_CODE_MAP = {
    "Eq. (1)": "build_dd_observation carrier-phase DD rows",
    "Eq. (2)": "DDObservationModel observation/design/covariance",
    "Eq. (3)": "build_dd_observation baseline and ambiguity columns",
    "Eq. (4)": "ned_attitude",
    "Eq. (5)": "BASELINE_LENGTH_M and baseline_constraint_linearization",
    "Eq. (6)": "baseline_constraint_linearization",
    "Eq. (7)": "constraint_update",
    "Eqs. (8)-(9)": "process_epoch sequential DD plus constraint updates",
}

RTKLIB_FUNCTION_MAP = {
    "moving_base_prediction": "rtkpos.c:udpos PMODE_MOVEB dynamics=0 initx(VAR_POS)",
    "ambiguity_prediction_reset": "rtkpos.c:udbias phase-minus-code cycle mean and std[0]^2 variance",
    "lli_slip": "rtkpos.c:detslp_ll",
    "geometry_free_slip": "rtkpos.c:detslp_gf and prcopt_default.thresslip",
    "melbourne_wubbena_slip": "ppp.c:detslp_mw and THRES_MW_JUMP",
    "measurement_update": "rtkcmn.c:filter; clean-room Joseph-form equivalent",
    "baseline_constraint": "rtkpos.c:constbl; paper Eq. (7) clean-room sequential equivalent",
    "integer_resolution": "lambda.c:lambda reduction and search through pinned bridge",
}


class Yang2024Error(ValueError):
    """Malformed model or failed numerical operation with a stable code."""

    def __init__(self, message: str, *, code: str = "EXT03_NUMERICAL_FAILURE") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, order=True)
class SignalIdentity:
    constellation: str
    satellite: str
    frequency: str

    def __post_init__(self) -> None:
        constellation = self.constellation.upper()
        if constellation not in {"GPS", "BDS"}:
            raise Yang2024Error("EXT03 permits only GPS and BDS")
        if not self.satellite or not self.frequency:
            raise Yang2024Error("signal identity fields must be nonempty")
        object.__setattr__(self, "constellation", constellation)


@dataclass(frozen=True, order=True)
class AmbiguityIdentity:
    constellation: str
    satellite: str
    frequency: str
    pivot: str
    receiver_order: str = "GNSS2_MINUS_GNSS1"

    def __post_init__(self) -> None:
        constellation = self.constellation.upper()
        if constellation not in {"GPS", "BDS"}:
            raise Yang2024Error("EXT03 permits only GPS and BDS")
        if not self.satellite or not self.frequency or not self.pivot:
            raise Yang2024Error("ambiguity identity fields must be nonempty")
        if self.satellite == self.pivot:
            raise Yang2024Error("DD ambiguity satellite cannot equal its pivot")
        if self.receiver_order != "GNSS2_MINUS_GNSS1":
            raise Yang2024Error("receiver order violates the physical contract")
        object.__setattr__(self, "constellation", constellation)

    @property
    def signal(self) -> SignalIdentity:
        return SignalIdentity(self.constellation, self.satellite, self.frequency)

    @property
    def pivot_signal(self) -> SignalIdentity:
        return SignalIdentity(self.constellation, self.pivot, self.frequency)


def _finite_vector(value: ArrayLike, size: int | None = None, *, name: str) -> FloatArray:
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 1 or (size is not None and result.size != size):
        raise Yang2024Error(f"{name} has invalid dimensions")
    if np.any(~np.isfinite(result)):
        raise Yang2024Error(f"{name} must be finite")
    return np.array(result, copy=True)


def _positive_definite(value: ArrayLike, size: int, *, name: str) -> FloatArray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (size, size) or np.any(~np.isfinite(matrix)):
        raise Yang2024Error(f"{name} must be a finite {size}-square matrix")
    scale = max(1.0, float(np.linalg.norm(matrix, ord=np.inf)))
    if np.max(np.abs(matrix - matrix.T)) > 128.0 * np.finfo(float).eps * scale:
        raise Yang2024Error(f"{name} must be symmetric")
    matrix = 0.5 * (matrix + matrix.T)
    try:
        np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as exc:
        raise Yang2024Error(f"{name} must be positive definite") from exc
    return np.array(matrix, copy=True)


@dataclass(frozen=True)
class DDObservationBlock:
    """One constellation/frequency DD block ordered ``[code, phase]``.

    ``los_ned`` contains the pivot and all listed satellites.  Rows are
    line-of-sight unit vectors from receiver to satellite in NED.  The full
    covariance must retain shared-pivot correlations; code/phase cross terms
    are accepted rather than discarded.
    """

    constellation: str
    frequency: str
    pivot: str
    satellites: tuple[str, ...]
    wavelength_m: float
    los_ned: Mapping[str, ArrayLike]
    code_dd_m: ArrayLike
    phase_dd_m: ArrayLike
    covariance_code_phase_m2: ArrayLike
    receiver_order: str = "GNSS2_MINUS_GNSS1"

    def __post_init__(self) -> None:
        constellation = self.constellation.upper()
        if constellation not in {"GPS", "BDS"}:
            raise Yang2024Error("DD blocks must be GPS or BDS")
        if not self.frequency or not self.pivot or not self.satellites:
            raise Yang2024Error("DD block identity is incomplete")
        if len(set(self.satellites)) != len(self.satellites):
            raise Yang2024Error("DD satellite identities must be unique")
        if self.pivot in self.satellites:
            raise Yang2024Error("pivot must not occur in DD satellite rows")
        if self.receiver_order != "GNSS2_MINUS_GNSS1":
            raise Yang2024Error("receiver order violates the physical contract")
        if not math.isfinite(self.wavelength_m) or self.wavelength_m <= 0.0:
            raise Yang2024Error("wavelength must be positive and finite")
        count = len(self.satellites)
        _finite_vector(self.code_dd_m, count, name="code DD")
        _finite_vector(self.phase_dd_m, count, name="phase DD")
        _positive_definite(self.covariance_code_phase_m2, 2 * count, name="DD covariance")
        identities = (self.pivot,) + tuple(self.satellites)
        expected_prefix = "G" if constellation == "GPS" else "C"
        if any(not satellite.upper().startswith(expected_prefix) for satellite in identities):
            raise Yang2024Error(
                "satellite label does not belong to the declared constellation",
                code="CROSS_SYSTEM_DD_FORBIDDEN",
            )
        for satellite in identities:
            los = _finite_vector(self.los_ned[satellite], 3, name=f"LOS {satellite}")
            if not math.isclose(float(np.linalg.norm(los)), 1.0, rel_tol=0.0, abs_tol=1e-10):
                raise Yang2024Error("LOS vectors must be unit length")
        object.__setattr__(self, "constellation", constellation)
        object.__setattr__(self, "satellites", tuple(self.satellites))


@dataclass(frozen=True)
class DDObservationModel:
    observation_m: FloatArray
    design: FloatArray
    covariance_m2: FloatArray
    ambiguity_identities: tuple[AmbiguityIdentity, ...]
    phase_minus_code_initial_ambiguity_cycles: Mapping[AmbiguityIdentity, float]
    block_row_slices: tuple[tuple[str, str, slice], ...]


def build_dd_observation(blocks: Sequence[DDObservationBlock]) -> DDObservationModel:
    """Stack Eqs. (1)--(3) without ever forming cross-system DDs."""

    if not blocks:
        raise Yang2024Error("at least one DD block is required")
    keys = [(block.constellation, block.frequency) for block in blocks]
    if len(set(keys)) != len(keys):
        raise Yang2024Error("each constellation/frequency block must be unique")
    identities = tuple(
        AmbiguityIdentity(
            block.constellation, satellite, block.frequency, block.pivot,
            block.receiver_order,
        )
        for block in blocks for satellite in block.satellites
    )
    ambiguity_index = {identity: index for index, identity in enumerate(identities)}
    row_count = sum(2 * len(block.satellites) for block in blocks)
    design = np.zeros((row_count, 3 + len(identities)), dtype=np.float64)
    observation = np.empty(row_count, dtype=np.float64)
    covariance = np.zeros((row_count, row_count), dtype=np.float64)
    slices: list[tuple[str, str, slice]] = []
    initial_ambiguities: dict[AmbiguityIdentity, float] = {}
    cursor = 0
    for block in blocks:
        count = len(block.satellites)
        block_slice = slice(cursor, cursor + 2 * count)
        code = _finite_vector(block.code_dd_m, count, name="code DD")
        phase = _finite_vector(block.phase_dd_m, count, name="phase DD")
        observation[block_slice] = np.concatenate((code, phase))
        pivot_los = np.asarray(block.los_ned[block.pivot], dtype=float)
        baseline_rows = np.asarray(
            [-(np.asarray(block.los_ned[satellite], dtype=float) - pivot_los)
             for satellite in block.satellites],
            dtype=float,
        )
        design[cursor:cursor + count, :3] = baseline_rows
        design[cursor + count:cursor + 2 * count, :3] = baseline_rows
        for offset, satellite in enumerate(block.satellites):
            identity = AmbiguityIdentity(
                block.constellation, satellite, block.frequency, block.pivot,
                block.receiver_order,
            )
            design[cursor + count + offset, 3 + ambiguity_index[identity]] = block.wavelength_m
            # Pinned non-IFLC udbias() initializes phase bias as phase-code in
            # cycles.  In a DD block the common baseline term cancels exactly.
            initial_ambiguities[identity] = float((phase[offset] - code[offset]) / block.wavelength_m)
        covariance[block_slice, block_slice] = _positive_definite(
            block.covariance_code_phase_m2, 2 * count, name="DD covariance"
        )
        slices.append((block.constellation, block.frequency, block_slice))
        cursor += 2 * count
    return DDObservationModel(
        observation, design, _positive_definite(covariance, row_count, name="stacked covariance"),
        identities, initial_ambiguities, tuple(slices),
    )


@dataclass(frozen=True)
class StochasticParameter:
    parameter: str
    value: float | str
    unit: str
    source: str
    paper_equation_or_RTKLIB_symbol: str
    primary_or_sensitivity: str
    trace_tuned: bool = False


@dataclass(frozen=True)
class ModelRequirement:
    requirement: str
    implementation_contract: str
    source: str


PAPER_MODEL_REGISTRY = (
    ModelRequirement("receiver_initialization", "INDEPENDENT_RAW_PSEUDORANGE_SPP_PER_RECEIVER", "paper textual specification"),
    ModelRequirement("satellite_orbits", "BROADCAST_EPHEMERIS_TRANSMIT_TIME_STATES", "paper textual specification"),
    ModelRequirement("earth_rotation", "APPLY_SAGNAC_EARTH_ROTATION_CORRECTION", "paper textual specification"),
    ModelRequirement("troposphere", "SAASTAMOINEN_CORRECTION", "paper textual specification"),
    ModelRequirement("constraint_spp_input", "GNSS2_MINUS_GNSS1_RAW_SPP_BASELINE_ONLY", "prompt fallback hierarchy"),
    ModelRequirement("new_or_reset_ambiguity_mean", "DD_PHASE_MINUS_CODE_DIVIDED_BY_WAVELENGTH_CYCLES", f"RTKLIB {RTKLIB_COMMIT} rtkpos.c:udbias"),
    ModelRequirement("double_differences", "WITHIN_SYSTEM_ONLY_SEPARATE_GPS_BDS_PIVOTS", "paper Eqs. (1)-(3)"),
    ModelRequirement("receiver_order", "GNSS2_MINUS_GNSS1", "project physical contract"),
    ModelRequirement("stochastic_registry_boundary", "ADAPTER_MUST_APPEND_REQUIRED_MEASUREMENT_AND_SYSTEM_WEIGHT_PARAMETERS", "ADAPTER_STOCHASTIC_REGISTRY_REQUIRED_PARAMETERS"),
)


STOCHASTIC_PARAMETER_REGISTRY = (
    StochasticParameter("baseline_length", BASELINE_LENGTH_M, "m", "paper-disclosed", "Eq. (5)", "primary"),
    StochasticParameter("initial_baseline_variance", INITIAL_BASELINE_VARIANCE_M2, "m^2", "paper-disclosed", "initial covariance", "primary"),
    StochasticParameter("initial_ambiguity_variance", INITIAL_AMBIGUITY_VARIANCE_CYCLES2, "cycle^2", "paper-disclosed", "initial covariance", "primary"),
    StochasticParameter("ratio_threshold", RATIO_THRESHOLD, "1", "paper-disclosed", "MLAMBDA ratio", "primary"),
    StochasticParameter("baseline_length_sigma", PRIMARY_BASELINE_SIGMA_M, "m", "pre-registered engineering prior", "Eq. (7)", "primary"),
    *(StochasticParameter("baseline_length_sigma", value, "m", "pre-registered sensitivity envelope", "Eq. (7)", "sensitivity") for value in SENSITIVITY_BASELINE_SIGMAS_M),
    StochasticParameter("geometry_free_slip_threshold", GEOMETRY_FREE_SLIP_THRESHOLD_M, "m", f"RTKLIB {RTKLIB_COMMIT}", "prcopt_default.thresslip", "primary"),
    StochasticParameter("melbourne_wubbena_slip_threshold", MELBOURNE_WUBBENA_SLIP_THRESHOLD_M, "m", f"RTKLIB {RTKLIB_COMMIT}", "ppp.c:THRES_MW_JUMP", "primary"),
    StochasticParameter("prior_dd_slip_threshold", PRIOR_DD_AMBIGUITY_SLIP_THRESHOLD_CYCLES, "cycle", "pre-registered physical threshold", "paper textual chain", "primary"),
    StochasticParameter("moving_base_position_reset_variance", RTKLIB_MOVING_BASE_POSITION_VARIANCE_M2, "m^2", f"RTKLIB {RTKLIB_COMMIT}", "rtkpos.c:udpos PMODE_MOVEB initx(VAR_POS)", "primary"),
    StochasticParameter("baseline_process_noise_diagnostic", 0.0, "m/sqrt(s)", "diagnostic-only identity/random-walk option", "not primary RTKLIB moving-base model", "sensitivity"),
    StochasticParameter("ambiguity_process_noise", 1.0e-4, "cycle/sqrt(s)", f"RTKLIB {RTKLIB_COMMIT}", "rtkpos.c:udbias prcopt_default.prn[0] non-IFLC state", "primary"),
)


@dataclass(frozen=True)
class EXT03Config:
    constraint_mode: str = "CONSTRAINED"
    baseline_sigma_m: float = PRIMARY_BASELINE_SIGMA_M
    ratio_threshold: float = RATIO_THRESHOLD
    baseline_process_sigma_m_sqrt_s: float = 0.0
    ambiguity_process_sigma_cycles_sqrt_s: float = 1.0e-4
    baseline_length_m: float = BASELINE_LENGTH_M
    baseline_prediction_mode: str = "RTKLIB_MOVING_BASE_SPP_RESET"

    def __post_init__(self) -> None:
        if self.constraint_mode not in {"CONSTRAINED", "UNCONSTRAINED"}:
            raise Yang2024Error("constraint_mode must be CONSTRAINED or UNCONSTRAINED")
        if self.baseline_prediction_mode not in {
            "RTKLIB_MOVING_BASE_SPP_RESET", "DIAGNOSTIC_IDENTITY_RANDOM_WALK"
        }:
            raise Yang2024Error("invalid baseline prediction mode")
        values = (
            self.baseline_sigma_m, self.ratio_threshold,
            self.baseline_process_sigma_m_sqrt_s,
            self.ambiguity_process_sigma_cycles_sqrt_s, self.baseline_length_m,
        )
        if any(not math.isfinite(value) or value < 0.0 for value in values):
            raise Yang2024Error("configuration values must be finite and nonnegative")
        if self.baseline_sigma_m == 0.0 or self.ratio_threshold == 0.0 or self.baseline_length_m == 0.0:
            raise Yang2024Error("baseline sigma, ratio threshold, and length must be positive")


@dataclass(frozen=True)
class TrackingMemory:
    geometry_free_m: Mapping[tuple[str, str], float] = field(default_factory=dict)
    melbourne_wubbena_m: Mapping[tuple[str, str], float] = field(default_factory=dict)
    estimated_dd_ambiguity_cycles: Mapping[AmbiguityIdentity, float] = field(default_factory=dict)


@dataclass(frozen=True)
class EXT03State:
    epoch_time_s: float
    state: FloatArray
    covariance: FloatArray
    ambiguity_identities: tuple[AmbiguityIdentity, ...]
    previous_fixed_baseline_ned_m: FloatArray | None = None
    tracking_memory: TrackingMemory = field(default_factory=TrackingMemory)


def initialize_state(
    epoch_time_s: float,
    ambiguity_identities: Sequence[AmbiguityIdentity],
    baseline_ned_m: ArrayLike | None = None,
) -> EXT03State:
    identities = tuple(ambiguity_identities)
    if len(set(identities)) != len(identities):
        raise Yang2024Error("ambiguity identities must be unique")
    if not math.isfinite(epoch_time_s):
        raise Yang2024Error("epoch time must be finite")
    baseline = np.zeros(3) if baseline_ned_m is None else _finite_vector(
        baseline_ned_m, 3, name="initial baseline"
    )
    state = np.concatenate((baseline, np.zeros(len(identities))))
    covariance = np.diag(
        [INITIAL_BASELINE_VARIANCE_M2] * 3
        + [INITIAL_AMBIGUITY_VARIANCE_CYCLES2] * len(identities)
    )
    return EXT03State(float(epoch_time_s), state, covariance, identities)


@dataclass(frozen=True)
class StateManagementReason:
    constellation: str
    frequency: str
    old_pivot: str
    new_pivot: str
    reason: str


@dataclass(frozen=True)
class StateManagementDiagnostics:
    state_dimension: int
    baseline_state_indices: tuple[int, int, int]
    ambiguity_state_identities: tuple[AmbiguityIdentity, ...]
    ambiguity_state_count: int
    new_ambiguity_count: int
    removed_ambiguity_count: int
    reset_ambiguity_count: int
    pivot_change_count: int
    pivot_transform_count: int
    pivot_reinitialization_count: int
    reasons: tuple[StateManagementReason, ...]


def _pivot_row(
    target: AmbiguityIdentity,
    old_identities: tuple[AmbiguityIdentity, ...],
) -> FloatArray | None:
    row = np.zeros(len(old_identities), dtype=float)
    group = [
        (index, identity) for index, identity in enumerate(old_identities)
        if (identity.constellation, identity.frequency, identity.receiver_order)
        == (target.constellation, target.frequency, target.receiver_order)
    ]
    old_pivots = {identity.pivot for _, identity in group}
    if len(old_pivots) != 1:
        return None
    old_pivot = next(iter(old_pivots))
    if old_pivot == target.pivot:
        return None
    by_satellite = {identity.satellite: index for index, identity in group}
    if target.pivot not in by_satellite:
        return None
    if target.satellite == old_pivot:
        row[by_satellite[target.pivot]] = -1.0
        return row
    if target.satellite not in by_satellite:
        return None
    row[by_satellite[target.satellite]] = 1.0
    row[by_satellite[target.pivot]] = -1.0
    return row


def reconcile_ambiguity_state(
    previous: EXT03State,
    new_identities: Sequence[AmbiguityIdentity],
    reset_identities: Iterable[AmbiguityIdentity] = (),
    initial_ambiguity_cycles: Mapping[AmbiguityIdentity, float] | None = None,
) -> tuple[EXT03State, StateManagementDiagnostics]:
    """Deterministically add/remove/reset states and transform pivot changes.

    New or reset non-IFLC states use the supplied DD phase-minus-code mean in
    cycles, matching pinned ``rtkpos.c:udbias``.  Their covariance remains the
    paper-disclosed 900 cycle².  This initializer is state seeding only and is
    never copied into the prior-DD cycle-slip statistic.
    """

    target = tuple(new_identities)
    if len(set(target)) != len(target):
        raise Yang2024Error("target ambiguity identities must be unique")
    old = previous.ambiguity_identities
    reset = set(reset_identities)
    initial = {} if initial_ambiguity_cycles is None else dict(initial_ambiguity_cycles)
    for identity, value in initial.items():
        if not isinstance(identity, AmbiguityIdentity) or not math.isfinite(float(value)):
            raise Yang2024Error(
                "ambiguity initializer requires finite cycle values keyed by AmbiguityIdentity",
                code="INVALID_AMBIGUITY_INITIALIZER",
            )
    old_index = {identity: index for index, identity in enumerate(old)}
    def group_key(identity: AmbiguityIdentity) -> tuple[str, str, str]:
        return identity.constellation, identity.frequency, identity.receiver_order

    old_groups: dict[tuple[str, str, str], list[AmbiguityIdentity]] = {}
    target_groups: dict[tuple[str, str, str], list[AmbiguityIdentity]] = {}
    for identity in old:
        old_groups.setdefault(group_key(identity), []).append(identity)
    for identity in target:
        target_groups.setdefault(group_key(identity), []).append(identity)
    pivot_changes: dict[tuple[str, str, str], tuple[str, str, bool]] = {}
    management_reasons: list[StateManagementReason] = []
    for key in sorted(set(old_groups) & set(target_groups)):
        old_pivots = {item.pivot for item in old_groups[key]}
        new_pivots = {item.pivot for item in target_groups[key]}
        if len(old_pivots) != 1 or len(new_pivots) != 1:
            raise Yang2024Error("ambiguity group has inconsistent pivot metadata")
        old_pivot, new_pivot = next(iter(old_pivots)), next(iter(new_pivots))
        if old_pivot == new_pivot:
            continue
        transformable = new_pivot in {item.satellite for item in old_groups[key]}
        pivot_changes[key] = (old_pivot, new_pivot, transformable)
        reason = "PIVOT_CHANGE_TRANSFORMED" if transformable else "PIVOT_CHANGE_REINITIALIZED"
        management_reasons.append(
            StateManagementReason(key[0], key[1], old_pivot, new_pivot, reason)
        )
    transform = np.zeros((3 + len(target), 3 + len(old)), dtype=float)
    transform[:3, :3] = np.eye(3)
    mapped = np.zeros(len(target), dtype=bool)
    for new_index, identity in enumerate(target):
        if identity in reset:
            continue
        change = pivot_changes.get(group_key(identity))
        if change is not None and not change[2]:
            # Exact basis transformation is impossible because the new pivot
            # had no old DD state.  Reinitialize the complete group explicitly.
            continue
        if identity in old_index:
            transform[3 + new_index, 3 + old_index[identity]] = 1.0
            mapped[new_index] = True
            continue
        pivot = _pivot_row(identity, old)
        if pivot is not None:
            transform[3 + new_index, 3:] = pivot
            mapped[new_index] = True
    state = transform @ previous.state
    covariance = transform @ previous.covariance @ transform.T
    for index, was_mapped in enumerate(mapped):
        if not was_mapped:
            state[3 + index] = float(initial.get(target[index], 0.0))
            covariance[3 + index, 3 + index] = INITIAL_AMBIGUITY_VARIANCE_CYCLES2
    covariance = 0.5 * (covariance + covariance.T)
    # State-management categories are disjoint.  A retained affected arc is a
    # reset, not simultaneously a removal and addition.  Old coordinates used
    # by an exact pivot transformation are likewise retained state information;
    # pivot turnover is reported independently by pivot_change_count.
    old_inventory = {
        key: {item.pivot for item in items} | {item.satellite for item in items}
        for key, items in old_groups.items()
    }
    target_inventory = {
        key: {item.pivot for item in items} | {item.satellite for item in items}
        for key, items in target_groups.items()
    }
    new_count = sum(
        identity not in reset
        and identity.satellite not in old_inventory.get(group_key(identity), set())
        for identity in target
    )
    removed_count = sum(
        identity.satellite not in target_inventory.get(group_key(identity), set())
        for identity in old
    )
    reset_count = sum(identity in reset for identity in target)
    result = EXT03State(
        previous.epoch_time_s, state, covariance, target,
        previous.previous_fixed_baseline_ned_m, previous.tracking_memory,
    )
    diagnostics = StateManagementDiagnostics(
        len(state), (0, 1, 2), target, len(target), new_count,
        removed_count, reset_count, len(pivot_changes),
        sum(change[2] for change in pivot_changes.values()),
        sum(not change[2] for change in pivot_changes.values()),
        tuple(management_reasons),
    )
    return result, diagnostics


@dataclass(frozen=True)
class EpochTrackingInput:
    actual_carrier_lli_tracking_discontinuities: frozenset[SignalIdentity] = frozenset()
    receiver_locktime_resets: frozenset[SignalIdentity] = frozenset()
    half_cycle_state_changes: frozenset[SignalIdentity] = frozenset()
    receiver_clock_reset_events: frozenset[SignalIdentity] = frozenset()
    geometry_free_m: Mapping[tuple[str, str], float] = field(default_factory=dict)
    melbourne_wubbena_m: Mapping[tuple[str, str], float] = field(default_factory=dict)
    estimated_dd_ambiguity_cycles: Mapping[AmbiguityIdentity, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject ambiguous raw phase/code inputs at the interface boundary.

        ``estimated_dd_ambiguity_cycles`` must be the current model/KF-derived
        DD ambiguity estimate after geometric and modeled terms are removed.
        It is intentionally not a raw carrier-minus-code combination, whose
        code noise would make the pre-registered 0.25-cycle check meaningless.
        """

        for category, signals in (
            ("actual carrier LLI/tracking discontinuity",
             self.actual_carrier_lli_tracking_discontinuities),
            ("receiver locktime reset", self.receiver_locktime_resets),
            ("half-cycle state change", self.half_cycle_state_changes),
            ("receiver clock-reset event", self.receiver_clock_reset_events),
        ):
            for signal in signals:
                if not isinstance(signal, SignalIdentity):
                    raise Yang2024Error(
                        f"{category} requires SignalIdentity values",
                        code="INVALID_SIGNAL_EVENT_INPUT",
                    )
        for name, mapping in (
            ("geometry-free", self.geometry_free_m),
            ("Melbourne-Wubbena", self.melbourne_wubbena_m),
        ):
            for key, value in mapping.items():
                try:
                    finite_value = math.isfinite(float(value))
                except (TypeError, ValueError):
                    finite_value = False
                if not (
                    isinstance(key, tuple) and len(key) == 2
                    and key[0] in {"GPS", "BDS"}
                    and isinstance(key[1], str) and key[1]
                    and key[1].startswith("G" if key[0] == "GPS" else "C")
                    and finite_value
                ):
                    raise Yang2024Error(
                        f"{name} input requires canonical (constellation,satellite) and finite value",
                        code="INVALID_TRACKING_COMBINATION_INPUT",
                    )
        for identity, value in self.estimated_dd_ambiguity_cycles.items():
            if not isinstance(identity, AmbiguityIdentity):
                raise Yang2024Error(
                    "prior-DD consistency requires AmbiguityIdentity keys",
                    code="INVALID_ESTIMATED_DD_AMBIGUITY_INPUT",
                )
            try:
                finite_value = math.isfinite(float(value))
            except (TypeError, ValueError):
                finite_value = False
            if not finite_value:
                raise Yang2024Error(
                    "estimated DD ambiguity must be finite cycles",
                    code="INVALID_ESTIMATED_DD_AMBIGUITY_INPUT",
                )


@dataclass(frozen=True)
class CycleSlipDiagnostics:
    """Tracking-event evidence and the de-duplicated ambiguity reset union.

    The four receiver-event counters count input signal events, not ambiguity
    states: one pivot event can affect several DD ambiguities.  Conversely,
    ``affected_identities`` contains each ambiguity at most once even when
    several independent detectors identify it.
    """

    affected_identities: tuple[AmbiguityIdentity, ...]
    actual_carrier_lli_tracking_event_count: int
    receiver_locktime_reset_event_count: int
    half_cycle_state_change_event_count: int
    receiver_clock_reset_event_count: int
    geometry_free_count: int
    melbourne_wubbena_count: int
    prior_dd_count: int
    reasons: tuple[tuple[AmbiguityIdentity, tuple[str, ...]], ...]
    detector_unavailable_reasons: tuple[tuple[AmbiguityIdentity, str], ...]
    method_state_initialization: bool
    updated_memory: TrackingMemory


def map_prior_dd_ambiguities_to_target_basis(
    identities: Sequence[AmbiguityIdentity],
    previous_estimated_dd_ambiguity_cycles: Mapping[AmbiguityIdentity, float],
) -> tuple[dict[AmbiguityIdentity, float], tuple[tuple[AmbiguityIdentity, str], ...]]:
    """Map a prior DD ambiguity vector into the current exact pivot basis.

    The mapping is algebraic and constellation/frequency/receiver-order local;
    it never creates cross-system DDs.  The returned unavailable entries make
    an untransformable pivot change explicit so an adapter can reinitialize
    those states and preserve the detector-unavailable reason in diagnostics.
    """

    identities = tuple(identities)
    for identity, value in previous_estimated_dd_ambiguity_cycles.items():
        try:
            finite_value = math.isfinite(float(value))
        except (TypeError, ValueError):
            finite_value = False
        if not isinstance(identity, AmbiguityIdentity) or not finite_value:
            raise Yang2024Error(
                "prior DD basis mapping requires finite AmbiguityIdentity values",
                code="INVALID_ESTIMATED_DD_AMBIGUITY_INPUT",
            )
    old_identities = tuple(previous_estimated_dd_ambiguity_cycles)
    prior_values = np.asarray(
        [previous_estimated_dd_ambiguity_cycles[item] for item in old_identities], dtype=float
    )
    transformed: dict[AmbiguityIdentity, float] = {}
    unavailable: list[tuple[AmbiguityIdentity, str]] = []
    for identity in identities:
        if identity in previous_estimated_dd_ambiguity_cycles:
            transformed[identity] = float(previous_estimated_dd_ambiguity_cycles[identity])
            continue
        old_group = tuple(
            item for item in old_identities
            if (item.constellation, item.frequency, item.receiver_order)
            == (identity.constellation, identity.frequency, identity.receiver_order)
        )
        if not old_group:
            continue
        old_pivots = {item.pivot for item in old_group}
        if len(old_pivots) != 1 or next(iter(old_pivots)) == identity.pivot:
            continue
        row = _pivot_row(identity, old_identities)
        if row is None:
            unavailable.append((identity, "PRIOR_DD_UNAVAILABLE_PIVOT_CHANGE_REINITIALIZED"))
        else:
            transformed[identity] = float(row @ prior_values)
    return transformed, tuple(unavailable)


def detect_cycle_slips(
    identities: Sequence[AmbiguityIdentity],
    tracking: EpochTrackingInput,
    previous: TrackingMemory,
    *,
    method_state_initialization: bool = False,
) -> CycleSlipDiagnostics:
    """Paper-stated LLI/GF/MW/prior-DD chain with affected-only resets.

    The prior-DD channel compares consecutive *estimated ambiguity states* in
    cycles.  It must never be populated with a raw phase-minus-code observable.
    """

    identities = tuple(identities)
    if method_state_initialization:
        return CycleSlipDiagnostics(
            (), 0, 0, 0, 0, 0, 0, 0, (), (), True,
            TrackingMemory(
                dict(tracking.geometry_free_m), dict(tracking.melbourne_wubbena_m),
                dict(tracking.estimated_dd_ambiguity_cycles),
            ),
        )
    reason_map: dict[AmbiguityIdentity, set[str]] = {identity: set() for identity in identities}
    prior_dd_in_basis, prior_unavailable = map_prior_dd_ambiguities_to_target_basis(
        identities, previous.estimated_dd_ambiguity_cycles
    )
    gf_slips: set[tuple[str, str]] = set()
    mw_slips: set[tuple[str, str]] = set()
    for key, current in tracking.geometry_free_m.items():
        prior = previous.geometry_free_m.get(key)
        if prior is not None and abs(float(current) - float(prior)) > GEOMETRY_FREE_SLIP_THRESHOLD_M:
            gf_slips.add((key[0].upper(), key[1]))
    for key, current in tracking.melbourne_wubbena_m.items():
        prior = previous.melbourne_wubbena_m.get(key)
        if prior is not None and abs(float(current) - float(prior)) > MELBOURNE_WUBBENA_SLIP_THRESHOLD_M:
            mw_slips.add((key[0].upper(), key[1]))
    for identity in identities:
        signals = {identity.signal, identity.pivot_signal}
        if signals & set(tracking.actual_carrier_lli_tracking_discontinuities):
            reason_map[identity].add(
                "ACTUAL_CARRIER_LLI_OR_TRACKING_VALIDITY_DISCONTINUITY"
            )
        if signals & set(tracking.receiver_locktime_resets):
            reason_map[identity].add("RECEIVER_LOCKTIME_RESET")
        if signals & set(tracking.half_cycle_state_changes):
            reason_map[identity].add("HALF_CYCLE_VALIDITY_OR_SUBHALFCYC_CHANGE")
        if signals & set(tracking.receiver_clock_reset_events):
            reason_map[identity].add("RECEIVER_CLOCK_RESET_EVENT")
        satellite_keys = {
            (identity.constellation, identity.satellite),
            (identity.constellation, identity.pivot),
        }
        if satellite_keys & gf_slips:
            reason_map[identity].add("GEOMETRY_FREE_JUMP")
        if satellite_keys & mw_slips:
            reason_map[identity].add("MELBOURNE_WUBBENA_JUMP")
        current_dd = tracking.estimated_dd_ambiguity_cycles.get(identity)
        prior_dd = prior_dd_in_basis.get(identity)
        if current_dd is not None and prior_dd is not None and (
            abs(float(current_dd) - float(prior_dd)) > PRIOR_DD_AMBIGUITY_SLIP_THRESHOLD_CYCLES
        ):
            reason_map[identity].add("PRIOR_DD_AMBIGUITY_INCONSISTENCY")
    affected = tuple(identity for identity in identities if reason_map[identity])
    updated = TrackingMemory(
        dict(tracking.geometry_free_m), dict(tracking.melbourne_wubbena_m),
        dict(tracking.estimated_dd_ambiguity_cycles),
    )
    reasons = tuple((identity, tuple(sorted(reason_map[identity]))) for identity in affected)
    return CycleSlipDiagnostics(
        affected,
        len(tracking.actual_carrier_lli_tracking_discontinuities),
        len(tracking.receiver_locktime_resets),
        len(tracking.half_cycle_state_changes),
        len(tracking.receiver_clock_reset_events),
        sum("GEOMETRY_FREE_JUMP" in reason_map[item] for item in affected),
        sum("MELBOURNE_WUBBENA_JUMP" in reason_map[item] for item in affected),
        sum("PRIOR_DD_AMBIGUITY_INCONSISTENCY" in reason_map[item] for item in affected),
        reasons, prior_unavailable, False, updated,
    )


@dataclass(frozen=True)
class ConstraintLinearization:
    applied: bool
    source: str
    b0_ned_m: FloatArray | None
    s0_m: float | None
    jacobian_baseline: FloatArray | None


def baseline_constraint_linearization(
    previous_fixed_baseline_ned_m: ArrayLike | None,
    spp_baseline_ned_m: ArrayLike | None,
    current_float_baseline_ned_m: ArrayLike | None,
) -> ConstraintLinearization:
    """Select the paper's b0 with the required pre-first-fix hierarchy."""

    choices = (
        ("PREVIOUS_SUCCESSFULLY_RATIO_FIXED_BASELINE", previous_fixed_baseline_ned_m),
        ("RAW_PSEUDORANGE_SPP_BASELINE_DIFFERENCE", spp_baseline_ned_m),
        ("CURRENT_FINITE_FLOAT_BASELINE", current_float_baseline_ned_m),
    )
    for source, candidate in choices:
        if candidate is None:
            continue
        value = np.asarray(candidate, dtype=float)
        if value.shape != (3,) or np.any(~np.isfinite(value)):
            continue
        norm = float(np.linalg.norm(value))
        if norm > 0.0:
            return ConstraintLinearization(True, source, np.array(value, copy=True), norm, value / norm)
    return ConstraintLinearization(False, "NO_VALID_CONSTRAINT_LINEARIZATION_POINT", None, None, None)


@dataclass(frozen=True)
class ConstraintDiagnostics:
    """Eq. (7) update audit with coordinate domains kept separate.

    ``constraint_update_norm`` is only ``||delta b_NED||`` in metres.  Any
    ambiguity movement induced by baseline/ambiguity cross-covariance is
    reported separately in cycles.
    """
    constraint_applied: bool
    constraint_linearization_source: str
    b0_ned_m: FloatArray | None
    s0_m: float | None
    constraint_innovation_m: float | None
    constraint_sigma_m: float
    constraint_nis: float | None
    constraint_update_norm: float | None
    constraint_ambiguity_update_norm_cycles: float | None
    jacobian: FloatArray | None


def _kalman_update(
    state: FloatArray, covariance: FloatArray, observation: FloatArray,
    design: FloatArray, measurement_covariance: FloatArray,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
    innovation = observation - design @ state
    innovation_covariance = design @ covariance @ design.T + measurement_covariance
    try:
        gain = np.linalg.solve(innovation_covariance, design @ covariance).T
    except np.linalg.LinAlgError as exc:
        raise Yang2024Error("innovation covariance is singular") from exc
    updated = state + gain @ innovation
    identity = np.eye(state.size)
    residual_transform = identity - gain @ design
    # Joseph form retains symmetry and PSD with a dense correlated R.
    updated_covariance = (
        residual_transform @ covariance @ residual_transform.T
        + gain @ measurement_covariance @ gain.T
    )
    updated_covariance = 0.5 * (updated_covariance + updated_covariance.T)
    return updated, updated_covariance, innovation, innovation_covariance


def constraint_update(
    state: ArrayLike,
    covariance: ArrayLike,
    linearization: ConstraintLinearization,
    baseline_length_m: float = BASELINE_LENGTH_M,
    sigma_m: float = PRIMARY_BASELINE_SIGMA_M,
) -> tuple[FloatArray, FloatArray, ConstraintDiagnostics]:
    x = _finite_vector(state, name="KF state")
    p = np.asarray(covariance, dtype=float)
    if p.shape != (x.size, x.size) or np.any(~np.isfinite(p)):
        raise Yang2024Error("KF covariance dimensions are invalid")
    if not linearization.applied:
        diagnostics = ConstraintDiagnostics(
            False, linearization.source, None, None, None, sigma_m,
            None, None, None, None,
        )
        return x, np.array(p, copy=True), diagnostics
    h = np.zeros((1, x.size), dtype=float)
    h[0, :3] = linearization.jacobian_baseline
    before = np.array(x, copy=True)
    updated, updated_covariance, innovation, innovation_covariance = _kalman_update(
        x, p, np.asarray([baseline_length_m]), h, np.asarray([[sigma_m**2]])
    )
    nis = float(innovation[0] ** 2 / innovation_covariance[0, 0])
    diagnostics = ConstraintDiagnostics(
        True, linearization.source, linearization.b0_ned_m, linearization.s0_m,
        float(innovation[0]), sigma_m, nis,
        float(np.linalg.norm(updated[:3] - before[:3])),
        float(np.linalg.norm(updated[3:] - before[3:])), h[0].copy(),
    )
    return updated, updated_covariance, diagnostics


@dataclass(frozen=True)
class MLAMBDAResult:
    best_integer: NDArray[np.int64] | None
    second_integer: NDArray[np.int64] | None
    best_objective: float | None
    second_objective: float | None
    ratio: float | None
    ratio_is_infinite: bool
    zero_best_objective: bool
    candidate_returned: bool
    failure_code: str | None


def mlambda_resolve(
    float_ambiguity: ArrayLike,
    covariance_aa: ArrayLike,
    lambda_bridge_path: str | Path,
) -> MLAMBDAResult:
    floating = _finite_vector(float_ambiguity, name="float ambiguity")
    if floating.size == 0:
        return MLAMBDAResult(
            None, None, None, None, None, False, False, False, "NO_AMBIGUITIES"
        )
    covariance = _positive_definite(covariance_aa, floating.size, name="ambiguity covariance")
    try:
        candidates = RTKLIBLambdaBridge(lambda_bridge_path).candidates(floating, covariance, 2)
    except LambdaBridgeError as exc:
        code = "LAMBDA_BRIDGE_UNAVAILABLE" if "does not exist" in str(exc) else "LAMBDA_SEARCH_FAILED"
        raise Yang2024Error(str(exc), code=code) from exc
    if len(candidates) != 2:
        raise Yang2024Error("MLAMBDA did not return two candidates", code="LAMBDA_SEARCH_FAILED")
    best, second = candidates
    if best.ambiguity_objective < 0.0 or second.ambiguity_objective < best.ambiguity_objective:
        raise Yang2024Error("MLAMBDA objectives are invalid", code="LAMBDA_SEARCH_FAILED")
    if best.ambiguity_objective == 0.0:
        ratio = None
        ratio_is_infinite = second.ambiguity_objective > 0.0
    else:
        ratio = second.ambiguity_objective / best.ambiguity_objective
        ratio_is_infinite = False
    return MLAMBDAResult(
        np.asarray(best.ambiguity, dtype=np.int64),
        np.asarray(second.ambiguity, dtype=np.int64),
        float(best.ambiguity_objective), float(second.ambiguity_objective),
        None if ratio is None else float(ratio), ratio_is_infinite,
        best.ambiguity_objective == 0.0, True, None,
    )


@dataclass(frozen=True)
class AttitudeSolution:
    baseline_length_m: float
    baseline_heading_deg: float
    pitch_deg: float
    body_yaw_deg: float


def ned_attitude(baseline_ned_m: ArrayLike) -> AttitudeSolution:
    baseline = _finite_vector(baseline_ned_m, 3, name="NED baseline")
    north, east, down = map(float, baseline)
    horizontal = math.hypot(north, east)
    if horizontal == 0.0 and down == 0.0:
        raise Yang2024Error("zero baseline has undefined attitude")
    heading = math.degrees(math.atan2(east, north)) % 360.0
    pitch = -math.degrees(math.atan2(down, horizontal))
    return AttitudeSolution(float(np.linalg.norm(baseline)), heading, pitch, (heading + 90.0) % 360.0)


@dataclass(frozen=True)
class KFDiagnostics:
    dt_s: float
    observation_count: int
    innovation_norm: float
    innovation_nis: float
    covariance_trace: float
    covariance_min_eigenvalue: float


@dataclass(frozen=True)
class EpochResult:
    state: EXT03State
    float_baseline_ned_m: FloatArray
    fixed_baseline_ned_m: FloatArray | None
    float_attitude: AttitudeSolution
    fixed_attitude: AttitudeSolution | None
    solution_state: str
    paper_ratio_fixed: bool
    ambiguity_correctness_known: bool
    state_diagnostics: StateManagementDiagnostics
    kf_diagnostics: KFDiagnostics
    constraint_diagnostics: ConstraintDiagnostics
    cycle_slip_diagnostics: CycleSlipDiagnostics
    mlambda_diagnostics: MLAMBDAResult


def _conditional_fixed_baseline(
    state: FloatArray, covariance: FloatArray, integer: NDArray[np.int64]
) -> FloatArray:
    ambiguity = state[3:]
    qba = covariance[:3, 3:]
    qaa = covariance[3:, 3:]
    try:
        correction = qba @ np.linalg.solve(qaa, ambiguity - integer)
    except np.linalg.LinAlgError as exc:
        raise Yang2024Error("conditional fixed-baseline covariance is singular") from exc
    return np.asarray(state[:3] - correction, dtype=float)


def process_epoch(
    previous: EXT03State | None,
    epoch_time_s: float,
    dd_model: DDObservationModel,
    config: EXT03Config,
    tracking: EpochTrackingInput | None = None,
    spp_baseline_ned_m: ArrayLike | None = None,
    lambda_bridge_path: str | Path | None = None,
    initial_ambiguity_cycles: Mapping[AmbiguityIdentity, float] | None = None,
) -> EpochResult:
    """Process exactly one chronological epoch of one recursive variant."""

    if not math.isfinite(epoch_time_s):
        raise Yang2024Error("epoch time must be finite")
    tracking = EpochTrackingInput() if tracking is None else tracking
    ambiguity_initializer = (
        dd_model.phase_minus_code_initial_ambiguity_cycles
        if initial_ambiguity_cycles is None else initial_ambiguity_cycles
    )
    if previous is None:
        state = initialize_state(epoch_time_s, (), spp_baseline_ned_m)
        slip = detect_cycle_slips(
            dd_model.ambiguity_identities, tracking, TrackingMemory(),
            method_state_initialization=True,
        )
        state, state_diag = reconcile_ambiguity_state(
            state, dd_model.ambiguity_identities, slip.affected_identities,
            ambiguity_initializer,
        )
        dt = 0.0
    else:
        dt = float(epoch_time_s - previous.epoch_time_s)
        if dt <= 0.0:
            raise Yang2024Error("epochs must be processed in strictly chronological order", code="NON_CHRONOLOGICAL_EPOCH")
        slip = detect_cycle_slips(dd_model.ambiguity_identities, tracking, previous.tracking_memory)
        state, state_diag = reconcile_ambiguity_state(
            previous, dd_model.ambiguity_identities, slip.affected_identities,
            ambiguity_initializer,
        )
    x = np.array(state.state, copy=True)
    p = np.array(state.covariance, copy=True)
    if config.baseline_prediction_mode == "RTKLIB_MOVING_BASE_SPP_RESET":
        if spp_baseline_ned_m is None:
            raise Yang2024Error(
                "RTKLIB moving-base prediction requires raw GNSS2-SPP minus GNSS1-SPP baseline",
                code="RAW_SPP_BASELINE_REQUIRED",
            )
        spp = _finite_vector(spp_baseline_ned_m, 3, name="raw SPP baseline")
        # Pinned rtkpos.c udpos() calls initx(VAR_POS) for PMODE_MOVEB with
        # dynamics disabled: replace coordinates and clear all cross terms.
        x[:3] = spp
        p[:3, :] = 0.0
        p[:, :3] = 0.0
        p[:3, :3] = np.eye(3) * RTKLIB_MOVING_BASE_POSITION_VARIANCE_M2
    else:
        p[:3, :3] += np.eye(3) * config.baseline_process_sigma_m_sqrt_s**2 * dt
    for index in range(len(state.ambiguity_identities)):
        # Non-IFLC rtkpos ambiguity states are cycles: ddres converts them to
        # metres with CLIGHT/freq.  Therefore prn[0]=1e-4 is already
        # cycle/sqrt(s), and no wavelength conversion belongs in Q.
        p[3 + index, 3 + index] += (
            config.ambiguity_process_sigma_cycles_sqrt_s ** 2 * dt
        )
    x, p, innovation, innovation_covariance = _kalman_update(
        x, p, dd_model.observation_m, dd_model.design, dd_model.covariance_m2
    )
    nis = float(innovation @ np.linalg.solve(innovation_covariance, innovation))
    if config.constraint_mode == "CONSTRAINED":
        linearization = baseline_constraint_linearization(
            state.previous_fixed_baseline_ned_m, spp_baseline_ned_m, x[:3]
        )
        x, p, constraint_diag = constraint_update(
            x, p, linearization, config.baseline_length_m, config.baseline_sigma_m
        )
    else:
        constraint_diag = ConstraintDiagnostics(
            False, "UNCONSTRAINED", None, None, None,
            config.baseline_sigma_m, None, None, None, None,
        )
    mlambda = MLAMBDAResult(
        None, None, None, None, None, False, False,
        False, "LAMBDA_BRIDGE_UNAVAILABLE",
    )
    if lambda_bridge_path is not None:
        mlambda = mlambda_resolve(x[3:], p[3:, 3:], lambda_bridge_path)
    fixed_baseline: FloatArray | None = None
    ratio_fixed = bool(
        mlambda.candidate_returned
        and (
            mlambda.ratio_is_infinite
            or (mlambda.ratio is not None and mlambda.ratio >= config.ratio_threshold)
        )
    )
    if ratio_fixed and mlambda.best_integer is not None:
        candidate = _conditional_fixed_baseline(x, p, mlambda.best_integer)
        if np.all(np.isfinite(candidate)):
            fixed_baseline = candidate
        else:
            ratio_fixed = False
    float_attitude = ned_attitude(x[:3])
    fixed_attitude = ned_attitude(fixed_baseline) if fixed_baseline is not None else None
    next_state = EXT03State(
        float(epoch_time_s), x, p, state.ambiguity_identities,
        fixed_baseline if ratio_fixed else state.previous_fixed_baseline_ned_m,
        slip.updated_memory,
    )
    kf_diag = KFDiagnostics(
        dt, dd_model.observation_m.size, float(np.linalg.norm(innovation)), nis,
        float(np.trace(p)), float(np.min(np.linalg.eigvalsh(p))),
    )
    return EpochResult(
        next_state, np.array(x[:3], copy=True), fixed_baseline,
        float_attitude, fixed_attitude,
        "paper_ratio_fixed" if ratio_fixed else "float",
        ratio_fixed, False, state_diag, kf_diag, constraint_diag, slip, mlambda,
    )
