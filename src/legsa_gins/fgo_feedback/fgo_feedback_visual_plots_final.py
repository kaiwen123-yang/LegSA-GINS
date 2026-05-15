"""Final N8H feedback visual plots and plot-data coverage.

中文说明：图像只写运行期目录，并同步生成 plotted-data coverage。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import (
    BASELINE_VARIANT,
    DIAGNOSTIC_PVA_VARIANT,
    N8G_VARIANT_ORDER,
    N8HVisualInputs,
    PRIMARY_FEEDBACK_VARIANT,
    REJECT_ALL_VARIANT,
    safe_float,
    write_json,
)


REQUIRED_N8H_FIGURES = [
    ("01_feedback_timeline", "feedback_window_timeline.png"),
    ("01_feedback_timeline", "feedback_accept_reject_timeline.png"),
    ("01_feedback_timeline", "feedback_variant_update_count_bar.png"),
    ("02_correction_norms", "feedback_position_correction_norm_by_variant.png"),
    ("02_correction_norms", "feedback_velocity_correction_norm_by_variant.png"),
    ("02_correction_norms", "feedback_attitude_correction_norm_by_variant.png"),
    ("02_correction_norms", "feedback_top_correction_epochs.png"),
    ("03_baseline_vs_feedback", "baseline_vs_feedback_horizontal_trajectory.png"),
    ("03_baseline_vs_feedback", "baseline_vs_feedback_horizontal_error.png"),
    ("03_baseline_vs_feedback", "baseline_vs_feedback_yaw_error.png"),
    ("03_baseline_vs_feedback", "baseline_vs_feedback_roll_pitch_error.png"),
    ("03_baseline_vs_feedback", "feedback_minus_baseline_delta_time.png"),
    ("04_gate_and_covariance", "feedback_covariance_std_time.png"),
    ("04_gate_and_covariance", "feedback_gate_threshold_panel.png"),
    ("04_gate_and_covariance", "feedback_reject_reason_panel.png"),
    ("05_variant_ablation", "feedback_variant_metric_delta_bar.png"),
    ("05_variant_ablation", "feedback_variant_gross_degradation_panel.png"),
    ("05_variant_ablation", "reject_all_sanity_vs_baseline.png"),
    ("05_variant_ablation", "diagnostic_pva_vs_primary_feedback.png"),
    ("06_summary", "position_disabled_audit_panel.png"),
    ("06_summary", "n8h_decision_panel.png"),
]


def generate_n8h_figures(
    *,
    bundle: N8HVisualInputs,
    position_audit: dict[str, Any],
    variant_review: dict[str, Any],
    gate_review: dict[str, Any],
    correction_review: dict[str, Any],
    semantic_guard: dict[str, Any],
    decision_report: dict[str, Any],
    figure_output_dir: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    coverage: list[dict[str, Any]] = []

    window = bundle.reports.get("SLIDING_WINDOW_MANAGER_REPORT.json", {})
    feedback_times = [safe_float(value) for value in window.get("feedback_time", [])]
    window_start = [safe_float(value) for value in window.get("window_start", [])]
    window_end = [safe_float(value) for value in window.get("window_end", [])]
    primary_trace = bundle.update_trace_by_variant.get(PRIMARY_FEEDBACK_VARIANT, [])
    primary_obs = bundle.observations_by_variant.get(PRIMARY_FEEDBACK_VARIANT, [])
    baseline_nav = bundle.eval_nav_by_variant.get(BASELINE_VARIANT, [])
    primary_nav = bundle.eval_nav_by_variant.get(PRIMARY_FEEDBACK_VARIANT, [])
    reject_nav = bundle.eval_nav_by_variant.get(REJECT_ALL_VARIANT, [])
    pva_nav = bundle.eval_nav_by_variant.get(DIAGNOSTIC_PVA_VARIANT, [])

    coverage.append(
        _line_plot(
            plt,
            out,
            "01_feedback_timeline",
            "feedback_window_timeline.png",
            "Feedback window timeline",
            "feedback time (s)",
            "window time (s)",
            [
                ("window start", feedback_times, window_start),
                ("window end", feedback_times, window_end),
            ],
            expected_min_series=2,
        )
    )
    accepted = [safe_float(row.get("accepted")) for row in primary_trace]
    rejected = [1.0 - value for value in accepted]
    update_time = [safe_float(row.get("update_time", row.get("observation_time"))) for row in primary_trace]
    coverage.append(
        _line_plot(
            plt,
            out,
            "01_feedback_timeline",
            "feedback_accept_reject_timeline.png",
            "Feedback accept and reject timeline",
            "time (s)",
            "gate state (0/1)",
            [("accepted", update_time, accepted), ("rejected", update_time, rejected)],
            expected_min_series=2,
        )
    )
    variant_entries = variant_review.get("variants", [])
    labels = [item["variant_id"].replace("fgo_feedback_", "").replace("ekf_", "") for item in variant_entries]
    update_counts = [safe_float(item.get("feedback_update_count")) for item in variant_entries]
    coverage.append(
        _bar_plot(
            plt,
            out,
            "01_feedback_timeline",
            "feedback_variant_update_count_bar.png",
            "Feedback updates by variant",
            "variant",
            "update count",
            labels,
            [("updates", update_counts)],
        )
    )

    for filename, block, ylabel in [
        ("feedback_position_correction_norm_by_variant.png", "position_m", "position correction norm (m)"),
        ("feedback_velocity_correction_norm_by_variant.png", "velocity_mps", "velocity correction norm (m/s)"),
        ("feedback_attitude_correction_norm_by_variant.png", "attitude_deg", "attitude correction norm (deg)"),
    ]:
        p95 = [safe_float(item.get("correction_norm_stats", {}).get(block, {}).get("p95")) for item in variant_entries]
        max_values = [safe_float(item.get("correction_norm_stats", {}).get(block, {}).get("max")) for item in variant_entries]
        coverage.append(
            _bar_plot(
                plt,
                out,
                "02_correction_norms",
                filename,
                filename.replace("_", " ").replace(".png", ""),
                "variant",
                ylabel,
                labels,
                [("p95", p95), ("max", max_values)],
                expected_min_series=2,
            )
        )

    top_epochs = correction_review.get("top_correction_epochs", [])
    top_labels = [f"{item.get('variant_id', '')[:10]}@{safe_float(item.get('time')):.1f}" for item in top_epochs]
    top_values = [safe_float(item.get("attitude_norm_deg")) for item in top_epochs]
    coverage.append(
        _bar_plot(
            plt,
            out,
            "02_correction_norms",
            "feedback_top_correction_epochs.png",
            "Top correction epochs",
            "epoch",
            "attitude correction norm (deg)",
            top_labels,
            [("attitude", top_values)],
        )
    )

    base_ne = _ned_xy(baseline_nav)
    primary_ne = _ned_xy(primary_nav, origin_rows=baseline_nav)
    coverage.append(
        _line_plot(
            plt,
            out,
            "03_baseline_vs_feedback",
            "baseline_vs_feedback_horizontal_trajectory.png",
            "Baseline vs feedback horizontal trajectory",
            "east (m)",
            "north (m)",
            [
                ("baseline", _downsample(base_ne[1]), _downsample(base_ne[0])),
                ("primary feedback", _downsample(primary_ne[1]), _downsample(primary_ne[0])),
            ],
            expected_min_series=2,
        )
    )
    delta = _nav_delta_series(baseline_nav, primary_nav)
    coverage.extend(
        [
            _line_plot(
                plt,
                out,
                "03_baseline_vs_feedback",
                "baseline_vs_feedback_horizontal_error.png",
                "Primary feedback minus baseline horizontal delta",
                "time (s)",
                "horizontal delta (m)",
                [("primary feedback", _downsample(delta["time"]), _downsample(delta["horizontal_m"]))],
            ),
            _line_plot(
                plt,
                out,
                "03_baseline_vs_feedback",
                "baseline_vs_feedback_yaw_error.png",
                "Primary feedback minus baseline yaw delta",
                "time (s)",
                "yaw delta (deg)",
                [("primary feedback", _downsample(delta["time"]), _downsample(delta["yaw_deg"]))],
            ),
            _line_plot(
                plt,
                out,
                "03_baseline_vs_feedback",
                "baseline_vs_feedback_roll_pitch_error.png",
                "Primary feedback minus baseline roll/pitch delta",
                "time (s)",
                "roll/pitch delta (deg)",
                [("primary feedback", _downsample(delta["time"]), _downsample(delta["roll_pitch_deg"]))],
            ),
            _line_plot(
                plt,
                out,
                "03_baseline_vs_feedback",
                "feedback_minus_baseline_delta_time.png",
                "Feedback minus baseline deltas",
                "time (s)",
                "delta value",
                [
                    ("horizontal m", _downsample(delta["time"]), _downsample(delta["horizontal_m"])),
                    ("yaw deg", _downsample(delta["time"]), _downsample(delta["yaw_deg"])),
                    ("roll/pitch deg", _downsample(delta["time"]), _downsample(delta["roll_pitch_deg"])),
                ],
                expected_min_series=3,
            ),
        ]
    )

    obs_time = [safe_float(row.get("time")) for row in primary_obs]
    coverage.append(
        _line_plot(
            plt,
            out,
            "04_gate_and_covariance",
            "feedback_covariance_std_time.png",
            "Feedback covariance std over time",
            "time (s)",
            "std (mixed units)",
            [
                ("std_vN m/s", obs_time, [safe_float(row.get("std_vN")) for row in primary_obs]),
                ("std_vE m/s", obs_time, [safe_float(row.get("std_vE")) for row in primary_obs]),
                ("std_roll deg", obs_time, [safe_float(row.get("std_roll")) for row in primary_obs]),
                ("std_yaw deg", obs_time, [safe_float(row.get("std_yaw")) for row in primary_obs]),
            ],
            expected_min_series=4,
        )
    )
    thresholds = gate_review.get("gate_thresholds", {})
    gate_stats = gate_review.get("correction_norm_stats", {})
    gate_labels = ["velocity", "attitude", "yaw"]
    observed = [
        safe_float(gate_stats.get("velocity_mps", {}).get("max")),
        safe_float(gate_stats.get("attitude_deg", {}).get("max")),
        max([abs(safe_float(row.get("yaw_residual_deg"))) for row in primary_trace] or [0.0]),
    ]
    caps = [
        safe_float(thresholds.get("max_velocity_correction_mps")),
        safe_float(thresholds.get("max_attitude_correction_deg")),
        safe_float(thresholds.get("max_yaw_correction_deg")),
    ]
    coverage.append(
        _bar_plot(
            plt,
            out,
            "04_gate_and_covariance",
            "feedback_gate_threshold_panel.png",
            "Gate observed max vs threshold",
            "state block",
            "norm (block units)",
            gate_labels,
            [("observed max", observed), ("threshold", caps)],
            expected_min_series=2,
        )
    )
    reasons = gate_review.get("reject_reasons", {}) or {"none": 0}
    coverage.append(
        _bar_plot(
            plt,
            out,
            "04_gate_and_covariance",
            "feedback_reject_reason_panel.png",
            "Feedback reject reasons",
            "reason",
            "count",
            list(reasons.keys()),
            [("count", [safe_float(value) for value in reasons.values()])],
        )
    )

    horizontal_p95 = [safe_float(item.get("baseline_delta", {}).get("horizontal_m", {}).get("p95")) for item in variant_entries]
    yaw_p95 = [safe_float(item.get("baseline_delta", {}).get("yaw_deg", {}).get("p95")) for item in variant_entries]
    roll_pitch_p95 = [safe_float(item.get("baseline_delta", {}).get("roll_pitch_deg", {}).get("p95")) for item in variant_entries]
    coverage.append(
        _bar_plot(
            plt,
            out,
            "05_variant_ablation",
            "feedback_variant_metric_delta_bar.png",
            "Variant metric deltas vs baseline",
            "variant",
            "p95 delta",
            labels,
            [("horizontal m", horizontal_p95), ("yaw deg", yaw_p95), ("roll/pitch deg", roll_pitch_p95)],
            expected_min_series=3,
        )
    )
    gross = [1.0 if item.get("gross_degradation") else 0.0 for item in variant_entries]
    coverage.append(
        _bar_plot(
            plt,
            out,
            "05_variant_ablation",
            "feedback_variant_gross_degradation_panel.png",
            "Gross degradation by variant",
            "variant",
            "gross degradation flag",
            labels,
            [("flag", gross)],
        )
    )
    reject_delta = _nav_delta_series(baseline_nav, reject_nav)
    coverage.append(
        _line_plot(
            plt,
            out,
            "05_variant_ablation",
            "reject_all_sanity_vs_baseline.png",
            "Reject-all sanity vs baseline",
            "time (s)",
            "horizontal delta (m)",
            [("reject-all", _downsample(reject_delta["time"]), _downsample(reject_delta["horizontal_m"]))],
        )
    )
    pva_delta = _nav_delta_series(primary_nav, pva_nav)
    coverage.append(
        _line_plot(
            plt,
            out,
            "05_variant_ablation",
            "diagnostic_pva_vs_primary_feedback.png",
            "Diagnostic PVA minus primary feedback",
            "time (s)",
            "horizontal delta (m)",
            [("diagnostic PVA", _downsample(pva_delta["time"]), _downsample(pva_delta["horizontal_m"]))],
        )
    )
    coverage.append(
        _bar_plot(
            plt,
            out,
            "06_summary",
            "position_disabled_audit_panel.png",
            "Position-disabled audit",
            "source",
            "position correction max (m)",
            ["primary applied", "primary residual proxy", "diagnostic PVA applied", "aggregate applied"],
            [
                (
                    "max",
                    [
                        safe_float(position_audit.get("primary_position_correction_applied_stats_m", {}).get("max")),
                        safe_float(position_audit.get("primary_position_residual_proxy_stats_m", {}).get("max")),
                        safe_float(position_audit.get("diagnostic_pva_position_correction_applied_stats_m", {}).get("max")),
                        safe_float(position_audit.get("all_variant_aggregate_position_correction_applied_stats_m", {}).get("max")),
                    ],
                )
            ],
        )
    )
    decision_flags = [
        1.0 if decision_report.get("status") == "fgo_feedback_visual_validation_passed" else 0.0,
        1.0 if semantic_guard.get("status") == "plot_semantics_passed" else 0.0,
        1.0 if variant_review.get("reject_all_sanity_passed") else 0.0,
        1.0 if gate_review.get("classification") == "gate_reasonable" else 0.0,
    ]
    coverage.append(
        _bar_plot(
            plt,
            out,
            "06_summary",
            "n8h_decision_panel.png",
            "N8H visual decision",
            "decision component",
            "pass flag (0/1)",
            ["visual", "semantics", "reject-all", "gate"],
            [("pass", decision_flags)],
        )
    )

    manifest = _figure_manifest(out, coverage)
    coverage_report = {
        "stage": "N8H",
        "required_figure_count": len(REQUIRED_N8H_FIGURES),
        "figure_count_total": len(coverage),
        "all_required_figures_present": manifest["all_required_figures_present"],
        "all_required_figures_nonempty": manifest["all_required_figures_nonempty"],
        "figures": coverage,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    write_json(out / "N8H_FIGURE_MANIFEST.json", manifest)
    return manifest, coverage_report


def _line_plot(
    plt: Any,
    root: Path,
    category: str,
    filename: str,
    title: str,
    xlabel: str,
    ylabel: str,
    series: list[tuple[str, list[float], list[float]]],
    *,
    expected_min_series: int = 1,
) -> dict[str, Any]:
    path = root / category / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=130)
    plotted = 0
    all_x: list[float] = []
    all_y: list[float] = []
    monotonic_checks: list[bool] = []
    for label, x_values, y_values in series:
        clean_x, clean_y = _paired_clean(x_values, y_values)
        if not clean_x:
            continue
        ax.plot(clean_x, clean_y, linewidth=1.2, label=label)
        plotted += 1
        all_x.extend(clean_x)
        all_y.extend(clean_y)
        monotonic_checks.append(_monotonic(clean_x))
    if plotted:
        ax.legend(loc="best", fontsize=8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    requires_time_monotonic = "time" in xlabel.lower()
    time_monotonic = all(monotonic_checks) if requires_time_monotonic else True
    return _coverage(path, category, filename, plotted, len(all_x), all_x, all_y, expected_min_series, time_monotonic=time_monotonic)


def _bar_plot(
    plt: Any,
    root: Path,
    category: str,
    filename: str,
    title: str,
    xlabel: str,
    ylabel: str,
    labels: list[str],
    series: list[tuple[str, list[float]]],
    *,
    expected_min_series: int = 1,
) -> dict[str, Any]:
    path = root / category / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=130)
    label_count = max(1, len(labels))
    x_positions = list(range(label_count))
    width = 0.8 / max(1, len(series))
    plotted = 0
    all_y: list[float] = []
    for index, (name, values) in enumerate(series):
        padded = [safe_float(value) for value in values[:label_count]]
        padded.extend(0.0 for _ in range(label_count - len(padded)))
        offsets = [pos - 0.4 + width / 2.0 + index * width for pos in x_positions]
        ax.bar(offsets, padded, width=width, label=name)
        plotted += 1
        all_y.extend(padded)
    ax.set_xticks(x_positions)
    ax.set_xticklabels([_short_label(label) for label in (labels or ["none"])], rotation=30, ha="right", fontsize=8)
    if plotted:
        ax.legend(loc="best", fontsize=8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return _coverage(path, category, filename, plotted, label_count, x_positions, all_y, expected_min_series, time_monotonic=True)


def _coverage(
    path: Path,
    category: str,
    filename: str,
    series_count: int,
    row_count: int,
    x_values: list[float],
    y_values: list[float],
    expected_min_series: int,
    *,
    time_monotonic: bool | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    nonempty = path.exists() and path.stat().st_size > 0
    if not nonempty:
        reasons.append("file_empty_or_missing")
    if series_count < expected_min_series:
        reasons.append("too_few_series")
    if row_count <= 0:
        reasons.append("no_plotted_rows")
    monotonic = _monotonic(x_values) if time_monotonic is None else time_monotonic
    if not monotonic:
        reasons.append("x_not_monotonic")
    return {
        "name": filename,
        "relative_path": f"{category}/{filename}",
        "category": category,
        "plotted_series_count": series_count,
        "row_count": row_count,
        "x_range": _range(x_values),
        "y_range": _range(y_values),
        "nonempty": nonempty,
        "time_monotonic": monotonic,
        "empty_plot_suspect": bool(reasons),
        "reason_codes": reasons,
    }


def _figure_manifest(root: Path, coverage: list[dict[str, Any]]) -> dict[str, Any]:
    by_relative = {item["relative_path"]: item for item in coverage}
    required = [f"{category}/{filename}" for category, filename in REQUIRED_N8H_FIGURES]
    missing = [relative for relative in required if relative not in by_relative or not (root / relative).exists()]
    empty = [relative for relative in required if (root / relative).exists() and (root / relative).stat().st_size <= 0]
    return {
        "stage": "N8H",
        "figure_count_total": len(coverage),
        "required_figure_count": len(required),
        "required_figures": required,
        "missing_required_figures": missing,
        "empty_required_figures": empty,
        "all_required_figures_present": not missing,
        "all_required_figures_nonempty": not missing and not empty,
        "figures": [
            {
                "name": item["name"],
                "relative_path": item["relative_path"],
                "role": "runtime_only",
                "nonempty": item["nonempty"],
            }
            for item in coverage
        ],
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _nav_delta_series(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, list[float]]:
    count = min(len(left), len(right))
    times: list[float] = []
    horizontal: list[float] = []
    yaw: list[float] = []
    roll_pitch: list[float] = []
    for lrow, rrow in zip(left[:count], right[:count]):
        times.append(safe_float(lrow.get("time")))
        dn = (safe_float(rrow.get("lat_deg")) - safe_float(lrow.get("lat_deg"))) * 111_000.0
        de = (safe_float(rrow.get("lon_deg")) - safe_float(lrow.get("lon_deg"))) * 111_000.0
        horizontal.append(math.sqrt(dn * dn + de * de))
        yaw.append(abs(_angle_delta(safe_float(rrow.get("yaw_deg")), safe_float(lrow.get("yaw_deg")))))
        roll = _angle_delta(safe_float(rrow.get("roll_deg")), safe_float(lrow.get("roll_deg")))
        pitch = _angle_delta(safe_float(rrow.get("pitch_deg")), safe_float(lrow.get("pitch_deg")))
        roll_pitch.append(math.sqrt(roll * roll + pitch * pitch))
    return {"time": times, "horizontal_m": horizontal, "yaw_deg": yaw, "roll_pitch_deg": roll_pitch}


def _ned_xy(rows: list[dict[str, Any]], *, origin_rows: list[dict[str, Any]] | None = None) -> tuple[list[float], list[float]]:
    if not rows:
        return [], []
    origin_source = origin_rows or rows
    if not origin_source:
        return [], []
    lat0 = safe_float(origin_source[0].get("lat_deg"))
    lon0 = safe_float(origin_source[0].get("lon_deg"))
    cos_lat = math.cos(math.radians(lat0))
    north = [(safe_float(row.get("lat_deg")) - lat0) * 111_000.0 for row in rows]
    east = [(safe_float(row.get("lon_deg")) - lon0) * 111_000.0 * cos_lat for row in rows]
    return north, east


def _downsample(values: list[float], max_count: int = 5000) -> list[float]:
    if len(values) <= max_count:
        return values
    step = max(1, len(values) // max_count)
    return values[::step]


def _paired_clean(x_values: list[float], y_values: list[float]) -> tuple[list[float], list[float]]:
    clean_x: list[float] = []
    clean_y: list[float] = []
    for x_value, y_value in zip(x_values, y_values):
        x = safe_float(x_value)
        y = safe_float(y_value)
        if math.isfinite(x) and math.isfinite(y):
            clean_x.append(x)
            clean_y.append(y)
    return clean_x, clean_y


def _range(values: list[float]) -> list[float]:
    clean = [safe_float(value) for value in values if math.isfinite(safe_float(value))]
    return [min(clean), max(clean)] if clean else []


def _monotonic(values: list[float]) -> bool:
    if len(values) <= 1:
        return True
    return all(left <= right for left, right in zip(values, values[1:]))


def _angle_delta(lhs: float, rhs: float) -> float:
    value = lhs - rhs
    while value > 180.0:
        value -= 360.0
    while value <= -180.0:
        value += 360.0
    return value


def _short_label(label: str) -> str:
    text = label.replace("horizontal_velocity_attitude", "hva")
    text = text.replace("position_velocity_attitude_diagnostic", "pva_diag")
    text = text.replace("velocity_attitude", "vel_att")
    text = text.replace("velocity_only", "vel_only")
    text = text.replace("attitude_only", "att_only")
    text = text.replace("baseline_no_fgo_feedback", "baseline")
    text = text.replace("reject_all_sanity", "reject_all")
    return text[:28]


def write_plot_coverage_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
