"""CLEAN1R1C deterministic kick-event alignment and common-window freeze.

The physical kick is an input-domain synchronization anchor.  This module
never reads trace, solver output, or performance metrics and never searches
over offsets.  Go2 body-state parsing and the historical maintained kick
candidate are imported as hash-recorded source dependencies; the formal
CLEAN1R1C selection itself follows the frozen robust jerk-score contract.
"""

from __future__ import annotations

import csv
import inspect
import json
import math
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from legsa_gins.datasets.by2.go2_body_state_parser import (
    parse_go2_body_state_text,
    write_go2_body_state_csv,
)
from legsa_gins.datasets.by2.unitree_imu_semantics import accel_norm, gyro_norm
from legsa_gins.time_alignment.event_normalization import detect_go2_kick_event

from .manifest import sha256_file, write_json_atomic


STAGE_ID = "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
PROTOCOL_ID = "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"
ALIGNMENT_MODE = "event_normalized_kick"
FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS = 0.0
MAINTAINED_DEFAULT_ZSCORE_THRESHOLD = 6.0
NORMALIZATION_BASELINE_MAX_SAMPLES = 1000
ROBUST_MAD_SCALE = 1.4826
NUMERICAL_SCALE_FLOOR = 1.0e-12

MAINTAINED_SOURCE_PATHS = (
    "src/legsa_gins/datasets/by2/go2_body_state_parser.py",
    "src/legsa_gins/datasets/by2/unitree_imu_semantics.py",
    "src/legsa_gins/time_alignment/event_normalization.py",
    "src/legsa_gins/time_alignment/time_domain_audit.py",
)


class KickAlignmentError(RuntimeError):
    """The frozen kick or common-window contract could not be reproduced."""


@dataclass(frozen=True)
class KickDiagnosticRow:
    sample_index: int
    timestamp: float
    dt_seconds: float
    acc_norm_mps2: float
    gyro_norm_radps: float
    acc_jerk_mps3: float
    gyro_jerk_radps2: float
    acc_jerk_robust_z: float
    gyro_jerk_robust_z: float
    kick_score: float
    selected: bool
    in_normalization_baseline: bool


@dataclass(frozen=True)
class KickDetection:
    t_go2_kick: float
    kick_score: float
    first_mode_or_gait_change_time: float
    event_segment_row_count: int
    derivative_sample_count: int
    normalization_sample_count: int
    acc_jerk_median: float
    acc_jerk_mad: float
    acc_jerk_scale: float
    gyro_jerk_median: float
    gyro_jerk_mad: float
    gyro_jerk_scale: float
    maintained_candidate_time: float
    maintained_candidate_score: float
    maintained_candidate_status: str
    diagnostics: tuple[KickDiagnosticRow, ...]


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _mode_gait_key(row: Mapping[str, Any]) -> tuple[Any, Any]:
    return row.get("mode"), row.get("gait_type")


def _median_mad(values: Sequence[float]) -> tuple[float, float, float]:
    if not values:
        raise KickAlignmentError("Kick normalization has no valid derivative samples")
    median = float(statistics.median(values))
    mad = float(statistics.median(abs(value - median) for value in values))
    scale = max(ROBUST_MAD_SCALE * mad, NUMERICAL_SCALE_FLOOR)
    return median, mad, scale


def _maintained_defaults() -> tuple[float, float]:
    signature = inspect.signature(detect_go2_kick_event)
    zscore = signature.parameters["zscore_threshold"].default
    min_score = signature.parameters["min_score"].default
    if float(zscore) != MAINTAINED_DEFAULT_ZSCORE_THRESHOLD:
        raise KickAlignmentError("Maintained kick z-score default drifted from the frozen contract")
    return float(zscore), float(min_score)


def _maintained_candidate(
    rows: list[dict[str, Any]], output_path: str | Path
) -> dict[str, Any]:
    """Run the maintained candidate on an attempt-owned derived CSV."""

    _maintained_defaults()
    candidate_csv = Path(output_path)
    candidate_csv.parent.mkdir(parents=True, exist_ok=True)
    write_go2_body_state_csv(rows, candidate_csv)
    return detect_go2_kick_event(candidate_csv)


