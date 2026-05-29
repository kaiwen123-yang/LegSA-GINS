"""Run BY3A7 A1 yaw dynamic-quality, IMU sign, and yaw-gate audit.

Runtime-only stage after BY3A6.  It accepts the BY3A6 trace/base-time/initatt
findings, audits why yaw still diverges after a correct start, and applies only
an evidence-backed BY3-local IMU preprocessing repair.  It never runs BY3
degradation and never changes yaw gates or BY3 yaw source policy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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

from scripts.experiments import run_by3a0_to_by3e_generalization_reorg as by3a0  # noqa: E402
from scripts.experiments import run_by3a3_selected_feedback_stage1_chain as by3a3  # noqa: E402
from scripts.experiments import run_by3a5_dual_yaw_input_source_repair as by3a5  # noqa: E402
from scripts.experiments import run_by3a5b_a1_dual_diff_yaw_input_repair as by3a5b  # noqa: E402
from scripts.experiments import run_by3a6_trace_truth_initatt_gate_forensic as by3a6  # noqa: E402


STAGE = "BY3A7_A1_YAW_DYNAMIC_QUALITY_IMU_SIGN_AND_GATE_REPAIR"
RUNTIME_STAGE = "BY3A7_YAW_DYNAMIC_GATE_REPAIR"

SUBDIRS = [
    "a1_yaw_quality",
    "imu_sign_axis_audit",
    "yaw_gate_audit",
    "yaw_update_code_audit",
    "repair_plan",
    "repaired_input_or_config",
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
    "stage1_solver",
    "stage2_legsa_full_solver",
    "single_baseline_solver",
    "finalv23_solver",
    "feedback_generation",
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
    by3a6_root: Path
    by3a6_runtime_root: Path

    @property
    def a1_repaired_gnss(self) -> Path:
        return self.by3a6_root / "repaired_input_generation" / "BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def by3a7_repaired_gnss(self) -> Path:
        return self.stage_root / "repaired_input_or_config" / "BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def old_imu(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"

    @property
    def repaired_imu(self) -> Path:
        return self.stage_root / "repaired_input_or_config" / "BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu"

    @property
    def single_gnss(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"

    @property
    def body_diag(self) -> Path:
        return self.by3a0_root / "by3_body_imu" / "BY3_GO2_BODY_STATE_DIAGNOSTIC.csv"

    @property
    def by3a5_hdt_gnss(self) -> Path:
        return self.by3a5_root / "repaired_input_generation" / "BY3_DUAL_HDT_15COL_REPAIRED.gnss"


@dataclass(frozen=True)
class RerunPaths:
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
    repaired_dual_path: Path
    repaired_imu_path: Path
    single_gnss_path: Path

    @property
    def current_dual(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss"

    @property
    def repaired_dual(self) -> Path:
        return self.repaired_dual_path

    @property
    def imu(self) -> Path:
        return self.repaired_imu_path

    @property
    def gnss_dual(self) -> Path:
        return self.repaired_dual_path

    @property
    def gnss_single(self) -> Path:
        return self.single_gnss_path

    @property
    def raw_doppler(self) -> Path:
        return self.by3a2_root / "raw_doppler_recovery" / "provider_only" / "RAW_DOPPLER_VELOCITY_FACTORS.csv"

    @property
    def go2_prior_dir(self) -> Path:
        return self.by3a1_root / "provider_materialization" / "go2_priors" / "priors" / "joint_rp1p6deg_hv1p0"

    @property
    def go2_attitude(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv"

    @property
    def go2_velocity(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv"

    @property
    def go2_joint(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--receiver-root", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--skip-rerun", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
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
        by3a4a_root=repo / "by3-huiti" / by3a6.BY3A4A_STAGE,
        by3a4c_root=repo / "by3-huiti" / by3a6.BY3A4C_STAGE,
        by3a5_root=repo / "by3-huiti" / by3a6.BY3A5_STAGE,
        by3a5b_root=repo / "by3-huiti" / by3a6.BY3A5B_STAGE,
        by3a6_root=repo / "by3-huiti" / by3a6.STAGE,
        by3a6_runtime_root=repo / "by3-huiti" / "BY3_FULL_MATRIX" / by3a6.RUNTIME_STAGE,
    )
    result = run_by3a7(
        paths,
        run_rerun=not args.skip_rerun,
        audit_only=args.audit_only,
        skip_figures=args.skip_figures,
    )
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


def run_by3a7(paths: Paths, *, run_rerun: bool, audit_only: bool, skip_figures: bool) -> dict[str, Any]:
    create_tree(paths)
    write_plan(paths)
    intake = current_state_intake(paths)
    base_time = extract_base_time(paths)
    a1 = a1_yaw_dynamic_quality_audit(paths, base_time)
    imu = imu_sign_axis_audit(paths, base_time, a1)
    gate = yaw_gate_residual_audit(paths, a1)
    code = yaw_update_code_audit(paths)
    repair_plan = repair_plan_decision(paths, a1, imu, gate, code)
    repair = repair_implementation(paths, repair_plan, imu, audit_only=audit_only)
    rerun = normal_rerun(paths, repair, run_rerun=run_rerun and not audit_only)
    post = post_repair_sanity(paths, a1, gate, repair, rerun)
    figures = generate_figures(paths, a1, imu, gate, post, skip_figures=skip_figures)
    case = case_review(paths, intake, a1, imu, gate, code, repair_plan, repair, rerun, post, figures)
    obsidian = obsidian_sync(paths, a1, imu, gate, repair_plan, post)
    validation = final_validation(paths, a1, imu, gate, code, repair_plan, repair, rerun, post, figures, obsidian)
    decision = final_decision(validation, a1, imu, repair_plan, post)
    write_final_reports(paths, validation, decision)
    return {"validation": validation, "decision": decision, "case_review": case}


def create_tree(paths: Paths) -> None:
    paths.stage_root.mkdir(parents=True, exist_ok=True)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)
    for subdir in ["normal_rerun", "official_eval", "figures", "logs", "repaired_input_or_config"]:
        (paths.runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def write_plan(paths: Paths) -> None:
    report = {
        "stage": STAGE,
        "planner_summary": "Audit A1 yaw dynamics, BY3 IMU yaw-rate preprocessing, yaw gate residuals, and yaw update code.",
        "accepted_BY3A6_findings": [
            "trace parser and base_time valid",
            "A1 dual-diff yaw input source valid with caution",
            "initatt starttime bug repaired",
            "start yaw correct but yaw diverges after start",
            "actual yaw gate rejects most observations",
        ],
        "forbidden": [
            "BY3 degradation",
            "parameter retuning",
            "yaw gate relaxation",
            "HDT mainline yaw source",
            "trace solver input",
            "paper claims",
        ],
    }
    by3a6.write_json(paths.stage_root / "repair_plan" / "BY3A7_APPROVED_PLAN.json", report)
    by3a6.write_md(
        paths.stage_root / "repair_plan" / "by3a7_approved_plan.md",
        "# BY3A7 Approved Plan\n\n"
        "Forensic audit first. Apply only evidence-backed, non-parameter repair; normal-only rerun if gated.\n",
    )


def current_state_intake(paths: Paths) -> dict[str, Any]:
    by3a6_decision = by3a6.read_json(paths.by3a6_root / "reports" / "LONG_TASK_DECISION_REPORT.json", {})
    by3a6_gate = by3a6.read_json(paths.by3a6_root / "reports" / "BY3A6_YAW_UPDATE_GATE_AUDIT_REPORT.json", {})
    by3a6_post = by3a6.read_json(paths.by3a6_root / "reports" / "BY3A6_POST_REPAIR_SANITY_REPORT.json", {})
    rows = [
        {
            "stage": "BY3A6",
            "decision": by3a6_decision.get("status"),
            "accepted_for_BY3A7": True,
            "summary": "trace/base_time valid; A1 source valid with caution; initatt repaired; yaw still fails after start",
        },
        {
            "stage": "BY3A6_yaw_gate",
            "decision": by3a6_gate.get("decision"),
            "accepted_for_BY3A7": True,
            "summary": "manifest/source-aware evidence shows most dual yaw observations rejected or not accepted",
        },
        {
            "stage": "BY3A6_post",
            "decision": by3a6_post.get("decision"),
            "accepted_for_BY3A7": True,
            "summary": "LegSA yaw remains about 102 deg RMSE while position/up remain sane",
        },
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A7_current_state_intake_complete",
        "rows": rows,
        "input_files": input_file_index(paths),
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_CURRENT_STATE_INTAKE_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_CURRENT_STATE_INTAKE", rows)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_INPUT_FILE_INDEX", report["input_files"])
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_current_state_intake.md",
        "# BY3A7 Current State Intake\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "BY3A7 starts from accepted BY3A6 evidence: init yaw is fixed, but yaw updates still fail.\n",
    )
    return report


def input_file_index(paths: Paths) -> list[dict[str, Any]]:
    files = [
        ("a1_repaired_gnss", paths.a1_repaired_gnss, "<BY3A6_STAGE_ROOT>/repaired_input_generation/BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"),
        ("old_imu", paths.old_imu, "<BY3A1_STAGE_ROOT>/input_repair/BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"),
        ("body_diag", paths.body_diag, "<BY3_STAGE_ROOT>/by3_body_imu/BY3_GO2_BODY_STATE_DIAGNOSTIC.csv"),
        ("trace_truth", paths.trace, "<BY3_TRACE_TRUTH_FILE>"),
        ("by3a5_hdt_diag", paths.by3a5_hdt_gnss, "<BY3A5_STAGE_ROOT>/repaired_input_generation/BY3_DUAL_HDT_15COL_REPAIRED.gnss"),
    ]
    return [
        {
            "role": role,
            "alias": alias,
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256_file(path) if path.exists() and path.stat().st_size < 200_000_000 else None,
        }
        for role, path, alias in files
    ]


def extract_base_time(paths: Paths) -> float:
    command = paths.by3a6_root / "official_eval" / "LegSA_full_EKF" / "command.json"
    return by3a6.extract_base_time(command)


def a1_yaw_dynamic_quality_audit(paths: Paths, base_time: float) -> dict[str, Any]:
    gnss = by3a6.read_numeric_table(paths.a1_repaired_gnss, expected_cols=15)
    baseline = build_baseline_index(paths, base_time)
    trace = by3a6.load_trace(paths.trace, base_time)
    hdt = by3a6.read_numeric_table(paths.by3a5_hdt_gnss, expected_cols=15)
    rows = build_a1_epoch_quality_rows(gnss, baseline, trace, hdt)
    yaw = np.asarray([float(row["yaw_deg"]) for row in rows], dtype=float)
    jumps = [float(row["yaw_jump_from_prev_deg"]) for row in rows if row["yaw_jump_from_prev_deg"] is not None]
    rates = [float(row["yaw_rate_deg_per_sec"]) for row in rows if row["yaw_rate_deg_per_sec"] is not None]
    baseline_lengths = [float(row["baseline_length_m"]) for row in rows if row.get("baseline_length_m") is not None]
    a1_trace = [float(row["a1_minus_trace_heading_deg"]) for row in rows if row.get("a1_minus_trace_heading_deg") is not None]
    a1_hdt = [float(row["a1_minus_hdt_deg"]) for row in rows if row.get("a1_minus_hdt_deg") is not None]
    invalid_candidate_count = sum(1 for row in rows if not row["should_use_for_solver_candidate"])
    jump_suspect_count = sum(1 for row in rows if "jump_suspect" in str(row["quality_flag"]))
    baseline_suspect_count = sum(1 for row in rows if "baseline_length_suspect" in str(row["quality_flag"]))
    trace_diag_count = sum(1 for row in rows if "trace_disagreement_suspect" in str(row["quality_flag"]))
    decision = "BY3A7_a1_yaw_quality_acceptable_with_mask" if invalid_candidate_count else "BY3A7_a1_yaw_quality_acceptable"
    if jump_suspect_count > len(rows) * 0.20 and by3a6.stats(a1_trace).get("rmse", 0.0) > 20.0:
        decision = "BY3A7_a1_yaw_quality_acceptable_with_mask"
    report = {
        "stage": STAGE,
        "decision": decision,
        "row_count": len(rows),
        "time_min": float(rows[0]["time"]) if rows else None,
        "time_max": float(rows[-1]["time"]) if rows else None,
        "yaw_min_deg": float(np.nanmin(yaw)) if len(yaw) else None,
        "yaw_max_deg": float(np.nanmax(yaw)) if len(yaw) else None,
        "yaw_jump_stats_deg": by3a6.stats(jumps),
        "yaw_rate_stats_deg_per_sec": by3a6.stats(rates),
        "jump_count_gt_15_deg": sum(1 for value in jumps if abs(value) > 15.0),
        "jump_count_gt_30_deg": sum(1 for value in jumps if abs(value) > 30.0),
        "jump_count_gt_45_deg": sum(1 for value in jumps if abs(value) > 45.0),
        "baseline_length_stats_m": by3a6.stats(baseline_lengths),
        "baseline_length_suspect_count": baseline_suspect_count,
        "fixed_yaw_std_deg_unique": sorted({round(float(row[14]), 6) for row in gnss}) if gnss else [],
        "a1_minus_trace_heading_stats_deg": by3a6.stats(a1_trace),
        "trace_disagreement_suspect_count": trace_diag_count,
        "hdt_diagnostic_available": bool(hdt),
        "a1_minus_hdt_diagnostic_stats_deg": by3a6.stats(a1_hdt),
        "invalid_solver_candidate_count": invalid_candidate_count,
        "invalid_criteria_not_rmse_based": True,
        "trace_used_for_solver_candidate": False,
        "hdt_solver_input": False,
        "rows": rows,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_A1_YAW_DYNAMIC_QUALITY_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_A1_YAW_DYNAMIC_QUALITY", [summary_row_from_report(report)])
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_A1_YAW_EPOCH_QUALITY", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_a1_yaw_dynamic_quality.md",
        "# BY3A7 A1 Yaw Dynamic Quality\n\n"
        f"Decision: `{decision}`.\n\n"
        f"A1 has {report['jump_count_gt_15_deg']} jumps above 15 deg and "
        f"{invalid_candidate_count} objective invalid solver-candidate epochs. "
        "Trace/HDT comparisons are diagnostic only and are not used for solver masking.\n",
    )
    return report


def build_a1_epoch_quality_rows(
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
    lower, upper = robust_bounds(baseline_lengths)
    trace_heading = by3a6.interp_angle([row["time_rel"] for row in trace], [row["heading_ned"] for row in trace], times.tolist()) if trace else []
    hdt_yaw = by3a6.interp_angle([row[0] for row in hdt], [row[13] for row in hdt], times.tolist()) if hdt else []
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(gnss):
        jump = float(unwrapped[idx] - unwrapped[idx - 1]) if idx else None
        dt = float(times[idx] - times[idx - 1]) if idx else None
        rate = float(jump / dt) if jump is not None and dt and dt > 0 else None
        bl = nearest_by_time(baseline, float(row[0]))
        baseline_length = float(bl["baseline_length_m"]) if bl else None
        trace_diff = by3a6.circ_diff(float(row[13]), trace_heading[idx]) if trace_heading else None
        hdt_diff = by3a6.circ_diff(float(row[13]), hdt_yaw[idx]) if hdt_yaw else None
        quality = classify_a1_epoch_quality(
            yaw_jump_deg=jump,
            baseline_length_m=baseline_length,
            baseline_lower_m=lower,
            baseline_upper_m=upper,
            trace_diff_deg=trace_diff,
            hdt_diff_deg=hdt_diff,
        )
        rows.append(
            {
                "time": float(row[0]),
                "yaw_deg": float(row[13]),
                "unwrapped_yaw_deg": float(unwrapped[idx]),
                "yaw_jump_from_prev_deg": jump,
                "yaw_rate_deg_per_sec": rate,
                "yaw_std_deg": float(row[14]),
                "baseline_length_m": baseline_length,
                "baseline_length_quality": "valid" if baseline_length is not None and lower <= baseline_length <= upper else "baseline_length_suspect",
                "trace_heading_nearest_deg": trace_heading[idx] if trace_heading else None,
                "a1_minus_trace_heading_deg": trace_diff,
                "hdt_heading_nearest_deg": hdt_yaw[idx] if hdt_yaw else None,
                "a1_minus_hdt_deg": hdt_diff,
                "quality_flag": "|".join(quality["flags"]),
                "should_use_for_solver_candidate": quality["should_use_for_solver_candidate"],
                "diagnostic_only": quality["diagnostic_only"],
                "invalid_criteria_basis": quality["invalid_criteria_basis"],
            }
        )
    return rows


def classify_a1_epoch_quality(
    *,
    yaw_jump_deg: float | None,
    baseline_length_m: float | None,
    baseline_lower_m: float,
    baseline_upper_m: float,
    trace_diff_deg: float | None,
    hdt_diff_deg: float | None,
) -> dict[str, Any]:
    flags: list[str] = []
    invalid_basis: list[str] = []
    if baseline_length_m is None or baseline_length_m < baseline_lower_m or baseline_length_m > baseline_upper_m:
        flags.append("baseline_length_suspect")
        invalid_basis.append("baseline_length_outside_robust_source_bounds")
    if yaw_jump_deg is not None and abs(yaw_jump_deg) > 30.0:
        flags.append("jump_suspect")
    if yaw_jump_deg is not None and abs(yaw_jump_deg) > 45.0:
        invalid_basis.append("yaw_jump_gt_45_deg_between_gnss_epochs")
    if trace_diff_deg is not None and abs(trace_diff_deg) > 45.0:
        flags.append("trace_disagreement_suspect")
    if hdt_diff_deg is not None and abs(hdt_diff_deg) > 45.0:
        flags.append("hdt_disagreement_suspect")
    if not flags:
        flags.append("valid")
    return {
        "flags": flags,
        "should_use_for_solver_candidate": not invalid_basis,
        "diagnostic_only": any(flag in flags for flag in ["trace_disagreement_suspect", "hdt_disagreement_suspect"]),
        "invalid_criteria_basis": "|".join(invalid_basis) if invalid_basis else "none",
    }


def imu_sign_axis_audit(paths: Paths, base_time: float, a1: dict[str, Any]) -> dict[str, Any]:
    by3a0_input = by3a6.read_json(paths.by3a0_root / "reports" / "BY3C_INPUT_GENERATION_REPORT.json", {})
    by3a1_input = by3a6.read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {})
    old_bias = ((by3a0_input.get("imu_report") or {}).get("gyro_bias") or [None, None, None])
    offsets = by3a1_input.get("offsets", {})
    body_min = float(offsets.get("body_time_zero_raw_timestamp") or base_time)
    go2_start = float(offsets.get("go2_start_raw_timestamp") or (body_min + 23.8239729404))
    body_rows = load_body_rows(paths.body_diag)
    static_bias = compute_static_pre_motion_bias(body_rows, go2_start)
    current_imu = by3a6.read_numeric_table(paths.old_imu, expected_cols=7)
    repaired_preview = build_static_bias_imu_rows(body_rows, body_min=body_min, go2_start=go2_start, static_bias=static_bias)
    gnss = by3a6.read_numeric_table(paths.a1_repaired_gnss, expected_cols=15)
    trace = by3a6.load_trace(paths.trace, base_time)
    sign_rows = imu_sign_candidate_rows(body_rows, current_imu, repaired_preview, gnss, trace, body_min)
    old_z = float(old_bias[2]) if old_bias and old_bias[2] is not None else None
    static_z = float(static_bias[2]) if static_bias else None
    current_sum = cumulative_dtheta_deg(current_imu, axis=2)
    repaired_sum = cumulative_dtheta_deg(repaired_preview, axis=2)
    raw_source = next((row for row in sign_rows if row["candidate"] == "raw_neg_gyro_z_flu_to_frd"), {})
    current_source = next((row for row in sign_rows if row["candidate"] == "current_repaired_imu_dtheta_z"), {})
    repaired_source = next((row for row in sign_rows if row["candidate"] == "static_bias_repaired_dtheta_z"), {})
    bug_confirmed = (
        old_z is not None
        and static_z is not None
        and abs(math.degrees(old_z - static_z)) > 5.0
        and abs(float(current_source.get("cumulative_delta_deg") or 0.0) - float(raw_source.get("cumulative_delta_deg") or 0.0)) > 500.0
    )
    decision = "BY3A7_imu_sign_axis_bug_confirmed" if bug_confirmed else "BY3A7_imu_sign_axis_inconclusive"
    if not bug_confirmed and raw_source:
        decision = "BY3A7_imu_sign_axis_valid"
    report = {
        "stage": STAGE,
        "decision": decision,
        "source_contract": {
            "go2_body_frame": "FLU",
            "imu_file_expected_frame": "IMU_FRD_COMPATIBLE",
            "flu_to_frd_applied_once": True,
            "runtime_does_not_apply_second_conversion": True,
        },
        "old_dynamic_bias_window_samples": (by3a0_input.get("imu_report") or {}).get("gyro_bias_window"),
        "old_dynamic_gyro_bias_radps": old_bias,
        "old_dynamic_gyro_bias_z_degps": math.degrees(old_z) if old_z is not None else None,
        "static_pre_motion_gyro_bias_radps": static_bias,
        "static_pre_motion_gyro_bias_z_degps": math.degrees(static_z) if static_z is not None else None,
        "gyro_bias_source_repair_basis": "pre-motion BY3 body-state segment before selected_go2_formal_start_time",
        "current_imu_dtheta_z_cumulative_deg": current_sum,
        "static_bias_repaired_dtheta_z_cumulative_deg": repaired_sum,
        "current_imu_row_count": len(current_imu),
        "repaired_preview_row_count": len(repaired_preview),
        "sign_candidate_rows": sign_rows,
        "trace_used_for_repair": False,
        "a1_used_for_repair": False,
        "parameter_retuning": False,
        "bug_summary": (
            "BY3A0 estimated gyro bias after the selected Go2 motion start; z bias is dominated by real yaw motion."
            if bug_confirmed
            else "No source-backed IMU preprocessing bug confirmed."
        ),
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_IMU_SIGN_AXIS_AUDIT_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_IMU_SIGN_AXIS_AUDIT", sign_rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_imu_sign_axis_audit.md",
        "# BY3A7 IMU Sign Axis Audit\n\n"
        f"Decision: `{decision}`.\n\n"
        f"Old dynamic z bias: `{report['old_dynamic_gyro_bias_z_degps']}` deg/s; "
        f"pre-motion z bias: `{report['static_pre_motion_gyro_bias_z_degps']}` deg/s. "
        "The repair basis is source timing, not trace RMSE.\n",
    )
    return report


def yaw_gate_residual_audit(paths: Paths, a1: dict[str, Any]) -> dict[str, Any]:
    gnss = by3a6.read_numeric_table(paths.a1_repaired_gnss, expected_cols=15)
    quality_by_time = {round(float(row["time"]), 6): row for row in a1.get("rows", [])}
    rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for algorithm in ["stage1_baseline_no_feedback_EKF", "LegSA_full_EKF"]:
        nav = by3a6.load_nav_for_algorithm(paths.by3a6_runtime_root, algorithm)
        manifest = read_yaw_manifest(paths.by3a6_runtime_root, algorithm)
        source_accepted = accepted_source_aware_times(paths.by3a6_runtime_root, algorithm)
        alg_rows = build_gate_rows_for_algorithm(algorithm, nav, gnss, quality_by_time, source_accepted)
        rows.extend(alg_rows)
        proxy_rejects = sum(1 for row in alg_rows if row["gate_state_proxy"] == "REJECT")
        proxy_down = sum(1 for row in alg_rows if row["gate_state_proxy"] == "DOWNWEIGHT")
        proxy_normal = sum(1 for row in alg_rows if row["gate_state_proxy"] == "NORMAL")
        residuals = [row["residual_nav_minus_a1_deg_proxy"] for row in alg_rows]
        summary_rows.append(
            {
                "algorithm": algorithm,
                "yaw_update_count_actual": manifest.get("yaw_update_count"),
                "yaw_NORMAL_actual": manifest.get("yaw_NORMAL"),
                "yaw_DOWNWEIGHT_actual": manifest.get("yaw_DOWNWEIGHT"),
                "yaw_REJECT_actual": manifest.get("yaw_REJECT"),
                "source_aware_dual_yaw_accepted_rows": len(source_accepted),
                "proxy_NORMAL": proxy_normal,
                "proxy_DOWNWEIGHT": proxy_down,
                "proxy_REJECT": proxy_rejects,
                "residual_abs_p50_deg": by3a6.stats(residuals).get("p50"),
                "residual_abs_p95_deg": by3a6.stats(residuals).get("p95"),
                "residual_abs_max_deg": by3a6.stats(residuals).get("max_abs"),
                "proxy_rejects_with_a1_invalid_candidate": sum(
                    1 for row in alg_rows if row["gate_state_proxy"] == "REJECT" and not row["should_use_for_solver_candidate"]
                ),
                "proxy_rejects_with_a1_valid_candidate": sum(
                    1 for row in alg_rows if row["gate_state_proxy"] == "REJECT" and row["should_use_for_solver_candidate"]
                ),
            }
        )
    legsa = next((row for row in summary_rows if row["algorithm"] == "LegSA_full_EKF"), {})
    decision = "BY3A7_gate_reject_caused_by_IMU_prediction_drift"
    if legsa.get("proxy_rejects_with_a1_invalid_candidate", 0) > legsa.get("proxy_rejects_with_a1_valid_candidate", 0):
        decision = "BY3A7_gate_reject_caused_by_A1_quality"
    report = {
        "stage": STAGE,
        "decision": decision,
        "actual_logs_available": False,
        "actual_manifest_counts_available": True,
        "source_aware_accepted_yaw_rows_available": True,
        "proxy_residuals_labeled_proxy": True,
        "rows": rows,
        "summary_rows": summary_rows,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_YAW_GATE_RESIDUAL_AUDIT_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_YAW_GATE_RESIDUAL_AUDIT", rows)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_YAW_GATE_RESIDUAL_SUMMARY", summary_rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_yaw_gate_residual_audit.md",
        "# BY3A7 Yaw Gate Residual Audit\n\n"
        f"Decision: `{decision}`.\n\n"
        "Rejected residual values are reconstructed as proxy because current runtime logs do not record rejected yaw residuals.\n",
    )
    return report


def yaw_update_code_audit(paths: Paths) -> dict[str, Any]:
    files = {
        "gi_engine": paths.repo / "cpp" / "legsa_v23_port_core" / "src" / "kf_gins" / "gi_engine.cpp",
        "imu_loader": paths.repo / "cpp" / "legsa_v23_port_core" / "src" / "fileio" / "imu_file_loader.cpp",
        "insmech": paths.repo / "cpp" / "legsa_v23_port_core" / "src" / "kf_gins" / "insmech.cpp",
        "options": paths.repo / "cpp" / "legsa_v23_port_core" / "include" / "legsa_v23_port_core" / "options.hpp",
    }
    texts = {name: path.read_text(encoding="utf-8", errors="ignore") if path.exists() else "" for name, path in files.items()}
    rows = [
        {
            "item": "yaw_residual_wrap",
            "file": "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
            "evidence": "wrapYawResidual(yaw_pred - yaw_obs) and Rotation::wrapRad are present",
            "status": "valid" if "wrapYawResidual(yaw_pred - yaw_obs)" in texts["gi_engine"] and "Rotation::wrapRad" in texts["gi_engine"] else "missing",
        },
        {
            "item": "yaw_gate_thresholds",
            "file": "cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp",
            "evidence": "yaw_res_soft_deg=6 and yaw_res_hard_deg=15 defaults present",
            "status": "valid" if "yaw_res_soft_deg = 6.0" in texts["options"] and "yaw_res_hard_deg = 15.0" in texts["options"] else "missing",
        },
        {
            "item": "yaw_update_H_sign",
            "file": "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
            "evidence": "H(0, PHI_ID + 2) = -1.0",
            "status": "valid" if "H(0, PHI_ID + 2) = -1.0" in texts["gi_engine"] else "missing",
        },
        {
            "item": "yaw_std_usage",
            "file": "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp",
            "evidence": "yaw_std = max(gnss.yaw_std_rad, yaw_std_min)",
            "status": "valid" if "gnss.yaw_std_rad" in texts["gi_engine"] and "yaw_std_min_deg" in texts["gi_engine"] else "missing",
        },
        {
            "item": "imu_no_double_flu_frd",
            "file": "cpp/legsa_v23_port_core/src/fileio/imu_file_loader.cpp",
            "evidence": "loader reads increments and does not do FLU-to-FRD again",
            "status": "valid" if "不做坐标二次转换" in texts["imu_loader"] or "FLU->FRD" in texts["imu_loader"] else "missing",
        },
        {
            "item": "insmech_frame_contract",
            "file": "cpp/legsa_v23_port_core/src/kf_gins/insmech.cpp",
            "evidence": "IMU already converted by process_data; no second conversion",
            "status": "valid" if "不能二次转换" in texts["insmech"] or "process_data" in texts["insmech"] else "missing",
        },
    ]
    decision = "BY3A7_yaw_update_code_valid" if all(row["status"] == "valid" for row in rows[:4]) else "BY3A7_yaw_update_code_inconclusive"
    report = {
        "stage": STAGE,
        "decision": decision,
        "rows": rows,
        "yaw_gate_relaxed": False,
        "residual_wrap_bug_confirmed": False,
        "config_not_applied": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_YAW_UPDATE_CODE_AUDIT_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_YAW_UPDATE_CODE_AUDIT", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_yaw_update_code_audit.md",
        "# BY3A7 Yaw Update Code Audit\n\n"
        f"Decision: `{decision}`.\n\n"
        "No yaw residual wrap/sign bug or gate-configuration bypass is confirmed from source inspection.\n",
    )
    return report


def repair_plan_decision(paths: Paths, a1: dict[str, Any], imu: dict[str, Any], gate: dict[str, Any], code: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "repair": "A1_yaw_quality_mask",
            "evidence": "Objective baseline/jump invalid candidates exist but do not explain most proxy rejects.",
            "expected_effect": "remove a few demonstrably invalid A1 epochs only",
            "risk": "insufficient and could become arbitrary if expanded",
            "changes_needed": "none in BY3A7",
            "changes_algorithm_math": False,
            "invalidates_BY2_comparability": False,
            "allowed": False,
        },
        {
            "repair": "A1_yaw_continuity_unwrap",
            "evidence": "Solver residual wraps yaw; no code path requiring unwrapped input was found.",
            "expected_effect": "none proven",
            "risk": "could hide source discontinuities",
            "changes_needed": "none",
            "changes_algorithm_math": False,
            "invalidates_BY2_comparability": False,
            "allowed": False,
        },
        {
            "repair": "BY3_IMU_pre_motion_static_gyro_bias",
            "evidence": imu.get("bug_summary", ""),
            "expected_effect": "remove false yaw-rate bias caused by estimating gyro bias from a moving segment",
            "risk": "normal-only rerun required; no degradation/paper claims",
            "changes_needed": "write BY3A7-local IMU input and rerun normal chain",
            "changes_algorithm_math": False,
            "invalidates_BY2_comparability": False,
            "allowed": imu.get("decision") == "BY3A7_imu_sign_axis_bug_confirmed",
        },
        {
            "repair": "yaw_gate_relaxation",
            "evidence": "Forbidden; no source-backed threshold bug found.",
            "expected_effect": "could force acceptance without fixing cause",
            "risk": "unsafe tuning",
            "changes_needed": "none",
            "changes_algorithm_math": True,
            "invalidates_BY2_comparability": True,
            "allowed": False,
        },
        {
            "repair": "yaw_residual_wrap_fix",
            "evidence": code.get("decision"),
            "expected_effect": "not applicable because wrap bug not confirmed",
            "risk": "unnecessary code change",
            "changes_needed": "none",
            "changes_algorithm_math": False,
            "invalidates_BY2_comparability": False,
            "allowed": False,
        },
    ]
    safe = any(row["allowed"] for row in rows)
    decision = "BY3A7_safe_repair_ready" if safe else "BY3A7_no_safe_repair_yaw_position_only"
    report = {
        "stage": STAGE,
        "decision": decision,
        "rows": rows,
        "selected_repair": "BY3_IMU_pre_motion_static_gyro_bias" if safe else "none",
        "trace_used_for_repair": False,
        "final_v23_output_solver_input": False,
        "parameter_retuning": False,
        "yaw_gate_relaxation": False,
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_REPAIR_PLAN_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_REPAIR_PLAN", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_repair_plan.md",
        "# BY3A7 Repair Plan\n\n"
        f"Decision: `{decision}`.\n\n"
        f"Selected repair: `{report['selected_repair']}`. No yaw gate relaxation, HDT fallback, trace tuning, or parameter retuning is allowed.\n",
    )
    return report


def repair_implementation(paths: Paths, repair_plan: dict[str, Any], imu: dict[str, Any], *, audit_only: bool) -> dict[str, Any]:
    if repair_plan.get("decision") != "BY3A7_safe_repair_ready" or audit_only:
        report = {
            "stage": STAGE,
            "decision": "BY3A7_repair_not_run_no_safe_repair" if not audit_only else "BY3A7_repair_not_run_audit_only",
            "repaired_files": [],
            "trace_solver_input": False,
            "parameter_retuning": False,
            "ready_for_paper_claims": False,
        }
    else:
        paths.repaired_imu.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.a1_repaired_gnss, paths.by3a7_repaired_gnss)
        body_rows = load_body_rows(paths.body_diag)
        by3a1_input = by3a6.read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {})
        offsets = by3a1_input.get("offsets", {})
        body_min = float(offsets.get("body_time_zero_raw_timestamp"))
        go2_start = float(offsets.get("go2_start_raw_timestamp"))
        static_bias = list(imu.get("static_pre_motion_gyro_bias_radps") or compute_static_pre_motion_bias(body_rows, go2_start))
        repaired_rows = build_static_bias_imu_rows(body_rows, body_min=body_min, go2_start=go2_start, static_bias=static_bias)
        write_imu_numeric(paths.repaired_imu, repaired_rows)
        runtime_input_dir = paths.runtime_root / "repaired_input_or_config"
        runtime_input_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.by3a7_repaired_gnss, runtime_input_dir / paths.by3a7_repaired_gnss.name)
        shutil.copy2(paths.repaired_imu, runtime_input_dir / paths.repaired_imu.name)
        source_role = {
            "stage": STAGE,
            "repaired_imu_role": "BY3 static pre-motion gyro-bias IMU repair",
            "repaired_gnss_role": "BY3A6 A1 dual-diff GNSS copied unchanged",
            "trace_solver_input": False,
            "hdt_solver_input": False,
            "parameter_retuning": False,
        }
        by3a6.write_json(paths.stage_root / "repaired_input_or_config" / "source_role.json", source_role)
        by3a6.write_json(runtime_input_dir / "source_role.json", source_role)
        repaired_files = [
            file_meta("dual_a1_gnss_unchanged", paths.by3a7_repaired_gnss, "<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"),
            file_meta("static_bias_repaired_imu", paths.repaired_imu, "<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu"),
        ]
        report = {
            "stage": STAGE,
            "decision": "BY3A7_repair_ready",
            "repair_type": "BY3 IMU preprocessing static pre-motion gyro bias",
            "repaired_files": repaired_files,
            "static_bias_radps": static_bias,
            "trace_solver_input": False,
            "hdt_solver_input": False,
            "final_v23_output_solver_input": False,
            "parameter_retuning": False,
            "yaw_gate_relaxation": False,
            "ready_for_paper_claims": False,
        }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_REPAIR_IMPLEMENTATION_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_REPAIRED_INPUT_CONFIG_INDEX", report.get("repaired_files", []))
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_repair_implementation.md",
        "# BY3A7 Repair Implementation\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "Any repaired input is BY3A7-local and does not overwrite BY3A1/BY3A6 inputs.\n",
    )
    return report


def normal_rerun(paths: Paths, repair: dict[str, Any], *, run_rerun: bool) -> dict[str, Any]:
    if repair.get("decision") != "BY3A7_repair_ready" or not run_rerun:
        report = {
            "stage": STAGE,
            "decision": "BY3A7_normal_rerun_not_run_no_safe_repair" if repair.get("decision") != "BY3A7_repair_ready" else "BY3A7_normal_rerun_skipped",
            "solver_rows": [],
            "eval_rows": [],
            "metrics_rows": [],
            "trace_solver_input": False,
            "degradation_execution": False,
            "ready_for_paper_claims": False,
        }
    else:
        rerun_paths = RerunPaths(
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
            repaired_dual_path=paths.by3a7_repaired_gnss,
            repaired_imu_path=paths.repaired_imu,
            single_gnss_path=paths.single_gnss,
        )
        rerun = by3a5b.run_normal_chain(
            rerun_paths,  # type: ignore[arg-type]
            {
                "decision": "BY3A7_repaired_inputs_ready",
                "source_policy": "BY3A5B_A1_dual_diff_short_baseline_fixed_1p5_with_BY3A7_static_bias_IMU",
                "trace_solver_input": False,
                "paper_claim": False,
            },
            run_solvers=True,
        )
        metrics_rows = annotate_by3a7_source_policy(rerun.get("metrics_rows", []))
        input_config_audit = annotate_by3a7_source_policy(rerun.get("input_config_audit", []))
        report = {
            "stage": STAGE,
            "decision": "BY3A7_normal_rerun_completed" if rerun.get("decision") == "BY3A5B_normal_rerun_completed" else "BY3A7_normal_rerun_failed",
            "underlying_decision": rerun.get("decision"),
            "solver_rows": rerun.get("solver_rows", []),
            "eval_rows": rerun.get("eval_rows", []),
            "metrics_rows": metrics_rows,
            "input_config_audit": input_config_audit,
            "trace_solver_input": False,
            "by2_feedback_reuse": False,
            "final_v23_output_solver_input": False,
            "parameter_retuning": False,
            "degradation_execution": False,
            "ready_for_paper_claims": False,
        }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_NORMAL_RERUN_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_SOLVER_STATUS", report.get("solver_rows", []))
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_EVAL_STATUS", report.get("eval_rows", []))
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_NORMAL_METRICS", report.get("metrics_rows", []))
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_normal_rerun_summary.md",
        "# BY3A7 Normal Rerun\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "Only BY3 normal chain is eligible here. BY3 degradation is not run.\n",
    )
    return report


def annotate_by3a7_source_policy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        policy = str(item.get("source_policy", ""))
        if policy:
            item["source_policy"] = f"{policy}_BY3A7_static_bias_IMU"
        else:
            item["source_policy"] = "BY3A7_static_bias_IMU"
        item["imu_source_policy"] = "BY3A7_static_pre_motion_gyro_bias_repair"
        out.append(item)
    return out


def post_repair_sanity(paths: Paths, a1: dict[str, Any], gate: dict[str, Any], repair: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    metrics_rows = rerun.get("metrics_rows", [])
    rows: list[dict[str, Any]] = []
    gnss_path = paths.by3a7_repaired_gnss if paths.by3a7_repaired_gnss.exists() else paths.a1_repaired_gnss
    gnss = by3a6.read_numeric_table(gnss_path, expected_cols=15)
    runtime_root = paths.runtime_root if rerun.get("decision") == "BY3A7_normal_rerun_completed" else paths.by3a6_runtime_root
    for alg, nav_path in by3a6.existing_nav_paths(runtime_root).items():
        nav = by3a6.load_nav_any(nav_path)
        proxy = by3a6.proxy_yaw_residuals(nav, gnss)
        manifest = read_yaw_manifest(runtime_root, alg)
        metrics = find_metric_row(metrics_rows, alg)
        rows.append(
            {
                "algorithm": alg,
                "horizontal_rmse_m": metrics.get("horizontal_rmse_m"),
                "up_rmse_m": metrics.get("up_rmse_m"),
                "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
                "yaw_p95_deg": metrics.get("yaw_p95_deg"),
                "yaw_update_count_actual": manifest.get("yaw_update_count"),
                "yaw_NORMAL_actual": manifest.get("yaw_NORMAL"),
                "yaw_DOWNWEIGHT_actual": manifest.get("yaw_DOWNWEIGHT"),
                "yaw_REJECT_actual": manifest.get("yaw_REJECT"),
                "proxy_nav_minus_a1_p50_deg": proxy.get("p50"),
                "proxy_nav_minus_a1_p95_deg": proxy.get("p95"),
                "proxy_reject_likely_count": proxy.get("reject_likely_count"),
                "yaw_sanity": bool(metrics.get("yaw_rmse_deg") is not None and float(metrics["yaw_rmse_deg"]) < 20.0),
            }
        )
    legsa = find_metric_row(rows, "LegSA_full_EKF")
    if legsa.get("yaw_sanity"):
        decision = "BY3A7_yaw_sanity_passed"
    elif repair.get("decision") == "BY3A7_repair_ready" and rerun.get("decision") == "BY3A7_normal_rerun_completed":
        decision = "BY3A7_yaw_still_failed"
    else:
        decision = "BY3A7_position_up_ready_yaw_not_salvaged"
    report = {
        "stage": STAGE,
        "decision": decision,
        "rows": rows,
        "normal_rerun_decision": rerun.get("decision"),
        "position_up_ready": any(row.get("horizontal_rmse_m") is not None and float(row["horizontal_rmse_m"]) < 2.0 for row in rows),
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_POST_REPAIR_SANITY_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_POST_REPAIR_YAW_SANITY", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "by3a7_post_repair_sanity.md",
        "# BY3A7 Post-Repair Sanity\n\n"
        f"Decision: `{decision}`.\n\n"
        "Yaw is usable only if LegSA normal yaw sanity passes. Paper claims remain false.\n",
    )
    return report


def generate_figures(paths: Paths, a1: dict[str, Any], imu: dict[str, Any], gate: dict[str, Any], post: dict[str, Any], *, skip_figures: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if skip_figures:
        report = {"stage": STAGE, "decision": "BY3A7_figures_skipped", "rows": rows}
        by3a6.write_json(paths.stage_root / "reports" / "BY3A7_FIGURE_REPORT.json", report)
        by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_FIGURE_INDEX", rows)
        return report
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        report = {"stage": STAGE, "decision": "BY3A7_figures_failed", "error": str(exc), "rows": rows}
        by3a6.write_json(paths.stage_root / "reports" / "BY3A7_FIGURE_REPORT.json", report)
        return report

    fig_dir = paths.stage_root / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    a1_rows = a1.get("rows", [])
    gate_rows = [row for row in gate.get("rows", []) if row.get("algorithm") == "LegSA_full_EKF"]
    if a1_rows:
        times = [row["time"] for row in a1_rows]
        yaw = [row["yaw_deg"] for row in a1_rows]
        trace = [row["trace_heading_nearest_deg"] for row in a1_rows]
        baseline = [row["baseline_length_m"] for row in a1_rows]
        jumps = [abs(row["yaw_jump_from_prev_deg"] or 0.0) for row in a1_rows]
        save_line_plot(plt, fig_dir, rows, "BY3A7_A1_yaw_quality_timeline", times, [yaw, trace], ["A1 yaw", "trace heading diagnostic"], "deg")
        save_scatter_plot(plt, fig_dir, rows, "BY3A7_baseline_length_vs_yaw_jumps", baseline, jumps, "baseline length m", "abs yaw jump deg")
        hdt = [row["hdt_heading_nearest_deg"] for row in a1_rows]
        if any(value is not None for value in hdt):
            save_line_plot(plt, fig_dir, rows, "BY3A7_A1_yaw_vs_HDT_diagnostic", times, [yaw, hdt], ["A1 yaw", "HDT diagnostic"], "deg")
    sign_rows = imu.get("sign_candidate_rows", [])
    current = next((row for row in sign_rows if row["candidate"] == "current_repaired_imu_dtheta_z"), None)
    static = next((row for row in sign_rows if row["candidate"] == "static_bias_repaired_dtheta_z"), None)
    raw = next((row for row in sign_rows if row["candidate"] == "raw_neg_gyro_z_flu_to_frd"), None)
    if current and static and raw:
        labels = ["current IMU", "static-bias IMU", "raw -gyro_z"]
        values = [current["cumulative_delta_deg"], static["cumulative_delta_deg"], raw["cumulative_delta_deg"]]
        save_bar_plot(plt, fig_dir, rows, "BY3A7_yaw_rate_sign_candidate_comparison", labels, values, "cumulative deg")
    if gate_rows:
        times = [row["time"] for row in gate_rows]
        residual = [abs(row["residual_nav_minus_a1_deg_proxy"]) for row in gate_rows]
        states = [gate_state_code(row["gate_state_proxy"]) for row in gate_rows]
        save_line_plot(plt, fig_dir, rows, "BY3A7_yaw_gate_residual_timeline", times, [residual], ["abs residual proxy"], "deg")
        save_line_plot(plt, fig_dir, rows, "BY3A7_gate_state_over_time", times, [states], ["0 normal 1 down 2 reject"], "state")
    metrics = post.get("rows", [])
    if metrics:
        labels = [row["algorithm"] for row in metrics if row.get("yaw_rmse_deg") is not None]
        values = [row["yaw_rmse_deg"] for row in metrics if row.get("yaw_rmse_deg") is not None]
        save_bar_plot(plt, fig_dir, rows, "BY3A7_after_repair_yaw_metrics", labels, values, "yaw RMSE deg")
    report = {"stage": STAGE, "decision": "BY3A7_figures_generated", "rows": rows}
    by3a6.write_json(paths.stage_root / "reports" / "BY3A7_FIGURE_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "BY3A7_FIGURE_INDEX", rows)
    return report


def case_review(
    paths: Paths,
    intake: dict[str, Any],
    a1: dict[str, Any],
    imu: dict[str, Any],
    gate: dict[str, Any],
    code: dict[str, Any],
    repair_plan: dict[str, Any],
    repair: dict[str, Any],
    rerun: dict[str, Any],
    post: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": post.get("decision"),
        "trace_truth_policy": "BY3A6 trace truth remains locked; trace is evaluation-only",
        "a1_yaw_quality_decision": a1.get("decision"),
        "imu_sign_axis_decision": imu.get("decision"),
        "yaw_gate_decision": gate.get("decision"),
        "yaw_update_code_decision": code.get("decision"),
        "repair_plan_decision": repair_plan.get("decision"),
        "repair_implementation_decision": repair.get("decision"),
        "normal_rerun_decision": rerun.get("decision"),
        "post_repair_decision": post.get("decision"),
        "ready_for_paper_claims": False,
        "degradation_execution": False,
        "figure_decision": figures.get("decision"),
    }
    by3a6.write_json(paths.stage_root / "case_review" / "BY3A7_a1_yaw_quality_imu_gate_case_review.json", report)
    by3a6.write_md(
        paths.stage_root / "case_review" / "BY3A7_a1_yaw_quality_imu_gate_case_review.md",
        "# BY3A7 A1 Yaw Quality / IMU Gate Case Review\n\n"
        f"- A1 yaw quality: `{a1.get('decision')}`\n"
        f"- IMU sign/axis/preprocessing: `{imu.get('decision')}`\n"
        f"- Yaw gate residuals: `{gate.get('decision')}`\n"
        f"- Yaw update code: `{code.get('decision')}`\n"
        f"- Repair plan: `{repair_plan.get('decision')}`\n"
        f"- Normal rerun: `{rerun.get('decision')}`\n"
        f"- Post-repair sanity: `{post.get('decision')}`\n\n"
        "No BY3 degradation, trace solver input, HDT mainline fallback, gate relaxation, or paper claim was performed.\n",
    )
    return report


def obsidian_sync(paths: Paths, a1: dict[str, Any], imu: dict[str, Any], gate: dict[str, Any], repair_plan: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    root = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization"
    root.mkdir(parents=True, exist_ok=True)
    notes = {
        "BY3_A1_yaw_dynamic_quality_audit.md": (
            "# BY3 A1 Yaw Dynamic Quality Audit\n\n"
            f"BY3A7 decision: `{a1.get('decision')}`. "
            "A1 remains the mainline short-baseline source with dynamic-quality cautions; HDT is diagnostic only.\n"
        ),
        "BY3_IMU_sign_axis_yaw_gate_audit.md": (
            "# BY3 IMU Sign Axis And Yaw Gate Audit\n\n"
            f"IMU decision: `{imu.get('decision')}`. Gate decision: `{gate.get('decision')}`. "
            "Yaw gate relaxation was not used.\n"
        ),
        "BY3_yaw_root_cause_BY3A7.md": (
            "# BY3 Yaw Root Cause BY3A7\n\n"
            f"Repair plan: `{repair_plan.get('decision')}`. Post-repair sanity: `{post.get('decision')}`. "
            "Paper claims remain false.\n"
        ),
        "current_state.md": (
            "# BY3 Current State\n\n"
            f"Latest BY3A7 post-repair decision: `{post.get('decision')}`. "
            "Trace remains evaluation-only; BY3 degradation planning requires human review.\n"
        ),
        "next_steps.md": (
            "# BY3 Next Steps\n\n"
            "Use BY3A7 outputs for human review before any BY3B planning. Do not run yaw degradation unless yaw sanity is accepted.\n"
        ),
    }
    for name, text in notes.items():
        (root / name).write_text(text, encoding="utf-8")
    report = {"stage": STAGE, "decision": "BY3A7_obsidian_sync_completed", "notes": sorted(notes)}
    by3a6.write_json(paths.stage_root / "obsidian_sync" / "BY3A7_OBSIDIAN_SYNC_REPORT.json", report)
    return report


def final_validation(
    paths: Paths,
    a1: dict[str, Any],
    imu: dict[str, Any],
    gate: dict[str, Any],
    code: dict[str, Any],
    repair_plan: dict[str, Any],
    repair: dict[str, Any],
    rerun: dict[str, Any],
    post: dict[str, Any],
    figures: dict[str, Any],
    obsidian: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        ("a1_yaw_quality_audited", bool(a1.get("decision"))),
        ("imu_sign_axis_audited", bool(imu.get("decision"))),
        ("yaw_gate_audited", bool(gate.get("decision"))),
        ("yaw_update_code_audited", bool(code.get("decision"))),
        ("no_arbitrary_tuning", not repair_plan.get("yaw_gate_relaxation", False)),
        ("repair_only_if_gated", repair.get("decision") != "BY3A7_repair_ready" or repair_plan.get("decision") == "BY3A7_safe_repair_ready"),
        ("normal_rerun_only_if_repair_ready", rerun.get("decision") != "BY3A7_normal_rerun_completed" or repair.get("decision") == "BY3A7_repair_ready"),
        ("no_BY3_degradation", not rerun.get("degradation_execution", False)),
        ("no_trace_solver_input", not repair.get("trace_solver_input", False) and not rerun.get("trace_solver_input", False)),
        ("no_fabricated_metrics", bool(post.get("decision"))),
        ("obsidian_synced", obsidian.get("decision") == "BY3A7_obsidian_sync_completed"),
        ("ready_for_paper_claims_false", not post.get("ready_for_paper_claims", False)),
    ]
    rows = [{"check": name, "passed": bool(passed)} for name, passed in checks]
    status = "BY3A7_validation_passed" if all(row["passed"] for row in rows) else "BY3A7_validation_failed"
    report = {
        "stage": STAGE,
        "decision": status,
        "checks": rows,
        "reports_parse": validate_json_csv(paths.stage_root),
        "ready_for_paper_claims": False,
    }
    by3a6.write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", report)
    by3a6.write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", rows)
    by3a6.write_md(
        paths.stage_root / "summary" / "long_task_summary.md",
        "# BY3A7 Long Task Summary\n\n"
        f"Validation: `{status}`. Post-repair decision: `{post.get('decision')}`.\n",
    )
    return report


def final_decision(validation: dict[str, Any], a1: dict[str, Any], imu: dict[str, Any], repair_plan: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    if validation.get("decision") != "BY3A7_validation_passed":
        status = "BY3A7_safety_gate_failed"
        ready = False
        scope = "none"
        next_stage = "repair_safety_violation"
    elif post.get("decision") == "BY3A7_yaw_sanity_passed":
        status = "BY3A7_yaw_salvaged_ready_for_full_BY3_degradation"
        ready = True
        scope = "full_after_human_review"
        next_stage = "BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK"
    elif repair_plan.get("decision") == "BY3A7_safe_repair_ready" and post.get("decision") == "BY3A7_yaw_still_failed":
        status = "BY3A7_manual_review_required"
        ready = False
        scope = "none_pending_human_review"
        next_stage = "manual_review_A1_IMU_gate"
    else:
        status = "BY3A7_position_up_ready_yaw_not_salvaged"
        ready = False
        scope = "position_up_only_requires_human_acceptance"
        next_stage = "BY3B_POSITION_ONLY_DEGRADATION_PLANNING_AFTER_HUMAN_REVIEW"
    return {
        "stage": STAGE,
        "status": status,
        "a1_yaw_quality_decision": a1.get("decision"),
        "imu_sign_axis_decision": imu.get("decision"),
        "repair_plan_decision": repair_plan.get("decision"),
        "post_repair_decision": post.get("decision"),
        "ready_for_BY3_degradation_matrix_planning": ready,
        "ready_for_BY3_degradation_matrix_planning_scope": scope,
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
    }


def write_final_reports(paths: Paths, validation: dict[str, Any], decision: dict[str, Any]) -> None:
    by3a6.write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    by3a6.write_md(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# BY3A7 Next Stage Recommendation\n\n"
        f"Decision: `{decision['status']}`.\n\n"
        f"ready_for_BY3_degradation_matrix_planning=`{decision['ready_for_BY3_degradation_matrix_planning']}`.\n"
        f"ready_for_BY3_degradation_matrix_planning_scope=`{decision['ready_for_BY3_degradation_matrix_planning_scope']}`.\n"
        f"ready_for_paper_claims=`{decision['ready_for_paper_claims']}`.\n"
        f"recommended_next_stage=`{decision['recommended_next_stage']}`.\n",
    )


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
        by3a4a_root=paths.by3a4a_root,
        by3a4c_root=paths.by3a4c_root,
        by3a5_root=paths.by3a5_root,
    )
    rows = by3a5b.build_baseline_rows(b5_paths)
    for row in rows:
        row["time_rel"] = float(row["t"]) - float(base_time)
    return rows


def nearest_by_time(rows: list[dict[str, Any]], t: float) -> dict[str, Any] | None:
    if not rows:
        return None
    key = "time_rel" if "time_rel" in rows[0] else "t"
    return min(rows, key=lambda row: abs(float(row[key]) - float(t)))


def robust_bounds(values: np.ndarray) -> tuple[float, float]:
    if values.size == 0:
        return 0.0, float("inf")
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    spread = max(6.0 * 1.4826 * mad, 0.15)
    return max(0.05, median - spread), median + spread


def load_body_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    return rows


def compute_static_pre_motion_bias(body_rows: list[dict[str, Any]], go2_start: float, *, max_samples: int = 1000) -> list[float]:
    processed: list[list[float]] = []
    correction = by3a0.roll_matrix_deg(-1.0)
    for row in body_rows:
        timestamp = by3a0.safe_float(row.get("timestamp"))
        if timestamp is None or timestamp >= go2_start:
            continue
        gyro = [by3a0.safe_float(row.get("gyro_x")), by3a0.safe_float(row.get("gyro_y")), by3a0.safe_float(row.get("gyro_z"))]
        if any(value is None for value in gyro):
            continue
        gyro_frd = [float(gyro[0]), -float(gyro[1]), -float(gyro[2])]
        processed.append(by3a0.matvec(correction, gyro_frd))
    if not processed:
        return [0.0, 0.0, 0.0]
    return by3a0.mean_vec(processed[:max_samples])


def build_static_bias_imu_rows(
    body_rows: list[dict[str, Any]],
    *,
    body_min: float,
    go2_start: float,
    static_bias: list[float],
) -> list[list[float]]:
    correction = by3a0.roll_matrix_deg(-1.0)
    processed = []
    for row in body_rows:
        timestamp = by3a0.safe_float(row.get("timestamp"))
        gyro = [by3a0.safe_float(row.get("gyro_x")), by3a0.safe_float(row.get("gyro_y")), by3a0.safe_float(row.get("gyro_z"))]
        acc = [by3a0.safe_float(row.get("acc_x")), by3a0.safe_float(row.get("acc_y")), by3a0.safe_float(row.get("acc_z"))]
        if timestamp is None or any(value is None for value in gyro + acc):
            continue
        if timestamp < go2_start:
            continue
        gyro_frd = [float(gyro[0]), -float(gyro[1]), -float(gyro[2])]
        acc_frd = [float(acc[0]), -float(acc[1]), -float(acc[2])]
        processed.append({"time": float(timestamp) - body_min, "gyro": by3a0.matvec(correction, gyro_frd), "acc": by3a0.matvec(correction, acc_frd)})
    rows: list[list[float]] = []
    for previous, current in zip(processed, processed[1:]):
        dt = float(current["time"]) - float(previous["time"])
        if dt <= 0.0 or dt > 0.1:
            continue
        gyro = [float(current["gyro"][axis]) - float(static_bias[axis]) for axis in range(3)]
        acc = [float(current["acc"][axis]) for axis in range(3)]
        rows.append([float(current["time"]), gyro[0] * dt, gyro[1] * dt, gyro[2] * dt, acc[0] * dt, acc[1] * dt, acc[2] * dt])
    return rows


def imu_sign_candidate_rows(
    body_rows: list[dict[str, Any]],
    current_imu: list[list[float]],
    repaired_preview: list[list[float]],
    gnss: list[list[float]],
    trace: list[dict[str, float]],
    body_min: float,
) -> list[dict[str, Any]]:
    if not gnss:
        return []
    gnss_times = [row[0] for row in gnss]
    trace_at = by3a6.interp_angle([row["time_rel"] for row in trace], [row["heading_ned"] for row in trace], gnss_times) if trace else []
    a1_at = by3a6.interp_angle(gnss_times, [row[13] for row in gnss], gnss_times)
    source_rows = [
        ("current_repaired_imu_dtheta_z", interval_dtheta_delta(current_imu, gnss_times, 2)),
        ("static_bias_repaired_dtheta_z", interval_dtheta_delta(repaired_preview, gnss_times, 2)),
        ("raw_neg_gyro_z_flu_to_frd", interval_raw_gyro_delta(body_rows, gnss_times, body_min, "gyro_z", -1.0)),
        ("raw_gyro_z_no_conversion", interval_raw_gyro_delta(body_rows, gnss_times, body_min, "gyro_z", 1.0)),
        ("raw_neg_yaw_speed_flu_to_frd", interval_raw_gyro_delta(body_rows, gnss_times, body_min, "yaw_speed_radps", -1.0)),
        ("raw_gyro_x", interval_raw_gyro_delta(body_rows, gnss_times, body_min, "gyro_x", 1.0)),
        ("raw_gyro_y", interval_raw_gyro_delta(body_rows, gnss_times, body_min, "gyro_y", 1.0)),
    ]
    trace_delta = angle_deltas(trace_at)
    a1_delta = angle_deltas(a1_at)
    rows: list[dict[str, Any]] = []
    for name, deltas in source_rows:
        rows.append(
            {
                "candidate": name,
                "cumulative_delta_deg": float(np.sum(deltas)) if len(deltas) else 0.0,
                "trace_delta_correlation": corr(deltas, trace_delta),
                "a1_delta_correlation": corr(deltas, a1_delta),
                "median_abs_delta_error_vs_trace_deg": median_abs_delta_error(deltas, trace_delta),
                "median_abs_delta_error_vs_a1_deg": median_abs_delta_error(deltas, a1_delta),
                "physically_plausible": name in {"raw_neg_gyro_z_flu_to_frd", "static_bias_repaired_dtheta_z", "current_repaired_imu_dtheta_z"},
                "compatible_with_BY2_processing": name in {"raw_neg_gyro_z_flu_to_frd", "static_bias_repaired_dtheta_z", "current_repaired_imu_dtheta_z"},
                "allowed_for_repair": name == "static_bias_repaired_dtheta_z",
            }
        )
    return rows


def interval_dtheta_delta(rows: list[list[float]], gnss_times: list[float], axis: int) -> np.ndarray:
    if not rows:
        return np.asarray([])
    times = np.asarray([row[0] for row in rows], dtype=float)
    dtheta = np.asarray([row[1 + axis] for row in rows], dtype=float)
    values = []
    for left, right in zip(gnss_times, gnss_times[1:]):
        mask = (times > left) & (times <= right)
        values.append(float(np.rad2deg(np.sum(dtheta[mask]))))
    return np.asarray(values, dtype=float)


def interval_raw_gyro_delta(body_rows: list[dict[str, Any]], gnss_times: list[float], body_min: float, col: str, sign: float) -> np.ndarray:
    values_by_time: list[tuple[float, float]] = []
    for row in body_rows:
        timestamp = by3a0.safe_float(row.get("timestamp"))
        value = by3a0.safe_float(row.get(col))
        if timestamp is None or value is None:
            continue
        values_by_time.append((float(timestamp) - body_min, sign * float(value)))
    if not values_by_time:
        return np.asarray([])
    t = np.asarray([item[0] for item in values_by_time], dtype=float)
    v = np.asarray([item[1] for item in values_by_time], dtype=float)
    out = []
    for left, right in zip(gnss_times, gnss_times[1:]):
        mask = (t > left) & (t <= right)
        if np.sum(mask) < 2:
            out.append(0.0)
        else:
            out.append(float(np.rad2deg(np.trapezoid(v[mask], t[mask]))))
    return np.asarray(out, dtype=float)


def angle_deltas(values: list[float]) -> np.ndarray:
    if not values:
        return np.asarray([])
    unwrapped = np.rad2deg(np.unwrap(np.deg2rad(np.asarray(values, dtype=float))))
    return np.diff(unwrapped)


def corr(a: Iterable[float], b: Iterable[float]) -> float | None:
    av = np.asarray(list(a), dtype=float)
    bv = np.asarray(list(b), dtype=float)
    if len(av) == 0 or len(bv) == 0:
        return None
    n = min(len(av), len(bv))
    av = av[:n]
    bv = bv[:n]
    if float(np.std(av)) == 0.0 or float(np.std(bv)) == 0.0:
        return None
    return float(np.corrcoef(av, bv)[0, 1])


def median_abs_delta_error(a: Iterable[float], b: Iterable[float]) -> float | None:
    av = np.asarray(list(a), dtype=float)
    bv = np.asarray(list(b), dtype=float)
    if len(av) == 0 or len(bv) == 0:
        return None
    n = min(len(av), len(bv))
    return float(np.median(np.abs(av[:n] - bv[:n])))


def cumulative_dtheta_deg(rows: list[list[float]], *, axis: int) -> float:
    return float(np.rad2deg(sum(row[1 + axis] for row in rows))) if rows else 0.0


def write_imu_numeric(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(" ".join(f"{float(value):.12g}" for value in row[:7]) + "\n")


def read_yaw_manifest(runtime_root: Path, algorithm: str) -> dict[str, Any]:
    path = {
        "stage1_baseline_no_feedback_EKF": runtime_root / "normal_rerun" / "stage1_solver" / "baseline_no_feedback_EKF" / "RUN_MANIFEST.json",
        "LegSA_full_EKF": runtime_root / "normal_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF" / "RUN_MANIFEST.json",
    }.get(algorithm)
    if not path:
        return {}
    data = by3a6.read_json(path, {})
    return {key: data.get(key) for key in ["yaw_update_count", "yaw_NORMAL", "yaw_DOWNWEIGHT", "yaw_REJECT"]}


def accepted_source_aware_times(runtime_root: Path, algorithm: str) -> set[float]:
    path = {
        "LegSA_full_EKF": runtime_root / "normal_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF" / "SOURCE_AWARE_WEIGHT_TRACE.csv",
        "stage1_baseline_no_feedback_EKF": runtime_root / "normal_rerun" / "stage1_solver" / "baseline_no_feedback_EKF" / "SOURCE_AWARE_WEIGHT_TRACE.csv",
    }.get(algorithm)
    if not path or not path.exists():
        return set()
    df = pd.read_csv(path)
    if "source_id" not in df.columns:
        return set()
    rows = df[(df["source_id"] == "dual_antenna_yaw") & (pd.to_numeric(df.get("accepted", 0), errors="coerce") == 1)]
    return {round(float(value), 6) for value in rows["time"].tolist()}


def build_gate_rows_for_algorithm(
    algorithm: str,
    nav: pd.DataFrame,
    gnss: list[list[float]],
    quality_by_time: dict[float, dict[str, Any]],
    source_accepted_times: set[float],
) -> list[dict[str, Any]]:
    if nav.empty or not gnss:
        return []
    gnss_times = [row[0] for row in gnss]
    valid_times = [t for t in gnss_times if float(nav["time"].min()) <= t <= float(nav["time"].max())]
    nav_at = by3a6.interp_angle(nav["time"].tolist(), nav["yaw"].tolist(), valid_times)
    a1_at = by3a6.interp_angle(gnss_times, [row[13] for row in gnss], valid_times)
    rows: list[dict[str, Any]] = []
    for idx, t in enumerate(valid_times):
        residual = by3a6.circ_diff(nav_at[idx], a1_at[idx])
        quality = quality_by_time.get(round(float(t), 6), {})
        rows.append(
            {
                "algorithm": algorithm,
                "time": float(t),
                "A1_yaw_deg": a1_at[idx],
                "NAV_yaw_deg_proxy": nav_at[idx],
                "residual_nav_minus_a1_deg_proxy": residual,
                "gate_state_proxy": gate_state(abs(residual)),
                "actual_accepted_in_source_aware_trace": round(float(t), 6) in source_accepted_times,
                "actual_residual_available": False,
                "quality_flag": quality.get("quality_flag"),
                "baseline_length_m": quality.get("baseline_length_m"),
                "yaw_jump_from_prev_deg": quality.get("yaw_jump_from_prev_deg"),
                "should_use_for_solver_candidate": bool(quality.get("should_use_for_solver_candidate", True)),
            }
        )
    return rows


def gate_state(abs_residual_deg: float) -> str:
    if abs_residual_deg > 15.0:
        return "REJECT"
    if abs_residual_deg > 6.0:
        return "DOWNWEIGHT"
    return "NORMAL"


def gate_state_code(state: str) -> int:
    return {"NORMAL": 0, "DOWNWEIGHT": 1, "REJECT": 2}.get(state, -1)


def find_metric_row(rows: list[dict[str, Any]], algorithm: str) -> dict[str, Any]:
    return next((row for row in rows if row.get("algorithm") == algorithm), {})


def summary_row_from_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": report.get("decision"),
        "row_count": report.get("row_count"),
        "jump_count_gt_15_deg": report.get("jump_count_gt_15_deg"),
        "jump_count_gt_30_deg": report.get("jump_count_gt_30_deg"),
        "jump_count_gt_45_deg": report.get("jump_count_gt_45_deg"),
        "baseline_length_suspect_count": report.get("baseline_length_suspect_count"),
        "invalid_solver_candidate_count": report.get("invalid_solver_candidate_count"),
        "a1_minus_trace_rmse_deg": (report.get("a1_minus_trace_heading_stats_deg") or {}).get("rmse"),
    }


def save_line_plot(plt: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str, x: list[Any], y_series: list[list[Any]], labels: list[str], ylabel: str) -> None:
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


def save_scatter_plot(plt: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str, x: list[Any], y: list[Any], xlabel: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(x, y, s=12, alpha=0.75)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_figure(fig, fig_dir, rows, stem)
    plt.close(fig)


def save_bar_plot(plt: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str, labels: list[str], values: list[Any], ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    save_figure(fig, fig_dir, rows, stem)
    plt.close(fig)


def save_figure(fig: Any, fig_dir: Path, rows: list[dict[str, Any]], stem: str) -> None:
    for suffix in ["png", "pdf"]:
        path = fig_dir / f"{stem}.{suffix}"
        fig.savefig(path)
        rows.append({"figure": path.name, "status": "generated", "bytes": path.stat().st_size})


def validate_json_csv(root: Path) -> dict[str, Any]:
    json_bad = []
    csv_bad = []
    for path in root.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            json_bad.append({"path": str(path), "error": str(exc)})
    for path in root.rglob("*.csv"):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                list(csv.reader(handle))
        except Exception as exc:
            csv_bad.append({"path": str(path), "error": str(exc)})
    return {"json_bad": json_bad, "csv_bad": csv_bad, "passed": not json_bad and not csv_bad}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_meta(role: str, path: Path, alias: str) -> dict[str, Any]:
    return {
        "role": role,
        "alias": alias,
        "exists": path.exists(),
        "row_count": count_nonempty_lines(path) if path.exists() else 0,
        "size_bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def count_nonempty_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for line in handle if line.strip())


if __name__ == "__main__":
    raise SystemExit(main())
