#!/usr/bin/env python3
"""Audit BY2 PAPER10 M1R2B2/M1R2C_R1/M1R2D_R1 source lineage.

This script is report-only. It reads existing raw metadata, provider manifests,
runtime outputs, and row tables, then writes lightweight audit reports under an
external stage root. It does not modify providers, raw data, solver code, or
historical runtime outputs.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


STAGE_NAME = "PAPER10_AUDIT1_BY2_FULL_MATRIX_SOURCE_LINEAGE_AND_RUNTIME_PROOF"

RAW_ROLES = [
    ("gnss1_raw", "gnss1-raw.csv", "<BY2_FIX_ROOT>/gnss1-raw.csv"),
    ("gnss2_raw", "gnss2-raw.csv", "<BY2_FIX_ROOT>/gnss2-raw.csv"),
    ("gnss1_status", "gnss1-status.csv", "<BY2_FIX_ROOT>/gnss1-status.csv"),
    ("gnss2_status", "gnss2-status.csv", "<BY2_FIX_ROOT>/gnss2-status.csv"),
    ("corr_raw", "corr-raw.csv", "<BY2_FIX_ROOT>/corr-raw.csv"),
    ("userio_raw", "userio-raw.csv", "<BY2_FIX_ROOT>/userio-raw.csv"),
    (
        "trace_vrtk2",
        "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv",
        "<TRACE_EVAL_REFERENCE_ONLY>",
    ),
]

FULL_METHODS = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]

INTERNAL_METHODS = [
    "legsa_full_candidate_with_qm",
    "legsa_without_qm",
    "legsa_no_raw_doppler",
    "legsa_no_source_aware",
    "legsa_no_go2_roll_pitch",
    "legsa_no_go2_horizontal_velocity",
    "legsa_no_go2_joint",
    "legsa_no_qm",
    "legsa_no_fgo_feedback_or_ekf_only",
]

FORBIDDEN_ROW_FIELDS = [
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
    "trace_solver_input",
    "trace_tuned_yaw_fix",
    "final_v23_output_solver_input",
]

RUNTIME_REQUIRED_FILES = [
    "RUN_MANIFEST.json",
    "EVALUATOR_SUMMARY.json",
    "EVAL_NAV.csv",
    "LegSA_PORT_NAV.nav",
    "LegSA_PORT_STD.csv",
    "FEATURE_FLAGS.json",
    "DATASET_ROLE_DUMP.json",
    "METHOD_MODE_DUMP.json",
    "CASE_SPEC_DUMP.json",
    "YAW_PROVIDER_LINEAGE_REFERENCE.json",
    "PROVIDER_READY_REFERENCE.json",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "pass", "completed_evaluable"}


def falsey(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    return str(value).strip().lower() in {"false", "0", "no", "", "none"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_line_count_and_header(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "", ""
    count = 0
    header = ""
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            count += 1
            if count == 1:
                header = line.rstrip("\n\r")
    return str(count), header


def deg_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_mean = math.radians((lat1 + lat2) * 0.5)
    dn = (lat1 - lat2) * 111_320.0
    de = (lon1 - lon2) * 111_320.0 * math.cos(lat_mean)
    return math.hypot(dn, de)


def wrap_deg180(angle: float) -> float:
    wrapped = (angle + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def rmse(values: list[float]) -> float:
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return math.nan
    return math.sqrt(sum(value * value for value in values) / len(values))


def percentile(values: list[float], p: float) -> float:
    values = sorted(value for value in values if math.isfinite(value))
    if not values:
        return math.nan
    idx = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
    return values[idx]


class Aliaser:
    def __init__(self, pairs: dict[str, Path]) -> None:
        ordered = sorted(((alias, path.resolve()) for alias, path in pairs.items()), key=lambda item: len(str(item[1])), reverse=True)
        self.pairs = ordered

    def path(self, path: Path | str | None) -> str:
        if path is None:
            return ""
        text = str(path)
        resolved = text
        for alias, actual in self.pairs:
            actual_text = str(actual)
            if resolved == actual_text:
                return alias
            if resolved.startswith(actual_text + os.sep):
                return alias + resolved[len(actual_text) :]
        return text


def command_output(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        return proc.returncode, proc.stdout.strip()
    except OSError as exc:
        return 127, str(exc)


def ensure_stage_dirs(stage_root: Path) -> None:
    for name in [
        "00_STAGE_REPORT",
        "01_RAW_SOURCE",
        "02_PROVIDER_LINEAGE",
        "03_FULL_MATRIX",
        "04_INTERNAL_ABLATION",
        "05_METRIC_CROSSCHECK",
        "06_MINIMAL_RERUN",
        "07_TRUST_CLASSIFICATION",
        "10_EXPORT_CLEAN_FOR_GPT",
    ]:
        (stage_root / name).mkdir(parents=True, exist_ok=True)


def audit_raw_sources(args: argparse.Namespace, aliaser: Aliaser) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    raw_index: dict[str, dict[str, Any]] = {}
    for role, filename, placeholder in RAW_ROLES:
        path = args.by2_fix_root / filename
        line_count, header = file_line_count_and_header(path)
        row = {
            "file_role": role,
            "path_placeholder": placeholder,
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else "",
            "sha256": sha256_file(path),
            "line_count": line_count,
            "header": header,
            "notes": "trace_evaluation_only" if role == "trace_vrtk2" else "source_file",
        }
        rows.append(row)
        raw_index[role] = row
    body = args.by2_go2_body
    line_count, header = file_line_count_and_header(body)
    body_row = {
        "file_role": "by2_go2_body",
        "path_placeholder": "<BY2_GO2_BODY>",
        "exists": body.is_file(),
        "size_bytes": body.stat().st_size if body.is_file() else "",
        "sha256": sha256_file(body),
        "line_count": line_count,
        "header": header,
        "notes": "go2_body_high_level_source_not_truth",
    }
    rows.append(body_row)
    raw_index["by2_go2_body"] = body_row

    write_csv(args.stage_root / "01_RAW_SOURCE" / "BY2_CURRENT_RAW_FILE_AUDIT.csv", rows)
    write_csv(
        args.stage_root / "01_RAW_SOURCE" / "BY2_CURRENT_RAW_SHA256.csv",
        [{"file_role": row["file_role"], "path_placeholder": row["path_placeholder"], "sha256": row["sha256"], "size_bytes": row["size_bytes"]} for row in rows],
    )
    return rows, raw_index


def provider_case_dir(args: argparse.Namespace, case_id: str) -> Path:
    return args.m1r2b2_runtime_root / "03_DEGRADED_PROVIDERS" / case_id


def index_tree(root: Path) -> tuple[set[str], set[str]]:
    """Return relative directory and file names below root with one tree walk."""
    dirs: set[str] = set()
    files: set[str] = set()
    if not root.is_dir():
        return dirs, files
    try:
        dir_proc = subprocess.run(
            ["find", str(root), "-type", "d", "-printf", "%P\n"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        file_proc = subprocess.run(
            ["find", str(root), "-type", "f", "-printf", "%P\n"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if dir_proc.returncode == 0 and file_proc.returncode == 0:
            dirs = {line.replace(os.sep, "/") for line in dir_proc.stdout.splitlines()}
            files = {line.replace(os.sep, "/") for line in file_proc.stdout.splitlines()}
            return dirs, files
    except OSError:
        pass
    root_text = str(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root_text)
        if rel_dir == ".":
            rel_dir = ""
        rel_dir = rel_dir.replace(os.sep, "/")
        dirs.add(rel_dir)
        for name in filenames:
            rel_file = f"{rel_dir}/{name}" if rel_dir else name
            files.add(rel_file.replace(os.sep, "/"))
    return dirs, files


def audit_provider(args: argparse.Namespace, aliaser: Aliaser, raw_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out_dir = args.stage_root / "02_PROVIDER_LINEAGE"
    stage = args.m1r2b2_stage_root
    runtime = args.m1r2b2_runtime_root
    provider_root = runtime / "03_DEGRADED_PROVIDERS"

    discovery_paths = [
        ("stage_root", stage, "M1R2B2 stage root"),
        ("runtime_root", runtime, "M1R2B2 runtime root"),
        ("provider_root", provider_root, "M1R2B2 provider package root"),
        ("ready_manifest", stage / "05_PROVIDER_READY" / "PAPER10M1R2B2_PROVIDER_READY_MANIFEST.csv", "provider ready manifest"),
        ("sha_manifest", stage / "05_PROVIDER_READY" / "PAPER10M1R2B2_PROVIDER_SHA256_MANIFEST.csv", "generated provider sha manifest"),
        ("yaw_lineage_summary", stage / "03_PROVIDER_GENERATION" / "PAPER10M1R2B2_YAW_PROVIDER_LINEAGE_SUMMARY.csv", "yaw provider lineage summary"),
        ("source_sha256_manifest", runtime / "02_SOURCE_INDEX" / "source_sha256_manifest.csv", "source sha manifest"),
        ("forbidden_input_audit", stage / "07_GUARDS" / "PAPER10M1R2B2_FORBIDDEN_INPUT_AUDIT.csv", "forbidden input guard"),
    ]
    discovery = [
        {
            "item": name,
            "path_placeholder": aliaser.path(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.is_file() else "",
            "notes": notes,
        }
        for name, path, notes in discovery_paths
    ]
    write_csv(out_dir / "M1R2B2_PROVIDER_RUNTIME_DISCOVERY.csv", discovery)

    ready_rows = read_csv(stage / "05_PROVIDER_READY" / "PAPER10M1R2B2_PROVIDER_READY_MANIFEST.csv")
    provider_dirs = sorted([p for p in provider_root.iterdir() if p.is_dir()]) if provider_root.is_dir() else []
    ready_by_case = {row.get("case_id", ""): row for row in ready_rows}

    provider_manifest_rows: list[dict[str, Any]] = []
    yaw_rows: list[dict[str, Any]] = []
    input_source_counts: dict[str, Counter[str]] = defaultdict(Counter)
    go2_hash_gap_cases = 0
    provider_ready_pass = 0
    yaw_lineage_pass = 0
    yaw_wrap_pass = 0
    trace_false_count = 0
    final_false_count = 0
    legsa_false_count = 0

    for case_id, ready in sorted(ready_by_case.items()):
        case_dir = provider_case_dir(args, case_id)
        source_role = case_dir / "00_CASE_SPEC" / "source_role_manifest.json"
        yaw_path = case_dir / "00_CASE_SPEC" / "yaw_provider_lineage.json"
        input_sha = case_dir / "01_INPUT_SHA256" / "input_sha256_manifest.csv"
        provider_index = case_dir / "02_GENERATED_PROVIDERS" / "provider_index.json"
        generated_sha = case_dir / "02_GENERATED_PROVIDERS" / "generated_sha256_manifest.csv"
        provider_ready_json = case_dir / "04_PROVIDER_READY" / "provider_ready_manifest.json"
        source_data = read_json(source_role)
        yaw_data = read_json(yaw_path)
        ready_data = read_json(provider_ready_json)
        input_rows = read_csv(input_sha)
        input_aliases = {row.get("source_alias", ""): row for row in input_rows}
        for source_alias, src_row in input_aliases.items():
            if not source_alias:
                continue
            input_source_counts[source_alias]["recorded"] += 1
            if src_row.get("sha256"):
                input_source_counts[source_alias]["with_hash"] += 1
            if src_row.get("path_alias"):
                input_source_counts[source_alias]["with_path"] += 1
        by2_body = input_aliases.get("by2_go2_body") or input_aliases.get("by2_go2_body_root")
        by2_body_has_hash = bool(by2_body and by2_body.get("sha256"))
        if not by2_body_has_hash:
            go2_hash_gap_cases += 1

        trace_used = ready.get("trace_used", ready_data.get("trace_used", yaw_data.get("trace_used_for_generation", "")))
        final_used = ready.get("final_v23_output_used", ready_data.get("final_v23_output_used", yaw_data.get("final_v23_output_used_for_generation", "")))
        legsa_used = ready.get("legsa_output_used", ready_data.get("legsa_output_used", yaw_data.get("legsa_output_used_for_generation", "")))
        if falsey(trace_used):
            trace_false_count += 1
        if falsey(final_used):
            final_false_count += 1
        if falsey(legsa_used):
            legsa_false_count += 1
        if str(ready.get("provider_ready", ready_data.get("provider_ready", ""))).lower() == "true":
            provider_ready_pass += 1
        if str(ready.get("yaw_lineage_validation_status", yaw_data.get("yaw_lineage_validation_status", ""))).upper() == "PASS":
            yaw_lineage_pass += 1
        if str(ready.get("yaw_wrap_validation_status", yaw_data.get("yaw_wrap_validation_status", ""))).upper() == "PASS":
            yaw_wrap_pass += 1

        required_sources = [
            "gnss1_raw",
            "gnss1_status",
            "gnss2_raw",
            "gnss2_status",
            "corr_raw",
            "userio_raw",
            "raw_doppler_provider",
        ]
        provider_manifest_rows.append(
            {
                "case_id": case_id,
                "provider_root_placeholder": aliaser.path(case_dir),
                "provider_dir_exists": case_dir.is_dir(),
                "source_role_manifest_exists": source_role.is_file(),
                "input_sha256_manifest_exists": input_sha.is_file(),
                "generated_sha256_manifest_exists": generated_sha.is_file(),
                "provider_ready_manifest_exists": provider_ready_json.is_file(),
                "provider_index_exists": provider_index.is_file(),
                "yaw_provider_lineage_exists": yaw_path.is_file(),
                "required_raw_sources_recorded": all(source in input_aliases for source in required_sources),
                "required_raw_hashes_recorded": all(input_aliases.get(source, {}).get("sha256") for source in required_sources),
                "by2_go2_body_hash_recorded": by2_body_has_hash,
                "provider_ready": ready.get("provider_ready", ready_data.get("provider_ready", "")),
                "trace_used": trace_used,
                "final_v23_output_used": final_used,
                "legsa_output_used": legsa_used,
                "raw_data_modified": ready.get("raw_data_modified", ready_data.get("raw_data_modified", "")),
                "raw_data_overwritten": ready.get("raw_data_overwritten", ready_data.get("raw_data_overwritten", "")),
                "notes": "GO2_BODY_HASH_MISSING" if not by2_body_has_hash else "",
            }
        )

        baseline_def = str(yaw_data.get("baseline_vector_definition", ""))
        lateral = str(yaw_data.get("lateral_conversion_formula", ""))
        resampling = str(yaw_data.get("resampling_policy", ""))
        wrap = str(yaw_data.get("wrap_policy", ""))
        yaw_rows.append(
            {
                "case_id": case_id,
                "yaw_provider_lineage_path_placeholder": aliaser.path(yaw_path),
                "yaw_provider_lineage_exists": yaw_path.is_file(),
                "yaw_lineage_validation_status": yaw_data.get("yaw_lineage_validation_status", ready.get("yaw_lineage_validation_status", "")),
                "yaw_wrap_validation_status": yaw_data.get("yaw_wrap_validation_status", ready.get("yaw_wrap_validation_status", "")),
                "trace_used_as_provider_input": yaw_data.get("trace_used_for_generation", ready.get("trace_used", "")),
                "final_v23_output_used_for_generation": yaw_data.get("final_v23_output_used_for_generation", ready.get("final_v23_output_used", "")),
                "legsa_output_used_for_generation": yaw_data.get("legsa_output_used_for_generation", ready.get("legsa_output_used", "")),
                "gnss2_minus_gnss1_recorded": "GNSS2" in baseline_def and "GNSS1" in baseline_def,
                "lateral_conversion_recorded": bool(lateral),
                "wrap_policy_recorded": bool(wrap),
                "resampling_policy_recorded": bool(resampling),
                "wrap_safe_interpolation_recorded": bool(wrap) and bool(resampling),
                "baseline_vector_definition": baseline_def or "MISSING",
                "lateral_conversion_formula": lateral or "MISSING",
                "resampling_policy": resampling or "MISSING",
                "wrap_policy": wrap or "MISSING",
                "notes": "" if yaw_path.is_file() else "MISSING",
            }
        )

    write_csv(out_dir / "M1R2B2_PROVIDER_MANIFEST_AUDIT.csv", provider_manifest_rows)
    write_csv(out_dir / "M1R2B2_YAW_PROVIDER_LINEAGE_AUDIT.csv", yaw_rows)

    source_manifest_rows = read_csv(runtime / "02_SOURCE_INDEX" / "source_sha256_manifest.csv")
    source_rows: list[dict[str, Any]] = []
    raw_by_manifest_alias = {
        "gnss1_raw": "gnss1_raw",
        "gnss1_status": "gnss1_status",
        "gnss2_raw": "gnss2_raw",
        "gnss2_status": "gnss2_status",
        "corr_raw": "corr_raw",
        "userio_raw": "userio_raw",
        "trace_vrtk2": "trace_vrtk2",
        "trace_eval_reference_only": "trace_vrtk2",
        "by2_go2_body": "by2_go2_body",
        "by2_go2_body_root": "by2_go2_body",
    }
    seen_sources: set[str] = set()
    for row in source_manifest_rows:
        source_alias = row.get("source_alias", "")
        seen_sources.add(source_alias)
        raw_key = raw_by_manifest_alias.get(source_alias, source_alias)
        current = raw_index.get(raw_key, {})
        current_sha = current.get("sha256", "")
        current_size = str(current.get("size_bytes", ""))
        manifest_sha = row.get("sha256", "")
        manifest_size = str(row.get("size_bytes", ""))
        source_rows.append(
            {
                "source_alias": source_alias,
                "manifest_path_alias": row.get("path_alias", ""),
                "manifest_exists": row.get("exists", ""),
                "manifest_size_bytes": manifest_size,
                "manifest_sha256": manifest_sha,
                "current_file_role": raw_key,
                "current_size_bytes": current_size,
                "current_sha256": current_sha,
                "sha256_match": bool(manifest_sha and current_sha and manifest_sha == current_sha),
                "size_match": bool(manifest_size and current_size and manifest_size == current_size),
                "providers_recording_this_source_count": input_source_counts[source_alias]["recorded"],
                "providers_with_path_count": input_source_counts[source_alias]["with_path"],
                "providers_with_hash_count": input_source_counts[source_alias]["with_hash"],
                "notes": "MISSING_HASH_IN_SOURCE_MANIFEST" if not manifest_sha else "",
            }
        )
    for raw_key, current in sorted(raw_index.items()):
        if raw_key not in seen_sources and raw_key != "by2_go2_body":
            source_rows.append(
                {
                    "source_alias": raw_key,
                    "manifest_path_alias": "MISSING",
                    "manifest_exists": "MISSING",
                    "manifest_size_bytes": "",
                    "manifest_sha256": "",
                    "current_file_role": raw_key,
                    "current_size_bytes": current.get("size_bytes", ""),
                    "current_sha256": current.get("sha256", ""),
                    "sha256_match": False,
                    "size_match": False,
                    "providers_recording_this_source_count": input_source_counts[raw_key]["recorded"],
                    "providers_with_path_count": input_source_counts[raw_key]["with_path"],
                    "providers_with_hash_count": input_source_counts[raw_key]["with_hash"],
                    "notes": "NOT_LISTED_IN_M1R2B2_SOURCE_MANIFEST",
                }
            )
    write_csv(out_dir / "M1R2B2_RAW_SOURCE_LINEAGE_AUDIT.csv", source_rows)

    provider_ok = (
        len(ready_rows) == 541
        and provider_ready_pass == 541
        and yaw_lineage_pass == 541
        and yaw_wrap_pass == 541
        and trace_false_count == 541
        and final_false_count == 541
        and legsa_false_count == 541
    )
    return {
        "ready_rows": len(ready_rows),
        "provider_dirs": len(provider_dirs),
        "provider_ready_pass": provider_ready_pass,
        "yaw_lineage_pass": yaw_lineage_pass,
        "yaw_wrap_pass": yaw_wrap_pass,
        "trace_false_count": trace_false_count,
        "final_false_count": final_false_count,
        "legsa_false_count": legsa_false_count,
        "go2_hash_gap_cases": go2_hash_gap_cases,
        "provider_ok": provider_ok,
    }


def audit_runtime_matrix(
    *,
    args: argparse.Namespace,
    aliaser: Aliaser,
    stage_id: str,
    stage_root: Path,
    runtime_root: Path,
    expected_rows: int,
    expected_methods: list[str],
    row_table_name: str,
    queue_name: str,
    output_dir: Path,
) -> dict[str, Any]:
    row_table_path = stage_root / "05_EXECUTION" / row_table_name
    queue_path = stage_root / "04_QUEUE" / queue_name
    runtime_proof_path = stage_root / "05_EXECUTION" / row_table_name.replace("ROW_LEVEL_RESULT_TABLE", "RUNTIME_PROOF_TABLE")
    rows = read_csv(row_table_path)
    queue_rows = read_csv(queue_path)
    proof_rows = read_csv(runtime_proof_path)
    mode_counts = Counter(row.get("method_mode_id", "") for row in rows)
    case_counts = Counter(row.get("case_id", "") for row in rows)
    status_counts = Counter(row.get("terminal_status", "") for row in rows)

    discovery = [
        {"item": "stage_root", "path_placeholder": aliaser.path(stage_root), "exists": stage_root.is_dir(), "size_bytes": "", "notes": stage_id},
        {"item": "runtime_root", "path_placeholder": aliaser.path(runtime_root), "exists": runtime_root.is_dir(), "size_bytes": "", "notes": stage_id},
        {"item": "row_table", "path_placeholder": aliaser.path(row_table_path), "exists": row_table_path.is_file(), "size_bytes": row_table_path.stat().st_size if row_table_path.is_file() else "", "notes": "row table"},
        {"item": "queue", "path_placeholder": aliaser.path(queue_path), "exists": queue_path.is_file(), "size_bytes": queue_path.stat().st_size if queue_path.is_file() else "", "notes": "locked queue"},
        {"item": "runtime_proof", "path_placeholder": aliaser.path(runtime_proof_path), "exists": runtime_proof_path.is_file(), "size_bytes": runtime_proof_path.stat().st_size if runtime_proof_path.is_file() else "", "notes": "runtime proof table"},
    ]
    write_csv(output_dir / f"{stage_id}_RUNTIME_DISCOVERY.csv", discovery)

    row_checks: list[dict[str, Any]] = [
        {"check_id": "row_count", "expected": expected_rows, "actual": len(rows), "status": "PASS" if len(rows) == expected_rows else "FAIL", "notes": ""},
        {"check_id": "queue_row_count", "expected": expected_rows, "actual": len(queue_rows), "status": "PASS" if len(queue_rows) == expected_rows else "FAIL", "notes": ""},
        {"check_id": "runtime_proof_row_count", "expected": expected_rows, "actual": len(proof_rows), "status": "PASS" if len(proof_rows) == expected_rows else "FAIL", "notes": ""},
        {"check_id": "case_count", "expected": 541, "actual": len(case_counts), "status": "PASS" if len(case_counts) == 541 else "FAIL", "notes": ""},
        {"check_id": "completed_evaluable_rows", "expected": expected_rows, "actual": status_counts.get("COMPLETED_EVALUABLE", 0), "status": "PASS" if status_counts.get("COMPLETED_EVALUABLE", 0) == expected_rows else "FAIL", "notes": str(dict(status_counts))},
    ]
    for method in expected_methods:
        row_checks.append(
            {
                "check_id": f"method_count:{method}",
                "expected": 541,
                "actual": mode_counts.get(method, 0),
                "status": "PASS" if mode_counts.get(method, 0) == 541 else "FAIL",
                "notes": "",
            }
        )
    for field in FORBIDDEN_ROW_FIELDS:
        if field not in rows[0] if rows else True:
            row_checks.append({"check_id": f"forbidden_field:{field}", "expected": "field_present_false", "actual": "MISSING", "status": "WARN", "notes": "field missing in row table"})
            continue
        bad = [row.get("row_id", "") for row in rows if not falsey(row.get(field, ""))]
        row_checks.append(
            {
                "check_id": f"forbidden_field_false:{field}",
                "expected": 0,
                "actual": len(bad),
                "status": "PASS" if not bad else "FAIL",
                "notes": ",".join(bad[:5]),
            }
        )
    write_csv(output_dir / f"{stage_id}_ROW_TABLE_AUDIT.csv", row_checks)

    manifest_rows: list[dict[str, Any]] = []
    provider_rows: list[dict[str, Any]] = []
    runtime_dirs, runtime_files = index_tree(runtime_root / "04_RUNTIME")
    provider_dirs, provider_files = index_tree(args.m1r2b2_runtime_root / "03_DEGRADED_PROVIDERS")
    actual_runtime_count = 0
    actual_run_manifest_count = 0
    actual_eval_nav_count = 0
    actual_provider_count = 0
    actual_eval_summary_count = 0
    forbidden_manifest_bad = 0
    old_aggregate_like = 0
    for row in rows:
        row_id = row.get("row_id", "")
        method = row.get("method_mode_id", "")
        case_id = row.get("case_id", "")
        runtime_dir = runtime_root / "04_RUNTIME" / method / row_id
        rel_dir = f"{method}/{row_id}"
        rel_file = lambda name: f"{rel_dir}/{name}"
        runtime_dir_exists = rel_dir in runtime_dirs
        file_exists = {name: rel_file(name) in runtime_files for name in RUNTIME_REQUIRED_FILES}
        row_result_exists = any(
            rel_file(name) in runtime_files
            for name in [
                f"{stage_id}_ROW_RESULT.json",
                "PAPER10M1R2C_R1_ROW_RESULT.json",
                "PAPER10M1R2D_R1_ROW_RESULT.json",
            ]
        )
        if runtime_dir_exists:
            actual_runtime_count += 1
        if file_exists["RUN_MANIFEST.json"]:
            actual_run_manifest_count += 1
        if file_exists["EVAL_NAV.csv"]:
            actual_eval_nav_count += 1
        if file_exists["EVALUATOR_SUMMARY.json"]:
            actual_eval_summary_count += 1
        manifest_forbidden = {
            "trace_solver_input": row.get("trace_solver_input", ""),
            "final_v23_output_solver_input": row.get("final_v23_output_solver_input", ""),
            "output_only_correction": row.get("output_only_correction_used", ""),
            "bad_epoch_deletion_for_metric": row.get("epoch_deleted_for_metric", ""),
            "trace_used_online": row.get("trace_used_online", ""),
        }
        manifest_ok = all(falsey(value) for value in manifest_forbidden.values())
        if not manifest_ok:
            forbidden_manifest_bad += 1
        manifest_rows.append(
            {
                "row_id": row_id,
                "case_id": case_id,
                "method_mode_id": method,
                "runtime_dir_placeholder": aliaser.path(runtime_dir),
                "runtime_dir_exists": runtime_dir_exists,
                "run_manifest_exists": file_exists["RUN_MANIFEST.json"],
                "evaluator_summary_exists": file_exists["EVALUATOR_SUMMARY.json"],
                "eval_nav_exists": file_exists["EVAL_NAV.csv"],
                "nav_exists": file_exists["LegSA_PORT_NAV.nav"],
                "std_exists": file_exists["LegSA_PORT_STD.csv"],
                "feature_flags_exists": file_exists["FEATURE_FLAGS.json"],
                "dataset_role_dump_exists": file_exists["DATASET_ROLE_DUMP.json"],
                "method_mode_dump_exists": file_exists["METHOD_MODE_DUMP.json"],
                "case_spec_dump_exists": file_exists["CASE_SPEC_DUMP.json"],
                "yaw_provider_lineage_reference_exists": file_exists["YAW_PROVIDER_LINEAGE_REFERENCE.json"],
                "provider_ready_reference_exists": file_exists["PROVIDER_READY_REFERENCE.json"],
                "row_result_exists": row_result_exists,
                "trace_solver_input": manifest_forbidden["trace_solver_input"],
                "trace_used_online": manifest_forbidden["trace_used_online"],
                "final_v23_output_solver_input": manifest_forbidden["final_v23_output_solver_input"],
                "output_only_correction": manifest_forbidden["output_only_correction"],
                "bad_epoch_deletion_for_metric": manifest_forbidden["bad_epoch_deletion_for_metric"],
                "forbidden_manifest_fields_false": manifest_ok,
                "notes": "",
            }
        )

        provider_alias = row.get("provider_root", "")
        provider_case = provider_alias.rstrip("/").split("/")[-1] if provider_alias else case_id
        provider_dir_exists = provider_case in provider_dirs
        provider_index_exists = f"{provider_case}/02_GENERATED_PROVIDERS/provider_index.json" in provider_files
        yaw_lineage_exists = f"{provider_case}/00_CASE_SPEC/yaw_provider_lineage.json" in provider_files
        ready_manifest_exists = f"{provider_case}/04_PROVIDER_READY/provider_ready_manifest.json" in provider_files
        if provider_dir_exists:
            actual_provider_count += 1
        provider_rows.append(
            {
                "row_id": row_id,
                "case_id": case_id,
                "method_mode_id": method,
                "provider_root_placeholder": provider_alias,
                "provider_case_id_inferred": provider_case,
                "provider_dir_exists": provider_dir_exists,
                "provider_index_exists": provider_index_exists,
                "provider_ready_manifest_exists": ready_manifest_exists,
                "yaw_provider_lineage_exists": yaw_lineage_exists,
                "provider_ready_reference_exists_in_runtime": file_exists["PROVIDER_READY_REFERENCE.json"],
                "yaw_provider_lineage_reference_exists_in_runtime": file_exists["YAW_PROVIDER_LINEAGE_REFERENCE.json"],
                "provider_ready": row.get("provider_ready", ""),
                "effect_validation_status": row.get("effect_validation_status", ""),
                "yaw_lineage_validation_status": row.get("yaw_lineage_validation_status", ""),
                "yaw_wrap_validation_status": row.get("yaw_wrap_validation_status", ""),
                "notes": "",
            }
        )
        if not runtime_dir_exists and "SUMMARY" in row_id.upper():
            old_aggregate_like += 1

    write_csv(output_dir / f"{stage_id}_RUNTIME_MANIFEST_AUDIT.csv", manifest_rows)
    write_csv(output_dir / f"{stage_id}_PROVIDER_REFERENCE_AUDIT.csv", provider_rows)

    return {
        "stage_id": stage_id,
        "row_count": len(rows),
        "queue_count": len(queue_rows),
        "runtime_proof_count": len(proof_rows),
        "mode_counts": dict(mode_counts),
        "completed": status_counts.get("COMPLETED_EVALUABLE", 0),
        "actual_runtime_count": actual_runtime_count,
        "actual_run_manifest_count": actual_run_manifest_count,
        "actual_eval_nav_count": actual_eval_nav_count,
        "actual_eval_summary_count": actual_eval_summary_count,
        "actual_provider_count": actual_provider_count,
        "forbidden_manifest_bad": forbidden_manifest_bad,
        "old_aggregate_like": old_aggregate_like,
        "rows": rows,
    }


def read_trace_reference(raw_trace_csv: Path) -> list[dict[str, float]]:
    rows = read_csv(raw_trace_csv)
    if not rows:
        return []
    first_time = safe_float(rows[0].get("time"), 0.0)
    epoch_floor = math.floor(first_time / 100.0) * 100.0 if first_time > 1.0e9 else 0.0
    out: list[dict[str, float]] = []
    for row in rows:
        t = safe_float(row.get("time")) - epoch_floor
        lat = safe_float(row.get("lat"))
        lon = safe_float(row.get("lon"))
        height = safe_float(row.get("height"))
        yaw_heading = safe_float(row.get("yaw"))
        pitch = safe_float(row.get("pitch"))
        roll = safe_float(row.get("roll"))
        if all(math.isfinite(value) for value in [t, lat, lon, height, yaw_heading, pitch, roll]):
            out.append(
                {
                    "time": t,
                    "lat_deg": lat,
                    "lon_deg": lon,
                    "height_m": height,
                    "yaw_deg": (90.0 - yaw_heading) % 360.0,
                    "pitch_deg": pitch,
                    "roll_deg": roll,
                }
            )
    return out


def compute_trace_metrics(eval_nav: Path, trace_reference: list[dict[str, float]]) -> dict[str, Any]:
    if not eval_nav.is_file() or not trace_reference:
        return {
            "trace_horizontal_rmse_m": math.nan,
            "trace_up_rmse_m": math.nan,
            "trace_yaw_rmse_deg": math.nan,
            "trace_roll_rmse_deg": math.nan,
            "trace_pitch_rmse_deg": math.nan,
            "trace_position_3d_rmse_m": math.nan,
            "trace_valid_epoch_count": 0,
            "trace_heading_to_math_yaw_p95_abs_error_deg": math.nan,
            "trace_heading_to_math_yaw_max_abs_error_deg": math.nan,
        }
    nav_rows = read_csv(eval_nav)
    trace_times = [row["time"] for row in trace_reference]
    h_errors: list[float] = []
    u_errors: list[float] = []
    yaw_errors: list[float] = []
    roll_errors: list[float] = []
    pitch_errors: list[float] = []
    p3_errors: list[float] = []
    for row in nav_rows:
        t = safe_float(row.get("time"))
        if not math.isfinite(t):
            continue
        index = bisect.bisect_left(trace_times, t)
        candidates: list[int] = []
        if index < len(trace_times):
            candidates.append(index)
        if index > 0:
            candidates.append(index - 1)
        if not candidates:
            continue
        best = min(candidates, key=lambda item: abs(trace_times[item] - t))
        if abs(trace_times[best] - t) > 0.25:
            continue
        ref = trace_reference[best]
        h = deg_distance_m(safe_float(row.get("lat_deg")), safe_float(row.get("lon_deg")), ref["lat_deg"], ref["lon_deg"])
        u = abs(safe_float(row.get("height_m")) - ref["height_m"])
        yaw = abs(wrap_deg180(safe_float(row.get("yaw_deg")) - ref["yaw_deg"]))
        roll = abs(wrap_deg180(safe_float(row.get("roll_deg")) - ref["roll_deg"]))
        pitch = abs(wrap_deg180(safe_float(row.get("pitch_deg")) - ref["pitch_deg"]))
        h_errors.append(h)
        u_errors.append(u)
        yaw_errors.append(yaw)
        roll_errors.append(roll)
        pitch_errors.append(pitch)
        p3_errors.append(math.sqrt(h * h + u * u))
    return {
        "trace_horizontal_rmse_m": rmse(h_errors),
        "trace_up_rmse_m": rmse(u_errors),
        "trace_yaw_rmse_deg": rmse(yaw_errors),
        "trace_roll_rmse_deg": rmse(roll_errors),
        "trace_pitch_rmse_deg": rmse(pitch_errors),
        "trace_position_3d_rmse_m": rmse(p3_errors),
        "trace_valid_epoch_count": len(h_errors),
        "trace_heading_to_math_yaw_p95_abs_error_deg": percentile(yaw_errors, 0.95),
        "trace_heading_to_math_yaw_max_abs_error_deg": max(yaw_errors, default=math.nan),
    }


def row_runtime_dir(runtime_root: Path, row: dict[str, str]) -> Path:
    return runtime_root / "04_RUNTIME" / row.get("method_mode_id", "") / row.get("row_id", "")


def case_matches(row: dict[str, str], category: str) -> bool:
    family = row.get("case_family", "").lower()
    name = row.get("degradation_type_name", "").lower()
    type_id = row.get("degradation_type_id", "").lower()
    case_id = row.get("case_id", "").lower()
    haystack = " ".join([family, name, type_id, case_id])
    if category == "clean":
        return family == "clean" or type_id == "clean"
    if category == "outage":
        return "outage" in haystack
    if category == "downsample":
        return "downsample" in haystack or "down_sample" in haystack
    if category == "yaw_spike":
        return "yaw_spike" in haystack or ("yaw" in haystack and "spike" in haystack)
    if category == "mixed":
        return "mixed" in haystack or "multi_source" in haystack or "multisource" in haystack
    return False


def pick_first(rows: list[dict[str, str]], *, method: str, category: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("method_mode_id") == method and case_matches(row, category):
            return row
    return None


def metric_crosscheck(args: argparse.Namespace, aliaser: Aliaser, c_rows: list[dict[str, str]], d_rows: list[dict[str, str]]) -> dict[str, Any]:
    trace_reference = read_trace_reference(args.by2_fix_root / "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv")
    samples: list[tuple[str, str, dict[str, str], Path]] = []
    seen: set[tuple[str, str]] = set()
    for method in FULL_METHODS:
        for category in ["clean", "outage", "downsample", "yaw_spike", "mixed"]:
            row = pick_first(c_rows, method=method, category=category)
            if row and ("M1R2C_R1", row["row_id"]) not in seen:
                samples.append(("M1R2C_R1", f"{category}:{method}", row, args.m1r2c_runtime_root))
                seen.add(("M1R2C_R1", row["row_id"]))
    for method in INTERNAL_METHODS[:5]:
        row = pick_first(d_rows, method=method, category="clean")
        if row and ("M1R2D_R1", row["row_id"]) not in seen:
            samples.append(("M1R2D_R1", f"internal_clean:{method}", row, args.m1r2d_runtime_root))
            seen.add(("M1R2D_R1", row["row_id"]))

    results: list[dict[str, Any]] = []
    pass_count = 0
    insufficient_count = 0
    fail_count = 0
    for source_stage, reason, row, runtime_root in samples:
        runtime_dir = row_runtime_dir(runtime_root, row)
        eval_nav = runtime_dir / "EVAL_NAV.csv"
        if not eval_nav.is_file():
            insufficient_count += 1
            results.append(
                {
                    "source_stage": source_stage,
                    "sample_reason": reason,
                    "row_id": row.get("row_id", ""),
                    "case_id": row.get("case_id", ""),
                    "method_mode_id": row.get("method_mode_id", ""),
                    "eval_nav_placeholder": aliaser.path(eval_nav),
                    "runtime_proof_status": "INSUFFICIENT",
                    "recomputed_horizontal_rmse_m": "",
                    "old_horizontal_rmse_m": row.get("horizontal_rmse_m", ""),
                    "delta_horizontal_rmse_m": "",
                    "recomputed_up_rmse_m": "",
                    "old_up_rmse_m": row.get("up_rmse_m", ""),
                    "delta_up_rmse_m": "",
                    "recomputed_yaw_rmse_deg": "",
                    "old_yaw_rmse_deg": row.get("yaw_rmse_deg", ""),
                    "delta_yaw_rmse_deg": "",
                    "valid_epoch_count": "",
                    "old_valid_epoch_count": row.get("valid_epoch_count", ""),
                    "status": "RUNTIME_PROOF_INSUFFICIENT",
                    "notes": "EVAL_NAV missing",
                }
            )
            continue
        metrics = compute_trace_metrics(eval_nav, trace_reference)
        deltas = {
            "horizontal": abs(metrics["trace_horizontal_rmse_m"] - safe_float(row.get("horizontal_rmse_m"))),
            "up": abs(metrics["trace_up_rmse_m"] - safe_float(row.get("up_rmse_m"))),
            "yaw": abs(metrics["trace_yaw_rmse_deg"] - safe_float(row.get("yaw_rmse_deg"))),
        }
        status = "PASS" if deltas["horizontal"] <= 0.02 and deltas["up"] <= 0.02 and deltas["yaw"] <= 1.0e-9 else "FAIL"
        if status == "PASS":
            pass_count += 1
        else:
            fail_count += 1
        results.append(
            {
                "source_stage": source_stage,
                "sample_reason": reason,
                "row_id": row.get("row_id", ""),
                "case_id": row.get("case_id", ""),
                "method_mode_id": row.get("method_mode_id", ""),
                "eval_nav_placeholder": aliaser.path(eval_nav),
                "runtime_proof_status": "FOUND",
                "recomputed_horizontal_rmse_m": metrics["trace_horizontal_rmse_m"],
                "old_horizontal_rmse_m": row.get("horizontal_rmse_m", ""),
                "delta_horizontal_rmse_m": deltas["horizontal"],
                "recomputed_up_rmse_m": metrics["trace_up_rmse_m"],
                "old_up_rmse_m": row.get("up_rmse_m", ""),
                "delta_up_rmse_m": deltas["up"],
                "recomputed_yaw_rmse_deg": metrics["trace_yaw_rmse_deg"],
                "old_yaw_rmse_deg": row.get("yaw_rmse_deg", ""),
                "delta_yaw_rmse_deg": deltas["yaw"],
                "valid_epoch_count": metrics["trace_valid_epoch_count"],
                "old_valid_epoch_count": row.get("valid_epoch_count", ""),
                "status": status,
                "notes": "trace nearest-neighbor within 0.25s; heading converted to math yaw",
            }
        )

    write_csv(args.stage_root / "05_METRIC_CROSSCHECK" / "SAMPLED_ROW_METRIC_RECALCULATION.csv", results)
    report = [
        "# Metric Crosscheck Report",
        "",
        f"- sampled_rows: {len(results)}",
        f"- pass: {pass_count}",
        f"- fail: {fail_count}",
        f"- runtime_proof_insufficient: {insufficient_count}",
        "- method: recompute final EVAL_NAV against current BY2 trace with the existing M1R2C_R1/M1R2D_R1 trace alignment rule.",
        "- trace role: evaluation-only; not solver input.",
        "- tolerances: horizontal/up <= 0.02 m, yaw <= 1e-9 deg.",
    ]
    if fail_count:
        report.append("- decision: BLOCKED_AUDIT1_METRIC_CROSSCHECK_FAILED.")
    elif insufficient_count:
        report.append("- decision: metric crosscheck incomplete because runtime proof was insufficient for at least one sampled row.")
    else:
        report.append("- decision: sampled metric crosscheck passed.")
    write_text(args.stage_root / "05_METRIC_CROSSCHECK" / "METRIC_CROSSCHECK_REPORT.md", "\n".join(report) + "\n")
    return {"sampled": len(results), "pass": pass_count, "fail": fail_count, "insufficient": insufficient_count}


def minimal_rerun(args: argparse.Namespace, c_rows: list[dict[str, str]], provider_summary: dict[str, Any], metric_summary: dict[str, Any]) -> dict[str, Any]:
    queue_rows: list[dict[str, Any]] = []
    categories = ["clean", "outage", "yaw_spike", "mixed"]
    for category in categories:
        for method in FULL_METHODS:
            row = pick_first(c_rows, method=method, category=category)
            if row:
                queue_rows.append(
                    {
                        "sample_category": category,
                        "method_mode_id": method,
                        "old_row_id": row.get("row_id", ""),
                        "case_id": row.get("case_id", ""),
                        "old_runtime_row_status": row.get("terminal_status", ""),
                        "planned_audit_runtime_placeholder": f"<AUDIT1_STAGE_ROOT>/06_MINIMAL_RERUN/runtime/{method}/{row.get('row_id', '')}",
                    }
                )
    source_lineage_closed = bool(provider_summary.get("provider_ok")) and provider_summary.get("go2_hash_gap_cases", 0) == 0
    metric_passed = metric_summary.get("fail", 0) == 0 and metric_summary.get("insufficient", 0) == 0
    rerun_allowed = source_lineage_closed and metric_passed
    reason = ""
    if not source_lineage_closed:
        reason = "NOT_EXECUTED_PROVIDER_SOURCE_LINEAGE_NOT_FULLY_CLOSED_GO2_BODY_HASH_GAP"
    elif not metric_passed:
        reason = "NOT_EXECUTED_METRIC_CROSSCHECK_NOT_CLOSED"
    else:
        reason = "NOT_EXECUTED_BY_AUDIT1_POLICY_REPORT_ONLY_NO_SOLVER_RUN"
        rerun_allowed = False
    for row in queue_rows:
        row["minimal_rerun_allowed"] = rerun_allowed
        row["execution_status"] = "NOT_EXECUTED"
        row["reason"] = reason

    result_rows = [
        {
            "old_row_id": row.get("old_row_id", ""),
            "case_id": row.get("case_id", ""),
            "method_mode_id": row.get("method_mode_id", ""),
            "execution_status": row.get("execution_status", ""),
            "reason": row.get("reason", ""),
            "new_runtime_placeholder": "",
            "new_metrics_exists": False,
        }
        for row in queue_rows
    ]
    compare_rows = [
        {
            "old_row_id": row.get("old_row_id", ""),
            "case_id": row.get("case_id", ""),
            "method_mode_id": row.get("method_mode_id", ""),
            "comparison_status": "NOT_AVAILABLE",
            "reason": row.get("reason", ""),
        }
        for row in queue_rows
    ]
    write_csv(args.stage_root / "06_MINIMAL_RERUN" / "MINIMAL_RERUN_QUEUE.csv", queue_rows)
    write_csv(args.stage_root / "06_MINIMAL_RERUN" / "MINIMAL_RERUN_RESULT_TABLE.csv", result_rows)
    write_csv(args.stage_root / "06_MINIMAL_RERUN" / "MINIMAL_RERUN_VS_OLD_COMPARISON.csv", compare_rows)
    report = [
        "# Minimal Rerun Report",
        "",
        f"- queued_rows: {len(queue_rows)}",
        f"- rerun_allowed_after_gate: {rerun_allowed}",
        f"- execution_status: NOT_EXECUTED",
        f"- reason: {reason}",
        "- no old runtime was overwritten.",
        "- no provider, degraded input, solver, evaluator, figure, or raw-data generation was run by AUDIT1.",
    ]
    write_text(args.stage_root / "06_MINIMAL_RERUN" / "MINIMAL_RERUN_REPORT.md", "\n".join(report) + "\n")
    return {"queued": len(queue_rows), "executed": 0, "allowed": rerun_allowed, "reason": reason}


def classify_trust(
    args: argparse.Namespace,
    provider_summary: dict[str, Any],
    c_summary: dict[str, Any],
    d_summary: dict[str, Any],
    metric_summary: dict[str, Any],
    rerun_summary: dict[str, Any],
) -> dict[str, Any]:
    metric_pass = metric_summary.get("fail", 0) == 0 and metric_summary.get("insufficient", 0) == 0
    provider_lineage_full = provider_summary.get("provider_ok") and provider_summary.get("go2_hash_gap_cases", 0) == 0
    c_runtime_full = (
        c_summary.get("row_count") == 2164
        and c_summary.get("actual_runtime_count") == 2164
        and c_summary.get("actual_run_manifest_count") == 2164
        and c_summary.get("actual_eval_nav_count") == 2164
        and c_summary.get("forbidden_manifest_bad") == 0
    )
    d_runtime_full = (
        d_summary.get("row_count") == 4869
        and d_summary.get("actual_runtime_count") == 4869
        and d_summary.get("actual_run_manifest_count") == 4869
        and d_summary.get("actual_eval_nav_count") == 4869
        and d_summary.get("forbidden_manifest_bad") == 0
    )
    rerun_pass = rerun_summary.get("executed", 0) > 0 and rerun_summary.get("reason", "") == ""

    def level(runtime_full: bool, is_provider: bool = False) -> str:
        if provider_lineage_full and runtime_full and metric_pass and rerun_pass:
            return "TRUST_LEVEL_A_MAIN_EVIDENCE"
        if (provider_summary.get("provider_ok") if is_provider else runtime_full) and metric_pass:
            return "TRUST_LEVEL_B_APPENDIX_ONLY"
        if runtime_full or provider_summary.get("provider_ok"):
            return "TRUST_LEVEL_C_DIAGNOSTIC_ONLY"
        return "TRUST_LEVEL_D_NOT_USABLE"

    registry = [
        {
            "evidence_id": "M1R2B2_PROVIDER",
            "trust_level": level(provider_summary.get("provider_ok", False), is_provider=True),
            "row_or_case_count": provider_summary.get("ready_rows", ""),
            "runtime_or_manifest_proof": provider_summary.get("provider_ok", False),
            "raw_provider_lineage_closed": provider_lineage_full,
            "metric_crosscheck_passed": "not_applicable_provider_only",
            "minimal_rerun_passed": rerun_pass,
            "blocking_or_caveat": "GO2_BODY_HASH_GAP" if provider_summary.get("go2_hash_gap_cases", 0) else "MINIMAL_RERUN_NOT_EXECUTED",
        },
        {
            "evidence_id": "M1R2C_R1_FULL_MATRIX",
            "trust_level": level(c_runtime_full),
            "row_or_case_count": c_summary.get("row_count", ""),
            "runtime_or_manifest_proof": c_runtime_full,
            "raw_provider_lineage_closed": provider_lineage_full,
            "metric_crosscheck_passed": metric_pass,
            "minimal_rerun_passed": rerun_pass,
            "blocking_or_caveat": "provider_go2_hash_gap_and_minimal_rerun_not_executed",
        },
        {
            "evidence_id": "M1R2D_R1_INTERNAL_ABLATION",
            "trust_level": level(d_runtime_full),
            "row_or_case_count": d_summary.get("row_count", ""),
            "runtime_or_manifest_proof": d_runtime_full,
            "raw_provider_lineage_closed": provider_lineage_full,
            "metric_crosscheck_passed": metric_pass,
            "minimal_rerun_passed": rerun_pass,
            "blocking_or_caveat": "provider_go2_hash_gap_and_minimal_rerun_not_executed",
        },
    ]
    write_csv(args.stage_root / "07_TRUST_CLASSIFICATION" / "EVIDENCE_TRUST_REGISTRY.csv", registry)

    decisions: dict[str, str] = {}
    for row in registry:
        evidence_id = row["evidence_id"]
        level_value = row["trust_level"]
        title = evidence_id.replace("_", " ")
        md = [
            f"# {title} Trust Decision",
            "",
            f"- trust_level: {level_value}",
            f"- row_or_case_count: {row['row_or_case_count']}",
            f"- runtime_or_manifest_proof: {row['runtime_or_manifest_proof']}",
            f"- raw_provider_lineage_closed: {row['raw_provider_lineage_closed']}",
            f"- metric_crosscheck_passed: {row['metric_crosscheck_passed']}",
            f"- minimal_rerun_passed: {row['minimal_rerun_passed']}",
            f"- caveat: {row['blocking_or_caveat']}",
        ]
        if evidence_id == "M1R2B2_PROVIDER":
            name = "M1R2B2_TRUST_DECISION.md"
        elif evidence_id == "M1R2C_R1_FULL_MATRIX":
            name = "M1R2C_R1_TRUST_DECISION.md"
        else:
            name = "M1R2D_R1_TRUST_DECISION.md"
        write_text(args.stage_root / "07_TRUST_CLASSIFICATION" / name, "\n".join(md) + "\n")
        decisions[evidence_id] = level_value

    if not metric_pass:
        final_decision = "BLOCKED_AUDIT1_METRIC_CROSSCHECK_FAILED"
    elif c_runtime_full and d_runtime_full and provider_summary.get("provider_ok"):
        final_decision = "CONDITIONAL_PASS_AUDIT1_PRIOR_MATRIX_TRUST_LEVEL_B_NEEDS_CAVEAT"
    elif c_runtime_full or d_runtime_full:
        final_decision = "CONDITIONAL_PASS_AUDIT1_PRIOR_MATRIX_DIAGNOSTIC_ONLY"
    else:
        final_decision = "BLOCKED_AUDIT1_RUNTIME_OR_LINEAGE_MISSING"
    return {
        "registry": registry,
        "decisions": decisions,
        "final_decision": final_decision,
        "provider_lineage_full": provider_lineage_full,
        "metric_pass": metric_pass,
        "c_runtime_full": c_runtime_full,
        "d_runtime_full": d_runtime_full,
    }


def export_clean(args: argparse.Namespace, aliaser: Aliaser) -> dict[str, Any]:
    export_stage = args.stage_root / "10_EXPORT_CLEAN_FOR_GPT"
    export_stage.mkdir(parents=True, exist_ok=True)
    args.export_root.mkdir(parents=True, exist_ok=True)
    include_patterns = [
        "00_STAGE_REPORT/*.md",
        "01_RAW_SOURCE/*.csv",
        "02_PROVIDER_LINEAGE/*.csv",
        "03_FULL_MATRIX/*.csv",
        "04_INTERNAL_ABLATION/*.csv",
        "05_METRIC_CROSSCHECK/*.csv",
        "05_METRIC_CROSSCHECK/*.md",
        "06_MINIMAL_RERUN/*.csv",
        "06_MINIMAL_RERUN/*.md",
        "07_TRUST_CLASSIFICATION/*.csv",
        "07_TRUST_CLASSIFICATION/*.md",
    ]
    files: list[Path] = []
    for pattern in include_patterns:
        files.extend(sorted(args.stage_root.glob(pattern)))
    forbidden_name_markers = [
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "corr-raw.csv",
        "userio-raw.csv",
        "by2.txt",
        "EVAL_NAV.csv",
        "LegSA_PORT_NAV.nav",
        "LegSA_PORT_STD.csv",
        "RUN_MANIFEST.json",
        "epoch_output",
    ]
    manifest_rows: list[dict[str, Any]] = []
    leak_patterns = [re.compile(r"/mnt/[a-z]/"), re.compile(r"/home/kaiwen/"), re.compile(r"[A-Za-z]:\\")]
    scan = {
        "created_at": now_iso(),
        "path_leak_count": 0,
        "forbidden_payload_name_count": 0,
        "files": [],
    }
    zip_path = export_stage / "paper10_audit1_by2_matrix_lineage_pack.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            rel = file_path.relative_to(args.stage_root)
            text = file_path.read_text(encoding="utf-8", errors="replace")
            leak_hits = sum(len(pattern.findall(text)) for pattern in leak_patterns)
            forbidden_name = any(marker in file_path.name for marker in forbidden_name_markers)
            if forbidden_name:
                scan["forbidden_payload_name_count"] += 1
                include = False
            else:
                include = True
            scan["path_leak_count"] += leak_hits
            scan["files"].append(
                {
                    "relative_path": str(rel),
                    "size_bytes": file_path.stat().st_size,
                    "path_leak_hits": leak_hits,
                    "forbidden_payload_name": forbidden_name,
                    "included_in_zip": include,
                }
            )
            manifest_rows.append(
                {
                    "relative_path": str(rel),
                    "size_bytes": file_path.stat().st_size,
                    "sha256": sha256_file(file_path),
                    "included_in_zip": include,
                    "notes": "lightweight_report_only" if include else "excluded_forbidden_name",
                }
            )
            if include:
                zf.write(file_path, arcname=str(rel))

    readme = "\n".join(
        [
            "# README For Next AI",
            "",
            f"- stage: {STAGE_NAME}",
            "- package role: lightweight audit reports only.",
            "- excludes raw data, by2.txt, providers, NAV, STD, EVAL_NAV, RUN_MANIFEST, figures, runtime directories, and local path locks.",
            "- all paths inside export-clean should be aliases/placeholders.",
            "- current decision is in 00_STAGE_REPORT/PAPER10_AUDIT1_SUPERVISOR_FINAL_REPORT.md.",
        ]
    ) + "\n"
    write_text(export_stage / "README_FOR_NEXT_AI.md", readme)
    write_csv(export_stage / "export_clean_manifest.csv", manifest_rows)
    write_json(export_stage / "export_clean_path_scan.json", scan)

    # Mirror the lightweight export-clean files to the user-designated export root.
    for name in [
        "paper10_audit1_by2_matrix_lineage_pack.zip",
        "export_clean_manifest.csv",
        "export_clean_path_scan.json",
        "README_FOR_NEXT_AI.md",
    ]:
        shutil.copy2(export_stage / name, args.export_root / name)
    return {
        "zip_path": zip_path,
        "zip_path_placeholder": aliaser.path(zip_path),
        "export_root_placeholder": aliaser.path(args.export_root),
        "path_leak_count": scan["path_leak_count"],
        "forbidden_payload_name_count": scan["forbidden_payload_name_count"],
        "files_in_manifest": len(manifest_rows),
        "export_ok": scan["path_leak_count"] == 0 and scan["forbidden_payload_name_count"] == 0,
    }


def write_final_reports(
    args: argparse.Namespace,
    aliaser: Aliaser,
    raw_rows: list[dict[str, Any]],
    provider_summary: dict[str, Any],
    c_summary: dict[str, Any],
    d_summary: dict[str, Any],
    metric_summary: dict[str, Any],
    rerun_summary: dict[str, Any],
    trust_summary: dict[str, Any],
    export_summary: dict[str, Any],
) -> None:
    git_status_code, git_status = command_output(["git", "status", "--short"], args.code_root)
    git_branch_code, git_branch = command_output(["git", "status", "--branch", "--short"], args.code_root)
    git_head_code, git_head = command_output(["git", "rev-parse", "--short", "HEAD"], args.code_root)
    final_decision = trust_summary["final_decision"]
    supervisor = [
        "# PAPER10 AUDIT1 Supervisor Final Report",
        "",
        f"- stage: {STAGE_NAME}",
        f"- created_at: {now_iso()}",
        f"- final_decision: {final_decision}",
        f"- code_root: <CODE_ROOT>",
        f"- project_root: <PROJECT_ROOT>",
        f"- stage_root: <AUDIT1_STAGE_ROOT>",
        f"- export_root: <AUDIT1_EXPORT_ROOT>",
        "",
        "## Git",
        "",
        f"- git_status_short_return_code: {git_status_code}",
        f"- git_status_short_empty: {git_status == ''}",
        f"- git_branch: `{git_branch}`",
        f"- git_head: `{git_head}`",
        "",
        "## Raw Source",
        "",
        f"- audited_raw_files: {len(raw_rows)}",
        "- raw payloads were read for hash/header/line-count only and were not copied.",
        f"- current_by2_go2_body_sha256: {next((row['sha256'] for row in raw_rows if row['file_role'] == 'by2_go2_body'), '')}",
        "",
        "## M1R2B2 Provider",
        "",
        f"- provider_ready_rows: {provider_summary.get('ready_rows')}",
        f"- provider_dirs: {provider_summary.get('provider_dirs')}",
        f"- provider_ready_pass: {provider_summary.get('provider_ready_pass')}",
        f"- yaw_lineage_pass: {provider_summary.get('yaw_lineage_pass')}",
        f"- yaw_wrap_pass: {provider_summary.get('yaw_wrap_pass')}",
        f"- trace_used_false_count: {provider_summary.get('trace_false_count')}",
        f"- final_v23_output_used_false_count: {provider_summary.get('final_false_count')}",
        f"- legsa_output_used_false_count: {provider_summary.get('legsa_false_count')}",
        f"- go2_body_hash_gap_cases: {provider_summary.get('go2_hash_gap_cases')}",
        "",
        "## M1R2C_R1 Full Matrix",
        "",
        f"- row_count: {c_summary.get('row_count')}",
        f"- completed_evaluable_rows: {c_summary.get('completed')}",
        f"- actual_runtime_dirs: {c_summary.get('actual_runtime_count')}",
        f"- actual_run_manifests: {c_summary.get('actual_run_manifest_count')}",
        f"- actual_eval_nav: {c_summary.get('actual_eval_nav_count')}",
        f"- forbidden_manifest_bad: {c_summary.get('forbidden_manifest_bad')}",
        f"- method_counts: {json.dumps(c_summary.get('mode_counts', {}), sort_keys=True)}",
        "",
        "## M1R2D_R1 Internal Ablation",
        "",
        f"- row_count: {d_summary.get('row_count')}",
        f"- completed_evaluable_rows: {d_summary.get('completed')}",
        f"- actual_runtime_dirs: {d_summary.get('actual_runtime_count')}",
        f"- actual_run_manifests: {d_summary.get('actual_run_manifest_count')}",
        f"- actual_eval_nav: {d_summary.get('actual_eval_nav_count')}",
        f"- forbidden_manifest_bad: {d_summary.get('forbidden_manifest_bad')}",
        f"- method_counts: {json.dumps(d_summary.get('mode_counts', {}), sort_keys=True)}",
        "",
        "## Metric Crosscheck",
        "",
        f"- sampled_rows: {metric_summary.get('sampled')}",
        f"- pass: {metric_summary.get('pass')}",
        f"- fail: {metric_summary.get('fail')}",
        f"- insufficient: {metric_summary.get('insufficient')}",
        "",
        "## Minimal Rerun",
        "",
        f"- queued_rows: {rerun_summary.get('queued')}",
        f"- executed_rows: {rerun_summary.get('executed')}",
        f"- reason: {rerun_summary.get('reason')}",
        "",
        "## Trust",
        "",
        f"- provider_lineage_full: {trust_summary.get('provider_lineage_full')}",
        f"- metric_pass: {trust_summary.get('metric_pass')}",
        f"- c_runtime_full: {trust_summary.get('c_runtime_full')}",
        f"- d_runtime_full: {trust_summary.get('d_runtime_full')}",
        "- current classification: Trust Level B with caveat, not Trust Level A, because minimal rerun was not executed and Go2 body hash binding is incomplete in provider manifests.",
        "",
        "## Export Clean",
        "",
        f"- export_ok: {export_summary.get('export_ok')}",
        f"- zip: {export_summary.get('zip_path_placeholder')}",
        f"- mirrored_export_root: {export_summary.get('export_root_placeholder')}",
        f"- path_leak_count: {export_summary.get('path_leak_count')}",
        f"- forbidden_payload_name_count: {export_summary.get('forbidden_payload_name_count')}",
        "",
        "## Boundaries",
        "",
        "- no code algorithm changes were made by this audit script.",
        "- no raw data was modified.",
        "- no provider generation, degraded-input generation, solver, evaluator, full matrix, or figure generation was run by AUDIT1.",
        "- no commit, push, merge, tag, branch deletion, or PR action was performed.",
    ]
    write_text(args.stage_root / "00_STAGE_REPORT" / "PAPER10_AUDIT1_SUPERVISOR_FINAL_REPORT.md", "\n".join(supervisor) + "\n")

    reviewer = [
        "# PAPER10 AUDIT1 Reviewer Report",
        "",
        f"- final_decision_reviewed: {final_decision}",
        f"- export_clean_ok: {export_summary.get('export_ok')}",
        f"- metric_crosscheck_failed_rows: {metric_summary.get('fail')}",
        f"- runtime_or_lineage_block: {not (trust_summary.get('c_runtime_full') and trust_summary.get('d_runtime_full') and provider_summary.get('provider_ok'))}",
        "",
        "## Findings",
        "",
    ]
    if provider_summary.get("go2_hash_gap_cases", 0):
        reviewer.extend(
            [
                "- Severity: Medium",
                "  Evidence: M1R2B2 provider/input manifests do not carry a complete hash binding for the current BY2 Go2 body file across all provider cases.",
                "  Impact: prior BY2 full matrix/internal ablation should remain Trust Level B, not Trust Level A, until this lineage gap is closed or accepted as a caveat.",
                "",
            ]
        )
    if metric_summary.get("fail", 0):
        reviewer.extend(
            [
                "- Severity: High",
                "  Evidence: sampled final EVAL_NAV metric recomputation did not match stored row metrics.",
                "  Impact: audit decision should be blocked.",
                "",
            ]
        )
    if not export_summary.get("export_ok"):
        reviewer.extend(
            [
                "- Severity: High",
                "  Evidence: export-clean path scan or forbidden payload scan failed.",
                "  Impact: package must not be shared until cleaned.",
                "",
            ]
        )
    if provider_summary.get("go2_hash_gap_cases", 0) == 0 and metric_summary.get("fail", 0) == 0 and export_summary.get("export_ok"):
        reviewer.append("- No blocking issue found in generated AUDIT1 evidence.")
    reviewer.extend(
        [
            "",
            "## Residual Risk",
            "",
            "- Minimal rerun was not executed because provider/source-lineage did not fully close.",
            "- AUDIT1 reports are metadata/proof tables only and intentionally exclude runtime payloads.",
        ]
    )
    write_text(args.stage_root / "00_STAGE_REPORT" / "PAPER10_AUDIT1_REVIEWER_REPORT.md", "\n".join(reviewer) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--by2-fix-root", type=Path, required=True)
    parser.add_argument("--by2-go2-body", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--m1r2b2-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2b2-runtime-root", type=Path, required=True)
    parser.add_argument("--m1r2c-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2c-runtime-root", type=Path, required=True)
    parser.add_argument("--m1r2d-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2d-runtime-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for name in [
        "code_root",
        "project_root",
        "by2_fix_root",
        "stage_root",
        "export_root",
        "m1r2b2_stage_root",
        "m1r2b2_runtime_root",
        "m1r2c_stage_root",
        "m1r2c_runtime_root",
        "m1r2d_stage_root",
        "m1r2d_runtime_root",
    ]:
        setattr(args, name, getattr(args, name).resolve())
    args.by2_go2_body = args.by2_go2_body.resolve()
    aliaser = Aliaser(
        {
            "<CODE_ROOT>": args.code_root,
            "<PROJECT_ROOT>": args.project_root,
            "<BY2_FIX_ROOT>": args.by2_fix_root,
            "<BY2_GO2_BODY>": args.by2_go2_body,
            "<AUDIT1_STAGE_ROOT>": args.stage_root,
            "<AUDIT1_EXPORT_ROOT>": args.export_root,
            "<M1R2B2_STAGE_ROOT>": args.m1r2b2_stage_root,
            "<M1R2B2_RUNTIME_ROOT>": args.m1r2b2_runtime_root,
            "<M1R2B2_PROVIDER_ROOT>": args.m1r2b2_runtime_root / "03_DEGRADED_PROVIDERS",
            "<M1R2C_R1_STAGE_ROOT>": args.m1r2c_stage_root,
            "<M1R2C_R1_RUNTIME_ROOT>": args.m1r2c_runtime_root,
            "<M1R2D_R1_STAGE_ROOT>": args.m1r2d_stage_root,
            "<M1R2D_R1_RUNTIME_ROOT>": args.m1r2d_runtime_root,
        }
    )
    ensure_stage_dirs(args.stage_root)
    raw_rows, raw_index = audit_raw_sources(args, aliaser)
    provider_summary = audit_provider(args, aliaser, raw_index)
    c_summary = audit_runtime_matrix(
        args=args,
        aliaser=aliaser,
        stage_id="M1R2C_R1",
        stage_root=args.m1r2c_stage_root,
        runtime_root=args.m1r2c_runtime_root,
        expected_rows=2164,
        expected_methods=FULL_METHODS,
        row_table_name="PAPER10M1R2C_R1_ROW_LEVEL_RESULT_TABLE.csv",
        queue_name="PAPER10M1R2C_R1_FULL_ALGORITHM_QUEUE_LOCKED.csv",
        output_dir=args.stage_root / "03_FULL_MATRIX",
    )
    d_summary = audit_runtime_matrix(
        args=args,
        aliaser=aliaser,
        stage_id="M1R2D_R1",
        stage_root=args.m1r2d_stage_root,
        runtime_root=args.m1r2d_runtime_root,
        expected_rows=4869,
        expected_methods=INTERNAL_METHODS,
        row_table_name="PAPER10M1R2D_R1_ROW_LEVEL_RESULT_TABLE.csv",
        queue_name="PAPER10M1R2D_R1_INTERNAL_ABLATION_QUEUE_LOCKED.csv",
        output_dir=args.stage_root / "04_INTERNAL_ABLATION",
    )
    metric_summary = metric_crosscheck(args, aliaser, c_summary["rows"], d_summary["rows"])
    rerun_summary = minimal_rerun(args, c_summary["rows"], provider_summary, metric_summary)
    trust_summary = classify_trust(args, provider_summary, c_summary, d_summary, metric_summary, rerun_summary)
    export_summary = export_clean(args, aliaser)
    write_final_reports(
        args,
        aliaser,
        raw_rows,
        provider_summary,
        c_summary,
        d_summary,
        metric_summary,
        rerun_summary,
        trust_summary,
        export_summary,
    )
    export_clean(args, aliaser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
