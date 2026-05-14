"""Unit tests for N8F legged factor activation runner.

中文说明：检查候选因子打开后 residual dimension 真实变化。
"""

from legsa_gins.fgo.fgo_contact_aware_weighting_factor import ContactAwareWeightRow
from legsa_gins.fgo.fgo_foot_kinematic_velocity_factor import FootKinematicVelocityFactorRow
from legsa_gins.fgo.fgo_legged_factor_activation_runner import run_n8f_legged_variants
from legsa_gins.fgo.fgo_legged_factor_dataset_builder import LeggedFactorDataset
from legsa_gins.fgo.fgo_relative_odometry_between_factor import RelativeOdometryBetweenFactorRow
from legsa_gins.fgo.fgo_yawrate_between_factor import YawRateBetweenFactorRow


def _row(index: int) -> dict:
    return {
        "index": index,
        "time": index * 0.2,
        "lat_deg": 30.0 + index * 1e-6,
        "lon_deg": 120.0 + index * 1e-6,
        "height_m": 10.0,
        "roll_deg": 0.0,
        "pitch_deg": 0.0,
        "yaw_deg": float(index),
        "vn_mps": 1.0,
        "ve_mps": 0.1,
        "vd_mps": 0.0,
    }


def test_activation_runner_changes_candidate_residual_dimension() -> None:
    dataset = LeggedFactorDataset(
        ekf_rows=[_row(0), _row(1), _row(2)],
        raw_factors=[],
        contact_rows=[ContactAwareWeightRow(0.0, 1.0, 0.8, 0.2, 0.2)] * 3,
        foot_factor_rows=[FootKinematicVelocityFactorRow(0, 0.0, 0.8, 0.0, 1.0, 1.0, 0.2, 1.0)],
        yawrate_factor_rows=[YawRateBetweenFactorRow(0, 1, 0.0, 0.2, 5.0, 2.0)],
        relative_factor_rows=[RelativeOdometryBetweenFactorRow(0, 1, 0.0, 0.2, 0.8, 0.1, 1.0, 1.0, 1.0)],
        source_reports={},
        manifest={},
    )
    report, _, _ = run_n8f_legged_variants(dataset)
    stack = next(row for row in report["variants"] if row["variant"] == "all_legged_candidate_stack")
    baseline = next(row for row in report["variants"] if row["variant"] == "n8d_best_balance_baseline")
    assert report["variant_count"] == 12
    assert stack["candidate_solver_residual_dim"] > 0
    assert stack["solver_residual_dim"] > baseline["solver_residual_dim"]
