"""Basic scalar error metrics for evaluation reports."""

import math


def rmse(errors: list[float]) -> float:
    values = _values(errors)
    return math.sqrt(sum(value * value for value in values) / len(values))


def mae(errors: list[float]) -> float:
    values = _values(errors)
    return sum(abs(value) for value in values) / len(values)


def p95_abs(errors: list[float]) -> float:
    values = sorted(abs(value) for value in _values(errors))
    index = math.ceil(0.95 * len(values)) - 1
    return values[index]


def max_abs(errors: list[float]) -> float:
    return max(abs(value) for value in _values(errors))


def metric_summary(errors: list[float]) -> dict:
    values = _values(errors)
    return {
        "rmse": rmse(values),
        "mae": mae(values),
        "p95_abs": p95_abs(values),
        "max_abs": max_abs(values),
        "count": len(values),
    }


def _values(errors: list[float]) -> list[float]:
    values = [float(value) for value in errors]
    if not values:
        raise ValueError("Metric input must not be empty.")
    return values
