"""Deterministic BY2 classic case manifest for external literature runs."""

from __future__ import annotations


CLASSIC_CASES: list[dict[str, str]] = [
    {"case_id": "C00_clean_normal", "case_family": "normal", "case_spec": "clean_normal"},
    {"case_id": "C01_outage_10s", "case_family": "outage", "case_spec": "yaw_and_position_outage_10s_midrun"},
    {"case_id": "C02_downsample_2Hz", "case_family": "downsample", "case_spec": "measurement_downsample_2Hz"},
    {"case_id": "C03_downsample_1Hz", "case_family": "downsample", "case_spec": "measurement_downsample_1Hz"},
    {"case_id": "C04_position_noise_medium_seed0", "case_family": "position_noise", "case_spec": "medium_position_noise_seed0"},
    {"case_id": "C05_position_noise_medium_seed1", "case_family": "position_noise", "case_spec": "medium_position_noise_seed1"},
    {"case_id": "C06_position_noise_medium_seed2", "case_family": "position_noise", "case_spec": "medium_position_noise_seed2"},
    {"case_id": "C07_position_spike_medium_seed0", "case_family": "position_spike", "case_spec": "medium_position_spike_seed0"},
    {"case_id": "C08_position_spike_medium_seed1", "case_family": "position_spike", "case_spec": "medium_position_spike_seed1"},
    {"case_id": "C09_position_spike_medium_seed2", "case_family": "position_spike", "case_spec": "medium_position_spike_seed2"},
    {"case_id": "C10_std_inflation_strong", "case_family": "std_inflation", "case_spec": "strong_position_and_yaw_std_inflation"},
    {"case_id": "C11_yaw_spike_10_seed0", "case_family": "yaw_spike", "case_spec": "yaw_spike_10deg_seed0"},
    {"case_id": "C12_yaw_spike_10_seed1", "case_family": "yaw_spike", "case_spec": "yaw_spike_10deg_seed1"},
    {"case_id": "C13_yaw_spike_10_seed2", "case_family": "yaw_spike", "case_spec": "yaw_spike_10deg_seed2"},
    {"case_id": "C14_yawstd_inflation_2x", "case_family": "yawstd_inflation", "case_spec": "yaw_std_inflation_2x"},
    {"case_id": "C15_mixed_medium_seed0", "case_family": "mixed", "case_spec": "mixed_medium_seed0"},
    {"case_id": "C16_mixed_medium_seed1", "case_family": "mixed", "case_spec": "mixed_medium_seed1"},
    {"case_id": "C17_mixed_medium_seed2", "case_family": "mixed", "case_spec": "mixed_medium_seed2"},
]


def classic_case_manifest() -> list[dict[str, str]]:
    return [dict(item) for item in CLASSIC_CASES]


def seed_for_case(case_id: str) -> int:
    if "seed0" in case_id:
        return 0
    if "seed1" in case_id:
        return 1
    if "seed2" in case_id:
        return 2
    return 0
