"""HX-02 sequence adaptation layer: one contract-declared sequence per native run.

Everything sequence-specific (raw streams, hash lock, base_time, window, start
convention, pair counts, antenna-midpoint baseline) is read from the registered
sequence registry, the frozen calibrated execution contract, H_EXT_CONTRACT_V1
and HX02_CONTRACT_V1. Nothing here opens a reference trajectory; the trace path
is carried as a string for the registered evaluator children only.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .sequence_paths import load_sequence_paths

HX02_CONTRACT = Path("configs/paper_rebuild/hext/HX02_CONTRACT_V1.yaml")
H_EXT_CONTRACT = Path("configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml")
GPS_EPOCH_UNIX = 315964800.0
WEEK_SECONDS = 604800.0
SPEC_SCHEMA = "hx02.sequence_spec.v1"


class SequenceAdaptationError(RuntimeError):
    """Sequence identity or pairing contract violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class HX02Sequence:
    sequence_id: str
    data_mode: str
    raw_root: str
    clean_root: str
    code_root: str
    fix_root: str
    gnss1_raw: str
    gnss2_raw: str
    go2_body: str
    raw_hash_lock: str
    raw_hash_lock_sha256: str
    trace_path_evaluator_only: str
    trace_sha256: str
    base_time: float
    window: tuple[float, float]
    baseline_median_m: float
    start_convention: str
    native_start_rel_s: float | None
    registered_rawx_epochs: int
    gps_week: int
    leap_seconds: int

    def to_json(self) -> dict[str, Any]:
        value = asdict(self)
        value["window"] = list(self.window)
        return value


def load_contract(path: Path = HX02_CONTRACT) -> dict[str, Any]:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != "hx02.five_category.contract.v1":
        raise SequenceAdaptationError("HX-02 contract schema mismatch")
    return document


def load_sequence(sequence_id: str, contract: Mapping[str, Any] | None = None) -> HX02Sequence:
    contract = load_contract() if contract is None else contract
    declared = contract["sequences"][sequence_id]
    paths = load_sequence_paths(sequence_id)
    hext = yaml.safe_load(H_EXT_CONTRACT.read_text(encoding="utf-8"))["sequences"][sequence_id]
    registry = yaml.safe_load(Path("configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml").read_text(
        encoding="utf-8"))["sequences"][sequence_id]
    if tuple(map(float, declared["window"])) != tuple(paths.window):
        raise SequenceAdaptationError("HX-02 window disagrees with the frozen sequence contract")
    if float(declared["base_time"]) != float(paths.base_time):
        raise SequenceAdaptationError("HX-02 base_time disagrees with the frozen sequence contract")
    if float(declared["baseline_median_m"]) != float(paths.baseline_median_m):
        raise SequenceAdaptationError("HX-02 b_med disagrees with the frozen sequence contract")
    if int(declared["registered_rawx_epochs"]) != int(hext["expected"]["rawx_epochs"]):
        raise SequenceAdaptationError("HX-02 RAWX epoch count disagrees with H_EXT_CONTRACT_V1")
    convention = declared["start_convention"]
    if convention not in ("FILE_START", "CONTRACT_START"):
        raise SequenceAdaptationError("unknown start convention")
    start = float(paths.window[0]) if convention == "CONTRACT_START" else None
    return HX02Sequence(
        sequence_id=sequence_id, data_mode=registry["data_mode"],
        raw_root=str(paths.raw_root), clean_root=str(paths.clean_root), code_root=str(paths.code_root),
        fix_root=str(paths.gnss1_raw.parent), gnss1_raw=str(paths.gnss1_raw), gnss2_raw=str(paths.gnss2_raw),
        go2_body=str(paths.go2_body), raw_hash_lock=str(paths.hash_lock),
        raw_hash_lock_sha256=str(paths.hash_lock_sha256),
        trace_path_evaluator_only=str(paths.trace), trace_sha256=str(paths.trace_sha256),
        base_time=float(paths.base_time), window=tuple(map(float, paths.window)),
        baseline_median_m=float(paths.baseline_median_m), start_convention=convention,
        native_start_rel_s=start, registered_rawx_epochs=int(hext["expected"]["rawx_epochs"]),
        gps_week=int(hext["expected"]["gps_week"]), leap_seconds=int(hext["expected"]["leap_seconds"]))


def lock_rows(lock: Path) -> dict[str, dict[str, str]]:
    with Path(lock).open(encoding="utf-8-sig", newline="") as handle:
        return {row["relative_path"].replace("\\", "/"): row for row in csv.DictReader(handle)}


