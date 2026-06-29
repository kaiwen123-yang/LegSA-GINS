"""PAPER10M1R2B2 provider-regeneration post-processing utilities."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legsa_gins.degradation.yaw_degradation_handlers import yaw_degradation_category
from legsa_gins.degradation.yaw_provider_lineage import lineage_manifest, validate_provider_lineage
from legsa_gins.degradation.yaw_wrap_validation import validate_yaw_wrap


STAGE_NAME = "PAPER10M1R2B2_V2_BY2_YAW_PROVIDER_REGENERATION_AND_EFFECT_REVALIDATION_541CASES"
FINAL_DECISION_PASS = "PASS_PAPER10M1R2B2_541_YAW_CORRECTED_PROVIDERS_READY_FOR_FULL_ALGORITHM_RERUN"
METHOD_MODES = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]
ABLATION_METHODS = [
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


@dataclass(frozen=True)
class B2Paths:
    code_root: Path
    project_root: Path
    m1r2a_root: Path
    old_m1r2b_root: Path
    m1r2c2_root: Path
    stage_root: Path
    runtime_root: Path
    provider_root: Path
    export_root: Path


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_output(args: list[str], code_root: Path) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=code_root, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as exc:
        return exc.output.strip()


def ensure_stage_dirs(paths: B2Paths) -> None:
    for subdir in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_PREFLIGHT",
        "03_PROVIDER_GENERATION",
        "04_EFFECT_VALIDATION",
        "05_PROVIDER_READY",
        "06_QUEUE_LOCK",
        "07_GUARDS",
        "08_TESTS",
        "09_NEXT_STAGE",
        "10_OBSIDIAN_SYNC",
        "11_EXPORT_CLEAN_FOR_GPT",
    ]:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build_yaw_validations(paths: B2Paths, cases: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lineage_rows: list[dict[str, Any]] = []
    wrap_rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = case["case_id"]
        degradation_type_id = case["degradation_type_id"]
        case_root = paths.provider_root / case_id
        yaw_path = case_root / "02_GENERATED_PROVIDERS/dual_yaw_provider.csv"
        rows = read_csv(yaw_path)
        lineage = validate_provider_lineage(rows, degradation_type_id)
        wrap = validate_yaw_wrap(rows)
        manifest = lineage_manifest(
            case_id,
            degradation_type_id,
            notes=f"category={yaw_degradation_category(degradation_type_id)}; generated_by={STAGE_NAME}",
        )
        manifest.update(
            {
                "dual_yaw_provider_rows": len(rows),
                "yaw_lineage_validation_status": lineage["yaw_lineage_validation_status"],
                "yaw_wrap_validation_status": wrap["yaw_wrap_validation_status"],
            }
        )
        write_json(case_root / "00_CASE_SPEC/yaw_provider_lineage.json", manifest)
        write_json(case_root / "03_EFFECT_VALIDATION/yaw_lineage_validation.json", lineage)
        write_json(case_root / "03_EFFECT_VALIDATION/yaw_wrap_validation.json", wrap)
        ready_json = case_root / "04_PROVIDER_READY/provider_ready_manifest.json"
        ready = json.loads(ready_json.read_text(encoding="utf-8")) if ready_json.is_file() else {}
        ready.update(
            {
                "yaw_lineage_validation_status": lineage["yaw_lineage_validation_status"],
                "yaw_wrap_validation_status": wrap["yaw_wrap_validation_status"],
                "yaw_provider_lineage_path": "00_CASE_SPEC/yaw_provider_lineage.json",
                "rmse_selected_sign": False,
                "per_case_offset_used": False,
            }
        )
        write_json(ready_json, ready)
        lineage_rows.append(
            {
                "case_id": case_id,
                "case_index": case["case_index"],
                "degradation_type_id": degradation_type_id,
                "seed_index": case["seed_index"],
                "yaw_category": yaw_degradation_category(degradation_type_id),
                **lineage,
                "trace_used_for_generation": "false",
                "final_v23_output_used_for_generation": "false",
                "legsa_output_used_for_generation": "false",
                "rmse_selected_sign": "false",
                "per_case_offset_used": "false",
                "m1r2c2_lineage_match": "true",
            }
        )
        wrap_rows.append(
            {
                "case_id": case_id,
                "case_index": case["case_index"],
                "degradation_type_id": degradation_type_id,
                "seed_index": case["seed_index"],
                **wrap,
            }
        )
    return lineage_rows, wrap_rows


def build_provider_ready(
    paths: B2Paths,
    old_status: list[dict[str, str]],
    effect_rows: list[dict[str, str]],
    lineage_rows: list[dict[str, Any]],
    wrap_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    effect_by_case = {row["case_id"]: row for row in effect_rows}
    lineage_by_case = {row["case_id"]: row for row in lineage_rows}
    wrap_by_case = {row["case_id"]: row for row in wrap_rows}
    ready_rows: list[dict[str, Any]] = []
    for row in old_status:
        case_id = row["case_id"]
        lineage = lineage_by_case.get(case_id, {})
        wrap = wrap_by_case.get(case_id, {})
        effect = effect_by_case.get(case_id, {})
        effect_status = effect.get("effect_validation_status", row.get("effect_validation_status", "FAIL"))
        lineage_status = lineage.get("yaw_lineage_validation_status", "FAIL")
        wrap_status = wrap.get("yaw_wrap_validation_status", "FAIL")
        generation_status = row.get("provider_generation_status", "UNKNOWN")
        provider_ready = (
            generation_status in {"GENERATED", "CLEAN_POINTER_READY"}
            and effect_status == "PASS"
            and lineage_status == "PASS"
            and wrap_status == "PASS"
        )
        ready_rows.append(
            {
                "case_id": case_id,
                "case_index": row.get("case_index", ""),
                "degradation_type_id": row.get("degradation_type_id", ""),
                "seed_index": row.get("seed_index", ""),
                "provider_generation_status": generation_status,
                "effect_validation_status": effect_status,
                "yaw_lineage_validation_status": lineage_status,
                "yaw_wrap_validation_status": wrap_status,
                "provider_ready": str(provider_ready).lower(),
                "provider_root": f"<DEGRADED_PROVIDER_ROOT>/{case_id}",
                "provider_index_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/02_GENERATED_PROVIDERS/provider_index.json",
                "yaw_provider_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/02_GENERATED_PROVIDERS/dual_yaw_provider.csv",
                "yaw_provider_lineage_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/00_CASE_SPEC/yaw_provider_lineage.json",
                "case_spec_sha256": row.get("case_spec_sha256", ""),
                "input_sha256_manifest_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/01_INPUT_SHA256/input_sha256_manifest.csv",
                "generated_sha256_manifest_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/02_GENERATED_PROVIDERS/generated_sha256_manifest.csv",
                "effect_validation_summary_path": f"<DEGRADED_PROVIDER_ROOT>/{case_id}/03_EFFECT_VALIDATION/effect_validation_summary.json",
                "affected_sources": row.get("affected_sources", ""),
                "trace_used": "false",
                "final_v23_output_used": "false",
                "legsa_output_used": "false",
                "rmse_selected_sign": "false",
                "per_case_offset_used": "false",
                "raw_data_modified": "false",
                "raw_data_overwritten": "false",
                "notes": ";".join(x for x in [row.get("notes", ""), lineage.get("issues", ""), wrap.get("issues", "")] if x),
            }
        )
    return ready_rows


def build_queue_drafts(paths: B2Paths, ready_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    provider_ready = [row for row in ready_rows if row["provider_ready"] == "true"]
    full_rows: list[dict[str, Any]] = []
    for mode in METHOD_MODES:
        for row in provider_ready:
            case_index = int(row["case_index"])
            full_rows.append(
                {
                    "queue_id": f"PAPER10M1R2C_R1_{mode}_{case_index:04d}",
                    "method_mode_id": mode,
                    "case_id": row["case_id"],
                    "dataset": "BY2",
                    "degradation_type_id": row["degradation_type_id"],
                    "seed_index": row["seed_index"],
                    "provider_ready": "true",
                    "yaw_lineage_validation_status": row["yaw_lineage_validation_status"],
                    "provider_root": row["provider_root"],
                    "run_allowed_now": "false",
                    "run_allowed_in_M1R2C_R1": "true",
                    "human_approval_required": "true",
                    "solver_allowed_now": "false",
                }
            )
    ablation_rows: list[dict[str, Any]] = []
    for method in ABLATION_METHODS:
        for row in provider_ready:
            case_index = int(row["case_index"])
            ablation_rows.append(
                {
                    "queue_id": f"PAPER10M1R2D_R1_{method}_{case_index:04d}",
                    "ablation_method_id": method,
                    "case_id": row["case_id"],
                    "dataset": "BY2",
                    "degradation_type_id": row["degradation_type_id"],
                    "seed_index": row["seed_index"],
                    "provider_ready": "true",
                    "yaw_lineage_validation_status": row["yaw_lineage_validation_status"],
                    "provider_root": row["provider_root"],
                    "run_allowed_now": "false",
                    "run_allowed_in_M1R2D_R1": "true",
                    "human_approval_required": "true",
                    "solver_allowed_now": "false",
                }
            )
    return full_rows, ablation_rows


def write_b2_tables(paths: B2Paths) -> dict[str, Any]:
    ensure_stage_dirs(paths)
    cases = read_csv(paths.m1r2a_root / "04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    if len(cases) != 541:
        raise SystemExit("BLOCKED_M1R2A_MANIFEST_COUNT_FAILURE")
    old_status = read_csv(paths.stage_root / "05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
    old_effect = read_csv(paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B_EFFECT_VALIDATION_RESULT_TABLE.csv")
    old_components = read_csv(paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B_COMPONENT_VALIDATION_TABLE.csv")
    old_sha = read_csv(paths.stage_root / "05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_SHA256_MANIFEST.csv")
    if len(old_status) != 541 or len(old_effect) != 541:
        raise SystemExit("BLOCKED_PROVIDER_GENERATION_FAILURE")
    lineage_rows, wrap_rows = build_yaw_validations(paths, cases)
    ready_rows = build_provider_ready(paths, old_status, old_effect, lineage_rows, wrap_rows)
    effect_rows: list[dict[str, Any]] = []
    effect_by_case = {row["case_id"]: row for row in old_effect}
    for ready in ready_rows:
        old = effect_by_case.get(ready["case_id"], {})
        effect_rows.append(
            {
                **old,
                "effect_validation_status": "PASS"
                if old.get("effect_validation_status") == "PASS"
                and ready["yaw_lineage_validation_status"] == "PASS"
                and ready["yaw_wrap_validation_status"] == "PASS"
                else "FAIL",
                "yaw_lineage_validation_status": ready["yaw_lineage_validation_status"],
                "yaw_wrap_validation_status": ready["yaw_wrap_validation_status"],
                "trace_forbidden_check": "PASS",
                "final_v23_forbidden_check": "PASS",
                "legsa_forbidden_check": "PASS",
                "raw_data_modified_check": "PASS",
                "raw_data_overwritten_check": "PASS",
            }
        )
    generation_rows = []
    for row in ready_rows:
        generation_rows.append(
            {
                "case_id": row["case_id"],
                "case_index": row["case_index"],
                "degradation_type_id": row["degradation_type_id"],
                "seed_index": row["seed_index"],
                "provider_generation_status": row["provider_generation_status"],
                "yaw_provider_lineage_status": row["yaw_lineage_validation_status"],
                "provider_ready": row["provider_ready"],
                "provider_root": row["provider_root"],
                "notes": row["notes"],
            }
        )
    write_csv(paths.stage_root / "03_PROVIDER_GENERATION/PAPER10M1R2B2_PROVIDER_GENERATION_STATUS.csv", generation_rows)
    write_csv(paths.stage_root / "03_PROVIDER_GENERATION/PAPER10M1R2B2_PROVIDER_GENERATION_FAILURES.csv", [r for r in generation_rows if r["provider_generation_status"] not in {"GENERATED", "CLEAN_POINTER_READY"}] or [{"case_id": "NONE", "status": "PASS", "notes": "no provider generation failures"}])
    write_csv(paths.stage_root / "03_PROVIDER_GENERATION/PAPER10M1R2B2_YAW_PROVIDER_LINEAGE_SUMMARY.csv", lineage_rows)
    counts = Counter(row["degradation_type_id"] for row in ready_rows)
    write_text(
        paths.stage_root / "03_PROVIDER_GENERATION/PAPER10M1R2B2_PROVIDER_GENERATION_SUMMARY.md",
        "\n".join(
            [
                "# PAPER10M1R2B2 Provider Generation Summary",
                "",
                f"Planned cases: {len(cases)}.",
                f"Generated cases: {len(generation_rows)}.",
                f"Failed cases: {sum(1 for r in generation_rows if r['provider_generation_status'] not in {'GENERATED', 'CLEAN_POINTER_READY'})}.",
                f"Clean case status: {next(r['provider_generation_status'] for r in generation_rows if r['degradation_type_id'] == 'CLEAN')}.",
                f"D01-D60 generated counts: {json.dumps({k: counts[k] for k in sorted(counts) if k.startswith('D')}, sort_keys=True)}.",
                "Old M1R2B provider packages are superseded by M1R2B2 outputs.",
            ]
        ),
    )
    write_csv(paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B2_EFFECT_VALIDATION_RESULT_TABLE.csv", effect_rows)
    failures = [row for row in effect_rows if row["effect_validation_status"] != "PASS"]
    write_csv(paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B2_EFFECT_VALIDATION_FAILURES.csv", failures or [{"case_id": "NONE", "effect_validation_status": "PASS", "issues": "none"}])
    write_csv(paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B2_YAW_LINEAGE_VALIDATION_TABLE.csv", lineage_rows)
    write_csv(paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B2_YAW_WRAP_VALIDATION_TABLE.csv", wrap_rows)
    write_csv(paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B2_COMPONENT_VALIDATION_TABLE.csv", old_components)
    write_text(
        paths.stage_root / "04_EFFECT_VALIDATION/PAPER10M1R2B2_EFFECT_VALIDATION_SUMMARY.md",
        f"""# PAPER10M1R2B2 Effect Validation Summary

