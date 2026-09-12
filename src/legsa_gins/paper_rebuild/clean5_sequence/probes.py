"""CLEAN5 C-01 input-only probes. No provider, solver or evaluator execution."""
from __future__ import annotations

import builtins
import csv
import datetime as dt
import io
import math
import os
import re
import statistics
from bisect import bisect_left
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from ..manifest import write_json_atomic

ALLOWED_CSV_NAMES = (
    "gnss1-status.csv", "gnss2-status.csv", "gnss1-raw.csv", "imu-data.csv",
    "tf_static.csv", "tf.csv", "user_io-out-odom_status.csv", "user_io-out-poi_odometry.csv",
    "gnss2-raw.csv", "userio-raw.csv", "user_io-status.csv",
)
BY2_BASE_TIME = 1772784000.0
BY2_FROZEN_WINDOW = (66.0, 340.0)
HEAD_MARGIN = 10.0
TAIL_MARGIN = 9.0
MARGIN_CORRECTION_NOTE = "tail margin definition corrected to common-coverage end; margins (10, 9) uniquely reproduce the frozen BY2 window"


class ProbeContractError(RuntimeError):
    """An input-side contract or guarded read failed."""


def reject_forbidden_path(path) -> None:
    if isinstance(path, int):
        return
    name = Path(os.fsdecode(path)).name.lower()
    if (name.startswith("trace_") and name.endswith(".csv")) or name.endswith((".bag", ".fpl")):
        raise ProbeContractError(f"Probe phase forbids opening {name}")


def open_probe_file(path, mode="r", **kwargs):
    """All direct probe input reads enter here, including synthetic guard tests."""
    reject_forbidden_path(path)
    if any(c in mode for c in "wax+"):
        raise ProbeContractError("Probe input entrypoint is read-only")
    return Path(path).open(mode, **kwargs)


@contextmanager
def forbidden_path_guard(raw_root: Path, allowed_paths):
    """Also guard reads inside the maintained A1, Go2 and kick helpers."""
    root = Path(raw_root).resolve()
    allowed = {Path(p).resolve() for p in allowed_paths}
    original_builtin, original_io, original_os, original_path = builtins.open, io.open, os.open, Path.open

    def check(path, mode="r", flags=None, dir_fd=None):
        if isinstance(path, int):
            return
        reject_forbidden_path(path)
        candidate = Path(os.fsdecode(path))
        if dir_fd is not None and not candidate.is_absolute():
            raise ProbeContractError("Unresolved dir_fd open is forbidden during probes")
        candidate = candidate.resolve()
        reject_forbidden_path(candidate)
        if candidate == root or root in candidate.parents:
            write = (flags is not None and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))) or any(c in str(mode) for c in "wax+")
            if write or candidate not in allowed:
                raise ProbeContractError(f"Raw open outside the read-only probe allowlist: {candidate}")

    def guarded_builtin(file, mode="r", *args, **kwargs):
        check(file, mode)
        return original_builtin(file, mode, *args, **kwargs)

    def guarded_io(file, mode="r", *args, **kwargs):
        check(file, mode)
        return original_io(file, mode, *args, **kwargs)

    def guarded_os(file, flags, *args, **kwargs):
        check(file, flags=flags, dir_fd=kwargs.get("dir_fd"))
        return original_os(file, flags, *args, **kwargs)

    def guarded_path(file, mode="r", *args, **kwargs):
        check(file, mode)
        return original_path(file, mode, *args, **kwargs)

    builtins.open, io.open, os.open = guarded_builtin, guarded_io, guarded_os
    Path.open = guarded_path
    try:
        yield
    finally:
        builtins.open, io.open, os.open = original_builtin, original_io, original_os
        Path.open = original_path


def probe_allowlist(registry):
    return {p for seq in registry.sequences.values() for p in
            [seq.body_path, *(seq.fix_root / name for name in ALLOWED_CSV_NAMES)]}


def _csv(path, *, header_only=False):
    reject_forbidden_path(path)
    if not Path(path).is_file():
        raise FileNotFoundError(f"Input table unavailable: {Path(path).name}")
    with open_probe_file(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        names = list(reader.fieldnames or [])
        return names, [] if header_only else list(reader)


def _float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _true(value):
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "ok"}


