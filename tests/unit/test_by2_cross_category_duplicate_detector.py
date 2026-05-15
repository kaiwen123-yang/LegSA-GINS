from pathlib import Path

from PIL import Image

from legsa_gins.reporting.by2_cross_category_duplicate_detector import build_cross_category_decision, scan_cross_category_duplicates

# 中文说明：N8K5 detector 必须识别同一 variant 内跨 category 的阻塞 exact duplicate。


def _png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 36), color).save(path)


def test_scan_cross_category_duplicates_blocks_velocity_pair(tmp_path):
    root = tmp_path / "fig"
    duplicate = (80, 40, 120)
    _png(root / "V0" / "03_velocity" / "velocity_residual_time.png", duplicate)
    _png(root / "V0" / "07_compare" / "compare_velocity_error.png", duplicate)
    _png(root / "V0" / "07_compare" / "compare_horizontal_error.png", (10, 20, 30))

    report = scan_cross_category_duplicates(root)
    assert report["same_variant_cross_category_duplicate_count"] == 1
    assert report["blocking_patterns"][0]["affected_variant_count"] == 1


def test_build_cross_category_decision_passes_when_blockers_clear():
    fix = {"semantic_mismatch_after_count": 0}
    duplicate = {"blocking_cross_category_duplicate_patterns_after": [], "same_variant_cross_category_duplicate_after": 0}
    coverage = {"feedback_empty_axis_after_count": 0}
    decision = build_cross_category_decision(fix, duplicate, coverage)
    assert decision["status"] == "BY2_formal_ablation_cross_category_semantic_fix_complete"
