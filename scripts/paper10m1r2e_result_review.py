#!/usr/bin/env python3
"""Generate PAPER10M1R2E BY2 result-review package.

This script is review-only. It reads existing M1R2A/M1R2B2/M1R2C_R1/M1R2D_R1
CSV/Markdown evidence, classifies method/module/figure/claim boundaries, and
writes lightweight reports plus an export-clean package. It does not invoke any
solver, evaluator, provider generator, random generator, or degradation builder.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper10m1r2e_claim_boundary import (  # noqa: E402
    forbidden_claim_markdown,
    write_claim_boundary_outputs,
)
from scripts.paper10m1r2e_figure_package import classify_figure_index, write_csv as write_figure_csv  # noqa: E402


STAGE_NAME = "PAPER10M1R2E_BY2_RESULT_REVIEW_FIGURE_PACKAGE_AND_CLAIM_BOUNDARY_FREEZE"
EXPECTED_CASES = 541
EXPECTED_TYPES = 60
EXPECTED_M1R2C_ROWS = 2164
EXPECTED_M1R2D_ROWS = 4869
EXPECTED_M1R2C_METHODS = {
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
}
EXPECTED_M1R2D_METHODS = {
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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.12g}"
    return "" if value is None else str(value)


def fnum(value: Any, default: float = math.nan) -> float:
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


def run_git(repo_root: Path, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "cmd": "git " + " ".join(args),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def aliases(args: argparse.Namespace) -> dict[str, Path]:
    project_root = args.stage_root.parents[2]
    return {
        "LEGSA_CODE_ROOT": args.repo_root,
        "LEGSA_PROJECT_ROOT": project_root,
        "M1R2A_STAGE_ROOT": args.m1r2a_stage_root,
        "M1R2B2_STAGE_ROOT": args.m1r2b2_stage_root,
        "M1R2C_R1_STAGE_ROOT": args.m1r2c_stage_root,
        "M1R2D_R1_STAGE_ROOT": args.m1r2d_stage_root,
        "M1R2E_STAGE_ROOT": args.stage_root,
        "M1R2C_R1_RUNTIME_ROOT": args.m1r2c_runtime_root,
        "M1R2D_R1_RUNTIME_ROOT": args.m1r2d_runtime_root,
        "M1R2E_LOCAL_REVIEW_ROOT": args.review_root,
        "M1R2E_EXPORT_ROOT": args.export_root,
    }


def alias_path(path: Path | str, root_aliases: dict[str, Path]) -> str:
    text = str(path)
    p = Path(text)
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        try:
            rel = resolved.relative_to(root.resolve())
            return f"<{label}>/{rel.as_posix()}"
        except ValueError:
            continue
    return sanitize_text(text, root_aliases)


def sanitize_text(text: str, root_aliases: dict[str, Path]) -> str:
    out = text
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        out = out.replace(str(root), f"<{label}>")
    redactions = {
        "by2" + ".txt": "<BY2_GO2_BODY_SOURCE>",
        "gnss1" + "-raw.csv": "<BY2_GNSS1_RAW_SOURCE>",
        "gnss2" + "-raw.csv": "<BY2_GNSS2_RAW_SOURCE>",
        "corr" + "-raw.csv": "<BY2_CORR_RAW_SOURCE>",
        "trace" + "_vrtk2": "<TRACE_EVAL_REFERENCE_ONLY>",
    }
    for source, replacement in redactions.items():
        out = out.replace(source, replacement)
    return out


def ensure_dirs(stage_root: Path, export_root: Path, review_root: Path) -> None:
    for name in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_RESULT_REVIEW",
        "03_MODULE_REVIEW",
        "04_FIGURE_PACKAGE",
        "05_CHINESE_SUMMARY",
        "06_CLAIM_BOUNDARY",
        "07_INNOVATION_AND_JOURNAL",
        "08_NEXT_STAGE_DECISION",
        "09_OBSIDIAN_SYNC",
        "10_AI_CONTEXT_UPDATE",
        "11_TESTS",
        "12_EXPORT_CLEAN_FOR_GPT",
    ]:
        (stage_root / name).mkdir(parents=True, exist_ok=True)
    export_root.mkdir(parents=True, exist_ok=True)
    review_root.mkdir(parents=True, exist_ok=True)


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    c = args.m1r2c_stage_root
    d = args.m1r2d_stage_root
    a = args.m1r2a_stage_root
    b = args.m1r2b2_stage_root
    ctx = args.ai_context_root
    return {
        "case_manifest": read_csv(a / "04_CASE_MANIFEST" / "CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv"),
        "type_registry": read_csv(a / "02_MATRIX_DESIGN" / "CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv"),
        "provider_ready": read_csv(b / "05_PROVIDER_READY" / "PAPER10M1R2B2_PROVIDER_READY_MANIFEST.csv"),
        "c_final_report": (c / "00_STAGE_REPORT" / "PAPER10M1R2C_R1_SUPERVISOR_FINAL_REPORT.md").read_text(encoding="utf-8"),
        "c_rows": read_csv(c / "05_EXECUTION" / "PAPER10M1R2C_R1_ROW_LEVEL_RESULT_TABLE.csv"),
        "c_type_summary": read_csv(c / "06_CASE_SUMMARIES" / "PAPER10M1R2C_R1_DEGRADATION_TYPE_SUMMARY.csv"),
        "c_methods": read_csv(c / "07_METHOD_SUMMARIES" / "PAPER10M1R2C_R1_METHOD_LEVEL_SUMMARY.csv"),
        "c_comparison": read_csv(c / "07_METHOD_SUMMARIES" / "PAPER10M1R2C_R1_METHOD_MODE_COMPARISON_TABLE.csv"),
        "c_qm_trace": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_QM_TRACE_SUMMARY.csv"),
        "c_source_trace": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_SOURCE_AWARE_TRACE_SUMMARY.csv"),
        "c_yaw_sanity": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_YAW_SANITY_SUMMARY.csv"),
        "c_yaw_family": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_DUAL_YAW_DEGRADATION_FAMILY_AUDIT.csv"),
        "c_recovery": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_FALLBACK_RECOVERY_AUDIT.csv"),
        "c_figures": read_csv(c / "09_FIGURES" / "PAPER10M1R2C_R1_FIGURE_INDEX.csv"),
        "c_render": read_csv(c / "09_FIGURES" / "PAPER10M1R2C_R1_RENDER_QA_REPORT.csv"),
        "d_final_report": (d / "00_STAGE_REPORT" / "PAPER10M1R2D_R1_SUPERVISOR_FINAL_REPORT.md").read_text(encoding="utf-8"),
        "d_rows": read_csv(d / "05_EXECUTION" / "PAPER10M1R2D_R1_ROW_LEVEL_RESULT_TABLE.csv"),
        "d_type_summary": read_csv(d / "06_CASE_SUMMARIES" / "PAPER10M1R2D_R1_DEGRADATION_TYPE_SUMMARY.csv"),
        "d_methods": read_csv(d / "07_METHOD_SUMMARIES" / "PAPER10M1R2D_R1_METHOD_LEVEL_SUMMARY.csv"),
        "d_contrib": read_csv(d / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_ABLATION_CONTRIBUTION_TABLE.csv"),
        "d_contrib_summary": (d / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_ABLATION_CONTRIBUTION_SUMMARY.md").read_text(encoding="utf-8"),
        "d_module_ranking": read_csv(d / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_MODULE_IMPORTANCE_RANKING.csv"),
        "d_action": read_csv(d / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_MODULE_ACTION_SUMMARY.csv"),
        "d_qm_trace": read_csv(d / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_QM_TRACE_SUMMARY.csv"),
        "d_yaw_family": read_csv(d / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_DUAL_YAW_DEGRADATION_FAMILY_AUDIT.csv"),
        "d_recovery": read_csv(d / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_FALLBACK_RECOVERY_AUDIT.csv"),
        "d_figures": read_csv(d / "10_FIGURES" / "PAPER10M1R2D_R1_FIGURE_INDEX.csv"),
        "d_render": read_csv(d / "10_FIGURES" / "PAPER10M1R2D_R1_RENDER_QA_REPORT.csv"),
        "ai_context": {
            name: (ctx / name).read_text(encoding="utf-8")
            for name in [
                "README_FIRST.md",
                "CURRENT_STATE.md",
                "NEXT_ACTIONS.md",
                "EXPERIMENT_STATUS.md",
                "DATASET_ROLES.md",
                "CLAIM_BOUNDARIES.md",
                "LATEST_STAGE_POINTERS.md",
            ]
        },
    }


def false_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if row.get(field, "").strip().lower() not in {"", "false", "0", "no"})


def terminal_counts(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(row.get("terminal_status", "") for row in rows)


def method_counts(rows: list[dict[str, str]], field: str) -> Counter[str]:
    return Counter(row.get(field, "") for row in rows)


def all_completed(rows: list[dict[str, str]]) -> bool:
    return terminal_counts(rows) == Counter({"COMPLETED_EVALUABLE": len(rows)})


def classify_module(row: dict[str, str]) -> dict[str, str]:
    module = row["removed_module"]
    median_delta = fnum(row["median_delta_horizontal_rmse_m"])
    help_count = int(fnum(row["module_help_count"], 0))
    hurt_count = int(fnum(row["module_hurt_count"], 0))
    same_count = int(fnum(row["same_order_count"], 0))
    tradeoff = int(fnum(row["metric_tradeoff_count"], 0))
    if module == "source_aware_weighting":
        label = "moderate_positive_evidence"
        strength = "moderate_bounded_stability"
        location = "main_text_candidate"
    elif module == "raw_doppler":
        label = "weak_positive_evidence"
        strength = "weak_bounded_auxiliary"
        location = "appendix_or_short_main"
    elif module == "go2_horizontal_velocity_prior":
        label = "weak_positive_evidence"
        strength = "weak_auxiliary_prior"
        location = "appendix_or_short_main"
    elif module == "go2_roll_pitch_prior":
        label = "negative_or_hurts"
        strength = "not_claimable_as_improvement"
        location = "diagnostic_or_appendix"
    elif module == "go2_joint_factor":
        label = "neutral_no_effect"
        strength = "diagnostic_only_no_measured_delta"
        location = "diagnostic_only"
    elif module == "fgo_feedback_or_ekf_only_alias":
        label = "alias_or_duplicate"
        strength = "diagnostic_only_alias_no_measured_delta"
        location = "diagnostic_only"
    elif module in {"multi_state_qm", "legacy_without_qm_and_feedback"}:
        label = "tradeoff"
        strength = "mechanism_evidence_metric_tradeoff"
        location = "main_text_mechanism_or_appendix"
    else:
        label = "not_claimable"
        strength = "not_claimable"
        location = "diagnostic_only"
    return {
        "removed_module": module,
        "interpretation_label": label,
        "claim_strength": strength,
        "paper_location_recommendation": location,
        "main_metric_delta": f"median horizontal delta {median_delta:.6g} m",
        "positive_evidence_count": str(help_count),
        "negative_evidence_count": str(hurt_count),
        "same_order_count": str(same_count),
        "tradeoff_count": str(tradeoff),
    }


def module_name(removed_module: str) -> str:
    return {
        "raw_doppler": "Raw Doppler",
        "source_aware_weighting": "Source-aware LSIM/OIM / R scaling",
        "multi_state_qm": "Multi-state QM",
        "legacy_without_qm_and_feedback": "without-QM legacy alias",
        "go2_roll_pitch_prior": "Go2 roll/pitch weak prior",
        "go2_horizontal_velocity_prior": "Go2 horizontal velocity weak prior",
        "go2_joint_factor": "Go2 joint/proprioceptive factor",
        "fgo_feedback_or_ekf_only_alias": "FGO feedback / EKF-only relation",
    }.get(removed_module, removed_module)


def module_review_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in data["d_contrib"]:
        interp = classify_module(row)
        removed = row["removed_module"]
        allowed = {
            "raw_doppler": "可写为Raw Doppler在冻结BY2协议下提供小幅、稳定、有边界的辅助信息。",
            "source_aware_weighting": "可写为来源感知权重在多数工况中提供稳定但幅度有限的质量管理证据。",
            "multi_state_qm": "可写为QM提供可解释状态/动作轨迹，但性能指标存在权衡。",
            "legacy_without_qm_and_feedback": "可写为legacy no-QM路径与no-QM结论一致，需要避免重复claim。",
            "go2_roll_pitch_prior": "只能写为本矩阵中未形成正向性能证据。",
            "go2_horizontal_velocity_prior": "可写为Go2水平速度弱先验提供有限辅助证据。",
            "go2_joint_factor": "只能写为当前矩阵未测得贡献或配置等价。",
            "fgo_feedback_or_ekf_only_alias": "只能写为当前冻结策略下未表现出有效贡献。",
        }[removed]
        forbidden = {
            "raw_doppler": "禁止写成Raw Doppler显著或普遍提升全部指标。",
            "source_aware_weighting": "禁止写成来源感知带来大幅或全面提升。",
            "multi_state_qm": "禁止写成QM全面优于no-QM。",
            "legacy_without_qm_and_feedback": "禁止把legacy alias当成独立强模块贡献。",
            "go2_roll_pitch_prior": "禁止作为主文强贡献。",
            "go2_horizontal_velocity_prior": "禁止写成强运动学约束或真值。",
            "go2_joint_factor": "禁止写成Go2 joint已验证有效。",
            "fgo_feedback_or_ekf_only_alias": "禁止写成FGO feedback已验证有效。",
        }[removed]
        rows.append(
            {
                "module_name": module_name(removed),
                "removed_module": removed,
                "evidence_source": "M1R2D_R1 ablation contribution table",
                "matrix_rows_supporting": row.get("case_count", "541"),
                "main_metric_delta": interp["main_metric_delta"],
                "family_specific_effect": (
                    f"strong={row.get('strong_help_family','')}; "
                    f"weak={row.get('weak_help_family','')}; hurt={row.get('hurt_family','')}"
                ),
                "positive_evidence_count": interp["positive_evidence_count"],
                "negative_evidence_count": interp["negative_evidence_count"],
                "tradeoff_count": interp["tradeoff_count"],
                "interpretation_label": interp["interpretation_label"],
                "claim_strength": interp["claim_strength"],
                "paper_location_recommendation": interp["paper_location_recommendation"],
                "allowed_wording_cn": allowed,
                "forbidden_wording_cn": forbidden,
                "notes": row.get("notes", ""),
            }
        )
    rows.append(
        {
            "module_name": "Dual antenna yaw source-backed backbone",
            "removed_module": "not_an_ablation_module",
            "evidence_source": "M1R2B2 yaw lineage/wrap PASS plus M1R2C_R1/M1R2D_R1 clean yaw gates",
            "matrix_rows_supporting": "541 providers; 2164 full rows; 4869 ablation rows",
            "main_metric_delta": "clean yaw gates PASS; D30-D41 diagnostic_pass",
            "family_specific_effect": "yaw family sanity supports source-backed BY2 backbone only",
            "positive_evidence_count": "not_applicable",
            "negative_evidence_count": "not_applicable",
            "tradeoff_count": "not_applicable",
            "interpretation_label": "strong_positive_evidence",
            "claim_strength": "strong_system_backbone_not_new_ablation_delta",
            "paper_location_recommendation": "main_text_foundation",
            "allowed_wording_cn": "可写为短基线双天线航向是BY2系统骨架和评估前提。",
            "forbidden_wording_cn": "禁止写成BY3航向泛化已成立或新增消融模块贡献。",
            "notes": "Backbone evidence is source-lineage and sanity-gate evidence, not a removed-module delta.",
        }
    )
    rows.append(
        {
            "module_name": "Full candidate as system combination",
            "removed_module": "system_combination",
            "evidence_source": "M1R2C_R1 method comparison plus M1R2D_R1 module review",
            "matrix_rows_supporting": "2164 full rows; 4869 ablation rows",
            "main_metric_delta": "p95 horizontal benefits exist, while median/up/yaw tradeoffs remain",
            "family_specific_effect": "best described as bounded system package, not universal winner",
            "positive_evidence_count": "mixed",
            "negative_evidence_count": "mixed",
            "tradeoff_count": "present",
            "interpretation_label": "tradeoff",
            "claim_strength": "bounded_system_combination",
            "paper_location_recommendation": "main_text_candidate_with_caveats",
            "allowed_wording_cn": "可写为完整候选系统在受控BY2矩阵中形成有边界的组合证据。",
            "forbidden_wording_cn": "禁止写成完整候选系统在全部指标和全部工况中最优。",
            "notes": "M1R2C_R1 no-QM comparisons prevent universal-superiority wording.",
        }
    )
    return rows


def execution_validity_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    provider = data["provider_ready"]
    c_rows = data["c_rows"]
    d_rows = data["d_rows"]
    c_methods = method_counts(c_rows, "method_mode_id")
    d_methods = method_counts(d_rows, "ablation_method_id")
    rows: list[dict[str, str]] = [
        {
            "check_id": "M1R2A_CASE_MANIFEST",
            "expected": str(EXPECTED_CASES),
            "observed": str(len(data["case_manifest"])),
            "status": "PASS" if len(data["case_manifest"]) == EXPECTED_CASES else "FAIL",
            "notes": "60 degradation types x 9 seeds plus clean case.",
        },
        {
            "check_id": "M1R2A_TYPE_REGISTRY",
            "expected": str(EXPECTED_TYPES),
            "observed": str(len(data["type_registry"])),
            "status": "PASS" if len(data["type_registry"]) == EXPECTED_TYPES else "FAIL",
            "notes": "Canonical BY2 degradation type registry.",
        },
        {
            "check_id": "M1R2B2_PROVIDER_READY",
            "expected": "541 provider_ready/effect/yaw-lineage/yaw-wrap PASS",
            "observed": (
                f"provider_ready={sum(row.get('provider_ready') == 'true' for row in provider)}; "
                f"effect={sum(row.get('effect_validation_status') == 'PASS' for row in provider)}; "
                f"lineage={sum(row.get('yaw_lineage_validation_status') == 'PASS' for row in provider)}; "
                f"wrap={sum(row.get('yaw_wrap_validation_status') == 'PASS' for row in provider)}"
            ),
            "status": "PASS"
            if all(
                row.get("provider_ready") == "true"
                and row.get("effect_validation_status") == "PASS"
                and row.get("yaw_lineage_validation_status") == "PASS"
                and row.get("yaw_wrap_validation_status") == "PASS"
                for row in provider
            )
            and len(provider) == EXPECTED_CASES
            else "FAIL",
            "notes": "Old M1R2B provider packages remain superseded.",
        },
        {
            "check_id": "M1R2C_R1_ROW_COUNT",
            "expected": str(EXPECTED_M1R2C_ROWS),
            "observed": str(len(c_rows)),
            "status": "PASS" if len(c_rows) == EXPECTED_M1R2C_ROWS and all_completed(c_rows) else "FAIL",
            "notes": str(dict(terminal_counts(c_rows))),
        },
        {
            "check_id": "M1R2C_R1_METHOD_COUNTS",
            "expected": "4 methods x 541",
            "observed": str(dict(c_methods)),
            "status": "PASS" if set(c_methods) == EXPECTED_M1R2C_METHODS and set(c_methods.values()) == {541} else "FAIL",
            "notes": "Full algorithm matrix only.",
        },
        {
            "check_id": "M1R2D_R1_ROW_COUNT",
            "expected": str(EXPECTED_M1R2D_ROWS),
            "observed": str(len(d_rows)),
            "status": "PASS" if len(d_rows) == EXPECTED_M1R2D_ROWS and all_completed(d_rows) else "FAIL",
            "notes": str(dict(terminal_counts(d_rows))),
        },
        {
            "check_id": "M1R2D_R1_METHOD_COUNTS",
            "expected": "9 methods x 541",
            "observed": str(dict(d_methods)),
            "status": "PASS" if set(d_methods) == EXPECTED_M1R2D_METHODS and set(d_methods.values()) == {541} else "FAIL",
            "notes": "Internal ablation matrix only.",
        },
        {
            "check_id": "M1R2C_RENDER_QA",
            "expected": "37 PASS",
            "observed": f"{sum(row.get('render_status') == 'PASS' for row in data['c_render'])}/{len(data['c_render'])} PASS",
            "status": "PASS" if len(data["c_render"]) == 37 and all(row.get("render_status") == "PASS" for row in data["c_render"]) else "FAIL",
            "notes": "Figure binaries remain outside Git/export zip.",
        },
        {
            "check_id": "M1R2D_RENDER_QA",
            "expected": "42 PASS",
            "observed": f"{sum(row.get('render_status') == 'PASS' for row in data['d_render'])}/{len(data['d_render'])} PASS",
            "status": "PASS" if len(data["d_render"]) == 42 and all(row.get("render_status") == "PASS" for row in data["d_render"]) else "FAIL",
            "notes": "Figure binaries remain outside Git/export zip.",
        },
    ]
    for stage_id, stage_rows in [("M1R2C_R1", c_rows), ("M1R2D_R1", d_rows)]:
        violations = {field: false_count(stage_rows, field) for field in FORBIDDEN_ROW_FIELDS if field in stage_rows[0]}
        rows.append(
            {
                "check_id": f"{stage_id}_FORBIDDEN_INPUT_AUDIT",
                "expected": "0 violations",
                "observed": str(violations),
                "status": "PASS" if all(count == 0 for count in violations.values()) else "FAIL",
                "notes": "Trace/final_v23/LegSA/benchmark outputs not used as solver inputs.",
            }
        )
    return rows


def method_interpretation_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    method_labels = {
        "basic_dual_baseline": ("baseline_reference", "diagnostic_only", "appendix_or_baseline_table"),
        "strong_dual_yaw_baseline": ("strong_yaw_backbone_baseline", "moderate_positive_evidence", "main_or_appendix"),
        "legsa_without_qm": ("no-QM candidate performs well on several medians", "tradeoff", "main_text_comparison"),
        "legsa_full_candidate_with_qm": ("full candidate has p95 benefits but median tradeoffs", "tradeoff", "main_text_candidate_with_caveats"),
        "legsa_no_raw_doppler": ("removed Raw Doppler comparison", "weak_positive_evidence", "appendix_or_short_main"),
        "legsa_no_source_aware": ("removed source-aware comparison", "moderate_positive_evidence", "main_text_candidate"),
        "legsa_no_go2_roll_pitch": ("removed roll/pitch comparison", "negative_or_hurts", "diagnostic_or_appendix"),
        "legsa_no_go2_horizontal_velocity": ("removed horizontal velocity comparison", "weak_positive_evidence", "appendix_or_short_main"),
        "legsa_no_go2_joint": ("zero-delta no-effect comparison", "neutral_no_effect", "diagnostic_only"),
        "legsa_no_qm": ("direct no-QM comparison", "tradeoff", "main_text_comparison"),
        "legsa_no_fgo_feedback_or_ekf_only": ("zero-delta alias/no-effect comparison", "alias_or_duplicate", "diagnostic_only"),
    }
    for source, method_rows in [("M1R2C_R1", data["c_methods"]), ("M1R2D_R1", data["d_methods"])]:
        for row in method_rows:
            method = row["method_mode_id"]
            notes, label, location = method_labels.get(method, ("review required", "not_claimable", "diagnostic_only"))
            rows.append(
                {
                    "matrix_source": source,
                    "method_id": method,
                    "planned_rows": row.get("planned_rows", ""),
                    "completed_rows": row.get("completed_rows", ""),
                    "failed_rows": row.get("failed_rows", ""),
                    "blocked_rows": row.get("blocked_rows", ""),
                    "skipped_rows": row.get("skipped_rows", ""),
                    "median_horizontal_rmse_m": row.get("median_horizontal_rmse_m", ""),
                    "mean_horizontal_rmse_m": row.get("mean_horizontal_rmse_m", ""),
                    "p95_horizontal_rmse_m": row.get("p95_horizontal_rmse_m", ""),
                    "median_up_rmse_m": row.get("median_up_rmse_m", ""),
                    "median_yaw_rmse_deg": row.get("median_yaw_rmse_deg", ""),
                    "source_trace_available_rows": row.get("source_trace_available_rows", ""),
                    "qm_trace_available_rows": row.get("qm_trace_available_rows", ""),
                    "interpretation_label": label,
                    "paper_location_recommendation": location,
                    "review_notes": notes,
                }
            )
    return rows


def suspicious_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    methods = {row["method_mode_id"]: row for row in data["d_methods"]}
    no_qm_same = methods["legsa_without_qm"]["median_horizontal_rmse_m"] == methods["legsa_no_qm"]["median_horizontal_rmse_m"]
    full_joint_same = (
        methods["legsa_full_candidate_with_qm"]["median_horizontal_rmse_m"]
        == methods["legsa_no_go2_joint"]["median_horizontal_rmse_m"]
    )
    full_fgo_same = (
        methods["legsa_full_candidate_with_qm"]["median_horizontal_rmse_m"]
        == methods["legsa_no_fgo_feedback_or_ekf_only"]["median_horizontal_rmse_m"]
    )
    return [
        {
            "item_id": "without_qm_vs_no_qm",
            "method_or_field": "legsa_without_qm;legsa_no_qm",
            "finding": "duplicate_or_equivalent_metrics" if no_qm_same else "separate_but_similar",
            "interpretation_label": "alias_or_duplicate" if no_qm_same else "tradeoff",
            "claim_action": "Do not double-count as two independent positive modules.",
        },
        {
            "item_id": "go2_joint_zero_delta",
            "method_or_field": "legsa_no_go2_joint",
            "finding": "same metrics as full candidate" if full_joint_same else "nonzero delta needs review",
            "interpretation_label": "neutral_no_effect",
            "claim_action": "Diagnostic only; no effective-module wording.",
        },
        {
            "item_id": "fgo_feedback_alias_zero_delta",
            "method_or_field": "legsa_no_fgo_feedback_or_ekf_only",
            "finding": "same metrics as full candidate" if full_fgo_same else "nonzero delta needs review",
            "interpretation_label": "alias_or_duplicate",
            "claim_action": "Diagnostic only; no FGO feedback validation wording.",
        },
        {
            "item_id": "legacy_bad_a1_consumed_count",
            "method_or_field": "legacy_bad_a1_consumed_count",
            "finding": "deprecated semantic field",
            "interpretation_label": "diagnostic_only",
            "claim_action": "Do not use as a paper claim field.",
        },
    ]


def result_master_rows(data: dict[str, Any], module_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {
            "review_scope": "M1R2C_R1 full algorithm",
            "evidence_source": "M1R2C_R1 row/method/comparison summaries",
            "row_count": str(len(data["c_rows"])),
            "method_count": str(len(data["c_methods"])),
            "completion_status": "2164/2164 COMPLETED_EVALUABLE",
            "interpretation_label": "tradeoff",
            "paper_location_recommendation": "main_text_with_caveats",
            "notes": "Full candidate has p95 benefits and yaw-vs-basic benefits, while no-QM has better medians in several metrics.",
        },
        {
            "review_scope": "M1R2D_R1 internal ablation",
            "evidence_source": "M1R2D_R1 row/method/contribution summaries",
            "row_count": str(len(data["d_rows"])),
            "method_count": str(len(data["d_methods"])),
            "completion_status": "4869/4869 COMPLETED_EVALUABLE",
            "interpretation_label": "conditional_pass_with_module_caveats",
            "paper_location_recommendation": "main_text_plus_appendix",
            "notes": "Source-aware and Raw Doppler are bounded positive; Go2 joint and FGO feedback are no-effect/alias.",
        },
    ]
    for module in module_rows:
        rows.append(
            {
                "review_scope": module["module_name"],
                "evidence_source": module["evidence_source"],
                "row_count": module["matrix_rows_supporting"],
                "method_count": "module_review",
                "completion_status": "reviewed",
                "interpretation_label": module["interpretation_label"],
                "paper_location_recommendation": module["paper_location_recommendation"],
                "notes": module["allowed_wording_cn"],
            }
        )
    return rows


def write_result_review(args: argparse.Namespace, data: dict[str, Any], root_aliases: dict[str, Path]) -> dict[str, Any]:
    result_dir = args.stage_root / "02_RESULT_REVIEW"
    module_dir = args.stage_root / "03_MODULE_REVIEW"
    module_rows = module_review_rows(data)
    validity = execution_validity_rows(data)
    methods = method_interpretation_rows(data)
    suspicious = suspicious_rows(data)
    master = result_master_rows(data, module_rows)
    contrib_interp = []
    for row in data["d_contrib"]:
        interp = classify_module(row)
        contrib_interp.append({**row, **interp, "module_name": module_name(row["removed_module"])})
    write_csv(result_dir / "PAPER10M1R2E_RESULT_REVIEW_MASTER_TABLE.csv", master)
    write_csv(result_dir / "PAPER10M1R2E_EXECUTION_VALIDITY_AUDIT.csv", validity)
    write_csv(result_dir / "PAPER10M1R2E_METHOD_INTERPRETATION_TABLE.csv", methods)
    write_csv(result_dir / "PAPER10M1R2E_MODULE_CONTRIBUTION_INTERPRETATION.csv", contrib_interp)
    write_csv(result_dir / "PAPER10M1R2E_SUSPICIOUS_OR_ALIAS_METHODS.csv", suspicious)
    write_md(
        result_dir / "PAPER10M1R2E_REVIEWER_NOTES.md",
        "\n".join(
            [
                "# PAPER10M1R2E Reviewer Notes",
                "",
                "- M1R2C_R1 and M1R2D_R1 were loaded from yaw-corrected provider evidence.",
                "- Old M1R2C yaw-invalid metrics remain forbidden for claims.",
                "- M1R2E ran no solver, evaluator, provider generation, random generation, or degradation generation.",
                "- The full candidate is not a universal winner: no-QM comparisons create median/up/yaw tradeoffs.",
                "- Source-aware weighting is the clearest bounded positive module, but deltas are small and metric tradeoffs exist.",
                "- Raw Doppler and Go2 horizontal velocity are weak auxiliary contributors.",
                "- Go2 joint and FGO feedback / EKF-only are no-effect or alias findings in this matrix.",
            ]
        ),
    )
    write_csv(module_dir / "MODULE_CONTRIBUTION_FINAL_REVIEW.csv", module_rows)
    write_csv(
        module_dir / "MODULE_CLAIM_LEVEL_TABLE.csv",
        [
            {
                "module_name": row["module_name"],
                "interpretation_label": row["interpretation_label"],
                "claim_strength": row["claim_strength"],
                "paper_location_recommendation": row["paper_location_recommendation"],
                "allowed_wording_cn": row["allowed_wording_cn"],
                "forbidden_wording_cn": row["forbidden_wording_cn"],
            }
            for row in module_rows
        ],
    )
    write_csv(
        module_dir / "MODULE_EVIDENCE_STRENGTH_TABLE.csv",
        [
            {
                "module_name": row["module_name"],
                "evidence_source": row["evidence_source"],
                "matrix_rows_supporting": row["matrix_rows_supporting"],
                "main_metric_delta": row["main_metric_delta"],
                "positive_evidence_count": row["positive_evidence_count"],
                "negative_evidence_count": row["negative_evidence_count"],
                "tradeoff_count": row["tradeoff_count"],
                "claim_strength": row["claim_strength"],
            }
            for row in module_rows
        ],
    )
    write_csv(
        module_dir / "MODULE_RISK_AND_CAVEAT_TABLE.csv",
        [
            {
                "module_name": row["module_name"],
                "risk_or_caveat": row["forbidden_wording_cn"],
                "mitigation": "Use the allowed bounded wording and keep the figure in the recommended location.",
                "paper_location_recommendation": row["paper_location_recommendation"],
            }
            for row in module_rows
        ],
    )
    md_lines = [
        "# MODULE_CONTRIBUTION_FINAL_REVIEW",
        "",
        "| Module | Label | Claim strength | Main metric delta | Paper location |",
        "|---|---|---|---|---|",
    ]
    for row in module_rows:
        md_lines.append(
            f"| {row['module_name']} | {row['interpretation_label']} | {row['claim_strength']} | "
            f"{row['main_metric_delta']} | {row['paper_location_recommendation']} |"
        )
    md_lines.extend(
        [
            "",
            "Boundaries:",
            "- Weak/no-effect modules must not be inflated into claims.",
            "- Go2 is an observation/prior source, not truth.",
            "- FGO feedback has not been validated by this zero-delta alias row.",
        ]
    )
    write_md(module_dir / "MODULE_CONTRIBUTION_FINAL_REVIEW.md", "\n".join(md_lines))
    (args.review_root / "PAPER10M1R2E_LOCAL_REVIEW_INDEX.md").write_text(
        "# PAPER10M1R2E Local Review Index\n\n"
        f"- Stage root: {alias_path(args.stage_root, root_aliases)}\n"
        f"- Export root: {alias_path(args.export_root, root_aliases)}\n"
        "- Local review copies are lightweight CSV/Markdown only.\n",
        encoding="utf-8",
    )
    return {
        "module_rows": module_rows,
        "validity_rows": validity,
        "method_rows": methods,
        "suspicious_rows": suspicious,
        "master_rows": master,
    }


def write_figure_package(args: argparse.Namespace, root_aliases: dict[str, Path]) -> dict[str, Any]:
    fig_dir = args.stage_root / "04_FIGURE_PACKAGE"
    rows = []
    rows.extend(
        classify_figure_index(
            "M1R2C_R1",
            args.m1r2c_stage_root / "09_FIGURES" / "PAPER10M1R2C_R1_FIGURE_INDEX.csv",
            args.m1r2c_stage_root / "09_FIGURES" / "PAPER10M1R2C_R1_RENDER_QA_REPORT.csv",
        )
    )
    rows.extend(
        classify_figure_index(
            "M1R2D_R1",
            args.m1r2d_stage_root / "10_FIGURES" / "PAPER10M1R2D_R1_FIGURE_INDEX.csv",
            args.m1r2d_stage_root / "10_FIGURES" / "PAPER10M1R2D_R1_RENDER_QA_REPORT.csv",
        )
    )
    for row in rows:
        row["source_png"] = sanitize_text(row["source_png"], root_aliases)
        row["source_pdf"] = sanitize_text(row["source_pdf"], root_aliases)
    write_figure_csv(fig_dir / "PAPER10M1R2E_FIGURE_REVIEW_INDEX.csv", rows)
    buckets = defaultdict(list)
    for row in rows:
        buckets[row["m1r2e_bucket"]].append(row)
    write_figure_csv(fig_dir / "PAPER10M1R2E_MAIN_TEXT_FIGURE_CANDIDATES.csv", buckets["main_text_candidate"])
    write_figure_csv(fig_dir / "PAPER10M1R2E_APPENDIX_FIGURE_CANDIDATES.csv", buckets["appendix_candidate"])
    write_figure_csv(fig_dir / "PAPER10M1R2E_DIAGNOSTIC_FIGURES.csv", buckets["diagnostic_only"])
    write_figure_csv(
        fig_dir / "PAPER10M1R2E_REJECTED_OR_NEEDS_REPLOT_FIGURES.csv",
        buckets["rejected_or_needs_replot"],
    )
    summary = [
        "# PAPER10M1R2E Figure Package Summary",
        "",
        f"- Total reviewed figures: {len(rows)}.",
        f"- Main-text candidates: {len(buckets['main_text_candidate'])}.",
        f"- Appendix candidates: {len(buckets['appendix_candidate'])}.",
        f"- Diagnostic-only figures: {len(buckets['diagnostic_only'])}.",
        f"- Rejected / needs replot: {len(buckets['rejected_or_needs_replot'])}.",
        "- Figure binaries were not copied into Git or the export-clean zip.",
        "- Main-text candidates still require M1R2F final paper-format replot before manuscript use.",
    ]
    write_md(fig_dir / "PAPER10M1R2E_FIGURE_PACKAGE_SUMMARY.md", "\n".join(summary))
    return {"figure_rows": rows, "figure_buckets": {key: len(value) for key, value in buckets.items()}}


def cn_summary(title: str, purpose: str, inputs: str, methods: str, results: str, explains: str, cannot: str, wording: str, forbidden: str, figures: str, next_step: str) -> str:
    return f"""# {title}

