"""N8K2 real trajectory plot generation."""

# 中文说明：轨迹类图必须有真实坐标轴、轨迹、起终点或 delta 箭头。

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


TRAJECTORY_FILES = {
    "local_trajectory_overlay.png",
    "baseline_vs_variant_trajectory.png",
    "trajectory_delta_vector.png",
    "start_end_marker_trajectory.png",
    "zoomed_trajectory_key_region.png",
}


def generate_real_trajectory_plot(variant_id: str, data: dict[str, Any], filename: str, path: str | Path) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = data["series"]
    if filename == "local_trajectory_overlay.png":
        _plot_overlay(path, variant_id, rows, include_reference=False)
    elif filename == "baseline_vs_variant_trajectory.png":
        _plot_baseline_vs_variant(path, variant_id, rows, data)
    elif filename == "trajectory_delta_vector.png":
        _plot_delta_vectors(path, variant_id, rows)
    elif filename == "start_end_marker_trajectory.png":
        _plot_start_end(path, variant_id, rows)
    elif filename == "zoomed_trajectory_key_region.png":
        _plot_zoom(path, variant_id, rows)
    else:
        _plot_overlay(path, variant_id, rows, include_reference=False)
    return {
        "variant_id": variant_id,
        "category": "01_trajectory",
        "filename": filename,
        "path_role": "N8K2_FIGURE_OUTPUT_DIR",
        "present": path.exists(),
        "nonempty": path.exists() and path.stat().st_size > 0,
        "applicable": True,
        "real_data": True,
        "placeholder_allowed": False,
        "plot_kind": "real_trajectory",
        "row_count": len(rows),
        "series_count": 2,
    }


def build_real_trajectory_plot_report(entries: list[dict[str, Any]]) -> dict[str, Any]:
    trajectory_entries = [item for item in entries if item.get("category") == "01_trajectory"]
    return {
        "stage": "N8K2",
        "generated_count": len(trajectory_entries),
        "variant_count": len({item["variant_id"] for item in trajectory_entries}),
        "min_row_count": min((item.get("row_count", 0) for item in trajectory_entries), default=0),
        "min_series_count": min((item.get("series_count", 0) for item in trajectory_entries), default=0),
        "all_real_trajectory": all(item.get("real_data") is True and item.get("row_count", 0) >= 100 for item in trajectory_entries),
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def _plot_overlay(path: Path, variant_id: str, rows: list[dict[str, float]], *, include_reference: bool) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 7.0), dpi=115)
    ax.plot([r["baseline_east_m"] for r in rows], [r["baseline_north_m"] for r in rows], label="baseline no-feedback", linewidth=1.6)
    ax.plot([r["east_m"] for r in rows], [r["north_m"] for r in rows], label="ablation variant", linewidth=1.4)
    if include_reference:
        ax.plot([r["baseline_east_m"] for r in rows], [r["baseline_north_m"] for r in rows], "--", label="reference/evaluation only", linewidth=1.0)
    ax.set_title(f"{variant_id}: local trajectory overlay")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_baseline_vs_variant(path: Path, variant_id: str, rows: list[dict[str, float]], data: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(7.8, 7.0), dpi=115)
    ax.plot([r["baseline_east_m"] for r in rows], [r["baseline_north_m"] for r in rows], label="baseline no-feedback", linewidth=1.8, color="#2b8cbe")
    ax.plot([r["east_m"] for r in rows], [r["north_m"] for r in rows], "--", label="ablation variant", linewidth=1.5, color="#e34a33")
    deltas = [math.hypot(r["east_m"] - r["baseline_east_m"], r["north_m"] - r["baseline_north_m"]) for r in rows]
    metrics = data.get("metrics", {})
    source = data.get("data_source", "")
    text = "\n".join(
        [
            f"horizontal RMSE delta: {float(metrics.get('horizontal_rmse', 0.0)):.4g} m",
            f"horizontal P95 delta: {float(metrics.get('horizontal_p95', 0.0)):.4g} m",
            f"max sampled delta: {max(deltas or [0.0]):.4g} m",
            f"reference available: {'yes' if data.get('reference_rows', 0) else 'no'}",
            f"data source: {source}",
        ]
    )
    ax.text(0.02, 0.98, text, transform=ax.transAxes, va="top", ha="left", fontsize=7.5, bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.86, "edgecolor": "#636363"})
    ax.set_title(f"{variant_id}: baseline vs variant trajectory")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_delta_vectors(path: Path, variant_id: str, rows: list[dict[str, float]]) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 7.0), dpi=115)
    step = max(1, len(rows) // 32)
    east = [r["baseline_east_m"] for r in rows[::step]]
    north = [r["baseline_north_m"] for r in rows[::step]]
    de = [r["east_m"] - r["baseline_east_m"] for r in rows[::step]]
    dn = [r["north_m"] - r["baseline_north_m"] for r in rows[::step]]
    max_delta = max([math.hypot(e, n) for e, n in zip(de, dn)] + [1e-9])
    scale = 1.0 if max_delta > 0.2 else 0.2 / max_delta
    ax.plot([r["baseline_east_m"] for r in rows], [r["baseline_north_m"] for r in rows], color="#808080", linewidth=1.0, label="baseline path")
    ax.quiver(east, north, [v * scale for v in de], [v * scale for v in dn], angles="xy", scale_units="xy", scale=1, color="#d95f0e", width=0.003, label=f"delta arrows x{scale:.1f}")
    ax.set_title(f"{variant_id}: sampled trajectory delta vectors")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_start_end(path: Path, variant_id: str, rows: list[dict[str, float]]) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 7.0), dpi=115)
    ax.plot([r["east_m"] for r in rows], [r["north_m"] for r in rows], label="ablation variant", linewidth=1.4)
    ax.scatter([rows[0]["east_m"]], [rows[0]["north_m"]], marker="o", color="#2ca25f", s=80, label="start")
    ax.scatter([rows[-1]["east_m"]], [rows[-1]["north_m"]], marker="X", color="#de2d26", s=90, label="end")
    ax.set_title(f"{variant_id}: start/end marked trajectory")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_zoom(path: Path, variant_id: str, rows: list[dict[str, float]]) -> None:
    deltas = [math.hypot(r["east_m"] - r["baseline_east_m"], r["north_m"] - r["baseline_north_m"]) for r in rows]
    center = max(range(len(deltas)), key=deltas.__getitem__) if deltas else 0
    half = max(20, len(rows) // 20)
    subset = rows[max(0, center - half) : min(len(rows), center + half)]
    fig, ax = plt.subplots(figsize=(7.4, 7.0), dpi=115)
    ax.plot([r["baseline_east_m"] for r in subset], [r["baseline_north_m"] for r in subset], label="baseline zoom", linewidth=1.8)
    ax.plot([r["east_m"] for r in subset], [r["north_m"] for r in subset], label="variant zoom", linewidth=1.6)
    ax.scatter([rows[center]["east_m"]], [rows[center]["north_m"]], color="#d95f0e", s=60, label="max delta region")
    ax.set_title(f"{variant_id}: zoomed key region")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
