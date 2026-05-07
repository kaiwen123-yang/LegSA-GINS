"""Minimal quaternion helpers using (w, x, y, z) ordering.

中文说明：frame 模块固定 Go2 FLU、NED/ENU/ECEF/BLH、qbn/qeb 与 yaw 约定，防止 Go2 body/odom/map/navigation frame 混用和双重 FLU->FRD。
"""

import math


Quaternion = tuple[float, float, float, float]
Vector3 = tuple[float, float, float]


def quat_normalize(q: Quaternion) -> Quaternion:
    w, x, y, z = q
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm == 0.0:
        raise ValueError("Cannot normalize a zero quaternion.")
    return (w / norm, x / norm, y / norm, z / norm)


def quat_conjugate(q: Quaternion) -> Quaternion:
    w, x, y, z = q
    return (w, -x, -y, -z)


def quat_multiply(q1: Quaternion, q2: Quaternion) -> Quaternion:
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    )


def quat_inverse(q: Quaternion) -> Quaternion:
    w, x, y, z = q
    norm_sq = w * w + x * x + y * y + z * z
    if norm_sq == 0.0:
        raise ValueError("Cannot invert a zero quaternion.")
    cw, cx, cy, cz = quat_conjugate(q)
    return (cw / norm_sq, cx / norm_sq, cy / norm_sq, cz / norm_sq)


def quat_rotate_vector(q: Quaternion, v: Vector3) -> Vector3:
    qn = quat_normalize(q)
    rotated = quat_multiply(
        quat_multiply(qn, (0.0, v[0], v[1], v[2])),
        quat_inverse(qn),
    )
    return (rotated[1], rotated[2], rotated[3])
