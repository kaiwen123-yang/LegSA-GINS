"""H-EXT-02 aggregation of sealed external results and pinned frozen scalar rows.

This module never calls a solver/evaluator or opens a reference trace. Frozen
main-chain values retain their original scientific commit and source tokens.
"""
from __future__ import annotations

import csv
from collections import Counter
import hashlib
import gzip
import io
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..canonical541 import offline_eval_aggregate as canonical
from ..manifest import sha256_file
from .sequence_paths import alias_path

TABLE_FIELDS = (
    "sequence_id", "method_id", "config", "start_convention", "main_row", "manuscript_row",
    "failure_classification", "evaluation_status",
    "geometric_audit_status", "h_rmse_m", "position_3d_rmse_m", "up_rmse_m", "yaw_rmse_deg",
    "yaw_p95_absolute_deg", "roll_rmse_deg", "pitch_rmse_deg", "body_forward_bias_m",
    "body_right_bias_m", "body_up_bias_m", "output_epoch_count", "matched_epoch_count", "coverage_ratio",
    "gap_events_in_window", "gnss2_pacc_inflated_epochs", "gnss2_float_epochs", "evaluator_contract",
    "source_nav_sha256", "evaluator_nav_sha256", "error_series_source", "code_commit", "notes",
)
METRIC_FIELDS = ("h_rmse_m", "position_3d_rmse_m", "up_rmse_m", "yaw_rmse_deg",
                 "yaw_p95_absolute_deg", "roll_rmse_deg", "pitch_rmse_deg")
LEGSA_METHODS = ("F01", "F02", "F03", "A04", "F04")
EXTERNAL_METHODS = ("LC01", "EXT05C", "LC01-S", "EXT05C-S")
AVAILABLE = {"COMPLETED", "AVAILABLE", "AVAILABLE_GEOMETRIC_AUDIT_FAIL"}
V21_ROOT = "stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/13_AGGREGATE_SEQUENCES"
P07_TABLE = "stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/HORIZONTAL_TABLE_V3.csv"
PARITY_SUMMARY = "stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json"
FROZEN_PINS = {
    "v21_v3": "e26dfcd830d6c711ffbb7debd68293fbf7b7ea28240e16bce582381b61ea6a0b",
    "v21_v2": "6c5a165eaf68bf762cbc803466b4496a5b522dba968785115db9d0338990044d",
    "p07_v3": "d91f53aaf855efc8c533a6f15a9c6c933e87bafb2bcc9bd169ba862163c82c01",
    "parity_summary": "7ad4294999bdb7b3668bb7cd59869f49a42fb0d840f76b83c94b0704aee64d75",
}
OCCLUSION_WINDOWS = (("occlusion_primary", 3369.94, 3411.95),
                     ("occlusion_secondary", 3495.94, 3508.94))
H03_PRIMARY_STARTS = {"BY2": "FILE_START", "BY2H": "CONTRACT_START", "BY2O": "FILE_START"}
H03_UNAVAILABLE = {"NOT_RUN_ALGORITHM_FAILURE", "UNAVAILABLE_EVALUATION_FAILED"}


def _json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, payload):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def _write_csv(path: Path, rows, fields=None):
    columns = list(fields or dict.fromkeys(key for row in rows for key in row)) or ["status"]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                             if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})


def pinned_payload(path: Path, expected_sha256: str) -> bytes:
    """Hash bytes before parsing their contents; every source table has a fixed pin."""
    if path.is_symlink():
        raise ValueError("Frozen table may not be a symlink")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("Frozen aggregate source hash mismatch: " + str(path))
    return payload


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _first(source, *keys, default="UNAVAILABLE"):
    return next((source[k] for k in keys if source.get(k) not in (None, "")), default)


def _notes(**values):
    return json.dumps(values, ensure_ascii=False, sort_keys=True)


