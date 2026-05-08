"""中文说明：N4R2 yaw convention policy 单元测试只验证 evaluator 层。"""

from legsa_gins.evaluation.yaw_evaluator_convention_policy import (
    apply_yaw_profile,
    default_yaw_convention_profiles,
    evaluate_with_yaw_profile,
    get_profile,
)


def test_official_candidate_is_not_formal_by_default() -> None:
    candidate = get_profile("official_candidate_ref_heading_to_math")
    assert candidate["formal_allowed"] is False
    assert candidate["source"] == "N4R_single_antenna_official_candidate"
    assert "requires_dual_final_v23_verification" in candidate["notes"]


def test_apply_yaw_profile() -> None:
    direct = get_profile("direct_identity")
    candidate = get_profile("official_candidate_ref_heading_to_math")
    assert apply_yaw_profile(0.0, 90.0, direct) == -90.0
    assert apply_yaw_profile(0.0, 90.0, candidate) == 0.0


def test_evaluate_with_yaw_profile_writes_boundary_report(tmp_path) -> None:
    nav = [{"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 0.0}]
    ref = [{"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 90.0}]
    report = evaluate_with_yaw_profile(nav, ref, get_profile("official_candidate_ref_heading_to_math"), tmp_path)
    assert report["summary"]["yaw_rmse_deg"] == 0.0
    assert report["solver_output_changed"] is False
    assert report["evaluator_only"] is True
    assert report["trace_solver_input"] is False
    assert report["output_only_correction"] is False
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "error_series.csv").exists()


def test_default_profiles_nonempty() -> None:
    names = {profile["name"] for profile in default_yaw_convention_profiles()}
    assert {"direct_identity", "official_candidate_ref_heading_to_math", "diagnostic_ref_neg", "diagnostic_ref_plus90"} <= names
