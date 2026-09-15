"""Four frozen canonical full methods."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


@dataclass(frozen=True)
class MethodProfile:
    method_id: str
    name: str
    effective_profile: str
    flags: Mapping[str, bool]

    @property
    def signature(self) -> tuple[bool, ...]:
        return tuple(self.flags[field] for field in FEATURE_FIELDS)


FEATURE_FIELDS = ("position_update", "dual_yaw", "scheme_c", "receiver_velocity", "raw_doppler", "source_aware", "go2_rp", "go2_hv")
FULL_METHODS = (
    MethodProfile("F01", "single_antenna_EKF", "single_antenna_EKF",
                  dict(position_update=True, dual_yaw=False, scheme_c=False, receiver_velocity=True, raw_doppler=False, source_aware=False, go2_rp=False, go2_hv=False)),
    MethodProfile("F02", "basic_dual_yaw_EKF", "basic_dual_yaw_EKF",
                  dict(position_update=True, dual_yaw=True, scheme_c=False, receiver_velocity=False, raw_doppler=False, source_aware=False, go2_rp=False, go2_hv=False)),
    MethodProfile("F03", "strong_dual_yaw_EKF", "AB0000",
                  dict(position_update=True, dual_yaw=True, scheme_c=True, receiver_velocity=True, raw_doppler=False, source_aware=False, go2_rp=False, go2_hv=False)),
    MethodProfile("F04", "LegSA_Paper_V1", "AB1111",
                  dict(position_update=True, dual_yaw=True, scheme_c=True, receiver_velocity=True, raw_doppler=True, source_aware=True, go2_rp=True, go2_hv=True)),
)


def validate_full_methods(methods: Iterable[MethodProfile] = FULL_METHODS) -> None:
    rows = tuple(methods)
    if tuple(row.method_id for row in rows) != ("F01", "F02", "F03", "F04"):
        raise ValueError("full method registry must be F01..F04")
    if len({row.signature for row in rows}) != 4:
        raise ValueError("four canonical methods must have unique effective flags")
    if any(key in row.name.lower() for row in rows for key in ("qm", "fgo", "contact")):
        raise ValueError("out-of-scope method appeared in canonical full registry")


def validate_tracked_method_contract(path: str | Path) -> None:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    tracked = payload.get("methods") if isinstance(payload, dict) else None
    if not isinstance(tracked, dict): raise ValueError("tracked methods contract missing")
    key_map = {
        "dual_yaw": "enable_dual_yaw", "receiver_velocity": "enable_receiver_velocity",
        "raw_doppler": "enable_raw_doppler", "source_aware": "enable_source_aware",
        "go2_rp": "enable_go2_roll_pitch_prior", "go2_hv": "enable_go2_horizontal_velocity_prior",
    }
    for profile in FULL_METHODS:
        row = tracked.get(profile.name); features = row.get("features") if isinstance(row, dict) else None
        if not isinstance(features, dict): raise ValueError(f"tracked method missing: {profile.name}")
        for internal, external in key_map.items():
            if bool(features.get(external)) != profile.flags[internal]:
                raise ValueError(f"tracked method flag drift: {profile.name}.{external}")
    basic = tracked["basic_dual_yaw_EKF"].get("yaw_contract", {})
    if basic.get("fixed_std_deg") != 1.5 or FULL_METHODS[1].flags["scheme_c"] is not False:
        raise ValueError("basic fixed-std identity drift")


def validate_canonical_full_config(path: str | Path) -> None:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("canonical full-method tracked contract is not a mapping")
    methods = payload.get("methods") if isinstance(payload, dict) else None
    if (
        payload.get("schema_version") != "paper_rebuild.canonical_by2_full_methods.v1"
        or payload.get("stage_id") != "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX"
        or payload.get("case_count") != 541 or payload.get("logical_row_count") != 2164
        or not isinstance(methods, list) or len(methods) != 4
    ):
        raise ValueError("canonical full-method tracked contract header drift")
    expected = [
        (row.method_id, row.name, row.effective_profile, runtime)
        for row, runtime in zip(FULL_METHODS, (
            "single_antenna_EKF", "basic_dual_yaw_EKF",
            "strong_dual_yaw_EKF", "LegSA_Paper_V1",
        ))
    ]
    actual = [
        (row.get("method_id"), row.get("canonical_method_id"), row.get("effective_profile"),
         row.get("execution_profile", row.get("canonical_method_id")))
        for row in methods
    ]
    if actual != expected or payload.get("forbidden_axes") != ["FGO", "multi_state_QM", "QA_fallback", "contact_FK"]:
        raise ValueError("canonical full-method tracked profiles drift")


CASE_QUEUE_FIELDS = (
    "case_family", "degradation_type_id", "degradation_type_name",
    "seed_index", "seed_value", "seed_effective", "independent_realization",
    "anchor_name", "anchor_time_s", "degradation_parameters_json",
)


def build_full_queue(cases: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    case_rows = tuple(cases)
    if len(case_rows) != 541:
        raise ValueError("full queue requires exactly 541 cases")
    validate_full_methods()
    rows: list[dict[str, Any]] = []
    for method in FULL_METHODS:
        for case in case_rows:
            rows.append({
                "logical_id": f"FULL_{method.method_id}_{case['case_id']}",
                "matrix": "full_algorithm", "method_id": method.method_id,
                "method_name": method.name, "effective_profile": method.effective_profile,
                "case_id": case["case_id"], "case_index": case["case_index"],
                "provider_ready": False, "formal": True,
                "execution_alias": False, "alias_of": "",
                "trace_used_online": False, "per_case_tuning": False,
                "metric_driven_rerun": False,
                **{field: case.get(field, "") for field in CASE_QUEUE_FIELDS},
                **method.flags,
            })
    if len(rows) != 2164 or len({row["logical_id"] for row in rows}) != 2164:
        raise ValueError("full queue closure mismatch")
    return rows
