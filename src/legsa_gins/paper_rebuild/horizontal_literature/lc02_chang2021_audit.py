"""Static R0--R4 audit support for the Chang et al. (2021) LC02 candidate.

This module deliberately contains no navigation or filtering implementation.  It
validates the tracked source/mathematics/input contracts, performs the narrowly
authorized BY2 field-availability audit, and publishes an exact, non-overwriting
copy of the tracked audit payload.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
import stat
import struct
import subprocess
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml


METHOD_ID = "LC02_CHANG2021_FSTCKF"
TERMINAL_STATUS = "NO_GO_LC02_CHANG2021_FSTCKF_AS_FORMAL_PRIMARY"
EXPECTED_HEAD = "7770837a00dbb3a465317eded1b77c6db6861c1c"
AUTHORIZED_COMMIT_SUBJECT = "Add Chang 2021 FSTCKF LC02 contracts"
PAPER_SHA256 = "8c9b65fe3842f9580b69ffd02f728412861c932c166d1cb4fc9950fa0aaf1da7"
PAPER_BYTES = 9_843_279
PAPER_PAGES = 15
CANONICAL_HASHES = {
    "scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py":
        "00a54aac97ec54715c47dda9350635aa3ea3e969e5deb152e52e33614a6a6480",
    "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py":
        "d021a503bc91dbd6a194182478770a1457cf0ca615c7d3adb2f7a6f68eadea16",
}
STAGE08_RELATIVE = Path(
    "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/08_LC02_YIN2023_RAEKF"
)
STAGE09_RELATIVE = Path(
    "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/09_LC02_CHANG2021_FSTCKF"
)
STAGE08_MANIFEST_SHA256 = (
    "17a55c6b1f2c02fa5f06b7ccb5c0d74cb01538a03cc2aa484f76f32b37d74729"
)
STAGE08_FILE_COUNT = 79
STAGE09_INITIAL_REVIEW_PREIMAGE_SHA256 = (
    "53ea9c956243ec8bc53c036d7d52bea550b4ffd459dce4743b60b6ab0c5af3b1"
)
STAGE09_REPAIR_PREIMAGE_SHA256 = (
    "ca78fe6d62cea131bebd4d6bd2a1bf7920e327dc0569146f3956a1ead3823ba1"
)
STAGE09_REPAIR_MODE = "GUARDED_TWO_RENAME_WITH_VERIFIED_ROLLBACK_NON_OVERWRITING"

AUTHORIZED_TRACKED_FILES = {
    "scripts/paper_rebuild/audit_lc02_chang2021_r0_r4.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/lc02_chang2021_audit.py",
    "tests/paper_rebuild/test_lc02_chang2021_r0_r4.py",
}

ALLOWED_PROVENANCE = {
    "PAPER_DIRECT",
    "PAPER_DERIVED",
    "CITED_SOURCE_COMPLETION",
    "OFFICIAL_CODE",
    "BY2_INSTANTIATION",
    "CURRENTLY_UNKNOWN",
}

EXPECTED_ARTIFACTS = frozenset(
    {
        "00_ACTIVE_METHOD_REGISTRY/ACTIVE_SOLUTION_LEVEL_LC_REGISTRY_R1.csv",
        "00_ACTIVE_METHOD_REGISTRY/LC02_CANDIDATE_HISTORY.md",
        "01_SOURCE_REGISTRY/LC02_CHANG_OFFICIAL_CODE_SEARCH.md",
        "01_SOURCE_REGISTRY/LC02_CHANG_SOURCE_REGISTRY.csv",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_FULL_METHOD_CARD.md",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_EQUATION_REGISTRY.csv",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_FIGURE_REGISTRY.csv",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_PARAMETER_REGISTRY.csv",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_EXPERIMENT_REGISTRY.csv",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_CLAIM_BOUNDARY.md",
        "03_CITED_SOURCE_CLOSURE/CHANG2021_CKF_SOURCE_MAP.csv",
        "03_CITED_SOURCE_CLOSURE/CHANG2021_EQ12_SOURCE_PROOF.md",
        "03_CITED_SOURCE_CLOSURE/CITED_SOURCE_CLOSURE_SUMMARY.md",
        "04_METHOD_CONTRACTS/CHANG2021_STATE_AND_DYNAMICS_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_MEASUREMENT_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_FRAME_SIGN_RESET_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_NOISE_AND_INITIALIZATION_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_CKF_CORE_IDENTITY_DECISION.json",
        "04_METHOD_CONTRACTS/CHANG2021_CKF_FINAL_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_EQ12_GENERALIZED_INVERSE_DECISION.json",
        "04_METHOD_CONTRACTS/CHANG2021_BETA_TO_15_STATE_MAPPING.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_AI_VECTOR_DECISION.json",
        "04_METHOD_CONTRACTS/CHANG2021_MEMBERSHIP_FUNCTIONS.csv",
        "04_METHOD_CONTRACTS/CHANG2021_FUZZY_RULES.csv",
        "04_METHOD_CONTRACTS/CHANG2021_TS_AGGREGATION_DECISION.json",
        "04_METHOD_CONTRACTS/CHANG2021_FUZZY_CONTROLLER_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_BY2_INPUT_CONTRACT.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_FUTURE_C00_GATE.yaml",
        "04_METHOD_CONTRACTS/CHANG2021_FORMAL_ADMISSION_RUBRIC.yaml",
        "05_NON_DUPLICATION_AUDIT/LC01_VS_CHANG2021_INFORMATION_STRUCTURE.csv",
        "05_NON_DUPLICATION_AUDIT/LC01_VS_CHANG2021_METHOD_IDENTITY.json",
        "05_NON_DUPLICATION_AUDIT/LC01_VS_CHANG2021_COMPLEMENTARITY.md",
        "05_NON_DUPLICATION_AUDIT/LC02_CHANG2021_NO_GO_REASON.md",
        "05_NON_DUPLICATION_AUDIT/LC02_REPLACEMENT_CANDIDATE_COMPARISON.md",
        "11_REPORT/LC02_CHANG_R0_R4_FULL_REPORT.md",
        "11_REPORT/LC02_CHANG_R0_R4_STATUS.json",
        "11_REPORT/LC02_CHANG_FORMAL_ADMISSION_DECISION.md",
    }
)

EXPECTED_DOC_ARTIFACTS = frozenset(
    {
        "00_ACTIVE_METHOD_REGISTRY/LC02_CANDIDATE_HISTORY.md",
        "01_SOURCE_REGISTRY/LC02_CHANG_OFFICIAL_CODE_SEARCH.md",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_CLAIM_BOUNDARY.md",
        "02_FULL_PAPER_REVIEW/LC02_CHANG_FULL_METHOD_CARD.md",
        "03_CITED_SOURCE_CLOSURE/CHANG2021_EQ12_SOURCE_PROOF.md",
        "03_CITED_SOURCE_CLOSURE/CITED_SOURCE_CLOSURE_SUMMARY.md",
        "05_NON_DUPLICATION_AUDIT/LC01_VS_CHANG2021_COMPLEMENTARITY.md",
        "05_NON_DUPLICATION_AUDIT/LC02_CHANG2021_NO_GO_REASON.md",
        "05_NON_DUPLICATION_AUDIT/LC02_REPLACEMENT_CANDIDATE_COMPARISON.md",
        "11_REPORT/LC02_CHANG_FORMAL_ADMISSION_DECISION.md",
        "11_REPORT/LC02_CHANG_R0_R4_FULL_REPORT.md",
    }
)
EXPECTED_CONFIG_ARTIFACTS = EXPECTED_ARTIFACTS - EXPECTED_DOC_ARTIFACTS
EXPECTED_POSTCOMMIT_PATHS = frozenset(
    {
        *(
            f"configs/paper_rebuild/horizontal_literature/lc02_chang2021/{relative}"
            for relative in EXPECTED_CONFIG_ARTIFACTS
        ),
        *(
            f"docs/paper_rebuild/horizontal_literature/lc02_chang2021/{relative}"
            for relative in EXPECTED_DOC_ARTIFACTS
        ),
        *AUTHORIZED_TRACKED_FILES,
    }
)

# The final review correction preserves the same exact 37 stage-relative paths.
PREVIOUS_ARTIFACTS = EXPECTED_ARTIFACTS

EXPECTED_BRANCH_LEVELS = {
    "CHANG2021_CKF": "FAITHFUL_MODULE_REPRODUCTION",
    "CHANG2021_STCKF_IFF": "PAPER_DERIVED_POLICY_BASELINE",
    "CHANG2021_STCKF_FB": "PAPER_DERIVED_POLICY_BASELINE",
    "CHANG2021_FSTCKF": "DIAGNOSTIC_ONLY",
}

EXPECTED_GATE_RESULTS = {
    "paper_and_source_identity_closed": "PASS",
    "base_15_state_dynamics_closed": "FAIL",
    "six_dimensional_measurement_closed": "PASS",
    "ckf_core_identity_unique": "PASS",
    "eq12_generalized_inverse_unique": "FAIL",
    "beta_to_all_fifteen_ai_unique": "FAIL",
    "innovation_expectation_and_startup_unique": "FAIL",
    "fig4_membership_functions_exact": "PASS",
    "ts_aggregation_unique": "FAIL",
    "all_parameters_closed": "FAIL",
    "by2_input_compatible": "FAIL",
    "distinct_from_lc01": "PASS",
}

EXPECTED_FIGURE_SEMANTICS = {
    1: (3, "METHOD", "METHOD_CONTRACT"),
    2: (4, "METHOD", "METHOD_CONTRACT"),
    3: (6, "METHOD", "METHOD_PARAMETER_PROVENANCE"),
    4: (6, "METHOD", "METHOD_PARAMETER_PROVENANCE"),
    5: (7, "METHOD", "METHOD_CONTRACT"),
    6: (8, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    7: (9, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    8: (9, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    9: (10, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    10: (11, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    11: (11, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    12: (13, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    13: (13, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
    14: (14, "PAPER_EXPERIMENT", "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"),
}

EXPECTED_EXPERIMENT_SEMANTICS = {
    **{
        f"FIGURE_{index:02d}": (
            "FIGURE",
            "SYNTHETIC_PAPER_EXPERIMENT" if index <= 12 else "REAL_EXTERNAL_PAPER_DATA",
            "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE",
        )
        for index in range(6, 15)
    },
    **{
        f"TABLE_{index:02d}": (
            "TABLE",
            "REAL_EXTERNAL_PAPER_DATA" if index == 7 else "SYNTHETIC_PAPER_EXPERIMENT",
            (
                "PAPER_PARAMETER_PROVENANCE_ONLY"
                if index <= 3
                else "PAPER_CLAIM_CONTEXT_ONLY_NO_ACTIVE_PERFORMANCE_EVIDENCE"
            ),
        )
        for index in range(1, 8)
    },
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_postcommit_scope(changed_paths: Iterable[str]) -> frozenset[str]:
    """Require the exact 37-artifact plus three-support-file commit scope."""

    changed = frozenset(changed_paths)
    if changed != EXPECTED_POSTCOMMIT_PATHS:
        raise ValueError(
            "postcommit changed-path set mismatch; "
            f"missing={sorted(EXPECTED_POSTCOMMIT_PATHS-changed)}, "
            f"unexpected={sorted(changed-EXPECTED_POSTCOMMIT_PATHS)}"
        )
    return changed


def verify_task_head(root: Path) -> dict[str, Any]:
    """Accept only the task anchor or its exact authorized one-commit child."""

    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", *arguments], cwd=root, text=True, stderr=subprocess.STDOUT
        ).strip()

    head = git("rev-parse", "HEAD")
    if head == EXPECTED_HEAD:
        return {
            "head": head,
            "mode": "UNCOMMITTED_ARTIFACT_BUILD_AT_TASK_START_HEAD",
            "task_start_head": EXPECTED_HEAD,
        }
    parents = git("rev-list", "--parents", "-n", "1", head).split()
    if len(parents) != 2 or parents[1] != EXPECTED_HEAD:
        raise ValueError("HEAD is not the exact one-commit descendant of task start")
    subject = git("show", "-s", "--format=%s", head)
    if subject != AUTHORIZED_COMMIT_SUBJECT:
        raise ValueError("postcommit HEAD has an unauthorized subject")
    changed = [
        value
        for value in git("diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines()
        if value
    ]
    validate_postcommit_scope(changed)
    return {
        "head": head,
        "mode": "AUTHORIZED_EXACT_ONE_COMMIT_DESCENDANT",
        "task_start_head": EXPECTED_HEAD,
        "parent": parents[1],
        "subject": subject,
        "changed_files": changed,
    }


def payload_aggregate_sha256(payload: dict[str, bytes]) -> str:
    records = "".join(
        f"{hashlib.sha256(raw).hexdigest()}  {relative}\n"
        for relative, raw in sorted(payload.items())
    )
    return hashlib.sha256(records.encode("utf-8")).hexdigest()


def normalized_tree_manifest(root: Path) -> tuple[int, str]:
    """Return count and hash of sorted ``sha256  relative-path`` records."""

    records: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink forbidden in frozen tree: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"special entry forbidden in frozen tree: {path}")
        records.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n")
    return len(records), hashlib.sha256("".join(records).encode("utf-8")).hexdigest()


def load_local_paths(local_yaml: Path) -> dict[str, Path]:
    raw = yaml.safe_load(local_yaml.read_text(encoding="utf-8"))
    values = raw.get("paths", {}) if isinstance(raw, dict) else {}
    required = ("by2_fix_root", "by2_go2_body", "clean_root")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError(f"local path aliases missing: {missing}")
    return {key: Path(values[key]) for key in required}


def _decode_bytes_repr(text: str) -> bytes:
    value = ast.literal_eval(text.strip())
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, list):
        return bytes(int(item) & 0xFF for item in value)
    raise ValueError(f"unsupported byte representation: {type(value).__name__}")


def _matrix_from_upper(values: Iterable[float]) -> np.ndarray:
    nn, ne, nd, ee, ed, dd = values
    return np.asarray([[nn, ne, nd], [ne, ee, ed], [nd, ed, dd]], dtype=float)


def audit_gnss1_solution_stream(path: Path) -> dict[str, Any]:
    """Decode only selected PVT/NAV-COV rows from the multiplexed GNSS1 file.

    Every serialized row must be streamed to find the message-name field.  The
    payload field is semantically decoded only for PVT and NAV-COV.  No RAWX,
    SFRBX, RTCM, or other message payload is decoded or retained.
    """

    pvt: list[dict[str, Any]] = []
    cov: list[dict[str, Any]] = []
    decode_errors: list[str] = []
    nonselected = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        header = next(handle)
        for line_number, serialized_line in enumerate(handle, start=2):
            if ",UBX-NAV-PVT," in serialized_line:
                kind = "PVT"
            elif ",UBX-NAV-COV," in serialized_line:
                kind = "COV"
            else:
                nonselected += 1
                continue
            row = next(csv.DictReader([header, serialized_line]))
            try:
                frame = _decode_bytes_repr(row["data"])
                stamp_ns = int(row["stamp.secs"]) * 1_000_000_000 + int(
                    row["stamp.nsecs"]
                )
                if kind == "PVT":
                    if frame[:4] != b"\xb5\x62\x01\x07" or len(frame) < 100:
                        raise ValueError("invalid UBX-NAV-PVT frame")
                    flags = frame[27]
                    pvt.append(
                        {
                            "stamp_ns": stamp_ns,
                            "itow_ms": struct.unpack("<I", frame[6:10])[0],
                            "fix_type": frame[26],
                            "gnss_fix_ok": flags & 1,
                            "diff_soln": (flags >> 1) & 1,
                            "carr_soln": (flags >> 6) & 3,
                            "longitude_deg": struct.unpack("<i", frame[30:34])[0]
                            * 1e-7,
                            "latitude_deg": struct.unpack("<i", frame[34:38])[0]
                            * 1e-7,
                            "height_m": struct.unpack("<i", frame[38:42])[0] * 1e-3,
                            "hmsl_m": struct.unpack("<i", frame[42:46])[0] * 1e-3,
                            "hacc_m": struct.unpack("<I", frame[46:50])[0] * 1e-3,
                            "vacc_m": struct.unpack("<I", frame[50:54])[0] * 1e-3,
                            "vn_mps": struct.unpack("<i", frame[54:58])[0] * 1e-3,
                            "ve_mps": struct.unpack("<i", frame[58:62])[0] * 1e-3,
                            "vd_mps": struct.unpack("<i", frame[62:66])[0] * 1e-3,
                            "sacc_mps": struct.unpack("<I", frame[74:78])[0] * 1e-3,
                            "pdop": struct.unpack("<H", frame[82:84])[0] * 0.01,
                        }
                    )
                else:
                    if frame[:4] != b"\xb5\x62\x01\x36" or len(frame) < 72:
                        raise ValueError("invalid UBX-NAV-COV frame")
                    position = _matrix_from_upper(struct.unpack("<6f", frame[22:46]))
                    velocity = _matrix_from_upper(struct.unpack("<6f", frame[46:70]))
                    cov.append(
                        {
                            "stamp_ns": stamp_ns,
                            "itow_ms": struct.unpack("<I", frame[6:10])[0],
                            "version": frame[10],
                            "position_valid": frame[11],
                            "velocity_valid": frame[12],
                            "position_covariance": position,
                            "velocity_covariance": velocity,
                        }
                    )
            except (ValueError, SyntaxError, struct.error) as exc:
                decode_errors.append(f"{line_number}:{kind}:{exc}")

    if not pvt or not cov:
        raise ValueError("selected GNSS1 PVT/NAV-COV stream is empty")
    pvt.sort(key=lambda item: item["itow_ms"])
    cov.sort(key=lambda item: item["itow_ms"])
    pvt_itow = [item["itow_ms"] for item in pvt]
    cov_itow = [item["itow_ms"] for item in cov]
    p_eigen = [np.linalg.eigvalsh(item["position_covariance"]) for item in cov]
    v_eigen = [np.linalg.eigvalsh(item["velocity_covariance"]) for item in cov]

    def span(values: list[float]) -> dict[str, float]:
        return {
            "minimum": float(min(values)),
            "median": float(np.median(values)),
            "maximum": float(max(values)),
        }

    result: dict[str, Any] = {
        "source_alias": "BY2_FIX_ROOT/gnss1-raw.csv",
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "serialized_rows_scanned_for_name": len(pvt) + len(cov) + nonselected,
        "nonselected_payload_semantic_decode_count": 0,
        "pvt_count": len(pvt),
        "nav_cov_count": len(cov),
        "decode_error_count": len(decode_errors),
        "exact_itow_join_count": sum(a == b for a, b in zip(pvt_itow, cov_itow)),
        "unique_pvt_itow_count": len(set(pvt_itow)),
        "unique_cov_itow_count": len(set(cov_itow)),
        "first_itow_ms": pvt_itow[0],
        "last_itow_ms": pvt_itow[-1],
        "itow_step_ms_values": sorted(
            {right - left for left, right in zip(pvt_itow, pvt_itow[1:])}
        ),
        "pvt_first_stamp_ns": min(item["stamp_ns"] for item in pvt),
        "pvt_last_stamp_ns": max(item["stamp_ns"] for item in pvt),
        "fix_type_values": sorted({item["fix_type"] for item in pvt}),
        "gnss_fix_ok_values": sorted({item["gnss_fix_ok"] for item in pvt}),
        "diff_soln_values": sorted({item["diff_soln"] for item in pvt}),
        "carr_soln_values": sorted({item["carr_soln"] for item in pvt}),
        "hacc_m": span([item["hacc_m"] for item in pvt]),
        "vacc_m": span([item["vacc_m"] for item in pvt]),
        "sacc_mps": span([item["sacc_mps"] for item in pvt]),
        "pdop": span([item["pdop"] for item in pvt]),
        "position_cov_valid_count": sum(item["position_valid"] == 1 for item in cov),
        "velocity_cov_valid_count": sum(item["velocity_valid"] == 1 for item in cov),
        "position_cov_psd_count": sum(eigen[0] >= -1e-12 for eigen in p_eigen),
        "velocity_cov_psd_count": sum(eigen[0] >= -1e-12 for eigen in v_eigen),
        "position_cov_min_eigenvalue": float(min(eigen[0] for eigen in p_eigen)),
        "velocity_cov_min_eigenvalue": float(min(eigen[0] for eigen in v_eigen)),
        "position_std_m": {},
        "velocity_std_mps": {},
    }
    for index, axis in enumerate(("N", "E", "D")):
        result["position_std_m"][axis] = span(
            [math.sqrt(float(item["position_covariance"][index, index])) for item in cov]
        )
        result["velocity_std_mps"][axis] = span(
            [math.sqrt(float(item["velocity_covariance"][index, index])) for item in cov]
        )
    return result


def audit_go2_imu_stream(path: Path) -> dict[str, Any]:
    """Parse only terminated records' timestamps, gyro and accelerometer vectors."""

    full_digest = hashlib.sha256()
    prefix_digest = hashlib.sha256()
    full_bytes = 0
    last_terminator_end = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            full_digest.update(raw_line)
            full_bytes += len(raw_line)
            if raw_line.strip() == b"---":
                last_terminator_end = full_bytes
    if last_terminator_end <= 0:
        raise ValueError("Go2 source has no terminated record")
    remaining = last_terminator_end
    with path.open("rb") as handle:
        while remaining:
            chunk = handle.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("Go2 source ended before authenticated prefix")
            prefix_digest.update(chunk)
            remaining -= len(chunk)

    records: list[tuple[int, list[float], list[float]]] = []
    current: dict[str, Any] = {
        "sec": None,
        "nanosec": None,
        "gyro": [],
        "accel": [],
    }
    stamp_context = False
    imu_context = False
    vector_context: str | None = None

    def finish_terminated_record() -> None:
        required = (
            current["sec"] is not None,
            current["nanosec"] is not None,
            len(current["gyro"]) == 3,
            len(current["accel"]) == 3,
        )
        if not all(required):
            raise ValueError("terminated Go2 record lacks an authorized field")
        stamp_ns = int(current["sec"]) * 1_000_000_000 + int(current["nanosec"])
        gyro = [float(value) for value in current["gyro"]]
        accel = [float(value) for value in current["accel"]]
        if not all(math.isfinite(value) for value in gyro + accel):
            raise ValueError("non-finite authorized Go2 field")
        records.append((stamp_ns, gyro, accel))

    bytes_seen = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            bytes_seen += len(raw_line)
            if bytes_seen > last_terminator_end:
                break
            text = raw_line.decode("utf-8", errors="strict").rstrip("\r\n")
            if text == "---":
                finish_terminated_record()
                current = {"sec": None, "nanosec": None, "gyro": [], "accel": []}
                stamp_context = False
                imu_context = False
                vector_context = None
                continue
            if text == "stamp:":
                stamp_context = True
                imu_context = False
                vector_context = None
                continue
            if text == "imu_state:":
                imu_context = True
                stamp_context = False
                vector_context = None
                continue
            if text and not text.startswith(" "):
                stamp_context = False
                imu_context = False
                vector_context = None
                continue
            if stamp_context and text.startswith("  sec:"):
                current["sec"] = int(text.split(":", 1)[1].strip())
                continue
            if stamp_context and text.startswith("  nanosec:"):
                current["nanosec"] = int(text.split(":", 1)[1].strip())
                continue
            if imu_context and text == "  gyroscope:":
                vector_context = "gyro"
                continue
            if imu_context and text == "  accelerometer:":
                vector_context = "accel"
                continue
            if vector_context and text.startswith("  - "):
                current[vector_context].append(float(text[4:].strip()))
                continue
            if vector_context and text and not text.startswith("  - "):
                vector_context = None

    stamps = [record[0] for record in records]
    deltas = [right - left for left, right in zip(stamps, stamps[1:])]
    if any(delta <= 0 for delta in deltas):
        raise ValueError("Go2 authenticated-prefix timestamps are not strictly increasing")
    return {
        "source_alias": "BY2_GO2_BODY",
        "full_sha256": full_digest.hexdigest(),
        "full_bytes": full_bytes,
        "authenticated_prefix_sha256": prefix_digest.hexdigest(),
        "authenticated_prefix_bytes": last_terminator_end,
        "authenticated_record_count": len(records),
        "first_stamp_ns": stamps[0],
        "last_stamp_ns": stamps[-1],
        "duration_ns": stamps[-1] - stamps[0],
        "minimum_dt_ns": min(deltas),
        "median_dt_ns": int(np.median(deltas)),
        "maximum_dt_ns": max(deltas),
        "nonpositive_dt_count": sum(delta <= 0 for delta in deltas),
        "gyro_valid_count": len(records),
        "accelerometer_valid_count": len(records),
        "unterminated_tail_bytes_excluded": full_bytes - last_terminator_end,
        "forbidden_go2_field_semantic_parse_count": 0,
    }


