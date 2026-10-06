#!/usr/bin/env python3
"""One fixed V3 body-input audit. Never reads GNSS, reference or navigation data."""
from __future__ import annotations
import argparse
from collections import Counter, deque
from dataclasses import asdict, dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback
import numpy as np

CODE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CODE / "src"))
from legsa_gins.paper_rebuild.body_velocity import iter_messages, STAMP, ERROR
from legsa_gins.paper_rebuild.horizontal_literature.hartley_h5 import (
    _parse_allowed_record, _rotation_x_minus_one_degree, H5_SENSOR_TO_BODY_ROLL_DEG,
    HartleyH5Error,
)
from legsa_gins.paper_rebuild.horizontal_literature.hartley_h0_h2 import (
    NATIVE_FOOT_ORDER, FROZEN_CONTACT_ON_THRESHOLDS, FROZEN_CONTACT_OFF_THRESHOLDS,
    IMU_INSTALL_RPY_DEG,
)
from legsa_gins.paper_rebuild.carrier_phase.support_arcs import (
    SupportArcTracker, SupportPolicy, FootForceThreshold, SupportArcError,
)
from legsa_gins.paper_rebuild.carrier_phase.contact_rotation import (
    FootPositionEpoch, estimate_contact_rotation,
)

DOCS = CODE / "docs/paper_rebuild/TRUSTED_HEADING_20261006"
LOCK = CODE / "docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json"
SOURCES = (
    "scripts/paper_rebuild/carrier_phase/trusted_heading_body_proxy_audit.py",
    "src/legsa_gins/paper_rebuild/body_velocity.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h0_h2.py",
    "src/legsa_gins/paper_rebuild/carrier_phase/support_arcs.py",
    "src/legsa_gins/paper_rebuild/carrier_phase/contact_rotation.py",
    "docs/paper_rebuild/TRUSTED_HEADING_20261006/BODY_PROXY_AUDIT_PLAN.md",
)
WINDOWS = {"BY2": [66., 340.], "BY2H": [413., 683.], "BY2O": [3186., 3563.]}
PERIOD_NS = 100_000_000
MAX_GAP_NS = 50_000_000
MAX_INTERVAL_NS = 150_000_000
DWELL_S = .0120356083
CSV_FIELDS = (
    "sequence", "grid_time_s", "current_source_time_s", "source_age_s",
    "previous_source_time_s", "actual_dt_s", "status", "rank", "usable_foot_count",
    "usable_feet", "support_states", "interval_continuity", "nullspace_frd_json",
    "observable_basis_frd_json", "minimum_norm_cayley_rate_rad_s_json",
    "observed_geometry_condition", "gyro_status", "gyro_interval_samples",
    "gyro_principal_rotation_angle_rad", "observable_cayley_difference_norm_rad_s",
    "observable_cayley_increment_difference_norm", "source_fault",
)
FAULT_FIELDS = ("sequence", "message_index", "relative_time_s", "scope", "reason")
EVENT_FIELDS = ("sequence", "source_time_s", "foot", "state_before", "state_after",
                "new_episode", "retired_episode", "reasons")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf8")


def writer(path, fields):
    handle = Path(path).open("w", encoding="utf8", newline="")
    out = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    out.writeheader()
    return handle, out


