"""Single-use DrvFS continuation of a frozen B ledger; no candidate payload reads.

Ordinary rename is the explicitly authorized filesystem strategy. Destination
absence is checked immediately before rename under the operation lock; no
renameat2, copy fallback, retry, rollback, or interrupted-attempt resume exists.
Content SHA-256 is inherited from B, not recomputed or represented as reverified.
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import xml.etree.ElementTree as ET

from . import storage_purge as base
from .storage_purge_dispatch import DispatchPermit, dispatch, seal_receipt


STRATEGY = "drvfs_plain_rename_b_sha256.v1"
GATES = {"preflight": ("IO_PROBE", "C1", "C2", "C3"),
         "quarantine": ("C4",), "c5": ("C5",), "purge": ("D",)}
RECEIPT_FILES = {"preflight": "GATE_PRE_MOVE.json", "quarantine": "GATE_QUARANTINE.json",
                 "c5": "C5_RECEIPT.json", "purge": "PURGE_RESULT.json"}
RECORD_CHECKS = {"decision_readability", "aggregate_readability", "three_sequence_CAL_readability"}
C5_NODES = (
    "tests/paper_rebuild/test_canonical541_derived_tables.py::test_real_attempt_reproduces_agents_7a2",
    "tests/paper_rebuild/test_clean5_sequence_contracts.py::test_contract_time_window_and_initialization_reproduce_c01b_report",
    "tests/paper_rebuild/test_clean5_sequence_contracts.py::test_contract_copies_exactly_22_locked_input_hashes_without_opening_raw",
    "tests/paper_rebuild/test_clean5_sequence_contracts.py::test_registered_occlusion_matches_traced_report_and_controls",
    "tests/paper_rebuild/test_clean5_outcome_scope.py",
)
CODE_FILES = (
    "src/legsa_gins/paper_rebuild/storage_purge.py",
    "src/legsa_gins/paper_rebuild/storage_purge_dispatch.py",
    "src/legsa_gins/paper_rebuild/storage_purge_drvfs.py",
    "scripts/paper_rebuild/storage_purge_drvfs.py",
    "scripts/paper_rebuild/storage_purge_record_check.py",
    "configs/paper_rebuild/clean6/STORAGE_PURGE_POLICY.yaml",
    "tests/paper_rebuild/test_canonical541_derived_tables.py",
    "tests/paper_rebuild/test_clean5_sequence_contracts.py",
    "tests/paper_rebuild/test_clean5_outcome_scope.py",
)


def _check_metadata(s, row, path):
    base._regular_single(s, path)
    for key, actual in (("size_bytes", s.st_size), ("device", s.st_dev),
                        ("inode", s.st_ino), ("mtime_ns", s.st_mtime_ns), ("nlink", s.st_nlink)):
        if type(row.get(key)) is not int or row[key] != actual:
            base._fail(f"source/quarantine metadata changed ({key}): {row['original_relative_path']}")


def _plain_rename(source, destination, expected):
    """Pinned parent FDs, no-follow metadata, explicit destination absence, no fallback."""
    with base._parent_fd(source) as (src, srcname), base._parent_fd(destination, create=True) as (dst, dstname):
        before = os.stat(srcname, dir_fd=src, follow_symlinks=False)
        base._regular_single(before, source)
        if not base._same_stat(before, expected):
            base._fail("source changed immediately before rename")
        if before.st_dev != os.fstat(dst).st_dev:
            base._fail("cross-filesystem rename forbidden")
        try:
            os.stat(dstname, dir_fd=dst, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            base._fail("destination collision immediately before rename")
        if os.path.lexists(destination):
            base._fail("destination lexists immediately before rename")
        os.rename(srcname, dstname, src_dir_fd=src, dst_dir_fd=dst)
        os.fsync(src)
        os.fsync(dst)
        try:
            os.stat(srcname, dir_fd=src, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            base._fail("source still present after rename")
        after = os.stat(dstname, dir_fd=dst, follow_symlinks=False)
        base._regular_single(after, destination)
        if not base._same_stat(before, after):
            base._fail("destination metadata changed across rename")
        return after


class DrvfsStoragePurge(base.StoragePurge):
    def __init__(self, clean_root, code_root, policy, closure, audit_root, *, code_commit,
                 canonical_attempt, metadata_workers=8):
        super().__init__(clean_root, code_root, policy, closure, audit_root)
        if re.fullmatch(r"[0-9a-f]{40}", code_commit) is None:
            base._fail("full frozen code commit required")
        if type(metadata_workers) is not int or not 1 <= metadata_workers <= 16:
            base._fail("metadata workers must be 1..16")
        self.policy_path = base._absolute_without_links(policy)
        if self.policy_path != self.code / "configs/paper_rebuild/clean6/STORAGE_PURGE_POLICY.yaml":
            base._fail("execution policy must be the tracked operation policy")
        self.closure_path = base._absolute_without_links(closure)
        if self.closure_path != self.audit / "REFERENCE_CLOSURE.json":
            base._fail("execution closure must be the imported audit REFERENCE_CLOSURE.json")
        self.canonical = base._absolute_without_links(canonical_attempt)
        if self.clean / "stages" not in self.canonical.parents or not stat.S_ISDIR(base._stat(self.canonical).st_mode):
            base._fail("canonical attempt must be an existing CLEAN_ROOT stage directory")
        amendment = self.policy.get("continuation_amendment", {})
        if (amendment.get("recompute_candidate_payload_sha256") is not False
                or amendment.get("fresh_preflight_required_for_continuation") is not True
                or self.policy.get("physical_operations", {}).get("rename_flags") != "none"):
            base._fail("policy does not authorize this exact DrvFS continuation")
        self.code_commit, self.metadata_workers = code_commit, metadata_workers
        self._active = False
        self._phase = "NOT_STARTED"
        self._permit = None
        self._receipts = {}
        self._events = []
        self._moved = self._purged = 0
        self._progress_bytes = None
        self._ledger_value = {"candidate_count": None, "candidate_bytes": None}

    def _code_identity(self):
        actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.code, capture_output=True, check=True).stdout.decode().strip()
        if actual != self.code_commit:
            base._fail("code HEAD changed from frozen commit")
        for relative in CODE_FILES:
            frozen = subprocess.run(["git", "show", self.code_commit + ":" + relative],
                                    cwd=self.code, capture_output=True, check=True).stdout
            if base._read(self.code / relative) != frozen:
                base._fail("tracked operation code or policy is dirty: " + relative)

    def _controls(self):
        ledger, hashes = self._ledger()
        if base._read(self.policy_path) != self.policy_bytes or base._read(self.closure_path) != self.closure_bytes:
            base._fail("policy/closure literal bytes changed")
        self._code_identity()
        if (ledger.get("continuation_strategy") != STRATEGY
                or ledger.get("candidate_payload_rehashed") is not False
                or ledger.get("candidate_selection_recomputed") is not False):
            base._fail("ledger is not an exact inherited-B continuation")
        origin = ledger.get("origin_b", {})
        if (not isinstance(origin.get("audit"), str)
                or not origin["audit"].startswith("<CLEAN_ROOT>/storage_purge/")):
            base._fail("missing portable origin-B audit")
        old_audit = self.alias(origin["audit"])
        if old_audit.parent != self.audit.parent or old_audit == self.audit:
            base._fail("invalid origin-B audit scope")
        for key in ("ledger_sha256", "plan_sha256", "closure_sha256", "policy_sha256", "journal_sha256"):
            if not isinstance(origin.get(key), str) or base.HEX.fullmatch(origin[key]) is None:
                base._fail("missing origin-B control hash: " + key)
            hashes["origin_b_" + key] = origin[key]
        binding = {"audit": self.portable(self.audit), "origin_b_audit": origin["audit"],
                   "code_commit": self.code_commit, "rename_strategy": STRATEGY}
        return ledger, binding, hashes

    def _check_controls(self):
        ledger, binding, hashes = self._controls()
        if binding != self._binding or hashes != self._hashes:
            base._fail("control ledger/plan/closure/policy/code binding changed")
        return ledger

    def _check_permit(self, permit):
        if not self._active or not isinstance(permit, DispatchPermit):
            base._fail("physical phase requires the active dispatcher permit")
        if self._permit is None:
            self._permit = permit
        elif self._permit is not permit:
            base._fail("physical phase substituted the permit object")
        self._check_controls()
        if dict(permit.binding) != self._binding or dict(permit.control_hashes) != self._hashes:
            base._fail("permit control binding mismatch")
        raw = base._read(self.audit / RECEIPT_FILES["preflight"])
        expected = self._receipts.get("preflight")
        if (expected is None or base._digest(raw) != expected[0]
                or json.loads(raw) != permit.preflight_receipt.to_dict()
                or permit.preflight_id != expected[1]["preflight_id"]
                or permit.preflight_sha256 != expected[1]["receipt_sha256"]):
            base._fail("preflight literal file SHA or receipt identity changed")
        for phase, (digest, _) in self._receipts.items():
            if base._digest(base._read(self.audit / RECEIPT_FILES[phase])) != digest:
                base._fail("prior phase receipt file changed: " + phase)

    def _save_receipt(self, phase, context, previous=None, **extra):
        fields = dict(phase=phase, status="PASS", exit_code=0,
                      gates={g: "PASS" for g in GATES[phase]}, preflight_id=context.preflight_id,
                      binding=dict(context.binding), control_hashes=dict(context.control_hashes),
                      **self._hashes, time_utc=base._utc(),
                      candidate_count=self._ledger_value["candidate_count"],
                      candidate_bytes=self._ledger_value["candidate_bytes"],
                      candidate_payload_rehashed=False, sha256_origin="B_LEDGER", **extra)
        if phase == "purge":
            fields["gates"].update({f"C{i}": "PASS" for i in range(1, 6)})
        if phase != "preflight":
            fields.update(preflight_sha256=context.preflight_sha256,
                          preflight_literal_sha256=self._receipts["preflight"][0],
                          previous_receipt_sha256=previous.receipt_sha256)
        sealed = seal_receipt(fields)
        data = base._json_bytes(sealed)
        base._write_new(self.audit / RECEIPT_FILES[phase], data)
        self._receipts[phase] = (base._digest(data), sealed)
        return sealed

    def _progress(self, status):
        data = base._json_bytes(dict(status=status, phase=self._phase, time_utc=base._utc(),
                                    moved_files=self._moved, purged_files=self._purged,
                                    candidate_count=self._ledger_value["candidate_count"],
                                    candidate_bytes=self._ledger_value["candidate_bytes"],
                                    counts_basis="durable_METADATA_VERIFIED_and_PURGED_events",
                                    candidate_payload_rehashed=False, sha256_origin="B_LEDGER"))
        path = self.audit / "QUARANTINE_PROGRESS.json"
        if self._progress_bytes is None:
            base._write_new(path, data)
        else:
            if base._read(path) != self._progress_bytes:
                base._fail("owned progress file changed unexpectedly")
            temporary = self.audit / "QUARANTINE_PROGRESS.next.json"
            base._write_new(temporary, data)
            with base._parent_fd(path) as (parent, name):
                base._regular_single(os.stat(name, dir_fd=parent, follow_symlinks=False), path)
                os.replace(temporary.name, name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
        self._progress_bytes = data
        print(f"{self._phase} {status}: moved {self._moved}, purged {self._purged}/{self._ledger_value['candidate_count']}", flush=True)

    def _probe(self):
        source, target = self.audit / "IO_PROBE/source.zero", self.audit / "IO_PROBE/destination.zero"
        base._write_new(source, b"")
        before = base._stat(source)
        _plain_rename(source, target, before)
        result = dict(status="PASS", exit_code=0, strategy=STRATEGY, source_absent=not base._exists(source),
                      destination_present=base._exists(target), size_bytes=base._stat(target).st_size,
                      candidate_payload_reads=0, artifacts_retained=True)
        if not result["source_absent"] or not result["destination_present"] or result["size_bytes"] != 0:
            base._fail("IO probe postconditions failed")
        base._write_new(self.audit / "IO_PROBE.json", base._json_bytes(result))
        return result

    def _free_space(self, name):
        space = os.statvfs(self.clean)
        base._write_new(self.audit / name, base._json_bytes(dict(
            time_utc=base._utc(), filesystem_alias="G: / <CLEAN_ROOT>",
            available_bytes=space.f_bavail * space.f_frsize,
            free_bytes=space.f_bfree * space.f_frsize,
            total_bytes=space.f_blocks * space.f_frsize)))

    def _metadata_gate(self, row):
        path = self.clean / row["original_relative_path"]
        s = base._stat(path)
        _check_metadata(s, row, path)
        classification = self.classify(row["original_relative_path"], s)
        if (row.get("classification") != "BULK_DELETABLE" or classification[0] != "BULK_DELETABLE"
                or classification[2:] != (row["family"], row["file_class"])):
            base._fail("C1 changed classification/family: " + row["original_relative_path"])
        if base._exists(self.clean / row["quarantine_relative_path"]):
            base._fail("quarantine destination exists")

    def _origin_and_seals(self):
        origin = self._ledger_value["origin_b"]
        old_root = self.alias(origin["audit"])
        for name, key in (("DELETION_LEDGER.json", "ledger_sha256"), ("DELETION_PLAN.csv", "plan_sha256"),
                          ("REFERENCE_CLOSURE.json", "closure_sha256"), ("JOURNAL.jsonl", "journal_sha256")):
            if base._digest(base._read(old_root / name)) != origin[key]:
                base._fail("origin-B literal control changed: " + name)
        old = base._load(old_root / "DELETION_LEDGER.json")
        if old["policy_sha256"] != origin["policy_sha256"]:
            base._fail("origin-B policy binding changed")
        ignored = {"quarantine_timestamp", "quarantine_relative_path"}
        if len(old["entries"]) != len(self._ledger_value["entries"]):
            base._fail("inherited B candidate count differs")
        for before, after in zip(old["entries"], self._ledger_value["entries"]):
            if {k: v for k, v in before.items() if k not in ignored} != {k: v for k, v in after.items() if k not in ignored}:
                base._fail("candidate selection or B evidence changed")
        sources = {}
        for row in self._ledger_value["entries"]:
            for item in row["seal_provenance"]:
                if item["path"] in sources and sources[item["path"]] != item["sha256"]:
                    base._fail("conflicting seal source hashes")
                sources[item["path"]] = item["sha256"]
        for path, sha in sorted(sources.items()):
            if base._digest(base._read(self.alias(path))) != sha:
                base._fail("seal metadata changed: " + path)

    def _command(self, args, log_name):
        env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPATH="src", LEGSA_C541_ATTEMPT_ROOT=str(self.canonical), LEGSA_CLEAN5_ROOT=str(self.clean))
        with base._parent_fd(self.audit / log_name) as (parent, name):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, "wb") as stream:
                result = subprocess.run(args, cwd=self.code, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                        check=False, shell=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent)
        if type(result.returncode) is not int or result.returncode != 0:
            base._fail(f"subprocess failed ({log_name}, exit {result.returncode})")

    def _records(self, *, after):
        name = "RECORDS_AFTER_QUARANTINE.json" if after else "RECORDS_BASELINE.json"
        path = self.audit / name
        if base._exists(path):
            base._fail("record check output already exists")
        args = ["/usr/bin/python3", str(self.code / "scripts/paper_rebuild/storage_purge_record_check.py"),
                "--clean-root", str(self.clean), "--code-root", str(self.code), "--output", str(path)]
        if after:
            args += ["--baseline", str(self.audit / "RECORDS_BASELINE.json")]
        self._command(args, name + ".stdout.log")
        result = base._load(path)
        if (result.get("status") != "PASS" or not RECORD_CHECKS <= result.get("checks", {}).keys()
                or any(v != "PASS" for v in result["checks"].values())
                or any(type(result.get(k)) is not int or result[k] != 0 for k in
                       ("solver_invocations", "evaluator_invocations", "raw_content_open_count"))):
            base._fail("record checker did not explicitly pass all checks")
        if after and (result.get("records_identical_to_baseline") is not True
                      or result.get("baseline_sha256") != self._baseline_sha):
            base._fail("record baseline identity or comparison failed")
        if not after:
            self._baseline_sha = base._digest(base._read(path))
        return result

    def _preflight(self, challenge):
        self._phase = "PREFLIGHT"
        self._free_space("FREE_SPACE_BEFORE.json")
        probe = self._probe()  # Mandatory first; exceptions prevent all candidate operations.
        if (not isinstance(probe, dict) or probe.get("status") != "PASS"
                or type(probe.get("exit_code")) is not int or probe["exit_code"] != 0
                or probe.get("source_absent") is not True or probe.get("destination_present") is not True
                or type(probe.get("size_bytes")) is not int or probe["size_bytes"] != 0
                or probe.get("strategy") != STRATEGY
                or base._load(self.audit / "IO_PROBE.json") != probe):
            base._fail("IO probe lacks an explicit successful bound result")
        self._check_controls()
        with ThreadPoolExecutor(max_workers=self.metadata_workers) as pool:
            rows = iter(self._ledger_value["entries"])
            pending = deque()
            for _ in range(self.metadata_workers):
                row = next(rows, None)
                if row is not None:
                    pending.append(pool.submit(self._metadata_gate, row))
            done = 0
            while pending:
                pending.popleft().result()
                done += 1
                if done % 1000 == 0:
                    print(f"preflight metadata {done}/{self._ledger_value['candidate_count']}", flush=True)
                row = next(rows, None)
                if row is not None:
                    pending.append(pool.submit(self._metadata_gate, row))
        removed = {r["original_relative_path"] for r in self._ledger_value["entries"]}
        references = self._references(removed)
        self._origin_and_seals()
        self._records(after=False)
        self._check_controls()
        return self._save_receipt("preflight", challenge, references=references,
                                  keep_match_count=0, outside_stages_count=0, invalidclassfamily_count=0,
                                  baseline_sha256=self._baseline_sha,
                                  io_probe_sha256=base._digest(base._read(self.audit / "IO_PROBE.json")))

    def _quarantine(self, permit):
        self._phase = "QUARANTINE"
        self._check_permit(permit)
        self._journal_binding = dict(self._hashes, preflight_id=permit.preflight_id,
                                     preflight_sha256=permit.preflight_sha256,
                                     preflight_literal_sha256=self._receipts["preflight"][0])
        for i, row in enumerate(self._ledger_value["entries"], 1):
            source, target = self.clean / row["original_relative_path"], self.clean / row["quarantine_relative_path"]
            before = base._stat(source)
            _check_metadata(before, row, source)
            self._append(self._events, self._journal_binding, "MOVE_PREPARED", row,
                         payload_rehashed=False, sha256_origin="B_LEDGER")
            after = _plain_rename(source, target, before)
            _check_metadata(after, row, target)
            self._append(self._events, self._journal_binding, "MOVED_METADATA_VERIFIED", row,
                         payload_rehashed=False, sha256_origin="B_LEDGER", source_absent=True,
                         destination_present=True, metadata_unchanged=True)
            self._moved += 1
            if i % 1000 == 0:
                self._progress("IN_PROGRESS")
        self._exact_quarantine(self._ledger_value)
        self._check_permit(permit)
        self._progress("QUARANTINED")
        return self._save_receipt("quarantine", permit, permit.preflight_receipt,
                                  moved_files=self._moved, verified_files=self._moved, exact_quarantine_set=True,
                                  moved_logical_bytes=self._ledger_value["candidate_bytes"],
                                  journal_binding=self._journal_binding)

    def _c5(self, permit, quarantine_receipt):
        self._phase = "C5"
        self._check_permit(permit)
        xml_path = self.audit / "C5_TESTS.xml"
        if base._exists(xml_path):
            base._fail("C5 XML output already exists")
        self._command(["/usr/bin/python3", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                       "--junitxml", str(xml_path), *C5_NODES], "C5_TESTS.stdout.log")
        root = ET.fromstring(base._read(xml_path))
        cases = list(root.iter("testcase"))
        suites = list(root.iter("testsuite"))
        if (len(cases) != 20 or not suites or any(list(root.iter(tag)) for tag in ("failure", "error", "skipped"))
                or sum(int(s.get("tests", "-1")) for s in suites) != 20
                or any(int(s.get(k, "-1")) != 0 for s in suites for k in ("failures", "errors", "skipped"))):
            base._fail("C5 requires exactly 20 passed, zero failed/errors/skipped")
        if base._digest(base._read(self.audit / "RECORDS_BASELINE.json")) != self._baseline_sha:
            base._fail("baseline file changed before C5")
        self._records(after=True)
        references = self._references({r["original_relative_path"] for r in self._ledger_value["entries"]})
        self._check_permit(permit)
        return self._save_receipt("c5", permit, quarantine_receipt,
                                  checks={**{k: "PASS" for k in base.C5_CHECKS}, "reference_paths_readability": "PASS"},
                                  reference_path_count=len(references),
                                  tests={"passed": 20, "failed": 0, "errors": 0, "skipped": 0},
                                  xml_sha256=base._digest(base._read(xml_path)),
                                  records_sha256=base._digest(base._read(self.audit / "RECORDS_AFTER_QUARANTINE.json")))

    def _validate_journal(self):
        events = self._journal(self._journal_binding)
        if events != self._events:
            base._fail("durable journal differs from this invocation")
        expected = ("MOVE_PREPARED", "MOVED_METADATA_VERIFIED", "PURGE_PREPARED", "PURGED")
        rows = {r["original_relative_path"]: r for r in self._ledger_value["entries"]}
        actions = {path: [] for path in rows}
        for event in events:
            relative = event.get("original_relative_path")
            row = rows.get(relative)
            if (row is None or any(event.get(k) != row[k] for k in ("sha256", "size_bytes"))
                    or event.get("payload_rehashed") is not False or event.get("sha256_origin") != "B_LEDGER"):
                base._fail("journal entry not bound to B candidate")
            actions[relative].append(event["action"])
            if tuple(actions[relative]) != expected[:len(actions[relative])]:
                base._fail("unexpected/repeated journal event order")
        return actions

    def _purge(self, permit, quarantine_receipt, c5_receipt):
        self._phase = "PURGE"
        self._check_permit(permit)
        actions = self._validate_journal()
        if any(values != ["MOVE_PREPARED", "MOVED_METADATA_VERIFIED"] for values in actions.values()):
            base._fail("purge requires every candidate metadata-verified exactly once")
        self._exact_quarantine(self._ledger_value)
        removed = set()
        for i, row in enumerate(self._ledger_value["entries"], 1):
            relative = row["original_relative_path"]
            path = self.clean / row["quarantine_relative_path"]
            if base._exists(self.clean / relative):
                base._fail("original path reappeared before purge")
            before = base._stat(path)
            _check_metadata(before, row, path)
            self._append(self._events, self._journal_binding, "PURGE_PREPARED", row,
                         payload_rehashed=False, sha256_origin="B_LEDGER")
            with base._parent_fd(path) as (parent, name):
                now = os.stat(name, dir_fd=parent, follow_symlinks=False)
                _check_metadata(now, row, path)
                os.unlink(name, dir_fd=parent)
                os.fsync(parent)
            self._append(self._events, self._journal_binding, "PURGED", row,
                         payload_rehashed=False, sha256_origin="B_LEDGER", recovered_after_prepare=False)
            self._purged += 1
            removed.add(relative)
            if i % 1000 == 0:
                self._progress("IN_PROGRESS")
        self._exact_quarantine(self._ledger_value, removed)
        actions = self._validate_journal()
        if any(len(values) != 4 for values in actions.values()):
            base._fail("purged journal coverage incomplete")
        if base._exists(self.quarantine):
            directories = [p for p, s in self._walk(self.quarantine) if stat.S_ISDIR(s.st_mode)]
            for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True) + [self.quarantine]:
                with base._parent_fd(directory) as (parent, name):
                    os.rmdir(name, dir_fd=parent)
                    os.fsync(parent)
        self._check_permit(permit)
        self._progress("PURGED")
        return self._save_receipt("purge", permit, c5_receipt,
                                  all_c_gates={f"C{i}": "PASS" for i in range(1, 6)},
                                  purged_files=self._purged, purged_logical_bytes=self._ledger_value["candidate_bytes"],
                                  journal_binding=self._journal_binding,
                                  journal_sha256=base._digest(base._read(self.audit / "JOURNAL.jsonl")),
                                  original_directories_retained=True)

    def run(self):
        if not __debug__:
            base._fail("optimized Python is forbidden")
        with self._operation_lock():
            forbidden = (*RECEIPT_FILES.values(), "JOURNAL.jsonl", "DRVFS_STARTED.json", "DRVFS_TERMINAL.json",
                         "QUARANTINE_PROGRESS.json", "IO_PROBE", "IO_PROBE.json", "RECORDS_BASELINE.json",
                         "FREE_SPACE_BEFORE.json", "FREE_SPACE_AFTER.json", "FREE_SPACE_AFTER_STOP.json")
            if self._active or any(base._exists(self.audit / name) for name in forbidden) or base._exists(self.quarantine):
                base._fail("old receipts, prior attempt or quarantine exists; no resume/replay")
            self._active = True
            try:
                self._ledger_value, self._binding, self._hashes = self._controls()
                base._write_new(self.audit / "DRVFS_STARTED.json", base._json_bytes(dict(
                    status="STARTED", binding=self._binding, control_hashes=self._hashes, time_utc=base._utc())))
                result = dispatch(expected_binding=self._binding, expected_control_hashes=self._hashes,
                                  required_gates=GATES, preflight=self._preflight, quarantine=self._quarantine,
                                  c5=self._c5, purge=self._purge)
                self._free_space("FREE_SPACE_AFTER.json")
                base._write_new(self.audit / "DRVFS_TERMINAL.json", base._json_bytes(dict(
                    status="PURGED", moved_files=self._moved, purged_files=self._purged,
                    candidate_count=self._ledger_value["candidate_count"],
                    candidate_bytes=self._ledger_value["candidate_bytes"],
                    purge_receipt_sha256=result.purge_receipt.receipt_sha256, time_utc=base._utc())))
                return result.purge_receipt.to_dict()
            except BaseException as exc:
                self._progress("FAILED")
                self._free_space("FREE_SPACE_AFTER_STOP.json")
                message = str(exc).replace(str(self.clean), "<CLEAN_ROOT>").replace(str(self.code), "<CODE_ROOT>")
                base._write_new(self.audit / "DRVFS_TERMINAL.json", base._json_bytes(dict(
                    status="FAILED", phase=self._phase, exception_type=type(exc).__name__, error=message,
                    moved_files=self._moved, purged_files=self._purged, time_utc=base._utc(),
                    counts_basis="durable_METADATA_VERIFIED_and_PURGED_events",
                    pending_move_prepared=sorted({e["original_relative_path"] for e in self._events if e["action"] == "MOVE_PREPARED"}
                        - {e["original_relative_path"] for e in self._events if e["action"] == "MOVED_METADATA_VERIFIED"}),
                    pending_purge_prepared=sorted({e["original_relative_path"] for e in self._events if e["action"] == "PURGE_PREPARED"}
                        - {e["original_relative_path"] for e in self._events if e["action"] == "PURGED"}),
                    retry_count=0, rollback_performed=False)))
                raise
            finally:
                self._active = False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("clean-root", "code-root", "policy", "closure", "audit-root", "canonical-attempt"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--metadata-workers", type=int, default=8)
    args = vars(parser.parse_args(argv))
    print(json.dumps(DrvfsStoragePurge(**args).run(), sort_keys=True))
