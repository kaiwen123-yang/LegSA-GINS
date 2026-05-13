"""Generate N7B3 diagnostic-only visual plots.

中文说明：所有图都写入 runtime figure dir，不进入 Git，也不构成 paper
performance evidence。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURES = [
    "velocity_frame_candidate_rmse_bar.png",
    "velocity_frame_bias_bar.png",
    "contact_model_uncertain_contact_swing_bar.png",
    "contact_model_alternating_ratio_bar.png",
    "contact_model_timeline_best_candidates.png",
    "go2_velocity_prior_epoch_timeline.png",
    "diagnostic_activation_metric_delta_bar.png",
    "diagnostic_activation_error_curves.png",
    "yaw_rate_diagnostic_consistency.png",
    "n7b3_decision_panel.png",
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    import csv

    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def generate_n7b3_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    velocity_frame_report: dict[str, Any],
    contact_candidate_report: dict[str, Any],
    contact_candidate_rows: list[dict[str, Any]],
    velocity_prior_report: dict[str, Any],
    yaw_rate_report: dict[str, Any],
    activation_report: dict[str, Any],
    variant_summaries: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    generated: list[dict[str, Any]] = []
    candidates = velocity_frame_report.get("candidates", {})
    labels = list(candidates.keys())
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[0],
            "Velocity frame candidate RMSE",
            labels,
            [_f(candidates[label].get("combined_cross_source_rmse")) for label in labels],
            "m/s",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[1],
            "Velocity frame receiver bias norm",
            labels,
            [
                math.sqrt(
                    sum(
                        _f(candidates[label].get("bias", {}).get("to_receiver", {}).get(axis)) ** 2
                        for axis in ("vn", "ve", "vd")
                    )
                )
                for label in labels
            ],
            "m/s",
        )
    )
    reports = contact_candidate_report.get("model_reports", {})
    model_labels = list(reports.keys())
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[2],
            "Contact model uncertain/contact/swing",
            model_labels,
            [
                _f(reports[label].get("uncertain_ratio"))
                + _f(reports[label].get("contact_ratio"))
                + _f(reports[label].get("swing_ratio"))
                for label in model_labels
            ],
            "ratio sum",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[3],
            "Contact model alternating ratio",
            model_labels,
            [_f(reports[label].get("alternating_ratio")) for label in model_labels],
            "ratio",
        )
    )
    selected = str(decision.get("selected_diagnostic_contact_model") or model_labels[0] if model_labels else "")
    timeline = [row for row in contact_candidate_rows if row.get("candidate_model") == selected][:5000]
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[4],
            "Best contact model timeline",
            [
                (
                    selected,
                    [_f(row.get("time")) for row in timeline],
                    [_f(row.get("contact_count")) for row in timeline],
                )
            ],
            "contact count",
        )
    )
    prior_rows = _read_csv(out / "GO2_VELOCITY_WEAK_PRIORS_DIAGNOSTIC.csv")
    gated_rows = _read_csv(out / "GO2_VELOCITY_CONTACT_GATED_PRIORS_DIAGNOSTIC.csv")
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[5],
            "Go2 velocity prior epoch timeline",
            [
                ("weak", [_f(row.get("time")) for row in prior_rows[:5000]], [1.0 for _ in prior_rows[:5000]]),
                ("contact_gated", [_f(row.get("time")) for row in gated_rows[:5000]], [2.0 for _ in gated_rows[:5000]]),
            ],
            "policy index",
        )
    )
    variants = variant_summaries.get("variants", [])
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[6],
            "Diagnostic activation update counts",
            [str(row.get("variant_id")) for row in variants],
            [_f(row.get("go2_velocity_prior_update_count")) + _f(row.get("go2_yaw_rate_prior_update_count")) for row in variants],
            "updates",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[7],
            "Diagnostic state delta",
            [str(row.get("variant_id")) for row in variants],
            [_f(row.get("state_delta_summary", {}).get("velocity_delta_p95_mps")) for row in variants],
            "m/s",
        )
    )
    yaw_rows = _read_csv(out / "GO2_YAW_RATE_WEAK_PRIORS_DIAGNOSTIC.csv")
    generated.append(
        _line(
            figs / REQUIRED_FIGURES[8],
            "Yaw-rate diagnostic consistency",
            [("go2_yaw_rate", [_f(row.get("time")) for row in yaw_rows[:5000]], [_f(row.get("yaw_rate_radps")) for row in yaw_rows[:5000]])],
            "rad/s",
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_FIGURES[9],
            "N7B3 decision panel",
            ["contact_ready", "activation_degraded", "paper_claim", "fgo"],
            [
                1.0 if decision.get("contact_model_ready") else 0.0,
                1.0 if activation_report.get("diagnostic_degradation_detected") else 0.0,
                1.0 if decision.get("paper_performance_claim") else 0.0,
                1.0 if decision.get("fgo") else 0.0,
            ],
        )
    )
    manifest = {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "required_figures": REQUIRED_FIGURES,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_FIGURES),
        "required_figures_nonempty": all(row["nonempty"] for row in generated),
        "figures": generated,
        "velocity_prior_epoch_count": velocity_prior_report.get("prior_epoch_count"),
        "yaw_rate_prior_epoch_count": yaw_rate_report.get("prior_epoch_count"),
        "paper_performance_claim": False,
    }
    (out / "N7B3_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
