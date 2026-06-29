from legsa_gins.qm.qm_counter_schema import count_mapping_rows, split_manifest_counters


def test_legacy_bad_a1_consumed_is_not_claim_valid() -> None:
    rows = count_mapping_rows()
    legacy = next(row for row in rows if row["legacy_field"] == "bad_a1_consumed_count")

    assert legacy["new_field"] == "a1_yaw_rejected_count"
    assert legacy["claim_valid"] is False


def test_manifest_counter_split_separates_accepted_downweighted_rejected() -> None:
    split = split_manifest_counters(
        {
            "yaw_update_count": 10,
            "yaw_NORMAL": 6,
            "yaw_DOWNWEIGHT": 2,
            "yaw_REJECT": 2,
            "qm_downweight_count_by_source": {"dual_antenna_yaw": 1},
            "qm_reject_count_by_source": {"dual_antenna_yaw": 2},
        },
        qm_trace_required=True,
        qm_trace_file_exists=True,
    )

    assert split["a1_yaw_update_count"] == 10
    assert split["a1_yaw_accepted_count"] == 8
    assert split["a1_yaw_downweighted_count"] == 2
    assert split["a1_yaw_rejected_count"] == 2
    assert split["legacy_bad_a1_consumed_count_valid_for_claim"] is False
