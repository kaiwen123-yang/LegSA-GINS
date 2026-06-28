"""Helpers for PAPER10M1R2A V2 generated manifest tests."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest


def stage_root() -> Path:
    value = os.environ.get("PAPER10M1R2A_V2_STAGE_ROOT")
    if not value:
        pytest.skip("PAPER10M1R2A_V2_STAGE_ROOT is not set")
    root = Path(value)
    if not root.exists():
        pytest.skip(f"PAPER10M1R2A_V2_STAGE_ROOT does not exist: {root}")
    return root


def read_csv(relative: str) -> list[dict[str, str]]:
    path = stage_root() / relative
    assert path.exists(), f"missing generated CSV: {relative}"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_text(relative: str) -> str:
    path = stage_root() / relative
    assert path.exists(), f"missing generated text file: {relative}"
    return path.read_text(encoding="utf-8")


def read_json(relative: str):
    path = stage_root() / relative
    assert path.exists(), f"missing generated JSON: {relative}"
    return json.loads(path.read_text(encoding="utf-8"))


EXPECTED_DEGRADATION_NAMES = [
    "GNSS_position_outage_3s",
    "GNSS_position_outage_5s",
    "GNSS_position_outage_10s",
    "GNSS_position_outage_20s",
    "GNSS_position_velocity_outage_10s",
    "GNSS_all_update_outage_20s",
    "GNSS_repeated_short_outage",
    "GNSS_downsample_5Hz",
    "GNSS_downsample_2Hz",
    "GNSS_downsample_1Hz",
    "GNSS_random_dropout_30",
    "GNSS_random_dropout_60",
    "position_noise_mild",
    "position_noise_medium",
    "position_noise_strong",
    "position_static_bias_1p5m",
    "position_static_bias_3m",
    "position_slow_drift_bias",
    "position_sinusoidal_multipath",
    "position_spike_mild",
    "position_spike_medium",
    "position_spike_burst_strong",
    "position_std_inflation_1p5",
    "position_std_inflation_2p5",
    "position_std_inflation_4p0",
    "position_std_deflation_0p25",
    "bad_position_optimistic_std",
    "good_position_pessimistic_std",
    "gnss_status_quality_downgrade_only",
    "dual_yaw_outage_5s",
    "dual_yaw_outage_20s",
    "dual_yaw_noise_mild",
    "dual_yaw_noise_strong",
    "dual_yaw_spike_5pct",
    "dual_yaw_spike_10pct",
    "dual_yaw_std_inflation_1p5",
    "dual_yaw_std_inflation_3p0",
    "bad_yaw_optimistic_std",
    "baseline_quality_dropout",
    "baseline_length_jitter_relacc",
    "gnss1_gnss2_asymmetric_noise",
    "receiver_velocity_outage_20s",
    "receiver_velocity_noise_0p5",
    "receiver_velocity_spike_2mps",
    "receiver_velocity_bad_optimistic_std",
    "raw_doppler_outage_20s",
    "raw_doppler_noise_0p5",
    "raw_doppler_spike_1p5mps",
    "raw_doppler_bad_optimistic_std",
    "raw_receiver_velocity_conflict",
    "go2_roll_pitch_dropout_noise",
    "go2_roll_pitch_bias",
    "go2_horizontal_velocity_noise",
    "go2_horizontal_velocity_scale_dropout",
    "go2_contact_motion_metadata_uncertain",
    "go2_foot_speed_contact_conflict",
    "multi_source_latency_jitter",
    "outage_yaw_spike_then_recovery",
    "bad_position_good_yaw_raw_conflict",
    "multisource_bad_optimistic_then_recovery",
]


EXPECTED_TYPE_IDS = [f"D{i:02d}" for i in range(1, 61)]


EXPECTED_SEEDS = [
    ("seed_00", "260306001"),
    ("seed_01", "260306002"),
    ("seed_02", "260306003"),
    ("seed_03", "260306004"),
    ("seed_04", "260306005"),
    ("seed_05", "260306006"),
    ("seed_06", "260306007"),
    ("seed_07", "260306008"),
    ("seed_08", "260306009"),
]
