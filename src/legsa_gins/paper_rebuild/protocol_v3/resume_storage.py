"""Append-only V3-01-R storage continuation; original scientific functions stay frozen.

Reconciliation is an explicit admission, not discovery or permission to retry.
Every reuse item supplies pinned JSON ``native_record`` and ``evaluations``
(keys v3/v2). ``identity_native_only`` keeps its original native slot, and may
supply existing evaluator pins. ``recovery_runs`` alone authorizes rerunning a
consumed original native slot, with any historical NAV/STD hashes mandatory.
"""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import zlib

import yaml

from ..clean6_canonical_v2.archive_io import retry_io, stream_copy, _write_all
from ..clean6_canonical_v2.io_recovery import _metadata_bytes
from ..hext.sequence_paths import load_sequence_paths, REGISTRY, CALIBRATED_CONTRACT
from ..manifest import sha256_file
from . import runtime
from .controller import Context, _resolve
from .registry import STAGE, validate_registry

WORKERS = BATCH_SIZE = 22
E_MIN = 40_000_000_000
G_MIN = 30_000_000_000
SCRATCH_MAX = 20_000_000_000
CONTINUATION = "V3R_CONTINUATION"
VERSIONS = ("v3", "v2")
_WRITE_LOCK = threading.Lock()


def safe(path):
    return runtime.frozen._safe(path)


def inside(path, root):
    path, root = safe(path), safe(root)
    if path == root or root not in path.parents:
        raise PermissionError("HARD_STOP_V3R_PATH_SCOPE: " + str(path))
    return path


def read_json(path):
    return json.loads(safe(path).read_text())


def pinned_json(pin, root=None):
    path = runtime.verify_pin(pin, cached=False)
    if root is not None:
        inside(path, root)
    return read_json(path)


def persist(path, value):
    """Exclusive metadata write through the established bounded I/O wrapper.

    No rename/replace assumption is made on exFAT. An existing complete record
    must be exactly equal; a partial record is preserved and stops admission.
    """
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    persist_bytes(path, payload)
    return value


def persist_bytes(path, payload):
    """Idempotent fixed bytes; only an exact prefix may complete after interruption."""
    path = safe(path)
    with _WRITE_LOCK:
        if path.exists():
            current, _ = retry_io(path.read_bytes, source=path, destination=path, operation="v3r_metadata_read")
            if current == payload:
                return
            if not payload.startswith(current):
                raise RuntimeError("HARD_STOP_V3R_CHECKPOINT_CHANGED: " + str(path))
            _metadata_bytes(path, payload[len(current):], append=True)
        else:
            _metadata_bytes(path, payload, append=False)
        if sha256_file(path) != hashlib.sha256(payload).hexdigest():
            raise RuntimeError("HARD_STOP_V3R_METADATA_COPY_HASH")


KEEP_CORE_CASES = frozenset({"C00_clean_normal"} | {f"D{i:02d}_seed_00" for i in range(1, 61)})


def retention_rows(specs, triggered):
    """Portable registry-derived decisions, independent of measured performance."""
    rows = []
    for spec in specs:
        if spec["domain"] not in ("CORE", "SEQUENCE", "ADDENDUM"):
            raise RuntimeError("HARD_STOP_V3R_RETENTION_UNKNOWN_DOMAIN")
        reason = ("FULL_RETENTION_THRESHOLD_NOT_TRIGGERED" if not triggered else
            "EXTRA_SEQUENCE" if spec["domain"] == "SEQUENCE" else
            "A1_A2_ADDENDUM" if spec["domain"] == "ADDENDUM" else
            "C00_AND_61_CASE_SEED_ZERO" if spec["case_id"] in KEEP_CORE_CASES else
            "OMIT_CORE_NON_RETAINED_ERROR_SERIES_ONLY")
        rows.append(dict(run_id=spec["run_id"], domain=spec["domain"],
            sequence_id=spec["sequence_id"], case_id=spec["case_id"], method_id=spec["method_id"],
            retain_error_series=reason != "OMIT_CORE_NON_RETAINED_ERROR_SERIES_ONLY",
            evaluator_versions="v3;v2", reason=reason))
    if len({r["run_id"] for r in rows}) != len(rows):
        raise RuntimeError("HARD_STOP_V3R_RETENTION_DUPLICATE_RUN")
    return rows


def capacity_admission(control, forecast_sha256, registry_sha256, specs):
    """Admit the measured 60% decision and write an immutable, exact policy."""
    control = safe(control)
    forecast_pin = dict(path=str(control / "CAPACITY_FORECAST.json"), sha256=forecast_sha256)
    forecast = pinned_json(forecast_pin, control)
    if (forecast.get("schema") != "V3R_CAPACITY_FORECAST_V1"
            or forecast.get("storage_provenance_only") is not True
            or forecast.get("native_calls") != 0 or forecast.get("evaluator_calls") != 0
            or forecast.get("registry_sha256") != registry_sha256
            or forecast.get("sample_batches") != 8 or forecast.get("threshold_fraction") != 0.6):
        raise RuntimeError("HARD_STOP_V3R_CAPACITY_FORECAST_IDENTITY")
    sample_pin = dict(path=str(control / "CAPACITY_SAMPLE_8_BATCHES.csv"), sha256=forecast["sample_csv_sha256"])
    runtime.verify_pin(sample_pin, cached=False)
    free = forecast["g_available_bytes_at_forecast"]
    baseline = forecast["matrix_aggregate_remaining_allocated_bytes"]
    triggered = baseline > free * 0.6
    if (free <= 0 or baseline < 0 or forecast["threshold_bytes"] != free * 0.6
            or forecast["conditional_retention_triggered"] is not triggered):
        raise RuntimeError("HARD_STOP_V3R_CAPACITY_THRESHOLD_MISMATCH")
    rows = retention_rows(specs, triggered)
    keep = sum(r["retain_error_series"] for r in rows)
    # Even when the threshold is false, the forecast's conditional scenario
    # describes the same explicit 1188-run whitelist.
    conditional_keep = sum(r["retain_error_series"] for r in retention_rows(specs, True))
    if (len(rows) != 6468 or conditional_keep != 1188
            or forecast["retained_native_slots"] != conditional_keep
            or forecast["retained_evaluator_slots"] != 2 * conditional_keep
            or forecast["omitted_evaluator_slots"] != 2 * (len(rows) - conditional_keep)):
        raise RuntimeError("HARD_STOP_V3R_RETENTION_COUNTS")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    index_bytes = stream.getvalue().encode("utf-8")
    policy = dict(schema="V3R_CONDITIONAL_RETENTION_V1", forecast=forecast_pin,
        registry_sha256=registry_sha256, threshold_fraction=0.6,
        conditional_retention_triggered=triggered,
        keep_core_cases=sorted(KEEP_CORE_CASES), keep_entire_domains=["SEQUENCE", "ADDENDUM"],
        methods="ALL_11_FROZEN_CONFIGURATIONS", evaluator_versions=list(VERSIONS),
        run_count=len(rows), retained_native_slots=keep, retained_evaluator_slots=2 * keep,
        omitted_evaluator_slots=2 * (len(rows) - keep),
        omitted_members_only=["error_series.csv", "error_series.csv.gz"],
        original_seals_results_manifests_hashes_unchanged=True, native_evaluator_calls=0,
        index=dict(relative_path="RETENTION_INDEX.csv", sha256=hashlib.sha256(index_bytes).hexdigest()))
    persist_bytes(control / "RETENTION_INDEX.csv", index_bytes)
    persist(control / "RETENTION_POLICY.json", policy)
    policy_pin = dict(path=str(control / "RETENTION_POLICY.json"), sha256=sha256_file(control / "RETENTION_POLICY.json"))
    decisions = {r["run_id"]: {**r, "policy": policy_pin} for r in rows}
    return decisions, dict(forecast=forecast_pin, retention_policy=policy_pin, **forecast)


def error_series_member(relative):
    return Path(relative).name in ("error_series.csv", "error_series.csv.gz")


def validate_retention_decision(decision):
    if (type(decision.get("retain_error_series")) is not bool
            or decision.get("domain") not in ("CORE", "SEQUENCE", "ADDENDUM")
            or not decision.get("run_id") or not decision.get("case_id") or not decision.get("policy")
            or (decision["retain_error_series"] is False
                and (decision["domain"] != "CORE" or decision["case_id"] in KEEP_CORE_CASES))):
        raise RuntimeError("HARD_STOP_V3R_RETENTION_PROTECTED_CASE_OR_INVALID_DECISION")


PROTECTION_INDEX_SHA256 = "6003ac1ad70d4b4bbe77d83cf00340a306486d1cea185dcce2e31ac430e02781"


def purge_prime_admission(archive, record_pin):
    """Require the committed P′ verification and complete 16411-item receipt."""
    archive = safe(archive)
    audit = archive / "V3R_PURGE/PROTOCOL_V2_RETAINED"
    record_path = safe(record_pin["path"])
    if record_path.parent != audit:
        raise RuntimeError("HARD_STOP_V3R_PURGE_PRIME_RECORD_SCOPE")
    record = pinned_json(record_pin, audit)
    index_pin = dict(path=str(audit / "PROTECTION_INDEX.json"), sha256=PROTECTION_INDEX_SHA256)
    original_index = dict(path=str(archive / "V3R_PURGE/PROTECTION_INDEX.json"), sha256=PROTECTION_INDEX_SHA256)
    index = pinned_json(index_pin, audit)
    runtime.verify_pin(original_index, cached=False)
    ledger_sha = sha256_file(audit / "PURGE_LEDGER.csv")
    result = read_json(audit / "PURGE_RESULT.json")
    events = [json.loads(line) for line in (audit / "OPERATIONS.jsonl").read_text().splitlines()]
    verified = [e for e in events if e.get("action") == "VERIFIED"]
    if (record.get("status") != "PASS" or record.get("ledger_sha256") != ledger_sha
            or result.get("status") != "PASS_LEDGERED_PURGE_COMPLETE"
            or not verified or verified[-1].get("record_path") != str(record_path)
            or verified[-1].get("record_sha256") != record_pin["sha256"]
            or any(e.get("action") in ("ROLLBACK_BEGIN", "ROLLED_BACK") for e in events)
            or not events or events[-1].get("action") != "PURGE_COMPLETE"):
        raise RuntimeError("HARD_STOP_V3R_PURGE_PRIME_NOT_COMMITTED_COMPLETE")
    receipt_path = safe(record["receipt_path"])
    if receipt_path.parent != audit:
        raise RuntimeError("HARD_STOP_V3R_PURGE_PRIME_RECEIPT_SCOPE")
    receipt_pin = dict(path=str(receipt_path), sha256=record["receipt_sha256"])
    receipt = pinned_json(receipt_pin, audit)
    if (receipt.get("status") != "PASS" or receipt.get("verification_complete") is not True
            or receipt.get("failed") != 0 or receipt.get("verified") != 16411 or receipt.get("total") != 16411
            or receipt.get("index_sha256") != PROTECTION_INDEX_SHA256
            or receipt.get("ledger_sha256") != ledger_sha
            or not any(e.get("action") == "VERIFY_EXIT" and e.get("returncode") == 0
                and e.get("receipt") == str(receipt_path) for e in events)):
        raise RuntimeError("HARD_STOP_V3R_PURGE_PRIME_INCOMPLETE_VERIFICATION")
    checks = receipt.get("checks", [])
    expected = index.get("verification_pins", [])
    key = lambda item: (item["path"], item.get("kind", ""), item.get("commit", ""), item["sha256"])
    if (len(checks) != 16411 or len(expected) != 16411
            or sorted(map(key, checks)) != sorted(map(key, expected))
            or any(row.get("status") != "PASS" or row.get("actual_sha256") != row["sha256"]
                or ("size_bytes" in row and row.get("actual_size_bytes") != row["size_bytes"]) for row in checks)):
        raise RuntimeError("HARD_STOP_V3R_PURGE_PRIME_CHECK_COVERAGE")
    return dict(status="PASS", verification_count=16411, record=record_pin,
        receipt=receipt_pin, protection_index=index_pin,
        result=dict(path=str(audit / "PURGE_RESULT.json"), sha256=sha256_file(audit / "PURGE_RESULT.json")),
        operation_journal=dict(path=str(audit / "OPERATIONS.jsonl"), sha256=sha256_file(audit / "OPERATIONS.jsonl")))


