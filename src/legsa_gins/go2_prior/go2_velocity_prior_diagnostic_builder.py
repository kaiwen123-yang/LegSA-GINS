"""Build runtime-only diagnostic Go2 velocity prior CSVs for N7B3.

中文说明：本模块只写 runtime-only CSV；Go2 velocity 不是 truth，生成的 prior
只允许 diagnostic-only activation attempt。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_velocity_frame_review import transform_go2_velocity_for_frame
from .go2_velocity_quality import _nearest_from_index


PRIOR_FIELDS = [
    "time",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "source_status",
    "quality_flag",
    "contact_model",
    "contact_label",
    "frame_candidate",
    "prior_policy",
    "diagnostic_only",
    "go2_velocity_truth_claim",
]


def _std_policy(frame_report: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    values = [
        _f(frame_report.get("rmse_to_receiver")),
        _f(frame_report.get("rmse_to_raw")),
    ]
    finite = [value for value in values if math.isfinite(value)]
    std = max([2.0, *finite]) if finite else 2.0
    return std, {"base_std_mps": std, "rule": "max(2.0, cross_source_rmse)"}


def _model_rows(candidate_timeseries: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    return sorted(
        [row for row in candidate_timeseries if row.get("candidate_model") == model_id],
        key=lambda row: _f(row.get("time"), 0.0),
    )


def _write_prior_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRIOR_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in PRIOR_FIELDS} for row in rows])


def build_go2_velocity_diagnostic_priors(
    *,
    go2_rows: list[dict[str, Any]],
    velocity_frame_report: dict[str, Any],
    contact_model_comparison: dict[str, Any],
    candidate_timeseries: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    frame_name = str(velocity_frame_report.get("recommended_frame_for_diagnostic_prior") or "")
    frame_status = str(velocity_frame_report.get("frame_ambiguity_status") or "")
    selected_contact = str(contact_model_comparison.get("selected_diagnostic_contact_model") or "")
    contact_ready = bool(contact_model_comparison.get("contact_model_ready", False))
    std, std_policy = _std_policy(velocity_frame_report)
    activation_allowed = bool(frame_name) and frame_status != "ambiguous_close_candidates"
    contact_rows = _model_rows(candidate_timeseries, selected_contact) if selected_contact else []
    contact_index = 0
    weak_rows: list[dict[str, Any]] = []
    direct_rows: list[dict[str, Any]] = []
    gated_rows: list[dict[str, Any]] = []
    zero_rows: list[dict[str, Any]] = []
    if activation_allowed:
        for row in sorted(go2_rows, key=_time_value):
            time_value = _time_value(row)
            selected_velocity = transform_go2_velocity_for_frame(row, frame_name)
            direct_velocity = transform_go2_velocity_for_frame(row, "go2_velocity_as_world_enu_or_ned_direct")
            if all(math.isfinite(value) for value in selected_velocity):
                base = {
                    "time": time_value,
                    "vn": selected_velocity[0],
                    "ve": selected_velocity[1],
                    "vd": selected_velocity[2],
                    "std_vn": std,
                    "std_ve": std,
                    "std_vd": std,
                    "source_status": "active",
                    "quality_flag": "diagnostic_frame_best",
                    "contact_model": selected_contact,
                    "contact_label": "",
                    "frame_candidate": frame_name,
                    "prior_policy": "direct_go2_velocity_weak_prior",
                    "diagnostic_only": True,
                    "go2_velocity_truth_claim": False,
                }
                weak_rows.append(base)
            if all(math.isfinite(value) for value in direct_velocity):
                direct_rows.append(
                    {
                        "time": time_value,
                        "vn": direct_velocity[0],
                        "ve": direct_velocity[1],
                        "vd": direct_velocity[2],
                        "std_vn": std,
                        "std_ve": std,
                        "std_vd": std,
                        "source_status": "active",
                        "quality_flag": "diagnostic_direct_frame",
                        "contact_model": "",
                        "contact_label": "",
                        "frame_candidate": "go2_velocity_as_world_enu_or_ned_direct",
                        "prior_policy": "direct_go2_velocity_weak_prior",
                        "diagnostic_only": True,
                        "go2_velocity_truth_claim": False,
                    }
                )
            if contact_ready and contact_rows:
                contact, contact_index = _nearest_from_index(contact_rows, time_value, contact_index, tolerance=0.10)
                label = str(contact.get("contact_label", "")) if contact else ""
                count = int(contact.get("contact_count", 0) or 0) if contact else 0
                if label == "walking_contact" and 1 <= count <= 3 and all(math.isfinite(value) for value in selected_velocity):
                    gated = dict(weak_rows[-1])
                    gated["contact_label"] = label
                    gated["prior_policy"] = "contact_gated_velocity_weak_prior"
                    gated["quality_flag"] = "diagnostic_contact_gated"
                    gated_rows.append(gated)
                if label == "standing_contact" and count >= 3:
                    zero_rows.append(
                        {
                            "time": time_value,
                            "vn": 0.0,
                            "ve": 0.0,
                            "vd": 0.0,
                            "std_vn": std,
                            "std_ve": std,
                            "std_vd": std,
                            "source_status": "active",
                            "quality_flag": "diagnostic_standing_contact_zero_velocity",
                            "contact_model": selected_contact,
                            "contact_label": label,
                            "frame_candidate": frame_name,
                            "prior_policy": "standing_contact_zero_velocity_diagnostic",
                            "diagnostic_only": True,
                            "go2_velocity_truth_claim": False,
                        }
                    )
    paths = {
        "weak": out / "GO2_VELOCITY_WEAK_PRIORS_DIAGNOSTIC.csv",
        "direct": out / "GO2_VELOCITY_DIRECT_WEAK_PRIORS_DIAGNOSTIC.csv",
        "contact_gated": out / "GO2_VELOCITY_CONTACT_GATED_PRIORS_DIAGNOSTIC.csv",
        "standing_zero": out / "GO2_STANDING_ZERO_VELOCITY_PRIORS_DIAGNOSTIC.csv",
    }
    for key, rows in [("weak", weak_rows), ("direct", direct_rows), ("contact_gated", gated_rows), ("standing_zero", zero_rows)]:
        _write_prior_csv(paths[key], rows)
    report = {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "prior_csv_generated": bool(weak_rows or direct_rows or gated_rows or zero_rows),
        "prior_csv_paths": {key: path.name for key, path in paths.items()},
        "prior_epoch_count": len(weak_rows),
        "direct_epoch_count": len(direct_rows),
        "contact_gated_epoch_count": len(gated_rows),
        "standing_zero_epoch_count": len(zero_rows),
        "selected_frame": frame_name,
        "selected_contact_model": selected_contact,
        "std_policy": std_policy,
        "activation_allowed_for_diagnostic": activation_allowed,
        "activation_blockers": [] if activation_allowed else ["frame_ambiguity_high_or_missing"],
        "diagnostic_only": True,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }
    (out / "GO2_VELOCITY_PRIOR_DIAGNOSTIC_BUILD_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths, report