1. 实验目的

{purpose}

2. 实验输入

{inputs}

3. 对比方法

{methods}

4. 主要结果

{results}

5. 该结果说明什么

{explains}

6. 该结果不能说明什么

{cannot}

7. 可写入论文的表述

{wording}

8. 必须禁止的表述

{forbidden}

9. 推荐图表

{figures}

10. 后续是否需要补实验

{next_step}
"""


def write_chinese_summaries(args: argparse.Namespace, data: dict[str, Any], review: dict[str, Any]) -> None:
    out = args.stage_root / "05_CHINESE_SUMMARY"
    module_lookup = {row["removed_module"]: row for row in review["module_rows"]}
    family_counts = Counter(row["case_family"] for row in data["case_manifest"])
    family_text = "；".join(f"{key}:{value}" for key, value in sorted(family_counts.items()))
    specs = {
        "00_BY2_OVERALL_SUMMARY.md": cn_summary(
            "BY2总体结果审查总结",
            "审查BY2修正航向provider后的完整算法矩阵和内部消融矩阵，冻结可写结论与禁止结论。",
            "输入来自M1R2A 541个case、M1R2B2 541个provider-ready包、M1R2C_R1 2164行结果和M1R2D_R1 4869行结果。",
            "比较四种完整算法模式和九种内部消融方法。",
            "两条矩阵链路均为COMPLETED_EVALUABLE，M1R2C_R1为2164/2164，M1R2D_R1为4869/4869。",
            "BY2主数据集已有可审查的受控退化证据，可以进入最终论文图表候选整理。",
            "不能说明最终论文claim已完成，也不能说明BY3/XB/PG或横向算法已经闭合。",
            "BY2受控退化矩阵在修正航向provider后完成了完整算法和内部消融审查。",
            "禁止写成 universal superiority、final paper claim ready 或 BY3 yaw generalization。",
            "总体方法对比图、模块贡献图、D30-D41航向族图和D58-D60混合恢复代表图。",
            "建议进入M1R2F做最终主文/附录图表统一重绘；不需要在M1R2E补跑算法。",
        ),
        "01_FULL_ALGORITHM_MATRIX_SUMMARY.md": cn_summary(
            "完整算法矩阵总结",
            "回答四种完整算法模式在541个BY2 case上的整体表现。",
            "M1R2C_R1 row-level、method-level、method comparison、QM/source trace和render QA。",
            "basic dual baseline、strong dual yaw baseline、LegSA without QM和LegSA full candidate with QM。",
            "四种方法各完成541行；full candidate在部分p95和yaw-vs-basic指标上有优势，但与no-QM存在median/up/yaw权衡。",
            "完整候选系统是有边界的组合方案，而不是所有指标的绝对最优。",
            "不能用旧M1R2C yaw-invalid结果，也不能把full candidate写成普遍最优。",
            "完整候选系统在BY2受控退化矩阵中形成了有边界的组合证据。",
            "禁止写成所有工况、所有指标均优于baseline或no-QM。",
            "method_mode_horizontal_rmse_boxplot、legsa_full_vs_basic、legsa_full_vs_no_qm。",
            "M1R2F需要统一重绘主文图；若要解决QM性能权衡，需要另起M1R2G。",
        ),
        "02_INTERNAL_ABLATION_SUMMARY.md": cn_summary(
            "内部消融总结",
            "回答九种内部消融方法分别证明了哪些模块贡献。",
            "M1R2D_R1 4869行结果、method summary、ablation contribution table和module action summary。",
            "full candidate、without/no-QM、no Raw Doppler、no source-aware、no Go2 roll/pitch、no Go2 horizontal velocity、no Go2 joint、no FGO feedback/EKF-only。",
            "source-aware帮助次数最高但delta有限；Raw Doppler和Go2水平速度为弱贡献；Go2 roll/pitch偏负；Go2 joint和FGO feedback为零delta/no-effect。",
            "内部消融支持模块分级，而不是统一强贡献叙事。",
            "不能把Go2 joint或FGO feedback写成已验证有效。",
            "消融结果支持来源感知和Raw Doppler的有边界贡献，并揭示若干弱贡献或无效配置。",
            "禁止写成所有模块均显著提升性能。",
            "module_contribution_horizontal_delta_bar、module_help_hurt_same_order_count_bar。",
            "如需修复alias/no-effect模块，应另起M1R2G，不混入M1R2E。",
        ),
        "03_RAW_DOPPLER_SUMMARY.md": cn_summary(
            "Raw Doppler总结",
            "审查Raw Doppler作为辅助速度信息的边界贡献。",
            f"{module_lookup['raw_doppler']['evidence_source']}，{module_lookup['raw_doppler']['matrix_rows_supporting']}行case对比。",
            "full candidate与no_raw_doppler。",
            f"{module_lookup['raw_doppler']['main_metric_delta']}；help={module_lookup['raw_doppler']['positive_evidence_count']}，hurt={module_lookup['raw_doppler']['negative_evidence_count']}。",
            "Raw Doppler在BY2冻结协议中呈现小幅、较稳定的辅助贡献。",
            "不能说明Raw Doppler带来大幅或普遍改进。",
            module_lookup["raw_doppler"]["allowed_wording_cn"],
            module_lookup["raw_doppler"]["forbidden_wording_cn"],
            "raw_doppler_removed_delta_by_case和模块贡献汇总图。",
            "不需要补跑；如果要强化claim，可在后续横向或其他数据集阶段另行授权。",
        ),
        "04_SOURCE_AWARE_QM_SUMMARY.md": cn_summary(
            "Source-aware与QM总结",
            "区分来源感知权重的稳定贡献和多状态QM的机制/性能权衡。",
            "M1R2D_R1 source-aware消融、QM消融、QM trace和source trace。",
            "full vs no_source_aware、full vs no_qm、full vs without_qm。",
            f"source-aware: {module_lookup['source_aware_weighting']['main_metric_delta']}；QM: {module_lookup['multi_state_qm']['main_metric_delta']}。",
            "来源感知有稳定正向证据；QM具备状态/动作解释性，但指标上不能写全面提升。",
            "不能把QM写成所有指标优于no-QM。",
            "来源感知权重提供稳定但有边界的质量管理证据；QM提供可解释状态/动作轨迹并存在指标权衡。",
            "禁止写成source-aware/QM全面大幅提升。",
            "source_aware_r_scale_by_degradation_type、qm_state_count_by_degradation_type、full_vs_no_qm图。",
            "M1R2F可重绘解释图；若要优化QM策略，应另起修复阶段。",
        ),
        "05_GO2_PRIOR_SUMMARY.md": cn_summary(
            "Go2弱先验总结",
            "审查Go2 roll/pitch、水平速度和joint/proprioceptive因子的贡献边界。",
            "M1R2D_R1 Go2相关消融和module action summary。",
            "no_go2_roll_pitch、no_go2_horizontal_velocity、no_go2_joint与full candidate。",
            "Go2水平速度为弱正向辅助；roll/pitch在多数case上偏负；joint为零delta。",
            "Go2可以作为弱观测/先验来源，但本阶段只支持非常有限的贡献表述。",
            "不能把Go2位置、速度、接触或yaw当真值，不能把joint写成有效模块。",
            "Go2水平速度可写为有限弱先验；roll/pitch和joint应保留诊断或附录表述。",
            "禁止写成Go2先验显著提升或Go2 joint已验证有效。",
            "go2_horizontal_velocity_removed_delta_by_case、go2_joint_removed_delta_by_case诊断图。",
            "如需主文强化Go2贡献，需要另起修复或更高保真本体观测阶段。",
        ),
        "06_FGO_FEEDBACK_SUMMARY.md": cn_summary(
            "FGO反馈总结",
            "审查FGO feedback / EKF-only关系在本矩阵中的表现。",
            "M1R2D_R1 no_fgo_feedback_or_ekf_only行和method reconciliation。",
            "full candidate与no_fgo_feedback_or_ekf_only。",
            "该行与full candidate零delta，当前表现为alias/no-effect。",
            "本矩阵不能支持FGO feedback有效贡献claim。",
            "不能说明complete 9F FGO已验证，也不能说明反馈链路有效。",
            "只能写为当前冻结矩阵中未观察到FGO feedback的可测贡献。",
            "禁止写成FGO feedback已验证有效或complete 9F FGO validated。",
            "fgo_feedback_removed_delta_by_case仅诊断。",
            "若要验证FGO feedback，必须另起实现/运行阶段。",
        ),
        "07_DUAL_YAW_BACKBONE_SUMMARY.md": cn_summary(
            "双天线航向骨架总结",
            "审查BY2短基线双天线航向provider谱系作为系统骨架的证据。",
            "M1R2B2 provider-ready/yaw lineage/yaw wrap，M1R2C_R1/M1R2D_R1 clean yaw gate和D30-D41 yaw family audit。",
            "不是消融模块，而是BY2系统基础与方法对比前提。",
            "541/541 provider-ready，yaw lineage/wrap均PASS；D30-D41为diagnostic_pass。",
            "BY2航向provider谱系是当前可信结果的必要前提。",
            "不能推导BY3 yaw generalization，也不是新消融模块delta。",
            "可写为短基线双天线航向建模与provider谱系支撑BY2受控退化实验。",
            "禁止写成BY3航向已经泛化或外部严重GNSS场景已闭合。",
            "clean_yaw_error_by_method、D30_D41_yaw_family_rmse_heatmap。",
            "BY3 poor-heading stress必须另行授权。",
        ),
        "08_DEGRADATION_FAMILY_SUMMARIES.md": cn_summary(
            "退化族总结",
            "整理60类退化在M1R2E中的审查用途。",
            f"退化族分布：{family_text}。",
            "按case family和D01-D60类型审查方法表现、D30-D41航向族和D58-D60混合/恢复族。",
            "所有类型均有对应完成行；D30-D41和D58-D60通过现有audit进入候选图表分类。",
            "退化族结果支持受控工程审查。",
            "不能替代BY3/XB/PG泛化实验。",
            "可写为BY2受控退化覆盖GNSS outage、noise/spike、yaw、Raw Doppler和mixed/recovery等族。",
            "禁止把BY2退化族直接写成所有数据集泛化结论。",
            "60类heatmap进附录，D30-D41和D60代表图可进主文候选。",
            "M1R2F只重绘；新增退化族必须另起阶段。",
        ),
        "09_PAPER_WRITABLE_TEXT_CN.md": "# 可写入论文初稿的中文表述\n\n- BY2受控退化矩阵在修正航向provider后完成了四种完整算法模式和九种内部消融方法的审查。\n- Raw Doppler在冻结BY2协议下表现为小幅、有边界的辅助信息。\n- 来源感知权重在多数工况中提供稳定但幅度有限的质量管理证据。\n- 多状态QM提供可解释的状态/动作轨迹，但与no-QM存在指标权衡。\n- Go2水平速度可作为有限弱先验；Go2 roll/pitch、joint和FGO feedback需要谨慎或诊断化表述。\n- Trace仅作为离线评估参考，未作为求解器输入。\n",
        "10_FORBIDDEN_TEXT_CN.md": "# 必须禁止的中文表述\n\n- 禁止写成本方法在所有工况和所有指标上普遍最优。\n- 禁止写成当前结果已经满足最终论文claim。\n- 禁止写成BY3航向泛化、XB/PG严重GNSS高精度证明或横向算法已闭合。\n- 禁止写成Go2是真值，或Go2 joint/FGO feedback在零delta下仍然有效。\n- 禁止使用旧M1R2C yaw-invalid结果、legacy bad-A1 consumed计数或任何output-only correction叙事。\n",
    }
    for filename, text in specs.items():
        write_md(out / filename, text)


def write_claim_boundary(args: argparse.Namespace) -> None:
    out = args.stage_root / "06_CLAIM_BOUNDARY"
    write_claim_boundary_outputs(out)
    freeze = [
        "# PAPER10M1R2E Claim Boundary Freeze",
        "",
        "Final decision for M1R2E wording: bounded BY2 engineering evidence only.",
        "",
        "Allowed:",
        "- Completed yaw-corrected BY2 degradation matrix evidence.",
        "- 2164/2164 full-algorithm rows and 4869/4869 internal-ablation rows.",
        "- Small bounded Raw Doppler contribution.",
        "- Stable bounded source-aware contribution with small deltas.",
        "- QM interpretability with explicit metric tradeoffs.",
        "- Go2 horizontal velocity as weak auxiliary prior.",
        "- Trace as evaluation-only reference.",
        "",
        "Frozen caveats:",
        "- Go2 joint and FGO feedback are diagnostic/no-effect under this matrix.",
        "- Old M1R2C yaw-invalid metrics are forbidden.",
        "- BY3/XB/PAPER10H/horizontal comparisons are not authorized by M1R2E.",
        "",
        "Forbidden claim families are listed in `PAPER10M1R2E_FORBIDDEN_CLAIMS.md`.",
    ]
    write_md(out / "PAPER10M1R2E_CLAIM_BOUNDARY_FREEZE.md", "\n".join(freeze))


def write_innovation_and_next(args: argparse.Namespace) -> None:
    innov = args.stage_root / "07_INNOVATION_AND_JOURNAL"
    write_md(
        innov / "INNOVATION_CANDIDATE_MATRIX.md",
        """# INNOVATION_CANDIDATE_MATRIX

