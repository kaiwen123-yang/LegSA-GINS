from legsa_gins.evaluation.yaw_method_mode_semantics import (
    common_yaw_convention_pass,
    method_mode_yaw_semantic_row,
)


def test_method_mode_yaw_row_requires_body_yaw_provider() -> None:
    row = method_mode_yaw_semantic_row(
        "strong_dual_yaw_baseline",
        {"required_inputs": ["gnss_position", "dual_antenna_yaw"]},
        {"enable_source_aware": False, "enable_multi_state_qm": False},
        yaw_source_path="<PAPER10M1R2C2_RUNTIME_ROOT>/clean/dual_yaw_provider.csv",
        yaw_provider_fixed=True,
    )

    assert row["semantic_status"] == "PASS"
    assert row["body_heading_or_baseline_heading"] == "body_heading"
    assert row["trace_solver_input"] is False
    assert row["final_v23_output_solver_input"] is False


def test_common_yaw_convention_detects_mismatch() -> None:
    rows = [
        {
            "yaw_unit": "deg",
            "yaw_frame": "NED solver body heading",
            "body_heading_or_baseline_heading": "body_heading",
            "lateral_offset_sign": "baseline_heading_plus_90_equivalent",
            "gnss_order_used": "gnss2_minus_gnss1",
            "semantic_status": "PASS",
        },
        {
            "yaw_unit": "deg",
            "yaw_frame": "NED solver body heading",
            "body_heading_or_baseline_heading": "baseline_heading",
            "lateral_offset_sign": "none",
            "gnss_order_used": "gnss2_minus_gnss1",
            "semantic_status": "BLOCKED",
        },
    ]

    assert common_yaw_convention_pass(rows) is False
