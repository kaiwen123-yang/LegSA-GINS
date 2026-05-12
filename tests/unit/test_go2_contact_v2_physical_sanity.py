"""中文说明：N7B2A contact v2 sanity blocks all-contact walking patterns。"""

from legsa_gins.go2_prior.go2_contact_v2_physical_sanity import analyze_contact_v2_physical_sanity


def test_contact_v2_physical_sanity_flags_all_contact_permissive():
    rows = []
    for index in range(20):
        row = {"time": index * 0.1, "contact_label_v2": "walking_contact", "contact_count_v2": 4}
        for foot in range(4):
            row[f"foot_{foot}_contact_v2"] = 1
            row[f"foot_{foot}_speed_norm"] = 1.4
            row[f"foot_{foot}_force"] = 30.0
        rows.append(row)
    report = analyze_contact_v2_physical_sanity(
        rows,
        distribution_report={"field_quality_status": "usable"},
        velocity_segment_report={"readiness_status": "acceptable"},
    )
    assert report["all_contact_suspect"] is True
    assert report["contact_too_permissive"] is True
    assert report["alternating_contact_ratio"] == 0.0
    assert report["physical_plausibility_status"] == "review_or_not_ready"
    assert report["go2_velocity_prior_enabled"] is False
