import pytest

from legsa_gins.evaluation.basic_metrics import (
    mae,
    max_abs,
    metric_summary,
    p95_abs,
    rmse,
)


def test_basic_metrics_values():
    errors = [1.0, -2.0, 3.0, -4.0]

    assert rmse(errors) == pytest.approx((30.0 / 4.0) ** 0.5)
    assert mae(errors) == pytest.approx(2.5)
    assert p95_abs(errors) == 4.0
    assert max_abs(errors) == 4.0

    summary = metric_summary(errors)
    assert summary["count"] == 4
    assert summary["rmse"] == pytest.approx((30.0 / 4.0) ** 0.5)


def test_basic_metrics_reject_empty_inputs():
    with pytest.raises(ValueError, match="must not be empty"):
        rmse([])
