"""N7B5 horizontal prior builder 单元测试：vertical component 必须关闭。"""

import csv
import json

from legsa_gins.go2_prior.go2_horizontal_velocity_prior_builder import (
    build_horizontal_velocity_diagnostic_priors,
    build_n7c_horizontal_velocity_weak_priors,
)


def _go2_rows():
    return [
        {
            "time": index * 0.1,
            "aligned_time": index * 0.1,
            "roll_rad": 0.0,
            "pitch_rad": 0.0,
            "yaw_rad": 0.0,
            "go2_velocity_0": 1.0,
            "go2_velocity_1": 0.2,
            "go2_velocity_2": 0.3,
        }
        for index in range(10)
    ]


def _prob_rows():
    return [
        {
            "time": index * 0.1,
            "model_id": "force_speed_fused_probability",
            "support_probability": 0.7 if index % 2 == 0 else 0.45,
            "confidence_score": 0.55 if index % 2 == 0 else 0.35,
        }
        for index in range(10)
    ]


def test_horizontal_builder_writes_vertical_disabled_csv(tmp_path):
    paths, report = build_horizontal_velocity_diagnostic_priors(
        go2_rows=_go2_rows(),
        frame_equivalence_report={
            "primary_frame": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
            "secondary_frame": "yaw_only_rotation_diagnostic_only",
            "recommended_horizontal_policy": "use_best_frame_horizontal_only",
            "top_candidate_difference": {"horizontal_rmse_mps": 0.01},
        },
        frame_score_report={
            "best_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
            "second_best": "yaw_only_rotation_diagnostic_only",
            "candidates": {},
        },
        probability_model_report={
            "selected_contact_probability_model": "force_speed_fused_probability",
            "contact_probability_model_ready": True,
        },
        probability_timeseries=_prob_rows(),
        output_dir=tmp_path,
    )
    assert report["csv_generated"] is True
    assert report["vertical_velocity_disabled"] is True
    assert report["formal_activation_allowed"] is False
    with paths["best_frame_horizontal_only"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(float(row["std_vd"]) >= 999.0 for row in rows)
    assert all(row["go2_velocity_truth_claim"] == "False" or row["go2_velocity_truth_claim"] is False for row in rows)


def test_n7c_builder_promotes_horizontal_only_without_truth_claim(tmp_path):
    n7b5 = tmp_path / "n7b5"
    paths, _report = build_horizontal_velocity_diagnostic_priors(
        go2_rows=_go2_rows(),
        frame_equivalence_report={
            "primary_frame": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
            "secondary_frame": "yaw_only_rotation_diagnostic_only",
            "recommended_horizontal_policy": "use_best_frame_horizontal_only",
            "top_candidate_difference": {"horizontal_rmse_mps": 0.01},
        },
        frame_score_report={
            "best_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
            "second_best": "yaw_only_rotation_diagnostic_only",
            "candidates": {},
        },
        probability_model_report={
            "selected_contact_probability_model": "force_speed_fused_probability",
            "contact_probability_model_ready": True,
        },
        probability_timeseries=_prob_rows(),
        output_dir=n7b5,
    )
    assert paths["best_frame_horizontal_only"].exists()
    prior_paths, report = build_n7c_horizontal_velocity_weak_priors(n7b5_root=n7b5, output_dir=tmp_path / "n7c")
    assert report["csv_generated"] is True
    assert report["controlled_activation_allowed"] is True
    assert report["vertical_velocity_disabled"] is True
    assert report["go2_velocity_truth_claim"] is False
    rows = list(csv.DictReader(prior_paths["main"].open("r", encoding="utf-8-sig", newline="")))
    assert rows
    assert set(rows[0]) >= {"vn", "ve", "std_vd", "go2_velocity_truth_claim"}
    assert all(float(row["std_vd"]) >= 999.0 for row in rows)
    assert json.loads((tmp_path / "n7c" / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json").read_text(encoding="utf-8"))["paper_performance_claim"] is False
