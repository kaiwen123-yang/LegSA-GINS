import math


def test_yaw_spikes_are_exact_signed_10deg_wrap_safe(apply_case):
    result = apply_case("C11")
    selected = [row for row in result.ledger_rows if row["selected"]]
    assert len(selected) == 2
    assert all(math.isclose(abs(float(row["yaw_delta_wrap_deg"])), 10.0, abs_tol=1e-9) for row in selected)
