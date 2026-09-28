"""G-only V3-01-R complete handoff from retained, closed evidence.

This adapter neither imports scientific runtime code nor executes native or
evaluator processes. The old packer and scientific freeze remain unchanged.
ZIP bytes are streamed directly to HANDOFF_ROOT; any failed attempt is kept.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import zipfile
import zlib

from ..clean6_canonical_v2.archive_io import _write_all, retry_io

BLOCK = 8 * 1024 * 1024
FIGURES = {*(f"MFIG{i:02}" for i in range(7)), "SFIG01", "FIG02S", "FIG02S-b"}
SOURCE_ROOTS = ("src/legsa_gins/paper_rebuild", "scripts/paper_rebuild",
                "configs/paper_rebuild", "tests/paper_rebuild", "cpp/legsa_v23_port_core",
                "docs/paper_rebuild/v3")
SOURCE_SUFFIXES = {".py", ".cpp", ".cc", ".h", ".hpp", ".cmake", ".yaml", ".yml",
                   ".json", ".md", ".csv", ".txt", ".sh", ".toml", ".in"}
FORBIDDEN_SUFFIXES = {".nav", ".std", ".imu", ".gnss", ".bag", ".fpl", ".bin",
                      ".so", ".o", ".a", ".exe", ".zip"}
REQUIRED_DOCS = ("V3_01_EXECUTION_RECORD.md", "V3_01R_FINAL_REPORT.md",
                 "V3_01R_MANUSCRIPT_REPLACEMENT.md")


def safe(path):
    path = Path(path).absolute()
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Handoff paths cannot traverse symlinks or parent components")
    return path


def below(path, root):
    path, root = safe(path), safe(root)
    if root not in path.parents:
        raise ValueError("Handoff input is outside its registered root: " + str(path))
    return path


def require_g_roots(root, handoff):
    """Match the admitted controller's permanent G-volume storage boundary."""
    mount = Path("/mnt/g")
    if mount not in root.parents or mount not in handoff.parents or not os.path.ismount(mount):
        raise ValueError("V3-01-R retained evidence and handoff must reside on the mounted G volume")


def payload_allowed(path):
    name = Path(path).name.lower()
    return (not set(Path(name).suffixes).intersection(FORBIDDEN_SUFFIXES)
            and not name.startswith("trace_") and name not in {"nav", "std", "eval_nav"})


class RetryFile:
    """Fixed-offset retries prevent duplicate bytes after uncertain I/O errors."""
    def __init__(self, path, mode, events=None):
        self.path, self.events = safe(path), events if events is not None else []
        self.stream = self._op(lambda: self.path.open(mode, buffering=0), "open")

    def _op(self, operation, name):
        result, events = retry_io(operation, source=self.path, destination=self.path,
                                  operation="v3r_handoff_" + name)
        self.events.extend(dict(path=str(self.path), **event) for event in events)
        return result

    def read(self, count=-1):
        offset = self.tell()
        def operation():
            self.stream.seek(offset)
            return self.stream.read(count)
        return self._op(operation, "read")

    def write(self, data):
        offset = self.tell()
        def operation():
            self.stream.seek(offset)
            return _write_all(self.stream, data)
        return self._op(operation, "write")

    def seek(self, offset, whence=0):
        return self._op(lambda: self.stream.seek(offset, whence), "seek")

    def tell(self):
        return self._op(self.stream.tell, "tell")

    def seekable(self):
        return True

    def flush(self):
        # Durability failure stops this package. Never promote a later fsync
        # alone to evidence that an earlier uncertain write was recovered.
        self.stream.flush()

    def durable(self):
        self.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def digest_stream(stream):
    digest, crc, size = hashlib.sha256(), 0, 0
    for block in iter(lambda: stream.read(BLOCK), b""):
        digest.update(block)
        crc = zlib.crc32(block, crc)
        size += len(block)
    return dict(sha256=digest.hexdigest(), crc32=f"{crc & 0xffffffff:08x}", size_bytes=size)


def digest_file(path):
    with RetryFile(path, "rb") as stream:
        return digest_stream(stream)


def read_json(path):
    with RetryFile(path, "rb") as stream:
        return json.loads(stream.read())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def exclusive_bytes(path, payload, events):
    with RetryFile(path, "xb", events) as stream:
        stream.write(payload)
        stream.durable()
    if digest_file(path)["sha256"] != hashlib.sha256(payload).hexdigest():
        raise ValueError("Handoff metadata verification failed")


def require_hash(path, expected):
    if digest_file(path)["sha256"] != expected:
        raise ValueError("Handoff input hash mismatch: " + str(path))


