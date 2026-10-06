#!/usr/bin/env python3
"""Necessary latency check on saved records; no AR/admission/navigation imports."""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def quantile(values, probability):
    values = sorted(values)
    position = (len(values) - 1) * probability
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def necessary_condition(selected_at, elapsed_s, measurement_time):
    selected_at, elapsed_s, measurement_time = map(float, (selected_at, elapsed_s, measurement_time))
    require(all(math.isfinite(x) for x in (selected_at, elapsed_s, measurement_time)), "nonfinite time")
    require(elapsed_s >= 0, "negative certificate elapsed")
    completion = selected_at + elapsed_s
    require(math.isfinite(completion), "nonfinite completion")
    return completion, measurement_time >= completion, measurement_time - completion


def diagnose(acquisition_summary, tracking_summary, output_dir, label):
    acquisition_summary, tracking_summary, output_dir = map(Path, (acquisition_summary, tracking_summary, output_dir))
    require(not output_dir.exists(), "output directory exists; preserve old diagnosis")
    pins = {}
    def read(path, alias):
        data = path.read_bytes()
        pins[alias] = hashlib.sha256(data).hexdigest()
        return data
    acquisition = json.loads(read(acquisition_summary, "acquisition/summary.json"))
    tracking = json.loads(read(tracking_summary, "tracking/summary.json"))
    require(pins["acquisition/summary.json"] == tracking["acquisition_summary_sha256"], "acquisition-summary SHA mismatch")
    ids = acquisition["attempted_case_ids"]
    require(len(ids) == len(set(ids)), "duplicate attempted case")
    cases, runtimes = {}, []
    for cid in ids:
        require(Path(cid).name == cid, "invalid case filename")
        alias = "acquisition/cases/" + cid + ".json"
        rec = json.loads(read(acquisition_summary.parent / "cases" / (cid + ".json"), alias))
        require(rec["case_id"] == cid, "case identity mismatch")
        mode = rec["mode"]
        expected = tracking["modes"][mode]["acquisition_cases_inspected_at_their_data_time"]
        require(pins[alias] == expected[cid], "original case SHA mismatch: " + cid)
        cases[cid] = rec
        if rec["search_called"]:
            cert = rec["search"]["certificate"]
            seconds = float(cert["elapsed_s"])
            necessary_condition(0, seconds, 0)
            runtimes.append(dict(mode=mode, case_id=cid, certificate_elapsed_s=seconds,
                over_1s=seconds > 1, over_2s=seconds > 2, globally_certified=cert["global_optimum_certified"],
                termination_reason=cert["termination_reason"], original_status=rec["status"]))
    stats, checks, origins, outputs, candidates = {}, {}, [], [], []
    for mode, ms in tracking["modes"].items():
        subset = [r for r in runtimes if r["mode"] == mode]
        values = [r["certificate_elapsed_s"] for r in subset]
        require(values, "no recorded searches")
        stats[mode] = dict(n=len(values), globally_certified=sum(r["globally_certified"] for r in subset),
            termination_counts=dict(collections.Counter(r["termination_reason"] for r in subset)),
            mean_s=sum(values)/len(values), over_1s_n=sum(x > 1 for x in values),
            over_1s_fraction=sum(x > 1 for x in values)/len(values), over_2s_n=sum(x > 2 for x in values),
            over_2s_fraction=sum(x > 2 for x in values)/len(values),
            quantiles_s={f"p{p:02d}":quantile(values, p/100) for p in (0,10,25,50,75,90,95,99,100)})
        event_name, csv_name = mode.upper()+"_EVENTS.jsonl", "CARRIER_TRACKED_"+mode.upper()+".csv"
        events = [json.loads(line) for line in read(tracking_summary.parent/event_name, "tracking/"+event_name).decode().splitlines()]
        table = list(csv.DictReader(read(tracking_summary.parent/csv_name, "tracking/"+csv_name).decode().splitlines()))
        require(len(events) == len(table) == ms["epochs"], "epoch-count disagreement")
        require(all(float(e["time_s"]) == float(e["measurement"]["measurement_time"]) for e in events), "event/measurement-time disagreement")
        valid = [e for e in events if e["measurement"]["valid"]]
        times = [float(e["measurement"]["measurement_time"]) for e in valid]
        require(times == [float(r["measurement_time"]) for r in table if r["valid"] == "1"] == ms["valid_times_s"],
                "event/CSV/summary valid-time disagreement")
        require(len(valid) == ms["valid_experimental_measurements"], "valid-count disagreement")
        starts = [e for e in events if e["event"] == "TRACK_STARTED"]
        require([{k:e[k] for k in ("case_id","origin_id","time_s")} for e in starts] == ms["origins"], "origin-list disagreement")
        start_map = {e["case_id"]:e for e in starts}
        require(len(start_map) == len(starts), "duplicate origin case")
        suppressed = collections.Counter(cid for e in events for cid in e.get("suppressed_valid_origins", []))
        valid_cases = {cid:r for cid,r in cases.items() if r["mode"] == mode and r.get("measurement", {}).get("valid")}
        require(set(valid_cases) == set(start_map) | set(suppressed), "unaccounted acquisition candidates")
        require(not set(start_map) & set(suppressed), "origin started and suppressed")
        require(len(valid_cases) == acquisition["modes"][mode]["valid_experimental_measurements"], "acquisition count disagreement")
        for cid, rec in valid_cases.items():
            selected = {float(c["selected_at"]) for c in rec["frozen_candidates"]}
            require(len(selected) == 1, "candidate selected_at mismatch")
            selected = selected.pop()
            elapsed = float(rec["search"]["certificate"]["elapsed_s"])
            initial = float(rec["measurement"]["measurement_time"])
            completion, initial_ok, _ = necessary_condition(selected, elapsed, initial)
            require(rec["search"]["certificate"]["global_optimum_certified"], "valid candidate without certificate")
            candidates.append(dict(case_id=cid, original_selected_at_s=selected, certificate_elapsed_s=elapsed,
                ideal_search_completion_s=completion, original_acquisition_export_time_s=initial,
                initial_export_necessary_condition_met=initial_ok,
                original_tracking_disposition="STARTED" if cid in start_map else "SUPPRESSED_BY_INCUMBENT"))
            if cid not in start_map:
                continue
            start = start_map[cid]
            oid = start["origin_id"]
            require(initial == float(start["measurement"]["measurement_time"]), "origin time mismatch")
            releases = [e for e in events if e["event"] == "TRACK_RELEASED" and e["origin_id"] == oid]
            require(len(releases) <= 1, "duplicate release")
            release = float(releases[0]["time_s"]) if releases else None
            relevant = [e for e in valid if e["origin_id"] == oid]
            require(relevant and all(e["time_s"] >= initial and (release is None or e["time_s"] < release)
                    for e in relevant), "output outside original lifetime")
            passed = 0
            for event in relevant:
                t = float(event["measurement"]["measurement_time"])
                _, ok, slack = necessary_condition(selected, elapsed, t)
                passed += ok
                outputs.append(dict(case_id=cid, origin_id=oid, event=event["event"],
                    original_selected_at_s=selected, certificate_elapsed_s=elapsed, ideal_search_completion_s=completion,
                    original_measurement_time_s=t, original_decision_available_time_s=event["measurement"]["decision_available_time"],
                    necessary_condition_met=ok, slack_s=slack))
            origins.append(dict(case_id=cid, origin_id=oid, original_selected_at_s=selected,
                certificate_elapsed_s=elapsed, ideal_search_completion_s=completion, initial_export_time_s=initial,
                initial_export_necessary_condition_met=initial_ok, last_valid_output_time_s=max(e["time_s"] for e in relevant),
                first_release_time_s=release, release_status=releases[0]["measurement"]["status"] if releases else "ACTIVE_AT_END",
                original_valid_outputs=len(relevant), necessary_condition_met_outputs=passed,
                completion_at_or_after_first_release=(completion >= release) if releases else None))
        checks[mode] = dict(event_and_csv_rows=len(events), original_valid_outputs=len(valid),
            origin_count=len(starts), acquisition_valid_candidates=len(valid_cases),
            suppressed_candidates=sum(suppressed.values()), summary_event_csv_agreement=True)
    require(len(outputs) == sum(x["original_valid_outputs"] for x in checks.values()), "unattributed output")
    summary = dict(label=label, formula="measurement_time >= original_selected_at + search.certificate.elapsed_s",
        interpretation="Necessary only: recorded runtime, immediate launch, zero queue and zero other overhead. Not a computed real-time schedule.",
        source_runtime_field="search.certificate.elapsed_s", total_case_elapsed_s_used=False, source_mutations=False,
        new_CILS_calls=0, new_native_calls=0, reference_reads=0, revalidation_calls=0,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        original_wall_clock_latency_charged=tracking["wall_clock_acquisition_latency_charged"],
        runtime_statistics=stats, original_tracking_crosschecks=checks, original_acquisition_valid_candidates=len(candidates),
        original_started_origins=len(origins), original_valid_outputs=len(outputs),
        necessary_condition_met_outputs=sum(r["necessary_condition_met"] for r in outputs),
        initial_exports_necessary_condition_met=sum(r["initial_export_necessary_condition_met"] for r in origins),
        candidate_exports_necessary_condition_met=sum(r["initial_export_necessary_condition_met"] for r in candidates),
        origins=origins, source_sha256=pins,
        origins_expired_by_ideal_completion=sum(r["completion_at_or_after_first_release"] is True for r in origins),
        late_origins_with_some_passing_outputs=sum(not r["initial_export_necessary_condition_met"] and r["necessary_condition_met_outputs"] > 0 for r in origins),
        original_release_status_counts=dict(collections.Counter(r["release_status"] for r in origins)))
    output_dir.mkdir(parents=True)
    for name, rows in (("SEARCH_RUNTIMES.csv",runtimes), ("CANDIDATE_LATENCY.csv",candidates),
                       ("ORIGIN_LATENCY.csv",origins), ("OUTPUT_NECESSARY_CONDITIONS.csv",outputs)):
        if rows:
            with (output_dir/name).open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
    (output_dir/"SUMMARY.json").write_text(json.dumps(summary, indent=2)+"\n")
    (output_dir/"REPORT.md").write_text(report(summary))
    return summary


