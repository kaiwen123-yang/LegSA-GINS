"""HX-02 adapters: method-native heading outputs -> one standard heading table per method variant.

Every native paired epoch keeps one row (the evaluator denominator is the native
paired-epoch table inside the window). Validity is the method's own flag:
  EXT01  integer_solution_returned == true (no ambiguity acceptance test exists)
  EXT02  method_native_accepted == true
  EXT03  primary variant GPS_BDS_DUAL_FREQUENCY/CONSTRAINED/0.010, solution_state != invalid;
         paper_ratio_fixed kept as a separate flag
  EXT04  GPS_BDS_DUAL_FREQUENCY rows of FAR_ALL_AMBIGUITIES and of the primary PAR
         policy, accepted_by_policy == true
Body yaw is the method's own body_yaw_deg (baseline heading + 90 deg, GNSS2 - GNSS1).
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import hx02_sequence

CSV_LIMIT = 64 * 1024 * 1024
EXT03_PRIMARY = ("GPS_BDS_DUAL_FREQUENCY", "CONSTRAINED", "0.01")
EXT04_MODE = "GPS_BDS_DUAL_FREQUENCY"
EXT04_POLICIES = {"FAR": "FAR_ALL_AMBIGUITIES", "PAR": "EXT04_PAR_DECLARED_POLICY_V1"}


def _rows(path: Path) -> Iterable[dict[str, str]]:
    previous = csv.field_size_limit()
    csv.field_size_limit(CSV_LIMIT)
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            yield from csv.DictReader(handle)
    finally:
        csv.field_size_limit(previous)


def _row(index: int, source: Mapping[str, str], valid: bool, leap_seconds: int, **extra: Any) -> dict[str, Any]:
    week, tow = int(source["gps_week"]), float(source["gps_tow_seconds"])
    yaw = source.get("body_yaw_deg", "")
    if valid and yaw in ("", None):
        raise ValueError("valid native heading row without body yaw")
    return {"epoch_index": index, "gps_week": week, "gps_tow_seconds": source["gps_tow_seconds"],
            "time_unix_s": repr(hx02_sequence.unix_time(week, tow, leap_seconds)),
            "valid": int(bool(valid)), "body_yaw_deg": yaw if valid or extra.get("keep_yaw") else "",
            **{key: value for key, value in extra.items() if key != "keep_yaw"}}


def ext01(path: Path, leap_seconds: int) -> dict[str, list[dict[str, Any]]]:
    rows = [_row(int(r["epoch_index"]), r, r["integer_solution_returned"] == "true", leap_seconds) for r in _rows(path)]
    return {"EXT01": rows}


def ext02(path: Path, leap_seconds: int) -> dict[str, list[dict[str, Any]]]:
    rows = [_row(int(r["epoch_index"]), r, r["method_native_accepted"] == "true", leap_seconds) for r in _rows(path)]
    return {"EXT02": rows}


def ext03(path: Path, leap_seconds: int) -> dict[str, list[dict[str, Any]]]:
    rows = []
    for r in _rows(path):
        if (r["system_mode"], r["constraint_mode"], r["baseline_sigma_m"]) != EXT03_PRIMARY:
            continue
        rows.append(_row(int(r["epoch_index"]), r, r["solution_state"] != "invalid", leap_seconds,
                         ratio_fixed=int(r["paper_ratio_fixed"] == "true")))
    return {"EXT03": rows}


def ext04(path: Path, leap_seconds: int) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {f"EXT04_{label}": [] for label in EXT04_POLICIES}
    identity = {policy: label for label, policy in EXT04_POLICIES.items()}
    for r in _rows(path):
        if r["system_mode"] != EXT04_MODE or r["policy_identity"] not in identity:
            continue
        tables[f"EXT04_{identity[r['policy_identity']]}"].append(
            _row(int(r["epoch_index"]), r, r["accepted_by_policy"] == "true", leap_seconds))
    for rows in tables.values():
        rows.sort(key=lambda row: row["epoch_index"])
    return tables


ADAPTERS = {"EXT01": ext01, "EXT02": ext02, "EXT03": ext03, "EXT04": ext04}


def write_table(rows: Sequence[Mapping[str, Any]], path: Path) -> str:
    extras = [name for name in ("ratio_fixed", "rtklib_q") if rows and name in rows[0]]
    columns = ["epoch_index", "gps_week", "gps_tow_seconds", "time_unix_s", "valid", "body_yaw_deg", *extras]
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
