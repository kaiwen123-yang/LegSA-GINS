#!/usr/bin/env python3
"""Replay fixed-candidate tracking, with one causal owner per raw epoch.

Only acquisitions completed at the current data epoch may start a track.
Incumbents own their failure epoch too; overlapping new acquisitions are never
queued. Saved full/partial integer searches are reused without CILS.
"""
from pathlib import Path
from collections import Counter, deque
import argparse, csv, json, os, re
import numpy as np
from shadow_replay import load_model
from real_trial import emit, serial, revision, source_snapshot, digest
from legsa_gins.paper_rebuild.carrier_phase.admission import (
    FrozenCandidate, AdmissionConfig, AdmissionDecision, AdmissionEpoch,
    CandidateEpochFit, CandidateGate)
from legsa_gins.paper_rebuild.carrier_phase.faults import FaultDiagnosis, SingleFaultScore
from legsa_gins.paper_rebuild.carrier_phase.measurement import (
    CSV_FIELDS, CarrierBaselineMeasurement, BoundFaultDiagnosis, unavailable_measurement)


def restored_origin(record):
    """Restore the existing explicit schema without recomputing or changing N."""
    pair = tuple(FrozenCandidate(**{**v,
        "integer_items": tuple(tuple(x) for x in v["integer_items"]),
        "active_labels": tuple(v["active_labels"])}) for v in record["frozen_candidates"])
    if len(pair) != 2:
        raise ValueError("exactly two original frozen candidates required")
    decision = dict(record["admission"])
    epochs = []
    for saved in decision["epochs"]:
        epoch = dict(saved)
        for key in ("rows_retained", "rows_withheld", "validated_active_labels", "unknown_labels"):
            epoch[key] = tuple(epoch[key])
        for name in ("primary", "competitor"):
            fit = epoch[name]
            if fit is not None:
                fit = dict(fit)
                for key in ("baseline_center_m", "rows_retained"):
                    fit[key] = tuple(fit[key])
                fit["baseline_covariance_m2"] = tuple(tuple(x) for x in fit["baseline_covariance_m2"])
                epoch[name] = CandidateEpochFit(**fit)
        epochs.append(AdmissionEpoch(**epoch))
    decision["epochs"] = tuple(epochs)
    for key in ("expected_future_times", "observed_future_times", "validated_labels",
                "unvalidated_selected_labels", "reasons", "assumptions"):
        decision[key] = tuple(decision[key])
    for name in ("primary", "competitor"):
        decision[name] = CandidateGate(**decision[name]) if decision[name] is not None else None
    admission = AdmissionDecision(**decision)
    bound = dict(record["phase_diagnosis"])
    diagnosis = dict(bound["diagnosis"])
    diagnosis["scores"] = tuple(SingleFaultScore(**{**score,
        "equivalent_hypotheses": tuple(score["equivalent_hypotheses"])})
        for score in diagnosis["scores"])
    for key in ("best_hypotheses", "unobservable_hypotheses"):
        diagnosis[key] = tuple(diagnosis[key])
    diagnosis["ranked_ties"] = tuple(tuple(x) for x in diagnosis["ranked_ties"])
    bound["diagnosis"] = FaultDiagnosis(**diagnosis)
    bound["ordered_model_fingerprints"] = tuple(bound["ordered_model_fingerprints"])
    measurement = dict(record["measurement"])
    for key in ("baseline_ecef_m", "retained_rows", "fixed_labels"):
        if measurement[key] is not None:
            measurement[key] = tuple(measurement[key])
    if measurement["covariance_ecef_m2"] is not None:
        measurement["covariance_ecef_m2"] = tuple(tuple(x) for x in measurement["covariance_ecef_m2"])
    return pair, admission, BoundFaultDiagnosis(**bound), CarrierBaselineMeasurement(**measurement)


