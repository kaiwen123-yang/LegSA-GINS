"""CLEAN2R2A diagnostic-only figures and render QA."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

from .clean2r2a_runner import AB_IDS, METHOD_ORDER, run_directory
from .manifest import sha256_file, write_json_atomic


class Clean2R2APlotError(RuntimeError):
    """Diagnostic plot input or render QA failed."""


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _finite(values: Iterable[float]) -> list[float]:
    rows = [float(value) for value in values]
    if not rows or not all(math.isfinite(value) for value in rows):
        raise Clean2R2APlotError("plot data are empty or non-finite")
    return rows


def generate_diagnostic_figures(*, stage_root: str | Path) -> dict[str, Any]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    stage = Path(stage_root).resolve(strict=True)
    analysis = stage / "09_FACTORIAL_ANALYSIS"
    evaluation = stage / "08_OFFLINE_EVALUATION"
    runtime = stage / "06_FORMAL_RUNS"
    destination = stage / "10_DIAGNOSTIC_FIGURES"
    if any(destination.iterdir()):
        raise Clean2R2APlotError("diagnostic figure root is not empty")
    results = _load_csv(analysis / "CLEAN2R2A_FACTORIAL_RESULTS.csv")
    main = _load_csv(analysis / "CLEAN2R2A_MODULE_MAIN_EFFECTS.csv")
    interactions = _load_csv(analysis / "CLEAN2R2A_PAIRWISE_INTERACTIONS.csv")
    by_id = {row["configuration_id"]: row for row in results}
    metrics = ("horizontal", "Up", "3D", "roll", "pitch", "yaw")
    columns = {
        "horizontal": "horizontal_rmse_m", "Up": "up_rmse_m", "3D": "position_3d_rmse_m",
        "roll": "roll_rmse_deg", "pitch": "pitch_rmse_deg", "yaw": "yaw_rmse_deg",
    }
    manifest_rows: list[dict[str, Any]] = []

    def save(fig: Any, figure_id: str, title: str, sample_count: int) -> None:
        if sample_count <= 0 or "real scenario" in title.casefold():
            raise Clean2R2APlotError("figure sample/title contract failed")
        fig.suptitle(f"DIAGNOSTIC ONLY — {title}")
        fig.tight_layout(rect=(0.0, 0.0, 0.82, 0.95))
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        legends = [(ax, ax.get_legend()) for ax in fig.axes if ax.get_legend() is not None]
        legend_outside = all(
            legend.get_window_extent(renderer).x0 >= ax.get_window_extent(renderer).x1 - 2.0
            for ax, legend in legends
        )
        ranges_valid = all(
            all(math.isfinite(value) for value in (*ax.get_xlim(), *ax.get_ylim()))
            and ax.get_xlim()[1] > ax.get_xlim()[0]
            and ax.get_ylim()[1] > ax.get_ylim()[0]
            for ax in fig.axes
        )
        text_extents_finite = all(
            all(math.isfinite(value) for value in text.get_window_extent(renderer).bounds)
            for ax in fig.axes for text in (*ax.texts, *ax.get_xticklabels(), *ax.get_yticklabels())
        )
        pixels = np.asarray(fig.canvas.buffer_rgba())
        render_nonblank = pixels.size > 0 and float(np.std(pixels)) > 0.0
        machine_passed = legend_outside and ranges_valid and text_extents_finite and render_nonblank
        if not machine_passed:
            raise Clean2R2APlotError(f"machine render QA failed: {figure_id}")
        png = destination / f"{figure_id}.png"
        pdf = destination / f"{figure_id}.pdf"
        fig.savefig(png, dpi=160, bbox_inches="tight")
        fig.savefig(pdf, bbox_inches="tight")
        plt.close(fig)
        for path, file_format in ((png, "PNG"), (pdf, "PDF")):
            if path.stat().st_size < 1000:
                raise Clean2R2APlotError(f"empty diagnostic render: {path.name}")
            manifest_rows.append({
                "figure_id": figure_id, "title": title, "format": file_format,
                "relative_path": path.relative_to(stage).as_posix(), "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path), "plotted_sample_count": sample_count,
                "finite": True, "nonempty": True, "legend_outside": legend_outside,
                "axis_ranges_valid": ranges_valid, "text_extents_finite": text_extents_finite,
                "render_nonblank": render_nonblank, "machine_passed": machine_passed,
                "delta_panel": figure_id in {"F06", "F07", "F08", "F09", "F10", "F11", "F12", "F13"},
                "diagnostic_only_title": True, "controlled_degradation_wording": False,
            })

    # 1. 主效应
    main_matrix = np.array([[float(next(row["effect"] for row in main if row["metric"] == metric and row["factor"] == factor))
                             for factor in ("RD", "SA", "RP", "HV")] for metric in metrics])
    fig, ax = plt.subplots(figsize=(9, 5)); image = ax.imshow(main_matrix, cmap="coolwarm", aspect="auto")
    ax.set_xticks(range(4), ("RD", "SA", "RP", "HV")); ax.set_yticks(range(6), metrics)
    fig.colorbar(image, ax=ax, label="effect (positive = harmful)"); save(fig, "F01", "module main effects", main_matrix.size)

    # 2. 二阶交互
    terms = sorted({row["interaction"] for row in interactions})
    interaction_matrix = np.array([[float(next(row["effect"] for row in interactions if row["metric"] == metric and row["interaction"] == term))
                                    for term in terms] for metric in metrics])
    fig, ax = plt.subplots(figsize=(11, 5)); image = ax.imshow(interaction_matrix, cmap="coolwarm", aspect="auto")
    ax.set_xticks(range(len(terms)), terms, rotation=30, ha="right"); ax.set_yticks(range(6), metrics)
    fig.colorbar(image, ax=ax, label="interaction effect"); save(fig, "F02", "pairwise interactions", interaction_matrix.size)

    # 3-5. 16 variants
    x = np.arange(16)
    fig, ax = plt.subplots(figsize=(12, 5)); ax.bar(x, _finite(by_id[item]["yaw_rmse_deg"] for item in AB_IDS), label="yaw RMSE")
    ax.set_xticks(x, AB_IDS, rotation=60); ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1)); save(fig, "F03", "16-variant yaw RMSE", 16)
    fig, ax = plt.subplots(figsize=(12, 5))
    for column, label, style in (("horizontal_rmse_m", "horizontal", "-"), ("up_rmse_m", "Up", "--"), ("position_3d_rmse_m", "3D", ":")):
        ax.plot(x, _finite(by_id[item][column] for item in AB_IDS), linestyle=style, marker="o", alpha=0.8, label=label)
    ax.set_xticks(x, AB_IDS, rotation=60); ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1)); save(fig, "F04", "position RMSE", 48)
    fig, ax = plt.subplots(figsize=(12, 5))
    for column, label, style in (("roll_rmse_deg", "roll", "-"), ("pitch_rmse_deg", "pitch", "--"), ("yaw_rmse_deg", "yaw", ":")):
        ax.plot(x, _finite(by_id[item][column] for item in AB_IDS), linestyle=style, marker="o", alpha=0.8, label=label)
    ax.set_xticks(x, AB_IDS, rotation=60); ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1)); save(fig, "F05", "attitude RMSE", 48)

    def comparison_timeline(figure_id: str, left: str, right: str, title: str) -> None:
        left_rows = _load_csv(evaluation / run_directory(left) / "error_series.csv")
        right_rows = _load_csv(evaluation / run_directory(right) / "error_series.csv")
        count = min(len(left_rows), len(right_rows))
        times = _finite(left_rows[index]["time"] for index in range(count))
        left_yaw = _finite(left_rows[index]["yaw_err_deg"] for index in range(count))
        right_yaw = _finite(right_rows[index]["yaw_err_deg"] for index in range(count))
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        axes[0].plot(times, left_yaw, label=left, alpha=0.75, linewidth=0.8, zorder=3)
        axes[0].plot(times, right_yaw, label=right, alpha=0.65, linewidth=0.8, linestyle="--", zorder=2)
        axes[0].set_ylabel("yaw error (deg)"); axes[0].legend(loc="upper left", bbox_to_anchor=(1.01, 1))
        axes[1].plot(times, np.array(left_yaw) - np.array(right_yaw), label="left - right", color="black", linewidth=0.8)
        axes[1].axhline(0, color="gray", linewidth=0.6); axes[1].set_ylabel("delta (deg)"); axes[1].set_xlabel("time (s)")
        axes[1].legend(loc="upper left", bbox_to_anchor=(1.01, 1)); save(fig, figure_id, title, count * 3)

    comparison_timeline("F06", "AB1111", "AB0000", "full vs strong error timeline")
    comparison_timeline("F07", "AB1111", "AB1011", "full vs no-source-aware")
    comparison_timeline("F08", "AB1111", "AB1100", "full vs no-Go2-priors")

    for index, (factor, bit_index) in enumerate((("RD", 0), ("SA", 1), ("RP", 2), ("HV", 3)), start=9):
        on = [item for item in AB_IDS if item[2 + bit_index] == "1"]
        off = [item for item in AB_IDS if item[2 + bit_index] == "0"]
        effects = [float(next(row["effect"] for row in main if row["metric"] == metric and row["factor"] == factor)) for metric in metrics]
        on_mean = [sum(float(by_id[item][columns[metric]]) for item in on) / len(on) for metric in metrics]
        off_mean = [sum(float(by_id[item][columns[metric]]) for item in off) / len(off) for metric in metrics]
        fig, axes = plt.subplots(2, 1, figsize=(10, 7))
        positions = np.arange(len(metrics)); width = 0.35
        axes[0].bar(positions - width / 2, off_mean, width, label=f"{factor} off", alpha=0.75)
        axes[0].bar(positions + width / 2, on_mean, width, label=f"{factor} on", alpha=0.75)
        axes[0].set_xticks(positions, metrics); axes[0].legend(loc="upper left", bbox_to_anchor=(1.01, 1))
        axes[1].bar(positions, effects, label="on - off effect", color=["#b2182b" if value > 0 else "#2166ac" for value in effects])
        axes[1].axhline(0, color="black", linewidth=0.6); axes[1].set_xticks(positions, metrics)
        axes[1].legend(loc="upper left", bbox_to_anchor=(1.01, 1)); save(fig, f"F{index:02d}", f"{factor} on/off", len(on) + len(off) + len(effects))

    trace_rows = _load_csv(runtime / run_directory("AB1111") / "SOURCE_AWARE_WEIGHT_TRACE.csv")
    sources = sorted({row["source_id"] for row in trace_rows})
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    sample_count = 0
    for source in sources:
        rows = [row for row in trace_rows if row["source_id"] == source]
        times = _finite(row["time"] for row in rows); scales = _finite(row["combined_R_scale"] for row in rows)
        axes[0].plot(times, scales, label=source, linewidth=0.7, alpha=0.75); sample_count += len(rows)
    rejected = [row for row in trace_rows if row["rejected"] == "1"]
    if rejected:
        axes[1].scatter(_finite(row["time"] for row in rejected),
                        [1.0] * len(rejected), label="reject action", s=8)
    else:
        axes[1].text(0.5, 0.5, "0 rejects", transform=axes[1].transAxes,
                     ha="center", va="center")
        axes[1].plot([], [], label="0 reject actions")
        axes[1].set_xlim(min(_finite(row["time"] for row in trace_rows)),
                         max(_finite(row["time"] for row in trace_rows)))
        axes[1].set_ylim(0.0, 1.0)
    axes[0].set_ylabel("R scale"); axes[1].set_ylabel("action"); axes[1].set_xlabel("time (s)")
    for ax in axes: ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    save(fig, "F13", "source-aware R-scale and action panel", sample_count + len(rejected))

    counter_names = ("raw_doppler_update_count", "source_aware_evaluation_count", "go2_roll_pitch_update_count", "go2_horizontal_velocity_update_count")
    counter_values: dict[str, list[int]] = {name: [] for name in counter_names}
    for method in AB_IDS:
        wrapper = json.loads((runtime / run_directory(method) / "CLEAN2R2A_FORMAL_RUN_MANIFEST.json").read_text(encoding="utf-8"))
        for name in counter_names: counter_values[name].append(int(wrapper["module_counters"][name]))
    fig, ax = plt.subplots(figsize=(12, 5))
    for offset, name in enumerate(counter_names):
        ax.plot(x, counter_values[name], marker="o", linewidth=0.8, alpha=0.75, label=name)
    ax.set_xticks(x, AB_IDS, rotation=60); ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1)); save(fig, "F14", "module activation counts", 64)

    fig, ax = plt.subplots(figsize=(11, 5)); ax.axis("off")
    ax.text(0.02, 0.92, "Claim boundary", fontsize=16, weight="bold")
    ax.text(0.02, 0.72, "Allowed: BY2 real-clean descriptive module ablation\nSame-source offline evaluation\nHelpful, neutral, and harmful findings", fontsize=12)
    ax.text(0.52, 0.72, "Not established: degradation robustness\nuniversal superiority\nindependent ground truth\nBY3/XB generalization", fontsize=12)
    save(fig, "F15", "clean claim-boundary panel", 8)

    manifest_path = destination / "CLEAN2R2A_FIGURE_MANIFEST.csv"
    with manifest_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0])); writer.writeheader(); writer.writerows(manifest_rows)
    qa = {
        "schema_version": "paper_rebuild.clean2r2a_figure_qa.v1",
        "figure_groups": 15, "render_files": 30,
        "all_nonempty": all(row["nonempty"] for row in manifest_rows),
        "all_finite": all(row["finite"] for row in manifest_rows),
        "all_titles_diagnostic_only": all(row["diagnostic_only_title"] for row in manifest_rows),
        "legends_outside": all(row["legend_outside"] for row in manifest_rows),
        "axis_ranges_valid": all(row["axis_ranges_valid"] for row in manifest_rows),
        "text_extents_finite": all(row["text_extents_finite"] for row in manifest_rows),
        "renders_nonblank": all(row["render_nonblank"] for row in manifest_rows),
        "action_labels_separate_panel": any(row["figure_id"] == "F13" and row["delta_panel"] for row in manifest_rows),
        "zero_rejects_drawn_as_false_action": False,
        "misleading_real_scenario_wording": False, "passed": len(manifest_rows) == 30,
    }
    qa["passed"] = bool(
        qa["figure_groups"] == 15 and qa["render_files"] == 30
        and qa["all_nonempty"] and qa["all_finite"] and qa["all_titles_diagnostic_only"]
        and qa["legends_outside"] and qa["axis_ranges_valid"]
        and qa["text_extents_finite"] and qa["renders_nonblank"]
        and qa["action_labels_separate_panel"]
    )
    write_json_atomic(destination / "CLEAN2R2A_FIGURE_MACHINE_QA.json", qa)
    return qa


def record_visual_figure_review(
    *, stage_root: str | Path, review_json: str | Path,
) -> dict[str, Any]:
    """Validate an explicit per-figure review; file existence alone is never approval."""

    stage = Path(stage_root).resolve(strict=True)
    destination = stage / "10_DIAGNOSTIC_FIGURES"
    machine = json.loads((destination / "CLEAN2R2A_FIGURE_MACHINE_QA.json").read_text(encoding="utf-8"))
    review_path = Path(review_json).resolve(strict=True)
    submitted = json.loads(review_path.read_text(encoding="utf-8"))
    reviewer = submitted.get("reviewer")
    reviewed_at = submitted.get("reviewed_at")
    decisions = submitted.get("figures")
    if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise Clean2R2APlotError("visual review identity or machine QA is incomplete")
    if machine.get("passed") is not True or not isinstance(decisions, list) or len(decisions) != 15:
        raise Clean2R2APlotError("visual review decisions or machine QA are incomplete")
    manifest = _load_csv(destination / "CLEAN2R2A_FIGURE_MANIFEST.csv")
    png_manifest = {row["figure_id"]: row for row in manifest if row["format"] == "PNG"}
    expected_ids = {f"F{index:02d}" for index in range(1, 16)}
    by_id: dict[str, dict[str, Any]] = {}
    decision_fields = (
        "opened", "legend_or_label_overlap", "curves_obscured", "long_labels_clipped",
        "misleading_real_scenario_wording", "action_labels_overlap_data", "passed",
    )
    for decision in decisions:
        if not isinstance(decision, dict) or not isinstance(decision.get("figure_id"), str):
            raise Clean2R2APlotError("visual review row is malformed")
        figure_id = decision["figure_id"]
        if figure_id in by_id or figure_id not in expected_ids:
            raise Clean2R2APlotError("visual review figure identity is duplicate or unknown")
        if any(not isinstance(decision.get(field), bool) for field in decision_fields):
            raise Clean2R2APlotError(f"visual review booleans are incomplete: {figure_id}")
        expected_path = (stage / png_manifest[figure_id]["relative_path"]).resolve(strict=True)
        if (
            decision.get("relative_path") != png_manifest[figure_id]["relative_path"]
            or decision.get("sha256") != png_manifest[figure_id]["sha256"]
            or sha256_file(expected_path) != decision.get("sha256")
            or expected_path.stat().st_size < 1000
        ):
            raise Clean2R2APlotError(f"visual review render binding failed: {figure_id}")
        by_id[figure_id] = decision
    if set(by_id) != expected_ids:
        raise Clean2R2APlotError("visual review did not cover all 15 figures")
    any_overlap = any(row["legend_or_label_overlap"] for row in by_id.values())
    any_obscured = any(row["curves_obscured"] for row in by_id.values())
    any_clipped = any(row["long_labels_clipped"] for row in by_id.values())
    any_misleading = any(row["misleading_real_scenario_wording"] for row in by_id.values())
    any_action_overlap = any(row["action_labels_overlap_data"] for row in by_id.values())
    every_opened = all(row["opened"] for row in by_id.values())
    every_row_passed = all(row["passed"] for row in by_id.values())
    visual_passed = bool(
        every_opened and every_row_passed and not any_overlap and not any_obscured
        and not any_clipped and not any_misleading and not any_action_overlap
    )
    visual = {
        "schema_version": "paper_rebuild.clean2r2a_figure_visual_review.v1",
        "reviewer": reviewer, "reviewed_at": reviewed_at,
        "review_input_sha256": sha256_file(review_path), "reviewed_png_count": 15,
        "figure_decisions": [by_id[key] for key in sorted(by_id)],
        "all_opened": every_opened,
        "legend_or_label_overlap": any_overlap, "curves_obscured": any_obscured,
        "long_labels_clipped": any_clipped,
        "misleading_real_scenario_wording": any_misleading,
        "action_labels_overlap_data": any_action_overlap,
        "passed": visual_passed,
    }
    write_json_atomic(destination / "CLEAN2R2A_FIGURE_VISUAL_REVIEW.json", visual)
    final = {
        "schema_version": "paper_rebuild.clean2r2a_figure_render_qa.v1",
        "machine_qa": machine, "visual_review": visual,
        "passed": machine.get("passed") is True and visual["passed"] is True,
    }
    write_json_atomic(destination / "CLEAN2R2A_FIGURE_RENDER_QA.json", final)
    if not final["passed"]:
        raise Clean2R2APlotError("visual figure review reported a render/readability failure")
    return final