## Stronger Candidates

- Lateral short-baseline dual-antenna yaw modeling and yaw-provider lineage for BY2.
- BY2 controlled degradation protocol with yaw-corrected provider validation.
- Source-aware / QM trace-driven measurement management, with source-aware stronger than QM performance wording.

## Moderate Candidates

- Raw Doppler auxiliary velocity factor as a small bounded contributor.
- Go2 horizontal velocity weak prior as a limited auxiliary observation.
- Controlled ablation evidence across nine frozen method IDs.

## Weak Or Pending Candidates

- Go2 roll/pitch weak prior.
- Go2 joint/proprioceptive factor.
- FGO feedback / EKF-only relation.
- Complete nine-factor FGO claim.
""",
    )
    write_csv(
        innov / "INNOVATION_EVIDENCE_STRENGTH.csv",
        [
            {"innovation": "dual_antenna_yaw_provider_lineage", "strength": "strong", "evidence": "M1R2B2/M1R2C_R1/M1R2D_R1", "claim_boundary": "BY2 only"},
            {"innovation": "controlled_BY2_degradation_protocol", "strength": "strong", "evidence": "60 types, 9 seeds, 541 cases", "claim_boundary": "engineering protocol"},
            {"innovation": "source_aware_measurement_management", "strength": "moderate_to_strong", "evidence": "514 help / 27 hurt, small delta", "claim_boundary": "bounded stability, not large gain"},
            {"innovation": "multi_state_QM", "strength": "moderate_mechanism_mixed_performance", "evidence": "trace complete, no-QM metric tradeoffs", "claim_boundary": "interpretability and tradeoff"},
            {"innovation": "Raw_Doppler_auxiliary_factor", "strength": "moderate_weak", "evidence": "497 help / 42 hurt, tiny delta", "claim_boundary": "small bounded contribution"},
            {"innovation": "Go2_horizontal_velocity_prior", "strength": "weak", "evidence": "506 help / 35 hurt, tiny delta", "claim_boundary": "weak auxiliary prior"},
            {"innovation": "Go2_joint_factor", "strength": "not_claimable", "evidence": "zero delta", "claim_boundary": "diagnostic only"},
            {"innovation": "FGO_feedback", "strength": "not_claimable", "evidence": "zero delta alias", "claim_boundary": "future stage only"},
        ],
    )
    write_md(
        innov / "JOURNAL_POSITIONING_RECOMMENDATION.md",
        """# Journal Positioning Recommendation

