"""Frozen, offline-only CLEAN1 evaluator with no alignment or result-driven edits."""

from __future__ import annotations

import bisect
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidence import write_csv_atomic, write_read_ledger
from .manifest import sha256_file, write_json_atomic
from .paths import load_yaml_mapping
from .protocol import load_frozen_window


REFERENCE_REQUIRED_COLUMNS = ("time", "lat", "lon", "height", "yaw", "pitch", "roll")
SOLVER_REQUIRED_COLUMNS = (
    "time",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn",
    "ve",
    "vd",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
)
ERROR_COLUMNS = (
    "horizontal_position_error_m",
    "up_error_m",
    "position_3d_error_m",
    "yaw_error_deg",
)

TRACKED_EVALUATOR_SCHEMA_V2 = "paper_rebuild.evaluator_contract.v2"
FROZEN_EVALUATOR_SCHEMA_V2 = "paper-rebuild-frozen-evaluator-contract-v2"
EVALUATOR_PROTOCOL_ID_V2 = "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"
EVALUATOR_PROFILE_V2 = "FIXPOSITION_SAME_SOURCE_DIRECT_REFERENCE"
READY_STATUS = "READY_FOR_OFFLINE_EVALUATION"


class EvaluatorContractError(ValueError):
    """Evaluator freeze/readiness/matching/cross-check failed."""


@dataclass(frozen=True)
class EvaluatorFreeze:
    contract_path: Path
    contract_hash: str
    reference_schema_audit_path: Path
    ready: bool
    terminal_status: str


def wrap_signed_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def wrap_360_deg(value: float) -> float:
    return value % 360.0


def reference_yaw_enu_to_solver_ned_deg(value: float) -> float:
    return wrap_360_deg(90.0 - value)


def _read_rows(path: Path, required: Sequence[str]) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        missing = [field for field in required if field not in fields]
        if missing:
            raise EvaluatorContractError(f"Missing CSV columns in {path.name}: {','.join(missing)}")
        rows = list(reader)
    if not rows:
        raise EvaluatorContractError(f"CSV has no data rows: {path.name}")
    return rows, fields


def _strict_timestamps(rows: Sequence[Mapping[str, str]], column: str, label: str) -> list[float]:
    values: list[float] = []
    for number, row in enumerate(rows, start=2):
        try:
            value = float(row.get(column) or "nan")
        except ValueError as exc:
            raise EvaluatorContractError(f"Invalid {label} timestamp at row {number}") from exc
        if not math.isfinite(value):
            raise EvaluatorContractError(f"Non-finite {label} timestamp at row {number}")
        values.append(value)
    if any(later <= earlier for earlier, later in zip(values, values[1:])):
        raise EvaluatorContractError(f"Duplicate or nonmonotonic {label} timestamp")
    return values


def _interval_percentile_type7(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise EvaluatorContractError("Reference needs at least two timestamps")
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def derive_reference_timing_profile(
    reference_rows: Sequence[Mapping[str, str]],
) -> dict[str, float | int]:
    """Derive the fixed V2 gap gate only from the offline reference timestamps."""

    times = _strict_timestamps(reference_rows, "time", "reference")
    if len(times) < 2:
        raise EvaluatorContractError("Reference needs at least two timestamps")
    intervals = [later - earlier for earlier, later in zip(times, times[1:])]
    median_dt = _interval_percentile_type7(intervals, 0.50)
    p99_dt = _interval_percentile_type7(intervals, 0.99)
    max_gap = max(3.0 * median_dt, p99_dt + 1.0e-9)
    return {
        "row_count": len(times),
        "first_timestamp": times[0],
        "last_timestamp": times[-1],
        "interval_count": len(intervals),
        "median_dt_seconds": median_dt,
        "p99_dt_seconds": p99_dt,
        "max_allowed_bracket_gap_seconds": max_gap,
    }


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False)


def _valid_locked_source_hashes(
    source_hashes: Any,
    verified_source_hashes: Mapping[str, str] | None,
) -> bool:
    if not isinstance(source_hashes, Mapping) or not source_hashes or not verified_source_hashes:
        return False
    for relative, digest in source_hashes.items():
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            return False
        if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            return False
        if verified_source_hashes.get(relative) != digest:
            return False
    return True


