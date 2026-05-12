"""N7B2A physical sanity checks for diagnostic contact-state v2.

中文说明：contact v2 必须通过物理合理性审计后才允许进入未来 Go2
velocity/contact weak-prior activation review；本模块不调 solver、不用 trace 调阈值。
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .go2_contact_distribution import percentile


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _ratio(count: int, total: int) -> float:
    return count / total if total else 0.0


def _foot_speed_contact_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[float] = []
    by_foot: dict[str, list[float]] = {f"foot_{foot}": [] for foot in range(4)}
    for row in rows:
        for foot in range(4):
            if int(_f(row.get(f"foot_{foot}_contact_v2"), 0.0)) != 1:
                continue
            speed = _f(row.get(f"foot_{foot}_speed_norm"))
            if math.isfinite(speed):
                values.append(speed)
                by_foot[f"foot_{foot}"].append(speed)
    return {
        "count": len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "by_foot": {
            foot: {"p50": percentile(items, 50), "p95": percentile(items, 95), "count": len(items)}
            for foot, items in by_foot.items()
        },
    }


def _alternating_ratio(rows: list[dict[str, Any]]) -> float | None:
    walking = [row for row in rows if row.get("contact_label_v2") == "walking_contact"]
    if not walking:
        return None
    plausible = 0
    for row in walking:
        left = int(_f(row.get("foot_0_contact_v2"), 0.0)) + int(_f(row.get("foot_2_contact_v2"), 0.0))
        right = int(_f(row.get("foot_1_contact_v2"), 0.0)) + int(_f(row.get("foot_3_contact_v2"), 0.0))
        contact_count = int(_f(row.get("contact_count_v2"), 0.0))
        if 1 <= contact_count <= 3 and left != right:
            plausible += 1
    return plausible / len(walking)


def analyze_contact_v2_physical_sanity(
    contact_v2_rows: list[dict[str, Any]],
    *,
    distribution_report: dict[str, Any],
    velocity_segment_report: dict[str, Any],
) -> dict[str, Any]:
    total = len(contact_v2_rows)
    labels = Counter(str(row.get("contact_label_v2", "unknown")) for row in contact_v2_rows)
    walking_ratio = _ratio(labels["walking_contact"], total)
    standing_ratio = _ratio(labels["standing_contact"], total)
    swing_ratio = _ratio(labels["swing_phase"], total)
    uncertain_ratio = _ratio(labels["uncertain"] + labels["invalid"], total)
    contact_ratio = standing_ratio + walking_ratio
    all_feet_contact_rows = sum(1 for row in contact_v2_rows if int(_f(row.get("contact_count_v2"), 0.0)) == 4)
    all_feet_contact_ratio = _ratio(all_feet_contact_rows, total)
    per_foot = {
        f"foot_{foot}": _ratio(sum(1 for row in contact_v2_rows if int(_f(row.get(f"foot_{foot}_contact_v2"), 0.0)) == 1), total)
        for foot in range(4)
    }
    alternating = _alternating_ratio(contact_v2_rows)
    speed_stats = _foot_speed_contact_stats(contact_v2_rows)
    p50 = speed_stats.get("p50")
    p95 = speed_stats.get("p95")
    high_contact_speed = (
        (isinstance(p50, (int, float)) and float(p50) > 0.8)
        or (isinstance(p95, (int, float)) and float(p95) > 2.0)
    )
    all_contact_suspect = contact_ratio >= 0.995 and walking_ratio > 0.5
    low_alternating = alternating is not None and alternating < 0.3
    contact_too_permissive = bool(all_contact_suspect or high_contact_speed or low_alternating)
    contact_too_conservative = uncertain_ratio > 0.5
    if contact_too_conservative:
        status = "review_or_not_ready"
    elif contact_too_permissive:
        status = "review_or_not_ready"
    else:
        status = "plausible"
    return {
        "stage": "N7B2A_go2_metric_contact_visual_audit",
        "contact_rows": total,
        "contact_ratio": contact_ratio,
        "contact_ratio_all_feet": all_feet_contact_ratio,
        "standing_contact_ratio": standing_ratio,
        "walking_contact_ratio": walking_ratio,
        "swing_ratio": swing_ratio,
        "uncertain_ratio": uncertain_ratio,
        "per_foot_contact_ratios": per_foot,
        "alternating_contact_ratio": alternating,
        "foot_speed_during_contact": speed_stats,
        "walking_contact_plausibility": "review" if low_alternating else "plausible",
        "all_contact_suspect": all_contact_suspect,
        "contact_too_permissive": contact_too_permissive,
        "contact_too_conservative": contact_too_conservative,
        "physical_plausibility_status": status,
        "field_quality_status": distribution_report.get("field_quality_status"),
        "velocity_segment_readiness_status": velocity_segment_report.get("readiness_status"),
        "go2_field_distribution_only": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_contact_v2_physical_sanity_report(
    contact_v2_rows: list[dict[str, Any]],
    *,
    distribution_report: dict[str, Any],
    velocity_segment_report: dict[str, Any],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = analyze_contact_v2_physical_sanity(
        contact_v2_rows,
        distribution_report=distribution_report,
        velocity_segment_report=velocity_segment_report,
    )
    path = out / "GO2_CONTACT_V2_PHYSICAL_SANITY_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