def normalize_row(source, *, sequence_id, method_id, config, start, geometric_status,
                  notes, body_bias=None, gaps="NOT_APPLICABLE", pacc="NOT_APPLICABLE", floats="NOT_APPLICABLE"):
    row = {name: "UNAVAILABLE" for name in TABLE_FIELDS}
    row.update(sequence_id=sequence_id, method_id=method_id, config=config, start_convention=start,
               main_row=False, manuscript_row=False,
               failure_classification=_first(source, "failure_classification", default="NONE"),
               geometric_audit_status=geometric_status,
               evaluation_status=_first(source, "evaluation_status", default="UNAVAILABLE"),
               gap_events_in_window=gaps, gnss2_pacc_inflated_epochs=pacc, gnss2_float_epochs=floats,
               notes=notes)
    for name in (*METRIC_FIELDS, "output_epoch_count", "matched_epoch_count", "coverage_ratio", "code_commit", "evaluator_contract"):
        row[name] = _first(source, name, "horizontal_rmse_m" if name == "h_rmse_m" else name)
    row["source_nav_sha256"] = _first(source, "source_nav_sha256", "native_nav_sha256")
    row["evaluator_nav_sha256"] = _first(source, "evaluator_nav_sha256", "eval_nav_sha256")
    row["error_series_source"] = _first(source, "error_series_source")
    for axis in ("forward", "right", "up"):
        row[f"body_{axis}_bias_m"] = _first(body_bias or {}, f"{axis}_signed_mean_m",
            default=_first(source, f"body_{axis}_bias_m", f"body_{axis}_signed_mean_m"))
    if row["evaluation_status"] in AVAILABLE and geometric_status == "FAIL":
        row["evaluation_status"] = "AVAILABLE_GEOMETRIC_AUDIT_FAIL"
    if row["evaluation_status"] not in AVAILABLE and row["failure_classification"] == "NONE":
        row["failure_classification"] = _first(source, "unavailable_reason", default="UNAVAILABLE_UNCLASSIFIED")
    return row


def select_main_config(rows):
    """The sole selector: BY2 C00 v3 LC01-S yaw versus frozen LC01 yaw."""
    candidates = {}
    for method in ("LC01", "LC01-S"):
        selected = [r for r in rows if r["sequence_id"] == "BY2" and r["method_id"] == method
                    and (method == "LC01-S" or r["start_convention"] == "FILE_START")]
        if len(selected) != 1 or selected[0]["evaluation_status"] not in AVAILABLE:
            raise ValueError("Main-version selector requires one available BY2 row per version")
        value = _number(selected[0]["yaw_rmse_deg"])
        if value is None:
            raise ValueError("Main-version yaw is unavailable; substitution is forbidden")
        candidates[method] = value
    if candidates["LC01"] != 2.9948274600591076:
        raise ValueError("Frozen BY2 LC01 yaw anchor changed")
    if candidates["LC01-S"] == candidates["LC01"]:
        raise ValueError("Equal yaw RMSE requires a human decision; no unregistered tie break")
    chosen = "S" if candidates["LC01-S"] < candidates["LC01"] else "LIT"
    return {"selected_config": chosen, "selected_method_id": "LC01-S" if chosen == "S" else "LC01",
            "by2_lit_yaw_rmse_deg": candidates["LC01"], "by2_shared_yaw_rmse_deg": candidates["LC01-S"],
            "rule": "smaller BY2 C00 v3 LC01 yaw; uniform configuration across all sequences; both versions retained"}


def mark_main_rows(rows, selection, primary_starts, *, continuation_v11=False):
    result = []
    for source in rows:
        row = dict(source)
        row["main_row"] = row["method_id"] in LEGSA_METHODS or (
            row["method_id"] == selection["selected_method_id"]
            and row["start_convention"] == primary_starts[row["sequence_id"]])
        row["manuscript_row"] = row["main_row"] and (
            not continuation_v11 or row["method_id"] not in ("F01", "F03"))
        result.append(row)
    return result


def delta_rows(rows):
    result = []
    for seq in ("BY2", "BY2H", "BY2O"):
        chosen = [r for r in rows if r["sequence_id"] == seq and r["main_row"] and r["method_id"] in ("LC01", "LC01-S")]
        if len(chosen) != 1:
            raise ValueError("Exactly one primary LC01 row required per sequence")
        candidate = chosen[0]
        for reference_id in ("F04", "A04"):
            reference = next(r for r in rows if r["sequence_id"] == seq and r["method_id"] == reference_id)
            for metric in METRIC_FIELDS:
                left, right = _number(candidate[metric]), _number(reference[metric])
                available = left is not None and right is not None and candidate["evaluation_status"] in AVAILABLE and reference["evaluation_status"] in AVAILABLE
                result.append({"sequence_id": seq, "candidate_method_id": candidate["method_id"],
                    "reference_method_id": reference_id, "metric": metric, "candidate_value": candidate[metric],
                    "reference_value": reference[metric], "delta_candidate_minus_reference": left-right if available else "UNAVAILABLE",
                    "negative_is_better": True, "status": "AVAILABLE" if available else "UNAVAILABLE",
                    "candidate_source": candidate["notes"], "reference_source": reference["notes"]})
    return result


