"""N7B2 contact-state window smoothing diagnostics.

中文说明：window/min-duration/debounce 都是固定诊断参数，不由 trace 或
final_v23 output 调参；平滑结果不进入 solver。
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _majority(values: list[str]) -> str:
    if not values:
        return "uncertain"
    counts = Counter(values)
    return counts.most_common(1)[0][0]


def _uncertain_ratio(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 1.0
    return sum(1 for row in rows if row.get(key) in {"uncertain", "invalid"}) / len(rows)


def _transition_count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(1 for a, b in zip(rows, rows[1:]) if a.get(key) != b.get(key))


def _min_duration_filter(labels: list[str], min_duration: int) -> list[str]:
    if min_duration <= 1 or not labels:
        return labels
    out = list(labels)
    start = 0
    while start < len(labels):
        end = start + 1
        while end < len(labels) and labels[end] == labels[start]:
            end += 1
        if end - start < min_duration:
            replacement = labels[start - 1] if start > 0 else (labels[end] if end < len(labels) else labels[start])
            for index in range(start, end):
                out[index] = replacement
        start = end
    return out


def _debounced_foot(rows: list[dict[str, Any]], foot: int, window_size: int) -> list[int]:
    half = window_size // 2
    values = [int(row.get(f"foot_{foot}_contact_v2", 0) or 0) for row in rows]
    out: list[int] = []
    for index in range(len(values)):
        window = values[max(0, index - half) : min(len(values), index + half + 1)]
        out.append(1 if sum(window) >= (len(window) / 2.0) else 0)
    return out


def smooth_contact_state_rows(
    rows: list[dict[str, Any]],
    *,
    window_size: int = 5,
    min_duration: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    half = window_size // 2
    raw_labels = [str(row.get("contact_label_v2", "uncertain")) for row in rows]
    majority_labels = [
        _majority(raw_labels[max(0, index - half) : min(len(raw_labels), index + half + 1)])
        for index in range(len(rows))
    ]
    labels = _min_duration_filter(majority_labels, min_duration)
    debounced = {foot: _debounced_foot(rows, foot, window_size) for foot in range(4)}
    smoothed: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        out = dict(row)
        out["contact_label_v2_raw"] = row.get("contact_label_v2", "uncertain")
        out["contact_label_v2"] = labels[index]
        for foot in range(4):
            out[f"foot_{foot}_contact_v2"] = debounced[foot][index]
        out["contact_count_v2"] = sum(debounced[foot][index] for foot in range(4))
        smoothed.append(out)
    report = {
        "stage": "N7B2_go2_contact_threshold_review",
        "window_size": window_size,
        "min_duration": min_duration,
        "contact_transition_count": _transition_count(smoothed, "contact_label_v2"),
        "uncertain_ratio_before": _uncertain_ratio(rows, "contact_label_v2"),
        "uncertain_ratio_after": _uncertain_ratio(smoothed, "contact_label_v2"),
        "per_foot_debounce": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    return smoothed, report


def write_contact_smoothing_outputs(
    rows: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    window_size: int = 5,
    min_duration: int = 3,
) -> tuple[Path, Path, list[dict[str, Any]], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    smoothed, report = smooth_contact_state_rows(rows, window_size=window_size, min_duration=min_duration)
    csv_path = out / "GO2_CONTACT_STATE_V2_SMOOTHED_TIMESERIES.csv"
    fieldnames = list(smoothed[0].keys()) if smoothed else ["row_index", "time", "contact_label_v2"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(smoothed)
    report_path = out / "GO2_CONTACT_SMOOTHING_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, report_path, smoothed, report
