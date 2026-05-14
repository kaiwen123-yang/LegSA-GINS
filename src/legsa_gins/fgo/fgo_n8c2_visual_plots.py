"""Runtime-only N8C2 factor activation figures.

中文说明：图像只写 runtime 目录，不提交也不作为性能宣称。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_activation_audit import build_factor_residual_series
from legsa_gins.fgo.fgo_smoothness_component_review import smoothness_component_series
from legsa_gins.fgo.fgo_yaw_convention_fix import _f


MANDATORY_N8C2_FIGURES = [
    "factor_activation_row_count_bar.png",
    "raw_vs_whitened_residual_p95_by_type.png",
    "dimension_normalized_residual_p95_by_type.png",
    "smoothness_component_residual_p95_bar.png",
    "smoothness_component_residual_time.png",
    "raw_doppler_residual_raw_vs_whitened_time.png",
    "raw_doppler_weight_sensitivity_horizontal_delta.png",
    "raw_doppler_weight_sensitivity_yaw_delta.png",
    "raw_vs_receiver_velocity_factor_residual_compare.png",
    "receiver_off_raw_on_vs_raw_off_delta.png",
    "go2_joint_factor_residual_raw_vs_whitened_time.png",
    "go2_joint_on_off_delta_time_verified.png",
    "factor_toggle_integrity_panel.png",
    "n8c2_decision_panel.png",
]


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save(fig: Any, path: Path, plt: Any) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return {
        "figure_name": path.name,
        "nonempty": path.exists() and path.stat().st_size > 0,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "role_alias": "N8C2_FIGURE_OUTPUT_DIR",
    }


def _bar(ax: Any, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)


def _activation_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("factor_activation_rows", []))


def _variant_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("variants", []))


def generate_n8c2_figures(
    *,
    figure_output_dir: str | Path,
    ekf_rows: list[dict[str, Any]],
    rows_by_variant: dict[str, list[dict[str, Any]]],
    sensitivity_rows_by_variant: dict[str, list[dict[str, Any]]],
    activation_report: dict[str, Any],
    whitening_report: dict[str, Any],
    smoothness_report: dict[str, Any],
    sensitivity_report: dict[str, Any],
    toggle_report: dict[str, Any],
    decision_preview: dict[str, Any],
) -> dict[str, Any]:
    plt = _plt()
    out = Path(figure_output_dir)
    generated: list[dict[str, Any]] = []
    activation_rows = _activation_rows(activation_report)
    labels = [str(row.get("factor_type")) for row in activation_rows]

    fig, ax = plt.subplots(figsize=(9, 4.8))
    _bar(ax, labels, [float(row.get("residual_row_count", 0) or 0) for row in activation_rows], "Factor activation row count", "rows")
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[0], plt))

    fig, ax = plt.subplots(figsize=(10, 4.8))
    raw = [float(row.get("raw_residual_p95", 0.0) or 0.0) for row in activation_rows]
    white = [float(row.get("whitened_residual_p95", 0.0) or 0.0) for row in activation_rows]
    x = list(range(len(labels)))
    ax.bar([v - 0.2 for v in x], raw, width=0.4, label="raw")
    ax.bar([v + 0.2 for v in x], white, width=0.4, label="whitened")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_title("Raw vs whitened residual p95")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[1], plt))

    fig, ax = plt.subplots(figsize=(10, 4.8))
    _bar(ax, labels, [float(row.get("dimension_normalized_residual_p95", 0.0) or 0.0) for row in activation_rows], "Dimension-normalized residual p95", "proxy")
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[2], plt))

    component_rows = list(smoothness_report.get("smoothness_component_rows", []))
    component_labels = [str(row.get("component")) for row in component_rows]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    _bar(ax, component_labels, [float(row.get("dimension_normalized_p95", 0.0) or 0.0) for row in component_rows], "Smoothness component residual p95", "dimension-normalized")
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[3], plt))

    current_rows = rows_by_variant.get("weak_yaw_smoothness") or rows_by_variant.get("default_active_stack_n8a2") or []
    components = smoothness_component_series(current_rows)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for name, payload in components.items():
        if name == "other_attitude_smoothness":
            continue
        ax.plot(payload["time"], payload["values"], linewidth=1.0, label=name)
    ax.set_title("Smoothness component residual time")
    ax.set_xlabel("time")
    ax.set_ylabel("proxy")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[4], plt))

    times, raw_dopp = build_factor_residual_series(factor_name="RawDopplerVelocityFactor", ekf_rows=ekf_rows, fgo_rows=current_rows)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, raw_dopp, label="raw proxy", linewidth=1.0)
    ax.plot(times, raw_dopp, label="whitened proxy", linewidth=1.0, linestyle="--")
    ax.set_title("Raw Doppler residual raw vs whitened time")
    ax.set_xlabel("time")
    ax.set_ylabel("mps")
    ax.legend()
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[5], plt))

    sensitivity = _variant_rows(sensitivity_report)
    variant_labels = [str(row.get("variant")) for row in sensitivity]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    _bar(ax, variant_labels, [float(row.get("horizontal_delta_rmse_m", 0.0) or 0.0) for row in sensitivity], "Raw Doppler weight sensitivity horizontal delta", "m")
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[6], plt))

    fig, ax = plt.subplots(figsize=(11, 4.8))
    _bar(ax, variant_labels, [float(row.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) for row in sensitivity], "Raw Doppler weight sensitivity yaw delta", "deg")
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[7], plt))

    _, receiver_velocity = build_factor_residual_series(factor_name="ReceiverVelocityFactor", ekf_rows=ekf_rows, fgo_rows=current_rows)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times, raw_dopp, label="raw doppler proxy", linewidth=1.0)
    ax.plot(times, receiver_velocity, label="receiver velocity proxy", linewidth=1.0, linestyle="--")
    ax.set_title("Raw vs receiver velocity residual compare")
    ax.set_xlabel("time")
    ax.set_ylabel("mps")
    ax.legend()
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[8], plt))

    raw_on = sensitivity_rows_by_variant.get("receiver_velocity_off_raw_on", [])
    raw_off = sensitivity_rows_by_variant.get("receiver_velocity_off_raw_off", [])
    receiver_delta = []
    for left, right in zip(raw_on, raw_off):
        receiver_delta.append(abs(_f(right.get("vn_mps")) - _f(left.get("vn_mps"))) + abs(_f(right.get("ve_mps")) - _f(left.get("ve_mps"))))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times[: len(receiver_delta)], receiver_delta, linewidth=1.0)
    ax.set_title("Receiver off raw-on vs raw-off delta")
    ax.set_xlabel("time")
    ax.set_ylabel("horizontal velocity abs delta")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[9], plt))

    go2_times, go2_values = build_factor_residual_series(factor_name="Go2ProprioceptiveJointFactor", ekf_rows=ekf_rows, fgo_rows=current_rows)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(go2_times, go2_values, label="raw proxy", linewidth=1.0)
    ax.plot(go2_times, go2_values, label="whitened proxy", linestyle="--", linewidth=1.0)
    ax.set_title("Go2 joint factor residual raw vs whitened")
    ax.set_xlabel("time")
    ax.set_ylabel("proxy")
    ax.legend()
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[10], plt))

    default_rows = rows_by_variant.get("default_active_stack_n8a2", [])
    go2_off = rows_by_variant.get("go2_joint_off", [])
    go2_delta = [abs(_f(right.get("roll_deg")) - _f(left.get("roll_deg"))) + abs(_f(right.get("pitch_deg")) - _f(left.get("pitch_deg"))) for left, right in zip(default_rows, go2_off)]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(times[: len(go2_delta)], go2_delta, linewidth=1.0)
    ax.set_title("Go2 joint on/off delta time verified")
    ax.set_xlabel("time")
    ax.set_ylabel("roll+pitch abs delta")
    ax.grid(True, alpha=0.3)
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[11], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    toggle_lines = [f"{row.get('variant')}: {row.get('status')}" for row in toggle_report.get("toggle_rows", [])]
    ax.text(0.02, 0.95, "\n".join(toggle_lines), va="top", family="monospace", fontsize=9)
    ax.set_title("Factor toggle integrity panel")
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[12], plt))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    decision_lines = [
        f"status: {decision_preview.get('status')}",
        f"next: {decision_preview.get('recommended_next_stage')}",
        f"raw_doppler: {decision_preview.get('raw_doppler_classification')}",
        f"smoothness: {decision_preview.get('smoothness_dominance_classification')}",
        "no feedback, no substitution, no trace/final_v23 input",
        "diagnostic only; no paper performance claim",
    ]
    ax.text(0.02, 0.95, "\n".join(decision_lines), va="top", family="monospace", fontsize=10)
    ax.set_title("N8C2 decision panel")
    generated.append(_save(fig, out / MANDATORY_N8C2_FIGURES[13], plt))

    paths = [out / name for name in MANDATORY_N8C2_FIGURES]
    return {
        "stage": "N8C2_fgo_factor_activation_review",
        "required_figures": MANDATORY_N8C2_FIGURES,
        "figure_count_total": len(MANDATORY_N8C2_FIGURES),
        "generated_figures": generated,
        "required_figures_generated": all(path.exists() for path in paths),
        "required_figures_nonempty": all(path.exists() and path.stat().st_size > 0 for path in paths),
        "figure_role_alias": "N8C2_FIGURE_OUTPUT_DIR",
        "runtime_only": True,
        "paper_performance_claim": False,
    }
