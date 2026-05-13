"""N7C6 Go2 proprioceptive joint factor policy matrix.

中文说明：policy 只扫描 roll/pitch std 和 horizontal velocity std；Go2
position/yaw/vertical velocity 始终 disabled。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_N7C6_VARIANT_IDS = [
    "baseline_no_go2_proprioceptive",
    "horizontal_only_fixed_1p0",
    "rollpitch_only_5deg",
    "rollpitch_only_3deg",
    "rollpitch_only_1p6deg",
    "rollpitch_only_1deg",
    "joint_rp3deg_hv1p0",
    "joint_rp1p6deg_hv1p0",
    "joint_rp1deg_hv1p0",
    "joint_rp0p75_hv1p0_diagnostic",
    "joint_rp1p6deg_hv0p75_diagnostic",
    "joint_rp1p6deg_hv1p0_sourceaware_off",
    "receiver_velocity_stress_baseline",
    "receiver_velocity_stress_joint",
    "raw_doppler_stress_baseline",
    "raw_doppler_stress_joint",
]


def _row(
    *,
    variant_id: str,
    output_root: Path,
    raw_doppler_factor_path: str | Path,
    attitude_prior_path: str | Path | None,
    horizontal_prior_path: str | Path | None,
    joint_prior_path: str | Path | None,
    enable_attitude: bool,
    enable_horizontal: bool,
    enable_joint: bool,
    rp_std_deg: float,
    hv_std_mps: float = 1.0,
    receiver_velocity_stress_mode: str = "none",
    receiver_velocity_std_scale: float = 1.0,
    raw_doppler_R_scale: float = 1.0,
    source_aware: bool = True,
    diagnostic_only: bool = False,
    diagnostic_stress_only: bool = False,
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "enable_receiver_velocity_update": True,
        "enable_raw_doppler": True,
        "raw_doppler_factor_path": str(raw_doppler_factor_path),
        "raw_doppler_R_scale": raw_doppler_R_scale,
        "enable_source_aware_weighting": source_aware,
        "source_aware_policy_version": "n6b_conservative_innovation_covariance",
        "source_aware_mode": "lsim_oim" if source_aware else "off",
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
        "enable_go2_attitude_weak_prior": enable_attitude,
        "go2_attitude_prior_path": str(attitude_prior_path or ""),
        "go2_attitude_prior_time_tolerance_sec": 0.02,
        "go2_attitude_prior_std_roll_deg": rp_std_deg,
        "go2_attitude_prior_std_pitch_deg": rp_std_deg,
        "go2_attitude_prior_sourceaware": source_aware,
        "go2_attitude_prior_diagnostic_only": False,
        "enable_go2_horizontal_velocity_prior": enable_horizontal,
        "go2_horizontal_velocity_prior_path": str(horizontal_prior_path or ""),
        "go2_horizontal_velocity_prior_std_scale": 1.0,
        "go2_horizontal_velocity_prior_vertical_disabled": True,
        "go2_horizontal_velocity_prior_source_aware_enabled": source_aware,
        "go2_horizontal_velocity_prior_mode": "horizontal_2d",
        "go2_horizontal_velocity_strength_policy": f"n7c6_hv{hv_std_mps:g}",
        "enable_go2_proprioceptive_joint_factor": enable_joint,
        "go2_proprioceptive_joint_factor_path": str(joint_prior_path or ""),
        "go2_proprioceptive_joint_factor_mode": "sequential_equivalent",
        "go2_proprioceptive_joint_factor_policy": variant_id,
        "go2_proprioceptive_source_aware_enabled": source_aware,
        "enable_go2_velocity_prior_diagnostic": False,
        "go2_velocity_prior_diagnostic_path": "",
        "go2_position_prior_enabled": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
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


def build_n7c6_joint_factor_matrix(
    *,
    output_dir: str | Path,
    raw_doppler_factor_path: str | Path,
    prior_paths: dict[str, dict[str, Path]],
    run_stress: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir)
    p5 = prior_paths["joint_rp5deg_hv1p0"]
    p3 = prior_paths["joint_rp3deg_hv1p0"]
    p16 = prior_paths["joint_rp1p6deg_hv1p0"]
    p1 = prior_paths["joint_rp1deg_hv1p0"]
    p075 = prior_paths["joint_rp0p75_hv1p0_diagnostic"]
    p16_hv075 = prior_paths["joint_rp1p6deg_hv0p75_diagnostic"]
    matrix = [
        _row(variant_id="baseline_no_go2_proprioceptive", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=None, horizontal_prior_path=None, joint_prior_path=None, enable_attitude=False, enable_horizontal=False, enable_joint=False, rp_std_deg=5.0),
        _row(variant_id="horizontal_only_fixed_1p0", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=None, horizontal_prior_path=p16["horizontal"], joint_prior_path=None, enable_attitude=False, enable_horizontal=True, enable_joint=False, rp_std_deg=5.0),
        _row(variant_id="rollpitch_only_5deg", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p5["attitude"], horizontal_prior_path=None, joint_prior_path=None, enable_attitude=True, enable_horizontal=False, enable_joint=False, rp_std_deg=5.0),
        _row(variant_id="rollpitch_only_3deg", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p3["attitude"], horizontal_prior_path=None, joint_prior_path=None, enable_attitude=True, enable_horizontal=False, enable_joint=False, rp_std_deg=3.0),
        _row(variant_id="rollpitch_only_1p6deg", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p16["attitude"], horizontal_prior_path=None, joint_prior_path=None, enable_attitude=True, enable_horizontal=False, enable_joint=False, rp_std_deg=1.6),
        _row(variant_id="rollpitch_only_1deg", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p1["attitude"], horizontal_prior_path=None, joint_prior_path=None, enable_attitude=True, enable_horizontal=False, enable_joint=False, rp_std_deg=1.0),
        _row(variant_id="joint_rp3deg_hv1p0", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p3["attitude"], horizontal_prior_path=p3["horizontal"], joint_prior_path=p3["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=3.0),
        _row(variant_id="joint_rp1p6deg_hv1p0", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p16["attitude"], horizontal_prior_path=p16["horizontal"], joint_prior_path=p16["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=1.6),
        _row(variant_id="joint_rp1deg_hv1p0", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p1["attitude"], horizontal_prior_path=p1["horizontal"], joint_prior_path=p1["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=1.0),
        _row(variant_id="joint_rp0p75_hv1p0_diagnostic", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p075["attitude"], horizontal_prior_path=p075["horizontal"], joint_prior_path=p075["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=0.75, diagnostic_only=True),
        _row(variant_id="joint_rp1p6deg_hv0p75_diagnostic", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p16_hv075["attitude"], horizontal_prior_path=p16_hv075["horizontal"], joint_prior_path=p16_hv075["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=1.6, hv_std_mps=0.75, diagnostic_only=True),
        _row(variant_id="joint_rp1p6deg_hv1p0_sourceaware_off", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p16["attitude"], horizontal_prior_path=p16["horizontal"], joint_prior_path=p16["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=1.6, source_aware=False, diagnostic_only=True),
    ]
    if run_stress:
        matrix.extend(
            [
                _row(variant_id="receiver_velocity_stress_baseline", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=None, horizontal_prior_path=None, joint_prior_path=None, enable_attitude=False, enable_horizontal=False, enable_joint=False, rp_std_deg=5.0, receiver_velocity_stress_mode="std_scale", receiver_velocity_std_scale=5.0, diagnostic_only=True, diagnostic_stress_only=True),
                _row(variant_id="receiver_velocity_stress_joint", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p16["attitude"], horizontal_prior_path=p16["horizontal"], joint_prior_path=p16["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=1.6, receiver_velocity_stress_mode="std_scale", receiver_velocity_std_scale=5.0, diagnostic_only=True, diagnostic_stress_only=True),
                _row(variant_id="raw_doppler_stress_baseline", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=None, horizontal_prior_path=None, joint_prior_path=None, enable_attitude=False, enable_horizontal=False, enable_joint=False, rp_std_deg=5.0, raw_doppler_R_scale=5.0, diagnostic_only=True, diagnostic_stress_only=True),
                _row(variant_id="raw_doppler_stress_joint", output_root=out, raw_doppler_factor_path=raw_doppler_factor_path, attitude_prior_path=p16["attitude"], horizontal_prior_path=p16["horizontal"], joint_prior_path=p16["joint"], enable_attitude=True, enable_horizontal=True, enable_joint=True, rp_std_deg=1.6, raw_doppler_R_scale=5.0, diagnostic_only=True, diagnostic_stress_only=True),
            ]
        )
    found = {row["variant_id"] for row in matrix}
    return {
        "stage": "N7C6_go2_proprioceptive_joint_factor",
        "matrix": matrix,
        "required_variant_ids": REQUIRED_N7C6_VARIANT_IDS,
        "required_variants_present": all(item in found for item in REQUIRED_N7C6_VARIANT_IDS if run_stress or "stress" not in item),
        "main_joint_candidate": "joint_rp1p6deg_hv1p0",
        "sequential_equivalent": True,
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
