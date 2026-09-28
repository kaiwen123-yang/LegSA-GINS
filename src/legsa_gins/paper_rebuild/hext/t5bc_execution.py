"""Sequential T5bc controller; identities gate every matrix launch and resume.

Accepts an already resolved, formally registered contract and caller-produced Git
freeze receipt. Does not select cases, calibrate, generate providers, run Git, or
open raw/trace data. Existing terminals are verified, never relaunched.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

from . import t5bc_runtime as rt
from . import t5bc_config_fidelity as fidelity
from . import t5bc_provider as provider
from ..clean6_canonical_v2 import storage


def _digest(value):
    return hashlib.sha256(rt._json(value).encode()).hexdigest()


def _source_files():
    """Actual imported source locations, not a second checkout named by a caller."""
    files = {Path(__file__).resolve(), Path(rt.__file__).resolve(), Path(fidelity.__file__).resolve(),
             Path(provider.__file__).resolve(), Path(storage.__file__).resolve()}
    root = Path(__file__).resolve().parents[4]
    for name, module in tuple(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if path.suffix == ".py" and (name.startswith("legsa_gins") or rt._within(path, root)):
            files.add(path)
    files.add(root / "src/legsa_gins/paper_rebuild/clean6_canonical_v2/resources.py")
    files.update((root / "scripts/paper_rebuild/clean5_evaluator_observer").rglob("*.py"))
    for module in (rt, fidelity, provider):
        for item in vars(module).values():
            code = getattr(item, "__code__", None)
            if code is not None and "legsa_gins/paper_rebuild/" in code.co_filename:
                files.add(Path(code.co_filename).resolve())
    return files


def _reference(path):
    path = rt._safe(path)
    return {"path": str(path), "sha256": rt.sha256_file(path)}


def _read(path):
    return json.loads(rt._safe(path).read_text(encoding="utf-8"))


def _write_or_verify(path, value):
    path = rt._safe(path)
    if path.exists():
        if rt._json(_read(path)) != rt._json(value):
            raise RuntimeError("HARD_STOP_T5BC_CONTROLLER_RECEIPT_CHANGED: " + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        rt._write(path, value)
    return _reference(path)


def _inventory(root):
    root = rt._safe(root)
    result = {}
    for path in sorted(root.rglob("*")):
        rt._safe(path)
        if path.is_file():
            result[path.relative_to(root).as_posix()] = {"sha256": rt.sha256_file(path), "size_bytes": path.stat().st_size}
    return result


def verify_terminal(root, filename):
    """Verify every sealed member and reject missing or extra output files."""
    root = rt._safe(root)
    path = root / filename
    if not path.is_file() or (root / "HARD_STOP.json").exists():
        raise RuntimeError("HARD_STOP_T5BC_INCOMPLETE_OR_HARD_STOP_SLOT: " + str(root))
    record = _read(path)
    if record.get("status") == "HARD_STOP":
        raise RuntimeError("HARD_STOP_T5BC_RECORDED_NATIVE_OR_EVALUATOR_FAILURE")
    files = record.get("file_hashes", {})
    if "OUTPUT_SEAL.json" not in files:
        raise RuntimeError("HARD_STOP_T5BC_TERMINAL_SEAL_MISSING")
    actual = _inventory(root)
    if set(actual) != set(files) | {filename}:
        raise RuntimeError("HARD_STOP_T5BC_TERMINAL_MEMBERS_CHANGED")
    for relative, digest in files.items():
        if actual[relative]["sha256"] != digest:
            raise RuntimeError("HARD_STOP_T5BC_TERMINAL_HASH_CHANGED: " + relative)
    seal = _read(root / "OUTPUT_SEAL.json")
    if seal.get("status") != "SEALED" or seal.get("files") != {k: v for k, v in files.items() if k != "OUTPUT_SEAL.json"}:
        raise RuntimeError("HARD_STOP_T5BC_TERMINAL_SEAL_CONTENT")
    descriptor = "native_summary" if filename == "T5BC_NATIVE_SUMMARY.json" else "evaluation_summary"
    return {**record, descriptor: _reference(path)}


class ArchivePending(OSError):
    def __init__(self, report):
        super().__init__("T5BC_ARCHIVE_IO_PENDING")
        self.report = report


def archive_tree_once(source, destination):
    """Copy absent members only; existing bytes must match, including on I/O resume."""
    source, destination = rt._safe(source), rt._safe(destination)
    before = _inventory(source)
    if not before:
        raise RuntimeError("HARD_STOP_T5BC_EMPTY_ARCHIVE_SOURCE")
    existing = _inventory(destination) if destination.exists() else {}
    if not set(existing) <= set(before) or any(value != before[name] for name,value in existing.items()):
        raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_BYTES_OR_MEMBER_SET")
    failures = []
    for relative in before:
        if relative in existing:
            continue
        incoming, target = source / relative, destination / relative
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with incoming.open("rb") as reader, target.open("xb") as writer:
                for chunk in iter(lambda: reader.read(4*1024*1024), b""):
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
        except OSError as error:
            if target.exists() and rt.sha256_file(target) != before[relative]["sha256"]:
                raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_BYTES_OR_MEMBER_SET") from error
            failures.append({"relative": relative, "error": str(error)})
    after, archived = _inventory(source), _inventory(destination) if destination.exists() else {}
    if before != after or not set(archived) <= set(before) or any(value != before[name] for name,value in archived.items()):
        raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_BYTES_OR_MEMBER_SET")
    report = {"status": "ARCHIVE_PENDING_IO" if failures else "ARCHIVE_VERIFIED",
        "source": str(source), "destination": str(destination), "files": before,
        "tree_sha256": _digest(before), "attempted_file_count": len(before),
        "failed_file_count": len(failures), "failures": failures}
    if failures:
        raise ArchivePending(report)
    if before != archived:
        raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_BYTES_OR_MEMBER_SET")
    return report


def archive_tree_bounded(source, destination, *, audit_root):
    """Each tree is one batch; >1% I/O failures hard-stop, hashes always hard-stop."""
    audit=rt._safe(audit_root)
    if rt._safe(destination).exists() and _inventory(source)==_inventory(destination):
        return archive_tree_once(source,destination)
    audit.mkdir(parents=True,exist_ok=True)
    history=sorted(audit.glob("BATCH_*.json"))
    previous=_read(history[-1]) if history else {}
    try:
        report=archive_tree_once(source,destination)
    except ArchivePending as error:
        report=error.report
    fraction=report["failed_file_count"]/report["attempted_file_count"]
    record={**report,"batch_failure_fraction":fraction,
        "aggregate_attempted_file_count":previous.get("aggregate_attempted_file_count",0)+report["attempted_file_count"],
        "aggregate_failed_file_count":previous.get("aggregate_failed_file_count",0)+report["failed_file_count"],
        "threshold_scope":"THIS_ARCHIVE_TREE_BATCH_NOT_CUMULATIVE_DILUTION","science_retry":False}
    rt._write(audit/f"BATCH_{len(history)+1:06d}.json",record)
    if fraction>.01:
        raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_IO_FAILURES_EXCEED_ONE_PERCENT")
    return report


def _archive_file_once(source, destination):
    source, destination = rt._safe(source), rt._safe(destination)
    expected = rt.sha256_file(source)
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, destination.open("xb") as writer:
            for chunk in iter(lambda: reader.read(4*1024*1024), b""):
                writer.write(chunk)
            writer.flush(); os.fsync(writer.fileno())
    if rt.sha256_file(source) != expected or rt.sha256_file(destination) != expected:
        raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_FILE_BYTES")


def _same_bytes(left, right):
    with rt._safe(left).open("rb") as a, rt._safe(right).open("rb") as b:
        while True:
            first, second = a.read(4*1024*1024), b.read(4*1024*1024)
            if first != second:
                return False
            if not first:
                return True


def _pure_gate(contract, contexts, evaluator, receipt):
    freeze = receipt.get("code_freeze", "")
    allowed, budgets = rt.validate_registration(contract, code_commit=freeze)
    contract_sha = rt.scientific_contract_sha256(contract)
    if (receipt.get("status") != "PASS_CODE_FREEZE_PUSHED" or receipt.get("head_commit") != freeze
            or receipt.get("remote_commit") != freeze or receipt.get("tracked_worktree_clean") is not True
            or receipt.get("scientific_contract_sha256") != contract_sha
            or receipt.get("resolved_contract_sha256") != _digest(contract)):
        raise PermissionError("T5BC_CALLER_GIT_FREEZE_RECEIPT_REJECTED")
    if set(contexts) != {"BY2", "BY2H", "BY2O"}:
        raise PermissionError("T5BC_EXACT_CONTEXT_SET_REQUIRED")
    control = contract["execution_control"]
    if set(control["identity_comparators"]) != set(allowed["identity_native"]):
        raise PermissionError("T5BC_EXACT_IDENTITY_COMPARATORS_REQUIRED")
    if len(control["frozen_figures"]) != 28 or any(not values for values in control["frozen_figures"].values()):
        raise PermissionError("T5BC_28_FROZEN_FIGURE_PIN_GROUPS_REQUIRED")
    if evaluator.get("sha256") != contract["frozen"]["evaluator_sha256"]:
        raise PermissionError("T5BC_REGISTERED_EVALUATOR_REQUIRED")
    return allowed, budgets, contract_sha, freeze


def _protected_pins(contract, contexts, evaluator, receipt):
    first = contexts["BY2"]
    code, clean = rt._safe(first.code_root), rt._safe(first.clean_root)
    for name, context in contexts.items():
        if context.sequence_id != name or rt._safe(context.code_root) != code or rt._safe(context.clean_root) != clean:
            raise PermissionError("T5BC_CONTEXT_ROOT_IDENTITY")
    source_pins = receipt["source_sha256"]
    for source in _source_files():
        if not rt._within(source, code) or source.relative_to(code).as_posix() not in source_pins:
            raise RuntimeError("HARD_STOP_T5BC_IMPORTED_SOURCE_NOT_IN_FREEZE_RECEIPT")
    refs = [contract["frozen"]["executable"], {key: contract["candidate"][key] for key in ("path", "sha256")}, evaluator]
    for relative, digest in source_pins.items():
        path = rt._safe(code / relative)
        if not rt._within(path, code):
            raise RuntimeError("HARD_STOP_T5BC_CODE_PIN_PATH")
        refs.append({"path": str(path), "sha256": digest})
    control = contract["execution_control"]
    refs += list(control["identity_comparators"].values()) + [control["render_manifest"]]
    refs += list(control["extra_frozen_pins"].values())
    calibration = control.get("calibration_pins", [])
    refs += calibration
    calibration_paths = {_safe_ref["path"] for _safe_ref in calibration}
    refs += [item for items in control["frozen_figures"].values() for item in items]
    for spec in contract["registered_runs"].values():
        refs.extend([spec["frozen_config"], spec["frozen_echo"], *spec["frozen_providers"].values()])
        if "frozen_echo_witness" in spec:
            refs.append(spec["frozen_echo_witness"]["config"])
        if spec["variant"] != "IDENTITY":
            refs.append(spec["r5_reference"])
    pins = {}
    for ref in refs:
        path = rt._safe(ref["path"])
        is_calibration = (str(path) in calibration_paths and
            rt._within(path, rt._safe(contract["scratch_root"])/"01_CALIBRATION")) if calibration else False
        if not (rt._within(path, code) or rt._within(path, clean) or is_calibration):
            raise RuntimeError("HARD_STOP_T5BC_PROTECTED_PIN_OUTSIDE_CODE_OR_CLEAN")
        if path in pins and pins[path] != ref["sha256"]:
            raise RuntimeError("HARD_STOP_T5BC_CONFLICTING_PROTECTED_PIN")
        pins[path] = ref["sha256"]
    return pins


def _execute(contract, *, contexts, evaluator, scratch_root, archive_root, code_freeze_receipt, identity_only):
    """Run/resume exactly the registered matrix after both byte identity gates.

    `code_freeze_receipt` is a caller-created verification of local HEAD, pushed
    remote HEAD, tracked-clean status, resolved contract hash and source hashes.
    This function never invokes Git. A persisted hard stop requires human action.

    Additional resolved contract fields under ``execution_control`` are:
    ``identity_comparators`` (two run_id -> path/sha256 refs), ``frozen_figures``
    (28 figure_id -> nonempty ref lists), ``render_manifest`` (one ref), and
    ``extra_frozen_pins`` (label -> ref). The frozen identity SHA map remains
    ``frozen.identity_nav_10hz_sha256`` keyed by BY2_F02/BY2_F04. Evaluator is a
    path/sha256 ref; contexts is the exact BY2/BY2H/BY2O runtime-context mapping.
    The caller's ``source_sha256`` must cover every path from ``_source_files``
    relative to the actual code root, plus any additional intended entrypoints.
    """
    allowed, budgets, contract_sha, freeze = _pure_gate(contract, contexts, evaluator, code_freeze_receipt)
    scratch, archive = rt._safe(scratch_root), rt._safe(archive_root)
    for spec in contract["registered_runs"].values():
        rt._registered(contexts[spec["sequence_id"]], contract, spec, scratch, freeze)
    if archive != rt._safe(contexts["BY2"].clean_root) / "stages" / rt.STAGE:
        raise ValueError("T5bc archive must be the exact new CLEAN7 stage")
    if not identity_only and not (scratch / "02_IDENTITY_GATE/IDENTITY_GATE.json").is_file():
        raise PermissionError("T5BC_BOTH_IDENTITIES_REQUIRED_BEFORE_MATRIX")
    state = scratch / "09_HANDOFF/EXECUTION"
    hard_stop = state / "CONTROLLER_HARD_STOP.json"
    if hard_stop.exists():
        raise RuntimeError("HARD_STOP_T5BC_AUTOMATIC_CONTINUATION_FORBIDDEN")
    state.mkdir(parents=True, exist_ok=True)
    with (state / "CONTROLLER.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if hard_stop.exists():
            raise RuntimeError("HARD_STOP_T5BC_AUTOMATIC_CONTINUATION_FORBIDDEN")
        try:
            pins = _protected_pins(contract, contexts, evaluator, code_freeze_receipt)
            stable_receipt = {key: value for key, value in code_freeze_receipt.items() if key != "resolved_contract_sha256"}
            _write_or_verify(state / "CODE_FREEZE_RECEIPT.json", stable_receipt)
            _write_or_verify(state / ("IDENTITY_RESOLVED_CONTRACT.json" if identity_only else "MATRIX_RESOLVED_CONTRACT.json"),
                {"resolved_contract_sha256": _digest(contract), "scientific_contract_sha256": contract_sha})
            def checkpoint(label):
                for path, digest in pins.items():
                    rt._pin({"path": str(path), "sha256": digest})
                return _write_or_verify(state / "CHECKPOINTS" / (label + ".json"),
                    {"status": "PASS", "code_freeze": freeze, "contract_sha256": contract_sha,
                     "pins": {str(path): digest for path, digest in sorted(pins.items())}})
            archives, native_results, evaluation_results = {}, {}, {}
            archive_pending, archive_attempted, archive_failed = {}, 0, 0
            def ledger_rows(kind):
                path = scratch / "LAUNCH_LEDGERS" / (kind + ".jsonl")
                rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
                if (len(rows) > budgets[kind] or len({row["run_id"] for row in rows}) != len(rows)
                        or any(row.get("run_id") not in allowed[kind] or row.get("contract_sha256") != contract_sha
                               or row.get("kind") != kind or row.get("budget") != budgets[kind] for row in rows)):
                    raise RuntimeError("HARD_STOP_T5BC_CONTROLLER_LEDGER_SCOPE")
                return rows
            for kind in budgets:
                ledger_rows(kind)
            def require_reservation(run_id, kind, root):
                rows = [row for row in ledger_rows(kind) if row["run_id"] == run_id]
                if len(rows) != 1 or _read(root / "LAUNCH_RESERVATION.json") != rows[0]:
                    raise RuntimeError("HARD_STOP_T5BC_TERMINAL_WITHOUT_MATCHING_RESERVATION")
            def archive_slot(relative, label):
                nonlocal archive_attempted, archive_failed
                value = archive_tree_bounded(scratch / relative, archive / relative, audit_root=scratch/"09_HANDOFF/ARCHIVE_IO")
                archive_attempted += value["attempted_file_count"]
                archive_failed += value["failed_file_count"]
                if value["status"] == "ARCHIVE_PENDING_IO":
                    archive_pending[label] = relative
                    _write_or_verify(state / "ARCHIVE_PENDING" / (label + ".json"), value)
                    return
                archives[label] = _write_or_verify(state / "ARCHIVE_RECEIPTS" / (label + ".json"), value)
                archive_pending.pop(label, None)
            def remember(record, filename, relative, label):
                verified = verify_terminal(scratch / relative, filename)
                descriptor = "native_summary" if filename == "T5BC_NATIVE_SUMMARY.json" else "evaluation_summary"
                if record is not None and rt._json(record) != rt._json(verified):
                    raise RuntimeError("HARD_STOP_T5BC_WRAPPER_RETURN_DIFFERS_FROM_TERMINAL")
                if verified["code_commit"] != freeze:
                    raise RuntimeError("HARD_STOP_T5BC_TERMINAL_CODE_FREEZE")
                _write_or_verify(state / "TERMINALS" / (label + ".json"),
                    {"contract_sha256": contract_sha, "code_freeze": freeze, "summary": verified[descriptor]})
                return verified
            def native(spec):
                relative = spec["output_relpath"]
                root = scratch / relative
                kind = "identity_native" if spec["variant"] == "IDENTITY" else "matrix_native"
                record = None
                if not root.exists():
                    print("T5bc native START " + spec["run_id"], flush=True)
                    if spec["variant"] == "IDENTITY" and not identity_only:
                        raise RuntimeError("HARD_STOP_T5BC_IDENTITY_SLOT_MISSING_NO_RETRY")
                    record = rt.run_native(contexts[spec["sequence_id"]], contract=contract, run_spec=spec,
                        output_root=root, scratch_root=scratch, code_commit=freeze,
                        launch_ledger=scratch / "LAUNCH_LEDGERS" / (kind + ".jsonl"))
                record = remember(record, "T5BC_NATIVE_SUMMARY.json", relative, "native__" + spec["run_id"])
                require_reservation(spec["run_id"], kind, root)
                if (record["contract_sha256"] != contract_sha or any(record[key] != spec[key] for key in rt.IDENTITY_KEYS)
                        or record["input_identities"]["binary"]["sha256"] !=
                        (contract["candidate"]["sha256"] if spec["variant"] in ("B3", "IDENTITY") else contract["frozen"]["executable"]["sha256"])):
                    raise RuntimeError("HARD_STOP_T5BC_NATIVE_SLOT_BINDING")
                if record.get("run_spec_sha256") != _digest(spec):
                    raise RuntimeError("HARD_STOP_T5BC_RESOLVED_RUN_SPEC_CHANGED")
                if record.get("trace_open_count") != 0:
                    raise RuntimeError("HARD_STOP_T5BC_NATIVE_TRACE_ACCOUNTING")
                if (any(type(record.get(key)) is not type(value) or record[key] != value
                        for key, value in rt.PROVENANCE_FLAGS.items())
                        or record.get("raw_source_hashes") != spec["raw_source_hashes"]):
                    raise RuntimeError("HARD_STOP_T5BC_NATIVE_PROVENANCE_BINDING")
                native_results[spec["run_id"]] = record
                print("T5bc native " + spec["run_id"] + " " + record["status"] + " reserved=" + str(len(ledger_rows(kind))) + "/" + str(budgets[kind]), flush=True)
                archive_slot(relative, "native__" + spec["run_id"])
                return record
            def identity(spec):
                record = native(spec)
                if (record["status"] != "COMPLETED" or record.get("effective_echo_gate", {}).get("passed") is not True
                        or record["effective_echo_gate"].get("legacy_static_field_count") != 211):
                    raise RuntimeError("HARD_STOP_T5BC_IDENTITY_NATIVE_OR_211_ECHO")
                comparison = contract["execution_control"]["identity_comparators"][spec["run_id"]]
                expected = contract["frozen"]["identity_nav_10hz_sha256"][spec["sequence_id"] + "_" + spec["configuration_id"]]
                if comparison["sha256"] != expected:
                    raise RuntimeError("HARD_STOP_T5BC_IDENTITY_COMPARATOR_REGISTRATION")
                rt._pin(comparison)
                relative = "02_IDENTITY_GATE/COMPARISONS/" + spec["run_id"]
                directory = scratch / relative
                product = directory / "NAV_10HZ.csv.gz"
                receipt_path = directory / "IDENTITY_COMPARISON.json"
                if not directory.exists():
                    directory.mkdir(parents=True, exist_ok=False)
                    storage.thin_nav(Path(record["nav_path"]), product)
                elif not receipt_path.is_file():
                    raise RuntimeError("HARD_STOP_T5BC_PARTIAL_IDENTITY_COMPARISON_NO_RETRY")
                product_ref = _reference(product)
                rt._pin({"path": record["nav_path"], "sha256": record["nav_sha256"]})
                if product_ref["sha256"] != expected or not _same_bytes(product, comparison["path"]):
                    raise RuntimeError("HARD_STOP_T5BC_SCALAR_OFF_NAV_10HZ_BYTE_IDENTITY")
                value = {"status": "PASS", "run_id": spec["run_id"], "code_freeze": freeze,
                         "contract_sha256": contract_sha, "candidate_sha256": contract["candidate"]["sha256"],
                         "native_summary": record["native_summary"], "native_nav_sha256": record["nav_sha256"],
                         "effective_echo_gate": record["effective_echo_gate"], "product": product_ref,
                         "comparator": comparison, "comparable_product": "NAV_10HZ.csv.gz",
                         "gzip_bytes_equal": True,
                         "thin_policy": "clean6_canonical_v2.storage.thin_nav; gzip filename empty, mtime0, level3"}
                comparison_ref = _write_or_verify(receipt_path, value)
                archive_slot(relative, "identity__" + spec["run_id"])
                return comparison_ref
            checkpoints = {"BY2_PRE": checkpoint("IDENTITY_PRE" if identity_only else "BY2_PRE")}
            identity_refs = {}
            for run_id in sorted(allowed["identity_native"]):
                identity_refs[run_id] = identity(contract["registered_runs"][run_id])
            gate_value = {"status": "PASS_BOTH_IDENTITIES", "code_freeze": freeze,
                          "contract_sha256": contract_sha, "candidate_sha256": contract["candidate"]["sha256"],
                          "identities": identity_refs}
            identity_gate = _write_or_verify(scratch / "02_IDENTITY_GATE/IDENTITY_GATE.json", gate_value)
            archive_slot("02_IDENTITY_GATE", "identity_gate_tree")
            def verify_identity_gate():
                rt._pin(identity_gate)
                if _read(identity_gate["path"]) != gate_value:
                    raise RuntimeError("HARD_STOP_T5BC_IDENTITY_GATE_BINDING")
                for reference in identity_refs.values():
                    rt._pin(reference)
                    value = _read(reference["path"])
                    for key in ("product", "comparator", "native_summary"):
                        rt._pin(value[key])
                    if value["candidate_sha256"] != contract["candidate"]["sha256"] or value["code_freeze"] != freeze:
                        raise RuntimeError("HARD_STOP_T5BC_IDENTITY_GATE_CANDIDATE_OR_FREEZE")
                rt._pin({key: contract["candidate"][key] for key in ("path", "sha256")})
            if identity_only:
                for label, relative in list(archive_pending.items()):
                    archive_slot(relative, label)
                verify_identity_gate()
                post = checkpoint("IDENTITY_POST")
                result = {"status": "PASS_BOTH_IDENTITIES", "code_freeze": freeze, "contract_sha256": contract_sha,
                    "identity_gate": identity_gate, "budget_reserved": {"identity_native": len(ledger_rows("identity_native")), "matrix_native": 0, "evaluator": 0},
                    "checkpoints": {**checkpoints, "BY2_POST": post}, "trace_open_count": 0, "evaluator_invocation_count": 0, "archive_pending": dict(archive_pending),
                    "native_terminals": {key: value["native_summary"] for key,value in native_results.items()}}
                result["summary"] = _write_or_verify(state / "IDENTITY_EXECUTION_SUMMARY.json", result)
                return result
            for sequence_id in ("BY2", "BY2H", "BY2O"):
                if sequence_id != "BY2":
                    checkpoints[sequence_id + "_PRE"] = checkpoint(sequence_id + "_PRE")
                for run_id in sorted(allowed["matrix_native"]):
                    spec = contract["registered_runs"][run_id]
                    if spec["sequence_id"] != sequence_id:
                        continue
                    verify_identity_gate()
                    record = native(spec)
                    for version in ("v3", "v2"):
                        eval_id = run_id + "__" + version
                        relative = "06_EVAL/" + version + "/" + run_id
                        root = scratch / relative
                        result = None
                        if not root.exists():
                            if record["status"] == "COMPLETED":
                                result = rt.evaluate_native(contexts[sequence_id], evaluator["path"], contract=contract,
                                    run_spec=spec, native_summary=record, version=version, output_root=root,
                                    scratch_root=scratch, code_commit=freeze,
                                    launch_ledger=scratch / "LAUNCH_LEDGERS/evaluator.jsonl")
                            else:
                                root.mkdir(parents=True, exist_ok=False)
                                status = "NOT_RUN_ALGORITHM_FAILURE" if record["status"].startswith("ALGORITHM_FAILURE_") else "NOT_RUN_NATIVE_UNAVAILABLE"
                                skipped = {"status": status, "run_id": eval_id, "code_commit": freeze,
                                    "native_summary": record["native_summary"], "evaluation_invoked": False,
                                    "contract_sha256": contract_sha, "row": {**{k: spec[k] for k in rt.IDENTITY_KEYS},
                                    "status": status, "evaluation_status": status,
                                    "failure_classification": record.get("failure_classification", record["status"]),
                                    "evaluator_contract": "evaluator_contract_" + version,
                                    "reason": record["status"], "metrics_admitted": False}}
                                provenance = {key: record[key] for key in (*rt.PROVENANCE_FLAGS, "code_commit", "config_hash", "raw_source_hashes",
                                    "provider_hashes", "data_mode", "synthetic_data_used", "semisynthetic_data_used",
                                    "controlled_degradation_applied", "original_native_config_data_roles")}
                                skipped.update(provenance)
                                skipped["row"].update(provenance)
                                result = rt._seal(root, skipped, filename="T5BC_EVALUATION_SUMMARY.json")
                        result = remember(result, "T5BC_EVALUATION_SUMMARY.json", relative, "eval__" + eval_id)
                        if result["evaluation_invoked"]:
                            require_reservation(eval_id, "evaluator", root)
                        if result["run_id"] != eval_id or result["native_summary"] != record["native_summary"]:
                            raise RuntimeError("HARD_STOP_T5BC_EVALUATION_SLOT_BINDING")
                        if result["evaluation_invoked"] and result.get("audit", {}).get("trace_open_count") != 1:
                            raise RuntimeError("HARD_STOP_T5BC_EVALUATOR_TRACE_ACCOUNTING")
                        evaluation_results[eval_id] = result
                        print("T5bc evaluator " + eval_id + " " + result["status"] + " reserved=" + str(len(ledger_rows("evaluator"))) + "/" + str(budgets["evaluator"]), flush=True)
                        archive_slot(relative, "eval__" + eval_id)
                checkpoints[sequence_id + "_POST"] = checkpoint(sequence_id + "_POST")
            verify_identity_gate()
            for label, relative in list(archive_pending.items()):
                archive_slot(relative, label)
            actual = {}
            for kind, maximum in budgets.items():
                rows = ledger_rows(kind)
                expected_ids = set(allowed[kind]) if kind != "evaluator" else {
                    key for key, value in evaluation_results.items() if value["evaluation_invoked"]}
                if {row["run_id"] for row in rows} != expected_ids:
                    raise RuntimeError("HARD_STOP_T5BC_TERMINAL_AND_RESERVATION_BUDGET_DISAGREE")
                actual[kind] = len(rows)
            result = {"status": "COMPLETE_REGISTERED_EXECUTION_ARCHIVE_PENDING" if archive_pending else "COMPLETE_REGISTERED_EXECUTION", "code_freeze": freeze,
                      "contract_sha256": contract_sha, "identity_gate": identity_gate,
                      "budget_reserved": actual, "budget_authorized": budgets,
                      "native_terminals": {key: value["native_summary"] for key, value in native_results.items()},
                      "evaluation_terminals": {key: value["evaluation_summary"] for key, value in evaluation_results.items()},
                      "checkpoints": checkpoints, "archives": archives, "archive_pending": dict(archive_pending),
                      "archive_attempted_file_count": archive_attempted, "archive_failed_file_count": archive_failed,
                      "archive_failure_fraction": archive_failed/archive_attempted if archive_attempted else 0.,
                      "parameter_search_count": 0, "retry_count": 0}
            result.update(trace_open_count_native=0,
                          trace_open_count_evaluator=sum(value["evaluation_invoked"] for value in evaluation_results.values()))
            modes, raw_hashes = {}, {}
            for record in native_results.values():
                modes[record["data_mode"]] = modes.get(record["data_mode"], 0) + 1
                for path, digest in record["raw_source_hashes"].items():
                    if path in raw_hashes and raw_hashes[path] != digest:
                        raise RuntimeError("HARD_STOP_T5BC_CONFLICTING_RAW_PROVENANCE")
                    raw_hashes[path] = digest
            result.update(rt.PROVENANCE_FLAGS)
            result.update(data_mode=next(iter(modes)) if len(modes) == 1 else "mixed_registered_frozen_data_modes",
                          native_data_mode_counts=modes,
                          synthetic_data_used=any(row["synthetic_data_used"] for row in native_results.values()),
                          semisynthetic_data_used=any(row["semisynthetic_data_used"] for row in native_results.values()),
                          raw_source_hashes=raw_hashes,
                          provider_hashes_by_run={key: row["provider_hashes"] for key, row in native_results.items()})
            final_ref = _write_or_verify(state / "FINAL_EXECUTION_SUMMARY.json", result)
            archive_tree_bounded(scratch / "LAUNCH_LEDGERS", archive / "LAUNCH_LEDGERS",audit_root=scratch/"09_HANDOFF/ARCHIVE_IO")
            state_archive = archive_tree_bounded(state, archive / "09_HANDOFF/EXECUTION",audit_root=scratch/"09_HANDOFF/ARCHIVE_IO")
            return {**result, "final_summary": final_ref, "controller_archive": state_archive}
        except Exception as error:
            if not hard_stop.exists():
                rt._write(hard_stop, {"status": "HARD_STOP", "error": str(error), "code_freeze": freeze,
                                     "contract_sha256": contract_sha, "automatic_continuation": False})
            raise


def execute_identities(contract, *, contexts, evaluator, scratch_root, archive_root, code_freeze_receipt):
    """After calibration/freeze, run exactly two scalar-off identities before providers exist.

    Complete planned matrix specs are required, including final generated paths;
    only generated sha256 values may be None. The scientific contract digest
    normalizes those three generated reference hashes and nothing else. No matrix
    or evaluation invocation is made by this function, including on resume.
    """
    return _execute(contract, contexts=contexts, evaluator=evaluator, scratch_root=scratch_root,
        archive_root=archive_root, code_freeze_receipt=code_freeze_receipt, identity_only=True)


def execute_registered(contract, *, contexts, evaluator, scratch_root, archive_root, code_freeze_receipt):
    """Run/resume 259 matrix slots only after the persisted two-identity gate.

    The caller fills generated provider hashes after identity using the registered
    final paths. Scientific changes invalidate the gate; complete resolved spec
    hashes bind every consumed matrix slot and evaluator. No identity is launched.
    """
    return _execute(contract, contexts=contexts, evaluator=evaluator, scratch_root=scratch_root,
        archive_root=archive_root, code_freeze_receipt=code_freeze_receipt, identity_only=False)


def finish_pending_archives(*, scratch_root, archive_root):
    """Copy-only recovery of recorded missing archive members; no solver/evaluator.

    Original pending reports and final scientific summary remain immutable. A
    new append-only ARCHIVE_RESOLVED receipt records completion of each tree.
    Existing mismatching destination bytes always hard-stop without overwrite.
    """
    scratch, archive = rt._safe(scratch_root), rt._safe(archive_root)
    if scratch.name != rt.STAGE or archive.name != rt.STAGE:
        raise ValueError("T5bc archive-only stage path mismatch")
    state = scratch / "09_HANDOFF/EXECUTION"
    resolved = {}
    pending_paths=sorted((state / "ARCHIVE_PENDING").glob("*.json"))
    pending_paths += sorted((scratch / "09_HANDOFF/ARCHIVE_IO").glob("BATCH_*.json"))
    for path in pending_paths:
        pending = _read(path)
        if pending.get("status") != "ARCHIVE_PENDING_IO":continue
        source, destination = rt._safe(pending["source"]), rt._safe(pending["destination"])
        if not rt._within(source, scratch) or destination != archive/source.relative_to(scratch):
            raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_RECOVERY_SCOPE")
        if _inventory(source) != pending["files"]:
            raise RuntimeError("HARD_STOP_T5BC_ARCHIVE_RECOVERY_SOURCE_CHANGED")
        receipt = archive_tree_once(source, destination)
        resolved[path.stem] = _write_or_verify(state / "ARCHIVE_RESOLVED" / path.name, receipt)
    return {"status": "ARCHIVE_RECOVERY_COMPLETE", "resolved": resolved,
            "native_invocation_count": 0, "evaluator_invocation_count": 0, "science_retry_count": 0}


def verify_identity_receipt(contract, *, scratch_root, code_commit):
    """Read-only identity admission for the provider phase; never launch a slot."""
    allowed, _ = rt.validate_registration(contract, code_commit=code_commit)
    root=rt._safe(scratch_root)
    path=root/'02_IDENTITY_GATE/IDENTITY_GATE.json'
    value=_read(path)
    if (value.get('status')!='PASS_BOTH_IDENTITIES' or value.get('code_freeze')!=code_commit
            or value.get('contract_sha256')!=rt.scientific_contract_sha256(contract)
            or value.get('candidate_sha256')!=contract['candidate']['sha256']
            or set(value.get('identities',{}))!=set(allowed['identity_native'])):
        raise RuntimeError('HARD_STOP_T5BC_IDENTITY_GATE_BINDING')
    for run_id, reference in value['identities'].items():
        rt._pin(reference); receipt=_read(reference['path'])
        spec=contract['registered_runs'][run_id]
        for key in ('native_summary','product','comparator'):rt._pin(receipt[key])
        native=verify_terminal(root/spec['output_relpath'],'T5BC_NATIVE_SUMMARY.json')
        if (native['native_summary']!=receipt['native_summary'] or native.get('run_spec_sha256')!=_digest(spec)
                or receipt.get('contract_sha256')!=value['contract_sha256']
                or receipt.get('candidate_sha256')!=value['candidate_sha256']
                or receipt.get('code_freeze')!=code_commit
                or native.get('effective_echo_gate',{}).get('legacy_static_field_count')!=211
                or native['effective_echo_gate'].get('passed') is not True
                or receipt.get('comparator')!=contract['execution_control']['identity_comparators'][run_id]
                or not _same_bytes(receipt['product']['path'],receipt['comparator']['path'])):
            raise RuntimeError('HARD_STOP_T5BC_IDENTITY_COMPARISON_BINDING')
    return _reference(path)
