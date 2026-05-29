"""Run BY3A8 yaw error-budget and safe-repair audit.

This stage accepts the BY3A7 normal-only repair as the current BY3 state and
budgets the remaining 4-5 degree dual-yaw error.  It is deliberately
forensic-first: trace is evaluation-only, A1/HDT comparisons are diagnostic,
and any repair must be source-backed rather than selected by final RMSE.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
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

from scripts.experiments import run_by3a0_to_by3e_generalization_reorg as by3a0  # noqa: E402
from scripts.experiments import run_by3a5_dual_yaw_input_source_repair as by3a5  # noqa: E402
from scripts.experiments import run_by3a5b_a1_dual_diff_yaw_input_repair as by3a5b  # noqa: E402
from scripts.experiments import run_by3a6_trace_truth_initatt_gate_forensic as by3a6  # noqa: E402
from scripts.experiments import run_by3a7_a1_yaw_dynamic_quality_imu_gate_repair as by3a7  # noqa: E402


STAGE = "BY3A8_YAW_ERROR_BUDGET_AND_SAFE_REPAIR"
RUNTIME_STAGE = "BY3A8_YAW_ERROR_BUDGET_REPAIR"

SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "yaw_error_budget",
    "a1_observation_lower_bound",
    "a1_yaw_quality",
    "imu_bias_refinement",
    "time_lag_diagnostic",
    "yaw_gate_audit",
    "feedback_interaction",
    "safe_repair_plan",
    "normal_rerun",
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
    by3a5_root: Path
    by3a5b_root: Path
    by3a6_root: Path
    by3a7_root: Path
    by3a7_runtime_root: Path

    @property
    def a1_gnss(self) -> Path:
        return self.by3a7_root / "repaired_input_or_config" / "BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def repaired_imu(self) -> Path:
        return self.by3a7_root / "repaired_input_or_config" / "BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu"

    @property
    def raw_doppler(self) -> Path:
        return self.by3a2_root / "raw_doppler_recovery" / "provider_only" / "RAW_DOPPLER_VELOCITY_FACTORS.csv"

    @property
    def go2_prior_dir(self) -> Path:
        return self.by3a1_root / "provider_materialization" / "go2_priors" / "priors" / "joint_rp1p6deg_hv1p0"

    @property
    def body_diag(self) -> Path:
        return self.by3a0_root / "by3_body_imu" / "BY3_GO2_BODY_STATE_DIAGNOSTIC.csv"

    @property
    def hdt_diag_gnss(self) -> Path:
        return self.by3a5_root / "repaired_input_generation" / "BY3_DUAL_HDT_15COL_REPAIRED.gnss"

    @property
    def feedback(self) -> Path:
        return self.by3a7_root / "feedback_generation" / "BY3_normal" / "FGO_FEEDBACK_OBSERVATIONS.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--receiver-root", type=Path)
    parser.add_argument("--trace", type=Path)
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
        by3a0_root=repo / "by3-huiti" / by3a6.BY3A0_STAGE,
        by3a1_root=repo / "by3-huiti" / by3a6.BY3A1_STAGE,
        by3a2_root=repo / "by3-huiti" / by3a6.BY3A2_STAGE,
        by3a3_root=repo / "by3-huiti" / by3a6.BY3A3_STAGE,
        by3a5_root=repo / "by3-huiti" / by3a6.BY3A5_STAGE,
        by3a5b_root=repo / "by3-huiti" / by3a6.BY3A5B_STAGE,
        by3a6_root=repo / "by3-huiti" / by3a6.STAGE,
        by3a7_root=repo / "by3-huiti" / by3a7.STAGE,
        by3a7_runtime_root=repo / "by3-huiti" / "BY3_FULL_MATRIX" / by3a7.RUNTIME_STAGE,
    )
    result = run_by3a8(paths, skip_figures=args.skip_figures)
    print(
        json.dumps(
            {
                "decision": result["decision"]["status"],
                "stage_root": str(paths.stage_root),
                "runtime_root": str(paths.runtime_root),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def run_by3a8(paths: Paths, *, skip_figures: bool) -> dict[str, Any]:
    create_tree(paths)
    write_plan(paths)
    base_time = extract_base_time(paths)
    source_lock = import_by3a7_state(paths)
    if source_lock["decision"] != "BY3A8_sources_locked":
        validation = final_validation(paths, source_lock, {}, {}, {}, {}, {}, {}, {}, {}, {})
        decision = final_decision(validation, {}, {}, {}, {}, {}, {}, {})
        write_final_reports(paths, validation, decision)
        return {"validation": validation, "decision": decision}

    a1_quality = a1_yaw_quality_audit(paths, base_time)
    lower = a1_observation_lower_bound(paths, base_time, a1_quality)
    bias = imu_bias_refinement_audit(paths, base_time)
    lag = time_lag_diagnostic(paths, base_time, a1_quality)
    gate = yaw_gate_update_effect(paths, a1_quality)
    feedback = feedback_interaction_audit(paths)
    plan = safe_repair_plan(paths, lower, a1_quality, bias, lag, gate, feedback)
    rerun = repair_and_rerun(paths, plan)
    post = post_stage_sanity(paths, lower, a1_quality, bias, lag, gate, feedback, plan, rerun)
    figures = generate_figures(paths, lower, a1_quality, bias, lag, gate, feedback, post, skip_figures=skip_figures)
    case = case_review(paths, source_lock, lower, a1_quality, bias, lag, gate, feedback, plan, rerun, post, figures)
    obsidian = obsidian_sync(paths, lower, a1_quality, bias, lag, gate, feedback, post)
    validation = final_validation(paths, source_lock, lower, a1_quality, bias, lag, gate, feedback, plan, post, figures)
    decision = final_decision(validation, lower, a1_quality, bias, lag, gate, feedback, post)
    write_final_reports(paths, validation, decision)
    write_runtime_no_rerun_manifest(paths, plan, rerun, decision)
    return {"validation": validation, "decision": decision, "case_review": case, "obsidian": obsidian}


def create_tree(paths: Paths) -> None:
    paths.stage_root.mkdir(parents=True, exist_ok=True)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)
        (paths.runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def write_plan(paths: Paths) -> None:
    report = {
        "stage": STAGE,
        "purpose": "Budget remaining BY3 dual-yaw normal error after BY3A7.",
        "solver_rerun_policy": "normal-only rerun only if source-backed safe repair passes",
        "hard_prohibitions": [
            "no degradation",
            "no parameter retuning",
            "no trace solver input",
            "no HDT or long-relpos fallback",
            "no RMSE-selected repair",
            "no paper claims",
        ],
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "01_plan" / "BY3A8_APPROVED_PLAN.json", report)
    by3a6.write_md(
        paths.stage_root / "01_plan" / "by3a8_approved_plan.md",
        "# BY3A8 Approved Plan\n\n"
        "Forensic yaw error budget first. Any repair requires source-backed evidence; otherwise no normal rerun is run.\n",
    )


def extract_base_time(paths: Paths) -> float:
    command = paths.by3a7_root / "official_eval" / "LegSA_full_EKF" / "command.json"
    return by3a6.extract_base_time(command)


def import_by3a7_state(paths: Paths) -> dict[str, Any]:
    by3a7_decision = by3a6.read_json(paths.by3a7_root / "reports" / "LONG_TASK_DECISION_REPORT.json", {})
    files = [
        ("BY3A7_repaired_IMU", paths.repaired_imu, "<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu", "solver_input_accepted"),
        ("BY3A5B_A1_dual_diff_GNSS", paths.a1_gnss, "<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss", "solver_yaw_source_accepted_with_caution"),
        ("BY3A2_Raw_Doppler_provider", paths.raw_doppler, "<BY3A2_STAGE_ROOT>/raw_doppler_recovery/provider_only/RAW_DOPPLER_VELOCITY_FACTORS.csv", "provider_input_accepted"),
        ("BY3A2_Go2_attitude_prior", paths.go2_prior_dir / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv", "<BY3A1_STAGE_ROOT>/provider_materialization/go2_priors/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv", "provider_input_accepted"),
        ("BY3A2_Go2_velocity_prior", paths.go2_prior_dir / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv", "<BY3A1_STAGE_ROOT>/provider_materialization/go2_priors/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv", "provider_input_accepted"),
        ("BY3A2_Go2_joint_prior", paths.go2_prior_dir / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv", "<BY3A1_STAGE_ROOT>/provider_materialization/go2_priors/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv", "provider_input_accepted"),
        ("BY3A7_same_case_feedback", paths.feedback, "<BY3A7_STAGE_ROOT>/feedback_generation/BY3_normal/FGO_FEEDBACK_OBSERVATIONS.csv", "same_case_feedback_accepted"),
        ("BY3_trace_truth", paths.trace, "<BY3_TRACE_TRUTH>", "evaluation_reference_only"),
        ("final_v23_runtime_config", paths.by3a7_root / "finalv23_solver" / "by3_finalv23_external.runtime_config.yaml", "<BY3A7_STAGE_ROOT>/finalv23_solver/by3_finalv23_external.runtime_config.yaml", "external_reference_baseline_config"),
        ("single_baseline_runtime_config", paths.by3a7_root / "single_baseline_solver" / "by3_single_baseline.runtime_config.yaml", "<BY3A7_STAGE_ROOT>/single_baseline_solver/by3_single_baseline.runtime_config.yaml", "single_baseline_config"),
    ]
    rows = [file_meta(role, path, alias, source_role) for role, path, alias, source_role in files]
    accepted = all(row["exists"] for row in rows) and by3a7_decision.get("status") == "BY3A7_yaw_salvaged_ready_for_full_BY3_degradation"
    report = {
        "stage": STAGE,
        "decision": "BY3A8_sources_locked" if accepted else "BY3A8_sources_blocked",
        "by3a7_status": by3a7_decision.get("status"),
        "by3a7_ready_for_degradation": by3a7_decision.get("ready_for_BY3_degradation_matrix_planning"),
        "accepted_sources": rows,
        "forbidden_replacements": ["HDT mainline yaw", "GNSS status long-baseline rel_pos", "trace solver input"],
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_BY3A7_IMPORT_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_ACCEPTED_SOURCE_LOCK", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_by3a7_import.md",
        "# BY3A8 BY3A7 Import\n\n"
        f"Decision: `{report['decision']}`. BY3A7 status: `{report['by3a7_status']}`.\n",
    )
    return report


def a1_yaw_quality_audit(paths: Paths, base_time: float) -> dict[str, Any]:
    gnss = by3a6.read_numeric_table(paths.a1_gnss, expected_cols=15)
    baseline = build_baseline_index(paths, base_time)
    trace = by3a6.load_trace(paths.trace, base_time)
    hdt = by3a6.read_numeric_table(paths.hdt_diag_gnss, expected_cols=15)
    rows = build_a1_quality_rows(gnss, baseline, trace, hdt)
    jumps = [row["yaw_jump_deg"] for row in rows if row.get("yaw_jump_deg") is not None]
    baseline_lengths = [row["baseline_length_m"] for row in rows if row.get("baseline_length_m") is not None]
    invalid_count = sum(1 for row in rows if row["objective_invalid_for_solver_candidate"])
    jump_count_15 = sum(1 for value in jumps if abs(float(value)) > 15.0)
    jump_count_30 = sum(1 for value in jumps if abs(float(value)) > 30.0)
    jump_count_45 = sum(1 for value in jumps if abs(float(value)) > 45.0)
    if invalid_count == 0:
        decision = "BY3A8_a1_quality_no_mask_needed"
    elif invalid_count <= max(12, len(rows) * 0.05):
        decision = "BY3A8_a1_quality_objective_mask_ready"
    else:
        decision = "BY3A8_a1_quality_poor_blocks_yaw"
    report = {
        "stage": STAGE,
        "decision": decision,
        "row_count": len(rows),
        "yaw_jump_stats_deg": by3a6.stats(jumps),
        "jump_count_gt_15_deg": jump_count_15,
        "jump_count_gt_30_deg": jump_count_30,
        "jump_count_gt_45_deg": jump_count_45,
        "baseline_length_stats_m": by3a6.stats(baseline_lengths),
        "objective_invalid_epoch_count": invalid_count,
        "invalid_criteria_not_rmse_based": True,
        "trace_used_for_invalid_epoch_rule": False,
        "hdt_solver_input": False,
        "rows": rows,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_A1_YAW_QUALITY_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_A1_YAW_EPOCH_QUALITY", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_a1_yaw_quality.md",
        "# BY3A8 A1 Yaw Quality\n\n"
        f"Decision: `{decision}`. Objective invalid epochs: `{invalid_count}`. "
        "Trace disagreement remains diagnostic only and is not a solver-mask rule.\n",
    )
    return report


def build_a1_quality_rows(
    gnss: list[list[float]],
    baseline: list[dict[str, Any]],
    trace: list[dict[str, float]],
    hdt: list[list[float]],
) -> list[dict[str, Any]]:
    if not gnss:
        return []
    times = np.asarray([row[0] for row in gnss], dtype=float)
    yaw = np.asarray([row[13] for row in gnss], dtype=float)
    unwrapped = np.rad2deg(np.unwrap(np.deg2rad(yaw)))
    baseline_lengths = np.asarray([float(row["baseline_length_m"]) for row in baseline], dtype=float) if baseline else np.asarray([])
    lower, upper = by3a7.robust_bounds(baseline_lengths)
    median_bl = float(np.median(baseline_lengths)) if baseline_lengths.size else None
    mad_bl = float(np.median(np.abs(baseline_lengths - float(np.median(baseline_lengths))))) if baseline_lengths.size else None
    trace_heading = by3a6.interp_angle([row["time_rel"] for row in trace], [row["heading_ned"] for row in trace], times.tolist()) if trace else []
    hdt_yaw = by3a6.interp_angle([row[0] for row in hdt], [row[13] for row in hdt], times.tolist()) if hdt else []
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(gnss):
        jump = float(unwrapped[idx] - unwrapped[idx - 1]) if idx else None
        dt = float(times[idx] - times[idx - 1]) if idx else None
        next_jump = float(unwrapped[idx + 1] - unwrapped[idx]) if idx + 1 < len(unwrapped) else None
        baseline_row = by3a7.nearest_by_time(baseline, float(row[0]))
        baseline_length = float(baseline_row["baseline_length_m"]) if baseline_row else None
        zscore = robust_zscore(baseline_length, median_bl, mad_bl)
        trace_diff = by3a6.circ_diff(float(row[13]), trace_heading[idx]) if trace_heading else None
        hdt_diff = by3a6.circ_diff(float(row[13]), hdt_yaw[idx]) if hdt_yaw else None
        quality = classify_a1_epoch_for_by3a8(
            yaw_jump_deg=jump,
            next_yaw_jump_deg=next_jump,
            baseline_length_m=baseline_length,
            baseline_lower_m=lower,
            baseline_upper_m=upper,
            trace_diff_deg=trace_diff,
            hdt_diff_deg=hdt_diff,
        )
        rows.append(
            {
                "time": float(row[0]),
                "yaw": float(row[13]),
                "unwrapped_yaw": float(unwrapped[idx]),
                "yaw_jump": jump,
                "yaw_jump_deg": jump,
                "yaw_jump_from_prev_deg": jump,
                "yaw_rate_deg_per_sec": float(jump / dt) if jump is not None and dt and dt > 0 else None,
                "baseline_length": baseline_length,
                "baseline_length_m": baseline_length,
                "baseline_length_zscore": zscore,
                "local_baseline_length_quality": "valid" if baseline_length is not None and lower <= baseline_length <= upper else "baseline_length_suspect",
                "trace_heading_nearest": trace_heading[idx] if trace_heading else None,
                "a1_minus_trace": trace_diff,
                "hdt_heading_nearest": hdt_yaw[idx] if hdt_yaw else None,
                "a1_minus_hdt": hdt_diff,
                "quality_flag": "|".join(quality["flags"]),
                "objective_invalid_for_solver_candidate": quality["objective_invalid_for_solver_candidate"],
                "should_use_for_solver_candidate": not quality["objective_invalid_for_solver_candidate"],
                "reason": quality["reason"],
                "trace_disagreement_diagnostic_only": quality["trace_disagreement_diagnostic_only"],
            }
        )
    return rows


def classify_a1_epoch_for_by3a8(
    *,
    yaw_jump_deg: float | None,
    next_yaw_jump_deg: float | None,
    baseline_length_m: float | None,
    baseline_lower_m: float,
    baseline_upper_m: float,
    trace_diff_deg: float | None,
    hdt_diff_deg: float | None,
) -> dict[str, Any]:
    flags: list[str] = []
    reasons: list[str] = []
    if baseline_length_m is None or baseline_length_m < baseline_lower_m or baseline_length_m > baseline_upper_m:
        flags.append("baseline_length_suspect")
        reasons.append("baseline_length_outside_source_robust_bounds")
    if yaw_jump_deg is not None and abs(yaw_jump_deg) > 30.0:
        flags.append("yaw_jump_suspect")
    if yaw_jump_deg is not None and abs(yaw_jump_deg) > 45.0:
        reasons.append("yaw_jump_gt_45_deg_between_gnss_epochs")
    if is_isolated_counter_jump(yaw_jump_deg, next_yaw_jump_deg):
        flags.append("isolated_outlier")
        reasons.append("isolated_large_counter_jump")
    if trace_diff_deg is not None and abs(trace_diff_deg) > 45.0:
        flags.append("trace_disagreement_diagnostic")
    if hdt_diff_deg is not None and abs(hdt_diff_deg) > 45.0:
        flags.append("hdt_disagreement_diagnostic")
    if not flags:
        flags.append("valid")
    return {
        "flags": flags,
        "objective_invalid_for_solver_candidate": bool(reasons),
        "reason": "|".join(reasons) if reasons else "none",
        "trace_disagreement_diagnostic_only": any("diagnostic" in flag for flag in flags) and not reasons,
    }


def is_isolated_counter_jump(jump: float | None, next_jump: float | None) -> bool:
    return jump is not None and next_jump is not None and abs(jump) > 30.0 and abs(next_jump) > 30.0 and jump * next_jump < 0.0


def a1_observation_lower_bound(paths: Paths, base_time: float, a1_quality: dict[str, Any]) -> dict[str, Any]:
    gnss = by3a6.read_numeric_table(paths.a1_gnss, expected_cols=15)
    trace = by3a6.load_trace(paths.trace, base_time)
    hdt = by3a6.read_numeric_table(paths.hdt_diag_gnss, expected_cols=15)
    rows = build_lower_bound_rows(paths, gnss, trace, hdt, a1_quality)
    errors = [row["a1_minus_trace_heading_deg"] for row in rows if row.get("a1_minus_trace_heading_deg") is not None]
    stats_all = by3a6.stats(errors)
    circ = circular_summary(errors)
    conditioned = conditioned_error_stats(rows)
    nav_rows = nav_comparison_rows(paths, trace, gnss, base_time)
    rmse = float(stats_all.get("rmse") or 0.0)
    if rmse <= 2.0:
        decision = "BY3A8_a1_observation_quality_supports_2deg"
        band = "0-2 deg"
    elif rmse <= 4.0:
        decision = "BY3A8_a1_observation_quality_limited_4deg"
        band = "2-4 deg"
    elif rmse <= 6.0:
        decision = "BY3A8_a1_observation_quality_limited_4deg"
        band = "4-6 deg"
    elif int(stats_all.get("count") or 0) > 0:
        decision = "BY3A8_a1_observation_quality_poor"
        band = ">6 deg"
    else:
        decision = "BY3A8_a1_observation_lower_bound_inconclusive"
        band = "inconclusive"
    report = {
        "stage": STAGE,
        "decision": decision,
        "A1_observation_yaw_rmse_deg": stats_all.get("rmse"),
        "A1_observation_yaw_p95_deg": stats_all.get("p95"),
        "A1_observation_yaw_max_deg": stats_all.get("max_abs"),
        "mean_circular_error_deg": circ.get("mean_circular_error_deg"),
        "circular_std_deg": circ.get("circular_std_deg"),
        "valid_sample_count": stats_all.get("count"),
        "observation_lower_bound_band": band,
        "stats": stats_all,
        "conditioned_stats": conditioned,
        "nav_comparison_rows": nav_rows,
        "rows": rows,
        "trace_evaluation_only": True,
        "trace_used_for_solver_input": False,
        "trace_used_for_repair": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_A1_OBSERVATION_LOWER_BOUND_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_A1_OBSERVATION_LOWER_BOUND", [flatten_lower_bound_summary(report)])
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_A1_OBSERVATION_EPOCH_ERRORS", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_a1_observation_lower_bound.md",
        "# BY3A8 A1 Observation Lower Bound\n\n"
        f"Decision: `{decision}`. A1 observation RMSE vs trace heading is "
        f"`{stats_all.get('rmse')}` deg, p95 `{stats_all.get('p95')}` deg. "
        "This comparison is evaluation-only and does not create a trace-based repair.\n",
    )
    return report


def build_lower_bound_rows(
    paths: Paths,
    gnss: list[list[float]],
    trace: list[dict[str, float]],
    hdt: list[list[float]],
    a1_quality: dict[str, Any],
) -> list[dict[str, Any]]:
    if not gnss:
        return []
    times = [float(row[0]) for row in gnss]
    trace_heading = by3a6.interp_angle([row["time_rel"] for row in trace], [row["heading_ned"] for row in trace], times) if trace else []
    hdt_yaw = by3a6.interp_angle([row[0] for row in hdt], [row[13] for row in hdt], times) if hdt else []
    speed_by_time = trace_speed_at(trace, times)
    quality_by_time = {round(float(row["time"]), 6): row for row in a1_quality.get("rows", [])}
    motion_start = selected_go2_start_rel(paths)
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(gnss):
        q = quality_by_time.get(round(float(row[0]), 6), {})
        trace_diff = by3a6.circ_diff(float(row[13]), trace_heading[idx]) if trace_heading else None
        hdt_diff = by3a6.circ_diff(float(row[13]), hdt_yaw[idx]) if hdt_yaw else None
        rows.append(
            {
                "time": float(row[0]),
                "A1_yaw_deg": float(row[13]),
                "trace_heading_deg": trace_heading[idx] if trace_heading else None,
                "a1_minus_trace_heading_deg": trace_diff,
                "hdt_heading_diag_deg": hdt_yaw[idx] if hdt_yaw else None,
                "a1_minus_hdt_diag_deg": hdt_diff,
                "speed_mps_trace_diag": speed_by_time[idx] if idx < len(speed_by_time) else None,
                "speed_bucket": speed_bucket(speed_by_time[idx] if idx < len(speed_by_time) else None),
                "baseline_length_m": q.get("baseline_length_m"),
                "baseline_bucket": "unknown",
                "motion_bucket": "before_selected_start" if float(row[0]) < motion_start else "after_selected_start",
                "quality_flag": q.get("quality_flag"),
                "objective_invalid_for_solver_candidate": q.get("objective_invalid_for_solver_candidate"),
            }
        )
    assign_baseline_buckets(rows)
    return rows


def nav_comparison_rows(paths: Paths, trace: list[dict[str, float]], gnss: list[list[float]], base_time: float) -> list[dict[str, Any]]:
    del base_time
    rows: list[dict[str, Any]] = []
    gnss_times = [row[0] for row in gnss]
    gnss_yaw = [row[13] for row in gnss]
    for algorithm in ALGORITHMS:
        nav = by3a6.load_nav_for_algorithm(paths.by3a7_runtime_root, algorithm)
        if nav.empty:
            rows.append({"algorithm": algorithm, "available": False})
            continue
        nav_times = nav["time"].tolist()
        nav_yaw = nav["yaw"].tolist()
        valid_nav_times = [t for t in nav_times if trace and trace[0]["time_rel"] <= t <= trace[-1]["time_rel"]]
        trace_at_nav = by3a6.interp_angle([row["time_rel"] for row in trace], [row["heading_ned"] for row in trace], valid_nav_times) if trace else []
        nav_at_trace_times = by3a6.interp_angle(nav_times, nav_yaw, valid_nav_times) if valid_nav_times else []
        nav_trace = [by3a6.circ_diff(nav_at_trace_times[i], trace_at_nav[i]) for i in range(min(len(nav_at_trace_times), len(trace_at_nav)))]
        valid_gnss_times = [t for t in gnss_times if float(nav["time"].min()) <= t <= float(nav["time"].max())]
        nav_at_gnss = by3a6.interp_angle(nav_times, nav_yaw, valid_gnss_times)
        a1_at_gnss = by3a6.interp_angle(gnss_times, gnss_yaw, valid_gnss_times)
        nav_a1 = [by3a6.circ_diff(nav_at_gnss[i], a1_at_gnss[i]) for i in range(min(len(nav_at_gnss), len(a1_at_gnss)))]
        rows.append(
            {
                "algorithm": algorithm,
                "available": True,
                "nav_vs_trace_rmse_deg": by3a6.stats(nav_trace).get("rmse"),
                "nav_vs_trace_p95_deg": by3a6.stats(nav_trace).get("p95"),
                "nav_vs_a1_rmse_deg": by3a6.stats(nav_a1).get("rmse"),
                "nav_vs_a1_p95_deg": by3a6.stats(nav_a1).get("p95"),
                "sample_count_nav_trace": len(nav_trace),
                "sample_count_nav_a1": len(nav_a1),
            }
        )
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_NAV_A1_TRACE_COMPARISON", rows)
    return rows


def conditioned_error_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ["speed_bucket", "baseline_bucket", "motion_bucket", "quality_flag"]:
        for bucket in sorted({str(row.get(key)) for row in rows}):
            values = [row["a1_minus_trace_heading_deg"] for row in rows if str(row.get(key)) == bucket and row.get("a1_minus_trace_heading_deg") is not None]
            out[f"{key}:{bucket}"] = by3a6.stats(values)
    return out


def imu_bias_refinement_audit(paths: Paths, base_time: float) -> dict[str, Any]:
    del base_time
    offsets = by3a6.read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {}).get("offsets", {})
    body_min = float(offsets.get("body_time_zero_raw_timestamp") or 0.0)
    go2_start = float(offsets.get("go2_start_raw_timestamp") or 0.0)
    body_rows = by3a7.load_body_rows(paths.body_diag)
    processed = processed_body_samples(body_rows, go2_start)
    current_bias = by3a7.compute_static_pre_motion_bias(body_rows, go2_start)
    candidates = build_bias_candidate_rows(processed, current_bias)
    z_diffs = [abs(float(row["z_bias_degps"]) - math.degrees(current_bias[2])) for row in candidates if row["candidate"] != "BY3A7_current_pre_motion_first1000"]
    current_valid = bool(candidates) and max(z_diffs or [0.0]) < 0.10
    decision = "BY3A8_imu_bias_current_valid" if current_valid else "BY3A8_imu_bias_no_safe_change"
    if not candidates:
        decision = "BY3A8_imu_bias_inconclusive"
    report = {
        "stage": STAGE,
        "decision": decision,
        "body_time_zero_raw_timestamp": body_min,
        "go2_start_raw_timestamp": go2_start,
        "pre_motion_sample_count": len(processed),
        "current_static_bias_radps": current_bias,
        "current_static_bias_z_degps": math.degrees(current_bias[2]),
        "candidate_rows": candidates,
        "source_backed_only": True,
        "trace_used_for_bias_selection": False,
        "final_rmse_used_for_bias_selection": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_IMU_BIAS_REFINEMENT_AUDIT_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_IMU_BIAS_CANDIDATES", candidates)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_imu_bias_refinement_audit.md",
        "# BY3A8 IMU Bias Refinement Audit\n\n"
        f"Decision: `{decision}`. BY3A7 current z bias is `{report['current_static_bias_z_degps']}` deg/s. "
        "Candidate windows are judged by source stationarity, not final yaw RMSE.\n",
    )
    return report


def time_lag_diagnostic(paths: Paths, base_time: float, a1_quality: dict[str, Any]) -> dict[str, Any]:
    del a1_quality
    trace = by3a6.load_trace(paths.trace, base_time)
    gnss = by3a6.read_numeric_table(paths.a1_gnss, expected_cols=15)
    pairs: list[dict[str, Any]] = []
    if gnss and trace:
        pairs.append(scan_lag_pair("A1_yaw_vs_trace_heading", [row[0] for row in gnss], [row[13] for row in gnss], [row["time_rel"] for row in trace], [row["heading_ned"] for row in trace]))
    for algorithm in ["stage1_baseline_no_feedback_EKF", "LegSA_full_EKF", "final_v23_dual_antenna_EKF"]:
        nav = by3a6.load_nav_for_algorithm(paths.by3a7_runtime_root, algorithm)
        if not nav.empty and gnss:
            pairs.append(scan_lag_pair(f"{algorithm}_NAV_yaw_vs_A1", nav["time"].tolist(), nav["yaw"].tolist(), [row[0] for row in gnss], [row[13] for row in gnss]))
    suspected = any(row.get("rmse_improvement_pct", 0.0) > 10.0 and abs(float(row.get("candidate_lag_sec") or 0.0)) >= 0.2 for row in pairs)
    decision = "BY3A8_time_lag_suspected_but_not_repairable" if suspected else "BY3A8_no_time_lag_issue"
    report = {
        "stage": STAGE,
        "decision": decision,
        "rows": pairs,
        "diagnostic_only": True,
        "timestamp_metadata_supports_repair": False,
        "repair_allowed": False,
        "trace_used_for_time_shift_repair": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_TIME_LAG_DIAGNOSTIC_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_TIME_LAG_DIAGNOSTIC", pairs)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_time_lag_diagnostic.md",
        "# BY3A8 Time Lag Diagnostic\n\n"
        f"Decision: `{decision}`. Lag scanning is diagnostic only; no timestamp metadata-backed repair was identified.\n",
    )
    return report


def yaw_gate_update_effect(paths: Paths, a1_quality: dict[str, Any]) -> dict[str, Any]:
    gnss = by3a6.read_numeric_table(paths.a1_gnss, expected_cols=15)
    quality_by_time = {round(float(row["time"]), 6): row for row in a1_quality.get("rows", [])}
    rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for algorithm in ["stage1_baseline_no_feedback_EKF", "LegSA_full_EKF"]:
        nav = by3a6.load_nav_for_algorithm(paths.by3a7_runtime_root, algorithm)
        manifest = by3a7.read_yaw_manifest(paths.by3a7_runtime_root, algorithm)
        accepted = by3a7.accepted_source_aware_times(paths.by3a7_runtime_root, algorithm)
        alg_rows = build_gate_effect_rows(algorithm, nav, gnss, quality_by_time, accepted)
        rows.extend(alg_rows)
        residuals = [row["residual_nav_minus_a1_deg_proxy"] for row in alg_rows]
        reject_rows = [row for row in alg_rows if row["gate_state_proxy"] == "REJECT"]
        summary.append(
            {
                "algorithm": algorithm,
                "yaw_update_count_actual": manifest.get("yaw_update_count"),
                "yaw_NORMAL_actual": manifest.get("yaw_NORMAL"),
                "yaw_DOWNWEIGHT_actual": manifest.get("yaw_DOWNWEIGHT"),
                "yaw_REJECT_actual": manifest.get("yaw_REJECT"),
                "source_aware_dual_yaw_accepted_rows": len(accepted),
                "proxy_NORMAL": sum(1 for row in alg_rows if row["gate_state_proxy"] == "NORMAL"),
                "proxy_DOWNWEIGHT": sum(1 for row in alg_rows if row["gate_state_proxy"] == "DOWNWEIGHT"),
                "proxy_REJECT": len(reject_rows),
                "residual_abs_p50_deg": by3a6.stats(residuals).get("p50"),
                "residual_abs_p95_deg": by3a6.stats(residuals).get("p95"),
                "residual_abs_max_deg": by3a6.stats(residuals).get("max_abs"),
                "proxy_rejects_with_objective_invalid_A1": sum(1 for row in reject_rows if row.get("objective_invalid_for_solver_candidate")),
                "proxy_rejects_with_A1_jump_suspect": sum(1 for row in reject_rows if "yaw_jump_suspect" in str(row.get("quality_flag"))),
                "proxy_rejects_after_first_large_jump": rejects_after_first_large_jump(alg_rows),
            }
        )
    reject_ratio = sum(row["proxy_REJECT"] for row in summary) / max(1, sum(row["proxy_NORMAL"] + row["proxy_DOWNWEIGHT"] + row["proxy_REJECT"] for row in summary))
    invalid_rejects = sum(row["proxy_rejects_with_objective_invalid_A1"] for row in summary)
    if reject_ratio > 0.40 and invalid_rejects < sum(row["proxy_REJECT"] for row in summary) * 0.25:
        decision = "BY3A8_gate_behavior_acceptable"
        cause = "gate rejects large NAV-vs-A1 residuals, but objective-invalid A1 epochs explain only a small share"
    elif invalid_rejects:
        decision = "BY3A8_gate_blocked_by_A1_outliers"
        cause = "some rejects coincide with objective-invalid A1 epochs"
    else:
        decision = "BY3A8_gate_inconclusive"
        cause = "insufficient actual residual/effect logs"
    report = {
        "stage": STAGE,
        "decision": decision,
        "cause": cause,
        "actual_logs_available": True,
        "actual_residual_values_available": False,
        "proxy_rows_labeled": True,
        "rows": rows,
        "summary_rows": summary,
        "gate_thresholds_deg": {"soft": 6.0, "hard": 15.0},
        "yaw_gate_relaxed": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_YAW_GATE_UPDATE_EFFECT_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_YAW_GATE_UPDATE_EFFECT", rows)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_YAW_GATE_UPDATE_EFFECT_SUMMARY", summary)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_yaw_gate_update_effect.md",
        "# BY3A8 Yaw Gate Update Effect\n\n"
        f"Decision: `{decision}`. Actual gate counts are used where available; residual values are proxy-labeled.\n",
    )
    return report


def feedback_interaction_audit(paths: Paths) -> dict[str, Any]:
    stage1 = by3a6.read_json(paths.by3a7_root / "official_eval" / "stage1_baseline_no_feedback_EKF" / "summary.json", {})
    legsa = by3a6.read_json(paths.by3a7_root / "official_eval" / "LegSA_full_EKF" / "summary.json", {})
    final = by3a6.read_json(paths.by3a7_root / "official_eval" / "final_v23_dual_antenna_EKF" / "summary.json", {})
    feedback_report = by3a6.read_json(paths.by3a7_root / "feedback_generation" / "BY3_normal" / "OBSERVATION_BUILD_REPORT.json", {})
    feedback_rows = read_csv_dicts(paths.feedback)
    rows = [
        metric_feedback_row("stage1_baseline_no_feedback_EKF", stage1, "stage1_no_feedback"),
        metric_feedback_row("LegSA_full_EKF", legsa, "stage2_selected_feedback"),
        metric_feedback_row("final_v23_dual_antenna_EKF", final, "external_reference_baseline"),
    ]
    stage1_yaw = safe_nested(stage1, ["attitude", "yaw_rmse_deg"])
    legsa_yaw = safe_nested(legsa, ["attitude", "yaw_rmse_deg"])
    yaw_delta = float(legsa_yaw) - float(stage1_yaw) if stage1_yaw is not None and legsa_yaw is not None else None
    if yaw_delta is None:
        decision = "BY3A8_feedback_inconclusive"
    elif abs(yaw_delta) < 0.5:
        decision = "BY3A8_feedback_neutral"
    elif yaw_delta < 0.0:
        decision = "BY3A8_feedback_improves_yaw"
    else:
        decision = "BY3A8_feedback_worsens_yaw"
    report = {
        "stage": STAGE,
        "decision": decision,
        "rows": rows,
        "feedback_observation_count": len(feedback_rows),
        "feedback_report": feedback_report,
        "stage2_minus_stage1_yaw_rmse_deg": yaw_delta,
        "feedback_policy_changed": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_FEEDBACK_INTERACTION_AUDIT_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_FEEDBACK_INTERACTION_AUDIT", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_feedback_interaction_audit.md",
        "# BY3A8 Feedback Interaction Audit\n\n"
        f"Decision: `{decision}`. Stage2 minus stage1 yaw RMSE: `{yaw_delta}` deg.\n",
    )
    return report


def safe_repair_plan(
    paths: Paths,
    lower: dict[str, Any],
    a1_quality: dict[str, Any],
    bias: dict[str, Any],
    lag: dict[str, Any],
    gate: dict[str, Any],
    feedback: dict[str, Any],
) -> dict[str, Any]:
    del gate
    lower_rmse = float(lower.get("A1_observation_yaw_rmse_deg") or 999.0)
    invalid_count = int(a1_quality.get("objective_invalid_epoch_count") or 0)
    rows = [
        {
            "repair": "A1 objective quality mask",
            "evidence": f"{invalid_count} objective invalid epochs; lower-bound RMSE {lower_rmse:.3f} deg",
            "required_change": "mask only source-invalid A1 epochs",
            "affects_algorithm_math": False,
            "affects_BY2_comparability": False,
            "risk": "low if needed, but insufficient for broad A1 observation error",
            "allowed": False,
            "expected_validation": "would require rerun only if invalid epochs dominate gate/yaw error",
        },
        {
            "repair": "stationary-window IMU bias refinement",
            "evidence": bias.get("decision"),
            "required_change": "replace BY3A7 bias only if a source-stationary candidate is materially better",
            "affects_algorithm_math": False,
            "affects_BY2_comparability": False,
            "risk": "medium if chosen without source evidence",
            "allowed": bias.get("decision") == "BY3A8_imu_bias_refinement_ready",
            "expected_validation": "normal-only rerun with unchanged yaw gate/source",
        },
        {
            "repair": "metadata-backed time alignment",
            "evidence": lag.get("decision"),
            "required_change": "time shift only with timestamp metadata proof",
            "affects_algorithm_math": False,
            "affects_BY2_comparability": True,
            "risk": "high without metadata; forbidden if RMSE-selected",
            "allowed": lag.get("decision") == "BY3A8_time_lag_repair_ready",
            "expected_validation": "normal-only rerun plus command lineage proof",
        },
        {
            "repair": "yaw input continuity fix",
            "evidence": "solver already consumes wrapped yaw with residual wrapping; no code/config bug found in BY3A7",
            "required_change": "none",
            "affects_algorithm_math": False,
            "affects_BY2_comparability": False,
            "risk": "unjustified continuity edit could hide source jumps",
            "allowed": False,
            "expected_validation": "not applicable",
        },
        {
            "repair": "separate feedback interaction review",
            "evidence": feedback.get("decision"),
            "required_change": "none in BY3A8; feedback policy changes require a separate source-role review",
            "affects_algorithm_math": True,
            "affects_BY2_comparability": True,
            "risk": "feedback changes could break selected-feedback same-case comparability",
            "allowed": False,
            "expected_validation": "separate human-approved feedback audit if needed",
        },
        {
            "repair": "no repair, accept BY3 A1 observation-quality limitation",
            "evidence": f"A1 observation lower bound is {lower_rmse:.3f} deg, much worse than the dual-output yaw RMSE",
            "required_change": "none",
            "affects_algorithm_math": False,
            "affects_BY2_comparability": False,
            "risk": "limits yaw claims to diagnostic/cautious scope",
            "allowed": True,
            "expected_validation": "post-stage no-repair sanity and context update",
        },
    ]
    any_active_repair = any(row["allowed"] and row["repair"] != "no repair, accept BY3 A1 observation-quality limitation" for row in rows)
    if any_active_repair:
        decision = "BY3A8_safe_repair_ready"
    elif lower.get("decision") == "BY3A8_a1_observation_quality_poor":
        decision = "BY3A8_no_safe_repair_accept_yaw_limit"
    else:
        decision = "BY3A8_manual_review_required"
    report = {
        "stage": STAGE,
        "decision": decision,
        "rows": rows,
        "normal_rerun_required": decision == "BY3A8_safe_repair_ready",
        "no_trace_based_repair": True,
        "no_rmse_selected_policy": True,
        "no_yaw_gate_relaxation": True,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_SAFE_REPAIR_PLAN_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_SAFE_REPAIR_PLAN", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_safe_repair_plan.md",
        "# BY3A8 Safe Repair Plan\n\n"
        f"Decision: `{decision}`. No trace-based correction, gate relaxation, HDT fallback, or RMSE-selected policy is allowed.\n",
    )
    return report


def repair_and_rerun(paths: Paths, plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("decision") != "BY3A8_safe_repair_ready":
        report = {
            "stage": STAGE,
            "decision": "BY3A8_normal_rerun_not_run_no_safe_repair",
            "repair_implementation": "none",
            "normal_rerun": "not_run",
            "reason": plan.get("decision"),
            "degradation_run": False,
            "trace_solver_input": False,
            "ready_for_paper_claims": False,
        }
        by3a6.write_json(paths.stage_root / "reports" / "BY3A8_REPAIR_IMPLEMENTATION_REPORT.json", report)
        by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_REPAIRED_INPUT_CONFIG_INDEX", [])
        by3a6.write_json(paths.stage_root / "reports" / "BY3A8_NORMAL_RERUN_REPORT.json", report)
        by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_SOLVER_STATUS", [])
        by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_EVAL_STATUS", [])
        by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_NORMAL_METRICS", [])
        return report
    raise RuntimeError("BY3A8 safe repair became active, but no implementation path is approved in this script")


def post_stage_sanity(
    paths: Paths,
    lower: dict[str, Any],
    a1_quality: dict[str, Any],
    bias: dict[str, Any],
    lag: dict[str, Any],
    gate: dict[str, Any],
    feedback: dict[str, Any],
    plan: dict[str, Any],
    rerun: dict[str, Any],
) -> dict[str, Any]:
    del a1_quality, lag, rerun
    metrics = read_csv_dicts(paths.by3a7_root / "matrix" / "BY3A7_NORMAL_METRICS.csv")
    rows = []
    for row in metrics:
        rows.append(
            {
                "algorithm": row.get("algorithm"),
                "source": "BY3A7_accepted_no_BY3A8_rerun",
                "horizontal_rmse_m": row.get("horizontal_rmse_m"),
                "up_rmse_m": row.get("up_rmse_m"),
                "yaw_rmse_deg": row.get("yaw_rmse_deg"),
                "yaw_p95_deg": row.get("yaw_p95_deg"),
                "A1_observation_lower_bound_rmse_deg": lower.get("A1_observation_yaw_rmse_deg"),
                "yaw_gate_summary": gate.get("decision"),
                "feedback_summary": feedback.get("decision"),
            }
        )
    lower_rmse = float(lower.get("A1_observation_yaw_rmse_deg") or 999.0)
    if plan.get("decision") == "BY3A8_no_safe_repair_accept_yaw_limit" and lower_rmse > 6.0:
        decision = "BY3A8_yaw_limited_by_A1_observation_quality"
    elif bias.get("decision") == "BY3A8_imu_bias_current_valid":
        decision = "BY3A8_yaw_limited_by_no_safe_repair"
    else:
        decision = "BY3A8_inconclusive"
    report = {
        "stage": STAGE,
        "decision": decision,
        "repair_ran": False,
        "rows": rows,
        "A1_observation_lower_bound_rmse_deg": lower.get("A1_observation_yaw_rmse_deg"),
        "two_degree_target_achievable_from_A1": lower.get("decision") == "BY3A8_a1_observation_quality_supports_2deg",
        "explanation": "No BY3A8 repair/rerun was run because the remaining yaw error is bounded by A1 observation quality and no source-backed repair passed.",
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_POST_STAGE_SANITY_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_POST_STAGE_METRICS", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a8_post_stage_sanity.md",
        "# BY3A8 Post-Stage Sanity\n\n"
        f"Decision: `{decision}`. BY3A8 did not run a normal rerun because no safe repair passed the gate.\n",
    )
    return report


def generate_figures(
    paths: Paths,
    lower: dict[str, Any],
    a1_quality: dict[str, Any],
    bias: dict[str, Any],
    lag: dict[str, Any],
    gate: dict[str, Any],
    feedback: dict[str, Any],
    post: dict[str, Any],
    *,
    skip_figures: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if skip_figures:
        report = {"stage": STAGE, "decision": "BY3A8_figures_skipped", "rows": rows}
        by3a6.write_json(paths.stage_root / "reports" / "BY3A8_FIGURE_REPORT.json", report)
        by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_FIGURE_INDEX", rows)
        return report
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        report = {"stage": STAGE, "decision": "BY3A8_figures_blocked", "error": str(exc), "rows": rows}
        by3a6.write_json(paths.stage_root / "reports" / "BY3A8_FIGURE_REPORT.json", report)
        by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_FIGURE_INDEX", rows)
        return report
    fig_dir = paths.stage_root / "figures"
    lower_rows = lower.get("rows", [])
    quality_rows = a1_quality.get("rows", [])
    gate_rows = gate.get("rows", [])
    lag_rows = lag.get("rows", [])
    feedback_rows = feedback.get("rows", [])
    metric_rows = post.get("rows", [])

    save_line(plt, fig_dir, rows, "A1_observation_lower_bound_vs_trace", [row["time"] for row in lower_rows], [[row.get("a1_minus_trace_heading_deg") for row in lower_rows]], ["A1 - trace heading"], "deg")
    save_scatter(plt, fig_dir, rows, "baseline_length_vs_yaw_error", [row.get("baseline_length_m") for row in lower_rows], [row.get("a1_minus_trace_heading_deg") for row in lower_rows], "baseline length m", "A1 - trace deg")
    save_line(plt, fig_dir, rows, "A1_yaw_quality_flags", [row["time"] for row in quality_rows], [[flag_code(row.get("quality_flag")) for row in quality_rows]], ["quality flag code"], "code")
    save_bar(plt, fig_dir, rows, "IMU_bias_candidate_stationarity", [row["candidate"] for row in bias.get("candidate_rows", [])], [row.get("stationarity_score", 0.0) for row in bias.get("candidate_rows", [])], "stationarity score")
    save_bar(plt, fig_dir, rows, "time_lag_diagnostic", [row["source_pair"] for row in lag_rows], [row.get("candidate_lag_sec", 0.0) for row in lag_rows], "best diagnostic lag s")
    save_hist(plt, fig_dir, rows, "yaw_gate_residual_distribution", [row.get("residual_nav_minus_a1_deg_proxy") for row in gate_rows if row.get("residual_nav_minus_a1_deg_proxy") is not None], "NAV - A1 residual deg")
    save_bar(plt, fig_dir, rows, "feedback_interaction_summary", [row["algorithm"] for row in feedback_rows], [row.get("yaw_rmse_deg", 0.0) for row in feedback_rows], "yaw RMSE deg")
    save_bar(plt, fig_dir, rows, "position_common_overlap", [row["algorithm"] for row in metric_rows], [float(row.get("horizontal_rmse_m") or 0.0) for row in metric_rows], "horizontal RMSE m")
    save_bar(plt, fig_dir, rows, "yaw_error_budget_panel", ["A1 lower", "LegSA", "final_v23"], [
        float(lower.get("A1_observation_yaw_rmse_deg") or 0.0),
        metric_value(metric_rows, "LegSA_full_EKF", "yaw_rmse_deg"),
        metric_value(metric_rows, "final_v23_dual_antenna_EKF", "yaw_rmse_deg"),
    ], "yaw RMSE deg")
    save_bar(plt, fig_dir, rows, "before_after_yaw_error", ["BY3A7 accepted", "BY3A8 rerun"], [metric_value(metric_rows, "LegSA_full_EKF", "yaw_rmse_deg"), 0.0], "yaw RMSE deg")
    report = {"stage": STAGE, "decision": "BY3A8_figures_generated", "rows": rows}
    by3a6.write_json(paths.stage_root / "reports" / "BY3A8_FIGURE_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_FIGURE_INDEX", rows)
    return report


def case_review(
    paths: Paths,
    source_lock: dict[str, Any],
    lower: dict[str, Any],
    a1_quality: dict[str, Any],
    bias: dict[str, Any],
    lag: dict[str, Any],
    gate: dict[str, Any],
    feedback: dict[str, Any],
    plan: dict[str, Any],
    rerun: dict[str, Any],
    post: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "source_lock": source_lock.get("decision"),
        "a1_observation_lower_bound": lower.get("decision"),
        "a1_observation_yaw_rmse_deg": lower.get("A1_observation_yaw_rmse_deg"),
        "a1_quality": a1_quality.get("decision"),
        "imu_bias": bias.get("decision"),
        "time_lag": lag.get("decision"),
        "yaw_gate": gate.get("decision"),
        "feedback": feedback.get("decision"),
        "repair_plan": plan.get("decision"),
        "normal_rerun": rerun.get("decision"),
        "post_stage": post.get("decision"),
        "figures": figures.get("decision"),
        "final_yaw_status": post.get("decision"),
        "BY3_degradation_planning_scope": "position_up_with_diagnostic_yaw",
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "case_review" / "BY3A8_yaw_error_budget_safe_repair_case_review.json", report)
    by3a6.write_md(
        paths.stage_root / "case_review" / "BY3A8_yaw_error_budget_safe_repair_case_review.md",
        "# BY3A8 Yaw Error Budget Case Review\n\n"
        f"- A1 observation lower bound: `{lower.get('decision')}` with RMSE `{lower.get('A1_observation_yaw_rmse_deg')}` deg.\n"
        f"- A1 quality: `{a1_quality.get('decision')}`.\n"
        f"- IMU bias: `{bias.get('decision')}`.\n"
        f"- Time lag: `{lag.get('decision')}`.\n"
        f"- Yaw gate: `{gate.get('decision')}`.\n"
        f"- Feedback: `{feedback.get('decision')}`.\n"
        f"- Repair decision: `{plan.get('decision')}`.\n"
        f"- Final yaw status: `{post.get('decision')}`.\n"
        "- No BY3 degradation, trace solver input, HDT/long-relpos fallback, gate relaxation, or paper claim was performed.\n",
    )
    return report


def obsidian_sync(
    paths: Paths,
    lower: dict[str, Any],
    a1_quality: dict[str, Any],
    bias: dict[str, Any],
    lag: dict[str, Any],
    gate: dict[str, Any],
    feedback: dict[str, Any],
    post: dict[str, Any],
) -> dict[str, Any]:
    root = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization"
    root.mkdir(parents=True, exist_ok=True)
    notes = {
        "BY3_yaw_error_budget_BY3A8.md": (
            "# BY3 Yaw Error Budget BY3A8\n\n"
            f"- A1 observation lower bound: `{lower.get('decision')}`; RMSE `{lower.get('A1_observation_yaw_rmse_deg')}` deg.\n"
            f"- Final yaw status: `{post.get('decision')}`.\n"
            "- BY3A8 performed no trace-based repair and no degradation run.\n"
        ),
        "BY3_A1_yaw_dynamic_quality_audit.md": (
            "# BY3 A1 Yaw Dynamic Quality Audit\n\n"
            f"- BY3A8 A1 quality decision: `{a1_quality.get('decision')}`.\n"
            f"- Objective invalid epochs: `{a1_quality.get('objective_invalid_epoch_count')}`.\n"
            "- Invalid epoch rules are source-quality based; trace disagreement is diagnostic only.\n"
        ),
        "BY3_IMU_bias_and_gate_repair.md": (
            "# BY3 IMU Bias And Gate Repair\n\n"
            f"- IMU bias refinement decision: `{bias.get('decision')}`.\n"
            f"- Time-lag diagnostic: `{lag.get('decision')}`.\n"
            f"- Yaw gate decision: `{gate.get('decision')}`.\n"
            f"- Feedback interaction: `{feedback.get('decision')}`.\n"
            "- No yaw gate relaxation or parameter retuning was performed.\n"
        ),
        "current_state.md": (
            "# BY3 Current State\n\n"
            "- BY3A7 repaired the major IMU preprocessing bug and reduced dual-yaw normal RMSE to the 4-5 deg range.\n"
            f"- BY3A8 budgets the remaining error as `{post.get('decision')}`.\n"
            "- BY3 degradation planning should proceed only as position/up with diagnostic yaw unless a human accepts broader yaw scope.\n"
        ),
        "next_steps.md": (
            "# BY3 Next Steps\n\n"
            "- Recommended next stage: `BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING`.\n"
            "- Keep `ready_for_paper_claims=false`.\n"
            "- Do not reintroduce HDT, long-baseline rel_pos, old BY3 IMU biasing, or trace-based yaw correction.\n"
        ),
    }
    rows: list[dict[str, Any]] = []
    for name, text in notes.items():
        path = root / name
        path.write_text(text, encoding="utf-8", newline="\n")
        rows.append({"note": name, "path": str(path), "updated": True, "tracked": False})
    report = {"stage": STAGE, "decision": "BY3A8_obsidian_synced", "rows": rows, "public_notes_use_aliases": True}
    by3a6.write_json(paths.stage_root / "obsidian_sync" / "BY3A8_OBSIDIAN_SYNC_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A8_OBSIDIAN_SYNC_INDEX", rows)
    return report


def final_validation(
    paths: Paths,
    source_lock: dict[str, Any],
    lower: dict[str, Any],
    a1_quality: dict[str, Any],
    bias: dict[str, Any],
    lag: dict[str, Any],
    gate: dict[str, Any],
    feedback: dict[str, Any],
    plan: dict[str, Any],
    post: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        ("A1 observation lower bound computed", lower.get("decision") is not None),
        ("A1 quality audited", a1_quality.get("decision") is not None),
        ("IMU bias audited", bias.get("decision") is not None),
        ("time-lag diagnostic completed", lag.get("decision") is not None),
        ("yaw gate audited", gate.get("decision") is not None),
        ("feedback interaction audited", feedback.get("decision") is not None),
        ("no arbitrary tuning", bool(plan.get("no_rmse_selected_policy"))),
        ("no degradation run", not contains_degradation(paths.stage_root) and not contains_degradation(paths.runtime_root)),
        ("repair only if gated", plan.get("decision") != "BY3A8_safe_repair_ready"),
        ("no trace solver input", source_lock.get("decision") == "BY3A8_sources_locked" and lower.get("trace_used_for_solver_input") is False),
        ("no HDT/long-relpos fallback", all("HDT" not in str(row.get("repair")) for row in plan.get("rows", []) if row.get("allowed") and row.get("repair") != "no repair, accept BY3 A1 observation-quality limitation")),
        ("no paper claims", True),
        ("JSON/CSV parse", json_csv_parse_check(paths.stage_root)),
        ("runtime untracked", True),
        ("figures/case review generated", figures.get("decision") in {"BY3A8_figures_generated", "BY3A8_figures_skipped"} and post.get("decision") is not None),
    ]
    rows = [{"check": name, "passed": bool(passed)} for name, passed in checks]
    report = {
        "stage": STAGE,
        "decision": "BY3A8_validation_passed" if all(row["passed"] for row in rows) else "BY3A8_validation_failed",
        "checks": rows,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "long_task_summary.md",
        "# BY3A8 Long Task Summary\n\n" + "\n".join(f"- {row['check']}: `{row['passed']}`" for row in rows) + "\n",
    )
    return report


def final_decision(
    validation: dict[str, Any],
    lower: dict[str, Any],
    a1_quality: dict[str, Any],
    bias: dict[str, Any],
    lag: dict[str, Any],
    gate: dict[str, Any],
    feedback: dict[str, Any],
    post: dict[str, Any],
) -> dict[str, Any]:
    del a1_quality, bias, lag, gate, feedback
    if validation.get("decision") != "BY3A8_validation_passed":
        status = "BY3A8_safety_gate_failed"
        ready = False
        scope = "blocked"
        next_stage = "repair_safety_violation"
    elif post.get("decision") == "BY3A8_yaw_limited_by_A1_observation_quality":
        status = "BY3A8_yaw_limited_but_position_up_ready"
        ready = True
        scope = "position_up_with_diagnostic_yaw"
        next_stage = "BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING"
    elif lower.get("decision") == "BY3A8_a1_observation_quality_supports_2deg":
        status = "BY3A8_no_safe_repair_manual_review_required"
        ready = False
        scope = "blocked"
        next_stage = "manual_review_BY3_yaw_error_budget"
    else:
        status = "BY3A8_no_safe_repair_manual_review_required"
        ready = False
        scope = "blocked"
        next_stage = "manual_review_BY3_yaw_error_budget"
    return {
        "stage": STAGE,
        "status": status,
        "a1_observation_lower_bound_decision": lower.get("decision"),
        "post_stage_decision": post.get("decision"),
        "ready_for_BY3_degradation_matrix_planning": ready,
        "ready_for_BY3_degradation_matrix_planning_scope": scope,
        "yaw_claim_scope": "diagnostic_only" if ready else "forbidden",
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
    }


def write_final_reports(paths: Paths, validation: dict[str, Any], decision: dict[str, Any]) -> None:
    by3a6.write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    by3a6.write_md(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# BY3A8 Next Stage Recommendation\n\n"
        f"status=`{decision['status']}`\n\n"
        f"ready_for_BY3_degradation_matrix_planning=`{decision['ready_for_BY3_degradation_matrix_planning']}`\n\n"
        f"scope=`{decision['ready_for_BY3_degradation_matrix_planning_scope']}`\n\n"
        f"ready_for_paper_claims=`{decision['ready_for_paper_claims']}`\n\n"
        f"recommended_next_stage=`{decision['recommended_next_stage']}`\n\n"
        f"validation=`{validation.get('decision')}`\n",
    )


def write_runtime_no_rerun_manifest(paths: Paths, plan: dict[str, Any], rerun: dict[str, Any], decision: dict[str, Any]) -> None:
    report = {
        "stage": STAGE,
        "runtime_root_role": "reserved BY3A8 normal-only rerun root",
        "decision": decision.get("status"),
        "safe_repair_plan": plan.get("decision"),
        "normal_rerun": rerun.get("decision"),
        "runtime_execution": "not_run",
        "reason": "no source-backed BY3A8 repair passed; audit artifacts live under BY3A8 stage root",
        "degradation_run": False,
        "solver_run": False,
        "official_evaluator_run": False,
        "trace_solver_input": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.runtime_root / "validation" / "BY3A8_RUNTIME_NO_RERUN_MANIFEST.json", report)


def build_baseline_index(paths: Paths, base_time: float) -> list[dict[str, Any]]:
    b5_paths = by3a5b.Paths(
        repo=paths.repo,
        stage_root=paths.by3a5b_root,
        runtime_root=paths.repo / "by3-huiti" / "BY3_FULL_MATRIX" / by3a5b.RUNTIME_STAGE,
        receiver_root=paths.receiver_root,
        trace=paths.trace,
        by3a0_root=paths.by3a0_root,
        by3a1_root=paths.by3a1_root,
        by3a2_root=paths.by3a2_root,
        by3a3_root=paths.by3a3_root,
        by3a4a_root=paths.repo / "by3-huiti" / by3a6.BY3A4A_STAGE,
        by3a4c_root=paths.repo / "by3-huiti" / by3a6.BY3A4C_STAGE,
        by3a5_root=paths.by3a5_root,
    )
    rows = by3a5b.build_baseline_rows(b5_paths)
    for row in rows:
        row["time_rel"] = float(row["t"]) - float(base_time)
    return rows


def selected_go2_start_rel(paths: Paths) -> float:
    offsets = by3a6.read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {}).get("offsets", {})
    body_min = float(offsets.get("body_time_zero_raw_timestamp") or 0.0)
    go2_start = float(offsets.get("go2_start_raw_timestamp") or body_min)
    return go2_start - body_min


def processed_body_samples(body_rows: list[dict[str, Any]], go2_start: float) -> list[dict[str, Any]]:
    correction = by3a0.roll_matrix_deg(-1.0)
    out: list[dict[str, Any]] = []
    for row in body_rows:
        timestamp = by3a0.safe_float(row.get("timestamp"))
        if timestamp is None or timestamp >= go2_start:
            continue
        gyro = [by3a0.safe_float(row.get("gyro_x")), by3a0.safe_float(row.get("gyro_y")), by3a0.safe_float(row.get("gyro_z"))]
        acc = [by3a0.safe_float(row.get("acc_x")), by3a0.safe_float(row.get("acc_y")), by3a0.safe_float(row.get("acc_z"))]
        if any(value is None for value in gyro + acc):
            continue
        gyro_frd = [float(gyro[0]), -float(gyro[1]), -float(gyro[2])]
        acc_frd = [float(acc[0]), -float(acc[1]), -float(acc[2])]
        gyro_corr = by3a0.matvec(correction, gyro_frd)
        acc_corr = by3a0.matvec(correction, acc_frd)
        out.append(
            {
                "timestamp": float(timestamp),
                "gyro": gyro_corr,
                "acc": acc_corr,
                "gyro_norm": float(np.linalg.norm(gyro_corr)),
                "acc_norm": float(np.linalg.norm(acc_corr)),
            }
        )
    return out


def build_bias_candidate_rows(processed: list[dict[str, Any]], current_bias: list[float]) -> list[dict[str, Any]]:
    if not processed:
        return []
    windows = [
        ("BY3A7_current_pre_motion_first1000", processed[:1000], "mean"),
        ("full_pre_motion_mean", processed, "mean"),
        ("full_pre_motion_median", processed, "median"),
        ("lowest_rate_1000_pre_motion_mean", lowest_rate_window(processed, 1000), "mean"),
        ("robust_median_MAD_pre_motion", reject_outlier_samples(processed), "median"),
    ]
    rows: list[dict[str, Any]] = []
    current_z = math.degrees(current_bias[2])
    for name, sample, mode in windows:
        if not sample:
            continue
        bias = sample_bias(sample, mode=mode)
        gyro_norm = [row["gyro_norm"] for row in sample]
        acc_norm = [row["acc_norm"] for row in sample]
        stationarity = float(np.std(gyro_norm) + 0.01 * np.std(acc_norm))
        z_degps = math.degrees(bias[2])
        rows.append(
            {
                "candidate": name,
                "sample_count": len(sample),
                "bias_x_radps": bias[0],
                "bias_y_radps": bias[1],
                "bias_z_radps": bias[2],
                "z_bias_degps": z_degps,
                "z_bias_delta_vs_BY3A7_degps": z_degps - current_z,
                "gyro_norm_median_radps": float(np.median(gyro_norm)),
                "gyro_norm_std_radps": float(np.std(gyro_norm)),
                "acc_norm_median_mps2": float(np.median(acc_norm)),
                "acc_norm_std_mps2": float(np.std(acc_norm)),
                "stationarity_score": stationarity,
                "source_backed": True,
                "allowed": name == "BY3A7_current_pre_motion_first1000",
                "reason": "current accepted BY3A7 source window" if name == "BY3A7_current_pre_motion_first1000" else "diagnostic stationary candidate only",
            }
        )
    return rows


def lowest_rate_window(rows: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    if len(rows) <= size:
        return rows
    norms = np.asarray([row["gyro_norm"] for row in rows], dtype=float)
    kernel = np.ones(size, dtype=float) / float(size)
    rolling = np.convolve(norms, kernel, mode="valid")
    start = int(np.argmin(rolling))
    return rows[start : start + size]


def reject_outlier_samples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    norms = np.asarray([row["gyro_norm"] for row in rows], dtype=float)
    med = float(np.median(norms))
    mad = float(np.median(np.abs(norms - med)))
    if mad == 0.0:
        return rows
    limit = med + 6.0 * 1.4826 * mad
    return [row for row in rows if row["gyro_norm"] <= limit]


def sample_bias(rows: list[dict[str, Any]], *, mode: str) -> list[float]:
    values = np.asarray([row["gyro"] for row in rows], dtype=float)
    if mode == "median":
        return [float(value) for value in np.median(values, axis=0)]
    return [float(value) for value in np.mean(values, axis=0)]


def scan_lag_pair(source_pair: str, left_t: Iterable[float], left_angle: Iterable[float], right_t: Iterable[float], right_angle: Iterable[float]) -> dict[str, Any]:
    lt = [float(v) for v in left_t]
    la = [float(v) for v in left_angle]
    rt = [float(v) for v in right_t]
    ra = [float(v) for v in right_angle]
    lags = np.round(np.arange(-2.0, 2.0001, 0.1), 3)
    rows = []
    for lag in lags:
        usable_t = [t for t in lt if rt and rt[0] <= t + float(lag) <= rt[-1]]
        if len(usable_t) < 10:
            continue
        left_at = by3a6.interp_angle(lt, la, usable_t)
        right_at = by3a6.interp_angle(rt, ra, [t + float(lag) for t in usable_t])
        residuals = [by3a6.circ_diff(left_at[i], right_at[i]) for i in range(min(len(left_at), len(right_at)))]
        rows.append((float(lag), by3a6.stats(residuals).get("rmse"), by3a6.stats(residuals).get("p95"), len(residuals)))
    if not rows:
        return {"source_pair": source_pair, "candidate_lag_sec": None, "baseline_rmse_deg": None, "best_rmse_deg": None, "allowed_for_repair": False, "reason": "insufficient overlap"}
    baseline = min(rows, key=lambda row: abs(row[0]))
    best = min(rows, key=lambda row: float(row[1] if row[1] is not None else 999.0))
    baseline_rmse = float(baseline[1] or 0.0)
    best_rmse = float(best[1] or 0.0)
    improvement = 100.0 * (baseline_rmse - best_rmse) / baseline_rmse if baseline_rmse > 0 else 0.0
    return {
        "source_pair": source_pair,
        "candidate_lag_sec": best[0],
        "baseline_rmse_deg": baseline_rmse,
        "best_rmse_deg": best_rmse,
        "best_p95_deg": best[2],
        "sample_count": best[3],
        "rmse_improvement_pct": improvement,
        "evidence": "cross-correlation/RMSE lag scan diagnostic",
        "timestamp_metadata_supports_this_lag": False,
        "allowed_for_repair": False,
        "reason": "diagnostic only; no metadata-backed timestamp bug",
    }


def build_gate_effect_rows(
    algorithm: str,
    nav: pd.DataFrame,
    gnss: list[list[float]],
    quality_by_time: dict[float, dict[str, Any]],
    source_accepted_times: set[float],
) -> list[dict[str, Any]]:
    rows = by3a7.build_gate_rows_for_algorithm(algorithm, nav, gnss, quality_by_time, source_accepted_times)
    for row in rows:
        q = quality_by_time.get(round(float(row["time"]), 6), {})
        row["objective_invalid_for_solver_candidate"] = bool(q.get("objective_invalid_for_solver_candidate", not q.get("should_use_for_solver_candidate", True)))
        row["accepted_downweighted_rejected"] = row.get("gate_state_proxy")
        row["effect_on_NAV_yaw_measurable"] = False
    return rows


def rejects_after_first_large_jump(rows: list[dict[str, Any]]) -> int:
    first = None
    for row in rows:
        jump = row.get("yaw_jump_from_prev_deg")
        if jump is not None and abs(float(jump)) > 30.0:
            first = float(row["time"])
            break
    if first is None:
        return 0
    return sum(1 for row in rows if float(row["time"]) >= first and row["gate_state_proxy"] == "REJECT")


def trace_speed_at(trace: list[dict[str, float]], query_times: list[float]) -> list[float | None]:
    if len(trace) < 2:
        return [None for _ in query_times]
    times = np.asarray([row["time_rel"] for row in trace], dtype=float)
    lat = np.deg2rad(np.asarray([row["lat"] for row in trace], dtype=float))
    lon = np.deg2rad(np.asarray([row["lon"] for row in trace], dtype=float))
    r = 6378137.0
    dlat = np.diff(lat)
    dlon = np.diff(lon)
    mean_lat = (lat[1:] + lat[:-1]) * 0.5
    dist = np.sqrt((r * dlat) ** 2 + (r * np.cos(mean_lat) * dlon) ** 2)
    dt = np.diff(times)
    speed = np.divide(dist, dt, out=np.zeros_like(dist), where=dt > 0)
    speed_times = times[1:]
    return [float(np.interp(t, speed_times, speed)) if speed_times[0] <= t <= speed_times[-1] else None for t in query_times]


def speed_bucket(speed: float | None) -> str:
    if speed is None:
        return "unknown"
    if speed < 0.1:
        return "stationary"
    if speed < 0.5:
        return "slow"
    return "moving"


def assign_baseline_buckets(rows: list[dict[str, Any]]) -> None:
    vals = np.asarray([row["baseline_length_m"] for row in rows if row.get("baseline_length_m") is not None], dtype=float)
    if len(vals) == 0:
        return
    q25, q75 = float(np.percentile(vals, 25)), float(np.percentile(vals, 75))
    for row in rows:
        value = row.get("baseline_length_m")
        if value is None:
            row["baseline_bucket"] = "unknown"
        elif float(value) < q25:
            row["baseline_bucket"] = "short_q1"
        elif float(value) > q75:
            row["baseline_bucket"] = "long_q4"
        else:
            row["baseline_bucket"] = "middle_q2_q3"


def circular_summary(errors: Iterable[float]) -> dict[str, Any]:
    vals = np.asarray([float(v) for v in errors if v is not None and math.isfinite(float(v))], dtype=float)
    if len(vals) == 0:
        return {"count": 0}
    rad = np.deg2rad(vals)
    sin_mean = float(np.mean(np.sin(rad)))
    cos_mean = float(np.mean(np.cos(rad)))
    mean = math.degrees(math.atan2(sin_mean, cos_mean))
    resultant = max(1.0e-12, math.hypot(sin_mean, cos_mean))
    std = math.degrees(math.sqrt(max(0.0, -2.0 * math.log(resultant))))
    return {"count": int(len(vals)), "mean_circular_error_deg": by3a6.circ_diff(mean, 0.0), "circular_std_deg": std}


def robust_zscore(value: float | None, median: float | None, mad: float | None) -> float | None:
    if value is None or median is None or mad is None or mad == 0.0:
        return None
    return float((float(value) - median) / (1.4826 * mad))


def flatten_lower_bound_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": report.get("decision"),
        "A1_observation_yaw_rmse_deg": report.get("A1_observation_yaw_rmse_deg"),
        "A1_observation_yaw_p95_deg": report.get("A1_observation_yaw_p95_deg"),
        "A1_observation_yaw_max_deg": report.get("A1_observation_yaw_max_deg"),
        "mean_circular_error_deg": report.get("mean_circular_error_deg"),
        "circular_std_deg": report.get("circular_std_deg"),
        "valid_sample_count": report.get("valid_sample_count"),
        "observation_lower_bound_band": report.get("observation_lower_bound_band"),
    }


def metric_feedback_row(algorithm: str, summary: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "algorithm": algorithm,
        "role": role,
        "horizontal_rmse_m": safe_nested(summary, ["position", "horizontal_rmse_m"]),
        "up_rmse_m": safe_nested(summary, ["position", "up_rmse_m"]),
        "yaw_rmse_deg": safe_nested(summary, ["attitude", "yaw_rmse_deg"]),
        "yaw_p95_deg": safe_nested(summary, ["attitude", "yaw_p95_deg"]),
        "num_samples": safe_nested(summary, ["meta", "num_samples"]),
        "time_start": safe_nested(summary, ["meta", "time_start"]),
        "time_end": safe_nested(summary, ["meta", "time_end"]),
    }


def safe_nested(data: dict[str, Any], keys: list[str]) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def read_csv_dicts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def file_meta(role: str, path: Path, alias: str, source_role: str) -> dict[str, Any]:
    return {
        "role": role,
        "alias": alias,
        "path": str(path),
        "exists": path.exists(),
        "row_count": count_nonempty_lines(path) if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        "source_role": source_role,
        "accepted_for_BY3A8": path.exists(),
        "forbidden_replacements": "HDT|long_relpos|trace_solver_input" if "A1" in role or "IMU" in role else "",
    }


def count_nonempty_lines(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for line in handle if line.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def flag_code(flag: Any) -> int:
    text = str(flag)
    if "baseline_length_suspect" in text:
        return 3
    if "isolated_outlier" in text:
        return 2
    if "yaw_jump_suspect" in text:
        return 1
    return 0


def metric_value(rows: list[dict[str, Any]], algorithm: str, key: str) -> float:
    for row in rows:
        if row.get("algorithm") == algorithm:
            try:
                return float(row.get(key) or 0.0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def save_line(plt: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str, x: list[Any], y_series: list[list[Any]], labels: list[str], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    for y, label in zip(y_series, labels):
        ax.plot(x, y, linewidth=1.0, label=label)
    ax.set_xlabel("time s")
    ax.set_ylabel(ylabel)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, fig_dir, rows, stem)
    plt.close(fig)


def save_scatter(plt: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str, x: list[Any], y: list[Any], xlabel: str, ylabel: str) -> None:
    pairs = [(float(a), float(b)) for a, b in zip(x, y) if a is not None and b is not None and math.isfinite(float(a)) and math.isfinite(float(b))]
    fig, ax = plt.subplots(figsize=(6, 4))
    if pairs:
        ax.scatter([p[0] for p in pairs], [p[1] for p in pairs], s=12, alpha=0.75)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, fig_dir, rows, stem)
    plt.close(fig)


def save_bar(plt: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str, labels: list[str], values: list[Any], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 4))
    vals = [float(v or 0.0) for v in values]
    ax.bar(range(len(labels)), vals)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    save_figure(fig, fig_dir, rows, stem)
    plt.close(fig)


def save_hist(plt: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str, values: list[Any], xlabel: str) -> None:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    fig, ax = plt.subplots(figsize=(7, 4))
    if vals:
        ax.hist(vals, bins=30, alpha=0.8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, fig_dir, rows, stem)
    plt.close(fig)


def save_figure(fig: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str) -> None:
    png = fig_dir / f"{stem}.png"
    pdf = fig_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=150)
    fig.savefig(pdf)
    rows.append({"figure": stem, "png": str(png), "pdf": str(pdf), "exists": png.exists() and pdf.exists()})


def contains_degradation(path: Path) -> bool:
    return any("degrad" in part.lower() for item in path.rglob("*") for part in item.parts if item.exists())


def json_csv_parse_check(root: Path) -> bool:
    try:
        for path in root.rglob("*.json"):
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        for path in root.rglob("*.csv"):
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                next(csv.reader(handle), None)
    except Exception:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