class EpochOwner:
    """Small deterministic scheduler; no ranking by residual or reference."""
    def __init__(self):
        self.track = None
        self.seen_origins = set()

    def advance(self, time_s, model, fresh, start, *, missing_reason="MODEL_UNAVAILABLE"):
        owner_at_entry = self.track
        suppressed = []
        if owner_at_entry is not None:
            for record in fresh:
                if record["measurement"]["valid"]:
                    suppressed.append(record["case_id"])
            if model is None:
                step = owner_at_entry.missing(time_s, missing_reason)
            else:
                step = owner_at_entry.observe(model, availability_time_s=time_s)
            if step.terminal:
                self.track = None
            return step.measurement, {
                "event": "TRACK_RELEASED" if step.terminal else "TRACK_UPDATED",
                "origin_id": owner_at_entry.origin_id,
                "suppressed_valid_origins": suppressed, "step": serial(step)}
        if len(fresh) > 1:
            raise ValueError("ambiguous simultaneous acquisition schedule")
        if fresh and fresh[0]["measurement"]["valid"]:
            record = fresh[0]
            key = record["case_id"]
            if key in self.seen_origins:
                raise ValueError("an origin may never be resurrected")
            if float(record["measurement"]["decision_available_time"]) != time_s:
                raise ValueError("origin must become available at this exact epoch")
            track, measurement = start(record)
            self.seen_origins.add(key)
            self.track = track
            return measurement, {"event": "TRACK_STARTED", "origin_id": track.origin_id,
                                 "case_id": key, "suppressed_valid_origins": []}
        reason = fresh[0]["status"] if fresh else "INACTIVE_NO_CURRENT_ADMISSION"
        return unavailable_measurement(time_s, reason), {
            "event": "INACTIVE", "origin_id": None, "suppressed_valid_origins": []}


def acquisition_schedule(summary, plan, mode):
    records = plan["records"]
    if not records or any(float(b["time_s"]) <= float(a["time_s"])
                          for a, b in zip(records, records[1:])):
        raise ValueError("prepared model epochs must be chronological")
    result = {}
    ids = summary["attempted_case_ids"]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate acquisition case identity")
    for case in ids:
        match = re.fullmatch(r"(full|partial)_(\d+\.\d+)", case)
        if match is None:
            raise ValueError("unrecognized fixed-window acquisition identity")
        if match[1] != mode:
            continue
        start = float(match[2])
        rows = [r for r in records if start <= r["time_s"] < start + 2.]
        if len(rows) != 10:
            raise ValueError("acquisition must have original ten real epochs")
        t = float(rows[-1]["time_s"])
        if t in result:
            raise ValueError("more than one acquisition at an epoch")
        result[t] = (case, float(rows[4]["time_s"]))
    if len(result) != summary["modes"][mode]["cases"]:
        raise ValueError("summary case count differs from acquisition schedule")
    return result