def detect_frozen_go2_kick(
    go2_body_text: str | Path,
    *,
    maintained_candidate_output_path: str | Path,
) -> KickDetection:
    """Detect the frozen physical kick from hash-locked Go2 body-state text.

    The initial event segment ends immediately before the first mode/gait
    transition.  Robust normalization uses at most the first 1000 valid
    derivative samples in that segment.  Ties are resolved by earliest time.
    """

    rows = parse_go2_body_state_text(go2_body_text)
    valid: list[dict[str, Any]] = []
    for row in rows:
        timestamp = _finite_float(row.get("timestamp"))
        if timestamp is None:
            continue
        values = (
            _finite_float(row.get("acc_x")),
            _finite_float(row.get("acc_y")),
            _finite_float(row.get("acc_z")),
            _finite_float(row.get("gyro_x")),
            _finite_float(row.get("gyro_y")),
            _finite_float(row.get("gyro_z")),
        )
        if any(value is None for value in values):
            continue
        valid.append(row)
    if len(valid) < 3:
        raise KickAlignmentError("Go2 source has fewer than three valid IMU rows")

    initial_key = _mode_gait_key(valid[0])
    change_index: int | None = None
    for index, row in enumerate(valid[1:], start=1):
        if _mode_gait_key(row) != initial_key:
            change_index = index
            break
    if change_index is None or change_index < 3:
        raise KickAlignmentError("First Go2 mode/gait transition does not close a usable initial event segment")
    event_rows = valid[:change_index]
    change_time = _finite_float(valid[change_index].get("timestamp"))
    if change_time is None:
        raise KickAlignmentError("First Go2 mode/gait transition has no finite timestamp")

    raw_samples: list[dict[str, float | int]] = []
    previous = event_rows[0]
    previous_time = float(previous["timestamp"])
    previous_acc = accel_norm(previous)
    previous_gyro = gyro_norm(previous)
    for row_index, row in enumerate(event_rows[1:], start=1):
        timestamp = float(row["timestamp"])
        dt = timestamp - previous_time
        current_acc = accel_norm(row)
        current_gyro = gyro_norm(row)
        if dt > 0.0 and math.isfinite(dt):
            raw_samples.append(
                {
                    "sample_index": row_index,
                    "timestamp": timestamp,
                    "dt_seconds": dt,
                    "acc_norm_mps2": current_acc,
                    "gyro_norm_radps": current_gyro,
                    "acc_jerk_mps3": abs(current_acc - previous_acc) / dt,
                    "gyro_jerk_radps2": abs(current_gyro - previous_gyro) / dt,
                }
            )
        previous = row
        previous_time = timestamp
        previous_acc = current_acc
        previous_gyro = current_gyro
    if not raw_samples:
        raise KickAlignmentError("Go2 initial event segment has no positive-dt derivative samples")

    baseline = raw_samples[:NORMALIZATION_BASELINE_MAX_SAMPLES]
    acc_median, acc_mad, acc_scale = _median_mad(
        [float(row["acc_jerk_mps3"]) for row in baseline]
    )
    gyro_median, gyro_mad, gyro_scale = _median_mad(
        [float(row["gyro_jerk_radps2"]) for row in baseline]
    )

    scored: list[dict[str, float | int]] = []
    for raw in raw_samples:
        acc_z = max(0.0, (float(raw["acc_jerk_mps3"]) - acc_median) / acc_scale)
        gyro_z = max(0.0, (float(raw["gyro_jerk_radps2"]) - gyro_median) / gyro_scale)
        scored.append({**raw, "acc_jerk_robust_z": acc_z, "gyro_jerk_robust_z": gyro_z, "kick_score": acc_z + gyro_z})
    selected_index = max(range(len(scored)), key=lambda index: (float(scored[index]["kick_score"]), -index))
    selected = scored[selected_index]
    score = float(selected["kick_score"])
    if score < MAINTAINED_DEFAULT_ZSCORE_THRESHOLD:
        raise KickAlignmentError("Frozen robust kick score is below the maintained z-score threshold")

    # The maintained cross-check is bounded to the same initial event segment;
    # later locomotion is not allowed to replace the physical kick candidate.
    maintained = _maintained_candidate(event_rows, maintained_candidate_output_path)
    maintained_time = _finite_float(maintained.get("go2_kick_raw_time"))
    maintained_score = _finite_float(maintained.get("kick_score"))
    maintained_status = str(maintained.get("evidence_status") or "")
    if maintained_time is None or maintained_score is None or maintained_status != "detected":
        raise KickAlignmentError("Maintained detect_go2_kick_event did not produce a detected candidate")

    diagnostics = tuple(
        KickDiagnosticRow(
            sample_index=int(row["sample_index"]),
            timestamp=float(row["timestamp"]),
            dt_seconds=float(row["dt_seconds"]),
            acc_norm_mps2=float(row["acc_norm_mps2"]),
            gyro_norm_radps=float(row["gyro_norm_radps"]),
            acc_jerk_mps3=float(row["acc_jerk_mps3"]),
            gyro_jerk_radps2=float(row["gyro_jerk_radps2"]),
            acc_jerk_robust_z=float(row["acc_jerk_robust_z"]),
            gyro_jerk_robust_z=float(row["gyro_jerk_robust_z"]),
            kick_score=float(row["kick_score"]),
            selected=index == selected_index,
            in_normalization_baseline=index < len(baseline),
        )
        for index, row in enumerate(scored)
    )
    return KickDetection(
        t_go2_kick=float(selected["timestamp"]),
        kick_score=score,
        first_mode_or_gait_change_time=change_time,
        event_segment_row_count=len(event_rows),
        derivative_sample_count=len(raw_samples),
        normalization_sample_count=len(baseline),
        acc_jerk_median=acc_median,
        acc_jerk_mad=acc_mad,
        acc_jerk_scale=acc_scale,
        gyro_jerk_median=gyro_median,
        gyro_jerk_mad=gyro_mad,
        gyro_jerk_scale=gyro_scale,
        maintained_candidate_time=maintained_time,
        maintained_candidate_score=maintained_score,
        maintained_candidate_status=maintained_status,
        diagnostics=diagnostics,
    )


