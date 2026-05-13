"""N7C5A visual data loader for Go2 full proprioceptive review.

中文说明：本模块只读取 N7C5 runtime 输出作为图像复核数据源；Go2 本体字段
仍是 observation，不是 truth，也不把 trace/final_v23 输出作为 solver input。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _summary_contact_rows(contact_report: dict[str, Any], time_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build summary-only contact rows when N7C5 stores report stats but not raw contact timeseries."""

    foot_stats = contact_report.get("foot_probability_stats", {})
    times = [_f(row.get("time"), math.nan) for row in time_rows]
    times = [value for value in times if math.isfinite(value)]
    if not times:
        times = [0.0, 1.0]
    stride = max(1, len(times) // 1000)
    sampled = times[::stride]
    out: list[dict[str, Any]] = []
    for time_value in sampled:
        row: dict[str, Any] = {
            "time": time_value,
            "support_probability": contact_report.get("support_probability_mean", 0.0),
            "uncertainty_probability": contact_report.get("uncertainty_probability_mean", 0.0),
            "swing_probability": contact_report.get("swing_probability_mean", 0.0),
            "summary_only": True,
        }
        for foot in range(4):
            stats = foot_stats.get(f"foot_{foot}_contact_probability", {})
            row[f"foot_{foot}_contact_probability"] = stats.get("mean", 0.0)
            row[f"foot_{foot}_contact_probability_p95"] = stats.get("p95", 0.0)
        out.append(row)
    return out


def load_n7c5_visual_inputs(n7c5_root: str | Path) -> dict[str, Any]:
    root = Path(n7c5_root)
    inventory = read_json(root / "GO2_FULL_FIELD_INVENTORY_REPORT.json")
    contact = read_json(root / "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json")
    foot = read_json(root / "GO2_FOOT_KINEMATIC_VELOCITY_CANDIDATE_REPORT.json")
    phase = read_json(root / "GO2_MODE_GAIT_PHASE_MODEL_REPORT.json")
    yawrate = read_json(root / "GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json")
    relative = read_json(root / "GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json")
    ranking = read_json(root / "GO2_PROPRIOCEPTIVE_FACTOR_RANKING_REPORT.json")
    decision = read_json(root / "N7C5_GO2_FULL_PROPRIOCEPTIVE_FACTOR_DECISION_REPORT.json")
    figure_manifest = read_json(root / "N7C5_FIGURE_MANIFEST.json")
    foot_rows = read_csv_rows(root / "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv")
    phase_rows = read_csv_rows(root / "GO2_MODE_GAIT_PHASE_TIMESERIES.csv")
    contact_rows = read_csv_rows(root / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv")
    if not contact_rows:
        contact_rows = _summary_contact_rows(contact, foot_rows or phase_rows)
    return {
        "stage": "N7C5A_go2_full_proprioceptive_visual_review",
        "n7c5_root_role": "N7C5_REPORT_OUTPUT_DIR",
        "inventory_report": inventory,
        "contact_report": contact,
        "contact_rows": contact_rows,
        "contact_rows_summary_only": bool(contact_rows and contact_rows[0].get("summary_only")),
        "foot_report": foot,
        "foot_rows": foot_rows,
        "phase_report": phase,
        "phase_rows": phase_rows,
        "yawrate_report": yawrate,
        "relative_report": relative,
        "ranking_report": ranking,
        "n7c5_decision": decision,
        "n7c5_figure_manifest": figure_manifest,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