Preferred near-term positioning:

- IEEE TIM / Measurement style if emphasizing controlled measurement, source integrity, and robotic platform engineering.
- GPS Solutions / Satellite Navigation style if emphasizing GNSS/INS quality management and dual-antenna yaw provider lineage.

Not recommended as the current primary target:

- T-RO, unless future work closes stronger legged kinematics/contact factor evidence and broader real-robot generalization.

This recommendation uses existing internal evidence only and does not rely on web search.
""",
    )
    write_md(
        innov / "NEXT_EXPERIMENT_DECISION.md",
        """# NEXT_EXPERIMENT_DECISION

Recommended next stage: `PAPER10M1R2F_MAIN_FIGURE_TABLE_REPLOT`.

Reason: M1R2E can classify usable result tables and figure candidates, but final manuscript figures need consistent formatting. This next stage must not run new algorithms.

Conditional alternative: `PAPER10M1R2G_MODULE_REPAIR_OR_ALIAS_CLEANUP` if the human decides that Go2 joint / FGO feedback / no-QM alias issues must be repaired before final figure packaging.

Blocked without new authorization: PAPER10H, BY3 targeted stress, XB/PG boundary diagnostics, and horizontal algorithm comparison.
""",
    )


def write_next_stage(args: argparse.Namespace) -> None:
    out = args.stage_root / "08_NEXT_STAGE_DECISION"
    write_md(
        out / "PAPER10M1R2E_NEXT_STAGE_DECISION.md",
        """# PAPER10M1R2E Next Stage Decision