def _stamp(row, prefix="sys_stamp"):
    seconds = _float(row.get(prefix + ".secs"))
    nanos = _float(row.get(prefix + ".nsecs"))
    if seconds is None:
        raise ProbeContractError(f"Missing finite {prefix}.secs")
    return seconds + (nanos or 0.0) * 1e-9


def _percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * fraction
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def _stats(values):
    finite = [v for x in values if (v := _float(x)) is not None]
    return {"finite_count": len(finite), "min": min(finite) if finite else None,
            "median": _percentile(finite, .5), "p95": _percentile(finite, .95),
            "max": max(finite) if finite else None}


def _range(times, origin=0.0):
    values = [float(t) - origin for t in times]
    return {"first": values[0] if values else None, "last": values[-1] if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None,
            "negative_time": any(t < 0.0 for t in values)}


def time_rules(rows):
    first = next((row for row in rows if _true(row.get("pos_valid"))), None)
    if first is None:
        raise ProbeContractError("No GNSS1 pos_valid epoch for R1")
    first_time = _stamp(first)
    r1 = math.floor(first_time / 3600.0) * 3600.0
    day = dt.datetime(int(first["utc_year"]), int(first["utc_month"]), int(first["utc_day"]), tzinfo=dt.timezone.utc)
    r3 = day.timestamp() + 28800.0
    times = [_stamp(row) for row in rows]
    return {"R1": r1, "R3": r3, "first_pos_valid_sys_stamp": first_time,
            "utc_day_midnight": day.timestamp(), "auxiliary_rebase_offset_seconds": r1 - day.timestamp(),
            "R1_gnss1_relative_time": _range(times, r1), "R3_gnss1_relative_time": _range(times, r3),
            "rule_R1": "floor(first_pos_valid_GNSS1_sys_stamp/3600)*3600",
            "rule_R3": "UTC calendar midnight from first pos_valid GNSS1 utc_* + 28800"}


def _endpoint_status(rows):
    if not rows:
        raise ProbeContractError("Empty GNSS status table")
    def endpoint(row):
        return {"sys_stamp": _stamp(row), "header_stamp": _stamp(row, "header.stamp"),
                "utc_fields": {k: v for k, v in row.items() if k.startswith("utc_")}}
    return {"rows": len(rows), "first": endpoint(rows[0]), "last": endpoint(rows[-1])}


def _inventory(seq, locked):
    prefix = seq.fix_prefix + "/"
    relatives = sorted(p for p in locked if p.startswith(prefix) or p in
                       {seq.fix_prefix + ".bag", seq.fix_prefix + ".fpl", seq.go2_body})
    inventory = []
    for relative in relatives:
        row = locked[relative]
        forbidden = Path(relative).name.startswith("trace_") or Path(relative).suffix in {".bag", ".fpl"}
        raw_count = str(row.get("line_count_or_file_type", ""))
        count_match = re.fullmatch(r"(?:line_count:)?(\d+)", raw_count)
        inventory.append({"relative_path": relative, "bytes": int(row["size_bytes"]), "sha256": row["sha256"],
                          "csv_line_count_including_header": int(count_match[1]) if not forbidden and count_match and relative.endswith(".csv") else None,
                          "line_count_or_file_type": "NOT_READ_HASH_ONLY" if forbidden else raw_count,
                          "row_count_source": "hash-matched original raw lock; not reopened for counting"})
    return inventory


def _write_csv(path, rows, columns):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _status_flags(row):
    return {"rel_valid_invalid": not _true(row.get("rel_valid")),
            "ant_valid_invalid": not _true(row.get("ant_valid")),
            "ant_state_invalid": _float(row.get("ant_state")) != 2.0}


