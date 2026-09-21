"""Append-only aggregation recovery from sealed V3-01-R terminal ledgers.

This module has no runtime context and cannot dispatch a solver or evaluator.
The original stop and operational STATE remain immutable; recovery has its own
state. Scientific reporting functions and their original freeze remain intact.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml

from .resume_storage import (CONTINUATION, Heartbeat, persist, persist_bytes,
                             read_json, safe, report_output_io)
from ..manifest import sha256_file

SCIENCE_FREEZE = "7d43b9af26120ed5dde21f53e515386361072ba6"
TRACE_SOURCE = "src/legsa_gins/datasets/by2/trace_reference_adapter.py"
TRACE_SOURCE_SHA256 = "2c4356af0e9948580c84fc3da7ce7353e1c3f6a838dc8ad72839625e721fb935"
F04_YAW = dict(BY2="1.886272", BY2H="1.933770", BY2O="2.433815")
T5AR_TABLE = "stages/CLEAN7_T5A_HEADING_SENSITIVITY/T5A_R/05_AGGREGATE/SENSITIVITY_TABLE_V3.csv"
T5AR_TABLE_SHA256 = "fd8ed33b803845a3a3b1c72ac5cf57c59e2a90654509da069f81aa5961328ee6"
VERSIONS = ("v3", "v2")
TERMINALS = {"COMPLETED", "ALGORITHM_FAILURE_DIVERGED", "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT"}


def within(path, root):
    return path == root or root in path.parents


class Pins:
    """Every read binding is retained in the recovery admission record."""
    def __init__(self):
        self.used = {}

    def check(self, path, digest=None):
        path = safe(path)
        actual = sha256_file(path)
        if digest is not None and actual != digest:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_PIN: " + str(path))
        if str(path) in self.used and self.used[str(path)] != actual:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_INPUT_CHANGED: " + str(path))
        self.used[str(path)] = actual
        return path

    def json(self, path, digest=None):
        return read_json(self.check(path, digest))

    def pin_json(self, pin):
        return self.json(pin["path"], pin["sha256"])


@contextmanager
def aggregation_guard(raw_root, code_root):
    """Deny raw sources and process launch; one exact source module is allowed.

    Python audit hooks cannot be unregistered. This hook is active only within
    this scope and its source exception is checked before every permitted open.
    """
    raw, code = safe(raw_root), safe(code_root)
    source = safe(code / TRACE_SOURCE)
    if sha256_file(source) != TRACE_SOURCE_SHA256:
        raise RuntimeError("HARD_STOP_V3R_TRACE_SOURCE_HASH")
    active = True
    checking = False
    audit = dict(raw_source_reads=0, trace_data_reads=0, source_module_opens=0,
                 denied_opens=[], process_launches=0)

    def hook(event, args):
        nonlocal checking
        if not active:
            return
        if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "os.exec", "os.fork", "os.forkpty"):
            audit["process_launches"] += 1
            raise PermissionError("HARD_STOP_V3R_AGGREGATION_PROCESS_LAUNCH")
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        lexical = Path(os.fsdecode(args[0])).absolute()
        path = Path(os.path.realpath(lexical))
        forbidden = (within(path, raw) or path.suffix.lower() in (".bag", ".fpl")
            or path.name.lower().startswith("trace_") or lexical.name.lower().startswith("trace_"))
        if not forbidden:
            return
        # This exception never admits raw data, sibling modules or bytecode.
        mode, flags = args[1:3]
        writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if path == source and not within(path, raw) and not writing:
            if not checking:
                checking = True
                try:
                    if sha256_file(source) != TRACE_SOURCE_SHA256:
                        raise RuntimeError("HARD_STOP_V3R_TRACE_SOURCE_HASH")
                finally:
                    checking = False
                audit["source_module_opens"] += 1
            return
        audit["denied_opens"].append(str(path))
        raise PermissionError("HARD_STOP_V3R_AGGREGATION_RAW_DENIED: " + str(path))

    sys.addaudithook(hook)
    try:
        yield audit
    finally:
        active = False


def validate_coverage(specs, native, evaluations, *, expected_native=6468):
    expected = {s["run_id"] for s in specs}
    actual = [r["run_id"] for r in native]
    pairs = [(p["row"]["run_id"], p["row"]["evaluator_contract"]) for p in evaluations]
    if len(specs) != expected_native or len(expected) != expected_native or len(actual) != expected_native or set(actual) != expected:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_NATIVE_COVERAGE")
    if len(pairs) != 2 * expected_native or set(pairs) != {(rid, "evaluator_contract_" + v) for rid in expected for v in VERSIONS}:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_EVALUATOR_COVERAGE")
    for row in native:
        if row.get("code_commit") != SCIENCE_FREEZE or row.get("status") not in TERMINALS:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_NATIVE_IDENTITY")
        audit = row.get("access_audit", {})
        if audit.get("trace_open_count") != 0 or row.get("trace_open_count") != 0 or audit.get("passed") is not True:
            raise RuntimeError("HARD_STOP_V3R_NATIVE_TRACE_AUDIT")
        echo = row.get("effective_echo_gate", {}).get("passed")
        if echo is not True and not (echo is None and row["status"].startswith("ALGORITHM_FAILURE_")):
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_EFFECTIVE_ECHO")
    for payload in evaluations:
        row = payload["row"]
        if row.get("code_commit") != SCIENCE_FREEZE:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_EVALUATION_FREEZE")
        if row.get("evaluation_invoked"):
            if payload.get("audit", {}).get("trace_open_count") != 1 or payload["audit"].get("passed") is not True:
                raise RuntimeError("HARD_STOP_V3R_EVALUATOR_TRACE_AUDIT")
        elif row.get("evaluation_status") != "NOT_RUN_ALGORITHM_FAILURE":
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_EVALUATION_NOT_INVOKED")


def f04_gate(evaluations, reference_rows=None):
    actual, precise = {}, {}
    for payload in evaluations:
        row = payload["row"]
        if (row["evaluator_contract"] == "evaluator_contract_v3" and row["method_id"] == "F04"
                and (row["domain"] == "SEQUENCE" or row["case_id"] == "C00_clean_normal")):
            seq = row["sequence_id"]
            if seq in actual or row.get("evaluation_status") != "COMPLETED":
                raise RuntimeError("HARD_STOP_V3R_F04_DUPLICATE_OR_FAILURE")
            actual[seq] = format(float(row["yaw_rmse_deg"]), ".6f")
            precise[seq] = float(row["yaw_rmse_deg"])
    if actual != F04_YAW:
        raise RuntimeError("HARD_STOP_V3R_F04_T5AR_MISMATCH: " + str(actual))
    result = dict(status="PASS", expected=F04_YAW, actual=actual, actual_full_precision=precise,
                  precision="six_decimal_places")
    if reference_rows is not None:
        selected = [r for r in reference_rows if r["method_id"] == "F04" and r["variant"] == "R5"]
        reference = {r["sequence_id"]: float(r["yaw_rmse_deg"]) for r in selected}
        if len(selected) != 3 or reference != precise:
            raise RuntimeError("HARD_STOP_V3R_F04_T5AR_FULL_PRECISION_MISMATCH")
        result.update(t5ar_full_precision_identical=True, precision="full_CSV_scalar_and_six_decimal_display",
            t5ar_table=dict(path="<CLEAN_ROOT>/" + T5AR_TABLE, sha256=T5AR_TABLE_SHA256),
            pin_authority="configs/paper_rebuild/hext/T5BC_FROZEN_SOURCE_INDEX.yaml:t5a_r.tables.SENSITIVITY_TABLE_V3.csv")
    return result


def validate_audit(summary, stop_sha):
    expected = dict(status="PASS", native_count=6468, evaluator_terminal_slots=12936,
        native_trace_open_count=0, evaluator_each_trace_exactly_one=True,
        native_calls=0, evaluator_calls=0, raw_trace_reads=0, completed_batches=279,
        original_hard_stop_sha256=stop_sha)
    for key, value in expected.items():
        if summary.get(key) != value:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_OPENAT_GATE: " + key)


def main_table_f04_gate(rows, expected):
    selected = [r for r in rows if r["method_id"] == "F04"]
    actual = {r["sequence_id"]: float(r["yaw_rmse_deg"]) for r in selected}
    if (len(rows) != 52 or len(selected) != 3 or actual != expected
            or any(r["evaluation_status"] != "COMPLETED" for r in selected)):
        raise RuntimeError("HARD_STOP_V3R_MAIN_TABLE_F04_T5AR_MISMATCH")


def read_reused(payload, run_id, version, control, pins):
    slot = control / "RETENTION_OVERLAYS" / run_id / version
    complete = slot / "RETENTION_COMPLETE.json"
    if not complete.exists():
        return payload
    done = pins.json(complete)
    if done.get("status") != "PASS_EXACT_ERROR_SERIES_RETENTION" or done.get("original_records_rewritten") is not False:
        raise RuntimeError("HARD_STOP_V3R_RETENTION_OVERLAY_INCOMPLETE")
    overlay = pins.pin_json(done["overlay"])
    pins.pin_json(done["original_archive_receipt"])
    if done["release_journal"]["sha256"]:
        pins.check(done["release_journal"]["path"], done["release_journal"]["sha256"])
    derived = pins.json(slot / "DERIVED_EVALUATION_RECORD.json")
    if derived != {**payload, "archive_receipt": done["overlay"]["path"]} or overlay.get("storage_overlay_only") is not True:
        raise RuntimeError("HARD_STOP_V3R_RETENTION_OVERLAY_CHANGED")
    return derived


def load_terminals(archive, scratch, pins):
    control = archive / "00_CONTROL" / CONTINUATION
    regroot = scratch / "00_PREREGISTRATION"
    regseal = pins.json(regroot / "REGISTRY_FILE_SEAL.json")
    specs = pins.json(regroot / "REGISTRY.json", regseal["sha256"])
    reconciliation = pins.pin_json(pins.json(control / "RECONCILIATION_PIN.json"))
    if reconciliation.get("status") != "PASS_ARCHIVE_RECONCILIATION" or reconciliation.get("science_freeze") != SCIENCE_FREEZE or reconciliation.get("completed_batch_count") != 8:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_RECONCILIATION")
    for pin in reconciliation["files"]:
        pins.check(pin["path"], pin["sha256"])
    reused, native, evaluations = set(), [], []
    for item in reconciliation["reused_runs"]:
        rid = item["run_id"]
        if rid in reused or set(item["evaluations"]) != set(VERSIONS):
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_REUSED_COVERAGE")
        reused.add(rid)
        record = pins.pin_json(item["native_record"])
        if record["run_id"] != rid:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_REUSED_IDENTITY")
        native.append(record)
        for version in VERSIONS:
            payload = pins.pin_json(item["evaluations"][version])
            if payload["row"]["run_id"] != rid or payload["row"]["evaluator_contract"] != "evaluator_contract_" + version:
                raise RuntimeError("HARD_STOP_V3R_RECOVERY_REUSED_EVALUATOR")
            evaluations.append(read_reused(payload, rid, version, control, pins))
    if len(reused) != 512:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_REUSED_COUNT")
    pending = [s for s in specs if s["run_id"] not in reused]
    for number, start in enumerate(range(0, len(pending), 22), 1):
        closed = pins.json(control / "BATCHES" / f"BATCH_{number:04d}" / "BATCH_COMPLETE.json")
        ids = [s["run_id"] for s in pending[start:start + 22]]
        if closed.get("status") != "PASS_COMPACT_BATCH_COMPLETE" or closed.get("run_ids") != ids:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_BATCH_IDENTITY")
        nrows, erows = pins.pin_json(closed["native_records"]), pins.pin_json(closed["evaluation_records"])
        if len(nrows) != len(ids) or {r["run_id"] for r in nrows} != set(ids) or len(erows) != 2 * len(ids):
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_BATCH_COUNTS")
        native.extend(nrows)
        evaluations.extend(erows)
    if number != 271:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_BATCH_COUNT")
    validate_coverage(specs, native, evaluations)
    return specs, sorted(native, key=lambda r: r["run_id"]), sorted(evaluations,
        key=lambda p: (p["row"]["run_id"], p["row"]["evaluator_contract"]))


def source_freeze(code, scratch, archive, repair_commit, pins):
    if not re.fullmatch(r"[0-9a-f]{40}", repair_commit):
        raise ValueError("A complete repair commit is required")
    # Read-only Git, before the no-process reporting guard is installed.
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=code).decode().strip()
    if head != repair_commit:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_REPAIR_COMMIT_NOT_HEAD")
    freeze = pins.json(archive / "00_CONTROL" / CONTINUATION / "CONTINUATION_FREEZE.json")
    if freeze.get("status") != "PASS_PUSHED_CONTINUATION_FROZEN_SCIENCE" or freeze.get("science_freeze") != SCIENCE_FREEZE:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_FREEZE")
    original = pins.json(scratch / "00_PREREGISTRATION/EXECUTION_FREEZE.json")
    if original.get("code_freeze") != SCIENCE_FREEZE or original.get("status") != "PASS_PUSHED_CODE_FREEZE":
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_ORIGINAL_FREEZE")
    for name in ("src/legsa_gins/paper_rebuild/protocol_v3/aggregate_recovery.py",
                 "scripts/paper_rebuild/v3r_aggregate_recovery.py"):
        blob = subprocess.check_output(["git", "show", repair_commit + ":" + name], cwd=code)
        pins.check(code / name, hashlib.sha256(blob).hexdigest())
    return freeze


def recovery_records(roots, repair_commit, audit_sha256):
    code, clean, scratch = (safe(roots[k]) for k in ("code_root", "clean_root", "protocol_v3_scratch"))
    archive = clean / "stages/CLEAN8_PROTOCOL_V3"
    if Path("/mnt/g") not in archive.parents or scratch.name != "CLEAN8_PROTOCOL_V3":
        raise PermissionError("HARD_STOP_V3R_RECOVERY_ROOTS")
    control, recovery = archive / "00_CONTROL" / CONTINUATION, archive / "00_CONTROL/AGGREGATE_RECOVERY"
    pins = Pins()
    freeze = source_freeze(code, scratch, archive, repair_commit, pins)
    with aggregation_guard(roots["raw_root"], code) as guard:
        for name, digest in freeze["source_sha256"].items():
            pins.check(code / name, digest)
        stop_path = control / "HARD_STOP.json"
        stop, state = pins.json(stop_path), pins.json(archive / "00_CONTROL/STATE.json")
        if (stop.get("error") != "V3 trace/bag/fpl only in registered evaluator child"
                or stop.get("all_started_workers_drained") is not True or stop.get("science_freeze") != SCIENCE_FREEZE
                or state.get("status") != "HARD_STOP" or state.get("completed_batches") != 279):
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_ORIGINAL_STOP")
        audit = pins.json(recovery / "OPENAT_AUDIT_SUMMARY.json", audit_sha256)
        validate_audit(audit, pins.used[str(stop_path)])
        pins.check(recovery / "OPENAT_AUDIT_ROWS.csv", audit["audit_rows_sha256"])
        source_pins = pins.json(recovery / "OPENAT_SOURCE_PINS.json", audit["source_pins_sha256"])
        for path, digest in source_pins.items():
            pins.check(path, digest)
        specs, native, evaluations = load_terminals(archive, scratch, pins)
        with pins.check(clean / T5AR_TABLE, T5AR_TABLE_SHA256).open(newline="") as stream:
            f04 = f04_gate(evaluations, list(csv.DictReader(stream)))
        gates = pins.json(scratch / "IDENTITY_GATES.json")
        if gates.get("status") != "PASS" or set(gates["gates"]) != {"2a", "2b", "2c", "2d", "2e"} or any(g["status"] != "PASS" for g in gates["gates"].values()):
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_IDENTITY_GATES")
        final_gates = deepcopy(gates)
        final_gates["gates"]["2c"].update(phase="COMPLETED_NATIVE_ADMISSION",
            actual_211_echo_pass_count=sum(r.get("effective_echo_gate", {}).get("passed") is True for r in native),
            actual_echo_unavailable_classified_failure_count=sum(r.get("effective_echo_gate", {}).get("passed") is None and r["status"].startswith("ALGORITHM_FAILURE_") for r in native),
            actual_echo_unavailable_not_a_pass=True)
        # Preserve original records verbatim before making FINAL aliases.
        persist_bytes(recovery / "ORIGINAL_STATE.json", (archive / "00_CONTROL/STATE.json").read_bytes())
        persist_bytes(recovery / "ORIGINAL_HARD_STOP.json", stop_path.read_bytes())
        persist_bytes(recovery / "ORIGINAL_PROGRESS.txt", (archive / "00_CONTROL/PROGRESS.txt").read_bytes())
        for name, value in (("FINAL_RUN_RECORDS.json", native), ("FINAL_EVALUATION_RECORDS.json", evaluations), ("FINAL_IDENTITY_GATES.json", final_gates)):
            persist(archive / name, value)
        status = dict(status="PASS_V3_EXECUTION_COMPLETE", science_freeze=SCIENCE_FREEZE,
            aggregation_repair_commit=repair_commit, continuation_commit=freeze["continuation_commit"],
            native_terminal_count=len(native), evaluator_terminal_count=len(evaluations),
            completed_batches=279, native_calls_in_recovery=0, evaluator_calls_in_recovery=0,
            final_run_records_sha256=sha256_file(archive / "FINAL_RUN_RECORDS.json"),
            final_evaluation_records_sha256=sha256_file(archive / "FINAL_EVALUATION_RECORDS.json"),
            automatic_native_retries=0, trace_open_count_parent=0,
            original_hard_stop_preserved=True, f04_t5ar_identity=f04)
        persist(archive / "STATUS.json", status)
        receipt = dict(status="PASS_AGGREGATION_RECOVERY_ADMISSION", science_freeze=SCIENCE_FREEZE,
            repair_commit=repair_commit, original_hard_stop_sha256=pins.used[str(stop_path)],
            original_state_sha256=pins.used[str(archive / "00_CONTROL/STATE.json")],
            openat_audit_sha256=audit_sha256, input_sha256=pins.used,
            native_count=len(native), evaluator_terminal_slots=len(evaluations), completed_batches=279,
            native_calls=0, evaluator_calls=0, data_mode="existing_sealed_result_metadata",
            synthetic_data_used=False, semisynthetic_data_used=True, f04_t5ar_identity=f04, access_guard=guard)
        persist(recovery / "ADMISSION.json", receipt)
        return receipt


def verify_render(root, render):
    if render.get("status") != "COMPLETE" or render.get("rendered_count") != 10 or render.get("code_freeze") != SCIENCE_FREEZE:
        raise RuntimeError("HARD_STOP_V3R_REQUIRED_FIGURE_OR_MACHINE_QA_INCOMPLETE")
    expected = {*(f"MFIG{i:02}" for i in range(7)), "SFIG01", "FIG02S", "FIG02S-b"}
    if len(render.get("figures", [])) != 10 or {e.get("figure_id") for e in render["figures"]} != expected:
        raise RuntimeError("HARD_STOP_V3R_FIGURE_COVERAGE")
    for entry in render["figures"]:
        if entry.get("status") != "RENDERED" or not entry.get("qa") or not all(row.get("pass") is True for row in entry["qa"]):
            raise RuntimeError("HARD_STOP_V3R_FIGURE_QA")
        if set(entry.get("output_sha256", {})) != {"png", "pdf", "svg"}:
            raise RuntimeError("HARD_STOP_V3R_FIGURE_EXPORT_COVERAGE")
        for ext, digest in entry["output_sha256"].items():
            if sha256_file(root / "08_FIGURES" / entry["figure_id"] / (entry["figure_id"] + "." + ext)) != digest:
                raise RuntimeError("HARD_STOP_V3R_FIGURE_HASH")


def failure_family_rows(current, frozen, version):
    """Explicit family x configuration x outcome, including zero-count F02."""
    profiles = ("F01", "F02", "F03", "A04", "F04", "A03", "A05", "A06", "A07", "A08", "A09")
    result = []
    for protocol, rows, field in (("v3", current, "failure_classification"), ("v2.1", frozen, "solver_terminal_status")):
        groups = Counter((r["case_family"], r["method_id"]) for r in rows)
        failures = Counter((r["case_family"], r["method_id"], r.get(field, "NONE")) for r in rows if r["evaluation_status"] == "NOT_RUN_ALGORITHM_FAILURE")
        classes = sorted({key[2] for key in failures})
        total = sum(failures.values())
        if total != (283 if protocol == "v3" else 177):
            raise RuntimeError("HARD_STOP_V3R_FAILURE_TOTAL: " + protocol)
        for family in sorted({r["case_family"] for r in rows}):
            for method in profiles:
                for classification in classes:
                    if not classification.startswith("ALGORITHM_FAILURE_"):
                        raise RuntimeError("HARD_STOP_V3R_FAILURE_CLASSIFICATION")
                    result.append(dict(evaluator_version=version, protocol=protocol, case_family=family,
                        method_id=method, failure_classification=classification,
                        failure_count=failures[family, method, classification], registered_count=groups[family, method],
                        authoritative_classification_field=field))
    return result


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def corrected_failure_comparison(comparison, frozen):
    """Only replace the frozen exporter field with its authoritative class."""
    key = lambda r: (r["dataset_id"], r["case_id"], r["method_id"])
    old = {key(r): r for r in frozen}
    if len(old) != len(frozen):
        raise RuntimeError("HARD_STOP_V3R_FROZEN_COMPARISON_DUPLICATE")
    output = []
    for row in comparison:
        original = old[key(row)]
        if original["evaluation_status"] != row["v21_status"]:
            raise RuntimeError("HARD_STOP_V3R_FROZEN_COMPARISON_STATUS")
        classification = original.get("solver_terminal_status", "")
        if original["evaluation_status"] == "COMPLETED":
            classification = "NONE"
        elif classification != "ALGORITHM_FAILURE_ALL_YAW_REJECTED":
            raise RuntimeError("HARD_STOP_V3R_FROZEN_COMPARISON_CLASS")
        if row["v21_failure"] not in ("", "NONE", classification):
            raise RuntimeError("HARD_STOP_V3R_UNEXPECTED_PRIOR_COMPARISON_CLASS")
        output.append({**row, "v21_failure": classification})
    return output


def report_appendix(archive, index, roots, repair_commit):
    from . import reporting
    folder = archive / "07C_FAILURE_FAMILY_CONFIG"
    sources, family, outputs, manuscript = reporting.Sources(roots), [], {}, []
    def rows(name):
        with (archive / "07_AGGREGATE" / name).open(newline="") as stream:
            return list(csv.DictReader(stream))
    for version in VERSIONS:
        current = rows("CORE_541_TABLE_" + version.upper() + ".csv")
        frozen = sources.rows(index["frozen_core"][version])
        family.extend(failure_family_rows(current, frozen, version))
        ablation = rows("SEQUENCE_TABLE_" + version.upper() + ".csv")
        if len(ablation) != 33 or len({(r["sequence_id"], r["method_id"]) for r in ablation}) != 33:
            raise RuntimeError("HARD_STOP_V3R_FULL_ABLATION_COVERAGE")
        outputs["FULL_ABLATION_TABLE_" + version.upper() + ".csv"] = ablation
        for cohort in ("CORE_541", "SUBSET61"):
            name = cohort + "_V21_COMPARISON_" + version.upper() + ".csv"
            outputs[name] = corrected_failure_comparison(rows(name), frozen)
        if version == "v3":
            manuscript = ["# Protocol v3 full ablation and failure comparison", "",
                "The companion full ablation contains all eleven configurations for each of the three sequences. "
                "The frozen 52-row main table remains unchanged. In the failure comparison, v2.1 classification "
                "comes from solver_terminal_status. Only the old comparison classification token is corrected; "
                "all numerical values, failed-row memberships and other fields remain unchanged.", "",
                "| Sequence | Configuration | Horizontal RMSE (m) | Up RMSE (m) | Yaw RMSE (deg) | Status |",
                "|---|---|---:|---:|---:|---|"]
            def formatted(row, field):
                try:
                    return format(float(row[field]), ".6f")
                except (ValueError, KeyError):
                    return "UNAVAILABLE"
            manuscript += ["| " + " | ".join((r["sequence_id"], r["method_id"], formatted(r, "horizontal_rmse_m"),
                formatted(r, "up_rmse_m"), formatted(r, "yaw_rmse_deg"), r["evaluation_status"])) + " |" for r in ablation]
    outputs["FAILURE_FAMILY_CONFIG.csv"] = family
    for name, rows_ in outputs.items():
        persist_bytes(folder / name, csv_bytes(rows_))
    persist_bytes(folder / "MANUSCRIPT_FULL_ABLATION_AND_FAILURES.md", ("\n".join(manuscript) + "\n").encode())
    manifest = dict(status="PASS_REPORT_ONLY_FULL_ABLATION_AND_FAILURE_FAMILY_CONFIG", native_calls=0,
        evaluator_calls=0, data_mode="existing_sealed_mixed_real_and_semisynthetic_result_metadata", synthetic_data_used=False,
        semisynthetic_data_used=True, science_freeze=SCIENCE_FREEZE, repair_commit=repair_commit,
        v3_failures=283, v21_failures=177, f02_separate=True, full_ablation_rows_per_version=33,
        corrected_field_only="v21_failure", numeric_tokens_changed=0, original_files_changed=0,
        source_sha256=sources.used, files_sha256={p.name: sha256_file(p) for p in folder.iterdir() if p.is_file() and p.name != "MANIFEST.json"})
    persist(folder / "MANIFEST.json", manifest)
    return manifest


def operational_state(archive, admission, phase, done=None):
    """Update requested operational views; original stop/state stay preserved."""
    recovery = archive / "00_CONTROL/AGGREGATE_RECOVERY"
    state = read_json(recovery / "ORIGINAL_STATE.json")
    state.update(phase=phase, status=phase if phase in ("DONE", "HARD_STOP") else "ACTIVE",
        updated_utc=datetime.now(timezone.utc).isoformat(), eta_seconds=0 if phase == "DONE" else None,
        estimated_completion_utc=None,
        aggregation_repair_commit=admission["repair_commit"],
        historical_hard_stop=state.pop("latest_hard_stop", None), latest_hard_stop=None,
        original_hard_stop_sha256=admission["original_hard_stop_sha256"],
        original_state_sha256=admission["original_state_sha256"],
        aggregation_recovery_admission_sha256=sha256_file(recovery / "ADMISSION.json"))
    if done:
        state["recovery_completion" if phase == "DONE" else "recovery_hard_stop"] = done
        if phase == "HARD_STOP":
            state["latest_hard_stop"] = done
    payload = (json.dumps(state, indent=2) + "\n").encode()
    Heartbeat._replace_operational(archive / "00_CONTROL/STATE.json", payload)
    Heartbeat._replace_operational(recovery / "STATE.json", payload)
    Heartbeat._replace_operational(archive / "00_CONTROL/PROGRESS.txt",
        (f"phase={phase} status={state['status']} native=6468/6468 evaluator_terminal_slots=12936/12936 archived_batches=279/279\n"
         "native/evaluator reruns=0; original hard stop and state preserved under AGGREGATE_RECOVERY.\n").encode())


def reports(roots, repair_commit):
    # Initialize matplotlib before denying subprocess creation (font discovery
    # may use fc-list); this initialization does not read any scientific input.
    from . import figures, reporting
    code, archive = safe(roots["code_root"]), safe(roots["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3"
    recovery = archive / "00_CONTROL/AGGREGATE_RECOVERY"
    if (recovery / "REPORT_HARD_STOP.json").exists():
        raise RuntimeError("HARD_STOP_V3R_PERSISTED_REPORT_STOP_NO_AUTOMATIC_RETRY")
    admission = read_json(recovery / "ADMISSION.json")
    if admission.get("status") != "PASS_AGGREGATION_RECOVERY_ADMISSION" or admission.get("repair_commit") != repair_commit:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_ADMISSION_REQUIRED")
    pins = Pins()
    with aggregation_guard(roots["raw_root"], code) as guard:
        for path, digest in admission["input_sha256"].items():
            if path == str(archive / "00_CONTROL/STATE.json"):
                pins.check(recovery / "ORIGINAL_STATE.json", digest)
            else:
                pins.check(path, digest)
        status = read_json(archive / "STATUS.json")
        pins.check(archive / "FINAL_RUN_RECORDS.json", status["final_run_records_sha256"])
        evaluations = pins.json(archive / "FINAL_EVALUATION_RECORDS.json", status["final_evaluation_records_sha256"])
        f04_gate(evaluations)
        del evaluations
        operational_state(archive, admission, "AGGREGATE")
        contract = yaml.safe_load((code / "configs/paper_rebuild/v3/PROTOCOL_V3_CONTRACT.yaml").read_text())
        index_pin = contract["report_source_index"]
        index = pins.json(code / index_pin["path"], index_pin["sha256"])
        aggregate_path = archive / "07_AGGREGATE/AGGREGATE_MANIFEST.json"
        if aggregate_path.exists():
            aggregate = read_json(aggregate_path)
            if aggregate.get("status") != "COMPLETE_V3_AGGREGATES" or aggregate.get("code_freeze") != SCIENCE_FREEZE:
                raise RuntimeError("HARD_STOP_V3R_EXISTING_AGGREGATE_INVALID")
            for name, digest in aggregate["files_sha256"].items():
                pins.check(aggregate_path.parent / name, digest)
        else:
            with report_output_io(archive):
                aggregate = reporting.aggregate(archive, index, roots=roots, code_freeze=SCIENCE_FREEZE)
        with (archive / "07_AGGREGATE/MAIN_TABLE_V3.csv").open(newline="") as stream:
            main_table_f04_gate(list(csv.DictReader(stream)), admission["f04_t5ar_identity"]["actual_full_precision"])
        report_appendix(archive, index, roots, repair_commit)
        render_path = archive / "08_FIGURES/RENDER_MANIFEST.json"
        if render_path.exists():
            render = read_json(render_path)
        else:
            with report_output_io(archive):
                writer = figures.write_json
                def stop_failed_figure(path, entry):
                    writer(path, entry)
                    if Path(path).name == "FIGURE_MANIFEST.json" and entry.get("status") != "RENDERED":
                        raise RuntimeError("HARD_STOP_V3R_FIGURE_QA: " + entry.get("figure_id", "UNKNOWN") + ": " + entry.get("reason", ""))
                figures.write_json = stop_failed_figure
                try:
                    render = figures.render(archive, roots=roots, code_freeze=SCIENCE_FREEZE)
                finally:
                    figures.write_json = writer
        verify_render(archive, render)
        done = dict(status="DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA", science_freeze=SCIENCE_FREEZE,
            aggregation_repair_commit=repair_commit, native_terminal_count=6468, evaluator_terminal_count=12936,
            native_calls_in_recovery=0, evaluator_calls_in_recovery=0, completed_batches=279,
            aggregate_manifest_sha256=sha256_file(aggregate_path), render_manifest_sha256=sha256_file(render_path),
            full_ablation_failure_appendix_sha256=sha256_file(archive / "07C_FAILURE_FAMILY_CONFIG/MANIFEST.json"),
            original_hard_stop_preserved=True, visual_review_status="PENDING_ACTUAL_RASTER_REVIEW",
            package_status="PENDING", access_guard=guard)
        persist(archive / "00_CONTROL/DONE.json", done)
        persist(archive / "00_CONTROL/SUMMARY.json", done)
        persist_bytes(archive / "00_CONTROL/SUMMARY.txt", ("DONE: 6468 native terminals, 12936 evaluator terminal slots, 279 archived batches; aggregation and ten figure groups passed machine QA.\nNo native/evaluator reruns. Original HARD_STOP/STATE preserved. Actual visual review and handoff pending.\n" + json.dumps(done, indent=2) + "\n").encode())
        operational_state(archive, admission, "DONE", done)
        return done


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("records", "reports", "package"), required=True)
    parser.add_argument("--local-config", type=Path, required=True)
    parser.add_argument("--repair-commit", required=True)
    parser.add_argument("--audit-sha256")
    args = parser.parse_args(argv)
    roots = yaml.safe_load(safe(args.local_config).read_text())["paths"]
    scratch = safe(roots["protocol_v3_scratch"]) / "AGGREGATE_RECOVERY_CACHE"
    for key, sub in (("MPLCONFIGDIR", "matplotlib"), ("XDG_CACHE_HOME", "xdg"), ("TMPDIR", "tmp")):
        (scratch / sub).mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(scratch / sub)
    os.environ["MPLBACKEND"] = "Agg"
    if args.phase == "records":
        if not args.audit_sha256:
            parser.error("--audit-sha256 is required for records")
        result = recovery_records(roots, args.repair_commit, args.audit_sha256)
    elif args.phase == "reports":
        try:
            result = reports(roots, args.repair_commit)
        except Exception as exc:
            archive = safe(roots["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3"
            stop_path = archive / "00_CONTROL/AGGREGATE_RECOVERY/REPORT_HARD_STOP.json"
            if not stop_path.exists():
                persist(stop_path, dict(status="HARD_STOP", error=str(exc), repair_commit=args.repair_commit,
                    native_calls=0, evaluator_calls=0, automatic_retry=False))
            admission_path = stop_path.parent / "ADMISSION.json"
            if admission_path.exists():
                operational_state(archive, read_json(admission_path), "HARD_STOP", read_json(stop_path))
            raise
    else:
        from .recovery_packaging import package
        archive = safe(roots["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3"
        result = package(roots, safe(roots["code_root"]), code_freeze=SCIENCE_FREEZE,
            repair_commit=args.repair_commit, gate_path=archive / "FINAL_IDENTITY_GATES.json",
            audit_path=archive / "00_CONTROL/AGGREGATE_RECOVERY/OPENAT_AUDIT_SUMMARY.json")
    print(json.dumps({k: v for k, v in result.items() if k not in ("input_sha256", "members")}, indent=2))
    return 0
