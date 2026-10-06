#!/usr/bin/env python3
"""Idealized single-worker replay using saved whole CILS certificate durations.

No search is rerun. Preparation, IO, validation, catch-up and tracking take zero
simulated time. This is NOT a wall-clock real-time implementation or benchmark.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class RecordedJob:
    case_id: str
    selected_at: float
    validation_times: tuple
    elapsed_s: float

    def __post_init__(self):
        values = (self.selected_at, self.elapsed_s, *self.validation_times)
        if (len(self.validation_times) != 5 or not all(math.isfinite(x) for x in values)
                or self.elapsed_s < 0 or self.validation_times[0] <= self.selected_at
                or any(b <= a for a, b in zip(self.validation_times, self.validation_times[1:]))
                or not math.isfinite(self.completion)):
            raise ValueError("invalid original times or recorded certificate elapsed")

    @property
    def completion(self):
        return self.selected_at + self.elapsed_s

    @property
    def validation_end(self):
        return self.validation_times[-1]

    @property
    def available_after(self):
        return max(self.completion, self.validation_end)


class SerialService:
    """Busy-drop, no service queue; finished jobs may await original validation."""
    def __init__(self):
        self.busy_until = -math.inf
        self.pending = []
        self.offered = set()
        self.last_ready = -math.inf

    def offer(self, job, time_s):
        if time_s != job.selected_at or time_s < self.last_ready or job.case_id in self.offered:
            raise ValueError("invalid or repeated selection-ready opportunity")
        self.offered.add(job.case_id)
        self.last_ready = time_s
        event = dict(case_id=job.case_id, selection_ready_s=time_s,
            recorded_cils_elapsed_s=job.elapsed_s, worker_busy_until_before_s=self.busy_until
            if math.isfinite(self.busy_until) else None)
        if time_s < self.busy_until:
            return {**event, "action":"BUSY_DROP_NO_QUEUE"}
        self.busy_until = job.completion
        self.pending.append(job)
        return {**event, "action":"SEARCH_LAUNCHED", "service_completion_s":job.completion,
                "original_validation_end_s":job.validation_end,
                "publication_not_before_s":job.available_after}

    def arrivals(self, time_s):
        ready = [job for job in self.pending if job.available_after <= time_s]
        self.pending = [job for job in self.pending if job.available_after > time_s]
        return sorted(ready, key=lambda job:(job.completion, job.selected_at, job.case_id))


@dataclass
class CatchupResult:
    track: object
    measurement: object
    status: str
    history: list
    original_origin_id: str | None = None


def step_track(track, time_s, model, missing_reason):
    if model is None:
        return track.missing(time_s, missing_reason or "MODEL_UNAVAILABLE")
    return track.observe(model, availability_time_s=time_s)


def catch_up(job, now, history, record, start):
    """Replay original data-time receipts internally; publish none of them here."""
    if now < job.available_after:
        raise ValueError("catch-up before recorded completion or original validation end")
    if not record["measurement"]["valid"]:
        return CatchupResult(None, None, "ORIGINAL_RESULT_UNAVAILABLE:"+record["status"], [])
    by_time = {t:(model,reason) for t,model,reason in history if t <= now}
    if len(by_time) != len(history) or any(t not in by_time for t in job.validation_times):
        raise ValueError("catch-up history must be unique, observed and contain original validation")
    original_models = tuple(by_time[t][0] for t in job.validation_times)
    if any(model is None for model in original_models):
        raise ValueError("saved qualified origin lacks its original validation models")
    track, measurement = start(record, original_models)
    internal = [dict(action="INTERNAL_ORIGIN_RECONSTRUCTION_NOT_EXPORTED",
        model_time_s=job.validation_end, processed_at_simulation_time_s=now)]
    origin_id = track.origin_id
    for t, model, reason in history:
        if not job.validation_end < t <= now:
            continue
        step = step_track(track, t, model, reason)
        internal.append(dict(action="INTERNAL_CATCHUP_NOT_EXPORTED", model_time_s=t,
            processed_at_simulation_time_s=now, status=step.measurement.status,
            terminal=step.terminal,
            receipt_fingerprint=getattr(getattr(step, "receipt", None), "fingerprint", None)))
        if step.terminal:
            return CatchupResult(None, None, "CATCHUP_DEAD:"+step.measurement.status, internal, origin_id)
        measurement = step.measurement
    if measurement.measurement_time != now or measurement.decision_available_time != now or not measurement.valid:
        raise ValueError("catch-up may export only a valid current-epoch measurement")
    return CatchupResult(track, measurement, "AVAILABLE_CURRENT_CANDIDATE", internal, origin_id)


class AvailabilityOwner:
    """Owner at epoch entry retains even its release epoch; no owner-result queue."""
    def __init__(self, unavailable):
        self.track = None
        self.unavailable = unavailable
        self.seen_arrivals = set()
        self.last_time = -math.inf

    def advance(self, now, model, arrivals, catchup, missing_reason=None):
        if not math.isfinite(now) or now <= self.last_time:
            raise ValueError("owner epochs must strictly increase")
        self.last_time = now
        ordered = sorted(arrivals, key=lambda j:(j.completion,j.selected_at,j.case_id))
        ids = [job.case_id for job in ordered]
        if len(ids) != len(set(ids)) or any(cid in self.seen_arrivals for cid in ids):
            raise ValueError("arrival cannot be resurrected")
        if any(job.available_after > now for job in ordered):
            raise ValueError("arrival before availability")
        self.seen_arrivals.update(ids)
        actions = []
        incumbent = self.track
        if incumbent is not None:
            for job in ordered:
                actions.append(dict(case_id=job.case_id, action="SUPPRESSED_OWNER_AT_ENTRY"))
            step = step_track(incumbent, now, model, missing_reason)
            if step.terminal:
                self.track = None
            return step.measurement, dict(event="TRACK_RELEASED" if step.terminal else "TRACK_UPDATED",
                origin_id=incumbent.origin_id, arrival_actions=actions, step=step)
        measurement = self.unavailable(now, "INACTIVE_NO_AVAILABLE_CANDIDATE")
        event = dict(event="INACTIVE", origin_id=None, arrival_actions=actions)
        for job in ordered:
            if self.track is not None:
                actions.append(dict(case_id=job.case_id, action="SUPPRESSED_AFTER_OWNER_ACQUIRED"))
                continue
            result = catchup(job, now)
            actions.append(dict(case_id=job.case_id, action=result.status,
                original_origin_id=result.original_origin_id, catchup_history=result.history))
            if result.track is None:
                continue
            if (not result.measurement.valid or result.measurement.measurement_time != now
                    or result.measurement.decision_available_time != now):
                raise ValueError("acquired owner cannot emit a historical measurement")
            self.track = result.track
            measurement = result.measurement
            event.update(event="TRACK_STARTED", case_id=job.case_id, origin_id=result.track.origin_id,
                original_selected_at_s=job.selected_at, original_validation_end_s=job.validation_end,
                service_completion_s=job.completion, scheduler_acquired_at_s=now)
        return measurement, event


def run(args):
    # All algorithm imports are deferred. Pure scheduler tests run no solvers.
    import csv
    import numpy as np
    from shadow_replay import load_model
    from real_trial import emit, serial, revision, source_snapshot, digest
    from tracking_frontend import restored_origin, acquisition_schedule
    from legsa_gins.paper_rebuild.carrier_phase.tracking import FixedCandidateTrack, TrackingConfig
    from legsa_gins.paper_rebuild.carrier_phase.admission import AdmissionConfig
    from legsa_gins.paper_rebuild.carrier_phase.measurement import CSV_FIELDS, unavailable_measurement

    summary = json.loads(args.summary.read_text())
    old_tracking = json.loads(args.original_tracking_summary.read_text())
    plan_path = args.trial/"PLAN.json"
    plan = json.loads(plan_path.read_text())
    contract = summary["input_contract"]
    if (digest(args.summary) != old_tracking["acquisition_summary_sha256"]
            or digest(plan_path) != contract["model_plan_sha256"]
            or digest(plan_path) != old_tracking["prepared_plan_sha256"]
            or contract["length_m"] != plan["baseline_length_m"]):
        raise ValueError("original acquisition/tracking/prepared input identity mismatch")
    config = AdmissionConfig(length_m=contract["length_m"], alpha_total=contract["alpha"])
    tracking_config = TrackingConfig()
    sources = source_snapshot(args.code)
    for name in ("latency_tracking_frontend.py","tracking_frontend.py","shadow_replay.py","real_trial.py"):
        path = Path(__file__).with_name(name)
        sources[str(path.relative_to(args.code))] = digest(path)
    manifest = dict(execution_commit=revision(args.code), data_mode=contract["data_mode"],
        prepared_plan_sha256=digest(plan_path), acquisition_summary_sha256=digest(args.summary),
        original_tracking_summary_sha256=digest(args.original_tracking_summary), source_files=sources,
        solver_calls=0, reference_reads=0, trace_used_online=False, production_validated=False,
        integer_truth_available=False, lifetime_false_fix_probability=None,
        replay_kind="IDEALIZED_RECORDED_CILS_SERVICE_COST",
        real_time_implementation=False, wall_clock_realtime_validated=False,
        cost_field="search.certificate.elapsed_s", worker_count_per_mode=1,
        multi_mode_disclosure="Each mode is a separate one-worker methodological replay, not concurrent deployment on a shared CPU; resource contention is unmodelled.",
        selection_opportunity="ORIGINAL_FIFTH_SELECTION_EPOCH_EVERY_TWO_SECONDS",
        worker_policy="BUSY_DROP_NO_QUEUE_FINISH_RELEASES_WORKER_IMMEDIATELY",
        owner_policy="INCUMBENT_AT_ENTRY_OWNS_FAILURE_EPOCH_NO_QUEUE_NO_RESURRECTION",
        publication_policy="FIRST_RAW_SLOT_GE_MAX_COMPLETION_ORIGINAL_VALIDATION_END_CURRENT_ONLY",
        internal_catchup_policy="LOGICAL_DATA_TIME_REPLAY_NOT_HISTORICAL_PUBLICATION",
        zero_cost_components=["preparation","model_loading","IO","validation","fault_diagnostics",
                              "catchup","tracking","export","navigation","worker_launch"],
        metadata_disclosure="Original saved case JSON is read as recorded-cost simulation input. Outcome/status never chooses launch or drop.",
        time_domain_s=[plan["records"][0]["time_s"],plan["records"][-1]["time_s"]], modes={})
    args.output.mkdir(parents=True, exist_ok=False)
    emit(args.output/"PLAN.json", manifest)
    for mode in args.modes:
        # Only timestamps define opportunities; neither status nor residuals enter scheduling.
        original_schedule = acquisition_schedule(summary, plan, mode)
        jobs, records, pins = {}, {}, {}
        expected_pins = old_tracking["modes"][mode]["acquisition_cases_inspected_at_their_data_time"]
        for end, (cid, selected_at) in original_schedule.items():
            path = args.summary.parent/"cases"/(cid+".json")
            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            if sha != expected_pins[cid]:
                raise ValueError("original acquisition case SHA mismatch: "+cid)
            rec = json.loads(data)
            if rec["case_id"] != cid or rec["mode"] != mode or rec["input_contract"] != contract["model_plan_sha256"]:
                raise ValueError("original acquisition case identity mismatch")
            # Missing/rejected/uncertified results do NOT get a free or zero-cost task.
            if not rec["search_called"]:
                raise ValueError("every registered opportunity requires recorded search service time")
            elapsed = rec["search"]["certificate"]["elapsed_s"]
            future = tuple(float(r["time_s"]) for r in plan["records"] if selected_at < r["time_s"] <= end)
            job = RecordedJob(cid,float(selected_at),future,float(elapsed))
            if selected_at in jobs:
                raise ValueError("duplicate selection-ready time")
            jobs[selected_at], records[cid], pins[cid] = job, rec, sha
        service = SerialService()
        owner = AvailabilityOwner(unavailable_measurement)
        history, valid_times, started_origins = [], [], []
        counts, service_counts, release_counts, arrival_counts = Counter(), Counter(), Counter(), Counter()
        csv_path = args.output/("CARRIER_LATENCY_TRACKED_"+mode.upper()+".csv")
        with csv_path.open("x",newline="") as csv_file, (args.output/(mode.upper()+"_EVENTS.jsonl")).open("x") as events, (args.output/(mode.upper()+"_SCHEDULE.jsonl")).open("x") as schedule_file:
            writer = csv.DictWriter(csv_file,fieldnames=CSV_FIELDS,lineterminator="\n")
            writer.writeheader()
            for row in plan["records"]:
                now = float(row["time_s"])
                if now in jobs:
                    action = service.offer(jobs[now], now)
                    service_counts[action["action"]] += 1
                    schedule_file.write(json.dumps(action,allow_nan=False)+"\n")
                arrivals = service.arrivals(now)
                for job in arrivals:
                    schedule_file.write(json.dumps(dict(action="RESULT_ARRIVAL",case_id=job.case_id,
                        service_completion_s=job.completion,original_validation_end_s=job.validation_end,
                        publication_not_before_s=job.available_after,arrival_raw_slot_s=now),allow_nan=False)+"\n")
                reason = None
                try:
                    model = load_model(args.trial,row,contract["family"])
                except (ValueError,np.linalg.LinAlgError) as exc:
                    model,reason = None,type(exc).__name__+":"+str(exc)
                history.append((now,model,reason))
                def starter(rec, original_models):
                    pair, admission, diagnosis, measurement = restored_origin(rec)
                    job = jobs[pair[0].selected_at]
                    if (not rec["search"]["certificate"]["global_optimum_certified"]
                            or any(c.selected_at != job.selected_at for c in pair)
                            or rec["case_id"] != job.case_id
                            or measurement.measurement_time != job.validation_end
                            or measurement.decision_available_time != job.validation_end):
                        raise ValueError("original certified candidate/time binding mismatch")
                    track = FixedCandidateTrack.start(*pair,original_models,admission,diagnosis,measurement,
                        admission_config=config,tracking_config=tracking_config)
                    return track,measurement
                def replay(job, current):
                    return catch_up(job,current,history,records[job.case_id],starter)
                measurement,event = owner.advance(now,model,arrivals,replay,reason)
                if measurement.measurement_time != now or measurement.decision_available_time != now:
                    raise ValueError("backdated export forbidden")
                writer.writerow(measurement.csv_row())
                event.update(time_s=now,measurement=serial(measurement),
                    selected_opportunity_action=action["action"] if now in jobs else None,
                    arrived_cases=[j.case_id for j in arrivals])
                events.write(json.dumps(serial(event),allow_nan=False)+"\n")
                counts[event["event"]] += 1
                for result in event["arrival_actions"]:
                    arrival_counts[result["action"].split(":")[0]] += 1
                if measurement.valid:
                    valid_times.append(now)
                if event["event"] == "TRACK_STARTED":
                    started_origins.append({k:event[k] for k in ("case_id","origin_id","original_selected_at_s",
                        "original_validation_end_s","service_completion_s","scheduler_acquired_at_s")})
                if event["event"] == "TRACK_RELEASED":
                    release_counts[measurement.status] += 1
        manifest["modes"][mode] = dict(epochs=len(plan["records"]),valid_experimental_measurements=len(valid_times),
            valid_times_s=valid_times,events=dict(counts),service_actions=dict(service_counts),
            arrival_actions=dict(arrival_counts),release_statuses=dict(release_counts),origins=started_origins,
            original_case_pins=pins,active_owner_at_end=owner.track is not None,worker_busy_until_s=service.busy_until,
            pending_at_end=[dict(case_id=j.case_id,completion_s=j.completion,publication_not_before_s=j.available_after)
                            for j in service.pending],csv=str(csv_path))
    emit(args.output/"SUMMARY.json",manifest)
    print(json.dumps({"event":"IDEALIZED_RECORDED_CILS_REPLAY_COMPLETE","modes":{
        mode:{k:v for k,v in value.items() if k not in ("original_case_pins","valid_times_s","origins")}
        for mode,value in manifest["modes"].items()}}),flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("trial","summary","original-tracking-summary","output"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--modes",nargs="+",choices=("full","partial"),default=("partial",))
    p.add_argument("--code",type=Path,default=Path(__file__).resolve().parents[3])
    args = p.parse_args()
    if os.uname().sysname != "Linux":
        raise RuntimeError("run only in Ubuntu WSL")
    if len(args.modes) != len(set(args.modes)):
        raise ValueError("duplicate mode")
    run(args)


if __name__ == "__main__":
    main()
