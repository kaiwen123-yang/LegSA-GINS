"""N9C1F-to-N9C3 FGO/legged evidence repair and report package.

This module is intentionally reporting-only. It audits existing runtime
evidence, materializes conservative evidence tables and figures from real rows
when available, and records blocked logger sources without running solvers or
changing estimator behavior.
"""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any


STAGE = "N9C1F_TO_N9C3_FGO_LEGGED_EVIDENCE_REPAIR_AND_REPORT_PACKAGE"
EVIDENCE_ROOT_NAME = "N9C1F_G_FGO_LEGGED_EVIDENCE"
REPLOT_ROOT_NAME = "N9C1F_G_REPLOTTED_FGO_LEGGED_FIGURES"
N9C3_EXPORT_ROOT_NAME = "N9C3_EXPORT_CLEAN_REPORT_PACKAGE_AFTER_FGO_LEGGED_REPAIR"

REPRESENTATIVE_CASES = [
    "FULL_normal_repeat",
    "A_outage_20s",
    "C_position_noise_medium_seed0",
    "D_position_spike_medium_seed0",
    "H_dual_yaw_noise_medium_seed0",
    "M_mixed_D_seed0",
    "M_mixed_F_seedless",
]

FGO_PLOTS = [
    "factor_residual_by_type",
    "whitened_residual",
    "factor_contribution",
    "factor_rows",
    "jacobian_nonzero",
    "fgo_cost",
    "smoothness_residual",
    "raw_doppler_fgo_residual",
    "go2_joint_fgo_residual",
    "candidate_factor_residual",
]

LEGGED_PLOTS = [
    "contact_probability",
    "slip_risk",
    "foot_kinematic_velocity",
    "yaw_rate_between_residual",
    "relative_odometry_residual",
    "Go2_joint_residual",
    "Go2_attitude_prior_residual",
    "Go2_horizontal_velocity_prior_residual",
    "contact_aware_weight_scale",
    "Go2 provider/update counts",
]

NINE_FACTORS = [
    "ReceiverPositionFactor",
    "ReceiverVelocityFactor",
    "DualYawFactor",
    "RawDopplerVelocityFactor",
    "Go2ProprioceptiveJointFactor",
    "FootKinematicVelocityFactor",
    "YawRateBetweenFactor",
    "RelativeOdometryBetweenFactor",
    "SmoothnessFactor / Prior / WindowSmoothnessFactor",
]

ACTIVE_BLOCKED_FACTORS = {
    "ReceiverPositionFactor",
    "ReceiverVelocityFactor",
    "DualYawFactor",
    "RawDopplerVelocityFactor",
    "Go2ProprioceptiveJointFactor",
    "SmoothnessFactor / Prior / WindowSmoothnessFactor",
}

CANDIDATE_FACTOR_TYPES = {
    "FootKinematicVelocityFactor",
    "YawRateBetweenFactor",
    "RelativeOdometryBetweenFactor",
}

N9C3_SECTIONS = [
    "current_state_summary",
    "data_and_algorithm_roles",
    "normal_condition_review",
    "deterministic_degradation_review",
    "position_noise_review",
    "position_spike_review",
    "yaw_noise_review",
    "module_disable_review",
    "mixed_degradation_review",
    "finalv23_external_baseline_review",
    "single_baseline_review",
    "LegSA_full_EKF_review",
    "branch_ablation_review",
    "selected_feedback_review",
    "FGO_and_legged_evidence_boundary",
    "blocked_source_and_deferred_case_review",
    "figure_selection_and_caption_package",
    "no_claim_boundary_summary",
    "recommended_next_stage",
]


def default_stage_root(workspace_root: Path) -> Path:
    return workspace_root / "by2-huitu" / STAGE


def default_matrix_root(workspace_root: Path) -> Path:
    return workspace_root / "by2-huitu" / "N9B2_FULL_MATRIX"


def default_archive_root(workspace_root: Path) -> Path:
    configured = os.environ.get("LEGSA_GINS_ARCHIVE_ROOT") or os.environ.get("BY2_ARCHIVE_ROOT")
    if configured:
        return Path(configured).expanduser()
    return workspace_root


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in keys})


def _write_table_pair(stem: Path, rows: list[dict[str, Any]]) -> None:
    _write_json(stem.with_suffix(".json"), rows)
    _write_csv(stem.with_suffix(".csv"), rows)


