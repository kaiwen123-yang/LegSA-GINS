"""N8G FGO feedback EKF foundation runner.

中文说明：runner 负责 runtime-only 联合滤波原型，不把 FGO 输出替换为 NAV。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import (
    locate_clean_inputs,
    run_port_core,
    write_port_clean_config,
)

from .feedback_state_types import FeedbackGateThresholds, FeedbackVariantSpec, NavStateSample
from .fgo_feedback_covariance_policy import apply_conservative_covariance_policy, write_covariance_policy_report
from .fgo_feedback_decision import build_n8g_decision_report, write_decision_report
from .fgo_feedback_ekf_interface import append_feedback_config
from .fgo_feedback_evaluator import build_evaluation_report, evaluate_variant_against_baseline, write_evaluation_report
from .fgo_feedback_gate import apply_feedback_gate, write_gate_report
from .fgo_feedback_manifest import summarize_variant_manifest
from .fgo_feedback_observation import build_feedback_observations, write_feedback_observations, write_observation_report
from .fgo_feedback_visual_plots import generate_n8g_figures
from .sliding_window_manager import build_sliding_windows, read_eval_nav_csv, read_first_column_times, write_sliding_window_report


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_n8f_residual_proxy(n8f_root: str | Path) -> float:
    path = Path(n8f_root) / "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json"
    if not path.exists():
        return 1.0
    data = json.loads(path.read_text(encoding="utf-8"))
    variants = data.get("variants", [])
    for item in variants:
        if item.get("variant") == "all_legged_candidate_stack":
            return float(item.get("candidate_whitened_residual_p95", item.get("residual_proxy_p95", 1.0)) or 1.0)
    return float(variants[0].get("residual_proxy_p95", 1.0) if variants else 1.0)


def n8g_variant_specs() -> list[FeedbackVariantSpec]:
    return [
        FeedbackVariantSpec("ekf_baseline_no_fgo_feedback", "no_feedback_baseline"),
        FeedbackVariantSpec("fgo_feedback_velocity_attitude", "velocity_attitude_feedback", velocity_enabled=True, attitude_enabled=True),
        FeedbackVariantSpec(
            "fgo_feedback_horizontal_velocity_attitude",
            "horizontal_velocity_attitude_feedback",
            velocity_enabled=True,
            attitude_enabled=True,
        ),
        FeedbackVariantSpec(
            "fgo_feedback_position_velocity_attitude_diagnostic",
            "position_velocity_attitude_feedback",
            position_enabled=True,
            velocity_enabled=True,
            attitude_enabled=True,
            diagnostic_only=True,
        ),
        FeedbackVariantSpec("fgo_feedback_velocity_only", "velocity_only_feedback", velocity_enabled=True),
        FeedbackVariantSpec("fgo_feedback_attitude_only", "attitude_only_feedback", attitude_enabled=True),
        FeedbackVariantSpec("fgo_feedback_reject_all_sanity", "velocity_attitude_feedback", velocity_enabled=True, attitude_enabled=True, reject_all=True),
    ]


def _run_variant(
    *,
    exe: str | Path,
    clean_inputs: dict[str, Any],
    output_root: Path,
    spec: FeedbackVariantSpec,
    observations_path: Path | None,
    allow_run: bool,
    cwd: Path,
) -> dict[str, Any]:
    variant_root = output_root / "variants" / spec.variant_id
    config_info = write_port_clean_config(clean_inputs, variant_root)
    config_path = Path(config_info["config_path"])
    if observations_path is not None:
        append_feedback_config(
            config_path,
            observation_path=observations_path,
            variant=spec,
            thresholds=FeedbackGateThresholds(),
        )
    run_dir = variant_root / "run"
    run_result = run_port_core(exe, config_path, run_dir, allow_run=allow_run, cwd=cwd)
    if run_result.get("returncode") not in (0, None):
        raise RuntimeError(f"N8G variant {spec.variant_id} failed: {run_result.get('stderr')}")
    summary = summarize_variant_manifest(spec.variant_id, run_dir)
    summary.update(
        {
            "feedback_mode": spec.feedback_mode,
            "position_enabled": spec.position_enabled,
            "velocity_enabled": spec.velocity_enabled,
            "attitude_enabled": spec.attitude_enabled,
            "reject_all": spec.reject_all,
            "diagnostic_only": spec.diagnostic_only,
            "config_path_role": "runtime_generated_config",
        }
    )
    return summary


def run_n8g_feedback_foundation(
    *,
    n8f_root: str | Path,
    n8f1_root: str | Path,
    n8e_root: str | Path,
    n8d_root: str | Path,
    n8c3_root: str | Path,
    n7c6_root: str | Path,
    clean_root: str | Path,
    dual_root: str | Path,
    build_dir: str | Path,
    exe: str | Path,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    allow_run: bool,
    cwd: str | Path,
) -> dict[str, Any]:
    del n8f1_root, n8e_root, n8d_root, n8c3_root, n7c6_root, dual_root, build_dir
    output_root = Path(output_dir)
    figure_root = Path(figure_output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    figure_root.mkdir(parents=True, exist_ok=True)
    clean_inputs = locate_clean_inputs(clean_root)
    if clean_inputs.get("clean_input_missing"):
        raise RuntimeError("clean input missing for N8G feedback run")

    specs = n8g_variant_specs()
    baseline_summary = _run_variant(
        exe=exe,
        clean_inputs=clean_inputs,
        output_root=output_root,
        spec=specs[0],
        observations_path=None,
        allow_run=allow_run,
        cwd=Path(cwd),
    )
    baseline_eval = output_root / "variants" / specs[0].variant_id / "run" / "EVAL_NAV.csv"
    samples = read_eval_nav_csv(baseline_eval)
    gnss_times = read_first_column_times(clean_inputs["gnss_path"])
    windows, window_report = build_sliding_windows(
        samples,
        candidate_feedback_times=gnss_times,
        window_duration_s=5.0,
        feedback_stride_s=1.0,
        min_epoch_count=3,
    )
    write_sliding_window_report(output_root / "SLIDING_WINDOW_MANAGER_REPORT.json", window_report)
    residual_proxy = _load_n8f_residual_proxy(n8f_root)
    origin = samples[0]
    primary_reports: dict[str, Any] = {}
    variant_summaries = [baseline_summary]
    evaluation_results: list[dict[str, Any]] = []
    primary_variant_id = "fgo_feedback_horizontal_velocity_attitude"
    for spec in specs[1:]:
        raw_obs, observation_report = build_feedback_observations(
            samples,
            windows,
            mode=spec.feedback_mode,
            origin=origin,
            residual_proxy_p95=residual_proxy,
        )
        cov_obs, covariance_report = apply_conservative_covariance_policy(raw_obs, residual_proxy_p95=residual_proxy)
        gated_obs, gate_report = apply_feedback_gate(
            cov_obs,
            samples,
            origin=origin,
            thresholds=FeedbackGateThresholds(),
            position_enabled=spec.position_enabled,
            velocity_enabled=spec.velocity_enabled,
            attitude_enabled=spec.attitude_enabled,
            reject_all=spec.reject_all,
        )
        obs_path = output_root / "variants" / spec.variant_id / "FGO_FEEDBACK_OBSERVATIONS.csv"
        write_feedback_observations(obs_path, gated_obs)
        if spec.variant_id == primary_variant_id:
            write_feedback_observations(output_root / "FGO_FEEDBACK_OBSERVATIONS.csv", gated_obs)
            write_observation_report(output_root / "FGO_FEEDBACK_OBSERVATION_BUILD_REPORT.json", observation_report)
            write_covariance_policy_report(output_root / "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json", covariance_report)
            write_gate_report(output_root / "FGO_FEEDBACK_GATE_REPORT.json", gate_report)
            primary_reports = {
                "observation": observation_report,
                "covariance": covariance_report,
                "gate": gate_report,
            }
        summary = _run_variant(
            exe=exe,
            clean_inputs=clean_inputs,
            output_root=output_root,
            spec=spec,
            observations_path=obs_path,
            allow_run=allow_run,
            cwd=Path(cwd),
        )
        variant_summaries.append(summary)
        manifest_path = output_root / "variants" / spec.variant_id / "run" / "RUN_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        evaluation_results.append(
            evaluate_variant_against_baseline(
                baseline_eval,
                output_root / "variants" / spec.variant_id / "run" / "EVAL_NAV.csv",
                variant_id=spec.variant_id,
                manifest=manifest,
            )
        )

    variant_report = {
        "stage": "N8G",
        "variant_count": len(variant_summaries),
        "variants": variant_summaries,
        "feedback_update_count_total": sum(int(item.get("feedback_update_count", 0) or 0) for item in variant_summaries),
        "feedback_accept_count_total": sum(int(item.get("feedback_accept_count", 0) or 0) for item in variant_summaries),
        "feedback_reject_count_total": sum(int(item.get("feedback_reject_count", 0) or 0) for item in variant_summaries),
        "baseline_variant": specs[0].variant_id,
        "primary_feedback_variant": primary_variant_id,
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    _write_json(output_root / "N8G_FGO_FEEDBACK_VARIANT_SUMMARIES.json", variant_report)
    evaluation_report = build_evaluation_report(evaluation_results)
    write_evaluation_report(output_root / "N8G_FGO_FEEDBACK_EVALUATION_REPORT.json", evaluation_report)
    comparison_report = {
        "stage": "N8G",
        "baseline_variant": specs[0].variant_id,
        "feedback_variants": [spec.variant_id for spec in specs[1:]],
        "gross_degradation_status": evaluation_report["gross_degradation_status"],
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    _write_json(output_root / "N8G_FGO_FEEDBACK_COMPARISON_REPORT.json", comparison_report)
    decision_report = build_n8g_decision_report(
        observation_report=primary_reports.get("observation", {"feedback_rows": 0}),
        variant_report=variant_report,
        evaluation_report=evaluation_report,
    )
    write_decision_report(output_root / "N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json", decision_report)
    figure_manifest = generate_n8g_figures(
        figure_output_dir=figure_root,
        window_report=window_report,
        gate_report=primary_reports.get("gate", {}),
        evaluation_report=evaluation_report,
        decision_report=decision_report,
    )
    _write_json(output_root / "N8G_FIGURE_MANIFEST.json", figure_manifest)
    primary_run = output_root / "variants" / primary_variant_id / "run"
    for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]:
        src = primary_run / name
        if src.exists():
            shutil.copyfile(src, output_root / name)
    _write_case_review(output_root / "n8g_fgo_feedback_ekf_case_review.md", decision_report, variant_report, window_report)
    result = {
        "stage": "N8G",
        "status": decision_report["status"],
        "output_dir": str(output_root),
        "figure_output_dir": str(figure_root),
        "window_count": window_report["window_count"],
        "feedback_rows": primary_reports.get("observation", {}).get("feedback_rows", 0),
        "feedback_accept_count": variant_report["feedback_accept_count_total"],
        "feedback_reject_count": variant_report["feedback_reject_count_total"],
        "figure_count": figure_manifest["figure_count_total"],
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "no_future_data": True,
        "paper_performance_claim": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _write_case_review(path: Path, decision: dict[str, Any], variant: dict[str, Any], window: dict[str, Any]) -> None:
    lines = [
        "# N8G FGO Feedback EKF Case Review",
        "",
        "N8G introduces controlled FGO feedback to the EKF as a pseudo-measurement/error-state correction.",
        "",
        f"- decision: `{decision.get('status')}`",
        f"- recommended next stage: `{decision.get('recommended_next_stage')}`",
        f"- window count: `{window.get('window_count')}`",
        f"- feedback updates: `{variant.get('feedback_update_count_total')}`",
        f"- accepted/rejected: `{variant.get('feedback_accept_count_total')}` / `{variant.get('feedback_reject_count_total')}`",
        "",
        "Boundary: no output substitution, no direct NAV overwrite, no future-data feedback, no trace/final_v23 tuning, and no paper performance claim.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
