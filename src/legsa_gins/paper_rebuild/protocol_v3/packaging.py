"""Lossless full/partial v3 handoff; no execution, deletion, or result promotion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import zipfile
import zlib

from .reporting import safe, sha256, write_json


def _digest(stream):
    digest, crc, size = hashlib.sha256(), 0, 0
    for block in iter(lambda: stream.read(1 << 20), b""):
        digest.update(block)
        crc = zlib.crc32(block, crc)
        size += len(block)
    return dict(sha256=digest.hexdigest(), crc32=f"{crc & 0xffffffff:08x}", size_bytes=size)


def member(path, name):
    with safe(path).open("rb") as stream:
        return dict(name=name, **_digest(stream))


def verify_zip(path, expected):
    checked = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected) | {"MEMBER_MANIFEST.json"}:
            raise ValueError("Handoff ZIP member inventory differs")
        for info in archive.infolist():
            with archive.open(info) as stream:
                row = dict(name=info.filename, **_digest(stream))
            if row["size_bytes"] != info.file_size or row["crc32"] != f"{info.CRC:08x}":
                raise ValueError("Handoff ZIP CRC/size mismatch")
            if info.filename in expected and row != expected[info.filename]:
                raise ValueError("Handoff ZIP SHA256 member mismatch")
            checked.append(row)
    return checked


def completion_checks(root, code_freeze, gate_path):
    root = safe(root)
    gates = json.loads(safe(gate_path).read_text())
    if gates.get("status") != "PASS" or set(gates.get("gates", {})) != {"2a", "2b", "2c", "2d", "2e"}:
        raise ValueError("Complete handoff requires the five named identity gates")
    if any(value.get("status") != "PASS" for value in gates["gates"].values()):
        raise ValueError("Failed identity gate cannot become complete delivery")
    if gates["gates"]["2c"].get("phase") != "COMPLETED_NATIVE_ADMISSION":
        raise ValueError("Final delivery requires actual native 211-parameter admission, not prelaunch expectation only")
    aggregates = json.loads((root / "07_AGGREGATE/AGGREGATE_MANIFEST.json").read_text())
    render = json.loads((root / "08_FIGURES/RENDER_MANIFEST.json").read_text())
    visual = json.loads((root / "09_HANDOFF/VISUAL_REVIEW.json").read_text())
    if aggregates.get("status") != "COMPLETE_V3_AGGREGATES" or aggregates.get("code_freeze") != code_freeze:
        raise ValueError("Incomplete or wrong-freeze aggregate")
    if render.get("status") != "COMPLETE" or render.get("rendered_count") != 10 or render.get("code_freeze") != code_freeze:
        raise ValueError("All ten v3 figures must be rendered before complete delivery")
    if visual.get("status") != "PASS" or set(visual.get("reviewed_figures", [])) != {e["figure_id"] for e in render["figures"]}:
        raise ValueError("Actual raster review of every v3 figure is required")
    for name, digest in aggregates["files_sha256"].items():
        if sha256(root / "07_AGGREGATE" / name) != digest:
            raise ValueError("Aggregate changed after report closure")
    for entry in render["figures"]:
        for extension, digest in entry["output_sha256"].items():
            if sha256(root / "08_FIGURES" / entry["figure_id"] / (entry["figure_id"] + "." + extension)) != digest:
                raise ValueError("Figure export changed after render closure")
    return gates, aggregates, render


def package(root, archive_root, handoff_root, *, code_freeze, gate_path=None,
            partial=False, stop_path=None, package_name=None):
    root, archive_root, handoff_root = map(safe, (root, archive_root, handoff_root))
    if root == archive_root or root in archive_root.parents or archive_root in root.parents:
        raise ValueError("Scratch and archive must be independent roots")
    if handoff_root == root or root in handoff_root.parents or handoff_root == archive_root or archive_root in handoff_root.parents:
        raise ValueError("Handoff destination must be independent of source trees")
    if partial:
        if stop_path is None:
            raise ValueError("Partial handoff requires the preserved hard-stop receipt")
        stop = json.loads(safe(stop_path).read_text())
        if not any("HARD_STOP" in str(stop.get(field, "")) for field in ("status", "terminal_status")):
            raise ValueError("Partial package stop receipt has no hard-stop terminal")
        status, gates = "HARD_STOP_PARTIAL_EVIDENCE", None
    else:
        if gate_path is None:
            raise ValueError("Complete handoff requires identity gates")
        gates, _, _ = completion_checks(root, code_freeze, gate_path)
        stop, status = None, "PASS_PROTOCOL_V3_COMPLETE"
    destination_name = package_name or ("protocol_v3_partial_handoff.zip" if partial else "protocol_v3_handoff.zip")
    if Path(destination_name).name != destination_name or not destination_name.endswith(".zip"):
        raise ValueError("Package name must be a single ZIP filename")
    folder = root / "09_HANDOFF"
    folder.mkdir(parents=True, exist_ok=True)
    zip_path, destination = folder / destination_name, handoff_root / destination_name
    if zip_path.exists() or destination.exists():
        raise FileExistsError("Prior v3 handoff packages must be preserved")
    summary_name = "PARTIAL_DELIVERY_SUMMARY.json" if partial else "FINAL_DELIVERY_SUMMARY.json"
    record = dict(status=status, protocol="v3", code_freeze=code_freeze,
        data_mode="mixed_real_clean_and_semisynthetic_registered_cases", synthetic_data_used=False, semisynthetic_data_used=True,
        identity_gates=gates, hard_stop=stop, scientific_completion_claim=not partial,
        native_calls_in_packaging=0, evaluator_calls_in_packaging=0, trace_open_count=0,
        package_scope="Complete new scratch and losslessly archived artifact trees; frozen comparator payloads remain external pinned references",
        preserved_frozen_v21_outputs=True, preserved_prior_attempts=True,
        partial_policy="Unexecuted and failed gates remain literal; no old metric substitutes" if partial else "NOT_APPLICABLE")
    write_json(folder / summary_name, record)
    files = []
    for prefix, source in (("V3_SCRATCH", root), ("V3_ARCHIVE", archive_root)):
        if not source.exists():
            continue
        for path in sorted(source.rglob("*")):
            safe(path)
            if path.is_file() and path.suffix != ".zip" and path.name not in ("ZIP_VERIFICATION.json", "PARTIAL_ZIP_VERIFICATION.json"):
                files.append((path, prefix + "/" + path.relative_to(source).as_posix()))
    if not files:
        raise ValueError("Empty handoff evidence")
    members = [member(path, name) for path, name in files]
    manifest = dict(code_freeze=code_freeze, status=status,
        data_mode=record["data_mode"], synthetic_data_used=False, semisynthetic_data_used=True,
        members=members, self_reference_policy="MEMBER_MANIFEST.json is checked by the external ZIP_VERIFICATION receipt; no self-hash cycle")
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as stream:
        for path, name in files:
            stream.write(path, name, compress_type=zipfile.ZIP_STORED if path.suffix in (".gz", ".png", ".pdf") else zipfile.ZIP_DEFLATED)
        stream.writestr("MEMBER_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    checked = verify_zip(zip_path, {row["name"]: row for row in members})
    digest = sha256(zip_path)
    handoff_root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(handoff_root).free
    required = zip_path.stat().st_size + (2 << 30)
    copied = free >= required
    if copied:
        # Exclusive destination creation protects earlier deliveries even in a race.
        with zip_path.open("rb") as source, destination.open("xb") as target:
            shutil.copyfileobj(source, target, length=1 << 20)
        if sha256(destination) != digest:
            raise ValueError("Scratch/handoff ZIP bytes differ")
    else:
        destination = zip_path
    receipt = dict(status="PASS_ZIP_INTEGRITY", scientific_status=status, code_freeze=code_freeze,
        zip_sha256=digest, zip_size_bytes=zip_path.stat().st_size, zip_member_count=len(checked),
        members=checked, source_and_handoff_identical=True if copied else "NOT_APPLICABLE_NOT_COPIED",
        handoff_copy_performed=copied, handoff_free_bytes_at_delivery=free,
        handoff_copy_required_bytes_with_reserve=required,
        handoff_copy_reason="COPIED_AND_VERIFIED" if copied else "INSUFFICIENT_DESTINATION_FREE_BYTES_FULL_ZIP_RETAINED_ON_EXT4",
        destination=str(destination),
        data_mode=record["data_mode"], synthetic_data_used=False, semisynthetic_data_used=True)
    write_json(folder / ("PARTIAL_ZIP_VERIFICATION.json" if partial else "ZIP_VERIFICATION.json"), receipt)
    return {key: receipt[key] for key in ("status", "scientific_status", "zip_sha256", "zip_size_bytes", "zip_member_count", "destination")}
