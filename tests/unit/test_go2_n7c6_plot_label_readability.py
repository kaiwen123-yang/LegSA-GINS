from pathlib import Path

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import write_json
from legsa_gins.go2_prior.go2_n7c6_plot_label_readability import build_plot_label_readability_report, shorten_variant_label


def test_short_variant_label_mapping() -> None:
    """中文说明：长 variant id 必须缩短成图上可读标签。"""
    assert shorten_variant_label("joint_rp1deg_hv1p0") == "rp1.0/hv1.0"
    assert shorten_variant_label("joint_rp1p6deg_hv1p0_sourceaware_off") == "rp1.6/hv1.0 SA-off"


def test_readability_detects_long_labels(tmp_path: Path) -> None:
    write_json(tmp_path / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json", {"matrix": [{"variant_id": "joint_rp1p6deg_hv1p0_sourceaware_off"}]})
    report = build_plot_label_readability_report(tmp_path)
    assert report["long_label_truncation_risk"] is True
    assert report["replacement_figures_required"] is True