def _reference_point_ready(
    contract: Mapping[str, Any] | None,
    verified_source_hashes: Mapping[str, str] | None,
) -> tuple[bool, dict[str, Any]]:
    if not contract:
        return False, {
            "reference_point_contract_proven": False,
            "reason": "no source-backed solver-state to evaluation-reference lever-arm/point identity",
            "trace_fit_or_alignment_used": False,
        }
    required = {
        "reference_point_contract_proven",
        "source_backed",
        "solver_output_reference_point",
        "evaluation_reference_point",
        "transform_or_identity_contract",
        "source_hashes",
        "trace_fit_or_alignment_used",
    }
    if not required.issubset(contract):
        raise EvaluatorContractError("Reference-point contract fields are incomplete")
    source_hashes = contract.get("source_hashes")
    hashes_ok = _valid_locked_source_hashes(source_hashes, verified_source_hashes)
    semantic_values = [
        contract.get("solver_output_reference_point"),
        contract.get("evaluation_reference_point"),
        contract.get("transform_or_identity_contract"),
    ]
    semantics_ok = all(
        isinstance(value, str) and value.strip() and value.strip().upper() not in {"UNKNOWN", "NOT_AVAILABLE", "NOT_PROVEN"}
        for value in semantic_values
    )
    transform = str(contract.get("transform_or_identity_contract") or "")
    transform_ok = transform.startswith("identity:") or transform.startswith("fixed_transform:")
    ready = (
        contract.get("reference_point_contract_proven") is True
        and contract.get("source_backed") is True
        and contract.get("trace_fit_or_alignment_used") is False
        and hashes_ok
        and semantics_ok
        and transform_ok
    )
    return ready, dict(contract)


def _reference_frame_ready(
    contract: Mapping[str, Any] | None,
    verified_source_hashes: Mapping[str, str] | None,
) -> tuple[bool, dict[str, Any]]:
    if not contract:
        return False, {
            "reference_attitude_frame_contract_proven": False,
            "reason": "no source-backed semantics for trace yaw frame/axis convention",
            "trace_fit_or_axis_selection_used": False,
        }
    required = {
        "reference_attitude_frame_contract_proven",
        "source_backed",
        "reference_attitude_frame",
        "solver_attitude_frame",
        "conversion_formula",
        "source_hashes",
        "trace_fit_or_axis_selection_used",
    }
    if not required.issubset(contract):
        raise EvaluatorContractError("Reference-frame contract fields are incomplete")
    ready = (
        contract.get("reference_attitude_frame_contract_proven") is True
        and contract.get("source_backed") is True
        and contract.get("reference_attitude_frame") == "ENU"
        and contract.get("solver_attitude_frame") == "NED_FRD"
        and contract.get("conversion_formula") == "wrap(90_deg-reference_yaw_ENU_deg)"
        and contract.get("trace_fit_or_axis_selection_used") is False
        and _valid_locked_source_hashes(contract.get("source_hashes"), verified_source_hashes)
    )
    return ready, dict(contract)


