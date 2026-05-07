"""BY2 input manifest generator for N4E.

中文说明：manifest 只记录 source role 与禁止项状态；不保存本地绝对路径，不提交 raw data，不做 performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FORBIDDEN_FALSE_FLAGS = [
    "trace_solver_input",
    "trace_used_for_tuning",
    "output_only_correction",
    "receiver_imu_as_body_imu",
    "final_v23_output_substitution",
    "raw_data_committed",
    "raw_doppler_extracted",
    "go2_prior_claim",
    "source_aware_weighting_claim",
    "fgo_smoother_claim",
]


def _basename(path: str | Path | None) -> str:
    if path is None:
        return ""
    return Path(path).name


def _generated_outputs(generated_outputs: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in generated_outputs.items():
        if isinstance(value, (str, Path)):
            sanitized[key] = _basename(value)
        else:
            sanitized[key] = value
    return sanitized


def create_by2_input_manifest(
    output_dir: str | Path,
    gnss1_status_path: str | Path,
    gnss2_status_path: str | Path,
    gnss1_raw_path: str | Path,
    gnss2_raw_path: str | Path,
    trace_path: str | Path,
    receiver_imu_data_path: str | Path,
    body_state_path: str | Path,
    generated_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Create a sanitized BY2 source-role manifest."""
    # 中文说明：输入路径只用于 basename 证据，避免把 WSL/Windows 本地绝对路径写入 tracked 文件。
    input_files = {
        "gnss1_status": _basename(gnss1_status_path),
        "gnss2_status": _basename(gnss2_status_path),
        "gnss1_raw": _basename(gnss1_raw_path),
        "gnss2_raw": _basename(gnss2_raw_path),
        "trace": _basename(trace_path),
        "receiver_imu_data": _basename(receiver_imu_data_path),
        "body_state_text": _basename(body_state_path),
    }
    manifest = {
        "dataset_name": "BY2",
        "phase": "N4E",
        "path_policy": {
            "local_absolute_paths_recorded": False,
            "path_recording": "basename_only",
            "output_dir_recorded": _basename(output_dir),
        },
        "input_files": input_files,
        "source_roles": {
            "gnss1_status": "receiver_native_gnss_status",
            "gnss2_status": "receiver_native_gnss_status",
            "gnss1_raw": "raw_gnss_message_stream_scanned_only",
            "gnss2_raw": "raw_gnss_message_stream_scanned_only",
            "trace": "evaluation_reference_only",
            "receiver_imu_data": "receiver_internal_imu_not_body_imu",
            "body_state_text": "go2_body_state_diagnostic",
        },
        "solver_input_policy": {
            "trace_solver_input": False,
            "trace_used_for_tuning": False,
            "trace_evaluation_only": True,
            "output_only_correction": False,
            "receiver_imu_as_body_imu": False,
            "final_v23_output_substitution": False,
            "raw_data_committed": False,
            "raw_doppler_extracted": False,
            "go2_prior_claim": False,
            "source_aware_weighting_claim": False,
            "fgo_smoother_claim": False,
        },
        "frame_policy": {
            "go2_body_frame": "FLU",
            "body_state_requires_frame_adapter": True,
            "odom_not_navigation_frame": True,
        },
        "generated_outputs": _generated_outputs(generated_outputs),
        "evidence_status": "source_roles_manifested_no_performance_evaluation",
    }
    return manifest


def write_manifest(manifest: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
