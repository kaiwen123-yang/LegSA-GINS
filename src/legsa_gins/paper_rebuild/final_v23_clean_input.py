"""Build the CLEAN1R2R1 clean-real final_v23 inputs from hash-locked BY2 raw.

This module is intentionally narrower than the archived ``process_data.py``.
It has no trace path, calibration, fallback, random-number, degradation, or
legacy-input parameter.  The only yaw source is the physical A1 status pair;
``1.5 deg`` is serialized as measurement standard deviation only.
"""

from __future__ import annotations

import csv
import bisect
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evidence import (
    BY2_BODY_RELATIVE_PATH,
    BY2_FIX_PREFIX,
    BY2_RAW_RELATIVE_PATHS,
    BY2_TRACE_RELATIVE_PATH,
    RawAudit,
    parse_strace_openat_paths,
    validate_provider_source_read_set,
)
from .manifest import (
    git_code_state,
    read_hash_lock,
    sha256_file,
    sha256_text,
    verify_raw_sources,
    write_json_atomic,
)
from .paths import CleanPaths, guard_path, is_within, load_yaml_mapping
from .providers import (
    RECEIVER_VELOCITY_PARSER_ADAPTER_ID,
    _generate_process_data_compat_with_active_pvt,
    infer_source_day_base_time,
)
from legsa_gins.input_generation.status_yaw_builder import (
    apply_status_valid_filter,
    status_time_header,
)


STAGE_ID = "CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION"
PROTOCOL_ID = "CLEAN_REAL_DATA_FINAL_V23"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
PROFILE_ID = "clean_real_final_v23"
MANIFEST_SCHEMA = "paper_rebuild.final_v23_clean_input_manifest.v1"
EXPECTED_RAW_LOCK_SHA256 = (
    "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"
)
EXPECTED_FULL_LOCK_ROWS = 9980
EXPECTED_BY2_LOCK_ROWS = 22

GNSS_OUTPUT_NAME = "FINAL_V23_CLEAN_FRESH.gnss"
IMU_OUTPUT_NAME = "FINAL_V23_CLEAN_FRESH.imu"
MANIFEST_NAME = "FINAL_V23_CLEAN_INPUT_MANIFEST.json"
COLUMN_AUDIT_NAME = "FINAL_V23_CLEAN_INPUT_COLUMN_AUDIT.csv"
TIME_AUDIT_NAME = "FINAL_V23_CLEAN_INPUT_TIME_AUDIT.json"
SOURCE_LEDGER_NAME = "FINAL_V23_CLEAN_INPUT_SOURCE_LEDGER.csv"
NO_TRACE_AUDIT_NAME = "FINAL_V23_CLEAN_NO_TRACE_NO_INJECTION_AUDIT.json"
FILE_OPEN_AUDIT_NAME = "FINAL_V23_CLEAN_INPUT_FILE_OPEN_AUDIT.json"

GNSS_COLUMNS = (
    "time",
    "lat",
    "lon",
    "height",
    "std_n",
    "std_e",
    "std_d",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "yaw",
    "yaw_std",
)
IMU_COLUMNS = (
    "time",
    "dtheta_x",
    "dtheta_y",
    "dtheta_z",
    "dvel_x",
    "dvel_y",
    "dvel_z",
)

RECEIVER_VELOCITY_CONTRACT = {
    "vel_n_full_frame": [54, 58],
    "vel_e_full_frame": [58, 62],
    "vel_d_full_frame": [62, 66],
    "sAcc_full_frame": [74, 78],
    "provider_std_mps": [0.05, 0.05, 0.05],
    "sAcc_parsed_for_audit": True,
    "sAcc_used_for_provider_std": False,
}

ACTUAL_SOURCE_ROLES = {
    f"{BY2_FIX_PREFIX}/gnss1-status.csv": (
        "gnss1_position_std_and_a1_status_source",
        "legsa_gins.input_generation.process_data_compat._status_base_rows",
    ),
    f"{BY2_FIX_PREFIX}/gnss2-status.csv": (
        "gnss2_a1_status_source",
        "legsa_gins.input_generation.status_yaw_builder.build_a1_dual_diff_yaw_rows",
    ),
    f"{BY2_FIX_PREFIX}/gnss1-raw.csv": (
        "receiver_velocity_nav_pvt_source",
        "legsa_gins.paper_rebuild.ubx_nav_pvt.extract_pvt_velocity_rows",
    ),
    BY2_BODY_RELATIVE_PATH: (
        "propagation_imu_source",
        "legsa_gins.input_generation.imu_txt_builder.build_process_data_imu_rows",
    ),
}


class FinalV23CleanInputError(RuntimeError):
    """The clean-real input failed a deterministic contract gate."""


def raw_checkpoint_from_audit(audit: RawAudit) -> dict[str, Any]:
    """Serialize an outer raw-integrity audit without opening any raw path here."""

    return {
        "schema_version": "paper_rebuild.final_v23_external_raw_checkpoint.v1",
        "audit_phase": audit.summary.get("audit_phase"),
        "raw_hash_lock_sha256": audit.summary.get("raw_hash_lock_sha256"),
        "expected": audit.summary.get("expected"),
        "verified": audit.summary.get("verified"),
        "missing": audit.summary.get("missing"),
        "mismatch": audit.summary.get("mismatch"),
        "symlink_escape": audit.summary.get("symlink_escape"),
        "raw_mutation": audit.summary.get("raw_mutation"),
        "passed": audit.summary.get("passed"),
        "verified_hashes": dict(audit.verified_hashes),
        "trace_read_role": "outer_raw_integrity_hash_audit_only",
        "trace_provider_or_solver_input": False,
    }