def freeze_evaluator_contract(
    tracked_contract_path: str | Path,
    reference_path: str | Path | None,
    output_dir: str | Path,
    *,
    reference_relative_path: str,
    expected_reference_sha256: str,
    reference_point_contract: Mapping[str, Any] | None = None,
    reference_frame_contract: Mapping[str, Any] | None = None,
    verified_source_hashes: Mapping[str, str] | None = None,
) -> EvaluatorFreeze:
    """Freeze V2 from the hash-lock declaration without opening the trace payload."""

    # 中文说明：reference_path 仅为 V1 调用兼容参数。V2 freeze 不解析、不 resolve、
    # 不 hash 该路径；真正的 trace 读取和 hash 复核只允许在 offline evaluator 中发生。
    del reference_path
    if reference_point_contract is not None or reference_frame_contract is not None:
        raise EvaluatorContractError(
            "CLEAN1R1C V2 proof injection is not authorized; use the fixed tracked profile"
        )

    tracked_path = Path(tracked_contract_path).resolve(strict=True)
    base = load_yaml_mapping(tracked_path)
    if base.get("schema_version") != TRACKED_EVALUATOR_SCHEMA_V2:
        raise EvaluatorContractError("Tracked evaluator contract schema mismatch")
    expected_top_level = {
        "protocol_id": EVALUATOR_PROTOCOL_ID_V2,
        "profile": EVALUATOR_PROFILE_V2,
        "formal_metrics_authorized": True,
        "method_output_read_during_freeze": False,
        "trace_read_during_freeze": False,
        "position_same_source_mounting_caveat": True,
        "independent_ground_truth": False,
        "point_compensation_in_evaluator": False,
        "terminal_status": READY_STATUS,
        "freeze_before_solver_output_inspection": True,
    }
    for field, expected in expected_top_level.items():
        if base.get(field) != expected:
            raise EvaluatorContractError(f"Tracked evaluator top-level field mismatch: {field}")
    forbidden = base.get("forbidden_postprocessing")
    if not isinstance(forbidden, Mapping) or any(value is not False for value in forbidden.values()):
        raise EvaluatorContractError("Tracked evaluator permits forbidden postprocessing")
    timestamp_contract = base.get("timestamps")
    if not isinstance(timestamp_contract, Mapping):
        raise EvaluatorContractError("Tracked evaluator timestamp contract is missing")
    expected_timestamp_fields = {
        "solver_to_common_formula": "solver_relative_seconds_plus_window_absolute_origin_seconds",
        "reference_to_common_formula": "identity_absolute_unix_seconds",
        "matching_policy": "bracketed_linear_interpolation",
        "max_gap_policy": "max_3x_median_dt_p99_dt_plus_1e-9",
        "reference_interval_percentile": "type7",
        "duplicate_solver_timestamp_policy": "fail",
        "duplicate_reference_timestamp_policy": "fail",
        "unmatched_epoch_policy": "retain_row_and_label_unmatched",
        "extrapolation_policy": "forbidden",
        "first_last_extrapolation": "forbidden",
        "bracket_gap_policy": "reference_bracket_interval_lte_derived_max_gap",
        "yaw_interpolation_policy": "unwrap_enu_degrees_then_linear_interpolate",
        "position_interpolation_policy": "wgs84_blh_to_ecef_then_linear_interpolate",
        "trace_based_time_offset_search": False,
    }
    for field, expected in expected_timestamp_fields.items():
        if timestamp_contract.get(field) != expected:
            raise EvaluatorContractError(f"Tracked evaluator timestamp field mismatch: {field}")
    if base.get("reference_wording") != "same-source direct evaluation-only reference" or base.get("reference_independence_established") is not False:
        raise EvaluatorContractError("Tracked evaluator reference wording/independence contract mismatch")
    frames = base.get("frames")
    if not isinstance(frames, Mapping) or frames.get("method_specific_conversion") is not False:
        raise EvaluatorContractError("Tracked evaluator frame contract is incomplete")
    expected_frame_fields = {
        "solver_position": "geodetic_WGS84_lat_lon_ellipsoidal_height",
        "reference_position": "geodetic_WGS84_lat_lon_ellipsoidal_height",
        "position_error_frame": "local_NED_at_interpolated_reference",
        "solver_attitude": "NED_FRD_degrees",
        "reference_attitude": "ENU_heading_degrees",
        "reference_yaw_to_solver_formula": "wrap360(90_deg-reference_yaw_ENU_deg)",
        "yaw_residual": "wrap_to_minus180_plus180(solver_minus_reference)",
        "point_compensation_in_evaluator": False,
        "position_same_source_mounting_caveat": True,
    }
    for field, expected in expected_frame_fields.items():
        if frames.get(field) != expected:
            raise EvaluatorContractError(f"Tracked evaluator frame field mismatch: {field}")
    aggregate = base.get("aggregate")
    if not isinstance(aggregate, Mapping) or aggregate.get("metrics") != ["rmse", "mae", "median", "p95", "max"]:
        raise EvaluatorContractError("Tracked evaluator aggregate metric contract mismatch")
    if float(aggregate.get("crosscheck_absolute_tolerance", -1.0)) != 1.0e-10 or float(
        aggregate.get("crosscheck_relative_tolerance", -1.0)
    ) != 1.0e-10:
        raise EvaluatorContractError("Tracked evaluator cross-check tolerance mismatch")

    relative = Path(reference_relative_path)
    if relative.is_absolute() or ".." in relative.parts or not reference_relative_path:
        raise EvaluatorContractError("Evaluation-only reference alias is not root-relative")
    digest = str(expected_reference_sha256)
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise EvaluatorContractError("Evaluation-only reference hash-lock digest is invalid")
    if not verified_source_hashes or verified_source_hashes.get(reference_relative_path) != digest:
        raise EvaluatorContractError("Evaluation-only reference hash-lock binding is missing")

    frozen = dict(base)
    frozen["schema_version"] = FROZEN_EVALUATOR_SCHEMA_V2
    frozen["tracked_contract_sha256"] = sha256_file(tracked_path)
    frozen["reference"] = {
        "path_alias": "<RAW_ROOT>",
        "relative_path": reference_relative_path,
        "sha256": digest,
        "hash_lock_binding_verified": True,
        "payload_read_during_freeze": False,
        "schema_validation_phase": "offline_evaluation_only",
        "cadence_derivation_phase": "offline_evaluation_only",
        "max_allowed_matching_gap_seconds": "DERIVED_OFFLINE_FROM_HASH_LOCKED_REFERENCE",
        "cadence_derivation_used_method_output": False,
        "metadata_ypr_frame": "ENU",
        "yaw_unit": "degree",
    }
    frozen["reference_point_contract"] = {
        "profile": EVALUATOR_PROFILE_V2,
        "point_compensation_in_evaluator": False,
        "position_same_source_mounting_caveat": True,
        "independent_ground_truth": False,
    }
    frozen["reference_point_contract_proven"] = False
    frozen["reference_attitude_frame_contract_proven"] = True
    frozen["formal_metrics_authorized"] = True
    frozen["method_output_read_during_freeze"] = False
    frozen["trace_read_during_freeze"] = False
    frozen["terminal_status"] = READY_STATUS

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    contract_path = destination / "EVALUATOR_CONTRACT.yaml"
    contract_path.write_text(_dump_yaml(frozen), encoding="utf-8")
    contract_hash = sha256_file(contract_path)
    (destination / "EVALUATOR_CONTRACT.sha256").write_text(
        f"{contract_hash}  EVALUATOR_CONTRACT.yaml\n", encoding="utf-8"
    )
    audit = {
        "schema_version": "paper-rebuild-reference-declaration-audit-v2",
        "protocol_id": EVALUATOR_PROTOCOL_ID_V2,
        "profile": EVALUATOR_PROFILE_V2,
        "reference_wording": "same-source direct evaluation-only reference",
        "reference_independence_established": False,
        "independent_ground_truth": False,
        "reference_path_alias": "<RAW_ROOT>",
        "reference_relative_path": reference_relative_path,
        "reference_sha256": digest,
        "hash_lock_binding_verified": True,
        "trace_read_during_freeze": False,
        "method_output_read_during_freeze": False,
        "declared_required_columns": list(REFERENCE_REQUIRED_COLUMNS),
        "schema_validation_phase": "offline_evaluation_only",
        "cadence_derivation_phase": "offline_evaluation_only",
        "yaw_frame": "ENU",
        "yaw_unit": "degree",
        "yaw_conversion": "wrap360(90_deg-reference_yaw_ENU_deg)",
        "roll_pitch_metric_supported": False,
        "velocity_metric_supported": False,
        "reference_point_contract_proven": False,
        "position_same_source_mounting_caveat": True,
        "point_compensation_in_evaluator": False,
        "reference_attitude_frame_contract_proven": True,
        "blocking_reasons": [],
        "formal_metrics_authorized": True,
        "terminal_status": READY_STATUS,
    }
    audit_path = write_json_atomic(destination / "REFERENCE_SCHEMA_AUDIT.json", audit)
    return EvaluatorFreeze(contract_path, contract_hash, audit_path, True, READY_STATUS)