def continuation_freeze(code, science_freeze, continuation_commit, original):
    code = safe(code)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=code,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).strip()
    remote = git("ls-remote", "origin", "refs/heads/stage/clean3-math-repair").split()
    if (git("rev-parse", "HEAD").decode() != continuation_commit
            or not remote or remote[0].decode() != continuation_commit):
        raise RuntimeError("HARD_STOP_V3R_CONTINUATION_NOT_CURRENT_AND_PUSHED")
    if (original.get("status") != "PASS_PUSHED_CODE_FREEZE"
            or original.get("code_freeze") != science_freeze
            or original.get("remote_commit") != science_freeze):
        raise RuntimeError("HARD_STOP_V3R_ORIGINAL_FREEZE")
    git("merge-base", "--is-ancestor", science_freeze, continuation_commit)
    checked = {}
    for name, expected in original["source_sha256"].items():
        # Documentation may append storage evidence. All original executable
        # science, tests, source indexes and contracts remain byte-identical.
        if name.startswith("docs/"):
            continue
        actual = (code / name).read_bytes()
        # check_output.strip above is for Git identifiers; use raw object bytes.
        frozen = subprocess.check_output(["git", "show", science_freeze + ":" + name], cwd=code)
        if hashlib.sha256(frozen).hexdigest() != expected or actual != frozen:
            raise RuntimeError("HARD_STOP_V3R_SCIENCE_SOURCE_CHANGED: " + name)
        checked[name] = expected
    adapter_names = ("src/legsa_gins/paper_rebuild/protocol_v3/resume_storage.py",
        "scripts/paper_rebuild/v3_resume_storage.py",
        "tests/paper_rebuild/test_protocol_v3_resume_storage.py")
    for name in adapter_names:
        frozen = subprocess.check_output(["git", "show", continuation_commit + ":" + name], cwd=code)
        if (code / name).read_bytes() != frozen:
            raise RuntimeError("HARD_STOP_V3R_CONTINUATION_SOURCE_CHANGED: " + name)
        checked[name] = hashlib.sha256(frozen).hexdigest()
    return dict(status="PASS_PUSHED_CONTINUATION_FROZEN_SCIENCE",
        science_freeze=science_freeze, continuation_commit=continuation_commit,
        source_sha256=checked, original_freeze_receipt_rewritten=False,
        reservation_io_adapter=dict(function="protocol_v3.resume_storage.reserve_slot_with_retry",
            policy="FLOCK_FIXED_OFFSET_METADATA_BYTES_2_4_8_IO_RETRY",
            scope_duplicate_budget_predicates="IDENTICAL_TO_FROZEN_RUNTIME_RESERVE_SLOT",
            runtime_source_bytes_changed=False, native_evaluator_function_code_changed=False),
        report_io_adapter=dict(function="protocol_v3.resume_storage.report_output_io",
            allowed_output_directories=["07_AGGREGATE", "08_FIGURES"],
            frozen_serializers_and_renderer_reused=True, fixed_byte_write_sha256_verified=True))


def reserve_slot_with_retry(path, run_id, allowed_run_ids, *, kind):
    """The frozen reservation predicates, with only durable G append I/O adapted.

    Replaying a whole reservation is forbidden. The existing metadata helper
    retries the same bytes at one captured offset under the original file lock.
    """
    allowed = set(allowed_run_ids)
    if run_id not in allowed or kind not in ("native", "evaluator"):
        raise PermissionError("HARD_STOP_V3_UNREGISTERED_RESERVATION")
    path = safe(path)
    retry_io(lambda: path.parent.mkdir(parents=True, exist_ok=True), source=path,
        destination=path, operation="v3r_reservation_parent")
    stream, _ = retry_io(lambda: path.open("a+", encoding="utf-8"), source=path,
        destination=path, operation="v3r_reservation_open")
    with stream:
        retry_io(lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_EX), source=path,
            destination=path, operation="v3r_reservation_lock")
        def read_rows():
            stream.seek(0)
            return [json.loads(line) for line in stream if line.strip()]
        rows, _ = retry_io(read_rows, source=path, destination=path, operation="v3r_reservation_read")
        if (any(r["kind"] != kind or r["run_id"] not in allowed for r in rows)
                or len({r["run_id"] for r in rows}) != len(rows)):
            raise RuntimeError("HARD_STOP_V3_RESERVATION_SCOPE")
        if any(r["run_id"] == run_id for r in rows):
            raise RuntimeError("HARD_STOP_V3_ALREADY_RESERVED_NO_RETRY")
        if len(rows) >= len(allowed):
            raise RuntimeError("HARD_STOP_V3_BUDGET")
        row = dict(run_id=run_id, kind=kind, ordinal=len(rows) + 1, budget=len(allowed),
            status="RESERVED_BEFORE_LAUNCH", retry_count=0)
        _metadata_bytes(path, (json.dumps(row) + "\n").encode(), append=True)
    return row


@contextmanager
def report_output_io(root):
    """Retry only newly authored 07/08 output bytes; retain frozen serializers.

    Frozen reporting functions still serialize all CSV/JSON values. Figure
    rendering still uses the unchanged savefig function and arguments, targeting
    BytesIO before the verified G write. Input reads are not intercepted.
    """
    from . import reporting, figures
    from matplotlib.figure import Figure
    root = safe(root)
    allowed = (root / "07_AGGREGATE", root / "08_FIGURES")
    owned = set()
    originals = reporting.write_json, reporting.write_csv, figures.write_json, Path.write_text, Figure.savefig

    def output_path(path):
        path = safe(path)
        if not any(parent in path.parents for parent in allowed):
            raise PermissionError("HARD_STOP_V3R_REPORT_WRITE_OUTSIDE_OUTPUT_ROOTS")
        return path

    def fixed_bytes(path, payload):
        path = output_path(path)
        if path not in owned:
            if path.exists():
                raise FileExistsError("Preserve existing report/figure output: " + str(path))
            _metadata_bytes(path, payload, append=False)
            owned.add(path)
        else:
            # The frozen renderer may refine PNG dpi up to four times. Only a
            # file created by this context can receive that same registered draw.
            def replay():
                with path.open("r+b", buffering=0) as stream:
                    stream.seek(0)
                    view = memoryview(payload)
                    while view:
                        count = stream.write(view)
                        if not count:
                            raise OSError(5, "Report output made no write progress")
                        view = view[count:]
                    stream.truncate()
                    stream.flush()
                    os.fsync(stream.fileno())
            retry_io(replay, source=path, destination=path, operation="v3r_owned_figure_refinement")
        if sha256_file(path) != hashlib.sha256(payload).hexdigest():
            raise RuntimeError("HARD_STOP_V3R_REPORT_OUTPUT_HASH")

    def captured(original, path, *args, **kwargs):
        path = output_path(path)
        open_original = Path.open
        payloads = []
        class Capture(io.StringIO):
            def close(self):
                if not self.closed:
                    payloads.append(self.getvalue().encode("utf-8"))
                super().close()
        def open_capture(candidate, mode="r", *open_args, **open_kwargs):
            if safe(candidate) == path and mode in ("x", "w"):
                if open_kwargs.get("encoding") not in (None, "utf-8", "UTF-8"):
                    raise ValueError("Unexpected report output encoding")
                return Capture(newline=open_kwargs.get("newline"))
            return open_original(candidate, mode, *open_args, **open_kwargs)
        Path.open = open_capture
        try:
            result = original(path, *args, **kwargs)
        finally:
            Path.open = open_original
        if len(payloads) != 1:
            raise RuntimeError("HARD_STOP_V3R_REPORT_SERIALIZATION_COUNT")
        fixed_bytes(path, payloads[0])
        return result

    def json_writer(path, value):
        return captured(originals[0], path, value)
    def csv_writer(path, rows, fields=None):
        return captured(originals[1], path, rows, fields=fields)
    def text_writer(path, *args, **kwargs):
        candidate = safe(path)
        if any(parent in candidate.parents for parent in allowed):
            return captured(originals[3], candidate, *args, **kwargs)
        return originals[3](path, *args, **kwargs)
    def savefig(figure, fname, *args, **kwargs):
        if not isinstance(fname, (str, os.PathLike)):
            return originals[4](figure, fname, *args, **kwargs)
        path = output_path(fname)
        extension = kwargs.get("format") or path.suffix.lstrip(".")
        if extension not in ("png", "pdf", "svg"):
            raise ValueError("Unregistered figure export format")
        buffer = io.BytesIO()
        options = {**kwargs, "format": extension}
        result = originals[4](figure, buffer, *args, **options)
        fixed_bytes(path, buffer.getvalue())
        return result
    reporting.write_json, reporting.write_csv, figures.write_json = json_writer, csv_writer, json_writer
    Path.write_text, Figure.savefig = text_writer, savefig
    try:
        yield
    finally:
        reporting.write_json, reporting.write_csv, figures.write_json, Path.write_text, Figure.savefig = originals


def tree_bytes(root):
    seen = set()
    size = 0
    for path in safe(root).rglob("*"):
        safe(path)
        if path.is_file():
            stat = path.stat()
            key = stat.st_dev, stat.st_ino
            if key not in seen:
                size += stat.st_size
                seen.add(key)
    return size


def df_available(mount):
    mount = safe(mount)
    if not os.path.ismount(mount):
        raise RuntimeError("HARD_STOP_V3R_REQUIRED_MOUNT_MISSING: " + str(mount))
    text = subprocess.check_output(["df", "--block-size=1", "--output=avail", str(mount)], text=True)
    return int(text.splitlines()[-1].strip())


