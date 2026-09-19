from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml


TASK_START_HEAD = "dee32bea365e4a3b478a35d4dd198894375c5dab"
EXPECTED_BRANCH = "stage/clean3-math-repair"
TERMINAL = "BLOCKED_LSE01_H7_REFERENCE_POINT_OR_FRAME_IDENTITY_UNRESOLVED"
H5_STATUS = "PASS_LSE01_H5_BY2_NATIVE_RUN_COMPLETE"
H6_STATUS = "BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE"
H6R_STATUS = "PASS_LSE01_H6R_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED"
EVALUATOR_SHA256 = "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
TRACE_DECLARED_SHA256 = "ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"
RAW_FULL_SHA256 = "95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
RAW_PREFIX_SHA256 = "03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097"
H5_CACHE_SHA256 = "c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065"
H5_EVENT_LEDGER_SHA256 = "8e80cde9b90ade49753d8fd97e554af3c032c664d1d336f663838cbb68204358"
CONTRACT_RELATIVE = Path(
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/"
    "04_METHOD_CONTRACTS/H7_EVALUATION_CONTRACT.yaml"
)
ALLOWED_UNTRACKED = {
    "scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py",
    "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py",
}
H7_SCOPED_PATHS = {
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/H7_EVALUATION_CONTRACT.yaml",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7.py",
    "scripts/paper_rebuild/evaluate_hartley_h7.py",
    "tests/paper_rebuild/test_hartley_h7_contracts.py",
    "docs/paper_rebuild/horizontal_literature/hartley/stage_payload/11_REPORT/LSE01_HARTLEY_CLAIM_BOUNDARY.md",
}
BRANCHES = (
    ("H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM", "01_PRIMARY_GO2_ALLAN_EQ61_FK10MM", True),
    ("H5_FK05MM_SENSITIVITY", "02_FK05MM", False),
    ("H5_FK20MM_SENSITIVITY", "03_FK20MM", False),
    (
        "H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY",
        "04_PAPER_PROCESS_REGRESSION",
        False,
    ),
)
Q_REPORT = np.diag([1.0, -1.0, -1.0])


