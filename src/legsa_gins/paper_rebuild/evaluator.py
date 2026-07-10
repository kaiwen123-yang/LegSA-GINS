"""Frozen, offline-only CLEAN1 evaluator with no alignment or result-driven edits."""

from __future__ import annotations

import bisect
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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
    "vertical_error_m",
    "position_3d_error_m",
    "yaw_error_deg",
)


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


def reference_yaw_enu_to_solver_ned_deg(value: float) -> float:
    return wrap_signed_deg(90.0 - value)


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
    reference_path: str | Path,
    output_dir: str | Path,
    *,
    reference_relative_path: str,
    expected_reference_sha256: str,
    reference_point_contract: Mapping[str, Any] | None = None,
    reference_frame_contract: Mapping[str, Any] | None = None,
    verified_source_hashes: Mapping[str, str] | None = None,
) -> EvaluatorFreeze:
    """Freeze from reference schema/cadence only, before any solver output is read."""

    # CLEAN1 has no independently proven active-source point or attitude-frame
    # schema.  Do not permit a caller to unlock evaluation by self-asserting
    # semantics around an otherwise valid raw hash.  A later authorized stage
    # must add a fixed, machine-validated source-role contract before this gate
    # can accept a proof object.
    if reference_point_contract is not None or reference_frame_contract is not None:
        raise EvaluatorContractError(
            "CLEAN1 evaluator source-contract proof injection is not authorized"
        )

    tracked_path = Path(tracked_contract_path).resolve(strict=True)
    base = load_yaml_mapping(tracked_path)
    if base.get("schema_version") != "paper_rebuild.evaluator_contract.v1":
        raise EvaluatorContractError("Tracked evaluator contract schema mismatch")
    forbidden = base.get("forbidden_postprocessing")
    if not isinstance(forbidden, Mapping) or any(value is not False for value in forbidden.values()):
        raise EvaluatorContractError("Tracked evaluator permits forbidden postprocessing")
    timestamp_contract = base.get("timestamps")
    if not isinstance(timestamp_contract, Mapping):
        raise EvaluatorContractError("Tracked evaluator timestamp contract is missing")
    expected_timestamp_fields = {
        "matching_policy": "nearest_neighbor",
        "max_gap_policy": "ceil_reference_max_positive_period_to_fixed_0p01_seconds",
        "duplicate_solver_timestamp_policy": "fail",
        "duplicate_reference_timestamp_policy": "fail",
        "unmatched_epoch_policy": "retain_row_and_label_unmatched",
        "extrapolation_policy": "forbidden",
        "first_last_extrapolation": "forbidden",
        "yaw_interpolation_policy": "none_nearest_neighbor_wrap_after_match",
        "trace_based_time_offset_search": False,
    }
    for field, expected in expected_timestamp_fields.items():
        if timestamp_contract.get(field) != expected:
            raise EvaluatorContractError(f"Tracked evaluator timestamp field mismatch: {field}")

    reference = Path(reference_path).resolve(strict=True)
    actual_hash = sha256_file(reference)
    if actual_hash != expected_reference_sha256:
        raise EvaluatorContractError("Evaluation-only reference hash mismatch")
    rows, fields = _read_rows(reference, REFERENCE_REQUIRED_COLUMNS)
    times = _strict_timestamps(rows, "time", "reference")
    intervals = [later - earlier for earlier, later in zip(times, times[1:])]
    maximum_interval = max(intervals)
    quantum = float(timestamp_contract.get("max_gap_ceiling_quantum_seconds") or 0.01)
    if quantum != 0.01:
        raise EvaluatorContractError("Evaluator max-gap ceiling quantum must remain 0.01 seconds")
    max_gap = math.ceil((maximum_interval - 1.0e-15) / quantum) * quantum
    if base.get("reference_wording") != "aligned evaluation-only reference" or base.get("reference_independence_established") is not False:
        raise EvaluatorContractError("Tracked evaluator reference wording/independence contract mismatch")
    frames = base.get("frames")
    if not isinstance(frames, Mapping) or frames.get("method_specific_conversion") is not False:
        raise EvaluatorContractError("Tracked evaluator frame contract is incomplete")
    if frames.get("reference_point_contract_proven") is not False or frames.get("reference_attitude_frame_contract_proven") is not False:
        raise EvaluatorContractError("Tracked evaluator may not predeclare unproven source contracts")
    aggregate = base.get("aggregate")
    if not isinstance(aggregate, Mapping) or aggregate.get("metrics") != ["rmse", "mae", "median", "p95", "max"]:
        raise EvaluatorContractError("Tracked evaluator aggregate metric contract mismatch")
    if float(aggregate.get("crosscheck_absolute_tolerance", -1.0)) != 1.0e-10 or float(
        aggregate.get("crosscheck_relative_tolerance", -1.0)
    ) != 1.0e-10:
        raise EvaluatorContractError("Tracked evaluator cross-check tolerance mismatch")
    point_ready, point_contract = _reference_point_ready(None, verified_source_hashes)
    frame_ready, frame_contract = _reference_frame_ready(None, verified_source_hashes)
    ready = point_ready and frame_ready

    frozen = dict(base)
    frozen["schema_version"] = "paper-rebuild-frozen-evaluator-contract-v1"
    frozen["tracked_contract_sha256"] = sha256_file(tracked_path)
    frozen["reference"] = {
        "path_alias": "<RAW_ROOT>",
        "relative_path": reference_relative_path,
        "sha256": actual_hash,
        "row_count": len(rows),
        "first_timestamp": times[0],
        "last_timestamp": times[-1],
        "max_positive_period_seconds": maximum_interval,
        "max_allowed_matching_gap_seconds": max_gap,
        "cadence_derivation_used_method_output": False,
        "metadata_ypr_frame": "ENU" if frame_ready else "NOT_PROVEN",
    }
    frozen["reference_point_contract"] = point_contract
    frozen["reference_point_contract_proven"] = point_ready
    frozen["reference_frame_contract"] = frame_contract
    frozen["reference_attitude_frame_contract_proven"] = frame_ready
    frozen["terminal_status"] = (
        "READY_FOR_OFFLINE_EVALUATION"
        if ready
        else "BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED"
    )
    frozen["formal_metrics_authorized"] = ready
    frozen["method_output_read_during_freeze"] = False

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    contract_path = destination / "EVALUATOR_CONTRACT.yaml"
    contract_path.write_text(_dump_yaml(frozen), encoding="utf-8")
    contract_hash = sha256_file(contract_path)
    (destination / "EVALUATOR_CONTRACT.sha256").write_text(
        f"{contract_hash}  EVALUATOR_CONTRACT.yaml\n", encoding="utf-8"
    )
    audit = {
        "schema_version": "paper-rebuild-reference-schema-audit-v1",
        "reference_wording": "aligned evaluation-only reference",
        "reference_independence_established": False,
        "columns": fields,
        "required_columns_present": True,
        "row_count": len(rows),
        "duplicate_timestamp_count": 0,
        "nonmonotonic_timestamp_count": 0,
        "timestamp_min": times[0],
        "timestamp_max": times[-1],
        "max_positive_period_seconds": maximum_interval,
        "max_allowed_matching_gap_seconds": max_gap,
        "yaw_frame": "ENU" if frame_ready else "NOT_PROVEN",
        "yaw_conversion": "wrap(90_deg-reference_yaw_ENU_deg)" if frame_ready else "NOT_AUTHORIZED",
        "roll_pitch_metric_supported": False,
        "velocity_metric_supported": False,
        "reference_point_contract_proven": point_ready,
        "reference_attitude_frame_contract_proven": frame_ready,
        "blocking_reasons": [
            reason
            for condition, reason in (
                (point_ready, "reference_point_identity_or_transform_not_proven"),
                (frame_ready, "reference_yaw_frame_semantics_not_proven"),
            )
            if not condition
        ],
        "formal_metrics_authorized": ready,
        "terminal_status": frozen["terminal_status"],
    }
    audit_path = write_json_atomic(destination / "REFERENCE_SCHEMA_AUDIT.json", audit)
    return EvaluatorFreeze(contract_path, contract_hash, audit_path, ready, frozen["terminal_status"])


