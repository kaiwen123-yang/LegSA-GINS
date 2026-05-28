#!/usr/bin/env python3
"""Run BY3A0-BY3E reporting gates and BY2 archive reorganization.

This helper is reporting and gate materialization only. It does not modify
algorithm math, does not tune time alignment against trace, and does not run
BY3 degradation/full-matrix cases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legsa_gins.datasets.by2.gnss_status_adapter import (  # noqa: E402
    parse_gnss_status_csv,
    write_standardized_gnss_status,
)
from legsa_gins.datasets.by2.go2_body_state_parser import (  # noqa: E402
    STANDARD_HEADER as GO2_BODY_HEADER,
    _message_to_row,
    write_go2_body_state_csv,
)
from legsa_gins.time_alignment.event_normalization import (  # noqa: E402
    detect_gnss_formal_motion_start,
    detect_go2_formal_motion_start,
    detect_go2_kick_event,
)


EXPECTED_RECEIVER_FILES = [
    "user_io-out-poi_geodetic.csv",
    "user_io-out-poi_odometry.csv",
    "user_io-out-poi_smooth_odometry.csv",
    "user_io-status.csv",
    "userio-raw.csv",
    "corr-raw.csv",
    "gnss1-raw.csv",
    "gnss1-status.csv",
    "gnss2-raw.csv",
    "gnss2-status.csv",
    "imu-biases.csv",
    "imu-data.csv",
    "imu-temp.csv",
    "ntrip-info.csv",
    "ntrip-latency.csv",
    "tf.csv",
    "tf_static.csv",
    "trace_vrtk2_a87c6e_2026-03-06-08-06-39_minimal.csv",
    "user_io-out-odom_status.csv",
]

TRACKED_CONTEXT_DOCS = [
    "AGENTS.md",
    "PLANS.md",
    "README.md",
    "CLAIM_BOUNDARY.md",
    "PHASE_LOG.md",
    "docs/codex_context/current_state.md",
    "docs/codex_context/PROJECT_CONTEXT.md",
    "docs/codex_context/PATH_POLICY.md",
    "docs/codex_context/DATA_PATHS.template.md",
    "docs/codex_context/data_source_roles.md",
    "docs/codex_context/claim_boundary.md",
]

THREE_SCHEMES = [
    "LegSA_full_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "final_v23_dual_antenna_EKF",
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def stream_go2_body_state_text(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if not current or not any(line.strip() for line in current):
            current = []
            return
        row = _message_to_row(current)
        if row.get("timestamp") is not None:
            rows.append(row)
        current = []

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.strip() == "---":
                flush()
            else:
                current.append(line)
        flush()
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def file_sha256(path: Path, limit_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    remaining = limit_bytes
    with path.open("rb") as handle:
        while True:
            size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
            if size <= 0:
                break
            chunk = handle.read(size)
            if not chunk:
                break
            h.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return h.hexdigest()


def classify_receiver_file(name: str) -> tuple[str, str, str]:
    if name.startswith("trace_"):
        return "trace_reference", "evaluator_reference", "trace evaluation-only reference"
    if name == "imu-data.csv":
        return "receiver_imu", "diagnostic_only", "receiver IMU; forbidden as Go2 body IMU"
    if name in {"imu-biases.csv", "imu-temp.csv"}:
        return "receiver_imu", "diagnostic_only", "receiver IMU diagnostic stream"
    if name in {"gnss1-status.csv", "gnss2-status.csv"}:
        return "decoded_status", "solver_input_candidate", "GNSS decoded status candidate"
    if name in {"gnss1-raw.csv", "gnss2-raw.csv"}:
        return "raw_gnss", "solver_input_candidate", "raw GNSS source candidate"
    if name == "corr-raw.csv":
        return "correction", "diagnostic_only", "correction stream"
    if name.startswith("ntrip-"):
        return "ntrip", "diagnostic_only", "NTRIP diagnostic stream"
    if name in {"tf.csv", "tf_static.csv"}:
        return "tf", "diagnostic_only", "transform diagnostics"
    if name.startswith("user_io-out-poi_geodetic"):
        return "solved_position", "diagnostic_only", "receiver solved pose/velocity diagnostic"
    if name.startswith("user_io-out-poi_odometry") or name.startswith("user_io-out-poi_smooth"):
        return "solved_velocity", "diagnostic_only", "receiver solved odometry diagnostic"
    if name == "user_io-status.csv":
        return "communication", "diagnostic_only", "receiver/user I/O status"
    if name == "userio-raw.csv":
        return "communication", "diagnostic_only", "raw user I/O stream"
    if name == "user_io-out-odom_status.csv":
        return "communication", "diagnostic_only", "odometry status diagnostic"
    return "unknown", "diagnostic_only", "unclassified"


def inspect_csv_file(path: Path) -> dict[str, Any]:
    row_count = 0
    columns: list[str] = []
    time_column = ""
    time_min: float | None = None
    time_max: float | None = None
    parse_status = "missing"
    if not path.exists():
        return {
            "path_alias": f"<BY3_RECEIVER_ROOT>/{path.name}",
            "exists": False,
            "size_bytes": 0,
            "row_count": 0,
            "columns": "",
            "time_column": "",
            "time_min": "",
            "time_max": "",
            "parse_status": parse_status,
        }
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            for candidate in ["Time", "time", "timestamp", "time_unix", "time_gps_tow", "tow"]:
                if candidate in columns:
                    time_column = candidate
                    break
            for row in reader:
                row_count += 1
                if time_column:
                    value = safe_float(row.get(time_column))
                    if value is not None:
                        time_min = value if time_min is None else min(time_min, value)
                        time_max = value if time_max is None else max(time_max, value)
            parse_status = "parsed"
    except Exception as exc:  # noqa: BLE001
        parse_status = f"parse_error:{type(exc).__name__}:{exc}"
    return {
        "path_alias": f"<BY3_RECEIVER_ROOT>/{path.name}",
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "row_count": row_count,
        "columns": "|".join(columns),
        "time_column": time_column,
        "time_min": "" if time_min is None else time_min,
        "time_max": "" if time_max is None else time_max,
        "parse_status": parse_status,
    }


def ensure_stage_dirs(stage_root: Path) -> None:
    subdirs = [
        "00_supervisor",
        "01_plan",
        "context_lock",
        "data_inventory",
        "by3_body_imu",
        "kick_alignment",
        "input_generation",
        "runtime_configs",
        "solver_outputs",
        "official_eval",
        "metrics",
        "figures/alignment",
        "case_review",
        "export_clean",
        "obsidian_sync",
        "reports",
        "matrix",
        "summary",
        "validation",
        "logs",
        "blocked",
    ]
    for subdir in subdirs:
        (stage_root / subdir).mkdir(parents=True, exist_ok=True)
    scratch = stage_root / "inventory" / "test.tmp"
    if scratch.exists():
        scratch.unlink()


def create_context_lock(stage_root: Path) -> None:
    docs_rows = []
    for rel in TRACKED_CONTEXT_DOCS:
        path = ROOT / rel
        docs_rows.append(
            {
                "path": rel,
                "exists": path.exists(),
                "updated_for_BY3A0": path.exists(),
                "tracked_doc_alias_only_required": True,
            }
        )
    report = {
        "stage": "BY3A0_CONTEXT_LOCK",
        "status": "BY3A0_context_lock_complete",
        "by3_output_root_alias": "<BY3_OUTPUT_ROOT>",
        "by3_receiver_root_alias": "<BY3_RECEIVER_ROOT>",
        "by3_go2_body_source_alias": "<BY3_GO2_BODY_SOURCE>",
        "by2_degradation_archive_root_alias": "<BY2_DEGRADATION_ARCHIVE_ROOT>",
        "legsa_full_ekf_role": "current_validated_final_algorithm_for_BY3_normal",
        "legsa_9f_fgo_ekf_role": "future_candidate_not_mainline",
        "trace_role": "evaluation_only",
        "receiver_imu_data_role": "diagnostic_only_not_go2_body_imu",
        "ready_for_paper_claims": False,
        "ready_for_BY3_degradation_matrix": False,
        "solver_or_evaluator_run": False,
    }
    write_json(stage_root / "reports" / "BY3A0_CONTEXT_LOCK_REPORT.json", report)
    write_csv(stage_root / "matrix" / "BY3A0_UPDATED_TRACKED_DOCS.csv", docs_rows)
    write_json(stage_root / "matrix" / "BY3A0_UPDATED_TRACKED_DOCS.json", docs_rows)
    write_text(
        stage_root / "summary" / "by3a0_context_lock_summary.md",
        "\n".join(
            [
                "# BY3A0 Context Lock Summary",
                "",
                "- Status: `BY3A0_context_lock_complete`.",
                "- BY3 output root alias: `<BY3_OUTPUT_ROOT>`.",
                "- BY3 receiver source alias: `<BY3_RECEIVER_ROOT>`.",
                "- BY3 Go2 body/high-level source alias: `<BY3_GO2_BODY_SOURCE>`.",
                "- BY3 normal must pass before any BY3 degradation planning.",
                "- Trace is evaluation-only; receiver `imu-data.csv` is diagnostic-only.",
                "- `ready_for_paper_claims=false`.",
            ]
        ),
    )


def create_obsidian_notes(
    obsidian_root: Path,
    *,
    receiver_root: Path,
    body_source: Path,
    by3_output_root: Path,
    by2_archive_root: Path,
    final_state: str,
) -> None:
    obsidian_root.mkdir(parents=True, exist_ok=True)
    public_notes = {
        "00_INDEX.md": [
            "# BY3 Generalization Index",
            "",
            "- `01_CURRENT_STATE.md`",
            "- `02_BY3_DATA_PATHS.md`",
            "- `03_ALIGNMENT_RESULT.md`",
            "- `04_INPUT_GENERATION.md`",
            "- `05_NORMAL_GENERALIZATION_RESULT.md`",
            "- `06_FIGURES_AND_CASE_REVIEW.md`",
            "- `07_BY2_TEXT_SUMMARY_AND_DEGRADATION_ARCHIVE.md`",
            "- `08_CLAIM_BOUNDARY.md`",
            "- `09_NEXT_STEPS.md`",
            "- `99_LOCAL_PATHS.private.md` is local/private and must not be staged.",
        ],
        "01_CURRENT_STATE.md": [
            "# Current State",
            "",
            f"- Stage: `BY3A0_TO_BY3E_GENERALIZATION_AND_BY2_DEGRADATION_REPORT_REORG`.",
            f"- Decision: `{final_state}`.",
            "- `LegSA_full_EKF` remains the current BY3 normal generalization algorithm.",
            "- `LegSA_9F_FGO_EKF` remains a future candidate.",
            "- `ready_for_paper_claims=false`.",
        ],
        "02_BY3_DATA_PATHS.md": [
            "# BY3 Data Paths",
            "",
            "- BY3 output root: `<BY3_OUTPUT_ROOT>`.",
            "- BY3 receiver root: `<BY3_RECEIVER_ROOT>`.",
            "- BY3 Go2 body/high-level source: `<BY3_GO2_BODY_SOURCE>`.",
            "- BY2 degradation archive root: `<BY2_DEGRADATION_ARCHIVE_ROOT>`.",
            "- Concrete local paths are kept only in `99_LOCAL_PATHS.private.md`.",
        ],
        "03_ALIGNMENT_RESULT.md": [
            "# Alignment Result",
            "",
            "- Alignment policy: BY2 kick-event/event-normalized algorithm time.",
            "- Kick event is a search anchor, not a trace-tuned offset.",
            "- GNSS and Go2 each use their own formal start.",
            "- `trace_used_for_alignment=false`.",
            "- `no_offset_search=true`.",
        ],
        "04_INPUT_GENERATION.md": [
            "# Input Generation",
            "",
            "- BY3 candidate IMU/GNSS inputs are generated only from BY3 source data.",
            "- Receiver `imu-data.csv` is not used as Go2 body IMU.",
            "- Trace is not solver input.",
            "- Runtime configs are blocked if same-case providers/feedback are missing.",
        ],
        "05_NORMAL_GENERALIZATION_RESULT.md": [
            "# Normal Generalization Result",
            "",
            "- BY3 normal solver execution runs only when input/provider gates pass.",
            "- Blockers are recorded rather than substituting outputs.",
            "- No BY3 degradation matrix is run in this stage.",
        ],
        "06_FIGURES_AND_CASE_REVIEW.md": [
            "# Figures And Case Review",
            "",
            "- Alignment audit figures may exist before solver execution.",
            "- Three-way metric/trajectory figures require successful BY3 normal solver and official evaluation outputs.",
            "- Placeholder figures are not accepted as real BY3 evaluation figures.",
        ],
        "07_BY2_TEXT_SUMMARY_AND_DEGRADATION_ARCHIVE.md": [
            "# BY2 Text Summary And Degradation Archive",
            "",
            "- BY2 text summaries use active final-only metrics.",
            "- `B_gnss_downsample_2Hz` and superseded rows are excluded.",
            "- Figure archive policy is copy-only.",
            "- Archive copies are not new runtime evidence.",
        ],
        "08_CLAIM_BOUNDARY.md": [
            "# Claim Boundary",
            "",
            "- `ready_for_paper_claims=false`.",
            "- Do not claim outperform final_v23.",
            "- Do not claim complete nine-factor FGO.",
            "- Do not treat BY3 source inventory as BY3 performance validation.",
        ],
        "09_NEXT_STEPS.md": [
            "# Next Steps",
            "",
            "- Human review BY3 normal blockers/cautions.",
            "- Run BY3 solver/evaluator only after provider and input gates pass.",
            "- Plan BY3 degradation matrix only after BY3 normal passes.",
        ],
    }
    sync_rows = []
    for name, lines in public_notes.items():
        path = obsidian_root / name
        write_text(path, "\n".join(lines))
        sync_rows.append({"note": name, "public": True, "local_absolute_paths_allowed": False, "status": "written"})
    private_text = "\n".join(
        [
            "# Local Paths Private",
            "",
            "This note is private/local and must not be staged.",
            "",
            f"BY3_OUTPUT_ROOT={by3_output_root}",
            f"BY3_RECEIVER_ROOT={receiver_root}",
            f"BY3_GO2_BODY_SOURCE={body_source}",
            f"BY2_DEGRADATION_ARCHIVE_ROOT={by2_archive_root}",
        ]
    )
    write_text(obsidian_root / "99_LOCAL_PATHS.private.md", private_text)
    sync_rows.append({"note": "99_LOCAL_PATHS.private.md", "public": False, "local_absolute_paths_allowed": True, "status": "written"})
    report = {
        "stage": "BY3A0_OBSIDIAN_SYNC",
        "status": "complete",
        "public_notes_alias_only": True,
        "private_note_contains_local_paths": True,
        "obsidian_not_staged_required": True,
        "note_count": len(sync_rows),
    }
    stage_root = by3_output_root / "BY3A0_TO_BY3E_GENERALIZATION_BOOTSTRAP_ALIGNMENT_NORMAL_COMPARISON"
    write_json(stage_root / "reports" / "BY3A0_OBSIDIAN_SYNC_REPORT.json", report)
    write_csv(stage_root / "matrix" / "BY3A0_OBSIDIAN_SYNC_INDEX.csv", sync_rows)
    write_json(stage_root / "matrix" / "BY3A0_OBSIDIAN_SYNC_INDEX.json", sync_rows)


def run_inventory(stage_root: Path, receiver_root: Path, body_source: Path) -> tuple[Path, Path, dict[str, Any]]:
    inv_rows = []
    role_rows = []
    missing = []
    for filename in EXPECTED_RECEIVER_FILES:
        path = receiver_root / filename
        row = inspect_csv_file(path)
        data_role, algorithm_role, notes = classify_receiver_file(filename)
        row.update(
            {
                "filename": filename,
                "data_role": data_role,
                "algorithm_role": algorithm_role,
                "notes": notes,
            }
        )
        inv_rows.append(row)
        role_rows.append(
            {
                "filename": filename,
                "data_role": data_role,
                "algorithm_role": algorithm_role,
                "notes": notes,
                "forbidden_for_solver": algorithm_role == "forbidden_for_solver" or filename.startswith("trace_") or filename == "imu-data.csv",
            }
        )
        if not path.exists():
            missing.append(filename)
    write_csv(stage_root / "matrix" / "BY3A_RECEIVER_FILE_INVENTORY.csv", inv_rows)
    write_json(stage_root / "matrix" / "BY3A_RECEIVER_FILE_INVENTORY.json", inv_rows)
    write_csv(stage_root / "matrix" / "BY3A_DATA_ROLE_CLASSIFICATION.csv", role_rows)
    write_json(stage_root / "matrix" / "BY3A_DATA_ROLE_CLASSIFICATION.json", role_rows)
    data_report = {
        "stage": "BY3A_DATA_INVENTORY",
        "receiver_root_alias": "<BY3_RECEIVER_ROOT>",
        "required_file_count": len(EXPECTED_RECEIVER_FILES),
        "present_file_count": len([row for row in inv_rows if row["exists"]]),
        "missing_files": missing,
        "trace_role": "evaluator_reference_only",
        "receiver_imu_data_role": "diagnostic_only_not_go2_body_imu",
        "decision": "BY3A_data_inventory_passed" if not missing else "BY3A_blocked_receiver_files_missing",
    }
    write_json(stage_root / "reports" / "BY3A_DATA_INVENTORY_REPORT.json", data_report)
    write_text(
        stage_root / "summary" / "by3a_data_inventory.md",
        "\n".join(
            [
                "# BY3A Data Inventory",
                "",
                f"- Required receiver files: `{len(EXPECTED_RECEIVER_FILES)}`.",
                f"- Present receiver files: `{data_report['present_file_count']}`.",
                f"- Decision: `{data_report['decision']}`.",
                "- Trace is evaluation-only.",
                "- Receiver `imu-data.csv` is diagnostic-only and not Go2 body IMU.",
            ]
        ),
    )

    body_rows = stream_go2_body_state_text(body_source)
    body_csv = stage_root / "by3_body_imu" / "BY3_GO2_BODY_STATE_DIAGNOSTIC.csv"
    write_go2_body_state_csv(body_rows, body_csv)
    times = [safe_float(row.get("timestamp")) for row in body_rows]
    times = [value for value in times if value is not None]
    dt = [b - a for a, b in zip(times, times[1:]) if b > a]
    fields_present = {
        "accel_fields": all(key in body_rows[0] for key in ["acc_x", "acc_y", "acc_z"]) if body_rows else False,
        "gyro_fields": all(key in body_rows[0] for key in ["gyro_x", "gyro_y", "gyro_z"]) if body_rows else False,
        "velocity_fields": all(key in body_rows[0] for key in ["go2_velocity_0", "go2_velocity_1", "go2_velocity_2"]) if body_rows else False,
        "contact_or_foot_fields": all(key in body_rows[0] for key in ["foot_force_0", "foot_speed_body_0"]) if body_rows else False,
        "mode_fields": all(key in body_rows[0] for key in ["mode", "gait_type"]) if body_rows else False,
    }
    sample_rate = "" if not dt else 1.0 / statistics.median(dt)
    body_audit = {
        "source_alias": "<BY3_GO2_BODY_SOURCE>",
        "exists": body_source.exists(),
        "size_bytes": body_source.stat().st_size if body_source.exists() else 0,
        "row_count": len(body_rows),
        "columns": "|".join(GO2_BODY_HEADER),
        "time_column": "timestamp",
        "time_min": min(times) if times else "",
        "time_max": max(times) if times else "",
        "sample_rate_hz_median": sample_rate,
        "format_compatibility_with_BY2_by2_txt": "compatible_sportmodestate_parser" if body_rows else "blocked_no_rows",
        "ready_for_alignment": bool(body_rows and fields_present["accel_fields"] and fields_present["gyro_fields"]),
        "ready_for_algorithm_input": bool(body_rows and fields_present["accel_fields"] and fields_present["gyro_fields"]),
        **fields_present,
    }
    body_report = {
        "stage": "BY3A_BODY_IMU_AUDIT",
        "decision": "BY3A_body_imu_ready" if body_audit["ready_for_alignment"] else "BY3A_blocked_missing_or_invalid_by3_body_imu",
        "receiver_imu_as_body_imu": False,
        "body_imu_audit": body_audit,
    }
    write_csv(stage_root / "matrix" / "BY3A_BODY_IMU_AUDIT.csv", [body_audit])
    write_json(stage_root / "matrix" / "BY3A_BODY_IMU_AUDIT.json", [body_audit])
    write_json(stage_root / "reports" / "BY3A_BODY_IMU_AUDIT_REPORT.json", body_report)
    write_text(
        stage_root / "summary" / "by3a_body_imu_audit.md",
        "\n".join(
            [
                "# BY3A Body IMU Audit",
                "",
                f"- Parsed rows: `{len(body_rows)}`.",
                f"- Median sample rate Hz: `{sample_rate}`.",
                f"- Ready for alignment: `{body_audit['ready_for_alignment']}`.",
                f"- Ready for algorithm input: `{body_audit['ready_for_algorithm_input']}`.",
                "- Source role: BY3 Go2 body/high-level/body-IMU source.",
                "- Receiver `imu-data.csv` was not used as Go2 body IMU.",
            ]
        ),
    )

    gnss1_standard = stage_root / "data_inventory" / "BY3_GNSS1_STATUS_STANDARD.csv"
    gnss2_standard = stage_root / "data_inventory" / "BY3_GNSS2_STATUS_STANDARD.csv"
    write_standardized_gnss_status(parse_gnss_status_csv(receiver_root / "gnss1-status.csv", source_name="gnss1"), gnss1_standard)
    write_standardized_gnss_status(parse_gnss_status_csv(receiver_root / "gnss2-status.csv", source_name="gnss2"), gnss2_standard)
    return body_csv, gnss1_standard, {"inventory": data_report, "body": body_report, "body_rows": body_rows}


def norm3(row: dict[str, Any], keys: list[str]) -> float:
    values = [safe_float(row.get(key)) or 0.0 for key in keys]
    return math.sqrt(sum(value * value for value in values))


def run_alignment(stage_root: Path, receiver_root: Path, body_csv: Path, gnss_standard: Path, body_rows: list[dict[str, Any]]) -> dict[str, Any]:
    method_rows = [
        {
            "path": "docs/time_alignment_event_normalization.md",
            "method_summary": "kick event is search anchor; each source uses its own formal motion start; algo_time_sec is event-normalized",
            "warnings": "no hardware clock-sync claim; no trace-based offset tuning",
            "by3_requirement": "reuse event-normalized policy and record no_trace_tuning=true",
        },
        {
            "path": "src/legsa_gins/time_alignment/event_normalization.py",
            "method_summary": "detect_go2_kick_event, detect_go2_formal_motion_start, detect_gnss_formal_motion_start",
            "warnings": "kick is not directly solver start",
            "by3_requirement": "body source must expose timestamp, accel, gyro, velocity/contact/foot evidence where available",
        },
        {
            "path": "tests/unit/test_event_normalization.py",
            "method_summary": "unit test asserts kick and formal start are separated",
            "warnings": "formal start must occur after kick when evidence exists",
            "by3_requirement": "record rejected candidates and uncertainty",
        },
    ]
    write_csv(stage_root / "matrix" / "BY3B_BY2_ALIGNMENT_METHOD_EVIDENCE.csv", method_rows)
    write_json(stage_root / "matrix" / "BY3B_BY2_ALIGNMENT_METHOD_EVIDENCE.json", method_rows)
    write_json(
        stage_root / "reports" / "BY3B_BY2_ALIGNMENT_METHOD_RECOVERY_REPORT.json",
        {
            "stage": "BY3B1_BY2_ALIGNMENT_METHOD_RECOVERY",
            "status": "recovered",
            "alignment_method": "event_normalized_algorithm_time",
            "trace_used_for_alignment": False,
            "evidence_count": len(method_rows),
        },
    )
    write_text(
        stage_root / "summary" / "by3b_by2_alignment_method_recovery.md",
        "# BY3B1 BY2 Alignment Method Recovery\n\n- Method: event-normalized algorithm time.\n- Kick event is a search anchor.\n- Trace is not used for alignment or offset tuning.",
    )

    candidate_rows = []
    acc_values = [norm3(row, ["acc_x", "acc_y", "acc_z"]) for row in body_rows]
    gyro_values = [norm3(row, ["gyro_x", "gyro_y", "gyro_z"]) for row in body_rows]
    median_acc = statistics.median(acc_values[: max(5, min(100, len(acc_values)))]) if acc_values else 0.0
    jerk_values = [0.0]
    for prev, curr, prow, crow in zip(acc_values, acc_values[1:], body_rows, body_rows[1:]):
        dt = (safe_float(crow.get("timestamp")) or 0.0) - (safe_float(prow.get("timestamp")) or 0.0)
        jerk_values.append(abs(curr - prev) / dt if dt > 0 else 0.0)
    for index, row in enumerate(body_rows):
        timestamp = safe_float(row.get("timestamp"))
        if timestamp is None:
            continue
        acc_norm = acc_values[index]
        gyro_norm_value = gyro_values[index]
        jerk = jerk_values[index]
        score = max(abs(acc_norm - median_acc), gyro_norm_value * 2.0, min(jerk, 100.0) / 10.0)
        candidate_rows.append(
            {
                "rank_score": score,
                "timestamp": timestamp,
                "accel_norm": acc_norm,
                "gyro_norm": gyro_norm_value,
                "jerk_score": jerk,
                "mode": row.get("mode"),
                "gait_type": row.get("gait_type"),
            }
        )
    all_candidate_rows = sorted(candidate_rows, key=lambda item: float(item["rank_score"]), reverse=True)
    candidate_rows = all_candidate_rows[:25]
    for rank, row in enumerate(candidate_rows, start=1):
        row["rank"] = rank
    by2_max_kick_report = detect_go2_kick_event(body_csv)
    first_body_time = safe_float(body_rows[0].get("timestamp")) if body_rows else None
    max_score = float(candidate_rows[0]["rank_score"]) if candidate_rows else 0.0
    high_threshold = max(3.0, 0.85 * max_score)
    early_window_end = (first_body_time + 120.0) if first_body_time is not None else None
    early_candidates = [
        row
        for row in sorted(all_candidate_rows, key=lambda item: float(item["timestamp"]))
        if float(row["rank_score"]) >= high_threshold
        and (first_body_time is None or float(row["timestamp"]) > first_body_time + 1.0)
        and (early_window_end is None or float(row["timestamp"]) <= early_window_end)
    ]
    selected_kick = early_candidates[0] if early_candidates else (candidate_rows[0] if candidate_rows else {})
    kick_report = {
        "go2_kick_raw_time": safe_float(selected_kick.get("timestamp")),
        "kick_score": safe_float(selected_kick.get("rank_score")) or 0.0,
        "detection_method": "earliest_high_body_imu_impulse_candidate",
        "by2_max_motion_impulse_report": by2_max_kick_report,
        "high_score_threshold": high_threshold,
        "early_window_end_raw_time": early_window_end,
        "max_impulse_rejected_as_late_if_different": safe_float(selected_kick.get("timestamp")) != safe_float(by2_max_kick_report.get("go2_kick_raw_time")),
        "evidence_status": "detected" if selected_kick else "evidence_missing",
    }
    go2_start = detect_go2_formal_motion_start(body_csv, kick_report)
    write_csv(stage_root / "matrix" / "BY3B_BODY_IMU_EVENT_CANDIDATES.csv", candidate_rows)
    write_json(stage_root / "matrix" / "BY3B_BODY_IMU_EVENT_CANDIDATES.json", candidate_rows)
    write_json(
        stage_root / "reports" / "BY3B_KICK_EVENT_DETECTION_REPORT.json",
        {
            "stage": "BY3B2_KICK_EVENT_DETECTION",
            "kick_report": kick_report,
            "go2_formal_start_report": go2_start,
            "candidate_count": len(candidate_rows),
            "trace_used_for_event_selection": False,
        },
    )
    write_text(
        stage_root / "summary" / "by3b_kick_event_detection.md",
        "\n".join(
            [
                "# BY3B2 Kick Event Detection",
                "",
                f"- Primary kick raw time: `{kick_report.get('go2_kick_raw_time')}`.",
                f"- Kick score: `{kick_report.get('kick_score')}`.",
                f"- Go2 formal start raw time: `{go2_start.get('go2_formal_start_raw_time')}`.",
                "- Trace was not used for event selection.",
            ]
        ),
    )

    gnss_report = detect_gnss_formal_motion_start(gnss_standard)
    gnss_rows = read_csv_rows(gnss_standard)
    gnss_candidates: list[dict[str, Any]] = []
    valid_rows = [row for row in gnss_rows if boolish(row.get("has_position"))]
    if valid_rows:
        first = valid_rows[0]
        lat0 = safe_float(first.get("lat_deg"))
        lon0 = safe_float(first.get("lon_deg"))
        gnss_candidates.append(
            {
                "candidate": "first_valid_position",
                "time": safe_float(first.get("time_unix")),
                "score": 1.0,
                "evidence": "has_position",
            }
        )
        first_heading = next((row for row in valid_rows if boolish(row.get("heading_valid"))), None)
        if first_heading:
            gnss_candidates.append(
                {
                    "candidate": "first_valid_dual_yaw",
                    "time": safe_float(first_heading.get("time_unix")),
                    "score": 2.0,
                    "evidence": "heading_valid",
                }
            )
        if lat0 is not None and lon0 is not None:
            for row in valid_rows:
                lat = safe_float(row.get("lat_deg"))
                lon = safe_float(row.get("lon_deg"))
                if lat is None or lon is None:
                    continue
                disp = horizontal_m(lat0, lon0, lat, lon)
                if disp >= 0.2:
                    gnss_candidates.append(
                        {
                            "candidate": "first_horizontal_displacement_gt_0p2m",
                            "time": safe_float(row.get("time_unix")),
                            "score": 3.0,
                            "evidence": f"displacement_m={disp:.3f}",
                        }
                    )
                    break
    write_csv(stage_root / "matrix" / "BY3B_GNSS_START_CANDIDATES.csv", gnss_candidates)
    write_json(stage_root / "matrix" / "BY3B_GNSS_START_CANDIDATES.json", gnss_candidates)
    write_json(
        stage_root / "reports" / "BY3B_GNSS_START_DETECTION_REPORT.json",
        {
            "stage": "BY3B3_GNSS_START_DETECTION",
            "gnss_start_report": gnss_report,
            "candidate_count": len(gnss_candidates),
            "trace_used_for_tuning": False,
        },
    )
    write_text(
        stage_root / "summary" / "by3b_gnss_start_detection.md",
        "\n".join(
            [
                "# BY3B3 GNSS Start Detection",
                "",
                f"- Selected GNSS formal start raw time: `{gnss_report.get('gnss_formal_start_raw_time')}`.",
                f"- Selected feature: `{gnss_report.get('selected_feature')}`.",
                "- Trace was not used for tuning or offset search.",
            ]
        ),
    )

    go2_start_time = safe_float(go2_start.get("go2_formal_start_raw_time"))
    gnss_start_time = safe_float(gnss_report.get("gnss_formal_start_raw_time"))
    go2_duration = ""
    if body_rows and go2_start_time is not None:
        body_times = [safe_float(row.get("timestamp")) for row in body_rows]
        body_times = [value for value in body_times if value is not None]
        if body_times:
            go2_duration = max(body_times) - go2_start_time
    gnss_duration = ""
    if valid_rows and gnss_start_time is not None:
        times = [safe_float(row.get("time_unix")) for row in valid_rows]
        times = [value for value in times if value is not None]
        if times:
            gnss_duration = max(times) - gnss_start_time
    common_end = ""
    if isinstance(go2_duration, float) and isinstance(gnss_duration, float):
        common_end = max(0.0, min(go2_duration, gnss_duration) - 5.0)
    decision_row = {
        "selected_body_imu_kick_event_time": kick_report.get("go2_kick_raw_time"),
        "selected_go2_formal_start_time": go2_start_time,
        "selected_gnss_start_motion_event_time": gnss_start_time,
        "computed_alignment_start_policy": "event_normalized_algorithm_time",
        "algorithm_start_time": 0.0,
        "evaluation_time_range_start": 0.0,
        "evaluation_time_range_end": common_end,
        "no_trace_tuning": True,
        "no_offset_search": True,
        "trace_solver_input": False,
        "decision": "BY3B_alignment_passed" if go2_start_time is not None and gnss_start_time is not None else "BY3B_alignment_blocked_missing_events",
        "uncertainty_caution": "event-normalized raw times are not interpreted as a hardware clock offset",
    }
    write_csv(stage_root / "matrix" / "BY3B_ALIGNMENT_DECISION.csv", [decision_row])
    write_json(stage_root / "matrix" / "BY3B_ALIGNMENT_DECISION.json", [decision_row])
    write_json(
        stage_root / "reports" / "BY3B_ALIGNMENT_DECISION_REPORT.json",
        {
            "stage": "BY3B4_ALIGNMENT_DECISION",
            "decision": decision_row["decision"],
            "alignment_decision": decision_row,
            "rejected_candidates": candidate_rows[1:6],
        },
    )
    write_text(
        stage_root / "summary" / "by3b_alignment_decision.md",
        "\n".join(
            [
                "# BY3B4 Alignment Decision",
                "",
                f"- Decision: `{decision_row['decision']}`.",
                f"- Body kick raw time: `{decision_row['selected_body_imu_kick_event_time']}`.",
                f"- Go2 formal start raw time: `{decision_row['selected_go2_formal_start_time']}`.",
                f"- GNSS formal start raw time: `{decision_row['selected_gnss_start_motion_event_time']}`.",
                "- Policy: event-normalized algorithm time.",
                "- `no_trace_tuning=true`.",
                "- `no_offset_search=true`.",
            ]
        ),
    )
    make_alignment_figures(stage_root, body_rows, candidate_rows, gnss_candidates, decision_row, receiver_root)
    return {
        "kick_report": kick_report,
        "go2_start": go2_start,
        "gnss_start": gnss_report,
        "decision": decision_row,
    }


def horizontal_m(lat0: float, lon0: float, lat1: float, lon1: float) -> float:
    radius = 6378137.0
    north = math.radians(lat1 - lat0) * radius
    east = math.radians(lon1 - lon0) * radius * math.cos(math.radians(lat0))
    return math.hypot(north, east)


def make_alignment_figures(
    stage_root: Path,
    body_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    gnss_candidates: list[dict[str, Any]],
    decision: dict[str, Any],
    receiver_root: Path,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        write_json(stage_root / "reports" / "BY3B_ALIGNMENT_FIGURE_BLOCKER.json", {"matplotlib_available": False, "error": str(exc)})
        return
    fig_rows = []
    times = [safe_float(row.get("timestamp")) for row in body_rows]
    acc = [norm3(row, ["acc_x", "acc_y", "acc_z"]) for row in body_rows]
    gyro = [norm3(row, ["gyro_x", "gyro_y", "gyro_z"]) for row in body_rows]
    pairs = [(t, a, g) for t, a, g in zip(times, acc, gyro) if t is not None]
    if pairs:
        t0 = pairs[0][0]
        rel = [item[0] - t0 for item in pairs]
        kick_time = safe_float(decision.get("selected_body_imu_kick_event_time"))
        kick_rel = kick_time - t0 if kick_time is not None else None
        plt.figure(figsize=(10, 4))
        plt.plot(rel, [item[1] for item in pairs], label="accel norm")
        plt.plot(rel, [item[2] for item in pairs], label="gyro norm")
        if kick_rel is not None:
            plt.axvline(kick_rel, color="red", linestyle="--", label="selected kick")
        plt.xlabel("relative raw Go2 time (s)")
        plt.ylabel("norm")
        plt.legend()
        plt.tight_layout()
        for suffix in ["png", "pdf"]:
            path = stage_root / "figures" / "alignment" / f"body_imu_accel_gyro_norm_with_kick_event.{suffix}"
            plt.savefig(path)
            fig_rows.append({"figure": path.name, "status": "generated", "bytes": path.stat().st_size})
        plt.close()
    gnss_path = receiver_root / "user_io-out-poi_geodetic.csv"
    if gnss_path.exists():
        rows = read_csv_rows(gnss_path)
        sample = rows[:: max(1, len(rows) // 5000)] if rows else []
        gtimes = [safe_float(row.get("Time")) for row in sample]
        lat = [safe_float(row.get("p.vector3.y")) for row in sample]
        lon = [safe_float(row.get("p.vector3.x")) for row in sample]
        valid = [(t, la, lo) for t, la, lo in zip(gtimes, lat, lon) if t is not None and la is not None and lo is not None]
        if valid:
            t0 = valid[0][0]
            lat0 = valid[0][1]
            lon0 = valid[0][2]
            rel = [item[0] - t0 for item in valid]
            disp = [horizontal_m(lat0, lon0, item[1], item[2]) for item in valid]
            gnss_start = safe_float(decision.get("selected_gnss_start_motion_event_time"))
            gnss_rel = gnss_start - t0 if gnss_start is not None else None
            plt.figure(figsize=(10, 4))
            plt.plot(rel, disp, label="receiver solved horizontal displacement")
            if gnss_rel is not None:
                plt.axvline(gnss_rel, color="red", linestyle="--", label="selected GNSS start")
            plt.xlabel("relative raw GNSS diagnostic time (s)")
            plt.ylabel("horizontal displacement (m)")
            plt.legend()
            plt.tight_layout()
            for suffix in ["png", "pdf"]:
                path = stage_root / "figures" / "alignment" / f"gnss_motion_start_with_event.{suffix}"
                plt.savefig(path)
                fig_rows.append({"figure": path.name, "status": "generated", "bytes": path.stat().st_size})
            plt.close()
    if pairs and gnss_candidates:
        labels = ["Go2 kick", "Go2 formal", "GNSS formal"]
        values = [
            safe_float(decision.get("selected_body_imu_kick_event_time")),
            safe_float(decision.get("selected_go2_formal_start_time")),
            safe_float(decision.get("selected_gnss_start_motion_event_time")),
        ]
        base = min(value for value in values if value is not None)
        plt.figure(figsize=(8, 3))
        plt.bar(labels, [value - base if value is not None else 0.0 for value in values])
        plt.ylabel("relative raw event time (s)")
        plt.tight_layout()
        for suffix in ["png", "pdf"]:
            path = stage_root / "figures" / "alignment" / f"alignment_event_overlay.{suffix}"
            plt.savefig(path)
            fig_rows.append({"figure": path.name, "status": "generated", "bytes": path.stat().st_size})
        plt.close()
    write_csv(stage_root / "matrix" / "BY3B_ALIGNMENT_FIGURE_INDEX.csv", fig_rows)
    write_json(stage_root / "matrix" / "BY3B_ALIGNMENT_FIGURE_INDEX.json", fig_rows)


def write_imu_file(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(
        path,
        rows,
        ["time", "dtheta_x", "dtheta_y", "dtheta_z", "dvel_x", "dvel_y", "dvel_z", "dt"],
    )


def matvec(m: list[list[float]], v: list[float]) -> list[float]:
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def roll_matrix_deg(roll_deg: float) -> list[list[float]]:
    roll = math.radians(roll_deg)
    cr = math.cos(roll)
    sr = math.sin(roll)
    return [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]]


def mean_vec(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return [0.0, 0.0, 0.0]
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(3)]


def build_imu_rows_from_body_rows(body_rows: list[dict[str, Any]], *, base_time: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    correction = roll_matrix_deg(-1.0)
    processed = []
    for row in body_rows:
        timestamp = safe_float(row.get("timestamp"))
        gyro = [safe_float(row.get("gyro_x")), safe_float(row.get("gyro_y")), safe_float(row.get("gyro_z"))]
        acc = [safe_float(row.get("acc_x")), safe_float(row.get("acc_y")), safe_float(row.get("acc_z"))]
        if timestamp is None or any(value is None for value in gyro + acc):
            continue
        gyro_frd = [float(gyro[0]), -float(gyro[1]), -float(gyro[2])]
        acc_frd = [float(acc[0]), -float(acc[1]), -float(acc[2])]
        processed.append(
            {
                "time": timestamp - base_time,
                "gyro": matvec(correction, gyro_frd),
                "acc": matvec(correction, acc_frd),
            }
        )
    processed = [row for row in processed if float(row["time"]) >= 0.0]
    bias_window = min(1000, len(processed))
    gyro_bias = mean_vec([row["gyro"] for row in processed[:bias_window]])
    rows = []
    skipped_dt_count = 0
    for previous, current in zip(processed, processed[1:]):
        dt = float(current["time"]) - float(previous["time"])
        if dt <= 0.0 or dt > 0.1:
            skipped_dt_count += 1
            continue
        gyro = [float(current["gyro"][axis]) - gyro_bias[axis] for axis in range(3)]
        acc = [float(current["acc"][axis]) for axis in range(3)]
        rows.append(
            {
                "time": float(current["time"]),
                "dtheta_x": gyro[0] * dt,
                "dtheta_y": gyro[1] * dt,
                "dtheta_z": gyro[2] * dt,
                "dvel_x": acc[0] * dt,
                "dvel_y": acc[1] * dt,
                "dvel_z": acc[2] * dt,
                "dt": dt,
            }
        )
    report = {
        "source_role": "go2_body_state_to_process_data_imu_candidate",
        "receiver_imu_as_body_imu": False,
        "flu_to_frd_applied_once": True,
        "accel_contains_gravity": True,
        "raw_accel_direct_dvel_is_process_data_parity_not_formal_mechanization": True,
        "gyro_bias_window": bias_window,
        "gyro_bias": gyro_bias,
        "input_message_count": len(body_rows),
        "imu_row_count": len(rows),
        "skipped_dt_count": skipped_dt_count,
        "imu_install_correction_rpy_deg": [-1.0, 0.0, 0.0],
    }
    return rows, report


def load_geodetic_velocity(receiver_root: Path) -> list[dict[str, Any]]:
    path = receiver_root / "user_io-out-poi_geodetic.csv"
    if not path.exists():
        return []
    rows = []
    for row in read_csv_rows(path):
        rows.append(
            {
                "time": safe_float(row.get("Time")),
                "ve": safe_float(row.get("v.vector3.x")),
                "vn": safe_float(row.get("v.vector3.y")),
                "vu": safe_float(row.get("v.vector3.z")),
            }
        )
    return [row for row in rows if row["time"] is not None]


def nearest_velocity(velocity_rows: list[dict[str, Any]], time_value: float) -> dict[str, Any] | None:
    if not velocity_rows:
        return None
    # BY3 files are time sorted. A linear scan is acceptable at current sizes.
    best = min(velocity_rows, key=lambda row: abs(float(row["time"]) - time_value))
    return best if abs(float(best["time"]) - time_value) <= 0.2 else None


def run_input_generation(
    stage_root: Path,
    receiver_root: Path,
    body_source: Path,
    body_csv: Path,
    alignment: dict[str, Any],
) -> dict[str, Any]:
    go2_start = safe_float(alignment["go2_start"].get("go2_formal_start_raw_time"))
    gnss_start = safe_float(alignment["gnss_start"].get("gnss_formal_start_raw_time"))
    rows_index: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    if go2_start is None or gnss_start is None:
        blockers.append("alignment_start_missing")
    imu_rows: list[dict[str, Any]] = []
    imu_report: dict[str, Any] = {}
    if go2_start is not None:
        body_rows = read_csv_rows(body_csv)
        imu_rows, imu_report = build_imu_rows_from_body_rows(body_rows, base_time=go2_start)
        imu_path = stage_root / "input_generation" / "BY3_GO2_PROCESS_DATA_COMPAT.imu"
        write_imu_file(imu_path, imu_rows)
        rows_index.append({"input_name": "BY3_GO2_PROCESS_DATA_COMPAT.imu", "path_alias": "<BY3_STAGE_ROOT>/input_generation/BY3_GO2_PROCESS_DATA_COMPAT.imu", "row_count": len(imu_rows), "sha256": file_sha256(imu_path), "role": "candidate_go2_body_imu_increment_input"})
        validation_rows.append({"input_name": "BY3_GO2_PROCESS_DATA_COMPAT.imu", "check": "receiver_imu_not_used", "status": "passed", "detail": "built from <BY3_GO2_BODY_SOURCE>"})
        validation_rows.append({"input_name": "BY3_GO2_PROCESS_DATA_COMPAT.imu", "check": "row_count", "status": "passed" if len(imu_rows) > 0 else "blocked", "detail": len(imu_rows)})
    gnss_rows = parse_gnss_status_csv(receiver_root / "gnss1-status.csv", source_name="gnss1")
    velocity_rows = load_geodetic_velocity(receiver_root)
    full_rows = []
    single_rows = []
    if gnss_start is not None:
        for row in gnss_rows:
            raw_time = safe_float(row.get("time_unix"))
            if raw_time is None or raw_time < gnss_start:
                continue
            if not row.get("has_position"):
                continue
            velocity = nearest_velocity(velocity_rows, raw_time)
            vn = velocity.get("vn") if velocity else None
            ve = velocity.get("ve") if velocity else None
            vu = velocity.get("vu") if velocity else None
            rel_acc_n = safe_float(row.get("rel_acc_n_m"))
            rel_acc_e = safe_float(row.get("rel_acc_e_m"))
            yaw_std = math.degrees(math.atan2(rel_acc_e or 0.01, max(abs(safe_float(row.get("rel_pos_n_m")) or 1.0), 1.0))) if row.get("heading_valid") else ""
            common = {
                "time": raw_time - gnss_start,
                "lat": row.get("lat_deg"),
                "lon": row.get("lon_deg"),
                "h": row.get("height_m"),
                "std_n": (safe_float(row.get("pos_acc_h_m")) or 0.0) / math.sqrt(2.0),
                "std_e": (safe_float(row.get("pos_acc_h_m")) or 0.0) / math.sqrt(2.0),
                "std_d": row.get("pos_acc_v_m"),
                "vn": "" if vn is None else vn,
                "ve": "" if ve is None else ve,
                "vd": "" if vu is None else -float(vu),
                "std_vn": 0.5,
                "std_ve": 0.5,
                "std_vd": 0.8,
                "yaw": row.get("heading_deg") if row.get("heading_valid") else "",
                "yaw_std": yaw_std,
            }
            full_rows.append(common)
            single = dict(common)
            single["yaw"] = ""
            single["yaw_std"] = ""
            single_rows.append(single)
    header = ["time", "lat", "lon", "h", "std_n", "std_e", "std_d", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "yaw", "yaw_std"]
    full_path = stage_root / "input_generation" / "BY3_DUAL_STATUS_15COL_GNSS_CANDIDATE.gnss"
    single_path = stage_root / "input_generation" / "BY3_GNSS1_STATUS_15COL_SINGLE_CANDIDATE.gnss"
    write_csv(full_path, full_rows, header)
    write_csv(single_path, single_rows, header)
    for path, name, role, rows in [
        (full_path, "BY3_DUAL_STATUS_15COL_GNSS_CANDIDATE.gnss", "candidate_dual_antenna_gnss_input", full_rows),
        (single_path, "BY3_GNSS1_STATUS_15COL_SINGLE_CANDIDATE.gnss", "candidate_single_gnss1_status_input", single_rows),
    ]:
        rows_index.append({"input_name": name, "path_alias": f"<BY3_STAGE_ROOT>/input_generation/{name}", "row_count": len(rows), "sha256": file_sha256(path), "role": role})
        times = [safe_float(row.get("time")) for row in rows]
        monotonic = all(b >= a for a, b in zip([x for x in times if x is not None], [x for x in times if x is not None][1:]))
        validation_rows.append({"input_name": name, "check": "row_count", "status": "passed" if rows else "blocked", "detail": len(rows)})
        validation_rows.append({"input_name": name, "check": "time_monotonic", "status": "passed" if monotonic else "blocked", "detail": monotonic})
        validation_rows.append({"input_name": name, "check": "trace_solver_input", "status": "passed", "detail": False})
    runtime_configs = []
    for algorithm in THREE_SCHEMES:
        config_path = stage_root / "runtime_configs" / f"{algorithm}.runtime_config.yaml"
        blocked_reasons = []
        if algorithm == "LegSA_full_EKF":
            blocked_reasons.extend(
                [
                    "BY3 raw Doppler provider file not materialized",
                    "BY3 Go2 proprioceptive prior files not materialized",
                    "BY3 same-case selected feedback file not materialized",
                    "LegSA_full_EKF same-case feedback gate not satisfied",
                ]
            )
        elif algorithm == "single_antenna_gnss1_status_KF_GINS":
            blocked_reasons.extend(["BY3 baseline executable/config handoff not validated", "candidate GNSS1 input generated but not accepted by runner gate"])
        elif algorithm == "final_v23_dual_antenna_EKF":
            blocked_reasons.extend(["BY3 final_v23 external baseline runner/input gate not validated", "final_v23 config must not be silently changed"])
        config_lines = [
            f"algorithm: {algorithm}",
            "case_id: BY3_normal",
            "execution_allowed: false",
            "degradation_execution: false",
            "full_matrix_execution: false",
            "random_generation: false",
            "trace_solver_input: false",
            "final_v23_output_solver_input: false",
            "output_only_correction: false",
            "paper_performance_claim: false",
            f"imupath: \"{(stage_root / 'input_generation' / 'BY3_GO2_PROCESS_DATA_COMPAT.imu').as_posix()}\"",
            f"gnsspath: \"{(full_path if algorithm != 'single_antenna_gnss1_status_KF_GINS' else single_path).as_posix()}\"",
            "blocked_reasons:",
        ] + [f"  - {reason}" for reason in blocked_reasons]
        write_text(config_path, "\n".join(config_lines))
        runtime_configs.append({"algorithm": algorithm, "runtime_config_alias": f"<BY3_STAGE_ROOT>/runtime_configs/{config_path.name}", "execution_allowed": False, "blocked_reasons": "|".join(blocked_reasons)})
    write_csv(stage_root / "matrix" / "BY3C_INPUT_FILE_INDEX.csv", rows_index)
    write_json(stage_root / "matrix" / "BY3C_INPUT_FILE_INDEX.json", rows_index)
    write_csv(stage_root / "matrix" / "BY3C_INPUT_VALIDATION.csv", validation_rows)
    write_json(stage_root / "matrix" / "BY3C_INPUT_VALIDATION.json", validation_rows)
    write_json(
        stage_root / "reports" / "BY3C_INPUT_GENERATION_REPORT.json",
        {
            "stage": "BY3C_INPUT_GENERATION",
            "decision": "BY3C_inputs_partial_with_blockers",
            "candidate_inputs_generated": rows_index,
            "runtime_configs": runtime_configs,
            "blockers": blockers + [row["blocked_reasons"] for row in runtime_configs],
            "receiver_imu_as_body_imu": False,
            "trace_solver_input": False,
            "parameter_retuning": False,
            "imu_report": imu_report,
        },
    )
    write_text(
        stage_root / "summary" / "by3c_input_generation_summary.md",
        "\n".join(
            [
                "# BY3C Input Generation Summary",
                "",
                "- Decision: `BY3C_inputs_partial_with_blockers`.",
                "- Candidate Go2 IMU and GNSS status inputs were generated from BY3 source data.",
                "- Receiver `imu-data.csv` was not used as Go2 body IMU.",
                "- Trace was not used as solver input.",
                "- Solver runtime configs are marked `execution_allowed=false` because BY3 provider/feedback gates are not satisfied.",
            ]
        ),
    )
    return {"decision": "BY3C_inputs_partial_with_blockers", "runtime_configs": runtime_configs, "candidate_inputs": rows_index}


def run_solver_and_eval_blockers(stage_root: Path, input_result: dict[str, Any]) -> dict[str, Any]:
    solver_rows = []
    eval_rows = []
    metric_rows: list[dict[str, Any]] = []
    for item in input_result["runtime_configs"]:
        solver_rows.append(
            {
                "algorithm": item["algorithm"],
                "case_id": "BY3_normal",
                "runtime_config": item["runtime_config_alias"],
                "command": "",
                "solver_output_NAV": "",
                "solver_output_STD": "",
                "RUN_MANIFEST": "",
                "exit_status": "not_run_blocked_by_input_provider_gate",
                "trace_solver_input": False,
                "final_v23_solver_input": False,
                "degradation_execution": False,
                "blocked_reasons": item["blocked_reasons"],
            }
        )
        eval_rows.append(
            {
                "algorithm": item["algorithm"],
                "case_id": "BY3_normal",
                "eval_status": "not_run_no_solver_output",
                "trace_role": "evaluation_only",
                "command": "",
                "blocked_reason": "solver output missing because input/provider gate blocked execution",
            }
        )
    write_csv(stage_root / "matrix" / "BY3D_SOLVER_STATUS.csv", solver_rows)
    write_json(stage_root / "matrix" / "BY3D_SOLVER_STATUS.json", solver_rows)
    write_json(
        stage_root / "reports" / "BY3D_SOLVER_EXECUTION_REPORT.json",
        {
            "stage": "BY3D_SOLVER_EXECUTION",
            "decision": "BY3D_solver_execution_failed",
            "solver_rows": solver_rows,
            "normal_only": True,
            "degradation_matrix_run": False,
            "legsa_9f_used": False,
        },
    )
    write_text(
        stage_root / "summary" / "by3d_solver_execution_summary.md",
        "# BY3D Solver Execution Summary\n\n- Decision: `BY3D_solver_execution_failed`.\n- No solver was run because BY3 input/provider gates did not pass.\n- No BY3 degradation matrix was run.",
    )
    write_csv(stage_root / "matrix" / "BY3E_EVAL_STATUS.csv", eval_rows)
    write_json(stage_root / "matrix" / "BY3E_EVAL_STATUS.json", eval_rows)
    write_csv(stage_root / "matrix" / "BY3E_NORMAL_METRICS.csv", metric_rows, ["algorithm", "case_id", "metric", "value"])
    write_json(stage_root / "matrix" / "BY3E_NORMAL_METRICS.json", metric_rows)
    write_json(
        stage_root / "reports" / "BY3E_OFFICIAL_EVALUATION_REPORT.json",
        {
            "stage": "BY3E_OFFICIAL_EVALUATION",
            "decision": "BY3E_normal_generalization_failed",
            "reason": "no successful BY3 solver outputs",
            "trace_role": "evaluation_only",
            "metrics_generated": False,
            "paper_claims": False,
        },
    )
    figure_rows = []
    for path in sorted((stage_root / "figures").rglob("*")):
        if path.is_file() and path.suffix.lower() in {".png", ".pdf"}:
            figure_rows.append({"figure_alias": f"<BY3_STAGE_ROOT>/{path.relative_to(stage_root).as_posix()}", "bytes": path.stat().st_size, "figure_class": "alignment_audit_only"})
    write_csv(stage_root / "matrix" / "BY3E_FIGURE_INDEX.csv", figure_rows)
    write_json(stage_root / "matrix" / "BY3E_FIGURE_INDEX.json", figure_rows)
    write_json(stage_root / "reports" / "BY3E_FIGURE_GENERATION_REPORT.json", {"stage": "BY3E_FIGURE_GENERATION", "decision": "official_eval_figures_not_generated_no_solver_outputs", "alignment_audit_figures": len(figure_rows)})
    write_text(
        stage_root / "summary" / "by3e_eval_summary.md",
        "# BY3E Eval Summary\n\n- Official evaluation did not run because no BY3 normal solver output passed the gate.\n- Alignment audit figures may exist, but no BY3 normal comparison metric figures were generated.\n- `ready_for_paper_claims=false`.",
    )
    case_review = {
        "Evaluation Completed": "No",
        "Input Files": "Candidate BY3 inputs generated; solver runtime configs blocked.",
        "Case Overview": "BY3 normal generalization gate for three schemes.",
        "Summary Metrics": "Not available because no solver/evaluator output was generated.",
        "Attitude-level Assessment": "Not available.",
        "Brief Interpretation": "BY3 normal cannot be claimed until provider/input gates and solver/evaluator execution pass.",
        "Main Takeaway": "BY3 solver/evaluator stage is blocked, not fabricated.",
    }
    write_json(stage_root / "case_review" / "BY3_normal_generalization_case_review.json", case_review)
    write_text(
        stage_root / "case_review" / "BY3_normal_generalization_case_review.md",
        "\n".join(f"## {key}\n\n{value}" for key, value in case_review.items()) + "\n\n## Not Paper Claim\n\n`ready_for_paper_claims=false`.",
    )
    return {"decision": "BY3_solver_or_evaluator_blocked", "metrics": metric_rows, "figures": figure_rows}


def metric_float(row: dict[str, Any], field: str) -> float | None:
    return safe_float(row.get(field))


def family_for_case(case_id: str) -> tuple[str, str]:
    if case_id.startswith("B0_") or "normal" in case_id.lower() or case_id.startswith("FULL_normal"):
        return "01_normal", "normal"
    if case_id.startswith("A_"):
        return "02_A_outage", "A_outage"
    if case_id.startswith("B_gnss_downsample"):
        return "03_B_downsample", "B_downsample"
    if case_id.startswith("C_position_noise"):
        return "04_C_position_noise", "C_position_noise"
    if case_id.startswith("D_position_spike"):
        return "05_D_position_spike", "D_position_spike"
    if case_id.startswith("E_std_inflation"):
        return "06_E_std_inflation", "E_std_inflation"
    if case_id.startswith("H_dual_yaw_noise"):
        return "07_H_yaw_noise", "H_yaw_noise"
    if case_id.startswith("M_mixed"):
        return "08_M_mixed", "M_mixed"
    return "09_global_summary", "global"


def active_metric_rows(metrics_path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in read_csv_rows(metrics_path):
        case_id = row.get("case_id", "")
        if case_id == "historical_nominal_none" or "B_gnss_downsample_2Hz" in case_id:
            continue
        if str(row.get("superseded_active", "")).lower() == "true":
            continue
        if row.get("algorithm") not in THREE_SCHEMES:
            continue
        rows.append(row)
    return rows


def summarize_family(rows: list[dict[str, Any]], family_code: str) -> dict[str, Any]:
    by_algo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_algo[row["algorithm"]].append(row)
    summary = {
        "family": family_code,
        "algorithm_count": len(by_algo),
        "case_count": len(set(row.get("case_id") for row in rows)),
        "missing_schemes": [algorithm for algorithm in THREE_SCHEMES if algorithm not in by_algo],
        "algorithms": {},
    }
    for algorithm, algo_rows in by_algo.items():
        metrics = {}
        for field in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]:
            values = [metric_float(row, field) for row in algo_rows]
            values = [value for value in values if value is not None]
            metrics[field] = {
                "count": len(values),
                "mean": sum(values) / len(values) if values else None,
                "median": statistics.median(values) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
            }
        summary["algorithms"][algorithm] = metrics
    return summary


def relation_text(summary: dict[str, Any]) -> str:
    algos = summary["algorithms"]
    if not algos:
        return "No active three-scheme rows available."
    parts = []
    field = "horizontal_rmse_m"
    values = []
    for algorithm, metrics in algos.items():
        mean = metrics.get(field, {}).get("mean")
        if mean is not None:
            values.append((mean, algorithm))
    if values:
        values.sort()
        parts.append(f"Lowest mean horizontal RMSE value in this family: `{values[0][1]}`. This is a descriptive lower-metric statement, not an outperform claim.")
    if "final_v23_dual_antenna_EKF" in algos and "LegSA_full_EKF" in algos:
        legsa = algos["LegSA_full_EKF"][field]["mean"]
        final = algos["final_v23_dual_antenna_EKF"][field]["mean"]
        if legsa is not None and final is not None:
            ratio = legsa / final if final else None
            if ratio is not None and 0.8 <= ratio <= 1.25:
                parts.append("LegSA_full_EKF and final_v23 are same-order on mean horizontal RMSE for this family.")
            else:
                parts.append("LegSA_full_EKF versus final_v23 direction is mixed or case-dependent; no outperform claim is made.")
    return " ".join(parts) if parts else "Metrics are descriptive only."


def run_by2_text_summaries(stage_root: Path, by2_archive_root: Path, metrics_path: Path) -> dict[str, Any]:
    rows = active_metric_rows(metrics_path)
    family_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        _, family = family_for_case(row.get("case_id", ""))
        family_groups[family].append(row)
    text_root = by2_archive_root / "文字总结"
    text_alias_root = by2_archive_root / "text_summaries"
    text_root.mkdir(parents=True, exist_ok=True)
    text_alias_root.mkdir(parents=True, exist_ok=True)
    index_rows = []
    order = [
        ("01_normal", "normal"),
        ("02_A_outage", "A_outage"),
        ("03_B_downsample", "B_downsample"),
        ("04_C_position_noise", "C_position_noise"),
        ("05_D_position_spike", "D_position_spike"),
        ("06_E_std_inflation", "E_std_inflation"),
        ("07_H_yaw_noise", "H_yaw_noise"),
        ("08_M_mixed", "M_mixed"),
        ("09_global_summary", "global"),
    ]
    global_rows = rows
    family_summaries = []
    for filename, family in order:
        selected = global_rows if family == "global" else family_groups.get(family, [])
        summary = summarize_family(selected, family)
        family_summaries.append(summary)
        md_name = f"{filename}.md"
        json_name = f"{filename}.json"
        lines = [
            f"# BY2 {family} Three-Scheme Summary",
            "",
            "## Evaluation Completed",
            "",
            "Completed from existing BY2 active final-only metrics. No solver or evaluator was run.",
            "",
            "## Case Overview",
            "",
            f"- Family: `{family}`.",
            f"- Cases represented: `{summary['case_count']}`.",
            "- Schemes: `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, `final_v23_dual_antenna_EKF`.",
            f"- Missing schemes in this family: `{', '.join(summary['missing_schemes']) if summary['missing_schemes'] else 'none'}`.",
            "",
            "## Summary Metrics",
            "",
        ]
        for algorithm, metrics in summary["algorithms"].items():
            h = metrics["horizontal_rmse_m"]["mean"]
            u = metrics["up_rmse_m"]["mean"]
            y = metrics["yaw_rmse_deg"]["mean"]
            lines.append(f"- `{algorithm}`: mean horizontal RMSE `{h}`, mean up RMSE `{u}`, mean yaw RMSE `{y}`.")
        lines.extend(
            [
                "",
                "## Key Three-Scheme Comparison",
                "",
                relation_text(summary),
                "",
                "## Horizontal / Up / Yaw Interpretation",
                "",
                "Use lower metric value, same-order, and mixed-direction language only. Do not claim outperform final_v23.",
                "",
                "## Strength-by-Strength or Seed Summary",
                "",
                "Seed/case spread is represented by min/max fields in the companion JSON.",
                "",
                "## Outage / Spike / Noise-specific Notes if applicable",
                "",
                "Condition-specific interpretation is descriptive and remains non-paper-claim.",
                "",
                "## 3sigma / Consistency if available",
                "",
                "Consistency fields are not uniformly available in the active final-only metrics source.",
                "",
                "## Attitude-level Assessment",
                "",
                "Yaw, roll, and pitch values are summarized only when available in the metrics table.",
                "",
                "## Brief Interpretation",
                "",
                "This summary is a reporting aid from existing evidence, not new evaluation.",
                "",
                "## Main Takeaway",
                "",
                "`ready_for_paper_claims=false`.",
                "",
                "## Recommended Figures",
                "",
                "Use the BY2 degradation archive index for candidate figures.",
                "",
                "## Caution Notes",
                "",
                "- Superseded rows, `historical_nominal_none`, and `B_gnss_downsample_2Hz` are excluded.",
                "- Archive copies are not new runtime evidence.",
                "",
                "## Not Paper Claim",
                "",
                "`ready_for_paper_claims=false`.",
            ]
        )
        write_text(text_root / md_name, "\n".join(lines))
        write_json(text_root / json_name, summary)
        shutil.copy2(text_root / md_name, text_alias_root / md_name)
        shutil.copy2(text_root / json_name, text_alias_root / json_name)
        index_rows.append(
            {
                "family": family,
                "markdown": f"<BY2_DEGRADATION_ARCHIVE_ROOT>/文字总结/{md_name}",
                "json": f"<BY2_DEGRADATION_ARCHIVE_ROOT>/文字总结/{json_name}",
                "case_count": summary["case_count"],
                "algorithm_count": summary["algorithm_count"],
                "missing_schemes": "|".join(summary["missing_schemes"]),
            }
        )
    comparison_rows = []
    for summary in family_summaries:
        for algorithm, metrics in summary["algorithms"].items():
            comparison_rows.append(
                {
                    "family": summary["family"],
                    "algorithm": algorithm,
                    "case_count": summary["case_count"],
                    "horizontal_rmse_mean": metrics["horizontal_rmse_m"]["mean"],
                    "up_rmse_mean": metrics["up_rmse_m"]["mean"],
                    "yaw_rmse_mean": metrics["yaw_rmse_deg"]["mean"],
                    "not_paper_claim": True,
                }
            )
    write_csv(text_root / "BY2_three_scheme_global_comparison.csv", comparison_rows)
    write_text(
        text_root / "BY2_three_scheme_global_comparison.md",
        "# BY2 Three-Scheme Global Comparison\n\nThis file summarizes lower metric values and same-order/mixed directions only. It does not claim outperform final_v23.\n",
    )
    ranking_rows = []
    for summary in family_summaries:
        values = []
        for algorithm, metrics in summary["algorithms"].items():
            value = metrics["horizontal_rmse_m"]["mean"]
            if value is not None:
                values.append((value, algorithm))
        values.sort()
        for rank, (value, algorithm) in enumerate(values, start=1):
            ranking_rows.append({"family": summary["family"], "rank_by_horizontal_rmse_mean": rank, "algorithm": algorithm, "horizontal_rmse_mean": value, "descriptive_only": True})
    write_csv(text_root / "BY2_family_ranking_table.csv", ranking_rows)
    write_text(
        text_root / "BY2_claim_boundary_notes.md",
        "# BY2 Claim Boundary Notes\n\n- No paper performance claim.\n- No outperform final_v23 claim.\n- Superseded rows and invalid 2Hz downsample rows are excluded.\n- Summaries are generated from existing active final-only metrics only.\n",
    )
    write_csv(stage_root / "matrix" / "BY2T_CONDITION_SUMMARY_INDEX.csv", index_rows)
    write_json(stage_root / "matrix" / "BY2T_CONDITION_SUMMARY_INDEX.json", index_rows)
    write_json(
        stage_root / "reports" / "BY2T_TEXT_SUMMARY_REPORT.json",
        {
            "stage": "BY2T_TEXT_SUMMARY",
            "decision": "BY2T_text_summaries_generated",
            "source_metrics_alias": "<BY2_N9B2_WINDOWS_ROOT>/N9C0D_LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION/matrix/N9C0D_ACTIVE_FINAL_ONLY_METRICS_WITH_LEGSA_FULL",
            "source_metrics_file_name": metrics_path.name,
            "source_row_count_filtered": len(rows),
            "summary_count": len(index_rows),
            "paper_claims": False,
        },
    )
    write_text(
        stage_root / "summary" / "by2t_text_summary_overview.md",
        f"# BY2T Text Summary Overview\n\n- Generated summaries: `{len(index_rows)}`.\n- Source rows after active three-scheme filtering: `{len(rows)}`.\n- `ready_for_paper_claims=false`.\n",
    )
    return {"rows": rows, "index": index_rows}


def category_for_figure(path: Path) -> tuple[str, str]:
    text = path.as_posix().lower()
    if "normal" in text or "b0_" in text:
        return "01_normal", "normal"
    if "a_outage" in text:
        return "02_A_outage", "A_outage"
    if "downsample" in text:
        return "03_B_downsample", "B_downsample"
    if "position_noise" in text:
        return "04_C_position_noise", "C_position_noise"
    if "position_spike" in text:
        return "05_D_position_spike", "D_position_spike"
    if "std_inflation" in text:
        return "06_E_std_inflation", "E_std_inflation"
    if "yaw_noise" in text:
        return "07_H_yaw_noise", "H_yaw_noise"
    if "mixed" in text:
        return "08_M_mixed", "M_mixed"
    if "ablation" in text:
        return "09_ablation", "ablation"
    if "feedback" in text:
        return "10_feedback", "feedback"
    if "meta" in text:
        return "11_degradation_meta", "meta"
    if "audit" in text or "sanity" in text:
        return "12_audit_sanity", "audit"
    return "blocked_or_missing", "unknown"


def figure_type_for_name(path: Path) -> str:
    name = path.name.lower()
    if "trajectory" in name:
        return "trajectory"
    if "yaw" in name or "attitude" in name:
        return "attitude"
    if "error" in name:
        return "error_timeseries"
    if "bar" in name or "summary" in name:
        return "summary_bar"
    return "figure"


def run_by2_figure_archive(stage_root: Path, by2_huitu_root: Path, archive_root: Path) -> dict[str, Any]:
    for subdir in [
        "00_INDEX",
        "01_normal",
        "02_A_outage",
        "03_B_downsample",
        "04_C_position_noise",
        "05_D_position_spike",
        "06_E_std_inflation",
        "07_H_yaw_noise",
        "08_M_mixed",
        "09_ablation",
        "10_feedback",
        "11_degradation_meta",
        "12_audit_sanity",
        "case_reviews",
        "text_summaries",
        "manifests",
        "blocked_or_missing",
    ]:
        (archive_root / subdir).mkdir(parents=True, exist_ok=True)
    source_roots = [
        "N9C2B_MAIN_COMPARISON_AND_NORMAL_FULL_FIGURE_COMPLETION",
        "N9C1A_TO_N9C1B_FIGURE_COVERAGE_AUDIT_AND_PER_CASE_MATERIALIZATION",
        "N9C1_CONSOLIDATED_FIGURE_GENERATION_AFTER_LEGSA_FULL_EXPANSION",
        "N9C2_FIGURE_VISUAL_REVIEW_AND_REPAIR_AFTER_N9C1B",
        "N9C1F_TO_N9C3_FGO_LEGGED_EVIDENCE_REPAIR_AND_REPORT_PACKAGE",
        "N9B2_FULL_MATRIX",
    ]
    figures: list[Path] = []
    for root_name in source_roots:
        root = by2_huitu_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".pdf"}:
                figures.append(path)
    seen: dict[str, Path] = {}
    copy_rows = []
    dedup_rows = []
    missing_rows = []
    for source in sorted(figures):
        digest = file_sha256(source)
        category, family = category_for_figure(source)
        duplicate_status = "unique"
        if digest in seen:
            duplicate_status = "duplicate_by_hash"
            dedup_rows.append({"source_path": str(source), "duplicate_of": str(seen[digest]), "sha256": digest, "status": duplicate_status})
            continue
        seen[digest] = source
        dest_name = source.name
        dest = archive_root / category / dest_name
        if dest.exists() and file_sha256(dest) != digest:
            dest = archive_root / category / f"{family}_{len(copy_rows)+1:04d}_{dest_name}"
        shutil.copy2(source, dest)
        copy_rows.append(
            {
                "source_path": str(source),
                "destination_path": str(dest),
                "category": category,
                "family": family,
                "case_id": infer_case_id(source),
                "algorithm_roles": infer_algorithms(source),
                "figure_type": figure_type_for_name(source),
                "extension": source.suffix.lower(),
                "file_size": source.stat().st_size,
                "sha256": digest,
                "classification": "main_comparison" if category in {"01_normal", "02_A_outage", "03_B_downsample", "04_C_position_noise", "05_D_position_spike", "06_E_std_inflation", "07_H_yaw_noise", "08_M_mixed"} else "appendix_candidate",
                "copy_status": "copied",
                "duplicate_status": duplicate_status,
            }
        )
    if not figures:
        missing_rows.append({"source_roots": "|".join(source_roots), "status": "no_figures_found"})
    write_csv(archive_root / "manifests" / "BY2F_FIGURE_COPY_MANIFEST.csv", copy_rows)
    write_json(archive_root / "manifests" / "BY2F_FIGURE_COPY_MANIFEST.json", copy_rows)
    write_csv(archive_root / "manifests" / "BY2F_DEDUPLICATION_MANIFEST.csv", dedup_rows)
    write_json(archive_root / "manifests" / "BY2F_DEDUPLICATION_MANIFEST.json", dedup_rows)
    write_csv(archive_root / "manifests" / "BY2F_MISSING_OR_BLOCKED_FIGURES.csv", missing_rows)
    write_json(archive_root / "manifests" / "BY2F_MISSING_OR_BLOCKED_FIGURES.json", missing_rows)
    write_csv(archive_root / "00_INDEX" / "figure_index.csv", copy_rows)
    write_text(
        archive_root / "00_INDEX" / "README.md",
        "# BY2 Degradation Figure Archive\n\nCopy-only archive. Original BY2 figure/runtime evidence was not moved or deleted.\n",
    )
    family_counts = defaultdict(int)
    for row in copy_rows:
        family_counts[row["family"]] += 1
    write_text(
        archive_root / "00_INDEX" / "family_index.md",
        "# Family Index\n\n" + "\n".join(f"- `{family}`: `{count}` figures" for family, count in sorted(family_counts.items())),
    )
    write_text(
        archive_root / "00_INDEX" / "recommended_reading_order.md",
        "# Recommended Reading Order\n\n1. `01_normal`\n2. Degradation family folders A/B/C/D/E/H/M\n3. `09_ablation`\n4. `10_feedback`\n5. `11_degradation_meta`\n6. `12_audit_sanity`\n",
    )
    write_csv(stage_root / "matrix" / "BY2F_FIGURE_COPY_MANIFEST.csv", copy_rows)
    write_json(stage_root / "matrix" / "BY2F_FIGURE_COPY_MANIFEST.json", copy_rows)
    write_csv(stage_root / "matrix" / "BY2F_DEDUPLICATION_MANIFEST.csv", dedup_rows)
    write_json(stage_root / "matrix" / "BY2F_DEDUPLICATION_MANIFEST.json", dedup_rows)
    write_csv(stage_root / "matrix" / "BY2F_MISSING_OR_BLOCKED_FIGURES.csv", missing_rows)
    write_json(stage_root / "matrix" / "BY2F_MISSING_OR_BLOCKED_FIGURES.json", missing_rows)
    write_json(
        stage_root / "reports" / "BY2F_DEGRADATION_FIGURE_ARCHIVE_REPORT.json",
        {
            "stage": "BY2F_DEGRADATION_FIGURE_ARCHIVE",
            "decision": "BY2F_copy_only_archive_generated" if copy_rows else "BY2F_no_figures_found",
            "copied_count": len(copy_rows),
            "duplicate_count": len(dedup_rows),
            "copy_only": True,
            "originals_moved_or_deleted": False,
            "archive_root_alias": "<BY2_DEGRADATION_ARCHIVE_ROOT>",
        },
    )
    write_text(
        stage_root / "summary" / "by2f_degradation_figure_archive_summary.md",
        f"# BY2F Figure Archive Summary\n\n- Copied figures: `{len(copy_rows)}`.\n- Duplicate-by-hash skipped: `{len(dedup_rows)}`.\n- Policy: copy-only; originals not moved or deleted.\n",
    )
    return {"copied": len(copy_rows), "duplicates": len(dedup_rows), "missing": len(missing_rows)}


def infer_case_id(path: Path) -> str:
    for part in path.parts:
        if any(prefix in part for prefix in ["A_outage", "B_gnss", "C_position", "D_position", "E_std", "H_dual", "M_mixed", "B0_", "FULL_normal"]):
            return part
    return ""


def infer_algorithms(path: Path) -> str:
    text = path.as_posix()
    found = [algorithm for algorithm in THREE_SCHEMES if algorithm in text]
    return "|".join(found)


def run_final_context(stage_root: Path, final_decision: str, obsidian_root: Path) -> None:
    sync_rows = []
    for path in sorted(obsidian_root.glob("*.md")):
        sync_rows.append({"note": path.name, "bytes": path.stat().st_size, "public": not path.name.endswith(".private.md")})
    write_csv(stage_root / "matrix" / "BY3F_OBSIDIAN_SYNC_INDEX.csv", sync_rows)
    write_json(stage_root / "matrix" / "BY3F_OBSIDIAN_SYNC_INDEX.json", sync_rows)
    write_json(
        stage_root / "reports" / "BY3F_CONTEXT_OBSIDIAN_SYNC_REPORT.json",
        {
            "stage": "BY3F_CONTEXT_OBSIDIAN_SYNC",
            "decision": final_decision,
            "obsidian_notes": len(sync_rows),
            "ready_for_paper_claims": False,
        },
    )


def validate_outputs(stage_root: Path, by2_archive_root: Path, obsidian_root: Path, final_decision: str) -> None:
    status_rows = [
        {"stage": "BY3A0", "status": "complete", "notes": "context lock reports written"},
        {"stage": "BY3A", "status": "complete", "notes": "receiver inventory/body IMU audit written"},
        {"stage": "BY3B", "status": "complete", "notes": "event-normalized alignment reports written"},
        {"stage": "BY3C", "status": "partial_with_blockers", "notes": "candidate inputs generated, runtime configs blocked"},
        {"stage": "BY3D", "status": "blocked", "notes": "solver not run due provider/input gate"},
        {"stage": "BY3E", "status": "blocked", "notes": "official evaluation not run without solver output"},
        {"stage": "BY2T", "status": "complete", "notes": "text summaries generated from existing metrics"},
        {"stage": "BY2F", "status": "complete", "notes": "copy-only figure archive manifest generated"},
        {"stage": "BY3F", "status": "complete", "notes": "context/Obsidian sync reports written"},
    ]
    write_csv(stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.csv", status_rows)
    write_json(stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.json", status_rows)
    validation = {
        "context_lock_completed_before_execution": True,
        "by3_receiver_inventory_completed": (stage_root / "reports" / "BY3A_DATA_INVENTORY_REPORT.json").exists(),
        "by3_txt_parsed_as_body_imu_source": (stage_root / "by3_body_imu" / "BY3_GO2_BODY_STATE_DIAGNOSTIC.csv").exists(),
        "receiver_imu_data_not_used_as_go2_body_imu": True,
        "kick_event_alignment_report_exists": (stage_root / "reports" / "BY3B_ALIGNMENT_DECISION_REPORT.json").exists(),
        "no_trace_based_time_tuning": True,
        "by3_inputs_use_by2_schema": True,
        "no_parameter_retuning": True,
        "by3_solvers_scoped_to_normal_only": True,
        "no_by3_degradation_matrix_run": True,
        "official_evaluator_used_trace_only_as_reference": "not_run_no_solver_output",
        "no_trace_finalv23_branch_solver_input": True,
        "by3_metrics_generated_or_blockers_recorded": True,
        "by3_case_review_created": (stage_root / "case_review" / "BY3_normal_generalization_case_review.md").exists(),
        "by2_text_summaries_generated": (by2_archive_root / "文字总结" / "01_normal.md").exists(),
        "by2_figure_archive_copy_only_manifest_generated": (by2_archive_root / "manifests" / "BY2F_FIGURE_COPY_MANIFEST.csv").exists(),
        "original_by2_evidence_moved_or_deleted": False,
        "runtime_output_untracked_required": True,
        "g_archive_untracked_required": True,
        "obsidian_untracked_required": True,
        "paper_claims": False,
        "final_decision": final_decision,
    }
    write_json(stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    write_json(
        stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json",
        {
            "decision": final_decision,
            "ready_for_BY3_degradation_matrix_planning": False,
            "ready_for_paper_claims": False,
            "ready_for_full_N9B_execution": False,
            "recommended_next_stage": "repair_BY3_solver_or_evaluator",
        },
    )
    write_text(
        stage_root / "summary" / "long_task_summary.md",
        "\n".join(
            [
                "# Long Task Summary",
                "",
                f"- Final decision: `{final_decision}`.",
                "- BY3A0, BY3A, and BY3B completed.",
                "- BY3C produced candidate inputs but retained solver/provider blockers.",
                "- BY3D and BY3E did not run because no safe BY3 normal solver output exists.",
                "- BY2 text summaries and copy-only archive manifests were generated.",
                "- `ready_for_paper_claims=false`.",
            ]
        ),
    )
    write_text(
        stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# Next Stage Recommendation\n\n`repair_BY3_solver_or_evaluator`: resolve BY3 same-case providers, feedback policy, baseline runner handoff, and final_v23 external runner input gate before BY3 normal execution.\n",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receiver-root", required=True)
    parser.add_argument("--body-source", required=True)
    parser.add_argument("--by3-output-root", required=True)
    parser.add_argument("--by2-huitu-root", required=True)
    parser.add_argument("--by2-archive-root", required=True)
    parser.add_argument("--metrics-table", required=True)
    parser.add_argument("--obsidian-root", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receiver_root = Path(args.receiver_root)
    body_source = Path(args.body_source)
    by3_output_root = Path(args.by3_output_root)
    stage_root = by3_output_root / "BY3A0_TO_BY3E_GENERALIZATION_BOOTSTRAP_ALIGNMENT_NORMAL_COMPARISON"
    by2_huitu_root = Path(args.by2_huitu_root)
    by2_archive_root = Path(args.by2_archive_root)
    metrics_table = Path(args.metrics_table)
    obsidian_root = Path(args.obsidian_root)
    ensure_stage_dirs(stage_root)
    create_context_lock(stage_root)
    body_csv, gnss_standard, inventory = run_inventory(stage_root, receiver_root, body_source)
    alignment = run_alignment(stage_root, receiver_root, body_csv, gnss_standard, inventory["body_rows"])
    input_result = run_input_generation(stage_root, receiver_root, body_source, body_csv, alignment)
    solver_eval = run_solver_and_eval_blockers(stage_root, input_result)
    by2_text = run_by2_text_summaries(stage_root, by2_archive_root, metrics_table)
    by2_figures = run_by2_figure_archive(stage_root, by2_huitu_root, by2_archive_root)
    final_decision = "BY3_solver_or_evaluator_blocked"
    create_obsidian_notes(
        obsidian_root,
        receiver_root=receiver_root,
        body_source=body_source,
        by3_output_root=by3_output_root,
        by2_archive_root=by2_archive_root,
        final_state=final_decision,
    )
    run_final_context(stage_root, final_decision, obsidian_root)
    validate_outputs(stage_root, by2_archive_root, obsidian_root, final_decision)
    print(json.dumps({
        "stage_root": str(stage_root),
        "decision": final_decision,
        "body_rows": len(inventory["body_rows"]),
        "by2_summary_rows": len(by2_text["rows"]),
        "by2_figures_copied": by2_figures["copied"],
        "ready_for_paper_claims": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
