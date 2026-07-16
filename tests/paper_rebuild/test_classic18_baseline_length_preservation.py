import math


def test_selected_vector_perturbations_preserve_035m(apply_case):
    for code in ("C04", "C07", "C15"):
        result = apply_case(code)
        selected = [row for row in result.ledger_rows if row["selected"]]
        assert selected
        assert all(math.isclose(float(row["modified_length"]), 0.350, abs_tol=1e-12) for row in selected)
