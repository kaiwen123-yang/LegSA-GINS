"""Resolve all sequences identically, without opening reference traces."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import yaml

LOCAL_CONFIG = Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")
REGISTRY = Path("configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml")
CALIBRATED_CONTRACT = Path("configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml")
STAGE = "CLEAN7_HEXT_EXTERNAL_SEQUENCES"


@dataclass(frozen=True)
class SequencePaths:
    sequence_id: str
    raw_root: Path
    clean_root: Path
    code_root: Path
    hext_scratch: Path
    output_root: Path
    gnss1_raw: Path
    gnss2_raw: Path
    go2_body: Path
    trace: Path
    trace_sha256: str
    base_time: float
    window: tuple[float, float]
    baseline_median_m: float
    hash_lock: Path
    hash_lock_sha256: str
    hash_lock_note: str


def _under(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Registry paths must be root-relative without traversal")
    # No stat/read/hash of trace is needed for path resolution.
    return root / path


def load_sequence_paths(sequence_id: str, local_config: Path = LOCAL_CONFIG,
                        registry_path: Path = REGISTRY,
                        calibrated_contract_path: Path = CALIBRATED_CONTRACT) -> SequencePaths:
    local = yaml.safe_load(Path(local_config).read_text())["paths"]
    registry = yaml.safe_load(Path(registry_path).read_text())["sequences"][sequence_id]
    contracts = yaml.safe_load(Path(calibrated_contract_path).read_text())["sequences"]
    record = contracts[sequence_id]
    raw, clean, code = (Path(local[k]) for k in ("raw_root", "clean_root", "code_root"))
    fix = _under(raw, registry["fix_prefix"])
    trace = _under(fix, registry["trace_name"])
    declared_trace = str(record["trace"]["path"]).replace("<RAW_ROOT>", str(raw))
    if trace != Path(declared_trace):
        raise ValueError("Registry trace identity disagrees with frozen contract")
    lock_record = contracts["BY2H"]["raw_lock"]
    lock = Path(lock_record["path"].replace("<CLEAN_ROOT>", str(clean)))
    note = "CLEAN5_LOCK"
    # The CLEAN5 extension lock has 44 H/O rows and contains no BY2 rows.
    # Preserve it unchanged; use the original BY2 lock already frozen in the
    # same calibrated execution contract for the control sequence only.
    if sequence_id == "BY2":
        with lock.open(encoding="utf-8-sig", newline="") as handle:
            relative_paths = {r["relative_path"] for r in csv.DictReader(handle)}
        if registry["go2_body"] not in relative_paths:
            lock_record = record["raw_lock"]
            lock = Path(lock_record["path"].replace("<CLEAN_ROOT>", str(clean)))
            note = "BY2_ORIGINAL_LOCK_CLEAN5_EXTENSION_HAS_NO_BY2_ROWS"
    return SequencePaths(sequence_id, raw, clean, code, Path(local["hext_scratch"]),
                         clean / "stages" / STAGE, fix / "gnss1-raw.csv",
                         fix / "gnss2-raw.csv", _under(raw, registry["go2_body"]),
                         trace, record["trace"]["sha256"], float(record["base_time"]),
                         tuple(map(float, record["window_seconds"])),
                         float(record["baseline_median_m"]), lock,
                         lock_record["sha256"], note)


def alias_path(path: Path, sequence: SequencePaths) -> str:
    for alias, root in (("<RAW_ROOT>", sequence.raw_root), ("<CLEAN_ROOT>", sequence.clean_root),
                        ("<HEXT_SCRATCH>", sequence.hext_scratch), ("<CODE_ROOT>", sequence.code_root)):
        if path == root or root in path.parents:
            return alias + "/" + path.relative_to(root).as_posix()
    return str(path)