def load_frozen_evaluator(path: str | Path, *, require_ready: bool = True) -> dict[str, Any]:
    payload = load_yaml_mapping(Path(path).resolve(strict=True))
    schema = payload.get("schema_version")
    if schema not in {"paper-rebuild-frozen-evaluator-contract-v1", FROZEN_EVALUATOR_SCHEMA_V2}:
        raise EvaluatorContractError("Frozen evaluator schema mismatch")
    if payload.get("method_output_read_during_freeze") is not False:
        raise EvaluatorContractError("Evaluator was not frozen before outputs")
    if schema == FROZEN_EVALUATOR_SCHEMA_V2:
        required_v2 = {
            "protocol_id": EVALUATOR_PROTOCOL_ID_V2,
            "profile": EVALUATOR_PROFILE_V2,
            "formal_metrics_authorized": True,
            "method_output_read_during_freeze": False,
            "trace_read_during_freeze": False,
            "position_same_source_mounting_caveat": True,
            "independent_ground_truth": False,
            "point_compensation_in_evaluator": False,
            "terminal_status": READY_STATUS,
        }
        if any(payload.get(field) != expected for field, expected in required_v2.items()):
            raise EvaluatorContractError("Frozen V2 evaluator invariant mismatch")
        reference = payload.get("reference")
        if not isinstance(reference, Mapping) or reference.get("hash_lock_binding_verified") is not True:
            raise EvaluatorContractError("Frozen V2 evaluator reference binding is missing")
    elif require_ready and (
        payload.get("reference_point_contract_proven") is not True
        or payload.get("reference_attitude_frame_contract_proven") is not True
        or payload.get("formal_metrics_authorized") is not True
    ):
        raise EvaluatorContractError("BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED")
    return payload


def _ecef(lat_deg: float, lon_deg: float, height_m: float) -> tuple[float, float, float]:
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)
    n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    return (
        (n + height_m) * cos_lat * cos_lon,
        (n + height_m) * cos_lat * sin_lon,
        (n * (1.0 - e2) + height_m) * sin_lat,
    )


def _geodetic_delta_ned(
    solver_lat: float,
    solver_lon: float,
    solver_height: float,
    ref_lat: float,
    ref_lon: float,
    ref_height: float,
) -> tuple[float, float, float]:
    solver_ecef = _ecef(solver_lat, solver_lon, solver_height)
    reference_ecef = _ecef(ref_lat, ref_lon, ref_height)
    return _ecef_delta_ned(solver_ecef, reference_ecef)


