from legsa_gins.degradation.yaw_provider_lineage import validate_provider_lineage


def test_direct_baseline_heading_is_rejected() -> None:
    rows = [
        {
            "yaw_deg": "12.0",
            "yaw_std_deg": "1.5",
            "yaw_provider_lineage": "BY2_A1_dual_diff_status_interp_to_provider_axis",
            "yaw_frame": "solver_visible_body_heading_ned_deg",
            "gnss_order_used": "gnss2_minus_gnss1",
            "lateral_offset_sign": "baseline_heading_plus_90_equivalent",
            "legacy_m1r2b_baseline_yaw_deg": "12.0",
        }
    ]
    assert validate_provider_lineage(rows, "CLEAN")["yaw_lineage_validation_status"] == "FAIL"

