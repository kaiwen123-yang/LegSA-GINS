"""Summary table helpers for DA3R2."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def write_csv(rows: list[dict[str, object]], path: str | Path, fieldnames: list[str] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _format(row.get(key)) for key in fieldnames})


def method_level_summary(row_results: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in row_results:
        grouped[str(row["method_id"])].append(row)
    out = []
    for method_id, rows in sorted(grouped.items()):
        full = [row for row in rows if row.get("terminal_status") == "COMPLETED_EVALUABLE_FULL_BACKEND"]
        out.append(
            {
                "method_id": method_id,
                "planned_rows": len(rows),
                "completed_evaluable_full_backend": len(full),
                "mean_yaw_rmse_deg": _mean([row.get("yaw_rmse_deg") for row in full]),
                "mean_yaw_mae_deg": _mean([row.get("yaw_mae_deg") for row in full]),
                "method_passed_18of18_full_backend": len(full) == 18,
            }
        )
    return out


def case_family_summary(row_results: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in row_results:
        grouped[str(row["case_family"])].append(row)
    return [
        {
            "case_family": family,
            "rows": len(rows),
            "completed_evaluable_full_backend": sum(1 for row in rows if row.get("terminal_status") == "COMPLETED_EVALUABLE_FULL_BACKEND"),
            "mean_yaw_rmse_deg": _mean([row.get("yaw_rmse_deg") for row in rows]),
        }
        for family, rows in sorted(grouped.items())
    ]


def final_decision(row_results: list[dict[str, object]], export_clean_pass: bool) -> str:
    completed = sum(1 for row in row_results if row.get("terminal_status") == "COMPLETED_EVALUABLE_FULL_BACKEND")
    passed_methods = {
        row["method_id"]
        for row in row_results
        if sum(1 for item in row_results if item["method_id"] == row["method_id"] and item.get("terminal_status") == "COMPLETED_EVALUABLE_FULL_BACKEND") == 18
    }
    if completed >= 90 and len(passed_methods) >= 5 and export_clean_pass:
        return "PASS_DA3R2_TRUE_DA_MIN5_FULL_BACKEND_COMPLETED_READY_FOR_FINAL_FIGURES"
    if completed >= 54 and len(passed_methods) >= 3 and export_clean_pass:
        return "PASS_DA3R2_TRUE_DA_MIN3_FULL_BACKEND_COMPLETED_READY_FOR_120CASE_OR_FINAL_FIGURES"
    return "BLOCKED_DA3R2_MIN3_FULL_BACKEND_NOT_MET"


def _mean(values: list[object]) -> float | None:
    nums = []
    for value in values:
        try:
            if value is not None:
                nums.append(float(value))
        except (TypeError, ValueError):
            pass
    return sum(nums) / len(nums) if nums else None


def _format(value: object) -> object:
    if isinstance(value, float):
        return f"{value:.6f}"
    if value is None:
        return "not_applicable"
    if isinstance(value, bool):
        return str(value).lower()
    return value
