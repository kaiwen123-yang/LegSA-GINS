"""Nine current-scope internal ablation methods."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from .full_method_registry import CASE_QUEUE_FIELDS, FEATURE_FIELDS, MethodProfile


def _ab(method_id: str, name: str, bits: str) -> MethodProfile:
    if len(bits) != 4 or set(bits) - {"0", "1"}:
        raise ValueError("ablation bits must be RD,SA,RP,HV")
    enabled = tuple(bit == "1" for bit in bits)
    return MethodProfile(method_id, name, f"AB{bits}", {
        "position_update": True, "dual_yaw": True, "scheme_c": True, "receiver_velocity": True,
        "raw_doppler": enabled[0], "source_aware": enabled[1],
        "go2_rp": enabled[2], "go2_hv": enabled[3],
    })


ABLATION_METHODS = (
    _ab("A01", "LegSA_full", "1111"),
    _ab("A02", "strong_backbone", "0000"),
    _ab("A03", "LegSA_no_raw_doppler", "0111"),
    _ab("A04", "LegSA_no_source_aware", "1011"),
    _ab("A05", "LegSA_no_go2_roll_pitch", "1101"),
    _ab("A06", "LegSA_no_go2_horizontal_velocity", "1110"),
    _ab("A07", "LegSA_no_go2_priors", "1100"),
    _ab("A08", "Raw_Doppler_only_on_strong", "1000"),
    _ab("A09", "Source_aware_only_on_strong", "0100"),
)
FULL_ALIAS = {"A01": "F04", "A02": "F03"}


def validate_ablation_methods(methods: Iterable[MethodProfile] = ABLATION_METHODS) -> None:
    rows = tuple(methods)
    if tuple(row.method_id for row in rows) != tuple(f"A{i:02d}" for i in range(1, 10)):
        raise ValueError("ablation registry must be A01..A09")
    if len({row.signature for row in rows}) != 9:
        raise ValueError("nine internal ablations must have unique effective flags")
    if any(term in row.name.lower() for row in rows for term in ("fgo", "multi_state_qm", "qa_fallback", "contact")):
        raise ValueError("out-of-scope axis appeared in internal ablations")


def validate_tracked_ablation_contract(path: str | Path) -> None:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("bit_order") != ["RD", "SA", "RP", "HV"]:
        raise ValueError("tracked ablation bit order drifted")
    variants = {row["configuration_id"]: row for row in payload.get("variants", ())}
    for profile in ABLATION_METHODS:
        row = variants.get(profile.effective_profile)
        if not isinstance(row, dict) or row.get("bit_string") != profile.effective_profile[2:]:
            raise ValueError(f"tracked ablation profile drift: {profile.effective_profile}")


def validate_canonical_ablation_config(path: str | Path) -> None:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("canonical ablation tracked contract is not a mapping")
    methods = payload.get("methods")
    if (
        payload.get("schema_version") != "paper_rebuild.canonical_by2_internal_ablation.v1"
        or payload.get("stage_id") != "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX"
        or payload.get("case_count") != 541 or payload.get("logical_row_count") != 4869
        or payload.get("bit_order") != ["RD", "SA", "RP", "HV"]
        or not isinstance(methods, list) or len(methods) != 9
    ):
        raise ValueError("canonical internal-ablation tracked contract header drift")
    actual = [(row.get("method_id"), row.get("name"), row.get("effective_profile")) for row in methods]
    expected = [(row.method_id, row.name, row.effective_profile) for row in ABLATION_METHODS]
    if actual != expected:
        raise ValueError("canonical internal-ablation profiles drift")
    alias = {row.get("method_id"): row.get("full_alias_method_id") for row in methods if row.get("full_alias_method_id")}
    if alias != FULL_ALIAS or payload.get("forbidden_axes") != ["FGO", "multi_state_QM", "QA_fallback", "contact_FK"]:
        raise ValueError("canonical internal-ablation alias/forbidden-axis drift")


def build_ablation_queue(cases: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    case_rows = tuple(cases)
    if len(case_rows) != 541:
        raise ValueError("ablation queue requires exactly 541 cases")
    validate_ablation_methods()
    rows: list[dict[str, Any]] = []
    for method in ABLATION_METHODS:
        for case in case_rows:
            full_alias = FULL_ALIAS.get(method.method_id)
            rows.append({
                "logical_id": f"ABLATION_{method.method_id}_{case['case_id']}",
                "matrix": "internal_ablation", "method_id": method.method_id,
                "method_name": method.name, "effective_profile": method.effective_profile,
                "case_id": case["case_id"], "case_index": case["case_index"],
                "provider_ready": False, "formal": True,
                "execution_alias": full_alias is not None,
                "alias_of": f"FULL_{full_alias}_{case['case_id']}" if full_alias else "",
                "trace_used_online": False, "per_case_tuning": False,
                "metric_driven_rerun": False,
                **{field: case.get(field, "") for field in CASE_QUEUE_FIELDS},
                **method.flags,
            })
    if len(rows) != 4869 or len({row["logical_id"] for row in rows}) != 4869:
        raise ValueError("internal ablation queue closure mismatch")
    return rows