def run(a):
    # Import only at actual execution; ownership tests need no carrier solver.
    from legsa_gins.paper_rebuild.carrier_phase.tracking import FixedCandidateTrack, TrackingConfig
    summary = json.loads(a.summary.read_text())
    plan = json.loads((a.trial / "PLAN.json").read_text())
    contract = summary["input_contract"]
    if digest(a.trial / "PLAN.json") != contract["model_plan_sha256"]:
        raise ValueError("acquisition and tracking prepared inputs differ")
    if contract["length_m"] != plan["baseline_length_m"]:
        raise ValueError("physical length mismatch")
    a.output.mkdir(parents=True, exist_ok=False)
    config = AdmissionConfig(length_m=contract["length_m"], alpha_total=contract["alpha"])
    tracking_config = TrackingConfig()
    sources = source_snapshot(a.code)
    sources[str(Path(__file__).relative_to(a.code))] = digest(__file__)
    manifest = {
        "execution_commit": revision(a.code), "data_mode": contract["data_mode"],
        "prepared_plan_sha256": digest(a.trial / "PLAN.json"),
        "acquisition_summary_sha256": digest(a.summary), "source_files": sources,
        "solver_calls": 0, "reference_reads": 0, "trace_used_online": False,
        "time_domain_s": [plan["records"][0]["time_s"], plan["records"][-1]["time_s"]],
        "ownership": "INCUMBENT_AT_ENTRY_EXCLUSIVE_NO_QUEUE_NO_RESURRECTION",
        "wall_clock_acquisition_latency_charged": False,
        "integer_truth_available": False, "production_validated": False,
        "lifetime_false_fix_probability": None, "modes": {}}
    emit(a.output / "PLAN.json", manifest)
    for mode in a.modes:
        schedule = acquisition_schedule(summary, plan, mode)
        owner = EpochOwner()
        recent = deque(maxlen=config.validation_epochs)
        counts, releases = Counter(), Counter()
        valid_times, origins, case_inputs = [], [], {}
        accepted_searches_reused = 0
        csv_path = a.output / ("CARRIER_TRACKED_" + mode.upper() + ".csv")
        with csv_path.open("x", newline="") as csv_file, (a.output / (mode.upper()+"_EVENTS.jsonl")).open("x") as events:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            for row in plan["records"]:
                t = float(row["time_s"])
                problem = None
                try:
                    model = load_model(a.trial, row, contract["family"])
                except (ValueError, np.linalg.LinAlgError) as exc:
                    model = None
                    problem = type(exc).__name__ + ":" + str(exc)
                recent.append(model)
                fresh = []
                if t in schedule:
                    case, selected_at = schedule[t]
                    path = a.summary.parent / "cases" / (case + ".json")
                    record = json.loads(path.read_text())
                    case_inputs[case] = digest(path)
                    if (record["case_id"] != case or record["mode"] != mode
                            or record["input_contract"] != contract["model_plan_sha256"]
                            or float(record["measurement"]["measurement_time"]) != t):
                        raise ValueError("acquisition identity/input/time mismatch")
                    if record["measurement"]["valid"]:
                        if (not record["search"]["certificate"]["global_optimum_certified"]
                                or any(c["selected_at"] != selected_at for c in record["frozen_candidates"])):
                            raise ValueError("certified original selection required")
                    fresh.append(record)
                def start(record):
                    nonlocal accepted_searches_reused
                    pair, admission, diagnosis, measurement = restored_origin(record)
                    if any(m is None for m in recent) or len(recent) != config.validation_epochs:
                        raise ValueError("qualified origin is missing its original validation models")
                    track = FixedCandidateTrack.start(*pair, tuple(recent), admission, diagnosis,
                        measurement, admission_config=config, tracking_config=tracking_config)
                    accepted_searches_reused += 1
                    return track, measurement
                measurement, event = owner.advance(t, model, fresh, start,
                    missing_reason=problem or "MODEL_UNAVAILABLE")
                if measurement.measurement_time != t or measurement.decision_available_time != t:
                    raise ValueError("tracking must never export a delayed or backdated update")
                writer.writerow(measurement.csv_row())
                event.update(time_s=t, measurement=serial(measurement),
                    acquisition_status=fresh[0]["status"] if fresh else None)
                events.write(json.dumps(serial(event), ensure_ascii=True, allow_nan=False)+"\n")
                counts[event["event"]] += 1
                counts["suppressed_valid_origins"] += len(event["suppressed_valid_origins"])
                if measurement.valid:
                    valid_times.append(t)
                if event["event"] == "TRACK_STARTED":
                    origins.append({"case_id": event["case_id"], "origin_id": event["origin_id"], "time_s": t})
                if event["event"] == "TRACK_RELEASED":
                    releases[measurement.status] += 1
                if event["event"] not in ("INACTIVE", "TRACK_UPDATED"):
                    print(json.dumps({"mode": mode, "time_s": t, "event": event["event"],
                                      "status": measurement.status}), flush=True)
        manifest["modes"][mode] = {
            "epochs": len(plan["records"]), "valid_experimental_measurements": len(valid_times),
            "valid_times_s": valid_times, "events": dict(counts), "release_statuses": dict(releases),
            "origins": origins, "reused_integer_searches_started": accepted_searches_reused,
            "acquisition_cases_inspected_at_their_data_time": case_inputs,
            "active_at_end": owner.track is not None, "csv": str(csv_path)}
    emit(a.output / "SUMMARY.json", manifest)
    print(json.dumps({"event": "TRACKING_COMPLETE", "modes":
        {k: {key: value for key, value in v.items() if key not in
             ("acquisition_cases_inspected_at_their_data_time", "valid_times_s", "origins")}
         for k, v in manifest["modes"].items()}}), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trial", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--modes", choices=("full", "partial"), nargs="+", default=("full", "partial"))
    p.add_argument("--code", type=Path, default=Path(__file__).resolve().parents[3])
    a = p.parse_args()
    if os.uname().sysname != "Linux":
        raise RuntimeError("run algorithms in Ubuntu WSL")
    if len(a.modes) != len(set(a.modes)):
        raise ValueError("duplicate mode")
    run(a)


if __name__ == "__main__":
    main()
