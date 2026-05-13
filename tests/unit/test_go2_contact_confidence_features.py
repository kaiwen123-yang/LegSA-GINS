"""N7B4 contact confidence feature 单元测试：特征只来自 Go2 fields。"""

from legsa_gins.go2_prior.go2_contact_confidence_features import build_contact_confidence_features


def _rows():
    rows = []
    for index in range(8):
        row = {
            "time": index * 0.1,
            "aligned_time": index * 0.1,
            "go2_velocity_0": 0.5,
            "go2_velocity_1": 0.1,
            "go2_velocity_2": 0.0,
            "yaw_speed_radps": 0.02,
            "mode": "walk",
            "gait_type": "trot",
            "body_height": 0.32,
        }
        pair = (0, 3) if index % 2 == 0 else (1, 2)
        for foot in range(4):
            row[f"foot_force_{foot}"] = 35.0 if foot in pair else 2.0
            row[f"foot_position_body_{3 * foot + 2}"] = -0.3
            row[f"foot_speed_body_{3 * foot + 0}"] = 0.05 if foot in pair else 1.0
            row[f"foot_speed_body_{3 * foot + 1}"] = 0.0
            row[f"foot_speed_body_{3 * foot + 2}"] = 0.0
        rows.append(row)
    return rows


def test_contact_confidence_features_cover_each_foot():
    features, report = build_contact_confidence_features(_rows())
    assert len(features) == 32
    assert report["diagnostic_only"] is True
    assert "does not automatically mean swing" in report["foot_speed_body_interpretation"]
