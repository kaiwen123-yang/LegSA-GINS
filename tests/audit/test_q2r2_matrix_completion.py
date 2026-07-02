from legsa_gins.external_dual_methods.summary import final_decision


def test_q2r2_provider_blocker_prevents_pass_decision():
    assert final_decision(provider_closed=False, completed_rows=0, faithful_completed_methods=0) == "BLOCKED_PROVIDER_CONTRACT_FAILURE"


def test_q2r2_minimum_completion_rule():
    assert (
        final_decision(provider_closed=True, completed_rows=360, faithful_completed_methods=3)
        == "PASS_PAPER10Q2R2_MIN3_TRUE_DUAL_METHODS_COMPLETED_READY_FOR_PAPER_APPENDIX_OR_MAIN_CAVEATED"
    )