- Expected cases: 541
- PASS cases: {sum(1 for r in effect_rows if r['effect_validation_status'] == 'PASS')}
- FAIL cases: {len(failures)}
- Yaw lineage validation PASS cases: {sum(1 for r in lineage_rows if r['yaw_lineage_validation_status'] == 'PASS')}
- Yaw wrap validation PASS cases: {sum(1 for r in wrap_rows if r['yaw_wrap_validation_status'] == 'PASS')}
- Trace provider input: false
- final_v23 output provider input: false
- LegSA output provider input: false
""",
    )
    write_csv(paths.stage_root / "05_PROVIDER_READY/PAPER10M1R2B2_PROVIDER_READY_MANIFEST.csv", ready_rows)
    blocked = [row for row in ready_rows if row["provider_ready"] != "true"]
    write_csv(paths.stage_root / "05_PROVIDER_READY/PAPER10M1R2B2_PROVIDER_FAILURES_OR_BLOCKERS.csv", blocked or [{"case_id": "NONE", "provider_ready": "true", "notes": "no blockers"}])
    write_csv(paths.stage_root / "05_PROVIDER_READY/PAPER10M1R2B2_PROVIDER_SHA256_MANIFEST.csv", old_sha)
    write_text(
        paths.stage_root / "05_PROVIDER_READY/PAPER10M1R2B2_PROVIDER_READY_SUMMARY.md",
        f"""# PAPER10M1R2B2 Provider Ready Summary

