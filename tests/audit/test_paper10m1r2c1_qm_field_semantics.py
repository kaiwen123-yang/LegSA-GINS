from legsa_gins.evaluation.qm_trace_semantic_audit import semantic_notes


def test_qm_semantic_notes_block_baseline_claim_use():
    notes = semantic_notes(
        qm_required=False,
        qm_file_exists=False,
        bad_a1_maps_to_yaw_reject=True,
        method="strong_dual_yaw_baseline",
    )
    assert "bad_a1_consumed_count_is_yaw_reject_count_not_consumed_count" in notes
    assert "baseline_or_no_qm_method_must_not_use_qm_counters_for_claim" in notes
