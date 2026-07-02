"""Lightweight raw GNSS provider summaries for two-receiver methods."""

from __future__ import annotations

import csv
from pathlib import Path


def summarize_raw_file(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    return {"file_name": path.name, "row_count": str(rows), "column_count": str(len(header)), "header_detected": str(bool(header)).lower()}


def summarize_raw_dual_receiver(gnss1_raw: Path, gnss2_raw: Path, corr_raw: Path) -> list[dict[str, str]]:
    rows = [summarize_raw_file(path) for path in (gnss1_raw, gnss2_raw, corr_raw)]
    for row in rows:
        row["provider_note"] = "raw_payload_available_for_feasibility; no RTKLIB solution substituted"
    return rows
