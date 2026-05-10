"""N6A clean/stress source-aware ablation matrix.

中文说明：矩阵只定义 runtime-only 诊断组合；stress variants 不作 paper claim，
不调参，不删除 epoch，不把 N5D1 spike 时间写进 solver 策略。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_VARIANT_IDS = [
    "baseline_full_no_raw_no_sourceaware",
    "baseline_plus_raw_no_sourceaware",
    "baseline_plus_raw_lsim_only",
    "baseline_plus_raw_oim_only",
    "baseline_plus_raw_lsim_oim",
    "receiver_velocity_disabled_plus_raw_no_sourceaware",
    "receiver_velocity_disabled_plus_raw_lsim_oim",
    "receiver_velocity_std_scale_5_plus_raw_no_sourceaware",
    "receiver_velocity_std_scale_5_plus_raw_lsim_oim",
    "receiver_velocity_outage_30s_plus_raw_no_sourceaware",
    "receiver_velocity_outage_30s_plus_raw_lsim_oim",
    "receiver_velocity_noise_0p5_plus_raw_no_sourceaware",
    "receiver_velocity_noise_0p5_plus_raw_lsim_oim",
    "baseline_plus_raw_lsim_oim_spike_response_audit",
]


def _row(
    *,
    variant_id: str,
    output_root: Path,
    factor_csv: str | Path,
    enable_raw_doppler: bool,
    source_aware_mode: str,
    receiver_velocity_stress_mode: str = "none",
    receiver_velocity_std_scale: float = 1.0,
    receiver_velocity_outage_start_sec: float = 0.0,
    receiver_velocity_outage_duration_sec: float = 0.0,
    receiver_velocity_additive_noise_std_mps: float = 0.0,
    diagnostic_only: bool = False,
    diagnostic_stress_only: bool = False,
    evaluate_spike_response: bool = False,
) -> dict[str, Any]:
    sourceaware = source_aware_mode != "off"
    return {
        "variant_id": variant_id,
        "enable_receiver_velocity_update": True,
        "enable_raw_doppler": enable_raw_doppler,
        "enable_source_aware_weighting": sourceaware,
        "source_aware_mode": source_aware_mode,
        "source_aware_max_R_scale": 25.0,
        "source_aware_reject_extreme": False,
        "source_aware_no_R_shrink": True,
        "source_aware_trace_enabled": True,
        "receiver_velocity_stress_mode": receiver_velocity_stress_mode,
        "receiver_velocity_std_scale": receiver_velocity_std_scale,
        "receiver_velocity_outage_start_sec": receiver_velocity_outage_start_sec,
        "receiver_velocity_outage_duration_sec": receiver_velocity_outage_duration_sec,
        "receiver_velocity_additive_noise_std_mps": receiver_velocity_additive_noise_std_mps,
        "receiver_velocity_additive_noise_seed": 20260510,
        "raw_doppler_R_scale": 1.0,
        "raw_doppler_factor_path": str(factor_csv) if enable_raw_doppler else "",
        "diagnostic_only": diagnostic_only,
        "diagnostic_stress_only": diagnostic_stress_only,
        "evaluate_spike_response": evaluate_spike_response,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "go2_prior": False,
        "fgo": False,
        "config_path": str(output_root / "runtime_configs" / f"{variant_id}.yaml"),
        "output_dir": str(output_root / "variants" / variant_id),
    }


def build_n6a_source_aware_ablation_matrix(
    factor_csv: str | Path,
    output_dir: str | Path,
    *,
    outage_start_sec: float = 0.0,
) -> dict[str, Any]:
    out = Path(output_dir)
    matrix = [
        _row(
            variant_id="baseline_full_no_raw_no_sourceaware",
            output_root=out,
            factor_csv=factor_csv,
            enable_raw_doppler=False,
            source_aware_mode="off",
        ),
        _row(
            variant_id="baseline_plus_raw_no_sourceaware",
            output_root=out,
            factor_csv=factor_csv,
            enable_raw_doppler=True,
            source_aware_mode="off",
        ),
        _row(
            variant_id="baseline_plus_raw_lsim_only",
            output_root=out,
            factor_csv=factor_csv,
            enable_raw_doppler=True,
            source_aware_mode="lsim_only",
        ),
        _row(
            variant_id="baseline_plus_raw_oim_only",
            output_root=out,
            factor_csv=factor_csv,
            enable_raw_doppler=True,
            source_aware_mode="oim_only",
        ),
        _row(
            variant_id="baseline_plus_raw_lsim_oim",
            output_root=out,
            factor_csv=factor_csv,
            enable_raw_doppler=True,
            source_aware_mode="lsim_oim",
        ),
    ]
    stress_specs = [
        ("receiver_velocity_disabled", "disabled", 1.0, 0.0, 0.0, 0.0),
        ("receiver_velocity_std_scale_5", "std_scale", 5.0, 0.0, 0.0, 0.0),
        ("receiver_velocity_outage_30s", "outage", 1.0, outage_start_sec, 30.0, 0.0),
        ("receiver_velocity_noise_0p5", "additive_noise", 1.0, 0.0, 0.0, 0.5),
    ]
    for label, mode, std_scale, outage_start, outage_duration, noise in stress_specs:
        matrix.append(
            _row(
                variant_id=f"{label}_plus_raw_no_sourceaware",
                output_root=out,
                factor_csv=factor_csv,
                enable_raw_doppler=True,
                source_aware_mode="off",
                receiver_velocity_stress_mode=mode,
                receiver_velocity_std_scale=std_scale,
                receiver_velocity_outage_start_sec=outage_start,
                receiver_velocity_outage_duration_sec=outage_duration,
                receiver_velocity_additive_noise_std_mps=noise,
                diagnostic_only=True,
                diagnostic_stress_only=True,
            )
        )
        matrix.append(
            _row(
                variant_id=f"{label}_plus_raw_lsim_oim",
                output_root=out,
                factor_csv=factor_csv,
                enable_raw_doppler=True,
                source_aware_mode="lsim_oim",
                receiver_velocity_stress_mode=mode,
                receiver_velocity_std_scale=std_scale,
                receiver_velocity_outage_start_sec=outage_start,
                receiver_velocity_outage_duration_sec=outage_duration,
                receiver_velocity_additive_noise_std_mps=noise,
                diagnostic_only=True,
                diagnostic_stress_only=True,
            )
        )
    matrix.append(
        _row(
            variant_id="baseline_plus_raw_lsim_oim_spike_response_audit",
            output_root=out,
            factor_csv=factor_csv,
            enable_raw_doppler=True,
            source_aware_mode="lsim_oim",
            diagnostic_only=True,
            evaluate_spike_response=True,
        )
    )
    return {
        "stage": "N6A_source_aware_LSIM_OIM_weighting",
        "matrix": matrix,
        "required_variant_ids": REQUIRED_VARIANT_IDS,
        "required_variants_present": all(item in {row["variant_id"] for row in matrix} for item in REQUIRED_VARIANT_IDS),
        "main_diagnostic_variant": "baseline_plus_raw_lsim_oim",
        "spike_response_audit_variant": "baseline_plus_raw_lsim_oim_spike_response_audit",
        "no_R_shrink": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "go2_prior": False,
        "fgo": False,
    }


def write_matrix(matrix: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
