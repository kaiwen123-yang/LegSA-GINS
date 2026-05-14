"""中文说明：测试 N8B smoothness policy recommendation。"""

from legsa_gins.fgo.fgo_policy_ablation_runner import run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid
from legsa_gins.fgo.fgo_smoothness_policy_review import review_smoothness_policy


def test_smoothness_review_recommends_weak_policy_without_deletion() -> None:
    rows = [
        {"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0])
    ]
    ablations, _ = run_n8b_policy_ablations(ekf_rows=rows, policy_grid=build_n8b_policy_grid())
    report = review_smoothness_policy(ablations)
    assert report["recommended_policy"] in {"weak_yaw_smoothness_policy", "N8C_yaw_smoothing_redesign_not_final_deletion"}
    assert not report["smoothness_factor_deleted_for_metric"]
