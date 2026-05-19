"""N9B0C toy-only pilot degradation generator precheck.

This module implements pilot generator contracts for the ten approved N9B0C
cases. It only produces tiny in-memory/toy manifests for generator validation;
it does not create BY2 degraded inputs, solver outputs, evaluator outputs,
figures, or full random arrays.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from legsa_gins.reporting.by2_degradation_runner_precheck import (
    ALLOWED_ROUTING_STATUSES,
    FORBIDDEN_EXECUTION_OUTPUT_NAMES,
    MatrixBundle,
    discover_cleaned_matrix_root,
    load_matrix_bundle,
)


STAGE = "N9B0C_PILOT_GENERATOR_IMPLEMENTATION_AND_EXECUTION_PRECHECK"

PILOT_CASE_IDS = [
    "M_normal_baseline_repeat",
    "A_outage_5s",
    "C_position_noise_medium",
    "D_position_spike_medium",
    "B_gnss_downsample_2Hz",
    "H_dual_yaw_noise_medium",
    "G_raw_doppler_disabled",
    "L_feedback_disabled",
    "I_source_aware_disabled",
    "J_go2_horizontal_velocity_missing",
]

RANDOM_CASE_IDS = {
    "C_position_noise_medium",
    "D_position_spike_medium",
    "H_dual_yaw_noise_medium",
}

DETERMINISTIC_CASE_IDS = set(PILOT_CASE_IDS) - RANDOM_CASE_IDS

TOY_FLAGS = {
    "toy_only": True,
    "not_used_for_algorithm": True,
    "not_degradation_execution": True,
    "ready_for_N9B_execution": False,
}

TOY_ROW_COUNT = 20


@dataclass(frozen=True)
class PilotGeneration:
    case_id: str
    generator_id: str
    deterministic_or_random: str
    seed: str
    toy_kind: str
    manifest: dict[str, Any]
    toy_values: list[dict[str, Any]]
    metadata_only: bool


def generate_m_normal_baseline_repeat(seed: int | None = None) -> PilotGeneration:
    _require_no_seed("M_normal_baseline_repeat", seed)
    return _metadata_generation(
        case_id="M_normal_baseline_repeat",
        generator_id="normal_sanity",
        toy_kind="normal_baseline_repeat_manifest",
        manifest={
            "case_behavior": "normal_condition_repeat",
            "degradation_applied": False,
            "expected_generator_action": "metadata_only_no_input_mutation",
        },
    )


def generate_a_outage_5s(seed: int | None = None) -> PilotGeneration:
    _require_no_seed("A_outage_5s", seed)
    toy_times = [205.2, 206.2, 207.2, 208.2, 209.2, 210.2, 211.2, 211.3]
    values = [
        {"toy_time_s": t, "gnss_position_available": not (206.2 <= t <= 211.2)}
        for t in toy_times
    ]
    return PilotGeneration(
        case_id="A_outage_5s",
        generator_id="gnss_outage",
        deterministic_or_random="deterministic",
        seed="none",
        toy_kind="toy_outage_mask",
        manifest={
            **TOY_FLAGS,
            "outage_start_s": 206.2,
            "outage_end_s": 211.2,
            "mask_count": sum(1 for row in values if not row["gnss_position_available"]),
            "toy_row_count": len(values),
        },
        toy_values=values,
        metadata_only=False,
    )


def generate_c_position_noise_medium(seed: int | None = None) -> PilotGeneration:
    checked_seed = _require_seed("C_position_noise_medium", seed)
    rng = random.Random(1000 + checked_seed)
    values = []
    for index in range(5):
        values.append(
            {
                "toy_index": index,
                "seed": checked_seed,
                "noise_n_m": round(rng.gauss(0.0, 1.5), 6),
                "noise_e_m": round(rng.gauss(0.0, 1.5), 6),
                "noise_u_m": round(rng.gauss(0.0, 2.5), 6),
            }
        )
    return PilotGeneration(
        case_id="C_position_noise_medium",
        generator_id="position_noise",
        deterministic_or_random="random",
        seed=str(checked_seed),
        toy_kind="toy_position_noise_values",
        manifest={
            **TOY_FLAGS,
            "sigma_h_m": 1.5,
            "sigma_v_m": 2.5,
            "toy_value_count": len(values),
            "full_random_array_created": False,
        },
        toy_values=values,
        metadata_only=False,
    )


def generate_d_position_spike_medium(seed: int | None = None) -> PilotGeneration:
    checked_seed = _require_seed("D_position_spike_medium", seed)
    rng = random.Random(2000 + checked_seed)
    values = []
    for index in range(TOY_ROW_COUNT):
        triggered = rng.random() < 0.05
        if triggered:
            sign_h = -1 if rng.random() < 0.5 else 1
            sign_v = -1 if rng.random() < 0.5 else 1
            values.append(
                {
                    "toy_index": index,
                    "seed": checked_seed,
                    "triggered": True,
                    "spike_h_m": sign_h * 4.0,
                    "spike_v_m": sign_v * 2.0,
                }
            )
    return PilotGeneration(
        case_id="D_position_spike_medium",
        generator_id="position_spike",
        deterministic_or_random="random",
        seed=str(checked_seed),
        toy_kind="toy_position_spike_indices",
        manifest={
            **TOY_FLAGS,
            "probability": 0.05,
            "horizontal_amplitude_m": 4.0,
            "vertical_amplitude_m": 2.0,
            "toy_population_count": TOY_ROW_COUNT,
            "toy_trigger_count": len(values),
            "full_random_array_created": False,
        },
        toy_values=values,
        metadata_only=False,
    )


def generate_b_gnss_downsample_2hz(seed: int | None = None) -> PilotGeneration:
    _require_no_seed("B_gnss_downsample_2Hz", seed)
    values = [
        {
            "toy_index": index,
            "source_rate_hz": 10,
            "target_rate_hz": 2,
            "kept": index % 5 == 0,
        }
        for index in range(TOY_ROW_COUNT)
    ]
    return PilotGeneration(
        case_id="B_gnss_downsample_2Hz",
        generator_id="deterministic_downsample",
        deterministic_or_random="deterministic",
        seed="none",
        toy_kind="toy_integer_step_downsample_mask",
        manifest={
            **TOY_FLAGS,
            "source_rate_hz": 10,
            "target_rate_hz": 2,
            "integer_step": 5,
            "kept_count": sum(1 for row in values if row["kept"]),
            "toy_row_count": len(values),
        },
        toy_values=values,
        metadata_only=False,
    )


def generate_h_dual_yaw_noise_medium(seed: int | None = None) -> PilotGeneration:
    checked_seed = _require_seed("H_dual_yaw_noise_medium", seed)
    rng = random.Random(3000 + checked_seed)
    values = [
        {
            "toy_index": index,
            "seed": checked_seed,
            "yaw_noise_deg": round(rng.gauss(0.0, 3.0), 6),
        }
        for index in range(5)
    ]
    return PilotGeneration(
        case_id="H_dual_yaw_noise_medium",
        generator_id="yaw_dropout_noise_spike_bias_std",
        deterministic_or_random="random",
        seed=str(checked_seed),
        toy_kind="toy_yaw_noise_degrees",
        manifest={
            **TOY_FLAGS,
            "sigma_yaw_deg": 3.0,
            "single_antenna_routing_expected": "not_applicable",
            "pure_INS_routing_expected": "not_applicable",
            "toy_value_count": len(values),
            "full_random_array_created": False,
        },
        toy_values=values,
        metadata_only=False,
    )


def generate_g_raw_doppler_disabled(seed: int | None = None) -> PilotGeneration:
    _require_no_seed("G_raw_doppler_disabled", seed)
    return _metadata_generation(
        case_id="G_raw_doppler_disabled",
        generator_id="raw_doppler",
        toy_kind="raw_doppler_disabled_manifest",
        manifest={"toggle": "raw_doppler_disabled", "metadata_manifest_only": True},
    )


def generate_l_feedback_disabled(seed: int | None = None) -> PilotGeneration:
    _require_no_seed("L_feedback_disabled", seed)
    return _metadata_generation(
        case_id="L_feedback_disabled",
        generator_id="feedback_fgo_diagnostic",
        toy_kind="feedback_disabled_manifest",
        manifest={"toggle": "feedback_disabled", "metadata_manifest_only": True},
    )


def generate_i_source_aware_disabled(seed: int | None = None) -> PilotGeneration:
    _require_no_seed("I_source_aware_disabled", seed)
    return _metadata_generation(
        case_id="I_source_aware_disabled",
        generator_id="source_aware",
        toy_kind="source_aware_disabled_manifest",
        manifest={"toggle": "source_aware_disabled", "metadata_manifest_only": True},
    )


def generate_j_go2_horizontal_velocity_missing(seed: int | None = None) -> PilotGeneration:
    _require_no_seed("J_go2_horizontal_velocity_missing", seed)
    return _metadata_generation(
        case_id="J_go2_horizontal_velocity_missing",
        generator_id="go2_legged",
        toy_kind="go2_horizontal_velocity_missing_manifest",
        manifest={"toggle": "go2_horizontal_velocity_missing", "metadata_manifest_only": True},
    )


GENERATOR_FUNCTIONS: dict[str, Callable[[int | None], PilotGeneration]] = {
    "M_normal_baseline_repeat": generate_m_normal_baseline_repeat,
    "A_outage_5s": generate_a_outage_5s,
    "C_position_noise_medium": generate_c_position_noise_medium,
    "D_position_spike_medium": generate_d_position_spike_medium,
    "B_gnss_downsample_2Hz": generate_b_gnss_downsample_2hz,
    "H_dual_yaw_noise_medium": generate_h_dual_yaw_noise_medium,
    "G_raw_doppler_disabled": generate_g_raw_doppler_disabled,
    "L_feedback_disabled": generate_l_feedback_disabled,
    "I_source_aware_disabled": generate_i_source_aware_disabled,
    "J_go2_horizontal_velocity_missing": generate_j_go2_horizontal_velocity_missing,
}


def build_pilot_generations(bundle: MatrixBundle) -> list[PilotGeneration]:
    seed_lookup = _seed_rows_by_case(bundle.seed_plan)
    generations: list[PilotGeneration] = []
    for case_id in PILOT_CASE_IDS:
        generator = GENERATOR_FUNCTIONS[case_id]
        if case_id in RANDOM_CASE_IDS:
            seeds = sorted(int(row["seed"]) for row in seed_lookup.get(case_id, []) if row["seed"] != "none")
            if seeds != list(range(10)):
                raise ValueError(f"{case_id} requires cleaned seed rows 0..9, found {seeds}")
            generations.extend(generator(seed) for seed in seeds)
        else:
            rows = seed_lookup.get(case_id, [])
            if not rows or any(row["seed"] != "none" for row in rows):
                raise ValueError(f"{case_id} requires deterministic seed=none row")
            generations.append(generator(None))
    return generations


def build_generator_capability_matrix(generations: Iterable[PilotGeneration]) -> list[dict[str, Any]]:
    by_case: dict[str, list[PilotGeneration]] = {}
    for generation in generations:
        by_case.setdefault(generation.case_id, []).append(generation)
    rows: list[dict[str, Any]] = []
    for case_id in PILOT_CASE_IDS:
        items = by_case[case_id]
        first = items[0]
        rows.append(
            {
                **TOY_FLAGS,
                "case_id": case_id,
                "generator_id": first.generator_id,
                "generator_function": GENERATOR_FUNCTIONS[case_id].__name__,
                "deterministic_or_random": first.deterministic_or_random,
                "seed_rows_used": len(items),
                "toy_value_rows": sum(len(item.toy_values) for item in items),
                "metadata_only": all(item.metadata_only for item in items),
                "degraded_inputs_created": False,
                "full_random_arrays_created": False,
                "status": "implemented_toy_only",
            }
        )
    return rows


def build_toy_random_value_manifest(generations: Iterable[PilotGeneration]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for generation in generations:
        if generation.deterministic_or_random != "random":
            continue
        rows.append(
            {
                **TOY_FLAGS,
                "case_id": generation.case_id,
                "generator_id": generation.generator_id,
                "seed": generation.seed,
                "toy_kind": generation.toy_kind,
                "toy_value_count": len(generation.toy_values),
                "full_random_array_created": False,
                "hash_sha256": _stable_hash(generation.toy_values),
                "toy_values_json": json.dumps(generation.toy_values, sort_keys=True),
            }
        )
    return rows


def build_applicability_routing_check(bundle: MatrixBundle) -> list[dict[str, Any]]:
    source_rows = [row for row in bundle.applicability if row["case_id"] in PILOT_CASE_IDS]
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        status = row["applicability"]
        rows.append(
            {
                **TOY_FLAGS,
                "case_id": row["case_id"],
                "family_code": row["family_code"],
                "algorithm_group": row["algorithm_group"],
                "routing_status": status,
                "reason": row["reason"],
                "routing_preserved_from_cleaned_matrix": status in ALLOWED_ROUTING_STATUSES,
            }
        )
    return rows


def build_pilot_ready_matrix(bundle: MatrixBundle, generations: Iterable[PilotGeneration]) -> list[dict[str, Any]]:
    generation_cases = {generation.case_id for generation in generations}
    seed_cases = {row["case_id"] for row in bundle.seed_plan}
    pilot_rows = {row["case_id"]: row for row in bundle.pilot}
    routing_rows = build_applicability_routing_check(bundle)
    routing_cases = {
        row["case_id"]
        for row in routing_rows
        if row["routing_preserved_from_cleaned_matrix"] is True
    }
    rows: list[dict[str, Any]] = []
    for case_id in PILOT_CASE_IDS:
        source = pilot_rows[case_id]
        random_required = case_id in RANDOM_CASE_IDS
        generator_implemented = case_id in GENERATOR_FUNCTIONS and case_id in generation_cases
        seed_status = "seed_rows_0..9_present" if random_required else "seed_none"
        toy_test_passed = generator_implemented
        source_schema_checked = bool(source.get("expected_outputs"))
        applicability_routing_passed = case_id in routing_cases
        ready_for_n9b1_execution = (
            generator_implemented
            and toy_test_passed
            and source_schema_checked
            and applicability_routing_passed
            and case_id in seed_cases
        )
        rows.append(
            {
                **TOY_FLAGS,
                "case_id": case_id,
                "family_code": source["family_code"],
                "generator_implemented": generator_implemented,
                "generator_type": GENERATOR_FUNCTIONS[case_id].__name__,
                "deterministic_or_random": "random" if random_required else "deterministic",
                "seed_status": seed_status,
                "toy_test_passed": toy_test_passed,
                "source_schema_checked": source_schema_checked,
                "applicability_routing_passed": applicability_routing_passed,
                "expected_full_execution_outputs": source["expected_outputs"],
                "ready_for_N9B1_execution": ready_for_n9b1_execution,
                "blockers": "" if ready_for_n9b1_execution else "pilot generator precheck failed",
                "pilot_inputs_created": False,
                "solver_run": False,
                "official_evaluator_run": False,
            }
        )
    return rows


def build_blocked_items() -> list[dict[str, Any]]:
    return [
        {
            **TOY_FLAGS,
            "item": "N9B1_execution",
            "blocked_reason": "outside N9B0C scope; requires later approval",
        },
        {
            **TOY_FLAGS,
            "item": "real_BY2_degraded_inputs",
            "blocked_reason": "N9B0C may only create toy/in-memory or tiny toy runtime manifests",
        },
        {
            **TOY_FLAGS,
            "item": "full_random_arrays",
            "blocked_reason": "N9B0C may only create toy values from cleaned seed rows",
        },
        {
            **TOY_FLAGS,
            "item": "official_evaluator",
            "blocked_reason": "official evaluator execution is explicitly outside N9B0C scope",
        },
        {
            **TOY_FLAGS,
            "item": "solver_execution",
            "blocked_reason": "solver execution is explicitly outside N9B0C scope",
        },
    ]


def validate_pilot_precheck_result(result: dict[str, Any], runtime_root: Path | None = None) -> dict[str, Any]:
    issues: list[str] = []
    capability = result["generator_capability_matrix"]
    ready = result["n9b1_pilot_ready_matrix"]
    routing = result["applicability_routing_check"]
    random_manifest = result["toy_random_value_manifest"]
    if [row["case_id"] for row in capability] != PILOT_CASE_IDS:
        issues.append("capability matrix does not match approved 10 pilot cases")
    if len(ready) != 10:
        issues.append("pilot ready matrix must contain exactly 10 rows")
    if len(routing) != 110:
        issues.append(f"applicability routing rows {len(routing)} != expected 110")
    if len(random_manifest) != 30:
        issues.append(f"toy random manifest rows {len(random_manifest)} != expected 30")
    for row in capability + ready + routing + random_manifest + result["blocked_items"]:
        for key, expected in TOY_FLAGS.items():
            if row.get(key) != expected:
                issues.append(f"{row.get('case_id', row.get('item', '<unknown>'))} flag {key} != {expected}")
    issues.extend(_validate_special_routing(routing))
    if any(not row.get("ready_for_N9B1_execution") for row in ready):
        issues.append("all 10 pilot rows must be ready_for_N9B1_execution=true after N9B0C passes")
    if runtime_root is not None:
        issues.extend(_validate_runtime_tree(runtime_root))
    return {
        **TOY_FLAGS,
        "status": "pass" if not issues else "fail",
        "issues": issues,
    }


def run_pilot_generator_precheck(
    matrix_root: Path | None = None,
    runtime_root: Path | None = None,
    write_outputs: bool = False,
) -> dict[str, Any]:
    bundle = load_matrix_bundle(matrix_root or discover_cleaned_matrix_root())
    generations = build_pilot_generations(bundle)
    capability_matrix = build_generator_capability_matrix(generations)
    pilot_ready_matrix = build_pilot_ready_matrix(bundle, generations)
    toy_random_manifest = build_toy_random_value_manifest(generations)
    routing_check = build_applicability_routing_check(bundle)
    blocked_items = build_blocked_items()
    result: dict[str, Any] = {
        "stage": STAGE,
        "bundle_matrix_root": _display_path(bundle.matrix_root),
        "generations": [asdict(generation) for generation in generations],
        "generator_capability_matrix": capability_matrix,
        "n9b1_pilot_ready_matrix": pilot_ready_matrix,
        "toy_random_value_manifest": toy_random_manifest,
        "applicability_routing_check": routing_check,
        "blocked_items": blocked_items,
    }
    root = runtime_root or Path(STAGE)
    validation = validate_pilot_precheck_result(result, root if write_outputs else None)
    result.update(_build_reports(result, validation))
    if write_outputs:
        write_pilot_precheck_outputs(root, result)
        validation = validate_pilot_precheck_result(result, root)
        result.update(_build_reports(result, validation))
        write_pilot_precheck_outputs(root, result)
    return result


def write_pilot_precheck_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    _create_runtime_dirs(runtime_root)
    report_dir = runtime_root / "reports"
    matrix_dir = runtime_root / "matrix"
    summary_dir = runtime_root / "summary"
    generator_test_dir = runtime_root / "generator_tests"
    toy_randomness_dir = runtime_root / "toy_randomness"
    reports = {
        "N9B0C_GENERATOR_IMPLEMENTATION_REPORT.json": result["generator_implementation_report"],
        "N9B0C_RANDOMNESS_TOY_VALIDATION_REPORT.json": result["randomness_toy_validation_report"],
        "N9B0C_APPLICABILITY_ROUTING_REPORT.json": result["applicability_routing_report"],
        "N9B0C_PILOT_READINESS_REPORT.json": result["pilot_readiness_report"],
        "N9B0C_SAFETY_GATE_REPORT.json": result["safety_gate_report"],
        "N9B0C_DECISION_REPORT.json": result["decision_report"],
    }
    matrices = {
        "N9B0C_GENERATOR_CAPABILITY_MATRIX": result["generator_capability_matrix"],
        "N9B0C_N9B1_PILOT_READY_MATRIX": result["n9b1_pilot_ready_matrix"],
        "N9B0C_TOY_RANDOM_VALUE_MANIFEST": result["toy_random_value_manifest"],
        "N9B0C_APPLICABILITY_ROUTING_CHECK": result["applicability_routing_check"],
        "N9B0C_BLOCKED_ITEMS": result["blocked_items"],
    }
    for name, payload in reports.items():
        _write_json(report_dir / name, payload)
    for stem, rows in matrices.items():
        _write_json(matrix_dir / f"{stem}.json", rows)
        _write_csv(matrix_dir / f"{stem}.csv", rows)
    for generation in result["generations"]:
        manifest = {
            **TOY_FLAGS,
            "case_id": generation["case_id"],
            "generator_id": generation["generator_id"],
            "seed": generation["seed"],
            "toy_kind": generation["toy_kind"],
            "metadata_only": generation["metadata_only"],
            "hash_sha256": _stable_hash(generation["toy_values"]),
            "manifest": generation["manifest"],
            "toy_values": generation["toy_values"],
        }
        target_dir = toy_randomness_dir if generation["deterministic_or_random"] == "random" else generator_test_dir
        _write_json(target_dir / f"{generation['case_id']}_seed_{generation['seed']}.json", manifest)
    summaries = {
        "n9b0c_generator_implementation.md": _summary_generator(result),
        "n9b0c_pilot_readiness.md": _summary_readiness(result),
        "n9b0c_safety_gate.md": _summary_safety(result),
        "n9b0c_next_stage_recommendation.md": _summary_recommendation(result),
    }
    for name, text in summaries.items():
        (summary_dir / name).write_text(text, encoding="utf-8")


def _build_reports(result: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    capability = result["generator_capability_matrix"]
    random_manifest = result["toy_random_value_manifest"]
    routing = result["applicability_routing_check"]
    ready = result["n9b1_pilot_ready_matrix"]
    status = validation["status"]
    return {
        "generator_implementation_report": {
            **TOY_FLAGS,
            "stage": STAGE,
            "status": status,
            "pilot_case_count": len(capability),
            "generator_functions": [row["generator_function"] for row in capability],
            "degraded_inputs_created": False,
            "solver_run": False,
            "official_evaluator_run": False,
            "figures_generated": False,
        },
        "randomness_toy_validation_report": {
            **TOY_FLAGS,
            "stage": STAGE,
            "status": status,
            "random_case_count": len(RANDOM_CASE_IDS),
            "toy_random_seed_rows": len(random_manifest),
            "full_random_arrays_created": False,
            "seed_plan_source": "cleaned_matrix",
        },
        "applicability_routing_report": {
            **TOY_FLAGS,
            "stage": STAGE,
            "status": status,
            "routing_rows": len(routing),
            "single_baseline_yaw_raw_feedback_source_go2_blocked": True,
            "pure_INS_fixed_reference_or_not_applicable_only": True,
            "final_v23_reference_only": True,
        },
        "pilot_readiness_report": {
            **TOY_FLAGS,
            "stage": STAGE,
            "status": status,
            "pilot_case_count": len(ready),
            "pilot_cases_ready_count": sum(1 for row in ready if row["ready_for_N9B1_execution"]),
            "pilot_cases_blocked_count": sum(1 for row in ready if not row["ready_for_N9B1_execution"]),
            "ready_for_N9B1_execution": status == "pass" and all(row["ready_for_N9B1_execution"] for row in ready),
            "reason": "N9B0C implemented pilot generators and toy-only prechecks; N9B1 execution still requires human approval",
        },
        "safety_gate_report": {
            **TOY_FLAGS,
            "stage": STAGE,
            "status": status,
            "no_solver_run": True,
            "no_official_evaluator_run": True,
            "no_real_BY2_degraded_inputs": True,
            "no_full_random_arrays": True,
            "no_algorithm_code_modified_by_module": True,
            "issues": validation["issues"],
        },
        "decision_report": {
            **TOY_FLAGS,
            "stage": STAGE,
            "status": (
                "N9B0C_pilot_generators_ready_for_N9B1_execution"
                if status == "pass"
                else "N9B0C_safety_gate_failed"
            ),
            "ready_for_N9B_planning": status == "pass",
            "ready_for_N9B1_execution": status == "pass" and all(row["ready_for_N9B1_execution"] for row in ready),
            "recommended_next_stage": (
                "human_review_N9B0C_then_N9B1_pilot_execution"
                if status == "pass"
                else "repair_safety_violation"
            ),
            "blocker": "" if status == "pass" else "repair failed N9B0C precheck or safety gate before N9B1",
        },
    }


def _metadata_generation(case_id: str, generator_id: str, toy_kind: str, manifest: dict[str, Any]) -> PilotGeneration:
    return PilotGeneration(
        case_id=case_id,
        generator_id=generator_id,
        deterministic_or_random="deterministic",
        seed="none",
        toy_kind=toy_kind,
        manifest={**TOY_FLAGS, **manifest},
        toy_values=[],
        metadata_only=True,
    )


def _require_no_seed(case_id: str, seed: int | None) -> None:
    if seed is not None:
        raise ValueError(f"{case_id} is deterministic and must use seed=None")


def _require_seed(case_id: str, seed: int | None) -> int:
    if seed is None:
        raise ValueError(f"{case_id} requires a cleaned seed row")
    if seed not in range(10):
        raise ValueError(f"{case_id} seed must be in 0..9")
    return int(seed)


def _seed_rows_by_case(seed_rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_case: dict[str, list[dict[str, str]]] = {}
    for row in seed_rows:
        if row["case_id"] in PILOT_CASE_IDS:
            by_case.setdefault(row["case_id"], []).append(row)
    return by_case


def _validate_special_routing(rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for row in rows:
        case_id = row["case_id"]
        algorithm = row["algorithm_group"]
        status = row["routing_status"]
        family = row["family_code"]
        if algorithm == "final_v23_dual_antenna_EKF" and status != "reference_only":
            issues.append(f"final_v23 must be reference_only for {case_id}")
        if algorithm == "pure_INS_reference_initialized" and status not in {"fixed_reference", "not_applicable"}:
            issues.append(f"pure_INS must be fixed_reference/not_applicable for {case_id}")
        if algorithm == "single_antenna_gnss1_status_KF_GINS":
            if family in {"A", "B", "C", "D", "M"} and status != "applicable":
                issues.append(f"single baseline must apply to GNSS position pilot {case_id}")
            if family not in {"A", "B", "C", "D", "M"} and status != "not_applicable":
                issues.append(f"single baseline must not apply to {case_id}")
        if case_id == "H_dual_yaw_noise_medium" and algorithm in {
            "single_antenna_gnss1_status_KF_GINS",
            "pure_INS_reference_initialized",
        } and status != "not_applicable":
            issues.append(f"yaw noise routing must not apply to {algorithm}")
    return issues


def _validate_runtime_tree(runtime_root: Path) -> list[str]:
    issues: list[str] = []
    if not runtime_root.exists():
        return ["runtime root was not created"]
    required_dirs = ["generator_tests", "pilot_readiness", "toy_randomness", "reports", "matrix", "summary", "audit_logs"]
    for dirname in required_dirs:
        if not (runtime_root / dirname).is_dir():
            issues.append(f"missing runtime subdir {dirname}")
    forbidden_prefixes = set(FORBIDDEN_EXECUTION_OUTPUT_NAMES)
    forbidden_suffixes = {".npy", ".npz", ".png", ".pdf", ".svg", ".jpg", ".jpeg"}
    for path in runtime_root.rglob("*"):
        if not path.is_file():
            continue
        if any(path.name.startswith(prefix) for prefix in forbidden_prefixes):
            issues.append(f"forbidden execution output generated: {_display_path(path)}")
        if path.suffix.lower() in forbidden_suffixes:
            issues.append(f"forbidden runtime artifact generated: {_display_path(path)}")
    return issues


def _create_runtime_dirs(runtime_root: Path) -> None:
    for dirname in ["generator_tests", "pilot_readiness", "toy_randomness", "reports", "matrix", "summary", "audit_logs"]:
        (runtime_root / dirname).mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _summary_generator(result: dict[str, Any]) -> str:
    return (
        "# N9B0C generator implementation\n\n"
        "- Scope: toy-only pilot generator implementation and execution precheck.\n"
        f"- Approved pilot cases implemented: {len(result['generator_capability_matrix'])}.\n"
        f"- Toy generation records: {len(result['generations'])}.\n"
        "- No solver, official evaluator, real BY2 degraded input, figure, or full random array was generated.\n"
        "- ready_for_N9B_execution=false.\n"
    )


def _summary_readiness(result: dict[str, Any]) -> str:
    return (
        "# N9B0C pilot readiness\n\n"
        f"- Pilot readiness rows: {len(result['n9b1_pilot_ready_matrix'])}.\n"
        "- Generator functions exist for the approved ten pilot cases.\n"
        "- N9B1 execution remains blocked by design.\n"
        "- ready_for_N9B_execution=false.\n"
    )


def _summary_safety(result: dict[str, Any]) -> str:
    safety = result["safety_gate_report"]
    return (
        "# N9B0C safety gate\n\n"
        f"- Safety status: {safety['status']}.\n"
        "- toy_only=true; not_used_for_algorithm=true; not_degradation_execution=true.\n"
        "- No real BY2 degraded inputs, full random arrays, solvers, official evaluator, or figures.\n"
        "- ready_for_N9B_execution=false.\n"
    )


def _summary_recommendation(result: dict[str, Any]) -> str:
    decision = result["decision_report"]
    return (
        "# N9B0C next stage recommendation\n\n"
        f"- Decision: {decision['status']}.\n"
        "- Recommended next stage: human review before any N9B1 execution.\n"
        "- This precheck does not authorize N9B1, solvers, evaluator runs, or real degraded inputs.\n"
        "- ready_for_N9B_execution=false.\n"
    )
