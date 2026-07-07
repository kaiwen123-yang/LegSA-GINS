"""Receiver approximate-position sources for DA01R1 LOS construction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import WGS84_A, WGS84_E2, as_bool, as_float, llh_to_ecef, percentile, read_csv_rows, status_time


@dataclass(frozen=True)
class ReceiverApproxPosition:
    receiver_id: str
    source: str
    x_ecef: float
    y_ecef: float
    z_ecef: float
    lat_deg: float
    lon_deg: float
    height_m: float
    time_span: str
    source_allowed: bool
    notes: str = ""

    @property
    def ecef(self) -> tuple[float, float, float]:
        return (self.x_ecef, self.y_ecef, self.z_ecef)


def ecef_to_llh(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert ECEF meters to geodetic latitude/longitude/height."""

    a = WGS84_A
    e2 = WGS84_E2
    b = a * math.sqrt(1.0 - e2)
    ep2 = (a * a - b * b) / (b * b)
    p = math.hypot(x, y)
    theta = math.atan2(z * a, p * b)
    sin_t = math.sin(theta)
    cos_t = math.cos(theta)
    lon = math.atan2(y, x)
    lat = math.atan2(z + ep2 * b * sin_t**3, p - e2 * a * cos_t**3)
    sin_lat = math.sin(lat)
    n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    height = p / math.cos(lat) - n
    return (math.degrees(lat), math.degrees(lon), height)


def parse_rinex_header_approx_position(obs_path: str | Path, *, receiver_id: str) -> ReceiverApproxPosition | None:
    path = Path(obs_path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "APPROX POSITION XYZ" not in line:
                continue
            parts = line[:60].split()
            if len(parts) < 3:
                return None
            x, y, z = (float(parts[0]), float(parts[1]), float(parts[2]))
            lat, lon, height = ecef_to_llh(x, y, z)
            return ReceiverApproxPosition(
                receiver_id=receiver_id,
                source="rinex_header_approx_position",
                x_ecef=x,
                y_ecef=y,
                z_ecef=z,
                lat_deg=lat,
                lon_deg=lon,
                height_m=height,
                time_span="rinex_header_static",
                source_allowed=True,
                notes="RINEX OBS header approximate ECEF position.",
            )
            break
    return None


def _valid_status_position(row: dict[str, Any]) -> bool:
    if "pos_valid" in row and not as_bool(row.get("pos_valid")):
        return False
    if "fix_ok" in row and not as_bool(row.get("fix_ok")):
        return False
    return all(as_float(row.get(name)) is not None for name in ("pos_lat", "pos_lon", "pos_height"))


def status_receiver_position(status_path: str | Path, *, receiver_id: str) -> ReceiverApproxPosition | None:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(status_path):
        if not _valid_status_position(row):
            continue
        t = status_time(row)
        lat = as_float(row.get("pos_lat"))
        lon = as_float(row.get("pos_lon"))
        height = as_float(row.get("pos_height"))
        if t is None or lat is None or lon is None or height is None:
            continue
        x, y, z = llh_to_ecef(lat, lon, height)
        rows.append({"time": t, "lat": lat, "lon": lon, "height": height, "x": x, "y": y, "z": z})
    if not rows:
        return None
    times = [row["time"] for row in rows]
    lat = percentile([row["lat"] for row in rows], 0.50)
    lon = percentile([row["lon"] for row in rows], 0.50)
    height = percentile([row["height"] for row in rows], 0.50)
    x = percentile([row["x"] for row in rows], 0.50)
    y = percentile([row["y"] for row in rows], 0.50)
    z = percentile([row["z"] for row in rows], 0.50)
    if None in (lat, lon, height, x, y, z):
        return None
    return ReceiverApproxPosition(
        receiver_id=receiver_id,
        source="gnss_status_ecef_from_llh_median",
        x_ecef=float(x),
        y_ecef=float(y),
        z_ecef=float(z),
        lat_deg=float(lat),
        lon_deg=float(lon),
        height_m=float(height),
        time_span=f"{min(times):.3f}..{max(times):.3f}",
        source_allowed=True,
        notes="Median ECEF converted from allowed receiver status LLH; trace/final/LegSA outputs not used.",
    )


def ecef_distance_m(a: ReceiverApproxPosition, b: ReceiverApproxPosition) -> float:
    return math.sqrt(sum((aa - bb) ** 2 for aa, bb in zip(a.ecef, b.ecef)))


def choose_receiver_approx_positions(
    *,
    gnss1_obs: str | Path,
    gnss2_obs: str | Path,
    gnss1_status: str | Path | None = None,
    gnss2_status: str | Path | None = None,
    physical_min_m: float = 0.20,
    physical_max_m: float = 0.60,
) -> tuple[dict[str, ReceiverApproxPosition], list[dict[str, Any]]]:
    """Choose receiver approximate positions without using trace or solver outputs.

    RINEX header approximate positions are inspected first. If the two receiver
    header positions fail the short-baseline physical sanity check and status
    positions are available, status LLH-derived ECEF is used as the approximate
    receiver position source.
    """

    candidates: list[dict[str, Any]] = []
    header1 = parse_rinex_header_approx_position(gnss1_obs, receiver_id="gnss1")
    header2 = parse_rinex_header_approx_position(gnss2_obs, receiver_id="gnss2")
    if header1 and header2:
        distance = ecef_distance_m(header1, header2)
        candidates.append(
            {
                "candidate_source": "rinex_header_approx_position",
                "pair_distance_m": distance,
                "physical_pair_pass": physical_min_m <= distance <= physical_max_m,
                "selected": False,
                "notes": "Header inspected first per source priority.",
            }
        )
        if physical_min_m <= distance <= physical_max_m:
            candidates[-1]["selected"] = True
            return {"gnss1": header1, "gnss2": header2}, candidates
    status1 = status_receiver_position(gnss1_status, receiver_id="gnss1") if gnss1_status else None
    status2 = status_receiver_position(gnss2_status, receiver_id="gnss2") if gnss2_status else None
    if status1 and status2:
        distance = ecef_distance_m(status1, status2)
        selected = physical_min_m <= distance <= physical_max_m or not (header1 and header2)
        candidates.append(
            {
                "candidate_source": "gnss_status_ecef_from_llh_median",
                "pair_distance_m": distance,
                "physical_pair_pass": physical_min_m <= distance <= physical_max_m,
                "selected": selected,
                "notes": "Status supplies approximate receiver coordinates only; status yaw/heading is not used.",
            }
        )
        if selected:
            return {"gnss1": status1, "gnss2": status2}, candidates
    if header1 and header2:
        candidates[0]["selected"] = True
        candidates[0]["notes"] += " Status fallback unavailable; header retained for LOS only."
        return {"gnss1": header1, "gnss2": header2}, candidates
    raise ValueError("no allowed receiver approximate-position source is available")


def receiver_position_table(positions: dict[str, ReceiverApproxPosition]) -> list[dict[str, Any]]:
    return [
        {
            "receiver_id": pos.receiver_id,
            "source": pos.source,
            "x_ecef": pos.x_ecef,
            "y_ecef": pos.y_ecef,
            "z_ecef": pos.z_ecef,
            "lat_deg": pos.lat_deg,
            "lon_deg": pos.lon_deg,
            "height_m": pos.height_m,
            "time_span": pos.time_span,
            "source_allowed": pos.source_allowed,
            "notes": pos.notes,
        }
        for pos in positions.values()
    ]
