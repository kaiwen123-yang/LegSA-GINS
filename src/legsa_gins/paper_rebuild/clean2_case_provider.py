"""Materialize source-isolated CLEAN2 Classic-18 case provider bundles."""

from __future__ import annotations

import bisect
import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .clean2_classic_cases import (
    AlignedGnssEpoch,
    ClassicCaseApplication,
    ClassicCaseCatalog,
    ClassicCaseError,
    apply_classic_case,
    load_classic_case_catalog,
    wrap_signed,
)
from .evidence import write_csv_atomic
from .final_v23_clean_input import (
    EXPECTED_RAW_LOCK_SHA256,
    load_raw_checkpoint,
    validate_raw_checkpoint,
)
from .final_v23_clean_parity import load_clean_bundle
from .clean1r2r1_formal import validate_auxiliary_bundle
from .clean2_stage_paths import (
    guard_clean2_stage_path,
    load_clean2_stage_paths,
)
from .manifest import (
    git_code_state,
    read_hash_lock,
    sha256_file,
    sha256_text,
    write_json_atomic,
)
from .paths import is_within


GNSS_COLUMN_COUNT = 18
BASE_GNSS_COLUMN_COUNT = 15
RAW_PRE_PHASE = "pre_provider"
RAW_POST_PHASE = "post_provider"
RAW_AUDIT_PHASES = (RAW_PRE_PHASE, RAW_POST_PHASE, "post_run")
EXPECTED_BASE_PROVIDER_HASHES = {
    "imu": "a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b",
    "gnss": "f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22",
    "raw_doppler": "a40b9933295f6c2c989884d67cc674313f2fe03113c8acdf1d02ddf28734d722",
    "go2_roll_pitch": "2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a",
    "go2_horizontal_velocity": "f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0",
}
LEDGER_FIELDS = (
    "case_id",
    "seed",
    "time",
    "operation",
    "selected",
    "original_baseline_e",
    "original_baseline_n",
    "original_baseline_u",
    "modified_baseline_e",
    "modified_baseline_n",
    "modified_baseline_u",
    "original_length",
    "modified_length",
    "original_yaw",
    "modified_yaw",
    "yaw_delta_wrap_deg",
    "original_yaw_std",
    "modified_yaw_std",
    "original_yaw_valid",
    "modified_yaw_valid",
    "position_valid",
    "receiver_velocity_valid",
    "operation_input_baseline_e",
    "operation_input_baseline_n",
    "operation_input_baseline_u",
    "operation_input_yaw",
    "operation_input_yaw_std",
    "operation_input_yaw_valid",
)
PROVIDER_FIELDS = (
    "case_id",
    "time",
    "baseline_e_m",
    "baseline_n_m",
    "baseline_u_m",
    "baseline_d_m",
    "baseline_length_m",
    "body_yaw_ned_deg",
    "yaw_std_deg",
    "position_valid",
    "receiver_velocity_valid",
    "yaw_valid",
    "source_layer",
    "gnss_order",
    "trace_used",
)
REQUIRED_SHARED_HASH_ROLES = (
    "imu",
    "raw_doppler",
    "go2_roll_pitch",
    "go2_horizontal_velocity",
)


