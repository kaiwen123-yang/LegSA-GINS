"""Pinned, alias-resolved P-07 inputs and exclusive artifact writes."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from ..manifest import sha256_file

FLAGS = dict(synthetic_data_used=False, semisynthetic_data_used=False,
             trace_used_online=False, receiver_imu_as_body_imu=False,
             final_v23_output_solver_input=False, LegSA_output_solver_input=False,
             per_case_tuning=False, output_only_correction=False,
             epoch_deleted_for_metric=False, old_runtime_input_count=0)


def registry(local_config):
    p = yaml.safe_load(Path(local_config).read_text())["paths"]
    return SimpleNamespace(**{k: Path(p[k]) for k in ("code_root", "clean_root", "raw_root")})


def resolve(value, reg):
    text = str(value)
    for name in ("CODE_ROOT", "CLEAN_ROOT", "RAW_ROOT"):
        text = text.replace("<" + name + ">", str(getattr(reg, name.lower())))
    if "<" in text or ">" in text:
        raise ValueError("Unresolved path alias")
    return Path(text)


def pinned(spec, reg):
    path = resolve(spec["path"], reg)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing/symlink pinned input: " + str(path))
    if path.name.lower().startswith("trace_") or path.suffix.lower() in (".bag", ".fpl"):
        raise ValueError("Reference/capture hashing prohibited in parent")
    if sha256_file(path) != spec["sha256"]:
        raise ValueError("Pinned hash mismatch: " + str(path))
    return path


def resolved_pins(value, reg):
    if isinstance(value, dict):
        return {k: str(resolve(v, reg)) if k == "path" else resolved_pins(v, reg)
                for k, v in value.items()}
    if isinstance(value, list):
        return [resolved_pins(v, reg) for v in value]
    return value


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write("\n")


def write_csv(path, rows):
    rows = list(rows)
    fields = list(dict.fromkeys(k for row in rows for k in row)) or ["status"]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, allow_nan=False)
                             if isinstance(v, (dict, list)) else v for k, v in row.items()})


def verify_seal(path, stage):
    seal = json.loads(Path(path).read_text())
    for relative, digest in seal["files_sha256"].items():
        member = Path(relative)
        if member.is_absolute() or ".." in member.parts:
            raise ValueError("Invalid sealed member")
        source = Path(stage) / member
        if source.is_symlink() or sha256_file(source) != digest:
            raise ValueError("Sealed artifact changed: " + relative)
    return seal


def seal_roots(stage, roots, destination, metadata):
    stage = Path(stage)
    files = {}
    for root in roots:
        for path in sorted((stage / root).rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlink in sealing scope")
            if path.is_file():
                files[path.relative_to(stage).as_posix()] = sha256_file(path)
    seal = {**FLAGS, **metadata, "status": "SEALED", "files_sha256": files}
    write_json(stage / destination, seal)
    verify_seal(stage / destination, stage)
    return seal
