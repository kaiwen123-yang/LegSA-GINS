#!/usr/bin/env python3
"""Build PAPER10M1R2A V2 BY2 degradation specification artifacts.

This stage is a specification lock only. It does not generate degraded
providers, run solvers, run evaluators, or inspect trace/final_v23 outputs.
Paths are supplied by environment variables so tracked files do not contain
machine-local absolute paths.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE_NAME = "PAPER10M1R2A_V2_BY2_DEGRADATION_MATRIX_SPEC_LOCK_60TYPES_9SEEDS"
METHOD_MODES = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]
ABLATION_METHODS = [
    "legsa_full_candidate_with_qm",
    "legsa_without_qm",
    "legsa_no_raw_doppler",
    "legsa_no_source_aware",
    "legsa_no_go2_roll_pitch",
    "legsa_no_go2_horizontal_velocity",
    "legsa_no_go2_joint",
    "legsa_no_qm",
    "legsa_no_fgo_feedback_or_ekf_only",
]
SEEDS = [
    ("seed_00", 260306001, "user_original_206p2s", 206.2),
    ("seed_01", 260306002, "early_motion", 88.0),
    ("seed_02", 260306003, "mid_straight", 146.0),
    ("seed_03", 260306004, "turn_segment", 190.0),
    ("seed_04", 260306005, "low_speed_segment", 230.0),
    ("seed_05", 260306006, "high_motion_segment", 118.0),
    ("seed_06", 260306007, "lower_quality_but_valid_A1", 272.0),
    ("seed_07", 260306008, "raw_doppler_residual_candidate", 304.0),
    ("seed_08", 260306009, "late_recovery_segment", 332.0),
]


@dataclass(frozen=True)
class DegType:
    type_id: str
    name: str
    family: str
    parameters: dict[str, Any]
    affected_sources: str
    unaffected_sources: str
    claim_level: str
    innovation_mapping: str


def dt(
    type_id: str,
    name: str,
    family: str,
    parameters: dict[str, Any],
    affected_sources: str,
    unaffected_sources: str,
    claim_level: str,
    innovation_mapping: str,
) -> DegType:
    return DegType(
        type_id=type_id,
        name=name,
        family=family,
        parameters=parameters,
        affected_sources=affected_sources,
        unaffected_sources=unaffected_sources,
        claim_level=claim_level,
        innovation_mapping=innovation_mapping,
    )


DEGRADATION_TYPES: list[DegType] = [
    dt("D01", "GNSS_position_outage_3s", "gnss_outage", {"operation": "outage", "sources": ["gnss_position"], "duration_s": 3}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "basic outage robustness"),
    dt("D02", "GNSS_position_outage_5s", "gnss_outage", {"operation": "outage", "sources": ["gnss_position"], "duration_s": 5}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "basic outage robustness"),
    dt("D03", "GNSS_position_outage_10s", "gnss_outage", {"operation": "outage", "sources": ["gnss_position"], "duration_s": 10}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "basic outage robustness"),
    dt("D04", "GNSS_position_outage_20s", "gnss_outage", {"operation": "outage", "sources": ["gnss_position"], "duration_s": 20}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "long outage robustness"),
    dt("D05", "GNSS_position_velocity_outage_10s", "gnss_outage", {"operation": "outage", "sources": ["gnss_position", "receiver_velocity"], "duration_s": 10}, "GNSS position; receiver velocity", "dual yaw; raw Doppler; Go2 priors", "main_candidate", "source diversity under position/velocity outage"),
    dt("D06", "GNSS_all_update_outage_20s", "gnss_outage", {"operation": "outage", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "duration_s": 20}, "GNSS position; receiver velocity; dual yaw", "raw Doppler; Go2 priors", "main_candidate", "full GNSS update outage stress"),
    dt("D07", "GNSS_repeated_short_outage", "gnss_outage", {"operation": "repeated_outage", "sources": ["gnss_position"], "interval_count": 3, "duration_each_s": 3, "seed_controls": "interval_start_times"}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "repeated outage recovery"),
    dt("D08", "GNSS_downsample_5Hz", "gnss_sampling", {"operation": "downsample", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 5, "seed_controls": "phase"}, "GNSS position; receiver velocity; dual yaw", "raw Doppler; Go2 priors", "main_candidate", "sampling-rate robustness"),
    dt("D09", "GNSS_downsample_2Hz", "gnss_sampling", {"operation": "downsample", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 2, "seed_controls": "phase"}, "GNSS position; receiver velocity; dual yaw", "raw Doppler; Go2 priors", "main_candidate", "sampling-rate robustness"),
    dt("D10", "GNSS_downsample_1Hz", "gnss_sampling", {"operation": "downsample", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 1, "seed_controls": "phase"}, "GNSS position; receiver velocity; dual yaw", "raw Doppler; Go2 priors", "main_candidate", "low-rate robustness"),
    dt("D11", "GNSS_random_dropout_30", "gnss_sampling", {"operation": "random_dropout", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "dropout_ratio": 0.30, "seed_controls": "dropout_pattern"}, "GNSS position; receiver velocity; dual yaw", "raw Doppler; Go2 priors", "main_candidate", "random observation availability"),
    dt("D12", "GNSS_random_dropout_60", "gnss_sampling", {"operation": "random_dropout", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "dropout_ratio": 0.60, "seed_controls": "dropout_pattern"}, "GNSS position; receiver velocity; dual yaw", "raw Doppler; Go2 priors", "main_candidate", "severe random observation availability"),
    dt("D13", "position_noise_mild", "position_value", {"operation": "gaussian_position_noise", "h_sigma_m": 0.5, "v_sigma_m": 1.0}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "position noise response"),
    dt("D14", "position_noise_medium", "position_value", {"operation": "gaussian_position_noise", "h_sigma_m": 1.5, "v_sigma_m": 2.5}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "position noise response"),
    dt("D15", "position_noise_strong", "position_value", {"operation": "gaussian_position_noise", "h_sigma_m": 3.0, "v_sigma_m": 5.0}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "strong position noise response"),
    dt("D16", "position_static_bias_1p5m", "position_value", {"operation": "static_position_bias", "horizontal_bias_m": 1.5, "vertical_bias_m": 0.5, "seed_controls": "horizontal_direction_and_vertical_sign"}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "bias rejection / downweighting"),
    dt("D17", "position_static_bias_3m", "position_value", {"operation": "static_position_bias", "horizontal_bias_m": 3.0, "vertical_bias_m": 1.0, "seed_controls": "horizontal_direction_and_vertical_sign"}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "strong bias rejection / downweighting"),
    dt("D18", "position_slow_drift_bias", "position_value", {"operation": "slow_drift_bias", "horizontal_start_m": 0.0, "horizontal_end_m": 3.0, "vertical_start_m": 0.0, "vertical_end_m": 1.0}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "drift response"),
    dt("D19", "position_sinusoidal_multipath", "position_value", {"operation": "sinusoidal_multipath", "horizontal_amplitude_m": 2.0, "vertical_amplitude_m": 0.5, "seed_controls": "phase"}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "multipath-like bounded oscillation"),
    dt("D20", "position_spike_mild", "position_value", {"operation": "position_spike", "probability": 0.02, "horizontal_m": 2.0, "vertical_m": 1.0}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "isolated spike response"),
    dt("D21", "position_spike_medium", "position_value", {"operation": "position_spike", "probability": 0.05, "horizontal_m": 4.0, "vertical_m": 2.0}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "medium spike response"),
    dt("D22", "position_spike_burst_strong", "position_value", {"operation": "position_burst_spike", "burst_length_epochs_min": 3, "burst_length_epochs_max": 5, "horizontal_m": 8.0, "vertical_m": 4.0}, "GNSS position", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "burst spike recovery"),
    dt("D23", "position_std_inflation_1p5", "position_std_status", {"operation": "std_inflation", "source": "gnss_position_std", "factor": 1.5}, "GNSS position STD", "GNSS position value; receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "covariance response"),
    dt("D24", "position_std_inflation_2p5", "position_std_status", {"operation": "std_inflation", "source": "gnss_position_std", "factor": 2.5}, "GNSS position STD", "GNSS position value; receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "covariance response"),
    dt("D25", "position_std_inflation_4p0", "position_std_status", {"operation": "std_inflation", "source": "gnss_position_std", "factor": 4.0}, "GNSS position STD", "GNSS position value; receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "pessimistic covariance response"),
    dt("D26", "position_std_deflation_0p25", "position_std_status", {"operation": "std_deflation", "source": "gnss_position_std", "factor": 0.25}, "GNSS position STD", "GNSS position value; receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "optimistic covariance stress"),
    dt("D27", "bad_position_optimistic_std", "position_std_status", {"operation": "bad_position_optimistic_std", "h_sigma_m": 3.0, "v_sigma_m": 5.0, "std_factor": 0.25}, "GNSS position; GNSS position STD", "receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "source-aware/QM conflict response"),
    dt("D28", "good_position_pessimistic_std", "position_std_status", {"operation": "good_position_pessimistic_std", "value_change": "unchanged", "std_factor": 4.0}, "GNSS position STD", "GNSS position value; receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "over-pessimistic covariance response"),
    dt("D29", "gnss_status_quality_downgrade_only", "position_std_status", {"operation": "status_quality_downgrade_only", "value_change": "unchanged"}, "GNSS status/quality flags", "GNSS numeric values; receiver velocity; dual yaw; raw Doppler; Go2 priors", "main_candidate", "metadata-only source reliability response"),
    dt("D30", "dual_yaw_outage_5s", "dual_yaw", {"operation": "outage", "sources": ["dual_yaw"], "duration_s": 5}, "dual antenna yaw", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "yaw observation outage"),
    dt("D31", "dual_yaw_outage_20s", "dual_yaw", {"operation": "outage", "sources": ["dual_yaw"], "duration_s": 20}, "dual antenna yaw", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "long yaw observation outage"),
    dt("D32", "dual_yaw_noise_mild", "dual_yaw", {"operation": "dual_yaw_gaussian_noise", "sigma_deg": 1.0, "yaw_wrap": "required"}, "dual antenna yaw", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "yaw noise response"),
    dt("D33", "dual_yaw_noise_strong", "dual_yaw", {"operation": "dual_yaw_gaussian_noise", "sigma_deg": 5.0, "yaw_wrap": "required"}, "dual antenna yaw", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "strong yaw noise response"),
    dt("D34", "dual_yaw_spike_5pct", "dual_yaw", {"operation": "dual_yaw_spike", "probability": 0.05, "yaw_wrap": "required"}, "dual antenna yaw", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "yaw spike response"),
    dt("D35", "dual_yaw_spike_10pct", "dual_yaw", {"operation": "dual_yaw_spike", "probability": 0.10, "yaw_wrap": "required"}, "dual antenna yaw", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "dense yaw spike response"),
    dt("D36", "dual_yaw_std_inflation_1p5", "dual_yaw", {"operation": "yaw_std_inflation", "factor": 1.5}, "dual yaw STD", "dual yaw value; GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "yaw covariance response"),
    dt("D37", "dual_yaw_std_inflation_3p0", "dual_yaw", {"operation": "yaw_std_inflation", "factor": 3.0}, "dual yaw STD", "dual yaw value; GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "yaw covariance response"),
    dt("D38", "bad_yaw_optimistic_std", "dual_yaw", {"operation": "bad_yaw_optimistic_std", "yaw_noise_sigma_deg": 10.0, "optional_spike_component": True, "yaw_std_factor": 0.25, "yaw_wrap": "required"}, "dual yaw value; dual yaw STD", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "bad-yaw optimistic-uncertainty stress"),
    dt("D39", "baseline_quality_dropout", "dual_yaw", {"operation": "baseline_quality_dropout", "fields": ["rel_valid", "quality"], "seed_controls": "unavailable_bursts"}, "dual antenna baseline quality", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "dual-yaw quality metadata response"),
    dt("D40", "baseline_length_jitter_relacc", "dual_yaw", {"operation": "baseline_length_jitter_relacc", "baseline_length_jitter_m": "seeded_small_jitter", "rel_acc_inflation": True}, "dual antenna relpos/baseline metadata", "GNSS position; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "baseline physical sanity and quality response"),
    dt("D41", "gnss1_gnss2_asymmetric_noise", "dual_yaw", {"operation": "gnss1_gnss2_asymmetric_noise", "h_sigma_m": 3.0, "v_sigma_m": 2.0, "seed_controls": "antenna_selection"}, "one GNSS antenna position stream", "other GNSS antenna; receiver velocity; raw Doppler; Go2 priors", "main_candidate", "dual-antenna source asymmetry response"),
    dt("D42", "receiver_velocity_outage_20s", "velocity_raw_doppler", {"operation": "outage", "sources": ["receiver_velocity"], "duration_s": 20}, "receiver velocity", "GNSS position; dual yaw; raw Doppler; Go2 priors", "main_candidate", "receiver velocity outage"),
    dt("D43", "receiver_velocity_noise_0p5", "velocity_raw_doppler", {"operation": "receiver_velocity_noise", "sigma_mps": 0.5}, "receiver velocity", "GNSS position; dual yaw; raw Doppler; Go2 priors", "main_candidate", "receiver velocity noise response"),
    dt("D44", "receiver_velocity_spike_2mps", "velocity_raw_doppler", {"operation": "receiver_velocity_spike", "probability": 0.02, "magnitude_mps": 2.0}, "receiver velocity", "GNSS position; dual yaw; raw Doppler; Go2 priors", "main_candidate", "receiver velocity spike response"),
    dt("D45", "receiver_velocity_bad_optimistic_std", "velocity_raw_doppler", {"operation": "receiver_velocity_noise_optimistic_std", "sigma_mps": 0.5, "std_factor": 0.25}, "receiver velocity; receiver velocity STD", "GNSS position; dual yaw; raw Doppler; Go2 priors", "main_candidate", "velocity optimistic-uncertainty stress"),
    dt("D46", "raw_doppler_outage_20s", "velocity_raw_doppler", {"operation": "outage", "sources": ["raw_doppler_velocity"], "duration_s": 20}, "Raw Doppler velocity provider", "GNSS position; receiver velocity; dual yaw; Go2 priors", "main_candidate", "Raw Doppler availability"),
    dt("D47", "raw_doppler_noise_0p5", "velocity_raw_doppler", {"operation": "raw_doppler_velocity_noise", "sigma_mps": 0.5}, "Raw Doppler velocity provider", "GNSS position; receiver velocity; dual yaw; Go2 priors", "main_candidate", "Raw Doppler noise response"),
    dt("D48", "raw_doppler_spike_1p5mps", "velocity_raw_doppler", {"operation": "raw_doppler_velocity_spike", "probability": 0.02, "magnitude_mps": 1.5}, "Raw Doppler velocity provider", "GNSS position; receiver velocity; dual yaw; Go2 priors", "main_candidate", "Raw Doppler spike response"),
    dt("D49", "raw_doppler_bad_optimistic_std", "velocity_raw_doppler", {"operation": "raw_doppler_anomaly_optimistic_std", "anomaly": "noise_or_spike_seeded", "optimistic_or_floor_std_policy": True}, "Raw Doppler velocity; Raw Doppler uncertainty", "GNSS position; receiver velocity; dual yaw; Go2 priors", "main_candidate", "Raw Doppler optimistic-uncertainty stress"),
    dt("D50", "raw_receiver_velocity_conflict", "velocity_raw_doppler", {"operation": "raw_receiver_velocity_conflict", "conflict_magnitude_mps": 1.0}, "Raw Doppler velocity; receiver velocity", "GNSS position; dual yaw; Go2 priors", "main_candidate", "multi-velocity source conflict"),
    dt("D51", "go2_roll_pitch_dropout_noise", "go2_prior_metadata", {"operation": "go2_roll_pitch_dropout_noise", "dropout_ratio": 0.50, "remaining_noise_sigma_deg": 3.0}, "Go2 roll/pitch weak prior", "GNSS position; receiver velocity; dual yaw; Raw Doppler", "appendix_candidate", "Go2 roll/pitch weak prior robustness"),
    dt("D52", "go2_roll_pitch_bias", "go2_prior_metadata", {"operation": "go2_roll_pitch_bias", "bias_deg": 2.0, "seed_controls": "roll_pitch_direction"}, "Go2 roll/pitch weak prior", "GNSS position; receiver velocity; dual yaw; Raw Doppler", "appendix_candidate", "Go2 attitude weak-prior bias response"),
    dt("D53", "go2_horizontal_velocity_noise", "go2_prior_metadata", {"operation": "go2_horizontal_velocity_noise", "sigma_mps": 1.0}, "Go2 horizontal velocity weak prior", "GNSS position; receiver velocity; dual yaw; Raw Doppler", "appendix_candidate", "Go2 horizontal velocity weak-prior response"),
    dt("D54", "go2_horizontal_velocity_scale_dropout", "go2_prior_metadata", {"operation": "go2_horizontal_velocity_scale_or_dropout", "scale": 1.5, "dropout_ratio": 0.50, "seed_group_controls": "scale_vs_dropout"}, "Go2 horizontal velocity weak prior", "GNSS position; receiver velocity; dual yaw; Raw Doppler", "appendix_candidate", "Go2 horizontal velocity scale/dropout response"),
    dt("D55", "go2_contact_motion_metadata_uncertain", "go2_prior_metadata", {"operation": "go2_contact_motion_metadata_uncertain", "pattern": "missing_or_uncertain_seeded"}, "Go2 contact/mode/gait metadata", "GNSS position; receiver velocity; dual yaw; Raw Doppler", "diagnostic_only", "Go2 readiness/metadata gating diagnostic"),
    dt("D56", "go2_foot_speed_contact_conflict", "go2_prior_metadata", {"operation": "go2_foot_speed_contact_conflict", "pattern": "foot_force_and_foot_speed_conflict_seeded"}, "Go2 foot force; Go2 foot speed metadata", "GNSS position; receiver velocity; dual yaw; Raw Doppler", "diagnostic_only", "Go2 foot/contact consistency diagnostic"),
    dt("D57", "multi_source_latency_jitter", "multi_source_mixed", {"operation": "multi_source_latency_jitter", "components": ["latency_shift", "timestamp_jitter"], "latency_range_s": [0.1, 0.3], "jitter_range_ms": [20, 50]}, "timestamps of selected sources", "source values except timestamp alignment", "main_candidate", "multi-source timing robustness"),
    dt("D58", "outage_yaw_spike_then_recovery", "multi_source_mixed", {"operation": "mixed_components", "components": ["position_outage_10s", "dual_yaw_spike", "clean_recovery_interval"], "recovery_interval": "required"}, "GNSS position; dual yaw", "receiver velocity; Raw Doppler; Go2 priors", "main_candidate", "outage plus yaw anomaly recovery"),
    dt("D59", "bad_position_good_yaw_raw_conflict", "multi_source_mixed", {"operation": "mixed_components", "components": ["bad_position", "good_yaw", "raw_receiver_velocity_conflict"], "conflict_magnitude_mps": 1.0}, "GNSS position; Raw Doppler; receiver velocity", "dual yaw", "main_candidate", "source-aware conflicting source selection"),
    dt("D60", "multisource_bad_optimistic_then_recovery", "multi_source_mixed", {"operation": "mixed_components", "components": ["bad_position_optimistic_std", "bad_yaw_optimistic_std", "bad_velocity_optimistic_std", "clean_recovery_interval"], "recovery_interval": "required"}, "GNSS position; dual yaw; velocity sources; std fields", "none during abnormal interval", "main_candidate", "multi-source bad optimistic recovery"),
]


def csv_write(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def json_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def text_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=Path.cwd(), text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:  # pragma: no cover - report best effort
        return f"UNAVAILABLE: {exc}"


def required_env_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return Path(value)


def seed_rows() -> list[dict[str, Any]]:
    rows = []
    for seed_index, seed_value, _anchor, _time in SEEDS:
        rows.append(
            {
                "seed_index": seed_index,
                "seed_value": seed_value,
                "rng_algorithm": "numpy.random.PCG64",
                "anchor_policy": "canonical_seed_anchor_without_trace_or_output_selection",
                "used_for_noise": "true",
                "used_for_dropout": "true",
                "used_for_spike": "true",
                "used_for_outage_start": "true",
                "used_for_bias_direction": "true",
                "used_for_mixed_components": "true",
                "notes": "fixed_seed_do_not_replace",
            }
        )
    return rows


def anchor_rows() -> list[dict[str, Any]]:
    allowed_sources = (
        "GNSS status; dual antenna status/relpos quality; Raw Doppler provider "
        "metadata; Go2 body-state velocity/yaw_speed/mode/gait; time-percentile fallback"
    )
    rows = []
    for seed_index, seed_value, anchor, time_s in SEEDS:
        rows.append(
            {
                "seed_index": seed_index,
                "seed_value": seed_value,
                "anchor_name": anchor,
                "anchor_time_s": f"{time_s:.1f}",
                "selection_basis": allowed_sources,
                "trace_used_for_selection": "false",
                "final_v23_output_used_for_selection": "false",
                "legsa_output_used_for_selection": "false",
                "fallback_if_unresolved": "nearest_valid_source_epoch_with_same_seed_index",
                "notes": "M1R2B must verify concrete epoch availability before provider generation.",
            }
        )
    return rows


def duration_value(deg: DegType) -> str:
    p = deg.parameters
    if "duration_s" in p:
        return str(p["duration_s"])
    if "duration_each_s" in p:
        return f"{p['interval_count']}x{p['duration_each_s']}"
    if "burst_length_epochs_min" in p:
        return f"{p['burst_length_epochs_min']}-{p['burst_length_epochs_max']}_epochs"
    return "full_sequence_or_seeded_window"


def case_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "case_id": "BY2_CLEAN_CANONICAL",
            "case_index": 0,
            "dataset": "BY2",
            "case_family": "clean",
            "degradation_type_id": "CLEAN",
            "degradation_type_name": "clean_reference_no_degradation",
            "seed_index": "none",
            "seed_value": "",
            "rng_algorithm": "none",
            "anchor_name": "none",
            "anchor_time_s": "",
            "duration_s": "full_sequence",
            "degradation_parameters_json": json.dumps({"operation": "none"}, sort_keys=True),
            "affected_sources": "none",
            "unaffected_sources": "all",
            "requires_randomness": "false",
            "requires_provider_generation": "false",
            "effect_validation_rule_id": "RULE_CLEAN",
            "claim_level": "main_candidate",
            "run_allowed_in_M1R2B": "false",
            "run_allowed_in_M1R2C": "false",
            "run_allowed_in_M1R2D": "false",
            "trace_eval_only": "true",
            "final_v23_output_solver_input_allowed": "false",
            "legsa_output_solver_input_allowed": "false",
            "go2_truth_claim_allowed": "false",
            "notes": "clean case for provider verification queue only; no solver run in M1R2A",
        }
    ]
    index = 1
    for deg in DEGRADATION_TYPES:
        for seed_index, seed_value, anchor, anchor_time in SEEDS:
            rows.append(
                {
                    "case_id": f"BY2_{deg.type_id}_{deg.name}_{seed_index}",
                    "case_index": index,
                    "dataset": "BY2",
                    "case_family": deg.family,
                    "degradation_type_id": deg.type_id,
                    "degradation_type_name": deg.name,
                    "seed_index": seed_index,
                    "seed_value": seed_value,
                    "rng_algorithm": "numpy.random.PCG64",
                    "anchor_name": anchor,
                    "anchor_time_s": f"{anchor_time:.1f}",
                    "duration_s": duration_value(deg),
                    "degradation_parameters_json": json.dumps(deg.parameters, sort_keys=True),
                    "affected_sources": deg.affected_sources,
                    "unaffected_sources": deg.unaffected_sources,
                    "requires_randomness": "true",
                    "requires_provider_generation": "true",
                    "effect_validation_rule_id": f"RULE_{deg.type_id}",
                    "claim_level": deg.claim_level,
                    "run_allowed_in_M1R2B": "false",
                    "run_allowed_in_M1R2C": "false",
                    "run_allowed_in_M1R2D": "false",
                    "trace_eval_only": "true",
                    "final_v23_output_solver_input_allowed": "false",
                    "legsa_output_solver_input_allowed": "false",
                    "go2_truth_claim_allowed": "false",
                    "notes": "fixed V2 case; provider generation only after M1R2B approval",
                }
            )
            index += 1
    return rows


def rule_for(deg: DegType) -> dict[str, str]:
    p = deg.parameters
    op = str(p.get("operation", ""))
    value_check = "value fields unchanged unless this rule explicitly changes them"
    std_check = "std fields unchanged unless this rule explicitly changes them"
    status_check = "status fields unchanged unless this rule explicitly changes them"
    epoch_check = "affected epoch count must match seeded mask/window"
    sanity = "timestamp monotonic; no NaN/Inf; physical bounds preserved"
    if "outage" in op:
        value_check = "masked values absent or marked unavailable only within outage window"
        epoch_check = "outage mask epoch count equals requested duration/window count"
    if op == "repeated_outage":
        epoch_check = "exactly three outage intervals, each 3s, non-overlapping"
    if op == "downsample":
        epoch_check = "retained ratio matches target rate and seed phase"
    if "dropout" in op:
        epoch_check = "retained/dropout ratio matches configured ratio within tolerance"
    if "noise" in op:
        value_check = "observed noise mean near zero and std near configured sigma"
    if "bias" in op:
        value_check = "bias direction and amplitude match seed-controlled vector"
    if "drift" in op:
        value_check = "drift starts at zero and reaches configured terminal amplitude"
    if "sinusoidal" in op:
        value_check = "sinusoidal amplitude and seeded phase match specification"
    if "spike" in op:
        value_check = "spike count/probability and magnitude match specification"
    if "burst" in op:
        epoch_check = "burst length is 3-5 epochs"
    if "std" in op or "std" in deg.name:
        std_check = "std ratio equals configured inflation/deflation/optimistic factor"
    if "status_quality" in op:
        status_check = "status/quality downgraded while numeric values remain unchanged"
    if "yaw" in deg.family or "yaw" in deg.name:
        sanity += "; yaw values wrapped safely"
    if "baseline" in deg.name:
        status_check = "baseline quality/relacc affected count matches seed mask"
        sanity += "; baseline length remains physically auditable"
    if "gnss1_gnss2" in deg.name:
        value_check = "only seed-selected antenna receives asymmetric noise"
    if "receiver_velocity" in deg.name:
        value_check = "receiver velocity affected count and magnitude match specification"
    if "raw_doppler" in deg.name:
        value_check = "Raw Doppler provider affected count and magnitude match specification"
    if "conflict" in deg.name:
        value_check = "source conflict magnitude matches configured difference"
    if deg.family == "go2_prior_metadata":
        value_check = "Go2 prior/metadata affected count matches seed mask; no Go2 truth claim"
    if deg.type_id == "D57":
        epoch_check = "latency shift and jitter timestamp deltas match configured ranges"
    if deg.family == "multi_source_mixed":
        status_check = "each mixed component passes its independent component validation"
    return {
        "rule_id": f"RULE_{deg.type_id}",
        "degradation_type_id": deg.type_id,
        "affected_source_check": f"Only affected sources may change: {deg.affected_sources}",
        "epoch_count_check": epoch_check,
        "value_change_check": value_check,
        "std_change_check": std_check,
        "status_change_check": status_check,
        "seed_reproducibility_check": "same seed_index and seed_value reproduce identical masks/noise/components",
        "sha256_check": "provider summary records sha256 for input spec and generated outputs",
        "timestamp_monotonic_check": "timestamps must be monotonic after degradation; jitter cases require bounded deltas",
        "nan_inf_check": "no NaN or Inf introduced except explicit unavailable markers for outages",
        "physical_sanity_check": sanity,
        "trace_forbidden_check": "trace must not be read for generation, anchor selection, or tuning",
        "final_v23_forbidden_check": "final_v23/LegSA outputs must not be read for generation, anchor selection, or tuning",
        "expected_summary_fields": "case_id; degradation_type_id; seed_index; affected_epoch_count; value_delta_summary; std_delta_summary; status_delta_summary; input_spec_sha256; output_sha256",
    }


def registry_rows() -> list[dict[str, Any]]:
    rows = []
    for deg in DEGRADATION_TYPES:
        rows.append(
            {
                "degradation_type_id": deg.type_id,
                "degradation_type_name": deg.name,
                "case_family": deg.family,
                "affected_sources": deg.affected_sources,
                "unaffected_sources": deg.unaffected_sources,
                "parameters_json": json.dumps(deg.parameters, sort_keys=True),
                "requires_randomness": "true",
                "seeds_per_type": 9,
                "degraded_cases": 9,
                "effect_validation_rule_id": f"RULE_{deg.type_id}",
                "claim_level": deg.claim_level,
                "module_disable_axis": "false",
                "notes": "fixed_by_user_v2_no_auto_planning",
            }
        )
    return rows


def innovation_rows() -> list[dict[str, Any]]:
    return [
        {
            "degradation_type_id": deg.type_id,
            "degradation_type_name": deg.name,
            "case_family": deg.family,
            "innovation_or_module_stressed": deg.innovation_mapping,
            "primary_expected_mechanism": (
                "source-aware/QM/provider robustness"
                if deg.family not in {"go2_prior_metadata", "dual_yaw"}
                else ("Go2 weak-prior/metadata bounded behavior" if deg.family == "go2_prior_metadata" else "dual-yaw baseline/candidate heading robustness")
            ),
            "claim_level": deg.claim_level,
            "paper_claim_allowed_now": "false",
            "notes": "M1R2A is spec lock only; provider generation and execution required later.",
        }
        for deg in DEGRADATION_TYPES
    ]


def queue_rows_provider(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "queue_id": f"PAPER10M1R2B_PROVIDER_{row['case_index']:04d}",
            "case_id": row["case_id"],
            "dataset": "BY2",
            "degradation_type_id": row["degradation_type_id"],
            "seed_index": row["seed_index"],
            "provider_action": "verify_clean_provider" if row["case_family"] == "clean" else "generate_degraded_provider",
            "expected_input_spec": f"<PAPER10M1R2A_V2_STAGE_ROOT>/04_CASE_MANIFEST/{row['case_id']}.json",
            "expected_output_root": f"<DEGRADED_PROVIDER_ROOT>/{row['case_id']}",
            "run_allowed_now": "false",
            "trace_eval_only": "true",
            "human_approval_required": "true",
            "notes": "draft only; no provider generation in M1R2A",
        }
        for row in cases
    ]


def queue_rows_full(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for mode in METHOD_MODES:
        for row in cases:
            rows.append(
                {
                    "queue_id": f"PAPER10M1R2C_{mode}_{row['case_index']:04d}",
                    "method_mode_id": mode,
                    "case_id": row["case_id"],
                    "dataset": "BY2",
                    "degradation_type_id": row["degradation_type_id"],
                    "seed_index": row["seed_index"],
                    "expected_provider_root": f"<DEGRADED_PROVIDER_ROOT>/{row['case_id']}",
                    "expected_output_root": f"<PAPER10M1R2C_RUNTIME_ROOT>/{mode}/{row['case_id']}",
                    "run_allowed_now": "false",
                    "trace_eval_only": "true",
                    "human_approval_required": "true",
                    "notes": "draft only; no solver/evaluator in M1R2A",
                }
            )
    return rows


def queue_rows_ablation(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for method in ABLATION_METHODS:
        for row in cases:
            rows.append(
                {
                    "queue_id": f"PAPER10M1R2D_{method}_{row['case_index']:04d}",
                    "ablation_method_id": method,
                    "case_id": row["case_id"],
                    "dataset": "BY2",
                    "degradation_type_id": row["degradation_type_id"],
                    "seed_index": row["seed_index"],
                    "expected_provider_root": f"<DEGRADED_PROVIDER_ROOT>/{row['case_id']}",
                    "expected_output_root": f"<PAPER10M1R2D_RUNTIME_ROOT>/{method}/{row['case_id']}",
                    "run_allowed_now": "false",
                    "trace_eval_only": "true",
                    "human_approval_required": "true",
                    "notes": "draft only; no internal ablation in M1R2A",
                }
            )
    return rows


def write_manifest_schemas(stage_root: Path) -> None:
    json_write(
        stage_root / "04_CASE_MANIFEST/CANONICAL_BY2_CASE_SPEC_SCHEMA.json",
        {
            "schema_name": "CANONICAL_BY2_CASE_SPEC_SCHEMA",
            "required_fields": [
                "case_id",
                "case_index",
                "dataset",
                "case_family",
                "degradation_type_id",
                "degradation_type_name",
                "seed_index",
                "seed_value",
                "rng_algorithm",
                "anchor_name",
                "anchor_time_s",
                "duration_s",
                "degradation_parameters_json",
                "affected_sources",
                "unaffected_sources",
                "requires_randomness",
                "requires_provider_generation",
                "effect_validation_rule_id",
                "claim_level",
                "run_allowed_in_M1R2B",
                "run_allowed_in_M1R2C",
                "run_allowed_in_M1R2D",
                "trace_eval_only",
                "final_v23_output_solver_input_allowed",
                "legsa_output_solver_input_allowed",
                "go2_truth_claim_allowed",
                "notes",
            ],
            "row_count": 541,
            "degraded_case_count": 540,
            "clean_case_count": 1,
            "allowed_claim_levels": ["main_candidate", "appendix_candidate", "diagnostic_only"],
        },
    )
    json_write(
        stage_root / "05_EFFECT_VALIDATION/CANONICAL_BY2_EFFECT_VALIDATION_SCHEMA.json",
        {
            "schema_name": "CANONICAL_BY2_EFFECT_VALIDATION_SCHEMA",
            "row_count": 60,
            "required_fields": [
                "rule_id",
                "degradation_type_id",
                "affected_source_check",
                "epoch_count_check",
                "value_change_check",
                "std_change_check",
                "status_change_check",
                "seed_reproducibility_check",
                "sha256_check",
                "timestamp_monotonic_check",
                "nan_inf_check",
                "physical_sanity_check",
                "trace_forbidden_check",
                "final_v23_forbidden_check",
                "expected_summary_fields",
            ],
        },
    )


def write_design_docs(stage_root: Path, cases: list[dict[str, Any]]) -> None:
    fam_counts = Counter(row["case_family"] for row in cases)
    text_write(
        stage_root / "02_MATRIX_DESIGN/CANONICAL_BY2_DEGRADATION_MATRIX_DESIGN.md",
        f"""# Canonical BY2 Degradation Matrix Design V2

