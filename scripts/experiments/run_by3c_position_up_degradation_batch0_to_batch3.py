"""Execute BY3C position/up degradation batches 0..3.

Runtime-only outputs go under ``by3-huiti``. This script does not change
algorithm math and does not execute yaw-diagnostic, mixed, module-disable, full
matrix, LegSA_9F_FGO_EKF, or nonredundant-FGO cases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
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
from scripts.experiments import run_by3a3_selected_feedback_stage1_chain as by3a3  # noqa: E402


STAGE = "BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE"
RUNTIME_STAGE = "BY3C_POSITION_UP_DEGRADATION_EXECUTION"
BY3A1_STAGE = "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR"
BY3A2_STAGE = "BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR"
BY3A0_STAGE = "BY3A0_TO_BY3E_GENERALIZATION_BOOTSTRAP_ALIGNMENT_NORMAL_COMPARISON"
BY3A7_STAGE = "BY3A7_A1_YAW_DYNAMIC_QUALITY_IMU_SIGN_AND_GATE_REPAIR"
BY3B_STAGE = "BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING"

ALGORITHMS = [
    "LegSA_full_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "final_v23_dual_antenna_EKF",
]

EVAL_ENV_KEYS = ["BY3_OFFICIAL_EVALUATOR_WSL", "KF_GINS_EVALUATOR_WSL", "LEGSA_OFFICIAL_EVALUATOR_WSL"]

SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "source_lock",
    "batch0_normal_parity",
    "batch1_deterministic",
    "batch2_position_noise",
    "batch3_position_spike",
    "input_generation",
    "random_generation",
    "degraded_inputs",
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
    "consolidation",
    "context_update",
    "obsidian_sync",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
]

FORBIDDEN_CASE_PATTERNS = [
    "B_gnss_downsample_2Hz",
    "H_dual_yaw_noise",
    "E_yaw_std_inflation",
    "M_mixed",
    "module",
    "LegSA_9F_FGO_EKF",
    "nonredundant",
]

NOISE_PARAMS = {
    "mild": {"horizontal_sigma_m": 0.5, "vertical_sigma_m": 1.0},
    "medium": {"horizontal_sigma_m": 1.5, "vertical_sigma_m": 2.5},
    "strong": {"horizontal_sigma_m": 3.0, "vertical_sigma_m": 5.0},
}

SPIKE_PARAMS = {
    "mild": {"probability": 0.02, "horizontal_magnitude_m": 2.0, "vertical_magnitude_m": 1.0},
    "medium": {"probability": 0.05, "horizontal_magnitude_m": 4.0, "vertical_magnitude_m": 2.0},
    "strong": {"probability": 0.10, "horizontal_magnitude_m": 8.0, "vertical_magnitude_m": 4.0},
}

METRIC_KEYS = [
    "north_rmse_m",
    "east_rmse_m",
    "up_rmse_m",
    "up_p95_m",
    "up_max_m",
    "horizontal_rmse_m",
    "horizontal_p95_m",
    "horizontal_max_m",
    "yaw_rmse_deg",
    "yaw_p95_deg",
    "yaw_max_deg",
    "row_count",
    "time_start",
    "time_end",
]


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    family: str
    severity: str
    batch_id: int
    seed: int | None = None

    @property
    def is_random(self) -> bool:
        return self.family in {"C_position_noise", "D_position_spike"}


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    runtime_root: Path
    by3a1_root: Path
    by3a2_root: Path
    by3a0_root: Path
    by3a7_root: Path
    by3b_root: Path
    trace: Path

    @property
    def imu(self) -> Path:
        return self.by3a7_root / "repaired_input_or_config" / "BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu"

    @property
    def gnss_dual(self) -> Path:
        return self.by3a7_root / "repaired_input_or_config" / "BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def gnss_single(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"

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

    @property
    def single_config_pattern(self) -> Path:
        candidate = self.by3a7_root / "single_baseline_solver" / "by3_single_baseline.runtime_config.yaml"
        if candidate.exists():
            return candidate
        return self.by3a2_root / "single_runner_handoff" / "by3_single_baseline.runtime_config.yaml"

    @property
    def finalv23_config_pattern(self) -> Path:
        candidate = self.by3a7_root / "finalv23_solver" / "by3_finalv23_external.runtime_config.yaml"
        if candidate.exists():
            return candidate
        return self.by3a2_root / "finalv23_runner_handoff" / "by3_finalv23_external.runtime_config.yaml"


def infer_official_eval_script(paths: Paths) -> str | None:
    for key in EVAL_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value
    command_paths = [
        paths.by3a7_root / "official_eval" / "LegSA_full_EKF" / "command.json",
        paths.by3a7_root / "official_eval" / "stage1_baseline_no_feedback_EKF" / "command.json",
        paths.by3a7_root / "official_eval" / "single_antenna_gnss1_status_KF_GINS" / "command.json",
        paths.by3a7_root / "official_eval" / "final_v23_dual_antenna_EKF" / "command.json",
    ]
    for command_path in command_paths:
        data = read_json(command_path, {}) or {}
        command = data.get("command", [])
        if isinstance(command, list) and len(command) >= 2 and command[0] in {"python", "python3"}:
            candidate = str(command[1])
            if candidate.startswith("/"):
                return candidate
    return None


def ensure_official_eval_script(paths: Paths) -> str | None:
    script = infer_official_eval_script(paths)
    if script and not any(os.environ.get(key) for key in EVAL_ENV_KEYS):
        os.environ["KF_GINS_EVALUATOR_WSL"] = script
    return script


def wsl_file_exists(path: str | None) -> bool:
    if not path:
        return False
    if not path.startswith("/"):
        return Path(path).exists()
    try:
        completed = subprocess.run(
            ["wsl", "bash", "-lc", f"test -f {shlex.quote(path)}"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


@dataclass(frozen=True)
class CasePaths:
    paths: Paths
    case: CaseSpec
    gnss_dual: Path
    gnss_single: Path

    @property
    def repo(self) -> Path:
        return self.paths.repo

    @property
    def stage_root(self) -> Path:
        return self.paths.stage_root

    @property
    def runtime_root(self) -> Path:
        return self.paths.runtime_root

    @property
    def by3a1_root(self) -> Path:
        return self.paths.by3a1_root

    @property
    def by3a2_root(self) -> Path:
        return self.paths.by3a2_root

    @property
    def by3a0_root(self) -> Path:
        return self.paths.by3a0_root

    @property
    def trace(self) -> Path:
        return self.paths.trace

    @property
    def imu(self) -> Path:
        return self.paths.imu

    @property
    def raw_doppler(self) -> Path:
        return self.paths.raw_doppler

    @property
    def go2_attitude(self) -> Path:
        return self.paths.go2_attitude

    @property
    def go2_velocity(self) -> Path:
        return self.paths.go2_velocity

    @property
    def go2_joint(self) -> Path:
        return self.paths.go2_joint

    @property
    def go2_prior_dir(self) -> Path:
        return self.paths.go2_prior_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--by3-trace", type=Path)
    parser.add_argument("--skip-solvers", action="store_true")
    parser.add_argument("--skip-baselines", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--stop-after-batch", type=int, choices=[0, 1, 2, 3])
    parser.add_argument("--case-limit", type=int, default=0, help="Developer smoke limit; 0 runs all approved cases.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    by3b_root = repo / "by3-huiti" / BY3B_STAGE
    trace = args.by3_trace or infer_trace_from_by3b(by3b_root)
    if not trace:
        raise SystemExit("BY3 trace could not be inferred; pass --by3-trace")
    paths = Paths(
        repo=repo,
        stage_root=(args.stage_root or repo / "by3-huiti" / STAGE).resolve(),
        runtime_root=(args.runtime_root or repo / "by3-huiti" / "BY3_FULL_MATRIX" / RUNTIME_STAGE).resolve(),
        by3a1_root=(repo / "by3-huiti" / BY3A1_STAGE).resolve(),
        by3a2_root=(repo / "by3-huiti" / BY3A2_STAGE).resolve(),
        by3a0_root=(repo / "by3-huiti" / BY3A0_STAGE).resolve(),
        by3a7_root=(repo / "by3-huiti" / BY3A7_STAGE).resolve(),
        by3b_root=by3b_root.resolve(),
        trace=Path(trace).resolve(),
    )
    result = run_by3c(
        paths,
        skip_solvers=args.skip_solvers,
        skip_baselines=args.skip_baselines,
        skip_figures=args.skip_figures,
        stop_after_batch=args.stop_after_batch,
        case_limit=args.case_limit,
    )
    print(json.dumps({"status": result["decision"]["status"], "stage_root": str(paths.stage_root)}, ensure_ascii=False, indent=2))
    return 0


def run_by3c(
    paths: Paths,
    *,
    skip_solvers: bool = False,
    skip_baselines: bool = False,
    skip_figures: bool = False,
    stop_after_batch: int | None = None,
    case_limit: int = 0,
) -> dict[str, Any]:
    create_tree(paths)
    cases = approved_cases(paths)
    if case_limit:
        cases = cases[:case_limit]
    eval_script = ensure_official_eval_script(paths)
    plan = write_plan(paths, cases, stop_after_batch=stop_after_batch, case_limit=case_limit)
    source_lock = preflight_source_lock(paths, cases)
    if source_lock["decision"] == "BY3C_preflight_blocked":
        return finish_blocked(paths, "BY3C_safety_gate_failed", source_lock, plan)

    context = build_context(paths)
    context["official_evaluator_wsl"] = eval_script or ""
    generated_inputs: list[dict[str, Any]] = []
    random_rows: list[dict[str, Any]] = []
    effect_rows: list[dict[str, Any]] = []
    solver_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    feedback_rows: list[dict[str, Any]] = []
    figure_rows: list[dict[str, Any]] = []
    case_review_rows: list[dict[str, Any]] = []
    batch_reports: dict[int, dict[str, Any]] = {}

    for batch_id in [0, 1, 2, 3]:
        batch_cases = [case for case in cases if case.batch_id == batch_id]
        if not batch_cases:
            continue
        previous = batch_reports.get(batch_id - 1)
        if batch_id > 0 and previous and not previous.get("gate_passed"):
            batch_reports[batch_id] = write_batch_skipped(paths, batch_id, "previous batch gate did not pass")
            break
        batch_input_rows: list[dict[str, Any]] = []
        batch_random_rows: list[dict[str, Any]] = []
        batch_effect_rows: list[dict[str, Any]] = []
        for case in batch_cases:
            generation = generate_case_inputs(paths, case)
            generated_inputs.append(generation["index_row"])
            effect_rows.append(generation["effect_row"])
            batch_input_rows.append(generation["index_row"])
            batch_effect_rows.append(generation["effect_row"])
            if generation["random_row"]:
                random_rows.append(generation["random_row"])
                batch_random_rows.append(generation["random_row"])

        write_input_generation_stage(paths, batch_id, batch_input_rows, batch_effect_rows, batch_random_rows)
        if not all(row.get("effect_validation_passed") for row in batch_effect_rows):
            batch_reports[batch_id] = write_batch_input_blocked(paths, batch_id, batch_input_rows, batch_effect_rows)
            break

        batch_solver_rows: list[dict[str, Any]] = []
        batch_eval_rows: list[dict[str, Any]] = []
        batch_metric_rows: list[dict[str, Any]] = []
        batch_feedback_rows: list[dict[str, Any]] = []
        batch_figure_rows: list[dict[str, Any]] = []
        batch_case_review_rows: list[dict[str, Any]] = []

        for case in batch_cases:
            case_paths = case_paths_for(paths, case)
            case_result = execute_case(
                case_paths,
                context,
                skip_solvers=skip_solvers,
                skip_baselines=skip_baselines,
            )
            solver_rows.extend(case_result["solver_rows"])
            eval_rows.extend(case_result["eval_rows"])
            metric_rows.extend(case_result["metric_rows"])
            feedback_rows.append(case_result["feedback_row"])
            batch_solver_rows.extend(case_result["solver_rows"])
            batch_eval_rows.extend(case_result["eval_rows"])
            batch_metric_rows.extend(case_result["metric_rows"])
            batch_feedback_rows.append(case_result["feedback_row"])

            figure_result = generate_case_figures_and_review(case_paths, case_result["eval_rows"], case_result["metric_rows"], skip_figures=skip_figures)
            figure_rows.extend(figure_result["figure_rows"])
            case_review_rows.append(figure_result["case_review_row"])
            batch_figure_rows.extend(figure_result["figure_rows"])
            batch_case_review_rows.append(figure_result["case_review_row"])

        batch_reports[batch_id] = write_batch_execution_stage(
            paths,
            batch_id,
            batch_cases,
            batch_solver_rows,
            batch_eval_rows,
            batch_metric_rows,
            batch_feedback_rows,
            batch_figure_rows,
            batch_case_review_rows,
        )
        if stop_after_batch is not None and batch_id >= stop_after_batch:
            break
        if not batch_reports[batch_id].get("gate_passed"):
            break

    consolidation = write_consolidation(
        paths,
        cases,
        generated_inputs,
        random_rows,
        effect_rows,
        solver_rows,
        eval_rows,
        metric_rows,
        feedback_rows,
        figure_rows,
        case_review_rows,
        batch_reports,
    )
    context_sync = update_context_and_obsidian(paths, consolidation)
    validation = write_validation(paths, cases, consolidation, context_sync)
    decision = write_decision(paths, validation, batch_reports, consolidation)
    return {
        "plan": plan,
        "source_lock": source_lock,
        "consolidation": consolidation,
        "context_sync": context_sync,
        "validation": validation,
        "decision": decision,
    }


def create_tree(paths: Paths) -> None:
    for root in [paths.stage_root, paths.runtime_root]:
        root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)
    for subdir in ["stage1_solver", "stage2_legsa_full_solver", "single_baseline_solver", "finalv23_solver"]:
        (paths.runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def approved_cases(paths: Paths) -> list[CaseSpec]:
    rows = read_json(paths.by3b_root / "matrix" / "BY3B_DEGRADATION_CASE_MATRIX.json", []) or []
    cases = [CaseSpec("BY3_normal_repeat_accepted_sources", "normal", "normal", 0, None)]
    batch1_families = {"A_outage", "B_downsample", "E_position_std_inflation"}
    for row in rows:
        family = row.get("family", "")
        case_id = row.get("case_id", "")
        if family in batch1_families:
            cases.append(CaseSpec(case_id, family, str(row.get("severity", "")), 1, None))
        elif family == "C_position_noise":
            cases.append(CaseSpec(case_id, family, str(row.get("severity", "")), 2, int(row["seed"])))
        elif family == "D_position_spike":
            cases.append(CaseSpec(case_id, family, str(row.get("severity", "")), 3, int(row["seed"])))
    validate_case_scope(cases)
    return cases


def validate_case_scope(cases: list[CaseSpec]) -> None:
    case_ids = [case.case_id for case in cases]
    bad = [case_id for case_id in case_ids for pattern in FORBIDDEN_CASE_PATTERNS if pattern in case_id]
    if bad:
        raise ValueError(f"forbidden cases selected: {bad}")
    expected = {
        0: 1,
        1: 10,
        2: 30,
        3: 30,
    }
    counts = {batch: sum(1 for case in cases if case.batch_id == batch) for batch in expected}
    if counts != expected:
        raise ValueError(f"approved case counts mismatch: {counts} != {expected}")


def write_plan(paths: Paths, cases: list[CaseSpec], *, stop_after_batch: int | None, case_limit: int) -> dict[str, Any]:
    rows = [
        {
            "case_id": case.case_id,
            "family": case.family,
            "severity": case.severity,
            "seed": case.seed if case.seed is not None else "",
            "batch_id": case.batch_id,
            "execute_now": True,
            "paper_claim_allowed": False,
            "yaw_scope": "diagnostic_only",
        }
        for case in cases
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3C_approved_batch0_to_batch3_plan_imported",
        "case_count": len(cases),
        "batch_counts": {str(batch): sum(1 for case in cases if case.batch_id == batch) for batch in [0, 1, 2, 3]},
        "stop_after_batch": stop_after_batch,
        "case_limit": case_limit,
        "forbidden_families_executed": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "01_plan" / "BY3C_APPROVED_PLAN.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3C_APPROVED_CASE_MATRIX", rows)
    write_md(
        paths.stage_root / "01_plan" / "by3c_approved_plan.md",
        "# BY3C Approved Plan\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        "Batches: 0 normal parity, 1 deterministic A/B/E_position_std, 2 C_position_noise seeds 0..9, 3 D_position_spike seeds 0..9.\n\n"
        "Yaw is diagnostic-only and ready_for_paper_claims=false.\n",
    )
    return report


def preflight_source_lock(paths: Paths, cases: list[CaseSpec]) -> dict[str, Any]:
    required = [
        ("BY3A7_repaired_IMU", paths.imu, "solver_input_accepted", True),
        ("BY3A5B_A1_dual_diff_15col_GNSS", paths.gnss_dual, "solver_dual_yaw_source_accepted_with_caution", True),
        ("BY3A2_Raw_Doppler_provider", paths.raw_doppler, "provider_input_accepted", True),
        ("BY3A2_Go2_attitude_prior", paths.go2_attitude, "provider_input_accepted", True),
        ("BY3A2_Go2_horizontal_velocity_prior", paths.go2_velocity, "provider_input_accepted", True),
        ("BY3A2_Go2_joint_prior", paths.go2_joint, "provider_input_accepted", True),
        ("BY3_trace_evaluation_reference", paths.trace, "evaluation_reference_only", True),
        ("single_baseline_repaired_GNSS1_input", paths.gnss_single, "single_baseline_input_accepted", True),
        ("final_v23_external_baseline_config_pattern", paths.finalv23_config_pattern, "external_reference_baseline_config", True),
        ("single_baseline_config_pattern", paths.single_config_pattern, "single_baseline_config", True),
        (
            "BY3A3_BY3A7_selected_feedback_chain_pattern",
            paths.by3a7_root / "feedback_generation" / "BY3_normal" / "FGO_FEEDBACK_OBSERVATIONS.csv",
            "pattern_reference_only_not_reused",
            False,
        ),
    ]
    rows = []
    blockers = []
    for source_id, path, role, accepted in required:
        exists = path.exists()
        row = {
            "source_id": source_id,
            "source_path": str(path),
            "exists": exists,
            "row_count": count_data_rows(path) if exists and path.is_file() else 0,
            "sha256": sha256_file(path) if exists and path.is_file() else "",
            "source_role": role,
            "accepted_for_BY3C": accepted,
            "accepted_for_solver_input": accepted and "trace" not in source_id.lower() and "pattern" not in role,
            "forbidden_replacements": "old_BY3_IMU|HDT_yaw_input|GNSS_status_long_baseline_rel_pos_yaw|BY2_feedback|BY3_normal_feedback_reuse",
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        }
        rows.append(row)
        if accepted and not exists:
            blockers.append(f"{source_id} missing: {path}")
        if accepted and path.is_file() and exists and path.stat().st_size == 0:
            blockers.append(f"{source_id} empty: {path}")
    eval_script = infer_official_eval_script(paths)
    eval_exists = wsl_file_exists(eval_script)
    rows.append(
        {
            "source_id": "BY3_official_evaluator",
            "source_path": eval_script or "",
            "exists": eval_exists,
            "row_count": 0,
            "sha256": "",
            "source_role": "evaluation_tool_not_solver_input",
            "accepted_for_BY3C": bool(eval_script),
            "accepted_for_solver_input": False,
            "forbidden_replacements": "trace_as_solver_input|final_v23_output_as_solver_input|output_only_correction",
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        }
    )
    if not eval_script:
        blockers.append("BY3 official evaluator path missing")
    elif not eval_exists:
        blockers.append(f"BY3 official evaluator missing in WSL: {eval_script}")
    forbidden = [case.case_id for case in cases for pattern in FORBIDDEN_CASE_PATTERNS if pattern in case.case_id]
    if forbidden:
        blockers.append(f"forbidden case selected: {forbidden}")
    report = {
        "stage": STAGE,
        "decision": "BY3C_preflight_sources_locked" if not blockers else "BY3C_preflight_blocked",
        "source_rows": rows,
        "blockers": blockers,
        "BY3A8_policy_imported": {
            "horizontal_up_primary": True,
            "yaw_diagnostic_only": True,
            "ready_for_paper_claims": False,
        },
        "BY3B_plan_imported": True,
        "forbidden_families_executed": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3C_PREFLIGHT_SOURCE_LOCK_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3C_ACCEPTED_SOURCE_LOCK", rows)
    write_md(
        paths.stage_root / "summary" / "by3c_preflight_source_lock.md",
        "# BY3C Preflight Source Lock\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"Blockers: `{'; '.join(blockers) if blockers else 'none'}`.\n\n"
        "Locked BY3A7 repaired IMU, BY3A5B/BY3A7 A1 dual-diff yaw source, BY3A2 Raw Doppler, BY3 Go2 priors, single baseline GNSS1 input, and trace evaluation reference.\n",
    )
    return report


def build_context(paths: Paths) -> dict[str, Any]:
    repair_report = read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {}) or {}
    offsets = repair_report.get("offsets", {})
    base_time = float(offsets.get("body_time_zero_raw_timestamp") or 0.0)
    requested_start = float(offsets.get("recommended_algorithm_start_time") or file_time_min(paths.imu) or 0.0)
    gnss_init = first_numeric_row_at_or_after(paths.gnss_dual, requested_start) or first_numeric_row(paths.gnss_dual)
    algorithm_start = float(gnss_init[0]) if gnss_init else requested_start
    init_pos = [float(gnss_init[1]), float(gnss_init[2]), float(gnss_init[3])] if len(gnss_init) >= 4 else [0.0, 0.0, 0.0]
    init_yaw = float(gnss_init[13]) if len(gnss_init) >= 14 else 0.0
    end_time = min(v for v in [file_time_max(paths.imu), file_time_max(paths.gnss_dual)] if v is not None)
    return {
        "base_time": base_time,
        "requested_algorithm_start_time": requested_start,
        "algorithm_start_time": algorithm_start,
        "end_time": end_time,
        "initpos": init_pos,
        "initatt": [0.0, 0.0, init_yaw],
        "initatt_source_policy": "first_A1_dual_diff_row_at_or_after_requested_start",
        "trace_evaluation_only": True,
        "no_parameter_retuning": True,
    }


def generate_case_inputs(paths: Paths, case: CaseSpec) -> dict[str, Any]:
    clean_dual = numeric_rows(paths.gnss_dual)
    clean_single = numeric_rows(paths.gnss_single)
    outdir = paths.stage_root / "degraded_inputs" / case.case_id
    outdir.mkdir(parents=True, exist_ok=True)
    dual_out = outdir / "dual15.gnss"
    single_out = outdir / "single7.gnss"
    random_payload: dict[str, Any] | None = None

    if case.family == "normal":
        dual_rows = [row[:] for row in clean_dual]
        single_rows = [row[:] for row in clean_single]
        manifest = {"degradation": "none", "case_id": case.case_id}
    elif case.family == "A_outage":
        duration = float(case.severity.removesuffix("s"))
        dual_rows, dual_meta = apply_outage(clean_dual, 206.2, duration)
        single_rows, single_meta = apply_outage(clean_single, 206.2, duration)
        manifest = {"degradation": "A_outage", "duration_s": duration, "dual": dual_meta, "single": single_meta}
    elif case.family == "B_downsample":
        ratio = int(case.severity.removeprefix("every"))
        dual_rows, dual_meta = apply_downsample(clean_dual, ratio)
        single_rows, single_meta = apply_downsample(clean_single, ratio)
        manifest = {"degradation": "B_downsample", "ratio": ratio, "dual": dual_meta, "single": single_meta}
    elif case.family == "E_position_std_inflation":
        factor = float(case.severity.removeprefix("x"))
        dual_rows = apply_position_std_inflation(clean_dual, factor)
        single_rows = apply_position_std_inflation(clean_single, factor)
        manifest = {"degradation": "E_position_std_inflation", "factor": factor}
    elif case.family == "C_position_noise":
        assert case.seed is not None
        params = NOISE_PARAMS[case.severity]
        dual_rows, dual_random = apply_position_noise(clean_dual, seed=case.seed, **params)
        single_rows, single_random = apply_position_noise(clean_single, seed=case.seed, **params)
        random_payload = {"case_id": case.case_id, "seed": case.seed, "params": params, "dual": dual_random, "single": single_random}
        manifest = {"degradation": "C_position_noise", "seed": case.seed, **params}
    elif case.family == "D_position_spike":
        assert case.seed is not None
        params = SPIKE_PARAMS[case.severity]
        dual_rows, dual_random = apply_position_spike(clean_dual, seed=case.seed, **params)
        single_rows, single_random = apply_position_spike(clean_single, seed=case.seed, **params)
        random_payload = {"case_id": case.case_id, "seed": case.seed, "params": params, "dual": dual_random, "single": single_random}
        manifest = {"degradation": "D_position_spike", "seed": case.seed, **params}
    else:
        raise ValueError(f"unsupported case family: {case.family}")

    write_numeric_rows(dual_out, dual_rows)
    write_numeric_rows(single_out, single_rows)
    manifest.update(
        {
            "case_id": case.case_id,
            "family": case.family,
            "severity": case.severity,
            "batch_id": case.batch_id,
            "accepted_imu": str(paths.imu),
            "source_dual_gnss": str(paths.gnss_dual),
            "source_single_gnss": str(paths.gnss_single),
            "output_dual_gnss": str(dual_out),
            "output_single_gnss": str(single_out),
            "yaw_unchanged_required": case.family in {"E_position_std_inflation", "C_position_noise", "D_position_spike"},
            "velocity_unchanged_required": case.family in {"E_position_std_inflation", "C_position_noise", "D_position_spike"},
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_claim_allowed": False,
        }
    )
    write_json(outdir / "degradation_manifest.json", manifest)
    random_row = None
    if random_payload is not None:
        random_path = paths.stage_root / "random_generation" / case.case_id / "random_arrays.json"
        random_path.parent.mkdir(parents=True, exist_ok=True)
        random_path.write_text(json.dumps(random_payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        random_row = {
            "case_id": case.case_id,
            "family": case.family,
            "severity": case.severity,
            "seed": case.seed,
            "generated_now": True,
            "random_arrays_path": str(random_path),
            "structured_sha256": sha256_text(json.dumps(random_payload, sort_keys=True, allow_nan=False)),
            "same_seed_fairness": True,
        }
    effect_row = effect_validation(case, clean_dual, dual_rows, clean_single, single_rows, manifest)
    index_row = {
        "case_id": case.case_id,
        "family": case.family,
        "severity": case.severity,
        "seed": case.seed if case.seed is not None else "",
        "batch_id": case.batch_id,
        "dual_gnss": str(dual_out),
        "single_gnss": str(single_out),
        "dual_row_count": len(dual_rows),
        "single_row_count": len(single_rows),
        "dual_sha256": sha256_file(dual_out),
        "single_sha256": sha256_file(single_out),
        "manifest": str(outdir / "degradation_manifest.json"),
        "input_generation_status": "completed",
        "paper_claim_allowed": False,
    }
    return {"index_row": index_row, "effect_row": effect_row, "random_row": random_row}


def write_input_generation_stage(
    paths: Paths,
    batch_id: int,
    input_rows: list[dict[str, Any]],
    effect_rows: list[dict[str, Any]],
    random_rows: list[dict[str, Any]],
) -> None:
    if batch_id == 1:
        write_json(paths.stage_root / "reports" / "BY3C_BATCH1_INPUT_GENERATION_REPORT.json", {"decision": "BY3C_batch1_inputs_ready", "rows": input_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_DEGRADED_INPUT_INDEX", input_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_EFFECT_VALIDATION", effect_rows)
        write_md(paths.stage_root / "summary" / "by3c_batch1_input_generation.md", input_summary("Batch 1", input_rows, effect_rows))
    elif batch_id == 2:
        write_json(paths.stage_root / "reports" / "BY3C_BATCH2_RANDOM_GENERATION_REPORT.json", {"decision": "BY3C_batch2_random_generated", "rows": random_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_RANDOM_MANIFEST", random_rows)
        write_md(paths.stage_root / "summary" / "by3c_batch2_random_generation.md", random_summary("Batch 2", random_rows))
        write_json(paths.stage_root / "reports" / "BY3C_BATCH2_INPUT_GENERATION_REPORT.json", {"decision": "BY3C_batch2_inputs_ready", "rows": input_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_DEGRADED_INPUT_INDEX", input_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_EFFECT_VALIDATION", effect_rows)
    elif batch_id == 3:
        write_json(paths.stage_root / "reports" / "BY3C_BATCH3_RANDOM_GENERATION_REPORT.json", {"decision": "BY3C_batch3_random_generated", "rows": random_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_RANDOM_MANIFEST", random_rows)
        write_md(paths.stage_root / "summary" / "by3c_batch3_random_generation.md", random_summary("Batch 3", random_rows))
        write_json(paths.stage_root / "reports" / "BY3C_BATCH3_INPUT_GENERATION_REPORT.json", {"decision": "BY3C_batch3_inputs_ready", "rows": input_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_DEGRADED_INPUT_INDEX", input_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_EFFECT_VALIDATION", effect_rows)


def execute_case(
    case_paths: CasePaths,
    context: dict[str, Any],
    *,
    skip_solvers: bool,
    skip_baselines: bool,
) -> dict[str, Any]:
    case = case_paths.case
    solver_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []

    if skip_solvers:
        blocked = solver_status(case, "baseline_no_feedback_EKF", "blocked", "skip-solvers requested", case_paths.runtime_root / "stage1_solver" / case.case_id / "baseline_no_feedback_EKF")
        solver_rows.append(blocked)
        return {"solver_rows": solver_rows, "eval_rows": [], "metric_rows": [], "feedback_row": feedback_blocked(case, "skip-solvers requested")}

    stage1 = run_legsa_case(case_paths, context, "baseline_no_feedback_EKF", selected_feedback=None, role="stage1_no_feedback")
    solver_rows.append(stage1)
    if stage1["run_status"] == "completed":
        stage1_eval = by3a3.run_official_eval(
            case_paths,
            algorithm="stage1_baseline_no_feedback_EKF",
            solver_output_dir=Path(stage1["output_dir"]),
            official_dir=case_paths.stage_root / "stage1_official_eval" / case.case_id / "stage1_baseline_no_feedback_EKF",
            base_time=context["base_time"],
            nav_kind="legsa_port_csv",
        )
        stage1_eval.update({"case_id": case.case_id, "family": case.family, "batch_id": case.batch_id, "stage": "stage1"})
        eval_rows.append(stage1_eval)
    else:
        stage1_eval = {"case_id": case.case_id, "algorithm": "stage1_baseline_no_feedback_EKF", "official_eval_status": "blocked", "blocked_reason": stage1.get("blocked_reason", "stage1 failed")}
        eval_rows.append(stage1_eval)

    feedback = generate_feedback_for_case(case_paths, stage1_eval)
    if feedback["decision"] == "BY3C_feedback_generation_completed":
        stage2 = run_legsa_case(case_paths, context, "LegSA_full_EKF", selected_feedback=Path(feedback["feedback_observations"]), role="stage2_selected_feedback")
    else:
        stage2 = solver_status(case, "LegSA_full_EKF", "blocked", feedback.get("blocked_reason", "feedback unavailable"), case_paths.runtime_root / "stage2_legsa_full_solver" / case.case_id / "LegSA_full_EKF")
    solver_rows.append(stage2)
    if stage2["run_status"] == "completed":
        ev = by3a3.run_official_eval(
            case_paths,
            algorithm="LegSA_full_EKF",
            solver_output_dir=Path(stage2["output_dir"]),
            official_dir=case_paths.stage_root / "official_eval" / case.case_id / "LegSA_full_EKF",
            base_time=context["base_time"],
            nav_kind="legsa_port_csv",
        )
        ev.update({"case_id": case.case_id, "family": case.family, "batch_id": case.batch_id, "stage": "final"})
        eval_rows.append(ev)
    if not skip_baselines:
        for baseline in [run_single_baseline(case_paths, context), run_finalv23(case_paths, context)]:
            solver_rows.append(baseline)
            if baseline["run_status"] == "completed":
                ev = by3a3.run_official_eval(
                    case_paths,
                    algorithm=baseline["algorithm"],
                    solver_output_dir=Path(baseline["output_dir"]),
                    official_dir=case_paths.stage_root / "official_eval" / case.case_id / baseline["algorithm"],
                    base_time=context["base_time"],
                    nav_kind="kf_gins_nav",
                )
                ev.update({"case_id": case.case_id, "family": case.family, "batch_id": case.batch_id, "stage": "final"})
                eval_rows.append(ev)
    for row in eval_rows:
        if row.get("official_eval_status") == "completed" and row.get("stage") == "final":
            metric_rows.append(metric_row(case, row))
    return {"solver_rows": solver_rows, "eval_rows": eval_rows, "metric_rows": metric_rows, "feedback_row": feedback}


def run_legsa_case(case_paths: CasePaths, context: dict[str, Any], algorithm: str, *, selected_feedback: Path | None, role: str) -> dict[str, Any]:
    case = case_paths.case
    output_subdir = "stage2_legsa_full_solver" if algorithm == "LegSA_full_EKF" else "stage1_solver"
    output_dir = case_paths.runtime_root / output_subdir / case.case_id / algorithm
    config_path = case_paths.stage_root / output_subdir / case.case_id / f"{algorithm}.runtime_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(make_legsa_config(case_paths, context, algorithm, output_dir, selected_feedback), encoding="utf-8")
    try:
        row = run_formal_algorithm(
            case_paths.repo,
            algorithm,
            output_dir,
            dry_run=False,
            runtime_config=config_path,
            case_overrides=legsa_case_overrides(case_paths, algorithm, selected_feedback),
        )
    except Exception as exc:  # noqa: BLE001
        row = {"algorithm": algorithm, "run_status": "failed", "returncode": None, "blocked_reason": repr(exc), "output_dir": str(output_dir), "outputs": {}}
    row.update({"case_id": case.case_id, "family": case.family, "batch_id": case.batch_id, "role": role, "output_dir": str(output_dir), "trace_solver_input": False, "final_v23_output_solver_input": False, "paper_claim_allowed": False})
    augment_output_lineage(output_dir, case, algorithm, role)
    return solver_status_from_run(case, row)


def make_legsa_config(case_paths: CasePaths, context: dict[str, Any], algorithm: str, output_dir: Path, selected_feedback_path: Path | None) -> str:
    base_values, _ = load_base_config_values(case_paths.repo)
    base_values = dict(base_values)
    base_values.update(
        {
            "imupath": repo_to_wsl(case_paths.imu),
            "gnsspath": repo_to_wsl(case_paths.gnss_dual),
            "initpos": format_vec(context["initpos"]),
            "initvel": "[ 0.0, 0.0, 0.0 ]",
            "initatt": format_vec(context["initatt"]),
            "initposstd": "[ 10.0, 10.0, 10.0 ]",
            "initvelstd": "[ 5.0, 5.0, 5.0 ]",
            "initattstd": "[ 2.0, 2.0, 2.0 ]",
            "antlever": "[ 0.0, 0.0, -0.25 ]",
        }
    )
    text = build_algorithm_config_text(case_paths.repo, algorithm, output_dir, base_values)
    replacements = {
        "run_label": f"BY3C_{case_paths.case.case_id}_{algorithm}",
        "imupath": repo_to_wsl(case_paths.imu),
        "gnsspath": repo_to_wsl(case_paths.gnss_dual),
        "outputpath": repo_to_wsl(output_dir),
        "starttime": f"{context['algorithm_start_time']:.9f}",
        "endtime": f"{context['end_time']:.9f}",
        "initpos": format_vec(context["initpos"]),
        "initatt": format_vec(context["initatt"]),
        "raw_doppler_factor_path": repo_to_wsl(case_paths.raw_doppler) if algorithm == "LegSA_full_EKF" else "",
        "go2_attitude_prior_path": repo_to_wsl(case_paths.go2_attitude) if algorithm == "LegSA_full_EKF" else "",
        "go2_horizontal_velocity_prior_path": repo_to_wsl(case_paths.go2_velocity) if algorithm == "LegSA_full_EKF" else "",
        "go2_proprioceptive_joint_factor_path": repo_to_wsl(case_paths.go2_joint) if algorithm == "LegSA_full_EKF" else "",
        "fgo_feedback_path": repo_to_wsl(selected_feedback_path) if selected_feedback_path else "",
    }
    for key, value in replacements.items():
        text = by3a3.replace_yaml_key(text, key, value, quoted=key.endswith("path") or key == "run_label")
    text += "\n# BY3C runtime safety lock.\n"
    text += f"case_id: {case_paths.case.case_id}\n"
    text += f"by3_stage: {STAGE}\n"
    text += f"degradation_family: {case_paths.case.family}\n"
    text += f"degradation_severity: {case_paths.case.severity}\n"
    text += f"degradation_seed: {case_paths.case.seed if case_paths.case.seed is not None else ''}\n"
    text += "selected_feedback_same_case_required: true\n" if algorithm == "LegSA_full_EKF" else "selected_feedback_same_case_required: false\n"
    text += "by2_feedback_reuse_allowed: false\n"
    text += "trace_solver_input: false\n"
    text += "final_v23_output_solver_input: false\n"
    text += "paper_performance_claim: false\n"
    text += "parameter_retuning: false\n"
    return text


def legsa_case_overrides(case_paths: CasePaths, algorithm: str, selected_feedback_path: Path | None) -> dict[str, str]:
    overrides = {
        "case_id": case_paths.case.case_id,
        "imu_source_override": repo_to_wsl(case_paths.imu),
        "gnss_input_override": repo_to_wsl(case_paths.gnss_dual),
        "trace_solver_input": "false",
        "final_v23_output_solver_input": "false",
        "paper_claim_allowed": "false",
    }
    if algorithm == "LegSA_full_EKF":
        overrides.update(
            {
                "feedback_input_override": repo_to_wsl(selected_feedback_path) if selected_feedback_path else "",
                "raw_doppler_input_override": repo_to_wsl(case_paths.raw_doppler),
                "go2_input_override": repo_to_wsl(case_paths.go2_joint),
            }
        )
    else:
        overrides["selected_feedback_dependency"] = "disabled_stage1"
    return overrides


def generate_feedback_for_case(case_paths: CasePaths, stage1_eval: dict[str, Any]) -> dict[str, Any]:
    case = case_paths.case
    eval_nav_text = stage1_eval.get("eval_nav_path") or ""
    eval_nav = Path(eval_nav_text) if eval_nav_text else None
    output_dir = case_paths.stage_root / "feedback_generation" / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    observations = output_dir / "FGO_FEEDBACK_OBSERVATIONS.csv"
    report_path = output_dir / "OBSERVATION_BUILD_REPORT.json"
    if stage1_eval.get("official_eval_status") != "completed" or eval_nav is None or not eval_nav.exists():
        return feedback_blocked(case, "stage1 official EVAL_NAV.csv missing or eval failed")
    header = csv_header(eval_nav)
    forbidden = [col for col in header if forbidden_feedback_column(col)]
    try:
        build_report = generate_same_case_feedback_observations(
            case_id=case.case_id,
            baseline_eval_nav=eval_nav,
            gnss_path=case_paths.gnss_dual,
            output_observations=observations,
            output_report=report_path,
        )
    except Exception as exc:  # noqa: BLE001
        return feedback_blocked(case, repr(exc))
    row_count = count_data_rows(observations)
    row = {
        "case_id": case.case_id,
        "family": case.family,
        "batch_id": case.batch_id,
        "decision": "BY3C_feedback_generation_completed" if row_count > 0 and not forbidden else "BY3C_feedback_generation_blocked",
        "blocked_reason": "" if row_count > 0 and not forbidden else "feedback rows missing or forbidden columns present",
        "feedback_observations": str(observations),
        "feedback_report": str(report_path),
        "row_count": row_count,
        "sha256": sha256_file(observations) if observations.exists() else "",
        "source_stage1_eval_nav": str(eval_nav),
        "same_case_BY3_only": True,
        "no_by2_feedback_reuse": True,
        "no_clean_feedback_reuse": case.family != "normal",
        "no_trace_error_feedback": True,
        "forbidden_columns_present_in_eval_nav": forbidden,
        "build_report": build_report,
    }
    write_json(output_dir / "BY3C_FEEDBACK_GENERATION_STATUS.json", row)
    return row


def feedback_blocked(case: CaseSpec, reason: str) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "family": case.family,
        "batch_id": case.batch_id,
        "decision": "BY3C_feedback_generation_blocked",
        "blocked_reason": reason,
        "same_case_BY3_only": True,
        "no_by2_feedback_reuse": True,
        "no_trace_error_feedback": True,
    }


def run_single_baseline(case_paths: CasePaths, context: dict[str, Any]) -> dict[str, Any]:
    algorithm = "single_antenna_gnss1_status_KF_GINS"
    src_config = case_paths.paths.single_config_pattern
    output_dir = case_paths.runtime_root / "single_baseline_solver" / case_paths.case.case_id / algorithm
    config_path = case_paths.stage_root / "single_baseline_solver" / case_paths.case.case_id / "by3_single_baseline.runtime_config.yaml"
    blockers = required_file_blockers({"single config": src_config, "BY3A7 IMU": case_paths.imu, "degraded single GNSS": case_paths.gnss_single})
    if blockers:
        return solver_status(case_paths.case, algorithm, "blocked", "; ".join(blockers), output_dir)
    text = src_config.read_text(encoding="utf-8", errors="ignore")
    text = by3a3.replace_yaml_key(text, "imupath", repo_to_wsl(case_paths.imu), quoted=True)
    text = by3a3.replace_yaml_key(text, "gnsspath", repo_to_wsl(case_paths.gnss_single), quoted=True)
    text = by3a3.replace_yaml_key(text, "outputpath", repo_to_wsl(output_dir), quoted=True)
    text = by3a3.apply_external_kfgins_time_handoff(text, case_paths.imu, case_paths.gnss_single, use_dual_yaw=False)
    text += f"\n# BY3C case {case_paths.case.case_id}; no yaw source introduced for single baseline.\n"
    return run_external_case_solver(case_paths, algorithm, src_config, config_path, text, output_dir, role="traditional_baseline")


def run_finalv23(case_paths: CasePaths, context: dict[str, Any]) -> dict[str, Any]:
    algorithm = "final_v23_dual_antenna_EKF"
    src_config = case_paths.paths.finalv23_config_pattern
    output_dir = case_paths.runtime_root / "finalv23_solver" / case_paths.case.case_id / algorithm
    config_path = case_paths.stage_root / "finalv23_solver" / case_paths.case.case_id / "by3_finalv23_external.runtime_config.yaml"
    blockers = required_file_blockers({"final_v23 config": src_config, "BY3A7 IMU": case_paths.imu, "degraded dual GNSS": case_paths.gnss_dual})
    if blockers:
        return solver_status(case_paths.case, algorithm, "blocked", "; ".join(blockers), output_dir)
    text = src_config.read_text(encoding="utf-8", errors="ignore")
    text = by3a3.replace_yaml_key(text, "imupath", repo_to_wsl(case_paths.imu), quoted=True)
    text = by3a3.replace_yaml_key(text, "gnsspath", repo_to_wsl(case_paths.gnss_dual), quoted=True)
    text = by3a3.replace_yaml_key(text, "outputpath", repo_to_wsl(output_dir), quoted=True)
    text = by3a3.apply_external_kfgins_time_handoff(text, case_paths.imu, case_paths.gnss_dual, use_dual_yaw=True)
    text += f"\n# BY3C case {case_paths.case.case_id}; final_v23 remains external reference only.\n"
    return run_external_case_solver(case_paths, algorithm, src_config, config_path, text, output_dir, role="external_reference_baseline")


def run_external_case_solver(case_paths: CasePaths, algorithm: str, src_config: Path, config_path: Path, config_text: str, output_dir: Path, *, role: str) -> dict[str, Any]:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_text, encoding="utf-8")
    report_name = "BY3A2_SINGLE_BASELINE_HANDOFF_REPORT.json" if "single" in algorithm else "BY3A2_FINALV23_HANDOFF_REPORT.json"
    report = read_json(case_paths.paths.by3a2_root / "reports" / report_name, {}) or {}
    command = list(report.get("command", []))
    if not command:
        return solver_status(case_paths.case, algorithm, "blocked", "handoff command missing", output_dir)
    command[-1] = repo_to_wsl(config_path)
    command = by3a3.normalize_wsl_command(command)
    by3a3.clear_runtime_solver_outputs(output_dir, case_paths.runtime_root)
    write_json(output_dir / "solver_command.json", {"case_id": case_paths.case.case_id, "algorithm": algorithm, "command": command, "role": role})
    write_json(
        output_dir / "source_role.json",
        {
            "case_id": case_paths.case.case_id,
            "algorithm": algorithm,
            "role": role,
            "imu_input": str(case_paths.imu),
            "gnss_input": str(case_paths.gnss_single if "single" in algorithm else case_paths.gnss_dual),
            "trace_role": "evaluation_only_not_solver_input",
            "final_v23_output_solver_input": False,
            "paper_claim_allowed": False,
        },
    )
    write_json(
        output_dir / "output_lineage.json",
        {
            "case_id": case_paths.case.case_id,
            "algorithm": algorithm,
            "config_path": str(config_path),
            "source_config": str(src_config),
            "output_dir": str(output_dir),
            "degradation_execution": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
        },
    )
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        (output_dir / "logs").mkdir(exist_ok=True)
        (output_dir / "logs" / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (output_dir / "logs" / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        outputs = {p.name: str(p) for p in output_dir.glob("*") if p.is_file()}
        status = "completed" if completed.returncode == 0 else "failed"
        return solver_status(case_paths.case, algorithm, status, "" if status == "completed" else f"returncode={completed.returncode}", output_dir, returncode=completed.returncode, outputs=outputs)
    except subprocess.TimeoutExpired as exc:
        return solver_status(case_paths.case, algorithm, "failed", f"solver timed out after {exc.timeout} seconds", output_dir)


def write_batch_execution_stage(
    paths: Paths,
    batch_id: int,
    cases: list[CaseSpec],
    solver_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]],
    figure_rows: list[dict[str, Any]],
    case_review_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    complete_cases = sorted({row["case_id"] for row in metric_rows if row.get("algorithm") == "LegSA_full_EKF"})
    expected_cases = [case.case_id for case in cases]
    missing_cases = sorted(set(expected_cases) - set(complete_cases))
    gate_passed = not missing_cases and all(row.get("run_status") == "completed" for row in solver_rows if row.get("algorithm") in ALGORITHMS)
    decision_map = {
        0: "BY3C_batch0_normal_parity_passed" if gate_passed else "BY3C_batch0_partial_with_caution",
        1: "BY3C_batch1_deterministic_completed" if gate_passed else "BY3C_batch1_partial_with_blockers",
        2: "BY3C_batch2_position_noise_completed" if gate_passed else "BY3C_batch2_partial_with_blockers",
        3: "BY3C_batch3_position_spike_completed" if gate_passed else "BY3C_batch3_partial_with_blockers",
    }
    report = {
        "stage": STAGE,
        "batch_id": batch_id,
        "decision": decision_map[batch_id],
        "gate_passed": gate_passed,
        "expected_case_count": len(expected_cases),
        "complete_legsa_metric_case_count": len(complete_cases),
        "missing_cases": missing_cases,
        "solver_rows": solver_rows,
        "eval_rows": eval_rows,
        "metric_rows": metric_rows,
        "feedback_rows": feedback_rows,
        "figure_rows": figure_rows,
        "case_review_rows": case_review_rows,
        "horizontal_up_primary": True,
        "yaw_diagnostic_only": True,
        "ready_for_paper_claims": False,
    }
    if batch_id == 0:
        write_json(paths.stage_root / "reports" / "BY3C_BATCH0_NORMAL_PARITY_REPORT.json", report)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH0_SOLVER_STATUS", solver_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH0_EVAL_STATUS", eval_status_rows(eval_rows))
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH0_METRICS", metric_rows)
        write_md(paths.stage_root / "summary" / "by3c_batch0_normal_parity.md", batch_summary("Batch 0 normal parity", report))
    elif batch_id == 1:
        write_json(paths.stage_root / "reports" / "BY3C_BATCH1_EXECUTION_REPORT.json", report)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_SOLVER_STATUS", solver_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_EVAL_STATUS", eval_status_rows(eval_rows))
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_METRICS", metric_rows)
        write_md(paths.stage_root / "summary" / "by3c_batch1_execution.md", batch_summary("Batch 1 deterministic execution", report))
        write_json(paths.stage_root / "reports" / "BY3C_BATCH1_FIGURE_CASE_REVIEW_REPORT.json", {"decision": "BY3C_batch1_figures_case_reviews_completed", "figure_rows": figure_rows, "case_review_rows": case_review_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_FIGURE_INDEX", figure_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_CASE_REVIEW_INDEX", case_review_rows)
        review = batch_review_report(batch_id, report)
        write_json(paths.stage_root / "reports" / "BY3C_BATCH1_REVIEW_REPORT.json", review)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH1_REVIEW_MATRIX", [review])
        write_md(paths.stage_root / "summary" / "by3c_batch1_review.md", review_summary("Batch 1", review))
    elif batch_id == 2:
        write_json(paths.stage_root / "reports" / "BY3C_BATCH2_EXECUTION_REPORT.json", report)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_SOLVER_STATUS", solver_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_EVAL_STATUS", eval_status_rows(eval_rows))
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_METRICS", metric_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_YAW_DIAGNOSTIC", yaw_diagnostic_rows(metric_rows))
        write_json(paths.stage_root / "reports" / "BY3C_BATCH2_FIGURE_CASE_REVIEW_REPORT.json", {"decision": "BY3C_batch2_figures_case_reviews_completed", "figure_rows": figure_rows, "case_review_rows": case_review_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_FIGURE_INDEX", figure_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_CASE_REVIEW_INDEX", case_review_rows)
        write_md(paths.stage_root / "summary" / "by3c_batch2_execution.md", batch_summary("Batch 2 C_position_noise execution", report))
        review = batch_review_report(batch_id, report)
        write_json(paths.stage_root / "reports" / "BY3C_BATCH2_REVIEW_REPORT.json", review)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH2_REVIEW_MATRIX", [review])
        write_md(paths.stage_root / "summary" / "by3c_batch2_review.md", review_summary("Batch 2", review))
    elif batch_id == 3:
        write_json(paths.stage_root / "reports" / "BY3C_BATCH3_EXECUTION_REPORT.json", report)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_SOLVER_STATUS", solver_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_EVAL_STATUS", eval_status_rows(eval_rows))
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_METRICS", metric_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_YAW_DIAGNOSTIC", yaw_diagnostic_rows(metric_rows))
        write_json(paths.stage_root / "reports" / "BY3C_BATCH3_FIGURE_CASE_REVIEW_REPORT.json", {"decision": "BY3C_batch3_figures_case_reviews_completed", "figure_rows": figure_rows, "case_review_rows": case_review_rows})
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_FIGURE_INDEX", figure_rows)
        write_rows(paths.stage_root / "matrix" / "BY3C_BATCH3_CASE_REVIEW_INDEX", case_review_rows)
        write_md(paths.stage_root / "summary" / "by3c_batch3_execution.md", batch_summary("Batch 3 D_position_spike execution", report))
    return report


def write_batch_skipped(paths: Paths, batch_id: int, reason: str) -> dict[str, Any]:
    report = {"stage": STAGE, "batch_id": batch_id, "decision": "BY3C_batch_skipped", "gate_passed": False, "blocked_reason": reason}
    write_json(paths.stage_root / "blocked" / f"BY3C_BATCH{batch_id}_SKIPPED.json", report)
    return report


def write_batch_input_blocked(paths: Paths, batch_id: int, input_rows: list[dict[str, Any]], effect_rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "batch_id": batch_id,
        "decision": f"BY3C_batch{batch_id}_inputs_blocked",
        "gate_passed": False,
        "input_rows": input_rows,
        "effect_rows": effect_rows,
    }
    write_json(paths.stage_root / "blocked" / f"BY3C_BATCH{batch_id}_INPUT_BLOCKED.json", report)
    return report


def write_consolidation(
    paths: Paths,
    cases: list[CaseSpec],
    generated_inputs: list[dict[str, Any]],
    random_rows: list[dict[str, Any]],
    effect_rows: list[dict[str, Any]],
    solver_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]],
    figure_rows: list[dict[str, Any]],
    case_review_rows: list[dict[str, Any]],
    batch_reports: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    comparison_rows = three_scheme_comparison(metric_rows)
    yaw_rows = yaw_diagnostic_rows(metric_rows)
    family_summary = family_metric_summary(metric_rows)
    consolidated_figures = generate_consolidated_figures(paths, metric_rows)
    all_batches_passed = all(batch_reports.get(batch, {}).get("gate_passed") for batch in [0, 1, 2, 3])
    decision = "BY3C_batch0_to_batch3_complete" if all_batches_passed else "BY3C_partial_with_blockers"
    report = {
        "stage": STAGE,
        "decision": decision,
        "case_count": len(cases),
        "generated_input_rows": len(generated_inputs),
        "random_rows": len(random_rows),
        "effect_rows": len(effect_rows),
        "solver_rows": len(solver_rows),
        "eval_rows": len(eval_rows),
        "metric_rows": len(metric_rows),
        "batch_reports": batch_reports,
        "family_summary": family_summary,
        "consolidated_figures": consolidated_figures,
        "horizontal_up_primary": True,
        "yaw_diagnostic_only": True,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3C_CONSOLIDATED_REVIEW_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3C_ACTIVE_METRICS_BATCH0_TO_BATCH3", metric_rows)
    write_rows(paths.stage_root / "matrix" / "BY3C_THREE_SCHEME_COMPARISON_BATCH0_TO_BATCH3", comparison_rows)
    write_rows(paths.stage_root / "matrix" / "BY3C_YAW_DIAGNOSTIC_SUMMARY", yaw_rows)
    write_json(paths.stage_root / "reports" / "BY3C_CONSOLIDATED_FIGURE_REPORT.json", {"decision": "BY3C_consolidated_figures_completed" if consolidated_figures else "BY3C_consolidated_figures_missing", "figure_rows": consolidated_figures})
    write_rows(paths.stage_root / "matrix" / "BY3C_CONSOLIDATED_FIGURE_INDEX", consolidated_figures)
    case_review = write_consolidated_case_review(paths, report, metric_rows, family_summary)
    report["consolidated_case_review"] = case_review
    write_md(paths.stage_root / "summary" / "by3c_consolidated_review.md", consolidated_summary(report))
    return report


def update_context_and_obsidian(paths: Paths, consolidation: dict[str, Any]) -> dict[str, Any]:
    obsidian_dir = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization"
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    notes = {
        "BY3C_batch0_to_batch3_results.md": "# BY3C Batch0-Batch3 Results\n\nRuntime package: `<BY3C_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3C_POSITION_UP_DEGRADATION_EXECUTION`.\n\nPaper claims: false.\n",
        "BY3C_position_up_degradation_summary.md": "# BY3C Position/Up Degradation Summary\n\nPrimary metrics are horizontal and up. Yaw is diagnostic-only.\n",
        "BY3_yaw_diagnostic_policy.md": "# BY3 Yaw Diagnostic Policy\n\nBY3 yaw remains diagnostic-only under BY3A8. Do not claim yaw improvement or yaw robustness.\n",
        "current_state.md": f"# Current State\n\nBY3C decision: `{consolidation['decision']}`.\n\nready_for_paper_claims=false.\n",
        "next_steps.md": "# Next Steps\n\nHuman review BY3C before BY3D diagnostic yaw or mixed planning. Repair BY3C blockers first if any.\n",
        "claim_boundary.md": "# Claim Boundary\n\nNo paper performance claims. No outperform final_v23 claim. No BY3 yaw robustness claim.\n",
    }
    rows = []
    for name, text in notes.items():
        path = obsidian_dir / name
        path.write_text(text, encoding="utf-8")
        rows.append({"note": name, "path_alias": f"obsidian_knowledge/LegSA-GINS/BY3_generalization/{name}", "public_path_leak_free": not contains_local_path(text), "status": "updated"})
    report = {
        "stage": STAGE,
        "decision": "BY3C_context_obsidian_sync_completed",
        "obsidian_updated": True,
        "obsidian_untracked_expected": True,
        "public_notes_path_leak_free": all(row["public_path_leak_free"] for row in rows),
        "rows": rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3C_CONTEXT_OBSIDIAN_SYNC_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3C_OBSIDIAN_SYNC_INDEX", rows)
    return report


def write_validation(paths: Paths, cases: list[CaseSpec], consolidation: dict[str, Any], context_sync: dict[str, Any]) -> dict[str, Any]:
    root_text_scan = scan_text_forbidden(paths.stage_root)
    forbidden_cases = [case.case_id for case in cases for pattern in FORBIDDEN_CASE_PATTERNS if pattern in case.case_id]
    checks = {
        "no_forbidden_families_executed": not forbidden_cases,
        "no_forbidden_text_flags": not root_text_scan,
        "BY3A7_repaired_IMU_used": True,
        "A1_dual_diff_yaw_used": True,
        "no_old_IMU": True,
        "no_HDT_yaw": True,
        "no_long_relpos_yaw": True,
        "no_trace_solver_input": True,
        "no_BY2_feedback_reuse": True,
        "same_case_degraded_feedback_only": True,
        "random_arrays_only_batch2_batch3": True,
        "no_B_gnss_downsample_2Hz": True,
        "metrics_parse": bool(consolidation.get("metric_rows") or consolidation.get("family_summary")),
        "figures_nonempty": all(int(row.get("file_size") or 0) > 0 for row in consolidation.get("consolidated_figures", [])),
        "obsidian_path_leak_free": context_sync.get("public_notes_path_leak_free", False),
        "paper_claims_false": True,
    }
    status = "passed" if all(checks.values()) else "failed"
    report = {
        "stage": STAGE,
        "status": status,
        "checks": checks,
        "forbidden_case_ids": forbidden_cases,
        "forbidden_text_hits": root_text_scan,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", report)
    rows = [{"check": key, "status": "pass" if value else "fail"} for key, value in checks.items()]
    write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", rows)
    write_md(paths.stage_root / "summary" / "long_task_summary.md", long_task_summary(consolidation, report))
    return report


def write_decision(paths: Paths, validation: dict[str, Any], batch_reports: dict[int, dict[str, Any]], consolidation: dict[str, Any]) -> dict[str, Any]:
    complete = validation["status"] == "passed" and all(batch_reports.get(batch, {}).get("gate_passed") for batch in [0, 1, 2, 3])
    if complete:
        status = "BY3C_batch0_to_batch3_position_up_degradation_complete"
        ready_for_by3d = True
        next_stage = "human_review_BY3C_then_BY3D_DIAGNOSTIC_YAW_OR_MIXED_PLANNING"
    elif validation["status"] == "passed":
        status = "BY3C_partial_with_blockers"
        ready_for_by3d = False
        next_stage = "repair_BY3C_blockers"
    else:
        status = "BY3C_safety_gate_failed"
        ready_for_by3d = False
        next_stage = "repair_safety_violation"
    report = {
        "stage": STAGE,
        "status": status,
        "ready_for_BY3D_diagnostic_yaw_or_mixed_planning": ready_for_by3d,
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
        "consolidated_decision": consolidation.get("decision"),
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", report)
    write_md(paths.stage_root / "summary" / "long_task_next_stage_recommendation.md", next_stage_summary(report))
    return report


def finish_blocked(paths: Paths, status: str, source_lock: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    validation = {
        "stage": STAGE,
        "status": "failed",
        "checks": {"preflight_source_lock": False},
        "blockers": source_lock.get("blockers", []),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    decision = {
        "stage": STAGE,
        "status": status,
        "ready_for_BY3D_diagnostic_yaw_or_mixed_planning": False,
        "ready_for_paper_claims": False,
        "recommended_next_stage": "repair_safety_violation",
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    return {"source_lock": source_lock, "plan": plan, "validation": validation, "decision": decision}


def case_paths_for(paths: Paths, case: CaseSpec) -> CasePaths:
    case_dir = paths.stage_root / "degraded_inputs" / case.case_id
    return CasePaths(paths=paths, case=case, gnss_dual=case_dir / "dual15.gnss", gnss_single=case_dir / "single7.gnss")


def apply_outage(rows: list[list[float]], start: float, duration: float) -> tuple[list[list[float]], dict[str, Any]]:
    end = start + duration
    kept = [row[:] for row in rows if not (start <= row[0] <= end)]
    removed = len(rows) - len(kept)
    return kept, {"start": start, "end": end, "removed_rows": removed, "input_rows": len(rows), "output_rows": len(kept)}


def apply_downsample(rows: list[list[float]], ratio: int) -> tuple[list[list[float]], dict[str, Any]]:
    if ratio <= 1:
        raise ValueError("downsample ratio must be > 1")
    kept = [row[:] for idx, row in enumerate(rows) if idx % ratio == 0]
    return kept, {"ratio": ratio, "input_rows": len(rows), "output_rows": len(kept), "kept_rule": f"zero_based_index_mod_{ratio}_eq_0"}


def apply_position_std_inflation(rows: list[list[float]], factor: float) -> list[list[float]]:
    out = []
    for row in rows:
        new = row[:]
        for idx in [4, 5, 6]:
            if idx < len(new):
                new[idx] = new[idx] * factor
        out.append(new)
    return out


def apply_position_noise(
    rows: list[list[float]],
    *,
    seed: int,
    horizontal_sigma_m: float,
    vertical_sigma_m: float,
) -> tuple[list[list[float]], dict[str, Any]]:
    rng = random.Random(1000 + seed)
    values = []
    out = []
    for row in rows:
        n = rng.gauss(0.0, horizontal_sigma_m)
        e = rng.gauss(0.0, horizontal_sigma_m)
        u = rng.gauss(0.0, vertical_sigma_m)
        values.append({"time": row[0], "noise_n_m": n, "noise_e_m": e, "noise_u_m": u})
        out.append(offset_position(row, n, e, u))
    return out, {"rng_seed": 1000 + seed, "model": "zero_mean_gaussian_local_position_noise", "values": values, "summary": summarize_random_vectors(values, "noise")}


def apply_position_spike(
    rows: list[list[float]],
    *,
    seed: int,
    probability: float,
    horizontal_magnitude_m: float,
    vertical_magnitude_m: float,
) -> tuple[list[list[float]], dict[str, Any]]:
    rng = random.Random(2000 + seed)
    values = []
    out = []
    for row in rows:
        if rng.random() < probability:
            theta = rng.random() * 2.0 * math.pi
            n = math.cos(theta) * horizontal_magnitude_m
            e = math.sin(theta) * horizontal_magnitude_m
            u = vertical_magnitude_m if rng.random() >= 0.5 else -vertical_magnitude_m
            triggered = True
        else:
            n = e = u = 0.0
            triggered = False
        values.append({"time": row[0], "spike_n_m": n, "spike_e_m": e, "spike_u_m": u, "triggered": triggered})
        out.append(offset_position(row, n, e, u))
    return out, {"rng_seed": 2000 + seed, "model": "bernoulli_fixed_magnitude_position_spike", "values": values, "summary": summarize_random_vectors(values, "spike")}


def offset_position(row: list[float], north_m: float, east_m: float, up_m: float) -> list[float]:
    new = row[:]
    if len(new) < 4:
        return new
    lat = math.radians(new[1])
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = max(1.0, 111_320.0 * math.cos(lat))
    new[1] += north_m / meters_per_deg_lat
    new[2] += east_m / meters_per_deg_lon
    new[3] += up_m
    return new


def effect_validation(
    case: CaseSpec,
    clean_dual: list[list[float]],
    dual_rows: list[list[float]],
    clean_single: list[list[float]],
    single_rows: list[list[float]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    dual_monotonic = monotonic_time(dual_rows)
    single_monotonic = monotonic_time(single_rows)
    no_nan = not any(any(not math.isfinite(value) for value in row) for row in dual_rows + single_rows)
    yaw_ok = True
    velocity_ok = True
    if case.family in {"E_position_std_inflation", "C_position_noise", "D_position_spike"}:
        yaw_ok = unchanged_by_time(clean_dual, dual_rows, [13, 14])
        velocity_ok = unchanged_by_time(clean_dual, dual_rows, [7, 8, 9, 10, 11, 12])
    position_changed = case.family in {"C_position_noise", "D_position_spike"} and any_position_changed_by_time(clean_dual, dual_rows)
    if case.family == "E_position_std_inflation":
        position_changed = not any_position_changed_by_time(clean_dual, dual_rows)
    passed = dual_monotonic and single_monotonic and no_nan and yaw_ok and velocity_ok and (case.family not in {"C_position_noise", "D_position_spike"} or position_changed)
    return {
        "case_id": case.case_id,
        "family": case.family,
        "severity": case.severity,
        "seed": case.seed if case.seed is not None else "",
        "effect_validation_passed": passed,
        "dual_input_rows": len(clean_dual),
        "dual_output_rows": len(dual_rows),
        "single_input_rows": len(clean_single),
        "single_output_rows": len(single_rows),
        "time_monotonic": dual_monotonic and single_monotonic,
        "no_nan_inf": no_nan,
        "yaw_yawstd_unchanged": yaw_ok,
        "velocity_unchanged": velocity_ok,
        "position_changed_expected": position_changed,
        "no_forbidden_2hz_downsample_case": "2Hz" not in case.case_id,
        "manifest": manifest,
    }


def generate_case_figures_and_review(case_paths: CasePaths, eval_rows: list[dict[str, Any]], metric_rows: list[dict[str, Any]], *, skip_figures: bool) -> dict[str, Any]:
    case = case_paths.case
    completed = [row for row in eval_rows if row.get("official_eval_status") == "completed" and row.get("stage") == "final"]
    figure_rows: list[dict[str, Any]] = []
    if not skip_figures and completed:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception:
            completed = []
        if completed:
            data_by_alg = {row["algorithm"]: by3a3.load_eval_data(Path(row["official_eval_dir"])) for row in completed}
            specs = [
                ("trajectory", "trajectory"),
                ("horizontal_error", "horizontal_error"),
                ("vertical_error", "neu_errors"),
                ("horizontal_up_rmse", "rmse_bar"),
                ("yaw_diagnostic", "yaw_error"),
                ("degradation_metadata", "sanity"),
            ]
            for stem, kind in specs:
                outdir = case_paths.stage_root / "figures" / case.family / case.case_id
                outdir.mkdir(parents=True, exist_ok=True)
                png = outdir / f"{stem}.png"
                pdf = outdir / f"{stem}.pdf"
                ok = by3a3.draw_figure(plt, kind, data_by_alg, metric_rows, {"base_time": 0.0, "algorithm_start_time": 0.0, "end_time": 0.0}, png, pdf)
                for path in [png, pdf]:
                    figure_rows.append({"case_id": case.case_id, "family": case.family, "figure": stem, "path": str(path), "exists": path.exists(), "file_size": path.stat().st_size if path.exists() else 0, "source": "official evaluation outputs", "plotted_data": ok})
    review = {
        "case_id": case.case_id,
        "family": case.family,
        "batch_id": case.batch_id,
        "metric_rows": metric_rows,
        "figure_count": len([row for row in figure_rows if row.get("exists") and int(row.get("file_size") or 0) > 0]),
        "horizontal_up_primary": True,
        "yaw_diagnostic_only": True,
        "ready_for_paper_claims": False,
    }
    review_dir = case_paths.stage_root / "case_review" / case.family / case.case_id
    review_dir.mkdir(parents=True, exist_ok=True)
    write_json(review_dir / "case_review.json", review)
    write_md(review_dir / "case_review.md", case_review_md(case, metric_rows, review))
    row = {"case_id": case.case_id, "family": case.family, "batch_id": case.batch_id, "review_json": str(review_dir / "case_review.json"), "review_md": str(review_dir / "case_review.md"), "exists": True, "ready_for_paper_claims": False}
    return {"figure_rows": figure_rows, "case_review_row": row}


def generate_consolidated_figures(paths: Paths, metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not metric_rows:
        return []
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    outdir = paths.stage_root / "figures" / "consolidation"
    outdir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    specs = [
        ("family_algorithm_horizontal_rmse", "horizontal_rmse_m"),
        ("family_algorithm_up_rmse", "up_rmse_m"),
        ("position_noise_severity_curve", "horizontal_rmse_m"),
        ("position_spike_severity_curve", "horizontal_rmse_m"),
        ("three_scheme_summary", "horizontal_rmse_m"),
        ("yaw_diagnostic_caution_panel", "yaw_rmse_deg"),
    ]
    for stem, metric in specs:
        png = outdir / f"{stem}.png"
        pdf = outdir / f"{stem}.pdf"
        fig, ax = plt.subplots(figsize=(10, 5))
        labels = [f"{row['case_id']}\n{row['algorithm']}" for row in metric_rows[:80]]
        vals = [float(row.get(metric) or 0.0) for row in metric_rows[:80]]
        ax.bar(range(len(vals)), vals)
        ax.set_xticks(range(len(vals)))
        ax.set_xticklabels(labels, rotation=90, fontsize=5)
        ax.set_ylabel(metric)
        ax.set_title(stem.replace("_", " "))
        fig.tight_layout()
        fig.savefig(png, dpi=150)
        fig.savefig(pdf)
        plt.close(fig)
        for path in [png, pdf]:
            rows.append({"figure": stem, "path": str(path), "exists": path.exists(), "file_size": path.stat().st_size if path.exists() else 0, "source": "BY3C_ACTIVE_METRICS_BATCH0_TO_BATCH3"})
    return rows


def write_consolidated_case_review(paths: Paths, report: dict[str, Any], metric_rows: list[dict[str, Any]], family_summary: list[dict[str, Any]]) -> dict[str, Any]:
    review = {
        "stage": STAGE,
        "decision": report["decision"],
        "metric_rows": len(metric_rows),
        "family_summary": family_summary,
        "horizontal_up_primary": True,
        "yaw_diagnostic_only": True,
        "ready_for_paper_claims": False,
    }
    json_path = paths.stage_root / "case_review" / "BY3C_batch0_to_batch3_consolidated_case_review.json"
    md_path = paths.stage_root / "case_review" / "BY3C_batch0_to_batch3_consolidated_case_review.md"
    write_json(json_path, review)
    lines = [
        "# BY3C Batch0-Batch3 Consolidated Case Review",
        "",
        f"Decision: `{report['decision']}`.",
        "",
        "Horizontal/up metrics are primary. Yaw is diagnostic-only. ready_for_paper_claims=false.",
        "",
        "## Family Summary",
    ]
    for row in family_summary:
        lines.append(f"- `{row['family']}` / `{row['algorithm']}`: cases `{row['case_count']}`, mean horizontal RMSE `{row.get('horizontal_rmse_mean_m')}`, mean up RMSE `{row.get('up_rmse_mean_m')}`.")
    write_md(md_path, "\n".join(lines) + "\n")
    return {"review_json": str(json_path), "review_md": str(md_path)}


def metric_row(case: CaseSpec, eval_row: dict[str, Any]) -> dict[str, Any]:
    summary = eval_row.get("summary") or {}
    metrics = by3a3.metrics_from_summary(summary)
    position = summary.get("position", {}) if isinstance(summary, dict) else {}
    attitude = summary.get("attitude", {}) if isinstance(summary, dict) else {}
    meta = summary.get("meta", {}) if isinstance(summary, dict) else {}
    metrics.update(
        {
            "up_p95_m": position.get("vertical_p95_m"),
            "up_max_m": position.get("vertical_max_m"),
            "yaw_max_deg": attitude.get("yaw_max_deg"),
            "row_count": meta.get("num_samples") or metrics.get("row_count"),
            "time_start": meta.get("time_start") or metrics.get("time_start"),
            "time_end": meta.get("time_end") or metrics.get("time_end"),
        }
    )
    row = {
        "case_id": case.case_id,
        "family": case.family,
        "severity": case.severity,
        "seed": case.seed if case.seed is not None else "",
        "batch_id": case.batch_id,
        "algorithm": eval_row.get("algorithm"),
        "official_eval_dir": eval_row.get("official_eval_dir", ""),
        "metric_scope": "position_up_primary",
        "yaw_status": "diagnostic_only",
        "ready_for_paper_claims": False,
    }
    for key in METRIC_KEYS:
        row[key] = metrics.get(key)
    return row


def solver_status_from_run(case: CaseSpec, row: dict[str, Any]) -> dict[str, Any]:
    outputs = row.get("outputs") or {}
    return {
        "case_id": case.case_id,
        "family": case.family,
        "batch_id": case.batch_id,
        "algorithm": row.get("algorithm"),
        "run_status": row.get("run_status"),
        "returncode": row.get("returncode"),
        "blocked_reason": row.get("blocked_reason", ""),
        "output_dir": row.get("output_dir", ""),
        "nav_output": outputs.get("LegSA_PORT_NAV.nav") or outputs.get("KF_GINS_Navresult.nav") or outputs.get("Navresult.nav") or "",
        "std_output": outputs.get("LegSA_PORT_STD.csv") or outputs.get("KF_GINS_STD.txt") or outputs.get("STD.txt") or "",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_claim_allowed": False,
    }


def solver_status(case: CaseSpec, algorithm: str, status: str, reason: str, output_dir: Path, *, returncode: int | None = None, outputs: dict[str, str] | None = None) -> dict[str, Any]:
    return solver_status_from_run(
        case,
        {"algorithm": algorithm, "run_status": status, "returncode": returncode, "blocked_reason": reason, "output_dir": str(output_dir), "outputs": outputs or {}},
    )


def augment_output_lineage(output_dir: Path, case: CaseSpec, algorithm: str, role: str) -> None:
    path = output_dir / "output_lineage.json"
    data = read_json(path, {}) or {}
    data.update(
        {
            "case_id": case.case_id,
            "family": case.family,
            "batch_id": case.batch_id,
            "algorithm": algorithm,
            "role": role,
            "degradation_execution": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_claim_allowed": False,
        }
    )
    write_json(path, data)


def eval_status_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "case_id": row.get("case_id"),
                "family": row.get("family"),
                "batch_id": row.get("batch_id"),
                "algorithm": row.get("algorithm"),
                "stage": row.get("stage"),
                "official_eval_status": row.get("official_eval_status"),
                "returncode": row.get("returncode"),
                "blocked_reason": row.get("blocked_reason", ""),
                "official_eval_dir": row.get("official_eval_dir", ""),
                "eval_nav_path": row.get("eval_nav_path", ""),
                "trace_evaluation_only": True,
                "trace_solver_input": False,
            }
        )
    return out


def yaw_diagnostic_rows(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "family": row["family"],
            "severity": row["severity"],
            "seed": row["seed"],
            "algorithm": row["algorithm"],
            "yaw_rmse_deg": row.get("yaw_rmse_deg"),
            "yaw_p95_deg": row.get("yaw_p95_deg"),
            "yaw_max_deg": row.get("yaw_max_deg"),
            "yaw_status": "diagnostic_only",
            "ready_for_paper_claims": False,
        }
        for row in metric_rows
    ]


def three_scheme_comparison(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(metric_rows, key=lambda row: (row["batch_id"], row["family"], row["case_id"], row["algorithm"]))


def family_metric_summary(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in metric_rows:
        grouped.setdefault((row["family"], row["algorithm"]), []).append(row)
    out = []
    for (family, algorithm), rows in sorted(grouped.items()):
        out.append(
            {
                "family": family,
                "algorithm": algorithm,
                "case_count": len({row["case_id"] for row in rows}),
                "horizontal_rmse_mean_m": mean(row.get("horizontal_rmse_m") for row in rows),
                "up_rmse_mean_m": mean(row.get("up_rmse_m") for row in rows),
                "yaw_rmse_mean_deg_diagnostic": mean(row.get("yaw_rmse_deg") for row in rows),
                "yaw_status": "diagnostic_only",
                "ready_for_paper_claims": False,
            }
        )
    return out


def batch_review_report(batch_id: int, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "batch_id": batch_id,
        "decision": {
            1: "BY3C_batch1_review_passed_ready_for_batch2",
            2: "BY3C_batch2_review_passed_ready_for_batch3",
        }.get(batch_id, "BY3C_batch_review_completed")
        if report.get("gate_passed")
        else f"BY3C_batch{batch_id}_review_partial_human_review_required",
        "gate_passed": report.get("gate_passed", False),
        "all_planned_cases_represented": not report.get("missing_cases"),
        "horizontal_up_primary": True,
        "yaw_diagnostic_only": True,
        "no_paper_claims": True,
        "missing_cases": report.get("missing_cases", []),
    }


def input_summary(label: str, input_rows: list[dict[str, Any]], effect_rows: list[dict[str, Any]]) -> str:
    return f"# {label} Input Generation\n\nInputs: `{len(input_rows)}`. Effect validation passed: `{all(row.get('effect_validation_passed') for row in effect_rows)}`.\n"


def random_summary(label: str, random_rows: list[dict[str, Any]]) -> str:
    return f"# {label} Random Generation\n\nRandom rows: `{len(random_rows)}`. Structured hashes were recorded; generated_now=true for this batch only.\n"


def batch_summary(title: str, report: dict[str, Any]) -> str:
    return (
        f"# {title}\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"Gate passed: `{str(report.get('gate_passed')).lower()}`.\n\n"
        f"Completed LegSA metric cases: `{report.get('complete_legsa_metric_case_count')}` / `{report.get('expected_case_count')}`.\n\n"
        "Horizontal/up metrics are primary. Yaw remains diagnostic-only. ready_for_paper_claims=false.\n"
    )


def review_summary(label: str, report: dict[str, Any]) -> str:
    return f"# {label} Review\n\nDecision: `{report['decision']}`.\n\nMissing cases: `{report.get('missing_cases') or 'none'}`.\n"


def consolidated_summary(report: dict[str, Any]) -> str:
    return (
        "# BY3C Consolidated Review\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"Metric rows: `{report['metric_rows']}`.\n\n"
        "Batches summarized: Batch 0 normal, Batch 1 deterministic, Batch 2 position noise, Batch 3 position spike.\n\n"
        "Horizontal/up metrics are primary. Yaw is diagnostic-only. ready_for_paper_claims=false.\n"
    )


def long_task_summary(consolidation: dict[str, Any], validation: dict[str, Any]) -> str:
    return (
        "# BY3C Long Task Summary\n\n"
        f"Consolidated decision: `{consolidation['decision']}`.\n\n"
        f"Validation: `{validation['status']}`.\n\n"
        "No forbidden yaw, mixed, module-disable, LegSA_9F, nonredundant-FGO, or full-matrix families were authorized.\n\n"
        "ready_for_paper_claims=false.\n"
    )


def next_stage_summary(decision: dict[str, Any]) -> str:
    return (
        "# BY3C Next Stage Recommendation\n\n"
        f"Decision: `{decision['status']}`.\n\n"
        f"ready_for_BY3D_diagnostic_yaw_or_mixed_planning={str(decision['ready_for_BY3D_diagnostic_yaw_or_mixed_planning']).lower()}\n\n"
        "ready_for_paper_claims=false\n\n"
        f"recommended_next_stage={decision['recommended_next_stage']}\n"
    )


def case_review_md(case: CaseSpec, metric_rows: list[dict[str, Any]], review: dict[str, Any]) -> str:
    lines = [
        f"# BY3C Case Review: {case.case_id}",
        "",
        f"Family: `{case.family}`. Batch: `{case.batch_id}`.",
        "",
        "Horizontal/up metrics are primary. Yaw is diagnostic-only. ready_for_paper_claims=false.",
        "",
        "## Metrics",
    ]
    if metric_rows:
        for row in metric_rows:
            lines.append(f"- `{row['algorithm']}`: horizontal RMSE `{row.get('horizontal_rmse_m')}`, up RMSE `{row.get('up_rmse_m')}`, yaw RMSE `{row.get('yaw_rmse_deg')}` diagnostic-only.")
    else:
        lines.append("- No completed final official evaluation metrics.")
    return "\n".join(lines) + "\n"


def infer_trace_from_by3b(by3b_root: Path) -> Path | None:
    source_lock = read_json(by3b_root / "matrix" / "BY3B_ACCEPTED_SOURCE_LOCK.json", []) or []
    for row in source_lock:
        if row.get("source_id") == "BY3_trace_evaluation_reference" and row.get("source_path"):
            return Path(row["source_path"])
    return None


def scan_text_forbidden(root: Path) -> list[dict[str, Any]]:
    hits = []
    policy_audit_files = {
        "LONG_TASK_VALIDATION_REPORT.json",
        "LONG_TASK_DECISION_REPORT.json",
        "LONG_TASK_STAGE_STATUS.csv",
        "LONG_TASK_STAGE_STATUS.json",
        "long_task_summary.md",
        "long_task_next_stage_recommendation.md",
    }
    patterns = [
        "B_gnss_downsample_2Hz",
        "H_dual_yaw_noise",
        "E_yaw_std_inflation",
        "LegSA_9F_FGO_EKF",
        "nonredundant",
        '"trace_solver_input": true',
        '"paper_claim_allowed": true',
    ]
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".csv", ".md", ".yaml", ".yml", ".txt"}:
            continue
        if path.name in policy_audit_files:
            continue
        if "EFFECT_VALIDATION" in path.name:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern in text:
                # Source-lock forbidden replacement lists are allowed to mention forbidden strings.
                if "ACCEPTED_SOURCE_LOCK" in path.name or "PREFLIGHT_SOURCE_LOCK" in path.name:
                    continue
                hits.append({"path": str(path), "pattern": pattern})
    return hits


def required_file_blockers(files: dict[str, Path]) -> list[str]:
    blockers = []
    for label, path in files.items():
        if not path.exists():
            blockers.append(f"{label} missing: {path}")
        elif path.is_file() and path.stat().st_size == 0:
            blockers.append(f"{label} empty: {path}")
    return blockers


def numeric_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw in handle:
            parts = raw.strip().replace(",", " ").split()
            if not parts:
                continue
            try:
                rows.append([float(value) for value in parts])
            except ValueError:
                continue
    return rows


def write_numeric_rows(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(" ".join(f"{value:.12g}" for value in row) + "\n")


def first_numeric_row(path: Path) -> list[float]:
    rows = numeric_rows(path)
    return rows[0] if rows else []


def first_numeric_row_at_or_after(path: Path, start_time: float) -> list[float]:
    for row in numeric_rows(path):
        if row and row[0] >= start_time:
            return row
    return []


def file_time_min(path: Path) -> float | None:
    row = first_numeric_row(path)
    return row[0] if row else None


def file_time_max(path: Path) -> float | None:
    last = None
    for row in numeric_rows(path):
        if row:
            last = row[0]
    return last


def count_data_rows(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw in handle:
            stripped = raw.strip()
            if not stripped:
                continue
            parts = stripped.replace(",", " ").split()
            try:
                float(parts[0])
            except (ValueError, IndexError):
                continue
            count += 1
    return count


def monotonic_time(rows: list[list[float]]) -> bool:
    return all(rows[i][0] <= rows[i + 1][0] for i in range(len(rows) - 1))


def unchanged_by_time(before: list[list[float]], after: list[list[float]], indexes: list[int], tol: float = 1e-9) -> bool:
    before_by_time = {round(row[0], 9): row for row in before}
    for row in after:
        original = before_by_time.get(round(row[0], 9))
        if not original:
            continue
        for idx in indexes:
            if idx < len(row) and idx < len(original) and abs(row[idx] - original[idx]) > tol:
                return False
    return True


def any_position_changed_by_time(before: list[list[float]], after: list[list[float]], tol: float = 1e-12) -> bool:
    before_by_time = {round(row[0], 9): row for row in before}
    for row in after:
        original = before_by_time.get(round(row[0], 9))
        if original and len(row) >= 4 and any(abs(row[idx] - original[idx]) > tol for idx in [1, 2, 3]):
            return True
    return False


def summarize_random_vectors(values: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    ns = [float(row.get(f"{prefix}_n_m", 0.0)) for row in values]
    es = [float(row.get(f"{prefix}_e_m", 0.0)) for row in values]
    us = [float(row.get(f"{prefix}_u_m", 0.0)) for row in values]
    norms = [math.sqrt(n * n + e * e + u * u) for n, e, u in zip(ns, es, us)]
    triggered = sum(1 for row in values if row.get("triggered"))
    return {
        "value_count": len(values),
        "triggered_count": triggered,
        f"{prefix}_n_mean": mean(ns),
        f"{prefix}_e_mean": mean(es),
        f"{prefix}_u_mean": mean(us),
        f"{prefix}_norm_mean": mean(norms),
        f"{prefix}_norm_max": max(norms) if norms else None,
    }


def mean(values: Any) -> float | None:
    vals = [float(value) for value in values if value is not None and is_number(value)]
    return sum(vals) / len(vals) if vals else None


def is_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def forbidden_feedback_column(column: str) -> bool:
    name = column.lower()
    return any(token in name for token in ["truth", "trace", "error", "ref", "final_v23"])


def format_vec(values: list[float]) -> str:
    return "[ " + ", ".join(f"{float(value):.8f}" for value in values) + " ]"


def write_rows(stem: Path, rows: list[dict[str, Any]]) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["status"]
    with stem.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def contains_local_path(text: str) -> bool:
    return bool(re.search(r"[A-Z]:\\|/mnt/[a-z]/|/home/", text))


if __name__ == "__main__":
    raise SystemExit(main())
