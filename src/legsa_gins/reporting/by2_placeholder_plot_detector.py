"""Detect placeholder-like N8K/N8K2 plots."""

# 中文说明：applicable=True 的数据图不能是低颜色、低信息量或重复模板图。

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import read_json, write_json


DATA_REQUIRED_CATEGORIES = {
    "01_trajectory",
    "02_position_errors",
    "03_velocity",
    "04_attitude",
    "05_consistency",
    "06_observation_quality",
    "07_compare",
    "10_fgo_factors",
    "11_feedback",
    "12_legged_factors",
}

TEXT_PANEL_ALLOWED_CATEGORIES = {"09_case_review", "13_ablation_meta", "14_audit_sanity"}


def detect_placeholder_plots(
    *,
    n8k_root: str | Path,
    original_figure_root: str | Path,
    fixed_figure_root: str | Path,
) -> dict[str, Any]:
    catalog = read_json(Path(n8k_root) / "N8K_BY2_ABLATION_FULL_PLOT_CATALOG.json")
    original = _scan(catalog, Path(original_figure_root), "N8K_original")
    fixed = _scan(catalog, Path(fixed_figure_root), "N8K2_fixed")
    return {
        "stage": "N8K2",
        "original_placeholder_count": original["placeholder_like_count"],
        "original_applicable_placeholder_count": original["applicable_placeholder_count"],
        "fixed_placeholder_count": fixed["placeholder_like_count"],
        "fixed_applicable_placeholder_count": fixed["applicable_placeholder_count"],
        "applicable_placeholder_remaining": fixed["applicable_placeholder_count"],
        "original_duplicate_template_suspect_count": original["duplicate_template_suspect_count"],
        "fixed_duplicate_template_suspect_count": fixed["duplicate_template_suspect_count"],
        "duplicate_template_suspect_count": fixed["duplicate_template_suspect_count"],
        "original": original,
        "fixed": fixed,
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
    }


def write_placeholder_detection_report(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)


def _scan(catalog: dict[str, Any], root: Path, label: str) -> dict[str, Any]:
    findings = []
    by_variant_category_hash: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    placeholder_count = 0
    applicable_placeholder_count = 0
    for variant in catalog.get("variants", []):
        variant_id = str(variant.get("variant_id"))
        for item in variant.get("files", []):
            filename = str(item.get("filename"))
            if not filename.endswith(".png"):
                continue
            category = str(item.get("category"))
            applicable = bool(item.get("applicable", True))
            path = root / variant_id / category / filename
            meta = _image_meta(path)
            placeholder_like = _placeholder_like(meta, category, applicable)
            if placeholder_like:
                placeholder_count += 1
                if applicable and category in DATA_REQUIRED_CATEGORIES:
                    applicable_placeholder_count += 1
            if meta.get("color_count_approx", 999) < 24:
                by_variant_category_hash[(variant_id, category)][meta.get("perceptual_hash", "")].append(filename)
            findings.append(
                {
                    "variant_id": variant_id,
                    "category": category,
                    "filename": filename,
                    "applicable": applicable,
                    "present": meta["present"],
                    "file_size": meta["file_size"],
                    "color_count_approx": meta["color_count_approx"],
                    "variance": meta["variance"],
                    "placeholder_like": placeholder_like,
                    "reason": meta.get("reason", ""),
                }
            )
    duplicate_suspects = []
    for (variant_id, category), hashes in by_variant_category_hash.items():
        if category in TEXT_PANEL_ALLOWED_CATEGORIES:
            continue
        for phash, names in hashes.items():
            if phash and len(names) > 1:
                duplicate_suspects.append({"variant_id": variant_id, "category": category, "perceptual_hash": phash, "filenames": sorted(names)})
    return {
        "scan_label": label,
        "figure_root_role": "N8K_FIGURE_OUTPUT_DIR" if label == "N8K_original" else "N8K2_FIGURE_OUTPUT_DIR",
        "png_count_scanned": len(findings),
        "placeholder_like_count": placeholder_count,
        "applicable_placeholder_count": applicable_placeholder_count,
        "duplicate_template_suspect_count": len(duplicate_suspects),
        "duplicate_template_suspects": duplicate_suspects[:50],
        "findings_sample": findings[:40],
    }


def _image_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"present": False, "file_size": 0, "color_count_approx": 0, "variance": 0.0, "perceptual_hash": "", "reason": "missing"}
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            small = rgb.resize((64, 64))
            colors = small.getcolors(maxcolors=4096) or []
            stat = ImageStat.Stat(small)
            variance = sum(stat.var) / max(1, len(stat.var))
            phash = _average_hash(rgb)
            digest = hashlib.sha256(rgb.resize((32, 32)).tobytes()).hexdigest()[:16]
            return {
                "present": True,
                "file_size": path.stat().st_size,
                "dimensions": list(rgb.size),
                "color_count_approx": len(colors),
                "variance": float(variance),
                "perceptual_hash": phash,
                "content_digest": digest,
                "reason": "",
            }
    except Exception as exc:  # pragma: no cover - corrupt runtime images are rare.
        return {"present": True, "file_size": path.stat().st_size, "color_count_approx": 0, "variance": 0.0, "perceptual_hash": "", "reason": f"read_error:{exc}"}


def _placeholder_like(meta: dict[str, Any], category: str, applicable: bool) -> bool:
    if not meta.get("present"):
        return True
    if category in TEXT_PANEL_ALLOWED_CATEGORIES and not (applicable and category in DATA_REQUIRED_CATEGORIES):
        return False
    if not applicable:
        return False
    if category not in DATA_REQUIRED_CATEGORIES:
        return False
    return meta.get("color_count_approx", 0) < 24 or meta.get("variance", 0.0) < 4.0 or meta.get("file_size", 0) < 8_000


def _average_hash(image: Image.Image) -> str:
    gray = image.convert("L").resize((8, 8))
    values = list(gray.getdata())
    avg = sum(values) / len(values)
    bits = ["1" if value >= avg else "0" for value in values]
    return f"{int(''.join(bits), 2):016x}"
