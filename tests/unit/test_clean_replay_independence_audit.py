"""中文说明：N4H2G2 clean replay independence 合同测试。"""

from legsa_gins.evaluation.clean_replay_independence_audit import _manifest_valid
from legsa_gins.evaluation.clean_status_yaw_replay import DEFAULT_CLEAN_POLICY


def test_clean_manifest_policy_validates_no_noise_no_outage() -> None:
    manifest = {
        "clean_input_policy": DEFAULT_CLEAN_POLICY,
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 0.0,
        "outlier_mode": "none",
        "outlier_ratio": 0.0,
        "enable_outage": False,
        "trace_solver_input": False,
    }
    assert _manifest_valid(manifest, DEFAULT_CLEAN_POLICY) is True


def test_clean_manifest_rejects_yaw_noise() -> None:
    manifest = dict(DEFAULT_CLEAN_POLICY)
    manifest["yaw_noise_std_deg"] = 1.5
    assert _manifest_valid(manifest, DEFAULT_CLEAN_POLICY) is False
