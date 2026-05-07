"""Small frame-transform utilities for N2 infrastructure tests.

中文说明：frame 模块固定 Go2 FLU、NED/ENU/ECEF/BLH、qbn/qeb 与 yaw 约定，防止 Go2 body/odom/map/navigation frame 混用和双重 FLU->FRD。
"""


def _triple(values: tuple[float, float, float]) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError("Expected a 3-vector.")
    return values


def flu_to_frd(v: tuple[float, float, float]) -> tuple[float, float, float]:
    # 中文说明：只做一次 FLU->FRD 轴向转换，调用方不得重复转换。
    # Apply FLU->FRD exactly once.
    x, y, z = _triple(v)
    return (x, -y, -z)


def frd_to_flu(v: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = _triple(v)
    return (x, -y, -z)


def enu_to_ned(v: tuple[float, float, float]) -> tuple[float, float, float]:
    # 中文说明：ENU/NED 只转换坐标表达，不改变数据来源角色。
    # ENU/NED conversion changes frame expression only.
    e, n, u = _triple(v)
    return (n, e, -u)


def ned_to_enu(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n, e, d = _triple(v)
    return (e, n, -d)


def wrap_angle_deg(angle: float) -> float:
    return (float(angle) + 180.0) % 360.0 - 180.0


def wrap_heading_deg(angle: float) -> float:
    return float(angle) % 360.0
