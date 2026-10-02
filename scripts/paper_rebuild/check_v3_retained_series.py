#!/usr/bin/env python3
"""One-read validation of explicitly indexed retained V3 series; stdlib only.

No project modules, solver, provider, evaluator, aggregate controller, NAV or raw
reference inputs are imported/opened. Each CLI execution handles ONE named group.
Preparation reads metadata only. Group execution needs a supervisor-provided
published preparation commit and an explicit per-group release string.
"""
from __future__ import annotations

import argparse
from array import array
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OUT_REL = "docs/paper_rebuild/audit_xbpg_20261001/v3_interpretation/series_checks"
RESULT_REL = "docs/paper_rebuild/audit_xbpg_20261001/v3_results"
ROOTS_REL = "configs/paper_rebuild/V3_RESULTS_ROOTS.local.json"
ABS_TOL = 1e-10
REL_TOL = 1e-10
TIME_TOL = 1e-9
ERROR_COLUMNS = ["time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m",
                 "position_3d_err_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg",
                 "horizontal_3sigma_m", "roll_3sigma_deg", "pitch_3sigma_deg", "yaw_3sigma_deg"]
MATCHED_COLUMNS = ["time", "truth_latitude_deg", "truth_longitude_deg", "truth_height_m",
                   "truth_yaw_deg", "estimate_latitude_deg", "estimate_longitude_deg",
                   "estimate_height_m", "estimate_yaw_deg"]
AXES = [("north", "m", "err_n_m"), ("east", "m", "err_e_m"), ("up", "m", "err_u_m"),
        ("roll", "deg", "roll_err_deg"), ("pitch", "deg", "pitch_err_deg"), ("yaw", "deg", "yaw_err_deg")]
NORMS = [("horizontal", "m", "horizontal_err_m"), ("position_3d", "m", "position_3d_err_m")]
OCCLUSIONS = [(3369.94, 3411.95), (3495.94, 3508.94)]
IDENTITY = ["file_id", "group", "run_id", "sequence_id", "domain", "case_id", "case_family",
            "seed_index", "method_id", "effective_profile", "evaluator_version", "payload_kind", "data_mode"]
SOURCE_DEFINITIONS = [
    "src/legsa_gins/paper_rebuild/protocol_v3/runtime.py",
    "src/legsa_gins/paper_rebuild/clean5_parity_p04/evaluation.py",
    "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py",
    "src/legsa_gins/paper_rebuild/canonical541/provider_generator.py",
    "src/legsa_gins/paper_rebuild/clean6_addendum/aggregate.py",
    "src/legsa_gins/paper_rebuild/hext/aggregate.py",
    "src/legsa_gins/paper_rebuild/hext/readonly_closeout.py",
    "scripts/paper_rebuild/v3_evaluator_observer/sitecustomize.py",
]


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def write_json_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path):
    # Preserve source JSON floating-number lexemes, instead of reformatting them.
    return json.loads(path.read_bytes(), parse_float=str)


def aliases():
    return json.loads((ROOT / ROOTS_REL).read_bytes())["aliases"]


def resolve(value, roots):
    for alias in sorted(roots, key=len, reverse=True):
        if value == alias or value.startswith(alias + "/"):
            if alias in ("<RAW_ROOT>", "<LEGACY_FREEZE_ROOT>"):
                raise ValueError("Forbidden input root")
            return Path(roots[alias] + value[len(alias):])
    raise ValueError("Input is not an explicitly resolved alias: " + value)


def portable(value, roots):
    value = str(value)
    for alias, actual in sorted(roots.items(), key=lambda item: len(item[1]), reverse=True):
        value = value.replace(actual, alias)
    return value


