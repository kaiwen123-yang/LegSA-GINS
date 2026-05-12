"""N7A Go2 weak-prior ablation runner and evaluator.

中文说明：本模块只生成 runtime-only config、运行诊断 replay，并汇总 R3C metric
namespace；评价结果不反向用于 Go2 prior 权重。
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


REQUIRED_N7A_VARIANT_IDS = [
    "baseline_plus_raw_sourceaware_n6b_no_go2",
    "baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior",
    "baseline_plus_raw_no_sourceaware_go2_attitude_weak_prior",
    "raw_doppler_stress_plus_sourceaware_no_go2",
    "raw_doppler_stress_plus_sourceaware_go2_attitude_weak_prior",
    "attitude_prior_std_3deg",
    "attitude_prior_std_5deg",
    "attitude_prior_std_10deg",
]


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def _row(
    *,
    variant_id: str,
    output_root: Path,
    raw_doppler_factor_path: str | Path,
    go2_prior_path: str | Path,
    enable_source_aware: bool,
    enable_go2: bool,
    std_deg: float = 5.0,
    stress: bool = False,
    diagnostic_only: bool = False,
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "enable_receiver_velocity_update": True,
        "enable_raw_doppler": True,
        "raw_doppler_factor_path": str(raw_doppler_factor_path),
        "enable_source_aware_weighting": enable_source_aware,
        "source_aware_policy_version": "n6b_conservative_innovation_covariance",
        "source_aware_mode": "lsim_oim" if enable_source_aware else "off",
        "source_aware_use_innovation_covariance": True,
        "source_aware_deadband_normalized": 1.5,
        "source_aware_moderate_normalized": 2.5,
        "source_aware_strong_normalized": 4.0,
        "source_aware_receiver_position_cap": 5.0,
        "source_aware_receiver_velocity_cap": 8.0,
        "source_aware_dual_yaw_cap": 10.0,
        "source_aware_raw_doppler_cap": 15.0,
        "source_aware_go2_attitude_cap": 10.0,
        "source_aware_global_cap": 25.0,
        "source_aware_max_R_scale": 25.0,
        "source_aware_reject_extreme": False,
        "source_aware_no_R_shrink": True,
        "source_aware_trace_enabled": True,
        "source_aware_enable_rolling_innovation_baseline": True,
        "source_aware_rolling_window_size": 31,
        "source_aware_rolling_mad_floor": 0.5,
        "enable_go2_attitude_weak_prior": enable_go2,
        "go2_attitude_prior_path": str(go2_prior_path) if enable_go2 else "",
        "go2_attitude_prior_time_tolerance_sec": 0.02,
        "go2_attitude_prior_std_roll_deg": std_deg,
        "go2_attitude_prior_std_pitch_deg": std_deg,
        "go2_attitude_prior_sourceaware": True,
        "go2_attitude_prior_diagnostic_only": True,
        "receiver_velocity_stress_mode": "additive_noise" if stress else "none",
        "receiver_velocity_additive_noise_std_mps": 0.5 if stress else 0.0,
        "receiver_velocity_additive_noise_seed": 20260510,
        "receiver_velocity_std_scale": 1.0,
        "receiver_velocity_outage_start_sec": 0.0,
        "receiver_velocity_outage_duration_sec": 0.0,
        "diagnostic_only": diagnostic_only or stress or std_deg != 5.0,
        "diagnostic_stress_only": stress,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_position_prior_enabled": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
        "config_path": str(output_root / "runtime_configs" / f"{variant_id}.yaml"),
        "output_dir": str(output_root / "variants" / variant_id),
    }


def build_n7a_go2_ablation_matrix(
    *,
    output_dir: str | Path,
    raw_doppler_factor_path: str | Path,
    go2_prior_path: str | Path,
) -> dict[str, Any]:
    out = Path(output_dir)
    matrix = [
        _row(
            variant_id="baseline_plus_raw_sourceaware_n6b_no_go2",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=True,
            enable_go2=False,
        ),
        _row(
            variant_id="baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=True,
            enable_go2=True,
        ),
        _row(
            variant_id="baseline_plus_raw_no_sourceaware_go2_attitude_weak_prior",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=False,
            enable_go2=True,
        ),
        _row(
            variant_id="raw_doppler_stress_plus_sourceaware_no_go2",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=True,
            enable_go2=False,
            stress=True,
        ),
        _row(
            variant_id="raw_doppler_stress_plus_sourceaware_go2_attitude_weak_prior",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=True,
            enable_go2=True,
            stress=True,
        ),
        _row(
            variant_id="attitude_prior_std_3deg",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=True,
            enable_go2=True,
            std_deg=3.0,
        ),
        _row(
            variant_id="attitude_prior_std_5deg",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=True,
            enable_go2=True,
            std_deg=5.0,
        ),
        _row(
            variant_id="attitude_prior_std_10deg",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=go2_prior_path,
            enable_source_aware=True,
            enable_go2=True,
            std_deg=10.0,
        ),
    ]
    found = {row["variant_id"] for row in matrix}
    return {
        "stage": "N7A_go2_body_state_weak_prior_foundation",
        "matrix": matrix,
        "required_variant_ids": REQUIRED_N7A_VARIANT_IDS,
        "required_variants_present": all(item in found for item in REQUIRED_N7A_VARIANT_IDS),
        "default_candidate": "baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior",
        "std_3deg_diagnostic_only": True,
        "std_5deg_default": True,
        "std_10deg_diagnostic_only": True,
        "go2_position_prior_enabled": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_n7a_variant_config(base_config: str | Path, variant: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = Path(base_config).read_text(encoding="utf-8", errors="ignore")
    lines = [
        "",
        "# N7A runtime-only Go2 weak attitude prior config.",
        "# 中文说明：Go2 rpy/quaternion 是机身内部状态，不是高精度 truth；N7A 只启用 roll/pitch 弱先验。",
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
        "raw_doppler_R_scale: 1.0",
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
        f"source_aware_global_cap: {float(variant['source_aware_global_cap'])}",
        f"source_aware_max_R_scale: {float(variant['source_aware_max_R_scale'])}",
        f"source_aware_reject_extreme: {str(bool(variant['source_aware_reject_extreme'])).lower()}",
        f"source_aware_no_R_shrink: {str(bool(variant['source_aware_no_R_shrink'])).lower()}",
        f"source_aware_trace_enabled: {str(bool(variant['source_aware_trace_enabled'])).lower()}",
        f"source_aware_enable_rolling_innovation_baseline: {str(bool(variant['source_aware_enable_rolling_innovation_baseline'])).lower()}",
        f"source_aware_rolling_window_size: {int(variant['source_aware_rolling_window_size'])}",
        f"source_aware_rolling_mad_floor: {float(variant['source_aware_rolling_mad_floor'])}",
        "source_aware_go2_attitude_roll_pitch_enabled: true",
        "source_aware_go2_attitude_roll_pitch_lsim_enabled: true",
        "source_aware_go2_attitude_roll_pitch_oim_enabled: true",
        f"enable_go2_attitude_weak_prior: {str(bool(variant['enable_go2_attitude_weak_prior'])).lower()}",
        f'go2_attitude_prior_path: "{variant["go2_attitude_prior_path"]}"',
        f"go2_attitude_prior_time_tolerance_sec: {float(variant['go2_attitude_prior_time_tolerance_sec'])}",
        f"go2_attitude_prior_std_roll_deg: {float(variant['go2_attitude_prior_std_roll_deg'])}",
        f"go2_attitude_prior_std_pitch_deg: {float(variant['go2_attitude_prior_std_pitch_deg'])}",
        f"go2_attitude_prior_sourceaware: {str(bool(variant['go2_attitude_prior_sourceaware'])).lower()}",
        f"go2_attitude_prior_diagnostic_only: {str(bool(variant['go2_attitude_prior_diagnostic_only'])).lower()}",
        "go2_position_prior_enabled: false",
        "go2_velocity_prior_enabled: false",
        "go2_yaw_prior_enabled: false",
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
    eval_nav = out / "EVAL_NAV.csv"
    if eval_nav.exists() and dual_reference and (Path(dual_reference) / "KF_GINS_Navresult.nav").exists():
        evaluation = evaluate_port_clean_replay(eval_nav, dual_reference)
        summary = evaluation["summary"]
    else:
        summary = {key: None for key in METRIC_KEYS}
        summary.update({"count": 0, "evidence_status": "reference_or_eval_nav_missing"})
        evaluation = {"summary": summary, "paper_performance_claim": False}
    return {
        "variant_id": manifest.get("ablation_variant", out.name),
        "summary": summary,
        "evaluation": evaluation,
        "manifest": manifest,
        "source_aware_trace": trace_summary,
        "go2_attitude_weak_prior_enabled": bool(manifest.get("go2_attitude_weak_prior_enabled", False)),
        "go2_attitude_weak_prior_update_count": int(manifest.get("go2_attitude_weak_prior_update_count", 0) or 0),
        "go2_attitude_weak_prior_reject_count": int(manifest.get("go2_attitude_weak_prior_reject_count", 0) or 0),
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def run_n7a_go2_matrix(
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
        config_path = write_n7a_variant_config(base_config, variant, variant["config_path"])
        run = run_variant(config_path, exe, variant["output_dir"])
        run["variant_id"] = variant["variant_id"]
        runs.append(run)
        summary = evaluate_variant(variant["output_dir"], dual_reference)
        summary["returncode"] = run["returncode"]
        summaries.append(summary)
    _write_json(Path(output_dir) / "N7A_GO2_WEAK_PRIOR_VARIANT_RUNS.json", {"runs": runs, "paper_performance_claim": False})
    _write_json(Path(output_dir) / "N7A_GO2_WEAK_PRIOR_VARIANT_SUMMARIES.json", {"variants": summaries, "paper_performance_claim": False})
    return runs, summaries


def compare_n7a_variants(variant_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["variant_id"]: row for row in variant_summaries}
    no_go2 = by_id.get("baseline_plus_raw_sourceaware_n6b_no_go2")
    go2 = by_id.get("baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior")
    stress_no_go2 = by_id.get("raw_doppler_stress_plus_sourceaware_no_go2")
    stress_go2 = by_id.get("raw_doppler_stress_plus_sourceaware_go2_attitude_weak_prior")
    std_screen = [
        {
            "variant_id": variant_id,
            "std_deg": by_id.get(variant_id, {}).get("manifest", {}).get("go2_attitude_prior_std_roll_deg"),
            "summary": by_id.get(variant_id, {}).get("summary", {}),
            "diagnostic_only": variant_id != "attitude_prior_std_5deg",
            "update_count": by_id.get(variant_id, {}).get("go2_attitude_weak_prior_update_count", 0),
        }
        for variant_id in ["attitude_prior_std_3deg", "attitude_prior_std_5deg", "attitude_prior_std_10deg"]
    ]
    return {
        "stage": "N7A_go2_body_state_weak_prior_foundation",
        "no_go2_summary": (no_go2 or {}).get("summary", {}),
        "go2_attitude_weak_prior_summary": (go2 or {}).get("summary", {}),
        "go2_attitude_weak_prior_minus_no_go2": {
            "delta": metric_delta(go2, no_go2),
            "paper_performance_claim": False,
        },
        "raw_doppler_stress_go2_minus_no_go2": {
            "delta": metric_delta(stress_go2, stress_no_go2),
            "paper_performance_claim": False,
        },
        "std_screen_summaries": std_screen,
        "go2_attitude_weak_prior_manifest": (go2 or {}).get("manifest", {}),
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def collect_go2_source_aware_stats(variant_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    main = next(
        (
            row
            for row in variant_summaries
            if row.get("variant_id") == "baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior"
        ),
        {},
    )
    trace = main.get("source_aware_trace", {})
    by_source = trace.get("stats_by_source", {}) if isinstance(trace, dict) else {}
    go2 = by_source.get("go2_attitude_roll_pitch", {})
    return {
        "stage": "N7A_go2_body_state_weak_prior_foundation",
        "go2_source_seen": bool(go2),
        "go2_source_stats": go2,
        "main_variant_source_aware_trace": trace,
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_n7a_reports(
    output_dir: str | Path,
    variant_summaries: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = Path(output_dir)
    comparison = compare_n7a_variants(variant_summaries)
    stats = collect_go2_source_aware_stats(variant_summaries)
    _write_json(out / "N7A_GO2_WEAK_PRIOR_COMPARISON_REPORT.json", comparison)
    _write_json(out / "N7A_GO2_SOURCE_AWARE_STATS.json", stats)
    return comparison, stats


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