def _ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert WGS84 ECEF to latitude/longitude degrees and ellipsoidal height."""

    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e2 = f * (2.0 - f)
    ep2 = (a * a - b * b) / (b * b)
    p = math.hypot(x, y)
    if p < 1.0e-12:
        latitude = math.copysign(math.pi / 2.0, z)
        longitude = 0.0
        height = abs(z) - b
        return math.degrees(latitude), math.degrees(longitude), height
    longitude = math.atan2(y, x)
    theta = math.atan2(z * a, p * b)
    sin_theta = math.sin(theta)
    cos_theta = math.cos(theta)
    latitude = math.atan2(
        z + ep2 * b * sin_theta**3,
        p - e2 * a * cos_theta**3,
    )
    sin_latitude = math.sin(latitude)
    prime_vertical = a / math.sqrt(1.0 - e2 * sin_latitude * sin_latitude)
    height = p / math.cos(latitude) - prime_vertical
    return math.degrees(latitude), math.degrees(longitude), height


def _ecef_delta_ned(
    solver_ecef: tuple[float, float, float],
    reference_ecef: tuple[float, float, float],
) -> tuple[float, float, float]:
    sx, sy, sz = solver_ecef
    rx, ry, rz = reference_ecef
    dx, dy, dz = sx - rx, sy - ry, sz - rz
    ref_lat, ref_lon, _ = _ecef_to_geodetic(rx, ry, rz)
    lat = math.radians(ref_lat)
    lon = math.radians(ref_lon)
    north = -math.sin(lat) * math.cos(lon) * dx - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    down = -math.cos(lat) * math.cos(lon) * dx - math.cos(lat) * math.sin(lon) * dy - math.sin(lat) * dz
    return north, east, down


def _float(row: Mapping[str, str], field: str) -> float:
    try:
        value = float(row.get(field) or "nan")
    except ValueError as exc:
        raise EvaluatorContractError(f"Invalid numeric value in column {field}") from exc
    if not math.isfinite(value):
        raise EvaluatorContractError(f"Non-finite numeric value in column {field}")
    return value


def _unwrap_degrees(values: Sequence[float]) -> list[float]:
    if not values:
        raise EvaluatorContractError("Reference yaw sequence is empty")
    if any(not math.isfinite(value) for value in values):
        raise EvaluatorContractError("Reference yaw contains a non-finite value")
    output = [float(values[0])]
    previous_wrapped = float(values[0])
    for value in values[1:]:
        current = float(value)
        output.append(output[-1] + wrap_signed_deg(current - previous_wrapped))
        previous_wrapped = current
    return output


def _lerp(left: float, right: float, fraction: float) -> float:
    return left + fraction * (right - left)


def build_row_level_errors(
    solver_rows: Sequence[Mapping[str, str]],
    reference_rows: Sequence[Mapping[str, str]],
    *,
    source_time_origin_seconds: float,
    max_gap_seconds: float | None = None,
) -> list[dict[str, Any]]:
    """Build V2 rows by bracketed ECEF/yaw interpolation; never extrapolate."""

    solver_times = _strict_timestamps(solver_rows, "time", "solver")
    reference_times = _strict_timestamps(reference_rows, "time", "reference")
    if not math.isfinite(source_time_origin_seconds):
        raise EvaluatorContractError("Window absolute time origin is not finite")
    timing = derive_reference_timing_profile(reference_rows)
    derived_max_gap = float(timing["max_allowed_bracket_gap_seconds"])
    effective_max_gap = derived_max_gap if max_gap_seconds is None else float(max_gap_seconds)
    if not math.isfinite(effective_max_gap) or effective_max_gap <= 0.0:
        raise EvaluatorContractError("Reference bracket gap gate is invalid")
    reference_ecef = [
        _ecef(_float(row, "lat"), _float(row, "lon"), _float(row, "height"))
        for row in reference_rows
    ]
    reference_yaw_unwrapped = _unwrap_degrees(
        [_float(row, "yaw") for row in reference_rows]
    )
    output: list[dict[str, Any]] = []
    for index, (solver, solver_time) in enumerate(zip(solver_rows, solver_times)):
        common_time = solver_time + source_time_origin_seconds
        row: dict[str, Any] = {
            "output_row_index": index,
            "solver_time": solver_time,
            "common_time": common_time,
            "reference_time": "",
            "matching_gap_seconds": "",
            "reference_left_time": "",
            "reference_right_time": "",
            "reference_bracket_gap_seconds": "",
            "interpolation_fraction": "",
            "matched": False,
            "unmatched_reason": "outside_reference_extent",
            "north_error_m": "",
            "east_error_m": "",
            "down_error_m": "",
            "vertical_error_m": "",
            **{field: "" for field in ERROR_COLUMNS},
        }
        if common_time < reference_times[0] or common_time > reference_times[-1]:
            output.append(row)
            continue

        right = bisect.bisect_left(reference_times, common_time)
        exact = right < len(reference_times) and math.isclose(
            reference_times[right], common_time, rel_tol=0.0, abs_tol=1.0e-12
        )
        if exact:
            left = right
            fraction = 0.0
            bracket_gap = 0.0
            interpolated_ecef = reference_ecef[left]
            interpolated_yaw_enu = reference_yaw_unwrapped[left]
        else:
            if right <= 0 or right >= len(reference_times):
                output.append(row)
                continue
            left = right - 1
            bracket_gap = reference_times[right] - reference_times[left]
            row.update(
                {
                    "reference_left_time": reference_times[left],
                    "reference_right_time": reference_times[right],
                    "reference_bracket_gap_seconds": bracket_gap,
                    "matching_gap_seconds": bracket_gap,
                }
            )
            if bracket_gap > effective_max_gap + 1.0e-12:
                row["unmatched_reason"] = "reference_bracket_gap_exceeds_gate"
                output.append(row)
                continue
            fraction = (common_time - reference_times[left]) / bracket_gap
            interpolated_ecef = tuple(
                _lerp(reference_ecef[left][axis], reference_ecef[right][axis], fraction)
                for axis in range(3)
            )
            interpolated_yaw_enu = _lerp(
                reference_yaw_unwrapped[left], reference_yaw_unwrapped[right], fraction
            )

        solver_ecef = _ecef(
            _float(solver, "lat_deg"),
            _float(solver, "lon_deg"),
            _float(solver, "height_m"),
        )
        north, east, down = _ecef_delta_ned(solver_ecef, interpolated_ecef)
        up = -down
        yaw_reference = reference_yaw_enu_to_solver_ned_deg(interpolated_yaw_enu)
        yaw_error = wrap_signed_deg(_float(solver, "yaw_deg") - yaw_reference)
        row.update(
            {
                "reference_time": common_time,
                "reference_left_time": reference_times[left],
                "reference_right_time": reference_times[right],
                "reference_bracket_gap_seconds": bracket_gap,
                "matching_gap_seconds": bracket_gap,
                "interpolation_fraction": fraction,
                "matched": True,
                "unmatched_reason": "",
                "north_error_m": north,
                "east_error_m": east,
                "down_error_m": down,
                "up_error_m": up,
                "vertical_error_m": abs(up),
                "horizontal_position_error_m": math.hypot(north, east),
                "position_3d_error_m": math.sqrt(north * north + east * east + up * up),
                "yaw_error_deg": yaw_error,
            }
        )
        output.append(row)
    return output


def _percentile_type7(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise EvaluatorContractError("Cannot aggregate an empty metric")
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def aggregate_row_level(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    matched = [row for row in rows if row.get("matched") is True]
    if not matched:
        raise EvaluatorContractError("No solver epochs matched the evaluation-only reference")
    metrics: dict[str, Any] = {}
    for field in ERROR_COLUMNS:
        values = [
            float(
                row.get("vertical_error_m")
                if field == "up_error_m" and row.get(field) in {None, ""}
                else row[field]
            )
            for row in matched
        ]
        metrics[field] = {
            "rmse": math.sqrt(math.fsum(value * value for value in values) / len(values)),
            "mae": math.fsum(abs(value) for value in values) / len(values),
            "median": _percentile_type7(values, 0.50),
            "p95": _percentile_type7(values, 0.95),
            "max": max(values),
        }
    return {
        "output_epoch_count": len(rows),
        "matched_epoch_count": len(matched),
        "unmatched_epoch_count": len(rows) - len(matched),
        "coverage_ratio": len(matched) / len(rows),
        "metrics": metrics,
        "roll_error": "NOT_AVAILABLE",
        "pitch_error": "NOT_AVAILABLE",
        "velocity_error": "NOT_AVAILABLE",
    }


def aggregate_row_level_independent(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Second implementation: explicit loops and rank interpolation."""

    matched_count = 0
    values_by_field: dict[str, list[float]] = {field: [] for field in ERROR_COLUMNS}
    for row in rows:
        if row.get("matched") is not True:
            continue
        matched_count += 1
        for field in ERROR_COLUMNS:
            value = (
                row.get("vertical_error_m")
                if field == "up_error_m" and row.get(field) in {None, ""}
                else row[field]
            )
            values_by_field[field].append(float(value))
    if matched_count == 0:
        raise EvaluatorContractError("Independent aggregate found no matched rows")
    metrics: dict[str, Any] = {}
    for field, values in values_by_field.items():
        total = 0.0
        square_total = 0.0
        for value in values:
            total += abs(value)
            square_total += value * value
        ordered = sorted(values)

        def quantile(probability: float) -> float:
            raw = probability * (len(ordered) - 1)
            left = int(raw)
            right = min(left + 1, len(ordered) - 1)
            return ordered[left] + (ordered[right] - ordered[left]) * (raw - left)

        metrics[field] = {
            "rmse": math.sqrt(square_total / matched_count),
            "mae": total / matched_count,
            "median": quantile(0.50),
            "p95": quantile(0.95),
            "max": ordered[-1],
        }
    return {
        "output_epoch_count": len(rows),
        "matched_epoch_count": matched_count,
        "unmatched_epoch_count": len(rows) - matched_count,
        "coverage_ratio": matched_count / len(rows),
        "metrics": metrics,
        "roll_error": "NOT_AVAILABLE",
        "pitch_error": "NOT_AVAILABLE",
        "velocity_error": "NOT_AVAILABLE",
    }