def completion_checks(root, code_freeze, gate_path, audit_path, *, repair_commit):
    """Fail closed before creating any archive, including on visual-QA failure."""
    root = safe(root)
    gate_path, audit_path = below(gate_path, root), below(audit_path, root)
    gates, audit = read_json(gate_path), read_json(audit_path)
    if (gates.get("status") != "PASS" or set(gates.get("gates", {})) != {"2a", "2b", "2c", "2d", "2e"}
            or any(g.get("status") != "PASS" for g in gates["gates"].values())
            or gates["gates"]["2c"].get("phase") != "COMPLETED_NATIVE_ADMISSION"):
        raise ValueError("Complete handoff requires all five admitted identity gates")
    if (audit.get("status") != "PASS" or audit.get("native_count") != 6468
            or audit.get("evaluator_terminal_slots") != 12936
            or audit.get("native_trace_open_count") != 0
            or audit.get("evaluator_each_trace_exactly_one") is not True
            or audit.get("completed_batches") != 279
            or not 0 < audit.get("evaluator_process_count", 0) <= 12936
            or any(audit.get(key) != 0 for key in ("native_calls", "evaluator_calls", "raw_trace_reads"))):
        raise ValueError("Complete handoff requires complete zero-native-trace recovery audit")
    counts = audit.get("counts", {})
    if (counts.get("evaluator_processes") != audit["evaluator_process_count"]
            or audit["evaluator_process_count"] + counts.get("evaluator_skipped_slots", -1) != 12936):
        raise ValueError("Evaluator audit terminal/process/skip conservation failed")
    for name, key in (("OPENAT_AUDIT_ROWS.csv", "audit_rows_sha256"),
                      ("OPENAT_SOURCE_PINS.json", "source_pins_sha256")):
        require_hash(audit_path.parent / name, audit[key])
    aggregate_path = root / "07_AGGREGATE/AGGREGATE_MANIFEST.json"
    render_path = root / "08_FIGURES/RENDER_MANIFEST.json"
    done_path = root / "00_CONTROL/DONE.json"
    visual_path = root / "09_HANDOFF/VISUAL_REVIEW.json"
    aggregate, render, done, visual = map(read_json, (aggregate_path, render_path, done_path, visual_path))
    if aggregate.get("status") != "COMPLETE_V3_AGGREGATES" or aggregate.get("code_freeze") != code_freeze:
        raise ValueError("Incomplete or wrong-freeze aggregates")
    for name, digest in aggregate["files_sha256"].items():
        require_hash(below(aggregate_path.parent / name, aggregate_path.parent), digest)
    if (done.get("status") != "DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA"
            or done.get("science_freeze") != code_freeze
            or not (root / "00_CONTROL/SUMMARY.txt").is_file()):
        raise ValueError("Missing closed DONE/SUMMARY evidence")
    for key, path in (("aggregate_manifest_sha256", aggregate_path), ("render_manifest_sha256", render_path)):
        require_hash(path, done[key])
    appendix_path = root / "07C_FAILURE_FAMILY_CONFIG/MANIFEST.json"
    appendix = read_json(appendix_path)
    if (appendix.get("status") != "PASS_REPORT_ONLY_FULL_ABLATION_AND_FAILURE_FAMILY_CONFIG"
            or appendix.get("science_freeze") != code_freeze or appendix.get("repair_commit") != repair_commit
            or appendix.get("v3_failures") != 283 or appendix.get("v21_failures") != 177
            or appendix.get("f02_separate") is not True or appendix.get("full_ablation_rows_per_version") != 33
            or appendix.get("corrected_field_only") != "v21_failure"
            or appendix.get("numeric_tokens_changed") != 0 or appendix.get("original_files_changed") != 0):
        raise ValueError("Required full ablation and family/configuration failure appendix is incomplete")
    expected_appendix = {"FULL_ABLATION_TABLE_V3.csv", "FULL_ABLATION_TABLE_V2.csv",
                        "CORE_541_V21_COMPARISON_V3.csv", "CORE_541_V21_COMPARISON_V2.csv",
                        "SUBSET61_V21_COMPARISON_V3.csv", "SUBSET61_V21_COMPARISON_V2.csv",
                        "FAILURE_FAMILY_CONFIG.csv", "MANUSCRIPT_FULL_ABLATION_AND_FAILURES.md"}
    if set(appendix.get("files_sha256", {})) != expected_appendix:
        raise ValueError("Required failure appendix file inventory differs")
    require_hash(appendix_path, done["full_ablation_failure_appendix_sha256"])
    for name, digest in appendix["files_sha256"].items():
        require_hash(appendix_path.parent / name, digest)
    entries = render.get("figures", [])
    if (render.get("status") != "COMPLETE" or render.get("rendered_count") != 10
            or render.get("code_freeze") != code_freeze or len(entries) != 10
            or {e.get("figure_id") for e in entries} != FIGURES):
        raise ValueError("All ten registered figure groups are required")
    for entry in entries:
        if (entry.get("status") != "RENDERED" or not entry.get("qa")
                or any(row.get("pass") is not True for row in entry["qa"])
                or set(entry.get("output_sha256", {})) != {"png", "pdf", "svg"}):
            raise ValueError("Figure machine QA failed or exports are incomplete")
        for extension, digest in entry["output_sha256"].items():
            require_hash(root / "08_FIGURES" / entry["figure_id"] / (entry["figure_id"] + "." + extension), digest)
    if (visual.get("status") != "PASS" or set(visual.get("reviewed_figures", [])) != FIGURES
            or len(visual.get("reviewed_figures", [])) != 10
            or visual.get("render_manifest_sha256") != digest_file(render_path)["sha256"]):
        raise ValueError("Actual visual review must pass and bind the final ten-figure render manifest")
    with RetryFile(root / "07_AGGREGATE/MAIN_TABLE_V3.csv", "rb") as stream:
        rows = list(csv.DictReader(io.StringIO(stream.read().decode("utf-8-sig"))))
    anchors = {"BY2": "1.886272", "BY2H": "1.933770", "BY2O": "2.433815"}
    f04 = {r["sequence_id"]: f"{float(r['yaw_rmse_deg']):.6f}" for r in rows if r["method_id"] == "F04"}
    if len(rows) != 52 or sum(r["method_id"] == "F04" for r in rows) != 3 or f04 != anchors:
        raise ValueError("HARD_STOP_F04_T5AR_THREE_SEQUENCE_IDENTITY")
    return dict(identity_gates=gates, audit=audit, done=done,
                visual_review_sha256=digest_file(visual_path)["sha256"], f04_yaw=f04)