def segment_rows(errors: pd.DataFrame, *, sequence_id: str, method_id: str,
                 start_convention: str, version: str, window, source: str):
    """Derived segments of frozen error series; whole-run metrics are not replaced."""
    t = np.asarray(errors["time"], float)
    if not np.isfinite(errors.select_dtypes(include="number").to_numpy()).all():
        raise ValueError("Nonfinite error series; epoch deletion forbidden")
    start, end = window
    windows = [("full", float(start), float(end))]
    if sequence_id == "BY2O":
        windows.extend(OCCLUSION_WINDOWS)
    result = []
    for label, low, high in windows:
        mask = (t >= low) & (t <= high)
        part = errors.loc[mask]
        common = {"sequence_id": sequence_id, "method_id": method_id, "start_convention": start_convention,
            "evaluator_contract": "evaluator_contract_"+version, "segment_id": label,
            "window_start_s": low, "window_end_s": high, "count": len(part), "error_series_source": source,
            "endpoint_policy": "CLOSED", "status": "AVAILABLE" if len(part) else "UNAVAILABLE_NO_MATCHED_EPOCHS"}
        for metric, column in (("h_rmse_m", "horizontal_err_m"), ("position_3d_rmse_m", "position_3d_err_m"),
                               ("up_rmse_m", "err_u_m"), ("yaw_rmse_deg", "yaw_err_deg"),
                               ("roll_rmse_deg", "roll_err_deg"), ("pitch_rmse_deg", "pitch_err_deg")):
            values = np.asarray(part[column], float)
            common[metric] = float(np.sqrt(np.mean(values**2))) if len(values) else "UNAVAILABLE"
        common["yaw_p95_absolute_deg"] = float(np.percentile(np.abs(part["yaw_err_deg"]), 95)) if len(part) else "UNAVAILABLE"
        result.append(common)
    return result


def unavailable_segments(*, sequence_id, method_id, start_convention, version, window,
                         source, status, reason):
    """Keep failed/missing rows visible; unavailable support is never a zero count."""
    windows = [("full", *map(float, window))]
    if sequence_id == "BY2O":
        windows.extend(OCCLUSION_WINDOWS)
    return [{"sequence_id": sequence_id, "method_id": method_id,
             "start_convention": start_convention, "evaluator_contract": "evaluator_contract_"+version,
             "segment_id": label, "window_start_s": low, "window_end_s": high,
             "count": "UNAVAILABLE", "error_series_source": source, "endpoint_policy": "CLOSED",
             "status": status, "unavailable_reason": reason,
             **{metric: "UNAVAILABLE" for metric in METRIC_FIELDS}}
            for label, low, high in windows]


def validate_evaluation_payload(payload, *, version, continuation_v11=False):
    """D12 separates successful capture from explicit, technically valid dispositions."""
    source, audit = payload["row"], payload["audit"]
    if source.get("evaluator_contract") != "evaluator_contract_"+version:
        raise ValueError("Evaluator-version identity mismatch")
    status = source.get("evaluation_status")
    if continuation_v11 and status == "NOT_RUN_ALGORITHM_FAILURE":
        valid = (source.get("failure_classification") == "ALGORITHM_FAILURE_DIVERGED"
                 and source.get("evaluation_invoked") is False
                 and audit.get("passed") is True and audit.get("trace_open_count") == 0)
    elif continuation_v11 and status == "UNAVAILABLE_EVALUATION_FAILED":
        valid = (source.get("failure_classification") in
                 {"FAILED_EVALUATOR_CONSISTENCY", "UNAVAILABLE_EVALUATION_FAILED"}
                 and source.get("evaluation_invoked") is True
                 and audit.get("technical_passed") is True
                 and audit.get("consistency_passed") is False and audit.get("trace_open_count") == 1)
    else:
        valid = (status in AVAILABLE and audit.get("passed") is True
                 and audit.get("trace_open_count") == 1)
    if not valid:
        raise ValueError("Evaluator open/capture/disposition gate failed; aggregation refused")
    if status in H03_UNAVAILABLE:
        # A rejected evaluation may still have output files; none of their numbers is admitted.
        source = {**source, **{name: "UNAVAILABLE" for name in
                  (*METRIC_FIELDS, "output_epoch_count", "matched_epoch_count", "coverage_ratio")},
                  "error_series_source": "UNAVAILABLE"}
        bias = {"status": status}
    else:
        bias = payload["body_frame_bias"]
    return source, bias