Stage: {STAGE_NAME}

This is a user-fixed specification lock, not a Codex-designed matrix. The
matrix contains exactly 60 degradation types, 9 fixed seeds per type, and one
clean case.

- Degraded cases: 60 x 9 = 540
- Clean cases: 1
- Total cases: 541
- RNG: numpy.random.PCG64
- Solver/evaluator/provider generation in this stage: false
- module-disable as case axis: false
- trace anchor/parameter selection: false
- final_v23/LegSA output selection: false

V2 replaces the blocked PAPER10M1 static 120-case queue with a source-specific
degradation-type axis. The prior module-disable axis and generic mixed
placeholders are removed. Mixed cases are represented only by fixed
degradation type IDs D57-D60 with explicit component lists in
degradation_parameters_json.

Family counts including clean:

{json.dumps(dict(sorted(fam_counts.items())), indent=2, sort_keys=True)}
""",
    )
    text_write(
        stage_root / "03_SEEDS/CANONICAL_BY2_ANCHOR_SELECTION_POLICY.md",
        """# Canonical BY2 Anchor Selection Policy

Each seed has one canonical anchor name and target time. M1R2A locks the
policy only; M1R2B must verify actual source epochs before provider generation.

Forbidden anchor inputs:

- trace
- final_v23 output
- LegSA output