def occlusion_rows(rows, names, base_time, gnss1_rows, a1_rows, association_tolerance, receiver="gnss2"):
    fix_fields = [c for c in names if re.search(r"fix|solution_type", c, re.I)]
    sat_fields = [c for c in names if re.search(r"sat|num_sv|numsv|n_sv", c, re.I)]
    one = sorted(gnss1_rows, key=lambda r: _stamp(r, "header.stamp"))
    one_times = [_stamp(r, "header.stamp") for r in one]
    a1_times = {float(r["timestamp"]) for r in a1_rows}
    output, segments, active = [], [], []
    for row in sorted(rows, key=_stamp):
        flags = _status_flags(row)
        triggers = [k for k, v in flags.items() if v]
        header = _stamp(row, "header.stamp")
        index = bisect_left(one_times, header)
        neighbors = [i for i in (index-1, index) if 0 <= i < len(one_times)]
        nearest = min(neighbors, key=lambda i: (abs(one_times[i]-header), one_times[i])) if neighbors else None
        matched = nearest is not None and abs(one_times[nearest]-header) <= association_tolerance
        constructed = matched and one_times[nearest] in a1_times
        actual_a1 = constructed and not any(flags.values())
        if not matched:
            triggers.append("no_gnss1_epoch_within_frozen_association_tolerance")
        elif not constructed:
            triggers.append("a1_not_constructed_at_matched_gnss1_epoch")
        if not _true(row.get("pos_valid")):
            triggers.insert(0, receiver + "_pos_invalid")
        if "fix_ok" in row and not _true(row["fix_ok"]):
            triggers.append(receiver + "_fix_ok_false")
        exported = list(dict.fromkeys(["pos_valid", "fix_type", "fix_ok", *fix_fields, *sat_fields,
                                     "pos_acc_h", "pos_acc_v", "rel_valid", "ant_valid", "ant_state"]))
        item = {"relative_time_R1": _stamp(row) - base_time,
                "header_time_R1": header - base_time,
                **{k: row.get(k, "UNAVAILABLE") for k in exported},
                "satellite_fields_status": "AVAILABLE" if sat_fields else "UNAVAILABLE",
                "a1_source_flags_valid": not any(flags.values()), "candidate_unavailable": bool(triggers),
                "a1_constructed": constructed, "a1_epoch_available": actual_a1,
                "a1_rel_valid": row.get("rel_valid", "UNAVAILABLE"),
                "a1_ant_valid": row.get("ant_valid", "UNAVAILABLE"),
                "a1_ant_state": row.get("ant_state", "UNAVAILABLE"),
                "matched_gnss1_header_R1": one_times[nearest]-base_time if matched else None,
                "gnss1_association_delta_seconds": one_times[nearest]-header if matched else None,
                **{"gnss1_"+k: one[nearest].get(k, "UNAVAILABLE") if matched else "UNAVAILABLE"
                   for k in ("rel_valid", "ant_valid", "ant_state")},
                "trigger_flags": ";".join(triggers)}
        output.append(item)
        if triggers:
            active.append(item)
        elif active:
            segments.append(_segment(active)); active = []
    if active:
        segments.append(_segment(active))
    segments.sort(key=lambda r: (-r["duration"], r["start"]))
    return output, {"fix_fields": fix_fields, "satellite_fields": sat_fields,
                    "unavailable_fields": [c for c in ("fix_type", "fix_ok", "pos_acc_h", "pos_acc_v") if c not in names],
                    "segments": segments, "epoch_count": len(output),
                    "selection": "all consecutive flagged source epochs, descending duration; no window selected",
                    "a1_flag_definition": "source flags valid AND matched GNSS1 header epoch exists in maintained A1 builder output; A1 rel/ant fields retain source flags, not invented builder fields",
                    "association_tolerance_seconds": association_tolerance,
                    "association_tolerance_source": "maintained process_data_compat.generate_process_data_compat_inputs dual_yaw_match_tolerance_seconds default; unchanged, no search",
                    "duration_definition": "last flagged sys_stamp minus first flagged sys_stamp; no extrapolation"}


def _segment(rows):
    return {"start": rows[0]["relative_time_R1"], "end": rows[-1]["relative_time_R1"],
            "duration": rows[-1]["relative_time_R1"] - rows[0]["relative_time_R1"], "epoch_count": len(rows),
            "trigger_flags": sorted({flag for row in rows for flag in row["trigger_flags"].split(";") if flag})}


