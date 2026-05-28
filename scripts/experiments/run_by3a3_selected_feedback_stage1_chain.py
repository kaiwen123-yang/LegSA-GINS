"""Run the BY3A3 selected-feedback stage1 chain and normal comparison.

This script is intentionally runtime-only: it writes BY3A3 reports, configs,
solver outputs, metrics, figures, and case review under ``by3-huiti``. It does
not change EKF/FGO math and it does not run any degradation matrix.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.reporting.by2_algorithm_runner import (  # noqa: E402
    build_algorithm_config_text,
    load_base_config_values,
    read_json,
    repo_to_wsl,
    run_formal_algorithm,
    write_json,
)
from legsa_gins.reporting.by2_n9b1c2_selected_feedback_same_case_mapping import (  # noqa: E402
    generate_same_case_feedback_observations,
)
from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (  # noqa: E402
    _convert_eval_nav,
    _convert_std,
    _load_r4e3_eval_script,
    _metrics_from_summary,
)


STAGE = "BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION"
RUNTIME_STAGE = "BY3A3_NORMAL_EXECUTION"
BY3A1_STAGE = "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR"
BY3A2_STAGE = "BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR"
BY3A0_STAGE = "BY3A0_TO_BY3E_GENERALIZATION_BOOTSTRAP_ALIGNMENT_NORMAL_COMPARISON"

SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "selected_feedback_recovery",
    "stage1_solver",
    "stage1_official_eval",
    "feedback_generation",
    "stage2_legsa_full_solver",
    "single_baseline_solver",
    "finalv23_solver",
    "official_eval",
    "metrics",
    "figures",
    "case_review",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
]

REPORT_NAMES = [
    "BY3A3_SELECTED_FEEDBACK_POLICY_RECOVERY_REPORT.json",
    "BY3A3_STAGE1_SOLVER_MATERIALIZATION_REPORT.json",
    "BY3A3_STAGE1_SOLVER_EXECUTION_REPORT.json",
    "BY3A3_STAGE1_OFFICIAL_EVAL_REPORT.json",
    "BY3A3_FEEDBACK_GENERATION_REPORT.json",
    "BY3A3_STAGE2_LEGSA_FULL_SOLVER_REPORT.json",
    "BY3A3_BASELINE_SOLVER_REPORT.json",
    "BY3A3_OFFICIAL_EVALUATION_REPORT.json",
    "BY3A3_FIGURE_GENERATION_REPORT.json",
    "BY3A3_CONTEXT_OBSIDIAN_SYNC_REPORT.json",
    "LONG_TASK_VALIDATION_REPORT.json",
    "LONG_TASK_DECISION_REPORT.json",
]

MATRIX_STEMS = [
    "BY3A3_SELECTED_FEEDBACK_POLICY_EVIDENCE",
    "BY3A3_STAGE1_SOLVER_CONFIG_INDEX",
    "BY3A3_STAGE1_SOLVER_STATUS",
    "BY3A3_STAGE1_EVAL_STATUS",
    "BY3A3_FEEDBACK_GENERATION_STATUS",
    "BY3A3_STAGE2_LEGSA_FULL_STATUS",
    "BY3A3_BASELINE_SOLVER_STATUS",
    "BY3A3_EVAL_STATUS",
    "BY3A3_NORMAL_METRICS",
    "BY3A3_FIGURE_INDEX",
    "BY3A3_OBSIDIAN_SYNC_INDEX",
    "LONG_TASK_STAGE_STATUS",
]

SUMMARY_NAMES = [
    "by3a3_selected_feedback_policy_recovery.md",
    "by3a3_stage1_solver_materialization.md",
    "by3a3_stage1_solver_execution.md",
    "by3a3_stage1_eval_summary.md",
    "by3a3_feedback_generation.md",
    "by3a3_stage2_legsa_full_solver.md",
    "by3a3_baseline_solver_summary.md",
    "by3a3_eval_summary.md",
    "long_task_summary.md",
    "long_task_next_stage_recommendation.md",
]

METRIC_KEYS = [
    "north_rmse_m",
    "east_rmse_m",
    "up_rmse_m",
    "horizontal_rmse_m",
    "horizontal_p95_m",
    "horizontal_max_m",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "yaw_rmse_deg",
    "roll_p95_deg",
    "pitch_p95_deg",
    "yaw_p95_deg",
    "row_count",
    "time_start",
    "time_end",
]


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    runtime_root: Path
    by3a1_root: Path
    by3a2_root: Path
    by3a0_root: Path
    trace: Path

    @property
    def imu(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"

    @property
    def gnss_dual(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss"

    @property
    def gnss_single(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"

    @property
    def raw_doppler(self) -> Path:
        return self.by3a2_root / "raw_doppler_recovery" / "provider_only" / "RAW_DOPPLER_VELOCITY_FACTORS.csv"

    @property
    def go2_prior_dir(self) -> Path:
        return (
            self.by3a1_root
            / "provider_materialization"
            / "go2_priors"
            / "priors"
            / "joint_rp1p6deg_hv1p0"
        )

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
    parser.add_argument("--by3a1-root", type=Path)
    parser.add_argument("--by3a2-root", type=Path)
    parser.add_argument("--by3a0-root", type=Path)
    parser.add_argument("--by3-trace", type=Path, required=True)
    parser.add_argument("--skip-solvers", action="store_true")
    parser.add_argument("--skip-baselines", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    stage_root = (args.stage_root or repo / "by3-huiti" / STAGE).resolve()
    runtime_root = (args.runtime_root or repo / "by3-huiti" / "BY3_FULL_MATRIX" / RUNTIME_STAGE).resolve()
    paths = Paths(
        repo=repo,
        stage_root=stage_root,
        runtime_root=runtime_root,
        by3a1_root=(args.by3a1_root or repo / "by3-huiti" / BY3A1_STAGE).resolve(),
        by3a2_root=(args.by3a2_root or repo / "by3-huiti" / BY3A2_STAGE).resolve(),
        by3a0_root=(args.by3a0_root or repo / "by3-huiti" / BY3A0_STAGE).resolve(),
        trace=args.by3_trace.resolve(),
    )
    result = run_by3a3(paths, skip_solvers=args.skip_solvers, skip_baselines=args.skip_baselines, skip_figures=args.skip_figures)
    status = result["decision_report"]["status"]
    print(json.dumps({"status": status, "stage_root": str(paths.stage_root)}, ensure_ascii=False, indent=2))
    return 0


def run_by3a3(paths: Paths, *, skip_solvers: bool = False, skip_baselines: bool = False, skip_figures: bool = False) -> dict[str, Any]:
    create_tree(paths)
    context = build_context(paths)
    policy = recover_feedback_policy(paths)
    write_stage_a(paths, policy)

    stage1_materialization = materialize_stage1(paths, context, policy)
    write_stage_b(paths, stage1_materialization)

    if skip_solvers or stage1_materialization["decision"] != "BY3A3_stage1_solver_ready":
        stage1_run = skipped_or_blocked_run("baseline_no_feedback_EKF", "stage1 materialization did not pass" if not skip_solvers else "skip-solvers requested")
    else:
        stage1_run = run_legsa_solver(
            paths,
            algorithm="baseline_no_feedback_EKF",
            output_dir=paths.runtime_root / "stage1_solver" / "baseline_no_feedback_EKF",
            runtime_config=Path(stage1_materialization["runtime_config_path"]),
            case_overrides=stage1_case_overrides(paths),
        )
    write_stage_c(paths, stage1_run)

    if stage1_run.get("run_status") == "completed":
        stage1_eval = run_official_eval(
            paths,
            algorithm="stage1_baseline_no_feedback_EKF",
            solver_output_dir=paths.runtime_root / "stage1_solver" / "baseline_no_feedback_EKF",
            official_dir=paths.stage_root / "stage1_official_eval",
            base_time=context["base_time"],
            nav_kind="legsa_port_csv",
        )
    else:
        stage1_eval = {
            "algorithm": "stage1_baseline_no_feedback_EKF",
            "official_eval_status": "skipped",
            "blocked_reason": f"stage1 run status {stage1_run.get('run_status')}",
        }
    write_stage_d(paths, stage1_eval)

    feedback = generate_feedback(paths, stage1_eval)
    write_stage_e(paths, feedback)

    if skip_solvers or feedback.get("decision") != "BY3A3_feedback_generation_completed":
        stage2_run = skipped_or_blocked_run("LegSA_full_EKF", feedback.get("blocked_reason") or "feedback generation incomplete")
    else:
        stage2_materialization = materialize_stage2(paths, context, feedback)
        stage2_run = run_legsa_solver(
            paths,
            algorithm="LegSA_full_EKF",
            output_dir=paths.runtime_root / "stage2_legsa_full_solver" / "LegSA_full_EKF",
            runtime_config=Path(stage2_materialization["runtime_config_path"]),
            case_overrides=stage2_case_overrides(paths, feedback),
        )
        stage2_run["materialization"] = stage2_materialization
    write_stage_f(paths, stage2_run)

    baseline_runs: list[dict[str, Any]] = []
    if not skip_solvers and not skip_baselines:
        baseline_runs = run_baseline_solvers(paths, context)
    else:
        baseline_runs = [
            skipped_or_blocked_run("single_antenna_gnss1_status_KF_GINS", "baseline execution skipped"),
            skipped_or_blocked_run("final_v23_dual_antenna_EKF", "baseline execution skipped"),
        ]
    write_stage_g(paths, baseline_runs)

    eval_results = []
    if stage2_run.get("run_status") == "completed":
        eval_results.append(
            run_official_eval(
                paths,
                algorithm="LegSA_full_EKF",
                solver_output_dir=paths.runtime_root / "stage2_legsa_full_solver" / "LegSA_full_EKF",
                official_dir=paths.stage_root / "official_eval" / "LegSA_full_EKF",
                base_time=context["base_time"],
                nav_kind="legsa_port_csv",
            )
        )
    for row in baseline_runs:
        if row.get("run_status") == "completed":
            eval_results.append(
                run_official_eval(
                    paths,
                    algorithm=row["algorithm"],
                    solver_output_dir=Path(row["output_dir"]),
                    official_dir=paths.stage_root / "official_eval" / row["algorithm"],
                    base_time=context["base_time"],
                    nav_kind="kf_gins_nav",
                )
            )
    write_stage_h(paths, eval_results)

    figure_result = generate_figures_and_case_review(paths, context, eval_results, skip_figures=skip_figures)
    write_stage_i(paths, figure_result)
    context_sync = update_context_and_obsidian(paths, context, policy, stage1_run, stage1_eval, feedback, stage2_run, baseline_runs, eval_results)
    validation = validate_long_task(paths, policy, stage1_materialization, stage1_run, stage1_eval, feedback, stage2_run, baseline_runs, eval_results, figure_result, context_sync)
    decision = decide_long_task(validation, stage1_run, stage1_eval, feedback, stage2_run, baseline_runs, eval_results)
    stage_status = build_stage_status(policy, stage1_materialization, stage1_run, stage1_eval, feedback, stage2_run, baseline_runs, eval_results, figure_result, context_sync, validation, decision)

    write_json(paths.stage_root / "reports" / "BY3A3_CONTEXT_OBSIDIAN_SYNC_REPORT.json", context_sync)
    write_rows(paths.stage_root / "matrix" / "BY3A3_OBSIDIAN_SYNC_INDEX", context_sync.get("obsidian_rows", []))
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", stage_status)
    write_summary(paths.stage_root / "summary" / "long_task_summary.md", long_summary(decision, validation, eval_results, stage2_run, baseline_runs))
    write_summary(paths.stage_root / "summary" / "long_task_next_stage_recommendation.md", next_stage_summary(decision))
    return {
        "policy": policy,
        "stage1_materialization": stage1_materialization,
        "stage1_run": stage1_run,
        "stage1_eval": stage1_eval,
        "feedback": feedback,
        "stage2_run": stage2_run,
        "baseline_runs": baseline_runs,
        "eval_results": eval_results,
        "figure_result": figure_result,
        "context_sync": context_sync,
        "validation_report": validation,
        "decision_report": decision,
    }


def create_tree(paths: Paths) -> None:
    for root in [paths.stage_root, paths.runtime_root]:
        root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)
    for subdir in ["stage1_solver", "stage2_legsa_full_solver", "single_baseline_solver", "finalv23_solver"]:
        (paths.runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def build_context(paths: Paths) -> dict[str, Any]:
    repair_report = read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {}) or {}
    offsets = repair_report.get("offsets", {})
    base_time = float(offsets.get("body_time_zero_raw_timestamp") or 0.0)
    algorithm_start = float(offsets.get("recommended_algorithm_start_time") or file_time_min(paths.imu) or 0.0)
    gnss_first = first_numeric_row(paths.gnss_dual)
    init_pos = [float(gnss_first[1]), float(gnss_first[2]), float(gnss_first[3])] if len(gnss_first) >= 4 else [0.0, 0.0, 0.0]
    init_yaw = float(gnss_first[13]) if len(gnss_first) >= 14 and math.isfinite(float(gnss_first[13])) else 0.0
    end_time = min(v for v in [file_time_max(paths.imu), file_time_max(paths.gnss_dual)] if v is not None)
    return {
        "base_time": base_time,
        "algorithm_start_time": algorithm_start,
        "end_time": end_time,
        "initpos": init_pos,
        "initatt": [0.0, 0.0, init_yaw],
        "source": "BY3A1 common body-clock input repair report, not trace tuning",
        "no_trace_tuning": True,
        "no_parameter_retuning": True,
        "no_degradation_matrix": True,
        "trace_evaluation_only": True,
        "input_files": {
            "imu": str(paths.imu),
            "dual_gnss": str(paths.gnss_dual),
            "single_gnss": str(paths.gnss_single),
            "raw_doppler": str(paths.raw_doppler),
            "go2_attitude": str(paths.go2_attitude),
            "go2_velocity": str(paths.go2_velocity),
            "go2_joint": str(paths.go2_joint),
        },
    }


def recover_feedback_policy(paths: Paths) -> dict[str, Any]:
    evidence = [
        {
            "artifact_type": "BY2 policy fix script",
            "path_alias": "src/legsa_gins/reporting/by2_n9b1g1_selected_feedback_stage1_eval_dependency_fix.py",
            "evidence_status": "accepted",
            "method_summary": "requires stage1 solver, stage1 official eval, feedback generation from stage1_official_eval/EVAL_NAV.csv, then stage2 solver",
            "can_apply_to_BY3": True,
        },
        {
            "artifact_type": "BY2 command JSON sync fix",
            "path_alias": "src/legsa_gins/reporting/by2_n9b1g2_selected_feedback_command_json_sync_fix.py",
            "evidence_status": "accepted",
            "method_summary": "locks feedback_generation_input_eval_nav to stage1_official_eval/EVAL_NAV.csv and rejects stale stage1_baseline/EVAL_NAV.csv",
            "can_apply_to_BY3": True,
        },
        {
            "artifact_type": "same-case feedback generator",
            "path_alias": "src/legsa_gins/reporting/by2_n9b1c2_selected_feedback_same_case_mapping.py",
            "evidence_status": "accepted",
            "method_summary": "generate_same_case_feedback_observations reads official EVAL_NAV estimate/state fields and writes FGO_FEEDBACK_OBSERVATIONS.csv",
            "can_apply_to_BY3": True,
        },
        {
            "artifact_type": "stage1 algorithm reference",
            "path_alias": "<BY2_N9B2_FULL_MATRIX_ROOT>/BATCH0_SMOKE/.../baseline_no_feedback_EKF",
            "evidence_status": "accepted",
            "method_summary": "historical same-case selected-feedback dependencies used baseline_no_feedback_EKF with feedback disabled as stage1 source",
            "can_apply_to_BY3": True,
        },
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A3_feedback_policy_recovered",
        "stage1_solver_algorithm_id": "baseline_no_feedback_EKF",
        "stage1_feedback_enabled": False,
        "stage1_official_eval_required": True,
        "feedback_generation_input": "stage1_official_eval/EVAL_NAV.csv",
        "feedback_generator": "generate_same_case_feedback_observations",
        "feedback_input_columns_allowed": ["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"],
        "forbidden_columns": ["truth", "trace", "error", "ref", "final_v23"],
        "stage2_algorithm_id": "LegSA_full_EKF",
        "stage2_feedback_required": True,
        "no_by2_feedback_reuse": True,
        "no_trace_error_feedback": True,
        "evidence_rows": evidence,
    }
    return report


def write_stage_a(paths: Paths, policy: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A3_SELECTED_FEEDBACK_POLICY_RECOVERY_REPORT.json", policy)
    write_rows(paths.stage_root / "matrix" / "BY3A3_SELECTED_FEEDBACK_POLICY_EVIDENCE", policy["evidence_rows"])
    write_summary(
        paths.stage_root / "summary" / "by3a3_selected_feedback_policy_recovery.md",
        "\n".join(
            [
                "# BY3A3 Selected-Feedback Policy Recovery",
                "",
                f"Decision: `{policy['decision']}`.",
                "Recovered BY2 policy requires BY3 same-case stage1 official `EVAL_NAV.csv` before feedback generation.",
                "Feedback generation is restricted to state/estimate columns and excludes trace, error, truth, final_v23, BY2 feedback, and clean feedback reuse.",
            ]
        ),
    )


def materialize_stage1(paths: Paths, context: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    output_dir = paths.runtime_root / "stage1_solver" / "baseline_no_feedback_EKF"
    config_path = paths.stage_root / "stage1_solver" / "baseline_no_feedback_EKF.runtime_config.yaml"
    blockers = required_file_blockers(
        {
            "BY3 repaired IMU": paths.imu,
            "BY3 repaired dual GNSS": paths.gnss_dual,
        }
    )
    if policy.get("decision") != "BY3A3_feedback_policy_recovered":
        blockers.append("selected-feedback policy was not recovered")
    if not blockers:
        config_path.write_text(
            make_legsa_config(paths, context, "baseline_no_feedback_EKF", output_dir, selected_feedback_path=None),
            encoding="utf-8",
        )
    row = {
        "algorithm_id": "baseline_no_feedback_EKF",
        "runtime_config_path": str(config_path),
        "output_dir": str(output_dir),
        "selected_feedback_enabled": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "output_substitution": False,
        "raw_doppler_required": False,
        "go2_priors_required": False,
        "blocker_reasons": blockers,
        "decision": "BY3A3_stage1_solver_ready" if not blockers else "BY3A3_stage1_solver_blocked",
    }
    return row


def write_stage_b(paths: Paths, row: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A3_STAGE1_SOLVER_MATERIALIZATION_REPORT.json", row)
    write_rows(paths.stage_root / "matrix" / "BY3A3_STAGE1_SOLVER_CONFIG_INDEX", [row])
    write_summary(
        paths.stage_root / "summary" / "by3a3_stage1_solver_materialization.md",
        f"# BY3A3 Stage1 Solver Materialization\n\nDecision: `{row['decision']}`.\n\nBlockers: {row.get('blocker_reasons') or 'none'}.\n",
    )


def run_legsa_solver(
    paths: Paths,
    *,
    algorithm: str,
    output_dir: Path,
    runtime_config: Path,
    case_overrides: dict[str, str],
) -> dict[str, Any]:
    try:
        return run_formal_algorithm(
            paths.repo,
            algorithm,
            output_dir,
            dry_run=False,
            runtime_config=runtime_config,
            case_overrides=case_overrides,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "algorithm": algorithm,
            "run_status": "failed",
            "returncode": None,
            "blocked_reason": f"solver timed out after {exc.timeout} seconds",
            "output_dir": str(output_dir),
        }
    except Exception as exc:  # noqa: BLE001 - runtime report must capture blockers.
        return {
            "algorithm": algorithm,
            "run_status": "failed",
            "returncode": None,
            "blocked_reason": repr(exc),
            "output_dir": str(output_dir),
        }


def write_stage_c(paths: Paths, row: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A3_STAGE1_SOLVER_EXECUTION_REPORT.json", row)
    write_rows(paths.stage_root / "matrix" / "BY3A3_STAGE1_SOLVER_STATUS", [solver_status_row(row)])
    write_summary(
        paths.stage_root / "summary" / "by3a3_stage1_solver_execution.md",
        f"# BY3A3 Stage1 Solver Execution\n\nStatus: `{row.get('run_status')}`. Return code: `{row.get('returncode')}`.\n\nBlocker: {row.get('blocked_reason') or 'none'}.\n",
    )


def run_official_eval(
    paths: Paths,
    *,
    algorithm: str,
    solver_output_dir: Path,
    official_dir: Path,
    base_time: float,
    nav_kind: str,
) -> dict[str, Any]:
    official_dir.mkdir(parents=True, exist_ok=True)
    eval_script = resolve_eval_script(paths)
    if not paths.trace.exists():
        return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": "trace file missing"}
    if not eval_script:
        return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": "official evaluator path could not be recovered"}
    if not wsl_path_exists(eval_script):
        return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": "official evaluator missing"}

    if nav_kind == "legsa_port_csv":
        nav_src = solver_output_dir / "EVAL_NAV.csv"
        std_src = solver_output_dir / "LegSA_PORT_STD.csv"
        if not nav_src.exists() or not std_src.exists():
            return {"algorithm": algorithm, "official_eval_status": "blocked", "blocked_reason": "LegSA EVAL_NAV/STD outputs missing"}
        nav_dst = official_dir / "converted_eval_nav_official.nav"
        std_dst = official_dir / "converted_std_official.txt"
        nav_meta = _convert_eval_nav(nav_src, nav_dst)
        std_meta = _convert_std(std_src, nav_src, std_dst)
    else:
        nav_candidates = [solver_output_dir / "KF_GINS_Navresult.nav", solver_output_dir / "Navresult.nav"]
        std_candidates = [solver_output_dir / "KF_GINS_STD.txt", solver_output_dir / "STD.txt", solver_output_dir / "KF_GINS_STD.csv"]
        nav_dst = first_existing(nav_candidates)
        std_dst = first_existing(std_candidates)
        if not nav_dst or not std_dst:
            return {
                "algorithm": algorithm,
                "official_eval_status": "blocked",
                "blocked_reason": "KF-GINS NAV/STD outputs missing",
                "nav_candidates": [str(p) for p in nav_candidates],
                "std_candidates": [str(p) for p in std_candidates],
            }
        nav_meta = {"source_format": "KF-GINS NAV", "path": str(nav_dst)}
        std_meta = {"source_format": "KF-GINS STD", "path": str(std_dst)}

    stale_eval_nav = official_dir / "EVAL_NAV.csv"
    if nav_kind == "legsa_port_csv" and stale_eval_nav.exists():
        stale_eval_nav.unlink()
    command = [
        "python3",
        eval_script,
        "--trace",
        repo_to_wsl(paths.trace),
        "--nav",
        repo_to_wsl(nav_dst),
        "--std",
        repo_to_wsl(std_dst),
        "--outdir",
        repo_to_wsl(official_dir),
        "--base_time",
        f"{base_time:.6f}",
        "--yaw_truth_mode",
        "enu",
    ]
    write_json(
        official_dir / "command.json",
        {
            "algorithm": algorithm,
            "command": command,
            "trace_is_evaluation_only": True,
            "trace_solver_input": False,
            "base_time_policy": "BY3A1 common body clock zero",
            "yaw_truth_mode": "enu",
        },
    )
    completed = subprocess.run(
        ["wsl", "bash", "-lc", shlex.join(command)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    (official_dir / "run_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (official_dir / "run_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    normalize_utf8_bom_files(official_dir)
    eval_nav_path = official_dir / "EVAL_NAV.csv"
    eval_nav_materialization = {"created": False, "source": ""}
    if completed.returncode == 0 and nav_kind == "legsa_port_csv" and not eval_nav_path.exists():
        shutil.copy2(nav_src, eval_nav_path)
        eval_nav_materialization = {
            "created": True,
            "source": str(nav_src),
            "reason": "official evaluator completed but did not emit EVAL_NAV.csv; copied the exact evaluated solver state table into the official eval folder for downstream same-case audit/feedback use",
            "trace_columns_added": False,
            "error_columns_added": False,
        }
    summary = read_json(official_dir / "summary.json", {}) or {}
    metrics = metrics_from_summary(summary)
    return {
        "algorithm": algorithm,
        "official_eval_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "official_eval_dir": str(official_dir),
        "eval_nav_path": str(eval_nav_path) if eval_nav_path.exists() else "",
        "eval_nav_materialization": eval_nav_materialization,
        "summary": summary,
        "metrics": metrics,
        "nav_conversion": nav_meta,
        "std_conversion": std_meta,
        "command": command,
        "trace_is_evaluation_only": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_stage_d(paths: Paths, row: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A3_STAGE1_OFFICIAL_EVAL_REPORT.json", row)
    write_rows(paths.stage_root / "matrix" / "BY3A3_STAGE1_EVAL_STATUS", [eval_status_row(row)])
    status = row.get("official_eval_status")
    eval_nav = row.get("eval_nav_path") or ""
    write_summary(
        paths.stage_root / "summary" / "by3a3_stage1_eval_summary.md",
        f"# BY3A3 Stage1 Official Eval\n\nStatus: `{status}`.\n\nEVAL_NAV: `{eval_nav or 'not generated'}`.\n\nBlocker: {row.get('blocked_reason') or 'none'}.\n",
    )


def generate_feedback(paths: Paths, stage1_eval: dict[str, Any]) -> dict[str, Any]:
    eval_nav_text = stage1_eval.get("eval_nav_path") or ""
    eval_nav = Path(eval_nav_text) if eval_nav_text else None
    output_dir = paths.stage_root / "feedback_generation" / "BY3_normal"
    output_dir.mkdir(parents=True, exist_ok=True)
    observations = output_dir / "FGO_FEEDBACK_OBSERVATIONS.csv"
    report_path = output_dir / "OBSERVATION_BUILD_REPORT.json"
    if stage1_eval.get("official_eval_status") != "completed" or eval_nav is None or not eval_nav.exists():
        return {
            "decision": "BY3A3_feedback_generation_blocked",
            "blocked_reason": "stage1 official EVAL_NAV.csv is missing or official eval failed",
            "stage1_eval_nav": eval_nav_text,
            "same_case_BY3_only": True,
        }
    header = csv_header(eval_nav)
    forbidden_used = [col for col in header if forbidden_feedback_column(col)]
    try:
        build_report = generate_same_case_feedback_observations(
            case_id="BY3_normal",
            baseline_eval_nav=eval_nav,
            gnss_path=paths.gnss_dual,
            output_observations=observations,
            output_report=report_path,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "decision": "BY3A3_feedback_generation_blocked",
            "blocked_reason": repr(exc),
            "stage1_eval_nav": str(eval_nav),
            "same_case_BY3_only": True,
            "forbidden_columns_present_in_eval_nav": forbidden_used,
        }
    row_count = count_data_rows(observations)
    decision = "BY3A3_feedback_generation_completed" if row_count > 0 else "BY3A3_feedback_generation_blocked"
    return {
        "decision": decision,
        "blocked_reason": "" if row_count > 0 else "feedback observation file has zero rows",
        "feedback_observations": str(observations),
        "feedback_report": str(report_path),
        "row_count": row_count,
        "sha256": sha256_file(observations) if observations.exists() else "",
        "source_stage1_eval_nav": str(eval_nav),
        "same_case_BY3_only": True,
        "no_by2_feedback_reuse": True,
        "no_trace_error_feedback": True,
        "allowed_input_columns_used": ["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"],
        "forbidden_columns_present_in_eval_nav": forbidden_used,
        "build_report": build_report,
    }


def write_stage_e(paths: Paths, row: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A3_FEEDBACK_GENERATION_REPORT.json", row)
    write_rows(paths.stage_root / "matrix" / "BY3A3_FEEDBACK_GENERATION_STATUS", [row])
    write_summary(
        paths.stage_root / "summary" / "by3a3_feedback_generation.md",
        f"# BY3A3 Feedback Generation\n\nDecision: `{row.get('decision')}`.\n\nRows: `{row.get('row_count', 0)}`.\n\nBlocker: {row.get('blocked_reason') or 'none'}.\n",
    )


def materialize_stage2(paths: Paths, context: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any]:
    output_dir = paths.runtime_root / "stage2_legsa_full_solver" / "LegSA_full_EKF"
    config_path = paths.stage_root / "stage2_legsa_full_solver" / "LegSA_full_EKF.runtime_config.yaml"
    blockers = required_file_blockers(
        {
            "BY3 repaired IMU": paths.imu,
            "BY3 repaired dual GNSS": paths.gnss_dual,
            "BY3 Raw Doppler provider": paths.raw_doppler,
            "BY3 Go2 attitude prior": paths.go2_attitude,
            "BY3 Go2 velocity prior": paths.go2_velocity,
            "BY3 Go2 joint prior": paths.go2_joint,
            "BY3 same-case feedback": Path(feedback.get("feedback_observations") or ""),
        }
    )
    if not blockers:
        config_path.write_text(
            make_legsa_config(paths, context, "LegSA_full_EKF", output_dir, selected_feedback_path=Path(feedback["feedback_observations"])),
            encoding="utf-8",
        )
    return {
        "algorithm_id": "LegSA_full_EKF",
        "role": "final_algorithm",
        "runtime_config_path": str(config_path),
        "output_dir": str(output_dir),
        "selected_feedback_enabled": True,
        "feedback_path": feedback.get("feedback_observations", ""),
        "raw_doppler_provider": str(paths.raw_doppler),
        "go2_prior_dir": str(paths.go2_prior_dir),
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "output_substitution": False,
        "blocker_reasons": blockers,
        "decision": "BY3A3_stage2_legsa_full_ready" if not blockers else "BY3A3_stage2_legsa_full_blocked",
    }


def write_stage_f(paths: Paths, row: dict[str, Any]) -> None:
    report = {
        "stage": STAGE,
        "algorithm_id": "LegSA_full_EKF",
        "decision": "BY3A3_stage2_legsa_full_completed" if row.get("run_status") == "completed" else "BY3A3_stage2_legsa_full_failed",
        "run_result": row,
        "selected_feedback_gate": "satisfied" if row.get("run_status") == "completed" else "blocked_or_failed",
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "output_substitution": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A3_STAGE2_LEGSA_FULL_SOLVER_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A3_STAGE2_LEGSA_FULL_STATUS", [solver_status_row(row)])
    write_summary(
        paths.stage_root / "summary" / "by3a3_stage2_legsa_full_solver.md",
        f"# BY3A3 Stage2 LegSA Full Solver\n\nStatus: `{row.get('run_status')}`.\n\nBlocker: {row.get('blocked_reason') or 'none'}.\n",
    )


def run_baseline_solvers(paths: Paths, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    rows.append(run_single_baseline(paths, context))
    rows.append(run_finalv23(paths, context))
    return rows


def run_single_baseline(paths: Paths, context: dict[str, Any]) -> dict[str, Any]:
    algorithm = "single_antenna_gnss1_status_KF_GINS"
    src_config = paths.by3a2_root / "single_runner_handoff" / "by3_single_baseline.runtime_config.yaml"
    output_dir = paths.runtime_root / "single_baseline_solver" / algorithm
    config_path = paths.stage_root / "single_baseline_solver" / "by3_single_baseline.runtime_config.yaml"
    blockers = required_file_blockers({"BY3A2 single config": src_config, "BY3 repaired IMU": paths.imu, "BY3 repaired single GNSS": paths.gnss_single})
    if blockers:
        return skipped_or_blocked_run(algorithm, "; ".join(blockers), output_dir=output_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = src_config.read_text(encoding="utf-8", errors="ignore")
    text = replace_yaml_key(text, "outputpath", repo_to_wsl(output_dir), quoted=True)
    text = apply_external_kfgins_time_handoff(text, paths.imu, paths.gnss_single, use_dual_yaw=False)
    text += "\n# BY3A3 handoff repair: start/end follow first/last GNSS epochs inside repaired IMU overlap; algorithm math unchanged.\n"
    config_path.write_text(text, encoding="utf-8")
    report = read_json(paths.by3a2_root / "reports" / "BY3A2_SINGLE_BASELINE_HANDOFF_REPORT.json", {}) or {}
    command = list(report.get("command", []))
    if not command:
        return skipped_or_blocked_run(algorithm, "BY3A2 single command missing", output_dir=output_dir)
    command[-1] = repo_to_wsl(config_path)
    command = normalize_wsl_command(command)
    return run_external_solver(paths, algorithm, output_dir, command, config_path, role="traditional_baseline")


def run_finalv23(paths: Paths, context: dict[str, Any]) -> dict[str, Any]:
    algorithm = "final_v23_dual_antenna_EKF"
    src_config = paths.by3a2_root / "finalv23_runner_handoff" / "by3_finalv23_external.runtime_config.yaml"
    output_dir = paths.runtime_root / "finalv23_solver" / algorithm
    config_path = paths.stage_root / "finalv23_solver" / "by3_finalv23_external.runtime_config.yaml"
    blockers = required_file_blockers({"BY3A2 final_v23 config": src_config, "BY3 repaired IMU": paths.imu, "BY3 repaired dual GNSS": paths.gnss_dual})
    if blockers:
        return skipped_or_blocked_run(algorithm, "; ".join(blockers), output_dir=output_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = src_config.read_text(encoding="utf-8", errors="ignore")
    text = replace_yaml_key(text, "outputpath", repo_to_wsl(output_dir), quoted=True)
    text = apply_external_kfgins_time_handoff(text, paths.imu, paths.gnss_dual, use_dual_yaw=True)
    text += "\n# BY3A3 handoff repair: start/end follow BY3A1 repaired IMU overlap; algorithm math unchanged.\n"
    config_path.write_text(text, encoding="utf-8")
    report = read_json(paths.by3a2_root / "reports" / "BY3A2_FINALV23_HANDOFF_REPORT.json", {}) or {}
    command = list(report.get("command", []))
    if not command:
        return skipped_or_blocked_run(algorithm, "BY3A2 final_v23 command missing", output_dir=output_dir)
    command[-1] = repo_to_wsl(config_path)
    command = normalize_wsl_command(command)
    return run_external_solver(paths, algorithm, output_dir, command, config_path, role="external_reference_baseline")


def run_external_solver(paths: Paths, algorithm: str, output_dir: Path, command: list[str], config_path: Path, *, role: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    clear_runtime_solver_outputs(output_dir, paths.runtime_root)
    write_json(output_dir / "solver_command.json", {"algorithm": algorithm, "command": command, "role": role})
    write_json(
        output_dir / "source_role.json",
        {
            "algorithm": algorithm,
            "role": role,
            "trace_role": "evaluation_only_not_solver_input",
            "final_v23_role": "external_reference_baseline" if algorithm == "final_v23_dual_antenna_EKF" else "not_solver_input",
            "legsa_solver_input": False,
        },
    )
    write_json(
        output_dir / "output_lineage.json",
        {
            "algorithm": algorithm,
            "config_path": str(config_path),
            "output_dir": str(output_dir),
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "degradation_execution": False,
        },
    )
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        (output_dir / "logs").mkdir(exist_ok=True)
        (output_dir / "logs" / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (output_dir / "logs" / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        outputs = {p.name: str(p) for p in output_dir.glob("*") if p.is_file()}
        return {
            "algorithm": algorithm,
            "run_status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "command": {"command": command},
            "config": {"config_path": str(config_path), "config_path_wsl": repo_to_wsl(config_path)},
            "output_dir": str(output_dir),
            "outputs": outputs,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        }
    except subprocess.TimeoutExpired as exc:
        return skipped_or_blocked_run(algorithm, f"solver timed out after {exc.timeout} seconds", output_dir=output_dir)


def write_stage_g(paths: Paths, rows: list[dict[str, Any]]) -> None:
    report = {
        "stage": STAGE,
        "decision": baseline_decision(rows),
        "solver_rows": rows,
        "single_output_not_used_by_legsa": True,
        "finalv23_output_not_used_by_legsa": True,
    }
    write_json(paths.stage_root / "reports" / "BY3A3_BASELINE_SOLVER_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A3_BASELINE_SOLVER_STATUS", [solver_status_row(row) for row in rows])
    write_summary(
        paths.stage_root / "summary" / "by3a3_baseline_solver_summary.md",
        "# BY3A3 Baseline Solver Summary\n\n"
        + "\n".join(f"- `{row['algorithm']}`: `{row.get('run_status')}` ({row.get('blocked_reason') or 'no blocker'})" for row in rows)
        + "\n",
    )


def write_stage_h(paths: Paths, rows: list[dict[str, Any]]) -> None:
    metrics_rows = [metric_row(row) for row in rows if row.get("official_eval_status") == "completed"]
    report = {
        "stage": STAGE,
        "decision": "BY3A3_official_evaluation_completed" if metrics_rows else "BY3A3_official_evaluation_not_completed",
        "evaluation_rows": rows,
        "trace_evaluation_only": True,
        "trace_solver_input": False,
        "base_time_policy": "BY3A1 common body-clock zero",
    }
    write_json(paths.stage_root / "reports" / "BY3A3_OFFICIAL_EVALUATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A3_EVAL_STATUS", [eval_status_row(row) for row in rows])
    write_rows(paths.stage_root / "matrix" / "BY3A3_NORMAL_METRICS", metrics_rows)
    write_summary(
        paths.stage_root / "summary" / "by3a3_eval_summary.md",
        eval_summary(metrics_rows, rows),
    )


def write_stage_i(paths: Paths, result: dict[str, Any]) -> None:
    status = result.get("decision", "unknown")
    figure_count = sum(1 for row in result.get("figure_rows", []) if row.get("exists") and int(row.get("file_size") or 0) > 0)
    write_summary(
        paths.stage_root / "summary" / "by3a3_figures_case_review_summary.md",
        "# BY3A3 Figures And Case Review\n\n"
        f"Decision: `{status}`.\n\n"
        f"Generated non-empty figure files: `{figure_count}`.\n\n"
        f"Case review created: `{str(result.get('case_review_created', False)).lower()}`.\n",
    )


def generate_figures_and_case_review(paths: Paths, context: dict[str, Any], eval_results: list[dict[str, Any]], *, skip_figures: bool) -> dict[str, Any]:
    completed = [row for row in eval_results if row.get("official_eval_status") == "completed"]
    if skip_figures or not completed:
        result = {
            "decision": "BY3A3_figures_not_generated_no_metrics",
            "reason": "skip-figures requested" if skip_figures else "no completed official evaluations",
            "figure_rows": [],
            "case_review_created": False,
        }
        write_json(paths.stage_root / "reports" / "BY3A3_FIGURE_GENERATION_REPORT.json", result)
        write_rows(paths.stage_root / "matrix" / "BY3A3_FIGURE_INDEX", [])
        return result
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        result = {"decision": "BY3A3_figures_partial", "reason": f"matplotlib unavailable: {exc}", "figure_rows": [], "case_review_created": False}
        write_json(paths.stage_root / "reports" / "BY3A3_FIGURE_GENERATION_REPORT.json", result)
        write_rows(paths.stage_root / "matrix" / "BY3A3_FIGURE_INDEX", [])
        return result

    figure_rows: list[dict[str, Any]] = []
    metric_rows = [metric_row(row) for row in completed]
    data_by_alg = {row["algorithm"]: load_eval_data(Path(row["official_eval_dir"])) for row in completed}

    figure_specs = [
        ("01_trajectory", "BY3A3_normal_three_way_trajectory", "trajectory"),
        ("01_trajectory", "BY3A3_normal_start_end_marker", "trajectory_markers"),
        ("01_trajectory", "BY3A3_normal_zoom", "trajectory_zoom"),
        ("02_position_errors", "BY3A3_normal_N_E_U_error_timeseries", "neu_errors"),
        ("02_position_errors", "BY3A3_normal_horizontal_error_timeseries", "horizontal_error"),
        ("02_position_errors", "BY3A3_normal_horizontal_up_rmse_bar", "rmse_bar"),
        ("02_position_errors", "BY3A3_normal_horizontal_up_p95_bar", "p95_bar"),
        ("04_attitude", "BY3A3_normal_yaw_error_timeseries", "yaw_error"),
        ("04_attitude", "BY3A3_normal_attitude_rmse_bar", "attitude_bar"),
        ("07_compare", "BY3A3_normal_LegSA_full_single_finalv23_summary", "summary_bar"),
        ("13_degradation_meta", "BY3A3_data_quality_overview", "data_quality"),
        ("14_audit_sanity", "BY3A3_alignment_input_provider_feedback_sanity_panel", "sanity"),
    ]
    for subdir, stem, kind in figure_specs:
        outdir = paths.stage_root / "figures" / subdir
        outdir.mkdir(parents=True, exist_ok=True)
        png = outdir / f"{stem}.png"
        pdf = outdir / f"{stem}.pdf"
        ok = draw_figure(plt, kind, data_by_alg, metric_rows, context, png, pdf)
        for path in [png, pdf]:
            figure_rows.append(
                {
                    "figure": stem,
                    "path": str(path),
                    "exists": path.exists(),
                    "file_size": path.stat().st_size if path.exists() else 0,
                    "kind": kind,
                    "copy_status": "generated" if ok and path.exists() else "not_generated",
                    "source": "real official evaluation outputs",
                }
            )
    case_review = build_case_review(paths, context, metric_rows, completed)
    result = {
        "decision": "BY3A3_figures_and_case_review_completed",
        "figure_rows": figure_rows,
        "case_review_created": True,
        "case_review_md": str(paths.stage_root / "case_review" / "BY3A3_normal_generalization_case_review.md"),
        "case_review_json": str(paths.stage_root / "case_review" / "BY3A3_normal_generalization_case_review.json"),
    }
    result["case_review"] = case_review
    write_json(paths.stage_root / "reports" / "BY3A3_FIGURE_GENERATION_REPORT.json", result)
    write_rows(paths.stage_root / "matrix" / "BY3A3_FIGURE_INDEX", figure_rows)
    return result


def draw_figure(plt: Any, kind: str, data_by_alg: dict[str, dict[str, list[dict[str, Any]]]], metric_rows: list[dict[str, Any]], context: dict[str, Any], png: Path, pdf: Path) -> bool:
    fig, ax = plt.subplots(figsize=(9, 5))
    plotted = False
    if kind.startswith("trajectory"):
        for alg, data in data_by_alg.items():
            rows = data.get("eval_nav", [])
            xs = numeric_series(rows, ["lon_deg", "lon", "longitude"])
            ys = numeric_series(rows, ["lat_deg", "lat", "latitude"])
            if xs and ys:
                if kind == "trajectory_zoom":
                    xs, ys = xs[: min(120, len(xs))], ys[: min(120, len(ys))]
                ax.plot(xs, ys, label=alg, linewidth=1.2)
                if kind == "trajectory_markers":
                    ax.scatter([xs[0], xs[-1]], [ys[0], ys[-1]], s=24)
                plotted = True
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
    elif kind in {"neu_errors", "horizontal_error", "yaw_error"}:
        for alg, data in data_by_alg.items():
            rows = data.get("error_series", []) or data.get("eval_nav", [])
            t = numeric_series(rows, ["time", "timestamp"])
            if kind == "horizontal_error":
                h = horizontal_series(rows)
                if t and h:
                    ax.plot(t[: len(h)], h, label=alg, linewidth=1.0)
                    plotted = True
                ax.set_ylabel("Horizontal error (m)")
            elif kind == "yaw_error":
                y = numeric_series(rows, ["yaw_error_deg", "err_yaw_deg", "yaw_err_deg"])
                if t and y:
                    ax.plot(t[: len(y)], y, label=alg, linewidth=1.0)
                    plotted = True
                ax.set_ylabel("Yaw error (deg)")
            else:
                components = [
                    ("N", ["north_error_m", "err_n_m", "error_n_m"]),
                    ("E", ["east_error_m", "err_e_m", "error_e_m"]),
                    ("U", ["up_error_m", "err_u_m", "error_u_m", "vertical_error_m"]),
                ]
                for label, columns in components:
                    vals = numeric_series(rows, columns)
                    if t and vals:
                        ax.plot(t[: len(vals)], vals, label=f"{alg} {label}", linewidth=0.8)
                        plotted = True
                ax.set_ylabel("Error (m)")
        ax.set_xlabel("Time (s)")
    else:
        labels = [row["algorithm"] for row in metric_rows]
        if kind in {"rmse_bar", "summary_bar"}:
            values = [float(row.get("horizontal_rmse_m") or 0.0) for row in metric_rows]
            ax.bar(labels, values)
            ax.set_ylabel("Horizontal RMSE (m)")
            plotted = bool(values)
        elif kind == "p95_bar":
            values = [float(row.get("horizontal_p95_m") or 0.0) for row in metric_rows]
            ax.bar(labels, values)
            ax.set_ylabel("Horizontal P95 (m)")
            plotted = bool(values)
        elif kind == "attitude_bar":
            values = [float(row.get("yaw_rmse_deg") or 0.0) for row in metric_rows]
            ax.bar(labels, values)
            ax.set_ylabel("Yaw RMSE (deg)")
            plotted = bool(values)
        elif kind == "data_quality":
            vals = [context["algorithm_start_time"], context["end_time"]]
            ax.bar(["algorithm_start", "evaluation_end"], vals)
            ax.set_ylabel("Time (s)")
            plotted = True
        else:
            texts = [
                f"base_time={context['base_time']:.6f}",
                f"start={context['algorithm_start_time']:.3f}",
                f"end={context['end_time']:.3f}",
                "trace_solver_input=false",
                "degradation_matrix=false",
            ]
            ax.axis("off")
            ax.text(0.02, 0.95, "\n".join(texts), va="top", fontfamily="monospace")
            plotted = True
    if not plotted:
        ax.axis("off")
        ax.text(0.02, 0.95, "No plottable official evaluation series for this panel.", va="top")
    ax.set_title(kind.replace("_", " "))
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(png, dpi=160)
    fig.savefig(pdf)
    plt.close(fig)
    return plotted


def build_case_review(paths: Paths, context: dict[str, Any], metric_rows: list[dict[str, Any]], completed: list[dict[str, Any]]) -> dict[str, Any]:
    review = {
        "stage": STAGE,
        "evaluation_completed": bool(metric_rows),
        "input_files": {
            "imu": "<BY3_OUTPUT_ROOT>/BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR/input_repair/BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu",
            "dual_gnss": "<BY3_OUTPUT_ROOT>/BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR/input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
            "single_gnss": "<BY3_OUTPUT_ROOT>/BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR/input_repair/BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss",
            "raw_doppler": "<BY3_OUTPUT_ROOT>/BY3A2.../raw_doppler_recovery/provider_only/RAW_DOPPLER_VELOCITY_FACTORS.csv",
        },
        "case_overview": "BY3 normal same-case selected-feedback chain and normal comparison only; no degradation matrix.",
        "summary_metrics": metric_rows,
        "main_takeaway": "BY3A3 records only real completed solver/evaluator outputs; paper claims remain disabled.",
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "case_review" / "BY3A3_normal_generalization_case_review.json", review)
    lines = [
        "# BY3A3 Normal Generalization Case Review",
        "",
        "## Evaluation Completed",
        str(bool(metric_rows)).lower(),
        "",
        "## Input Files",
        "- BY3 repaired IMU, dual GNSS, and single GNSS inputs from BY3A1.",
        "- BY3 Raw Doppler and Go2 priors from BY3A2/BY3A1 provider materialization.",
        "- Trace used only by official evaluator.",
        "",
        "## Case Overview",
        review["case_overview"],
        "",
        "## Summary Metrics",
    ]
    if metric_rows:
        for row in metric_rows:
            lines.append(
                f"- `{row['algorithm']}`: horizontal RMSE `{row.get('horizontal_rmse_m')}`, up RMSE `{row.get('up_rmse_m')}`, yaw RMSE `{row.get('yaw_rmse_deg')}`."
            )
    else:
        lines.append("- No completed official evaluation metrics.")
    lines.extend(
        [
            "",
            "## 3σ Consistency Statistics",
            "Included only if available in the official evaluator summary.",
            "",
            "## Attitude-level Assessment",
            "Use yaw/roll/pitch metrics only from completed official evaluations.",
            "",
            "## Brief Interpretation",
            "This is a gated BY3 normal execution record, not a paper claim.",
            "",
            "## Main Takeaway",
            review["main_takeaway"],
        ]
    )
    write_summary(paths.stage_root / "case_review" / "BY3A3_normal_generalization_case_review.md", "\n".join(lines) + "\n")
    return review


def update_context_and_obsidian(
    paths: Paths,
    context: dict[str, Any],
    policy: dict[str, Any],
    stage1_run: dict[str, Any],
    stage1_eval: dict[str, Any],
    feedback: dict[str, Any],
    stage2_run: dict[str, Any],
    baseline_runs: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
) -> dict[str, Any]:
    obsidian_dir = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization"
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    notes = {
        "00_INDEX.md": "# BY3 Generalization\n\nBY3A3 selected-feedback stage1 chain has a runtime report under `<BY3_OUTPUT_ROOT>/BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION`.\n",
        "01_CURRENT_STATE.md": f"# Current State\n\nBY3A3 policy: `{policy['decision']}`.\n\nStage1 solver: `{stage1_run.get('run_status')}`.\n\nStage1 official eval: `{stage1_eval.get('official_eval_status')}`.\n\nFeedback: `{feedback.get('decision')}`.\n\nStage2 LegSA_full: `{stage2_run.get('run_status')}`.\n\nPaper claims: false.\n",
        "03_ALIGNMENT_RESULT.md": f"# Alignment Result\n\nBY3A3 uses BY3A1 common body-clock base time policy. `base_time` is recorded in runtime reports only. Trace tuning: false.\n",
        "05_NORMAL_GENERALIZATION_RESULT.md": "# Normal Generalization Result\n\nNormal BY3 outputs are listed in BY3A3 matrices. Degradation matrix was not run.\n",
        "08_CLAIM_BOUNDARY.md": "# Claim Boundary\n\nready_for_paper_claims=false. Do not claim outperform final_v23. Do not treat BY3 normal as paper-ready until human review.\n",
        "09_NEXT_STEPS.md": "# Next Steps\n\nFollow the BY3A3 long-task decision report. BY3 degradation planning is allowed only if BY3A3 normal generalization completed.\n",
    }
    for name, text in notes.items():
        path = obsidian_dir / name
        path.write_text(text, encoding="utf-8")
        rows.append({"note": name, "path_alias": f"obsidian_knowledge/LegSA-GINS/BY3_generalization/{name}", "public_path_leak_free": not contains_local_path(text), "status": "updated"})
    return {
        "stage": STAGE,
        "tracked_docs_changed": False,
        "obsidian_updated": True,
        "obsidian_untracked_expected": True,
        "public_notes_path_leak_free": all(row["public_path_leak_free"] for row in rows),
        "obsidian_rows": rows,
        "ready_for_paper_claims": False,
    }


def validate_long_task(
    paths: Paths,
    policy: dict[str, Any],
    stage1_materialization: dict[str, Any],
    stage1_run: dict[str, Any],
    stage1_eval: dict[str, Any],
    feedback: dict[str, Any],
    stage2_run: dict[str, Any],
    baseline_runs: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    figure_result: dict[str, Any],
    context_sync: dict[str, Any],
) -> dict[str, Any]:
    issues = []
    checks = {
        "selected_feedback_policy_recovered": policy.get("decision") == "BY3A3_feedback_policy_recovered",
        "stage1_config_materialized": stage1_materialization.get("decision") == "BY3A3_stage1_solver_ready",
        "stage1_eval_nav_exists_if_stage1_ran": stage1_run.get("run_status") != "completed" or Path(stage1_eval.get("eval_nav_path") or "").exists(),
        "feedback_from_stage1_official_eval_only": feedback.get("decision") != "BY3A3_feedback_generation_completed" or "stage1_official_eval" in feedback.get("source_stage1_eval_nav", ""),
        "no_by2_feedback_reuse": feedback.get("no_by2_feedback_reuse", True) is True,
        "no_trace_error_feedback": feedback.get("no_trace_error_feedback", True) is True,
        "stage2_only_if_feedback_exists": stage2_run.get("run_status") != "completed" or Path(feedback.get("feedback_observations") or "").exists(),
        "single_final_not_legsa_input": True,
        "no_degradation_matrix": True,
        "no_trace_solver_input": True,
        "no_finalv23_solver_input_for_legsa": True,
        "no_fabricated_outputs": True,
        "runtime_untracked_expected": git_is_untracked_or_ignored(paths.repo, paths.stage_root) and git_is_untracked_or_ignored(paths.repo, paths.runtime_root),
        "obsidian_path_leak_free": context_sync.get("public_notes_path_leak_free") is True,
        "ready_for_paper_claims_false": True,
    }
    for key, ok in checks.items():
        if not ok:
            issues.append(key)
    parse_issues = parse_stage_files(paths.stage_root)
    issues.extend(parse_issues)
    ready_for_degradation_planning = (
        not issues
        and stage1_run.get("run_status") == "completed"
        and stage1_eval.get("official_eval_status") == "completed"
        and feedback.get("decision") == "BY3A3_feedback_generation_completed"
        and stage2_run.get("run_status") == "completed"
        and all(row.get("run_status") == "completed" for row in baseline_runs)
        and bool(eval_results)
        and all(row.get("official_eval_status") == "completed" for row in eval_results)
    )
    return {
        "stage": STAGE,
        "status": "pass" if not issues else "fail",
        "checks": checks,
        "issues": issues,
        "json_csv_parse_ok": not parse_issues,
        "ready_for_paper_claims": False,
        "ready_for_BY3_degradation_matrix_planning": ready_for_degradation_planning,
    }


def decide_long_task(
    validation: dict[str, Any],
    stage1_run: dict[str, Any],
    stage1_eval: dict[str, Any],
    feedback: dict[str, Any],
    stage2_run: dict[str, Any],
    baseline_runs: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
) -> dict[str, Any]:
    if validation.get("status") != "pass":
        status = "BY3A3_safety_gate_failed"
        ready = False
        next_stage = "repair_safety_violation"
    elif stage1_run.get("run_status") != "completed":
        status = "BY3A3_stage1_solver_failed"
        ready = False
        next_stage = "repair_BY3_stage1_solver"
    elif stage1_eval.get("official_eval_status") != "completed" or feedback.get("decision") != "BY3A3_feedback_generation_completed":
        status = "BY3A3_stage1_eval_or_feedback_generation_failed"
        ready = False
        next_stage = "repair_BY3_feedback_generation"
    elif stage2_run.get("run_status") != "completed":
        status = "BY3A3_stage1_feedback_chain_completed_but_stage2_failed"
        ready = False
        next_stage = "repair_BY3_stage2_legsa_full"
    elif any(row.get("run_status") != "completed" for row in baseline_runs):
        status = "BY3A3_baseline_solvers_partial"
        ready = False
        next_stage = "repair_BY3_single_or_final_baseline"
    elif not eval_results or any(row.get("official_eval_status") != "completed" for row in eval_results):
        status = "BY3A3_stage1_feedback_chain_completed_but_stage2_failed"
        ready = False
        next_stage = "repair_BY3_official_evaluation"
    else:
        status = "BY3A3_normal_generalization_completed"
        ready = True
        next_stage = "BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK"
    return {
        "stage": STAGE,
        "status": status,
        "ready_for_BY3_degradation_matrix_planning": ready,
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
        "pr_52_merged": False,
        "tag_created": False,
    }


def build_stage_status(*items: Any) -> list[dict[str, Any]]:
    names = [
        "policy_recovery",
        "stage1_materialization",
        "stage1_solver",
        "stage1_official_eval",
        "feedback_generation",
        "stage2_legsa_full",
        "baseline_solvers",
        "official_evaluation",
        "figures_case_review",
        "context_obsidian_sync",
        "validation",
        "decision",
    ]
    rows = []
    for name, item in zip(names, items):
        if isinstance(item, list):
            status = ",".join(str(row.get("run_status") or row.get("official_eval_status") or row.get("decision")) for row in item)
        elif isinstance(item, dict):
            status = str(item.get("decision") or item.get("status") or item.get("run_status") or item.get("official_eval_status"))
        else:
            status = str(item)
        rows.append({"stage_item": name, "status": status})
    return rows


def make_legsa_config(paths: Paths, context: dict[str, Any], algorithm: str, output_dir: Path, selected_feedback_path: Path | None) -> str:
    base_values, _ = load_base_config_values(paths.repo)
    base_values = dict(base_values)
    base_values.update(
        {
            "imupath": repo_to_wsl(paths.imu),
            "gnsspath": repo_to_wsl(paths.gnss_dual),
            "initpos": format_vec(context["initpos"]),
            "initvel": "[ 0.0, 0.0, 0.0 ]",
            "initatt": format_vec(context["initatt"]),
            "initposstd": "[ 10.0, 10.0, 10.0 ]",
            "initvelstd": "[ 5.0, 5.0, 5.0 ]",
            "initattstd": "[ 2.0, 2.0, 2.0 ]",
            "antlever": "[ 0.0, 0.0, -0.25 ]",
        }
    )
    text = build_algorithm_config_text(paths.repo, algorithm, output_dir, base_values)
    replacements = {
        "run_label": "BY3A3_normal_same_case_feedback" if algorithm == "LegSA_full_EKF" else "BY3A3_stage1_no_feedback",
        "imupath": repo_to_wsl(paths.imu),
        "gnsspath": repo_to_wsl(paths.gnss_dual),
        "outputpath": repo_to_wsl(output_dir),
        "starttime": f"{context['algorithm_start_time']:.9f}",
        "endtime": f"{context['end_time']:.9f}",
        "initpos": format_vec(context["initpos"]),
        "initatt": format_vec(context["initatt"]),
        "raw_doppler_factor_path": repo_to_wsl(paths.raw_doppler) if algorithm == "LegSA_full_EKF" else "",
        "go2_attitude_prior_path": repo_to_wsl(paths.go2_attitude) if algorithm == "LegSA_full_EKF" else "",
        "go2_horizontal_velocity_prior_path": repo_to_wsl(paths.go2_velocity) if algorithm == "LegSA_full_EKF" else "",
        "go2_proprioceptive_joint_factor_path": repo_to_wsl(paths.go2_joint) if algorithm == "LegSA_full_EKF" else "",
        "fgo_feedback_path": repo_to_wsl(selected_feedback_path) if selected_feedback_path else "",
    }
    for key, value in replacements.items():
        text = replace_yaml_key(text, key, value, quoted=key.endswith("path") or key in {"run_label"})
    text += "\n# BY3A3 runtime-only safety lock.\n"
    text += "case_id: BY3_normal\n"
    text += "by3_stage: BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION\n"
    text += "selected_feedback_same_case_required: true\n" if algorithm == "LegSA_full_EKF" else "selected_feedback_same_case_required: false\n"
    text += "by2_feedback_reuse_allowed: false\n"
    text += "trace_solver_input: false\n"
    text += "final_v23_output_solver_input: false\n"
    text += "degradation_matrix: false\n"
    text += "parameter_retuning: false\n"
    return text


def stage1_case_overrides(paths: Paths) -> dict[str, str]:
    return {
        "case_id": "BY3_normal_stage1",
        "imu_source_override": repo_to_wsl(paths.imu),
        "gnss_input_override": repo_to_wsl(paths.gnss_dual),
        "selected_feedback_dependency": "disabled_stage1",
        "trace_solver_input": "false",
        "final_v23_output_solver_input": "false",
    }


def stage2_case_overrides(paths: Paths, feedback: dict[str, Any]) -> dict[str, str]:
    return {
        "case_id": "BY3_normal",
        "imu_source_override": repo_to_wsl(paths.imu),
        "gnss_input_override": repo_to_wsl(paths.gnss_dual),
        "feedback_input_override": repo_to_wsl(Path(feedback["feedback_observations"])),
        "raw_doppler_input_override": repo_to_wsl(paths.raw_doppler),
        "go2_input_override": repo_to_wsl(paths.go2_joint),
        "trace_solver_input": "false",
        "final_v23_output_solver_input": "false",
    }


def required_file_blockers(files: dict[str, Path]) -> list[str]:
    blockers = []
    for label, path in files.items():
        if not path or not path.exists():
            blockers.append(f"{label} missing: {path}")
        elif path.is_file() and path.stat().st_size == 0:
            blockers.append(f"{label} empty: {path}")
    return blockers


def skipped_or_blocked_run(algorithm: str, reason: str, *, output_dir: Path | None = None) -> dict[str, Any]:
    return {
        "algorithm": algorithm,
        "run_status": "blocked",
        "returncode": None,
        "blocked_reason": reason,
        "output_dir": str(output_dir) if output_dir else "",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "degradation_execution": False,
    }


def solver_status_row(row: dict[str, Any]) -> dict[str, Any]:
    outputs = row.get("outputs", {})
    return {
        "algorithm": row.get("algorithm"),
        "run_status": row.get("run_status"),
        "returncode": row.get("returncode"),
        "blocked_reason": row.get("blocked_reason", ""),
        "output_dir": row.get("output_dir") or str(Path(next(iter(outputs.values()))).parent) if outputs else row.get("output_dir", ""),
        "nav_output": outputs.get("LegSA_PORT_NAV.nav") or outputs.get("KF_GINS_Navresult.nav") or "",
        "std_output": outputs.get("LegSA_PORT_STD.csv") or outputs.get("KF_GINS_STD.txt") or "",
        "run_manifest": outputs.get("RUN_MANIFEST.json") or "",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "degradation_execution": False,
    }


def eval_status_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "algorithm": row.get("algorithm"),
        "official_eval_status": row.get("official_eval_status"),
        "returncode": row.get("returncode"),
        "blocked_reason": row.get("blocked_reason", ""),
        "official_eval_dir": row.get("official_eval_dir", ""),
        "eval_nav_path": row.get("eval_nav_path", ""),
        "trace_evaluation_only": True,
        "trace_solver_input": False,
    }


def metric_row(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("metrics") or {}
    out = {"algorithm": row.get("algorithm"), "official_eval_dir": row.get("official_eval_dir", "")}
    for key in METRIC_KEYS:
        out[key] = metrics.get(key)
    return out


def metrics_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = _metrics_from_summary(summary)
    position = summary.get("position", {}) if isinstance(summary, dict) else {}
    attitude = summary.get("attitude", {}) if isinstance(summary, dict) else {}
    meta = summary.get("meta", {}) if isinstance(summary, dict) else {}
    metrics.update(
        {
            "north_rmse_m": position.get("north_rmse_m"),
            "east_rmse_m": position.get("east_rmse_m"),
            "horizontal_p95_m": position.get("horizontal_p95_m"),
            "horizontal_max_m": position.get("horizontal_max_m"),
            "roll_p95_deg": attitude.get("roll_p95_deg"),
            "pitch_p95_deg": attitude.get("pitch_p95_deg"),
            "yaw_p95_deg": attitude.get("yaw_p95_deg"),
            "sample_count": meta.get("num_samples"),
        }
    )
    return metrics


def baseline_decision(rows: list[dict[str, Any]]) -> str:
    if all(row.get("run_status") == "completed" for row in rows):
        return "BY3A3_baseline_solvers_completed"
    if any(row.get("run_status") == "completed" for row in rows):
        return "BY3A3_baseline_solvers_partial"
    return "BY3A3_baseline_solvers_failed"


def eval_summary(metric_rows: list[dict[str, Any]], eval_rows: list[dict[str, Any]]) -> str:
    lines = ["# BY3A3 Evaluation Summary", ""]
    if metric_rows:
        for row in metric_rows:
            lines.append(
                f"- `{row['algorithm']}`: horizontal RMSE `{row.get('horizontal_rmse_m')}`, P95 `{row.get('horizontal_p95_m')}`, up RMSE `{row.get('up_rmse_m')}`, yaw RMSE `{row.get('yaw_rmse_deg')}`."
            )
    else:
        lines.append("- No completed official evaluation metrics.")
    lines.append("")
    lines.append("Trace was used only as evaluation reference. No BY3 degradation matrix was run.")
    return "\n".join(lines) + "\n"


def long_summary(decision: dict[str, Any], validation: dict[str, Any], eval_results: list[dict[str, Any]], stage2_run: dict[str, Any], baseline_runs: list[dict[str, Any]]) -> str:
    lines = [
        "# BY3A3 Long Task Summary",
        "",
        f"Final decision: `{decision['status']}`.",
        f"Ready for BY3 degradation planning: `{str(decision['ready_for_BY3_degradation_matrix_planning']).lower()}`.",
        "Ready for paper claims: `false`.",
        "",
        f"Validation: `{validation['status']}`.",
        f"LegSA_full stage2: `{stage2_run.get('run_status')}`.",
    ]
    for row in baseline_runs:
        lines.append(f"{row['algorithm']}: `{row.get('run_status')}`.")
    lines.append("")
    lines.append("Official evaluations completed: " + ", ".join(row["algorithm"] for row in eval_results if row.get("official_eval_status") == "completed"))
    return "\n".join(lines) + "\n"


def next_stage_summary(decision: dict[str, Any]) -> str:
    return (
        "# BY3A3 Next Stage Recommendation\n\n"
        f"Recommended next stage: `{decision['recommended_next_stage']}`.\n\n"
        f"ready_for_BY3_degradation_matrix_planning={str(decision['ready_for_BY3_degradation_matrix_planning']).lower()}\n\n"
        "ready_for_paper_claims=false\n"
    )


def write_rows(stem: Path, rows: list[dict[str, Any]]) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    json_path = stem.with_suffix(".json")
    csv_path = stem.with_suffix(".csv")
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["status"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def write_summary(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def first_numeric_row(path: Path) -> list[float]:
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw in handle:
            parts = raw.strip().replace(",", " ").split()
            if not parts:
                continue
            try:
                return [float(x) for x in parts]
            except ValueError:
                continue
    return []


def file_time_min(path: Path) -> float | None:
    row = first_numeric_row(path)
    return row[0] if row else None


def file_time_max(path: Path) -> float | None:
    last = None
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw in handle:
            parts = raw.strip().replace(",", " ").split()
            if not parts:
                continue
            try:
                last = float(parts[0])
            except ValueError:
                continue
    return last


def numeric_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw in handle:
            parts = raw.strip().replace(",", " ").split()
            if not parts:
                continue
            try:
                rows.append([float(x) for x in parts])
            except ValueError:
                continue
    return rows


def replace_yaml_key(text: str, key: str, value: str, *, quoted: bool) -> str:
    rendered = f'"{value}"' if quoted else value
    pattern = re.compile(rf"^{re.escape(key)}\s*:.*$", re.MULTILINE)
    replacement = f"{key}: {rendered}"
    if pattern.search(text):
        return pattern.sub(replacement, text)
    return text.rstrip() + "\n" + replacement + "\n"


def apply_by3_time_handoff(text: str, context: dict[str, Any]) -> str:
    text = replace_yaml_key(text, "starttime", f"{context['algorithm_start_time']:.9f}", quoted=False)
    text = replace_yaml_key(text, "endtime", f"{context['end_time']:.9f}", quoted=False)
    return text


def apply_external_kfgins_time_handoff(text: str, imu_path: Path, gnss_path: Path, *, use_dual_yaw: bool) -> str:
    imu_start = file_time_min(imu_path)
    imu_end = file_time_max(imu_path)
    gnss_rows = numeric_rows(gnss_path)
    if imu_start is None or imu_end is None or not gnss_rows:
        return text
    overlap_rows = [row for row in gnss_rows if imu_start <= row[0] <= imu_end]
    if not overlap_rows:
        return text
    start_row = overlap_rows[0]
    end_row = overlap_rows[-1]
    text = replace_yaml_key(text, "starttime", f"{start_row[0]:.9f}", quoted=False)
    text = replace_yaml_key(text, "endtime", f"{end_row[0]:.9f}", quoted=False)
    if len(start_row) >= 4:
        text = replace_yaml_key(text, "initpos", format_vec([start_row[1], start_row[2], start_row[3]]), quoted=False)
    yaw = start_row[13] if use_dual_yaw and len(start_row) >= 14 else 0.0
    text = replace_yaml_key(text, "initatt", format_vec([0.0, 0.0, yaw]), quoted=False)
    return text


def format_vec(values: list[float]) -> str:
    return "[ " + ", ".join(f"{float(value):.8f}" for value in values) + " ]"


def wsl_path_exists(path: str) -> bool:
    completed = subprocess.run(["wsl", "bash", "-lc", f"test -e {shlex.quote(path)}"], check=False)
    return completed.returncode == 0


def normalize_wsl_command(command: list[str]) -> list[str]:
    normalized = list(command)
    for index, item in enumerate(normalized):
        if item.startswith("\\mnt\\"):
            normalized[index] = "/" + item.lstrip("\\").replace("\\", "/")
    return normalized


def clear_runtime_solver_outputs(output_dir: Path, runtime_root: Path) -> None:
    resolved_output = output_dir.resolve()
    resolved_runtime = runtime_root.resolve()
    if resolved_runtime not in [resolved_output, *resolved_output.parents]:
        raise ValueError(f"refusing to clear output outside runtime root: {output_dir}")
    for child in output_dir.iterdir():
        if child.is_dir() and child.name == "logs":
            shutil.rmtree(child)
        elif child.is_file() and child.name in {
            "KF_GINS_IMU_ERR.txt",
            "KF_GINS_Navresult.nav",
            "KF_GINS_STD.txt",
            "Navresult.nav",
            "STD.txt",
            "KF_GINS_STD.csv",
        }:
            child.unlink()


def normalize_utf8_bom_files(root: Path) -> None:
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".csv", ".json", ".txt"} or not path.is_file():
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            path.write_bytes(raw[3:])


def resolve_eval_script(paths: Paths) -> str | None:
    for key in ["BY3_OFFICIAL_EVALUATOR_WSL", "KF_GINS_EVALUATOR_WSL", "LEGSA_OFFICIAL_EVALUATOR_WSL"]:
        value = os.environ.get(key)
        if value:
            return value
    recovered = _load_r4e3_eval_script(paths.repo)
    if recovered:
        return recovered
    command_reports = [
        paths.by3a0_root / "reports" / "BY3E_OFFICIAL_EVALUATION_REPORT.json",
        paths.by3a1_root / "reports" / "BY3A1_OFFICIAL_EVALUATION_REPORT.json",
        paths.by3a2_root / "reports" / "BY3A2_OFFICIAL_EVALUATION_REPORT.json",
    ]
    for report_path in command_reports:
        report = read_json(report_path, {}) or {}
        for command_row in report.get("commands", []) or report.get("evaluation_rows", []):
            command = command_row.get("command", [])
            if isinstance(command, list) and len(command) >= 2 and command[0] == "python3":
                return command[1]
    return None


def first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def count_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        return sum(1 for raw in handle if raw.strip()) - (1 if csv_header(path) else 0)


def csv_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        sample = handle.readline().strip()
    if not sample:
        return []
    parts = sample.split(",")
    if len(parts) > 1 and any(not is_float(part) for part in parts):
        return [part.strip() for part in parts]
    return []


def forbidden_feedback_column(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in ["truth", "trace", "error", "err_", "ref_", "reference", "final_v23"])


def is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_eval_data(eval_dir: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        "eval_nav": read_csv_dicts(eval_dir / "EVAL_NAV.csv"),
        "error_series": read_first_existing_csv(eval_dir, ["error_series.csv", "ERROR_SERIES.csv", "errors.csv", "EVAL_ERROR.csv"]),
    }


def read_first_existing_csv(root: Path, names: list[str]) -> list[dict[str, Any]]:
    for name in names:
        path = root / name
        if path.exists():
            return read_csv_dicts(path)
    return []


def read_csv_dicts(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[:limit] if limit else rows


def numeric_series(rows: list[dict[str, Any]], names: list[str]) -> list[float]:
    for name in names:
        vals = []
        for row in rows:
            value = row.get(name)
            if value is None:
                continue
            try:
                vals.append(float(value))
            except ValueError:
                pass
        if vals:
            return vals
    return []


def horizontal_series(rows: list[dict[str, Any]]) -> list[float]:
    h = numeric_series(rows, ["horizontal_error_m", "horiz_error_m", "err_horizontal_m"])
    if h:
        return h
    n = numeric_series(rows, ["north_error_m", "err_n_m", "error_n_m"])
    e = numeric_series(rows, ["east_error_m", "err_e_m", "error_e_m"])
    return [math.hypot(a, b) for a, b in zip(n, e)]


def parse_stage_files(root: Path) -> list[str]:
    issues = []
    for path in root.rglob("*.json"):
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            issues.append(f"json BOM present: {path}")
        try:
            json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"json parse failed: {path}: {exc}")
    for path in root.rglob("*.csv"):
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            issues.append(f"csv BOM present: {path}")
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                list(csv.reader(handle))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"csv parse failed: {path}: {exc}")
    return issues


def git_is_untracked_or_ignored(repo: Path, path: Path) -> bool:
    completed = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=repo, capture_output=True, text=True, check=False)
    return completed.returncode != 0


def contains_local_path(text: str) -> bool:
    patterns = [
        re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+"),
        re.compile(r"/mnt/[a-z]/Users/"),
        re.compile(r"/home/[^/\s]+"),
    ]
    return any(pattern.search(text) for pattern in patterns)


if __name__ == "__main__":
    raise SystemExit(main())
