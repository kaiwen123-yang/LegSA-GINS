"""Minimal GPS broadcast ephemeris satellite position and LOS provider.

This module intentionally implements a bounded GPS-only RINEX NAV path for
DA01R1. It is not a replacement for full multi-GNSS RTKLIB satellite-state
support.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.raw_doppler_types import RawDopplerMeasurement
from legsa_gins.raw_gnss.ubx_rawx_parser import parse_rawx_from_csv

from .common import ecef_delta_to_enu
from .common_epoch_satellite_matcher import group_by_epoch_sat, satellite_key
from .receiver_position import ReceiverApproxPosition


GPS_MU = 3.986005e14
GPS_OMEGA_E = 7.2921151467e-5
SECONDS_IN_HALF_WEEK = 302400.0


@dataclass(frozen=True)
class GpsBroadcastEphemeris:
    prn: int
    toe: float
    sqrt_a: float
    eccentricity: float
    delta_n: float
    m0: float
    omega0: float
    inclination0: float
    argument_of_perigee: float
    omega_dot: float
    idot: float
    cuc: float
    cus: float
    crc: float
    crs: float
    cic: float
    cis: float
    gps_week: int | None = None
    clock_epoch: str = ""


def _rinex_float(text: str) -> float:
    return float(text.strip().replace("D", "E").replace("d", "E"))


def _line_values(line: str, *, first: bool = False) -> list[float]:
    padded = line.rstrip("\n").ljust(80)
    start = 22 if first else 3
    values: list[float] = []
    for index in range(start, 79, 19):
        cell = padded[index : index + 19]
        if cell.strip():
            values.append(_rinex_float(cell))
    return values


def parse_rinex2_gps_nav(nav_path: str | Path) -> list[GpsBroadcastEphemeris]:
    path = Path(nav_path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body_start = 0
    for index, line in enumerate(lines):
        if "END OF HEADER" in line:
            body_start = index + 1
            break
    records: list[GpsBroadcastEphemeris] = []
    index = body_start
    while index + 7 < len(lines):
        block = lines[index : index + 8]
        index += 8
        if not block[0].strip():
            continue
        try:
            prn = int(block[0][:2])
        except ValueError:
            continue
        values = [_line_values(block[0], first=True)]
        values.extend(_line_values(line) for line in block[1:])
        if any(len(row) < 4 for row in values[1:7]) or len(values[0]) < 3:
            continue
        line1, line2, line3, line4, line5, line6, line7 = values[1:8]
        records.append(
            GpsBroadcastEphemeris(
                prn=prn,
                toe=line3[0],
                sqrt_a=line2[3],
                eccentricity=line2[1],
                delta_n=line1[2],
                m0=line1[3],
                omega0=line3[2],
                inclination0=line4[0],
                argument_of_perigee=line4[2],
                omega_dot=line4[3],
                idot=line5[0],
                cuc=line2[0],
                cus=line2[2],
                crc=line4[1],
                crs=line1[1],
                cic=line3[1],
                cis=line3[3],
                gps_week=int(round(line5[2])) if len(line5) > 2 else None,
                clock_epoch=block[0][:22].strip(),
            )
        )
    return records


def _gps_time_diff(seconds: float) -> float:
    while seconds > SECONDS_IN_HALF_WEEK:
        seconds -= 2.0 * SECONDS_IN_HALF_WEEK
    while seconds < -SECONDS_IN_HALF_WEEK:
        seconds += 2.0 * SECONDS_IN_HALF_WEEK
    return seconds


def choose_ephemeris(ephemerides: list[GpsBroadcastEphemeris], prn: int, tow: float) -> GpsBroadcastEphemeris | None:
    candidates = [eph for eph in ephemerides if eph.prn == prn]
    if not candidates:
        return None
    return min(candidates, key=lambda eph: abs(_gps_time_diff(tow - eph.toe)))


def gps_satellite_position_ecef(eph: GpsBroadcastEphemeris, tow: float) -> tuple[float, float, float]:
    tk = _gps_time_diff(tow - eph.toe)
    semi_major = eph.sqrt_a * eph.sqrt_a
    mean_motion = math.sqrt(GPS_MU / (semi_major**3)) + eph.delta_n
    mean_anomaly = eph.m0 + mean_motion * tk
    eccentric_anomaly = mean_anomaly
    for _ in range(12):
        eccentric_anomaly = mean_anomaly + eph.eccentricity * math.sin(eccentric_anomaly)
    sin_e = math.sin(eccentric_anomaly)
    cos_e = math.cos(eccentric_anomaly)
    true_anomaly = math.atan2(math.sqrt(1.0 - eph.eccentricity**2) * sin_e, cos_e - eph.eccentricity)
    argument_latitude = true_anomaly + eph.argument_of_perigee
    sin_2u = math.sin(2.0 * argument_latitude)
    cos_2u = math.cos(2.0 * argument_latitude)
    corrected_u = argument_latitude + eph.cus * sin_2u + eph.cuc * cos_2u
    corrected_r = semi_major * (1.0 - eph.eccentricity * cos_e) + eph.crs * sin_2u + eph.crc * cos_2u
    corrected_i = eph.inclination0 + eph.idot * tk + eph.cis * sin_2u + eph.cic * cos_2u
    x_orb = corrected_r * math.cos(corrected_u)
    y_orb = corrected_r * math.sin(corrected_u)
    omega = eph.omega0 + (eph.omega_dot - GPS_OMEGA_E) * tk - GPS_OMEGA_E * eph.toe
    cos_omega = math.cos(omega)
    sin_omega = math.sin(omega)
    cos_i = math.cos(corrected_i)
    sin_i = math.sin(corrected_i)
    x = x_orb * cos_omega - y_orb * cos_i * sin_omega
    y = x_orb * sin_omega + y_orb * cos_i * cos_omega
    z = y_orb * sin_i
    return (x, y, z)


def _unit_los(receiver: ReceiverApproxPosition, sat_pos: tuple[float, float, float]) -> tuple[float, float, float]:
    dx = sat_pos[0] - receiver.x_ecef
    dy = sat_pos[1] - receiver.y_ecef
    dz = sat_pos[2] - receiver.z_ecef
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if norm <= 0.0:
        raise ValueError("zero satellite-receiver vector")
    return (dx / norm, dy / norm, dz / norm)


def elevation_azimuth_deg(receiver: ReceiverApproxPosition, sat_pos: tuple[float, float, float]) -> tuple[float, float]:
    east, north, up = ecef_delta_to_enu(
        sat_pos[0] - receiver.x_ecef,
        sat_pos[1] - receiver.y_ecef,
        sat_pos[2] - receiver.z_ecef,
        receiver.lat_deg,
        receiver.lon_deg,
    )
    horizontal = math.hypot(east, north)
    elevation = math.degrees(math.atan2(up, horizontal))
    azimuth = math.degrees(math.atan2(east, north)) % 360.0
    return elevation, azimuth


def _gps_l1_common_groups(
    gnss1_raw: str | Path,
    gnss2_raw: str | Path,
) -> tuple[dict[float, dict[str, RawDopplerMeasurement]], dict[float, dict[str, RawDopplerMeasurement]]]:
    grouped1 = group_by_epoch_sat(
        meas for meas in parse_rawx_from_csv(gnss1_raw) if meas.gnss_id == 0 and meas.sig_id == 0 and meas.freq_id == 0
    )
    grouped2 = group_by_epoch_sat(
        meas for meas in parse_rawx_from_csv(gnss2_raw) if meas.gnss_id == 0 and meas.sig_id == 0 and meas.freq_id == 0
    )
    return grouped1, grouped2


def build_gps_l1_los_epochs(
    *,
    gnss1_raw: str | Path,
    gnss2_raw: str | Path,
    nav_path: str | Path,
    receiver_positions: dict[str, ReceiverApproxPosition],
    max_epochs: int | None = None,
) -> dict[str, Any]:
    """Build common GPS L1 epochs with satellite ECEF positions and LOS vectors."""

    ephemerides = parse_rinex2_gps_nav(nav_path)
    grouped1, grouped2 = _gps_l1_common_groups(gnss1_raw, gnss2_raw)
    epochs: list[dict[str, Any]] = []
    missing_eph = 0
    for tow in sorted(set(grouped1) & set(grouped2)):
        sat_keys = sorted(set(grouped1[tow]) & set(grouped2[tow]))
        sat_rows: list[dict[str, Any]] = []
        for key in sat_keys:
            meas1 = grouped1[tow][key]
            meas2 = grouped2[tow][key]
            if meas1.wavelength_m is None or meas2.wavelength_m is None:
                continue
            eph = choose_ephemeris(ephemerides, meas1.sv_id, meas1.rcv_tow)
            if eph is None:
                missing_eph += 1
                continue
            sat_pos = gps_satellite_position_ecef(eph, meas1.rcv_tow)
            los1 = _unit_los(receiver_positions["gnss1"], sat_pos)
            los2 = _unit_los(receiver_positions["gnss2"], sat_pos)
            elevation, azimuth = elevation_azimuth_deg(receiver_positions["gnss1"], sat_pos)
            sat_rows.append(
                {
                    "satellite_key": satellite_key(meas1),
                    "sat_id": f"G{meas1.sv_id:02d}",
                    "constellation": "GPS",
                    "frequency": "L1",
                    "gnss_id": meas1.gnss_id,
                    "sv_id": meas1.sv_id,
                    "sig_id": meas1.sig_id,
                    "freq_id": meas1.freq_id,
                    "timestamp": meas1.time,
                    "gps_week": meas1.week,
                    "rcv_tow": tow,
                    "pr1_m": meas1.pr_mes,
                    "pr2_m": meas2.pr_mes,
                    "cp1_cycles": meas1.cp_mes,
                    "cp2_cycles": meas2.cp_mes,
                    "doppler1_hz": meas1.do_mes_hz,
                    "doppler2_hz": meas2.do_mes_hz,
                    "cno1_dbhz": meas1.cno,
                    "cno2_dbhz": meas2.cno,
                    "cno_avg_dbhz": (meas1.cno + meas2.cno) * 0.5,
                    "wavelength_m": meas1.wavelength_m,
                    "sat_x": sat_pos[0],
                    "sat_y": sat_pos[1],
                    "sat_z": sat_pos[2],
                    "los1_x": los1[0],
                    "los1_y": los1[1],
                    "los1_z": los1[2],
                    "los2_x": los2[0],
                    "los2_y": los2[1],
                    "los2_z": los2[2],
                    "elevation_deg": elevation,
                    "azimuth_deg": azimuth,
                    "valid_flag": True,
                }
            )
        if sat_rows:
            epochs.append({"rcv_tow": tow, "timestamp": sat_rows[0]["timestamp"], "satellites": sat_rows})
        if max_epochs is not None and len(epochs) >= max_epochs:
            break
    counts = [len(epoch["satellites"]) for epoch in epochs]
    return {
        "provider": "python_minimal_gps_rinex2_broadcast_ephemeris",
        "multi_gnss_complete": False,
        "supported_constellations": ["GPS"],
        "supported_frequency": "L1",
        "ephemeris_count": len(ephemerides),
        "epoch_count": len(epochs),
        "max_satellite_count": max(counts) if counts else 0,
        "median_satellite_count": sorted(counts)[len(counts) // 2] if counts else 0,
        "missing_ephemeris_observation_count": missing_eph,
        "epochs": epochs,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "status_yaw_used_as_los": False,
    }


def satpos_los_csv_rows(los_report: dict[str, Any], *, max_rows: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for epoch in los_report.get("epochs", []):
        for sat in epoch.get("satellites", []):
            for receiver_id, los_prefix in (("gnss1", "los1"), ("gnss2", "los2")):
                rows.append(
                    {
                        "epoch_time": epoch["rcv_tow"],
                        "timestamp": sat["timestamp"],
                        "receiver_id": receiver_id,
                        "sat_id": sat["sat_id"],
                        "constellation": sat["constellation"],
                        "frequency": sat["frequency"],
                        "pseudorange": sat["pr1_m"] if receiver_id == "gnss1" else sat["pr2_m"],
                        "carrier_phase": sat["cp1_cycles"] if receiver_id == "gnss1" else sat["cp2_cycles"],
                        "doppler": sat["doppler1_hz"] if receiver_id == "gnss1" else sat["doppler2_hz"],
                        "sat_x": sat["sat_x"],
                        "sat_y": sat["sat_y"],
                        "sat_z": sat["sat_z"],
                        "receiver_approx_x": "",
                        "receiver_approx_y": "",
                        "receiver_approx_z": "",
                        "los_x": sat[f"{los_prefix}_x"],
                        "los_y": sat[f"{los_prefix}_y"],
                        "los_z": sat[f"{los_prefix}_z"],
                        "elevation": sat["elevation_deg"],
                        "azimuth": sat["azimuth_deg"],
                        "valid_flag": sat["valid_flag"],
                    }
                )
                if len(rows) >= max_rows:
                    return rows
    return rows
