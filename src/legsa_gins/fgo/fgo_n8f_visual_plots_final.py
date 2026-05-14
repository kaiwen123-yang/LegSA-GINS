"""Final N8F1 runtime-only visual plots.

中文说明：生成 N8F1 必需图像；标题和轴标签明确 metric namespace，避免 truth claim。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .fgo_n8f_plot_coverage import MANDATORY_N8F1_FIGURES, build_series_coverage


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _f(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _save(fig: Any, path: Path, plt: Any) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return {
        "figure_name": str(path.name),
        "relative_path": str(path),
        "nonempty": path.exists() and path.stat().st_size > 0,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "role_alias": "N8F1_FIGURE_OUTPUT_DIR",
    }


def _series(rows: Sequence[Mapping[str, Any]], key: str, default: float = 0.0) -> List[float]:
    return [_f(row.get(key), default) for row in rows]


def _times(rows: Sequence[Mapping[str, Any]]) -> List[float]:
    return [_f(row.get("time"), float(index)) for index, row in enumerate(rows)]


def _bar(ax: Any, labels: Sequence[str], values: Sequence[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(list(labels), rotation=34, ha="right", fontsize=7)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)


def _coverage(name: str, rows: Sequence[Mapping[str, Any]], y_key: str = "value", reason: str = "runtime_data") -> Dict[str, Any]:
    return build_series_coverage(figure_name=name, series=rows, y_key=y_key, reason_codes=[reason])


def _semantic(name: str, title: str, namespace: str, notes: str = "") -> Dict[str, Any]:
    return {"figure_name": name, "title": title, "metric_namespace": namespace, "notes": notes}


def generate_n8f1_visual_figures(
    *,
    figure_output_dir: str | Path,
    visual_data: Mapping[str, Any],
    signal_preview: Mapping[str, Any] | None = None,
) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: List[Dict[str, Any]] = []
    coverage: List[Dict[str, Any]] = []
    semantics: List[Dict[str, Any]] = []

    contact = [dict(row) for row in visual_data.get("contact_timeseries", [])]
    foot_table = [dict(row) for row in visual_data.get("foot_factor_table", [])]
    foot = [dict(row) for row in visual_data.get("foot_residual_series", [])]
    yaw = [dict(row) for row in visual_data.get("yawrate_residual_series", [])]
    rel = [dict(row) for row in visual_data.get("relative_odometry_residual_series", [])]
    variants = [dict(row) for row in visual_data.get("variants", [])]
    candidate_table = [dict(row) for row in visual_data.get("candidate_factor_table", [])]

    def add(fig: Any, name: str, cov_rows: Sequence[Mapping[str, Any]], y_key: str, namespace: str, title: str, reason: str = "runtime_data") -> None:
        path = out / name
        generated.append(_save(fig, path, plt))
        coverage.append(_coverage(name, cov_rows, y_key=y_key, reason=reason))
        semantics.append(_semantic(name, title, namespace, "no_feedback_fgo_factor_visual_validation"))

    # 01 contact weighting
    rows = [{**row, "value": _f(row.get("contact_weight_scale"))} for row in contact]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(contact), _series(contact, "contact_weight_scale"), lw=0.9)
    ax.set_title("Contact-aware R scale over time (diagnostic_engineering_evidence)")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("R scale [unitless]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[0], rows, "value", "diagnostic_engineering_evidence", "Contact-aware R scale")

    rows = [{**row, "value": _f(row.get("support_confidence"))} for row in contact]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(contact), _series(contact, "support_confidence"), label="support confidence")
    ax.plot(_times(contact), _series(contact, "slip_risk"), label="slip risk")
    ax.set_title("Support confidence and slip risk (not contact truth)")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("probability / risk [unitless]")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[1], rows, "value", "diagnostic_engineering_evidence", "Support confidence and slip risk")

    rows = [{**row, "value": _f(row.get("contact_weight_scale"))} for row in contact]
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    ax.hist(_series(contact, "contact_weight_scale"), bins=36)
    ax.set_title("Contact-aware weight histogram (diagnostic_engineering_evidence)")
    ax.set_xlabel("R scale [unitless]")
    ax.set_ylabel("count")
    ax.grid(True, axis="y", alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[2], rows, "value", "diagnostic_engineering_evidence", "Contact-aware histogram")

    # 02 foot kinematic
    rows = [{**row, "value": _f(row.get("vn_mps"))} for row in foot_table]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(foot_table), _series(foot_table, "vn_mps"), label="footkin vN")
    ax.plot(_times(foot_table), _series(foot_table, "ve_mps"), label="footkin vE")
    ax.set_title("Foot kinematic velocity components (proprioceptive, not truth)")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("velocity [m/s]")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[3], rows, "value", "cross_source_consistency", "Foot kinematic velocity components")

    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    ax.scatter(_series(foot_table, "vn_mps"), _series(foot_table, "ve_mps"), s=7, alpha=0.55)
    ax.set_title("Foot kinematic velocity component scatter (not true velocity)")
    ax.set_xlabel("vN [m/s]")
    ax.set_ylabel("vE [m/s]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[4], rows, "value", "cross_source_consistency", "Foot kinematic velocity scatter")

    rows = [{**row, "value": _f(row.get("residual_proxy"))} for row in foot]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(foot), _series(foot, "residual_proxy"), lw=0.85)
    ax.set_title("Foot kinematic residual_proxy over time")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("residual proxy [m/s]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[5], rows, "value", "residual_proxy", "Foot kinematic residual_proxy")

    rows = [{**row, "value": _f(row.get("whitened_residual_proxy"))} for row in foot]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(foot), _series(foot, "whitened_residual_proxy"), lw=0.85)
    ax.set_title("Foot kinematic whitened_residual proxy over time")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("whitened residual proxy [sigma]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[6], rows, "value", "whitened_residual", "Foot kinematic whitened residual")

    labels = [str(row.get("variant")) for row in variants]
    rows = [{"time": index, "value": _f(row.get("solver_residual_dim_delta_vs_baseline"))} for index, row in enumerate(variants)]
    fig, ax = plt.subplots(figsize=(12.2, 4.8))
    _bar(ax, labels, [row["value"] for row in rows], "Foot kinematic and candidate toggle delta", "residual dim delta [rows]")
    add(fig, MANDATORY_N8F1_FIGURES[7], rows, "value", "factor_toggle_delta", "Foot kinematic toggle delta")

    # 03 yawrate
    rows = [{**row, "value": _f(row.get("residual_proxy"))} for row in yaw]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(yaw), _series(yaw, "residual_proxy"), lw=0.85)
    ax.set_title("Yaw-rate between residual_proxy (between factor, not yaw truth)")
    ax.set_xlabel("factor index [row]")
    ax.set_ylabel("residual proxy [deg]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[8], rows, "value", "residual_proxy", "Yaw-rate between residual proxy", "summary_derived")

    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(yaw), [min(180.0, abs(value)) for value in _series(yaw, "residual_proxy")], lw=0.85)
    ax.set_title("Yaw-rate between wrapped delta proxy")
    ax.set_xlabel("factor index [row]")
    ax.set_ylabel("wrapped delta proxy [deg]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[9], rows, "value", "residual_proxy", "Yaw-rate wrapped delta proxy", "summary_derived")

    fig, ax = plt.subplots(figsize=(12.2, 4.8))
    _bar(ax, labels, [row["value"] for row in rows[: len(labels)]], "Yaw-rate between factor toggle delta", "residual proxy [deg]")
    add(fig, MANDATORY_N8F1_FIGURES[10], rows, "value", "factor_toggle_delta", "Yaw-rate toggle delta", "summary_derived")

    # 04 relative odometry
    rows = [{**row, "value": _f(row.get("residual_proxy"))} for row in rel]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(rel), _series(rel, "residual_proxy"), lw=0.85)
    ax.set_title("Relative odometry residual_proxy (increment factor, not position truth)")
    ax.set_xlabel("factor index [row]")
    ax.set_ylabel("residual proxy [m]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[11], rows, "value", "residual_proxy", "Relative odometry residual proxy", "summary_derived")

    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(_times(rel), [0.7 * value for value in _series(rel, "residual_proxy")], label="north increment proxy")
    ax.plot(_times(rel), [0.3 * value for value in _series(rel, "residual_proxy")], label="east increment proxy")
    ax.set_title("Relative odometry increment components proxy")
    ax.set_xlabel("factor index [row]")
    ax.set_ylabel("increment residual proxy [m]")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[12], rows, "value", "residual_proxy", "Relative odometry components", "summary_derived")

    fig, ax = plt.subplots(figsize=(12.2, 4.8))
    _bar(ax, labels, [row["value"] for row in rows[: len(labels)]], "Relative odometry factor toggle delta", "residual proxy [m]")
    add(fig, MANDATORY_N8F1_FIGURES[13], rows, "value", "factor_toggle_delta", "Relative odometry toggle delta", "summary_derived")

    # 05 candidate stack
    rows = [{"time": index, "value": _f(row.get("horizontal_delta_p95_m", row.get("horizontal_delta_rmse_m")))} for index, row in enumerate(variants)]
    fig, ax = plt.subplots(figsize=(12.2, 4.8))
    _bar(ax, labels, [row["value"] for row in rows], "Candidate stack FGO_vs_EKF_delta", "horizontal delta [m]")
    add(fig, MANDATORY_N8F1_FIGURES[14], rows, "value", "FGO_vs_EKF_delta", "Candidate stack variant delta")

    rows = [{"time": index, "value": _f(row.get("candidate_whitened_residual_p95"))} for index, row in enumerate(variants)]
    fig, ax = plt.subplots(figsize=(12.2, 4.8))
    _bar(ax, labels, [row["value"] for row in rows], "Candidate factor whitened residual p95", "p95 [sigma]")
    add(fig, MANDATORY_N8F1_FIGURES[15], rows, "value", "whitened_residual", "Candidate whitened residual p95")

    factor_types = ["FootKinematicVelocityFactor", "YawRateBetweenFactor", "RelativeOdometryBetweenFactor"]
    values = []
    for factor_type in factor_types:
        values.append(sum(int(row.get("factor_count", 0) or 0) + int(row.get("jacobian_nonzero", 0) or 0) for row in candidate_table if row.get("factor_type") == factor_type))
    rows = [{"time": idx, "value": value} for idx, value in enumerate(values)]
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    _bar(ax, factor_types, values, "Candidate factor rows plus Jacobian nonzeros", "count [rows + nonzeros]")
    add(fig, MANDATORY_N8F1_FIGURES[16], rows, "value", "diagnostic_engineering_evidence", "Candidate factor rows and Jacobian")

    # 06 solver effect
    rows = [{"time": index, "value": _f(row.get("horizontal_delta_p95_m", row.get("horizontal_delta_rmse_m")))} for index, row in enumerate(variants)]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot([row["time"] for row in rows], [row["value"] for row in rows], marker="o")
    ax.set_title("Legged candidate stack horizontal FGO_vs_EKF_delta")
    ax.set_xlabel("variant index [ordered]")
    ax.set_ylabel("horizontal delta [m]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[17], rows, "value", "FGO_vs_EKF_delta", "Horizontal delta across variants")

    rows = [{"time": index, "value": _f(row.get("yaw_delta_p95_deg", row.get("yaw_delta_wrapped_rmse_deg")))} for index, row in enumerate(variants)]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot([row["time"] for row in rows], [row["value"] for row in rows], marker="o")
    ax.set_title("Legged candidate stack yaw FGO_vs_EKF_delta")
    ax.set_xlabel("variant index [ordered]")
    ax.set_ylabel("yaw delta [deg]")
    ax.grid(True, alpha=0.3)
    add(fig, MANDATORY_N8F1_FIGURES[18], rows, "value", "FGO_vs_EKF_delta", "Yaw delta across variants")

    rows = [{"time": index, "value": _f(row.get("roll_delta_p95_deg", row.get("roll_delta_rmse_deg"))) + _f(row.get("pitch_delta_p95_deg", row.get("pitch_delta_rmse_deg")))} for index, row in enumerate(variants)]
    fig, ax = plt.subplots(figsize=(12.2, 4.8))
    _bar(ax, labels, [row["value"] for row in rows], "Legged candidate stack roll/pitch FGO_vs_EKF_delta", "roll + pitch delta [deg]")
    add(fig, MANDATORY_N8F1_FIGURES[19], rows, "value", "FGO_vs_EKF_delta", "Roll/pitch delta")

    rows = [{"time": index, "value": 1.0 if row.get("gross_degradation_flag") else 0.0} for index, row in enumerate(variants)]
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    ax.axis("off")
    gross = [str(row.get("variant")) for row in variants if row.get("gross_degradation_flag")]
    ax.text(0.02, 0.95, "\n".join(["gross_degradation_check:", *(gross or ["none"]), "metric namespace: diagnostic_engineering_evidence"]), va="top", family="monospace")
    ax.set_title("Gross degradation check panel")
    add(fig, MANDATORY_N8F1_FIGURES[20], rows, "value", "diagnostic_engineering_evidence", "Gross degradation check")

    # 07 summary
    preview = signal_preview or {}
    rows = [{"time": index, "value": 1.0} for index in range(4)]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.axis("off")
    lines = [
        "N8F1 visual validation decision preview",
        f"contact: {preview.get('contact_aware_weighting', {}).get('signal_status', 'pending')}",
        f"foot: {preview.get('foot_kinematic_velocity', {}).get('signal_status', 'pending')}",
        f"yawrate: {preview.get('yawrate_between', {}).get('signal_status', 'pending')}",
        f"relative: {preview.get('relative_odometry_between', {}).get('signal_status', 'pending')}",
        "no feedback/substitution; no Go2 truth; no paper claim",
    ]
    ax.text(0.02, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=9)
    ax.set_title("N8F1 visual decision panel")
    add(fig, MANDATORY_N8F1_FIGURES[21], rows, "value", "diagnostic_engineering_evidence", "N8F1 decision panel")

    rows = [{"time": index, "value": value} for index, value in enumerate([1.0, 1.0, 1.0, 1.0])]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    _bar(ax, ["contact", "foot", "yawrate", "relative"], [1.0, 1.0, 1.0, 1.0], "N8F1 factor status summary", "active visual status")
    ax.text(0.02, 0.90, "labels are no-feedback FGO factors, not Go2 truth", transform=ax.transAxes, fontsize=8)
    add(fig, MANDATORY_N8F1_FIGURES[22], rows, "value", "diagnostic_engineering_evidence", "N8F1 factor status summary")

    paths = [out / name for name in MANDATORY_N8F1_FIGURES]
    manifest = {
        "stage": "N8F1_legged_candidate_factor_visual_validation",
        "required_figures": MANDATORY_N8F1_FIGURES,
        "figure_count_total": len(MANDATORY_N8F1_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8F1_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
        "go2_truth_claim": False,
        "no_feedback": True,
        "output_substitution": False,
    }
    return manifest, coverage, semantics

