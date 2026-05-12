"""Generate runtime-only N7B Go2 readiness figures.

中文说明：figures 写到 runtime-only 目录，不提交到 Git，也不构成 paper claim。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURES = [
    "01_contact_state/foot_force_time.png",
    "01_contact_state/per_foot_contact_state_time.png",
    "01_contact_state/contact_state_timeline.png",
    "01_contact_state/foot_speed_norm_time.png",
    "02_velocity_quality/go2_velocity_time.png",
    "02_velocity_quality/go2_vs_receiver_velocity_norm.png",
    "02_velocity_quality/go2_vs_raw_doppler_velocity_norm.png",
    "02_velocity_quality/contact_conditioned_velocity_box.png",
    "03_motion_state/motion_state_timeline.png",
    "04_yaw_rate/yaw_speed_time.png",
    "04_yaw_rate/yaw_speed_vs_go2_yaw_derivative.png",
    "05_summary/n7b_decision_panel.png",
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


def _save_scatter(plt, path: Path, x: list[float], y: list[float], title: str, xlabel: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.scatter(x, y, s=8, alpha=0.65)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar(plt, path: Path, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(9.8, 4.8))
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=24, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_box(plt, path: Path, groups: dict[str, list[float]], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(9.8, 4.8))
    labels = list(groups.keys()) or ["missing"]
    values = [[value for value in groups.get(label, []) if math.isfinite(value)] or [0.0] for label in labels]
    ax.boxplot(values, labels=labels, showfliers=False)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=24)
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


def _categorical_values(rows: list[dict[str, Any]], key: str) -> tuple[list[str], list[float]]:
    labels = sorted({str(row.get(key, "unknown")) for row in rows}) or ["unknown"]
    mapping = {label: float(index) for index, label in enumerate(labels)}
    return labels, [mapping[str(row.get(key, "unknown"))] for row in rows]


def _sample_rows(rows: list[dict[str, Any]], max_points: int = 5000) -> list[dict[str, Any]]:
    if len(rows) <= max_points:
        return rows
    step = max(1, len(rows) // max_points)
    return rows[::step][:max_points]


def generate_n7b_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    contact_rows: list[dict[str, Any]],
    velocity_rows: list[dict[str, Any]],
    motion_rows: list[dict[str, Any]],
    yaw_rows: list[dict[str, Any]],
    reports: dict[str, dict[str, Any]],
    decision: dict[str, Any],
) -> dict[str, Any]:
    plt = _load_matplotlib()
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    for folder in ["01_contact_state", "02_velocity_quality", "03_motion_state", "04_yaw_rate", "05_summary", "06_case_review"]:
        (figs / folder).mkdir(parents=True, exist_ok=True)

    generated: list[dict[str, Any]] = []
    contact_plot_rows = _sample_rows(contact_rows)
    velocity_plot_rows = _sample_rows(velocity_rows)
    motion_plot_rows = _sample_rows(motion_rows)
    yaw_plot_rows = _sample_rows(yaw_rows)
    contact_time = _times(contact_plot_rows)
    generated.append((figs / REQUIRED_FIGURES[0], lambda path: _save_line(
        plt,
        path,
        [(f"foot_{foot}", contact_time, _values(contact_plot_rows, f"foot_{foot}_force")) for foot in range(4)],
        "Go2 foot-force time",
        "force diagnostic unit",
    )))
    generated.append((figs / REQUIRED_FIGURES[1], lambda path: _save_line(
        plt,
        path,
        [(f"foot_{foot}", contact_time, _values(contact_plot_rows, f"foot_{foot}_contact")) for foot in range(4)],
        "Per-foot contact state",
        "contact bool",
    )))
    contact_labels, contact_values = _categorical_values(contact_plot_rows, "contact_label")
    generated.append((figs / REQUIRED_FIGURES[2], lambda path: _save_line(
        plt,
        path,
        [("contact_label", contact_time, contact_values)],
        "Contact-state timeline: " + ", ".join(contact_labels),
        "label index",
    )))
    generated.append((figs / REQUIRED_FIGURES[3], lambda path: _save_line(
        plt,
        path,
        [(f"foot_{foot}", contact_time, _values(contact_plot_rows, f"foot_{foot}_speed_norm")) for foot in range(4)],
        "Go2 foot-speed norm time",
        "m/s diagnostic",
    )))
    velocity_time = _times(velocity_plot_rows)
    generated.append((figs / REQUIRED_FIGURES[4], lambda path: _save_line(
        plt,
        path,
        [
            ("go2_v0", velocity_time, _values(velocity_plot_rows, "go2_v0")),
            ("go2_v1", velocity_time, _values(velocity_plot_rows, "go2_v1")),
            ("go2_v2", velocity_time, _values(velocity_plot_rows, "go2_v2")),
        ],
        "Go2 velocity components",
        "m/s",
    )))
    generated.append((figs / REQUIRED_FIGURES[5], lambda path: _save_scatter(
        plt,
        path,
        _values(velocity_plot_rows, "receiver_speed_norm"),
        _values(velocity_plot_rows, "go2_speed_norm"),
        "Go2 vs receiver velocity norm",
        "receiver-native velocity norm",
        "Go2 velocity norm",
    )))
    generated.append((figs / REQUIRED_FIGURES[6], lambda path: _save_scatter(
        plt,
        path,
        _values(velocity_plot_rows, "raw_speed_norm"),
        _values(velocity_plot_rows, "go2_speed_norm"),
        "Go2 vs raw Doppler velocity norm",
        "raw Doppler velocity norm",
        "Go2 velocity norm",
    )))
    groups: dict[str, list[float]] = {}
    for row in velocity_plot_rows:
        groups.setdefault(str(row.get("contact_label", "unknown")), []).append(_f(row.get("go2_speed_norm")))
    generated.append((figs / REQUIRED_FIGURES[7], lambda path: _save_box(
        plt,
        path,
        groups,
        "Contact-conditioned Go2 velocity",
        "Go2 speed norm",
    )))
    motion_labels, motion_values = _categorical_values(motion_plot_rows, "motion_state")
    generated.append((figs / REQUIRED_FIGURES[8], lambda path: _save_line(
        plt,
        path,
        [("motion_state", _times(motion_plot_rows), motion_values)],
        "Motion-state timeline: " + ", ".join(motion_labels),
        "label index",
    )))
    generated.append((figs / REQUIRED_FIGURES[9], lambda path: _save_line(
        plt,
        path,
        [("yaw_speed", _times(yaw_plot_rows), _values(yaw_plot_rows, "go2_yaw_speed_radps"))],
        "Go2 yaw-speed time",
        "rad/s",
    )))
    generated.append((figs / REQUIRED_FIGURES[10], lambda path: _save_scatter(
        plt,
        path,
        _values(yaw_plot_rows, "go2_yaw_derivative_radps"),
        _values(yaw_plot_rows, "go2_yaw_speed_radps"),
        "Go2 yaw-speed vs yaw derivative",
        "d(yaw)/dt rad/s",
        "yaw_speed rad/s",
    )))
    generated.append((figs / REQUIRED_FIGURES[11], lambda path: _save_text_panel(
        plt,
        path,
        "N7B decision",
        [
            f"status: {decision.get('status')}",
            f"next: {decision.get('recommended_next_stage')}",
            f"contact: {reports.get('contact', {}).get('recommended_contact_quality_status')}",
            f"velocity: {reports.get('velocity', {}).get('consistency_status')}",
            f"yaw_rate: {reports.get('yaw', {}).get('consistency_status')}",
            "paper_performance_claim: false",
            "go2_velocity_prior_enabled: false",
            "go2_yaw_prior_enabled: false",
            "fgo: false",
        ],
    )))

    figure_rows: list[dict[str, Any]] = []
    for path, writer in generated:
        writer(path)
        figure_rows.append({"path": str(path), "relative_path": str(path.relative_to(figs)), "nonempty": path.exists() and path.stat().st_size > 0})
    manifest = {
        "stage": "N7B_go2_velocity_contact_readiness",
        "required_figures": REQUIRED_FIGURES,
        "figure_count_total": len(figure_rows),
        "required_figures_generated": len(figure_rows) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(row["nonempty"] for row in figure_rows),
        "figures": figure_rows,
        "paper_performance_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }
    (out / "N7B_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
