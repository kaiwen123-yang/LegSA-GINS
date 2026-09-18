"""T5a trace-free D4 diagnostics over caller-verified, immutable arrays.

No file access, providers, solver calls or corrections occur in this module.
Frozen IMU increments are already installed, scaled and gyro-debiased.
"""
from __future__ import annotations

import math
import numpy as np

from ...input_generation.status_yaw_builder import (
    apply_status_valid_filter, _prepared_rows, status_time_header, status_time_sys,
)
from .readonly_closeout import region_masks

GRAVITY_MPS2 = 9.801554354839126
MAX_GAP_S = .1
HISTOGRAM_EDGES = [-180, -90, -45, -20, -10, -5, -2, -1, 0, 1, 2, 5, 10, 20, 45, 90, 180]
QUALITY = ("all", "both_fixed", "float_involved", "other", "unknown")
ACCEL_BINS = ("all", "lt_0p3", "from_0p3_to_1", "gt_1", "unavailable")


def _quality(row):
    values = [_finite(row.get(key)) for key in ("receiver1_carrSoln", "receiver2_carrSoln")]
    if any(value is None or value not in (0, 1, 2, 3) for value in values):
        return "unknown"
    pair = tuple(int(value) for value in values)
    return "both_fixed" if pair == (2, 2) else "float_involved" if set(pair) <= {1, 2} else "other"


def _finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def _delta(row):
    values = [_finite(row.get(key)) for key in ("yaw_raw_unrounded_deg", "yaw_a1_deg", "delta_raw_minus_a1_deg")]
    return (values[2] + 180) % 360 - 180 if all(value is not None for value in values) else None


def _scopes(times, sequence_id, window):
    result = {"full_provider": np.ones(len(times), dtype=bool)}
    for name, mask in region_masks(times, sequence_id, window).items():
        result["evaluation_window" if name == "full" else name] = mask
    return result


def _array(values, width, name):
    a = np.asarray(values, float)
    if a.ndim != 2 or a.shape[1] != width or len(a) < 2 or not np.isfinite(a).all():
        raise ValueError(name + " requires finite chronological input with at least two rows")
    if np.any(np.diff(a[:, 0]) <= 0):
        raise ValueError(name + " times must strictly increase")
    return a


def _interval_supported(times, start, end, valid_intervals=None):
    """Whole closed interval support; rates belong to (t[i-1],t[i]]."""
    if start < times[0] or end > times[-1] or end <= start:
        return False
    first = max(1, int(np.searchsorted(times, start, side="right")))
    last = int(np.searchsorted(times, end, side="left"))
    good = np.diff(times[first - 1:last + 1]) <= MAX_GAP_S + 1e-12
    return bool(good.all() and (valid_intervals is None or valid_intervals[first:last + 1].all()))


def _rp_at(rp, targets):
    times = rp[:, 0]
    result = np.full((len(targets), 2), np.nan)
    valid = np.zeros(len(targets), bool)
    for i, target in enumerate(targets):
        right = int(np.searchsorted(times, target, side="left"))
        if right < len(times) and times[right] == target:
            result[i] = rp[right, 1:]
            valid[i] = True
        elif 0 < right < len(times) and times[right] - times[right - 1] <= MAX_GAP_S + 1e-12:
            alpha = (target - times[right - 1]) / (times[right] - times[right - 1])
            # Roll/pitch interpolation follows shortest wrapped angles; no fit.
            diff = (rp[right, 1:] - rp[right - 1, 1:] + np.pi) % (2 * np.pi) - np.pi
            result[i] = rp[right - 1, 1:] + alpha * diff
            valid[i] = True
    return result, valid


def _imu_diagnostics(imu, rp):
    t = imu[:, 0]
    dt = np.r_[np.nan, np.diff(t)]
    good = np.r_[False, np.diff(t) <= MAX_GAP_S + 1e-12]
    attitude, rp_good = _rp_at(rp, t)
    rp_whole = np.r_[False, [_interval_supported(rp[:, 0], a, b) for a, b in zip(t[:-1], t[1:])]]
    rp_good &= rp_whole
    rates = np.divide(imu[:, 1:4], dt[:, None])
    force = np.divide(imu[:, 4:7], dt[:, None])
    phi, theta = attitude[:, 0] + np.deg2rad(1.), attitude[:, 1]
    gravity_body = GRAVITY_MPS2 * np.column_stack((-np.sin(theta), np.cos(theta) * np.sin(phi), np.cos(theta) * np.cos(phi)))
    acceleration = np.linalg.norm(force + gravity_body, axis=1)
    euler = (rates[:, 1] * np.sin(phi) + rates[:, 2] * np.cos(phi)) / np.cos(theta)
    euler_good = good & rp_good & (np.abs(np.cos(theta)) > .1) & np.isfinite(euler)
    accel_good = good & rp_good & np.isfinite(acceleration)
    return dict(times=t, good=good, rp_good=rp_good, acceleration=acceleration,
                accel_good=accel_good, z=rates[:, 2], euler=euler, euler_good=euler_good)