def compact(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def resolve(aliased, aliases):
    for token, base in sorted(aliases.items(), key=lambda item: -len(item[0])):
        if aliased == token or aliased.startswith(token + "/"):
            return Path(base) / aliased[len(token):].lstrip("/")
    raise ValueError("Unresolved path alias: " + aliased)


def statistics(values):
    a = np.asarray(values, dtype=float)
    if a.size == 0:
        return {"count": 0}
    if not np.all(np.isfinite(a)):
        raise ValueError("nonfinite summary values must not be silently dropped")
    return {"count": int(a.size), "min": float(np.min(a)),
            "p50": float(np.quantile(a, .5)), "p90": float(np.quantile(a, .9)),
            "p99": float(np.quantile(a, .99)), "max": float(np.max(a)),
            "mean": float(np.mean(a))}


def rotation_exp(vector):
    angle = float(np.linalg.norm(vector))
    if angle == 0.:
        return np.eye(3)
    axis = vector / angle
    x, y, z = axis
    k = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def rotation_to_cayley_rate(rotation, dt):
    # R is body1-to-body0. Reject the principal pi singularity; do not unwrap.
    system = rotation + np.eye(3)
    if np.linalg.cond(system) > 1e10:
        raise ValueError("GYRO_PRINCIPAL_PI_SINGULARITY")
    cross = 2. / dt * np.linalg.solve(system.T, (rotation - np.eye(3)).T).T
    w = np.array([cross[2, 1], cross[0, 2], cross[1, 0]])
    skew_part = .5 * (rotation - rotation.T)
    sin_angle = np.linalg.norm([skew_part[2, 1], skew_part[0, 2], skew_part[1, 0]])
    cos_angle = (np.trace(rotation) - 1.) * .5
    angle = math.atan2(float(sin_angle), float(cos_angle))
    if not np.all(np.isfinite(w)):
        raise ValueError("NONFINITE_GYRO_CAYLEY_RATE")
    return w, angle


def self_check():
    v = np.array([.07, -.03, .09])
    dt = .1
    r = rotation_exp(v)
    w, angle = rotation_to_cayley_rate(r, dt)
    expected = 2 * math.tan(np.linalg.norm(v) / 2) * v / np.linalg.norm(v) / dt
    np.testing.assert_allclose(w, expected, atol=1e-14)
    np.testing.assert_allclose(angle, np.linalg.norm(v), atol=1e-14)
    np.testing.assert_allclose(r.T @ r, np.eye(3), atol=1e-14)
    a, b = np.array([.03, 0., 0.]), np.array([0., .04, 0.])
    assert np.linalg.norm(rotation_exp(a) @ rotation_exp(b) -
                          rotation_exp(b) @ rotation_exp(a)) > 1e-3
    assert list(NATIVE_FOOT_ORDER) == ["FR", "FL", "RR", "RL"]
    assert tuple(IMU_INSTALL_RPY_DEG) == (-1., 0., 0.)
    assert H5_SENSOR_TO_BODY_ROLL_DEG == -1.
    assert sum(round((v[1] - v[0]) * 10) + 1 for v in WINDOWS.values()) == 9213
    synthetic_tracker = SupportArcTracker(SupportPolicy(tuple(
        FootForceThreshold(foot, 30., 20.) for foot in NATIVE_FOOT_ORDER), .01, .05),
        stream_id="self-check")
    synthetic_samples = deque()
    positions = np.array([[.3,.2,.4],[.3,-.2,.4],[-.3,.2,.4],[-.3,-.2,.4]])
    for index in range(31):
        ns = index * 5_000_000
        support = synthetic_tracker.update(ns * 1e-9, dict.fromkeys(NATIVE_FOOT_ORDER, 40.),
                                            available_time_s=ns * 1e-9)
        synthetic_samples.append(Sample(ns, support, positions, np.zeros(3), True, "", 0))
    row = grid_row("synthetic", 151_000_000, synthetic_samples, synthetic_tracker, 0, 0)
    assert row["rank"] == 3 and row["current_source_time_s"] <= row["grid_time_s"]
    assert row["actual_dt_s"] >= .1 and row["source_age_s"] == .001
    assert row["observable_cayley_difference_norm_rad_s"] == 0.
    stale = grid_row("synthetic", 201_000_000, synthetic_samples, synthetic_tracker, 0, 0)
    assert stale["status"] == "STALE_CURRENT_SOURCE"
    faulted = grid_row("synthetic", 151_000_000, synthetic_samples, synthetic_tracker, 0, 1)
    assert faulted["status"] == "UNLOCATED_SOURCE_FAULT_AFTER_CURRENT_SAMPLE"
    return {"status": "PASS", "scope": "local SO3/Cayley sign/order, complete-grid count, causal endpoint/age/fault guards",
            "measured_input_reads": 0, "solver_calls": 0}


def prepare(args):
    aliases = json.loads(args.local_paths.read_text())["aliases"]
    if resolve("<CODE_ROOT>", aliases).resolve() != CODE:
        raise ValueError("LOCAL_PATHS code root differs from executing runner")
    lock = json.loads(LOCK.read_text())
    stage = resolve(args.output_alias, aliases)
    if stage.exists():
        raise FileExistsError("attempt output must not preexist: " + str(stage))
    if not stage.is_relative_to(resolve("<SCRATCH_ROOT>", aliases)):
        raise ValueError("output must be under scratch alias")
    sequences = []
    for sequence in lock["sequences"]:
        name = sequence["sequence_id"]
        if name not in WINDOWS or sequence["full_window_s"] != WINDOWS[name]:
            raise ValueError("unexpected V3 sequence/window")
        source = sequence["raw_files"]["body"]
        actual = resolve(source["path"], aliases)
        if actual.stat().st_size != source["current_size_bytes"]:
            raise ValueError("locked raw body size mismatch: " + name)
        sequences.append({"sequence_id": name, "body": source,
                          "base_time_unix_s": sequence["base_time_unix_s"],
                          "full_window_s": sequence["full_window_s"],
                          "grid_count": round((WINDOWS[name][1] - WINDOWS[name][0]) * 10) + 1})
    if set(v["sequence_id"] for v in sequences) != set(WINDOWS):
        raise ValueError("incomplete locked sequence set")
    checks = self_check()
    plan = {
        "schema": "trusted_heading.body_proxy_input_audit.v1",
        "stage_alias": args.output_alias, "body_payload_reads_before_run": 0,
        "lock_relative_path": str(LOCK.relative_to(CODE)), "lock_sha256": sha(LOCK),
        "source_pins": {p: sha(CODE / p) for p in SOURCES},
        "sequences": sequences, "grid_total": 9213,
        "read_scope": "three body text prefixes through original full-window end; first following timestamp only",
        "policy": {"foot_order": list(NATIVE_FOOT_ORDER),
                   "on": list(FROZEN_CONTACT_ON_THRESHOLDS),
                   "off": list(FROZEN_CONTACT_OFF_THRESHOLDS),
                   "dwell_s": DWELL_S, "max_source_gap_s": MAX_GAP_NS * 1e-9,
                   "period_s": .1, "target_interval_s": .1, "max_interval_s": .15},
        "geometry_weighting": "endpoint I, w_linearization zero; unweighted geometry only; no uncertainty exported",
        "gyro_alignment": "inherited H5 Rx(-1 degree) sensor->body FLU, then diag(1,-1,-1) to FRD",
        "availability": "source-time replay assumption, not calibrated receipt timing",
        "repeat_policy": "one run; no automatic retries; preserve FAILED and all partial files",
        "self_check": checks,
        "forbidden_reads": ["GNSS", "reference", "navigation", "existing error series"],
        "native_solver_calls": 0, "integer_search_calls": 0, "evaluator_calls": 0,
    }
    stage.mkdir(parents=True)
    write_json(stage / "PLAN.json", plan)
    write_json(stage / "PREPARATION.json", {"plan_sha256": sha(stage / "PLAN.json"),
               "command": sys.argv, "self_check": checks})
    print(json.dumps({"status": "PREPARED", "stage": str(stage),
                      "plan_sha256": sha(stage / "PLAN.json")}), flush=True)


@dataclass
class Sample:
    ns: int
    support: object
    feet: np.ndarray | None
    gyro_frd: np.ndarray | None
    source_good: bool
    fault: str
    generation: int


def gyro_consistency(samples, previous, current, proxy):
    selected = [v for v in samples if previous.ns <= v.ns <= current.ns]
    if not selected or selected[0] is not previous or selected[-1] is not current:
        return {"gyro_status": "INCOMPLETE_EXACT_INTERVAL"}
    if any(not v.source_good or v.gyro_frd is None for v in selected):
        return {"gyro_status": "INVALID_GYRO_OR_SOURCE"}
    if any(v.generation != previous.generation for v in selected):
        return {"gyro_status": "UNLOCATED_SOURCE_FAULT_IN_INTERVAL"}
    r = np.eye(3)
    for a, b in zip(selected[:-1], selected[1:]):
        step = b.ns - a.ns
        if not 0 < step <= MAX_GAP_NS:
            return {"gyro_status": "GYRO_INTERVAL_GAP"}
        r = r @ rotation_exp(a.gyro_frd * (step * 1e-9))
    dt = (current.ns - previous.ns) * 1e-9
    try:
        wgyro, angle = rotation_to_cayley_rate(r, dt)
    except ValueError as exc:
        return {"gyro_status": str(exc)}
    difference = proxy.observable_basis_frd.T @ (
        proxy.minimum_norm_cayley_rate_frd_rad_s - wgyro)
    norm = float(np.linalg.norm(difference))
    return {"gyro_status": "INTERNAL_CONSISTENCY_ONLY", "gyro_interval_samples": len(selected),
            "gyro_principal_rotation_angle_rad": angle,
            "observable_cayley_difference_norm_rad_s": norm,
            "observable_cayley_increment_difference_norm": dt * norm}


def grid_row(name, grid_ns, samples, tracker, start_ns, generation):
    row = {key: "" for key in CSV_FIELDS}
    row.update(sequence=name, grid_time_s=grid_ns * 1e-9, rank=0, usable_foot_count=0,
               status="NO_WINDOW_SOURCE_SAMPLE", gyro_status="GEOMETRY_UNAVAILABLE")
    if not samples:
        return row
    current = samples[-1]
    if current.ns > grid_ns:
        raise AssertionError("future source sample")
    row.update(current_source_time_s=current.ns * 1e-9,
               source_age_s=(grid_ns - current.ns) * 1e-9,
               support_states=compact({v.foot_id: v.state for v in current.support.feet}),
               source_fault=current.fault)
    if grid_ns - current.ns > MAX_GAP_NS:
        row["status"] = "STALE_CURRENT_SOURCE"
        return row
    if generation != current.generation:
        row["status"] = "UNLOCATED_SOURCE_FAULT_AFTER_CURRENT_SAMPLE"
        return row
    if not current.source_good or current.feet is None:
        row["status"] = "INVALID_CURRENT_SOURCE"
        return row
    target = current.ns - PERIOD_NS
    previous = next((v for v in reversed(samples) if v.ns <= target), None)
    if previous is None or previous.ns < start_ns:
        row["status"] = "NO_PAST_WINDOW_ENDPOINT"
        return row
    delta = current.ns - previous.ns
    row.update(previous_source_time_s=previous.ns * 1e-9, actual_dt_s=delta * 1e-9)
    if delta > MAX_INTERVAL_NS:
        row["status"] = "ENDPOINT_INTERVAL_TOO_LONG"
        return row
    if not previous.source_good or previous.feet is None:
        row["status"] = "INVALID_PREVIOUS_SOURCE"
        return row
    continuity = tracker.interval_continuity(previous.support, current.support)
    row["interval_continuity"] = compact(continuity)
    def endpoint(sample):
        return FootPositionEpoch(sample.ns * 1e-9, sample.support.available_time_s,
            tuple(NATIVE_FOOT_ORDER), sample.feet,
            tuple(True if v.state == "STANCE" else False if v.state == "SWING" else None
                  for v in sample.support.feet),
            tuple(v.token for v in sample.support.feet), "FLU")
    proxy = estimate_contact_rotation(
        endpoint(previous), endpoint(current), np.eye(24),
        linearization_cayley_rate_frd_rad_s=np.zeros(3),
        interval_continuous_support=continuity, decision_time_s=grid_ns * 1e-9)
    row.update(status=proxy.status, rank=proxy.rank, usable_foot_count=len(proxy.foot_ids),
               usable_feet="|".join(proxy.foot_ids),
               nullspace_frd_json=compact(proxy.nullspace_frd.tolist()),
               observable_basis_frd_json=compact(proxy.observable_basis_frd.tolist()))
    if proxy.rank:
        row["minimum_norm_cayley_rate_rad_s_json"] = compact(
            proxy.minimum_norm_cayley_rate_frd_rad_s.tolist())
        row["observed_geometry_condition"] = float(
            proxy.singular_values[0] / proxy.singular_values[proxy.rank - 1])
        row.update(gyro_consistency(samples, previous, current, proxy))
    return row




def audit_sequence(sequence, aliases, stage):
    name = sequence["sequence_id"]
    source = resolve(sequence["body"]["path"], aliases)
    if source.stat().st_size != sequence["body"]["current_size_bytes"]:
        raise ValueError("source size changed before read")
    start_ns, end_ns = (round(v * 1e9) for v in sequence["full_window_s"])
    base_ns = round(sequence["base_time_unix_s"] * 1e9)
    tracker = SupportArcTracker(SupportPolicy(tuple(
        FootForceThreshold(name, on, off) for name, on, off in
        zip(NATIVE_FOOT_ORDER, FROZEN_CONTACT_ON_THRESHOLDS, FROZEN_CONTACT_OFF_THRESHOLDS)),
        DWELL_S, MAX_GAP_NS * 1e-9), stream_id="BODY_PROXY_AUDIT_" + name)
    samples = deque()
    row_file, row_writer = writer(stage / (name + "_GRID.csv"), CSV_FIELDS)
    fault_file, fault_writer = writer(stage / (name + "_FAULTS.csv"), FAULT_FIELDS)
    event_file, event_writer = writer(stage / (name + "_SUPPORT_EVENTS.csv"), EVENT_FIELDS)
    counts, statuses, ranks, error_codes, reasons = Counter(), Counter(), Counter(), Counter(), Counter()
    field_previous, repeated, field_pairs = {}, Counter(), Counter()
    timings, intervals, ages, conditions, consistency, increments = [], [], [], [], [], []
    source_first = source_last = first_window = last_window = beyond_stamp = None
    grid_ns = start_ns
    generation = 0
    previous_support = None
    last_processed_ns = None
    unusable_run = max_unusable = 0
    consistency_missing_run = max_consistency_missing = 0
    semantic = Counter()

    def emit():
        nonlocal grid_ns, unusable_run, max_unusable, consistency_missing_run, max_consistency_missing
        row = grid_row(name, grid_ns, samples, tracker, start_ns, generation)
        row_writer.writerow(row)
        counts["grid_rows"] += 1
        statuses[row["status"]] += 1
        ranks[str(row["rank"])] += 1
        if row["rank"] > 0:
            unusable_run = 0
        else:
            unusable_run += 1
            max_unusable = max(max_unusable, unusable_run)
        if row["gyro_status"] == "INTERNAL_CONSISTENCY_ONLY":
            consistency.append(row["observable_cayley_difference_norm_rad_s"])
            increments.append(row["observable_cayley_increment_difference_norm"])
            consistency_missing_run = 0
        else:
            consistency_missing_run += 1
            max_consistency_missing = max(max_consistency_missing, consistency_missing_run)
        for field, dest in (("actual_dt_s", intervals), ("source_age_s", ages),
                            ("observed_geometry_condition", conditions)):
            if row[field] != "":
                dest.append(row[field])
        grid_ns += PERIOD_NS

    def fault(index, ns, reason):
        scope = "UNKNOWN_TIMESTAMP" if ns is None else "PREFIX" if ns < start_ns else "WINDOW"
        fault_writer.writerow(dict(sequence=name, message_index=index,
             relative_time_s="" if ns is None else ns * 1e-9, scope=scope, reason=reason))
        counts["fault_records_" + scope] += 1
        reasons[reason] += 1

    try:
        for index, message in enumerate(iter_messages(source), 1):
            counts["messages_framed"] += 1
            match = STAMP.search(message)
            try:
                if match is None:
                    raise ValueError("MISSING_TIMESTAMP")
                sec, nsec = int(match[1]), int(match[2])
                if not 0 <= nsec < 1_000_000_000:
                    raise ValueError("INVALID_NANOSECONDS")
                ns = sec * 1_000_000_000 + nsec - base_ns
            except ValueError as exc:
                generation += 1
                try:
                    tracker.update(float("nan"), {}, available_time_s=float("nan"))
                except SupportArcError:
                    pass
                fault(index, None, str(exc))
                continue
            if ns > end_ns:
                beyond_stamp = ns * 1e-9
                counts["following_timestamp_only"] += 1
                break
            if source_first is None:
                source_first = ns * 1e-9
            if last_processed_ns is not None and ns <= last_processed_ns:
                generation += 1
                try:
                    tracker.update(ns * 1e-9, {}, available_time_s=ns * 1e-9)
                except SupportArcError:
                    pass
                fault(index, ns, "NONMONOTONIC_SOURCE_TIMESTAMP")
                continue
            while grid_ns < ns and grid_ns <= end_ns:
                emit()
            in_window = ns >= start_ns
            counts["source_records_window" if in_window else "source_records_prefix"] += 1
            t = ns * 1e-9
            source_last = t
            if in_window:
                if first_window is None:
                    first_window = t
                last_window = t
                if last_processed_ns is not None and last_processed_ns >= start_ns:
                    timings.append((ns - last_processed_ns) * 1e-9)
            errors = []
            gyro = force = feet = None
            try:
                parsed_ns, raw_gyro, unused_accel, force, raw_feet, counter = _parse_allowed_record(
                    message.splitlines(keepends=True), index)
                if parsed_ns - base_ns != ns:
                    raise HartleyH5Error("STAMP_PARSER_DISAGREEMENT")
                semantic.update(asdict(counter))
                feet = np.asarray(raw_feet, dtype=float).reshape(4, 3)
                gyro = np.asarray(_rotation_x_minus_one_degree(raw_gyro)) * [1., -1., -1.]
            except (HartleyH5Error, ValueError) as exc:
                errors.append("ALLOWED_FIELD_PARSE:" + str(exc))
            found = ERROR.findall(message)
            error_label = None
            if len(found) != 1:
                errors.append("ERROR_CODE_MISSING_OR_DUPLICATED")
                error_label = "missing_or_duplicated"
            else:
                try:
                    error_value = int(found[0].strip().split("#", 1)[0], 0)
                    error_label = str(error_value)
                    if error_value != 0:
                        errors.append("SOURCE_ERROR_CODE_" + error_label)
                except ValueError:
                    error_label = "malformed"
                    errors.append("ERROR_CODE_MALFORMED")
            if in_window:
                error_codes[error_label] += 1
            good = not errors
            support = tracker.update(t, {} if force is None else dict(zip(NATIVE_FOOT_ORDER, force)),
                                     available_time_s=t, source_ok=good)
            if errors:
                fault(index, ns, ";".join(errors))
            if in_window:
                counts["source_good_window"] += int(good)
                for record in support.feet:
                    counts["support_state_" + record.state] += 1
                    counts["support_eligible_foot_samples"] += int(record.eligible)
                    before = None if previous_support is None else previous_support.by_foot()[record.foot_id]
                    new = record.token is not None and (before is None or before.token != record.token)
                    retired = before is not None and before.token is not None and before.token != record.token
                    changed = before is not None and before.state != record.state
                    counts["new_stance_episodes_window"] += int(new)
                    counts["retired_stance_episodes_window"] += int(retired)
                    counts["state_transitions_window"] += int(changed)
                    if new or retired or changed:
                        event_writer.writerow(dict(sequence=name, source_time_s=t, foot=record.foot_id,
                            state_before="" if before is None else before.state, state_after=record.state,
                            new_episode=int(new), retired_episode=int(retired),
                            reasons="|".join(record.reasons)))
                field_values = {"force": None if force is None else tuple(force),
                                "feet": None if feet is None else tuple(feet.ravel()),
                                "gyro": None if gyro is None else tuple(gyro)}
                for label, values in field_values.items():
                    if values is not None and field_previous.get(label) is not None:
                        field_pairs[label] += 1
                        repeated[label] += int(values == field_previous[label])
                    field_previous[label] = values
            if ns >= start_ns:
                samples.append(Sample(ns, support, feet, gyro, good, ";".join(errors), generation))
                while samples and ns - samples[0].ns > 300_000_000:
                    samples.popleft()
            previous_support = support
            last_processed_ns = ns
            if counts["source_records_window"] and counts["source_records_window"] % 10000 == 0:
                print(name, "source_window", counts["source_records_window"], "time", t, flush=True)
        while grid_ns <= end_ns:
            emit()
    finally:
        row_file.close()
        fault_file.close()
        event_file.close()
    if counts["grid_rows"] != sequence["grid_count"]:
        raise AssertionError("complete grid denominator mismatch")
    if source.stat().st_size != sequence["body"]["current_size_bytes"]:
        raise ValueError("source size changed during read")
    summary = {
        "sequence": name, "full_window_s": sequence["full_window_s"],
        "registered_grid_denominator": sequence["grid_count"], "counts": dict(counts),
        "grid_rank_counts": {str(k): ranks[str(k)] for k in range(4)},
        "grid_status_counts": dict(statuses),
        "rank_positive_fraction_full_grid": (ranks["1"] + ranks["2"] + ranks["3"]) / counts["grid_rows"],
        "gyro_consistency_count": len(consistency),
        "max_consecutive_rank0_grid_slots": max_unusable,
        "max_rank0_grid_coverage_s": max_unusable * .1,
        "max_consecutive_no_consistency_grid_slots": max_consistency_missing,
        "max_no_consistency_grid_coverage_s": max_consistency_missing * .1,
        "gap_duration_convention": "count * 0.1s nominal grid-bin coverage; not continuous physical outage truth",
        "source_prefix_first_time_s": source_first, "source_decoded_last_time_s": source_last,
        "source_window_first_time_s": first_window, "source_window_last_time_s": last_window,
        "first_following_timestamp_only_s": beyond_stamp,
        "source_step_s": statistics(timings), "endpoint_dt_s": statistics(intervals),
        "current_age_s": statistics(ages), "observed_geometry_condition": statistics(conditions),
        "observable_cayley_difference_norm_rad_s": statistics(consistency),
        "observable_cayley_increment_difference_norm": statistics(increments),
        "source_error_code_counts_window": dict(error_codes), "fault_reason_counts": dict(reasons),
        "exact_adjacent_field_repeats_window": {
            field: {"repeated": repeated[field], "valid_adjacent_pairs": field_pairs[field],
                    "fraction": repeated[field] / field_pairs[field] if field_pairs[field] else None}
            for field in ("force", "feet", "gyro")},
        "semantic_read_counts_prefix_and_window": dict(semantic),
        "source_identity": sequence["body"],
        "raw_hash_recomputed": False, "raw_size_verified_before_and_after": True,
        "measurement_uncertainty_exported": False,
    }
    write_json(stage / (name + "_SUMMARY.json"), summary)
    print(name, "COMPLETE", compact(summary["grid_rank_counts"]), flush=True)
    return summary


def run(args):
    aliases = json.loads(args.local_paths.read_text())["aliases"]
    stage = resolve(args.output_alias, aliases)
    plan = json.loads((stage / "PLAN.json").read_text())
    if (stage / "INVOCATION.json").exists():
        raise FileExistsError("attempt already invoked; no retry")
    if plan["stage_alias"] != args.output_alias or sha(LOCK) != plan["lock_sha256"]:
        raise ValueError("plan/lock identity mismatch")
    for path, expected in plan["source_pins"].items():
        if sha(CODE / path) != expected:
            raise ValueError("source pin changed: " + path)
    start = time.time()
    write_json(stage / "INVOCATION.json", {"command": sys.argv, "started_unix_s": start,
               "plan_sha256": sha(stage / "PLAN.json"), "pid": __import__("os").getpid()})
    allowed_body = {str(resolve(seq["body"]["path"], aliases).resolve()): seq["body"]["path"]
                    for seq in plan["sequences"]}
    protected_roots = tuple(resolve(alias, aliases).resolve()
                            for alias in ("<RAW_ROOT>", "<CLEAN_ROOT>", "<V3_SCRATCH>", "<SCRATCH_ROOT>"))
    raw_open_events = []
    def audit_hook(event, arguments):
        if event != "open" or not isinstance(arguments[0], (str, bytes)):
            return
        opened = Path(arguments[0].decode() if isinstance(arguments[0], bytes) else arguments[0]).resolve()
        key = str(opened)
        if key in allowed_body:
            mode = arguments[1]
            if mode is None or any(flag in mode for flag in ("w", "a", "+")):
                raise RuntimeError("body raw input is strictly read-only")
            raw_open_events.append({"path": allowed_body[key], "mode": mode})
        elif any(opened.is_relative_to(root) for root in protected_roots):
            if not opened.is_relative_to(stage.resolve()):
                raise RuntimeError("unregistered research payload open: " + str(opened))
    sys.addaudithook(audit_hook)
    try:
        summaries = [audit_sequence(sequence, aliases, stage) for sequence in plan["sequences"]]
        if len(raw_open_events) != 3 or set(v["path"] for v in raw_open_events) != set(allowed_body.values()):
            raise AssertionError("exact three body input opens required")
        write_json(stage / "IO_AUDIT.json", {"scope": "Python file-open audit with protected raw/research payload roots",
                   "body_open_events": raw_open_events, "unregistered_payload_opens_allowed": False,
                   "GNSS_reference_navigation_payload_opens": 0})
        if sum(v["counts"]["grid_rows"] for v in summaries) != 9213:
            raise AssertionError("joint denominator")
        result = {"status": "COMPLETE_INPUT_ONLY", "plan_sha256": sha(stage / "PLAN.json"),
            "sequence_summaries": summaries, "grid_total": 9213,
            "raw_body_payload_stream_opens": 3,
            "raw_full_hash_reads": 0, "GNSS_payload_reads": 0, "reference_payload_reads": 0,
            "navigation_solver_calls": 0, "integer_search_calls": 0, "evaluator_calls": 0,
            "elapsed_s": time.time() - start,
            "interpretation": "SDK-derived geometric/gyro internal consistency; no calibrated covariance, physical contact/slip truth or independent error metric",
            "no_threshold_fitted": True, "failures_not_filtered": True}
        write_json(stage / "SUMMARY.json", result)
        files = sorted(p for p in stage.iterdir() if p.suffix in (".json", ".csv"))
        write_json(stage / "COMPLETE.json", {"status": "COMPLETE_INPUT_ONLY",
            "grid_total": 9213, "source_pins": plan["source_pins"],
            "files": {p.name: sha(p) for p in files}, "elapsed_s": time.time() - start})
        print("COMPLETE", str(stage), flush=True)
    except BaseException:
        write_json(stage / "FAILED.json", {"status": "FAILED_NO_AUTORETRY",
                   "traceback": traceback.format_exc(), "elapsed_s": time.time() - start,
                   "plan_sha256": sha(stage / "PLAN.json")})
        raise




def publish(args):
    aliases = json.loads(args.local_paths.read_text())["aliases"]
    stage = resolve(args.output_alias, aliases)
    seal = json.loads((stage / "COMPLETE.json").read_text())
    for name, expected in seal["files"].items():
        if sha(stage / name) != expected:
            raise ValueError("sealed output mismatch: " + name)
    result = json.loads((stage / "SUMMARY.json").read_text())
    # Engineering readout of sealed outputs, no source replay.
    write_json(DOCS / "BODY_PROXY_AUDIT_SUMMARY.json", result)
    fields = ("sequence", "grid_rows", "rank0", "rank1", "rank2", "rank3",
              "rank_positive_fraction", "gyro_consistency_count",
              "max_rank0_grid_coverage_s", "source_good_window", "new_stance_episodes",
              "retired_stance_episodes", "consistency_median_rad_s", "consistency_p99_rad_s")
    handle, out = writer(DOCS / "BODY_PROXY_AUDIT_COUNTS.csv", fields)
    lines = ["# Three-window body-proxy engineering diagnostic", "",
        "The fixed audit ran once in Ubuntu 22.04 WSL: 9213 complete-grid rows, three body streams, no GNSS/reference/native/search/evaluator payload reads or calls. All faults and unavailable grid rows remain in scratch. No thresholds were adjusted.", "",
        "| Sequence | Full-grid rows | Rank 0 / 1 / 2 / 3 | Rank-positive fraction | Internal-consistency rows | Maximum rank-0 grid coverage (s) |",
        "|---|---:|---|---:|---:|---:|"]
    for item in result["sequence_summaries"]:
        ranks, counts = item["grid_rank_counts"], item["counts"]
        stats = item["observable_cayley_difference_norm_rad_s"]
        row = dict(sequence=item["sequence"], grid_rows=counts["grid_rows"],
            rank0=ranks["0"], rank1=ranks["1"], rank2=ranks["2"], rank3=ranks["3"],
            rank_positive_fraction=item["rank_positive_fraction_full_grid"],
            gyro_consistency_count=item["gyro_consistency_count"],
            max_rank0_grid_coverage_s=item["max_rank0_grid_coverage_s"],
            source_good_window=counts.get("source_good_window", 0),
            new_stance_episodes=counts.get("new_stance_episodes_window", 0),
            retired_stance_episodes=counts.get("retired_stance_episodes_window", 0),
            consistency_median_rad_s=stats.get("p50", ""),
            consistency_p99_rad_s=stats.get("p99", ""))
        out.writerow(row)
        lines.append("| {} | {} | {} / {} / {} / {} | {:.4f} | {} | {:.1f} |".format(
            item["sequence"], counts["grid_rows"], ranks["0"], ranks["1"], ranks["2"], ranks["3"],
            item["rank_positive_fraction_full_grid"], item["gyro_consistency_count"],
            item["max_rank0_grid_coverage_s"]))
    handle.close()
    lines += ["", "Rank-positive coverage means that common-support SDK geometry supplied at least one observable rotation direction. It is not a trusted-heading acceptance rate. Rank 2 retains a null axis and supplies no full orientation.",
        "", "Endpoint Q=I and zero working Cayley rate produce an unweighted geometric projection. No physical covariance is exported or used as a gate. Observed-subspace Cayley-rate differences against raw gyro are internal consistency, not truth error. The inherited Rx(-1 degree) alignment and FLU-to-FRD conversion are declared assumptions, not new calibration.",
        "", "Grid gap duration is count times 0.1 s nominal bin coverage; initial endpoint insufficiency is included. All source records within the windows, complete prior support history, source errors and episode retirements remain accounted for. Exact field repetition, first/last times and actual endpoint intervals are in BODY_PROXY_AUDIT_SUMMARY.json.",
        "", "A support episode is an SDK-force classification under fixed historical thresholds and the declared 0.05 s gap rule. It does not certify no slip, no hidden intersample lift-off or independence from IMU. No navigation fusion or AR acceptance follows from this audit.",
        "", "Reproduction: trusted_heading_body_proxy_audit.py prepare / run / publish with the recorded LOCAL_PATHS file and output alias. PLAN.json, INVOCATION.json, COMPLETE.json and all *_GRID.csv / *_FAULTS.csv / *_SUPPORT_EVENTS.csv remain under " + args.output_alias + "."]
    (DOCS / "BODY_PROXY_AUDIT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    write_json(DOCS / "BODY_PROXY_AUDIT_RECEIPT.json", {
        "source_stage_alias": args.output_alias, "complete_sha256": sha(stage / "COMPLETE.json"),
        "plan_sha256": sha(stage / "PLAN.json"), "source_pins": seal["source_pins"],
        "grid_total": 9213, "derivation_command": ["publish", "--output-alias", args.output_alias],
        "files": {name: sha(DOCS / name) for name in
                  ("BODY_PROXY_AUDIT_SUMMARY.json", "BODY_PROXY_AUDIT_COUNTS.csv", "BODY_PROXY_AUDIT_REPORT.md")},
        "raw_payload_reopened_for_publish": 0})
    print("PUBLISHED", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "publish"))
    parser.add_argument("--local-paths", type=Path, required=True)
    parser.add_argument("--output-alias", required=True)
    args = parser.parse_args()
    {"prepare": prepare, "run": run, "publish": publish}[args.action](args)


if __name__ == "__main__":
    main()


