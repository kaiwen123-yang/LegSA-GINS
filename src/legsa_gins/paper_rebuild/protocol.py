"""CLEAN1 protocol loading, kick-aligned/V1 window freeze, and init gates."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidence import EvidenceContractError, LOCAL_PATH_RE, write_csv_atomic
from .formal_generation import (
    FormalGenerationError,
    validate_raw_doppler_reproducible_build,
)
from .manifest import sha256_file, sha256_text
from .methods import FORMAL_METHOD_ORDER
from .paths import load_yaml_mapping


STAGE_ID = "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
PROTOCOL_ID = "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"
DATA_MODE = "real_by2_raw"
V1_STAGE_ID = "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION"
V1_PROTOCOL_ID = "CLEAN1_BY2_CLEAN_NORMAL_V1"
V1_SCHEMA_VERSION = "paper_rebuild.clean1_by2_protocol.v1"
V2_SCHEMA_VERSION = "paper_rebuild.clean1_by2_protocol.v2_kick_aligned"
V1_WINDOW_POLICY = "full_common_required_stream_interval"
V2_WINDOW_POLICY = "event_normalized_kick_core_gnss_interval"
REQUIRED_WINDOW_STREAMS = (
    "propagation_imu",
    "gnss_position",
    "receiver_velocity",
    "dual_yaw",
    "raw_doppler",
    "go2_roll_pitch_prior",
    "go2_horizontal_velocity_prior",
)
CORE_START_STREAMS = ("propagation_imu", "gnss_position", "dual_yaw")
OPTIONAL_START_STREAMS = (
    "receiver_velocity",
    "raw_doppler",
    "go2_roll_pitch_prior",
    "go2_horizontal_velocity_prior",
)

ERROR_STATE_ORDER = (
    "position_n", "position_e", "position_d",
    "velocity_n", "velocity_e", "velocity_d",
    "attitude_roll", "attitude_pitch", "attitude_yaw",
    "gyro_bias_x", "gyro_bias_y", "gyro_bias_z",
    "accel_bias_x", "accel_bias_y", "accel_bias_z",
    "gyro_scale_x", "gyro_scale_y", "gyro_scale_z",
    "accel_scale_x", "accel_scale_y", "accel_scale_z",
)


class ProtocolContractError(ValueError):
    """A formal protocol/window/initialization invariant failed."""


@dataclass(frozen=True)
class ProtocolConfig:
    path: Path
    payload: dict[str, Any]
    sha256: str


@dataclass(frozen=True)
class StreamCoverage:
    stream_role: str
    source_alias: str
    relative_path: str
    source_sha256: str
    first_valid_timestamp: float
    last_valid_timestamp: float
    valid_epoch_count: int
    internal_dropout_preserved: bool = True


@dataclass(frozen=True)
class FrozenWindow:
    t_start: float
    t_end: float
    duration_seconds: float
    source_time_origin_seconds: float
    streams: tuple[StreamCoverage, ...]
    common_initialization: dict[str, Any]
    policy: str = V1_WINDOW_POLICY
    t_start_formula: str = "max(all_required_stream_first_valid_timestamps)"
    t_end_formula: str = "min(all_required_stream_last_valid_timestamps)"
    mapped_kick_provider_time: float | None = None
    first_valid_gnss_after_kick: float | None = None
    optional_streams_delay_start: bool = True


def load_clean1_protocol(path: str | Path) -> ProtocolConfig:
    source = Path(path).resolve(strict=True)
    payload = load_yaml_mapping(source)
    schema_version = payload.get("schema_version")
    if schema_version == V2_SCHEMA_VERSION:
        stage_id = STAGE_ID
        protocol_id = PROTOCOL_ID
    elif schema_version == V1_SCHEMA_VERSION:
        # Compatibility is intentionally read-only: V1 contracts remain
        # loadable for preserved checkpoints, while the tracked protocol is V2.
        stage_id = V1_STAGE_ID
        protocol_id = V1_PROTOCOL_ID
    else:
        raise ProtocolContractError("Protocol schema version is not CLEAN1 V1 or V2")
    expected = {
        "schema_version": schema_version,
        "stage_id": stage_id,
        "case_id": CASE_ID,
        "protocol_id": protocol_id,
        "data_mode": DATA_MODE,
        "formal_method_count": 4,
        "paper_figure_count": 0,
        "diagnostic_plot_count": 0,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ProtocolContractError(f"Protocol field mismatch: {field}")
    if tuple(payload.get("method_order") or ()) != FORMAL_METHOD_ORDER:
        raise ProtocolContractError("Protocol method order mismatch")
    window = payload.get("window")
    if not isinstance(window, Mapping):
        raise ProtocolContractError("Protocol window mapping is missing")
    if tuple(window.get("required_streams") or ()) != REQUIRED_WINDOW_STREAMS:
        raise ProtocolContractError("Protocol required stream order mismatch")
    if schema_version == V2_SCHEMA_VERSION:
        if window.get("policy") != V2_WINDOW_POLICY:
            raise ProtocolContractError("Protocol is not the frozen kick-aligned window policy")
        if tuple(window.get("core_start_streams") or ()) != CORE_START_STREAMS:
            raise ProtocolContractError("Protocol kick-aligned core stream order mismatch")
        if tuple(window.get("optional_start_streams") or ()) != OPTIONAL_START_STREAMS:
            raise ProtocolContractError("Protocol optional stream order mismatch")
        if window.get("optional_streams_delay_start") is not False:
            raise ProtocolContractError("Optional streams must not delay CLEAN1R1C start")
        alignment = payload.get("time_alignment")
        expected_alignment = {
            "alignment_mode": "event_normalized_kick",
            "fixed_event_alignment_offset_seconds": 0.0,
            "initial_event_segment_end": "first_mode_or_gait_change_exclusive",
            "normalization_baseline_max_samples": 1000,
            "normalization_center": "median",
            "normalization_scale": "max_1p4826_mad_1e-12",
            "kick_score": "max_0_z_acc_jerk_plus_max_0_z_gyro_jerk",
            "minimum_kick_score": 6.0,
            "maintained_candidate_required_status": "detected",
            "trace_used_for_alignment": False,
            "offset_search_performed": False,
            "method_specific_shift": False,
        }
        if not isinstance(alignment, Mapping) or dict(alignment) != expected_alignment:
            raise ProtocolContractError("Tracked kick-alignment contract differs from CLEAN1R1C freeze")
    elif window.get("policy") != V1_WINDOW_POLICY:
        raise ProtocolContractError("Protocol is not a V1 full common-window policy")
    if window.get("smoke_truncation_seconds") is not None:
        raise ProtocolContractError("Formal protocol must not contain smoke truncation")
    if window.get("method_specific_window") is not False:
        raise ProtocolContractError("Method-specific windows are forbidden")
    provider_generation = payload.get("provider_generation")
    expected_provider_generation = {
        "max_status_rows": None,
        "max_raw_rows": None,
        "max_imu_messages": None,
        "yaw_source_mode": "status",
        "yaw_sign": 1.0,
        "yaw_install_offset_deg": 0.0,
        "yaw_std_mode": "fixed_1p5",
        "status_fixed_yaw_std_deg": 1.5,
        "receiver_velocity_match_tolerance_seconds": 0.1,
        "dual_yaw_match_tolerance_seconds": 0.6,
        "receiver_velocity_std_mps": 0.05,
        "imu_install_roll_deg": -1.0,
        "imu_install_pitch_deg": 0.0,
        "imu_install_yaw_deg": 0.0,
        "imu_gnss_time_offset_seconds": 0.0,
        "go2_velocity_frame_transform": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
        "go2_roll_pitch_std_deg": 1.6,
        "go2_horizontal_velocity_std_mps": 1.5,
        "raw_doppler_min_sat": 5,
        "raw_doppler_std_floor_mps": 0.2,
        "raw_doppler_covariance_policy": "conservative_isotropic_max_ecef_std_floor_0p2_mps",
        "outage_enabled": False,
        "outlier_mode": "none",
        "yaw_noise_std_deg": 0.0,
    }
    expected_provider_keys = set(expected_provider_generation)
    if schema_version == V2_SCHEMA_VERSION:
        expected_provider_keys.add("raw_doppler_reproducible_build")
    if (
        not isinstance(provider_generation, Mapping)
        or set(provider_generation) != expected_provider_keys
        or {
            key: provider_generation[key] for key in expected_provider_generation
        }
        != expected_provider_generation
    ):
        raise ProtocolContractError("Tracked provider-generation parameters differ from CLEAN1 freeze")
    if schema_version == V2_SCHEMA_VERSION:
        try:
            validate_raw_doppler_reproducible_build(
                provider_generation["raw_doppler_reproducible_build"]
            )
        except FormalGenerationError as exc:
            raise ProtocolContractError(
                "Tracked Raw Doppler reproducible-build contract differs from CLEAN1 freeze"
            ) from exc
    solver_common = payload.get("solver_common")
    if not isinstance(solver_common, Mapping) or provider_generation["raw_doppler_min_sat"] != solver_common.get("raw_doppler_min_sat"):
        raise ProtocolContractError("Provider and solver Raw Doppler minimum-satellite contracts differ")
    if schema_version == V2_SCHEMA_VERSION:
        lever = solver_common.get("antenna_lever_m")
        if not isinstance(lever, list) or [float(value) for value in lever] != [0.03, 0.03, -0.30]:
            raise ProtocolContractError("CLEAN1R1C measurement antenna lever differs from the user freeze")
    forbidden = payload.get("forbidden")
    if not isinstance(forbidden, Mapping):
        raise ProtocolContractError("Protocol forbidden mapping is missing")
    for field, value in forbidden.items():
        expected_value: Any = 0 if field == "old_runtime_input_count" else False
        if value != expected_value:
            raise ProtocolContractError(f"Protocol forbidden field is enabled: {field}")
    return ProtocolConfig(source, payload, sha256_file(source))


def _safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or ".." in Path(normalized).parts or LOCAL_PATH_RE.search(normalized):
        raise ProtocolContractError("Coverage artifacts must use alias plus safe relative paths")
    return normalized


def coverage_from_timestamps(
    stream_role: str,
    timestamps: Sequence[float],
    *,
    source_alias: str,
    relative_path: str,
    source_sha256: str,
) -> StreamCoverage:
    if stream_role not in REQUIRED_WINDOW_STREAMS:
        raise ProtocolContractError(f"Unexpected formal window stream: {stream_role}")
    finite = [float(value) for value in timestamps if math.isfinite(float(value))]
    if len(finite) < 2:
        raise ProtocolContractError(f"Required stream has fewer than two valid epochs: {stream_role}")
    if any(later <= earlier for earlier, later in zip(finite, finite[1:])):
        raise ProtocolContractError(f"Required stream timestamps are not strictly increasing: {stream_role}")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise ProtocolContractError(f"Required stream hash is invalid: {stream_role}")
    return StreamCoverage(
        stream_role=stream_role,
        source_alias=source_alias,
        relative_path=_safe_relative_path(relative_path),
        source_sha256=source_sha256,
        first_valid_timestamp=finite[0],
        last_valid_timestamp=finite[-1],
        valid_epoch_count=len(finite),
    )


def csv_stream_coverage(
    path: str | Path,
    stream_role: str,
    *,
    timestamp_column: str,
    source_alias: str,
    relative_path: str,
    source_sha256: str | None = None,
) -> StreamCoverage:
    """Read one explicitly named stream; this function performs no discovery."""

    source = Path(path).resolve(strict=True)
    timestamps: list[float] = []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or timestamp_column not in reader.fieldnames:
            raise ProtocolContractError(f"Missing timestamp column for {stream_role}")
        for row in reader:
            try:
                value = float(row.get(timestamp_column) or "nan")
            except ValueError:
                continue
            if math.isfinite(value):
                timestamps.append(value)
    return coverage_from_timestamps(
        stream_role,
        timestamps,
        source_alias=source_alias,
        relative_path=relative_path,
        source_sha256=source_sha256 or sha256_file(source),
    )


def whitespace_stream_coverage(
    path: str | Path,
    stream_role: str,
    *,
    timestamp_index: int,
    source_alias: str,
    relative_path: str,
    source_sha256: str | None = None,
) -> StreamCoverage:
    source = Path(path).resolve(strict=True)
    timestamps: list[float] = []
    with source.open("r", encoding="utf-8", errors="strict") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            fields = stripped.split()
            if timestamp_index >= len(fields):
                raise ProtocolContractError(f"Missing timestamp field at {source.name}:{number}")
            try:
                value = float(fields[timestamp_index])
            except ValueError as exc:
                raise ProtocolContractError(f"Invalid timestamp at {source.name}:{number}") from exc
            if math.isfinite(value):
                timestamps.append(value)
    return coverage_from_timestamps(
        stream_role,
        timestamps,
        source_alias=source_alias,
        relative_path=relative_path,
        source_sha256=source_sha256 or sha256_file(source),
    )


def build_common_covariance_contract(solver_common: Mapping[str, Any]) -> dict[str, Any]:
    """Mechanically mirror the C++ 21-state initialization std/unit contract."""

    fields = (
        ("init_position_std_m", 1.0),
        ("init_velocity_std_mps", 1.0),
        ("init_attitude_std_deg", math.pi / 180.0),
        ("init_gyro_bias_std_deg_h", math.pi / 180.0 / 3600.0),
        ("init_accel_bias_std_mgal", 1.0e-5),
        ("init_gyro_scale_std_ppm", 1.0e-6),
        ("init_accel_scale_std_ppm", 1.0e-6),
    )
    std_internal: list[float] = []
    source_groups: dict[str, list[float]] = {}
    for field, scale in fields:
        raw = solver_common.get(field)
        if not isinstance(raw, list) or len(raw) != 3:
            raise ProtocolContractError(f"solver_common.{field} must contain exactly three values")
        values = [float(value) for value in raw]
        if any(not math.isfinite(value) or value < 0.0 for value in values):
            raise ProtocolContractError(f"solver_common.{field} contains an invalid std")
        source_groups[field] = values
        std_internal.extend(value * scale for value in values)
    if len(std_internal) != 21:
        raise ProtocolContractError("Common initialization must describe exactly 21 error states")
    return {
        "error_state_dimension": 21,
        "error_state_order": list(ERROR_STATE_ORDER),
        "source_std_groups": source_groups,
        "state_std_internal": std_internal,
        "covariance_diagonal_internal": [value * value for value in std_internal],
        "covariance_off_diagonal_policy": "zero",
        "cpp_contract": "GIEngine.initializeCovariance seven contiguous 3-state blocks",
    }


def validate_common_initialization(initialization: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "position_geodetic_deg_m",
        "velocity_ned_mps",
        "roll_pitch_deg",
        "yaw_ned_deg",
        "bias_scale_state",
        "covariance_diagonal",
        "covariance_contract",
        "position_velocity_source_role",
        "roll_pitch_source_role",
        "yaw_source_role",
        "trace_used",
        "method_specific",
        "common_initialization_dual_yaw_used",
    }
    missing = sorted(required - set(initialization))
    if missing:
        raise ProtocolContractError("Common initialization fields missing: " + ",".join(missing))
    if initialization.get("trace_used") is not False:
        raise ProtocolContractError("Trace cannot initialize the solver")
    if initialization.get("method_specific") is not False:
        raise ProtocolContractError("Method-specific initialization is forbidden")
    position_velocity_role = initialization.get("position_velocity_source_role")
    roll_pitch_role = initialization.get("roll_pitch_source_role")
    legacy_roles = (
        position_velocity_role == "gnss_source_at_common_start"
        and roll_pitch_role == "go2_body_attitude_at_common_start"
    )
    kick_aligned_roles = (
        position_velocity_role
        == (
            "gnss_position_exact_common_start_and_receiver_velocity_"
            "latest_valid_at_or_before_common_start"
        )
        and initialization.get("position_source_role")
        == "gnss_position_exact_common_start"
        and initialization.get("velocity_source_role")
        == "gnss_receiver_velocity_latest_valid_at_or_before_common_start"
        and roll_pitch_role
        == "go2_body_attitude_latest_valid_at_or_before_common_start"
    )
    if not legacy_roles and not kick_aligned_roles:
        raise ProtocolContractError(
            "Position/velocity/roll-pitch initialization provenance is not source-backed"
        )
    if kick_aligned_roles:
        timestamp_fields = (
            "position_initialization_timestamp",
            "velocity_initialization_timestamp",
            "roll_pitch_initialization_timestamp",
            "yaw_initialization_timestamp",
        )
        try:
            position_time, velocity_time, roll_pitch_time, yaw_time = (
                float(initialization[field]) for field in timestamp_fields
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolContractError(
                "Kick-aligned initialization provenance timestamps are missing"
            ) from exc
        if not all(
            math.isfinite(value)
            for value in (position_time, velocity_time, roll_pitch_time, yaw_time)
        ):
            raise ProtocolContractError(
                "Kick-aligned initialization provenance timestamps are invalid"
            )
        if not math.isclose(position_time, yaw_time, rel_tol=0.0, abs_tol=1.0e-9):
            raise ProtocolContractError(
                "Position and dual-yaw initialization must use the common start epoch"
            )
        if velocity_time > position_time + 1.0e-9 or roll_pitch_time > position_time + 1.0e-9:
            raise ProtocolContractError(
                "Kick-aligned initialization cannot consume a future observation"
            )
        if initialization.get("future_observation_used_for_initialization") is not False:
            raise ProtocolContractError(
                "Kick-aligned initialization must explicitly deny future observations"
            )
    if initialization.get("yaw_source_role") != "fixed_physical_dual_yaw_at_common_start":
        raise ProtocolContractError("Yaw initialization is not the fixed physical dual-yaw source")
    if initialization.get("common_initialization_dual_yaw_used") is not True:
        raise ProtocolContractError("Common initialization must explicitly record dual-yaw use")
    covariance = initialization.get("covariance_contract")
    if not isinstance(covariance, Mapping):
        raise ProtocolContractError("Common initialization covariance contract is missing")
    if covariance.get("error_state_dimension") != 21 or tuple(covariance.get("error_state_order") or ()) != ERROR_STATE_ORDER:
        raise ProtocolContractError("Common initialization covariance state identity mismatch")
    std_values = covariance.get("state_std_internal")
    diagonal = covariance.get("covariance_diagonal_internal")
    declared_diagonal = initialization.get("covariance_diagonal")
    if not isinstance(std_values, list) or not isinstance(diagonal, list) or not isinstance(declared_diagonal, list):
        raise ProtocolContractError("Common initialization covariance arrays are missing")
    if len(std_values) != len(diagonal) or len(diagonal) != len(declared_diagonal) or len(diagonal) != 21:
        raise ProtocolContractError("Common initialization covariance must contain 21 diagonal entries")
    for std, expected, declared in zip(std_values, diagonal, declared_diagonal):
        std_value = float(std)
        expected_value = float(expected)
        declared_value = float(declared)
        if not all(math.isfinite(value) and value >= 0.0 for value in (std_value, expected_value, declared_value)):
            raise ProtocolContractError("Common initialization covariance contains invalid values")
        if not math.isclose(expected_value, std_value * std_value, rel_tol=1.0e-12, abs_tol=1.0e-24):
            raise ProtocolContractError("Common initialization covariance is not the square of its std")
        if not math.isclose(declared_value, expected_value, rel_tol=1.0e-12, abs_tol=1.0e-24):
            raise ProtocolContractError("Common initialization covariance diagonal drifted")
    bias_scale = initialization.get("bias_scale_state")
    if not isinstance(bias_scale, list) or len(bias_scale) != 12 or any(
        not math.isfinite(float(value)) for value in bias_scale
    ):
        raise ProtocolContractError("Common initialization bias/scale state must contain 12 finite values")
    return dict(initialization)


def _validate_kick_aligned_initialization_timestamps(
    initialization: Mapping[str, Any], t_start: float
) -> None:
    """Bind every V2 initialization source timestamp to the frozen start."""

    position_time = float(initialization["position_initialization_timestamp"])
    velocity_time = float(initialization["velocity_initialization_timestamp"])
    roll_pitch_time = float(initialization["roll_pitch_initialization_timestamp"])
    yaw_time = float(initialization["yaw_initialization_timestamp"])
    if not (
        math.isclose(position_time, t_start, rel_tol=0.0, abs_tol=1.0e-9)
        and math.isclose(yaw_time, t_start, rel_tol=0.0, abs_tol=1.0e-9)
    ):
        raise ProtocolContractError(
            "Kick-aligned position/yaw initialization is not bound to the common start"
        )
    if velocity_time > t_start + 1.0e-9 or roll_pitch_time > t_start + 1.0e-9:
        raise ProtocolContractError(
            "Kick-aligned initialization consumed an observation after the common start"
        )
    if initialization.get("future_observation_used_for_initialization") is not False:
        raise ProtocolContractError(
            "Kick-aligned initialization must explicitly deny future observations"
        )


def compute_full_common_window(
    coverages: Sequence[StreamCoverage],
    *,
    source_time_origin_seconds: float,
    common_initialization: Mapping[str, Any],
) -> FrozenWindow:
    by_role = {coverage.stream_role: coverage for coverage in coverages}
    if tuple(coverage.stream_role for coverage in coverages) != REQUIRED_WINDOW_STREAMS:
        raise ProtocolContractError("Coverage set/order must exactly match all required formal streams")
    if len(by_role) != len(REQUIRED_WINDOW_STREAMS):
        raise ProtocolContractError("Duplicate formal window stream role")
    start = max(coverage.first_valid_timestamp for coverage in coverages)
    end = min(coverage.last_valid_timestamp for coverage in coverages)
    if not math.isfinite(start) or not math.isfinite(end) or end <= start:
        raise ProtocolContractError("Formal full common window is empty")
    if not math.isfinite(source_time_origin_seconds):
        raise ProtocolContractError("Source time origin is not finite")
    initialization = validate_common_initialization(common_initialization)
    return FrozenWindow(
        t_start=start,
        t_end=end,
        duration_seconds=end - start,
        source_time_origin_seconds=float(source_time_origin_seconds),
        streams=tuple(coverages),
        common_initialization=initialization,
    )


def compute_kick_aligned_window(
    coverages: Sequence[StreamCoverage],
    *,
    core_gnss_timestamps: Sequence[float],
    dual_yaw_timestamps: Sequence[float],
    mapped_kick_provider_time: float,
    source_time_origin_seconds: float,
    common_initialization: Mapping[str, Any],
) -> FrozenWindow:
    """Build the V2 interval from kick + core streams, never optional streams.

    ``mapped_kick_provider_time`` and ``core_gnss_timestamps`` share the
    provider/solver time origin.  The first GNSS epoch at or after the kick is
    the immutable start.  Propagation IMU and dual yaw must already cover that
    epoch; their first availability cannot silently move it.
    """

    if tuple(coverage.stream_role for coverage in coverages) != REQUIRED_WINDOW_STREAMS:
        raise ProtocolContractError("Coverage set/order must exactly match all formal streams")
    by_role = {coverage.stream_role: coverage for coverage in coverages}
    if len(by_role) != len(REQUIRED_WINDOW_STREAMS):
        raise ProtocolContractError("Duplicate formal window stream role")
    finite_gnss = [float(value) for value in core_gnss_timestamps if math.isfinite(float(value))]
    if len(finite_gnss) < 2 or any(
        later <= earlier for earlier, later in zip(finite_gnss, finite_gnss[1:])
    ):
        raise ProtocolContractError("Core GNSS timestamps must be strictly increasing")
    finite_dual_yaw = [float(value) for value in dual_yaw_timestamps if math.isfinite(float(value))]
    if len(finite_dual_yaw) < 2 or any(
        later <= earlier for earlier, later in zip(finite_dual_yaw, finite_dual_yaw[1:])
    ):
        raise ProtocolContractError("Dual-yaw timestamps must be strictly increasing")
    if not math.isfinite(mapped_kick_provider_time):
        raise ProtocolContractError("Mapped kick time is not finite")
    start = next((value for value in finite_gnss if value >= mapped_kick_provider_time), None)
    if start is None:
        raise ProtocolContractError("No core GNSS epoch exists at or after the mapped kick")
    propagation = by_role["propagation_imu"]
    gnss = by_role["gnss_position"]
    dual_yaw = by_role["dual_yaw"]
    if not (propagation.first_valid_timestamp <= start <= propagation.last_valid_timestamp):
        raise ProtocolContractError("Propagation IMU is unavailable at the frozen V2 start")
    if not (gnss.first_valid_timestamp <= start <= gnss.last_valid_timestamp):
        raise ProtocolContractError("GNSS coverage does not contain the frozen V2 start")
    if not (dual_yaw.first_valid_timestamp <= start <= dual_yaw.last_valid_timestamp) or not any(
        math.isclose(value, start, rel_tol=0.0, abs_tol=1.0e-9)
        for value in finite_dual_yaw
    ):
        raise ProtocolContractError("Dual yaw is unavailable at the frozen V2 start")
    end = min(propagation.last_valid_timestamp, gnss.last_valid_timestamp)
    if end <= start:
        raise ProtocolContractError("Kick-aligned formal window is empty")
    if not math.isfinite(source_time_origin_seconds):
        raise ProtocolContractError("Source time origin is not finite")
    initialization = validate_common_initialization(common_initialization)
    _validate_kick_aligned_initialization_timestamps(initialization, start)
    return FrozenWindow(
        t_start=start,
        t_end=end,
        duration_seconds=end - start,
        source_time_origin_seconds=float(source_time_origin_seconds),
        streams=tuple(coverages),
        common_initialization=initialization,
        policy=V2_WINDOW_POLICY,
        t_start_formula="first(valid_core_gnss_time >= mapped_kick_provider_time)",
        t_end_formula="min(propagation_imu_last_valid,core_gnss_last_valid)",
        mapped_kick_provider_time=float(mapped_kick_provider_time),
        first_valid_gnss_after_kick=start,
        optional_streams_delay_start=False,
    )


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False)


def freeze_window_contract(
    protocol: ProtocolConfig,
    window: FrozenWindow,
    output_dir: str | Path,
) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    initialization = window.common_initialization
    init_hash = sha256_text(json.dumps(initialization, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    protocol_schema = protocol.payload.get("schema_version")
    expected_policy = V2_WINDOW_POLICY if protocol_schema == V2_SCHEMA_VERSION else V1_WINDOW_POLICY
    if window.policy != expected_policy:
        raise ProtocolContractError("Frozen window policy differs from the loaded protocol")
    schema_version = (
        "paper-rebuild-window-contract-v2"
        if window.policy == V2_WINDOW_POLICY
        else "paper-rebuild-window-contract-v1"
    )
    payload = {
        "schema_version": schema_version,
        "stage_id": protocol.payload["stage_id"],
        "case_id": protocol.payload["case_id"],
        "protocol_id": protocol.payload["protocol_id"],
        "data_mode": DATA_MODE,
        "policy": window.policy,
        "t_start_formula": window.t_start_formula,
        "t_end_formula": window.t_end_formula,
        "t_start": window.t_start,
        "t_end": window.t_end,
        "duration_seconds": window.duration_seconds,
        "source_time_origin_seconds": window.source_time_origin_seconds,
        "internal_dropout_preserved": True,
        "method_specific_window": False,
        "smoke_truncation_applied": False,
        "evaluation_burn_in_seconds": 0.0,
        "trace_or_method_output_used_to_select_window": False,
        "mapped_kick_provider_time": window.mapped_kick_provider_time,
        "first_valid_gnss_after_kick": window.first_valid_gnss_after_kick,
        "optional_streams_delay_start": window.optional_streams_delay_start,
        "common_initialization": initialization,
        "common_initialization_hash": init_hash,
        "protocol_source_hash": protocol.sha256,
    }
    contract = destination / "WINDOW_CONTRACT.yaml"
    contract.write_text(_dump_yaml(payload), encoding="utf-8")
    contract_hash = sha256_file(contract)
    (destination / "WINDOW_CONTRACT.sha256").write_text(
        f"{contract_hash}  WINDOW_CONTRACT.yaml\n", encoding="utf-8"
    )
    coverage_rows = [asdict(stream) for stream in window.streams]
    coverage_path = write_csv_atomic(
        destination / "WINDOW_SOURCE_COVERAGE.csv",
        list(coverage_rows[0]),
        coverage_rows,
    )
    return {
        "window_contract_hash": contract_hash,
        "window_source_coverage_hash": sha256_file(coverage_path),
        "common_initialization_hash": init_hash,
    }


def load_frozen_window(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    payload = load_yaml_mapping(source)
    schema = payload.get("schema_version")
    if schema not in {"paper-rebuild-window-contract-v1", "paper-rebuild-window-contract-v2"}:
        raise ProtocolContractError("Frozen window schema mismatch")
    policy = payload.get("policy")
    if schema == "paper-rebuild-window-contract-v1":
        if policy != V1_WINDOW_POLICY:
            raise ProtocolContractError("Frozen V1 window policy mismatch")
    else:
        if policy != V2_WINDOW_POLICY:
            raise ProtocolContractError("Frozen V2 window policy mismatch")
        if payload.get("optional_streams_delay_start") is not False:
            raise ProtocolContractError("Frozen V2 optional streams delay start")
        mapped_kick = payload.get("mapped_kick_provider_time")
        first_gnss = payload.get("first_valid_gnss_after_kick")
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in (mapped_kick, first_gnss)):
            raise ProtocolContractError("Frozen V2 kick/GNSS start fields are missing")
        if float(first_gnss) < float(mapped_kick):
            raise ProtocolContractError("Frozen V2 GNSS start precedes the mapped kick")
        if not math.isclose(float(first_gnss), float(payload.get("t_start", math.nan)), rel_tol=0.0, abs_tol=1.0e-9):
            raise ProtocolContractError("Frozen V2 t_start differs from first post-kick GNSS epoch")
    if payload.get("smoke_truncation_applied") is not False:
        raise ProtocolContractError("Frozen formal window contains smoke truncation")
    if payload.get("trace_or_method_output_used_to_select_window") is not False:
        raise ProtocolContractError("Frozen window used trace or method output")
    if float(payload.get("t_end", 0.0)) <= float(payload.get("t_start", 0.0)):
        raise ProtocolContractError("Frozen window is empty")
    initialization = validate_common_initialization(
        payload.get("common_initialization") or {}
    )
    if schema == "paper-rebuild-window-contract-v2":
        expected_initialization_hash = sha256_text(
            json.dumps(
                initialization,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        if payload.get("common_initialization_hash") != expected_initialization_hash:
            raise ProtocolContractError("Frozen common initialization hash mismatch")
        _validate_kick_aligned_initialization_timestamps(
            initialization, float(payload["t_start"])
        )
    return payload
