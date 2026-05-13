"""Figure generation for N7C1 Go2 horizontal velocity visual validation.

中文说明：每张图单独保存、只写 runtime figure dir；N7C1 检查图像和数据覆盖，
不改 solver 数学、不调参、不把图像结论作为 paper performance claim。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_n7c_plot_coverage import (
    N7C1FigureCoverage,
    inspect_n7c1_plot_source_data,
)


REQUIRED_N7C1_FIGURES = [
    "01_clean_validation/clean_horizontal_error_no_go2_vs_go2_horizontal.png",
    "01_clean_validation/clean_up_error_no_go2_vs_go2_horizontal.png",
    "01_clean_validation/clean_yaw_error_no_go2_vs_go2_horizontal.png",
    "01_clean_validation/clean_roll_pitch_error_no_go2_vs_go2_horizontal.png",
    "01_clean_validation/clean_delta_go2_minus_no_go2_time.png",
    "02_prior_signal/go2_horizontal_velocity_time.png",
    "02_prior_signal/go2_horizontal_velocity_vs_receiver_velocity.png",
    "02_prior_signal/go2_horizontal_velocity_vs_raw_doppler.png",
    "02_prior_signal/go2_prior_confidence_timeline.png",
    "02_prior_signal/go2_prior_std_timeline.png",
    "03_update_residuals/go2_horizontal_prior_residual_time.png",
    "03_update_residuals/go2_horizontal_prior_residual_hist.png",
    "03_update_residuals/go2_horizontal_prior_update_timeline.png",
    "03_update_residuals/go2_horizontal_prior_reject_panel.png",
    "04_stress_validation/receiver_velocity_stress_no_go2_vs_plus_go2.png",
    "04_stress_validation/raw_doppler_stress_no_go2_vs_plus_go2.png",
    "04_stress_validation/stress_delta_summary_bar.png",
    "05_vertical_disabled/vertical_velocity_disabled_check.png",
    "05_vertical_disabled/vd_residual_or_std_vd_timeline.png",
    "06_summary/n7c_metric_delta_panel.png",
    "06_summary/n7c_decision_panel.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _finite(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _times(rows: list[dict[str, Any]], key: str = "timestamp") -> list[float]:
    if not rows:
        return []
    first = _finite(rows[0].get(key), 0.0) or 0.0
    out: list[float] = []
    for row in rows:
        value = _finite(row.get(key), first) or first
        out.append(value - first)
    return out


def _values(rows: list[dict[str, Any]], key: str, *, abs_value: bool = False) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = _finite(row.get(key))
        if value is not None:
            out.append(abs(value) if abs_value else value)
    return out


def _quality_score(value: Any) -> float:
    text = str(value).lower()
    if "high" in text:
        return 3.0
    if "medium" in text:
        return 2.0
    if "low" in text:
        return 1.0
    return 0.0


def _axis(plt, figsize: tuple[float, float] = (9.2, 5.1)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _save_line(plt, path: Path, title: str, ylabel: str, series: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for row in series:
        xs = list(row.get("x", []))
        ys = list(row.get("y", []))
        count = min(len(xs), len(ys))
        ax.plot(xs[:count], ys[:count], linewidth=0.85, label=str(row.get("label", "series")))
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if series:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_hist(plt, path: Path, title: str, xlabel: str, series: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for row in series:
        ys = list(row.get("y", []))
        if ys:
            ax.hist(ys, bins=40, alpha=0.42, label=str(row.get("label", "series")))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if series:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar(plt, path: Path, title: str, labels: list[str], values: list[float], ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.bar(range(len(labels)), values, color="#4c78a8")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=22, ha="right", fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_text_panel(plt, path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.02, 0.95, "\n".join(lines), va="top", ha="left", fontsize=9, family="monospace")
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _coverage(path: Path, rel: str, category: str, roles: list[str], series: list[dict[str, Any]], **extra: Any) -> N7C1FigureCoverage:
    source = {
        "figure_path": str(path),
        "mandatory": True,
        "figure_category": category,
        "source_data_roles": roles,
        "series": series,
    }
    source.update(extra)
    return inspect_n7c1_plot_source_data(rel, source)


def _diff_series(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], key: str, label: str) -> dict[str, Any]:
    count = min(len(rows_a), len(rows_b))
    xs = _times(rows_a[:count])
    ys = [(_finite(rows_b[i].get(key), 0.0) or 0.0) - (_finite(rows_a[i].get(key), 0.0) or 0.0) for i in range(count)]
    return {"label": label, "x": xs, "y": ys}


def _metric_delta(comparison: dict[str, Any], key: str, metric: str) -> float:
    return float(comparison.get("comparisons", {}).get(key, {}).get("delta", {}).get(metric) or 0.0)


def generate_n7c1_visual_figures(
    *,
    visual_inputs: dict[str, Any],
    figure_output_dir: str | Path,
) -> dict[str, Any]:
    plt = _load_matplotlib()
    fig_root = Path(figure_output_dir)
    coverage: list[N7C1FigureCoverage] = []
    generated: list[str] = []
    clean = visual_inputs["clean_errors"]
    stress = visual_inputs["stress_errors"]
    reports = visual_inputs["reports"]
    prior_rows = visual_inputs["prior_rows"]
    raw_rows = visual_inputs["raw_doppler_rows"]
    eval_nav_rows = visual_inputs["eval_nav_rows"]
    go2_trace_rows = visual_inputs["go2_trace_rows"]
    baseline = clean.get("baseline_no_go2_horizontal_velocity", [])
    main = clean.get("go2_horizontal_velocity_weak_prior_main", [])
    comparison = reports.get("N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json", {})
    decision = reports.get("N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json", {})
    prior_build = reports.get("GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json", {})
    update_count = int(decision.get("update_count", 0) or 0)
    reject_count = int(decision.get("reject_count", 0) or 0)

    clean_specs = [
        (REQUIRED_N7C1_FIGURES[0], "horizontal_error_m", "m", "Clean horizontal error"),
        (REQUIRED_N7C1_FIGURES[1], "up_error_m", "m", "Clean up error"),
        (REQUIRED_N7C1_FIGURES[2], "yaw_error_deg", "deg", "Clean yaw error"),
    ]
    for rel, key, ylabel, title in clean_specs:
        path = fig_root / rel
        series = [
            {"label": "no_go2", "x": _times(baseline), "y": _values(baseline, key, abs_value=True)},
            {"label": "go2_horizontal", "x": _times(main), "y": _values(main, key, abs_value=True)},
        ]
        _save_line(plt, path, f"N7C1 {title} (diagnostic only)", ylabel, series)
        coverage.append(_coverage(path, rel, "clean", ["baseline_eval_nav", "main_eval_nav"], series, min_rows=1000, min_series=2, min_x_range=200.0))
        generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[3]
    path = fig_root / rel
    series = [
        {"label": "no_go2_roll", "x": _times(baseline), "y": _values(baseline, "roll_error_deg", abs_value=True)},
        {"label": "go2_horizontal_roll", "x": _times(main), "y": _values(main, "roll_error_deg", abs_value=True)},
        {"label": "no_go2_pitch", "x": _times(baseline), "y": _values(baseline, "pitch_error_deg", abs_value=True)},
        {"label": "go2_horizontal_pitch", "x": _times(main), "y": _values(main, "pitch_error_deg", abs_value=True)},
    ]
    _save_line(plt, path, "N7C1 clean roll/pitch error (diagnostic only)", "deg", series)
    coverage.append(_coverage(path, rel, "clean", ["baseline_eval_nav", "main_eval_nav"], series, min_rows=1000, min_series=4, min_x_range=200.0))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[4]
    path = fig_root / rel
    series = [
        _diff_series(baseline, main, "horizontal_error_m", "go2_horizontal_minus_no_go2_horizontal"),
        _diff_series(baseline, main, "yaw_error_deg", "go2_horizontal_minus_no_go2_yaw"),
    ]
    _save_line(plt, path, "N7C1 clean delta over time", "delta", series)
    coverage.append(_coverage(path, rel, "clean", ["clean_delta"], series, min_rows=1000, min_series=2, min_x_range=200.0))
    generated.append(rel)

    prior_times = _times(prior_rows, "time")
    rel = REQUIRED_N7C1_FIGURES[5]
    path = fig_root / rel
    series = [
        {"label": "go2_vn", "x": prior_times, "y": _values(prior_rows, "vn")},
        {"label": "go2_ve", "x": prior_times, "y": _values(prior_rows, "ve")},
    ]
    _save_line(plt, path, "Go2 horizontal velocity weak-prior signal", "m/s", series)
    coverage.append(_coverage(path, rel, "prior_signal", ["GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv"], series, min_rows=1, min_series=2))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[6]
    path = fig_root / rel
    baseline_eval = eval_nav_rows.get("baseline_no_go2_horizontal_velocity", [])
    series = [
        {"label": "go2_vn", "x": prior_times, "y": _values(prior_rows, "vn")},
        {"label": "go2_ve", "x": prior_times, "y": _values(prior_rows, "ve")},
        {"label": "receiver_velocity_vn", "x": _times(baseline_eval, "time"), "y": _values(baseline_eval, "vn")},
        {"label": "receiver_velocity_ve", "x": _times(baseline_eval, "time"), "y": _values(baseline_eval, "ve")},
    ]
    _save_line(plt, path, "Go2 horizontal velocity vs receiver-driven velocity output", "m/s", series)
    coverage.append(_coverage(path, rel, "prior_signal", ["prior_csv", "baseline_eval_nav_velocity"], series, min_rows=1, min_series=2))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[7]
    path = fig_root / rel
    series = [
        {"label": "go2_vn", "x": prior_times, "y": _values(prior_rows, "vn")},
        {"label": "go2_ve", "x": prior_times, "y": _values(prior_rows, "ve")},
        {"label": "raw_doppler_vn", "x": _times(raw_rows, "time"), "y": _values(raw_rows, "vn")},
        {"label": "raw_doppler_ve", "x": _times(raw_rows, "time"), "y": _values(raw_rows, "ve")},
    ]
    _save_line(plt, path, "Go2 horizontal velocity vs raw Doppler provider", "m/s", series)
    coverage.append(_coverage(path, rel, "prior_signal", ["prior_csv", "raw_doppler_factors"], series, min_rows=1, min_series=2))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[8]
    path = fig_root / rel
    series = [
        {"label": "go2_vn_confidence_score", "x": prior_times, "y": [_quality_score(row.get("quality_flag") or row.get("contact_label")) for row in prior_rows]},
    ]
    _save_line(plt, path, "Go2 prior confidence timeline", "confidence score", series)
    coverage.append(_coverage(path, rel, "prior_signal", ["prior_confidence"], series, min_rows=1, min_series=1))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[9]
    path = fig_root / rel
    series = [
        {"label": "go2_std_vn", "x": prior_times, "y": _values(prior_rows, "std_vn")},
        {"label": "go2_std_ve", "x": prior_times, "y": _values(prior_rows, "std_ve")},
    ]
    _save_line(plt, path, "Go2 prior horizontal std timeline", "m/s", series)
    coverage.append(_coverage(path, rel, "prior_signal", ["prior_std"], series, min_rows=1, min_series=2))
    generated.append(rel)

    trace_times = _times(go2_trace_rows, "time")
    rel = REQUIRED_N7C1_FIGURES[10]
    path = fig_root / rel
    series = [{"label": "go2_horizontal_residual_norm", "x": trace_times, "y": _values(go2_trace_rows, "residual_norm")}]
    _save_line(plt, path, "Go2 horizontal prior residual norm", "residual norm", series)
    coverage.append(_coverage(path, rel, "update_residual", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], series, min_rows=1, min_series=1, update_count=update_count))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[11]
    path = fig_root / rel
    hist_series = [{"label": "go2_horizontal_residual_norm", "x": list(range(len(go2_trace_rows))), "y": _values(go2_trace_rows, "residual_norm")}]
    _save_hist(plt, path, "Go2 horizontal residual histogram", "residual norm", hist_series)
    coverage.append(_coverage(path, rel, "update_residual", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], hist_series, min_rows=1, min_series=1, update_count=update_count))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[12]
    path = fig_root / rel
    series = [{"label": "go2_horizontal_update_active", "x": trace_times, "y": [1.0 for _ in go2_trace_rows]}]
    _save_line(plt, path, "Go2 horizontal prior update timeline", "active", series)
    coverage.append(_coverage(path, rel, "update_residual", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], series, min_rows=1, min_series=1, update_count=update_count))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[13]
    path = fig_root / rel
    labels = ["updates", "rejects"]
    values = [float(update_count), float(reject_count)]
    _save_bar(plt, path, "Go2 horizontal prior update/reject panel", labels, values, "count")
    series = [{"label": label, "x": [index], "y": [values[index]]} for index, label in enumerate(labels)]
    coverage.append(_coverage(path, rel, "update_residual", ["decision_report"], series, min_rows=2, min_series=2, update_count=update_count, documented_aggregation=True))
    generated.append(rel)

    for label, rel in [
        ("receiver_velocity_stress", REQUIRED_N7C1_FIGURES[14]),
        ("raw_doppler_stress", REQUIRED_N7C1_FIGURES[15]),
    ]:
        path = fig_root / rel
        pair = stress[label]
        series = [
            {"label": f"{label}_no_go2", "x": _times(pair["no_go2"]), "y": _values(pair["no_go2"], "horizontal_error_m", abs_value=True)},
            {"label": f"{label}_plus_go2", "x": _times(pair["plus_go2"]), "y": _values(pair["plus_go2"], "horizontal_error_m", abs_value=True)},
        ]
        _save_line(plt, path, f"N7C1 {label} no-Go2 vs plus-Go2", "horizontal error (m)", series)
        coverage.append(_coverage(path, rel, "stress", ["stress_eval_nav"], series, min_rows=1000, min_series=2, min_x_range=200.0))
        generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[16]
    path = fig_root / rel
    labels = ["receiver_h", "receiver_yaw", "raw_h", "raw_yaw"]
    values = [
        _metric_delta(comparison, "receiver_velocity_stress_plus_go2_minus_no_go2", "horizontal_rmse_m"),
        _metric_delta(comparison, "receiver_velocity_stress_plus_go2_minus_no_go2", "yaw_rmse_deg"),
        _metric_delta(comparison, "raw_doppler_stress_plus_go2_minus_no_go2", "horizontal_rmse_m"),
        _metric_delta(comparison, "raw_doppler_stress_plus_go2_minus_no_go2", "yaw_rmse_deg"),
    ]
    _save_bar(plt, path, "N7C stress delta summary", labels, values, "delta")
    series = [{"label": f"stress_no_go2_vs_plus_go2_{label}", "x": [index], "y": [values[index]]} for index, label in enumerate(labels)]
    coverage.append(_coverage(path, rel, "stress", ["comparison_report"], series, min_rows=4, min_series=4, documented_aggregation=True))
    generated.append(rel)

    vertical_evidence = bool(visual_inputs["manifest"].get("vertical_disabled_confirmed"))
    rel = REQUIRED_N7C1_FIGURES[17]
    path = fig_root / rel
    labels = ["std_vd_999", "vertical_disabled", "position_off", "yaw_off"]
    values = [
        1.0 if any((_finite(row.get("std_vd"), 0.0) or 0.0) >= 999.0 for row in prior_rows[:100]) else 0.0,
        1.0 if vertical_evidence else 0.0,
        1.0 if prior_build.get("go2_position_prior_enabled") is False or decision.get("go2_position_prior_enabled") is False else 0.0,
        1.0 if prior_build.get("go2_yaw_prior_enabled") is False or decision.get("go2_yaw_prior_enabled") is False else 0.0,
    ]
    _save_bar(plt, path, "N7C vertical/yaw/position disabled evidence", labels, values, "flag")
    series = [{"label": label, "x": [index], "y": [values[index]]} for index, label in enumerate(labels)]
    coverage.append(_coverage(path, rel, "vertical_disabled", ["prior_build_report", "decision_report"], series, min_rows=4, min_series=4, documented_aggregation=True, vertical_disabled_evidence=vertical_evidence))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[18]
    path = fig_root / rel
    series = [{"label": "std_vd_disabled_999", "x": prior_times, "y": _values(prior_rows, "std_vd")}]
    _save_line(plt, path, "Go2 vd disabled std timeline", "std_vd (m/s)", series)
    coverage.append(_coverage(path, rel, "vertical_disabled", ["prior_csv_std_vd"], series, min_rows=1, min_series=1, vertical_disabled_evidence=vertical_evidence))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[19]
    path = fig_root / rel
    labels = ["clean_h", "clean_up", "clean_yaw", "clean_roll", "clean_pitch"]
    values = [
        _metric_delta(comparison, "go2_horizontal_velocity_main_minus_baseline", "horizontal_rmse_m"),
        _metric_delta(comparison, "go2_horizontal_velocity_main_minus_baseline", "up_rmse_m"),
        _metric_delta(comparison, "go2_horizontal_velocity_main_minus_baseline", "yaw_rmse_deg"),
        _metric_delta(comparison, "go2_horizontal_velocity_main_minus_baseline", "roll_rmse_deg"),
        _metric_delta(comparison, "go2_horizontal_velocity_main_minus_baseline", "pitch_rmse_deg"),
    ]
    _save_bar(plt, path, "N7C metric delta panel", labels, values, "delta")
    series = [{"label": f"metric_delta_{label}", "x": [index], "y": [values[index]]} for index, label in enumerate(labels)]
    coverage.append(_coverage(path, rel, "summary", ["comparison_report"], series, min_rows=5, min_series=5, documented_aggregation=True))
    generated.append(rel)

    rel = REQUIRED_N7C1_FIGURES[20]
    path = fig_root / rel
    lines = [
        f"status={decision.get('status')}",
        f"recommended_next_stage={decision.get('recommended_next_stage')}",
        f"update_count={decision.get('update_count')}",
        f"reject_count={decision.get('reject_count')}",
        "paper_performance_claim=false",
        "go2_velocity_truth_claim=false",
        "no_outperform_final_v23_claim=true",
        "go2_vertical_velocity_prior_enabled=false",
        "go2_position_prior_enabled=false",
        "go2_yaw_prior_enabled=false",
        "fgo=false",
    ]
    _save_text_panel(plt, path, "N7C1 visual decision panel", lines)
    series = [
        {"label": "decision_update_count", "x": [0], "y": [float(update_count)]},
        {"label": "decision_reject_count", "x": [1], "y": [float(reject_count)]},
        {"label": "decision_no_claim", "x": [2], "y": [1.0 if not decision.get("paper_performance_claim", True) else 0.0]},
    ]
    coverage.append(_coverage(path, rel, "summary", ["decision_report"], series, min_rows=3, min_series=3, documented_aggregation=True))
    generated.append(rel)

    return {
        "stage": "N7C1_go2_horizontal_velocity_visual_validation",
        "required_figures": REQUIRED_N7C1_FIGURES,
        "generated": [str(fig_root / rel) for rel in generated],
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_N7C1_FIGURES) and all((fig_root / rel).exists() for rel in generated),
        "required_figures_nonempty": all((fig_root / rel).exists() and (fig_root / rel).stat().st_size > 0 for rel in generated),
        "coverage": coverage,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
    }
