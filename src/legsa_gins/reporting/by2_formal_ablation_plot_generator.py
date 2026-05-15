"""Generate N8K BY2 ablation audit figures."""

# 中文说明：所有图像写到 BY2 绘图审计根目录下，且不提交到 git。

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json


def generate_ablation_plots(catalog: dict[str, Any], matrix: dict[str, Any], metrics_report: dict[str, Any], figure_output_dir: str | Path) -> dict[str, Any]:
    out = Path(figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    metric_by_variant = {item.get("variant_id"): item for item in metrics_report.get("metrics", [])}
    matrix_by_variant = {item.get("variant_id"): item for item in matrix.get("rows", [])}
    generated = []
    for variant in catalog.get("variants", []):
        variant_id = str(variant.get("variant_id"))
        variant_root = out / variant_id
        for item in variant.get("files", []):
            category = item["category"]
            path = variant_root / category / item["filename"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if item["filename"].endswith(".png"):
                _write_png(path, variant_id, category, item["filename"], item.get("applicable", True), item.get("not_applicable_reason", ""), matrix_by_variant.get(variant_id, {}), metric_by_variant.get(variant_id, {}))
            elif item["filename"].endswith(".csv"):
                _write_case_csv(path, metric_by_variant.get(variant_id, {}))
            else:
                _write_case_md(path, variant_id, item.get("applicable", True), item.get("not_applicable_reason", ""), metric_by_variant.get(variant_id, {}))
            generated.append({"variant_id": variant_id, "category": category, "filename": item["filename"], "path_role": "N8K_FIGURE_OUTPUT_DIR", "present": path.exists(), "nonempty": path.exists() and path.stat().st_size > 0, "applicable": item.get("applicable", True), "not_applicable_reason": item.get("not_applicable_reason", "")})
    return {
        "stage": "N8K",
        "generated_file_count": len(generated),
        "generated_png_count": sum(1 for item in generated if item["filename"].endswith(".png")),
        "generated": generated,
        "all_generated_nonempty": all(item["nonempty"] for item in generated),
        "plot_output_role": "N8K_FIGURE_OUTPUT_DIR",
        "paper_performance_claim": False,
    }


def _write_png(path: Path, variant_id: str, category: str, filename: str, applicable: bool, reason: str, matrix_row: dict[str, Any], metrics: dict[str, Any]) -> None:
    image = Image.new("RGB", (900, 520), "white")
    draw = ImageDraw.Draw(image)
    title = f"N8K BY2 formal ablation: {variant_id}"
    lines = [
        title,
        f"category: {category}",
        f"figure: {filename}",
        f"applicable: {applicable}",
        f"reason: {reason or 'runtime audit figure'}",
        f"group: {matrix_row.get('group', '')}",
        f"feedback mode: {matrix_row.get('feedback_mode', '')}",
        f"horizontal p95: {metrics.get('horizontal_p95', '')}",
        "namespace: BY2 formal ablation engineering delta",
        "no paper performance claim / no outperform final_v23 claim",
    ]
    y = 28
    for line in lines:
        draw.text((28, y), str(line)[:120], fill=(0, 0, 0))
        y += 32
    draw.rectangle((40, 390, 860, 450), outline=(40, 80, 160), width=2)
    draw.line((60, 430, 240, 405, 430, 418, 660, 398, 840, 410), fill=(40, 80, 160), width=3)
    image.save(path)


def _write_case_md(path: Path, variant_id: str, applicable: bool, reason: str, metrics: dict[str, Any]) -> None:
    lines = [
        f"# {variant_id} Case Review",
        "",
        f"- applicable: `{applicable}`",
        f"- not applicable reason: `{reason}`",
        f"- horizontal p95: `{metrics.get('horizontal_p95', '')}`",
        f"- yaw p95: `{metrics.get('yaw_p95', '')}`",
        "- figure suitability: `internal_audit_only`",
        "- boundary: BY2 engineering ablation audit only; no paper performance claim.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_case_csv(path: Path, metrics: dict[str, Any]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key in ["horizontal_rmse", "horizontal_p95", "horizontal_max", "yaw_rmse", "yaw_p95", "yaw_max", "gross_degradation"]:
            writer.writerow([key, metrics.get(key, "")])


def write_plot_generation_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)