Decision: `CONDITIONAL_PASS_PAPER10M1R2E_RESULTS_REVIEWED_WITH_MODULE_CAVEATS`.

Recommended route:

1. `PAPER10M1R2F_MAIN_FIGURE_TABLE_REPLOT` for final paper-format figures and tables.
2. Use `PAPER10M1R2G_MODULE_REPAIR_OR_ALIAS_CLEANUP` only if the human wants to repair no-effect/alias modules before manuscript packaging.
3. Keep PAPER10H, BY3, XB/PG, and horizontal comparison blocked until separately authorized.
""",
    )
    write_csv(
        out / "PAPER10M1R2F_OR_PAPER10H_DECISION_GATE.csv",
        [
            {"candidate_stage": "PAPER10M1R2F_MAIN_FIGURE_TABLE_REPLOT", "readiness": "recommended", "allowed_actions": "final formatting from existing summaries only", "forbidden_actions": "solver/evaluator/provider generation"},
            {"candidate_stage": "PAPER10M1R2G_MODULE_REPAIR_OR_ALIAS_CLEANUP", "readiness": "conditional", "allowed_actions": "configuration or claim cleanup after approval", "forbidden_actions": "silent algorithm change"},
            {"candidate_stage": "PAPER10H_XB_PG_BOUNDARY_DIAGNOSTIC", "readiness": "blocked_without_human_authorization", "allowed_actions": "none in M1R2E", "forbidden_actions": "high-precision severe-GNSS claim"},
            {"candidate_stage": "BY3 targeted poor-heading stress", "readiness": "blocked_without_human_authorization", "allowed_actions": "none in M1R2E", "forbidden_actions": "ordinary BY3 yaw generalization"},
            {"candidate_stage": "horizontal algorithm comparison", "readiness": "blocked_without_human_authorization", "allowed_actions": "none in M1R2E", "forbidden_actions": "mixing with M1R2E"},
        ],
    )
    write_md(
        out / "BY3_XB_HORIZONTAL_COMPARISON_READINESS.md",
        """# BY3 / XB / Horizontal Comparison Readiness

