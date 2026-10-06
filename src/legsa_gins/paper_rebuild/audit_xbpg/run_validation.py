"""Validate retained GNSS outputs without treating exit zero as a solution."""
from __future__ import annotations

import csv
import math
from pathlib import Path


def validate_output(directory: Path, kind: str) -> dict:
    try:
        return _validate_output(directory, kind)
    except (OSError, UnicodeError, csv.Error) as exc:
        return {"kind": kind, "file_present": True, "rows": 0, "finite_rows": 0, "times": [],
                "quality_counts": {}, "errors": [f"READ_EXCEPTION:{type(exc).__name__}:{exc}"]}


def _validate_output(directory: Path, kind: str) -> dict:
    name = {"rtk": "solution.pos", "rd": "doppler_ecef.csv"}[kind]
    path = directory / name
    result = {"kind": kind, "file_present": path.is_file(), "rows": 0,
              "finite_rows": 0, "errors": [], "times": [], "quality_counts": {}}
    if not path.is_file():
        result["errors"].append("MISSING_OUTPUT")
        return result
    with path.open(newline="", encoding="utf-8", errors="strict") as stream:
        if kind == "rtk":
            header_ok = any(line.startswith("%") and "GPST" in line and "e-baseline(m)" in line for line in stream)
            if not header_ok:
                result["errors"].append("BAD_HEADER")
            stream.seek(0)
            rows = ((i, row) for i, row in enumerate(csv.reader(stream, strict=True), 1)
                    if row and not row[0].lstrip().startswith("%"))
            width = 15  # GPST week,tow,E,N,U,Q,ns,6 covariance terms,age,ratio.
        else:
            reader = csv.reader(stream, strict=True)
            header = next(reader, [])
            expected = ["time", "vecef_x", "vecef_y", "vecef_z", "std_vx", "std_vy", "std_vz",
                        "sat_count", "doppler_obs_count", "provider_status", "source_epoch_time", "quality_flag"]
            if header != expected:
                result["errors"].append("BAD_HEADER")
            rows = enumerate(reader, 2)
            width = 12
        for line, row in rows:
            result["rows"] += 1
            if len(row) != width:
                result["errors"].append(f"LINE_{line}:COLUMN_COUNT_{len(row)}")
                continue
            try:
                numeric = [float(x) for j, x in enumerate(row) if kind == "rtk" or j != 9]
            except ValueError:
                result["errors"].append(f"LINE_{line}:NOT_NUMERIC")
                continue
            if not all(math.isfinite(x) for x in numeric):
                result["errors"].append(f"LINE_{line}:NONFINITE")
                continue
            if kind == "rtk":
                if numeric[0] % 1 or not 0 <= numeric[1] < 604800 or numeric[5] not in range(1, 7):
                    result["errors"].append(f"LINE_{line}:BAD_WEEK_TOW_OR_QUALITY")
                    continue
                if any(numeric[j] < 0 for j in (7, 8, 9)):
                    result["errors"].append(f"LINE_{line}:NEGATIVE_STD")
                    continue
                epoch = numeric[0] * 604800 + numeric[1]
                q = str(int(numeric[5]))
                result["quality_counts"][q] = result["quality_counts"].get(q, 0) + 1
            else:
                epoch = numeric[0]
                if row[9].strip() != "available" or any(float(row[j]) % 1 or float(row[j]) < 0 for j in (7, 8, 11)):
                    result["errors"].append(f"LINE_{line}:BAD_RD_STATUS_OR_COUNT")
                    continue
                if abs(float(row[10]) - epoch) > .0011:
                    result["errors"].append(f"LINE_{line}:INCONSISTENT_SOURCE_TIME")
                    continue
                if any(float(row[j]) < 0 for j in (4, 5, 6)):
                    result["errors"].append(f"LINE_{line}:NEGATIVE_STD")
                    continue
            result["finite_rows"] += 1
            result["times"].append(epoch)
    if any(b <= a for a, b in zip(result["times"], result["times"][1:])):
        result["errors"].append("DUPLICATE_OR_NONMONOTONIC_OUTPUT_TIME")
    return result


def terminal_status(receipt: dict, validation: dict) -> str:
    """Preserve process failure priority and distinguish valid empty output."""
    if receipt.get("status") in {"TIMEOUT", "LAUNCH_ERROR", "ACCESS_AUDIT_MISSING", "FORBIDDEN_REFERENCE_ACCESS"}:
        return receipt["status"]
    rc = receipt.get("returncode")
    if validation["kind"] == "rd" and rc == 4:
        return "INPUT_NAV_READ_FAILED"
    if validation["kind"] == "rd" and rc == 6 and not validation["errors"] and validation["rows"] == 0:
        return "NO_USABLE_DOPPLER_SOLUTION"
    if rc != 0:
        return "PROCESS_FAILURE"
    if validation["errors"]:
        return "INVALID_OUTPUT"
    return "NO_SOLUTION" if validation["finite_rows"] == 0 else "OUTPUT_REQUIRES_SUPPORT_CHECK"


def permits_full_after_smoke(status: str) -> bool:
    # A valid zero-solution smoke cannot select a good window or suppress other data.
    return status in {"NO_SOLUTION", "OUTPUT_REQUIRES_SUPPORT_CHECK"}