def load_frozen_evaluator(path: str | Path, *, require_ready: bool = True) -> dict[str, Any]:
    payload = load_yaml_mapping(Path(path).resolve(strict=True))
    if payload.get("schema_version") != "paper-rebuild-frozen-evaluator-contract-v1":
        raise EvaluatorContractError("Frozen evaluator schema mismatch")
    if payload.get("method_output_read_during_freeze") is not False:
        raise EvaluatorContractError("Evaluator was not frozen before outputs")
    if require_ready and (
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
    sx, sy, sz = _ecef(solver_lat, solver_lon, solver_height)
    rx, ry, rz = _ecef(ref_lat, ref_lon, ref_height)
    dx, dy, dz = sx - rx, sy - ry, sz - rz
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


def _nearest_index(reference_times: Sequence[float], value: float) -> int | None:
    position = bisect.bisect_left(reference_times, value)
    candidates = []
    if position > 0:
        candidates.append(position - 1)
    if position < len(reference_times):
        candidates.append(position)
    if not candidates:
        return None
    return min(candidates, key=lambda index: (abs(reference_times[index] - value), reference_times[index]))


def build_row_level_errors(
    solver_rows: Sequence[Mapping[str, str]],
    reference_rows: Sequence[Mapping[str, str]],
    *,
    source_time_origin_seconds: float,
    max_gap_seconds: float,
) -> list[dict[str, Any]]:
    solver_times = _strict_timestamps(solver_rows, "time", "solver")
    reference_times = _strict_timestamps(reference_rows, "time", "reference")
    output: list[dict[str, Any]] = []
    for index, (solver, solver_time) in enumerate(zip(solver_rows, solver_times)):
        common_time = solver_time + source_time_origin_seconds
        ref_index = _nearest_index(reference_times, common_time)
        matched = False
        gap: float | str = ""
        row: dict[str, Any] = {
            "output_row_index": index,
            "solver_time": solver_time,
            "common_time": common_time,
            "reference_time": "",
            "matching_gap_seconds": "",
            "matched": False,
            "unmatched_reason": "outside_reference_extent_or_gap",
            "north_error_m": "",
            "east_error_m": "",
            "down_error_m": "",
            **{field: "" for field in ERROR_COLUMNS},
        }
        if ref_index is not None and reference_times[0] <= common_time <= reference_times[-1]:
            gap = abs(reference_times[ref_index] - common_time)
            if gap <= max_gap_seconds + 1.0e-12:
                reference = reference_rows[ref_index]
                north, east, down = _geodetic_delta_ned(
                    _float(solver, "lat_deg"),
                    _float(solver, "lon_deg"),
                    _float(solver, "height_m"),
                    _float(reference, "lat"),
                    _float(reference, "lon"),
                    _float(reference, "height"),
                )
                yaw_reference = reference_yaw_enu_to_solver_ned_deg(_float(reference, "yaw"))
                yaw_error = abs(wrap_signed_deg(_float(solver, "yaw_deg") - yaw_reference))
                row.update(
                    {
                        "reference_time": reference_times[ref_index],
                        "matching_gap_seconds": gap,
                        "matched": True,
                        "unmatched_reason": "",
                        "north_error_m": north,
                        "east_error_m": east,
                        "down_error_m": down,
                        "horizontal_position_error_m": math.hypot(north, east),
                        "vertical_error_m": abs(down),
                        "position_3d_error_m": math.sqrt(north * north + east * east + down * down),
                        "yaw_error_deg": yaw_error,
                    }
                )
                matched = True
        if not matched and gap != "":
            row["matching_gap_seconds"] = gap
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
        values = [float(row[field]) for row in matched]
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
            values_by_field[field].append(float(row[field]))
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
    reference_rows, _ = _read_rows(reference, REFERENCE_REQUIRED_COLUMNS)
    row_level = build_row_level_errors(
        solver_rows,
        reference_rows,
        source_time_origin_seconds=float(window["source_time_origin_seconds"]),
        max_gap_seconds=float(evaluator["reference"]["max_allowed_matching_gap_seconds"]),
    )
    destination = Path(output_dir)
    if destination.exists():
        raise EvaluatorContractError("Fresh evaluator output directory already exists")
    destination.mkdir(parents=True, exist_ok=False)
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
        "schema_version": "paper-rebuild-aggregate-metrics-v1",
        "title": "BY2 clean normal relative-to-evaluation-reference descriptive results",
        "reference_wording": "aligned evaluation-only reference",
        "reference_independence_established": False,
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
        "schema_version": "paper-rebuild-matching-audit-v1",
        "matching_policy": "nearest_neighbor",
        "max_gap_seconds": evaluator["reference"]["max_allowed_matching_gap_seconds"],
        "output_epoch_count": len(row_level),
        "reference_epoch_count": len(reference_rows),
        "matched_epoch_count": primary["matched_epoch_count"],
        "unmatched_epoch_count": primary["unmatched_epoch_count"],
        "coverage_ratio": primary["coverage_ratio"],
        "alignment_applied": False,
        "time_offset_search_applied": False,
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
        },
    }