def _strict_finite_times(values: Sequence[float], role: str) -> list[float]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if len(finite) < 2:
        raise KickAlignmentError(f"{role} has fewer than two finite timestamps")
    if any(later <= earlier for earlier, later in zip(finite, finite[1:])):
        raise KickAlignmentError(f"{role} timestamps are not strictly increasing")
    return finite


def build_kick_aligned_common_window(
    detection: KickDetection,
    *,
    propagation_imu_timestamps: Sequence[float],
    core_gnss_timestamps: Sequence[float],
    dual_yaw_valid_timestamps: Sequence[float],
    source_time_origin_seconds: float,
    fixed_event_alignment_offset: float = FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS,
) -> dict[str, Any]:
    """Freeze the V2 common interval without optional-stream start gating."""

    if fixed_event_alignment_offset != FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS:
        raise KickAlignmentError("CLEAN1R1C event offset is frozen at exactly 0.0 seconds")
    if not math.isfinite(source_time_origin_seconds):
        raise KickAlignmentError("Source time origin is not finite")
    imu = _strict_finite_times(propagation_imu_timestamps, "propagation_imu")
    gnss = _strict_finite_times(core_gnss_timestamps, "core_gnss")
    dual_yaw = _strict_finite_times(dual_yaw_valid_timestamps, "dual_yaw")
    mapped_kick_absolute = detection.t_go2_kick + fixed_event_alignment_offset
    mapped_kick_provider_time = mapped_kick_absolute - source_time_origin_seconds
    first_after = next((timestamp for timestamp in gnss if timestamp >= mapped_kick_provider_time), None)
    if first_after is None:
        raise KickAlignmentError("No valid core GNSS epoch exists at or after the mapped kick")
    if not (imu[0] <= first_after <= imu[-1]):
        raise KickAlignmentError("Propagation IMU is unavailable at the first post-kick GNSS epoch")
    if not any(math.isclose(value, first_after, rel_tol=0.0, abs_tol=1.0e-9) for value in dual_yaw):
        raise KickAlignmentError("Dual-yaw provider is unavailable at the common start")
    end = min(imu[-1], gnss[-1])
    if end <= first_after:
        raise KickAlignmentError("Kick-aligned common interval is empty")
    return {
        "alignment_mode": ALIGNMENT_MODE,
        "t_go2_kick": detection.t_go2_kick,
        "fixed_event_alignment_offset": fixed_event_alignment_offset,
        "mapped_kick_absolute_time": mapped_kick_absolute,
        "mapped_kick_provider_time": mapped_kick_provider_time,
        "first_valid_gnss_after_kick": first_after,
        "t_start": first_after,
        "t_end": end,
        "duration_seconds": end - first_after,
        "source_time_origin_seconds": float(source_time_origin_seconds),
        "trace_used_for_alignment": False,
        "offset_search_performed": False,
        "method_specific_shift": False,
        "optional_streams_delay_start": False,
        "internal_dropout_preserved": True,
    }


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False)


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(_dump_yaml(payload), encoding="utf-8")


