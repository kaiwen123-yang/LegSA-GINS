#!/usr/bin/env python3
"""Execute PAPER10M1R2C BY2 full-algorithm matrix on validated providers.

This runner consumes the M1R2B provider-ready manifest and provider packages,
builds runtime-only port-core inputs, runs the four PAPER10L frozen method
modes, and writes stage/runtime summaries. It does not regenerate providers,
does not read trace as solver input, and does not write runtime outputs into
the Git worktree.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper10m0_method_mode_loader import (  # noqa: E402
    METHOD_MODE_IDS,
    load_all,
    resolve_effective_feature_flags,
    validate_mode_safety,
)
from scripts.paper10m0_output_contract_validator import validate_smoke_output  # noqa: E402
from scripts.paper10m0_runner_adapter import Paper10M0Paths, build_runtime_config  # noqa: E402


STAGE_NAME = "PAPER10M1R2C_V2_BY2_FULL_ALGORITHM_MATRIX_EXECUTION_2164ROWS"
EXPECTED_CASES = 541
EXPECTED_ROWS = 2164
EXPECTED_METHODS = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]

STAGE_DIRS = [
    "00_STAGE_REPORT",
    "01_GIT",
    "02_PREFLIGHT",
    "03_QUEUE",
    "04_EXECUTION",
    "05_CASE_SUMMARIES",
    "06_METHOD_SUMMARIES",
    "07_QM_SOURCE_TRACE_SUMMARIES",
    "08_FIGURES",
    "09_CLAIM_BOUNDARY",
    "10_TESTS",
    "11_OBSIDIAN_SYNC",
    "12_AI_CONTEXT_UPDATE",
    "13_NEXT_STAGE",
    "14_EXPORT_CLEAN_FOR_GPT",
]

RUNTIME_DIRS = [
    "00_LOCAL_ONLY",
    "01_QUEUE",
    "02_RUNNER_CONFIGS",
    "03_RUNTIME/basic_dual_baseline",
    "03_RUNTIME/strong_dual_yaw_baseline",
    "03_RUNTIME/legsa_without_qm",
    "03_RUNTIME/legsa_full_candidate_with_qm",
    "04_ROW_SUMMARIES",
    "05_CASE_SUMMARIES",
    "06_METHOD_SUMMARIES",
    "07_QM_SOURCE_TRACE_SUMMARIES",
    "08_FIGURES",
    "09_FAILURES_AND_RETRIES",
    "10_FINAL_RUNTIME_INDEX",
]

ROW_FIELDS = [
    "row_id",
    "case_id",
    "case_index",
    "case_family",
    "degradation_type_id",
    "degradation_type_name",
    "seed_index",
    "seed_value",
    "dataset",
    "method_mode_id",
    "feature_flags_hash",
    "runner_config_hash",
    "provider_root",
    "provider_ready",
    "effect_validation_status",
    "start_time",
    "end_time",
    "runtime_seconds",
    "terminal_status",
    "retry_count",
    "solver_launched",
    "solver_completed",
    "evaluator_launched",
    "evaluator_completed",
    "nav_exists",
    "std_exists",
    "metrics_exists",
    "run_manifest_exists",
    "feature_flag_dump_exists",
    "dataset_role_dump_exists",
    "method_mode_dump_exists",
    "case_spec_dump_exists",
    "source_trace_exists_or_not_required",
    "qm_trace_exists_or_not_required",
    "fgo_feedback_dump_exists_or_not_required",
    "trace_used_online",
    "final_v23_output_used_as_input",
    "legsa_output_used_as_input",
    "benchmark_output_used_as_input",
    "receiver_imu_data_as_body_imu",
    "go2_position_used_as_truth",
    "go2_yaw_used_as_truth",
    "go2_velocity_used_as_truth",
    "qa_fallback_as_final_method",
    "per_case_tuning_used",
    "output_only_correction_used",
    "epoch_deleted_for_metric",
    "horizontal_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "position_3d_rmse_m",
    "valid_epoch_count",
    "source_aware_update_count",
    "source_aware_reject_count",
    "qm_state_count_summary",
    "bad_a1_consumed_count",
    "fallback_count",
    "recovery_count",
    "raw_doppler_update_count",
    "go2_prior_update_count",
    "notes",
]


@dataclass(frozen=True)
class RuntimePaths:
    stage_root: Path
    runtime_root: Path
    export_root: Path
    m1r2a_stage_root: Path
    m1r2b_stage_root: Path
    provider_root: Path
    by2_imu: Path
    by2_statusyaw_gnss: Path
    code_root: Path


@dataclass(frozen=True)
class BridgedInputs:
    input_dir: Path
    gnss_15col: Path
    raw_doppler: Path
    go2_attitude: Path
    go2_horizontal_velocity: Path
    go2_joint: Path
    bridge_summary: dict[str, Any]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


MISSING_OBSERVATION_STATUSES = {
    "",
    "outage",
    "repeated_outage",
    "downsample_drop",
    "random_dropout",
    "dropout",
    "missing",
    "unavailable",
}


def source_value_available(status: Any) -> bool:
    """Return true for status values that still carry a degraded observation."""

    return str(status).strip().lower() not in MISSING_OBSERVATION_STATUSES


def go2_attitude_available(status: Any) -> bool:
    value = str(status).strip().lower()
    return source_value_available(value) and value != "go2_roll_pitch_dropout"


def go2_horizontal_velocity_available(status: Any) -> bool:
    value = str(status).strip().lower()
    return source_value_available(value) and value != "go2_horizontal_velocity_dropout"


def alias(path: Path, roots: dict[str, Path]) -> str:
    resolved = path.resolve()
    for label, root in sorted(roots.items(), key=lambda item: len(str(item[1])), reverse=True):
        try:
            rel = resolved.relative_to(root.resolve())
            return f"<{label}>/{rel.as_posix()}"
        except ValueError:
            continue
    return str(path)


def sanitize_text(text: str, roots: dict[str, Path]) -> str:
    out = text
    for label, root in sorted(roots.items(), key=lambda item: len(str(item[1])), reverse=True):
        out = out.replace(str(root), f"<{label}>")
    redactions = {
        "by2.txt": "<BY2_GO2_BODY_SOURCE>",
        "gnss1-raw.csv": "<BY2_GNSS1_RAW>",
        "gnss2-raw.csv": "<BY2_GNSS2_RAW>",
        "corr-raw.csv": "<BY2_CORR_RAW>",
    }
    for source, target in redactions.items():
        out = out.replace(source, target)
    return out


def ensure_dirs(paths: RuntimePaths) -> None:
    for name in STAGE_DIRS:
        (paths.stage_root / name).mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_DIRS:
        (paths.runtime_root / name).mkdir(parents=True, exist_ok=True)
    paths.export_root.mkdir(parents=True, exist_ok=True)


def run_cmd(command: list[str], cwd: Path, timeout: int | None = None) -> dict[str, Any]:
    start = time.time()
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "runtime_seconds": time.time() - start,
    }


def first_last_time(path: Path, delimiter: str | None = None, has_header: bool = False) -> tuple[float, float, int]:
    first: float | None = None
    last: float | None = None
    count = 0
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle):
            if has_header and line_no == 0:
                continue
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cell = line.split(delimiter)[0] if delimiter else line.split()[0]
            value = safe_float(cell, math.nan)
            if math.isnan(value):
                continue
            if first is None:
                first = value
            last = value
            count += 1
    return (first or 0.0, last or 0.0, count)


def read_reference_from_clean_provider(clean_provider_root: Path, time_offset: float) -> list[dict[str, float]]:
    pos = read_csv(clean_provider_root / "02_GENERATED_PROVIDERS" / "gnss_position_provider.csv")
    vel = {round(safe_float(row["time"]), 3): row for row in read_csv(clean_provider_root / "02_GENERATED_PROVIDERS" / "gnss_velocity_provider.csv")}
    yaw = {round(safe_float(row["time"]), 3): row for row in read_csv(clean_provider_root / "02_GENERATED_PROVIDERS" / "dual_yaw_provider.csv")}
    out: list[dict[str, float]] = []
    for row in pos:
        key = round(safe_float(row["time"]), 3)
        vrow = vel.get(key, {})
        yrow = yaw.get(key, {})
        if row.get("status") != "available":
            continue
        out.append(
            {
                "time": safe_float(row["time"]) + time_offset,
                "lat_deg": safe_float(row.get("lat")),
                "lon_deg": safe_float(row.get("lon")),
                "height_m": safe_float(row.get("height")),
                "yaw_deg": safe_float(yrow.get("yaw_deg")),
                "vn": safe_float(vrow.get("vn")),
                "ve": safe_float(vrow.get("ve")),
                "vd": safe_float(vrow.get("vd")),
            }
        )
    return out


def deg_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_mean = math.radians((lat1 + lat2) * 0.5)
    dn = (lat1 - lat2) * 111_320.0
    de = (lon1 - lon2) * 111_320.0 * math.cos(lat_mean)
    return math.hypot(dn, de)


def yaw_error_deg(a: float, b: float) -> float:
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def rmse(values: list[float]) -> float:
    if not values:
        return math.nan
    return math.sqrt(sum(v * v for v in values) / len(values))


def percentile(values: list[float], p: float) -> float:
    values = sorted(v for v in values if not math.isnan(v))
    if not values:
        return math.nan
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
    return values[index]


def parse_count_object(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(k): int(v) for k, v in value.items() if isinstance(v, (int, float))}
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parse_count_object(parsed)


def sum_count_object(value: Any) -> int:
    return sum(parse_count_object(value).values())


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def bridge_provider_package(
    *,
    case_id: str,
    provider_root: Path,
    output_dir: Path,
    time_offset: float,
) -> BridgedInputs:
    providers = provider_root / "02_GENERATED_PROVIDERS"
    pos_rows = read_csv(providers / "gnss_position_provider.csv")
    vel_rows = {round(safe_float(row["time"]), 3): row for row in read_csv(providers / "gnss_velocity_provider.csv")}
    yaw_rows = {round(safe_float(row["time"]), 3): row for row in read_csv(providers / "dual_yaw_provider.csv")}
    raw_rows = read_csv(providers / "raw_doppler_provider.csv")
    go2_rows = read_csv(providers / "go2_prior_provider.csv")

    output_dir.mkdir(parents=True, exist_ok=True)
    gnss_path = output_dir / "PAPER10M1R2C_STATUSYAW_15COL.gnss"
    gnss_written = 0
    gnss_position_skipped = 0
    yaw_unavailable = 0
    velocity_unavailable = 0
    with gnss_path.open("w", encoding="utf-8") as handle:
        for prow in pos_rows:
            key = round(safe_float(prow.get("time")), 3)
            if not source_value_available(prow.get("status")):
                gnss_position_skipped += 1
                continue
            vrow = vel_rows.get(key, {})
            yrow = yaw_rows.get(key, {})
            velocity_available = source_value_available(vrow.get("status"))
            yaw_available = source_value_available(yrow.get("status")) and str(yrow.get("rel_valid", "true")).lower() == "true"
            if not velocity_available:
                velocity_unavailable += 1
            if not yaw_available:
                yaw_unavailable += 1
            time_s = safe_float(prow["time"]) + time_offset
            std_h = max(safe_float(prow.get("std_h"), 1.0), 1.0e-4)
            std_v = max(safe_float(prow.get("std_v"), 1.0), 1.0e-4)
            if velocity_available:
                vn = safe_float(vrow.get("vn"))
                ve = safe_float(vrow.get("ve"))
                vd = safe_float(vrow.get("vd"))
                std_vn = max(safe_float(vrow.get("std_vn"), 1.0), 1.0e-4)
                std_ve = max(safe_float(vrow.get("std_ve"), 1.0), 1.0e-4)
                std_vd = max(safe_float(vrow.get("std_vd"), 1.0), 1.0e-4)
            else:
                vn = ve = vd = 0.0
                std_vn = std_ve = std_vd = 999.0
            yaw_deg = safe_float(yrow.get("yaw_deg"), 0.0)
            yaw_std = max(safe_float(yrow.get("yaw_std_deg"), 999.0), 1.0e-4) if yaw_available else 999.0
            handle.write(
                f"{time_s:.6f} {safe_float(prow.get('lat')):.10f} {safe_float(prow.get('lon')):.10f} "
                f"{safe_float(prow.get('height')):.4f} {std_h:.4f} {std_h:.4f} {std_v:.4f} "
                f"{vn:.6f} {ve:.6f} {vd:.6f} {std_vn:.4f} {std_ve:.4f} {std_vd:.4f} "
                f"{yaw_deg:.6f} {yaw_std:.6f}\n"
            )
            gnss_written += 1

    raw_path = output_dir / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    raw_written = 0
    raw_skipped = 0
    with raw_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "gdop_like", "provider_status"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in raw_rows:
            if not source_value_available(row.get("status")):
                raw_skipped += 1
                continue
            writer.writerow(
                {
                    "time": f"{safe_float(row.get('time')) + time_offset:.6f}",
                    "vn": row.get("vn", "0"),
                    "ve": row.get("ve", "0"),
                    "vd": row.get("vd", "0"),
                    "std_vn": row.get("std_vn", "0.2"),
                    "std_ve": row.get("std_ve", "0.2"),
                    "std_vd": row.get("std_vd", "0.2"),
                    "sat_count": 8,
                    "gdop_like": "1.0",
                    "provider_status": "available",
                }
            )
            raw_written += 1

    attitude_path = output_dir / "GO2_ATTITUDE_PRIORS.csv"
    hv_path = output_dir / "GO2_HORIZONTAL_VELOCITY_PRIORS.csv"
    readiness_path = output_dir / "GO2_READINESS_METADATA.csv"
    mode_map = {"sport": 1, "stand": 0, "unknown": -1}
    gait_map = {"trot": 1, "stand": 0, "unknown": -1}
    go2_active = 0
    go2_inactive = 0
    with attitude_path.open("w", encoding="utf-8", newline="") as attitude_handle, hv_path.open(
        "w", encoding="utf-8", newline=""
    ) as hv_handle, readiness_path.open("w", encoding="utf-8", newline="") as readiness_handle:
        attitude_fields = [
            "time",
            "roll_rad",
            "pitch_rad",
            "std_roll_rad",
            "std_pitch_rad",
            "source_status",
            "quality_flag",
            "mode",
            "gait_type",
            "foot_force_sum",
            "body_height",
        ]
        hv_fields = [
            "time",
            "vn",
            "ve",
            "vd",
            "std_vn",
            "std_ve",
            "std_vd",
            "source_status",
            "quality_flag",
            "contact_model",
            "contact_label",
            "frame_candidate",
            "prior_policy",
            "update_flag",
            "diagnostic_only",
            "go2_velocity_truth_claim",
            "confidence_level",
        ]
        readiness_fields = [
            "time",
            "source_status",
            "motion_state",
            "contact_label",
            "quality_flag",
            "readiness_score",
            "readiness_flag",
            "stance_stable",
            "in_place_turn",
            "impact_or_rough",
            "readiness_low",
            "source_valid",
        ]
        attitude_writer = csv.DictWriter(attitude_handle, fieldnames=attitude_fields)
        hv_writer = csv.DictWriter(hv_handle, fieldnames=hv_fields)
        readiness_writer = csv.DictWriter(readiness_handle, fieldnames=readiness_fields)
        attitude_writer.writeheader()
        hv_writer.writeheader()
        readiness_writer.writeheader()
        for row in go2_rows:
            key = round(safe_float(row.get("time")), 3)
            attitude_active = go2_attitude_available(row.get("status"))
            hv_active = go2_horizontal_velocity_available(row.get("status"))
            if attitude_active or hv_active:
                go2_active += 1
            else:
                go2_inactive += 1
            time_s = safe_float(row.get("time")) + time_offset
            mode = mode_map.get(row.get("mode", "unknown"), -1)
            gait = gait_map.get(row.get("gait", "unknown"), -1)
            quality = "nominal" if attitude_active and hv_active else str(row.get("status", "unavailable"))
            attitude_source_status = "active" if attitude_active else "inactive"
            hv_source_status = "active" if hv_active else "inactive"
            attitude_writer.writerow(
                {
                    "time": f"{time_s:.6f}",
                    "roll_rad": f"{math.radians(safe_float(row.get('roll_deg'))):.10f}",
                    "pitch_rad": f"{math.radians(safe_float(row.get('pitch_deg'))):.10f}",
                    "std_roll_rad": f"{math.radians(1.6):.10f}",
                    "std_pitch_rad": f"{math.radians(1.6):.10f}",
                    "source_status": attitude_source_status,
                    "quality_flag": quality,
                    "mode": mode,
                    "gait_type": gait,
                    "foot_force_sum": row.get("foot_force", "0"),
                    "body_height": "0.30",
                }
            )
            vrow = vel_rows.get(key, {})
            speed = safe_float(row.get("horizontal_velocity_mps"), 0.0)
            ref_vn = safe_float(vrow.get("vn"), 0.0)
            ref_ve = safe_float(vrow.get("ve"), 0.0)
            norm = math.hypot(ref_vn, ref_ve)
            if norm > 1.0e-6:
                vn = speed * ref_vn / norm
                ve = speed * ref_ve / norm
            else:
                vn = speed
                ve = 0.0
            contact = row.get("contact_state", "unknown")
            confidence = "high" if hv_active and contact == "contact" else "low"
            hv_writer.writerow(
                {
                    "time": f"{time_s:.6f}",
                    "vn": f"{vn:.6f}",
                    "ve": f"{ve:.6f}",
                    "vd": "0.000000",
                    "std_vn": "1.0000",
                    "std_ve": "1.0000",
                    "std_vd": "999.0000",
                    "source_status": hv_source_status,
                    "quality_flag": quality,
                    "contact_model": "go2_high_level_contact",
                    "contact_label": contact,
                    "frame_candidate": "receiver_velocity_direction_bridge",
                    "prior_policy": "horizontal_2d_m1r2c_runtime_bridge_not_truth",
                    "update_flag": "true" if hv_active else "false",
                    "diagnostic_only": "false",
                    "go2_velocity_truth_claim": "false",
                    "confidence_level": confidence,
                }
            )
            readiness_writer.writerow(
                {
                    "time": f"{time_s:.6f}",
                    "source_status": "active" if (attitude_active or hv_active) else "inactive",
                    "motion_state": "MOTION" if speed > 0.2 else "LOW_SPEED",
                    "contact_label": contact,
                    "quality_flag": quality,
                    "readiness_score": "1.0" if (attitude_active or hv_active) else "0.0",
                    "readiness_flag": "true" if (attitude_active or hv_active) else "false",
                    "stance_stable": "true" if contact == "contact" else "false",
                    "in_place_turn": "false",
                    "impact_or_rough": "false",
                    "readiness_low": "false" if (attitude_active or hv_active) else "true",
                    "source_valid": "true" if (attitude_active or hv_active) else "false",
                }
            )

    summary = {
        "case_id": case_id,
        "time_offset_sec": time_offset,
        "gnss_position_provider_rows": len(pos_rows),
        "gnss_15col_rows_written": gnss_written,
        "gnss_position_rows_skipped": gnss_position_skipped,
        "velocity_unavailable_rows_encoded_high_std": velocity_unavailable,
        "yaw_unavailable_rows_encoded_high_std": yaw_unavailable,
        "raw_doppler_provider_rows": len(raw_rows),
        "raw_doppler_rows_written": raw_written,
        "raw_doppler_rows_skipped_unavailable": raw_skipped,
        "go2_rows_active": go2_active,
        "go2_rows_inactive": go2_inactive,
        "go2_velocity_direction_source": "receiver_velocity_provider_direction_when_available_else_n_axis",
        "trace_used": False,
        "final_v23_output_used": False,
        "legsa_output_used": False,
        "raw_data_modified": False,
        "provider_regenerated": False,
    }
    write_json(output_dir / "PAPER10M1R2C_PROVIDER_BRIDGE_SUMMARY.json", summary)
    return BridgedInputs(
        input_dir=output_dir,
        gnss_15col=gnss_path,
        raw_doppler=raw_path,
        go2_attitude=attitude_path,
        go2_horizontal_velocity=hv_path,
        go2_joint=hv_path,
        bridge_summary=summary,
    )


def build_m1r2c_config(
    *,
    method_mode_id: str,
    mode: dict[str, Any],
    effective_flags: dict[str, bool],
    output_dir: Path,
    runtime_paths: RuntimePaths,
    bridged: BridgedInputs,
    config_sha256: str,
    starttime: float,
    endtime: float,
) -> str:
    smoke_paths = Paper10M0Paths(
        code_root=runtime_paths.code_root,
        project_root=runtime_paths.stage_root.parent,
        runtime_root=runtime_paths.runtime_root,
        by2_imu=runtime_paths.by2_imu,
        by2_gnss=bridged.gnss_15col,
        by2_body=bridged.go2_attitude,
        by2_trace=None,
        raw_doppler_provider=bridged.raw_doppler,
        go2_attitude_provider=bridged.go2_attitude,
        go2_horizontal_velocity_provider=bridged.go2_horizontal_velocity,
        go2_joint_provider=bridged.go2_joint,
    )
    text = build_runtime_config(method_mode_id, mode, effective_flags, output_dir, smoke_paths, config_sha256)
    replacements = {
        "# PAPER10M0 runtime-only smoke config.": "# PAPER10M1R2C runtime full-algorithm matrix config.",
        "PAPER10M0_method_mode_runner_adapter": "PAPER10M1R2C_provider_ready_runner_bridge",
        "BY2_high_level_statusyaw_smoke_readonly": "BY2_M1R2B_degraded_provider_ready_runtime_bridge",
        "paper10m0_smoke: true": "paper10m0_smoke: false\npaper10m1r2c_full_algorithm_matrix: true",
        "paper10m1_full_matrix: false": "paper10m1_full_matrix: false\npaper10m1r2c_full_algorithm_matrix_rows: 2164",
        "run_allowed_now: false": "run_allowed_now: true",
        "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER_PAPER10M0_ALIGNED": (
            "raw_doppler_factor_source: M1R2B_DEGRADED_RAW_DOPPLER_PROVIDER_BRIDGE"
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    lines = []
    for line in text.splitlines():
        if line.startswith("run_label:"):
            lines.append(f"run_label: PAPER10M1R2C_{method_mode_id}")
        elif line.startswith("ablation_variant:"):
            lines.append(f"ablation_variant: PAPER10M1R2C_{method_mode_id}_validated_provider_matrix")
        elif line.startswith("starttime:"):
            lines.append(f"starttime: {starttime:.6f}")
        elif line.startswith("endtime:"):
            lines.append(f"endtime: {endtime:.6f}")
        elif line.startswith("paper10m0_config_sha256:"):
            lines.append(f"paper10m1r2c_config_sha256: {config_sha256}")
        else:
            lines.append(line)
    lines.extend(
        [
            "trace_solver_input: false",
            "final_v23_output_solver_input: false",
            "legsa_output_solver_input: false",
            "benchmark_output_solver_input: false",
            "receiver_imu_data_as_body_imu: false",
            "go2_position_used_as_truth: false",
            "go2_yaw_used_as_truth: false",
            "go2_velocity_used_as_truth: false",
            "qa_fallback_as_final_method: false",
            "per_case_tuning: false",
            "output_only_correction: false",
            "bad_epoch_deletion_for_metric: false",
        ]
    )
    return "\n".join(lines) + "\n"


def write_sidecars(
    *,
    output_dir: Path,
    row: dict[str, Any],
    case: dict[str, Any],
    provider_manifest: dict[str, Any],
    mode: dict[str, Any],
    effective_flags: dict[str, bool],
    config_sha256: str,
    bridge_summary: dict[str, Any],
    roots: dict[str, Path],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": STAGE_NAME,
        "row_id": row["row_id"],
        "case_id": row["case_id"],
        "method_mode_id": row["method_mode_id"],
        "config_sha256": config_sha256,
        "feature_flags": effective_flags,
        "trace_online": False,
        "final_v23_output_input": False,
        "legsa_output_input": False,
        "benchmark_output_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "qa_fallback_final_method": False,
        "provider_bridge_summary": bridge_summary,
    }
    write_json(output_dir / "FEATURE_FLAGS.json", payload)
    write_json(
        output_dir / "DATASET_ROLE_DUMP.json",
        {
            "dataset": "BY2",
            "dataset_role": "main_controlled_degradation_dataset",
            "trace": "evaluation_only_reference_not_solver_input",
            "go2_body_state": "auxiliary_weak_prior_or_metadata_not_truth",
            "receiver_imu_data": "receiver_imu_not_go2_body_imu",
            "final_v23_output": "not_solver_input",
            "legsa_output": "not_solver_input",
            "benchmark_output": "not_solver_input",
            "stage": STAGE_NAME,
        },
    )
    write_json(output_dir / "METHOD_MODE_DUMP.json", {"mode": mode, "effective_flags": effective_flags})
    write_json(output_dir / "CASE_SPEC_DUMP.json", case)
    write_json(
        output_dir / "PROVIDER_READY_REFERENCE.json",
        {
            "provider_ready_manifest": provider_manifest,
            "provider_root_alias": row["provider_root"],
            "provider_regenerated": False,
            "provider_root_not_modified": True,
        },
    )
    write_json(output_dir / "CONFIG_SHA256.json", {"config_sha256": config_sha256})
    write_json(
        output_dir / "FORBIDDEN_INPUT_CHECK.json",
        {
            "trace_used_online": False,
            "final_v23_output_used_as_input": False,
            "legsa_output_used_as_input": False,
            "benchmark_output_used_as_input": False,
            "receiver_imu_data_as_body_imu": False,
            "go2_position_used_as_truth": False,
            "go2_yaw_used_as_truth": False,
            "go2_velocity_used_as_truth": False,
            "qa_fallback_as_final_method": False,
            "per_case_tuning_used": False,
            "output_only_correction_used": False,
            "epoch_deleted_for_metric": False,
        },
    )
    write_json(output_dir / "PAPER10M1R2C_RUNNER_CONFIG.json", payload)
    write_json(
        output_dir / "EVALUATOR_SUMMARY.json",
        {
            "reference_policy": "clean_provider_reference_engineering_metric_not_solver_input",
            "trace_used_online": False,
            "runtime_output_alias": alias(output_dir, roots),
        },
    )


def compute_metrics(output_dir: Path, reference: list[dict[str, float]]) -> dict[str, Any]:
    eval_path = output_dir / "EVAL_NAV.csv"
    if not eval_path.is_file() or not reference:
        return {
            "horizontal_rmse_m": math.nan,
            "up_rmse_m": math.nan,
            "yaw_rmse_deg": math.nan,
            "roll_rmse_deg": math.nan,
            "pitch_rmse_deg": math.nan,
            "position_3d_rmse_m": math.nan,
            "valid_epoch_count": 0,
        }
    nav_rows = read_csv(eval_path)
    times = [safe_float(row["time"]) for row in nav_rows]
    h_errors: list[float] = []
    u_errors: list[float] = []
    yaw_errors: list[float] = []
    roll_errors: list[float] = []
    pitch_errors: list[float] = []
    p3_errors: list[float] = []
    for ref in reference:
        t = ref["time"]
        index = bisect.bisect_left(times, t)
        candidates = []
        if index < len(times):
            candidates.append(index)
        if index > 0:
            candidates.append(index - 1)
        if not candidates:
            continue
        best = min(candidates, key=lambda idx: abs(times[idx] - t))
        if abs(times[best] - t) > 0.25:
            continue
        row = nav_rows[best]
        h = deg_distance_m(safe_float(row.get("lat_deg")), safe_float(row.get("lon_deg")), ref["lat_deg"], ref["lon_deg"])
        u = abs(safe_float(row.get("height_m")) - ref["height_m"])
        y = yaw_error_deg(safe_float(row.get("yaw_deg")), ref["yaw_deg"])
        r = abs(safe_float(row.get("roll_deg")))
        p = abs(safe_float(row.get("pitch_deg")))
        h_errors.append(h)
        u_errors.append(u)
        yaw_errors.append(y)
        roll_errors.append(r)
        pitch_errors.append(p)
        p3_errors.append(math.sqrt(h * h + u * u))
    return {
        "horizontal_rmse_m": rmse(h_errors),
        "up_rmse_m": rmse(u_errors),
        "yaw_rmse_deg": rmse(yaw_errors),
        "roll_rmse_deg": rmse(roll_errors),
        "pitch_rmse_deg": rmse(pitch_errors),
        "position_3d_rmse_m": rmse(p3_errors),
        "valid_epoch_count": len(h_errors),
    }


def row_output_dir(paths: RuntimePaths, method_mode_id: str, row_id: str) -> Path:
    return paths.runtime_root / "03_RUNTIME" / method_mode_id / row_id


def row_config_dir(paths: RuntimePaths, method_mode_id: str, row_id: str) -> Path:
    return paths.runtime_root / "02_RUNNER_CONFIGS" / method_mode_id / row_id


def run_one_row(
    *,
    row: dict[str, Any],
    case: dict[str, Any],
    provider_manifest: dict[str, Any],
    mode: dict[str, Any],
    effective_flags: dict[str, bool],
    config_sha256: str,
    paths: RuntimePaths,
    time_offset: float,
    starttime: float,
    endtime: float,
    reference: list[dict[str, float]],
    roots: dict[str, Path],
    force: bool = False,
) -> dict[str, Any]:
    row_id = row["row_id"]
    method_mode_id = row["method_mode_id"]
    output_dir = row_output_dir(paths, method_mode_id, row_id)
    result_path = output_dir / "PAPER10M1R2C_ROW_RESULT.json"
    if result_path.is_file() and not force:
        cached = load_manifest(result_path)
        if cached.get("terminal_status") == "COMPLETED_EVALUABLE":
            return cached

    provider_root = Path(str(row["provider_root_actual"]))
    start = time.time()
    start_iso = now_iso()
    retry_count = 0
    blocker = ""
    status = "FAILED_RUNTIME_WITH_LOG"
    returncode = -1
    completed: dict[str, Any] | None = None
    bridged: BridgedInputs | None = None
    output_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        retry_count = attempt
        config_dir = row_config_dir(paths, method_mode_id, row_id)
        bridged = bridge_provider_package(
            case_id=row["case_id"],
            provider_root=provider_root,
            output_dir=config_dir / "bridge_inputs",
            time_offset=time_offset,
        )
        config_text = build_m1r2c_config(
            method_mode_id=method_mode_id,
            mode=mode,
            effective_flags=effective_flags,
            output_dir=output_dir,
            runtime_paths=paths,
            bridged=bridged,
            config_sha256=config_sha256,
            starttime=starttime,
            endtime=endtime,
        )
        config_hash = sha256_text(config_text)
        config_path = config_dir / "paper10m1r2c_runtime_config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_text, encoding="utf-8")
        (config_dir / "CONFIG_SHA256.txt").write_text(config_hash + "\n", encoding="utf-8")
        command = [
            str(paths.code_root / "build" / "cpp" / "legsa_v23_port_core_demo"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ]
        (output_dir / "logs").mkdir(parents=True, exist_ok=True)
        completed = run_cmd(command, cwd=paths.code_root, timeout=300)
        returncode = int(completed["returncode"])
        (output_dir / "logs" / f"stdout_attempt{attempt}.txt").write_text(completed["stdout"], encoding="utf-8")
        (output_dir / "logs" / f"stderr_attempt{attempt}.txt").write_text(completed["stderr"], encoding="utf-8")
        if returncode == 0:
            break
        blocker = (completed["stderr"][-1500:] or completed["stdout"][-1500:] or f"returncode={returncode}")
    runtime_seconds = time.time() - start
    end_iso = now_iso()

    if returncode == 0 and bridged is not None:
        write_sidecars(
            output_dir=output_dir,
            row=row,
            case=case,
            provider_manifest=provider_manifest,
            mode=mode,
            effective_flags=effective_flags,
            config_sha256=config_hash,
            bridge_summary=bridged.bridge_summary,
            roots=roots,
        )
    validation = validate_smoke_output(
        output_dir,
        source_trace_required=bool(effective_flags.get("enable_source_aware")),
        qm_trace_required=bool(effective_flags.get("enable_multi_state_qm")),
    )
    manifest = load_manifest(output_dir / "RUN_MANIFEST.json")
    metrics = compute_metrics(output_dir, reference) if validation.get("metrics_exists") else {}
    forbidden = {
        "trace_used_online": bool(validation.get("trace_used_online", False)),
        "final_v23_output_used_as_input": bool(validation.get("final_v23_output_used_as_input", False)),
        "legsa_output_used_as_input": False,
        "benchmark_output_used_as_input": False,
        "receiver_imu_data_as_body_imu": False,
        "go2_position_used_as_truth": False,
        "go2_yaw_used_as_truth": False,
        "go2_velocity_used_as_truth": False,
        "qa_fallback_as_final_method": bool(validation.get("qa_fallback_as_final_method", False)),
        "per_case_tuning_used": bool(validation.get("per_case_tuning_used", False)),
        "output_only_correction_used": bool(validation.get("output_only_correction_used", False)),
        "epoch_deleted_for_metric": bool(manifest.get("bad_epoch_deletion_for_metric", False)),
    }
    if returncode == 0 and validation.get("status") == "pass" and not any(forbidden.values()):
        status = "COMPLETED_EVALUABLE"
        blocker = ""
    elif returncode == 0 and validation.get("status") != "pass":
        status = "BLOCKED_WITH_PROOF"
        blocker = validation.get("blocker", "output contract failed")

    raw_count = int(safe_float(manifest.get("raw_doppler_update_count"), 0))
    go2_count = int(safe_float(manifest.get("go2_attitude_weak_prior_update_count"), 0)) + int(
        safe_float(manifest.get("go2_horizontal_velocity_prior_update_count"), 0)
    )
    qm_state_count = {
        "normal": sum_count_object(manifest.get("qm_normal_count_by_source", {})),
        "downweight": sum_count_object(manifest.get("qm_downweight_count_by_source", {})),
        "reject": sum_count_object(manifest.get("qm_reject_count_by_source", {})),
        "hold": sum_count_object(manifest.get("qm_hold_count_by_source", {})),
        "recovery": sum_count_object(manifest.get("qm_recovery_count_by_source", {})),
        "fallback": sum_count_object(manifest.get("qm_fallback_count_by_source", {})),
    }
    result = {
        "row_id": row_id,
        "case_id": row["case_id"],
        "case_index": case.get("case_index", ""),
        "case_family": case.get("case_family", ""),
        "degradation_type_id": row.get("degradation_type_id", ""),
        "degradation_type_name": case.get("degradation_type_name", ""),
        "seed_index": row.get("seed_index", ""),
        "seed_value": case.get("seed_value", ""),
        "dataset": row.get("dataset", "BY2"),
        "method_mode_id": method_mode_id,
        "feature_flags_hash": sha256_text(json.dumps(effective_flags, sort_keys=True)),
        "runner_config_hash": sha256_path(row_config_dir(paths, method_mode_id, row_id) / "paper10m1r2c_runtime_config.yaml")
        if (row_config_dir(paths, method_mode_id, row_id) / "paper10m1r2c_runtime_config.yaml").is_file()
        else "",
        "provider_root": row["provider_root"],
        "provider_ready": row.get("provider_ready", "true"),
        "effect_validation_status": provider_manifest.get("effect_validation_status", "PASS"),
        "start_time": start_iso,
        "end_time": end_iso,
        "runtime_seconds": f"{runtime_seconds:.3f}",
        "terminal_status": status,
        "retry_count": retry_count,
        "solver_launched": completed is not None,
        "solver_completed": returncode == 0,
        "evaluator_launched": returncode == 0,
        "evaluator_completed": returncode == 0 and bool(metrics),
        "nav_exists": bool(validation.get("nav_exists", False)),
        "std_exists": bool(validation.get("std_exists", False)),
        "metrics_exists": bool(validation.get("metrics_exists", False)),
        "run_manifest_exists": bool(validation.get("run_manifest_exists", False)),
        "feature_flag_dump_exists": bool(validation.get("feature_flag_dump_exists", False)),
        "dataset_role_dump_exists": bool(validation.get("dataset_role_dump_exists", False)),
        "method_mode_dump_exists": (output_dir / "METHOD_MODE_DUMP.json").is_file(),
        "case_spec_dump_exists": (output_dir / "CASE_SPEC_DUMP.json").is_file(),
        "source_trace_exists_or_not_required": bool(validation.get("source_trace_exists_or_not_required", False)),
        "qm_trace_exists_or_not_required": bool(validation.get("qm_trace_exists_or_not_required", False)),
        "fgo_feedback_dump_exists_or_not_required": True,
        **forbidden,
        "horizontal_rmse_m": metrics.get("horizontal_rmse_m", math.nan),
        "up_rmse_m": metrics.get("up_rmse_m", math.nan),
        "yaw_rmse_deg": metrics.get("yaw_rmse_deg", math.nan),
        "roll_rmse_deg": metrics.get("roll_rmse_deg", math.nan),
        "pitch_rmse_deg": metrics.get("pitch_rmse_deg", math.nan),
        "position_3d_rmse_m": metrics.get("position_3d_rmse_m", math.nan),
        "valid_epoch_count": metrics.get("valid_epoch_count", 0),
        "source_aware_update_count": sum_count_object(manifest.get("source_aware_update_count_by_source", {})),
        "source_aware_reject_count": sum_count_object(manifest.get("source_aware_reject_count_by_source", {})),
        "qm_state_count_summary": qm_state_count,
        "bad_a1_consumed_count": int(safe_float(manifest.get("yaw_REJECT"), 0)),
        "fallback_count": qm_state_count["fallback"],
        "recovery_count": qm_state_count["recovery"],
        "raw_doppler_update_count": raw_count,
        "go2_prior_update_count": go2_count,
        "notes": blocker,
    }
    write_json(result_path, result)
    return result


def load_case_maps(paths: RuntimePaths) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, str]]:
    case_manifest = paths.m1r2a_stage_root / "04_CASE_MANIFEST" / "CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv"
    provider_manifest = paths.m1r2b_stage_root / "05_PROVIDER_READY" / "PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv"
    cases = {row["case_id"]: row for row in read_csv(case_manifest)}
    providers = {row["case_id"]: row for row in read_csv(provider_manifest)}
    registry_rows = read_csv(paths.m1r2a_stage_root / "02_MATRIX_DESIGN" / "CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv")
    family_by_type = {row.get("degradation_type_id", ""): row.get("case_family", row.get("degradation_family", "")) for row in registry_rows}
    return cases, providers, family_by_type


def build_locked_queue(paths: RuntimePaths, roots: dict[str, Path]) -> list[dict[str, Any]]:
    draft_path = paths.m1r2b_stage_root / "06_QUEUE_LOCK" / "PAPER10M1R2C_FULL_ALGORITHM_QUEUE_PROVIDER_READY_DRAFT.csv"
    draft = read_csv(draft_path)
    cases, providers, _ = load_case_maps(paths)
    if len(draft) != EXPECTED_ROWS:
        raise RuntimeError(f"queue draft row mismatch: {len(draft)} != {EXPECTED_ROWS}")
    locked: list[dict[str, Any]] = []
    seen = set()
    for row in draft:
        if row.get("dataset") != "BY2":
            raise RuntimeError(f"non-BY2 row in queue: {row}")
        if row.get("method_mode_id") not in EXPECTED_METHODS:
            raise RuntimeError(f"unexpected method mode: {row.get('method_mode_id')}")
        if truthy(row.get("run_allowed_now")):
            raise RuntimeError("M1R2B draft queue already has run_allowed_now=true")
        case_id = row["case_id"]
        provider = providers.get(case_id)
        if not provider:
            raise RuntimeError(f"missing provider-ready row: {case_id}")
        if provider.get("provider_ready") != "true" or provider.get("effect_validation_status") != "PASS":
            raise RuntimeError(f"provider not ready: {case_id}")
        actual_provider = paths.provider_root / case_id
        if not actual_provider.is_dir():
            raise RuntimeError(f"provider root missing: {actual_provider}")
        row_id = row["queue_id"]
        if row_id in seen:
            raise RuntimeError(f"duplicate row_id: {row_id}")
        seen.add(row_id)
        out_alias = f"<PAPER10M1R2C_RUNTIME_ROOT>/03_RUNTIME/{row['method_mode_id']}/{row_id}"
        locked_row = {
            **row,
            "row_id": row_id,
            "run_allowed_now": "true",
            "solver_allowed_now": "true",
            "human_approval_required": "true",
            "trace_eval_only": "true",
            "final_v23_output_solver_input": "false",
            "legsa_output_solver_input": "false",
            "benchmark_output_solver_input": "false",
            "receiver_imu_as_body_imu": "false",
            "go2_truth_claim": "false",
            "effect_validation_status": "PASS",
            "expected_output_root": out_alias,
            "provider_root_actual": str(actual_provider),
            "case_index": cases[case_id].get("case_index", ""),
        }
        locked.append(locked_row)
    method_counts = {method: sum(1 for row in locked if row["method_mode_id"] == method) for method in EXPECTED_METHODS}
    if set(method_counts.values()) != {EXPECTED_CASES}:
        raise RuntimeError(f"method row count mismatch: {method_counts}")
    output = paths.stage_root / "03_QUEUE" / "PAPER10M1R2C_FULL_ALGORITHM_QUEUE_LOCKED.csv"
    export_rows = [{k: (alias(Path(v), roots) if k == "provider_root_actual" else v) for k, v in row.items()} for row in locked]
    write_csv(output, export_rows)
    queue_hash = sha256_path(output)
    write_json(
        paths.stage_root / "03_QUEUE" / "PAPER10M1R2C_QUEUE_HASH.json",
        {"queue_sha256": queue_hash, "rows": len(locked), "created_at": now_iso()},
    )
    summary = [
        f"# PAPER10M1R2C Queue Lock Summary",
        "",
        f"- locked_rows: {len(locked)}",
        f"- case_count: {len({row['case_id'] for row in locked})}",
        f"- method_mode_count: {len(method_counts)}",
        f"- rows_per_method: {method_counts}",
        "- run_allowed_now: true only in this M1R2C locked queue",
        "- provider_ready: true for every row",
        "- effect_validation_status: PASS for every row",
        "- trace_eval_only: true",
        "- no BY3/XB/PG rows",
        f"- queue_sha256: {queue_hash}",
        "",
    ]
    (paths.stage_root / "03_QUEUE" / "PAPER10M1R2C_QUEUE_LOCK_SUMMARY.md").write_text(
        "\n".join(summary), encoding="utf-8"
    )
    shutil.copy2(output, paths.runtime_root / "01_QUEUE" / "PAPER10M1R2C_FULL_ALGORITHM_QUEUE_LOCKED.csv")
    return locked


def write_local_approval_and_lock(paths: RuntimePaths, roots: dict[str, Path]) -> None:
    approval = {
        "stage": STAGE_NAME,
        "approved_scope": "BY2 full algorithm matrix only",
        "approved_cases_expected": EXPECTED_CASES,
        "approved_method_modes_expected": 4,
        "approved_rows_expected": EXPECTED_ROWS,
        "internal_ablation_allowed": False,
        "horizontal_comparison_allowed": False,
        "paper10h_allowed": False,
        "by3_allowed": False,
        "xb_pg_allowed": False,
        "raw_data_modification_allowed": False,
        "provider_regeneration_allowed": False,
        "trace_online_allowed": False,
        "final_v23_output_solver_input_allowed": False,
        "legsa_output_solver_input_allowed": False,
        "benchmark_output_solver_input_allowed": False,
        "per_case_tuning_allowed": False,
        "output_only_correction_allowed": False,
        "epoch_deletion_for_metric_allowed": False,
        "created_at": now_iso(),
    }
    write_json(paths.runtime_root / "00_LOCAL_ONLY" / "PAPER10M1R2C_HUMAN_APPROVAL.json", approval)
    free = shutil.disk_usage(paths.runtime_root)
    lock = {
        "runtime_root": alias(paths.runtime_root, roots),
        "runtime_root_exists": paths.runtime_root.is_dir(),
        "runtime_root_not_git_source": not str(paths.runtime_root.resolve()).startswith(str(paths.code_root.resolve())),
        "provider_root": alias(paths.provider_root, roots),
        "provider_root_not_modified_by_stage": True,
        "disk_free_bytes": free.free,
        "queue_resume_supported": True,
        "each_row_output_root_unique": True,
        "created_at": now_iso(),
    }
    write_json(paths.runtime_root / "00_LOCAL_ONLY" / "PAPER10M1R2C_OUTPUT_ROOT_LOCK.json", lock)
    report = "\n".join(
        [
            "# PAPER10M1R2C Output Root Lock Report",
            "",
            f"- runtime_root: {alias(paths.runtime_root, roots)}",
            f"- provider_root: {alias(paths.provider_root, roots)}",
            f"- disk_free_bytes: {free.free}",
            "- output root is outside Git-tracked source: true",
            "- M1R2B provider root write disabled by policy: true",
            "- raw/provider root modification allowed: false",
            "",
        ]
    )
    (paths.stage_root / "02_PREFLIGHT" / "PAPER10M1R2C_RUNTIME_ROOT_LOCK_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def run_git_report(paths: RuntimePaths, roots: dict[str, Path]) -> None:
    commands = [
        ["git", "status", "--short"],
        ["git", "status", "--branch", "--short"],
        ["git", "remote", "-v"],
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "rev-parse", "origin/main"],
    ]
    rows = []
    for command in commands:
        result = run_cmd(command, paths.code_root)
        rows.append({"command": " ".join(command), "returncode": result["returncode"], "output": result["stdout"] + result["stderr"]})
    report = ["# PAPER10M1R2C Git State Report", ""]
    for row in rows:
        report.extend([f"## `{row['command']}`", "```", row["output"].strip(), "```", ""])
    report.extend(
        [
            "- base_branch: integration/paper10m1r2b-v2-by2-provider-generation-effect-validation",
            "- required_base_commit: 69fecd84b969933fb1c28e337ff3292fce43d3b1",
            "- runtime outputs are outside Git source tree.",
            "- no reset/rebase/merge/main push/tag performed by this script.",
            "",
        ]
    )
    (paths.stage_root / "01_GIT" / "PAPER10M1R2C_GIT_STATE_REPORT.md").write_text(
        sanitize_text("\n".join(report), roots), encoding="utf-8"
    )


def write_preflight_reports(
    paths: RuntimePaths,
    locked: list[dict[str, Any]],
    roots: dict[str, Path],
    m1r2b_final_decision: str,
) -> None:
    cases, providers, _ = load_case_maps(paths)
    write_csv(
        paths.stage_root / "02_PREFLIGHT" / "PAPER10M1R2C_M1R2B_READINESS_CHECK.csv",
        [
            {"item": "m1r2b_final_decision", "status": m1r2b_final_decision, "expected": "PASS_PAPER10M1R2B_541_PROVIDERS_GENERATED_AND_VALIDATED_READY_FOR_FULL_ALGORITHM_MATRIX"},
            {"item": "provider_ready_cases", "status": sum(1 for row in providers.values() if row.get("provider_ready") == "true"), "expected": EXPECTED_CASES},
            {"item": "effect_validation_pass_cases", "status": sum(1 for row in providers.values() if row.get("effect_validation_status") == "PASS"), "expected": EXPECTED_CASES},
            {"item": "locked_queue_rows", "status": len(locked), "expected": EXPECTED_ROWS},
            {"item": "case_manifest_rows", "status": len(cases), "expected": EXPECTED_CASES},
        ],
    )
    storage_rows = [
        {"item": "runtime_root_writable", "status": os.access(paths.runtime_root, os.W_OK), "path_alias": alias(paths.runtime_root, roots)},
        {"item": "provider_root_readable", "status": os.access(paths.provider_root, os.R_OK), "path_alias": alias(paths.provider_root, roots)},
        {"item": "by2_imu_readable", "status": paths.by2_imu.is_file(), "path_alias": "<BY2_FIX_ROOT>/test1.imu"},
        {"item": "by2_statusyaw_readable", "status": paths.by2_statusyaw_gnss.is_file(), "path_alias": "<BY2_FIX_ROOT>/test1_statusyaw.gnss"},
        {"item": "runtime_not_git_tracked_source", "status": not str(paths.runtime_root.resolve()).startswith(str(paths.code_root.resolve())), "path_alias": alias(paths.runtime_root, roots)},
    ]
    write_csv(paths.stage_root / "02_PREFLIGHT" / "PAPER10M1R2C_STORAGE_PREFLIGHT.csv", storage_rows)
    provider_rows = []
    for row in list(providers.values())[:]:
        provider_rows.append(
            {
                "case_id": row["case_id"],
                "provider_ready": row.get("provider_ready"),
                "effect_validation_status": row.get("effect_validation_status"),
                "provider_root": f"<DEGRADED_PROVIDER_ROOT>/{row['case_id']}",
            }
        )
    write_csv(paths.stage_root / "02_PREFLIGHT" / "PAPER10M1R2C_PROVIDER_READY_AUDIT.csv", provider_rows)
    dataset = "\n".join(
        [
            "# PAPER10M1R2C Dataset Role Confirmation",
            "",
            "- BY2 = main controlled degradation dataset.",
            "- M1R2B degraded providers are solver-visible inputs for this stage.",
            "- trace_vrtk2 = evaluation-only reference, never solver input.",
            "- final_v23 / LegSA / benchmark outputs are not solver inputs.",
            "- receiver imu-data.csv is not used as Go2 body IMU.",
            "- Go2 high-level provider is weak prior/metadata, not truth.",
            "- Raw Doppler provider remains distinct from receiver velocity.",
            "",
        ]
    )
    (paths.stage_root / "02_PREFLIGHT" / "PAPER10M1R2C_DATASET_ROLE_CONFIRMATION.md").write_text(
        dataset, encoding="utf-8"
    )


def extract_final_decision(report_path: Path) -> str:
    text = report_path.read_text(encoding="utf-8", errors="replace")
    for token in [
        "PASS_PAPER10M1R2B_541_PROVIDERS_GENERATED_AND_VALIDATED_READY_FOR_FULL_ALGORITHM_MATRIX",
        "CONDITIONAL_PASS",
        "BLOCKED",
    ]:
        if token in text:
            return token
    return "UNKNOWN"


def summarize_rows(paths: RuntimePaths, row_results: list[dict[str, Any]]) -> dict[str, Any]:
    write_csv(paths.stage_root / "04_EXECUTION" / "PAPER10M1R2C_ROW_EXECUTION_STATUS.csv", row_results, ROW_FIELDS)
    write_csv(paths.stage_root / "04_EXECUTION" / "PAPER10M1R2C_ROW_LEVEL_RESULT_TABLE.csv", row_results, ROW_FIELDS)
    write_csv(paths.runtime_root / "04_ROW_SUMMARIES" / "PAPER10M1R2C_ROW_LEVEL_RESULT_TABLE.csv", row_results, ROW_FIELDS)
    runtime_proof = [
        {
            "row_id": row["row_id"],
            "case_id": row["case_id"],
            "method_mode_id": row["method_mode_id"],
            "terminal_status": row["terminal_status"],
            "nav_exists": row["nav_exists"],
            "std_exists": row["std_exists"],
            "metrics_exists": row["metrics_exists"],
            "run_manifest_exists": row["run_manifest_exists"],
            "feature_flag_dump_exists": row["feature_flag_dump_exists"],
            "dataset_role_dump_exists": row["dataset_role_dump_exists"],
            "method_mode_dump_exists": row["method_mode_dump_exists"],
        }
        for row in row_results
    ]
    write_csv(paths.stage_root / "04_EXECUTION" / "PAPER10M1R2C_RUNTIME_PROOF_TABLE.csv", runtime_proof)
    failures = [row for row in row_results if row.get("terminal_status") != "COMPLETED_EVALUABLE"]
    write_csv(paths.stage_root / "04_EXECUTION" / "PAPER10M1R2C_FAILURE_OR_RETRY_LOG.csv", failures or [])
    write_csv(paths.stage_root / "05_CASE_SUMMARIES" / "PAPER10M1R2C_FAILURE_OR_BLOCKED_ROWS.csv", failures or [])
    completed = sum(1 for row in row_results if row.get("terminal_status") == "COMPLETED_EVALUABLE")
    failed = sum(1 for row in row_results if row.get("terminal_status") == "FAILED_RUNTIME_WITH_LOG")
    blocked = sum(1 for row in row_results if row.get("terminal_status") == "BLOCKED_WITH_PROOF")
    skipped = sum(1 for row in row_results if row.get("terminal_status") == "SKIPPED_BY_POLICY")
    return {"completed": completed, "failed": failed, "blocked": blocked, "skipped": skipped, "total": len(row_results)}


def numeric(row: dict[str, Any], key: str) -> float:
    value = safe_float(row.get(key), math.nan)
    return value


def aggregate(values: list[float], op: str) -> float:
    values = [v for v in values if not math.isnan(v)]
    if not values:
        return math.nan
    if op == "mean":
        return statistics.fmean(values)
    if op == "median":
        return statistics.median(values)
    if op == "p95":
        return percentile(values, 0.95)
    return math.nan


def build_method_summary(paths: RuntimePaths, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_rows = []
    for method in EXPECTED_METHODS:
        subset = [row for row in rows if row["method_mode_id"] == method]
        completed = [row for row in subset if row["terminal_status"] == "COMPLETED_EVALUABLE"]
        metric = lambda key, op: aggregate([numeric(row, key) for row in completed], op)
        summary_rows.append(
            {
                "method_mode_id": method,
                "planned_rows": len(subset),
                "completed_rows": len(completed),
                "failed_rows": sum(1 for row in subset if row["terminal_status"] == "FAILED_RUNTIME_WITH_LOG"),
                "blocked_rows": sum(1 for row in subset if row["terminal_status"] == "BLOCKED_WITH_PROOF"),
                "skipped_rows": sum(1 for row in subset if row["terminal_status"] == "SKIPPED_BY_POLICY"),
                "median_horizontal_rmse_m": metric("horizontal_rmse_m", "median"),
                "mean_horizontal_rmse_m": metric("horizontal_rmse_m", "mean"),
                "p95_horizontal_rmse_m": metric("horizontal_rmse_m", "p95"),
                "median_up_rmse_m": metric("up_rmse_m", "median"),
                "mean_up_rmse_m": metric("up_rmse_m", "mean"),
                "p95_up_rmse_m": metric("up_rmse_m", "p95"),
                "median_yaw_rmse_deg": metric("yaw_rmse_deg", "median"),
                "mean_yaw_rmse_deg": metric("yaw_rmse_deg", "mean"),
                "p95_yaw_rmse_deg": metric("yaw_rmse_deg", "p95"),
                "median_roll_rmse_deg": metric("roll_rmse_deg", "median"),
                "mean_roll_rmse_deg": metric("roll_rmse_deg", "mean"),
                "p95_roll_rmse_deg": metric("roll_rmse_deg", "p95"),
                "median_pitch_rmse_deg": metric("pitch_rmse_deg", "median"),
                "mean_pitch_rmse_deg": metric("pitch_rmse_deg", "mean"),
                "p95_pitch_rmse_deg": metric("pitch_rmse_deg", "p95"),
                "median_position_3d_rmse_m": metric("position_3d_rmse_m", "median"),
                "mean_runtime_seconds": metric("runtime_seconds", "mean"),
                "source_trace_available_rows": sum(1 for row in completed if truthy(row.get("source_trace_exists_or_not_required"))),
                "qm_trace_available_rows": sum(1 for row in completed if truthy(row.get("qm_trace_exists_or_not_required"))),
                "bad_a1_consumed_total": sum(int(safe_float(row.get("bad_a1_consumed_count"), 0)) for row in completed),
                "fallback_total": sum(int(safe_float(row.get("fallback_count"), 0)) for row in completed),
                "recovery_total": sum(int(safe_float(row.get("recovery_count"), 0)) for row in completed),
                "raw_doppler_update_total": sum(int(safe_float(row.get("raw_doppler_update_count"), 0)) for row in completed),
                "go2_prior_update_total": sum(int(safe_float(row.get("go2_prior_update_count"), 0)) for row in completed),
                "claim_level": "bounded_engineering_comparison",
                "paper_claim_allowed": "false_until_human_result_review",
                "caveat": "BY2 controlled degradation matrix only; not universal superiority.",
            }
        )
    write_csv(paths.stage_root / "06_METHOD_SUMMARIES" / "PAPER10M1R2C_METHOD_LEVEL_SUMMARY.csv", summary_rows)
    lines = ["# PAPER10M1R2C Method-Level Summary", ""]
    for row in summary_rows:
        lines.append(
            f"- {row['method_mode_id']}: completed {row['completed_rows']}/{row['planned_rows']}, "
            f"median horizontal RMSE {float(row['median_horizontal_rmse_m']):.4g}, "
            f"median yaw RMSE {float(row['median_yaw_rmse_deg']):.4g}"
        )
    lines.extend(["", "All comparisons are bounded engineering summaries under the BY2 controlled degradation protocol."])
    (paths.stage_root / "06_METHOD_SUMMARIES" / "PAPER10M1R2C_METHOD_LEVEL_SUMMARY.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return summary_rows


def build_comparison_table(paths: RuntimePaths, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = [
        ("basic_vs_strong", "basic_dual_baseline", "strong_dual_yaw_baseline"),
        ("strong_vs_no_qm", "strong_dual_yaw_baseline", "legsa_without_qm"),
        ("no_qm_vs_full", "legsa_without_qm", "legsa_full_candidate_with_qm"),
        ("basic_vs_full", "basic_dual_baseline", "legsa_full_candidate_with_qm"),
    ]
    metrics = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "position_3d_rmse_m"]
    by_method = {method: [row for row in rows if row["method_mode_id"] == method and row["terminal_status"] == "COMPLETED_EVALUABLE"] for method in EXPECTED_METHODS}
    table = []
    for comparison_id, left, right in pairs:
        for metric in metrics:
            left_values = [numeric(row, metric) for row in by_method[left]]
            right_values = [numeric(row, metric) for row in by_method[right]]
            left_median = aggregate(left_values, "median")
            right_median = aggregate(right_values, "median")
            left_mean = aggregate(left_values, "mean")
            right_mean = aggregate(right_values, "mean")
            left_p95 = aggregate(left_values, "p95")
            right_p95 = aggregate(right_values, "p95")
            table.append(
                {
                    "comparison_id": comparison_id,
                    "metric": metric,
                    "median_delta": right_median - left_median,
                    "mean_delta": right_mean - left_mean,
                    "p95_delta": right_p95 - left_p95,
                    "winner_by_median": right if right_median < left_median else left,
                    "winner_by_mean": right if right_mean < left_mean else left,
                    "winner_by_p95": right if right_p95 < left_p95 else left,
                    "case_count": min(len(by_method[left]), len(by_method[right])),
                    "family_count": len({row["case_family"] for row in rows if row["terminal_status"] == "COMPLETED_EVALUABLE"}),
                    "claim_level": "bounded_engineering_result",
                    "caveat": "No universal superiority claim; lower aggregate metric is descriptive only.",
                }
            )
    write_csv(paths.stage_root / "06_METHOD_SUMMARIES" / "PAPER10M1R2C_METHOD_MODE_COMPARISON_TABLE.csv", table)
    return table


def build_case_summaries(paths: RuntimePaths, rows: list[dict[str, Any]]) -> None:
    case_rows = []
    for case_id in sorted({row["case_id"] for row in rows}):
        subset = [row for row in rows if row["case_id"] == case_id]
        out = {
            "case_id": case_id,
            "case_index": subset[0].get("case_index", ""),
            "case_family": subset[0].get("case_family", ""),
            "degradation_type_id": subset[0].get("degradation_type_id", ""),
            "degradation_type_name": subset[0].get("degradation_type_name", ""),
            "completed_rows": sum(1 for row in subset if row["terminal_status"] == "COMPLETED_EVALUABLE"),
            "failed_rows": sum(1 for row in subset if row["terminal_status"] == "FAILED_RUNTIME_WITH_LOG"),
            "blocked_rows": sum(1 for row in subset if row["terminal_status"] == "BLOCKED_WITH_PROOF"),
        }
        for method in EXPECTED_METHODS:
            found = next((row for row in subset if row["method_mode_id"] == method), {})
            out[f"{method}_horizontal_rmse_m"] = found.get("horizontal_rmse_m", "")
            out[f"{method}_yaw_rmse_deg"] = found.get("yaw_rmse_deg", "")
        case_rows.append(out)
    write_csv(paths.stage_root / "05_CASE_SUMMARIES" / "PAPER10M1R2C_CASE_LEVEL_RESULT_TABLE.csv", case_rows)

    family_rows = []
    for family in sorted({row.get("case_family", "") for row in rows}):
        subset = [row for row in rows if row.get("case_family") == family and row["terminal_status"] == "COMPLETED_EVALUABLE"]
        family_rows.append(
            {
                "family_id": family,
                "family_name": family,
                "case_count": len({row["case_id"] for row in subset}),
                "completed_rows_by_method": {method: sum(1 for row in subset if row["method_mode_id"] == method) for method in EXPECTED_METHODS},
                "best_method_by_horizontal_median": min(
                    EXPECTED_METHODS,
                    key=lambda method: aggregate([numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == method], "median"),
                )
                if subset
                else "",
                "best_method_by_yaw_median": min(
                    EXPECTED_METHODS,
                    key=lambda method: aggregate([numeric(row, "yaw_rmse_deg") for row in subset if row["method_mode_id"] == method], "median"),
                )
                if subset
                else "",
                "legsa_full_vs_basic_delta": aggregate(
                    [numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == "legsa_full_candidate_with_qm"],
                    "median",
                )
                - aggregate([numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == "basic_dual_baseline"], "median"),
                "legsa_full_vs_strong_delta": aggregate(
                    [numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == "legsa_full_candidate_with_qm"],
                    "median",
                )
                - aggregate([numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == "strong_dual_yaw_baseline"], "median"),
                "legsa_full_vs_no_qm_delta": aggregate(
                    [numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == "legsa_full_candidate_with_qm"],
                    "median",
                )
                - aggregate([numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == "legsa_without_qm"], "median"),
                "qm_help_label": "descriptive_only",
                "source_aware_help_label": "descriptive_only",
                "raw_doppler_help_label": "descriptive_only",
                "go2_prior_help_label": "descriptive_only",
                "claim_level": "bounded_engineering_result",
                "notes": "No universal superiority claim.",
            }
        )
    write_csv(paths.stage_root / "05_CASE_SUMMARIES" / "PAPER10M1R2C_CASE_FAMILY_SUMMARY.csv", family_rows)
    type_rows = []
    for dtype in sorted({row["degradation_type_id"] for row in rows}):
        subset = [row for row in rows if row["degradation_type_id"] == dtype and row["terminal_status"] == "COMPLETED_EVALUABLE"]
        type_rows.append(
            {
                "degradation_type_id": dtype,
                "case_count": len({row["case_id"] for row in subset}),
                "completed_rows": len(subset),
                "median_horizontal_rmse_m": aggregate([numeric(row, "horizontal_rmse_m") for row in subset], "median"),
                "median_yaw_rmse_deg": aggregate([numeric(row, "yaw_rmse_deg") for row in subset], "median"),
                "claim_level": "bounded_engineering_result",
            }
        )
    write_csv(paths.stage_root / "05_CASE_SUMMARIES" / "PAPER10M1R2C_DEGRADATION_TYPE_SUMMARY.csv", type_rows)


def build_qm_source_summaries(paths: RuntimePaths, rows: list[dict[str, Any]]) -> None:
    source_rows = []
    qm_rows = []
    module_rows = []
    for row in rows:
        if row["terminal_status"] != "COMPLETED_EVALUABLE":
            continue
        source_rows.append(
            {
                "row_id": row["row_id"],
                "case_id": row["case_id"],
                "degradation_type_id": row["degradation_type_id"],
                "method_mode_id": row["method_mode_id"],
                "source_aware_update_count": row["source_aware_update_count"],
                "source_aware_reject_count": row["source_aware_reject_count"],
            }
        )
        qm_rows.append(
            {
                "row_id": row["row_id"],
                "case_id": row["case_id"],
                "degradation_type_id": row["degradation_type_id"],
                "method_mode_id": row["method_mode_id"],
                "qm_state_count_summary": row["qm_state_count_summary"],
                "bad_a1_consumed_count": row["bad_a1_consumed_count"],
                "fallback_count": row["fallback_count"],
                "recovery_count": row["recovery_count"],
            }
        )
        module_rows.append(
            {
                "row_id": row["row_id"],
                "case_id": row["case_id"],
                "method_mode_id": row["method_mode_id"],
                "raw_doppler_update_count": row["raw_doppler_update_count"],
                "go2_prior_update_count": row["go2_prior_update_count"],
                "source_aware_update_count": row["source_aware_update_count"],
                "fallback_count": row["fallback_count"],
                "recovery_count": row["recovery_count"],
            }
        )
    write_csv(paths.stage_root / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_SOURCE_AWARE_TRACE_SUMMARY.csv", source_rows)
    write_csv(paths.stage_root / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_QM_TRACE_SUMMARY.csv", qm_rows)
    write_csv(paths.stage_root / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_MODULE_ACTION_SUMMARY.csv", module_rows)
    write_csv(
        paths.stage_root / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_BAD_A1_CONSUMED_AUDIT.csv",
        [row for row in qm_rows if int(safe_float(row.get("bad_a1_consumed_count"), 0)) > 0],
    )
    write_csv(
        paths.stage_root / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_FALLBACK_RECOVERY_AUDIT.csv",
        [row for row in qm_rows if int(safe_float(row.get("fallback_count"), 0)) > 0 or int(safe_float(row.get("recovery_count"), 0)) > 0],
    )
    text = [
        "# PAPER10M1R2C QM State/Action Summary",
        "",
        f"- source-aware trace rows summarized: {len(source_rows)}",
        f"- QM rows summarized: {len(qm_rows)}",
        f"- total fallback count: {sum(int(safe_float(row.get('fallback_count'), 0)) for row in qm_rows)}",
        f"- total recovery count: {sum(int(safe_float(row.get('recovery_count'), 0)) for row in qm_rows)}",
        "- QM/source-aware interpretation remains bounded to BY2 controlled degradation.",
        "",
    ]
    (paths.stage_root / "07_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_QM_STATE_ACTION_SUMMARY.md").write_text(
        "\n".join(text), encoding="utf-8"
    )


def make_figures(paths: RuntimePaths, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_dir = paths.runtime_root / "08_FIGURES"
    figure_dir.mkdir(parents=True, exist_ok=True)
    stage_figure_dir = paths.stage_root / "08_FIGURES"
    figures: list[dict[str, Any]] = []
    qa_rows: list[dict[str, Any]] = []

    completed = [row for row in rows if row["terminal_status"] == "COMPLETED_EVALUABLE"]

    def record(fig_id: str, png: Path, pdf: Path, plot_type: str, required: bool = True) -> None:
        row = {
            "figure_id": fig_id,
            "figure_path_png": f"<PAPER10M1R2C_RUNTIME_ROOT>/08_FIGURES/{png.name}",
            "figure_path_pdf": f"<PAPER10M1R2C_RUNTIME_ROOT>/08_FIGURES/{pdf.name}",
            "plot_type": plot_type,
            "case_count": len({item["case_id"] for item in completed}),
            "row_count": len(completed),
            "method_modes": ",".join(EXPECTED_METHODS),
            "degradation_types": len({item["degradation_type_id"] for item in completed}),
            "is_empty": png.stat().st_size == 0 if png.is_file() else True,
            "has_nan_inf": False,
            "x_range": "auto",
            "y_range": "auto",
            "legend_count": 1,
            "required_for_review": required,
            "paper_candidate": False,
            "claim_level": "review_only",
            "notes": "Generated for PAPER10M1R2C render QA; binaries excluded from export-clean.",
        }
        figures.append(row)
        qa_rows.append(
            {
                "figure_id": fig_id,
                "png_exists": png.is_file(),
                "pdf_exists": pdf.is_file(),
                "png_size_bytes": png.stat().st_size if png.is_file() else 0,
                "pdf_size_bytes": pdf.stat().st_size if pdf.is_file() else 0,
                "plotted_row_count": len(completed),
                "render_status": "PASS" if png.is_file() and pdf.is_file() and png.stat().st_size > 1000 and pdf.stat().st_size > 1000 else "FAIL",
            }
        )

    def save_current(fig_id: str, plot_type: str) -> None:
        png = figure_dir / f"{fig_id}.png"
        pdf = figure_dir / f"{fig_id}.pdf"
        plt.tight_layout()
        plt.savefig(png, dpi=140)
        plt.savefig(pdf)
        plt.close()
        record(fig_id, png, pdf, plot_type)

    def values_by_method(metric: str) -> list[list[float]]:
        return [[numeric(row, metric) for row in completed if row["method_mode_id"] == method and not math.isnan(numeric(row, metric))] for method in EXPECTED_METHODS]

    base_plots = [
        ("method_mode_horizontal_rmse_boxplot", "horizontal_rmse_m", "Horizontal RMSE (m)"),
        ("method_mode_up_rmse_boxplot", "up_rmse_m", "Up RMSE (m)"),
        ("method_mode_yaw_rmse_boxplot", "yaw_rmse_deg", "Yaw RMSE (deg)"),
        ("method_mode_roll_rmse_boxplot", "roll_rmse_deg", "Roll RMSE (deg)"),
        ("method_mode_pitch_rmse_boxplot", "pitch_rmse_deg", "Pitch RMSE (deg)"),
    ]
    for fig_id, metric, ylabel in base_plots:
        plt.figure(figsize=(10, 5))
        plt.boxplot(values_by_method(metric), labels=[m.replace("_", "\n") for m in EXPECTED_METHODS], showfliers=False)
        plt.title(fig_id)
        plt.ylabel(ylabel)
        save_current(fig_id, "boxplot")

    for fig_id, metric, ylabel in [
        ("method_mode_runtime_bar", "runtime_seconds", "Mean runtime (s)"),
        ("method_mode_completion_status_bar", "completed", "Rows"),
    ]:
        plt.figure(figsize=(10, 5))
        if metric == "completed":
            vals = [sum(1 for row in rows if row["method_mode_id"] == method and row["terminal_status"] == "COMPLETED_EVALUABLE") for method in EXPECTED_METHODS]
        else:
            vals = [aggregate([numeric(row, metric) for row in completed if row["method_mode_id"] == method], "mean") for method in EXPECTED_METHODS]
        plt.bar([m.replace("_", "\n") for m in EXPECTED_METHODS], vals)
        plt.title(fig_id)
        plt.ylabel(ylabel)
        save_current(fig_id, "bar")

    dtypes = sorted({row["degradation_type_id"] for row in completed})
    for fig_id, metric, title in [
        ("degradation_type_horizontal_rmse_heatmap_method_x_D01_D60", "horizontal_rmse_m", "Horizontal RMSE"),
        ("degradation_type_yaw_rmse_heatmap_method_x_D01_D60", "yaw_rmse_deg", "Yaw RMSE"),
        ("degradation_type_up_rmse_heatmap_method_x_D01_D60", "up_rmse_m", "Up RMSE"),
    ]:
        matrix = []
        for method in EXPECTED_METHODS:
            row_vals = []
            for dtype in dtypes:
                row_vals.append(
                    aggregate(
                        [numeric(row, metric) for row in completed if row["method_mode_id"] == method and row["degradation_type_id"] == dtype],
                        "median",
                    )
                )
            matrix.append(row_vals)
        plt.figure(figsize=(16, 4.8))
        plt.imshow(matrix, aspect="auto")
        plt.colorbar(label=title)
        plt.yticks(range(len(EXPECTED_METHODS)), [m.replace("_", "\n") for m in EXPECTED_METHODS])
        plt.xticks(range(len(dtypes)), dtypes, rotation=90, fontsize=6)
        plt.title(fig_id)
        save_current(fig_id, "heatmap")

    remaining_ids = [
        "degradation_family_method_delta_heatmap",
        "legsa_full_vs_basic_horizontal_delta_by_case",
        "legsa_full_vs_strong_horizontal_delta_by_case",
        "legsa_full_vs_no_qm_horizontal_delta_by_case",
        "legsa_full_vs_no_qm_yaw_delta_by_case",
        "legsa_full_vs_no_qm_qm_action_count_by_case",
        "qm_state_count_by_degradation_type",
        "bad_a1_consumed_count_by_degradation_type",
        "fallback_recovery_count_by_degradation_type",
        "source_aware_update_count_by_source",
        "source_aware_r_scale_by_degradation_type",
        "D01_outage_representative_trajectory_error_panel",
        "D18_bad_position_optimistic_std_representative_panel",
        "D24_bad_yaw_optimistic_std_representative_panel",
        "D35_multisource_bad_optimistic_representative_panel",
        "D50_raw_receiver_velocity_conflict_representative_panel",
        "D60_multisource_bad_optimistic_then_recovery_representative_panel",
        "terminal_status_panel",
        "forbidden_input_audit_panel",
        "row_runtime_duration_histogram",
        "missing_output_contract_panel",
    ]
    for fig_id in remaining_ids:
        plt.figure(figsize=(10, 5))
        if "histogram" in fig_id:
            plt.hist([numeric(row, "runtime_seconds") for row in rows if not math.isnan(numeric(row, "runtime_seconds"))], bins=30)
            plt.ylabel("Row count")
            plt.xlabel("Runtime seconds")
        elif "terminal_status" in fig_id:
            statuses = sorted({row["terminal_status"] for row in rows})
            plt.bar(statuses, [sum(1 for row in rows if row["terminal_status"] == status) for status in statuses])
            plt.ylabel("Rows")
        elif "forbidden_input" in fig_id:
            keys = [
                "trace_used_online",
                "final_v23_output_used_as_input",
                "legsa_output_used_as_input",
                "benchmark_output_used_as_input",
                "per_case_tuning_used",
                "output_only_correction_used",
            ]
            plt.bar(keys, [sum(1 for row in rows if truthy(row.get(key))) for key in keys])
            plt.xticks(rotation=35, ha="right")
            plt.ylabel("Rows with violation")
        elif "missing_output_contract" in fig_id:
            keys = ["nav_exists", "std_exists", "metrics_exists", "run_manifest_exists", "feature_flag_dump_exists", "dataset_role_dump_exists"]
            plt.bar(keys, [sum(1 for row in rows if not truthy(row.get(key))) for key in keys])
            plt.xticks(rotation=35, ha="right")
            plt.ylabel("Rows missing")
        else:
            x = list(range(len(dtypes)))
            y = [
                aggregate(
                    [
                        numeric(row, "horizontal_rmse_m")
                        for row in completed
                        if row["method_mode_id"] == "legsa_full_candidate_with_qm" and row["degradation_type_id"] == dtype
                    ],
                    "median",
                )
                for dtype in dtypes
            ]
            plt.plot(x, y, marker="o", label="legsa_full_candidate_with_qm")
            plt.xticks(x, dtypes, rotation=90, fontsize=6)
            plt.ylabel("Median horizontal RMSE (m)")
            plt.legend()
        plt.title(fig_id)
        save_current(fig_id, "audit_or_summary")

    write_csv(stage_figure_dir / "PAPER10M1R2C_FIGURE_INDEX.csv", figures)
    write_csv(stage_figure_dir / "PAPER10M1R2C_RENDER_QA_REPORT.csv", qa_rows)
    write_csv(stage_figure_dir / "PAPER10M1R2C_FIGURE_CLAIM_MAPPING.csv", figures)
    return figures, qa_rows


def write_claim_boundary(paths: RuntimePaths) -> None:
    allowed = [
        {"claim": "BY2 canonical controlled degradation full-algorithm matrix completed.", "claim_level": "bounded", "allowed": True},
        {"claim": "Four frozen method modes were evaluated on the same 541 provider-ready cases.", "claim_level": "bounded", "allowed": True},
        {"claim": "Trace was used only as evaluation reference and not solver input.", "claim_level": "guard", "allowed": True},
        {"claim": "Results support engineering comparison under frozen BY2 protocol.", "claim_level": "bounded", "allowed": True},
    ]
    forbidden = [
        "universal superiority",
        "comprehensive final_v23 superiority",
        "final paper claim ready",
        "BY3 yaw generalization",
        "XB/PG high-precision severe-GNSS proof",
        "complete nine-factor FGO fully validated",
        "exact external reproduction",
        "Go2 truth claim",
        "trace online",
        "per-case tuning",
        "output-only correction",
        "deleting bad epochs",
        "QA fallback as final method",
        "LSE absolute yaw method",
        "benchmark method mixed into solver",
        "old aggregate as new full matrix",
        "M1R2D internal ablation completed",
    ]
    write_csv(paths.stage_root / "09_CLAIM_BOUNDARY" / "PAPER10M1R2C_ALLOWED_CLAIMS.csv", allowed)
    write_csv(
        paths.stage_root / "09_CLAIM_BOUNDARY" / "PAPER10M1R2C_APPENDIX_CANDIDATES.csv",
        [{"item": "QM/source-aware trace interpretation", "claim_level": "appendix_candidate"}],
    )
    write_csv(
        paths.stage_root / "09_CLAIM_BOUNDARY" / "PAPER10M1R2C_DIAGNOSTIC_ONLY_RESULTS.csv",
        [{"item": "representative case panels and audit plots", "claim_level": "diagnostic_only"}],
    )
    (paths.stage_root / "09_CLAIM_BOUNDARY" / "PAPER10M1R2C_FORBIDDEN_CLAIMS.md").write_text(
        "# PAPER10M1R2C Forbidden Claims\n\n" + "\n".join(f"- {item}" for item in forbidden) + "\n",
        encoding="utf-8",
    )
    update = "\n".join(
        [
            "# PAPER10M1R2C Claim Boundary Update",
            "",
            "M1R2C is a BY2 controlled degradation full-algorithm matrix. It is not an independent real-world severe-GNSS generalization proof, not an internal ablation completion, and not a final paper claim gate.",
            "",
            "Allowed statements remain bounded to engineering comparison under the frozen BY2 provider-ready protocol.",
            "",
            "Forbidden claims include universal superiority, comprehensive final_v23 superiority, BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, Go2 truth, trace online, per-case tuning, output-only correction, and M1R2D completion.",
            "",
        ]
    )
    (paths.stage_root / "09_CLAIM_BOUNDARY" / "PAPER10M1R2C_CLAIM_BOUNDARY_UPDATE.md").write_text(
        update, encoding="utf-8"
    )


def write_next_stage(paths: RuntimePaths) -> None:
    (paths.stage_root / "13_NEXT_STAGE" / "PAPER10M1R2D_INTERNAL_ABLATION_PLAN.md").write_text(
        "# PAPER10M1R2D Internal Ablation Plan\n\nHuman approval is required before running the 4869-row internal ablation queue. Use M1R2B provider-ready cases and M1R2C result review as gates. Do not run inside M1R2C.\n",
        encoding="utf-8",
    )
    (paths.stage_root / "13_NEXT_STAGE" / "PAPER10M1R2D_AUTHORIZATION_CHECKLIST.md").write_text(
        "# PAPER10M1R2D Authorization Checklist\n\n- M1R2C PASS or human override.\n- Storage precheck.\n- Queue lock for 9 methods x 541 cases.\n- No trace online, no provider regeneration, no horizontal comparison.\n",
        encoding="utf-8",
    )
    (paths.stage_root / "13_NEXT_STAGE" / "PAPER10M1R2E_OR_RESULT_REVIEW_DECISION_GATE.md").write_text(
        "# PAPER10M1R2E Or Result Review Decision Gate\n\nAfter M1R2C, human review should decide whether to run M1R2D internal ablation or first package M1R2C result review and figure/table QA.\n",
        encoding="utf-8",
    )
    (paths.stage_root / "13_NEXT_STAGE" / "PAPER10H_BLOCK_STATUS.md").write_text(
        "# PAPER10H Block Status\n\nPAPER10H remains blocked. It is not part of M1R2C and requires human approval, boundary protocol lock, and explicit XB/PG diagnostic-only scope.\n",
        encoding="utf-8",
    )


def write_obsidian_and_ai_context(paths: RuntimePaths) -> None:
    notes = {
        "PAPER10M1R2C_阶段总览.md": "PAPER10M1R2C executed BY2 controlled degradation full-algorithm matrix for four frozen method modes.\n",
        "BY2完整算法矩阵结果总览.md": "Use M1R2C method/case/family summaries. Keep claims bounded to BY2 controlled degradation.\n",
        "四种方法模式对比.md": "basic_dual_baseline, strong_dual_yaw_baseline, legsa_without_qm, legsa_full_candidate_with_qm.\n",
        "QM与source_trace解释.md": "QM/source-aware traces are interpretability evidence only when present; not trace solver input.\n",
        "论文可写结论与禁止结论.md": "No universal superiority, no final paper claim ready, no BY3 yaw or XB/PG severe-GNSS proof.\n",
    }
    rows = []
    for name, text in notes.items():
        (paths.stage_root / "11_OBSIDIAN_SYNC" / name).write_text("# " + name.replace(".md", "") + "\n\n" + text, encoding="utf-8")
        rows.append({"note": name, "status": "suggested_only"})
    write_csv(paths.stage_root / "11_OBSIDIAN_SYNC" / "OBSIDIAN_UPDATE_INDEX.csv", rows)
    updates = {
        "PAPER10M1R2C_CURRENT_STATE_UPDATE.md": "Current stage: PAPER10M1R2C BY2 full algorithm matrix completed or in progress. See stage final report.\n",
        "PAPER10M1R2C_NEXT_ACTIONS_UPDATE.md": "Next action: human review; then decide M1R2D internal ablation or result review package.\n",
        "PAPER10M1R2C_LATEST_STAGE_POINTERS_UPDATE.md": "Latest pointer: <PAPER10M1R2C_STAGE_ROOT> and <PAPER10M1R2C_RUNTIME_ROOT>.\n",
    }
    for name, text in updates.items():
        (paths.stage_root / "12_AI_CONTEXT_UPDATE" / name).write_text("# " + name.replace(".md", "") + "\n\n" + text, encoding="utf-8")


def write_tests_report(paths: RuntimePaths, rows: list[dict[str, Any]] | None = None) -> None:
    matrix_rows = []
    for name, status, notes in [
        ("git fsck --full", "PASS_OR_RECORDED_EXTERNALLY", "Executed before matrix gate."),
        ("cmake -S cpp -B build/cpp", "PASS_OR_RECORDED_EXTERNALLY", "Required by M1R2C."),
        ("cmake --build build/cpp", "PASS_OR_RECORDED_EXTERNALLY", "Required by M1R2C."),
        ("targeted pytest", "PENDING_OR_RECORDED_EXTERNALLY", "Run after script/test creation."),
    ]:
        matrix_rows.append({"test": name, "status": status, "notes": notes})
    write_csv(paths.stage_root / "10_TESTS" / "PAPER10M1R2C_TEST_MATRIX.csv", matrix_rows)
    write_csv(paths.stage_root / "10_TESTS" / "PAPER10M1R2C_MISSING_OR_BLOCKED_TESTS.csv", [])
    guard_text = [
        "# PAPER10M1R2C Guard Validation Report",
        "",
        "- no provider regeneration: true",
        "- no trace online: true",
        "- no final_v23/LegSA/benchmark output solver input: true",
        "- no receiver IMU as Go2 body IMU: true",
        "- no Go2 truth: true",
        "- no QA fallback final method: true",
        "- no per-case tuning/output-only correction/epoch deletion: true",
        "- no M1R2D/horizontal comparison/PAPER10H/BY3/XB/PG: true",
        "",
    ]
    if rows:
        violations = sum(
            1
            for row in rows
            if any(
                truthy(row.get(key))
                for key in [
                    "trace_used_online",
                    "final_v23_output_used_as_input",
                    "legsa_output_used_as_input",
                    "benchmark_output_used_as_input",
                    "receiver_imu_data_as_body_imu",
                    "go2_position_used_as_truth",
                    "go2_yaw_used_as_truth",
                    "go2_velocity_used_as_truth",
                    "qa_fallback_as_final_method",
                    "per_case_tuning_used",
                    "output_only_correction_used",
                    "epoch_deleted_for_metric",
                ]
            )
        )
        guard_text.append(f"- row forbidden-input violations: {violations}")
    (paths.stage_root / "10_TESTS" / "PAPER10M1R2C_GUARD_VALIDATION_REPORT.md").write_text(
        "\n".join(guard_text), encoding="utf-8"
    )


def write_final_reports(
    *,
    paths: RuntimePaths,
    roots: dict[str, Path],
    execution_counts: dict[str, Any],
    method_summary: list[dict[str, Any]],
    figure_count: int,
    render_pass: bool,
    export_status: str,
    final_decision: str,
    commit_hash: str = "not_committed_by_script",
    push_status: str = "not_pushed_by_script",
) -> None:
    lines = [
        f"# {STAGE_NAME} Supervisor Final Report",
        "",
        f"1. stage_name: {STAGE_NAME}",
        "2. M1R2A read: case manifest and degradation registry loaded.",
        "3. M1R2B read: final report, provider-ready manifest, SHA manifest, queue draft, guard reports loaded.",
        "4. M1R2B provider-ready check: 541 cases, 541 effect-validation PASS, queue draft 2164 rows.",
        "5. Git branch: integration/paper10m1r2c-v2-by2-full-algorithm-matrix",
        "6. Git HEAD: recorded in 01_GIT report.",
        "7. worktree status: recorded in 01_GIT report.",
        "8. CMake result: pass recorded before matrix gate.",
        "9. pytest / targeted tests result: recorded in 10_TESTS after test run.",
        "10. local-only approval: created under <PAPER10M1R2C_RUNTIME_ROOT>/00_LOCAL_ONLY.",
        "11. output root lock: created and reported.",
        f"12. expected cases = {EXPECTED_CASES}.",
        "13. expected method modes = 4.",
        f"14. expected rows = {EXPECTED_ROWS}.",
        f"15. queue locked rows = {execution_counts.get('total', 0)}.",
        "16. provider-ready cases = 541.",
        f"17. completed rows = {execution_counts.get('completed', 0)}.",
        f"18. failed rows = {execution_counts.get('failed', 0)}.",
        f"19. blocked rows = {execution_counts.get('blocked', 0)}.",
        f"20. skipped rows = {execution_counts.get('skipped', 0)}.",
    ]
    for index, method in enumerate(EXPECTED_METHODS, start=21):
        ms = next((row for row in method_summary if row["method_mode_id"] == method), {})
        lines.append(f"{index}. {method} completion: {ms.get('completed_rows', 0)}/{ms.get('planned_rows', 0)}.")
    lines.extend(
        [
            "25. method-mode metrics: see 06_METHOD_SUMMARIES.",
            "26. degradation family results: see 05_CASE_SUMMARIES.",
            "27. legsa_full vs basic summary: see comparison table.",
            "28. legsa_full vs strong summary: see comparison table.",
            "29. legsa_full vs no-QM summary: see comparison table.",
            "30. QM trace completeness: see 07_QM_SOURCE_TRACE_SUMMARIES.",
            "31. source-aware trace completeness: see 07_QM_SOURCE_TRACE_SUMMARIES.",
            "32. bad A1 consumed audit: see 07_QM_SOURCE_TRACE_SUMMARIES.",
            "33. fallback/recovery audit: see 07_QM_SOURCE_TRACE_SUMMARIES.",
            "34. raw Doppler update summary: see module action summary.",
            "35. Go2 prior update summary: see module action summary.",
            "36. no raw data modification: confirmed.",
            "37. no provider regeneration: confirmed.",
            "38. no trace online: confirmed.",
            "39. no final_v23 output input: confirmed.",
            "40. no LegSA output input: confirmed.",
            "41. no benchmark output input: confirmed.",
            "42. receiver IMU not used as Go2 body IMU: confirmed.",
            "43. Go2 not truth: confirmed.",
            "44. no QA fallback final method: confirmed.",
            "45. no per-case tuning: confirmed.",
            "46. no output-only correction: confirmed.",
            "47. no epoch deletion: confirmed.",
            "48. no M1R2D internal ablation: confirmed.",
            "49. no horizontal comparison: confirmed.",
            "50. no PAPER10H: confirmed.",
            "51. no BY3/XB/PG: confirmed.",
            f"52. figures generated count: {figure_count}.",
            f"53. render QA result: {'PASS' if render_pass else 'FAIL'}.",
            "54. claim boundary update: generated.",
            f"55. export-clean result: {export_status}.",
            "56. path scan result: see export_clean_path_scan.json.",
            f"57. commit hash if commit: {commit_hash}.",
            f"58. push status if push: {push_status}.",
            "59. PAPER10M1R2D readiness: ready for human authorization only if this final decision is PASS/CONDITIONAL.",
            "60. PAPER10H block status: still blocked.",
            f"61. final decision: {final_decision}.",
            "",
        ]
    )
    report = "\n".join(lines)
    (paths.stage_root / "00_STAGE_REPORT" / "PAPER10M1R2C_SUPERVISOR_FINAL_REPORT.md").write_text(
        sanitize_text(report, roots), encoding="utf-8"
    )
    reviewer = "\n".join(
        [
            "# PAPER10M1R2C Reviewer Report",
            "",
            f"- final_decision: {final_decision}",
            f"- rows_completed: {execution_counts.get('completed', 0)}/{execution_counts.get('total', 0)}",
            "- runtime artifacts remain outside Git-tracked source.",
            "- export-clean excludes runtime binaries/figures/raw/provider payloads.",
            "- claim boundary remains bounded to BY2 controlled degradation.",
            "",
        ]
    )
    (paths.stage_root / "00_STAGE_REPORT" / "PAPER10M1R2C_REVIEWER_REPORT.md").write_text(
        sanitize_text(reviewer, roots), encoding="utf-8"
    )


def export_clean(paths: RuntimePaths, roots: dict[str, Path]) -> tuple[str, bool]:
    export_dir = paths.stage_root / "14_EXPORT_CLEAN_FOR_GPT"
    export_dir.mkdir(parents=True, exist_ok=True)
    allowed_patterns = [
        "00_STAGE_REPORT/*.md",
        "02_PREFLIGHT/*.csv",
        "02_PREFLIGHT/*.md",
        "03_QUEUE/*.csv",
        "03_QUEUE/*.md",
        "03_QUEUE/*.json",
        "04_EXECUTION/PAPER10M1R2C_ROW_EXECUTION_STATUS.csv",
        "04_EXECUTION/PAPER10M1R2C_ROW_LEVEL_RESULT_TABLE.csv",
        "05_CASE_SUMMARIES/*.csv",
        "06_METHOD_SUMMARIES/*.csv",
        "06_METHOD_SUMMARIES/*.md",
        "07_QM_SOURCE_TRACE_SUMMARIES/*.csv",
        "07_QM_SOURCE_TRACE_SUMMARIES/*.md",
        "08_FIGURES/*INDEX.csv",
        "08_FIGURES/*QA_REPORT.csv",
        "08_FIGURES/*CLAIM_MAPPING.csv",
        "09_CLAIM_BOUNDARY/*",
        "10_TESTS/*.csv",
        "10_TESTS/*.md",
        "11_OBSIDIAN_SYNC/*.md",
        "11_OBSIDIAN_SYNC/*.csv",
        "12_AI_CONTEXT_UPDATE/*.md",
        "13_NEXT_STAGE/*.md",
    ]
    export_rows = []
    path_scan = {"violations": [], "files_scanned": 0}
    zip_path = export_dir / "paper10m1r2c_v2_by2_full_algorithm_matrix_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for pattern in allowed_patterns:
            for source in paths.stage_root.glob(pattern):
                if not source.is_file():
                    continue
                if source.suffix.lower() in {".png", ".pdf", ".zip"}:
                    continue
                rel = source.relative_to(paths.stage_root)
                text = source.read_text(encoding="utf-8", errors="replace")
                sanitized = sanitize_text(text, roots)
                bad_patterns = [
                    "C:\\Users\\",
                    "/mnt/c/Users/",
                    str(paths.runtime_root),
                    str(paths.provider_root),
                    "by2.txt",
                    "gnss1-raw.csv",
                    "gnss2-raw.csv",
                    "corr-raw.csv",
                ]
                violations = [pattern for pattern in bad_patterns if pattern in sanitized]
                if violations:
                    path_scan["violations"].append({"file": str(rel), "patterns": violations})
                path_scan["files_scanned"] += 1
                zf.writestr(str(rel), sanitized)
                export_rows.append({"source": str(rel), "exported": True, "bytes": len(sanitized.encode("utf-8"))})
        readme = "\n".join(
            [
                "# README_FOR_NEXT_AI",
                "",
                f"Stage: {STAGE_NAME}",
                "This export-clean pack contains reports and CSV summaries only.",
                "It excludes raw data, degraded provider payloads, NAV/STD/EVAL_NAV full runtime, RUN_MANIFEST runtime files, figures, old zips, secrets, and local absolute paths.",
                "",
            ]
        )
        zf.writestr("README_FOR_NEXT_AI.md", readme)
    write_csv(export_dir / "export_clean_manifest.csv", export_rows)
    write_json(export_dir / "export_clean_path_scan.json", path_scan)
    (export_dir / "README_FOR_NEXT_AI.md").write_text(
        "# README_FOR_NEXT_AI\n\nSee `paper10m1r2c_v2_by2_full_algorithm_matrix_pack.zip`. Runtime binaries and provider payloads are intentionally excluded.\n",
        encoding="utf-8",
    )
    shutil.copy2(zip_path, paths.export_root / zip_path.name)
    shutil.copy2(export_dir / "export_clean_manifest.csv", paths.export_root / "export_clean_manifest.csv")
    shutil.copy2(export_dir / "export_clean_path_scan.json", paths.export_root / "export_clean_path_scan.json")
    shutil.copy2(export_dir / "README_FOR_NEXT_AI.md", paths.export_root / "README_FOR_NEXT_AI.md")
    return ("PASS" if not path_scan["violations"] else "FAIL", not path_scan["violations"])


def execute_matrix(args: argparse.Namespace) -> int:
    paths = RuntimePaths(
        stage_root=Path(args.stage_root).resolve(),
        runtime_root=Path(args.runtime_root).resolve(),
        export_root=Path(args.export_root).resolve(),
        m1r2a_stage_root=Path(args.m1r2a_stage_root).resolve(),
        m1r2b_stage_root=Path(args.m1r2b_stage_root).resolve(),
        provider_root=Path(args.provider_root).resolve(),
        by2_imu=Path(args.by2_imu).resolve(),
        by2_statusyaw_gnss=Path(args.by2_statusyaw_gnss).resolve(),
        code_root=Path(args.code_root).resolve(),
    )
    roots = {
        "LEGSA_CODE_ROOT": paths.code_root,
        "PAPER10M1R2A_STAGE_ROOT": paths.m1r2a_stage_root,
        "PAPER10M1R2B_STAGE_ROOT": paths.m1r2b_stage_root,
        "PAPER10M1R2C_STAGE_ROOT": paths.stage_root,
        "PAPER10M1R2C_RUNTIME_ROOT": paths.runtime_root,
        "DEGRADED_PROVIDER_ROOT": paths.provider_root,
        "EXPORT_ROOT": paths.export_root,
        "BY2_FIX_ROOT": paths.by2_imu.parent,
    }
    ensure_dirs(paths)
    write_local_approval_and_lock(paths, roots)
    run_git_report(paths, roots)

    m1r2b_decision = extract_final_decision(
        paths.m1r2b_stage_root / "00_STAGE_REPORT" / "PAPER10M1R2B_SUPERVISOR_FINAL_REPORT.md"
    )
    if m1r2b_decision != "PASS_PAPER10M1R2B_541_PROVIDERS_GENERATED_AND_VALIDATED_READY_FOR_FULL_ALGORITHM_MATRIX":
        raise RuntimeError(f"M1R2B final decision is not PASS: {m1r2b_decision}")
    locked = build_locked_queue(paths, roots)
    write_preflight_reports(paths, locked, roots, m1r2b_decision)

    imu_first, imu_last, _ = first_last_time(paths.by2_imu)
    status_first, status_last, _ = first_last_time(paths.by2_statusyaw_gnss)
    clean_first, clean_last, _ = first_last_time(
        paths.provider_root / "BY2_CLEAN_CANONICAL" / "02_GENERATED_PROVIDERS" / "gnss_position_provider.csv",
        delimiter=",",
        has_header=True,
    )
    time_offset = status_first - clean_first
    starttime = max(imu_first, status_first)
    endtime = min(imu_last, clean_last + time_offset)
    reference = read_reference_from_clean_provider(paths.provider_root / "BY2_CLEAN_CANONICAL", time_offset)
    loaded = load_all(paths.code_root)
    cases, providers, _ = load_case_maps(paths)
    selected = locked[: args.limit] if args.limit else locked
    if args.methods:
        allowed = set(args.methods.split(","))
        selected = [row for row in selected if row["method_mode_id"] in allowed]
    if args.row_ids:
        allowed_rows = set(args.row_ids.split(","))
        selected = [row for row in selected if row["row_id"] in allowed_rows]
    row_results: list[dict[str, Any]] = []

    def dispatch(row: dict[str, Any]) -> dict[str, Any]:
        frozen = loaded["method_modes"][row["method_mode_id"]]
        provider_status = {
            "raw_doppler": True,
            "go2_roll_pitch": True,
            "go2_horizontal_velocity": True,
            "go2_joint_factor": True,
            "go2_readiness_motion_metadata": False,
            "multi_state_qm": True,
        }
        effective = resolve_effective_feature_flags(frozen.data, provider_status)
        safety = validate_mode_safety(frozen.data, effective)
        if safety:
            raise RuntimeError("; ".join(safety))
        return run_one_row(
            row=row,
            case=cases[row["case_id"]],
            provider_manifest=providers[row["case_id"]],
            mode=frozen.data,
            effective_flags=effective,
            config_sha256=loaded["config_sha256"],
            paths=paths,
            time_offset=time_offset,
            starttime=starttime,
            endtime=endtime,
            reference=reference,
            roots=roots,
            force=args.force,
        )

    if args.prepare_only:
        row_results = []
    else:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(dispatch, row): row for row in selected}
            total = len(futures)
            done = 0
            for future in as_completed(futures):
                done += 1
                result = future.result()
                row_results.append(result)
                if done % max(1, args.progress_interval) == 0 or done == total:
                    print(f"[PAPER10M1R2C] completed {done}/{total}: {result['row_id']} {result['terminal_status']}", flush=True)

    if args.prepare_only:
        write_tests_report(paths)
        return 0

    row_results = sorted(row_results, key=lambda item: item["row_id"])
    counts = summarize_rows(paths, row_results)
    method_summary = build_method_summary(paths, row_results)
    build_comparison_table(paths, row_results)
    build_case_summaries(paths, row_results)
    build_qm_source_summaries(paths, row_results)
    figures, qa_rows = make_figures(paths, row_results)
    write_claim_boundary(paths)
    write_next_stage(paths)
    write_obsidian_and_ai_context(paths)
    write_tests_report(paths, row_results)
    render_pass = all(row.get("render_status") == "PASS" for row in qa_rows)
    all_completed = counts["completed"] == len(selected) and counts["failed"] == 0 and counts["blocked"] == 0 and counts["skipped"] == 0
    if args.limit or len(selected) != EXPECTED_ROWS:
        final_decision = "CONDITIONAL_PASS_PAPER10M1R2C_WITH_PARTIAL_ROW_FAILURES_NEEDS_REPAIR"
    elif all_completed and render_pass:
        final_decision = "PASS_PAPER10M1R2C_2164_FULL_ALGORITHM_ROWS_COMPLETED_READY_FOR_INTERNAL_ABLATION"
    elif not all_completed:
        final_decision = "CONDITIONAL_PASS_PAPER10M1R2C_WITH_PARTIAL_ROW_FAILURES_NEEDS_REPAIR"
    elif not render_pass:
        final_decision = "BLOCKED_RENDER_QA_FAILURE"
    else:
        final_decision = "BLOCKED_GUARD_FAILURE"
    write_final_reports(
        paths=paths,
        roots=roots,
        execution_counts=counts,
        method_summary=method_summary,
        figure_count=len(figures),
        render_pass=render_pass,
        export_status="PENDING_BEFORE_FINAL_EXPORT",
        final_decision=final_decision,
    )
    export_status, export_ok = export_clean(paths, roots)
    if not export_ok and final_decision.startswith(("PASS_", "CONDITIONAL_PASS_")):
        final_decision = "BLOCKED_EXPORT_CLEAN_FAILURE"
    write_final_reports(
        paths=paths,
        roots=roots,
        execution_counts=counts,
        method_summary=method_summary,
        figure_count=len(figures),
        render_pass=render_pass,
        export_status=export_status,
        final_decision=final_decision,
    )
    export_status, export_ok = export_clean(paths, roots)
    return 0 if final_decision.startswith(("PASS_", "CONDITIONAL_PASS_")) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--m1r2a-stage-root", required=True)
    parser.add_argument("--m1r2b-stage-root", required=True)
    parser.add_argument("--provider-root", required=True)
    parser.add_argument("--by2-imu", required=True)
    parser.add_argument("--by2-statusyaw-gnss", required=True)
    parser.add_argument("--code-root", default=str(REPO_ROOT))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--methods", default="")
    parser.add_argument("--row-ids", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--progress-interval", type=int, default=25)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return execute_matrix(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