def frozen_comparison_segments(sequences, descriptors=None, error_descriptors=None):
    """Copy exact-window frozen CSV tokens; never derive from thinned NAV or adjacent windows.

    Each descriptor supplies path, sha256 and version. Optional column_map maps
    canonical field names to source names. The original source row and hash are retained.
    """
    candidates = []
    for descriptor in descriptors or ():
        sequence = sequences["BY2O"]
        path = _evidence_path(descriptor["path"], sequence)
        original_rows = list(csv.DictReader(io.StringIO(
            pinned_payload(path, descriptor["sha256"]).decode("utf-8-sig"))))
        mapping = descriptor.get("column_map", {})
        for line, original in enumerate(original_rows, 2):
            row = {**original, **{key: original.get(value) for key, value in mapping.items()}}
            row.setdefault("sequence_id", row.get("dataset_id"))
            row.setdefault("evaluator_contract", "evaluator_contract_"+descriptor["version"])
            if row.get("sequence_id") != "BY2O" or row.get("method_id") not in ("F04", "A04"):
                continue
            row["frozen_source"] = _notes(source_table=alias_path(path, sequence), source_line=line,
                source_table_sha256=descriptor["sha256"], original_row=original, result_reused=True,
                rerun=False, metric_recomputation=False)
            candidates.append(row)
    for descriptor in error_descriptors or ():
        if (descriptor["sequence_id"] != "BY2O" or descriptor["method_id"] not in ("F04", "A04")
                or descriptor["version"] not in ("v3", "v2")):
            raise ValueError("Frozen segment error source is outside BY2O F04/A04 v3/v2 scope")
        sequence = sequences["BY2O"]
        path = _evidence_path(descriptor["path"], sequence)
        payload = pinned_payload(path, descriptor["sha256"])
        if path.suffix == ".gz":
            payload = gzip.decompress(payload)
        errors = pd.read_csv(io.BytesIO(payload), encoding="utf-8-sig")
        provenance = _notes(source=alias_path(path, sequence), source_sha256=descriptor["sha256"],
            frozen_evaluation_reused=True, full_rate_error_series=True, evaluator_invoked=False,
            trace_payload_reads=0, metric_scope="EXACT_CLOSED_WINDOW_OF_FROZEN_ERROR_SERIES",
            archive_provenance=descriptor.get("provenance", {}))
        derived = segment_rows(errors, sequence_id="BY2O", method_id=descriptor["method_id"],
            start_convention="FROZEN_V21", version=descriptor["version"], window=sequence.window,
            source=provenance)
        for row in derived:
            row["frozen_source"] = provenance
        candidates.extend(derived)
    result = []
    for version in ("v3", "v2"):
        for method in ("F04", "A04"):
            placeholders = unavailable_segments(sequence_id="BY2O", method_id=method,
                start_convention="FROZEN_V21", version=version, window=sequences["BY2O"].window,
                source="UNAVAILABLE", status="UNAVAILABLE_FROZEN_SAME_WINDOW_SEGMENT",
                reason="NO_HASH_VERIFIED_FROZEN_ROW_FOR_EXACT_WINDOW; NAV_10HZ_NOT_USED")
            for row in placeholders:
                matches = [r for r in candidates if r["method_id"] == method
                    and r.get("evaluator_contract") == "evaluator_contract_"+version
                    and _number(r.get("window_start_s")) == row["window_start_s"]
                    and _number(r.get("window_end_s")) == row["window_end_s"]]
                if len(matches) > 1:
                    raise ValueError("Duplicate frozen same-window segment identity")
                if matches:
                    frozen = matches[0]
                    row.update({key: frozen.get(key, "UNAVAILABLE") for key in (*METRIC_FIELDS, "count")})
                    row.update(status=frozen.get("status", "AVAILABLE_FROZEN"),
                               error_series_source=frozen["frozen_source"], unavailable_reason="")
                result.append(row)
    return result


