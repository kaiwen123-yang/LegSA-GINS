"""Single-sequence heading evaluation; one child/reference read, no native runs.

The three new native streams use the frozen HX02 heading functions. HX07R
metrics are quoted, and common support uses retained errors with unique decimal
microsecond keys. Plotting consumes saved derived CSV only and can be retried
independently; it never reopens reference or re-enters evaluation.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import numpy as np

from ..hext import hx02_heading_evaluation as frozen

SCHEMA = "ext_reproduction.heading_evaluation.v1"
METHODS = ("EXT01", "EXT02", "EXT03")
VARIANTS = ("V0", "V0E", "V1", "V2")
SEQUENCES = ("BY2", "BY2H", "BY2O")
MODES = ("native_valid", "ratio_fixed", "causal_held")
MICROSECOND = Decimal("0.000001")
MAX_TIME_DIFFERENCE = MICROSECOND
PLOT_GAP_SECONDS = 0.300001  # 1.5 x the registered 5 Hz cadence + 1 us.
FROZEN_PINS = {
    "src/legsa_gins/paper_rebuild/hext/hx02_heading_evaluation.py":
        "eedb3faf56ccffca222d915c401d3075dc64583ce68a10f08add9f8b705fa994",
    "src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py":
        "85112d34e27f1fa8c3043bdcdeb2f418232cd2fffacb40cab3f387f179db6c9b",
}
# V2 changes only non-metric Phase2 source: raw input identity and failure
# tracking. Its wrap/statistics functions are unchanged from the V1 freeze.
V2_FROZEN_PINS = {**FROZEN_PINS,
    "src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py":
        "b4cece4a634b1d884f0f84284067dc12a96d56fcede804a8a2963ffe35a1f156"}


def frozen_source_pins(native_version):
    if native_version not in ("V1", "V2"):
        raise EvaluationError("unknown native reproduction version")
    return FROZEN_PINS if native_version == "V1" else V2_FROZEN_PINS


MODULE = "legsa_gins.paper_rebuild.horizontal_literature.reproduction_evaluation"
SOURCE_RELATIVE = "src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_evaluation.py"
PROTOCOL_RELATIVE = "docs/paper_rebuild/hext/EXT_REPRODUCTION/EVALUATION_PROTOCOL.md"
V3_TABLE = "<CODE_ROOT>/docs/paper_rebuild/audit_xbpg_20261001/v3_results/run_statistics/NATURAL_C00_ALL_CONFIGS.csv"
HX_FILE_INDEX = "<CODE_ROOT>/docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_hx/EXISTING_HX_FILES.csv"
ERROR_CONVENTION = "wrap180(method_body_yaw_ned - reference_body_yaw_ned)"
REFERENCE_SEMANTICS = "wrap360(90-interp(unwrap(yaw_ENU))) inside trace support; no extrapolation"


class EvaluationError(RuntimeError):
    pass


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def expand(value, roots):
    for alias in sorted(roots, key=len, reverse=True):
        if value == alias or value.startswith(alias + "/"):
            return Path(roots[alias] + value[len(alias):])
    raise EvaluationError("unregistered alias: " + value)


def portable(value, roots):
    text = str(value)
    if text.startswith("<"):
        expand(text, roots)
        return text
    for alias, path in sorted(roots.items(), key=lambda item: len(item[1]), reverse=True):
        if text == path or text.startswith(path + "/"):
            return alias + text[len(path):]
    raise EvaluationError("path outside registered roots")


def sanitize(value, roots):
    text = str(value)
    for alias, path in sorted(roots.items(), key=lambda item: len(item[1]), reverse=True):
        text = text.replace(path, alias)
    return text


def write_json(path, value, *, exclusive=False):
    with Path(path).open("x" if exclusive else "w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows, fields=None):
    columns = fields or list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns or ["status"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def csv_rows(payload):
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))


def number(value):
    if value in (None, ""):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def decimal_time(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise EvaluationError("invalid time literal") from exc
    if not result.is_finite():
        raise EvaluationError("nonfinite time")
    return result


def time_key(value):
    """Nearest microsecond, ties-to-even; never a fitted time shift."""
    return int((decimal_time(value) / MICROSECOND).to_integral_value(rounding=ROUND_HALF_EVEN))


def index_time_rows(rows):
    indexed = {}
    previous = None
    for row in rows:
        current = decimal_time(row["time_unix_s"])
        key = time_key(row["time_unix_s"])
        if key in indexed or (previous is not None and current <= previous):
            raise EvaluationError("duplicate microsecond key or nonincreasing source time")
        indexed[key] = row
        previous = current
    return indexed


def verify_time_pair(rows):
    times = [decimal_time(row["time_unix_s"]) for row in rows]
    if len({time_key(row["time_unix_s"]) for row in rows}) != 1:
        raise EvaluationError("unequal microsecond keys")
    difference = max(times) - min(times)
    if difference > MAX_TIME_DIFFERENCE:
        raise EvaluationError("paired time difference exceeds fixed 1 us limit")
    return float(difference)


def parse_heading(payload):
    rows = csv_rows(payload)
    table = frozen.read_heading_table(payload)
    for key in ("time_unix_s", "gps_tow_seconds"):
        if not np.isfinite(table[key]).all():
            raise EvaluationError("nonfinite heading clock: " + key)
    if any(row["valid"] not in ("0", "1") for row in rows):
        raise EvaluationError("valid must be an explicit 0/1 flag")
    index_time_rows(rows)
    return table, rows


def enrich_series(table, native_rows, rows, *, method, reference=None):
    """Add original yaw, causal source time/age and native statuses; no new fit."""
    positions = {int(row["epoch_index"]): i for i, row in enumerate(native_rows)}
    last = None
    held_positions = []
    for i, valid in enumerate(table["valid"]):
        if valid:
            last = i
        held_positions.append(last)
    result = []
    for original in rows:
        i = positions[int(original["epoch_index"])]
        verify_time_pair([original, native_rows[i]])
        source = held_positions[i]
        row = dict(original)
        row.update(method_id=method, time_key_us=time_key(original["time_unix_s"]),
                   native_body_yaw_deg=native_rows[i]["body_yaw_deg"],
                   solution_state=native_rows[i].get("solution_state", ""),
                   failure_code=native_rows[i].get("failure_code", ""),
                   held_body_yaw_deg="" if source is None else repr(float(table["body_yaw_deg"][source])),
                   hold_source_time_unix_s="" if source is None else native_rows[source]["time_unix_s"],
                   held_age_s="" if source is None else repr(float(table["time_unix_s"][i] - table["time_unix_s"][source])),
                   reference_yaw_ned_deg="" if reference is None or not np.isfinite(reference[i]) else repr(float(reference[i])),
                   source_heading_epoch_index=native_rows[i]["epoch_index"])
        fixed = (int(row.get("ratio_fixed", -1)) == 1 if method in METHODS
                 else int(row.get("rtklib_q", -1)) == 1)
        row["error_ratio_fixed_deg"] = row["error_valid_deg"] if fixed else ""
        for key in ("baseline_n_m", "baseline_e_m", "baseline_d_m", "baseline_length_m",
                    "float_solved", "search_attempted", "search_complete", "candidate_returned",
                    "acceptance_test_defined"):
            row[key] = native_rows[i].get(key, "")
        result.append(row)
    index_time_rows(result)
    return result


def support_details(table, rows, series, base_time, window, fixed_defined):
    times = table["time_unix_s"]
    relative = times - base_time
    in_window = (relative >= window[0]) & (relative <= window[1])
    valid = table["valid"]
    fixed_column = "rtklib_q" if fixed_defined == "RTKLIB_Q1_FIXED" else "ratio_fixed"
    fixed = ((table.get(fixed_column, np.full(times.shape, -1)) == 1) & valid)
    result = {"native_row_count": len(rows), "native_invalid_epochs_in_window": int(np.count_nonzero(in_window & ~valid)),
              "status_counts_in_window_json": json.dumps({state: sum(r.get("solution_state", "") == state
                  for r, inside in zip(rows, in_window) if inside) for state in sorted({r.get("solution_state", "") for r in rows})}, sort_keys=True),
              "fixed_definition": fixed_defined}
    for label, mask in (("valid", valid), ("fixed", fixed)):
        for scope, select in (("native", mask), ("window", mask & in_window)):
            indices = np.flatnonzero(select)
            result[f"first_{label}_{scope}_t_rel_s"] = (float(relative[indices[0]]) if len(indices) else None)
        if label == "fixed" and fixed_defined == "NOT_APPLICABLE_NO_ACCEPTANCE_TEST":
            result["first_fixed_native_t_rel_s"] = result["first_fixed_window_t_rel_s"] = None
    gaps = np.diff(np.r_[float(window[0]), relative[valid & in_window], float(window[1])])
    result["maximum_uncovered_interval_with_window_edges_s"] = float(np.max(gaps))
    result["edge_gap_definition"] = "max gap between window start, native-valid epochs, window end; includes censored edges"
    ages = [number(row["held_age_s"]) for row in series if number(row["held_age_s"]) is not None]
    result.update(held_age_count=len(ages), held_age_max_s=max(ages) if ages else None,
                  held_age_p95_s=float(np.quantile(ages, .95)) if ages else None)
    return result


def validate_reused_support(table, native_rows, errors, metrics, reference_bounds):
    """Validate old support, not old RMSE: every mask/source must match heading."""
    if (metrics["error_convention"] != ERROR_CONVENTION or
            metrics["reference_semantics"] != REFERENCE_SEMANTICS):
        raise EvaluationError("reused frozen error/reference convention mismatch")
    times = table["time_unix_s"]
    relative = times - metrics["base_time"]
    lo, hi = metrics["window_seconds"]
    expected_positions = np.flatnonzero((relative >= lo) & (relative <= hi))
    index_time_rows(errors)
    if len(errors) != len(expected_positions):
        raise EvaluationError("reused error rows do not cover the whole original window")
    last = None
    held = []
    for i, valid in enumerate(table["valid"]):
        if valid: last = i
        held.append(last)
    for row, i in zip(errors, expected_positions, strict=True):
        i = int(i)
        source = held[i]
        if (int(row["epoch_index"]) != int(table["epoch_index"][i]) or
                float(row["time_unix_s"]) != float(times[i]) or float(row["t_rel_s"]) != float(relative[i])):
            raise EvaluationError("reused epoch/time identity mismatch")
        verify_time_pair([row, native_rows[i]])
        supported = reference_bounds[0] <= times[i] <= reference_bounds[1]
        valid = bool(table["valid"][i])
        expected_flags = {"valid": int(valid), "reference_supported": int(supported),
                          "hold_available": int(source is not None),
                          "hold_source_epoch_index": -1 if source is None else int(table["epoch_index"][source]),
                          "rtklib_q": int(table["rtklib_q"][i])}
        if any(int(row[key]) != expected for key, expected in expected_flags.items()):
            raise EvaluationError("reused per-row validity/reference/q/hold-source mismatch")
        if (number(row["error_valid_deg"]) is not None) != (valid and supported):
            raise EvaluationError("reused native error mask mismatch")
        if (number(row["error_hold_deg"]) is not None) != (source is not None and supported):
            raise EvaluationError("reused held error mask mismatch")


def metric_rows(sequence, method, metrics, details, source, *, reused=False):
    rows = []
    defined = details["fixed_definition"]
    for mode in MODES:
        if mode == "native_valid":
            values = metrics["valid"]
            available = metrics["valid_epochs_in_window"]
            pointer = "/valid"
        elif mode == "causal_held":
            values = metrics["hold_last_valid"]
            available = values["held_epochs_in_window"]
            pointer = "/hold_last_valid"
        else:
            key = "q1_fixed" if method.startswith("RTKLIB_") else "ratio_fixed"
            container = metrics.get(key, {})
            values = container.get("errors", {})
            available = container.get("count") if defined != "NOT_APPLICABLE_NO_ACCEPTANCE_TEST" else None
            pointer = "/" + key + "/errors"
        count = values.get("count") if available is not None else None
        state = ("NOT_APPLICABLE_NO_ACCEPTANCE_TEST" if available is None else
                 "NO_FINITE_MATCHES" if count == 0 else "COMPLETED")
        rows.append({"sequence_id": sequence, "method_id": method, "support": mode,
                     "status": state, "paired_epoch_denominator": metrics["denominator_native_paired_epochs_in_window"],
                     "available_epoch_count": available, "scored_count": count,
                     **{k: values.get(k) if available is not None else None for k in
                        ("rmse_deg", "p95_absolute_deg", "max_absolute_deg", "mae_deg", "circular_bias_deg")},
                     "base_time": metrics["base_time"], "window_start_s": metrics["window_seconds"][0],
                     "window_end_s": metrics["window_seconds"][1],
                     "native_valid_maximum_gap_s": metrics["valid_segments"]["maximum_gap_seconds"],
                     **details, "metric_origin": "REUSED_ORIGINAL_METRIC" if reused else "NEW_OFFLINE_HEADING_EVALUATION",
                     "source_path": source, "source_row_key": pointer,
                     "support_boundary": "method-native paired epochs, not common support or navigation-point support"})
    return rows


def common_support(series_by_method, fixed_definitions, source_paths):
    indices = {method: index_time_rows(rows) for method, rows in series_by_method.items()}
    groups = [(f"{method}__RTKLIB_{variant}", [method, f"RTKLIB_{variant}"])
              for method in METHODS for variant in VARIANTS]
    groups += [("NEW_ALL3", list(METHODS))]
    groups += [("NEW_ALL3_WITH_RTKLIB_" + variant, [*METHODS, "RTKLIB_" + variant]) for variant in VARIANTS]
    groups += [("ALL7", [*METHODS, *("RTKLIB_" + x for x in VARIANTS)])]
    output, key_sets = [], {}
    field_for = {"native_valid": "error_valid_deg", "causal_held": "error_hold_deg", "ratio_fixed": "error_ratio_fixed_deg"}
    for group, members in groups:
        for mode in MODES:
            missing = [m for m in members if m not in indices]
            undefined = [m for m in members if mode == "ratio_fixed" and
                         fixed_definitions.get(m) == "NOT_APPLICABLE_NO_ACCEPTANCE_TEST"]
            status = "MISSING_MEMBER" if missing else "NOT_APPLICABLE_NO_ACCEPTANCE_TEST" if undefined else "COMPLETED"
            keys = []
            maximum_dt = None
            if status == "COMPLETED":
                candidate_keys = set.intersection(*(set(indices[m]) for m in members))
                for key in sorted(candidate_keys):
                    aligned = [indices[m][key] for m in members]
                    dt = verify_time_pair(aligned)
                    if all(number(row.get(field_for[mode])) is not None for row in aligned):
                        keys.append(key)
                        maximum_dt = max(maximum_dt or 0.0, dt)
                if not keys:
                    status = "EMPTY_FINITE_INTERSECTION"
            key_id = group + "/" + mode
            key_sets[key_id] = keys
            for member in members:
                errors = [float(indices[member][k][field_for[mode]]) for k in keys]
                stats = frozen._abs_stats(np.asarray(errors)) if status in ("COMPLETED", "EMPTY_FINITE_INTERSECTION") else {}
                output.append({"group_id": group, "support": mode, "method_id": member,
                               "members_json": json.dumps(members), "status": status,
                               "common_finite_count": len(keys) if stats else None,
                               **{k: stats.get(k) for k in ("rmse_deg", "p95_absolute_deg", "max_absolute_deg", "mae_deg")},
                               "original_window_row_count": len(indices[member]) if member in indices else None,
                               "first_key_us": keys[0] if keys else None, "last_key_us": keys[-1] if keys else None,
                               "maximum_member_time_difference_s": maximum_dt,
                               "source_path": source_paths.get(member, ""), "error_column": field_for[mode],
                               "key_list_source": "COMMON_SUPPORT_KEYS.json#/" + key_id.replace("/", "~1"),
                               "reason": json.dumps({"missing": missing, "undefined_fixed": undefined}),
                               "calculation_origin": "NEW_COMMON_SUPPORT_REDUCTION_OF_RETAINED_ERRORS"})
    return output, key_sets


def native_run_identity(sequence, method, native_version, native_attempt):
    """Bind a selected native attempt exactly; never glob or splice attempts."""
    frozen_source_pins(native_version)
    if type(native_attempt) is not int or native_attempt < 1:
        raise EvaluationError("native attempt must be a positive integer")
    if native_version == "V1" and native_attempt != 1:
        raise EvaluationError("technical retry identity requires explicit native V2")
    suffix = "" if native_attempt == 1 else f"__TECH_RETRY_{native_attempt}"
    return f"{sequence}__{method}__RAW_REPRO_{native_version}" + suffix


def prepare_spec(roots_path, sequence, *, verify_committed=True, native_version="V1", native_attempt=1):
    roots = json.loads(Path(roots_path).read_text())["aliases"]
    if sequence not in SEQUENCES:
        raise EvaluationError("unknown sequence")
    repo = Path(roots["<CODE_ROOT>"])
    native_run_identity(sequence, METHODS[0], native_version, native_attempt)
    pins = dict(frozen_source_pins(native_version))
    for relative, expected in pins.items():
        if digest((repo / relative).read_bytes()) != expected:
            raise EvaluationError("frozen evaluator source mismatch: " + relative)
    for relative in (SOURCE_RELATIVE, PROTOCOL_RELATIVE):
        pins[relative] = digest((repo / relative).read_bytes())
    head = None
    if verify_committed:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        for relative, expected in pins.items():
            recorded = subprocess.check_output(["git", "show", head + ":" + relative], cwd=repo)
            if digest(recorded) != expected:
                raise EvaluationError("evaluation source/protocol not committed: " + relative)
    input_path = f"<EXT_REPRO_ROOT>/inputs/{sequence}/INPUT.json"
    payload = expand(input_path, roots).read_bytes()
    info = json.loads(payload)
    if info["sequence"] != sequence:
        raise EvaluationError("input sequence mismatch")
    methods = []
    for method in METHODS:
        run_id = native_run_identity(sequence, method, native_version, native_attempt)
        run_path = f"<EXT_REPRO_ROOT>/runs/{run_id}/RUN.json"
        run_payload = expand(run_path, roots).read_bytes()
        run = json.loads(run_payload)
        if (run["status"] != "COMPLETED" or run["sequence"] != sequence or run["method"] != method
                or run["run_id"] != run_id or run.get("attempt", 1) != native_attempt
                or run["completed_epochs"] != info["pair_count"]
                or run["input_manifest_sha256"] != digest(payload)):
            raise EvaluationError("native terminal/identity gate failed: " + method)
        if run.get("data_mode") != "real_raw" or any(run.get(x) is not False for x in
                ("synthetic_data_used", "semisynthetic_data_used", "trace_used_online", "per_case_tuning",
                 "output_only_correction", "epoch_deleted_for_metric")):
            raise EvaluationError("native data-role gate failed: " + method)
        heading = run["outputs"]["HEADING.csv"]
        if heading["path"] != f"<EXT_REPRO_ROOT>/runs/{run_id}/HEADING.csv":
            raise EvaluationError("native heading pointer is not its own declared run")
        methods.append({"method_id": method, "run_id": run_id, "run_path": run_path,
                        "run_sha256": digest(run_payload), "heading_table": heading["path"],
                        "heading_table_sha256": heading["sha256"], "native_status": run["status"],
                        "native_code_commit": run["code_commit"]})
    old_sources, reference = [], None
    recorded_error_pins = {}
    index_path = expand(HX_FILE_INDEX, roots)
    if index_path.exists():
        for row in csv_rows(index_path.read_bytes()):
            if row.get("stage") != "HX07R":
                continue
            pin = json.loads(row.get("source_values_json") or "{}").get("recorded_sha256", "")
            if re.fullmatch(r"[0-9a-f]{64}", pin):
                recorded_error_pins[row["metric_source"]] = {"sha256": pin, "source": HX_FILE_INDEX,
                                                            "source_row_key": row["record_id"]}
    for variant in VARIANTS:
        prefix = f"<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS/{sequence}_{variant}"
        spec_path = prefix + "/eval/SPEC.json"
        spec_payload = expand(spec_path, roots).read_bytes()
        old = json.loads(spec_payload)
        identity = (portable(old["trace"], roots), old["trace_sha256"], old["base_time"], old["window"])
        if (old["sequence_id"] != sequence or old["method_id"] != "RTKLIB"
                or old["base_time"] != info["base_time"] or old["window"] != info["window_seconds"]
                or (reference is not None and identity != reference)):
            raise EvaluationError("HX07R reference/window identities disagree")
        reference = identity
        if len(old["variants"]) != 1 or old["variants"][0]["label"] != "RTKLIB":
            raise EvaluationError("unexpected HX07R variant schema")
        source = old["variants"][0]
        error_path = portable(old["outdir"], roots) + "/HEADING_ERROR_SERIES_RTKLIB.csv"
        old_sources.append({"method_id": "RTKLIB_" + variant, "spec_path": spec_path,
                            "spec_sha256": digest(spec_payload),
                            "heading_table": portable(source["heading_table"], roots),
                            "heading_table_sha256": source["heading_table_sha256"],
                            "metrics_path": portable(old["outdir"], roots) + "/HEADING_METRICS.json",
                            "error_path": error_path, "error_recorded_pin": recorded_error_pins.get(error_path)})
    return roots, {"schema": SCHEMA, "sequence_id": sequence, "preparation_commit": head,
                   "native_version": native_version, "native_attempt": native_attempt, "source_overlay": not verify_committed,
                   "source_pins": pins, "input_manifest": input_path, "input_manifest_sha256": digest(payload),
                   "pair_count": info["pair_count"], "base_time": info["base_time"], "window": info["window_seconds"],
                   "trace": reference[0], "trace_sha256": reference[1], "methods": methods,
                   "reused_variants": old_sources, "v3_table": V3_TABLE,
                   "data_mode": "real_raw_offline_heading_evaluation", "synthetic_data_used": False,
                   "semisynthetic_data_used": False, "trace_used_online": False,
                   "outdir": f"<EXT_REPRO_ROOT>/evaluation/{sequence}"}


def evaluate_child(spec, roots):
    """Only this function opens the reference; one same-handle read and hash."""
    out = expand(spec["outdir"], roots)
    receipt = {"schema": SCHEMA, "status": "STARTED", "evaluator_child_invocations": 1,
               "reference_open_count": 0, "reference_open_attempts": 0, "reference_hash_matched": False,
               "data_mode": spec["data_mode"], "synthetic_data_used": spec["synthetic_data_used"],
               "semisynthetic_data_used": spec["semisynthetic_data_used"], "new_native_calls": 0}
    write_json(out / "CHILD_RECEIPT.json", receipt, exclusive=True)
    sources = []

    def load(alias, role, expected=None):
        payload = expand(alias, roots).read_bytes()
        value = digest(payload)
        sources.append({"source_path": alias, "role": role, "sha256": value, "bytes": len(payload),
                        "read_depth": "FULL_PAYLOAD_READ", "hash_status": (
                            "NEW_READ_HASH_NOT_HISTORICAL_PIN" if role == "reused_error_series" and not expected
                            else "NEWLY_VERIFIED_SAME_BYTES_READ"),
                        "recorded_sha256": expected or "", "recorded_pin_matches": value == expected if expected else "NOT_PINNED"})
        if expected and value != expected:
            raise EvaluationError("source SHA256 mismatch: " + alias)
        return payload

    try:
        if [item["method_id"] for item in spec["methods"]] != list(METHODS):
            raise EvaluationError("expected exactly three ordered method identities")
        if spec["data_mode"] != "synthetic_unit_test":
            for relative, expected in spec["source_pins"].items():
                if digest((Path(roots["<CODE_ROOT>"]) / relative).read_bytes()) != expected:
                    raise EvaluationError("child source pin mismatch: " + relative)
            if any(spec["source_pins"].get(p) != v for p, v in frozen_source_pins(spec.get("native_version", "V1")).items()):
                raise EvaluationError("child frozen evaluator pins missing")
        tables, raw = {}, {}
        for declaration in spec["methods"]:
            label = declaration["method_id"]
            tables[label], raw[label] = parse_heading(load(declaration["heading_table"], "new_native_heading", declaration["heading_table_sha256"]))
            if len(raw[label]) != spec["pair_count"]:
                raise EvaluationError("native full paired denominator mismatch")
        first = tables[METHODS[0]]
        for label in METHODS[1:]:
            if any(not np.array_equal(first[key], tables[label][key]) for key in
                   ("epoch_index", "gps_week", "gps_tow_seconds", "time_unix_s")):
                raise EvaluationError("three new methods do not share the exact original paired grid")
        receipt["reference_open_attempts"] = 1
        write_json(out / "CHILD_RECEIPT.json", receipt)
        with expand(spec["trace"], roots).open("rb") as handle:
            receipt["reference_open_count"] = 1
            trace_payload = handle.read()
        observed = digest(trace_payload)
        receipt["reference_sha256_observed"] = observed
        receipt["reference_hash_matched"] = observed == spec["trace_sha256"]
        if not receipt["reference_hash_matched"]:
            raise EvaluationError("reference SHA256 mismatch")
        sources.append({"source_path": spec["trace"], "role": "evaluation_only_reference", "sha256": observed,
                        "recorded_sha256": spec["trace_sha256"], "recorded_pin_matches": True,
                        "bytes": len(trace_payload), "read_depth": "FULL_PAYLOAD_READ",
                        "hash_status": "NEWLY_VERIFIED_SAME_HANDLE_BYTES"})
        reference = frozen.reference_yaw_ned(trace_payload, first["time_unix_s"])
        reference_times = (float(row["time"]) for row in csv.DictReader(io.StringIO(trace_payload.decode("utf-8-sig"))))
        reference_start = next(reference_times)
        reference_end = reference_start
        for reference_end in reference_times:
            pass
        reference_bounds = (reference_start, reference_end)
        del trace_payload
        metrics_by_method, series, definitions, paths, result_rows = {}, {}, {}, {}, []
        for declaration in spec["methods"]:
            label = declaration["method_id"]
            flags = {row.get("acceptance_test_defined", "") for row in raw[label]}
            if flags not in ({"0"}, {"1"}):
                raise EvaluationError("acceptance-test definition is missing or mixed")
            definitions[label] = "PAPER_RATIO_TEST" if flags == {"1"} else "NOT_APPLICABLE_NO_ACCEPTANCE_TEST"
            table_for_metrics = dict(tables[label])
            if flags == {"0"}:
                table_for_metrics.pop("ratio_fixed", None)
            metrics, errors = frozen.heading_metrics(table_for_metrics, reference, base_time=spec["base_time"],
                                                     window=spec["window"], method_id=label)
            series[label] = enrich_series(tables[label], raw[label], errors, method=label, reference=reference)
            details = support_details(tables[label], raw[label], series[label], spec["base_time"], spec["window"], definitions[label])
            metrics["additional_support_diagnostics"] = details
            metrics["native_identity"] = declaration
            metrics_by_method[label] = metrics
            paths[label] = spec["outdir"] + "/ERROR_SERIES.csv"
            result_rows += metric_rows(spec["sequence_id"], label, metrics, details,
                                      spec["outdir"] + "/HEADING_METRICS.json#/" + label)
        # Save primary results before optional reuse/comparison and plotting.
        write_json(out / "HEADING_METRICS.json", metrics_by_method, exclusive=True)
        write_csv(out / "ERROR_SERIES.csv", [row for label in METHODS for row in series[label]])
        reused, reuse_failures = {}, []
        for declaration in spec["reused_variants"]:
            label = declaration["method_id"]
            original_metrics = None
            try:
                original = json.loads(load(declaration["metrics_path"], "reused_original_metrics"))
                if (original["sequence_id"] != spec["sequence_id"] or original["trace_sha256_observed"] != observed):
                    raise EvaluationError("reused metrics identity/reference mismatch")
                metrics = original["variants"]["RTKLIB"]
                if (metrics["base_time"] != spec["base_time"] or metrics["window_seconds"] != spec["window"]
                        or metrics["heading_table_sha256"] != declaration["heading_table_sha256"]):
                    raise EvaluationError("reused metric window/heading pin mismatch")
                if metrics["error_convention"] != ERROR_CONVENTION or metrics["reference_semantics"] != REFERENCE_SEMANTICS:
                    raise EvaluationError("reused frozen error/reference convention mismatch")
                original_metrics = metrics
                reused[label] = original  # Quoted metrics survive a later payload/support failure.
                table, rows = parse_heading(load(declaration["heading_table"], "reused_native_heading", declaration["heading_table_sha256"]))
                pin = declaration.get("error_recorded_pin")
                errors = csv_rows(load(declaration["error_path"], "reused_error_series", pin["sha256"] if pin else None))
                if (len(errors) != metrics["denominator_native_paired_epochs_in_window"] or
                        sum(number(row["error_valid_deg"]) is not None for row in errors) != metrics["valid"]["count"] or
                        sum(number(row["error_hold_deg"]) is not None for row in errors) != metrics["hold_last_valid"]["count"]):
                    raise EvaluationError("reused error support disagrees with original counts")
                validate_reused_support(table, rows, errors, metrics, reference_bounds)
                enriched = enrich_series(table, rows, errors, method=label)
                details = support_details(table, rows, enriched, spec["base_time"], spec["window"], "RTKLIB_Q1_FIXED")
                rows_to_add = metric_rows(spec["sequence_id"], label, metrics, details,
                                         declaration["metrics_path"] + "#/variants/RTKLIB", reused=True)
                # Atomic publication into common support only after every check.
                definitions[label] = "RTKLIB_Q1_FIXED"
                series[label] = enriched
                paths[label] = declaration["error_path"]
                result_rows += rows_to_add
            except (OSError, ValueError, KeyError, EvaluationError, frozen.HeadingEvaluationError) as exc:
                series.pop(label, None); definitions.pop(label, None); paths.pop(label, None)
                reuse_failures.append({"method_id": label, "status": "REUSED_SOURCE_UNAVAILABLE_OR_INCONSISTENT",
                                      "reason": sanitize(exc, roots), "source_path": declaration["metrics_path"]})
                if original_metrics is not None:
                    quoted = metric_rows(spec["sequence_id"], label, original_metrics,
                                         {"fixed_definition": "RTKLIB_Q1_FIXED"},
                                         declaration["metrics_path"] + "#/variants/RTKLIB", reused=True)
                    for row in quoted:
                        row.update(status="ORIGINAL_METRIC_QUOTED_COMMON_SUPPORT_REJECTED",
                                   common_support_eligible=False, support_failure=sanitize(exc, roots))
                    result_rows += quoted
                else:
                    for mode in MODES:
                        result_rows.append({"sequence_id": spec["sequence_id"], "method_id": label,
                                            "support": mode, **reuse_failures[-1]})
        write_csv(out / "RESULT_ROWS.csv", result_rows)
        write_json(out / "REUSED_METRICS.json", reused, exclusive=True)
        write_json(out / "REUSE_LIMITATIONS.json", reuse_failures, exclusive=True)
        write_csv(out / "REUSED_ERROR_SERIES.csv", [row for label in series if label not in METHODS for row in series[label]])
        comparisons, keys = common_support(series, definitions, paths)
        write_csv(out / "COMMON_SUPPORT.csv", comparisons)
        write_json(out / "COMMON_SUPPORT_KEYS.json", keys, exclusive=True)
        # Quote only the already-collected F04/v3 C00 row; no retained V3 payload.
        v3 = csv_rows(load(spec["v3_table"], "original_v3_c00_table"))
        selected = [row for row in v3 if row["sequence_id"] == spec["sequence_id"] and row["method_id"] == "F04"]
        if len(selected) != 1:
            raise EvaluationError("expected exactly one quoted V3 F04/C00 row")
        source = selected[0]
        quote = {key: value for key, value in source.items() if key in ("run_id", "sequence_id", "method_id") or
                 key.startswith("v3_") and any(x in key for x in ("rmse", "epoch_count", "window", "ledger_json_pointer"))}
        write_csv(out / "V3_REFERENCE.csv", [{"source_path": spec["v3_table"], "source_row_key": "run_id=" + source["run_id"],
                    "source_values_json": json.dumps(quote, ensure_ascii=False),
                    "comparison_status": "DIFFERENT_NAVIGATION_POINT_AND_EPOCH_SUPPORT; QUOTED_ONLY"}])
        receipt.update(status="NUMERICALLY_COMPLETED", new_method_count=3, reused_method_count=len(series) - 3,
                       quoted_original_metric_count=len(reused),
                       reuse_limitations_count=len(reuse_failures), original_paired_epochs=spec["pair_count"],
                       new_heading_error_rows=sum(len(series[m]) for m in METHODS),
                       common_support_result_rows=len(comparisons), common_support_groups=len(keys),
                       error_series_sha256=digest((out / "ERROR_SERIES.csv").read_bytes()))
    except Exception as exc:
        receipt.update(status="FAILED_RETAINED_NO_RETRY", failure_type=type(exc).__name__, reason=sanitize(exc, roots))
        raise
    finally:
        write_csv(out / "SOURCE_FILES.csv", sources)
        write_json(out / "CHILD_RECEIPT.json", receipt)
    return receipt


def audit_reference_opens(payload, roots, reference):
    """Parse strace -xx paths; count successful read opens, never infer from names."""
    reference_path = str(expand(reference, roots))
    raw_root = roots["<RAW_ROOT>"].rstrip("/")
    reference_opens, other_raw = [], []
    exec_count = 0
    for line in payload.decode("utf-8", errors="replace").splitlines():
        if "execve(" in line and re.search(r"= 0$", line):
            exec_count += 1
        if not re.search(r"\bopen(?:at)?\(", line) or not re.search(r"= \d+(?:\s|$)", line):
            continue
        match = re.search(r'"((?:\\x[0-9a-fA-F]{2})*)"', line)
        if not match:
            continue
        path = bytes.fromhex(match.group(1).replace("\\x", "")).decode("utf-8", errors="replace")
        if path == reference_path:
            reference_opens.append({"read_only": "O_RDONLY" in line and "O_RDWR" not in line and "O_WRONLY" not in line})
        elif path == raw_root or path.startswith(raw_root + "/"):
            other_raw.append(portable(path, roots))
    passed = len(reference_opens) == 1 and all(x["read_only"] for x in reference_opens) and not other_raw and exec_count == 1
    return {"passed": passed, "reference_successful_opens": len(reference_opens),
            "reference_all_read_only": all(x["read_only"] for x in reference_opens),
            "other_raw_open_paths": other_raw, "successful_execve_count": exec_count,
            "audit_scope": "single evaluator child under strace; parent does not open reference in code"}


def broken_line(rows, field, *, valid_field=None, wrap=False):
    """Insert NaN separators for missing values, invalid epochs, gaps and wraps."""
    x, y, previous = [], [], None
    for row in rows:
        t = float(row["t_rel_s"])
        value = number(row.get(field))
        if valid_field and str(row.get(valid_field)) != "1":
            value = None
        index = int(row["epoch_index"])
        if previous is not None:
            pt, pv, pi = previous
            if index != pi + 1 or t - pt > PLOT_GAP_SECONDS or (wrap and value is not None and pv is not None and abs(value - pv) > 180):
                x.append(math.nan); y.append(math.nan)
        x.append(t); y.append(math.nan if value is None else value)
        previous = (t, value, index)
    return np.asarray(x), np.asarray(y)


def plot_saved(out, sequence):
    """No source/ref access: only ERROR_SERIES.csv, with exclusive plot attempts."""
    payload = (out / "ERROR_SERIES.csv").read_bytes()
    rows = csv_rows(payload)
    root = out / "figures"
    root.mkdir(exist_ok=True)
    attempt = 1
    while (root / f"attempt_{attempt:03d}").exists():
        attempt += 1
    target = root / f"attempt_{attempt:03d}"
    target.mkdir(exist_ok=False)
    receipt = {"status": "STARTED", "attempt": attempt, "sequence_id": sequence,
               "source": "ERROR_SERIES.csv", "source_sha256": digest(payload),
               "reference_opens": 0, "evaluator_invocations": 0}
    write_json(target / "PLOT_RECEIPT.json", receipt, exclusive=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=True, constrained_layout=True)
        colors = ("#0072B2", "#D55E00", "#009E73")
        grouped = {method: [row for row in rows if row["method_id"] == method] for method in METHODS}
        display = {
            method: [{**row, **{target: "" if number(row.get(source)) is None else number(row[source]) % 360.0
                                for source, target in (("native_body_yaw_deg", "display_native_yaw_deg"),
                                                       ("reference_yaw_ned_deg", "display_reference_yaw_deg"))}}
                     for row in subset]
            for method, subset in grouped.items()
        }
        for i, (method, color) in enumerate(zip(METHODS, colors, strict=True)):
            subset = grouped[method]
            axes[0].plot(*broken_line(display[method], "display_native_yaw_deg", valid_field="valid", wrap=True), color=color, lw=.8,
                         marker=".", markersize=1.7, label=method)
            axes[1].plot(*broken_line(subset, "error_valid_deg", valid_field="valid", wrap=True), color=color, lw=.8,
                         marker=".", markersize=1.7, label=method)
            for label, marker, state_color, offset, choose in (
                    ("invalid", "x", "#7f7f7f", -.16, lambda r: r["valid"] == "0"),
                    ("native valid", ".", color, 0., lambda r: r["valid"] == "1" and r.get("ratio_fixed") != "1"),
                    ("ratio fixed", "|", "black", .16, lambda r: r["valid"] == "1" and r.get("ratio_fixed") == "1")):
                chosen = [row for row in subset if choose(row)]
                axes[2].scatter([float(row["t_rel_s"]) for row in chosen], [i + offset] * len(chosen),
                                s=10, marker=marker, c=state_color, alpha=.8, label=label if i == 2 else None)
            for column, style, suffix in (("baseline_n_m", "-", "N"), ("baseline_e_m", "--", "E"),
                                          ("baseline_length_m", ":", "length")):
                axes[3].plot(*broken_line(subset, column, valid_field="valid"), color=color, ls=style, lw=.8, marker=".", markersize=1.7,
                             label=method + " " + suffix)
        axes[0].plot(*broken_line(display[METHODS[0]], "display_reference_yaw_deg", wrap=True), c="black", lw=.65, label="Reference")
        for axis, letter in zip(axes, "abcd", strict=True):
            axis.text(.01, .94, "(" + letter + ")", transform=axis.transAxes, va="top")
            axis.grid(alpha=.2)
        axes[0].set_ylabel("Body yaw (deg)"); axes[1].set_ylabel("Yaw error (deg)")
        axes[2].set_yticks(range(3)); axes[2].set_yticklabels(METHODS); axes[2].set_ylim(-.4, 2.4)
        axes[3].set_ylabel("Relative baseline (m)"); axes[3].set_xlabel("Time from sequence base (s)")
        axes[0].legend(loc="upper center", bbox_to_anchor=(.5, 1.20), ncol=4, fontsize=8)
        axes[2].legend(loc="upper center", bbox_to_anchor=(.5, 1.20), ncol=3, fontsize=8)
        axes[3].legend(loc="upper center", bbox_to_anchor=(.5, -.28), ncol=3, fontsize=7)
        for extension in ("png", "pdf"):
            fig.savefig(target / ("HEADING_COMPARISON." + extension), dpi=420)
        plt.close(fig)
        receipt.update(status="COMPLETED_VISUAL_REVIEW_PENDING", outputs=["HEADING_COMPARISON.png", "HEADING_COMPARISON.pdf"],
                       png_width_pixels=4200, reference_label_note="Fixposition-derived reference; not independent truth",
                       plot_gap_rule_seconds=PLOT_GAP_SECONDS, plot_implementation="WRAP360_STATUS_LANES_V2",
                       heading_display_rule="native/reference wrap360 then gap/wrap breaks; display only; errors unchanged",
                       status_offsets={"invalid": -.16, "native_valid": 0., "ratio_fixed": .16},
                       baseline_display_rule="original finite relative-baseline values; no clipping")
    except Exception as exc:
        receipt.update(status="PLOT_FAILED_NUMERIC_RESULTS_PRESERVED", failure_type=type(exc).__name__)
    write_json(target / "PLOT_RECEIPT.json", receipt)
    return receipt


def run(roots_path, sequence, *, plot_only=False, native_version="V1", native_attempt=1, allow_source_overlay=False):
    if allow_source_overlay and native_version != "V2":
        raise EvaluationError("source overlay requires explicit native V2 evaluation")
    if plot_only:
        roots = json.loads(Path(roots_path).read_text())["aliases"]
        out = expand(f"<EXT_REPRO_ROOT>/evaluation/{sequence}", roots)
        child = json.loads((out / "CHILD_RECEIPT.json").read_text())
        if child["status"] != "NUMERICALLY_COMPLETED":
            raise EvaluationError("plot-only requires completed saved numerical output")
        return plot_saved(out, sequence)
    native_run_identity(sequence, METHODS[0], native_version, native_attempt)
    if native_version == "V1" and not allow_source_overlay:
        roots, spec = prepare_spec(roots_path, sequence)
    else:
        roots, spec = prepare_spec(roots_path, sequence, native_version=native_version, native_attempt=native_attempt,
                                   verify_committed=not allow_source_overlay)
    strace = shutil.which("strace")
    if strace is None:
        raise EvaluationError("strace is required before the reference child is invoked")
    out = expand(spec["outdir"], roots)
    if not out.resolve().is_relative_to(Path(roots["<EXT_REPRO_ROOT>"]).resolve()):
        raise EvaluationError("output resolves outside the isolated result root")
    out.mkdir(parents=True, exist_ok=False)
    if native_version == "V2":
        spec["preparation_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=roots["<CODE_ROOT>"], text=True).strip()
        spec["code_commit_role"] = "BASE_HEAD_ONLY" if allow_source_overlay else "HEAD_PINNED_RUNTIME_SOURCE"
        for relative, expected in spec["source_pins"].items():
            payload = (Path(roots["<CODE_ROOT>"]) / relative).read_bytes()
            if digest(payload) != expected:
                raise EvaluationError("evaluation snapshot source drift")
            snapshot = out / "SOURCE_SNAPSHOT" / relative
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(payload)
    write_json(out / "SPEC.json", spec, exclusive=True)
    receipt = {"schema": SCHEMA, "sequence_id": sequence, "evaluation_status": "STARTED",
               "plot_status": "NOT_STARTED", "evaluator_child_attempts": 1, "evaluator_child_invocations": 0,
               "parent_reference_opens": 0, "automatic_retries": 0, "new_native_calls": 0,
               "data_mode": spec["data_mode"], "synthetic_data_used": False, "semisynthetic_data_used": False,
               "preparation_commit": spec["preparation_commit"], "started_unix": time.time()}
    write_json(out / "EVALUATION_RECEIPT.json", receipt, exclusive=True)
    command = [strace, "-f", "-qq", "-xx", "-s", "8192", "-e", "trace=open,openat,execve", "-o", str(out / "IO_AUDIT.strace"),
               sys.executable, "-m", MODULE, "--roots", str(Path(roots_path).resolve()), "--child-spec", str(out / "SPEC.json")]
    env = os.environ.copy()
    env.update(PYTHONPATH=str(Path(roots["<CODE_ROOT>"]) / "src"), PYTHONDONTWRITEBYTECODE="1",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    try:
        with (out / "CHILD.stdout").open("x") as stdout, (out / "CHILD.stderr").open("x") as stderr:
            result = subprocess.run(command, env=env, cwd=roots["<CODE_ROOT>"], stdout=stdout, stderr=stderr, check=False)
        receipt["child_exit_code"] = result.returncode
        audit = audit_reference_opens((out / "IO_AUDIT.strace").read_bytes(), roots, spec["trace"])
        write_json(out / "ACCESS_AUDIT.json", audit, exclusive=True)
        receipt["evaluator_child_invocations"] = audit["successful_execve_count"]
        child_path = out / "CHILD_RECEIPT.json"
        child = json.loads(child_path.read_text()) if child_path.exists() else {}
        success = result.returncode == 0 and audit["passed"] and child.get("status") == "NUMERICALLY_COMPLETED"
        receipt["evaluation_status"] = "COMPLETED" if success else "FAILED_RETAINED_NO_RETRY"
        receipt["reference_hash_matched"] = child.get("reference_hash_matched", False)
        receipt["actual_reference_open_count"] = audit["reference_successful_opens"]
        receipt["numeric_child_status"] = child.get("status", "NOT_STARTED")
        write_json(out / "EVALUATION_RECEIPT.json", receipt)
        if success:
            receipt["plot_status"] = plot_saved(out, sequence)["status"]
    except Exception as exc:
        receipt["failure_type"] = type(exc).__name__
        receipt["failure_reason"] = sanitize(exc, roots)
        if receipt["evaluation_status"] == "COMPLETED":
            receipt["plot_status"] = "PLOT_FAILED_NUMERIC_RESULTS_PRESERVED"
        else:
            receipt["evaluation_status"] = "FAILED_RETAINED_NO_RETRY"
    finally:
        receipt["finished_unix"] = time.time()
        write_json(out / "EVALUATION_RECEIPT.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roots", required=True)
    parser.add_argument("--sequence", choices=SEQUENCES)
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--native-version", choices=("V1", "V2"), default="V1")
    parser.add_argument("--native-attempt", type=int, default=1, help="Exact V2 native technical-attempt identity; no attempt merging")
    parser.add_argument("--allow-source-overlay", action="store_true")
    parser.add_argument("--child-spec", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child_spec:
        roots = json.loads(Path(args.roots).read_text())["aliases"]
        spec = json.loads(args.child_spec.read_text())
        result = evaluate_child(spec, roots)
    else:
        if not args.sequence:
            parser.error("--sequence is required")
        result = run(args.roots, args.sequence, plot_only=args.plot_only,
                     native_version=args.native_version, native_attempt=args.native_attempt,
                     allow_source_overlay=args.allow_source_overlay)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result.get("evaluation_status", result.get("status")) in (
        "COMPLETED", "NUMERICALLY_COMPLETED", "COMPLETED_VISUAL_REVIEW_PENDING") else 1


if __name__ == "__main__":
    raise SystemExit(main())
