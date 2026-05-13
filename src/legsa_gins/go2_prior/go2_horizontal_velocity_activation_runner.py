"""N7C runtime activation runner for Go2 horizontal velocity weak prior.

中文说明：本模块只生成 runtime-only 配置、调用 C++ replay，并汇总受控
horizontal velocity weak prior 的工程诊断证据。
"""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import evaluate_port_clean_replay
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config
from legsa_gins.source_aware.source_aware_policy_diagnostics import METRIC_KEYS, metric_delta
from legsa_gins.source_aware.source_weight_trace import read_source_weight_trace, summarize_source_weight_trace


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_eval_nav(path: str | Path) -> list[dict[str, float]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: _float(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def write_n7c_variant_config(base_config: str | Path, variant: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = Path(base_config).read_text(encoding="utf-8", errors="ignore")
    lines = [
        "",
        "# N7C runtime-only Go2 horizontal velocity weak-prior activation config.",
        "# 中文说明：N7C 只启用 vn/ve weak prior；vd/yaw/position/FGO 均关闭，Go2 velocity 不是 truth。",
        f"ablation_variant: {variant['variant_id']}",
        f"enable_receiver_velocity_update: {str(bool(variant['enable_receiver_velocity_update'])).lower()}",
        f"receiver_velocity_stress_mode: {variant['receiver_velocity_stress_mode']}",
        f"receiver_velocity_std_scale: {float(variant['receiver_velocity_std_scale'])}",
        f"receiver_velocity_outage_start_sec: {float(variant['receiver_velocity_outage_start_sec'])}",
        f"receiver_velocity_outage_duration_sec: {float(variant['receiver_velocity_outage_duration_sec'])}",
        f"receiver_velocity_additive_noise_std_mps: {float(variant['receiver_velocity_additive_noise_std_mps'])}",
        f"receiver_velocity_additive_noise_seed: {int(variant['receiver_velocity_additive_noise_seed'])}",
        f"enable_raw_doppler: {str(bool(variant['enable_raw_doppler'])).lower()}",
        f'raw_doppler_factor_path: "{variant["raw_doppler_factor_path"]}"',
        "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER",
        "raw_doppler_time_tolerance_sec: 0.08",
        "raw_doppler_min_sat: 5",
        "raw_doppler_residual_gate_mps: 3.0",
        f"raw_doppler_R_scale: {float(variant['raw_doppler_R_scale'])}",
        "raw_doppler_mode: doppler_ls_velocity",
        f"enable_source_aware_weighting: {str(bool(variant['enable_source_aware_weighting'])).lower()}",
        f"source_aware_policy_version: {variant['source_aware_policy_version']}",
        f"source_aware_mode: {variant['source_aware_mode']}",
        f"source_aware_use_innovation_covariance: {str(bool(variant['source_aware_use_innovation_covariance'])).lower()}",
        f"source_aware_deadband_normalized: {float(variant['source_aware_deadband_normalized'])}",
        f"source_aware_moderate_normalized: {float(variant['source_aware_moderate_normalized'])}",
        f"source_aware_strong_normalized: {float(variant['source_aware_strong_normalized'])}",
        f"source_aware_receiver_position_cap: {float(variant['source_aware_receiver_position_cap'])}",
        f"source_aware_receiver_velocity_cap: {float(variant['source_aware_receiver_velocity_cap'])}",
        f"source_aware_dual_yaw_cap: {float(variant['source_aware_dual_yaw_cap'])}",
        f"source_aware_raw_doppler_cap: {float(variant['source_aware_raw_doppler_cap'])}",
        f"source_aware_go2_attitude_cap: {float(variant['source_aware_go2_attitude_cap'])}",
        f"source_aware_go2_horizontal_velocity_cap: {float(variant['source_aware_go2_horizontal_velocity_cap'])}",
        f"source_aware_global_cap: {float(variant['source_aware_global_cap'])}",
        f"source_aware_max_R_scale: {float(variant['source_aware_max_R_scale'])}",
        f"source_aware_reject_extreme: {str(bool(variant['source_aware_reject_extreme'])).lower()}",
        f"source_aware_no_R_shrink: {str(bool(variant['source_aware_no_R_shrink'])).lower()}",
        f"source_aware_trace_enabled: {str(bool(variant['source_aware_trace_enabled'])).lower()}",
        f"source_aware_enable_rolling_innovation_baseline: {str(bool(variant['source_aware_enable_rolling_innovation_baseline'])).lower()}",
        f"source_aware_rolling_window_size: {int(variant['source_aware_rolling_window_size'])}",
        f"source_aware_rolling_mad_floor: {float(variant['source_aware_rolling_mad_floor'])}",
        "source_aware_go2_horizontal_velocity_enabled: true",
        "source_aware_go2_horizontal_velocity_lsim_enabled: true",
        "source_aware_go2_horizontal_velocity_oim_enabled: true",
        f"enable_go2_horizontal_velocity_prior: {str(bool(variant['enable_go2_horizontal_velocity_prior'])).lower()}",
        f'go2_horizontal_velocity_prior_path: "{variant["go2_horizontal_velocity_prior_path"]}"',
        f"go2_horizontal_velocity_prior_std_scale: {float(variant['go2_horizontal_velocity_prior_std_scale'])}",
        f"go2_horizontal_velocity_prior_vertical_disabled: {str(bool(variant['go2_horizontal_velocity_prior_vertical_disabled'])).lower()}",
        f"go2_horizontal_velocity_prior_source_aware_enabled: {str(bool(variant['go2_horizontal_velocity_prior_source_aware_enabled'])).lower()}",
        f"go2_horizontal_velocity_prior_mode: {variant['go2_horizontal_velocity_prior_mode']}",
        f"go2_horizontal_velocity_adaptive_std_enabled: {str(bool(variant.get('go2_horizontal_velocity_adaptive_std_enabled', False))).lower()}",
        f"go2_horizontal_velocity_bounded_std_policy: {variant.get('go2_horizontal_velocity_bounded_std_policy', '')}",
        f"go2_horizontal_velocity_strength_policy: {variant.get('go2_horizontal_velocity_strength_policy', '')}",
        "enable_go2_velocity_prior_diagnostic: false",
        'go2_velocity_prior_diagnostic_path: ""',
        "go2_position_prior_enabled: false",
        "go2_velocity_prior_enabled: false",
        "go2_yaw_prior_enabled: false",
        "enable_go2_yaw_rate_prior_diagnostic: false",
        'go2_yaw_rate_prior_diagnostic_path: ""',
        f"diagnostic_only: {str(bool(variant['diagnostic_only'])).lower()}",
        f"diagnostic_stress_only: {str(bool(variant['diagnostic_stress_only'])).lower()}",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
        "trace_solver_input: false",
        "final_v23_output_solver_input: false",
        "output_only_correction: false",
        "bad_epoch_deletion_for_metric: false",
        "fgo: false",
    ]
    target.write_text(content + "\n".join(lines) + "\n", encoding="utf-8")
    return target


def run_variant(config_path: str | Path, exe: str | Path, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(exe), "--config", str(config_path), "--output-dir", str(out)],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )
    return {
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "manifest": _read_json(out / "RUN_MANIFEST.json"),
    }


def evaluate_variant(output_dir: str | Path, dual_reference: str | Path | None) -> dict[str, Any]:
    out = Path(output_dir)
    manifest = _read_json(out / "RUN_MANIFEST.json")
    trace_rows = read_source_weight_trace(out / "SOURCE_AWARE_WEIGHT_TRACE.csv")
    trace_summary = summarize_source_weight_trace(trace_rows)
    if (out / "EVAL_NAV.csv").exists() and dual_reference and (Path(dual_reference) / "KF_GINS_Navresult.nav").exists():
        evaluation = evaluate_port_clean_replay(out / "EVAL_NAV.csv", dual_reference)
        summary = evaluation["summary"]
    else:
        summary = {key: None for key in METRIC_KEYS}
        summary.update({"count": 0, "evidence_status": "reference_or_eval_nav_missing"})
        evaluation = {"summary": summary, "paper_performance_claim": False}
    by_source = trace_summary.get("stats_by_source", {}) if isinstance(trace_summary, dict) else {}
    return {
        "variant_id": manifest.get("ablation_variant", out.name),
        "summary": summary,
        "evaluation": evaluation,
        "manifest": manifest,
        "source_aware_trace": trace_summary,
        "go2_horizontal_velocity_source_aware_stats": by_source.get("go2_horizontal_velocity", {}),
        "go2_horizontal_velocity_prior_enabled": bool(manifest.get("go2_horizontal_velocity_prior_enabled", False)),
        "go2_horizontal_velocity_prior_update_count": int(manifest.get("go2_horizontal_velocity_prior_update_count", 0) or 0),
        "go2_horizontal_velocity_prior_reject_count": int(manifest.get("go2_velocity_prior_reject_count", 0) or 0),
        "go2_horizontal_velocity_prior_vertical_disabled": bool(manifest.get("go2_horizontal_velocity_prior_vertical_disabled", False)),
        "go2_velocity_truth_claim": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def run_n7c_horizontal_velocity_matrix(
    matrix: dict[str, Any],
    *,
    clean_root: str | Path,
    exe: str | Path,
    output_dir: str | Path,
    dual_reference: str | Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_config = find_clean_config(clean_root)
    if base_config is None:
        raise FileNotFoundError("clean replay config missing")
    runs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for variant in matrix["matrix"]:
        config_path = write_n7c_variant_config(base_config, variant, variant["config_path"])
        run = run_variant(config_path, exe, variant["output_dir"])
        run["variant_id"] = variant["variant_id"]
        runs.append(run)
        summary = evaluate_variant(variant["output_dir"], dual_reference)
        summary["returncode"] = run["returncode"]
        summaries.append(summary)
    out = Path(output_dir)
    _write_json(out / "N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_RUNS.json", {"runs": runs, "paper_performance_claim": False})
    _write_json(out / "N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_SUMMARIES.json", {"variants": summaries, "paper_performance_claim": False})
    return runs, summaries


def compare_n7c_variants(variant_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["variant_id"]: row for row in variant_summaries}
    baseline = by_id.get("baseline_no_go2_horizontal_velocity")
    main = by_id.get("go2_horizontal_velocity_weak_prior_main")
    receiver_no = by_id.get("receiver_velocity_stress_no_go2")
    receiver_go2 = by_id.get("receiver_velocity_stress_plus_go2_horizontal")
    raw_no = by_id.get("raw_doppler_stress_no_go2")
    raw_go2 = by_id.get("raw_doppler_stress_plus_go2_horizontal")
    comparisons = {
        "go2_horizontal_velocity_main_minus_baseline": {
            "delta": metric_delta(main, baseline),
            "paper_performance_claim": False,
        },
        "receiver_velocity_stress_plus_go2_minus_no_go2": {
            "delta": metric_delta(receiver_go2, receiver_no),
            "paper_performance_claim": False,
        },
        "raw_doppler_stress_plus_go2_minus_no_go2": {
            "delta": metric_delta(raw_go2, raw_no),
            "paper_performance_claim": False,
        },
    }
    for variant_id in [
        "go2_horizontal_velocity_probability_weighted",
        "go2_horizontal_velocity_contact_weighted",
        "go2_horizontal_velocity_high_confidence_only",
    ]:
        comparisons[f"{variant_id}_minus_main"] = {
            "delta": metric_delta(by_id.get(variant_id), main),
            "paper_performance_claim": False,
        }
    return {
        "stage": "N7C_go2_horizontal_velocity_weak_prior",
        "baseline": (baseline or {}).get("summary", {}),
        "main_horizontal_prior": (main or {}).get("summary", {}),
        "main_manifest": (main or {}).get("manifest", {}),
        "comparisons": comparisons,
        "metric_namespace": {
            "parity_to_final_v23": True,
            "absolute_to_trace": "evaluation_only_if_available",
            "variant_delta": True,
            "paper_performance_claim": False,
        },
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_n7c_reports(output_dir: str | Path, variant_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    comparison = compare_n7c_variants(variant_summaries)
    _write_json(Path(output_dir) / "N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json", comparison)
    return comparison
