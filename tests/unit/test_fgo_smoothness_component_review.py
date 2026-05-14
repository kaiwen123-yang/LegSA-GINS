"""Tests for N8C2 smoothness component review.

中文说明：验证 smoothness 分量审查不把删除 smoothness 当最终捷径。
"""

from legsa_gins.fgo.fgo_smoothness_component_review import build_smoothness_component_review


def test_smoothness_component_review_keeps_smoothness_not_deleted() -> None:
    rows = [
        {"index": i, "time": float(i), "lat_deg": 30.0 + i * 1e-6, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.1 * i, "pitch_deg": 0.0, "yaw_deg": float(i), "vn_mps": 1.0, "ve_mps": 0.1, "vd_mps": 0.0}
        for i in range(6)
    ]
    report = build_smoothness_component_review(rows_by_variant={"weak_yaw_smoothness": rows})
    assert len(report["smoothness_component_rows"]) == 5
    assert not report["smoothness_deleted_as_final_shortcut"]
    assert "redesign smoothness as process/kinematic factor" in report["recommendations"]