def load_frozen_rows(sequences, frozen_pins=None):
    seq = sequences["BY2"]
    pins = {**FROZEN_PINS, **(frozen_pins or {})}
    p07_path = seq.clean_root / P07_TABLE
    p07 = list(csv.DictReader(io.StringIO(pinned_payload(p07_path, pins["p07_v3"]).decode("utf-8-sig"))))
    parity_path = seq.clean_root / PARITY_SUMMARY
    parity = json.loads(pinned_payload(parity_path, pins["parity_summary"]))
    rows = {"v3": [], "v2": []}
    source_records = []
    for version in rows:
        table = seq.clean_root / V21_ROOT / version / "UNIQUE_EVALUATION_RESULTS.csv"
        originals = list(csv.DictReader(io.StringIO(pinned_payload(table, pins["v21_"+version]).decode("utf-8-sig"))))
        chosen = [(line, row) for line, row in enumerate(originals, 2) if row["method_id"] in LEGSA_METHODS]
        if len(chosen) != 15 or len({(r["dataset_id"], r["method_id"]) for _, r in chosen}) != 15:
            raise ValueError("Frozen v2.1 five-method/three-sequence rows incomplete")
        for line, original in chosen:
            note = _notes(source_table=alias_path(table, seq), source_line=line, source_table_sha256=pins["v21_"+version],
                source_row=original.get("source_row"), frozen_scientific_code_commit=original["code_commit"],
                result_reused=True, rerun=False, body_bias_availability="UNAVAILABLE_FULL_RATE_NAV_NOT_RETAINED")
            normalized = normalize_row(original, sequence_id=original["dataset_id"], method_id=original["method_id"],
                config="NOT_APPLICABLE_V21", start="FROZEN_V21", geometric_status="NOT_APPLICABLE", notes=note)
            rows[version].append(normalized)
        for method, horizontal in (("LC01", "LC01_EXT05A"), ("EXT05C", "EXT05C")):
            if version == "v3":
                source = next(r for r in p07 if r["horizontal_method"] == horizontal)
                line = p07.index(source)+2
                errors = p07_path.parent / horizontal / "FROZEN_EVALUATOR"
                source = {**source, "error_series_source": str(errors)}
                bias = None
                table_path, pin = p07_path, pins["p07_v3"]
                rationale = "P07_FROZEN_LITERATURE_ROW_UNCHANGED"
            else:
                source = next(r for r in parity["rows"][version] if r["method_id"] == method)
                bias = next(r for r in parity["body_frame_bias"][version] if r["method_id"] == method)
                line = "rows/v2/"+method
                table_path, pin = parity_path, pins["parity_summary"]
                rationale = "P07_HAS_NO_V2_HORIZONTAL_TABLE_REUSE_PINNED_FROZEN_PARITY_V2_WITHOUT_EVALUATION"
            source = {**source, "evaluator_contract": "evaluator_contract_"+version}
            row = normalize_row(source, sequence_id="BY2", method_id=method, config="LIT", start="FILE_START",
                geometric_status="FROZEN_PRIOR_AUDIT" if method == "LC01" else "NOT_APPLICABLE_SINGLE_RECEIVER",
                notes=_notes(source_table=alias_path(table_path, seq), source_line=line, source_table_sha256=pin,
                             result_reused=True, rerun=False, reason=rationale), body_bias=bias, gaps=0, pacc=20, floats=0)
            rows[version].append(row)
        for sequence_id in ("BY2", "BY2H", "BY2O"):
            for original in p07:
                method = original["horizontal_method"]
                if method not in ("EXT01", "EXT02", "EXT03", "EXT04", "Hartley", "LC02_GINAV", "EXT05B"):
                    continue
                reason = original["availability"]
                row = normalize_row({}, sequence_id=sequence_id, method_id=method, config="NOT_APPLICABLE",
                    start="NOT_EXECUTED", geometric_status="NOT_APPLICABLE",
                    notes=_notes(availability=reason, original_evaluation_status=original["evaluation_status"],
                        frozen_failure=original.get("failure"), source_table=alias_path(p07_path, seq),
                        source_line=p07.index(original)+2, source_table_sha256=pins["p07_v3"],
                        scope="BY2_FROZEN_REGISTRY_REASON; NO_NEW_H_OR_O_EXECUTION"))
                row.update(evaluation_status="UNAVAILABLE", evaluator_contract="evaluator_contract_"+version,
                           code_commit=original["code_commit"], failure_classification=reason)
                rows[version].append(row)
        source_records.append({"version": version, "v21_source_sha256": pins["v21_"+version]})
    return rows, {"pins": pins, "sources": source_records}