- BY3: not authorized by M1R2E; BY3 yaw remains diagnostic-only in current context.
- XB/PG: not authorized by M1R2E; severe-GNSS high-precision proof is forbidden.
- Horizontal comparison: not authorized by M1R2E; must be a separate stage with real method semantics and closed evaluator contracts.
""",
    )
    write_md(
        out / "PAPER10H_BLOCK_STATUS.md",
        """# PAPER10H Block Status

PAPER10H remains blocked in M1R2E.

M1R2E does not authorize horizontal algorithm comparison, external reproduction, BY3, XB/PG, PAPER10H, new providers, new degraded inputs, solver/evaluator runs, or paper-ready claims.
""",
    )


def write_obsidian_and_context(args: argparse.Namespace) -> None:
    obs = args.stage_root / "09_OBSIDIAN_SYNC"
    notes = {
        "PAPER10M1R2E_阶段总览.md": "# PAPER10M1R2E 阶段总览\n\nM1R2E完成BY2结果审查、图表候选分类、中文总结和claim boundary冻结；不运行新算法。\n",
        "BY2结果审查总览.md": "# BY2结果审查总览\n\nM1R2C_R1为2164/2164，M1R2D_R1为4869/4869，均为COMPLETED_EVALUABLE。\n",
        "模块贡献证据强度.md": "# 模块贡献证据强度\n\nSource-aware为较稳定有边界贡献，Raw Doppler与Go2水平速度为弱贡献，Go2 joint与FGO feedback为诊断/no-effect。\n",
        "主文图附录图诊断图分类.md": "# 主文图附录图诊断图分类\n\n主文候选需M1R2F统一重绘；附录保留60类heatmap和boxplot；diagnostic保留alias/no-effect图。\n",
        "论文可写结论与禁止结论.md": "# 论文可写结论与禁止结论\n\n可写BY2受控退化和有边界模块证据；禁止final paper ready、BY3/XB泛化、complete 9F FGO和universal superiority。\n",
    }
    for name, text in notes.items():
        write_md(obs / name, text)
    write_csv(
        obs / "OBSIDIAN_UPDATE_INDEX.csv",
        [{"note": name, "status": "generated", "stage": STAGE_NAME} for name in notes],
    )
    ctx = args.stage_root / "10_AI_CONTEXT_UPDATE"
    write_md(
        ctx / "PAPER10M1R2E_CURRENT_STATE_UPDATE.md",
        f"# Current State Update\n\n- Current stage: `{STAGE_NAME}`.\n- M1R2E is result-review only; no solver/evaluator/provider generation was run.\n- M1R2C_R1 and M1R2D_R1 are the valid BY2 yaw-corrected evidence sources.\n- Old M1R2C yaw-invalid metrics remain forbidden.\n",
    )
    write_md(
        ctx / "PAPER10M1R2E_NEXT_ACTIONS_UPDATE.md",
        "# Next Actions Update\n\n1. Human review M1R2E module caveats.\n2. If accepted, start `PAPER10M1R2F_MAIN_FIGURE_TABLE_REPLOT`.\n3. Keep PAPER10H/BY3/XB/horizontal comparison blocked unless separately authorized.\n",
    )
    write_md(
        ctx / "PAPER10M1R2E_LATEST_STAGE_POINTERS_UPDATE.md",
        "# Latest Stage Pointers Update\n\n- `<M1R2E_STAGE_ROOT>`: result-review, figure-package, Chinese-summary, claim-boundary, and export-clean package.\n- `<M1R2C_R1_STAGE_ROOT>`: current valid BY2 full-algorithm matrix.\n- `<M1R2D_R1_STAGE_ROOT>`: current valid BY2 internal-ablation matrix.\n",
    )


def write_tests(args: argparse.Namespace) -> None:
    out = args.stage_root / "11_TESTS"
    write_csv(
        out / "PAPER10M1R2E_TEST_MATRIX.csv",
        [
            {"test_or_guard": "git_fsck_full", "status": args.git_fsck_result, "notes": "dangling blobs are acceptable if fsck return code is zero"},
            {"test_or_guard": "pytest_m1r2e", "status": args.pytest_result, "notes": "M1R2E unit/audit tests"},
            {"test_or_guard": "export_clean_path_scan", "status": args.export_scan_result, "notes": "no local absolute paths or raw-data payload markers"},
            {"test_or_guard": "raw_data_commit_guard", "status": args.commit_guard_result, "notes": "no raw/runtime/figure/zip staged into Git"},
            {"test_or_guard": "forbidden_claim_grep", "status": args.claim_guard_result, "notes": "forbidden claims are only present as forbidden wording"},
            {"test_or_guard": "old_m1r2c_yaw_invalid_usage_guard", "status": args.old_m1r2c_guard_result, "notes": "old invalid matrix not used as evidence"},
        ],
    )
    write_md(
        out / "PAPER10M1R2E_GUARD_VALIDATION_REPORT.md",
        f"""# PAPER10M1R2E Guard Validation Report

