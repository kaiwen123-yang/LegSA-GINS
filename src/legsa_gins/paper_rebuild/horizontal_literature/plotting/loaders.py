"""Small read-only loaders for frozen CSV and JSON evidence."""

from __future__ import annotations

import csv
import gzip
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PlotSourceError(RuntimeError):
    status = "FAILED_SOURCE"


class SourceMissing(PlotSourceError):
    status = "BLOCKED_MISSING_SOURCE_FILE"


class MissingSourceField(PlotSourceError):
    status = "SKIPPED_MISSING_SOURCE_FIELD"


class IdentityMismatch(PlotSourceError):
    status = "BLOCKED_RESULT_IDENTITY_MISMATCH"


class SchemaConflict(PlotSourceError):
    status = "FAILED_SOURCE_SCHEMA_CONFLICT"


@dataclass(frozen=True)
class FrozenTable:
    source: Path
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


def _coerce(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped == "":
        return None
    if stripped.upper() in {"NA", "N/A", "NULL", "NONE", "NAN"}:
        return None
    lower = stripped.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        result = float(stripped)
        if math.isfinite(result):
            return int(result) if result.is_integer() and not any(c in stripped.lower() for c in (".", "e")) else result
    except ValueError:
        pass
    return stripped


def _flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flat.update(_flatten_json(child, child_prefix))
    elif isinstance(value, list):
        flat[prefix] = json.dumps(value, separators=(",", ":"), sort_keys=True)
    else:
        flat[prefix] = value
    return flat


def load_frozen_table(path: Path, required_fields: tuple[str, ...]) -> FrozenTable:
    if not path.is_file():
        raise SourceMissing(f"source file missing: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv" or path.name.endswith(".csv.gz"):
        stream_context = (
            gzip.open(path, mode="rt", newline="", encoding="utf-8-sig", errors="replace")
            if path.name.endswith(".gz")
            else path.open(mode="rt", newline="", encoding="utf-8-sig", errors="replace")
        )
        with stream_context as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise SchemaConflict(f"CSV has no header: {path}")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise SchemaConflict(f"CSV has duplicate columns: {path}")
            columns = tuple(reader.fieldnames)
            selected = required_fields or columns
            rows = tuple(
                {key: _coerce(row.get(key)) for key in selected}
                for row in reader
            )
    elif suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise SchemaConflict(f"invalid JSON: {path}: {exc}") from exc
        if isinstance(payload, list):
            rows = tuple(_flatten_json(item) if isinstance(item, dict) else {"value": item} for item in payload)
        elif isinstance(payload, dict):
            rows = (_flatten_json(payload),)
        else:
            rows = ({"value": payload},)
        columns = tuple(sorted({key for row in rows for key in row}))
    else:
        raise SchemaConflict(f"unsupported frozen source format {suffix}: {path}")
    missing = [field for field in required_fields if field not in columns]
    if missing:
        raise MissingSourceField(
            f"source {path} lacks required field(s): {', '.join(missing)}"
        )
    if not rows:
        raise MissingSourceField(
            f"source {path} has a header but zero data rows for required field(s): "
            f"{', '.join(required_fields) if required_fields else 'data rows'}"
        )
    entirely_unpopulated = [
        field for field in required_fields if all(row.get(field) is None for row in rows)
    ]
    if entirely_unpopulated:
        raise MissingSourceField(
            f"source {path} has required field(s) but no populated finite value: "
            f"{', '.join(entirely_unpopulated)}"
        )
    return FrozenTable(source=path, columns=columns, rows=rows)


def finite_values(table: FrozenTable, field: str) -> list[float]:
    values: list[float] = []
    for row in table.rows:
        value = row.get(field)
        if isinstance(value, bool):
            values.append(float(value))
        elif isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def categorical_values(table: FrozenTable, field: str) -> list[str]:
    return [str(row[field]) for row in table.rows if row.get(field) is not None]
