from scripts.paper10q2_horizontal_reconciliation import build_method_rows


def test_paper1f_secondary_aggregate_stays_diagnostic_only():
    rows = build_method_rows({"da_registry": [], "lc_registry": [], "lse_registry": [], "paper4g_ledger": [], "paper4a_da": [], "paper10c_go2_rows": []})
    paper1f = next(row for row in rows if row["method_id"] == "PAPER1F_DUAL_ANTENNA_ADAPTERS")
    assert paper1f["diagnostic_only"] == "true"
    assert paper1f["paper_location_recommendation"] == "diagnostic_only"
    assert paper1f["exact_reproduction"] == "false"
    assert "Do not call" in paper1f["notes"]
