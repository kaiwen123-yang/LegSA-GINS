"""Source-preserving official-sample and BY2 configuration derivation."""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .constants import (
    BY2_CONFIG_ALLOWED_CHANGES,
    BY2_CONFIG_REQUIRED_UNCHANGED,
    GO2_ALLAN_ASD,
    GO2_ALLAN_PROFILE_ID,
    GO2_ALLAN_PSD,
    GO2_ALLAN_SOURCE,
    GO2_ALLAN_SOURCE_SHA256,
    GO2_SAMPLE_RATE_HZ,
    GO2_SAMPLE_RATE_SOURCE,
    GO2_SAMPLE_RATE_SOURCE_SHA256,
    LEVER_FRD_M,
    LEVER_LABELS,
    LEVER_RFU_M,
    OFFICIAL_NAMED_HASHES,
    SAMPLE_CONFIG_ALLOWED_CHANGES,
)
from .source import sha256_file


class ConfigContractError(ValueError):
    pass


ASSIGNMENT_RE = re.compile(
    r"^(?P<prefix>\s*(?P<key>[A-Za-z0-9_]+)\s*=\s*)"
    r"(?P<value>.*?)(?P<comment>\s+%.*)?(?P<newline>\r?\n)?$"
)


@dataclasses.dataclass(frozen=True)
class ConfigAssignment:
    key: str
    value: str
    line_number: int


def parse_config_text(text: str) -> dict[str, ConfigAssignment]:
    assignments: dict[str, ConfigAssignment] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = ASSIGNMENT_RE.match(line)
        if match is None:
            continue
        key = match.group("key")
        if key in assignments:
            raise ConfigContractError(f"duplicate GINav config key: {key}")
        assignments[key] = ConfigAssignment(key, match.group("value").strip(), line_number)
    if not assignments:
        raise ConfigContractError("GINav config has no assignments")
    return assignments


def parse_config(path: str | Path) -> dict[str, ConfigAssignment]:
    return parse_config_text(Path(path).read_text(encoding="utf-8"))


def _rewrite_config(
    source: Path,
    destination: Path,
    changes: Mapping[str, str],
    allowed: frozenset[str],
) -> tuple[dict[str, Any], ...]:
    if set(changes) - allowed:
        raise ConfigContractError(
            "GINav config change is outside allowlist: "
            + ",".join(sorted(set(changes) - allowed))
        )
    text = source.read_text(encoding="utf-8")
    original = parse_config_text(text)
    missing = set(changes) - set(original)
    if missing:
        raise ConfigContractError("GINav config key is absent: " + ",".join(sorted(missing)))
    output: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines(keepends=True):
        match = ASSIGNMENT_RE.match(raw)
        if match is None or match.group("key") not in changes:
            output.append(raw)
            continue
        key = match.group("key")
        newline = match.group("newline") or ""
        comment = match.group("comment") or ""
        output.append(f"{match.group('prefix')}{changes[key]}{comment}{newline}")
        seen.add(key)
    if seen != set(changes):
        raise ConfigContractError("not every requested GINav config key was rewritten")
    rendered = "".join(output)
    final = parse_config_text(rendered)
    actual_changed = {
        key for key in original if original[key].value != final[key].value
    }
    if not actual_changed.issubset(allowed):
        raise ConfigContractError("rendered GINav config changed a denied field")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8", newline="")
    rows = []
    for key in original:
        rows.append(
            {
                "field": key,
                "official_value": original[key].value,
                "derived_value": final[key].value,
                "changed": key in actual_changed,
                "change_allowed": key in allowed,
                "official_line": original[key].line_number,
            }
        )
    return tuple(rows)


def derive_official_sample_config(
    official_config: str | Path,
    destination: str | Path,
    data_directory: str | Path,
) -> dict[str, Any]:
    source = Path(official_config).resolve(strict=True)
    if sha256_file(source) != OFFICIAL_NAMED_HASHES[
        "conf/LC/GINav_SPP_LC_CPT.ini"
    ]:
        raise ConfigContractError("official sample config hash mismatch")
    data = Path(data_directory).resolve(strict=True)
    if any(character.isspace() for character in str(data)):
        raise ConfigContractError("official decode_cfg cannot consume a spaced data_dir")
    rows = _rewrite_config(
        source, Path(destination), {"data_dir": str(data)},
        SAMPLE_CONFIG_ALLOWED_CHANGES,
    )
    changed = [row["field"] for row in rows if row["changed"]]
    if changed != ["data_dir"]:
        raise ConfigContractError(
            "official sample config must change data_dir and no other field"
        )
    return {
        "schema_version": "ginav2021.official_sample_config_contract.v1",
        "official_config_sha256": sha256_file(source),
        "derived_config_sha256": sha256_file(destination),
        "allowed_changes": sorted(SAMPLE_CONFIG_ALLOWED_CHANGES),
        "actual_changed_fields": changed,
        "algorithm_mode_changed": False,
        "navigation_system_changed": False,
        "frequency_changed": False,
        "noise_or_lever_changed": False,
        "sample_rate_or_robust_settings_changed": False,
        "time_interval_or_initialization_changed": False,
        "diff_rows": list(rows),
        "pass": True,
    }


