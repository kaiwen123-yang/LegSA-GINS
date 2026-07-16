import pytest

from legsa_gins.paper_rebuild.clean2_case_provider import (
    Clean2CaseProviderError,
    align_gnss_with_dual_provider,
)


def test_classic18_mapping_is_current_a1_and_not_legacy_backend(classic_catalog):
    payload = classic_catalog.payload
    assert payload["active_provider"]["layer"] == "A1_dual_diff_status_baseline_vector"
    assert payload["provenance"]["legacy_full_backend_provider_layer_promoted"] is False
    assert payload["provenance"]["legacy_provider_payload_used"] is False
    assert payload["gnss_schema"]["extended_column_count"] == 18


def _gnss_row(time_value: float) -> tuple[str, ...]:
    return tuple(
        [str(time_value), "39", "116", "42", "1", "1", "1", "0", "0", "0", "1", "1", "1", "10", "1.5", "1", "1", "1"]
    )


def test_missing_current_vector_fails_closed_only_outside_formal_window():
    provider = [{
        "time": 356.0,
        "baseline_e_m": 0.0,
        "baseline_n_m": 0.35,
        "baseline_d_m": 0.0,
        "body_yaw_ned_deg": 90.0,
        "yaw_std_deg": 1.5,
    }]
    outside = align_gnss_with_dual_provider([_gnss_row(357.2)], provider)
    assert outside[0].fields[17] == "0"
    assert outside[0].baseline_e_m is None
    with pytest.raises(Clean2CaseProviderError, match="formal-window"):
        align_gnss_with_dual_provider([_gnss_row(100.0)], provider)
