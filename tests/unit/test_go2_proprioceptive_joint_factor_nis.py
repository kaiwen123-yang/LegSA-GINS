"""Unit tests for N7C6 NIS diagnostics.

中文说明：测试 N7C6 residual/NIS proxy 统计。
"""

import csv

from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_nis import build_n7c6_joint_factor_nis_report


def test_joint_factor_nis_reads_source_trace(tmp_path):
    variant = tmp_path / "variants" / "joint_rp1p6deg_hv1p0"
    variant.mkdir(parents=True)
    with (variant / "SOURCE_AWARE_WEIGHT_TRACE.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "source_id", "combined_R_scale", "residual_norm", "normalized_innovation"])
        writer.writeheader()
        writer.writerow({"time": 0, "source_id": "go2_attitude_roll_pitch", "combined_R_scale": 1, "residual_norm": 0.01, "normalized_innovation": 0.5})
        writer.writerow({"time": 0, "source_id": "go2_horizontal_velocity", "combined_R_scale": 1, "residual_norm": 0.2, "normalized_innovation": 0.8})
    report = build_n7c6_joint_factor_nis_report(tmp_path, ["joint_rp1p6deg_hv1p0"])
    assert report["variants"]["joint_rp1p6deg_hv1p0"]["overconfidence_flag"] is False
    assert report["paper_performance_claim"] is False
