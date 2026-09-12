"""C-04 output validation against frozen configuration and native solver evidence.

No reference data, evaluator, provider generation, or numerical correction is used.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import yaml

from .profile_expectations import profile_flags
from .runtime_config import (BACKEND_PROVENANCE_KEYS, METHODS, NATIVE_IDENTITY,
                             RuntimeConfigError, frozen_parameter_hash,
                             scientific_runtime_config_hash)


class SolverValidationError(RuntimeError):
    terminal_status = "technical_failure"


class AlgorithmFailure(SolverValidationError):
    terminal_status = "algorithm_failure"


class CounterMismatch(SolverValidationError):
    terminal_status = "counter_mismatch"

    def __init__(self, message: str, *, counters=None):
        super().__init__(message)
        self.counters = dict(counters or {})


# Sources: file_saver.cpp:928-964; port_runtime.cpp:122-144.
COUNTER_SOURCES = {
    "position_update_count": "position_update_count",
    "receiver_velocity_update_count": "receiver_velocity_update_count",
    "dual_yaw_attempt_count": "dual_yaw_attempt_count",
    "dual_yaw_normal_count": "yaw_NORMAL",
    "dual_yaw_downweight_count": "yaw_DOWNWEIGHT",
    "dual_yaw_reject_count": "yaw_REJECT",
    "dual_yaw_accepted_count": "dual_yaw_accepted_count",
    "raw_doppler_update_count": "raw_doppler_update_count",
    "source_aware_evaluation_count": "source_aware_evaluation_count",
    "source_aware_weight_changed_count": "source_aware_weight_changed_count",
    "go2_roll_pitch_update_count": "go2_roll_pitch_update_count",
    "go2_horizontal_velocity_update_count": "go2_horizontal_velocity_update_count",
    "selected_fgo_feedback_update_count": "selected_fgo_feedback_update_count",
    "nine_factor_fgo_update_count": "nine_factor_fgo_update_count",
    "qm_count": "multi_state_qm_update_count",
    "qa_count": "qa_fallback_count",
    "contact_fk_count": "contact_fk_update_count",
}
FORBIDDEN_FLAGS = (
    "trace_used_online", "trace_solver_input", "synthetic_data_used", "semisynthetic_data_used",
    "receiver_imu_as_body_imu", "final_v23_output_solver_input", "LegSA_output_solver_input",
    "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric",
    "enable_qa_fallback", "qa_active_mode", "enable_multi_state_qm", "selected_fgo_feedback",
    "no_feedback_fgo", "active_nine_factor_fgo", "contact_fk_factor",
)
ZERO_INPUT_COUNTS = ("old_runtime_input_count", "legacy_provider_input_count",
                     "legacy_row_input_count", "legacy_aggregate_input_count")
CONFIG_FLAG_TO_MANIFEST = {
    "enable_dual_yaw": "enable_dual_yaw_update",
    "enable_receiver_velocity": "enable_receiver_velocity_update",
    "enable_raw_doppler": "enable_raw_doppler",
    "enable_source_aware": "source_aware_weighting_enabled",
    "enable_go2_roll_pitch_prior": "go2_attitude_weak_prior_enabled",
    "enable_go2_horizontal_velocity_prior": "go2_horizontal_velocity_prior_enabled",
}
REQUIRED_NATIVE_OUTPUTS = ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "RUN_MANIFEST.json")


def _mapping(text: str) -> dict[str, Any]:
    # The flat frozen native configuration cannot contain duplicate YAML keys.
    class UniqueLoader(yaml.SafeLoader):
        pass

    def construct(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in result:
                raise RuntimeConfigError(f"duplicate runtime key: {key}")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct)
    value = yaml.load(text, Loader=UniqueLoader)
    if not isinstance(value, dict):
        raise RuntimeConfigError("runtime configuration is not a mapping")
    json.dumps(value, allow_nan=False)
    return value


def validate_outputpath_only(rendered_text: str, bound_text: str) -> None:
    """Reject additions, removals, type changes, or values outside outputpath."""
    before, after = _mapping(rendered_text), _mapping(bound_text)
    if "outputpath" not in before or set(before) != set(after):
        raise RuntimeConfigError("binding changed runtime configuration keys")
    changed = [key for key in before if key != "outputpath" and
               json.dumps(before[key], sort_keys=True, allow_nan=False) !=
               json.dumps(after[key], sort_keys=True, allow_nan=False)]
    if changed:
        raise RuntimeConfigError("binding changed keys outside outputpath", details=changed)


def bind_output_config(rendered_text: str, output_dir: str | Path,
                       expected_frozen_hash: str) -> tuple[str, dict[str, str]]:
    """Replace the single native output line without reserializing other fields."""
    _mapping(rendered_text)
    if frozen_parameter_hash(rendered_text) != expected_frozen_hash:
        raise RuntimeConfigError("rendered frozen_parameter_hash differs from C-03")
    root = Path(output_dir)
    if not root.is_absolute():
        raise RuntimeConfigError("bound outputpath must be absolute")
    seen, lines = 0, []
    for line in rendered_text.splitlines(keepends=True):
        if line.startswith("outputpath:"):
            seen += 1
            newline = "\n" if line.endswith("\n") else ""
            line = "outputpath: " + json.dumps(str(root), ensure_ascii=False) + newline
        lines.append(line)
    if seen != 1:
        raise RuntimeConfigError("binding requires exactly one top-level outputpath")
    bound = "".join(lines)
    validate_outputpath_only(rendered_text, bound)
    frozen, scientific = frozen_parameter_hash(bound), scientific_runtime_config_hash(bound)
    if frozen != expected_frozen_hash or scientific != scientific_runtime_config_hash(rendered_text):
        raise RuntimeConfigError("outputpath binding changed a normalized configuration hash")
    return bound, {"config_hash": hashlib.sha256(bound.encode()).hexdigest(),
                   "scientific_runtime_config_hash": scientific, "frozen_parameter_hash": frozen}


def _numeric_rows(path: Path, minimum_columns: int) -> list[list[float]]:
    if path.is_symlink() or not path.is_file():
        raise SolverValidationError(f"missing or symlink output: {path.name}")
    rows = []
    with path.open(encoding="utf-8", errors="strict") as handle:
        for number, line in enumerate(handle, 1):
            text = line.strip()
            if not text or text.startswith(("#", "%")):
                continue
            try:
                row = [float(item) for item in text.replace(",", " ").split()]
            except ValueError as exc:
                raise SolverValidationError(f"nonnumeric output row: {path.name}:{number}") from exc
            if len(row) < minimum_columns or (rows and len(row) != len(rows[0])):
                raise SolverValidationError(f"invalid column count: {path.name}:{number}")
            if not all(math.isfinite(value) for value in row):
                raise AlgorithmFailure(f"non-finite output: {path.name}:{number}")
            rows.append(row)
    if not rows:
        raise SolverValidationError(f"empty numeric output: {path.name}")
    return rows


def validate_run_outputs(run_dir: str | Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(run_dir)
    for name in REQUIRED_NATIVE_OUTPUTS:
        if (root / name).is_symlink() or not (root / name).is_file():
            raise SolverValidationError(f"missing or symlink required output: {name}")
    nav = _numeric_rows(root / REQUIRED_NATIVE_OUTPUTS[0], 10)
    std = _numeric_rows(root / REQUIRED_NATIVE_OUTPUTS[1], 10)
    time_index = 1 if len(nav[0]) == 11 else 0
    times = [row[time_index] for row in nav]
    start, end = (float(contract["window_contract"][key]) for key in ("t_start", "t_end"))
    if not math.isfinite(start) or not math.isfinite(end) or start >= end:
        raise SolverValidationError("invalid contract time interval")
    if any(right <= left for left, right in zip(times, times[1:])):
        raise AlgorithmFailure("NAV time is not strictly increasing")
    if times[0] < start or times[-1] > end:
        raise AlgorithmFailure("NAV time lies outside frozen sequence window")
    if len(std) != len(nav) or any(row[0] != time for row, time in zip(std, times)):
        raise SolverValidationError("STD rows/time do not match NAV")
    files = list(REQUIRED_NATIVE_OUTPUTS)
    optional = root / "PORT_GNSS_UPDATE_TRACE.csv"
    if optional.is_symlink():
        raise SolverValidationError("symlink GNSS update trace")
    if optional.is_file():
        files.append(optional.name)
    return {"nav_rows": len(nav), "std_rows": len(std), "nav_columns": len(nav[0]),
            "std_columns": len(std[0]), "nav_time_start": times[0], "nav_time_end": times[-1],
            "time_start": times[0], "time_end": times[-1], "finite": True, "output_files": files}


def _strict_count(value: Any, key: str) -> int:
    if type(value) is not int or value < 0:
        raise CounterMismatch(f"counter must be a present nonnegative integer: {key}")
    return value


def native_loader_string(config: Mapping[str, Any] | str, key: str) -> str:
    """Reproduce port_config_loader.cpp normalizeLine/readKeyValues/stringOrDefault.

    The production caller supplies bound raw YAML. Mapping input uses the C-03
    JSON-literal serialization for the selected value, for synthetic fixtures.
    Whitespace, comma removal, comment stripping and outer quote removal are
    intentionally the native parser's literal behavior, not JSON decoding.
    """
    if isinstance(config, str):
        lines = config.splitlines()
    else:
        if key not in config:
            raise SolverValidationError(f"native provenance configuration key missing: {key}")
        lines = [key + ": " + json.dumps(config[key], ensure_ascii=False, allow_nan=False)]
    found = None
    whitespace = " \t\r\n\v\f"
    for raw in lines:
        line = raw.split("#", 1)[0].translate(str.maketrans({"[": " ", "]": " ", ",": " "})).strip(whitespace)
        delimiter = line.find("=")
        if delimiter < 0:
            delimiter = line.find(":")
        if delimiter < 0 or line[:delimiter].strip(whitespace) != key:
            continue
        found = line[delimiter + 1:].strip(whitespace)
    if found is None:
        raise SolverValidationError(f"native provenance configuration line missing: {key}")
    if len(found) >= 2 and found[0] == found[-1] and found[0] in {"'", '"'}:
        found = found[1:-1]
    return found


def expected_update_epochs(config: Mapping[str, Any] | str,
                           native_time_audit: Mapping[str, Any],
                           gnss_path: str | Path) -> dict[str, Any]:
    """Derive initialization and eligible GNSS epochs from frozen provider input.

    t_init is the first increment-IMU time >= config.starttime, following the
    native initialization loop. The old native effective_starttime remains a
    separately checked report field; NAV and actual counters never select t_init.
    """
    cfg = _mapping(config) if isinstance(config, str) else dict(config)
    audit = dict(native_time_audit)
    def number(source, key):
        value = source.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise SolverValidationError(f"time audit requires finite number: {key}")
        return float(value)
    start, end = number(cfg, "starttime"), number(cfg, "endtime")
    first_imu, last_imu = number(audit, "first_imu_time"), number(audit, "last_imu_time")
    first_gnss, last_gnss = number(audit, "first_gnss_time"), number(audit, "last_gnss_time")
    effective, effective_end = number(audit, "effective_starttime"), number(audit, "effective_endtime")
    if start >= end or first_imu > last_imu or first_gnss > last_gnss:
        raise SolverValidationError("invalid configured/native time ordering")
    # Native snapshot uses fixed precision(10); reproduce its serialization.
    printed = lambda value: float(format(value, ".10f"))
    expected_fields = {"config_starttime": printed(start), "config_endtime": printed(end),
        "effective_starttime": max(printed(start), first_imu),
        "effective_endtime": min(printed(end), last_imu, last_gnss),
        "overlap_start": effective, "overlap_end": effective_end}
    for key, expected in expected_fields.items():
        if number(audit, key) != expected:
            raise SolverValidationError(f"native time audit is inconsistent with frozen config/input bounds: {key}")
    for flag in ("trace_solver_input", "final_v23_output_solver_input", "paper_performance_claim"):
        if audit.get(flag) is not False:
            raise SolverValidationError(f"native time audit forbidden flag: {flag}")
    provider = Path(gnss_path)
    if "gnsspath" in cfg and Path(str(cfg["gnsspath"])) != provider:
        raise SolverValidationError("eligible-epoch GNSS path differs from bound configuration")
    rows = _numeric_rows(provider, 15)
    if any(len(row) != 15 for row in rows):
        raise SolverValidationError("eligible-epoch count requires frozen GNSS 15-column provider")
    times = [row[0] for row in rows]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise SolverValidationError("GNSS provider time is not strictly increasing")
    if (_strict_count(audit.get("gnss_row_count"), "gnss_row_count") != len(times)
            or first_gnss != printed(times[0]) or last_gnss != printed(times[-1])):
        raise SolverValidationError("native GNSS timeline differs from provider epochs")
    imu_path = cfg.get("imupath")
    if not isinstance(imu_path, str) or not imu_path:
        raise SolverValidationError("initialization epoch requires the bound frozen IMU path")
    imu_rows = _numeric_rows(Path(imu_path), 7)
    if any(len(row) != 7 for row in imu_rows):
        raise SolverValidationError("initialization epoch requires frozen IMU 7-column increments")
    imu_times = [row[0] for row in imu_rows]
    if any(right <= left for left, right in zip(imu_times, imu_times[1:])):
        raise SolverValidationError("IMU provider time is not strictly increasing")
    if (_strict_count(audit.get("imu_row_count"), "imu_row_count") != len(imu_times)
            or first_imu != printed(imu_times[0]) or last_imu != printed(imu_times[-1])):
        raise SolverValidationError("native IMU timeline differs from provider epochs")
    index = next((i for i, value in enumerate(imu_times) if value >= start), None)
    if index is None or index + 1 >= len(imu_times):
        raise SolverValidationError("no aligned IMU initialization sample and following increment")
    t_init = imu_times[index]
    if t_init >= end:
        raise SolverValidationError("aligned IMU initialization does not precede config end")
    previous = imu_times[index - 1] if index else None
    following = imu_times[index + 1]
    aligned_fields = {}
    for key in ("first_aligned_imu_time", "aligned_first_imu_time", "aligned_imu_starttime", "t_init"):
        if key in audit:
            value = number(audit, key)
            if value != printed(t_init):
                raise SolverValidationError(f"native aligned IMU field differs from input-derived t_init: {key}")
            aligned_fields[key] = value
    bracket = None if previous is None else {"start_s": previous, "end_s": t_init,
        "duration_seconds": t_init - previous}
    # C-04b C.1 preregisters the IMU-hole threshold dt > 0.1 s. It is report-only.
    causal_gap = (dict(bracket) if bracket is not None and previous < start < t_init
                  and bracket["duration_seconds"] > 0.1 else None)
    configured = [time for time in times if start <= time <= end]
    eligible = [time for time in times if t_init < time <= end]
    if any(time > effective_end for time in eligible):
        raise SolverValidationError("configured GNSS eligible epochs extend beyond native effective end")
    skipped = [time for time in configured if time <= t_init]
    overlap_count = sum(effective < time <= effective_end for time in times)
    for key in ("gnss_rows_in_overlap", "gnss_rows_after_start_before_end"):
        if _strict_count(audit.get(key), key) != overlap_count:
            raise SolverValidationError(f"native overlap count differs from provider epochs: {key}")
    return {"t_init": t_init, "t_init_source": "frozen increment IMU provider first time >= config.starttime",
        "t_init_rule": "first IMU7.t >= config.starttime", "aligned_imu_row_index": index,
        "previous_imu_time": previous, "next_imu_time": following,
        "next_imu_interval": following - t_init, "imu_provider_rows": len(imu_times),
        "native_aligned_imu_fields": aligned_fields, "initialization_bracketing_interval": bracket,
        "causative_imu_gap": causal_gap, "imu_hole_threshold_seconds": 0.1,
        "imu_hole_threshold_source": "C-04b C.1: dt > 0.1 s, report-only",
        "native_effective_starttime": effective, "effective_starttime": effective,
        "effective_endtime": effective_end,
        "effective_starttime_source": "PORT_INPUT_TIMELINE_SNAPSHOT.json.effective_starttime",
        "effective_starttime_rule": "max(config.starttime, native first_imu_time); report-only for update eligibility",
        "configured_window_rows": len(configured), "expected_update_count": len(eligible),
        "expected_update_rule": "GNSS15.t > t_init and GNSS15.t <= config.endtime",
        "skipped_epoch_times": skipped, "skipped_epoch_count": len(skipped),
        "skipped_epochs": [{"time": time, "reason": "precedes_first_aligned_imu_sample",
            "causative_imu_gap": causal_gap,
            "note": "initialization boundary exclusion; no IMU hole identified" if causal_gap is None else
                    "configured start lies inside the preregistered IMU hole"} for time in skipped],
        "eligible_epoch_times": eligible, "gnss_provider_rows": len(times),
        "expected_count_derived_from_actual_counters": False,
        "expected_count_derived_from_NAV": False}


def validate_nav_alignment(first_nav_time: float, eligibility: Mapping[str, Any]) -> dict[str, Any]:
    """Check the first saved state against the next frozen IMU increment."""
    values = {"first_nav_time": first_nav_time, "t_init": eligibility.get("t_init"),
              "next_imu_time": eligibility.get("next_imu_time"),
              "next_imu_interval": eligibility.get("next_imu_interval")}
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values.values()):
        raise SolverValidationError("NAV initialization alignment requires finite input times")
    t_init, following, interval = values["t_init"], values["next_imu_time"], values["next_imu_interval"]
    if interval <= 0 or following <= t_init or interval != following - t_init:
        raise SolverValidationError("NAV initialization alignment has inconsistent IMU interval")
    difference = abs(first_nav_time - following)
    if first_nav_time <= t_init or difference > interval:
        raise SolverValidationError("NAV first time differs from the next aligned IMU sample by more than one interval")
    return {"passed": True, **values, "absolute_difference_seconds": difference,
            "tolerance_seconds": interval, "tolerance_source": "one following frozen IMU sample interval",
            "t_init_selected_from_NAV": False}



def validate_profile_counters(effective_profile: str, manifest: Mapping[str, Any],
                              expected_gnss_rows: int) -> dict[str, int]:
    if effective_profile not in METHODS.values():
        raise CounterMismatch(f"unknown frozen profile: {effective_profile}")
    n = _strict_count(expected_gnss_rows, "expected_gnss_rows")
    flags = profile_flags(effective_profile)
    counters, errors = {}, []
    for key, source in COUNTER_SOURCES.items():
        value = manifest.get(source)
        try:
            counters[key] = _strict_count(value, source)
        except CounterMismatch as exc:
            errors.append(str(exc))
    if errors:
        raise CounterMismatch("; ".join(errors), counters=counters)
    counters["fgo_count"] = counters["selected_fgo_feedback_update_count"] + counters["nine_factor_fgo_update_count"]
    for source, target in (("yaw_update_count", "dual_yaw_attempt_count"),
                           ("dual_yaw_update_count", "dual_yaw_accepted_count"),
                           ("velocity_update_count", "receiver_velocity_update_count")):
        if source in manifest and (type(manifest[source]) is not int or manifest[source] != counters[target]):
            errors.append(f"native duplicate counter differs: {source}")
    nested = manifest.get("module_update_counts")
    if nested is not None:
        if not isinstance(nested, Mapping):
            errors.append("native module_update_counts is not a mapping")
        else:
            for source, value in nested.items():
                if source not in manifest or type(value) is not int or value != manifest[source]:
                    errors.append(f"native nested counter differs: {source}")
    if counters["position_update_count"] != n:
        errors.append(f"position_update_count != {n}")
    receiver_expected = n if flags["receiver_velocity"] else 0
    if counters["receiver_velocity_update_count"] != receiver_expected:
        errors.append(f"receiver_velocity_update_count != {receiver_expected}")
    yaw = flags["dual_yaw"]
    if counters["dual_yaw_attempt_count"] != (n if yaw else 0):
        errors.append("dual_yaw_attempt_count differs from profile GNSS-row contract")
    if counters["dual_yaw_attempt_count"] != sum(counters[f"dual_yaw_{action}_count"] for action in ("normal", "downweight", "reject")):
        errors.append("dual-yaw action counts do not close")
    if counters["dual_yaw_accepted_count"] != counters["dual_yaw_normal_count"] + counters["dual_yaw_downweight_count"]:
        errors.append("dual-yaw accepted count does not close")
    if yaw and not flags["scheme_c"] and any(counters[f"dual_yaw_{key}_count"] != 0 for key in ("downweight", "reject")):
        errors.append("F02 downweight/reject must both be zero")
    for key, feature in (("raw_doppler_update_count", "raw_doppler"),
                         ("go2_roll_pitch_update_count", "go2_rp"),
                         ("go2_horizontal_velocity_update_count", "go2_hv")):
        if (counters[key] > 0) != flags[feature]:
            errors.append(f"{key} violates frozen profile")
    for key in ("source_aware_evaluation_count", "source_aware_weight_changed_count"):
        if (counters[key] > 0) != flags["source_aware"]:
            errors.append(f"{key} violates frozen profile")
    if counters["source_aware_weight_changed_count"] > counters["source_aware_evaluation_count"]:
        errors.append("Source-Aware changed count exceeds evaluations")
    for key in ("fgo_count", "qm_count", "qa_count", "contact_fk_count"):
        if counters[key] != 0:
            errors.append(f"out-of-scope counter nonzero: {key}")
    if errors:
        raise CounterMismatch("; ".join(errors), counters=counters)
    return counters


def validate_clean5_manifest(manifest: Mapping[str, Any], config: Mapping[str, Any] | str,
                             contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate actual native compatibility identity, independently of wrapper identity."""
    cfg = _mapping(config) if isinstance(config, str) else dict(config)
    identity = contract["identity"]
    if identity.get("dataset_id") not in {"BY2H", "BY2O"}:
        raise SolverValidationError("manifest validation requires CLEAN5 sequence identity")
    if any(cfg.get(key) != value for key, value in NATIVE_IDENTITY.items()):
        raise SolverValidationError("runtime native compatibility identity differs from C-03")
    profile = cfg.get("algorithm_id")
    if profile not in METHODS.values():
        raise SolverValidationError("native algorithm_id is outside five frozen profiles")
    expected = {key: cfg[key] for key in (*NATIVE_IDENTITY, "run_id", "algorithm_id")}
    expected.update({"clean_final_v23_parity_mode": True, "clean1_formal_mode": True,
                     "phase": cfg["stage_id"], "port_role": "clean2r2a_formal_clean_ablation_solver"})
    for key, native in CONFIG_FLAG_TO_MANIFEST.items():
        if type(cfg.get(key)) is not bool:
            raise SolverValidationError(f"configuration missing boolean flag: {key}")
        expected[native] = cfg[key]
    expected.update({key: False for key in FORBIDDEN_FLAGS})
    expected.update({key: 0 for key in ZERO_INPUT_COUNTS})
    mismatch = [key for key, value in expected.items()
                if key not in manifest or type(manifest[key]) is not type(value) or manifest[key] != value]
    if mismatch:
        raise SolverValidationError("solver manifest contract mismatch: " + ",".join(sorted(mismatch)))
    roles = {"propagation_imu": ("imupath", "source_backed_propagation"),
             "gnss_position_receiver_velocity_dual_yaw": ("gnsspath", "validity_gated_measurements")}
    for flag, role, path, purpose in (
        ("enable_raw_doppler", "raw_doppler_velocity", "raw_doppler_factor_path", "source_backed_auxiliary_velocity"),
        ("enable_go2_roll_pitch_prior", "go2_roll_pitch_weak_prior", "go2_attitude_prior_path", "weak_prior_not_truth"),
        ("enable_go2_horizontal_velocity_prior", "go2_horizontal_velocity_weak_prior", "go2_horizontal_velocity_prior_path", "horizontal_weak_prior_not_truth"),
    ):
        if cfg[flag]:
            roles[role] = (path, purpose)
    paths = manifest.get("actual_solver_input_paths")
    actual_roles = manifest.get("actual_solver_input_roles")
    if not isinstance(paths, Mapping) or not isinstance(actual_roles, Mapping) or set(paths) != set(roles) or set(actual_roles) != set(roles):
        raise SolverValidationError("solver input path/role ledger is incomplete or has extra roles")
    for role, (key, purpose) in roles.items():
        if paths[role] != cfg.get(key) or actual_roles[role] != purpose:
            raise SolverValidationError(f"solver input ledger differs from frozen configuration: {role}")
    # The native YAML-like parser replaces brackets and commas before string
    # transport. Its source-file/source-hash values are therefore NOT JSON.
    # Disabled RD statuses do not populate obs/nav/conversion; validate when enabled.
    provenance_keys = set(BACKEND_PROVENANCE_KEYS) if cfg["enable_raw_doppler"] else {
        "raw_doppler_backend_source_files", "raw_doppler_backend_source_hashes", "helper_executable_hash"}
    for key in sorted(provenance_keys):
        actual = manifest.get(key)
        expected_value = native_loader_string(config, key)
        if type(actual) is not str or actual != expected_value:
            raise SolverValidationError(f"native backend provenance mismatch: {key}")
    if cfg["enable_raw_doppler"] and manifest.get("raw_doppler_backend_lineage_proven") is not True:
        raise SolverValidationError("Raw Doppler backend lineage is not proven")
    return {"paths": dict(paths), "roles": dict(actual_roles), "native_identity": {
        key: cfg[key] for key in (*NATIVE_IDENTITY, "run_id", "algorithm_id")},
        "actual_identity": dict(identity), "passed": True}
