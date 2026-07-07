"""Common epoch/common satellite matching for dual receiver RAWX data."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.raw_doppler_types import RawDopplerMeasurement
from legsa_gins.raw_gnss.ubx_rawx_parser import parse_rawx_from_csv


def satellite_key(meas: RawDopplerMeasurement) -> str:
    return f"{meas.gnss_id}:{meas.sv_id}:{meas.sig_id}:{meas.freq_id}"


def group_by_epoch_sat(measurements: list[RawDopplerMeasurement]) -> dict[float, dict[str, RawDopplerMeasurement]]:
    grouped: dict[float, dict[str, RawDopplerMeasurement]] = defaultdict(dict)
    for meas in measurements:
        grouped[round(float(meas.rcv_tow), 3)][satellite_key(meas)] = meas
    return dict(grouped)


def match_rawx_common(gnss1_raw: str | Path, gnss2_raw: str | Path) -> dict[str, Any]:
    meas1 = parse_rawx_from_csv(gnss1_raw)
    meas2 = parse_rawx_from_csv(gnss2_raw)
    grouped1 = group_by_epoch_sat(meas1)
    grouped2 = group_by_epoch_sat(meas2)
    common_epochs = sorted(set(grouped1) & set(grouped2))
    rows: list[dict[str, Any]] = []
    for epoch in common_epochs:
        sats = sorted(set(grouped1[epoch]) & set(grouped2[epoch]))
        if sats:
            rows.append({"rcv_tow": epoch, "common_satellite_count": len(sats), "satellites": sats})
    counts = [int(row["common_satellite_count"]) for row in rows]
    return {
        "gnss1_rawx_measurement_count": len(meas1),
        "gnss2_rawx_measurement_count": len(meas2),
        "gnss1_rawx_epoch_count": len(grouped1),
        "gnss2_rawx_epoch_count": len(grouped2),
        "common_epoch_count": len(common_epochs),
        "common_epoch_with_satellite_count": len(rows),
        "max_common_satellite_count": max(counts) if counts else 0,
        "median_common_satellite_count": sorted(counts)[len(counts) // 2] if counts else 0,
        "sample_rows": rows[:20],
        "common_rawx_available": bool(rows),
        "blocker_reasons": [] if rows else ["no_common_rawx_epoch_satellite"],
    }
