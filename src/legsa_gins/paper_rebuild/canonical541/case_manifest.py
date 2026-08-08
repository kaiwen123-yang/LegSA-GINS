"""Materialize the exact 541 canonical case rows."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from .matrix_spec import (
    ALL_SOURCE_IDS, CASE_COUNT, CLEAN_CASE_ID, DATA_MODE, DATASET,
    DEGRADED_CASE_COUNT, load_type_registry,
)
from .seed_anchor import ANCHOR_NAMES, SEED_IDS, SEEDS


ANCHOR_DEPENDENT_TYPES = frozenset({
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10",
    "D22", "D30", "D31", "D39", "D42", "D46", "D58", "D60",
})


class CaseManifestError(ValueError):
    pass


def _anchor_map(anchors: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    output = {str(row["seed_index"]): row for row in anchors}
    if set(output) != set(SEED_IDS):
        raise CaseManifestError("anchor manifest must contain seed_00..seed_08")
    return output


def build_case_manifest(anchors: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    anchor_by_seed = _anchor_map(anchors)
    rows: list[dict[str, Any]] = [{
        "case_id": CLEAN_CASE_ID, "case_index": 0, "dataset": DATASET,
        "data_mode": "real_clean", "case_family": "clean",
        "degradation_type_id": "CLEAN", "degradation_type_name": "clean_reference_no_degradation",
        "seed_index": "none", "seed_value": "", "rng_algorithm": "none",
        "anchor_name": "none", "anchor_time_s": "", "duration_s": "full_sequence",
        "degradation_parameters_json": json.dumps({"operation": "none"}, separators=(",", ":")),
        "affected_sources": "", "unaffected_sources": ";".join(ALL_SOURCE_IDS),
        "requires_randomness": False, "seed_effective": False,
        "independent_realization": False,
        "effect_validation_rule_id": "RULE_CLEAN",
        "trace_eval_only": True, "final_v23_output_solver_input_allowed": False,
        "legsa_output_solver_input_allowed": False, "go2_truth_claim_allowed": False,
        "synthetic_data_used": False, "semisynthetic_data_used": False,
        "claim_level": "clean_reference_real_data",
    }]
    case_index = 1
    for degradation in load_type_registry():
        for seed_offset, seed_id in enumerate(SEED_IDS):
            anchor = anchor_by_seed[seed_id]
            affected = set(degradation.affected_sources)
            duration = (
                degradation.parameters.get("duration_each_s", 3.0)
                if degradation.type_id == "D07"
                else degradation.parameters.get("duration_s", degradation.parameters.get("degradation_duration_s", "full_sequence"))
            )
            rows.append({
                "case_id": f"{degradation.type_id}_{seed_id}", "case_index": case_index,
                "dataset": DATASET, "data_mode": DATA_MODE,
                "case_family": degradation.family,
                "degradation_type_id": degradation.type_id,
                "degradation_type_name": degradation.name,
                "seed_index": seed_id, "seed_value": SEEDS[seed_offset],
                "rng_algorithm": "numpy.random.PCG64",
                "anchor_name": ANCHOR_NAMES[seed_offset],
                "anchor_time_s": float(anchor["anchor_time_s"]),
                "anchor_selection_status": anchor.get("selection_status", "selected"),
                "duration_s": duration,
                "degradation_parameters_json": json.dumps(degradation.parameters, sort_keys=True, separators=(",", ":")),
                "affected_sources": ";".join(degradation.affected_sources),
                "unaffected_sources": ";".join(source for source in ALL_SOURCE_IDS if source not in affected),
                "requires_randomness": degradation.requires_randomness,
                "seed_effective": degradation.requires_randomness or degradation.type_id in ANCHOR_DEPENDENT_TYPES,
                "independent_realization": degradation.requires_randomness,
                "effect_validation_rule_id": degradation.effect_validation_rule_id,
                "trace_eval_only": True, "final_v23_output_solver_input_allowed": False,
                "legsa_output_solver_input_allowed": False, "go2_truth_claim_allowed": False,
                "synthetic_data_used": False, "semisynthetic_data_used": False,
                "claim_level": degradation.claim_level,
            })
            case_index += 1
    validate_case_manifest(rows)
    return rows


def validate_case_manifest(rows: Iterable[Mapping[str, Any]]) -> None:
    items = tuple(rows)
    ids = tuple(str(row.get("case_id")) for row in items)
    expected = (CLEAN_CASE_ID, *(f"D{d:02d}_seed_{s:02d}" for d in range(1, 61) for s in range(9)))
    if len(items) != CASE_COUNT or ids != expected or len(set(ids)) != CASE_COUNT:
        raise CaseManifestError("case manifest is not the exact ordered 541-row closure")
    if sum(row.get("degradation_type_id") != "CLEAN" for row in items) != DEGRADED_CASE_COUNT:
        raise CaseManifestError("degraded case count is not 540")
    if any("placeholder" in str(row).lower() for row in items):
        raise CaseManifestError("placeholder case is forbidden")
    forbidden_true = ("final_v23_output_solver_input_allowed", "legsa_output_solver_input_allowed", "go2_truth_claim_allowed")
    if any(any(row.get(key) is not False for key in forbidden_true) for row in items):
        raise CaseManifestError("forbidden solver/truth role drifted")
