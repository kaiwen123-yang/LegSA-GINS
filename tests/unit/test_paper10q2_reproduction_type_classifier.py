from scripts.paper10q2_horizontal_claim_boundary import classify_reproduction_type, flag_row


def test_reproduction_type_priority_keeps_exact_explicit():
    assert classify_reproduction_type(exact=True, faithful_algorithm=True) == "EXACT_REPRODUCTION"


def test_policy_baseline_not_marked_faithful_algorithm():
    reproduction_type = classify_reproduction_type(paper_policy=True)
    flags = flag_row(reproduction_type)
    assert reproduction_type == "PAPER_DERIVED_POLICY_BASELINE"
    assert flags["exact_reproduction"] == "false"
    assert flags["faithful_algorithm"] == "false"
    assert flags["paper_derived_policy"] == "true"


def test_blocked_with_proof_classification():
    reproduction_type = classify_reproduction_type(blocked=True)
    flags = flag_row(reproduction_type)
    assert reproduction_type == "BLOCKED_WITH_PROOF"
    assert flags["blocked_with_proof"] == "true"
