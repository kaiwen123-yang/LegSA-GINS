"""Summary helpers for DA2R2 row-level results."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean


def method_level_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["method_id"]].append(row)
    out: list[dict[str, str]] = []
    for method_id, items in sorted(grouped.items()):
        completed = [row for row in items if row["completed_evaluable"] == "true"]
        out.append(
            {
                "method_id": method_id,
                "planned_rows": str(len(items)),
                "completed_evaluable": str(len(completed)),
                "failed_runtime": str(sum(row["terminal_status"] == "FAILED_RUNTIME_WITH_LOG" for row in items)),
                "blocked_with_proof": str(sum(row["terminal_status"] == "BLOCKED_WITH_PROOF" for row in items)),
                "mean_yaw_rmse_deg": _mean_float(completed, "yaw_rmse_deg"),
                "mean_horizontal_rmse_m": _mean_float(completed, "horizontal_rmse_m"),
                "reproduction_type": completed[0]["reproduction_type"] if completed else items[0].get("reproduction_type", ""),
                "claim_level": completed[0]["claim_level"] if completed else items[0].get("claim_level", ""),
            }
        )
    return out


def case_family_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["method_id"], row["case_family"])].append(row)
    out: list[dict[str, str]] = []
    for (method_id, family), items in sorted(grouped.items()):
        completed = [row for row in items if row["completed_evaluable"] == "true"]
        out.append(
            {
                "method_id": method_id,
                "case_family": family,
                "completed_evaluable": str(len(completed)),
                "mean_yaw_rmse_deg": _mean_float(completed, "yaw_rmse_deg"),
                "mean_horizontal_rmse_m": _mean_float(completed, "horizontal_rmse_m"),
            }
        )
    return out


def _mean_float(rows: list[dict[str, str]], key: str) -> str:
    values = []
    for row in rows:
        try:
            values.append(float(row[key]))
        except (KeyError, TypeError, ValueError):
            pass
    return f"{mean(values):.6f}" if values else "not_applicable"