class HartleyH7Error(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _write_json(path: Path, value: Any) -> None:
    _write_exclusive(path, _canonical_json(value))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise HartleyH7Error(f"JSON object required: {path}")
    return value


def target_grid() -> np.ndarray:
    return 66.0 + np.arange(2741, dtype=np.float64) * 0.1


def validate_reporting_rotation(rotation: np.ndarray = Q_REPORT) -> dict[str, Any]:
    rotation = np.asarray(rotation, dtype=np.float64)
    determinant = float(np.linalg.det(rotation))
    orthogonality_error = float(np.linalg.norm(rotation.T @ rotation - np.eye(3)))
    round_trip_error = float(np.linalg.norm(rotation.T @ (rotation @ np.eye(3)) - np.eye(3)))
    gravity_world_up = np.asarray([0.0, 0.0, -9.81])
    gravity_reporting = rotation @ gravity_world_up
    passed = (
        rotation.shape == (3, 3)
        and abs(determinant - 1.0) <= 1.0e-15
        and orthogonality_error <= 1.0e-15
        and round_trip_error <= 1.0e-15
        and np.allclose(gravity_reporting, [0.0, 0.0, 9.81])
    )
    return {
        "determinant": determinant,
        "orthogonality_error_fro": orthogonality_error,
        "round_trip_error_fro": round_trip_error,
        "right_handed": determinant > 0.0,
        "gravity_world_up_mps2": gravity_world_up.tolist(),
        "gravity_ned_shaped_reporting_mps2": gravity_reporting.tolist(),
        "passed": bool(passed),
    }


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = np.asarray(vector, dtype=np.float64)
    return np.asarray([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def so3_exp(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    theta = float(np.linalg.norm(vector))
    matrix = _skew(vector)
    if theta < 1.0e-10:
        return np.eye(3) + matrix + 0.5 * matrix @ matrix
    return np.eye(3) + math.sin(theta) / theta * matrix + (
        (1.0 - math.cos(theta)) / (theta * theta)
    ) * matrix @ matrix


def so3_log(rotation: np.ndarray) -> np.ndarray:
    rotation = np.asarray(rotation, dtype=np.float64)
    cosine = float(np.clip((np.trace(rotation) - 1.0) * 0.5, -1.0, 1.0))
    theta = math.acos(cosine)
    vee = np.asarray([
        rotation[2, 1] - rotation[1, 2],
        rotation[0, 2] - rotation[2, 0],
        rotation[1, 0] - rotation[0, 1],
    ])
    if theta < 1.0e-10:
        return 0.5 * vee
    return theta / (2.0 * math.sin(theta)) * vee


def interpolate_so3(rotation0: np.ndarray, rotation1: np.ndarray, fraction: float) -> np.ndarray:
    if not 0.0 <= fraction <= 1.0:
        raise HartleyH7Error("SO(3) interpolation fraction would extrapolate")
    return np.asarray(rotation0) @ so3_exp(fraction * so3_log(np.asarray(rotation0).T @ rotation1))


def pose(rotation: np.ndarray, position: np.ndarray) -> np.ndarray:
    value = np.eye(4)
    value[:3, :3] = np.asarray(rotation)
    value[:3, 3] = np.asarray(position)
    return value


def relative_pose_error(
    estimate0: np.ndarray, estimate1: np.ndarray, reference0: np.ndarray, reference1: np.ndarray,
) -> np.ndarray:
    delta_estimate = np.linalg.inv(estimate0) @ estimate1
    delta_reference = np.linalg.inv(reference0) @ reference1
    return np.linalg.inv(delta_reference) @ delta_estimate


def rotation_z(yaw_rad: float) -> np.ndarray:
    cosine, sine = math.cos(yaw_rad), math.sin(yaw_rad)
    return np.asarray([[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]])


def left_gauge_pose(transform: np.ndarray, value: np.ndarray) -> np.ndarray:
    return np.asarray(transform) @ np.asarray(value)


def fixed_primary_gauge(
    primary_rotation: np.ndarray,
    primary_position: np.ndarray,
    reference_rotation: np.ndarray,
    reference_position: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    estimate_yaw = math.atan2(primary_rotation[1, 0], primary_rotation[0, 0])
    reference_yaw = math.atan2(reference_rotation[1, 0], reference_rotation[0, 0])
    yaw_only = rotation_z(reference_yaw - estimate_yaw)
    translation = np.asarray(reference_position) - yaw_only @ np.asarray(primary_position)
    return yaw_only, translation


def apply_fixed_gauge(
    yaw_only: np.ndarray, translation: np.ndarray, rotation: np.ndarray,
    velocity: np.ndarray, position: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return yaw_only @ rotation, yaw_only @ velocity, yaw_only @ position + translation


def verify_git_start(repository: Path) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=repository, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if head != TASK_START_HEAD or branch != EXPECTED_BRANCH:
        raise HartleyH7Error(f"frozen Git identity mismatch: {branch}@{head}")
    status_lines = subprocess.run(
        ["git", "status", "--short"], cwd=repository, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.splitlines()
    untracked = {line[3:] for line in status_lines if line.startswith("?? ")}
    unexpected_untracked = sorted(untracked - ALLOWED_UNTRACKED - H7_SCOPED_PATHS)
    tracked_changes = [line for line in status_lines if not line.startswith("?? ")]
    unexpected_tracked = [line for line in tracked_changes if line[3:] not in H7_SCOPED_PATHS]
    if unexpected_untracked or unexpected_tracked or not ALLOWED_UNTRACKED.issubset(untracked):
        raise HartleyH7Error(
            f"worktree scope mismatch: unexpected_untracked={unexpected_untracked}, "
            f"unexpected_tracked={unexpected_tracked}, untracked={sorted(untracked)}"
        )
    return {
        "branch": branch,
        "head": head,
        "preserved_untracked_files": sorted(ALLOWED_UNTRACKED),
        "uncommitted_h7_scoped_paths": sorted(untracked & H7_SCOPED_PATHS),
        "tracked_changes_limited_to_h7_allowlist": True,
    }


def _verify_one(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        raise HartleyH7Error(f"frozen file missing: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != int(expected["size"]) or digest != expected["sha256"]:
        raise HartleyH7Error(f"frozen file mismatch: {path}")
    return {"size": size, "sha256": digest}


def verify_h5_inputs(stage_root: Path, h5_scratch: Path) -> dict[str, Any]:
    status = _load_json(stage_root / "11_REPORT/LSE01_H5_STATUS.json")
    if status.get("terminal_status") != H5_STATUS:
        raise HartleyH7Error("H5 accepted status mismatch")
    if status.get("reference_open_count") != 0 or status.get("trace_open_count") != 0:
        raise HartleyH7Error("H5 reference access was not zero")
    required_provenance = {
        "data_mode": "real_by2_raw",
        "old_runtime_input_count": 0,
        "trace_used_online": False,
    }
    if any(status.get(key) != value for key, value in required_provenance.items()):
        raise HartleyH7Error("H5 runtime provenance boundary mismatch")
    expected_status_hashes = {
        "provider_raw_sha256": RAW_FULL_SHA256,
        "provider_complete_prefix_sha256": RAW_PREFIX_SHA256,
        "cache_sha256": H5_CACHE_SHA256,
        "provider_event_ledger_sha256": H5_EVENT_LEDGER_SHA256,
    }
    if any(status.get(key) != value for key, value in expected_status_hashes.items()):
        raise HartleyH7Error("H5 raw/provider accepted identity mismatch")
    checked: list[dict[str, Any]] = []
    native_freezes: dict[str, dict[str, Any]] = {}
    for run_id, publication_directory, primary in BRANCHES:
        external = stage_root / "08_BY2_NATIVE" / publication_directory
        freeze_path = external / "NATIVE_FREEZE.json"
        freeze = _load_json(freeze_path)
        native_freezes[run_id] = {
            "relative_path": str(freeze_path.relative_to(stage_root)),
            "sha256": sha256_file(freeze_path),
            "size": freeze_path.stat().st_size,
        }
        if freeze.get("schema_version") != "hartley.h5.native_freeze.v1":
            raise HartleyH7Error(f"native freeze schema mismatch: {run_id}")
        files = freeze.get("files")
        if not isinstance(files, dict) or len(files) != 13:
            raise HartleyH7Error(f"native freeze file count mismatch: {run_id}")
        roots = {
            "source_run": h5_scratch / "01_RUNS" / run_id,
            "local_final_publication": h5_scratch / "FINAL_PUBLICATION_V4/08_BY2_NATIVE" / publication_directory,
            "external_stage": external,
        }
        for filename, expected in files.items():
            identities = {role: _verify_one(root / filename, expected) for role, root in roots.items()}
            checked.append({
                "run_id": run_id,
                "primary": primary,
                "relative_file": filename,
                "identities": identities,
            })
        freeze_expected = {
            "size": freeze_path.stat().st_size,
            "sha256": sha256_file(freeze_path),
        }
        for role, root in roots.items():
            if role == "external_stage":
                continue
            _verify_one(root / "NATIVE_FREEZE.json", freeze_expected)
    provider = _load_json(stage_root / "08_BY2_NATIVE/00_PROVIDER/H5_INPUT_CACHE_MANIFEST.json")
    provider_files = {
        "H5_INPUT_CACHE.bin": {
            "size": provider["cache_size_bytes"], "sha256": provider["cache_sha256"],
        },
        "H5_INPUT_CONTACT_EVENT_LEDGER.jsonl": {
            "size": 340502, "sha256": provider["event_ledger_sha256"],
        },
    }
    provider_roots = {
        "source_provider": h5_scratch / "00_PROVIDER",
        "local_final_publication": h5_scratch / "FINAL_PUBLICATION_V4/08_BY2_NATIVE/00_PROVIDER",
        "external_stage": stage_root / "08_BY2_NATIVE/00_PROVIDER",
    }
    for filename, expected in provider_files.items():
        for root in provider_roots.values():
            _verify_one(root / filename, expected)
    publication = _load_json(stage_root / "08_BY2_NATIVE/00_PROVIDER/H5_EXTERNAL_PUBLICATION_PARITY.json")
    if publication.get("source_to_publication_hash_mismatch_count") != 0:
        raise HartleyH7Error("H5 publication parity mismatch")
    return {
        "status": status["terminal_status"],
        "run_order": [run_id for run_id, _directory, _primary in BRANCHES],
        "primary_run": BRANCHES[0][0],
        "nonselective_run_count": 3,
        "native_freeze_count": 4,
        "native_freezes": native_freezes,
        "native_file_count_per_freeze": 13,
        "source_local_publication_external_identity_count": len(checked),
        "all_three_copy_hash_and_size_parity": True,
        "input_cache_sha256": provider["cache_sha256"],
        "input_event_ledger_sha256": provider["event_ledger_sha256"],
        "raw_full_sha256": status["provider_raw_sha256"],
        "complete_prefix_sha256": status["provider_complete_prefix_sha256"],
        "external_publication_manifest_sha256": publication["manifest_sha256"],
        "external_publication_mismatch_count": 0,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "data_mode": status["data_mode"],
        "old_runtime_input_count": status["old_runtime_input_count"],
        "trace_used_online": status["trace_used_online"],
    }


def verify_h6r_preservation(stage_root: Path) -> dict[str, Any]:
    original = _load_json(stage_root / "11_REPORT/LSE01_H6_STATUS.json")
    recovery = _load_json(stage_root / "11_REPORT/LSE01_H6R_STATUS.json")
    parity = _load_json(stage_root / "11_REPORT/H6R_EXTERNAL_PUBLICATION_PARITY.json")
    if original.get("terminal_status") != H6_STATUS:
        raise HartleyH7Error("original H6 blocker was not preserved")
    if recovery.get("terminal_status") != H6R_STATUS:
        raise HartleyH7Error("H6R accepted status mismatch")
    if not recovery.get("original_h6_status_preserved"):
        raise HartleyH7Error("H6R does not preserve original H6")
    if recovery.get("reference_open_count") != 0 or recovery.get("trace_open_count") != 0:
        raise HartleyH7Error("H6R reference access was not zero")
    if not parity.get("all_published_bytes_equal") or parity.get("file_count") != 97:
        raise HartleyH7Error("H6R publication parity mismatch")
    return {
        "original_h6_terminal": original["terminal_status"],
        "original_h6_preserved": True,
        "h6r_terminal": recovery["terminal_status"],
        "h6r_scientifically_supersedes_original_blocker_without_deletion": True,
        "gauge_equivalence_pass": recovery["gauge_equivalence_pass"],
        "ideal_observability_gauge_dimension": recovery["ideal_observability_gauge_dimension"],
        "reference_open_count": 0,
        "trace_open_count": 0,
        "published_file_count": parity["file_count"],
        "all_published_bytes_equal": True,
    }


def _point_contract_markdown(evaluator_path: Path) -> str:
    return f"""# H7 reference and physical-point identity contract

Terminal: `{TERMINAL}`.

This contract was frozen with `reference_open_count=0`, `trace_open_count=0`, and
`reference_rows_read=0`. The trace CSV was not opened, statted, or hashed.

## Closed Hartley side

- `p` is the Go2 body-IMU origin used by the reproduced InEKF.
- `R_WB` maps Go2 body FLU to Hartley world-up.
- The reporting conversion is the proper rotation `diag(1,-1,-1)`; it is
  right-handed, has determinant +1, round-trips, and maps world-up gravity to
  the NED-shaped positive-z gravity direction without creating north.

## Frozen evaluator evidence

The exact evaluator implementation `{evaluator_path.name}` has SHA-256
`{EVALUATOR_SHA256}`. It interprets scalar trace latitude, longitude,
ellipsoidal height, roll, pitch, and yaw; unwraps ENU yaw before interpolation;
and converts yaw by `wrap360(90-yaw_ENU)`. It does not expose reference velocity
or a full SO(3) attitude/body-frame contract.

## Unresolved reference side

Frozen project evidence does not identify whether trace position is the same
Go2 body-IMU point, a GNSS antenna, the Fixposition device IMU/BODY point, or
another configured POI. It also supplies no measured Fixposition POI/BODY to
Go2 body-IMU fixed transform and no closed reference BODY-axis identity.

The project `[0.03,0.03,-0.30] m` vector is a solver GNSS measurement lever arm
in FRD. The maintained evaluator explicitly applies no point compensation, so
that vector is not an authorized evaluator point transform.

No trajectory error was used to infer a lever arm, sign, axis permutation, or
constant rotation. Therefore position, velocity, pose, relative-yaw, alignment,
branch-comparison, and evaluator-gauge metrics are all `NOT_EVALUATED`.
"""


def _claim_boundary() -> str:
    return f"""# LSE01 Hartley claim boundary

Terminal: `{TERMINAL}`.

- Algorithm core: faithful IJRR2020-reported backend reproduction.
- BY2 adaptation: Go2 high-level FK-like proxy, not raw joint/URDF FK.
- Global translation and global yaw about gravity are unobservable.
- Absolute position/yaw RMSE are not applicable and have no numeric values.
- Only gauge-invariant relative odometry and fixed-gauge same-source descriptive
  metrics would be admissible; H7 metrics are `NOT_EVALUATED` because the
  reference physical point/body-frame identity is unresolved.
- The reference is Fixposition-derived and same-source, not independent ground
  truth.
- NIS reflects conservative/correlated proxy behavior and is not accuracy proof.
- Hartley must not enter a flat absolute-yaw ranking against LegSA.
"""


def _metric_absence() -> dict[str, str]:
    return {
        "RELATIVE_POSE_ERROR_1S.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "RELATIVE_POSE_ERROR_5S.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "RELATIVE_POSE_ERROR_10S.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "RELATIVE_POSE_ERROR_SUMMARY.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "RELATIVE_YAW_INCREMENT.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "RELATIVE_YAW_INCREMENT_SUMMARY.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "GAUGE_ALIGNED_DESCRIPTIVE_EPOCH_METRICS.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "GAUGE_ALIGNED_DESCRIPTIVE_SUMMARY.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "H7_BRANCH_METRIC_SUMMARY.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "H7_BRANCH_RELATIVE_METRIC_PAIRWISE.csv": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
        "H7_EVALUATOR_GAUGE_INVARIANCE_TEST.json": "NOT_EVALUATED_DUE_TO_REFERENCE_POINT_OR_FRAME_BLOCKER",
    }


def _file_identity(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    return {"sha256": sha256_file(path), "size": path.stat().st_size}


def materialize_blocker(
    repository: Path,
    scratch: Path,
    stage_root: Path,
    h5_scratch: Path,
    evaluator_path: Path,
    storage_health: dict[str, Any],
) -> dict[str, Any]:
    raise HartleyH7Error("LEGACY_H7_MATERIALIZER_DISABLED")
    # Historical implementation is retained below solely to audit immutable H7.
    git = verify_git_start(repository)
    if scratch.exists():
        raise HartleyH7Error(f"non-overwriting scratch already exists: {scratch}")
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.mkdir()
    if storage_health.get("FileSystem") != "exFAT" or storage_health.get("HealthStatus") != "Warning":
        raise HartleyH7Error("required read-only unhealthy G: evidence mismatch")
    if storage_health.get("OperationalStatus") != "Full Repair Needed":
        raise HartleyH7Error("G: operational status mismatch")
    if sha256_file(evaluator_path) != EVALUATOR_SHA256:
        raise HartleyH7Error("exact evaluator identity mismatch")

    h5 = verify_h5_inputs(stage_root, h5_scratch)
    h6r = verify_h6r_preservation(stage_root)
    contract_source = repository / CONTRACT_RELATIVE
    contract = yaml.safe_load(contract_source.read_text())
    if contract["reference_access_freeze"] != {
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "contract_must_be_frozen_before_reference_open": True,
        "trace_stat_or_hash_before_point_frame_gate": False,
    }:
        raise HartleyH7Error("reference counter freeze mismatch")
    if contract["reference_identity"]["declared_sha256"] != TRACE_DECLARED_SHA256:
        raise HartleyH7Error("declared trace lock identity mismatch")

    output = scratch
    contract_relative = Path("12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_EVALUATION_CONTRACT.yaml")
    _write_exclusive(output / contract_relative, contract_source.read_bytes())
    contract_freeze_relative = Path("12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_CONTRACT_FREEZE.json")
    contract_freeze = {
        "schema_version": "hartley.h7.contract_freeze.v1",
        "contract_relative_path": str(contract_relative),
        "contract_sha256": sha256_file(output / contract_relative),
        "contract_size": (output / contract_relative).stat().st_size,
        "frozen_before_reference_open": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
    }
    _write_json(output / contract_freeze_relative, contract_freeze)

    point_relative = Path(
        "12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_REFERENCE_AND_POINT_IDENTITY_CONTRACT.md"
    )
    _write_exclusive(output / point_relative, _point_contract_markdown(evaluator_path).encode())
    audit_relative = Path("12_POST_NATIVE_EVALUATION/01_REFERENCE_AUDIT/H7_REFERENCE_AUDIT.json")
    frame = validate_reporting_rotation()
    if not frame["passed"]:
        raise HartleyH7Error("Hartley reporting transform validation failed")
    audit = {
        "schema_version": "hartley.h7.reference_audit.v1",
        "terminal_status": TERMINAL,
        "contract_freeze_sha256": sha256_file(output / contract_freeze_relative),
        "reference_contract_frozen_before_open": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_used_for_declared_identity_only": True,
        "reference_relative_path": contract["reference_identity"]["relative_path"],
        "reference_declared_raw_lock_sha256": TRACE_DECLARED_SHA256,
        "reference_same_source": True,
        "reference_independent_ground_truth": False,
        "exact_evaluator_sha256": EVALUATOR_SHA256,
        "exact_evaluator_ordinary_absolute_rmse_path_called": False,
        "hartley_position_point": "GO2_BODY_IMU_ORIGIN_USED_BY_REPRODUCED_INEKF",
        "hartley_body_frame": "GO2_BODY_FLU",
        "hartley_reporting_transform": frame,
        "reference_position_point": "UNRESOLVED",
        "reference_attitude_body_frame": "UNRESOLVED",
        "reference_velocity_contract": "NOT_AVAILABLE",
        "reference_full_so3_contract": "NOT_AVAILABLE",
        "required_fixed_transform": "ABSENT_FROM_FROZEN_PROJECT_EVIDENCE",
        "project_0p03_0p03_m0p30_lever_used": False,
        "project_lever_role": "SOLVER_GNSS_MEASUREMENT_LEVER_ARM_NOT_EVALUATOR_TRANSFORM",
        "trajectory_error_used_to_infer_transform": False,
        "h5_input_and_native_freeze_audit": h5,
        "h6r_preservation_audit": h6r,
    }
    _write_json(output / audit_relative, audit)

    claim_relative = Path("11_REPORT/LSE01_HARTLEY_CLAIM_BOUNDARY.md")
    _write_exclusive(output / claim_relative, _claim_boundary().encode())
    status_relative = Path("11_REPORT/LSE01_FINAL_STATUS.json")
    status = {
        "schema_version": "hartley.h7.final_status.v1",
        "terminal_status": TERMINAL,
        "start_head": TASK_START_HEAD,
        "end_head": TASK_START_HEAD,
        "h6_original_blocker_preserved": True,
        "h6r_gauge_and_observability_preserved": True,
        "reference_contract_frozen_before_open": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "reference_same_source": True,
        "reference_independent_ground_truth": False,
        "relative_pose_metrics_complete": False,
        "relative_yaw_increment_complete": False,
        "gauge_aligned_descriptive_metrics_complete": False,
        "absolute_yaw_RMSE": None,
        "absolute_position_RMSE": None,
        "absolute_global_position_RMSE": None,
        "parameter_selection_performed": False,
        "metric_artifacts": _metric_absence(),
        "filter_rerun_count": 0,
        "h5_filter_rerun_count": 0,
        "h6_h6r_gauge_member_rerun_count": 0,
        "hartley_synthetic_validation_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
        "horizontal18_executed": False,
        "other_method_executed": False,
        "lse01_terminalized": True,
        "lse01_complete": False,
        "scratch_retention": "RETAIN_WHILE_G_UNHEALTHY",
        "storage_health": {
            **storage_health,
            "read_only_query_performed": True,
            "repair_invoked": False,
            "runtime_storage": "LINUX_LOCAL_EXT4_SCRATCH",
        },
        "git_identity": git,
    }
    _write_json(output / status_relative, status)

    report_relative = Path("11_REPORT/LSE01_H7_GAUGE_INVARIANT_RELATIVE_EVALUATION_REPORT.md")
    report = f"""# LSE01 H7 gauge-invariant relative evaluation report

Terminal: `{TERMINAL}`.

The H7 evaluation contract was frozen before reference access. All three access
counters remain zero, and the trace file was neither statted nor hashed. All
four frozen H5 branches, their 13-file native freezes, the H5 source/local-
publication/external-stage copies, H5 input cache, original H6 preservation,
and H6R PASS/publication evidence verified.

The Hartley output point/frame and reporting rotation are closed. The frozen
project evidence does not resolve the Fixposition trace physical point or BODY
frame relative to the Go2 body-IMU origin, and supplies no authorized fixed
transform. The exact evaluator also lacks reference velocity and a full SO(3)
contract. The physical-point gate therefore blocks before trace opening.

No metric CSV, scalar-yaw diagnostic, fixed gauge alignment, branch comparison,
or evaluator gauge test was created. Every requested metric is `NOT_EVALUATED`;
absolute yaw and global-position RMSE are not applicable and remain null.

No filter, H6/H6R gauge member, Hartley synthetic validation, EXT06,
HORIZONTAL18, other method, or Canonical-541 execution occurred.
"""
    _write_exclusive(output / report_relative, report.encode())
    final_report_relative = Path("11_REPORT/LSE01_FINAL_REPORT.md")
    final_report = f"""# LSE01 final report

LSE01 is terminalized but not scientifically complete at
`{TERMINAL}`. H0-H5 and H6R remain accepted; the immutable original H6 blocker
remains preserved and is scientifically superseded by H6R without deletion.

H7 stopped at the mandatory reference physical-point/body-frame gate with zero
reference rows read. Gauge-invariant and fixed-gauge metrics remain
`NOT_EVALUATED`. EXT06 remains unexecuted.
"""
    _write_exclusive(output / final_report_relative, final_report.encode())

    freeze_relative = Path("12_POST_NATIVE_EVALUATION/H7_EVALUATION_FREEZE.json")
    frozen_relatives = (
        contract_relative, contract_freeze_relative, point_relative, audit_relative,
        report_relative, claim_relative, final_report_relative, status_relative,
    )
    evaluation_freeze = {
        "schema_version": "hartley.h7.evaluation_freeze.v1",
        "terminal_status": TERMINAL,
        "files": {str(relative): _file_identity(output, relative) for relative in frozen_relatives},
        "metric_files_created": 0,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
    }
    _write_json(output / freeze_relative, evaluation_freeze)

    manifest_relative = Path("12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_PUBLICATION_MANIFEST.json")
    publish_relatives = (*frozen_relatives, freeze_relative)
    manifest = {
        "schema_version": "hartley.h7.publication_manifest.v1",
        "terminal_status": TERMINAL,
        "exclusive_create_required": True,
        "files": {str(relative): _file_identity(output, relative) for relative in publish_relatives},
    }
    _write_json(output / manifest_relative, manifest)
    publish_relatives = (*publish_relatives, manifest_relative)
    for relative in publish_relatives:
        source = output / relative
        destination = stage_root / relative
        _write_exclusive(destination, source.read_bytes())
    parity_rows = []
    for relative in publish_relatives:
        source_identity = _file_identity(output, relative)
        published_identity = _file_identity(stage_root, relative)
        parity_rows.append({
            "relative_path": str(relative),
            "source": source_identity,
            "published": published_identity,
            "bytes_equal": source_identity == published_identity,
        })
    if not all(row["bytes_equal"] for row in parity_rows):
        raise HartleyH7Error("H7 compact publication parity failure")
    parity_relative = Path("12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_PUBLICATION_PARITY.json")
    parity = {
        "schema_version": "hartley.h7.publication_parity.v1",
        "terminal_status": TERMINAL,
        "file_count": len(parity_rows),
        "all_published_bytes_equal": True,
        "files": parity_rows,
        "scratch_retained_while_G_unhealthy": True,
    }
    _write_json(output / parity_relative, parity)
    _write_exclusive(stage_root / parity_relative, (output / parity_relative).read_bytes())
    if _file_identity(output, parity_relative) != _file_identity(stage_root, parity_relative):
        raise HartleyH7Error("H7 parity control file mismatch")
    return {
        "terminal_status": TERMINAL,
        "scratch": str(scratch),
        "stage_root": str(stage_root),
        "contract_freeze_sha256": sha256_file(output / contract_freeze_relative),
        "evaluation_freeze_sha256": sha256_file(output / freeze_relative),
        "publication_manifest_sha256": sha256_file(output / manifest_relative),
        "publication_parity_sha256": sha256_file(output / parity_relative),
        "published_file_count_including_parity_control": len(parity_rows) + 1,
        "all_published_bytes_equal": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
        "lse01_terminalized": True,
        "lse01_complete": False,
    }


R1_RECOVERY_RELATIVE = Path("12_POST_NATIVE_EVALUATION/08_BLOCKER_PROVENANCE_RECOVERY")
R2_RECOVERY_RELATIVE = Path("12_POST_NATIVE_EVALUATION/09_PATH_ALIAS_RECOVERY")
EXPECTED_STAGE_SUFFIX = Path(
    "LegSA-GINS-project/clean_rebuild_202607/stages/"
    "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/07_LSE01_HARTLEY_CONTACT_INEKF"
)
R1_SCOPED_SOURCE_RELATIVES = (
    CONTRACT_RELATIVE,
    Path("src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7.py"),
    Path("scripts/paper_rebuild/evaluate_hartley_h7.py"),
    Path("tests/paper_rebuild/test_hartley_h7_contracts.py"),
)
ORIGINAL_H7_PARITY_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_PUBLICATION_PARITY.json"
)
ORIGINAL_H7_MANIFEST_RELATIVE = Path(
    "12_POST_NATIVE_EVALUATION/00_CONTRACTS/H7_PUBLICATION_MANIFEST.json"
)
H7R1_PARITY_RELATIVE = R1_RECOVERY_RELATIVE / "H7R1_PUBLICATION_PARITY.json"
H7R1_MANIFEST_RELATIVE = R1_RECOVERY_RELATIVE / "H7R1_PUBLICATION_MANIFEST.json"


def validate_no_tracked_machine_absolute_paths(repository: Path) -> dict[str, Any]:
    separator = chr(47)
    machine_roots = ("mnt", "home", "root", "tmp", "var", "opt", "usr")
    needles = tuple(separator + root + separator for root in machine_roots)
    violations: dict[str, list[str]] = {}
    for relative in R1_SCOPED_SOURCE_RELATIVES:
        text = (repository / relative).read_text()
        found = [needle for needle in needles if needle in text]
        if found:
            violations[str(relative)] = found
    if violations:
        raise HartleyH7Error(f"tracked machine-local absolute path literal: {violations}")
    return {
        "scoped_file_count": len(R1_SCOPED_SOURCE_RELATIVES),
        "machine_local_absolute_path_literal_count": 0,
        "repository_relative_paths_only": True,
    }


def _run_read_only(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "read_only": True,
    }


def collect_storage_health_read_only(scratch_parent: Path, stage_root: Path) -> dict[str, Any]:
    if not stage_root.is_dir():
        raise HartleyH7Error(f"external stage root is absent: {stage_root}")
    local = _run_read_only(["findmnt", "-J", "-T", str(scratch_parent)])
    external = _run_read_only(["findmnt", "-J", "-T", str(stage_root)])
    if any(record["returncode"] != 0 for record in (local, external)):
        raise HartleyH7Error("read-only findmnt command failed")
    local_value = json.loads(local["stdout"])["filesystems"][0]
    external_value = json.loads(external["stdout"])["filesystems"][0]
    mount_target = Path(external_value.get("target", ""))
    try:
        stage_below_mount = stage_root.relative_to(mount_target)
    except ValueError as error:
        raise HartleyH7Error("external stage is outside its resolved mount target") from error
    if stage_below_mount != EXPECTED_STAGE_SUFFIX:
        raise HartleyH7Error(f"external stage relative identity mismatch: {stage_below_mount}")
    source = str(external_value.get("source", ""))
    if len(source) < 2 or source[1] != ":" or source[0].upper() != "G":
        raise HartleyH7Error("H7 recovery external stage does not resolve to authorized G drive")
    drive_letter = source[0].upper()
    powershell_command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        f"$v=Get-Volume -DriveLetter {drive_letter}; [ordered]@{{"
        "DriveLetter=\"$($v.DriveLetter)\";FileSystem=\"$($v.FileSystem)\";"
        "HealthStatus=\"$($v.HealthStatus)\";"
        "OperationalStatus=\"$(($v.OperationalStatus -join ', '))\";"
        "Size=[int64]$v.Size;SizeRemaining=[int64]$v.SizeRemaining} | ConvertTo-Json -Compress",
    ]
    volume = _run_read_only(powershell_command)
    if volume["returncode"] != 0:
        raise HartleyH7Error("read-only storage command failed")
    volume_value = json.loads(volume["stdout"])
    if local_value.get("fstype") != "ext4":
        raise HartleyH7Error("H7R1 scratch parent is not ext4")
    if external_value.get("fstype") != "9p":
        raise HartleyH7Error("H7R1 external stage is not the mounted G: drvfs/9p target")
    required_volume = {
        "DriveLetter": "G",
        "FileSystem": "exFAT",
        "HealthStatus": "Warning",
        "OperationalStatus": "Full Repair Needed",
    }
    if any(volume_value.get(key) != value for key, value in required_volume.items()):
        raise HartleyH7Error(f"G volume health mismatch: {volume_value}")
    if any("Repair-Volume" in part for part in powershell_command):
        raise HartleyH7Error("repair command is forbidden")
    return {
        "schema_version": "hartley.h7r1.storage_health.v1",
        "scratch_parent": str(scratch_parent),
        "scratch_parent_findmnt": local,
        "scratch_parent_fstype": local_value["fstype"],
        "stage_root": str(stage_root),
        "stage_root_identity_validated": True,
        "external_findmnt": external,
        "external_mount_target": external_value["target"],
        "external_stage_relative_to_mount": str(stage_below_mount),
        "external_mount_source": external_value["source"],
        "external_mount_fstype": external_value["fstype"],
        "get_volume_G_read_only": volume,
        "volume": volume_value,
        "repair_command_invoked": False,
        "runtime_storage": "LINUX_LOCAL_EXT4_SCRATCH",
        "external_storage_health": "EXFAT_WARNING_FULL_REPAIR_NEEDED",
    }


def snapshot_original_h7(original_scratch: Path, stage_root: Path) -> dict[str, Any]:
    parity_path = original_scratch / ORIGINAL_H7_PARITY_RELATIVE
    parity = _load_json(parity_path)
    if not parity.get("all_published_bytes_equal") or parity.get("file_count") != 10:
        raise HartleyH7Error("original H7 parity evidence mismatch")
    relatives = [Path(row["relative_path"]) for row in parity["files"]]
    relatives.append(ORIGINAL_H7_PARITY_RELATIVE)
    files: dict[str, Any] = {}
    for relative in relatives:
        scratch_identity = _file_identity(original_scratch, relative)
        stage_identity = _file_identity(stage_root, relative)
        if scratch_identity != stage_identity:
            raise HartleyH7Error(f"original H7 scratch/stage mismatch: {relative}")
        files[str(relative)] = scratch_identity
    return {
        "original_h7_scratch": str(original_scratch),
        "file_count": len(files),
        "files": files,
        "publication_manifest_sha256": sha256_file(
            original_scratch / ORIGINAL_H7_MANIFEST_RELATIVE
        ),
        "publication_manifest_size": (
            original_scratch / ORIGINAL_H7_MANIFEST_RELATIVE
        ).stat().st_size,
        "publication_parity_sha256": sha256_file(parity_path),
        "publication_parity_size": parity_path.stat().st_size,
        "scratch_stage_hash_size_parity": True,
    }


def snapshot_h7r1(h7r1_scratch: Path, stage_root: Path) -> dict[str, Any]:
    parity_path = h7r1_scratch / H7R1_PARITY_RELATIVE
    parity = _load_json(parity_path)
    if not parity.get("all_published_bytes_equal") or parity.get("file_count") != 12:
        raise HartleyH7Error("H7R1 parity evidence mismatch")
    relatives = [Path(row["relative_path"]) for row in parity["files"]]
    relatives.append(H7R1_PARITY_RELATIVE)
    files: dict[str, Any] = {}
    for relative in relatives:
        scratch_identity = _file_identity(h7r1_scratch, relative)
        stage_identity = _file_identity(stage_root, relative)
        if scratch_identity != stage_identity:
            raise HartleyH7Error(f"H7R1 scratch/stage mismatch: {relative}")
        files[str(relative)] = scratch_identity
    return {
        "h7r1_scratch": str(h7r1_scratch),
        "file_count": len(files),
        "files": files,
        "publication_manifest_sha256": sha256_file(h7r1_scratch / H7R1_MANIFEST_RELATIVE),
        "publication_manifest_size": (h7r1_scratch / H7R1_MANIFEST_RELATIVE).stat().st_size,
        "publication_parity_sha256": sha256_file(parity_path),
        "publication_parity_size": parity_path.stat().st_size,
        "scratch_stage_hash_size_parity": True,
    }


def _r1_provenance(repository: Path, h5: dict[str, Any]) -> dict[str, Any]:
    scoped_sources = {
        str(relative): _file_identity(repository, relative)
        for relative in R1_SCOPED_SOURCE_RELATIVES
    }
    config_hash = scoped_sources[str(CONTRACT_RELATIVE)]["sha256"]
    return {
        "data_mode": h5["data_mode"],
        "raw_source_hashes": {
            "accepted_raw_full": {
                "sha256": h5["raw_full_sha256"],
                "source_evidence": "11_REPORT/LSE01_H5_STATUS.json:provider_raw_sha256",
            },
            "accepted_complete_prefix": {
                "sha256": h5["complete_prefix_sha256"],
                "source_evidence": "11_REPORT/LSE01_H5_STATUS.json:provider_complete_prefix_sha256",
            },
        },
        "provider_hashes": {
            "h5_input_cache": {
                "sha256": h5["input_cache_sha256"],
                "source_evidence": "08_BY2_NATIVE/00_PROVIDER/H5_INPUT_CACHE_MANIFEST.json:cache_sha256",
            },
            "h5_contact_event_ledger": {
                "sha256": h5["input_event_ledger_sha256"],
                "source_evidence": "08_BY2_NATIVE/00_PROVIDER/H5_INPUT_CACHE_MANIFEST.json:event_ledger_sha256",
            },
        },
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": h5["trace_used_online"],
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": h5["old_runtime_input_count"],
        "code_commit": TASK_START_HEAD,
        "config_hash": config_hash,
        "execution_code_committed": False,
        "dirty_or_precommit_scoped_execution": True,
        "scoped_h7_source_hashes": scoped_sources,
        "later_commit_mapping": "PENDING_SUPERVISOR_COMMIT_HASH_MAPPING",
    }


def materialize_blocker_provenance_recovery(
    repository: Path,
    scratch: Path,
    original_h7_scratch: Path,
    stage_root: Path,
    h5_scratch: Path,
    evaluator_path: Path,
) -> dict[str, Any]:
    git = verify_git_start(repository)
    if scratch.exists():
        raise HartleyH7Error(f"non-overwriting H7R1 scratch already exists: {scratch}")
    storage = collect_storage_health_read_only(scratch.parent, stage_root)
    original_before = snapshot_original_h7(original_h7_scratch, stage_root)
    if sha256_file(evaluator_path) != EVALUATOR_SHA256:
        raise HartleyH7Error("exact evaluator identity mismatch")
    h5 = verify_h5_inputs(stage_root, h5_scratch)
    h6r = verify_h6r_preservation(stage_root)
    provenance = _r1_provenance(repository, h5)
    contract_source = repository / CONTRACT_RELATIVE
    contract = yaml.safe_load(contract_source.read_text())
    if contract["reference_identity"]["local_path_config_opened"] is not False:
        raise HartleyH7Error("H7R1 local path config contract mismatch")
    if contract["reference_identity"]["reference_path_resolution"] != (
        "NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER"
    ):
        raise HartleyH7Error("H7R1 reference path resolution contract mismatch")
    scratch.mkdir()

    contract_relative = R1_RECOVERY_RELATIVE / "H7R1_EVALUATION_CONTRACT.yaml"
    point_relative = R1_RECOVERY_RELATIVE / "H7R1_REFERENCE_AND_POINT_IDENTITY_CONTRACT.md"
    _write_exclusive(scratch / contract_relative, contract_source.read_bytes())
    point_text = _point_contract_markdown(evaluator_path) + """

## H7R1 administrative recovery

H7R1 is an additive provenance recovery, not new science or reference
evaluation. The ignored local path configuration was not opened and reference
path resolution was `NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER`.
The original H7 scratch and published files remain immutable predecessors.
"""
    _write_exclusive(scratch / point_relative, point_text.encode())
    contract_freeze_relative = R1_RECOVERY_RELATIVE / "H7R1_CONTRACT_FREEZE.json"
    contract_freeze = {
        "schema_version": "hartley.h7r1.contract_freeze.v1",
        "contracts_written_before_freeze": [str(contract_relative), str(point_relative)],
        "files": {
            str(contract_relative): _file_identity(scratch, contract_relative),
            str(point_relative): _file_identity(scratch, point_relative),
        },
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "reference_path_resolution": "NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER",
        "freeze_completed_before_audit_status_or_report": True,
    }
    _write_json(scratch / contract_freeze_relative, contract_freeze)

    storage_relative = R1_RECOVERY_RELATIVE / "H7R1_STORAGE_HEALTH_READ_ONLY.json"
    _write_json(scratch / storage_relative, storage)
    audit_relative = R1_RECOVERY_RELATIVE / "H7R1_REFERENCE_AUDIT.json"
    frame = validate_reporting_rotation()
    if not frame["passed"]:
        raise HartleyH7Error("Hartley reporting transform validation failed")
    audit = {
        "schema_version": "hartley.h7r1.reference_audit.v1",
        "terminal_status": TERMINAL,
        "administrative_recovery_not_new_science": True,
        "contract_freeze_sha256": sha256_file(scratch / contract_freeze_relative),
        "both_contracts_hash_and_size_frozen_before_audit": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "reference_path_resolution": "NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER",
        "reference_same_source": True,
        "reference_independent_ground_truth": False,
        "exact_evaluator_sha256": EVALUATOR_SHA256,
        "exact_evaluator_ordinary_absolute_rmse_path_called": False,
        "hartley_position_point": "GO2_BODY_IMU_ORIGIN_USED_BY_REPRODUCED_INEKF",
        "hartley_body_frame": "GO2_BODY_FLU",
        "hartley_reporting_transform": frame,
        "reference_position_point": "UNRESOLVED",
        "reference_attitude_body_frame": "UNRESOLVED",
        "reference_velocity_contract": "NOT_AVAILABLE",
        "reference_full_so3_contract": "NOT_AVAILABLE",
        "required_fixed_transform": "ABSENT_FROM_FROZEN_PROJECT_EVIDENCE",
        "project_0p03_0p03_m0p30_lever_used": False,
        "trajectory_error_used_to_infer_transform": False,
        "h5_input_and_native_freeze_audit": h5,
        "h6r_preservation_audit": h6r,
        "original_h7_predecessor": original_before,
        "runtime_provenance": provenance,
    }
    _write_json(scratch / audit_relative, audit)

    status_relative = Path("11_REPORT/LSE01_H7R1_FINAL_STATUS.json")
    status = {
        "schema_version": "hartley.h7r1.final_status.v1",
        "terminal_status": TERMINAL,
        "recovery_status": "H7R1_BLOCKER_PROVENANCE_RECOVERY_COMPLETE",
        "administrative_recovery_not_new_science": True,
        "original_h7_preserved": True,
        "start_head": TASK_START_HEAD,
        "end_head": TASK_START_HEAD,
        "h6_original_blocker_preserved": True,
        "h6r_gauge_and_observability_preserved": True,
        "reference_contract_frozen_before_open": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "reference_path_resolution": "NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER",
        "reference_same_source": True,
        "reference_independent_ground_truth": False,
        "relative_pose_metrics_complete": False,
        "relative_yaw_increment_complete": False,
        "gauge_aligned_descriptive_metrics_complete": False,
        "absolute_yaw_RMSE": None,
        "absolute_position_RMSE": None,
        "absolute_global_position_RMSE": None,
        "parameter_selection_performed": False,
        "metric_artifacts": _metric_absence(),
        "metric_files_created": 0,
        "filter_rerun_count": 0,
        "h5_filter_rerun_count": 0,
        "h6_h6r_gauge_member_rerun_count": 0,
        "hartley_synthetic_validation_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
        "horizontal18_executed": False,
        "other_method_executed": False,
        "lse01_terminalized": True,
        "lse01_complete": False,
        "storage_health_evidence": str(storage_relative),
        "scratch_retention": "RETAIN_WHILE_G_UNHEALTHY",
        "runtime_provenance": provenance,
        "h5_native_freezes": h5["native_freezes"],
        "original_h7_predecessor_manifest_sha256": original_before["publication_manifest_sha256"],
        "original_h7_predecessor_parity_sha256": original_before["publication_parity_sha256"],
        "validation_logs": {
            "directory": "99_VALIDATION",
            "state": "WRITTEN_AFTER_TERMINAL_MATERIALIZATION_AND_RETAINED_LOCALLY",
        },
        "git_identity": git,
    }
    _write_json(scratch / status_relative, status)

    report_relative = Path("11_REPORT/LSE01_H7R1_BLOCKER_PROVENANCE_RECOVERY_REPORT.md")
    report = f"""# LSE01 H7R1 blocker provenance recovery

Terminal remains `{TERMINAL}`. H7R1 is additive administrative provenance
recovery, not new science and not a reference evaluation.

Both R1 contract files were written first and then hash/size-locked by the R1
contract freeze before any audit, status, or report. Reference/trace access and
row counters remain zero. The ignored local path configuration was not opened,
and reference path resolution was not performed.

The final status/evaluation freeze contain raw/provider lineage, all required
forbidden-input flags, dirty/precommit scoped-source hashes, four durable native
freeze identities, self-contained read-only storage command evidence, and the
immutable original H7 predecessor manifest/parity identities.

No metric file, filter run, EXT06, HORIZONTAL18, other method, or Canonical-541
execution was created.
"""
    _write_exclusive(scratch / report_relative, report.encode())
    final_report_relative = Path("11_REPORT/LSE01_H7R1_FINAL_REPORT.md")
    _write_exclusive(scratch / final_report_relative, (
        "# LSE01 H7R1 final report\n\n"
        f"H7R1 closes the provenance deficiencies while preserving `{TERMINAL}`. "
        "The original H7 attempt remains immutable. LSE01 is terminalized but not "
        "scientifically complete, and EXT06 remains unexecuted.\n"
    ).encode())
    claim_relative = Path("11_REPORT/LSE01_H7R1_HARTLEY_CLAIM_BOUNDARY.md")
    _write_exclusive(scratch / claim_relative, _claim_boundary().encode())

    freeze_relative = R1_RECOVERY_RELATIVE / "H7R1_EVALUATION_FREEZE.json"
    core_relatives = (
        contract_relative, point_relative, contract_freeze_relative, storage_relative,
        audit_relative, status_relative, report_relative, final_report_relative, claim_relative,
    )
    evaluation_freeze = {
        "schema_version": "hartley.h7r1.evaluation_freeze.v1",
        "terminal_status": TERMINAL,
        "administrative_recovery_not_new_science": True,
        "files": {str(relative): _file_identity(scratch, relative) for relative in core_relatives},
        "runtime_provenance": provenance,
        "h5_native_freezes": h5["native_freezes"],
        "original_h7_predecessor": original_before,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "metric_files_created": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
    }
    _write_json(scratch / freeze_relative, evaluation_freeze)
    publish_relatives = (*core_relatives, freeze_relative)
    for relative in publish_relatives:
        _write_exclusive(stage_root / relative, (scratch / relative).read_bytes())

    original_after = snapshot_original_h7(original_h7_scratch, stage_root)
    if original_before != original_after:
        raise HartleyH7Error("original H7 changed during H7R1 publication")
    preservation_relative = R1_RECOVERY_RELATIVE / "H7R1_ORIGINAL_H7_PRESERVATION.json"
    preservation = {
        "schema_version": "hartley.h7r1.original_preservation.v1",
        "original_before": original_before,
        "original_after": original_after,
        "unchanged_before_after": True,
        "original_h7_scratch_modified": False,
        "original_h7_published_files_modified": False,
    }
    _write_json(scratch / preservation_relative, preservation)
    _write_exclusive(stage_root / preservation_relative, (scratch / preservation_relative).read_bytes())
    publish_relatives = (*publish_relatives, preservation_relative)

    manifest_relative = R1_RECOVERY_RELATIVE / "H7R1_PUBLICATION_MANIFEST.json"
    manifest = {
        "schema_version": "hartley.h7r1.publication_manifest.v1",
        "terminal_status": TERMINAL,
        "exclusive_create_required": True,
        "original_h7_predecessor_preserved": True,
        "files": {str(relative): _file_identity(scratch, relative) for relative in publish_relatives},
    }
    _write_json(scratch / manifest_relative, manifest)
    _write_exclusive(stage_root / manifest_relative, (scratch / manifest_relative).read_bytes())
    publish_relatives = (*publish_relatives, manifest_relative)
    parity_rows = []
    for relative in publish_relatives:
        source_identity = _file_identity(scratch, relative)
        published_identity = _file_identity(stage_root, relative)
        parity_rows.append({
            "relative_path": str(relative),
            "source": source_identity,
            "published": published_identity,
            "bytes_equal": source_identity == published_identity,
        })
    if not all(row["bytes_equal"] for row in parity_rows):
        raise HartleyH7Error("H7R1 publication parity failure")
    parity_relative = R1_RECOVERY_RELATIVE / "H7R1_PUBLICATION_PARITY.json"
    parity = {
        "schema_version": "hartley.h7r1.publication_parity.v1",
        "terminal_status": TERMINAL,
        "file_count": len(parity_rows),
        "all_published_bytes_equal": True,
        "files": parity_rows,
        "original_h7_preserved_unchanged": True,
        "scratch_retained_while_G_unhealthy": True,
    }
    _write_json(scratch / parity_relative, parity)
    _write_exclusive(stage_root / parity_relative, (scratch / parity_relative).read_bytes())
    if _file_identity(scratch, parity_relative) != _file_identity(stage_root, parity_relative):
        raise HartleyH7Error("H7R1 parity control mismatch")
    return {
        "terminal_status": TERMINAL,
        "recovery_status": "H7R1_BLOCKER_PROVENANCE_RECOVERY_COMPLETE",
        "scratch": str(scratch),
        "stage_root": str(stage_root),
        "contract_freeze_sha256": sha256_file(scratch / contract_freeze_relative),
        "evaluation_freeze_sha256": sha256_file(scratch / freeze_relative),
        "publication_manifest_sha256": sha256_file(scratch / manifest_relative),
        "publication_parity_sha256": sha256_file(scratch / parity_relative),
        "published_file_count_including_parity_control": len(parity_rows) + 1,
        "all_published_bytes_equal": True,
        "original_h7_preserved_unchanged": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "metric_files_created": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
        "lse01_complete": False,
    }


def materialize_path_alias_recovery(
    repository: Path,
    scratch: Path,
    original_h7_scratch: Path,
    h7r1_scratch: Path,
    stage_root: Path,
    h5_scratch: Path,
    evaluator_path: Path,
) -> dict[str, Any]:
    git = verify_git_start(repository)
    path_alias_audit = validate_no_tracked_machine_absolute_paths(repository)
    if scratch.exists():
        raise HartleyH7Error(f"non-overwriting H7R2 scratch already exists: {scratch}")
    storage = collect_storage_health_read_only(scratch.parent, stage_root)
    h7_before = snapshot_original_h7(original_h7_scratch, stage_root)
    h7r1_before = snapshot_h7r1(h7r1_scratch, stage_root)
    if sha256_file(evaluator_path) != EVALUATOR_SHA256:
        raise HartleyH7Error("exact evaluator identity mismatch")
    h5 = verify_h5_inputs(stage_root, h5_scratch)
    h6r = verify_h6r_preservation(stage_root)
    provenance = _r1_provenance(repository, h5)
    contract_source = repository / CONTRACT_RELATIVE
    contract = yaml.safe_load(contract_source.read_text())
    if contract["reference_identity"]["local_path_config_opened"] is not False:
        raise HartleyH7Error("H7R2 local path config contract mismatch")
    scratch.mkdir()

    contract_relative = R2_RECOVERY_RELATIVE / "H7R2_EVALUATION_CONTRACT.yaml"
    point_relative = R2_RECOVERY_RELATIVE / "H7R2_REFERENCE_AND_POINT_IDENTITY_CONTRACT.md"
    _write_exclusive(scratch / contract_relative, contract_source.read_bytes())
    point_text = _point_contract_markdown(evaluator_path) + """

## H7R2 administrative path-alias recovery

H7R2 is additive path/provenance recovery, not new science or reference
evaluation. Storage aliases are resolved only from read-only mount evidence at
runtime. Tracked H7 sources contain no machine-local absolute path literal.
The ignored local path configuration remains unopened and reference path
resolution remains `NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER`.
"""
    _write_exclusive(scratch / point_relative, point_text.encode())
    contract_freeze_relative = R2_RECOVERY_RELATIVE / "H7R2_CONTRACT_FREEZE.json"
    contract_freeze = {
        "schema_version": "hartley.h7r2.contract_freeze.v1",
        "contracts_written_before_freeze": [str(contract_relative), str(point_relative)],
        "files": {
            str(contract_relative): _file_identity(scratch, contract_relative),
            str(point_relative): _file_identity(scratch, point_relative),
        },
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "freeze_completed_before_audit_status_or_report": True,
    }
    _write_json(scratch / contract_freeze_relative, contract_freeze)

    storage_relative = R2_RECOVERY_RELATIVE / "H7R2_STORAGE_HEALTH_READ_ONLY.json"
    _write_json(scratch / storage_relative, storage)
    audit_relative = R2_RECOVERY_RELATIVE / "H7R2_REFERENCE_AUDIT.json"
    frame = validate_reporting_rotation()
    if not frame["passed"]:
        raise HartleyH7Error("Hartley reporting transform validation failed")
    audit = {
        "schema_version": "hartley.h7r2.reference_audit.v1",
        "terminal_status": TERMINAL,
        "administrative_path_alias_recovery_not_new_science": True,
        "contract_freeze_sha256": sha256_file(scratch / contract_freeze_relative),
        "both_contracts_hash_and_size_frozen_before_audit": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "reference_path_resolution": "NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER",
        "reference_same_source": True,
        "reference_independent_ground_truth": False,
        "exact_evaluator_sha256": EVALUATOR_SHA256,
        "exact_evaluator_ordinary_absolute_rmse_path_called": False,
        "hartley_position_point": "GO2_BODY_IMU_ORIGIN_USED_BY_REPRODUCED_INEKF",
        "hartley_body_frame": "GO2_BODY_FLU",
        "hartley_reporting_transform": frame,
        "reference_position_point": "UNRESOLVED",
        "reference_attitude_body_frame": "UNRESOLVED",
        "reference_velocity_contract": "NOT_AVAILABLE",
        "reference_full_so3_contract": "NOT_AVAILABLE",
        "required_fixed_transform": "ABSENT_FROM_FROZEN_PROJECT_EVIDENCE",
        "trajectory_error_used_to_infer_transform": False,
        "path_alias_audit": path_alias_audit,
        "h5_input_and_native_freeze_audit": h5,
        "h6r_preservation_audit": h6r,
        "h7_predecessor": h7_before,
        "h7r1_predecessor": h7r1_before,
        "runtime_provenance": provenance,
    }
    _write_json(scratch / audit_relative, audit)

    status_relative = Path("11_REPORT/LSE01_H7R2_FINAL_STATUS.json")
    status = {
        "schema_version": "hartley.h7r2.final_status.v1",
        "terminal_status": TERMINAL,
        "recovery_status": "H7R2_PATH_ALIAS_RECOVERY_COMPLETE",
        "administrative_path_alias_recovery_not_new_science": True,
        "h7_preserved": True,
        "h7r1_preserved": True,
        "start_head": TASK_START_HEAD,
        "end_head": TASK_START_HEAD,
        "h6_original_blocker_preserved": True,
        "h6r_gauge_and_observability_preserved": True,
        "reference_contract_frozen_before_open": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "reference_path_resolution": "NOT_PERFORMED_DUE_TO_PRE_REFERENCE_POINT_FRAME_BLOCKER",
        "reference_same_source": True,
        "reference_independent_ground_truth": False,
        "relative_pose_metrics_complete": False,
        "relative_yaw_increment_complete": False,
        "gauge_aligned_descriptive_metrics_complete": False,
        "absolute_yaw_RMSE": None,
        "absolute_position_RMSE": None,
        "absolute_global_position_RMSE": None,
        "parameter_selection_performed": False,
        "metric_artifacts": _metric_absence(),
        "metric_files_created": 0,
        "filter_rerun_count": 0,
        "h5_filter_rerun_count": 0,
        "h6_h6r_gauge_member_rerun_count": 0,
        "hartley_synthetic_validation_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
        "horizontal18_executed": False,
        "other_method_executed": False,
        "lse01_terminalized": True,
        "lse01_complete": False,
        "storage_health_evidence": str(storage_relative),
        "scratch_retention": "RETAIN_WHILE_G_UNHEALTHY",
        "path_alias_audit": path_alias_audit,
        "runtime_provenance": provenance,
        "h5_native_freezes": h5["native_freezes"],
        "h7_predecessor_manifest_sha256": h7_before["publication_manifest_sha256"],
        "h7_predecessor_parity_sha256": h7_before["publication_parity_sha256"],
        "h7r1_predecessor_manifest_sha256": h7r1_before["publication_manifest_sha256"],
        "h7r1_predecessor_parity_sha256": h7r1_before["publication_parity_sha256"],
        "validation_logs": {
            "directory": "99_VALIDATION",
            "state": "WRITTEN_AFTER_TERMINAL_MATERIALIZATION_AND_RETAINED_LOCALLY",
        },
        "git_identity": git,
    }
    _write_json(scratch / status_relative, status)

    report_relative = Path("11_REPORT/LSE01_H7R2_PATH_ALIAS_RECOVERY_REPORT.md")
    report = f"""# LSE01 H7R2 path-alias recovery

Terminal remains `{TERMINAL}`. H7R2 is administrative path/provenance recovery,
not new science and not a reference evaluation.

The stage mount target and source were obtained from read-only `findmnt` output.
The configured stage was validated by its repository-relative suffix below that
runtime mount target, with 9p and authorized G-drive checks retained. The drive
letter for the read-only volume query was derived from the mount source.

All four tracked H7 files passed the no-machine-local-absolute-path audit. The
legacy original H7 CLI materializer is disabled; this H7R2 route is the only
entrypoint. H7 and H7R1 predecessors remain byte-identical before and after.
"""
    _write_exclusive(scratch / report_relative, report.encode())
    final_report_relative = Path("11_REPORT/LSE01_H7R2_FINAL_REPORT.md")
    _write_exclusive(scratch / final_report_relative, (
        "# LSE01 H7R2 final report\n\n"
        f"H7R2 closes tracked path-alias provenance while preserving `{TERMINAL}`. "
        "H7 and H7R1 remain immutable; EXT06 remains unexecuted.\n"
    ).encode())
    claim_relative = Path("11_REPORT/LSE01_H7R2_HARTLEY_CLAIM_BOUNDARY.md")
    _write_exclusive(scratch / claim_relative, _claim_boundary().encode())

    freeze_relative = R2_RECOVERY_RELATIVE / "H7R2_EVALUATION_FREEZE.json"
    core_relatives = (
        contract_relative, point_relative, contract_freeze_relative, storage_relative,
        audit_relative, status_relative, report_relative, final_report_relative, claim_relative,
    )
    evaluation_freeze = {
        "schema_version": "hartley.h7r2.evaluation_freeze.v1",
        "terminal_status": TERMINAL,
        "administrative_path_alias_recovery_not_new_science": True,
        "files": {str(relative): _file_identity(scratch, relative) for relative in core_relatives},
        "path_alias_audit": path_alias_audit,
        "runtime_provenance": provenance,
        "h5_native_freezes": h5["native_freezes"],
        "h7_predecessor": h7_before,
        "h7r1_predecessor": h7r1_before,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "trace_file_statted_or_hashed": False,
        "local_path_config_opened": False,
        "metric_files_created": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
    }
    _write_json(scratch / freeze_relative, evaluation_freeze)
    publish_relatives = (*core_relatives, freeze_relative)
    for relative in publish_relatives:
        _write_exclusive(stage_root / relative, (scratch / relative).read_bytes())

    h7_after = snapshot_original_h7(original_h7_scratch, stage_root)
    h7r1_after = snapshot_h7r1(h7r1_scratch, stage_root)
    if h7_before != h7_after or h7r1_before != h7r1_after:
        raise HartleyH7Error("H7 or H7R1 changed during H7R2 publication")
    preservation_relative = R2_RECOVERY_RELATIVE / "H7R2_PREDECESSOR_PRESERVATION.json"
    preservation = {
        "schema_version": "hartley.h7r2.predecessor_preservation.v1",
        "h7_before": h7_before,
        "h7_after": h7_after,
        "h7r1_before": h7r1_before,
        "h7r1_after": h7r1_after,
        "h7_unchanged_before_after": True,
        "h7r1_unchanged_before_after": True,
        "predecessor_scratch_or_stage_modified": False,
    }
    _write_json(scratch / preservation_relative, preservation)
    _write_exclusive(stage_root / preservation_relative, (scratch / preservation_relative).read_bytes())
    publish_relatives = (*publish_relatives, preservation_relative)

    manifest_relative = R2_RECOVERY_RELATIVE / "H7R2_PUBLICATION_MANIFEST.json"
    manifest = {
        "schema_version": "hartley.h7r2.publication_manifest.v1",
        "terminal_status": TERMINAL,
        "exclusive_create_required": True,
        "h7_and_h7r1_predecessors_preserved": True,
        "files": {str(relative): _file_identity(scratch, relative) for relative in publish_relatives},
    }
    _write_json(scratch / manifest_relative, manifest)
    _write_exclusive(stage_root / manifest_relative, (scratch / manifest_relative).read_bytes())
    publish_relatives = (*publish_relatives, manifest_relative)
    parity_rows = []
    for relative in publish_relatives:
        source_identity = _file_identity(scratch, relative)
        published_identity = _file_identity(stage_root, relative)
        parity_rows.append({
            "relative_path": str(relative),
            "source": source_identity,
            "published": published_identity,
            "bytes_equal": source_identity == published_identity,
        })
    if not all(row["bytes_equal"] for row in parity_rows):
        raise HartleyH7Error("H7R2 publication parity failure")
    parity_relative = R2_RECOVERY_RELATIVE / "H7R2_PUBLICATION_PARITY.json"
    parity = {
        "schema_version": "hartley.h7r2.publication_parity.v1",
        "terminal_status": TERMINAL,
        "file_count": len(parity_rows),
        "all_published_bytes_equal": True,
        "files": parity_rows,
        "h7_and_h7r1_preserved_unchanged": True,
        "scratch_retained_while_G_unhealthy": True,
    }
    _write_json(scratch / parity_relative, parity)
    _write_exclusive(stage_root / parity_relative, (scratch / parity_relative).read_bytes())
    if _file_identity(scratch, parity_relative) != _file_identity(stage_root, parity_relative):
        raise HartleyH7Error("H7R2 parity control mismatch")
    return {
        "terminal_status": TERMINAL,
        "recovery_status": "H7R2_PATH_ALIAS_RECOVERY_COMPLETE",
        "scratch": str(scratch),
        "stage_root": str(stage_root),
        "contract_freeze_sha256": sha256_file(scratch / contract_freeze_relative),
        "evaluation_freeze_sha256": sha256_file(scratch / freeze_relative),
        "publication_manifest_sha256": sha256_file(scratch / manifest_relative),
        "publication_parity_sha256": sha256_file(scratch / parity_relative),
        "published_file_count_including_parity_control": len(parity_rows) + 1,
        "all_published_bytes_equal": True,
        "h7_and_h7r1_preserved_unchanged": True,
        "tracked_machine_local_absolute_path_literal_count": 0,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "reference_rows_read": 0,
        "metric_files_created": 0,
        "filter_rerun_count": 0,
        "ext06_executed": False,
        "canonical541_executed": False,
        "lse01_complete": False,
    }
