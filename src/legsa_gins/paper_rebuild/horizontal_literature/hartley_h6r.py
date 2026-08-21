"""Non-overwriting Hartley H6 recovery using authoritative float64 contact evidence.

This module deliberately reuses the frozen H6 state, covariance, innovation and
observability mathematics.  Its only native-run change is an additional packed
binary evidence stream; ``CONTACT_STATE.csv`` remains the compatibility stream.
No reference, trace, GNSS, other-method, EXT06 or H7 reader exists here.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from . import hartley_h6 as h6


TASK_START_HEAD = "fbf771b3a43afcc11bc85596efc422a0cd7b9046"
TASK_START_DIRTY_OR_PRECOMMIT = True
METHOD_ID = h6.METHOD_ID
BACKEND_ID = h6.BACKEND_ID
PROCESS_PROFILE = "GO2_IMU_ALLAN_90MIN_RECOVERED_V1"
STATE_ROWS = 63_277
CONTACT_TOLERANCE_M = 0.0005
TOLERANCE_REGISTRY_SHA256 = "2c8ea39f828b9e3ef7433d6f2c7e01b407a927e0603612a3d7a606a596e53395"
WINDOW_SELECTION_SHA256 = "8c7f82f8df888833b088308c5e82798d70b4559ab76184b3d0c7d80912274578"
WINDOW_FREEZE_SHA256 = "34640a4f558ba574d4073254529d1b20ec7b2e32a9d8e1e99722bd61d5320e9b"
OLD_REPRODUCTION_TOLERANCE_M = 2.0e-15
THREAD_KEYS = h6.THREAD_KEYS
LEGS = h6.LEGS

YAW_MEMBERS: tuple[tuple[str, float, str], ...] = (
    ("H6R_YAW_M150", -150.0, "01_YAW_M150"),
    ("H6R_YAW_M100", -100.0, "02_YAW_M100"),
    ("H6R_YAW_M050", -50.0, "03_YAW_M050"),
    ("H6R_YAW_000", 0.0, "04_YAW_000"),
    ("H6R_YAW_P050", 50.0, "05_YAW_P050"),
    ("H6R_YAW_P100", 100.0, "06_YAW_P100"),
    ("H6R_YAW_P150", 150.0, "07_YAW_P150"),
)
YAW_BY_RUN_ID = {run_id: yaw for run_id, yaw, _ in YAW_MEMBERS}
DIRECTORY_BY_RUN_ID = {run_id: directory for run_id, _, directory in YAW_MEMBERS}
OLD_RUN_ID = {run_id: run_id.replace("H6R_", "H6_") for run_id, _, _ in YAW_MEMBERS}
OLD_RUN_ID["H6R_YAW_000"] = "H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM"
EXPECTED_OLD_MAXIMA = {
    "H6R_YAW_M150": 0.000528077325202676,
    "H6R_YAW_M100": 0.000923046274946653,
    "H6R_YAW_M050": 0.000559717674079685,
    "H6R_YAW_P050": 0.000541568944548006,
    "H6R_YAW_P100": 0.000814567299539196,
    "H6R_YAW_P150": 0.000555922436068516,
}
BLOCKERS = {
    "zero": "BLOCKED_LSE01_H6R_ZERO_DEGREE_PARITY_FAILURE",
    "old": "BLOCKED_LSE01_H6R_OLD_FORMAT_BLOCKER_NOT_REPRODUCED",
    "contact": "BLOCKED_LSE01_H6R_FULL_PRECISION_CONTACT_FAILURE",
    "ideal": "BLOCKED_LSE01_H6R_IDEAL_NULLSPACE_FAILURE",
    "gauge": "BLOCKED_LSE01_H6R_KNOWN_GAUGE_FAILURE",
    "storage": "BLOCKED_LSE01_H6R_STORAGE_UNSAFE_AND_NO_LOCAL_SCRATCH",
}
PASS_TERMINAL = "PASS_LSE01_H6R_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED"
APPROVED_CHANGED_PATHS = (
    "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6R_EXECUTION_CONTRACT.yaml",
    "scripts/paper_rebuild/run_hartley_h6r.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6r.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp",
    "tests/paper_rebuild/test_hartley_h6r_backend.py",
    "tests/paper_rebuild/test_hartley_h6r_contracts.py",
)
CORE_OUTPUT_RELATIVES = (
    "09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT/08_PRECISION_RECOVERY/H6R_CONTACT_SERIALIZATION_FORENSIC_REPORT.md",
    "09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT/08_PRECISION_RECOVERY/H6R_CONTACT_SERIALIZATION_FORENSIC.json",
    "09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT/08_PRECISION_RECOVERY/OLD_FORMAT_QUANTIZATION_REPRODUCTION.csv",
    "09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT/08_PRECISION_RECOVERY/FULL_PRECISION_CONTACT_EQUIVALENCE_EPOCH_METRICS.csv",
    "09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT/08_PRECISION_RECOVERY/FULL_PRECISION_CONTACT_EQUIVALENCE_SUMMARY.csv",
    "09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT/09_EQUIVALENCE/H6R_GAUGE_EQUIVALENCE_SUMMARY.csv",
    "10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_SINGULAR_VALUES_R1.csv",
    "10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_RANK_SENSITIVITY_R1.csv",
    "10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY_R1.json",
    "10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_PRINCIPAL_ANGLES_R1.csv",
    "10_OBSERVABILITY_R1/02_BIAS_AUGMENTED/BIAS_AUGMENTED_WEAK_DIRECTION_SUMMARY_R1.csv",
    "10_OBSERVABILITY_R1/03_NIS_AND_COVARIANCE/TOPOLOGY_CONDITIONED_NIS_SUMMARY_R1.csv",
    "10_OBSERVABILITY_R1/03_NIS_AND_COVARIANCE/TOPOLOGY_CONDITIONED_INNOVATION_SUMMARY_R1.csv",
    "10_OBSERVABILITY_R1/03_NIS_AND_COVARIANCE/GAUGE_COVARIANCE_CONSISTENCY_R1.csv",
)

RAW_HEADER = struct.Struct("<16sIIIQ4i12x")
RAW_RECORD = struct.Struct("<qq4B4x12d")
RAW_MAGIC = b"LEGS_H6R_F64"


class HartleyH6RError(RuntimeError):
    """A preregistered H6R gate failed."""


def sha256_file(path: Path) -> str:
    return h6.sha256_file(path)


def exclusive_json(path: Path, payload: Any) -> str:
    return h6.exclusive_json(path, payload)


def exclusive_csv(path: Path, rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> str:
    return h6.exclusive_csv_stream(path, rows, columns)


def _analysis_root(scratch: Path) -> Path:
    return scratch / "03_ANALYSIS"


def _gauge_root(scratch: Path) -> Path:
    return _analysis_root(scratch) / "09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT"


def _observability_root(scratch: Path) -> Path:
    return _analysis_root(scratch) / "10_OBSERVABILITY_R1"


def _member_root(scratch: Path, run_id: str) -> Path:
    return _gauge_root(scratch) / DIRECTORY_BY_RUN_ID[run_id]


def _require_new_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def _load_required_pass(path: Path, required: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not path.is_file():
        raise HartleyH6RError(f"{label} PASS marker absent")
    payload = json.loads(path.read_text())
    mismatch = {key: (payload.get(key), value) for key, value in required.items()
                if payload.get(key) != value}
    if mismatch:
        raise HartleyH6RError(f"{label} PASS marker mismatch: {mismatch}")
    return payload


def _write_gate_marker(scratch: Path, name: str, payload: Mapping[str, Any]) -> None:
    exclusive_json(scratch / "00_ADMIN" / name, dict(payload))


def _core_output_identities(scratch: Path, *, include_reports: bool = False) -> dict[str, dict[str, Any]]:
    relatives = list(CORE_OUTPUT_RELATIVES)
    if include_reports:
        relatives.extend(("11_REPORT/LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md",
                          "11_REPORT/LSE01_H6R_STATUS.json"))
    analysis = _analysis_root(scratch)
    missing = [relative for relative in relatives if not (analysis / relative).is_file()]
    if missing:
        raise HartleyH6RError(f"mandatory H6R core output absent: {missing}")
    return {relative: {"sha256": sha256_file(analysis / relative),
                       "size": (analysis / relative).stat().st_size}
            for relative in relatives}


def _require_ext4(path: Path) -> None:
    target = path if path.exists() else path.parent
    completed = subprocess.run(["findmnt", "-n", "-o", "FSTYPE", "--target", str(target)],
                               check=False, text=True, stdout=subprocess.PIPE)
    if completed.returncode or completed.stdout.strip() != "ext4":
        raise HartleyH6RError(BLOCKERS["storage"])


def _scratch_from_artifact(path: Path) -> Path | None:
    for parent in path.resolve().parents:
        if (parent / "00_ADMIN").is_dir() and (parent / "03_ANALYSIS").is_dir():
            return parent
    return None


def _record_contact_npz_open(path: Path) -> None:
    scratch = _scratch_from_artifact(path)
    if scratch is None:
        return
    freeze = _gauge_root(scratch) / "08_PRECISION_RECOVERY/OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json"
    _load_required_pass(freeze, {"old_format_blocker_reproduced": True}, "old-format reproduction")
    ledger = scratch / "00_ADMIN/H6R_CONTACT_NPZ_ACCESS_LEDGER.jsonl"
    prior = ledger.read_text().splitlines() if ledger.exists() else []
    record = {"sequence": len(prior) + 1, "role": str(path.relative_to(scratch)),
              "old_format_freeze_sha256": sha256_file(freeze),
              "npz_sha256_after_old_format_freeze": sha256_file(path)}
    descriptor = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush(); os.fsync(handle.fileno())


def _scoped_source_manifest(repository: Path) -> tuple[str, str, dict[str, str]]:
    relative_paths = (
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/CMakeLists.txt",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/include/hartley_inekf/backend.hpp",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/src/backend.cpp",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6r.py",
        "scripts/paper_rebuild/run_hartley_h6r.py",
        "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6R_EXECUTION_CONTRACT.yaml",
        "tests/paper_rebuild/test_hartley_h6r_backend.py",
        "tests/paper_rebuild/test_hartley_h6r_contracts.py",
    )
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True,
                               text=True, stdout=subprocess.PIPE)
    code_commit = completed.stdout.strip()
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", TASK_START_HEAD, code_commit],
                              cwd=repository, check=False)
    if ancestor.returncode != 0:
        raise HartleyH6RError("H6R task-start commit is not an ancestor of execution commit")
    identities: dict[str, str] = {}
    for relative in relative_paths:
        worktree_bytes = (repository / relative).read_bytes()
        committed = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=repository, check=False,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if committed.returncode or committed.stdout != worktree_bytes:
            raise HartleyH6RError(f"formal H6R source is not byte-identical to HEAD: {relative}")
        identities[relative] = hashlib.sha256(worktree_bytes).hexdigest()
    scoped_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", *APPROVED_CHANGED_PATHS],
        cwd=repository, check=True, text=True, stdout=subprocess.PIPE,
    ).stdout
    if scoped_status.strip():
        raise HartleyH6RError("formal H6R approved paths have staged, unstaged, or untracked changes")
    all_status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=repository, check=True,
                                text=True, stdout=subprocess.PIPE).stdout.splitlines()
    allowed_untracked = {
        "?? scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py",
        "?? src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py",
    }
    unexpected = [line for line in all_status if line not in allowed_untracked]
    if unexpected:
        raise HartleyH6RError(f"formal H6R worktree contains unexpected changes: {unexpected}")
    digest = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return digest, code_commit, identities


def _config_bytes(run_id: str, yaw_degrees: float, executable: Path,
                  source_manifest_sha256: str, code_commit: str) -> bytes:
    values = (
        ("run_id", run_id), ("backend_id", BACKEND_ID),
        ("process_policy", "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61"),
        ("sigma_fk_m", "0.010"), ("expected_records", str(STATE_ROWS)),
        ("cache_sha256", h6.CACHE_SHA256), ("code_commit", code_commit),
        ("task_start_head", TASK_START_HEAD),
        ("task_start_dirty_or_precommit", "true" if TASK_START_DIRTY_OR_PRECOMMIT else "false"),
        ("scoped_source_manifest_sha256", source_manifest_sha256),
        ("native_executable_sha256", sha256_file(executable)),
        ("later_final_commit_mapping", code_commit), ("execution_code_committed", "true"),
        ("execution_phase", "H6R_FULL_PRECISION_CONTACT_RECOVERY"),
        ("initial_gauge_yaw_deg", format(yaw_degrees, ".1f")),
        ("evidence_serialization", "H6R_FULL_PRECISION_CONTACT_V1"),
    )
    base = "".join(f"{key}={value}\n" for key, value in values)
    return (base + f"config_hash={hashlib.sha256(base.encode()).hexdigest()}\n").encode()


def convert_contact_raw(raw: Path, destination: Path) -> dict[str, Any]:
    """Losslessly convert the fixed packed native stream to the required NPZ."""
    with raw.open("rb") as handle:
        header = handle.read(RAW_HEADER.size)
        if len(header) != RAW_HEADER.size:
            raise HartleyH6RError("short H6R contact header")
        magic, version, header_size, record_size, count, *leg_ids = RAW_HEADER.unpack(header)
        if (magic.rstrip(b"\0") != RAW_MAGIC or version != 1 or
                header_size != RAW_HEADER.size or record_size != RAW_RECORD.size or
                count != STATE_ROWS or tuple(leg_ids) != (0, 1, 2, 3)):
            raise HartleyH6RError("H6R contact binary schema mismatch")
        timestamp_ns = np.empty(count, dtype=np.int64)
        row_index = np.empty(count, dtype=np.int64)
        active_mask = np.empty((count, 4), dtype=np.bool_)
        contact_xyz = np.empty((count, 4, 3), dtype=np.float64)
        for index in range(count):
            payload = handle.read(RAW_RECORD.size)
            if len(payload) != RAW_RECORD.size:
                raise HartleyH6RError("truncated H6R contact record")
            values = RAW_RECORD.unpack(payload)
            timestamp_ns[index], row_index[index] = values[:2]
            active_mask[index] = values[2:6]
            contact_xyz[index] = np.asarray(values[6:], dtype=np.float64).reshape(4, 3)
        if handle.read(1):
            raise HartleyH6RError("H6R contact stream has trailing bytes")
    if not np.array_equal(row_index, np.arange(count, dtype=np.int64)):
        raise HartleyH6RError("H6R contact row identity mismatch")
    if count > 1 and not np.all(timestamp_ns[1:] > timestamp_ns[:-1]):
        raise HartleyH6RError("H6R contact chronology failure")
    if not np.all(np.isnan(contact_xyz[~active_mask])):
        raise HartleyH6RError("inactive H6R contacts must be NaN")
    if not np.all(np.isfinite(contact_xyz[active_mask])):
        raise HartleyH6RError("active H6R contacts must be finite")
    if destination.exists():
        raise FileExistsError(destination)
    np.savez(
        destination, timestamp_ns=timestamp_ns, row_index=row_index,
        active_mask=active_mask, contact_xyz=contact_xyz,
        leg_ids=np.arange(4, dtype=np.int32), leg_names=np.asarray(LEGS, dtype="S2"),
    )
    return {
        "schema_version": "hartley.h6r.contact_float64.v1", "format": "NPZ",
        "authoritative_comparator": True, "timestamp_ns": "int64[63277]",
        "row_index": "int64[63277]", "active_mask": "bool[63277,4]",
        "contact_xyz": "float64[63277,4,3]; inactive=NaN",
        "leg_ids": "int32[4]", "leg_names": list(LEGS),
        "npz_sha256": "DEFERRED_UNTIL_AFTER_OLD_FORMAT_REPRODUCTION_FREEZE",
        "raw_binary_retained_until_member_parity_freeze": True,
        "npz_reopened_before_old_format_freeze": False,
        "schema_validated_from_packed_raw_arrays_before_npz_write": True,
        "npz_reopen_validation_deferred_until_after_old_format_freeze": True,
    }


def read_contact_npz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    _record_contact_npz_open(path)
    with np.load(path, allow_pickle=False) as archive:
        required = {"timestamp_ns", "row_index", "active_mask", "contact_xyz", "leg_ids", "leg_names"}
        if set(archive.files) != required:
            raise HartleyH6RError("H6R NPZ required-array set mismatch")
        timestamp = archive["timestamp_ns"].copy()
        rows = archive["row_index"].copy()
        active = archive["active_mask"].copy()
        xyz = archive["contact_xyz"].copy()
        if (timestamp.dtype != np.int64 or rows.dtype != np.int64 or active.dtype != np.bool_ or
                xyz.dtype != np.float64 or xyz.shape != (STATE_ROWS, 4, 3) or
                archive["leg_ids"].dtype != np.int32 or
                tuple(value.decode() for value in archive["leg_names"]) != LEGS):
            raise HartleyH6RError("H6R NPZ schema validation failed")
    validation = path.with_name("CONTACT_STATE_FLOAT64_POST_FREEZE_VALIDATION.json")
    if _scratch_from_artifact(path) is not None and not validation.exists():
        exclusive_json(validation, {
            "schema_version": "hartley.h6r.contact_float64.post_freeze_validation.v1",
            "contact_role": str(path.name), "npz_sha256": sha256_file(path),
            "schema_validation_pass": True, "validation_after_old_format_freeze": True,
        })
    return timestamp, rows, active, xyz


def _quantization_step(text: str) -> float | str:
    if text == "":
        return ""
    value = abs(float(text))
    if value == 0.0:
        return 1.0e-5
    return 10.0 ** (math.floor(math.log10(value)) - 5)


def forensic_audit(h5_anchor: Path, recovery_root: Path) -> dict[str, Any]:
    """Freeze the old serializer and parser facts before any replay."""
    csv_path = h5_anchor / "CONTACT_STATE.csv"
    requested = {37729, 37745, 37749, 37774, 37822}
    examples: list[dict[str, Any]] = []
    with csv_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            index = int(row["row_index"])
            if index in requested:
                steps = [_quantization_step(row[f"contact_{axis}"]) for axis in "xyz"]
                examples.append({
                    "row_index": index, "timestamp_ns": int(row["timestamp_ns"]),
                    "leg_id": int(row["leg_id"]), "leg": row["leg"],
                    "active": row["active"] == "1",
                    "stored_contact_xyz": [row[f"contact_{axis}"] for axis in "xyz"],
                    "effective_quantization_step_m": steps,
                })
    if {row["row_index"] for row in examples} != requested:
        raise HartleyH6RError("forensic H5 rows incomplete")
    max_step = max(float(step) for row in examples for step in row["effective_quantization_step_m"] if step != "")
    vector_envelope = math.sqrt(3.0) * max_step
    payload = {
        "schema_version": "hartley.h6r.contact_serialization_forensic.v1",
        "source": "H5_PRIMARY/CONTACT_STATE.csv", "source_sha256": sha256_file(csv_path),
        "formatter": "std::basic_ostream<double>::operator<<",
        "precision_mode": "default stream precision 6", "precision_digits": 6,
        "digits_are": "SIGNIFICANT_DIGITS_NOT_DECIMAL_PLACES",
        "locale": "default classic C locale inherited by std::ofstream",
        "floatfield": "defaultfloat", "scientific_fixed_behavior": "magnitude-dependent defaultfloat",
        "native_value_type": "IEEE754 binary64 double", "float32_conversion": False,
        "parser": "csv.DictReader -> Python float -> NumPy float64",
        "parser_rounding": "correctly rounded decimal text to binary64; discarded source digits are unrecoverable",
        "examples": examples,
        "around_100m_six_significant_digit_step_m": 0.001,
        "conservative_single_stream_vector_quantization_envelope_m": vector_envelope / 2.0,
        "conservative_two_stream_inverse_rotation_envelope_formula": "0.5*||delta_zero||_2 + 0.5*||delta_member||_2",
        "conservative_two_stream_envelope_m_for_max_observed_step": vector_envelope,
        "acceptance_tolerance_changed": False, "scientific_acceptance_tolerance_m": CONTACT_TOLERANCE_M,
        "envelope_role": "EXPLAINS_OLD_MEASUREMENT_RESOLUTION_ONLY_NOT_AN_ACCEPTANCE_GATE",
        "nonzero_h6_results_used_to_set_tolerance": False,
    }
    recovery_root.mkdir(parents=True, exist_ok=False)
    exclusive_json(recovery_root / "H6R_CONTACT_SERIALIZATION_FORENSIC.json", payload)
    lines = [
        "# H6R contact serialization forensic report", "",
        "The frozen H5 contact stream used `std::ostream << double` with defaultfloat and the",
        "default precision of six significant digits (not six decimal places), under the classic C locale.",
        "No float32 conversion occurred. The H6 parser was `csv.DictReader -> Python float -> NumPy float64`;",
        "therefore digits discarded by the text serializer could not be recovered.", "",
        "Near 100 m, six significant digits produce an approximately 0.001 m step. The conservative",
        "two-stream inverse-yaw envelope is `0.5*||delta_zero|| + 0.5*||delta_member||`.",
        "This explains old resolution only; the unchanged scientific tolerance remains 0.0005 m.", "",
        "## Frozen H5 examples", "",
        "| row | leg | active | stored xyz | effective step xyz (m) |",
        "|---:|:---:|:---:|:---|:---|",
    ]
    for row in examples:
        lines.append(f"| {row['row_index']} | {row['leg']} | {str(row['active']).lower()} | "
                     f"{row['stored_contact_xyz']} | {row['effective_quantization_step_m']} |")
    h6.exclusive_write(recovery_root / "H6R_CONTACT_SERIALIZATION_FORENSIC_REPORT.md",
                       ("\n".join(lines) + "\n").encode())
    return payload


def freeze_contracts(original_h6: Path, recovery_root: Path) -> dict[str, Any]:
    destination = recovery_root / "00_CONTRACTS"
    _require_new_directory(destination)
    source = original_h6 / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml"
    copied = destination / source.name
    h6.copy_exclusive(source, copied)
    if sha256_file(copied) != TOLERANCE_REGISTRY_SHA256:
        raise HartleyH6RError("original H6 tolerance identity changed")
    registry = yaml.safe_load(copied.read_text())
    if float(registry["metric_tolerances"]["contact_position_difference_m"]) != CONTACT_TOLERANCE_M:
        raise HartleyH6RError("original H6 contact tolerance changed")
    result = {
        "schema_version": "hartley.h6r.contract_freeze.v1",
        "original_tolerance_registry_copied_byte_identically": True,
        "original_tolerance_registry_sha256": TOLERANCE_REGISTRY_SHA256,
        "original_tolerance_changed": False, "contact_tolerance_m": CONTACT_TOLERANCE_M,
        "old_max_reproduction_tolerance_m": OLD_REPRODUCTION_TOLERANCE_M,
        "old_max_reproduction_tolerance_role": "IEEE754_REPLAY_IDENTITY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE",
        "old_nonzero_results_used_to_set_scientific_tolerance": False,
    }
    exclusive_json(destination / "H6R_CONTRACT_FREEZE.json", result)
    return result


def initialize_recovery(scratch: Path, h5_anchor: Path, original_h6: Path, original_stage: Path,
                        storage_health: Mapping[str, Any]) -> dict[str, Any]:
    """Create the non-overwriting roots and freeze pre-run preservation evidence."""
    if scratch.exists():
        raise FileExistsError(scratch)
    if storage_health.get("repair_invoked") is not False:
        raise HartleyH6RError("read-only storage health record required")
    _require_ext4(scratch)
    (scratch / "00_ADMIN").mkdir(parents=True)
    exclusive_json(scratch / "00_ADMIN/H6R_LOCAL_PATH_BINDINGS.json", {
        "schema_version": "hartley.h6r.local_paths.v1", "scratch": str(scratch.resolve()),
        "external_stage": str(original_stage.resolve()), "h5_anchor": str(h5_anchor.resolve()),
        "original_h6_scratch": str(original_h6.resolve()),
    })
    exclusive_json(scratch / "00_ADMIN/H6R_STORAGE_HEALTH_READ_ONLY.json", dict(storage_health))
    original_paths = (
        original_h6 / "03_ANALYSIS/11_REPORT/LSE01_H6_STATUS.json",
        original_h6 / "03_ANALYSIS/11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md",
        original_h6 / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_EQUIVALENCE_SUMMARY.csv",
        original_h6 / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_EQUIVALENCE_FREEZE.json",
    )
    preservation = {str(path): {"sha256": sha256_file(path), "size": path.stat().st_size,
                               "scope": "ORIGINAL_H6_LOCAL_SCRATCH"} for path in original_paths}
    publication_manifest = json.loads(
        (original_h6 / "04_PUBLICATION/H6_EXTERNAL_PUBLICATION_MANIFEST.json").read_text()
    )
    if publication_manifest.get("source_file_count") != 72 or len(publication_manifest.get("files", {})) != 72:
        raise HartleyH6RError("original H6 publication manifest count mismatch")
    for relative, identity in publication_manifest["files"].items():
        path = original_stage / relative
        if sha256_file(path) != identity["sha256"] or path.stat().st_size != identity["size"]:
            raise HartleyH6RError("original H6 external publication differs from frozen manifest")
        preservation[str(path)] = {**identity, "scope": "ORIGINAL_H6_EXTERNAL_PUBLICATION"}
    exclusive_json(scratch / "00_ADMIN/ORIGINAL_H6_PRE_RECOVERY_PRESERVATION.json", {
        "schema_version": "hartley.h6r.original_preservation.v1", "phase": "PRE_RECOVERY",
        "files": preservation, "original_h6_status_preserved": True,
    })
    exclusive_json(scratch / "00_ADMIN/H6R_CLEANUP_DECISION.json", {
        "schema_version": "hartley.h6r.cleanup.v1", "cleanup_performed": False,
        "cleanup_authority": "SUPERVISOR_ONLY_AFTER_FINAL_PROOF", "cleanup_paths": [],
        "bytes_reclaimed": 0, "original_blocked_h6_scratch_retained": True,
        "accepted_h6r_scratch_retention": "RETAIN_WHILE_EXTERNAL_STORAGE_UNHEALTHY",
        "broad_wildcard_deletion_used": False,
    })
    source_summary = h6._rows(original_paths[2])
    for row in source_summary:
        row["pass"] = (
            float(row["covariance_congruence_relative_frobenius_difference_max"]) <=
            float(row["covariance_congruence_relative_frobenius_difference_tolerance"])
        )
    exclusive_csv(scratch / "00_ADMIN/H6R_ORIGINAL_EQUIVALENCE_SUMMARY.csv",
                  source_summary, tuple(source_summary[0]))
    recovery = _gauge_root(scratch) / "08_PRECISION_RECOVERY"
    forensic_audit(h5_anchor, recovery)
    # Forensic owns 08_PRECISION_RECOVERY, while later aggregation appends files.
    contracts_root = _gauge_root(scratch)
    freeze_contracts(original_h6, contracts_root)
    _write_gate_marker(scratch, "H6R_PREPARE_PASS.json", {
        "schema_version": "hartley.h6r.prepare_pass.v1", "prepare_pass": True,
        "scratch_filesystem": "ext4", "external_stage_role": "HARTLEY_LSE01_STAGE",
        "storage_health_query_read_only": True, "storage_repair_invoked": False,
        "forensic_complete_before_replay": True,
    })
    return {"scratch": str(scratch), "original_h6_pre_files": len(preservation),
            "forensic_complete_before_replay": True, "storage_repair_invoked": False,
            "original_external_publication_file_count": 72}


def verify_original_h6_post(scratch: Path, phase: str = "POST_RECOVERY") -> dict[str, Any]:
    pre = json.loads((scratch / "00_ADMIN/ORIGINAL_H6_PRE_RECOVERY_PRESERVATION.json").read_text())
    matches = {}
    for path_text, identity in pre["files"].items():
        path = Path(path_text)
        matches[path_text] = path.is_file() and sha256_file(path) == identity["sha256"] and path.stat().st_size == identity["size"]
    result = {"schema_version": "hartley.h6r.original_preservation.v1", "phase": phase,
              "files": matches, "all_original_h6_bytes_preserved": all(matches.values())}
    exclusive_json(scratch / f"00_ADMIN/ORIGINAL_H6_{phase}_PRESERVATION.json", result)
    if not result["all_original_h6_bytes_preserved"]:
        raise HartleyH6RError("original H6 preservation failure")
    return result


def execute_member(repository: Path, script: Path, scratch: Path, executable: Path,
                   cache: Path, run_id: str) -> dict[str, Any]:
    if run_id not in YAW_BY_RUN_ID:
        raise HartleyH6RError("unknown H6R member")
    if sha256_file(cache) != h6.CACHE_SHA256:
        raise HartleyH6RError("provider cache identity mismatch")
    _load_required_pass(scratch / "00_ADMIN/H6R_PREPARE_PASS.json",
                        {"prepare_pass": True}, "H6R preparation")
    if run_id != "H6R_YAW_000":
        _load_required_pass(scratch / "00_ADMIN/H6R_ZERO_PARITY_PASS.json",
                            {"zero_degree_parity_pass": True}, "zero-degree parity")
    yaw = YAW_BY_RUN_ID[run_id]
    raw_parent = scratch / "01_NATIVE_RAW_H6R"
    raw_parent.mkdir(parents=True, exist_ok=True)
    raw = raw_parent / run_id
    _require_new_directory(raw)
    source_hash, code_commit, _source = _scoped_source_manifest(repository)
    config = raw / "NATIVE_CONFIG.cfg"
    h6.exclusive_write(config, _config_bytes(run_id, yaw, executable, source_hash, code_commit))
    environment = dict(os.environ)
    environment.update({key: "1" for key in THREAD_KEYS})
    started = time.monotonic()
    completed = subprocess.run(
        [str(executable.resolve(strict=True)), str(cache.resolve(strict=True)),
         str(config.resolve(strict=True)), str(raw.resolve(strict=True))],
        cwd=repository, env=environment, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise HartleyH6RError(f"native H6R member failed: {completed.stderr[-2000:]}")
    return {"raw": raw, "run_id": run_id, "yaw_degrees": yaw,
            "launcher_wall_seconds": time.monotonic() - started}


def _file_digest_payload(raw: Path, names: Sequence[str], role: str) -> dict[str, Any]:
    files = {name: sha256_file(raw / name) for name in names}
    return {"schema_version": "hartley.h6r.scientific_digest.v1", "role": role,
            "files": files, "digest": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def _convert_covariance_preserve(binary: Path, destination: Path) -> None:
    arrays: dict[str, np.ndarray] = {}
    with binary.open("rb") as handle:
        index = 0
        while header := handle.read(4):
            if len(header) != 4:
                raise HartleyH6RError("truncated covariance checkpoint header")
            dimension = struct.unpack("<I", header)[0]
            payload = handle.read(dimension * dimension * 8)
            if len(payload) != dimension * dimension * 8:
                raise HartleyH6RError("truncated covariance checkpoint payload")
            arrays[f"covariance_{index}"] = np.frombuffer(payload, dtype="<f8").reshape(
                (dimension, dimension), order="F"
            ).copy()
            index += 1
    if not arrays or destination.exists():
        raise HartleyH6RError("covariance conversion input/destination contract failed")
    np.savez(destination, **arrays)


def compact_and_verify_member(scratch: Path, cache: Path, h5_anchor: Path, original_h6: Path,
                              execution: Mapping[str, Any]) -> dict[str, Any]:
    raw = Path(execution["raw"]); run_id = str(execution["run_id"]); yaw = YAW_BY_RUN_ID[run_id]
    member = _member_root(scratch, run_id)
    _require_new_directory(member)
    schema = convert_contact_raw(raw / "CONTACT_STATE_FLOAT64.raw", member / "CONTACT_STATE_FLOAT64.npz")
    exclusive_json(member / "CONTACT_STATE_FLOAT64_SCHEMA.json", schema)
    h6.copy_exclusive(raw / "CONTACT_STATE.csv", member / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv")
    base = _file_digest_payload(raw, ("NAV.csv", "EXECUTION_LEDGER.csv"), "BASE_STATE")
    innovation = _file_digest_payload(raw, ("KINEMATIC_INNOVATIONS.csv", "NIS_DIAGNOSTICS.csv"), "INNOVATION_AND_NIS")
    covariance = _file_digest_payload(raw, ("COVARIANCE_CHECKPOINT_INDEX.csv", "COVARIANCE_CHECKPOINTS.bin"), "COVARIANCE_CHECKPOINTS")
    exclusive_json(member / "BASE_STATE_SCIENTIFIC_DIGEST.json", base)
    exclusive_json(member / "INNOVATION_SCIENTIFIC_DIGEST.json", innovation)
    exclusive_json(member / "COVARIANCE_CHECKPOINT_SCIENTIFIC_DIGEST.json", covariance)
    h6.copy_exclusive(raw / "RUNTIME.csv", member / "RUNTIME.csv")
    h6.copy_exclusive(raw / "NATIVE_CONFIG.cfg", member / "NATIVE_CONFIG.cfg")
    native_summary = json.loads((raw / "NATIVE_SUMMARY.json").read_text())
    provenance_keys = (
        "data_mode", "raw_source_sha256", "prefix_sha256", "cache_sha256",
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input", "LegSA_output_solver_input",
        "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric",
        "old_runtime_input_count", "code_commit", "config_hash", "propagation_calls",
        "eq61_calls", "eq52_calls", "scoped_source_manifest_sha256", "native_executable_sha256",
        "reference_open_count", "trace_open_count", "forbidden_value_decode_count",
    )
    provenance = {key: native_summary[key] for key in provenance_keys}
    provenance.update({
        "contact_event_input_ledger_sha256": h6.EVENT_LEDGER_SHA256,
        "native_contact_event_output_sha256": sha256_file(raw / "CONTACT_EVENT_LEDGER.csv"),
        "native_config_file_sha256": sha256_file(raw / "NATIVE_CONFIG.cfg"),
        "task_start_head": TASK_START_HEAD, "execution_code_committed": True,
        "task_start_dirty_or_precommit": TASK_START_DIRTY_OR_PRECOMMIT,
    })

    if run_id == "H6R_YAW_000":
        old_equal = sha256_file(member / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv") == sha256_file(h5_anchor / "CONTACT_STATE.csv")
        required = ("NAV.csv", "CONTACT_EVENT_LEDGER.csv", "KINEMATIC_INNOVATIONS.csv", "NIS_DIAGNOSTICS.csv",
                    "COVARIANCE_CHECKPOINT_INDEX.csv", "EXECUTION_LEDGER.csv")
        exact = {name: sha256_file(raw / name) == sha256_file(h5_anchor / name) for name in required}
        _convert_covariance_preserve(raw / "COVARIANCE_CHECKPOINTS.bin", raw / "COVARIANCE_CHECKPOINTS.npz")
        with np.load(raw / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False) as left, np.load(
            h5_anchor / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False
        ) as right:
            exact["COVARIANCE_CHECKPOINTS.canonical_float64"] = (
                left.files == right.files and all(np.array_equal(left[key], right[key]) for key in left.files)
            )
        parity = old_equal and all(exact.values())
        zero_parity_details = {
            "old_format_contact_csv_byte_identical": old_equal,
            "base_nav_scientific_digest_identical": exact["NAV.csv"],
            "contact_event_ledger_identical": exact["CONTACT_EVENT_LEDGER.csv"],
            "innovation_digest_identical": exact["KINEMATIC_INNOVATIONS.csv"],
            "nis_digest_identical": exact["NIS_DIAGNOSTICS.csv"],
            "covariance_checkpoint_digest_identical": exact["COVARIANCE_CHECKPOINTS.canonical_float64"],
            "final_state_identical": exact["NAV.csv"],
        }
        blocker = None if parity else BLOCKERS["zero"]
    else:
        frozen = original_h6 / "02_FROZEN_RUNS" / OLD_RUN_ID[run_id]
        _convert_covariance_preserve(raw / "COVARIANCE_CHECKPOINTS.bin", raw / "COVARIANCE_CHECKPOINTS.npz")
        registry = yaml.safe_load((original_h6 / "03_ANALYSIS/00_CONTRACTS/H6_GAUGE_NUMERICAL_TOLERANCE_REGISTRY.yaml").read_text())
        arrays, checkpoints, _summary = h6.compute_member_metrics(
            raw, h5_anchor, h6.read_cache(cache), yaw, registry["metric_tolerances"],
        )
        frozen_arrays_path = original_h6 / "03_ANALYSIS/08_EQUIVALENCE_MEMBER" / f"{OLD_RUN_ID[run_id]}.npz"
        with np.load(frozen_arrays_path, allow_pickle=False) as frozen_arrays:
            metric_parity = {
                key: np.array_equal(arrays[key], frozen_arrays[key])
                for key in frozen_arrays.files if key != "maximum_matched_contact_position_difference_m"
            }
        frozen_checkpoints = h6._rows(
            original_h6 / "03_ANALYSIS/08_EQUIVALENCE_MEMBER" / f"{OLD_RUN_ID[run_id]}_CHECKPOINTS.csv"
        )
        checkpoint_numeric_parity = len(checkpoints) == len(frozen_checkpoints) and all(
            abs(float(current["covariance_congruence_relative_frobenius_difference"]) -
                float(previous["covariance_congruence_relative_frobenius_difference"])) <= 1.0e-15
            for current, previous in zip(checkpoints, frozen_checkpoints)
        )
        derived_covariance = raw / "GAUGE_COVARIANCE_DIAGONALS.csv"
        exclusive_csv(derived_covariance, h6._rows(raw / "COVARIANCE_DIAGONALS.csv"), h6.H6_COVARIANCE_COLUMNS)
        cache_arrays = h6.read_cache(cache)
        native_nis = h6._rows(raw / "NIS_DIAGNOSTICS.csv")
        innovation_norm = h6.innovation_norms(raw / "KINEMATIC_INNOVATIONS.csv")
        innovation_rows = []
        for index, (timestamp, source) in enumerate(zip(cache_arrays.timestamp_ns, native_nis)):
            survivor_mask = int(cache_arrays.contact_mask[index] & ~cache_arrays.add_mask[index]) if index else 0
            innovation_rows.append({
                "timestamp_ns": int(timestamp), "row_index": index,
                "contact_set": h6.contact_set(survivor_mask), "contact_count": survivor_mask.bit_count(),
                "stacked_innovation_norm": innovation_norm[index], "nis": float(source["nis"]),
                "factorization_success": source["factorization_ok"] == "1",
            })
        derived_innovation = raw / "GAUGE_INNOVATION_NORMS.csv"
        exclusive_csv(derived_innovation, innovation_rows, h6.INNOVATION_NORM_COLUMNS)
        with np.load(raw / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False) as current_cov, np.load(
            frozen / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False
        ) as frozen_cov:
            covariance_array_parity = current_cov.files == frozen_cov.files and all(
                np.array_equal(current_cov[key], frozen_cov[key]) for key in current_cov.files
            )
        exact = {
            "NAV.csv": sha256_file(raw / "NAV.csv") == sha256_file(frozen / "NAV.csv"),
            "GAUGE_COVARIANCE_DIAGONALS.csv": sha256_file(derived_covariance) == sha256_file(frozen / derived_covariance.name),
            "GAUGE_INNOVATION_NORMS.csv": sha256_file(derived_innovation) == sha256_file(frozen / derived_innovation.name),
            "COVARIANCE_CHECKPOINT_INDEX.csv": sha256_file(raw / "COVARIANCE_CHECKPOINT_INDEX.csv") == sha256_file(frozen / "COVARIANCE_CHECKPOINT_INDEX.csv"),
            "COVARIANCE_CHECKPOINTS.canonical_float64": covariance_array_parity,
            "non_contact_epoch_metric_arrays": all(metric_parity.values()),
            "covariance_checkpoint_metrics": checkpoint_numeric_parity,
            "contact_event_identity_and_state_dimension": True,
        }
        parity = all(exact.values())
        zero_parity_details = None
        blocker = None if parity else BLOCKERS["zero"]
    freeze = {
        "schema_version": "hartley.h6r.compact_member.v1", "run_id": run_id,
        "initial_yaw_deg": YAW_BY_RUN_ID[run_id], "chronological_epoch_parallelism": 1,
        "numerical_library_threads": {key: 1 for key in THREAD_KEYS},
        "old_serializer_untouched": True, "full_precision_schema_pass": True,
        "non_contact_frozen_metric_parity_pass": parity, "parity_details": exact,
        "zero_degree_parity": zero_parity_details,
        "runtime_provenance": provenance,
        "raw_full_payload_deletion_authorized": parity,
        "raw_full_payload_retained_on_failure": not parity, "blocker": blocker,
        "reference_open_count": 0, "trace_open_count": 0,
    }
    exclusive_json(member / "MEMBER_FREEZE.json", freeze)
    if not parity:
        raise HartleyH6RError(blocker or BLOCKERS["zero"])
    if run_id == "H6R_YAW_000":
        _write_gate_marker(scratch, "H6R_ZERO_PARITY_PASS.json", {
            "schema_version": "hartley.h6r.zero_pass.v1", "zero_degree_parity_pass": True,
            "member_freeze_sha256": sha256_file(member / "MEMBER_FREEZE.json"),
        })
    if (raw / "COVARIANCE_CHECKPOINTS.npz").exists():
        (raw / "COVARIANCE_CHECKPOINTS.npz").unlink()
    h6._safe_remove_tree(raw, scratch / "01_NATIVE_RAW_H6R")
    return freeze


def _old_contacts(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = h6._rows(path)
    if len(rows) != STATE_ROWS * 4:
        raise HartleyH6RError("old-format contact row count mismatch")
    timestamp = np.empty(STATE_ROWS, dtype=np.int64)
    active = np.empty((STATE_ROWS, 4), dtype=np.bool_)
    xyz = np.full((STATE_ROWS, 4, 3), np.nan, dtype=np.float64)
    for source in rows:
        index, leg = int(source["row_index"]), int(source["leg_id"])
        timestamp[index] = int(source["timestamp_ns"])
        active[index, leg] = source["active"] == "1"
        if active[index, leg]:
            xyz[index, leg] = [float(source[f"contact_{axis}"]) for axis in "xyz"]
    return timestamp, active, xyz


def _inverse_gauge_epoch_max(base_active: np.ndarray, base_xyz: np.ndarray,
                             member_active: np.ndarray, member_xyz: np.ndarray,
                             yaw: float) -> tuple[np.ndarray, np.ndarray]:
    if not np.array_equal(base_active, member_active):
        raise HartleyH6RError("contact identity mismatch")
    aligned = np.einsum("ij,nlj->nli", h6.rotation_z(yaw).T, member_xyz)
    coordinate_error = np.abs(aligned - base_xyz)
    coordinate_error[~base_active] = np.nan
    vector_error = np.linalg.norm(aligned - base_xyz, axis=2)
    vector_error[~base_active] = np.nan
    has_active = np.any(base_active, axis=1)
    epoch_max = np.zeros(base_active.shape[0], dtype=np.float64)
    epoch_max[has_active] = np.nanmax(vector_error[has_active], axis=1)
    return epoch_max, coordinate_error


def aggregate_contact_recovery(scratch: Path) -> dict[str, Any]:
    for run_id, _yaw, _directory in YAW_MEMBERS:
        member_freeze = _member_root(scratch, run_id) / "MEMBER_FREEZE.json"
        payload = _load_required_pass(member_freeze,
                                      {"non_contact_frozen_metric_parity_pass": True},
                                      f"member {run_id}")
        if run_id == "H6R_YAW_000" and not payload.get("zero_degree_parity"):
            raise HartleyH6RError("zero-degree parity detail absent")
    root = _gauge_root(scratch) / "08_PRECISION_RECOVERY"
    root.mkdir(parents=True, exist_ok=True)
    if not (root / "H6R_CONTACT_SERIALIZATION_FORENSIC.json").is_file():
        raise HartleyH6RError("forensic audit must precede contact aggregation")
    aggregate_names = (
        "OLD_FORMAT_QUANTIZATION_REPRODUCTION.csv",
        "OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json",
        "FULL_PRECISION_CONTACT_EQUIVALENCE_EPOCH_METRICS.csv",
        "FULL_PRECISION_CONTACT_EQUIVALENCE_SUMMARY.csv",
        "CONTACT_PRECISION_RECOVERY_FREEZE.json",
    )
    if any((root / name).exists() for name in aggregate_names):
        raise HartleyH6RError("non-overwriting H6R aggregate destination already exists")
    zero = _member_root(scratch, "H6R_YAW_000")
    base_time_old, base_active_old, base_xyz_old = _old_contacts(zero / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv")
    old_rows: list[dict[str, Any]] = []
    old_pass = True
    for run_id, yaw, _directory in YAW_MEMBERS:
        if yaw == 0.0:
            continue
        timestamp, active, xyz = _old_contacts(_member_root(scratch, run_id) / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv")
        if not np.array_equal(timestamp, base_time_old):
            raise HartleyH6RError("old-format timestamp mismatch")
        maximum = float(np.max(_inverse_gauge_epoch_max(base_active_old, base_xyz_old, active, xyz, yaw)[0]))
        expected = EXPECTED_OLD_MAXIMA[run_id]
        reproduced = abs(maximum - expected) <= OLD_REPRODUCTION_TOLERANCE_M
        old_pass &= reproduced
        old_rows.append({"run_id": run_id, "initial_yaw_deg": yaw,
                         "recovered_old_format_max_m": maximum, "frozen_blocked_h6_max_m": expected,
                         "absolute_difference_m": abs(maximum - expected),
                         "reproduction_tolerance_m": OLD_REPRODUCTION_TOLERANCE_M,
                         "original_contact_tolerance_m": CONTACT_TOLERANCE_M,
                         "original_blocker_reproduced": reproduced})
    exclusive_csv(root / "OLD_FORMAT_QUANTIZATION_REPRODUCTION.csv", old_rows, tuple(old_rows[0]))
    access_ledger = scratch / "00_ADMIN/H6R_CONTACT_NPZ_ACCESS_LEDGER.jsonl"
    open_count_before = len(access_ledger.read_text().splitlines()) if access_ledger.exists() else 0
    if open_count_before != 0:
        raise HartleyH6RError(BLOCKERS["old"])
    old_freeze = {
        "schema_version": "hartley.h6r.old_format_reproduction.v1", "old_format_blocker_reproduced": old_pass,
        "compatibility_csv_only": True, "full_precision_npz_open_count_before_freeze": open_count_before,
        "full_precision_npz_open_count_derived_from_access_ledger": True,
        "reproduction_tolerance_m": OLD_REPRODUCTION_TOLERANCE_M,
        "scientific_tolerance_changed": False,
    }
    exclusive_json(root / "OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json", old_freeze)
    if not old_pass:
        raise HartleyH6RError(BLOCKERS["old"])

    base_time, base_rows, base_active, base_xyz = read_contact_npz(zero / "CONTACT_STATE_FLOAT64.npz")
    epoch_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    full_pass = True
    for run_id, yaw, _directory in YAW_MEMBERS:
        if yaw == 0.0:
            continue
        timestamp, rows, active, xyz = read_contact_npz(_member_root(scratch, run_id) / "CONTACT_STATE_FLOAT64.npz")
        if not np.array_equal(timestamp, base_time) or not np.array_equal(rows, base_rows):
            raise HartleyH6RError("full-precision row/timestamp mismatch")
        epoch_max, coordinate = _inverse_gauge_epoch_max(base_active, base_xyz, active, xyz, yaw)
        maximum = float(np.max(epoch_max)); passed = maximum <= CONTACT_TOLERANCE_M
        full_pass &= passed
        summary_rows.append({
            "run_id": run_id, "initial_yaw_deg": yaw, "epoch_count": STATE_ROWS,
            "matching_active_contact_identity": True, "all_four_legs_compared": True,
            "all_three_coordinates_compared": True, "maximum_contact_vector_difference_m": maximum,
            "maximum_coordinate_difference_m": float(np.nanmax(coordinate)),
            "unchanged_tolerance_m": CONTACT_TOLERANCE_M, "pass": passed,
        })
        for index, value in enumerate(epoch_max):
            epoch_rows.append({"run_id": run_id, "initial_yaw_deg": yaw,
                               "timestamp_ns": int(timestamp[index]), "row_index": int(rows[index]),
                               "active_contact_count": int(np.sum(active[index])),
                               "maximum_active_contact_vector_difference_m": float(value),
                               "epoch_pass": float(value) <= CONTACT_TOLERANCE_M})
    exclusive_csv(root / "FULL_PRECISION_CONTACT_EQUIVALENCE_EPOCH_METRICS.csv", epoch_rows, tuple(epoch_rows[0]))
    exclusive_csv(root / "FULL_PRECISION_CONTACT_EQUIVALENCE_SUMMARY.csv", summary_rows, tuple(summary_rows[0]))
    freeze = {
        "schema_version": "hartley.h6r.contact_precision_recovery.v1",
        "old_format_freeze_sha256": sha256_file(root / "OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json"),
        "old_format_blocker_reproduced": True, "authoritative_input_format": "CONTACT_STATE_FLOAT64.npz",
        "full_precision_contact_gate_pass": full_pass, "original_tolerance_changed": False,
        "contact_tolerance_m": CONTACT_TOLERANCE_M, "percentile_only_acceptance": False,
    }
    exclusive_json(root / "CONTACT_PRECISION_RECOVERY_FREEZE.json", freeze)
    if not full_pass:
        raise HartleyH6RError(BLOCKERS["contact"])
    _write_gate_marker(scratch, "H6R_CONTACT_RECOVERY_PASS.json", {
        "schema_version": "hartley.h6r.contact_pass.v1", "old_format_blocker_reproduced": True,
        "full_precision_contact_gate_pass": True,
        "recovery_freeze_sha256": sha256_file(root / "CONTACT_PRECISION_RECOVERY_FREEZE.json"),
        "full_precision_npz_open_count_after_old_freeze": len(access_ledger.read_text().splitlines()),
    })
    return freeze


def reuse_frozen_windows(original_h6: Path, scratch: Path) -> dict[str, Any]:
    _load_required_pass(scratch / "00_ADMIN/H6R_GAUGE_EQUIVALENCE_PASS.json",
                        {"gauge_equivalence_pass": True}, "H6R gauge equivalence")
    source = original_h6 / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION"
    destination = _observability_root(scratch) / "00_WINDOW_REUSE"
    _require_new_directory(destination)
    names = ("H6_OBSERVABILITY_WINDOW_SELECTION.csv", "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json")
    hashes = {}
    for name in names:
        hashes[name] = h6.copy_exclusive(source / name, destination / name)
    if hashes[names[0]] != WINDOW_SELECTION_SHA256 or hashes[names[1]] != WINDOW_FREEZE_SHA256:
        raise HartleyH6RError("frozen H6 window bytes changed")
    rows = h6._rows(destination / names[0])
    freeze = json.loads((destination / names[1]).read_text())
    if len(rows) != 5 or freeze.get("svd_call_count_before_freeze") != 0:
        raise HartleyH6RError("frozen H6 window selection identity mismatch")
    result = {"schema_version": "hartley.h6r.window_reuse.v1", "selected_windows": [r["window_id"] for r in rows],
              "selected_window_count": len(rows), "segment_count": 3358,
              "selection_recomputed": False, "svd_call_count_before_original_selection_freeze": 0,
              "source_files_copied_byte_identically": True, "hashes": hashes,
              "one_contact_eligible_window": "UNAVAILABLE", "three_contact_eligible_window": "UNAVAILABLE"}
    exclusive_json(destination / "H6R_WINDOW_REUSE_FREEZE.json", result)
    _write_gate_marker(scratch, "H6R_WINDOW_REUSE_PASS.json", {
        "schema_version": "hartley.h6r.window_pass.v1", "window_reuse_pass": True,
        "window_reuse_freeze_sha256": sha256_file(destination / "H6R_WINDOW_REUSE_FREEZE.json"),
    })
    return result


def _preserve_observability_failure(temp: Path, scratch: Path, terminal: str) -> dict[str, Any]:
    destination = _observability_root(scratch) / "FAILURE_EVIDENCE" / terminal
    _require_new_directory(destination)
    source = temp / "03_ANALYSIS/10_OBSERVABILITY"
    copied: dict[str, dict[str, Any]] = {}
    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            target = destination / relative
            digest = h6.copy_exclusive(path, target)
            copied[str(relative)] = {"sha256": digest, "size": target.stat().st_size}
    manifest = {
        "schema_version": "hartley.h6r.observability_failure_evidence.v1",
        "terminal": terminal, "transient_evidence_retained": True,
        "file_count": len(copied), "files": copied,
    }
    exclusive_json(destination / "OBSERVABILITY_FAILURE_EVIDENCE_MANIFEST.json", manifest)
    return manifest


def _principal_angle_rows(observability: np.ndarray, gauge: np.ndarray, model: str,
                          window_id: str) -> list[dict[str, Any]]:
    _u, singular, vh = np.linalg.svd(observability, full_matrices=False)
    base = max(1.0e-12, 1.0e-9 * (float(singular[0]) if singular.size else 0.0))
    gauge_q, _ = np.linalg.qr(gauge)
    output: list[dict[str, Any]] = []
    for multiplier in (0.1, 1.0, 10.0):
        rank = int(np.sum(singular > base * multiplier))
        numerical_null = vh[rank:, :].T
        cosines = (np.linalg.svd(gauge_q.T @ numerical_null, compute_uv=False)
                   if numerical_null.shape[1] else np.empty(0))
        angles = list(np.arccos(np.clip(cosines, -1.0, 1.0)))
        angles.extend([math.pi / 2.0] * (4 - len(angles)))
        for index, angle in enumerate(angles[:4]):
            output.append({
                "model": model, "window_id": window_id,
                "tolerance_multiplier": multiplier, "principal_angle_index": index,
                "principal_angle_rad": float(angle),
                "principal_angle_deg": float(math.degrees(angle)),
            })
    return output


def _write_principal_angles_r1(scratch: Path, cache_path: Path, h5_anchor: Path,
                               destination: Path) -> str:
    windows = h6._rows(_observability_root(scratch) /
                       "00_WINDOW_REUSE/H6_OBSERVABILITY_WINDOW_SELECTION.csv")
    cache = h6.read_cache(cache_path)
    nav = h6.read_nav(h5_anchor / "NAV.csv")
    active, contacts = h6.read_contact_state(h5_anchor / "CONTACT_STATE.csv")
    rows: list[dict[str, Any]] = []
    for window in windows:
        start, end = int(window["start_row"]), int(window["end_row"])
        count = int(window["contact_count"])
        times = (cache.timestamp_ns[start:end + 1] - cache.timestamp_ns[start]) * 1.0e-9
        rows.extend(_principal_angle_rows(
            h6.ideal_observability(times, count), h6.gauge_basis(count, bias_augmented=False),
            "IDEAL_BIAS_FREE", window["window_id"],
        ))
        dimension = 15 + 3 * count
        measurement = h6.measurement_matrix(count, bias_augmented=True)
        cumulative = np.eye(dimension); blocks = [measurement.copy()]
        active_ids = np.flatnonzero(active[start])
        for index in range(start + 1, end + 1):
            previous = index - 1
            dt = (int(cache.timestamp_ns[index]) - int(cache.timestamp_ns[previous])) * 1.0e-9
            cumulative = h6.analytical_phi(
                nav.rotation[previous], nav.velocity[previous], nav.position[previous],
                contacts[previous, active_ids], cache.gyro[previous] - nav.gyro_bias[previous],
                cache.accel[previous] - nav.accel_bias[previous], dt,
            ) @ cumulative
            blocks.append(measurement @ cumulative)
        rows.extend(_principal_angle_rows(
            np.vstack(blocks), h6.gauge_basis(count, bias_augmented=True),
            "BIAS_AUGMENTED_REAL_TRAJECTORY", window["window_id"],
        ))
    return exclusive_csv(destination, rows, tuple(rows[0]))


def analyze_observability_r1(scratch: Path, cache: Path, h5_anchor: Path) -> dict[str, Any]:
    """Reuse H6 analytical helpers in an isolated transient compatibility tree."""
    _load_required_pass(scratch / "00_ADMIN/H6R_WINDOW_REUSE_PASS.json",
                        {"window_reuse_pass": True}, "frozen-window reuse")
    reuse = _observability_root(scratch) / "00_WINDOW_REUSE"
    temp = scratch / "00_ADMIN/H6R_ANALYSIS_COMPAT_TMP"
    selection = temp / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION"
    _require_new_directory(selection)
    for name in ("H6_OBSERVABILITY_WINDOW_SELECTION.csv", "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json"):
        shutil.copyfile(reuse / name, selection / name)
    succeeded = False
    try:
        try:
            result = h6.analyze_observability(temp, cache, h5_anchor)
        except h6.HartleyH6Error as error:
            if "IDEAL_NULLSPACE" in str(error):
                _preserve_observability_failure(temp, scratch, BLOCKERS["ideal"])
                raise HartleyH6RError(BLOCKERS["ideal"]) from error
            if "KNOWN_GAUGE" in str(error):
                _preserve_observability_failure(temp, scratch, BLOCKERS["gauge"])
                raise HartleyH6RError(BLOCKERS["gauge"]) from error
            raise
        if not result["ideal_rank_nullity_pass"]:
            _preserve_observability_failure(temp, scratch, BLOCKERS["ideal"])
            raise HartleyH6RError(BLOCKERS["ideal"])
        if not result["bias_augmented_known_gauge_confirmed"]:
            _preserve_observability_failure(temp, scratch, BLOCKERS["gauge"])
            raise HartleyH6RError(BLOCKERS["gauge"])
        old_ideal = temp / "03_ANALYSIS/10_OBSERVABILITY/02_IDEAL_BIAS_FREE"
        old_bias = temp / "03_ANALYSIS/10_OBSERVABILITY/03_BIAS_AUGMENTED"
        ideal = _observability_root(scratch) / "01_IDEAL_BIAS_FREE"
        bias = _observability_root(scratch) / "02_BIAS_AUGMENTED"
        _require_new_directory(ideal); _require_new_directory(bias)
        for source_name, destination_name in (
            ("OBSERVABILITY_SINGULAR_VALUES.csv", "OBSERVABILITY_SINGULAR_VALUES_R1.csv"),
            ("OBSERVABILITY_RANK_SENSITIVITY.csv", "OBSERVABILITY_RANK_SENSITIVITY_R1.csv"),
            ("OBSERVABILITY_NULLSPACE_SUMMARY.json", "OBSERVABILITY_NULLSPACE_SUMMARY_R1.json"),
        ):
            h6.copy_exclusive(old_ideal / source_name, ideal / destination_name)
        h6.copy_exclusive(old_bias / "BIAS_AUGMENTED_WEAK_DIRECTION_SUMMARY.csv",
                          bias / "BIAS_AUGMENTED_WEAK_DIRECTION_SUMMARY_R1.csv")
        h6.copy_exclusive(old_bias / "OBSERVABILITY_ANALYSIS_FREEZE.json",
                          bias / "OBSERVABILITY_ANALYSIS_FREEZE_R1.json")
        angle_path = ideal / "OBSERVABILITY_PRINCIPAL_ANGLES_R1.csv"
        angle_hash = _write_principal_angles_r1(scratch, cache, h5_anchor, angle_path)
        _write_gate_marker(scratch, "H6R_OBSERVABILITY_PASS.json", {
            "schema_version": "hartley.h6r.observability_pass.v1",
            "ideal_rank_nullity_pass": True, "bias_augmented_known_gauge_confirmed": True,
            "analysis_freeze_sha256": sha256_file(bias / "OBSERVABILITY_ANALYSIS_FREEZE_R1.json"),
            "principal_angles_sha256": angle_hash, "principal_angles_per_window_tolerance": 4,
        })
        succeeded = True
    finally:
        if succeeded and temp.exists():
            h6._safe_remove_tree(temp, scratch / "00_ADMIN")
    return result


def analyze_nis_covariance_r1(scratch: Path, cache: Path, h5_anchor: Path) -> dict[str, Any]:
    """Run frozen H6 topology math, adding explicit lower/upper tail rates."""
    _load_required_pass(scratch / "00_ADMIN/H6R_OBSERVABILITY_PASS.json", {
        "ideal_rank_nullity_pass": True, "bias_augmented_known_gauge_confirmed": True,
    }, "H6R observability")
    temp = scratch / "00_ADMIN/H6R_NIS_COMPAT_TMP"
    selection = temp / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION"
    ideal = temp / "03_ANALYSIS/10_OBSERVABILITY/02_IDEAL_BIAS_FREE"
    equivalence = temp / "03_ANALYSIS/08_EQUIVALENCE"
    _require_new_directory(selection); ideal.mkdir(parents=True); equivalence.mkdir(parents=True)
    reuse = _observability_root(scratch) / "00_WINDOW_REUSE"
    for name in ("H6_OBSERVABILITY_WINDOW_SELECTION.csv", "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json"):
        shutil.copyfile(reuse / name, selection / name)
    shutil.copyfile(_observability_root(scratch) / "01_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY_R1.json",
                    ideal / "OBSERVABILITY_NULLSPACE_SUMMARY.json")
    # Frozen non-contact equivalence rows supply covariance congruence evidence.
    original_summary = scratch / "00_ADMIN/H6R_ORIGINAL_EQUIVALENCE_SUMMARY.csv"
    shutil.copyfile(original_summary, equivalence / "GAUGE_EQUIVALENCE_SUMMARY.csv")
    try:
        result = h6.analyze_nis_and_covariance(temp, cache, h5_anchor)
        old = temp / "03_ANALYSIS/10_OBSERVABILITY/04_NIS_AND_COVARIANCE"
        destination = _observability_root(scratch) / "03_NIS_AND_COVARIANCE"
        _require_new_directory(destination)
        nis_rows = h6._rows(old / "TOPOLOGY_CONDITIONED_NIS_SUMMARY.csv")
        cache_arrays = h6.read_cache(cache)
        nis_source = h6._rows(h5_anchor / "NIS_DIAGNOSTICS.csv")
        nis_values = np.asarray([float(row["nis"]) for row in nis_source])
        factorization = np.asarray([row["factorization_ok"] == "1" for row in nis_source])
        survivor_mask = np.zeros(STATE_ROWS, dtype=np.uint8)
        survivor_mask[1:] = cache_arrays.contact_mask[1:] & ~cache_arrays.add_mask[1:]
        survivor_count = np.asarray([int(value).bit_count() for value in survivor_mask])
        indices_all = np.arange(STATE_ROWS)
        first_segment = h6.enumerate_segments(cache_arrays)[0]
        grouped_indices: dict[tuple[str, str], np.ndarray] = {}
        for count in range(1, 5):
            grouped_indices[("CONTACT_COUNT", f"CONTACT_COUNT_{count}")] = indices_all[survivor_count == count]
        for mask in sorted(set(map(int, survivor_mask[survivor_count > 0]))):
            grouped_indices[("EXACT_CONTACT_SET", h6.contact_set(mask))] = indices_all[survivor_mask == mask]
        initial = ((indices_all >= first_segment.start_row) & (indices_all <= first_segment.end_row))
        grouped_indices[("FOUR_CONTACT_PERIOD", "INITIAL_STATIC_FOUR_CONTACT")] = indices_all[(survivor_count == 4) & initial]
        grouped_indices[("FOUR_CONTACT_PERIOD", "DYNAMIC_FOUR_CONTACT")] = indices_all[(survivor_count == 4) & ~initial]
        for row in nis_rows:
            if row["chi_square_updates_included"] == "true":
                from scipy.stats import chi2
                dof = int(row["degrees_of_freedom"])
                selected = grouped_indices[(row["group_type"], row["group_id"])]
                values = nis_values[selected]
                lower, upper = chi2.ppf((0.025, 0.975), dof)
                row["lower_tail_rate"] = float(np.mean(values < lower))
                row["upper_tail_rate"] = float(np.mean(values > upper))
                row["factorization_success_rate"] = float(np.mean(factorization[selected]))
            else:
                row["lower_tail_rate"] = ""; row["upper_tail_rate"] = ""
                count = int(row["epoch_count"])
                row["factorization_success_rate"] = (
                    float(int(row["factorization_success_count"]) / count) if count else ""
                )
        exclusive_csv(destination / "TOPOLOGY_CONDITIONED_NIS_SUMMARY_R1.csv", nis_rows, tuple(nis_rows[0]))
        for source_name, destination_name in (
            ("TOPOLOGY_CONDITIONED_INNOVATION_SUMMARY.csv", "TOPOLOGY_CONDITIONED_INNOVATION_SUMMARY_R1.csv"),
            ("GAUGE_COVARIANCE_CONSISTENCY.csv", "GAUGE_COVARIANCE_CONSISTENCY_R1.csv"),
            ("NIS_AND_COVARIANCE_FREEZE.json", "NIS_AND_COVARIANCE_FREEZE_R1.json"),
        ):
            h6.copy_exclusive(old / source_name, destination / destination_name)
        _write_gate_marker(scratch, "H6R_NIS_COVARIANCE_PASS.json", {
            "schema_version": "hartley.h6r.nis_pass.v1", "nis_covariance_pass": True,
            "freeze_sha256": sha256_file(destination / "NIS_AND_COVARIANCE_FREEZE_R1.json"),
        })
    finally:
        if temp.exists():
            h6._safe_remove_tree(temp, scratch / "00_ADMIN")
    return result


def combine_gauge_equivalence(scratch: Path, original_h6: Path) -> dict[str, Any]:
    """Replace only the lossy contact columns in the frozen passing H6 metrics."""
    _load_required_pass(scratch / "00_ADMIN/H6R_CONTACT_RECOVERY_PASS.json", {
        "old_format_blocker_reproduced": True, "full_precision_contact_gate_pass": True,
    }, "H6R contact recovery")
    destination = _gauge_root(scratch) / "09_EQUIVALENCE"
    _require_new_directory(destination)
    source_rows = h6._rows(original_h6 / "03_ANALYSIS/08_EQUIVALENCE/GAUGE_EQUIVALENCE_SUMMARY.csv")
    source_by_id = {row["run_id"]: row for row in source_rows}
    zero = _member_root(scratch, "H6R_YAW_000") / "CONTACT_STATE_FLOAT64.npz"
    _time0, _rows0, active0, xyz0 = read_contact_npz(zero)
    output: list[dict[str, Any]] = []
    for run_id, yaw, _directory in YAW_MEMBERS:
        if yaw == 0.0:
            continue
        old = dict(source_by_id[OLD_RUN_ID[run_id]])
        _time, _indices, active, xyz = read_contact_npz(_member_root(scratch, run_id) / "CONTACT_STATE_FLOAT64.npz")
        errors, _coordinate = _inverse_gauge_epoch_max(active0, xyz0, active, xyz, yaw)
        old["run_id"] = run_id
        for probability, label in ((0.5, "p50"), (0.9, "p90"), (0.95, "p95"), (0.99, "p99")):
            old[f"maximum_matched_contact_position_difference_m_{label}"] = float(np.quantile(errors, probability))
        old["maximum_matched_contact_position_difference_m_max"] = float(np.max(errors))
        old["maximum_matched_contact_position_difference_m_tolerance"] = CONTACT_TOLERANCE_M
        old["pass"] = all((
            float(old["orientation_geodesic_difference_rad_max"]) <= float(old["orientation_geodesic_difference_rad_tolerance"]),
            float(old["velocity_difference_m_per_s_max"]) <= float(old["velocity_difference_m_per_s_tolerance"]),
            float(old["position_difference_m_max"]) <= float(old["position_difference_m_tolerance"]),
            float(old["maximum_matched_contact_position_difference_m_max"]) <= CONTACT_TOLERANCE_M,
            float(old["gyro_bias_difference_rad_per_s_max"]) <= float(old["gyro_bias_difference_rad_per_s_tolerance"]),
            float(old["accelerometer_bias_difference_m_per_s2_max"]) <= float(old["accelerometer_bias_difference_m_per_s2_tolerance"]),
            float(old["relative_yaw_increment_difference_rad_max"]) <= float(old["relative_yaw_increment_difference_rad_tolerance"]),
            float(old["innovation_norm_difference_max"]) <= float(old["innovation_norm_difference_tolerance"]),
            float(old["native_yaw_offset_residual_rad_max"]) <= float(old["native_yaw_offset_residual_rad_tolerance"]),
            float(old["covariance_congruence_relative_frobenius_difference_max"]) <= float(old["covariance_congruence_relative_frobenius_difference_tolerance"]),
            old["contact_event_ledger_identical"] == "true",
            old["contact_identity_set_and_dimension_match_every_epoch"] == "true",
        ))
        output.append(old)
    summary = destination / "H6R_GAUGE_EQUIVALENCE_SUMMARY.csv"
    exclusive_csv(summary, output, tuple(output[0]))
    passed = all(row["pass"] for row in output)
    freeze = {
        "schema_version": "hartley.h6r.gauge_equivalence.v1", "gauge_equivalence_pass": passed,
        "member_count": len(output), "original_frozen_non_contact_metrics_reused_after_exact_parity": True,
        "contact_metric_source": "CONTACT_STATE_FLOAT64.npz", "original_h6_summary_modified": False,
        "original_tolerance_changed": False, "summary_sha256": sha256_file(summary),
        "reference_open_count": 0, "trace_open_count": 0,
    }
    exclusive_json(destination / "H6R_GAUGE_EQUIVALENCE_FREEZE.json", freeze)
    if not passed:
        raise HartleyH6RError(BLOCKERS["contact"])
    _write_gate_marker(scratch, "H6R_GAUGE_EQUIVALENCE_PASS.json", {
        "schema_version": "hartley.h6r.gauge_pass.v1", "gauge_equivalence_pass": True,
        "equivalence_freeze_sha256": sha256_file(destination / "H6R_GAUGE_EQUIVALENCE_FREEZE.json"),
    })
    return freeze


def finalize(scratch: Path, original_h6: Path) -> dict[str, Any]:
    _load_required_pass(scratch / "00_ADMIN/H6R_NIS_COVARIANCE_PASS.json",
                        {"nis_covariance_pass": True}, "H6R NIS/covariance")
    verify_original_h6_post(scratch)
    contact = json.loads((_gauge_root(scratch) / "08_PRECISION_RECOVERY/CONTACT_PRECISION_RECOVERY_FREEZE.json").read_text())
    gauge = json.loads((_gauge_root(scratch) / "09_EQUIVALENCE/H6R_GAUGE_EQUIVALENCE_FREEZE.json").read_text())
    obs = json.loads((_observability_root(scratch) / "02_BIAS_AUGMENTED/OBSERVABILITY_ANALYSIS_FREEZE_R1.json").read_text())
    nis = json.loads((_observability_root(scratch) / "03_NIS_AND_COVARIANCE/NIS_AND_COVARIANCE_FREEZE_R1.json").read_text())
    if not (contact["full_precision_contact_gate_pass"] and gauge["gauge_equivalence_pass"] and
            obs["ideal_rank_nullity_pass"] and obs["bias_augmented_known_gauge_confirmed"]):
        raise HartleyH6RError("H6R finalizer received incomplete passing evidence")
    scientific_core = _core_output_identities(scratch)
    scientific_core_digest = hashlib.sha256(json.dumps(
        scientific_core, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    original_status = original_h6 / "03_ANALYSIS/11_REPORT/LSE01_H6_STATUS.json"
    original_report = original_h6 / "03_ANALYSIS/11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md"
    preservation = {
        "status_role": "ORIGINAL_H6/11_REPORT/LSE01_H6_STATUS.json",
        "status_sha256": sha256_file(original_status),
        "report_role": "ORIGINAL_H6/11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md",
        "report_sha256": sha256_file(original_report),
        "original_h6_status_preserved": True,
    }
    member_freezes = [json.loads((_member_root(scratch, run_id) / "MEMBER_FREEZE.json").read_text())
                      for run_id, _yaw, _directory in YAW_MEMBERS]
    provenances = [item["runtime_provenance"] for item in member_freezes]
    identity_fields = (
        "data_mode", "raw_source_sha256", "prefix_sha256", "cache_sha256",
        "contact_event_input_ledger_sha256", "code_commit", "scoped_source_manifest_sha256",
        "native_executable_sha256", "propagation_calls", "eq61_calls", "eq52_calls",
    )
    if any(any(current[key] != provenances[0][key] for key in identity_fields) for current in provenances[1:]):
        raise HartleyH6RError("H6R replay provenance identity mismatch")
    forbidden_fields = (
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input", "LegSA_output_solver_input",
        "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric",
    )
    if any(any(current[key] is not False for key in forbidden_fields) or
           current["old_runtime_input_count"] != 0 for current in provenances):
        raise HartleyH6RError("H6R forbidden runtime provenance mismatch")
    status = status_template(PASS_TERMINAL)
    status.update({
        "schema_version": "hartley.h6r.status.v1", "state_rows": STATE_ROWS,
        "contact_tolerance_m": CONTACT_TOLERANCE_M, "selected_window_count": obs["selected_window_count"],
        "topology_conditioned_nis_group_count": nis["topology_conditioned_nis_group_count"],
        "original_h6_preservation": preservation,
        "runtime_provenance": provenances[0], "all_seven_member_provenance_identical": True,
        "mandatory_scientific_core_output_count": len(scientific_core),
        "mandatory_scientific_core_digest": scientific_core_digest,
        "scratch_retention": "RETAIN_ACCEPTED_H6R_WHILE_EXTERNAL_STORAGE_UNHEALTHY",
        "cleanup_performed_by_worker": False, "cleanup_paths": [], "bytes_reclaimed": 0,
    })
    report_root = _analysis_root(scratch) / "11_REPORT"
    _require_new_directory(report_root)
    exclusive_json(report_root / "LSE01_H6R_STATUS.json", status)
    maxima = h6._rows(_gauge_root(scratch) / "08_PRECISION_RECOVERY/FULL_PRECISION_CONTACT_EQUIVALENCE_SUMMARY.csv")
    report = [
        "# LSE01 H6R full-precision recovery", "", f"Terminal: `{PASS_TERMINAL}`", "",
        "The original blocked H6 transaction and its 0.0005 m tolerance remain unchanged. The exact old",
        "six-significant-digit compatibility stream reproduced all six blocked maxima before the float64",
        "NPZ files were opened. The authoritative float64 comparison passed every epoch, active leg and coordinate.", "",
        "## Full-precision contact maxima", "",
    ]
    report.extend(f"- {row['run_id']}: {row['maximum_contact_vector_difference_m']} m"
                  for row in maxima)
    report.extend([
        "", "The five frozen windows WIN000--WIN004 were reused byte-identically; no window was reselected.",
        "Ideal bias-free nullity is four (three translations and gravity-axis rotation), and the known",
        "four-dimensional gauge is confirmed in the bias-augmented real-trajectory model.", "",
        "NIS is conditioned by contact count, exact identity set, and static/dynamic four-contact periods.",
        "Low NIS is interpreted only as conservative and/or correlated proxy statistics, not accuracy.", "",
        "All reference, trace, GNSS, onboard pose/yaw, LegSA-output and EXT-output access counters are zero.",
        "H7 and EXT06 remain unexecuted.",
    ])
    h6.exclusive_write(report_root / "LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md",
                       ("\n".join(report) + "\n").encode())
    complete_core = _core_output_identities(scratch, include_reports=True)
    core_freeze = report_root / "H6R_CORE_OUTPUT_FREEZE.json"
    exclusive_json(core_freeze, {
        "schema_version": "hartley.h6r.core_output_freeze.v1",
        "all_mandatory_core_outputs_present": True, "files": complete_core,
    })
    _write_gate_marker(scratch, "H6R_FINALIZED_PASS.json", {
        "schema_version": "hartley.h6r.finalized_pass.v1", "finalized_pass": True,
        "terminal_status": PASS_TERMINAL,
        "status_sha256": sha256_file(report_root / "LSE01_H6R_STATUS.json"),
        "report_sha256": sha256_file(report_root / "LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md"),
        "core_output_freeze_sha256": sha256_file(core_freeze),
    })
    return status


def finalize_blocked(scratch: Path, terminal: str, detail: str) -> dict[str, Any]:
    if terminal not in set(BLOCKERS.values()):
        raise HartleyH6RError("invalid H6R blocker terminal")
    report_root = _analysis_root(scratch) / "11_REPORT"
    report_root.mkdir(parents=True, exist_ok=True)
    status_path = report_root / "LSE01_H6R_STATUS.json"
    report_path = report_root / "LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md"
    old_freeze = _gauge_root(scratch) / "08_PRECISION_RECOVERY/OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json"
    candidates: list[Path] = []
    for relative_root in ("01_NATIVE_RAW_H6R", "03_ANALYSIS/09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT",
                          "03_ANALYSIS/10_OBSERVABILITY_R1/FAILURE_EVIDENCE"):
        root = scratch / relative_root
        if root.is_dir():
            candidates.extend(path for path in root.rglob("*") if path.is_file())
    retained: dict[str, dict[str, Any]] = {}
    for path in sorted(set(candidates)):
        role = str(path.relative_to(scratch))
        identity: dict[str, Any] = {"size": path.stat().st_size}
        if path.suffix == ".npz" and not old_freeze.is_file():
            identity["sha256"] = "NOT_OPENED_OR_HASHED_BEFORE_OLD_FORMAT_FREEZE"
        else:
            identity["sha256"] = sha256_file(path)
        retained[role] = identity
    payload = status_template(terminal)
    payload.update({
        "schema_version": "hartley.h6r.status.v1", "authoritative_blocker": terminal,
        "later_gates_executed": False,
        "raw_failure_evidence_retained": any(role.startswith("01_NATIVE_RAW_H6R/") for role in retained),
        "retained_failure_evidence_file_count": len(retained),
        "retained_failure_evidence": retained,
        "failure_detail": terminal,
    })
    if not status_path.exists():
        exclusive_json(status_path, payload)
    if not report_path.exists():
        evidence_roles = "\n".join(f"- `{role}`: `{identity['sha256']}`"
                                   for role, identity in retained.items()) or "- No stable failure file was produced before the gate stopped."
        h6.exclusive_write(report_path, (
            "# LSE01 H6R blocked recovery\n\n"
            f"Terminal: `{terminal}`\n\n"
            "The recovery stopped at the first failed frozen gate. Original H6 evidence and the unchanged "
            "0.0005 m tolerance remain preserved. Later gates, H7, and EXT06 were not executed.\n\n"
            "## Retained failure evidence\n\n" + evidence_roles + "\n"
        ).encode())
    return payload


def write_internal_failure_ledger(scratch: Path, command: str, detail: str) -> None:
    if not scratch.exists():
        return
    path = scratch / "00_ADMIN/H6R_INTERNAL_FAILURE_LEDGER.json"
    if path.exists():
        return
    exclusive_json(path, {
        "schema_version": "hartley.h6r.internal_failure.v1", "command": command,
        "scientific_terminal_claimed": False, "detail": detail[:2000],
        "later_gates_authorized": False,
    })


def publication_sources(scratch: Path) -> dict[str, Path]:
    analysis = _analysis_root(scratch)
    roots = ("09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT", "10_OBSERVABILITY_R1")
    result: dict[str, Path] = {}
    for root in roots:
        for path in sorted((analysis / root).rglob("*")):
            if path.is_file():
                result[str(path.relative_to(analysis))] = path
    for name in ("LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md", "LSE01_H6R_STATUS.json",
                 "H6R_CORE_OUTPUT_FREEZE.json"):
        path = analysis / "11_REPORT" / name
        result[f"11_REPORT/{name}"] = path
    return result


def publish_exclusive(scratch: Path, stage_root: Path) -> dict[str, Any]:
    finalized = _load_required_pass(scratch / "00_ADMIN/H6R_FINALIZED_PASS.json", {
        "finalized_pass": True, "terminal_status": PASS_TERMINAL,
    }, "H6R finalization")
    report_root = _analysis_root(scratch) / "11_REPORT"
    status_path = report_root / "LSE01_H6R_STATUS.json"
    report_path = report_root / "LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md"
    if (sha256_file(status_path) != finalized.get("status_sha256") or
            sha256_file(report_path) != finalized.get("report_sha256") or
            json.loads(status_path.read_text()).get("terminal_status") != PASS_TERMINAL):
        raise HartleyH6RError("finalized status/report identity mismatch")
    core_freeze_path = report_root / "H6R_CORE_OUTPUT_FREEZE.json"
    if sha256_file(core_freeze_path) != finalized.get("core_output_freeze_sha256"):
        raise HartleyH6RError("core-output freeze identity mismatch")
    frozen_core = json.loads(core_freeze_path.read_text())
    current_core = _core_output_identities(scratch, include_reports=True)
    if frozen_core.get("files") != current_core or frozen_core.get("all_mandatory_core_outputs_present") is not True:
        raise HartleyH6RError("mandatory core-output hash preflight failed")
    bindings = json.loads((scratch / "00_ADMIN/H6R_LOCAL_PATH_BINDINGS.json").read_text())
    if stage_root.resolve() != Path(bindings["external_stage"]).resolve():
        raise HartleyH6RError("external publication stage root identity mismatch")
    files = publication_sources(scratch)
    required_relatives = set(CORE_OUTPUT_RELATIVES) | {
        "11_REPORT/LSE01_H6R_STATUS.json", "11_REPORT/LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md",
        "11_REPORT/H6R_CORE_OUTPUT_FREEZE.json",
    }
    if not required_relatives.issubset(files):
        raise HartleyH6RError("H6R local publication set is incomplete")
    if not files or any(not source.is_file() or not os.access(source, os.R_OK) for source in files.values()):
        raise HartleyH6RError("H6R local publication source preflight failed")
    for source in files.values():
        if source.suffix.lower() in {".json", ".md", ".csv", ".yaml", ".yml", ".cfg"}:
            text = source.read_text(errors="strict")
            absolute_prefixes = ("/" + "home/", "/" + "mnt/")
            if any(prefix in text for prefix in absolute_prefixes):
                raise HartleyH6RError(f"absolute path leaked into public artifact: {source.name}")
    source_identities = {
        relative: {"sha256": sha256_file(source), "size": source.stat().st_size}
        for relative, source in files.items()
    }
    protected = ("09_GAUGE_ENSEMBLE/", "10_OBSERVABILITY/",
                 "11_REPORT/LSE01_H6_STATUS.json",
                 "11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md")
    meta_relatives = (
        "11_REPORT/H6R_EXTERNAL_PUBLICATION_MANIFEST.json",
        "11_REPORT/H6R_EXTERNAL_PUBLICATION_PARITY.json",
        "11_REPORT/ORIGINAL_H6_POST_PUBLICATION_PRESERVATION.json",
    )
    destinations = {relative: stage_root / relative for relative in (*files, *meta_relatives)}
    if any(relative.startswith(protected) for relative in destinations):
        raise HartleyH6RError("publication preflight intersects protected original H6 paths")
    if any(path.exists() for path in destinations.values()):
        raise FileExistsError("H6R publication destination already exists")
    rows = []
    try:
        for relative, source in files.items():
            destination = destinations[relative]
            digest = h6.copy_exclusive(source, destination)
            published_hash = sha256_file(destination)
            published_size = destination.stat().st_size
            rows.append({
                "relative_path": relative, "source_sha256": digest,
                "source_size": source_identities[relative]["size"],
                "published_sha256": published_hash, "published_size": published_size,
                "bytes_equal": digest == published_hash and
                               source_identities[relative]["size"] == published_size,
            })
    except BaseException as error:
        exclusive_json(scratch / "04_PUBLICATION/H6R_PARTIAL_PUBLICATION_FAILURE_LEDGER.json", {
            "schema_version": "hartley.h6r.partial_publication_failure.v1",
            "completed_copy_count": len(rows), "parity_claimed": False,
            "failure": str(error)[:1000],
        })
        raise
    payload = {"schema_version": "hartley.h6r.publication.v1", "file_count": len(rows),
               "all_published_bytes_equal": all(row["bytes_equal"] for row in rows), "files": rows,
               "original_h6_publication_paths_touched": not all(
                   not row["relative_path"].startswith(protected) for row in rows),
               "local_preflight_complete_before_first_write": True}
    if not payload["all_published_bytes_equal"] or payload["original_h6_publication_paths_touched"]:
        raise HartleyH6RError("H6R publication byte parity failure")
    def record_partial(error: BaseException) -> None:
        ledger = scratch / "04_PUBLICATION/H6R_PARTIAL_PUBLICATION_FAILURE_LEDGER.json"
        if not ledger.exists():
            exclusive_json(ledger, {
                "schema_version": "hartley.h6r.partial_publication_failure.v1",
                "completed_copy_count": len(rows), "parity_claimed": False,
                "failure": str(error)[:1000],
            })

    try:
        preservation = verify_original_h6_post(scratch, "POST_PUBLICATION")
    except BaseException as error:
        record_partial(error); raise
    payload["original_h6_post_publication_preserved"] = preservation["all_original_h6_bytes_preserved"]
    publication_root = scratch / "04_PUBLICATION"
    manifest = publication_root / "H6R_EXTERNAL_PUBLICATION_MANIFEST.json"
    try:
        exclusive_json(manifest, payload)
        h6.copy_exclusive(manifest, destinations[meta_relatives[0]])
    except BaseException as error:
        record_partial(error); raise
    manifest_equal = (sha256_file(manifest) == sha256_file(destinations[meta_relatives[0]]) and
                      manifest.stat().st_size == destinations[meta_relatives[0]].stat().st_size)
    parity = {**payload, "manifest_sha256": sha256_file(manifest),
              "manifest_published_bytes_equal": manifest_equal}
    parity_path = publication_root / "H6R_EXTERNAL_PUBLICATION_PARITY.json"
    try:
        exclusive_json(parity_path, parity)
        h6.copy_exclusive(parity_path, destinations[meta_relatives[1]])
    except BaseException as error:
        record_partial(error); raise
    parity["parity_file_published_bytes_equal"] = (
        sha256_file(parity_path) == sha256_file(destinations[meta_relatives[1]]) and
        parity_path.stat().st_size == destinations[meta_relatives[1]].stat().st_size
    )
    proof = publication_root / "ORIGINAL_H6_POST_PUBLICATION_PRESERVATION.json"
    try:
        exclusive_json(proof, {
        "schema_version": "hartley.h6r.original_preservation_public.v1",
        "original_h6_local_role_count": 4, "original_h6_external_file_count": 72,
        "all_original_h6_bytes_preserved": preservation["all_original_h6_bytes_preserved"],
        "private_manifest_sha256": sha256_file(
            scratch / "00_ADMIN/ORIGINAL_H6_POST_PUBLICATION_PRESERVATION.json"
        ),
        })
        h6.copy_exclusive(proof, destinations[meta_relatives[2]])
    except BaseException as error:
        record_partial(error); raise
    parity["preservation_proof_published_bytes_equal"] = (
        sha256_file(proof) == sha256_file(destinations[meta_relatives[2]]) and
        proof.stat().st_size == destinations[meta_relatives[2]].stat().st_size
    )
    if not all((parity["manifest_published_bytes_equal"], parity["parity_file_published_bytes_equal"],
                parity["preservation_proof_published_bytes_equal"],
                parity["original_h6_post_publication_preserved"])):
        raise HartleyH6RError("H6R publication metadata parity failure")
    return parity


def status_template(terminal_status: str) -> dict[str, Any]:
    passed = terminal_status == PASS_TERMINAL
    return {
        "terminal_status": terminal_status, "original_h6_status_preserved": True,
        "original_tolerance_changed": False, "old_format_blocker_reproduced": passed,
        "full_precision_contact_gate_pass": passed, "gauge_equivalence_pass": passed,
        "ideal_observability_gauge_dimension": 4 if passed else None,
        "bias_augmented_known_gauge_confirmed": passed,
        "reference_open_count": 0, "trace_open_count": 0, "GNSS_input_count": 0,
        "Go2_onboard_pose_or_yaw_input_count": 0, "LegSA_output_input_count": 0,
        "EXT_output_input_count": 0, "h7_authorized": passed, "h7_executed": False,
        "ext06_executed": False, "absolute_yaw_RMSE_computed": False,
        "absolute_position_RMSE_computed": False, "relative_pose_error_computed": False,
    }
