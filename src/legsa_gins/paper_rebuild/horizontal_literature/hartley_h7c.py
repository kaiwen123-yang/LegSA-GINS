from __future__ import annotations

import csv
import decimal
import hashlib
import inspect
import io
import json
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml


TASK_START_HEAD = "ff0202f8029ded5c141eb82ef526c85096abe786"
EXPECTED_BRANCH = "stage/clean3-math-repair"
CONTRACT_RELATIVE = Path(
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "04_METHOD_CONTRACTS/H7C_SOURCE_RECOVERY_CONTRACT.yaml"
)
PUBLICATION_ROOT_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/10_H7C_REFERENCE_EXTRINSIC_CLOSURE"
)
CONTRACT_COPY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "00_CONTRACTS/H7C_SOURCE_RECOVERY_CONTRACT.yaml"
)
CONTRACT_FREEZE_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "00_CONTRACTS/H7C_CONTRACT_FREEZE.json"
)
PREDECESSOR_PRE_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "00_PREFLIGHT/H7C_PREDECESSOR_PRE_SNAPSHOT.json"
)
PREDECESSOR_POST_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "09_PRESERVATION/H7C_PREDECESSOR_POST_SNAPSHOT.json"
)
RAW_INVENTORY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "01_SOURCE_ACCESS/H7C_RAW_ACCESS_INVENTORY.json"
)
ACCESS_LEDGER_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "01_SOURCE_ACCESS/H7C_SOURCE_ACCESS_LEDGER.json"
)
SCHEMA_HEADERS_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "02_SCHEMA/H7C_CSV_SCHEMA_HEADERS.json"
)
FIELD_MAP_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_TRACE_FIELD_MAP.json"
)
FIELD_MAP_FREEZE_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_TRACE_FIELD_MAP_FREEZE.json"
)
TRACE_IDENTITY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_TRACE_POI_GEODETIC_IDENTITY.json"
)
TRACE_PROOF_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_TRACE_LINEAGE_PROOF.md"
)
LINEAGE_AUX_FAILURE_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_LINEAGE_AUXILIARY_PARSE_FAILURE.json"
)
FIELD_MAP_UNIT_CORRECTION_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_TRACE_FIELD_MAP_UNIT_CORRECTION.json"
)
SERIALIZATION_CONTRACT_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_DECIMAL_SERIALIZATION_EQUIVALENCE_CONTRACT.json"
)
SERIALIZATION_CONTRACT_FREEZE_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_DECIMAL_SERIALIZATION_EQUIVALENCE_FREEZE.json"
)
SERIALIZATION_IDENTITY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_TRACE_DECIMAL_SERIALIZATION_IDENTITY.json"
)
SERIALIZATION_PROOF_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_TRACE_LINEAGE_SERIALIZATION_PROOF.md"
)
REQUIRED_FIELD_MAP_CSV_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/TRACE_TO_POI_GEODETIC_FIELD_MAP.csv"
)
REQUIRED_LINEAGE_IDENTITY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/TRACE_TO_POI_GEODETIC_IDENTITY.json"
)
REQUIRED_LINEAGE_PROOF_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/REFERENCE_LINEAGE_PROOF.md"
)
EXACT_BINARY_INTERPRETATION_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "03_LINEAGE/H7C_EXACT_BINARY_DIAGNOSTIC_INTERPRETATION.json"
)
FINAL_ACCESS_LEDGER_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "01_SOURCE_ACCESS/H7C_FINAL_SOURCE_ACCESS_LEDGER.json"
)
TERMINAL_AUDIT_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "08_TERMINAL/H7C_LINEAGE_TERMINAL_AUDIT.json"
)
EVALUATION_FREEZE_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "08_TERMINAL/H7C_EVALUATION_FREEZE.json"
)
STORAGE_HEALTH_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "00_PREFLIGHT/H7C_STORAGE_HEALTH_READ_ONLY.json"
)
FINAL_STATUS_RELATIVE = Path("11_REPORT/LSE01_H7C_FINAL_STATUS.json")
FINAL_REPORT_RELATIVE = Path("11_REPORT/LSE01_H7C_FINAL_REPORT.md")
FINAL_CLAIM_RELATIVE = Path("11_REPORT/LSE01_FINAL_CLAIM_BOUNDARY.md")
TRACKED_FINAL_CLAIM_RELATIVE = Path(
    "docs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "11_REPORT/LSE01_FINAL_CLAIM_BOUNDARY.md"
)
PUBLICATION_MANIFEST_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "H7C_PUBLICATION_MANIFEST.json"
)
PUBLICATION_PARITY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "H7C_PUBLICATION_PARITY.json"
)
EXPECTED_STAGE_SUFFIX = Path(
    "LegSA-GINS-project/clean_rebuild_202607/stages/"
    "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/07_LSE01_HARTLEY_CONTACT_INEKF"
)
RAW_CAPTURE_STEM = Path(
    "BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/"
    "vrtk2_a87c6e_2026-03-06-08-00-54_minimal"
)
RAW_FILENAMES = (
    "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv",
    "user_io-out-poi_geodetic.csv",
    "user_io-out-poi_odometry.csv",
    "user_io-out-poi_smooth_odometry.csv",
    "tf.csv",
    "tf_static.csv",
    "userio-raw.csv",
    "user_io-status.csv",
    "vrtk2_a87c6e_2026-03-06-08-00-54_minimal.fpl",
    "vrtk2_a87c6e_2026-03-06-08-00-54_minimal.bag",
)
RAW_RELATIVE_PATHS = {
    filename: (
        Path(f"{RAW_CAPTURE_STEM}{Path(filename).suffix}")
        if Path(filename).suffix in {".fpl", ".bag"}
        else RAW_CAPTURE_STEM / filename
    )
    for filename in RAW_FILENAMES
}
ALLOWED_UNRELATED_UNTRACKED = {
    "scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py": {
        "sha256": "00a54aac97ec54715c47dda9350635aa3ea3e969e5deb152e52e33614a6a6480",
        "size": 432,
    },
    "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py": {
        "sha256": "d021a503bc91dbd6a194182478770a1457cf0ca615c7d3adb2f7a6f68eadea16",
        "size": 65596,
    },
}
H7C_TRACKED_PATHS = {
    str(CONTRACT_RELATIVE),
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7c.py",
    "scripts/paper_rebuild/evaluate_hartley_h7c.py",
    "tests/paper_rebuild/test_hartley_h7c_contracts.py",
    (
        "docs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
        "11_REPORT/LSE01_FINAL_CLAIM_BOUNDARY.md"
    ),
}
H6R_PARITY_RELATIVE = Path("11_REPORT/H6R_EXTERNAL_PUBLICATION_PARITY.json")
H6R_MANIFEST_RELATIVE = Path("11_REPORT/H6R_EXTERNAL_PUBLICATION_MANIFEST.json")
ORIGINAL_H7_PARITY_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_PUBLICATION_PARITY.json"
)
ORIGINAL_H7_MANIFEST_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_PUBLICATION_MANIFEST.json"
)
H7R1_PARITY_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/08_BLOCKER_PROVENANCE_RECOVERY/"
    "H7R1_PUBLICATION_PARITY.json"
)
H7R1_MANIFEST_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/08_BLOCKER_PROVENANCE_RECOVERY/"
    "H7R1_PUBLICATION_MANIFEST.json"
)
H7R2_PARITY_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/09_PATH_ALIAS_RECOVERY/H7R2_PUBLICATION_PARITY.json"
)
H7R2_MANIFEST_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/09_PATH_ALIAS_RECOVERY/H7R2_PUBLICATION_MANIFEST.json"
)
PASS_A = "PASS_LSE01_H7C_FULL_RELATIVE_EVALUATION_COMPLETE"
PASS_B = "PASS_LSE01_COMPLETE_WITH_REFERENCE_EXTRINSIC_LIMITATION"
BLOCKED_LINEAGE = "BLOCKED_LSE01_H7C_REFERENCE_LINEAGE_CONTRADICTED"
BLOCKED_FRAME_GRAPH = "BLOCKED_LSE01_H7C_FRAME_GRAPH_CONTRADICTED"
BLOCKED_EXTRINSIC = "BLOCKED_LSE01_H7C_EXTRINSIC_SOURCE_CONTRADICTED"
PROOF_CLASSES = {
    "SOURCE_EXPLICIT",
    "DETERMINISTIC_FIELD_MAPPING",
    "NUMERICAL_IDENTITY_CROSSCHECK",
    "UNPROVEN",
    "CONTRADICTED",
}
V1_CONTRACT_FREEZE_SHA256 = (
    "3375eab8d2b26b3f44b9969bc603aea6abac9806d53a29ac158a5e8de571d2ec"
)
V1_CONTRACT_FREEZE_SIZE = 1215
V1_CONTRACT_SHA256 = "bb19f713796346440dd3af042acb87db2a02d82a05f664bb7f07bbc8595b33c3"
V1_CONTRACT_SIZE = 10490
V1_FAILURE_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "00_PREFLIGHT/H7C_V1_PATH_RESOLUTION_FAILURE.json"
)


class HartleyH7CError(RuntimeError):
    """A frozen H7C safety, provenance, or scientific contract failed."""


def quaternion_xyzw_to_rotation(quaternion: Sequence[float]) -> np.ndarray:
    value = np.asarray(quaternion, dtype=np.float64)
    if value.shape != (4,) or not np.all(np.isfinite(value)):
        raise HartleyH7CError("finite xyzw quaternion required")
    norm = float(np.linalg.norm(value))
    if abs(norm - 1.0) > 1.0e-9:
        raise HartleyH7CError(f"quaternion normalization failure: {norm}")
    x, y, z, w = value / norm
    return np.asarray([
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
    ])


def fp_a_tf_wxyz_to_parent_from_child(
    frame_a: str,
    frame_b: str,
    translation: Sequence[float],
    quaternion_wxyz: Sequence[float],
) -> dict[str, Any]:
    """Decode official FP_A-TF order/direction without an inferred inversion."""
    if not frame_a or not frame_b:
        raise HartleyH7CError("FP_A-TF frame_a and frame_b are required")
    value = np.asarray(quaternion_wxyz, dtype=np.float64)
    if value.shape != (4,):
        raise HartleyH7CError("FP_A-TF quaternion must have WXYZ length four")
    w, x, y, z = value
    return {
        "parent_frame": frame_a,
        "child_frame": frame_b,
        "transform_convention": "T_parent_from_child",
        "input_quaternion_order": "wxyz",
        "transform_parent_from_child": rigid_transform(
            quaternion_xyzw_to_rotation([x, y, z, w]), translation
        ),
    }


def resolve_body_alias(candidate: Mapping[str, Any]) -> str:
    """Resolve the ambiguous BODY label only from an explicit source record."""
    if candidate.get("alias") != "BODY":
        raise HartleyH7CError("BODY alias record required")
    target = candidate.get("canonical_frame")
    provenance = candidate.get("source_explicit_provenance")
    if (
        not isinstance(target, str)
        or not target
        or not isinstance(provenance, str)
        or not provenance
        or candidate.get("proof_classification") != "SOURCE_EXPLICIT"
    ):
        raise HartleyH7CError("BODY alias is UNPROVEN without explicit provenance")
    return target


def rotation_z(angle_rad: float) -> np.ndarray:
    cosine, sine = math.cos(angle_rad), math.sin(angle_rad)
    return np.asarray([
        [cosine, -sine, 0.0],
        [sine, cosine, 0.0],
        [0.0, 0.0, 1.0],
    ])


def rigid_transform(rotation: Sequence[Sequence[float]], translation: Sequence[float]) -> np.ndarray:
    rotation_array = np.asarray(rotation, dtype=np.float64)
    translation_array = np.asarray(translation, dtype=np.float64)
    if rotation_array.shape != (3, 3) or translation_array.shape != (3,):
        raise HartleyH7CError("rigid transform requires 3x3 rotation and length-3 translation")
    if not np.allclose(rotation_array.T @ rotation_array, np.eye(3), atol=1.0e-12):
        raise HartleyH7CError("rigid transform rotation is not orthogonal")
    if not math.isclose(float(np.linalg.det(rotation_array)), 1.0, abs_tol=1.0e-12):
        raise HartleyH7CError("rigid transform rotation is not proper")
    result = np.eye(4)
    result[:3, :3] = rotation_array
    result[:3, 3] = translation_array
    return result


def invert_rigid_transform(transform: Sequence[Sequence[float]]) -> np.ndarray:
    value = np.asarray(transform, dtype=np.float64)
    if value.shape != (4, 4) or not np.allclose(value[3], [0.0, 0.0, 0.0, 1.0]):
        raise HartleyH7CError("4x4 homogeneous transform required")
    rotation = value[:3, :3]
    return rigid_transform(rotation.T, -(rotation.T @ value[:3, 3]))


def compose_rigid_transforms(*transforms: Sequence[Sequence[float]]) -> np.ndarray:
    result = np.eye(4)
    for transform in transforms:
        result = result @ np.asarray(transform, dtype=np.float64)
    return result


def convert_go2_pose_to_fp_poi(
    world_from_go2_body_imu: Sequence[Sequence[float]],
    fp_poi_from_go2_body_imu: Sequence[Sequence[float]],
) -> np.ndarray:
    return compose_rigid_transforms(
        world_from_go2_body_imu,
        invert_rigid_transform(fp_poi_from_go2_body_imu),
    )


def so3_geodesic_angle(rotation: Sequence[Sequence[float]]) -> float:
    value = np.asarray(rotation, dtype=np.float64)
    cosine = float(np.clip((np.trace(value) - 1.0) * 0.5, -1.0, 1.0))
    return math.acos(cosine)


def relative_pose_metrics(
    estimate0: Sequence[Sequence[float]],
    estimate1: Sequence[Sequence[float]],
    reference0: Sequence[Sequence[float]],
    reference1: Sequence[Sequence[float]],
) -> dict[str, float]:
    delta_estimate = invert_rigid_transform(estimate0) @ np.asarray(estimate1)
    delta_reference = invert_rigid_transform(reference0) @ np.asarray(reference1)
    error = invert_rigid_transform(delta_reference) @ delta_estimate
    angle = so3_geodesic_angle(error[:3, :3])
    return {
        "translation_error_m": float(np.linalg.norm(error[:3, 3])),
        "rotation_geodesic_error_rad": angle,
        "rotation_geodesic_error_deg": math.degrees(angle),
    }