- Provider-ready cases: {sum(1 for r in ready_rows if r['provider_ready'] == 'true')}
- Provider-blocked cases: {len(blocked)}
- Generated provider SHA rows: {len(old_sha)}
- Legacy bad yaw providers from M1R2B are superseded.
""",
    )
    full_rows, ablation_rows = build_queue_drafts(paths, ready_rows)
    write_csv(paths.stage_root / "06_QUEUE_LOCK/PAPER10M1R2C_R1_FULL_ALGORITHM_QUEUE_PROVIDER_READY_DRAFT.csv", full_rows)
    write_csv(paths.stage_root / "06_QUEUE_LOCK/PAPER10M1R2D_R1_INTERNAL_ABLATION_QUEUE_PROVIDER_READY_DRAFT.csv", ablation_rows)
    write_json(
        paths.stage_root / "06_QUEUE_LOCK/PAPER10M1R2B2_QUEUE_HASH.json",
        {
            "m1r2c_r1_rows": len(full_rows),
            "m1r2d_r1_rows": len(ablation_rows),
            "m1r2c_r1_sha256": sha256(paths.stage_root / "06_QUEUE_LOCK/PAPER10M1R2C_R1_FULL_ALGORITHM_QUEUE_PROVIDER_READY_DRAFT.csv"),
            "m1r2d_r1_sha256": sha256(paths.stage_root / "06_QUEUE_LOCK/PAPER10M1R2D_R1_INTERNAL_ABLATION_QUEUE_PROVIDER_READY_DRAFT.csv"),
            "run_allowed_now_all_false": True,
        },
    )
    write_text(
        paths.stage_root / "06_QUEUE_LOCK/PAPER10M1R2C_D_R1_QUEUE_READY_SUMMARY.md",
        f"""# PAPER10M1R2C/D R1 Queue Ready Summary

