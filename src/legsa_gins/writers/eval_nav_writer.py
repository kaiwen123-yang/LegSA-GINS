"""EVAL_NAV writer contract for standardized evaluation outputs."""

import csv
from pathlib import Path
from typing import Iterable


EVAL_NAV_COLUMNS = [
    "timestamp",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn_mps",
    "ve_mps",
    "vd_mps",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "status",
    "source_role",
]


def write_eval_nav(rows: list[dict], output_path: str | Path) -> None:
    validated_rows = _validate_rows(rows)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVAL_NAV_COLUMNS)
        writer.writeheader()
        writer.writerows(validated_rows)


def validate_eval_nav_file(path: str | Path) -> bool:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"EVAL_NAV file does not exist: {file_path}")

    with file_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != EVAL_NAV_COLUMNS:
            raise ValueError(
                "EVAL_NAV header mismatch. Expected "
                f"{EVAL_NAV_COLUMNS}, got {reader.fieldnames}."
            )
        rows = list(reader)

    if not rows:
        raise ValueError("EVAL_NAV file must contain at least one data row.")
    _validate_rows(rows)
    return True


def _validate_rows(rows: Iterable[dict]) -> list[dict]:
    rows_list = list(rows)
    previous_timestamp: float | None = None
    validated: list[dict] = []
    for index, row in enumerate(rows_list):
        missing = [column for column in EVAL_NAV_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"EVAL_NAV row {index} is missing fields: {missing}")

        extra = sorted(set(row) - set(EVAL_NAV_COLUMNS))
        if extra:
            raise ValueError(
                f"EVAL_NAV row {index} contains non-contract/raw fields: {extra}"
            )

        try:
            timestamp = float(row["timestamp"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"EVAL_NAV row {index} has non-float timestamp.") from exc

        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise ValueError("EVAL_NAV timestamp must be monotonically non-decreasing.")
        previous_timestamp = timestamp
        validated.append(row)

    return validated
