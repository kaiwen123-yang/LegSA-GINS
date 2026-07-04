"""Schema probes for BY2 receiver raw/status CSV files."""

from __future__ import annotations

import csv
from pathlib import Path


def probe_csv(path: str | Path, *, sample_rows: int = 3) -> dict[str, object]:
    path = Path(path)
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if index >= sample_rows:
                break
            rows.append({key: (value or "")[:160] for key, value in row.items()})
        fieldnames = reader.fieldnames or []
    return {
        "file_name": path.name,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "column_count": len(fieldnames),
        "columns": fieldnames,
        "sample_rows": rows,
    }


def probe_receiver_root(receiver_root: str | Path) -> list[dict[str, object]]:
    root = Path(receiver_root)
    names = [
        "gnss1-status.csv",
        "gnss2-status.csv",
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "corr-raw.csv",
        "userio-raw.csv",
    ]
    return [probe_csv(root / name) for name in names if (root / name).exists()]
