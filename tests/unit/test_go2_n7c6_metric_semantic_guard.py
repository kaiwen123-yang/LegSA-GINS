from pathlib import Path

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import write_json
from legsa_gins.go2_prior.go2_n7c6_metric_semantic_guard import build_metric_semantic_guard_report


def test_metric_guard_marks_raw_error_names_for_replacement(tmp_path: Path) -> None:
    """中文说明：raw series 被命名为 error 时应要求 runtime replacement figure。"""
    write_json(tmp_path / "N7C6_FIGURE_MANIFEST.json", {"required_figures": ["clean_yaw_error_baseline_vs_joint.png"]})
    report = build_metric_semantic_guard_report(tmp_path)
    assert report["metric_semantic_status"] == "passed_with_runtime_replacements"
    assert report["original_issues"]
    assert report["go2_not_truth"] is True
