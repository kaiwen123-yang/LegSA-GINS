"""Provider-backed raw Doppler velocity least-squares.

中文说明：Mode A 需要 satellite position/velocity provider；provider 缺失时进入
Mode B，不生成假速度，也不允许 solver factor activation。
"""

from __future__ import annotations

import math
from typing import Protocol

from .raw_doppler_types import (
    DopplerVelocitySolution,
    RawDopplerMeasurement,
    ReceiverApproxState,
    SatelliteState,
)


class SatelliteStateProvider(Protocol):
    def state_for(self, measurement: RawDopplerMeasurement) -> SatelliteState | None:
        ...


def _mat_transpose(a: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*a)]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(x * y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


def _matvec(a: list[list[float]], x: list[float]) -> list[float]:
    return [sum(v * xi for v, xi in zip(row, x)) for row in a]


def _inverse(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1.0e-12:
            raise ValueError("singular Doppler LS normal matrix")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [v - factor * p for v, p in zip(aug[row], aug[col])]
    return [row[n:] for row in aug]


def _ecef_to_ned_matrix(lat: float, lon: float) -> list[list[float]]:
    s_lat, c_lat = math.sin(lat), math.cos(lat)
    s_lon, c_lon = math.sin(lon), math.cos(lon)
    return [
        [-s_lat * c_lon, -s_lat * s_lon, c_lat],
        [-s_lon, c_lon, 0.0],
        [-c_lat * c_lon, -c_lat * s_lon, -s_lat],
    ]


def _unit_los(receiver: tuple[float, float, float], sat: tuple[float, float, float]) -> tuple[float, float, float]:
    dx = sat[0] - receiver[0]
    dy = sat[1] - receiver[1]
    dz = sat[2] - receiver[2]
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if norm <= 0.0:
        raise ValueError("zero LOS")
    return dx / norm, dy / norm, dz / norm


def solve_raw_doppler_velocity(
    measurements: list[RawDopplerMeasurement],
    provider: SatelliteStateProvider | None,
    receiver: ReceiverApproxState,
    *,
    min_sat: int = 5,
    min_cno: float = 20.0,
) -> DopplerVelocitySolution | None:
    if provider is None:
        return None
    rows: list[list[float]] = []
    obs: list[float] = []
    weights: list[float] = []
    used: list[RawDopplerMeasurement] = []
    for measurement in measurements:
        rr = measurement.observed_range_rate_mps
        if rr is None or not math.isfinite(rr) or abs(measurement.do_mes_hz) <= 0.0 or measurement.cno < min_cno:
            continue
        sat = provider.state_for(measurement)
        if sat is None:
            continue
        los = _unit_los(receiver.pos_ecef_m, sat.pos_ecef_m)
        # observed_range_rate = los dot (receiver_velocity - satellite_velocity) + clock_drift
        sat_projection = los[0] * sat.vel_ecef_mps[0] + los[1] * sat.vel_ecef_mps[1] + los[2] * sat.vel_ecef_mps[2]
        rows.append([los[0], los[1], los[2], 1.0])
        obs.append(rr + sat_projection - sat.clock_drift_mps)
        weights.append(max(1.0, measurement.cno / 30.0))
        used.append(measurement)
    if len(rows) < min_sat:
        return None
    aw = [[value * math.sqrt(w) for value in row] for row, w in zip(rows, weights)]
    bw = [value * math.sqrt(w) for value, w in zip(obs, weights)]
    at = _mat_transpose(aw)
    normal = _matmul(at, aw)
    inv_normal = _inverse(normal)
    rhs = _matvec(at, bw)
    x = _matvec(inv_normal, rhs)
    residuals = [sum(a * b for a, b in zip(row, x)) - value for row, value in zip(rows, obs)]
    rms = math.sqrt(sum(r * r for r in residuals) / max(1, len(residuals) - 4))
    ned = _matvec(_ecef_to_ned_matrix(receiver.lat_rad, receiver.lon_rad), x[:3])
    cov_ecef = [max(inv_normal[i][i] * rms * rms, 1.0e-6) for i in range(3)]
    std_ecef = [math.sqrt(v) for v in cov_ecef]
    # 中文说明：NED STD 采用保守对角近似，避免在 provider toy 中伪造完整相关性。
    std_ned = [max(std_ecef) for _ in range(3)]
    gdop_like = math.sqrt(sum(inv_normal[i][i] for i in range(4)))
    return DopplerVelocitySolution(
        time=used[0].time,
        vn=ned[0],
        ve=ned[1],
        vd=ned[2],
        std_vn=std_ned[0],
        std_ve=std_ned[1],
        std_vd=std_ned[2],
        sat_count=len(used),
        gdop_like=gdop_like,
        provider_status="available",
        residual_rms_mps=rms,
        metadata={"mode": "provider_backed_ls", "receiver_clock_drift_mps": x[3]},
    )
