"""Run N5D receiver velocity stress variants.

中文说明：本模块写 runtime-only config 并调用 C++ replay；stress variants 均为
diagnostic-only，不使用 trace 调参，不删 epoch，不做 output-only correction。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.raw_doppler_ablation_evaluator import evaluate_variant
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_stress_variant_config(base_config: str | Path, variant: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = Path(base_config).read_text(encoding="utf-8", errors="ignore")
    variant_id = str(variant["variant_id"])
    lines = [
        "",
        "# N5D runtime-only raw Doppler visual/stress config.",
        f"ablation_variant: {variant_id}",
        f"raw_doppler_diagnostic_variant_label: {variant_id}",
        f"enable_receiver_velocity_update: {str(bool(variant['enable_receiver_velocity_update'])).lower()}",
        f"receiver_velocity_stress_mode: {variant['receiver_velocity_stress_mode']}",
        f"receiver_velocity_std_scale: {float(variant['receiver_velocity_std_scale'])}",
        f"receiver_velocity_outage_start_sec: {float(variant['receiver_velocity_outage_start_sec'])}",
        f"receiver_velocity_outage_duration_sec: {float(variant['receiver_velocity_outage_duration_sec'])}",
        f"receiver_velocity_additive_noise_std_mps: {float(variant['receiver_velocity_additive_noise_std_mps'])}",
        f"receiver_velocity_additive_noise_seed: {int(variant['receiver_velocity_additive_noise_seed'])}",
        f"diagnostic_stress_only: {str(bool(variant['diagnostic_stress_only'])).lower()}",
        f"diagnostic_only: {str(bool(variant['diagnostic_only'])).lower()}",
        f"enable_raw_doppler: {str(bool(variant['enable_raw_doppler'])).lower()}",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
        "output_only_correction: false",
        "bad_epoch_deletion_for_metric: false",
    ]
    if variant["enable_raw_doppler"]:
        # 中文说明：raw Doppler 来自 RTKLIB Doppler provider，不是 UBX-NAV-PVT 或 .gnss 速度。
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


def run_stress_variant(config_path: str | Path, exe: str | Path, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    command = [
        str(exe),
        "--config",
        str(config_path),
        "--output-dir",
        str(out),
        "--debug-update-timeline",
        "--debug-output-dir",
        str(out),
    ]
    proc = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=360,
    )
    manifest_path = out / "RUN_MANIFEST.json"
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "manifest_path": str(manifest_path) if manifest_path.exists() else "",
        "manifest": _read_json(manifest_path),
    }


def evaluate_stress_variant(output_dir: str | Path, dual_reference: str | Path | None, variant: dict[str, Any]) -> dict[str, Any]:
    report = evaluate_variant(output_dir, dual_reference)
    manifest = _read_json(Path(output_dir) / "RUN_MANIFEST.json")
    report.update(
        {
            "variant_id": variant["variant_id"],
            "enable_raw_doppler": bool(variant["enable_raw_doppler"]),
            "enable_receiver_velocity_update": bool(variant["enable_receiver_velocity_update"]),
            "receiver_velocity_stress_mode": variant["receiver_velocity_stress_mode"],
            "receiver_velocity_std_scale": variant["receiver_velocity_std_scale"],
            "receiver_velocity_outage_start_sec": variant["receiver_velocity_outage_start_sec"],
            "receiver_velocity_outage_duration_sec": variant["receiver_velocity_outage_duration_sec"],
            "receiver_velocity_additive_noise_std_mps": variant["receiver_velocity_additive_noise_std_mps"],
            "receiver_velocity_additive_noise_seed": variant["receiver_velocity_additive_noise_seed"],
            "diagnostic_stress_only": bool(variant["diagnostic_stress_only"]),
            "diagnostic_only": bool(variant["diagnostic_only"]),
            "manifest": manifest,
            "raw_doppler_update_count": int(manifest.get("raw_doppler_update_count", report.get("raw_doppler_update_count", 0)) or 0),
            "raw_doppler_reject_count": int(manifest.get("raw_doppler_reject_count", report.get("raw_doppler_reject_count", 0)) or 0),
            "raw_doppler_residual_p95": manifest.get("raw_doppler_residual_p95", report.get("raw_doppler_residual_p95")),
            "parity_metrics": report.get("summary", {}),
            "absolute_metrics": {
                "metric_namespace": "port_vs_trace_absolute",
                "absolute_trace_evaluation_status": "evidence_missing_trace_reference_not_supplied_to_N5D_runner",
                "paper_performance_claim": False,
                "proposed_factor_claim": False,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "output_only_correction": False,
                "bad_epoch_deletion_for_metric": False,
            },
            "metric_namespaces": {
                "parity_metrics": "port_vs_final_v23_nav_parity",
                "absolute_metrics": "port_vs_trace_absolute_evidence_missing",
            },
            "paper_performance_claim": False,
            "proposed_factor_claim": False,
            "no_outperform_final_v23_claim": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
        }
    )
    return report


def run_n5d_stress_variants(
    matrix_report: dict[str, Any],
    *,
    clean_root: str | Path,
    exe: str | Path,
    build_dir: str | Path,
    output_dir: str | Path,
    dual_reference: str | Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del build_dir
    base_config = find_clean_config(clean_root)
    if base_config is None:
        raise FileNotFoundError("clean replay config missing")
    runs: list[dict[str, Any]] = []
    evals: list[dict[str, Any]] = []
    for variant in matrix_report["matrix"]:
        config_path = write_stress_variant_config(base_config, variant, variant["config_path"])
        run = run_stress_variant(config_path, exe, variant["output_dir"])
        run["variant_id"] = variant["variant_id"]
        runs.append(run)
        report = evaluate_stress_variant(variant["output_dir"], dual_reference, variant)
        report["returncode"] = run["returncode"]
        evals.append(report)
    _write_json(Path(output_dir) / "N5D_STRESS_VARIANT_RUNS.json", {"runs": runs, "paper_performance_claim": False})
    _write_json(
        Path(output_dir) / "N5D_STRESS_VARIANT_SUMMARIES.json",
        {
            "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
            "variants": evals,
            "metric_namespaces": {
                "parity_metrics": "port_vs_final_v23_nav_parity",
                "absolute_metrics": "port_vs_trace_absolute_or_evidence_missing",
            },
            "paper_performance_claim": False,
            "proposed_factor_claim": False,
            "no_outperform_final_v23_claim": True,
        },
    )
    return runs, evals


def load_existing_or_n5c_variant_summaries(n5c_root: str | Path) -> list[dict[str, Any]]:
    root = Path(n5c_root)
    data = _read_json(root / "N5C_ABLATION_VARIANT_EVALUATIONS.json")
    variants = data.get("variants")
    if isinstance(variants, list):
        return [row for row in variants if isinstance(row, dict)]
    return []