def audit_by2_inputs(local_yaml: Path) -> dict[str, Any]:
    aliases = load_local_paths(local_yaml)
    gnss = audit_gnss1_solution_stream(aliases["by2_fix_root"] / "gnss1-raw.csv")
    go2 = audit_go2_imu_stream(aliases["by2_go2_body"])
    first = int(go2["first_stamp_ns"])
    last = int(go2["last_stamp_ns"])
    # The PVT epoch list is reconstructed narrowly to count cross-stream coverage.
    pvt_stamps: list[int] = []
    raw_path = aliases["by2_fix_root"] / "gnss1-raw.csv"
    with raw_path.open("r", encoding="utf-8-sig", newline="") as handle:
        header = next(handle)
        for serialized_line in handle:
            if ",UBX-NAV-PVT," not in serialized_line:
                continue
            row = next(csv.DictReader([header, serialized_line]))
            pvt_stamps.append(
                int(row["stamp.secs"]) * 1_000_000_000 + int(row["stamp.nsecs"])
            )
    overlap = [stamp for stamp in pvt_stamps if first <= stamp <= last]
    return {
        "data_mode": "REAL_BY2_INPUT_AVAILABILITY_AUDIT",
        "navigation_filter_run": False,
        "gnss1": gnss,
        "go2": go2,
        "cross_stream": {
            "association_domain": "outer acquisition timestamp nanoseconds",
            "pvt_epochs_within_go2_authenticated_coverage": len(overlap),
            "first_overlap_offset_from_go2_start_ns": overlap[0] - first,
            "last_overlap_margin_before_go2_end_ns": last - overlap[-1],
            "future_policy": "must be frozen before C00; no association performed here",
        },
        "access_counters": {
            "gnss1_multiplexed_serialized_rows_scanned": gnss[
                "serialized_rows_scanned_for_name"
            ],
            "gnss1_pvt_payloads_decoded": gnss["pvt_count"],
            "gnss1_nav_cov_payloads_decoded": gnss["nav_cov_count"],
            "gnss1_nonselected_payloads_semantically_decoded": 0,
            "gnss2_payloads_opened": 0,
            "rawx_payloads_semantically_decoded": 0,
            "sfrbx_payloads_semantically_decoded": 0,
            "rtcm_payloads_semantically_decoded": 0,
            "trace_or_reference_files_opened": 0,
            "provider_or_runtime_outputs_opened": 0,
            "go2_source_bytes_streamed_for_identity_and_record_selection": go2[
                "full_bytes"
            ],
            "go2_allowed_field_records_parsed": go2["authenticated_record_count"],
            "go2_forbidden_fields_semantically_parsed": 0,
            "solver_runs": 0,
            "c00_runs": 0,
            "comparison_runs": 0,
        },
    }