def a1_missing_segments(yaw):
    times = sorted(float(r["aligned_time"]) for r in yaw)
    intervals = [b-a for a, b in zip(times, times[1:])]
    median = _percentile(intervals, .5)
    segments = [{"start": a, "end": b, "duration": b-a, "epoch_count": 0,
                 "bounding_epoch_count": 2, "trigger_flags": ["a1_interval_exceeds_twice_median"]}
                for a, b in zip(times, times[1:]) if median is not None and b-a > 2*median]
    return {"median_interval_seconds": median, "threshold_definition": "2 * median adjacent A1 interval; no search",
            "duration_definition": "observed bounding A1 epochs; no missing epoch count inferred",
            "segments": sorted(segments, key=lambda r: (-r["duration"], r["start"]))}


def candidate_window_bprime(common, imu, gnss, a1):
    if not common or not imu or not gnss or not a1:
        raise ProbeContractError("No valid three-stream common coverage")
    streams = {"propagation_go2_imu": _range(imu), "gnss1_pos_valid_sys": _range(gnss),
               "a1_constructed_header": _range(a1)}
    end_support = min(imu[-1], gnss[-1], a1[-1])
    return {"common_coverage": _range(common), "streams": streams,
            "common_end_limited_by": [name for name, bounds in streams.items() if bounds["last"] == end_support],
            "common_end_support_seconds": end_support,
            "rule_B_prime": {"t_start": math.ceil(common[0]) + HEAD_MARGIN,
                             "t_end": math.floor(common[-1]) - TAIL_MARGIN},
            "head_margin_seconds": HEAD_MARGIN, "tail_margin_seconds": TAIL_MARGIN,
            "margin_definition_note": MARGIN_CORRECTION_NOTE,
            "common_epoch_definition": "GNSS1 pos_valid sys_stamp bracketed by valid propagation Go2 IMU rows, with its exact header.stamp in constructed A1 output and rel_valid/ant_valid/ant_state==2; helper validates both receivers",
            "stream_clock_note": "IMU timestamp and GNSS1 sys_stamp are absolute source times; A1 uses GNSS1 header.stamp. All displayed relative to R1; association is by exact source row, no clock adjustment",
            "window_selected": False, "time_or_threshold_search": False}


def run_item(report, key, operation):
    """Record one item failure without suppressing the remaining operations."""
    try:
        result = operation()
        report[key] = {"status": "PASS", **result}
    except Exception as exc:
        report[key] = {"status": "FAIL", "error_class": type(exc).__name__, "error_message": str(exc)}
    return report[key]


def kick_report(seq, base, common, imu, gnss, detector):
    diagnostic_path = seq.probe_dir / "KICK_DETECTOR_DIAGNOSTICS.json"
    segment_path = seq.probe_dir / "GO2_INITIAL_EVENT_SEGMENT.csv"
    try:
        detection = detector(seq.body_path, maintained_candidate_output_path=segment_path)
        values = asdict(detection)
        write_json_atomic(diagnostic_path, {"status": "PASS", "returned_detection": values})
        after = [t for t in common if t >= detection.t_go2_kick - base]
        return {"status": "PASS", "report_only": True, "t_start": after[0] if after else None,
                "t_end": min(imu[-1], gnss[-1]), "relative_kick_time_R1": detection.t_go2_kick-base,
                "kick": {k: v for k, v in values.items() if k != "diagnostics"},
                "diagnostic_file": diagnostic_path.name, "diagnostic_rows": len(values["diagnostics"])}
    except Exception as exc:
        # Preserve values already computed by the unchanged detector. No rerun,
        # reconstructed diagnostic rows, threshold change or candidate selection.
        exposed = {"exception_attributes": vars(exc)}
        tb = exc.__traceback__
        allowed = ("change_index", "change_time", "raw_samples", "scored", "selected_index", "selected", "score",
                   "acc_median", "acc_mad", "acc_scale", "gyro_median", "gyro_mad", "gyro_scale",
                   "maintained", "maintained_time", "maintained_score", "maintained_status", "diagnostics")
        while tb:
            if tb.tb_frame.f_code is detector.__code__:
                local = tb.tb_frame.f_locals
                exposed["detector_locals_at_failure"] = {k: local[k] for k in allowed if k in local}
                exposed["event_segment_row_count"] = len(local.get("event_rows", []))
                exposed["normalization_sample_count"] = len(local.get("baseline", []))
                exposed["KickDiagnosticRow_status"] = "EXPOSED" if "diagnostics" in local else "NOT_CONSTRUCTED_BEFORE_EXCEPTION"
            tb = tb.tb_next
        failure = {"status": "FAIL", "error_class": type(exc).__name__, "error_message": str(exc),
                   "report_only": True, "retry_count": 0, "diagnostic_file": diagnostic_path.name,
                   "event_segment_file": segment_path.name if segment_path.exists() else "NOT_CREATED"}
        write_json_atomic(diagnostic_path, {**failure, **exposed})
        return failure


