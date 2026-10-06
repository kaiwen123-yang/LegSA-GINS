"""Shared synthetic source-backed-shaped fixtures (not formal evidence)."""

from pathlib import Path

import numpy as np

from legsa_gins.paper_rebuild.canonical541.provider_generator import ProviderBundle, ProviderTable


def make_bundle(tmp_path: Path, n: int = 1000) -> ProviderBundle:
    imu = tmp_path / "fresh.imu"; imu.write_text("66 0 0 0 0 0 0\n", encoding="utf-8")
    times = np.linspace(66.0, 340.0, n)
    position = [{"time": f"{t:.12f}", "lat_deg": "39.9848", "lon_deg": "116.3431", "height_m": "41.8", "std_n_m": ".014", "std_e_m": ".014", "std_d_m": ".02", "valid": "1", "status": "clean"} for t in times]
    velocity = [{"time": f"{t:.12f}", "vn": f"{.5 + .1*np.sin(t):.9f}", "ve": f"{.2*np.cos(t):.9f}", "vd": "0", "std_vn": ".05", "std_ve": ".05", "std_vd": ".05", "valid": "1", "status": "clean"} for t in times]
    yaw = [{"time": f"{t:.12f}", "yaw_deg": f"{10*np.sin(t/20):.9f}", "yaw_std_deg": "1.5", "valid": "1", "baseline_n_m": "0.0", "baseline_e_m": "-0.35", "baseline_d_m": "0", "baseline_length_m": ".35", "physical_in_band": "True", "source_status": "active", "gnss_order": "GNSS2-GNSS1", "lateral_to_body_offset_deg": "90", "wrap_safe_residual": "True", "trace_sign_or_offset_selection": "False"} for t in times]
    raw = [{"time": f"{t:.12f}", "source_time": f"{t:.12f}", "vn": ".1", "ve": ".2", "vd": "0", "std_vn": ".3", "std_ve": ".3", "std_vd": ".3", "sat_count": "10", "gdop_like": ".4", "provider_status": "available", "valid": "1", "quality": "5", "quality_flag": "5", "raw_doppler_backend_id": "rtklib", "covariance_policy": "frozen"} for t in times]
    rp = [{"time": f"{t:.12f}", "roll_rad": ".01", "pitch_rad": ".02", "std_roll_rad": ".03", "std_pitch_rad": ".03", "source_status": "active", "mode": "1", "gait_type": "1", "quality_flag": "fresh", "go2_roll_pitch_truth_claim": "False", "valid": "1"} for t in times]
    hv = [{"time": f"{t:.12f}", "vn": ".2", "ve": ".1", "vd": "0", "std_vn": "1.5", "std_ve": "1.5", "std_vd": "999", "update_flag": "True", "source_status": "active", "go2_velocity_truth_claim": "False"} for t in times]
    meta = [{"time": f"{t:.12f}", "position_valid": "1", "receiver_velocity_valid": "1", "dual_yaw_valid": "1", "source": "fresh", "trace_used": "False"} for t in times]
    tables = {"gnss_position": ProviderTable(tuple(position[0]), position), "receiver_velocity": ProviderTable(tuple(velocity[0]), velocity), "dual_yaw": ProviderTable(tuple(yaw[0]), yaw), "raw_doppler": ProviderTable(tuple(raw[0]), raw), "go2_rp": ProviderTable(tuple(rp[0]), rp), "go2_hv": ProviderTable(tuple(hv[0]), hv), "source_quality_metadata": ProviderTable(tuple(meta[0]), meta)}
    return ProviderBundle(imu, tables, {"raw": "a"*64}, {"imu": "b"*64}, [])


def case(type_id: str, seed: int = 0) -> dict:
    return {"case_id": f"{type_id}_seed_{seed:02d}", "degradation_type_id": type_id,
            "seed_index": f"seed_{seed:02d}", "seed_value": 260306001 + seed,
            "anchor_name": "test", "anchor_time_s": 206.2,
            "effect_validation_rule_id": f"RULE_{type_id}", "trace_eval_only": True,
            "final_v23_output_solver_input_allowed": False, "legsa_output_solver_input_allowed": False,
            "go2_truth_claim_allowed": False}
