"""Generate runtime-only N7B2 contact-threshold review figures.

中文说明：N7B2 figures 只用于人工诊断；不提交到 Git，也不构成 performance claim。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURES = [
    "01_distribution/foot_force_hist_by_foot.png",
    "01_distribution/foot_force_time_with_v1_v2_thresholds.png",
    "01_distribution/foot_speed_norm_time.png",
    "01_distribution/foot_force_vs_foot_speed_scatter.png",
    "02_contact_v2/contact_state_v1_vs_v2_timeline.png",
    "02_contact_v2/per_foot_contact_v2_timeline.png",
    "02_contact_v2/contact_uncertain_ratio_before_after.png",
    "03_velocity_segments/velocity_diff_by_contact_state.png",
    "03_velocity_segments/go2_vs_receiver_velocity_by_contact_state.png",
    "03_velocity_segments/go2_vs_raw_doppler_velocity_by_contact_state.png",
    "04_summary/n7b2_decision_panel.png",
]


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _axis(plt, figsize: tuple[float, float] = (8.8, 4.8)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _sample(rows: list[dict[str, Any]], max_points: int = 5000) -> list[dict[str, Any]]:
    if len(rows) <= max_points:
        return rows
    step = max(1, len(rows) // max_points)
    return rows[::step][:max_points]


def _save_line(plt, path: Path, series: list[tuple[str, list[float], list[float]]], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for label, xs, ys in series:
        ax.plot(xs[: len(ys)], ys, linewidth=0.9, label=label)
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if series:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_hist(plt, path: Path, groups: list[tuple[str, list[float]]], title: str, xlabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for label, values in groups:
        ax.hist([value for value in values if math.isfinite(value)], bins=36, alpha=0.45, label=label)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_scatter(plt, path: Path, x: list[float], y: list[float], title: str, xlabel: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.scatter(x, y, s=8, alpha=0.55)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar(plt, path: Path, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(9.6, 4.8))
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=24, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_text_panel(plt, path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(8.8, 5.2))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.02, 0.92, "\n".join(lines), va="top", ha="left", fontsize=10, family="monospace")
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _times(rows: list[dict[str, Any]]) -> list[float]:
    return [_f(row.get("time"), 0.0) for row in rows]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [_f(row.get(key), 0.0) for row in rows]


def _label_values(rows: list[dict[str, Any]], key: str) -> tuple[list[str], list[float]]:
    labels = sorted({str(row.get(key, "unknown")) for row in rows}) or ["unknown"]
    mapping = {label: float(index) for index, label in enumerate(labels)}
    return labels, [mapping[str(row.get(key, "unknown"))] for row in rows]


def _threshold_line(rows: list[dict[str, Any]], threshold: float) -> list[float]:
    return [threshold for _ in rows]


def _threshold_mean(threshold_report: dict[str, Any]) -> float:
    candidate = threshold_report.get("candidate_thresholds", {}).get(threshold_report.get("recommended_candidate", ""), {})
    values = candidate.get("force_threshold_by_foot", {})
    finite = [float(value) for value in values.values() if isinstance(value, (int, float))]
    return sum(finite) / len(finite) if finite else 0.0


def generate_n7b2_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    go2_rows: list[dict[str, Any]],
    contact_v1_rows: list[dict[str, Any]],
    contact_v2_rows: list[dict[str, Any]],
    threshold_report: dict[str, Any],
    smoothing_report: dict[str, Any],
    velocity_segment_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    plt = _load_matplotlib()
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    for folder in ["01_distribution", "02_contact_v2", "03_velocity_segments", "04_summary", "05_case_review"]:
        (figs / folder).mkdir(parents=True, exist_ok=True)

    go2_plot = _sample(go2_rows)
    v1_plot = _sample(contact_v1_rows)
    v2_plot = _sample(contact_v2_rows)
    time = _times(v2_plot)
    threshold = _threshold_mean(threshold_report)
    figure_writers: list[tuple[Path, Any]] = []
    force_groups = [(f"foot_{foot}", _values(go2_plot, f"foot_force_{foot}")) for foot in range(4)]
    figure_writers.append((figs / REQUIRED_FIGURES[0], lambda path: _save_hist(plt, path, force_groups, "Foot-force hist by foot", "force diagnostic unit")))
    figure_writers.append((figs / REQUIRED_FIGURES[1], lambda path: _save_line(
        plt,
        path,
        [(f"foot_{foot}", _times(go2_plot), _values(go2_plot, f"foot_force_{foot}")) for foot in range(4)]
        + [("v2_threshold_mean", _times(go2_plot), _threshold_line(go2_plot, threshold))],
        "Foot force with V2 threshold",
        "force diagnostic unit",
    )))
    figure_writers.append((figs / REQUIRED_FIGURES[2], lambda path: _save_line(
        plt,
        path,
        [(f"foot_{foot}", time, _values(v2_plot, f"foot_{foot}_speed_norm")) for foot in range(4)],
        "Foot-speed norm time",
        "m/s diagnostic",
    )))
    figure_writers.append((figs / REQUIRED_FIGURES[3], lambda path: _save_scatter(
        plt,
        path,
        _values(v2_plot, "foot_0_force") + _values(v2_plot, "foot_1_force") + _values(v2_plot, "foot_2_force") + _values(v2_plot, "foot_3_force"),
        _values(v2_plot, "foot_0_speed_norm") + _values(v2_plot, "foot_1_speed_norm") + _values(v2_plot, "foot_2_speed_norm") + _values(v2_plot, "foot_3_speed_norm"),
        "Foot force vs foot speed",
        "force diagnostic unit",
        "foot speed norm",
    )))
    v1_labels, v1_values = _label_values(v1_plot, "contact_label")
    v2_labels, v2_values = _label_values(v2_plot, "contact_label_v2")
    figure_writers.append((figs / REQUIRED_FIGURES[4], lambda path: _save_line(
        plt,
        path,
        [("v1 " + ",".join(v1_labels), _times(v1_plot), v1_values), ("v2 " + ",".join(v2_labels), time, v2_values)],
        "Contact-state v1 vs v2 timeline",
        "label index",
    )))
    figure_writers.append((figs / REQUIRED_FIGURES[5], lambda path: _save_line(
        plt,
        path,
        [(f"foot_{foot}", time, _values(v2_plot, f"foot_{foot}_contact_v2")) for foot in range(4)],
        "Per-foot contact V2 timeline",
        "contact bool",
    )))
    figure_writers.append((figs / REQUIRED_FIGURES[6], lambda path: _save_bar(
        plt,
        path,
        ["before", "after"],
        [float(smoothing_report.get("uncertain_ratio_before", 0.0) or 0.0), float(smoothing_report.get("uncertain_ratio_after", 0.0) or 0.0)],
        "Contact uncertain ratio before/after",
        "ratio",
    )))
    by_state = velocity_segment_report.get("velocity_consistency_by_contact_state", {})
    labels = list(by_state.keys()) or ["missing"]
    figure_writers.append((figs / REQUIRED_FIGURES[7], lambda path: _save_bar(
        plt,
        path,
        labels,
        [float((by_state.get(label, {}) or {}).get("velocity_diff_rmse_to_receiver") or 0.0) for label in labels],
        "Velocity diff by contact state",
        "RMSE to receiver",
    )))
    figure_writers.append((figs / REQUIRED_FIGURES[8], lambda path: _save_bar(
        plt,
        path,
        labels,
        [float((by_state.get(label, {}) or {}).get("go2_velocity_norm_mean") or 0.0) for label in labels],
        "Go2 vs receiver by contact state",
        "Go2 speed mean",
    )))
    figure_writers.append((figs / REQUIRED_FIGURES[9], lambda path: _save_bar(
        plt,
        path,
        labels,
        [float((by_state.get(label, {}) or {}).get("velocity_diff_rmse_to_raw_doppler") or 0.0) for label in labels],
        "Go2 vs raw Doppler by contact state",
        "RMSE to raw Doppler",
    )))
    figure_writers.append((figs / REQUIRED_FIGURES[10], lambda path: _save_text_panel(
        plt,
        path,
        "N7B2 decision",
        [
            f"status: {decision.get('status')}",
            f"next: {decision.get('recommended_next_stage')}",
            f"field_quality: {decision.get('field_quality_status')}",
            f"contact_quality: {decision.get('contact_quality_status')}",
            f"velocity_segments: {decision.get('velocity_segment_readiness_status')}",
            "paper_performance_claim: false",
            "go2_velocity_prior_enabled: false",
            "go2_yaw_prior_enabled: false",
            "fgo: false",
        ],
    )))

    figures = []
    for path, writer in figure_writers:
        writer(path)
        figures.append({"path": str(path), "relative_path": str(path.relative_to(figs)), "nonempty": path.exists() and path.stat().st_size > 0})
    manifest = {
        "stage": "N7B2_go2_contact_threshold_review",
        "required_figures": REQUIRED_FIGURES,
        "figure_count_total": len(figures),
        "required_figures_generated": len(figures) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(item["nonempty"] for item in figures),
        "figures": figures,
        "paper_performance_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }
    (out / "N7B2_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
