"""Input-only C-04b timing diagnostics; no diagnostic offset is applied."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from legsa_gins.datasets.by2.go2_body_state_parser import parse_go2_body_state_text

from .event_window import EventWindowError, _series, xcorr_gate_report
from .probes import open_probe_file, reject_forbidden_path

REPORT_FIRST_LINE = "DIAGNOSTIC ONLY — imu_gnss_time_offset stays 0.0"
IMU_HOLE_THRESHOLD_SECONDS = 0.1
GRID_HZ = 10.0
MAX_LAG_SECONDS = 5.0
LAG_STEP_SECONDS = 0.05
INTERPOLATION_GAP_MEDIAN_MULTIPLIER = 2.0
MIN_CORRELATION_PAIRS = 2


def diagnostic_constants():
    return {"imu_hole_threshold_seconds": IMU_HOLE_THRESHOLD_SECONDS,
            "hole_condition": "adjacent original source timestamps have dt >0.1 s; source row order is preserved",
            "missing_sample_count": "unavailable; no nominal-frequency missing count is inferred",
            "common_grid_hz": GRID_HZ, "grid_origin": "integer tenths of R1 seconds inside frozen common coverage",
            "lag_min_seconds": -MAX_LAG_SECONDS, "lag_max_seconds": MAX_LAG_SECONDS,
            "lag_step_seconds": LAG_STEP_SECONDS,
            "speed_inputs": "raw magnitudes sg=sqrt(vn^2+ve^2), sb=sqrt(vn^2+ve^2); no causal onset smoothing used for correlation",
            "resampling": "linear interpolation onto common 10 Hz grid; no extrapolation",
            "no_interpolation_gap_rule": "source bracket dt >2*median positive source dt produces unavailable samples, not zeros",
            "lag_interpolation": "linearly interpolate 10 Hz sb at grid_time+lag for 0.05 s lags; unavailable grid neighbors remain unavailable",
            "normalization": "overlap-only Pearson correlation after subtracting each overlap mean",
            "minimum_overlap_pairs": MIN_CORRELATION_PAIRS,
            "lag_sign": "positive lag means sb occurs later: corr(sg(t),sb(t+lag))",
            "peak_selection": "highest coefficient, then smallest absolute lag, then lower signed lag",
            "secondary_peak": "next distinct local maximum; contiguous equal-coefficient plateau is one maximum",
            "imu_gnss_time_offset": 0.0, "diagnostic_offset_applied": False}


def read_imu_increment_times(path):
    times = []
    with open_probe_file(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 7:
                raise EventWindowError(f"Increment IMU input requires seven columns at line {number}")
            values = [float(value) for value in fields]
            if not all(math.isfinite(value) for value in values):
                raise EventWindowError(f"Nonfinite increment IMU input at line {number}")
            times.append(values[0])
    return times


def read_raw_go2_times(path, *, base_time):
    """Read only when admitted by the caller's straced raw-read ledger.

    Nonfinite timestamps retain their row positions as None, with no sorting or
    duplicate removal. The diagnostic report records those source rows.
    """
    reject_forbidden_path(path)
    rows = parse_go2_body_state_text(path)
    result = []
    for row in rows:
        try:
            value = float(row.get("timestamp"))
        except (ValueError, TypeError):
            value = math.nan
        result.append(value-float(base_time) if math.isfinite(value) else None)
    return result


def summarize_time_holes(times, *, v2_window=None):
    values, invalid, nonpositive, holes = [], [], [], []
    for index, value in enumerate(times):
        try:
            value = float(value)
        except (ValueError, TypeError):
            value = math.nan
        if not math.isfinite(value):
            invalid.append(index)
            values.append(None)
        else:
            values.append(value)
    for index, (left, right) in enumerate(zip(values, values[1:])):
        if left is None or right is None:
            continue
        delta = right-left
        if delta <= 0:
            nonpositive.append({"left_row_index_zero_based": index,
                                "right_row_index_zero_based": index+1,
                                "t_start": left, "t_end": right, "dt_seconds": delta})
        if delta > IMU_HOLE_THRESHOLD_SECONDS:
            overlap = None if v2_window is None else max(0.0, min(right,float(v2_window["t_end"]))-max(left,float(v2_window["t_start"])))
            holes.append({"t_start": left, "t_end": right, "duration_seconds": delta,
                          "left_row_index_zero_based": index, "right_row_index_zero_based": index+1,
                          "bounding_sample_count": 2, "observed_samples_strictly_between": 0,
                          "inferred_missing_sample_count": None,
                          "overlaps_v2_window": None if overlap is None else overlap>0.0,
                          "overlap_seconds": overlap})
    valid = [value for value in values if value is not None]
    return {"source_row_count": len(values), "finite_timestamp_count": len(valid),
            "source_first_timestamp": next((value for value in values if value is not None),None),
            "source_last_timestamp": next((value for value in reversed(values) if value is not None),None),
            "invalid_timestamp_row_indices_zero_based": invalid, "nonpositive_intervals": nonpositive,
            "strictly_increasing_finite_source_times": not invalid and not nonpositive,
            "hole_count": len(holes), "holes": holes,
            "first_hole_end": holes[0]["t_end"] if holes else None,
            "v2_window_supplied": v2_window is not None, "source_rows_sorted_or_deleted": False}


def _interpolate(times, values, queries, maximum_gap):
    result = np.full(len(queries), np.nan, dtype=float)
    indexes = np.searchsorted(times, queries, side="left")
    for index, (query, right) in enumerate(zip(queries,indexes)):
        if right < len(times) and times[right] == query:
            result[index] = values[right]
        elif 0 < right < len(times):
            left = right-1
            width = times[right]-times[left]
            if width <= maximum_gap and np.isfinite(values[left]) and np.isfinite(values[right]):
                weight = (query-times[left])/width
                result[index] = values[left]+weight*(values[right]-values[left])
    return result


def normalized_speed_xcorr(*, gnss_times, gnss_speeds, body_times, body_speeds, common_coverage):
    gt, gs = _series(gnss_times, gnss_speeds, "GNSS correlation")
    bt, bs = _series(body_times, body_speeds, "Go2 HV correlation")
    if len(gt) < 2 or len(bt) < 2:
        raise EventWindowError("Correlation requires at least two timestamps from each provider")
    first, last = float(common_coverage["first"]), float(common_coverage["last"])
    if not math.isfinite(first) or not math.isfinite(last) or first>=last:
        raise EventWindowError("Correlation common coverage must be finite and ordered")
    grid = np.arange(math.ceil(first*GRID_HZ),math.floor(last*GRID_HZ)+1,dtype=float)/GRID_HZ
    gt,gs,bt,bs = (np.asarray(values,dtype=float) for values in (gt,gs,bt,bs))
    gdt,bdt = float(np.median(np.diff(gt))),float(np.median(np.diff(bt)))
    g = _interpolate(gt,gs,grid,INTERPOLATION_GAP_MEDIAN_MULTIPLIER*gdt)
    b = _interpolate(bt,bs,grid,INTERPOLATION_GAP_MEDIAN_MULTIPLIER*bdt)
    rows = []
    lag_count = int(round(MAX_LAG_SECONDS/LAG_STEP_SECONDS))
    for step in range(-lag_count,lag_count+1):
        lag = step*LAG_STEP_SECONDS
        # Original-source gaps are already unavailable on b. Grid interpolation
        # cannot cross an unavailable endpoint or extrapolate support.
        shifted = _interpolate(grid,b,grid+lag,2.0/GRID_HZ)
        available = np.isfinite(g)&np.isfinite(shifted)
        count = int(np.count_nonzero(available))
        coefficient, reason = None, None
        if count < MIN_CORRELATION_PAIRS:
            reason = "INSUFFICIENT_OVERLAP"
        else:
            left,right = g[available],shifted[available]
            left,right = left-left.mean(),right-right.mean()
            scale = float(np.linalg.norm(left)*np.linalg.norm(right))
            if scale == 0.0:
                reason = "ZERO_VARIANCE"
            else:
                coefficient = max(-1.0,min(1.0,float(np.dot(left,right)/scale)))
        rows.append({"lag_seconds": lag, "lag_ms": 1000.0*lag, "coefficient": coefficient,
                     "overlap_pair_count": count, "unavailable_reason": reason})
    available_rows = [row for row in rows if row["coefficient"] is not None]
    rank = lambda row: (-row["coefficient"],abs(row["lag_seconds"]),row["lag_seconds"])
    peak = min(available_rows,key=rank) if available_rows else None
    local_maxima = []
    i = 0
    while i < len(rows):
        value = rows[i]["coefficient"]
        if value is None:
            i += 1
            continue
        j = i
        while j+1 < len(rows) and rows[j+1]["coefficient"] == value:
            j += 1
        before = rows[i-1]["coefficient"] if i else None
        after = rows[j+1]["coefficient"] if j+1<len(rows) else None
        if (before is None or value>=before) and (after is None or value>=after):
            local_maxima.append(min(rows[i:j+1],key=rank))
        i = j+1
    secondary = [row for row in local_maxima if peak is not None and row["lag_seconds"] != peak["lag_seconds"]]
    return {"status": "AVAILABLE" if peak is not None else "UNAVAILABLE", "peak": peak,
            "secondary_peak": min(secondary,key=rank) if secondary else None,
            "secondary_peak_definition": "next distinct local maximum, not the next sample on the primary peak",
            "lag_profile": rows, "common_grid_sample_count": len(grid),
            "gnss_unavailable_grid_sample_count": int(np.count_nonzero(~np.isfinite(g))),
            "body_unavailable_grid_sample_count": int(np.count_nonzero(~np.isfinite(b))),
            "gnss_source_median_interval_seconds": gdt, "body_source_median_interval_seconds": bdt,
            "gnss_maximum_interpolation_bracket_seconds": INTERPOLATION_GAP_MEDIAN_MULTIPLIER*gdt,
            "body_maximum_interpolation_bracket_seconds": INTERPOLATION_GAP_MEDIAN_MULTIPLIER*bdt,
            "offset_applied": False, "imu_gnss_time_offset": 0.0}


def diagnose(*, dataset_id, imu_times, raw_body_times, gnss_times, gnss_speeds,
             body_times, body_speeds, common_coverage, v2_window=None, xcorr=None,
             event_report=None, by2_peak_lag_seconds=None):
    correlation = xcorr if xcorr is not None else normalized_speed_xcorr(
        gnss_times=gnss_times,gnss_speeds=gnss_speeds,body_times=body_times,
        body_speeds=body_speeds,common_coverage=common_coverage)
    result = {"schema_version": "paper_rebuild.clean5.alignment_diagnostics.v2",
            "first_line": REPORT_FIRST_LINE, "dataset_id": dataset_id, "diagnostic_only": True,
            "constants": diagnostic_constants(), "imu_gnss_time_offset": 0.0,
            "imu_increment_holes": summarize_time_holes(imu_times,v2_window=v2_window),
            "raw_go2_holes": summarize_time_holes(raw_body_times,v2_window=v2_window),
            "xcorr": correlation,
            "xcorr_gate": xcorr_gate_report(correlation,by2_peak_lag_seconds=by2_peak_lag_seconds),
            "v2_window": v2_window, "trace_content_read": False, "offset_selected_for_solver": False,
            "event_window_reselected_from_correlation": False}
    if event_report is not None:
        keys = ("onset_censored_b","onset_censored_g","body_onset_interval_R1","gnss_onset_interval_R1",
                "delta_t_onset_ms","delta_t_onset_interval_ms","clock_consistency_gate",
                "propagation_start_adjustment","preserve_internal_dropout","kick_dropout_hypothesis")
        result["event_timing"] = {key:event_report[key] for key in keys}
    return result


def markdown_report(report):
    lines = [REPORT_FIRST_LINE,"",f"Dataset: {report['dataset_id']}","",
             "Source row order is preserved. Missing sample counts are unavailable; no offset is applied.","",
             "| Source | Rows | dt > 0.1 s intervals | Nonpositive intervals | Invalid timestamps |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for key,label in (("imu_increment_holes","increment IMU"),("raw_go2_holes","raw Go2")):
        item = report[key]
        lines.append(f"| {label} | {item['source_row_count']} | {item['hole_count']} | {len(item['nonpositive_intervals'])} | {len(item['invalid_timestamp_row_indices_zero_based'])} |")
    lines += ["","| Source | Gap start s | Gap end s | Duration s | Bounding samples | V2 overlap |",
              "| --- | ---: | ---: | ---: | ---: | --- |"]
    for key,label in (("imu_increment_holes","increment IMU"),("raw_go2_holes","raw Go2")):
        for gap in report[key]["holes"]:
            overlap = "unavailable" if gap["overlaps_v2_window"] is None else str(gap["overlaps_v2_window"])
            lines.append(f"| {label} | {gap['t_start']:.12g} | {gap['t_end']:.12g} | {gap['duration_seconds']:.12g} | 2 | {overlap} |")
    lines += ["","| Correlation peak | Lag ms | Coefficient | Overlap pairs |","| --- | ---: | ---: | ---: |"]
    for key,label in (("peak","primary"),("secondary_peak","secondary local maximum")):
        item = report["xcorr"][key]
        lines.append(f"| {label} | unavailable | unavailable | unavailable |" if item is None else
                     f"| {label} | {item['lag_ms']:.12g} | {item['coefficient']:.12g} | {item['overlap_pair_count']} |")
    lines += ["","Positive lag means body speed occurs later: corr(sg(t), sb(t+lag)).",
              "Raw speed magnitudes are resampled at 10 Hz; lag step is 0.05 s over [-5, 5] s.",
              "Interpolation never extrapolates or crosses a source bracket greater than twice that source's median interval.",
              "No clock correction or solver-input modification is inferred from these diagnostics.",""]
    gate = report["xcorr_gate"]
    lines += [f"Primary |lag| <= 1 s diagnostic gate: {gate['passed']}; available: {gate['available']}.",
              f"Primary lag difference from BY2 (report only): {gate['difference_from_by2_primary_lag_seconds']} s.",""]
    timing = report.get("event_timing")
    if timing is not None:
        lines += [f"Onset censored: GNSS={timing['onset_censored_g']}, raw Go2={timing['onset_censored_b']}.",
                  f"GNSS onset interval R1: {timing['gnss_onset_interval_R1']}; body onset interval R1: {timing['body_onset_interval_R1']}."]
        if timing["onset_censored_g"] or timing["onset_censored_b"]:
            lines += [f"Onset difference interval only (ms): {timing['delta_t_onset_interval_ms']}."]
        else:
            lines += [f"Uncensored onset difference (ms): {timing['delta_t_onset_ms']}."]
        selected = timing["clock_consistency_gate"]
        shift = timing["propagation_start_adjustment"]
        lines += [f"Clock consistency gate: {selected['basis']}; passed={selected['passed']}.",
                  f"Propagation start: original={shift['unadjusted_start']}; t_init={shift['first_imu_time_at_or_after_start']}; "
                  f"delay={shift['initialization_delay_seconds']} s; adjusted={shift['adjusted']}; final={shift['adjusted_start']}.",
                  f"Internal dropout intervals preserved: {len(timing['preserve_internal_dropout'])}."]
        if timing["kick_dropout_hypothesis"] is not None:
            lines += ["HYPOTHESIS ONLY: "+timing["kick_dropout_hypothesis"]["statement"]]
        lines += [""]
    return "\n".join(lines)