def walk_stage(root):
    files, excluded = [], []
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs:
            safe(Path(directory) / name)
        for name in names:
            path = safe(Path(directory) / name)
            relative = path.relative_to(root).as_posix()
            if not path.is_file():
                raise ValueError("Non-regular stage member: " + relative)
            if not payload_allowed(path) or relative.startswith("09_HANDOFF/PACKAGES/"):
                excluded.append(dict(path=relative, reason="RAW_BINARY_PROVIDER_OR_PRIOR_PACKAGE_EXCLUDED"))
            else:
                files.append((path, "V3_RETAINED/" + relative, None))
    return sorted(files, key=lambda row: row[1]), excluded


def reference_files(index, roots):
    """Copy only explicitly registered metadata/table pins, never recurse stage roots."""
    result, seen = [], set()
    def visit(item):
        if isinstance(item, list):
            for value in item:
                visit(value)
        if not isinstance(item, dict):
            return
        if {"path", "sha256"} <= item.keys():
            name = str(item["path"])
            for key, root in roots.items():
                name = name.replace("<" + key.upper() + ">", str(root))
            if "<" in name:
                raise ValueError("Unresolved external-reference alias")
            path = safe(name)
            matches = [(alias, safe(roots[alias])) for alias in ("clean_root", "code_root")
                       if alias in roots and safe(roots[alias]) in path.parents]
            if len(matches) != 1 or not payload_allowed(path) or path.suffix.lower() not in {".csv", ".json", ".yaml", ".yml", ".md", ".gz"}:
                raise ValueError("Unregistered or forbidden external-reference payload")
            if path not in seen:
                alias, base = matches[0]
                result.append((path, "REGISTERED_REFERENCES/" + alias.upper() + "/" + path.relative_to(base).as_posix(), item["sha256"]))
                seen.add(path)
            return
        for value in item.values():
            visit(value)
    visit(index)
    return sorted(result, key=lambda row: row[1])


