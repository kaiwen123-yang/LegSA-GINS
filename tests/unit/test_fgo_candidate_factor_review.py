"""中文说明：测试 N8B candidate factor diagnostic boundary。"""

from legsa_gins.fgo.fgo_candidate_factor_review import review_candidate_factors
from legsa_gins.fgo.fgo_policy_ablation_runner import run_n8b_policy_ablations
from legsa_gins.fgo.fgo_policy_grid import build_n8b_policy_grid


def test_candidate_factor_review_keeps_candidates_diagnostic() -> None:
    rows = [
        {"index": index, "time": float(index), "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.0, "vd_mps": 0.0}
        for index, yaw in enumerate([359.0, 1.0, 2.0, 3.0, 4.0])
    ]
    ablations, _ = run_n8b_policy_ablations(ekf_rows=rows, policy_grid=build_n8b_policy_grid())
    report = review_candidate_factors(ablation_summary=ablations, n7c6_available=True, n7c5_available=True)
    assert report["candidate_factors_remain_diagnostic"]
    assert report["no_formal_activation"]
    assert all(row["diagnostic_only"] for row in report["candidate_factor_reviews"])
