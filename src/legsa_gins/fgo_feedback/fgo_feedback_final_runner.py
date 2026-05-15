"""N8J final feedback validation runner helpers.

中文说明：N8J 只复现 selected policy 和固定 reference variants，不做大范围调参。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import locate_clean_inputs

from .fgo_feedback_evaluator import evaluate_variant_against_baseline
from .fgo_feedback_gate import apply_feedback_gate
from .fgo_feedback_observation import build_feedback_observations, write_feedback_observations
from .fgo_feedback_policy_ablation_runner import (
    N8G_REPORT_NAMES,
    N8H_REPORT_NAMES,
    _apply_policy_covariance,
    _load_named_reports,
    _policy_report,
    _residual_proxy_from_reports,
    _run_policy,
    _variant_entry,
    policy_trace_stats,
)
from .fgo_feedback_policy_grid import FeedbackPolicySpec
from .fgo_feedback_visual_loader import read_csv_rows, read_json, safe_int, write_json
from .sliding_window_manager import build_sliding_windows, read_eval_nav_csv, read_first_column_times


N8I_REPORT_NAMES = [
    "N8I_FEEDBACK_POLICY_GRID.json",
    "FGO_FEEDBACK_GATE_POLICY_REVIEW_REPORT.json",
    "FGO_FEEDBACK_COVARIANCE_REFINEMENT_REPORT.json",
    "FGO_FEEDBACK_WINDOW_POLICY_REVIEW_REPORT.json",
    "N8I_FEEDBACK_MODE_ABLATION_SUMMARIES.json",
    "N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json",
]


@dataclass
class N8JFinalRunBundle:
    output_root: Path
    baseline_eval_nav: Path
    policy_summaries: dict[str, dict[str, Any]]
    evaluation_by_policy: dict[str, dict[str, Any]]
    gate_reports: dict[str, dict[str, Any]]
    covariance_reports: dict[str, dict[str, Any]]
    window_reports: dict[str, dict[str, Any]]
    observation_reports: dict[str, dict[str, Any]]
    trace_rows: dict[str, list[dict[str, Any]]]
    n8i_reports: dict[str, dict[str, Any]]
    n8g_reports: dict[str, dict[str, Any]]
    n8h_reports: dict[str, dict[str, Any]]


def final_variant_specs() -> list[FeedbackPolicySpec]:
    return [
        FeedbackPolicySpec(
            "baseline_no_feedback",
            "baseline_no_feedback",
            "no_feedback_baseline",
            position_enabled=False,
            velocity_enabled=False,
            attitude_enabled=False,
            covariance_policy="none",
            covariance_inflation=1.0,
            gate_policy="none",
            run_feedback=False,
        ),
        FeedbackPolicySpec(
            "n8j_selected_conservative_feedback",
            "horizontal_velocity_attitude_primary",
            "horizontal_velocity_attitude_feedback",
            position_enabled=False,
            velocity_enabled=True,
            attitude_enabled=True,
            gate_policy="combined_conservative_gate",
            covariance_policy="inflation_auto_from_residual_proxy",
        ),
        FeedbackPolicySpec(
            "default_gate_feedback_for_reference",
            "horizontal_velocity_attitude_primary",
            "horizontal_velocity_attitude_feedback",
            position_enabled=False,
            velocity_enabled=True,
            attitude_enabled=True,
            gate_policy="default_gate",
            covariance_policy="inflation_auto_from_residual_proxy",
            diagnostic_only=True,
        ),
        FeedbackPolicySpec(
            "reject_all_sanity",
            "horizontal_velocity_attitude_primary",
            "horizontal_velocity_attitude_feedback",
            position_enabled=False,
            velocity_enabled=True,
            attitude_enabled=True,
            gate_policy="combined_conservative_gate",
            covariance_policy="inflation_auto_from_residual_proxy",
            reject_all=True,
            diagnostic_only=True,
        ),
        FeedbackPolicySpec(
            "velocity_only_reference",
            "velocity_only",
            "velocity_only_feedback",
            position_enabled=False,
            velocity_enabled=True,
            attitude_enabled=False,
            gate_policy="combined_conservative_gate",
            covariance_policy="inflation_auto_from_residual_proxy",
            diagnostic_only=True,
        ),
        FeedbackPolicySpec(
            "attitude_only_reference",
            "attitude_only",
            "attitude_only_feedback",
            position_enabled=False,
            velocity_enabled=False,
            attitude_enabled=True,
            gate_policy="combined_conservative_gate",
            covariance_policy="inflation_auto_from_residual_proxy",
            diagnostic_only=True,
        ),
        FeedbackPolicySpec(
            "diagnostic_PVA_reference",
            "PVA_diagnostic",
            "position_velocity_attitude_feedback",
            position_enabled=True,
            velocity_enabled=True,
            attitude_enabled=True,
            gate_policy="combined_conservative_gate",
            covariance_policy="inflation_auto_from_residual_proxy",
            diagnostic_only=True,
        ),
    ]


def run_final_feedback_variants(
    *,
    n8i_root: str | Path,
    n8h_root: str | Path,
    n8g_root: str | Path,
    n8f1_root: str | Path,
    clean_root: str | Path,
    dual_root: str | Path,
    build_dir: str | Path,
    exe: str | Path,
    output_dir: str | Path,
    allow_run: bool,
    cwd: str | Path,
) -> N8JFinalRunBundle:
    del n8f1_root, dual_root, build_dir
    if not allow_run:
        raise RuntimeError("--allow-run is required for N8J final validation")
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    clean_inputs = locate_clean_inputs(clean_root)
    if clean_inputs.get("clean_input_missing"):
        raise RuntimeError("clean input missing for N8J final validation")

    n8i_reports = _load_named_reports(n8i_root, N8I_REPORT_NAMES)
    n8g_reports = _load_named_reports(n8g_root, N8G_REPORT_NAMES)
    n8h_reports = _load_named_reports(n8h_root, N8H_REPORT_NAMES)
    residual_proxy = _residual_proxy_from_reports(n8g_reports, n8h_reports)
    specs = final_variant_specs()
    baseline = specs[0]
    baseline_summary = _run_policy(
        exe=exe,
        clean_inputs=clean_inputs,
        output_root=output_root,
        policy=baseline,
        observations_path=None,
        allow_run=allow_run,
        cwd=Path(cwd),
    )
    baseline_eval = output_root / "variants" / baseline.policy_id / "run" / "EVAL_NAV.csv"
    samples = read_eval_nav_csv(baseline_eval)
    gnss_times = read_first_column_times(clean_inputs["gnss_path"])
    origin = samples[0]

    summaries = {baseline.policy_id: _final_summary(baseline_summary, baseline)}
    evaluations: dict[str, dict[str, Any]] = {}
    gate_reports: dict[str, dict[str, Any]] = {}
    covariance_reports: dict[str, dict[str, Any]] = {}
    window_reports: dict[str, dict[str, Any]] = {}
    observation_reports: dict[str, dict[str, Any]] = {}
    trace_rows: dict[str, list[dict[str, Any]]] = {
        baseline.policy_id: read_csv_rows(output_root / "variants" / baseline.policy_id / "run" / "FGO_FEEDBACK_UPDATE_TRACE.csv")
    }

    for policy in specs[1:]:
        windows, window_report = build_sliding_windows(
            samples,
            candidate_feedback_times=gnss_times,
            window_duration_s=policy.window_duration_s,
            feedback_stride_s=policy.feedback_stride_s,
            min_epoch_count=policy.thresholds().min_window_epoch_count,
        )
        raw_obs, observation_report = build_feedback_observations(
            samples,
            windows,
            mode=policy.feedback_mode,
            origin=origin,
            residual_proxy_p95=residual_proxy,
        )
        cov_obs, covariance_report = _apply_policy_covariance(raw_obs, policy, residual_proxy)
        gated_obs, gate_report = apply_feedback_gate(
            cov_obs,
            samples,
            origin=origin,
            thresholds=policy.thresholds(),
            position_enabled=policy.position_enabled,
            velocity_enabled=policy.velocity_enabled,
            attitude_enabled=policy.attitude_enabled,
            reject_all=policy.reject_all,
        )
        variant_root = output_root / "variants" / policy.policy_id
        obs_path = variant_root / "FGO_FEEDBACK_OBSERVATIONS.csv"
        write_feedback_observations(obs_path, gated_obs)
        write_json(variant_root / "WINDOW_POLICY_REPORT.json", _policy_report(window_report, policy))
        write_json(variant_root / "OBSERVATION_BUILD_REPORT.json", _policy_report(observation_report, policy))
        write_json(variant_root / "COVARIANCE_POLICY_REPORT.json", _policy_report(covariance_report, policy))
        write_json(variant_root / "GATE_POLICY_REPORT.json", _policy_report(gate_report, policy))
        summary = _run_policy(
            exe=exe,
            clean_inputs=clean_inputs,
            output_root=output_root,
            policy=policy,
            observations_path=obs_path,
            allow_run=allow_run,
            cwd=Path(cwd),
        )
        manifest = read_json(output_root / "variants" / policy.policy_id / "run" / "RUN_MANIFEST.json")
        evaluations[policy.policy_id] = evaluate_variant_against_baseline(
            baseline_eval,
            output_root / "variants" / policy.policy_id / "run" / "EVAL_NAV.csv",
            variant_id=policy.policy_id,
            manifest=manifest,
        )
        summaries[policy.policy_id] = _final_summary(summary, policy)
        gate_reports[policy.policy_id] = _policy_report(gate_report, policy)
        covariance_reports[policy.policy_id] = _policy_report(covariance_report, policy)
        window_reports[policy.policy_id] = _policy_report(window_report, policy)
        observation_reports[policy.policy_id] = _policy_report(observation_report, policy)
        trace_rows[policy.policy_id] = read_csv_rows(output_root / "variants" / policy.policy_id / "run" / "FGO_FEEDBACK_UPDATE_TRACE.csv")

    return N8JFinalRunBundle(
        output_root=output_root,
        baseline_eval_nav=baseline_eval,
        policy_summaries=summaries,
        evaluation_by_policy=evaluations,
        gate_reports=gate_reports,
        covariance_reports=covariance_reports,
        window_reports=window_reports,
        observation_reports=observation_reports,
        trace_rows=trace_rows,
        n8i_reports=n8i_reports,
        n8g_reports=n8g_reports,
        n8h_reports=n8h_reports,
    )


def build_final_variant_summaries(bundle: N8JFinalRunBundle) -> dict[str, Any]:
    variants = [_final_variant_entry(bundle, spec.policy_id) for spec in final_variant_specs() if spec.policy_id in bundle.policy_summaries]
    reject = next((item for item in variants if item["policy_id"] == "reject_all_sanity"), {})
    reject_passed = bool(
        reject
        and reject.get("feedback_accept_count") == 0
        and reject.get("baseline_delta", {}).get("horizontal_m", {}).get("max", 1.0) <= 1.0e-9
        and reject.get("baseline_delta", {}).get("yaw_deg", {}).get("max", 1.0) <= 1.0e-9
    )
    return {
        "stage": "N8J",
        "variant_count": len(variants),
        "variants": variants,
        "baseline_variant": "baseline_no_feedback",
        "selected_feedback_variant": "n8j_selected_conservative_feedback",
        "reference_variants": [
            "default_gate_feedback_for_reference",
            "reject_all_sanity",
            "velocity_only_reference",
            "attitude_only_reference",
            "diagnostic_PVA_reference",
        ],
        "reject_all_sanity_passed": reject_passed,
        "feedback_update_count_total": sum(safe_int(item.get("feedback_update_count")) for item in variants),
        "feedback_accept_count_total": sum(safe_int(item.get("feedback_accept_count")) for item in variants),
        "feedback_reject_count_total": sum(safe_int(item.get("feedback_reject_count")) for item in variants),
        "gross_degradation_present": any(item.get("gross_degradation") for item in variants),
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def build_final_comparison_report(bundle: N8JFinalRunBundle) -> dict[str, Any]:
    selected = bundle.evaluation_by_policy.get("n8j_selected_conservative_feedback", {})
    default = bundle.evaluation_by_policy.get("default_gate_feedback_for_reference", {})
    reject = bundle.evaluation_by_policy.get("reject_all_sanity", {})
    return {
        "stage": "N8J",
        "metric_namespace": "feedback_vs_baseline_delta",
        "selected_feedback_variant": "n8j_selected_conservative_feedback",
        "selected_feedback_delta": selected.get("feedback_vs_baseline_delta", {}),
        "default_gate_reference_delta": default.get("feedback_vs_baseline_delta", {}),
        "reject_all_sanity_delta": reject.get("feedback_vs_baseline_delta", {}),
        "selected_gross_degradation": bool(selected.get("clean_gross_degradation", False)),
        "default_gate_gross_degradation": bool(default.get("clean_gross_degradation", False)),
        "reject_all_gross_degradation": bool(reject.get("clean_gross_degradation", False)),
        "reference_evaluation_only": True,
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def final_policy_trace_stats(bundle: N8JFinalRunBundle, policy_id: str) -> dict[str, Any]:
    return policy_trace_stats(bundle, policy_id)


def _final_variant_entry(bundle: N8JFinalRunBundle, policy_id: str) -> dict[str, Any]:
    entry = _variant_entry(bundle, policy_id)
    summary = bundle.policy_summaries.get(policy_id, {})
    entry.update(
        {
            "stage": "N8J",
            "nav_generated": bool(summary.get("nav_generated")),
            "std_generated": bool(summary.get("std_generated")),
            "eval_nav_generated": bool(summary.get("eval_nav_generated")),
            "run_manifest_generated": bool(summary.get("run_manifest_generated")),
            "runtime_outputs_generated": bool(summary.get("runtime_outputs_generated")),
            "runtime_artifacts_committed": False,
            "selected_variant": policy_id == "n8j_selected_conservative_feedback",
            "reference_only": bool(summary.get("reference_only")),
            "policy_locked_from_n8i": bool(summary.get("policy_locked_from_n8i")),
        }
    )
    return entry


def _final_summary(summary: dict[str, Any], policy: FeedbackPolicySpec) -> dict[str, Any]:
    out = dict(summary)
    out.update(
        {
            "stage": "N8J",
            "policy_id": policy.policy_id,
            "selected_variant": policy.policy_id == "n8j_selected_conservative_feedback",
            "reference_only": policy.diagnostic_only,
            "policy_locked_from_n8i": policy.policy_id == "n8j_selected_conservative_feedback",
            "runtime_outputs_generated": bool(out.get("nav_generated")) and bool(out.get("std_generated")) and bool(out.get("eval_nav_generated")) and bool(out.get("run_manifest_generated")),
            "runtime_artifacts_committed": False,
        }
    )
    return out
