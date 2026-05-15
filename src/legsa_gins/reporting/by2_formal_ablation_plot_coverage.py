"""N8K BY2 formal ablation plot coverage audit."""

# 中文说明：coverage 审计要求每个正式消融 variant 的图像类别完整。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from .by2_formal_ablation_plot_catalog import PLOT_CATEGORIES


def build_plot_coverage(catalog: dict[str, Any], generation_manifest: dict[str, Any], figure_output_dir: str | Path) -> dict[str, Any]:
    out = Path(figure_output_dir)
    by_variant: dict[str, dict[str, Any]] = {}
    missing = []
    not_applicable = 0
    for variant in catalog.get("variants", []):
        variant_id = variant["variant_id"]
        categories = {key: {"expected": len(value), "present": 0, "nonempty": 0} for key, value in PLOT_CATEGORIES.items()}
        for item in variant.get("files", []):
            path = out / variant_id / item["category"] / item["filename"]
            present = path.exists()
            nonempty = present and path.stat().st_size > 0
            categories[item["category"]]["present"] += int(present)
            categories[item["category"]]["nonempty"] += int(nonempty)
            if not item.get("applicable", True):
                not_applicable += 1
            if not nonempty:
                missing.append({"variant_id": variant_id, "category": item["category"], "filename": item["filename"]})
        by_variant[variant_id] = {"categories": categories, "all_categories_present": all(v["present"] == v["expected"] and v["nonempty"] == v["expected"] for v in categories.values())}
    return {
        "stage": "N8K",
        "variant_count": len(by_variant),
        "required_category_count": len(PLOT_CATEGORIES),
        "total_expected_files": sum(len(v.get("files", [])) for v in catalog.get("variants", [])),
        "total_generated_files": generation_manifest.get("generated_file_count", 0),
        "total_png_figures_generated": generation_manifest.get("generated_png_count", 0),
        "missing_count": len(missing),
        "not_applicable_count": not_applicable,
        "missing": missing,
        "coverage_by_variant": by_variant,
        "all_required_categories_complete": len(missing) == 0 and all(v["all_categories_present"] for v in by_variant.values()),
        "plot_output_role": "N8K_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
    }


def write_plot_coverage(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
