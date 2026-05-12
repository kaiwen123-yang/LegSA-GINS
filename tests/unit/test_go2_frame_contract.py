"""中文说明：frame contract 可阻止不一致的 Go2 attitude prior。"""

from legsa_gins.go2_state.go2_frame_contract import build_frame_contract_report


def test_go2_frame_contract_blocks_when_quaternion_failed():
    rows = [{"roll_rad": "0.01", "pitch_rad": "0.02"}, {"roll_rad": "0.02", "pitch_rad": "0.03"}]
    report = build_frame_contract_report(rows, {"activation_allowed_for_attitude_prior": False})
    assert report["go2_body_frame"] == "FLU"
    assert report["activation_allowed"] is False
    assert "quaternion_rpy_internal_consistency_failed" in report["blocker_reasons"]