def as_number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def source_value(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def pointer_part(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def identity(entry):
    return {key: entry.get(key, "") for key in IDENTITY}


def interval_window(name, start, end, policy, source):
    return {"window_id": name, "start_s": float(start), "end_s": float(end),
            "endpoint_policy": policy, "definition_source": source}


def old_event_window(meta):
    """Independent transcription of the old canonical _event_window definition."""
    params = json.loads(meta.get("degradation_parameters_json") or "{}")
    start = next((as_number(params[k]) for k in ("start_s", "start_time_s", "fault_start_s", "outage_start_s")
                  if as_number(params.get(k)) is not None), as_number(meta.get("anchor_time_s")))
    end = next((as_number(params[k]) for k in ("end_s", "end_time_s", "fault_end_s", "outage_end_s")
                if as_number(params.get(k)) is not None), None)
    duration = next((as_number(params[k]) for k in ("duration_s", "fault_duration_s", "outage_duration_s")
                     if as_number(params.get(k)) is not None), None)
    if end is None and start is not None and duration is not None:
        end = start + duration
    return (start, end) if start is not None and end is not None and end > start else None


def group_for(row):
    if row["case_id"] == "C00_clean_normal" or row["domain"] == "SEQUENCE":
        return row["sequence_id"] + "_NATURAL"
    if row["domain"] == "ADDENDUM":
        return row["case_family"] + "_" + str(int(float(row["case_meta_duration_s"]))) + "s"
    return "CORE_" + row["case_family"]


def prepare():
    roots = aliases()
    out = ROOT / OUT_REL
    if (out / "SCAN_MANIFEST.json").exists():
        raise ValueError("Preparation already exists; never silently overwrite its contract")
    index_path = ROOT / RESULT_REL / "V3_RUN_RESULT_INDEX.csv"
    index_data = index_path.read_bytes()
    rows = list(csv.DictReader(index_data.decode("utf-8-sig").splitlines()))
    registry_aliases = sorted({r["registry_source"] for r in rows})
    registries = {}
    metadata_sources = [{"source_path": "<RESULTS_ROOT>/V3_RUN_RESULT_INDEX.csv", "sha256": sha(index_data)}]
    for alias in registry_aliases:
        raw = resolve(alias, roots).read_bytes()
        registries[alias] = json.loads(raw, parse_float=str)
        metadata_sources.append({"source_path": alias, "sha256": sha(raw)})
    bundle_cache = {}
    case_windows = {}
    entries = []
    for row in rows:
        versions = [v for v in ("v3", "v2") if row[v + "_error_series_status"] == "GZIP_PAYLOAD_PRESENT_HEADER_READ"]
        if not versions:
            continue
        registry = registries[row["registry_source"]][int(row["registry_json_pointer"].lstrip("/"))]
        if registry["run_id"] != row["run_id"] or registry["case_id"] != row["case_id"]:
            raise ValueError("Registry identity mismatch")
        key = (row["sequence_id"], row["case_id"])
        if key not in case_windows:
            start, end = map(float, registry["evaluation"]["window"])
            source = row["registry_source"] + "#" + row["registry_json_pointer"] + "/evaluation/window"
            windows = [interval_window("full", start, end, "CLOSED", source)]
            if row["sequence_id"] == "BY2O":
                if (start, end) != (3186.0, 3563.0):
                    raise ValueError("BY2O registered full window changed")
                definition = "<CODE_ROOT>/src/legsa_gins/paper_rebuild/hext/aggregate.py#OCCLUSION_WINDOWS"
                for name, pair in zip(("occlusion_primary", "occlusion_secondary"), OCCLUSIONS):
                    windows.append(interval_window(name, *pair, "CLOSED", definition))
                for name, policy in (("inside_union", "UNION_OF_CLOSED_OCCLUSIONS"),
                                     ("outside", "CLOSED_WINDOW_MINUS_CLOSED_OCCLUSIONS")):
                    windows.append(interval_window(name, start, end, policy, definition))
            if row["domain"] in ("CORE", "ADDENDUM") and row["case_id"] != "C00_clean_normal":
                meta = registry.get("case_meta", {})
                old = old_event_window(meta)
                meta_source = row["registry_source"] + "#" + row["registry_json_pointer"] + "/case_meta"
                if old:
                    a, b = old
                    windows += [interval_window("evaluator_event_pre", start, a, "PRE_STRICT", meta_source),
                                interval_window("evaluator_event_during", a, b, "CLOSED", meta_source),
                                interval_window("evaluator_event_post", b, end, "POST_STRICT", meta_source)]
                # Only this explicitly pinned JSON is opened. No provider payloads.
                bundle_pin = registry.get("frozen_bundle", {})
                bundle_alias = portable(bundle_pin.get("path", ""), roots)
                components = []
                if bundle_alias:
                    if bundle_alias not in bundle_cache:
                        data = resolve(bundle_alias, roots).read_bytes()
                        actual = sha(data)
                        if bundle_pin.get("sha256") and actual != bundle_pin["sha256"]:
                            raise ValueError("Pinned provider-bundle metadata changed: " + bundle_alias)
                        bundle_cache[bundle_alias] = json.loads(data, parse_float=str)
                        metadata_sources.append({"source_path": bundle_alias, "sha256": actual,
                                                 "payload_role": "JSON_METADATA_ONLY"})
                    components = bundle_cache[bundle_alias].get("components", [])
                intervals = {}
                for ci, component in enumerate(components):
                    details = component.get("details", {})
                    pairs = details.get("intervals", [])
                    pair_key = "intervals"
                    if "interval" in details:
                        pairs = [details["interval"]]
                        pair_key = "interval"
                    for pi, pair in enumerate(pairs):
                        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                            continue
                        a, b = map(float, pair)
                        if not b > a:
                            raise ValueError("Invalid registered component interval")
                        role = "registered_recovery" if component.get("component") == "clean_recovery_interval" else "registered_fault"
                        loc = bundle_alias + f"#/components/{ci}/details/{pair_key}" + (f"/{pi}" if pair_key == "intervals" else "")
                        intervals.setdefault((role, a, b), []).append(loc)
                if row["domain"] == "ADDENDUM" and not any(k[0] == "registered_fault" for k in intervals):
                    a, b = float(meta["outage_start_s"]), float(meta["outage_end_s"])
                    intervals[("registered_fault", a, b)] = [meta_source]
                for wi, ((role, a, b), sources) in enumerate(sorted(intervals.items())):
                    name = role + f"_{wi + 1:02d}"
                    windows.append(interval_window(name, a, b, "HALF_OPEN", ";".join(sources)))
                    if role == "registered_fault":
                        windows += [interval_window(name + "_pre", start, a, "PRE_STRICT", ";".join(sources)),
                                    interval_window(name + "_post", b, end, "POST_INCLUSIVE", ";".join(sources))]
            case_windows[key] = windows
        for version in versions:
            entry = {k: row[k] for k in ("run_id", "sequence_id", "domain", "case_id", "case_family",
                                         "seed_index", "method_id", "effective_profile", "data_mode")}
            entry.update(file_id=row["run_id"] + "__" + version, group=group_for(row),
                         evaluator_version=version, payload_kind="error_series", windows=case_windows[key],
                         source_path=row[version + "_error_series_path"],
                         recorded_uncompressed_sha256=row[version + "_error_series_recorded_source_sha256"],
                         evaluation_result_source=row[version + "_evaluation_result_path"],
                         evaluation_result_sha256=row[version + "_evaluation_result_recorded_source_sha256"],
                         summary_source=row[version + "_evaluator_summary_path"],
                         summary_sha256=row[version + "_evaluator_summary_recorded_source_sha256"],
                         registry_source=row["registry_source"], registry_pointer=row["registry_json_pointer"],
                         original_native_status=row["native_status"], original_evaluation_status=row[version + "_status"])
            if not entry["source_path"].startswith("<V3_ROOT>/04_EVALUATION/") or not entry["source_path"].endswith("/error_series.csv.gz"):
                raise ValueError("Unexpected indexed error-series location")
            entries.append(entry)
            matched = row.get(version + "_matched_trajectory_path", "unknown")
            if matched not in ("", "unknown") and row.get(version + "_matched_trajectory_status") == "GZIP_PAYLOAD_PRESENT_HEADER_READ":
                companion = dict(entry)
                companion.update(file_id=entry["file_id"] + "__matched", payload_kind="matched_trajectory",
                                 source_path=matched, recorded_uncompressed_sha256=row[version + "_matched_trajectory_recorded_source_sha256"],
                                 matched_manifest_source=row[version + "_matched_trajectory_manifest_path"],
                                 matched_manifest_sha256=row[version + "_matched_trajectory_manifest_recorded_source_sha256"],
                                 companion_error_file_id=entry["file_id"])
                entries.append(companion)
    if Counter(e["payload_kind"] for e in entries) != {"error_series": 2308, "matched_trajectory": 1}:
        raise ValueError("Retained payload count changed; report before scanning")
    if len({e["source_path"] for e in entries}) != len(entries):
        raise ValueError("Same payload path registered more than once")
    group_order = ["BY2_NATURAL", "BY2H_NATURAL", "BY2O_NATURAL"]
    group_order += ["CORE_" + family for family in ("gnss_outage", "gnss_sampling", "position_value",
                     "position_std_status", "dual_yaw", "velocity_raw_doppler", "go2_prior_metadata", "multi_source_mixed")]
    group_order += ["A1_10s", "A1_20s", "A1_30s", "A2_10s", "A2_20s"]
    for path in SOURCE_DEFINITIONS:
        metadata_sources.append({"source_path": "<CODE_ROOT>/" + path, "sha256": sha((ROOT / path).read_bytes()),
                                 "payload_role": "STATIC_SOURCE_ONLY_NOT_EXECUTED"})
    evaluator = "<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py"
    eval_sha = sha(resolve(evaluator, roots).read_bytes())
    if eval_sha != "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da":
        raise ValueError("Frozen evaluator static source hash mismatch")
    metadata_sources.append({"source_path": evaluator, "sha256": eval_sha,
                             "payload_role": "STATIC_SOURCE_ONLY_NOT_EXECUTED"})
    manifest = {"schema_version": 1, "prepared_at_utc": utc(), "data_mode": "mixed_existing_source_modes_separated_by_row",
                "synthetic_data_used": False, "semisynthetic_data_used": True, "semisynthetic_data_generated": False,
                "validation_calculation": True, "prior_collection_receipt_unchanged": True,
                "absolute_tolerance": ABS_TOL, "relative_tolerance": REL_TOL, "time_tolerance_s": TIME_TOL,
                "integer_tolerance": 0, "group_order": group_order, "group_counts": dict(Counter(e["group"] for e in entries)),
                "metadata_sources": metadata_sources, "entries": entries}
    write_json_new(out / "SCAN_MANIFEST.json", manifest)
    write_json_new(out / "PREPARATION_RECEIPT.json", {"status": "PREPARED_NO_SERIES_BODY_READ",
        "prepared_at_utc": utc(), "scan_manifest_sha256": sha((out / "SCAN_MANIFEST.json").read_bytes()),
        "script_sha256": sha(Path(__file__).read_bytes()), "group_order": group_order,
        "group_counts": manifest["group_counts"], "retained_error_series_count": 2308, "retained_matched_count": 1,
        "provider_bundle_metadata_files_read": len(bundle_cache), "metadata_source_count": len(metadata_sources),
        "data_mode": manifest["data_mode"], "synthetic_data_used": False, "semisynthetic_data_used": True,
        "semisynthetic_data_generated": False, "series_body_reads": 0,
        "solver_calls": 0, "provider_generator_calls": 0, "original_evaluator_calls": 0,
        "controller_calls": 0, "raw_reference_payload_opens": 0, "nav_std_payload_opens": 0})
    print(json.dumps({"status": "PREPARED_NO_SERIES_BODY_READ", "group_counts": manifest["group_counts"]}), flush=True)


def percentile(ordered, q):
    h = (len(ordered) - 1) * q
    low = int(math.floor(h))
    high = int(math.ceil(h))
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (h - low)


def full_stats(times, values, signed):
    n = len(values)
    if not n:
        return {}
    absolute = sorted(abs(x) for x in values)
    mean = math.fsum(values) / n
    squared_sum = math.fsum(x * x for x in values)
    iae = math.fsum((abs(values[i - 1]) + abs(values[i])) * (times[i] - times[i - 1]) / 2 for i in range(1, n))
    ise = math.fsum((values[i - 1] ** 2 + values[i] ** 2) * (times[i] - times[i - 1]) / 2 for i in range(1, n))
    result = {"rmse": math.sqrt(squared_sum / n), "mae": math.fsum(absolute) / n, "iae": iae, "ise": ise}
    if signed:
        result.update(signed_mean=mean, bias=mean, signed_median=percentile(sorted(values), .5),
                      standard_deviation=math.sqrt(math.fsum((x - mean) ** 2 for x in values) / n),
                      median_absolute_error=percentile(absolute, .5), max_absolute=absolute[-1],
                      final_signed_error=values[-1], final_absolute_error=abs(values[-1]))
        result.update({f"p{int(q * 100)}_absolute": percentile(absolute, q) for q in (.5, .75, .9, .95, .99)})
    else:
        result.update(mean=mean, median=percentile(sorted(values), .5), max=absolute[-1], final=abs(values[-1]))
        result.update({f"p{int(q * 100)}": percentile(absolute, q) for q in (.5, .75, .9, .95, .99)})
    return result


def all_full_metrics(columns):
    times = columns["time"]
    result = {}
    for specs, signed in ((AXES, True), (NORMS, False)):
        for prefix, unit, field in specs:
            result.update({f"{prefix}_{stat}_{unit}": value for stat, value in full_stats(times, columns[field], signed).items()})
    return result


def read_payload_once(entry, roots, scan_state):
    path = resolve(entry["source_path"], roots)
    if path.is_symlink():
        raise ValueError("Payload symlink not allowed")
    expected = ERROR_COLUMNS if entry["payload_kind"] == "error_series" else MATCHED_COLUMNS
    before = path.stat()
    scan_state["compressed_size_bytes"] = before.st_size
    digest = hashlib.sha256()
    uncompressed_bytes = 0
    cols = {name: array("d") for name in expected}
    bad = {name: {"non_numeric_count": 0, "nan_count": 0, "positive_infinity_count": 0, "negative_infinity_count": 0} for name in expected}
    with gzip.open(path, "rb") as stream:
        scan_state["main_scan_count"] = 1
        def lines():
            nonlocal uncompressed_bytes
            for raw in stream:
                digest.update(raw)
                uncompressed_bytes += len(raw)
                scan_state["uncompressed_size_bytes_read"] = uncompressed_bytes
                yield raw.decode("utf-8-sig" if uncompressed_bytes == len(raw) else "utf-8")
        reader = csv.reader(lines())
        header = next(reader)
        scan_state["read_depth"] = "HEADER_READ"
        if header != expected:
            raise ValueError("Payload header differs from frozen schema")
        for line_number, fields in enumerate(reader, 2):
            scan_state["payload_read_completion"] = "PARTIAL_BODY_READ"
            if len(fields) != len(expected):
                raise ValueError("CSV field count differs at line " + str(line_number))
            for name, text in zip(expected, fields):
                try:
                    value = float(text)
                except ValueError:
                    bad[name]["non_numeric_count"] += 1
                    value = math.nan
                if math.isnan(value):
                    bad[name]["nan_count"] += 1
                elif value == math.inf:
                    bad[name]["positive_infinity_count"] += 1
                elif value == -math.inf:
                    bad[name]["negative_infinity_count"] += 1
                cols[name].append(value)
            scan_state["complete_rows_parsed_before_error"] = line_number - 1
    scan_state.update(read_depth="FULL_PAYLOAD_READ", payload_read_completion="EOF_REACHED_CRC_CHECKED",
                      row_count=len(cols["time"]), newly_verified_uncompressed_sha256=digest.hexdigest())
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Source changed during the one allowed scan")
    quality = []
    for name, values in cols.items():
        finite = [x for x in values if math.isfinite(x)]
        quality.append({**identity(entry), "field": name, "row_count": len(values), "finite_count": len(finite),
                        **bad[name], "finite_min": min(finite) if finite else None,
                        "finite_max": max(finite) if finite else None,
                        "negative_count": sum(x < 0 for x in finite)})
    times = cols["time"]
    finite_times = [x for x in times if math.isfinite(x)]
    dt = [b - a for a, b in zip(times, times[1:]) if math.isfinite(a) and math.isfinite(b)]
    positive = sorted(x for x in dt if x > 0)
    info = {**identity(entry), "source_path": entry["source_path"],
            "evaluation_result_source": entry["evaluation_result_source"], "summary_source": entry["summary_source"],
            "registry_source": entry["registry_source"], "registry_pointer": entry["registry_pointer"],
            "read_depth": "FULL_PAYLOAD_READ", "eof_receipt": "FULL_STREAM_TO_GZIP_EOF_CRC_CHECKED", "main_scan_count": 1,
            "payload_read_completion": "EOF_REACHED_CRC_CHECKED",
            "compressed_size_bytes": before.st_size, "uncompressed_size_bytes": uncompressed_bytes,
            "recorded_uncompressed_sha256": entry["recorded_uncompressed_sha256"],
            "newly_verified_uncompressed_sha256": digest.hexdigest(),
            "sha256_status": "MATCH" if digest.hexdigest() == entry["recorded_uncompressed_sha256"] else "DIFFERENCE",
            "row_count": len(times), "column_count": len(expected), "nonfinite_cell_count": sum(len(times) - q["finite_count"] for q in quality),
            "duplicate_timestamp_count": len(finite_times) - len(set(finite_times)),
            "nonincreasing_adjacent_timestamp_count": sum(x <= 0 for x in dt),
            "backward_timestamp_count": sum(x < 0 for x in dt),
            "time_start": times[0] if times and math.isfinite(times[0]) else None,
            "time_end": times[-1] if times and math.isfinite(times[-1]) else None,
            "minimum_positive_interval_s": positive[0] if positive else None,
            "median_positive_interval_s": percentile(positive, .5) if positive else None,
            "maximum_positive_interval_s": positive[-1] if positive else None,
            "interval_over_0p01s_count": sum(x > .01 for x in dt),
            "interval_over_0p1s_count": sum(x > .1 for x in dt),
            "interval_over_1s_count": sum(x > 1 for x in dt),
            "timestamp_double_stream_sha256": sha(b"".join(struct.pack(">d", t) for t in times)),
            "source_metadata_unchanged_during_read": True}
    if entry["payload_kind"] == "matched_trajectory":
        info["matched_manifest_source"] = entry["matched_manifest_source"]
    return cols, info, quality


def add_check(rows, entry, field, recorded, check, denominator, source, pointer, *, integer=False, time=False,
              status=None, reason="SAME_RETAINED_FIELDS_SUPPORT_AND_FROZEN_DEFINITION", numerator=""):
    tolerance = 0 if integer else TIME_TOL if time else (ABS_TOL + REL_TOL * abs(float(recorded))) if as_number(recorded) is not None else None
    difference = None
    if status is None:
        if recorded is None and check is None:
            status = "MATCH_NULL"
        elif as_number(recorded) is not None and as_number(check) is not None:
            difference = float(check) - float(recorded)
            status = "MATCH" if abs(difference) <= tolerance else "DIFFERENCE"
        elif source_value(recorded) == source_value(check):
            status = "MATCH"
        else:
            status = "DIFFERENCE"
    rows.append({**identity(entry), "metric": field, "recorded_source": source, "recorded_pointer_or_row_key": pointer,
                 "recorded_value": source_value(recorded), "check_value": source_value(check),
                 "denominator": denominator, "numerator": numerator, "difference_check_minus_recorded": difference,
                 "allowed_absolute_difference": tolerance, "tolerance_rule": "INTEGER_EXACT" if integer else "TIME_ABS_1e-9" if time else "ABS_1e-10_PLUS_REL_1e-10_TIMES_ABS_RECORDED",
                 "source_precision": "PANDAS_DEFAULT_FLOAT_CSV_NO_FLOAT_FORMAT;JSON_NUMERIC_LEXEME_PRESERVED",
                 "status": status, "reason": reason, "validation_calculation": True})


def metadata_for(entry, roots):
    result_path = resolve(entry["evaluation_result_source"], roots)
    data = result_path.read_bytes()
    if sha(data) != entry["evaluation_result_sha256"]:
        raise ValueError("Evaluation JSON changed since collection")
    result = json.loads(data, parse_float=str)["row"]
    if result["run_id"] != entry["run_id"] or result["method_id"] != entry["method_id"]:
        raise ValueError("Evaluation JSON identity differs")
    raw = resolve(entry["summary_source"], roots).read_bytes()
    if sha(raw) != entry["summary_sha256"]:
        raise ValueError("Evaluator summary changed since collection")
    return result, json.loads(raw, parse_float=str)


def mask_indices(times, window, full):
    a, b, policy = window["start_s"], window["end_s"], window["endpoint_policy"]
    result = []
    for i, t in enumerate(times):
        if not full["start_s"] <= t <= full["end_s"]:
            continue
        if policy == "CLOSED":
            keep = a <= t <= b
        elif policy == "HALF_OPEN":
            keep = a <= t < b
        elif policy == "PRE_STRICT":
            keep = t < b
        elif policy == "POST_STRICT":
            keep = t > a
        elif policy == "POST_INCLUSIVE":
            keep = t >= a
        elif policy == "UNION_OF_CLOSED_OCCLUSIONS":
            keep = any(x <= t <= y for x, y in OCCLUSIONS)
        elif policy == "CLOSED_WINDOW_MINUS_CLOSED_OCCLUSIONS":
            keep = not any(x <= t <= y for x, y in OCCLUSIONS)
        else:
            raise ValueError("Unknown fixed endpoint policy")
        if keep:
            result.append(i)
    return result


def window_summaries(entry, columns):
    out = []
    times = columns["time"]
    for window in entry["windows"]:
        ix = mask_indices(times, window, entry["windows"][0])
        count = len(ix)
        row = {**identity(entry), **window, "matched_epoch_count": count,
               "first_matched_time_s": times[ix[0]] if ix else None,
               "last_matched_time_s": times[ix[-1]] if ix else None,
               "selected_support_blocks": 1 + sum(b != a + 1 for a, b in zip(ix, ix[1:])) if ix else 0,
               "maximum_selected_adjacent_interval_s": max((times[b] - times[a] for a, b in zip(ix, ix[1:])), default=None),
               "validation_calculation": True,
               "role": "CHECK_OF_EXISTING_FULL_WINDOW" if window["window_id"] == "full" else "FIXED_WINDOW_VALIDATION_DERIVED_NOT_ORIGINAL_V3_RUN_METRIC",
               "status": "AVAILABLE" if count else "EMPTY_FIXED_WINDOW_NO_METRIC",
               "integrals": "NOT_CALCULATED_FOR_WINDOW_SUMMARY;NO_GAP_INTERPOLATION"}
        for prefix, unit, field in AXES + NORMS:
            values = [columns[field][i] for i in ix]
            if not values:
                continue
            absolute = sorted(abs(v) for v in values)
            mean = math.fsum(values) / count
            row[f"{prefix}_rmse_{unit}"] = math.sqrt(math.fsum(v * v for v in values) / count)
            row[f"{prefix}_mean_{unit}"] = mean
            row[f"{prefix}_p95_absolute_{unit}"] = percentile(absolute, .95)
            row[f"{prefix}_max_absolute_{unit}"] = absolute[-1]
            row[f"{prefix}_final_signed_{unit}"] = values[-1]
            if prefix == "yaw":
                row["yaw_median_absolute_deg"] = percentile(absolute, .5)
                row["yaw_p99_absolute_deg"] = percentile(absolute, .99)
                row["yaw_standard_deviation_deg"] = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / count)
        out.append(row)
    return out


def summary_checks(entry, cols, metrics, recorded, checks):
    n = len(cols["time"])
    aliases_map = {"vertical_p95_m": "up_p95_absolute_m", "vertical_max_m": "up_max_absolute_m"}
    for axis in ("roll", "pitch", "yaw"):
        aliases_map[axis + "_p95_deg"] = axis + "_p95_absolute_deg"
        aliases_map[axis + "_max_deg"] = axis + "_max_absolute_deg"
    for category in ("position", "attitude"):
        for key, value in recorded.get(category, {}).items():
            numerator = ""
            if key.endswith("_pass_ratio"):
                prefix = key.removesuffix("_pass_ratio")
                field, threshold = {"horizontal": ("horizontal_err_m", 2.0), "vertical": ("err_u_m", 3.0),
                                    "roll": ("roll_err_deg", 1.0), "pitch": ("pitch_err_deg", 1.0),
                                    "yaw": ("yaw_err_deg", 2.0)}[prefix]
                numerator = sum(abs(v) <= threshold for v in cols[field])
                check = numerator / n
            else:
                check = metrics[aliases_map.get(key, key)]
            add_check(checks, entry, category + "/" + key, value, check, n, "@summary", f"/{category}/{key}", numerator=numerator)
    for key, value in recorded.get("consistency_3sigma", {}).items():
        prefix = key.removesuffix("_in_3sigma_ratio")
        field = "horizontal_err_m" if prefix == "horizontal" else prefix + "_err_deg"
        sigma = prefix + ("_3sigma_m" if prefix == "horizontal" else "_3sigma_deg")
        numerator = sum(abs(v) <= s for v, s in zip(cols[field], cols[sigma]))
        add_check(checks, entry, "consistency_3sigma/" + key, value, numerator / n, n, "@summary", "/consistency_3sigma/" + key, numerator=numerator)
    start = None
    convergence = None
    for i, t in enumerate(cols["time"]):
        if abs(cols["horizontal_err_m"][i]) <= 2.0 and abs(cols["yaw_err_deg"][i]) <= 2.0:
            if start is None:
                start = t
            if t - start >= 3.0:
                convergence = start - cols["time"][0]
                break
        else:
            start = None
    for key, value in recorded.get("convergence", {}).items():
        add_check(checks, entry, "convergence/" + key, value, convergence, n, "@summary", "/convergence/" + key, time=True)
    meta_checks = {"num_samples": n, "time_start": cols["time"][0], "time_end": cols["time"][-1],
                   "duration_sec": cols["time"][-1] - cols["time"][0]}
    for key, value in recorded.get("meta", {}).items():
        if key in meta_checks:
            add_check(checks, entry, "meta/" + key, value, meta_checks[key], n, "@summary", "/meta/" + key,
                      integer=key == "num_samples", time=key != "num_samples")
        else:
            add_check(checks, entry, "meta/" + key, value, None, "unknown", "@summary", "/meta/" + key,
                      status="NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS", reason="Original absolute-time origin/reference heading construction is not encoded in error fields")


def validate_error(entry, roots, segment_targets, scan_state):
    recorded, summary = metadata_for(entry, roots)
    cols, info, quality = read_payload_once(entry, roots, scan_state)
    checks = []
    windows = []
    n = len(cols["time"])
    valid = n > 0 and info["nonfinite_cell_count"] == 0 and info["nonincreasing_adjacent_timestamp_count"] == 0
    if valid:
        metrics = all_full_metrics(cols)
        for key, value in metrics.items():
            add_check(checks, entry, key, recorded.get(key), value, n, "@evaluation_result", "/row/" + key,
                      status=None if key in recorded else "NO_RECORDED_TARGET")
        for key, value in (("matched_epoch_count", n), ("time_start", cols["time"][0]), ("time_end", cols["time"][-1])):
            add_check(checks, entry, key, recorded.get(key), value, n, "@evaluation_result", "/row/" + key,
                      integer=key == "matched_epoch_count", time=key != "matched_epoch_count")
        summary_checks(entry, cols, metrics, summary, checks)
        windows = window_summaries(entry, cols)
        full = entry["windows"][0]
        outside = sum(not full["start_s"] <= t <= full["end_s"] for t in cols["time"])
        add_check(checks, entry, "epochs_outside_registered_full_window", 0, outside, n, "@registry", entry["registry_pointer"] + "/evaluation/window",
                  integer=True, reason="Containment check; interval endpoints remain the frozen registry values")
        for target in segment_targets:
            if target["method_id"] != entry["method_id"] or target["evaluator_contract"] != "evaluator_contract_" + entry["evaluator_version"]:
                continue
            window = next(x for x in windows if x["window_id"] == target["segment_id"])
            mapping = {"count": "matched_epoch_count", "h_rmse_m": "horizontal_rmse_m",
                       "yaw_p95_absolute_deg": "yaw_p95_absolute_deg", "yaw_median_absolute_deg": "yaw_median_absolute_deg"}
            mapping.update({k: k for k in ("position_3d_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg")})
            for column, check_name in mapping.items():
                add_check(checks, entry, "BY2O/" + target["segment_id"] + "/" + column, target[column], window.get(check_name),
                          window["matched_epoch_count"], target["_source_path"], target["_source_row_key"] + ";column=" + column,
                          integer=column == "count", reason="Existing BY2O Protocol V3 segment table; same explicit closed mask")
    else:
        for key in recorded:
            if any(key.startswith(prefix + "_") for prefix, _, _ in AXES + NORMS) or key in ("matched_epoch_count", "time_start", "time_end"):
                add_check(checks, entry, key, recorded[key], None, n, "@evaluation_result", "/row/" + key,
                          status="NOT_COMPARABLE_INVALID_RETAINED_SUPPORT", reason="Empty/nonfinite/nonchronological series; no epoch filtering or repair permitted")
    for key in ("output_epoch_count", "reference_epoch_count", "unmatched_epoch_count", "coverage_ratio", "finite_output", "finite_ratio", "evaluation_runtime_seconds"):
        if key in recorded:
            add_check(checks, entry, key, recorded[key], None, "unknown", "@evaluation_result", "/row/" + key,
                      status="NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS", reason="Retained errors contain matched epochs only; original NAV/reference/process support is unavailable here")
    info["metric_status_counts"] = json.dumps(dict(Counter(x["status"] for x in checks)), sort_keys=True)
    info["window_count"] = len(windows)
    info["numeric_validation_status"] = "NUMERICALLY_CHECKED_WITHIN_SCOPE" if valid else "NOT_COMPARABLE_INVALID_RETAINED_SUPPORT"
    info["validation_status"] = "COMPLETE_WITH_DIFFERENCES" if any(c["status"] == "DIFFERENCE" for c in checks) or info["sha256_status"] != "MATCH" else "COMPLETE_INVALID_SUPPORT" if not valid else "COMPLETE_WITHIN_PREDECLARED_TOLERANCE"
    return {"file": info, "checks": checks, "windows": windows, "quality": quality}, cols


def validate_matched(entry, roots, error_columns, scan_state):
    recorded, _ = metadata_for(entry, roots)
    raw = resolve(entry["matched_manifest_source"], roots).read_bytes()
    if sha(raw) != entry["matched_manifest_sha256"]:
        raise ValueError("Matched manifest changed since collection")
    manifest = json.loads(raw, parse_float=str)
    cols, info, quality = read_payload_once(entry, roots, scan_state)
    checks = []
    n = len(cols["time"])
    valid = n > 0 and info["nonfinite_cell_count"] == 0 and info["nonincreasing_adjacent_timestamp_count"] == 0
    add_check(checks, entry, "matched_epoch_count", manifest["matched_epoch_count"], n, n, "@matched_manifest", "/matched_epoch_count", integer=True)
    if valid:
        wrapped = array("d", ((estimate - truth + 180.0) % 360.0 - 180.0 for estimate, truth in zip(cols["estimate_yaw_deg"], cols["truth_yaw_deg"])))
        for stat, value in full_stats(cols["time"], wrapped, True).items():
            key = "yaw_" + stat + "_deg"
            add_check(checks, entry, key, recorded.get(key), value, n, "@evaluation_result", "/row/" + key,
                      reason="Independent wrapped estimate_yaw minus truth_yaw; matched display fields only")
        for key, value in (("time_start", cols["time"][0]), ("time_end", cols["time"][-1])):
            add_check(checks, entry, key, recorded[key], value, n, "@evaluation_result", "/row/" + key, time=True)
        companion_valid = (error_columns is not None and len(error_columns["time"]) > 0
                           and all(math.isfinite(v) for field in ("time", "yaw_err_deg") for v in error_columns[field])
                           and all(b > a for a, b in zip(error_columns["time"], error_columns["time"][1:])))
        same_count = companion_valid and len(error_columns["time"]) == n
        add_check(checks, entry, "error_series_row_count", len(error_columns["time"]) if error_columns is not None else None,
                  n, n, "@companion_error_series", "row_count", integer=True,
                  status=None if companion_valid else "NOT_COMPARABLE_INVALID_RETAINED_SUPPORT",
                  reason="Companion finite strictly ordered support required; no row filtering")
        if same_count:
            time_difference = max(abs(a - b) for a, b in zip(cols["time"], error_columns["time"]))
            yaw_difference = max(abs(a - b) for a, b in zip(wrapped, error_columns["yaw_err_deg"]))
            time_bad = sum(abs(a - b) > TIME_TOL for a, b in zip(cols["time"], error_columns["time"]))
            yaw_bad = sum(abs(a - b) > ABS_TOL + REL_TOL * abs(b) for a, b in zip(wrapped, error_columns["yaw_err_deg"]))
            add_check(checks, entry, "paired_epoch_time_mismatch_count", 0, time_bad, n, "@companion_error_series", "time[row]", integer=True,
                      reason="Every row paired once in memory; maximum absolute difference=" + repr(time_difference))
            add_check(checks, entry, "paired_epoch_wrapped_yaw_mismatch_count", 0, yaw_bad, n, "@companion_error_series", "yaw_err_deg[row]", integer=True,
                      reason="Every row paired once in memory; maximum absolute difference=" + repr(yaw_difference))
            info["paired_time_maximum_absolute_difference_s"] = time_difference
            info["paired_wrapped_yaw_maximum_absolute_difference_deg"] = yaw_difference
        else:
            for metric in ("paired_epoch_time_mismatch_count", "paired_epoch_wrapped_yaw_mismatch_count"):
                add_check(checks, entry, metric, None, None, n, "@companion_error_series", "paired_rows",
                          status="NOT_COMPARABLE_INVALID_RETAINED_SUPPORT",
                          reason="Companion unavailable, nonfinite, nonchronological or different row count; no silent NaN comparison")
    for key in ("horizontal_rmse_m", "position_3d_rmse_m", "up_rmse_m", "roll_rmse_deg", "pitch_rmse_deg"):
        add_check(checks, entry, key, recorded.get(key), None, n, "@evaluation_result", "/row/" + key,
                  status="NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS", reason="Matched export lacks error/projection or roll/pitch fields; no new geodetic projection authorized")
    info["companion_error_file_id"] = entry["companion_error_file_id"]
    info["metric_status_counts"] = json.dumps(dict(Counter(x["status"] for x in checks)), sort_keys=True)
    info["window_count"] = 0
    info["numeric_validation_status"] = "NUMERICALLY_CHECKED_WITHIN_SCOPE" if valid else "NOT_COMPARABLE_INVALID_RETAINED_SUPPORT"
    info["validation_status"] = "COMPLETE_WITH_DIFFERENCES" if any(c["status"] == "DIFFERENCE" for c in checks) or info["sha256_status"] != "MATCH" else "COMPLETE_INVALID_SUPPORT" if not valid else "COMPLETE_WITHIN_PREDECLARED_TOLERANCE"
    return {"file": info, "checks": checks, "windows": [], "quality": quality}


def initial_scan_state(entry):
    return {**identity(entry), "source_path": entry["source_path"],
            "evaluation_result_source": entry["evaluation_result_source"], "summary_source": entry["summary_source"],
            "registry_source": entry["registry_source"], "registry_pointer": entry["registry_pointer"],
            "read_depth": "INDEXED_ONLY", "payload_read_completion": "NOT_OPENED",
            "main_scan_count": 0, "complete_rows_parsed_before_error": 0,
            "recorded_uncompressed_sha256": entry["recorded_uncompressed_sha256"]}


def failed_file(entry, state, reason, contract):
    info = {**state, "validation_status": "UNREADABLE_OR_INCOMPLETE_NO_REREAD",
            "numeric_validation_status": "NOT_NUMERICALLY_CHECKED", "failure_reason": reason,
            "row_count": state.get("row_count", "unknown"), "sha256_status": "NOT_COMPARABLE_READ_INCOMPLETE",
            "metric_status_counts": "{}", "window_count": 0}
    return {"file": info, "checks": [], "windows": [], "quality": [],
            "contract": contract, "completed_at_utc": utc()}


def one_job(job):
    entry, companion, roots, checkpoints, segment_targets, contract = job
    outputs = []
    cols = None
    for item in (entry, companion):
        if item is None:
            continue
        state = initial_scan_state(item)
        write_json_new(Path(checkpoints) / (item["file_id"] + ".STARTED.json"),
                       {"started_at_utc": utc(), "file_id": item["file_id"], "source_path": item["source_path"], **contract})
        try:
            if item["payload_kind"] == "error_series":
                result, cols = validate_error(item, roots, segment_targets, state)
            else:
                result = validate_matched(item, roots, cols, state)
            result["completed_at_utc"] = utc()
            result["contract"] = contract
        except Exception as exc:
            reason = portable(type(exc).__name__ + ": " + str(exc), roots)
            result = failed_file(item, state, reason, contract)
        write_json_new(Path(checkpoints) / (item["file_id"] + ".COMPLETE.json"), result)
        outputs.append(result)
    return outputs


def write_csv_new(path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_group(args):
    if not re.fullmatch(r"[0-9a-f]{40}", args.preparation_commit or ""):
        raise ValueError("Provide supervisor-confirmed published preparation commit")
    if args.group_release != "SUPERVISOR_RELEASED:" + args.group:
        raise ValueError("Explicit per-group supervisor release is required")
    if not 1 <= args.workers <= 4:
        raise ValueError("Use one to four workers")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    out = ROOT / OUT_REL
    raw_manifest = (out / "SCAN_MANIFEST.json").read_bytes()
    manifest = json.loads(raw_manifest)
    prep = json.loads((out / "PREPARATION_RECEIPT.json").read_bytes())
    if sha(raw_manifest) != prep["scan_manifest_sha256"] or sha(Path(__file__).read_bytes()) != prep["script_sha256"]:
        raise ValueError("Prepared script/manifest identity changed before scan")
    if args.group not in manifest["group_order"]:
        raise ValueError("Unknown group")
    for previous in manifest["group_order"][:manifest["group_order"].index(args.group)]:
        if not (out / previous / "RECEIPT.json").exists():
            raise ValueError("Earlier group has no completed receipt: " + previous)
    destination = out / args.group
    if (destination / "RECEIPT.json").exists():
        raise ValueError("Group already completed; no second payload scan")
    roots = aliases()
    entries = [e for e in manifest["entries"] if e["group"] == args.group]
    checkpoints = out / ".checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    contract = {"preparation_commit": args.preparation_commit, "group_release": args.group_release,
                "scan_manifest_sha256": sha(raw_manifest), "script_sha256": prep["script_sha256"]}
    completed = {}
    for entry in entries:
        done = checkpoints / (entry["file_id"] + ".COMPLETE.json")
        started = checkpoints / (entry["file_id"] + ".STARTED.json")
        if done.exists():
            completed[entry["file_id"]] = json.loads(done.read_bytes())
            cached = completed[entry["file_id"]]
            if (cached["contract"]["scan_manifest_sha256"] != contract["scan_manifest_sha256"]
                    or cached["contract"]["script_sha256"] != contract["script_sha256"]
                    or cached["file"]["file_id"] != entry["file_id"]
                    or cached["file"]["source_path"] != entry["source_path"]):
                raise ValueError("Checkpoint contract/identity mismatch; no source reread")
        elif started.exists():
            state = initial_scan_state(entry)
            state.update(payload_read_completion="UNKNOWN_INTERRUPTED_NO_REREAD", main_scan_count="unknown")
            completed[entry["file_id"]] = failed_file(entry, state, "Interrupted checkpoint; payload read extent unknown, do not reopen", contract)
    companions = {e["companion_error_file_id"]: e for e in entries if e["payload_kind"] == "matched_trajectory"}
    for error_id, companion in companions.items():
        if (error_id in completed) != (companion["file_id"] in completed):
            missing_id = companion["file_id"] if error_id in completed else error_id
            missing_entry = next(e for e in entries if e["file_id"] == missing_id)
            completed[missing_id] = failed_file(missing_entry, initial_scan_state(missing_entry),
                                               "Unfinished paired scan; independent item unavailable this attempt, no companion reread", contract)
    segment_targets = []
    if args.group == "BY2O_NATURAL":
        with (ROOT / RESULT_REL / "source_tables/BY2O_SEGMENT_TABLE.csv").open(encoding="utf-8-sig", newline="") as stream:
            segment_targets = [row for row in csv.DictReader(stream) if row["variant"] == "PROTOCOL_V3"]
        if len(segment_targets) != 110:
            raise ValueError("BY2O existing Protocol V3 segment table scope changed")
    jobs = [(e, companions.get(e["file_id"]), roots, str(checkpoints), segment_targets, contract)
            for e in entries if e["payload_kind"] == "error_series" and e["file_id"] not in completed]
    started_at = utc()
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(one_job, job): job[0]["file_id"] for job in jobs}
        for future in as_completed(future_map):
            try:
                for item in future.result():
                    completed[item["file"]["file_id"]] = item
            except Exception as exc:
                failed_id = future_map[future]
                for entry in [e for e in entries if e["file_id"] == failed_id or e.get("companion_error_file_id") == failed_id]:
                    done = checkpoints / (entry["file_id"] + ".COMPLETE.json")
                    if done.exists():
                        completed[entry["file_id"]] = json.loads(done.read_bytes())
                    else:
                        state = initial_scan_state(entry)
                        state.update(payload_read_completion="UNKNOWN_WORKER_FAILURE_NO_REREAD", main_scan_count="unknown")
                        completed[entry["file_id"]] = failed_file(entry, state, portable(str(exc), roots), contract)
            print(json.dumps({"group": args.group, "completed_files": len(completed), "expected_files": len(entries),
                              "just_completed": future_map[future]}), flush=True)
    ordered = [completed[e["file_id"]] for e in entries]
    destination.mkdir(parents=True, exist_ok=True)
    tables = {"FILE_CHECKS.csv": [x["file"] for x in ordered],
              "METRIC_CHECKS.csv": [v for x in ordered for v in x["checks"]],
              "WINDOW_SUMMARY.csv": [v for x in ordered for v in x["windows"]],
              "FIELD_QUALITY.csv": [v for x in ordered for v in x["quality"]]}
    for filename, rows in tables.items():
        write_csv_new(destination / filename, rows)
    statuses = Counter(row["status"] for row in tables["METRIC_CHECKS.csv"])
    unreadable = sum(x["file"]["validation_status"] == "UNREADABLE_OR_INCOMPLETE_NO_REREAD" for x in ordered)
    receipt = {"status": "COMPLETE_WITH_UNREADABLE_ITEMS" if unreadable else "GROUP_COMPLETE_STOP_FOR_SUPERVISOR_REVIEW_AND_PUSH", "started_at_utc": started_at,
               "completed_at_utc": utc(), "group": args.group, "expected_files": len(entries),
               "completed_files": len(ordered), "unreadable_or_incomplete_files": unreadable,
               "new_full_stream_reads": sum(x["file"]["read_depth"] == "FULL_PAYLOAD_READ" for x in ordered if any(x["file"]["file_id"] in (job[0]["file_id"], job[1]["file_id"] if job[1] else "") for job in jobs)),
               "checkpoint_reuse_without_payload_open": len(entries) - sum(1 + (job[1] is not None) for job in jobs),
               "compressed_bytes_for_fully_read_files": sum(x["file"]["compressed_size_bytes"] for x in ordered if x["file"]["read_depth"] == "FULL_PAYLOAD_READ"),
               "payload_kind_counts": dict(Counter(x["file"]["payload_kind"] for x in ordered)),
               "uncompressed_row_count_fully_read": sum(x["file"]["row_count"] for x in ordered if x["file"]["read_depth"] == "FULL_PAYLOAD_READ"),
               "metric_check_status_counts": dict(statuses),
               "sha256_status_counts": dict(Counter(x["file"]["sha256_status"] for x in ordered)),
               "data_mode_counts": dict(Counter(x["file"]["data_mode"] for x in ordered)),
               "data_mode": "mixed_existing_source_modes_separated_by_row" if len({x["file"]["data_mode"] for x in ordered}) > 1 else ordered[0]["file"]["data_mode"],
               "synthetic_data_used": False, "semisynthetic_data_used": any(x["file"]["data_mode"] == "semisynthetic" for x in ordered),
               "semisynthetic_data_generated": False, "validation_calculation": True,
               "new_validation_statistic_cells": sum(x["check_value"] != "null" for x in tables["METRIC_CHECKS.csv"]),
               "prior_collection_receipt_unchanged": True, "solver_calls": 0, "provider_generator_calls": 0,
               "original_evaluator_calls": 0, "controller_calls": 0, "raw_reference_payload_opens": 0,
               "nav_std_payload_opens": 0, "source_series_writes": 0, "workers": args.workers,
               "outputs": [{"file": name, "row_count": len(rows), "sha256": sha((destination / name).read_bytes()),
                            "size_bytes": (destination / name).stat().st_size} for name, rows in tables.items()], **contract}
    write_json_new(destination / "RECEIPT.json", receipt)
    print(json.dumps({"status": receipt["status"], "group": args.group, "files": len(ordered), "metric_status_counts": dict(statuses)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    task = parser.add_mutually_exclusive_group(required=True)
    task.add_argument("--prepare", action="store_true", help="Read metadata/static definitions only; no gzip payload")
    task.add_argument("--group")
    parser.add_argument("--preparation-commit")
    parser.add_argument("--group-release")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    prepare() if args.prepare else run_group(args)


if __name__ == "__main__":
    main()