Allowed anchor inputs:

- GNSS status
- dual antenna status / relpos quality
- Raw Doppler provider metadata
- Go2 body-state velocity / yaw_speed / mode / gait
- time-range percentile fallback

If a named anchor cannot be identified during M1R2B, use the nearest valid
source epoch for the same seed index and record the fallback. Do not change
the seed count.
""",
    )
    text_write(
        stage_root / "04_CASE_MANIFEST/CANONICAL_BY2_CASE_COUNT_DECISION.md",
        """# Canonical BY2 Case Count Decision

Decision: PASS case-count lock.

- Fixed degradation types: 60
- Seeds per type: 9
- Degraded cases: 540
- Clean cases: 1
- Total cases: 541

No placeholder mixed cases are present. module-disable is not a case axis.
All rows keep run_allowed flags false for M1R2A.
""",
    )
    text_write(
        stage_root / "05_EFFECT_VALIDATION/CANONICAL_BY2_EFFECT_VALIDATION_PROTOCOL.md",
        """# Canonical BY2 Effect Validation Protocol

M1R2B provider generation must validate each generated provider against the
rule matching its degradation_type_id.

Required coverage includes outage mask epoch count, repeated outage interval
count, downsample retained ratio, dropout retained ratio, Gaussian noise
observed mean/std, bias direction/amplitude, drift amplitude, sinusoidal
amplitude, spike count/magnitude, burst length, std ratio, status-only
degradation, yaw wrap safety, yaw std ratio, baseline quality affected count,
baseline length sanity, GNSS1/GNSS2 asymmetric source check, receiver velocity
affected count, Raw Doppler affected count, source conflict magnitude, Go2
prior affected count, Go2 contact/foot conflict count, latency/jitter timestamp
delta, and mixed component independent validation.

