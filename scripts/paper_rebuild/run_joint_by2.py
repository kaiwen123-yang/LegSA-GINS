#!/usr/bin/env python3
"""Run BY2 measurement epochs through the joint navigator, without a reference.

Output retains the required IMU source availability separately from measurement
time. Original GNSS receipt delays are not yet represented by GNSS18 inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

CSV_FIELDS = [
    "time_s", *[f"p_{axis}_m" for axis in "NED"], *[f"v_{axis}_mps" for axis in "NED"],
    "roll_rad", "pitch_rad", "yaw_rad", *[f"bias_{i}" for i in range(6)],
    "candidate_yaws_rad", "candidate_costs", "support_ids", "direction_status",
    "candidate_support_complete", "gnss_innovation_nis", "extra_fields",
]
ROW_FIELDS = {
    "time_s", "p", "v", "rpy_rad", "bias", "candidate_yaws_rad", "candidate_costs",
    "support_ids", "direction_status", "candidate_support_complete", "gnss_innovation_nis",
}


def json_value(value):
    """Keep every unavailable state component as JSON null, never as a fabricated state."""
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return json_value(value.tolist())
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path, value):
    with path.open("w", encoding="utf-8") as stream:
        json.dump(json_value(value), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_rows(output_root, rows):
    with (output_root / "navigation.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(json_value(row), ensure_ascii=False, allow_nan=False) + "\n")
    with (output_root / "navigation.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            saved = {name: row.get(name) for name in (
                "time_s", "direction_status", "candidate_support_complete", "gnss_innovation_nis")}
            for field, start, end in (("p", 1, 4), ("v", 4, 7), ("rpy_rad", 7, 10), ("bias", 10, 16)):
                saved.update(zip(CSV_FIELDS[start:end], row[field]))
            for field in ("candidate_yaws_rad", "candidate_costs", "support_ids"):
                saved[field] = json.dumps(json_value(row[field]), ensure_ascii=False, allow_nan=False)
            saved["extra_fields"] = json.dumps(
                json_value({key: value for key, value in row.items() if key not in ROW_FIELDS}),
                ensure_ascii=False, allow_nan=False)
            writer.writerow(saved)


def output_summary(rows):
    finite = sum(all(math.isfinite(float(value)) for field in ("p", "v", "rpy_rad")
                     for value in row[field]) for row in rows)
    no_init = sum("NO_INIT" in row["direction_status"] for row in rows)
    navigation_status = ("FINITE_CONDITIONAL_OUTPUT_AVAILABLE" if finite else
                         "NO_INIT" if rows and no_init == len(rows) else "NO_FINITE_NAVIGATION_OUTPUT")
    return dict(
        causal_output_rows=len(rows), finite_navigation_state_rows=finite, no_init_rows=no_init,
        unavailable_navigation_state_rows=len(rows)-finite,
        direction_status_counts=dict(Counter(row["direction_status"] for row in rows)),
        first_output_time_s=rows[0]["time_s"] if rows else None,
        last_output_time_s=rows[-1]["time_s"] if rows else None,
        navigation_status=navigation_status,
        json_nonfinite_representation="null; CSV numeric state columns retain nan/inf",
        output_scope="emitted_measurement_epoch_rows_with_IMU_availability_no_historical_replacement",
        arrival_time_online_equivalence=False,
        arrival_time_limitation="original_GNSS_receipt_delays_not_in_GNSS18",
        maximum_imu_publication_delay_s=max((row.get("available_time_s", row["time_s"])-row["time_s"]
                                           for row in rows), default=0.),
        navigation_accuracy_evaluated=False, navigation_benefit_established=False,
        reference_reads=0, evaluator_calls=0,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("body", "imu", "gnss", "carrier-plan", "calibration-model"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--noise-profile", type=Path, default=ROOT / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml")
    parser.add_argument("--phase-noise-model", type=Path,
                        help="Frozen BY development working measurement model JSON; raw input files remain original")
    parser.add_argument("--support-motion-model", type=Path,
                        help="BY-derived finite common-motion model with joint foot/external source qualification")
    parser.add_argument("--start", type=float, default=96.)
    parser.add_argument("--end", type=float, default=101.)
    parser.add_argument("--key-dt", type=float, default=.1)
    parser.add_argument("--mode", choices=("U0", "U1", "U2", "U3"), default="U1")
    parser.add_argument("--support-inference", choices=("full_nonlinear", "shared_linearization", "shared_separator"),
                        default="full_nonlinear")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    products = (
        "run_status.json", "input_summary.json", "sensor_metadata.json", "navigation.jsonl",
        "navigation.csv", "decisions.json", "estimator_summary.json", "summary.json",
    )
    if any((output / name).exists() for name in products):
        parser.error("output-root already contains run products; use a new output directory")
    started = time.monotonic()
    record = dict(
        status="STARTING", started_at_utc=datetime.now(timezone.utc).isoformat(),
        data_mode="real_by2_raw", sequence="BY2", mode=args.mode,
        support_inference=args.support_inference,
        window_s=[args.start, args.end], key_dt_s=args.key_dt,
        purpose="REAL_ASYNCHRONOUS_INITIALIZATION_INTEGRATION_ONLY",
        estimator_truth_input=False, synthetic_data_used=False, reference_reads=0,
        evaluator_calls=0, navigation_benefit_established=False,
        runtime=dict(python=platform.python_version(), platform=platform.platform()),
    )
    write_json(output / "run_status.json", record)
    navigator = None
    try:
        sources = sorted((ROOT / "src/legsa_gins/paper_rebuild/joint_navigation").glob("*.py"))
        sources.append(Path(__file__).resolve())
        record["source_sha256"] = {}
        for path in sources:
            relative = path.relative_to(ROOT)
            content = path.read_bytes()
            target = output / "SOURCE_SNAPSHOT" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            record["source_sha256"][str(relative)] = hashlib.sha256(content).hexdigest()
        record["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        from legsa_gins.paper_rebuild.joint_navigation.real_data import By2InputConfig, load_by2_events
        from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator

        config = By2InputConfig(
            args.body, args.imu, args.gnss, args.carrier_plan,
            args.calibration_model, args.noise_profile,
            start_s=args.start, end_s=args.end, key_dt_s=args.key_dt)
        record["input_config"] = asdict(config)
        record["status"] = "READING_INPUT"
        write_json(output / "run_status.json", record)
        inputs = load_by2_events(config)
        inputs["metadata"]["support_inference"] = args.support_inference
        if args.support_motion_model is not None:
            motion_content = args.support_motion_model.read_bytes()
            motion_model = json.loads(motion_content)
            inputs["metadata"]["support_motion_model"] = motion_model["support_motion_model"]
            inputs["metadata"]["support_prediction"] = "foot_external"
            inputs["metadata"]["support_policy_search"] = "observed_groups"
            record["support_motion_model"] = dict(path=str(args.support_motion_model.resolve()),
                sha256=hashlib.sha256(motion_content).hexdigest(), content=motion_model)
            (output / "support_motion_model.json").write_bytes(motion_content)
        if args.phase_noise_model is not None:
            model_content = args.phase_noise_model.read_bytes()
            model = json.loads(model_content)
            inputs["metadata"]["phase_noise_model"] = dict(model["parameters"],
                model_id=model["model_id"], qualification_scope=model["qualification_scope"])
            record["phase_noise_model"] = dict(path=str(args.phase_noise_model.resolve()),
                sha256=hashlib.sha256(model_content).hexdigest(), content=model)
            (output / "phase_noise_model.json").write_bytes(model_content)
        write_json(output / "input_summary.json", inputs["input_summary"])
        write_json(output / "sensor_metadata.json", inputs["metadata"])
        record.update(status="RUNNING", input_event_count=len(inputs["events"]),
                      input_read_elapsed_s=time.monotonic()-started)
        write_json(output / "run_status.json", record)
        print(f"BY2 {args.mode}: {args.start:g}--{args.end:g} s; {len(inputs['events'])} source-time events", flush=True)
        navigator = JointNavigator(inputs["metadata"], mode=args.mode)
        result = navigator.run(inputs["events"])
        write_rows(output, result["rows"])
        write_json(output / "decisions.json", result["decisions"])
        write_json(output / "estimator_summary.json", result["summary"])
        summary = output_summary(result["rows"])
        summary.update(mode=args.mode, data_mode="real_by2_raw", purpose=record["purpose"],
                       input_event_count=len(inputs["events"]))
        write_json(output / "summary.json", summary)
        record.update(status="COMPLETED", navigation_status=summary["navigation_status"],
                      causal_output_rows=len(result["rows"]), elapsed_s=time.monotonic()-started)
        write_json(output / "run_status.json", record)
        print(json.dumps(json_value(summary), ensure_ascii=False, allow_nan=False), flush=True)
    except (Exception, KeyboardInterrupt) as error:
        record.update(status="INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "FAILED",
                      failed_phase=record["status"], error_type=type(error).__name__,
                      error=str(error), elapsed_s=time.monotonic()-started)
        write_json(output / "run_status.json", record)
        if navigator is not None:
            # Keep all rows emitted before failure, including NO_INIT rows.
            write_rows(output, navigator.rows)
            write_json(output / "decisions.json", navigator.decisions)
            summary = output_summary(navigator.rows)
            summary.update(status=record["status"], partial_output=True, mode=args.mode,
                           data_mode="real_by2_raw", purpose=record["purpose"])
            write_json(output / "summary.json", summary)
            write_json(output / "estimator_summary.json", dict(
                status=record["status"], final_estimator_summary_available=False,
                causal_output_rows=len(navigator.rows), partial_output=True))
        raise


if __name__ == "__main__":
    main()
