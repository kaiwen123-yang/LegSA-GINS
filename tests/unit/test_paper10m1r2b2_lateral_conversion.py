from legsa_gins.degradation.lateral_baseline_yaw_conversion import convert_gnss2_minus_gnss1_to_body_yaw


def test_gnss2_minus_gnss1_lateral_conversion_body_yaw() -> None:
    result = convert_gnss2_minus_gnss1_to_body_yaw(
        gnss1_rel_n_m=0.0,
        gnss1_rel_e_m=0.0,
        gnss1_rel_d_m=0.0,
        gnss2_rel_n_m=1.0,
        gnss2_rel_e_m=0.0,
        gnss2_rel_d_m=0.0,
    )
    assert result.gnss_order == "GNSS2-GNSS1"
    assert result.baseline_heading_deg == 0.0
    assert result.body_yaw_deg == 90.0
    assert result.trace_used_for_generation is False
    assert result.rmse_selected_sign is False