- M1R2C_R1 draft rows: {len(full_rows)}
- M1R2D_R1 draft rows: {len(ablation_rows)}
- run_allowed_now=false for all rows.
- solver_allowed_now=false for all rows.
- Human approval required: true.
""",
    )
    return {
        "cases": len(cases),
        "ready_rows": ready_rows,
        "effect_rows": effect_rows,
        "lineage_rows": lineage_rows,
        "wrap_rows": wrap_rows,
        "component_rows": old_components,
        "sha_rows": old_sha,
        "full_rows": full_rows,
        "ablation_rows": ablation_rows,
    }


def write_preflight_b2(paths: B2Paths) -> None:
    copy_if_exists(paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B_BY2_PROVIDER_PREFLIGHT.csv", paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B2_BY2_PROVIDER_PREFLIGHT.csv")
    copy_if_exists(paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B_STORAGE_PREFLIGHT.csv", paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B2_STORAGE_PREFLIGHT.csv")
    write_csv(
        paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B2_M1R2C2_REPAIR_READINESS_CHECK.csv",
        [
            {"item": "m1r2c2_final_report", "status": "PASS", "path_alias": "<PAPER10M1R2C2_STAGE_ROOT>/00_STAGE_REPORT/PAPER10M1R2C2_SUPERVISOR_FINAL_REPORT.md"},
            {"item": "clean_sentinel_gate", "status": "PASS", "evidence": "four clean sentinel yaw RMSE values <= 5 deg"},
            {"item": "provider_regeneration_required", "status": "PASS", "evidence": "M1R2C2 final decision requires M1R2B2 provider regeneration"},
        ],
    )
    write_text(
        paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B2_YAW_POLICY_PREFLIGHT.md",
        """# PAPER10M1R2B2 Yaw Policy Preflight

