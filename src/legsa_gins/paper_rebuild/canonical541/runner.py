"""Method-bound input generation, case-isolated execution, and output sealing."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import signal
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from .provider_generator import ProviderBundle, ProviderTable, compose_solver_gnss18, sha256_file, _read_csv
from .full_method_registry import FEATURE_FIELDS, MethodProfile
from .authorization import validate_attempt_root
from ..clean2r2a_runner import build_runtime_config as build_clean_runtime_config
from ..clean1r2r1_formal import module_counters
from ..evidence import BY2_TRACE_RELATIVE_PATH, parse_strace_openat_paths
from ..manifest import git_code_state
from ..paths import is_within, legacy_reason


STAGE_ID = "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"
PROTOCOL_ID = "CANONICAL541_BY2_CONTROLLED_DEGRADATION"
TECHNICAL_FAILURE_CLASSES = {"process_crash_signal", "io_transient", "resource_exhaustion", "lost_pty"}
TERMINAL_STATUSES = {
    "COMPLETED_EVALUABLE",
    "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF",
}
EXPECTED_OUTPUT_ROWS = 56642
EXPECTED_TIME_START_S = 66.005054
EXPECTED_TIME_END_S = 339.997056
REQUIRED_SOLVER_OUTPUTS = (
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "RUN_MANIFEST.json",
    "PORT_GNSS_UPDATE_TRACE.csv",
)


class CanonicalRunnerError(RuntimeError):
    pass


CANONICAL_CASE_RE = re.compile(r"D(?:0[1-9]|[1-5][0-9]|60)_seed_0[0-8]\Z")


def canonical_data_mode(case_id: str) -> str:
    """Return the only lawful formal data mode for an exact canonical case."""

    if case_id == "C00_clean_normal":
        return "real_clean"
    if CANONICAL_CASE_RE.fullmatch(case_id):
        return "real_base_controlled_degradation"
    raise CanonicalRunnerError(f"case_id outside canonical 541 contract: {case_id}")


def method_bound_bundle(base: ProviderBundle, case_bundle: ProviderBundle,
                        profile: MethodProfile) -> ProviderBundle:
    """Restore every unconsumed source to C00 before constructing actual input.

    This is what makes an invariant alias an exact byte identity rather than an
    assumption about ignored columns.
    """

    output = case_bundle.clone()
    consumed = {
        "gnss_position": True,
        "receiver_velocity": profile.flags["receiver_velocity"],
        "dual_yaw": profile.flags["dual_yaw"],
        "raw_doppler": profile.flags["raw_doppler"],
        "go2_rp": profile.flags["go2_rp"],
        "go2_hv": profile.flags["go2_hv"],
        # Current C++ runtime has no source-quality-metadata file loader.
        "source_quality_metadata": False,
    }
    for source, enabled in consumed.items():
        if not enabled:
            output.tables[source] = base.tables[source].clone()
    return output


def materialize_method_bound_inputs(
    *, base: ProviderBundle, case_bundle: ProviderBundle, profile: MethodProfile,
    output_root: str | Path, case_provider_paths: Mapping[str, str | Path],
    shared_gnss_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=False)
    bound = method_bound_bundle(base, case_bundle, profile)
    gnss_clean = all(bound.tables[source].sha256() == base.tables[source].sha256()
                     for source in ("gnss_position", "receiver_velocity", "dual_yaw"))
    if gnss_clean:
        gnss_path = Path(base.original_provider_paths["combined_gnss"]).resolve(strict=True)
        if sha256_file(gnss_path) != base.base_provider_hashes["gnss"]:
            raise CanonicalRunnerError("clean method-bound GNSS is not the original fresh 15-column provider")
    else:
        gnss_bytes = "".join(" ".join(row) + "\n" for row in compose_solver_gnss18(bound)).encode("utf-8")
        gnss_hash = hashlib.sha256(gnss_bytes).hexdigest()
        if shared_gnss_root is None:
            gnss_path = root / "method_bound_18col.gnss"
        else:
            store = Path(shared_gnss_root); store.mkdir(parents=True, exist_ok=True)
            gnss_path = store / f"{gnss_hash}.gnss"
        if gnss_path.exists():
            if sha256_file(gnss_path) != gnss_hash:
                raise CanonicalRunnerError("shared method-bound GNSS hash collision")
        else:
            gnss_path.write_bytes(gnss_bytes)
    actual: dict[str, Path] = {"imu": base.imu_path.resolve(strict=True), "gnss": gnss_path}
    for source, filename, flag in (
        ("raw_doppler", "raw_doppler_provider.csv", "raw_doppler"),
        ("go2_rp", "go2_rp_provider.csv", "go2_rp"),
        ("go2_hv", "go2_hv_provider.csv", "go2_hv"),
    ):
        if profile.flags[flag]:
            # 中文说明：auxiliary 输入直接指向已封存 case/C00 provider；每个 run 不再复制大文件。
            path = Path(case_provider_paths[source]).resolve(strict=True)
            expected = bound.tables[source].sha256()
            if expected == base.tables[source].sha256():
                base_path = Path(base.original_provider_paths[source]).resolve(strict=True)
                path = base_path
                if sha256_file(path) != base.base_provider_hashes[source]:
                    raise CanonicalRunnerError(f"clean auxiliary is not original fresh bytes: {source}")
            else:
                fields, rows = _read_csv(path)
                if ProviderTable(fields, rows).sha256() != expected:
                    raise CanonicalRunnerError(f"method-bound provider semantic mismatch: {source}")
            actual[source] = path
    hashes = {role: sha256_file(path) for role, path in actual.items()}
    payload = {
        "method_id": profile.method_id, "method_name": profile.name,
        "effective_profile": profile.effective_profile,
        "effective_flags": dict(profile.flags),
        "actual_solver_inputs": {role: str(path) for role, path in actual.items()},
        "actual_solver_input_hashes": hashes,
        "full_case_bundle_hashes": case_bundle.hashes(),
        "method_bound_source_hashes": bound.hashes(),
        "source_quality_metadata_active_loader": False,
        "method_bound_bundle_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest(),
    }
    (root / "METHOD_BOUND_INPUT_MANIFEST.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _replace_yaml_values(text: str, replacements: Mapping[str, Any]) -> str:
    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise CanonicalRunnerError("runtime template is not YAML mapping")
    payload.update(replacements)
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def runtime_profile_id(profile: MethodProfile) -> str:
    # F03/F04 retain methods.yaml identity; A02/A01 bind to those same exact profiles.
    aliases = {"AB0000": "strong_dual_yaw_EKF", "AB1111": "LegSA_Paper_V1"}
    if profile.effective_profile in aliases:
        return aliases[profile.effective_profile]
    if profile.name in {"single_antenna_EKF", "basic_dual_yaw_EKF"}:
        return profile.name
    return profile.effective_profile


def clean2r2a_template_profile_id(profile: MethodProfile) -> str:
    """Select the narrow parent template identity without changing canonical identity."""

    if profile.effective_profile in {"single_antenna_EKF", "basic_dual_yaw_EKF"}:
        return profile.effective_profile
    if re.fullmatch(r"AB[01]{4}", profile.effective_profile):
        # 中文说明：CLEAN2R2A 父构造器只认识 single/basic 与 ABxxxx；
        # canonical 的算法/展示身份仍由 runtime_profile_id 独立保存。
        return profile.effective_profile
    raise CanonicalRunnerError(
        f"profile cannot bridge to frozen CLEAN2R2A template: {profile.method_id}"
    )


def build_runtime_config(
    *, profile: MethodProfile, clean_input_manifest: str | Path,
    auxiliary_manifest: str | Path, provider_protocol: str | Path,
    method_bound_manifest: Mapping[str, Any], output_dir: str | Path,
    case_id: str, run_id: str,
) -> str:
    template = build_clean_runtime_config(
        method_id=clean2r2a_template_profile_id(profile),
        clean_input_manifest=clean_input_manifest,
        auxiliary_manifest=auxiliary_manifest, provider_protocol=provider_protocol,
        output_dir=output_dir,
    )
    actual = method_bound_manifest["actual_solver_inputs"]
    values: dict[str, Any] = {
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": case_id,
        "run_id": run_id, "run_label": run_id,
        # 中文说明：canonical541 有自己的 formal 身份；不得伪装成 CLEAN2R2A/C00。
        "algorithm_id": runtime_profile_id(profile),
        "data_mode": canonical_data_mode(case_id), "imupath": actual["imu"],
        "gnsspath": actual["gnss"], "outputpath": str(Path(output_dir).resolve()),
        "enable_dual_yaw": profile.flags["dual_yaw"],
        "enable_receiver_velocity": profile.flags["receiver_velocity"],
        "enable_raw_doppler": profile.flags["raw_doppler"],
        "enable_source_aware": profile.flags["source_aware"],
        "enable_go2_roll_pitch_prior": profile.flags["go2_rp"],
        "enable_go2_horizontal_velocity_prior": profile.flags["go2_hv"],
        "trace_used_online": False, "synthetic_data_used": False,
        "semisynthetic_data_used": False, "per_case_tuning": False,
        "output_only_correction": False, "epoch_deleted_for_metric": False,
        "enable_selected_fgo_feedback": False, "enable_no_feedback_fgo": False,
        "enable_active_nine_factor_fgo": False, "enable_multi_state_qm": False,
        "enable_qa_fallback": False, "enable_contact_fk_factor": False,
    }
    if profile.flags["raw_doppler"]: values["raw_doppler_factor_path"] = actual["raw_doppler"]
    if profile.flags["go2_rp"]: values["go2_attitude_prior_path"] = actual["go2_rp"]
    if profile.flags["go2_hv"]: values["go2_horizontal_velocity_prior_path"] = actual["go2_hv"]
    return _replace_yaml_values(template, values)


def scientific_runtime_config_hash(text: str) -> str:
    payload = yaml.safe_load(text)
    if not isinstance(payload, dict): raise CanonicalRunnerError("runtime config is not a mapping")
    for field in ("run_id", "run_label", "case_id", "algorithm_id", "outputpath"):
        payload.pop(field, None)
    for path_field in ("imupath", "gnsspath", "raw_doppler_factor_path", "go2_attitude_prior_path", "go2_horizontal_velocity_prior_path"):
        if path_field in payload: payload[path_field] = f"input-role://{path_field}"
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def actual_rendered_runtime_config_sha256(text: str) -> str:
    """Hash the normalized rendered config, retaining identities and input paths.

    Only the attempt-owned output directory and the optional self-hash field are
    normalized, so preparation and retry renderings have one non-circular value.
    """

    payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise CanonicalRunnerError("runtime config is not a mapping")
    payload.pop("actual_rendered_runtime_config_sha256", None)
    if "outputpath" in payload:
        payload["outputpath"] = "attempt-output://canonical541"
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def classify_failure(returncode: int | None, stdout: str, stderr: str) -> str:
    """Classify only frozen technical retry reasons; metrics never enter here."""

    if returncode == 0:
        return "success"
    text = f"{stdout}\n{stderr}".lower()
    if returncode is not None and returncode < 0:
        return "process_crash_signal"
    if returncode == 137 or any(token in text for token in (
        "out of memory", "cannot allocate memory", "resource temporarily unavailable",
    )):
        return "resource_exhaustion"
    if any(token in text for token in ("input/output error", "stale file handle")):
        return "io_transient"
    if any(token in text for token in ("lost pty", "pty closed", "transport endpoint is not connected")):
        return "lost_pty"
    return "nontechnical_algorithm_or_contract_failure"


def _numeric_file_audit(path: Path) -> dict[str, Any]:
    rows = 0
    first_time: float | None = None
    last_time: float | None = None
    last_finite_time: float | None = None
    first_nonfinite_time: float | None = None
    malformed_rows = 0
    if not path.is_file():
        return {
            "exists": False, "rows": 0, "time_start": None, "time_end": None,
            "finite": False, "first_nonfinite_time": None, "last_finite_time": None,
            "malformed_rows": 0,
        }
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "%")):
            continue
        try:
            values = [float(value) for value in stripped.replace(",", " ").split()]
        except ValueError:
            malformed_rows += 1
            continue
        if not values:
            continue
        rows += 1
        time_value = values[1] if len(values) == 11 else values[0]
        first_time = time_value if first_time is None else first_time
        last_time = time_value
        if all(math.isfinite(value) for value in values):
            last_finite_time = time_value
        elif first_nonfinite_time is None:
            first_nonfinite_time = time_value
    return {
        "exists": True, "rows": rows, "time_start": first_time, "time_end": last_time,
        "finite": first_nonfinite_time is None and malformed_rows == 0 and rows > 0,
        "first_nonfinite_time": first_nonfinite_time, "last_finite_time": last_finite_time,
        "malformed_rows": malformed_rows,
    }


def validate_output_structure(output_root: str | Path, *, require_exact: bool) -> dict[str, Any]:
    root = Path(output_root).resolve(strict=True)
    nav = _numeric_file_audit(root / "KF_GINS_Navresult.nav")
    std = _numeric_file_audit(root / "KF_GINS_STD.txt")
    payload = {"nav": nav, "std": std}
    exact = (
        nav["rows"] == std["rows"] == EXPECTED_OUTPUT_ROWS
        and nav["finite"] is True and std["finite"] is True
        and nav["time_start"] is not None and nav["time_end"] is not None
        and std["time_start"] is not None and std["time_end"] is not None
        and abs(float(nav["time_start"]) - EXPECTED_TIME_START_S) <= 1.0e-6
        and abs(float(nav["time_end"]) - EXPECTED_TIME_END_S) <= 1.0e-6
        and abs(float(std["time_start"]) - EXPECTED_TIME_START_S) <= 1.0e-6
        and abs(float(std["time_end"]) - EXPECTED_TIME_END_S) <= 1.0e-6
    )
    payload["exact_clean_structure"] = exact
    if require_exact and not exact:
        raise CanonicalRunnerError("canonical541 successful output structure differs from CLEAN1R2R1")
    return payload


def _expected_solver_inputs(method_bound_manifest: Mapping[str, Any]) -> dict[str, Path]:
    actual = method_bound_manifest.get("actual_solver_inputs")
    flags = method_bound_manifest.get("effective_flags")
    if not isinstance(actual, Mapping) or not isinstance(flags, Mapping):
        raise CanonicalRunnerError("method-bound input manifest is incomplete")
    expected = {
        "propagation_imu": Path(str(actual["imu"])).resolve(strict=True),
        "gnss_position_receiver_velocity_dual_yaw": Path(str(actual["gnss"])).resolve(strict=True),
    }
    if _as_bool(flags.get("raw_doppler")):
        expected["raw_doppler_velocity"] = Path(str(actual["raw_doppler"])).resolve(strict=True)
    if _as_bool(flags.get("go2_rp")):
        expected["go2_roll_pitch_weak_prior"] = Path(str(actual["go2_rp"])).resolve(strict=True)
    if _as_bool(flags.get("go2_hv")):
        expected["go2_horizontal_velocity_weak_prior"] = Path(str(actual["go2_hv"])).resolve(strict=True)
    recorded = method_bound_manifest.get("actual_solver_input_hashes")
    role_map = {
        "propagation_imu": "imu",
        "gnss_position_receiver_velocity_dual_yaw": "gnss",
        "raw_doppler_velocity": "raw_doppler",
        "go2_roll_pitch_weak_prior": "go2_rp",
        "go2_horizontal_velocity_weak_prior": "go2_hv",
    }
    if not isinstance(recorded, Mapping):
        raise CanonicalRunnerError("method-bound actual input hashes missing")
    for role, path in expected.items():
        if sha256_file(path) != recorded.get(role_map[role]):
            raise CanonicalRunnerError(f"method-bound input byte hash drift: {role}")
    return expected


def validate_solver_manifest(
    *, profile: MethodProfile, case_id: str, run_id: str,
    manifest: Mapping[str, Any], method_bound_manifest: Mapping[str, Any],
) -> dict[str, Path]:
    expected_values = {
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID,
        "port_role": "canonical541_formal_controlled_degradation_solver",
        "case_id": case_id, "data_mode": canonical_data_mode(case_id),
        "run_id": run_id, "algorithm_id": runtime_profile_id(profile),
        "clean_final_v23_parity_mode": True,
        "enable_dual_yaw_update": profile.flags["dual_yaw"],
        "enable_receiver_velocity_update": profile.flags["receiver_velocity"],
        "enable_raw_doppler": profile.flags["raw_doppler"],
        "source_aware_weighting_enabled": profile.flags["source_aware"],
        "go2_attitude_weak_prior_enabled": profile.flags["go2_rp"],
        "go2_horizontal_velocity_prior_enabled": profile.flags["go2_hv"],
        "yaw_scheme_C_enabled": profile.flags["scheme_c"],
        "trace_used_online": False, "synthetic_data_used": False,
        "semisynthetic_data_used": False, "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False, "LegSA_output_solver_input": False,
        "per_case_tuning": False, "output_only_correction": False,
        "epoch_deleted_for_metric": False, "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0, "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0, "enable_qa_fallback": False,
        "qa_active_mode": False, "enable_multi_state_qm": False,
        "selected_fgo_feedback": False, "no_feedback_fgo": False,
        "active_nine_factor_fgo": False, "contact_fk_factor": False,
        "go2_body_state_not_truth": True, "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False, "go2_yaw_truth_claim": False,
        "go2_contact_truth_claim": False,
    }
    mismatches = [key for key, value in expected_values.items() if manifest.get(key) != value]
    if mismatches:
        raise CanonicalRunnerError("solver manifest contract mismatch: " + ",".join(sorted(mismatches)))
    paths = manifest.get("actual_solver_input_paths")
    roles = manifest.get("actual_solver_input_roles")
    expected_paths = _expected_solver_inputs(method_bound_manifest)
    if not isinstance(paths, Mapping) or not isinstance(roles, Mapping) or set(paths) != set(roles):
        raise CanonicalRunnerError("solver actual-input path/role ledger is incomplete")
    if set(paths) != set(expected_paths):
        raise CanonicalRunnerError("solver actual-input roles differ from method-bound inputs")
    for role, expected in expected_paths.items():
        if Path(str(paths[role])).resolve(strict=True) != expected:
            raise CanonicalRunnerError(f"solver actual input path mismatch: {role}")
    return expected_paths


def validate_method_counters(profile: MethodProfile, manifest: Mapping[str, Any]) -> dict[str, int]:
    counters = module_counters(manifest)
    active = {
        "dual_yaw": counters["dual_yaw_attempt_count"] > 0,
        "receiver_velocity": counters["receiver_velocity_update_count"] > 0,
        "raw_doppler": counters["raw_doppler_update_count"] > 0,
        "source_aware": counters["source_aware_evaluation_count"] > 0,
        "go2_rp": counters["go2_roll_pitch_update_count"] > 0,
        "go2_hv": counters["go2_horizontal_velocity_update_count"] > 0,
    }
    expected = {key: bool(profile.flags[key]) for key in active}
    if counters["position_update_count"] <= 0 or active != expected:
        raise CanonicalRunnerError(f"module counters do not match effective flags: {profile.method_id}")
    if counters["dual_yaw_attempt_count"] != (
        counters["dual_yaw_normal_count"] + counters["dual_yaw_downweight_count"]
        + counters["dual_yaw_reject_count"]
    ):
        raise CanonicalRunnerError("Scheme-C normal/downweight/reject counts do not close")
    if not profile.flags["source_aware"] and counters["source_aware_weight_changed_count"] != 0:
        raise CanonicalRunnerError("source-aware changed weights while disabled")
    for field in ("fgo_count", "qm_count", "qa_count", "contact_fk_count"):
        if counters[field] != 0:
            raise CanonicalRunnerError(f"out-of-scope counter is nonzero: {field}")
    return counters


def mechanism_evidence(profile: MethodProfile, manifest: Mapping[str, Any],
                       counters: Mapping[str, int]) -> dict[str, Any]:
    updates = manifest.get("source_aware_update_count_by_source")
    rejects = manifest.get("source_aware_reject_count_by_source")
    scales = manifest.get("source_aware_R_scale_p50_p95_max_by_source")
    if not all(isinstance(value, Mapping) for value in (updates, rejects, scales)):
        raise CanonicalRunnerError("source-aware mechanism statistics are missing")
    update_total = sum(int(value) for value in updates.values())
    trace_rows = int(manifest.get("source_aware_trace_rows", 0))
    if trace_rows != update_total or trace_rows != counters["source_aware_evaluation_count"]:
        raise CanonicalRunnerError("source-aware action counts do not close")
    if not profile.flags["source_aware"] and any((trace_rows, sum(int(v) for v in rejects.values()))):
        raise CanonicalRunnerError("source-aware actions occurred while disabled")
    return {
        "scheme_c": {
            "enabled": bool(profile.flags["scheme_c"]),
            "attempt": counters["dual_yaw_attempt_count"],
            "normal": counters["dual_yaw_normal_count"],
            "downweight": counters["dual_yaw_downweight_count"],
            "reject": counters["dual_yaw_reject_count"],
            "accept": counters["dual_yaw_accepted_count"],
        },
        "source_aware": {
            "enabled": bool(profile.flags["source_aware"]),
            "evaluations": counters["source_aware_evaluation_count"],
            "changes": counters["source_aware_weight_changed_count"],
            "updates_by_source": dict(updates), "rejects_by_source": dict(rejects),
            "R_scale_p50_p95_max_by_source": dict(scales),
        },
    }


def audit_solver_file_opens(
    *, strace_path: str | Path, cwd: str | Path, raw_root: str | Path,
    clean_root: str | Path, output_root: str | Path, runtime_config: str | Path,
    expected_inputs: Mapping[str, Path], require_all_inputs: bool,
) -> dict[str, Any]:
    traced = Path(strace_path).resolve(strict=True)
    work = Path(cwd).resolve(strict=True)
    raw = Path(raw_root).resolve(strict=True)
    clean = Path(clean_root).resolve(strict=True)
    output = Path(output_root).resolve(strict=True)
    config = Path(runtime_config).resolve(strict=True)
    opened = parse_strace_openat_paths(traced, cwd=work)
    counts = {role: sum(path == expected for path in opened) for role, expected in expected_inputs.items()}
    missing = sorted(role for role, count in counts.items() if count == 0)
    raw_opens = sorted({str(path) for path in opened if is_within(path, raw)})
    trace_path = (raw / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    trace_count = sum(path == trace_path for path in opened)
    legacy_opens = sorted({str(path) for path in opened if legacy_reason(path) is not None})
    expected_set = set(expected_inputs.values())
    unexpected_clean = sorted({
        str(path) for path in opened
        if is_within(path, clean) and path not in expected_set and path != config
        and not is_within(path, output)
    })
    passed = (
        (not require_all_inputs or not missing) and not raw_opens and not legacy_opens
        and not unexpected_clean and trace_count == 0
    )
    report = {
        "schema_version": "paper_rebuild.canonical541_solver_read_ledger.v1",
        "actual_solver_input_paths": {key: str(value) for key, value in expected_inputs.items()},
        "actual_solver_input_open_counts": counts, "missing_solver_inputs": missing,
        "raw_root_open_count": len(raw_opens), "raw_root_opens": raw_opens,
        "legacy_open_count": len(legacy_opens), "legacy_opens": legacy_opens,
        "unexpected_clean_root_opens": unexpected_clean,
        "trace_open_count": trace_count, "trace_used_online": False,
        "strace_sha256": sha256_file(traced), "passed": passed,
    }
    if not passed:
        raise CanonicalRunnerError("solver file-open audit failed")
    return report


def _system_snapshot() -> dict[str, Any]:
    try:
        import psutil
        virtual = psutil.virtual_memory(); swap = psutil.swap_memory()
        cpu = psutil.cpu_times_percent(interval=None)
        return {
            "available_ram_bytes": int(virtual.available), "swap_used_bytes": int(swap.used),
            "iowait_percent": float(getattr(cpu, "iowait", 0.0)),
            "load_1m": float(os.getloadavg()[0]),
        }
    except Exception:
        return {"available_ram_bytes": None, "swap_used_bytes": None,
                "iowait_percent": None, "load_1m": None}


def _run_monitored(command: Sequence[str], *, cwd: Path, timeout_seconds: float) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    """Run one process group and sample the complete process-tree RSS."""

    argv = [str(value) for value in command]
    child_env = dict(os.environ)
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        child_env[name] = "1"
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", start_new_session=True,
            env=child_env,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(argv, 127, "", f"solver launch failure: {exc}"), {
            "max_rss_bytes": 0, "samples": 0, **_system_snapshot(),
        }
    started = time.monotonic(); max_rss = 0; samples = 0
    min_available: int | None = None; max_iowait: float | None = None; max_swap: int | None = None
    while True:
        try:
            stdout, stderr = process.communicate(timeout=0.25)
            break
        except subprocess.TimeoutExpired:
            samples += 1
            snapshot = _system_snapshot()
            available = snapshot["available_ram_bytes"]; iowait = snapshot["iowait_percent"]; swap = snapshot["swap_used_bytes"]
            if available is not None: min_available = available if min_available is None else min(min_available, available)
            if iowait is not None: max_iowait = iowait if max_iowait is None else max(max_iowait, iowait)
            if swap is not None: max_swap = swap if max_swap is None else max(max_swap, swap)
            try:
                import psutil
                parent = psutil.Process(process.pid)
                processes = [parent, *parent.children(recursive=True)]
                max_rss = max(max_rss, sum(item.memory_info().rss for item in processes if item.is_running()))
            except Exception:
                pass
            if time.monotonic() - started > timeout_seconds:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: stdout, stderr = process.communicate(timeout=5.0)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    stdout, stderr = process.communicate()
                return subprocess.CompletedProcess(argv, 124, stdout, (stderr or "") + "\ncanonical541 solver timeout"), {
                    "max_rss_bytes": max_rss, "samples": samples,
                    "min_available_ram_bytes": min_available, "max_iowait_percent": max_iowait,
                    "max_swap_used_bytes": max_swap,
                }
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr), {
        "max_rss_bytes": max_rss, "samples": samples,
        "min_available_ram_bytes": min_available, "max_iowait_percent": max_iowait,
        "max_swap_used_bytes": max_swap,
    }


def run_unique_execution(
    *, executable: str | Path, runtime_config: str | Path,
    method_bound_manifest: str | Path, output_root: str | Path,
    profile: MethodProfile, case_id: str, run_id: str,
    raw_root: str | Path, clean_root: str | Path, repo_root: str | Path,
    expected_executable_hash: str, expected_runtime_config_hash: str,
    expected_scientific_config_hash: str, expected_method_bound_manifest_hash: str,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    binary = Path(executable).resolve(strict=True)
    config = Path(runtime_config).resolve(strict=True)
    method_manifest_path = Path(method_bound_manifest).resolve(strict=True)
    root = Path(output_root).resolve(strict=False)
    if root.exists():
        existing = {path.resolve(strict=True) for path in root.iterdir()}
        if existing != {config} or config.parent != root or config.name != "CANONICAL541_RUNTIME_CONFIG.yaml":
            raise CanonicalRunnerError("attempt output root contains unexplained pre-launch state")
    else:
        raise CanonicalRunnerError("attempt-owned output root/runtime config must be created before launch")
    if sha256_file(binary) != expected_executable_hash:
        raise CanonicalRunnerError("executable changed immediately before launch")
    if sha256_file(config) != expected_runtime_config_hash:
        raise CanonicalRunnerError("runtime config changed immediately before launch")
    if scientific_runtime_config_hash(config.read_text(encoding="utf-8")) != expected_scientific_config_hash:
        raise CanonicalRunnerError("scientific runtime config hash drifted")
    if sha256_file(method_manifest_path) != expected_method_bound_manifest_hash:
        raise CanonicalRunnerError("method-bound manifest changed immediately before launch")
    method_manifest = json.loads(method_manifest_path.read_text(encoding="utf-8"))
    actual_rendered_hash = actual_rendered_runtime_config_sha256(config.read_text(encoding="utf-8"))
    if method_manifest.get("actual_rendered_runtime_config_sha256") != actual_rendered_hash:
        raise CanonicalRunnerError("actual rendered runtime config hash differs from method binding")
    if (method_manifest.get("method_id") != profile.method_id
            or method_manifest.get("effective_profile") != profile.effective_profile
            or {key: _as_bool(value) for key, value in method_manifest.get("effective_flags", {}).items()}
            != dict(profile.flags)):
        raise CanonicalRunnerError("method-bound manifest/profile identity mismatch")
    expected_inputs = _expected_solver_inputs(method_manifest)
    logs = root / "logs"; logs.mkdir(parents=True, exist_ok=False)
    strace = shutil.which("strace")
    if not strace:
        raise CanonicalRunnerError("strace is required for formal trace-embargo proof")
    trace_log = logs / "SOLVER_FILE_OPEN_TRACE.raw"
    command = [
        strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat",
        "-o", str(trace_log), str(binary), "--config", str(config),
        "--output-dir", str(root), "--debug-update-timeline",
        "--debug-output-dir", str(root), "--debug-max-rows", "1000000",
    ]
    started = time.monotonic()
    completed, resources = _run_monitored(command, cwd=Path(repo_root).resolve(strict=True), timeout_seconds=timeout_seconds)
    runtime_seconds = time.monotonic() - started
    (logs / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (logs / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    failure_class = classify_failure(completed.returncode, completed.stdout, completed.stderr)
    structure = validate_output_structure(root, require_exact=False)
    manifest_path = root / "RUN_MANIFEST.json"
    solver_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    has_partial_state = structure["nav"]["rows"] > 0 or structure["std"]["rows"] > 0
    failure_text = f"{completed.stdout}\n{completed.stderr}".lower()
    explicit_algorithm_failure = (
        solver_manifest is not None and has_partial_state
        and any(token in failure_text for token in (
            "algorithm failure", "filter divergence", "non-finite state",
            "nonfinite state", "covariance failure", "numerical divergence",
        ))
        and "canonical541 solver timeout" not in failure_text
    )
    if completed.returncode == 0:
        missing = [name for name in REQUIRED_SOLVER_OUTPUTS if not (root / name).is_file()]
        if missing:
            terminal_status = "UNEXPLAINED_TECHNICAL_FAILURE"
        elif structure["nav"]["finite"] is not True or structure["std"]["finite"] is not True:
            terminal_status = "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"
        elif structure["exact_clean_structure"] is not True:
            # 中文说明：returncode=0 的有限短输出本身不是算法失败证明；除非
            # runtime 明确发出冻结的 algorithm-state marker，否则 fail closed。
            terminal_status = (
                "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"
                if explicit_algorithm_failure else "UNEXPLAINED_TECHNICAL_FAILURE"
            )
        else:
            terminal_status = "COMPLETED_EVALUABLE"
    elif failure_class in TECHNICAL_FAILURE_CLASSES:
        terminal_status = "TECHNICAL_FAILURE_RETRYABLE"
    elif explicit_algorithm_failure:
        terminal_status = "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"
    else:
        terminal_status = "UNEXPLAINED_TECHNICAL_FAILURE"
    counters: dict[str, int] = {}
    mechanisms: dict[str, Any] = {}
    if solver_manifest is not None:
        validate_solver_manifest(profile=profile, case_id=case_id, run_id=run_id,
                                 manifest=solver_manifest, method_bound_manifest=method_manifest)
        counters = module_counters(solver_manifest)
        if terminal_status == "COMPLETED_EVALUABLE":
            counters = validate_method_counters(profile, solver_manifest)
            mechanisms = mechanism_evidence(profile, solver_manifest, counters)
        forbidden = {field: int(counters.get(field, 0)) for field in ("fgo_count", "qm_count", "qa_count", "contact_fk_count")}
        if any(forbidden.values()):
            raise CanonicalRunnerError("out-of-scope mechanism activated in failed run")
    else:
        forbidden = {field: 0 for field in ("fgo_count", "qm_count", "qa_count", "contact_fk_count")}
    read_ledger = audit_solver_file_opens(
        strace_path=trace_log, cwd=repo_root, raw_root=raw_root, clean_root=clean_root,
        output_root=root, runtime_config=config, expected_inputs=expected_inputs,
        require_all_inputs=terminal_status == "COMPLETED_EVALUABLE",
    )
    (root / "CANONICAL541_SOLVER_READ_LEDGER.json").write_text(
        json.dumps(read_ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    with (root / "CANONICAL541_SOLVER_READ_LEDGER.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("role", "path", "open_count", "sha256"), lineterminator="\n",
        )
        writer.writeheader()
        for role, path in expected_inputs.items():
            writer.writerow({
                "role": role, "path": str(path),
                "open_count": read_ledger["actual_solver_input_open_counts"][role],
                "sha256": sha256_file(path),
            })
    output_hashes = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }
    terminal_failure_type = failure_class
    if terminal_status == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF" and failure_class == "success":
        terminal_failure_type = (
            "nonfinite_algorithm_state"
            if not (structure["nav"]["finite"] and structure["std"]["finite"])
            else "early_termination_short_output"
        )
    elif terminal_status == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF":
        terminal_failure_type = "explicit_algorithm_state_failure"
    first_failure_epoch = structure["nav"]["first_nonfinite_time"]
    if terminal_status == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF" and first_failure_epoch is None:
        # 只有显式算法 marker 的 epoch/time 才能补足 first failure。
        # last finite/time_end 只是 last-known-good boundary，不能冒充失败时刻。
        marker = re.search(
            r"(?:failure[_ ](?:epoch|time)|first_failure_epoch)\s*[:=]\s*"
            r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))",
            failure_text,
        )
        if marker is not None:
            first_failure_epoch = float(marker.group(1))
    if (terminal_status == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"
            and (first_failure_epoch is None or not math.isfinite(float(first_failure_epoch)))):
        terminal_status = "UNEXPLAINED_TECHNICAL_FAILURE"
        terminal_failure_type = "algorithm_failure_epoch_unlocated"
    proof = {
        "schema_version": "paper_rebuild.canonical541_execution_proof.v1",
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID,
        "case_id": case_id, "run_id": run_id, "method_id": profile.method_id,
        "effective_profile": profile.effective_profile, "effective_flags": dict(profile.flags),
        "terminal_status": terminal_status, "returncode": completed.returncode,
        "failure_type": terminal_failure_type,
        "first_failure_epoch": first_failure_epoch,
        "last_finite_state_time": structure["nav"]["last_finite_time"],
        "has_partial_state": has_partial_state, "structure": structure,
        "finite": structure["nav"]["finite"] and structure["std"]["finite"],
        "runtime_seconds": runtime_seconds, "resource_monitor": resources,
        "thread_environment": {
            name: "1" for name in (
                "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
            )
        },
        "executable_hash": expected_executable_hash,
        "runtime_config_hash": expected_runtime_config_hash,
        "runtime_config_path": str(config),
        "scientific_runtime_contract_sha256": expected_scientific_config_hash,
        "actual_rendered_runtime_config_sha256": actual_rendered_hash,
        "method_bound_manifest_hash": expected_method_bound_manifest_hash,
        "method_bound_manifest_path": str(method_manifest_path),
        "actual_solver_input_hashes": {role: sha256_file(path) for role, path in expected_inputs.items()},
        "solver_manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
        "solver_read_ledger": read_ledger, "module_counters": counters,
        "mechanism_evidence": mechanisms, "forbidden_counts": forbidden,
        "trace_used_online": False, "metric_driven_rerun": False,
        "stderr_sha256": sha256_file(logs / "stderr.txt"), "output_hashes_before_proof": output_hashes,
    }
    proof_path = root / "CANONICAL541_EXECUTION_PROOF.json"
    proof_bytes = (json.dumps(proof, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    proof_path.write_bytes(proof_bytes)
    (root / "CANONICAL541_FORMAL_RUN_MANIFEST.json").write_bytes(proof_bytes)
    if sha256_file(binary) != expected_executable_hash or sha256_file(config) != expected_runtime_config_hash:
        raise CanonicalRunnerError("executable/config changed during solver execution")
    return proof


def select_adaptive_jobs(smoke_proofs: Iterable[Mapping[str, Any]], *, hard_max: int = 16) -> dict[str, Any]:
    proofs = tuple(smoke_proofs)
    if len(proofs) != 32:
        raise CanonicalRunnerError("adaptive decision requires exactly 32 formal smoke proofs")
    rss = [int(row.get("resource_monitor", {}).get("max_rss_bytes") or 0) for row in proofs]
    available = [row.get("resource_monitor", {}).get("min_available_ram_bytes") for row in proofs]
    iowait = [row.get("resource_monitor", {}).get("max_iowait_percent") for row in proofs]
    usable_available = [int(value) for value in available if value is not None]
    usable_iowait = [float(value) for value in iowait if value is not None]
    max_rss = max(rss, default=0); min_available = min(usable_available, default=0)
    max_iowait = max(usable_iowait, default=100.0)
    jobs = 8
    if min_available > 8 * 1024**3 and max_rss * 12 < 24 * 1024**3 and max_iowait < 25.0:
        jobs = 12
    if hard_max >= 16 and min_available > 8 * 1024**3 and max_rss * 16 < 25 * 1024**3 and max_iowait < 20.0:
        jobs = 16
    jobs = min(jobs, hard_max, 16)
    return {
        "smoke_run_count": 32, "selected_jobs": jobs, "hard_max": min(hard_max, 16),
        "max_run_rss_bytes": max_rss, "min_available_ram_bytes": min_available,
        "max_iowait_percent": max_iowait, "blas_threads": 1,
    }


def safe_initial_jobs(*, requested: int = 8, hard_max: int = 16) -> int:
    """Lower the initial pool when current available RAM cannot safely host eight."""

    available = _system_snapshot().get("available_ram_bytes")
    if available is None:
        return min(requested, hard_max, 8)
    if available < 5 * 1024**3:
        selected = 2
    elif available < 8 * 1024**3:
        selected = 4
    elif available < 12 * 1024**3:
        selected = 6
    else:
        selected = 8
    return max(1, min(selected, requested, hard_max, 16))


C00_REFERENCE_BY_PROFILE = {
    "single_antenna_EKF": "01_single_antenna_EKF",
    "basic_dual_yaw_EKF": "02_basic_dual_yaw_EKF",
    "AB0000": "03_AB0000",
    "AB1111": "18_AB1111",
    "AB0111": "10_AB0111",
    "AB1011": "14_AB1011",
    "AB1101": "16_AB1101",
    "AB1110": "17_AB1110",
    "AB1100": "15_AB1100",
    "AB1000": "11_AB1000",
    "AB0100": "07_AB0100",
}


def validate_c00_structural_gate(
    *, unique_runs: Iterable[Mapping[str, Any]], logical_rows: Iterable[Mapping[str, Any]],
    clean_ablation_runtime_root: str | Path, stage_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Require AB0000 anchor parity and structural closure for all other C00 profiles."""

    all_unique = [dict(row) for row in unique_runs]
    all_logical = [dict(row) for row in logical_rows]
    unique = [row for row in all_unique if row.get("case_id") == "C00_clean_normal"]
    logical = [row for row in all_logical if row.get("case_id") == "C00_clean_normal"]
    if len(unique) != 11 or len(logical) != 13:
        raise CanonicalRunnerError("C00 gate requires exactly 11 unique / 13 logical rows")
    profiles = {str(row["effective_profile"]): row for row in unique}
    if set(profiles) != set(C00_REFERENCE_BY_PROFILE):
        raise CanonicalRunnerError("C00 effective-profile set differs from frozen eleven")
    anchor = Path(clean_ablation_runtime_root).resolve(strict=True)
    rows: list[dict[str, Any]] = []
    for profile_id, reference_name in C00_REFERENCE_BY_PROFILE.items():
        current_row = profiles[profile_id]
        proof = validate_terminal_output(current_row)
        if proof["terminal_status"] != "COMPLETED_EVALUABLE":
            raise CanonicalRunnerError(f"C00 profile is not evaluable: {profile_id}")
        current = Path(str(current_row["output_root"])).resolve(strict=True)
        current_structure = validate_output_structure(current, require_exact=True)
        current_manifest = json.loads((current / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        if current_manifest.get("port_role") != "canonical541_formal_controlled_degradation_solver":
            raise CanonicalRunnerError(f"C00 canonical role mismatch: {profile_id}")
        profile = MethodProfile(
            str(current_row.get("method_id", profile_id)), profile_id, profile_id,
            {field: _as_bool(current_row[field]) for field in FEATURE_FIELDS},
        )
        counters = validate_method_counters(profile, current_manifest)
        is_parity_anchor = profile_id == "AB0000"
        nav_equal: bool | None = None
        std_equal: bool | None = None
        reference_rows: int | None = None
        if is_parity_anchor:
            reference = (anchor / reference_name).resolve(strict=True)
            reference_structure = validate_output_structure(reference, require_exact=True)
            nav_equal = sha256_file(current / "KF_GINS_Navresult.nav") == sha256_file(reference / "KF_GINS_Navresult.nav")
            std_equal = sha256_file(current / "KF_GINS_STD.txt") == sha256_file(reference / "KF_GINS_STD.txt")
            reference_rows = int(reference_structure["nav"]["rows"])
        structural_passed = (
            current_structure["nav"]["finite"] is True
            and current_structure["std"]["finite"] is True
            and current_structure["exact_clean_structure"] is True
            and bool(counters)
        )
        row = {
            "effective_profile": profile_id, "run_id": current_row["run_id"],
            "reference_run": reference_name if is_parity_anchor else None,
            "parity_required": is_parity_anchor,
            "nav_bit_identical": nav_equal, "std_bit_identical": std_equal,
            "module_counters_valid": True,
            "current_rows": current_structure["nav"]["rows"],
            "reference_rows": reference_rows,
            "finite_outputs": True,
            "passed": structural_passed and (not is_parity_anchor or (nav_equal is True and std_equal is True)),
        }
        rows.append(row)
    by_logical = {(str(row["matrix"]), str(row["method_id"])): row for row in logical}
    alias_pairs = (("internal_ablation", "A01", "full_algorithm", "F04"),
                   ("internal_ablation", "A02", "full_algorithm", "F03"))
    alias_exact = all(
        by_logical[(lm, lid)]["run_id"] == by_logical[(rm, rid)]["run_id"]
        and _as_bool(by_logical[(lm, lid)]["execution_alias"])
        for lm, lid, rm, rid in alias_pairs
    )
    trace_open_count = sum(
        int(row.get("solver_read_ledger", {}).get("trace_open_count", 0))
        for row in (validate_terminal_output(item) for item in unique)
    )
    run_case = {str(row["run_id"]): str(row["case_id"]) for row in all_unique}
    degraded_attempts: set[str] = set()
    stage = validate_attempt_root(stage_root)
    for parent in (
        stage / "08_FULL_ALGORITHM_RUNS/.attempts",
        stage / "10_INTERNAL_ABLATION_RUNS/.attempts",
    ):
        if parent.is_dir():
            for run_root in parent.iterdir():
                if run_root.is_dir() and run_case.get(run_root.name) != "C00_clean_normal":
                    degraded_attempts.update(
                        str(path.resolve(strict=True)) for path in run_root.glob("attempt_*") if path.is_dir()
                    )
    for row in all_unique:
        if row.get("case_id") != "C00_clean_normal" and Path(str(row.get("output_root", ""))).is_dir():
            degraded_attempts.add(str(Path(str(row["output_root"])).resolve(strict=True)))
    degraded_attempt_count = len(degraded_attempts)
    report = {
        "schema_version": "paper_rebuild.canonical541_c00_structural_gate.v2_ab0000_only_parity",
        "logical_row_count": len(logical), "unique_run_count": len(unique),
        "c00_logical_count": len(logical),
        "c00_unique_profile_count": len(profiles), "c00_unique_count": len(unique),
        "rows": rows, "full_ablation_aliases_exact": alias_exact,
        "ab0000_parity_only": True,
        "report_only_profile_count": 10,
        "trace_open_count": trace_open_count,
        "trace_opened_for_performance": False, "performance_metrics_read": False,
        "old_performance_reused": False,
        "degraded_attempt_count_before_gate": degraded_attempt_count,
        "passed": (
            alias_exact and all(row["passed"] for row in rows)
            and trace_open_count == 0 and degraded_attempt_count == 0
        ),
    }
    destination = Path(output_path); destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise CanonicalRunnerError("BLOCKED_CANONICAL541_C00_STRUCTURAL_GATE_FAILED")
    return report


def validate_terminal_output(row: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(str(row["output_root"])).resolve(strict=True)
    proof_path = root / "CANONICAL541_EXECUTION_PROOF.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    if proof.get("run_id") != row.get("run_id") or proof.get("terminal_status") not in TERMINAL_STATUSES:
        raise CanonicalRunnerError("unique terminal proof identity/status mismatch")
    if proof.get("trace_used_online") is not False or proof.get("solver_read_ledger", {}).get("trace_open_count") != 0:
        raise CanonicalRunnerError("terminal output violated trace embargo")
    if proof.get("executable_hash") != row.get("executable_hash"):
        raise CanonicalRunnerError("terminal output executable identity mismatch")
    if proof.get("runtime_config_hash") != row.get("runtime_config_file_hash"):
        raise CanonicalRunnerError("terminal output runtime config identity mismatch")
    if proof.get("method_bound_manifest_hash") != row.get("method_bound_manifest_hash"):
        raise CanonicalRunnerError("terminal output method-bound identity mismatch")
    if proof.get("terminal_status") == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF":
        epoch = proof.get("first_failure_epoch")
        if epoch is None or not math.isfinite(float(epoch)):
            raise CanonicalRunnerError("terminal algorithm failure proof lacks finite first_failure_epoch")
        if not proof.get("failure_type") or proof.get("has_partial_state") is not True:
            raise CanonicalRunnerError("terminal algorithm failure proof is incomplete")
    return proof


def seal_unique_outputs(
    unique_runs: Iterable[Mapping[str, Any]], logical_rows: Iterable[Mapping[str, Any]],
    output_dir: str | Path, *, raw_root: str | Path,
    attempt_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    unique = tuple(dict(row) for row in unique_runs)
    logical = tuple(dict(row) for row in logical_rows)
    if not unique or len(logical) != 7033:
        raise CanonicalRunnerError("output seal requires all unique runs and 7033 logical rows")
    by_run: dict[str, dict[str, Any]] = {}
    for row in unique:
        run_id = str(row["run_id"])
        if run_id in by_run:
            raise CanonicalRunnerError("duplicate unique run_id at seal")
        proof = validate_terminal_output(row)
        row["terminal_status"] = proof["terminal_status"]
        by_run[run_id] = row
    for row in logical:
        run_id = str(row.get("run_id", "")); expected = by_run.get(run_id)
        if expected is None:
            raise CanonicalRunnerError("logical row lacks a sealed unique run")
        status = expected["terminal_status"]
        if row.get("terminal_status") not in (status, "PENDING"):
            raise CanonicalRunnerError("logical/unique terminal status mismatch")
        row["terminal_status"] = status
    if len({row["logical_id"] for row in logical}) != 7033:
        raise CanonicalRunnerError("logical output seal has duplicate/missing IDs")
    root = Path(output_dir)
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise CanonicalRunnerError("partial/nonempty output seal exists")
    else:
        root.mkdir(parents=True, exist_ok=False)
    manifest_rows: list[dict[str, Any]] = []
    trace_path = (Path(raw_root).resolve(strict=True) / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    reparsed_trace_open_count = 0
    for run_id in sorted(by_run):
        record = by_run[run_id]; run_root = Path(str(record["output_root"])).resolve(strict=True)
        solver_trace = run_root / "logs/SOLVER_FILE_OPEN_TRACE.raw"
        opened = parse_strace_openat_paths(solver_trace, cwd=Path(str(record["repo_root"])).resolve(strict=True))
        run_trace_count = sum(path == trace_path for path in opened)
        reparsed_trace_open_count += run_trace_count
        proof = json.loads((run_root / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
        if (proof.get("solver_read_ledger", {}).get("strace_sha256") != sha256_file(solver_trace)
                or proof.get("solver_read_ledger", {}).get("trace_open_count") != run_trace_count):
            raise CanonicalRunnerError("solver strace/read-ledger closure failed at seal")
        for path in sorted(candidate for candidate in run_root.rglob("*") if candidate.is_file()):
            manifest_rows.append({
                "run_id": run_id, "run_root": str(run_root),
                "execution_key": record["execution_key"],
                "relative_path": path.relative_to(run_root).as_posix(),
                "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                "terminal_status": record["terminal_status"], "sealed_before_trace": True,
            })
    if not manifest_rows:
        raise CanonicalRunnerError("no output files available to seal")
    manifest = root / "OUTPUT_HASH_MANIFEST.csv"
    with manifest.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(manifest_rows)
    for filename, records in (("UNIQUE_RUN_TERMINAL_REGISTRY.csv", unique),
                              ("LOGICAL_RESULT_TERMINAL_REGISTRY.csv", logical)):
        with (root / filename).open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]), extrasaction="ignore", lineterminator="\n")
            writer.writeheader(); writer.writerows(records)
    attempts = tuple(dict(row) for row in attempt_rows)
    if not attempts:
        raise CanonicalRunnerError("formal run-attempt registry is empty at seal")
    with (root / "RUN_ATTEMPTS.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(attempts[0]), extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(attempts)
    trace_open_count = reparsed_trace_open_count
    journal = {
        "schema_version": "paper_rebuild.canonical541_output_seal.v1",
        "unique_run_count": len(unique), "logical_result_count": len(logical),
        "full_algorithm_logical_rows": sum(row.get("matrix") == "full_algorithm" for row in logical),
        "internal_ablation_logical_rows": sum(row.get("matrix") == "internal_ablation" for row in logical),
        "file_count": len(manifest_rows), "trace_open_count_before_seal": trace_open_count,
        "c00_logical_row_count": sum(row.get("case_id") == "C00_clean_normal" for row in logical),
        "c00_unique_run_count": sum(row.get("case_id") == "C00_clean_normal" for row in unique),
        "common_executable_sha256": next(iter({str(row["executable_hash"]) for row in unique}), ""),
        "all_hashes_recorded": True, "all_logical_rows_terminal": True,
        "sealed_before_offline_trace": trace_open_count == 0,
        "manifest_sha256": sha256_file(manifest),
        "unique_registry_sha256": sha256_file(root / "UNIQUE_RUN_TERMINAL_REGISTRY.csv"),
        "logical_registry_sha256": sha256_file(root / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv"),
        "run_attempts_sha256": sha256_file(root / "RUN_ATTEMPTS.csv"),
        "run_attempt_count": len(attempts),
        "passed": trace_open_count == 0,
    }
    if journal["full_algorithm_logical_rows"] != 2164 or journal["internal_ablation_logical_rows"] != 4869:
        raise CanonicalRunnerError("matrix split did not close at output seal")
    if journal["c00_logical_row_count"] != 13 or journal["c00_unique_run_count"] != 11:
        raise CanonicalRunnerError("C00 logical/unique seal count mismatch")
    if len({str(row["executable_hash"]) for row in unique}) != 1 or len(journal["common_executable_sha256"]) != 64:
        raise CanonicalRunnerError("sealed outputs do not share one executable")
    (root / "OUTPUT_SEAL_JOURNAL.json").write_text(
        json.dumps(journal, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    if not journal["passed"]:
        raise CanonicalRunnerError("trace was opened before output seal")
    return journal


def validate_output_seal(seal_root: str | Path, *, raw_root: str | Path) -> dict[str, Any]:
    root = Path(seal_root).resolve(strict=True)
    journal_path = root / "OUTPUT_SEAL_JOURNAL.json"
    manifest_path = root / "OUTPUT_HASH_MANIFEST.csv"
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    if (
        journal.get("passed") is not True or journal.get("logical_result_count") != 7033
        or journal.get("full_algorithm_logical_rows") != 2164
        or journal.get("internal_ablation_logical_rows") != 4869
        or journal.get("c00_logical_row_count") != 13
        or journal.get("c00_unique_run_count") != 11
        or len(str(journal.get("common_executable_sha256", ""))) != 64
        or journal.get("trace_open_count_before_seal") != 0
        or journal.get("sealed_before_offline_trace") is not True
        or journal.get("manifest_sha256") != sha256_file(manifest_path)
    ):
        raise CanonicalRunnerError("output seal journal contract failed")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle); rows = list(reader)
    required = {"run_id", "run_root", "execution_key", "relative_path", "size_bytes", "sha256", "terminal_status", "sealed_before_trace"}
    if not required.issubset(reader.fieldnames or ()) or len(rows) != journal.get("file_count"):
        raise CanonicalRunnerError("output seal schema/count mismatch")
    unique_registry = root / "UNIQUE_RUN_TERMINAL_REGISTRY.csv"
    logical_registry = root / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv"
    attempts_registry = root / "RUN_ATTEMPTS.csv"
    if (journal.get("unique_registry_sha256") != sha256_file(unique_registry)
            or journal.get("logical_registry_sha256") != sha256_file(logical_registry)
            or journal.get("run_attempts_sha256") != sha256_file(attempts_registry)):
        raise CanonicalRunnerError("terminal registry hashes changed after seal")
    with unique_registry.open("r", encoding="utf-8-sig", newline="") as handle:
        unique_rows = list(csv.DictReader(handle))
    with logical_registry.open("r", encoding="utf-8-sig", newline="") as handle:
        logical_rows = list(csv.DictReader(handle))
    with attempts_registry.open("r", encoding="utf-8-sig", newline="") as handle:
        attempt_rows = list(csv.DictReader(handle))
    if (len(unique_rows) != journal.get("unique_run_count") or len(logical_rows) != 7033
            or len(attempt_rows) != journal.get("run_attempt_count")):
        raise CanonicalRunnerError("terminal registry row counts changed after seal")
    trace_path = (Path(raw_root).resolve(strict=True) / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    reparsed_trace_count = 0
    observed: set[tuple[str, str]] = set()
    for row in rows:
        relative = Path(row["relative_path"])
        if relative.is_absolute() or ".." in relative.parts or row["sealed_before_trace"] != "True":
            raise CanonicalRunnerError("unsafe/unsealed output manifest row")
        path = Path(row["run_root"]).resolve(strict=True) / relative
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or sha256_file(path) != row["sha256"]:
            raise CanonicalRunnerError("sealed output byte closure failed")
        pair = (row["run_id"], row["relative_path"])
        if pair in observed:
            raise CanonicalRunnerError("duplicate output seal row")
        observed.add(pair)
    by_run = {str(row["run_id"]): row for row in unique_rows}
    if len(by_run) != len(unique_rows):
        raise CanonicalRunnerError("terminal unique registry duplicate run_id")
    for run_id, row in by_run.items():
        run_root = Path(str(row["output_root"])).resolve(strict=True)
        proof = json.loads((run_root / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
        if proof.get("terminal_status") == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF":
            epoch = proof.get("first_failure_epoch")
            if epoch is None or not math.isfinite(float(epoch)) or not proof.get("failure_type"):
                raise CanonicalRunnerError("sealed algorithm failure proof fields are incomplete")
        solver_trace = run_root / "logs/SOLVER_FILE_OPEN_TRACE.raw"
        opened = parse_strace_openat_paths(solver_trace, cwd=Path(str(row["repo_root"])).resolve(strict=True))
        reparsed_trace_count += sum(path == trace_path for path in opened)
    for row in rows:
        expected = by_run.get(row["run_id"])
        if (expected is None or row["run_root"] != str(Path(expected["output_root"]).resolve(strict=True))
                or row["execution_key"] != expected["execution_key"]):
            raise CanonicalRunnerError("output seal run-root/execution-key binding failed")
    for row in attempt_rows:
        if not row.get("attempt_root") or not row.get("output_root"):
            raise CanonicalRunnerError("attempt registry lacks exact attempt/output roots")
    if reparsed_trace_count != 0:
        raise CanonicalRunnerError("solver trace embargo failed during seal revalidation")
    return journal
