import math

from legsa_gins.evaluation.yaw_provider_lineage import (
    by2_a1_dual_diff_yaw_from_status_relpos,
    interpolate_angle_deg,
    m1r2b_legacy_provider_yaw_from_status_relpos,
    repair_provider_rows_from_source_yaw,
)


def test_by2_a1_dual_diff_applies_lateral_body_heading_conversion() -> None:
    lineage = by2_a1_dual_diff_yaw_from_status_relpos(
        gnss1_rel_n_m=3020.26123046875,
        gnss1_rel_e_m=650.0797729492188,
        gnss1_rel_d_m=14.969499588012695,
        gnss2_rel_n_m=3020.2705078125,
        gnss2_rel_e_m=649.727783203125,
        gnss2_rel_d_m=14.973999977111816,
    )
    legacy = m1r2b_legacy_provider_yaw_from_status_relpos(
        gnss1_rel_n_m=3020.26123046875,
        gnss1_rel_e_m=650.0797729492188,
        gnss2_rel_n_m=3020.2705078125,
        gnss2_rel_e_m=649.727783203125,
    )

    assert math.isclose(legacy, 91.50978718019846)
    assert math.isclose(lineage.yaw_ned_deg, 1.5097871801984581)
    assert lineage.trace_tuned is False
    assert lineage.gnss_order_used == "gnss2_minus_gnss1"


def test_provider_repair_interpolates_source_yaw_to_provider_axis() -> None:
    source = [{"time": 10.0, "yaw_deg": 350.0}, {"time": 11.0, "yaw_deg": 10.0}]
    assert math.isclose(interpolate_angle_deg(source, 10.5), 0.0)
    repaired, summary = repair_provider_rows_from_source_yaw(
        [{"time": "0.500", "yaw_deg": "90.0"}],
        source,
        provider_to_source_time_offset_sec=10.0,
    )

    assert repaired[0]["yaw_deg"] == "0.000000"
    assert repaired[0]["trace_tuned_yaw_fix"] == "false"
    assert summary["updated_yaw_row_count"] == 1
    assert summary["output_only_metric_correction"] is False
