from legsa_gins.degradation.yaw_provider_lineage import lineage_manifest, validate_provider_lineage


def _row(yaw: str = "90.0", legacy: str = "0.0") -> dict[str, str]:
    return {
        "yaw_deg": yaw,
        "yaw_std_deg": "1.5",
        "yaw_provider_lineage": "BY2_A1_dual_diff_status_interp_to_provider_axis",
        "yaw_frame": "solver_visible_body_heading_ned_deg",
        "gnss_order_used": "gnss2_minus_gnss1",
        "lateral_offset_sign": "baseline_heading_plus_90_equivalent",
        "legacy_m1r2b_baseline_yaw_deg": legacy,
    }


def test_lineage_manifest_forbids_trace_and_rmse_sign() -> None:
    manifest = lineage_manifest("toy", "D30")
    assert manifest["gnss_order"] == "GNSS2-GNSS1"
    assert manifest["trace_used_for_generation"] is False
    assert manifest["rmse_selected_sign"] is False


def test_provider_lineage_passes_fixed_fields() -> None:
    result = validate_provider_lineage([_row()], "D30")
    assert result["yaw_lineage_validation_status"] == "PASS"
    assert result["direct_baseline_heading_match_count"] == 0


def test_provider_lineage_rejects_direct_baseline_heading() -> None:
    result = validate_provider_lineage([_row(yaw="0.0", legacy="0.0")], "D30")
    assert result["yaw_lineage_validation_status"] == "FAIL"

