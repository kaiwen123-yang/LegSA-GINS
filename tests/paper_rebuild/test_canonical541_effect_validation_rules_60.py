from legsa_gins.paper_rebuild.canonical541.effect_validation import expected_changed_tables


def test_effect_rule_closure():
    assert all(expected_changed_tables(f"D{i:02d}") for i in range(1,61))
    assert expected_changed_tables("D29") == {"source_quality_metadata"}
