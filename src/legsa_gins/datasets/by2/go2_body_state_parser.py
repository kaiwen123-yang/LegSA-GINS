"""BY2 Go2 sportmodestate diagnostic parser.

中文说明：
Go2 body / IMU frame 视为 FLU；sportmodestate position/velocity 是 Go2 odom，不得直接当 NED navigation measurement。
foot_position_body 与 foot_speed_body 是 body-relative；N4E 只 diagnostic，不进入 solver，后续必须经过 frame adapter。
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.unitree_imu_semantics import check_quaternion_rpy_consistency


SOURCE_ROLE = "go2_body_state_diagnostic"

ARRAY_FIELDS = {
    "quaternion": 4,
    "gyroscope": 3,
    "accelerometer": 3,
    "rpy": 3,
    "position": 3,
    "velocity": 3,
    "foot_force": 4,
    "foot_position_body": 12,
    "foot_speed_body": 12,
}

STANDARD_HEADER = [
    "timestamp",
    "stamp_sec",
    "stamp_nanosec",
    "error_code",
    "quat_w",
    "quat_x",
    "quat_y",
    "quat_z",
    "quat_0",
    "quat_1",
    "quat_2",
    "quat_3",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "acc_x",
    "acc_y",
    "acc_z",
    "roll_rad",
    "pitch_rad",
    "yaw_rad",
    "temperature",
    "mode",
    "gait_type",
    "foot_raise_height",
    "go2_position_0",
    "go2_position_1",
    "go2_position_2",
    "go2_velocity_0",
    "go2_velocity_1",
    "go2_velocity_2",
    "yaw_speed_radps",
    "foot_force_0",
    "foot_force_1",
    "foot_force_2",
    "foot_force_3",
    *[f"foot_position_body_{index}" for index in range(12)],
    *[f"foot_speed_body_{index}" for index in range(12)],
    "quaternion_order",
    "gyro_unit",
    "accel_unit",
    "accel_contains_gravity",
    "rpy_order",
    "rpy_unit",
    "go2_body_frame",
    "sportmodestate_position_frame",
    "sportmodestate_velocity_frame",
    "foot_position_body_frame",
    "foot_speed_body_frame",
    "quaternion_rpy_consistency_status",
    "max_quat_rpy_delta_rad",
    "source_role",
    "body_frame",
    "frame_adapter_required",
    "position_velocity_navigation_measurement",
]


def _split_messages(text: str) -> list[list[str]]:
    messages: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == "---":
            if current:
                messages.append(current)
                current = []
            continue
        current.append(line.rstrip("\n"))
    if current:
        messages.append(current)
    return [message for message in messages if any(line.strip() for line in message)]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _inline_numbers(value: str) -> list[float] | None:
    stripped = value.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return None
    body = stripped[1:-1].strip()
    if not body:
        return []
    return [_to_float(part.strip()) for part in body.split(",")]


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip().strip("'\"")
    if stripped == "":
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    parsed = _to_float(value)
    return None if parsed is None else int(parsed)


def _find_path_line(lines: list[str], path: list[str]) -> tuple[int, int, str] | None:
    start = 0
    end = len(lines)
    parent_indent = -1
    found: tuple[int, int, str] | None = None
    for key in path:
        found = None
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*)$")
        for index in range(start, end):
            line = lines[index]
            if _indent(line) <= parent_indent:
                continue
            match = pattern.match(line)
            if match:
                found = (index, _indent(line), match.group(1))
                break
        if found is None:
            return None
        line_index, line_indent, _value = found
        block_end = len(lines)
        for next_index in range(line_index + 1, len(lines)):
            if lines[next_index].strip() and _indent(lines[next_index]) <= line_indent:
                block_end = next_index
                break
        start = line_index + 1
        end = block_end
        parent_indent = line_indent
    return found


def _scalar(lines: list[str], path: list[str]) -> str | None:
    found = _find_path_line(lines, path)
    if found is None:
        return None
    value = found[2].strip()
    return value if value != "" else None


def _array(lines: list[str], path: list[str], expected: int) -> list[float | None]:
    found = _find_path_line(lines, path)
    values: list[float | None] = []
    if found is not None:
        line_index, line_indent, inline = found
        inline_values = _inline_numbers(inline)
        if inline_values is not None:
            values.extend(inline_values)
        else:
            for next_index in range(line_index + 1, len(lines)):
                line = lines[next_index]
                stripped = line.strip()
                if stripped.startswith("-"):
                    values.append(_to_float(stripped[1:].strip()))
                    continue
                if stripped and _indent(line) <= line_indent:
                    break
    while len(values) < expected:
        values.append(None)
    return values[:expected]


def _message_to_row(lines: list[str]) -> dict[str, Any]:
    sec = _to_int(_scalar(lines, ["stamp", "sec"]))
    nanosec = _to_int(_scalar(lines, ["stamp", "nanosec"]))
    timestamp = None
    if sec is not None and nanosec is not None:
        timestamp = sec + nanosec * 1.0e-9

    quat = _array(lines, ["imu_state", "quaternion"], ARRAY_FIELDS["quaternion"])
    gyro = _array(lines, ["imu_state", "gyroscope"], ARRAY_FIELDS["gyroscope"])
    acc = _array(lines, ["imu_state", "accelerometer"], ARRAY_FIELDS["accelerometer"])
    rpy = _array(lines, ["imu_state", "rpy"], ARRAY_FIELDS["rpy"])
    position = _array(lines, ["position"], ARRAY_FIELDS["position"])
    velocity = _array(lines, ["velocity"], ARRAY_FIELDS["velocity"])
    foot_force = _array(lines, ["foot_force"], ARRAY_FIELDS["foot_force"])
    foot_position_body = _array(
        lines, ["foot_position_body"], ARRAY_FIELDS["foot_position_body"]
    )
    foot_speed_body = _array(lines, ["foot_speed_body"], ARRAY_FIELDS["foot_speed_body"])

    row: dict[str, Any] = {
        "timestamp": timestamp,
        "stamp_sec": sec,
        "stamp_nanosec": nanosec,
        "error_code": _to_int(_scalar(lines, ["error_code"])),
        "quat_w": quat[0],
        "quat_x": quat[1],
        "quat_y": quat[2],
        "quat_z": quat[3],
        "quat_0": quat[0],
        "quat_1": quat[1],
        "quat_2": quat[2],
        "quat_3": quat[3],
        "gyro_x": gyro[0],
        "gyro_y": gyro[1],
        "gyro_z": gyro[2],
        "acc_x": acc[0],
        "acc_y": acc[1],
        "acc_z": acc[2],
        "roll_rad": rpy[0],
        "pitch_rad": rpy[1],
        "yaw_rad": rpy[2],
        "temperature": _to_float(_scalar(lines, ["imu_state", "temperature"])),
        "mode": _to_int(_scalar(lines, ["mode"])),
        "gait_type": _to_int(_scalar(lines, ["gait_type"])),
        "foot_raise_height": _to_float(_scalar(lines, ["foot_raise_height"])),
        "go2_position_0": position[0],
        "go2_position_1": position[1],
        "go2_position_2": position[2],
        "go2_velocity_0": velocity[0],
        "go2_velocity_1": velocity[1],
        "go2_velocity_2": velocity[2],
        "yaw_speed_radps": _to_float(_scalar(lines, ["yaw_speed"])),
        "foot_force_0": foot_force[0],
        "foot_force_1": foot_force[1],
        "foot_force_2": foot_force[2],
        "foot_force_3": foot_force[3],
        "quaternion_order": "wxyz",
        "gyro_unit": "rad_per_sec",
        "accel_unit": "m_per_s2",
        "accel_contains_gravity": True,
        "rpy_order": "roll_pitch_yaw",
        "rpy_unit": "rad",
        "go2_body_frame": "FLU",
        "sportmodestate_position_frame": "go2_odom",
        "sportmodestate_velocity_frame": "go2_odom_or_body_evidence_missing",
        "foot_position_body_frame": "body_relative",
        "foot_speed_body_frame": "body_relative",
        "source_role": SOURCE_ROLE,
        "body_frame": "FLU",
        "frame_adapter_required": True,
        "position_velocity_navigation_measurement": False,
    }
    for index, value in enumerate(foot_position_body):
        row[f"foot_position_body_{index}"] = value
    for index, value in enumerate(foot_speed_body):
        row[f"foot_speed_body_{index}"] = value
    row.update(check_quaternion_rpy_consistency(row))
    return row


def parse_go2_body_state_text(
    path: str | Path, *, max_messages: int | None = None
) -> list[dict[str, Any]]:
    """Parse ros2 topic echo sportmodestate text into diagnostic rows."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    rows: list[dict[str, Any]] = []
    previous_timestamp: float | None = None
    for index, message in enumerate(_split_messages(text)):
        if max_messages is not None and index >= max_messages:
            break
        row = _message_to_row(message)
        timestamp = row.get("timestamp")
        if timestamp is not None and previous_timestamp is not None and timestamp < previous_timestamp:
            raise ValueError("Go2 body-state timestamp must be monotonic non-decreasing.")
        if timestamp is not None:
            previous_timestamp = timestamp
        rows.append(row)
    return rows


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def write_go2_body_state_csv(rows: list[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARD_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in STANDARD_HEADER})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="BY2 Go2/body-state text input.")
    parser.add_argument("--output", required=True, help="Diagnostic CSV output path.")
    parser.add_argument("--max-messages", type=int, default=None, help="Optional message limit.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rows = parse_go2_body_state_text(args.input, max_messages=args.max_messages)
    write_go2_body_state_csv(rows, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