def _integral(t, rates, left, right):
    # Invalid intervals never enter a reported pair (checked separately).
    values = np.r_[0., np.cumsum(np.nan_to_num(rates[1:]) * np.diff(t))]
    return float(np.interp(right, t, values) - np.interp(left, t, values))


def _statistics(values, suffix, total=None):
    a = np.asarray(values, float)
    if not np.isfinite(a).all():
        raise ValueError("Nonfinite diagnostic value; deletion forbidden")
    total = len(a) if total is None else int(total)
    out = dict(count=len(a), n=len(a), total_count=total, available_count=len(a), unavailable_count=total-len(a),
               status="AVAILABLE" if len(a) == total and len(a) else "AVAILABLE_PARTIAL_SUPPORT" if len(a)
               else "UNAVAILABLE_NO_FINITE_SOURCE" if total else "UNAVAILABLE_EMPTY_SELECTION")
    for name, fn in (("mean", np.mean), ("std_population", lambda x: np.std(x, ddof=0)),
                     ("p95_absolute", lambda x: np.percentile(np.abs(x), 95)),
                     ("p95_signed", lambda x: np.percentile(x, 95)), ("minimum", np.min), ("maximum", np.max)):
        out[name + "_" + suffix] = float(fn(a)) if len(a) else None
    return out


def _status_key(row):
    return int(round(float(row["time_gps_tow"]) * 1000))


def _status_map(rows):
    out = {}
    for row in rows:
        try:
            key = _status_key(row)
        except (ValueError, TypeError, KeyError):
            continue
        out.setdefault(key, []).append(row)
    return out


def _time_or_none(fn, row):
    try:
        result = fn(row)
        return float(result) if math.isfinite(result) else None
    except (ValueError, TypeError, KeyError):
        return None


def _timings(epochs, status1, status2):
    maps = [_status_map(rows) for rows in (status1, status2)]
    prepared, _ = _prepared_rows(apply_status_valid_filter(status2, "gnss2")[0])
    times = np.array([r["t"] for r in prepared], float)
    rows = []
    for epoch in epochs:
        row = dict(sequence_id=epoch["sequence_id"], time_s=epoch["time_s"], itow_ms=epoch["itow_ms"],
                   quality=epoch["raw_fixed_float_label"], status="UNAVAILABLE_STATUS_ITOW_MATCH",
                   header_delta_s=None, sys_delta_s=None, gps_delta_s=None,
                   interpolation_status="UNAVAILABLE", interpolation_left_offset_s=None,
                   interpolation_right_offset_s=None, interpolation_weight=None, nearest_header_offset_s=None)
        matches = [mapping.get(int(epoch["itow_ms"]), []) for mapping in maps]
        row.update(gnss1_same_itow_count=len(matches[0]), gnss2_same_itow_count=len(matches[1]))
        if len(matches[0]) == 1:
            target = _time_or_none(status_time_header, matches[0][0])
            if target is not None and len(times) and times[0] <= target <= times[-1]:
                right = int(np.searchsorted(times, target, side="left"))
                left = right if times[right] == target else right - 1
                gap = times[right] - times[left]
                dl, dr = float(times[left] - target), float(times[right] - target)
                row.update(interpolation_status="AVAILABLE", interpolation_left_offset_s=dl,
                           interpolation_right_offset_s=dr, interpolation_weight=0. if gap == 0 else float(-dl / gap),
                           nearest_header_offset_s=dl if abs(dl) <= abs(dr) else dr)
        if all(len(match) == 1 for match in matches):
            left, right = matches[0][0], matches[1][0]
            for name, fn in (("header", status_time_header), ("sys", status_time_sys),
                             ("gps", lambda x: float(x["time_gps_wno"]) * 604800 + float(x["time_gps_tow"]))):
                a, b = _time_or_none(fn, left), _time_or_none(fn, right)
                row[name + "_delta_s"] = b - a if a is not None and b is not None else None
            row["status"] = "AVAILABLE" if row["header_delta_s"] is not None else "UNAVAILABLE_HEADER_TIME"
        rows.append(row)
    return rows