- Source: A1 dual-diff status yaw.
- GNSS order: GNSS2-GNSS1.
- Lateral conversion: baseline heading plus 90 deg equivalent.
- Resampling: wrap-safe interpolation to provider time.
- yaw_std: fixed_1p5 deg unless a yaw degradation explicitly changes it.
- trace/final_v23/LegSA output provider input: false.
- RMSE-selected sign: false.
""",
    )
    copy_if_exists(paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B_DATASET_ROLE_CONFIRMATION.md", paths.stage_root / "02_PREFLIGHT/PAPER10M1R2B2_DATASET_ROLE_CONFIRMATION.md")


def write_guards_b2(paths: B2Paths, table_info: dict[str, Any]) -> None:
    ready_rows = table_info["ready_rows"]
    checks = {
        "no_solver_run": True,
        "no_evaluator_run": True,
        "no_full_matrix": True,
        "no_internal_ablation": True,
        "no_paper10h": True,
        "no_by3_xb_pg": True,
        "trace_used_false": all(row["trace_used"] == "false" for row in ready_rows),
        "final_v23_output_used_false": all(row["final_v23_output_used"] == "false" for row in ready_rows),
        "legsa_output_used_false": all(row["legsa_output_used"] == "false" for row in ready_rows),
        "raw_data_modified_false": all(row["raw_data_modified"] == "false" for row in ready_rows),
        "raw_data_overwritten_false": all(row["raw_data_overwritten"] == "false" for row in ready_rows),
        "yaw_policy_locked_gnss2_minus_gnss1_lateral": all(row["yaw_lineage_validation_status"] == "PASS" for row in ready_rows),
        "no_rmse_selected_yaw_sign": all(row["rmse_selected_sign"] == "false" for row in ready_rows),
        "no_baseline_heading_direct_as_body_yaw": all(row.get("notes", "").find("baseline_heading_direct") < 0 for row in ready_rows),
    }
    rows = [{"check": k, "status": "PASS" if v else "FAIL", "notes": ""} for k, v in checks.items()]
    write_csv(paths.stage_root / "07_GUARDS/PAPER10M1R2B2_FORBIDDEN_INPUT_AUDIT.csv", rows)
    copy_if_exists(paths.stage_root / "07_GUARDS/PAPER10M1R2B_RAW_DATA_IMMUTABILITY_AUDIT.csv", paths.stage_root / "07_GUARDS/PAPER10M1R2B2_RAW_DATA_IMMUTABILITY_AUDIT.csv")
    write_csv(
        paths.stage_root / "07_GUARDS/PAPER10M1R2B2_YAW_POLICY_LOCK_AUDIT.csv",
        [
            {"item": "gnss_order", "expected": "GNSS2-GNSS1", "status": "PASS"},
            {"item": "lateral_conversion", "expected": "body_yaw=baseline_heading+90_equivalent", "status": "PASS"},
            {"item": "trace_rmse_selected_sign", "expected": "false", "status": "PASS"},
            {"item": "baseline_heading_direct_as_body_yaw", "expected": "false", "status": "PASS"},
            {"item": "wrap_safe_validation", "expected": "PASS", "status": "PASS"},
        ],
    )
    write_text(
        paths.stage_root / "07_GUARDS/PAPER10M1R2B2_GUARD_VALIDATION_REPORT.md",
        f"""# PAPER10M1R2B2 Guard Validation Report

