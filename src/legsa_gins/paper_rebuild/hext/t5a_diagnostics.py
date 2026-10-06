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
STATUS_GPS_WEEK = 2408
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
    tow = float(row["time_gps_tow"])
    if not math.isfinite(tow) or not 0 <= tow < 604800:
        raise ValueError("Invalid status GPS time of week")
    key = int(round(tow * 1000))
    if key >= 604800000:
        raise ValueError("Status iTOW rounds outside the declared GPS week")
    return key


def _status_week(row):
    raw = row.get("time_gps_wno")
    if raw is None or str(raw).strip() == "":
        return None, "UNAVAILABLE_WEEK_IDENTITY"
    value = _finite(raw)
    if value is None or value != int(value) or value < 0:
        return None, "INVALID_WEEK_IDENTITY"
    week = int(value)
    return week, "VERIFIED_2408" if week == STATUS_GPS_WEEK else "GPS_WEEK_MISMATCH"


def _week_eligible(row):
    # Missing week is explicitly unverified; a known wrong/invalid week is never
    # silently paired across a rollover or substituted into week 2408.
    return _status_week(row)[1] in ("VERIFIED_2408", "UNAVAILABLE_WEEK_IDENTITY")


def _pair_week_status(first, second):
    left, left_status = _status_week(first)
    right, right_status = _status_week(second)
    if not _week_eligible(first) or not _week_eligible(second) or left is not None and right is not None and left != right:
        return "GPS_WEEK_MISMATCH"
    return "VERIFIED_2408" if left_status == right_status == "VERIFIED_2408" else "UNAVAILABLE_WEEK_IDENTITY"


def _gps_time_or_none(row):
    week, state = _status_week(row)
    tow = _finite(row.get("time_gps_tow"))
    return week * 604800 + tow if state == "VERIFIED_2408" and tow is not None and 0 <= tow < 604800 else None


