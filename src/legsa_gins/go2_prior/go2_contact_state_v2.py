"""N7B2 diagnostic Go2 contact-state v2 classifier.

中文说明：V2 classifier 使用 Go2 field distribution threshold、foot speed
support 和 mode/gait hints；结果只写 readiness reports，不启用 solver prior。
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .go2_contact_distribution import velocity_norm
from .go2_contact_state import _f, _foot_speed_norm, _standing_hint, _walking_hint, _time_value


CONTACT_V2_LABELS = ["standing_contact", "walking_contact", "swing_phase", "uncertain", "invalid"]


def _candidate(threshold_report: dict[str, Any]) -> dict[str, Any]:
    candidates = threshold_report.get("candidate_thresholds", {})
    name = threshold_report.get("recommended_candidate", "mode_gait_assisted_contact")
    return candidates.get(name, candidates.get("mode_gait_assisted_contact", {}))


def _threshold(candidate: dict[str, Any], key: str, foot: int, fallback: float) -> float:
    values = candidate.get(key, {})
    value = values.get(f"foot_{foot}") if isinstance(values, dict) else None
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else fallback


def _row_label(row: dict[str, Any], contacts: list[bool | None]) -> str:
    valid_count = sum(1 for item in contacts if item is not None)
    contact_count = sum(1 for item in contacts if item)
    speed = velocity_norm(row)
    standing = _standing_hint(row) or (math.isfinite(speed) and speed < 0.12)
    walking = _walking_hint(row) or (math.isfinite(speed) and speed >= 0.25)
    if valid_count == 0:
        return "invalid"
    if contact_count == 0:
        return "swing_phase" if walking else "uncertain"
    if standing and contact_count >= 3:
        return "standing_contact"
    if walking and contact_count >= 1:
        return "walking_contact"
    if contact_count >= 3 and not walking:
        return "standing_contact"
    return "uncertain"


def _alternating_score(rows: list[dict[str, Any]]) -> float | None:
    walking = [row for row in rows if row.get("contact_label_v2") == "walking_contact"]
    if not walking:
        return None
    plausible = 0
    for row in walking:
        left = int(row.get("foot_0_contact_v2", 0)) + int(row.get("foot_2_contact_v2", 0))
        right = int(row.get("foot_1_contact_v2", 0)) + int(row.get("foot_3_contact_v2", 0))
        if 1 <= int(row.get("contact_count_v2", 0)) <= 3 and left != right:
            plausible += 1
    return plausible / len(walking)


def build_contact_state_v2(
    rows: list[dict[str, Any]],
    threshold_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate = _candidate(threshold_report)
    out_rows: list[dict[str, Any]] = []
    per_foot_counts = [0, 0, 0, 0]
    per_foot_valid = [0, 0, 0, 0]
    for index, row in enumerate(rows):
        contacts: list[bool | None] = []
        for foot in range(4):
            force = _f(row.get(f"foot_force_{foot}"))
            speed = _foot_speed_norm(row, foot)
            force_threshold = _threshold(candidate, "force_threshold_by_foot", foot, 10.0)
            low_force_threshold = _threshold(candidate, "low_force_threshold_by_foot", foot, force_threshold * 0.6)
            speed_threshold = _threshold(candidate, "speed_support_threshold_by_foot", foot, 0.75)
            valid = math.isfinite(force) or math.isfinite(speed)
            if valid:
                per_foot_valid[foot] += 1
            else:
                contacts.append(None)
                continue
            contact = False
            if math.isfinite(force) and force >= force_threshold:
                contact = True
            elif math.isfinite(force) and math.isfinite(speed) and force >= low_force_threshold and speed <= speed_threshold:
                contact = True
            if contact:
                per_foot_counts[foot] += 1
            contacts.append(contact)
        label = _row_label(row, contacts)
        out_rows.append(
            {
                "row_index": index,
                "time": _time_value(row),
                "mode": row.get("mode", ""),
                "gait_type": row.get("gait_type", ""),
                "body_height": row.get("body_height", ""),
                "velocity_norm": velocity_norm(row),
                "contact_label_v2": label,
                "contact_count_v2": sum(1 for item in contacts if item),
                **{f"foot_{foot}_contact_v2": int(bool(contacts[foot])) for foot in range(4)},
                **{f"foot_{foot}_force": _f(row.get(f"foot_force_{foot}")) for foot in range(4)},
                **{f"foot_{foot}_speed_norm": _foot_speed_norm(row, foot) for foot in range(4)},
                "threshold_source": "go2_field_distribution_only",
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "go2_velocity_prior_enabled": False,
                "go2_yaw_prior_enabled": False,
            }
        )
    counts = Counter(row["contact_label_v2"] for row in out_rows)
    total = len(out_rows)
    uncertain_ratio = (counts["uncertain"] + counts["invalid"]) / total if total else 1.0
    contact_ratio = (counts["standing_contact"] + counts["walking_contact"]) / total if total else 0.0
    alternating_score = _alternating_score(out_rows)
    physical_plausibility_status = "insufficient_walking_rows"
    if alternating_score is not None:
        physical_plausibility_status = "plausible" if alternating_score >= 0.35 else "review"
    quality = "ready" if total and uncertain_ratio <= 0.50 and contact_ratio >= 0.20 else "not_ready"
    if physical_plausibility_status == "review":
        quality = "not_ready"
    per_foot_ratio = {
        f"foot_{foot}": (per_foot_counts[foot] / per_foot_valid[foot] if per_foot_valid[foot] else None)
        for foot in range(4)
    }
    report: dict[str, Any] = {
        "stage": "N7B2_go2_contact_threshold_review",
        "contact_rows": total,
        "standing_contact_ratio": counts["standing_contact"] / total if total else 0.0,
        "walking_contact_ratio": counts["walking_contact"] / total if total else 0.0,
        "swing_phase_ratio": counts["swing_phase"] / total if total else 0.0,
        "uncertain_ratio": uncertain_ratio,
        "invalid_ratio": counts["invalid"] / total if total else 1.0,
        "per_foot_contact_ratio": per_foot_ratio,
        "alternating_contact_plausibility_ratio": alternating_score,
        "physical_plausibility_status": physical_plausibility_status,
        "contact_quality_status": quality,
        "contact_labels": CONTACT_V2_LABELS,
        "threshold_source": "go2_field_distribution_only",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return out_rows, report


def write_contact_state_v2_outputs(
    rows: list[dict[str, Any]],
    threshold_report: dict[str, Any],
    output_dir: str | Path,
) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timeseries, report = build_contact_state_v2(rows, threshold_report)
    csv_path = out / "GO2_CONTACT_STATE_V2_TIMESERIES.csv"
    fieldnames = list(timeseries[0].keys()) if timeseries else ["row_index", "time", "contact_label_v2"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(timeseries)
    report_path = out / "GO2_CONTACT_STATE_V2_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, timeseries, report