def _tracked_payload_roots(root: Path) -> tuple[Path, Path]:
    suffix = Path("paper_rebuild/horizontal_literature/lc02_chang2021")
    return root / "configs" / suffix, root / "docs" / suffix


def collect_tracked_payload(root: Path) -> dict[str, bytes]:
    payload: dict[str, bytes] = {}
    for source_root in _tracked_payload_roots(root):
        if not source_root.is_dir():
            raise ValueError(f"tracked payload root missing: {source_root}")
        for path in sorted(source_root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"tracked payload symlink forbidden: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"tracked payload special entry forbidden: {path}")
            relative = path.relative_to(source_root).as_posix()
            if relative in payload:
                raise ValueError(f"duplicate tracked payload path: {relative}")
            payload[relative] = path.read_bytes()
    actual = set(payload)
    if actual != EXPECTED_ARTIFACTS:
        raise ValueError(
            f"tracked payload set mismatch; missing={sorted(EXPECTED_ARTIFACTS-actual)}, "
            f"unexpected={sorted(actual-EXPECTED_ARTIFACTS)}"
        )
    return payload


def read_stage_payload(stage_root: Path) -> dict[str, bytes]:
    if stage_root.is_symlink() or not stage_root.is_dir():
        raise ValueError("stage root must be a real directory")
    payload: dict[str, bytes] = {}
    for path in sorted(stage_root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"stage special entry forbidden: {path}")
        payload[path.relative_to(stage_root).as_posix()] = path.read_bytes()
    return payload


def _parse_structured(relative: str, raw: bytes) -> Any:
    text = raw.decode("utf-8")
    if relative.endswith(".json"):
        return json.loads(text)
    if relative.endswith((".yaml", ".yml")):
        return yaml.safe_load(text)
    if relative.endswith(".csv"):
        return list(csv.DictReader(text.splitlines()))
    return None


def validate_payload(payload: dict[str, bytes]) -> dict[str, Any]:
    if set(payload) != EXPECTED_ARTIFACTS:
        raise ValueError("payload manifest is not exact")
    if (
        len(EXPECTED_CONFIG_ARTIFACTS) != 26
        or len(EXPECTED_DOC_ARTIFACTS) != 11
        or len(EXPECTED_POSTCOMMIT_PATHS) != 40
        or EXPECTED_CONFIG_ARTIFACTS | EXPECTED_DOC_ARTIFACTS != EXPECTED_ARTIFACTS
        or EXPECTED_CONFIG_ARTIFACTS & EXPECTED_DOC_ARTIFACTS
    ):
        raise ValueError("exact tracked/postcommit scope constants are inconsistent")
    if any(name.lower().endswith((".pdf", ".zip")) for name in payload):
        raise ValueError("PDF/ZIP forbidden in audit payload")
    for relative, raw in payload.items():
        if b"/home/" in raw or b"/mnt/" in raw:
            raise ValueError(f"user-specific/local absolute path forbidden: {relative}")
    parsed: dict[str, Any] = {}
    for relative, raw in payload.items():
        if not raw:
            raise ValueError(f"empty artifact forbidden: {relative}")
        value = _parse_structured(relative, raw)
        if value is not None:
            parsed[relative] = value

    status = parsed["11_REPORT/LC02_CHANG_R0_R4_STATUS.json"]
    if status["terminal_status"] != TERMINAL_STATUS:
        raise ValueError("terminal status mismatch")
    if status.get("conditional_outcome") != "OUTCOME_B_NO_GO":
        raise ValueError("conditional Outcome-B status mismatch")
    if status.get("executed_stages") != ["R0", "R1", "R2"]:
        raise ValueError("only R0--R2 may be marked executed")
    for field in (
        "r3_executed",
        "r4_executed",
        "implementation_executed",
        "synthetic_validation_executed",
    ):
        if status.get(field) is not False:
            raise ValueError(f"conditional non-execution field must be false: {field}")
    if status.get("branch_reproduction_levels") != EXPECTED_BRANCH_LEVELS:
        raise ValueError("branch reproduction-level map mismatch")
    if status.get("gate_summary") != {
        "gate_count": 12,
        "pass_count": 5,
        "fail_count": 7,
        "all_pass_required": True,
    }:
        raise ValueError("status gate summary mismatch")
    if status.get("ckf_core_identity") != "A_LITERAL_PRINTED_LINEAR_ERROR_STATE_RECURSION":
        raise ValueError("status CKF scientific decision mismatch")
    if status.get("eq12_decision") != "UNRESOLVED_NON_SQUARE_INVERSE_AND_STATE_LIFT":
        raise ValueError("status Eq12 scientific decision mismatch")
    if status.get("non_duplication_decision") != "DISTINCT_COMPLEMENTARY_METHOD":
        raise ValueError("status non-duplication decision mismatch")
    for gate in (
        "formal_lc02_admission",
        "implementation_authorized",
        "production_solver_authorized",
        "c00_authorized",
        "representative_cases_authorized",
        "comparison_run_authorized",
    ):
        if status.get(gate) is not False:
            raise ValueError(f"authorization gate must be false: {gate}")
    if status.get("implementation_directory_created") is not False:
        raise ValueError("Outcome B must not create an implementation directory")
    if status.get("synthetic_validation_directory_created") is not False:
        raise ValueError("Outcome B must not create a synthetic validation directory")
    repair_history = status.get("external_stage_repair_history", {})
    if repair_history.get("repair_mode") != STAGE09_REPAIR_MODE:
        raise ValueError("stage09 repair-mode disclosure mismatch")
    if repair_history.get("aggregate_atomic_exchange") is not False:
        raise ValueError("two-rename repair must not be called aggregate-atomic")
    if repair_history.get("initial_atomic_exchange_attempt") != (
        "UNSUPPORTED_ON_DRVFS_EINVAL_NO_STAGE_CHANGE"
    ):
        raise ValueError("initial atomic-exchange failure disclosure mismatch")
    review_repair = repair_history.get("final_review_correction_transaction", {})
    if review_repair.get("preimage_aggregate_sha256") != STAGE09_REPAIR_PREIMAGE_SHA256:
        raise ValueError("final review-correction preimage disclosure mismatch")
    if review_repair.get("repair_mode") != STAGE09_REPAIR_MODE:
        raise ValueError("final review-correction mode disclosure mismatch")
    if review_repair.get("postimage_aggregate") != (
        "EXTERNALLY_COMPUTED_AND_REPORTED_TO_AVOID_SELF_REFERENTIAL_PAYLOAD_HASH"
    ):
        raise ValueError("final review-correction postimage disclosure mismatch")

    rubric = parsed["04_METHOD_CONTRACTS/CHANG2021_FORMAL_ADMISSION_RUBRIC.yaml"]
    rows = rubric.get("gates", [])
    gate_results = {row.get("gate"): row.get("result") for row in rows}
    if len(rows) != 12 or gate_results != EXPECTED_GATE_RESULTS:
        raise ValueError("formal admission rubric exact result map mismatch")
    if rubric.get("decision") != TERMINAL_STATUS:
        raise ValueError("rubric terminal mismatch")

    ckf = parsed["04_METHOD_CONTRACTS/CHANG2021_CKF_CORE_IDENTITY_DECISION.json"]
    eq12 = parsed[
        "04_METHOD_CONTRACTS/CHANG2021_EQ12_GENERALIZED_INVERSE_DECISION.json"
    ]
    beta = parsed["04_METHOD_CONTRACTS/CHANG2021_BETA_TO_15_STATE_MAPPING.yaml"]
    ts = parsed["04_METHOD_CONTRACTS/CHANG2021_TS_AGGREGATION_DECISION.json"]
    identity = parsed[
        "05_NON_DUPLICATION_AUDIT/LC01_VS_CHANG2021_METHOD_IDENTITY.json"
    ]
    if ckf.get("decision") != "A" or ckf.get("gate_result") != "PASS":
        raise ValueError("CKF identity decision mismatch")
    if eq12.get("decision") != "UNRESOLVED_NON_SQUARE_INVERSE_AND_STATE_LIFT":
        raise ValueError("Eq12 decision mismatch")
    if beta.get("mapping", {}).get("selected") is not None:
        raise ValueError("beta-to-state policy was silently selected")
    if ts.get("decision") != "UNRESOLVED" or ts.get("gate_result") != "FAIL":
        raise ValueError("T-S aggregation decision mismatch")
    if identity.get("decision") != "DISTINCT_COMPLEMENTARY_METHOD":
        raise ValueError("LC01/Chang identity decision mismatch")

    equations = parsed["02_FULL_PAPER_REVIEW/LC02_CHANG_EQUATION_REGISTRY.csv"]
    if [int(row["equation"]) for row in equations] != list(range(1, 31)):
        raise ValueError("equation registry must contain exact Eqs 1--30")
    figures = parsed["02_FULL_PAPER_REVIEW/LC02_CHANG_FIGURE_REGISTRY.csv"]
    figure_semantics = {
        int(row["figure"]): (
            int(row["paper_page"]),
            row["category"],
            row["current_evidence_role"],
        )
        for row in figures
    }
    if figure_semantics != EXPECTED_FIGURE_SEMANTICS:
        raise ValueError("figure registry exact per-row semantics mismatch")
    if any(
        row["provenance"] != "PAPER_DIRECT"
        or row["visual_review"] != "VISUALLY_INSPECTED_RENDERED_PAGE"
        for row in figures
    ):
        raise ValueError("figure provenance/review status mismatch")
    experiments = parsed[
        "02_FULL_PAPER_REVIEW/LC02_CHANG_EXPERIMENT_REGISTRY.csv"
    ]
    experiment_semantics = {
        row["artifact_id"]: (
            row["artifact_type"],
            row["data_mode"],
            row["current_evidence_role"],
        )
        for row in experiments
    }
    if experiment_semantics != EXPECTED_EXPERIMENT_SEMANTICS:
        raise ValueError("experiment figure/table exact per-row semantics mismatch")
    if any(
        row["provenance"] != "PAPER_DIRECT"
        or row["review_status"] != "FULLY_VISUALLY_REVIEWED"
        for row in experiments
    ):
        raise ValueError("experiment figure/table provenance/review mismatch")

    memberships = parsed[
        "04_METHOD_CONTRACTS/CHANG2021_MEMBERSHIP_FUNCTIONS.csv"
    ]
    exact_memberships = {
        ("L_k1", "small"): (
            "(-inf,5];(5,15);[15,inf)",
            "1;(15-L)/10;0",
            "mu(5)=1;mu(15)=0",
        ),
        ("L_k1", "medium"): (
            "(-inf,5];(5,15);[15,25];(25,35);[35,inf)",
            "0;(L-5)/10;1;(35-L)/10;0",
            "mu(5)=0;mu(15)=1;mu(25)=1;mu(35)=0",
        ),
        ("L_k1", "large"): (
            "(-inf,25];(25,35);[35,inf)",
            "0;(L-25)/10;1",
            "mu(25)=0;mu(35)=1",
        ),
        ("L_k2", "small"): (
            "(-inf,5];(5,15);[15,inf)",
            "1;(15-L)/10;0",
            "mu(5)=1;mu(15)=0",
        ),
        ("L_k2", "medium"): (
            "(-inf,5];(5,15];(15,25);[25,inf)",
            "0;(L-5)/10;(25-L)/10;0",
            "mu(5)=0;mu(15)=1;mu(25)=0",
        ),
        ("L_k2", "large"): (
            "(-inf,15];(15,25);[25,inf)",
            "0;(L-15)/10;1",
            "mu(15)=0;mu(25)=1",
        ),
    }
    observed_memberships = {
        (row["input"], row["label"]): (
            row["interval"],
            row["piecewise_membership"],
            row["boundary_values"],
        )
        for row in memberships
    }
    if observed_memberships != exact_memberships:
        raise ValueError("Fig. 4 membership interval/formula/boundary map mismatch")
    for relative, value in parsed.items():
        if not relative.endswith(".csv"):
            continue
        for row in value:
            if "provenance" in row and row["provenance"] not in ALLOWED_PROVENANCE:
                raise ValueError(
                    f"invalid provenance {row['provenance']!r} in {relative}"
                )
    if any(
        part in relative
        for relative in payload
        for part in ("06_IMPLEMENTATION", "07_SYNTHETIC_VALIDATION")
    ):
        raise ValueError("Outcome B payload contains forbidden implementation output")
    return {
        "artifact_count": len(payload),
        "structured_artifact_count": len(parsed),
        "terminal_status": status["terminal_status"],
    }


def validate_stage(stage_root: Path) -> dict[str, Any]:
    return validate_payload(read_stage_payload(stage_root))


def publish_stage(payload: dict[str, bytes], stage_root: Path) -> dict[str, Any]:
    """Create the exact stage once.  Existing targets are never replaced."""

    validate_payload(payload)
    if stage_root.exists() or stage_root.is_symlink():
        raise FileExistsError(f"refusing to replace existing audit stage: {stage_root}")
    parent = stage_root.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("stage parent must be an existing real directory")
    stage_root.mkdir(mode=0o755)
    for relative in sorted(payload):
        destination = stage_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.parent.is_symlink():
            raise ValueError(f"destination parent symlink forbidden: {destination.parent}")
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o644,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(payload[relative])
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
    directory_descriptor = os.open(stage_root, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    return validate_stage(stage_root)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_payload_directories(root: Path) -> None:
    directories = [root, *(path for path in root.rglob("*") if path.is_dir())]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        _fsync_directory(directory)


def _remove_verified_payload_tree(
    stage_root: Path, *, expected_set: frozenset[str], expected_aggregate: str
) -> None:
    """Remove only an exact verified transaction tree, never a protected root."""

    payload = read_stage_payload(stage_root)
    if set(payload) != expected_set:
        raise ValueError("refusing cleanup of transaction tree with unexpected manifest")
    if payload_aggregate_sha256(payload) != expected_aggregate:
        raise ValueError("refusing cleanup of transaction tree with unexpected aggregate")
    for path in sorted(
        (item for item in stage_root.rglob("*") if item.is_file()), reverse=True
    ):
        path.unlink()
    for path in sorted(
        (item for item in stage_root.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        path.rmdir()
    stage_root.rmdir()


def repair_stage_guarded_two_rename(
    payload: dict[str, bytes], *, stage_root: Path, expected_stage_root: Path
) -> dict[str, Any]:
    """Repair only the exact reviewed preimage with a verified rollback path.

    Each rename is atomic, but the two-rename transaction is deliberately not
    described as an aggregate-atomic exchange.  This is the explicitly approved
    fallback for the drvfs filesystem, which rejected RENAME_EXCHANGE with EINVAL.
    """

    validate_payload(payload)
    if stage_root.is_symlink() or not stage_root.is_dir():
        raise ValueError("repair target must be an existing real directory")
    if stage_root.resolve() != expected_stage_root.resolve():
        raise ValueError("repair target is not the exact protected Chang stage")
    parent = stage_root.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("repair parent must be an existing real directory")
    if os.stat(stage_root).st_dev != os.stat(parent).st_dev:
        raise ValueError("repair target and parent are not on the same filesystem")
    old_payload = read_stage_payload(stage_root)
    if set(old_payload) != PREVIOUS_ARTIFACTS:
        raise ValueError("repair preimage artifact set mismatch")
    old_aggregate = payload_aggregate_sha256(old_payload)
    if old_aggregate != STAGE09_REPAIR_PREIMAGE_SHA256:
        raise ValueError("repair preimage aggregate mismatch")

    new_aggregate = payload_aggregate_sha256(payload)
    scratch = parent / f".{stage_root.name}.corrected-{new_aggregate}"
    backup = parent / f".{stage_root.name}.backup-{old_aggregate}"
    failed = parent / f".{stage_root.name}.failed-postimage-{new_aggregate}"
    for sibling in (scratch, backup, failed):
        if os.path.lexists(sibling):
            raise FileExistsError(f"repair sibling already exists: {sibling.name}")
    scratch.mkdir(mode=0o755)
    try:
        for relative in sorted(payload):
            destination = scratch / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                destination,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o644,
            )
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as handle:
                    handle.write(payload[relative])
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                os.close(descriptor)
        _fsync_payload_directories(scratch)
        validate_stage(scratch)
        scratch_payload = read_stage_payload(scratch)
        if set(scratch_payload) != EXPECTED_ARTIFACTS:
            raise ValueError("corrected sibling artifact set mismatch")
        if payload_aggregate_sha256(scratch_payload) != new_aggregate:
            raise ValueError("scratch payload aggregate mismatch")

        if os.path.lexists(backup):
            raise FileExistsError("repair backup appeared before first rename")
        os.rename(stage_root, backup)
        _fsync_directory(parent)
        try:
            if os.path.lexists(stage_root):
                raise FileExistsError("stage path appeared before second rename")
            os.rename(scratch, stage_root)
            _fsync_directory(parent)
        except Exception:
            if os.path.lexists(stage_root):
                os.rename(stage_root, failed)
                _fsync_directory(parent)
            if not backup.is_dir() or backup.is_symlink():
                raise RuntimeError("repair rollback preimage is unavailable")
            os.rename(backup, stage_root)
            _fsync_directory(parent)
            restored = read_stage_payload(stage_root)
            if (
                set(restored) != PREVIOUS_ARTIFACTS
                or payload_aggregate_sha256(restored) != old_aggregate
            ):
                raise RuntimeError("repair rollback did not restore exact preimage")
            if scratch.exists():
                _remove_verified_payload_tree(
                    scratch,
                    expected_set=EXPECTED_ARTIFACTS,
                    expected_aggregate=new_aggregate,
                )
            raise

        try:
            validate_stage(stage_root)
            post_payload = read_stage_payload(stage_root)
            if post_payload != payload:
                raise ValueError("post-rename stage parity mismatch")
            if payload_aggregate_sha256(post_payload) != new_aggregate:
                raise ValueError("post-rename stage aggregate mismatch")
        except Exception:
            if os.path.lexists(failed):
                raise RuntimeError("failed-postimage sibling appeared during validation")
            os.rename(stage_root, failed)
            _fsync_directory(parent)
            os.rename(backup, stage_root)
            _fsync_directory(parent)
            restored = read_stage_payload(stage_root)
            if (
                set(restored) != PREVIOUS_ARTIFACTS
                or payload_aggregate_sha256(restored) != old_aggregate
            ):
                raise RuntimeError("validation rollback did not restore exact preimage")
            raise

        _remove_verified_payload_tree(
            backup,
            expected_set=PREVIOUS_ARTIFACTS,
            expected_aggregate=old_aggregate,
        )
        _fsync_directory(parent)
        if any(os.path.lexists(path) for path in (scratch, backup, failed)):
            raise RuntimeError("repair left an unexpected transaction sibling")
    except Exception:
        if scratch.exists() and not backup.exists() and not stage_root.exists():
            raise RuntimeError("repair failed with both stage and backup absent")
        if scratch.exists() and stage_root.exists() and not backup.exists():
            scratch_payload = read_stage_payload(scratch)
            if scratch_payload == payload:
                _remove_verified_payload_tree(
                    scratch,
                    expected_set=EXPECTED_ARTIFACTS,
                    expected_aggregate=new_aggregate,
                )
        raise
    return {
        "repair_mode": STAGE09_REPAIR_MODE,
        "aggregate_atomic_exchange": False,
        "preimage_aggregate_sha256": old_aggregate,
        "postimage_aggregate_sha256": new_aggregate,
        "artifact_count": len(payload),
        "stage_validation": validate_stage(stage_root),
    }


def verify_protected_inputs(root: Path, clean_root: Path) -> dict[str, Any]:
    canonical: dict[str, str] = {}
    for relative, expected in CANONICAL_HASHES.items():
        actual = sha256_file(root / relative)
        if actual != expected:
            raise ValueError(f"Canonical hash mismatch: {relative}")
        canonical[relative] = actual
    count, digest = normalized_tree_manifest(clean_root / STAGE08_RELATIVE)
    if count != STAGE08_FILE_COUNT or digest != STAGE08_MANIFEST_SHA256:
        raise ValueError("frozen Yin stage08 identity changed")
    return {
        "canonical_hashes": canonical,
        "stage08_file_count": count,
        "stage08_manifest_sha256": digest,
    }


def verify_paper(path: Path) -> dict[str, Any]:
    if path.stat().st_size != PAPER_BYTES or sha256_file(path) != PAPER_SHA256:
        raise ValueError("Chang paper binary identity mismatch")
    if path.read_bytes()[:5] != b"%PDF-":
        raise ValueError("Chang source is not a PDF")
    try:
        import fitz

        document = fitz.open(path)
        pages = len(document)
        encrypted = bool(document.is_encrypted)
        document.close()
    except ImportError as exc:  # pragma: no cover - environment dependency
        raise RuntimeError("PyMuPDF is required for PDF verification") from exc
    if pages != PAPER_PAGES or encrypted:
        raise ValueError("Chang paper page/encryption identity mismatch")
    return {
        "sha256": PAPER_SHA256,
        "bytes": PAPER_BYTES,
        "pages": pages,
        "encrypted": encrypted,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--audit-inputs", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--repair-existing-audit-stage", action="store_true")
    parser.add_argument(
        "--local-paths",
        type=Path,
        default=repo_root() / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml",
    )
    parser.add_argument("--paper", type=Path)
    parser.add_argument("--stage-root", type=Path)
    args = parser.parse_args(argv)
    if args.publish and args.repair_existing_audit_stage:
        parser.error("--publish and --repair-existing-audit-stage are mutually exclusive")
    root = repo_root()
    aliases = load_local_paths(args.local_paths)
    payload = collect_tracked_payload(root)
    result: dict[str, Any] = {
        "task_head": verify_task_head(root),
        "tracked_payload": validate_payload(payload),
    }
    stage_root = args.stage_root or aliases["clean_root"] / STAGE09_RELATIVE
    if stage_root.exists() and not args.repair_existing_audit_stage:
        current_stage_payload = read_stage_payload(stage_root)
        if (
            set(current_stage_payload) == PREVIOUS_ARTIFACTS
            and payload_aggregate_sha256(current_stage_payload)
            == STAGE09_REPAIR_PREIMAGE_SHA256
        ):
            result["external_stage"] = {
                "status": "EXACT_REVIEWED_PREIMAGE_PENDING_GUARDED_TWO_RENAME_REPAIR",
                "artifact_count": len(current_stage_payload),
                "aggregate_sha256": STAGE09_REPAIR_PREIMAGE_SHA256,
            }
        else:
            result["external_stage"] = validate_stage(stage_root)
    if args.audit_inputs:
        result["by2_input_audit"] = audit_by2_inputs(args.local_paths)
    if args.paper:
        result["paper"] = verify_paper(args.paper)
    if args.publish:
        result["protected_before_publish"] = verify_protected_inputs(
            root, aliases["clean_root"]
        )
        result["external_stage"] = publish_stage(payload, stage_root)
        result["protected_after_publish"] = verify_protected_inputs(
            root, aliases["clean_root"]
        )
    if args.repair_existing_audit_stage:
        if args.stage_root is not None:
            raise ValueError("repair forbids a stage-root override")
        exact_stage_root = aliases["clean_root"] / STAGE09_RELATIVE
        result["protected_before_repair"] = verify_protected_inputs(
            root, aliases["clean_root"]
        )
        result["external_stage_repair"] = repair_stage_guarded_two_rename(
            payload,
            stage_root=stage_root,
            expected_stage_root=exact_stage_root,
        )
        result["protected_after_repair"] = verify_protected_inputs(
            root, aliases["clean_root"]
        )
    def json_default(value: Any) -> Any:
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    print(json.dumps(result, indent=2, sort_keys=True, default=json_default))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
