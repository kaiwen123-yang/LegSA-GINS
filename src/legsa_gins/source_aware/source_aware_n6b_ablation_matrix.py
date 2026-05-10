"""N6B source-aware policy refinement ablation matrix.

中文说明：矩阵只定义 runtime-only 诊断组合，不产生 paper claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .source_aware_n6b_policy import POLICY_VERSION


REQUIRED_N6B_VARIANT_IDS = [
    "baseline_plus_raw_no_sourceaware",
    "n6a_lsim_oim_original_policy",
    "n6b_lsim_only",
    "n6b_oim_only",
    "n6b_lsim_oim",
    "receiver_velocity_disabled_plus_raw_no_sourceaware",
    "receiver_velocity_disabled_plus_raw_n6b_lsim_oim",
    "receiver_velocity_std_scale_5_plus_raw_no_sourceaware",
    "receiver_velocity_std_scale_5_plus_raw_n6b_lsim_oim",
    "receiver_velocity_outage_30s_plus_raw_no_sourceaware",
    "receiver_velocity_outage_30s_plus_raw_n6b_lsim_oim",
    "receiver_velocity_noise_0p5_plus_raw_no_sourceaware",
    "receiver_velocity_noise_0p5_plus_raw_n6b_lsim_oim",
    "n6b_lsim_oim_spike_response_audit",
]


def _row(
    *,
    variant_id: str,
    output_root: Path,
    factor_csv: str | Path,
    source_aware_mode: str,
    policy_version: str = POLICY_VERSION,
    enable_raw_doppler: bool = True,
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
    n6a_original = policy_version == "n6a_original_residual_ratio"
    return {
        "variant_id": variant_id,
        "enable_receiver_velocity_update": True,
        "enable_raw_doppler": enable_raw_doppler,
        "enable_source_aware_weighting": sourceaware,
        "source_aware_policy_version": policy_version,
        "source_aware_mode": source_aware_mode,
        "source_aware_use_innovation_covariance": not n6a_original,
        "source_aware_deadband_normalized": 1.5,
        "source_aware_moderate_normalized": 2.5,
        "source_aware_strong_normalized": 4.0,
        "source_aware_receiver_position_cap": 25.0 if n6a_original else 5.0,
        "source_aware_receiver_velocity_cap": 25.0 if n6a_original else 8.0,
        "source_aware_dual_yaw_cap": 25.0 if n6a_original else 10.0,
        "source_aware_raw_doppler_cap": 25.0 if n6a_original else 15.0,
        "source_aware_global_cap": 25.0,
        "source_aware_max_R_scale": 25.0,
        "source_aware_reject_extreme": False,
        "source_aware_no_R_shrink": True,
        "source_aware_trace_enabled": True,
        "source_aware_enable_rolling_innovation_baseline": not n6a_original,
        "source_aware_rolling_window_size": 31,
        "source_aware_rolling_mad_floor": 0.5,
        "receiver_velocity_stress_mode": receiver_velocity_stress_mode,
        "receiver_velocity_std_scale": receiver_velocity_std_scale,
        "receiver_velocity_outage_start_sec": receiver_velocity_outage_start_sec,
        "receiver_velocity_outage_duration_sec": receiver_velocity_outage_duration_sec,
        "receiver_velocity_additive_noise_std_mps": receiver_velocity_additive_noise_std_mps,
        "receiver_velocity_additive_noise_seed": 20260510,
        "raw_doppler_R_scale": 1.0,
        "raw_doppler_factor_path": str(factor_csv) if enable_raw_doppler else "",
        "diagnostic_only": diagnostic_only or n6a_original,
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


def build_n6b_source_aware_ablation_matrix(
    factor_csv: str | Path,
    output_dir: str | Path,
    *,
    outage_start_sec: float = 0.0,
    run_stress: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir)
    matrix = [
        _row(variant_id="baseline_plus_raw_no_sourceaware", output_root=out, factor_csv=factor_csv, source_aware_mode="off"),
        _row(
            variant_id="n6a_lsim_oim_original_policy",
            output_root=out,
            factor_csv=factor_csv,
            source_aware_mode="lsim_oim",
            policy_version="n6a_original_residual_ratio",
        ),
        _row(variant_id="n6b_lsim_only", output_root=out, factor_csv=factor_csv, source_aware_mode="lsim_only"),
        _row(variant_id="n6b_oim_only", output_root=out, factor_csv=factor_csv, source_aware_mode="oim_only"),
        _row(variant_id="n6b_lsim_oim", output_root=out, factor_csv=factor_csv, source_aware_mode="lsim_oim"),
    ]
    if run_stress:
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
                    variant_id=f"{label}_plus_raw_n6b_lsim_oim",
                    output_root=out,
                    factor_csv=factor_csv,
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
            variant_id="n6b_lsim_oim_spike_response_audit",
            output_root=out,
            factor_csv=factor_csv,
            source_aware_mode="lsim_oim",
            diagnostic_only=True,
            evaluate_spike_response=True,
        )
    )
    found = {row["variant_id"] for row in matrix}
    return {
        "stage": "N6B_source_aware_policy_refinement",
        "policy_version": POLICY_VERSION,
        "matrix": matrix,
        "required_variant_ids": REQUIRED_N6B_VARIANT_IDS,
        "required_variants_present": all(item in found for item in REQUIRED_N6B_VARIANT_IDS if run_stress or "receiver_velocity" not in item),
        "main_candidate_variant": "n6b_lsim_oim",
        "n6a_original_policy_variant": "n6a_lsim_oim_original_policy",
        "spike_response_audit_variant": "n6b_lsim_oim_spike_response_audit",
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
