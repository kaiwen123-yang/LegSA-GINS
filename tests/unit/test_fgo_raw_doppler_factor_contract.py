"""Tests for N8C3 Raw Doppler factor contract.

中文说明：验证 Raw Doppler residual/Jacobian 只约束速度状态。
"""

from legsa_gins.fgo.fgo_raw_doppler_factor_contract import build_raw_doppler_factor_contract_report


def test_raw_doppler_contract_touches_velocity_only() -> None:
    report = build_raw_doppler_factor_contract_report()
    assert report["toy_passed"]
    assert report["state_blocks_touched"] == ["velocity_north", "velocity_east", "velocity_down"]
    assert not report["touches_yaw"]
    assert not report["trace_weight_tuning"]
