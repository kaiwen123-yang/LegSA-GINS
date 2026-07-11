"""Focused tests for the frozen CLEAN1R1C kick/window contract."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.kick_alignment import (
    FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS,
    build_kick_aligned_contract,
    freeze_kick_alignment_contracts,
)
from legsa_gins.paper_rebuild.manifest import sha256_text
from legsa_gins.paper_rebuild.paths import load_yaml_mapping
from legsa_gins.paper_rebuild.protocol import (
    OPTIONAL_START_STREAMS,
    PROTOCOL_ID,
    ProtocolContractError,
    REQUIRED_WINDOW_STREAMS,
    STAGE_ID,
    V2_WINDOW_POLICY,
    build_common_covariance_contract,
    compute_kick_aligned_window,
    coverage_from_timestamps,
    freeze_window_contract,
    load_clean1_protocol,
    load_frozen_window,
)


ROOT = Path(__file__).resolve().parents[2]
DIGEST = "a" * 64


def _write_go2_text(path: Path, *, base_time: int = 1_700_000_000) -> None:
    messages: list[str] = []
    for index in range(80):
        nanosec = index * 20_000_000
        acc_x = 0.01 * math.sin(index * 0.31)
        gyro_z = 0.002 * math.sin(index * 0.17)
        if index == 25:
            acc_x = 30.0
            gyro_z = 12.0
        mode = 1 if index < 60 else 2
        gait = 0 if index < 60 else 1
        messages.append(
            "\n".join(
                [
                    "stamp:",
                    f"  sec: {base_time}",
                    f"  nanosec: {nanosec}",
                    "imu_state:",
                    "  quaternion: [1.0, 0.0, 0.0, 0.0]",
                    f"  gyroscope: [0.0, 0.0, {gyro_z}]",
                    f"  accelerometer: [{acc_x}, 0.0, 9.80665]",
                    "  rpy: [0.0, 0.0, 0.0]",
                    f"mode: {mode}",
                    f"gait_type: {gait}",
                    "position: [0.0, 0.0, 0.0]",
                    "velocity: [0.0, 0.0, 0.0]",
                    "yaw_speed: 0.0",
                    "foot_force: [0.0, 0.0, 0.0, 0.0]",
                    "foot_position_body: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]",
                    "foot_speed_body: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]",
                    "---",
                ]
            )
        )
    path.write_text("\n".join(messages), encoding="utf-8")


def _common_initialization(
    protocol_path: Path, *, start: float = 0.6
) -> dict[str, object]:
    protocol = load_clean1_protocol(protocol_path)
    covariance = build_common_covariance_contract(protocol.payload["solver_common"])
    return {
        "position_geodetic_deg_m": [40.0, 116.0, 10.0],
        "velocity_ned_mps": [0.0, 0.0, 0.0],
        "roll_pitch_deg": [0.0, 0.0],
        "yaw_ned_deg": 90.0,
        "bias_scale_state": [0.0] * 12,
        "covariance_diagonal": covariance["covariance_diagonal_internal"],
        "covariance_contract": covariance,
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
        "position_initialization_timestamp": start,
        "velocity_initialization_timestamp": start - 0.1,
        "roll_pitch_initialization_timestamp": start - 0.05,
        "yaw_initialization_timestamp": start,
        "future_observation_used_for_initialization": False,
        "yaw_source_role": "fixed_physical_dual_yaw_at_common_start",
        "trace_used": False,
        "method_specific": False,
        "common_initialization_dual_yaw_used": True,
    }


def test_frozen_kick_alignment_emits_alias_only_contracts(tmp_path: Path) -> None:
    go2 = tmp_path / "by2.txt"
    _write_go2_text(go2)
    output = tmp_path / "protocol"
    result = freeze_kick_alignment_contracts(
        go2,
        propagation_imu_timestamps=[0.0, 0.2, 0.6, 1.0, 2.5],
        core_gnss_timestamps=[0.1, 0.4, 0.6, 1.2, 2.0],
        dual_yaw_valid_timestamps=[0.1, 0.4, 0.6, 1.2, 2.0],
        source_time_origin_seconds=1_700_000_000.0,
        output_dir=output,
    )

    assert result["fixed_event_alignment_offset"] == FIXED_EVENT_ALIGNMENT_OFFSET_SECONDS
    assert result["t_start"] == 0.6
    assert result["t_end"] == 2.0
    assert result["optional_streams_delay_start"] is False
    report = json.loads((output / "KICK_EVENT_ALIGNMENT_REPORT.json").read_text(encoding="utf-8"))
    assert report["kick_alignment_pass"] is True
    assert report["maintained_candidate_status"] == "detected"
    assert report["trace_used_for_alignment"] is False
    assert report["offset_search_performed"] is False
    assert report["method_specific_shift"] is False
    assert report["maintained_detect_go2_kick_event_defaults"]["zscore_threshold"] == 6.0
    assert set(report["maintained_source_hashes"]) == {
        "src/legsa_gins/datasets/by2/go2_body_state_parser.py",
        "src/legsa_gins/datasets/by2/unitree_imu_semantics.py",
        "src/legsa_gins/time_alignment/event_normalization.py",
        "src/legsa_gins/time_alignment/time_domain_audit.py",
    }
    rows = list(csv.DictReader((output / "KICK_EVENT_DIAGNOSTIC.csv").open(encoding="utf-8")))
    assert sum(row["selected"] == "True" for row in rows) == 1
    exported = "\n".join(path.read_text(encoding="utf-8") for path in output.iterdir())
    assert str(tmp_path) not in exported


def test_v2_protocol_and_window_ignore_optional_first_availability(tmp_path: Path) -> None:
    protocol_path = ROOT / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"
    protocol = load_clean1_protocol(protocol_path)
    assert protocol.payload["stage_id"] == STAGE_ID
    assert protocol.payload["protocol_id"] == PROTOCOL_ID
    assert protocol.payload["window"]["policy"] == V2_WINDOW_POLICY
    assert protocol.payload["solver_common"]["antenna_lever_m"] == [0.03, 0.03, -0.30]

    optional = set(OPTIONAL_START_STREAMS)
    coverages = []
    for role in REQUIRED_WINDOW_STREAMS:
        timestamps = [1.5, 2.0] if role in optional else [0.0, 2.0]
        coverages.append(
            coverage_from_timestamps(
                role,
                timestamps,
                source_alias="<PROVIDER_ROOT>",
                relative_path=f"providers/{role}.csv",
                source_sha256=DIGEST,
            )
        )
    window = compute_kick_aligned_window(
        coverages,
        core_gnss_timestamps=[0.1, 0.4, 0.6, 1.2, 2.0],
        dual_yaw_timestamps=[0.1, 0.4, 0.6, 1.2, 2.0],
        mapped_kick_provider_time=0.5,
        source_time_origin_seconds=1_700_000_000.0,
        common_initialization=_common_initialization(protocol_path),
    )
    assert window.t_start == 0.6
    assert window.t_end == 2.0
    assert window.policy == V2_WINDOW_POLICY
    assert window.optional_streams_delay_start is False

    freeze_window_contract(protocol, window, tmp_path)
    frozen = load_frozen_window(tmp_path / "WINDOW_CONTRACT.yaml")
    assert frozen["schema_version"] == "paper-rebuild-window-contract-v2"
    assert frozen["first_valid_gnss_after_kick"] == 0.6
    assert frozen["optional_streams_delay_start"] is False
    assert load_yaml_mapping(tmp_path / "WINDOW_CONTRACT.yaml")["protocol_id"] == PROTOCOL_ID

    tampered = load_yaml_mapping(tmp_path / "WINDOW_CONTRACT.yaml")
    initialization = tampered["common_initialization"]
    initialization["position_initialization_timestamp"] = 1.6
    initialization["yaw_initialization_timestamp"] = 1.6
    tampered["common_initialization_hash"] = sha256_text(
        json.dumps(
            initialization,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    tampered_path = tmp_path / "WINDOW_CONTRACT.tampered.yaml"
    tampered_path.write_text(
        json.dumps(tampered, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with pytest.raises(ProtocolContractError, match="common start"):
        load_frozen_window(tampered_path)


def test_integration_entrypoint_reads_formal_18_column_validity(tmp_path: Path) -> None:
    go2 = tmp_path / "by2.txt"
    _write_go2_text(go2)
    gnss = tmp_path / "GNSS-RTK.txt"
    rows = []
    for timestamp in (0.1, 0.4, 0.6, 1.0, 1.2):
        fields = ["0"] * 18
        fields[0] = str(timestamp)
        fields[15] = "1"
        fields[16] = "0"
        fields[17] = "1"
        rows.append(" ".join(fields))
    gnss.write_text("\n".join(rows) + "\n", encoding="utf-8")
    imu = tmp_path / "IMU.txt"
    imu.write_text(
        "\n".join(
            " ".join([str(timestamp), "0", "0", "0", "0", "0", "0"])
            for timestamp in (0.0, 0.2, 0.6, 1.0, 1.4)
        )
        + "\n",
        encoding="utf-8",
    )

    result = build_kick_aligned_contract(
        go2,
        gnss,
        imu,
        tmp_path / "contracts",
        1_700_000_000.0,
    )
    assert result["t_start"] == 0.6
    assert result["t_end"] == 1.2
    assert result["gnss_position_valid_epoch_count"] == 5
    assert result["dual_yaw_valid_epoch_count"] == 5
    assert result["propagation_imu_epoch_count"] == 5