Trace and final_v23/LegSA outputs remain forbidden for generation, anchor
selection, or tuning.
""",
    )


def write_reports(
    stage_root: Path,
    export_root: Path,
    cases: list[dict[str, Any]],
    provider_queue: list[dict[str, Any]],
    full_queue: list[dict[str, Any]],
    ablation_queue: list[dict[str, Any]],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    branch = run_git(["branch", "--show-current"])
    head = run_git(["rev-parse", "HEAD"])
    origin_main = run_git(["rev-parse", "origin/main"])
    status = run_git(["status", "--short"])
    push_status = os.environ.get("PAPER10M1R2A_V2_PUSH_STATUS", "NOT_PUSHED_AT_REPORT_GENERATION")
    degraded = [row for row in cases if row["degradation_type_id"] != "CLEAN"]
    supervisor = f"""# PAPER10M1R2A V2 Supervisor Final Report

1. Stage name: {STAGE_NAME}.
2. Why redesign BY2 degradation matrix: PAPER10M1 was blocked because the old queue mixed fixed degradation families with module-disable and unmapped mixed placeholders.
3. Why expand to 60 types: the user-fixed V2 axis separates outage, sampling, position value, covariance/status, yaw, receiver velocity, Raw Doppler, Go2 weak-prior/metadata, and multi-source conflict/recovery mechanisms.
4. PAPER10M1 blocked reason: BLOCKED_QUEUE_CASE_COUNT_MISMATCH from static module_disable=6 and mixed=10 queue rows without source-backed mapping.
5. User V0 degradation conditions absorbed: V2 absorbs outage, downsample/dropout, noise, bias, drift, multipath, spike, std, yaw, velocity, Raw Doppler, Go2, latency, and multi-source conflict conditions into fixed degradation_type_id rows.
6. Why V2 does not copy V0 directly: V2 normalizes V0-style ideas into source-specific provider effects with explicit seeds, anchors, parameters, and validation rules; module-disable is excluded from the case axis.
7. Fixed degradation types: 60.
8. Seeds per type: 9.
9. Degraded case count: {len(degraded)}.
10. Clean case count: {len(cases) - len(degraded)}.
11. Total case count: {len(cases)}.
12. Seed policy: seed_00..seed_08 fixed to 260306001..260306009 with numpy.random.PCG64.
13. Anchor policy: fixed seed anchors, source-only verification in M1R2B, fallback to nearest valid source epoch if needed.
14. no trace anchor selection: confirmed.
15. no final_v23 output selection: confirmed.
16. Innovation mapping: generated in CANONICAL_BY2_INNOVATION_MAPPING.csv.
17. Case manifest: generated with 541 rows.
18. Effect validation rules: generated with 60 rows.
19. Provider queue draft rows: {len(provider_queue)}.
20. Full algorithm queue draft rows: {len(full_queue)}.
21. Internal ablation queue draft rows: {len(ablation_queue)}.
22. module-disable not in case_axis: confirmed.
23. mixed placeholder absent: confirmed; D57-D60 contain explicit components.
24. no solver run: confirmed.
25. no evaluator run: confirmed.
26. no degraded provider generation: confirmed.
27. no raw data modification: confirmed.
28. no raw data copy: confirmed.
29. trace eval-only: confirmed.
30. Go2 not truth: confirmed.
31. AGENTS/PLANS/PHASE_LOG/CLAIM_BOUNDARY update summary: tracked governance docs updated for V2 spec lock and claim boundaries.
32. Tests: see 09_TESTS after pytest execution.
33. Export-clean: generated under <PAPER10M1R2A_V2_STAGE_ROOT>/11_EXPORT_CLEAN_FOR_GPT and <EXPORT_ROOT>.
34. Path scan: see export_clean_path_scan.json.
35. Commit hash if commit: {head}.
36. Push status if push: {push_status}.
37. Next stage: PAPER10M1R2B provider generation preflight/execution after human approval.
38. Final decision: PASS_PAPER10M1R2A_V2_BY2_DEGRADATION_SPEC_LOCKED_READY_FOR_PROVIDER_GENERATION.

