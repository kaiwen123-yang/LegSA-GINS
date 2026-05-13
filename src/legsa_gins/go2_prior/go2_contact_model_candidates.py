"""N7B3 diagnostic Go2 contact model candidates.

中文说明：所有 contact model threshold 只来自 Go2 field distributions 和 mode/gait
字段，不读取 trace/final_v23 output，也不把 contact label 写成正式 solver result。
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .go2_contact_distribution import analyze_contact_distribution, percentile, velocity_norm
from .go2_contact_state import _f, _foot_speed_norm, _standing_hint, _time_value, _walking_hint, build_contact_state
from .go2_contact_state_v2 import build_contact_state_v2
from .go2_contact_threshold_review import review_contact_thresholds


MODEL_IDS = [
    "v1_original",
    "v2_force_percentile_existing",
    "v3_force_speed_joint",
    "v4_speed_dominant",
    "v5_gait_mode_windowed",
    "v6_physical_plausibility_filtered",
]


def _stats(values: list[float]) -> dict[str, float | None]:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return {"p50": None, "p95": None, "mean": None, "max": None}
    return {
        "p50": finite[len(finite) // 2],
        "p95": finite[max(0, min(len(finite) - 1, math.ceil(0.95 * len(finite)) - 1))],
        "mean": sum(finite) / len(finite),
        "max": finite[-1],
    }


def _field_distributions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    force_by_foot = {foot: [] for foot in range(4)}
    speed_by_foot = {foot: [] for foot in range(4)}
    for row in rows:
        for foot in range(4):
            force = _f(row.get(f"foot_force_{foot}"))
            speed = _foot_speed_norm(row, foot)
            if math.isfinite(force):
                force_by_foot[foot].append(force)
            if math.isfinite(speed):
                speed_by_foot[foot].append(speed)
    return {
        "force_p25": {foot: percentile(force_by_foot[foot], 25) or 8.0 for foot in range(4)},
        "force_p35": {foot: percentile(force_by_foot[foot], 35) or 10.0 for foot in range(4)},
        "force_p50": {foot: percentile(force_by_foot[foot], 50) or 12.0 for foot in range(4)},
        "force_p65": {foot: percentile(force_by_foot[foot], 65) or 15.0 for foot in range(4)},
        "speed_p20": {foot: percentile(speed_by_foot[foot], 20) or 0.25 for foot in range(4)},
        "speed_p25": {foot: percentile(speed_by_foot[foot], 25) or 0.30 for foot in range(4)},
        "speed_p35": {foot: percentile(speed_by_foot[foot], 35) or 0.40 for foot in range(4)},
        "speed_p50": {foot: percentile(speed_by_foot[foot], 50) or 0.55 for foot in range(4)},
    }


def _label_from_contacts(row: dict[str, Any], contacts: list[bool], *, reject_all_contact_walking: bool = False) -> str:
    count = sum(1 for item in contacts if item)
    standing = _standing_hint(row) or (math.isfinite(velocity_norm(row)) and velocity_norm(row) < 0.12)
    walking = _walking_hint(row) or (math.isfinite(velocity_norm(row)) and velocity_norm(row) >= 0.25)
    if reject_all_contact_walking and walking and count == 4:
        return "uncertain"
    if count == 0:
        return "swing_phase" if walking else "uncertain"
    if standing and count >= 3:
        return "standing_contact"
    if walking and 1 <= count <= 3:
        return "walking_contact"
    if count >= 3:
        return "standing_contact"
    return "uncertain"


def _candidate_rows(
    rows: list[dict[str, Any]],
    *,
    model_id: str,
    distributions: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        contacts: list[bool] = []
        for foot in range(4):
            force = _f(row.get(f"foot_force_{foot}"))
            speed = _foot_speed_norm(row, foot)
            force_p25 = float(distributions["force_p25"][foot])
            force_p35 = float(distributions["force_p35"][foot])
            force_p50 = float(distributions["force_p50"][foot])
            force_p65 = float(distributions["force_p65"][foot])
            speed_p20 = float(distributions["speed_p20"][foot])
            speed_p25 = float(distributions["speed_p25"][foot])
            speed_p35 = float(distributions["speed_p35"][foot])
            speed_p50 = float(distributions["speed_p50"][foot])
            standing = _standing_hint(row)
            walking = _walking_hint(row)
            if model_id == "v3_force_speed_joint":
                contact = math.isfinite(force) and math.isfinite(speed) and force >= force_p50 and speed <= speed_p35
            elif model_id == "v4_speed_dominant":
                contact = math.isfinite(speed) and speed <= speed_p25 and (standing or walking)
            elif model_id == "v5_gait_mode_windowed":
                if standing:
                    contact = math.isfinite(speed) and speed <= speed_p50
                elif walking:
                    contact = math.isfinite(force) and math.isfinite(speed) and force >= force_p35 and speed <= speed_p50
                else:
                    contact = math.isfinite(force) and math.isfinite(speed) and force >= force_p65 and speed <= speed_p35
            elif model_id == "v6_physical_plausibility_filtered":
                contact = math.isfinite(force) and math.isfinite(speed) and (
                    (force >= force_p50 and speed <= speed_p35) or (speed <= speed_p20 and force >= force_p25)
                )
            else:
                contact = math.isfinite(force) and force >= force_p25
            contacts.append(bool(contact))
        label = _label_from_contacts(row, contacts, reject_all_contact_walking=model_id == "v6_physical_plausibility_filtered")
        count = sum(1 for item in contacts if item)
        out.append(
            {
                "candidate_model": model_id,
                "row_index": index,
                "time": _time_value(row),
                "contact_label": label,
                "contact_count": count,
                **{f"foot_{foot}_contact": int(contacts[foot]) for foot in range(4)},
                **{f"foot_{foot}_force": _f(row.get(f"foot_force_{foot}")) for foot in range(4)},
                **{f"foot_{foot}_speed_norm": _foot_speed_norm(row, foot) for foot in range(4)},
                "velocity_norm": velocity_norm(row),
                "threshold_source": "percentile_force+percentile_speed+mode_gait_rule",
                "diagnostic_only": True,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
            }
        )
    return out, _summarize_model(model_id, out)


def _smooth_window(rows: list[dict[str, Any]], *, window: int = 3) -> list[dict[str, Any]]:
    if len(rows) < window:
        return rows
    labels = [row["contact_label"] for row in rows]
    smoothed: list[dict[str, Any]] = []
    half = window // 2
    for index, row in enumerate(rows):
        start = max(0, index - half)
        end = min(len(rows), index + half + 1)
        common = Counter(labels[start:end]).most_common(1)[0][0]
        updated = dict(row)
        updated["contact_label_raw"] = row["contact_label"]
        updated["contact_label"] = common
        updated["threshold_source"] = f"{updated['threshold_source']}+window_smoothing"
        smoothed.append(updated)
    return smoothed


def _alternating_ratio(rows: list[dict[str, Any]]) -> float | None:
    walking = [row for row in rows if row.get("contact_label") == "walking_contact"]
    if not walking:
        return None
    alternating = 0
    for row in walking:
        left = int(row.get("foot_0_contact", 0)) + int(row.get("foot_2_contact", 0))
        right = int(row.get("foot_1_contact", 0)) + int(row.get("foot_3_contact", 0))
        if 1 <= int(row.get("contact_count", 0)) <= 3 and left != right:
            alternating += 1
    return alternating / len(walking)


def _summarize_model(model_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    counts = Counter(str(row.get("contact_label", "unknown")) for row in rows)
    contact_rows = [row for row in rows if str(row.get("contact_label")) in {"standing_contact", "walking_contact"}]
    contact_count_dist = Counter(str(row.get("contact_count", 0)) for row in rows)
    foot_speed_contact = [
        _f(row.get(f"foot_{foot}_speed_norm"))
        for row in contact_rows
        for foot in range(4)
        if int(row.get(f"foot_{foot}_contact", 0) or 0) == 1
    ]
    per_foot = {}
    for foot in range(4):
        valid = [row for row in rows if math.isfinite(_f(row.get(f"foot_{foot}_speed_norm")))]
        per_foot[f"foot_{foot}"] = (
            sum(int(row.get(f"foot_{foot}_contact", 0) or 0) for row in valid) / len(valid) if valid else None
        )
    all_contact_walking = [
        row
        for row in rows
        if row.get("contact_label") == "walking_contact" and int(row.get("contact_count", 0) or 0) >= 4
    ]
    alternating = _alternating_ratio(rows)
    uncertain_ratio = (counts["uncertain"] + counts["invalid"]) / total if total else 1.0
    swing_ratio = counts["swing_phase"] / total if total else 0.0
    contact_ratio = len(contact_rows) / total if total else 0.0
    speed_stats = _stats(foot_speed_contact)
    plausible = bool(
        total
        and contact_ratio >= 0.05
        and uncertain_ratio <= 0.70
        and (alternating is None or alternating >= 0.25)
        and len(all_contact_walking) / max(1, counts["walking_contact"]) <= 0.40
        and (speed_stats["p50"] is None or float(speed_stats["p50"]) <= 1.25)
    )
    return {
        "model_id": model_id,
        "contact_rows": total,
        "contact_ratio": contact_ratio,
        "standing_contact_ratio": counts["standing_contact"] / total if total else 0.0,
        "walking_contact_ratio": counts["walking_contact"] / total if total else 0.0,
        "swing_ratio": swing_ratio,
        "uncertain_ratio": uncertain_ratio,
        "per_foot_contact_ratios": per_foot,
        "alternating_ratio": alternating,
        "contact_count_distribution": dict(sorted(contact_count_dist.items())),
        "foot_speed_during_contact": speed_stats,
        "all_contact_walking_ratio": len(all_contact_walking) / max(1, counts["walking_contact"]),
        "physical_plausibility_status": "plausible" if plausible else "review_or_not_ready",
        "plausible_for_diagnostic": plausible,
        "threshold_source": "go2_field_distribution_only",
        "diagnostic_only": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def build_contact_model_candidates(go2_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    distributions = _field_distributions(go2_rows)
    distribution_report = analyze_contact_distribution(go2_rows)
    threshold_report = review_contact_thresholds(distribution_report)
    all_rows: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}

    v1_rows_raw, _v1_report = build_contact_state(go2_rows)
    v1_rows = [
        {
            "candidate_model": "v1_original",
            "row_index": row.get("row_index"),
            "time": row.get("time"),
            "contact_label": row.get("contact_label"),
            "contact_count": row.get("contact_count"),
            **{f"foot_{foot}_contact": row.get(f"foot_{foot}_contact", 0) for foot in range(4)},
            **{f"foot_{foot}_force": row.get(f"foot_{foot}_force", "") for foot in range(4)},
            **{f"foot_{foot}_speed_norm": row.get(f"foot_{foot}_speed_norm", "") for foot in range(4)},
            "threshold_source": "diagnostic_default",
            "diagnostic_only": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        }
        for row in v1_rows_raw
    ]
    reports["v1_original"] = _summarize_model("v1_original", v1_rows)
    all_rows.extend(v1_rows)

    v2_rows_raw, _v2_report = build_contact_state_v2(go2_rows, threshold_report)
    v2_rows = [
        {
            "candidate_model": "v2_force_percentile_existing",
            "row_index": row.get("row_index"),
            "time": row.get("time"),
            "contact_label": row.get("contact_label_v2"),
            "contact_count": row.get("contact_count_v2"),
            **{f"foot_{foot}_contact": row.get(f"foot_{foot}_contact_v2", 0) for foot in range(4)},
            **{f"foot_{foot}_force": row.get(f"foot_{foot}_force", "") for foot in range(4)},
            **{f"foot_{foot}_speed_norm": row.get(f"foot_{foot}_speed_norm", "") for foot in range(4)},
            "threshold_source": "percentile_force+percentile_speed+mode_gait_rule",
            "diagnostic_only": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        }
        for row in v2_rows_raw
    ]
    reports["v2_force_percentile_existing"] = _summarize_model("v2_force_percentile_existing", v2_rows)
    all_rows.extend(v2_rows)

    for model_id in MODEL_IDS[2:]:
        rows, report = _candidate_rows(go2_rows, model_id=model_id, distributions=distributions)
        if model_id == "v5_gait_mode_windowed":
            rows = _smooth_window(rows)
            report = _summarize_model(model_id, rows)
            report["threshold_source"] = "mode_gait_rule+percentile_speed+window_smoothing"
        reports[model_id] = report
        all_rows.extend(rows)

    candidate_report = {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "candidate_models": MODEL_IDS,
        "candidate_count": len(MODEL_IDS),
        "model_reports": reports,
        "threshold_sources": [
            "percentile_force",
            "percentile_speed",
            "mode_gait_rule",
            "window_smoothing",
        ],
        "threshold_source": "go2_field_distribution_only",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_truth_claim": False,
        "diagnostic_only": True,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return all_rows, candidate_report


def write_contact_model_candidate_outputs(
    go2_rows: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, report = build_contact_model_candidates(go2_rows)
    csv_path = out / "GO2_CONTACT_MODEL_CANDIDATES_TIMESERIES.csv"
    fieldnames = sorted({key for row in rows for key in row}) if rows else ["candidate_model", "time", "contact_label"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    report_path = out / "GO2_CONTACT_MODEL_CANDIDATES_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, rows, report
