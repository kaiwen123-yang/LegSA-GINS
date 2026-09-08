"""C-04b preregistered input-event window; no trace, solver, or offset fitting.

All thresholds below are fixed before observing any C-04b input calculations.
Provider velocities are observations/weak priors, never reference truth.
"""
from __future__ import annotations

from bisect import bisect_right
import csv
from dataclasses import asdict
import math
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
FIXED_IMU_GNSS_TIME_OFFSET = 0.0
OCCLUSION_INTERVALS = ((3369.943066596985, 3411.951585292816),
                       (3495.939144849777, 3508.9415624141693))
GNSS_NUMERIC_COLUMNS = 15
GNSS_TIME_COLUMN = 0
GNSS_VN_COLUMN = 7
GNSS_VE_COLUMN = 8


class EventWindowError(RuntimeError):
    """An input schema or fixed event definition cannot be applied."""


def constants():
    return {"speed_threshold_mps": SPEED_THRESHOLD_MPS, "gnss_consecutive_epochs": GNSS_CONSECUTIVE_EPOCHS,
            "body_mean_window_seconds": BODY_MEAN_WINDOW_SECONDS,
            "body_mean_definition": "sample arithmetic mean of all frozen HV speeds in (t-1,t]; provider must supply a full 1 s history",
            "body_mean_warmup_definition": "first provider timestamp <= t-1; no zero padding or future samples",
            "body_persistence_seconds": BODY_PERSISTENCE_SECONDS,
            "body_persistence_definition": "consecutive observed above-threshold causal means spanning >=3 s; onset is the first sample, confirmed by the later sample",
            "gap_policy": "no additional event-selection gap veto; holes are diagnostic only; no artificial samples inserted",
            "candidate_epoch_scope": "closed frozen three-stream common coverage, strictly after kick if DETECTED",
            "max_onset_difference_seconds": MAX_ONSET_DIFFERENCE_SECONDS,
            "onset_difference_definition": "t_on_g-t_on_b, reported in ms; no offset applied",
            "start_formula": "floor(max(t_on_g,t_on_b))", "end_formula": "floor(last_common_epoch)-9",
            "tail_margin_seconds": TAIL_MARGIN_SECONDS, "imu_gnss_time_offset": FIXED_IMU_GNSS_TIME_OFFSET,
            "by2_control": {"kick_time_lower_bound": BY2_CONTROL_KICK_SECONDS,
                            "start_reference": BY2_CONTROL_START_SECONDS,
                            "start_absolute_tolerance": BY2_CONTROL_START_TOLERANCE_SECONDS,
                            "required_end": BY2_CONTROL_END_SECONDS},
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


def compute_event_window(*, dataset_id, gnss_times, gnss_speeds, body_times, body_speeds,
                         common_coverage, kick_report, v1_window, first_imu_hole_end=None,
                         occlusion_window=None):
    gt, gs = _series(gnss_times, gnss_speeds, "GNSS")
    bt, bs = _series(body_times, body_speeds, "Go2 HV")
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
    end = float(math.floor(last)-TAIL_MARGIN_SECONDS)
    start = None if tg is None or tb is None else float(math.floor(max(tg, tb)))
    delta = None if tg is None or tb is None else tg-tb
    candidate = None if start is None else {"t_start": start, "t_end": end}
    failures = []
    status = "PASS_EVENT_WINDOW_V2"
    if tg is None or tb is None:
        failures.append("Motion onset not detected under the preregistered definition")
        status = "EVENT_WINDOW_NOT_DETECTED"
    elif abs(delta) > MAX_ONSET_DIFFERENCE_SECONDS:
        failures.append("abs(t_on_g-t_on_b) exceeds 1.0 s; no v2 contract may be written")
        status = "CLOCK_OFFSET_SUSPECTED"
    if candidate is not None:
        if start >= end:
            failures.append("Event window is empty or reversed")
        if dataset_id == "BY2":
            if not (start > BY2_CONTROL_KICK_SECONDS
                    and abs(start-BY2_CONTROL_START_SECONDS) <= BY2_CONTROL_START_TOLERANCE_SECONDS
                    and end == BY2_CONTROL_END_SECONDS):
                failures.append("BY2 frozen control window gate failed; thresholds remain unchanged")
                if status == "PASS_EVENT_WINDOW_V2":
                    status = "CONTROL_GATE_FAILED"
        elif kick is not None and start <= kick:
            failures.append("Floored window start is not strictly after the detected kick")
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
    comparison = {"diagnostic_only": True, "first_imu_hole_end": first_imu_hole_end,
                  "candidate_start": start, "used_to_select_window": False,
                  "candidate_start_minus_hole_end_seconds": None if start is None or first_imu_hole_end is None else start-float(first_imu_hole_end),
                  "candidate_start_at_or_after_hole_end": None if start is None or first_imu_hole_end is None else start>=float(first_imu_hole_end)}
    return {"schema_version": "paper_rebuild.clean5.event_window_v2.v1", "dataset_id": dataset_id,
            "status": status, "ready_for_v2_contract": passed, "failures": failures,
            "human_statement": HUMAN_STATEMENT, "constants": constants(), "kick": dict(kick_report),
            "t_on_g": tg, "t_on_b": tb, "delta_t_onset_ms": None if delta is None else 1000.0*delta,
            "gnss_onset": gnss, "body_onset": body, "common_coverage": dict(common_coverage),
            "v1_window": dict(v1_window), "v2_window": candidate if passed else None,
            "candidate_v2_window": candidate, "first_imu_hole_end_comparison": comparison,
            "occlusion_preservation": occlusion, "trace_content_read": False, "solver_execution_count": 0,
            "evaluator_execution_count": 0, "offset_search_or_application": False,
            "imu_gnss_time_offset": FIXED_IMU_GNSS_TIME_OFFSET}
