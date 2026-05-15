"""N8K2 real plot coverage audit."""

# 中文说明：coverage 要求 applicable 数据图没有 placeholder、缺失或低信息量未解决项。

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, write_json


def build_real_plot_coverage(
    *,
    n8k_root: str | Path,
    materialization: dict[str, Any],
    placeholder_report: dict[str, Any],
    data_report: dict[str, Any],
) -> dict[str, Any]:
    catalog = read_json(Path(n8k_root) / "N8K_BY2_ABLATION_FULL_PLOT_CATALOG.json")
    entries = materialization.get("generated", [])
    by_key = {(item["variant_id"], item["category"], item["filename"]): item for item in entries}
    missing = []
    missing_real = []
    not_applicable = 0
    category_coverage = {f"{index:02d}": {"expected": 0, "generated": 0} for index in range(1, 15)}
    for variant in catalog.get("variants", []):
        variant_id = str(variant.get("variant_id"))
        for item in variant.get("files", []):
            category = str(item["category"])
            filename = str(item["filename"])
            prefix = category.split("_", 1)[0]
            category_coverage.setdefault(prefix, {"expected": 0, "generated": 0})
            category_coverage[prefix]["expected"] += 1
            entry = by_key.get((variant_id, category, filename))
            if not item.get("applicable", True):
                not_applicable += 1
            if not entry or not entry.get("present") or not entry.get("nonempty"):
                missing.append({"variant_id": variant_id, "category": category, "filename": filename})
                continue
            category_coverage[prefix]["generated"] += 1
            if filename.endswith(".png") and item.get("applicable", True) and category not in {"13_ablation_meta", "14_audit_sanity"}:
                if entry.get("real_data") is not True or int(entry.get("row_count", 0)) <= 0:
                    missing_real.append({"variant_id": variant_id, "category": category, "filename": filename, "reason": "missing real rows"})
    coverage = {
        "stage": "N8K2",
        "variant_count": len(catalog.get("variants", [])),
        "required_category_count": 14,
        "category_coverage": category_coverage,
        "missing_count": len(missing),
        "missing": missing,
        "not_applicable_count": not_applicable,
        "applicable_placeholder_count": placeholder_report.get("applicable_placeholder_remaining", 0),
        "duplicate_template_suspect_count": placeholder_report.get("duplicate_template_suspect_count", 0),
        "semantic_filename_mismatch_count": placeholder_report.get("semantic_filename_mismatch_count", 0),
        "missing_real_plot_count": len(missing_real),
        "missing_real_plots": missing_real,
        "unresolved_missing_data_count": data_report.get("unresolved_missing_data_count", 0),
        "low_information_unresolved_count": placeholder_report.get("applicable_placeholder_remaining", 0),
        "all_categories_complete": len(missing) == 0 and all(item["expected"] == item["generated"] for item in category_coverage.values()),
        "all_applicable_plots_real": len(missing_real) == 0 and placeholder_report.get("applicable_placeholder_remaining", 0) == 0,
        "algorithm_changes": False,
        "degradation_matrix_run": False,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }
    return coverage


def write_real_plot_coverage(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