def load_raw_checkpoint(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FinalV23CleanInputError("external raw checkpoint must be an object")
    return payload


def validate_raw_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    phase: str,
    lock: Mapping[str, Mapping[str, str]],
    expected_lock_sha256: str,
) -> dict[str, str]:
    """Validate an outer 22/22 checkpoint from metadata only.

    The raw checker is deliberately a separate process/phase.  This generator
    never opens the trace file, including for validation.
    """

    if checkpoint.get("schema_version") != "paper_rebuild.final_v23_external_raw_checkpoint.v1":
        raise FinalV23CleanInputError("external raw checkpoint schema mismatch")
    if checkpoint.get("audit_phase") != phase:
        raise FinalV23CleanInputError("external raw checkpoint phase mismatch")
    expected_scalars = {
        "raw_hash_lock_sha256": expected_lock_sha256,
        "expected": EXPECTED_BY2_LOCK_ROWS,
        "verified": EXPECTED_BY2_LOCK_ROWS,
        "missing": 0,
        "mismatch": 0,
        "symlink_escape": 0,
        "raw_mutation": 0,
        "passed": True,
        "trace_read_role": "outer_raw_integrity_hash_audit_only",
        "trace_provider_or_solver_input": False,
    }
    mismatches = [key for key, value in expected_scalars.items() if checkpoint.get(key) != value]
    if mismatches:
        raise FinalV23CleanInputError(
            "external raw checkpoint mismatch: " + ",".join(sorted(mismatches))
        )
    hashes = checkpoint.get("verified_hashes")
    if not isinstance(hashes, Mapping) or set(hashes) != set(BY2_RAW_RELATIVE_PATHS):
        raise FinalV23CleanInputError("external raw checkpoint path set is not exact BY2 22")
    normalized: dict[str, str] = {}
    for relative in BY2_RAW_RELATIVE_PATHS:
        digest = hashes.get(relative)
        row = lock.get(relative)
        if not isinstance(digest, str) or len(digest) != 64 or row is None:
            raise FinalV23CleanInputError(f"external raw checkpoint hash is invalid: {relative}")
        if digest != row.get("sha256"):
            raise FinalV23CleanInputError(f"external raw checkpoint disagrees with lock: {relative}")
        normalized[relative] = digest
    return normalized


def load_contract(path: str | Path) -> dict[str, Any]:
    payload = load_yaml_mapping(path)
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping):
        raise FinalV23CleanInputError("final_v23 contract has no profiles mapping")
    profile = profiles.get(PROFILE_ID)
    if not isinstance(profile, Mapping):
        raise FinalV23CleanInputError("clean_real_final_v23 profile is missing")
    validate_clean_profile(profile)
    correction = payload.get("profile_identity_correction")
    if not isinstance(correction, Mapping):
        raise FinalV23CleanInputError("profile identity correction is missing")
    if correction.get("human_profile_decision") != "CLEAN_REAL_DATA_FINAL_V23":
        raise FinalV23CleanInputError("clean-real human profile decision is not frozen")
    if correction.get("E001_selected_as_clean_input_anchor") is not False:
        raise FinalV23CleanInputError("E001 remains selected as a clean input anchor")
    authorization = payload.get("current_authorization")
    if not isinstance(authorization, Mapping) or (
        authorization.get("stage_id") != STAGE_ID
        or authorization.get("protocol_id") != PROTOCOL_ID
        or authorization.get("case_id") != CASE_ID
        or authorization.get("selected_profile") != PROFILE_ID
        or authorization.get("clean_execution_eligible") is not True
        or authorization.get("current_active_evidence_contaminated") is not False
    ):
        raise FinalV23CleanInputError("CLEAN1R2R1 current authorization is incomplete")
    return payload


def validate_clean_profile(profile: Mapping[str, Any]) -> None:
    expected = {
        "role": "CLEAN_FINAL_V23_PARITY_AND_STRONG_BASELINE",
        "data_mode": "real_by2_raw",
        "yaw_measurement_std_deg": 1.5,
        "yaw_noise_injection_enabled": False,
        "yaw_noise_injection_std_deg": 0.0,
        "yaw_noise_seed": None,
        "trace_used_during_input_generation": False,
        "clean_solver_input_eligible": True,
        "clean_metric_evidence_eligible": True,
        "dual_yaw_source": "A1_dual_diff_status",
    }
    mismatches = [key for key, value in expected.items() if profile.get(key) != value]
    if mismatches:
        raise FinalV23CleanInputError(
            "clean-real profile mismatch: " + ",".join(sorted(mismatches))
        )


