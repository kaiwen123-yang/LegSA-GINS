"""BY2 provider factory for DA2R2 external literature execution."""

from __future__ import annotations

import csv
import math
from bisect import bisect_left
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .by2_classic_case_manifest import seed_for_case
from .yaw_frame_contract import baseline_heading_ned_deg, baseline_heading_to_body_yaw_deg, wrap360_deg


@dataclass(frozen=True)
class ProviderEpoch:
    time: float
    pos_n_m: float
    pos_e_m: float
    pos_u_m: float
    vel_n_mps: float
    vel_e_mps: float
    vel_u_mps: float
    baseline_n_m: float
    baseline_e_m: float
    baseline_d_m: float
    baseline_length_m: float
    baseline_heading_deg: float
    body_yaw_meas_deg: float
    yaw_std_deg: float
    pos_std_m: float
    yaw_rate_rad_s: float
    valid_position: bool
    valid_yaw: bool


@dataclass(frozen=True)
class TraceEpoch:
    time: float
    lat_deg: float
    lon_deg: float
    height_m: float
    yaw_deg: float
    pos_n_m: float
    pos_e_m: float
    pos_u_m: float


@dataclass(frozen=True)
class BY2Provider:
    epochs: list[ProviderEpoch]
    trace: list[TraceEpoch]
    raw_summary: dict[str, str]
    go2_summary: dict[str, str]
    status_summary: dict[str, str]
    origin_lat_deg: float
    origin_lon_deg: float
    origin_height_m: float


def build_by2_provider(receiver_root: Path, go2_body_path: Path) -> BY2Provider:
    gnss1_rows = _read_csv(receiver_root / "gnss1-status.csv")
    gnss2_rows = _read_csv(receiver_root / "gnss2-status.csv")
    origin = _first_valid_origin(gnss1_rows)
    go2_yaw_rates, go2_summary = _parse_go2_yaw_rates(go2_body_path)
    epochs = _build_status_epochs(gnss1_rows, gnss2_rows, origin, go2_yaw_rates)
    trace_path = next(receiver_root.glob("trace_vrtk2*.csv"))
    trace = _load_trace(trace_path, origin)
    raw_summary = _raw_summary(receiver_root)
    status_summary = _status_summary(epochs)
    return BY2Provider(
        epochs=epochs,
        trace=trace,
        raw_summary=raw_summary,
        go2_summary=go2_summary,
        status_summary=status_summary,
        origin_lat_deg=origin[0],
        origin_lon_deg=origin[1],
        origin_height_m=origin[2],
    )


def apply_classic_case(epochs: list[ProviderEpoch], case_id: str) -> list[ProviderEpoch]:
    if not epochs:
        return []
    seed = seed_for_case(case_id)
    rng = np.random.default_rng(seed)
    family = _case_family(case_id)
    times = [epoch.time for epoch in epochs]
    start = times[0]
    mid = 0.5 * (times[0] + times[-1])
    out: list[ProviderEpoch] = []
    for idx, epoch in enumerate(epochs):
        pos_n, pos_e, pos_u = epoch.pos_n_m, epoch.pos_e_m, epoch.pos_u_m
        yaw = epoch.body_yaw_meas_deg
        pos_std = epoch.pos_std_m
        yaw_std = epoch.yaw_std_deg
        valid_position = epoch.valid_position
        valid_yaw = epoch.valid_yaw
        if family == "outage" and mid <= epoch.time < mid + 10.0:
            valid_position = False
            valid_yaw = False
        if family == "downsample":
            interval = 0.5 if "2Hz" in case_id else 1.0
            valid = abs(((epoch.time - start) / interval) - round((epoch.time - start) / interval)) < 0.08
            valid_position = valid_position and valid
            valid_yaw = valid_yaw and valid
        if family == "position_noise" or family == "mixed":
            sigma = 0.45 if family == "position_noise" else 0.35
            pos_n += float(rng.normal(0.0, sigma))
            pos_e += float(rng.normal(0.0, sigma))
            pos_u += float(rng.normal(0.0, 0.12))
            pos_std = max(pos_std, sigma)
        if family == "position_spike":
            if idx in _spike_indices(len(epochs), seed, count=8):
                pos_n += float(rng.normal(0.0, 3.0))
                pos_e += float(rng.normal(0.0, 3.0))
                pos_u += float(rng.normal(0.0, 0.8))
                pos_std = max(pos_std, 3.0)
        if family == "std_inflation":
            pos_std *= 4.0
            yaw_std *= 4.0
        if family == "yaw_spike":
            if idx in _spike_indices(len(epochs), seed, count=8):
                yaw = wrap360_deg(yaw + (10.0 if idx % 2 == 0 else -10.0))
                yaw_std = max(yaw_std, 10.0)
        if family == "yawstd_inflation":
            yaw_std *= 2.0
        if family == "mixed":
            if mid <= epoch.time < mid + 6.0:
                valid_yaw = False
            if idx in _spike_indices(len(epochs), seed + 100, count=6):
                yaw = wrap360_deg(yaw + (8.0 if idx % 2 == 0 else -8.0))
                yaw_std = max(yaw_std, 8.0)
            if idx % 3 != 0:
                valid_position = False
                valid_yaw = False
        out.append(
            replace(
                epoch,
                pos_n_m=pos_n,
                pos_e_m=pos_e,
                pos_u_m=pos_u,
                body_yaw_meas_deg=yaw,
                pos_std_m=pos_std,
                yaw_std_deg=yaw_std,
                valid_position=valid_position,
                valid_yaw=valid_yaw,
            )
        )
    return out