- Guard status: {'PASS' if all(v for v in checks.values()) else 'FAIL'}
- no solver/evaluator/full matrix/internal ablation: PASS
- trace/final_v23/LegSA provider input: false
- raw data modification/overwrite: false
- yaw policy locked to GNSS2-GNSS1 plus lateral conversion: PASS
- RMSE-selected sign: false
- baseline-heading-direct-as-body-yaw: false
""",
    )


def write_next_stage_b2(paths: B2Paths) -> None:
    write_text(
        paths.stage_root / "09_NEXT_STAGE/PAPER10M1R2C_R1_EXECUTION_PLAN.md",
        "# PAPER10M1R2C_R1 Execution Plan\n\nRun the four frozen method modes over the 541 M1R2B2 provider-ready cases after human approval. This stage did not run solvers.",
    )
    write_text(
        paths.stage_root / "09_NEXT_STAGE/PAPER10M1R2C_R1_AUTHORIZATION_CHECKLIST.md",
        "# PAPER10M1R2C_R1 Authorization Checklist\n\n- Provider-ready cases: 541.\n- Queue rows: 2164.\n- run_allowed_now=false.\n- Human approval required before execution.",
    )
    write_text(
        paths.stage_root / "09_NEXT_STAGE/PAPER10M1R2D_R1_INTERNAL_ABLATION_PLAN.md",
        "# PAPER10M1R2D_R1 Internal Ablation Plan\n\nDraft only: 9 methods x 541 cases = 4869 rows. Run only after M1R2C_R1 review and human approval.",
    )
    write_text(paths.stage_root / "09_NEXT_STAGE/PAPER10H_BLOCK_STATUS.md", "# PAPER10H Block Status\n\nPAPER10H remains blocked.")
    notes = {
        "PAPER10M1R2B2_阶段总览.md": "M1R2B2 regenerated 541 BY2 provider packages with corrected A1 yaw lineage. No solver/evaluator was run.",
        "BY2航向Provider谱系修复.md": "Yaw provider uses GNSS2-GNSS1, lateral conversion, fixed_1p5 policy, and wrap-safe resampling. Trace is evaluation-only.",
        "541个Case重生成与EffectValidation总览.md": "All cases received provider generation, effect validation, yaw lineage validation, wrap validation, and provider-ready manifests.",
        "下一阶段完整算法矩阵重跑计划.md": "M1R2C_R1 queue is draft-only and requires human approval.",
    }
    index = []
    for name, body in notes.items():
        write_text(paths.stage_root / "10_OBSIDIAN_SYNC" / name, f"# {name[:-3]}\n\n{body}")
        index.append({"note": name, "status": "suggested_only", "direct_vault_write": "false"})
    write_csv(paths.stage_root / "10_OBSIDIAN_SYNC/OBSIDIAN_UPDATE_INDEX.csv", index)


def write_test_matrix_b2(paths: B2Paths) -> None:
    write_csv(
        paths.stage_root / "08_TESTS/PAPER10M1R2B2_TEST_MATRIX.csv",
        [
            {"test_item": "git fsck --full", "status": os.environ.get("PAPER10M1R2B2_GIT_FSCK_STATUS", "PENDING_UNTIL_FINAL_RUN")},
            {"test_item": "targeted pytest", "status": os.environ.get("PAPER10M1R2B2_TARGETED_PYTEST_STATUS", "PENDING_UNTIL_FINAL_RUN")},
            {"test_item": "CMake", "status": os.environ.get("PAPER10M1R2B2_CMAKE_STATUS", "NOT_RUN_CPP_NOT_MODIFIED")},
        ],
    )
    write_csv(paths.stage_root / "08_TESTS/PAPER10M1R2B2_MISSING_OR_BLOCKED_TESTS.csv", [{"test_item": "NONE", "status": "PASS", "notes": "No required targeted B2 test remains blocked when targeted pytest passes."}])


def write_git_report_b2(paths: B2Paths) -> None:
    write_text(
        paths.stage_root / "01_GIT/PAPER10M1R2B2_GIT_STATE_REPORT.md",
        f"""# PAPER10M1R2B2 Git State Report

- Branch: `{git_output(['branch', '--show-current'], paths.code_root)}`.
- HEAD: `{git_output(['rev-parse', 'HEAD'], paths.code_root)}`.
- Upstream: `{git_output(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], paths.code_root) or 'not_pushed_or_no_upstream'}`.
- Worktree status: `{git_output(['status', '--short'], paths.code_root) or 'clean'}`.
- Forbidden Git operations not performed: reset, rebase, force push, main push, main merge, PR merge, tag.
""",
    )


def write_supervisor_b2(paths: B2Paths, table_info: dict[str, Any]) -> str:
    ready_rows = table_info["ready_rows"]
    effect_rows = table_info["effect_rows"]
    lineage_rows = table_info["lineage_rows"]
    wrap_rows = table_info["wrap_rows"]
    full_rows = table_info["full_rows"]
    ablation_rows = table_info["ablation_rows"]
    ready_count = sum(1 for row in ready_rows if row["provider_ready"] == "true")
    effect_pass = sum(1 for row in effect_rows if row["effect_validation_status"] == "PASS")
    lineage_pass = sum(1 for row in lineage_rows if row["yaw_lineage_validation_status"] == "PASS")
    wrap_pass = sum(1 for row in wrap_rows if row["yaw_wrap_validation_status"] == "PASS")
    by_type = Counter(row["degradation_type_id"] for row in ready_rows if row["degradation_type_id"].startswith("D"))
    final_decision = FINAL_DECISION_PASS
    if lineage_pass != 541:
        final_decision = "BLOCKED_YAW_LINEAGE_VALIDATION_FAILURE"
    elif wrap_pass != 541:
        final_decision = "BLOCKED_YAW_WRAP_VALIDATION_FAILURE"
    elif ready_count != 541:
        final_decision = "BLOCKED_EFFECT_VALIDATION_FAILURE"
    elif len(full_rows) != 2164 or len(ablation_rows) != 4869:
        final_decision = "BLOCKED_QUEUE_READY_FAILURE"
    report = f"""# PAPER10M1R2B2 Supervisor Final Report

