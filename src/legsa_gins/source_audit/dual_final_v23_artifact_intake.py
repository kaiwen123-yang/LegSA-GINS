"""Manual dual_final_v23 artifact intake for N4R3.

中文说明：本模块只校验仓库外 artifact root；runtime report 可以写实际路径，
tracked docs/config 只能写 role alias，且不能提交 input/nav/std/summary/error_series。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import load_official_summary


REQUIRED_FILES = [
    "input.gnss",
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "summary.json",
    "error_series.csv",
]
OPTIONAL_FILES = ["KF_GINS_IMU_ERR.txt", "case_review.md"]
SUMMARY_FIELDS = [
    "horizontal_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "horizontal_p95_m",
    "yaw_p95_deg",
    "count",
    "aligned_count",
]


def _default_dual_root() -> Path:
    return Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"


def _line_count(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _file_size(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.stat().st_size
    except OSError:
        return None


def resolve_dual_artifact_root(cli_dual_root: str | Path | None = None) -> dict[str, Any]:
    """Resolve the manual dual artifact root by CLI, env, then default."""

    if cli_dual_root:
        root = Path(cli_dual_root)
        source = "cli_dual_root"
    elif os.environ.get("LEGSA_DUAL_FINAL_V23_ROOT"):
        root = Path(str(os.environ["LEGSA_DUAL_FINAL_V23_ROOT"]))
        source = "env_LEGSA_DUAL_FINAL_V23_ROOT"
    else:
        root = _default_dual_root()
        source = "default_dual_root"
    exists = root.exists() and root.is_dir()
    return {
        "root_role": "DUAL_FINAL_V23_ARTIFACT_ROOT",
        "root": str(root),
        "resolve_source": source,
        "exists": exists,
        "evidence_status": "root_exists" if exists else "evidence_missing",
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def validate_dual_artifact_root(root: str | Path) -> dict[str, Any]:
    """Validate required/optional artifacts under one manual root."""

    base = Path(root)
    files = {name: base / name for name in REQUIRED_FILES + OPTIONAL_FILES}
    has = {name: path.exists() and path.is_file() for name, path in files.items()}
    missing = [name for name in REQUIRED_FILES if not has[name]]
    complete = not missing
    return {
        "root_role": "DUAL_FINAL_V23_ARTIFACT_ROOT",
        "has_input_gnss": has["input.gnss"],
        "has_nav": has["KF_GINS_Navresult.nav"],
        "has_std": has["KF_GINS_STD.txt"],
        "has_summary": has["summary.json"],
        "has_error_series": has["error_series.csv"],
        "has_imu_err": has["KF_GINS_IMU_ERR.txt"],
        "has_case_review": has["case_review.md"],
        "required_files_complete": complete,
        "missing_required_files": missing,
        "line_counts": {name: _line_count(path) for name, path in files.items()},
        "file_size_bytes": {name: _file_size(path) for name, path in files.items()},
        "artifacts": {name: str(path) for name, path in files.items() if has[name]},
        "evidence_status": "required_files_complete" if complete else "manual_artifact_incomplete",
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def read_dual_summary(summary_path: str | Path) -> dict[str, Any]:
    """Read dual summary metrics from summary.json."""

    summary = load_official_summary(summary_path)
    extracted = {"evidence_status": summary.get("evidence_status", "evidence_missing")}
    for field in SUMMARY_FIELDS:
        if field in summary:
            extracted[field] = summary[field]
    extracted["raw_summary"] = summary.get("raw_summary")
    extracted["trace_solver_input"] = False
    extracted["output_only_correction"] = False
    extracted["numerical_performance_claim"] = False
    return extracted


def classify_dual_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Classify whether summary metrics match the dual_final_v23 envelope."""

    horizontal = summary.get("horizontal_rmse_m")
    up = summary.get("up_rmse_m")
    yaw = summary.get("yaw_rmse_deg")
    missing = [
        name
        for name, value in [
            ("horizontal_rmse_m", horizontal),
            ("up_rmse_m", up),
            ("yaw_rmse_deg", yaw),
        ]
        if not isinstance(value, (int, float))
    ]
    if missing:
        confirmed = False
        single_like = False
        ambiguous = False
        blocker = f"missing_summary_metrics:{','.join(missing)}"
    else:
        confirmed = float(horizontal) <= 1.0 and float(up) <= 1.5 and float(yaw) <= 3.0
        single_like = float(horizontal) > 10.0 or float(yaw) > 10.0
        ambiguous = not confirmed and not single_like
        if confirmed:
            blocker = None
        elif single_like:
            blocker = "single_antenna_like_summary_metrics"
        else:
            blocker = "summary_outside_dual_confirmation_window"
    return {
        "dual_final_v23_confirmed": confirmed,
        "single_like": single_like,
        "ambiguous": ambiguous,
        "blocker_reason": blocker,
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }


def make_dual_artifact_intake_report(
    root_report: dict[str, Any],
    validation: dict[str, Any],
    summary_classification: dict[str, Any],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the N4R3 manual intake report."""

    exists = bool(root_report.get("exists"))
    complete = bool(validation.get("required_files_complete"))
    confirmed = bool(summary_classification.get("dual_final_v23_confirmed"))
    single_like = bool(summary_classification.get("single_like"))
    if not exists:
        status = "manual_artifact_missing"
        evidence = "evidence_missing"
    elif not complete:
        status = "manual_artifact_incomplete"
        evidence = "manual_artifact_incomplete"
    elif confirmed:
        status = "dual_final_v23_confirmed"
        evidence = "dual_final_v23_confirmed"
    elif single_like:
        status = "wrong_artifact_group_single_like"
        evidence = "single_antenna_like_rejected"
    else:
        status = "dual_artifact_ambiguous"
        evidence = "ambiguous"
    return {
        "phase": "N4R3",
        "root_report": root_report,
        "validation": validation,
        "summary": summary or {},
        "summary_classification": summary_classification,
        "dual_artifact_intake_status": status,
        "dual_final_v23_confirmed": confirmed,
        "manual_artifact_required": not confirmed,
        "evidence_status": evidence,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def run_dual_artifact_intake(
    cli_dual_root: str | Path | None,
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve, validate, classify, and optionally write the intake report."""

    root_report = resolve_dual_artifact_root(cli_dual_root)
    root = Path(str(root_report["root"]))
    validation = validate_dual_artifact_root(root)
    summary: dict[str, Any] = {"evidence_status": "evidence_missing"}
    if validation.get("has_summary"):
        summary = read_dual_summary(root / "summary.json")
    classification = classify_dual_summary(summary)
    report = make_dual_artifact_intake_report(root_report, validation, classification, summary)
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "DUAL_FINAL_V23_ARTIFACT_INTAKE_REPORT.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report