def crosscheck_aggregates(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> dict[str, Any]:
    mismatches: list[str] = []
    for field in ("output_epoch_count", "matched_epoch_count", "unmatched_epoch_count"):
        if primary.get(field) != secondary.get(field):
            mismatches.append(field)
    left_coverage = float(primary.get("coverage_ratio", -1.0))
    right_coverage = float(secondary.get("coverage_ratio", -1.0))
    if not math.isclose(
        left_coverage,
        right_coverage,
        abs_tol=absolute_tolerance,
        rel_tol=relative_tolerance,
    ):
        mismatches.append("coverage_ratio")
    for metric in ERROR_COLUMNS:
        for statistic in ("rmse", "mae", "median", "p95", "max"):
            left = float(primary["metrics"][metric][statistic])
            right = float(secondary["metrics"][metric][statistic])
            if not math.isclose(left, right, abs_tol=absolute_tolerance, rel_tol=relative_tolerance):
                mismatches.append(f"{metric}.{statistic}")
    return {
        "schema_version": "paper-rebuild-aggregate-crosscheck-v1",
        "absolute_tolerance": absolute_tolerance,
        "relative_tolerance": relative_tolerance,
        "mismatches": mismatches,
        "passed": not mismatches,
    }


def read_persisted_row_level(path: str | Path) -> list[dict[str, Any]]:
    """Read the frozen row-level artifact; aggregate implementations consume this, not transient rows."""

    source = Path(path).resolve(strict=True)
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise EvaluatorContractError("Persisted row-level artifact is empty")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        value = str(row.get("matched") or "").strip().casefold()
        if value not in {"true", "false"}:
            raise EvaluatorContractError("Persisted row-level matched flag is invalid")
        converted: dict[str, Any] = dict(row)
        converted["matched"] = value == "true"
        # V1 fixture compatibility: V2 reports signed up, while V1 persisted only
        # an absolute vertical field. New formal rows always contain up_error_m.
        if converted["matched"] and not converted.get("up_error_m") and converted.get("vertical_error_m"):
            converted["up_error_m"] = converted["vertical_error_m"]
        normalized.append(converted)
    return normalized


def evaluate_formal_output(
    solver_output_path: str | Path,
    reference_path: str | Path,
    window_contract_path: str | Path,
    evaluator_contract_path: str | Path,
    output_dir: str | Path,
    *,
    expected_output_sha256: str,
) -> dict[str, Any]:
    """Evaluate only after output hash freeze; unmatched rows are retained."""

    solver_path = Path(solver_output_path).resolve(strict=True)
    reference = Path(reference_path).resolve(strict=True)
    window_path = Path(window_contract_path).resolve(strict=True)
    evaluator_path = Path(evaluator_contract_path).resolve(strict=True)
    evaluator = load_frozen_evaluator(evaluator_path, require_ready=True)
    window = load_frozen_window(window_path)
    if sha256_file(reference) != evaluator["reference"]["sha256"]:
        raise EvaluatorContractError("Reference hash changed after evaluator freeze")
    output_hash = sha256_file(solver_path)
    if output_hash != expected_output_sha256:
        raise EvaluatorContractError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    solver_rows, _ = _read_rows(solver_path, SOLVER_REQUIRED_COLUMNS)
    reference_rows, reference_fields = _read_rows(reference, REFERENCE_REQUIRED_COLUMNS)
    reference_timing = derive_reference_timing_profile(reference_rows)
    max_gap_seconds = float(reference_timing["max_allowed_bracket_gap_seconds"])
    row_level = build_row_level_errors(
        solver_rows,
        reference_rows,
        source_time_origin_seconds=float(window["source_time_origin_seconds"]),
        max_gap_seconds=max_gap_seconds,
    )
    destination = Path(output_dir)
    if destination.exists():
        raise EvaluatorContractError("Fresh evaluator output directory already exists")
    destination.mkdir(parents=True, exist_ok=False)
    reference_audit_path = write_json_atomic(
        destination / "REFERENCE_OFFLINE_SCHEMA_AUDIT.json",
        {
            "schema_version": "paper-rebuild-reference-offline-schema-audit-v2",
            "protocol_id": EVALUATOR_PROTOCOL_ID_V2,
            "profile": EVALUATOR_PROFILE_V2,
            "path_alias": "<RAW_ROOT>",
            "relative_path": evaluator["reference"]["relative_path"],
            "sha256": evaluator["reference"]["sha256"],
            "trace_read_during_freeze": False,
            "trace_read_offline": True,
            "columns": reference_fields,
            "required_columns_present": True,
            "duplicate_timestamp_count": 0,
            "nonmonotonic_timestamp_count": 0,
            **reference_timing,
            "max_gap_formula": "max(3*median_dt,p99_dt+1e-9)",
            "reference_interval_percentile": "type7",
            "passed": True,
        },
    )
    row_path = write_csv_atomic(destination / "ROW_LEVEL_ERRORS.csv", list(row_level[0]), row_level)
    row_level_hash = sha256_file(row_path)
    primary = aggregate_row_level(read_persisted_row_level(row_path))
    secondary = aggregate_row_level_independent(read_persisted_row_level(row_path))
    aggregate_contract = evaluator["aggregate"]
    crosscheck = crosscheck_aggregates(
        primary,
        secondary,
        absolute_tolerance=float(aggregate_contract["crosscheck_absolute_tolerance"]),
        relative_tolerance=float(aggregate_contract["crosscheck_relative_tolerance"]),
    )
    if not crosscheck["passed"]:
        raise EvaluatorContractError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    if sha256_file(row_path) != row_level_hash or sha256_file(solver_path) != output_hash:
        raise EvaluatorContractError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    aggregate = {
        "schema_version": "paper-rebuild-aggregate-metrics-v2",
        "title": "BY2 clean normal relative-to-same-source-direct-reference descriptive results",
        "protocol_id": EVALUATOR_PROTOCOL_ID_V2,
        "profile": EVALUATOR_PROFILE_V2,
        "reference_wording": "same-source direct evaluation-only reference",
        "reference_independence_established": False,
        "independent_ground_truth": False,
        "position_same_source_mounting_caveat": True,
        "point_compensation_in_evaluator": False,
        "output_sha256": output_hash,
        "row_level_sha256": row_level_hash,
        **primary,
        "paper_performance_claim": False,
    }
    aggregate_json = write_json_atomic(destination / "AGGREGATE_METRICS.json", aggregate)
    flat_rows = []
    for metric, stats in primary["metrics"].items():
        flat_rows.append({"metric": metric, **stats})
    aggregate_csv = write_csv_atomic(
        destination / "AGGREGATE_METRICS.csv",
        ["metric", "rmse", "mae", "median", "p95", "max"],
        flat_rows,
    )
    cross_path = write_json_atomic(destination / "AGGREGATE_CROSSCHECK.json", crosscheck)
    write_csv_atomic(
        destination / "OUTPUT_HASH_MANIFEST.csv",
        ["output_role", "path_alias", "relative_path", "sha256", "frozen_before_evaluation"],
        [{
            "output_role": "current_solver_eval_nav",
            "path_alias": "<CURRENT_RUN_OUTPUT>",
            "relative_path": solver_path.name,
            "sha256": output_hash,
            "frozen_before_evaluation": True,
        }],
    )
    matching = {
        "schema_version": "paper-rebuild-matching-audit-v2",
        "protocol_id": EVALUATOR_PROTOCOL_ID_V2,
        "profile": EVALUATOR_PROFILE_V2,
        "matching_policy": "bracketed_linear_interpolation",
        "position_interpolation": "wgs84_blh_to_ecef_then_linear_interpolate",
        "yaw_interpolation": "unwrap_enu_degrees_then_linear_interpolate",
        "max_gap_formula": "max(3*median_dt,p99_dt+1e-9)",
        "max_gap_seconds": max_gap_seconds,
        "median_dt_seconds": reference_timing["median_dt_seconds"],
        "p99_dt_seconds": reference_timing["p99_dt_seconds"],
        "duplicate_solver_timestamp_policy": "fail",
        "duplicate_reference_timestamp_policy": "fail",
        "unmatched_epoch_policy": "retain_row_and_label_unmatched",
        "extrapolation_policy": "forbidden",
        "bracket_gap_policy": "reference_bracket_interval_lte_derived_max_gap",
        "output_epoch_count": len(row_level),
        "reference_epoch_count": len(reference_rows),
        "matched_epoch_count": primary["matched_epoch_count"],
        "unmatched_epoch_count": primary["unmatched_epoch_count"],
        "coverage_ratio": primary["coverage_ratio"],
        "alignment_applied": False,
        "time_offset_search_applied": False,
        "sign_or_axis_search_applied": False,
        "point_compensation_in_evaluator": False,
        "position_same_source_mounting_caveat": True,
        "independent_ground_truth": False,
        "epoch_deleted_for_metric": False,
        "passed": True,
    }
    write_json_atomic(destination / "MATCHING_AUDIT.json", matching)
    if sha256_file(row_path) != row_level_hash or sha256_file(solver_path) != output_hash:
        raise EvaluatorContractError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    write_read_ledger(
        destination / "EVALUATOR_ACTUAL_READ_LEDGER.csv",
        [
            {"read_order": 1, "path_alias": "<CURRENT_RUN_OUTPUT>", "relative_path": solver_path.name, "role": "current_solver_output", "sha256": output_hash, "reader_component": "paper_rebuild.evaluator"},
            {"read_order": 2, "path_alias": "<RAW_ROOT>", "relative_path": evaluator["reference"]["relative_path"], "role": "evaluation_only_trace", "sha256": sha256_file(reference), "reader_component": "paper_rebuild.evaluator"},
            {"read_order": 3, "path_alias": "<STAGE_PROTOCOL>", "relative_path": window_path.name, "role": "window_contract", "sha256": sha256_file(window_path), "reader_component": "paper_rebuild.evaluator"},
            {"read_order": 4, "path_alias": "<STAGE_PROTOCOL>", "relative_path": evaluator_path.name, "role": "evaluator_contract", "sha256": sha256_file(evaluator_path), "reader_component": "paper_rebuild.evaluator"},
        ],
        allowed_roles={"current_solver_output", "evaluation_only_trace", "window_contract", "evaluator_contract"},
    )
    return {
        "aggregate": aggregate,
        "crosscheck": crosscheck,
        "artifacts": {
            "row_level": str(row_path),
            "aggregate_json": str(aggregate_json),
            "aggregate_csv": str(aggregate_csv),
            "crosscheck": str(cross_path),
            "reference_offline_schema_audit": str(reference_audit_path),
        },
    }
