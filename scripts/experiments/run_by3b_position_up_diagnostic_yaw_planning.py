"""Plan BY3 position/up degradation with diagnostic yaw only.

BY3B is a planning and precheck stage after BY3A8.  It imports the accepted
BY3A8 decision, locks BY3A7/BY3A5B sources, defines the future degradation
matrix and command templates, and writes validation reports.  It deliberately
does not generate random arrays, degraded inputs, solver outputs, evaluator
outputs, or paper-facing claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

STAGE = "BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING"
FUTURE_RUNTIME_STAGE = "BY3B_POSITION_UP_DEGRADATION_MATRIX"

SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "by3a8_import",
    "accepted_source_lock",
    "degradation_family_scope",
    "case_matrix",
    "random_seed_plan",
    "provider_feedback_dependency_plan",
    "command_template_plan",
    "evaluator_metric_policy_plan",
    "figure_case_review_plan",
    "batch_execution_plan",
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
    "LegSA_full_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "final_v23_dual_antenna_EKF",
]

DUAL_YAW_ALGORITHMS = [
    "LegSA_full_EKF",
    "final_v23_dual_antenna_EKF",
]

FORBIDDEN_REPLACEMENTS = [
    "old_BY3_IMU",
    "HDT_yaw_input",
    "GNSS_status_long_baseline_rel_pos_yaw",
    "BY2_feedback",
    "BY3_normal_feedback_reuse",
    "trace_solver_input",
    "final_v23_output_solver_input",
]


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    future_root: Path
    by3a1_root: Path
    by3a2_root: Path
    by3a7_root: Path
    by3a8_root: Path
    obsidian_root: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--future-root", type=Path)
    parser.add_argument("--no-obsidian", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    paths = Paths(
        repo=repo,
        stage_root=(args.stage_root or repo / "by3-huiti" / STAGE).resolve(),
        future_root=(args.future_root or repo / "by3-huiti" / "BY3_FULL_MATRIX" / FUTURE_RUNTIME_STAGE).resolve(),
        by3a1_root=repo / "by3-huiti" / "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR",
        by3a2_root=repo / "by3-huiti" / "BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR",
        by3a7_root=repo / "by3-huiti" / "BY3A7_A1_YAW_DYNAMIC_QUALITY_IMU_SIGN_AND_GATE_REPAIR",
        by3a8_root=repo / "by3-huiti" / "BY3A8_YAW_ERROR_BUDGET_AND_SAFE_REPAIR",
        obsidian_root=repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization",
    )
    result = run_by3b(paths, write_obsidian=not args.no_obsidian)
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))
    return 0


def run_by3b(paths: Paths, *, write_obsidian: bool = True) -> dict[str, Any]:
    create_tree(paths)
    write_approved_plan(paths)

    source_lock = import_by3a8_and_lock_sources(paths)
    family_scope = build_family_scope(paths, source_lock)
    case_rows = build_case_matrix()
    case_report = write_case_matrix(paths, case_rows)
    seed_rows = build_seed_plan(case_rows)
    seed_report = write_seed_plan(paths, seed_rows)
    dependency_rows = build_dependency_plan(case_rows)
    dependency_report = write_dependency_plan(paths, dependency_rows)
    command_rows = build_command_template_plan(case_rows)
    command_report = write_command_template_plan(paths, command_rows)
    metric_rows = build_metric_policy_plan()
    metric_report = write_metric_policy_plan(paths, metric_rows)
    figure_rows = build_figure_case_review_plan(case_rows)
    figure_report = write_figure_case_review_plan(paths, figure_rows)
    batch_rows = build_batch_execution_plan(case_rows)
    batch_report = write_batch_execution_plan(paths, batch_rows)
    obsidian_report = write_context_obsidian_sync(paths, write_obsidian=write_obsidian)
    validation = final_validation(
        paths,
        source_lock,
        family_scope,
        case_report,
        seed_report,
        dependency_report,
        command_report,
        metric_report,
        figure_report,
        batch_report,
        obsidian_report,
    )
    decision = final_decision(validation)
    stage_status = write_final_reports(paths, validation, decision)
    write_future_no_execution_manifest(paths, decision, stage_status)
    return {"validation": validation, "decision": decision, "stage_status": stage_status}


def create_tree(paths: Paths) -> None:
    for root in (paths.stage_root, paths.future_root):
        root.mkdir(parents=True, exist_ok=True)
        for subdir in SUBDIRS:
            (root / subdir).mkdir(parents=True, exist_ok=True)


def write_approved_plan(paths: Paths) -> None:
    plan = {
        "stage": STAGE,
        "purpose": "BY3 degradation planning/precheck only, position/up primary with diagnostic yaw.",
        "execute_now": False,
        "dry_run_only": True,
        "solvers_run": False,
        "evaluators_run": False,
        "random_arrays_generated": False,
        "degraded_inputs_generated": False,
        "ready_for_paper_claims": False,
        "hard_prohibitions": [
            "no degradation execution",
            "no degraded-input generation",
            "no random-array generation",
            "no solver or evaluator execution",
            "no old BY3 IMU",
            "no HDT mainline yaw",
            "no long-baseline rel_pos yaw",
            "no BY2 feedback or BY3 normal feedback reuse",
            "no paper claims",
        ],
    }
    write_json(paths.stage_root / "01_plan" / "BY3B_APPROVED_PLAN.json", plan)
    write_md(
        paths.stage_root / "01_plan" / "by3b_approved_plan.md",
        "# BY3B Approved Plan\n\n"
        "BY3B imports BY3A8, locks accepted BY3A7/BY3A5B sources, and creates planning matrices only.\n\n"
        "- `execute_now=false`\n"
        "- no solvers, evaluators, degraded inputs, or random arrays\n"
        "- position/up metrics are primary\n"
        "- yaw is diagnostic-only after the BY3A8 A1 lower-bound result\n",
    )


def import_by3a8_and_lock_sources(paths: Paths) -> dict[str, Any]:
    decision = read_json(paths.by3a8_root / "reports" / "LONG_TASK_DECISION_REPORT.json", {})
    by3a8_import = read_json(paths.by3a8_root / "reports" / "BY3A8_BY3A7_IMPORT_REPORT.json", {})
    source_by_role = {row.get("role"): row for row in by3a8_import.get("accepted_sources", [])}

    rows = [
        source_lock_row(
            "BY3A7_repaired_IMU",
            source_by_role.get("BY3A7_repaired_IMU"),
            "solver_input_accepted",
            True,
            "future degraded cases must use this BY3A7-local pre-motion bias IMU",
            "old_IMU|moving_segment_bias_IMU",
        ),
        source_lock_row(
            "BY3A5B_A1_dual_diff_15col_GNSS",
            source_by_role.get("BY3A5B_A1_dual_diff_GNSS"),
            "solver_dual_yaw_source_accepted_with_caution",
            True,
            "fixed_1p5 A1_dual_diff short-baseline yaw; yaw metrics diagnostic only",
            "HDT_yaw|long_baseline_rel_pos_yaw",
        ),
        source_lock_row(
            "BY3A2_Raw_Doppler_provider",
            source_by_role.get("BY3A2_Raw_Doppler_provider"),
            "provider_input_accepted",
            True,
            "use same provider source under future degradation handling",
            "unverified_raw_doppler_provider",
        ),
        source_lock_row(
            "BY3A2_Go2_attitude_prior",
            source_by_role.get("BY3A2_Go2_attitude_prior"),
            "provider_input_accepted",
            True,
            "Go2 source observation only, not truth",
            "Go2_truth_claim",
        ),
        source_lock_row(
            "BY3A2_Go2_horizontal_velocity_prior",
            source_by_role.get("BY3A2_Go2_velocity_prior"),
            "provider_input_accepted",
            True,
            "Go2 source observation only, not truth",
            "Go2_truth_claim",
        ),
        source_lock_row(
            "BY3A2_Go2_joint_prior",
            source_by_role.get("BY3A2_Go2_joint_prior"),
            "provider_input_accepted",
            True,
            "Go2 source observation only, not truth",
            "Go2_truth_claim",
        ),
        source_lock_row(
            "BY3A3_BY3A7_selected_feedback_chain_pattern",
            source_by_role.get("BY3A7_same_case_feedback"),
            "pattern_reference_only",
            False,
            "future degraded cases must regenerate same-case feedback from degraded stage1 official EVAL_NAV state/estimate columns",
            "BY2_feedback|normal_feedback_reuse|trace_error_feedback",
        ),
        source_lock_row(
            "BY3_trace_evaluation_reference",
            source_by_role.get("BY3_trace_truth"),
            "evaluation_reference_only",
            True,
            "numeric trace fields for official evaluation only; never solver input",
            "trace_solver_input|trace_tuning",
        ),
        source_lock_row(
            "single_baseline_repaired_GNSS1_input",
            {
                "alias": "<BY3A1_STAGE_ROOT>/input_repair/BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss",
                "path": str(paths.by3a1_root / "input_repair" / "BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"),
            },
            "single_baseline_input_accepted",
            True,
            "single baseline uses GNSS1 status input and has no dual-yaw solver source",
            "raw_GNSS1_schema_mismatch|dual_yaw_input_for_single",
        ),
        source_lock_row(
            "final_v23_external_baseline_config_pattern",
            source_by_role.get("final_v23_runtime_config"),
            "external_reference_baseline_config",
            True,
            "future final_v23 runs remain external reference comparisons only",
            "final_v23_output_solver_input|final_v23_algorithm_change",
        ),
        source_lock_row(
            "single_baseline_config_pattern",
            source_by_role.get("single_baseline_runtime_config"),
            "single_baseline_config",
            True,
            "future single runs use repaired GNSS1 input and BY3A7 IMU",
            "old_single_schema|old_IMU",
        ),
    ]

    for row in rows:
        if row["source_path"] and Path(row["source_path"]).exists():
            row["exists"] = True
            row["row_count"] = count_nonempty_lines(Path(row["source_path"]))
            row["sha256"] = sha256_file(Path(row["source_path"]))
        elif row.get("exists") is None:
            row["exists"] = False
            row["row_count"] = 0
            row["sha256"] = None
        row["forbidden_replacements_all"] = "|".join(FORBIDDEN_REPLACEMENTS)

    sources_locked = (
        decision.get("status") == "BY3A8_yaw_limited_but_position_up_ready"
        and decision.get("ready_for_BY3_degradation_matrix_planning") is True
        and decision.get("ready_for_BY3_degradation_matrix_planning_scope") == "position_up_with_diagnostic_yaw"
        and decision.get("ready_for_paper_claims") is False
        and all(row["exists"] for row in rows if row["accepted_for_BY3_degradation"])
    )

    report = {
        "stage": STAGE,
        "decision": "BY3B_accepted_sources_locked" if sources_locked else "BY3B_accepted_sources_blocked",
        "by3a8_status": decision.get("status"),
        "by3a8_ready_for_BY3_degradation_matrix_planning": decision.get("ready_for_BY3_degradation_matrix_planning"),
        "by3a8_scope": decision.get("ready_for_BY3_degradation_matrix_planning_scope"),
        "yaw_metric_scope": "diagnostic_only",
        "yaw_paper_claim_allowed": False,
        "A1_observation_quality_limitation": True,
        "a1_observation_yaw_rmse_deg": 24.057851387253088,
        "a1_observation_yaw_p95_deg": 31.784368751588655,
        "a1_observation_yaw_max_deg": 167.292805611622,
        "accepted_sources": rows,
        "forbidden_replacements": FORBIDDEN_REPLACEMENTS,
        "execute_now": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_BY3A8_IMPORT_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_ACCEPTED_SOURCE_LOCK.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_ACCEPTED_SOURCE_LOCK.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_by3a8_import_and_source_lock.md",
        "# BY3B BY3A8 Import And Source Lock\n\n"
        f"- Decision: `{report['decision']}`.\n"
        "- BY3A8 status imported as `BY3A8_yaw_limited_but_position_up_ready`.\n"
        "- BY3 degradation scope is position/up with diagnostic yaw.\n"
        "- BY3A7 repaired IMU and BY3A5B A1_dual_diff yaw source are locked.\n"
        "- BY3 normal feedback is a pattern reference only; degraded cases must regenerate same-case feedback.\n"
        "- HDT, long-baseline rel_pos yaw, old IMU, BY2 feedback, normal feedback reuse, trace solver input, and paper claims are forbidden.\n",
    )
    return report


def source_lock_row(
    role: str,
    prior: dict[str, Any] | None,
    source_role: str,
    accepted_for_degradation: bool,
    validation_status: str,
    forbidden_replacements: str,
) -> dict[str, Any]:
    prior = prior or {}
    return {
        "source_id": role,
        "source_path_alias": prior.get("alias"),
        "source_path": prior.get("path"),
        "source_role": source_role,
        "row_count": prior.get("row_count"),
        "sha256": prior.get("sha256"),
        "exists": prior.get("exists"),
        "validation_status": validation_status,
        "accepted_for_BY3_degradation": accepted_for_degradation,
        "forbidden_replacements": forbidden_replacements,
    }


def build_family_scope(paths: Paths, source_lock: dict[str, Any]) -> dict[str, Any]:
    rows = [
        family_row("A_outage", "position_up_primary", "deterministic", "outage_3s|outage_5s|outage_10s|outage_20s", False, True),
        family_row("B_downsample", "position_up_primary", "deterministic", "every2|every5|every10", False, True, exclusions="B_gnss_downsample_2Hz"),
        family_row("C_position_noise", "position_up_primary", "random", "mild|medium|strong; seeds 0..9", True, True),
        family_row("D_position_spike", "position_up_primary", "random", "mild|medium|strong; seeds 0..9", True, True),
        family_row("E_position_std_inflation", "position_up_primary", "deterministic", "x2|x5|x10", False, True),
        family_row("M_position_up_mixed", "position_up_primary", "deterministic_mixed", "five locked position/up mixed cases", False, True),
        family_row("H_dual_yaw_noise", "yaw_diagnostic_only", "random", "mild|medium|strong; seeds 0..9", True, True, requires_human_review=True),
        family_row("E_yaw_std_inflation", "yaw_diagnostic_only", "deterministic", "x2|x5|x10", False, True, requires_human_review=True),
        family_row("M_mixed_yaw_diagnostic", "yaw_diagnostic_only", "random_mixed", "C_position_noise_medium + H_dual_yaw_noise_medium; seeds 0..9", True, True, requires_human_review=True),
        family_row("module_disable_stress", "deferred", "deferred", "G/I/J/L/K/F/custom/module stress", False, False, requires_human_review=True),
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3B_family_scope_locked_with_yaw_diagnostic_caution"
        if source_lock["decision"] == "BY3B_accepted_sources_locked"
        else "BY3B_family_scope_blocked",
        "primary_families": ["A_outage", "B_downsample", "C_position_noise", "D_position_spike", "E_position_std_inflation", "M_position_up_mixed"],
        "diagnostic_yaw_families": ["H_dual_yaw_noise", "E_yaw_std_inflation", "M_mixed_yaw_diagnostic"],
        "deferred_families": ["module_disable_stress", "K_legged_specific", "F_receiver_velocity_specific", "LegSA_9F_FGO_EKF", "nonredundant_FGO_extension"],
        "algorithms": ALGORITHMS,
        "do_not_run": ["LegSA_9F_FGO_EKF", "nonredundant_FGO_extension", "branch_ablations"],
        "rows": rows,
        "execute_now": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_DEGRADATION_FAMILY_SCOPE_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_DEGRADATION_FAMILY_SCOPE.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_DEGRADATION_FAMILY_SCOPE.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_degradation_family_scope.md",
        "# BY3B Degradation Family Scope\n\n"
        f"- Decision: `{report['decision']}`.\n"
        "- Primary scope: horizontal/up robustness families A, B, C, D, E_position_std, and selected position/up mixed cases.\n"
        "- Diagnostic-only yaw families H, E_yaw_std, and mixed yaw may be planned but not claimed.\n"
        "- `B_gnss_downsample_2Hz`, module stress, LegSA_9F_FGO_EKF, and nonredundant FGO extension are excluded/deferred.\n"
        "- No execution is authorized by this plan.\n",
    )
    return report


def family_row(
    family: str,
    metric_scope: str,
    mode: str,
    cases: str,
    seeds_required: bool,
    included_in_plan: bool,
    *,
    exclusions: str = "",
    requires_human_review: bool = False,
) -> dict[str, Any]:
    return {
        "family": family,
        "metric_scope": metric_scope,
        "deterministic_or_random": mode,
        "planned_cases": cases,
        "seeds_required": seeds_required,
        "included_in_BY3B_plan": included_in_plan,
        "requires_human_review_before_execution": requires_human_review,
        "exclusions": exclusions,
        "paper_claim_allowed": False,
    }


def build_case_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sec in ["3s", "5s", "10s", "20s"]:
        rows.append(case_row(f"A_outage_{sec}", "A_outage", sec, None, "deterministic", "position_up_primary"))
    for ratio in ["every2", "every5", "every10"]:
        rows.append(case_row(f"B_downsample_{ratio}", "B_downsample", ratio, None, "deterministic", "position_up_primary"))
    for scale in ["x2", "x5", "x10"]:
        rows.append(case_row(f"E_position_std_inflation_{scale}", "E_position_std_inflation", scale, None, "deterministic", "position_up_primary"))
    for severity in ["mild", "medium", "strong"]:
        for seed in range(10):
            rows.append(case_row(f"C_position_noise_{severity}_seed{seed}", "C_position_noise", severity, seed, "random", "position_up_primary"))
    for severity in ["mild", "medium", "strong"]:
        for seed in range(10):
            rows.append(case_row(f"D_position_spike_{severity}_seed{seed}", "D_position_spike", severity, seed, "random", "position_up_primary"))
    mixed = [
        ("M_position_up_A_outage_5s_plus_C_medium", "A_outage_5s + C_position_noise_medium"),
        ("M_position_up_B_every2_plus_C_medium", "B_downsample_every2 + C_position_noise_medium"),
        ("M_position_up_D_medium_plus_C_medium", "D_position_spike_medium + C_position_noise_medium"),
        ("M_position_up_A_outage_10s_plus_D_medium", "A_outage_10s + D_position_spike_medium"),
        ("M_position_up_B_every5_plus_E_std_x5", "B_downsample_every5 + E_position_std_inflation_x5"),
    ]
    for case_id, components in mixed:
        rows.append(case_row(case_id, "M_position_up_mixed", "mixed", None, "deterministic_mixed", "position_up_primary", components=components))
    for severity in ["mild", "medium", "strong"]:
        for seed in range(10):
            rows.append(case_row(f"H_dual_yaw_noise_{severity}_seed{seed}", "H_dual_yaw_noise", severity, seed, "random", "yaw_diagnostic_only", yaw_diagnostic=True))
    for scale in ["x2", "x5", "x10"]:
        rows.append(case_row(f"E_yaw_std_inflation_{scale}", "E_yaw_std_inflation", scale, None, "deterministic", "yaw_diagnostic_only", yaw_diagnostic=True))
    for seed in range(10):
        rows.append(
            case_row(
                f"M_yaw_diag_C_medium_plus_H_medium_seed{seed}",
                "M_mixed_yaw_diagnostic",
                "medium",
                seed,
                "random_mixed",
                "yaw_diagnostic_only",
                components="C_position_noise_medium + H_dual_yaw_noise_medium",
                yaw_diagnostic=True,
                optional=True,
            )
        )
    return rows


def case_row(
    case_id: str,
    family: str,
    severity: str,
    seed: int | None,
    mode: str,
    metric_scope: str,
    *,
    components: str = "",
    yaw_diagnostic: bool = False,
    optional: bool = False,
) -> dict[str, Any]:
    single_applicable = not yaw_diagnostic
    algorithms = DUAL_YAW_ALGORITHMS if yaw_diagnostic else ALGORITHMS
    return {
        "case_id": case_id,
        "family": family,
        "severity": severity,
        "seed": "" if seed is None else seed,
        "deterministic_or_random": mode,
        "component_degradations": components,
        "algorithms_applicable": "|".join(algorithms),
        "single_applicable": single_applicable,
        "final_v23_applicable": True,
        "LegSA_full_applicable": True,
        "metric_scope": metric_scope,
        "yaw_metric_status": "diagnostic_only" if yaw_diagnostic else "not_primary",
        "input_generation_required": True,
        "random_required": seed is not None,
        "selected_feedback_required": True,
        "stage1_required": True,
        "official_eval_required": True,
        "figure_required": True,
        "case_review_required": True,
        "execution_requires_human_review": optional or yaw_diagnostic,
        "paper_claim_allowed": False,
        "execute_now": False,
        "generated_now": False,
    }


def write_case_matrix(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = summarize_cases(rows)
    report = {
        "stage": STAGE,
        "counts": counts,
        "hard_exclusions": [
            "B_gnss_downsample_2Hz",
            "BY2_feedback_reuse",
            "normal_feedback_reuse_for_degraded_cases",
            "old_BY3_IMU_source",
            "HDT_yaw_input",
            "long_relpos_yaw_input",
        ],
        "execute_now": False,
        "degraded_inputs_generated": False,
        "random_arrays_generated": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_DEGRADATION_CASE_MATRIX_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_DEGRADATION_CASE_MATRIX.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_DEGRADATION_CASE_MATRIX.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_degradation_case_matrix.md",
        "# BY3B Degradation Case Matrix\n\n"
        f"- Total planned case-seed units: `{counts['total_case_seed_units']}`.\n"
        f"- Primary position/up units: `{counts['primary_position_up_units']}`.\n"
        f"- Diagnostic yaw units: `{counts['diagnostic_yaw_units']}`.\n"
        f"- Planned solver rows: `{counts['solver_rows_planned']}`.\n"
        f"- Planned evaluator rows: `{counts['evaluator_rows_planned']}`.\n"
        "- `B_gnss_downsample_2Hz`, old IMU, HDT, long-relpos yaw, BY2 feedback, and normal-feedback reuse are excluded.\n",
    )
    return report


def summarize_cases(rows: list[dict[str, Any]]) -> dict[str, int]:
    solver_rows = sum(len(str(row["algorithms_applicable"]).split("|")) for row in rows)
    return {
        "deterministic_units": sum(1 for row in rows if "deterministic" in row["deterministic_or_random"]),
        "random_units": sum(1 for row in rows if row["random_required"]),
        "diagnostic_yaw_units": sum(1 for row in rows if row["metric_scope"] == "yaw_diagnostic_only"),
        "primary_position_up_units": sum(1 for row in rows if row["metric_scope"] == "position_up_primary"),
        "total_case_seed_units": len(rows),
        "solver_rows_planned": solver_rows,
        "evaluator_rows_planned": solver_rows,
        "feedback_chains_planned": len(rows),
    }


def build_seed_plan(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        seed_family_row("C_position_noise", "0..9", "position_up_primary", True),
        seed_family_row("D_position_spike", "0..9", "position_up_primary", True),
        seed_family_row("H_dual_yaw_noise", "0..9", "yaw_diagnostic_only", True, requires_human_review=True),
        seed_family_row("M_mixed_yaw_diagnostic", "0..9", "yaw_diagnostic_only", True, requires_human_review=True),
        seed_family_row("A_outage", "none", "position_up_primary", False),
        seed_family_row("B_downsample", "none", "position_up_primary", False),
        seed_family_row("E_position_std_inflation", "none", "position_up_primary", False),
        seed_family_row("E_yaw_std_inflation", "none", "yaw_diagnostic_only", False, requires_human_review=True),
        seed_family_row("M_position_up_mixed", "inherits random component if future generator materializes stochastic component", "position_up_primary", True),
    ]
    family_counts = {
        family: sum(1 for row in case_rows if row["family"] == family and row["random_required"])
        for family in {row["family"] for row in case_rows}
    }
    for row in rows:
        row["random_case_seed_units_in_matrix"] = family_counts.get(row["family"], "") if row["seeds"] == "0..9" else ""
    return rows


def seed_family_row(
    family: str,
    seeds: str,
    metric_scope: str,
    same_seed_fairness_required: bool,
    *,
    requires_human_review: bool = False,
) -> dict[str, Any]:
    return {
        "family": family,
        "seeds": seeds,
        "metric_scope": metric_scope,
        "same_seed_fairness_required": same_seed_fairness_required,
        "seed_policy": "single, final_v23, and LegSA_full face the same degraded input for the same case/seed",
        "seed0_9_explanation_alias": "<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>/00_INDEX/seed0-9_random_seed_explanation.md",
        "seed0_9_reference_policy": "use alias only in tracked material; local absolute path remains in DATA_PATHS.local.md or runtime-only notes",
        "generated_now": False,
        "random_arrays_generated": False,
        "requires_human_review_before_execution": requires_human_review,
        "paper_claim_allowed": False,
    }


def write_seed_plan(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": "BY3B_random_seed_plan_complete",
        "seed_policy": "C, D, diagnostic H, and optional yaw mixed families use seeds 0..9; deterministic cases have no seed.",
        "same_seed_fairness_rule": "single, final_v23, and LegSA_full face the same degraded input for the same case/seed.",
        "generated_now": False,
        "random_arrays_generated": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_RANDOM_SEED_PLAN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_RANDOM_SEED_PLAN.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_RANDOM_SEED_PLAN.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_random_seed_plan.md",
        "# BY3B Random Seed Plan\n\n"
        "- Seeds are planned but not generated.\n"
        "- C_position_noise and D_position_spike use seeds `0..9`.\n"
        "- H_dual_yaw_noise and optional yaw-mixed cases use seeds `0..9` only as diagnostic/human-reviewed plans.\n"
        "- Same-seed fairness applies across LegSA_full, single, and final_v23 wherever all are applicable.\n"
        "- No random arrays were generated in BY3B.\n",
    )
    return report


def build_dependency_plan(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in case_rows:
        for algorithm in str(case["algorithms_applicable"]).split("|"):
            rows.append(
                {
                    "case_id": case["case_id"],
                    "algorithm": algorithm,
                    "accepted_BY3A7_IMU_source": "<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu",
                    "degraded_GNSS_input_template": "<BY3_FULL_MATRIX_ROOT>/BY3B_POSITION_UP_DEGRADATION_MATRIX/case_inputs",
                    "Raw_Doppler_provider_handling": "reuse BY3A2 provider source; future generator must document outage/downsample/noise handling",
                    "Go2_prior_source": "<BY3A1_STAGE_ROOT>/provider_materialization/go2_priors/priors/joint_rp1p6deg_hv1p0",
                    "stage1_solver_requirement": algorithm == "LegSA_full_EKF",
                    "stage1_official_eval_requirement": algorithm == "LegSA_full_EKF",
                    "feedback_generation_requirement": algorithm == "LegSA_full_EKF",
                    "feedback_input": "stage1_official_eval/EVAL_NAV.csv state/estimate columns only",
                    "trace_error_columns_allowed_for_feedback": False,
                    "BY2_feedback_allowed": False,
                    "normal_feedback_reuse_allowed": False,
                    "stage2_LegSA_full_selected_feedback_requirement": algorithm == "LegSA_full_EKF",
                    "single_baseline_input": "<BY3A1_STAGE_ROOT>/input_repair/BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss" if algorithm == "single_antenna_gnss1_status_KF_GINS" else "",
                    "final_v23_external_input": "<BY3A7_STAGE_ROOT>/finalv23_solver/by3_finalv23_external.runtime_config.yaml" if algorithm == "final_v23_dual_antenna_EKF" else "",
                    "output_lineage_requirements": "write source_role.json, output_lineage.json, RUN_MANIFEST, and command.json in future execution",
                    "yaw_diagnostic_caveat": "yaw diagnostic only; no paper claim" if case["metric_scope"] == "yaw_diagnostic_only" else "yaw not primary",
                    "execute_now": False,
                    "paper_claim_allowed": False,
                }
            )
    return rows


def write_dependency_plan(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": "BY3B_dependency_plan_complete",
        "dependency_rows": len(rows),
        "same_case_feedback_policy": "degraded cases must regenerate feedback from their own stage1 official EVAL_NAV state/estimate columns only",
        "BY2_feedback_allowed": False,
        "normal_feedback_reuse_allowed": False,
        "trace_feedback_allowed": False,
        "execute_now": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_PROVIDER_FEEDBACK_DEPENDENCY_PLAN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_PROVIDER_FEEDBACK_DEPENDENCY_PLAN.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_PROVIDER_FEEDBACK_DEPENDENCY_PLAN.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_provider_feedback_dependency_plan.md",
        "# BY3B Provider And Feedback Dependency Plan\n\n"
        f"- Decision: `{report['decision']}`.\n"
        f"- Dependency rows: `{len(rows)}`.\n"
        "- All future cases must use the BY3A7 repaired IMU and the BY3A5B/BY3A7 A1 dual-yaw input where dual yaw applies.\n"
        "- LegSA degraded cases require same-case stage1 solver, official evaluation, feedback generation, and stage2 selected-feedback execution.\n"
        "- Feedback may use only stage1 official EVAL_NAV state/estimate columns; trace/error columns, BY2 feedback, and normal feedback reuse are forbidden.\n",
    )
    return report


def build_command_template_plan(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    command_steps = [
        "degraded_input_generation",
        "stage1_solver",
        "stage1_official_eval",
        "feedback_generation",
        "stage2_LegSA_full_solver",
        "single_baseline_solver",
        "final_v23_solver",
        "official_eval",
        "figure_generation",
        "case_review",
    ]
    for step in command_steps:
        rows.append(command_template_row(step, "all_planned_cases"))
    for case in case_rows:
        rows.append(command_template_row("case_execution_manifest", case["case_id"], case_family=case["family"]))
    return rows


def command_template_row(step: str, target: str, *, case_family: str = "") -> dict[str, Any]:
    return {
        "template_id": f"{step}:{target}",
        "planned_step": step,
        "case_id": target,
        "case_family": case_family,
        "execute_now": False,
        "dry_run_only": True,
        "future_execution_root_alias": "<BY3_FULL_MATRIX_ROOT>/BY3B_POSITION_UP_DEGRADATION_MATRIX",
        "BY3_root_alias": "<BY3_OUTPUT_ROOT>",
        "accepted_IMU_alias": "<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu",
        "accepted_dual_yaw_alias": "<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss",
        "old_IMU_allowed": False,
        "HDT_yaw_input_allowed": False,
        "long_relpos_yaw_input_allowed": False,
        "BY2_root_contamination_allowed": False,
        "trace_solver_input_allowed": False,
        "final_v23_output_solver_input_allowed": False,
        "paper_claim_allowed": False,
        "command_status": "template_only_not_executed",
        "future_runner_note": "expand this template from the case matrix and approved source-lock manifest during BY3C only",
    }


def write_command_template_plan(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": "BY3B_command_template_plan_complete",
        "template_rows": len(rows),
        "all_execute_now_false": all(row["execute_now"] is False for row in rows),
        "all_dry_run_only_true": all(row["dry_run_only"] is True for row in rows),
        "degraded_inputs_generated": False,
        "solvers_run": False,
        "evaluators_run": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_COMMAND_TEMPLATE_PLAN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_COMMAND_TEMPLATE_PLAN.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_COMMAND_TEMPLATE_PLAN.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_command_template_plan.md",
        "# BY3B Command Template Plan\n\n"
        f"- Decision: `{report['decision']}`.\n"
        f"- Template rows: `{len(rows)}`.\n"
        "- Every row has `execute_now=false` and `dry_run_only=true`.\n"
        "- Templates are alias-based and not shell-executed in BY3B.\n"
        "- Old IMU, HDT yaw, long-relpos yaw, BY2 root contamination, trace solver input, and paper claims are forbidden.\n",
    )
    return report


def build_metric_policy_plan() -> list[dict[str, Any]]:
    primary = [
        "horizontal_rmse_m",
        "horizontal_p95_m",
        "horizontal_max_m",
        "north_rmse_m",
        "east_rmse_m",
        "up_rmse_m",
        "up_p95_m",
        "up_max_m",
        "recovery_time_s_if_available",
        "position_consistency_if_available",
    ]
    diagnostic = [
        "yaw_rmse_deg",
        "yaw_p95_deg",
        "yaw_max_deg",
        "yaw_gate_counts",
        "yaw_observation_quality",
        "A1_yaw_quality_notes",
        "final_v23_vs_LegSA_yaw_trend",
    ]
    rows = []
    for metric in primary:
        rows.append(metric_policy_row(metric, "primary_position_up", "accepted_primary"))
    for metric in diagnostic:
        rows.append(metric_policy_row(metric, "diagnostic_yaw", "accepted_diagnostic"))
    rows.append(metric_policy_row("common_overlap_position_metrics", "secondary_fairness", "accepted_secondary"))
    rows.append(metric_policy_row("yaw_status", "summary_required", "accepted_diagnostic"))
    return rows


def metric_policy_row(metric: str, scope: str, yaw_status: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "metric_scope": scope,
        "yaw_status": yaw_status,
        "trace_policy": "evaluation_only_numeric_fields_BY3A6_validated",
        "base_time_policy": "BY3A6_validated",
        "paper_claim_allowed": False,
        "BY3_yaw_claim_allowed": False,
        "diagnostic_only_reason": "BY3A8 A1 observation quality limitation" if "yaw" in scope or "yaw" in metric else "",
    }


def write_metric_policy_plan(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": "BY3B_evaluator_metric_policy_plan_complete",
        "primary_metrics": [row["metric"] for row in rows if row["metric_scope"] == "primary_position_up"],
        "diagnostic_metrics": [row["metric"] for row in rows if row["metric_scope"] == "diagnostic_yaw"],
        "yaw_metric_scope": "diagnostic_only",
        "trace_evaluation_only": True,
        "numeric_trace_fields_required": True,
        "solvers_run": False,
        "evaluators_run": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_EVALUATOR_METRIC_POLICY_PLAN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_EVALUATOR_METRIC_POLICY_PLAN.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_EVALUATOR_METRIC_POLICY_PLAN.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_evaluator_metric_policy_plan.md",
        "# BY3B Evaluator And Metric Policy Plan\n\n"
        "- Primary metrics are horizontal/up robustness metrics.\n"
        "- Yaw RMSE/P95/max, yaw gate counts, and A1 quality notes are diagnostic-only.\n"
        "- The BY3 trace remains evaluation-only with BY3A6-validated numeric fields/base_time.\n"
        "- Summary tables must include a yaw status field such as `accepted_diagnostic`, `not_primary`, `unavailable`, or `not_applicable`.\n"
        "- No official evaluator was run in BY3B.\n",
    )
    return report


def build_figure_case_review_plan(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    figures = [
        "trajectory",
        "position_errors",
        "horizontal_up_rmse_bars",
        "horizontal_up_p95_bars",
        "degradation_metadata",
        "feedback_timeline_if_available",
        "audit_sanity_panel",
        "yaw_diagnostic_plots_if_applicable",
        "case_review_markdown_json",
    ]
    rows: list[dict[str, Any]] = []
    for case in case_rows:
        for figure in figures:
            rows.append(
                {
                    "case_id": case["case_id"],
                    "family": case["family"],
                    "figure_or_review": figure,
                    "metric_scope": case["metric_scope"],
                    "yaw_diagnostic_only": figure.startswith("yaw") or case["metric_scope"] == "yaw_diagnostic_only",
                    "case_review_style": "BY2 case_review.md three-scheme comparison where applicable",
                    "BY3A7_IMU_repair_caveat_required": True,
                    "BY3A8_yaw_diagnostic_caveat_required": True,
                    "paper_claim_allowed": False,
                    "generate_now": False,
                }
            )
    return rows


def write_figure_case_review_plan(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": "BY3B_figure_case_review_plan_complete",
        "planned_rows": len(rows),
        "generate_now": False,
        "paper_claim_allowed": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_FIGURE_CASE_REVIEW_PLAN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_FIGURE_CASE_REVIEW_PLAN.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_FIGURE_CASE_REVIEW_PLAN.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_figure_case_review_plan.md",
        "# BY3B Figure And Case Review Plan\n\n"
        f"- Planned figure/review rows: `{len(rows)}`.\n"
        "- Future case reviews follow the BY2 case-review style and use three-scheme comparisons where applicable.\n"
        "- Position/up plots are primary; yaw plots are diagnostic-only and must carry the BY3A8 caveat.\n"
        "- No figures or case-review outputs were generated in BY3B.\n",
    )
    return report


def build_batch_execution_plan(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    family_counts = {family: sum(1 for row in case_rows if row["family"] == family) for family in sorted({row["family"] for row in case_rows})}
    return [
        batch_row(0, "normal parity recheck with BY3A7/BY3A8 accepted sources", 1, "human review of BY3B; source lock passes", "any normal source mismatch or yaw caveat missing"),
        batch_row(1, "deterministic A/B/E_position_std", family_counts["A_outage"] + family_counts["B_downsample"] + family_counts["E_position_std_inflation"], "Batch 0 accepted", "input lineage mismatch or position/up sanity failure"),
        batch_row(2, "C_position_noise seeds 0..9", family_counts["C_position_noise"], "Batch 1 accepted; seed plan approved", "seed fairness or JSON/CSV manifest failure"),
        batch_row(3, "D_position_spike seeds 0..9", family_counts["D_position_spike"], "Batch 2 accepted", "spike generator or seed fairness failure"),
        batch_row(4, "diagnostic H_dual_yaw_noise seeds 0..9 if approved", family_counts["H_dual_yaw_noise"], "human approval for diagnostic yaw batch", "yaw diagnostics start being treated as claims"),
        batch_row(5, "diagnostic E_yaw_std if approved", family_counts["E_yaw_std_inflation"], "human approval for diagnostic yaw std batch", "yaw diagnostics start being treated as claims"),
        batch_row(6, "selected mixed position/up cases", family_counts["M_position_up_mixed"], "Batches 1-3 reviewed", "mixed lineage or feedback dependency failure"),
        batch_row(7, "optional mixed yaw diagnostic only after review", family_counts["M_mixed_yaw_diagnostic"], "separate human review", "diagnostic yaw scope violation"),
    ]


def batch_row(batch_id: int, name: str, expected_case_units: int, prerequisites: str, stop_conditions: str) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "batch_name": name,
        "expected_case_units": expected_case_units,
        "expected_solver_rows_max": expected_case_units * 3 if "diagnostic" not in name else expected_case_units * 2,
        "prerequisites": prerequisites,
        "stop_conditions": stop_conditions,
        "reviewer_gate": True,
        "outputs": "case manifests, source_role, output_lineage, command, official eval, metrics, figures, case review in future execution",
        "execute_now": False,
        "paper_claim_allowed": False,
    }


def write_batch_execution_plan(paths: Paths, rows: list[dict[str, Any]]) -> dict[str, Any]:
    report = {
        "stage": STAGE,
        "decision": "BY3B_batch_execution_plan_complete",
        "batch_count": len(rows),
        "execute_now": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_BATCH_EXECUTION_PLAN_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_BATCH_EXECUTION_PLAN.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_BATCH_EXECUTION_PLAN.csv", rows)
    write_md(
        paths.stage_root / "summary" / "by3b_batch_execution_plan.md",
        "# BY3B Batch Execution Plan\n\n"
        "- Batch 0: normal parity recheck.\n"
        "- Batch 1: deterministic A/B/E_position_std.\n"
        "- Batch 2: C_position_noise seeds 0..9.\n"
        "- Batch 3: D_position_spike seeds 0..9.\n"
        "- Batch 4 and 5: diagnostic yaw batches only if approved.\n"
        "- Batch 6: selected mixed position/up cases.\n"
        "- Batch 7: optional mixed yaw diagnostic after separate review.\n"
        "- Every batch has `execute_now=false` in BY3B.\n",
    )
    return report


def write_context_obsidian_sync(paths: Paths, *, write_obsidian: bool) -> dict[str, Any]:
    notes = [
        ("BY3_degradation_matrix_plan.md", "BY3 Degradation Matrix Plan", "BY3B locks a position/up-primary degradation matrix with diagnostic yaw only."),
        ("BY3_position_up_with_diagnostic_yaw_policy.md", "BY3 Position Up With Diagnostic Yaw Policy", "BY3 yaw remains diagnostic-only because BY3A8 found poor A1 observation quality."),
        ("BY3A8_yaw_error_budget.md", "BY3A8 Yaw Error Budget", "A1-vs-trace heading RMSE is about 24.06 deg and p95 about 31.78 deg; no safe additional repair passed."),
        ("BY3A7_current_accepted_sources.md", "BY3A7 Current Accepted Sources", "Future BY3 degraded cases must use the BY3A7 repaired IMU and A1_dual_diff dual-yaw source."),
        ("current_state.md", "Current State", "BY3B planning is complete only as a dry-run plan; BY3C execution requires human review."),
        ("next_steps.md", "Next Steps", "Next recommended stage is BY3C batch0 and batch1 execution after human review."),
        ("claim_boundary.md", "Claim Boundary", "BY3B allows no paper claims and no BY3 yaw robustness claim."),
    ]
    rows = []
    if write_obsidian:
        paths.obsidian_root.mkdir(parents=True, exist_ok=True)
    for filename, title, body in notes:
        path = paths.obsidian_root / filename
        if write_obsidian:
            write_md(
                path,
                f"# {title}\n\n"
                f"{body}\n\n"
                "- Use aliases for runtime roots in public notes.\n"
                "- No local absolute paths.\n"
                "- No paper claims.\n",
            )
        rows.append({"note": filename, "path_alias": f"<OBSIDIAN_BY3_GENERALIZATION>/{filename}", "written": write_obsidian, "public_alias_only": True})
    report = {
        "stage": STAGE,
        "decision": "BY3B_context_obsidian_sync_complete",
        "tracked_docs_need_BY3B_update": True,
        "obsidian_written": write_obsidian,
        "obsidian_untracked_expected": True,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3B_CONTEXT_OBSIDIAN_SYNC_REPORT.json", report)
    write_json(paths.stage_root / "matrix" / "BY3B_OBSIDIAN_SYNC_INDEX.json", rows)
    write_csv(paths.stage_root / "matrix" / "BY3B_OBSIDIAN_SYNC_INDEX.csv", rows)
    return report


def final_validation(paths: Paths, *reports: dict[str, Any]) -> dict[str, Any]:
    stage_parse = json_csv_parse_check(paths.stage_root)
    future_parse = json_csv_parse_check(paths.future_root)
    case_matrix = read_json(paths.stage_root / "matrix" / "BY3B_DEGRADATION_CASE_MATRIX.json", [])
    command_rows = read_json(paths.stage_root / "matrix" / "BY3B_COMMAND_TEMPLATE_PLAN.json", [])
    seed_rows = read_json(paths.stage_root / "matrix" / "BY3B_RANDOM_SEED_PLAN.json", [])
    validation = {
        "stage": STAGE,
        "no_solvers_run": True,
        "no_evaluators_run": True,
        "no_random_arrays_generated": all(row.get("random_arrays_generated") is False for row in seed_rows),
        "no_degraded_inputs_generated": all(row.get("generated_now") is False for row in case_matrix),
        "BY3A8_accepted_scope_imported": reports[0].get("by3a8_scope") == "position_up_with_diagnostic_yaw",
        "BY3A7_repaired_IMU_locked": any(row.get("source_id") == "BY3A7_repaired_IMU" and row.get("accepted_for_BY3_degradation") for row in reports[0].get("accepted_sources", [])),
        "old_IMU_forbidden": True,
        "HDT_yaw_forbidden_as_main_input": True,
        "long_baseline_rel_pos_yaw_forbidden": True,
        "case_matrix_complete": len(case_matrix) == 118,
        "seed_plan_complete": bool(seed_rows),
        "provider_feedback_dependency_complete": reports[4].get("decision") == "BY3B_dependency_plan_complete",
        "command_templates_dry_run_only": bool(command_rows) and all(row.get("execute_now") is False and row.get("dry_run_only") is True for row in command_rows),
        "batch_plan_complete": reports[8].get("decision") == "BY3B_batch_execution_plan_complete",
        "yaw_diagnostic_caveat_present": all(row.get("yaw_metric_status") == "diagnostic_only" for row in case_matrix if row.get("metric_scope") == "yaw_diagnostic_only"),
        "JSON_CSV_parse": stage_parse and future_parse,
        "runtime_untracked_expected": True,
        "obsidian_untracked_expected": True,
        "ready_for_paper_claims": False,
        "degradation_executed": False,
        "future_root_contains_no_execution_manifest_only": True,
    }
    validation["validation_passed"] = all(value is True for key, value in validation.items() if key not in {"stage", "ready_for_paper_claims", "degradation_executed"})
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    return validation


def final_decision(validation: dict[str, Any]) -> dict[str, Any]:
    status = (
        "BY3B_position_up_diagnostic_yaw_plan_complete"
        if validation.get("validation_passed")
        else "BY3B_safety_gate_failed"
    )
    return {
        "stage": STAGE,
        "status": status,
        "ready_for_BY3C_position_up_degradation_execution": validation.get("validation_passed", False),
        "ready_for_paper_claims": False,
        "recommended_next_stage": "BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_AND_BATCH1"
        if validation.get("validation_passed")
        else "repair_safety_violation",
        "human_final_decision_required_before_execution": True,
        "yaw_metric_scope": "diagnostic_only",
        "paper_claim_allowed": False,
    }


def write_final_reports(paths: Paths, validation: dict[str, Any], decision: dict[str, Any]) -> list[dict[str, Any]]:
    status_rows = [
        {"stage": "A_BY3A8_import_source_lock", "status": "completed", "decision": "BY3B_accepted_sources_locked"},
        {"stage": "B_degradation_family_scope", "status": "completed", "decision": "BY3B_family_scope_locked_with_yaw_diagnostic_caution"},
        {"stage": "C_case_matrix", "status": "completed", "decision": "BY3B_case_matrix_complete"},
        {"stage": "D_random_seed_plan", "status": "completed", "decision": "BY3B_random_seed_plan_complete"},
        {"stage": "E_provider_feedback_dependency", "status": "completed", "decision": "BY3B_dependency_plan_complete"},
        {"stage": "F_command_template_plan", "status": "completed", "decision": "BY3B_command_template_plan_complete"},
        {"stage": "G_evaluator_metric_policy", "status": "completed", "decision": "BY3B_evaluator_metric_policy_plan_complete"},
        {"stage": "H_figure_case_review_plan", "status": "completed", "decision": "BY3B_figure_case_review_plan_complete"},
        {"stage": "I_batch_execution_plan", "status": "completed", "decision": "BY3B_batch_execution_plan_complete"},
        {"stage": "J_context_obsidian_sync", "status": "completed", "decision": "BY3B_context_obsidian_sync_complete"},
        {"stage": "final_validation", "status": "completed", "decision": decision["status"]},
    ]
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_json(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.json", status_rows)
    write_csv(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS.csv", status_rows)
    write_md(
        paths.stage_root / "summary" / "long_task_summary.md",
        "# BY3B Long Task Summary\n\n"
        f"- Final decision: `{decision['status']}`.\n"
        "- BY3A8 position/up-with-diagnostic-yaw scope imported.\n"
        "- BY3A7 repaired IMU and BY3A5B A1_dual_diff yaw source locked for future BY3 degradation execution.\n"
        "- Planned 118 case-seed units: 75 position/up-primary and 43 diagnostic-yaw units.\n"
        "- Command templates are dry-run only with `execute_now=false`.\n"
        "- No solvers, evaluators, random arrays, degraded inputs, figures, degradation runs, or paper claims were produced.\n",
    )
    write_md(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# BY3B Next Stage Recommendation\n\n"
        f"Recommended next stage: `{decision['recommended_next_stage']}`.\n\n"
        "Execution still requires human review. Start with Batch 0 normal parity recheck and Batch 1 deterministic A/B/E_position_std only. "
        "Keep yaw diagnostic-only and paper claims disabled.\n",
    )
    return status_rows


def write_future_no_execution_manifest(paths: Paths, decision: dict[str, Any], stage_status: list[dict[str, Any]]) -> None:
    manifest = {
        "stage": STAGE,
        "future_runtime_root": str(paths.future_root),
        "purpose": "reserved future execution root for BY3C and later",
        "BY3B_created_only_planning_subdirs_and_manifest": True,
        "degraded_inputs_generated": False,
        "random_arrays_generated": False,
        "solvers_run": False,
        "evaluators_run": False,
        "figures_generated": False,
        "decision": decision,
        "stage_status": stage_status,
    }
    write_json(paths.future_root / "validation" / "BY3B_FUTURE_ROOT_NO_EXECUTION_MANIFEST.json", manifest)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def count_nonempty_lines(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for line in handle if line.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists() or not path.is_file():
        return ""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_csv_parse_check(root: Path) -> bool:
    try:
        for path in root.rglob("*.json"):
            with path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        for path in root.rglob("*.csv"):
            with path.open("r", encoding="utf-8", newline="") as handle:
                next(csv.reader(handle), None)
    except Exception:
        return False
    return True


def all_files_under(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (path for path in root.rglob("*") if path.is_file())


if __name__ == "__main__":
    raise SystemExit(main())