def _case_family(case_id: str) -> str:
    if "outage" in case_id:
        return "outage"
    if "downsample" in case_id:
        return "downsample"
    if "position_noise" in case_id:
        return "position_noise"
    if "position_spike" in case_id:
        return "position_spike"
    if "std_inflation" in case_id:
        return "std_inflation"
    if "yaw_spike" in case_id:
        return "yaw_spike"
    if "yawstd_inflation" in case_id:
        return "yawstd_inflation"
    if "mixed" in case_id:
        return "mixed"
    return "normal"


def _spike_indices(length: int, seed: int, *, count: int) -> set[int]:
    rng = np.random.default_rng(seed + 12345)
    if length <= count:
        return set(range(length))
    low = max(1, length // 10)
    high = max(low + 1, length - length // 10)
    return set(int(item) for item in rng.choice(np.arange(low, high), size=count, replace=False))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as handle:
        return list(csv.DictReader(handle))


def _build_status_epochs(
    gnss1_rows: list[dict[str, str]],
    gnss2_rows: list[dict[str, str]],
    origin: tuple[float, float, float],
    go2_yaw_rates: list[tuple[float, float]],
) -> list[ProviderEpoch]:
    gnss2_times = [_float(row, "Time") for row in gnss2_rows]
    rows: list[ProviderEpoch] = []
    for row1 in gnss1_rows:
        time1 = _float(row1, "Time")
        if math.isnan(time1):
            continue
        row2 = _nearest_row(gnss2_rows, gnss2_times, time1)
        if row2 is None:
            continue
        time2 = _float(row2, "Time")
        lat, lon, height = _float(row1, "pos_lat"), _float(row1, "pos_lon"), _float(row1, "pos_height")
        if any(math.isnan(v) for v in (lat, lon, height)):
            continue
        n, e, u = geodetic_to_enu(lat, lon, height, origin)
        baseline_n = _float(row2, "rel_pos_n") - _float(row1, "rel_pos_n")
        baseline_e = _float(row2, "rel_pos_e") - _float(row1, "rel_pos_e")
        baseline_d = _float(row2, "rel_pos_d") - _float(row1, "rel_pos_d")
        length = math.sqrt(baseline_n * baseline_n + baseline_e * baseline_e + baseline_d * baseline_d)
        heading = baseline_heading_ned_deg(baseline_n, baseline_e)
        rel_acc = math.sqrt(
            max(0.0, _float(row1, "rel_acc_n", 0.0) ** 2 + _float(row1, "rel_acc_e", 0.0) ** 2 + _float(row1, "rel_acc_d", 0.0) ** 2)
            + max(0.0, _float(row2, "rel_acc_n", 0.0) ** 2 + _float(row2, "rel_acc_e", 0.0) ** 2 + _float(row2, "rel_acc_d", 0.0) ** 2)
        )
        yaw_std = min(45.0, max(0.5, math.degrees(math.atan2(rel_acc, max(length, 1e-3)))))
        pos_std = max(_float(row1, "pos_acc_h", 0.5), 0.05)
        valid_yaw = abs(time2 - time1) <= 1.0 and _bool(row1, "rel_valid") and _bool(row2, "rel_valid") and _bool(row1, "fix_ok") and _bool(row2, "fix_ok") and 0.2 <= length <= 2.0
        valid_position = _bool(row1, "pos_valid") and _bool(row1, "fix_ok")
        rows.append(
            ProviderEpoch(
                time=time1,
                pos_n_m=n,
                pos_e_m=e,
                pos_u_m=u,
                vel_n_mps=0.0,
                vel_e_mps=0.0,
                vel_u_mps=0.0,
                baseline_n_m=baseline_n,
                baseline_e_m=baseline_e,
                baseline_d_m=baseline_d,
                baseline_length_m=length,
                baseline_heading_deg=heading,
                body_yaw_meas_deg=baseline_heading_to_body_yaw_deg(heading),
                yaw_std_deg=yaw_std,
                pos_std_m=pos_std,
                yaw_rate_rad_s=_nearest_yaw_rate(go2_yaw_rates, time1),
                valid_position=valid_position,
                valid_yaw=valid_yaw,
            )
        )
    return _with_velocity(rows)


def _with_velocity(rows: list[ProviderEpoch]) -> list[ProviderEpoch]:
    if not rows:
        return []
    out: list[ProviderEpoch] = []
    for idx, row in enumerate(rows):
        if idx == 0:
            nxt = rows[min(1, len(rows) - 1)]
            dt = max(nxt.time - row.time, 1e-3)
            vn, ve, vu = (nxt.pos_n_m - row.pos_n_m) / dt, (nxt.pos_e_m - row.pos_e_m) / dt, (nxt.pos_u_m - row.pos_u_m) / dt
        else:
            prev = rows[idx - 1]
            dt = max(row.time - prev.time, 1e-3)
            vn, ve, vu = (row.pos_n_m - prev.pos_n_m) / dt, (row.pos_e_m - prev.pos_e_m) / dt, (row.pos_u_m - prev.pos_u_m) / dt
        out.append(replace(row, vel_n_mps=vn, vel_e_mps=ve, vel_u_mps=vu))
    return out


def _nearest_row(rows: list[dict[str, str]], times: list[float], time_s: float) -> dict[str, str] | None:
    pos = bisect_left(times, time_s)
    candidates = []
    if pos < len(rows):
        candidates.append(rows[pos])
    if pos:
        candidates.append(rows[pos - 1])
    return min(candidates, key=lambda row: abs(_float(row, "Time") - time_s)) if candidates else None


def _nearest_yaw_rate(samples: list[tuple[float, float]], time_s: float) -> float:
    if not samples:
        return 0.0
    times = [item[0] for item in samples]
    pos = bisect_left(times, time_s)
    candidates = []
    if pos < len(samples):
        candidates.append(samples[pos])
    if pos:
        candidates.append(samples[pos - 1])
    nearest = min(candidates, key=lambda item: abs(item[0] - time_s))
    return nearest[1] if abs(nearest[0] - time_s) <= 0.5 else 0.0


def _parse_go2_yaw_rates(path: Path) -> tuple[list[tuple[float, float]], dict[str, str]]:
    samples: list[tuple[float, float]] = []
    sec: int | None = None
    nanosec: int | None = None
    in_stamp = False
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line == "stamp:":
                in_stamp = True
                sec = None
                nanosec = None
            elif in_stamp and line.startswith("sec:"):
                sec = _int_value(line.split(":", 1)[1])
            elif in_stamp and line.startswith("nanosec:"):
                nanosec = _int_value(line.split(":", 1)[1])
                in_stamp = False
            elif line.startswith("yaw_speed:") and sec is not None and nanosec is not None:
                value = _float_text(line.split(":", 1)[1], 0.0)
                samples.append((float(sec) + float(nanosec) * 1e-9, value))
    samples.sort()
    return samples, {
        "epoch_count": str(len(samples)),
        "has_yaw_speed": str(bool(samples)).lower(),
        "receiver_imu_as_body_imu": "false",
        "go2_position_velocity_yaw_truth": "false",
        "source_role": "sportmodestate_yaw_rate_source_not_truth",
    }


def _load_trace(path: Path, origin: tuple[float, float, float]) -> list[TraceEpoch]:
    trace: list[TraceEpoch] = []
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as handle:
        for row in csv.DictReader(handle):
            try:
                time = float(row["time"])
                lat = float(row["lat"])
                lon = float(row["lon"])
                height = float(row["height"])
                yaw = float(row["yaw"]) % 360.0
            except (KeyError, TypeError, ValueError):
                continue
            n, e, u = geodetic_to_enu(lat, lon, height, origin)
            trace.append(TraceEpoch(time=time, lat_deg=lat, lon_deg=lon, height_m=height, yaw_deg=yaw, pos_n_m=n, pos_e_m=e, pos_u_m=u))
    trace.sort(key=lambda item: item.time)
    return trace


def nearest_trace(trace: list[TraceEpoch], time_s: float, *, max_dt_s: float = 0.75) -> TraceEpoch | None:
    if not trace:
        return None
    times = [item.time for item in trace]
    pos = bisect_left(times, time_s)
    candidates = []
    if pos < len(trace):
        candidates.append(trace[pos])
    if pos:
        candidates.append(trace[pos - 1])
    if not candidates:
        return None
    nearest = min(candidates, key=lambda item: abs(item.time - time_s))
    return nearest if abs(nearest.time - time_s) <= max_dt_s else None


def _raw_summary(receiver_root: Path) -> dict[str, str]:
    summary: dict[str, str] = {}
    for name in ("gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv"):
        path = receiver_root / name
        summary[name.replace(".csv", "_rows")] = str(_count_rows(path))
    summary["raw_payload_exported"] = "false"
    summary["rinex_feasibility"] = "raw_csv_present_not_converted_in_DA2R2_min3"
    return summary


def _status_summary(epochs: list[ProviderEpoch]) -> dict[str, str]:
    valid = [epoch for epoch in epochs if epoch.valid_yaw]
    lengths = sorted(epoch.baseline_length_m for epoch in valid)
    return {
        "epoch_count": str(len(epochs)),
        "valid_yaw_epoch_count": str(len(valid)),
        "median_baseline_length_m": f"{lengths[len(lengths)//2]:.6f}" if lengths else "not_available",
        "gnss_order": "baseline_vector=GNSS2_minus_GNSS1",
        "lateral_body_yaw_policy": "body_yaw=baseline_heading_plus_90_deg",
        "trace_used_for_sign_or_offset": "false",
    }


def _count_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _first_valid_origin(rows: list[dict[str, str]]) -> tuple[float, float, float]:
    for row in rows:
        lat, lon, height = _float(row, "pos_lat"), _float(row, "pos_lon"), _float(row, "pos_height")
        if not any(math.isnan(v) for v in (lat, lon, height)):
            return lat, lon, height
    raise ValueError("No valid GNSS1 origin row")


def geodetic_to_enu(lat_deg: float, lon_deg: float, height_m: float, origin: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = _geodetic_to_ecef(lat_deg, lon_deg, height_m)
    x0, y0, z0 = _geodetic_to_ecef(origin[0], origin[1], origin[2])
    lat0 = math.radians(origin[0])
    lon0 = math.radians(origin[1])
    dx, dy, dz = x - x0, y - y0, z - z0
    east = -math.sin(lon0) * dx + math.cos(lon0) * dy
    north = -math.sin(lat0) * math.cos(lon0) * dx - math.sin(lat0) * math.sin(lon0) * dy + math.cos(lat0) * dz
    up = math.cos(lat0) * math.cos(lon0) * dx + math.cos(lat0) * math.sin(lon0) * dy + math.sin(lat0) * dz
    return north, east, up


def _geodetic_to_ecef(lat_deg: float, lon_deg: float, height_m: float) -> tuple[float, float, float]:
    a = 6378137.0
    e2 = 6.69437999014e-3
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    x = (n + height_m) * math.cos(lat) * math.cos(lon)
    y = (n + height_m) * math.cos(lat) * math.sin(lon)
    z = (n * (1.0 - e2) + height_m) * math.sin(lat)
    return x, y, z


def _float(row: dict[str, str], key: str, default: float = math.nan) -> float:
    return _float_text(row.get(key, ""), default)


def _float_text(text: str, default: float = math.nan) -> float:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def _int_value(text: str) -> int | None:
    try:
        return int(str(text).strip())
    except ValueError:
        return None


def _bool(row: dict[str, str], key: str) -> bool:
    return str(row.get(key, "")).strip().lower() in {"true", "1", "yes"}
