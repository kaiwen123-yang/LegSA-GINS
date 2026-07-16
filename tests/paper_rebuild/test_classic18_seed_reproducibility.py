def test_classic18_seed_reproducibility(apply_case):
    first = apply_case("C07")
    second = apply_case("C07")
    assert first.output_fields == second.output_fields
    assert first.ledger_rows == second.ledger_rows