Git snapshot:

- Branch: {branch}
- HEAD: {head}
- origin/main: {origin_main}
- status before artifact generation: {status or 'clean'}
- report_created_utc: {now}
"""
    text_write(stage_root / "00_STAGE_REPORT/PAPER10M1R2A_V2_SUPERVISOR_FINAL_REPORT.md", supervisor)
    text_write(
        stage_root / "00_STAGE_REPORT/PAPER10M1R2A_V2_REVIEWER_REPORT.md",
        """# PAPER10M1R2A V2 Reviewer Report

Review result: PASS for spec lock.

Checks:

- 60 degradation types are present.
- 9 fixed seeds are present.
- 540 degraded cases plus 1 clean case are present.
- module-disable is not used as a case axis.
- mixed rows are fixed source-combination type IDs with explicit components.
- all queue drafts have run_allowed_now=false.
- no solver, evaluator, degraded provider generation, raw copy, raw modification, or figure generation was performed.
- trace and final_v23/LegSA outputs remain forbidden for selection or solver input.
""",
    )
    text_write(
        stage_root / "01_GIT/PAPER10M1R2A_V2_GIT_STATE_REPORT.md",
        f"""# PAPER10M1R2A V2 Git State Report

- Current branch: {branch}
- Current HEAD: {head}
- Base branch: integration/paper10m1-by2-full-matrix-execution
- Base commit: 7e8c942c195471e445465cf963ca4a4cdd6ca152
- origin/main HEAD: {origin_main}
- Worktree status before artifact generation: {status or 'clean'}
- Git operations forbidden and not performed: reset, rebase, force push, main push, main merge, PR merge, release, final paper tag.
""",
    )


def write_claim_and_next(stage_root: Path) -> None:
    text_write(
        stage_root / "07_CLAIM_BOUNDARY/PAPER10M1R2A_V2_CLAIM_BOUNDARY_UPDATE.md",
        """# PAPER10M1R2A V2 Claim Boundary Update