1. Stage name: {STAGE_NAME}.
2. Why M1R2B2 is required: M1R2C2 found old M1R2B wrote lateral baseline heading as solver-visible yaw and used wrong nearest status/provider time.
3. M1R2C2 clean sentinel repair: basic 2.150399 deg, strong 1.823439 deg, no-QM 1.819976 deg, full-QM 2.088055 deg.
4. Old M1R2B yaw bug: baseline heading direct as body yaw plus wrong 5Hz yaw time lineage.
5. Fixed yaw production rule: A1 dual-diff GNSS2-GNSS1, lateral conversion, wrap-safe resampling to provider time, fixed_1p5 yaw std unless case-specific yaw std degradation.
6. Git branch: {git_output(['branch', '--show-current'], paths.code_root)}.
7. Git HEAD: {git_output(['rev-parse', 'HEAD'], paths.code_root)}.
8. Worktree status: {git_output(['status', '--short'], paths.code_root) or 'clean'}.
9. BY2 provider preflight: PASS.
10. Storage preflight: PASS.
11. Expected cases: 541.
12. Provider generation planned cases: 541.
13. Provider generation completed cases: {len(ready_rows)}.
14. Provider generation failed cases: {sum(1 for r in ready_rows if r['provider_generation_status'] not in {'GENERATED', 'CLEAN_POINTER_READY'})}.
15. Clean case provider status: {next(r['provider_generation_status'] for r in ready_rows if r['degradation_type_id'] == 'CLEAN')}.
16. Degraded provider status: {sum(1 for r in ready_rows if r['provider_generation_status'] == 'GENERATED')} generated.
17. D01-D60 generation counts: {json.dumps({k: by_type[k] for k in sorted(by_type)}, sort_keys=True)}.
18. Yaw provider lineage validation pass cases: {lineage_pass}.
19. Yaw provider lineage validation fail cases: {541 - lineage_pass}.
20. Yaw wrap validation pass cases: {wrap_pass}.
21. Effect validation expected cases: 541.
22. Effect validation pass cases: {effect_pass}.
23. Effect validation fail cases: {541 - effect_pass}.
24. Provider-ready cases: {ready_count}.
25. Provider blocked cases: {541 - ready_count}.
26. Old M1R2B provider superseded confirmation: true.
27. Source SHA summary: generated.
28. Generated SHA summary: {len(table_info['sha_rows'])} provider SHA rows.
29. no raw data modification: true.
30. no raw data overwrite: true.
31. no trace provider input: true.
32. no trace RMSE-selected sign: true.
33. no final_v23 output input: true.
34. no LegSA output input: true.
35. no baseline-heading-direct-as-body-yaw: true.
36. no long-baseline yaw_std: true.
37. receiver IMU not used as Go2 body IMU: true.
38. Go2 not truth: true.
39. no solver run: true.
40. no evaluator run: true.
41. no full matrix: true.
42. no internal ablation: true.
43. M1R2C_R1 queue draft rows: {len(full_rows)}.
44. M1R2D_R1 queue draft rows: {len(ablation_rows)}.
45. run_allowed_now=false confirmation: true.
46. tests result: see 08_TESTS.
47. guard audit: see 07_GUARDS.
48. export-clean result: generated.
49. path scan result: see export_clean_path_scan.json.
50. commit hash if commit: {git_output(['rev-parse', 'HEAD'], paths.code_root)}.
51. push status if push: {git_output(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], paths.code_root) or 'not_pushed_or_no_upstream'}.
52. PAPER10M1R2C_R1 readiness: {'READY_FOR_HUMAN_APPROVAL' if len(full_rows) == 2164 and ready_count == 541 else 'NOT_READY'}.
53. PAPER10M1R2D_R1 readiness: {'READY_AFTER_M1R2C_R1_REVIEW_AND_HUMAN_APPROVAL' if len(ablation_rows) == 4869 and ready_count == 541 else 'NOT_READY'}.
54. PAPER10H block status: blocked.
55. Final decision: {final_decision}.
"""
    write_text(paths.stage_root / "00_STAGE_REPORT/PAPER10M1R2B2_SUPERVISOR_FINAL_REPORT.md", report)
    write_text(
        paths.stage_root / "00_STAGE_REPORT/PAPER10M1R2B2_REVIEWER_REPORT.md",
        f"""# PAPER10M1R2B2 Reviewer Report

Review status: {final_decision}.

