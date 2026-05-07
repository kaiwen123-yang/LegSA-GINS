"""BY2 trace reference adapter.

中文说明：trace 只能作为 evaluation-only reference；禁止作为 solver input，禁止用于 tuning，禁止用于 output-only correction。
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ["time", "lat", "lon", "height", "yaw", "pitch", "roll"]
STANDARD_HEADER = [
    "timestamp",
    "lat_deg",
    "lon_deg",
    "height_m",
    "yaw_deg",
    "pitch_deg",
    "roll_deg",
    "source_role",
    "trace_solver_input",
    "trace_evaluation_only",
]


def _require_header(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise ValueError("Trace reference CSV is missing a header.")
    missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(f"Trace reference CSV missing required fields: {missing}")


def _as_float(value: str | None, field: str) -> float:
    if value is None or value.strip() == "":
        raise ValueError(f"Trace reference field {field} is empty.")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Trace reference field {field} is not numeric: {value}") from exc


def parse_trace_reference(path: str | Path, *, max_rows: int | None = None) -> list[dict[str, Any]]:
    """Parse trace into standardized eval-only rows."""
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_header(reader.fieldnames)
        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            rows.append(
                {
                    "timestamp": _as_float(row.get("time"), "time"),
                    "lat_deg": _as_float(row.get("lat"), "lat"),
                    "lon_deg": _as_float(row.get("lon"), "lon"),
                    "height_m": _as_float(row.get("height"), "height"),
                    "yaw_deg": _as_float(row.get("yaw"), "yaw"),
                    "pitch_deg": _as_float(row.get("pitch"), "pitch"),
                    "roll_deg": _as_float(row.get("roll"), "roll"),
                    "source_role": "evaluation_reference",
                    "trace_solver_input": False,
                    "trace_evaluation_only": True,
                }
            )
    return rows


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def write_trace_eval_reference(rows: list[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARD_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in STANDARD_HEADER})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="BY2 trace_vrtk2_*.csv input.")
    parser.add_argument("--output", required=True, help="Eval-only trace CSV output path.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row limit for probes.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rows = parse_trace_reference(args.input, max_rows=args.max_rows)
    write_trace_eval_reference(rows, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