def _status_map(rows, *, enforce_week=True):
    out = {}
    for row in rows:
        if enforce_week and not _week_eligible(row):
            continue
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
    all_maps = [_status_map(rows, enforce_week=False) for rows in (status1, status2)]
    prepared, _ = _prepared_rows(apply_status_valid_filter(status2, "gnss2")[0])
    rejected_week_count = sum(not _week_eligible(item["row"]) for item in prepared)
    rejected_header_count = sum(not math.isfinite(float(item["t"])) for item in prepared)
    prepared = [item for item in prepared if _week_eligible(item["row"]) and math.isfinite(float(item["t"]))]
    times = np.array([r["t"] for r in prepared], float)
    rows = []
    for epoch in epochs:
        row = dict(sequence_id=epoch["sequence_id"], time_s=epoch["time_s"], itow_ms=epoch["itow_ms"],
                   quality=epoch["raw_fixed_float_label"], status="UNAVAILABLE_STATUS_ITOW_MATCH",
                   header_delta_s=None, sys_delta_s=None, gps_delta_s=None,
                   same_itow_pair_week_status="UNAVAILABLE", fitted_offset_used=False,
                   interpolation_status="UNAVAILABLE", interpolation_left_offset_s=None,
                   interpolation_right_offset_s=None, interpolation_weight=None, nearest_header_offset_s=None,
                   nearest_header_pair_status="UNAVAILABLE_GNSS1_ITOW_MATCH",
                   nearest_header_pair_policy="MINIMUM_ABSOLUTE_HEADER_DIFFERENCE_EARLIER_HEADER_THEN_INPUT_ORDER_ON_TIE",
                   nearest_header_pair_week_status="UNAVAILABLE",
                   nearest_header_pair_header_delta_s=None, nearest_header_pair_sys_delta_s=None,
                   nearest_header_pair_gps_delta_s=None,
                   nearest_header_pair_gnss1_week=None, nearest_header_pair_gnss1_itow_ms=None,
                   nearest_header_pair_gnss2_week=None, nearest_header_pair_gnss2_itow_ms=None,
                   nearest_header_pair_gnss2_tow_s=None, nearest_header_pair_gnss2_header_s=None,
                   nearest_header_pair_gnss2_sys_s=None, nearest_header_pair_tie_count=None,
                   nearest_header_pair_target_bracketed=False,
                   gnss2_header_candidates_rejected_week_count=rejected_week_count,
                   gnss2_header_candidates_nonfinite_count=rejected_header_count)
        matches = [mapping.get(int(epoch["itow_ms"]), []) for mapping in maps]
        row.update(gnss1_same_itow_count=len(matches[0]), gnss2_same_itow_count=len(matches[1]),
                   gnss1_same_itow_rejected_week_count=len(all_maps[0].get(int(epoch["itow_ms"]), [])) - len(matches[0]),
                   gnss2_same_itow_rejected_week_count=len(all_maps[1].get(int(epoch["itow_ms"]), [])) - len(matches[1]))
        if len(matches[0]) == 1:
            first = matches[0][0]
            target = _time_or_none(status_time_header, first)
            row["nearest_header_pair_status"] = "UNAVAILABLE_GNSS1_HEADER_TIME" if target is None else "UNAVAILABLE_GNSS2_HEADER_CANDIDATE"
            if target is not None and len(times):
                distances = np.abs(times - target)
                nearest = int(np.argmin(distances))
                second = prepared[nearest]["row"]
                week_status = _pair_week_status(first, second)
                # No fitted offset and no forced same-iTOW association: the
                # selected receiver identity is retained beside each difference.
                selected_itow = None
                try:
                    selected_itow = _status_key(second)
                except (ValueError, TypeError, KeyError):
                    pass
                row.update(nearest_header_pair_status="AVAILABLE" if week_status == "VERIFIED_2408" else "AVAILABLE_HEADER_PAIR_WEEK_UNVERIFIED",
                           nearest_header_pair_week_status=week_status,
                           nearest_header_pair_gnss1_week=_status_week(first)[0],
                           nearest_header_pair_gnss1_itow_ms=_status_key(first),
                           nearest_header_pair_gnss2_week=_status_week(second)[0],
                           nearest_header_pair_gnss2_itow_ms=selected_itow,
                           nearest_header_pair_gnss2_tow_s=_finite(second.get("time_gps_tow")),
                           nearest_header_pair_gnss2_header_s=float(times[nearest]),
                           nearest_header_pair_gnss2_sys_s=_time_or_none(status_time_sys, second),
                           nearest_header_pair_tie_count=int(np.count_nonzero(distances == distances[nearest])),
                           nearest_header_pair_target_bracketed=bool(times[0] <= target <= times[-1]))
                if selected_itow is None:
                    row["nearest_header_pair_status"] = "AVAILABLE_HEADER_PAIR_GPS_IDENTITY_UNAVAILABLE"
                if week_status != "GPS_WEEK_MISMATCH":
                    for name, fn in (("header", status_time_header), ("sys", status_time_sys), ("gps", _gps_time_or_none)):
                        a, b = _time_or_none(fn, first), _time_or_none(fn, second)
                        row["nearest_header_pair_" + name + "_delta_s"] = b - a if a is not None and b is not None else None
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
            row["same_itow_pair_week_status"] = _pair_week_status(left, right)
            for name, fn in (("header", status_time_header), ("sys", status_time_sys),
                             ("gps", _gps_time_or_none)):
                a, b = _time_or_none(fn, left), _time_or_none(fn, right)
                row[name + "_delta_s"] = b - a if a is not None and b is not None else None
            row["status"] = "AVAILABLE" if row["header_delta_s"] is not None else "UNAVAILABLE_HEADER_TIME"
            if row["status"] == "AVAILABLE" and row["same_itow_pair_week_status"] != "VERIFIED_2408":
                row["status"] = "AVAILABLE_ITOW_PAIR_WEEK_UNVERIFIED"
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
                     "interpolation_right_offset_s", "interpolation_weight", "nearest_header_offset_s",
                     "nearest_header_pair_header_delta_s", "nearest_header_pair_sys_delta_s", "nearest_header_pair_gps_delta_s")
    for scope, mask in scopes.items():
        for quality in QUALITY:
            selected = [row for row, keep in zip(timing_rows, mask) if keep and (quality == "all" or row["quality"] == quality)]
            for field in timing_fields:
                values = [row[field] for row in selected if row[field] is not None]
                pairing = ("NEAREST_HEADER_NO_FITTED_OFFSET" if field.startswith("nearest_header_pair_")
                           else "EXACT_ITOW" if field in ("header_delta_s", "sys_delta_s", "gps_delta_s")
                           else "A1_GNSS2_HEADER_INTERPOLATION_BRACKETS")
                source.append(dict(category="timing", sequence_id=sequence_id, scope=scope, quality=quality,
                                   timing_field=field, pairing=pairing, fitted_offset_used=False,
                                   expected_gps_week=STATUS_GPS_WEEK,
                                   total_epochs=len(selected), unmatched_count=len(selected) - len(values),
                                   **_statistics(values, "dimensionless" if field == "interpolation_weight" else "s", len(selected))))
    if sequence_id == "BY2O":
        # Explicit count rows include every E epoch, independent of delta/IMU
        # availability. These observed-vs-preregistered counts are report-only.
        expected_counts = {"evaluation_window": 58, "occlusion_primary": 42,
                           "occlusion_secondary": 13, "inside_union": 55, "outside": 3}
        window_float_count = sum(bool(keep) and row["raw_fixed_float_label"] == "float_involved"
                                 for row, keep in zip(epochs, scopes["evaluation_window"]))
        for scope, expected_count in expected_counts.items():
            selected = [row for row, keep in zip(epochs, scopes[scope]) if keep]
            count = sum(row["raw_fixed_float_label"] == "float_involved" for row in selected)
            source.append(dict(category="float_epoch_overlap", sequence_id=sequence_id, scope=scope,
                               quality="float_involved", count=count, n=count, total_a1_epochs=len(selected),
                               evaluation_window_float_count=window_float_count, expected_count=expected_count,
                               observed_equals_preregistered_expected=count == expected_count,
                               status="AVAILABLE_COUNT", report_only=True, decision_rule="NONE",
                               count_definition="A1_VALID_E_AND_PVT_FLOAT_INVOLVED_IN_CLOSED_REGION",
                               partition_definition="evaluation_window = occlusion_primary + occlusion_secondary + outside; inside_union = primary + secondary"))
    def json_ready(value):
        if isinstance(value, np.generic): return json_ready(value.item())
        if isinstance(value, float) and not math.isfinite(value): return None
        if isinstance(value, dict): return {key: json_ready(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)): return [json_ready(item) for item in value]
        return value
    return json_ready(dict(source_consistency_rows=source, per_epoch=epochs, histograms=histograms,
                           sigma_pairs=pairs, timing_rows=timing_rows))