def git_identity(repo, commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Source snapshots require full immutable commit SHA")
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", commit + "^{commit}"], text=True).strip()
    if actual != commit:
        raise ValueError("Git source commit identity differs")
    return actual


def verify_running_source(repo, repair_commit):
    relative = "src/legsa_gins/paper_rebuild/protocol_v3/recovery_packaging.py"
    executing = safe(__file__)
    if executing != safe(repo / relative):
        raise ValueError("Packaging module must execute from the registered code root")
    frozen = subprocess.check_output(["git", "-C", str(repo), "show", repair_commit + ":" + relative])
    digest = hashlib.sha256(frozen).hexdigest()
    require_hash(executing, digest)
    return digest


def add_member(archive, stream, name, expected=None):
    parts = PurePosixPath(name)
    if parts.is_absolute() or ".." in parts.parts:
        raise ValueError("Unsafe ZIP member name")
    item = zipfile.ZipInfo(name)
    item.compress_type = zipfile.ZIP_STORED if parts.suffix.lower() in {".gz", ".png", ".pdf"} else zipfile.ZIP_DEFLATED
    digest, crc, size = hashlib.sha256(), 0, 0
    with archive.open(item, "w", force_zip64=True) as writer:
        for block in iter(lambda: stream.read(BLOCK), b""):
            writer.write(block)
            digest.update(block)
            crc = zlib.crc32(block, crc)
            size += len(block)
    row = dict(name=name, sha256=digest.hexdigest(), crc32=f"{crc & 0xffffffff:08x}", size_bytes=size)
    if expected is not None and row["sha256"] != expected:
        raise ValueError("Source changed or external reference pin differs: " + name)
    return row


def source_snapshot(archive, repo, commit, prefix):
    # git archive streams a tar to memory/ZIP, never an intermediate WSL archive.
    available = [path for path in SOURCE_ROOTS if subprocess.check_output(
        ["git", "-C", str(repo), "ls-tree", "--name-only", commit, "--", path], text=True).strip()]
    if not available:
        raise ValueError("Source snapshot has no registered source directories")
    process = subprocess.Popen(["git", "-C", str(repo), "archive", "--format=tar", commit, "--", *available],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    members = []
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as source:
            for item in source:
                if item.isdir():
                    continue
                if not item.isfile():
                    raise ValueError("Git source snapshot contains a link or special file")
                # A tracked trace_* Python module is source provenance, not a
                # raw reference payload. git supplies exact frozen blob bytes.
                if ".local." in item.name or Path(item.name).suffix not in SOURCE_SUFFIXES:
                    continue
                with source.extractfile(item) as stream:
                    members.append(add_member(archive, stream, prefix + "/" + item.name))
        error = process.stderr.read()
        if process.wait() != 0:
            raise ValueError("Git archive failed: " + error.decode(errors="replace"))
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    return members


def verify_zip(path, members, manifest_bytes):
    expected = {row["name"]: row for row in members}
    expected["MEMBER_MANIFEST.json"] = dict(name="MEMBER_MANIFEST.json", **digest_stream(io.BytesIO(manifest_bytes)))
    if len(expected) != len(members) + 1:
        raise ValueError("Duplicate planned ZIP member names")
    verified = []
    with RetryFile(path, "rb") as stream, zipfile.ZipFile(stream) as archive:
        if len(archive.namelist()) != len(expected) or set(archive.namelist()) != set(expected):
            raise ValueError("ZIP member inventory differs")
        for info in archive.infolist():
            with archive.open(info) as member:
                row = dict(name=info.filename, **digest_stream(member))
            if (row != expected[info.filename] or row["size_bytes"] != info.file_size
                    or row["crc32"] != f"{info.CRC:08x}"):
                raise ValueError("ZIP member SHA256/CRC/size differs")
            verified.append(row)
    return verified


def package(roots, repo, *, code_freeze, repair_commit, gate_path, audit_path,
            package_name="protocol_v3r_complete_handoff.zip"):
    """Create a complete unique ZIP on G after final machine and visual closure."""
    repo = safe(repo)
    roots = {**roots, "code_root": str(repo)}
    root = safe(Path(roots["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3")
    handoff = safe(roots["handoff_root"])
    require_g_roots(root, handoff)
    if handoff == root or handoff in root.parents or root in handoff.parents:
        raise ValueError("Handoff destination must be independent of retained evidence")
    if Path(package_name).name != package_name or not package_name.endswith(".zip"):
        raise ValueError("Package name must be a single ZIP filename")
    destination = handoff / package_name
    sidecar = handoff / (Path(package_name).stem + "_MANIFEST.json")
    checksum = handoff / (Path(package_name).stem + "_ZIP_SHA256.txt")
    stage_receipt = root / "09_HANDOFF/PACKAGES" / (Path(package_name).stem + "_VERIFICATION.json")
    for path in (destination, sidecar, checksum, stage_receipt):
        if path.exists():
            raise FileExistsError("Prior complete or incomplete handoff must be preserved: " + str(path))
    gates = completion_checks(root, code_freeze, gate_path, audit_path, repair_commit=repair_commit)
    for commit in (code_freeze, repair_commit):
        git_identity(repo, commit)
    packaging_source_sha256 = verify_running_source(repo, repair_commit)
    files, excluded = walk_stage(root)
    files += reference_files(read_json(root / "07_AGGREGATE/REPORT_SOURCE_INDEX.json"), roots)
    for name in REQUIRED_DOCS:
        path = below(repo / "docs/paper_rebuild/v3" / name, repo)
        if not path.is_file():
            raise ValueError("Required final manuscript/result documentation missing: " + name)
        files.append((path, "CURRENT_REVIEW_DOCS/" + name, None))
    if len({name for _, name, _ in files}) != len(files):
        raise ValueError("Duplicate planned handoff names")
    # Physical capacity cannot be inferred from a virtual WSL filesystem.
    handoff.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(handoff).free
    source_bytes = sum(path.stat().st_size for path, _, _ in files)
    if free < source_bytes + 2_000_000_000:
        raise ValueError("Insufficient HANDOFF_ROOT free space for conservative uncompressed archive bound")
    events, members = [], []
    record = dict(status="PASS_PROTOCOL_V3R_COMPLETE", protocol="v3", code_freeze=code_freeze,
                  recovery_commit=repair_commit, data_mode="mixed_real_clean_and_semisynthetic_registered_cases",
                  packaging_source_sha256=packaging_source_sha256,
                  synthetic_data_used=False, semisynthetic_data_used=True,
                  native_calls_in_packaging=0, evaluator_calls_in_packaging=0, trace_open_count=0,
                  source_snapshot_commits={"SCIENCE_SOURCE": code_freeze, "REPAIR_SOURCE": repair_commit},
                  full_retained_evidence=True, raw_and_provider_binary_payloads_included=False,
                  archive_written_directly_to_handoff=True, wsl_archive_created=False,
                  preserved_prior_attempts=True, preserved_frozen_v21_outputs=True,
                  external_reference_scope="Only exact hash-pinned REPORT_SOURCE_INDEX metadata/table files",
                  completion_gates=gates, exclusions=excluded)
    with RetryFile(destination, "xb", events) as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as archive:
            for path, name, expected in files:
                before = path.stat()
                with RetryFile(path, "rb", events) as source:
                    members.append(add_member(archive, source, name, expected))
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("Handoff input changed while streamed: " + name)
            for prefix, commit in record["source_snapshot_commits"].items():
                members.extend(source_snapshot(archive, repo, commit, prefix))
            members.append(add_member(archive, io.BytesIO(encoded(record)), "FINAL_DELIVERY_SUMMARY.json"))
            manifest_bytes = encoded(dict(**record, members=members,
                self_reference_policy="MEMBER_MANIFEST.json hash is recorded in external all-member verification"))
            archive.writestr("MEMBER_MANIFEST.json", manifest_bytes)
        output.durable()
    checked = verify_zip(destination, members, manifest_bytes)
    zip_digest = digest_file(destination)
    receipt = dict(status="PASS_ZIP_INTEGRITY", scientific_status=record["status"],
                   code_freeze=code_freeze, recovery_commit=repair_commit,
                   data_mode=record["data_mode"], synthetic_data_used=False, semisynthetic_data_used=True,
                   zip_sha256=zip_digest["sha256"], zip_size_bytes=zip_digest["size_bytes"],
                   zip_member_count=len(checked), members=checked, exclusions=excluded,
                   handoff_free_bytes_before=free, source_bytes=source_bytes,
                   all_member_sha256_crc_size_verified=True, archive_written_directly_to_handoff=True,
                   wsl_archive_created=False, native_calls=0, evaluator_calls=0, trace_open_count=0,
                   destination=str(destination), retry_events=events)
    exclusive_bytes(sidecar, encoded(receipt), events)
    exclusive_bytes(checksum, (receipt["zip_sha256"] + "  " + package_name + "\n").encode(), events)
    stage_receipt.parent.mkdir(parents=True, exist_ok=True)
    exclusive_bytes(stage_receipt, encoded(receipt), events)
    return {key: receipt[key] for key in ("status", "scientific_status", "zip_sha256", "zip_size_bytes", "zip_member_count", "destination")}


def main():
    import yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--code-freeze", required=True)
    parser.add_argument("--repair-commit", required=True)
    parser.add_argument("--gates", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--package-name", required=True)
    args = parser.parse_args()
    roots = yaml.safe_load(safe(args.local_config).read_text())["paths"]
    print(json.dumps(package(roots, args.repo, code_freeze=args.code_freeze, repair_commit=args.repair_commit,
                             gate_path=args.gates, audit_path=args.audit, package_name=args.package_name), indent=2))


if __name__ == "__main__":
    main()