def conjugated_rotation(
    relative_rotation: Sequence[Sequence[float]],
    unknown_fixed_rotation: Sequence[Sequence[float]],
) -> np.ndarray:
    relative = np.asarray(relative_rotation, dtype=np.float64)
    fixed = np.asarray(unknown_fixed_rotation, dtype=np.float64)
    return fixed.T @ relative @ fixed


def fixed_primary_yaw_translation_gauge(
    primary_rotation: Sequence[Sequence[float]],
    primary_position: Sequence[float],
    reference_rotation: Sequence[Sequence[float]],
    reference_position: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    primary = np.asarray(primary_rotation, dtype=np.float64)
    reference = np.asarray(reference_rotation, dtype=np.float64)
    primary_yaw = math.atan2(primary[1, 0], primary[0, 0])
    reference_yaw = math.atan2(reference[1, 0], reference[0, 0])
    yaw = rotation_z(reference_yaw - primary_yaw)
    translation = np.asarray(reference_position) - yaw @ np.asarray(primary_position)
    return yaw, translation


def apply_fixed_gauge_to_pose(
    yaw_rotation: Sequence[Sequence[float]],
    translation: Sequence[float],
    world_from_body: Sequence[Sequence[float]],
) -> np.ndarray:
    pose = np.asarray(world_from_body, dtype=np.float64)
    gauge = rigid_transform(yaw_rotation, translation)
    return gauge @ pose


def validate_extrinsic_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "from_frame", "to_frame", "translation_m", "rotation_xyzw",
        "convention", "direction", "applicable_configuration_and_time",
        "unique",
    )
    missing = [key for key in required if key not in candidate]
    forbidden_evidence_keys = (
        "rmse_selection_used",
        "trajectory_fitting_used",
        "go2_onboard_pose_used",
        "go2_onboard_yaw_used",
        "hartley_or_reference_derived_rotation_used",
        "final_v23_or_legsa_output_used",
    )
    forbidden_evidence = [
        key for key in forbidden_evidence_keys if candidate.get(key) is True
    ]
    source_proven = bool(candidate.get("source_proven"))
    accepted = (
        not missing
        and not forbidden_evidence
        and source_proven
        and candidate.get("unique") is True
    )
    return {
        "accepted": accepted,
        "missing_fields": missing,
        "forbidden_evidence": forbidden_evidence,
        "source_proven": source_proven,
        "unique": candidate.get("unique") is True,
    }


def classify_h7c_outcome(
    hypothesis_states: Mapping[str, str],
    *,
    unique_extrinsic_proven: bool,
    extrinsic_search_exhausted: bool,
) -> str:
    if hypothesis_states.get("H1") == "CONTRADICTED":
        return BLOCKED_LINEAGE
    if hypothesis_states.get("FRAME_GRAPH") == "CONTRADICTED":
        return BLOCKED_FRAME_GRAPH
    if hypothesis_states.get("EXTRINSIC") == "CONTRADICTED":
        return BLOCKED_EXTRINSIC
    closed = {
        "SOURCE_EXPLICIT",
        "DETERMINISTIC_FIELD_MAPPING_PLUS_NUMERICAL_IDENTITY_CROSSCHECK",
    }
    if any(hypothesis_states.get(f"H{index}") not in closed for index in range(1, 5)):
        raise HartleyH7CError("H1-H4 must close before selecting Outcome A or B")
    if unique_extrinsic_proven:
        return PASS_A
    if extrinsic_search_exhausted:
        return PASS_B
    raise HartleyH7CError("extrinsic search must close before selecting Outcome B")