def build_clean_a1_yaw_rows(
    gnss1_status_path: str | Path,
    gnss2_status_path: str | Path,
    *,
    base_time: float,
    max_rows: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reproduce archive ``numpy.interp`` A1 yaw without trace or noise.

    Unlike the maintained generic status helper, the archived implementation
    holds GNSS2 endpoints and wraps every angular value to ``[-180, 180)``.
    Those two behaviors are part of the clean final_v23 input contract.
    """

    def read_rows(path: str | Path) -> list[dict[str, str]]:
        output: list[dict[str, str]] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                if max_rows is not None and index >= max_rows:
                    break
                output.append(row)
        return output

    def numeric(row: Mapping[str, Any], field: str) -> float | None:
        text = str(row.get(field, "")).strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        return value if math.isfinite(value) else None

    fields = ("rel_pos_n", "rel_pos_e", "rel_pos_d", "rel_acc_n", "rel_acc_e", "rel_acc_d")

    def prepare(raw: list[dict[str, str]], label: str) -> tuple[list[dict[str, float]], dict[str, Any], int]:
        valid, stats = apply_status_valid_filter(raw, label)
        prepared: list[dict[str, float]] = []
        dropped = 0
        for row in valid:
            values = {field: numeric(row, field) for field in fields}
            try:
                timestamp = status_time_header(row)
            except ValueError:
                timestamp = math.nan
            if not math.isfinite(timestamp) or any(value is None for value in values.values()):
                dropped += 1
                continue
            prepared.append({"t": timestamp, **{key: float(value) for key, value in values.items()}})
        prepared.sort(key=lambda item: item["t"])
        return prepared, stats, dropped

    raw1, raw2 = read_rows(gnss1_status_path), read_rows(gnss2_status_path)
    rows1, stats1, dropped1 = prepare(raw1, "gnss1")
    rows2, stats2, dropped2 = prepare(raw2, "gnss2")
    if not rows1 or not rows2:
        raise FinalV23CleanInputError("clean A1 status source has no valid paired rows")
    t2 = [item["t"] for item in rows2]
    endpoint_hold_count = 0

    def interpolate(t: float, field: str) -> float:
        nonlocal endpoint_hold_count
        if t <= t2[0]:
            if t < t2[0]:
                endpoint_hold_count += 1
            return rows2[0][field]
        if t >= t2[-1]:
            if t > t2[-1]:
                endpoint_hold_count += 1
            return rows2[-1][field]
        right_index = bisect.bisect_left(t2, t)
        right = rows2[right_index]
        if right["t"] == t:
            return right[field]
        left = rows2[right_index - 1]
        alpha = (t - left["t"]) / (right["t"] - left["t"])
        return left[field] + alpha * (right[field] - left[field])

    def wrap_minus180(angle: float) -> float:
        return (angle + 180.0) % 360.0 - 180.0

    rows: list[dict[str, Any]] = []
    for item1 in rows1:
        t1 = item1["t"]
        item2 = {field: interpolate(t1, field) for field in fields}
        rel_n = item2["rel_pos_n"] - item1["rel_pos_n"]
        rel_e = item2["rel_pos_e"] - item1["rel_pos_e"]
        rel_d = item2["rel_pos_d"] - item1["rel_pos_d"]
        rel_acc_n = max(abs(item1["rel_acc_n"]), abs(item2["rel_acc_n"]))
        rel_acc_e = max(abs(item1["rel_acc_e"]), abs(item2["rel_acc_e"]))
        rel_acc_d = max(abs(item1["rel_acc_d"]), abs(item2["rel_acc_d"]))
        yaw_baseline = wrap_minus180(-math.degrees(math.atan2(rel_e, rel_n)))
        yaw_body = wrap_minus180(yaw_baseline)
        rows.append(
            {
                "timestamp": t1,
                "aligned_time": t1 - base_time,
                "rel_n": rel_n,
                "rel_e": rel_e,
                "rel_d": rel_d,
                "rel_acc_n": rel_acc_n,
                "rel_acc_e": rel_acc_e,
                "rel_acc_d": rel_acc_d,
                "rel_acc_h": math.hypot(rel_acc_n, rel_acc_e),
                "baseline_len_m": math.sqrt(rel_n * rel_n + rel_e * rel_e + rel_d * rel_d),
                "yaw_baseline_deg": yaw_baseline,
                "yaw_body_deg": yaw_body,
                "yaw_ned_deg": wrap_minus180(90.0 - yaw_body),
                "yaw_std": 1.5,
                "yaw_source": "A1_dual_diff_status",
            }
        )
    audit = {
        "scheme_key": "A1_dual_diff",
        "gnss1_filter": stats1,
        "gnss2_filter": stats2,
        "gnss1_missing_rel_or_time_count": dropped1,
        "gnss2_missing_rel_or_time_count": dropped2,
        "status2_to_status1_interpolation": "numpy_linear_with_endpoint_hold",
        "endpoint_hold_field_evaluation_count": endpoint_hold_count,
        "yaw_wrap_range": "[-180,180)",
        "yaw_row_count": len(rows),
    }
    audit = {
        **audit,
        "yaw_measurement_std_deg": 1.5,
        "yaw_measurement_std_role": "measurement_covariance_R",
        "yaw_noise_injection_enabled": False,
        "yaw_noise_injection_std_deg": 0.0,
        "yaw_noise_seed": None,
        "trace_used_online": False,
    }
    return rows, audit


def _apply_exact_clean_yaw(
    gnss_rows: list[list[float]], yaw_rows: Sequence[Mapping[str, Any]], *, tolerance: float
) -> None:
    """Apply archive nearest/ffill/bfill yaw merge to finalized GNSS rows."""

    times = [float(row["aligned_time"]) for row in yaw_rows]
    matched: list[tuple[float, float] | None] = []
    for gnss in gnss_rows:
        t = float(gnss[0])
        index = bisect.bisect_left(times, t)
        candidates = [candidate for candidate in (index - 1, index) if 0 <= candidate < len(times)]
        if not candidates:
            matched.append(None)
            continue
        best = min(candidates, key=lambda candidate: (abs(times[candidate] - t), candidate))
        if abs(times[best] - t) <= tolerance:
            matched.append((float(yaw_rows[best]["yaw_ned_deg"]), 1.5))
        else:
            matched.append(None)
    last: tuple[float, float] | None = None
    for index, value in enumerate(matched):
        if value is None and last is not None:
            matched[index] = last
        elif value is not None:
            last = value
    following: tuple[float, float] | None = None
    for index in range(len(matched) - 1, -1, -1):
        value = matched[index]
        if value is None and following is not None:
            matched[index] = following
        elif value is not None:
            following = value
    if any(value is None for value in matched):
        raise FinalV23CleanInputError("exact clean A1 yaw merge left missing rows")
    for gnss, value in zip(gnss_rows, matched):
        assert value is not None
        gnss[13], gnss[14] = value


def _write_exact_input_tables(gnss_path: Path, imu_path: Path,
                              gnss_rows: Sequence[Sequence[float]],
                              imu_rows: Sequence[Sequence[float]]) -> None:
    with gnss_path.open("w", encoding="utf-8") as handle:
        for row in gnss_rows:
            handle.write(" ".join(f"{float(value):.6f}" for value in row) + "\n")
    with imu_path.open("w", encoding="utf-8") as handle:
        for row in imu_rows:
            handle.write(
                f"{float(row[0]):.6f} "
                + " ".join(f"{float(value):.8f}" for value in row[1:])
                + "\n"
            )


def _read_numeric_table(path: Path, columns: Sequence[str]) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            if len(parts) != len(columns):
                raise FinalV23CleanInputError(
                    f"{path.name} row {number} has {len(parts)} columns; expected {len(columns)}"
                )
            try:
                values = [float(value) for value in parts]
            except ValueError as exc:
                raise FinalV23CleanInputError(
                    f"{path.name} row {number} contains a non-numeric field"
                ) from exc
            if not all(math.isfinite(value) for value in values):
                raise FinalV23CleanInputError(
                    f"{path.name} row {number} contains a non-finite field"
                )
            rows.append(values)
    if not rows:
        raise FinalV23CleanInputError(f"{path.name} is empty")
    return rows


def audit_time_rows(rows: Sequence[Sequence[float]], *, label: str) -> dict[str, Any]:
    times = [float(row[0]) for row in rows]
    non_increasing = sum(right <= left for left, right in zip(times, times[1:]))
    return {
        "label": label,
        "row_count": len(rows),
        "time_start_seconds": times[0],
        "time_end_seconds": times[-1],
        "strictly_increasing": non_increasing == 0,
        "non_increasing_transition_count": non_increasing,
    }


def build_column_audit(
    rows: Sequence[Sequence[float]], contract: Mapping[str, Any]
) -> list[dict[str, Any]]:
    input_format = contract.get("input_format")
    definitions = input_format.get("columns") if isinstance(input_format, Mapping) else None
    if not isinstance(definitions, list) or len(definitions) != len(GNSS_COLUMNS):
        raise FinalV23CleanInputError("contract 15-column definitions are incomplete")
    output: list[dict[str, Any]] = []
    for offset, name in enumerate(GNSS_COLUMNS):
        definition = definitions[offset]
        if not isinstance(definition, Mapping) or definition.get("name") != name:
            raise FinalV23CleanInputError(f"contract column {offset + 1} is not {name}")
        values = [float(row[offset]) for row in rows]
        output.append(
            {
                "index": offset + 1,
                "name": name,
                "unit": definition.get("unit", ""),
                "source": definition.get("source", ""),
                "row_count": len(values),
                "finite_count": sum(math.isfinite(value) for value in values),
                "missing_count": 0,
                "minimum": min(values),
                "maximum": max(values),
            }
        )
    return output


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def build_source_ledger(verified_hashes: Mapping[str, str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for order, (relative, (role, reader)) in enumerate(
        ACTUAL_SOURCE_ROLES.items(), start=1
    ):
        digest = verified_hashes.get(relative)
        if not digest:
            raise FinalV23CleanInputError(f"verified hash missing for {relative}")
        candidates.append(
            {
                "relative_path": relative,
                "role": role,
                "expected_sha256": digest,
                "actual_sha256": digest,
                "reader_component": reader,
                "reason": "clean-real final_v23 input generation",
                "output_provider_lineage": f"provider://{PROFILE_ID}",
                "read_order": order,
                "path_alias": f"raw://{relative}",
                "sha256": digest,
            }
        )
    validated = validate_provider_source_read_set(candidates, verified_hashes)
    by_relative = {row["relative_path"]: row for row in candidates}
    return [by_relative[row["relative_path"]] for row in validated]


def _guard_output_root(paths: CleanPaths, output_root: str | Path) -> Path:
    provider_parent = guard_path(
        paths.clean_root / "04_PROVIDER_FREEZE",
        role="CLEAN1R2R1 provider parent",
        allowed_root=paths.clean_root,
    )
    root = guard_path(
        Path(output_root),
        role="CLEAN1R2R1 provider attempt",
        allowed_root=provider_parent,
    )
    if root.parent != provider_parent:
        raise FinalV23CleanInputError("provider attempt must be a direct child of 04_PROVIDER_FREEZE")
    if not root.name.startswith("FINAL_V23_CLEAN_"):
        raise FinalV23CleanInputError("provider attempt name must start with FINAL_V23_CLEAN_")
    if root.exists():
        raise FinalV23CleanInputError("provider attempt root already exists")
    return root


def validate_clean_input_manifest(
    payload: Mapping[str, Any], *, require_post_raw_checkpoint: bool = True
) -> None:
    expected_false = (
        "synthetic_data_used",
        "semisynthetic_data_used",
        "trace_used_online",
        "yaw_noise_injection_enabled",
        "receiver_imu_as_body_imu",
        "legacy_input_payload_used",
        "final_v23_output_solver_input",
        "LegSA_output_solver_input",
        "per_case_tuning",
        "output_only_correction",
        "epoch_deleted_for_metric",
    )
    if payload.get("schema_version") != MANIFEST_SCHEMA:
        raise FinalV23CleanInputError("clean input manifest schema mismatch")
    if (
        payload.get("stage_id") != STAGE_ID
        or payload.get("protocol_id") != PROTOCOL_ID
        or payload.get("case_id") != CASE_ID
        or payload.get("profile_id") != PROFILE_ID
    ):
        raise FinalV23CleanInputError("clean input manifest identity mismatch")
    if payload.get("data_mode") != "real_by2_raw":
        raise FinalV23CleanInputError("clean input manifest data_mode mismatch")
    for field in expected_false:
        if payload.get(field) is not False:
            raise FinalV23CleanInputError(f"clean input forbidden field is not false: {field}")
    if payload.get("trace_open_count_during_input_generation") != 0:
        raise FinalV23CleanInputError("trace was opened during input generation")
    if payload.get("yaw_noise_injection_std_deg") != 0.0:
        raise FinalV23CleanInputError("yaw noise std is not zero")
    if payload.get("yaw_measurement_std_deg") != 1.5:
        raise FinalV23CleanInputError("yaw measurement std is not 1.5 deg")
    if payload.get("old_runtime_input_count") != 0:
        raise FinalV23CleanInputError("old runtime input count is not zero")
    if payload.get("E001_old_input_used_by_solver") is not False:
        raise FinalV23CleanInputError("E001 old input is not explicitly excluded")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != {"imu", "gnss"}:
        raise FinalV23CleanInputError("clean input artifacts are incomplete")
    if artifacts["imu"].get("column_count") != 7:
        raise FinalV23CleanInputError("clean IMU artifact is not 7 columns")
    if artifacts["gnss"].get("column_count") != 15:
        raise FinalV23CleanInputError("clean GNSS artifact is not 15 columns")
    raw_hashes = payload.get("raw_source_hashes")
    if not isinstance(raw_hashes, Mapping) or set(raw_hashes) != set(BY2_RAW_RELATIVE_PATHS):
        raise FinalV23CleanInputError("clean input manifest does not bind exact BY2 22")
    actual_hashes = payload.get("actual_generation_source_hashes")
    if not isinstance(actual_hashes, Mapping) or set(actual_hashes) != set(ACTUAL_SOURCE_ROLES):
        raise FinalV23CleanInputError("clean input manifest actual read set is not exact four")
    if BY2_TRACE_RELATIVE_PATH in actual_hashes:
        raise FinalV23CleanInputError("trace appears in input-generation read set")
    if require_post_raw_checkpoint:
        if payload.get("file_open_audit_sealed") is not True:
            raise FinalV23CleanInputError("clean input file-open audit is not sealed")
        if payload.get("trace_open_count_during_input_generation") != 0:
            raise FinalV23CleanInputError("sealed clean input trace-open count is nonzero")
        if not isinstance(payload.get("file_open_audit_sha256"), str):
            raise FinalV23CleanInputError("clean input file-open audit hash is missing")
        if payload.get("terminal_status") != "PASS_CLEAN_FINAL_V23_INPUT_GENERATION":
            raise FinalV23CleanInputError("clean input manifest is not post-checkpoint sealed")
        post = payload.get("raw_post_generation")
        mutation = payload.get("raw_mutation_audit")
        if not isinstance(post, Mapping) or post.get("verified") != 22 or post.get("passed") is not True:
            raise FinalV23CleanInputError("post-generation raw checkpoint is missing")
        if not isinstance(mutation, Mapping) or mutation.get("passed") is not True:
            raise FinalV23CleanInputError("raw mutation audit is missing")


def generate_final_v23_clean_input(
    paths: CleanPaths,
    *,
    output_root: str | Path,
    contract_path: str | Path,
    raw_pre_checkpoint: Mapping[str, Any],
    expected_code_commit: str | None = None,
    expected_raw_lock_sha256: str = EXPECTED_RAW_LOCK_SHA256,
    max_status_rows: int | None = None,
    max_raw_rows: int | None = None,
    max_imu_messages: int | None = None,
    raw_pre_checkpoint_phase: str = "pre_generation",
) -> dict[str, Any]:
    """Generate one immutable attempt; callers must supply a new direct child root."""

    contract = load_contract(contract_path)
    profile = contract["profiles"][PROFILE_ID]
    root = _guard_output_root(paths, output_root)
    commit, dirty = git_code_state(paths.code_root)
    if dirty:
        raise FinalV23CleanInputError("clean input generation requires a clean Git worktree")
    if expected_code_commit is not None and commit != expected_code_commit:
        raise FinalV23CleanInputError("clean input generator commit does not match code freeze")

    if sha256_file(paths.raw_hash_lock) != expected_raw_lock_sha256:
        raise FinalV23CleanInputError("raw hash lock SHA256 mismatch")
    lock = read_hash_lock(paths.raw_hash_lock)
    if len(lock) != EXPECTED_FULL_LOCK_ROWS:
        raise FinalV23CleanInputError("raw hash lock full row count mismatch")
    locked_by2 = {
        relative: row for relative, row in lock.items() if row.get("dataset") == "BY2"
    }
    if set(locked_by2) != set(BY2_RAW_RELATIVE_PATHS):
        raise FinalV23CleanInputError("raw hash lock BY2 path set mismatch")
    pre_verified_hashes = validate_raw_checkpoint(
        raw_pre_checkpoint,
        phase=raw_pre_checkpoint_phase,
        lock=locked_by2,
        expected_lock_sha256=expected_raw_lock_sha256,
    )
    actual_pre_hashes = verify_raw_sources(
        paths.raw_root, ACTUAL_SOURCE_ROLES, locked_by2
    )
    source_utc_day_midnight = infer_source_day_base_time(
        paths.by2_fix_root / "gnss1-status.csv"
    )
    expected_base_time = float(contract["time_contract"]["base_time_unix_seconds"])
    # The archived runtime freezes Beijing-local day origin (UTC midnight plus
    # eight hours), while the maintained helper intentionally reports UTC day
    # midnight.  Validate that exact relationship instead of replacing the
    # archived base_time with a newly inferred value.
    if expected_base_time - source_utc_day_midnight != 8.0 * 3600.0:
        raise FinalV23CleanInputError(
            "source UTC-day origin is inconsistent with archived +08:00 base_time"
        )

    root.mkdir(parents=True, exist_ok=False)
    scratch = root / ".compat-builder"
    try:
        generated = _generate_process_data_compat_with_active_pvt(
            paths.by2_fix_root,
            paths.by2_go2_body,
            scratch,
            base_time=expected_base_time,
            yaw_source_mode="status",
            yaw_sign=1.0,
            yaw_install_offset_deg=0.0,
            yaw_std_mode="fixed_1p5",
            status_fixed_yaw_std_deg=float(profile["yaw_measurement_std_deg"]),
            enable_outage=False,
            outlier_mode="none",
            yaw_noise_std_deg=0.0,
            imu_install_roll_deg=-1.0,
            imu_install_pitch_deg=0.0,
            imu_install_yaw_deg=0.0,
            imu_gnss_time_offset=0.0,
            receiver_velocity_match_tolerance_seconds=0.1,
            dual_yaw_match_tolerance_seconds=0.6,
            receiver_velocity_std_mps=0.05,
            stage_id=STAGE_ID,
            max_status_rows=max_status_rows,
            max_raw_rows=max_raw_rows,
            max_imu_messages=max_imu_messages,
        )
        report = generated["report"]
        if (
            report.get("trace_solver_input") is not False
            or report.get("trace_yaw_for_solver") is not False
            or report.get("yaw_noise_injection") is not False
            or report.get("yaw_noise_std_deg") != 0.0
            or report.get("yaw_source") != "A1_dual_diff_status"
            or report.get("receiver_velocity_std_mps") != 0.05
        ):
            raise FinalV23CleanInputError("maintained builder violated clean-real profile")

        imu_path = root / IMU_OUTPUT_NAME
        gnss_path = root / GNSS_OUTPUT_NAME
        os.replace(generated["imu_path"], imu_path)
        os.replace(generated["gnss_path"], gnss_path)

        gnss_rows = _read_numeric_table(gnss_path, GNSS_COLUMNS)
        imu_rows = _read_numeric_table(imu_path, IMU_COLUMNS)
        clean_yaw_rows, clean_yaw_audit = build_clean_a1_yaw_rows(
            paths.by2_fix_root / "gnss1-status.csv",
            paths.by2_fix_root / "gnss2-status.csv",
            base_time=expected_base_time,
            max_rows=max_status_rows,
        )
        _apply_exact_clean_yaw(gnss_rows, clean_yaw_rows, tolerance=0.6)
        _write_exact_input_tables(gnss_path, imu_path, gnss_rows, imu_rows)
        # Re-read the serialized payload so every audit/hash describes the
        # exact bytes consumed by both solvers, not pre-serialization floats.
        gnss_rows = _read_numeric_table(gnss_path, GNSS_COLUMNS)
        imu_rows = _read_numeric_table(imu_path, IMU_COLUMNS)
        if any(not -180.0 <= row[13] < 180.0 or row[14] != 1.5 for row in gnss_rows):
            raise FinalV23CleanInputError("exact clean yaw range/std serialization mismatch")
        imu_report = generated["imu_report"]
        if (
            imu_report.get("receiver_imu_as_body_imu") is not False
            or imu_report.get("flu_to_frd_applied_once") is not True
            or imu_report.get("imu_install_correction_rpy_deg") != [-1.0, 0.0, 0.0]
            or imu_report.get("imu_row_count") != len(imu_rows)
            or not 0 < int(imu_report.get("gyro_bias_window", 0)) <= 1000
        ):
            raise FinalV23CleanInputError("maintained IMU builder violated final_v23 contract")
        gnss_time = audit_time_rows(gnss_rows, label="gnss_15_column")
        imu_time = audit_time_rows(imu_rows, label="imu_increment_7_column")
        if not gnss_time["strictly_increasing"] or not imu_time["strictly_increasing"]:
            raise FinalV23CleanInputError("fresh input timestamps are not strictly increasing")

        column_rows = build_column_audit(gnss_rows, contract)
        _write_csv(
            root / COLUMN_AUDIT_NAME,
            column_rows,
            (
                "index",
                "name",
                "unit",
                "source",
                "row_count",
                "finite_count",
                "missing_count",
                "minimum",
                "maximum",
            ),
        )

        source_ledger = build_source_ledger(actual_pre_hashes)
        _write_csv(
            root / SOURCE_LEDGER_NAME,
            source_ledger,
            (
                "read_order",
                "path_alias",
                "relative_path",
                "role",
                "sha256",
                "expected_sha256",
                "actual_sha256",
                "reader_component",
                "reason",
                "output_provider_lineage",
            ),
        )

        time_audit = {
            "schema_version": "paper_rebuild.final_v23_clean_input_time_audit.v1",
            "base_time_unix_seconds": expected_base_time,
            "source_utc_day_midnight_unix_seconds": source_utc_day_midnight,
            "archive_base_time_offset_from_utc_midnight_seconds": 28800.0,
            "runtime_window_seconds": [
                float(contract["time_contract"]["starttime_seconds"]),
                float(contract["time_contract"]["endtime_seconds"]),
            ],
            "gnss": gnss_time,
            "imu": imu_time,
            "serialization_contract": {
                "gnss_float_format": "%.6f",
                "imu_time_format": "%.6f",
                "imu_increment_format": "%.8f",
            },
            "dual_yaw_contract_audit": clean_yaw_audit,
            "imu_contract_audit": {
                "column_count": len(IMU_COLUMNS),
                "columns": list(IMU_COLUMNS),
                "source": "raw://BY2_GO2_BODY/by2.txt",
                "source_frame": "FLU",
                "solver_frame": "FRD",
                "flu_to_frd_applied_once": True,
                "imu_install_rpy_deg": [-1.0, 0.0, 0.0],
                "gyro_bias_window": imu_report["gyro_bias_window"],
                "first_frame_emitted": False,
                "receiver_imu_as_body_imu": False,
                "increment_policy": "current_sample_times_dt",
                "skipped_invalid_dt_count": imu_report["skipped_dt_count"],
            },
        }
        write_json_atomic(root / TIME_AUDIT_NAME, time_audit)

        no_trace_audit = {
            "schema_version": "paper_rebuild.final_v23_clean_no_trace_no_injection.v1",
            "profile_id": PROFILE_ID,
            "data_mode": "real_by2_raw",
            "trace_path_parameter_present": False,
            "trace_reader_present": False,
            "trace_open_count_during_input_generation": 0,
            "actual_file_open_audit_external_seal_required": True,
            "trace_integrity_hash_audit_is_not_provider_generation": True,
            "trace_used_online": False,
            "yaw_source": "A1_dual_diff_status",
            "yaw_wrap_range": "[-180,180)",
            "status2_to_status1_interpolation": "numpy_linear_with_endpoint_hold",
            "yaw_measurement_std_deg": 1.5,
            "yaw_measurement_std_role": "measurement_covariance_R",
            "yaw_noise_injection_enabled": False,
            "yaw_noise_injection_std_deg": 0.0,
            "yaw_noise_seed": None,
            "random_number_generator_used": False,
            "semisynthetic_data_used": False,
            "legacy_input_payload_used": False,
            "actual_generation_source_count": len(source_ledger),
            "actual_generation_source_paths": [row["relative_path"] for row in source_ledger],
            "trace_relative_path_excluded": BY2_TRACE_RELATIVE_PATH not in ACTUAL_SOURCE_ROLES,
            "clean_yaw_contract_audit": clean_yaw_audit,
        }
        write_json_atomic(root / NO_TRACE_AUDIT_NAME, no_trace_audit)

        actual_post_hashes = verify_raw_sources(
            paths.raw_root, ACTUAL_SOURCE_ROLES, locked_by2
        )
        changed_actual = sorted(
            relative
            for relative in ACTUAL_SOURCE_ROLES
            if actual_pre_hashes.get(relative) != actual_post_hashes.get(relative)
        )
        if changed_actual:
            raise FinalV23CleanInputError(
                "actual input source mutation detected: " + ",".join(changed_actual)
            )

        final_commit, final_dirty = git_code_state(paths.code_root)
        if final_commit != commit or final_dirty:
            raise FinalV23CleanInputError("Git code state changed during input generation")

        artifacts = {
            "imu": {
                "relative_path": IMU_OUTPUT_NAME,
                "sha256": sha256_file(imu_path),
                "row_count": len(imu_rows),
                "column_count": len(IMU_COLUMNS),
            },
            "gnss": {
                "relative_path": GNSS_OUTPUT_NAME,
                "sha256": sha256_file(gnss_path),
                "row_count": len(gnss_rows),
                "column_count": len(GNSS_COLUMNS),
            },
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "stage_id": STAGE_ID,
            "profile_id": PROFILE_ID,
            "protocol_id": PROTOCOL_ID,
            "case_id": CASE_ID,
            "terminal_status": "AWAITING_EXTERNAL_POST_GENERATION_RAW_CHECKPOINT",
            "data_mode": "real_by2_raw",
            "base_time_unix_seconds": expected_base_time,
            "source_utc_day_midnight_unix_seconds": source_utc_day_midnight,
            "archive_base_time_offset_from_utc_midnight_seconds": 28800.0,
            "generator_code_commit": commit,
            "generator_worktree_dirty": False,
            "contract_sha256": sha256_file(contract_path),
            "generation_config_sha256": sha256_text(
                json.dumps(
                    {
                        "profile_id": PROFILE_ID,
                        "base_time": expected_base_time,
                        "yaw_source": "A1_dual_diff_status",
                        "yaw_measurement_std_deg": 1.5,
                        "yaw_noise_injection_std_deg": 0.0,
                        "velocity_std_mps": 0.05,
                        "imu_install_rpy_deg": [-1.0, 0.0, 0.0],
                        "velocity_tolerance_seconds": 0.1,
                        "dual_yaw_tolerance_seconds": 0.6,
                        "status2_interpolation": "numpy_linear_with_endpoint_hold",
                        "yaw_wrap_range": "[-180,180)",
                        "gnss_float_format": "%.6f",
                        "imu_time_format": "%.6f",
                        "imu_increment_format": "%.8f",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            "raw_source_hashes": dict(pre_verified_hashes),
            "actual_generation_source_hashes": {
                row["relative_path"]: row["sha256"] for row in source_ledger
            },
            "raw_pre_generation": dict(raw_pre_checkpoint),
            "raw_actual_source_pre_generation": dict(actual_pre_hashes),
            "raw_actual_source_post_generation": dict(actual_post_hashes),
            "raw_actual_source_mutation_count": len(changed_actual),
            "raw_post_generation": None,
            "raw_mutation_audit": None,
            "artifacts": artifacts,
            "column_audit_relative_path": COLUMN_AUDIT_NAME,
            "time_audit_relative_path": TIME_AUDIT_NAME,
            "source_ledger_relative_path": SOURCE_LEDGER_NAME,
            "no_trace_no_injection_audit_relative_path": NO_TRACE_AUDIT_NAME,
            "receiver_velocity_parser_adapter_id": RECEIVER_VELOCITY_PARSER_ADAPTER_ID,
            "receiver_velocity_sAcc_full_frame_offsets": [74, 78],
            "receiver_velocity_provider_std_mps": [0.05, 0.05, 0.05],
            "dual_yaw_source": "A1_dual_diff_status",
            "dual_yaw_contract_audit": clean_yaw_audit,
            "gnss_float_format": "%.6f",
            "imu_time_format": "%.6f",
            "imu_increment_format": "%.8f",
            "yaw_measurement_std_deg": 1.5,
            "yaw_measurement_std_role": "measurement_covariance_R",
            "yaw_noise_injection_enabled": False,
            "yaw_noise_injection_std_deg": 0.0,
            "yaw_noise_seed": None,
            "trace_open_count_during_input_generation": 0,
            "file_open_audit_sealed": False,
            "file_open_audit_sha256": None,
            "file_open_trace_sha256": None,
            "trace_used_online": False,
            "synthetic_data_used": False,
            "semisynthetic_data_used": False,
            "receiver_imu_as_body_imu": False,
            "legacy_input_payload_used": False,
            "E001_old_input_used_by_solver": False,
            "old_runtime_input_count": 0,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deleted_for_metric": False,
        }
        validate_clean_input_manifest(manifest, require_post_raw_checkpoint=False)
        write_json_atomic(root / MANIFEST_NAME, manifest)
        return manifest
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def seal_clean_input_file_open_audit(
    manifest_path: str | Path,
    *,
    strace_path: str | Path,
    raw_root: str | Path,
    code_root: str | Path,
) -> dict[str, Any]:
    """Bind the generator's actual openat trace before post-raw sealing."""

    source = Path(manifest_path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FinalV23CleanInputError("clean input manifest must be an object")
    validate_clean_input_manifest(payload, require_post_raw_checkpoint=False)
    if payload.get("file_open_audit_sealed") is not False:
        raise FinalV23CleanInputError("clean input file-open audit was already sealed")
    raw = Path(raw_root).resolve(strict=True)
    trace_file = Path(strace_path).resolve(strict=True)
    opened = parse_strace_openat_paths(trace_file, cwd=code_root)
    raw_opened = [path for path in opened if is_within(path, raw)]
    expected = {
        relative: (raw / relative).resolve(strict=True)
        for relative in ACTUAL_SOURCE_ROLES
    }
    counts = {
        relative: sum(path == candidate for path in raw_opened)
        for relative, candidate in expected.items()
    }
    expected_paths = set(expected.values())
    unexpected = sorted(
        path.relative_to(raw).as_posix()
        for path in set(raw_opened)
        if path not in expected_paths
    )
    trace_path = (raw / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    trace_count = sum(path == trace_path for path in raw_opened)
    missing = sorted(relative for relative, count in counts.items() if count == 0)
    audit = {
        "schema_version": "paper_rebuild.final_v23_clean_input_file_open_audit.v1",
        "strace_sha256": sha256_file(trace_file),
        "expected_raw_open_counts": counts,
        "missing_expected_raw_opens": missing,
        "unexpected_raw_root_relative_paths": unexpected,
        "trace_open_count": trace_count,
        "trace_opened_during_input_generation": trace_count > 0,
        "passed": not missing and not unexpected and trace_count == 0,
    }
    if not audit["passed"]:
        raise FinalV23CleanInputError("clean input file-open audit failed")
    audit_path = write_json_atomic(source.parent / FILE_OPEN_AUDIT_NAME, audit)
    payload["trace_open_count_during_input_generation"] = trace_count
    payload["file_open_audit_sealed"] = True
    payload["file_open_audit_sha256"] = sha256_file(audit_path)
    payload["file_open_trace_sha256"] = sha256_file(trace_file)
    write_json_atomic(source, payload)
    return payload


def seal_clean_input_post_raw_checkpoint(
    manifest_path: str | Path,
    *,
    raw_post_checkpoint: Mapping[str, Any],
    raw_hash_lock_path: str | Path,
    expected_raw_lock_sha256: str = EXPECTED_RAW_LOCK_SHA256,
    raw_post_checkpoint_phase: str = "post_generation",
) -> dict[str, Any]:
    """Seal a generated manifest from an outer post-generation 22/22 audit.

    Only the checkpoint JSON and hash-lock metadata are read here.  Raw source
    files, including trace, remain outside this module's read set.
    """

    source = Path(manifest_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FinalV23CleanInputError("clean input manifest must be an object")
    validate_clean_input_manifest(payload, require_post_raw_checkpoint=False)
    if payload.get("terminal_status") != "AWAITING_EXTERNAL_POST_GENERATION_RAW_CHECKPOINT":
        raise FinalV23CleanInputError("clean input manifest is not awaiting post checkpoint")
    lock_path = Path(raw_hash_lock_path)
    if sha256_file(lock_path) != expected_raw_lock_sha256:
        raise FinalV23CleanInputError("raw hash lock SHA256 mismatch during seal")
    lock = read_hash_lock(lock_path)
    locked_by2 = {
        relative: row for relative, row in lock.items() if row.get("dataset") == "BY2"
    }
    post_hashes = validate_raw_checkpoint(
        raw_post_checkpoint,
        phase=raw_post_checkpoint_phase,
        lock=locked_by2,
        expected_lock_sha256=expected_raw_lock_sha256,
    )
    pre_hashes = payload.get("raw_source_hashes")
    changed = sorted(
        relative
        for relative in BY2_RAW_RELATIVE_PATHS
        if not isinstance(pre_hashes, Mapping)
        or pre_hashes.get(relative) != post_hashes.get(relative)
    )
    mutation = {
        "schema_version": "paper-rebuild-by2-raw-mutation-audit-v1",
        "pre_verified": len(pre_hashes) if isinstance(pre_hashes, Mapping) else 0,
        "post_verified": len(post_hashes),
        "raw_mutation": len(changed),
        "changed_relative_paths": changed,
        "passed": not changed and len(post_hashes) == EXPECTED_BY2_LOCK_ROWS,
    }
    if not mutation["passed"]:
        raise FinalV23CleanInputError("outer raw mutation checkpoint failed")
    payload["raw_post_generation"] = dict(raw_post_checkpoint)
    payload["raw_mutation_audit"] = mutation
    payload["terminal_status"] = "PASS_CLEAN_FINAL_V23_INPUT_GENERATION"
    validate_clean_input_manifest(payload, require_post_raw_checkpoint=True)
    write_json_atomic(source, payload)
    return payload


def load_clean_input_manifest(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FinalV23CleanInputError("clean input manifest must be an object")
    validate_clean_input_manifest(payload, require_post_raw_checkpoint=True)
    root = source.parent.resolve(strict=True)
    file_open_audit = root / FILE_OPEN_AUDIT_NAME
    if (
        not file_open_audit.is_file()
        or sha256_file(file_open_audit) != payload.get("file_open_audit_sha256")
    ):
        raise FinalV23CleanInputError("clean input file-open audit is missing or changed")
    for role, artifact in payload["artifacts"].items():
        relative = artifact.get("relative_path")
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise FinalV23CleanInputError(f"unsafe {role} artifact path")
        candidate = (root / relative).resolve(strict=True)
        if root not in candidate.parents or not candidate.is_file():
            raise FinalV23CleanInputError(f"{role} artifact escapes manifest root")
        if sha256_file(candidate) != artifact.get("sha256"):
            raise FinalV23CleanInputError(f"{role} artifact hash mismatch")
    return payload
