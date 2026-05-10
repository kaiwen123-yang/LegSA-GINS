"""N5D1 repair for clean ablation raw Doppler figures.

中文说明：N5D1 只修复 visual validation 的数据覆盖和图像语义；clean 曲线来自
已有 runtime EVAL_NAV 与 evaluation-only reference 对齐，不修改滤波器数学、不删 epoch。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import (
    align_by_time,
    compute_error_rows,
    load_port_eval_nav,
)
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav
from legsa_gins.raw_gnss.raw_doppler_plot_data_coverage import (
    FigureCoverage,
    inspect_plot_source_data,
)


REQUIRED_CLEAN_REPAIRED_FIGURES = [
    "01_clean_ablation_repaired/clean_horizontal_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/clean_up_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/clean_yaw_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/clean_roll_pitch_error_baseline_vs_raw_repaired.png",
    "01_clean_ablation_repaired/baseline_minus_raw_horizontal_diff_repaired.png",
    "01_clean_ablation_repaired/baseline_minus_raw_yaw_diff_repaired.png",
]


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


def _rel_time(rows: list[dict[str, float]]) -> list[float]:
    if not rows:
        return []
    first = float(rows[0]["timestamp"])
    return [float(row["timestamp"]) - first for row in rows]


def _values(rows: list[dict[str, float]], key: str) -> list[float]:
    return _finite([row.get(key) for row in rows])


def _save_line(
    plt,
    path: Path,
    series: list[tuple[str, list[float], list[float]]],
    *,
    title: str,
    ylabel: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for label, x, y in series:
        n = min(len(x), len(y))
        ax.plot(x[:n], y[:n], linewidth=0.95, label=label)
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _variant_eval_nav(root: Path, variant_id: str) -> Path | None:
    candidates = [
        root / "variants" / variant_id / "EVAL_NAV.csv",
        root / variant_id / "EVAL_NAV.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(root.rglob(f"{variant_id}/EVAL_NAV.csv"))
    return matches[0] if matches else None


def locate_clean_ablation_eval_navs(
    *,
    n5c_root: str | Path | None,
    n5d_root: str | Path | None,
) -> dict[str, str]:
    """Find clean variant EVAL_NAV files using the N5C-priority rule."""

    roots = [Path(root) for root in [n5c_root, n5d_root] if root]
    out: dict[str, str] = {}
    for variant_id in ["baseline_full", "baseline_plus_raw_doppler_r1"]:
        for root in roots:
            candidate = _variant_eval_nav(root, variant_id)
            if candidate:
                out[variant_id] = str(candidate)
                break
    return out


def load_clean_ablation_error_rows(
    *,
    n5c_root: str | Path | None,
    n5d_root: str | Path | None,
    dual_root: str | Path,
) -> dict[str, Any]:
    """Load repaired clean ablation error rows.

    中文说明：dual/final_v23 artifact 只作为 evaluation reference；不会作为 proposed
    solver input，也不会对输出做后处理修正。
    """

    eval_navs = locate_clean_ablation_eval_navs(n5c_root=n5c_root, n5d_root=n5d_root)
    reference_path = Path(dual_root) / "KF_GINS_Navresult.nav"
    if not reference_path.exists():
        return {
            "clean_ablation_data_missing": True,
            "missing_reason": "dual_reference_nav_missing",
            "variant_error_rows": {},
            "eval_nav_paths": eval_navs,
        }
    reference = parse_kfgins_nav(reference_path)
    errors: dict[str, list[dict[str, float]]] = {}
    missing: list[str] = []
    for variant_id in ["baseline_full", "baseline_plus_raw_doppler_r1"]:
        eval_nav = eval_navs.get(variant_id)
        if not eval_nav:
            missing.append(variant_id)
            continue
        estimate = load_port_eval_nav(eval_nav)
        errors[variant_id] = compute_error_rows(align_by_time(estimate, reference, tolerance=0.005))
        if not errors[variant_id]:
            missing.append(variant_id + "_aligned_rows")
    return {
        "clean_ablation_data_missing": bool(missing),
        "missing_clean_variants": missing,
        "variant_error_rows": errors,
        "eval_nav_paths": eval_navs,
        "reference_role": "DUAL_FINAL_V23_ARTIFACT_ROOT/KF_GINS_Navresult.nav",
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
    }


def _clean_series(
    figure_path: Path,
    baseline_rows: list[dict[str, float]],
    raw_rows: list[dict[str, float]],
    key: str,
    *,
    ylabel: str,
    title: str,
) -> dict[str, Any]:
    del ylabel, title
    return {
        "figure_path": str(figure_path),
        "mandatory": True,
        "source_data_roles": ["baseline_full_eval_nav_vs_reference", "baseline_plus_raw_doppler_eval_nav_vs_reference"],
        "min_rows": 1000,
        "min_series": 2,
        "min_x_range": 200.0,
        "series": [
            {"label": "baseline_full", "x": _rel_time(baseline_rows), "y": _values(baseline_rows, key)},
            {"label": "baseline_plus_raw_doppler_r1", "x": _rel_time(raw_rows), "y": _values(raw_rows, key)},
        ],
    }


def _diff_source(
    figure_path: Path,
    baseline_rows: list[dict[str, float]],
    raw_rows: list[dict[str, float]],
    key: str,
) -> dict[str, Any]:
    n = min(len(baseline_rows), len(raw_rows))
    x = _rel_time(baseline_rows[:n])
    y = [float(baseline_rows[i][key]) - float(raw_rows[i][key]) for i in range(n)]
    return {
        "figure_path": str(figure_path),
        "mandatory": True,
        "source_data_roles": ["baseline_minus_raw_clean_ablation_diff"],
        "min_rows": 1000,
        "min_series": 1,
        "min_x_range": 200.0,
        "series": [{"label": "baseline_minus_raw", "x": x, "y": y}],
    }


def generate_repaired_clean_ablation_figures(
    *,
    clean_data: dict[str, Any],
    figure_output_dir: str | Path,
) -> dict[str, Any]:
    """Regenerate the six N5D1 clean ablation figures with real time-series."""

    fig_root = Path(figure_output_dir)
    baseline = clean_data.get("variant_error_rows", {}).get("baseline_full", [])
    raw = clean_data.get("variant_error_rows", {}).get("baseline_plus_raw_doppler_r1", [])
    if not baseline or not raw:
        return {
            "clean_ablation_data_missing": True,
            "repaired_figures_count": 0,
            "coverage": [],
            "figure_paths": [],
            "paper_performance_claim": False,
            "proposed_factor_claim": False,
        }
    plt = _load_matplotlib()
    specs = [
        ("clean_horizontal_error_baseline_vs_raw_repaired.png", "horizontal_error_m", "m", "N5D1 repaired clean horizontal error (diagnostic only)"),
        ("clean_up_error_baseline_vs_raw_repaired.png", "up_error_m", "m", "N5D1 repaired clean up error (diagnostic only)"),
        ("clean_yaw_error_baseline_vs_raw_repaired.png", "yaw_error_deg", "deg", "N5D1 repaired clean yaw error (diagnostic only)"),
    ]
    coverage: list[FigureCoverage] = []
    generated: list[str] = []
    for file_name, key, ylabel, title in specs:
        rel = "01_clean_ablation_repaired/" + file_name
        path = fig_root / rel
        source = _clean_series(path, baseline, raw, key, ylabel=ylabel, title=title)
        _save_line(
            plt,
            path,
            [(row["label"], row["x"], row["y"]) for row in source["series"]],
            title=title,
            ylabel=ylabel,
        )
        coverage.append(inspect_plot_source_data(rel, source))
        generated.append(rel)

    rel = "01_clean_ablation_repaired/clean_roll_pitch_error_baseline_vs_raw_repaired.png"
    path = fig_root / rel
    rp_source = {
        "figure_path": str(path),
        "mandatory": True,
        "source_data_roles": ["baseline_full_eval_nav_vs_reference", "baseline_plus_raw_doppler_eval_nav_vs_reference"],
        "min_rows": 1000,
        "min_series": 4,
        "min_x_range": 200.0,
        "series": [
            {"label": "baseline_roll", "x": _rel_time(baseline), "y": _values(baseline, "roll_error_deg")},
            {"label": "raw_roll", "x": _rel_time(raw), "y": _values(raw, "roll_error_deg")},
            {"label": "baseline_pitch", "x": _rel_time(baseline), "y": _values(baseline, "pitch_error_deg")},
            {"label": "raw_pitch", "x": _rel_time(raw), "y": _values(raw, "pitch_error_deg")},
        ],
    }
    _save_line(
        plt,
        path,
        [(row["label"], row["x"], row["y"]) for row in rp_source["series"]],
        title="N5D1 repaired clean roll/pitch error (diagnostic only)",
        ylabel="deg",
    )
    coverage.append(inspect_plot_source_data(rel, rp_source))
    generated.append(rel)

    for file_name, key, ylabel in [
        ("baseline_minus_raw_horizontal_diff_repaired.png", "horizontal_error_m", "m"),
        ("baseline_minus_raw_yaw_diff_repaired.png", "yaw_error_deg", "deg"),
    ]:
        rel = "01_clean_ablation_repaired/" + file_name
        path = fig_root / rel
        source = _diff_source(path, baseline, raw, key)
        _save_line(
            plt,
            path,
            [(row["label"], row["x"], row["y"]) for row in source["series"]],
            title="N5D1 repaired baseline minus raw diff (diagnostic only)",
            ylabel=ylabel,
        )
        coverage.append(inspect_plot_source_data(rel, source))
        generated.append(rel)

    return {
        "clean_ablation_data_missing": False,
        "repaired_figures_count": len(generated),
        "figure_paths": generated,
        "coverage": coverage,
        "baseline_row_count": len(baseline),
        "baseline_plus_raw_row_count": len(raw),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def write_clean_fix_report(path: str | Path, report: dict[str, Any]) -> None:
    serializable = dict(report)
    serializable["coverage"] = [
        item.__dict__ if isinstance(item, FigureCoverage) else item for item in serializable.get("coverage", [])
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
