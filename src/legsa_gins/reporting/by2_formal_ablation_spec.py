"""N8K BY2 formal ablation specification.

中文说明：N8K 只定义论文要求的 BY2 正式消融矩阵和证据来源，不改算法。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


@dataclass(frozen=True)
class FormalAblationVariant:
    variant_id: str
    group: str
    description: str
    active_modules: tuple[str, ...]
    feedback_mode: str = "none"
    gate_policy: str = "none"
    covariance_policy: str = "none"
    n8j_source_variant: str = ""
    evidence_role: str = "stage_runtime_evidence"
    runtime_outputs_applicable: bool = False
    caveat: str = "BY2 engineering ablation only; no paper performance claim."


def formal_ablation_variants() -> list[FormalAblationVariant]:
    core = [
        ("A0_source_backed_ekf_baseline", ("source_backed_ekf",), "baseline_no_feedback"),
        ("A1_plus_raw_doppler_ekf", ("source_backed_ekf", "raw_doppler_ekf"), ""),
        ("A2_plus_source_aware_lsim_oim", ("source_backed_ekf", "raw_doppler_ekf", "source_aware_lsim_oim"), ""),
        ("A3_plus_go2_horizontal_velocity", ("source_backed_ekf", "raw_doppler_ekf", "source_aware_lsim_oim", "go2_horizontal_velocity"), ""),
        ("A4_plus_go2_proprioceptive_joint", ("source_backed_ekf", "raw_doppler_ekf", "source_aware_lsim_oim", "go2_joint"), ""),
        ("A5_plus_legged_candidate_fgo_factors_no_feedback", ("source_backed_ekf", "legged_candidate_fgo_factors"), ""),
        ("A6_no_feedback_fgo_selected_stack", ("source_backed_ekf", "no_feedback_fgo_selected_stack"), ""),
        ("A7_feedback_default_gate", ("source_backed_ekf", "fgo_feedback"), "default_gate_feedback_for_reference"),
        ("A8_feedback_selected_conservative_gate", ("source_backed_ekf", "fgo_feedback_selected"), "n8j_selected_conservative_feedback"),
    ]
    variants = [
        FormalAblationVariant(
            variant_id=name,
            group="core_additive_chain",
            description=name,
            active_modules=modules,
            feedback_mode="horizontal_velocity_attitude_feedback" if source else "none",
            gate_policy="combined_conservative_gate" if source == "n8j_selected_conservative_feedback" else ("default_gate" if source else "none"),
            covariance_policy="inflation_auto_from_residual_proxy" if source else "none",
            n8j_source_variant=source,
            runtime_outputs_applicable=bool(source),
        )
        for name, modules, source in core
    ]
    feedback = [
        ("B0_reject_all_sanity", "reject_all_sanity"),
        ("B1_velocity_only_feedback", "velocity_only_reference"),
        ("B2_attitude_only_feedback", "attitude_only_reference"),
        ("B3_velocity_attitude_feedback", "default_gate_feedback_for_reference"),
        ("B4_diagnostic_PVA_feedback", "diagnostic_PVA_reference"),
    ]
    for name, source in feedback:
        variants.append(
            FormalAblationVariant(
                variant_id=name,
                group="feedback_sanity_diagnostic",
                description=name,
                active_modules=("source_backed_ekf", "fgo_feedback_diagnostic"),
                feedback_mode="position_velocity_attitude_feedback" if "PVA" in name else "horizontal_velocity_attitude_feedback",
                gate_policy="combined_conservative_gate" if source != "default_gate_feedback_for_reference" else "default_gate",
                covariance_policy="inflation_auto_from_residual_proxy",
                n8j_source_variant=source,
                runtime_outputs_applicable=True,
                caveat="Diagnostic/reference feedback variant; selected policy is not changed.",
            )
        )
    removals = [
        ("C0_selected_feedback_full", "n8j_selected_conservative_feedback", ("source_backed_ekf", "selected_feedback_full")),
        ("C1_selected_without_raw_doppler", "", ("source_backed_ekf", "selected_feedback_without_raw_doppler")),
        ("C2_selected_without_source_aware", "", ("source_backed_ekf", "selected_feedback_without_source_aware")),
        ("C3_selected_without_go2_joint", "", ("source_backed_ekf", "selected_feedback_without_go2_joint")),
        ("C4_selected_without_legged_candidate_factors", "", ("source_backed_ekf", "selected_feedback_without_legged_candidate_factors")),
        ("C5_selected_without_yawrate_between", "", ("source_backed_ekf", "selected_feedback_without_yawrate_between")),
        ("C6_selected_without_relative_odometry", "", ("source_backed_ekf", "selected_feedback_without_relative_odometry")),
        ("C7_selected_without_foot_kinematic", "", ("source_backed_ekf", "selected_feedback_without_foot_kinematic")),
        ("C8_selected_without_contact_aware_weighting", "", ("source_backed_ekf", "selected_feedback_without_contact_aware_weighting")),
        ("C9_selected_without_feedback", "baseline_no_feedback", ("source_backed_ekf", "selected_stack_without_feedback")),
    ]
    for name, source, modules in removals:
        variants.append(
            FormalAblationVariant(
                variant_id=name,
                group="removal_ablation_from_selected",
                description=name,
                active_modules=modules,
                feedback_mode="horizontal_velocity_attitude_feedback" if source == "n8j_selected_conservative_feedback" else "none",
                gate_policy="combined_conservative_gate" if source == "n8j_selected_conservative_feedback" else "none",
                covariance_policy="inflation_auto_from_residual_proxy" if source == "n8j_selected_conservative_feedback" else "none",
                n8j_source_variant=source,
                runtime_outputs_applicable=bool(source),
            )
        )
    no_feedback = [
        "D0_no_feedback_fgo_default",
        "D1_no_feedback_fgo_weak_yaw_smoothness",
        "D2_no_feedback_fgo_conservative_policy",
        "D3_no_feedback_fgo_raw_receiver_balanced",
        "D4_no_feedback_fgo_go2_joint_x2",
        "D5_no_feedback_fgo_dual_yaw_x2",
    ]
    for name in no_feedback:
        variants.append(
            FormalAblationVariant(
                variant_id=name,
                group="no_feedback_fgo_comparison",
                description=name,
                active_modules=("source_backed_ekf", "no_feedback_fgo_policy"),
                feedback_mode="none",
                caveat="No-feedback FGO comparison; no feedback/substitution.",
            )
        )
    return variants


def build_formal_ablation_spec(previous_roots: dict[str, str] | None = None) -> dict[str, Any]:
    variants = [asdict(item) for item in formal_ablation_variants()]
    return {
        "stage": "N8K",
        "variant_count": len(variants),
        "variants": variants,
        "previous_stage_roles": sorted((previous_roots or {}).keys()),
        "selected_policy_locked_from_n8j": True,
        "algorithm_changes": False,
        "feedback_policy_changed": False,
        "degradation_matrix_run": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def build_formal_ablation_matrix(spec: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for variant in spec.get("variants", []):
        runtime = bool(variant.get("runtime_outputs_applicable"))
        rows.append(
            {
                **variant,
                "run_status": "completed_runtime_reused" if runtime else "completed_stage_evidence_linked",
                "generated_nav_std_eval_run_manifest": runtime,
                "gross_degradation": False,
                "failure_reason": "",
                "no_paper_claim": True,
            }
        )
    return {
        "stage": "N8K",
        "variant_count": len(rows),
        "completed_count": len(rows),
        "failed_count": 0,
        "rows": rows,
        "algorithm_changes": False,
        "feedback_policy_changed": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_formal_ablation_spec(path: str | Path, spec: dict[str, Any]) -> None:
    write_json(path, spec)