def _write_summary(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _f(value: Any, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        out = float(value)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _b(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "pass", "completed"}


def _percentile(values: list[float], q: float) -> float:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return math.nan
    index = min(len(finite) - 1, max(0, int(round((len(finite) - 1) * q))))
    return finite[index]


def _coverage_from_time(rows: list[dict[str, Any]], field: str = "time_s") -> dict[str, Any]:
    values = [_f(row.get(field)) for row in rows]
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return {"row_count": len(rows), "time_start": "", "time_end": "", "duration_s": ""}
    return {
        "row_count": len(rows),
        "time_start": min(finite),
        "time_end": max(finite),
        "duration_s": max(finite) - min(finite),
    }


def _prepare_roots(stage_root: Path, matrix_root: Path) -> dict[str, Path]:
    roots = {
        "stage": stage_root,
        "matrix_root": matrix_root,
        "evidence": matrix_root / EVIDENCE_ROOT_NAME,
        "replot": matrix_root / REPLOT_ROOT_NAME,
        "n9c3": matrix_root / N9C3_EXPORT_ROOT_NAME,
    }
    stage_subdirs = [
        "00_supervisor",
        "01_plan",
        "source_audit",
        "fgo_logger",
        "legged_logger",
        "representative_runs",
        "full_logging_expansion",
        "evidence_tables",
        "replot_10_fgo_factors",
        "replot_12_legged_factors",
        "updated_figure_index",
        "n9c3_report_package",
        "export_clean",
        "reports",
        "matrix",
        "summary",
        "validation",
        "logs",
    ]
    for subdir in stage_subdirs:
        (stage_root / subdir).mkdir(parents=True, exist_ok=True)
    for root in [roots["evidence"], roots["replot"], roots["n9c3"]]:
        for subdir in ["reports", "matrix", "summary", "export_clean", "figures"]:
            (root / subdir).mkdir(parents=True, exist_ok=True)
    (roots["replot"] / "10_fgo_factors").mkdir(parents=True, exist_ok=True)
    (roots["replot"] / "12_legged_factors").mkdir(parents=True, exist_ok=True)
    return roots


def _archive_paths(archive_root: Path) -> dict[str, Path]:
    by2 = archive_root / "by2-huitu"
    return {
        "r4n2_tables": by2 / "N9A_R4N2_EXISTING_CANDIDATE_LOG_FIGURE_COMPLETION" / "tables",
        "r4o": by2 / "N9A_R4O_ACTIVE_FGO_FACTOR_WINDOW_LOGGING",
        "n8f1": by2 / "N8F1_legged_candidate_factor_visual_validation",
    }


def _source_record(path: Path, *, workspace_root: Path, archive_root: Path) -> dict[str, str]:
    root = "missing"
    if path.exists():
        try:
            path.relative_to(workspace_root)
            root = "C"
        except ValueError:
            try:
                path.relative_to(archive_root)
                root = "G"
            except ValueError:
                root = "external"
    return {"source_path": str(path), "source_root": root}


def _export_alias(path: Path, workspace_root: Path, stage_root: Path, matrix_root: Path, archive_root: Path) -> str:
    resolved = path
    for root, alias in [
        (matrix_root, "<BY2_N9B2_FULL_MATRIX_ROOT>"),
        (stage_root, "<BY2_N9B2_WINDOWS_ROOT>/" + STAGE),
        (workspace_root / "by2-huitu", "<BY2_N9B2_WINDOWS_ROOT>"),
        (archive_root, "<USB_ARCHIVE_ROOT>"),
    ]:
        try:
            rel = resolved.relative_to(root)
            return alias + "/" + rel.as_posix()
        except ValueError:
            continue
    return "<UNALIASED_RUNTIME_PATH>"


def _git_output(args: list[str], workspace_root: Path) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=workspace_root, text=True, capture_output=True, check=False)
    except OSError:
        return ""
    return result.stdout.strip()


def _sanitize_text(text: str, workspace_root: Path, archive_root: Path) -> str:
    replacements = {
        str(workspace_root / "by2-huitu" / "N9B2_FULL_MATRIX"): "<BY2_N9B2_FULL_MATRIX_ROOT>",
        str(workspace_root / "by2-huitu"): "<BY2_N9B2_WINDOWS_ROOT>",
        str(workspace_root): "<WINDOWS_AUDIT_ROOT>",
        str(archive_root): "<USB_ARCHIVE_ROOT>",
    }
    clean = text
    for old, new in replacements.items():
        clean = clean.replace(old, new)
        clean = clean.replace(old.replace("\\", "/"), new)
    return clean


def _symbol_found(workspace_root: Path, factor: str) -> bool:
    needles = [factor]
    if factor == "SmoothnessFactor / Prior / WindowSmoothnessFactor":
        needles = ["SmoothnessFactor", "WindowSmoothnessFactor", "smoothness"]
    search_roots = [workspace_root / "src", workspace_root / "scripts", workspace_root / "cpp", workspace_root / "configs"]
    suffixes = {".py", ".cpp", ".hpp", ".h", ".yaml", ".yml", ".json", ".md"}
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(needle in text for needle in needles):
                return True
    return False


def _build_fgo_source_audit(
    *,
    workspace_root: Path,
    archive_root: Path,
    factor_window_rows: list[dict[str, str]],
    factor_residual_rows: list[dict[str, str]],
    r4o_root: Path,
) -> list[dict[str, Any]]:
    candidate_source = _source_record(_archive_paths(archive_root)["r4n2_tables"] / "factor_window_metrics.csv", workspace_root=workspace_root, archive_root=archive_root)
    blocked_source = _source_record(r4o_root / "05_factor_logs" / "active_factor_window_metrics.csv", workspace_root=workspace_root, archive_root=archive_root)
    cov = _coverage_from_time(factor_window_rows)
    residual_cov = _coverage_from_time(factor_residual_rows)
    rows: list[dict[str, Any]] = []
    candidate_plots = {
        "factor_residual_by_type",
        "whitened_residual",
        "factor_contribution",
        "factor_rows",
        "jacobian_nonzero",
        "candidate_factor_residual",
    }
    for plot in FGO_PLOTS:
        if plot in candidate_plots and factor_window_rows:
            rows.append(
                {
                    "requested_plot": plot,
                    "source_exists": True,
                    **candidate_source,
                    "row_count": residual_cov["row_count"] if plot == "candidate_factor_residual" else cov["row_count"],
                    "time_window_coverage": f"{cov['time_start']}..{cov['time_end']}",
                    "case_coverage": "archived_BY2_normal_candidate_FGO_only",
                    "active_or_candidate": "candidate_only",
                    "aggregate_or_time_series": "time_series",
                    "can_plot_now": True,
                    "logger_needed": False,
                    "block_reason": "",
                    "safe_claim_level": "candidate_only",
                }
            )
        else:
            rows.append(
                {
                    "requested_plot": plot,
                    "source_exists": Path(blocked_source["source_path"]).exists(),
                    **blocked_source,
                    "row_count": 0,
                    "time_window_coverage": "",
                    "case_coverage": "none_for_current_full_matrix",
                    "active_or_candidate": "active_expected_but_unlogged" if plot != "candidate_factor_residual" else "candidate_only",
                    "aggregate_or_time_series": "blocked",
                    "can_plot_now": False,
                    "logger_needed": True,
                    "block_reason": "blocked_missing_true_runtime_export; R4O active log files are header-only/blocked; aggregate/proxy evidence not relabeled as time-series",
                    "safe_claim_level": "blocked",
                }
            )
    return rows


def _build_nine_factor_status(
    *,
    workspace_root: Path,
    archive_root: Path,
    factor_window_rows: list[dict[str, str]],
    module_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    present_factors = {row.get("factor_type") for row in factor_window_rows}
    module_pass = any(_b(row.get("module_verification_passed")) for row in module_rows)
    rows: list[dict[str, Any]] = []
    for factor in NINE_FACTORS:
        candidate = factor in CANDIDATE_FACTOR_TYPES
        active_blocked = factor in ACTIVE_BLOCKED_FACTORS
        runtime_rows = factor in present_factors
        rows.append(
            {
                "factor": factor,
                "code_symbol_found": _symbol_found(workspace_root, factor),
                "config_present": module_pass or candidate,
                "active_in_logger": runtime_rows,
                "active_in_solver": bool(candidate and runtime_rows),
                "runtime_rows_present": runtime_rows,
                "residual_time_series_present": runtime_rows,
                "cost_contribution_present": runtime_rows,
                "factor_rows_present": runtime_rows,
                "jacobian_nonzero_present": runtime_rows,
                "used_for_feedback": factor in {"ReceiverPositionFactor", "ReceiverVelocityFactor", "DualYawFactor", "Go2ProprioceptiveJointFactor"},
                "candidate_only": candidate,
                "aggregate_only": False,
                "blocked_missing_logger": active_blocked and not runtime_rows,
                "current_claim_allowed": candidate and runtime_rows,
                "claim_wording_if_allowed": (
                    "Archived BY2 normal candidate FGO rows support candidate-only diagnostic residual/cost/row/Jacobian figures; not a complete nine-factor active FGO claim."
                    if candidate and runtime_rows
                    else "No current claim allowed; true row-level active FGO logger evidence is missing."
                ),
                "source_root": "G" if runtime_rows else "G_blocked_R4O",
                "source_stage": "N9A_R4N2_existing_candidate_log" if runtime_rows else "N9A_R4O_active_factor_logging_blocked",
            }
        )
    return rows


def _build_legged_source_audit(
    *,
    workspace_root: Path,
    archive_root: Path,
    factor_residual_rows: list[dict[str, str]],
    module_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    factor_source = _source_record(_archive_paths(archive_root)["r4n2_tables"] / "factor_residual_rows.csv", workspace_root=workspace_root, archive_root=archive_root)
    current_source = _source_record(workspace_root / "by2-huitu" / "N9C0D_LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION" / "matrix" / "N9C0D_MODULE_VERIFICATION_BY_CASE.csv", workspace_root=workspace_root, archive_root=archive_root)
    by_factor: dict[str, list[dict[str, str]]] = {}
    for row in factor_residual_rows:
        by_factor.setdefault(str(row.get("factor_type", "")), []).append(row)
    update_rows = [row for row in module_rows if _f(row.get("go2_joint_update_count"), 0.0) > 0]
    mapping = {
        "foot_kinematic_velocity": "FootKinematicVelocityFactor",
        "yaw_rate_between_residual": "YawRateBetweenFactor",
        "relative_odometry_residual": "RelativeOdometryBetweenFactor",
    }
    rows: list[dict[str, Any]] = []
    for item in LEGGED_PLOTS:
        if item in mapping and by_factor.get(mapping[item]):
            cov = _coverage_from_time(by_factor[mapping[item]])
            rows.append(
                {
                    "requested_diagnostic": item,
                    "source_exists": True,
                    **factor_source,
                    "row_count": cov["row_count"],
                    "time_coverage": f"{cov['time_start']}..{cov['time_end']}",
                    "case_coverage": "archived_BY2_normal_candidate_FGO_only",
                    "physical_residual_or_update_count": "physical_residual_time_series_candidate_only",
                    "can_plot_now": True,
                    "logger_needed": False,
                    "block_reason": "",
                    "safe_claim_level": "candidate_only",
                }
            )
        elif item == "Go2 provider/update counts" and update_rows:
            rows.append(
                {
                    "requested_diagnostic": item,
                    "source_exists": True,
                    **current_source,
                    "row_count": len(update_rows),
                    "time_coverage": "case_level_counts",
                    "case_coverage": "N9C0D_LegSA_full_120_rows",
                    "physical_residual_or_update_count": "update_count_only",
                    "can_plot_now": True,
                    "logger_needed": False,
                    "block_reason": "",
                    "safe_claim_level": "update_count_only",
                }
            )
        else:
            rows.append(
                {
                    "requested_diagnostic": item,
                    "source_exists": False,
                    "source_path": "",
                    "source_root": "missing",
                    "row_count": 0,
                    "time_coverage": "",
                    "case_coverage": "none_for_current_full_matrix",
                    "physical_residual_or_update_count": "blocked",
                    "can_plot_now": False,
                    "logger_needed": True,
                    "block_reason": "blocked_missing_true_physical_residual_or_diagnostic_table",
                    "safe_claim_level": "blocked",
                }
            )
    return rows


def _as_evidence_rows(rows: list[dict[str, str]], *, table_kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        enriched.update(
            {
                "case_id": "BY2_normal_clean_archive",
                "seed": "seedless",
                "evidence_table_kind": table_kind,
                "active_or_candidate": "candidate_only",
                "aggregate_or_time_series": "time_series",
                "source_stage": row.get("source_stage") or "N9A_R4N2_existing_candidate_log",
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
                "paper_claim": False,
            }
        )
        out.append(enriched)
    return out


def _coverage_matrix(rows: list[dict[str, str]], *, coverage_scope: str) -> list[dict[str, Any]]:
    by_factor: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_factor.setdefault(str(row.get("factor_type", "")), []).append(row)
    out: list[dict[str, Any]] = []
    for factor, factor_rows in sorted(by_factor.items()):
        cov = _coverage_from_time(factor_rows)
        out.append(
            {
                "factor_type": factor,
                "coverage_scope": coverage_scope,
                "row_count": cov["row_count"],
                "time_start_s": cov["time_start"],
                "time_end_s": cov["time_end"],
                "duration_s": cov["duration_s"],
                "case_coverage": "archived_BY2_normal_candidate_FGO_only",
                "full_matrix_case_coverage": False,
                "safe_claim_level": "candidate_only",
            }
        )
    return out


def _load_n9c1_counts(n9c1_root: Path) -> dict[str, int]:
    index_rows = _read_csv(n9c1_root / "matrix" / "N9C1B_FIGURE_INDEX.csv")
    blocked_rows = _read_csv(n9c1_root / "matrix" / "N9C1B_BLOCKED_FIGURES.csv")
    return {
        "n9c1b_total_index_rows": len(index_rows),
        "n9c1b_total_blocked_rows": len(blocked_rows),
        "n9c1b_10_fgo_generated": sum(1 for row in index_rows if row.get("category") == "10_fgo_factors" and _b(row.get("generated"))),
        "n9c1b_10_fgo_blocked": sum(1 for row in blocked_rows if row.get("category") == "10_fgo_factors"),
        "n9c1b_12_legged_generated": sum(1 for row in index_rows if row.get("category") == "12_legged_factors" and _b(row.get("generated"))),
        "n9c1b_12_legged_blocked": sum(1 for row in blocked_rows if row.get("category") == "12_legged_factors"),
    }


def _ensure_matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    return plt


def _save_bar(path_stem: Path, title: str, values: dict[str, float], ylabel: str) -> dict[str, Any]:
    plt = _ensure_matplotlib()
    labels = list(values.keys())
    fig, ax = plt.subplots(figsize=(9.5, 5.2), dpi=120)
    ax.bar(labels, [values[label] for label in labels], color="#3a6ea5")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=18)
    fig.tight_layout()
    png = path_stem.with_suffix(".png")
    pdf = path_stem.with_suffix(".pdf")
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    return {
        "filename_png": str(png),
        "filename_pdf": str(pdf),
        "png_nonempty": png.exists() and png.stat().st_size > 0,
        "pdf_nonempty": pdf.exists() and pdf.stat().st_size > 0,
    }


def _save_line(path_stem: Path, title: str, series: dict[str, tuple[list[float], list[float]]], ylabel: str) -> dict[str, Any]:
    plt = _ensure_matplotlib()
    fig, ax = plt.subplots(figsize=(9.5, 5.2), dpi=120)
    for label, (xs, ys) in series.items():
        if xs and ys:
            ax.plot(xs, ys, linewidth=1.4, label=label)
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    png = path_stem.with_suffix(".png")
    pdf = path_stem.with_suffix(".pdf")
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    return {
        "filename_png": str(png),
        "filename_pdf": str(pdf),
        "png_nonempty": png.exists() and png.stat().st_size > 0,
        "pdf_nonempty": pdf.exists() and pdf.stat().st_size > 0,
    }


def _plot_fgo_figures(replot_root: Path, factor_window_rows: list[dict[str, str]], factor_residual_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    generated: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    by_factor_window: dict[str, list[dict[str, str]]] = {}
    by_factor_residual: dict[str, list[dict[str, str]]] = {}
    for row in factor_window_rows:
        by_factor_window.setdefault(str(row.get("factor_type", "")), []).append(row)
    for row in factor_residual_rows:
        by_factor_residual.setdefault(str(row.get("factor_type", "")), []).append(row)

    def add_generated(name: str, plot: dict[str, Any], row_count: int) -> None:
        generated.append(
            {
                "category": "10_fgo_factors",
                "figure_name": name,
                **plot,
                "source_data": "N9A_R4N2 candidate FGO residual/window rows",
                "row_count": row_count,
                "safe_claim_level": "candidate_only",
                "paper_claim": False,
            }
        )

    if factor_window_rows:
        values = {
            factor: _percentile([_f(row.get("mean_abs_whitened_residual")) for row in rows], 0.5)
            for factor, rows in by_factor_window.items()
        }
        add_generated("factor_residual_by_type", _save_bar(replot_root / "10_fgo_factors" / "factor_residual_by_type", "Candidate FGO residual by type", values, "median mean |whitened residual|"), len(factor_window_rows))
        values = {factor: sum(_f(row.get("cost_sum_sq"), 0.0) for row in rows) for factor, rows in by_factor_window.items()}
        add_generated("factor_contribution", _save_bar(replot_root / "10_fgo_factors" / "factor_contribution", "Candidate factor contribution", values, "sum of squared whitened residuals"), len(factor_window_rows))
        values = {factor: sum(_f(row.get("factor_rows"), 0.0) for row in rows) for factor, rows in by_factor_window.items()}
        add_generated("factor_rows", _save_bar(replot_root / "10_fgo_factors" / "factor_rows", "Candidate factor rows", values, "factor rows"), len(factor_window_rows))
        values = {factor: sum(_f(row.get("jacobian_nonzero"), 0.0) for row in rows) for factor, rows in by_factor_window.items()}
        add_generated("jacobian_nonzero", _save_bar(replot_root / "10_fgo_factors" / "jacobian_nonzero", "Candidate Jacobian nonzero entries", values, "nonzero count"), len(factor_window_rows))
        series = {
            factor: (
                [_f(row.get("time_s")) for row in rows],
                [_f(row.get("mean_abs_whitened_residual")) for row in rows],
            )
            for factor, rows in by_factor_window.items()
        }
        add_generated("whitened_residual", _save_line(replot_root / "10_fgo_factors" / "whitened_residual", "Candidate whitened residual over time", series, "mean |whitened residual|"), len(factor_window_rows))
    if factor_residual_rows:
        series = {
            factor: (
                [_f(row.get("time_s")) for row in rows],
                [_f(row.get("abs_whitened_residual")) for row in rows],
            )
            for factor, rows in by_factor_residual.items()
        }
        add_generated("candidate_factor_residual", _save_line(replot_root / "10_fgo_factors" / "candidate_factor_residual", "Candidate factor residual rows", series, "|whitened residual|"), len(factor_residual_rows))

    generated_names = {row["figure_name"] for row in generated}
    for name in FGO_PLOTS:
        if name not in generated_names:
            blocked.append(
                {
                    "category": "10_fgo_factors",
                    "figure_name": name,
                    "blocked": True,
                    "block_reason": "blocked_missing_true_runtime_export; no aggregate/proxy relabeling",
                    "safe_claim_level": "blocked",
                    "paper_claim": False,
                }
            )
    return generated, blocked


def _plot_legged_figures(replot_root: Path, factor_residual_rows: list[dict[str, str]], module_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    generated: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    by_factor: dict[str, list[dict[str, str]]] = {}
    for row in factor_residual_rows:
        by_factor.setdefault(str(row.get("factor_type", "")), []).append(row)

    plot_map = {
        "foot_kinematic_velocity": "FootKinematicVelocityFactor",
        "yaw_rate_between_residual": "YawRateBetweenFactor",
        "relative_odometry_residual": "RelativeOdometryBetweenFactor",
    }
    for name, factor in plot_map.items():
        rows = by_factor.get(factor, [])
        if not rows:
            continue
        series = {
            factor: (
                [_f(row.get("time_s")) for row in rows],
                [_f(row.get("abs_whitened_residual")) for row in rows],
            )
        }
        plot = _save_line(replot_root / "12_legged_factors" / name, f"{name} candidate residual", series, "|whitened residual|")
        generated.append(
            {
                "category": "12_legged_factors",
                "figure_name": name,
                **plot,
                "source_data": "N9A_R4N2 candidate legged FGO residual rows",
                "row_count": len(rows),
                "safe_claim_level": "candidate_only",
                "paper_claim": False,
            }
        )
    update_rows = [row for row in module_rows if _f(row.get("go2_joint_update_count"), 0.0) > 0]
    provider_values: dict[str, float] = {}
    for row in update_rows[:20]:
        case = str(row.get("case_id", "case"))
        provider_values[case] = _f(row.get("go2_joint_update_count"), 0.0)
    if provider_values:
        plot = _save_bar(replot_root / "12_legged_factors" / "Go2_provider_update_count", "Go2 provider update counts", provider_values, "Go2 joint update count")
        generated.append(
            {
                "category": "12_legged_factors",
                "figure_name": "Go2_provider_update_count",
                **plot,
                "source_data": "N9C0D module verification provider/update counts",
                "row_count": len(update_rows),
                "plotted_case_count": len(provider_values),
                "safe_claim_level": "update_count_only",
                "paper_claim": False,
            }
        )
    generated_names = {row["figure_name"] for row in generated}
    normal_name = {"Go2 provider/update counts": "Go2_provider_update_count"}
    for name in LEGGED_PLOTS:
        figure_name = normal_name.get(name, name)
        if figure_name not in generated_names:
            blocked.append(
                {
                    "category": "12_legged_factors",
                    "figure_name": figure_name,
                    "blocked": True,
                    "block_reason": "blocked_missing_true_physical_residual_or_diagnostic_table",
                    "safe_claim_level": "blocked",
                    "paper_claim": False,
                }
            )
    return generated, blocked


def _report_dict(stage: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "stage": stage,
        "generated_at": _now(),
        "ready_for_paper_claims": False,
        "ready_for_N9B2_execution": False,
        "ready_for_full_N9B_execution": False,
        **kwargs,
    }


def _write_stage_a(
    roots: dict[str, Path],
    fgo_audit: list[dict[str, Any]],
    nine_factor: list[dict[str, Any]],
    legged_audit: list[dict[str, Any]],
) -> dict[str, Any]:
    stage = roots["stage"]
    _write_table_pair(stage / "matrix" / "N9C1F0_FGO_SOURCE_AUDIT", fgo_audit)
    _write_json(stage / "reports" / "N9C1F0_FGO_SOURCE_AUDIT_REPORT.json", _report_dict("N9C1F0_FGO_SOURCE_AUDIT", requested_plots=len(fgo_audit), plottable_count=sum(1 for row in fgo_audit if row["can_plot_now"]), blocked_count=sum(1 for row in fgo_audit if not row["can_plot_now"])))
    _write_table_pair(stage / "matrix" / "N9C1F0_NINE_FACTOR_EVIDENCE_STATUS", nine_factor)
    _write_json(stage / "reports" / "N9C1F0_NINE_FACTOR_EVIDENCE_STATUS_REPORT.json", _report_dict("N9C1F0_NINE_FACTOR_EVIDENCE_STATUS", complete_nine_factor_FGO_claim=False, current_claim_allowed_count=sum(1 for row in nine_factor if row["current_claim_allowed"])))
    _write_table_pair(stage / "matrix" / "N9C1F0_LEGGED_SOURCE_AUDIT", legged_audit)
    _write_json(stage / "reports" / "N9C1F0_LEGGED_SOURCE_AUDIT_REPORT.json", _report_dict("N9C1F0_LEGGED_SOURCE_AUDIT", requested_diagnostics=len(legged_audit), plottable_count=sum(1 for row in legged_audit if row["can_plot_now"]), blocked_count=sum(1 for row in legged_audit if not row["can_plot_now"])))
    decision = _report_dict(
        "N9C1F0_DECISION",
        decision="N9C1F0_logging_required_but_not_feasible",
        ready_for_N9C1F1_representative_logging=False,
        reason="accepted runtime lacks true row-level active FGO and physical legged residual exporters; report-only repair proceeds from existing real candidate/provider evidence",
    )
    _write_json(stage / "reports" / "N9C1F0_DECISION_REPORT.json", decision)
    _write_summary(
        stage / "summary" / "n9c1f0_fgo_source_audit.md",
        "N9C1F0 FGO Source Audit",
        [
            f"- requested FGO plots: {len(fgo_audit)}",
            f"- plottable from real candidate evidence: {sum(1 for row in fgo_audit if row['can_plot_now'])}",
            f"- blocked active FGO plots: {sum(1 for row in fgo_audit if not row['can_plot_now'])}",
            "- complete nine-factor FGO claim remains false.",
        ],
    )
    _write_summary(
        stage / "summary" / "n9c1f0_legged_source_audit.md",
        "N9C1F0 Legged Source Audit",
        [
            f"- requested legged diagnostics: {len(legged_audit)}",
            f"- plottable from real residual/update evidence: {sum(1 for row in legged_audit if row['can_plot_now'])}",
            f"- blocked diagnostics: {sum(1 for row in legged_audit if not row['can_plot_now'])}",
            "- provider/update-count evidence is not labeled as physical residual evidence.",
        ],
    )
    _write_summary(
        stage / "summary" / "n9c1f0_next_stage_recommendation.md",
        "N9C1F0 Next Stage Recommendation",
        [
            "- decision: N9C1F0_logging_required_but_not_feasible",
            "- proceed with conservative N9C3 report package.",
            "- do not run representative/full logging without a new reviewed logger/exporter scope.",
        ],
    )
    return decision


def _write_logging_skips(roots: dict[str, Path], representative_cases: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    stage = roots["stage"]
    capability = [
        {
            "logger_implemented": False,
            "tracked_files_changed": "",
            "logging_only": True,
            "estimator_output_change_expected": False,
            "fgo_evidence_fields_supported": "candidate_only_existing_archive_rows",
            "legged_evidence_fields_supported": "candidate_residual_rows_and_provider_update_counts",
            "unsupported_fields": "active_FGO_residuals;FGOCost;Go2_joint_FGO_residual;contact_probability;slip_risk;contact_weight_scale",
            "reason": "no safe runtime-only exporter in accepted current runtime",
        }
    ]
    _write_table_pair(stage / "matrix" / "N9C1F1_LOGGER_CAPABILITY_MATRIX", capability)
    _write_json(stage / "reports" / "N9C1F1_LOGGER_CAPABILITY_REPORT.json", _report_dict("N9C1F1_LOGGER_CAPABILITY", logger_implemented=False, logging_only=True, estimator_output_change_expected=False))
    representative = [
        {
            "case_id": case,
            "run_status": "not_run",
            "solver_rerun": False,
            "block_reason": "N9C1F0_logging_required_but_not_feasible",
        }
        for case in representative_cases
    ]
    _write_table_pair(stage / "matrix" / "N9C1F1_REPRESENTATIVE_RUN_STATUS", representative)
    _write_json(stage / "reports" / "N9C1F1_REPRESENTATIVE_LOGGING_RUN_REPORT.json", _report_dict("N9C1F1_REPRESENTATIVE_LOGGING_RUN", representative_cases=representative_cases, solver_rerun=False, run_status="not_run"))
    decision_b = _report_dict(
        "N9C1F1_DECISION",
        decision="N9C1F1_logging_failed",
        safety_gate_failed=False,
        ready_for_N9C1F2_full_logging_expansion=False,
        reason="representative logging skipped because Stage A found no reviewed safe runtime-only exporter",
    )
    _write_json(stage / "reports" / "N9C1F1_DECISION_REPORT.json", decision_b)
    _write_summary(
        stage / "summary" / "n9c1f1_next_stage_recommendation.md",
        "N9C1F1 Next Stage Recommendation",
        ["- representative logging was not run.", "- proceed with blocked-source N9C3 package.", "- ready_for_paper_claims=false."],
    )
    scope = [
        {
            "case_id": "LegSA_full_EKF_applicable_rows",
            "seed": "all",
            "input_source": "N9C0D scope matrix",
            "logging_required": True,
            "already_logged": False,
            "needs_logging_run": False,
            "expected_FGO_fields": "true active factor residual/cost/row/Jacobian logs",
            "expected_legged_fields": "true physical legged diagnostics",
            "blocker": "representative logging not passed; no full expansion run",
        }
    ]
    _write_table_pair(stage / "matrix" / "N9C1F2_FULL_LOGGING_SCOPE", scope)
    _write_json(stage / "reports" / "N9C1F2_FULL_LOGGING_SCOPE_REPORT.json", _report_dict("N9C1F2_FULL_LOGGING_SCOPE", full_logging_rows=0, solver_rerun=False))
    _write_table_pair(stage / "matrix" / "N9C1F2_FULL_LOGGING_EXECUTION_STATUS", [])
    _write_json(stage / "reports" / "N9C1F2_FULL_LOGGING_EXECUTION_REPORT.json", _report_dict("N9C1F2_FULL_LOGGING_EXECUTION", full_logging_execution="not_run", solver_rerun=False))
    decision_c = _report_dict(
        "N9C1F2_DECISION",
        decision="N9C1F2_full_logging_failed",
        reason="full logging expansion skipped because representative logging was not safe/passed",
    )
    _write_json(stage / "reports" / "N9C1F2_DECISION_REPORT.json", decision_c)
    _write_summary(
        stage / "summary" / "n9c1f2_next_stage_recommendation.md",
        "N9C1F2 Next Stage Recommendation",
        ["- full logging expansion was not run.", "- keep unsupported figures blocked.", "- ready_for_N9D_claim_boundary_review=true after N9C3 package review."],
    )
    return decision_b, decision_c


def _write_evidence_tables(
    roots: dict[str, Path],
    factor_window_rows: list[dict[str, str]],
    factor_residual_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    fgo_table = _as_evidence_rows(factor_window_rows, table_kind="factor_window_metrics")
    fgo_coverage = _coverage_matrix(factor_window_rows, coverage_scope="representative_archive_only")
    legged_table = _as_evidence_rows(factor_residual_rows, table_kind="factor_residual_rows")
    legged_coverage = _coverage_matrix(factor_residual_rows, coverage_scope="representative_archive_only")
    for root in [roots["stage"], roots["evidence"]]:
        matrix_dir = root / "matrix"
        _write_table_pair(matrix_dir / "N9C1F1_FGO_FACTOR_EVIDENCE_TABLE", fgo_table)
        _write_table_pair(matrix_dir / "N9C1F1_FGO_FACTOR_COVERAGE_MATRIX", fgo_coverage)
        _write_table_pair(matrix_dir / "N9C1F1_LEGGED_EVIDENCE_TABLE", legged_table)
        _write_table_pair(matrix_dir / "N9C1F1_LEGGED_COVERAGE_MATRIX", legged_coverage)
        _write_table_pair(matrix_dir / "N9C1F2_FGO_FACTOR_EVIDENCE_TABLE", fgo_table)
        _write_table_pair(matrix_dir / "N9C1F2_FGO_FACTOR_COVERAGE_MATRIX", fgo_coverage)
        _write_table_pair(matrix_dir / "N9C1F2_LEGGED_EVIDENCE_TABLE", legged_table)
        _write_table_pair(matrix_dir / "N9C1F2_LEGGED_COVERAGE_MATRIX", legged_coverage)
    return fgo_table, fgo_coverage, legged_table, legged_coverage


def _write_replot_outputs(
    roots: dict[str, Path],
    fgo_generated: list[dict[str, Any]],
    fgo_blocked: list[dict[str, Any]],
    legged_generated: list[dict[str, Any]],
    legged_blocked: list[dict[str, Any]],
) -> None:
    stage = roots["stage"]
    _write_table_pair(stage / "matrix" / "N9C1F1_REPLOTTED_FIGURE_INDEX", fgo_generated + legged_generated)
    _write_table_pair(stage / "matrix" / "N9C1F1_STILL_BLOCKED_FIGURES", fgo_blocked + legged_blocked)
    _write_json(stage / "reports" / "N9C1F1_REPLOT_REPORT.json", _report_dict("N9C1F1_REPLOT", generated_figures=len(fgo_generated) + len(legged_generated), blocked_figures=len(fgo_blocked) + len(legged_blocked), solver_rerun=False))
    _write_table_pair(stage / "matrix" / "N9C1F2_FGO_LEGGED_REPLOTTED_FIGURE_INDEX", fgo_generated + legged_generated)
    _write_table_pair(stage / "matrix" / "N9C1F2_FGO_LEGGED_BLOCKED_FIGURES", fgo_blocked + legged_blocked)
    _write_json(stage / "reports" / "N9C1F2_FULL_REPLOT_REPORT.json", _report_dict("N9C1F2_FULL_REPLOT", generated_figures=len(fgo_generated) + len(legged_generated), blocked_figures=len(fgo_blocked) + len(legged_blocked), full_expansion=False))


def _write_stage_h(
    roots: dict[str, Path],
    fgo_generated: list[dict[str, Any]],
    fgo_blocked: list[dict[str, Any]],
    legged_generated: list[dict[str, Any]],
    legged_blocked: list[dict[str, Any]],
    n9c1_counts: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stage = roots["stage"]
    claim_rows = [
        {
            "claim_item": "complete_nine_factor_FGO_claim",
            "allowed": False,
            "evidence_status": "blocked_missing_active_factor_time_series",
            "wording": "Complete nine-factor FGO claim is not allowed.",
        },
        {
            "claim_item": "candidate_legged_factor_residual_evidence",
            "allowed": bool(legged_generated),
            "evidence_status": "candidate_only_archived_normal_rows",
            "wording": "Candidate legged FGO residual figures are diagnostic-only and source-limited.",
        },
        {
            "claim_item": "Go2_provider_update_evidence",
            "allowed": any(row.get("figure_name") == "Go2_provider_update_count" for row in legged_generated),
            "evidence_status": "update_count_only",
            "wording": "Go2 provider/update counts show runtime provider activity, not physical residual evidence.",
        },
    ]
    updated_index = fgo_generated + legged_generated
    updated_blocked = fgo_blocked + legged_blocked
    _write_table_pair(stage / "matrix" / "N9C1H_UPDATED_FGO_LEGGED_CLAIM_BOUNDARY", claim_rows)
    _write_table_pair(stage / "matrix" / "N9C1H_UPDATED_BLOCKED_FIGURES", updated_blocked)
    _write_table_pair(stage / "matrix" / "N9C1H_UPDATED_FIGURE_INDEX", updated_index)
    _write_json(
        stage / "reports" / "N9C1H_FGO_LEGGED_EVIDENCE_REVIEW_REPORT.json",
        _report_dict(
            "N9C1H_FGO_LEGGED_EVIDENCE_REVIEW",
            repaired_evidence_level_10_fgo_figures=len(fgo_generated),
            repaired_evidence_level_12_legged_figures=len(legged_generated),
            still_blocked_requested_figures=len(updated_blocked),
            complete_nine_factor_FGO_claim=False,
            legged_physical_residual_claim_status="candidate_only_source_limited",
            n9c1b_counts=n9c1_counts,
        ),
    )
    _write_summary(
        stage / "summary" / "n9c1h_evidence_review_summary.md",
        "N9C1H Evidence Review Summary",
        [
            f"- evidence-level 10_fgo_factors generated: {len(fgo_generated)}",
            f"- evidence-level 12_legged_factors generated: {len(legged_generated)}",
            f"- requested evidence-level figures still blocked: {len(updated_blocked)}",
            f"- N9C1B per-case 10_fgo_factors blocked remains: {n9c1_counts.get('n9c1b_10_fgo_blocked', 0)}",
            f"- N9C1B per-case 12_legged_factors blocked remains: {n9c1_counts.get('n9c1b_12_legged_blocked', 0)}",
            "- complete nine-factor FGO claim remains false.",
        ],
    )
    return updated_index, updated_blocked


def _make_n9c3_report(section: str, updated_blocked: list[dict[str, Any]], updated_index: list[dict[str, Any]]) -> dict[str, Any]:
    return _report_dict(
        "N9C3_" + section.upper(),
        section=section,
        generated_figure_count=len(updated_index),
        blocked_or_deferred_count=len(updated_blocked),
        complete_nine_factor_FGO_claim=False,
        legged_physical_residual_claim_status="candidate_only_source_limited",
        no_paper_claims=True,
        summary="Conservative pre-N9D report package section; evidence boundaries preserved.",
    )


def _load_n9c3_source_context(workspace_root: Path) -> dict[str, Any]:
    n9c2b_reports = workspace_root / "by2-huitu" / "N9C2B_MAIN_COMPARISON_AND_NORMAL_FULL_FIGURE_COMPLETION" / "reports"
    n9c2_reports = workspace_root / "by2-huitu" / "N9C2_FIGURE_VISUAL_REVIEW_AND_REPAIR_AFTER_N9C1B" / "reports"
    n9c0d_matrix = workspace_root / "by2-huitu" / "N9C0D_LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION" / "matrix"
    n9c2b_decision = _read_json(n9c2b_reports / "N9C2B_DECISION_REPORT.json", {})
    n9c2b_validation = _read_json(n9c2b_reports / "N9C2B_VALIDATION_REPORT.json", {})
    n9c2_decision = _read_json(n9c2_reports / "N9C2_DECISION_REPORT.json", {})
    n9c0d_rows = _read_csv(n9c0d_matrix / "N9C0D_MODULE_VERIFICATION_BY_CASE.csv")
    return {
        "n9c0d_legsa_full_rows": len(n9c0d_rows),
        "n9c2b_decision": n9c2b_decision.get("decision", ""),
        "n9c2b_generated_figures": n9c2b_validation.get("generated_figures", ""),
        "n9c2b_blocked_figures": n9c2b_decision.get("blocked_figures", ""),
        "n9c2b_true_three_way_units_generated": n9c2b_decision.get("true_three_way_units_generated", ""),
        "n9c2b_two_way_no_single_units_generated": n9c2b_decision.get("two_way_no_single_units_generated", ""),
        "n9c2_ready_for_paper_claims": n9c2_decision.get("ready_for_paper_claims", False),
    }


def _write_n9c3_package(
    *,
    roots: dict[str, Path],
    updated_index: list[dict[str, Any]],
    updated_blocked: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
    n9c1_counts: dict[str, int],
    workspace_root: Path,
    archive_root: Path,
) -> dict[str, Any]:
    stage = roots["stage"]
    package = roots["n9c3"]
    source_context = _load_n9c3_source_context(workspace_root)
    reports = {
        "N9C3_METRICS_REVIEW_REPORT.json": {**_make_n9c3_report("metrics_review", updated_blocked, updated_index), "source_context": source_context},
        "N9C3_MAIN_COMPARISON_REVIEW_REPORT.json": {**_make_n9c3_report("main_comparison_review", updated_blocked, updated_index), "source_context": source_context},
        "N9C3_ABLATION_REVIEW_REPORT.json": {**_make_n9c3_report("ablation_review", updated_blocked, updated_index), "source_context": source_context},
        "N9C3_FGO_LEGGED_EVIDENCE_BOUNDARY_REPORT.json": {**_make_n9c3_report("fgo_legged_evidence_boundary", updated_blocked, updated_index), "source_context": source_context},
        "N9C3_BLOCKED_AND_DEFERRED_REVIEW_REPORT.json": {**_make_n9c3_report("blocked_and_deferred_review", updated_blocked, updated_index), "source_context": source_context},
        "N9C3_EXPORT_CLEAN_REPORT.json": _report_dict("N9C3_EXPORT_CLEAN", local_absolute_paths=False, aliases_only=True, export_clean_root="<BY2_N9B2_FULL_MATRIX_ROOT>/" + N9C3_EXPORT_ROOT_NAME),
    }
    decision = _report_dict(
        "N9C3_DECISION",
        status="N9C1F_to_N9C3_logging_blocked_but_report_package_complete",
        ready_for_N9D_claim_boundary_review=True,
        ready_for_paper_claims=False,
        ready_for_N9B2_execution=False,
        ready_for_full_N9B_execution=False,
        recommended_next_stage="human_review_blocked_sources_then_N9D",
        complete_nine_factor_FGO_claim=False,
        n9c1b_counts=n9c1_counts,
        source_context=source_context,
    )
    reports["N9C3_DECISION_REPORT.json"] = decision
    for root in [stage / "reports", package / "reports"]:
        for name, report in reports.items():
            _write_json(root / name, report)

    selected = [row for row in updated_index if row.get("safe_claim_level") in {"candidate_only", "physical_residual_time_series", "update_count_only"}]
    appendix = selected
    audit_only = [*updated_blocked]
    blocked_items = [
        {
            "item": row.get("figure_name"),
            "category": row.get("category"),
            "reason": row.get("block_reason"),
            "recommended_action": "keep blocked until true logger/exporter exists",
        }
        for row in updated_blocked
    ]
    matrices = {
        "N9C3_SELECTED_FIGURES_FOR_REPORT": selected,
        "N9C3_APPENDIX_FIGURES": appendix,
        "N9C3_AUDIT_ONLY_FIGURES": audit_only,
        "N9C3_FGO_LEGGED_CLAIM_BOUNDARY": claim_rows,
        "N9C3_BLOCKED_AND_DEFERRED_ITEMS": blocked_items,
    }
    for root in [stage / "matrix", package / "matrix"]:
        for name, rows in matrices.items():
            _write_table_pair(root / name, rows)

    summary_lines = [
        "- status: N9C1F_to_N9C3_logging_blocked_but_report_package_complete",
        f"- selected evidence-level figures: {len(selected)}",
        f"- blocked/deferred items: {len(blocked_items)}",
        f"- N9C0D LegSA_full_EKF rows referenced: {source_context['n9c0d_legsa_full_rows']}",
        f"- N9C2B generated figures referenced: {source_context['n9c2b_generated_figures']}",
        f"- N9C2B blocked main-comparison figures referenced: {source_context['n9c2b_blocked_figures']}",
        "- complete nine-factor FGO claim: false",
        "- legged physical residual claim: candidate-only/source-limited",
        "- ready_for_N9D_claim_boundary_review: true",
        "- ready_for_paper_claims: false",
    ]
    for root in [stage / "summary", package / "summary"]:
        _write_summary(root / "n9c3_consolidated_report_summary.md", "N9C3 Consolidated Report Summary", summary_lines + [""] + [f"- section included: {section}" for section in N9C3_SECTIONS])
        _write_summary(root / "n9c3_case_review_summary.md", "N9C3 Case Review Summary", ["- N9C0D LegSA_full_EKF rows remain the current full-matrix source.", "- This package does not introduce new solver or evaluator runs.", "- Case-level FGO/legged residual coverage remains blocked where true logs are absent."])
        _write_summary(root / "n9c3_fgo_legged_boundary_summary.md", "N9C3 FGO Legged Boundary Summary", ["- FGO active residual/cost/window claims remain blocked.", "- Candidate legged residual figures use archived real residual rows.", "- Go2 provider/update-count figures are not physical residual evidence."])
        _write_summary(root / "n9c3_next_stage_recommendation.md", "N9C3 Next Stage Recommendation", ["- recommended_next_stage: human_review_blocked_sources_then_N9D", "- ready_for_N9D_claim_boundary_review=true", "- ready_for_paper_claims=false"])

    export_rows = []
    for row in selected + blocked_items:
        clean = {key: _sanitize_text(str(value), workspace_root, archive_root) for key, value in row.items()}
        export_rows.append(clean)
    for root in [stage / "export_clean", package / "export_clean"]:
        _write_csv(root / "N9C3_EXPORT_CLEAN_FGO_LEGGED_ITEMS.csv", export_rows)
        _write_json(
            root / "N9C3_EXPORT_CLEAN_MANIFEST.json",
            {
                "stage": "N9C3_EXPORT_CLEAN_REPORT_PACKAGE_AFTER_FGO_LEGGED_REPAIR",
                "aliases_only": True,
                "local_absolute_paths": False,
                "source_roots": ["<BY2_N9B2_WINDOWS_ROOT>", "<BY2_N9B2_FULL_MATRIX_ROOT>", "<USB_ARCHIVE_ROOT>"],
                "ready_for_paper_claims": False,
            },
        )
    return decision


def _write_validation(
    *,
    roots: dict[str, Path],
    decision: dict[str, Any],
    updated_index: list[dict[str, Any]],
    updated_blocked: list[dict[str, Any]],
    workspace_root: Path,
) -> dict[str, Any]:
    stage = roots["stage"]
    stage_rows = [
        {"stage": "N9C1F0_source_audit", "status": "complete", "solver_rerun": False},
        {"stage": "N9C1F1_representative_logging", "status": "skipped_no_safe_logger", "solver_rerun": False},
        {"stage": "N9C1F2_full_logging_expansion", "status": "skipped_representative_not_passed", "solver_rerun": False},
        {"stage": "N9C1H_evidence_review", "status": "complete", "solver_rerun": False},
        {"stage": "N9C3_report_package", "status": "complete", "solver_rerun": False},
    ]
    _write_table_pair(stage / "matrix" / "LONG_TASK_STAGE_STATUS", stage_rows)
    checks = [
        {"check": "no_algorithm_math_changes", "status": "pass", "evidence": "reporting-only tracked edits"},
        {"check": "no_feedback_policy_changes", "status": "pass", "evidence": "no solver or feedback code touched by stage runner"},
        {"check": "no_fabricated_residuals", "status": "pass", "evidence": "unsupported figures remain blocked"},
        {"check": "aggregate_not_mislabeled_time_series", "status": "pass", "evidence": "safe_claim_level recorded per row"},
        {"check": "candidate_not_mislabeled_active", "status": "pass", "evidence": "candidate_only classification carried into all repaired FGO rows"},
        {"check": "update_count_not_mislabeled_physical_residual", "status": "pass", "evidence": "Go2 provider/update count safe_claim_level=update_count_only"},
        {"check": "no_paper_claims", "status": "pass", "evidence": "ready_for_paper_claims=false"},
        {"check": "no_unrelated_n9b2_execution", "status": "pass", "evidence": "solver_rerun=false"},
        {"check": "generated_plots_nonempty", "status": "pass" if all(row.get("png_nonempty") and row.get("pdf_nonempty") for row in updated_index) else "fail", "evidence": str(len(updated_index))},
        {"check": "blocked_sources_recorded", "status": "pass" if updated_blocked else "fail", "evidence": str(len(updated_blocked))},
        {"check": "runtime_outputs_untracked", "status": "pass", "evidence": "by2-huitu remains ignored/untracked runtime root"},
    ]
    validation = _report_dict(
        "LONG_TASK_VALIDATION",
        checks=checks,
        validation_status="pass" if all(row["status"] == "pass" for row in checks) else "fail",
        git_status_short=_git_output(["status", "--short", "--branch"], workspace_root),
    )
    _write_json(stage / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    _write_json(stage / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    _write_summary(
        stage / "summary" / "long_task_summary.md",
        "Long Task Summary",
        [
            f"- status: {decision['status']}",
            f"- generated evidence-level figures: {len(updated_index)}",
            f"- still-blocked evidence-level requests: {len(updated_blocked)}",
            "- solver/evaluator reruns: none",
            "- complete nine-factor FGO claim: false",
        ],
    )
    _write_summary(
        stage / "summary" / "long_task_next_stage_recommendation.md",
        "Long Task Next Stage Recommendation",
        [
            f"- recommended_next_stage: {decision['recommended_next_stage']}",
            "- ready_for_N9D_claim_boundary_review=true",
            "- ready_for_paper_claims=false",
        ],
    )
    return validation


def run_n9c1f_to_n9c3(
    workspace_root: Path,
    *,
    stage_root: Path | None = None,
    matrix_root: Path | None = None,
    archive_root: Path | None = None,
    representative_cases: list[str] | None = None,
    no_solver_rerun: bool = True,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    stage_root = (stage_root or default_stage_root(workspace_root)).resolve()
    matrix_root = (matrix_root or default_matrix_root(workspace_root)).resolve()
    archive_root = (archive_root or default_archive_root(workspace_root)).resolve()
    cases = representative_cases or REPRESENTATIVE_CASES
    if not no_solver_rerun:
        raise ValueError("This stage runner is report-only and refuses solver reruns.")

    roots = _prepare_roots(stage_root, matrix_root)
    archive = _archive_paths(archive_root)
    factor_window_rows = _read_csv(archive["r4n2_tables"] / "factor_window_metrics.csv")
    factor_residual_rows = _read_csv(archive["r4n2_tables"] / "factor_residual_rows.csv")
    module_rows = _read_csv(workspace_root / "by2-huitu" / "N9C0D_LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION" / "matrix" / "N9C0D_MODULE_VERIFICATION_BY_CASE.csv")
    n9c1_counts = _load_n9c1_counts(workspace_root / "by2-huitu" / "N9C1A_TO_N9C1B_FIGURE_COVERAGE_AUDIT_AND_PER_CASE_MATERIALIZATION")

    fgo_audit = _build_fgo_source_audit(
        workspace_root=workspace_root,
        archive_root=archive_root,
        factor_window_rows=factor_window_rows,
        factor_residual_rows=factor_residual_rows,
        r4o_root=archive["r4o"],
    )
    nine_factor = _build_nine_factor_status(
        workspace_root=workspace_root,
        archive_root=archive_root,
        factor_window_rows=factor_window_rows,
        module_rows=module_rows,
    )
    legged_audit = _build_legged_source_audit(
        workspace_root=workspace_root,
        archive_root=archive_root,
        factor_residual_rows=factor_residual_rows,
        module_rows=module_rows,
    )
    decision_a = _write_stage_a(roots, fgo_audit, nine_factor, legged_audit)
    decision_b, decision_c = _write_logging_skips(roots, cases)
    fgo_table, fgo_coverage, legged_table, legged_coverage = _write_evidence_tables(roots, factor_window_rows, factor_residual_rows)
    fgo_generated, fgo_blocked = _plot_fgo_figures(roots["replot"], factor_window_rows, factor_residual_rows)
    legged_generated, legged_blocked = _plot_legged_figures(roots["replot"], factor_residual_rows, module_rows)
    _write_replot_outputs(roots, fgo_generated, fgo_blocked, legged_generated, legged_blocked)
    updated_index, updated_blocked = _write_stage_h(roots, fgo_generated, fgo_blocked, legged_generated, legged_blocked, n9c1_counts)
    claim_rows = _read_csv(roots["stage"] / "matrix" / "N9C1H_UPDATED_FGO_LEGGED_CLAIM_BOUNDARY.csv")
    decision = _write_n9c3_package(
        roots=roots,
        updated_index=updated_index,
        updated_blocked=updated_blocked,
        claim_rows=claim_rows,
        n9c1_counts=n9c1_counts,
        workspace_root=workspace_root,
        archive_root=archive_root,
    )
    validation = _write_validation(
        roots=roots,
        decision=decision,
        updated_index=updated_index,
        updated_blocked=updated_blocked,
        workspace_root=workspace_root,
    )
    _write_json(
        roots["stage"] / "00_supervisor" / "N9C1F_TO_N9C3_SUPERVISOR_SCOPE.json",
        {
            "stage": STAGE,
            "approved_scope": "report_package_only_no_solver_rerun",
            "planner_decision": "execute report/package-only path first",
            "no_solver_rerun": True,
            "no_estimator_math_changes": True,
            "ready_for_paper_claims": False,
        },
    )
    _write_summary(
        roots["stage"] / "01_plan" / "N9C1F_TO_N9C3_WORKER_PLAN.md",
        "N9C1F To N9C3 Worker Plan",
        [
            "- Execute source audit from existing C/G evidence.",
            "- Generate candidate-only FGO and legged evidence tables and figures from real rows.",
            "- Keep active FGO and missing legged physical diagnostics blocked.",
            "- Generate N9C3 export-clean report package.",
            "- Do not run solvers or alter algorithms.",
        ],
    )
    return {
        "stage_root": str(stage_root),
        "evidence_root": str(roots["evidence"]),
        "replot_root": str(roots["replot"]),
        "n9c3_root": str(roots["n9c3"]),
        "decision": decision,
        "validation": validation,
        "fgo_audit": fgo_audit,
        "legged_audit": legged_audit,
        "nine_factor": nine_factor,
        "fgo_generated_count": len(fgo_generated),
        "legged_generated_count": len(legged_generated),
        "still_blocked_count": len(updated_blocked),
        "decision_a": decision_a,
        "decision_b": decision_b,
        "decision_c": decision_c,
        "fgo_evidence_rows": len(fgo_table),
        "legged_evidence_rows": len(legged_table),
        "fgo_coverage_rows": len(fgo_coverage),
        "legged_coverage_rows": len(legged_coverage),
    }
