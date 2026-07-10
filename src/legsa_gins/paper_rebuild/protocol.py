"""CLEAN1 protocol loading, full common-window freeze, and initialization gates."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidence import EvidenceContractError, LOCAL_PATH_RE, write_csv_atomic
from .manifest import sha256_file, sha256_text
from .methods import FORMAL_METHOD_ORDER
from .paths import load_yaml_mapping


STAGE_ID = "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
PROTOCOL_ID = "CLEAN1_BY2_CLEAN_NORMAL_V1"
DATA_MODE = "real_by2_raw"
REQUIRED_WINDOW_STREAMS = (
    "propagation_imu",
    "gnss_position",
    "receiver_velocity",
    "dual_yaw",
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


def load_clean1_protocol(path: str | Path) -> ProtocolConfig:
    source = Path(path).resolve(strict=True)
    payload = load_yaml_mapping(source)
    expected = {
        "schema_version": "paper_rebuild.clean1_by2_protocol.v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "protocol_id": PROTOCOL_ID,
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
    if window.get("policy") != "full_common_required_stream_interval":
        raise ProtocolContractError("Protocol is not a full common-window policy")
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
    if not isinstance(provider_generation, Mapping) or dict(provider_generation) != expected_provider_generation:
        raise ProtocolContractError("Tracked provider-generation parameters differ from CLEAN1 freeze")
    solver_common = payload.get("solver_common")
    if not isinstance(solver_common, Mapping) or provider_generation["raw_doppler_min_sat"] != solver_common.get("raw_doppler_min_sat"):
        raise ProtocolContractError("Provider and solver Raw Doppler minimum-satellite contracts differ")
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
    if initialization.get("position_velocity_source_role") != "gnss_source_at_common_start":
        raise ProtocolContractError("Position/velocity initialization is not source-backed GNSS")
    if initialization.get("roll_pitch_source_role") != "go2_body_attitude_at_common_start":
        raise ProtocolContractError("Roll/pitch initialization is not source-backed Go2 body attitude")
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
    payload = {
        "schema_version": "paper-rebuild-window-contract-v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "protocol_id": PROTOCOL_ID,
        "data_mode": DATA_MODE,
        "policy": "full_common_required_stream_interval",
        "t_start_formula": "max(all_required_stream_first_valid_timestamps)",
        "t_end_formula": "min(all_required_stream_last_valid_timestamps)",
        "t_start": window.t_start,
        "t_end": window.t_end,
        "duration_seconds": window.duration_seconds,
        "source_time_origin_seconds": window.source_time_origin_seconds,
        "internal_dropout_preserved": True,
        "method_specific_window": False,
        "smoke_truncation_applied": False,
        "evaluation_burn_in_seconds": 0.0,
        "trace_or_method_output_used_to_select_window": False,
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
    if payload.get("schema_version") != "paper-rebuild-window-contract-v1":
        raise ProtocolContractError("Frozen window schema mismatch")
    if payload.get("policy") != "full_common_required_stream_interval":
        raise ProtocolContractError("Frozen window policy mismatch")
    if payload.get("smoke_truncation_applied") is not False:
        raise ProtocolContractError("Frozen formal window contains smoke truncation")
    if payload.get("trace_or_method_output_used_to_select_window") is not False:
        raise ProtocolContractError("Frozen window used trace or method output")
    if float(payload.get("t_end", 0.0)) <= float(payload.get("t_start", 0.0)):
        raise ProtocolContractError("Frozen window is empty")
    validate_common_initialization(payload.get("common_initialization") or {})
    return payload
