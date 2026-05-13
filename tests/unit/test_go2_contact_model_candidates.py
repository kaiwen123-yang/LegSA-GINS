"""中文说明：N7B3 contact candidates 来自 Go2 field distributions only。"""

from legsa_gins.go2_prior.go2_contact_model_candidates import MODEL_IDS, build_contact_model_candidates


def _rows():
    out = []
    for index in range(24):
        row = {
            "time": index * 0.1,
            "aligned_time": index * 0.1,
            "mode": "walk",
            "gait_type": "trot",
            "go2_velocity_0": 1.0,
            "go2_velocity_1": 0.2,
            "go2_velocity_2": 0.1,
        }
        pair = (0, 3) if index % 2 == 0 else (1, 2)
        for foot in range(4):
            row[f"foot_force_{foot}"] = 30.0 if foot in pair else 2.0
            for axis in range(3):
                row[f"foot_speed_body_{3 * foot + axis}"] = 0.05 if foot in pair and axis == 0 else (1.1 if axis == 0 else 0.0)
        out.append(row)
    return out


def test_contact_model_candidates_include_all_models_and_boundaries():
    rows, report = build_contact_model_candidates(_rows())
    assert report["candidate_models"] == MODEL_IDS
    assert len({row["candidate_model"] for row in rows}) == len(MODEL_IDS)
    assert report["threshold_source"] == "go2_field_distribution_only"
    assert report["trace_solver_input"] is False
    assert report["final_v23_output_solver_input"] is False