def _evidence_path(value, sequence):
    path = Path(str(value).replace("<CLEAN_ROOT>", str(sequence.clean_root)).replace("<HEXT_SCRATCH>", str(sequence.hext_scratch)))
    if Path(sequence.raw_root) in path.parents or path.name.startswith("trace_"):
        raise ValueError("Aggregation never reads raw reference payloads")
    if not any(root == path or root in path.parents for root in (sequence.clean_root, sequence.hext_scratch)):
        raise ValueError("Aggregation evidence must be under resolved clean/scratch roots")
    return path


def validate_run_identities(records):
    """Fourteen slots, with pre-registered static-failure replacement/deduplication."""
    if len(records) > 14 or len({r["run_id"] for r in records}) != len(records):
        raise ValueError("H-EXT-02 aggregation requires unique records within fourteen slots")
    primary = {}
    for sequence in ("BY2", "BY2H", "BY2O"):
        starts = {r.get("primary_start_mode", "FILE_START") for r in records if r["sequence_id"] == sequence}
        if len(starts) != 1 or not starts <= {"FILE_START", "CONTRACT_START"}:
            raise ValueError("Inconsistent primary-start identity")
        primary[sequence] = starts.pop()
    identities = {(r["sequence_id"], r["configuration_id"], r["start_mode"]) for r in records}
    expected = {("BY2", m, primary["BY2"]) for m in ("LC01-S", "EXT05C-S")}
    h_starts = ("FILE_START", "CONTRACT_START") if primary["BY2H"] == "FILE_START" else ("CONTRACT_START",)
    expected |= {("BY2H", m, s) for m in EXTERNAL_METHODS for s in h_starts}
    expected |= {("BY2O", m, primary["BY2O"]) for m in EXTERNAL_METHODS}
    if identities != expected or len(identities) != len(records):
        raise ValueError("Run identities differ from the registered fourteen-slot design")


