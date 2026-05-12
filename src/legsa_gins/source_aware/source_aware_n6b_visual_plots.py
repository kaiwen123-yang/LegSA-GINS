"""Figure generation for N6B1 source-aware visual validation.

中文说明：所有图片都是 runtime-only 的诊断图；N6B1 不改 solver、不调参、
不删 epoch，也不把图像结果回灌到滤波器。
"""

from __future__ import annotations

import math
from pathlib import Path
from statistics import median
from typing import Any

from legsa_gins.source_aware.source_aware_n6b_plot_coverage import (
    N6B1FigureCoverage,
    inspect_n6b1_plot_source_data,
)


REQUIRED_N6B1_FIGURES = [
    "01_clean_validation/clean_horizontal_error_no_sourceaware_vs_n6b.png",
    "01_clean_validation/clean_up_error_no_sourceaware_vs_n6b.png",
    "01_clean_validation/clean_yaw_error_no_sourceaware_vs_n6b.png",
    "01_clean_validation/clean_roll_pitch_error_no_sourceaware_vs_n6b.png",
    "01_clean_validation/clean_delta_n6b_minus_no_sourceaware_time.png",
    "02_weight_traces/n6b_R_scale_by_source_time.png",
    "02_weight_traces/n6b_R_scale_hist_by_source.png",
    "02_weight_traces/n6b_oim_normalized_innovation_by_source.png",
    "02_weight_traces/n6b_lsim_score_by_source.png",
    "02_weight_traces/n6b_combined_scale_p95_by_source.png",
    "03_spike_response/raw_doppler_spike_response_zoom_96_97s.png",
    "03_spike_response/raw_doppler_residual_and_R_scale_spike_zoom.png",
    "03_spike_response/raw_doppler_spike_response_table.png",
    "04_stress_validation/stress_disabled_no_sourceaware_vs_n6b.png",
    "04_stress_validation/stress_std_scale5_no_sourceaware_vs_n6b.png",
    "04_stress_validation/stress_outage30_no_sourceaware_vs_n6b.png",
    "04_stress_validation/stress_noise0p5_no_sourceaware_vs_n6b.png",
    "04_stress_validation/stress_delta_summary_bar.png",
    "05_policy_diagnostics/n6a_vs_n6b_R_scale_hist.png",
    "05_policy_diagnostics/n6a_vs_n6b_clean_metric_delta.png",
    "05_policy_diagnostics/n6b_policy_deadband_diagnostic.png",
    "06_summary/n6b_visual_decision_panel.png",
    "06_summary/n6b_metric_summary_panel.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _axis(plt, figsize: tuple[float, float] = (9.2, 5.1)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


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
    return [(_finite(row.get(key), first) or first) - first for row in rows]


def _values(rows: list[dict[str, Any]], key: str, *, abs_value: bool = False) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _finite(row.get(key))
        if value is not None:
            values.append(abs(value) if abs_value else value)
    return values


def _trace_times(rows: list[dict[str, Any]]) -> list[float]:
    if not rows:
        return []
    first = _finite(rows[0].get("time"), 0.0) or 0.0
    return [(_finite(row.get("time"), first) or first) - first for row in rows]


def _trace_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [value for value in (_finite(row.get(key)) for row in rows) if value is not None]


def _source_ids(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("source_id", "")) for row in rows if row.get("source_id")})


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * q)]


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
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_hist(plt, path: Path, title: str, xlabel: str, series: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for row in series:
        ys = list(row.get("y", []))
        if ys:
            ax.hist(ys, bins=32, alpha=0.42, label=str(row.get("label", "series")))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar(plt, path: Path, title: str, labels: list[str], values: list[float], ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.bar(range(len(labels)), values, color="#4c78a8")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=24, ha="right", fontsize=8)
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
    ax.text(0.02, 0.94, "\n".join(lines), va="top", ha="left", fontsize=9, family="monospace")
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _coverage(path: Path, rel: str, category: str, roles: list[str], series: list[dict[str, Any]], **extra: Any) -> N6B1FigureCoverage:
    source = {
        "figure_path": str(path),
        "mandatory": True,
        "figure_category": category,
        "source_data_roles": roles,
        "series": series,
    }
    source.update(extra)
    return inspect_n6b1_plot_source_data(rel, source)


def _diff_series(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], key: str, label: str) -> dict[str, Any]:
    count = min(len(rows_a), len(rows_b))
    x = _times(rows_a[:count])
    y = [(_finite(rows_b[i].get(key), 0.0) or 0.0) - (_finite(rows_a[i].get(key), 0.0) or 0.0) for i in range(count)]
    return {"label": label, "x": x, "y": y}