def _tf_summary(path, *, retain_all=False):
    columns, rows = _csv(path)
    pairs = {}
    for row in rows:
        blocks = re.split(r",\s*header:\s*\n", row.get("transforms", "").strip("[]"))
        for block in blocks:
            if "transforms" in row:
                frame = re.search(r'(?m)^\s*frame_id:\s*"?([^"\n]+)', block)
                child = re.search(r'(?m)^\s*child_frame_id:\s*"?([^"\n]+)', block)
                if not frame or not child:
                    raise ProbeContractError("Cannot extract raw tf frame pair")
                key = (frame[1].strip(), child[1].strip())
                if key in pairs:
                    continue
                trans = re.search(r"translation:\s*\n(.*?)\n\s*rotation:", block, re.S)
                rot = re.search(r"rotation:\s*\n(.*)", block, re.S)
                if not trans or not rot:
                    raise ProbeContractError("Cannot extract raw tf translation/quaternion")
                scalars = lambda text: dict(re.findall(r"(?m)^\s*([xyzw]):\s*([^\n]+)", text))
                pairs[key] = {"frame_id": key[0], "child_frame_id": key[1], "translation": scalars(trans[1]),
                              "quaternion": scalars(rot[1]), "first_csv_time": row.get("Time", "UNAVAILABLE"),
                              "raw_transform_text": block}
            else:
                key = (row.get("header.frame_id", row.get("frame_id")), row.get("child_frame_id"))
                if None in key:
                    raise ProbeContractError("No supported raw tf frame columns")
                pairs.setdefault(key, {"frame_id": key[0], "child_frame_id": key[1], "first_raw_row": row})
    result = {"columns": columns, "row_count": len(rows), "unique_frame_pairs": [list(k) for k in pairs],
              "first_raw_transform_per_pair": list(pairs.values())}
    if retain_all:
        result["all_raw_rows"] = rows
    return result


def _receiver_quality(rows, names):
    return {"fix_distributions": {field: dict(Counter(r.get(field, "") for r in rows)) if field in names else "UNAVAILABLE"
                                  for field in ("fix_type", "fix_ok")},
            **{field: _stats(r.get(field) for r in rows) if field in names else "UNAVAILABLE"
               for field in ("pos_acc_h", "pos_acc_v")}}


def absolute_yaw_increment(first, second):
    """Shortest adjacent angle difference, including either crossing of zero."""
    return abs((second - first + 180.0) % 360.0 - 180.0)


def _provenance():
    return {"synthetic_data_used": False, "semisynthetic_data_used": False, "trace_used_online": False,
            "trace_content_read": False, "solver_process_count": 0, "evaluator_process_count": 0,
            "provider_generation_count": 0, "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False, "per_case_tuning": False, "output_only_correction": False,
            "epoch_deleted_for_metric": False, "old_runtime_input_count": 0}


