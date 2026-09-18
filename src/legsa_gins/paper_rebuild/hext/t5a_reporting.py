"""Read-only T5a aggregation and independent publication figures.

No native, evaluator, provider, NAV, or reference trace is opened here. Frozen
scalar fields are copied as CSV strings. New segment metrics use only sealed
full-rate evaluator errors; failed evaluations never contribute numbers.
"""
from __future__ import annotations

import csv
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .aggregate import TABLE_FIELDS, METRIC_FIELDS, AVAILABLE, normalize_row, segment_rows, validate_evaluation_payload
from .readonly_closeout import region_masks, yaw_metrics
from .readonly_reporting import PINS

CONTRACT = Path("configs/paper_rebuild/hext/T5A_CONTRACT_V1.yaml")
LOCAL_CONFIG = Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
SEQUENCES = ("BY2", "BY2H", "BY2O")
PROFILES = ("F02", "F04")
FROZEN = "FROZEN_V21"
UNAVAILABLE = "UNAVAILABLE"
REGIONS = ("full", "occlusion_primary", "occlusion_secondary", "inside_union", "outside")
NUMERIC_FIELDS = (*METRIC_FIELDS, "body_forward_bias_m", "body_right_bias_m", "body_up_bias_m",
                  "output_epoch_count", "matched_epoch_count", "coverage_ratio", "gap_events_in_window",
                  "gnss2_pacc_inflated_epochs", "gnss2_float_epochs")
EXTRA_FIELDS = ("configuration_id", "variant", "role", "frozen_source_table", "frozen_source_line",
                *("delta_" + field for field in NUMERIC_FIELDS))
ERROR_COLUMNS = ("time", "horizontal_err_m", "position_3d_err_m", "err_u_m",
                 "yaw_err_deg", "roll_err_deg", "pitch_err_deg")
COLORS = {FROZEN: "#4D4D4D", "R1": "#0072B2", "R5": "#D55E00", "R1F": "#56B4E9", "R5F": "#E69F00"}
HATCHES = {FROZEN: "", "R1": "///", "R5": "...", "R1F": "\\\\", "R5F": "xx"}


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fields or dict.fromkeys(key for row in rows for key in row)) or ["status"]
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                             if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})


def _csv(payload):
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))