def report(s):
    lines = [f'# {s["label"]}: recorded-search latency necessary condition', "",
        "Read-only saved-record calculation: no AR, navigation, revalidation or reference reads. "
        "Original selected_at, N, owners, release times and retrospective outcomes remain unchanged.", "",
        "**Test:** measurement_time >= original_selected_at + search.certificate.elapsed_s. "
        "Use certificate search wall-clock time, not total frontend elapsed. Assume immediate launch at original selection time, "
        "zero queue and zero other overhead. This is an optimistic necessary condition for recorded durations, "
        "not a computed real-time schedule or a new valid-measurement result.", "",
        f'Acquisition candidates: {s["original_acquisition_valid_candidates"]}; started origins: {s["original_started_origins"]}; '
        f'original valid outputs: {s["original_valid_outputs"]}. Necessary-condition passes: '
        f'**{s["necessary_condition_met_outputs"]}/{s["original_valid_outputs"]} outputs**. '
        f'First-export passes among started origins: {s["initial_exports_necessary_condition_met"]}/{s["original_started_origins"]}. '
        f'Acquisition-export passes including suppressed candidates: {s["candidate_exports_necessary_condition_met"]}/'
        f'{s["original_acquisition_valid_candidates"]}.', "",
        f'Origins already released by ideal completion: {s["origins_expired_by_ideal_completion"]}. '
        f'Late origins with later passing outputs: {s["late_origins_with_some_passing_outputs"]}. '
        f'Original release counts: {s["original_release_status_counts"]}.', "",
        "## Original started origins", "",
        "| Case | Selected_at | Search s | Ideal completion | First export | Last valid | First release | Original outputs | Passes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in s["origins"]:
        release = f'{r["first_release_time_s"]:.6f}' if r["first_release_time_s"] is not None else "NA"
        lines.append(f'| {r["case_id"]} | {r["original_selected_at_s"]:.6f} | {r["certificate_elapsed_s"]:.6f} | '
            f'{r["ideal_search_completion_s"]:.6f} | {r["initial_export_time_s"]:.6f} | {r["last_valid_output_time_s"]:.6f} | '
            f'{release} | {r["original_valid_outputs"]} | {r["necessary_condition_met_outputs"]} |')
    lines += ["", "## All recorded searches", "",
        "Modes stay separate. Timeout records are included; no conditioning on certification or acceptance. "
        "Quantiles interpolate linearly at (n-1)*p; over-1/2-second counts use strict >.", "",
        "| Mode | n | Certified | Min | p25 | Median | p75 | p90 | p95 | p99 | Max | >1 s | >2 s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for mode, v in s["runtime_statistics"].items():
        cells = [mode,str(v["n"]),str(v["globally_certified"])]
        cells += [f'{v["quantiles_s"][f"p{p:02d}"]:.6f}' for p in (0,25,50,75,90,95,99,100)]
        cells += [f'{v["over_1s_n"]}/{v["n"]} ({v["over_1s_fraction"]:.2%})',
                  f'{v["over_2s_n"]}/{v["n"]} ({v["over_2s_fraction"]:.2%})']
        lines.append("| "+" | ".join(cells)+" |")
    lines += ["", "## Boundaries and reproduction", "",
        "Passing does not newly admit a measurement. We do not reschedule owners, promote suppressed candidates, "
        "recreate missed validation, shift measurement time, or revive released origins. An origin whose ideal completion "
        "is after its original release is already expired. Even later passing outputs do not prove an implementable delayed pipeline.", "",
        "Durations are one-run workstation observations, not worst-case execution times or universal lower bounds for optimized code. "
        "Queueing, preparation, screening, export and navigation add uncounted delay under the stated model. "
        "Integer truth and lifetime false-fix probability remain unavailable. Original retrospective metrics are not replaced.", "",
        "Acquisition-summary SHA and every original case SHA are checked against tracking pins. "
        "Event/CSV/summary valid times and started-origin lists agree. Tables contain no raw observation payloads.", "",
        "Run the standard-library-only companion script with the original saved acquisition summary and a new output directory:", "",
        "    python3 diagnose_solver_latency.py --acquisition-summary FRONTEND/SUMMARY.json "
        "--tracking-summary TRACKING/SUMMARY.json --output-dir NEW_OUTPUT --label LABEL", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition-summary", type=Path, required=True)
    parser.add_argument("--tracking-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    s = diagnose(args.acquisition_summary, args.tracking_summary, args.output_dir, args.label)
    keys = ("label","original_acquisition_valid_candidates","original_started_origins","original_valid_outputs",
            "necessary_condition_met_outputs","initial_exports_necessary_condition_met",
            "candidate_exports_necessary_condition_met","runtime_statistics")
    print(json.dumps({k:s[k] for k in keys}, indent=2))


if __name__ == "__main__":
    main()
