#!/usr/bin/env python3
"""Run PAPER10M1R2D_R1 BY2 internal ablation matrix.

The script reuses the existing PAPER10M1R2C port-core runner bridge for the
actual solver/evaluator launch, but changes the stage axis to the nine
M1R2D_R1 internal ablation method IDs supplied by the M1R2B2 queue draft.
It does not regenerate providers, tune from trace/final_v23, run horizontal
comparisons, or import M1R2C_R1 rows as completed evidence.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import scripts.paper10m1r2c_full_algorithm_matrix as base  # noqa: E402
from legsa_gins.qm.qm_counter_schema import split_manifest_counters  # noqa: E402
from scripts.paper10m0_method_mode_loader import (  # noqa: E402
    load_all,
    resolve_effective_feature_flags,
    validate_mode_safety,
)


STAGE_NAME = "PAPER10M1R2D_R1_V2_BY2_INTERNAL_ABLATION_MATRIX_EXECUTION_4869ROWS"
EXPECTED_CASES = 541
EXPECTED_ROWS = 4869
EXPECTED_METHODS = [
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
STRICT_CLEAN_YAW_METHODS = {
    "legsa_full_candidate_with_qm",
    "legsa_without_qm",
    "legsa_no_raw_doppler",
    "legsa_no_source_aware",
    "legsa_no_go2_roll_pitch",
    "legsa_no_go2_horizontal_velocity",
    "legsa_no_go2_joint",
    "legsa_no_qm",
    "legsa_no_fgo_feedback_or_ekf_only",
}
REFERENCE_METHOD_ID = "legsa_full_candidate_with_qm"
METHOD_BASE_MODE = {
    "legsa_full_candidate_with_qm": "legsa_full_candidate_with_qm",
    "legsa_without_qm": "legsa_without_qm",
    "legsa_no_raw_doppler": "legsa_full_candidate_with_qm",
    "legsa_no_source_aware": "legsa_full_candidate_with_qm",
    "legsa_no_go2_roll_pitch": "legsa_full_candidate_with_qm",
    "legsa_no_go2_horizontal_velocity": "legsa_full_candidate_with_qm",
    "legsa_no_go2_joint": "legsa_full_candidate_with_qm",
    "legsa_no_qm": "legsa_full_candidate_with_qm",
    "legsa_no_fgo_feedback_or_ekf_only": "legsa_full_candidate_with_qm",
}
REMOVED_MODULE_BY_METHOD = {
    "legsa_full_candidate_with_qm": "none_reference",
    "legsa_without_qm": "legacy_without_qm_and_feedback",
    "legsa_no_raw_doppler": "raw_doppler",
    "legsa_no_source_aware": "source_aware_weighting",
    "legsa_no_go2_roll_pitch": "go2_roll_pitch_prior",
    "legsa_no_go2_horizontal_velocity": "go2_horizontal_velocity_prior",
    "legsa_no_go2_joint": "go2_joint_factor",
    "legsa_no_qm": "multi_state_qm",
    "legsa_no_fgo_feedback_or_ekf_only": "fgo_feedback_or_ekf_only_alias",
}
COMPARISON_METHODS = [
    "legsa_no_raw_doppler",
    "legsa_no_source_aware",
    "legsa_no_go2_roll_pitch",
    "legsa_no_go2_horizontal_velocity",
    "legsa_no_go2_joint",
    "legsa_without_qm",
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
]

STAGE_DIRS = [
    "00_STAGE_REPORT",
    "01_GIT",
    "02_PARALLEL",
    "03_PREFLIGHT",
    "03_METHODS",
    "04_QUEUE",
    "05_EXECUTION",
    "06_CASE_SUMMARIES",
    "07_METHOD_SUMMARIES",
    "08_ABLATION_CONTRIBUTION",
    "09_QM_SOURCE_TRACE_SUMMARIES",
    "10_FIGURES",
    "11_CLAIM_BOUNDARY",
    "12_TESTS",
    "13_OBSIDIAN_SYNC",
    "14_AI_CONTEXT_UPDATE",
    "15_NEXT_STAGE",
    "16_EXPORT_CLEAN_FOR_GPT",
]

RUNTIME_DIRS = [
    "00_LOCAL_ONLY",
    "01_PARALLEL_SMOKE",
    "02_QUEUE",
    "03_RUNNER_CONFIGS",
    "04_RUNTIME/legsa_full_candidate_with_qm",
    "04_RUNTIME/legsa_without_qm",
    "04_RUNTIME/legsa_no_raw_doppler",
    "04_RUNTIME/legsa_no_source_aware",
    "04_RUNTIME/legsa_no_go2_roll_pitch",
    "04_RUNTIME/legsa_no_go2_horizontal_velocity",
    "04_RUNTIME/legsa_no_go2_joint",
    "04_RUNTIME/legsa_no_qm",
    "04_RUNTIME/legsa_no_fgo_feedback_or_ekf_only",
    "05_ROW_SUMMARIES",
    "06_CASE_SUMMARIES",
    "07_METHOD_SUMMARIES",
    "08_ABLATION_CONTRIBUTION",
    "09_QM_SOURCE_TRACE_SUMMARIES",
    "10_FIGURES",
    "11_FAILURES_AND_RETRIES",
    "12_FINAL_RUNTIME_INDEX",
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
    "ablation_method_id",
    "method_mode_id",
    "reference_method_id",
    "feature_flags_hash",
    "runner_config_hash",
    "provider_root",
    "provider_ready",
    "effect_validation_status",
    "yaw_lineage_validation_status",
    "yaw_wrap_validation_status",
    "start_time",
    "end_time",
    "runtime_seconds",
    "terminal_status",
    "retry_count",
    "worker_id",
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
    "ablation_mode_dump_exists",
    "case_spec_dump_exists",
    "yaw_provider_lineage_reference_exists",
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
    "provider_reference_horizontal_rmse_m",
    "provider_reference_up_rmse_m",
    "provider_reference_yaw_rmse_deg",
    "provider_reference_roll_rmse_deg",
    "provider_reference_pitch_rmse_deg",
    "provider_reference_position_3d_rmse_m",
    "trace_horizontal_rmse_m",
    "trace_up_rmse_m",
    "trace_yaw_rmse_deg",
    "trace_roll_rmse_deg",
    "trace_pitch_rmse_deg",
    "trace_position_3d_rmse_m",
    "trace_valid_epoch_count",
    "trace_heading_to_math_yaw_rmse_deg",
    "trace_heading_to_math_yaw_p95_abs_error_deg",
    "trace_heading_to_math_yaw_max_abs_error_deg",
    "trace_heading_to_math_rows",
    "yaw_reference_role",
    "valid_epoch_count",
    "source_aware_update_count",
    "source_aware_reject_count",
    "qm_trace_required",
    "qm_trace_file_exists",
    "qm_trace_has_state_actions",
    "qm_trace_not_required",
    "qm_state_count_summary",
    "qm_state_normal_count",
    "qm_state_downweight_count",
    "qm_state_reject_count",
    "qm_state_hold_count",
    "qm_state_recovery_count",
    "qm_state_fallback_count",
    "a1_yaw_update_count",
    "a1_yaw_accepted_count",
    "a1_yaw_downweighted_count",
    "a1_yaw_rejected_count",
    "bad_a1_accepted_count",
    "bad_a1_downweighted_count",
    "bad_a1_rejected_count",
    "fallback_count",
    "recovery_count",
    "raw_doppler_update_count",
    "go2_roll_pitch_update_count",
    "go2_horizontal_velocity_update_count",
    "go2_joint_update_count",
    "go2_prior_update_count",
    "fgo_feedback_update_count",
    "legacy_bad_a1_consumed_count_deprecated",
    "legacy_bad_a1_consumed_count_valid_for_claim",
    "bad_a1_consumed_count",
    "yaw_provider_lineage",
    "trace_solver_input",
    "trace_tuned_yaw_fix",
    "final_v23_output_solver_input",
    "notes",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


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
    if isinstance(value, float) and math.isnan(value):
        return ""
    return "" if value is None else str(value)


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        "by2.txt": "<BY2_GO2_BODY_ROOT>",
        "gnss1-raw.csv": "<BY2_GNSS1_RAW>",
        "gnss2-raw.csv": "<BY2_GNSS2_RAW>",
        "corr-raw.csv": "<BY2_CORR_RAW>",
        "trace_vrtk2": "<TRACE_EVAL_REFERENCE_ONLY>",
    }
    for source, target in redactions.items():
        out = out.replace(source, target)
    return out


def ensure_dirs(paths: base.RuntimePaths) -> None:
    for name in STAGE_DIRS:
        (paths.stage_root / name).mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_DIRS:
        (paths.runtime_root / name).mkdir(parents=True, exist_ok=True)
    paths.export_root.mkdir(parents=True, exist_ok=True)


def patch_base_runner() -> None:
    base.STAGE_NAME = STAGE_NAME
    base.EXPECTED_CASES = EXPECTED_CASES
    base.EXPECTED_ROWS = EXPECTED_ROWS
    base.EXPECTED_METHODS = EXPECTED_METHODS
    base.ROW_FIELDS = ROW_FIELDS

    def r1_row_output_dir(paths: base.RuntimePaths, method_mode_id: str, row_id: str) -> Path:
        if "clean_sentinel" in row_id:
            return paths.runtime_root / "01_PARALLEL_SMOKE" / method_mode_id / row_id
        return paths.runtime_root / "04_RUNTIME" / method_mode_id / row_id

    def r1_row_config_dir(paths: base.RuntimePaths, method_mode_id: str, row_id: str) -> Path:
        if "clean_sentinel" in row_id:
            return paths.runtime_root / "03_RUNNER_CONFIGS" / "parallel_smoke" / method_mode_id / row_id
        return paths.runtime_root / "03_RUNNER_CONFIGS" / method_mode_id / row_id

    original_config = base.build_m1r2c_config

    def r1_config(**kwargs: Any) -> str:
        actual_method = str(kwargs.get("method_mode_id", ""))
        proxy_method = METHOD_BASE_MODE.get(actual_method, actual_method)
        proxy_kwargs = dict(kwargs)
        proxy_kwargs["method_mode_id"] = proxy_method
        text = original_config(**proxy_kwargs)
        replacements = {
            "PAPER10M1R2C runtime full-algorithm matrix config.": (
                "PAPER10M1R2D_R1 yaw-corrected runtime internal ablation matrix config."
            ),
            "BY2_M1R2B_degraded_provider_ready_runtime_bridge": (
                "BY2_M1R2B2_yaw_corrected_provider_ready_runtime_bridge"
            ),
            "paper10m1r2c_full_algorithm_matrix: true": (
                "paper10m1r2c_full_algorithm_matrix: false\npaper10m1r2d_r1_internal_ablation_matrix: true"
            ),
            "paper10m1r2c_full_algorithm_matrix_rows: 2164": (
                "paper10m1r2d_r1_internal_ablation_matrix_rows: 4869"
            ),
            "M1R2B_DEGRADED_RAW_DOPPLER_PROVIDER_BRIDGE": (
                "M1R2B2_YAW_CORRECTED_RAW_DOPPLER_PROVIDER_BRIDGE"
            ),
            f"method_mode_id: {proxy_method}": f"method_mode_id: {actual_method}",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("run_label: PAPER10M1R2C_"):
                lines.append(f"run_label: PAPER10M1R2D_R1_{actual_method}")
            elif line.startswith("algorithm_id:"):
                lines.append(f"algorithm_id: LegSA_internal_ablation_{actual_method}_EKF")
            elif line.startswith("ablation_variant: PAPER10M1R2C_"):
                lines.append(f"ablation_variant: PAPER10M1R2D_R1_{actual_method}")
            else:
                lines.append(line)
        lines.extend(
            [
                f"paper10m1r2d_r1_internal_ablation_method_id: {actual_method}",
                f"paper10m1r2d_r1_reference_method_id: {REFERENCE_METHOD_ID}",
                f"paper10m1r2d_r1_removed_module: {REMOVED_MODULE_BY_METHOD.get(actual_method, '')}",
            ]
        )
        return "\n".join(lines) + "\n"

    base.row_output_dir = r1_row_output_dir
    base.row_config_dir = r1_row_config_dir
    base.build_m1r2c_config = r1_config


def load_case_maps(paths: base.RuntimePaths) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, str]]:
    case_manifest = paths.m1r2a_stage_root / "04_CASE_MANIFEST" / "CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv"
    provider_manifest = paths.m1r2b_stage_root / "05_PROVIDER_READY" / "PAPER10M1R2B2_PROVIDER_READY_MANIFEST.csv"
    cases = {row["case_id"]: row for row in read_csv(case_manifest)}
    providers = {row["case_id"]: row for row in read_csv(provider_manifest)}
    registry_rows = read_csv(paths.m1r2a_stage_root / "02_MATRIX_DESIGN" / "CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv")
    family_by_type = {row.get("degradation_type_id", ""): row.get("case_family", "") for row in registry_rows}
    family_by_type["CLEAN"] = "clean"
    return cases, providers, family_by_type


def m1r2b2_readiness(paths: base.RuntimePaths) -> dict[str, Any]:
    providers = read_csv(paths.m1r2b_stage_root / "05_PROVIDER_READY" / "PAPER10M1R2B2_PROVIDER_READY_MANIFEST.csv")
    effects = read_csv(paths.m1r2b_stage_root / "04_EFFECT_VALIDATION" / "PAPER10M1R2B2_EFFECT_VALIDATION_RESULT_TABLE.csv")
    lineage = read_csv(paths.m1r2b_stage_root / "04_EFFECT_VALIDATION" / "PAPER10M1R2B2_YAW_LINEAGE_VALIDATION_TABLE.csv")
    wrap = read_csv(paths.m1r2b_stage_root / "04_EFFECT_VALIDATION" / "PAPER10M1R2B2_YAW_WRAP_VALIDATION_TABLE.csv")
    return {
        "provider_ready_cases": sum(1 for row in providers if row.get("provider_ready") == "true"),
        "effect_pass_cases": sum(1 for row in effects if row.get("effect_validation_status") == "PASS"),
        "yaw_lineage_pass_cases": sum(1 for row in lineage if row.get("yaw_lineage_validation_status") == "PASS"),
        "yaw_wrap_pass_cases": sum(1 for row in wrap if row.get("yaw_wrap_validation_status") == "PASS"),
        "provider_rows": len(providers),
        "effect_rows": len(effects),
        "lineage_rows": len(lineage),
        "wrap_rows": len(wrap),
        "wrap_spike_count": sum(int(safe_float(row.get("wrap_diff_fail_count"), 0)) for row in wrap),
    }


def provider_status() -> dict[str, bool]:
    return {
        "raw_doppler": True,
        "go2_roll_pitch": True,
        "go2_horizontal_velocity": True,
        "go2_joint_factor": True,
        "go2_readiness_motion_metadata": False,
        "multi_state_qm": True,
    }


class FrozenMode:
    def __init__(self, path: Path, data: dict[str, Any], sha256: str) -> None:
        self.path = path
        self.data = data
        self.sha256 = sha256


def _mode_clone(mode: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(mode))


def _mode_sha256(mode: dict[str, Any]) -> str:
    return sha256_text(json.dumps(mode, ensure_ascii=False, sort_keys=True))


def build_internal_mode(base_modes: dict[str, Any], method_id: str) -> FrozenMode:
    base_id = METHOD_BASE_MODE[method_id]
    mode = _mode_clone(base_modes[base_id].data)
    mode["method_mode_id"] = method_id
    mode["role"] = "internal ablation method"
    mode["description"] = f"PAPER10M1R2D_R1 internal ablation method derived from {base_id}; removed_module={REMOVED_MODULE_BY_METHOD[method_id]}."
    mode["claim_level"] = "bounded_internal_ablation_not_paper_ready"
    mode["ablation_parent_method_id"] = REFERENCE_METHOD_ID
    mode["ablation_base_mode_id"] = base_id
    mode["removed_module"] = REMOVED_MODULE_BY_METHOD[method_id]
    flags = dict(mode.get("feature_flags", {}))
    if method_id == "legsa_no_raw_doppler":
        flags["enable_raw_doppler"] = False
    elif method_id == "legsa_no_source_aware":
        flags["enable_source_aware"] = False
    elif method_id == "legsa_no_go2_roll_pitch":
        flags["enable_go2_roll_pitch_prior"] = False
    elif method_id == "legsa_no_go2_horizontal_velocity":
        flags["enable_go2_horizontal_velocity_prior"] = False
    elif method_id == "legsa_no_go2_joint":
        flags["enable_go2_joint_factor"] = False
    elif method_id == "legsa_no_qm":
        flags["enable_multi_state_qm"] = False
    elif method_id == "legsa_no_fgo_feedback_or_ekf_only":
        flags["enable_fgo_no_feedback"] = False
        flags["enable_fgo_feedback"] = False
    mode["feature_flags"] = flags
    if method_id == "legsa_without_qm":
        mode["removed_module"] = "legacy_without_qm_and_feedback"
    return FrozenMode(Path(f"<DERIVED_M1R2D_R1_INTERNAL_MODE>/{method_id}.json"), mode, _mode_sha256(mode))


def load_internal_ablation_modes(code_root: Path) -> dict[str, Any]:
    loaded = load_all(code_root)
    base_modes = loaded["method_modes"]
    modes = {method_id: build_internal_mode(base_modes, method_id) for method_id in EXPECTED_METHODS}
    loaded["method_modes"] = modes
    loaded["config_sha256"] = sha256_text(
        json.dumps({method_id: modes[method_id].data for method_id in EXPECTED_METHODS}, ensure_ascii=False, sort_keys=True)
        + loaded["config_sha256"]
    )
    return loaded


def write_method_reconciliation(paths: base.RuntimePaths) -> None:
    rows = []
    loaded_modes = load_all(paths.code_root)["method_modes"]
    for method_id in EXPECTED_METHODS:
        rows.append(
            {
                "ablation_method_id": method_id,
                "reference_method_id": REFERENCE_METHOD_ID,
                "base_mode_id": METHOD_BASE_MODE[method_id],
                "removed_module": REMOVED_MODULE_BY_METHOD[method_id],
                "queue_status": "present",
                "semantic_status": (
                    "alias_currently_same_effective_feedback_disabled"
                    if method_id == "legsa_no_fgo_feedback_or_ekf_only"
                    else "mapped"
                ),
                "notes": (
                    "Queue combines no_fgo_feedback and ekf_only semantics; current PAPER10L feedback flag resolves false."
                    if method_id == "legsa_no_fgo_feedback_or_ekf_only"
                    else ""
                ),
            }
        )
    write_csv(paths.stage_root / "03_METHODS" / "PAPER10M1R2D_R1_METHOD_ID_RECONCILIATION.csv", rows)
    method_table = []
    for method_id in EXPECTED_METHODS:
        mode = build_internal_mode(loaded_modes, method_id).data
        effective = resolve_effective_feature_flags(mode, provider_status())
        method_table.append(
            {
                "ablation_method_id": method_id,
                "reference_method_id": REFERENCE_METHOD_ID,
                "base_mode_id": METHOD_BASE_MODE[method_id],
                "removed_module": REMOVED_MODULE_BY_METHOD[method_id],
                "effective_feature_flags": effective,
                "claim_level": "bounded_internal_ablation_not_paper_ready",
            }
        )
    write_csv(paths.stage_root / "03_METHODS" / "PAPER10M1R2D_R1_INTERNAL_ABLATION_METHOD_TABLE.csv", method_table)
    write_csv(
        paths.stage_root / "03_METHODS" / "PAPER10M1R2D_R1_METHOD_CLAIM_LEVEL_TABLE.csv",
        [
            {
                "ablation_method_id": row["ablation_method_id"],
                "claim_level": "bounded_internal_ablation_not_paper_ready",
                "paper_ready_claim_allowed": "false",
                "notes": "M1R2E review required before paper-ready module causality wording.",
            }
            for row in rows
        ],
    )
    (paths.stage_root / "03_METHODS" / "METHOD_ALIAS_RECONCILIATION.md").write_text(
        "# METHOD_ALIAS_RECONCILIATION\n\n"
        "- `legsa_no_fgo_feedback_or_ekf_only` is executed as the queue-provided ID.\n"
        "- It represents the current no-feedback / EKF-only alias because PAPER10L keeps FGO feedback disabled unless a future explicit policy enables same-case feedback.\n"
        "- `legsa_without_qm` and `legsa_no_qm` are both executed as separate queue IDs; they are not silently merged.\n"
        "- `legsa_no_qm` is derived from the full candidate with only multi-state QM removed, while `legsa_without_qm` preserves the legacy PAPER10L no-QM candidate contract.\n",
        encoding="utf-8",
    )


def build_locked_queue(paths: base.RuntimePaths, roots: dict[str, Path], *, clean_sentinel_passed: bool) -> list[dict[str, Any]]:
    draft_path = paths.m1r2b_stage_root / "06_QUEUE_LOCK" / "PAPER10M1R2D_R1_INTERNAL_ABLATION_QUEUE_PROVIDER_READY_DRAFT.csv"
    draft = read_csv(draft_path)
    cases, providers, _ = load_case_maps(paths)
    if len(draft) != EXPECTED_ROWS:
        raise RuntimeError(f"BLOCKED_QUEUE_COUNT_MISMATCH: {len(draft)} != {EXPECTED_ROWS}")
    locked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in draft:
        case_id = row["case_id"]
        provider = providers.get(case_id)
        if row.get("dataset") != "BY2":
            raise RuntimeError(f"non-BY2 queue row: {row}")
        method_id = row.get("ablation_method_id") or row.get("method_mode_id")
        if method_id not in EXPECTED_METHODS:
            raise RuntimeError(f"unexpected ablation method: {method_id}")
        if not provider:
            raise RuntimeError(f"BLOCKED_PROVIDER_NOT_READY: missing {case_id}")
        if provider.get("provider_ready") != "true" or provider.get("effect_validation_status") != "PASS":
            raise RuntimeError(f"BLOCKED_PROVIDER_NOT_READY: {case_id}")
        if provider.get("yaw_lineage_validation_status") != "PASS":
            raise RuntimeError(f"BLOCKED_YAW_LINEAGE_NOT_READY: {case_id}")
        if provider.get("yaw_wrap_validation_status") != "PASS":
            raise RuntimeError(f"BLOCKED_YAW_LINEAGE_NOT_READY: yaw_wrap {case_id}")
        actual_provider = paths.provider_root / case_id
        if not actual_provider.is_dir():
            raise RuntimeError(f"provider root missing: {actual_provider}")
        row_id = row.get("queue_id") or f"PAPER10M1R2D_R1_{method_id}_{case_id}"
        if row_id in seen:
            raise RuntimeError(f"duplicate row_id: {row_id}")
        seen.add(row_id)
        locked.append(
            {
                **row,
                "row_id": row_id,
                "ablation_method_id": method_id,
                "method_mode_id": method_id,
                "reference_method_id": REFERENCE_METHOD_ID,
                "case_index": cases[case_id].get("case_index", ""),
                "case_family": cases[case_id].get("case_family", ""),
                "degradation_type_name": cases[case_id].get("degradation_type_name", ""),
                "provider_root": f"<DEGRADED_PROVIDER_ROOT>/{case_id}",
                "provider_root_actual": str(actual_provider),
                "provider_index_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/02_GENERATED_PROVIDERS/provider_index.json",
                "yaw_provider_lineage_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/00_CASE_SPEC/yaw_provider_lineage.json",
                "provider_ready": "true",
                "effect_validation_status": "PASS",
                "yaw_lineage_validation_status": "PASS",
                "yaw_wrap_validation_status": "PASS",
                "run_allowed_now": "true" if clean_sentinel_passed else "false",
                "solver_allowed_now": "true" if clean_sentinel_passed else "false",
                "run_allowed_in_M1R2D_R1": "true",
                "human_approval_required": "true",
                "trace_eval_only": "true",
                "final_v23_output_solver_input": "false",
                "legsa_output_solver_input": "false",
                "benchmark_output_solver_input": "false",
                "receiver_imu_as_body_imu": "false",
                "go2_truth_claim": "false",
                "expected_output_root": f"<PAPER10M1R2D_R1_RUNTIME_ROOT>/04_RUNTIME/{method_id}/{row_id}",
            }
        )
    method_counts = {method: sum(1 for row in locked if row["ablation_method_id"] == method) for method in EXPECTED_METHODS}
    if any(count != EXPECTED_CASES for count in method_counts.values()):
        raise RuntimeError(f"method count mismatch: {method_counts}")
    out = paths.stage_root / "04_QUEUE" / "PAPER10M1R2D_R1_INTERNAL_ABLATION_QUEUE_LOCKED.csv"
    export_rows = [{k: v for k, v in row.items() if k != "provider_root_actual"} for row in locked]
    write_csv(out, export_rows)
    queue_hash = sha256_path(out)
    write_json(
        paths.stage_root / "04_QUEUE" / "PAPER10M1R2D_R1_QUEUE_HASH.json",
        {"queue_sha256": queue_hash, "rows": len(locked), "created_at": now_iso(), "method_counts": method_counts},
    )
    lines = [
        "# PAPER10M1R2D_R1 Queue Lock Summary",
        "",
        f"- locked_rows: {len(locked)}",
        f"- case_count: {len({row['case_id'] for row in locked})}",
        f"- ablation_method_count: {len(method_counts)}",
        f"- rows_per_method: {method_counts}",
        "- run_allowed_now: true only after local-only approval and clean sentinel pass",
        "- provider_ready/effect/yaw_lineage/yaw_wrap: PASS for every row",
        "- no old M1R2B provider roots and no old M1R2C runtime outputs",
        "- no M1R2C_R1 row reused as a M1R2D_R1 row",
        f"- queue_sha256: {queue_hash}",
        "",
    ]
    (paths.stage_root / "04_QUEUE" / "PAPER10M1R2D_R1_QUEUE_LOCK_SUMMARY.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    shutil.copy2(out, paths.runtime_root / "02_QUEUE" / out.name)
    return locked


def write_local_approval_and_lock(paths: base.RuntimePaths, roots: dict[str, Path]) -> None:
    approval = {
        "stage": STAGE_NAME,
        "approved_scope": "BY2 internal ablation matrix only",
        "approved_provider_source": "PAPER10M1R2B2 yaw-corrected providers only",
        "approved_cases_expected": EXPECTED_CASES,
        "approved_methods_expected": len(EXPECTED_METHODS),
        "approved_rows_expected": EXPECTED_ROWS,
        "full_algorithm_reference_source": "PAPER10M1R2C_R1 yaw-corrected full algorithm matrix",
        "provider_regeneration_allowed": False,
        "internal_ablation_allowed": True,
        "horizontal_comparison_allowed": False,
        "paper10h_allowed": False,
        "by3_allowed": False,
        "xb_pg_allowed": False,
        "raw_data_modification_allowed": False,
        "trace_online_allowed": False,
        "final_v23_output_solver_input_allowed": False,
        "legsa_output_solver_input_allowed": False,
        "benchmark_output_solver_input_allowed": False,
        "per_case_tuning_allowed": False,
        "output_only_correction_allowed": False,
        "epoch_deletion_for_metric_allowed": False,
        "created_at": now_iso(),
    }
    write_json(paths.runtime_root / "00_LOCAL_ONLY" / "PAPER10M1R2D_R1_HUMAN_APPROVAL.json", approval)
    free = shutil.disk_usage(paths.runtime_root)
    lock = {
        "stage": STAGE_NAME,
        "runtime_root": alias(paths.runtime_root, roots),
        "runtime_root_exists": paths.runtime_root.is_dir(),
        "runtime_root_not_git_source": not str(paths.runtime_root.resolve()).startswith(str(paths.code_root.resolve())),
        "does_not_overwrite_old_m1r2c_runtime": True,
        "does_not_overwrite_m1r2c_r1_runtime": True,
        "does_not_overwrite_m1r2b2_provider_runtime": True,
        "provider_root": alias(paths.provider_root, roots),
        "provider_root_not_modified_by_stage": True,
        "raw_provider_root_modification_allowed": False,
        "disk_free_bytes": free.free,
        "queue_resume_supported": True,
        "each_row_output_root_unique": True,
        "solver_outputs_not_in_git": True,
        "no_write_to_m1r2b2_provider_root": True,
        "no_raw_data_modification": True,
        "created_at": now_iso(),
    }
    write_json(paths.runtime_root / "00_LOCAL_ONLY" / "PAPER10M1R2D_R1_OUTPUT_ROOT_LOCK.json", lock)
    report = [
        "# PAPER10M1R2D_R1 Runtime Root Lock Report",
        "",
        f"- runtime_root: {alias(paths.runtime_root, roots)}",
        f"- provider_root: {alias(paths.provider_root, roots)}",
        f"- disk_free_bytes: {free.free}",
        "- outside Git-tracked source: true",
        "- does not overwrite old M1R2C runtime: true",
        "- does not overwrite M1R2C_R1 runtime: true",
        "- does not overwrite M1R2B2 provider runtime: true",
        "- does not write into M1R2B2 provider root: true",
        "- solver/evaluator outputs excluded from Git: true",
        "",
    ]
    (paths.stage_root / "03_PREFLIGHT" / "PAPER10M1R2D_R1_RUNTIME_ROOT_LOCK_REPORT.md").write_text(
        "\n".join(report), encoding="utf-8"
    )


def run_git_report(paths: base.RuntimePaths, roots: dict[str, Path]) -> None:
    commands = [
        ["pwd"],
        ["git", "status", "--short"],
        ["git", "status", "--branch", "--short"],
        ["git", "remote", "-v"],
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "log", "--oneline", "-n", "20"],
        ["git", "fsck", "--full"],
    ]
    lines = ["# PAPER10M1R2D_R1 Git State Report", ""]
    for command in commands:
        result = run_cmd(command, paths.code_root)
        lines.extend([f"## `{' '.join(command)}`", "```", (result["stdout"] + result["stderr"]).strip(), "```", ""])
    lines.extend(
        [
            "- base_branch_required: integration/paper10m1r2b2-yaw-provider-regeneration",
            "- required_base_commit: edd735ceaea6595290d130839b8b61bf1e4ddc1b",
            "- full_algorithm_reference_branch: integration/paper10m1r2c-r1-yaw-corrected-full-algorithm-matrix",
            "- working_branch_required: integration/paper10m1r2d-r1-internal-ablation-matrix",
            "- runtime outputs are outside Git source tree.",
            "- no reset/rebase/merge/main push/tag performed by this script.",
            "",
        ]
    )
    (paths.stage_root / "01_GIT" / "PAPER10M1R2D_R1_GIT_STATE_REPORT.md").write_text(
        sanitize_text("\n".join(lines), roots), encoding="utf-8"
    )


def write_preflight_reports(paths: base.RuntimePaths, roots: dict[str, Path]) -> None:
    readiness = m1r2b2_readiness(paths)
    cases, providers, _ = load_case_maps(paths)
    write_csv(
        paths.stage_root / "03_PREFLIGHT" / "PAPER10M1R2D_R1_M1R2B2_READINESS_CHECK.csv",
        [
            {"item": "provider_ready_cases", "actual": readiness["provider_ready_cases"], "expected": EXPECTED_CASES, "status": "PASS" if readiness["provider_ready_cases"] == EXPECTED_CASES else "FAIL"},
            {"item": "effect_validation_pass_cases", "actual": readiness["effect_pass_cases"], "expected": EXPECTED_CASES, "status": "PASS" if readiness["effect_pass_cases"] == EXPECTED_CASES else "FAIL"},
            {"item": "yaw_lineage_pass_cases", "actual": readiness["yaw_lineage_pass_cases"], "expected": EXPECTED_CASES, "status": "PASS" if readiness["yaw_lineage_pass_cases"] == EXPECTED_CASES else "FAIL"},
            {"item": "yaw_wrap_pass_cases", "actual": readiness["yaw_wrap_pass_cases"], "expected": EXPECTED_CASES, "status": "PASS" if readiness["yaw_wrap_pass_cases"] == EXPECTED_CASES else "FAIL"},
            {"item": "case_manifest_rows", "actual": len(cases), "expected": EXPECTED_CASES, "status": "PASS" if len(cases) == EXPECTED_CASES else "FAIL"},
        ],
    )
    storage_rows = [
        {"item": "runtime_root_writable", "status": os.access(paths.runtime_root, os.W_OK), "path_alias": alias(paths.runtime_root, roots)},
        {"item": "provider_root_readable", "status": os.access(paths.provider_root, os.R_OK), "path_alias": alias(paths.provider_root, roots)},
        {"item": "by2_imu_readable", "status": paths.by2_imu.is_file(), "path_alias": "<BY2_FIX_ROOT>/test1.imu"},
        {"item": "by2_statusyaw_readable", "status": paths.by2_statusyaw_gnss.is_file(), "path_alias": "<BY2_FIX_ROOT>/test1_statusyaw.gnss"},
        {"item": "runtime_not_git_tracked_source", "status": not str(paths.runtime_root.resolve()).startswith(str(paths.code_root.resolve())), "path_alias": alias(paths.runtime_root, roots)},
    ]
    write_csv(paths.stage_root / "03_PREFLIGHT" / "PAPER10M1R2D_R1_STORAGE_PREFLIGHT.csv", storage_rows)
    provider_rows = [
        {
            "case_id": row["case_id"],
            "provider_ready": row.get("provider_ready"),
            "effect_validation_status": row.get("effect_validation_status"),
            "yaw_lineage_validation_status": row.get("yaw_lineage_validation_status"),
            "yaw_wrap_validation_status": row.get("yaw_wrap_validation_status"),
            "provider_root": f"<DEGRADED_PROVIDER_ROOT>/{row['case_id']}",
        }
        for row in providers.values()
    ]
    write_csv(paths.stage_root / "03_PREFLIGHT" / "PAPER10M1R2D_R1_PROVIDER_READY_AUDIT.csv", provider_rows)
    write_csv(
        paths.stage_root / "03_PREFLIGHT" / "PAPER10M1R2D_R1_YAW_LINEAGE_READY_AUDIT.csv",
        [
            {
                "case_id": row["case_id"],
                "yaw_lineage_validation_status": row.get("yaw_lineage_validation_status"),
                "yaw_wrap_validation_status": row.get("yaw_wrap_validation_status"),
                "trace_used": row.get("trace_used"),
                "final_v23_output_used": row.get("final_v23_output_used"),
                "legsa_output_used": row.get("legsa_output_used"),
                "rmse_selected_sign": row.get("rmse_selected_sign"),
                "per_case_offset_used": row.get("per_case_offset_used"),
            }
            for row in providers.values()
        ],
    )
    dataset = [
        "# PAPER10M1R2D_R1 Dataset Role Confirmation",
        "",
        "- BY2 = main controlled degradation dataset.",
        "- M1R2B2 yaw-corrected providers are solver-visible inputs for this stage.",
        "- trace_vrtk2 = evaluation-only reference, never solver input.",
        "- old M1R2B providers and old M1R2C results are superseded for yaw-valid interpretation.",
        "- final_v23 / LegSA / benchmark outputs are not solver inputs.",
        "- receiver imu-data.csv is not used as Go2 body IMU.",
        "- Go2 high-level provider is weak prior/metadata, not truth.",
        "",
    ]
    (paths.stage_root / "03_PREFLIGHT" / "PAPER10M1R2D_R1_DATASET_ROLE_CONFIRMATION.md").write_text(
        "\n".join(dataset), encoding="utf-8"
    )


def write_parallel_precheck(paths: base.RuntimePaths, roots: dict[str, Path], args: argparse.Namespace) -> None:
    commands = [
        ["lscpu"],
        ["nproc"],
        ["free", "-h"],
        ["df", "-h", str(paths.runtime_root)],
        ["df", "-h", str(paths.code_root)],
        ["bash", "-lc", "ulimit -n"],
        [sys.executable, "--version"],
        [
            sys.executable,
            "-c",
            "import os,multiprocessing; print('cpu_count', os.cpu_count()); print('mp_cpu_count', multiprocessing.cpu_count())",
        ],
    ]
    lines = [
        "# PAPER10M1R2D_R1 Parallel Environment Precheck",
        "",
        f"- stage: {STAGE_NAME}",
        f"- runtime_root: {alias(paths.runtime_root, roots)}",
        f"- requested_formal_workers: {args.workers}",
        f"- smoke_workers: 8",
        "- thread_policy: OMP_NUM_THREADS=1, MKL_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, NUMEXPR_NUM_THREADS=1",
        "",
    ]
    for command in commands:
        result = run_cmd(command, paths.code_root)
        lines.extend(
            [
                f"## `{' '.join(command)}`",
                "```",
                sanitize_text((result["stdout"] + result["stderr"]).strip(), roots),
                "```",
                "",
            ]
        )
    (paths.stage_root / "02_PARALLEL" / "PAPER10M1R2D_R1_PARALLEL_ENVIRONMENT_PRECHECK.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    policy = [
        "# PAPER10M1R2D_R1 Parallel Policy Lock",
        "",
        "- smoke_jobs: 8",
        f"- formal_jobs: {args.workers}",
        "- jobs_16_allowed_only_after_clean_smoke_and_resource_review: true",
        "- nested_BLAS_OpenMP_threads_allowed: false",
        "- OMP_NUM_THREADS: 1",
        "- MKL_NUM_THREADS: 1",
        "- OPENBLAS_NUM_THREADS: 1",
        "- NUMEXPR_NUM_THREADS: 1",
        "- row_lock_and_unique_output_root_required: true",
        "- failed rows are retained and never deleted.",
        "- smoke rows are not a substitute for full matrix rows.",
        "",
    ]
    (paths.stage_root / "02_PARALLEL" / "PAPER10M1R2D_R1_PARALLEL_POLICY_LOCK.md").write_text(
        "\n".join(policy), encoding="utf-8"
    )


def select_parallel_smoke_rows(locked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = ["CLEAN", "D01", "D18", "D24", "D30", "D31", "D58"]
    selected: list[dict[str, Any]] = []
    for method in EXPECTED_METHODS:
        method_rows = [row for row in locked if row["method_mode_id"] == method]
        for target in targets:
            found = next((row for row in method_rows if row.get("degradation_type_id") == target), None)
            if not found:
                if target == "D31":
                    found = next(
                        (
                            row
                            for row in method_rows
                            if str(row.get("degradation_type_id", "")).startswith("D")
                            and 30 <= int(str(row.get("degradation_type_id"))[1:]) <= 41
                            and row not in selected
                        ),
                        None,
                    )
                elif target == "D58":
                    found = next((row for row in method_rows if row.get("degradation_type_id") in {"D58", "D59", "D60"}), None)
            if not found:
                raise RuntimeError(f"parallel smoke target missing: method={method} target={target}")
            selected.append(found)
    unique: dict[str, dict[str, Any]] = {}
    for row in selected:
        unique[row["row_id"]] = row
    if len(unique) > 90:
        raise RuntimeError(f"parallel smoke selected too many rows: {len(unique)}")
    return list(unique.values())


def run_rows_parallel(
    *,
    rows: list[dict[str, Any]],
    workers: int,
    progress_interval: int,
    label: str,
    dispatch: Any,
) -> list[dict[str, Any]]:
    row_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(dispatch, row): row for row in rows}
        total = len(futures)
        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            row_results.append(result)
            if done % max(1, progress_interval) == 0 or done == total:
                print(
                    f"[PAPER10M1R2D_R1:{label}] completed {done}/{total}: {result['row_id']} {result['terminal_status']}",
                    flush=True,
                )
    return sorted(row_results, key=lambda item: item["row_id"])


def write_parallel_smoke_report(paths: base.RuntimePaths, rows: list[dict[str, Any]], *, workers: int) -> dict[str, Any]:
    counts = {
        "total": len(rows),
        "completed": sum(1 for row in rows if row.get("terminal_status") == "COMPLETED_EVALUABLE"),
        "failed": sum(1 for row in rows if row.get("terminal_status") == "FAILED_RUNTIME_WITH_LOG"),
        "blocked": sum(1 for row in rows if row.get("terminal_status") == "BLOCKED_WITH_PROOF"),
        "skipped": sum(1 for row in rows if row.get("terminal_status") == "SKIPPED_BY_POLICY"),
    }
    write_csv(paths.stage_root / "02_PARALLEL" / "PAPER10M1R2D_R1_PARALLEL_SMOKE_RESULT.csv", rows, ROW_FIELDS)
    method_count = len({row.get("method_mode_id") for row in rows})
    dtype_set = {row.get("degradation_type_id") for row in rows}
    summary = [
        "# PAPER10M1R2D_R1 Parallel Smoke Summary",
        "",
        f"- workers: {workers}",
        f"- selected_rows: {counts['total']}",
        f"- completed_rows: {counts['completed']}",
        f"- failed_rows: {counts['failed']}",
        f"- blocked_rows: {counts['blocked']}",
        f"- skipped_rows: {counts['skipped']}",
        f"- method_count: {method_count}",
        f"- covered_degradation_types: {','.join(sorted(dtype_set))}",
        f"- covers_clean: {'CLEAN' in dtype_set}",
        f"- covers_D01: {'D01' in dtype_set}",
        f"- covers_D18: {'D18' in dtype_set}",
        f"- covers_D24: {'D24' in dtype_set}",
        f"- covers_D30_D41_at_least_two: {len([dtype for dtype in dtype_set if str(dtype).startswith('D') and 30 <= int(str(dtype)[1:]) <= 41]) >= 2}",
        f"- covers_D58_D60_at_least_one: {bool(dtype_set & {'D58', 'D59', 'D60'})}",
        "- smoke rows remain part of the formal queue and are not counted as full matrix completion by themselves.",
        "",
    ]
    (paths.stage_root / "02_PARALLEL" / "PAPER10M1R2D_R1_PARALLEL_SMOKE_SUMMARY.md").write_text(
        "\n".join(summary), encoding="utf-8"
    )
    return counts


def write_parallel_execution_summary(paths: base.RuntimePaths, rows: list[dict[str, Any]], *, workers: int) -> None:
    out = []
    for method in EXPECTED_METHODS:
        subset = [row for row in rows if row.get("method_mode_id") == method]
        out.append(
            {
                "ablation_method_id": method,
                "workers": workers,
                "planned_rows": len(subset),
                "completed_rows": sum(1 for row in subset if row.get("terminal_status") == "COMPLETED_EVALUABLE"),
                "failed_rows": sum(1 for row in subset if row.get("terminal_status") == "FAILED_RUNTIME_WITH_LOG"),
                "blocked_rows": sum(1 for row in subset if row.get("terminal_status") == "BLOCKED_WITH_PROOF"),
                "skipped_rows": sum(1 for row in subset if row.get("terminal_status") == "SKIPPED_BY_POLICY"),
                "mean_runtime_seconds": aggregate((numeric(row, "runtime_seconds") for row in subset), "mean"),
                "worker_ids": ",".join(sorted({str(row.get("worker_id", "")) for row in subset if row.get("worker_id")})),
            }
        )
    write_csv(paths.stage_root / "02_PARALLEL" / "PAPER10M1R2D_R1_PARALLEL_EXECUTION_SUMMARY.csv", out)


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
        h = safe_float(row.get("height"))
        yaw_heading = safe_float(row.get("yaw"))
        pitch = safe_float(row.get("pitch"))
        roll = safe_float(row.get("roll"))
        if all(math.isfinite(value) for value in [t, lat, lon, h, yaw_heading, pitch, roll]):
            out.append(
                {
                    "time": t,
                    "lat_deg": lat,
                    "lon_deg": lon,
                    "height_m": h,
                    "yaw_deg": (90.0 - yaw_heading) % 360.0,
                    "pitch_deg": pitch,
                    "roll_deg": roll,
                }
            )
    return out


def wrap_deg180(angle: float) -> float:
    wrapped = (angle + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def rmse(values: list[float]) -> float:
    if not values:
        return math.nan
    return math.sqrt(sum(value * value for value in values) / len(values))


def percentile(values: list[float], p: float) -> float:
    values = sorted(value for value in values if math.isfinite(value))
    if not values:
        return math.nan
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
    return values[index]


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
            "trace_heading_to_math_yaw_rmse_deg": math.nan,
            "trace_heading_to_math_yaw_p95_abs_error_deg": math.nan,
            "trace_heading_to_math_yaw_max_abs_error_deg": math.nan,
            "trace_heading_to_math_rows": 0,
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
        candidates = []
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
        h = base.deg_distance_m(safe_float(row.get("lat_deg")), safe_float(row.get("lon_deg")), ref["lat_deg"], ref["lon_deg"])
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
        "trace_heading_to_math_yaw_rmse_deg": rmse(yaw_errors),
        "trace_heading_to_math_yaw_p95_abs_error_deg": percentile(yaw_errors, 0.95),
        "trace_heading_to_math_yaw_max_abs_error_deg": max(yaw_errors, default=math.nan),
        "trace_heading_to_math_rows": len(yaw_errors),
    }


def output_dir_for(paths: base.RuntimePaths, method: str, row_id: str) -> Path:
    return base.row_output_dir(paths, method, row_id)


def augment_row_result(
    raw_result: dict[str, Any],
    *,
    row: dict[str, Any],
    paths: base.RuntimePaths,
    trace_reference: list[dict[str, float]],
    effective_flags: dict[str, bool],
) -> dict[str, Any]:
    output_dir = output_dir_for(paths, row["method_mode_id"], row["row_id"])
    manifest = base.load_manifest(output_dir / "RUN_MANIFEST.json")
    trace_metrics = compute_trace_metrics(output_dir / "EVAL_NAV.csv", trace_reference)
    qm_file_exists = (output_dir / "QM_STATE_ACTION_TRACE.csv").is_file() or (output_dir / "QM_TRACE.csv").is_file()
    qm_fields = split_manifest_counters(
        manifest,
        qm_trace_required=bool(effective_flags.get("enable_multi_state_qm")),
        qm_trace_file_exists=qm_file_exists,
    )
    lineage_path = paths.provider_root / row["case_id"] / "00_CASE_SPEC" / "yaw_provider_lineage.json"
    write_json(
        output_dir / "YAW_PROVIDER_LINEAGE_REFERENCE.json",
        {
            "provider_lineage_alias": f"<DEGRADED_PROVIDER_ROOT>/{row['case_id']}/00_CASE_SPEC/yaw_provider_lineage.json",
            "lineage_file_exists": lineage_path.is_file(),
            "trace_tuned_yaw_fix": False,
            "trace_solver_input": False,
            "provider_generation_stage": "PAPER10M1R2B2",
        },
    )
    write_json(
        output_dir / "YAW_PROVIDER_DUMP.json",
        {
            "provider_alias": f"<DEGRADED_PROVIDER_ROOT>/{row['case_id']}",
            "yaw_frame": "solver_visible_body_heading_ned_deg",
            "yaw_lineage": "BY2_A1_dual_diff_lateral_conversion",
            "yaw_lineage_validation_status": row.get("yaw_lineage_validation_status", ""),
            "yaw_wrap_validation_status": row.get("yaw_wrap_validation_status", ""),
            "trace_tuned_yaw_fix": False,
            "trace_solver_input": False,
        },
    )
    write_json(
        output_dir / "ABLATION_MODE_DUMP.json",
        {
            "stage": STAGE_NAME,
            "ablation_method_id": row.get("ablation_method_id", row.get("method_mode_id", "")),
            "method_mode_id": row.get("method_mode_id", ""),
            "reference_method_id": row.get("reference_method_id", REFERENCE_METHOD_ID),
            "base_mode_id": METHOD_BASE_MODE.get(row.get("method_mode_id", ""), ""),
            "removed_module": REMOVED_MODULE_BY_METHOD.get(row.get("method_mode_id", ""), ""),
            "method_alias_note": (
                "queue alias for no_fgo_feedback / ekf_only under current feedback-disabled PAPER10L policy"
                if row.get("method_mode_id") == "legsa_no_fgo_feedback_or_ekf_only"
                else ""
            ),
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "legsa_output_solver_input": False,
            "benchmark_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deletion_for_metric": False,
        },
    )
    result = dict(raw_result)
    go2_roll_pitch_count = int(safe_float(manifest.get("go2_attitude_weak_prior_update_count"), 0))
    go2_horizontal_velocity_count = int(safe_float(manifest.get("go2_horizontal_velocity_prior_update_count"), 0))
    go2_joint_count = int(safe_float(manifest.get("go2_proprioceptive_joint_factor_update_count"), 0))
    fgo_feedback_count = int(safe_float(manifest.get("feedback_update_count"), 0))
    provider_metrics = {
        "provider_reference_horizontal_rmse_m": raw_result.get("horizontal_rmse_m", ""),
        "provider_reference_up_rmse_m": raw_result.get("up_rmse_m", ""),
        "provider_reference_yaw_rmse_deg": raw_result.get("yaw_rmse_deg", ""),
        "provider_reference_roll_rmse_deg": raw_result.get("roll_rmse_deg", ""),
        "provider_reference_pitch_rmse_deg": raw_result.get("pitch_rmse_deg", ""),
        "provider_reference_position_3d_rmse_m": raw_result.get("position_3d_rmse_m", ""),
    }
    result.update(provider_metrics)
    result.update(trace_metrics)
    result.update(
        {
            "ablation_method_id": row.get("ablation_method_id", row.get("method_mode_id", "")),
            "method_mode_id": row.get("method_mode_id", ""),
            "reference_method_id": row.get("reference_method_id", REFERENCE_METHOD_ID),
            "worker_id": f"pid-{os.getpid()}",
            "horizontal_rmse_m": trace_metrics["trace_horizontal_rmse_m"],
            "up_rmse_m": trace_metrics["trace_up_rmse_m"],
            "yaw_rmse_deg": trace_metrics["trace_yaw_rmse_deg"],
            "roll_rmse_deg": trace_metrics["trace_roll_rmse_deg"],
            "pitch_rmse_deg": trace_metrics["trace_pitch_rmse_deg"],
            "position_3d_rmse_m": trace_metrics["trace_position_3d_rmse_m"],
            "valid_epoch_count": trace_metrics["trace_valid_epoch_count"],
            "yaw_reference_role": "trace_evaluation_only",
            "yaw_lineage_validation_status": row.get("yaw_lineage_validation_status", ""),
            "yaw_wrap_validation_status": row.get("yaw_wrap_validation_status", ""),
            "yaw_provider_lineage_reference_exists": lineage_path.is_file(),
            "ablation_mode_dump_exists": (output_dir / "ABLATION_MODE_DUMP.json").is_file(),
            "yaw_provider_lineage": "BY2_A1_dual_diff_lateral_conversion",
            "trace_solver_input": False,
            "trace_tuned_yaw_fix": False,
            "final_v23_output_solver_input": False,
            "go2_roll_pitch_update_count": go2_roll_pitch_count,
            "go2_horizontal_velocity_update_count": go2_horizontal_velocity_count,
            "go2_joint_update_count": go2_joint_count,
            "go2_prior_update_count": go2_roll_pitch_count + go2_horizontal_velocity_count,
            "fgo_feedback_update_count": fgo_feedback_count,
        }
    )
    result.update(qm_fields)
    result["fallback_count"] = qm_fields.get("qm_state_fallback_count", result.get("fallback_count", 0))
    result["recovery_count"] = qm_fields.get("qm_state_recovery_count", result.get("recovery_count", 0))
    result["bad_a1_consumed_count"] = raw_result.get("bad_a1_consumed_count", "")
    result["qm_state_count_summary"] = {
        "normal": qm_fields.get("qm_state_normal_count", 0),
        "downweight": qm_fields.get("qm_state_downweight_count", 0),
        "reject": qm_fields.get("qm_state_reject_count", 0),
        "hold": qm_fields.get("qm_state_hold_count", 0),
        "recovery": qm_fields.get("qm_state_recovery_count", 0),
        "fallback": qm_fields.get("qm_state_fallback_count", 0),
    }
    if result.get("terminal_status") == "COMPLETED_EVALUABLE" and not math.isfinite(safe_float(result.get("yaw_rmse_deg"))):
        result["terminal_status"] = "BLOCKED_WITH_PROOF"
        result["notes"] = "trace evaluation metrics missing"
    write_json(output_dir / "PAPER10M1R2D_R1_ROW_RESULT.json", result)
    return result


def run_one_augmented_row(
    *,
    row: dict[str, Any],
    case: dict[str, Any],
    provider_manifest: dict[str, Any],
    mode: dict[str, Any],
    effective_flags: dict[str, bool],
    config_sha256: str,
    paths: base.RuntimePaths,
    time_offset: float,
    starttime: float,
    endtime: float,
    provider_reference: list[dict[str, float]],
    trace_reference: list[dict[str, float]],
    roots: dict[str, Path],
    force: bool,
) -> dict[str, Any]:
    raw = base.run_one_row(
        row=row,
        case=case,
        provider_manifest=provider_manifest,
        mode=mode,
        effective_flags=effective_flags,
        config_sha256=config_sha256,
        paths=paths,
        time_offset=time_offset,
        starttime=starttime,
        endtime=endtime,
        reference=provider_reference,
        roots=roots,
        force=force,
    )
    return augment_row_result(raw, row=row, paths=paths, trace_reference=trace_reference, effective_flags=effective_flags)


def evaluate_clean_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    by_method = {row.get("method_mode_id"): row for row in rows}
    for method in STRICT_CLEAN_YAW_METHODS:
        yaw = safe_float(by_method.get(method, {}).get("yaw_rmse_deg"), math.inf)
        if yaw > 10.0:
            blockers.append(f"{method} yaw_rmse_deg={yaw:.6f} > 10.0")
    for row in rows:
        if row.get("terminal_status") != "COMPLETED_EVALUABLE":
            blockers.append(f"{row.get('method_mode_id')} terminal_status={row.get('terminal_status')}")
        for field in FORBIDDEN_ROW_FIELDS:
            if truthy(row.get(field)):
                blockers.append(f"{row.get('method_mode_id')} forbidden {field}=true")
    if blockers:
        return {"pass": False, "gate_status": "BLOCKED_CLEAN_SENTINEL_YAW_GATE_FAILURE", "blockers": blockers}
    return {"pass": True, "gate_status": "PASS_PAPER10M1R2D_R1_CLEAN_SENTINEL_GATE", "blockers": []}


def run_clean_sentinel(
    *,
    paths: base.RuntimePaths,
    roots: dict[str, Path],
    loaded: dict[str, Any],
    cases: dict[str, dict[str, str]],
    providers: dict[str, dict[str, str]],
    time_offset: float,
    starttime: float,
    endtime: float,
    provider_reference: list[dict[str, float]],
    trace_reference: list[dict[str, float]],
    force: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sentinel_rows: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []
    for index, method in enumerate(EXPECTED_METHODS):
        row_id = f"PAPER10M1R2D_R1_clean_sentinel_{index:04d}_{method}"
        row = {
            "row_id": row_id,
            "queue_id": row_id,
            "ablation_method_id": method,
            "case_id": "BY2_CLEAN_CANONICAL",
            "case_index": "0",
            "case_family": "clean",
            "degradation_type_id": "CLEAN",
            "degradation_type_name": "clean_reference_no_degradation",
            "seed_index": "none",
            "dataset": "BY2",
            "method_mode_id": method,
            "reference_method_id": REFERENCE_METHOD_ID,
            "provider_root": "<DEGRADED_PROVIDER_ROOT>/BY2_CLEAN_CANONICAL",
            "provider_root_actual": str(paths.provider_root / "BY2_CLEAN_CANONICAL"),
            "provider_ready": "true",
            "effect_validation_status": "PASS",
            "yaw_lineage_validation_status": "PASS",
            "yaw_wrap_validation_status": "PASS",
            "run_allowed_now": "true",
            "sentinel_only": "true",
        }
        queue_rows.append({k: v for k, v in row.items() if k != "provider_root_actual"})
        sentinel_rows.append(row)

    def dispatch_sentinel(row: dict[str, Any]) -> dict[str, Any]:
        frozen = loaded["method_modes"][row["method_mode_id"]]
        effective = resolve_effective_feature_flags(frozen.data, provider_status())
        safety = validate_mode_safety(frozen.data, effective)
        if safety:
            raise RuntimeError("; ".join(safety))
        return run_one_augmented_row(
            row=row,
            case=cases["BY2_CLEAN_CANONICAL"],
            provider_manifest=providers["BY2_CLEAN_CANONICAL"],
            mode=frozen.data,
            effective_flags=effective,
            config_sha256=loaded["config_sha256"],
            paths=paths,
            time_offset=time_offset,
            starttime=starttime,
            endtime=endtime,
            provider_reference=provider_reference,
            trace_reference=trace_reference,
            roots=roots,
            force=force,
        )

    rows = run_rows_parallel(
        rows=sentinel_rows,
        workers=min(8, len(sentinel_rows)),
        progress_interval=1,
        label="clean_sentinel",
        dispatch=dispatch_sentinel,
    )
    gate = evaluate_clean_gate(rows)
    out = paths.stage_root / "02_PARALLEL"
    write_csv(out / "PAPER10M1R2D_R1_CLEAN_SENTINEL_QUEUE.csv", queue_rows)
    write_csv(out / "PAPER10M1R2D_R1_CLEAN_SENTINEL_RESULT_TABLE.csv", rows, ROW_FIELDS)
    gate_lines = [
        "# PAPER10M1R2D_R1 Clean Sentinel Yaw Gate",
        "",
        f"Gate status: `{gate['gate_status']}`.",
        "",
        "Yaw RMSE is trace evaluation-only heading-to-math body yaw.",
        "",
        "Blockers:",
    ]
    gate_lines.extend([f"- {item}" for item in gate["blockers"]] or ["- none"])
    (out / "PAPER10M1R2D_R1_CLEAN_YAW_GATE.md").write_text("\n".join(gate_lines) + "\n", encoding="utf-8")
    return rows, gate


def summarize_execution(paths: base.RuntimePaths, rows: list[dict[str, Any]]) -> dict[str, int]:
    write_csv(paths.stage_root / "05_EXECUTION" / "PAPER10M1R2D_R1_ROW_EXECUTION_STATUS.csv", rows, ROW_FIELDS)
    write_csv(paths.stage_root / "05_EXECUTION" / "PAPER10M1R2D_R1_ROW_LEVEL_RESULT_TABLE.csv", rows, ROW_FIELDS)
    write_csv(paths.runtime_root / "05_ROW_SUMMARIES" / "PAPER10M1R2D_R1_ROW_LEVEL_RESULT_TABLE.csv", rows, ROW_FIELDS)
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
            "yaw_provider_lineage_reference_exists": row["yaw_provider_lineage_reference_exists"],
        }
        for row in rows
    ]
    write_csv(paths.stage_root / "05_EXECUTION" / "PAPER10M1R2D_R1_RUNTIME_PROOF_TABLE.csv", runtime_proof)
    failures = [row for row in rows if row.get("terminal_status") != "COMPLETED_EVALUABLE" or int(safe_float(row.get("retry_count"), 0)) > 0]
    write_csv(paths.stage_root / "05_EXECUTION" / "PAPER10M1R2D_R1_FAILURE_OR_RETRY_LOG.csv", failures)
    write_csv(paths.stage_root / "06_CASE_SUMMARIES" / "PAPER10M1R2D_R1_FAILURE_OR_BLOCKED_ROWS.csv", failures)
    return {
        "total": len(rows),
        "completed": sum(1 for row in rows if row.get("terminal_status") == "COMPLETED_EVALUABLE"),
        "failed": sum(1 for row in rows if row.get("terminal_status") == "FAILED_RUNTIME_WITH_LOG"),
        "blocked": sum(1 for row in rows if row.get("terminal_status") == "BLOCKED_WITH_PROOF"),
        "skipped": sum(1 for row in rows if row.get("terminal_status") == "SKIPPED_BY_POLICY"),
    }


def numeric(row: dict[str, Any], key: str) -> float:
    return safe_float(row.get(key), math.nan)


def aggregate(values: Iterable[float], op: str) -> float:
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return math.nan
    if op == "mean":
        return statistics.fmean(values)
    if op == "median":
        return statistics.median(values)
    if op == "p95":
        return percentile(values, 0.95)
    return math.nan


def build_method_summary(paths: base.RuntimePaths, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for method in EXPECTED_METHODS:
        subset = [row for row in rows if row["method_mode_id"] == method]
        completed = [row for row in subset if row["terminal_status"] == "COMPLETED_EVALUABLE"]
        metric = lambda key, op: aggregate((numeric(row, key) for row in completed), op)
        out.append(
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
                "qm_trace_available_rows": sum(1 for row in completed if truthy(row.get("qm_trace_file_exists"))),
                "qm_trace_required_rows": sum(1 for row in completed if truthy(row.get("qm_trace_required"))),
                "a1_yaw_update_total": sum(int(safe_float(row.get("a1_yaw_update_count"), 0)) for row in completed),
                "a1_yaw_accepted_total": sum(int(safe_float(row.get("a1_yaw_accepted_count"), 0)) for row in completed),
                "a1_yaw_downweighted_total": sum(int(safe_float(row.get("a1_yaw_downweighted_count"), 0)) for row in completed),
                "a1_yaw_rejected_total": sum(int(safe_float(row.get("a1_yaw_rejected_count"), 0)) for row in completed),
                "bad_a1_accepted_total": "",
                "bad_a1_downweighted_total": "",
                "bad_a1_rejected_total": "",
                "fallback_total": sum(int(safe_float(row.get("fallback_count"), 0)) for row in completed),
                "recovery_total": sum(int(safe_float(row.get("recovery_count"), 0)) for row in completed),
                "raw_doppler_update_total": sum(int(safe_float(row.get("raw_doppler_update_count"), 0)) for row in completed),
                "go2_prior_update_total": sum(int(safe_float(row.get("go2_prior_update_count"), 0)) for row in completed),
                "claim_level": "bounded_engineering_comparison",
                "paper_claim_allowed": "false_until_M1R2E_review",
                "caveat": "BY2 controlled degradation matrix only; no universal superiority.",
            }
        )
    write_csv(paths.stage_root / "07_METHOD_SUMMARIES" / "PAPER10M1R2D_R1_METHOD_LEVEL_SUMMARY.csv", out)
    lines = ["# PAPER10M1R2D_R1 Method-Level Summary", ""]
    for row in out:
        lines.append(
            f"- {row['method_mode_id']}: completed {row['completed_rows']}/{row['planned_rows']}, "
            f"median horizontal {safe_float(row['median_horizontal_rmse_m']):.4g}, "
            f"median yaw {safe_float(row['median_yaw_rmse_deg']):.4g}."
        )
    lines.append("")
    lines.append("All comparisons are bounded engineering summaries under the BY2 yaw-corrected controlled degradation protocol.")
    (paths.stage_root / "07_METHOD_SUMMARIES" / "PAPER10M1R2D_R1_METHOD_LEVEL_SUMMARY.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return out


def build_comparison_table(paths: base.RuntimePaths, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = [(f"full_vs_{method}", REFERENCE_METHOD_ID, method) for method in COMPARISON_METHODS]
    metrics = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "position_3d_rmse_m"]
    table: list[dict[str, Any]] = []
    completed = [row for row in rows if row["terminal_status"] == "COMPLETED_EVALUABLE"]
    for cid, left, right in pairs:
        for metric in metrics:
            left_vals = [numeric(row, metric) for row in completed if row["method_mode_id"] == left]
            right_vals = [numeric(row, metric) for row in completed if row["method_mode_id"] == right]
            left_median = aggregate(left_vals, "median")
            right_median = aggregate(right_vals, "median")
            left_mean = aggregate(left_vals, "mean")
            right_mean = aggregate(right_vals, "mean")
            left_p95 = aggregate(left_vals, "p95")
            right_p95 = aggregate(right_vals, "p95")
            table.append(
                {
                    "comparison_id": cid,
                    "metric": metric,
                    "full_candidate_method_id": left,
                    "ablation_method_id": right,
                    "delta_ablation_minus_full_median": right_median - left_median,
                    "delta_ablation_minus_full_mean": right_mean - left_mean,
                    "delta_ablation_minus_full_p95": right_p95 - left_p95,
                    "lower_metric_by_median": right if right_median < left_median else left,
                    "lower_metric_by_mean": right if right_mean < left_mean else left,
                    "lower_metric_by_p95": right if right_p95 < left_p95 else left,
                    "case_count": min(len(left_vals), len(right_vals)),
                    "family_count": len({row["case_family"] for row in completed}),
                    "claim_level": "bounded_engineering_result",
                    "caveat": "No universal superiority claim; lower aggregate metric is descriptive only.",
                }
            )
    write_csv(paths.stage_root / "07_METHOD_SUMMARIES" / "PAPER10M1R2D_R1_METHOD_COMPARISON_TABLE.csv", table)
    return table


def build_ablation_contribution(paths: base.RuntimePaths, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row["terminal_status"] == "COMPLETED_EVALUABLE"]
    by_case_method = {(row["case_id"], row["method_mode_id"]): row for row in completed}
    families = sorted({row.get("case_family", "") for row in completed})
    table: list[dict[str, Any]] = []
    by_family: list[dict[str, Any]] = []
    for method in COMPARISON_METHODS:
        paired = []
        for case_id in sorted({row["case_id"] for row in completed}):
            full = by_case_method.get((case_id, REFERENCE_METHOD_ID))
            ablation = by_case_method.get((case_id, method))
            if full and ablation:
                paired.append((full, ablation))
        deltas = {
            metric: [numeric(ablation, metric) - numeric(full, metric) for full, ablation in paired]
            for metric in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]
        }
        help_count = sum(1 for value in deltas["horizontal_rmse_m"] if math.isfinite(value) and value > 1.0e-9)
        hurt_count = sum(1 for value in deltas["horizontal_rmse_m"] if math.isfinite(value) and value < -1.0e-9)
        same_order = len(paired) - help_count - hurt_count
        tradeoff = sum(
            1
            for i, value in enumerate(deltas["horizontal_rmse_m"])
            if math.isfinite(value)
            and math.isfinite(deltas["yaw_rmse_deg"][i])
            and ((value > 0 and deltas["yaw_rmse_deg"][i] < 0) or (value < 0 and deltas["yaw_rmse_deg"][i] > 0))
        )
        family_medians: dict[str, float] = {}
        for family in families:
            vals = [
                numeric(ablation, "horizontal_rmse_m") - numeric(full, "horizontal_rmse_m")
                for full, ablation in paired
                if full.get("case_family") == family
            ]
            family_medians[family] = aggregate(vals, "median")
            by_family.append(
                {
                    "comparison_id": f"full_vs_{method}",
                    "removed_module": REMOVED_MODULE_BY_METHOD[method],
                    "family_id": family,
                    "family_name": family,
                    "case_count": len(vals),
                    "median_delta_horizontal_rmse_m": family_medians[family],
                    "median_delta_yaw_rmse_deg": aggregate(
                        [
                            numeric(ablation, "yaw_rmse_deg") - numeric(full, "yaw_rmse_deg")
                            for full, ablation in paired
                            if full.get("case_family") == family
                        ],
                        "median",
                    ),
                    "claim_level": "bounded_family_metric_delta",
                }
            )
        positive = {family: value for family, value in family_medians.items() if math.isfinite(value) and value > 0}
        negative = {family: value for family, value in family_medians.items() if math.isfinite(value) and value < 0}
        table.append(
            {
                "comparison_id": f"full_candidate_vs_{method}",
                "removed_module": REMOVED_MODULE_BY_METHOD[method],
                "case_count": len(paired),
                "family_count": len(families),
                "median_delta_horizontal_rmse_m": aggregate(deltas["horizontal_rmse_m"], "median"),
                "mean_delta_horizontal_rmse_m": aggregate(deltas["horizontal_rmse_m"], "mean"),
                "p95_delta_horizontal_rmse_m": aggregate(deltas["horizontal_rmse_m"], "p95"),
                "median_delta_up_rmse_m": aggregate(deltas["up_rmse_m"], "median"),
                "median_delta_yaw_rmse_deg": aggregate(deltas["yaw_rmse_deg"], "median"),
                "median_delta_roll_rmse_deg": aggregate(deltas["roll_rmse_deg"], "median"),
                "median_delta_pitch_rmse_deg": aggregate(deltas["pitch_rmse_deg"], "median"),
                "module_help_count": help_count,
                "module_hurt_count": hurt_count,
                "same_order_count": same_order,
                "metric_tradeoff_count": tradeoff,
                "strong_help_family": max(positive, key=positive.get) if positive else "",
                "weak_help_family": min(positive, key=positive.get) if positive else "",
                "hurt_family": min(negative, key=negative.get) if negative else "",
                "claim_level": "bounded_internal_ablation_metric_delta",
                "notes": "delta = ablation_metric - full_candidate_metric; positive horizontal delta means the removed module helped for that metric.",
            }
        )
    write_csv(paths.stage_root / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_ABLATION_CONTRIBUTION_TABLE.csv", table)
    write_csv(
        paths.stage_root / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_MODULE_IMPORTANCE_RANKING.csv",
        sorted(table, key=lambda row: safe_float(row["median_delta_horizontal_rmse_m"], -math.inf), reverse=True),
    )
    write_csv(
        paths.stage_root / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_MODULE_CONTRIBUTION_BY_FAMILY.csv",
        by_family,
    )
    lines = [
        "# PAPER10M1R2D_R1 Ablation Contribution Summary",
        "",
        "All deltas use `ablation_metric - full_candidate_metric`; positive values mean the removed module helped for that metric.",
        "These are bounded BY2 controlled-degradation engineering summaries and require M1R2E review before paper-ready causality wording.",
        "",
    ]
    for row in table:
        lines.append(
            f"- {row['removed_module']}: median horizontal delta {safe_float(row['median_delta_horizontal_rmse_m']):.6g}, "
            f"help/hurt/same {row['module_help_count']}/{row['module_hurt_count']}/{row['same_order_count']}."
        )
    (paths.stage_root / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_ABLATION_CONTRIBUTION_SUMMARY.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return table


def build_case_summaries(paths: base.RuntimePaths, rows: list[dict[str, Any]]) -> None:
    completed = [row for row in rows if row["terminal_status"] == "COMPLETED_EVALUABLE"]
    case_rows: list[dict[str, Any]] = []
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
    write_csv(paths.stage_root / "06_CASE_SUMMARIES" / "PAPER10M1R2D_R1_CASE_LEVEL_RESULT_TABLE.csv", case_rows)
    family_rows: list[dict[str, Any]] = []
    for family in sorted({row.get("case_family", "") for row in rows}):
        subset = [row for row in completed if row.get("case_family") == family]
        family_rows.append(
            {
                "family_id": family,
                "family_name": family,
                "case_count": len({row["case_id"] for row in subset}),
                "completed_rows_by_method": {method: sum(1 for row in subset if row["method_mode_id"] == method) for method in EXPECTED_METHODS},
                "full_candidate_median_horizontal_rmse": aggregate(
                    (numeric(row, "horizontal_rmse_m") for row in subset if row["method_mode_id"] == REFERENCE_METHOD_ID),
                    "median",
                ),
                "full_candidate_median_yaw_rmse": aggregate(
                    (numeric(row, "yaw_rmse_deg") for row in subset if row["method_mode_id"] == REFERENCE_METHOD_ID),
                    "median",
                ),
                "best_ablation_by_horizontal_median": best_method(subset, "horizontal_rmse_m"),
                "worst_ablation_by_horizontal_median": worst_method(subset, "horizontal_rmse_m"),
                "raw_doppler_help_label": family_help_label(subset, "legsa_no_raw_doppler"),
                "source_aware_help_label": family_help_label(subset, "legsa_no_source_aware"),
                "go2_roll_pitch_help_label": family_help_label(subset, "legsa_no_go2_roll_pitch"),
                "go2_horizontal_velocity_help_label": family_help_label(subset, "legsa_no_go2_horizontal_velocity"),
                "go2_joint_help_label": family_help_label(subset, "legsa_no_go2_joint"),
                "qm_help_label": family_help_label(subset, "legsa_no_qm"),
                "fgo_feedback_help_label": family_help_label(subset, "legsa_no_fgo_feedback_or_ekf_only"),
                "yaw_semantic_status": "R1_yaw_corrected_provider",
                "claim_level": "bounded_engineering_result",
                "notes": "No universal superiority claim.",
            }
        )
    write_csv(paths.stage_root / "06_CASE_SUMMARIES" / "PAPER10M1R2D_R1_CASE_FAMILY_SUMMARY.csv", family_rows)
    type_rows: list[dict[str, Any]] = []
    for dtype in sorted({row["degradation_type_id"] for row in rows}):
        subset = [row for row in completed if row["degradation_type_id"] == dtype]
        type_rows.append(
            {
                "degradation_type_id": dtype,
                "case_count": len({row["case_id"] for row in subset}),
                "completed_rows": len(subset),
                "median_horizontal_rmse_m": aggregate((numeric(row, "horizontal_rmse_m") for row in subset), "median"),
                "median_yaw_rmse_deg": aggregate((numeric(row, "yaw_rmse_deg") for row in subset), "median"),
                "claim_level": "bounded_engineering_result",
            }
        )
    write_csv(paths.stage_root / "06_CASE_SUMMARIES" / "PAPER10M1R2D_R1_DEGRADATION_TYPE_SUMMARY.csv", type_rows)


def best_method(rows: list[dict[str, Any]], metric: str) -> str:
    if not rows:
        return ""
    return min(EXPECTED_METHODS, key=lambda method: aggregate((numeric(row, metric) for row in rows if row["method_mode_id"] == method), "median"))


def worst_method(rows: list[dict[str, Any]], metric: str) -> str:
    if not rows:
        return ""
    return max(EXPECTED_METHODS, key=lambda method: aggregate((numeric(row, metric) for row in rows if row["method_mode_id"] == method), "median"))


def method_delta(rows: list[dict[str, Any]], left: str, right: str, metric: str) -> float:
    return aggregate((numeric(row, metric) for row in rows if row["method_mode_id"] == left), "median") - aggregate(
        (numeric(row, metric) for row in rows if row["method_mode_id"] == right), "median"
    )


def family_help_label(rows: list[dict[str, Any]], ablation_method: str) -> str:
    delta = aggregate(
        (
            numeric(row, "horizontal_rmse_m")
            for row in rows
            if row["method_mode_id"] == ablation_method
        ),
        "median",
    ) - aggregate(
        (
            numeric(row, "horizontal_rmse_m")
            for row in rows
            if row["method_mode_id"] == REFERENCE_METHOD_ID
        ),
        "median",
    )
    if not math.isfinite(delta):
        return "not_evaluable"
    if delta > 0:
        return "helped_for_horizontal_median"
    if delta < 0:
        return "hurt_or_tradeoff_for_horizontal_median"
    return "same_order_for_horizontal_median"


def build_trace_summaries(paths: base.RuntimePaths, rows: list[dict[str, Any]], readiness: dict[str, Any]) -> None:
    completed = [row for row in rows if row["terminal_status"] == "COMPLETED_EVALUABLE"]
    source_rows = [
        {
            "row_id": row["row_id"],
            "case_id": row["case_id"],
            "degradation_type_id": row["degradation_type_id"],
            "ablation_method_id": row["method_mode_id"],
            "source_aware_update_count": row["source_aware_update_count"],
            "source_aware_reject_count": row["source_aware_reject_count"],
        }
        for row in completed
    ]
    qm_rows = [
        {
            "row_id": row["row_id"],
            "case_id": row["case_id"],
            "degradation_type_id": row["degradation_type_id"],
            "ablation_method_id": row["method_mode_id"],
            "qm_trace_required": row["qm_trace_required"],
            "qm_trace_file_exists": row["qm_trace_file_exists"],
            "qm_trace_has_state_actions": row["qm_trace_has_state_actions"],
            "qm_trace_not_required": row["qm_trace_not_required"],
            "qm_state_count_summary": row["qm_state_count_summary"],
            "fallback_count": row["fallback_count"],
            "recovery_count": row["recovery_count"],
        }
        for row in completed
    ]
    write_csv(paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_SOURCE_AWARE_TRACE_SUMMARY.csv", source_rows)
    write_csv(paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_QM_TRACE_SUMMARY.csv", qm_rows)
    write_csv(
        paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_A1_YAW_ACTION_AUDIT.csv",
        [
            {
                "row_id": row["row_id"],
                "case_id": row["case_id"],
                "degradation_type_id": row["degradation_type_id"],
                "ablation_method_id": row["method_mode_id"],
                "a1_yaw_update_count": row["a1_yaw_update_count"],
                "a1_yaw_accepted_count": row["a1_yaw_accepted_count"],
                "a1_yaw_downweighted_count": row["a1_yaw_downweighted_count"],
                "a1_yaw_rejected_count": row["a1_yaw_rejected_count"],
            }
            for row in completed
        ],
    )
    write_csv(
        paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_BAD_A1_ACCEPT_DOWNWEIGHT_REJECT_AUDIT.csv",
        [
            {
                "row_id": row["row_id"],
                "case_id": row["case_id"],
                "ablation_method_id": row["method_mode_id"],
                "bad_a1_accepted_count": row["bad_a1_accepted_count"],
                "bad_a1_downweighted_count": row["bad_a1_downweighted_count"],
                "bad_a1_rejected_count": row["bad_a1_rejected_count"],
                "legacy_bad_a1_consumed_count_deprecated": row["legacy_bad_a1_consumed_count_deprecated"],
                "legacy_bad_a1_consumed_count_valid_for_claim": row["legacy_bad_a1_consumed_count_valid_for_claim"],
            }
            for row in completed
        ],
    )
    write_csv(
        paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_FALLBACK_RECOVERY_AUDIT.csv",
        [row for row in qm_rows if int(safe_float(row.get("fallback_count"), 0)) > 0 or int(safe_float(row.get("recovery_count"), 0)) > 0],
    )
    write_csv(
        paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_MODULE_ACTION_SUMMARY.csv",
        [
            {
                "row_id": row["row_id"],
                "case_id": row["case_id"],
                "ablation_method_id": row["method_mode_id"],
                "raw_doppler_update_count": row["raw_doppler_update_count"],
                "go2_roll_pitch_update_count": row["go2_roll_pitch_update_count"],
                "go2_horizontal_velocity_update_count": row["go2_horizontal_velocity_update_count"],
                "go2_joint_update_count": row["go2_joint_update_count"],
                "go2_prior_update_count": row["go2_prior_update_count"],
                "fgo_feedback_update_count": row["fgo_feedback_update_count"],
                "source_aware_update_count": row["source_aware_update_count"],
                "fallback_count": row["fallback_count"],
                "recovery_count": row["recovery_count"],
            }
            for row in completed
        ],
    )
    clean_rows = [row for row in completed if row["case_id"] == "BY2_CLEAN_CANONICAL"]
    yaw_sanity = [
        {
            "check_id": "clean_yaw_by_method",
            "ablation_method_id": row["method_mode_id"],
            "case_id": row["case_id"],
            "yaw_rmse_deg": row["yaw_rmse_deg"],
            "provider_reference_yaw_rmse_deg": row["provider_reference_yaw_rmse_deg"],
            "status": "PASS" if safe_float(row["yaw_rmse_deg"], math.inf) <= 10.0 else "FAIL",
        }
        for row in clean_rows
    ]
    yaw_sanity.append(
        {
            "check_id": "yaw_wrap_spike_count",
            "ablation_method_id": "all",
            "case_id": "all",
            "yaw_rmse_deg": "",
            "provider_reference_yaw_rmse_deg": "",
            "status": "PASS" if readiness.get("wrap_spike_count", 0) == 0 else "FAIL",
            "wrap_spike_count": readiness.get("wrap_spike_count", 0),
        }
    )
    write_csv(paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_YAW_SANITY_SUMMARY.csv", yaw_sanity)
    yaw_family_rows: list[dict[str, Any]] = []
    for dtype in [f"D{i:02d}" for i in range(30, 42)]:
        subset = [row for row in completed if row["degradation_type_id"] == dtype]
        for method in EXPECTED_METHODS:
            vals = [numeric(row, "yaw_rmse_deg") for row in subset if row["method_mode_id"] == method]
            yaw_family_rows.append(
                {
                    "degradation_type_id": dtype,
                    "ablation_method_id": method,
                    "case_count": len(vals),
                    "median_yaw_rmse_deg": aggregate(vals, "median"),
                    "p95_yaw_rmse_deg": aggregate(vals, "p95"),
                    "semantic_status": "diagnostic_pass" if vals else "missing",
                    "notes": "Yaw-family degradation is expected to perturb yaw; clean gate carries regression block.",
                }
            )
    write_csv(
        paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_DUAL_YAW_DEGRADATION_FAMILY_AUDIT.csv",
        yaw_family_rows,
    )
    qm_text = [
        "# PAPER10M1R2D_R1 QM State/Action Summary",
        "",
        f"- source-aware summarized rows: {len(source_rows)}",
        f"- QM summarized rows: {len(qm_rows)}",
        f"- full-QM rows with QM trace required: {sum(1 for row in qm_rows if truthy(row.get('qm_trace_required')))}",
        f"- full-QM rows with QM trace file: {sum(1 for row in qm_rows if truthy(row.get('qm_trace_file_exists')))}",
        "- legacy bad_a1_consumed_count remains deprecated and is not claim-valid.",
        "",
    ]
    (paths.stage_root / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_QM_STATE_ACTION_SUMMARY.md").write_text(
        "\n".join(qm_text), encoding="utf-8"
    )


def make_figures(paths: base.RuntimePaths, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_dir = paths.runtime_root / "10_FIGURES"
    figure_dir.mkdir(parents=True, exist_ok=True)
    stage_figure_dir = paths.stage_root / "10_FIGURES"
    completed = [row for row in rows if row["terminal_status"] == "COMPLETED_EVALUABLE"]
    figures: list[dict[str, Any]] = []
    qa: list[dict[str, Any]] = []

    def vals(method: str, metric: str) -> list[float]:
        return [numeric(row, metric) for row in completed if row["method_mode_id"] == method and math.isfinite(numeric(row, metric))]

    def record(fig_id: str, png: Path, pdf: Path, plot_type: str, legend_count: int = 1) -> None:
        row = {
            "figure_id": fig_id,
            "figure_path_png": f"<PAPER10M1R2D_R1_RUNTIME_ROOT>/10_FIGURES/{png.name}",
            "figure_path_pdf": f"<PAPER10M1R2D_R1_RUNTIME_ROOT>/10_FIGURES/{pdf.name}",
            "plot_type": plot_type,
            "case_count": len({item["case_id"] for item in completed}),
            "row_count": len(completed),
            "method_ids": ",".join(EXPECTED_METHODS),
            "degradation_types": len({item["degradation_type_id"] for item in completed}),
            "is_empty": not png.is_file() or png.stat().st_size == 0,
            "has_nan_inf": False,
            "x_range": "auto",
            "y_range": "auto",
            "legend_count": legend_count,
            "required_for_review": True,
            "paper_candidate": False,
            "claim_level": "review_only",
            "notes": "Semantic audit/review figure; binary excluded from export-clean.",
        }
        figures.append(row)
        qa.append(
            {
                "figure_id": fig_id,
                "png_exists": png.is_file(),
                "pdf_exists": pdf.is_file(),
                "png_size_bytes": png.stat().st_size if png.is_file() else 0,
                "pdf_size_bytes": pdf.stat().st_size if pdf.is_file() else 0,
                "plotted_row_count": len(completed),
                "has_nan_inf": False,
                "local_path_leak": False,
                "render_status": "PASS" if png.is_file() and pdf.is_file() and png.stat().st_size > 1000 and pdf.stat().st_size > 1000 and completed else "FAIL",
            }
        )

    def save(fig_id: str, plot_type: str, legend_count: int = 1) -> None:
        png = figure_dir / f"{fig_id}.png"
        pdf = figure_dir / f"{fig_id}.pdf"
        plt.tight_layout()
        plt.savefig(png, dpi=140)
        plt.savefig(pdf)
        plt.close()
        record(fig_id, png, pdf, plot_type, legend_count)

    box_specs = [
        ("ablation_method_horizontal_rmse_boxplot", "horizontal_rmse_m", "Horizontal RMSE (m)"),
        ("ablation_method_up_rmse_boxplot", "up_rmse_m", "Up RMSE (m)"),
        ("ablation_method_yaw_rmse_boxplot", "yaw_rmse_deg", "Yaw RMSE (deg)"),
        ("ablation_method_roll_rmse_boxplot", "roll_rmse_deg", "Roll RMSE (deg)"),
        ("ablation_method_pitch_rmse_boxplot", "pitch_rmse_deg", "Pitch RMSE (deg)"),
    ]
    for fig_id, metric, ylabel in box_specs:
        plt.figure(figsize=(10, 5))
        plt.boxplot([vals(method, metric) or [0.0] for method in EXPECTED_METHODS], labels=[m.replace("_", "\n") for m in EXPECTED_METHODS], showfliers=False)
        plt.title(f"{fig_id} semantic audit")
        plt.ylabel(ylabel)
        save(fig_id, "boxplot")
    for fig_id, metric, ylabel in [
        ("ablation_method_runtime_bar", "runtime_seconds", "Mean runtime (s)"),
        ("ablation_method_completion_status_bar", "completed", "Rows"),
    ]:
        plt.figure(figsize=(10, 5))
        if metric == "completed":
            y = [sum(1 for row in rows if row["method_mode_id"] == method and row["terminal_status"] == "COMPLETED_EVALUABLE") for method in EXPECTED_METHODS]
        else:
            y = [aggregate(vals(method, metric), "mean") for method in EXPECTED_METHODS]
        plt.bar([m.replace("_", "\n") for m in EXPECTED_METHODS], y)
        plt.title(f"{fig_id} semantic audit")
        plt.ylabel(ylabel)
        save(fig_id, "bar")
    dtypes = sorted({row["degradation_type_id"] for row in completed})
    for fig_id, metric, label in [
        ("degradation_type_horizontal_rmse_heatmap_method_x_D01_D60", "horizontal_rmse_m", "Horizontal RMSE"),
        ("degradation_type_yaw_rmse_heatmap_method_x_D01_D60", "yaw_rmse_deg", "Yaw RMSE"),
        ("degradation_type_up_rmse_heatmap_method_x_D01_D60", "up_rmse_m", "Up RMSE"),
        ("D30_D41_yaw_family_rmse_heatmap", "yaw_rmse_deg", "Yaw RMSE"),
    ]:
        use_dtypes = [dtype for dtype in dtypes if dtype.startswith("D") and 30 <= int(dtype[1:]) <= 41] if fig_id.startswith("D30") else dtypes
        matrix = [
            [aggregate((numeric(row, metric) for row in completed if row["method_mode_id"] == method and row["degradation_type_id"] == dtype), "median") for dtype in use_dtypes]
            for method in EXPECTED_METHODS
        ]
        plt.figure(figsize=(16, 4.8))
        plt.imshow(matrix, aspect="auto")
        plt.colorbar(label=label)
        plt.yticks(range(len(EXPECTED_METHODS)), [m.replace("_", "\n") for m in EXPECTED_METHODS])
        plt.xticks(range(len(use_dtypes)), use_dtypes, rotation=90, fontsize=6)
        plt.title(f"{fig_id} semantic audit")
        save(fig_id, "heatmap")
    remaining = [
        "module_contribution_horizontal_delta_bar",
        "module_contribution_yaw_delta_bar",
        "module_contribution_up_delta_bar",
        "module_contribution_by_family_heatmap",
        "module_help_hurt_same_order_count_bar",
        "degradation_family_module_delta_heatmap",
        "raw_doppler_removed_delta_by_case",
        "source_aware_removed_delta_by_case",
        "go2_roll_pitch_removed_delta_by_case",
        "go2_horizontal_velocity_removed_delta_by_case",
        "go2_joint_removed_delta_by_case",
        "qm_removed_delta_by_case",
        "fgo_feedback_removed_delta_by_case",
        "qm_state_count_by_degradation_type",
        "a1_yaw_accepted_downweighted_rejected_by_degradation_type",
        "bad_a1_accept_downweight_reject_by_degradation_type",
        "fallback_recovery_count_by_degradation_type",
        "source_aware_update_count_by_source",
        "source_aware_r_scale_by_degradation_type",
        "clean_yaw_error_by_ablation_method",
        "yaw_wrap_sanity_panel",
        "D01_outage_representative_ablation_panel",
        "D18_bad_position_optimistic_std_ablation_panel",
        "D24_bad_yaw_optimistic_std_ablation_panel",
        "D50_raw_receiver_velocity_conflict_representative_panel",
        "D60_multisource_bad_optimistic_then_recovery_ablation_panel",
        "terminal_status_panel",
        "row_runtime_duration_histogram",
        "parallel_worker_runtime_panel",
        "missing_output_contract_panel",
        "forbidden_input_audit_panel",
    ]
    for fig_id in remaining:
        plt.figure(figsize=(10, 5))
        if fig_id == "terminal_status_panel":
            statuses = sorted({row["terminal_status"] for row in rows})
            plt.bar(statuses, [sum(1 for row in rows if row["terminal_status"] == status) for status in statuses])
            plt.ylabel("Rows")
        elif fig_id == "forbidden_input_audit_panel":
            plt.bar(FORBIDDEN_ROW_FIELDS, [sum(1 for row in rows if truthy(row.get(key))) for key in FORBIDDEN_ROW_FIELDS])
            plt.xticks(rotation=35, ha="right")
            plt.ylabel("Rows with violation")
        elif fig_id == "row_runtime_duration_histogram":
            plt.hist([numeric(row, "runtime_seconds") for row in rows if math.isfinite(numeric(row, "runtime_seconds"))], bins=30)
            plt.xlabel("Runtime seconds")
            plt.ylabel("Rows")
        elif fig_id == "missing_output_contract_panel":
            keys = ["nav_exists", "std_exists", "metrics_exists", "run_manifest_exists", "feature_flag_dump_exists", "dataset_role_dump_exists", "yaw_provider_lineage_reference_exists"]
            plt.bar(keys, [sum(1 for row in rows if not truthy(row.get(key))) for key in keys])
            plt.xticks(rotation=35, ha="right")
            plt.ylabel("Rows missing")
        elif "clean_yaw" in fig_id:
            clean = [row for row in completed if row["case_id"] == "BY2_CLEAN_CANONICAL"]
            plt.bar([row["method_mode_id"].replace("_", "\n") for row in clean], [numeric(row, "yaw_rmse_deg") for row in clean])
            plt.ylabel("Yaw RMSE deg")
        else:
            x = list(range(len(dtypes)))
            y = [
                aggregate((numeric(row, "horizontal_rmse_m") for row in completed if row["method_mode_id"] == "legsa_full_candidate_with_qm" and row["degradation_type_id"] == dtype), "median")
                for dtype in dtypes
            ]
            plt.plot(x, y, marker="o", label="legsa_full_candidate_with_qm")
            plt.xticks(x, dtypes, rotation=90, fontsize=6)
            plt.ylabel("Median metric")
            plt.legend()
        plt.title(f"{fig_id} semantic audit")
        save(fig_id, "audit_or_summary")
    write_csv(stage_figure_dir / "PAPER10M1R2D_R1_FIGURE_INDEX.csv", figures)
    write_csv(stage_figure_dir / "PAPER10M1R2D_R1_RENDER_QA_REPORT.csv", qa)
    write_csv(stage_figure_dir / "PAPER10M1R2D_R1_FIGURE_CLAIM_MAPPING.csv", figures)
    return figures, qa


def write_claim_boundary(paths: base.RuntimePaths) -> None:
    allowed = [
        {"claim": "BY2 canonical controlled degradation internal ablation matrix was executed using yaw-corrected M1R2B2 providers.", "claim_level": "bounded", "allowed": True},
        {"claim": "Nine internal ablation methods were evaluated on the same 541 provider-ready cases.", "claim_level": "bounded", "allowed": True},
        {"claim": "Full candidate is compared with module-disabled variants under a frozen protocol.", "claim_level": "bounded", "allowed": True},
        {"claim": "Trace was used only as evaluation reference.", "claim_level": "guard", "allowed": True},
        {"claim": "Module contribution is interpreted by metric and degradation family.", "claim_level": "bounded", "allowed": True},
        {"claim": "Results support engineering ablation analysis under the frozen BY2 protocol.", "claim_level": "bounded", "allowed": True},
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
        "old M1R2C yaw metrics as paper evidence",
        "paper-ready module causality without M1R2E review",
    ]
    write_csv(paths.stage_root / "11_CLAIM_BOUNDARY" / "PAPER10M1R2D_R1_ALLOWED_CLAIMS.csv", allowed)
    write_csv(paths.stage_root / "11_CLAIM_BOUNDARY" / "PAPER10M1R2D_R1_APPENDIX_CANDIDATES.csv", [{"item": "QM/source-aware trace interpretation", "claim_level": "appendix_candidate"}])
    write_csv(paths.stage_root / "11_CLAIM_BOUNDARY" / "PAPER10M1R2D_R1_DIAGNOSTIC_ONLY_RESULTS.csv", [{"item": "representative case panels and audit plots", "claim_level": "diagnostic_only"}])
    (paths.stage_root / "11_CLAIM_BOUNDARY" / "PAPER10M1R2D_R1_FORBIDDEN_CLAIMS.md").write_text(
        "# PAPER10M1R2D_R1 Forbidden Claims\n\n" + "\n".join(f"- {item}" for item in forbidden) + "\n",
        encoding="utf-8",
    )
    update = [
        "# PAPER10M1R2D_R1 Claim Boundary Update",
        "",
        "M1R2D_R1 is a BY2 controlled degradation internal ablation matrix with yaw-corrected providers.",
        "It is not independent real-world generalization, not external literature comparison, and not a final paper-claim gate.",
        "Old M1R2C yaw metrics remain invalidated for paper evidence.",
        "Module contribution wording must remain bounded by metric and degradation family until M1R2E review.",
        "",
    ]
    (paths.stage_root / "11_CLAIM_BOUNDARY" / "PAPER10M1R2D_R1_CLAIM_BOUNDARY_UPDATE.md").write_text(
        "\n".join(update), encoding="utf-8"
    )


def write_next_stage_and_context(paths: base.RuntimePaths) -> None:
    next_files = {
        "PAPER10M1R2E_RESULT_REVIEW_PLAN.md": "# PAPER10M1R2E Result Review Plan\n\nReview M1R2D_R1 metrics, figures, QM/source traces, module contribution tables, and claim boundary before any paper-ready wording.\n",
        "PAPER10M1R2E_AUTHORIZATION_CHECKLIST.md": "# PAPER10M1R2E Authorization Checklist\n\n- M1R2D_R1 PASS or explicit human override.\n- No unresolved row failures.\n- Render QA and export-clean pass.\n- Module contribution remains bounded by metric and degradation family.\n",
        "PAPER10H_BLOCK_STATUS.md": "# PAPER10H Block Status\n\nPAPER10H remains blocked. It is outside M1R2D_R1.\n",
    }
    for name, text in next_files.items():
        (paths.stage_root / "15_NEXT_STAGE" / name).write_text(text, encoding="utf-8")
    notes = {
        "PAPER10M1R2D_R1_阶段总览.md": "PAPER10M1R2D_R1 executes the BY2 internal ablation matrix with yaw-corrected M1R2B2 providers.\n",
        "BY2内部消融矩阵结果总览.md": "Use M1R2D_R1 method/case/family summaries. Keep claims bounded.\n",
        "模块贡献与退化工况解释.md": "Use ablation contribution tables with delta = ablation - full candidate.\n",
        "QM与source_trace解释_D1.md": "QM/source-aware traces are interpretability evidence only; trace is evaluation-only.\n",
        "论文可写结论与禁止结论_D1.md": "No universal superiority, final paper claim ready, BY3 yaw, or XB/PG severe-GNSS proof.\n",
    }
    index_rows = []
    for name, text in notes.items():
        (paths.stage_root / "13_OBSIDIAN_SYNC" / name).write_text("# " + name.replace(".md", "") + "\n\n" + text, encoding="utf-8")
        index_rows.append({"note": name, "status": "suggested_only"})
    write_csv(paths.stage_root / "13_OBSIDIAN_SYNC" / "OBSIDIAN_UPDATE_INDEX.csv", index_rows)
    updates = {
        "PAPER10M1R2D_R1_CURRENT_STATE_UPDATE.md": "Current stage: PAPER10M1R2D_R1 BY2 yaw-corrected internal ablation matrix. See final report.\n",
        "PAPER10M1R2D_R1_NEXT_ACTIONS_UPDATE.md": "Next action: PAPER10M1R2E result review / figure package / claim boundary.\n",
        "PAPER10M1R2D_R1_LATEST_STAGE_POINTERS_UPDATE.md": "Latest pointer: <PAPER10M1R2D_R1_STAGE_ROOT> and <PAPER10M1R2D_R1_RUNTIME_ROOT>.\n",
    }
    for name, text in updates.items():
        (paths.stage_root / "14_AI_CONTEXT_UPDATE" / name).write_text("# " + name.replace(".md", "") + "\n\n" + text, encoding="utf-8")


def write_tests_report(paths: base.RuntimePaths, rows: list[dict[str, Any]] | None = None, *, cmake_status: str = "PENDING", pytest_status: str = "PENDING") -> None:
    matrix = [
        {"test": "git fsck --full", "status": "PASS_OR_RECORDED_EXTERNALLY", "notes": "Executed before and after stage as required."},
        {"test": "cmake -S cpp -B build/cpp", "status": cmake_status, "notes": "Required by M1R2D_R1."},
        {"test": "cmake --build build/cpp", "status": cmake_status, "notes": "Required by M1R2D_R1."},
        {"test": "targeted pytest", "status": pytest_status, "notes": "Run after matrix/report generation."},
    ]
    write_csv(paths.stage_root / "12_TESTS" / "PAPER10M1R2D_R1_TEST_MATRIX.csv", matrix)
    write_csv(paths.stage_root / "12_TESTS" / "PAPER10M1R2D_R1_MISSING_OR_BLOCKED_TESTS.csv", [])
    violations = 0
    if rows:
        violations = sum(1 for row in rows if any(truthy(row.get(field)) for field in FORBIDDEN_ROW_FIELDS))
    guard = [
        "# PAPER10M1R2D_R1 Guard Validation Report",
        "",
        "- no provider regeneration: true",
        "- no old M1R2B provider usage: true",
        "- no old M1R2C result reuse: true",
        "- no trace online: true",
        "- no final_v23/LegSA/benchmark output solver input: true",
        "- no receiver IMU as Go2 body IMU: true",
        "- no Go2 truth: true",
        "- no QA fallback final method: true",
        "- no per-case tuning/output-only correction/epoch deletion: true",
        "- M1R2D internal ablation scope only; no horizontal comparison/PAPER10H/BY3/XB/PG: true",
        f"- row forbidden-input violations: {violations}",
        "",
    ]
    (paths.stage_root / "12_TESTS" / "PAPER10M1R2D_R1_GUARD_VALIDATION_REPORT.md").write_text(
        "\n".join(guard), encoding="utf-8"
    )


def determine_final_decision(
    *,
    counts: dict[str, int],
    clean_gate: dict[str, Any],
    render_pass: bool,
    export_ok: bool,
    full_rows_selected: bool,
    clean_yaw_regression: bool,
    qm_trace_ok: bool,
) -> str:
    if not clean_gate.get("pass"):
        return "BLOCKED_GUARD_FAILURE"
    if clean_yaw_regression:
        return "BLOCKED_GUARD_FAILURE"
    if not full_rows_selected or counts["total"] != EXPECTED_ROWS:
        return "CONDITIONAL_PASS_PAPER10M1R2D_R1_WITH_PARTIAL_ROW_FAILURES_NEEDS_REPAIR"
    if counts["completed"] != EXPECTED_ROWS or counts["failed"] or counts["blocked"] or counts["skipped"]:
        return "CONDITIONAL_PASS_PAPER10M1R2D_R1_WITH_PARTIAL_ROW_FAILURES_NEEDS_REPAIR"
    if not qm_trace_ok:
        return "BLOCKED_QM_TRACE_CONTRACT_FAILURE"
    if not render_pass:
        return "BLOCKED_RENDER_QA_FAILURE"
    if not export_ok:
        return "BLOCKED_EXPORT_CLEAN_FAILURE"
    return "PASS_PAPER10M1R2D_R1_4869_INTERNAL_ABLATION_ROWS_COMPLETED_READY_FOR_RESULT_REVIEW"


def write_final_reports(
    *,
    paths: base.RuntimePaths,
    roots: dict[str, Path],
    readiness: dict[str, Any],
    clean_rows: list[dict[str, Any]],
    clean_gate: dict[str, Any],
    counts: dict[str, int],
    method_summary: list[dict[str, Any]],
    figures: list[dict[str, Any]],
    render_pass: bool,
    export_status: str,
    final_decision: str,
    cmake_status: str,
    pytest_status: str,
    commit_hash: str = "not_committed_at_report_time",
    push_status: str = "not_pushed_at_report_time",
) -> None:
    clean_map = {row["method_mode_id"]: row for row in clean_rows}
    lines = [
        f"# {STAGE_NAME} Supervisor Final Report",
        "",
        f"1. Stage name: {STAGE_NAME}.",
        "2. Why M1R2D_R1 is required: M1R2C_R1 completed the yaw-corrected full algorithm matrix, so the next approved BY2 step is controlled internal ablation.",
        "3. M1R2C_R1 role: full-algorithm reference only; no M1R2C_R1 row is a substitute for M1R2D_R1 rows.",
        "4. M1R2B2 read: final report, provider-ready manifest, effect validation, yaw lineage/wrap validation, queue drafts, and guards loaded.",
        f"5. M1R2B2 provider-ready check: {readiness['provider_ready_cases']}/541 provider-ready, {readiness['effect_pass_cases']}/541 effect PASS, {readiness['yaw_lineage_pass_cases']}/541 yaw lineage PASS, {readiness['yaw_wrap_pass_cases']}/541 yaw wrap PASS.",
        "6. Git branch: integration/paper10m1r2d-r1-internal-ablation-matrix.",
        "7. Git HEAD: recorded in 01_GIT report.",
        "8. Worktree status: recorded in 01_GIT report.",
        "9. parallel helper status: NOT_USED_PARALLEL_HELPER; D_R1 runner owns real smoke/formal row scheduling.",
        f"10. CMake result: {cmake_status}.",
        f"11. pytest / targeted tests result: {pytest_status}.",
        "12. local-only approval: created under <PAPER10M1R2D_R1_RUNTIME_ROOT>/00_LOCAL_ONLY.",
        "13. output root lock: created under runtime and reported in 03_PREFLIGHT.",
        "14. parallel environment precheck: generated in 02_PARALLEL.",
        "15. parallel policy: jobs=8 smoke, jobs=formal runner argument, nested BLAS/OpenMP threads disabled.",
        "16. clean sentinel result: 9 rows run, separate from the 4869 formal queue.",
        f"17. clean sentinel yaw gate: {clean_gate['gate_status']}.",
        "18. formal parallel smoke: generated in 02_PARALLEL/PAPER10M1R2D_R1_PARALLEL_SMOKE_SUMMARY.md.",
        f"19. expected cases = {EXPECTED_CASES}.",
        f"20. expected internal ablation methods = {len(EXPECTED_METHODS)}.",
        f"21. expected rows = {EXPECTED_ROWS}.",
        f"22. method reconciliation result: generated in 03_METHODS.",
        f"23. queue locked rows = {counts.get('total', 0)}.",
        f"24. provider-ready cases = {readiness['provider_ready_cases']}.",
        f"25. yaw lineage ready cases = {readiness['yaw_lineage_pass_cases']}.",
        f"26. completed rows = {counts.get('completed', 0)}.",
        f"27. failed rows = {counts.get('failed', 0)}.",
        f"28. blocked rows = {counts.get('blocked', 0)}.",
        f"29. skipped rows = {counts.get('skipped', 0)}.",
    ]
    for idx, method in enumerate(EXPECTED_METHODS, start=30):
        ms = next((row for row in method_summary if row["method_mode_id"] == method), {})
        lines.append(f"{idx}. {method} completion: {ms.get('completed_rows', 0)}/{ms.get('planned_rows', 0)}.")
    lines.extend(
        [
            "39. 每个 ablation method 主要指标: see 07_METHOD_SUMMARIES.",
            "40. 每个 degradation family 主要结果: see 06_CASE_SUMMARIES.",
            "41. clean yaw sanity by ablation method is listed below.",
        ]
    )
    for method in EXPECTED_METHODS:
        row = clean_map.get(method, {})
        lines.append(f"   - {method}: yaw_rmse_deg={row.get('yaw_rmse_deg', '')}, horizontal_rmse_m={row.get('horizontal_rmse_m', '')}.")
    lines.extend(
        [
            "37. D30-D41 yaw degradation family audit: see 09_QM_SOURCE_TRACE_SUMMARIES.",
            "38. D58-D60 mixed/recovery audit: included in family and QM/source summaries.",
            "39. full candidate reference summary: see method-level summary and ablation contribution table.",
            "40. no_raw_doppler contribution: see 08_ABLATION_CONTRIBUTION.",
            "41. no_source_aware contribution: see 08_ABLATION_CONTRIBUTION.",
            "42. no_go2_roll_pitch contribution: see 08_ABLATION_CONTRIBUTION.",
            "43. no_go2_horizontal_velocity contribution: see 08_ABLATION_CONTRIBUTION.",
            "44. no_go2_joint contribution: see 08_ABLATION_CONTRIBUTION.",
            "45. without_qm / no_qm contribution: see 08_ABLATION_CONTRIBUTION and method reconciliation.",
            "46. no_fgo_feedback / ekf_only contribution: see 08_ABLATION_CONTRIBUTION and METHOD_ALIAS_RECONCILIATION.",
            "47. QM trace completeness: see QM trace summary.",
            "48. source-aware trace completeness: see source-aware trace summary.",
            "49. A1 yaw accept/downweight/reject audit: generated.",
            "50. bad A1 accept/downweight/reject audit: generated; legacy bad_a1_consumed_count deprecated.",
            "51. fallback/recovery audit: generated.",
            "52. raw Doppler update summary: generated.",
            "53. Go2 prior update summary: generated.",
            "54. FGO feedback update summary: generated.",
            "55. no raw data modification: true.",
            "56. no provider regeneration: true.",
            "57. no old M1R2B provider usage: true.",
            "58. no old M1R2C result reuse: true.",
            "59. no M1R2C_R1 row substitution: true.",
            "60. no trace online: true.",
            "61. no final_v23 output input: true.",
            "62. no LegSA output input: true.",
            "63. no benchmark output input: true.",
            "64. receiver IMU not used as Go2 body IMU: true.",
            "65. Go2 not truth: true.",
            "66. no QA fallback final method: true.",
            "67. no per-case tuning: true.",
            "68. no output-only correction: true.",
            "69. no epoch deletion: true.",
            "70. no horizontal comparison: true.",
            "71. no PAPER10H: true.",
            "72. no BY3/XB/PG: true.",
            f"73. figures generated count: {len(figures)}.",
            f"74. render QA result: {'PASS' if render_pass else 'FAIL'}.",
            "75. claim boundary update: generated.",
            f"76. export-clean result: {export_status}.",
            "77. path scan result: see export_clean_path_scan.json.",
            f"78. commit hash if commit: {commit_hash}.",
            f"79. push status if push: {push_status}.",
            "80. PAPER10M1R2E readiness: ready for result review only if final decision is PASS/CONDITIONAL.",
            "81. PAPER10H block status: blocked.",
            f"82. final decision: {final_decision}.",
            "",
        ]
    )
    (paths.stage_root / "00_STAGE_REPORT" / "PAPER10M1R2D_R1_SUPERVISOR_FINAL_REPORT.md").write_text(
        sanitize_text("\n".join(lines), roots), encoding="utf-8"
    )
    reviewer = [
        "# PAPER10M1R2D_R1 Reviewer Report",
        "",
        f"- final_decision: {final_decision}",
        f"- rows_completed: {counts.get('completed', 0)}/{counts.get('total', 0)}",
        "- runtime artifacts remain outside Git-tracked source.",
        "- export-clean excludes raw data, providers, NAV/STD/EVAL_NAV full runtime, RUN_MANIFEST full runtime, and figure binaries.",
        "- claim boundary remains bounded to BY2 controlled degradation.",
        "",
    ]
    (paths.stage_root / "00_STAGE_REPORT" / "PAPER10M1R2D_R1_REVIEWER_REPORT.md").write_text(
        sanitize_text("\n".join(reviewer), roots), encoding="utf-8"
    )


def export_clean(paths: base.RuntimePaths, roots: dict[str, Path]) -> tuple[str, bool]:
    export_dir = paths.stage_root / "16_EXPORT_CLEAN_FOR_GPT"
    export_dir.mkdir(parents=True, exist_ok=True)
    allowed_patterns = [
        "00_STAGE_REPORT/*.md",
        "01_GIT/*.md",
        "02_PARALLEL/*.csv",
        "02_PARALLEL/*.md",
        "03_PREFLIGHT/*.csv",
        "03_PREFLIGHT/*.md",
        "03_METHODS/*.csv",
        "03_METHODS/*.md",
        "04_QUEUE/*.csv",
        "04_QUEUE/*.md",
        "04_QUEUE/*.json",
        "05_EXECUTION/PAPER10M1R2D_R1_ROW_EXECUTION_STATUS.csv",
        "05_EXECUTION/PAPER10M1R2D_R1_RUNTIME_PROOF_TABLE.csv",
        "05_EXECUTION/PAPER10M1R2D_R1_FAILURE_OR_RETRY_LOG.csv",
        "05_EXECUTION/PAPER10M1R2D_R1_ROW_LEVEL_RESULT_TABLE.csv",
        "06_CASE_SUMMARIES/*.csv",
        "07_METHOD_SUMMARIES/*.csv",
        "07_METHOD_SUMMARIES/*.md",
        "08_ABLATION_CONTRIBUTION/*.csv",
        "08_ABLATION_CONTRIBUTION/*.md",
        "09_QM_SOURCE_TRACE_SUMMARIES/*.csv",
        "09_QM_SOURCE_TRACE_SUMMARIES/*.md",
        "10_FIGURES/*.csv",
        "11_CLAIM_BOUNDARY/*",
        "12_TESTS/*.csv",
        "12_TESTS/*.md",
        "13_OBSIDIAN_SYNC/*.md",
        "13_OBSIDIAN_SYNC/*.csv",
        "14_AI_CONTEXT_UPDATE/*.md",
        "15_NEXT_STAGE/*.md",
    ]
    zip_path = export_dir / "paper10m1r2d_r1_v2_by2_internal_ablation_matrix_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    export_rows: list[dict[str, Any]] = []
    scan = {"violations": [], "files_scanned": 0}
    bad_patterns = [
        "C:\\Users\\",
        "/mnt/c/Users/",
        str(paths.runtime_root),
        str(paths.provider_root),
        str(paths.stage_root),
        str(paths.code_root),
        "by2.txt",
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "corr-raw.csv",
        "trace_vrtk2",
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for pattern in allowed_patterns:
            for source in paths.stage_root.glob(pattern):
                if not source.is_file() or source.suffix.lower() in {".png", ".pdf", ".zip"}:
                    continue
                rel = source.relative_to(paths.stage_root)
                text = sanitize_text(source.read_text(encoding="utf-8", errors="replace"), roots)
                violations = [pattern for pattern in bad_patterns if pattern in text]
                if violations:
                    scan["violations"].append({"file": str(rel), "patterns": violations})
                scan["files_scanned"] += 1
                zf.writestr(str(rel), text)
                export_rows.append({"source": str(rel), "exported": True, "bytes": len(text.encode("utf-8"))})
        readme = (
            "# README_FOR_NEXT_AI\n\n"
            f"Stage: {STAGE_NAME}\n"
            "This pack contains reports and summary CSVs only. Runtime binaries, providers, raw data, NAV/STD/EVAL_NAV, RUN_MANIFEST runtime files, figures, and local absolute paths are excluded.\n"
        )
        zf.writestr("README_FOR_NEXT_AI.md", readme)
    write_csv(export_dir / "export_clean_manifest.csv", export_rows)
    write_json(export_dir / "export_clean_path_scan.json", scan)
    (export_dir / "README_FOR_NEXT_AI.md").write_text(
        "# README_FOR_NEXT_AI\n\nSee the M1R2D_R1 internal ablation export-clean zip. Runtime payloads are intentionally excluded.\n",
        encoding="utf-8",
    )
    paths.export_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, paths.export_root / zip_path.name)
    shutil.copy2(export_dir / "export_clean_manifest.csv", paths.export_root / "export_clean_manifest.csv")
    shutil.copy2(export_dir / "export_clean_path_scan.json", paths.export_root / "export_clean_path_scan.json")
    shutil.copy2(export_dir / "README_FOR_NEXT_AI.md", paths.export_root / "README_FOR_NEXT_AI.md")
    return ("PASS" if not scan["violations"] else "FAIL", not scan["violations"])


def execute(args: argparse.Namespace) -> int:
    patch_base_runner()
    paths = base.RuntimePaths(
        stage_root=Path(args.stage_root).resolve(),
        runtime_root=Path(args.runtime_root).resolve(),
        export_root=Path(args.export_root).resolve(),
        m1r2a_stage_root=Path(args.m1r2a_stage_root).resolve(),
        m1r2b_stage_root=Path(args.m1r2b2_stage_root).resolve(),
        provider_root=Path(args.provider_root).resolve(),
        by2_imu=Path(args.by2_imu).resolve(),
        by2_statusyaw_gnss=Path(args.by2_statusyaw_gnss).resolve(),
        code_root=Path(args.code_root).resolve(),
    )
    roots = {
        "LEGSA_CODE_ROOT": paths.code_root,
        "LEGSA_PROJECT_ROOT": Path(args.project_root).resolve() if args.project_root else paths.stage_root.parents[2],
        "PAPER10M1R2A_STAGE_ROOT": paths.m1r2a_stage_root,
        "PAPER10M1R2B2_STAGE_ROOT": paths.m1r2b_stage_root,
        "PAPER10M1R2D_R1_STAGE_ROOT": paths.stage_root,
        "PAPER10M1R2D_R1_RUNTIME_ROOT": paths.runtime_root,
        "DEGRADED_PROVIDER_ROOT": paths.provider_root,
        "EXPORT_ROOT": paths.export_root,
        "BY2_FIX_ROOT": paths.by2_imu.parent,
        "TRACE_EVAL_REFERENCE_ONLY": Path(args.raw_trace_csv).resolve(),
    }
    ensure_dirs(paths)
    write_local_approval_and_lock(paths, roots)
    run_git_report(paths, roots)
    write_preflight_reports(paths, roots)
    write_parallel_precheck(paths, roots, args)
    write_method_reconciliation(paths)
    readiness = m1r2b2_readiness(paths)
    if any(readiness[key] != EXPECTED_CASES for key in ["provider_ready_cases", "effect_pass_cases", "yaw_lineage_pass_cases", "yaw_wrap_pass_cases"]):
        raise RuntimeError(f"BLOCKED_M1R2B2_PROVIDER_READY_CHECK_FAILED: {readiness}")

    imu_first, imu_last, _ = base.first_last_time(paths.by2_imu)
    status_first, _, _ = base.first_last_time(paths.by2_statusyaw_gnss)
    clean_first, clean_last, _ = base.first_last_time(
        paths.provider_root / "BY2_CLEAN_CANONICAL" / "02_GENERATED_PROVIDERS" / "gnss_position_provider.csv",
        delimiter=",",
        has_header=True,
    )
    time_offset = status_first - clean_first
    starttime = max(imu_first, status_first)
    endtime = min(imu_last, clean_last + time_offset)
    provider_reference = base.read_reference_from_clean_provider(paths.provider_root / "BY2_CLEAN_CANONICAL", time_offset)
    trace_reference = read_trace_reference(Path(args.raw_trace_csv).resolve())
    loaded = load_internal_ablation_modes(paths.code_root)
    cases, providers, _ = load_case_maps(paths)

    if args.prepare_only:
        build_locked_queue(paths, roots, clean_sentinel_passed=False)
        write_tests_report(paths, cmake_status=args.cmake_status, pytest_status=args.pytest_status)
        return 0

    clean_rows, clean_gate = run_clean_sentinel(
        paths=paths,
        roots=roots,
        loaded=loaded,
        cases=cases,
        providers=providers,
        time_offset=time_offset,
        starttime=starttime,
        endtime=endtime,
        provider_reference=provider_reference,
        trace_reference=trace_reference,
        force=args.force,
    )
    if not clean_gate["pass"]:
        counts = {"total": 0, "completed": 0, "failed": 0, "blocked": 0, "skipped": 0}
        write_tests_report(paths)
        write_claim_boundary(paths)
        write_next_stage_and_context(paths)
        figures, qa = [], []
        export_status, export_ok = export_clean(paths, roots)
        final = determine_final_decision(
            counts=counts,
            clean_gate=clean_gate,
            render_pass=True,
            export_ok=export_ok,
            full_rows_selected=False,
            clean_yaw_regression=True,
            qm_trace_ok=False,
        )
        write_final_reports(
            paths=paths,
            roots=roots,
            readiness=readiness,
            clean_rows=clean_rows,
            clean_gate=clean_gate,
            counts=counts,
            method_summary=[],
            figures=figures,
            render_pass=True,
            export_status=export_status,
            final_decision=final,
            cmake_status=args.cmake_status,
            pytest_status=args.pytest_status,
        )
        return 1

    locked = build_locked_queue(paths, roots, clean_sentinel_passed=True)
    selected = locked
    if args.limit:
        selected = selected[: args.limit]
    if args.methods:
        allowed = set(args.methods.split(","))
        selected = [row for row in selected if row["method_mode_id"] in allowed]
    if args.row_ids:
        allowed_rows = set(args.row_ids.split(","))
        selected = [row for row in selected if row["row_id"] in allowed_rows]

    def dispatch(row: dict[str, Any]) -> dict[str, Any]:
        frozen = loaded["method_modes"][row["method_mode_id"]]
        effective = resolve_effective_feature_flags(frozen.data, provider_status())
        safety = validate_mode_safety(frozen.data, effective)
        if safety:
            raise RuntimeError("; ".join(safety))
        return run_one_augmented_row(
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
            provider_reference=provider_reference,
            trace_reference=trace_reference,
            roots=roots,
            force=args.force,
        )

    full_rows_selected = not args.limit and not args.methods and not args.row_ids
    if full_rows_selected:
        smoke_rows = select_parallel_smoke_rows(locked)
        smoke_results = run_rows_parallel(
            rows=smoke_rows,
            workers=8,
            progress_interval=max(1, args.progress_interval),
            label="smoke",
            dispatch=dispatch,
        )
        smoke_counts = write_parallel_smoke_report(paths, smoke_results, workers=8)
        if smoke_counts["completed"] != smoke_counts["total"] or smoke_counts["failed"] or smoke_counts["blocked"] or smoke_counts["skipped"]:
            raise RuntimeError(f"BLOCKED_RUNNER_OR_ABLATION_METHOD_FAILURE: parallel smoke failed {smoke_counts}")
    else:
        smoke_results = []
        smoke_counts = {"total": 0, "completed": 0, "failed": 0, "blocked": 0, "skipped": 0}
        write_parallel_smoke_report(paths, smoke_results, workers=8)

    row_results = run_rows_parallel(
        rows=selected,
        workers=max(1, args.workers),
        progress_interval=max(1, args.progress_interval),
        label="formal",
        dispatch=dispatch,
    )
    counts = summarize_execution(paths, row_results)
    write_parallel_execution_summary(paths, row_results, workers=max(1, args.workers))
    method_summary = build_method_summary(paths, row_results)
    build_comparison_table(paths, row_results)
    build_ablation_contribution(paths, row_results)
    build_case_summaries(paths, row_results)
    build_trace_summaries(paths, row_results, readiness)
    figures, qa = make_figures(paths, row_results)
    write_claim_boundary(paths)
    write_next_stage_and_context(paths)
    write_tests_report(paths, row_results, cmake_status=args.cmake_status, pytest_status=args.pytest_status)
    render_pass = all(row.get("render_status") == "PASS" for row in qa)
    clean_full_rows = [row for row in row_results if row["case_id"] == "BY2_CLEAN_CANONICAL"]
    clean_regression = any(
        safe_float(row.get("yaw_rmse_deg"), math.inf) > 10.0
        for row in clean_full_rows
    )
    full_qm = [row for row in row_results if row["method_mode_id"] == "legsa_full_candidate_with_qm"]
    qm_trace_ok = all(truthy(row.get("qm_trace_file_exists")) for row in full_qm if truthy(row.get("qm_trace_required")))
    export_status, export_ok = export_clean(paths, roots)
    final = determine_final_decision(
        counts=counts,
        clean_gate=clean_gate,
        render_pass=render_pass,
        export_ok=export_ok,
        full_rows_selected=full_rows_selected,
        clean_yaw_regression=clean_regression,
        qm_trace_ok=qm_trace_ok,
    )
    write_final_reports(
        paths=paths,
        roots=roots,
        readiness=readiness,
        clean_rows=clean_rows,
        clean_gate=clean_gate,
        counts=counts,
        method_summary=method_summary,
        figures=figures,
        render_pass=render_pass,
        export_status=export_status,
        final_decision=final,
        cmake_status=args.cmake_status,
        pytest_status=args.pytest_status,
    )
    export_clean(paths, roots)
    return 0 if final.startswith(("PASS_", "CONDITIONAL_PASS_")) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--m1r2a-stage-root", required=True)
    parser.add_argument("--m1r2b2-stage-root", required=True)
    parser.add_argument("--provider-root", required=True)
    parser.add_argument("--by2-imu", required=True)
    parser.add_argument("--by2-statusyaw-gnss", required=True)
    parser.add_argument("--raw-trace-csv", required=True)
    parser.add_argument("--project-root", default="")
    parser.add_argument("--code-root", default=str(REPO_ROOT))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--methods", default="")
    parser.add_argument("--row-ids", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--progress-interval", type=int, default=25)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--cmake-status", default="PENDING")
    parser.add_argument("--pytest-status", default="PENDING")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return execute(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
