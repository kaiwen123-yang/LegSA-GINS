"""Canonical 60-type BY2 degradation specification.

The tracked clean specification remains the declarative source for names and
most parameters.  Four programmatic laws are deliberately bound to the last
effect-validated static generator source, while the master protocol supplies
the newer exact overrides.  No historical provider or result is opened here.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


STAGE_ID = "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX"
DATASET = "BY2"
DATA_MODE = "real_base_controlled_degradation"
DEGRADATION_TYPE_COUNT = 60
SEED_COUNT = 9
DEGRADED_CASE_COUNT = 540
CASE_COUNT = 541
CLEAN_CASE_ID = "C00_clean_normal"
WINDOW_START_S = 66.0
WINDOW_END_S = 340.0

ALL_SOURCE_IDS = (
    "imu",
    "gnss_position",
    "gnss_position_std",
    "gnss_status_quality_flags",
    "receiver_velocity",
    "receiver_velocity_std",
    "dual_yaw",
    "dual_yaw_std",
    "dual_yaw_quality",
    "raw_doppler_velocity",
    "raw_doppler_std",
    "go2_roll_pitch_weak_prior",
    "go2_horizontal_velocity_weak_prior",
    "go2_source_metadata",
)

PRESERVED_SOURCE_COMMIT = "2f02424237071444dc54406c6437209b528948ec"
PRESERVED_SOURCE_PATH = "scripts/paper10m1r2b_generate_by2_degraded_providers.py"
PRESERVED_SOURCE_SHA256 = "1f908cb45b21bc482838a00e4ae3c192957e2a5af6fdaf23a106b15333971826"


def verify_preserved_generator_source(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Bind layer-3 laws to the real preserved Git blob, never a declared constant."""

    repo = Path(repo_root).resolve(strict=True) if repo_root else repo_root_from_module()
    object_spec = f"{PRESERVED_SOURCE_COMMIT}:{PRESERVED_SOURCE_PATH}"
    try:
        content = subprocess.run(
            ["git", "show", object_spec], cwd=repo, capture_output=True, check=True,
        ).stdout
        object_id = subprocess.run(
            ["git", "rev-parse", object_spec], cwd=repo, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CanonicalSpecError("preserved generator Git object is unavailable") from exc
    actual = hashlib.sha256(content).hexdigest()
    if actual != PRESERVED_SOURCE_SHA256 or len(object_id) != 40:
        raise CanonicalSpecError("preserved generator Git object SHA256 mismatch")
    return {
        "commit": PRESERVED_SOURCE_COMMIT, "path": PRESERVED_SOURCE_PATH,
        "git_object_id": object_id, "sha256": actual, "verified": True,
        "runtime_performance_payload_read": False,
    }
EXTERNAL_SOURCE_SPEC_SHA256 = "44c1d68b2d2bac34aa1f61d692e85aaab4cd03c5bec178291d8e7b822cd1a24a"


class CanonicalSpecError(ValueError):
    """The matrix is not the exact 60 x 9 + clean contract."""


@dataclass(frozen=True)
class DegradationType:
    type_id: str
    name: str
    family: str
    parameters: Mapping[str, Any]
    affected_sources: tuple[str, ...]
    claim_level: str = "controlled_degradation_descriptive"
    effect_validation_rule_id: str = ""

    @property
    def requires_randomness(self) -> bool:
        return self.type_id not in DETERMINISTIC_TYPES


# Cases with no random draw.  Their anchors still differ by seed, so provider
# bytes can differ when an interval is placed at a different source-only anchor.
DETERMINISTIC_TYPES = frozenset(
    {
        "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10",
        "D23", "D24", "D25", "D26", "D28", "D29", "D30", "D31",
        "D36", "D37", "D42", "D46",
    }
)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[4]


def _yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CanonicalSpecError(f"YAML root is not a mapping: {path}")
    return payload


def _normalized_sources(values: Iterable[str]) -> tuple[str, ...]:
    aliases = {
        "gnss_position_std": "gnss_position_std",
        "GNSS position STD": "gnss_position_std",
        "gnss_status_quality_flags": "gnss_status_quality_flags",
        "dual_yaw_STD": "dual_yaw_std",
        "raw_doppler": "raw_doppler_velocity",
        "raw_doppler_and_receiver_velocity": "raw_doppler_velocity",
        "Go2 roll/pitch weak prior": "go2_roll_pitch_weak_prior",
        "Go2 horizontal velocity weak prior": "go2_horizontal_velocity_weak_prior",
        "baseline_metadata": "dual_yaw_quality",
        "dual_antenna_baseline_quality": "dual_yaw_quality",
        "dual_antenna_relpos": "dual_yaw_quality",
        "one_seed_selected_gnss_antenna_position": "dual_yaw",
        "raw_doppler_uncertainty": "raw_doppler_std",
        "go2_contact": "go2_source_metadata",
        "go2_foot_force": "go2_source_metadata",
        "go2_foot_speed_metadata": "go2_source_metadata",
        "go2_gait_metadata": "go2_source_metadata",
        "go2_mode": "go2_source_metadata",
    }
    result: list[str] = []
    for value in values:
        normalized = aliases.get(str(value), str(value))
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def _canonical_affected_sources(type_id: str, values: Iterable[str]) -> tuple[str, ...]:
    affected = _normalized_sources(values)
    explicit = {
        "D40": ("dual_yaw_quality",), "D41": ("dual_yaw",),
        "D49": ("raw_doppler_velocity", "raw_doppler_std"),
        "D50": ("raw_doppler_velocity",), "D55": ("go2_source_metadata",),
        "D56": ("go2_source_metadata",),
        "D57": ("gnss_position", "receiver_velocity", "dual_yaw", "raw_doppler_velocity",
                "go2_roll_pitch_weak_prior", "go2_horizontal_velocity_weak_prior"),
        "D58": ("gnss_position", "dual_yaw"),
        "D59": ("gnss_position", "raw_doppler_velocity"),
        "D60": ("gnss_position", "gnss_position_std", "dual_yaw", "dual_yaw_std",
                "receiver_velocity", "receiver_velocity_std", "raw_doppler_velocity", "raw_doppler_std"),
    }
    return explicit.get(type_id, affected)


def _apply_exact_laws(type_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Apply the frozen source priority without consulting performance data."""

    p = copy.deepcopy(parameters)
    if type_id == "D07":
        p.update(duration_each_s=3.0, interval_count=3,
                 interval_centers_relative_to_anchor_s=[-6.0, 0.0, 6.0])
    elif type_id == "D19":
        # 中文说明：真实 effect-validation generator 使用 sin(t/30+phase)，
        # 因而周期是 60*pi 秒；这里不误写成提示词 fallback 的 60 秒。
        p.update(horizontal_amplitude_m=2.0, vertical_amplitude_m=0.5,
                 angular_time_denominator_s=30.0,
                 period_s=60.0 * 3.141592653589793,
                 phase_rule="2*pi*U(component_substream)")
    elif type_id in {"D34", "D35"}:
        p["signed_spike_magnitude_deg"] = 10.0
    elif type_id == "D39":
        p.update(burst_count=3, burst_length_valid_epochs_min=2,
                 burst_length_valid_epochs_max=4)
    elif type_id == "D40":
        p.update(baseline_length_additive_jitter_sigma_m=0.03,
                 preserve_baseline_direction=True, rel_acc_factor=2.0,
                 minimum_baseline_length_m=0.01,
                 rel_acc_field_available=False,
                 rel_acc_no_active_path=True,
                 baseline_length_solver_visible=False,
                 solver_runtime_input_expected_invariant=True,
                 unit_aliasing_forbidden=True)
    elif type_id == "D49":
        p.update(gaussian_sigma_mps=0.5, std_factor=0.25,
                 spike_component=False, std_floor_component=False)
    elif type_id == "D50":
        p.update(receiver_velocity_unchanged=True,
                 raw_doppler_horizontal_offset_mps=1.0)
    elif type_id == "D54":
        p.update(seed_groups={
            "seed_00_to_seed_03": {"scale": 1.5, "dropout_ratio": 0.0},
            "seed_04_to_seed_07": {"scale": 1.0, "dropout_ratio": 0.5},
            "seed_08": {"scale": 1.5, "dropout_ratio": 0.5},
        })
    elif type_id == "D55":
        p.update(selection_ratio=0.35,
                 uncertainty_pattern="contact_uncertain_and_mode_gait_unknown")
    elif type_id == "D56":
        p.update(selection_ratio=0.30, even_pattern="high_force_high_speed",
                 odd_pattern="low_force_low_speed", seed_08_pattern="alternating")
    elif type_id == "D57":
        p.update(latency_range_s=[0.1, 0.3], jitter_max_range_s=[0.020, 0.050],
                 per_source_independent_substreams=True, stable_sort=True)
    elif type_id == "D58":
        p.update(degradation_duration_s=10.0, yaw_spike_probability=0.10,
                 yaw_spike_magnitude_deg=10.0, recovery_duration_s=20.0)
    elif type_id == "D60":
        p.update(degradation_duration_s=20.0, recovery_duration_s=20.0)
    return p


def load_type_registry(source_path: str | Path | None = None) -> tuple[DegradationType, ...]:
    path = Path(source_path) if source_path else repo_root_from_module() / "configs/paper_rebuild/degradation_60types_9seeds.yaml"
    payload = _yaml_mapping(path)
    rows = payload.get("degradation_types")
    if not isinstance(rows, list) or len(rows) != DEGRADATION_TYPE_COUNT:
        raise CanonicalSpecError("degradation registry must contain exactly D01..D60")
    output: list[DegradationType] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise CanonicalSpecError("degradation row is not a mapping")
        expected = f"D{index:02d}"
        if row.get("id") != expected or not row.get("name") or not row.get("family"):
            raise CanonicalSpecError(f"degradation identity mismatch at {expected}")
        parameters = _apply_exact_laws(expected, dict(row.get("parameters") or {}))
        affected = _canonical_affected_sources(expected, row.get("affected_sources") or ())
        output.append(DegradationType(
            type_id=expected,
            name=str(row["name"]),
            family=str(row["family"]),
            parameters=parameters,
            affected_sources=affected,
            effect_validation_rule_id=f"RULE_{expected}",
        ))
    validate_type_registry(output)
    return tuple(output)


def load_external_source_registry(path: str | Path) -> tuple[DegradationType, ...]:
    """Parse the current 00_CONTEXT CSV (layer 1), including its JSON column."""

    source = Path(path).expanduser().resolve(strict=True)
    if hashlib.sha256(source.read_bytes()).hexdigest() != EXTERNAL_SOURCE_SPEC_SHA256:
        raise CanonicalSpecError("current DEGRADATION_MATRIX_SPEC.csv SHA256 mismatch")
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 61 or rows[0].get("degradation_type_id") != "CLEAN":
        raise CanonicalSpecError("external source spec must contain CLEAN + D01..D60")
    output: list[DegradationType] = []
    for index, row in enumerate(rows[1:], start=1):
        expected = f"D{index:02d}"
        if row.get("degradation_type_id") != expected:
            raise CanonicalSpecError(f"external source spec identity mismatch at {expected}")
        try:
            parameters = json.loads(row["parameters_json"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise CanonicalSpecError(f"external parameters_json invalid at {expected}") from exc
        if not isinstance(parameters, dict):
            raise CanonicalSpecError(f"external parameters_json not a mapping at {expected}")
        if row.get("rng_algorithm") != "numpy.random.PCG64":
            raise CanonicalSpecError(f"external RNG contract mismatch at {expected}")
        if row.get("execution_authorized_in_CLEAN0") != "false" or row.get("performance_evidence") != "false":
            raise CanonicalSpecError(f"external historical role flags mismatch at {expected}")
        affected = _canonical_affected_sources(
            expected, filter(None, str(row.get("affected_sources", "")).split(";"))
        )
        output.append(DegradationType(
            type_id=expected,
            name=str(row["degradation_type_name"]), family=str(row["family"]),
            parameters=_apply_exact_laws(expected, parameters),
            affected_sources=affected,
            claim_level="controlled_degradation_descriptive",
            effect_validation_rule_id=f"RULE_{expected}",
        ))
    validate_type_registry(output)
    return tuple(output)


def load_and_crosscheck_source_specs(external_csv: str | Path,
                                     tracked_yaml: str | Path | None = None) -> tuple[DegradationType, ...]:
    """Require byte-locked layer 1 and exact pre-overlay layer-2 identity.

    The preserved/master overlays are intentionally applied only *after* this
    comparison.  Otherwise a drift in the declarative source parameters could
    be hidden by a later implementation override.
    """

    external_path = Path(external_csv).expanduser().resolve(strict=True)
    tracked_path = (Path(tracked_yaml).expanduser().resolve(strict=True) if tracked_yaml
                    else repo_root_from_module() / "configs/paper_rebuild/degradation_60types_9seeds.yaml")
    tracked_payload = _yaml_mapping(tracked_path)
    tracked_rows = tracked_payload.get("degradation_types")
    matrix = tracked_payload.get("matrix")
    if (not isinstance(tracked_rows, list) or len(tracked_rows) != 60 or
            not isinstance(matrix, Mapping) or
            (matrix.get("degradation_type_count"), matrix.get("seeds_per_type"),
             matrix.get("degraded_case_count"), matrix.get("clean_case_count"),
             matrix.get("total_case_count")) != (60, 9, 540, 1, 541) or
            tracked_payload.get("execution_authorized_in_CLEAN0") is not False):
        raise CanonicalSpecError("tracked layer-2 matrix/count/history contract mismatch")
    with external_path.open("r", encoding="utf-8-sig", newline="") as handle:
        raw_external = list(csv.DictReader(handle))
    if len(raw_external) != 61 or raw_external[0].get("degradation_type_id") != "CLEAN":
        raise CanonicalSpecError("external layer-1 row closure mismatch")
    for index, (left, right) in enumerate(zip(raw_external[1:], tracked_rows), start=1):
        expected = f"D{index:02d}"
        try:
            left_parameters = json.loads(left["parameters_json"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise CanonicalSpecError(f"external parameters_json invalid at {expected}") from exc
        left_sources = _normalized_sources(filter(None, str(left.get("affected_sources", "")).split(";")))
        right_sources = _normalized_sources(right.get("affected_sources") or ())
        if (left.get("degradation_type_id"), left.get("degradation_type_name"), left.get("family")) != (
                right.get("id"), right.get("name"), right.get("family")):
            raise CanonicalSpecError(f"external/tracked static identity drift: {expected}")
        if left_parameters != (right.get("parameters") or {}):
            raise CanonicalSpecError(f"external/tracked parameter drift: {expected}")
        if left_sources != right_sources:
            raise CanonicalSpecError(f"external/tracked affected-source drift: {expected}")
        if (left.get("rng_algorithm") != "numpy.random.PCG64" or
                left.get("execution_authorized_in_CLEAN0") != "false" or
                left.get("performance_evidence") != "false"):
            raise CanonicalSpecError(f"external historical/RNG role drift: {expected}")
    external = load_external_source_registry(external_path)
    tracked = load_type_registry(tracked_path)
    for left, right in zip(external, tracked):
        if (left.type_id, left.name, left.family, left.parameters, left.affected_sources) != (
                right.type_id, right.name, right.family, right.parameters, right.affected_sources):
            raise CanonicalSpecError(f"post-overlay source identity drift: {left.type_id}")
    return external


def validate_type_registry(rows: Iterable[DegradationType]) -> None:
    items = tuple(rows)
    if len(items) != 60 or tuple(row.type_id for row in items) != tuple(f"D{i:02d}" for i in range(1, 61)):
        raise CanonicalSpecError("type registry is not the exact ordered D01..D60 closure")
    if any(not row.affected_sources for row in items):
        raise CanonicalSpecError("every degradation must identify an affected source")
    unknown = sorted({source for row in items for source in row.affected_sources if source not in ALL_SOURCE_IDS})
    if unknown:
        raise CanonicalSpecError("unknown canonical affected-source token: " + ",".join(unknown))


def parameter_provenance_rows(registry: Iterable[DegradationType] | None = None) -> list[dict[str, Any]]:
    repo = repo_root_from_module()
    tracked = repo / "configs/paper_rebuild/degradation_60types_9seeds.yaml"
    master = repo / "configs/paper_rebuild/canonical_by2_degradation_541.yaml"
    anchors = repo / "configs/paper_rebuild/canonical_by2_seed_anchor_policy.yaml"
    handler = Path(__file__).with_name("provider_generator.py")
    try:
        current_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover
        current_commit = "UNAVAILABLE_FAIL_CLOSED"
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (tracked, master, anchors, handler)}
    preserved_fields = {
        "D19": {"angular_time_denominator_s", "period_s", "phase_rule"},
        "D40": {"baseline_length_additive_jitter_sigma_m", "preserve_baseline_direction", "rel_acc_factor", "minimum_baseline_length_m",
                "rel_acc_field_available", "rel_acc_no_active_path", "baseline_length_solver_visible",
                "solver_runtime_input_expected_invariant", "unit_aliasing_forbidden"},
        "D49": {"gaussian_sigma_mps", "std_factor", "spike_component", "std_floor_component"},
        "D55": {"selection_ratio", "uncertainty_pattern"},
    }
    master_fields = {
        "D07": {"duration_each_s", "interval_count", "interval_centers_relative_to_anchor_s"},
        "D34": {"signed_spike_magnitude_deg"}, "D35": {"signed_spike_magnitude_deg"},
        "D39": {"burst_count", "burst_length_valid_epochs_min", "burst_length_valid_epochs_max"},
        "D50": {"receiver_velocity_unchanged", "raw_doppler_horizontal_offset_mps"},
        "D54": {"seed_groups"}, "D56": {"selection_ratio", "even_pattern", "odd_pattern", "seed_08_pattern"},
        "D57": {"latency_range_s", "jitter_max_range_s", "per_source_independent_substreams", "stable_sort"},
        "D58": {"degradation_duration_s", "yaw_spike_probability", "yaw_spike_magnitude_deg", "recovery_duration_s"},
        "D60": {"degradation_duration_s", "recovery_duration_s"},
    }
    preserved_symbols = {
        "D19": "handle_position_sinusoidal", "D40": "handle_baseline_length_jitter",
        "D49": "handle_velocity_bad_optimistic", "D55": "handle_go2_metadata_uncertain",
    }
    rows: list[dict[str, Any]] = []
    for item in registry or load_type_registry():
        for field, value in sorted(item.parameters.items()):
            if field in preserved_fields.get(item.type_id, set()):
                layer, path, commit, symbol, digest = 3, PRESERVED_SOURCE_PATH, PRESERVED_SOURCE_COMMIT, preserved_symbols[item.type_id], PRESERVED_SOURCE_SHA256
            elif field in master_fields.get(item.type_id, set()):
                layer, path, commit, symbol, digest = 4, str(master.relative_to(repo)), current_commit, f"master_overrides.{item.type_id}.{field}", hashes[master]
            else:
                layer, path, commit, symbol, digest = 1, "clean://00_CONTEXT/DEGRADATION_MATRIX_SPEC.csv", "external_current_context", f"{item.type_id}.parameters_json.{field}", EXTERNAL_SOURCE_SPEC_SHA256
            rows.append({"degradation_type_id": item.type_id, "field": field,
                         "value_json": json.dumps(value, sort_keys=True, separators=(",", ":")),
                         "source_layer": layer, "source_path": path, "source_commit": commit,
                         "symbol": symbol, "source_sha256": digest, "fallback_used": False})
        # Layer 2 is an exact declarative crosscheck, not a replacement for layer 1.
        rows.append({"degradation_type_id": item.type_id, "field": "__layer2_identity_crosscheck__",
                     "value_json": "true", "source_layer": 2,
                     "source_path": str(tracked.relative_to(repo)), "source_commit": current_commit,
                     "symbol": f"degradation_types[{int(item.type_id[1:])-1}]", "source_sha256": hashes[tracked], "fallback_used": False})
        for field, value in (("__anchor_policy__", "source_only_frozen_seed_anchor"),
                             ("__component_substreams__", "SeedSequence.spawn_named_components")):
            rows.append({"degradation_type_id": item.type_id, "field": field,
                         "value_json": json.dumps(value), "source_layer": 4,
                         "source_path": str(anchors.relative_to(repo)), "source_commit": current_commit,
                         "symbol": "interval_policy" if field == "__anchor_policy__" else "component_substreams",
                         "source_sha256": hashes[anchors], "fallback_used": False})
        rows.append({"degradation_type_id": item.type_id, "field": "__handler_implementation__",
                     "value_json": json.dumps("apply_degradation"), "source_layer": 4,
                     "source_path": str(handler.relative_to(repo)), "source_commit": current_commit,
                     "symbol": f"apply_degradation:{item.type_id}", "source_sha256": hashes[handler],
                     "fallback_used": False})
    return rows


def registry_sha256(registry: Iterable[DegradationType] | None = None) -> str:
    payload = [
        {"id": row.type_id, "name": row.name, "family": row.family,
         "parameters": row.parameters, "affected_sources": row.affected_sources}
        for row in (registry or load_type_registry())
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
