"""CLEAN1R1C initialization must never consume a future observation."""

import pytest

from scripts.paper_rebuild.generate_clean1_by2_inputs import (
    _initialization_provenance,
    _select_initialization_epochs,
)


def _gnss(time_value: float, *, position: int, velocity: int, yaw: int) -> list[float]:
    row = [0.0] * 18
    row[0] = time_value
    row[15] = float(position)
    row[16] = float(velocity)
    row[17] = float(yaw)
    return row


def test_optional_stream_late_does_not_move_or_peek_past_start() -> None:
    gnss = [
        _gnss(9.0, position=1, velocity=1, yaw=1),
        _gnss(10.0, position=1, velocity=0, yaw=1),
        _gnss(11.0, position=1, velocity=1, yaw=1),
    ]
    attitude = [
        {"time": "9.5", "source_status": "active"},
        {"time": "10.5", "source_status": "active"},
    ]

    start, velocity, roll_pitch = _select_initialization_epochs(
        gnss, attitude, 10.0
    )

    assert start[0] == 10.0
    assert velocity[0] == 9.0
    assert float(roll_pitch["time"]) == 9.5
    provenance = _initialization_provenance(start, velocity, roll_pitch)
    assert provenance == {
        "position_velocity_source_role": (
            "gnss_position_exact_common_start_and_receiver_velocity_"
            "latest_valid_at_or_before_common_start"
        ),
        "position_source_role": "gnss_position_exact_common_start",
        "velocity_source_role": (
            "gnss_receiver_velocity_latest_valid_at_or_before_common_start"
        ),
        "roll_pitch_source_role": (
            "go2_body_attitude_latest_valid_at_or_before_common_start"
        ),
        "position_initialization_timestamp": 10.0,
        "velocity_initialization_timestamp": 9.0,
        "roll_pitch_initialization_timestamp": 9.5,
        "yaw_initialization_timestamp": 10.0,
        "future_observation_used_for_initialization": False,
    }


def test_missing_historical_velocity_fails_instead_of_using_future() -> None:
    gnss = [
        _gnss(10.0, position=1, velocity=0, yaw=1),
        _gnss(11.0, position=1, velocity=1, yaw=1),
    ]
    with pytest.raises(
        RuntimeError,
        match="BLOCKED_CLEAN1_WINDOW_OR_INITIALIZATION_CONTRACT_FAILED",
    ):
        _select_initialization_epochs(
            gnss,
            [{"time": "9.5", "source_status": "active"}],
            10.0,
        )
