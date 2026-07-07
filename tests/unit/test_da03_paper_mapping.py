from legsa_gins.da_repro.method_liu_cwls import METHOD_ID, PAPER_TO_CODE_MAPPING_ROWS, method_contract


def test_da03_paper_mapping_covers_core_cwls_items():
    items = {row["paper_item"] for row in PAPER_TO_CODE_MAPPING_ROWS}
    assert "DD carrier/code observation model" in items
    assert "wrapped residual" in items
    assert "C-WLS objective with code" in items
    assert "integer ambiguity treatment" in items
    contract = method_contract()
    assert contract["method_id"] == METHOD_ID
    assert contract["wrapped_residual"] is True
    assert contract["status_yaw_as_full_backend"] is False
    assert contract["trace_used_for_sign_or_offset"] is False
