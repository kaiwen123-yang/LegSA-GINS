"""中文说明：测试 R3 evaluator 的 gate 语义，尤其 yaw 不允许 >2 度通过。"""

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import summarize_port_errors


def _err(yaw: float = 1.0, roll: float = 1.2, pitch: float = 1.2):
    return {
        "timestamp": 0.0,
        "reference_timestamp": 0.0,
        "dt": 0.0,
        "north_error_m": 0.2,
        "east_error_m": 0.1,
        "up_error_m": 0.5,
        "horizontal_error_m": 0.2236,
        "roll_error_deg": roll,
        "pitch_error_deg": pitch,
        "yaw_error_deg": yaw,
    }


def test_summary_gates_pass_relaxed_roll_pitch():
    summary = summarize_port_errors([_err() for _ in range(10)])
    assert summary["horizontal_gate_pass"] is True
    assert summary["up_gate_pass"] is True
    assert summary["yaw_gate_pass"] is True
    assert summary["roll_strict_pass"] is False
    assert summary["roll_relaxed_pass"] is True
    assert summary["pitch_strict_pass"] is False
    assert summary["pitch_relaxed_pass"] is True


def test_yaw_above_two_degrees_not_pass():
    summary = summarize_port_errors([_err(yaw=2.05) for _ in range(10)])
    assert summary["yaw_gate_pass"] is False
