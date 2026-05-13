"""Unit tests for N7C2 visual overlap audit.

中文说明：验证重合曲线解释和 delta/zoom 门禁。
"""

from legsa_gins.go2_prior.go2_n7c_visual_overlap_audit import build_n7c2_visual_overlap_audit


def _rows(offset: float):
    return [
        {
            "time": f"{index * 0.2:.3f}",
            "lat_deg": f"{39.0 + index * 1.0e-9 + offset:.12f}",
            "lon_deg": f"{116.0 + index * 1.0e-9 + offset:.12f}",
            "height_m": f"{40.0 + offset:.12f}",
            "roll_deg": f"{offset:.12f}",
            "pitch_deg": f"{offset:.12f}",
            "yaw_deg": f"{1.0 + offset:.12f}",
        }
        for index in range(120)
    ]


def test_overlap_audit_explains_near_identical_curves():
    report = build_n7c2_visual_overlap_audit({"baseline_eval_nav": _rows(0.0), "main_eval_nav": _rows(1.0e-12)})
    assert report["summary"]["item_count"] == 5
    assert report["summary"]["all_overlaps_explained"]
    assert report["summary"]["delta_zoom_required"]
    overlapped = [
        item
        for item in report["overlap_items"]
        if item["visible_difference_status"] in {"mostly_overlapped", "identical_or_near_identical"}
    ]
    assert overlapped
    assert all("overlap_due_to_small_effect" in item["reason_codes"] for item in overlapped)
    assert not any(item["overlap_is_failure"] for item in report["overlap_items"])
    assert report["paper_performance_claim"] is False