class StorageGuard:
    def __init__(self, scratch, root, *, sample=None, sleeper=time.sleep):
        self.scratch, self.root = safe(scratch), safe(root)
        self.sample = sample or self.measure
        self.sleeper = sleeper
        self.sequence = len(list(self.root.glob("*.json"))) if self.root.exists() else 0
        self.lock = threading.Lock()
        self.on_pause = None

    def measure(self):
        return dict(e_available_bytes=df_available("/mnt/e"),
            g_available_bytes=df_available("/mnt/g"), scratch_bytes=tree_bytes(self.scratch))

    def checkpoint(self, batch, phase):
        values = self.sample()
        passed = (values["e_available_bytes"] >= E_MIN
            and values["g_available_bytes"] >= G_MIN
            and values["scratch_bytes"] <= SCRATCH_MAX)
        receipt = dict(**values, batch=batch, phase=phase, passed=passed,
            utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with self.lock:
            self.sequence += 1
            persist(self.root / f"{self.sequence:06d}.json", receipt)
        return receipt

    def before_batch(self, batch):
        for attempt in range(1, 4):
            receipt = self.checkpoint(batch, "PRE_BATCH_CHECK_" + str(attempt))
            if receipt["passed"]:
                return receipt
            print("V3R_STORAGE_PAUSED", batch, attempt, json.dumps(receipt), flush=True)
            if self.on_pause:
                self.on_pause(receipt)
            if attempt < 3:
                # Small sleeps let SIGTERM/new operator input remain responsive.
                for _ in range(10):
                    self.sleeper(60)
        raise RuntimeError("HARD_STOP_V3R_STORAGE_THREE_CONSECUTIVE_FAILURES")

    def summary(self):
        with self.lock:
            rows = [read_json(path) for path in sorted(self.root.glob("*.json"))]
        return dict(samples=len(rows), scratch_peak_bytes=max(r["scratch_bytes"] for r in rows),
            e_available_min_bytes=min(r["e_available_bytes"] for r in rows),
            g_available_min_bytes=min(r["g_available_bytes"] for r in rows),
            peak_scope="RECORDED_BOUNDARIES_NATIVE_EVALUATOR_AND_ARCHIVE") if rows else {"samples": 0}


def retained(relative, inventory=None):
    name = Path(relative).name
    uncompressed_name = name[:-3] if name.endswith(".gz") else name
    suffix = Path(uncompressed_name).suffix.lower()
    if (suffix == ".nav" or "STD" in name or name.startswith(("NAV_10HZ", "EVAL_NAV", "KF_GINS_IMU_ERR"))):
        return False
    if suffix in (".strace", ".log") or name.startswith("strace"):
        return False
    return inventory is None or str(relative) + ".gz" not in inventory


class ReleaseJournal:
    """One append-only file per slot, retaining fsynced per-file checkpoints."""
    def __init__(self, path, inventory, *, action="DELETE_VERIFIED_SCRATCH_FILE"):
        self.path = safe(path)
        self.inventory = inventory
        self.action = action
        self.names = list(inventory)
        self.states = {}
        self.count = 0
        payload = b""
        if self.path.exists():
            payload, _ = retry_io(self.path.read_bytes, source=self.path,
                destination=self.path, operation="v3r_release_journal_read")
        self.offset = len(payload)
        if payload and not payload.endswith(b"\n"):
            raise RuntimeError("HARD_STOP_V3R_RELEASE_JOURNAL_UNTERMINATED_RECORD")
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate journal key")
                result[key] = value
            return result
        for line in payload.splitlines():
            try:
                row = json.loads(line, object_pairs_hook=unique_object)
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError("HARD_STOP_V3R_RELEASE_JOURNAL_SCHEMA") from exc
            self._admit(row)

    def expected(self):
        if self.count >= 2 * len(self.names):
            raise RuntimeError("HARD_STOP_V3R_RELEASE_JOURNAL_EXCESS_RECORD")
        relative = self.names[self.count // 2]
        return dict(relative_path=relative, sha256=self.inventory[relative]["source_sha256"],
            action=self.action, event="INTENT" if self.count % 2 == 0 else "DONE")

    def _admit(self, row):
        if row != self.expected():
            raise RuntimeError("HARD_STOP_V3R_RELEASE_JOURNAL_SCOPE_OR_ORDER")
        self.states[row["relative_path"]] = row["event"]
        self.count += 1

    def append(self, relative, event):
        row = dict(relative_path=relative, sha256=self.inventory[relative]["source_sha256"],
            action=self.action, event=event)
        if row != self.expected():
            raise RuntimeError("HARD_STOP_V3R_RELEASE_JOURNAL_SCOPE_OR_ORDER")
        payload = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
        retry_io(lambda: self.path.parent.mkdir(parents=True, exist_ok=True), source=self.path,
            destination=self.path, operation="v3r_release_journal_parent")
        stream, _ = retry_io(lambda: self.path.open("a+b"), source=self.path,
            destination=self.path, operation="v3r_release_journal_open")
        with stream:
            retry_io(lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_EX), source=self.path,
                destination=self.path, operation="v3r_release_journal_lock")
            if os.fstat(stream.fileno()).st_size != self.offset:
                raise RuntimeError("HARD_STOP_V3R_RELEASE_JOURNAL_CHANGED_OUTSIDE_OWNED_APPEND")
            # The helper captures this same offset and retries only this row's
            # bytes; fsync completes before either unlink or the next file.
            _metadata_bytes(self.path, payload, append=True)
            if os.fstat(stream.fileno()).st_size != self.offset + len(payload):
                raise RuntimeError("HARD_STOP_V3R_RELEASE_JOURNAL_APPEND_SIZE")
        self.offset += len(payload)
        self._admit(row)


def _gzip_source_identity(path, expected_sha256, expected_size):
    digest, size = hashlib.sha256(), 0
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
            size += len(block)
    if digest.hexdigest() != expected_sha256 or size != expected_size:
        raise RuntimeError("HARD_STOP_V3R_GZIP_SOURCE_IDENTITY")


def _gzip_copy(source, target, item, slot):
    """Deterministic streaming gzip with bounded memory and existing I/O retries."""
    attempted = False
    def copy():
        nonlocal attempted
        mode = "wb" if attempted else "xb"
        attempted = True
        source_path, target_path = safe(source), safe(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_digest, storage_digest = hashlib.sha256(), hashlib.sha256()
        source_size = storage_size = 0
        with source_path.open("rb") as reader, target_path.open(mode, buffering=0) as output:
            class DigestWriter:
                def write(self, payload):
                    nonlocal storage_size
                    _write_all(output, payload)
                    storage_digest.update(payload)
                    storage_size += len(payload)
                    return len(payload)
                def flush(self):
                    output.flush()
            with gzip.GzipFile(filename="", mode="wb", fileobj=DigestWriter(),
                    compresslevel=6, mtime=0) as compressed:
                for block in iter(lambda: reader.read(8 << 20), b""):
                    source_digest.update(block)
                    source_size += len(block)
                    compressed.write(block)
            output.flush()
            os.fsync(output.fileno())
        if source_digest.hexdigest() != item["source_sha256"] or source_size != item["source_size_bytes"]:
            raise RuntimeError("HARD_STOP_V3R_GZIP_SOURCE_CHANGED")
        digest = storage_digest.hexdigest()
        if sha256_file(target_path) != digest or target_path.stat().st_size != storage_size:
            raise RuntimeError("HARD_STOP_V3R_GZIP_STORAGE_HASH")
        return dict(sha256=digest, size_bytes=storage_size)
    result, _ = retry_io(copy, source=source, destination=target, operation="v3r_gzip_copy", staging_root=slot)
    return result


def archive_compressed_csv(source, target, item, slot, previous=None):
    """Reuse a sealed G gzip without reopening a source already journal-released."""
    if previous is not None:
        identity = {k: value for k, value in item.items() if k not in ("sha256", "size_bytes")}
        if {k: value for k, value in previous.items() if k not in ("sha256", "size_bytes")} != identity:
            raise RuntimeError("HARD_STOP_V3R_GZIP_RECEIPT_IDENTITY")
        runtime.verify_pin(dict(path=str(target), sha256=previous["sha256"]), cached=False)
        if target.stat().st_size != previous["size_bytes"]:
            raise RuntimeError("HARD_STOP_V3R_GZIP_RECEIPT_SIZE")
        return dict(sha256=previous["sha256"], size_bytes=previous["size_bytes"])
    runtime.verify_pin(dict(path=str(source), sha256=item["source_sha256"]), cached=False)
    if target.exists():
        try:
            _gzip_source_identity(target, item["source_sha256"], item["source_size_bytes"])
        except (EOFError, gzip.BadGzipFile, zlib.error):
            persist(slot / "COPY_REPLAY" / (hashlib.sha256(item["storage_relative_path"].encode()).hexdigest() + ".json"),
                dict(relative_path=item["storage_relative_path"], action="REPLACE_INCOMPLETE_OWNED_GZIP",
                    expected_source_sha256=item["source_sha256"]))
            retry_io(lambda: target.unlink(missing_ok=True), source=source, destination=target,
                operation="v3r_partial_gzip_release")
        else:
            return dict(sha256=sha256_file(target), size_bytes=target.stat().st_size)
    return _gzip_copy(source, target, item, slot)


def compact_archive(source, destination, *, scratch_root, batch, retention=None):
    """Copy selected sealed files through the existing retry wrapper, then release.

    All source hashes are recorded, including omitted NAV/STD/EVAL_NAV/logs.
    The original OUTPUT_SEAL is retained literally; discarded members are never
    presented as archived members. Required plot series and Truth stay.
    """
    if retention is not None:
        validate_retention_decision(retention)
    scratch = safe(scratch_root)
    source, destination = inside(source, scratch), safe(destination)
    allowed = (scratch / "03_NATIVE", scratch / "04_EVALUATION",
        scratch / CONTINUATION / "03_NATIVE", scratch / CONTINUATION / "04_EVALUATION")
    if not any(root in source.parents for root in allowed):
        raise PermissionError("HARD_STOP_V3R_COMPACT_SOURCE_SCOPE")
    stage = next((p for p in destination.parents if p.name == STAGE and p.parent.name == "stages"), None)
    ledger_base = stage / "00_CONTROL" / CONTINUATION if stage else destination.parent
    slot = ledger_base / "ARCHIVE_SLOTS" / hashlib.sha256(str(destination).encode()).hexdigest()
    plan_path = slot / "COMPACT_PLAN.json"
    if plan_path.exists():
        plan = read_json(plan_path)
        if (plan["source_root"] != str(source) or plan["archive_root"] != str(destination)
                or plan["batch"] != batch or plan.get("retention") != retention):
            raise RuntimeError("HARD_STOP_V3R_ARCHIVE_PLAN_CHANGED")
        inventory = plan["files"]
    else:
        if destination.exists():
            raise FileExistsError("Existing archive without owned copy plan")
        inventory = {}
        for path in sorted(source.rglob("*")):
            safe(path)
            if path.is_file():
                rel = path.relative_to(source).as_posix()
                inventory[rel] = dict(source_sha256=sha256_file(path),
                    source_size_bytes=path.stat().st_size)
        if "OUTPUT_SEAL.json" not in inventory:
            raise RuntimeError("HARD_STOP_V3R_COMPACT_WITHOUT_SEAL")
        seal = read_json(source / "OUTPUT_SEAL.json")
        for rel, digest in seal["files"].items():
            if rel not in inventory or inventory[rel]["source_sha256"] != digest:
                raise RuntimeError("HARD_STOP_V3R_COMPACT_SOURCE_SEAL")
        persist(plan_path, dict(source_root=str(source), archive_root=str(destination), batch=batch,
            files=inventory, retention=retention))
    def keep(rel):
        return retained(rel) and not (retention is not None
            and retention["retain_error_series"] is False and error_series_member(rel))
    previous_receipt = read_json(destination / "ARCHIVE_RECEIPT.json") if (destination / "ARCHIVE_RECEIPT.json").exists() else None
    files = {}
    for rel, item in inventory.items():
        if not keep(rel):
            continue
        existing_gzip = rel + ".gz" in inventory
        generated_gzip = (not existing_gzip and Path(rel).suffix.lower() == ".csv"
            and item["source_size_bytes"] >= 1_000_000)
        compressed = existing_gzip or generated_gzip
        stored = rel + ".gz" if compressed else rel
        storage_item = inventory.get(stored, {})
        files[rel] = {**item, "storage_relative_path": stored,
            "sha256": storage_item.get("source_sha256"), "size_bytes": storage_item.get("source_size_bytes"),
            "compression": "gzip" if compressed else "identity"}
        if generated_gzip:
            files[rel]["compression_profile"] = dict(compresslevel=6, filename="", mtime=0)
    for rel, item in files.items():
        stored = item["storage_relative_path"]
        target = inside(destination / stored, destination)
        if stored not in inventory:
            previous = previous_receipt["files"].get(rel) if previous_receipt else None
            item.update(archive_compressed_csv(inside(source / rel, source), target, item, slot, previous))
            continue
        path = inside(source / stored, source)
        if target.exists() and sha256_file(target) == item["sha256"]:
            continue
        runtime.verify_pin(dict(path=str(path), sha256=item["sha256"]), cached=False)
        if target.exists():
            # The durable exact-member plan precedes every destination creation.
            # Only an incomplete member owned by that plan can be replayed.
            persist(slot / "COPY_REPLAY" / (hashlib.sha256(rel.encode()).hexdigest() + ".json"),
                dict(relative_path=rel, action="REPLACE_INCOMPLETE_OWNED_COPY", expected_sha256=item["sha256"]))
            retry_io(lambda: target.unlink(missing_ok=True), source=path, destination=target, operation="v3r_partial_copy_release")
        stream_copy(path, target, expected_sha256=item["sha256"],
            expected_size_bytes=item["size_bytes"], staging_root=slot)
        runtime.verify_pin(dict(path=str(target), sha256=item["sha256"]), cached=False)
    for item in files.values():
        if item["compression"] == "gzip":
            _gzip_source_identity(destination / item["storage_relative_path"],
                item["source_sha256"], item["source_size_bytes"])
    receipt = dict(status="ARCHIVE_VERIFIED", archive_mode="COMPACT_HASH_AND_EVALUATION",
        data_mode="execution_metadata_only", synthetic_data_used=False, semisynthetic_data_used=False,
        source_root=str(source), archive_root=str(destination), files=files,
        discarded_payloads={rel: item for rel, item in inventory.items() if not keep(rel)},
        retention=retention,
        native_and_evaluator_calls_in_archiving=0)
    persist(destination / "ARCHIVE_RECEIPT.json", receipt)
    # The exact recorded inventory is released only after every retained member
    # and the durable G receipt pass. No glob-driven deletion and no rmtree.
    journal = ReleaseJournal(slot / "RELEASE_JOURNAL.jsonl", inventory)
    released = []
    for rel, item in inventory.items():
        path = inside(source / rel, source)
        state = journal.states.get(rel)
        if state == "DONE":
            if path.exists():
                raise RuntimeError("HARD_STOP_V3R_RELEASED_SOURCE_REAPPEARED")
            released.append(dict(relative_path=rel, sha256=item["source_sha256"]))
            continue
        if path.exists():
            if sha256_file(path) != item["source_sha256"]:
                raise RuntimeError("HARD_STOP_V3R_RELEASE_SOURCE_CHANGED")
            if state is None:
                journal.append(rel, "INTENT")
            retry_io(lambda: path.unlink(missing_ok=True), source=path, destination=destination,
                operation="v3r_exact_scratch_release")
        elif state != "INTENT":
            raise RuntimeError("HARD_STOP_V3R_SOURCE_MISSING_WITHOUT_RELEASE_INTENT")
        journal.append(rel, "DONE")
        released.append(dict(relative_path=rel, sha256=item["source_sha256"]))
    persist(destination / "COMPACT_RELEASE.json", dict(status="PASS", source_root=str(source), files=released,
        release_journal=dict(path=str(journal.path), sha256=sha256_file(journal.path), records=journal.count)))
    return receipt


def native_archived(record, receipt):
    return {**record, "archive_output_root": receipt["archive_root"],
        "archive_receipt": str(Path(receipt["archive_root"]) / "ARCHIVE_RECEIPT.json")}


def evaluation_archived(payload, receipt):
    return {**payload, "archive_output_root": receipt["archive_root"],
        "archive_receipt": str(Path(receipt["archive_root"]) / "ARCHIVE_RECEIPT.json"),
        "resolved_error_series_source": str(Path(receipt["archive_root"]) / "FROZEN_EVALUATOR")}


def apply_existing_retention(payload, *, archive, control, decision, reconciliation_pin, evaluation_pin):
    """Append a storage overlay for one B2-admitted evaluator; never rewrite B2.

    Plans contain deduplicated physical members. Verification precedes every
    first delete; the journal admits recovery only after a durable INTENT.
    """
    validate_retention_decision(decision)
    if decision["retain_error_series"]:
        return payload
    archive, control = safe(archive), safe(control)
    inside(control, archive / "00_CONTROL")
    reconciliation = pinned_json(reconciliation_pin, archive)
    if reconciliation.get("status") != "PASS_ARCHIVE_RECONCILIATION":
        raise RuntimeError("HARD_STOP_V3R_RETENTION_RECONCILIATION_NOT_COMPLETE")
    rid = payload["row"]["run_id"]
    version = payload["row"]["evaluator_contract"].removeprefix("evaluator_contract_")
    if rid != decision["run_id"] or decision["domain"] != "CORE" or version not in VERSIONS:
        raise RuntimeError("HARD_STOP_V3R_RETENTION_EXISTING_SLOT_IDENTITY")
    admissions = [item for item in reconciliation["reused_runs"] if item["run_id"] == rid]
    if (len(admissions) != 1 or admissions[0]["evaluations"].get(version) != evaluation_pin
            or pinned_json(evaluation_pin, archive) != payload):
        raise RuntimeError("HARD_STOP_V3R_RETENTION_REUSE_PIN_NOT_ADMITTED")
    runtime.verify_pin(decision["policy"], cached=False)
    root = archive / "04_EVALUATION" / rid / version
    original_path = root / "ARCHIVE_RECEIPT.json"
    if payload.get("archive_output_root") != str(root) or payload.get("archive_receipt") != str(original_path):
        raise RuntimeError("HARD_STOP_V3R_RETENTION_ORIGINAL_ARCHIVE_SCOPE")
    original = read_json(original_path)
    if original.get("status") != "ARCHIVE_VERIFIED" or original.get("archive_root") != str(root):
        raise RuntimeError("HARD_STOP_V3R_RETENTION_ORIGINAL_RECEIPT")
    seal = read_json(root / "OUTPUT_SEAL.json")
    runtime.verify_pin(dict(path=str(root / "EVALUATION_RESULT.json"),
        sha256=seal["files"]["EVALUATION_RESULT.json"]), cached=False)
    drop = {name: item for name, item in original["files"].items() if error_series_member(name)}
    inventory = {}
    for name, item in sorted(drop.items()):
        relative = item["storage_relative_path"]
        inside(root / relative, root)
        if (not error_series_member(relative) or item["source_sha256"] != seal["files"].get(name)
                or item["compression"] not in ("identity", "gzip", "gz")):
            raise RuntimeError("HARD_STOP_V3R_RETENTION_MEMBER_IDENTITY")
        entry = dict(source_sha256=item["sha256"], source_size_bytes=item["size_bytes"])
        if relative in inventory and any(inventory[relative][k] != v for k, v in entry.items()):
            raise RuntimeError("HARD_STOP_V3R_RETENTION_PHYSICAL_ALIAS_DIFFERS")
        inventory.setdefault(relative, {**entry, "logical_members": {}})["logical_members"][name] = item
    if any(item["storage_relative_path"] in inventory for name, item in original["files"].items() if name not in drop):
        raise RuntimeError("HARD_STOP_V3R_RETENTION_SHARED_WITH_RETAINED_MEMBER")
    slot = control / "RETENTION_OVERLAYS" / rid / version
    original_pin = dict(path=str(original_path), sha256=sha256_file(original_path))
    plan = dict(schema="V3R_EXISTING_RETENTION_PLAN_V1", archive_root=str(root),
        decision=decision, reconciliation=reconciliation_pin, evaluation_record=evaluation_pin,
        original_receipt=original_pin,
        original_seal=dict(path=str(root / "OUTPUT_SEAL.json"), sha256=sha256_file(root / "OUTPUT_SEAL.json")),
        files=inventory)
    plan_path = slot / "RETENTION_PLAN.json"
    if plan_path.exists() and read_json(plan_path) != plan:
        raise RuntimeError("HARD_STOP_V3R_RETENTION_PLAN_CHANGED")
    journal = ReleaseJournal(slot / "RELEASE_JOURNAL.jsonl", inventory,
        action="DELETE_VERIFIED_G_ERROR_SERIES")
    if journal.count and not plan_path.exists():
        raise RuntimeError("HARD_STOP_V3R_RETENTION_JOURNAL_WITHOUT_PLAN")

    def verify_member(relative, item):
        path = inside(root / relative, root)
        runtime.verify_pin(dict(path=str(path), sha256=item["source_sha256"]), cached=False)
        if path.stat().st_size != item["source_size_bytes"]:
            raise RuntimeError("HARD_STOP_V3R_RETENTION_STORAGE_SIZE")
        for logical in item["logical_members"].values():
            if logical["compression"] in ("gzip", "gz"):
                _gzip_source_identity(path, logical["source_sha256"], logical["source_size_bytes"])
            elif logical["source_sha256"] != item["source_sha256"]:
                raise RuntimeError("HARD_STOP_V3R_RETENTION_SOURCE_HASH")
        return path

    # Check every still-present candidate before deleting any candidate. Missing
    # files without this exact plan and a prior INTENT are never inferred safe.
    for relative, item in inventory.items():
        path = inside(root / relative, root)
        state = journal.states.get(relative)
        if path.exists():
            if state == "DONE":
                raise RuntimeError("HARD_STOP_V3R_RETENTION_DELETED_MEMBER_REAPPEARED")
            verify_member(relative, item)
        elif state not in ("INTENT", "DONE") or not plan_path.exists():
            raise RuntimeError("HARD_STOP_V3R_RETENTION_MISSING_WITHOUT_INTENT")
    persist(plan_path, plan)
    for relative, item in inventory.items():
        if journal.states.get(relative) == "DONE":
            continue
        path = inside(root / relative, root)
        if path.exists():
            verify_member(relative, item)
            if journal.states.get(relative) is None:
                journal.append(relative, "INTENT")
            retry_io(lambda: path.unlink(missing_ok=True), source=path,
                destination=slot, operation="v3r_exact_g_error_series_release")
        elif journal.states.get(relative) != "INTENT":
            raise RuntimeError("HARD_STOP_V3R_RETENTION_MISSING_WITHOUT_INTENT")
        journal.append(relative, "DONE")
    overlay = {**original, "files": {name: item for name, item in original["files"].items() if name not in drop},
        "discarded_payloads": {**original.get("discarded_payloads", {}), **drop},
        "retention": decision, "original_archive_receipt": original_pin,
        "storage_overlay_only": True, "native_and_evaluator_calls_in_archiving": 0,
        "data_mode": "storage_provenance_only", "synthetic_data_used": False, "semisynthetic_data_used": False}
    overlay_path = slot / "ARCHIVE_RECEIPT.json"
    persist(overlay_path, overlay)
    derived = {**payload, "archive_receipt": str(overlay_path)}
    persist(slot / "DERIVED_EVALUATION_RECORD.json", derived)
    persist(slot / "RETENTION_COMPLETE.json", dict(status="PASS_EXACT_ERROR_SERIES_RETENTION",
        physical_files_deleted=len(inventory), logical_members_omitted=len(drop),
        deleted_bytes=sum(item["source_size_bytes"] for item in inventory.values()),
        original_records_rewritten=False, original_archive_receipt=original_pin,
        release_journal=dict(path=str(journal.path), sha256=sha256_file(journal.path) if inventory else None,
            records=journal.count), overlay=dict(path=str(overlay_path), sha256=sha256_file(overlay_path))))
    return derived


def check_recovery_hashes(record, admission):
    for role in ("nav", "std"):
        expected = admission.get("expected_" + role + "_sha256")
        if expected and record.get(role + "_sha256") != expected:
            raise RuntimeError("HARD_STOP_V3R_RECOVERY_" + role.upper() + "_HASH_MISMATCH")


def original_reservations(pin, kind):
    path = runtime.verify_pin(pin, cached=False)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids = [row["run_id"] for row in rows]
    if len(ids) != len(set(ids)) or any(row["kind"] != kind for row in rows):
        raise RuntimeError("HARD_STOP_V3R_ORIGINAL_RESERVATION_SCOPE")
    return set(ids)


def admission_sets(manifest, allowed, reserved):
    result = {}
    all_seen = set()
    for field in ("reused_runs", "identity_native_only", "recovery_runs"):
        rows = manifest.get(field, [])
        indexed = {row["run_id"]: row for row in rows}
        if len(indexed) != len(rows) or set(indexed) - set(allowed) or all_seen.intersection(indexed):
            raise RuntimeError("HARD_STOP_V3R_RECONCILIATION_COVERAGE")
        all_seen.update(indexed)
        result[field] = indexed
    if reserved - all_seen:
        raise RuntimeError("HARD_STOP_V3R_CONSUMED_SLOT_WITHOUT_RECONCILIATION")
    if set(result["recovery_runs"]) - reserved:
        raise RuntimeError("HARD_STOP_V3R_RECOVERY_NOT_ORIGINALLY_RESERVED")
    return result


def parallel_bounded(items, function):
    outcomes, first = [], None
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(function, item): item for item in items}
        for future in as_completed(futures):
            if future.cancelled():
                continue
            try:
                outcomes.append(future.result())
            except Exception as exc:
                if first is None:
                    first = exc
                    for pending in futures:
                        pending.cancel()
    if first is not None:
        raise first
    return outcomes


def progress_counts(specs, native_ids, evaluator_ids):
    """5410 is the requested CORE non-F01 view; total science queue is 6468."""
    result = {}
    groups = {"core_non_f01": lambda s: s["domain"] == "CORE" and s["method_id"] != "F01",
        "core_f01": lambda s: s["domain"] == "CORE" and s["method_id"] == "F01",
        "f01_all_domains": lambda s: s["method_id"] == "F01",
        "three_sequence_unique_extra": lambda s: s["domain"] == "SEQUENCE",
        "a1_a2_all_methods": lambda s: s["domain"] == "ADDENDUM",
        "total_queue": lambda s: True}
    for name, predicate in groups.items():
        ids = {s["run_id"] for s in specs if predicate(s)}
        slots = {rid + "__" + v for rid in ids for v in VERSIONS}
        result[name] = dict(solver_done=len(ids & native_ids), solver_total=len(ids),
            evaluator_done=len(slots & evaluator_ids), evaluator_total=2 * len(ids))
    return result


class Heartbeat:
    """60-second G-only operational snapshots; evidence records remain append-only."""
    def __init__(self, control, guard, specs, total_batches, original_batches=0):
        self.control, self.guard, self.specs = safe(control), guard, specs
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.native_ids, self.eval_ids, self.failed_native, self.failed_eval = set(), set(), set(), set()
        self.phase, self.batch, self.completed = "GATES", 0, original_batches
        self.completed_continuation_batches = set()
        self.total_batches = total_batches
        self.started, self.durations = None, []
        self.pause, self.hardstop, self.error = None, None, None
        self.thread = None
        self.capacity = None

    def native(self, record):
        with self.lock:
            self.native_ids.add(record["run_id"])
            if record["status"] != "COMPLETED":
                self.failed_native.add(record["run_id"])

    def evaluation(self, payload):
        row = payload["row"]
        key = row["run_id"] + "__" + row["evaluator_contract"].removeprefix("evaluator_contract_")
        with self.lock:
            self.eval_ids.add(key)
            if row.get("evaluation_status") == "UNAVAILABLE_EVALUATION_FAILED":
                self.failed_eval.add(key)

    def start_batch(self, number):
        with self.lock:
            self.phase, self.batch, self.started = "MATRIX", number, time.time()
        self.flush()

    def end_batch(self):
        with self.lock:
            self.completed += 1
            self.completed_continuation_batches.add(self.batch)
            if self.started is not None:
                self.durations.append(time.time() - self.started)
        self.flush()

    def paused(self, receipt):
        with self.lock:
            self.pause = receipt
        self.flush()

    @staticmethod
    def _replace_operational(path, payload):
        # Mutable STATE/PROGRESS are explicitly user-requested operational views.
        # Their append-only source snapshots are kept beside them, never renamed.
        def write():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if path.read_bytes() != payload:
                raise RuntimeError("HARD_STOP_V3R_PROGRESS_WRITE_HASH")
        retry_io(write, source=path, destination=path, operation="v3r_operational_progress")

    def flush(self):
        with self.lock:
            resource = self.guard.checkpoint(self.batch, "HEARTBEAT_" + self.phase)
            average = sum(self.durations[-10:]) / len(self.durations[-10:]) if self.durations else None
            eta = None if average is None else average * (self.total_batches - self.completed)
            state = dict(phase=self.phase, updated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                status="HARD_STOP" if self.hardstop else "ACTIVE",
                progress=progress_counts(self.specs, self.native_ids, self.eval_ids),
                completed_batches=self.completed, total_batches=self.total_batches,
                current_continuation_batch=self.batch, batch_start_unix_s=self.started,
                batch_start_utc=None if self.started is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started)),
                last_ten_batches_mean_seconds=average,
                eta_seconds=eta,
                estimated_completion_utc=None if eta is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + eta)),
                native_failure_count=len(self.failed_native), evaluator_failure_count=len(self.failed_eval),
                resources=resource, latest_pause=self.pause, latest_hard_stop=self.hardstop,
                capacity_forecast=self.capacity,
                heartbeat_interval_seconds=60, visual_review_status="PENDING_ACTUAL_RASTER_REVIEW")
            snapshot = self.control / "HEARTBEATS" / (str(time.time_ns()) + ".json")
            persist(snapshot, state)
            main, total = state["progress"]["core_non_f01"], state["progress"]["total_queue"]
            capacity = self.capacity or {}
            native_sample = capacity.get("samples", {}).get("native", {})
            evaluator_sample = capacity.get("samples", {}).get("evaluator", {})
            text = (f"phase={self.phase} status={state['status']} updated={state['updated_utc']}\n"
                f"core non-F01 solver={main['solver_done']}/{main['solver_total']} "
                f"eval={main['evaluator_done']}/{main['evaluator_total']}\n"
                f"total queue solver={total['solver_done']}/{total['solver_total']} "
                f"eval={total['evaluator_done']}/{total['evaluator_total']}\n"
                f"batches={self.completed}/{self.total_batches} batch_start_utc={state['batch_start_utc']} "
                f"last10_mean_s={average} eta_s={state['eta_seconds']} estimated_completion_utc={state['estimated_completion_utc']}\n"
                f"failures native={len(self.failed_native)} evaluator={len(self.failed_eval)}\n"
                f"scratch_bytes={resource['scratch_bytes']} E_free={resource['e_available_bytes']} G_free={resource['g_available_bytes']}\n"
                f"capacity sample means bytes: native allocated={native_sample.get('mean_allocated_bytes')} "
                f"apparent={native_sample.get('mean_apparent_bytes')}; evaluator allocated={evaluator_sample.get('mean_allocated_bytes')} "
                f"apparent={evaluator_sample.get('mean_apparent_bytes')}\n"
                f"capacity baseline MATRIX+AGGREGATE bytes: allocated={capacity.get('matrix_aggregate_remaining_allocated_bytes')} "
                f"apparent={capacity.get('matrix_aggregate_remaining_apparent_bytes')}\n"
                f"capacity conditional MATRIX+AGGREGATE bytes: allocated={capacity.get('conditional_matrix_aggregate_remaining_allocated_bytes')} "
                f"apparent={capacity.get('conditional_matrix_aggregate_remaining_apparent_bytes')}\n"
                f"capacity G free bytes: at_forecast={capacity.get('g_available_bytes_at_forecast')} "
                f"current={resource['g_available_bytes']} threshold60pct={capacity.get('threshold_bytes')}\n"
                f"capacity_forecast={json.dumps(self.capacity, ensure_ascii=False, sort_keys=True)}\n"
                f"latest_pause={json.dumps(self.pause)} latest_hard_stop={json.dumps(self.hardstop)}\n"
                f"other_groups={json.dumps({k: v for k, v in state['progress'].items() if k not in ('core_non_f01', 'total_queue')})}\n")
            self._replace_operational(self.control / "STATE.json", (json.dumps(state, indent=2) + "\n").encode())
            self._replace_operational(self.control / "PROGRESS.txt", text.encode())
            return state

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.flush()
        def watch():
            while not self.stop_event.wait(60):
                try:
                    self.flush()
                except Exception as exc:
                    self.error = exc
                    return
        self.thread = threading.Thread(target=watch, daemon=True, name="v3r-g-heartbeat")
        self.thread.start()

    def check(self):
        if self.error is not None:
            raise RuntimeError("HARD_STOP_V3R_HEARTBEAT_FAILED") from self.error

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)


