"""V3-01-R exact-ledger purge. Planning never hashes candidate payloads.

Only registered completed stages with pinned successful handoff-validation records
can contribute candidates. A separate, preregistered verifier must pass after
quarantine. Every mutation has an fsynced intent and completion checkpoint.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from ..storage_purge import _parent_fd, _stat, _exists, _regular_single
from ..storage_purge_drvfs import _plain_rename
from ..clean6_canonical_v2.io_recovery import _metadata_bytes

MIN_BYTES = 1_000_000
ALLOWED_STAGES = {
    "CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2", "CLEAN6_ADDENDUM_FAMILIES_A1_A2",
    "CLEAN6_SENSOR_MODEL_V21", "CLEAN7_HEXT_EXTERNAL_SEQUENCES",
    "CLEAN7_T5A_HEADING_SENSITIVITY", "CLEAN7_T5BC_V3_CANDIDATE_PILOT",
}
FIELDS = ("path", "relative_path", "size_bytes", "mtime_ns", "device", "inode",
          "nlink", "stage", "existing_sha256", "evidence_path", "evidence_sha256",
          "basis", "classification", "row_type")
KEEP_SUFFIXES = {".json", ".jsonl", ".yaml", ".yml", ".md", ".png", ".pdf", ".svg"}


def fail(message):
    raise RuntimeError("HARD_STOP_V3R_PURGE: " + message)


def safe(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        fail("absolute, non-traversing path required: " + str(path))
    for component in (path, *path.parents):
        if component.is_symlink():
            fail("symlink forbidden: " + str(component))
    return path


def within(path, root):
    return path == root or root in path.parents


def digest(path):
    """Metadata/proof files only; never called on a candidate by this module."""
    path = safe(path)
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    path = safe(path)
    data = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()
    _metadata_bytes(path, data, append=False)


class _CsvSink:
    """Bounded metadata buffers with the existing fixed-offset exFAT retry writer."""
    def __init__(self, path):
        self.path = safe(path)
        self.buffer = io.StringIO(newline="")
        _metadata_bytes(self.path, b"", append=False)

    def write(self, text):
        count = self.buffer.write(text)
        if self.buffer.tell() >= 256 * 1024: self.flush()
        return count

    def flush(self):
        data = self.buffer.getvalue().encode("utf-8")
        if data:
            _metadata_bytes(self.path, data, append=True)
            self.buffer.seek(0); self.buffer.truncate()

    def close(self):
        self.flush(); self.buffer.close()


def read_json(path):
    return json.loads(safe(path).read_text(encoding="utf-8"))


def _assert_checks(document, checks, label):
    if not isinstance(checks, dict) or not checks:
        fail("explicit successful-record checks required: " + label)
    for key, expected in checks.items():
        actual = document
        for component in key.split("."):
            if not isinstance(actual, dict) or component not in actual:
                fail("missing record check " + label + ": " + key)
            actual = actual[component]
        if type(actual) is not type(expected) or actual != expected:
            fail("record check mismatch " + label + ": " + key)


def _pin(path, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected)) or digest(path) != expected:
        fail("record pin mismatch: " + str(path))


def validate_policy(policy, protection, *, verify_records=True):
    stages = safe(policy["stages_root"])
    if stages.name != "stages" or stages.parent.name != "clean_rebuild_202607":
        fail("stages root identity")
    quarantine = safe(policy["quarantine_root"])
    if quarantine != stages.parent.parent / "_QUARANTINE_20260919":
        fail("quarantine root identity")
    output = safe(policy["output_root"])
    if not within(output, stages / "CLEAN8_PROTOCOL_V3" / "V3R_PURGE"):
        fail("audit output root identity")
    argv = policy.get("verifier_command")
    if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
        fail("registered verifier argv required")
    if sum(v.count("{receipt}") for v in argv) != 1:
        fail("verifier argv must contain exactly one {receipt}")
    if protection.get("references_complete") is not True:
        fail("complete DATA_PATHS/contract protection index required")
    if not isinstance(protection.get("verification_pins"), list) or not protection["verification_pins"]:
        fail("nonempty P4 verification pins required")
    for key in ("protected_paths", "protected_root_objects"):
        for path in protection.get(key, []):
            safe(path)
    if verify_records:
        for pin in protection.get("reference_sources", []):
            _pin(pin["path"], pin["sha256"])
    roots = []
    for entry in policy["stages"]:
        root = safe(entry["path"])
        if not within(root, stages) or root == stages or root.relative_to(stages).parts[0] not in ALLOWED_STAGES:
            fail("stage outside bounded allowlist: " + str(root))
        if any(within(root, old) or within(old, root) for old in roots):
            fail("overlapping stage registrations")
        roots.append(root)
        for prefix in ("completion", "handoff_validation"):
            path = safe(entry[prefix + "_record"])
            if verify_records:
                _pin(path, entry[prefix + "_sha256"])
                checks = entry.get("completion_checks" if prefix == "completion" else "handoff_checks")
                _assert_checks(read_json(path), checks, str(path))
        for relative in entry["bulk_dirs"]:
            part = Path(relative)
            if part.is_absolute() or ".." in part.parts or part == Path("."):
                fail("bulk directory must be an exact stage-relative subdirectory")
            safe(root / part)
    return stages, quarantine, output


def _compile_protection(protection):
    protection["_trees"] = {str(Path(p)) for p in protection.get("protected_paths", [])}
    protection["_trees"].update(str(Path(pin["path"])) for pin in protection.get("verification_pins", []))
    protection["_roots"] = set(protection.get("protected_root_objects", []))


def _protection_reason(path, stages, protection):
    if str(path) in protection.get("_roots", protection.get("protected_root_objects", [])):
        return "PROTECTED_ROOT_OBJECT"
    trees = protection.get("_trees")
    if trees is None: trees = set(protection.get("protected_paths", []))
    if any(str(parent) in trees for parent in (path, *path.parents)):
        return "CONTRACT_OR_DATA_PATHS_REFERENCE"
    parts = path.relative_to(stages).parts
    for part in parts[:-1]:
        upper = part.upper()
        if (re.match(r"^0[0-2](?:_|$)", upper) or
                any(token in upper for token in ("PROVIDER", "INPUT", "RETAINED_RUNS", "HANDOFF", "RAW",
                                                 "CONFIG", "FROZEN", "BINARY", "EVALUATOR", "HASH_LOCK"))):
            return "INPUT_PROVIDER_RETAINED_OR_HANDOFF_DIRECTORY"
    upper = path.name.upper()
    if path.suffix.lower() in KEEP_SUFFIXES or any(token in upper for token in (
            "LEDGER", "AGGREGATE", "SUMMARY", "MANIFEST", "HASH", "SEAL", "CHECKSUM", "SHA256")):
        return "PERMANENT_RECORD_OR_FIGURE"
    return None


def _directory_protection_reason(path, stages, protection):
    # A fictitious member tests directory-tree protection, including the final
    # directory component. Root-object aliases intentionally do not prune trees.
    return _protection_reason(path / "__P2_DIRECTORY_MEMBER__", stages, protection)


def _bulk_kind(path):
    name = path.name.lower()
    if path.suffix.lower() == ".nav" or "std" in name or name.startswith("nav_10hz"):
        return "NATIVE_NAV_STD"
    if name.startswith("strace") or path.suffix.lower() == ".strace":
        return "PER_RUN_STRACE"
    if "stdout" in name or "stderr" in name:
        return "PER_RUN_STDOUT_STDERR"
    if path.suffix.lower() == ".csv" and any(token in name for token in (
            "diagnostic", "innovation", "residual", "gating", "factor", "nis", "nav_error", "errors")):
        return "PER_RUN_DIAGNOSTIC_CSV"
    return None


def _seal_evidence(directory, names):
    """Accept exact relative members in local OUTPUT_SEAL only, with old hashes."""
    if "OUTPUT_SEAL.json" not in names:
        return {}
    seal = Path(directory) / "OUTPUT_SEAL.json"
    if seal.is_symlink():
        return {}
    try:
        document = read_json(seal)
    except (json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(document, dict): return {}
    hashes = document.get("files", {})
    if not isinstance(hashes, dict):
        return {}
    seal_hash = digest(seal)
    result = {}
    for name, value in hashes.items():
        part = Path(name)
        if part.is_absolute() or ".." in part.parts:
            continue
        if isinstance(value, dict):
            value = value.get("sha256")
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            result[str(Path(directory) / part)] = (value, str(seal), seal_hash)
    return result


def _additional_evidence(policy):
    result = {}
    for entry in policy.get("additional_evidence", []):
        path, record = safe(entry["path"]), safe(entry["record_path"])
        _pin(record, entry["record_sha256"])
        # Exact string token, not a substring match to a neighbouring file.
        document = read_json(record)
        tokens = set()
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    tokens.add(str(key)); visit(child)
            elif isinstance(value, list):
                for child in value: visit(child)
            elif isinstance(value, str): tokens.add(value)
        visit(document)
        inherited = entry.get("existing_sha256", "")
        if str(path) not in tokens and (not inherited or inherited not in tokens):
            fail("additional evidence lacks exact path or inherited hash: " + str(path))
        if inherited and not re.fullmatch(r"[0-9a-f]{64}", inherited):
            fail("invalid inherited hash")
        result[str(path)] = (inherited, str(record), entry["record_sha256"])
    return result


def plan(policy_path, protection_path):
    policy, protection = read_json(policy_path), read_json(protection_path)
    stages, quarantine, output = validate_policy(policy, protection)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ("PLAN.json", "PURGE_LEDGER.csv", "SKIPPED.csv")):
        fail("existing plan must not be overwritten")
    write_json(output / "POLICY.json", policy)
    write_json(output / "PROTECTION_INDEX.json", protection)
    _compile_protection(protection)
    evidence = _additional_evidence(policy)
    registered_roots = tuple(Path(entry["path"]) for entry in policy["stages"])
    bulk_roots = tuple(Path(entry["path"]) / relative
                       for entry in policy["stages"] for relative in entry["bulk_dirs"])
    counts, reasons, by_stage = Counter(), Counter(), defaultdict(Counter)
    handles = {name: _CsvSink(output / name)
               for name in ("INVENTORY.csv", "PURGE_LEDGER.csv", "SKIPPED.csv")}
    writers = {name: csv.DictWriter(stream, fieldnames=FIELDS) for name, stream in handles.items()}
    for writer in writers.values(): writer.writeheader()
    try:
        for directory, dirs, names in os.walk(stages, followlinks=False):
            parent = Path(directory)
            if within(parent, output):
                dirs[:] = []
                continue
            links, excluded, descend = [], [], []
            for name in sorted(dirs):
                child = parent / name
                if child.is_symlink(): links.append(name)
                elif not any(within(child, root) or within(root, child) for root in registered_roots):
                    excluded.append((child, "STAGE_NOT_REGISTERED_COMPLETED_WITH_VERIFIED_HANDOFF"))
                else:
                    protected = _directory_protection_reason(child, stages, protection)
                    if protected:
                        excluded.append((child, protected))
                    elif any(within(child, root) or within(root, child) for root in bulk_roots):
                        descend.append(name)
                    else:
                        excluded.append((child, "OUTSIDE_REGISTERED_PER_CASE_OUTPUT_DIRECTORY"))
            dirs[:] = descend
            for path, reason in excluded:
                info = path.lstat()
                relative = path.relative_to(stages).as_posix()
                stage = relative.split("/")[0]
                row = dict(path=str(path), relative_path=relative, size_bytes="UNAVAILABLE_NOT_ENUMERATED",
                           mtime_ns=info.st_mtime_ns, device=info.st_dev, inode=info.st_ino,
                           nlink=info.st_nlink, stage=stage, existing_sha256="",
                           evidence_path="", evidence_sha256="", basis=reason, classification="SKIPPED",
                           row_type="EXCLUDED_DIRECTORY_UNENUMERATED")
                writers["INVENTORY.csv"].writerow(row)
                writers["SKIPPED.csv"].writerow(row)
                counts["SKIPPED"] += 1
                counts["EXCLUDED_DIRECTORIES"] += 1
                by_stage[stage]["SKIPPED"] += 1
                by_stage[stage]["EXCLUDED_DIRECTORIES"] += 1
                reasons[reason] += 1
            if any(within(parent, Path(s["path"])) for s in policy["stages"]):
                evidence.update(_seal_evidence(parent, names))
            for name in sorted(names + links):
                path = parent / name
                info = path.lstat()
                relative = path.relative_to(stages).as_posix()
                stage = relative.split("/")[0]
                row = dict(path=str(path), relative_path=relative, size_bytes=info.st_size,
                           mtime_ns=info.st_mtime_ns, device=info.st_dev, inode=info.st_ino,
                           nlink=info.st_nlink, stage=stage, existing_sha256="",
                           evidence_path="", evidence_sha256="", basis="", classification="SKIPPED",
                           row_type="REGULAR_FILE" if stat.S_ISREG(info.st_mode) else "SYMLINK_OR_SPECIAL")
                reason = None
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    reason = "SYMLINK_SPECIAL_OR_MULTILINK"
                if reason is None: reason = _protection_reason(path, stages, protection)
                if reason is None and info.st_size < MIN_BYTES: reason = "SMALLER_THAN_1_MB"
                entry = next((s for s in policy["stages"] if within(path, Path(s["path"]))), None)
                if reason is None and entry is None: reason = "STAGE_NOT_REGISTERED_COMPLETED_WITH_VERIFIED_HANDOFF"
                if reason is None and not any(within(path, Path(entry["path"]) / d) for d in entry["bulk_dirs"]):
                    reason = "OUTSIDE_REGISTERED_PER_CASE_OUTPUT_DIRECTORY"
                kind = _bulk_kind(path)
                if reason is None and kind is None: reason = "TYPE_NOT_REGISTERED_PER_CASE_BULK"
                proof = evidence.get(str(path))
                if reason is None and proof is None: reason = "NO_EXISTING_EXACT_PATH_OR_HASH_EVIDENCE"
                if reason is None:
                    row.update(existing_sha256=proof[0], evidence_path=proof[1], evidence_sha256=proof[2],
                               basis="P1_P2_P3_PASS:" + kind, classification="CANDIDATE")
                else: row["basis"] = reason
                writers["INVENTORY.csv"].writerow(row)
                writers["PURGE_LEDGER.csv" if reason is None else "SKIPPED.csv"].writerow(row)
                counts[row["classification"]] += 1
                counts[row["classification"] + "_bytes"] += info.st_size
                by_stage[stage][row["classification"]] += 1
                by_stage[stage][row["classification"] + "_bytes"] += info.st_size
                if reason:
                    reasons[reason] += 1
                    kind_key = "SKIPPED_FILES" if stat.S_ISREG(info.st_mode) else "SKIPPED_OTHER_OBJECTS"
                    counts[kind_key] += 1
                    by_stage[stage][kind_key] += 1
    finally:
        for stream in handles.values():
            stream.close()
    summary = {"status": "PLANNED", "counts": dict(counts), "by_stage": dict(by_stage),
               "skipped_reasons": dict(reasons), "candidate_payload_hash_reads": 0,
               "skipped_files": counts["SKIPPED_FILES"],
               "skipped_other_objects": counts["SKIPPED_OTHER_OBJECTS"],
               "excluded_directories": counts["EXCLUDED_DIRECTORIES"],
               "excluded_directory_bytes": None,
               "excluded_directory_bytes_status": "UNAVAILABLE_NOT_ENUMERATED",
               "inventory_scope": "REGISTERED_BULK_DIRS_WITH_PERMANENTLY_PROTECTED_SUBTREES_EXCLUDED",
               "byte_count_scope": "ENUMERATED_OBJECTS_ONLY_EXCLUDED_SUBTREE_BYTES_UNAVAILABLE",
               "skipped_reasons_unit": "ENUMERATED_SKIPPED_OBJECT_OR_EXCLUDED_DIRECTORY_ROWS",
               "protected_reference_sources": protection.get("reference_sources", []),
               "pins": {name: digest(output / name) for name in (*handles, "POLICY.json", "PROTECTION_INDEX.json")}}
    write_json(output / "PLAN.json", summary)
    return summary


class Purge:
    def __init__(self, plan_dir):
        self.output = safe(plan_dir)
        self.summary = read_json(self.output / "PLAN.json")
        for name, expected in self.summary["pins"].items(): _pin(self.output / name, expected)
        self.policy = read_json(self.output / "POLICY.json")
        self.protection = read_json(self.output / "PROTECTION_INDEX.json")
        self.stages, self.quarantine, output = validate_policy(self.policy, self.protection, verify_records=False)
        _compile_protection(self.protection)
        if output != self.output: fail("plan-directory binding")
        with (self.output / "PURGE_LEDGER.csv").open(newline="", encoding="utf-8") as stream:
            self.rows = list(csv.DictReader(stream))
        if len({row["path"] for row in self.rows}) != len(self.rows): fail("duplicate ledger paths")
        for row in self.rows:
            path = safe(row["path"])
            if not within(path, self.stages) or path == self.stages:
                fail("ledger path escaped stages")
            if path.relative_to(self.stages).as_posix() != row["relative_path"]:
                fail("ledger relative-path mismatch")
            if row["classification"] != "CANDIDATE" or _protection_reason(path, self.stages, self.protection):
                fail("protected ledger path")
        self.journal = self.output / "OPERATIONS.jsonl"

    @contextmanager
    def lock(self):
        with (self.output / "OPERATION.lock").open("a+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def events(self):
        if not self.journal.exists(): return []
        try: return [json.loads(line) for line in self.journal.read_text().splitlines()]
        except (ValueError, UnicodeError): fail("incomplete journal; preserve for explicit recovery")

    def event(self, action, **data):
        value = {"utc": datetime.now(timezone.utc).isoformat(), "action": action, **data}
        _metadata_bytes(safe(self.journal), (json.dumps(value, sort_keys=True) + "\n").encode(), append=True)

    def destination(self, row):
        return safe(self.quarantine / row["relative_path"])

    def check_size(self, path, row):
        value = _stat(path); _regular_single(value, path)
        if value.st_size != int(row["size_bytes"]): fail("ledger size changed: " + str(path))
        return value

    def check_source(self, row):
        value = self.check_size(safe(row["path"]), row)
        for key, actual in (("mtime_ns", value.st_mtime_ns), ("device", value.st_dev),
                            ("inode", value.st_ino), ("nlink", value.st_nlink)):
            if int(row[key]) != actual: fail("source metadata changed: " + row["path"])
        return value

    def _rollback(self, reason):
        events = self.events()
        if any(e["action"].startswith("DELETE_") for e in events):
            fail("deletion has begun; rollback cannot fabricate deleted files")
        moved = {e.get("path") for e in events if e["action"] in ("MOVE_INTENT", "MOVE_DONE")}
        self.event("ROLLBACK_BEGIN", reason=reason)
        for row in reversed(self.rows):
            source, target = safe(row["path"]), self.destination(row)
            if _exists(target):
                if row["path"] not in moved: fail("unregistered quarantine member")
                if _exists(source): fail("rollback collision; no overwrite: " + str(source))
                value = self.check_size(target, row)
                self.event("ROLLBACK_INTENT", path=str(source))
                _plain_rename(target, source, value)
                self.check_size(source, row)
                self.event("ROLLBACK_DONE", path=str(source))
            elif not _exists(source): fail("source and quarantine both absent during rollback")
        self.event("ROLLED_BACK", reason=reason)
        return {"status": "HARD_STOP_ROLLED_BACK", "reason": reason}

    def rollback(self):
        with self.lock(): return self._rollback("explicit recovery")

    def quarantine_files(self):
        with self.lock():
            events = self.events()
            if any(e["action"] in ("ROLLBACK_BEGIN", "ROLLED_BACK") for e in events):
                fail("rollback terminal; no automatic requarantine")
            if any(e["action"] == "QUARANTINE_COMPLETE" for e in events):
                return {"status": "QUARANTINE_COMPLETE", "resumed": True}
            if not any(e["action"] == "FREE_SPACE_BEFORE" for e in events):
                self.event("FREE_SPACE_BEFORE", df=subprocess.check_output(
                    ["df", "-B1", str(self.stages)], text=True))
            intents = {e.get("path") for e in events if e["action"] == "MOVE_INTENT"}
            try:
                validate_policy(self.policy, self.protection)
                proof_pins = {(r["evidence_path"], r["evidence_sha256"]) for r in self.rows}
                for path, expected in proof_pins: _pin(path, expected)
                for row in self.rows:
                    source, target = safe(row["path"]), self.destination(row)
                    if not _exists(source) and _exists(target) and str(source) in intents:
                        self.check_size(target, row)
                        self.event("MOVE_DONE", path=str(source), recovered=True)
                        continue
                    if _exists(target): fail("quarantine destination collision: " + str(target))
                    info = self.check_source(row)
                    self.event("MOVE_INTENT", path=str(source), size_bytes=info.st_size)
                    _plain_rename(source, target, info)
                    self.check_size(target, row)
                    self.event("MOVE_DONE", path=str(source))
                self.event("QUARANTINE_COMPLETE", files=len(self.rows),
                           bytes=sum(int(r["size_bytes"]) for r in self.rows))
            except Exception as exc:
                self._rollback(str(exc))
                raise
            return {"status": "QUARANTINE_COMPLETE", "files": len(self.rows)}

    def _check_verifier_receipt(self, value):
        total = len(self.protection["verification_pins"])
        if (value.get("status") != "PASS" or value.get("verification_complete") is not True
                or type(value.get("failed")) is not int or value["failed"] != 0
                or type(value.get("total")) is not int or value["total"] != total
                or type(value.get("verified")) is not int or value["verified"] != total
                or value.get("index_sha256") != self.summary["pins"]["PROTECTION_INDEX.json"]):
            fail("P4 verifier requires complete PASS, failed=0, full count and frozen index binding")

    def _check_verified_record(self, path):
        value = read_json(path)
        if value.get("status") != "PASS" or value.get("ledger_sha256") != self.summary["pins"]["PURGE_LEDGER.csv"]:
            fail("verification ledger binding")
        receipt = safe(value["receipt_path"])
        if receipt.parent != self.output: fail("verification receipt escaped audit directory")
        _pin(receipt, value["receipt_sha256"])
        self._check_verifier_receipt(read_json(receipt))
        if not any(event["action"] == "VERIFY_EXIT" and event["returncode"] == 0
                   and event.get("receipt") == str(receipt) for event in self.events()):
            fail("verification exit checkpoint binding")
        return value

    def _verify(self):
        events = self.events()
        committed = [e for e in events if e["action"] == "VERIFIED"]
        if committed:
            record = safe(committed[-1]["record_path"])
            if record.parent != self.output: fail("verified record escaped audit directory")
            _pin(record, committed[-1]["record_sha256"])
            return self._check_verified_record(record)
        if any(e["action"].startswith("DELETE_") for e in events):
            fail("deletion without durable verification")
        try:
            validate_policy(self.policy, self.protection)
            pass_records = sorted(p for p in self.output.iterdir()
                                  if re.fullmatch(r"P4_VERIFIED(?:_\d{4})?\.json", p.name))
            interrupted_pass = False
            for record in pass_records:
                try: value = self._check_verified_record(record)
                except (json.JSONDecodeError, UnicodeError):
                    interrupted_pass = True
                    self.event("VERIFIED_RECORD_INCOMPLETE_PRESERVED", record_path=str(record))
                    continue
                # The record is durable and fully bound, but the controller was
                # interrupted before its final journal checkpoint.
                self.event("VERIFIED", record_path=str(record), record_sha256=digest(record), **value)
                return value
            intents = [e for e in events if e["action"] == "VERIFY_INTENT"]
            prior = intents[-1] if intents else None
            exits = [e for e in events if e["action"] == "VERIFY_EXIT" and prior
                     and e.get("receipt") == prior["receipt"]]
            if prior and exits and not interrupted_pass:
                receipt = safe(prior["receipt"])
                if receipt.parent != self.output: fail("prior verifier receipt escaped audit directory")
                if exits[-1]["returncode"] != 0: fail("registered verifier failed")
            else:
                # An interrupted verifier is unverified. Preserve its receipt at
                # its original immutable path and start a new numbered attempt.
                if prior: self.event("VERIFY_INTERRUPTED_PRESERVED", receipt=prior["receipt"])
                receipt = self.output / f"P4_VERIFIER_RECEIPT_{len(intents) + 1:04d}.json"
                if receipt.exists(): fail("unregistered existing verifier receipt")
                self.event("VERIFY_INTENT", receipt=str(receipt))
                argv = [part.replace("{receipt}", str(receipt)) for part in self.policy["verifier_command"]]
                env = dict(os.environ, V3R_PURGE_LEDGER_SHA256=self.summary["pins"]["PURGE_LEDGER.csv"])
                result = subprocess.run(argv, shell=False, env=env, check=False)
                self.event("VERIFY_EXIT", receipt=str(receipt), returncode=result.returncode)
                if result.returncode != 0: fail("registered verifier failed")
            value = read_json(receipt)
            self._check_verifier_receipt(value)
            result = {"status": "PASS", "ledger_sha256": self.summary["pins"]["PURGE_LEDGER.csv"],
                      "receipt_path": str(receipt), "receipt_sha256": digest(receipt)}
            pass_record = self.output / ("P4_VERIFIED.json" if not pass_records
                                        else f"P4_VERIFIED_{len(pass_records) + 1:04d}.json")
            write_json(pass_record, result)
            self.event("VERIFIED", record_path=str(pass_record), record_sha256=digest(pass_record), **result)
            return result
        except Exception as exc:
            self._rollback(str(exc))
            raise

    def verify_purge(self):
        with self.lock():
            events = self.events()
            if any(e["action"] in ("ROLLBACK_BEGIN", "ROLLED_BACK") for e in events):
                fail("rolled-back plan is terminal")
            if not any(e["action"] == "QUARANTINE_COMPLETE" for e in events):
                fail("complete quarantine required before P4")
            try:
                self._verify()
            except Exception as exc:
                actions = {event["action"] for event in self.events()}
                if "ROLLBACK_BEGIN" not in actions and "DELETE_INTENT" not in actions:
                    self._rollback(str(exc))
                raise
            delete_intents = {e.get("path") for e in self.events() if e["action"] == "DELETE_INTENT"}
            for row in self.rows:
                source, target = safe(row["path"]), self.destination(row)
                if _exists(source): fail("original path reappeared before purge")
                if not _exists(target):
                    if str(source) not in delete_intents: fail("quarantine member missing without delete intent")
                    continue
                info = self.check_size(target, row)
                self.event("DELETE_INTENT", path=str(source), size_bytes=info.st_size)
                with _parent_fd(target) as (fd, name):
                    current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    _regular_single(current, target)
                    if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                            info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns):
                        fail("quarantine member changed immediately before unlink")
                    os.unlink(name, dir_fd=fd); os.fsync(fd)
                self.event("DELETE_DONE", path=str(source))
            parents = {parent for row in self.rows for parent in self.destination(row).parents
                       if within(parent, self.quarantine)}
            for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
                if not parent.exists(): continue
                safe(parent)
                self.event("RMDIR_INTENT", path=str(parent))
                with _parent_fd(parent) as (fd, name): os.rmdir(name, dir_fd=fd); os.fsync(fd)
                self.event("RMDIR_DONE", path=str(parent))
            result = {"status": "PASS_LEDGERED_PURGE_COMPLETE", "files": len(self.rows),
                      "deleted_bytes": sum(int(r["size_bytes"]) for r in self.rows),
                      "df_after": subprocess.check_output(["df", "-B1", str(self.stages)], text=True),
                      "skipped_reasons": self.summary["skipped_reasons"], "by_stage": self.summary["by_stage"]}
            if not (self.output / "PURGE_RESULT.json").exists(): write_json(self.output / "PURGE_RESULT.json", result)
            self.event("PURGE_COMPLETE", files=result["files"], deleted_bytes=result["deleted_bytes"])
            return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("plan")
    command.add_argument("--policy", required=True)
    command.add_argument("--protection-index", required=True)
    for name in ("quarantine", "verify-purge", "rollback"):
        command = sub.add_parser(name); command.add_argument("--plan-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "plan": result = plan(args.policy, args.protection_index)
    else:
        runner = Purge(args.plan_dir)
        result = {"quarantine": runner.quarantine_files, "verify-purge": runner.verify_purge,
                  "rollback": runner.rollback}[args.command]()
    print(json.dumps(result, ensure_ascii=False, indent=2))
