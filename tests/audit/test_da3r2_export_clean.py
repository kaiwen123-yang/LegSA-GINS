from legsa_gins.da_repro.result_summary import final_decision


def test_da3r2_export_clean_decision_requires_export_pass():
    rows = [{"method_id": "M", "terminal_status": "COMPLETED_EVALUABLE_FULL_BACKEND"} for _ in range(54)]
    assert final_decision(rows, export_clean_pass=False) == "BLOCKED_DA3R2_MIN3_FULL_BACKEND_NOT_MET"
