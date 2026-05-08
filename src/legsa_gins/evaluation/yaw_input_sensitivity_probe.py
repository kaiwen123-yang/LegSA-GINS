"""Yaw input sensitivity probe for N4H2G2.

中文说明：本模块只做 +30 deg yaw-column smoke test，检查 runtime NAV 对
`.gnss` yaw 列是否敏感；该 probe 不是 factor experiment，不是性能结论。
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from legsa_gins.evaluation.actual_vs_replay_yaw_path import (
    compare_input_yaw_paths,
    compare_nav_yaw_paths,
    wrap_deg360,
)
from legsa_gins.evaluation.clean_status_yaw_replay import evaluate_clean_replay_against_dual_reference, run_external_kfgins_clean_replay


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def create_yaw_shifted_gnss(
    clean_gnss: str | Path,
    output_gnss: str | Path,
    *,
    yaw_shift_deg: float = 30.0,
) -> dict[str, Any]:
    """Create a diagnostic `.gnss` where only column 14 yaw is shifted."""

    src = Path(clean_gnss)
    dst = Path(output_gnss)
    dst.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    yaw_std_unchanged = True
    lines: list[str] = []
    with src.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text or text.startswith("#"):
                lines.append(line.rstrip("\n"))
                continue
            parts = [part for part in text.replace(",", " ").split() if part]
            if len(parts) != 15:
                raise ValueError(f"{src}:{line_number} expected 15 columns, got {len(parts)}")
            original_yaw_std = parts[14]
            parts[13] = f"{wrap_deg360(float(parts[13]) + yaw_shift_deg):.12g}"
            if parts[14] != original_yaw_std:
                yaw_std_unchanged = False
            lines.append(" ".join(parts))
            row_count += 1
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "phase": "N4H2G2",
        "output_role": "diagnostic_yaw_shifted_input",
        "shifted_yaw_deg": float(yaw_shift_deg),
        "row_count": row_count,
        "yaw_std_unchanged": yaw_std_unchanged,
        "formal_allowed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def classify_yaw_sensitivity(nav_yaw_diff_rmse_deg: float | None) -> dict[str, Any]:
    """Classify runtime yaw sensitivity from shifted-vs-clean NAV yaw RMSE."""

    low_effect = isinstance(nav_yaw_diff_rmse_deg, (int, float)) and float(nav_yaw_diff_rmse_deg) < 0.5
    affects = isinstance(nav_yaw_diff_rmse_deg, (int, float)) and float(nav_yaw_diff_rmse_deg) > 5.0
    bounded = isinstance(nav_yaw_diff_rmse_deg, (int, float)) and not low_effect and not affects
    return {
        "yaw_input_affects_runtime": bool(affects),
        "yaw_input_has_low_runtime_effect_or_update_rejected": bool(low_effect),
        "yaw_input_runtime_effect_bounded": bool(bounded),
    }


def run_yaw_shift_sensitivity(
    clean_input_dir: str | Path,
    shifted_gnss: str | Path,
    external_source_root: str | Path,
    output_dir: str | Path,
    *,
    clean_nav: str | Path | None = None,
    dual_reference: list[dict[str, Any]] | None = None,
    clean_summary: dict[str, Any] | None = None,
    allow_build: bool = False,
    allow_run: bool = False,
) -> dict[str, Any]:
    """Run the shifted-yaw diagnostic replay and compare it with clean NAV."""

    clean_dir = Path(clean_input_dir)
    out = Path(output_dir)
    shifted_input_dir = out / "yaw_shifted_input"
    shifted_input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(shifted_gnss, shifted_input_dir / "CLEAN_STATUS_YAW.gnss")
    shutil.copyfile(clean_dir / "CLEAN_STATUS_YAW.imu", shifted_input_dir / "CLEAN_STATUS_YAW.imu")

    run_report = run_external_kfgins_clean_replay(
        shifted_input_dir,
        external_source_root,
        out / "yaw_shifted_run",
        allow_build=allow_build,
        allow_run=allow_run,
    )
    shifted_nav = out / "yaw_shifted_run" / "kfgins_output" / "KF_GINS_Navresult.nav"
    input_report = compare_input_yaw_paths(clean_dir / "CLEAN_STATUS_YAW.gnss", shifted_input_dir / "CLEAN_STATUS_YAW.gnss")

    shifted_summary: dict[str, Any] = {}
    if run_report.get("completed") and dual_reference:
        evaluation = evaluate_clean_replay_against_dual_reference(shifted_nav, dual_reference, out / "yaw_shifted_run" / "evaluation")
        shifted_summary = evaluation.get("clean_replay_summary") or {}

    nav_report: dict[str, Any]
    if run_report.get("completed") and clean_nav is not None and Path(clean_nav).exists() and shifted_nav.exists():
        nav_report = compare_nav_yaw_paths(clean_nav, shifted_nav)
    else:
        nav_report = {"nav_yaw_diff_rmse_deg": None, "nav_position_diff_rmse_m": None, "evidence_status": "evidence_missing"}

    clean_yaw = (clean_summary or {}).get("yaw_rmse_deg")
    shifted_yaw = shifted_summary.get("yaw_rmse_deg")
    yaw_delta = float(shifted_yaw) - float(clean_yaw) if isinstance(clean_yaw, (int, float)) and isinstance(shifted_yaw, (int, float)) else None
    nav_yaw_diff = nav_report.get("nav_yaw_diff_rmse_deg")
    sensitivity = classify_yaw_sensitivity(nav_yaw_diff)
    report = {
        "phase": "N4H2G2",
        "shifted_yaw_deg": input_report.get("input_yaw_diff_rmse_deg"),
        "requested_yaw_shift_deg": 30.0,
        "shifted_input_vs_clean_input_yaw_diff_rmse": input_report.get("input_yaw_diff_rmse_deg"),
        "shifted_nav_vs_clean_nav_yaw_diff_rmse": nav_yaw_diff,
        "shifted_nav_vs_clean_nav_position_diff_rmse_m": nav_report.get("nav_position_diff_rmse_m"),
        "summary_yaw_delta_deg": yaw_delta,
        "input_yaw_path_report": input_report,
        "nav_yaw_path_report": nav_report,
        "shifted_replay_run_report": run_report,
        "shifted_summary": shifted_summary,
        **sensitivity,
        "evidence_status": "completed" if run_report.get("completed") else "evidence_missing",
        "diagnostic_only": True,
        "formal_allowed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "YAW_INPUT_SENSITIVITY_PROBE_REPORT.json", report)
    return report