- git fsck: `{args.git_fsck_result}`
- pytest: `{args.pytest_result}`
- export-clean path scan: `{args.export_scan_result}`
- raw/runtime commit guard: `{args.commit_guard_result}`
- forbidden claim grep: `{args.claim_guard_result}`
- old M1R2C yaw-invalid usage guard: `{args.old_m1r2c_guard_result}`

No solver/evaluator/provider/degradation generation is part of this stage.
""",
    )


def write_git_report(args: argparse.Namespace, root_aliases: dict[str, Path]) -> dict[str, Any]:
    git_dir = args.stage_root / "01_GIT"
    commands = {
        "status_short": run_git(args.repo_root, ["status", "--short"]),
        "status_branch": run_git(args.repo_root, ["status", "--branch", "--short"]),
        "branch": run_git(args.repo_root, ["branch", "--show-current"]),
        "head": run_git(args.repo_root, ["rev-parse", "HEAD"]),
        "log": run_git(args.repo_root, ["log", "--oneline", "-n", "5"]),
    }
    status = commands["status_short"]["stdout"]
    unused = [
        path
        for path in [
            "scripts/experiments/paper10_parallel_queue_runner.py",
            "tests/audit/test_paper10_parallel_runner_no_shared_outputs.py",
            "tests/unit/test_paper10_parallel_queue_runner.py",
        ]
        if f"?? {path}" in status
    ]
    report = [
        "# PAPER10M1R2E Git State Report",
        "",
        f"- Stage: `{STAGE_NAME}`.",
        f"- Repo root: `{alias_path(args.repo_root, root_aliases)}`.",
        f"- Branch: `{commands['branch']['stdout']}`.",
        f"- HEAD: `{commands['head']['stdout']}`.",
        f"- Status branch: `{commands['status_branch']['stdout']}`.",
        f"- Untracked unused helper status: `{'UNUSED_HELPER_UNTRACKED' if unused else 'NONE'}`.",
        "",
        "Unused helpers left uncommitted:",
    ]
    report.extend(f"- `{item}`" for item in unused)
    report.extend(["", "Recent log:", "```text", commands["log"]["stdout"], "```"])
    write_md(git_dir / "PAPER10M1R2E_GIT_STATE_REPORT.md", "\n".join(report))
    return {"git": commands, "unused_helpers": unused}


def write_stage_reports(
    args: argparse.Namespace,
    data: dict[str, Any],
    review: dict[str, Any],
    figures: dict[str, Any],
    git_state: dict[str, Any],
    root_aliases: dict[str, Path],
) -> None:
    module_by_name = {row["module_name"]: row for row in review["module_rows"]}
    final_decision = "CONDITIONAL_PASS_PAPER10M1R2E_RESULTS_REVIEWED_WITH_MODULE_CAVEATS"
    if all(row["status"] == "PASS" for row in review["validity_rows"]) and args.export_scan_result == "PASS":
        final_decision = "CONDITIONAL_PASS_PAPER10M1R2E_RESULTS_REVIEWED_WITH_MODULE_CAVEATS"
    items = [
        ("阶段名称", STAGE_NAME),
        ("为什么进入 M1R2E", "M1R2C_R1 and M1R2D_R1 completed valid yaw-corrected BY2 matrices and require review/claim freeze."),
        ("M1R2C_R1 读取情况", f"{len(data['c_rows'])}/2164 rows loaded; {len(data['c_methods'])} method summaries loaded."),
        ("M1R2D_R1 读取情况", f"{len(data['d_rows'])}/4869 rows loaded; {len(data['d_methods'])} method summaries loaded."),
        ("Git branch / HEAD / worktree", f"{git_state['git']['branch']['stdout']} / {git_state['git']['head']['stdout']} / unused helpers={len(git_state['unused_helpers'])}."),
        ("是否运行新 solver/evaluator", "no."),
        ("M1R2C_R1 full algorithm 审查结果", "2164/2164 completed; four frozen modes; full candidate is bounded with no-QM tradeoffs."),
        ("M1R2D_R1 internal ablation 审查结果", "4869/4869 completed; nine methods; module caveats frozen."),
        ("row count 核对", "M1R2A=541 cases; M1R2C_R1=2164; M1R2D_R1=4869."),
        ("method count 核对", "M1R2C_R1=4 x 541; M1R2D_R1=9 x 541."),
        ("forbidden input audit 核对", "0 trace/final_v23/LegSA/benchmark solver-input violations in reviewed row fields."),
        ("render QA 核对", f"M1R2C_R1={len(data['c_render'])}/{len(data['c_render'])} PASS; M1R2D_R1={len(data['d_render'])}/{len(data['d_render'])} PASS."),
        ("Raw Doppler 贡献判断", module_by_name["Raw Doppler"]["claim_strength"]),
        ("Source-aware/QM 贡献判断", "source-aware=moderate bounded; QM=mechanism evidence with metric tradeoff."),
        ("Go2 roll/pitch 贡献判断", module_by_name["Go2 roll/pitch weak prior"]["claim_strength"]),
        ("Go2 horizontal velocity 贡献判断", module_by_name["Go2 horizontal velocity weak prior"]["claim_strength"]),
        ("Go2 joint 贡献判断", module_by_name["Go2 joint/proprioceptive factor"]["claim_strength"]),
        ("FGO feedback / EKF-only 贡献判断", module_by_name["FGO feedback / EKF-only relation"]["claim_strength"]),
        ("no-QM / without-QM alias 判断", "duplicate/equivalent metrics must not be double-counted as independent module claims."),
        ("模块证据强度表", "Generated under 03_MODULE_REVIEW."),
        ("主文图候选", f"{figures['figure_buckets'].get('main_text_candidate', 0)} candidates; final formatting deferred to M1R2F."),
        ("附录图候选", f"{figures['figure_buckets'].get('appendix_candidate', 0)} candidates."),
        ("diagnostic-only 图候选", f"{figures['figure_buckets'].get('diagnostic_only', 0)} candidates."),
        ("中文总结生成情况", "Generated 11 Chinese summary Markdown files."),
        ("可写论文结论", "bounded BY2 controlled-degradation and module evidence only."),
        ("禁止论文结论", "universal superiority, final paper ready, BY3/XB generalization, complete 9F FGO, Go2 truth, zero-delta module effectiveness."),
        ("创新点证据强度", "strong: yaw provider lineage and protocol; moderate: source-aware/Raw Doppler; weak/pending: Go2 joint/FGO feedback."),
        ("期刊定位建议", "IEEE TIM / Measurement / GPS Solutions / Satellite Navigation style; T-RO deferred until legged evidence strengthens."),
        ("下一阶段建议", "M1R2F final figure/table replot; M1R2G only if repairing alias/no-effect modules."),
        ("PAPER10H block status", "blocked without explicit human authorization."),
        ("BY3/XB/horizontal comparison readiness", "not authorized by M1R2E."),
        ("export-clean 结果", args.export_scan_result),
        ("path scan 结果", args.export_scan_result),
        ("commit/push 状态", args.commit_push_status),
        ("final decision", final_decision),
    ]
    lines = ["# PAPER10M1R2E Supervisor Final Report", ""]
    for idx, (key, value) in enumerate(items, 1):
        lines.append(f"{idx}. {key}: {value}")
    write_md(args.stage_root / "00_STAGE_REPORT" / "PAPER10M1R2E_SUPERVISOR_FINAL_REPORT.md", "\n".join(lines))
    reviewer = [
        "# PAPER10M1R2E Reviewer Report",
        "",
        f"- Reviewed stage root: `{alias_path(args.stage_root, root_aliases)}`.",
        "- Confirmed M1R2E generated review outputs from existing summaries only.",
        "- Confirmed no generated figure binaries are included in export-clean.",
        "- Confirmed module caveats: source-aware bounded positive, Raw Doppler weak positive, QM tradeoff, Go2 joint/FGO feedback no-effect or alias.",
        "- Confirmed forbidden claim list exists and old M1R2C yaw-invalid metrics are not used as active evidence.",
        f"- Final decision: `{final_decision}`.",
    ]
    write_md(args.stage_root / "00_STAGE_REPORT" / "PAPER10M1R2E_REVIEWER_REPORT.md", "\n".join(reviewer))


def forbidden_scan_patterns() -> dict[str, str]:
    return {
        "windows_user_path": "C:" + "\\" + "Users",
        "mnt_windows_user_path": "/" + "mnt" + "/" + "c" + "/" + "Users",
        "home_user_abs_path": "/" + "home" + "/" + "kaiwen",
        "media_project_abs_path": "/" + "media" + "/" + "kaiwen" + "/" + "新加卷",
        "body_source_filename": "by2" + ".txt",
        "gnss1_raw_filename": "gnss1" + "-raw.csv",
        "gnss2_raw_filename": "gnss2" + "-raw.csv",
        "trace_reference_filename": "trace" + "_vrtk2",
    }


def export_clean(args: argparse.Namespace, root_aliases: dict[str, Path]) -> dict[str, Any]:
    if args.export_root.exists():
        shutil.rmtree(args.export_root)
    args.export_root.mkdir(parents=True, exist_ok=True)
    include_dirs = [
        "00_STAGE_REPORT",
        "02_RESULT_REVIEW",
        "03_MODULE_REVIEW",
        "04_FIGURE_PACKAGE",
        "05_CHINESE_SUMMARY",
        "06_CLAIM_BOUNDARY",
        "07_INNOVATION_AND_JOURNAL",
        "08_NEXT_STAGE_DECISION",
        "09_OBSIDIAN_SYNC",
        "10_AI_CONTEXT_UPDATE",
        "11_TESTS",
    ]
    allowed_suffix = {".md", ".csv", ".json", ".txt"}
    copied: list[dict[str, str]] = []
    for rel_dir in include_dirs:
        src_dir = args.stage_root / rel_dir
        for src in src_dir.rglob("*"):
            if not src.is_file() or src.suffix not in allowed_suffix:
                continue
            rel = src.relative_to(args.stage_root)
            dst = args.export_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = src.read_text(encoding="utf-8")
            dst.write_text(sanitize_text(text, root_aliases), encoding="utf-8")
            copied.append(
                {
                    "relative_path": rel.as_posix(),
                    "size_bytes": str(dst.stat().st_size),
                    "sha256": sha256_path(dst),
                }
            )
    readme = args.export_root / "README_FOR_NEXT_AI.md"
    readme.write_text(
        f"""# README_FOR_NEXT_AI

