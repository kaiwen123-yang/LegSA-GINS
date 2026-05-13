"""Generate N7B5 diagnostic-only horizontal velocity figures.

中文说明：图像只写入 runtime figure dir，不进入 Git；图中 metric 仅为
diagnostic state delta / frame consistency，不是 truth error 或 paper performance。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURES = [
    "top_frame_horizontal_difference_time.png",
    "top_frame_vertical_difference_time.png",
    "frame_equivalence_by_segment.png",
    "horizontal_prior_std_time.png",
    "horizontal_prior_update_timeline.png",
    "frame_sensitivity_metric_delta_bar.png",
    "horizontal_only_error_curves.png",
    "n7b5_decision_panel.png",
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


def generate_n7b5_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    frame_equivalence_timeseries: list[dict[str, Any]],
    frame_equivalence_report: dict[str, Any],
    prior_build_report: dict[str, Any],
    activation_report: dict[str, Any],
    variant_summaries: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    generated: list[dict[str, Any]] = []
    eq_rows = frame_equivalence_timeseries[:6000]
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[0],
            "Top-frame horizontal difference",
            [
                (
                    "horizontal_diff",
                    [_f(row.get("time")) for row in eq_rows],
                    [_f(row.get("horizontal_difference_mps")) for row in eq_rows],
                )
            ],
            "m/s",
        )
    )
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[1],
            "Top-frame vertical difference",
            [("vertical_diff", [_f(row.get("time")) for row in eq_rows], [_f(row.get("vertical_difference_mps")) for row in eq_rows])],
            "m/s",
        )
    )
    segments = frame_equivalence_report.get("per_segment_difference", {})
    labels = list(segments.keys())
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[2],
            "Frame equivalence by segment",
            labels,
            [_f(segments[label].get("horizontal_difference_rmse")) for label in labels],
            "horizontal RMSE m/s",
        )
    )
    prior_rows = _read_csv(out / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv")
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[3],
            "Horizontal prior std",
            [
                ("std_vn", [_f(row.get("time")) for row in prior_rows[:6000]], [_f(row.get("std_vn")) for row in prior_rows[:6000]]),
                ("std_ve", [_f(row.get("time")) for row in prior_rows[:6000]], [_f(row.get("std_ve")) for row in prior_rows[:6000]]),
            ],
            "m/s",
        )
    )
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[4],
            "Horizontal prior update timeline",
            [("active", [_f(row.get("time")) for row in prior_rows[:6000]], [1.0 for _ in prior_rows[:6000]])],
            "active row",
        )
    )
    variants = variant_summaries.get("variants", [])
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[5],
            "Frame sensitivity update counts",
            [str(row.get("variant_id")) for row in variants],
            [_f(row.get("go2_velocity_prior_update_count")) for row in variants],
            "updates",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[6],
            "Horizontal-only state delta",
            [str(row.get("variant_id")) for row in variants],
            [_f(row.get("state_delta_summary", {}).get("velocity_delta_p95_mps")) for row in variants],
            "state delta p95 m/s",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[7],
            "N7B5 decision panel",
            ["horizontal_equiv", "prior_rows", "stable_horizontal", "vertical_disabled", "no_claim"],
            [
                1.0 if frame_equivalence_report.get("frame_equivalent_for_horizontal_only") else 0.0,
                min(1.0, _f(prior_build_report.get("epoch_count")) / 100.0),
                1.0 if activation_report.get("stable_horizontal_variants") else 0.0,
                1.0 if prior_build_report.get("vertical_velocity_disabled") else 0.0,
                1.0 if not decision.get("paper_performance_claim", True) else 0.0,
            ],
            "boolean/proxy",
        )
    )
    manifest = {
        "stage": "N7B5_go2_velocity_frame_horizontal_diagnostic",
        "required_figures": REQUIRED_FIGURES,
        "generated": generated,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(item.get("nonempty") for item in generated),
        "diagnostic_only": True,
        "paper_performance_claim": False,
    }
    (out / "N7B5_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
