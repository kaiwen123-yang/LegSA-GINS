from legsa_gins.qm.qm_counter_schema import count_mapping_rows


def test_legacy_bad_a1_counter_is_blocked_from_claim() -> None:
    legacy = next(row for row in count_mapping_rows() if row["legacy_field"] == "bad_a1_consumed_count")

    assert legacy["claim_valid"] is False
    assert "legacy name implied consumed bad A1" in legacy["reason"]
