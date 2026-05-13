"""中文说明：N7B3 velocity prior CSV 是 runtime-only diagnostic evidence。"""

import csv

from legsa_gins.go2_prior.go2_velocity_prior_diagnostic_builder import build_go2_velocity_diagnostic_priors


def test_velocity_prior_builder_writes_diagnostic_csvs(tmp_path):
    go2_rows = [
        {
            "time": 0.0,
            "aligned_time": 0.0,
            "go2_velocity_0": 1.0,
            "go2_velocity_1": 0.2,
            "go2_velocity_2": 0.1,
            "roll_rad": 0.0,
            "pitch_rad": 0.0,
            "yaw_rad": 0.0,
        }
    ]
    contact_rows = [
        {
            "candidate_model": "v3_force_speed_joint",
            "time": 0.0,
            "contact_label": "walking_contact",
            "contact_count": 2,
        }
    ]
    paths, report = build_go2_velocity_diagnostic_priors(
        go2_rows=go2_rows,
        velocity_frame_report={
            "recommended_frame_for_diagnostic_prior": "go2_velocity_as_world_enu_or_ned_direct",
            "frame_ambiguity_status": "resolved_for_diagnostic_prior",
            "rmse_to_receiver": 1.2,
            "rmse_to_raw": 1.5,
        },
        contact_model_comparison={
            "contact_model_ready": True,
            "selected_diagnostic_contact_model": "v3_force_speed_joint",
        },
        candidate_timeseries=contact_rows,
        output_dir=tmp_path,
    )
    assert report["prior_csv_generated"] is True
    assert report["contact_gated_epoch_count"] == 1
    with paths["contact_gated"].open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["diagnostic_only"] == "True"
    assert rows[0]["go2_velocity_truth_claim"] == "False"