def write_report(seq, report):
    write_json_atomic(seq.probe_dir / "PROBE_REPORT.json", report)
    lines = [f"# {seq.dataset_id} C-01 input probes", "", f"Status: {report['status']}", ""]
    # Preserve full raw values and every unavailable segment, without interpretation.
    import json
    for key, value in report.items():
        if key in {"dataset_id", "stage_id", "status"}:
            continue
        lines += [f"## {key}", "", "```json", json.dumps(value, ensure_ascii=False, indent=2), "```", ""]
    (seq.probe_dir / "PROBE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run_probes(registry, original_rows, clean5_rows, provenance, *, resume_heading_only=False):
    """Each item and sequence completes independently; item failures are evidence."""
    with forbidden_path_guard(registry.raw_root, []):
        from .. import providers, kick_alignment
    reports = {}
    with forbidden_path_guard(registry.raw_root, probe_allowlist(registry)):
        for dataset in ("BY2", "BY2H", "BY2O"):
            seq = registry.sequences[dataset]
            seq.probe_dir.mkdir(parents=True, exist_ok=True)
            report = {"dataset_id": dataset, "stage_id": seq.stage_id, "data_mode": seq.data_mode,
                      "status": "IN_PROGRESS", **_provenance(), **provenance}
            if resume_heading_only:
                import json
                previous = json.loads((seq.probe_dir / "PROBE_REPORT.json").read_text(encoding="utf-8"))
                if previous["dataset_id"] != dataset or previous["data_mode"] != seq.data_mode:
                    raise ProbeContractError("Heading continuation requires the matching completed sequence report")
                history = previous.setdefault("probe_execution_history", [])
                history.append({"items": "a-h initial execution", "provenance": {k: previous[k] for k in provenance},
                                "audit_file": "PROBE_C01B_INITIAL_STRACE_AUDIT.json"})
                history.append({"items": ["h_heading_quality"], "provenance": provenance,
                                "reason": "Use shortest signed angle difference before absolute value; no kick retry"})
                report = {**previous, **provenance, "heading_only_continuation": True}
            reports[dataset] = report
            cache = {}

            def cached(key, operation):
                if key not in cache:
                    try:
                        cache[key] = operation()
                    except Exception as exc:
                        cache[key] = exc
                if isinstance(cache[key], Exception):
                    raise cache[key]
                return cache[key]

            def status(n):
                return cached("status"+str(n), lambda: _csv(seq.fix_root / f"gnss{n}-status.csv"))

            def rules():
                return cached("rules", lambda: time_rules(status(1)[1]))

            def a1():
                return cached("a1", lambda: providers.build_a1_dual_diff_yaw_rows(
                    seq.fix_root / "gnss1-status.csv", seq.fix_root / "gnss2-status.csv", base_time=rules()["R1"]))

            def body():
                return cached("body", lambda: providers.parse_go2_body_state_text(seq.body_path))

            def probe_a():
                result = {"files": _inventory(seq, original_rows if dataset == "BY2" else clean5_rows)}
                for n in (1, 2):
                    run_item(result, f"gnss{n}_status", lambda n=n: _endpoint_status(status(n)[1]))
                def body_info():
                    times = [float(r["timestamp"]) for r in body() if _float(r.get("timestamp")) is not None]
                    diffs = [b-a for a, b in zip(times, times[1:]) if b>a]
                    med = _percentile(diffs, .5)
                    return {"messages": len(body()), "timestamp": _range(times), "median_dt_seconds": med,
                            "rate_from_median_dt_hz": 1/med if med else None}
                run_item(result, "go2_body", body_info)
                def imu_count():
                    with open_probe_file(seq.fix_root / "imu-data.csv", encoding="utf-8-sig", newline="") as handle:
                        reader = csv.reader(handle); next(reader, None)
                        count = sum(1 for _ in reader)
                    return {"rows": count, "nominal_rate_hz": None,
                            "nominal_rate_status": "UNAVAILABLE: no rate metadata in row-count-only read",
                            "role": "receiver diagnostic only; propagation IMU comes from Go2 body"}
                run_item(result, "receiver_imu_data", imu_count)
                return _nested_status(result)

            def probe_b():
                result = dict(rules())
                if dataset == "BY2":
                    result["R1_BY2_gate"] = "PASS" if result["R1"] == BY2_BASE_TIME else "FAIL"
                    if result["R1_BY2_gate"] == "FAIL":
                        result.update(status="FAIL", error_class="ProbeContractError", error_message="R1(BY2) differs from frozen origin")
                return result

            def probe_c():
                yaw, audit = a1()
                lengths = [float(r["baseline_len_m"]) for r in yaw]
                median = _percentile(lengths, .5)
                regression = sum(3.5 <= x <= 4.5 for x in lengths)
                return {"epochs": len(yaw), "median_m": median, "p05_m": _percentile(lengths, .05),
                        "p95_m": _percentile(lengths, .95), "epochs_3p5_to_4p5_m": regression,
                        "fraction_0p20_to_0p60_m": sum(.2 <= x <= .6 for x in lengths)/len(lengths) if lengths else None,
                        "physical_preview": "PASS" if median is not None and .2 <= median <= .6 and regression == 0 else "FAIL",
                        "formal_gate_executed": False, "formal_gate_stage": "C-03", "input_status_audit": audit}

            def probe_d():
                base = rules()["R1"]
                imu_rows = sorted((r for r in body() if _float(r.get("timestamp")) is not None), key=lambda r: float(r["timestamp"]))
                all_times = [float(r["timestamp"])-base for r in imu_rows]
                valid = [all(_float(r.get(k)) is not None for k in ("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z")) for r in imu_rows]
                imu = [t for t, ok in zip(all_times, valid) if ok]
                yaw_headers = {float(r["timestamp"]) for r in a1()[0]}
                pos = sorted((r for r in status(1)[1] if _true(r.get("pos_valid"))), key=_stamp)
                gnss = [_stamp(r)-base for r in pos]
                common = []
                for r in pos:
                    t = _stamp(r)-base
                    i = bisect_left(all_times, t)
                    imu_valid = (i < len(all_times) and all_times[i] == t and valid[i]) or (0 < i < len(all_times) and valid[i-1] and valid[i])
                    if imu_valid and _stamp(r, "header.stamp") in yaw_headers and not any(_status_flags(r).values()):
                        common.append(t)
                a1_times = sorted(t-base for t in yaw_headers)
                result = candidate_window_bprime(common, imu, gnss, a1_times)
                result["propagation_imu_invalid_row_count"] = len(valid)-sum(valid)
                if dataset == "BY2":
                    window = result["rule_B_prime"]
                    result["B_prime_BY2_gate"] = "PASS" if (window["t_start"], window["t_end"]) == BY2_FROZEN_WINDOW else "FAIL"
                    if result["B_prime_BY2_gate"] == "FAIL":
                        result.update(status="FAIL", error_class="ProbeContractError", error_message="B-prime(BY2) differs from frozen 66/340")
                result["rule_A"] = kick_report(seq, base, common, imu, gnss, kick_alignment.detect_frozen_go2_kick)
                return _nested_status(result)

            def probe_e():
                base = rules()["R1"]
                start = report["d_window_candidates"]["rule_B_prime"]["t_start"]
                pos0 = next(r for r in status(1)[1] if _true(r.get("pos_valid")) and _stamp(r)-base >= start)
                yaw0 = next(r for r in a1()[0] if float(r["aligned_time"]) >= start)
                llh = [float(pos0[k]) for k in ("pos_lat", "pos_lon", "pos_height")]
                ned = providers.wrap_deg(90.0-float(yaw0["yaw_baseline_deg"]))
                result = {"candidate_t_start": start, "first_position_time_R1": _stamp(pos0)-base, "position_llh": llh,
                          "first_A1_time_R1": yaw0["aligned_time"], "first_A1_NED_yaw_deg": ned,
                          "report_only_no_gate": True, "frozen_anchor_comparison": dataset == "BY2"}
                if dataset == "BY2":
                    anchor = [39.98482973, 116.34312609, 41.80208107]
                    diff = [abs(x-y) for x, y in zip(llh, anchor)]
                    result.update(frozen_position_llh=anchor, frozen_yaw_deg=.688505,
                                  position_absolute_difference=diff,
                                  approximate_position_absolute_difference_m=[math.radians(diff[0])*6378137.0, math.radians(diff[1])*6378137.0*math.cos(math.radians(anchor[0])), diff[2]],
                                  position_difference_m_note="angular differences scaled by spherical radius 6378137 m at frozen latitude; report only",
                                  yaw_absolute_difference_deg=abs(providers.wrap_deg(ned-.688505)))
                return result

            def probe_f():
                import inspect
                tolerance = float(inspect.signature(providers._shared_process_data_compat.generate_process_data_compat_inputs)
                                  .parameters["dual_yaw_match_tolerance_seconds"].default)
                result = {}
                for n in (1, 2):
                    def receiver(n=n):
                        names, rows = status(n)
                        raw_names, _ = _csv(seq.fix_root / f"gnss{n}-raw.csv", header_only=True)
                        epochs, availability = occlusion_rows(rows, names, rules()["R1"], status(1)[1], a1()[0], tolerance, receiver=f"gnss{n}")
                        csv_path = seq.probe_dir / f"GNSS{n}_AVAILABILITY_EPOCHS.csv"
                        _write_csv(csv_path, epochs, list(epochs[0]) if epochs else ["relative_time_R1"])
                        return {"status_columns": names, "raw_columns": raw_names, "epoch_csv": csv_path.name, **availability}
                    run_item(result, f"gnss{n}", receiver)
                run_item(result, "a1_missing_segments", lambda: a1_missing_segments(a1()[0]))
                result["all_segments_descending_duration"] = sorted(
                    [{**s, "source": key} for key, value in result.items() for s in value.get("segments", [])],
                    key=lambda r: (-r["duration"], r["start"], r["source"]))
                return _nested_status(result)

            def probe_g():
                result = {}
                run_item(result, "gnss1_quality", lambda: _receiver_quality(status(1)[1], status(1)[0]))
                run_item(result, "tf_static", lambda: _tf_summary(seq.fix_root / "tf_static.csv", retain_all=True))
                run_item(result, "tf", lambda: _tf_summary(seq.fix_root / "tf.csv"))
                for name in ("user_io-out-odom_status.csv", "user_io-out-poi_odometry.csv", "userio-raw.csv", "user_io-status.csv"):
                    run_item(result, name, lambda name=name: {"columns": _csv(seq.fix_root / name, header_only=True)[0]})
                return _nested_status(result)

            def probe_h():
                yaw = sorted(a1()[0], key=lambda r: r["aligned_time"])
                headings = [providers.wrap_deg(90.0-float(r["yaw_baseline_deg"])) for r in yaw]
                delta = [absolute_yaw_increment(a, b) for a, b in zip(headings, headings[1:])]
                intervals = [float(b["aligned_time"])-float(a["aligned_time"]) for a, b in zip(yaw, yaw[1:])]
                outside = sum(not .2 <= float(r["baseline_len_m"]) <= .6 for r in yaw)
                return {"abs_adjacent_yaw_increment_deg": _stats(delta), "baseline_band_m": [.2, .6],
                        "baseline_outside_epoch_count": outside, "baseline_epoch_count": len(yaw),
                        "baseline_outside_fraction": outside/len(yaw) if yaw else None,
                        "a1_interval_seconds": _stats(intervals),
                        **{f"gnss{n}": _receiver_quality(status(n)[1], status(n)[0]) for n in (1, 2)}}

            operations = (("h_heading_quality", probe_h),) if resume_heading_only else (
                ("b_base_time", probe_b), ("a_inventory", probe_a), ("c_a1_baseline", probe_c),
                ("d_window_candidates", probe_d), ("e_initialization", probe_e),
                ("f_occlusion_candidates", probe_f), ("g_source_fields", probe_g), ("h_heading_quality", probe_h))
            for key, operation in operations:
                run_item(report, key, operation)
            # Available ranges use cached inputs only; one unavailable stream never
            # prevents the remaining streams or sequences from being reported.
            if not resume_heading_only and "rules" in cache and not isinstance(cache["rules"], Exception):
                for rule in ("R1", "R3"):
                    origin = cache["rules"][rule]
                    ranges = {}
                    for n in (1, 2):
                        value = cache.get("status"+str(n))
                        if value is not None and not isinstance(value, Exception):
                            run_item(ranges, f"gnss{n}_status", lambda value=value: _range([_stamp(r) for r in value[1]], origin))
                    value = cache.get("body")
                    if value is not None and not isinstance(value, Exception):
                        run_item(ranges, "go2_body", lambda: _range([r["timestamp"] for r in value], origin))
                    value = cache.get("a1")
                    if value is not None and not isinstance(value, Exception):
                        run_item(ranges, "a1_header_epochs", lambda: _range([r["timestamp"] for r in value[0]], origin))
                    report["b_base_time"][rule+"_relative_ranges"] = ranges
            report["item_failures"] = [key for key, value in report.items() if isinstance(value, dict) and value.get("status") == "FAIL"]
            report["status"] = "COMPLETED_WITH_ITEM_FAILURES" if report["item_failures"] else "PASS_INPUT_PROBES"
            write_report(seq, report)
    return reports


def _nested_status(result):
    failures = [key for key, value in result.items() if isinstance(value, dict) and value.get("status") == "FAIL"]
    if failures:
        result.update(status="FAIL", failed_subitems=failures)
    return result