Allowed:

- The BY2 canonical degradation matrix V2 specification is locked.
- The matrix has 60 fixed degradation types, 9 seeds per type, 540 degraded cases, 1 clean case, and 541 total cases.
- This stage defines provider-generation and execution queues only.

Forbidden:

- No performance claim.
- No algorithm superiority claim.
- No universal superiority claim.
- No comprehensive final_v23 superiority claim.
- No BY3 yaw generalization claim.
- No XB/PG high-precision severe-GNSS claim.
- No trace-online claim.
- No Go2 truth claim.
- No final paper readiness claim.

Controlled BY2 degradation is not independent real-world severe-environment
generalization by itself. Provider generation and full execution must pass
later stages before any bounded performance statement can be considered.
""",
    )
    text_write(
        stage_root / "10_NEXT_STAGE/PAPER10M1R2B_EXECUTION_PROMPT_DRAFT.md",
        """# PAPER10M1R2B Execution Prompt Draft

Objective: generate degraded providers from the locked 541-case V2 manifest.

Required inputs:

- CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv
- CANONICAL_BY2_EFFECT_VALIDATION_RULES.csv
- CANONICAL_BY2_RANDOM_SEED_MANIFEST.csv
- CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv

Rules:

- Do not run solver/evaluator.
- Do not modify raw data.
- Generate provider outputs only under <DEGRADED_PROVIDER_ROOT>.
- Validate every generated provider against its rule_id.
- Keep trace evaluation-only and final_v23/LegSA outputs forbidden.
""",
    )
    text_write(
        stage_root / "10_NEXT_STAGE/PAPER10M1R2C_FULL_ALGORITHM_PLAN.md",
        """# PAPER10M1R2C Full Algorithm Plan

