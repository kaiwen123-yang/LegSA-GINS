"""Generate N7B4 diagnostic-only Go2 contact/velocity figures.

中文说明：图像只写入 runtime figure dir，不进入 Git，不作为 paper performance
evidence。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURES = [
    "contact_probability_by_foot_time.png",
    "contact_probability_heatmap.png",
    "contact_probability_vs_force_speed.png",
    "selected_contact_probability_timeline.png",
    "velocity_frame_combined_score_bar.png",
    "internal_vs_external_frame_score_scatter.png",
    "probability_weighted_prior_std_time.png",
    "diagnostic_update_count_bar.png",
    "diagnostic_metric_delta_bar.png",
    "n7b4_decision_panel.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _f(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _bar(path: Path, title: str, labels: list[str], values: list[float], ylabel: str = "") -> dict[str, Any]:
    plt = _load_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(9.0, 4.8))
    ax = fig.add_axes([0.16, 0.30, 0.78, 0.58])
    ax.bar(range(len(labels)), values, color="#4477aa")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=24, ha="right", fontsize=8)
    ax.set_title(title)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def _line(path: Path, title: str, series: list[tuple[str, list[float], list[float]]], ylabel: str = "") -> dict[str, Any]:
    plt = _load_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(9.0, 4.8))
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.72])
    for label, xs, ys in series:
        ax.plot(xs, ys, linewidth=0.9, label=label)
    ax.set_title(title)
    ax.set_xlabel("time (s)")
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if series:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def _scatter(path: Path, title: str, xs: list[float], ys: list[float], xlabel: str, ylabel: str) -> dict[str, Any]:
    plt = _load_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(7.0, 5.0))
    ax = fig.add_axes([0.14, 0.14, 0.80, 0.74])
    ax.scatter(xs, ys, s=28, alpha=0.8, color="#228833")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def generate_n7b4_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    feature_rows: list[dict[str, Any]],
    probability_rows: list[dict[str, Any]],
    probability_report: dict[str, Any],
    frame_score_report: dict[str, Any],
    prior_build_report: dict[str, Any],
    activation_report: dict[str, Any],
    variant_summaries: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    generated: list[dict[str, Any]] = []
    selected_model = str(probability_report.get("selected_contact_probability_model") or "")
    selected_rows = [row for row in probability_rows if row.get("model_id") == selected_model][:5000]
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[0],
            "Contact probability by foot",
            [
                (f"foot_{foot}", [_f(row.get("time")) for row in selected_rows], [_f(row.get(f"foot_{foot}_contact_probability")) for row in selected_rows])
                for foot in range(4)
            ],
            "probability",
        )
    )
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[1],
            "Contact probability heatmap proxy",
            [
                ("support", [_f(row.get("time")) for row in selected_rows], [_f(row.get("support_probability")) for row in selected_rows]),
                ("uncertainty", [_f(row.get("time")) for row in selected_rows], [_f(row.get("uncertainty_probability")) for row in selected_rows]),
            ],
            "probability",
        )
    )
    force = [_f(row.get("normalized_foot_force")) for row in feature_rows[:6000]]
    speed = [_f(row.get("normalized_inverse_foot_speed")) for row in feature_rows[:6000]]
    generated.append(_scatter(figs / REQUIRED_FIGURES[2], "Contact probability inputs", force, speed, "normalized force", "inverse speed hint"))
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[3],
            "Selected contact probability timeline",
            [
                ("support", [_f(row.get("time")) for row in selected_rows], [_f(row.get("support_probability")) for row in selected_rows]),
                ("confidence", [_f(row.get("time")) for row in selected_rows], [_f(row.get("confidence_score")) for row in selected_rows]),
            ],
            "probability",
        )
    )
    candidates = frame_score_report.get("candidates", {})
    labels = list(candidates.keys())
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[4],
            "Velocity frame combined score",
            labels,
            [_f(candidates[label].get("combined_score")) for label in labels],
            "lower is better",
        )
    )
    generated.append(
        _scatter(
            figs / REQUIRED_FIGURES[5],
            "Internal vs external frame score",
            [_f(candidates[label].get("internal_score")) for label in labels],
            [_f(candidates[label].get("external_score")) for label in labels],
            "internal",
            "external",
        )
    )
    prior_rows = _read_csv(out / "GO2_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv")
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[6],
            "Probability-weighted prior std",
            [("std_vn", [_f(row.get("time")) for row in prior_rows[:5000]], [_f(row.get("std_vn")) for row in prior_rows[:5000]])],
            "m/s",
        )
    )
    variants = variant_summaries.get("variants", [])
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[7],
            "Diagnostic update counts",
            [str(row.get("variant_id")) for row in variants],
            [_f(row.get("go2_velocity_prior_update_count")) for row in variants],
            "updates",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[8],
            "Diagnostic state delta",
            [str(row.get("variant_id")) for row in variants],
            [_f(row.get("state_delta_summary", {}).get("velocity_delta_p95_mps")) for row in variants],
            "m/s",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[9],
            "N7B4 decision panel",
            ["contact_ready", "frame_testable", "prior_rows", "stable_updates", "no_claim"],
            [
                1.0 if probability_report.get("contact_probability_model_ready") else 0.0,
                1.0 if frame_score_report.get("frame_status") in {"resolved_for_diagnostic", "ambiguous_but_testable"} else 0.0,
                min(1.0, _f(prior_build_report.get("epoch_count")) / 100.0),
                1.0 if activation_report.get("stable_with_updates") else 0.0,
                1.0 if not decision.get("paper_performance_claim", True) else 0.0,
            ],
            "boolean/proxy",
        )
    )
    manifest = {
        "stage": "N7B4_literature_informed_contact_velocity",
        "required_figures": REQUIRED_FIGURES,
        "generated": generated,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(item.get("nonempty") for item in generated),
        "diagnostic_only": True,
        "paper_performance_claim": False,
    }
    (out / "N7B4_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