def _number(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def scalar_delta(value, frozen):
    """Exact decimal subtraction of serialized scalar values, without refitting."""
    try:
        left, right = Decimal(str(value)), Decimal(str(frozen))
    except (InvalidOperation, ValueError):
        return UNAVAILABLE
    return str(left - right) if left.is_finite() and right.is_finite() else UNAVAILABLE


def enrich_evaluation_slots(evaluations, native_records, *, matrix, code_freeze,
                            execution_status, adjudication=None):
    """Report-only slot identities and technical dispositions; inputs stay intact.

    A postmortem may invalidate a native run's scientific admission. It never
    upgrades a failed/missing evaluation, fabricates an invocation, or modifies
    the original execution summary. All uninvoked slots remain explicit.
    """
    expected = {f"{sequence}__{profile}__{variant}": (sequence, profile, variant)
                for sequence, item in matrix.items() for profile in item["configurations"]
                for variant in item["variants"]}
    native = {}
    for record in native_records:
        run_id = record.get("run_id") or "__".join(record[key] for key in ("sequence_id", "configuration_id", "variant"))
        if run_id not in expected or run_id in native:
            raise ValueError("Duplicate or unregistered native report identity")
        native[run_id] = record
    document = adjudication or {}
    invalid = {}
    for run_id in document.get("invalid_native_run_ids", []):
        invalid[run_id] = {"classification": document.get("classification"),
                           "status": "TECHNICAL_INVALID", "reason": document.get("reason", document.get("evidence_reason"))}
    for run_id, value in document.get("run_adjudications", {}).items():
        invalid[run_id] = {"classification": value.get("classification", document.get("classification")),
                           "status": value.get("status", "TECHNICAL_INVALID"),
                           "reason": value.get("reason", document.get("reason"))}
    for run_id, value in invalid.items():
        if (run_id not in native or not str(value.get("classification") or "").startswith("TECHNICAL_INVALID")
                or not value.get("reason")):
            raise ValueError("Postmortem must identify an invoked run, technical-invalid classification, and reason")
    lookup = {}
    for payload in evaluations:
        row = payload["row"]
        run_id = row.get("run_id") or "__".join(str(row.get(key)) for key in ("sequence_id", "configuration_id", "variant"))
        version = row.get("evaluator_contract")
        key = (run_id, version)
        if run_id not in expected or version not in ("evaluator_contract_v3", "evaluator_contract_v2") or key in lookup:
            raise ValueError("Duplicate or unregistered evaluator report identity")
        lookup[key] = payload
    result = []
    for run_id, (sequence, profile, variant) in expected.items():
        record = native.get(run_id)
        for version in ("v3", "v2"):
            evaluator_contract = "evaluator_contract_" + version
            existing = lookup.get((run_id, evaluator_contract))
            payload = deepcopy(existing) if existing is not None else {"row": {}}
            row = payload["row"]
            identity = {"run_id": run_id, "sequence_id": sequence, "configuration_id": profile,
                        "variant": variant, "evaluator_contract": evaluator_contract, "code_commit": code_freeze}
            for field, value in identity.items():
                if row.get(field) not in (None, "", UNAVAILABLE, value):
                    raise ValueError("Execution report identity conflicts with frozen slot: " + field)
                row[field] = value
            native_status = record.get("status", "UNAVAILABLE") if record is not None else "NOT_RUN"
            payload["native_status_for_report"] = native_status
            if run_id in invalid:
                value = invalid[run_id]
                invoked = (row.get("evaluation_invoked") is True or row.get("evaluation_status") in AVAILABLE
                           or payload.get("audit", {}).get("trace_open_count") == 1)
                row.update(evaluation_status="UNAVAILABLE_TECHNICAL_INVALID" if invoked else "NOT_RUN_TECHNICAL_INVALID",
                           failure_classification=value["classification"],
                           reason=value["reason"], metrics_admitted=False, evaluation_invoked=invoked)
                payload["native_status_for_report"] = "TECHNICAL_INVALID"
                payload["technical_adjudication"] = dict(value)
                payload["body_frame_bias"] = {}
            elif existing is None:
                if record is None:
                    status = "NOT_RUN_NATIVE_SLOT"
                    classification = "PREDECESSOR_HARD_STOP" if execution_status.startswith("HARD_STOP") else "NOT_EXECUTED"
                elif native_status.startswith("HARD_STOP"):
                    status, classification = "NOT_RUN_NATIVE_HARD_STOP", record.get("failure_classification", native_status)
                elif native_status.startswith("ALGORITHM_FAILURE"):
                    status, classification = "NOT_RUN_ALGORITHM_FAILURE", record.get("failure_classification", native_status)
                elif native_status == "COMPLETED":
                    status, classification = "NOT_RUN_EVALUATOR_SLOT", "EVALUATOR_NOT_INVOKED"
                else:
                    status, classification = "NOT_RUN_NATIVE_UNAVAILABLE", record.get("failure_classification", native_status)
                row.update(evaluation_status=status, failure_classification=classification,
                           reason="No evaluator record; native status: " + native_status,
                           evaluation_invoked=False, metrics_admitted=False)
            result.append(payload)
    return result, invalid


def sensitivity_rows(frozen_rows, evaluations, matrix, version):
    """Pure 6 frozen + 16 variant table construction, including absent slots."""
    frozen = {}
    for line, original in frozen_rows:
        key = (original.get("sequence_id"), original.get("method_id"))
        if key[0] not in SEQUENCES or key[1] not in PROFILES or original.get("start_convention") != FROZEN:
            continue
        if key in frozen:
            raise ValueError("Duplicate frozen T5a comparator")
        if any(field not in original for field in TABLE_FIELDS):
            raise ValueError("Frozen three-sequence table schema changed")
        frozen[key] = (line, original)
    if set(frozen) != {(sequence, profile) for sequence in SEQUENCES for profile in PROFILES}:
        raise ValueError("Six frozen F02/F04 comparator rows are required")
    available = {}
    for payload in evaluations:
        row = payload["row"]
        if row.get("evaluator_contract") != "evaluator_contract_" + version:
            continue
        key = (row.get("sequence_id"), row.get("configuration_id", row.get("method_id")), row.get("variant"))
        if key in available:
            raise ValueError("Duplicate T5a evaluation slot")
        available[key] = payload
    expected = {(sequence, profile, variant) for sequence, item in matrix.items()
                for profile in item["configurations"] for variant in item["variants"]}
    if not set(available) <= expected:
        raise ValueError("Evaluation outside the preregistered T5a matrix")
    result = []
    for sequence in SEQUENCES:
        for profile in PROFILES:
            line, reference = frozen[sequence, profile]
            extras = {"configuration_id": profile, "variant": FROZEN, "role": "FROZEN_COMPARATOR_UNCHANGED",
                      "frozen_source_table": "<HEXT_ROOT>/08_AGGREGATE/HORIZONTAL_TABLE_" + version.upper() + "_THREE_SEQUENCES.csv",
                      "frozen_source_line": line,
                      **{"delta_" + field: scalar_delta(reference[field], reference[field]) for field in NUMERIC_FIELDS}}
            result.append({**{field: reference[field] for field in TABLE_FIELDS}, **extras})
            for variant in matrix[sequence]["variants"]:
                payload = available.get((sequence, profile, variant), {})
                source = dict(payload.get("row", {}))
                admitted = source.get("evaluation_status") in AVAILABLE
                if admitted:
                    validate_evaluation_payload(payload, version=version, continuation_v11=True)
                    if source.get("metrics_admitted") is False or payload["audit"].get("consistency_passed") is False:
                        raise ValueError("Rejected evaluator capture cannot contribute sensitivity metrics")
                if not admitted:
                    source = {**source, **{field: UNAVAILABLE for field in NUMERIC_FIELDS},
                              "error_series_source": UNAVAILABLE,
                              "evaluation_status": source.get("evaluation_status", "NOT_RUN"),
                              "failure_classification": source.get("failure_classification", source.get("reason", "NOT_EXECUTED"))}
                row = normalize_row(source, sequence_id=sequence, method_id=profile, config=profile,
                                    start="FROZEN_V21_RUNTIME_CONFIG", geometric_status="NOT_APPLICABLE",
                                    body_bias=payload.get("body_frame_bias") if admitted else {},
                                    notes=json.dumps({"sensitivity_only": True, "frozen_rows_replaced": 0,
                                                      "variant": variant, "native_run_id": source.get("run_id", "NOT_RUN"),
                                                      "native_status": payload.get("native_status_for_report", "UNAVAILABLE"),
                                                      "technical_adjudication": payload.get("technical_adjudication", "NOT_APPLICABLE")}, sort_keys=True))
                for field in ("gap_events_in_window", "gnss2_pacc_inflated_epochs", "gnss2_float_epochs"):
                    row[field] = source.get(field, "NOT_APPLICABLE")
                row.update({**extras, "variant": variant, "role": "SENSITIVITY_OUTSIDE_FROZEN_CHAIN",
                            **{"delta_" + field: scalar_delta(row[field], reference[field]) if admitted else UNAVAILABLE
                               for field in NUMERIC_FIELDS}})
                result.append(row)
    return result


def derive_segments(errors, *, profile, variant, version, window, source):
    """Same arithmetic and closed regions as H-EXT-04L, over sealed errors."""
    values = segment_rows(errors, sequence_id="BY2O", method_id=profile,
                          start_convention="FROZEN_V21_RUNTIME_CONFIG", version=version,
                          window=window, source=source)
    masks = region_masks(errors["time"], "BY2O", window)
    for row in values:
        row["yaw_median_absolute_deg"] = yaw_metrics(errors.loc[masks[row["segment_id"]], "yaw_err_deg"])["yaw_median_absolute_deg"]
    for region in ("inside_union", "outside"):
        part = errors.loc[masks[region]]
        row = segment_rows(part, sequence_id="COMPLEMENT", method_id=profile,
                           start_convention="FROZEN_V21_RUNTIME_CONFIG", version=version,
                           window=window, source=source)[0]
        row.update(sequence_id="BY2O", segment_id=region,
                   endpoint_policy="UNION_OF_CLOSED_OCCLUSIONS" if region == "inside_union" else "CLOSED_WINDOW_MINUS_CLOSED_OCCLUSIONS",
                   yaw_median_absolute_deg=yaw_metrics(part["yaw_err_deg"])["yaw_median_absolute_deg"])
        values.append(row)
    for row in values:
        row.update(configuration_id=profile, variant=variant, role="SENSITIVITY_OUTSIDE_FROZEN_CHAIN")
    return values


def unavailable_segments(profile, variant, version, reason):
    return [{"sequence_id": "BY2O", "method_id": profile, "configuration_id": profile,
             "variant": variant, "evaluator_contract": "evaluator_contract_" + version,
             "segment_id": region, "count": UNAVAILABLE, "status": UNAVAILABLE,
             "unavailable_reason": reason, "role": "SENSITIVITY_OUTSIDE_FROZEN_CHAIN",
             **{metric: UNAVAILABLE for metric in (*METRIC_FIELDS, "yaw_median_absolute_deg")}}
            for region in REGIONS]


def gating_rows(log, *, sequence, profile, variant, window, source, switches=None):
    """Count actual yaw attempts and classified dispositions, never inferred zeros."""
    required = ("gnss_time", "yaw_update", "yaw_mode")
    if any(field not in log for field in required):
        raise ValueError("Yaw update log lacks required columns")
    if not np.isfinite(log[["gnss_time", "yaw_update"]].to_numpy(float)).all():
        raise ValueError("Nonfinite yaw update log")
    result = []
    for region, mask in region_masks(log["gnss_time"], sequence, window).items():
        part = log.loc[mask]
        attempted_mask = part["yaw_update"].to_numpy(float) == 1
        modes = part["yaw_mode"].astype(str)
        accepted_mask = modes.isin(("NORMAL", "DOWNWEIGHT")).to_numpy()
        rejected_mask = (modes == "REJECT").to_numpy()
        consistent = np.array_equal(attempted_mask, accepted_mask | rejected_mask)
        counts = {"attempted": int(attempted_mask.sum()), "accepted": int(accepted_mask.sum()),
                  "rejected": int(rejected_mask.sum()), "not_attempted": int((~attempted_mask).sum())}
        result.append({"sequence_id": sequence, "configuration_id": profile, "method_id": profile,
                       "variant": variant, "segment_id": region, "epochs": len(part), **counts,
                       "accounting_consistent": consistent, "status": "AVAILABLE" if consistent else "UNAVAILABLE_ACCOUNTING_MISMATCH",
                       "source": source, **(switches or {})})
    return result


class Sources:
    """All report input reads pass a trace/raw denial and optional historical pin."""
    def __init__(self, roots):
        self.roots = {key: Path(value).absolute() for key, value in roots.items()}
        self.hashes = {}

    def resolve(self, value):
        text = str(value)
        for key, root in self.roots.items():
            text = text.replace("<" + key.upper() + ">", str(root))
        if "<" in text:
            raise ValueError("Unresolved report source alias")
        return Path(text).absolute()

    def alias(self, value):
        path = Path(value).absolute()
        for key, root in sorted(self.roots.items(), key=lambda item: len(str(item[1])), reverse=True):
            if path == root or root in path.parents:
                return "<" + key.upper() + ">/" + path.relative_to(root).as_posix()
        return str(path)

    def alias_values(self, value):
        """Map provenance strings only; numerical strings retain every token."""
        if isinstance(value, dict):
            return {key: self.alias_values(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.alias_values(item) for item in value]
        if isinstance(value, str):
            for key, root in sorted(self.roots.items(), key=lambda item: len(str(item[1])), reverse=True):
                value = value.replace(str(root), "<" + key.upper() + ">")
        return value

    def read(self, value, expected=None):
        path = self.resolve(value)
        raw = self.roots.get("raw_root")
        if (path.name.lower().startswith("trace_") or path.suffix.lower() in (".bag", ".fpl", ".nav")
                or raw is not None and (path == raw or raw in path.parents)):
            raise PermissionError("Reporting cannot open raw/trace/NAV input")
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError("Symlink report input forbidden")
        payload = path.read_bytes()
        digest = _sha(payload)
        if expected is not None and digest != expected:
            raise ValueError("Report input SHA-256 mismatch: " + self.alias(path))
        if path in self.hashes and self.hashes[path] != digest:
            raise ValueError("Report input changed during derivation")
        self.hashes[path] = digest
        return payload

    def frame(self, path, expected=None):
        payload = self.read(path, expected)
        if str(path).endswith(".gz"):
            payload = gzip.decompress(payload)
        return pd.read_csv(io.BytesIO(payload), encoding="utf-8-sig")

    def verify_after(self):
        for path, digest in list(self.hashes.items()):
            self.read(path, digest)

    def manifest(self):
        return {self.alias(path): digest for path, digest in sorted(self.hashes.items())}


def _validated_errors(frame):
    if any(field not in frame for field in ERROR_COLUMNS):
        raise ValueError("Full-rate evaluator errors lack required fields")
    result = frame[list(ERROR_COLUMNS)]
    if not len(result) or not np.isfinite(result.to_numpy(float)).all() or np.any(np.diff(result["time"]) <= 0):
        raise ValueError("Unusable full-rate evaluator errors; epoch deletion forbidden")
    return result


def _one_error_path(directory, *, sources=None, seal=None, seal_root=None):
    """Prefer gzip; dual exports must pass both pins and decompressed byte parity."""
    directory = Path(directory)
    if directory.is_file():
        return directory
    plain, compressed = directory / "error_series.csv", directory / "error_series.csv.gz"
    candidates = [path for path in (compressed, plain) if path.is_file()]
    if not candidates:
        raise ValueError("Full-rate evaluator error series unavailable")
    if len(candidates) == 2:
        if sources is None or seal is None or seal_root is None:
            raise ValueError("Dual evaluator error exports require both historical/output seal pins")
        payloads = {}
        for path in (plain, compressed):
            relative = path.relative_to(seal_root).as_posix()
            if relative not in seal:
                raise ValueError("Dual evaluator error export absent from output seal")
            pin = seal[relative]
            expected = pin["sha256"] if isinstance(pin, dict) else pin
            payloads[path] = sources.read(path, expected)
        if payloads[plain] != gzip.decompress(payloads[compressed]):
            raise ValueError("Evaluator plain/gzip error-series byte mismatch")
    return candidates[0]


def _series_file(output, frame, *, sequence, profile, variant, version, source, source_sha256):
    relative = Path("YAW_ERROR_SERIES") / version / (sequence + "__" + profile + "__" + variant + ".csv.gz")
    path = output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = frame[["time", "yaw_err_deg"]].to_csv(index=False, float_format="%.17g").encode()
    with path.open("xb") as handle:
        handle.write(gzip.compress(payload, mtime=0))
    return {"sequence_id": sequence, "configuration_id": profile, "variant": variant,
            "evaluator_contract": "evaluator_contract_" + version, "status": "AVAILABLE", "count": len(frame),
            "path": relative.as_posix(), "sha256": _sha(path.read_bytes()),
            "source": source, "source_sha256": source_sha256, "full_rate": True}


def aggregate_t5a(scratch_root, *, code_freeze, contract_path=CONTRACT, local_paths_path=LOCAL_CONFIG):
    """Build independent tables from the completed/partial execution summary."""
    scratch = Path(scratch_root).absolute()
    local = yaml.safe_load(Path(local_paths_path).read_text(encoding="utf-8"))["paths"]
    if Path(local["t5a_scratch"]).absolute() != scratch:
        raise ValueError("Scratch root differs from ignored T5a local configuration")
    roots = {**{key: local[key] for key in ("clean_root", "raw_root", "code_root", "hext_scratch", "handoff_root") if key in local},
             "t5a_scratch": str(scratch), "hext_root": str(Path(local["clean_root"]) / "stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES")}
    sources = Sources(roots)
    contract = yaml.safe_load(sources.read(contract_path))
    summary = json.loads(sources.read(scratch / "07_HANDOFF/EXECUTION_SUMMARY.json"))
    if summary.get("code_commit") != code_freeze:
        raise ValueError("T5a report code-freeze identity mismatch")
    if summary.get("contract_sha256") != _sha(sources.read(contract_path)):
        raise ValueError("Execution/report contract mismatch")
    windows = contract["definitions"]["D1"]["windows_s"]
    matrix = contract["matrix"]
    adjudication_path = scratch / "07_HANDOFF/POSTMORTEM_ADJUDICATION.json"
    adjudication = json.loads(sources.read(adjudication_path)) if adjudication_path.is_file() else None
    report_evaluations, invalid_native = enrich_evaluation_slots(
        summary.get("evaluations", []), summary.get("native", []), matrix=matrix,
        code_freeze=code_freeze, execution_status=summary["status"], adjudication=adjudication)
    frozen_specs = contract["frozen"]
    spec = frozen_specs["hext04l_data_manifest"]
    h04 = json.loads(sources.read(spec["path"], spec["sha256"]))
    historical_pins = {sources.resolve(row["path"]): row["sha256"] for row in h04["sources"]}
    spec = frozen_specs["hext04l_segments"]
    frozen_segments = _csv(sources.read(spec["path"], spec["sha256"]))
    output = scratch / "05_AGGREGATE"
    output.mkdir(parents=True, exist_ok=False)
    tables, frozen_refs, all_segments, yaw_index, gates = {}, {}, [], [], []
    for version in ("v3", "v2"):
        path = sources.resolve("<HEXT_ROOT>/08_AGGREGATE/HORIZONTAL_TABLE_" + version.upper() + "_THREE_SEQUENCES.csv")
        originals = _csv(sources.read(path, PINS[version]))
        table = sensitivity_rows(list(enumerate(originals, 2)), report_evaluations, matrix, version)
        tables[version] = table
        _write_csv(output / ("SENSITIVITY_TABLE_" + version.upper() + ".csv"), sources.alias_values(table), (*TABLE_FIELDS, *EXTRA_FIELDS))
        for row in table:
            if row["variant"] == FROZEN:
                frozen_refs[row["sequence_id"], row["configuration_id"], version] = row
    native = {(row["sequence_id"], row["configuration_id"], row["variant"]): row for row in summary.get("native", [])}
    if len(native) != len(summary.get("native", [])):
        raise ValueError("Duplicate native run in execution summary")
    for sequence in SEQUENCES:
        for profile in PROFILES:
            config_spec = frozen_specs["runtime_configs"][sequence + "_" + profile]
            config_path = sources.resolve(frozen_specs["runtime_config_template"].replace("<RUN_ID>", config_spec["run_id"]))
            config = yaml.safe_load(sources.read(config_path, config_spec["sha256"]))
            attempt = config_path.parent.parent
            receipt_path = attempt / "ARCHIVE_RECEIPT.json"
            if receipt_path not in historical_pins:
                raise ValueError("H-EXT-04L manifest lacks frozen archive-receipt pin")
            receipt = json.loads(sources.read(receipt_path, historical_pins[receipt_path]))
            retained = receipt["retained_files"]
            log_path = attempt / "solver/PORT_GNSS_UPDATE_TRACE.csv.gz"
            log_key = log_path.relative_to(attempt).as_posix()
            if log_key in retained:
                log = sources.frame(log_path, retained[log_key]["sha256"])
                gates.extend(gating_rows(log, sequence=sequence, profile=profile, variant=FROZEN,
                                         window=windows[sequence], source=sources.alias(log_path),
                                         switches={key: config.get(key, UNAVAILABLE) for key in ("enable_multi_state_qm", "enable_qa_fallback")}))
            else:
                gates.extend(_unavailable_gating(sequence, profile, FROZEN, "FROZEN_LOG_NOT_RETAINED"))
            for version in ("v3", "v2"):
                row = frozen_refs[sequence, profile, version]
                error_path = _one_error_path(sources.resolve(row["error_series_source"]),
                                             sources=sources, seal=retained, seal_root=attempt)
                if attempt not in error_path.parents:
                    raise ValueError("Frozen errors do not belong to the exact retained attempt")
                relative = error_path.relative_to(attempt).as_posix()
                if relative not in retained:
                    raise ValueError("Frozen full-rate errors absent from retained-file seal")
                expected = retained[relative]["sha256"]
                errors = _validated_errors(sources.frame(error_path, expected))
                yaw_index.append(_series_file(output, errors, sequence=sequence, profile=profile,
                                              variant=FROZEN, version=version, source=sources.alias(error_path), source_sha256=expected))
                if sequence == "BY2O":
                    chosen = [original for original in frozen_segments if original.get("method_id") == profile
                              and original.get("evaluator_contract") == "evaluator_contract_" + version]
                    if {original.get("segment_id") for original in chosen} != set(REGIONS) or len(chosen) != len(REGIONS):
                        raise ValueError("H-EXT-04L frozen segments are incomplete or duplicated")
                    all_segments.extend({**original, "configuration_id": profile, "variant": FROZEN,
                                         "role": "FROZEN_H_EXT_04L_ROW_UNCHANGED"} for original in chosen)
            for variant in matrix[sequence]["variants"]:
                record = native.get((sequence, profile, variant))
                gate_values = _native_gates(record, sequence, profile, variant, windows[sequence], sources, scratch)
                run_id = "__".join((sequence, profile, variant))
                if run_id in invalid_native:
                    value = invalid_native[run_id]
                    for gate_row in gate_values:
                        gate_row.update(status="TECHNICAL_DIAGNOSTIC_ONLY" if gate_row["status"] != UNAVAILABLE else "UNAVAILABLE_TECHNICAL_INVALID",
                                        native_status="TECHNICAL_INVALID", failure_classification=value["classification"],
                                        technical_adjudication_reason=value["reason"], metrics_admitted=False,
                                        scientific_evidence_admitted=False)
                gates.extend(gate_values)
                for version in ("v3", "v2"):
                    row = next(item for item in tables[version] if (item["sequence_id"], item["configuration_id"], item["variant"]) == (sequence, profile, variant))
                    if row["evaluation_status"] not in AVAILABLE:
                        yaw_index.append({"sequence_id": sequence, "configuration_id": profile, "variant": variant,
                                          "evaluator_contract": "evaluator_contract_" + version, "status": UNAVAILABLE,
                                          "reason": row["evaluation_status"], "count": UNAVAILABLE, "path": UNAVAILABLE})
                        if sequence == "BY2O":
                            all_segments.extend(unavailable_segments(profile, variant, version, row["evaluation_status"]))
                        continue
                    error_source = sources.resolve(row["error_series_source"])
                    if scratch not in error_source.parents:
                        raise ValueError("New evaluator errors must originate in this scratch attempt")
                    eval_root = error_source.parent.parent if error_source.is_file() else error_source.parent
                    seal = json.loads(sources.read(eval_root / "OUTPUT_SEAL.json"))
                    error_path = _one_error_path(error_source, sources=sources, seal=seal["files"], seal_root=eval_root)
                    relative = error_path.relative_to(eval_root).as_posix()
                    expected = seal["files"][relative]
                    errors = _validated_errors(sources.frame(error_path, expected))
                    yaw_index.append(_series_file(output, errors, sequence=sequence, profile=profile,
                                                  variant=variant, version=version, source=sources.alias(error_path), source_sha256=expected))
                    if sequence == "BY2O":
                        all_segments.extend(derive_segments(errors, profile=profile, variant=variant, version=version,
                                                            window=windows[sequence], source=sources.alias(error_path)))
    _write_csv(output / "BY2O_SEGMENTS_BY_VARIANT.csv", sources.alias_values(all_segments))
    _write_csv(output / "GATING_COUNTS.csv", sources.alias_values(gates))
    _write_csv(output / "YAW_ERROR_SERIES/INDEX.csv", sources.alias_values(yaw_index))
    consistency, diagnostics = [], []
    for item in summary.get("diagnostics", []):
        path = sources.resolve(item["path"])
        if scratch not in path.parents:
            raise ValueError("D4 diagnostics must originate in the current scratch attempt")
        diagnostic = json.loads(sources.read(path))
        diagnostics.append({"sequence_id": item["sequence_id"], "source": sources.alias(path), "payload": diagnostic})
        consistency.extend({"sequence_id": item["sequence_id"], **row} for row in diagnostic.get("source_consistency_rows", []))
    for sequence in SEQUENCES:
        if not any(row.get("sequence_id") == sequence for row in consistency):
            consistency.append({"sequence_id": sequence, "status": UNAVAILABLE, "reason": "D4_NOT_EXECUTED_OR_UNAVAILABLE"})
    _write_csv(output / "SOURCE_CONSISTENCY.csv", sources.alias_values(consistency))
    _write_json(output / "D4_DIAGNOSTICS.json", sources.alias_values(diagnostics))
    sources.verify_after()
    manifest = {"schema_version": "t5a.reporting.v1.1",
                "status": "AGGREGATED" if summary["status"] == "COMPLETED" else "AGGREGATED_PARTIAL_EVIDENCE", "code_commit": code_freeze,
                "execution_status": summary["status"], "native_invocation_count": 0, "evaluator_invocation_count": 0,
                "trace_open_count": 0, "data_mode": summary.get("data_mode", "real_raw_heading_sensitivity_outside_v21"),
                "synthetic_data_used": summary.get("synthetic_data_used", False), "semisynthetic_data_used": summary.get("semisynthetic_data_used", False),
                "frozen_rows_replaced": 0, "table_rows": {version: len(rows) for version, rows in tables.items()},
                "postmortem_adjudication": sources.alias(adjudication_path) if adjudication is not None else "NOT_PRESENT",
                "technical_invalid_native_runs": sources.alias_values(invalid_native),
                "execution_summary_mutated": False,
                "segment_rows": len(all_segments), "gating_rows": len(gates), "yaw_series_rows": len(yaw_index),
                "matrix": matrix, "windows_s": windows, "source_hashes": sources.manifest(),
                "scalar_delta_definition": "Exact decimal subtraction of serialized variant minus frozen scalar values",
                "segment_definition": "H-EXT-04L arithmetic over sealed full-rate errors; closed windows; no metric epoch deletion",
                "files_sha256": {path.relative_to(output).as_posix(): _sha(path.read_bytes())
                                 for path in sorted(output.rglob("*")) if path.is_file()}}
    _write_json(output / "AGGREGATE_MANIFEST.json", manifest)
    return manifest


def _unavailable_gating(sequence, profile, variant, reason):
    regions = REGIONS if sequence == "BY2O" else ("full", "outside")
    return [{"sequence_id": sequence, "configuration_id": profile, "method_id": profile,
             "variant": variant, "segment_id": region, "status": UNAVAILABLE, "reason": reason,
             **{field: UNAVAILABLE for field in ("epochs", "attempted", "accepted", "rejected", "not_attempted")}}
            for region in regions]


def _native_gates(record, sequence, profile, variant, window, sources, scratch):
    if record is None:
        return _unavailable_gating(sequence, profile, variant, "NATIVE_NOT_EXECUTED")
    root = sources.resolve(record["output_root"])
    if scratch not in root.parents:
        raise ValueError("New native output outside current scratch")
    names = [name for name in ("PORT_GNSS_UPDATE_TRACE.csv", "PORT_GNSS_UPDATE_TRACE.csv.gz") if name in record.get("file_hashes", {})]
    if len(names) != 1:
        return _unavailable_gating(sequence, profile, variant, "NATIVE_UPDATE_LOG_UNAVAILABLE")
    name = names[0]
    log = sources.frame(root / name, record["file_hashes"][name])
    config = yaml.safe_load(sources.read(root / "T5A_RUNTIME_CONFIG.yaml", record["config_hash"]))
    return gating_rows(log, sequence=sequence, profile=profile, variant=variant, window=window,
                       source=sources.alias(root / name),
                       switches={key: config.get(key, UNAVAILABLE) for key in ("enable_multi_state_qm", "enable_qa_fallback")})


def _draw_bars(ax, rows, variants, metric, ylabel):
    values = [next((_number(row.get(metric)) for row in rows if row["variant"] == variant), None) for variant in variants]
    for index, (variant, value) in enumerate(zip(variants, values)):
        if value is None:
            ax.text(index, .04, "UNAVAILABLE", rotation=90, ha="center", va="bottom", fontsize=7,
                    transform=ax.get_xaxis_transform())
        else:
            ax.bar(index, value, width=.68, color=COLORS[variant], hatch=HATCHES[variant],
                   edgecolor="#333333", linewidth=.45)
    ax.set_xticks(range(len(variants)), ["Frozen" if variant == FROZEN else variant for variant in variants])
    ax.set_ylim(bottom=0)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)


def render_t5a(scratch_root, *, code_freeze):
    """Render only sealed derived tables/series into a new independent directory."""
    scratch = Path(scratch_root).absolute()
    aggregate = scratch / "05_AGGREGATE"
    sources = Sources({"t5a_scratch": scratch})
    manifest_path = aggregate / "AGGREGATE_MANIFEST.json"
    manifest = json.loads(sources.read(manifest_path))
    if manifest["code_commit"] != code_freeze:
        raise ValueError("Render code-freeze identity mismatch")
    pins = manifest["files_sha256"]

    def read(relative):
        if relative not in pins:
            raise ValueError("Render input missing from aggregate seal")
        return sources.read(aggregate / relative, pins[relative])

    table = _csv(read("SENSITIVITY_TABLE_V3.csv"))
    segments = _csv(read("BY2O_SEGMENTS_BY_VARIANT.csv"))
    index = _csv(read("YAW_ERROR_SERIES/INDEX.csv"))
    diagnostics = json.loads(read("D4_DIAGNOSTICS.json"))
    output = scratch / "06_FIGURES"
    output.mkdir(parents=True, exist_ok=False)
    os.environ["MPLCONFIGDIR"] = str(output / ".mplconfig")
    from ..publication import style, qa
    import matplotlib.pyplot as plt
    plt.rcParams["path.simplify"] = False
    products, qa_rows, plotted_counts = [], [], {}

    def save(fig, figure_id):
        checks = qa.check_figure(fig, figure_id)
        result = style.save_figure(fig, output / figure_id, figure_id)
        checks.extend(qa.check_png(Path(result["png"]), figure_id))
        result = {key: (str(Path(value).relative_to(output)) if key in ("png", "pdf", "svg") else value)
                  for key, value in result.items()}
        result["machine_qa_passed"] = all(row["pass"] for row in checks)
        result["manual_visual_inspection"] = "NOT_PERFORMED_BY_RENDERER"
        products.append(result)
        qa_rows.extend(checks)
        plt.close(fig)

    for sequence in SEQUENCES:
        fig, axes = style.new_figure(1, 2, 2.65, wspace=.28)
        plotted_counts[sequence] = {}
        ranges = []
        for col, profile in enumerate(PROFILES):
            ax = axes[0, col]
            for variant, linestyle in ((FROZEN, "-"), ("R1", "--"), ("R5", ":")):
                item = next((row for row in index if (row["sequence_id"], row["configuration_id"], row["variant"], row["evaluator_contract"])
                             == (sequence, profile, variant, "evaluator_contract_v3")), None)
                label = "Frozen" if variant == FROZEN else variant
                if item is None or item["status"] != "AVAILABLE":
                    ax.plot([], [], color=COLORS[variant], linestyle=linestyle, label=label + " (unavailable)")
                    continue
                frame = pd.read_csv(io.BytesIO(gzip.decompress(read(item["path"]))))
                ax.plot(frame["time"], frame["yaw_err_deg"], color=COLORS[variant], linestyle=linestyle,
                        linewidth=.75, label=label)
                ranges.extend([float(frame["yaw_err_deg"].min()), float(frame["yaw_err_deg"].max())])
                plotted_counts[sequence][profile + "__" + variant] = len(frame)
            ax.axhline(0, color="#222222", linewidth=.5, zorder=0)
            if sequence == "BY2O":
                for low, high in ((3369.94, 3411.95), (3495.94, 3508.94)):
                    ax.axvspan(low, high, color="#BBBBBB", alpha=.22, zorder=-2)
            ax.set_xlim(manifest["windows_s"][sequence])
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Yaw error (deg)")
            ax.text(.5, 1.12, profile, transform=ax.transAxes, ha="center", fontsize=8)
            style.panel_label(ax, chr(97 + col), x=-.13)
            ax.legend(loc="upper center", bbox_to_anchor=(.5, -.24), ncol=3, handlelength=1.8, columnspacing=.8)
        if ranges:
            low, high = min(0., min(ranges)), max(0., max(ranges))
            margin = max((high - low) * .04, .1)
            for ax in axes.flat:
                ax.set_ylim(low - margin, high + margin)
        fig.subplots_adjust(left=.10, right=.985, top=.80, bottom=.28)
        save(fig, "T5A_YAW_TIME_SERIES_" + sequence)

    fig, axes = style.new_figure(6, 2, 8.6, wspace=.30, hspace=.70)
    for sequence_index, sequence in enumerate(SEQUENCES):
        variants = (FROZEN, *manifest["matrix"][sequence]["variants"])
        for metric_index, (metric, label) in enumerate((("yaw_rmse_deg", "Yaw RMSE (deg)"), ("h_rmse_m", "H RMSE (m)"))):
            row_index = sequence_index * 2 + metric_index
            for col, profile in enumerate(PROFILES):
                ax = axes[row_index, col]
                chosen = [row for row in table if row["sequence_id"] == sequence and row["configuration_id"] == profile]
                _draw_bars(ax, chosen, variants, metric, sequence + "\n" + label)
                style.panel_label(ax, chr(97 + row_index * 2 + col), x=-.13)
                if row_index == 0:
                    ax.text(.5, 1.2, profile, transform=ax.transAxes, ha="center", fontsize=8)
            top = max(ax.get_ylim()[1] for ax in axes[row_index])
            for ax in axes[row_index]:
                ax.set_ylim(0, top)
    fig.subplots_adjust(left=.12, right=.985, top=.96, bottom=.05)
    save(fig, "T5A_FIGURE")

    fig, axes = style.new_figure(4, 2, 5.9, wspace=.30, hspace=.72)
    variants = (FROZEN, *manifest["matrix"]["BY2O"]["variants"])
    for region_index, region in enumerate(("inside_union", "outside")):
        for metric_index, (metric, label) in enumerate((("yaw_rmse_deg", "Yaw RMSE (deg)"), ("h_rmse_m", "H RMSE (m)"))):
            row_index = region_index * 2 + metric_index
            for col, profile in enumerate(PROFILES):
                ax = axes[row_index, col]
                chosen = [row for row in segments if row["method_id"] == profile and row["segment_id"] == region
                          and row["evaluator_contract"] == "evaluator_contract_v3"]
                _draw_bars(ax, chosen, variants, metric, ("Inside" if region == "inside_union" else "Outside") + "\n" + label)
                style.panel_label(ax, chr(97 + row_index * 2 + col), x=-.13)
                if row_index == 0:
                    ax.text(.5, 1.2, profile, transform=ax.transAxes, ha="center", fontsize=8)
            top = max(ax.get_ylim()[1] for ax in axes[row_index])
            for ax in axes[row_index]:
                ax.set_ylim(0, top)
    fig.subplots_adjust(left=.12, right=.985, top=.94, bottom=.07)
    save(fig, "T5A_FIGURE_BY2O")

    histogram_records = []
    for item in diagnostics:
        histogram_records.extend(_histogram_records(item["sequence_id"], item["payload"]))
    _write_csv(output / "D4_HISTOGRAM_RENDER_DATA.csv", histogram_records)
    fig, axes = style.new_figure(3, 1, 5.5, hspace=.55)
    for row_index, sequence in enumerate(SEQUENCES):
        ax = axes[row_index, 0]
        records = [row for row in histogram_records if row["sequence_id"] == sequence]
        if records:
            left = np.asarray([row["bin_left_deg"] for row in records])
            right = np.asarray([row["bin_right_deg"] for row in records])
            ax.bar(left, [row["count"] for row in records], width=right-left, align="edge",
                   color="#0072B2", edgecolor="#333333", linewidth=.45)
        else:
            ax.text(.5, .5, "UNAVAILABLE", transform=ax.transAxes, ha="center")
        ax.set_xlabel("Raw minus A1 yaw (deg)")
        ax.set_ylabel(sequence + "\nEpochs (count)")
        ax.set_xlim(-180, 180)
        ax.set_ylim(bottom=0)
        style.panel_label(ax, chr(97 + row_index), x=-.08)
    fig.subplots_adjust(left=.12, right=.98, top=.95, bottom=.10)
    save(fig, "T5A_SOURCE_CONSISTENCY_HISTOGRAM")
    sources.verify_after()
    _write_csv(output / "FIGURE_QA.csv", qa_rows)
    render_manifest = {"schema_version": "t5a.render.v1", "code_commit": code_freeze,
                       "status": "PASS_MACHINE_QA" if all(row["pass"] for row in qa_rows) else "FIGURE_QA_ISSUES_RECORDED",
                       "data_mode": manifest["data_mode"], "synthetic_data_used": manifest["synthetic_data_used"],
                       "semisynthetic_data_used": manifest["semisynthetic_data_used"],
                       "source_hashes": sources.manifest(), "figures": products,
                       "time_series_points_plotted": plotted_counts, "line_data_decimation": False,
                       "native_invocation_count": 0, "evaluator_invocation_count": 0, "trace_open_count": 0,
                       "original_28_figures_modified": False, "manual_visual_inspection": "NOT_PERFORMED_BY_RENDERER"}
    _write_json(output / "T5A_RENDER_MANIFEST.json", render_manifest)
    return render_manifest


def _histogram_records(sequence, diagnostic):
    """Extract preregistered bins from full-window D4 rows, without reading trace."""
    # D4 owns the scope and histogram arithmetic. This renderer merely flattens
    # a declared whole evaluation-window signed histogram when one is present.
    declared = [row for row in diagnostic.get("histograms", [])
                if row.get("scope") == "evaluation_window" and row.get("quality") == "all"]
    if declared:
        return [{"sequence_id": sequence, "scope": "evaluation_window",
                 "bin_left_deg": row["bin_left_deg"], "bin_right_deg": row["bin_right_deg"], "count": row["count"]}
                for row in declared]
    rows = diagnostic.get("source_consistency_rows", [])
    candidates = [row for row in rows if row.get("scope") in ("closed_window", "evaluation_window", "window")
                  and row.get("segment_id", row.get("region", "full")) == "full"
                  and row.get("acceleration_bin", "all") in ("all", "ALL", "NOT_APPLICABLE")
                  and row.get("carrier_group", "all") in ("all", "ALL")]
    for row in candidates:
        edges = row.get("histogram_edges_deg")
        counts = row.get("histogram_counts")
        if edges is not None and counts is not None and len(edges) == len(counts) + 1:
            return [{"sequence_id": sequence, "scope": "closed_window", "bin_left_deg": low,
                     "bin_right_deg": high, "count": count}
                    for low, high, count in zip(edges[:-1], edges[1:], counts)]
    return []
