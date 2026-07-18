"""CLEAN2R2A clean-only 18-run formal execution and output sealing."""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .clean1r2r1_formal import (
    _solver_extra_config,
    module_counters,
    validate_auxiliary_bundle,
)
from .evidence import BY2_TRACE_RELATIVE_PATH, parse_strace_openat_paths
from .final_v23_clean_parity import active_runtime_config, load_clean_bundle
from .manifest import git_code_state, sha256_file, write_json_atomic
from .paths import is_within, legacy_reason, load_yaml_mapping
from .subprocess_guard import run_process_group


STAGE_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
PROTOCOL_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
DATA_MODE = "real_clean"
AB_IDS = tuple(f"AB{value:04b}" for value in range(16))
METHOD_ORDER = ("single_antenna_EKF", "basic_dual_yaw_EKF", *AB_IDS)
STRUCTURAL_ORDER = ("single_antenna_EKF", "basic_dual_yaw_EKF", "AB0000", "AB1111")
OUTPUT_ROLES = (
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "RUN_MANIFEST.json",
    "PORT_GNSS_UPDATE_TRACE.csv",
    "CLEAN2R2A_FORMAL_RUN_MANIFEST.json",
    "CLEAN2R2A_RUNTIME_CONFIG.yaml",
)
EXPECTED_PROVIDER_HASHES = {
    "imu": "a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b",
    "gnss": "f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22",
    "raw_doppler": "a40b9933295f6c2c989884d67cc674313f2fe03113c8acdf1d02ddf28734d722",
    "go2_roll_pitch": "2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a",
    "go2_horizontal_velocity": "f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0",
}
FORMAL_SCHEMA_NAME = "clean2r2a_formal_manifest_schema.yaml"
CANONICAL_PROVIDER_PROTOCOL_RELATIVE = Path("configs/paper_rebuild/clean1_by2_clean_protocol.yaml")
CANONICAL_PROVIDER_PROTOCOL_SHA256 = "fc3cea6a84cbb535be7fba705cc5001981022538f85f9d8d8ddcb74a23c08afd"
TECHNICAL_FAILURE_CLASSES = {
    "process_crash_signal", "io_transient", "resource_exhaustion", "lost_pty",
}


class Clean2R2ARunError(RuntimeError):
    """CLEAN2R2A formal execution failed closed."""


def validate_canonical_provider_protocol(repo_root: str | Path, candidate: str | Path) -> Path:
    """Bind provider thresholds/std/tolerances to the tracked code-freeze protocol."""

    repo = Path(repo_root).resolve(strict=True)
    canonical = (repo / CANONICAL_PROVIDER_PROTOCOL_RELATIVE).resolve(strict=True)
    selected = Path(candidate).expanduser().resolve(strict=True)
    if (
        selected != canonical
        or selected.is_symlink()
        or sha256_file(selected) != CANONICAL_PROVIDER_PROTOCOL_SHA256
    ):
        raise Clean2R2ARunError("provider protocol is not the canonical tracked code-freeze file")
    return selected


def method_features(method_id: str) -> dict[str, bool]:
    """Return the six solver flags; AB bit order is RD, SA, RP, HV."""

    if method_id == "single_antenna_EKF":
        return {"dual": False, "receiver": True, "raw": False, "source_aware": False,
                "go2_roll_pitch": False, "go2_horizontal": False}
    if method_id == "basic_dual_yaw_EKF":
        return {"dual": True, "receiver": False, "raw": False, "source_aware": False,
                "go2_roll_pitch": False, "go2_horizontal": False}
    if method_id in AB_IDS:
        bits = tuple(value == "1" for value in method_id[2:])
        return {"dual": True, "receiver": True, "raw": bits[0], "source_aware": bits[1],
                "go2_roll_pitch": bits[2], "go2_horizontal": bits[3]}
    raise Clean2R2ARunError(f"method outside frozen CLEAN2R2A set: {method_id}")


def run_directory(method_id: str) -> str:
    return f"{METHOD_ORDER.index(method_id) + 1:02d}_{method_id}"


def _replace_config(text: str, values: Mapping[str, str]) -> str:
    rows: list[str] = []
    seen: set[str] = set()
    for row in text.splitlines():
        if ":" in row and not row.lstrip().startswith("#"):
            key = row.split(":", 1)[0].strip()
            if key in values:
                rows.append(f"{key}: {values[key]}")
                seen.add(key)
                continue
        rows.append(row)
    for key, value in values.items():
        if key not in seen:
            rows.append(f"{key}: {value}")
    rows[0] = "# CLEAN2R2A clean-only common-contract config."
    return "\n".join(rows) + "\n"