def diagnose(sequence_id, window, diagnostic_rows, imu7, rp, status1, status2):
    """Return JSON/CSV-ready D4 facts; caller writes and pins all provenance.

    ``rp`` columns are time seconds, frozen FRD roll radians, frozen pitch radians.
    ``imu7`` columns are time, installed/debiased dtheta xyz, installed/scaled dv xyz.
    Only frozen A1-valid E rows enter source consistency, including float rows.
    """
    imu, rp = _array(imu7, 7, "IMU"), _array(rp, 3, "RP")
    motion = _imu_diagnostics(imu, rp)
    epochs = [dict(row) for row in diagnostic_rows if bool(int(float(row["a1_valid"])))]
    epochs.sort(key=lambda row: int(row["itow_ms"]))
    if len({int(row["itow_ms"]) for row in epochs}) != len(epochs):
        raise ValueError("Duplicate E iTOW")
    times = np.array([float(row["time_s"]) for row in epochs])
    if len(times) and (not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
        raise ValueError("E times must be finite and increasing")
    scopes = _scopes(times, sequence_id, window)
    for i, row in enumerate(epochs):
        row.update(sequence_id=sequence_id, raw_fixed_float_label=_quality(row),
                   segment="outside_window" if not scopes["evaluation_window"][i] else "outside")
        row.update(source_delta_status="AVAILABLE" if _delta(row) is not None else "UNAVAILABLE_RAW_OR_A1_HEADING",
                   delta_raw_minus_a1_deg=_delta(row))
        for label in ("occlusion_primary", "occlusion_secondary"):
            if label in scopes and scopes[label][i]: row["segment"] = label
        index = int(np.searchsorted(motion["times"], times[i], side="left"))
        imu_ok = 0 < index < len(imu) and bool(motion["good"][index])
        rp_ok = imu_ok and bool(motion["rp_good"][index])
        accel_ok = imu_ok and bool(motion["accel_good"][index])
        value = float(motion["acceleration"][index]) if accel_ok else None
        row.update(imu_supported=imu_ok, rp_supported=rp_ok, acceleration_mps2=value,
                   acceleration_bin="unavailable" if value is None else "lt_0p3" if value < .3 else "from_0p3_to_1" if value <= 1 else "gt_1")
    source, histograms = [], []
    for scope, mask in scopes.items():
        for quality in QUALITY:
            selected = [row for row, keep in zip(epochs, mask) if keep and (quality == "all" or row["raw_fixed_float_label"] == quality)]
            for acceleration_bin in ACCEL_BINS:
                subset = [row for row in selected if acceleration_bin == "all" or row["acceleration_bin"] == acceleration_bin]
                values = [value for row in subset if (value := _delta(row)) is not None]
                source.append(dict(category="delta", sequence_id=sequence_id, scope=scope, quality=quality,
                                   acceleration_bin=acceleration_bin, **_statistics(values, "deg", len(subset))))
            values = [value for row in selected if (value := _delta(row)) is not None]
            counts, _ = np.histogram(values, bins=HISTOGRAM_EDGES)
            histograms.extend(dict(sequence_id=sequence_id, scope=scope, quality=quality, bin_left_deg=left,
                                   bin_right_deg=right, count=int(count), total_count=len(selected),
                                   available_count=len(values), unavailable_count=len(selected)-len(values), right_edge_inclusive=right == 180)
                              for left, right, count in zip(HISTOGRAM_EDGES[:-1], HISTOGRAM_EDGES[1:], counts))
    by_key = {int(row["itow_ms"]): row for row in epochs}
    pairs = []
    for key, left in by_key.items():
        right = by_key.get(key + 1000)
        if right is None: continue
        a, b = float(left["time_s"]), float(right["time_s"])
        source_rows = [row for row in diagnostic_rows if key <= int(row["itow_ms"]) <= key + 1000]
        qualities = [_quality(row) for row in source_rows]
        both_fixed = bool(qualities) and all(q == "both_fixed" for q in qualities)
        fixed_float = bool(qualities) and all(q in ("both_fixed", "float_involved") for q in qualities)
        quality = "unknown" if "unknown" in qualities else "both_fixed" if both_fixed else "float_involved" if fixed_float else "other"
        missing_raw_count = sum(_finite(row.get("yaw_raw_unrounded_deg")) is None for row in source_rows)
        unknown_pvt_count = qualities.count("unknown")
        source_supported = fixed_float and missing_raw_count == 0
        supported = _interval_supported(motion["times"], a, b, motion["good"])
        euler_supported = source_supported and supported and _interval_supported(motion["times"], a, b, motion["euler_good"])
        endpoints = [_finite(row.get("yaw_raw_unrounded_deg")) for row in (left, right)]
        dy = (endpoints[1] - endpoints[0] + 180) % 360 - 180 if all(value is not None for value in endpoints) else None
        pair = dict(sequence_id=sequence_id, start_s=a, end_s=b, start_itow_ms=key, end_itow_ms=key + 1000,
                    quality=quality, raw_fixed_only_eligible=both_fixed, raw_fixed_float_eligible=fixed_float,
                    start_quality=left["raw_fixed_float_label"], end_quality=right["raw_fixed_float_label"],
                    source_interval_count=len(source_rows), source_supported=source_supported,
                    missing_raw_interval_count=missing_raw_count, unknown_pvt_interval_count=unknown_pvt_count,
                    imu_supported=supported, installed_z_supported=source_supported and supported, euler_supported=euler_supported,
                    yaw_increment_deg=dy, installed_z_residual_deg=None, euler_yaw_rate_residual_deg=None,
                    status="UNAVAILABLE_RAW_OR_PVT_SUPPORT" if not source_supported else "AVAILABLE" if euler_supported else "UNAVAILABLE_IMU_OR_RP_SUPPORT")
        for name, rate, ok in (("installed_z", motion["z"], source_supported and supported), ("euler_yaw_rate", motion["euler"], euler_supported)):
            if ok: pair[name + "_residual_deg"] = dy - math.degrees(_integral(motion["times"], rate, a, b))
        pairs.append(pair)
    for scope in scopes:
        for quality in QUALITY:
            selected = []
            for pair in pairs:
                endpoints = _scopes(np.array([pair["start_s"], pair["end_s"]]), sequence_id, window)
                if endpoints[scope].all() and (quality == "all" or quality == pair["quality"]): selected.append(pair)
            for projection in ("installed_z", "euler_yaw_rate"):
                values = [r[projection + "_residual_deg"] for r in selected if r[projection + "_residual_deg"] is not None]
                statistics = _statistics(values, "deg", len(selected))
                statistics.update(status="AVAILABLE" if len(values) >= 2 else "UNAVAILABLE_FEWER_THAN_TWO_PAIRS")
                source.append(dict(category="sigma", sequence_id=sequence_id, scope=scope, quality=quality,
                    projection=projection, candidate_pair_count=len(selected), unsupported_pair_count=len(selected) - len(values),
                    effective_sigma_deg=float(np.std(values, ddof=1) / np.sqrt(2)) if len(values) >= 2 else None,
                    report_only=True, **statistics))
    timing_rows = _timings(epochs, status1, status2)
    timing_fields = ("header_delta_s", "sys_delta_s", "gps_delta_s", "interpolation_left_offset_s",
                     "interpolation_right_offset_s", "interpolation_weight", "nearest_header_offset_s")
    for scope, mask in scopes.items():
        for quality in QUALITY:
            selected = [row for row, keep in zip(timing_rows, mask) if keep and (quality == "all" or row["quality"] == quality)]
            for field in timing_fields:
                values = [row[field] for row in selected if row[field] is not None]
                source.append(dict(category="timing", sequence_id=sequence_id, scope=scope, quality=quality,
                                   timing_field=field, total_epochs=len(selected), unmatched_count=len(selected) - len(values),
                                   **_statistics(values, "dimensionless" if field == "interpolation_weight" else "s", len(selected))))
    def json_ready(value):
        if isinstance(value, np.generic): return json_ready(value.item())
        if isinstance(value, float) and not math.isfinite(value): return None
        if isinstance(value, dict): return {key: json_ready(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)): return [json_ready(item) for item in value]
        return value
    return json_ready(dict(source_consistency_rows=source, per_epoch=epochs, histograms=histograms,
                           sigma_pairs=pairs, timing_rows=timing_rows))
