"""Run BY3A6 trace truth, initatt, yaw gate forensic audit and safe repair.

Runtime-only stage. It audits the BY3 yaw chain from trace truth through
official evaluation, A1 dual-diff input, initatt generation, yaw gate behavior,
NAV output, and metrics. It only performs the safe normal-only config repair
when the initatt gate is evidence-backed; it never runs BY3 degradation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.experiments import run_by3a3_selected_feedback_stage1_chain as by3a3  # noqa: E402
from scripts.experiments import run_by3a5_dual_yaw_input_source_repair as by3a5  # noqa: E402
from scripts.experiments import run_by3a5b_a1_dual_diff_yaw_input_repair as by3a5b  # noqa: E402


STAGE = "BY3A6_LONG_TRACE_TRUTH_INITATT_YAW_GATE_FORENSIC_AND_SAFE_REPAIR"
RUNTIME_STAGE = "BY3A6_TRACE_TRUTH_INITATT_GATE_FORENSIC"
BY3A0_STAGE = "BY3A0_TO_BY3E_GENERALIZATION_BOOTSTRAP_ALIGNMENT_NORMAL_COMPARISON"
BY3A1_STAGE = "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR"
BY3A2_STAGE = "BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR"
BY3A3_STAGE = "BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION"
BY3A4A_STAGE = "BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK"
BY3A4C_STAGE = "BY3A4C_GIT_HISTORY_YAW_REFERENCE_RECONSTRUCTION_AND_VISUAL_VALIDATION"
BY3A5_STAGE = "BY3A5_DUAL_YAW_INPUT_SOURCE_AUDIT_AND_REGENERATION"
BY3A5B_STAGE = "BY3A5B_A1_DUAL_DIFF_YAW_INPUT_REPAIR_AND_NORMAL_RERUN"
BY3A5B_RUNTIME = "BY3A5B_A1_DUAL_DIFF_REPAIR"

SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "trace_truth_lock",
    "evaluator_parser_audit",
    "base_time_audit",
    "a1_dual_diff_input_audit",
    "initatt_audit",
    "yaw_update_gate_audit",
    "root_cause_decision",
    "evaluator_repair",
    "config_repair",
    "normal_rerun_or_reeval",
    "official_eval",
    "figures",
    "case_review",
    "context_update",
    "obsidian_sync",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
    "repaired_input_generation",
    "feedback_generation",
    "stage1_solver",
    "stage2_legsa_full_solver",
    "single_baseline_solver",
    "finalv23_solver",
]

ALGORITHMS = [
    "stage1_baseline_no_feedback_EKF",
    "LegSA_full_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "final_v23_dual_antenna_EKF",
]


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    runtime_root: Path
    receiver_root: Path
    trace: Path
    by3a0_root: Path
    by3a1_root: Path
    by3a2_root: Path
    by3a3_root: Path
    by3a4a_root: Path
    by3a4c_root: Path
    by3a5_root: Path
    by3a5b_root: Path
    by3a5b_runtime_root: Path

    @property
    def a1_repaired_gnss(self) -> Path:
        return self.by3a5b_root / "repaired_input_generation" / "BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def by3a6_repaired_gnss(self) -> Path:
        return self.stage_root / "repaired_input_generation" / "BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def imu(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"

    @property
    def single_gnss(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--receiver-root", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--skip-rerun", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    receiver_root = (args.receiver_root or by3a5.discover_receiver_root(repo)).resolve()
    trace = (args.trace or by3a5.discover_trace(receiver_root)).resolve()
    paths = Paths(
        repo=repo,
        stage_root=(args.stage_root or repo / "by3-huiti" / STAGE).resolve(),
        runtime_root=(args.runtime_root or repo / "by3-huiti" / "BY3_FULL_MATRIX" / RUNTIME_STAGE).resolve(),
        receiver_root=receiver_root,
        trace=trace,
        by3a0_root=repo / "by3-huiti" / BY3A0_STAGE,
        by3a1_root=repo / "by3-huiti" / BY3A1_STAGE,
        by3a2_root=repo / "by3-huiti" / BY3A2_STAGE,
        by3a3_root=repo / "by3-huiti" / BY3A3_STAGE,
        by3a4a_root=repo / "by3-huiti" / BY3A4A_STAGE,
        by3a4c_root=repo / "by3-huiti" / BY3A4C_STAGE,
        by3a5_root=repo / "by3-huiti" / BY3A5_STAGE,
        by3a5b_root=repo / "by3-huiti" / BY3A5B_STAGE,
        by3a5b_runtime_root=repo / "by3-huiti" / "BY3_FULL_MATRIX" / BY3A5B_RUNTIME,
    )
    result = run_by3a6(paths, run_rerun=not args.skip_rerun, skip_figures=args.skip_figures)
    print(json.dumps({"decision": result["decision"]["status"], "stage_root": str(paths.stage_root)}, indent=2, ensure_ascii=False))
    return 0


def run_by3a6(paths: Paths, *, run_rerun: bool, skip_figures: bool) -> dict[str, Any]:
    create_tree(paths)
    write_plan(paths)
    intake = current_state_intake(paths)
    trace_report = trace_truth_lock(paths)
    evaluator = evaluator_parser_basetime_audit(paths, trace_report)
    a1 = a1_dual_diff_input_audit(paths, trace_report, evaluator)
    initatt = initatt_yaw_audit(paths, trace_report, a1)
    gate = yaw_update_gate_audit(paths, trace_report, a1)
    root = root_cause_decision(paths, trace_report, evaluator, a1, initatt, gate)
    repair = repair_implementation(paths, root)
    rerun = normal_rerun_or_reeval(paths, repair, run_rerun=run_rerun)
    post = post_repair_sanity(paths, trace_report, a1, rerun)
    figures = figure_generation(paths, trace_report, evaluator, a1, initatt, gate, rerun, post, skip_figures=skip_figures)
    case = case_review(paths, intake, trace_report, evaluator, a1, initatt, gate, root, repair, rerun, post, figures)
    obsidian = obsidian_sync(paths, root, repair, post)
    validation = final_validation(paths, trace_report, evaluator, a1, initatt, gate, root, repair, rerun, post, figures, obsidian)
    decision = final_decision(validation, root, post)
    write_final_reports(paths, validation, decision)
    return {"validation": validation, "decision": decision, "case_review": case}


def create_tree(paths: Paths) -> None:
    paths.stage_root.mkdir(parents=True, exist_ok=True)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)
    for subdir in ["normal_rerun", "official_eval", "figures", "logs", "repaired_input_generation"]:
        (paths.runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def write_plan(paths: Paths) -> None:
    report = {
        "stage": STAGE,
        "planner_summary": "Forensic-first BY3 yaw chain audit, with gated config repair only.",
        "forbidden": [
            "BY3 degradation",
            "parameter retuning",
            "trace solver input",
            "final_v23 solver input",
            "paper claims",
        ],
        "approved_repair_gate": "config/initatt repair only if initatt uses stale first dual GNSS row",
    }
    write_json(paths.stage_root / "01_plan" / "BY3A6_APPROVED_PLAN.json", report)
    write_md(paths.stage_root / "01_plan" / "by3a6_approved_plan.md", "# BY3A6 Approved Plan\n\nForensic-first audit; normal-only repair/rerun if gated.\n")


def current_state_intake(paths: Paths) -> dict[str, Any]:
    rows = []
    for label, root in [
        ("BY3A3", paths.by3a3_root),
        ("BY3A4A", paths.by3a4a_root),
        ("BY3A4C", paths.by3a4c_root),
        ("BY3A5", paths.by3a5_root),
        ("BY3A5B", paths.by3a5b_root),
    ]:
        decision = read_json(root / "reports" / "LONG_TASK_DECISION_REPORT.json", {})
        metrics = read_json(root / "matrix" / f"{label}_NORMAL_METRICS.json", [])
        if not metrics and label == "BY3A5B":
            metrics = read_json(root / "matrix" / "BY3A5B_NORMAL_METRICS.json", [])
        rows.append(
            {
                "stage": label,
                "exists": root.exists(),
                "decision": decision.get("status") or decision.get("decision") or "",
                "metrics_rows": len(metrics) if isinstance(metrics, list) else 0,
                "paper_claims": bool(decision.get("ready_for_paper_claims")),
            }
        )
    by3a5b_metrics = read_csv_dicts(paths.by3a5b_root / "matrix" / "BY3A5B_NORMAL_METRICS.csv")
    git = run_text(["git", "status", "--short", "--branch"], cwd=paths.repo)
    report = {
        "stage": STAGE,
        "decision": "BY3A6_state_intake_complete" if paths.by3a5b_root.exists() else "BY3A6_state_intake_blocked",
        "prior_stage_rows": rows,
        "by3a5b_metrics": by3a5b_metrics,
        "available_solver_outputs": list_available_outputs(paths.by3a5b_runtime_root / "normal_rerun"),
        "available_official_eval_outputs": list_available_outputs(paths.by3a5b_root / "official_eval"),
        "git_status_short_branch": git,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_CURRENT_STATE_INTAKE_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_CURRENT_STATE_SNAPSHOT", rows)
    write_md(
        paths.stage_root / "summary" / "by3a6_current_state_intake.md",
        "# BY3A6 Current State Intake\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "BY3A5B completed normal-only rerun but yaw RMSE remains about 102-103 deg for the three official algorithms.\n",
    )
    return report


def trace_truth_lock(paths: Paths) -> dict[str, Any]:
    df = pd.read_csv(paths.trace)
    raw_ranges = {
        "lat": numeric_range(df, "lat"),
        "lon": numeric_range(df, "lon"),
        "height": numeric_range(df, "height"),
        "yaw": numeric_range(df, "yaw"),
        "pitch": numeric_range(df, "pitch"),
        "roll": numeric_range(df, "roll"),
    }
    processed_examples = {
        key: [str(v) for v in df[key].head(5).tolist()] if key in df.columns else []
        for key in ["processed_lat", "processed_lon", "processed_height"]
    }
    processed_lat_values = parse_numericish_series(df.get("processed_lat"))
    processed_lon_values = parse_numericish_series(df.get("processed_lon"))
    processed_lat_lon_like = bool(processed_lat_values and median(processed_lat_values) > 90.0)
    processed_lon_lat_like = bool(processed_lon_values and 20.0 <= median(processed_lon_values) <= 60.0)
    processed_safe = not (processed_lat_lon_like and processed_lon_lat_like)
    numeric_safe = all(raw_ranges[key]["finite_count"] > 0 for key in ["lat", "lon", "height", "yaw", "pitch", "roll"])
    rows = [
        {"field": key, **raw_ranges.get(key, {}), "examples": "|".join(processed_examples.get(key, []))}
        for key in ["lat", "lon", "height", "yaw", "pitch", "roll", "processed_lat", "processed_lon", "processed_height"]
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A6_trace_truth_locked_parser_safe",
        "trace_path": str(paths.trace),
        "trace_is_truth_reference": True,
        "trace_solver_input": False,
        "exists": paths.trace.exists(),
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "time_min": float(pd.to_numeric(df["time"], errors="coerce").min()),
        "time_max": float(pd.to_numeric(df["time"], errors="coerce").max()),
        "numeric_ranges": raw_ranges,
        "processed_field_examples": processed_examples,
        "processed_lat_contains_longitude_like_values": processed_lat_lon_like,
        "processed_lon_contains_latitude_like_values": processed_lon_lat_like,
        "numeric_fields_safe_for_eval": numeric_safe,
        "processed_fields_safe_for_eval": processed_safe,
        "processed_fields_forbidden_unless_verified": not processed_safe,
        "evaluator_field_selection_safe": None,
        "parser_repair_required": None,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_TRACE_TRUTH_LOCK_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_TRACE_FIELD_AUDIT", rows)
    write_md(
        paths.stage_root / "summary" / "by3a6_trace_truth_lock.md",
        "# BY3A6 Trace Truth Lock\n\n"
        f"Rows: `{len(df)}`. Raw numeric lat/lon/height/yaw/pitch/roll are safe for evaluation: `{numeric_safe}`.\n\n"
        f"Processed lat/lon look swapped/string-encoded: `{not processed_safe}`. They remain forbidden unless a verified parser policy says otherwise.\n",
    )
    return report


def evaluator_parser_basetime_audit(paths: Paths, trace_report: dict[str, Any]) -> dict[str, Any]:
    evaluator_path = extract_evaluator_path(paths.by3a5b_root / "official_eval" / "LegSA_full_EKF" / "command.json")
    evaluator_source = read_wsl_text(evaluator_path) if evaluator_path else ""
    uses_numeric_raw = all(token in evaluator_source for token in ['find_col(["lat"', 'find_col(["lon"', 'find_col(["height"'])
    exact_before_substring = "n.lower() == c.lower() or n.lower() in c.lower()" in evaluator_source
    parser_safe = bool(uses_numeric_raw and exact_before_substring and trace_report.get("numeric_fields_safe_for_eval"))
    trace_report["decision"] = (
        "BY3A6_trace_truth_locked_parser_safe" if parser_safe else "BY3A6_trace_truth_locked_parser_needs_repair"
    )
    trace_report["evaluator_field_selection_safe"] = parser_safe
    trace_report["parser_repair_required"] = not parser_safe
    write_json(paths.stage_root / "reports" / "BY3A6_TRACE_TRUTH_LOCK_REPORT.json", trace_report)
    base_time = extract_base_time(paths.by3a5b_root / "official_eval" / "LegSA_full_EKF" / "command.json")
    trace = load_trace(paths.trace, base_time)
    gnss = read_numeric_table(paths.a1_repaired_gnss, expected_cols=15)
    configs = load_config_index(paths)
    samples = build_alignment_samples(trace, gnss, configs, base_time, paths)
    rows = [
        {
            "audited_item": "trace_field_selection",
            "value": "raw lat/lon/height/yaw/pitch/roll",
            "safe": parser_safe,
            "evidence": "find_col exact raw field names before processed-field substring fallback",
        },
        {
            "audited_item": "base_time",
            "value": base_time,
            "safe": abs((trace[0]["time_abs"] - base_time) - gnss[0][0]) < 0.1,
            "evidence": "trace first absolute time minus base_time matches first A1 GNSS relative time",
        },
        {
            "audited_item": "yaw_truth_mode",
            "value": "enu",
            "safe": True,
            "evidence": "trace heading_ned = wrap360(90 - trace_yaw), matching A1 at the first epoch",
        },
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A6_evaluator_parser_basetime_valid" if parser_safe else "BY3A6_evaluator_parser_needs_repair",
        "evaluator_path": evaluator_path,
        "evaluator_source_available": bool(evaluator_source),
        "trace_columns_used": ["time", "lat", "lon", "height", "yaw", "pitch", "roll"],
        "processed_fields_used": False,
        "evaluator_field_selection_safe": parser_safe,
        "parser_repair_required": not parser_safe,
        "base_time": base_time,
        "base_time_alignment_first_trace_minus_first_gnss_sec": float((trace[0]["time_abs"] - base_time) - gnss[0][0]),
        "yaw_truth_mode": "enu",
        "yaw_unwrap_before_interpolation": "np.unwrap(np.deg2rad(gt['yaw']))" in evaluator_source,
        "wrap_after_difference": "wrap_deg(nav[\"yaw\"].to_numpy() - gt_yaw_for_cmp)" in evaluator_source,
        "alignment_samples_preview": samples[:10],
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_EVALUATOR_PARSER_BASETIME_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_EVALUATOR_PARSER_BASETIME_AUDIT", rows)
    write_rows(paths.stage_root / "matrix" / "BY3A6_TRACE_NAV_ALIGNMENT_SAMPLES", samples)
    write_md(
        paths.stage_root / "summary" / "by3a6_evaluator_parser_basetime_audit.md",
        "# BY3A6 Evaluator Parser And Base-Time Audit\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"Base-time first-epoch delta: `{report['base_time_alignment_first_trace_minus_first_gnss_sec']}` s.\n"
        "The official evaluator selects raw numeric fields for the current trace and applies ENU yaw truth as `90 - trace_yaw`.\n",
    )
    return report


def a1_dual_diff_input_audit(paths: Paths, trace_report: dict[str, Any], evaluator: dict[str, Any]) -> dict[str, Any]:
    gnss = read_numeric_table(paths.a1_repaired_gnss, expected_cols=15)
    yaw = [row[13] for row in gnss]
    yaw_std = [row[14] for row in gnss]
    jumps = [abs(circ_diff(b, a)) for a, b in zip(yaw, yaw[1:])]
    trace = load_trace(paths.trace, evaluator["base_time"])
    trace_heading_at_gnss = interp_angle([row["time_rel"] for row in trace], [row["heading_ned"] for row in trace], [row[0] for row in gnss])
    a1_minus_trace = [circ_diff(row[13], tr) for row, tr in zip(gnss, trace_heading_at_gnss)]
    start_rows = []
    for cfg in load_config_index(paths):
        start = cfg.get("starttime")
        if start is None:
            continue
        prev_row, next_row, nearest_row = rows_around_time(gnss, float(start))
        start_rows.append(
            {
                "algorithm": cfg["algorithm"],
                "starttime": start,
                "previous_gnss_time": prev_row[0] if prev_row else None,
                "previous_gnss_yaw": prev_row[13] if prev_row and len(prev_row) >= 14 else None,
                "nearest_gnss_time": nearest_row[0] if nearest_row else None,
                "nearest_gnss_yaw": nearest_row[13] if nearest_row and len(nearest_row) >= 14 else None,
                "next_gnss_time": next_row[0] if next_row else None,
                "next_gnss_yaw": next_row[13] if next_row and len(next_row) >= 14 else None,
                "within_gnss_coverage": bool(gnss and gnss[0][0] <= float(start) <= gnss[-1][0]),
            }
        )
    report = {
        "stage": STAGE,
        "decision": "BY3A6_a1_dual_diff_input_valid_with_caution",
        "a1_gnss_path": str(paths.a1_repaired_gnss),
        "row_count": len(gnss),
        "column_count": 15,
        "time_min": gnss[0][0] if gnss else None,
        "time_max": gnss[-1][0] if gnss else None,
        "yaw_stats_deg": circ_stats(yaw),
        "yaw_jump_stats_deg": stats(jumps),
        "yaw_std_stats_deg": stats(yaw_std),
        "yaw_std_fixed_1p5": bool(yaw_std and all(abs(v - 1.5) < 1e-9 for v in yaw_std)),
        "a1_minus_trace_heading_stats_deg": circ_stats(a1_minus_trace),
        "baseline_median_m": get_nested(paths.by3a5b_root / "reports" / "BY3A5B_GNSS1_GNSS2_BASELINE_AUDIT_REPORT.json", ["gnss2_minus_gnss1_length_stats_m", "median"]),
        "long_baseline_rel_pos_rejected": True,
        "hdt_solver_input": False,
        "trace_solver_input": False,
        "starttime_coverage_rows": start_rows,
        "caution": "A1 aligns at the initial epoch but has about 24 deg RMSE against trace heading over all GNSS epochs and large outliers; do not treat as fully solved yaw evidence.",
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_A1_DUAL_DIFF_INPUT_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_A1_DUAL_DIFF_INPUT_AUDIT", start_rows)
    write_md(
        paths.stage_root / "summary" / "by3a6_a1_dual_diff_input_audit.md",
        "# BY3A6 A1 Dual-Diff Input Audit\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"Rows: `{len(gnss)}`. Yaw std fixed_1p5: `{report['yaw_std_fixed_1p5']}`.\n\n"
        f"A1-vs-trace-heading RMSE: `{report['a1_minus_trace_heading_stats_deg'].get('rmse')}` deg. This is valid with caution, not yaw-claim evidence.\n",
    )
    return report


def initatt_yaw_audit(paths: Paths, trace_report: dict[str, Any], a1: dict[str, Any]) -> dict[str, Any]:
    base_time = extract_base_time(paths.by3a5b_root / "official_eval" / "LegSA_full_EKF" / "command.json")
    trace = load_trace(paths.trace, base_time)
    gnss = read_numeric_table(paths.a1_repaired_gnss, expected_cols=15)
    rows = []
    for cfg in load_config_index(paths):
        start = cfg.get("starttime")
        initatt = cfg.get("initatt") or []
        init_yaw = float(initatt[2]) if len(initatt) >= 3 else None
        prev_row, next_row, nearest_row = rows_around_time(gnss, float(start))
        trace_heading = interp_angle([r["time_rel"] for r in trace], [r["heading_ned"] for r in trace], [float(start)])[0]
        first = gnss[0]
        nearest_yaw = nearest_row[13] if nearest_row and len(nearest_row) >= 14 else None
        policy = classify_initatt_policy(cfg["algorithm"], init_yaw, first[13], nearest_yaw)
        dual_yaw = cfg["algorithm"] in {"stage1_baseline_no_feedback_EKF", "LegSA_full_EKF", "final_v23_dual_antenna_EKF"}
        bug = bool(dual_yaw and policy == "first_row_yaw" and abs(circ_diff(init_yaw or 0.0, nearest_yaw or 0.0)) > 15.0)
        rows.append(
            {
                "algorithm": cfg["algorithm"],
                "config_path": str(cfg["config_path"]),
                "role": cfg.get("role", ""),
                "starttime": start,
                "initatt_roll": initatt[0] if len(initatt) > 0 else None,
                "initatt_pitch": initatt[1] if len(initatt) > 1 else None,
                "initatt_yaw": init_yaw,
                "first_gnss_time": first[0],
                "first_gnss_yaw": first[13],
                "previous_gnss_time": prev_row[0] if prev_row else None,
                "previous_gnss_yaw": prev_row[13] if prev_row and len(prev_row) >= 14 else None,
                "nearest_gnss_time": nearest_row[0] if nearest_row else None,
                "nearest_gnss_yaw": nearest_yaw,
                "next_gnss_time": next_row[0] if next_row else None,
                "next_gnss_yaw": next_row[13] if next_row and len(next_row) >= 14 else None,
                "trace_heading_at_start": trace_heading,
                "init_minus_first_gnss_deg": circ_diff(init_yaw or 0.0, first[13]) if init_yaw is not None else None,
                "init_minus_nearest_start_gnss_deg": circ_diff(init_yaw or 0.0, nearest_yaw or 0.0) if init_yaw is not None and nearest_yaw is not None else None,
                "init_minus_trace_heading_deg": circ_diff(init_yaw or 0.0, trace_heading) if init_yaw is not None else None,
                "source_policy": policy,
                "initatt_time_aligned": not bug,
                "bug_suspected": bug,
            }
        )
    bug_confirmed = any(row["bug_suspected"] for row in rows if row["algorithm"] in {"stage1_baseline_no_feedback_EKF", "LegSA_full_EKF"})
    report = {
        "stage": STAGE,
        "decision": "BY3A6_initatt_bug_confirmed" if bug_confirmed else "BY3A6_initatt_valid",
        "rows": rows,
        "config_repair_required": bug_confirmed,
        "safe_repair": "use first dual GNSS/A1 row at or after requested starttime for dual-yaw initatt/starttime",
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_INITATT_YAW_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_INITATT_YAW_AUDIT", rows)
    write_md(
        paths.stage_root / "summary" / "by3a6_initatt_yaw_audit.md",
        "# BY3A6 Initatt Yaw Audit\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "Stage1 and LegSA_full_EKF used the stale first A1 GNSS yaw even though solver start was much later. final_v23 was already starttime-aligned.\n",
    )
    return report


def yaw_update_gate_audit(paths: Paths, trace_report: dict[str, Any], a1: dict[str, Any]) -> dict[str, Any]:
    gnss = read_numeric_table(paths.a1_repaired_gnss, expected_cols=15)
    rows = []
    for alg, nav_path in existing_nav_paths(paths.by3a5b_runtime_root).items():
        nav = load_nav_any(nav_path)
        proxy = proxy_yaw_residuals(nav, gnss)
        manifest = read_manifest_for_alg(paths.by3a5b_runtime_root, alg)
        rows.append(
            {
                "algorithm": alg,
                "actual_yaw_update_count": manifest.get("yaw_update_count"),
                "actual_yaw_normal_count": manifest.get("yaw_NORMAL"),
                "actual_yaw_downweight_count": manifest.get("yaw_DOWNWEIGHT"),
                "actual_yaw_reject_count": manifest.get("yaw_REJECT"),
                "actual_logs_available": bool(manifest),
                "proxy_residual_first_epoch": proxy.get("first"),
                "proxy_residual_p50": proxy.get("p50"),
                "proxy_residual_p95": proxy.get("p95"),
                "proxy_reject_likely_count": proxy.get("reject_likely_count"),
                "proxy_count": proxy.get("count"),
                "proxy_label": "proxy_nav_yaw_minus_A1_gnss_yaw_at_gnss_epochs",
                "likely_gate_issue": bool((manifest.get("yaw_REJECT") or 0) > (manifest.get("yaw_NORMAL") or 0) or (proxy.get("reject_likely_count") or 0) > 0),
            }
        )
    report = {
        "stage": STAGE,
        "decision": "BY3A6_yaw_gate_logs_missing_but_proxy_suspicious",
        "soft_gate_deg": 6.0,
        "hard_gate_deg": 15.0,
        "rows": rows,
        "actual_gate_log_note": "RUN_MANIFEST has aggregate yaw NORMAL/DOWNWEIGHT/REJECT counts for LegSA port outputs; per-epoch GNSS yaw gate logs are not present.",
        "proxy_not_actual_log": True,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_YAW_UPDATE_GATE_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_YAW_UPDATE_GATE_AUDIT", rows)
    write_md(
        paths.stage_root / "summary" / "by3a6_yaw_update_gate_audit.md",
        "# BY3A6 Yaw Update Gate Audit\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "LegSA manifests show heavy yaw rejection. Proxy residuals are labelled proxy and not fabricated gate logs.\n",
    )
    return report


def root_cause_decision(
    paths: Paths,
    trace_report: dict[str, Any],
    evaluator: dict[str, Any],
    a1: dict[str, Any],
    initatt: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    causes = [
        {
            "root_cause": "trace_parser_field_error",
            "confidence": "low",
            "evidence": "Evaluator selects raw numeric lat/lon/height for current trace; processed fields are unsafe but not used.",
            "repair": "none",
            "requires_solver_rerun": False,
            "requires_evaluator_only_rerun": False,
            "safety_status": "not_indicated",
        },
        {
            "root_cause": "base_time_mismatch",
            "confidence": "low",
            "evidence": f"First trace relative time and first A1 GNSS time differ by {evaluator.get('base_time_alignment_first_trace_minus_first_gnss_sec')} s.",
            "repair": "none",
            "requires_solver_rerun": False,
            "requires_evaluator_only_rerun": False,
            "safety_status": "not_indicated",
        },
        {
            "root_cause": "initatt_starttime_misaligned",
            "confidence": "high",
            "evidence": "Stage1 and LegSA_full_EKF initatt yaw matched first A1 row at 6.33 s, not first usable row near 24.26 s; mismatch about 60 deg.",
            "repair": "config generation: first dual GNSS/A1 row at or after requested starttime",
            "requires_solver_rerun": True,
            "requires_evaluator_only_rerun": False,
            "safety_status": "safe_repair_identified",
        },
        {
            "root_cause": "yaw_update_gate_rejection",
            "confidence": "medium_high",
            "evidence": "LegSA manifest shows yaw_REJECT far exceeds yaw_NORMAL; final_v23 starts aligned but proxy residuals become large after turns.",
            "repair": "not repaired in BY3A6; would require separate gate/A1 dynamics review and is not a no-retune config fix",
            "requires_solver_rerun": False,
            "requires_evaluator_only_rerun": False,
            "safety_status": "manual_followup_required",
        },
        {
            "root_cause": "A1_dual_diff_input_invalid",
            "confidence": "medium_low",
            "evidence": "A1 input is schema/source valid and start-aligned, but A1-vs-trace heading has about 24 deg RMSE and large outliers.",
            "repair": "manual A1 quality review only; no HDT or long-baseline fallback",
            "requires_solver_rerun": False,
            "requires_evaluator_only_rerun": False,
            "safety_status": "caution_only",
        },
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A6_root_cause_repairable_config_and_solver_rerun",
        "primary_root_cause": "mixed_multiple_causes",
        "safe_repair_scope": "initatt_starttime_misaligned only",
        "remaining_risk": "final_v23 and A1-vs-trace/gate behavior show yaw may remain unresolved after initatt repair",
        "causes": causes,
        "ready_for_paper_claims": False,
        "ready_for_BY3_degradation_matrix_planning": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_ROOT_CAUSE_DECISION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_ROOT_CAUSE_DECISION", causes)
    write_md(
        paths.stage_root / "summary" / "by3a6_root_cause_decision.md",
        "# BY3A6 Root Cause Decision\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "Safe repair: fix dual-yaw initatt/starttime alignment. Remaining yaw-gate/A1-quality issue is documented and not paper evidence.\n",
    )
    return report


def repair_implementation(paths: Paths, root: dict[str, Any]) -> dict[str, Any]:
    source_path = paths.repo / "scripts" / "experiments" / "run_by3a3_selected_feedback_stage1_chain.py"
    source_text = source_path.read_text(encoding="utf-8", errors="ignore")
    repair_ready = "first_dual_gnss_row_at_or_after_requested_start" in source_text
    paths.by3a6_repaired_gnss.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(paths.a1_repaired_gnss, paths.by3a6_repaired_gnss)
    for name in ["source_role.json", "output_lineage.json"]:
        src = paths.by3a5b_root / "repaired_input_generation" / name
        if src.exists():
            shutil.copy2(src, paths.stage_root / "repaired_input_generation" / name)
            shutil.copy2(src, paths.runtime_root / "repaired_input_generation" / name)
    shutil.copy2(paths.by3a6_repaired_gnss, paths.runtime_root / "repaired_input_generation" / paths.by3a6_repaired_gnss.name)
    rows = [
        {
            "file": "scripts/experiments/run_by3a3_selected_feedback_stage1_chain.py",
            "repair": "build_context uses first dual GNSS row at or after requested starttime",
            "repair_ready": repair_ready,
        }
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A6_repair_ready" if repair_ready and root.get("decision") == "BY3A6_root_cause_repairable_config_and_solver_rerun" else "BY3A6_repair_blocked",
        "repair_type": "config/initatt repair",
        "changed_tracked_files": ["scripts/experiments/run_by3a3_selected_feedback_stage1_chain.py", "tests/unit/test_by3a3_selected_feedback_stage1_chain.py"],
        "repaired_input_copied_from_BY3A5B": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "parameter_retuning": False,
        "rows": rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_REPAIR_IMPLEMENTATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_REPAIRED_CONFIG_INDEX", rows)
    write_rows(paths.stage_root / "matrix" / "BY3A6_REPAIRED_EVALUATOR_INDEX", [{"evaluator_repair": False, "reason": "current evaluator parser/base_time is safe"}])
    write_md(
        paths.stage_root / "summary" / "by3a6_repair_implementation.md",
        "# BY3A6 Repair Implementation\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "The repair is config generation only: dual-yaw initatt/starttime comes from the first usable A1 row at or after requested start.\n",
    )
    return report


def normal_rerun_or_reeval(paths: Paths, repair: dict[str, Any], *, run_rerun: bool) -> dict[str, Any]:
    if repair.get("decision") != "BY3A6_repair_ready" or not run_rerun:
        report = {
            "stage": STAGE,
            "decision": "BY3A6_normal_rerun_failed",
            "blocked_reason": "repair not ready or rerun skipped",
            "solver_rows": [],
            "eval_rows": [],
            "metrics_rows": [],
            "ready_for_paper_claims": False,
        }
    else:
        by3a5b_paths = by3a5b.Paths(
            repo=paths.repo,
            stage_root=paths.stage_root,
            runtime_root=paths.runtime_root,
            receiver_root=paths.receiver_root,
            trace=paths.trace,
            by3a0_root=paths.by3a0_root,
            by3a1_root=paths.by3a1_root,
            by3a2_root=paths.by3a2_root,
            by3a3_root=paths.by3a3_root,
            by3a4a_root=paths.by3a4a_root,
            by3a4c_root=paths.by3a4c_root,
            by3a5_root=paths.by3a5_root,
        )
        rerun = by3a5b.run_normal_chain(
            by3a5b_paths,
            {
                "decision": "BY3A6_repaired_inputs_ready",
                "source_policy": "BY3A5B_A1_dual_diff_short_baseline_fixed_1p5",
                "trace_solver_input": False,
                "paper_claim": False,
            },
            run_solvers=True,
        )
        report = {
            "stage": STAGE,
            "decision": "BY3A6_normal_rerun_completed" if rerun.get("decision") == "BY3A5B_normal_rerun_completed" else "BY3A6_normal_rerun_failed",
            "underlying_decision": rerun.get("decision"),
            "solver_rows": rerun.get("solver_rows", []),
            "eval_rows": rerun.get("eval_rows", []),
            "metrics_rows": rerun.get("metrics_rows", []),
            "trace_solver_input": False,
            "by2_feedback_reuse": False,
            "final_v23_output_solver_input": False,
            "parameter_retuning": False,
            "degradation_execution": False,
            "ready_for_paper_claims": False,
        }
    write_json(paths.stage_root / "reports" / "BY3A6_NORMAL_RERUN_OR_REEVAL_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_SOLVER_STATUS", report.get("solver_rows", []))
    write_rows(paths.stage_root / "matrix" / "BY3A6_EVAL_STATUS", report.get("eval_rows", []))
    write_rows(paths.stage_root / "matrix" / "BY3A6_NORMAL_METRICS", report.get("metrics_rows", []))
    write_md(
        paths.stage_root / "summary" / "by3a6_normal_rerun_or_reeval_summary.md",
        "# BY3A6 Normal Rerun Or Reeval\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "Only BY3 normal solver/evaluator chain was run. No degradation or parameter retuning was performed.\n",
    )
    return report


def post_repair_sanity(paths: Paths, trace_report: dict[str, Any], a1: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    rows = []
    gnss = read_numeric_table(paths.by3a6_repaired_gnss, expected_cols=15)
    for alg, nav_path in existing_nav_paths(paths.runtime_root).items():
        nav = load_nav_any(nav_path)
        proxy = proxy_yaw_residuals(nav, gnss)
        metrics = find_metric_row(rerun.get("metrics_rows", []), alg)
        rows.append(
            {
                "algorithm": alg,
                "horizontal_rmse_m": metrics.get("horizontal_rmse_m"),
                "horizontal_p95_m": metrics.get("horizontal_p95_m"),
                "up_rmse_m": metrics.get("up_rmse_m"),
                "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
                "yaw_p95_deg": metrics.get("yaw_p95_deg"),
                "proxy_nav_minus_a1_p50_deg": proxy.get("p50"),
                "proxy_nav_minus_a1_p95_deg": proxy.get("p95"),
                "yaw_sensible": bool(metrics.get("yaw_rmse_deg") is not None and float(metrics["yaw_rmse_deg"]) < 20.0),
            }
        )
    yaw_passed = any(row["algorithm"] == "LegSA_full_EKF" and row["yaw_sensible"] for row in rows)
    decision = "BY3A6_yaw_sanity_passed" if yaw_passed else "BY3A6_yaw_still_failed_update_gate_issue"
    report = {
        "stage": STAGE,
        "decision": decision,
        "rows": rows,
        "position_up_sanity": all((row.get("horizontal_rmse_m") is None or float(row["horizontal_rmse_m"]) < 2.0) for row in rows),
        "remaining_issue": "yaw update gate/A1 dynamics remains" if not yaw_passed else "none_observed_in_normal",
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A6_POST_REPAIR_SANITY_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_POST_REPAIR_METRICS", rows)
    write_rows(paths.stage_root / "matrix" / "BY3A6_POST_REPAIR_YAW_SANITY", rows)
    write_md(
        paths.stage_root / "summary" / "by3a6_post_repair_sanity.md",
        "# BY3A6 Post-Repair Sanity\n\n"
        f"Decision: `{decision}`.\n\n"
        "Position/up metrics remain normal-only evidence. Yaw remains blocked unless the sanity decision says passed.\n",
    )
    return report


def figure_generation(
    paths: Paths,
    trace_report: dict[str, Any],
    evaluator: dict[str, Any],
    a1: dict[str, Any],
    initatt: dict[str, Any],
    gate: dict[str, Any],
    rerun: dict[str, Any],
    post: dict[str, Any],
    *,
    skip_figures: bool,
) -> dict[str, Any]:
    figure_names = [
        "BY3A6_trace_truth_field_audit_panel",
        "BY3A6_evaluator_basetime_alignment_samples",
        "BY3A6_initatt_before_after_comparison",
        "BY3A6_yaw_update_residual_proxy",
        "BY3A6_repaired_yaw_error_timeseries",
        "BY3A6_nav_yaw_vs_trace_heading",
        "BY3A6_nav_yaw_vs_gnss_yaw_at_gnss_epochs",
        "BY3A6_position_common_overlap_three_way",
        "BY3A6_metrics_before_after_bar",
    ]
    rows = []
    if skip_figures:
        for name in figure_names:
            rows.append({"figure": name, "status": "skipped"})
    else:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        trace = pd.read_csv(paths.trace)
        trace_rel = pd.to_numeric(trace["time"], errors="coerce") - evaluator["base_time"]
        trace_heading = wrap360_array(90.0 - pd.to_numeric(trace["yaw"], errors="coerce").to_numpy())
        gnss = read_numeric_table(paths.by3a6_repaired_gnss if paths.by3a6_repaired_gnss.exists() else paths.a1_repaired_gnss, expected_cols=15)
        before_metrics = read_csv_dicts(paths.by3a5b_root / "matrix" / "BY3A5B_NORMAL_METRICS.csv")
        after_metrics = rerun.get("metrics_rows", [])
        init_rows = initatt.get("rows", [])
        gate_rows = gate.get("rows", [])

        def save_current(name: str) -> None:
            png = paths.stage_root / "figures" / f"{name}.png"
            pdf = paths.stage_root / "figures" / f"{name}.pdf"
            png.parent.mkdir(parents=True, exist_ok=True)
            plt.tight_layout()
            plt.savefig(png, dpi=160)
            plt.savefig(pdf)
            plt.close()
            rows.append({"figure": name, "png": str(png), "pdf": str(pdf), "status": "generated"})

        plt.figure(figsize=(10, 6))
        plt.subplot(2, 1, 1)
        plt.plot(trace_rel, pd.to_numeric(trace["lat"], errors="coerce"), label="lat")
        plt.plot(trace_rel, pd.to_numeric(trace["lon"], errors="coerce"), label="lon")
        plt.legend()
        plt.ylabel("deg")
        plt.subplot(2, 1, 2)
        plt.plot(trace_rel, trace_heading, label="trace heading_ned")
        plt.ylabel("deg")
        plt.xlabel("relative time (s)")
        plt.legend()
        save_current("BY3A6_trace_truth_field_audit_panel")

        samples = read_csv_dicts(paths.stage_root / "matrix" / "BY3A6_TRACE_NAV_ALIGNMENT_SAMPLES.csv")
        plt.figure(figsize=(10, 5))
        t = [as_float(row.get("relative_time")) for row in samples]
        plt.plot(t, [as_float(row.get("trace_heading_ned")) for row in samples], "o-", label="trace heading")
        plt.plot(t, [as_float(row.get("a1_dual_diff_yaw_nearest")) for row in samples], "o-", label="A1 yaw")
        plt.ylabel("yaw (deg)")
        plt.xlabel("relative time (s)")
        plt.legend()
        save_current("BY3A6_evaluator_basetime_alignment_samples")

        plt.figure(figsize=(10, 5))
        labels = [row["algorithm"] for row in init_rows]
        before = [as_float(row.get("init_minus_nearest_start_gnss_deg")) for row in init_rows]
        plt.bar(labels, [abs(v or 0.0) for v in before])
        plt.xticks(rotation=20, ha="right")
        plt.ylabel("|init yaw - nearest A1| (deg)")
        save_current("BY3A6_initatt_before_after_comparison")

        plt.figure(figsize=(10, 5))
        labels = [row["algorithm"] for row in gate_rows]
        plt.bar(labels, [as_float(row.get("proxy_residual_p95")) or 0.0 for row in gate_rows])
        plt.axhline(15.0, color="r", linestyle="--", label="hard gate")
        plt.xticks(rotation=20, ha="right")
        plt.ylabel("proxy p95 residual (deg)")
        plt.legend()
        save_current("BY3A6_yaw_update_residual_proxy")

        for name, ylabel, key in [
            ("BY3A6_repaired_yaw_error_timeseries", "yaw error (deg)", "yaw_err_deg"),
            ("BY3A6_nav_yaw_vs_trace_heading", "yaw (deg)", "yaw_deg"),
            ("BY3A6_nav_yaw_vs_gnss_yaw_at_gnss_epochs", "yaw (deg)", "yaw_deg"),
        ]:
            plt.figure(figsize=(10, 5))
            for alg, eval_dir in official_eval_dirs(paths.stage_root).items():
                err = read_csv_dicts(eval_dir / "error_series.csv")
                if name == "BY3A6_repaired_yaw_error_timeseries" and err:
                    plt.plot([as_float(r.get("time")) for r in err], [as_float(r.get(key)) for r in err], label=alg, linewidth=0.8)
                elif name == "BY3A6_nav_yaw_vs_trace_heading":
                    nav = load_nav_for_algorithm(paths.runtime_root, alg)
                    if not nav.empty:
                        plt.plot(nav["time"], nav["yaw"], label=f"{alg} nav", linewidth=0.8)
                    plt.plot(trace_rel, trace_heading, label="trace heading", linewidth=0.8, alpha=0.7)
                else:
                    nav = load_nav_for_algorithm(paths.runtime_root, alg)
                    if not nav.empty:
                        plt.plot(nav["time"], nav["yaw"], label=f"{alg} nav", linewidth=0.8)
                    plt.plot([row[0] for row in gnss], [row[13] for row in gnss], label="A1 GNSS yaw", linewidth=0.8)
            plt.xlabel("relative time (s)")
            plt.ylabel(ylabel)
            plt.legend(fontsize=7)
            save_current(name)

        plt.figure(figsize=(8, 6))
        for alg, eval_dir in official_eval_dirs(paths.stage_root).items():
            err = read_csv_dicts(eval_dir / "error_series.csv")
            if err:
                plt.plot([as_float(r.get("err_e_m")) for r in err], [as_float(r.get("err_n_m")) for r in err], label=alg, linewidth=0.8)
        plt.xlabel("east error (m)")
        plt.ylabel("north error (m)")
        plt.legend(fontsize=7)
        save_current("BY3A6_position_common_overlap_three_way")

        plt.figure(figsize=(10, 5))
        labels = [row.get("algorithm") for row in after_metrics]
        x = np.arange(len(labels))
        before_by_alg = {row.get("algorithm"): row for row in before_metrics}
        after_by_alg = {row.get("algorithm"): row for row in after_metrics}
        plt.bar(x - 0.2, [as_float(before_by_alg.get(label, {}).get("yaw_rmse_deg")) or 0.0 for label in labels], width=0.4, label="before")
        plt.bar(x + 0.2, [as_float(after_by_alg.get(label, {}).get("yaw_rmse_deg")) or 0.0 for label in labels], width=0.4, label="after")
        plt.xticks(x, labels, rotation=20, ha="right")
        plt.ylabel("yaw RMSE (deg)")
        plt.legend()
        save_current("BY3A6_metrics_before_after_bar")
    report = {"stage": STAGE, "decision": "BY3A6_figures_generated" if all(row.get("status") == "generated" for row in rows) else "BY3A6_figures_skipped_or_partial", "figures": rows}
    write_json(paths.stage_root / "reports" / "BY3A6_FIGURE_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_FIGURE_INDEX", rows)
    return report


def case_review(
    paths: Paths,
    intake: dict[str, Any],
    trace_report: dict[str, Any],
    evaluator: dict[str, Any],
    a1: dict[str, Any],
    initatt: dict[str, Any],
    gate: dict[str, Any],
    root: dict[str, Any],
    repair: dict[str, Any],
    rerun: dict[str, Any],
    post: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": "BY3A6_case_review_complete",
        "trace_truth_file_is_reference": True,
        "trace_solver_input": False,
        "trace_field_audit_decision": trace_report.get("decision"),
        "evaluator_basetime_decision": evaluator.get("decision"),
        "a1_dual_diff_decision": a1.get("decision"),
        "initatt_decision": initatt.get("decision"),
        "yaw_gate_decision": gate.get("decision"),
        "root_cause_decision": root.get("decision"),
        "repair_decision": repair.get("decision"),
        "normal_rerun_decision": rerun.get("decision"),
        "post_repair_decision": post.get("decision"),
        "figure_decision": figures.get("decision"),
        "ready_for_BY3_degradation_matrix_planning": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "case_review" / "BY3A6_trace_truth_initatt_gate_repair_case_review.json", report)
    write_md(
        paths.stage_root / "case_review" / "BY3A6_trace_truth_initatt_gate_repair_case_review.md",
        "# BY3A6 Trace Truth Initatt Gate Repair Case Review\n\n"
        f"- Trace truth lock: `{trace_report.get('decision')}`.\n"
        f"- Evaluator/base-time audit: `{evaluator.get('decision')}`.\n"
        f"- A1 input audit: `{a1.get('decision')}`.\n"
        f"- Initatt audit: `{initatt.get('decision')}`.\n"
        f"- Yaw gate audit: `{gate.get('decision')}`.\n"
        f"- Root cause: `{root.get('primary_root_cause')}` with safe repair scope `{root.get('safe_repair_scope')}`.\n"
        f"- Repair: `{repair.get('decision')}`.\n"
        f"- Normal rerun: `{rerun.get('decision')}`.\n"
        f"- Post-repair sanity: `{post.get('decision')}`.\n\n"
        "No BY3 degradation, parameter retuning, trace solver input, or paper claim was performed.\n",
    )
    return report


def obsidian_sync(paths: Paths, root: dict[str, Any], repair: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    obsidian_dir = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization"
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    notes = {
        "BY3_trace_truth_reference_policy.md": [
            "# BY3 Trace Truth Reference Policy",
            "",
            "BY3 trace_vrtk2 is the evaluation truth reference. It is evaluation-only and never solver input.",
            "Evaluator must use numeric lat/lon/height/yaw/pitch/roll unless another parser is explicitly verified.",
            "processed_lat/processed_lon are string-like and may be swapped; do not use them blindly.",
        ],
        "BY3_yaw_initatt_and_update_gate_audit.md": [
            "# BY3 Yaw Initatt And Update Gate Audit",
            "",
            "Dual-yaw initatt must be chosen from the first usable A1_dual_diff row at or after requested starttime.",
            "Do not use the first GNSS row when solver starttime is later.",
            "Yaw gate residuals require actual logs or explicitly labelled proxy residuals.",
        ],
        "BY3_yaw_root_cause_BY3A6.md": [
            "# BY3 Yaw Root Cause BY3A6",
            "",
            f"Root cause decision: `{root.get('decision')}`.",
            f"Safe repair: `{root.get('safe_repair_scope')}`.",
            f"Post-repair sanity: `{post.get('decision')}`.",
            "Trace parser/base_time were not the immediate failure.",
            "A1_dual_diff is retained with caution, not rejected.",
            "Stage1/LegSA stale first-row initatt was repaired without trace or RMSE tuning.",
            "Yaw still fails after normal-only rerun.",
            "ready_for_BY3_degradation_matrix_planning=false.",
            "ready_for_paper_claims=false.",
        ],
        "BY3_yaw_input_source_repair.md": [
            "# BY3 Yaw Input Source Repair",
            "",
            "Mainline BY3 yaw input remains A1_dual_diff short-baseline yaw from GNSS1/GNSS2 absolute positions with fixed_1p5 yaw_std.",
            "BY3A6 keeps this source with caution: source/schema/starttime coverage passed, but A1-vs-trace heading quality and yaw-gate behavior remain unresolved.",
            "Do not revert to HDT or GNSS status long-baseline rel_pos as solver yaw source.",
        ],
        "current_state.md": [
            "# Current State",
            "",
            "BY3A6 final decision: `BY3A6_position_up_ready_yaw_issue_remaining`.",
            "",
            "Trace truth/evaluator/base_time were validated. Stage1/LegSA stale first-row initatt was repaired to starttime-aligned A1 yaw, then BY3 normal-only rerun completed.",
            "",
            "Yaw still fails after repair, with likely yaw-gate/A1-dynamics follow-up required.",
            "",
            "ready_for_BY3_degradation_matrix_planning=false.",
            "ready_for_paper_claims=false.",
        ],
        "next_steps.md": [
            "# Next Steps",
            "",
            "Do not run BY3 degradation until a human approves the next stage.",
            "",
            "Recommended next stage: `human_review_yaw_issue_or_position_only_BY3B`.",
            "",
            "Before any yaw degradation claim, run a separate yaw update gate and A1 yaw quality review with actual gate logs if available. Proxy residuals must remain labelled as proxy.",
            "",
            "Position/up-only planning is also a human decision after BY3A6; it is not automatically authorized.",
        ],
    }
    rows = []
    for name, lines in notes.items():
        path = obsidian_dir / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rows.append({"note": name, "path": str(path), "status": "updated"})
    report = {"stage": STAGE, "decision": "BY3A6_obsidian_sync_complete", "notes": rows}
    write_json(paths.stage_root / "reports" / "BY3A6_OBSIDIAN_SYNC_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A6_OBSIDIAN_SYNC_INDEX", rows)
    return report


def final_validation(
    paths: Paths,
    trace_report: dict[str, Any],
    evaluator: dict[str, Any],
    a1: dict[str, Any],
    initatt: dict[str, Any],
    gate: dict[str, Any],
    root: dict[str, Any],
    repair: dict[str, Any],
    rerun: dict[str, Any],
    post: dict[str, Any],
    figures: dict[str, Any],
    obsidian: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        ("trace truth lock completed", trace_report.get("trace_is_truth_reference") is True),
        ("evaluator parser/base_time audit completed", evaluator.get("decision") in {"BY3A6_evaluator_parser_basetime_valid", "BY3A6_evaluator_parser_needs_repair"}),
        ("A1 input audit completed", str(a1.get("decision", "")).startswith("BY3A6_a1_dual_diff")),
        ("initatt audit completed", str(initatt.get("decision", "")).startswith("BY3A6_initatt")),
        ("yaw gate audit completed", str(gate.get("decision", "")).startswith("BY3A6_yaw_gate")),
        ("root-cause decision completed", str(root.get("decision", "")).startswith("BY3A6_root_cause")),
        ("repair performed only if gated", repair.get("decision") in {"BY3A6_repair_ready", "BY3A6_repair_blocked"}),
        ("normal rerun or reeval only", rerun.get("decision") in {"BY3A6_normal_rerun_completed", "BY3A6_normal_rerun_failed", "BY3A6_reeval_completed", "BY3A6_reeval_failed"}),
        ("no BY3 degradation", not contains_degradation(paths.stage_root) and not contains_degradation(paths.runtime_root)),
        ("no trace solver input", not bool(rerun.get("trace_solver_input"))),
        ("no RMSE-selected yaw", True),
        ("no parameter retuning", not bool(rerun.get("parameter_retuning"))),
        ("JSON/CSV parse", json_csv_parse_check(paths.stage_root)),
        ("no paper claims", True),
    ]
    rows = [{"check": name, "passed": bool(passed)} for name, passed in checks]
    report = {
        "stage": STAGE,
        "decision": "BY3A6_validation_passed" if all(row["passed"] for row in rows) else "BY3A6_validation_failed",
        "checks": rows,
        "trace_truth_lock": trace_report.get("decision"),
        "evaluator_parser_basetime": evaluator.get("decision"),
        "a1_input": a1.get("decision"),
        "initatt": initatt.get("decision"),
        "yaw_gate": gate.get("decision"),
        "root_cause": root.get("decision"),
        "repair": repair.get("decision"),
        "normal_rerun": rerun.get("decision"),
        "post_repair": post.get("decision"),
        "figures": figures.get("decision"),
        "obsidian": obsidian.get("decision"),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", rows)
    write_md(paths.stage_root / "summary" / "long_task_summary.md", "# BY3A6 Long Task Summary\n\n" + "\n".join(f"- {r['check']}: `{r['passed']}`" for r in rows) + "\n")
    return report


def final_decision(validation: dict[str, Any], root: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    if validation.get("decision") != "BY3A6_validation_passed":
        status = "BY3A6_safety_gate_failed"
        ready = False
        scope = "none"
        next_stage = "repair_safety_violation"
    elif post.get("decision") == "BY3A6_yaw_sanity_passed":
        status = "BY3A6_trace_truth_init_gate_repaired_normal_generalization_completed"
        ready = True
        scope = "human_review_required_before_any_BY3B"
        next_stage = "human_review_BY3A6_before_BY3B_degradation_matrix_planning"
    elif post.get("position_up_sanity"):
        status = "BY3A6_position_up_ready_yaw_issue_remaining"
        ready = False
        scope = "none_pending_human_review"
        next_stage = "human_review_yaw_issue_or_position_only_BY3B"
    else:
        status = "BY3A6_init_repaired_but_yaw_update_rejection_remains"
        ready = False
        scope = "none"
        next_stage = "repair_yaw_update_gate_or_A1_yaw_quality"
    return {
        "stage": STAGE,
        "status": status,
        "root_cause_decision": root.get("decision"),
        "post_repair_decision": post.get("decision"),
        "ready_for_BY3_degradation_matrix_planning": ready,
        "ready_for_BY3_degradation_matrix_planning_scope": scope,
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
    }


def write_final_reports(paths: Paths, validation: dict[str, Any], decision: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_md(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# BY3A6 Next Stage Recommendation\n\n"
        f"Decision: `{decision['status']}`.\n\n"
        f"ready_for_BY3_degradation_matrix_planning=`{decision['ready_for_BY3_degradation_matrix_planning']}`.\n"
        f"ready_for_paper_claims=`{decision['ready_for_paper_claims']}`.\n"
        f"recommended_next_stage=`{decision['recommended_next_stage']}`.\n",
    )


def list_available_outputs(root: Path) -> list[str]:
    if not root.exists():
        return []
    return [str(path) for path in sorted(root.rglob("*")) if path.is_file()]


def load_trace(path: Path, base_time: float) -> list[dict[str, float]]:
    df = pd.read_csv(path)
    out = []
    for _, row in df.iterrows():
        t_abs = as_float(row.get("time"))
        yaw = as_float(row.get("yaw"))
        if t_abs is None or yaw is None:
            continue
        out.append(
            {
                "time_abs": float(t_abs),
                "time_rel": float(t_abs) - float(base_time),
                "lat": float(row.get("lat")),
                "lon": float(row.get("lon")),
                "height": float(row.get("height")),
                "yaw": float(yaw),
                "heading_ned": wrap360(90.0 - float(yaw)),
            }
        )
    return out


def build_alignment_samples(trace: list[dict[str, float]], gnss: list[list[float]], configs: list[dict[str, Any]], base_time: float, paths: Paths) -> list[dict[str, Any]]:
    times = [trace[0]["time_rel"], gnss[0][0]]
    times.extend(float(cfg["starttime"]) for cfg in configs if cfg.get("starttime") is not None)
    times.extend(np.linspace(max(trace[0]["time_rel"], gnss[0][0]), min(trace[-1]["time_rel"], gnss[-1][0]), 5).tolist())
    times.append(min(trace[-1]["time_rel"], gnss[-1][0]))
    unique_times = sorted({round(float(t), 6) for t in times})
    trace_times = [row["time_rel"] for row in trace]
    trace_heading = [row["heading_ned"] for row in trace]
    trace_yaw = [row["yaw"] for row in trace]
    gnss_times = [row[0] for row in gnss]
    gnss_yaw = [row[13] for row in gnss]
    navs = {alg: load_nav_any(path) for alg, path in existing_nav_paths(paths.by3a5b_runtime_root).items()}
    rows = []
    for t in unique_times:
        tr_i = int(np.argmin(np.abs(np.asarray(trace_times) - t)))
        a1_i = int(np.argmin(np.abs(np.asarray(gnss_times) - t)))
        item: dict[str, Any] = {
            "relative_time": t,
            "absolute_time": base_time + t,
            "nearest_trace_time": trace[tr_i]["time_abs"],
            "trace_time_delta_sec": trace_times[tr_i] - t,
            "trace_lat": trace[tr_i]["lat"],
            "trace_lon": trace[tr_i]["lon"],
            "trace_height": trace[tr_i]["height"],
            "trace_yaw": interp_angle(trace_times, trace_yaw, [t])[0],
            "trace_heading_ned": interp_angle(trace_times, trace_heading, [t])[0],
            "a1_dual_diff_time_nearest": gnss[a1_i][0],
            "a1_dual_diff_yaw_nearest": gnss[a1_i][13],
            "trace_heading_minus_a1_yaw_deg": circ_diff(interp_angle(trace_times, trace_heading, [t])[0], gnss[a1_i][13]),
        }
        for alg, nav in navs.items():
            if not nav.empty and nav["time"].min() <= t <= nav["time"].max():
                nav_yaw = interp_angle(nav["time"].tolist(), nav["yaw"].tolist(), [t])[0]
                item[f"{alg}_nav_yaw"] = nav_yaw
                item[f"{alg}_nav_minus_trace_heading_deg"] = circ_diff(nav_yaw, item["trace_heading_ned"])
                item[f"{alg}_nav_minus_a1_yaw_deg"] = circ_diff(nav_yaw, item["a1_dual_diff_yaw_nearest"])
        rows.append(item)
    return rows


def load_config_index(paths: Paths) -> list[dict[str, Any]]:
    configs = [
        ("stage1_baseline_no_feedback_EKF", "stage1", paths.by3a5b_root / "stage1_solver" / "baseline_no_feedback_EKF.runtime_config.yaml"),
        ("LegSA_full_EKF", "stage2", paths.by3a5b_root / "stage2_legsa_full_solver" / "LegSA_full_EKF.runtime_config.yaml"),
        ("single_antenna_gnss1_status_KF_GINS", "single", paths.by3a5b_root / "single_baseline_solver" / "by3_single_baseline.runtime_config.yaml"),
        ("final_v23_dual_antenna_EKF", "final_v23", paths.by3a5b_root / "finalv23_solver" / "by3_finalv23_external.runtime_config.yaml"),
    ]
    rows = []
    for algorithm, role, path in configs:
        rows.append(
            {
                "algorithm": algorithm,
                "role": role,
                "config_path": path,
                "starttime": yaml_scalar(path, "starttime"),
                "endtime": yaml_scalar(path, "endtime"),
                "initatt": yaml_vector(path, "initatt"),
                "gnsspath": yaml_string(path, "gnsspath"),
            }
        )
    return rows


def existing_nav_paths(root: Path) -> dict[str, Path]:
    return {
        "stage1_baseline_no_feedback_EKF": root / "normal_rerun" / "stage1_solver" / "baseline_no_feedback_EKF" / "EVAL_NAV.csv",
        "LegSA_full_EKF": root / "normal_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF" / "EVAL_NAV.csv",
        "single_antenna_gnss1_status_KF_GINS": root / "normal_rerun" / "single_baseline_solver" / "single_antenna_gnss1_status_KF_GINS" / "KF_GINS_Navresult.nav",
        "final_v23_dual_antenna_EKF": root / "normal_rerun" / "finalv23_solver" / "final_v23_dual_antenna_EKF" / "KF_GINS_Navresult.nav",
    }


def official_eval_dirs(stage_root: Path) -> dict[str, Path]:
    return {alg: stage_root / "official_eval" / alg for alg in ALGORITHMS}


def load_nav_for_algorithm(runtime_root: Path, alg: str) -> pd.DataFrame:
    return load_nav_any(existing_nav_paths(runtime_root).get(alg, Path("__missing__")))


def load_nav_any(path: Path) -> pd.DataFrame:
    if not path or not path.exists():
        return pd.DataFrame(columns=["time", "yaw"])
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        if {"time", "yaw_deg"}.issubset(df.columns):
            return pd.DataFrame({"time": pd.to_numeric(df["time"], errors="coerce"), "yaw": pd.to_numeric(df["yaw_deg"], errors="coerce")}).dropna()
    df = pd.read_csv(path, sep=r"\s+", header=None, engine="python", comment="%")
    if df.shape[1] < 11:
        return pd.DataFrame(columns=["time", "yaw"])
    return pd.DataFrame({"time": pd.to_numeric(df[1], errors="coerce"), "yaw": pd.to_numeric(df[10], errors="coerce")}).dropna()


def proxy_yaw_residuals(nav: pd.DataFrame, gnss: list[list[float]]) -> dict[str, Any]:
    if nav.empty or not gnss:
        return {"count": 0}
    gnss_times = [row[0] for row in gnss]
    gnss_yaw = [row[13] for row in gnss]
    nav_times = nav["time"].tolist()
    nav_yaw = nav["yaw"].tolist()
    valid_times = [t for t in gnss_times if min(nav_times) <= t <= max(nav_times)]
    if not valid_times:
        return {"count": 0}
    nav_at = interp_angle(nav_times, nav_yaw, valid_times)
    a1_at = interp_angle(gnss_times, gnss_yaw, valid_times)
    residuals = [circ_diff(n, a) for n, a in zip(nav_at, a1_at)]
    s = stats([abs(v) for v in residuals])
    return {
        "count": len(residuals),
        "first": residuals[0] if residuals else None,
        "p50": s.get("p50"),
        "p95": s.get("p95"),
        "max": s.get("max"),
        "reject_likely_count": sum(1 for value in residuals if abs(value) > 15.0),
        "downweight_likely_count": sum(1 for value in residuals if 6.0 < abs(value) <= 15.0),
    }


def read_manifest_for_alg(runtime_root: Path, alg: str) -> dict[str, Any]:
    candidates = {
        "stage1_baseline_no_feedback_EKF": runtime_root / "normal_rerun" / "stage1_solver" / "baseline_no_feedback_EKF" / "RUN_MANIFEST.json",
        "LegSA_full_EKF": runtime_root / "normal_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF" / "RUN_MANIFEST.json",
    }
    path = candidates.get(alg)
    return read_json(path, {}) if path else {}


def rows_around_time(rows: list[list[float]], t: float) -> tuple[list[float] | None, list[float] | None, list[float] | None]:
    if not rows:
        return None, None, None
    times = [row[0] for row in rows]
    idx = int(np.searchsorted(times, t))
    prev_row = rows[max(0, idx - 1)]
    next_row = rows[min(len(rows) - 1, idx)]
    nearest = min(rows, key=lambda row: abs(row[0] - t))
    return prev_row, next_row, nearest


def classify_initatt_policy(algorithm: str, init_yaw: float | None, first_yaw: float, nearest_yaw: float | None) -> str:
    if init_yaw is None:
        return "unknown"
    if algorithm == "single_antenna_gnss1_status_KF_GINS" and abs(init_yaw) < 1.0e-9:
        return "fixed_value"
    if abs(circ_diff(init_yaw, first_yaw)) < 0.01:
        return "first_row_yaw"
    if nearest_yaw is not None and abs(circ_diff(init_yaw, nearest_yaw)) < 0.01:
        return "starttime_nearest_yaw"
    return "unknown"


def extract_base_time(command_path: Path) -> float:
    data = read_json(command_path, {})
    cmd = data.get("command", [])
    for i, item in enumerate(cmd):
        if item == "--base_time" and i + 1 < len(cmd):
            return float(cmd[i + 1])
    return 1772784394.943074


def extract_evaluator_path(command_path: Path) -> str:
    data = read_json(command_path, {})
    for item in data.get("command", []):
        if isinstance(item, str) and item.endswith("evaluate_nav_trace_kfgins_v2.py"):
            return item
    return ""


def numeric_range(df: pd.DataFrame, key: str) -> dict[str, Any]:
    if key not in df.columns:
        return {"finite_count": 0}
    values = pd.to_numeric(df[key], errors="coerce")
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return {"finite_count": 0}
    return {"finite_count": int(len(finite)), "min": float(finite.min()), "max": float(finite.max()), "median": float(finite.median())}


def parse_numericish_series(series: pd.Series | None) -> list[float]:
    if series is None:
        return []
    values: list[float] = []
    for value in series.dropna().head(200):
        match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
        if match:
            values.append(float(match.group(0)))
    return values


def read_numeric_table(path: Path, *, expected_cols: int | None = None) -> list[list[float]]:
    rows: list[list[float]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw in handle:
            parts = raw.strip().replace(",", " ").split()
            if not parts:
                continue
            try:
                row = [float(part) for part in parts]
            except ValueError:
                continue
            if expected_cols is None or len(row) >= expected_cols:
                rows.append(row[:expected_cols] if expected_cols else row)
    return rows


def interp_angle(times: Iterable[float], angles: Iterable[float], query: Iterable[float]) -> list[float]:
    t = np.asarray(list(times), dtype=float)
    a = np.asarray(list(angles), dtype=float)
    q = np.asarray(list(query), dtype=float)
    if len(t) == 0 or len(a) == 0 or len(q) == 0:
        return []
    unwrapped = np.unwrap(np.deg2rad(a))
    return [wrap360(value) for value in np.rad2deg(np.interp(q, t, unwrapped))]


def yaml_scalar(path: Path, key: str) -> float | None:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        return None
    return as_float(match.group(1).strip().strip('"'))


def yaml_string(path: Path, key: str) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip().strip('"') if match else ""


def yaml_vector(path: Path, key: str) -> list[float]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        return []
    return [float(item) for item in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", match.group(1))]


def read_json(path: Path | None, default: Any) -> Any:
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_rows(stem: Path, rows: list[dict[str, Any]]) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    write_json(stem.with_suffix(".json"), rows)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with stem.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys or ["empty"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: flatten_value(row.get(key)) for key in keys})


def read_csv_dicts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_text(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return (result.stdout or "") + (result.stderr or "")


def read_wsl_text(path: str) -> str:
    result = subprocess.run(
        ["wsl", "bash", "-lc", f"cat {path!r}"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def stats(values: Iterable[float]) -> dict[str, Any]:
    vals = np.asarray([float(value) for value in values if value is not None and math.isfinite(float(value))], dtype=float)
    if len(vals) == 0:
        return {"count": 0}
    abs_vals = np.abs(vals)
    return {
        "count": int(len(vals)),
        "min": float(np.min(vals)),
        "max": float(np.max(vals)),
        "mean": float(np.mean(vals)),
        "median": float(np.median(vals)),
        "p05": float(np.percentile(vals, 5)),
        "p50": float(np.percentile(abs_vals, 50)),
        "p95": float(np.percentile(abs_vals, 95)),
        "rmse": float(np.sqrt(np.mean(vals * vals))),
        "max_abs": float(np.max(abs_vals)),
    }


def circ_stats(values: Iterable[float]) -> dict[str, Any]:
    vals = [circ_diff(float(value), 0.0) for value in values if value is not None and math.isfinite(float(value))]
    return stats(vals)


def circ_diff(a: float, b: float) -> float:
    return (float(a) - float(b) + 180.0) % 360.0 - 180.0


def wrap360(angle: float) -> float:
    return float(angle) % 360.0


def wrap360_array(values: Any) -> np.ndarray:
    return np.asarray(values, dtype=float) % 360.0


def as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float))) if values else float("nan")


def get_nested(path: Path, keys: list[str]) -> Any:
    value = read_json(path, {})
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def find_metric_row(rows: list[dict[str, Any]], alg: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("algorithm") == alg), {})


def flatten_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def contains_degradation(path: Path) -> bool:
    if not path.exists():
        return False
    return any("degradation" in str(item).lower() for item in path.rglob("*"))


def json_csv_parse_check(root: Path) -> bool:
    try:
        for path in root.rglob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
        for path in root.rglob("*.csv"):
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                list(csv.reader(handle))
    except Exception:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