def build_runtime_config(
    *,
    method_id: str,
    clean_input_manifest: str | Path,
    auxiliary_manifest: str | Path,
    provider_protocol: str | Path,
    output_dir: str | Path,
) -> str:
    """Build one stage-specific config without changing final_v23 mathematics."""

    clean = load_clean_bundle(clean_input_manifest)
    auxiliary = validate_auxiliary_bundle(
        auxiliary_manifest,
        expected_stage_id=STAGE_ID,
        expected_protocol_id=PROTOCOL_ID,
    )
    if auxiliary.get("provider_protocol_sha256") != CANONICAL_PROVIDER_PROTOCOL_SHA256:
        raise Clean2R2ARunError("base provider used a non-canonical provider protocol")
    protocol = load_yaml_mapping(provider_protocol)
    common = protocol.get("solver_common")
    if not isinstance(common, Mapping):
        raise Clean2R2ARunError("solver_common contract missing")
    aux_paths = {
        "raw_doppler": auxiliary["auxiliary_artifacts"]["raw_doppler_provider"]["path"],
        "go2_roll_pitch": auxiliary["auxiliary_artifacts"]["go2_attitude_prior"]["path"],
        "go2_horizontal_velocity": auxiliary["auxiliary_artifacts"]["go2_horizontal_velocity_prior"]["path"],
    }
    # 中文说明：先复用完整 LegSA common config，再只替换阶段身份与冻结的六个方法旗标。
    text = active_runtime_config(
        clean.imu_path,
        clean.gnss_path,
        Path(output_dir),
        method_id="LegSA_Paper_V1",
        auxiliary_paths=aux_paths,
        extra_config=_solver_extra_config(auxiliary, common),
        run_id=run_directory(method_id),
    )
    flags = method_features(method_id)
    replacements = {
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
        "run_id": run_directory(method_id),
        "run_label": run_directory(method_id),
        "algorithm_id": method_id,
        "ablation_variant": method_id if method_id in AB_IDS else "STRUCTURAL_ONLY",
        "enable_dual_yaw": str(flags["dual"]).lower(),
        "enable_receiver_velocity": str(flags["receiver"]).lower(),
        "enable_raw_doppler": str(flags["raw"]).lower(),
        "enable_source_aware": str(flags["source_aware"]).lower(),
        "enable_go2_roll_pitch_prior": str(flags["go2_roll_pitch"]).lower(),
        "enable_go2_horizontal_velocity_prior": str(flags["go2_horizontal"]).lower(),
    }
    return _replace_config(text, replacements)


def audit_base_provider_parity(
    *, clean_input_manifest: str | Path, auxiliary_manifest: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    output = Path(output_path).resolve(strict=False)
    provider_root = output.parent.resolve(strict=True)
    if (
        provider_root.name != "04_BASE_PROVIDER"
        or provider_root.parent.name != STAGE_ID
        or provider_root.parent.parent.name != "stages"
        or provider_root.is_symlink()
    ):
        raise Clean2R2ARunError("base provider evidence is outside the exact CLEAN2R2A stage root")
    clean_manifest_path = Path(clean_input_manifest).resolve(strict=True)
    auxiliary_manifest_path = Path(auxiliary_manifest).resolve(strict=True)
    if (
        clean_manifest_path.parent.parent != provider_root
        or auxiliary_manifest_path.parent.parent != provider_root
        or clean_manifest_path.parent.is_symlink()
        or auxiliary_manifest_path.parent.is_symlink()
    ):
        raise Clean2R2ARunError("provider attempts are not direct children of CLEAN2R2A 04_BASE_PROVIDER")
    clean = load_clean_bundle(clean_manifest_path)
    auxiliary = validate_auxiliary_bundle(
        auxiliary_manifest_path, expected_stage_id=STAGE_ID, expected_protocol_id=PROTOCOL_ID,
    )
    if auxiliary.get("provider_protocol_sha256") != CANONICAL_PROVIDER_PROTOCOL_SHA256:
        raise Clean2R2ARunError("provider parity used a non-canonical provider protocol")
    clean_payload = json.loads(clean_manifest_path.read_text(encoding="utf-8"))
    if clean_payload.get("generator_code_commit") != auxiliary.get("code_freeze_commit"):
        raise Clean2R2ARunError("base/auxiliary provider code-freeze identity differs")
    if clean_payload.get("raw_source_hashes") != auxiliary.get("raw_source_hashes"):
        raise Clean2R2ARunError("base/auxiliary raw source hash set differs")
    if len(clean_payload.get("raw_source_hashes", {})) != 22:
        raise Clean2R2ARunError("provider does not bind the exact 22 raw hashes")
    actual = {
        "imu": sha256_file(clean.imu_path), "gnss": sha256_file(clean.gnss_path),
        "raw_doppler": sha256_file(auxiliary["auxiliary_artifacts"]["raw_doppler_provider"]["path"]),
        "go2_roll_pitch": sha256_file(auxiliary["auxiliary_artifacts"]["go2_attitude_prior"]["path"]),
        "go2_horizontal_velocity": sha256_file(auxiliary["auxiliary_artifacts"]["go2_horizontal_velocity_prior"]["path"]),
    }
    report = {
        "schema_version": "paper_rebuild.clean2r2a_base_provider_parity.v1",
        "stage_id": STAGE_ID, "expected_hashes": EXPECTED_PROVIDER_HASHES,
        "actual_hashes": actual, "source_quality_metadata": auxiliary["source_quality_metadata"],
        "provider_root": str(provider_root), "provider_root_exact": True,
        "clean_input_manifest_path": str(clean_manifest_path),
        "auxiliary_manifest_path": str(auxiliary_manifest_path),
        "clean_input_manifest_sha256": sha256_file(clean_manifest_path),
        "auxiliary_manifest_sha256": sha256_file(auxiliary_manifest_path),
        "raw_source_hashes": clean_payload["raw_source_hashes"],
        "code_freeze_commit": auxiliary["code_freeze_commit"],
        "base_generation_config_sha256": clean_payload["generation_config_sha256"],
        "auxiliary_bundle_hash": auxiliary["bundle_hash"],
        "provider_protocol_sha256": auxiliary["provider_protocol_sha256"],
        "provider_protocol_relative_path": CANONICAL_PROVIDER_PROTOCOL_RELATIVE.as_posix(),
        "fresh_current_raw": True, "old_provider_reused": False,
        "trace_open_count": 0, "passed": actual == EXPECTED_PROVIDER_HASHES,
    }
    write_json_atomic(output_path, report)
    if not report["passed"]:
        raise Clean2R2ARunError("BLOCKED_CLEAN2R2A_BASE_PROVIDER_PARITY_FAILED")
    return report


def _numeric_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "%")):
            continue
        try:
            values = [float(value) for value in stripped.replace(",", " ").split()]
        except ValueError:
            continue
        if not values or not all(math.isfinite(value) for value in values):
            raise Clean2R2ARunError(f"non-finite output: {path.name}")
        rows.append(values)
    if not rows:
        raise Clean2R2ARunError(f"empty numeric output: {path.name}")
    return rows


