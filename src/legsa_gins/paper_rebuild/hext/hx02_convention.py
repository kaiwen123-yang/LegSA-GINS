"""HX-02 read-only convention diagnostic for heading-only methods.

On method-valid native epochs, compare the method body yaw with the receivers'
own NAV-HPPOSECEF baseline body yaw (GNSS2 - GNSS1 vector heading + 90 deg) on
epochs where both receivers report a fixed carrier solution (NAV-PVT carrSoln
== 2). HPPOSECEF/NAV-PVT iTOW = RAWX time + 2 ms (registered for all three
sequences). Uses receiver outputs only; never the reference trajectory.
Median of wrap-safe differences within +/-20 deg of +/-90 or 180 deg is a
registered hard stop (convention error); nothing is changed here.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..horizontal_literature import phase2_runner as phase2
from ..horizontal_literature.shared_raw_backend import iter_ubx_frames, reconstruct_ubx_stream
from . import hx02_sequence

HPPOSECEF_MINUS_RAWX_MS = 2
BAND_DEG = 20.0


def wrap180(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


def receiver_solutions(raw_csv: Path) -> tuple[dict[int, np.ndarray], dict[int, int]]:
    reconstruction = reconstruct_ubx_stream(Path(raw_csv), decode_nav_hpposecef_semantics=True)
    positions = {epoch.itow_ms: epoch.position_ecef_m for epoch in reconstruction.nav_hpposecef_epochs}
    carrier: dict[int, int] = {}
    for msg_class, msg_id, payload in iter_ubx_frames(reconstruction.stream):
        if (msg_class, msg_id) == (0x01, 0x07) and len(payload) == 92:
            itow = struct.unpack_from("<I", payload, 0)[0]
            carrier[itow] = (payload[21] >> 6) & 3
    return positions, carrier


def proxy_body_yaw(sequence: hx02_sequence.HX02Sequence) -> dict[int, float]:
    """RAWX-ms key -> dual-fixed HPPOSECEF baseline body yaw (deg, [0, 360))."""
    hx02_sequence.verify_raw(sequence, "gnss1_raw", "gnss2_raw")
    p1, c1 = receiver_solutions(Path(sequence.gnss1_raw))
    p2, c2 = receiver_solutions(Path(sequence.gnss2_raw))
    result = {}
    for itow in sorted(set(p1) & set(p2)):
        if c1.get(itow) != 2 or c2.get(itow) != 2:
            continue
        vector = phase2._ecef_vector_to_ned(p2[itow] - p1[itow], p1[itow])
        if math.hypot(float(vector[0]), float(vector[1])) <= 0.0:
            continue
        _heading, _elevation, body_yaw = phase2._baseline_angles(vector.tolist())
        result[itow - HPPOSECEF_MINUS_RAWX_MS] = body_yaw
    return result


def diagnose(rows: Sequence[Mapping[str, Any]], proxy: Mapping[int, float]) -> dict[str, Any]:
    differences = []
    for row in rows:
        if int(row["valid"]) != 1:
            continue
        key = int(round(float(row["gps_tow_seconds"]) * 1000.0))
        if key in proxy:
            differences.append(wrap180(float(row["body_yaw_deg"]) - proxy[key]))
    values = np.asarray(differences, dtype=float)
    if values.size == 0:
        return {"compared_epochs": 0, "median_deg": None, "hard_stop": False,
                "status": "UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH"}
    median = float(np.median(values))
    fractions = {
        "within_20_of_0": float(np.mean(np.abs(values) <= BAND_DEG)),
        "within_20_of_plus_minus_90": float(np.mean(np.abs(np.abs(values) - 90.0) <= BAND_DEG)),
        "within_20_of_180": float(np.mean(np.abs(values) >= 180.0 - BAND_DEG)),
    }
    near90 = abs(abs(median) - 90.0) <= BAND_DEG
    near180 = abs(median) >= 180.0 - BAND_DEG
    return {"compared_epochs": int(values.size), "median_deg": median,
            "mean_circular_deg": math.degrees(math.atan2(float(np.mean(np.sin(np.radians(values)))),
                                                         float(np.mean(np.cos(np.radians(values)))))),
            "fractions": fractions, "median_near_plus_minus_90": near90, "median_near_180": near180,
            "hard_stop": bool(near90 or near180), "status": "HARD_STOP" if (near90 or near180) else "PASS",
            "definition": ("wrap180(method body yaw - (GNSS2-GNSS1 HPPOSECEF baseline heading + 90 deg)) "
                           "on method-valid epochs where both receivers report carrSoln == 2")}
