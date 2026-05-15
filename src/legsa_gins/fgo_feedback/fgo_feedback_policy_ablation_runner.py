"""N8I policy-ablation replay runner helpers.

中文说明：这里实际生成 feedback pseudo-measurement 并跑 EKF replay；策略选择只
使用 solver 可见 correction/gate/residual 诊断，不使用 trace 或 final_v23 调参。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import (
    locate_clean_inputs,
    run_port_core,
    write_port_clean_config,
)

from .feedback_state_types import FeedbackObservation
from .fgo_feedback_covariance_policy import apply_conservative_covariance_policy
from .fgo_feedback_ekf_interface import append_feedback_config
from .fgo_feedback_evaluator import build_evaluation_report, evaluate_variant_against_baseline
from .fgo_feedback_gate import apply_feedback_gate
from .fgo_feedback_manifest import summarize_variant_manifest
from .fgo_feedback_observation import build_feedback_observations, write_feedback_observations
from .fgo_feedback_policy_grid import (
    FeedbackPolicySpec,
    build_covariance_sweep_specs,
    build_gate_sweep_specs,
    build_mode_ablation_specs,
    build_window_policy_specs,
)
from .fgo_feedback_visual_loader import read_csv_rows, read_json, safe_float, safe_int, stats, write_json
from .sliding_window_manager import build_sliding_windows, read_eval_nav_csv, read_first_column_times


@dataclass
class N8IPolicyRunBundle:
    output_root: Path
    baseline_eval_nav: Path
    policy_summaries: dict[str, dict[str, Any]]
    evaluation_by_policy: dict[str, dict[str, Any]]
    gate_reports: dict[str, dict[str, Any]]
    covariance_reports: dict[str, dict[str, Any]]
    window_reports: dict[str, dict[str, Any]]
    observation_reports: dict[str, dict[str, Any]]
    trace_rows: dict[str, list[dict[str, Any]]]
    n8g_reports: dict[str, dict[str, Any]]
    n8h_reports: dict[str, dict[str, Any]]


N8H_REPORT_NAMES = [
    "N8H_VISUAL_INPUT_MANIFEST.json",
    "FGO_FEEDBACK_POSITION_DISABLED_AUDIT_REPORT.json",
    "N8H_FEEDBACK_VARIANT_ABLATION_REVIEW.json",
    "FGO_FEEDBACK_GATE_VISUAL_REVIEW_REPORT.json",
    "FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json",
    "N8H_FGO_FEEDBACK_VISUAL_DECISION_REPORT.json",
]

N8G_REPORT_NAMES = [
    "SLIDING_WINDOW_MANAGER_REPORT.json",
    "FGO_FEEDBACK_GATE_REPORT.json",
    "FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json",
    "N8G_FGO_FEEDBACK_EVALUATION_REPORT.json",
    "N8G_FGO_FEEDBACK_EKF_DECISION_REPORT.json",
]


def run_policy_ablation_matrix(
    *,
    n8g_root: str | Path,
    n8h_root: str | Path,
    n8f1_root: str | Path,
    n8f_root: str | Path,
    clean_root: str | Path,
    dual_root: str | Path,
    build_dir: str | Path,
    exe: str | Path,
    output_dir: str | Path,
    allow_run: bool,
    cwd: str | Path,
) -> N8IPolicyRunBundle:
    del n8f1_root, n8f_root, dual_root, build_dir
    if not allow_run:
        raise RuntimeError("--allow-run is required for N8I policy replay")
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    clean_inputs = locate_clean_inputs(clean_root)
    if clean_inputs.get("clean_input_missing"):
        raise RuntimeError("clean input missing for N8I feedback policy run")

    n8g_reports = _load_named_reports(n8g_root, N8G_REPORT_NAMES)
    n8h_reports = _load_named_reports(n8h_root, N8H_REPORT_NAMES)
    residual_proxy = _residual_proxy_from_reports(n8g_reports, n8h_reports)
    specs = _runtime_specs()
    baseline = next(spec for spec in specs if not spec.run_feedback)
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

    policy_summaries = {baseline.policy_id: baseline_summary}
    evaluation_by_policy: dict[str, dict[str, Any]] = {}
    gate_reports: dict[str, dict[str, Any]] = {}
    covariance_reports: dict[str, dict[str, Any]] = {}
    window_reports: dict[str, dict[str, Any]] = {}
    observation_reports: dict[str, dict[str, Any]] = {}
    trace_rows: dict[str, list[dict[str, Any]]] = {
        baseline.policy_id: read_csv_rows(output_root / "variants" / baseline.policy_id / "run" / "FGO_FEEDBACK_UPDATE_TRACE.csv")
    }

    for policy in [spec for spec in specs if spec.run_feedback]:
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
        evaluation = evaluate_variant_against_baseline(
            baseline_eval,
            output_root / "variants" / policy.policy_id / "run" / "EVAL_NAV.csv",
            variant_id=policy.policy_id,
            manifest=manifest,
        )
        policy_summaries[policy.policy_id] = summary
        evaluation_by_policy[policy.policy_id] = evaluation
        gate_reports[policy.policy_id] = _policy_report(gate_report, policy)
        covariance_reports[policy.policy_id] = _policy_report(covariance_report, policy)
        window_reports[policy.policy_id] = _policy_report(window_report, policy)
        observation_reports[policy.policy_id] = _policy_report(observation_report, policy)
        trace_rows[policy.policy_id] = read_csv_rows(output_root / "variants" / policy.policy_id / "run" / "FGO_FEEDBACK_UPDATE_TRACE.csv")

    return N8IPolicyRunBundle(
        output_root=output_root,
        baseline_eval_nav=baseline_eval,
        policy_summaries=policy_summaries,
        evaluation_by_policy=evaluation_by_policy,
        gate_reports=gate_reports,
        covariance_reports=covariance_reports,
        window_reports=window_reports,
        observation_reports=observation_reports,
        trace_rows=trace_rows,
        n8g_reports=n8g_reports,
        n8h_reports=n8h_reports,
    )


def build_mode_ablation_reports(bundle: N8IPolicyRunBundle) -> tuple[dict[str, Any], dict[str, Any]]:
    mode_ids = [spec.policy_id for spec in build_mode_ablation_specs()]
    variants = [_variant_entry(bundle, policy_id) for policy_id in mode_ids if policy_id in bundle.policy_summaries]
    evaluation_report = build_evaluation_report(
        [bundle.evaluation_by_policy[policy_id] for policy_id in mode_ids if policy_id in bundle.evaluation_by_policy]
    )
    reject = next((item for item in variants if item["policy_id"] == "reject_all_sanity"), {})
    reject_passed = bool(
        reject
        and reject.get("feedback_accept_count") == 0
        and reject.get("baseline_delta", {}).get("horizontal_m", {}).get("max", 1.0) <= 1.0e-9
        and reject.get("baseline_delta", {}).get("yaw_deg", {}).get("max", 1.0) <= 1.0e-9
    )
    summaries = {
        "stage": "N8I",
        "variant_count": len(variants),
        "variants": variants,
        "baseline_variant": "baseline_no_feedback",
        "primary_feedback_variant": "primary_horizontal_velocity_attitude_default",
        "selected_diagnostic_variants": [
            "primary_hv_att_conservative_gate",
            "primary_hv_att_cov_x4",
            "diagnostic_PVA",
            "reject_all_sanity",
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
    comparison = {
        "stage": "N8I",
        "metric_namespace": "feedback_vs_baseline_delta",
        "variant_count": len(evaluation_report.get("variant_results", [])),
        "variant_results": evaluation_report.get("variant_results", []),
        "gross_degradation_status": evaluation_report.get("gross_degradation_status"),
        "reject_all_sanity_passed": reject_passed,
        "reference_evaluation_only": True,
        "no_output_substitution": True,
        "no_direct_nav_override": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    return summaries, comparison


def policy_trace_stats(bundle: N8IPolicyRunBundle, policy_id: str) -> dict[str, Any]:
    rows = bundle.trace_rows.get(policy_id, [])
    return {
        "row_count": len(rows),
        "accepted_count_from_trace": sum(1 for row in rows if safe_int(row.get("accepted")) == 1),
        "position_m": stats([safe_float(row.get("position_norm_m")) for row in rows]),
        "velocity_mps": stats([safe_float(row.get("velocity_norm_mps")) for row in rows]),
        "attitude_deg": stats([safe_float(row.get("attitude_norm_deg")) for row in rows]),
        "yaw_abs_deg": stats([abs(safe_float(row.get("yaw_residual_deg"))) for row in rows]),
        "attitude_spike_count_over_4deg": sum(1 for row in rows if safe_float(row.get("attitude_norm_deg")) > 4.0),
        "top_epochs": _top_trace_epochs(rows, limit=5),
    }


def _runtime_specs() -> list[FeedbackPolicySpec]:
    specs = build_mode_ablation_specs() + build_gate_sweep_specs() + build_covariance_sweep_specs() + build_window_policy_specs()
    unique: dict[str, FeedbackPolicySpec] = {}
    for spec in specs:
        unique.setdefault(spec.policy_id, spec)
    return list(unique.values())


def _run_policy(
    *,
    exe: str | Path,
    clean_inputs: dict[str, Any],
    output_root: Path,
    policy: FeedbackPolicySpec,
    observations_path: Path | None,
    allow_run: bool,
    cwd: Path,
) -> dict[str, Any]:
    variant_root = output_root / "variants" / policy.policy_id
    config_info = write_port_clean_config(clean_inputs, variant_root)
    config_path = Path(config_info["config_path"])
    if observations_path is not None:
        append_feedback_config(
            config_path,
            observation_path=observations_path,
            variant=policy.variant_spec(),
            thresholds=policy.thresholds(),
            covariance_scale=policy.covariance_scale,
        )
    run_dir = variant_root / "run"
    run_result = run_port_core(exe, config_path, run_dir, allow_run=allow_run, cwd=cwd)
    if run_result.get("returncode") not in (0, None):
        raise RuntimeError(f"N8I policy {policy.policy_id} failed: {run_result.get('stderr')}")
    summary = summarize_variant_manifest(policy.policy_id, run_dir)
    summary.update(
        {
            "policy_id": policy.policy_id,
            "mode_id": policy.mode_id,
            "feedback_mode": policy.feedback_mode,
            "position_enabled": policy.position_enabled,
            "velocity_enabled": policy.velocity_enabled,
            "attitude_enabled": policy.attitude_enabled,
            "reject_all": policy.reject_all,
            "diagnostic_only": policy.diagnostic_only,
            "covariance_policy": policy.covariance_policy,
            "gate_policy": policy.gate_policy,
            "window_duration_s": policy.window_duration_s,
            "feedback_stride_s": policy.feedback_stride_s,
            "config_path_role": "runtime_generated_config",
            "no_output_substitution": True,
            "no_direct_nav_override": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        }
    )
    return summary


def _apply_policy_covariance(
    observations: list[FeedbackObservation],
    policy: FeedbackPolicySpec,
    residual_proxy_p95: float,
) -> tuple[list[FeedbackObservation], dict[str, Any]]:
    base_inflation = 1.0 if policy.covariance_policy.startswith("block_") else policy.covariance_inflation
    adjusted, report = apply_conservative_covariance_policy(
        observations,
        residual_proxy_p95=residual_proxy_p95,
        inflation_factor=base_inflation,
    )
    block_scales = _block_scales(policy.covariance_policy)
    if block_scales != {"p": 1.0, "v": 1.0, "att": 1.0}:
        adjusted = [_scale_observation_std(obs, block_scales) for obs in adjusted]
        report["std_v_stats"] = stats([max(obs.std_vN, obs.std_vE, obs.std_vD) for obs in adjusted])
        report["std_att_stats"] = stats([max(obs.std_roll, obs.std_pitch, obs.std_yaw) for obs in adjusted])
    report.update(
        {
            "stage": "N8I",
            "policy_id": policy.policy_id,
            "covariance_policy": policy.covariance_policy,
            "base_inflation": base_inflation,
            "block_scales": block_scales,
            "no_R_shrink": True,
            "no_trace_tuning": True,
            "no_finalv23_tuning": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        }
    )
    return adjusted, report


def _block_scales(policy_id: str) -> dict[str, float]:
    if policy_id == "block_velocity_x2_attitude_x4":
        return {"p": 1.0, "v": 2.0, "att": 4.0}
    if policy_id == "block_attitude_x6_diagnostic":
        return {"p": 1.0, "v": 1.0, "att": 6.0}
    return {"p": 1.0, "v": 1.0, "att": 1.0}


def _scale_observation_std(obs: FeedbackObservation, scales: dict[str, float]) -> FeedbackObservation:
    return replace(
        obs,
        std_pN=obs.std_pN * scales["p"],
        std_pE=obs.std_pE * scales["p"],
        std_pD=obs.std_pD * scales["p"],
        std_vN=obs.std_vN * scales["v"],
        std_vE=obs.std_vE * scales["v"],
        std_vD=obs.std_vD * scales["v"],
        std_roll=obs.std_roll * scales["att"],
        std_pitch=obs.std_pitch * scales["att"],
        std_yaw=obs.std_yaw * scales["att"],
    )


def _policy_report(report: dict[str, Any], policy: FeedbackPolicySpec) -> dict[str, Any]:
    payload = dict(report)
    payload.update(policy.to_report_dict())
    payload["stage"] = "N8I"
    payload["no_output_substitution"] = True
    payload["no_direct_nav_override"] = True
    payload["trace_solver_input"] = False
    payload["final_v23_output_solver_input"] = False
    payload["paper_performance_claim"] = False
    return payload


def _variant_entry(bundle: N8IPolicyRunBundle, policy_id: str) -> dict[str, Any]:
    summary = bundle.policy_summaries.get(policy_id, {})
    evaluation = bundle.evaluation_by_policy.get(policy_id, {})
    trace_stats = policy_trace_stats(bundle, policy_id)
    gate = bundle.gate_reports.get(policy_id, {})
    return {
        "policy_id": policy_id,
        "feedback_mode": summary.get("feedback_mode", ""),
        "mode_id": summary.get("mode_id", ""),
        "state_blocks": {
            "position": bool(summary.get("position_enabled")),
            "velocity": bool(summary.get("velocity_enabled")),
            "attitude": bool(summary.get("attitude_enabled")),
        },
        "covariance_policy": summary.get("covariance_policy"),
        "gate_policy": summary.get("gate_policy"),
        "window_duration_s": summary.get("window_duration_s"),
        "feedback_stride_s": summary.get("feedback_stride_s"),
        "diagnostic_only": bool(summary.get("diagnostic_only")),
        "reject_all": bool(summary.get("reject_all")),
        "feedback_update_count": safe_int(summary.get("feedback_update_count")),
        "feedback_accept_count": safe_int(summary.get("feedback_accept_count")),
        "feedback_reject_count": safe_int(summary.get("feedback_reject_count")),
        "pre_runtime_gate_accept_count": safe_int(gate.get("accept_count")),
        "pre_runtime_gate_reject_count": safe_int(gate.get("reject_count")),
        "correction_norm_stats": {
            "position_m": trace_stats["position_m"],
            "velocity_mps": trace_stats["velocity_mps"],
            "attitude_deg": trace_stats["attitude_deg"],
            "yaw_abs_deg": trace_stats["yaw_abs_deg"],
        },
        "attitude_spike_count_over_4deg": trace_stats["attitude_spike_count_over_4deg"],
        "baseline_delta": evaluation.get(
            "feedback_vs_baseline_delta",
            {
                "horizontal_m": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                "yaw_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
                "roll_pitch_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
            },
        ),
        "gross_degradation": bool(evaluation.get("clean_gross_degradation", False)),
        "top_correction_epochs": trace_stats["top_epochs"],
        "no_output_substitution": summary.get("no_output_substitution") is True,
        "no_direct_nav_override": summary.get("no_direct_nav_override") is True,
    }


def _top_trace_epochs(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        score = max(
            safe_float(row.get("position_norm_m")),
            safe_float(row.get("velocity_norm_mps")) * 10.0,
            safe_float(row.get("attitude_norm_deg")),
        )
        scored.append(
            {
                "time": safe_float(row.get("update_time", row.get("observation_time"))),
                "position_norm_m": safe_float(row.get("position_norm_m")),
                "velocity_norm_mps": safe_float(row.get("velocity_norm_mps")),
                "attitude_norm_deg": safe_float(row.get("attitude_norm_deg")),
                "yaw_residual_deg": safe_float(row.get("yaw_residual_deg")),
                "accepted": safe_int(row.get("accepted")) == 1,
                "score": score,
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]


def _load_named_reports(root: str | Path, names: list[str]) -> dict[str, dict[str, Any]]:
    base = Path(root)
    return {name: read_json(base / name) for name in names}


def _residual_proxy_from_reports(n8g_reports: dict[str, dict[str, Any]], n8h_reports: dict[str, dict[str, Any]]) -> float:
    cov = n8g_reports.get("FGO_FEEDBACK_COVARIANCE_POLICY_REPORT.json", {})
    gate = n8g_reports.get("FGO_FEEDBACK_GATE_REPORT.json", {})
    n8h_correction = n8h_reports.get("FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json", {})
    candidates = [
        safe_float(cov.get("conservative_inflation_factor")),
        safe_float(gate.get("correction_norm_stats", {}).get("velocity_mps", {}).get("p95")),
        safe_float(n8h_correction.get("primary_correction_stats", {}).get("velocity_mps", {}).get("p95")),
    ]
    for value in candidates:
        if value > 0.0:
            return value
    return 1.0


def write_mode_ablation_reports(
    output_root: str | Path,
    summaries: dict[str, Any],
    comparison: dict[str, Any],
) -> None:
    root = Path(output_root)
    write_json(root / "N8I_FEEDBACK_MODE_ABLATION_SUMMARIES.json", summaries)
    write_json(root / "N8I_FEEDBACK_MODE_COMPARISON_REPORT.json", comparison)
