#!/usr/bin/env python3
"""One offline BY2 development comparison against the frozen original V3."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.paper_rebuild.clean5_parity.evaluation import body_to_ned, transform_nav, write_transformed_nav
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records, write_scope_audit
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import ecef_to_geodetic
from legsa_gins.paper_rebuild.subprocess_guard import run_process_group

METRICS = ("horizontal_err_m", "position_3d_err_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def geographic_ned(latitude, longitude):
    sl, cl, so, co = math.sin(latitude), math.cos(latitude), math.sin(longitude), math.cos(longitude)
    return np.array([[-sl*co, -so, -cl*co], [-sl*so, co, -cl*so], [cl, 0., -sl]])


def export_nav(rows, metadata, output, baseline_median):
    """Convert the fixed NED state to geographic NED at the IMU, then shift only position."""
    origin = np.asarray(metadata["origin_ecef_m"], float)
    rotation_origin = np.asarray(metadata["R_ecef_from_ned"], float)
    native = []
    for row in rows:
        p, v, rpy = (np.asarray(row[key], float) for key in ("p", "v", "rpy_rad"))
        latitude, longitude, height = ecef_to_geodetic(origin+rotation_origin@p)
        fixed_to_geographic = geographic_ned(latitude, longitude).T@rotation_origin
        rotation_body = fixed_to_geographic@body_to_ned(np.degrees(rpy).reshape(1, 3))[0]
        roll_pitch_yaw = Rotation.from_matrix(rotation_body).as_euler("ZYX", degrees=True)[::-1]
        velocity = fixed_to_geographic@v
        # Column zero is an unused format placeholder, not a reconstructed GPS week.
        native.append([0., row["time_s"], math.degrees(latitude), math.degrees(longitude),
                       height, *velocity, *roll_pitch_yaw])
    native = np.asarray(native)
    source = output / "NAV_IMU_POINT.nav"
    target = output / "EVAL_NAV_V3.nav"
    np.savetxt(source, native, fmt="%.17g", header="unused time_s lat_deg lon_deg height_m vN vE vD roll_deg pitch_deg yaw_deg", comments="% ")
    written = pd.read_csv(source, sep=r"\s+", engine="python", header=None, comment="%").to_numpy(float)
    transformed = transform_nav(written, baseline_median)
    write_transformed_nav(source, target, transformed)
    return target, dict(
        source_frame="fixed_local_NED", exported_frame="geographic_NED_at_IMU",
        source_point="IMU", evaluation_point="original_V3_dual_antenna_midpoint",
        baseline_median_m=baseline_median,
        lever_frd_m=[.03, .03-baseline_median/2., -.30],
        position_transform_applications=1, fit_used=False, time_shift_s=0.,
        position_only_POI_transform=True, exported_velocity_point="IMU",
        velocity_accuracy_evaluated=False, STD="NOT_AVAILABLE_NOT_FABRICATED",
        source_nav_sha256=sha(source), evaluator_nav_sha256=sha(target))


def merge_pairs(times, valid, start, end):
    """Only adjacent available published rows support an interval; do not cross NO_INIT."""
    intervals = []
    for index in range(len(times)-1):
        left, right = max(start, float(times[index])), min(end, float(times[index+1]))
        if not (valid[index] and valid[index+1]) or right <= left:
            continue
        if intervals and left == intervals[-1][1]:
            intervals[-1][1] = right
        else:
            intervals.append([left, right])
    return intervals


def intersect_intervals(first, second):
    return [[max(a, c), min(b, d)] for a, b in first for c, d in second if min(b, d) > max(a, c)]


def interval_metrics(errors, intervals):
    """Integrate linearly interpolated squared errors, clipping to the same physical intervals."""
    times = errors["time"].to_numpy(float)
    result = {}
    for name in METRICS:
        squared = errors[name].to_numpy(float)**2
        integral, duration, maximum = 0., 0., 0.
        sample_mask = np.zeros(len(times), dtype=bool)
        for left, right in intervals:
            inside = (times > left) & (times < right)
            knots = np.r_[left, times[inside], right]
            values = np.interp(knots, times, squared)
            integral += float(np.trapz(values, knots))
            duration += right-left
            maximum = max(maximum, float(np.sqrt(values.max())))
            sample_mask |= (times >= left) & (times <= right)
        result[name] = dict(time_weighted_rmse=math.sqrt(integral/duration) if duration else None,
                            duration_s=duration, samples=int(sample_mask.sum()),
                            absolute_max=maximum if duration else None)
    return result


def evaluate_child(evaluator, trace, nav, output, window, lock, raw_root, clean_root):
    child = output / "FROZEN_EVALUATOR"
    child.mkdir()
    config = dict(evaluator=str(evaluator), evaluator_sha256=lock["evaluator"]["sha256"],
                  trace=str(trace), trace_sha256=lock["sequence"]["evaluation"]["reference"]["sha256"],
                  window=window, outdir=str(child), v3_export_matched_truth=False,
                  consistency_policy="canonical_v2_wgs84_full_support")
    config_path = child / "CAPTURE_CONFIG.json"
    write_json(config_path, config)
    environment = dict(PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                       MKL_NUM_THREADS="1", MPLBACKEND="Agg", MPLCONFIGDIR=str(child/".matplotlib"),
                       XDG_CACHE_HOME=str(child/".cache"),
                       PYTHONPATH=str(ROOT/"scripts/paper_rebuild/v3_evaluator_observer")+":"+str(ROOT/"src"),
                       CLEAN5_EVALUATOR_CAPTURE_CONFIG=str(config_path))
    argv = [sys.executable, str(evaluator), "--trace", str(trace), "--nav", str(nav),
            "--outdir", str(child), "--base_time", "1772784000", "--yaw_truth_mode", "enu"]
    log = child / "EVALUATOR_OPENAT.strace"
    command = ["env", *[f"{key}={value}" for key, value in environment.items()],
               "strace", "-f", "-yy", "-s", "4096", "-e", "trace=openat,execve", "-o", str(log), *argv]
    result = run_process_group(command, cwd=ROOT, timeout_seconds=1800.,
                               timeout_message="BY2 offline evaluator timed out",
                               launch_failure_message="BY2 offline evaluator launch failed")
    (child/"stdout.log").write_text(result.stdout, encoding="utf-8")
    (child/"stderr.log").write_text(result.stderr, encoding="utf-8")
    records = audited_open_records(log, ROOT)
    reference_opens = [item for item in records if Path(item["path"]) == trace]
    raw_opens = [item for item in records if raw_root in Path(item["path"]).parents]
    capture_path = child / "EVALUATOR_CAPTURE.json"
    capture = json.loads(capture_path.read_text()) if capture_path.exists() else {}
    scope = write_scope_audit(records, raw_root=raw_root, clean_root=clean_root, allowed_write_roots=[child])
    passed = (result.returncode == 0 and len(reference_opens) == len(raw_opens) == 1
              and reference_opens[0]["return_code"] >= 0 and "O_RDONLY" in reference_opens[0]["flags"]
              and capture.get("trace_sha256") == config["trace_sha256"]
              and capture.get("trace_handle_hash_count") == 1
              and capture.get("consistency", {}).get("passed") is True and scope["pass"])
    audit = dict(passed=passed, argv=argv, exit_code=result.returncode,
                 reference_child_opens=len(reference_opens), parent_reference_payload_reads=0,
                 evaluator_invocation_attempts=1, raw_opens=len(raw_opens),
                 STD="OMITTED; no uncertainty/NEES comparison", write_scope=scope)
    write_json(child/"EVALUATION_AUDIT.json", audit)
    if not passed:
        raise RuntimeError("Frozen BY2 evaluation or observation contract failed; see EVALUATION_AUDIT.json")
    return pd.read_csv(child/"error_series.csv"), audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--clean-root", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--start", type=float)
    parser.add_argument("--end", type=float)
    args = parser.parse_args(argv)
    run, output, clean, raw = [path.resolve() for path in (
        args.run_root, args.output_root, args.clean_root, args.raw_root)]
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    record = dict(status="STARTING", purpose="BY2_OFFLINE_DEVELOPMENT_READOUT_NOT_FORMAL_GAIN",
                  started_at_utc=datetime.now(timezone.utc).isoformat(), source_run=str(run),
                  source_sha256=sha(Path(__file__)), reference_parent_reads=0, navigator_calls=0)
    write_json(output/"run_status.json", record)
    try:
        metadata = json.loads((run/"sensor_metadata.json").read_text())
        run_record = json.loads((run/"run_status.json").read_text())
        if metadata["sequence"] != "BY2" or metadata["data_mode"] != "real_by2_raw" or run_record["status"] != "COMPLETED":
            raise ValueError("Expected a completed real BY2 run")
        start = metadata["window_s"][0] if args.start is None else args.start
        end = metadata["window_s"][1] if args.end is None else args.end
        if not metadata["window_s"][0] <= start < end <= metadata["window_s"][1]:
            raise ValueError("Requested evaluation interval must lie within the recorded input window")
        window = [start, end]
        rows = [json.loads(line) for line in (run/"navigation.jsonl").read_text().splitlines() if line.strip()]
        rows = [row for row in rows if start <= row["time_s"] <= end]
        times = np.asarray([row["time_s"] for row in rows])
        if not len(times) or np.any(np.diff(times) <= 0):
            raise ValueError("Causal output time must be nonempty and strictly increasing")
        finite = np.array([all(np.isfinite(np.asarray(row[key], float)).all()
                               for key in ("p", "v", "rpy_rad")) for row in rows])
        available = merge_pairs(times, finite, start, end)
        finite_rows = [row for row, valid in zip(rows, finite) if valid]
        coverage = dict(requested_window_s=window, causal_rows=len(rows), finite_state_rows=len(finite_rows),
                        no_init_rows=sum(row["direction_status"] == "NO_INIT" for row in rows),
                        unavailable_rows=int((~finite).sum()), finite_intervals_s=available,
                        finite_interval_duration_s=sum(b-a for a, b in available),
                        requested_duration_s=end-start,
                        complete_candidate_support_rows=sum(row.get("candidate_support_complete") is True for row in finite_rows),
                        complete_direction_domain_certified=False,
                        input_run_status_sha256=sha(run/"run_status.json"),
                        input_navigation_sha256=sha(run/"navigation.jsonl"),
                        metadata_sha256=sha(run/"sensor_metadata.json"))
        write_json(output/"OUTPUT_COVERAGE.json", coverage)
        if len(finite_rows) < 2:
            record.update(status="NO_FINITE_EVALUATION_INTERVAL", evaluator_invocation_attempts=0)
            write_json(output/"run_status.json", record)
            return
        lock = json.loads((ROOT/"docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json").read_text())
        sequence = next(item for item in lock["sequences"] if item["sequence_id"] == "BY2")
        lock["sequence"] = sequence
        def resolve(value):
            return Path(value.replace("<CLEAN_ROOT>", str(clean)).replace("<RAW_ROOT>", str(raw)).replace("<V3_ROOT>", str(clean/"stages/CLEAN8_PROTOCOL_V3")))
        evaluator = resolve(lock["evaluator"]["path"])
        trace = resolve(sequence["evaluation"]["reference"]["path"])
        old_errors = resolve(sequence["evaluation"]["retained_error_series"]["path"])
        if sha(evaluator) != lock["evaluator"]["sha256"] or sha(old_errors) != sequence["evaluation"]["retained_error_series"]["sha256"]:
            raise ValueError("Frozen evaluator or original V3 BY2 error-series identity mismatch")
        nav, transform = export_nav(finite_rows, metadata, output, sequence["evaluation"]["baseline_median_m"])
        write_json(output/"NAV_TRANSFORM.json", transform)
        record.update(status="EVALUATING", requested_window_s=window, evaluator_invocation_attempts=1,
                      frozen_v3_commit=lock["scientific_freeze"], frozen_v3_run_id=sequence["run_id"],
                      baseline_error_path=str(old_errors), baseline_error_sha256=sha(old_errors),
                      original_v3_formal_window_s=sequence["full_window_s"],
                      source_run_record=run_record)
        write_json(output/"run_status.json", record)
        new, audit = evaluate_child(evaluator, trace, nav, output, window, lock, raw, clean)
        old = pd.read_csv(old_errors, encoding="utf-8-sig")
        new_valid = np.isfinite(new[list(METRICS)].to_numpy(float)).all(axis=1)
        old_valid = np.isfinite(old[list(METRICS)].to_numpy(float)).all(axis=1)
        new_intervals = intersect_intervals(available, merge_pairs(new["time"].to_numpy(), new_valid, start, end))
        old_intervals = merge_pairs(old["time"].to_numpy(), old_valid, start, end)
        common = intersect_intervals(new_intervals, old_intervals)
        full_new = interval_metrics(new, new_intervals)
        full_old = interval_metrics(old, old_intervals)
        common_new = interval_metrics(new, common)
        common_old = interval_metrics(old, common)
        comparison = dict(
            requested_window_s=window, output_coverage=coverage,
            requested_window=dict(
                joint_finite_metrics=full_new, v3_metrics=full_old,
                direct_gain_not_computed="Joint NO_INIT and unequal availability are retained, not scored as zero"),
            common_finite_intervals_s=common,
            common_finite=dict(joint=common_new, frozen_v3=common_old,
                joint_minus_v3={name: common_new[name]["time_weighted_rmse"]-common_old[name]["time_weighted_rmse"]
                               if common_new[name]["time_weighted_rmse"] is not None else None for name in METRICS}),
            metric_policy="time-weighted RMSE of piecewise-linear squared errors; identical physical intervals; no interval crosses a joint NO_INIT row",
            comparison_type="original_V3_system_comparison_not_same_backend_mechanism_ablation",
            initialization_difference="joint starts at requested run start; frozen V3 is the original 66--340 s causal run, not restarted at this short window",
            timing_scope="state accuracy at measurement epochs; not a zero-delay arrival-time navigation comparison",
            joint_imu_availability_recorded=all("available_time_s" in row for row in rows),
            maximum_recorded_imu_publication_delay_s=(max(row["available_time_s"]-row["time_s"] for row in rows)
                if all("available_time_s" in row for row in rows) else None),
            original_gnss_receipt_delays_modeled=False,
            reference_claim="Fixposition-derived fused reference with shared GNSS lineage; not independent truth",
            velocity_accuracy=dict(status="NOT_EVALUATED", reason="Frozen error series and evaluator do not provide velocity truth or velocity errors"),
            uncertainty_comparison="NOT_EVALUATED_NO_FABRICATED_STD",
            complete_research_goal=False, scientific_scope="single BY2 development window",
            frozen_v3_commit=lock["scientific_freeze"], baseline_error_sha256=sha(old_errors),
            evaluator_audit=audit)
        write_json(output/"COMPARISON.json", comparison)
        with (output/"COMPARISON.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["scope", "arm", "metric", "time_weighted_rmse", "duration_s", "samples", "absolute_max"])
            writer.writeheader()
            for scope, arm, metrics in [("requested_finite_support", "joint", full_new),
                                        ("requested_window", "frozen_v3", full_old),
                                        ("common_finite_support", "joint", common_new),
                                        ("common_finite_support", "frozen_v3", common_old)]:
                for name, values in metrics.items():
                    writer.writerow(dict(scope=scope, arm=arm, metric=name, **values))
        record.update(status="COMPLETED_DEVELOPMENT_READOUT", elapsed_s=time.monotonic()-started,
                      common_finite_duration_s=sum(b-a for a, b in common),
                      reference_child_opens=audit["reference_child_opens"], velocity_accuracy_evaluated=False)
        write_json(output/"run_status.json", record)
        print(json.dumps(dict(status=record["status"], coverage=coverage, common_finite=comparison["common_finite"]), ensure_ascii=False, allow_nan=False), flush=True)
    except (Exception, KeyboardInterrupt) as error:
        record.update(status="INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAILED",
                      error_type=type(error).__name__, error=str(error), elapsed_s=time.monotonic()-started)
        write_json(output/"run_status.json", record)
        raise


if __name__ == "__main__":
    main()