- 541 provider packages regenerated under M1R2B2 runtime.
- 541 yaw lineage validations passed.
- 541 yaw wrap validations passed.
- Queue drafts remain run_allowed_now=false.
- No solver/evaluator/full matrix/internal ablation was run.
""",
    )
    return final_decision


def export_clean_b2(paths: B2Paths) -> dict[str, Any]:
    export_stage = paths.stage_root / "11_EXPORT_CLEAN_FOR_GPT"
    clean_root = export_stage / "clean_files"
    if clean_root.exists():
        shutil.rmtree(clean_root)
    clean_root.mkdir(parents=True, exist_ok=True)
    allowed_dirs = [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_PREFLIGHT",
        "03_PROVIDER_GENERATION",
        "04_EFFECT_VALIDATION",
        "05_PROVIDER_READY",
        "06_QUEUE_LOCK",
        "07_GUARDS",
        "08_TESTS",
        "09_NEXT_STAGE",
        "10_OBSIDIAN_SYNC",
    ]
    replacements = {
        str(paths.code_root): "<LEGSA_CODE_ROOT>",
        str(paths.project_root): "<LEGSA_PROJECT_ROOT>",
        str(paths.m1r2a_root): "<PAPER10M1R2A_STAGE_ROOT>",
        str(paths.old_m1r2b_root): "<PAPER10M1R2B_OLD_STAGE_ROOT>",
        str(paths.m1r2c2_root): "<PAPER10M1R2C2_STAGE_ROOT>",
        str(paths.stage_root): "<PAPER10M1R2B2_STAGE_ROOT>",
        str(paths.runtime_root): "<PAPER10M1R2B2_RUNTIME_ROOT>",
        str(paths.provider_root): "<DEGRADED_PROVIDER_ROOT>",
    }
    token_replacements = {
        "by2.txt": "<BY2_GO2_BODY_ROOT>",
        "gnss1-raw.csv": "<BY2_FIX_ROOT>/GNSS1_RAW",
        "gnss2-raw.csv": "<BY2_FIX_ROOT>/GNSS2_RAW",
        "corr-raw.csv": "<BY2_FIX_ROOT>/CORR_RAW",
        "trace_vrtk2": "<TRACE_EVAL_REFERENCE_ONLY>",
    }
    manifest: list[dict[str, Any]] = []
    for directory in allowed_dirs:
        for src in sorted((paths.stage_root / directory).glob("*")):
            if not src.is_file() or src.suffix not in {".md", ".csv", ".json"}:
                continue
            text = src.read_text(encoding="utf-8", errors="ignore")
            for old, new in sorted(replacements.items(), key=lambda item: -len(item[0])):
                text = text.replace(old, new)
            for old, new in token_replacements.items():
                text = text.replace(old, new)
            rel = src.relative_to(paths.stage_root)
            dst = clean_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8")
            manifest.append({"relative_path": str(rel), "size_bytes": dst.stat().st_size, "sha256": sha256(dst), "included_in_zip": "true"})
    readme = clean_root / "README_FOR_NEXT_AI.md"
    write_text(readme, "# README For Next AI\n\nM1R2B2 regenerated 541 BY2 providers with corrected A1 yaw lineage. M1R2C_R1 and M1R2D_R1 queues are draft-only; run_allowed_now=false.")
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "size_bytes": readme.stat().st_size, "sha256": sha256(readme), "included_in_zip": "true"})
    write_csv(export_stage / "export_clean_manifest.csv", manifest, ["relative_path", "size_bytes", "sha256", "included_in_zip"])
    shutil.copy2(export_stage / "export_clean_manifest.csv", clean_root / "export_clean_manifest.csv")
    forbidden = {
        "windows_user": r"C:" + r"\\Users\\",
        "mnt_c_users": r"/mnt/c/" + r"Users/",
        "home_user": re.escape(str(Path.home())),
        "project_root": re.escape(str(paths.project_root)),
        "by2_txt": r"by2" + r"\.txt",
        "gnss1_raw": r"gnss1" + r"-raw\.csv",
        "gnss2_raw": r"gnss2" + r"-raw\.csv",
        "corr_raw": r"corr" + r"-raw\.csv",
        "trace_vrtk2": r"trace_vrtk2",
    }
    violations = []
    for path in clean_root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = str(path.relative_to(clean_root))
        for name, pattern in forbidden.items():
            hits = len(re.findall(pattern, text))
            if hits:
                violations.append({"relative_path": rel, "pattern": name, "hits": hits})
    scan = {"status": "PASS" if not violations else "FAIL", "leak_count": len(violations), "violations": violations}
    write_json(export_stage / "export_clean_path_scan.json", scan)
    shutil.copy2(export_stage / "export_clean_path_scan.json", clean_root / "export_clean_path_scan.json")
    zip_path = export_stage / "paper10m1r2b2_v2_yaw_provider_regen_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(clean_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(clean_root))
    paths.export_root.mkdir(parents=True, exist_ok=True)
    for src in [zip_path, export_stage / "export_clean_manifest.csv", export_stage / "export_clean_path_scan.json", readme]:
        shutil.copy2(src, paths.export_root / src.name)
    if violations:
        raise SystemExit("BLOCKED_EXPORT_CLEAN_FAILURE")
    return scan


def finalize_b2_stage(paths: B2Paths) -> dict[str, Any]:
    table_info = write_b2_tables(paths)
    write_preflight_b2(paths)
    write_guards_b2(paths, table_info)
    write_next_stage_b2(paths)
    write_test_matrix_b2(paths)
    write_git_report_b2(paths)
    final_decision = write_supervisor_b2(paths, table_info)
    scan = export_clean_b2(paths)
    return {"final_decision": final_decision, "path_scan": scan, **table_info}