def lever_frd_to_rfu(lever_frd_m: Sequence[float]) -> tuple[float, float, float]:
    if len(lever_frd_m) != 3:
        raise ConfigContractError("lever must have three components")
    forward, right, down = (float(value) for value in lever_frd_m)
    # GINav RFU order is [R,F,U].
    return right, forward, -down


def _verify_project_parameter_sources(repository_root: str | Path) -> dict[str, str]:
    root = Path(repository_root).resolve(strict=True)
    expected = {
        GO2_SAMPLE_RATE_SOURCE: GO2_SAMPLE_RATE_SOURCE_SHA256,
        GO2_ALLAN_SOURCE: GO2_ALLAN_SOURCE_SHA256,
    }
    verified: dict[str, str] = {}
    for relative, expected_hash in expected.items():
        file_relative = relative.split("#", 1)[0]
        source = (root / file_relative).resolve(strict=True)
        if root not in source.parents or sha256_file(source) != expected_hash:
            raise ConfigContractError(
                f"project-authenticated parameter source mismatch: {relative}"
            )
        verified[relative] = expected_hash
    return verified


def allan_psd_mapping(
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    calculated = {
        "psd_gyro": GO2_ALLAN_ASD["gyro_measurement_white_noise_density"] ** 2,
        "psd_acce": GO2_ALLAN_ASD["accelerometer_measurement_white_noise_density"] ** 2,
        "psd_bg": GO2_ALLAN_ASD["gyro_bias_random_walk_density"] ** 2,
        "psd_ba": GO2_ALLAN_ASD["accelerometer_bias_random_walk_density"] ** 2,
    }
    for key, expected in GO2_ALLAN_PSD.items():
        if not math.isclose(calculated[key], expected, rel_tol=1e-15, abs_tol=0.0):
            raise ConfigContractError(f"Allan ASD-to-PSD mapping mismatch for {key}")
    verified_sources = (
        _verify_project_parameter_sources(repository_root)
        if repository_root is not None else None
    )
    return {
        "profile_id": GO2_ALLAN_PROFILE_ID,
        "source_role": "PROJECT_AUTHENTICATED_GO2_ALLAN_CONTINUOUS_NOISE_PROFILE",
        "source_path": GO2_ALLAN_SOURCE,
        "source_sha256": GO2_ALLAN_SOURCE_SHA256,
        "user_thesis_opened_by_this_route": False,
        "continuous_asd": dict(GO2_ALLAN_ASD),
        "continuous_psd": dict(calculated),
        "mapping_rule": "square_each_continuous_ASD_exactly_once",
        "sqrt_dt_preprocessing": False,
        "dt_preprocessing_before_GINav_Qc": False,
        "bias_instability_values_used_as_process_psd": False,
        "project_parameter_source_hashes_verified": verified_sources,
    }


def _format_time(value: dt.datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y/%m/%d %H:%M:%S")


def derive_by2_config(
    official_config: str | Path,
    destination: str | Path,
    *,
    data_directory: str | Path,
    site_name: str,
    start_time_gpst: dt.datetime,
    end_time_gpst: dt.datetime,
    navsys: str,
    nfreq: int,
    project_repository_root: str | Path,
) -> dict[str, Any]:
    source = Path(official_config).resolve(strict=True)
    if sha256_file(source) != OFFICIAL_NAMED_HASHES[
        "conf/LC/GINav_SPP_LC_CPT.ini"
    ]:
        raise ConfigContractError("official BY2 base-config hash mismatch")
    data = Path(data_directory).resolve(strict=True)
    if any(character.isspace() for character in str(data)):
        raise ConfigContractError("decode_cfg cannot consume a spaced BY2 data_dir")
    if not site_name or any(character.isspace() for character in site_name):
        raise ConfigContractError("site_name must be one nonempty token")
    if start_time_gpst > end_time_gpst:
        raise ConfigContractError("BY2 config start time is after end time")
    if not navsys or any(system not in "GRECJ" for system in navsys):
        raise ConfigContractError("BY2 navsys is outside GINav support")
    if not 1 <= nfreq <= 3:
        raise ConfigContractError("BY2 nfreq is outside GINav support")
    if lever_frd_to_rfu(LEVER_FRD_M) != LEVER_RFU_M:
        raise ConfigContractError("frozen FRD-to-RFU lever mapping failed")
    verified_parameter_sources = _verify_project_parameter_sources(
        project_repository_root
    )
    allan = allan_psd_mapping(project_repository_root)
    changes = {
        "data_dir": str(data),
        "site_name": site_name,
        "start_time": "1  " + _format_time(start_time_gpst),
        "end_time": "1  " + _format_time(end_time_gpst),
        "navsys": navsys,
        "nfreq": str(nfreq),
        "data_format": "2",
        "sample_rate": str(GO2_SAMPLE_RATE_HZ),
        "lever": ",".join(f"{value:.2f}" for value in LEVER_RFU_M),
        **{key: f"{value:.16g}" for key, value in GO2_ALLAN_PSD.items()},
    }
    rows = _rewrite_config(
        source, Path(destination), changes, BY2_CONFIG_ALLOWED_CHANGES
    )
    original = parse_config(source)
    final = parse_config(destination)
    for key, expected in BY2_CONFIG_REQUIRED_UNCHANGED.items():
        if original[key].value.replace(" ", "") != expected or final[key].value.replace(" ", "") != expected:
            raise ConfigContractError(f"required official config field changed: {key}")
    changed = [row["field"] for row in rows if row["changed"]]
    if not set(changed).issubset(BY2_CONFIG_ALLOWED_CHANGES):
        raise ConfigContractError("BY2 config diff exceeds allowlist")
    provenance = {
        "data_dir": "runtime_source_explicit_scratch",
        "site_name": "dataset_identifier_BY2_GNSS1",
        "start_time": "prepared_RINEX_and_Go2_overlap_before_navigation",
        "end_time": "prepared_RINEX_and_Go2_overlap_before_navigation",
        "navsys": "RINEX_observation_broadcast_ephemeris_inventory",
        "nfreq": (
            "pinned_official_config_nfreq_1_with_prange_P_1_and_"
            "tdcp_current_previous_L_1_consumers;_audited_maximum_"
            "contiguous_slots_is_diagnostic_only"
        ),
        "data_format": "official_readimu_format2_current_sample_times_dt",
        "sample_rate": GO2_SAMPLE_RATE_SOURCE,
        "lever": "frozen_rough_project_lever_FRD_to_GINav_RFU",
        "psd_gyro": GO2_ALLAN_PROFILE_ID,
        "psd_acce": GO2_ALLAN_PROFILE_ID,
        "psd_bg": GO2_ALLAN_PROFILE_ID,
        "psd_ba": GO2_ALLAN_PROFILE_ID,
    }
    for row in rows:
        row["provenance"] = provenance.get(row["field"], "unchanged_official_config")
    return {
        "schema_version": "ginav2021.by2_config_contract.v1",
        "base_config": "conf/LC/GINav_SPP_LC_CPT.ini",
        "base_config_sha256": sha256_file(source),
        "derived_config_sha256": sha256_file(destination),
        "allowed_change_fields": sorted(BY2_CONFIG_ALLOWED_CHANGES),
        "actual_changed_fields": changed,
        "gnss_mode": 1,
        "ins_mode": 1,
        "ins_aid": [0, 1],
        "official_robust_path_unchanged": True,
        "innovation_and_rejection_thresholds_unchanged": True,
        "filter_core_feedback_reset_unchanged": True,
        "initial_state_uncertainties_unchanged": True,
        "imu_data_format": 2,
        "imu_increment_policy": "current_sample_times_dt",
        "sample_rate_hz": GO2_SAMPLE_RATE_HZ,
        "sample_rate_source": GO2_SAMPLE_RATE_SOURCE,
        "sample_rate_source_sha256": GO2_SAMPLE_RATE_SOURCE_SHA256,
        "lever": {
            "frd_m": list(LEVER_FRD_M),
            "rfu_m": list(LEVER_RFU_M),
            **LEVER_LABELS,
        },
        "imu_stochastic": allan,
        "verified_project_parameter_sources": verified_parameter_sources,
        "diff_rows": list(rows),
        "trace_tuned": False,
        "performance_selected_parameter_count": 0,
        "pass": True,
    }
