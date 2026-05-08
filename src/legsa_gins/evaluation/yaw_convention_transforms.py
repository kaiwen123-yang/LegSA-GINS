"""Yaw convention transforms for N4R evaluator-parity diagnostics.

中文说明：这些变换只用于 evaluator parity，不能作为 solver 调参、天线安装角
formal selection，或 output-only correction。
"""

from __future__ import annotations


TRANSFORM_NAMES = [
    "identity",
    "neg",
    "plus90",
    "minus90",
    "plus180",
    "heading_to_math_yaw",
    "math_to_heading_yaw",
    "neg_plus90",
    "neg_minus90",
    "heading_reverse",
    "trace_yaw_as_math",
    "trace_yaw_neg",
    "trace_yaw_neg_plus90",
]


def wrap_deg180(angle: float) -> float:
    """Wrap an angle to [-180, 180)."""

    wrapped = (float(angle) + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def wrap_deg360(angle: float) -> float:
    """Wrap an angle to [0, 360)."""

    return float(angle) % 360.0


def transform_yaw(value_deg: float, transform_name: str) -> float:
    """Apply one diagnostic yaw convention transform."""

    value = float(value_deg)
    if transform_name == "identity":
        transformed = value
    elif transform_name == "neg":
        transformed = -value
    elif transform_name == "plus90":
        transformed = value + 90.0
    elif transform_name == "minus90":
        transformed = value - 90.0
    elif transform_name == "plus180":
        transformed = value + 180.0
    elif transform_name in {"heading_to_math_yaw", "math_to_heading_yaw", "trace_yaw_as_math"}:
        transformed = 90.0 - value
    elif transform_name == "neg_plus90":
        transformed = -value + 90.0
    elif transform_name == "neg_minus90":
        transformed = -value - 90.0
    elif transform_name == "heading_reverse":
        transformed = value + 180.0
    elif transform_name == "trace_yaw_neg":
        transformed = -value
    elif transform_name == "trace_yaw_neg_plus90":
        transformed = -value + 90.0
    else:
        raise ValueError(f"unknown yaw transform: {transform_name}")
    return wrap_deg360(transformed)


def compute_yaw_error(
    est_yaw_deg: float,
    ref_yaw_deg: float,
    *,
    est_transform: str,
    ref_transform: str,
) -> float:
    """Compute wrapped yaw error after applying independent est/ref transforms."""

    est = transform_yaw(est_yaw_deg, est_transform)
    ref = transform_yaw(ref_yaw_deg, ref_transform)
    return wrap_deg180(est - ref)


def generate_yaw_transform_grid() -> list[dict[str, str]]:
    """Return the N4R candidate grid for evaluator-parity search."""

    candidates: list[dict[str, str]] = []
    for est_transform in TRANSFORM_NAMES:
        for ref_transform in TRANSFORM_NAMES:
            candidates.append(
                {
                    "candidate_id": f"est={est_transform}|ref={ref_transform}",
                    "est_transform": est_transform,
                    "ref_transform": ref_transform,
                }
            )
    return candidates