def _metric(report: dict[str, Any], key: str) -> float:
    value = report.get(key)
    return float(value) if isinstance(value, (int, float)) else 0.0


def generate_n6b1_visual_figures(
    *,
    visual_inputs: dict[str, Any],
    figure_output_dir: str | Path,
) -> dict[str, Any]:
    plt = _load_matplotlib()
    fig_root = Path(figure_output_dir)
    coverage: list[N6B1FigureCoverage] = []
    generated: list[str] = []
    clean = visual_inputs["clean_errors"]
    stress = visual_inputs["stress_errors"]
    reports = visual_inputs["reports"]
    n6b_trace = visual_inputs["n6b_trace"]
    n6a_trace = visual_inputs["n6a_trace"]
    baseline = clean.get("baseline_plus_raw_no_sourceaware", [])
    n6b = clean.get("n6b_lsim_oim", [])

    clean_specs = [
        (REQUIRED_N6B1_FIGURES[0], "horizontal_error_m", "m", "Clean horizontal error"),
        (REQUIRED_N6B1_FIGURES[1], "up_error_m", "m", "Clean up error"),
        (REQUIRED_N6B1_FIGURES[2], "yaw_error_deg", "deg", "Clean yaw error"),
    ]
    for rel, key, ylabel, title in clean_specs:
        path = fig_root / rel
        series = [
            {"label": "no_sourceaware", "x": _times(baseline), "y": _values(baseline, key, abs_value=True)},
            {"label": "n6b_lsim_oim", "x": _times(n6b), "y": _values(n6b, key, abs_value=True)},
        ]
        _save_line(plt, path, f"N6B1 {title} (diagnostic only)", ylabel, series)
        coverage.append(_coverage(path, rel, "clean", ["no_sourceaware_eval_nav", "n6b_eval_nav"], series, min_rows=1000, min_series=2, min_x_range=200.0))
        generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[3]
    path = fig_root / rel
    series = [
        {"label": "no_sourceaware_roll", "x": _times(baseline), "y": _values(baseline, "roll_error_deg", abs_value=True)},
        {"label": "n6b_roll", "x": _times(n6b), "y": _values(n6b, "roll_error_deg", abs_value=True)},
        {"label": "no_sourceaware_pitch", "x": _times(baseline), "y": _values(baseline, "pitch_error_deg", abs_value=True)},
        {"label": "n6b_pitch", "x": _times(n6b), "y": _values(n6b, "pitch_error_deg", abs_value=True)},
    ]
    _save_line(plt, path, "N6B1 clean roll/pitch error (diagnostic only)", "deg", series)
    coverage.append(_coverage(path, rel, "clean", ["no_sourceaware_eval_nav", "n6b_eval_nav"], series, min_rows=1000, min_series=4, min_x_range=200.0))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[4]
    path = fig_root / rel
    series = [
        _diff_series(baseline, n6b, "horizontal_error_m", "n6b_minus_no_sourceaware_horizontal"),
        _diff_series(baseline, n6b, "yaw_error_deg", "n6b_minus_no_sourceaware_yaw"),
    ]
    _save_line(plt, path, "N6B1 clean delta over time (diagnostic only)", "delta", series)
    coverage.append(_coverage(path, rel, "clean", ["clean_delta"], series, min_rows=1000, min_series=2, min_x_range=200.0))
    generated.append(rel)

    source_ids = _source_ids(n6b_trace)
    rel = REQUIRED_N6B1_FIGURES[5]
    path = fig_root / rel
    series = []
    for source_id in source_ids:
        rows = [row for row in n6b_trace if row.get("source_id") == source_id]
        series.append({"label": source_id, "x": _trace_times(rows), "y": _trace_values(rows, "combined_R_scale")})
    _save_line(plt, path, "N6B R scale by source", "R scale", series)
    coverage.append(_coverage(path, rel, "weight_trace", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], series, min_rows=1000, min_series=4, source_ids=source_ids))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[6]
    path = fig_root / rel
    hist_series = []
    for source_id in source_ids:
        rows = [row for row in n6b_trace if row.get("source_id") == source_id]
        hist_series.append({"label": source_id, "x": list(range(len(rows))), "y": _trace_values(rows, "combined_R_scale")})
    _save_hist(plt, path, "N6B R scale histogram by source", "R scale", hist_series)
    coverage.append(_coverage(path, rel, "weight_trace", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], hist_series, min_rows=1000, min_series=4, source_ids=source_ids))
    generated.append(rel)

    for rel, key, title in [
        (REQUIRED_N6B1_FIGURES[7], "normalized_innovation", "N6B OIM normalized innovation by source"),
        (REQUIRED_N6B1_FIGURES[8], "lsim_score", "N6B LSIM score by source"),
    ]:
        path = fig_root / rel
        series = []
        for source_id in source_ids:
            rows = [row for row in n6b_trace if row.get("source_id") == source_id]
            series.append({"label": source_id, "x": _trace_times(rows), "y": _trace_values(rows, key)})
        _save_line(plt, path, title, key, series)
        coverage.append(_coverage(path, rel, "weight_trace", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], series, min_rows=1000, min_series=4, source_ids=source_ids))
        generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[9]
    path = fig_root / rel
    labels = source_ids
    values = [_percentile(_trace_values([row for row in n6b_trace if row.get("source_id") == source_id], "combined_R_scale"), 0.95) for source_id in labels]
    _save_bar(plt, path, "N6B combined R scale p95 by source", labels, values, "p95 R scale")
    bar_series = [{"label": label, "x": [index], "y": [values[index]]} for index, label in enumerate(labels)]
    coverage.append(_coverage(path, rel, "weight_trace", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], bar_series, min_rows=4, min_series=4, source_ids=source_ids))
    generated.append(rel)

    spike_report = reports["N6B_SPIKE_RESPONSE_REPORT.json"]
    spike_times = [float(row.get("spike_time")) for row in spike_report.get("responses", []) if row.get("spike_time") is not None]
    raw_rows = [row for row in n6b_trace if row.get("source_id") == "raw_doppler_velocity"]
    zoom_rows = [
        row
        for row in raw_rows
        if spike_times and min(abs((_finite(row.get("time"), 0.0) or 0.0) - spike_time) for spike_time in spike_times) <= 1.5
    ] or raw_rows[:50]
    rel = REQUIRED_N6B1_FIGURES[10]
    path = fig_root / rel
    series = [
        {"label": "raw_doppler_scale", "x": _trace_times(zoom_rows), "y": _trace_values(zoom_rows, "combined_R_scale")},
        {"label": "raw_doppler_residual", "x": _trace_times(zoom_rows), "y": _trace_values(zoom_rows, "residual_norm")},
    ]
    _save_line(plt, path, "Raw Doppler spike response zoom around 96-97s", "scale / residual", series)
    coverage.append(_coverage(path, rel, "spike_zoom", ["SOURCE_AWARE_WEIGHT_TRACE.csv", "N6B_SPIKE_RESPONSE_REPORT.json"], series, min_rows=2, min_series=2))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[11]
    path = fig_root / rel
    series = [
        {"label": "raw_doppler_scale", "x": _trace_times(zoom_rows), "y": _trace_values(zoom_rows, "combined_R_scale")},
        {"label": "raw_doppler_normalized_innovation", "x": _trace_times(zoom_rows), "y": _trace_values(zoom_rows, "normalized_innovation")},
        {"label": "raw_doppler_residual", "x": _trace_times(zoom_rows), "y": _trace_values(zoom_rows, "residual_norm")},
    ]
    _save_line(plt, path, "Raw Doppler residual and R scale spike zoom", "diagnostic value", series)
    coverage.append(_coverage(path, rel, "spike_zoom", ["SOURCE_AWARE_WEIGHT_TRACE.csv", "N6B_SPIKE_RESPONSE_REPORT.json"], series, min_rows=2, min_series=2))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[12]
    path = fig_root / rel
    table_lines = [
        f"spike_time={row.get('spike_time')} nearest={row.get('nearest_time')} scale={row.get('raw_doppler_combined_R_scale')} norm={row.get('oim_normalized_at_spike')}"
        for row in spike_report.get("responses", [])
    ]
    _save_text_panel(plt, path, "N6B raw Doppler spike response table", table_lines or ["evidence_missing"])
    table_series = [
        {"label": "raw_doppler_scale", "x": [index], "y": [_finite(row.get("raw_doppler_combined_R_scale"), 0.0) or 0.0]}
        for index, row in enumerate(spike_report.get("responses", []))
    ] + [
        {"label": "raw_doppler_residual", "x": [index], "y": [_finite(row.get("oim_normalized_at_spike"), 0.0) or 0.0]}
        for index, row in enumerate(spike_report.get("responses", []))
    ]
    coverage.append(_coverage(path, rel, "spike_zoom", ["N6B_SPIKE_RESPONSE_REPORT.json"], table_series, min_rows=2, min_series=2))
    generated.append(rel)

    stress_order = [
        ("stress_disabled", REQUIRED_N6B1_FIGURES[13], "receiver velocity disabled"),
        ("stress_std_scale5", REQUIRED_N6B1_FIGURES[14], "receiver velocity std scale 5"),
        ("stress_outage30", REQUIRED_N6B1_FIGURES[15], "receiver velocity outage 30s"),
        ("stress_noise0p5", REQUIRED_N6B1_FIGURES[16], "receiver velocity noise 0.5"),
    ]
    for label, rel, title in stress_order:
        path = fig_root / rel
        pair = stress[label]
        series = [
            {"label": f"{label}_no_sourceaware", "x": _times(pair["no_sourceaware"]), "y": _values(pair["no_sourceaware"], "horizontal_error_m", abs_value=True)},
            {"label": f"{label}_n6b", "x": _times(pair["n6b"]), "y": _values(pair["n6b"], "horizontal_error_m", abs_value=True)},
        ]
        _save_line(plt, path, f"N6B stress validation: {title}", "horizontal error (m)", series)
        coverage.append(_coverage(path, rel, "stress", ["stress_eval_nav"], series, min_rows=1000, min_series=2, min_x_range=200.0))
        generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[17]
    path = fig_root / rel
    comparisons = reports["N6B_SOURCE_AWARE_COMPARISON_REPORT.json"].get("comparisons", {})
    labels = ["disabled", "std5", "outage30", "noise0p5"]
    comp_keys = [
        "receiver_velocity_disabled_n6b_lsim_oim_minus_no_sourceaware",
        "receiver_velocity_std_scale_5_n6b_lsim_oim_minus_no_sourceaware",
        "receiver_velocity_outage_30s_n6b_lsim_oim_minus_no_sourceaware",
        "receiver_velocity_noise_0p5_n6b_lsim_oim_minus_no_sourceaware",
    ]
    values = [float(comparisons.get(key, {}).get("delta", {}).get("horizontal_rmse_m") or 0.0) for key in comp_keys]
    _save_bar(plt, path, "N6B stress horizontal delta summary", labels, values, "delta horizontal RMSE")
    coverage.append(_coverage(path, rel, "stress", ["N6B_SOURCE_AWARE_COMPARISON_REPORT.json"], [{"label": f"{labels[i]}_no_sourceaware_n6b", "x": [i], "y": [values[i]]} for i in range(len(values))], min_rows=4, min_series=4))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[18]
    path = fig_root / rel
    hist_series = [
        {"label": "n6a_original_policy", "x": list(range(len(n6a_trace))), "y": _trace_values(n6a_trace, "combined_R_scale")},
        {"label": "n6b_conservative_policy", "x": list(range(len(n6b_trace))), "y": _trace_values(n6b_trace, "combined_R_scale")},
    ]
    _save_hist(plt, path, "N6A vs N6B R scale histogram", "R scale", hist_series)
    coverage.append(_coverage(path, rel, "policy", ["N6A trace", "N6B trace"], hist_series, min_rows=1000, min_series=2))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[19]
    path = fig_root / rel
    delta = comparisons.get("n6b_lsim_oim_minus_n6a_original_policy", {}).get("delta", {})
    labels = ["H", "Up", "Yaw", "Roll", "Pitch"]
    values = [
        float(delta.get("horizontal_rmse_m") or 0.0),
        float(delta.get("up_rmse_m") or 0.0),
        float(delta.get("yaw_rmse_deg") or 0.0),
        float(delta.get("roll_rmse_deg") or 0.0),
        float(delta.get("pitch_rmse_deg") or 0.0),
    ]
    _save_bar(plt, path, "N6B minus N6A clean metric delta", labels, values, "delta")
    coverage.append(_coverage(path, rel, "policy", ["N6B_SOURCE_AWARE_COMPARISON_REPORT.json"], [{"label": labels[i], "x": [i], "y": [values[i]]} for i in range(len(values))], min_rows=5, min_series=5))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[20]
    path = fig_root / rel
    series = [
        {"label": "normalized_innovation", "x": _trace_times(n6b_trace), "y": _trace_values(n6b_trace, "normalized_innovation")},
        {"label": "combined_R_scale", "x": _trace_times(n6b_trace), "y": _trace_values(n6b_trace, "combined_R_scale")},
    ]
    _save_line(plt, path, "N6B policy deadband diagnostic", "diagnostic value", series)
    coverage.append(_coverage(path, rel, "policy", ["SOURCE_AWARE_WEIGHT_TRACE.csv"], series, min_rows=1000, min_series=2, min_x_range=200.0))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[21]
    path = fig_root / rel
    diagnostics = reports["N6B_SOURCE_AWARE_POLICY_DIAGNOSTICS.json"]
    lines = [
        f"clean_neutrality_gate={diagnostics.get('clean_neutrality_gate', {}).get('pass')}",
        f"R_scale_gate={diagnostics.get('R_scale_gate', {}).get('pass')}",
        f"spike_response_status={diagnostics.get('spike_response_status')}",
        "paper_performance_claim=false",
        "trace_solver_input=false",
    ]
    _save_text_panel(plt, path, "N6B visual decision panel", lines)
    panel_series = [
        {"label": "clean_gate", "x": [0], "y": [1.0 if diagnostics.get("clean_neutrality_gate", {}).get("pass") else 0.0]},
        {"label": "R_scale_gate", "x": [1], "y": [1.0 if diagnostics.get("R_scale_gate", {}).get("pass") else 0.0]},
    ]
    coverage.append(_coverage(path, rel, "summary", ["N6B_SOURCE_AWARE_POLICY_DIAGNOSTICS.json"], panel_series, min_rows=2, min_series=2))
    generated.append(rel)

    rel = REQUIRED_N6B1_FIGURES[22]
    path = fig_root / rel
    no_summary = reports["N6B_SOURCE_AWARE_COMPARISON_REPORT.json"].get("baseline_plus_raw_no_sourceaware", {})
    n6b_summary = reports["N6B_SOURCE_AWARE_COMPARISON_REPORT.json"].get("n6b_lsim_oim", {})
    labels = ["no_H", "n6b_H", "no_Up", "n6b_Up", "no_Yaw", "n6b_Yaw"]
    values = [
        _metric(no_summary, "horizontal_rmse_m"),
        _metric(n6b_summary, "horizontal_rmse_m"),
        _metric(no_summary, "up_rmse_m"),
        _metric(n6b_summary, "up_rmse_m"),
        _metric(no_summary, "yaw_rmse_deg"),
        _metric(n6b_summary, "yaw_rmse_deg"),
    ]
    _save_bar(plt, path, "N6B metric summary panel", labels, values, "metric value")
    coverage.append(_coverage(path, rel, "summary", ["N6B_SOURCE_AWARE_COMPARISON_REPORT.json"], [{"label": labels[i], "x": [i], "y": [values[i]]} for i in range(len(values))], min_rows=6, min_series=6))
    generated.append(rel)

    return {
        "stage": "N6B1_source_aware_visual_validation",
        "required_figures": REQUIRED_N6B1_FIGURES,
        "figure_count_total": len(generated),
        "required_figures_generated": len(generated) == len(REQUIRED_N6B1_FIGURES),
        "required_figures_nonempty": all((fig_root / rel).exists() and (fig_root / rel).stat().st_size > 0 for rel in REQUIRED_N6B1_FIGURES),
        "figure_paths": generated,
        "coverage": coverage,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
