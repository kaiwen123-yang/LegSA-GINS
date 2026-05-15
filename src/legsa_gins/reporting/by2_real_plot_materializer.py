"""N8K2 real plot materializer."""

# 中文说明：编排真实绘图生成，只向 N8K2 runtime 目录写图，不覆盖 N8K 原图。

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, write_json

from .by2_formal_ablation_plot_catalog import PLOT_CATEGORIES
from .by2_real_factor_plots import build_real_factor_plot_report, generate_real_factor_plot
from .by2_real_feedback_plots import build_real_feedback_plot_report, generate_real_feedback_plot
from .by2_real_legged_factor_plots import build_real_legged_plot_report, generate_real_legged_plot
from .by2_real_timeseries_plots import REAL_TIMESERIES_CATEGORIES, generate_real_timeseries_plot, write_not_applicable_panel, write_semantic_panel
from .by2_real_trajectory_plots import build_real_trajectory_plot_report, generate_real_trajectory_plot


TEXT_PANEL_CATEGORIES = {"13_ablation_meta", "14_audit_sanity"}


def materialize_real_plots(
    *,
    n8k_root: str | Path,
    data_bundle: dict[str, Any],
    figure_output_dir: str | Path,
    case_review_dir: str | Path,
    summary_dir: str | Path,
) -> dict[str, Any]:
    n8k = Path(n8k_root)
    out = Path(figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    Path(case_review_dir).mkdir(parents=True, exist_ok=True)
    Path(summary_dir).mkdir(parents=True, exist_ok=True)
    catalog = read_json(n8k / "N8K_BY2_ABLATION_FULL_PLOT_CATALOG.json")
    variants = data_bundle["variants"]
    generated: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    for variant in catalog.get("variants", []):
        variant_id = str(variant.get("variant_id"))
        data = variants.get(variant_id)
        if not data:
            blockers.append({"variant_id": variant_id, "reason": "missing loaded plot data"})
            continue
        for item in variant.get("files", []):
            category = str(item["category"])
            filename = str(item["filename"])
            path = out / variant_id / category / filename
            if filename.endswith(".png"):
                if not item.get("applicable", True):
                    entry = write_not_applicable_panel(path, variant_id, category, filename, item.get("not_applicable_reason", "not applicable"))
                elif category == "01_trajectory":
                    entry = generate_real_trajectory_plot(variant_id, data, filename, path)
                elif category in REAL_TIMESERIES_CATEGORIES:
                    entry = generate_real_timeseries_plot(variant_id, data, category, filename, path)
                elif category == "10_fgo_factors":
                    entry = generate_real_factor_plot(variant_id, data, filename, path)
                elif category == "11_feedback":
                    entry = generate_real_feedback_plot(variant_id, data, filename, path)
                elif category == "12_legged_factors":
                    entry = generate_real_legged_plot(variant_id, data, filename, path)
                elif category in TEXT_PANEL_CATEGORIES:
                    entry = write_semantic_panel(path, variant_id, category, filename, data)
                else:
                    entry = generate_real_timeseries_plot(variant_id, data, "08_summary_panels", filename, path)
                catalog_reason = item.get("not_applicable_reason", "")
                if catalog_reason:
                    entry["not_applicable_reason"] = catalog_reason
                generated.append(entry)
            elif filename.endswith(".csv"):
                _write_case_csv(path, data)
                generated.append(_file_entry(variant_id, category, filename, path, item.get("applicable", True), data))
            else:
                _write_case_md(path, data, filename)
                generated.append(_file_entry(variant_id, category, filename, path, item.get("applicable", True), data))
    png_entries = [item for item in generated if item["filename"].endswith(".png")]
    materialization = {
        "stage": "N8K2",
        "variants_processed": len({item["variant_id"] for item in generated}),
        "figures_requested": sum(1 for variant in catalog.get("variants", []) for item in variant.get("files", []) if str(item["filename"]).endswith(".png")),
        "figures_generated": len(png_entries),
        "real_data_figures": sum(1 for item in png_entries if item.get("real_data") is True),
        "placeholder_figures": sum(1 for item in png_entries if item.get("placeholder_allowed") is True),
        "not_applicable_figures": sum(1 for item in png_entries if item.get("applicable") is False),
        "blockers": blockers,
        "rerun_performed": False,
        "plot_output_role": "N8K2_FIGURE_OUTPUT_DIR",
        "generated": generated,
        "trajectory_report": build_real_trajectory_plot_report(generated),
        "factor_report": build_real_factor_plot_report(generated),
        "feedback_report": build_real_feedback_plot_report(generated),
        "legged_report": build_real_legged_plot_report(generated),
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    return materialization


def write_real_plot_materialization_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)


def _write_case_md(path: Path, data: dict[str, Any], filename: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = data.get("metrics", {})
    lines = [
        f"# {data['variant_id']} N8K2 Real Plot Case Review",
        "",
        f"- file: `{filename}`",
        f"- data source: `{data.get('data_source')}`",
        f"- plot rows: `{data.get('plot_row_count')}`",
        f"- horizontal p95: `{metrics.get('horizontal_p95')}`",
        f"- yaw p95: `{metrics.get('yaw_p95')}`",
        "- figure suitability: `internal_audit_only`",
        "- boundary: real plot materialization audit only; no paper performance claim.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_case_csv(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = data.get("metrics", {})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerow(["data_source", data.get("data_source")])
        writer.writerow(["plot_rows", data.get("plot_row_count")])
        for key in ["horizontal_rmse", "horizontal_p95", "horizontal_max", "yaw_rmse", "yaw_p95", "yaw_max"]:
            writer.writerow([key, metrics.get(key, "")])


def _file_entry(variant_id: str, category: str, filename: str, path: Path, applicable: bool, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "category": category,
        "filename": filename,
        "path_role": "N8K2_FIGURE_OUTPUT_DIR",
        "present": path.exists(),
        "nonempty": path.exists() and path.stat().st_size > 0,
        "applicable": applicable,
        "real_data": True,
        "placeholder_allowed": False,
        "plot_kind": "case_review_file",
        "row_count": data.get("plot_row_count", 0),
    }


def required_png_count() -> int:
    return sum(1 for names in PLOT_CATEGORIES.values() for name in names if name.endswith(".png"))
