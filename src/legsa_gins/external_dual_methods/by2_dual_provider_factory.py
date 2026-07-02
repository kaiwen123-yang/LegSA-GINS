"""BY2 input contract preflight for external dual-antenna methods."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


RECEIVER_FILES: tuple[str, ...] = (
    "gnss1-status.csv",
    "gnss2-status.csv",
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
    "userio-raw.csv",
    "user_io-out-odom_status.csv",
    "user_io-out-poi_geodetic.csv",
    "user_io-out-poi_odometry.csv",
    "user_io-out-poi_smooth_odometry.csv",
    "user_io-status.csv",
    "imu-data.csv",
    "imu-biases.csv",
    "imu-temp.csv",
    "ntrip-info.csv",
    "ntrip-latency.csv",
    "tf.csv",
    "tf_static.csv",
)

REQUIRED_FOR_EXTERNAL_DUAL: tuple[str, ...] = (
    "gnss1-status.csv",
    "gnss2-status.csv",
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
)


@dataclass(frozen=True)
class InputFileStatus:
    file_name: str
    role: str
    required_for_q2r2: bool
    exists: bool
    size_bytes: int
    notes: str


def receiver_file_role(file_name: str) -> str:
    roles = {
        "gnss1-status.csv": "GNSS1 status, right antenna, source-backed dual yaw/relpos context",
        "gnss2-status.csv": "GNSS2 status, left antenna, source-backed dual yaw/relpos context",
        "gnss1-raw.csv": "GNSS1 raw carrier/code/Doppler source for DD/LOS feasibility",
        "gnss2-raw.csv": "GNSS2 raw carrier/code/Doppler source for DD/LOS feasibility",
        "corr-raw.csv": "Correction/NTRIP context for raw GNSS feasibility",
        "imu-data.csv": "Receiver IMU diagnostic only; forbidden as Go2 body IMU",
    }
    return roles.get(file_name, "Receiver auxiliary status/output source")


def audit_receiver_root(receiver_root: Path) -> list[InputFileStatus]:
    rows: list[InputFileStatus] = []
    for file_name in RECEIVER_FILES:
        path = receiver_root / file_name
        rows.append(
            InputFileStatus(
                file_name=file_name,
                role=receiver_file_role(file_name),
                required_for_q2r2=file_name in REQUIRED_FOR_EXTERNAL_DUAL,
                exists=path.exists(),
                size_bytes=path.stat().st_size if path.exists() else 0,
                notes="" if path.exists() else "missing_in_current_environment",
            )
        )
    trace_candidates = sorted(receiver_root.glob("trace_vrtk2*.csv")) if receiver_root.exists() else []
    rows.append(
        InputFileStatus(
            file_name="trace_vrtk2_*.csv",
            role="Evaluation reference only",
            required_for_q2r2=True,
            exists=bool(trace_candidates),
            size_bytes=sum(path.stat().st_size for path in trace_candidates) if trace_candidates else 0,
            notes="trace_eval_only" if trace_candidates else "missing_in_current_environment",
        )
    )
    return rows


def audit_go2_body(go2_body_path: Path) -> dict[str, str]:
    return {
        "source_id": "by2_go2_body",
        "role": "Go2 sportmodestate/high-level body context; not truth",
        "path_placeholder": "<BY2_GO2_BODY_ROOT>",
        "exists": "true" if go2_body_path.exists() else "false",
        "size_bytes": str(go2_body_path.stat().st_size if go2_body_path.exists() else 0),
        "receiver_imu_as_body_imu": "false",
        "go2_truth_claim_allowed": "false",
        "notes": "" if go2_body_path.exists() else "missing_in_current_environment",
    }


def provider_contract_closed(receiver_rows: list[InputFileStatus], go2_body_exists: bool) -> tuple[bool, list[str]]:
    missing = [row.file_name for row in receiver_rows if row.required_for_q2r2 and not row.exists]
    if not go2_body_exists:
        missing.append("by2.txt")
    return not missing, missing


def load_q2r2_case_manifest(canonical_manifest: Path, limit: int = 120) -> list[dict[str, str]]:
    """Build a deterministic Q2R2 120-case queue from the canonical BY2 manifest.

    This does not generate new degradations.  It selects existing case IDs only.
    """

    with canonical_manifest.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: int(row.get("case_index", "0") or 0))
    selected = rows[:limit]
    return [
        {
            "q2r2_case_index": str(index),
            "case_id": row.get("case_id", ""),
            "source_case_index": row.get("case_index", ""),
            "dataset": row.get("dataset", "BY2"),
            "case_family": row.get("case_family", ""),
            "degradation_type_id": row.get("degradation_type_id", ""),
            "degradation_type_name": row.get("degradation_type_name", ""),
            "trace_eval_only": row.get("trace_eval_only", "true"),
            "final_v23_output_solver_input_allowed": row.get("final_v23_output_solver_input_allowed", "false"),
            "legsa_output_solver_input_allowed": row.get("legsa_output_solver_input_allowed", "false"),
            "notes": "Q2R2 selected existing canonical case; no new random generation.",
        }
        for index, row in enumerate(selected)
    ]
