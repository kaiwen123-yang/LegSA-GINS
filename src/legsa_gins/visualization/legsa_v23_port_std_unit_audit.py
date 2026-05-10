"""Audit STD unit consistency for N4H4E1 visual validation.

中文说明：本模块只审计 source-backed port 与 dual_final_v23 的 STD 单位；
不修改 solver，不修改 runtime artifact，不做 output-only correction。
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

from legsa_gins.visualization.dual_replay_plot_loader import parse_kfgins_std
from legsa_gins.visualization.legsa_v23_port_visual_loader import load_port_std


ATTITUDE_KEYS = ("std_roll_deg", "std_pitch_deg", "std_yaw_deg")
FALSE_FLAGS = {
    "paper_performance_claim": False,
    "proposed_factor_claim": False,
    "trace_solver_input": False,
    "final_v23_output_solver_input": False,
    "output_only_correction": False,
    "bad_epoch_deletion_for_metric": False,
    "no_outperform_final_v23_claim": True,
}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_std_file(path: str | Path | None, role: str) -> list[dict[str, Any]]:
    """Load port or final_v23 STD rows into common field names."""

    if not path or not Path(path).exists():
        return []
    candidate = Path(path)
    if candidate.name == "KF_GINS_STD.txt" or role == "final_v23_reference_baseline":
        rows = parse_kfgins_std(candidate)
    else:
        rows = load_port_std(candidate)
    for row in rows:
        row["std_role"] = role
    return rows


def _series(rows: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None, "first": None}
    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "first": values[0],
    }


def infer_attitude_std_unit(std_rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    """Infer whether attitude STD values look like deg, rad, or missing evidence."""

    if not std_rows:
        return {
            "role": role,
            "attitude_std_unit": "evidence_missing",
            "evidence_status": "missing_std_rows",
            "yaw_std_rad_deg_confusion_suspect": False,
            "attitude_summaries": {},
        }
    summaries = {key: _summary(_series(std_rows, key)) for key in ATTITUDE_KEYS}
    yaw = summaries["std_yaw_deg"]
    max_yaw = yaw["max"]
    median_yaw = yaw["median"]
    if max_yaw is None or median_yaw is None:
        unit = "evidence_missing"
        status = "missing_attitude_columns"
    elif max_yaw <= 0.2 and median_yaw <= 0.05:
        unit = "rad"
        status = "values_match_rad_scale"
    elif max_yaw >= 0.2:
        unit = "deg"
        status = "values_match_deg_scale"
    else:
        unit = "unknown"
        status = "ambiguous_attitude_std_scale"
    suspect = unit == "rad" or (max_yaw is not None and 0.02 <= max_yaw <= 0.05)
    return {
        "role": role,
        "attitude_std_unit": unit,
        "evidence_status": status,
        "yaw_std_rad_deg_confusion_suspect": suspect,
        "attitude_summaries": summaries,
    }


def audit_std_writer_source(repo_root: str | Path) -> dict[str, Any]:
    """Inspect source-backed writer code for KF-GINS common-unit STD output."""

    root = Path(repo_root)
    file_saver = root / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp"
    port_writers = root / "cpp/legsa_v23_port_core/src/writers/port_writers.cpp"
    text = ""
    for path in [file_saver, port_writers]:
        if path.exists():
            text += path.read_text(encoding="utf-8", errors="ignore") + "\n"
    attitude_ok = "PHI_ID" in text and "R2D" in text and "std_roll_deg" in text
    gyro_ok = "BG_ID" in text and "3600.0" in text and "std_gyrbias_x_dph" in text
    acc_ok = "BA_ID" in text and "1.0e5" in text and "std_accbias_x_mgal" in text
    scale_ok = "SG_ID" in text and "SA_ID" in text and "1.0e6" in text
    comment_ok = "姿态协方差内部单位为 rad²，输出 STD 转为 deg" in text
    return {
        "source_backed_writeSTD_expected_unit": "deg",
        "file_saver_exists": file_saver.exists(),
        "port_writers_exists": port_writers.exists(),
        "attitude_std_writer_deg_conversion_evidence": attitude_ok,
        "gyro_bias_writer_dph_conversion_evidence": gyro_ok,
        "acc_bias_writer_mgal_conversion_evidence": acc_ok,
        "scale_writer_ppm_conversion_evidence": scale_ok,
        "chinese_comment_present": comment_ok,
        "port_writer_common_unit_ok": bool(attitude_ok and gyro_ok and acc_ok and scale_ok and comment_ok),
    }


def audit_visual_loader_unit_policy(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root)
    loader = root / "src/legsa_gins/visualization/legsa_v23_port_visual_loader.py"
    plotter = root / "src/legsa_gins/visualization/legsa_v23_port_visual_plots.py"
    text = ""
    for path in [loader, plotter]:
        if path.exists():
            text += path.read_text(encoding="utf-8", errors="ignore") + "\n"
    return {
        "port_attitude_std_unit_input": "deg_or_unlabeled_legacy",
        "finalv23_attitude_std_unit_input": "deg",
        "plot_attitude_std_unit": "deg",
        "conversion_applied_to_port": "N4H4E1_plot_only_when_legacy_rad_detected",
        "conversion_applied_to_finalv23": "none",
        "visual_loader_unit_policy_ok": bool("unit_policy" in text and "plot_attitude_std_unit" in text),
    }


def normalize_attitude_std_for_plot(std_rows: list[dict[str, Any]], attitude_unit: str) -> list[dict[str, Any]]:
    """Return copied STD rows with roll/pitch/yaw attitude STD in degrees."""

    factor = 180.0 / math.pi if attitude_unit == "rad" else 1.0
    normalized: list[dict[str, Any]] = []
    for row in std_rows:
        item = dict(row)
        for key in ATTITUDE_KEYS:
            if isinstance(item.get(key), (int, float)):
                item[key] = float(item[key]) * factor
        item["plot_attitude_std_unit"] = "deg"
        item["attitude_std_conversion_applied"] = attitude_unit == "rad"
        normalized.append(item)
    return normalized


def make_std_unit_audit_report(
    *,
    port_std_rows: list[dict[str, Any]],
    finalv23_std_rows: list[dict[str, Any]],
    repo_root: str | Path,
    fix_applied: bool | None = None,
) -> dict[str, Any]:
    port = infer_attitude_std_unit(port_std_rows, "source_backed_port_core")
    final = infer_attitude_std_unit(finalv23_std_rows, "final_v23_reference_baseline")
    writer = audit_std_writer_source(repo_root)
    loader = audit_visual_loader_unit_policy(repo_root)
    port_unit = port["attitude_std_unit"]
    final_unit = final["attitude_std_unit"]
    unit_confusion = bool(port["yaw_std_rad_deg_confusion_suspect"] and final_unit == "deg")
    fix_required = bool(port_unit == "rad" or not writer["port_writer_common_unit_ok"] or not loader["visual_loader_unit_policy_ok"])
    applied = bool(fix_applied if fix_applied is not None else writer["port_writer_common_unit_ok"] and loader["visual_loader_unit_policy_ok"])
    if port_unit == "rad" and writer["port_writer_common_unit_ok"]:
        fix_type = "writer_fix"
    elif port_unit == "deg" and not loader["visual_loader_unit_policy_ok"]:
        fix_type = "loader_fix"
    elif not fix_required:
        fix_type = "no_fix_needed"
    else:
        fix_type = "evidence_missing"
    consistency_ok = bool(
        final_unit == "deg"
        and writer["port_writer_common_unit_ok"]
        and loader["visual_loader_unit_policy_ok"]
        and applied
    )
    report = {
        "phase": "N4H4E1",
        "finalv23_attitude_std_unit": final_unit,
        "port_attitude_std_unit": port_unit,
        "port_writer_common_unit_ok": writer["port_writer_common_unit_ok"],
        "visual_loader_unit_policy_ok": loader["visual_loader_unit_policy_ok"],
        "yaw_std_rad_deg_confusion_suspect": unit_confusion,
        "attitude_3sigma_unit_consistency_ok": consistency_ok,
        "source_backed_writeSTD_expected_unit": "deg",
        "fix_required": fix_required,
        "fix_applied": applied,
        "fix_type": fix_type,
        "port_std_evidence": port,
        "finalv23_std_evidence": final,
        "writer_source_audit": writer,
        "visual_loader_unit_policy": loader,
        **FALSE_FLAGS,
    }
    return report


def write_std_unit_audit_report(path: str | Path, report: dict[str, Any]) -> None:
    _write_json(path, report)