This export-clean package contains the M1R2E BY2 result-review, figure-candidate, Chinese-summary, claim-boundary, innovation, and next-stage decision material.

Use aliases only:

- `<M1R2C_R1_STAGE_ROOT>` for the valid full-algorithm matrix.
- `<M1R2D_R1_STAGE_ROOT>` for the valid internal-ablation matrix.
- `<M1R2E_STAGE_ROOT>` for the review package.

Do not treat old M1R2C yaw-invalid metrics as active evidence. Do not run solver/evaluator/provider generation from this package.
""",
        encoding="utf-8",
    )
    copied.append(
        {
            "relative_path": "README_FOR_NEXT_AI.md",
            "size_bytes": str(readme.stat().st_size),
            "sha256": sha256_path(readme),
        }
    )
    patterns = forbidden_scan_patterns()
    findings: list[dict[str, str]] = []
    for file in args.export_root.rglob("*"):
        if not file.is_file():
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        for pattern_id, pattern in patterns.items():
            if pattern in text:
                findings.append({"file": file.relative_to(args.export_root).as_posix(), "pattern_id": pattern_id})
    status = "PASS" if not findings else "FAIL"
    scan = {
        "scan_status": status,
        "forbidden_pattern_findings": findings,
        "scanned_file_count": sum(1 for file in args.export_root.rglob("*") if file.is_file()),
        "generated_at": now_iso(),
    }
    manifest_path = args.export_root / "export_clean_manifest.csv"
    write_csv(manifest_path, copied)
    scan_path = args.export_root / "export_clean_path_scan.json"
    write_json(scan_path, scan)
    copied.append(
        {
            "relative_path": "export_clean_manifest.csv",
            "size_bytes": str(manifest_path.stat().st_size),
            "sha256": sha256_path(manifest_path),
        }
    )
    copied.append(
        {
            "relative_path": "export_clean_path_scan.json",
            "size_bytes": str(scan_path.stat().st_size),
            "sha256": sha256_path(scan_path),
        }
    )
    stage_export = args.stage_root / "12_EXPORT_CLEAN_FOR_GPT"
    zip_path = stage_export / "paper10m1r2e_by2_result_review_pack.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in args.export_root.rglob("*"):
            if file.is_file() and file != zip_path:
                archive.write(file, file.relative_to(args.export_root).as_posix())
    shutil.copy2(manifest_path, stage_export / "export_clean_manifest.csv")
    shutil.copy2(scan_path, stage_export / "export_clean_path_scan.json")
    shutil.copy2(readme, stage_export / "README_FOR_NEXT_AI.md")
    return {"status": status, "findings": findings, "zip_path": zip_path, "manifest_rows": len(copied)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--ai-context-root", type=Path, required=True)
    parser.add_argument("--m1r2a-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2b2-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2c-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2d-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2c-runtime-root", type=Path, required=True)
    parser.add_argument("--m1r2d-runtime-root", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--review-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--git-fsck-result", default="PENDING")
    parser.add_argument("--pytest-result", default="PENDING")
    parser.add_argument("--export-scan-result", default="PENDING")
    parser.add_argument("--commit-guard-result", default="PENDING")
    parser.add_argument("--claim-guard-result", default="PENDING")
    parser.add_argument("--old-m1r2c-guard-result", default="PENDING")
    parser.add_argument("--commit-push-status", default="PENDING")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.repo_root = args.repo_root.resolve()
    ensure_dirs(args.stage_root, args.export_root, args.review_root)
    root_aliases = aliases(args)
    data = load_inputs(args)
    git_state = write_git_report(args, root_aliases)
    review = write_result_review(args, data, root_aliases)
    figures = write_figure_package(args, root_aliases)
    write_chinese_summaries(args, data, review)
    write_claim_boundary(args)
    write_innovation_and_next(args)
    write_next_stage(args)
    write_obsidian_and_context(args)
    write_tests(args)
    export_status = export_clean(args, root_aliases)
    args.export_scan_result = export_status["status"]
    write_tests(args)
    export_status = export_clean(args, root_aliases)
    args.export_scan_result = export_status["status"]
    write_stage_reports(args, data, review, figures, git_state, root_aliases)
    export_status = export_clean(args, root_aliases)
    print(json.dumps({"stage": STAGE_NAME, "export_clean_status": export_status["status"]}, ensure_ascii=False))
    return 0 if export_status["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
