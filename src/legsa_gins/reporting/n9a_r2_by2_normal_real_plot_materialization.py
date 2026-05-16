"""N9A R2 BY2 normal real plot materialization.

This stage fixes the N9A_R1 boundary: source lineage evidence is useful, but it
does not make BY2 normal algorithm-result plots complete unless real algorithm
NAV/EVAL/STD runtime outputs are found first.

中文说明：本模块先发现真实算法输出，再判断 BY2 正常工况绘图是否完成。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, safe_float, write_json
from legsa_gins.reporting.n9a_r1_by2_source_aligned_normal import CASE_NAME, R1_CATEGORY_SCHEMA


STAGE = "N9A_R2"
STATUS_R1_SOURCE_LINEAGE_ONLY = "N9A_R1_source_lineage_only_plot_materialization_failed"
POINTER_PATH = Path(".legsa_runtime") / "n9a_r2_latest.json"

TARGET_ALGORITHM_SERIES = [
    "pure_INS",
    "single_antenna_original_KF_GINS",
    "final_v23_dual_antenna_EKF",
    "source_backed_EKF",
    "Raw_Doppler_EKF",
    "source_aware_EKF",
    "Go2_joint_EKF",
    "no_feedback_FGO",
    "selected_feedback_EKF",
    "reject_all_sanity",
]

R2_CATEGORY_SCHEMA: "OrderedDict[str, list[str]]" = R1_CATEGORY_SCHEMA

SERIES_HINTS = {
    "pure_INS": ["pure_ins", "pure-ins", "pureins", "ins_only"],
    "single_antenna_original_KF_GINS": ["single_antenna", "original_kf", "original_kf_gins", "kfgins_baseline"],
    "final_v23_dual_antenna_EKF": ["final_v23", "dual_final_v23", "final-v23", "dual_antenna"],
    "source_backed_EKF": ["source_backed", "source-backed", "clean_replay", "baseline_replay", "baseline_full"],
    "Raw_Doppler_EKF": ["raw_doppler", "plus_raw", "doppler_enabled"],
    "source_aware_EKF": ["source_aware", "sourceaware", "n6b", "lsim_oim"],
    "Go2_joint_EKF": ["go2_joint", "proprioceptive_joint", "go2_full", "go2_velocity", "go2_attitude"],
    "no_feedback_FGO": ["no_feedback_fgo", "no_feedback", "fgo_no_feedback"],
    "selected_feedback_EKF": ["selected_feedback", "feedback_full", "n8j_selected", "c0_selected"],
    "reject_all_sanity": ["reject_all", "reject_all_sanity", "sanity_reject"],
}

NAV_NAMES = {"legsa_port_nav.nav", "nav.nav", "kf_gins_navresult.nav"}
STD_NAMES = {"legsa_port_std.csv", "std.csv"}
EVAL_NAMES = {"eval_nav.csv", "error_series.csv"}
MANIFEST_NAMES = {"run_manifest.json"}
METRIC_NAMES = {"summary.json", "metrics.json", "metric_summary.csv", "case_key_metrics_table.csv"}
FEEDBACK_NAMES = {"fgo_feedback_observations.csv", "feedback_report.json", "fgo_feedback_report.json"}
FACTOR_NAMES = {"fgo_factor_table.csv", "factor_table.csv", "factor_report.json"}

FORMAL_ABLATION_TOKENS = [
    "by2_formal_ablation",
    "formal_ablation_plot",
    "n8k_by2_formal_ablation",
    "n8k2_by2_formal_ablation",
    "n8k3_by2_formal_ablation",
    "n8k4_by2_formal_ablation",
    "n8k5_by2_formal_ablation",
    "n8k6_a0_feedback",
]


@dataclass(frozen=True)
class R2Args:
    by2_plot_root: Path
    n8k_tag: str
    by2_fixposition_root: Path
    gnss1_raw: Path
    gnss2_raw: Path
    gnss1_status: Path
    gnss2_status: Path
    trace_truth: Path
    go2_body_imu_highlevel: Path
    algorithm_output_search_roots: tuple[Path, ...]
    clean_replay_root: Path
    dual_final_v23_artifact_root: Path
    legsa_run_root: Path
    output_dir: Path
    figure_output_dir: Path
    case_review_dir: Path
    summary_dir: Path
    index_output_dir: Path


def run_n9a_r2_by2_normal_real_plot_materialization(args: R2Args) -> dict[str, Any]:
    for path in [args.output_dir, args.figure_output_dir, args.case_review_dir, args.summary_dir, args.index_output_dir]:
        path.mkdir(parents=True, exist_ok=True)

    input_report = audit_source_inputs(args)
    discovery = discover_algorithm_outputs(args)
    inventory, category_report, plot_report, semantic_reports = materialize_real_plot_reports(args, input_report, discovery)
    decision = build_decision(discovery, category_report, plot_report, semantic_reports)

    reports: dict[str, dict[str, Any]] = {
        "N9A_R2_INPUT_SOURCE_ROLE_REPORT.json": input_report,
        "N9A_R2_ALGORITHM_OUTPUT_DISCOVERY_REPORT.json": discovery,
        "N9A_R2_BY2_NORMAL_REAL_PLOT_AUDIT_REPORT.json": plot_report,
        "N9A_R2_CATEGORY_COVERAGE_REPORT.json": category_report,
        "N9A_R2_DECISION_REPORT.json": decision,
        **semantic_reports,
    }
    for name, payload in reports.items():
        write_json(args.output_dir / name, payload)
    write_markdown_reports(args, discovery, category_report, plot_report, decision)
    write_pointer(args)
    available = [item for item in discovery["algorithm_series"] if item["available"]]
    missing = [item for item in discovery["algorithm_series"] if not item["available"]]
    return {
        "stage": STAGE,
        "case_name": CASE_NAME,
        "status": decision["status"],
        "r1_corrected_status": STATUS_R1_SOURCE_LINEAGE_ONLY,
        "available_algorithm_series_count": discovery["available_algorithm_series_count"],
        "algorithm_outputs_found": [item["series_name"] for item in available],
        "algorithm_outputs_missing": [item["series_name"] for item in missing],
        "BY2_normal_clean_real_plot_status": decision["BY2_normal_clean_real_plot_status"],
        "ready_for_N9B": decision["ready_for_N9B"],
        "recommended_next_stage": decision["recommended_next_stage"],
        "source_proxy_figures_count": plot_report["source_proxy_figures_count"],
        "source_proxy_figures_excluded_from_completion_count": plot_report["source_proxy_figures_excluded_from_completion_count"],
        "placeholder_count": plot_report["placeholder_count"],
        "semantic_mismatch_count": plot_report["semantic_mismatch_count"],
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def audit_source_inputs(args: R2Args) -> dict[str, Any]:
    files = {
        "gnss1_raw": audit_table(args.gnss1_raw, "gnss_observation_quality_only"),
        "gnss2_raw": audit_table(args.gnss2_raw, "gnss_observation_quality_only"),
        "gnss1_status": audit_table(args.gnss1_status, "gnss_status_yaw_receiver_velocity_observation_only"),
        "gnss2_status": audit_table(args.gnss2_status, "gnss_status_yaw_observation_only"),
        "trace_truth": audit_table(args.trace_truth, "truth_reference_evaluation_only_not_solver_input"),
        "go2_body_imu_highlevel": audit_text(args.go2_body_imu_highlevel, "go2_body_imu_high_level_source_not_truth"),
    }
    receiver_imu = find_first_existing(args.by2_fixposition_root, ["imu-data.csv", "imu_data.csv"])
    files["receiver_imu_data"] = audit_table(receiver_imu, "fixposition_receiver_imu_diagnostic_only") if receiver_imu else missing_source("receiver_imu_data", "fixposition_receiver_imu_diagnostic_only")
    return {
        "stage": STAGE,
        "case_name": CASE_NAME,
        "files": files,
        "trace_evaluation_only": True,
        "trace_solver_input": False,
        "trace_used_for_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_output_used_for_tuning": False,
        "by2_txt_body_imu_highlevel": True,
        "by2_txt_truth": False,
        "go2_position_truth": False,
        "go2_velocity_truth": False,
        "go2_contact_truth": False,
        "go2_yaw_truth": False,
        "receiver_imu_diagnostic_only": True,
        "receiver_imu_used_as_fused_body_imu": False,
        "no_future_data_check": True,
        "no_output_substitution_check": True,
        "path_leak_check_scope": "tracked_docs_config_scripts_only",
    }


def discover_algorithm_outputs(args: R2Args) -> dict[str, Any]:
    roots = unique_paths(
        [
            args.by2_plot_root,
            args.legsa_run_root,
            args.clean_replay_root,
            args.dual_final_v23_artifact_root,
            *args.algorithm_output_search_roots,
        ]
    )
    groups = collect_output_groups(roots)
    series_reports = []
    for series_name in TARGET_ALGORITHM_SERIES:
        candidates = [group for group in groups if group["series_name"] == series_name]
        best = choose_best_candidate(candidates)
        if best is None:
            series_reports.append(missing_series(series_name, "no runtime NAV/EVAL/STD/RUN_MANIFEST group matched this normal algorithm series"))
        elif best.get("excluded"):
            series_reports.append(missing_series(series_name, best.get("missing_reason", "candidate excluded")))
        elif not best.get("available_candidate"):
            series_reports.append(missing_series(series_name, "matched candidate lacks real algorithm NAV rows"))
        else:
            series_reports.append(series_from_group(series_name, best))
    available_count = sum(1 for item in series_reports if item["available"])
    for item in series_reports:
        item["can_plot_compare"] = bool(item["available"] and available_count >= 2 and item.get("can_plot_position_error"))
    return {
        "stage": STAGE,
        "case_name": CASE_NAME,
        "searched_roots": [str(path) for path in roots],
        "search_root_count": len(roots),
        "candidate_output_group_count": len(groups),
        "target_algorithm_series_count": len(TARGET_ALGORITHM_SERIES),
        "algorithm_series_count": len(TARGET_ALGORITHM_SERIES),
        "available_algorithm_series_count": available_count,
        "unavailable_algorithm_series_count": len(TARGET_ALGORITHM_SERIES) - available_count,
        "algorithm_series": series_reports,
        "formal_ablation_variants_counted_as_normal_cases": False,
        "formal_ablation_candidates_excluded_count": sum(1 for group in groups if group.get("excluded")),
        "source_lineage_is_not_algorithm_output": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
    }


def collect_output_groups(roots: Iterable[Path]) -> list[dict[str, Any]]:
    by_parent: dict[Path, dict[str, Any]] = {}
    root_list = list(roots)
    root_rank = {root: rank for rank, root in enumerate(root_list)}
    for root in root_list:
        if not root.exists():
            continue
        for path in iter_runtime_files(root):
            role = classify_runtime_file(path.name)
            if role is None:
                continue
            parent = path.parent
            group = by_parent.setdefault(
                parent,
                {
                    "output_root": str(parent),
                    "root_rank": root_rank[root],
                    "nav_path": "",
                    "std_path": "",
                    "eval_path": "",
                    "manifest_path": "",
                    "metrics_path": "",
                    "feedback_report_path": "",
                    "fgo_factor_table_path": "",
                    "matched_files": [],
                },
            )
            group["matched_files"].append(str(path))
            if role == "nav":
                group["nav_path"] = str(path)
            elif role == "std":
                group["std_path"] = str(path)
            elif role == "eval":
                group["eval_path"] = str(path)
            elif role == "manifest":
                group["manifest_path"] = str(path)
            elif role == "metrics":
                group["metrics_path"] = str(path)
            elif role == "feedback":
                group["feedback_report_path"] = str(path)
            elif role == "factor":
                group["fgo_factor_table_path"] = str(path)
    groups = []
    for parent, group in by_parent.items():
        enriched = enrich_group(parent, group)
        if enriched["series_name"]:
            groups.append(enriched)
    return groups


def iter_runtime_files(root: Path, max_depth: int = 8) -> Iterable[Path]:
    skip_names = {
        ".git",
        "__pycache__",
        "绘图",
        "figures",
        "figure",
        "plots",
        "ppt",
        "pptx",
        "index",
        "summary",
    }
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.parts) - base_depth
        if depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = [name for name in dirnames if name.lower() not in skip_names]
        for filename in filenames:
            lower = filename.lower()
            if not (
                "nav" in lower
                or "std" in lower
                or "eval" in lower
                or "manifest" in lower
                or "summary" in lower
                or "metric" in lower
                or "feedback" in lower
                or "factor" in lower
                or lower == "error_series.csv"
            ):
                continue
            yield current / filename


def classify_runtime_file(name: str) -> str | None:
    lower = name.lower()
    if lower in NAV_NAMES or lower.endswith("_nav.nav") or lower.endswith("navresult.nav"):
        return "nav"
    if lower in STD_NAMES or lower.endswith("_std.csv"):
        return "std"
    if lower in EVAL_NAMES or lower.endswith("eval_nav.csv") or lower.endswith("error_series.csv"):
        return "eval"
    if lower in MANIFEST_NAMES:
        return "manifest"
    if lower in METRIC_NAMES or "metric" in lower and lower.endswith((".json", ".csv")):
        return "metrics"
    if lower in FEEDBACK_NAMES or "feedback" in lower and lower.endswith((".json", ".csv")):
        return "feedback"
    if lower in FACTOR_NAMES or "factor" in lower and lower.endswith((".json", ".csv")):
        return "factor"
    return None


def enrich_group(parent: Path, group: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(group["manifest_path"]) if group.get("manifest_path") else {}
    path_text = str(parent).lower()
    manifest_text = manifest_role_text(manifest)
    text = (path_text + " " + manifest_text).lower()
    score_by_series = {series: series_score(series, text, path_text) for series in SERIES_HINTS}
    series_name, score = max(score_by_series.items(), key=lambda item: item[1])
    excluded = is_formal_ablation_archive(parent, group)
    has_nav = file_nonempty(group.get("nav_path", ""))
    has_eval = file_nonempty(group.get("eval_path", ""))
    has_std = file_nonempty(group.get("std_path", ""))
    complete_score = int(has_nav) * 5 + int(has_eval) * 3 + int(has_std) * 2 + int(bool(group.get("manifest_path"))) + int(bool(group.get("metrics_path")))
    group.update(
        {
            "series_name": series_name if score > 0 else "",
            "series_match_score": score,
            "available_candidate": bool(score > 0 and has_nav and not excluded),
            "has_nav": has_nav,
            "has_eval": has_eval,
            "has_std": has_std,
            "complete_score": complete_score,
            "excluded": excluded,
            "missing_reason": "formal ablation or plot-archive candidate is excluded from BY2_normal_clean real algorithm completion" if excluded else "",
        }
    )
    return group


def manifest_role_text(manifest: dict[str, Any]) -> str:
    keys = [
        "phase",
        "port_role",
        "run_label",
        "variant",
        "variant_name",
        "algorithm",
        "algorithm_line",
        "algorithm_role",
        "config_policy_evidence_status",
    ]
    return " ".join(str(manifest.get(key, "")) for key in keys)


def series_score(series: str, text: str, path_text: str) -> int:
    if series == "final_v23_dual_antenna_EKF" and "final_v23" not in path_text:
        return 0
    if series == "source_backed_EKF" and "baseline_replay" not in path_text:
        advanced_tokens = ["raw_doppler", "source_aware", "sourceaware", "go2", "fgo", "feedback", "lsim", "oim"]
        if any(token in path_text for token in advanced_tokens):
            return 0
    if series == "source_aware_EKF" and ("no_sourceaware" in text or "no_source_aware" in text):
        return 0
    if series == "Go2_joint_EKF" and ("no_go2" in text or "without_go2" in text):
        return 0
    if series == "selected_feedback_EKF" and "reject_all" in text:
        return 0
    score = sum(1 for hint in SERIES_HINTS[series] if hint in text)
    if series == "Raw_Doppler_EKF" and "raw_doppler" in path_text:
        score += 3
    return score


def is_formal_ablation_archive(parent: Path, group: dict[str, Any]) -> bool:
    lower = str(parent).lower()
    formal = any(token in lower for token in FORMAL_ABLATION_TOKENS)
    if formal and not group.get("nav_path"):
        return True
    return bool(formal and "/绘图/" in str(parent))


def choose_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.get("excluded", False), -item.get("available_candidate", False), -item.get("complete_score", 0), item.get("root_rank", 99), item.get("output_root", "")))[0]


def missing_series(series_name: str, reason: str) -> dict[str, Any]:
    return {
        "series_name": series_name,
        "available": False,
        "output_root": "",
        "nav_path": "",
        "std_path": "",
        "eval_path": "",
        "manifest_path": "",
        "metrics_path": "",
        "feedback_report_path": "",
        "fgo_factor_table_path": "",
        "figure_source_role": "missing_real_algorithm_output",
        "row_count_nav": 0,
        "row_count_eval": 0,
        "row_count_std": 0,
        "can_plot_trajectory": False,
        "can_plot_position_error": False,
        "can_plot_velocity": False,
        "can_plot_attitude": False,
        "can_plot_consistency": False,
        "can_plot_compare": False,
        "missing_reason": reason,
    }


def series_from_group(series_name: str, group: dict[str, Any]) -> dict[str, Any]:
    nav_path = Path(group["nav_path"]) if group.get("nav_path") else None
    eval_path = Path(group["eval_path"]) if group.get("eval_path") else None
    std_path = Path(group["std_path"]) if group.get("std_path") else None
    nav_header = table_header(nav_path) if nav_path else []
    eval_rows = count_data_rows(eval_path) if eval_path else 0
    return {
        "series_name": series_name,
        "available": True,
        "output_root": group["output_root"],
        "nav_path": group.get("nav_path", ""),
        "std_path": group.get("std_path", ""),
        "eval_path": group.get("eval_path", ""),
        "manifest_path": group.get("manifest_path", ""),
        "metrics_path": group.get("metrics_path", ""),
        "feedback_report_path": group.get("feedback_report_path", ""),
        "fgo_factor_table_path": group.get("fgo_factor_table_path", ""),
        "figure_source_role": "real_algorithm_runtime_output",
        "row_count_nav": count_data_rows(nav_path) if nav_path else 0,
        "row_count_eval": eval_rows,
        "row_count_std": count_data_rows(std_path) if std_path else 0,
        "can_plot_trajectory": True,
        "can_plot_position_error": bool(eval_rows or nav_path),
        "can_plot_velocity": any(key in nav_header for key in ["vn", "ve", "vd", "vn_mps", "ve_mps", "vd_mps"]),
        "can_plot_attitude": any(key in nav_header for key in ["roll_deg", "pitch_deg", "yaw_deg", "roll", "pitch", "yaw"]),
        "can_plot_consistency": bool(std_path and count_data_rows(std_path) > 0),
        "can_plot_compare": False,
        "missing_reason": "",
    }


def materialize_real_plot_reports(args: R2Args, input_report: dict[str, Any], discovery: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    available = [item for item in discovery["algorithm_series"] if item["available"]]
    data = load_plot_data(available, args.trace_truth, args.gnss1_status, args.gnss2_status, args.go2_body_imu_highlevel)
    inventory: list[dict[str, Any]] = []
    for category, filenames in R2_CATEGORY_SCHEMA.items():
        if category == "09_case_review":
            continue
        for filename in filenames:
            entry = materialize_one_figure(args.figure_output_dir, category, filename, input_report, discovery, data)
            inventory.append(entry)
    write_case_review(args, discovery, inventory)
    inventory.extend(case_review_entries(args))
    category_report = category_coverage(inventory)
    plot_report = plot_audit_report(inventory)
    semantic_reports = build_semantic_reports(discovery, inventory)
    return inventory, category_report, plot_report, semantic_reports


def materialize_one_figure(figure_root: Path, category: str, filename: str, input_report: dict[str, Any], discovery: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    path = figure_root / CASE_NAME / category / filename
    available = [item for item in discovery["algorithm_series"] if item["available"]]
    if not filename.endswith(".png"):
        return base_entry(category, filename, path, True, "case review artifact", plot_kind="document")
    if category == "01_trajectory":
        return materialize_trajectory(path, category, filename, available, data)
    if category == "02_position_errors":
        return materialize_position_error(path, category, filename, available, data)
    if category == "03_velocity":
        return materialize_velocity(path, category, filename, available, data)
    if category == "04_attitude":
        return materialize_attitude(path, category, filename, available, data)
    if category == "05_consistency":
        return materialize_consistency(path, category, filename, available, data)
    if category == "06_observation_quality":
        plot_source_panel(path, f"{CASE_NAME} {filename}", input_report)
        return base_entry(category, filename, path, True, "source observation quality figure", source_type="source_quality", completion_eligible=True, plot_kind="line_or_bar")
    if category == "07_compare":
        return materialize_compare(path, category, filename, available, data)
    if category == "08_summary_panels":
        return materialize_summary_panel(path, category, filename, available, input_report, data)
    if category in {"10_fgo_factors", "11_feedback", "12_legged_factors"}:
        return materialize_optional_runtime_panel(path, category, filename, available)
    if category == "13_degradation_meta":
        documented_not_applicable(path, category, filename, "normal_condition_no_degradation_injection")
        return base_entry(category, filename, path, False, "normal_condition_no_degradation_injection", source_type="not_applicable_documentation", plot_kind="documented_not_applicable")
    if category == "14_audit_sanity":
        plot_source_panel(path, f"{CASE_NAME} {filename}", input_report)
        return base_entry(category, filename, path, True, "audit sanity source check", source_type="audit_sanity", completion_eligible=True, plot_kind="line_or_bar")
    return missing_entry(category, filename, path, "no R2 real plot rule for this figure")


def materialize_trajectory(path: Path, category: str, filename: str, available: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    if not available:
        return missing_entry(category, filename, path, "algorithm NAV missing; source-only trajectory is excluded from real completion", source_proxy=True)
    if filename in {"algorithm_trajectory_compare.png", "trajectory_delta_vector.png"} and len(available) < 2:
        return missing_entry(category, filename, path, "requires at least two real algorithm NAV series")
    plot_algorithm_trajectory(path, filename, available, data)
    return base_entry(category, filename, path, True, "real algorithm NAV trajectory", source_type="algorithm_nav", completion_eligible=True, plot_kind="trajectory")


def materialize_position_error(path: Path, category: str, filename: str, available: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    usable = [item for item in available if data["errors"].get(item["series_name"])]
    if not usable:
        return missing_entry(category, filename, path, "algorithm EVAL/NAV-to-trace position error missing", source_proxy=True)
    if filename.endswith("_bar.png"):
        metric = "horizontal_rmse_m"
        if filename.startswith("up_"):
            metric = "up_rmse_m"
        elif "p95" in filename and filename.startswith("horizontal"):
            metric = "horizontal_p95_m"
        elif "p95" in filename and filename.startswith("up"):
            metric = "up_p95_m"
        elif filename.startswith("max"):
            metric = "max_error_m"
        plot_metric_bar(path, filename, usable, data["metrics"], metric)
        return base_entry(category, filename, path, True, "algorithm error metric bar", source_type="algorithm_eval_or_nav_trace", completion_eligible=True, plot_kind="bar")
    plot_position_error(path, filename, usable, data)
    kind = "cdf" if "cdf" in filename else "timeseries"
    return base_entry(category, filename, path, True, "algorithm EVAL/NAV-to-trace position error", source_type="algorithm_eval_or_nav_trace", completion_eligible=True, plot_kind=kind)


def materialize_velocity(path: Path, category: str, filename: str, available: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    source_roles = velocity_source_roles(data)
    role = source_roles.get(filename)
    if role is None:
        return missing_entry(category, filename, path, "velocity source chain not available or not distinguishable")
    plot_velocity_panel(path, filename, role, available, data)
    return base_entry(category, filename, path, True, f"velocity source role: {role}", source_type=role, completion_eligible=role != "proxy", plot_kind="timeseries")


def materialize_attitude(path: Path, category: str, filename: str, available: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    usable = [item for item in available if data["nav"].get(item["series_name"]) and item["can_plot_attitude"]]
    if not usable:
        return missing_entry(category, filename, path, "algorithm attitude NAV missing")
    plot_attitude_panel(path, filename, usable, data)
    return base_entry(category, filename, path, True, "attitude source roles separated", source_type="algorithm_estimate_reference_observation", completion_eligible=bool(usable), plot_kind="bar" if filename.endswith("_bar.png") else "timeseries")


def materialize_consistency(path: Path, category: str, filename: str, available: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    usable = [item for item in available if item["can_plot_consistency"] and data["std"].get(item["series_name"])]
    if not usable:
        return missing_entry(category, filename, path, "algorithm STD/covariance/residual missing; error proxy is not allowed")
    plot_consistency_panel(path, filename, usable, data)
    return base_entry(category, filename, path, True, "algorithm STD/covariance-backed consistency", source_type="algorithm_std_covariance", completion_eligible=True, plot_kind="timeseries")


def materialize_compare(path: Path, category: str, filename: str, available: list[dict[str, Any]], data: dict[str, Any]) -> dict[str, Any]:
    usable = [item for item in available if data["metrics"].get(item["series_name"])]
    if len(usable) < 2:
        return missing_entry(category, filename, path, "07_compare requires at least two real algorithm outputs with metrics")
    if filename.endswith("_bar.png") or "rmse_p95_max" in filename:
        plot_compare_bar(path, filename, usable, data["metrics"])
        plot_kind = "bar"
    else:
        plot_compare_matrix(path, filename, usable, data["metrics"])
        plot_kind = "matrix"
    return base_entry(category, filename, path, True, "real algorithm output comparison", source_type="algorithm_metrics", completion_eligible=True, plot_kind=plot_kind)


def materialize_summary_panel(path: Path, category: str, filename: str, available: list[dict[str, Any]], input_report: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    if filename in {"source_availability_summary.png", "data_lineage_summary.png"}:
        plot_source_panel(path, f"{CASE_NAME} {filename}", input_report)
        return base_entry(category, filename, path, True, "source availability or lineage summary", source_type="source_summary", completion_eligible=True, plot_kind="bar")
    if not available:
        return missing_entry(category, filename, path, "normal algorithm metric summary requires real algorithm metrics")
    plot_compare_matrix(path, filename, available, data["metrics"])
    return base_entry(category, filename, path, True, "normal algorithm metric summary from real metrics", source_type="algorithm_metrics", completion_eligible=True, plot_kind="matrix")


def materialize_optional_runtime_panel(path: Path, category: str, filename: str, available: list[dict[str, Any]]) -> dict[str, Any]:
    if category == "10_fgo_factors":
        usable = [item for item in available if item.get("fgo_factor_table_path")]
        reason = "FGO factor report missing for BY2_normal_clean"
    elif category == "11_feedback":
        usable = [item for item in available if item.get("feedback_report_path")]
        reason = "feedback report missing for BY2_normal_clean"
    else:
        usable = [item for item in available if "go2" in item["series_name"].lower()]
        reason = "legged factor report missing for BY2_normal_clean"
    if not usable:
        documented_not_applicable(path, category, filename, reason)
        return base_entry(category, filename, path, False, reason, source_type="not_applicable_documentation", plot_kind="documented_missing")
    plot_optional_runtime_panel(path, filename, usable)
    return base_entry(category, filename, path, True, "runtime factor/feedback report exists", source_type="runtime_factor_feedback_report", completion_eligible=True, plot_kind="bar")


def base_entry(category: str, filename: str, path: Path, applicable: bool, reason: str, *, source_type: str = "", completion_eligible: bool = False, plot_kind: str = "", source_proxy: bool = False) -> dict[str, Any]:
    present = path.exists()
    return {
        "case_name": CASE_NAME,
        "category": category,
        "filename": filename,
        "path": str(path),
        "path_role": "N9A_R2_FIGURE_OUTPUT_DIR",
        "present": present,
        "nonempty": present and path.stat().st_size > 0,
        "applicable": applicable,
        "documented_not_applicable": not applicable and present,
        "not_applicable_reason": "" if applicable else reason,
        "missing_reason": "" if present else reason,
        "placeholder": False,
        "empty_axis": False,
        "semantic_mismatch": False,
        "source_type": source_type,
        "source_proxy": source_proxy,
        "excluded_from_completion": bool(source_proxy),
        "completion_eligible": bool(completion_eligible and not source_proxy),
        "plot_kind": plot_kind,
    }


def missing_entry(category: str, filename: str, path: Path, reason: str, *, source_proxy: bool = False) -> dict[str, Any]:
    return base_entry(category, filename, path, True, reason, source_type="missing_real_algorithm_output", completion_eligible=False, plot_kind="missing", source_proxy=source_proxy)


def load_plot_data(available: list[dict[str, Any]], trace_path: Path, gnss1_status: Path, gnss2_status: Path, go2_path: Path) -> dict[str, Any]:
    trace = read_table_rows(trace_path, limit=2000)
    add_enu(trace)
    gnss1 = read_table_rows(gnss1_status, limit=2000)
    gnss2 = read_table_rows(gnss2_status, limit=2000)
    go2 = read_go2_rows(go2_path, limit=2000)
    nav: dict[str, list[dict[str, Any]]] = {}
    std: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, dict[str, list[float]]] = {}
    metrics: dict[str, dict[str, float]] = {}
    for item in available:
        name = item["series_name"]
        nav_rows = read_table_rows(Path(item["nav_path"]), limit=2000)
        add_enu(nav_rows)
        std_rows = read_table_rows(Path(item["std_path"]), limit=2000) if item.get("std_path") else []
        nav[name] = nav_rows
        std[name] = std_rows
        errors[name] = compute_position_errors(nav_rows, trace)
        metrics[name] = compute_metrics(errors[name])
    return {"trace": trace, "gnss1": gnss1, "gnss2": gnss2, "go2": go2, "nav": nav, "std": std, "errors": errors, "metrics": metrics}


def compute_position_errors(nav_rows: list[dict[str, Any]], trace_rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    n = min(len(nav_rows), len(trace_rows), 1000)
    north: list[float] = []
    east: list[float] = []
    up: list[float] = []
    horizontal: list[float] = []
    for index in range(n):
        dn = safe_float(nav_rows[index].get("north_m")) - safe_float(trace_rows[index].get("north_m"))
        de = safe_float(nav_rows[index].get("east_m")) - safe_float(trace_rows[index].get("east_m"))
        du = value_for(nav_rows[index], ["up_m", "height_m", "height"]) - value_for(trace_rows[index], ["up_m", "height_m", "height"])
        north.append(dn)
        east.append(de)
        up.append(du)
        horizontal.append(math.hypot(de, dn))
    return {"north_m": north, "east_m": east, "up_m": up, "horizontal_m": horizontal, "max_m": [max(abs(north[i]), abs(east[i]), abs(up[i]), horizontal[i]) for i in range(len(horizontal))]}


def compute_metrics(errors: dict[str, list[float]]) -> dict[str, float]:
    horizontal = errors.get("horizontal_m", [])
    up = [abs(value) for value in errors.get("up_m", [])]
    max_error = errors.get("max_m", [])
    return {
        "horizontal_rmse_m": rmse(horizontal),
        "up_rmse_m": rmse(up),
        "horizontal_p95_m": percentile(horizontal, 0.95),
        "up_p95_m": percentile(up, 0.95),
        "max_error_m": max(max_error) if max_error else 0.0,
    }


def plot_algorithm_trajectory(path: Path, filename: str, available: list[dict[str, Any]], data: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 6.0), dpi=110)
    trace = data["trace"]
    if trace and "east_m" in trace[0]:
        ax.plot([row["east_m"] for row in trace], [row["north_m"] for row in trace], label="trace/reference", linewidth=1.0, color="black")
    if filename == "trajectory_delta_vector.png" and len(available) >= 2:
        first = data["nav"].get(available[0]["series_name"], [])
        second = data["nav"].get(available[1]["series_name"], [])
        n = min(len(first), len(second), 80)
        xs = [safe_float(first[i].get("east_m")) for i in range(n)]
        ys = [safe_float(first[i].get("north_m")) for i in range(n)]
        us = [safe_float(second[i].get("east_m")) - xs[i] for i in range(n)]
        vs = [safe_float(second[i].get("north_m")) - ys[i] for i in range(n)]
        ax.quiver(xs, ys, us, vs, angles="xy", scale_units="xy", scale=1, width=0.002, label="algorithm delta vector")
    else:
        for item in available[:4]:
            rows = data["nav"].get(item["series_name"], [])
            if rows:
                ax.plot([row.get("east_m", 0.0) for row in rows], [row.get("north_m", 0.0) for row in rows], label=item["series_name"], linewidth=1.2)
    if filename == "start_end_marker_trajectory.png":
        for item in available[:3]:
            rows = data["nav"].get(item["series_name"], [])
            if rows:
                ax.scatter([rows[0].get("east_m", 0.0), rows[-1].get("east_m", 0.0)], [rows[0].get("north_m", 0.0), rows[-1].get("north_m", 0.0)], s=35)
    if filename == "zoomed_trajectory_key_region.png":
        all_rows = data["nav"].get(available[0]["series_name"], [])
        if len(all_rows) > 20:
            mid = len(all_rows) // 2
            window = all_rows[max(0, mid - 30) : mid + 30]
            xs = [row.get("east_m", 0.0) for row in window]
            ys = [row.get("north_m", 0.0) for row in window]
            pad = 2.0
            ax.set_xlim(min(xs) - pad, max(xs) + pad)
            ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_title(f"{CASE_NAME} {filename}\nreal algorithm NAV; trace is reference only")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    save_fig(fig, path)


def plot_position_error(path: Path, filename: str, usable: list[dict[str, Any]], data: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    component = "horizontal_m"
    if filename.startswith("north"):
        component = "north_m"
    elif filename.startswith("east"):
        component = "east_m"
    elif filename.startswith("up"):
        component = "up_m"
    for item in usable[:5]:
        values = data["errors"].get(item["series_name"], {}).get(component, [])
        if "cdf" in filename:
            ordered = sorted(abs(value) for value in values)
            y = [(i + 1) / len(ordered) for i in range(len(ordered))] if ordered else []
            ax.plot(ordered, y, label=item["series_name"])
            ax.set_xlabel("error (m)")
            ax.set_ylabel("ECDF")
        else:
            ax.plot(list(range(len(values))), values, label=item["series_name"], linewidth=1.2)
            ax.set_xlabel("sample")
            ax.set_ylabel("m")
    ax.set_title(f"{CASE_NAME} {filename}\nalgorithm NAV/EVAL compared with trace reference")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    save_fig(fig, path)


def plot_metric_bar(path: Path, filename: str, usable: list[dict[str, Any]], metrics: dict[str, dict[str, float]], metric: str) -> None:
    labels = [item["series_name"] for item in usable]
    values = [metrics.get(label, {}).get(metric, 0.0) for label in labels]
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    ax.bar(labels, values, color="#4c78a8")
    ax.set_title(f"{CASE_NAME} {filename}\nalgorithm metric bar from real NAV/EVAL")
    ax.set_xlabel("algorithm series")
    ax.set_ylabel(metric)
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    save_fig(fig, path)


def plot_velocity_panel(path: Path, filename: str, role: str, available: list[dict[str, Any]], data: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    if role == "algorithm_nav_velocity":
        for item in available[:4]:
            rows = data["nav"].get(item["series_name"], [])
            values = [math.hypot(value_for(row, ["vn", "vn_mps"]), value_for(row, ["ve", "ve_mps"])) for row in rows[:800]]
            ax.plot(values, label=item["series_name"], linewidth=1.2)
    elif role == "receiver_status_velocity":
        rows = data["gnss1"]
        values = [math.hypot(value_for(row, ["vel_n", "vel_n_mps", "vn"]), value_for(row, ["vel_e", "vel_e_mps", "ve"])) for row in rows[:800]]
        ax.plot(values, label="receiver status velocity", linewidth=1.2)
    elif role == "go2_highlevel_velocity":
        values = [math.hypot(value_for(row, ["vx", "vel_x", "body_vx"]), value_for(row, ["vy", "vel_y", "body_vy"])) for row in data["go2"][:800]]
        ax.plot(values, label="Go2 high-level horizontal velocity source", linewidth=1.2)
    else:
        values = [0.0]
        ax.plot(values, label=role)
    ax.set_title(f"{CASE_NAME} {filename}\nsource role = {role}")
    ax.set_xlabel("sample")
    ax.set_ylabel("m/s or diagnostic unit")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    save_fig(fig, path)


def plot_attitude_panel(path: Path, filename: str, usable: list[dict[str, Any]], data: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    key = "yaw_deg" if "yaw" in filename else "roll_deg" if "roll" in filename else "pitch_deg"
    if filename.endswith("_bar.png"):
        labels = [item["series_name"] for item in usable]
        values = []
        for item in usable:
            rows = data["nav"].get(item["series_name"], [])
            values.append(rmse([value_for(row, [key, key.replace("_deg", "")]) for row in rows[:800]]))
        ax.bar(labels, values, color="#72b7b2")
        ax.set_xlabel("algorithm series")
        ax.set_ylabel("deg")
        ax.tick_params(axis="x", rotation=25)
    else:
        for item in usable[:3]:
            rows = data["nav"].get(item["series_name"], [])
            ax.plot([value_for(row, [key, key.replace("_deg", "")]) for row in rows[:800]], label=f"{item['series_name']} estimate")
        trace = data["trace"]
        if trace and key.replace("_deg", "") in trace[0]:
            ax.plot([value_for(row, [key, key.replace("_deg", "")]) for row in trace[:800]], label="trace/reference", linewidth=1.0)
        if "yaw" in filename:
            ax.plot([yaw_from_status(row) for row in data["gnss1"][:800]], label="GNSS yaw observation", linewidth=1.0)
        ax.set_xlabel("sample")
        ax.set_ylabel("deg")
    ax.set_title(f"{CASE_NAME} {filename}\nestimate, observation, reference roles separated")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    save_fig(fig, path)


def plot_consistency_panel(path: Path, filename: str, usable: list[dict[str, Any]], data: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=110)
    for item in usable[:3]:
        std_rows = data["std"].get(item["series_name"], [])
        values = [3.0 * value_for(row, ["std_pos_n_m", "std_vel_n_mps", "std_roll_deg", "std_yaw_deg"]) for row in std_rows[:800]]
        ax.plot(values, label=f"{item['series_name']} 3sigma/STD", linewidth=1.2)
    ax.set_title(f"{CASE_NAME} {filename}\nalgorithm STD/covariance required")
    ax.set_xlabel("sample")
    ax.set_ylabel("3sigma")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=7)
    save_fig(fig, path)


def plot_compare_bar(path: Path, filename: str, usable: list[dict[str, Any]], metrics: dict[str, dict[str, float]]) -> None:
    metric = "horizontal_rmse_m"
    if "up" in filename:
        metric = "up_rmse_m"
    labels = [item["series_name"] for item in usable]
    values = [metrics.get(label, {}).get(metric, 0.0) for label in labels]
    fig, ax = plt.subplots(figsize=(9.8, 5.2), dpi=110)
    ax.bar(labels, values, color="#59a14f")
    ax.set_title(f"{CASE_NAME} {filename}\nreal algorithm outputs only")
    ax.set_xlabel("algorithm series")
    ax.set_ylabel(metric)
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    save_fig(fig, path)


def plot_compare_matrix(path: Path, filename: str, usable: list[dict[str, Any]], metrics: dict[str, dict[str, float]]) -> None:
    labels = [item["series_name"] for item in usable]
    metric_keys = ["horizontal_rmse_m", "horizontal_p95_m", "up_rmse_m", "up_p95_m", "max_error_m"]
    values = [[metrics.get(label, {}).get(metric, 0.0) for metric in metric_keys] for label in labels]
    fig, ax = plt.subplots(figsize=(9.5, 5.4), dpi=110)
    image = ax.imshow(values or [[0.0]], aspect="auto", cmap="viridis")
    ax.set_title(f"{CASE_NAME} {filename}\nalgorithm metrics matrix")
    ax.set_xticks(range(len(metric_keys)), metric_keys, rotation=25, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    save_fig(fig, path)


def plot_source_panel(path: Path, title: str, input_report: dict[str, Any]) -> None:
    labels = list(input_report["files"].keys())
    values = [input_report["files"][label].get("row_count", 0) for label in labels]
    fig, ax = plt.subplots(figsize=(10.0, 5.4), dpi=110)
    ax.bar(labels, values, color="#f28e2b")
    ax.set_title(title + "\nsource role only; not an algorithm estimate")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    save_fig(fig, path)


def plot_optional_runtime_panel(path: Path, filename: str, usable: list[dict[str, Any]]) -> None:
    labels = [item["series_name"] for item in usable]
    values = [1 for _ in usable]
    fig, ax = plt.subplots(figsize=(8.8, 4.8), dpi=110)
    ax.bar(labels, values, color="#b07aa1")
    ax.set_title(f"{CASE_NAME} {filename}\nruntime factor/feedback report exists")
    ax.set_ylabel("available")
    ax.tick_params(axis="x", rotation=25)
    save_fig(fig, path)


def documented_not_applicable(path: Path, category: str, filename: str, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1080, 600), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        f"{STAGE} documented not-applicable or missing",
        f"case = {CASE_NAME}",
        f"category = {category}",
        f"figure = {filename}",
        f"reason = {reason}",
        "not counted as applicable real algorithm plot completion",
    ]
    for index, line in enumerate(lines):
        draw.text((36, 42 + index * 42), line[:145], fill=(0, 0, 0))
    image.save(path)


def category_coverage(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    categories = []
    for category, filenames in R2_CATEGORY_SCHEMA.items():
        entries = [item for item in inventory if item["category"] == category]
        required = [item for item in entries if item["applicable"]]
        missing = [item for item in required if not item["present"] or not item["nonempty"]]
        status = "complete" if len(entries) >= len(filenames) and not missing else "incomplete"
        if required and all(item["source_type"] == "missing_real_algorithm_output" for item in required):
            status = "missing_real_algorithm_output"
        if not required:
            status = "documented_not_applicable"
        categories.append(
            {
                "category": category,
                "expected_count": len(filenames),
                "entry_count": len(entries),
                "present_count": sum(1 for item in entries if item["present"]),
                "missing_count": len(missing),
                "source_proxy_count": sum(1 for item in entries if item["source_proxy"]),
                "status": status,
            }
        )
    return {
        "stage": STAGE,
        "case_name": CASE_NAME,
        "category_count": len(R2_CATEGORY_SCHEMA),
        "categories": categories,
        "complete_category_count": sum(1 for item in categories if item["status"] == "complete"),
        "incomplete_category_count": sum(1 for item in categories if item["status"] != "complete"),
        "category_coverage_complete": all(item["status"] == "complete" for item in categories),
        "ready_for_N9B": False,
    }


def plot_audit_report(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [item for item in inventory if item["applicable"]]
    missing = [item for item in applicable if not item["present"] or not item["nonempty"]]
    return {
        "stage": STAGE,
        "case_name": CASE_NAME,
        "inventory": inventory,
        "figure_count": sum(1 for item in inventory if item["filename"].endswith(".png") and item["present"]),
        "applicable_figure_count": sum(1 for item in applicable if item["filename"].endswith(".png")),
        "missing_count": len(missing),
        "missing_or_incomplete_figures": [f"{item['category']}/{item['filename']}" for item in missing],
        "placeholder_count": sum(1 for item in inventory if item["placeholder"]),
        "semantic_mismatch_count": sum(1 for item in inventory if item["semantic_mismatch"]),
        "source_proxy_figures_count": sum(1 for item in inventory if item["source_proxy"]),
        "source_proxy_figures_excluded_from_completion_count": sum(1 for item in inventory if item["source_proxy"] and item["excluded_from_completion"]),
        "documented_not_applicable_count": sum(1 for item in inventory if item["documented_not_applicable"]),
        "no_false_complete": bool(missing),
        "ready_for_N9B": False,
    }


def build_semantic_reports(discovery: dict[str, Any], inventory: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    available_count = discovery["available_algorithm_series_count"]
    compare_entries = [item for item in inventory if item["category"] == "07_compare"]
    trajectory_entries = [item for item in inventory if item["category"] == "01_trajectory"]
    position_entries = [item for item in inventory if item["category"] == "02_position_errors"]
    consistency_entries = [item for item in inventory if item["category"] == "05_consistency"]
    metric_bar_entries = [item for item in inventory if item["filename"].endswith("_bar.png")]
    velocity_entries = [item for item in inventory if item["category"] == "03_velocity" and item["present"]]
    velocity_roles = [item["source_type"] for item in velocity_entries if item["source_type"]]
    return {
        "N9A_R2_SOURCE_PROXY_EXCLUSION_REPORT.json": {
            "stage": STAGE,
            "source_proxy_figures_count": sum(1 for item in inventory if item["source_proxy"]),
            "source_proxy_figures_excluded_from_completion_count": sum(1 for item in inventory if item["source_proxy"] and item["excluded_from_completion"]),
            "source_data_treated_as_algorithm_estimate": False,
            "trace_solver_input": False,
            "by2_txt_truth": False,
        },
        "N9A_R2_REAL_TRAJECTORY_SEMANTICS_REPORT.json": {
            "stage": STAGE,
            "available_algorithm_nav_series_count": sum(1 for item in discovery["algorithm_series"] if item["can_plot_trajectory"]),
            "trajectory_compare_requires_algorithm_nav": True,
            "trajectory_category_complete": all(item["present"] and item["source_type"] == "algorithm_nav" for item in trajectory_entries if item["applicable"]) and bool(trajectory_entries),
            "semantic_mismatch_count": sum(1 for item in trajectory_entries if item["semantic_mismatch"]),
        },
        "N9A_R2_REAL_POSITION_ERROR_SEMANTICS_REPORT.json": {
            "stage": STAGE,
            "available_algorithm_error_series_count": sum(1 for item in discovery["algorithm_series"] if item["can_plot_position_error"]),
            "position_error_uses_algorithm_eval_or_nav_trace": True,
            "gnss_status_minus_trace_as_algorithm_error": False,
            "position_error_category_complete": all(item["present"] and item["source_type"] == "algorithm_eval_or_nav_trace" for item in position_entries if item["applicable"]) and bool(position_entries),
        },
        "N9A_R2_METRIC_BAR_SEMANTICS_REPORT.json": {
            "stage": STAGE,
            "bar_entries": [{"category": item["category"], "filename": item["filename"], "present": item["present"], "plot_kind": item["plot_kind"]} for item in metric_bar_entries],
            "non_bar_metric_bar_count": sum(1 for item in metric_bar_entries if item["present"] and item["plot_kind"] != "bar"),
        },
        "N9A_R2_VELOCITY_SOURCE_DISTINCTION_REPORT.json": {
            "stage": STAGE,
            "velocity_source_roles": velocity_roles,
            "distinct_velocity_source_role_count": len(set(velocity_roles)),
            "same_proxy_used_for_all_velocity_sources": bool(velocity_roles and len(set(velocity_roles)) == 1 and len(velocity_roles) > 1 and velocity_roles[0] == "proxy"),
        },
        "N9A_R2_COMPARE_REQUIRES_ALGORITHM_OUTPUTS_REPORT.json": {
            "stage": STAGE,
            "available_algorithm_series_count": available_count,
            "compare_complete": all(item["present"] for item in compare_entries if item["applicable"]) and bool(compare_entries),
            "compare_requires_at_least_two_real_algorithm_outputs": True,
        },
        "N9A_R2_CONSISTENCY_REQUIRES_STD_REPORT.json": {
            "stage": STAGE,
            "available_std_series_count": sum(1 for item in discovery["algorithm_series"] if item["can_plot_consistency"]),
            "consistency_entries_present_without_std": sum(1 for item in consistency_entries if item["present"] and item["source_type"] != "algorithm_std_covariance"),
            "error_proxy_used_as_3sigma": False,
        },
    }


def build_decision(discovery: dict[str, Any], category_report: dict[str, Any], plot_report: dict[str, Any], semantic_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    available_count = discovery["available_algorithm_series_count"]
    complete = category_report["category_coverage_complete"] and plot_report["missing_count"] == 0
    blockers = []
    if available_count == 0:
        blockers.append("real algorithm outputs missing")
    if available_count < 2:
        blockers.append("07_compare requires at least two real algorithm outputs")
    if not complete:
        blockers.append("01-14 real plot materialization incomplete")
    if semantic_reports["N9A_R2_CONSISTENCY_REQUIRES_STD_REPORT.json"]["available_std_series_count"] == 0:
        blockers.append("algorithm STD/covariance missing for consistency plots")
    if available_count == 0:
        status = "N9A_R2_algorithm_outputs_missing"
        next_stage = "locate_or_generate_BY2_normal_algorithm_outputs"
        plot_status = "failed_no_real_algorithm_outputs"
    elif complete and not blockers:
        status = "N9A_R2_BY2_normal_real_plot_materialization_complete"
        next_stage = "N9B_after_explicit_user_approval"
        plot_status = "complete"
    else:
        status = "N9A_R2_real_plot_materialization_incomplete"
        next_stage = "targeted_real_plot_completion"
        plot_status = "incomplete"
    return {
        "stage": STAGE,
        "case_name": CASE_NAME,
        "status": status,
        "r1_corrected_status": STATUS_R1_SOURCE_LINEAGE_ONLY,
        "blockers": blockers,
        "BY2_normal_clean_real_plot_status": plot_status,
        "available_algorithm_series_count": available_count,
        "ready_for_N9B": False if status != "N9A_R2_BY2_normal_real_plot_materialization_complete" else "true_only_after_user_approval",
        "recommended_next_stage": next_stage,
        "initial_N9A_R1_case_model_after": "BY2_normal_clean",
        "initial_N9A_R1_case_count_after": 1,
        "initial_N9A_R1_algorithm_series_count": len(TARGET_ALGORITHM_SERIES),
        "initial_N9A_R1_available_algorithm_series_count": 0,
        "source_lineage_only_is_not_plot_materialization": True,
        "algorithm_changes": False,
        "no_algorithm_changes": True,
        "degradation_matrix_run": False,
        "N9B_degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_finalv23_tuning": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_markdown_reports(args: R2Args, discovery: dict[str, Any], category_report: dict[str, Any], plot_report: dict[str, Any], decision: dict[str, Any]) -> None:
    found = [item["series_name"] for item in discovery["algorithm_series"] if item["available"]]
    missing = [item["series_name"] for item in discovery["algorithm_series"] if not item["available"]]
    write_md(
        args.output_dir / "n9a_r2_algorithm_output_discovery.md",
        "N9A R2 Algorithm Output Discovery",
        [
            f"- available_algorithm_series_count: `{discovery['available_algorithm_series_count']}`",
            f"- found: `{', '.join(found) if found else 'none'}`",
            f"- missing: `{', '.join(missing)}`",
            "- formal ablation plot variants are not counted as BY2_normal_clean cases.",
        ],
    )
    write_md(
        args.summary_dir / "n9a_r2_decision_summary.md",
        "N9A R2 Decision",
        [
            f"- status: `{decision['status']}`",
            f"- ready_for_N9B: `{decision['ready_for_N9B']}`",
            f"- recommended_next_stage: `{decision['recommended_next_stage']}`",
            "- N9A_R2 does not run N9B and does not change algorithms.",
        ],
    )
    write_md(
        args.index_output_dir / "n9a_r2_figure_index.md",
        "N9A R2 Figure Index",
        [f"- `{item['category']}/{item['filename']}`: present=`{item['present']}`, source_type=`{item['source_type']}`" for item in plot_report["inventory"]],
    )
    write_md(
        args.output_dir / "n9a_r2_category_status.md",
        "N9A R2 Category Status",
        [f"- `{item['category']}`: `{item['status']}`" for item in category_report["categories"]],
    )


def write_case_review(args: R2Args, discovery: dict[str, Any], inventory: list[dict[str, Any]]) -> None:
    args.case_review_dir.mkdir(parents=True, exist_ok=True)
    found = [item for item in discovery["algorithm_series"] if item["available"]]
    missing = [item for item in discovery["algorithm_series"] if not item["available"]]
    write_md(
        args.case_review_dir / "case_review.md",
        f"{CASE_NAME} N9A R2 Case Review",
        [
            "- N9A_R1 source lineage is acknowledged but not sufficient for real plot completion.",
            f"- real algorithm outputs found: `{len(found)}`.",
            f"- real algorithm outputs missing: `{len(missing)}`.",
            "- trace remains reference/evaluation only.",
            "- source/proxy figures are excluded from algorithm completion.",
        ],
    )
    csv_path = args.case_review_dir / "case_key_metrics_table.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["series_name", "available", "row_count_nav", "row_count_eval", "row_count_std", "missing_reason"])
        for item in discovery["algorithm_series"]:
            writer.writerow([item["series_name"], item["available"], item["row_count_nav"], item["row_count_eval"], item["row_count_std"], item["missing_reason"]])
    write_md(args.case_review_dir / "case_recommended_figures.md", f"{CASE_NAME} Recommended Figures", ["- Complete only figures backed by real algorithm NAV/EVAL/STD outputs."])


def case_review_entries(args: R2Args) -> list[dict[str, Any]]:
    entries = []
    for filename in R2_CATEGORY_SCHEMA["09_case_review"]:
        path = args.case_review_dir / filename
        entries.append(base_entry("09_case_review", filename, path, True, "case review artifact", source_type="case_review", completion_eligible=True, plot_kind="document"))
    return entries


def write_pointer(args: R2Args) -> None:
    POINTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        POINTER_PATH,
        {
            "stage": STAGE,
            "report_output_dir": str(args.output_dir),
            "figure_output_dir": str(args.figure_output_dir),
            "case_review_dir": str(args.case_review_dir),
            "summary_dir": str(args.summary_dir),
            "index_output_dir": str(args.index_output_dir),
        },
    )


def audit_table(path: Path, role: str) -> dict[str, Any]:
    if not path or not path.exists():
        return missing_source(path.name if path else role, role)
    rows = count_data_rows(path)
    header = table_header(path)
    return {
        "path": str(path),
        "path_role": f"<{role.upper()}>",
        "data_role": role,
        "exists": True,
        "row_count": rows,
        "header": header[:80],
        "time_column": time_key(header),
        "time_monotonic": table_time_monotonic(path, header),
        "nan_inf_count": table_nan_inf_count(path),
    }


def audit_text(path: Path, role: str) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": str(path),
        "path_role": f"<{role.upper()}>",
        "data_role": role,
        "exists": exists,
        "row_count": count_data_rows(path) if exists else 0,
        "time_monotonic": True if exists else False,
    }


def missing_source(name: str, role: str) -> dict[str, Any]:
    return {"path": name, "path_role": f"<{role.upper()}>", "data_role": role, "exists": False, "row_count": 0, "header": [], "time_monotonic": False, "nan_inf_count": 0}


def read_table_rows(path: Path, limit: int = 2000) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        first = handle.readline()
        handle.seek(0)
        if first.startswith("#"):
            header = first.lstrip("#").strip().replace(",", " ").split()
            rows = []
            for raw in handle.readlines()[1:]:
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                values = raw.strip().replace(",", " ").split()
                rows.append({key: coerce(values[index]) if index < len(values) else "" for index, key in enumerate(header)})
                if len(rows) >= limit:
                    break
            return rows
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append({key: coerce(value) for key, value in row.items()})
            if len(rows) >= limit:
                break
        return rows


def read_go2_rows(path: Path, limit: int = 2000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            parts = raw.replace(",", " ").split()
            rows.append({f"col{index}": coerce(value) for index, value in enumerate(parts)})
            if len(rows) >= limit:
                break
    return rows


def table_header(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        first = handle.readline().strip()
    if first.startswith("#"):
        return first.lstrip("#").strip().replace(",", " ").split()
    return [item.strip() for item in first.split(",")]


def count_data_rows(path: Path | None) -> int:
    if not path or not path.exists() or not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        first = True
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if first:
                first = False
                if line.startswith("#") or any(ch.isalpha() for ch in line):
                    continue
            if line.startswith("#"):
                continue
            count += 1
    return count


def file_nonempty(value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    return path.exists() and path.is_file() and path.stat().st_size > 0


def table_time_monotonic(path: Path, header: list[str]) -> bool:
    key = time_key(header)
    if not key:
        return True
    previous: float | None = None
    for row in read_table_rows(path, limit=2000):
        value = safe_float(row.get(key), float("nan"))
        if not math.isfinite(value):
            continue
        if previous is not None and value < previous:
            return False
        previous = value
    return True


def table_nan_inf_count(path: Path) -> int:
    count = 0
    for row in read_table_rows(path, limit=200):
        for value in row.values():
            if str(value).strip().lower() in {"nan", "inf", "-inf"}:
                count += 1
    return count


def add_enu(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    lat0 = value_for(rows[0], ["lat_deg", "lat", "latitude"])
    lon0 = value_for(rows[0], ["lon_deg", "lon", "longitude"])
    h0 = value_for(rows[0], ["height_m", "height", "height_msl"])
    cos_lat = math.cos(math.radians(lat0)) or 1.0
    for row in rows:
        lat = value_for(row, ["lat_deg", "lat", "latitude"], lat0)
        lon = value_for(row, ["lon_deg", "lon", "longitude"], lon0)
        row["north_m"] = (lat - lat0) * 111_320.0
        row["east_m"] = (lon - lon0) * 111_320.0 * cos_lat
        row["up_m"] = value_for(row, ["height_m", "height", "height_msl"], h0) - h0


def velocity_source_roles(data: dict[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    if data["gnss1"]:
        roles["receiver_velocity.png"] = "receiver_status_velocity"
    if any(data["nav"].values()):
        roles["velocity_residual.png"] = "algorithm_nav_velocity"
        roles["velocity_delta_between_sources.png"] = "algorithm_nav_velocity"
    if data["go2"]:
        roles["go2_horizontal_velocity.png"] = "go2_highlevel_velocity"
    return roles


def yaw_from_status(row: dict[str, Any]) -> float:
    east = value_for(row, ["rel_pos_e", "baseline_e", "east"])
    north = value_for(row, ["rel_pos_n", "baseline_n", "north"])
    if east == 0.0 and north == 0.0:
        return value_for(row, ["yaw", "yaw_deg"])
    return math.degrees(math.atan2(east, north))


def value_for(row: dict[str, Any], keys: list[str], default: float = 0.0) -> float:
    for key in keys:
        if key in row:
            return safe_float(row.get(key), default)
    return default


def time_key(header: list[str]) -> str | None:
    for key in ["time", "Time", "timestamp", "stamp.secs", "header.stamp.secs"]:
        if key in header:
            return key
    return None


def coerce(value: Any) -> Any:
    if value is None:
        return ""
    text = str(value).strip()
    try:
        parsed = float(text)
    except ValueError:
        return text
    return parsed if math.isfinite(parsed) else text


def rmse(values: Iterable[float]) -> float:
    clean = [abs(float(value)) for value in values if math.isfinite(float(value))]
    if not clean:
        return 0.0
    return math.sqrt(sum(value * value for value in clean) / len(clean))


def percentile(values: Iterable[float], q: float) -> float:
    clean = sorted(abs(float(value)) for value in values if math.isfinite(float(value)))
    if not clean:
        return 0.0
    index = int(round((len(clean) - 1) * max(0.0, min(1.0, q))))
    return clean[index]


def save_fig(fig: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def find_first_existing(root: Path, names: list[str]) -> Path | None:
    if not root.exists():
        return None
    wanted = {name.lower() for name in names}
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() in wanted:
            return path
    return None


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if not path:
            continue
        key = str(path)
        if key and key not in seen:
            seen.add(key)
            result.append(path)
    return result


def write_md(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def build_args(namespace: argparse.Namespace) -> R2Args:
    return R2Args(
        by2_plot_root=Path(namespace.by2_plot_root),
        n8k_tag=namespace.n8k_tag,
        by2_fixposition_root=Path(namespace.by2_fixposition_root),
        gnss1_raw=Path(namespace.gnss1_raw),
        gnss2_raw=Path(namespace.gnss2_raw),
        gnss1_status=Path(namespace.gnss1_status),
        gnss2_status=Path(namespace.gnss2_status),
        trace_truth=Path(namespace.trace_truth),
        go2_body_imu_highlevel=Path(namespace.go2_body_imu_highlevel),
        algorithm_output_search_roots=tuple(Path(item) for item in namespace.algorithm_output_search_root),
        clean_replay_root=Path(namespace.clean_replay_root),
        dual_final_v23_artifact_root=Path(namespace.dual_final_v23_artifact_root),
        legsa_run_root=Path(namespace.legsa_run_root),
        output_dir=Path(namespace.output_dir),
        figure_output_dir=Path(namespace.figure_output_dir),
        case_review_dir=Path(namespace.case_review_dir),
        summary_dir=Path(namespace.summary_dir),
        index_output_dir=Path(namespace.index_output_dir),
    )
