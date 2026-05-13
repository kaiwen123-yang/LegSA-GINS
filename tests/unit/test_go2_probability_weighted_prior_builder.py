"""N7B4 probability-weighted prior 单元测试：CSV 仅 runtime diagnostic。"""

from legsa_gins.go2_prior.go2_contact_confidence_features import build_contact_confidence_features
from legsa_gins.go2_prior.go2_contact_probability_model import build_contact_probability_models
from legsa_gins.go2_prior.go2_probability_weighted_prior_builder import build_probability_weighted_diagnostic_priors
from legsa_gins.go2_prior.go2_velocity_frame_internal_external_score import score_velocity_frames

from .test_go2_contact_confidence_features import _rows


def test_probability_weighted_prior_builder_writes_runtime_csvs(tmp_path):
    rows = _rows()
    for index, row in enumerate(rows):
        row["go2_position_0"] = index * 0.05
        row["go2_position_1"] = 0.0
        row["go2_position_2"] = 0.0
        row["roll_rad"] = 0.0
        row["pitch_rad"] = 0.0
        row["yaw_rad"] = 0.0
    features, _ = build_contact_confidence_features(rows)
    probs, prob_report = build_contact_probability_models(features)
    source = [{"time": row["time"], "vn": row["go2_velocity_0"], "ve": row["go2_velocity_1"], "vd": row["go2_velocity_2"]} for row in rows]
    frame = score_velocity_frames(go2_rows=rows, receiver_velocity_rows=source, raw_doppler_rows=source)
    paths, report = build_probability_weighted_diagnostic_priors(
        go2_rows=rows,
        frame_score_report=frame,
        probability_model_report=prob_report,
        probability_timeseries=probs,
        output_dir=tmp_path,
    )
    assert paths["probability_weighted"].exists()
    assert report["formal_activation_allowed"] is False
    assert report["diagnostic_only"] is True
