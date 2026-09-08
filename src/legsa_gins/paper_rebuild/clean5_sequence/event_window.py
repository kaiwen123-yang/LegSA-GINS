"""C-04b preregistered input-event window; no trace, solver, or offset fitting.

All thresholds below are fixed before observing any C-04b input calculations.
Provider velocities are observations/weak priors, never reference truth.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import csv
from dataclasses import asdict
from decimal import Decimal
import math
from statistics import median
from pathlib import Path
from typing import Mapping, Sequence

from .. import kick_alignment
from ..manifest import sha256_file
from .probes import open_probe_file, reject_forbidden_path

HUMAN_STATEMENT = "无 PTP 跨设备对时；启动时蹬一脚；算法起点 = 蹬脚后 GNSS 与机身 IMU 同时出现运动的时刻；结束 = 去掉末尾若干秒。"
SPEED_THRESHOLD_MPS = 0.15
GNSS_CONSECUTIVE_EPOCHS = 3
BODY_MEAN_WINDOW_SECONDS = 1.0
BODY_PERSISTENCE_SECONDS = 3.0
MAX_ONSET_DIFFERENCE_SECONDS = 1.0
TAIL_MARGIN_SECONDS = 9
BY2_CONTROL_KICK_SECONDS = 62.579067
BY2_CONTROL_START_SECONDS = 66.0
BY2_CONTROL_START_TOLERANCE_SECONDS = 3.0
BY2_CONTROL_END_SECONDS = 340.0
RAW_BODY_HOLE_SECONDS = 0.1
GNSS_HOLE_MEDIAN_MULTIPLIER = 2.0
ONSET_CENSOR_LOOKBACK_SECONDS = 3.0
MAX_XCORR_PEAK_LAG_SECONDS = 1.0
MAX_PROPAGATION_INITIALIZATION_DELAY_SECONDS = 1.0
BY2O_POST_KICK_BOUND_SECONDS = 3154.351049
FIXED_IMU_GNSS_TIME_OFFSET = 0.0
OCCLUSION_INTERVALS = ((3369.943066596985, 3411.951585292816),
                       (3495.939144849777, 3508.9415624141693))
GNSS_NUMERIC_COLUMNS = 15
GNSS_TIME_COLUMN = 0
GNSS_VN_COLUMN = 7
GNSS_VE_COLUMN = 8
HV_AUXILIARY_REBASE_OFFSETS = {"BY2":28800.0,"BY2H":28800.0,"BY2O":25200.0}


class EventWindowError(RuntimeError):
    """An input schema or fixed event definition cannot be applied."""


def constants():
    return {"speed_threshold_mps": SPEED_THRESHOLD_MPS, "gnss_consecutive_epochs": GNSS_CONSECUTIVE_EPOCHS,
            "body_mean_window_seconds": BODY_MEAN_WINDOW_SECONDS,
            "body_mean_definition": "sample arithmetic mean of all frozen HV speeds in (t-1,t]; provider must supply a full 1 s history",
            "body_mean_warmup_definition": "first provider timestamp <= t-1; no zero padding or future samples",
            "body_persistence_seconds": BODY_PERSISTENCE_SECONDS,
            "body_persistence_definition": "consecutive observed above-threshold causal means spanning >=3 s; onset is the first sample, confirmed by the later sample",
            "gap_policy": "onset selection unchanged; source holes censor onset timing; internal dropout remains in the window; no artificial samples inserted",
            "candidate_epoch_scope": "closed frozen three-stream common coverage, strictly after kick if DETECTED",
            "max_onset_difference_seconds": MAX_ONSET_DIFFERENCE_SECONDS,
            "onset_difference_definition": "uncensored: t_on_g-t_on_b in ms; if either onset is censored, only [g_low-b_high,g_high-b_low] in ms; no offset applied",
            "onset_censoring": {"raw_body_hole_dt_greater_than_seconds": RAW_BODY_HOLE_SECONDS,
                "gnss_hole_dt_greater_than_median_multiplier": GNSS_HOLE_MEDIAN_MULTIPLIER,
                "lookback_seconds": ONSET_CENSOR_LOOKBACK_SECONDS,
                "trigger": "observed onset is the first sample after a hole, or a hole intersects the closed [onset-3,onset] lookback; hole left endpoint must precede onset",
                "interval": "earliest triggering hole left endpoint through observed onset; uncensored onset is a point interval",
                "raw_to_hv_sample_identity": "replay UTC-relative float str, Decimal auxiliary offset subtraction and .12f from clean1r2r1_formal.rebase_auxiliary_time_csv; exact encoded equality, no time tolerance",
                "clock_gate": "either censored: full-common-coverage xcorr primary abs(lag)<=1 s and available; neither censored: abs(point delta)<=1 s; xcorr still reported"},
            "xcorr_primary_maximum_absolute_lag_seconds": MAX_XCORR_PEAK_LAG_SECONDS,
            "propagation_initialization": {"time": "first original frozen propagation IMU timestamp >= floor(max(onsets))",
                "adjust_when_delay_strictly_greater_than_seconds": MAX_PROPAGATION_INITIALIZATION_DELAY_SECONDS,
                "adjusted_start": "floor(t_init); no samples inserted or removed"},
            "start_formula": "floor(max(t_on_g,t_on_b))", "end_formula": "floor(last_common_epoch)-9",
            "tail_margin_seconds": TAIL_MARGIN_SECONDS, "imu_gnss_time_offset": FIXED_IMU_GNSS_TIME_OFFSET,
            "by2_control": {"kick_time_lower_bound": BY2_CONTROL_KICK_SECONDS,
                            "start_reference": BY2_CONTROL_START_SECONDS,
                            "required_start": BY2_CONTROL_START_SECONDS,
                            "required_end": BY2_CONTROL_END_SECONDS},
            "by2o_start_strictly_after_seconds": BY2O_POST_KICK_BOUND_SECONDS,
            "kick": {"zscore_threshold": 6.0, "normalization_baseline_max_samples": 1000,
                     "robust_mad_scale": 1.4826, "numerical_scale_floor": 1e-12,
                     "segment": "initial segment before first mode/gait change",
                     "detector": "kick_alignment.detect_frozen_go2_kick unchanged",
                     "not_detected_policy": "report only; no replacement event, threshold change, or retry"}}


def _series(times, speeds, role):
    if len(times) != len(speeds) or len(times) == 0:
        raise EventWindowError(f"{role}: empty or unequal time/speed arrays")
    t, s = [float(value) for value in times], [float(value) for value in speeds]
    if any(not math.isfinite(value) for value in t + s) or any(value < 0 for value in s):
        raise EventWindowError(f"{role}: nonfinite time/speed or negative speed")
    if any(right <= left for left, right in zip(t, t[1:])):
        raise EventWindowError(f"{role}: provider times must be strictly increasing")
    return t, s


def load_speed_inputs(gnss_provider_path, hv_provider_path):
    """Read only frozen 15-column GNSS and named-column Go2 HV observations.

    GNSS indices are the maintained process_data_compat.GNSS_COLUMNS schema:
    time=0, vn=7, ve=8 (zero-based). No raw source is reconstructed here.
    """
    gt, gs, bt, bs = [], [], [], []
    with open_probe_file(gnss_provider_path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            values = [float(value) for value in line.split()]
            if len(values) != GNSS_NUMERIC_COLUMNS or not all(math.isfinite(value) for value in values):
                raise EventWindowError(f"Frozen GNSS input must have 15 finite columns at line {number}")
            gt.append(values[GNSS_TIME_COLUMN])
            gs.append(math.hypot(values[GNSS_VN_COLUMN], values[GNSS_VE_COLUMN]))
    with open_probe_file(hv_provider_path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"time", "vn", "ve"}.issubset(reader.fieldnames or []):
            raise EventWindowError("Frozen Go2 HV input lacks time/vn/ve")
        for row in reader:
            bt.append(float(row["time"]))
            bs.append(math.hypot(float(row["vn"]), float(row["ve"])))
    _series(gt, gs, "GNSS")
    _series(bt, bs, "Go2 HV")
    return {"gnss_times": gt, "gnss_speeds": gs, "body_times": bt, "body_speeds": bs,
            "source_row_counts": {"gnss": len(gt), "body": len(bt)},
            "input_roles": {"gnss": "frozen GNSS1 receiver-velocity observation, 15-column provider",
                            "body": "frozen Go2 horizontal-velocity weak prior; not truth"},
            "velocity_columns": {"gnss_zero_based": {"time": 0, "vn": 7, "ve": 8},
                                 "body_named": ["time", "vn", "ve"]}}


def detect_kick_report(raw_go2_path, *, base_time, diagnostic_dir):
    """Call the unchanged detector exactly once, retaining a failed detection.

    The caller admits the raw source and confines this operation under strace.
    Only a new attempt-owned maintained-candidate CSV can be written here.
    """
    reject_forbidden_path(raw_go2_path)
    out = Path(diagnostic_dir)
    if out.is_symlink() or any(parent.is_symlink() for parent in out.parents):
        raise EventWindowError("Kick diagnostic destination must not have symlink ancestors")
    candidate = out / "GO2_INITIAL_EVENT_SEGMENT_C04B.csv"
    if candidate.exists() or candidate.is_symlink():
        raise FileExistsError("Kick candidate output already exists; no overwrite or detector retry")
    fixed = (kick_alignment.MAINTAINED_DEFAULT_ZSCORE_THRESHOLD,
             kick_alignment.NORMALIZATION_BASELINE_MAX_SAMPLES, kick_alignment.ROBUST_MAD_SCALE,
             kick_alignment.NUMERICAL_SCALE_FLOOR)
    if fixed != (6.0, 1000, 1.4826, 1e-12):
        raise EventWindowError("Frozen kick-detector constants drifted")
    report = {"status": "NOT_DETECTED", "kick_time_R1": None, "kick_time_absolute": None,
              "report_only": True, "retry_count": 0, "constants": constants()["kick"],
              "detector_source_sha256": sha256_file(kick_alignment.__file__),
              "maintained_candidate_path": None, "diagnostic_rows": [],
              "base_time": float(base_time), "trace_used_for_alignment": False,
              "offset_applied_seconds": FIXED_IMU_GNSS_TIME_OFFSET}
    try:
        detection = kick_alignment.detect_frozen_go2_kick(raw_go2_path,
                            maintained_candidate_output_path=candidate)
        values = asdict(detection)
        report.update(status="DETECTED", kick_time_R1=detection.t_go2_kick-float(base_time),
                      kick_time_absolute=detection.t_go2_kick,
                      diagnostic_rows=values.pop("diagnostics"), detector_result=values)
    except kick_alignment.KickAlignmentError as exc:
        report.update(error_class=type(exc).__name__, error_message=str(exc))
        # Preserve already-computed scalar intermediates; never rerun or select
        # a failed robust/maintained candidate as the physical kick.
        allowed = ("change_index", "change_time", "selected_index", "score", "acc_median", "acc_mad",
                   "acc_scale", "gyro_median", "gyro_mad", "gyro_scale", "maintained_time",
                   "maintained_score", "maintained_status")
        tb = exc.__traceback__
        while tb:
            if tb.tb_frame.f_code is kick_alignment.detect_frozen_go2_kick.__code__:
                local = tb.tb_frame.f_locals
                report["detector_intermediates_at_failure"] = {key: local[key] for key in allowed if key in local}
                report["event_segment_row_count"] = len(local.get("event_rows", []))
                report["normalization_sample_count"] = len(local.get("baseline", []))
            tb = tb.tb_next
    if candidate.is_file():
        report["maintained_candidate_path"] = str(candidate)
        report["maintained_candidate_sha256"] = sha256_file(candidate)
    return report


def causal_body_means(times, speeds):
    t, s = _series(times, speeds, "Go2 HV")
    means, counts = [], []
    for index, timestamp in enumerate(t):
        left = bisect_right(t, timestamp-BODY_MEAN_WINDOW_SECONDS, 0, index+1)
        count = index+1-left
        supported = t[0] <= timestamp-BODY_MEAN_WINDOW_SECONDS and count > 0
        means.append(math.fsum(s[left:index+1])/count if supported else None)
        counts.append(count if supported else 0)
    return means, counts


def _eligible(timestamp, first, last, kick):
    return first <= timestamp <= last and (kick is None or timestamp > kick)


def _gnss_onset(times, speeds, first, last, kick):
    active = []
    eligible_count = 0
    for index, (timestamp, speed) in enumerate(zip(times, speeds)):
        if not _eligible(timestamp, first, last, kick):
            active = []
            continue
        eligible_count += 1
        active = active + [index] if speed >= SPEED_THRESHOLD_MPS else []
        if len(active) == GNSS_CONSECUTIVE_EPOCHS:
            return {"status": "DETECTED", "onset": times[active[0]], "confirmed_at": timestamp,
                    "provider_row_indices_zero_based": active, "speeds_mps": [speeds[i] for i in active],
                    "epochs_scanned_to_confirmation": eligible_count}
    return {"status": "NOT_DETECTED", "onset": None, "eligible_epoch_count": eligible_count}


def _body_onset(times, speeds, first, last, kick):
    means, counts = causal_body_means(times, speeds)
    start = None
    eligible_count = 0
    for index, (timestamp, mean) in enumerate(zip(times, means)):
        if not _eligible(timestamp, first, last, kick) or mean is None or mean < SPEED_THRESHOLD_MPS:
            start = None
            continue
        eligible_count += 1
        if start is None:
            start = index
        if timestamp-times[start] >= BODY_PERSISTENCE_SECONDS:
            return {"status": "DETECTED", "onset": times[start], "confirmed_at": timestamp,
                    "observed_duration_seconds": timestamp-times[start], "observed_sample_count": index-start+1,
                    "onset_row_index_zero_based": start, "confirmation_row_index_zero_based": index,
                    "onset_causal_mean_mps": means[start], "confirmation_causal_mean_mps": mean,
                    "onset_mean_sample_count": counts[start], "confirmation_mean_sample_count": counts[index],
                    "maximum_adjacent_interval_in_confirmation_seconds": max(times[j]-times[j-1] for j in range(start+1,index+1)),
                    "epochs_scanned_above_threshold_to_confirmation": eligible_count}
    return {"status": "NOT_DETECTED", "onset": None, "above_threshold_eligible_epoch_count": eligible_count}


def _timestamp_series(values, role):
    try:
        times = [float(value) for value in values]
    except (ValueError, TypeError) as exc:
        raise EventWindowError(f"{role}: invalid original timestamp") from exc
    if not times or any(not math.isfinite(value) for value in times):
        raise EventWindowError(f"{role}: empty or nonfinite original timestamps")
    if any(right <= left for left,right in zip(times,times[1:])):
        raise EventWindowError(f"{role}: original timestamps must be strictly increasing")
    return times


def _source_holes(times, threshold):
    return [{"t_start":left,"t_end":right,"duration_seconds":right-left,
             "left_row_index_zero_based":index,"right_row_index_zero_based":index+1}
            for index,(left,right) in enumerate(zip(times,times[1:])) if right-left>threshold]


def _encoded_hv_time(raw_r1_time, auxiliary_offset_seconds):
    """Replay the frozen CSV clock encoding, rather than relax time gates.

    providers._go2_priors subtracts UTC midnight and _write_csv stringifies the
    float. clean1r2r1_formal.rebase_auxiliary_time_csv then subtracts the exact
    auxiliary offset in Decimal and writes twelve decimal places. Reconstructing
    that encoding from an original R1 timestamp preserves sample identity.
    """
    utc_relative = raw_r1_time+auxiliary_offset_seconds
    rebased = Decimal(str(utc_relative))-Decimal(str(auxiliary_offset_seconds))
    return float(f"{rebased:.12f}")


def onset_censoring(times, onset, *, gap_threshold_seconds, source, hv_auxiliary_offset_seconds=None):
    """Describe an observed onset interval without estimating missing samples."""
    holes = _source_holes(times,gap_threshold_seconds)
    relevant = [] if onset is None else [hole for hole in holes
        if hole["t_start"]<onset and hole["t_end"]>=onset-ONSET_CENSOR_LOOKBACK_SECONDS]
    # Restrict to holes already started at the observed onset. The complete
    # left endpoint is retained even when it lies before the lookback boundary.
    interval = None if onset is None else [min([onset]+[hole["t_start"] for hole in relevant]),onset]
    first_after = onset is not None and any(
        (hole["t_end"] if hv_auxiliary_offset_seconds is None else
         _encoded_hv_time(hole["t_end"],hv_auxiliary_offset_seconds))==onset for hole in holes)
    return {"source":source,"observed_onset":onset,"censored":bool(relevant),
            "onset_interval_R1":interval,"gap_threshold_seconds":gap_threshold_seconds,
            "lookback_interval_R1":None if onset is None else [onset-ONSET_CENSOR_LOOKBACK_SECONDS,onset],
            "first_sample_after_hole":first_after,
            "sample_identity_comparison":"exact original timestamp" if hv_auxiliary_offset_seconds is None else "exact frozen HV encoded timestamp",
            "hv_auxiliary_rebase_offset_seconds":hv_auxiliary_offset_seconds,
            "triggering_holes":relevant,"source_holes":holes,"missing_samples_reconstructed":False}


def xcorr_gate_report(xcorr, *, by2_peak_lag_seconds=None):
    peak = xcorr.get("peak") if isinstance(xcorr,Mapping) else None
    lag = peak.get("lag_seconds") if isinstance(peak,Mapping) else None
    available = (isinstance(xcorr,Mapping) and xcorr.get("status")=="AVAILABLE"
                 and isinstance(lag,(int,float)) and not isinstance(lag,bool) and math.isfinite(lag))
    reference = by2_peak_lag_seconds
    if reference is not None and (not isinstance(reference,(int,float)) or not math.isfinite(reference)):
        raise EventWindowError("BY2 diagnostic primary lag reference is nonfinite")
    return {"available":available,"passed":bool(available and abs(lag)<=MAX_XCORR_PEAK_LAG_SECONDS),
            "primary_lag_seconds":lag if available else None,
            "maximum_absolute_lag_seconds":MAX_XCORR_PEAK_LAG_SECONDS,
            "lag_sign":"corr(sg(t), sb(t+lag)); positive means body speed occurs later",
            "by2_primary_lag_seconds":reference,
            "difference_from_by2_primary_lag_seconds":None if not available or reference is None else lag-reference,
            "by2_difference_report_only":True,"offset_applied_seconds":0.0}


def compute_event_window(*, dataset_id, gnss_times, gnss_speeds, body_times, body_speeds,
                         common_coverage, kick_report, v1_window, raw_body_times, imu_times,
                         xcorr, by2_peak_lag_seconds=None, first_imu_hole_end=None,
                         occlusion_window=None):
    gt, gs = _series(gnss_times, gnss_speeds, "GNSS")
    bt, bs = _series(body_times, body_speeds, "Go2 HV")
    raw_times = _timestamp_series(raw_body_times,"Raw Go2 censoring")
    propagation_times = _timestamp_series(imu_times,"Propagation IMU initialization")
    if dataset_id not in {"BY2", "BY2H", "BY2O"}:
        raise EventWindowError("Unknown CLEAN5 sequence")
    first, last = float(common_coverage["first"]), float(common_coverage["last"])
    if not math.isfinite(first) or not math.isfinite(last) or first >= last:
        raise EventWindowError("Frozen three-stream common coverage is not finite and ordered")
    if kick_report.get("status") not in {"DETECTED", "NOT_DETECTED"}:
        raise EventWindowError("Kick status must be DETECTED or explicit NOT_DETECTED")
    kick = kick_report.get("kick_time_R1") if kick_report["status"] == "DETECTED" else None
    if kick is not None and not math.isfinite(float(kick)):
        raise EventWindowError("Detected kick must have a finite R1 timestamp")
    if kick_report["status"] == "DETECTED" and kick is None:
        raise EventWindowError("Detected kick lacks its R1 timestamp")
    kick = None if kick is None else float(kick)
    gnss = _gnss_onset(gt, gs, first, last, kick)
    body = _body_onset(bt, bs, first, last, kick)
    tg, tb = gnss["onset"], body["onset"]
    gdt = median(right-left for left,right in zip(gt,gt[1:])) if len(gt)>1 else None
    if gdt is None:
        raise EventWindowError("GNSS censoring requires at least two original provider epochs")
    censor_g = onset_censoring(gt,tg,gap_threshold_seconds=GNSS_HOLE_MEDIAN_MULTIPLIER*gdt,source="frozen GNSS15")
    censor_b = onset_censoring(raw_times,tb,gap_threshold_seconds=RAW_BODY_HOLE_SECONDS,source="original raw Go2",
                              hv_auxiliary_offset_seconds=HV_AUXILIARY_REBASE_OFFSETS[dataset_id])
    censored = censor_g["censored"] or censor_b["censored"]
    delta_interval = None if tg is None or tb is None else [
        1000.0*(censor_g["onset_interval_R1"][0]-censor_b["onset_interval_R1"][1]),
        1000.0*(censor_g["onset_interval_R1"][1]-censor_b["onset_interval_R1"][0])]
    xcorr_gate = xcorr_gate_report(xcorr,by2_peak_lag_seconds=by2_peak_lag_seconds)
    end = float(math.floor(last)-TAIL_MARGIN_SECONDS)
    start = None if tg is None or tb is None else float(math.floor(max(tg, tb)))
    unadjusted_start = start
    init_index = None if start is None else bisect_left(propagation_times,start)
    t_init = None if init_index is None or init_index==len(propagation_times) else propagation_times[init_index]
    delay = None if start is None or t_init is None else t_init-start
    adjusted = delay is not None and delay>MAX_PROPAGATION_INITIALIZATION_DELAY_SECONDS
    if adjusted:
        start = float(math.floor(t_init))
    adjustment = {"unadjusted_start":unadjusted_start,"first_imu_time_at_or_after_start":t_init,
                  "initialization_delay_seconds":delay,"delay_limit_seconds":MAX_PROPAGATION_INITIALIZATION_DELAY_SECONDS,
                  "adjusted":adjusted,"adjusted_start":start,"rule":"delay >1 s => floor(t_init)",
                  "original_imu_row_index_zero_based":init_index if t_init is not None else None}
    delta = None if tg is None or tb is None or censored else tg-tb
    candidate = None if start is None else {"t_start": start, "t_end": end}
    failures = []
    status = "PASS_EVENT_WINDOW_V2"
    if tg is None or tb is None:
        failures.append("Motion onset not detected under the preregistered definition")
        status = "EVENT_WINDOW_NOT_DETECTED"
    elif censored and not xcorr_gate["passed"]:
        failures.append("Censored onset requires available full-coverage xcorr primary abs(lag)<=1.0 s")
        status = "CLOCK_OFFSET_SUSPECTED"
    elif not censored and abs(delta)>MAX_ONSET_DIFFERENCE_SECONDS:
        failures.append("Uncensored abs(t_on_g-t_on_b) exceeds 1.0 s; no v2 contract may be written")
        status = "CLOCK_OFFSET_SUSPECTED"
    clock_gate = {"basis":"full_coverage_xcorr" if censored else "uncensored_onset_point_difference",
                  "passed":tg is not None and tb is not None and (xcorr_gate["passed"] if censored else abs(delta)<=MAX_ONSET_DIFFERENCE_SECONDS),
                  "xcorr_used_as_hard_gate":censored,"delta_interval_is_not_point_offset":censored,
                  "offset_applied_seconds":0.0}
    if candidate is not None:
        if t_init is None:
            failures.append("No original propagation IMU sample exists at or after candidate start")
        if start >= end:
            failures.append("Event window is empty or reversed")
        if dataset_id == "BY2":
            if not (start > BY2_CONTROL_KICK_SECONDS
                    and start == BY2_CONTROL_START_SECONDS
                    and end == BY2_CONTROL_END_SECONDS):
                failures.append("BY2 frozen control window gate failed; thresholds remain unchanged")
                if status == "PASS_EVENT_WINDOW_V2":
                    status = "CONTROL_GATE_FAILED"
        elif kick is not None and start <= kick:
            failures.append("Floored window start is not strictly after the detected kick")
        if dataset_id=="BY2O" and start<=BY2O_POST_KICK_BOUND_SECONDS:
            failures.append("BY2O final start must be strictly after 3154.351049 s")
    occlusion = None
    if dataset_id == "BY2O":
        if not isinstance(occlusion_window, Mapping):
            failures.append("Preregistered BY2O occlusion metadata is required")
        else:
            main = occlusion_window["main_window"]
            intervals = [(float(main["t0"]), float(main["t1"]))] + [
                (float(item["t0"]), float(item["t1"])) for item in occlusion_window["secondary_runs"]]
            exact = tuple(intervals) == OCCLUSION_INTERVALS
            contained = candidate is not None and all(start <= a <= b <= end for a,b in intervals)
            occlusion = {"intervals": [[a,b] for a,b in intervals], "matches_preregistered_intervals": exact,
                         "wholly_within_v2_window": contained,
                         "before_main_seconds": None if start is None else intervals[0][0]-start,
                         "after_main_seconds": end-intervals[0][1],
                         "secondary_before_after_seconds": [{"before": None if start is None else a-start,
                                                              "after": end-b} for a,b in intervals[1:]]}
            if not exact or not contained:
                failures.append("BY2O preregistered main/secondary intervals are not unchanged and wholly retained")
    if failures and status == "PASS_EVENT_WINDOW_V2":
        status = "WINDOW_GATE_FAILED"
    passed = not failures
    raw_holes = _source_holes(raw_times,RAW_BODY_HOLE_SECONDS)
    propagation_holes = _source_holes(propagation_times,RAW_BODY_HOLE_SECONDS)
    preserved = []
    for source,holes in (("raw_go2",raw_holes),("propagation_imu",propagation_holes),("gnss",censor_g["source_holes"])):
        for hole in holes:
            overlap = None if candidate is None else max(0.0,min(end,hole["t_end"])-max(start,hole["t_start"]))
            if overlap is not None and overlap>0:
                preserved.append({"source":source,**hole,"overlap_seconds":overlap,"preserved_without_interpolation_or_deletion":True})
    hypothesis = None
    if dataset_id=="BY2H" and kick is None:
        first_raw_hole = raw_holes[0] if raw_holes else None
        hypothesis = {"status":"HYPOTHESIS_ONLY","kick_status":"NOT_DETECTED","first_raw_go2_hole":first_raw_hole,
            "statement":"The kick may have occurred during the first raw Go2 dropout; this is not a detected kick or clock-offset estimate.",
            "kick_time_assigned":False,"used_to_select_window":False,
            "body_onset_after_first_hole_end":None if tb is None or first_raw_hole is None else tb>=first_raw_hole["t_end"]}
    comparison = {"diagnostic_only": True, "first_imu_hole_end": first_imu_hole_end,
                  "candidate_start": start, "used_to_select_window": False,
                  "candidate_start_minus_hole_end_seconds": None if start is None or first_imu_hole_end is None else start-float(first_imu_hole_end),
                  "candidate_start_at_or_after_hole_end": None if start is None or first_imu_hole_end is None else start>=float(first_imu_hole_end)}
    return {"schema_version": "paper_rebuild.clean5.event_window_v2.v2", "dataset_id": dataset_id,
            "status": status, "ready_for_v2_contract": passed, "failures": failures,
            "human_statement": HUMAN_STATEMENT, "constants": constants(), "kick": dict(kick_report),
            "t_on_g": tg, "t_on_b": tb, "delta_t_onset_ms": None if delta is None else 1000.0*delta,
            "onset_censored_g":censor_g["censored"],"onset_censored_b":censor_b["censored"],
            "censor_g":censor_g,"censor_b":censor_b,
            "gnss_onset_interval_R1":censor_g["onset_interval_R1"],"body_onset_interval_R1":censor_b["onset_interval_R1"],
            "delta_t_onset_interval_ms":delta_interval,"clock_consistency_gate":clock_gate,"xcorr_gate":xcorr_gate,
            "propagation_start_adjustment":adjustment,"adjusted_for_imu_dropout":adjusted,
            "preserve_internal_dropout":preserved,
            "kick_dropout_hypothesis":hypothesis,
            "gnss_onset": gnss, "body_onset": body, "common_coverage": dict(common_coverage),
            "v1_window": dict(v1_window), "v2_window": candidate if passed else None,
            "candidate_v2_window": candidate, "first_imu_hole_end_comparison": comparison,
            "occlusion_preservation": occlusion, "trace_content_read": False, "solver_execution_count": 0,
            "evaluator_execution_count": 0, "offset_search_or_application": False,
            "imu_gnss_time_offset": FIXED_IMU_GNSS_TIME_OFFSET}