def freeze_kick_alignment_contracts(
    go2_body_text: str | Path,
    *,
    propagation_imu_timestamps: Sequence[float],
    core_gnss_timestamps: Sequence[float],
    dual_yaw_valid_timestamps: Sequence[float],
    source_time_origin_seconds: float,
    output_dir: str | Path,
    fixed_event_alignment_offset: float = FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS,
    go2_source_alias: str = "<RAW_ROOT>",
    go2_source_relative_path: str = "BY2_BY3/2026-03-06/高层数据/by2.txt",
) -> dict[str, Any]:
    """Detect, validate, and emit the four required CLEAN1R1C artifacts."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    maintained_candidate_path = destination / "GO2_INITIAL_EVENT_SEGMENT.csv"
    detection = detect_frozen_go2_kick(
        go2_body_text,
        maintained_candidate_output_path=maintained_candidate_path,
    )
    window = build_kick_aligned_common_window(
        detection,
        propagation_imu_timestamps=propagation_imu_timestamps,
        core_gnss_timestamps=core_gnss_timestamps,
        dual_yaw_valid_timestamps=dual_yaw_valid_timestamps,
        source_time_origin_seconds=source_time_origin_seconds,
        fixed_event_alignment_offset=fixed_event_alignment_offset,
    )
    code_root = Path(__file__).resolve().parents[3]
    source_hashes = {
        relative: sha256_file(code_root / relative) for relative in MAINTAINED_SOURCE_PATHS
    }
    zscore_default, min_score_default = _maintained_defaults()
    source_contract = {
        "go2_source_alias": go2_source_alias,
        "go2_source_relative_path": go2_source_relative_path,
        "go2_source_sha256": sha256_file(go2_body_text),
        "maintained_source_hashes": source_hashes,
        "maintained_detect_go2_kick_event_defaults": {
            "zscore_threshold": zscore_default,
            "min_score": min_score_default,
        },
    }
    alignment_contract = {
        "schema_version": "paper-rebuild-clean1r1c-kick-alignment-v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "protocol_id": PROTOCOL_ID,
        "alignment_mode": ALIGNMENT_MODE,
        "event_segment_end": "first_mode_or_gait_change_exclusive",
        "event_score": "max(0,z_acc_jerk)+max(0,z_gyro_jerk)",
        "normalization": {
            "samples": "first_1000_valid_derivative_samples_or_all_if_fewer",
            "center": "median",
            "scale": "max(1.4826*MAD,1e-12)",
            "required_score": MAINTAINED_DEFAULT_ZSCORE_THRESHOLD,
        },
        "absolute_mapping": "t_abs_go2=t_go2+fixed_event_alignment_offset",
        "fixed_event_alignment_offset": fixed_event_alignment_offset,
        "trace_used_for_alignment": False,
        "offset_search_performed": False,
        "method_specific_shift": False,
        **source_contract,
    }
    _write_yaml(destination / "KICK_EVENT_ALIGNMENT_CONTRACT.yaml", alignment_contract)

    diagnostic_rows = [asdict(row) for row in detection.diagnostics]
    diagnostic_path = destination / "KICK_EVENT_DIAGNOSTIC.csv"
    with diagnostic_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(diagnostic_rows[0]))
        writer.writeheader()
        writer.writerows(diagnostic_rows)

    detection_payload = {key: value for key, value in asdict(detection).items() if key != "diagnostics"}
    report = {
        "schema_version": "paper-rebuild-clean1r1c-kick-alignment-report-v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "protocol_id": PROTOCOL_ID,
        **detection_payload,
        "robust_jerk_max_time": detection.t_go2_kick,
        "robust_jerk_max_score": detection.kick_score,
        "maintained_candidate_scope": "initial_event_segment_only",
        "maintained_candidate_derived_csv": "GO2_INITIAL_EVENT_SEGMENT.csv",
        "maintained_candidate_derived_csv_hash": sha256_file(maintained_candidate_path),
        **window,
        **source_contract,
        "kick_alignment_pass": True,
    }
    report_path = write_json_atomic(destination / "KICK_EVENT_ALIGNMENT_REPORT.json", report)
    common_start = {
        "schema_version": "paper-rebuild-clean1r1c-common-start-v1",
        "stage_id": STAGE_ID,
        "case_id": CASE_ID,
        "protocol_id": PROTOCOL_ID,
        "policy": "first_valid_core_gnss_epoch_at_or_after_mapped_kick",
        "t_start_formula": "first(valid_core_gnss_time >= mapped_kick_provider_time)",
        "t_end_formula": "min(propagation_imu_last_valid,core_gnss_last_valid)",
        **window,
        "dual_yaw_available_at_start": True,
        "optional_streams_begin_when_available": True,
        "trace_or_method_output_used_to_select_window": False,
    }
    _write_yaml(destination / "COMMON_START_TIME_CONTRACT.yaml", common_start)
    return {
        **window,
        "kick_score": detection.kick_score,
        "kick_alignment_report_hash": sha256_file(report_path),
        "kick_alignment_contract_hash": sha256_file(destination / "KICK_EVENT_ALIGNMENT_CONTRACT.yaml"),
        "kick_diagnostic_hash": sha256_file(diagnostic_path),
        "maintained_candidate_derived_csv_hash": sha256_file(maintained_candidate_path),
        "common_start_contract_hash": sha256_file(destination / "COMMON_START_TIME_CONTRACT.yaml"),
    }


def build_kick_aligned_contract(
    go2_source: str | Path,
    gnss_runtime_input: str | Path,
    propagation_imu_input: str | Path,
    output_dir: str | Path,
    source_time_origin_seconds: float,
    fixed_event_alignment_offset: float = FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS,
) -> dict[str, Any]:
    """Integration entrypoint using raw Go2 plus formal IMU/GNSS inputs.

    The formal GNSS validity columns are ``position_valid`` (15) and
    ``dual_yaw_valid`` (17).  The first position-valid post-kick row is not
    shifted to accommodate optional providers; dual yaw must already be valid.
    Raw Go2 timestamps are used only for kick detection.  The common end is
    computed from the generated seven-column propagation IMU and core GNSS.
    """

    if fixed_event_alignment_offset != FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS:
        raise KickAlignmentError("CLEAN1R1C event offset is frozen at exactly 0.0 seconds")
    propagation_times: list[float] = []
    with Path(propagation_imu_input).open("r", encoding="utf-8", errors="strict") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            fields = stripped.split()
            if len(fields) != 7:
                raise KickAlignmentError(
                    f"Propagation IMU input must contain 7 columns at line {number}"
                )
            timestamp = _finite_float(fields[0])
            if timestamp is None:
                raise KickAlignmentError(f"Propagation IMU time is invalid at line {number}")
            propagation_times.append(timestamp)
    core_gnss_times: list[float] = []
    dual_yaw_times: list[float] = []
    with Path(gnss_runtime_input).open("r", encoding="utf-8", errors="strict") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            fields = stripped.split()
            if len(fields) != 18:
                raise KickAlignmentError(
                    f"Formal GNSS input must contain 18 columns at line {number}"
                )
            timestamp = _finite_float(fields[0])
            if timestamp is None:
                raise KickAlignmentError(f"Formal GNSS time is invalid at line {number}")
            try:
                position_valid = int(fields[15]) == 1
                dual_yaw_valid = int(fields[17]) == 1
            except ValueError as exc:
                raise KickAlignmentError(
                    f"Formal GNSS validity is invalid at line {number}"
                ) from exc
            if position_valid:
                core_gnss_times.append(timestamp)
            if dual_yaw_valid:
                dual_yaw_times.append(timestamp)
    if len(dual_yaw_times) < 2:
        raise KickAlignmentError("Formal GNSS input has fewer than two dual-yaw-valid epochs")
    result = freeze_kick_alignment_contracts(
        go2_source,
        propagation_imu_timestamps=propagation_times,
        core_gnss_timestamps=core_gnss_times,
        dual_yaw_valid_timestamps=dual_yaw_times,
        source_time_origin_seconds=source_time_origin_seconds,
        output_dir=output_dir,
        fixed_event_alignment_offset=fixed_event_alignment_offset,
    )
    return {
        **result,
        "gnss_runtime_input_hash": sha256_file(gnss_runtime_input),
        "propagation_imu_input_hash": sha256_file(propagation_imu_input),
        "propagation_imu_epoch_count": len(propagation_times),
        "gnss_position_valid_epoch_count": len(core_gnss_times),
        "dual_yaw_valid_epoch_count": len(dual_yaw_times),
    }
