"""Small frame-transform utilities for N2 infrastructure tests."""


def _triple(values: tuple[float, float, float]) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError("Expected a 3-vector.")
    return values


def flu_to_frd(v: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = _triple(v)
    return (x, -y, -z)


def frd_to_flu(v: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = _triple(v)
    return (x, -y, -z)


def enu_to_ned(v: tuple[float, float, float]) -> tuple[float, float, float]:
    e, n, u = _triple(v)
    return (n, e, -u)


def ned_to_enu(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n, e, d = _triple(v)
    return (e, n, -d)


def wrap_angle_deg(angle: float) -> float:
    return (float(angle) + 180.0) % 360.0 - 180.0


def wrap_heading_deg(angle: float) -> float:
    return float(angle) % 360.0