def verify_raw(sequence: HX02Sequence, *names: str) -> dict[str, dict[str, Any]]:
    """Size and SHA-256 of declared raw inputs against the registered hash lock."""
    lock = Path(sequence.raw_hash_lock)
    if sha256_file(lock) != sequence.raw_hash_lock_sha256:
        raise SequenceAdaptationError("raw hash lock identity mismatch")
    rows = lock_rows(lock)
    result = {}
    for name in names:
        path = Path(getattr(sequence, name))
        if "trace" in path.name.lower():
            raise SequenceAdaptationError("reference trajectory is outside the raw-input scope")
        relative = path.relative_to(Path(sequence.raw_root)).as_posix()
        row = rows.get(relative)
        if row is None:
            raise SequenceAdaptationError(f"raw input absent from lock: {relative}")
        digest = sha256_file(path)
        if digest != row["sha256"] or path.stat().st_size != int(row["size_bytes"]):
            raise SequenceAdaptationError(f"raw input hash-lock mismatch: {relative}")
        result[name] = {"relative_path": relative, "sha256": digest, "size_bytes": path.stat().st_size}
    return result


def unix_time(week: int, tow_seconds: float, leap_seconds: int) -> float:
    return GPS_EPOCH_UNIX + int(week) * WEEK_SECONDS + float(tow_seconds) - int(leap_seconds)


def select_pairs(sequence: HX02Sequence | Mapping[str, Any], pairs):
    """CONTRACT_START keeps exact pairs whose receiver-1 RAWX time is at/after the start."""
    get = (lambda key: sequence[key]) if isinstance(sequence, Mapping) else (lambda key: getattr(sequence, key))
    start = get("native_start_rel_s")
    if start is None:
        return list(pairs)
    base_time = float(get("base_time"))
    return [pair for pair in pairs
            if unix_time(pair[0].gps_week, pair[0].gps_tow_seconds, pair[0].leap_seconds) - base_time >= float(start)]


def pairing_inventory(sequence: HX02Sequence) -> dict[str, Any]:
    """Exact RAWX pairing of the two receivers; raw GNSS only (no reference, no HPPOSECEF)."""
    from ..horizontal_literature.shared_raw_backend import pair_epochs, reconstruct_ubx_stream

    raw = verify_raw(sequence, "gnss1_raw", "gnss2_raw")
    first = reconstruct_ubx_stream(Path(sequence.gnss1_raw), decode_nav_hpposecef_semantics=False)
    second = reconstruct_ubx_stream(Path(sequence.gnss2_raw), decode_nav_hpposecef_semantics=False)
    pairs, failures = pair_epochs(first.rawx_epochs, second.rawx_epochs, tolerance_seconds=0.0)
    selected = select_pairs(sequence, pairs)
    relative = [unix_time(a.gps_week, a.gps_tow_seconds, a.leap_seconds) - sequence.base_time for a, _ in selected]
    start, end = sequence.window
    weeks = sorted({a.gps_week for a, _ in pairs})
    leaps = sorted({e.leap_seconds for e in (*first.rawx_epochs, *second.rawx_epochs)})
    return {
        "sequence_id": sequence.sequence_id, "raw_inputs": raw,
        "rawx_epochs": [len(first.rawx_epochs), len(second.rawx_epochs)],
        "exact_pairs_full_file": len(pairs), "pairing_failures": len(failures),
        "start_convention": sequence.start_convention, "native_start_rel_s": sequence.native_start_rel_s,
        "selected_pairs": len(selected),
        "selected_first_rel_s": relative[0] if relative else None,
        "selected_last_rel_s": relative[-1] if relative else None,
        "window": list(sequence.window),
        "selected_pairs_in_window": sum(1 for value in relative if start <= value <= end),
        "gps_weeks": weeks, "leap_seconds": leaps,
        "registered_rawx_epochs": sequence.registered_rawx_epochs,
        "matches_registered_rawx_epochs": len(pairs) == sequence.registered_rawx_epochs and not failures,
        "reference_opened": False,
    }


def write_spec(path: Path, payload: Mapping[str, Any]) -> str:
    """Write a new run spec (never overwrite) and return its SHA-256."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps({"schema": SPEC_SCHEMA, **payload}, indent=2, sort_keys=True) + "\n")
    return sha256_file(path)


def go2_prefix_inventory(sequence: HX02Sequence) -> dict[str, Any]:
    """Complete-record prefix of the Go2 high-level log (records end at a '---' line).

    The prefix ends right after the last '---' line; a trailing partial record is
    excluded exactly as for the frozen BY2 prefix. Raw body log only.
    """
    raw = verify_raw(sequence, "go2_body")
    path = Path(sequence.go2_body)
    separators = 0
    stamps = 0
    prefix_end = 0
    offset = 0
    with path.open("rb") as handle:
        for line in handle:
            offset += len(line)
            stripped = line.strip()
            if stripped == b"---":
                separators += 1
                prefix_end = offset
            elif line.startswith(b"stamp:"):
                stamps += 1
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        remaining = prefix_end
        while remaining:
            block = handle.read(min(1 << 20, remaining))
            if not block:
                raise SequenceAdaptationError("Go2 log shorter than its computed prefix")
            digest.update(block)
            remaining -= len(block)
    return {"sequence_id": sequence.sequence_id, "raw": raw["go2_body"], "size_bytes": offset,
            "record_separator_count": separators, "stamp_line_count": stamps,
            "prefix_end_exclusive": prefix_end, "prefix_sha256": digest.hexdigest(),
            "tail_bytes": offset - prefix_end, "rule": "PREFIX_ENDS_AFTER_LAST_RECORD_SEPARATOR_LINE"}
