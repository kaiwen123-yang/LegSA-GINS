"""Go2 sportmodestate parser for high-level body source fields."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Go2BodyEpoch:
    time: float
    yaw_speed_rad_s: float
    mode: int | None
    gait_type: int | None


def parse_go2_body(path: Path, *, max_epochs: int | None = None) -> list[Go2BodyEpoch]:
    epochs: list[Go2BodyEpoch] = []
    sec = nanosec = mode = gait_type = None
    in_stamp = False
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line == "stamp:":
                in_stamp = True
                sec = nanosec = mode = gait_type = None
            elif in_stamp and line.startswith("sec:"):
                sec = _to_int(line.split(":", 1)[1])
            elif in_stamp and line.startswith("nanosec:"):
                nanosec = _to_int(line.split(":", 1)[1])
                in_stamp = False
            elif line.startswith("mode:"):
                mode = _to_int(line.split(":", 1)[1])
            elif line.startswith("gait_type:"):
                gait_type = _to_int(line.split(":", 1)[1])
            elif line.startswith("yaw_speed:"):
                yaw_speed = _to_float(line.split(":", 1)[1])
                if sec is not None and nanosec is not None and yaw_speed is not None:
                    epochs.append(Go2BodyEpoch(float(sec) + float(nanosec) * 1e-9, yaw_speed, mode, gait_type))
                    if max_epochs is not None and len(epochs) >= max_epochs:
                        break
    return epochs


def summarize_go2_body(epochs: list[Go2BodyEpoch]) -> dict[str, str]:
    return {
        "epoch_count": str(len(epochs)),
        "has_yaw_speed": str(bool(epochs)).lower(),
        "receiver_imu_as_body_imu": "false",
        "go2_position_velocity_yaw_truth": "false",
        "source_role": "sportmodestate_high_level_body_source_not_truth",
    }


def _to_int(text: str) -> int | None:
    try:
        return int(text.strip())
    except ValueError:
        return None


def _to_float(text: str) -> float | None:
    try:
        return float(text.strip())
    except ValueError:
        return None
