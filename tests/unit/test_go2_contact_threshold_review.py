"""中文说明：N7B2 threshold candidates 来自 Go2 distribution。"""

from legsa_gins.go2_prior.go2_contact_threshold_review import review_contact_thresholds


def test_contact_threshold_review_uses_distribution_only():
    distribution = {
        "field_quality_status": "usable",
        "foot_force_stats_by_foot": {f"foot_{foot}": {"p25": 8.0, "p35": 10.0, "p50": 14.0} for foot in range(4)},
        "foot_speed_norm_stats_by_foot": {f"foot_{foot}": {"p35": 0.2, "p50": 0.4} for foot in range(4)},
    }
    report = review_contact_thresholds(distribution)
    assert report["recommended_candidate"] == "mode_gait_assisted_contact"
    assert report["threshold_source"] == "go2_field_distribution_only"
    assert report["thresholds_are_diagnostic"] is True
    assert report["navigation_metric_tuning"] is False
    assert report["candidate_thresholds"]["speed_assisted_contact"]["low_force_threshold_by_foot"]["foot_0"] == 4.8
