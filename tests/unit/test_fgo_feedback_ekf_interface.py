"""中文说明：单测 runtime feedback config 生成，不写 tracked 绝对路径。"""

from pathlib import Path

from legsa_gins.fgo_feedback.feedback_state_types import FeedbackVariantSpec
from legsa_gins.fgo_feedback.fgo_feedback_ekf_interface import append_feedback_config, feedback_interface_contract


def test_feedback_config_appends_runtime_path(tmp_path: Path):
    config = tmp_path / "run.conf"
    config.write_text("imupath: input.imu\ngnsspath: input.gnss\n", encoding="utf-8")
    append_feedback_config(
        config,
        observation_path=tmp_path / "FGO_FEEDBACK_OBSERVATIONS.csv",
        variant=FeedbackVariantSpec("v", "velocity_attitude_feedback", velocity_enabled=True, attitude_enabled=True),
    )
    text = config.read_text(encoding="utf-8")
    assert "enable_fgo_feedback: true" in text
    assert feedback_interface_contract()["fgo_feedback_enters_ekf_update"] is True