def aggregate_stage(*, sequences, records, output_root: Path, code_commit: str,
                    budget_ledger: Mapping[str, Any], frozen_pins=None,
                    continuation_v11=False, frozen_segment_sources=None, frozen_error_sources=None):
    """Write 08_AGGREGATE from the bounded, sealed run records."""
    validate_run_identities(records)
    if continuation_v11 and (len(records) != 14 or any(
            r.get("primary_start_mode", "FILE_START") != "FILE_START" for r in records)):
        raise ValueError("H-EXT-03 must preserve the original fourteen native run identities")
    rows, source_manifest = load_frozen_rows(sequences, frozen_pins)
    segments, biases, gaps, geometries, result_sources = [], [], [], [], []
    primary_starts = dict(H03_PRIMARY_STARTS) if continuation_v11 else {name: "FILE_START" for name in sequences}
    for record in records:
        seq = sequences[record["sequence_id"]]
        primary = primary_starts[seq.sequence_id] if continuation_v11 else record.get("primary_start_mode", "FILE_START")
        if primary == "CONTRACT_START" and not continuation_v11:
            primary_starts[seq.sequence_id] = primary
        native_path = _evidence_path(record["native_summary_path"], seq)
        native = _json(native_path)
        geom = native.get("geometric_audit", {})
        single = record["configuration_id"].startswith("EXT05C")
        geom_status = "NOT_APPLICABLE_SINGLE_RECEIVER" if single else (
            ("PASS" if geom["thresholds_pass"] and geom.get("continuity", {}).get("no_180_degree_representation_discontinuity", True) else "FAIL")
            if isinstance(geom.get("thresholds_pass"), bool) else str(geom.get("terminal_status", "UNAVAILABLE")))
        if continuation_v11 and not single and geom_status == "UNAVAILABLE" and geom.get("error"):
            # Preserve the original unavailable statistics, while exposing the failed geometry check.
            geom_status = "FAIL"
        geometric_row = {"run_id": record["run_id"], "sequence_id": seq.sequence_id,
            "method_id": record["configuration_id"], "start_convention": record["start_mode"],
            "geometric_audit_status": geom_status, "audit": geom, "source": alias_path(native_path, seq)}
        geometries.append(geometric_row)
        gap_events = _json(_evidence_path(record["gap_log_path"], seq))
        if isinstance(gap_events, dict):
            gap_events = gap_events.get("events", gap_events.get("gaps", []))
        for event in gap_events:
            gaps.append({"run_id": record["run_id"], "sequence_id": seq.sequence_id,
                "method_id": record["configuration_id"], "start_convention": record["start_mode"], **event})
        gap_count = sum(e.get("window_position") not in ("BEFORE", "AFTER") for e in gap_events)
        for version in ("v3", "v2"):
            result_path = _evidence_path(record["evaluations"][version], seq)
            payload = _json(result_path)
            source, bias = validate_evaluation_payload(payload, version=version,
                                                       continuation_v11=continuation_v11)
            if source["evaluation_status"] == "NOT_RUN_ALGORITHM_FAILURE" and record.get(
                    "native_status") != "ALGORITHM_FAILURE_DIVERGED":
                raise ValueError("Algorithm-failure disposition requires a diverged native classification")
            note = _notes(source=alias_path(result_path, seq), source_sha256=sha256_file(result_path),
                native_source=alias_path(native_path, seq), native_sha256=sha256_file(native_path),
                result_reused=continuation_v11 and record.get("evaluation_dispositions", {}).get(version)
                    == "REUSED_H02_COMPLETED",
                native_result_reused=continuation_v11, scientific_code_commit=source.get("code_commit"),
                static_initialization_waiver=record["start_mode"] == "CONTRACT_START",
                diagnostic_start=record["start_mode"] != primary,
                amended_after_results_seen=continuation_v11 and seq.sequence_id == "BY2H",
                native_status=record.get("native_status", "COMPLETED"),
                historical_evaluation_status=payload.get("historical_evaluation_status", source.get("historical_evaluation_status")),
                historical_evaluation_source=payload.get("historical_evaluation_source", source.get("historical_evaluation_source")))
            row = normalize_row(source, sequence_id=seq.sequence_id, method_id=record["configuration_id"],
                config="S" if record["configuration_id"].endswith("-S") else "LIT", start=record["start_mode"],
                geometric_status=geom_status, notes=note, body_bias=bias, gaps=gap_count,
                pacc={"BY2": 20, "BY2H": 24, "BY2O": 52}[seq.sequence_id], floats=57 if seq.sequence_id == "BY2O" else 0)
            rows[version].append(row)
            biases.append({"sequence_id": seq.sequence_id, "method_id": row["method_id"], "config": row["config"],
                "start_convention": row["start_convention"], "evaluator_contract": row["evaluator_contract"],
                "body_forward_bias_m": row["body_forward_bias_m"], "body_right_bias_m": row["body_right_bias_m"],
                "body_up_bias_m": row["body_up_bias_m"], "status": bias.get("status", "AVAILABLE"), "source": note})
            if source["evaluation_status"] in H03_UNAVAILABLE:
                segments.extend(unavailable_segments(sequence_id=seq.sequence_id, method_id=row["method_id"],
                    start_convention=row["start_convention"], version=version, window=seq.window,
                    source=alias_path(result_path, seq), status=source["evaluation_status"],
                    reason=source["failure_classification"]))
            else:
                errors_root = _evidence_path(source["error_series_source"], seq)
                errors = canonical._read_error_series(errors_root if errors_root.is_dir() else errors_root.parent)
                segments.extend(segment_rows(errors, sequence_id=seq.sequence_id, method_id=row["method_id"],
                    start_convention=row["start_convention"], version=version, window=seq.window,
                    source=alias_path(errors_root, seq)))
            result_sources.append({"run_id": record["run_id"], "version": version,
                "source": alias_path(result_path, seq), "sha256": sha256_file(result_path),
                "evaluation_status": row["evaluation_status"], "failure_classification": row["failure_classification"],
                "evaluation_invoked": source.get("evaluation_invoked", True),
                "trace_open_count": payload["audit"].get("trace_open_count")})
    selection = select_main_config(rows["v3"])
    if continuation_v11:
        if selection["selected_config"] != "S":
            raise ValueError("H-EXT-03 D10 fixed S selection disagrees with frozen BY2 evidence")
        selection.update(authorization="H-EXT-03 prompt 2026-09-16", decision="D10_RECORDED_SELECTION",
                         amended_after_results_seen=True, paper_primary_starts=primary_starts)
        segments.extend(frozen_comparison_segments(sequences, frozen_segment_sources, frozen_error_sources))
    rows = {v: mark_main_rows(values, selection, primary_starts, continuation_v11=continuation_v11)
            for v, values in rows.items()}
    # Frozen biases remain explicit (not reconstructed from thinned NAV).
    for version, values in rows.items():
        for row in values:
            if row["method_id"] not in (*LEGSA_METHODS, "LC01", "EXT05C") or row["sequence_id"] != "BY2" and row["method_id"] not in LEGSA_METHODS:
                continue
            if not json.loads(row["notes"]).get("result_reused"):
                continue
            biases.append({"sequence_id": row["sequence_id"], "method_id": row["method_id"], "config": row["config"],
                "start_convention": row["start_convention"], "evaluator_contract": row["evaluator_contract"],
                "body_forward_bias_m": row["body_forward_bias_m"], "body_right_bias_m": row["body_right_bias_m"],
                "body_up_bias_m": row["body_up_bias_m"], "status": "AVAILABLE_FROZEN" if _number(row["body_forward_bias_m"]) is not None else "UNAVAILABLE_FULL_RATE_NAV_NOT_RETAINED",
                "source": row["notes"]})
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=False)
    for version in ("v3", "v2"):
        _write_csv(output_root / f"HORIZONTAL_TABLE_{version.upper()}_THREE_SEQUENCES.csv", rows[version], TABLE_FIELDS)
    _write_csv(output_root / "DELTA_TABLE_V3.csv", delta_rows(rows["v3"]))
    for name, values in (("WINDOW_SEGMENT_SUMMARY.csv", segments), ("BODY_FRAME_BIAS.csv", biases),
                         ("GAP_EVENTS.csv", gaps), ("GEOMETRIC_AUDIT.csv", geometries)):
        _write_csv(output_root / name, values)
    definitions = {"columns": list(TABLE_FIELDS), "main_row": "selected external LC01 configuration at primary start, plus frozen F01/F02/F03/A04/F04",
        "manuscript_row": "H-EXT-03: globally selected LC01-S at D9 paper start, plus F02/A04/F04; F01/F03 retained in table",
        "failure_classification": "NONE or explicit unavailable/algorithm/evaluator classification; no failed metric becomes zero",
        "config": "LIT/S for external method; NOT_APPLICABLE_V21 for frozen internal methods",
        "unavailable_numeric": "UNAVAILABLE; never zero", "delta": "candidate minus reference; negative better",
        "coverage_ratio": "matched native output epochs / native output epochs within frozen closed window; not reference-row coverage",
        "body_frame_bias": "same frozen yaw-only FRD projection; frozen internal full-rate NAV absent => unavailable",
        "gnss2_pacc_inflated_epochs": "whole-file HPPOSECEF pAcc2 > 3 times BY2 receiver2 median; BY2O=52",
        "gnss2_float_epochs": "separate status fix_type=7 count; BY2O=57",
        "geometric_audit_failure": "AVAILABLE_GEOMETRIC_AUDIT_FAIL retains finite evaluated metrics",
        "occlusion_windows": OCCLUSION_WINDOWS, "selection": selection, "frozen_sources": source_manifest,
        "aggregation_code_commit": code_commit, "trace_payload_reads": 0}
    _write_json(output_root / "FIELD_DEFINITIONS.json", definitions)
    summary = {"status": "COMPLETED_H_EXT_03_AGGREGATION" if continuation_v11 else "COMPLETED_H_EXT_02_AGGREGATION",
        "selection": selection, "primary_starts": primary_starts,
        "native_registered_count": len(records), "external_evaluation_terminal_records": len(result_sources),
        "row_counts": {v: len(values) for v, values in rows.items()},
        "new_native_budget": 0 if continuation_v11 else 14, "new_evaluator_budget": 11 if continuation_v11 else 28,
        "evaluation_disposition_counts": dict(Counter(item["evaluation_status"] for item in result_sources)),
        "failure_classification_counts": dict(Counter(item["failure_classification"] for item in result_sources)),
        "native_classification_counts": dict(Counter(record.get("native_status", "COMPLETED") for record in records)),
        "budget_ledger": dict(budget_ledger), "frozen_sources": source_manifest, "result_sources": result_sources,
        "code_commit": code_commit, "trace_payload_reads": 0, "solver_invocations": 0, "evaluator_invocations": 0,
        "data_mode": "real_external_and_frozen_comparison", "synthetic_data_used": False, "semisynthetic_data_used": False,
        "files_sha256": {p.name: sha256_file(p) for p in output_root.iterdir() if p.is_file()}}
    if not continuation_v11:
        summary["new_evaluation_rows"] = len(result_sources)
    _write_json(output_root / "FINAL_SUMMARY.json", summary)
    return summary
