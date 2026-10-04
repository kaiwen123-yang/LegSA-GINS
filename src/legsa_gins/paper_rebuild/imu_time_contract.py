"""Explicit measured-duration IMU contract and fail-closed missing-data segments.

The original seven increment tokens remain untouched. No rate is held, scaled,
or interpolated across unavailable raw intervals. Segment restart is a declared
engineering strategy, never a reconstruction of the missing motion.
"""
from __future__ import annotations

import math
from pathlib import Path

from ..input_generation.imu_txt_builder import build_process_data_imu_rows

TIME_TOKEN_TOLERANCE = 1.1e-6  # two independently rounded six-decimal timestamps


def bind_measured_durations(payload: str, measured_rows: list[dict]) -> list[dict]:
    lines = [line for line in payload.splitlines() if line.strip() and not line.startswith('#')]
    if len(lines) != len(measured_rows):
        raise ValueError('IMU_DURATION_ROW_COUNT_MISMATCH')
    result = []
    for index, (line, measured) in enumerate(zip(lines, measured_rows)):
        tokens = line.split()
        if len(tokens) != 7 or not all(math.isfinite(float(t)) for t in tokens):
            raise ValueError('IMU_EXPECTED_FINITE_SEVEN_COLUMNS')
        dt = float(measured['dt'])
        time = float(tokens[0])
        if not 0 < dt <= .1 or abs(time - measured['time']) > TIME_TOKEN_TOLERANCE:
            raise ValueError('IMU_RAW_DURATION_MAPPING_MISMATCH')
        if index and time <= result[-1]['time']:
            raise ValueError('IMU_TIME_NOT_STRICTLY_INCREASING')
        # Check gyro lineage without comparing/calibrating against a trajectory.
        for token, key in zip(tokens[1:4], ('dtheta_x', 'dtheta_y', 'dtheta_z')):
            if abs(float(token) - float(measured[key])) > 5.1e-9:
                raise ValueError('IMU_GYRO_INCREMENT_LINEAGE_MISMATCH')
        result.append({'time': time, 'dt': dt, 'legacy_line': line,
                       'line': line + ' ' + format(dt, '.17g') + '\n', 'source_row': index + 1})
    return result


def read_raw_duration_contract(body: Path, legacy_imu: Path, *, base_time: float):
    measured, report = build_process_data_imu_rows(body, base_time=base_time)
    rows = bind_measured_durations(legacy_imu.read_text(), measured)
    return rows, report


def continuous_segments(rows: list[dict], *, start: float, end: float):
    """Retain all observed rows, partition only from input-side duration mismatch."""
    selected = [r for r in rows if start <= r['time'] <= end]
    segments, gaps = [], []
    for row in selected:
        if not segments:
            segments.append([row])
            continue
        previous = segments[-1][-1]
        elapsed = row['time'] - previous['time']
        missing = elapsed - row['dt']
        if missing < -TIME_TOKEN_TOLERANCE:
            raise ValueError('IMU_DURATION_OVERLAPS_PREVIOUS_ROW')
        if missing > TIME_TOKEN_TOLERANCE:
            gaps.append({'previous_time': previous['time'], 'next_time': row['time'],
                         'measured_dt': row['dt'], 'missing_duration': missing,
                         'source_row': row['source_row'], 'policy': 'STOP_AND_REINITIALIZE'})
            segments.append([row])
        else:
            segments[-1].append(row)
    return segments, gaps


def write_segment(path: Path, rows: list[dict]):
    if len(rows) < 2:
        raise ValueError('IMU_SEGMENT_HAS_NO_PROPAGATION_SUPPORT')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write('# IMU8: time dtheta_xyz dvel_xyz measured_dt; strict continuity\n')
        stream.writelines(row['line'] for row in rows)
