from legsa_gins.degradation.yaw_provider_lineage import FIXED_LINEAGE


def test_yaw_policy_lock_values() -> None:
    assert FIXED_LINEAGE["gnss_order"] == "GNSS2-GNSS1"
    assert "lateral" in FIXED_LINEAGE["lateral_conversion_formula"].lower()
    assert FIXED_LINEAGE["per_case_offset_used"] is False

