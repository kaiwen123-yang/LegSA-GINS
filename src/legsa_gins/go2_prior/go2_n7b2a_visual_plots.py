"""Generate runtime-only N7B2A visual sanity figures.

中文说明：图像仅写入运行目录用于人工审查，禁止作为 tracked artifact 提交。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURES = [
    "01_attitude_std_policy/go2_attitude_std_policy_context.png",
    "02_metric_namespace/n7a_parity_vs_absolute_metric_namespace_panel.png",
    "03_contact_physical_sanity/contact_v2_all_feet_contact_timeline.png",
    "03_contact_physical_sanity/per_foot_contact_ratio_bar.png",
    "03_contact_physical_sanity/contact_v2_vs_foot_speed_timeline.png",
    "03_contact_physical_sanity/foot_force_vs_foot_speed_contact_colored.png",
    "03_contact_physical_sanity/contact_alternating_pattern_heatmap.png",
    "04_summary/contact_physical_sanity_panel.png",
    "04_summary/n7b2a_decision_panel.png",
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


def _save_text_panel(plt, path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(9.2, 5.2))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.02, 0.92, "\n".join(lines), va="top", ha="left", fontsize=9.5, family="monospace")
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar(plt, path: Path, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.bar(range(len(labels)), values)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_line(plt, path: Path, series: list[tuple[str, list[float], list[float]]], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for label, xs, ys in series:
        ax.plot(xs[: len(ys)], ys, linewidth=0.85, label=label)
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if series:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _times(rows: list[dict[str, Any]]) -> list[float]:
    values = [_f(row.get("time"), 0.0) for row in rows]
    if not values:
        return []
    start = values[0]
    return [value - start for value in values]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [_f(row.get(key), 0.0) for row in rows]


def _save_scatter(plt, path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    xs: list[float] = []
    ys: list[float] = []
    colors: list[float] = []
    for row in rows:
        for foot in range(4):
            xs.append(_f(row.get(f"foot_{foot}_force"), 0.0))
            ys.append(_f(row.get(f"foot_{foot}_speed_norm"), 0.0))
            colors.append(_f(row.get(f"foot_{foot}_contact_v2"), 0.0))
    ax.scatter(xs, ys, c=colors, cmap="viridis", s=7, alpha=0.55)
    ax.set_title("Foot force vs foot speed, colored by contact")
    ax.set_xlabel("force diagnostic unit")
    ax.set_ylabel("foot speed norm")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_heatmap(plt, path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = _sample(rows, max_points=1000)
    matrix = [[_f(row.get(f"foot_{foot}_contact_v2"), 0.0) for row in sample] for foot in range(4)]
    fig, ax = _axis(plt, figsize=(9.0, 3.8))
    ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="Greys", vmin=0.0, vmax=1.0)
    ax.set_yticks(range(4))
    ax.set_yticklabels([f"foot{foot}" for foot in range(4)])
    ax.set_title("Contact alternating pattern heatmap")
    ax.set_xlabel("sample index")
    fig.savefig(path, dpi=140)
    plt.close(fig)


def generate_n7b2a_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    contact_v2_rows: list[dict[str, Any]],
    attitude_std_report: dict[str, Any],
    metric_namespace_report: dict[str, Any],
    contact_physical_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    plt = _load_matplotlib()
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    for folder in [
        "01_attitude_std_policy",
        "02_metric_namespace",
        "03_contact_physical_sanity",
        "04_summary",
        "05_case_review",
    ]:
        (figs / folder).mkdir(parents=True, exist_ok=True)
    rows = _sample(contact_v2_rows)
    generated: list[dict[str, Any]] = []

    writers = [
        (
            figs / REQUIRED_FIGURES[0],
            lambda path: _save_text_panel(
                plt,
                path,
                "Go2 attitude std policy",
                [
                    f"current_std_deg: {attitude_std_report.get('current_roll_pitch_std_deg')}",
                    "measurement_std: true",
                    "gate_or_threshold: false",
                    "absolute_truth_available: false",
                    "future_screen: 1.0, 1.6, 3.0, 5.0",
                ],
            ),
        ),
        (
            figs / REQUIRED_FIGURES[1],
            lambda path: _save_text_panel(
                plt,
                path,
                "Metric namespace guard",
                [
                    f"metric_namespace_missing: {metric_namespace_report.get('metric_namespace_missing')}",
                    "N7A roll/pitch deltas: parity_to_final_v23",
                    "final_v23 abs roll/pitch context: not claim",
                    "Go2 velocity comparison: cross_source_consistency",
                    "paper_performance_claim: false",
                ],
            ),
        ),
        (
            figs / REQUIRED_FIGURES[2],
            lambda path: _save_line(
                plt,
                path,
                [("all_feet_contact", _times(rows), [1.0 if int(_f(row.get("contact_count_v2"), 0.0)) == 4 else 0.0 for row in rows])],
                "Contact V2 all-feet contact timeline",
                "all feet contact",
            ),
        ),
        (
            figs / REQUIRED_FIGURES[3],
            lambda path: _save_bar(
                plt,
                path,
                list((contact_physical_report.get("per_foot_contact_ratios") or {}).keys()),
                [float(value or 0.0) for value in (contact_physical_report.get("per_foot_contact_ratios") or {}).values()],
                "Per-foot contact ratio",
                "ratio",
            ),
        ),
        (
            figs / REQUIRED_FIGURES[4],
            lambda path: _save_line(
                plt,
                path,
                [(f"foot{foot}_speed", _times(rows), _values(rows, f"foot_{foot}_speed_norm")) for foot in range(4)]
                + [("contact_count", _times(rows), _values(rows, "contact_count_v2"))],
                "Contact V2 vs foot speed timeline",
                "speed / contact count",
            ),
        ),
        (figs / REQUIRED_FIGURES[5], lambda path: _save_scatter(plt, path, rows)),
        (figs / REQUIRED_FIGURES[6], lambda path: _save_heatmap(plt, path, contact_v2_rows)),
        (
            figs / REQUIRED_FIGURES[7],
            lambda path: _save_text_panel(
                plt,
                path,
                "Contact physical sanity",
                [
                    f"all_contact_suspect: {contact_physical_report.get('all_contact_suspect')}",
                    f"contact_too_permissive: {contact_physical_report.get('contact_too_permissive')}",
                    f"alternating_ratio: {contact_physical_report.get('alternating_contact_ratio')}",
                    f"speed_p50_p95: {(contact_physical_report.get('foot_speed_during_contact') or {}).get('p50')} / {(contact_physical_report.get('foot_speed_during_contact') or {}).get('p95')}",
                    f"status: {contact_physical_report.get('physical_plausibility_status')}",
                ],
            ),
        ),
        (
            figs / REQUIRED_FIGURES[8],
            lambda path: _save_text_panel(
                plt,
                path,
                "N7B2A decision",
                [
                    f"status: {decision.get('status')}",
                    f"next: {decision.get('recommended_next_stage')}",
                    "go2_velocity_prior_enabled: false",
                    "go2_yaw_prior_enabled: false",
                    "fgo: false",
                    "paper_performance_claim: false",
                ],
            ),
        ),
    ]
    for path, writer in writers:
        writer(path)
        generated.append({"path": str(path), "relative_path": str(path.relative_to(figs)), "nonempty": path.exists() and path.stat().st_size > 0})
    manifest = {
        "stage": "N7B2A_go2_metric_contact_visual_audit",
        "required_figures": REQUIRED_FIGURES,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(item["nonempty"] for item in generated),
        "figures": generated,
        "paper_performance_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }
    (out / "N7B2A_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