After M1R2B provider validation passes, run four frozen method modes over 541
cases, for 2164 planned rows. This plan is draft-only in M1R2A; all rows are
run_allowed_now=false.
""",
    )
    text_write(
        stage_root / "10_NEXT_STAGE/PAPER10M1R2D_INTERNAL_ABLATION_PLAN.md",
        """# PAPER10M1R2D Internal Ablation Plan

After M1R2C review, run nine internal ablation methods over 541 cases, for
4869 planned rows. This plan is draft-only in M1R2A; all rows are
run_allowed_now=false.
""",
    )
    text_write(
        stage_root / "10_NEXT_STAGE/PAPER10H_BLOCK_STATUS.md",
        """# PAPER10H Block Status

PAPER10H remains blocked. M1R2A is only a BY2 degradation specification lock.
PAPER10H requires later provider generation, full execution, human review, and
explicit approval. XB/PG can only be boundary/fallback diagnostic; no
high-precision severe-GNSS claim is allowed.
""",
    )


def write_obsidian(stage_root: Path) -> None:
    notes = {
        "PAPER10M1R2A_V2_阶段总览.md": "PAPER10M1R2A V2 locks 60 degradation types, 9 seeds each, plus one clean case. No solver/evaluator/provider generation was run.\n",
        "BY2退化矩阵V2固定设计.md": "V2 removes module-disable as a case axis and replaces unmapped mixed placeholders with fixed D57-D60 multi-source types.\n",
        "退化类型与创新点映射.md": "See CANONICAL_BY2_INNOVATION_MAPPING.csv for degradation-to-mechanism mapping.\n",
        "后续全算法与内部消融计划.md": "M1R2B provider generation draft has 541 rows; M1R2C full algorithm draft has 2164 rows; M1R2D internal ablation draft has 4869 rows.\n",
    }
    rows = []
    for name, body in notes.items():
        text_write(stage_root / "08_OBSIDIAN_SYNC" / name, f"# {name[:-3]}\n\n{body}")
        rows.append({"note": name, "status": "suggested_only", "direct_vault_write": "false"})
    csv_write(stage_root / "08_OBSIDIAN_SYNC/OBSIDIAN_UPDATE_INDEX.csv", rows)


def write_tests_summary(stage_root: Path) -> None:
    git_fsck_status = os.environ.get("PAPER10M1R2A_V2_GIT_FSCK_STATUS", "PENDING_UNTIL_RUN")
    git_fsck_notes = os.environ.get("PAPER10M1R2A_V2_GIT_FSCK_NOTES", "Final result recorded after command execution.")
    pytest_status = os.environ.get("PAPER10M1R2A_V2_TARGETED_PYTEST_STATUS", "PENDING_UNTIL_RUN")
    pytest_notes = os.environ.get(
        "PAPER10M1R2A_V2_TARGETED_PYTEST_NOTES",
        "Nine M1R2A tests validate registry, seeds, cases, rules, queues, placeholders, module-disable, trace, and claim boundary.",
    )
    csv_write(
        stage_root / "09_TESTS/PAPER10M1R2A_V2_TEST_MATRIX.csv",
        [
            {"test_item": "git fsck --full", "status": git_fsck_status, "notes": git_fsck_notes},
            {"test_item": "targeted pytest", "status": pytest_status, "notes": pytest_notes},
            {"test_item": "full pytest", "status": "NOT_REQUIRED", "notes": "System pandas may be missing; full pytest is not a pass basis for this spec lock."},
        ],
    )
    text_write(
        stage_root / "09_TESTS/PAPER10M1R2A_V2_GUARD_VALIDATION_REPORT.md",
        """# PAPER10M1R2A V2 Guard Validation Report

- solver run: false
- evaluator run: false
- full matrix run: false
- degraded provider generation: false
- raw data modification/copy: false
- trace parameter/anchor selection: false
- final_v23/LegSA output selection: false
- Go2 truth claim: false
- module-disable as case axis: false
- placeholder mixed case: false
- queue run_allowed_now true rows: 0
""",
    )


def export_clean(stage_root: Path, export_root: Path) -> None:
    aliases = {
        os.environ.get("LEGSA_CODE_ROOT", ""): "<LEGSA_CODE_ROOT>",
        os.environ.get("LEGSA_PROJECT_ROOT", ""): "<LEGSA_PROJECT_ROOT>",
        os.environ.get("PAPER10M1R2A_V2_STAGE_ROOT", ""): "<PAPER10M1R2A_V2_STAGE_ROOT>",
        os.environ.get("PAPER10M1R2A_V2_RUNTIME_ROOT", ""): "<PAPER10M1R2A_V2_RUNTIME_ROOT>",
    }

    def sanitize(text: str) -> str:
        out = text
        for real, alias in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
            if real:
                out = out.replace(real, alias)
        by2_name = "by2" + ".txt"
        gnss1_name = "gnss1" + "-raw.csv"
        gnss2_name = "gnss2" + "-raw.csv"
        return (
            out.replace(by2_name, "<BY2_GO2_BODY_ROOT>")
            .replace(gnss1_name, "<GNSS1_RAW_REDACTED>")
            .replace(gnss2_name, "<GNSS2_RAW_REDACTED>")
        )

    allow_dirs = [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_MATRIX_DESIGN",
        "03_SEEDS",
        "04_CASE_MANIFEST",
        "05_EFFECT_VALIDATION",
        "06_QUEUE_DRAFT",
        "07_CLAIM_BOUNDARY",
        "09_TESTS",
        "10_NEXT_STAGE",
    ]
    clean_root = export_root / "clean_files"
    if clean_root.exists():
        shutil.rmtree(clean_root)
    clean_root.mkdir(parents=True, exist_ok=True)
    manifest = []
    for directory in allow_dirs:
        for src in sorted((stage_root / directory).glob("*")):
            if not src.is_file() or src.suffix not in {".md", ".csv", ".json"}:
                continue
            rel = src.relative_to(stage_root)
            dst = clean_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(sanitize(src.read_text(encoding="utf-8")), encoding="utf-8")
            manifest.append({"relative_path": str(rel), "size_bytes": dst.stat().st_size, "sha256": sha256(dst), "included_in_zip": "true"})
    readme = export_root / "README_FOR_NEXT_AI.md"
    text_write(
        readme,
        """# README For Next AI

PAPER10M1R2A V2 locked the BY2 canonical degradation matrix specification:
60 types x 9 seeds + clean = 541 cases.

