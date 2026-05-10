"""N6A source-aware variant runner/evaluator.

中文说明：本模块写 runtime-only config，运行 port-core，并汇总 manifest/trace/metric；
不把 trace、final_v23 output 或评价结果用于调权。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import evaluate_port_clean_replay
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config
from legsa_gins.source_aware.source_weight_trace import read_source_weight_trace, summarize_source_weight_trace


METRIC_KEYS = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_source_aware_variant_config(base_config: str | Path, variant: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = Path(base_config).read_text(encoding="utf-8", errors="ignore")
    lines = [
        "",
        "# N6A runtime-only source-aware LSIM/OIM config.",
        "# 中文说明：N6A 只在 EKFUpdate 前放大 R，不读取 trace/final_v23 output 调权。",
        f"ablation_variant: {variant['variant_id']}",
        f"enable_receiver_velocity_update: {str(bool(variant['enable_receiver_velocity_update'])).lower()}",
        f"receiver_velocity_stress_mode: {variant['receiver_velocity_stress_mode']}",
        f"receiver_velocity_std_scale: {float(variant['receiver_velocity_std_scale'])}",
        f"receiver_velocity_outage_start_sec: {float(variant['receiver_velocity_outage_start_sec'])}",
        f"receiver_velocity_outage_duration_sec: {float(variant['receiver_velocity_outage_duration_sec'])}",
        f"receiver_velocity_additive_noise_std_mps: {float(variant['receiver_velocity_additive_noise_std_mps'])}",
        f"receiver_velocity_additive_noise_seed: {int(variant['receiver_velocity_additive_noise_seed'])}",
        f"enable_raw_doppler: {str(bool(variant['enable_raw_doppler'])).lower()}",
        f"enable_source_aware_weighting: {str(bool(variant['enable_source_aware_weighting'])).lower()}",
        f"source_aware_mode: {variant['source_aware_mode']}",
        f"source_aware_max_R_scale: {float(variant['source_aware_max_R_scale'])}",
        f"source_aware_reject_extreme: {str(bool(variant['source_aware_reject_extreme'])).lower()}",
        f"source_aware_no_R_shrink: {str(bool(variant['source_aware_no_R_shrink'])).lower()}",
        f"source_aware_trace_enabled: {str(bool(variant['source_aware_trace_enabled'])).lower()}",
        "source_aware_receiver_position_enabled: true",
        "source_aware_receiver_position_lsim_enabled: true",
        "source_aware_receiver_position_oim_enabled: true",
        "source_aware_receiver_velocity_enabled: true",
        "source_aware_receiver_velocity_lsim_enabled: true",
        "source_aware_receiver_velocity_oim_enabled: true",
        "source_aware_dual_antenna_yaw_enabled: true",
        "source_aware_dual_antenna_yaw_lsim_enabled: true",
        "source_aware_dual_antenna_yaw_oim_enabled: true",
        "source_aware_raw_doppler_velocity_enabled: true",
        "source_aware_raw_doppler_velocity_lsim_enabled: true",
        "source_aware_raw_doppler_velocity_oim_enabled: true",
        f"diagnostic_only: {str(bool(variant['diagnostic_only'])).lower()}",
        f"diagnostic_stress_only: {str(bool(variant['diagnostic_stress_only'])).lower()}",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
    ]
    if variant["enable_raw_doppler"]:
        lines.extend(
            [
                f'raw_doppler_factor_path: "{variant["raw_doppler_factor_path"]}"',
                "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER",
                "raw_doppler_time_tolerance_sec: 0.08",
                "raw_doppler_min_sat: 5",
                "raw_doppler_residual_gate_mps: 3.0",
                f"raw_doppler_R_scale: {float(variant['raw_doppler_R_scale'])}",
                "raw_doppler_mode: doppler_ls_velocity",
            ]
        )
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
        "trace_path": str(out / "SOURCE_AWARE_WEIGHT_TRACE.csv"),
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
        "raw_doppler_update_count": int(manifest.get("raw_doppler_update_count", 0) or 0),
        "source_aware_weighting_enabled": bool(manifest.get("source_aware_weighting_enabled", False)),
        "source_aware_mode": manifest.get("source_aware_mode", "off"),
        "diagnostic_only": bool(manifest.get("diagnostic_only", True)),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def run_source_aware_matrix(
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
        config_path = write_source_aware_variant_config(base_config, variant, variant["config_path"])
        run = run_variant(config_path, exe, variant["output_dir"])
        run["variant_id"] = variant["variant_id"]
        runs.append(run)
        summary = evaluate_variant(variant["output_dir"], dual_reference)
        summary["returncode"] = run["returncode"]
        summaries.append(summary)
    _write_json(Path(output_dir) / "N6A_SOURCE_AWARE_VARIANT_RUNS.json", {"runs": runs, "paper_performance_claim": False})
    _write_json(Path(output_dir) / "N6A_SOURCE_AWARE_VARIANT_SUMMARIES.json", {"variants": summaries, "paper_performance_claim": False})
    return runs, summaries


def _delta(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        av = (a or {}).get("summary", {}).get(key)
        bv = (b or {}).get("summary", {}).get(key)
        out[key] = float(av) - float(bv) if isinstance(av, (int, float)) and isinstance(bv, (int, float)) else None
    return out


def classify_delta(delta: dict[str, float | None]) -> str:
    numeric = [value for value in delta.values() if value is not None]
    if not numeric:
        return "evidence_missing"
    if any(value > limit for value, limit in zip(numeric[:3], [0.5, 0.5, 0.5])):
        return "diagnostic_degradation"
    if any(value < -limit for value, limit in zip(numeric[:3], [0.02, 0.02, 0.05])):
        return "diagnostic_improvement"
    return "diagnostic_neutral"


def compare_source_aware_variants(variant_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["variant_id"]: row for row in variant_summaries}
    comparisons: dict[str, Any] = {}
    baseline = by_id.get("baseline_plus_raw_no_sourceaware")
    for variant_id in ["baseline_plus_raw_lsim_only", "baseline_plus_raw_oim_only", "baseline_plus_raw_lsim_oim"]:
        delta = _delta(by_id.get(variant_id), baseline)
        comparisons[f"{variant_id}_minus_no_sourceaware"] = {
            "delta": delta,
            "diagnostic_label": classify_delta(delta),
        }
    for label in [
        "receiver_velocity_disabled",
        "receiver_velocity_std_scale_5",
        "receiver_velocity_outage_30s",
        "receiver_velocity_noise_0p5",
    ]:
        delta = _delta(by_id.get(f"{label}_plus_raw_lsim_oim"), by_id.get(f"{label}_plus_raw_no_sourceaware"))
        comparisons[f"{label}_sourceaware_minus_no_sourceaware"] = {
            "delta": delta,
            "diagnostic_label": classify_delta(delta),
        }
    return {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "comparisons": comparisons,
        "baseline_plus_raw_no_sourceaware": (baseline or {}).get("summary", {}),
        "baseline_plus_raw_lsim_oim": (by_id.get("baseline_plus_raw_lsim_oim") or {}).get("summary", {}),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def collect_weight_stats(variant_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant = {
        row["variant_id"]: row.get("source_aware_trace", {})
        for row in variant_summaries
        if row.get("source_aware_weighting_enabled")
    }
    return {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "weight_stats_by_variant": by_variant,
        "main_variant_stats": by_variant.get("baseline_plus_raw_lsim_oim", {}),
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_reports(output_dir: str | Path, variant_summaries: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    out = Path(output_dir)
    weight_stats = collect_weight_stats(variant_summaries)
    comparison = compare_source_aware_variants(variant_summaries)
    _write_json(out / "N6A_SOURCE_AWARE_WEIGHT_STATS.json", weight_stats)
    _write_json(out / "N6A_SOURCE_AWARE_COMPARISON_REPORT.json", comparison)
    return weight_stats, comparison
