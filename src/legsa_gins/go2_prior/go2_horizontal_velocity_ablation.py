"""N7C Go2 horizontal velocity ablation matrix.

中文说明：矩阵只定义受控激活和诊断变体；stress variant 只作工程诊断，
不用于 paper performance claim，也不声称优于 final_v23。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_N7C_VARIANT_IDS = [
    "baseline_no_go2_horizontal_velocity",
    "go2_horizontal_velocity_weak_prior_main",
    "go2_horizontal_velocity_probability_weighted",
    "go2_horizontal_velocity_contact_weighted",
    "go2_horizontal_velocity_high_confidence_only",
    "receiver_velocity_stress_no_go2",
    "receiver_velocity_stress_plus_go2_horizontal",
    "raw_doppler_stress_no_go2",
    "raw_doppler_stress_plus_go2_horizontal",
]


def _row(
    *,
    variant_id: str,
    output_root: Path,
    raw_doppler_factor_path: str | Path,
    go2_prior_path: str | Path | None,
    enable_go2: bool,
    enable_source_aware: bool = True,
    receiver_velocity_stress_mode: str = "none",
    receiver_velocity_std_scale: float = 1.0,
    raw_doppler_R_scale: float = 1.0,
    diagnostic_only: bool = False,
    diagnostic_stress_only: bool = False,
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "enable_receiver_velocity_update": True,
        "enable_raw_doppler": True,
        "raw_doppler_factor_path": str(raw_doppler_factor_path),
        "raw_doppler_R_scale": raw_doppler_R_scale,
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
        "source_aware_go2_horizontal_velocity_cap": 10.0,
        "source_aware_global_cap": 25.0,
        "source_aware_max_R_scale": 25.0,
        "source_aware_reject_extreme": False,
        "source_aware_no_R_shrink": True,
        "source_aware_trace_enabled": True,
        "source_aware_enable_rolling_innovation_baseline": True,
        "source_aware_rolling_window_size": 31,
        "source_aware_rolling_mad_floor": 0.5,
        "source_aware_go2_horizontal_velocity_enabled": True,
        "source_aware_go2_horizontal_velocity_lsim_enabled": True,
        "source_aware_go2_horizontal_velocity_oim_enabled": True,
        "enable_go2_horizontal_velocity_prior": enable_go2,
        "go2_horizontal_velocity_prior_path": str(go2_prior_path) if enable_go2 and go2_prior_path else "",
        "go2_horizontal_velocity_prior_std_scale": 1.0,
        "go2_horizontal_velocity_prior_vertical_disabled": True,
        "go2_horizontal_velocity_prior_source_aware_enabled": enable_source_aware,
        "go2_horizontal_velocity_prior_mode": "horizontal_2d",
        "enable_go2_velocity_prior_diagnostic": False,
        "go2_velocity_prior_diagnostic_path": "",
        "go2_position_prior_enabled": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "enable_go2_yaw_rate_prior_diagnostic": False,
        "go2_yaw_rate_prior_diagnostic_path": "",
        "receiver_velocity_stress_mode": receiver_velocity_stress_mode,
        "receiver_velocity_std_scale": receiver_velocity_std_scale,
        "receiver_velocity_outage_start_sec": 0.0,
        "receiver_velocity_outage_duration_sec": 0.0,
        "receiver_velocity_additive_noise_std_mps": 0.0,
        "receiver_velocity_additive_noise_seed": 20260510,
        "diagnostic_only": diagnostic_only,
        "diagnostic_stress_only": diagnostic_stress_only,
        "proposed_factor_claim": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
        "config_path": str(output_root / "runtime_configs" / f"{variant_id}.yaml"),
        "output_dir": str(output_root / "variants" / variant_id),
    }


def build_n7c_go2_horizontal_velocity_ablation_matrix(
    *,
    output_dir: str | Path,
    raw_doppler_factor_path: str | Path,
    prior_paths: dict[str, Path],
    run_stress: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir)
    matrix = [
        _row(
            variant_id="baseline_no_go2_horizontal_velocity",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=None,
            enable_go2=False,
        ),
        _row(
            variant_id="go2_horizontal_velocity_weak_prior_main",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["main"],
            enable_go2=True,
        ),
        _row(
            variant_id="go2_horizontal_velocity_probability_weighted",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["probability_weighted"],
            enable_go2=True,
            diagnostic_only=True,
        ),
        _row(
            variant_id="go2_horizontal_velocity_contact_weighted",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["contact_weighted"],
            enable_go2=True,
            diagnostic_only=True,
        ),
        _row(
            variant_id="go2_horizontal_velocity_high_confidence_only",
            output_root=out,
            raw_doppler_factor_path=raw_doppler_factor_path,
            go2_prior_path=prior_paths["high_confidence_only"],
            enable_go2=True,
            diagnostic_only=True,
        ),
    ]
    if run_stress:
        matrix.extend(
            [
                _row(
                    variant_id="receiver_velocity_stress_no_go2",
                    output_root=out,
                    raw_doppler_factor_path=raw_doppler_factor_path,
                    go2_prior_path=None,
                    enable_go2=False,
                    receiver_velocity_stress_mode="std_scale",
                    receiver_velocity_std_scale=5.0,
                    diagnostic_only=True,
                    diagnostic_stress_only=True,
                ),
                _row(
                    variant_id="receiver_velocity_stress_plus_go2_horizontal",
                    output_root=out,
                    raw_doppler_factor_path=raw_doppler_factor_path,
                    go2_prior_path=prior_paths["main"],
                    enable_go2=True,
                    receiver_velocity_stress_mode="std_scale",
                    receiver_velocity_std_scale=5.0,
                    diagnostic_only=True,
                    diagnostic_stress_only=True,
                ),
                _row(
                    variant_id="raw_doppler_stress_no_go2",
                    output_root=out,
                    raw_doppler_factor_path=raw_doppler_factor_path,
                    go2_prior_path=None,
                    enable_go2=False,
                    raw_doppler_R_scale=5.0,
                    diagnostic_only=True,
                    diagnostic_stress_only=True,
                ),
                _row(
                    variant_id="raw_doppler_stress_plus_go2_horizontal",
                    output_root=out,
                    raw_doppler_factor_path=raw_doppler_factor_path,
                    go2_prior_path=prior_paths["main"],
                    enable_go2=True,
                    raw_doppler_R_scale=5.0,
                    diagnostic_only=True,
                    diagnostic_stress_only=True,
                ),
            ]
        )
    found = {row["variant_id"] for row in matrix}
    return {
        "stage": "N7C_go2_horizontal_velocity_weak_prior",
        "matrix": matrix,
        "required_variant_ids": REQUIRED_N7C_VARIANT_IDS,
        "required_variants_present": all(item in found for item in REQUIRED_N7C_VARIANT_IDS if run_stress or "stress" not in item),
        "main_candidate_variant": "go2_horizontal_velocity_weak_prior_main",
        "stress_variants_diagnostic_only": True,
        "go2_velocity_truth_claim": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_n7c_ablation_matrix(matrix: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
