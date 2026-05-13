"""N7C figure generation for Go2 horizontal velocity weak-prior evidence.

中文说明：图像只写入 runtime figure dir，不进入 Git；所有曲线都是工程诊断，
不是 paper performance claim。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_N7C_FIGURES = [
    "go2_horizontal_velocity_time.png",
    "go2_horizontal_velocity_vs_receiver_velocity.png",
    "go2_horizontal_velocity_vs_raw_doppler.png",
    "clean_horizontal_error_no_go2_vs_go2_horizontal.png",
    "clean_yaw_error_no_go2_vs_go2_horizontal.png",
    "horizontal_velocity_prior_residual_time.png",
    "horizontal_velocity_prior_update_timeline.png",
    "stress_receiver_velocity_no_go2_vs_go2.png",
    "stress_raw_doppler_no_go2_vs_go2.png",
    "n7c_decision_panel.png",
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


def _bar(path: Path, title: str, labels: list[str], values: list[float], ylabel: str = "") -> dict[str, Any]:
    plt = _load_matplotlib()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(9.0, 4.8))
    ax = fig.add_axes([0.16, 0.30, 0.78, 0.60])
    ax.bar(range(len(labels)), values, color="#4c78a8")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=24, ha="right", fontsize=8)
    ax.set_title(title)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"path": str(path), "nonempty": path.exists() and path.stat().st_size > 0}


def generate_n7c_visual_plots(
    *,
    figure_output_dir: str | Path,
    output_dir: str | Path,
    clean_root: str | Path,
    n5b_root: str | Path,
    prior_build_report: dict[str, Any],
    variant_summaries: dict[str, Any],
    comparison_report: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    figs = Path(figure_output_dir)
    out = Path(output_dir)
    generated: list[dict[str, Any]] = []
    prior_rows = _read_csv(out / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv")[:6000]
    receiver_rows: list[dict[str, str]] = []
    for candidate in Path(clean_root).rglob("*.gnss"):
        receiver_rows = _read_csv(candidate)[:6000]
        if receiver_rows:
            break
    raw_rows: list[dict[str, str]] = []
    for candidate in Path(n5b_root).rglob("*DOPPLER*FACTORS*.csv"):
        raw_rows = _read_csv(candidate)[:6000]
        if raw_rows:
            break
    generated.append(
        _line(
            figs / REQUIRED_N7C_FIGURES[0],
            "Go2 horizontal velocity weak prior",
            [
                ("vn", [_f(row.get("time")) for row in prior_rows], [_f(row.get("vn")) for row in prior_rows]),
                ("ve", [_f(row.get("time")) for row in prior_rows], [_f(row.get("ve")) for row in prior_rows]),
            ],
            "m/s",
        )
    )
    generated.append(
        _line(
            figs / REQUIRED_N7C_FIGURES[1],
            "Go2 horizontal velocity vs receiver velocity",
            [
                ("go2_vn", [_f(row.get("time")) for row in prior_rows], [_f(row.get("vn")) for row in prior_rows]),
                ("receiver_vn", [_f(row.get("time")) for row in receiver_rows], [_f(row.get("vn")) for row in receiver_rows]),
            ],
            "m/s",
        )
    )
    generated.append(
        _line(
            figs / REQUIRED_N7C_FIGURES[2],
            "Go2 horizontal velocity vs raw Doppler",
            [
                ("go2_vn", [_f(row.get("time")) for row in prior_rows], [_f(row.get("vn")) for row in prior_rows]),
                ("raw_vn", [_f(row.get("time")) for row in raw_rows], [_f(row.get("vn")) for row in raw_rows]),
            ],
            "m/s",
        )
    )
    variants = variant_summaries.get("variants", [])
    labels = [str(row.get("variant_id")) for row in variants]
    horizontal = [_f(row.get("summary", {}).get("horizontal_rmse_m")) for row in variants]
    yaw = [_f(row.get("summary", {}).get("yaw_rmse_deg")) for row in variants]
    generated.append(_bar(figs / REQUIRED_N7C_FIGURES[3], "Clean horizontal error", labels[:5], horizontal[:5], "m"))
    generated.append(_bar(figs / REQUIRED_N7C_FIGURES[4], "Clean yaw error", labels[:5], yaw[:5], "deg"))
    generated.append(
        _line(
            figs / REQUIRED_N7C_FIGURES[5],
            "Horizontal velocity prior residual proxy",
            [("std_vn", [_f(row.get("time")) for row in prior_rows], [_f(row.get("std_vn")) for row in prior_rows])],
            "m/s",
        )
    )
    generated.append(
        _line(
            figs / REQUIRED_N7C_FIGURES[6],
            "Horizontal velocity prior update timeline",
            [("active", [_f(row.get("time")) for row in prior_rows], [1.0 for _ in prior_rows])],
            "active row",
        )
    )
    comp = comparison_report.get("comparisons", {})
    generated.append(
        _bar(
            figs / REQUIRED_N7C_FIGURES[7],
            "Receiver velocity stress delta",
            ["horizontal", "yaw"],
            [
                _f(comp.get("receiver_velocity_stress_plus_go2_minus_no_go2", {}).get("delta", {}).get("horizontal_rmse_m")),
                _f(comp.get("receiver_velocity_stress_plus_go2_minus_no_go2", {}).get("delta", {}).get("yaw_rmse_deg")),
            ],
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_N7C_FIGURES[8],
            "Raw Doppler stress delta",
            ["horizontal", "yaw"],
            [
                _f(comp.get("raw_doppler_stress_plus_go2_minus_no_go2", {}).get("delta", {}).get("horizontal_rmse_m")),
                _f(comp.get("raw_doppler_stress_plus_go2_minus_no_go2", {}).get("delta", {}).get("yaw_rmse_deg")),
            ],
        )
    )
    generated.append(
        _bar(
            figs / REQUIRED_N7C_FIGURES[9],
            "N7C decision panel",
            ["csv", "updates", "vertical_off", "no_claim", "no_fgo"],
            [
                1.0 if prior_build_report.get("csv_generated") else 0.0,
                min(1.0, _f(decision.get("update_count")) / 10.0),
                1.0 if not decision.get("go2_vertical_velocity_prior_enabled", True) else 0.0,
                1.0 if not decision.get("paper_performance_claim", True) else 0.0,
                1.0 if not decision.get("fgo", True) else 0.0,
            ],
        )
    )
    manifest = {
        "stage": "N7C_go2_horizontal_velocity_weak_prior",
        "required_figures": REQUIRED_N7C_FIGURES,
        "generated": generated,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_N7C_FIGURES),
        "required_figures_nonempty": all(row.get("nonempty") for row in generated),
        "paper_performance_claim": False,
    }
    (out / "N7C_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