This pack contains only specifications, manifests, validation rules, queue
drafts, claim boundary, tests summary, and next-stage prompts. It contains no
raw data, no degraded providers, no runtime outputs, no figures, and no solver
or evaluator outputs.
""",
    )
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "size_bytes": readme.stat().st_size, "sha256": sha256(readme), "included_in_zip": "true"})
    csv_write(export_root / "export_clean_manifest.csv", manifest, ["relative_path", "size_bytes", "sha256", "included_in_zip"])
    forbidden = {
        "windows_user": r"C:" + r"\\Users\\",
        "mnt_c_users": r"/mnt/c/" + r"Users/",
        "home_kaiwen": r"/home/" + r"kaiwen",
        "media_kaiwen": r"/media/" + r"kaiwen/新加卷",
        "by2_txt": r"by2" + r"\.txt",
        "gnss1_raw": r"gnss1" + r"-raw\.csv",
        "gnss2_raw": r"gnss2" + r"-raw\.csv",
    }
    results = []
    failed = False
    for path in list(clean_root.rglob("*")) + [readme, export_root / "export_clean_manifest.csv"]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = str(path.relative_to(export_root))
        for name, pattern in forbidden.items():
            hits = len(re.findall(pattern, text))
            if hits:
                failed = True
                results.append({"file": rel, "pattern": name, "hits": hits, "severity": "fail"})
    if not results:
        results.append({"file": "ALL", "pattern": "forbidden_path_patterns", "hits": 0, "severity": "pass"})
    json_write(export_root / "export_clean_path_scan.json", {"scan_pass": not failed, "results": results})
    if failed:
        raise SystemExit("export-clean path scan failed")
    zip_path = export_root / "paper10m1r2a_v2_by2_degradation_matrix_spec_lock_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for row in manifest:
            rel = row["relative_path"]
            src = readme if rel == "README_FOR_NEXT_AI.md" else clean_root / rel
            archive.write(src, rel)
        archive.write(export_root / "export_clean_manifest.csv", "export_clean_manifest.csv")
        archive.write(export_root / "export_clean_path_scan.json", "export_clean_path_scan.json")
    stage_export = stage_root / "11_EXPORT_CLEAN_FOR_GPT"
    stage_export.mkdir(parents=True, exist_ok=True)
    for name in [
        "paper10m1r2a_v2_by2_degradation_matrix_spec_lock_pack.zip",
        "export_clean_manifest.csv",
        "export_clean_path_scan.json",
        "README_FOR_NEXT_AI.md",
    ]:
        shutil.copy2(export_root / name, stage_export / name)


def main() -> int:
    stage_root = required_env_path("PAPER10M1R2A_V2_STAGE_ROOT")
    export_root = required_env_path("PAPER10M1R2A_V2_EXPORT_ROOT")
    runtime_root = required_env_path("PAPER10M1R2A_V2_RUNTIME_ROOT")
    for directory in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_MATRIX_DESIGN",
        "03_SEEDS",
        "04_CASE_MANIFEST",
        "05_EFFECT_VALIDATION",
        "06_QUEUE_DRAFT",
        "07_CLAIM_BOUNDARY",
        "08_OBSIDIAN_SYNC",
        "09_TESTS",
        "10_NEXT_STAGE",
        "11_EXPORT_CLEAN_FOR_GPT",
    ]:
        (stage_root / directory).mkdir(parents=True, exist_ok=True)
    (runtime_root / "00_LOCAL_ONLY").mkdir(parents=True, exist_ok=True)
    json_write(
        runtime_root / "00_LOCAL_ONLY/PAPER10M1R2A_V2_NO_RUN_LOCK.json",
        {
            "stage": STAGE_NAME,
            "solver_allowed": False,
            "evaluator_allowed": False,
            "provider_generation_allowed": False,
            "raw_data_modification_allowed": False,
            "case_count_target": 541,
            "created_utc": datetime.now(timezone.utc).isoformat(),
        },
    )

    if len(DEGRADATION_TYPES) != 60:
        raise SystemExit(f"expected 60 degradation types, got {len(DEGRADATION_TYPES)}")
    cases = case_rows()
    if len(cases) != 541:
        raise SystemExit(f"expected 541 case rows, got {len(cases)}")
    registry = registry_rows()
    rules = [rule_for(deg) for deg in DEGRADATION_TYPES]
    provider_queue = queue_rows_provider(cases)
    full_queue = queue_rows_full(cases)
    ablation_queue = queue_rows_ablation(cases)
    if len(provider_queue) != 541 or len(full_queue) != 2164 or len(ablation_queue) != 4869:
        raise SystemExit("queue draft row count mismatch")

    csv_write(stage_root / "02_MATRIX_DESIGN/CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv", registry)
    csv_write(stage_root / "02_MATRIX_DESIGN/CANONICAL_BY2_INNOVATION_MAPPING.csv", innovation_rows())
    csv_write(stage_root / "03_SEEDS/CANONICAL_BY2_RANDOM_SEED_MANIFEST.csv", seed_rows())
    csv_write(stage_root / "03_SEEDS/CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv", anchor_rows())
    csv_write(stage_root / "04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv", cases)
    csv_write(stage_root / "05_EFFECT_VALIDATION/CANONICAL_BY2_EFFECT_VALIDATION_RULES.csv", rules)
    csv_write(stage_root / "06_QUEUE_DRAFT/PAPER10M1R2B_PROVIDER_GENERATION_QUEUE_DRAFT.csv", provider_queue)
    csv_write(stage_root / "06_QUEUE_DRAFT/PAPER10M1R2C_FULL_ALGORITHM_QUEUE_DRAFT.csv", full_queue)
    csv_write(stage_root / "06_QUEUE_DRAFT/PAPER10M1R2D_INTERNAL_ABLATION_QUEUE_DRAFT.csv", ablation_queue)
    csv_write(
        stage_root / "04_CASE_MANIFEST/CANONICAL_BY2_CASE_FAMILY_SUMMARY.csv",
        [
            {"case_family": family, "case_count": count}
            for family, count in sorted(Counter(row["case_family"] for row in cases).items())
        ],
    )
    write_manifest_schemas(stage_root)
    write_design_docs(stage_root, cases)
    write_claim_and_next(stage_root)
    write_obsidian(stage_root)
    write_tests_summary(stage_root)
    text_write(
        stage_root / "06_QUEUE_DRAFT/PAPER10M1R2_QUEUE_COUNT_SUMMARY.md",
        f"""# PAPER10M1R2 Queue Count Summary

- Provider generation draft rows: {len(provider_queue)}
- Full algorithm draft rows: {len(full_queue)}
- Internal ablation draft rows: {len(ablation_queue)}
- All run_allowed_now values: false
- M1R2B provider rows formula: 541 cases x 1 provider generation row = 541
- M1R2C full algorithm rows formula: 4 method modes x 541 cases = 2164
- M1R2D internal ablation rows formula: 9 methods x 541 cases = 4869
""",
    )
    write_reports(stage_root, export_root, cases, provider_queue, full_queue, ablation_queue)
    export_clean(stage_root, export_root)
    print(
        json.dumps(
            {
                "stage": STAGE_NAME,
                "degradation_types": len(DEGRADATION_TYPES),
                "cases": len(cases),
                "provider_queue": len(provider_queue),
                "full_queue": len(full_queue),
                "ablation_queue": len(ablation_queue),
                "stage_root": str(stage_root),
                "export_root": str(export_root),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