class ResumeContext:
    def __init__(self, local_config, contract_path, science_freeze, continuation_commit,
                 reconciliation, reconciliation_sha256, capacity_forecast_sha256,
                 purge_prime_receipt, purge_prime_sha256):
        self.storage_roots_validated = False
        self.local = safe(local_config)
        self.paths = yaml.safe_load(self.local.read_text())["paths"]
        self.code, self.clean = safe(self.paths["code_root"]), safe(self.paths["clean_root"])
        self.scratch = safe(self.paths["protocol_v3_scratch"])
        self.archive = safe(self.clean / "stages" / STAGE)
        if (self.scratch.name != STAGE or self.scratch.parent.name != "LegSA-GINS-SCRATCH"
                or str(self.scratch).startswith("/mnt/") or Path("/mnt/g") not in self.archive.parents):
            raise PermissionError("HARD_STOP_V3R_STORAGE_ROOTS")
        if self.archive.name != STAGE or not self.archive.is_dir():
            raise RuntimeError("HARD_STOP_V3R_EXISTING_G_STAGE_REQUIRED")
        self.control = self.archive / "00_CONTROL" / CONTINUATION
        self.storage_roots_validated = True
        if (self.control / "HARD_STOP.json").exists():
            raise RuntimeError("HARD_STOP_V3R_PERSISTED_CONTINUATION_STOP")
        # Native/evaluator children already pin their own output directories.
        # Parent report caches and temporary data must stay in the same scratch.
        cache = self.scratch / CONTINUATION / "CACHE"
        for key, part in (("MPLCONFIGDIR", "matplotlib"), ("XDG_CACHE_HOME", "xdg"),
                          ("TMPDIR", "tmp"), ("TMP", "tmp"), ("TEMP", "tmp")):
            os.environ[key] = str(cache / part)
        os.environ["MPLBACKEND"] = "Agg"
        self.work = self.scratch / CONTINUATION
        self.code_freeze = science_freeze
        self.continuation_commit = continuation_commit
        original = read_json(self.scratch / "00_PREREGISTRATION/EXECUTION_FREEZE.json")
        self.freeze = continuation_freeze(self.code, science_freeze, continuation_commit, original)
        # Explicitly approved storage-only hook. The scientific native/evaluator
        # function objects and all frozen source files remain unmodified.
        runtime.reserve_slot = reserve_slot_with_retry
        for part in ("matplotlib", "xdg", "tmp"):
            (cache / part).mkdir(parents=True, exist_ok=True)
        import tempfile
        tempfile.tempdir = str(cache / "tmp")
        self.contract_path = safe(contract_path)
        self.contract = _resolve(yaml.safe_load(self.contract_path.read_text()), self.paths)
        self.contract["config_hash"] = sha256_file(self.contract_path)
        self.reconciliation_pin = dict(path=str(reconciliation), sha256=reconciliation_sha256)
        self.reconciliation = pinned_json(self.reconciliation_pin, self.archive)
        if (self.reconciliation.get("status") != "PASS_ARCHIVE_RECONCILIATION"
                or self.reconciliation.get("science_freeze") != science_freeze):
            raise RuntimeError("HARD_STOP_V3R_RECONCILIATION_REQUIRED")
        for pin in self.reconciliation.get("files", []):
            runtime.verify_pin(pin, cached=False)
        self.contexts = {s: load_sequence_paths(s, local_config=self.local,
            registry_path=self.code / REGISTRY, calibrated_contract_path=self.code / CALIBRATED_CONTRACT)
            for s in ("BY2", "BY2H", "BY2O")}
        registry = self.scratch / "00_PREREGISTRATION/REGISTRY.json"
        seal = read_json(registry.parent / "REGISTRY_FILE_SEAL.json")
        self.specs = pinned_json(dict(path=str(registry), sha256=seal["sha256"]))
        validate_registry(self.specs)
        self.purge_prime = purge_prime_admission(self.archive,
            dict(path=str(purge_prime_receipt), sha256=purge_prime_sha256))
        self.retention, self.capacity = capacity_admission(self.archive / "00_CONTROL",
            capacity_forecast_sha256, seal["sha256"], self.specs)
        self.freeze.update(purge_prime=self.purge_prime, capacity_forecast=self.capacity)
        self.allowed = [s["run_id"] for s in self.specs]
        self.eval_allowed = [rid + "__" + v for rid in self.allowed for v in VERSIONS]
        ledger_pins = self.reconciliation["original_ledger_pins"]
        self.original_native = original_reservations(ledger_pins["native"], "native")
        self.original_eval = original_reservations(ledger_pins["evaluator"], "evaluator")
        if self.original_native - set(self.allowed) or self.original_eval - set(self.eval_allowed):
            raise RuntimeError("HARD_STOP_V3R_ORIGINAL_SLOT_NOT_REGISTERED")
        groups = admission_sets(self.reconciliation, self.allowed, self.original_native)
        self.reused = groups["reused_runs"]
        self.identity = groups["identity_native_only"]
        self.recovery = groups["recovery_runs"]
        self.binary = runtime.verify_pin(self.contract["frozen"]["executable"], cached=False)
        self.evaluator = runtime.verify_pin(self.contract["frozen"]["evaluator"], cached=False)
        if (self.contract["frozen"]["executable"]["sha256"] != runtime.BINARY_SHA256
                or self.contract["frozen"]["evaluator"]["sha256"] != runtime.EVALUATOR_SHA256):
            raise RuntimeError("HARD_STOP_V3R_BINARY_EVALUATOR_REGISTRATION")
        self.providers = read_json(self.scratch / "02_PROVIDERS/PROVIDER_REGISTRY.json")
        self.admissions = {rid: read_json(self.scratch / "02_CONFIGS" / rid / "CONFIG_ADMISSION.json") for rid in self.allowed}
        self.gates = read_json(self.scratch / "IDENTITY_GATES.json")["gates"]
        if set(self.gates) != {"2a", "2b", "2c", "2d", "2e"} or any(g["status"] != "PASS" for g in self.gates.values()):
            raise RuntimeError("HARD_STOP_V3R_IDENTITY_GATE")
        identity_ids = {row["run_id"] for gate in ("2d", "2e") for row in self.gates[gate]["comparisons"]}
        if len(identity_ids) != 4 or not identity_ids <= set(self.reused) | set(self.identity):
            raise RuntimeError("HARD_STOP_V3R_IDENTITY_MUST_REUSE")
        persist(self.control / "CONTINUATION_FREEZE.json", self.freeze)
        persist(self.control / "RECONCILIATION_PIN.json", dict(path=str(reconciliation), sha256=reconciliation_sha256))
        self.guard = StorageGuard(self.scratch, self.control / "STORAGE")
        original_batches = self.reconciliation.get("completed_batch_count", len(self.reused) // 64)
        self.progress = Heartbeat(self.archive / "00_CONTROL", self.guard, self.specs,
            original_batches + (len(self.specs) - len(self.reused) + BATCH_SIZE - 1) // BATCH_SIZE,
            original_batches=original_batches)
        self.progress.capacity = self.capacity
        self.guard.on_pause = self.progress.paused
        Context._install_guard(self)
        self._seed_admitted_progress()
        self.progress.start()
        self._verify_admissions()

    def _seed_admitted_progress(self):
        """Read pinned metadata before the first heartbeat; never archive or run."""
        def admit(record, payloads, rid):
            if (record.get("run_id") != rid or record.get("code_commit") != self.code_freeze
                    or record.get("status") not in ("COMPLETED", "ALGORITHM_FAILURE_DIVERGED",
                        "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT")):
                raise RuntimeError("HARD_STOP_V3R_PROGRESS_NATIVE_IDENTITY")
            keys = set()
            for payload in payloads:
                row = payload["row"]
                version = row["evaluator_contract"].removeprefix("evaluator_contract_")
                if row["run_id"] != rid or version not in VERSIONS or version in keys:
                    raise RuntimeError("HARD_STOP_V3R_PROGRESS_EVALUATOR_IDENTITY")
                keys.add(version)
            self.progress.native(record)
            for payload in payloads:
                self.progress.evaluation(payload)

        for item in [*self.reused.values(), *self.identity.values()]:
            record = pinned_json(item["native_record"], self.archive)
            payloads = []
            for version, pin in item.get("evaluations", {}).items():
                payload = pinned_json(pin, self.archive)
                if payload["row"]["evaluator_contract"] != "evaluator_contract_" + version:
                    raise RuntimeError("HARD_STOP_V3R_PROGRESS_EVALUATOR_VERSION")
                payloads.append(payload)
            if item["run_id"] in self.reused and len(payloads) != 2:
                raise RuntimeError("HARD_STOP_V3R_PROGRESS_REUSED_EVALUATORS_INCOMPLETE")
            admit(record, payloads, item["run_id"])
        pending = [s for s in self.specs if s["run_id"] not in self.reused]
        for number, start in enumerate(range(0, len(pending), BATCH_SIZE), 1):
            closed = self.control / "BATCHES" / f"BATCH_{number:04d}" / "BATCH_COMPLETE.json"
            if not closed.exists():
                continue
            seal = read_json(closed)
            ids = [s["run_id"] for s in pending[start:start + BATCH_SIZE]]
            if seal.get("status") != "PASS_COMPACT_BATCH_COMPLETE" or seal.get("run_ids") != ids:
                raise RuntimeError("HARD_STOP_V3R_PROGRESS_COMPLETED_BATCH_SCOPE")
            native = pinned_json(seal["native_records"], self.archive)
            evaluated = pinned_json(seal["evaluation_records"], self.archive)
            if len(native) != len(ids) or {r["run_id"] for r in native} != set(ids) or len(evaluated) != 2 * len(ids):
                raise RuntimeError("HARD_STOP_V3R_PROGRESS_COMPLETED_BATCH_COUNTS")
            for record in native:
                payloads = [p for p in evaluated if p["row"]["run_id"] == record["run_id"]]
                if len(payloads) != 2:
                    raise RuntimeError("HARD_STOP_V3R_PROGRESS_COMPLETED_BATCH_EVALUATORS")
                admit(record, payloads, record["run_id"])
            if number not in self.progress.completed_continuation_batches:
                self.progress.completed_continuation_batches.add(number)
                self.progress.completed += 1

    def _verify_admissions(self):
        for spec in self.specs:
            item = self.admissions[spec["run_id"]]
            config = runtime.verify_pin(item["config"], cached=True)
            provider = self.providers[spec["provider_key"]]
            runtime.verify_pin(provider, cached=True)
            if item["prepared_gnss"] != provider:
                raise RuntimeError("HARD_STOP_V3R_PROVIDER_ADMISSION_CHANGED")
            original = runtime.verify_pin(spec["frozen_config"], cached=True).read_bytes()
            cloned, gate = runtime.frozen.clone_runtime_config(original,
                expected_sha256=spec["frozen_config"]["sha256"], gnsspath=provider["path"])
            if config.read_bytes() != cloned or gate != item["byte_gate"]:
                raise RuntimeError("HARD_STOP_V3R_CONFIG_ADMISSION_CHANGED")
            if item["expected_echo_gate"].get("passed") is not True:
                raise RuntimeError("HARD_STOP_V3R_EXPECTED_ECHO_GATE")
            for pin in spec["frozen_providers"].values():
                runtime.verify_pin(pin, cached=True)

    def _load_reused(self, item):
        record = pinned_json(item["native_record"], self.archive)
        if (record["run_id"] != item["run_id"] or record.get("code_commit") != self.code_freeze
                or record["status"] not in ("COMPLETED", "ALGORITHM_FAILURE_DIVERGED", "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT")):
            raise RuntimeError("HARD_STOP_V3R_REUSE_NATIVE_IDENTITY")
        evaluations = []
        for version, pin in item.get("evaluations", {}).items():
            payload = pinned_json(pin, self.archive)
            if (version not in VERSIONS or payload["row"]["run_id"] != record["run_id"]
                    or payload["row"]["evaluator_contract"] != "evaluator_contract_" + version):
                raise RuntimeError("HARD_STOP_V3R_REUSE_EVALUATION_IDENTITY")
            payload = apply_existing_retention(payload, archive=self.archive, control=self.control,
                decision=self.retention[record["run_id"]], reconciliation_pin=self.reconciliation_pin,
                evaluation_pin=pin)
            evaluations.append(payload)
        return record, evaluations

    def _native(self, spec):
        rid = spec["run_id"]
        if rid in self.identity:
            record, _ = self._load_reused(self.identity[rid])
            for role in ("nav", "std"):
                runtime.verify_pin(dict(path=record[role + "_path"], sha256=record[role + "_sha256"]), cached=False)
            self.progress.native(record)
            return record
        root = self.work / "03_NATIVE" / rid
        if root.exists():
            if not (root / "V3_NATIVE_SUMMARY.json").is_file() or not (root / "OUTPUT_SEAL.json").is_file():
                raise RuntimeError("HARD_STOP_V3R_UNSEALED_CONTINUATION_NATIVE_NO_RETRY")
            record = runtime.load_native(root)
            if record["run_id"] != rid or record.get("code_commit") != self.code_freeze:
                raise RuntimeError("HARD_STOP_V3R_SEALED_NATIVE_REUSE_IDENTITY")
        else:
            record = runtime.run_native(self.contexts[spec["sequence_id"]], spec, self.admissions[rid],
                binary=self.binary, output_root=root, scratch_root=self.scratch,
                code_freeze=self.code_freeze, ledger=self.control / "NATIVE_RESERVATIONS.jsonl",
                allowed_run_ids=[r for r in self.allowed if r not in self.reused and r not in self.identity],
                timeout_seconds=self.contract.get("native_timeout_seconds", 1800))
        check_recovery_hashes(record, self.recovery.get(rid, {}))
        self.progress.native(record)
        return record

    def _evaluate(self, pair):
        record, version = pair
        rid = record["run_id"]
        previous = self.identity.get(rid, {}).get("evaluations", {}).get(version)
        if previous:
            payload = pinned_json(previous, self.archive)
            self.progress.evaluation(payload)
            return payload
        if rid + "__" + version in self.original_eval and rid not in self.recovery:
            raise RuntimeError("HARD_STOP_V3R_CONSUMED_EVALUATOR_WITHOUT_RECONCILIATION")
        root = self.work / "04_EVALUATION" / rid / version
        if root.exists() and (not (root / "EVALUATION_RESULT.json").is_file()
                or not (root / "OUTPUT_SEAL.json").is_file() or (root / "HARD_STOP.json").exists()):
            raise RuntimeError("HARD_STOP_V3R_UNSEALED_CONTINUATION_EVALUATOR_NO_RETRY")
        payload = runtime.evaluate_native(self.contexts[record["sequence_id"]], self.evaluator,
            record, version, output_root=root, scratch_root=self.scratch,
            ledger=self.control / "EVALUATOR_RESERVATIONS.jsonl", allowed_run_ids=self.eval_allowed)
        self.progress.evaluation(payload)
        return payload

    def matrix(self):
        final_status = self.archive / "STATUS.json"
        if final_status.exists():
            status = read_json(final_status)
            if status.get("status") != "PASS_V3_EXECUTION_COMPLETE" or status.get("science_freeze") != self.code_freeze:
                raise RuntimeError("HARD_STOP_V3R_EXISTING_FINAL_STATUS")
            final_records = pinned_json(dict(path=str(self.archive / "FINAL_RUN_RECORDS.json"),
                sha256=status["final_run_records_sha256"]))
            final_evaluations = pinned_json(dict(path=str(self.archive / "FINAL_EVALUATION_RECORDS.json"),
                sha256=status["final_evaluation_records_sha256"]))
            if ({r["run_id"] for r in final_records} != set(self.allowed)
                    or len(final_records) != len(self.allowed) or len(final_evaluations) != len(self.eval_allowed)):
                raise RuntimeError("HARD_STOP_V3R_EXISTING_FINAL_COVERAGE")
            for record in final_records:
                self.progress.native(record)
            for payload in final_evaluations:
                self.progress.evaluation(payload)
            if self.progress.eval_ids != set(self.eval_allowed):
                raise RuntimeError("HARD_STOP_V3R_EXISTING_FINAL_EVALUATOR_COVERAGE")
            self.progress.completed = self.progress.total_batches
            self.progress.phase = "MATRIX"
            self.progress.flush()
            return status
        records, evaluations = [], []
        for rid, item in self.reused.items():
            record, payloads = self._load_reused(item)
            if {p["row"]["evaluator_contract"] for p in payloads} != {"evaluator_contract_" + v for v in VERSIONS}:
                raise RuntimeError("HARD_STOP_V3R_REUSED_BATCH_EVALUATORS_INCOMPLETE")
            records.append(record)
            evaluations.extend(payloads)
            self.progress.native(record)
            for payload in payloads:
                self.progress.evaluation(payload)
        # B2 already admitted these native identities, although their remaining
        # evaluator/archive work stays at the original position in the queue.
        # Progress uses sets; final record lists are populated only by that batch.
        for item in self.identity.values():
            record, payloads = self._load_reused(item)
            self.progress.native(record)
            for payload in payloads:
                self.progress.evaluation(payload)
        self.progress.start()
        pending = [s for s in self.specs if s["run_id"] not in self.reused]
        for number, start in enumerate(range(0, len(pending), BATCH_SIZE), 1):
            specs = pending[start:start + BATCH_SIZE]
            batch_root = self.control / "BATCHES" / f"BATCH_{number:04d}"
            closed = batch_root / "BATCH_COMPLETE.json"
            if closed.exists():
                seal = read_json(closed)
                if seal["run_ids"] != [s["run_id"] for s in specs]:
                    raise RuntimeError("HARD_STOP_V3R_COMPLETED_BATCH_SCOPE_CHANGED")
                saved_native = pinned_json(seal["native_records"], self.archive)
                saved_eval = pinned_json(seal["evaluation_records"], self.archive)
                records.extend(saved_native)
                evaluations.extend(saved_eval)
                for record in saved_native:
                    self.progress.native(record)
                for payload in saved_eval:
                    self.progress.evaluation(payload)
                if number not in self.progress.completed_continuation_batches:
                    self.progress.completed_continuation_batches.add(number)
                    self.progress.completed += 1
                continue
            self.progress.check()
            self.progress.start_batch(number)
            self.guard.before_batch(number)
            terminal_seal = batch_root / "BATCH_TERMINALS.json"
            if terminal_seal.exists():
                terminal = read_json(terminal_seal)
                if terminal["run_ids"] != [s["run_id"] for s in specs]:
                    raise RuntimeError("HARD_STOP_V3R_TERMINAL_BATCH_SCOPE_CHANGED")
                native = pinned_json(terminal["native_records"], self.archive)
                evaluated = pinned_json(terminal["evaluation_records"], self.archive)
                for record in native:
                    self.progress.native(record)
                for payload in evaluated:
                    self.progress.evaluation(payload)
            else:
                native = parallel_bounded(specs, self._native)
                measured = self.guard.checkpoint(number, "AFTER_NATIVE")
                if measured["scratch_bytes"] > SCRATCH_MAX:
                    raise RuntimeError("HARD_STOP_V3R_SCRATCH_CAP_EXCEEDED")
                self.progress.check()
                evaluated = parallel_bounded([(r, v) for r in native for v in VERSIONS], self._evaluate)
                measured = self.guard.checkpoint(number, "AFTER_EVALUATION")
                if measured["scratch_bytes"] > SCRATCH_MAX:
                    raise RuntimeError("HARD_STOP_V3R_SCRATCH_CAP_EXCEEDED")
                terminal_native = batch_root / "RUN_TERMINALS.json"
                terminal_eval = batch_root / "EVALUATION_TERMINALS.json"
                persist(terminal_native, sorted(native, key=lambda r: r["run_id"]))
                persist(terminal_eval, sorted(evaluated, key=lambda p: (p["row"]["run_id"], p["row"]["evaluator_contract"])))
                persist(terminal_seal, dict(status="PASS_NATIVE_EVALUATOR_TERMINALS_SEALED_BEFORE_ARCHIVE",
                    run_ids=[s["run_id"] for s in specs],
                    native_records=dict(path=str(terminal_native), sha256=sha256_file(terminal_native)),
                    evaluation_records=dict(path=str(terminal_eval), sha256=sha256_file(terminal_eval))))
            saved_native, saved_eval = [], []
            for record in native:
                rid = record["run_id"]
                receipt = compact_archive(record["output_root"], self.archive / "03_NATIVE" / CONTINUATION / rid,
                    scratch_root=self.scratch, batch=number, retention=self.retention[rid])
                saved_native.append(native_archived(record, receipt))
            for payload in evaluated:
                rid = payload["row"]["run_id"]
                version = payload["row"]["evaluator_contract"].removeprefix("evaluator_contract_")
                if version in self.identity.get(rid, {}).get("evaluations", {}):
                    saved_eval.append(payload)
                    continue
                receipt = compact_archive(self.work / "04_EVALUATION" / rid / version,
                    self.archive / "04_EVALUATION" / CONTINUATION / rid / version, scratch_root=self.scratch,
                    batch=number, retention=self.retention[rid])
                saved_eval.append(evaluation_archived(payload, receipt))
            native_path, eval_path = batch_root / "RUN_RECORDS.json", batch_root / "EVALUATION_RECORDS.json"
            persist(native_path, sorted(saved_native, key=lambda r: r["run_id"]))
            persist(eval_path, sorted(saved_eval, key=lambda p: (p["row"]["run_id"], p["row"]["evaluator_contract"])))
            persist(closed, dict(status="PASS_COMPACT_BATCH_COMPLETE", run_ids=[s["run_id"] for s in specs],
                native_records=dict(path=str(native_path), sha256=sha256_file(native_path)),
                evaluation_records=dict(path=str(eval_path), sha256=sha256_file(eval_path))))
            records.extend(saved_native)
            evaluations.extend(saved_eval)
            self.guard.checkpoint(number, "AFTER_ARCHIVE_RELEASE")
            self.progress.end_batch()
            print("V3R_PROGRESS", len(records), len(self.specs), "EVALUATIONS", len(evaluations), flush=True)
        if len(records) != len(self.specs) or len(evaluations) != 2 * len(self.specs):
            raise RuntimeError("HARD_STOP_V3R_FINAL_COUNTS")
        self._verify_admissions()
        for key in ("executable", "evaluator"):
            runtime.verify_pin(self.contract["frozen"][key], cached=False)
        for name, digest in self.freeze["source_sha256"].items():
            runtime.verify_pin(dict(path=str(self.code / name), sha256=digest), cached=False)
        self.gates["2c"] = {**self.gates["2c"], "phase": "COMPLETED_NATIVE_ADMISSION",
            "actual_211_echo_pass_count": sum(r.get("effective_echo_gate", {}).get("passed") is True for r in records),
            "actual_echo_unavailable_classified_failure_count": sum(r.get("effective_echo_gate", {}).get("passed") is None
                and r["status"].startswith("ALGORITHM_FAILURE_") for r in records),
            "actual_echo_unavailable_not_a_pass": True}
        persist(self.archive / "FINAL_IDENTITY_GATES.json", dict(status="PASS", gates=self.gates))
        persist(self.archive / "FINAL_RUN_RECORDS.json", sorted(records, key=lambda r: r["run_id"]))
        persist(self.archive / "FINAL_EVALUATION_RECORDS.json", sorted(evaluations,
            key=lambda p: (p["row"]["run_id"], p["row"]["evaluator_contract"])))
        status = dict(status="PASS_V3_EXECUTION_COMPLETE", native_terminal_count=len(records),
            evaluator_terminal_count=len(evaluations), science_freeze=self.code_freeze,
            final_run_records_sha256=sha256_file(self.archive / "FINAL_RUN_RECORDS.json"),
            final_evaluation_records_sha256=sha256_file(self.archive / "FINAL_EVALUATION_RECORDS.json"),
            continuation_commit=self.continuation_commit, original_completed_native_reused=len(self.reused),
            identity_native_only_reused=len(self.identity), authorized_recovery_native_count=len(self.recovery),
            automatic_native_retries=0, workers=WORKERS, batch_size=BATCH_SIZE,
            storage=self.guard.summary(), trace_open_count_parent=len(self.parent_raw_opens))
        status["capacity_forecast"] = self.capacity
        persist(self.archive / "STATUS.json", status)
        return status

    def finish_reports(self):
        """Numerical tables, ten figures and machine QA; packaging is deferred."""
        from . import reporting, figures
        complete = self.archive / "00_CONTROL/DONE.json"
        if complete.exists():
            summary = read_json(complete)
            if summary.get("status") != "DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA" or summary.get("science_freeze") != self.code_freeze:
                raise RuntimeError("HARD_STOP_V3R_EXISTING_DONE_IDENTITY")
            self.progress.phase = "DONE"
            self.progress.flush()
            return summary
        self.progress.phase = "AGGREGATE"
        self.progress.flush()
        index = self.code / self.contract["report_source_index"]["path"]
        source_index = pinned_json(dict(path=str(index), sha256=self.contract["report_source_index"]["sha256"]))
        aggregate_path = self.archive / "07_AGGREGATE/AGGREGATE_MANIFEST.json"
        if aggregate_path.exists():
            aggregate = read_json(aggregate_path)
            if aggregate.get("status") != "COMPLETE_V3_AGGREGATES" or aggregate.get("code_freeze") != self.code_freeze:
                raise RuntimeError("HARD_STOP_V3R_EXISTING_AGGREGATE_INVALID")
            for name, digest in aggregate["files_sha256"].items():
                runtime.verify_pin(dict(path=str(aggregate_path.parent / name), sha256=digest), cached=False)
        else:
            with report_output_io(self.archive):
                aggregate = reporting.aggregate(self.archive, source_index, roots=self.paths, code_freeze=self.code_freeze)
        render_path = self.archive / "08_FIGURES/RENDER_MANIFEST.json"
        if render_path.exists():
            render = read_json(render_path)
        else:
            with report_output_io(self.archive):
                render = figures.render(self.archive, roots=self.paths, code_freeze=self.code_freeze)
        if render.get("status") != "COMPLETE" or render.get("rendered_count") != 10 or render.get("code_freeze") != self.code_freeze:
            raise RuntimeError("HARD_STOP_V3R_REQUIRED_FIGURE_OR_MACHINE_QA_INCOMPLETE")
        for entry in render["figures"]:
            if not all(row["pass"] for row in entry["qa"]):
                raise RuntimeError("HARD_STOP_V3R_FIGURE_QA")
            for extension, digest in entry["output_sha256"].items():
                runtime.verify_pin(dict(path=str(render_path.parent / entry["figure_id"] /
                    (entry["figure_id"] + "." + extension)), sha256=digest), cached=False)
        self.progress.phase = "DONE"
        state = self.progress.flush()
        summary = dict(status="DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA", state=state,
            science_freeze=self.code_freeze, continuation_commit=self.continuation_commit,
            aggregate_manifest_sha256=sha256_file(aggregate_path), render_manifest_sha256=sha256_file(render_path),
            visual_review_status="PENDING_ACTUAL_RASTER_REVIEW", package_status="DEFERRED_TO_NEXT_SESSION",
            git_results_status="DEFERRED_TO_NEXT_SESSION", storage=self.guard.summary())
        persist(self.archive / "00_CONTROL/SUMMARY.json", summary)
        self.progress._replace_operational(self.archive / "00_CONTROL/SUMMARY.txt",
            ("DONE: matrix, aggregates, ten figure groups and machine QA complete.\n"
             + "Visual review, packaging and Git result delivery remain for the next session.\n"
             + json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode())
        persist(self.archive / "00_CONTROL/DONE.json", summary)
        return summary


def record_hard_stop(ctx, error, *, science_freeze, continuation_commit):
    """Persist the first stop before refreshing G-only operational status.

    A partially initialized context carries the validated-root boundary. A
    failed or malformed existing stop is preserved byte-for-byte on reentry.
    """
    progress = getattr(ctx, "progress", None)
    if progress is not None:
        progress.stop()
    if not getattr(ctx, "storage_roots_validated", False):
        print("HARD_STOP persistence unavailable: G stage/root validation did not complete; "
            + str(error), file=sys.stderr, flush=True)
        return
    stop_path = ctx.control / "HARD_STOP.json"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        if stop_path.exists():
            try:
                stop = read_json(stop_path)
                if (not isinstance(stop, dict) or stop.get("status") != "HARD_STOP"
                        or not isinstance(stop.get("error"), str)):
                    stop = dict(status="HARD_STOP", error="PERSISTED_HARD_STOP_INVALID_SCHEMA_PRESERVED",
                        original_sha256=sha256_file(stop_path))
            except (ValueError, UnicodeError):
                stop = dict(status="HARD_STOP", error="PERSISTED_HARD_STOP_UNREADABLE_PRESERVED",
                    original_sha256=sha256_file(stop_path))
        else:
            stop = dict(status="HARD_STOP", error=str(error), utc=now,
                phase=getattr(progress, "phase", "GATES"),
                all_started_workers_drained=True, science_freeze=science_freeze,
                continuation_commit=continuation_commit, automatic_retry=False)
            persist(stop_path, stop)
    except Exception as persistence_error:
        print("HARD_STOP persistence unavailable at validated G stage: " + str(persistence_error)
            + "; original failure: " + str(error), file=sys.stderr, flush=True)
        return
    if progress is not None:
        progress.hardstop = stop
        try:
            progress.flush()
            return
        except Exception as refresh_error:
            print("HARD_STOP full heartbeat unavailable; writing G-only minimal state: "
                + str(refresh_error), file=sys.stderr, flush=True)
    # Early pin/freeze/P′ failures may have no guard, registry or heartbeat yet.
    # Never sample another disk or invent progress to construct a stop view.
    state_path = ctx.archive / "00_CONTROL/STATE.json"
    try:
        previous = read_json(state_path) if state_path.exists() else {}
        if not isinstance(previous, dict):
            previous = {}
    except (ValueError, UnicodeError, OSError):
        previous = {}
    state = {**previous, "phase": getattr(progress, "phase", "GATES"), "status": "HARD_STOP",
        "updated_utc": now, "latest_hard_stop": stop, "current_failure": str(error),
        "hard_stop_record": str(stop_path), "automatic_retry": False}
    if hasattr(ctx, "capacity"):
        state["capacity_forecast"] = ctx.capacity
    try:
        Heartbeat._replace_operational(state_path, (json.dumps(state, indent=2) + "\n").encode())
        Heartbeat._replace_operational(ctx.archive / "00_CONTROL/PROGRESS.txt",
            (f"phase={state['phase']} status=HARD_STOP updated={now}\n"
             f"cause={stop.get('error', str(error))}\ncurrent_failure={error}\n"
             f"immutable_record={stop_path}\n" + json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    except Exception as persistence_error:
        print("HARD_STOP operational persistence unavailable at validated G stage: "
            + str(persistence_error), file=sys.stderr, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--science-freeze", required=True)
    parser.add_argument("--continuation-commit", required=True)
    parser.add_argument("--reconciliation", required=True)
    parser.add_argument("--reconciliation-sha256", required=True)
    parser.add_argument("--capacity-forecast-sha256", required=True)
    parser.add_argument("--purge-prime-receipt", required=True,
        help="Pinned P4_VERIFIED record in V3R_PURGE/PROTOCOL_V2_RETAINED")
    parser.add_argument("--purge-prime-sha256", required=True)
    args = parser.parse_args(argv)
    ctx = ResumeContext.__new__(ResumeContext)
    try:
        ctx.__init__(args.local_config, args.contract, args.science_freeze,
            args.continuation_commit, args.reconciliation, args.reconciliation_sha256,
            args.capacity_forecast_sha256, args.purge_prime_receipt, args.purge_prime_sha256)
        result = ctx.matrix()
        result = ctx.finish_reports()
    except Exception as exc:
        record_hard_stop(ctx, exc, science_freeze=args.science_freeze,
            continuation_commit=args.continuation_commit)
        raise
    finally:
        if hasattr(ctx, "progress"):
            ctx.progress.stop()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