def validate_output_structure(output: str | Path) -> dict[str, Any]:
    root = Path(output).resolve(strict=True)
    nav = _numeric_rows(root / "KF_GINS_Navresult.nav")
    std = _numeric_rows(root / "KF_GINS_STD.txt")
    if len(nav) != 56642 or len(std) != 56642:
        raise Clean2R2ARunError("formal row count differs from CLEAN1R2R1")
    nav_times = [row[1] if len(row) == 11 else row[0] for row in nav]
    if abs(nav_times[0] - 66.005054) > 1.0e-6 or abs(nav_times[-1] - 339.997056) > 1.0e-6:
        raise Clean2R2ARunError("formal output time range differs from CLEAN1R2R1")
    return {
        "nav_rows": len(nav), "std_rows": len(std),
        "time_start": nav_times[0], "time_end": nav_times[-1], "finite": True,
    }


def validate_counters(method_id: str, manifest: Mapping[str, Any]) -> dict[str, int]:
    counters = module_counters(manifest)
    flags = method_features(method_id)
    active = {
        "dual": counters["dual_yaw_attempt_count"] > 0,
        "receiver": counters["receiver_velocity_update_count"] > 0,
        "raw": counters["raw_doppler_update_count"] > 0,
        "source_aware": counters["source_aware_evaluation_count"] > 0,
        "go2_roll_pitch": counters["go2_roll_pitch_update_count"] > 0,
        "go2_horizontal": counters["go2_horizontal_velocity_update_count"] > 0,
    }
    if counters["position_update_count"] <= 0 or active != flags:
        raise Clean2R2ARunError(f"module counters do not match frozen flags: {method_id}")
    if counters["dual_yaw_attempt_count"] != (
        counters["dual_yaw_normal_count"] + counters["dual_yaw_downweight_count"] +
        counters["dual_yaw_reject_count"]
    ):
        raise Clean2R2ARunError("Scheme-C action counts do not close")
    if not flags["source_aware"] and counters["source_aware_weight_changed_count"] != 0:
        raise Clean2R2ARunError("source-aware changed weights while disabled")
    for field in ("fgo_count", "qm_count", "qa_count", "contact_fk_count"):
        if counters[field] != 0:
            raise Clean2R2ARunError(f"out-of-scope counter is nonzero: {field}")
    return counters