class Clean2CaseProviderError(ClassicCaseError):
    """Case-provider materialization failed a source or hash isolation gate."""


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _read_base_gnss(path: Path) -> tuple[list[tuple[str, ...]], bytes, dict[str, Any]]:
    """Accept sealed 15-col C00 or existing 18-col input and freeze 15-col parity.

    Fresh CLEAN1R2R1 evidence is 15 columns.  CLEAN2 adds three explicit
    validity flags as textual ``1 1 1`` and never reparses/reformats the first
    fifteen source tokens.
    """

    payload = path.read_bytes()
    rows: list[tuple[str, ...]] = []
    source_first15: list[tuple[str, ...]] = []
    source_widths: set[int] = set()
    for number, raw_line in enumerate(payload.decode("utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = tuple(stripped.split())
        if len(fields) not in {BASE_GNSS_COLUMN_COUNT, GNSS_COLUMN_COUNT}:
            raise Clean2CaseProviderError(
                f"Current formal GNSS row {number} has {len(fields)} columns, expected 15 or 18"
            )
        source_widths.add(len(fields))
        if len(source_widths) != 1:
            raise Clean2CaseProviderError("Base GNSS mixes 15- and 18-column rows")
        try:
            numeric = [float(value) for value in fields[:15]]
        except ValueError as exc:
            raise Clean2CaseProviderError(f"Invalid GNSS numeric field at row {number}") from exc
        if not all(math.isfinite(value) for value in numeric):
            raise Clean2CaseProviderError("GNSS input contains NaN or infinity")
        if len(fields) == GNSS_COLUMN_COUNT and any(
            value not in {"0", "1"} for value in fields[15:18]
        ):
            raise Clean2CaseProviderError(
                "Current formal GNSS explicit validity fields must be 0 or 1"
            )
        source_first15.append(fields[:15])
        rows.append(fields if len(fields) == GNSS_COLUMN_COUNT else (*fields, "1", "1", "1"))
    if not rows:
        raise Clean2CaseProviderError("Current formal GNSS input is empty")
    times = [float(row[0]) for row in rows]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise Clean2CaseProviderError("GNSS input timestamps are not strictly increasing")
    extended_payload = ("\n".join(" ".join(fields) for fields in rows) + "\n").encode("utf-8")
    token_parity = all(row[:15] == original for row, original in zip(rows, source_first15))
    numerical_parity = all(
        all(float(left) == float(right) for left, right in zip(row[:15], original))
        for row, original in zip(rows, source_first15)
    )
    if not token_parity or not numerical_parity:
        raise Clean2CaseProviderError("C00 15-to-18 extension changed a frozen source field")
    return rows, extended_payload, {
        "source_column_count": next(iter(source_widths)),
        "extended_column_count": GNSS_COLUMN_COUNT,
        "row_count": len(rows),
        "first15_token_parity": token_parity,
        "first15_numerical_parity": numerical_parity,
        "appended_validity_tokens": ["1", "1", "1"] if next(iter(source_widths)) == 15 else "preexisting_explicit_validity",
        "source_payload_sha256": sha256_file(path),
        "extended_payload_sha256": sha256_text(extended_payload.decode("utf-8")),
    }


def _read_extended_gnss(path: Path) -> tuple[list[tuple[str, ...]], bytes]:
    """Compatibility helper used by focused tests; formal generation uses _read_base_gnss."""

    rows, payload, _ = _read_base_gnss(path)
    return rows, payload


def _read_dual_provider(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        numeric_required = {
            "time",
            "baseline_n_m",
            "baseline_e_m",
            "baseline_d_m",
            "baseline_length_m",
            "body_yaw_ned_deg",
            "yaw_std_deg",
        }
        required = numeric_required | {
            "physical_in_band",
            "gnss_order",
            "lateral_to_body_offset_deg",
            "wrap_safe_residual",
            "trace_sign_or_offset_selection",
        }
        if not required.issubset(reader.fieldnames or ()):
            raise Clean2CaseProviderError("Base dual-yaw provider schema is incomplete")
        for number, row in enumerate(reader, start=2):
            try:
                parsed = {field: float(row[field]) for field in numeric_required}
            except (TypeError, ValueError) as exc:
                raise Clean2CaseProviderError(
                    f"Invalid base dual-yaw provider row {number}"
                ) from exc
            if not all(math.isfinite(value) for value in parsed.values()):
                raise Clean2CaseProviderError("Base dual-yaw provider contains NaN or infinity")
            length = math.sqrt(
                parsed["baseline_e_m"] ** 2
                + parsed["baseline_n_m"] ** 2
                + parsed["baseline_d_m"] ** 2
            )
            expected_yaw = (
                math.degrees(
                    math.atan2(parsed["baseline_e_m"], parsed["baseline_n_m"])
                )
                + 90.0
            ) % 360.0
            declared_in_band = str(row["physical_in_band"]).strip().casefold() == "true"
            expected_in_band = 0.20 <= length <= 0.60
            if (
                not 0.0 < length <= 0.60
                or abs(length - parsed["baseline_length_m"]) > 1.0e-9
                or declared_in_band != expected_in_band
                or str(row["gnss_order"]) != "GNSS2-GNSS1"
                or not math.isclose(float(row["lateral_to_body_offset_deg"]), 90.0)
                or str(row["wrap_safe_residual"]).strip().casefold() != "true"
                or str(row["trace_sign_or_offset_selection"]).strip().casefold() != "false"
                or abs(
                wrap_signed(parsed["body_yaw_ned_deg"] - expected_yaw)
                ) > 1.0e-6
            ):
                raise Clean2CaseProviderError(
                    "Base dual-yaw provider violates the frozen physical vector/yaw gate"
                )
            rows.append(parsed)
    if not rows or any(
        right["time"] <= left["time"] for left, right in zip(rows, rows[1:])
    ):
        raise Clean2CaseProviderError("Base dual-yaw provider timestamps are invalid")
    return rows


def _nearest_provider_row(
    rows: Sequence[Mapping[str, float]], times: Sequence[float], value: float
) -> tuple[Mapping[str, float], float]:
    index = bisect.bisect_left(times, value)
    candidates: list[Mapping[str, float]] = []
    if index > 0:
        candidates.append(rows[index - 1])
    if index < len(rows):
        candidates.append(rows[index])
    if not candidates:
        raise Clean2CaseProviderError("Base dual-yaw provider has no nearest row")
    candidate = min(candidates, key=lambda row: abs(float(row["time"]) - value))
    return candidate, abs(float(candidate["time"]) - value)


def align_gnss_with_dual_provider(
    gnss_rows: Sequence[tuple[str, ...]],
    dual_rows: Sequence[Mapping[str, float]],
    *,
    tolerance_seconds: float = 0.6,
    yaw_tolerance_deg: float = 1.0e-3,
    runtime_window_seconds: tuple[float, float] = (66.0, 340.0),
) -> list[AlignedGnssEpoch]:
    """Attach the source-backed A1 vector only; no trace or output is consulted."""

    if not math.isfinite(tolerance_seconds) or tolerance_seconds <= 0.0:
        raise Clean2CaseProviderError("Dual-yaw alignment tolerance is invalid")
    provider_times = [float(row["time"]) for row in dual_rows]
    aligned: list[AlignedGnssEpoch] = []
    for row_index, fields in enumerate(gnss_rows):
        mutable_fields = list(fields)
        time_value = float(fields[0])
        yaw_valid = fields[17].strip().casefold() in {"1", "true"}
        candidate, delta = _nearest_provider_row(dual_rows, provider_times, time_value)
        yaw_difference = abs(
            wrap_signed(float(fields[13]) - float(candidate["body_yaw_ned_deg"]))
        )
        if yaw_valid and (
            delta > tolerance_seconds + 1.0e-12 or yaw_difference > yaw_tolerance_deg
        ):
            start, end = runtime_window_seconds
            if start < time_value <= end:
                raise Clean2CaseProviderError(
                    "Yaw-valid formal-window GNSS epoch lacks matching current A1 evidence"
                )
            # 15列CLEAN1只有隐式validity；正式窗口外若缺current provider，
            # 显式置false，禁止外推或伪造baseline vector。
            mutable_fields[17] = "0"
            yaw_valid = False
        # NED provider的 down 在账本中显式转为 up；GNSS1/2原始位置列不参与修改。
        aligned.append(
            AlignedGnssEpoch(
                row_index=row_index,
                time=time_value,
                fields=tuple(mutable_fields),
                baseline_e_m=float(candidate["baseline_e_m"]) if yaw_valid else None,
                baseline_n_m=float(candidate["baseline_n_m"]) if yaw_valid else None,
                baseline_u_m=-float(candidate["baseline_d_m"]) if yaw_valid else None,
            )
        )
    return aligned


def _canonical_hash_mapping(mapping: Mapping[str, str]) -> str:
    return sha256_text(json.dumps(dict(mapping), sort_keys=True, separators=(",", ":")))


def _validate_actual_provider_files(paths: Mapping[str, str | Path]) -> tuple[dict[str, str], dict[str, str]]:
    if set(paths) != set(REQUIRED_SHARED_HASH_ROLES):
        raise Clean2CaseProviderError(
            "Actual provider paths must contain IMU, Raw Doppler, Go2 RP and Go2 HV"
        )
    resolved: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for role in REQUIRED_SHARED_HASH_ROLES:
        path = Path(paths[role]).resolve(strict=True)
        if not path.is_file():
            raise Clean2CaseProviderError(f"Fresh provider role is not a file: {role}")
        digest = sha256_file(path)
        if digest != EXPECTED_BASE_PROVIDER_HASHES[role]:
            raise Clean2CaseProviderError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
        resolved[role] = str(path)
        hashes[role] = digest
    return resolved, hashes


def _validate_raw_checkpoint_evidence(
    *, pre_path: str | Path, post_path: str | Path, raw_hash_lock_path: str | Path
) -> dict[str, Any]:
    lock_path = Path(raw_hash_lock_path).resolve(strict=True)
    if sha256_file(lock_path) != EXPECTED_RAW_LOCK_SHA256:
        raise Clean2CaseProviderError("Raw hash lock differs from the frozen CLEAN1 lock")
    lock = read_hash_lock(lock_path)
    pre_source = Path(pre_path).resolve(strict=True)
    post_source = Path(post_path).resolve(strict=True)
    pre = load_raw_checkpoint(pre_source)
    post = load_raw_checkpoint(post_source)
    pre_hashes = validate_raw_checkpoint(
        pre,
        phase=RAW_PRE_PHASE,
        lock=lock,
        expected_lock_sha256=EXPECTED_RAW_LOCK_SHA256,
    )
    post_hashes = validate_raw_checkpoint(
        post,
        phase=RAW_POST_PHASE,
        lock=lock,
        expected_lock_sha256=EXPECTED_RAW_LOCK_SHA256,
    )
    if pre_hashes != post_hashes:
        raise Clean2CaseProviderError("Raw 22/22 hashes changed during CLEAN2 case generation")
    return {
        "raw_source_hashes": pre_hashes,
        "raw_pre_checkpoint_path": str(pre_source),
        "raw_pre_checkpoint_sha256": sha256_file(pre_source),
        "raw_post_checkpoint_path": str(post_source),
        "raw_post_checkpoint_sha256": sha256_file(post_source),
        "raw_hash_lock_path": str(lock_path),
        "raw_hash_lock_sha256": sha256_file(lock_path),
        "raw_mutation_count": 0,
        "passed": True,
    }


def validate_fresh_base_provider_evidence(
    *,
    clean_input_manifest_path: str | Path,
    auxiliary_bundle_manifest_path: str | Path,
    base_dual_yaw_provider_path: str | Path,
    raw_pre_checkpoint_path: str | Path,
    raw_post_checkpoint_path: str | Path,
    raw_hash_lock_path: str | Path,
    raw_root: str | Path,
    code_root: str | Path,
    expected_code_freeze_commit: str,
) -> dict[str, Any]:
    """Bind fresh manifests, actual files, exact five hashes, raw 22/22, and Git identity."""

    commit, dirty = git_code_state(Path(code_root).resolve(strict=True))
    if dirty or commit != expected_code_freeze_commit:
        raise Clean2CaseProviderError("Provider generation requires the exact clean code freeze")
    clean_manifest_path = Path(clean_input_manifest_path).resolve(strict=True)
    clean_bundle = load_clean_bundle(clean_manifest_path)
    clean_manifest = json.loads(clean_manifest_path.read_text(encoding="utf-8"))
    auxiliary_path = Path(auxiliary_bundle_manifest_path).resolve(strict=True)
    auxiliary = validate_auxiliary_bundle(auxiliary_path)
    if (
        clean_manifest.get("generator_code_commit") != expected_code_freeze_commit
        or auxiliary.get("code_freeze_commit") != expected_code_freeze_commit
        or auxiliary.get("clean_input_manifest_sha256") != sha256_file(clean_manifest_path)
    ):
        raise Clean2CaseProviderError("Fresh provider manifests are not bound to CLEAN2 code freeze")
    actual_paths = {
        "imu": clean_bundle.imu_path,
        "raw_doppler": auxiliary["auxiliary_artifacts"]["raw_doppler_provider"]["path"],
        "go2_roll_pitch": auxiliary["auxiliary_artifacts"]["go2_attitude_prior"]["path"],
        "go2_horizontal_velocity": auxiliary["auxiliary_artifacts"]["go2_horizontal_velocity_prior"]["path"],
    }
    resolved_paths, hashes = _validate_actual_provider_files(actual_paths)
    if sha256_file(clean_bundle.gnss_path) != EXPECTED_BASE_PROVIDER_HASHES["gnss"]:
        raise Clean2CaseProviderError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
    dual_path = _validate_fresh_dual_yaw_binding(
        auxiliary,
        auxiliary_manifest_path=auxiliary_path,
        provided_dual_yaw_path=base_dual_yaw_provider_path,
        expected_code_commit=expected_code_freeze_commit,
    )
    raw = _validate_raw_checkpoint_evidence(
        pre_path=raw_pre_checkpoint_path,
        post_path=raw_post_checkpoint_path,
        raw_hash_lock_path=raw_hash_lock_path,
    )
    raw_root_path = Path(raw_root).resolve(strict=True)
    if raw_root_path.is_symlink() or not raw_root_path.is_dir():
        raise Clean2CaseProviderError("Configured raw root is missing or a symlink")
    return {
        "code_freeze_commit": expected_code_freeze_commit,
        "code_worktree_dirty": False,
        "clean_input_manifest_path": str(clean_manifest_path),
        "clean_input_manifest_sha256": sha256_file(clean_manifest_path),
        "auxiliary_bundle_manifest_path": str(auxiliary_path),
        "auxiliary_bundle_manifest_sha256": sha256_file(auxiliary_path),
        "base_gnss_path": str(clean_bundle.gnss_path),
        "base_dual_yaw_provider_path": str(dual_path),
        "base_dual_yaw_provider_sha256": sha256_file(dual_path),
        "shared_provider_paths": resolved_paths,
        "raw_root_path": str(raw_root_path),
        "provider_hashes": {**hashes, "gnss": EXPECTED_BASE_PROVIDER_HASHES["gnss"]},
        **raw,
    }


def _write_export_safe_base_provider_snapshot(
    *,
    base_provider_evidence: Mapping[str, Any],
    destination: Path,
) -> tuple[Path, Path]:
    """Write only alias/hash base evidence; original generator manifests stay local."""

    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / "CLEAN2_BASE_PROVIDER_MANIFEST.json"
    hashes_path = destination / "CLEAN2_BASE_PROVIDER_HASHES.csv"
    if manifest_path.exists() or hashes_path.exists():
        raise Clean2CaseProviderError("CLEAN2 base-provider snapshot must be fresh")
    provider_hashes = dict(base_provider_evidence["provider_hashes"])
    payload = {
        "schema_version": "paper_rebuild.clean2_base_provider_snapshot.v1",
        "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
        "code_freeze_commit": base_provider_evidence["code_freeze_commit"],
        "data_mode": "real_by2_raw",
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "trace_read_count": 0,
        "raw_mutation_count": 0,
        "provider_paths": {
            role: f"provider://fresh/{role}" for role in sorted(provider_hashes)
        },
        "provider_hashes": provider_hashes,
        "base_dual_yaw_provider": {
            "path": "provider://fresh/a1_dual_yaw",
            "sha256": base_provider_evidence["base_dual_yaw_provider_sha256"],
            "source_backed": True,
        },
        "source_manifest_hashes": {
            "clean_input": base_provider_evidence["clean_input_manifest_sha256"],
            "auxiliary_bundle": base_provider_evidence["auxiliary_bundle_manifest_sha256"],
        },
        "raw_source_hashes": dict(base_provider_evidence["raw_source_hashes"]),
        "raw_pre_checkpoint_sha256": base_provider_evidence["raw_pre_checkpoint_sha256"],
        "raw_post_checkpoint_sha256": base_provider_evidence["raw_post_checkpoint_sha256"],
        "raw_hash_lock_sha256": base_provider_evidence["raw_hash_lock_sha256"],
        "base_provider_hash_parity": provider_hashes == EXPECTED_BASE_PROVIDER_HASHES,
        "terminal_status": "PASS",
    }
    if not payload["base_provider_hash_parity"]:
        raise Clean2CaseProviderError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
    write_json_atomic(manifest_path, payload)
    rows = [
        {"artifact_role": role, "sha256": digest}
        for role, digest in sorted(provider_hashes.items())
    ] + [
        {
            "artifact_role": "base_dual_yaw_provider",
            "sha256": base_provider_evidence["base_dual_yaw_provider_sha256"],
        },
        {"artifact_role": "clean_input_manifest", "sha256": base_provider_evidence["clean_input_manifest_sha256"]},
        {"artifact_role": "auxiliary_bundle_manifest", "sha256": base_provider_evidence["auxiliary_bundle_manifest_sha256"]},
        {"artifact_role": "clean2_base_provider_manifest", "sha256": sha256_file(manifest_path)},
    ]
    write_csv_atomic(hashes_path, ["artifact_role", "sha256"], rows)
    return manifest_path, hashes_path


def _required_regular_file(raw: Any, *, label: str) -> Path:
    value = str(raw or "")
    if not value:
        raise Clean2CaseProviderError(f"{label} path is missing")
    candidate = Path(value)
    if candidate.is_symlink():
        raise Clean2CaseProviderError(f"{label} path is a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise Clean2CaseProviderError(f"{label} path is missing") from exc
    if not resolved.is_file():
        raise Clean2CaseProviderError(f"{label} is not a regular file")
    return resolved


def _validate_terminal_base_provider_evidence(
    base: Mapping[str, Any], *, expected_code_commit: str
) -> dict[str, Any]:
    """Rehash the five frozen providers and the sanitized exact hash maps."""

    provider_hashes = base.get("provider_hashes")
    if not isinstance(provider_hashes, Mapping) or dict(provider_hashes) != EXPECTED_BASE_PROVIDER_HASHES:
        raise Clean2CaseProviderError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
    raw_source_hashes = base.get("raw_source_hashes")
    if (
        not isinstance(raw_source_hashes, Mapping)
        or len(raw_source_hashes) != 22
        or any(not _is_sha256(value) for value in raw_source_hashes.values())
    ):
        raise Clean2CaseProviderError("Classic-18 base raw 22 hash map is incomplete")
    for field in (
        "clean_input_manifest_sha256", "auxiliary_bundle_manifest_sha256",
        "base_dual_yaw_provider_sha256", "raw_pre_checkpoint_sha256",
        "raw_post_checkpoint_sha256", "raw_hash_lock_sha256",
    ):
        if not _is_sha256(base.get(field)):
            raise Clean2CaseProviderError(f"Classic-18 base evidence hash is invalid: {field}")
    shared_paths = base.get("shared_provider_paths")
    if not isinstance(shared_paths, Mapping) or set(shared_paths) != set(REQUIRED_SHARED_HASH_ROLES):
        raise Clean2CaseProviderError("Classic-18 base provider paths are incomplete")
    actual_paths: dict[str, Path] = {}
    for role in REQUIRED_SHARED_HASH_ROLES:
        actual = _required_regular_file(shared_paths[role], label=f"fresh {role}")
        if sha256_file(actual) != EXPECTED_BASE_PROVIDER_HASHES[role]:
            raise Clean2CaseProviderError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
        actual_paths[role] = actual
    base_gnss = _required_regular_file(base.get("base_gnss_path"), label="fresh gnss")
    if sha256_file(base_gnss) != EXPECTED_BASE_PROVIDER_HASHES["gnss"]:
        raise Clean2CaseProviderError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
    base_dual = _required_regular_file(
        base.get("base_dual_yaw_provider_path"), label="fresh A1 dual-yaw provider"
    )
    if sha256_file(base_dual) != base.get("base_dual_yaw_provider_sha256"):
        raise Clean2CaseProviderError("Fresh A1 dual-yaw provider hash changed")

    manifest_path = _required_regular_file(
        base.get("export_safe_base_manifest_path"), label="sanitized base-provider manifest"
    )
    hashes_path = _required_regular_file(
        base.get("export_safe_base_hashes_path"), label="sanitized base-provider hash table"
    )
    if (
        sha256_file(manifest_path) != base.get("export_safe_base_manifest_sha256")
        or sha256_file(hashes_path) != base.get("export_safe_base_hashes_sha256")
    ):
        raise Clean2CaseProviderError("Export-safe base-provider snapshot changed")
    sanitized = json.loads(manifest_path.read_text(encoding="utf-8"))
    exact_manifest_fields = {
        "schema_version", "stage_id", "code_freeze_commit", "data_mode",
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "trace_read_count", "raw_mutation_count", "provider_paths", "provider_hashes",
        "base_dual_yaw_provider", "source_manifest_hashes", "raw_source_hashes",
        "raw_pre_checkpoint_sha256", "raw_post_checkpoint_sha256",
        "raw_hash_lock_sha256", "base_provider_hash_parity", "terminal_status",
    }
    expected_aliases = {
        role: f"provider://fresh/{role}" for role in sorted(EXPECTED_BASE_PROVIDER_HASHES)
    }
    expected_source_hashes = {
        "clean_input": base.get("clean_input_manifest_sha256"),
        "auxiliary_bundle": base.get("auxiliary_bundle_manifest_sha256"),
    }
    expected_dual = {
        "path": "provider://fresh/a1_dual_yaw",
        "sha256": base.get("base_dual_yaw_provider_sha256"),
        "source_backed": True,
    }
    if (
        not isinstance(sanitized, Mapping)
        or set(sanitized) != exact_manifest_fields
        or sanitized.get("schema_version") != "paper_rebuild.clean2_base_provider_snapshot.v1"
        or sanitized.get("stage_id") != "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
        or sanitized.get("code_freeze_commit") != expected_code_commit
        or sanitized.get("data_mode") != "real_by2_raw"
        or sanitized.get("synthetic_data_used") is not False
        or sanitized.get("semisynthetic_data_used") is not False
        or sanitized.get("trace_used_online") is not False
        or sanitized.get("trace_read_count") != 0
        or sanitized.get("raw_mutation_count") != 0
        or sanitized.get("provider_paths") != expected_aliases
        or sanitized.get("provider_hashes") != EXPECTED_BASE_PROVIDER_HASHES
        or sanitized.get("base_dual_yaw_provider") != expected_dual
        or sanitized.get("source_manifest_hashes") != expected_source_hashes
        or sanitized.get("raw_source_hashes") != base.get("raw_source_hashes")
        or sanitized.get("raw_pre_checkpoint_sha256") != base.get("raw_pre_checkpoint_sha256")
        or sanitized.get("raw_post_checkpoint_sha256") != base.get("raw_post_checkpoint_sha256")
        or sanitized.get("raw_hash_lock_sha256") != base.get("raw_hash_lock_sha256")
        or sanitized.get("base_provider_hash_parity") is not True
        or sanitized.get("terminal_status") != "PASS"
    ):
        raise Clean2CaseProviderError("Sanitized base-provider manifest is inconsistent")

    with hashes_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ("artifact_role", "sha256"):
            raise Clean2CaseProviderError("Sanitized base-provider hash table columns drifted")
        hash_rows = list(reader)
    declared = {
        str(row.get("artifact_role") or ""): str(row.get("sha256") or "")
        for row in hash_rows
    }
    expected_declared = {
        **EXPECTED_BASE_PROVIDER_HASHES,
        "base_dual_yaw_provider": str(base.get("base_dual_yaw_provider_sha256")),
        "clean_input_manifest": str(base.get("clean_input_manifest_sha256")),
        "auxiliary_bundle_manifest": str(base.get("auxiliary_bundle_manifest_sha256")),
        "clean2_base_provider_manifest": sha256_file(manifest_path),
    }
    if len(declared) != len(hash_rows) or declared != expected_declared:
        raise Clean2CaseProviderError("Sanitized base-provider hash map is inconsistent")
    return {
        "provider_hashes": dict(provider_hashes),
        "shared_provider_paths": {role: str(path) for role, path in actual_paths.items()},
        "base_gnss_path": str(base_gnss),
        "base_dual_yaw_provider_path": str(base_dual),
        "sanitized_manifest_sha256": sha256_file(manifest_path),
        "sanitized_hashes_sha256": sha256_file(hashes_path),
    }


def _validate_fresh_dual_yaw_binding(
    auxiliary: Mapping[str, Any],
    *,
    auxiliary_manifest_path: str | Path,
    provided_dual_yaw_path: str | Path,
    expected_code_commit: str,
) -> Path:
    """Resolve A1 dual-yaw only through the fresh helper manifest/hash chain."""

    auxiliary_path = Path(auxiliary_manifest_path).resolve(strict=True)
    binding = auxiliary.get("classic18_dual_yaw_provider")
    if not isinstance(binding, Mapping):
        raise Clean2CaseProviderError("Fresh auxiliary manifest lacks Classic-18 dual-yaw binding")
    helper_path = Path(str(binding.get("helper_manifest_path") or "")).resolve(strict=True)
    if (
        helper_path.parent != auxiliary_path.parent
        or sha256_file(helper_path) != binding.get("helper_manifest_sha256")
    ):
        raise Clean2CaseProviderError("Fresh helper manifest identity/hash mismatch")
    helper = json.loads(helper_path.read_text(encoding="utf-8"))
    if (
        helper.get("schema_version") != "paper-rebuild-clean1-input-v1"
        or helper.get("stage_id") != "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION"
        or helper.get("protocol_id") != "CLEAN1_BY2_CLEAN_NORMAL_V1"
        or helper.get("generator_code_commit") != expected_code_commit
        or helper.get("generator_worktree_dirty") is not False
        or helper.get("data_mode") != "real_by2_raw"
        or helper.get("synthetic_data_used") is not False
        or helper.get("semisynthetic_data_used") is not False
        or helper.get("trace_used_online") is not False
        or helper.get("raw_source_hashes") != auxiliary.get("raw_source_hashes")
        or helper.get("generator_config_hash") != binding.get("generator_config_hash")
        or helper.get("provider_bundle_hash") != binding.get("helper_provider_bundle_hash")
    ):
        raise Clean2CaseProviderError("Fresh helper dual-yaw lineage mismatch")
    artifacts = helper.get("artifacts")
    provider_hashes = helper.get("provider_hashes")
    if not isinstance(artifacts, Mapping) or not isinstance(provider_hashes, Mapping):
        raise Clean2CaseProviderError("Fresh helper provider map is missing")
    entry = artifacts.get("dual_yaw_provider")
    if not isinstance(entry, Mapping):
        raise Clean2CaseProviderError("Fresh helper dual-yaw artifact is missing")
    relative = entry.get("relative_path")
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise Clean2CaseProviderError("Fresh helper dual-yaw path is unsafe")
    helper_source = (helper_path.parent / relative).resolve(strict=True)
    provided = Path(provided_dual_yaw_path).resolve(strict=True)
    expected_hash = provider_hashes.get("dual_yaw_provider")
    time_audit = binding.get("time_basis_audit")
    if (
        str(helper_source) != binding.get("helper_source_path")
        or expected_hash != binding.get("helper_source_sha256")
        or sha256_file(helper_source) != expected_hash
        or str(provided) != binding.get("path")
        or sha256_file(provided) != binding.get("sha256")
        or entry.get("solver_input") is not False
        or entry.get("artifact_role") != "audit_only_lineage"
        or not isinstance(time_audit, Mapping)
        or time_audit.get("passed") is not True
        or time_audit.get("source_path") != str(helper_source)
        or time_audit.get("active_path") != str(provided)
        or time_audit.get("time_column_only_transformed") is not True
        or time_audit.get("source_time_column_preserved") is not True
        or float(time_audit.get("offset_subtracted_seconds", math.nan)) != 28800.0
    ):
        raise Clean2CaseProviderError("Current A1 dual-yaw provider differs from fresh helper binding")
    return provided


def _source_isolation_audit(
    base_rows: Sequence[tuple[str, ...]], output_rows: Sequence[tuple[str, ...]]
) -> dict[str, Any]:
    if len(base_rows) != len(output_rows):
        raise Clean2CaseProviderError("Classic case deleted or added a GNSS epoch")
    position_equal = all(
        left[0:7] == right[0:7] and left[15] == right[15]
        for left, right in zip(base_rows, output_rows)
    )
    velocity_equal = all(
        left[7:13] == right[7:13] and left[16] == right[16]
        for left, right in zip(base_rows, output_rows)
    )
    if not position_equal or not velocity_equal:
        raise Clean2CaseProviderError("FAIL_CLEAN2_POSITION_VELOCITY_SOURCE_ISOLATION")
    return {
        "row_count_equal": True,
        "time_and_position_columns_bit_identical": position_equal,
        "receiver_velocity_columns_bit_identical": velocity_equal,
        "allowed_changed_zero_based_columns": [13, 14, 17],
        "passed": True,
    }


def materialize_case_bundle(
    application: ClassicCaseApplication,
    *,
    base_gnss_path: str | Path,
    base_dual_yaw_provider_path: str | Path,
    base_rows: Sequence[tuple[str, ...]],
    base_payload: bytes,
    base_extension_audit: Mapping[str, Any],
    destination: str | Path,
    mapping_catalog: ClassicCaseCatalog,
    base_provider_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Write one fresh case directory and close every non-yaw isolation hash."""

    shared = dict(base_provider_evidence["provider_hashes"])
    shared_paths = dict(base_provider_evidence["shared_provider_paths"])
    # CASE manifest/policy enter the final review ZIP. Keep real local paths
    # only in the non-exported provider index and RUN_BINDINGS; exported case
    # evidence records stable aliases plus the same content hashes.
    shared_path_aliases = {
        role: f"provider://fresh/{role}" for role in sorted(shared_paths)
    }
    if set(shared) != {"imu", "gnss", "raw_doppler", "go2_roll_pitch", "go2_horizontal_velocity"}:
        raise Clean2CaseProviderError("Fresh base provider evidence is incomplete")
    output_root = Path(destination).resolve(strict=False)
    if output_root.exists():
        raise Clean2CaseProviderError("Fresh Classic case destination already exists")
    output_root.mkdir(parents=True, exist_ok=False)
    gnss_path = output_root / "CASE_GNSS_INPUT.extended"
    output_rows = list(application.output_fields)
    isolation = _source_isolation_audit(base_rows, output_rows)
    if application.case.case_code == "C00":
        # C00直接复用原始字节，保证扩展格式与冻结clean输入逐字节一致。
        gnss_path.write_bytes(base_payload)
    else:
        gnss_path.write_text(
            "\n".join(" ".join(fields) for fields in output_rows) + "\n",
            encoding="utf-8",
        )
    dual_path = write_csv_atomic(
        output_root / "CASE_DUAL_YAW_PROVIDER.csv",
        list(PROVIDER_FIELDS),
        list(application.provider_rows),
    )
    ledger_path = write_csv_atomic(
        output_root / "CASE_PERTURBATION_LEDGER.csv",
        list(LEDGER_FIELDS),
        list(application.ledger_rows),
    )
    policy_payload = {
        **application.policy_report,
        "source_isolation": isolation,
        "base_gnss_sha256": sha256_file(base_gnss_path),
        "base_dual_yaw_provider_sha256": sha256_file(base_dual_yaw_provider_path),
        "shared_provider_hashes": shared,
        "shared_provider_paths": shared_path_aliases,
        "shared_provider_hashes_unchanged": True,
        "raw_pre_checkpoint_sha256": base_provider_evidence["raw_pre_checkpoint_sha256"],
        "raw_post_checkpoint_sha256": base_provider_evidence["raw_post_checkpoint_sha256"],
        "raw_hash_lock_sha256": base_provider_evidence["raw_hash_lock_sha256"],
        "raw_mutation_count": 0,
        "trace_read_count": 0,
    }
    policy_path = write_json_atomic(output_root / "CASE_POLICY_REPORT.json", policy_payload)
    output_hashes = {
        "case_gnss_input": sha256_file(gnss_path),
        "case_dual_yaw_provider": sha256_file(dual_path),
        "case_perturbation_ledger": sha256_file(ledger_path),
        "case_policy_report": sha256_file(policy_path),
        **{f"shared_{key}": value for key, value in shared.items()},
    }
    bundle_hash = _canonical_hash_mapping(output_hashes)
    clean = application.case.case_code == "C00"
    manifest = {
        "schema_version": "paper_rebuild.clean2_case_provider_manifest.v1",
        "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
        "case_id": application.case.case_id,
        "case_code": application.case.case_code,
        "family": application.case.family,
        "display_label": application.case.display_label,
        "provider_std_scale": application.case.provider_std_scale,
        "operations": [dict(operation) for operation in application.case.operations],
        "data_mode": "real_by2_raw" if clean else "real_base_controlled_degradation",
        "result_namespace": (
            "BY2_REAL_CLEAN_MODULE_ABLATION"
            if clean
            else "BY2_CONTROLLED_DUAL_YAW_DEGRADATION"
        ),
        "synthetic_data_used": False,
        "semisynthetic_data_used": not clean,
        "trace_used_online": False,
        "trace_read_count": 0,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "legacy_provider_payload_used": False,
        "legacy_performance_evidence_used": False,
        "active_provider_layer": "A1_dual_diff_status_baseline_vector",
        "mapping_config_sha256": mapping_catalog.source_sha256,
        "source_spec_sha256": mapping_catalog.source_spec_sha256,
        "code_freeze_commit": base_provider_evidence["code_freeze_commit"],
        "code_worktree_dirty": False,
        "clean_input_manifest_sha256": base_provider_evidence["clean_input_manifest_sha256"],
        "auxiliary_bundle_manifest_sha256": base_provider_evidence["auxiliary_bundle_manifest_sha256"],
        "base_gnss_sha256": sha256_file(base_gnss_path),
        "base_dual_yaw_provider_sha256": sha256_file(base_dual_yaw_provider_path),
        "shared_provider_hashes": shared,
        "shared_provider_paths": shared_path_aliases,
        "raw_source_hashes": dict(base_provider_evidence["raw_source_hashes"]),
        "output_hashes": output_hashes,
        "provider_bundle_hash": bundle_hash,
        "source_isolation": isolation,
        "raw_pre_checkpoint_sha256": base_provider_evidence["raw_pre_checkpoint_sha256"],
        "raw_post_checkpoint_sha256": base_provider_evidence["raw_post_checkpoint_sha256"],
        "raw_hash_lock_sha256": base_provider_evidence["raw_hash_lock_sha256"],
        "raw_mutation_count": 0,
        "base_gnss_extension_audit": dict(base_extension_audit),
        "c00_extended_payload_exact": clean and gnss_path.read_bytes() == base_payload,
        "c00_first15_token_parity": clean and base_extension_audit.get("first15_token_parity") is True,
        "c00_first15_numerical_parity": clean and base_extension_audit.get("first15_numerical_parity") is True,
        "terminal_status": "PASS",
    }
    manifest_path = write_json_atomic(output_root / "CASE_PROVIDER_MANIFEST.json", manifest)
    hash_rows = [
        {"artifact_role": role, "sha256": digest}
        for role, digest in {**output_hashes, "case_provider_manifest": sha256_file(manifest_path)}.items()
    ]
    hashes_path = write_csv_atomic(
        output_root / "CASE_PROVIDER_HASHES.csv",
        ["artifact_role", "sha256"],
        hash_rows,
    )
    return {
        "case_id": application.case.case_id,
        "case_code": application.case.case_code,
        "provider_bundle_hash": bundle_hash,
        "manifest_sha256": sha256_file(manifest_path),
        "manifest_path": str(manifest_path),
        "hashes_path": str(hashes_path),
        "gnss_path": str(gnss_path),
        "gnss_sha256": sha256_file(gnss_path),
        "dual_yaw_path": str(dual_path),
        "dual_yaw_sha256": sha256_file(dual_path),
        "shared_provider_paths": shared_paths,
        "shared_provider_hashes": shared,
        "terminal_status": "PASS",
    }


def validate_case_provider_index(
    path: str | Path,
    *,
    expected_code_commit: str | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Rehash every case payload/ledger/policy/hash row and recompute bundle identity."""

    source = Path(path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != "paper_rebuild.clean2_case_provider_index.v1"
        or payload.get("stage_id") != "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
        or payload.get("case_count") != 18
        or payload.get("all_terminal_pass") is not True
        or payload.get("trace_read_count") != 0
        or payload.get("raw_mutation_count") != 0
        or payload.get("code_worktree_dirty") is not False
        or (
            expected_code_commit is not None
            and payload.get("code_freeze_commit") != expected_code_commit
        )
    ):
        raise Clean2CaseProviderError("Classic-18 case provider index identity is incomplete")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 18:
        raise Clean2CaseProviderError("Classic-18 case provider index lacks 18 rows")
    base = payload.get("base_provider_evidence")
    if not isinstance(base, Mapping):
        raise Clean2CaseProviderError("Classic-18 index lacks base-provider evidence")
    frozen_commit = str(expected_code_commit or payload.get("code_freeze_commit") or "")
    if len(frozen_commit) != 40:
        raise Clean2CaseProviderError("Classic-18 index lacks the frozen code commit")
    terminal_base = _validate_terminal_base_provider_evidence(
        base, expected_code_commit=frozen_commit
    )
    base_rows, _, _ = _read_base_gnss(Path(terminal_base["base_gnss_path"]))
    by_id: dict[str, dict[str, Any]] = {}
    rows_by_id: dict[str, list[tuple[str, ...]]] = {}
    manifests_by_id: dict[str, dict[str, Any]] = {}
    policies_by_id: dict[str, dict[str, Any]] = {}
    expected_codes = {f"C{index:02d}" for index in range(18)}
    for row in cases:
        if not isinstance(row, Mapping):
            raise Clean2CaseProviderError("Classic-18 index row is malformed")
        case_id = str(row.get("case_id") or "")
        case_code = str(row.get("case_code") or "")
        manifest_path = Path(str(row.get("manifest_path") or "")).resolve(strict=True)
        case_root = manifest_path.parent
        if (
            not case_id.startswith(case_code + "_")
            or case_code not in expected_codes
            or case_id in by_id
            or case_root.parent != source.parent
            or case_root.name != case_id
            or manifest_path.name != "CASE_PROVIDER_MANIFEST.json"
        ):
            raise Clean2CaseProviderError("Classic-18 case directory/index identity mismatch")
        manifest_hash = sha256_file(manifest_path)
        if manifest_hash != row.get("manifest_sha256"):
            raise Clean2CaseProviderError("Classic-18 case manifest changed after generation")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("case_id") != case_id
            or manifest.get("case_code") != case_code
            or manifest.get("terminal_status") != "PASS"
            or manifest.get("trace_read_count") != 0
            or manifest.get("raw_mutation_count") != 0
            or (
                expected_code_commit is not None
                and manifest.get("code_freeze_commit") != expected_code_commit
            )
        ):
            raise Clean2CaseProviderError("Classic-18 case manifest identity mismatch")
        files = {
            "case_gnss_input": case_root / "CASE_GNSS_INPUT.extended",
            "case_dual_yaw_provider": case_root / "CASE_DUAL_YAW_PROVIDER.csv",
            "case_perturbation_ledger": case_root / "CASE_PERTURBATION_LEDGER.csv",
            "case_policy_report": case_root / "CASE_POLICY_REPORT.json",
        }
        if any(file.is_symlink() or not file.is_file() for file in files.values()):
            raise Clean2CaseProviderError("Classic-18 case payload is missing or a symlink")
        shared = manifest.get("shared_provider_hashes")
        expected_aliases = {
            role: f"provider://fresh/{role}" for role in sorted(REQUIRED_SHARED_HASH_ROLES)
        }
        if (
            not isinstance(shared, Mapping)
            or dict(shared) != EXPECTED_BASE_PROVIDER_HASHES
            or manifest.get("shared_provider_paths") != expected_aliases
            or manifest.get("base_gnss_sha256") != EXPECTED_BASE_PROVIDER_HASHES["gnss"]
            or manifest.get("clean_input_manifest_sha256")
            != base.get("clean_input_manifest_sha256")
            or manifest.get("auxiliary_bundle_manifest_sha256")
            != base.get("auxiliary_bundle_manifest_sha256")
            or manifest.get("raw_source_hashes") != base.get("raw_source_hashes")
            or row.get("shared_provider_hashes") != EXPECTED_BASE_PROVIDER_HASHES
            or row.get("shared_provider_paths") != terminal_base["shared_provider_paths"]
        ):
            raise Clean2CaseProviderError("Classic-18 shared provider binding is incomplete")
        expected_outputs = {
            **{role: sha256_file(file) for role, file in files.items()},
            **{f"shared_{role}": str(digest) for role, digest in shared.items()},
        }
        if manifest.get("output_hashes") != expected_outputs:
            raise Clean2CaseProviderError("Classic-18 case output/ledger/policy hash changed")
        bundle_hash = _canonical_hash_mapping(expected_outputs)
        if (
            manifest.get("provider_bundle_hash") != bundle_hash
            or row.get("provider_bundle_hash") != bundle_hash
            or Path(str(row.get("gnss_path") or "")).resolve(strict=True) != files["case_gnss_input"]
            or row.get("gnss_sha256") != expected_outputs["case_gnss_input"]
            or Path(str(row.get("dual_yaw_path") or "")).resolve(strict=True) != files["case_dual_yaw_provider"]
            or row.get("dual_yaw_sha256") != expected_outputs["case_dual_yaw_provider"]
        ):
            raise Clean2CaseProviderError("Classic-18 provider bundle/index hash mismatch")
        hashes_path = Path(str(row.get("hashes_path") or "")).resolve(strict=True)
        if hashes_path != case_root / "CASE_PROVIDER_HASHES.csv":
            raise Clean2CaseProviderError("Classic-18 case hash table path mismatch")
        with hashes_path.open("r", encoding="utf-8-sig", newline="") as handle:
            hash_rows = list(csv.DictReader(handle))
        declared = {
            str(item.get("artifact_role") or ""): str(item.get("sha256") or "")
            for item in hash_rows
        }
        expected_declared = {
            **expected_outputs,
            "case_provider_manifest": manifest_hash,
        }
        if len(declared) != len(hash_rows) or declared != expected_declared:
            raise Clean2CaseProviderError("Classic-18 CASE_PROVIDER_HASHES.csv is inconsistent")
        policy = json.loads(files["case_policy_report"].read_text(encoding="utf-8"))
        if (
            not isinstance(policy, Mapping)
            or policy.get("shared_provider_hashes") != EXPECTED_BASE_PROVIDER_HASHES
            or policy.get("shared_provider_paths") != expected_aliases
            or policy.get("shared_provider_hashes_unchanged") is not True
            or policy.get("raw_mutation_count") != 0
            or policy.get("trace_read_count") != 0
        ):
            raise Clean2CaseProviderError("Classic-18 case policy provider binding drifted")
        case_rows, _, _ = _read_base_gnss(files["case_gnss_input"])
        by_id[case_id] = dict(row)
        rows_by_id[case_id] = case_rows
        manifests_by_id[case_id] = dict(manifest)
        policies_by_id[case_id] = dict(policy)
    if {str(row["case_code"]) for row in by_id.values()} != expected_codes:
        raise Clean2CaseProviderError("Classic-18 case codes are incomplete")
    c00_ids = [case_id for case_id in rows_by_id if case_id.startswith("C00_")]
    if len(c00_ids) != 1:
        raise Clean2CaseProviderError("Classic-18 case index lacks one C00 provider")
    c00_rows = rows_by_id[c00_ids[0]]
    if len(base_rows) != len(c00_rows) or any(
        left[:13] != right[:13] or left[15:17] != right[15:17]
        for left, right in zip(base_rows, c00_rows)
    ):
        raise Clean2CaseProviderError("FAIL_CLEAN2_POSITION_VELOCITY_SOURCE_ISOLATION")
    for case_id, case_rows in rows_by_id.items():
        recomputed_isolation = _source_isolation_audit(c00_rows, case_rows)
        if (
            manifests_by_id[case_id].get("source_isolation") != recomputed_isolation
            or policies_by_id[case_id].get("source_isolation") != recomputed_isolation
        ):
            raise Clean2CaseProviderError("Classic-18 source-isolation evidence is stale")
    payload["index_path"] = str(source)
    payload["index_sha256"] = sha256_file(source)
    return payload, by_id


def generate_classic18_case_bundles(
    *,
    mapping_config: str | Path,
    clean_input_manifest_path: str | Path,
    auxiliary_bundle_manifest_path: str | Path,
    base_dual_yaw_provider_path: str | Path,
    output_root: str | Path,
    raw_pre_checkpoint_path: str | Path,
    raw_post_checkpoint_path: str | Path,
    raw_hash_lock_path: str | Path,
    local_config_path: str | Path,
    code_root: str | Path,
    expected_code_freeze_commit: str,
    dual_yaw_match_tolerance_seconds: float = 0.6,
) -> list[dict[str, Any]]:
    """Generate all 18 fresh bundles; partial pre-existing roots are rejected."""

    if not math.isclose(
        dual_yaw_match_tolerance_seconds, 0.6, rel_tol=0.0, abs_tol=1.0e-15
    ):
        raise Clean2CaseProviderError("Classic-18 dual-yaw match tolerance is frozen at 0.6 s")
    stage_paths = load_clean2_stage_paths(local_config_path)
    guarded_output = guard_clean2_stage_path(
        stage_paths,
        output_root,
        slot="case_providers",
        role="CLEAN2 Classic-18 provider root",
    )
    if guarded_output != stage_paths.slot("case_providers"):
        raise Clean2CaseProviderError("Classic-18 providers must use exact CLEAN2 stage slot 05")
    if Path(code_root).resolve(strict=True) != stage_paths.clean.code_root:
        raise Clean2CaseProviderError("CLEAN2 provider code root differs from ignored local config")
    expected_mapping = (
        stage_paths.clean.code_root
        / "configs/paper_rebuild/clean2_classic18_active_mapping.yaml"
    ).resolve(strict=True)
    if Path(mapping_config).resolve(strict=True) != expected_mapping:
        raise Clean2CaseProviderError("Classic-18 formal mapping must be the tracked CLEAN2 config")
    if Path(raw_hash_lock_path).resolve(strict=True) != stage_paths.clean.raw_hash_lock.resolve(strict=True):
        raise Clean2CaseProviderError("CLEAN2 raw hash lock differs from ignored local config")
    for source, role in (
        (clean_input_manifest_path, "clean input manifest"),
        (auxiliary_bundle_manifest_path, "auxiliary bundle manifest"),
        (base_dual_yaw_provider_path, "A1 dual-yaw provider"),
    ):
        resolved = Path(source).resolve(strict=True)
        provider_parent = (stage_paths.clean.clean_root / "04_PROVIDER_FREEZE").resolve(strict=True)
        if not is_within(resolved, provider_parent):
            raise Clean2CaseProviderError(f"Fresh {role} escaped CLEAN_ROOT/04_PROVIDER_FREEZE")
    for checkpoint in (raw_pre_checkpoint_path, raw_post_checkpoint_path):
        guard_clean2_stage_path(
            stage_paths,
            checkpoint,
            slot="raw_audits",
            role="CLEAN2 raw checkpoint",
            must_exist=True,
            regular_file=True,
        )
    catalog = load_classic_case_catalog(mapping_config)
    evidence = validate_fresh_base_provider_evidence(
        clean_input_manifest_path=clean_input_manifest_path,
        auxiliary_bundle_manifest_path=auxiliary_bundle_manifest_path,
        base_dual_yaw_provider_path=base_dual_yaw_provider_path,
        raw_pre_checkpoint_path=raw_pre_checkpoint_path,
        raw_post_checkpoint_path=raw_post_checkpoint_path,
        raw_hash_lock_path=raw_hash_lock_path,
        raw_root=stage_paths.clean.raw_root,
        code_root=code_root,
        expected_code_freeze_commit=expected_code_freeze_commit,
    )
    base_gnss = Path(evidence["base_gnss_path"]).resolve(strict=True)
    base_dual = Path(evidence["base_dual_yaw_provider_path"]).resolve(strict=True)
    base_rows, base_payload, extension_audit = _read_base_gnss(base_gnss)
    if sha256_file(base_gnss) != EXPECTED_BASE_PROVIDER_HASHES["gnss"]:
        raise Clean2CaseProviderError("BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED")
    dual_rows = _read_dual_provider(base_dual)
    epochs = align_gnss_with_dual_provider(
        base_rows,
        dual_rows,
        tolerance_seconds=dual_yaw_match_tolerance_seconds,
    )
    canonical_rows = tuple(epoch.fields for epoch in epochs)
    validity_exception_count = sum(
        before[17] != after[17] for before, after in zip(base_rows, canonical_rows)
    )
    if any(
        before[17] != after[17] and 66.0 < float(before[0]) <= 340.0
        for before, after in zip(base_rows, canonical_rows)
    ):
        raise Clean2CaseProviderError("Formal-window current-provider validity changed")
    base_rows = canonical_rows
    base_payload = (
        "\n".join(" ".join(fields) for fields in base_rows) + "\n"
    ).encode("utf-8")
    extension_audit = {
        **extension_audit,
        "outside_runtime_yaw_validity_exception_count": validity_exception_count,
        "formal_window_yaw_validity_exception_count": 0,
        "current_provider_fail_closed_outside_runtime_window": True,
    }
    base_snapshot, base_hashes = _write_export_safe_base_provider_snapshot(
        base_provider_evidence=evidence,
        destination=stage_paths.slot("base_provider"),
    )
    evidence = {
        **evidence,
        "export_safe_base_manifest_path": str(base_snapshot),
        "export_safe_base_manifest_sha256": sha256_file(base_snapshot),
        "export_safe_base_hashes_path": str(base_hashes),
        "export_safe_base_hashes_sha256": sha256_file(base_hashes),
    }
    root = guarded_output
    if root.exists():
        raise Clean2CaseProviderError("Fresh Classic-18 provider root already exists")
    root.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    for case in catalog.cases:
        application = apply_classic_case(epochs, case)
        results.append(
            materialize_case_bundle(
                application,
                base_gnss_path=base_gnss,
                base_dual_yaw_provider_path=base_dual,
                base_rows=base_rows,
                base_payload=base_payload,
                base_extension_audit=extension_audit,
                destination=root / case.case_id,
                mapping_catalog=catalog,
                base_provider_evidence=evidence,
            )
        )
    index_payload = {
        "schema_version": "paper_rebuild.clean2_case_provider_index.v1",
        "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
        "case_count": len(results),
        "cases": results,
        "trace_read_count": 0,
        "raw_mutation_count": 0,
        "code_freeze_commit": expected_code_freeze_commit,
        "code_worktree_dirty": False,
        "base_provider_evidence": evidence,
        "base_gnss_extension_audit": extension_audit,
        "all_terminal_pass": all(row["terminal_status"] == "PASS" for row in results),
    }
    index_path = write_json_atomic(root / "CLASSIC18_PROVIDER_INDEX.json", index_payload)
    validate_case_provider_index(
        index_path,
        expected_code_commit=expected_code_freeze_commit,
    )
    return results
