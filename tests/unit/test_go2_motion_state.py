"""中文说明：motion state 使用 Go2 高层状态，不读取 trace。"""

from legsa_gins.go2_prior.go2_motion_state import analyze_motion_state, classify_motion_state


def test_go2_motion_state_classifies_turn_and_standing():
    standing = {
        "go2_velocity_0": 0.01,
        "go2_velocity_1": 0.0,
        "go2_velocity_2": 0.0,
        "yaw_speed_radps": 0.0,
        **{f"foot_force_{i}": 20.0 for i in range(4)},
    }
    turning = dict(standing, go2_velocity_0=0.02, yaw_speed_radps=0.5)
    assert classify_motion_state(standing) == "standing"
    assert classify_motion_state(turning) == "turn_in_place"
    _, report = analyze_motion_state([standing, turning])
    assert report["standing_ratio"] == 0.5
    assert report["trace_solver_input"] is False