def validate_solver_manifest(
    method_id: str,
    run_id: str,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify identities and forbidden fields from the solver-authored manifest."""

    flags = method_features(method_id)
    expected = {
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
        "run_id": run_id,
        "algorithm_id": method_id,
        "clean_final_v23_parity_mode": True,
        "enable_dual_yaw_update": flags["dual"],
        "enable_receiver_velocity_update": flags["receiver"],
        "enable_raw_doppler": flags["raw"],
        "source_aware_weighting_enabled": flags["source_aware"],
        "go2_attitude_weak_prior_enabled": flags["go2_roll_pitch"],
        "go2_horizontal_velocity_prior_enabled": flags["go2_horizontal"],
        "trace_used_online": False,
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0,
        "enable_qa_fallback": False,
        "qa_active_mode": False,
        "enable_multi_state_qm": False,
        "selected_fgo_feedback": False,
        "no_feedback_fgo": False,
        "active_nine_factor_fgo": False,
        "contact_fk_factor": False,
    }
    mismatches = [key for key, value in expected.items() if manifest.get(key) != value]
    if mismatches:
        raise Clean2R2ARunError(
            "solver-authored manifest contract mismatch: " + ",".join(sorted(mismatches))
        )
    paths = manifest.get("actual_solver_input_paths")
    roles = manifest.get("actual_solver_input_roles")
    if not isinstance(paths, Mapping) or not isinstance(roles, Mapping) or set(paths) != set(roles):
        raise Clean2R2ARunError("solver actual-input path/role ledger is incomplete")
    expected_roles = {"propagation_imu", "gnss_position_receiver_velocity_dual_yaw"}
    if flags["raw"]:
        expected_roles.add("raw_doppler_velocity")
    if flags["go2_roll_pitch"]:
        expected_roles.add("go2_roll_pitch_weak_prior")
    if flags["go2_horizontal"]:
        expected_roles.add("go2_horizontal_velocity_weak_prior")
    if set(paths) != expected_roles:
        raise Clean2R2ARunError("solver actual-input roles do not match enabled modules")
    return {"paths": dict(paths), "roles": dict(roles)}


def _audit_solver_file_opens(
    *,
    strace_path: Path,
    cwd: Path,
    raw_root: Path,
    provider_root: Path,
    runtime_root: Path,
    actual_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    opened = parse_strace_openat_paths(strace_path, cwd=cwd)
    expected = {
        role: Path(str(path)).resolve(strict=True)
        for role, path in actual_inputs["paths"].items()
    }
    if any(not is_within(path, provider_root) for path in expected.values()):
        raise Clean2R2ARunError("solver-authored input path escaped fresh provider root")
    counts = {role: sum(path == expected_path for path in opened) for role, expected_path in expected.items()}
    provider_opens = {path for path in opened if is_within(path, provider_root)}
    raw_opens = sorted({path for path in opened if is_within(path, raw_root)})
    unexpected_provider = sorted(str(path) for path in provider_opens - set(expected.values()))
    unexpected_clean = sorted(
        str(path)
        for path in set(opened)
        if is_within(path, provider_root.parents[2])
        and not is_within(path, provider_root)
        and not is_within(path, runtime_root)
    )
    legacy_opens = sorted({str(path) for path in opened if legacy_reason(path) is not None})
    trace = (raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    trace_count = sum(path == trace for path in opened)
    missing = sorted(role for role, count in counts.items() if count == 0)
    report = {
        "schema_version": "paper_rebuild.clean2r2a_solver_read_ledger.v1",
        "actual_solver_input_paths": {role: str(path) for role, path in expected.items()},
        "actual_solver_input_roles": dict(actual_inputs["roles"]),
        "actual_solver_input_open_counts": counts,
        "missing_solver_inputs": missing,
        "unexpected_provider_opens": unexpected_provider,
        "unexpected_clean_root_opens": unexpected_clean,
        "raw_root_open_count": len(raw_opens),
        "raw_root_opens": [str(path) for path in raw_opens],
        "legacy_open_count": len(legacy_opens),
        "legacy_opens": legacy_opens,
        "trace_open_count": trace_count,
        "passed": not missing and not unexpected_provider and not unexpected_clean
        and not raw_opens and not legacy_opens and trace_count == 0,
    }
    if not report["passed"]:
        raise Clean2R2ARunError("solver file-open provenance audit failed")
    return report


def validate_formal_wrapper(wrapper: Mapping[str, Any], schema_path: str | Path) -> None:
    """Execute the tracked stage schema plus fail-closed provenance checks."""

    import jsonschema

    schema = load_yaml_mapping(schema_path)
    # 运行环境冻结在 jsonschema 3.2；使用其完整支持的 Draft 7，避免
    # 因库版本差异而跳过正式 manifest 的机器校验。
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(dict(wrapper))
    if len(wrapper.get("raw_source_hashes", {})) != 22:
        raise Clean2R2ARunError("formal wrapper does not bind 22 raw hashes")
    if wrapper.get("solver_read_ledger", {}).get("passed") is not True:
        raise Clean2R2ARunError("formal wrapper read ledger is not PASS")
    if not wrapper.get("output_hashes"):
        raise Clean2R2ARunError("formal wrapper output hashes are empty")


def mechanism_evidence(method_id: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Bind actual Scheme-C/source-aware actions, not just configuration flags."""

    counters = module_counters(manifest)
    flags = method_features(method_id)
    scheme_expected = flags["dual"] and method_id != "basic_dual_yaw_EKF"
    if manifest.get("yaw_scheme_C_enabled") is not scheme_expected:
        raise Clean2R2ARunError(f"Scheme-C runtime identity mismatch: {method_id}")
    update_counts = manifest.get("source_aware_update_count_by_source")
    reject_counts = manifest.get("source_aware_reject_count_by_source")
    scale_stats = manifest.get("source_aware_R_scale_p50_p95_max_by_source")
    if not all(isinstance(value, Mapping) for value in (update_counts, reject_counts, scale_stats)):
        raise Clean2R2ARunError("source-aware runtime statistics are missing")
    trace_rows = int(manifest.get("source_aware_trace_rows", 0))
    update_total = sum(int(value) for value in update_counts.values())
    reject_total = sum(int(value) for value in reject_counts.values())
    if trace_rows != update_total or trace_rows != counters["source_aware_evaluation_count"]:
        raise Clean2R2ARunError("source-aware trace/action counts do not close")
    if not flags["source_aware"] and any(
        value != 0 for value in (
            trace_rows,
            update_total,
            reject_total,
            counters["source_aware_weight_changed_count"],
        )
    ):
        raise Clean2R2ARunError("source-aware action occurred while the module was disabled")
    return {
        "scheme_c": {
            "enabled": scheme_expected,
            "attempt": counters["dual_yaw_attempt_count"],
            "normal": counters["dual_yaw_normal_count"],
            "downweight": counters["dual_yaw_downweight_count"],
            "reject": counters["dual_yaw_reject_count"],
            "accepted": counters["dual_yaw_accepted_count"],
        },
        "source_aware": {
            "enabled": flags["source_aware"],
            "evaluations": counters["source_aware_evaluation_count"],
            "changed": counters["source_aware_weight_changed_count"],
            "rejects": reject_total,
            "updates_by_source": dict(update_counts),
            "rejects_by_source": dict(reject_counts),
            "R_scale_p50_p95_max_by_source": dict(scale_stats),
        },
    }


def _trace_open_count(strace_path: Path, *, cwd: Path, raw_root: Path) -> int:
    trace = (raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    return sum(path == trace for path in parse_strace_openat_paths(strace_path, cwd=cwd))


def classify_failure(returncode: int | None, stdout: str, stderr: str) -> str:
    """只授权冻结的技术失败类别；合同/数据/方法错误不得自动重试。"""

    if returncode == 0:
        return "success"
    text = f"{stdout}\n{stderr}".lower()
    if returncode is not None and returncode < 0:
        return "process_crash_signal"
    if returncode == 137 or any(token in text for token in (
        "cannot allocate memory", "out of memory", "resource temporarily unavailable",
    )):
        return "resource_exhaustion"
    if any(token in text for token in ("input/output error", "stale file handle")):
        return "io_transient"
    if any(token in text for token in ("lost pty", "pty closed", "transport endpoint is not connected")):
        return "lost_pty"
    return "nontechnical_solver_contract_or_data_failure"


def run_methods(
    *,
    methods: Sequence[str],
    repo_root: str | Path,
    raw_root: str | Path,
    executable: str | Path,
    clean_input_manifest: str | Path,
    auxiliary_manifest: str | Path,
    provider_protocol: str | Path,
    provider_parity_report: str | Path,
    local_config: str | Path,
    runtime_root: str | Path,
    code_freeze_commit: str,
    timeout_seconds: int = 1800,
) -> list[dict[str, Any]]:
    repo = Path(repo_root).resolve(strict=True)
    raw = Path(raw_root).resolve(strict=True)
    binary = Path(executable).resolve(strict=True)
    root = Path(runtime_root).resolve(strict=True)
    local_config_path = Path(local_config).resolve(strict=True)
    provider_protocol_path = validate_canonical_provider_protocol(repo, provider_protocol)
    schema_path = repo / "configs" / "paper_rebuild" / FORMAL_SCHEMA_NAME
    clean_manifest_path = Path(clean_input_manifest).resolve(strict=True)
    auxiliary_manifest_path = Path(auxiliary_manifest).resolve(strict=True)
    parity_path = Path(provider_parity_report).resolve(strict=True)
    if (
        root.name != "06_FORMAL_RUNS"
        or root.parent.name != STAGE_ID
        or root.parent.parent.name != "stages"
        or root.is_symlink()
    ):
        raise Clean2R2ARunError("formal runtime root is not the exact CLEAN2R2A stage root")
    stage_root = root.parent
    expected_provider_root = stage_root / "04_BASE_PROVIDER"
    expected_parity_path = expected_provider_root / "CLEAN2R2A_BASE_PROVIDER_PARITY.json"
    if parity_path != expected_parity_path.resolve(strict=True):
        raise Clean2R2ARunError("formal provider parity report path is not exact")
    clean_bundle = load_clean_bundle(clean_manifest_path)
    auxiliary_bundle = validate_auxiliary_bundle(
        auxiliary_manifest_path,
        expected_stage_id=STAGE_ID,
        expected_protocol_id=PROTOCOL_ID,
    )
    clean_payload = json.loads(clean_manifest_path.read_text(encoding="utf-8"))
    if auxiliary_bundle.get("provider_protocol_sha256") != sha256_file(provider_protocol_path):
        raise Clean2R2ARunError("formal provider protocol differs from auxiliary generation")
    raw_source_hashes = clean_payload.get("raw_source_hashes")
    if not isinstance(raw_source_hashes, Mapping) or len(raw_source_hashes) != 22:
        raise Clean2R2ARunError("formal provider does not bind exact 22 raw hashes")
    provider_root = clean_manifest_path.parent.parent.resolve(strict=True)
    if (
        provider_root != auxiliary_manifest_path.parent.parent.resolve(strict=True)
        or provider_root != expected_provider_root.resolve(strict=True)
        or provider_root.is_symlink()
    ):
        raise Clean2R2ARunError("formal providers are not bound to the exact fresh stage root")
    provider_hashes = {
        "clean_input_manifest": sha256_file(clean_manifest_path),
        "auxiliary_manifest": sha256_file(auxiliary_manifest_path),
        "imu": sha256_file(clean_bundle.imu_path),
        "gnss": sha256_file(clean_bundle.gnss_path),
        "raw_doppler": sha256_file(auxiliary_bundle["auxiliary_artifacts"]["raw_doppler_provider"]["path"]),
        "go2_roll_pitch": sha256_file(auxiliary_bundle["auxiliary_artifacts"]["go2_attitude_prior"]["path"]),
        "go2_horizontal_velocity": sha256_file(auxiliary_bundle["auxiliary_artifacts"]["go2_horizontal_velocity_prior"]["path"]),
        "source_quality_metadata": sha256_file(auxiliary_bundle["source_quality_metadata"]["path"]),
    }
    parity = json.loads(parity_path.read_text(encoding="utf-8"))
    if (
        parity.get("stage_id") != STAGE_ID
        or parity.get("passed") is not True
        or parity.get("provider_root_exact") is not True
        or Path(str(parity.get("provider_root", ""))).resolve(strict=True) != provider_root
        or parity.get("actual_hashes") != EXPECTED_PROVIDER_HASHES
        or parity.get("clean_input_manifest_sha256") != provider_hashes["clean_input_manifest"]
        or parity.get("auxiliary_manifest_sha256") != provider_hashes["auxiliary_manifest"]
        or parity.get("source_quality_metadata", {}).get("sha256") != provider_hashes["source_quality_metadata"]
        or parity.get("raw_source_hashes") != raw_source_hashes
        or parity.get("code_freeze_commit") != code_freeze_commit
    ):
        raise Clean2R2ARunError("formal provider bundle does not close against the PASS parity report")
    local_paths = load_yaml_mapping(local_config_path).get("paths")
    expected_local_paths = {
        "code_root": repo,
        "raw_root": raw,
        "clean_root": stage_root.parents[1],
        "provider_root": provider_root,
        "runtime_root": root,
    }
    if not isinstance(local_paths, Mapping):
        raise Clean2R2ARunError("formal local config paths are missing")
    for role, expected in expected_local_paths.items():
        candidate = Path(str(local_paths.get(role, ""))).expanduser().resolve(strict=True)
        if candidate != expected or any(path.is_symlink() for path in (candidate, *candidate.parents)):
            raise Clean2R2ARunError(f"formal local config path mismatch: {role}")
    expected_input_paths = {
        "propagation_imu": clean_bundle.imu_path,
        "gnss_position_receiver_velocity_dual_yaw": clean_bundle.gnss_path,
        "raw_doppler_velocity": Path(auxiliary_bundle["auxiliary_artifacts"]["raw_doppler_provider"]["path"]),
        "go2_roll_pitch_weak_prior": Path(auxiliary_bundle["auxiliary_artifacts"]["go2_attitude_prior"]["path"]),
        "go2_horizontal_velocity_weak_prior": Path(auxiliary_bundle["auxiliary_artifacts"]["go2_horizontal_velocity_prior"]["path"]),
        "go2_source_quality_metadata": Path(auxiliary_bundle["source_quality_metadata"]["path"]),
    }
    commit, dirty = git_code_state(repo)
    if dirty or commit != code_freeze_commit:
        raise Clean2R2ARunError("formal run requires exact clean code freeze")
    attempts_path = root.parent / "05_RUN_REGISTRY" / "CLEAN2R2A_RUN_ATTEMPTS.csv"
    attempts_path.parent.mkdir(parents=True, exist_ok=True)
    failed_root = root / ".failed_attempts"
    records: list[dict[str, Any]] = []
    for method_id in methods:
        if method_id not in METHOD_ORDER:
            raise Clean2R2ARunError("requested method is outside frozen registry")
        output = root / run_directory(method_id)
        if output.exists():
            raise Clean2R2ARunError(f"formal output already exists: {method_id}")
        completed = None
        completed_returncode: int | None = None
        runtime_seconds = 0.0
        config = output / "CLEAN2R2A_RUNTIME_CONFIG.yaml"
        strace_path = output / "logs" / "SOLVER_FILE_OPEN_TRACE.raw"
        for attempt_number in (1, 2):
            output.mkdir(parents=True)
            logs = output / "logs"
            logs.mkdir()
            config = output / "CLEAN2R2A_RUNTIME_CONFIG.yaml"
            config.write_text(build_runtime_config(
                method_id=method_id,
                clean_input_manifest=clean_manifest_path,
                auxiliary_manifest=auxiliary_manifest_path,
                provider_protocol=provider_protocol_path,
                output_dir=output,
            ), encoding="utf-8")
            config_hash = sha256_file(config)
            strace_path = logs / "SOLVER_FILE_OPEN_TRACE.raw"
            solver_command = [
                str(binary), "--config", str(config), "--output-dir", str(output),
                "--debug-update-timeline", "--debug-output-dir", str(output),
                "--debug-max-rows", "1000000",
            ]
            strace = shutil.which("strace")
            if not strace:
                raise Clean2R2ARunError("strace is required for formal no-trace proof")
            command = [strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat",
                       "-o", str(strace_path), *solver_command]
            started = time.monotonic()
            execution_exception: Exception | None = None
            try:
                completed = run_process_group(
                    command,
                    cwd=repo,
                    timeout_seconds=timeout_seconds,
                    timeout_message="CLEAN2R2A solver timeout; process group terminated",
                    launch_failure_message="CLEAN2R2A solver launch failure",
                )
                completed_returncode = completed.returncode
                stdout = completed.stdout
                stderr = completed.stderr
            except Exception as exc:  # fail closed, but still journal the owned attempt
                execution_exception = exc
                completed_returncode = None
                stdout = ""
                stderr = str(exc)
            runtime_seconds = time.monotonic() - started
            (logs / "stdout.txt").write_text(stdout, encoding="utf-8")
            (logs / "stderr.txt").write_text(stderr, encoding="utf-8")
            failure_class = classify_failure(completed_returncode, stdout, stderr)
            technical_failure = failure_class in TECHNICAL_FAILURE_CLASSES
            terminal_success = completed_returncode == 0
            attempt = {
                "method_id": method_id, "attempt": attempt_number,
                "returncode": "" if completed_returncode is None else completed_returncode,
                "technical_retry": attempt_number == 2,
                "technical_failure": technical_failure,
                "failure_class": failure_class,
                "retry_authorized": technical_failure and attempt_number == 1,
                "terminal_success": terminal_success,
                "metric_driven_rerun": False,
                "runtime_config_hash": config_hash,
                "executable_hash": sha256_file(binary),
                "runtime_seconds": runtime_seconds,
            }
            exists = attempts_path.is_file()
            with attempts_path.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(attempt))
                if not exists:
                    writer.writeheader()
                writer.writerow(attempt)
            if terminal_success:
                break
            failed_root.mkdir(exist_ok=True)
            failed_destination = failed_root / f"{run_directory(method_id)}_attempt_{attempt_number:02d}"
            os.replace(output, failed_destination)
            if execution_exception is not None and not technical_failure:
                break
            if not technical_failure or attempt_number == 2:
                break
        if completed_returncode != 0:
            raise Clean2R2ARunError(f"BLOCKED_CLEAN2R2A_FORMAL_EXECUTION_FAILED: {method_id}")
        required = [output / name for name in OUTPUT_ROLES[:4]]
        if not all(path.is_file() for path in required):
            raise Clean2R2ARunError(f"formal output set incomplete: {method_id}")
        solver_manifest = json.loads((output / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        actual_inputs = validate_solver_manifest(method_id, run_directory(method_id), solver_manifest)
        for role, path in actual_inputs["paths"].items():
            if Path(str(path)).resolve(strict=True) != expected_input_paths[role].resolve(strict=True):
                raise Clean2R2ARunError(f"solver input path differs from fresh provider: {role}")
        counters = validate_counters(method_id, solver_manifest)
        mechanisms = mechanism_evidence(method_id, solver_manifest)
        structure = validate_output_structure(output)
        read_ledger = _audit_solver_file_opens(
            strace_path=strace_path, cwd=repo, raw_root=raw,
            provider_root=provider_root, runtime_root=root, actual_inputs=actual_inputs,
        )
        read_ledger_path = write_json_atomic(output / "CLEAN2R2A_SOLVER_READ_LEDGER.json", read_ledger)
        with (output / "CLEAN2R2A_SOLVER_READ_LEDGER.csv").open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("role", "path", "semantic_role", "open_count", "sha256"))
            writer.writeheader()
            for role, path in actual_inputs["paths"].items():
                resolved = Path(str(path)).resolve(strict=True)
                writer.writerow({"role": role, "path": str(resolved),
                                 "semantic_role": actual_inputs["roles"][role],
                                 "open_count": read_ledger["actual_solver_input_open_counts"][role],
                                 "sha256": sha256_file(resolved)})
        output_hashes = {
            path.relative_to(output).as_posix(): sha256_file(path)
            for path in sorted(item for item in output.rglob("*") if item.is_file())
        }
        wrapper = {
            "schema_version": "paper_rebuild.clean2r2a_formal_run.v1",
            "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": CASE_ID,
            "data_mode": DATA_MODE, "run_id": run_directory(method_id),
            "algorithm_id": method_id, "method_features": method_features(method_id),
            "code_commit": code_freeze_commit, "code_worktree_dirty_at_run": False,
            "executable_hash": sha256_file(binary), "runtime_config_hash": sha256_file(config),
            "local_config_hash": sha256_file(local_config_path),
            "provider_protocol_hash": sha256_file(provider_protocol_path),
            "formal_schema_hash": sha256_file(schema_path),
            "base_provider_parity_sha256": sha256_file(parity_path),
            "provider_hashes": provider_hashes,
            "raw_source_hashes": dict(raw_source_hashes),
            "provider_generation": {
                "base_generator_code_commit": clean_payload["generator_code_commit"],
                "base_generation_config_sha256": clean_payload["generation_config_sha256"],
                "base_contract_sha256": clean_payload["contract_sha256"],
                "auxiliary_code_freeze_commit": auxiliary_bundle["code_freeze_commit"],
                "auxiliary_bundle_hash": auxiliary_bundle["bundle_hash"],
                "provider_protocol_sha256": auxiliary_bundle["provider_protocol_sha256"],
            },
            "solver_manifest_sha256": sha256_file(output / "RUN_MANIFEST.json"),
            "actual_solver_inputs": {
                role: {"path": str(Path(str(path)).resolve(strict=True)),
                       "role": actual_inputs["roles"][role],
                       "sha256": sha256_file(Path(str(path)).resolve(strict=True)),
                       "open_count": read_ledger["actual_solver_input_open_counts"][role]}
                for role, path in actual_inputs["paths"].items()
            },
            "solver_read_ledger": read_ledger,
            "solver_read_ledger_sha256": sha256_file(read_ledger_path),
            "output_hashes": output_hashes,
            "synthetic_data_used": False, "semisynthetic_data_used": False,
            "trace_used_online": False, "trace_open_count": read_ledger["trace_open_count"],
            "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False, "per_case_tuning": False,
            "output_only_correction": False, "epoch_deleted_for_metric": False,
            "old_runtime_input_count": 0, "legacy_provider_input_count": 0,
            "legacy_row_input_count": 0, "legacy_aggregate_input_count": 0,
            "module_counters": counters, "mechanism_evidence": mechanisms,
            "structure": structure,
            "runtime_seconds": runtime_seconds, "solver_returncode": 0,
            "metric_driven_rerun": False, "terminal_status": "PASS",
        }
        validate_formal_wrapper(wrapper, schema_path)
        wrapper_path = write_json_atomic(output / "CLEAN2R2A_FORMAL_RUN_MANIFEST.json", wrapper)
        records.append({
            "method_id": method_id, "run_id": run_directory(method_id),
            "runtime_config_hash": sha256_file(config), "formal_manifest_hash": sha256_file(wrapper_path),
            "terminal_status": "PASS", "trace_open_count": 0,
        })
    commit_after, dirty_after = git_code_state(repo)
    if dirty_after or commit_after != code_freeze_commit:
        raise Clean2R2ARunError("code state changed during formal execution")
    return records


def structural_parity_gate(*, runtime_root: str | Path, clean1_runtime_root: str | Path) -> dict[str, Any]:
    current = Path(runtime_root).resolve(strict=True)
    anchor = Path(clean1_runtime_root).resolve(strict=True)
    expected_anchor = (
        current.parents[2] / "17_LOGS" / "CLEAN1R2R1_FINAL" / "04_FOUR_METHOD_RUNTIME"
    ).resolve(strict=True)
    if anchor != expected_anchor or anchor.is_symlink():
        raise Clean2R2ARunError("CLEAN1R2R1 structural anchor path is not the frozen current-evidence root")
    mapping = {
        "single_antenna_EKF": "01_single_antenna_EKF",
        "basic_dual_yaw_EKF": "02_basic_dual_yaw_EKF",
        "AB0000": "03_strong_dual_yaw_EKF",
        "AB1111": "04_LegSA_Paper_V1",
    }
    rows: list[dict[str, Any]] = []
    for method_id, reference_dir in mapping.items():
        output = current / run_directory(method_id)
        reference = anchor / reference_dir
        current_manifest = json.loads((output / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        reference_manifest = json.loads((reference / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        counters_equal = module_counters(current_manifest) == module_counters(reference_manifest)
        nav_equal = sha256_file(output / "KF_GINS_Navresult.nav") == sha256_file(reference / "KF_GINS_Navresult.nav")
        std_equal = sha256_file(output / "KF_GINS_STD.txt") == sha256_file(reference / "KF_GINS_STD.txt")
        rows.append({"method_id": method_id, "clean1_anchor": reference_dir,
                     "nav_bit_identical": nav_equal, "std_bit_identical": std_equal,
                     "counters_exact": counters_equal, "passed": nav_equal and std_equal and counters_equal})
    report = {
        "schema_version": "paper_rebuild.clean2r2a_structural_gate.v1",
        "trace_opened": False, "performance_metrics_read": False,
        "rows": rows, "passed": all(row["passed"] for row in rows),
    }
    write_json_atomic(current.parent / "11_AUDITS" / "CLEAN2R2A_C00_STRUCTURAL_GATE.json", report)
    if not report["passed"]:
        raise Clean2R2ARunError("BLOCKED_CLEAN2R2A_C00_STRUCTURAL_GATE_FAILED")
    return report


def seal_outputs(runtime_root: str | Path) -> dict[str, Any]:
    root = Path(runtime_root).resolve(strict=True)
    expected_dirs = {run_directory(method) for method in METHOD_ORDER}
    actual_dirs = {path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")}
    if actual_dirs != expected_dirs:
        raise Clean2R2ARunError("cannot seal without the exact 18 formal run directories")
    evaluation_root = root.parent / "08_OFFLINE_EVALUATION"
    if any(evaluation_root.iterdir()):
        raise Clean2R2ARunError("offline evaluation opened before the formal output seal")
    schema_path = root.parent / "02_PROTOCOLS" / FORMAL_SCHEMA_NAME
    rows: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        run_root = root / run_directory(method)
        wrapper = json.loads((run_root / "CLEAN2R2A_FORMAL_RUN_MANIFEST.json").read_text(encoding="utf-8"))
        validate_formal_wrapper(wrapper, schema_path)
        if wrapper.get("terminal_status") != "PASS" or wrapper.get("trace_open_count") != 0:
            raise Clean2R2ARunError("formal wrapper is not terminal PASS/no-trace")
        for path in sorted(item for item in run_root.rglob("*") if item.is_file()):
            rows.append({"algorithm_id": method, "relative_path": path.relative_to(root).as_posix(),
                         "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                         "sealed_before_trace": True})
    seal_root = root.parent / "07_OUTPUT_SEAL"
    seal_root.mkdir(parents=True, exist_ok=True)
    manifest = seal_root / "OUTPUT_HASH_MANIFEST.csv"
    with manifest.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    counts = {method: sum(row["algorithm_id"] == method for row in rows) for method in METHOD_ORDER}
    journal = {
        "schema_version": "paper_rebuild.clean2r2a_output_seal.v1",
        "unique_formal_runs": 18, "sealed_file_count": len(rows),
        "method_ids": list(METHOD_ORDER), "sealed_file_count_by_method": counts,
        "all_terminal_pass": True, "trace_open_count_before_seal": 0,
        "all_outputs_sealed_before_trace": True,
        "output_hash_manifest_sha256": sha256_file(manifest),
        "output_hash_manifest_size_bytes": manifest.stat().st_size,
        "passed": True,
    }
    write_json_atomic(seal_root / "OUTPUT_SEAL_JOURNAL.json", journal)
    return journal


def validate_output_seal(stage_root: str | Path) -> list[dict[str, str]]:
    stage = Path(stage_root).resolve(strict=True)
    runtime = stage / "06_FORMAL_RUNS"
    manifest = stage / "07_OUTPUT_SEAL" / "OUTPUT_HASH_MANIFEST.csv"
    journal = json.loads((stage / "07_OUTPUT_SEAL" / "OUTPUT_SEAL_JOURNAL.json").read_text(encoding="utf-8"))
    if (
        journal.get("passed") is not True
        or journal.get("all_outputs_sealed_before_trace") is not True
        or journal.get("trace_open_count_before_seal") != 0
        or journal.get("unique_formal_runs") != 18
        or journal.get("method_ids") != list(METHOD_ORDER)
        or journal.get("output_hash_manifest_sha256") != sha256_file(manifest)
        or journal.get("output_hash_manifest_size_bytes") != manifest.stat().st_size
    ):
        raise Clean2R2ARunError("output seal journal failed")
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    required_fields = {"algorithm_id", "relative_path", "size_bytes", "sha256", "sealed_before_trace"}
    if set(reader.fieldnames or ()) != required_fields or len(rows) != journal.get("sealed_file_count"):
        raise Clean2R2ARunError("output seal row schema/count mismatch")
    expected_dirs = {run_directory(method) for method in METHOD_ORDER}
    actual_dirs = {path.name for path in runtime.iterdir() if path.is_dir() and not path.name.startswith(".")}
    if actual_dirs != expected_dirs:
        raise Clean2R2ARunError("sealed runtime directory set changed")
    expected_pairs: list[tuple[str, str]] = []
    for method in METHOD_ORDER:
        run_root = runtime / run_directory(method)
        for path in sorted(item for item in run_root.rglob("*") if item.is_file()):
            expected_pairs.append((method, path.relative_to(runtime).as_posix()))
    actual_pairs = [(row["algorithm_id"], row["relative_path"]) for row in rows]
    if actual_pairs != expected_pairs or len(set(actual_pairs)) != len(actual_pairs):
        raise Clean2R2ARunError("output seal is not an exact current-file closure")
    observed_counts = {method: 0 for method in METHOD_ORDER}
    for row in rows:
        if row["algorithm_id"] not in observed_counts or row.get("sealed_before_trace") != "True":
            raise Clean2R2ARunError("output seal method/trace identity mismatch")
        observed_counts[row["algorithm_id"]] += 1
        path = (runtime / row["relative_path"]).resolve(strict=True)
        if (
            runtime not in path.parents
            or path.stat().st_size != int(row["size_bytes"])
            or sha256_file(path) != row["sha256"]
        ):
            raise Clean2R2ARunError("sealed output changed")
    if observed_counts != journal.get("sealed_file_count_by_method") or any(value <= 0 for value in observed_counts.values()):
        raise Clean2R2ARunError("output seal 18-method coverage mismatch")
    return rows
