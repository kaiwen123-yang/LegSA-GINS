#!/usr/bin/env python3
"""Read only sealed six-run outputs; never import a solver or open reference.

Primary full-window metrics use frozen evaluator rows vs immutable V3 facts.
Actual matched-time intersections are separate diagnostics, without interpolation.
Events use the union of V3 actual matched keys and the new actual NAV keys;
missing output/error keys interrupt stable confirmation. No nominal 500 Hz grid.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SEQUENCES = ("BY2", "BY2H", "BY2O")
ARMS = ("PVT_CONTROL", "CARRIER_FALLBACK")
CHANNELS = {"yaw": ("yaw_err_deg", 2.), "horizontal": ("horizontal_err_m", 2.),
            "up": ("err_u_m", 3.)}
METRICS = ("yaw_rmse_deg", "yaw_p95_absolute_deg", "yaw_p99_absolute_deg",
           "horizontal_rmse_m", "horizontal_p95_m", "horizontal_p99_m",
           "up_rmse_m", "up_p95_absolute_m", "up_p99_absolute_m")
MAXIMA = ("yaw_max_absolute_deg", "horizontal_max_m", "up_max_absolute_m")
NA = None
V3_LOCK_SHA256 = "d961acfd483c420e24e5b48f0b313cbac5932ef7a036a21ffe5a00dd742a09ff"
V3_FACTS_SHA256 = "ead96647f27d9c97182487311ebd23f48553fbac86f972e4e02a0c935916de98"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def read_csv(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(value):
    if value in (None, "", "NA"):
        return None
    result = float(value)
    require(math.isfinite(result), "Nonfinite metric; do not silently drop")
    return result


def strict_times(values):
    a = np.asarray(values, dtype=float)
    require(a.ndim == 1 and np.isfinite(a).all(), "Invalid time keys")
    require(len(a) < 2 or np.all(np.diff(a) > 0), "Time keys must be unique increasing")
    return a


def errors_from_rows(rows):
    out = {"time": strict_times([float(r["time"]) for r in rows])}
    for _, (column, _) in CHANNELS.items():
        out[column] = np.asarray([float(r[column]) for r in rows], dtype=float)
        require(np.isfinite(out[column]).all(), "Nonfinite error; no metric-driven deletion")
    require(np.all(out["horizontal_err_m"] >= 0), "Horizontal norm must be nonnegative")
    # Frozen errors are already wrapped; allow only the boundary equivalent.
    require(np.all(np.abs(out["yaw_err_deg"]) <= 180.000000001), "Non-wrap-safe yaw errors")
    out["yaw_err_deg"] = (out["yaw_err_deg"] + 180.) % 360. - 180.
    return out


def empty_errors():
    return errors_from_rows([])


def subset_errors(errors, keys):
    keys = strict_times(keys)
    index = np.searchsorted(errors["time"], keys)
    require(np.all(index < len(errors["time"])) and
            np.array_equal(errors["time"][index], keys), "Exact keys required; interpolation forbidden")
    return {k: v[index] for k, v in errors.items()}


def common_errors(left, right):
    keys = np.intersect1d(left["time"], right["time"], assume_unique=True)
    return subset_errors(left, keys), subset_errors(right, keys)


def metrics(errors):
    if not len(errors["time"]):
        return {k: None for k in METRICS + MAXIMA}
    out = {}
    for channel, (column, _) in CHANNELS.items():
        values = np.abs(errors[column])
        unit = "deg" if channel == "yaw" else "m"
        suffix = "_absolute" if channel in ("yaw", "up") else ""
        out[f"{channel}_rmse_{unit}"] = float(np.sqrt(np.mean(values * values)))
        for percentile in (95, 99):
            out[f"{channel}_p{percentile}{suffix}_{unit}"] = float(np.percentile(values, percentile))
        out[f"{channel}_max{suffix}_{unit}"] = float(np.max(values))
    return out


def tolerance(key, baseline):
    floor = .02 if key.startswith("yaw_") else .0005 if "_rmse_" in key else .001
    return max(floor, .01 * baseline)


def comparison_row(sequence, arm, support, current, baseline, count=None):
    out = {"sequence_id": sequence, "arm": arm, "support": support, "matched_count": count}
    flags = []
    for key in METRICS:
        x, b = number(current.get(key)), number(baseline.get(key))
        limit = None if b is None else b + tolerance(key, b)
        passed = None if x is None or b is None else x <= limit
        flags.append(passed)
        out.update({key: x, "v3_" + key: b,
                    "delta_" + key: None if x is None or b is None else x - b,
                    "limit_" + key: limit, "nondegraded_" + key: passed})
    for key in MAXIMA:
        x, b = number(current.get(key)), number(baseline.get(key))
        out.update({key: x, "v3_" + key: b,
                    "delta_" + key: None if x is None or b is None else x - b})
    out["all_metric_nondegraded"] = False if False in flags else None if None in flags else True
    b, x = number(baseline.get("yaw_rmse_deg")), number(current.get("yaw_rmse_deg"))
    out["yaw_rmse_relative_reduction"] = (b-x)/b if b is not None and x is not None and b > 0 else None
    return out


def contract_gate(rows, coverage):
    """Only fallback/full-window rows count for contract A/B, never pooled means."""
    by_seq = {r["sequence_id"]: r for r in rows if r["arm"] == "CARRIER_FALLBACK"
              and r["support"] == "FULL_AVAILABLE_FROZEN"}
    complete = set(by_seq) == set(SEQUENCES)
    values = [by_seq[s]["all_metric_nondegraded"] for s in SEQUENCES] if complete else [None]
    covs = [coverage.get(s) for s in SEQUENCES]
    nondeg = False if False in values + covs else None if None in values + covs else True
    count = sum(r.get("yaw_rmse_relative_reduction") is not None and
                r["yaw_rmse_relative_reduction"] >= .05 for r in by_seq.values())
    gate_a = None if nondeg is None else bool(nondeg and count >= 2)
    return {"all_sequence_nondegradation": nondeg, "A": gate_a,
            "A_sequences_at_least_5_percent_yaw_rmse_reduction": count,
            "B": None, "B_reason": "NO_REGISTERED_RAW_CARRIER_FAULT_RECOVERY_CASES",
            "recommend_for_human_review_under_this_contract": bool(gate_a),
            "failure_or_missing_is_not_a_zero_metric": True,
            "reference_is_independent_truth": False,
            "integer_correctness": None, "false_fix_probability": None,
            "velocity_truth_metrics": None, "main_replacement_authorized": False}


def event_summary(grid, errors, channel, window):
    """Count contiguous exceedance runs; each awaits its first later stable 1 s.

    A renewed exceedance before recovery is a new contiguous run; both pending
    runs can share a later confirmation. Missing slots break a run and stable
    confirmation, but do not assert recovery or erase pending events.
    """
    grid = strict_times(grid)
    times = errors["time"]
    column, threshold = CHANNELS[channel]
    require(len(grid) == 0 or (grid[0] >= window[0] and grid[-1] <= window[1]), "Grid outside window")
    require(np.isin(times, grid).all(), "Error key absent from observation grid")
    lookup = dict(zip(times.tolist(), np.abs(errors[column]).tolist()))
    events, pending, active = [], [], None
    good_since = None
    missing_runs, missing = [], None
    for t in grid.tolist():
        value = lookup.get(t)
        if value is None:
            if missing is None:
                missing = {"first_missing_key_s": t, "last_missing_key_s": t, "slots": 0}
                missing_runs.append(missing)
            missing["last_missing_key_s"] = t
            missing["slots"] += 1
            active = None
            good_since = None
            continue
        missing = None
        if value > threshold:
            good_since = None
            if active is None:
                active = {"start_s": t, "last_exceedance_s": t, "exceedance_samples": 0,
                          "confirmation_s": None, "time_from_start_to_confirmation_s": None,
                          "right_censored": True}
                events.append(active)
                pending.append(active)
            active["last_exceedance_s"] = t
            active["exceedance_samples"] += 1
        else:
            active = None
            if good_since is None:
                good_since = t
            if t - good_since >= 1. - 2e-12:
                for item in pending:
                    item.update(confirmation_s=t, time_from_start_to_confirmation_s=t-item["start_s"],
                                right_censored=False)
                pending = []
    for missing_run in missing_runs:
        first = np.searchsorted(grid, missing_run["first_missing_key_s"])
        last = np.searchsorted(grid, missing_run["last_missing_key_s"])
        left = float(grid[first-1]) if first else float(window[0])
        right = float(grid[last+1]) if last+1 < len(grid) else float(window[1])
        missing_run.update(left_available_boundary_s=left, right_available_boundary_s=right,
                           gap_bracket_s=right-left)
    return {"channel": channel, "threshold": threshold, "threshold_equality_is_exceedance": False,
            "event_count": len(events), "no_exceedance_observed": not events,
            "recovery_status": "NO_EXCEEDANCE_OBSERVED" if not events else
                               "RIGHT_CENSORED_PRESENT" if pending else "ALL_CONFIRMED",
            "right_censored_count": sum(e["right_censored"] for e in events),
            "events": events, "missing_runs": missing_runs,
            "missing_slot_count": sum(x["slots"] for x in missing_runs),
            "longest_missing_key_gap_bracket_s": max((x["gap_bracket_s"] for x in missing_runs), default=0.),
            "missing_duration_is_bracket_not_continuous_observation_proof": True,
            "last_supported_error_time_s": float(times[-1]) if len(times) else None,
            "window_end_s": window[1],
            "recovery_is_navigation_error_recovery_not_AR_reacquisition": True}


def checked_artifact(pin, stage, cache):
    path = Path(pin["path"])
    if not path.is_absolute():
        path = stage / path
    path = path.resolve()
    require(stage == path or stage in path.parents, "New output outside registered stage")
    if path not in cache:
        cache[path] = digest(path)
    require(cache[path] == pin["sha256"], "Output identity changed: " + str(path))
    return path


def nav_times(path):
    values = []
    with path.open() as stream:
        for line in stream:
            if line.strip() and not line.lstrip().startswith(("#", "%")):
                tokens = line.split()
                require(len(tokens) == 11, "Expected 11-column NAV")
                values.append(float(tokens[1]))
    return strict_times(values)


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "NA" if v is None else v for k, v in row.items()})


def run(args):
    stage = Path(args.stage).resolve()
    lock_path = ROOT / "docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json"
    facts_path = ROOT / "docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_METRICS.csv"
    require(digest(lock_path) == V3_LOCK_SHA256 and digest(facts_path) == V3_FACTS_SHA256,
            "Original V3 lock/facts bytes changed")
    lock = read_json(lock_path)
    facts = {x["sequence_id"]: x for x in read_csv(facts_path)}
    require(set(facts) == set(SEQUENCES), "Original V3 facts identity")
    spec = {x["sequence_id"]: x for x in lock["sequences"]}
    cache = {}
    native_path, evaluation_path = stage/"ALL_NATIVE_SEALED.json", stage/"EVALUATION_COMPLETE.json"
    native, evaluation = read_json(native_path), read_json(evaluation_path)
    require(evaluation["native_seal_sha256"] == digest(native_path), "Native seal chain mismatch")
    require(evaluation["plan_sha256"] == native["plan_sha256"] == digest(stage/"PLAN.json"),
            "Plan chain mismatch")
    require(native["status"] == "SEALED" and evaluation["status"] == "COMPLETE",
            "Incomplete run cannot supply adopted metrics")
    native_rows = {x["run_id"]: x for x in native["records"]}
    evaluation_rows = {x["run_id"]: x for x in evaluation["records"]}
    expected = {s+"__"+a for s in SEQUENCES for a in ARMS}
    require(set(native_rows) == set(evaluation_rows) == expected and
            len(native["records"]) == len(evaluation["records"]) == 6, "Preserve all six registered runs")
    for manifest in (native, evaluation):
        for rel, h in manifest["files"].items():
            # The complete seal itself is not included in its own files map.
            checked_artifact({"path": rel, "sha256": h}, stage, cache)
    old, new, summaries = {}, {}, {}
    comparisons, coverage, event_records, matched_controls = [], [], [], []
    inputs = {"v3_lock_sha256": digest(lock_path), "v3_facts_sha256": digest(facts_path),
              "native_seal_sha256": digest(native_path), "evaluation_complete_sha256": digest(evaluation_path)}
    for sequence in SEQUENCES:
        s = spec[sequence]
        require(facts[sequence]["source_result_sha256"] == s["evaluation"]["result"]["sha256"],
                "V3 facts/result identity mismatch")
        pin = s["evaluation"]["retained_error_series"]
        old_path = Path(pin["path"].replace("<V3_ROOT>", str(Path(args.v3_root).resolve())))
        require(digest(old_path) == pin["sha256"], "Old retained error series identity mismatch")
        old[sequence] = errors_from_rows(read_csv(old_path))
        require(len(old[sequence]["time"]) == int(facts[sequence]["matched_epoch_count"]), "V3 support count")
        event_records.append({"run_id": s["run_id"], "sequence_id": sequence, "arm": "ORIGINAL_V3",
            "support": "FULL_OLD_MATCHED_KEYS",
            "channels": [event_summary(old[sequence]["time"], old[sequence], c, s["full_window_s"])
                         for c in CHANNELS]})
        for arm in ARMS:
            run_id = sequence+"__"+arm
            n, e = native_rows[run_id], evaluation_rows[run_id]
            require(n["sequence_id"] == e["sequence_id"] == sequence and n["arm"] == e["arm"] == arm,
                    "Run identity mismatch")
            nav = checked_artifact(n["nav"], stage, cache) if n.get("nav") else None
            nt = nav_times(nav) if nav else np.array([], float)
            if nav:
                require(len(nt) == n["output_rows"], "Native count mismatch")
                require(hashlib.sha256(np.asarray(nt, dtype="<f8").tobytes(order="C")).hexdigest()
                        == n["time_keys_sha256"], "Native time-key hash mismatch")
            require(len(nt) == 0 or (nt[0] >= s["full_window_s"][0] and
                    nt[-1] <= s["full_window_s"][1]), "Native outside full window")
            result = read_json(checked_artifact(e["result"], stage, cache))
            row = result.get("row", {})
            require(row["run_id"] == run_id and row["sequence_id"] == sequence and row["arm"] == arm,
                    "Evaluator row identity mismatch")
            epin = e.get("error_series")
            if epin:
                require(result["audit"]["passed"] is True and row["evaluation_status"] == "COMPLETED",
                        "Unqualified evaluator result cannot supply metrics")
                require(result.get("error_series") == epin, "Evaluator error payload identity mismatch")
                transform, capture = result["transform"], result["capture"]
                require(transform["baseline_median_m"] == s["evaluation"]["baseline_median_m"] and
                        transform["changed_columns_zero_based"] == [2, 3, 4] and
                        transform["std_transformed"] is False, "Physical evaluation point changed")
                require(capture["trace_sha256"] == s["evaluation"]["reference"]["sha256"],
                        "Reference identity metadata changed")
                require(row["evaluator_sha256"] == lock["evaluator"]["sha256"] and
                        row["evaluator_contract"] == "evaluator_contract_v3",
                        "Frozen evaluator changed")
                require(n["status"] == "COMPLETED" and row["metrics_admitted"] is True and
                        row["source_nav_sha256"] == n["nav"]["sha256"] and
                        row["std_sha256"] == n["std"]["sha256"],
                        "Evaluator source NAV/STD or completed status mismatch")
                errors = errors_from_rows(read_csv(checked_artifact(epin, stage, cache)))
                require(np.isin(errors["time"], nt).all(), "Matched evaluator keys not in native output")
                require(len(errors["time"]) == int(row["matched_epoch_count"]), "Evaluation count mismatch")
            else:
                errors = empty_errors()
                # No matching payload means no numeric claim, even if a stale
                # summary happens to contain metric-looking values.
                row = {}
            new[run_id], summaries[run_id] = errors, row
            native_missing = np.setdiff1d(old[sequence]["time"], nt, assume_unique=True)
            error_missing = np.setdiff1d(old[sequence]["time"], errors["time"], assume_unique=True)
            old_complete = int(facts[sequence]["unmatched_epoch_count"]) == 0
            cov = {"run_id": run_id, "sequence_id": sequence, "arm": arm,
                "native_status": n["status"], "native_output_rows": len(nt),
                "matched_error_rows": len(errors["time"]), "unmatched_native_rows": len(nt)-len(errors["time"]),
                "initial_output_gap_s": float(nt[0]-s["full_window_s"][0]) if len(nt) else None,
                "terminal_output_gap_s": float(s["full_window_s"][1]-nt[-1]) if len(nt) else None,
                "longest_between_output_sample_s": float(np.max(np.diff(nt))) if len(nt)>1 else None,
                "matched_per_native_output": len(errors["time"])/len(nt) if len(nt) else None,
                "v3_actual_matched_keys": len(old[sequence]["time"]),
                "missing_v3_actual_keys_in_new_native": len(native_missing),
                "missing_v3_actual_keys_in_new_errors": len(error_missing),
                "extra_new_native_keys": len(np.setdiff1d(nt, old[sequence]["time"], assume_unique=True)),
                "v3_grid_is_complete_old_output": old_complete,
                "coverage_nondegraded": bool(not len(native_missing) and not len(error_missing) and nav and epin)
                    if old_complete else None,
                "absolute_heading_available_coverage": None,
                "absolute_heading_coverage_reason": "NO_REGISTERED_DURATION_DENOMINATOR; propagation is not measurement availability",
                "heading_counts": json.dumps(n.get("heading_counts"), sort_keys=True),
                "integer_accuracy": None, "velocity_truth_rmse": None}
            coverage.append(cov)
            comparisons.append(comparison_row(sequence, arm, "FULL_AVAILABLE_FROZEN", row, facts[sequence], len(errors["time"])))
            left, right = common_errors(old[sequence], errors)
            comparisons.append(comparison_row(sequence, arm, "COMMON_V3_MATCHED_EXACT_KEYS",
                                               metrics(right), metrics(left), len(left["time"])))
            grid = np.union1d(old[sequence]["time"], nt)
            event_records.append({"run_id": run_id, "sequence_id": sequence, "arm": arm,
                "support": "UNION_OF_ACTUAL_OLD_MATCHED_AND_NEW_NATIVE_KEYS",
                "channels": [event_summary(grid, errors, c, s["full_window_s"]) for c in CHANNELS]})
        c_id, f_id = sequence+"__PVT_CONTROL", sequence+"__CARRIER_FALLBACK"
        c, f = common_errors(new[c_id], new[f_id])
        for support, cm, fm, count in (
                ("FULL_AVAILABLE_FROZEN", summaries[c_id], summaries[f_id], None),
                ("COMMON_CONTROL_FALLBACK_EXACT_KEYS", metrics(c), metrics(f), len(c["time"]))):
            r = {"sequence_id": sequence, "support": support, "matched_count": count}
            for key in METRICS + MAXIMA:
                cv, fv = number(cm.get(key)), number(fm.get(key))
                r.update({"control_"+key: cv, "fallback_"+key: fv,
                          "fallback_minus_control_"+key: None if cv is None or fv is None else fv-cv})
            matched_controls.append(r)
    gate = contract_gate(comparisons, {r["sequence_id"]: r["coverage_nondegraded"] for r in coverage
                                      if r["arm"] == "CARRIER_FALLBACK"})
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output/"V3_COMPARISONS.csv", comparisons)
    write_csv(output/"MATCHED_CONTROL_DIFFERENCES.csv", matched_controls)
    write_csv(output/"COVERAGE.csv", coverage)
    result = {"schema": "trusted_heading.full_navigation_comparison.v1", "inputs": inputs,
              "comparator_source_sha256": digest(Path(__file__)) ,
              "gate": gate, "events": event_records, "reference_reads": 0,
              "solver_calls": 0, "evaluator_calls": 0, "scope": "DERIVED_SEALED_EVALUATION_ONLY",
              "common_support_not_a_substitute_for_full_window_adoption": True,
              "conditional_or_propagated_heading_not_counted_as_trusted_FIX": True}
    (output/"COMPARISON.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for name in ("stage", "v3-root", "out"):
        ap.add_argument("--"+name, required=True)
    run(ap.parse_args())