def status_for_outcome(terminal: str) -> dict[str, Any]:
    common = {
        "terminal": terminal,
        "terminal_status": terminal,
        "lse01_algorithm_reproduction_complete": True,
        "lse01_native_real_data_complete": True,
        "lse01_yaw_unobservability_claim_complete": True,
        "absolute_yaw_RMSE": None,
        "absolute_global_position_RMSE": None,
        "parameter_selection_performed": False,
        "filter_rerun_count": 0,
        "ext06_executed": False,
    }
    if terminal == PASS_A:
        return {
            **common,
            "lse01_full_reference_relative_pose_evaluation_complete": True,
            "reference_point": "FP_POI",
            "reference_full_pose_source_closed": True,
            "go2_to_fp_poi_extrinsic_proven": True,
            "lse01_complete": True,
            "ready_for_ext06": True,
        }
    if terminal == PASS_B:
        return {
            **common,
            "lse01_full_reference_relative_pose_evaluation_complete": False,
            "reference_point": "FP_POI",
            "reference_full_pose_source_closed": True,
            "go2_to_fp_poi_extrinsic_proven": False,
            "lse01_complete": True,
            "ready_for_ext06": True,
        }
    if terminal in {BLOCKED_LINEAGE, BLOCKED_FRAME_GRAPH, BLOCKED_EXTRINSIC}:
        return {
            **common,
            "lse01_full_reference_relative_pose_evaluation_complete": False,
            "reference_point": None,
            "reference_full_pose_source_closed": False,
            "go2_to_fp_poi_extrinsic_proven": False,
            "lse01_complete": False,
            "ready_for_ext06": False,
        }
    raise HartleyH7CError(f"unsupported H7C terminal: {terminal}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_exclusive(path: Path, data: bytes) -> None:
    missing: list[Path] = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir()
        _fsync_directory(directory.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)


def write_json_exclusive(path: Path, value: Any) -> None:
    write_exclusive(path, _canonical_json(value))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise HartleyH7CError(f"JSON object required: {path}")
    return value


def file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise HartleyH7CError(f"required file is absent: {path}")
    return {"sha256": sha256_file(path), "size": path.stat().st_size}


def hash_size_parity(source: Path, published: Path) -> dict[str, Any]:
    source_identity = file_identity(source)
    published_identity = file_identity(published)
    return {
        "source": source_identity,
        "published": published_identity,
        "bytes_equal": source_identity == published_identity,
    }


def _identity_matches(path: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    actual = file_identity(path)
    normalized = {"sha256": str(expected["sha256"]), "size": int(expected["size"])}
    if actual != normalized:
        raise HartleyH7CError(
            f"frozen identity mismatch: {path}; expected={normalized}; actual={actual}"
        )
    return actual


def compute_contract_config_hash(contract: Mapping[str, Any]) -> str:
    normalized = json.loads(json.dumps(contract, ensure_ascii=False))
    config_hash = normalized.get("config_hash")
    if not isinstance(config_hash, dict):
        raise HartleyH7CError("contract config_hash mapping is absent")
    config_hash.pop("value", None)
    payload = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def load_and_validate_contract(repository: Path) -> tuple[dict[str, Any], Path]:
    path = repository / CONTRACT_RELATIVE
    contract = yaml.safe_load(path.read_text())
    if not isinstance(contract, dict):
        raise HartleyH7CError("H7C contract must be a YAML mapping")
    if contract.get("task_start_head") != TASK_START_HEAD:
        raise HartleyH7CError("H7C task-start identity mismatch")
    actual_hash = compute_contract_config_hash(contract)
    if contract.get("config_hash", {}).get("value") != actual_hash:
        raise HartleyH7CError("H7C canonical config hash mismatch")
    freeze = contract.get("reference_access_freeze", {})
    initial = freeze.get("initial_pre_access_freeze", {})
    expected_counters = {
        "trace_open_count": 0,
        "reference_output_open_count": 0,
        "reference_rows_read": 0,
    }
    if any(initial.get(key) != value for key, value in expected_counters.items()):
        raise HartleyH7CError("pre-reference counter freeze mismatch")
    if initial.get("contract_freeze_sha256") != V1_CONTRACT_FREEZE_SHA256:
        raise HartleyH7CError("initial H7C freeze identity mismatch")
    correction = freeze.get("v2_path_correction_freeze", {})
    if correction.get("zero_additional_raw_opens_between_v1_failure_and_v2_freeze") is not True:
        raise HartleyH7CError("V2 path correction did not preserve the raw-access pause")
    if correction.get("scientific_extrinsic_search_execution_count") != 0:
        raise HartleyH7CError("extrinsic search ran before corrected inventory freeze")
    hypotheses = contract.get("frozen_hypotheses", {})
    if hypotheses.get("H5", {}).get("initial_state") != "UNPROVEN":
        raise HartleyH7CError("H5 must be frozen UNPROVEN")
    if hypotheses.get("H5", {}).get("availability_assumed") is not False:
        raise HartleyH7CError("H5 availability must not be assumed")
    if set(contract.get("proof_classifications", {}).get("allowed", [])) != PROOF_CLASSES:
        raise HartleyH7CError("proof classification set mismatch")
    raw = contract.get("raw_access_allowlist", {})
    if raw.get("exact_file_count") != len(RAW_FILENAMES):
        raise HartleyH7CError("raw allowlist count mismatch")
    if tuple(row.get("name") for row in raw.get("files", [])) != RAW_FILENAMES:
        raise HartleyH7CError("raw allowlist names or order mismatch")
    relative_paths = {
        row["name"]: Path(str(row.get("relative_path", "")))
        for row in raw.get("files", [])
    }
    if relative_paths != RAW_RELATIVE_PATHS:
        raise HartleyH7CError("raw per-file relative path mapping mismatch")
    return contract, path


def _git_output(repository: Path, arguments: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=repository, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def verify_git_identity(repository: Path) -> dict[str, Any]:
    head = _git_output(repository, ["rev-parse", "HEAD"]).strip()
    branch = _git_output(repository, ["branch", "--show-current"]).strip()
    if head != TASK_START_HEAD or branch != EXPECTED_BRANCH:
        raise HartleyH7CError(f"Git identity mismatch: {branch}@{head}")
    lines = _git_output(
        repository, ["status", "--porcelain=v1", "--untracked-files=all"]
    ).splitlines()
    unrelated = set(ALLOWED_UNRELATED_UNTRACKED)
    observed_unrelated = {line[3:] for line in lines if line.startswith("?? ")} & unrelated
    if observed_unrelated != unrelated:
        raise HartleyH7CError("the two unrelated Canonical files are not both present")
    unexpected: list[str] = []
    for line in lines:
        relative = line[3:]
        if relative not in unrelated and relative not in H7C_TRACKED_PATHS:
            unexpected.append(line)
    if unexpected:
        raise HartleyH7CError(f"worktree scope mismatch: {unexpected}")
    identities = {
        relative: _identity_matches(repository / relative, expected)
        for relative, expected in ALLOWED_UNRELATED_UNTRACKED.items()
    }
    return {
        "branch": branch,
        "head": head,
        "status_lines": lines,
        "unrelated_canonical_files": identities,
        "unexpected_change_count": 0,
    }


def _findmnt(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["findmnt", "-J", "-T", str(path)], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    filesystems = payload.get("filesystems", [])
    if len(filesystems) != 1:
        raise HartleyH7CError(f"one filesystem expected for {path}")
    return {
        "command": ["findmnt", "-J", "-T", str(path)],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "returncode": completed.returncode,
        "filesystem": filesystems[0],
        "read_only_query": True,
    }


def verify_storage_identity(scratch_parent: Path, stage_root: Path) -> dict[str, Any]:
    local = _findmnt(scratch_parent)
    external = _findmnt(stage_root)
    if local["filesystem"].get("fstype") != "ext4":
        raise HartleyH7CError("H7C scratch parent must be Linux ext4")
    if external["filesystem"].get("fstype") != "9p":
        raise HartleyH7CError("external stage must resolve to drvfs/9p")
    mount_target = Path(str(external["filesystem"].get("target", "")))
    try:
        suffix = stage_root.resolve().relative_to(mount_target.resolve())
    except ValueError as error:
        raise HartleyH7CError("stage root is outside its resolved mount") from error
    if suffix != EXPECTED_STAGE_SUFFIX:
        raise HartleyH7CError(f"stage-root suffix mismatch: {suffix}")
    source = str(external["filesystem"].get("source", ""))
    if len(source) < 2 or source[0].upper() != "G" or source[1] != ":":
        raise HartleyH7CError("external stage is not on the authorized G drive")
    return {
        "scratch_parent": str(scratch_parent),
        "scratch_parent_findmnt": local,
        "stage_root": str(stage_root),
        "stage_root_findmnt": external,
        "stage_root_relative_to_mount": str(suffix),
        "stage_root_identity_validated": True,
        "repair_command_invoked": False,
    }


def _snapshot_parity_family(
    label: str,
    scratch_root: Path,
    stage_root: Path,
    parity_relative: Path,
    manifest_relative: Path,
    expected_parity_count: int,
) -> dict[str, Any]:
    parity_source = scratch_root / parity_relative
    parity_stage = stage_root / parity_relative
    parity = _load_json(parity_source)
    if parity.get("file_count") != expected_parity_count:
        raise HartleyH7CError(f"{label} parity file-count mismatch")
    if not parity.get("all_published_bytes_equal"):
        raise HartleyH7CError(f"{label} parity is not accepted")
    rows = parity.get("files")
    if not isinstance(rows, list) or len(rows) != expected_parity_count:
        raise HartleyH7CError(f"{label} parity rows mismatch")
    files: dict[str, Any] = {}
    for row in rows:
        relative = Path(str(row["relative_path"]))
        source_identity = file_identity(scratch_root / relative)
        stage_identity = file_identity(stage_root / relative)
        expected_source = row.get("source") or {
            "sha256": row.get("source_sha256"), "size": row.get("source_size")
        }
        expected_stage = row.get("published") or {
            "sha256": row.get("published_sha256"), "size": row.get("published_size")
        }
        if source_identity != {
            "sha256": str(expected_source["sha256"]), "size": int(expected_source["size"])
        }:
            raise HartleyH7CError(f"{label} source changed: {relative}")
        if stage_identity != {
            "sha256": str(expected_stage["sha256"]), "size": int(expected_stage["size"])
        }:
            raise HartleyH7CError(f"{label} stage changed: {relative}")
        if source_identity != stage_identity:
            raise HartleyH7CError(f"{label} source/stage mismatch: {relative}")
        files[str(relative)] = source_identity
    controls = {
        str(parity_relative): {
            "source": file_identity(parity_source),
            "stage": file_identity(parity_stage),
        },
        str(manifest_relative): {
            "source": file_identity(scratch_root / manifest_relative),
            "stage": file_identity(stage_root / manifest_relative),
        },
    }
    if any(value["source"] != value["stage"] for value in controls.values()):
        raise HartleyH7CError(f"{label} parity/manifest control mismatch")
    return {
        "label": label,
        "scratch_root": str(scratch_root),
        "stage_root": str(stage_root),
        "manifest_driven_file_count": len(files),
        "files": files,
        "controls": controls,
        "source_stage_hash_size_parity": True,
    }


def snapshot_predecessors(
    stage_root: Path,
    h6r_scratch: Path,
    original_h7_scratch: Path,
    h7r1_scratch: Path,
    h7r2_scratch: Path,
) -> dict[str, Any]:
    h6r_source = h6r_scratch / "03_ANALYSIS"
    h6r_parity = _load_json(stage_root / H6R_PARITY_RELATIVE)
    if h6r_parity.get("file_count") != 97 or not h6r_parity.get("all_published_bytes_equal"):
        raise HartleyH7CError("H6R accepted parity control mismatch")
    h6r_files: dict[str, Any] = {}
    for row in h6r_parity.get("files", []):
        relative = Path(str(row["relative_path"]))
        expected = {"sha256": row["source_sha256"], "size": row["source_size"]}
        source_identity = _identity_matches(h6r_source / relative, expected)
        stage_identity = _identity_matches(
            stage_root / relative,
            {"sha256": row["published_sha256"], "size": row["published_size"]},
        )
        if source_identity != stage_identity:
            raise HartleyH7CError(f"H6R source/stage mismatch: {relative}")
        h6r_files[str(relative)] = source_identity
    h6r = {
        "label": "H6R",
        "scratch_root": str(h6r_scratch),
        "source_root": str(h6r_source),
        "stage_root": str(stage_root),
        "manifest_driven_file_count": len(h6r_files),
        "files": h6r_files,
        "controls": {
            str(H6R_PARITY_RELATIVE): file_identity(stage_root / H6R_PARITY_RELATIVE),
            str(H6R_MANIFEST_RELATIVE): file_identity(stage_root / H6R_MANIFEST_RELATIVE),
        },
        "source_stage_hash_size_parity": True,
    }
    if len(h6r_files) != 97:
        raise HartleyH7CError("H6R manifest did not enumerate 97 files")
    families = {
        "h6r": h6r,
        "original_h7": _snapshot_parity_family(
            "ORIGINAL_H7", original_h7_scratch, stage_root,
            ORIGINAL_H7_PARITY_RELATIVE, ORIGINAL_H7_MANIFEST_RELATIVE, 10,
        ),
        "h7r1": _snapshot_parity_family(
            "H7R1", h7r1_scratch, stage_root,
            H7R1_PARITY_RELATIVE, H7R1_MANIFEST_RELATIVE, 12,
        ),
        "h7r2": _snapshot_parity_family(
            "H7R2", h7r2_scratch, stage_root,
            H7R2_PARITY_RELATIVE, H7R2_MANIFEST_RELATIVE, 12,
        ),
    }
    return {
        "schema_version": "hartley.h7c.predecessor_snapshot.v1",
        "families": families,
        "manifest_driven_file_count": 97 + 10 + 12 + 12,
        "all_predecessor_files_hash_size_verified": True,
        "all_available_source_stage_copies_equal": True,
    }


def record_v1_path_resolution_failure(v1_scratch: Path) -> dict[str, Any]:
    freeze_path = v1_scratch / CONTRACT_FREEZE_RELATIVE
    contract_path = v1_scratch / CONTRACT_COPY_RELATIVE
    _identity_matches(
        freeze_path,
        {"sha256": V1_CONTRACT_FREEZE_SHA256, "size": V1_CONTRACT_FREEZE_SIZE},
    )
    _identity_matches(
        contract_path,
        {"sha256": V1_CONTRACT_SHA256, "size": V1_CONTRACT_SIZE},
    )
    failure = {
        "schema_version": "hartley.h7c.v1_path_resolution_failure.v1",
        "classification": "ADMINISTRATIVE_PATH_LAYOUT_CORRECTION_NOT_SCIENTIFIC_SEARCH",
        "terminal_status": "NOT_A_SCIENTIFIC_TERMINAL",
        "initial_pre_access_freeze": {
            "identity": file_identity(freeze_path),
            "validly_froze_h1_through_h5": True,
            "trace_open_count": 0,
            "reference_output_open_count": 0,
            "reference_rows_read": 0,
        },
        "resolver_open_count": 2,
        "files_opened_and_hashed_before_failure": [
            {
                "sequence": index,
                "relative_path_as_v1_constructed": str(RAW_CAPTURE_STEM / filename),
                "name": filename,
                "opened_for_sha256": True,
                "rows_or_messages_decoded": 0,
                "trajectory_values_decoded": False,
                "hash_value_retained_by_aborted_command": False,
            }
            for index, filename in enumerate(RAW_FILENAMES[:8], start=1)
        ],
        "failure_path": str(RAW_CAPTURE_STEM / RAW_FILENAMES[8]),
        "failure_operation": "FILE_IDENTITY_EXISTENCE_STAT",
        "failure_path_opened": False,
        "failure_path_hashed": False,
        "bag_path_statted_opened_or_hashed": False,
        "cumulative_counters": {
            "trace_open_count": 1,
            "reference_output_open_count": 7,
            "reference_rows_read": 0,
            "raw_hash_open_count": 8,
            "raw_stat_attempt_count": 9,
            "fpl_bag_trajectory_values_decoded": 0,
        },
        "tracked_layout_provenance": {
            "relative_path": "src/legsa_gins/paper_rebuild/evidence.py",
            "commit": TASK_START_HEAD,
            "git_blob": "3f759059f9bf16f6dd57afcee26f47397706be42",
            "sha256": "c60b6d61cb2d1aae5431a3b973c8ea67f391df85964201c6ad03463b144dfa5a",
            "finding": "capture .bag/.fpl are siblings of the exported CSV directory",
        },
        "zero_additional_raw_opens_before_v2_correction_freeze": True,
        "zero_additional_raw_stats_before_v2_correction_freeze": True,
        "scientific_extrinsic_search_execution_count": 0,
        "h7r4_or_h7r5_created": False,
    }
    destination = v1_scratch / V1_FAILURE_RELATIVE
    write_json_exclusive(destination, failure)
    return {
        "v1_path_failure_recorded": True,
        "relative_path": str(V1_FAILURE_RELATIVE),
        "identity": file_identity(destination),
        "cumulative_counters": failure["cumulative_counters"],
        "scientific_extrinsic_search_execution_count": 0,
    }


def prepare_contract_freeze(
    repository: Path,
    scratch: Path,
    stage_root: Path,
    h6r_scratch: Path,
    original_h7_scratch: Path,
    h7r1_scratch: Path,
    h7r2_scratch: Path,
    initial_h7c_scratch: Path | None = None,
) -> dict[str, Any]:
    git = verify_git_identity(repository)
    contract, contract_path = load_and_validate_contract(repository)
    if scratch.exists():
        raise HartleyH7CError(f"H7C scratch already exists: {scratch}")
    if (stage_root / PUBLICATION_ROOT_RELATIVE).exists():
        raise HartleyH7CError("H7C stage publication root already exists")
    for relative in (
        Path("11_REPORT/LSE01_H7C_FINAL_REPORT.md"),
        Path("11_REPORT/LSE01_H7C_FINAL_STATUS.json"),
        Path("11_REPORT/LSE01_FINAL_CLAIM_BOUNDARY.md"),
    ):
        if (stage_root / relative).exists():
            raise HartleyH7CError(f"H7C report destination already exists: {relative}")
    storage = verify_storage_identity(scratch.parent, stage_root)
    if initial_h7c_scratch is None:
        raise HartleyH7CError("V2 freeze requires the immutable initial H7C scratch")
    initial_freeze = _identity_matches(
        initial_h7c_scratch / CONTRACT_FREEZE_RELATIVE,
        {"sha256": V1_CONTRACT_FREEZE_SHA256, "size": V1_CONTRACT_FREEZE_SIZE},
    )
    initial_failure = file_identity(initial_h7c_scratch / V1_FAILURE_RELATIVE)
    predecessor = snapshot_predecessors(
        stage_root, h6r_scratch, original_h7_scratch, h7r1_scratch, h7r2_scratch,
    )
    scratch.mkdir()
    _fsync_directory(scratch.parent)
    preflight = {
        **predecessor,
        "snapshot_phase": "PRE_H7C_CONTRACT_FREEZE_AND_PRE_PUBLICATION",
        "git_identity": git,
        "storage_identity": storage,
        "reference_access_counters": {
            "trace_open_count": 0,
            "reference_output_open_count": 0,
            "reference_rows_read": 0,
        },
        "raw_or_local_path_config_opened_statted_or_hashed": False,
    }
    write_json_exclusive(scratch / PREDECESSOR_PRE_RELATIVE, preflight)
    write_exclusive(scratch / CONTRACT_COPY_RELATIVE, contract_path.read_bytes())
    freeze = {
        "schema_version": "hartley.h7c.contract_freeze.v2",
        "contract_relative_path": str(CONTRACT_COPY_RELATIVE),
        "contract_identity": file_identity(scratch / CONTRACT_COPY_RELATIVE),
        "config_hash": contract["config_hash"]["value"],
        "config_hash_algorithm": contract["config_hash"]["algorithm"],
        "predecessor_pre_snapshot_relative_path": str(PREDECESSOR_PRE_RELATIVE),
        "predecessor_pre_snapshot_identity": file_identity(
            scratch / PREDECESSOR_PRE_RELATIVE
        ),
        "start_head": TASK_START_HEAD,
        "initial_pre_access_freeze": {
            "scratch": str(initial_h7c_scratch),
            "identity": initial_freeze,
            "validly_froze_h1_through_h5_before_access": True,
            "trace_open_count": 0,
            "reference_output_open_count": 0,
            "reference_rows_read": 0,
        },
        "v1_administrative_path_resolution_failure": {
            "relative_path": str(V1_FAILURE_RELATIVE),
            "identity": initial_failure,
            "scientific_or_extrinsic_search": False,
        },
        "v2_path_correction": {
            "tracked_layout_provenance_relative_path": (
                "src/legsa_gins/paper_rebuild/evidence.py"
            ),
            "tracked_layout_provenance_commit": TASK_START_HEAD,
            "tracked_layout_provenance_git_blob": (
                "3f759059f9bf16f6dd57afcee26f47397706be42"
            ),
            "tracked_layout_provenance_sha256": (
                "c60b6d61cb2d1aae5431a3b973c8ea67f391df85964201c6ad03463b144dfa5a"
            ),
            "exact_per_file_relative_paths_frozen": True,
            "zero_additional_raw_opens_between_v1_failure_and_v2_freeze": True,
            "zero_additional_raw_stats_between_v1_failure_and_v2_freeze": True,
        },
        "v2_contract_frozen_before_corrected_raw_inventory_access": True,
        "contract_frozen_before_raw_local_path_config_or_reference_access": False,
        "global_zero_counter_claim_for_v2": False,
        "trace_open_count": 1,
        "reference_output_open_count": 7,
        "reference_rows_read": 0,
        "raw_hash_open_count": 8,
        "raw_stat_attempt_count": 9,
        "local_resolver_open_count": 2,
        "raw_or_local_path_config_opened_statted_or_hashed": True,
        "scientific_extrinsic_search_execution_count": 0,
        "h5_filter_rerun_count": 0,
        "h6_h6r_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
    }
    write_json_exclusive(scratch / CONTRACT_FREEZE_RELATIVE, freeze)
    return {
        "contract_frozen": True,
        "freeze_version": "V2_PATH_CORRECTION",
        "scratch": str(scratch),
        "stage_root": str(stage_root),
        "contract_freeze_relative_path": str(CONTRACT_FREEZE_RELATIVE),
        "contract_freeze_identity": file_identity(scratch / CONTRACT_FREEZE_RELATIVE),
        "predecessor_manifest_driven_file_count": predecessor[
            "manifest_driven_file_count"
        ],
        "reference_access_counters": {
            "trace_open_count": 1,
            "reference_output_open_count": 7,
            "reference_rows_read": 0,
        },
        "scientific_extrinsic_search_execution_count": 0,
    }


def require_contract_freeze(scratch: Path) -> dict[str, Any]:
    freeze_path = scratch / CONTRACT_FREEZE_RELATIVE
    freeze = _load_json(freeze_path)
    if freeze.get("v2_contract_frozen_before_corrected_raw_inventory_access") is not True:
        raise HartleyH7CError("H7C V2 corrected contract freeze is not valid")
    initial = freeze.get("initial_pre_access_freeze", {})
    for key in ("trace_open_count", "reference_output_open_count", "reference_rows_read"):
        if initial.get(key) != 0:
            raise HartleyH7CError("initial pre-access counter was not zero")
    if freeze.get("global_zero_counter_claim_for_v2") is not False:
        raise HartleyH7CError("V2 must not make a false global-zero counter claim")
    if freeze.get("scientific_extrinsic_search_execution_count") != 0:
        raise HartleyH7CError("extrinsic search ran before corrected inventory")
    contract_path = scratch / CONTRACT_COPY_RELATIVE
    if file_identity(contract_path) != freeze.get("contract_identity"):
        raise HartleyH7CError("frozen H7C contract identity changed")
    return freeze


@dataclass
class ReferenceAccessGuard:
    scratch: Path
    prior_counter_relative: Path | None = None
    contract_freeze_verified: bool = False
    trace_open_count: int = 0
    reference_output_open_count: int = 0
    reference_rows_read: int = 0
    raw_hash_open_count: int = 0
    raw_stat_attempt_count: int = 0
    local_resolver_open_count: int = 0

    def verify_freeze(self) -> None:
        freeze = require_contract_freeze(self.scratch)
        self.trace_open_count = int(freeze["trace_open_count"])
        self.reference_output_open_count = int(freeze["reference_output_open_count"])
        self.reference_rows_read = int(freeze["reference_rows_read"])
        self.raw_hash_open_count = int(freeze["raw_hash_open_count"])
        self.raw_stat_attempt_count = int(freeze["raw_stat_attempt_count"])
        self.local_resolver_open_count = int(freeze["local_resolver_open_count"])
        if self.prior_counter_relative is not None:
            prior = _load_json(self.scratch / self.prior_counter_relative)
            for key in (
                "trace_open_count",
                "reference_output_open_count",
                "reference_rows_read",
                "raw_hash_open_count",
                "raw_stat_attempt_count",
                "local_resolver_open_count",
            ):
                value = int(prior[key])
                if value < int(getattr(self, key)):
                    raise HartleyH7CError(f"cumulative counter regressed: {key}")
                setattr(self, key, value)
        self.contract_freeze_verified = True

    def require_ready(self) -> None:
        if not self.contract_freeze_verified:
            raise HartleyH7CError(
                "raw open/stat/hash forbidden before H7C contract freeze verification"
            )

    def identity(self, path: Path, *, trace: bool = False) -> dict[str, Any]:
        self.require_ready()
        self.raw_stat_attempt_count += 1
        identity = file_identity(path)
        self.raw_hash_open_count += 1
        if trace:
            self.trace_open_count += 1
        else:
            self.reference_output_open_count += 1
        return identity

    def open_text(self, path: Path, *, trace: bool = False):
        self.require_ready()
        if trace:
            self.trace_open_count += 1
        else:
            self.reference_output_open_count += 1
        return path.open("r", encoding="utf-8", newline="")

    def add_rows(self, count: int) -> None:
        self.require_ready()
        self.reference_rows_read += int(count)

    def counters(self) -> dict[str, int]:
        return {
            "trace_open_count": self.trace_open_count,
            "reference_output_open_count": self.reference_output_open_count,
            "reference_rows_read": self.reference_rows_read,
            "raw_hash_open_count": self.raw_hash_open_count,
            "raw_stat_attempt_count": self.raw_stat_attempt_count,
            "local_resolver_open_count": self.local_resolver_open_count,
        }


def resolve_raw_sources(
    repository: Path,
    scratch: Path,
) -> dict[str, Any]:
    guard = ReferenceAccessGuard(scratch)
    guard.verify_freeze()
    contract, _contract_path = load_and_validate_contract(repository)
    resolver_relative = Path(contract["raw_access_allowlist"]["resolver"])
    if resolver_relative != Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"):
        raise HartleyH7CError("unexpected raw path resolver")
    resolver_path = repository / resolver_relative
    resolver_payload = yaml.safe_load(resolver_path.read_text())
    guard.local_resolver_open_count += 1
    if not isinstance(resolver_payload, dict) or not isinstance(
        resolver_payload.get("paths"), dict
    ):
        raise HartleyH7CError("local resolver schema mismatch")
    paths = resolver_payload["paths"]
    raw_root = Path(str(paths.get("raw_root", "")))
    configured_fix_root = Path(str(paths.get("by2_fix_root", "")))
    if not raw_root.is_absolute():
        raise HartleyH7CError("RAW_ROOT must be absolute in ignored local config")
    expected_fix_root = raw_root / RAW_CAPTURE_STEM
    if configured_fix_root != expected_fix_root:
        raise HartleyH7CError("configured BY2 Fixposition root does not match RAW_ROOT alias")
    roles = {
        row["name"]: row["role"]
        for row in contract["raw_access_allowlist"]["files"]
    }
    entries: list[dict[str, Any]] = []
    identities: dict[str, Any] = {}
    for sequence, filename in enumerate(RAW_FILENAMES, start=1):
        relative = RAW_RELATIVE_PATHS[filename]
        path = raw_root / relative
        identity = guard.identity(path, trace=(sequence == 1))
        identities[filename] = identity
        binary_metadata_only = path.suffix in {".fpl", ".bag"}
        v1_hash_open_count = 1 if sequence <= 8 else 0
        entries.append({
            "sequence": sequence,
            "raw_root_alias": "RAW_ROOT",
            "relative_path": str(relative),
            "role": roles[filename],
            "authorized": True,
            "identity": identity,
            "v1_hash_open_count": v1_hash_open_count,
            "v2_hash_open_count": 1,
            "cumulative_hash_open_count": v1_hash_open_count + 1,
            "semantic_content_open_count": 0,
            "rows_or_messages_inspected": 0,
            "trajectory_values_decoded": False,
            "metadata_only_if_fpl_or_bag": binary_metadata_only,
        })
    inventory = {
        "schema_version": "hartley.h7c.raw_access_inventory.v1",
        "contract_freeze_verified_before_any_raw_stat_hash_or_open": True,
        "initial_global_zero_freeze_preceded_v1_access": True,
        "v2_correction_freeze_preceded_corrected_inventory_access": True,
        "global_zero_counter_claim_for_v2": False,
        "resolver_relative_path": str(resolver_relative),
        "resolver_open_count_this_command": 1,
        "resolver_open_count_prior_to_command": 2,
        "resolver_open_count_total": guard.local_resolver_open_count,
        "raw_root_alias": "RAW_ROOT",
        "raw_capture_stem_relative_path": str(RAW_CAPTURE_STEM),
        "configured_fix_root_matches_alias_plus_relative_root": True,
        "exact_authorized_file_count": len(entries),
        "files": entries,
        "unlisted_directory_entries_inspected": False,
        "fpl_bag_trajectory_values_decoded": False,
        "reference_access_counters_after_identity_hashing": guard.counters(),
    }
    write_json_exclusive(scratch / RAW_INVENTORY_RELATIVE, inventory)
    access_ledger = {
        "schema_version": "hartley.h7c.source_access_ledger.v1",
        "contract_freeze_identity": file_identity(scratch / CONTRACT_FREEZE_RELATIVE),
        "resolver": {
            "relative_path": str(resolver_relative),
            "open_count": guard.local_resolver_open_count,
            "role": "IGNORED_LOCAL_ALIAS_RESOLUTION_ONLY",
        },
        "v1_administrative_path_failure": {
            "record_relative_path": str(V1_FAILURE_RELATIVE),
            "trace_open_count": 1,
            "reference_output_open_count": 7,
            "reference_rows_read": 0,
            "raw_hash_open_count": 8,
            "raw_stat_attempt_count": 9,
        },
        "raw_files": entries,
        "denied_path_access_count": 0,
        "broad_directory_scan_count": 0,
        **guard.counters(),
        "fpl_bag_trajectory_values_decoded": False,
    }
    write_json_exclusive(scratch / ACCESS_LEDGER_RELATIVE, access_ledger)
    return {
        "raw_root": str(raw_root),
        "fixposition_root": str(expected_fix_root),
        "exact_authorized_file_count": len(entries),
        "file_identities": identities,
        "inventory_identity": file_identity(scratch / RAW_INVENTORY_RELATIVE),
        "access_ledger_identity": file_identity(scratch / ACCESS_LEDGER_RELATIVE),
        "reference_access_counters": guard.counters(),
    }


def _resolve_raw_root_with_guard(
    repository: Path, guard: ReferenceAccessGuard
) -> tuple[Path, Path]:
    contract, _contract_path = load_and_validate_contract(repository)
    resolver_relative = Path(contract["raw_access_allowlist"]["resolver"])
    payload = yaml.safe_load((repository / resolver_relative).read_text())
    guard.local_resolver_open_count += 1
    if not isinstance(payload, dict) or not isinstance(payload.get("paths"), dict):
        raise HartleyH7CError("local path resolver schema mismatch")
    raw_root = Path(str(payload["paths"].get("raw_root", "")))
    expected_fix_root = raw_root / RAW_CAPTURE_STEM
    if Path(str(payload["paths"].get("by2_fix_root", ""))) != expected_fix_root:
        raise HartleyH7CError("local BY2 Fixposition alias mismatch")
    return raw_root, resolver_relative


def inspect_csv_schema_headers(repository: Path, scratch: Path) -> dict[str, Any]:
    guard = ReferenceAccessGuard(scratch, ACCESS_LEDGER_RELATIVE)
    guard.verify_freeze()
    raw_root, resolver_relative = _resolve_raw_root_with_guard(repository, guard)
    schemas: dict[str, Any] = {}
    for sequence, filename in enumerate(RAW_FILENAMES[:8], start=1):
        path = raw_root / RAW_RELATIVE_PATHS[filename]
        with guard.open_text(path, trace=(sequence == 1)) as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as error:
                raise HartleyH7CError(f"CSV has no header: {filename}") from error
        schemas[filename] = {
            "relative_path": str(RAW_RELATIVE_PATHS[filename]),
            "column_count": len(header),
            "columns": header,
            "header_rows_read": 1,
            "data_rows_read": 0,
        }
    payload = {
        "schema_version": "hartley.h7c.csv_schema_headers.v1",
        "contract_freeze_verified": True,
        "resolver_relative_path": str(resolver_relative),
        "schema_only_no_data_rows": True,
        "csv_file_count": len(schemas),
        "files": schemas,
        "fpl_bag_open_count": 0,
        "fpl_bag_trajectory_values_decoded": False,
        **guard.counters(),
    }
    write_json_exclusive(scratch / SCHEMA_HEADERS_RELATIVE, payload)
    return {
        "schema_headers_identity": file_identity(scratch / SCHEMA_HEADERS_RELATIVE),
        "files": schemas,
        "counters": guard.counters(),
    }


def freeze_trace_field_mapping(scratch: Path) -> dict[str, Any]:
    require_contract_freeze(scratch)
    schema = _load_json(scratch / SCHEMA_HEADERS_RELATIVE)
    required_trace = {
        "time", "lat", "lon", "height", "processed_lat", "processed_lon",
        "processed_height", "yaw", "pitch", "roll",
    }
    required_geodetic = {
        "Time", "header.stamp.secs", "header.stamp.nsecs", "header.frame_id",
        "p.frame_id", "p.vector3.x", "p.vector3.y", "p.vector3.z",
        "ypr.frame_id", "ypr.vector3.x", "ypr.vector3.y", "ypr.vector3.z",
    }
    trace_columns = set(
        schema["files"][RAW_FILENAMES[0]]["columns"]
    )
    geodetic_columns = set(
        schema["files"][RAW_FILENAMES[1]]["columns"]
    )
    if trace_columns != required_trace:
        raise HartleyH7CError("trace schema changed before field-map freeze")
    if not required_geodetic.issubset(geodetic_columns):
        raise HartleyH7CError("POI geodetic schema lacks frozen mapping fields")
    mapping = {
        "schema_version": "hartley.h7c.trace_field_map.v1",
        "mapping_fixed_before_numeric_comparison": True,
        "mapping_proof_classification": "DETERMINISTIC_FIELD_MAPPING",
        "row_identity_policy": "SAME_ROW_INDEX_AFTER_EQUAL_ROW_COUNT_AND_CHRONOLOGY_CHECK",
        "fields": [
            {"semantic": "export_timestamp", "trace": "time", "poi_geodetic": "Time"},
            {"semantic": "latitude_deg", "trace": "lat", "poi_geodetic": "p.vector3.x"},
            {"semantic": "longitude_deg", "trace": "lon", "poi_geodetic": "p.vector3.y"},
            {"semantic": "ellipsoidal_height_m", "trace": "height", "poi_geodetic": "p.vector3.z"},
            {"semantic": "yaw_rad", "trace": "yaw", "poi_geodetic": "ypr.vector3.x"},
            {"semantic": "pitch_rad", "trace": "pitch", "poi_geodetic": "ypr.vector3.y"},
            {"semantic": "roll_rad", "trace": "roll", "poi_geodetic": "ypr.vector3.z"},
        ],
        "status_mapping": {
            "trace_status_field": None,
            "classification": "UNPROVEN",
            "reason": "TRACE_SCHEMA_HAS_NO_STATUS_OR_VALIDITY_COLUMN",
            "poi_frame_fields_audited_separately": [
                "header.frame_id", "p.frame_id", "ypr.frame_id",
            ],
            "user_io_status_not_row_joined": True,
        },
        "auxiliary_trace_columns": {
            "columns": ["processed_lat", "processed_lon", "processed_height"],
            "source_mapping": "UNPROVEN_NOT_USED_TO_CHOOSE_OR_REPLACE_PRIMARY_MAPPING",
            "numeric_values_may_be_reported_nonselectively": True,
        },
        "numeric_comparison_may_support_lineage_but_not_choose_frame_convention": True,
        "trace_open_count_at_mapping_freeze": schema["trace_open_count"],
        "reference_output_open_count_at_mapping_freeze": schema[
            "reference_output_open_count"
        ],
        "reference_rows_read_at_mapping_freeze": schema["reference_rows_read"],
    }
    write_json_exclusive(scratch / FIELD_MAP_RELATIVE, mapping)
    freeze = {
        "schema_version": "hartley.h7c.trace_field_map_freeze.v1",
        "mapping_relative_path": str(FIELD_MAP_RELATIVE),
        "mapping_identity": file_identity(scratch / FIELD_MAP_RELATIVE),
        "schema_headers_identity": file_identity(scratch / SCHEMA_HEADERS_RELATIVE),
        "numeric_data_rows_read_before_mapping_freeze": 0,
        "mapping_fixed_before_numeric_comparison": True,
        "trace_open_count": schema["trace_open_count"],
        "reference_output_open_count": schema["reference_output_open_count"],
        "reference_rows_read": schema["reference_rows_read"],
        "scientific_extrinsic_search_execution_count": 0,
    }
    write_json_exclusive(scratch / FIELD_MAP_FREEZE_RELATIVE, freeze)
    return {
        "field_map_identity": file_identity(scratch / FIELD_MAP_RELATIVE),
        "field_map_freeze_identity": file_identity(scratch / FIELD_MAP_FREEZE_RELATIVE),
        "mapping_fixed_before_numeric_comparison": True,
        "reference_rows_read": 0,
    }


def _read_dict_rows(
    guard: ReferenceAccessGuard, path: Path, *, trace: bool = False
) -> tuple[list[str], list[dict[str, str]]]:
    with guard.open_text(path, trace=trace) as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    guard.add_rows(len(rows))
    return fieldnames, rows


def _mapped_identity(
    trace_rows: Sequence[Mapping[str, str]],
    poi_rows: Sequence[Mapping[str, str]],
    trace_field: str,
    poi_field: str,
    *,
    unwrap_bracketed_scalar: bool = False,
) -> dict[str, Any]:
    lexical_mismatches = 0
    numeric_mismatches = 0
    finite_pair_count = 0
    maximum_absolute_difference = 0.0
    first_mismatch: dict[str, Any] | None = None
    for index, (trace_row, poi_row) in enumerate(zip(trace_rows, poi_rows)):
        left_text = str(trace_row[trace_field]).strip()
        right_text = str(poi_row[poi_field]).strip()
        if left_text != right_text:
            lexical_mismatches += 1
        try:
            numeric_left_text = left_text
            if unwrap_bracketed_scalar:
                while (
                    len(numeric_left_text) >= 2
                    and numeric_left_text[0] == "["
                    and numeric_left_text[-1] == "]"
                ):
                    numeric_left_text = numeric_left_text[1:-1].strip()
            left = float(numeric_left_text)
            right = float(right_text)
        except ValueError as error:
            raise HartleyH7CError(
                f"non-numeric mapped value at row {index}: {trace_field}/{poi_field}"
            ) from error
        if math.isfinite(left) and math.isfinite(right):
            finite_pair_count += 1
            difference = abs(left - right)
            maximum_absolute_difference = max(maximum_absolute_difference, difference)
            equal = left == right
        else:
            equal = math.isnan(left) and math.isnan(right)
            difference = None
        if not equal:
            numeric_mismatches += 1
            if first_mismatch is None:
                first_mismatch = {
                    "zero_based_data_row": index,
                    "trace_value": left_text,
                    "poi_value": right_text,
                    "absolute_difference": difference,
                }
    return {
        "trace_field": trace_field,
        "poi_geodetic_field": poi_field,
        "compared_row_count": min(len(trace_rows), len(poi_rows)),
        "finite_pair_count": finite_pair_count,
        "lexical_mismatch_count": lexical_mismatches,
        "parsed_float_exact_mismatch_count": numeric_mismatches,
        "maximum_absolute_difference": maximum_absolute_difference,
        "first_numeric_mismatch": first_mismatch,
        "parsed_float_exact_identity": numeric_mismatches == 0,
        "bracketed_scalar_unwrap_applied": unwrap_bracketed_scalar,
    }


def record_lineage_auxiliary_parse_failure(scratch: Path) -> dict[str, Any]:
    require_contract_freeze(scratch)
    if (scratch / TRACE_IDENTITY_RELATIVE).exists():
        raise HartleyH7CError("lineage result already exists; cannot record prior failure")
    payload = {
        "schema_version": "hartley.h7c.lineage_auxiliary_parse_failure.v1",
        "classification": "ADMINISTRATIVE_AUXILIARY_SERIALIZATION_PARSE_FAILURE",
        "scientific_contradiction": False,
        "fixed_primary_field_mapping_changed": False,
        "failure_field": "processed_lat",
        "first_observed_serialization": "[[116.34312609]]",
        "failure_reason": "AUXILIARY_TRACE_SCALAR_WRAPPED_IN_NESTED_BRACKETS",
        "required_primary_comparison_result_published": False,
        "raw_files_opened": [RAW_FILENAMES[0], RAW_FILENAMES[1]],
        "data_rows_read_this_failed_attempt": 12080,
        "trace_open_count": 4,
        "reference_output_open_count": 24,
        "reference_rows_read": 12080,
        "raw_hash_open_count": 18,
        "raw_stat_attempt_count": 19,
        "local_resolver_open_count": 5,
        "fpl_bag_trajectory_values_decoded": False,
        "scientific_extrinsic_search_execution_count": 0,
    }
    write_json_exclusive(scratch / LINEAGE_AUX_FAILURE_RELATIVE, payload)
    return {
        "recorded": True,
        "identity": file_identity(scratch / LINEAGE_AUX_FAILURE_RELATIVE),
        "counters": {
            key: payload[key]
            for key in (
                "trace_open_count", "reference_output_open_count",
                "reference_rows_read", "raw_hash_open_count",
                "raw_stat_attempt_count", "local_resolver_open_count",
            )
        },
    }


def audit_trace_lineage(repository: Path, scratch: Path) -> dict[str, Any]:
    require_contract_freeze(scratch)
    field_map_freeze = _load_json(scratch / FIELD_MAP_FREEZE_RELATIVE)
    if field_map_freeze.get("numeric_data_rows_read_before_mapping_freeze") != 0:
        raise HartleyH7CError("field mapping was not frozen before numeric rows")
    if file_identity(scratch / FIELD_MAP_RELATIVE) != field_map_freeze.get(
        "mapping_identity"
    ):
        raise HartleyH7CError("trace field map changed after freeze")
    prior_counter = (
        LINEAGE_AUX_FAILURE_RELATIVE
        if (scratch / LINEAGE_AUX_FAILURE_RELATIVE).is_file()
        else SCHEMA_HEADERS_RELATIVE
    )
    guard = ReferenceAccessGuard(scratch, prior_counter)
    guard.verify_freeze()
    raw_root, resolver_relative = _resolve_raw_root_with_guard(repository, guard)
    trace_path = raw_root / RAW_RELATIVE_PATHS[RAW_FILENAMES[0]]
    geodetic_path = raw_root / RAW_RELATIVE_PATHS[RAW_FILENAMES[1]]
    trace_fields, trace_rows = _read_dict_rows(guard, trace_path, trace=True)
    poi_fields, poi_rows = _read_dict_rows(guard, geodetic_path)
    mapping = _load_json(scratch / FIELD_MAP_RELATIVE)
    comparisons = {
        row["semantic"]: _mapped_identity(
            trace_rows, poi_rows, row["trace"], row["poi_geodetic"]
        )
        for row in mapping["fields"]
    }
    processed = {
        semantic: _mapped_identity(
            trace_rows, poi_rows, trace_field, poi_field,
            unwrap_bracketed_scalar=True,
        )
        for semantic, trace_field, poi_field in (
            ("processed_latitude_nonselective", "processed_lat", "p.vector3.x"),
            ("processed_longitude_nonselective", "processed_lon", "p.vector3.y"),
            ("processed_height_nonselective", "processed_height", "p.vector3.z"),
        )
    }
    trace_time = [float(row["time"]) for row in trace_rows]
    poi_time = [float(row["Time"]) for row in poi_rows]
    chronology = {
        "trace_strictly_increasing": all(
            right > left for left, right in zip(trace_time, trace_time[1:])
        ),
        "poi_geodetic_strictly_increasing": all(
            right > left for left, right in zip(poi_time, poi_time[1:])
        ),
        "trace_first_time": trace_time[0] if trace_time else None,
        "trace_last_time": trace_time[-1] if trace_time else None,
        "poi_first_time": poi_time[0] if poi_time else None,
        "poi_last_time": poi_time[-1] if poi_time else None,
    }
    frame_values = {
        field: sorted({str(row[field]) for row in poi_rows})
        for field in ("header.frame_id", "p.frame_id", "ypr.frame_id")
    }
    expected_rows = 6040
    row_counts_match = len(trace_rows) == len(poi_rows) == expected_rows
    required_exact = all(
        result["parsed_float_exact_identity"] for result in comparisons.values()
    )
    chronology_pass = all(
        chronology[key]
        for key in ("trace_strictly_increasing", "poi_geodetic_strictly_increasing")
    )
    lineage_pass = row_counts_match and required_exact and chronology_pass
    hypothesis_state = "NUMERICAL_IDENTITY_CROSSCHECK" if lineage_pass else "CONTRADICTED"
    payload = {
        "schema_version": "hartley.h7c.trace_poi_geodetic_identity.v1",
        "hypothesis": "H1",
        "hypothesis_state": hypothesis_state,
        "terminal_if_contradicted": BLOCKED_LINEAGE,
        "field_mapping_fixed_before_numeric_comparison": True,
        "field_map_identity": file_identity(scratch / FIELD_MAP_RELATIVE),
        "field_map_freeze_identity": file_identity(scratch / FIELD_MAP_FREEZE_RELATIVE),
        "resolver_relative_path": str(resolver_relative),
        "trace_relative_path": str(RAW_RELATIVE_PATHS[RAW_FILENAMES[0]]),
        "poi_geodetic_relative_path": str(RAW_RELATIVE_PATHS[RAW_FILENAMES[1]]),
        "trace_schema": trace_fields,
        "poi_geodetic_schema": poi_fields,
        "expected_data_row_count": expected_rows,
        "trace_data_row_count": len(trace_rows),
        "poi_geodetic_data_row_count": len(poi_rows),
        "equal_expected_row_counts": row_counts_match,
        "chronology": chronology,
        "required_mapped_fields": comparisons,
        "required_yaw_identity": comparisons["yaw_rad"],
        "auxiliary_processed_fields_nonselective": processed,
        "status_or_validity": {
            "trace_status_column_present": False,
            "poi_geodetic_status_column_present": False,
            "rowwise_status_comparison": "NOT_APPLICABLE",
            "frame_fields": frame_values,
            "user_io_status_is_separate_system_status_not_joined_to_trace": True,
            "classification": "DETERMINISTIC_FIELD_MAPPING",
        },
        "numerical_identity_used_to_choose_frame_convention": False,
        "lineage_identity_pass": lineage_pass,
        **guard.counters(),
    }
    write_json_exclusive(scratch / TRACE_IDENTITY_RELATIVE, payload)
    proof = f"""# H7C trace to FP_POI geodetic lineage proof

H1 classification: `{hypothesis_state}`.

The trace-to-POI field map was frozen before any numeric data row was read.
The two files contain `{len(trace_rows)}` and `{len(poi_rows)}` data rows; the
expected count is `{expected_rows}`. Required timestamp, latitude, longitude,
height, yaw, pitch, and roll mappings have parsed-float exact identity:
`{required_exact}`. In particular, `trace.yaw ==
poi_geodetic.ypr.vector3.x` for all rows: `{comparisons['yaw_rad']['parsed_float_exact_identity']}`.

Neither CSV schema contains a status/validity column. The POI header, position,
and YPR frame-id fields are audited explicitly in the identity JSON. The
separate `user_io-status.csv` is system-output status and was not fabricated as
a rowwise trace-validity field.

This numerical identity cross-check supports derived/export lineage only after
the deterministic field mapping was fixed. It did not select a frame
convention, transform, sign, or offset.
"""
    write_exclusive(scratch / TRACE_PROOF_RELATIVE, proof.encode())
    return {
        "hypothesis": "H1",
        "hypothesis_state": hypothesis_state,
        "lineage_identity_pass": lineage_pass,
        "identity_artifact": file_identity(scratch / TRACE_IDENTITY_RELATIVE),
        "proof_artifact": file_identity(scratch / TRACE_PROOF_RELATIVE),
        "counters": guard.counters(),
    }


def decimal_token_interval(token: str) -> tuple[decimal.Decimal, decimal.Decimal, int]:
    stripped = token.strip()
    try:
        value = decimal.Decimal(stripped)
    except decimal.InvalidOperation as error:
        raise HartleyH7CError(f"invalid decimal token: {token!r}") from error
    if not value.is_finite():
        raise HartleyH7CError(f"non-finite decimal token: {token!r}")
    exponent = int(value.as_tuple().exponent)
    with decimal.localcontext() as context:
        context.prec = max(100, len(value.as_tuple().digits) + abs(exponent) + 20)
        quantum = decimal.Decimal(1).scaleb(exponent)
        half_quantum = quantum / decimal.Decimal(2)
        return value - half_quantum, value + half_quantum, int(value.as_tuple().sign)


def decimal_tokens_serialization_compatible(left: str, right: str) -> bool:
    left_low, left_high, left_sign = decimal_token_interval(left)
    right_low, right_high, right_sign = decimal_token_interval(right)
    if left_sign != right_sign:
        return False
    return max(left_low, right_low) <= min(left_high, right_high)


def freeze_decimal_serialization_contract(scratch: Path) -> dict[str, Any]:
    require_contract_freeze(scratch)
    exact_identity = _load_json(scratch / TRACE_IDENTITY_RELATIVE)
    if exact_identity.get("lineage_identity_pass") is not False:
        raise HartleyH7CError("expected preserved exact-binary diagnostic failure is absent")
    exact_identity_file = file_identity(scratch / TRACE_IDENTITY_RELATIVE)
    exact_proof_file = file_identity(scratch / TRACE_PROOF_RELATIVE)
    algorithm_source = (
        inspect.getsource(decimal_token_interval)
        + "\n"
        + inspect.getsource(decimal_tokens_serialization_compatible)
    )
    algorithm_sha256 = hashlib.sha256(algorithm_source.encode()).hexdigest()
    correction = {
        "schema_version": "hartley.h7c.trace_field_map_unit_correction.v1",
        "predecessor_field_map_identity": file_identity(scratch / FIELD_MAP_RELATIVE),
        "predecessor_field_map_preserved_byte_identical": True,
        "correction_classification": "ADDITIVE_SEMANTIC_LABEL_CORRECTION",
        "incorrect_predecessor_labels": ["yaw_rad", "pitch_rad", "roll_rad"],
        "corrected_lineage_labels": [
            "yaw_source_scalar", "pitch_source_scalar", "roll_source_scalar",
        ],
        "unit_conversion_applied_to_lineage_values": False,
        "unit_used_to_select_or_change_field_mapping": False,
        "unit_state_for_h1": "NOT_REQUIRED_FOR_UNCHANGED_SAME_SOURCE_SCALAR_COMPARISON",
        "h3_unit_and_orientation_semantics_require_separate_source_explicit_audit": True,
    }
    write_json_exclusive(scratch / FIELD_MAP_UNIT_CORRECTION_RELATIVE, correction)
    interpretation = {
        "schema_version": "hartley.h7c.exact_binary_diagnostic_interpretation.v1",
        "preserved_identity_artifact": {
            "relative_path": str(TRACE_IDENTITY_RELATIVE),
            "identity": exact_identity_file,
        },
        "preserved_proof_artifact": {
            "relative_path": str(TRACE_PROOF_RELATIVE),
            "identity": exact_proof_file,
        },
        "EXACT_PARSED_BINARY64_IDENTITY": False,
        "classification": "CONTRADICTED",
        "classification_scope": "EXACT_PARSED_BINARY64_IDENTITY_DIAGNOSTIC_ONLY",
        "h1_lineage_classification": "NOT_DECIDED_BY_THIS_DIAGNOSTIC",
        "artifact_overwritten_or_relabelled_in_place": False,
        "observed_maxima_used_to_define_next_acceptance_rule": False,
    }
    write_json_exclusive(scratch / EXACT_BINARY_INTERPRETATION_RELATIVE, interpretation)
    contract = {
        "schema_version": "hartley.h7c.decimal_serialization_equivalence_contract.v1",
        "criterion_frozen_before_second_interpretive_row_pass": True,
        "purpose": "SOURCE_EXPORT_DECIMAL_SERIALIZATION_EQUIVALENCE_NOT_TOLERANCE",
        "algorithm": {
            "arithmetic": "PYTHON_DECIMAL_EXACT_BASE10",
            "token_cell": (
                "For token d with printed Decimal exponent e, use the closed exact "
                "rounding cell [d-0.5*10^e,d+0.5*10^e]."
            ),
            "pair_rule": "SIGNS_EQUAL_AND_EXACT_DECIMAL_ROUNDING_CELLS_INTERSECT",
            "sign_rule": "DECIMAL_SIGN_BITS_MUST_MATCH_INCLUDING_SIGNED_ZERO",
            "empirical_absolute_tolerance": None,
            "empirical_relative_tolerance": None,
            "observed_maximum_used": False,
            "binary_float_used_for_compatibility": False,
            "algorithm_source_sha256": algorithm_sha256,
        },
        "required_row_count_each": 6040,
        "required_row_order": "SAME_INDEX_AND_STRICTLY_INCREASING_SOURCE_TIMESTAMPS",
        "required_field_pairs": [
            ["time", "Time"],
            ["lat", "p.vector3.x"],
            ["lon", "p.vector3.y"],
            ["height", "p.vector3.z"],
            ["yaw", "ypr.vector3.x"],
            ["pitch", "ypr.vector3.y"],
            ["roll", "ypr.vector3.z"],
        ],
        "unit_conversion_before_comparison": False,
        "processed_trace_fields_used": False,
        "frame_convention_selected_by_numerical_identity": False,
        "pass_classifications": [
            "DETERMINISTIC_FIELD_MAPPING", "NUMERICAL_IDENTITY_CROSSCHECK",
        ],
        "failure_classification": "CONTRADICTED",
        "failure_terminal": BLOCKED_LINEAGE,
    }
    write_json_exclusive(scratch / SERIALIZATION_CONTRACT_RELATIVE, contract)
    freeze = {
        "schema_version": "hartley.h7c.decimal_serialization_equivalence_freeze.v1",
        "contract_relative_path": str(SERIALIZATION_CONTRACT_RELATIVE),
        "contract_identity": file_identity(scratch / SERIALIZATION_CONTRACT_RELATIVE),
        "unit_correction_identity": file_identity(
            scratch / FIELD_MAP_UNIT_CORRECTION_RELATIVE
        ),
        "exact_binary_interpretation_identity": file_identity(
            scratch / EXACT_BINARY_INTERPRETATION_RELATIVE
        ),
        "exact_binary_identity_artifact_preserved": exact_identity_file,
        "exact_binary_proof_artifact_preserved": exact_proof_file,
        "criterion_frozen_before_second_interpretive_row_pass": True,
        "trace_open_count": exact_identity["trace_open_count"],
        "reference_output_open_count": exact_identity["reference_output_open_count"],
        "reference_rows_read": exact_identity["reference_rows_read"],
        "local_resolver_open_count": exact_identity["local_resolver_open_count"],
        "raw_hash_open_count": exact_identity["raw_hash_open_count"],
        "raw_stat_attempt_count": exact_identity["raw_stat_attempt_count"],
        "scientific_extrinsic_search_execution_count": 0,
    }
    write_json_exclusive(scratch / SERIALIZATION_CONTRACT_FREEZE_RELATIVE, freeze)
    return {
        "serialization_contract_identity": file_identity(
            scratch / SERIALIZATION_CONTRACT_RELATIVE
        ),
        "serialization_freeze_identity": file_identity(
            scratch / SERIALIZATION_CONTRACT_FREEZE_RELATIVE
        ),
        "algorithm_source_sha256": algorithm_sha256,
        "observed_maximum_used": False,
        "reference_rows_read_at_freeze": exact_identity["reference_rows_read"],
    }


def _decimal_field_compatibility(
    trace_rows: Sequence[Mapping[str, str]],
    poi_rows: Sequence[Mapping[str, str]],
    trace_field: str,
    poi_field: str,
) -> dict[str, Any]:
    failures = 0
    first_failure: dict[str, Any] | None = None
    exact_token_matches = 0
    for index, (trace_row, poi_row) in enumerate(zip(trace_rows, poi_rows)):
        left = str(trace_row[trace_field]).strip()
        right = str(poi_row[poi_field]).strip()
        if left == right:
            exact_token_matches += 1
        if not decimal_tokens_serialization_compatible(left, right):
            failures += 1
            if first_failure is None:
                left_low, left_high, left_sign = decimal_token_interval(left)
                right_low, right_high, right_sign = decimal_token_interval(right)
                first_failure = {
                    "zero_based_data_row": index,
                    "trace_token": left,
                    "poi_token": right,
                    "trace_interval": [str(left_low), str(left_high)],
                    "poi_interval": [str(right_low), str(right_high)],
                    "trace_sign": left_sign,
                    "poi_sign": right_sign,
                }
    return {
        "trace_field": trace_field,
        "poi_geodetic_field": poi_field,
        "compared_row_count": min(len(trace_rows), len(poi_rows)),
        "exact_token_match_count": exact_token_matches,
        "decimal_serialization_incompatibility_count": failures,
        "first_incompatibility": first_failure,
        "decimal_serialization_equivalence_pass": failures == 0,
    }


def audit_trace_decimal_serialization_lineage(
    repository: Path, scratch: Path
) -> dict[str, Any]:
    freeze = _load_json(scratch / SERIALIZATION_CONTRACT_FREEZE_RELATIVE)
    if freeze.get("criterion_frozen_before_second_interpretive_row_pass") is not True:
        raise HartleyH7CError("decimal serialization criterion was not frozen")
    if file_identity(scratch / SERIALIZATION_CONTRACT_RELATIVE) != freeze.get(
        "contract_identity"
    ):
        raise HartleyH7CError("decimal serialization contract changed after freeze")
    guard = ReferenceAccessGuard(scratch, TRACE_IDENTITY_RELATIVE)
    guard.verify_freeze()
    raw_root, resolver_relative = _resolve_raw_root_with_guard(repository, guard)
    _trace_fields, trace_rows = _read_dict_rows(
        guard, raw_root / RAW_RELATIVE_PATHS[RAW_FILENAMES[0]], trace=True
    )
    _poi_fields, poi_rows = _read_dict_rows(
        guard, raw_root / RAW_RELATIVE_PATHS[RAW_FILENAMES[1]]
    )
    contract = _load_json(scratch / SERIALIZATION_CONTRACT_RELATIVE)
    fields = {
        f"{left}__to__{right}": _decimal_field_compatibility(
            trace_rows, poi_rows, left, right
        )
        for left, right in contract["required_field_pairs"]
    }
    trace_times = [decimal.Decimal(row["time"].strip()) for row in trace_rows]
    poi_times = [decimal.Decimal(row["Time"].strip()) for row in poi_rows]
    chronology = {
        "trace_strictly_increasing": all(
            right > left for left, right in zip(trace_times, trace_times[1:])
        ),
        "poi_strictly_increasing": all(
            right > left for left, right in zip(poi_times, poi_times[1:])
        ),
        "same_index_decimal_timestamp_serialization_compatible": fields[
            "time__to__Time"
        ]["decimal_serialization_equivalence_pass"],
    }
    rows_pass = len(trace_rows) == len(poi_rows) == int(contract["required_row_count_each"])
    fields_pass = all(
        value["decimal_serialization_equivalence_pass"] for value in fields.values()
    )
    chronology_pass = all(chronology.values())
    lineage_pass = rows_pass and fields_pass and chronology_pass
    state = (
        "DETERMINISTIC_FIELD_MAPPING_PLUS_NUMERICAL_IDENTITY_CROSSCHECK"
        if lineage_pass else "CONTRADICTED"
    )
    payload = {
        "schema_version": "hartley.h7c.trace_decimal_serialization_identity.v1",
        "hypothesis": "H1",
        "hypothesis_state": state,
        "lineage_identity_pass": lineage_pass,
        "proof_classifications": (
            ["DETERMINISTIC_FIELD_MAPPING", "NUMERICAL_IDENTITY_CROSSCHECK"]
            if lineage_pass else ["CONTRADICTED"]
        ),
        "terminal_if_contradicted": BLOCKED_LINEAGE,
        "serialization_contract_identity": file_identity(
            scratch / SERIALIZATION_CONTRACT_RELATIVE
        ),
        "serialization_contract_freeze_identity": file_identity(
            scratch / SERIALIZATION_CONTRACT_FREEZE_RELATIVE
        ),
        "exact_parsed_binary64_identity": False,
        "exact_binary_diagnostic_preserved": file_identity(
            scratch / TRACE_IDENTITY_RELATIVE
        ),
        "not_byte_text_or_binary_float_identity": True,
        "no_empirical_tolerance": True,
        "observed_maximum_used_to_define_rule": False,
        "resolver_relative_path": str(resolver_relative),
        "expected_row_count_each": 6040,
        "trace_row_count": len(trace_rows),
        "poi_geodetic_row_count": len(poi_rows),
        "row_count_pass": rows_pass,
        "chronology": chronology,
        "field_results": fields,
        "unit_conversion_applied": False,
        "frame_convention_selected_by_numeric_comparison": False,
        **guard.counters(),
    }
    write_json_exclusive(scratch / SERIALIZATION_IDENTITY_RELATIVE, payload)
    proof = f"""# H7C deterministic trace serialization-lineage proof

H1 classification: `{state}`.

The exact-Decimal serialization contract was frozen before this row pass. It
uses no empirical absolute or relative tolerance and does not use the observed
maxima: every printed decimal token defines its exact base-10 rounding cell at
its own printed least-significant digit; paired cells must intersect and signs
must match.

Both sources contain `{len(trace_rows)}` rows. Row order and chronology pass:
`{chronology_pass}`. All seven pre-mapped scalar pairs pass for every row:
`{fields_pass}`. No unit conversion, frame choice, sign choice, offset search,
or trajectory fitting was performed.

The predecessor diagnostic remains byte-identical and proves only
`EXACT_PARSED_BINARY64_IDENTITY=false`. H1 is therefore not byte identity,
text identity, or parsed-binary-float identity; it is deterministic field
mapping plus a numerical serialization-identity cross-check.
"""
    write_exclusive(scratch / SERIALIZATION_PROOF_RELATIVE, proof.encode())
    return {
        "hypothesis": "H1",
        "hypothesis_state": state,
        "lineage_identity_pass": lineage_pass,
        "identity": file_identity(scratch / SERIALIZATION_IDENTITY_RELATIVE),
        "proof": file_identity(scratch / SERIALIZATION_PROOF_RELATIVE),
        "counters": guard.counters(),
    }


def materialize_required_lineage_outputs(scratch: Path) -> dict[str, Any]:
    require_contract_freeze(scratch)
    exact = _load_json(scratch / TRACE_IDENTITY_RELATIVE)
    decimal_identity = _load_json(scratch / SERIALIZATION_IDENTITY_RELATIVE)
    if exact.get("lineage_identity_pass") is not False:
        raise HartleyH7CError("exact-binary diagnostic contradiction is absent")
    if decimal_identity.get("lineage_identity_pass") is not False:
        raise HartleyH7CError("exact-Decimal H1 contradiction is absent")
    rows = (
        (1, "export_timestamp", "time", "Time", "seconds_or_export_native", "DETERMINISTIC_FIELD_MAPPING"),
        (2, "latitude", "lat", "p.vector3.x", "degrees", "DETERMINISTIC_FIELD_MAPPING"),
        (3, "longitude", "lon", "p.vector3.y", "degrees", "DETERMINISTIC_FIELD_MAPPING"),
        (4, "ellipsoidal_height", "height", "p.vector3.z", "metres", "DETERMINISTIC_FIELD_MAPPING"),
        (5, "yaw_source_scalar", "yaw", "ypr.vector3.x", "NOT_EVALUATED_AFTER_LINEAGE_BLOCKER", "DETERMINISTIC_FIELD_MAPPING"),
        (6, "pitch_source_scalar", "pitch", "ypr.vector3.y", "NOT_EVALUATED_AFTER_LINEAGE_BLOCKER", "DETERMINISTIC_FIELD_MAPPING"),
        (7, "roll_source_scalar", "roll", "ypr.vector3.z", "NOT_EVALUATED_AFTER_LINEAGE_BLOCKER", "DETERMINISTIC_FIELD_MAPPING"),
    )
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([
        "order", "semantic", "trace_field", "poi_geodetic_field", "unit_state",
        "classification", "mapping_fixed_before_numeric_comparison",
        "unit_conversion_applied",
    ])
    for order, semantic, trace_field, poi_field, unit, classification in rows:
        writer.writerow([
            order, semantic, trace_field, poi_field, unit, classification, "true", "false",
        ])
    write_exclusive(scratch / REQUIRED_FIELD_MAP_CSV_RELATIVE, stream.getvalue().encode())
    identity = {
        "schema_version": "hartley.h7c.required_trace_to_poi_identity.v1",
        "terminal": BLOCKED_LINEAGE,
        "hypothesis": "H1",
        "hypothesis_state": "CONTRADICTED",
        "mapping_fixed_before_numeric_comparison": True,
        "field_map_csv_identity": file_identity(scratch / REQUIRED_FIELD_MAP_CSV_RELATIVE),
        "trace_data_row_count": 6040,
        "poi_geodetic_data_row_count": 6040,
        "row_count_order_and_chronology_match": True,
        "exact_parsed_binary64_identity": False,
        "exact_binary_diagnostic_identity": file_identity(
            scratch / TRACE_IDENTITY_RELATIVE
        ),
        "exact_binary_maximum_absolute_differences_diagnostic_only": {
            key: value["maximum_absolute_difference"]
            for key, value in exact["required_mapped_fields"].items()
        },
        "exact_decimal_serialization_identity": False,
        "exact_decimal_identity": file_identity(
            scratch / SERIALIZATION_IDENTITY_RELATIVE
        ),
        "exact_decimal_incompatibility_counts": {
            key: value["decimal_serialization_incompatibility_count"]
            for key, value in decimal_identity["field_results"].items()
        },
        "unit_label_correction_identity": file_identity(
            scratch / FIELD_MAP_UNIT_CORRECTION_RELATIVE
        ),
        "ypr_exported_message_official_unit": "UNPROVEN",
        "ypr_dataset_unit_interpretation": "NOT_EVALUATED_AFTER_LINEAGE_BLOCKER",
        "unit_conversion_applied": False,
        "post_result_tolerance_introduced": False,
        "scientific_extrinsic_search_execution_count": 0,
        "trace_open_count": decimal_identity["trace_open_count"],
        "reference_output_open_count": decimal_identity[
            "reference_output_open_count"
        ],
        "reference_rows_read": decimal_identity["reference_rows_read"],
    }
    write_json_exclusive(scratch / REQUIRED_LINEAGE_IDENTITY_RELATIVE, identity)
    proof = f"""# H7C reference-lineage proof

Terminal: `{BLOCKED_LINEAGE}`.

`TRACE_TO_POI_GEODETIC_FIELD_MAP.csv` records the deterministic field mapping
that was fixed before any numeric comparison. Yaw, pitch, and roll use neutral
source-scalar labels: the firmware-exported message unit is `UNPROVEN`, no unit
conversion was applied, and unit semantics are
`NOT_EVALUATED_AFTER_LINEAGE_BLOCKER`.

The trace and FP_POI geodetic exports each have 6,040 rows with matching order
and strict chronology. The immutable exact parsed-binary64 diagnostic is
`{file_identity(scratch / TRACE_IDENTITY_RELATIVE)['sha256']}` and proves
`EXACT_PARSED_BINARY64_IDENTITY=false`. Its additive interpretation is frozen
by `{file_identity(scratch / EXACT_BINARY_INTERPRETATION_RELATIVE)['sha256']}`.

Before another row pass, the exact-Decimal token-cell rule was frozen at
`{file_identity(scratch / SERIALIZATION_CONTRACT_FREEZE_RELATIVE)['sha256']}`.
The resulting immutable identity is
`{file_identity(scratch / SERIALIZATION_IDENTITY_RELATIVE)['sha256']}` and also
fails. The unit-label correction is
`{file_identity(scratch / FIELD_MAP_UNIT_CORRECTION_RELATIVE)['sha256']}`.

The observed differences are tiny CSV-serialization scale, but the required
exact row-wise identity is false. No empirical or post-result tolerance was
introduced. H1 is therefore `CONTRADICTED`; H2-H5 and the extrinsic search are
not evaluated.
"""
    write_exclusive(scratch / REQUIRED_LINEAGE_PROOF_RELATIVE, proof.encode())
    return {
        "field_map": file_identity(scratch / REQUIRED_FIELD_MAP_CSV_RELATIVE),
        "identity": file_identity(scratch / REQUIRED_LINEAGE_IDENTITY_RELATIVE),
        "proof": file_identity(scratch / REQUIRED_LINEAGE_PROOF_RELATIVE),
        "terminal": BLOCKED_LINEAGE,
    }


INITIAL_CONTRACT_COPY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "00_CONTRACTS/H7C_INITIAL_V1_SOURCE_RECOVERY_CONTRACT.yaml"
)
INITIAL_FREEZE_COPY_RELATIVE = (
    PUBLICATION_ROOT_RELATIVE / "00_CONTRACTS/H7C_INITIAL_V1_CONTRACT_FREEZE.json"
)


def collect_storage_health_read_only(scratch_parent: Path, stage_root: Path) -> dict[str, Any]:
    storage = verify_storage_identity(scratch_parent, stage_root)
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "$v=Get-Volume -DriveLetter G; [ordered]@{"
        "DriveLetter=\"$($v.DriveLetter)\";FileSystem=\"$($v.FileSystem)\";"
        "HealthStatus=\"$($v.HealthStatus)\";"
        "OperationalStatus=\"$(($v.OperationalStatus -join ', '))\";"
        "Size=[int64]$v.Size;SizeRemaining=[int64]$v.SizeRemaining} | "
        "ConvertTo-Json -Compress",
    ]
    completed = subprocess.run(
        command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        raise HartleyH7CError("read-only G volume health query failed")
    volume = json.loads(completed.stdout)
    required = {
        "DriveLetter": "G",
        "FileSystem": "exFAT",
        "HealthStatus": "Warning",
        "OperationalStatus": "Full Repair Needed",
    }
    if any(volume.get(key) != value for key, value in required.items()):
        raise HartleyH7CError(f"external volume health identity changed: {volume}")
    return {
        "schema_version": "hartley.h7c.storage_health.v1",
        **storage,
        "get_volume_G_read_only": {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "read_only": True,
        },
        "volume": volume,
        "runtime_storage": "LINUX_LOCAL_EXT4_SCRATCH",
        "external_storage_health": "EXFAT_WARNING_FULL_REPAIR_NEEDED",
        "repair_command_invoked": False,
        "scratch_retention": "RETAIN_WHILE_EXTERNAL_G_STORAGE_UNHEALTHY",
    }


def _final_access_ledger(scratch: Path) -> dict[str, Any]:
    identity = _load_json(scratch / SERIALIZATION_IDENTITY_RELATIVE)
    inventory = _load_json(scratch / RAW_INVENTORY_RELATIVE)
    totals = {
        RAW_FILENAMES[0]: {"hash": 2, "header": 1, "data": 3, "rows": 18120},
        RAW_FILENAMES[1]: {"hash": 2, "header": 1, "data": 3, "rows": 18120},
        RAW_FILENAMES[2]: {"hash": 2, "header": 1, "data": 0, "rows": 0},
        RAW_FILENAMES[3]: {"hash": 2, "header": 1, "data": 0, "rows": 0},
        RAW_FILENAMES[4]: {"hash": 2, "header": 1, "data": 0, "rows": 0},
        RAW_FILENAMES[5]: {"hash": 2, "header": 1, "data": 0, "rows": 0},
        RAW_FILENAMES[6]: {"hash": 2, "header": 1, "data": 0, "rows": 0},
        RAW_FILENAMES[7]: {"hash": 2, "header": 1, "data": 0, "rows": 0},
        RAW_FILENAMES[8]: {"hash": 1, "header": 0, "data": 0, "rows": 0},
        RAW_FILENAMES[9]: {"hash": 1, "header": 0, "data": 0, "rows": 0},
    }
    inventory_rows = {Path(row["relative_path"]).name: row for row in inventory["files"]}
    files = []
    for sequence, filename in enumerate(RAW_FILENAMES, start=1):
        row = inventory_rows[filename]
        counts = totals[filename]
        files.append({
            "sequence": sequence,
            "name": filename,
            "relative_path": row["relative_path"],
            "role": row["role"],
            "identity": row["identity"],
            "cumulative_hash_open_count": counts["hash"],
            "cumulative_header_open_count": counts["header"],
            "cumulative_data_open_count": counts["data"],
            "cumulative_data_rows_read": counts["rows"],
            "trajectory_values_decoded": (
                counts["data"] > 0 and filename in RAW_FILENAMES[:2]
            ),
            "fpl_bag_metadata_decoded": False,
            "fpl_bag_trajectory_values_decoded": False,
        })
    return {
        "schema_version": "hartley.h7c.final_source_access_ledger.v1",
        "initial_pre_access_freeze_was_global_zero": True,
        "v2_freeze_preserved_cumulative_counters": True,
        "phases": [
            {
                "phase": "V1_ADMINISTRATIVE_PATH_RESOLUTION",
                "hash_opens": 8,
                "stat_attempts": 9,
                "data_rows_read": 0,
                "scientific_extrinsic_search": False,
            },
            {
                "phase": "V2_CORRECTED_EXACT_TEN_FILE_INVENTORY",
                "hash_opens": 10,
                "stat_attempts": 10,
                "data_rows_read": 0,
                "scientific_extrinsic_search": False,
            },
            {
                "phase": "CSV_HEADER_SCHEMA_AUDIT",
                "header_opens": 8,
                "data_rows_read": 0,
            },
            {
                "phase": "AUXILIARY_WRAPPER_PARSE_FAILURE",
                "data_opens": 2,
                "data_rows_read": 12080,
                "scientific_contradiction": False,
            },
            {
                "phase": "EXACT_PARSED_BINARY64_DIAGNOSTIC",
                "data_opens": 2,
                "data_rows_read": 12080,
                "result": "CONTRADICTED_DIAGNOSTIC_ONLY",
            },
            {
                "phase": "FROZEN_EXACT_DECIMAL_SERIALIZATION_IDENTITY",
                "data_opens": 2,
                "data_rows_read": 12080,
                "result": "CONTRADICTED_H1_LINEAGE",
            },
        ],
        "files": files,
        "local_resolver_open_count": identity["local_resolver_open_count"],
        "trace_open_count": identity["trace_open_count"],
        "reference_output_open_count": identity["reference_output_open_count"],
        "reference_rows_read": identity["reference_rows_read"],
        "raw_hash_open_count": identity["raw_hash_open_count"],
        "raw_stat_attempt_count": identity["raw_stat_attempt_count"],
        "denied_path_access_count": 0,
        "broad_raw_or_disk_scan_count": 0,
        "fpl_bag_trajectory_values_decoded": False,
        "go2_onboard_pose_or_yaw_input_count": 0,
        "hartley_output_open_count": 0,
        "h5_filter_rerun_count": 0,
        "h6_h6r_rerun_count": 0,
        "scientific_extrinsic_search_execution_count": 0,
    }


def _metric_absence_after_lineage_blocker() -> dict[str, str]:
    reason = "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION"
    return {
        "RELATIVE_POSE_ERROR_1S.csv": reason,
        "RELATIVE_POSE_ERROR_5S.csv": reason,
        "RELATIVE_POSE_ERROR_10S.csv": reason,
        "RELATIVE_POSE_ERROR_SUMMARY.csv": reason,
        "RELATIVE_YAW_INCREMENT.csv": reason,
        "RELATIVE_YAW_INCREMENT_SUMMARY.csv": reason,
        "GAUGE_ALIGNED_DESCRIPTIVE_EPOCH_METRICS.csv": reason,
        "GAUGE_ALIGNED_DESCRIPTIVE_SUMMARY.csv": reason,
        "H7C_BRANCH_METRIC_SUMMARY.csv": reason,
        "H7C_CONJUGATION_INVARIANT_ROTATION_MAGNITUDE_DIAGNOSTIC.csv": reason,
    }


def finalize_blocked_lineage(
    repository: Path,
    scratch: Path,
    initial_h7c_scratch: Path,
    stage_root: Path,
    validation_summary: Mapping[str, Any],
) -> dict[str, Any]:
    git = verify_git_identity(repository)
    decimal_identity = _load_json(scratch / SERIALIZATION_IDENTITY_RELATIVE)
    if decimal_identity.get("lineage_identity_pass") is not False:
        raise HartleyH7CError("H1 decimal lineage contradiction is absent")
    if decimal_identity.get("hypothesis_state") != "CONTRADICTED":
        raise HartleyH7CError("H1 terminal classification mismatch")
    exact_identity_before = file_identity(scratch / TRACE_IDENTITY_RELATIVE)
    exact_proof_before = file_identity(scratch / TRACE_PROOF_RELATIVE)
    frozen = _load_json(scratch / SERIALIZATION_CONTRACT_FREEZE_RELATIVE)
    if exact_identity_before != frozen["exact_binary_identity_artifact_preserved"]:
        raise HartleyH7CError("exact binary identity artifact changed")
    if exact_proof_before != frozen["exact_binary_proof_artifact_preserved"]:
        raise HartleyH7CError("exact binary proof artifact changed")
    write_exclusive(
        scratch / INITIAL_CONTRACT_COPY_RELATIVE,
        (initial_h7c_scratch / CONTRACT_COPY_RELATIVE).read_bytes(),
    )
    write_exclusive(
        scratch / INITIAL_FREEZE_COPY_RELATIVE,
        (initial_h7c_scratch / CONTRACT_FREEZE_RELATIVE).read_bytes(),
    )
    write_exclusive(
        scratch / V1_FAILURE_RELATIVE,
        (initial_h7c_scratch / V1_FAILURE_RELATIVE).read_bytes(),
    )
    if file_identity(scratch / INITIAL_CONTRACT_COPY_RELATIVE) != {
        "sha256": V1_CONTRACT_SHA256, "size": V1_CONTRACT_SIZE,
    }:
        raise HartleyH7CError("initial H7C contract copy mismatch")
    if file_identity(scratch / INITIAL_FREEZE_COPY_RELATIVE) != {
        "sha256": V1_CONTRACT_FREEZE_SHA256, "size": V1_CONTRACT_FREEZE_SIZE,
    }:
        raise HartleyH7CError("initial H7C freeze copy mismatch")
    final_access = _final_access_ledger(scratch)
    write_json_exclusive(scratch / FINAL_ACCESS_LEDGER_RELATIVE, final_access)
    storage = collect_storage_health_read_only(scratch.parent, stage_root)
    write_json_exclusive(scratch / STORAGE_HEALTH_RELATIVE, storage)
    exact = _load_json(scratch / TRACE_IDENTITY_RELATIVE)
    incompatibilities = {
        key: value["decimal_serialization_incompatibility_count"]
        for key, value in decimal_identity["field_results"].items()
    }
    exact_maxima = {
        key: value["maximum_absolute_difference"]
        for key, value in exact["required_mapped_fields"].items()
    }
    terminal_audit = {
        "schema_version": "hartley.h7c.lineage_terminal_audit.v1",
        "terminal": BLOCKED_LINEAGE,
        "h1_state": "CONTRADICTED",
        "row_counts": {"trace": 6040, "poi_geodetic": 6040},
        "row_count_order_and_chronology_match": True,
        "exact_parsed_binary64_identity": False,
        "exact_binary_maximum_absolute_differences_diagnostic_only": exact_maxima,
        "exact_decimal_serialization_identity": False,
        "exact_decimal_incompatibility_counts": incompatibilities,
        "differences_are_tiny_csv_serialization_scale": True,
        "required_exact_rowwise_identity_is_false": True,
        "post_result_tolerance_introduced": False,
        "empirical_tolerance_used": False,
        "field_mapping_selected_from_numeric_results": False,
        "unit_semantics": "NOT_EVALUATED_AFTER_LINEAGE_BLOCKER",
        "incorrect_rad_labels_preserved_only_as_predecessor_diagnostic": True,
        "official_exported_message_unit": "UNPROVEN",
        "h2_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "h3_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "h4_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "h5_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "pose_semantics_audit_executed": False,
        "frame_graph_audit_executed": False,
        "scientific_extrinsic_search_execution_count": 0,
        "hartley_outputs_opened": False,
        "metric_files_created": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
    }
    write_json_exclusive(scratch / TERMINAL_AUDIT_RELATIVE, terminal_audit)
    raw_inventory = _load_json(scratch / RAW_INVENTORY_RELATIVE)
    raw_hashes = {
        row["relative_path"]: row["identity"] for row in raw_inventory["files"]
    }
    status = {
        "schema_version": "hartley.h7c.final_status.v1",
        **status_for_outcome(BLOCKED_LINEAGE),
        "start_head": TASK_START_HEAD,
        "end_head": TASK_START_HEAD,
        "lse01_terminalized": True,
        "h1_trace_lineage_state": "CONTRADICTED",
        "h2_reference_point_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "h3_orientation_semantics_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "h4_full_pose_source_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "h5_extrinsic_state": "NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION",
        "exact_trace_and_poi_row_count": 6040,
        "trace_poi_row_order_and_chronology_match": True,
        "required_exact_trace_poi_identity": False,
        "exact_parsed_binary64_identity": False,
        "exact_decimal_serialization_identity": False,
        "post_result_tolerance_introduced": False,
        "absolute_position_RMSE": None,
        "relative_pose_metrics_complete": False,
        "relative_yaw_increment_complete": False,
        "gauge_aligned_descriptive_metrics_complete": False,
        "metric_artifacts": _metric_absence_after_lineage_blocker(),
        "metric_files_created": 0,
        "trace_open_count": final_access["trace_open_count"],
        "reference_output_open_count": final_access["reference_output_open_count"],
        "reference_rows_read": final_access["reference_rows_read"],
        "raw_hash_open_count": final_access["raw_hash_open_count"],
        "raw_stat_attempt_count": final_access["raw_stat_attempt_count"],
        "local_resolver_open_count": final_access["local_resolver_open_count"],
        "denied_path_access_count": 0,
        "broad_raw_or_disk_scan_count": 0,
        "fpl_bag_trajectory_values_decoded": False,
        "scientific_extrinsic_search_execution_count": 0,
        "extrinsic_search_exhausted": False,
        "h5_filter_rerun_count": 0,
        "h6_h6r_rerun_count": 0,
        "hartley_synthetic_validation_rerun_count": 0,
        "canonical541_executed": False,
        "horizontal18_executed": False,
        "other_method_executed": False,
        "ext01_through_ext06_executed": False,
        "runtime_provenance": {
            "data_mode": "real_by2_raw",
            "raw_source_hashes": raw_hashes,
            "provider_hashes": {
                "h5_input_cache": "c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065",
                "h5_contact_event_ledger": "8e80cde9b90ade49753d8fd97e554af3c032c664d1d336f663838cbb68204358",
            },
            "synthetic_data_used": False,
            "semisynthetic_data_used": False,
            "trace_used_online": False,
            "receiver_imu_as_body_imu": False,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deleted_for_metric": False,
            "old_runtime_input_count": 0,
            "code_commit": TASK_START_HEAD,
            "execution_code_committed": False,
            "dirty_or_precommit_scoped_execution": True,
            "later_commit_mapping": "PENDING_SUPERVISOR_COMMIT_HASH_MAPPING",
            "config_hash": load_and_validate_contract(repository)[0]["config_hash"]["value"],
        },
        "initial_v1_path_resolution_failure_preserved": True,
        "v2_path_correction_not_scientific_retry": True,
        "h7r4_or_h7r5_created": False,
        "predecessor_files_preserved": True,
        "scratch_retention": "RETAIN_WHILE_EXTERNAL_G_STORAGE_UNHEALTHY",
        "validation_summary": dict(validation_summary),
        "git_identity": git,
    }
    write_json_exclusive(scratch / FINAL_STATUS_RELATIVE, status)
    report = f"""# LSE01 H7C final report

Terminal: `{BLOCKED_LINEAGE}`.

The frozen deterministic mapping found 6,040 trace rows and 6,040 FP_POI
geodetic rows with matching order and strict chronology. The required exact
row-wise identity nevertheless failed. Differences are tiny CSV-serialization
scale, but exact parsed-binary64 identity is false and the separately frozen
exact-Decimal printed-token-cell test also fails. No post-result tolerance was
introduced, so H1 is genuinely `CONTRADICTED`.

H2-H5, pose semantics, frame graph construction, the bounded
`T_FP_POI_from_GO2_BODY_IMU` source search, Hartley output access, and all
reference-relative metrics are `NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION`.
The scientific extrinsic-search execution count is zero. No H5/H6/H6R filter,
synthetic validation, EXT01-EXT06, HORIZONTAL18, Canonical-541, or other method
was executed.

The original H7, H7R1, H7R2, H6R, and two unrelated Canonical worktree files
remain preserved. The initial H7C path-layout failure is retained as an
administrative V1 record; the V2 sibling-path correction carried counters
forward and was not a scientific retry.

LSE01 is not complete, `ready_for_ext06=false`, and `ext06_executed=false`.
"""
    write_exclusive(scratch / FINAL_REPORT_RELATIVE, report.encode())
    claim_source = repository / TRACKED_FINAL_CLAIM_RELATIVE
    write_exclusive(scratch / FINAL_CLAIM_RELATIVE, claim_source.read_bytes())
    core_for_freeze = (
        CONTRACT_COPY_RELATIVE, CONTRACT_FREEZE_RELATIVE,
        INITIAL_CONTRACT_COPY_RELATIVE, INITIAL_FREEZE_COPY_RELATIVE,
        PREDECESSOR_PRE_RELATIVE, V1_FAILURE_RELATIVE, STORAGE_HEALTH_RELATIVE,
        RAW_INVENTORY_RELATIVE, ACCESS_LEDGER_RELATIVE, FINAL_ACCESS_LEDGER_RELATIVE,
        SCHEMA_HEADERS_RELATIVE, FIELD_MAP_RELATIVE, FIELD_MAP_FREEZE_RELATIVE,
        LINEAGE_AUX_FAILURE_RELATIVE, TRACE_IDENTITY_RELATIVE, TRACE_PROOF_RELATIVE,
        FIELD_MAP_UNIT_CORRECTION_RELATIVE, EXACT_BINARY_INTERPRETATION_RELATIVE,
        SERIALIZATION_CONTRACT_RELATIVE, SERIALIZATION_CONTRACT_FREEZE_RELATIVE,
        SERIALIZATION_IDENTITY_RELATIVE, SERIALIZATION_PROOF_RELATIVE,
        REQUIRED_FIELD_MAP_CSV_RELATIVE, REQUIRED_LINEAGE_IDENTITY_RELATIVE,
        REQUIRED_LINEAGE_PROOF_RELATIVE,
        TERMINAL_AUDIT_RELATIVE, FINAL_STATUS_RELATIVE, FINAL_REPORT_RELATIVE,
        FINAL_CLAIM_RELATIVE,
    )
    evaluation_freeze = {
        "schema_version": "hartley.h7c.evaluation_freeze.v1",
        "terminal": BLOCKED_LINEAGE,
        "files": {
            str(relative): file_identity(scratch / relative)
            for relative in core_for_freeze
        },
        "exact_binary_artifacts_preserved": (
            file_identity(scratch / TRACE_IDENTITY_RELATIVE) == exact_identity_before
            and file_identity(scratch / TRACE_PROOF_RELATIVE) == exact_proof_before
        ),
        "predecessor_post_snapshot_state": "WRITTEN_AFTER_CORE_PUBLICATION",
        "scientific_extrinsic_search_execution_count": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
    }
    write_json_exclusive(scratch / EVALUATION_FREEZE_RELATIVE, evaluation_freeze)
    return {
        "terminal": BLOCKED_LINEAGE,
        "status_identity": file_identity(scratch / FINAL_STATUS_RELATIVE),
        "report_identity": file_identity(scratch / FINAL_REPORT_RELATIVE),
        "claim_identity": file_identity(scratch / FINAL_CLAIM_RELATIVE),
        "evaluation_freeze_identity": file_identity(scratch / EVALUATION_FREEZE_RELATIVE),
        "scientific_extrinsic_search_execution_count": 0,
        "lse01_complete": False,
        "ready_for_ext06": False,
        "ext06_executed": False,
    }


CORE_PUBLICATION_RELATIVES = (
    CONTRACT_COPY_RELATIVE, CONTRACT_FREEZE_RELATIVE,
    INITIAL_CONTRACT_COPY_RELATIVE, INITIAL_FREEZE_COPY_RELATIVE,
    PREDECESSOR_PRE_RELATIVE, V1_FAILURE_RELATIVE, STORAGE_HEALTH_RELATIVE,
    RAW_INVENTORY_RELATIVE, ACCESS_LEDGER_RELATIVE, FINAL_ACCESS_LEDGER_RELATIVE,
    SCHEMA_HEADERS_RELATIVE, FIELD_MAP_RELATIVE, FIELD_MAP_FREEZE_RELATIVE,
    LINEAGE_AUX_FAILURE_RELATIVE, TRACE_IDENTITY_RELATIVE, TRACE_PROOF_RELATIVE,
    FIELD_MAP_UNIT_CORRECTION_RELATIVE, EXACT_BINARY_INTERPRETATION_RELATIVE,
    SERIALIZATION_CONTRACT_RELATIVE, SERIALIZATION_CONTRACT_FREEZE_RELATIVE,
    SERIALIZATION_IDENTITY_RELATIVE, SERIALIZATION_PROOF_RELATIVE,
    REQUIRED_FIELD_MAP_CSV_RELATIVE, REQUIRED_LINEAGE_IDENTITY_RELATIVE,
    REQUIRED_LINEAGE_PROOF_RELATIVE,
    TERMINAL_AUDIT_RELATIVE, EVALUATION_FREEZE_RELATIVE,
    FINAL_STATUS_RELATIVE, FINAL_REPORT_RELATIVE, FINAL_CLAIM_RELATIVE,
)


def publish_blocked_lineage(
    repository: Path,
    scratch: Path,
    stage_root: Path,
    h6r_scratch: Path,
    original_h7_scratch: Path,
    h7r1_scratch: Path,
    h7r2_scratch: Path,
) -> dict[str, Any]:
    verify_git_identity(repository)
    status = _load_json(scratch / FINAL_STATUS_RELATIVE)
    if status.get("terminal") != BLOCKED_LINEAGE:
        raise HartleyH7CError("blocked-lineage status is not frozen")
    for relative in (*CORE_PUBLICATION_RELATIVES, PREDECESSOR_POST_RELATIVE,
                     PUBLICATION_MANIFEST_RELATIVE, PUBLICATION_PARITY_RELATIVE):
        if (stage_root / relative).exists():
            raise HartleyH7CError(f"non-overwriting H7C destination exists: {relative}")
    for relative in CORE_PUBLICATION_RELATIVES:
        source = scratch / relative
        if not source.is_file():
            raise HartleyH7CError(f"H7C publication source absent: {relative}")
        write_exclusive(stage_root / relative, source.read_bytes())
    pre = _load_json(scratch / PREDECESSOR_PRE_RELATIVE)
    post = snapshot_predecessors(
        stage_root, h6r_scratch, original_h7_scratch, h7r1_scratch, h7r2_scratch,
    )
    if pre.get("families") != post.get("families"):
        raise HartleyH7CError("predecessor identities changed during H7C publication")
    post_payload = {
        **post,
        "snapshot_phase": "POST_H7C_CORE_PUBLICATION",
        "pre_snapshot_identity": file_identity(scratch / PREDECESSOR_PRE_RELATIVE),
        "unchanged_from_pre_snapshot": True,
        "h6r_original_h7_h7r1_h7r2_modified": False,
    }
    write_json_exclusive(scratch / PREDECESSOR_POST_RELATIVE, post_payload)
    write_exclusive(
        stage_root / PREDECESSOR_POST_RELATIVE,
        (scratch / PREDECESSOR_POST_RELATIVE).read_bytes(),
    )
    publish_relatives = (*CORE_PUBLICATION_RELATIVES, PREDECESSOR_POST_RELATIVE)
    manifest = {
        "schema_version": "hartley.h7c.publication_manifest.v1",
        "terminal": BLOCKED_LINEAGE,
        "exclusive_create_and_fsync_required": True,
        "compact_publication_only": True,
        "h5_h6_h6r_payload_duplicated": False,
        "predecessors_preserved": True,
        "files": {
            str(relative): file_identity(scratch / relative)
            for relative in publish_relatives
        },
    }
    write_json_exclusive(scratch / PUBLICATION_MANIFEST_RELATIVE, manifest)
    write_exclusive(
        stage_root / PUBLICATION_MANIFEST_RELATIVE,
        (scratch / PUBLICATION_MANIFEST_RELATIVE).read_bytes(),
    )
    parity_relatives = (*publish_relatives, PUBLICATION_MANIFEST_RELATIVE)
    rows = []
    for relative in parity_relatives:
        rows.append({
            "relative_path": str(relative),
            **hash_size_parity(scratch / relative, stage_root / relative),
        })
    if not all(row["bytes_equal"] for row in rows):
        raise HartleyH7CError("H7C publication parity failure")
    parity = {
        "schema_version": "hartley.h7c.publication_parity.v1",
        "terminal": BLOCKED_LINEAGE,
        "file_count": len(rows),
        "files": rows,
        "all_published_bytes_equal": True,
        "predecessors_preserved_unchanged": True,
        "scratch_retained_while_external_storage_unhealthy": True,
    }
    write_json_exclusive(scratch / PUBLICATION_PARITY_RELATIVE, parity)
    write_exclusive(
        stage_root / PUBLICATION_PARITY_RELATIVE,
        (scratch / PUBLICATION_PARITY_RELATIVE).read_bytes(),
    )
    if file_identity(scratch / PUBLICATION_PARITY_RELATIVE) != file_identity(
        stage_root / PUBLICATION_PARITY_RELATIVE
    ):
        raise HartleyH7CError("H7C parity-control copy mismatch")
    return {
        "terminal": BLOCKED_LINEAGE,
        "published_file_count_including_parity_control": len(rows) + 1,
        "publication_manifest_identity": file_identity(
            scratch / PUBLICATION_MANIFEST_RELATIVE
        ),
        "publication_parity_identity": file_identity(
            scratch / PUBLICATION_PARITY_RELATIVE
        ),
        "all_published_bytes_equal": True,
        "predecessors_preserved": True,
        "scientific_extrinsic_search_execution_count": 0,
        "lse01_complete": False,
        "ready_for_ext06": False,
        "ext06_executed": False,
    }
