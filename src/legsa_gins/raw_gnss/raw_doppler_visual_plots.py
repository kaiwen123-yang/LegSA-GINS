"""Generate N5D raw Doppler visual/stress figures.

中文说明：每张图都是 runtime-only 单图输出；不画 pure INS / single antenna，
不使用 seaborn，不提交生成的 png/pdf/svg/jpg/jpeg。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURE_NAMES = [
    "01_clean_ablation/clean_horizontal_error_baseline_vs_raw.png",
    "01_clean_ablation/clean_up_error_baseline_vs_raw.png",
    "01_clean_ablation/clean_yaw_error_baseline_vs_raw.png",
    "01_clean_ablation/clean_roll_pitch_error_baseline_vs_raw.png",
    "01_clean_ablation/baseline_minus_raw_horizontal_diff.png",
    "01_clean_ablation/baseline_minus_raw_yaw_diff.png",
    "02_velocity_factor/raw_doppler_velocity_ned_time.png",
    "02_velocity_factor/receiver_velocity_vs_raw_doppler_velocity_north.png",
    "02_velocity_factor/receiver_velocity_vs_raw_doppler_velocity_east.png",
    "02_velocity_factor/receiver_velocity_vs_raw_doppler_velocity_down.png",
    "02_velocity_factor/raw_minus_receiver_velocity_norm.png",
    "02_velocity_factor/raw_doppler_velocity_bias_hist.png",
    "03_time_alignment/raw_doppler_time_diff_hist.png",
    "03_time_alignment/raw_doppler_update_timeline.png",
    "03_time_alignment/raw_doppler_update_match_status.png",
    "04_residuals/raw_doppler_residual_norm_time.png",
    "04_residuals/raw_doppler_residual_hist.png",
    "04_residuals/raw_doppler_residual_vs_sat_count.png",
    "04_residuals/raw_doppler_reject_count_panel.png",
    "05_stress_protocol/stress_horizontal_rmse_bar.png",
    "05_stress_protocol/stress_up_rmse_bar.png",
    "05_stress_protocol/stress_yaw_rmse_bar.png",
    "05_stress_protocol/stress_roll_pitch_rmse_bar.png",
    "05_stress_protocol/velocity_disabled_baseline_vs_raw_errors.png",
    "05_stress_protocol/receiver_velocity_outage_baseline_vs_raw_errors.png",
    "05_stress_protocol/receiver_velocity_noise_baseline_vs_raw_errors.png",
    "06_std_consistency/raw_doppler_std_velocity_time.png",
    "06_std_consistency/velocity_error_vs_raw_doppler_3sigma.png",
    "06_std_consistency/raw_doppler_sat_count_time.png",
    "07_summary/clean_ablation_delta_panel.png",
    "07_summary/stress_delta_panel.png",
    "07_summary/n5d_decision_panel.png",
]


def _load_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _axis(plt, figsize: tuple[float, float] = (8.5, 4.8)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0.12, 0.16, 0.82, 0.74])
    return fig, ax


def _save_line(plt, path: Path, series: list[tuple[str, list[float], list[float]]], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for label, x, y in series:
        ax.plot(x[: len(y)], y, linewidth=1.0, label=label)
    ax.set_title(title)
    ax.set_xlabel("time since start (s)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_hist(plt, path: Path, series: list[tuple[str, list[float]]], title: str, xlabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    for label, values in series:
        ax.hist([value for value in values if math.isfinite(value)], bins=40, alpha=0.50, label=label)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.grid(True, linewidth=0.3, alpha=0.45)
    if len(series) > 1:
        ax.legend(loc="best", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar(plt, path: Path, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(9.5, 4.8))
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=25)
    ax.grid(True, axis="y", linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_scatter(
    plt,
    path: Path,
    x: list[float],
    y: list[float],
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt)
    ax.scatter(x[: len(y)], y, s=8, alpha=0.60)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linewidth=0.3, alpha=0.45)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_text_panel(plt, path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = _axis(plt, figsize=(8.5, 5.2))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.02, 0.92, "\n".join(lines), va="top", ha="left", fontsize=10, family="monospace")
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _rel_times(rows: list[dict[str, Any]]) -> list[float]:
    if not rows:
        return []
    first = float(rows[0].get("timestamp", rows[0].get("time", 0.0)) or 0.0)
    return [float(row.get("timestamp", row.get("time", first)) or first) - first for row in rows]


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            out.append(float(value))
    return out


def _summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {}
    return report.get("summary") or report.get("parity_metrics") or {}


def _paired_clean_errors(inputs: dict[str, Any]) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    errors = inputs.get("variant_error_rows", {})
    return errors.get("baseline_full", []), errors.get("baseline_plus_raw_doppler_r1", [])


def _pair_report(stress_eval: dict[str, Any], pair_id: str) -> dict[str, Any]:
    for pair in stress_eval.get("pairwise_stress_deltas", []):
        if pair.get("pair_id") == pair_id:
            return pair
    return {}


def _stress_metric_bars(stress_eval: dict[str, Any], key: str) -> tuple[list[str], list[float]]:
    labels: list[str] = []
    values: list[float] = []
    for pair in stress_eval.get("pairwise_stress_deltas", []):
        if pair.get("pair_id") == "velocity_isolation":
            continue
        labels.append(str(pair.get("pair_id", "")).replace("receiver_velocity_", ""))
        delta = pair.get("delta_plus_raw_minus_no_raw", {}).get(key)
        values.append(float(delta) if isinstance(delta, (int, float)) else 0.0)
    return labels, values


def _variant_summary(inputs: dict[str, Any], variant_id: str) -> dict[str, Any]:
    return _summary(inputs.get("variant_reports_by_id", {}).get(variant_id))


def _metric_value(summary: dict[str, Any], key: str) -> float:
    value = summary.get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else 0.0


def _write_case_review(path: Path, sanity: dict[str, Any], stress_eval: dict[str, Any], decision: dict[str, Any] | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# N5D visual/stress case review",
        "",
        "This report is diagnostic engineering evidence only.",
        "",
        f"- visual_stress_candidate_passed: {sanity.get('visual_stress_candidate_passed')}",
        f"- stress_help_pair_count: {stress_eval.get('stress_help_pair_count')}",
        f"- stress_degrade_pair_count: {stress_eval.get('stress_degrade_pair_count')}",
        f"- decision_status: {(decision or {}).get('status')}",
        f"- recommended_next_stage: {(decision or {}).get('recommended_next_stage')}",
        "- paper_performance_claim: false",
        "- no_outperform_final_v23_claim: true",
        "- final_v23_output_solver_input: false",
        "- trace_solver_input: false",
        "- output_only_correction: false",
        "- bad_epoch_deletion_for_metric: false",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_n5d_visual_plots(
    inputs: dict[str, Any],
    *,
    output_dir: str | Path,
    figure_output_dir: str | Path,
    stress_eval: dict[str, Any],
    visual_sanity: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plt = _load_matplotlib()
    fig_root = Path(figure_output_dir)
    out = Path(output_dir)
    fig_root.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    def add(rel: str) -> Path:
        generated.append(rel)
        return fig_root / rel

    baseline_errors, raw_errors = _paired_clean_errors(inputs)
    t_base = _rel_times(baseline_errors)
    t_raw = _rel_times(raw_errors)
    _save_line(plt, add("01_clean_ablation/clean_horizontal_error_baseline_vs_raw.png"), [("baseline", t_base, _values(baseline_errors, "horizontal_error_m")), ("baseline+raw", t_raw, _values(raw_errors, "horizontal_error_m"))], "clean horizontal error", "m")
    _save_line(plt, add("01_clean_ablation/clean_up_error_baseline_vs_raw.png"), [("baseline", t_base, _values(baseline_errors, "up_error_m")), ("baseline+raw", t_raw, _values(raw_errors, "up_error_m"))], "clean up error", "m")
    _save_line(plt, add("01_clean_ablation/clean_yaw_error_baseline_vs_raw.png"), [("baseline", t_base, _values(baseline_errors, "yaw_error_deg")), ("baseline+raw", t_raw, _values(raw_errors, "yaw_error_deg"))], "clean yaw error", "deg")
    _save_line(plt, add("01_clean_ablation/clean_roll_pitch_error_baseline_vs_raw.png"), [("baseline roll", t_base, _values(baseline_errors, "roll_error_deg")), ("raw roll", t_raw, _values(raw_errors, "roll_error_deg")), ("baseline pitch", t_base, _values(baseline_errors, "pitch_error_deg")), ("raw pitch", t_raw, _values(raw_errors, "pitch_error_deg"))], "clean roll/pitch error", "deg")
    n = min(len(baseline_errors), len(raw_errors))
    diff_h = [baseline_errors[i].get("horizontal_error_m", 0.0) - raw_errors[i].get("horizontal_error_m", 0.0) for i in range(n)]
    diff_yaw = [baseline_errors[i].get("yaw_error_deg", 0.0) - raw_errors[i].get("yaw_error_deg", 0.0) for i in range(n)]
    _save_line(plt, add("01_clean_ablation/baseline_minus_raw_horizontal_diff.png"), [("baseline - raw", t_base[:n], diff_h)], "baseline minus raw horizontal diff", "m")
    _save_line(plt, add("01_clean_ablation/baseline_minus_raw_yaw_diff.png"), [("baseline - raw", t_base[:n], diff_yaw)], "baseline minus raw yaw diff", "deg")

    raw_rows = inputs.get("raw_factor_rows", [])
    raw_time = _rel_times(raw_rows)
    _save_line(plt, add("02_velocity_factor/raw_doppler_velocity_ned_time.png"), [("vn", raw_time, _values(raw_rows, "vn")), ("ve", raw_time, _values(raw_rows, "ve")), ("vd", raw_time, _values(raw_rows, "vd"))], "raw Doppler velocity NED", "m/s")
    pairs = inputs.get("raw_receiver_velocity_pairs", [])
    pair_t = _rel_times(pairs)
    _save_line(plt, add("02_velocity_factor/receiver_velocity_vs_raw_doppler_velocity_north.png"), [("raw north", pair_t, _values(pairs, "raw_vn")), ("receiver north", pair_t, _values(pairs, "receiver_vn"))], "receiver vs raw Doppler north velocity", "m/s")
    _save_line(plt, add("02_velocity_factor/receiver_velocity_vs_raw_doppler_velocity_east.png"), [("raw east", pair_t, _values(pairs, "raw_ve")), ("receiver east", pair_t, _values(pairs, "receiver_ve"))], "receiver vs raw Doppler east velocity", "m/s")
    _save_line(plt, add("02_velocity_factor/receiver_velocity_vs_raw_doppler_velocity_down.png"), [("raw down", pair_t, _values(pairs, "raw_vd")), ("receiver down", pair_t, _values(pairs, "receiver_vd"))], "receiver vs raw Doppler down velocity", "m/s")
    _save_line(plt, add("02_velocity_factor/raw_minus_receiver_velocity_norm.png"), [("raw - receiver norm", pair_t, _values(pairs, "diff_norm"))], "raw minus receiver velocity norm", "m/s")
    _save_hist(plt, add("02_velocity_factor/raw_doppler_velocity_bias_hist.png"), [("north", _values(pairs, "diff_n")), ("east", _values(pairs, "diff_e")), ("down", _values(pairs, "diff_d"))], "raw Doppler velocity bias histogram", "m/s")

    diffs = _values(pairs, "dt")
    _save_hist(plt, add("03_time_alignment/raw_doppler_time_diff_hist.png"), [("raw - receiver time", diffs)], "raw Doppler time diff", "s")
    variant_reports = inputs.get("variant_reports", [])
    labels = [str(row.get("variant_id", "")) for row in variant_reports if row.get("enable_raw_doppler") or row.get("raw_doppler_solver_enabled")]
    updates = [float(row.get("raw_doppler_update_count", 0) or 0) for row in variant_reports if row.get("enable_raw_doppler") or row.get("raw_doppler_solver_enabled")]
    rejects = [float(row.get("raw_doppler_reject_count", 0) or 0) for row in variant_reports if row.get("enable_raw_doppler") or row.get("raw_doppler_solver_enabled")]
    _save_bar(plt, add("03_time_alignment/raw_doppler_update_timeline.png"), labels, updates, "raw Doppler update count by variant", "count")
    match_values = [1.0 if value == max(updates or [0.0]) and value > 0 else 0.0 for value in updates]
    _save_bar(plt, add("03_time_alignment/raw_doppler_update_match_status.png"), labels, match_values, "raw Doppler update match status", "ok=1")

    residual_proxy = _values(pairs, "diff_norm")
    _save_line(plt, add("04_residuals/raw_doppler_residual_norm_time.png"), [("velocity residual proxy", pair_t, residual_proxy)], "raw Doppler residual norm proxy", "m/s")
    _save_hist(plt, add("04_residuals/raw_doppler_residual_hist.png"), [("velocity residual proxy", residual_proxy)], "raw Doppler residual histogram", "m/s")
    _save_scatter(plt, add("04_residuals/raw_doppler_residual_vs_sat_count.png"), _values(raw_rows, "sat_count")[: len(residual_proxy)], residual_proxy, "raw Doppler residual vs sat count", "sat count", "m/s")
    _save_bar(plt, add("04_residuals/raw_doppler_reject_count_panel.png"), labels, rejects, "raw Doppler reject count", "count")

    labels_h, values_h = _stress_metric_bars(stress_eval, "horizontal_rmse_m")
    labels_up, values_up = _stress_metric_bars(stress_eval, "up_rmse_m")
    labels_yaw, values_yaw = _stress_metric_bars(stress_eval, "yaw_rmse_deg")
    labels_roll, values_roll = _stress_metric_bars(stress_eval, "roll_rmse_deg")
    labels_pitch, values_pitch = _stress_metric_bars(stress_eval, "pitch_rmse_deg")
    _save_bar(plt, add("05_stress_protocol/stress_horizontal_rmse_bar.png"), labels_h, values_h, "stress H delta plus_raw - no_raw", "m")
    _save_bar(plt, add("05_stress_protocol/stress_up_rmse_bar.png"), labels_up, values_up, "stress Up delta plus_raw - no_raw", "m")
    _save_bar(plt, add("05_stress_protocol/stress_yaw_rmse_bar.png"), labels_yaw, values_yaw, "stress Yaw delta plus_raw - no_raw", "deg")
    _save_bar(plt, add("05_stress_protocol/stress_roll_pitch_rmse_bar.png"), labels_roll + [label + " pitch" for label in labels_pitch], values_roll + values_pitch, "stress roll/pitch delta", "deg")
    for pair_id, rel in [
        ("receiver_velocity_disabled", "velocity_disabled_baseline_vs_raw_errors.png"),
        ("receiver_velocity_outage_30s", "receiver_velocity_outage_baseline_vs_raw_errors.png"),
        ("receiver_velocity_noise_0p5", "receiver_velocity_noise_baseline_vs_raw_errors.png"),
    ]:
        pair = _pair_report(stress_eval, pair_id)
        no_raw = pair.get("no_raw_summary", {})
        plus_raw = pair.get("plus_raw_summary", {})
        _save_bar(
            plt,
            add("05_stress_protocol/" + rel),
            ["no_raw H", "plus_raw H", "no_raw yaw", "plus_raw yaw"],
            [
                _metric_value(no_raw, "horizontal_rmse_m"),
                _metric_value(plus_raw, "horizontal_rmse_m"),
                _metric_value(no_raw, "yaw_rmse_deg"),
                _metric_value(plus_raw, "yaw_rmse_deg"),
            ],
            pair_id + " baseline vs raw",
            "RMSE",
        )

    _save_line(plt, add("06_std_consistency/raw_doppler_std_velocity_time.png"), [("std vn", raw_time, _values(raw_rows, "std_vn")), ("std ve", raw_time, _values(raw_rows, "std_ve")), ("std vd", raw_time, _values(raw_rows, "std_vd"))], "raw Doppler velocity STD", "m/s")
    _save_line(plt, add("06_std_consistency/velocity_error_vs_raw_doppler_3sigma.png"), [("velocity diff norm", pair_t, residual_proxy), ("raw Doppler 3sigma norm", pair_t, _values(pairs, "raw_3sigma_norm"))], "velocity error vs raw Doppler 3sigma", "m/s")
    _save_line(plt, add("06_std_consistency/raw_doppler_sat_count_time.png"), [("sat count", raw_time, _values(raw_rows, "sat_count"))], "raw Doppler satellite count", "count")

    clean_delta = stress_eval.get("clean_delta_baseline_plus_raw_minus_baseline", {})
    _save_bar(plt, add("07_summary/clean_ablation_delta_panel.png"), ["H", "Up", "Yaw", "Roll", "Pitch"], [float(clean_delta.get(key, 0.0) or 0.0) for key in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]], "clean ablation delta", "plus_raw - baseline")
    _save_bar(plt, add("07_summary/stress_delta_panel.png"), ["helps", "degrades"], [float(stress_eval.get("stress_help_pair_count", 0)), float(stress_eval.get("stress_degrade_pair_count", 0))], "stress diagnostic summary", "pair count")
    _save_text_panel(
        plt,
        add("07_summary/n5d_decision_panel.png"),
        "N5D decision boundary",
        [
            f"status: {(decision or {}).get('status', 'pending')}",
            f"next: {(decision or {}).get('recommended_next_stage', 'pending')}",
            f"visual_candidate: {(visual_sanity or {}).get('visual_stress_candidate_passed', 'pending')}",
            "paper_performance_claim: false",
            "no_outperform_final_v23_claim: true",
        ],
    )

    case_dir = fig_root / "08_case_review"
    case_dir.mkdir(parents=True, exist_ok=True)
    sanity = visual_sanity or {}
    manifest = {
        "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
        "figure_paths": generated,
        "figure_count_total": len(generated),
        "figure_count_by_folder": {},
        "required_figures_generated": all((fig_root / rel).exists() for rel in REQUIRED_FIGURE_NAMES),
        "pure_single_absent": not any(("pure" in rel.lower() or "single" in rel.lower()) for rel in generated),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    for rel in generated:
        folder = rel.split("/", 1)[0]
        manifest["figure_count_by_folder"][folder] = manifest["figure_count_by_folder"].get(folder, 0) + 1
    (out / "N5D_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "N5D_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    visual_report = {
        "stage": manifest["stage"],
        "figure_count_total": manifest["figure_count_total"],
        "required_figures_generated": manifest["required_figures_generated"],
        "clean_delta_baseline_plus_raw_minus_baseline": stress_eval.get("clean_delta_baseline_plus_raw_minus_baseline", {}),
        "stress_help_pair_count": stress_eval.get("stress_help_pair_count", 0),
        "stress_degrade_pair_count": stress_eval.get("stress_degrade_pair_count", 0),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    (out / "N5D_RAW_DOPPLER_VISUAL_STRESS_REPORT.json").write_text(json.dumps(visual_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "N5D_VISUAL_STRESS_REPORT.json").write_text(json.dumps(visual_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if sanity:
        (case_dir / "N5D_VISUAL_SANITY_REPORT.json").write_text(json.dumps(sanity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_case_review(case_dir / "n5d_visual_case_review.md", sanity, stress_eval, decision)
    return manifest
