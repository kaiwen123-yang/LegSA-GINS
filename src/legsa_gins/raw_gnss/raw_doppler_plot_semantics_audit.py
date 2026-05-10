"""N5D1 plot semantics fixes for raw Doppler visual validation.

中文说明：这里修正图名和标签语义，特别是 raw-vs-receiver velocity 只能叫
cross-source consistency，不能叫 truth error；stress pair 计数也去重。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.raw_doppler_plot_data_coverage import FigureCoverage, inspect_plot_source_data


CORRECTED_3SIGMA_FIGURE = "03_semantics_fixed/raw_minus_receiver_velocity_consistency_vs_raw_doppler_3sigma.png"
STRESS_UNIQUE_PAIR_FIGURE = "03_semantics_fixed/stress_delta_unique_pairs_bar.png"
STRESS_LABEL_MAPPING_FIGURE = "03_semantics_fixed/stress_pair_label_mapping.png"

SHORT_LABELS = {
    "velocity_isolation": "isolation",
    "receiver_velocity_disabled": "disabled",
    "receiver_velocity_std_scale_5": "stdx5",
    "receiver_velocity_outage_30s": "outage30",
    "receiver_velocity_noise_0p5": "noise0.5",
}

DUPLICATE_PAIR_ALIASES = {
    "receiver_velocity_disabled": "velocity_isolation",
}


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _axis(plt, figsize: tuple[float, float] = (8.8, 4.9)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _finite(values: list[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            out.append(number)
    return out


def _rel_times(rows: list[dict[str, Any]]) -> list[float]:
    if not rows:
        return []
    first = float(rows[0].get("time", rows[0].get("timestamp", 0.0)) or 0.0)
    return [float(row.get("time", row.get("timestamp", first)) or first) - first for row in rows]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return _finite([row.get(key) for row in rows])


def _metric_delta(pair: dict[str, Any], key: str) -> float:
    value = pair.get("delta_plus_raw_minus_no_raw", {}).get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else 0.0


def deduplicate_stress_pairs(stress_eval: dict[str, Any]) -> dict[str, Any]:
    pairs = [row for row in stress_eval.get("pairwise_stress_deltas", []) if isinstance(row, dict)]
    seen_keys: set[str] = set()
    unique_pairs: list[dict[str, Any]] = []
    duplicate_pairs: list[dict[str, Any]] = []
    for pair in pairs:
        pair_id = str(pair.get("pair_id", ""))
        semantic_key = DUPLICATE_PAIR_ALIASES.get(pair_id, pair_id)
        if semantic_key in seen_keys:
            duplicate_pairs.append(pair)
            continue
        seen_keys.add(semantic_key)
        unique_pairs.append(pair)
    return {
        "unique_pairs": unique_pairs,
        "duplicate_pairs": duplicate_pairs,
        "unique_stress_pair_count": len(unique_pairs),
        "duplicate_stress_pair_count": len(duplicate_pairs),
        "short_label_mapping": SHORT_LABELS,
    }


def generate_semantics_fixed_figures(
    *,
    raw_receiver_velocity_pairs: list[dict[str, Any]],
    stress_eval: dict[str, Any],
    figure_output_dir: str | Path,
) -> dict[str, Any]:
    """Generate corrected N5D1 semantics figures."""

    fig_root = Path(figure_output_dir)
    plt = _load_matplotlib()
    coverage: list[FigureCoverage] = []
    generated: list[str] = []

    rel = CORRECTED_3SIGMA_FIGURE
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    times = _rel_times(raw_receiver_velocity_pairs)
    diff = _values(raw_receiver_velocity_pairs, "diff_norm")
    sigma = _values(raw_receiver_velocity_pairs, "raw_3sigma_norm")
    fig, ax = _axis(plt)
    ax.plot(times[: len(diff)], diff, linewidth=0.9, label="raw minus receiver velocity norm")
    ax.plot(times[: len(sigma)], sigma, linewidth=0.9, label="raw Doppler velocity 3sigma norm")
    ax.set_title("N5D1 cross-source velocity consistency (diagnostic only)")
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel("raw Doppler minus receiver velocity norm (m/s)")
    ax.text(
        0.02,
        0.95,
        "receiver-native velocity is not truth; consistency only",
        transform=ax.transAxes,
        va="top",
        fontsize=8,
    )
    ax.grid(True, linewidth=0.3, alpha=0.45)
    ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["raw_doppler_velocity", "receiver_native_velocity"],
                "min_rows": 200,
                "min_series": 2,
                "series": [
                    {"label": "raw_minus_receiver_velocity_norm", "x": times, "y": diff},
                    {"label": "raw_doppler_3sigma_norm", "x": times, "y": sigma},
                ],
            },
        )
    )
    generated.append(rel)

    dedup = deduplicate_stress_pairs(stress_eval)
    unique_pairs = [pair for pair in dedup["unique_pairs"] if pair.get("pair_id") in SHORT_LABELS]
    labels = [SHORT_LABELS[str(pair.get("pair_id"))] for pair in unique_pairs]
    values = [_metric_delta(pair, "yaw_rmse_deg") for pair in unique_pairs]
    rel = STRESS_UNIQUE_PAIR_FIGURE
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.bar(labels, values)
    ax.set_title("N5D1 unique stress pairs yaw delta (diagnostic only)")
    ax.set_ylabel("plus_raw - no_raw yaw RMSE (deg)")
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["unique_stress_pair_deltas"],
                "min_rows": 4,
                "min_series": 1,
                "required_pairs": ["isolation", "stdx5", "outage30", "noise0.5"],
                "present_pairs": labels,
                "series": [{"label": "unique_yaw_delta", "x": list(range(len(values))), "y": values}],
            },
        )
    )
    generated.append(rel)

    rel = STRESS_LABEL_MAPPING_FIGURE
    path = fig_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(8.8, 4.2))
    ax.axis("off")
    lines = [
        "short label mapping:",
        *[f"{short}: {long}" for long, short in SHORT_LABELS.items()],
        "",
        f"unique_stress_pair_count: {dedup['unique_stress_pair_count']}",
        f"duplicate_stress_pair_count: {dedup['duplicate_stress_pair_count']}",
        "diagnostic only; not tuning evidence",
    ]
    ax.text(0.02, 0.92, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9)
    ax.set_title("N5D1 stress label mapping")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    coverage.append(
        inspect_plot_source_data(
            rel,
            {
                "figure_path": str(path),
                "mandatory": True,
                "source_data_roles": ["stress_label_mapping"],
                "min_rows": 5,
                "min_series": 1,
                "series": [{"label": "mapping_rows", "x": list(range(len(lines))), "y": [1.0] * len(lines)}],
            },
        )
    )
    generated.append(rel)

    return {
        "velocity_3sigma_semantics_fixed": True,
        "old_name_deprecated": "06_std_consistency/velocity_error_vs_raw_doppler_3sigma.png",
        "new_figure_name": CORRECTED_3SIGMA_FIGURE,
        "receiver_velocity_not_truth_note": True,
        "duplicate_stress_pair_count": dedup["duplicate_stress_pair_count"],
        "unique_stress_pair_count": dedup["unique_stress_pair_count"],
        "long_labels_fixed": True,
        "short_label_mapping": SHORT_LABELS,
        "figure_paths": generated,
        "coverage": coverage,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def write_semantics_fix_report(path: str | Path, report: dict[str, Any]) -> None:
    serializable = dict(report)
    serializable["coverage"] = [
        item.__dict__ if isinstance(item, FigureCoverage) else item for item in serializable.get("coverage", [])
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
