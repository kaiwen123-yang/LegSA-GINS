"""Deterministic, deduplicated 110-run CLEAN2 formal registry."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .clean2_ablation import AblationCatalog, AblationVariant, load_ablation_catalog
from .clean2_classic_cases import ClassicCaseCatalog, ClassicCaseSpec, load_classic_case_catalog
from .manifest import sha256_text


REGISTRY_FIELDS = (
    "run_id",
    "case_id",
    "result_namespace",
    "structural_method",
    "ablation_id",
    "feature_RD",
    "feature_SA",
    "feature_RP",
    "feature_HV",
    "provider_bundle_hash",
    "runtime_config_hash",
    "executable_hash",
    "run_order",
    "formal",
    "alias_roles",
)
CANONICAL_METHODS = (
    "single_antenna_EKF",
    "basic_dual_yaw_EKF",
    "strong_dual_yaw_EKF",
    "LegSA_Paper_V1",
)
CANONICAL_FEATURES = {
    "single_antenna_EKF": (False, False, False, False),
    "basic_dual_yaw_EKF": (False, False, False, False),
    "strong_dual_yaw_EKF": (False, False, False, False),
    "LegSA_Paper_V1": (True, True, True, True),
}
SENTINEL_CODES = ("C01", "C04", "C07", "C10", "C11", "C15")
SENTINEL_LOO = (
    ("LOO_NO_RD", "AB0111"),
    ("LOO_NO_SA", "AB1011"),
    ("LOO_NO_RP", "AB1101"),
    ("LOO_NO_HV", "AB1110"),
)


class Clean2RunRegistryError(ValueError):
    """The formal process registry violates count, order, or deduplication."""


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _namespace(case: ClassicCaseSpec) -> str:
    return (
        "BY2_REAL_CLEAN_MODULE_ABLATION"
        if case.case_code == "C00"
        else "BY2_CONTROLLED_DUAL_YAW_DEGRADATION"
    )


def _run_id(order: int, case: ClassicCaseSpec, label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", label).strip("_")
    return f"R{order:03d}_{case.case_code}_{safe}"


def _semantic_runtime_hash(row: Mapping[str, Any]) -> str:
    frozen = {
        key: row[key]
        for key in (
            "case_id",
            "result_namespace",
            "structural_method",
            "ablation_id",
            "feature_RD",
            "feature_SA",
            "feature_RP",
            "feature_HV",
            "provider_bundle_hash",
            "executable_hash",
        )
    }
    return sha256_text(json.dumps(frozen, sort_keys=True, separators=(",", ":")))


def _append_row(
    rows: list[dict[str, Any]],
    *,
    case: ClassicCaseSpec,
    structural_method: str,
    ablation_id: str,
    features: Sequence[bool],
    provider_bundle_hash: str,
    executable_hash: str,
    alias_roles: Sequence[str],
    label: str,
) -> None:
    order = len(rows) + 1
    if len(features) != 4 or not all(isinstance(value, bool) for value in features):
        raise Clean2RunRegistryError("CLEAN2 feature vector must contain four booleans")
    row: dict[str, Any] = {
        "run_id": _run_id(order, case, label),
        "case_id": case.case_id,
        "result_namespace": _namespace(case),
        "structural_method": structural_method,
        "ablation_id": ablation_id,
        "feature_RD": features[0],
        "feature_SA": features[1],
        "feature_RP": features[2],
        "feature_HV": features[3],
        "provider_bundle_hash": provider_bundle_hash,
        "runtime_config_hash": "",
        "executable_hash": executable_hash,
        "run_order": order,
        "formal": True,
        "alias_roles": ";".join(alias_roles),
    }
    row["runtime_config_hash"] = _semantic_runtime_hash(row)
    rows.append(row)


def build_run_registry_rows(
    ablation: AblationCatalog,
    classic: ClassicCaseCatalog,
    *,
    provider_bundle_hashes: Mapping[str, str],
    executable_hash: str,
) -> list[dict[str, Any]]:
    """Build the frozen phase order: 4 gate + 14 factorial + 68 canonical + 24 LOO."""

    expected_case_ids = {case.case_id for case in classic.cases}
    if set(provider_bundle_hashes) != expected_case_ids:
        raise Clean2RunRegistryError("Provider bundle hash registry must cover exactly 18 cases")
    if not _is_sha256(executable_hash) or not all(
        _is_sha256(value) for value in provider_bundle_hashes.values()
    ):
        raise Clean2RunRegistryError("Registry executable/provider SHA-256 is invalid")
    c00 = classic.case("C00")
    rows: list[dict[str, Any]] = []

    # 结构 gate 必须先完成；AB0000/AB1111同时承担strong/full canonical别名。
    for method in CANONICAL_METHODS[:2]:
        _append_row(
            rows,
            case=c00,
            structural_method=method,
            ablation_id="",
            features=CANONICAL_FEATURES[method],
            provider_bundle_hash=provider_bundle_hashes[c00.case_id],
            executable_hash=executable_hash,
            alias_roles=(f"canonical_{method}", "C00_structural_gate"),
            label=method,
        )
    for ablation_id, alias in (("AB0000", "canonical_strong"), ("AB1111", "canonical_LegSA")):
        variant = ablation.variant(ablation_id)
        _append_row(
            rows,
            case=c00,
            structural_method="strong_dual_yaw_EKF",
            ablation_id=variant.ablation_id,
            features=variant.features,
            provider_bundle_hash=provider_bundle_hashes[c00.case_id],
            executable_hash=executable_hash,
            alias_roles=(alias, "C00_structural_gate", "ablation_configuration"),
            label=variant.ablation_id,
        )
    for variant in ablation.variants:
        if variant.ablation_id in {"AB0000", "AB1111"}:
            continue
        _append_row(
            rows,
            case=c00,
            structural_method="strong_dual_yaw_EKF",
            ablation_id=variant.ablation_id,
            features=variant.features,
            provider_bundle_hash=provider_bundle_hashes[c00.case_id],
            executable_hash=executable_hash,
            alias_roles=("C00_factorial", "ablation_configuration"),
            label=variant.ablation_id,
        )

    for case in classic.cases[1:]:
        for method in CANONICAL_METHODS:
            _append_row(
                rows,
                case=case,
                structural_method=method,
                ablation_id="",
                features=CANONICAL_FEATURES[method],
                provider_bundle_hash=provider_bundle_hashes[case.case_id],
                executable_hash=executable_hash,
                alias_roles=(f"canonical_{method}", "controlled_pilot"),
                label=method,
            )

    for case_code in SENTINEL_CODES:
        case = classic.case(case_code)
        for alias, ablation_id in SENTINEL_LOO:
            variant = ablation.variant(ablation_id)
            _append_row(
                rows,
                case=case,
                structural_method="strong_dual_yaw_EKF",
                ablation_id=ablation_id,
                features=variant.features,
                provider_bundle_hash=provider_bundle_hashes[case.case_id],
                executable_hash=executable_hash,
                alias_roles=(alias, "sentinel_LOO", "ablation_configuration"),
                label=alias,
            )
    validate_run_registry_rows(rows)
    return rows


def effective_config_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row["case_id"],
        row["structural_method"],
        bool(row["feature_RD"]),
        bool(row["feature_SA"]),
        bool(row["feature_RP"]),
        bool(row["feature_HV"]),
    )


def validate_run_registry_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(rows) != 110:
        raise Clean2RunRegistryError(f"CLEAN2 unique formal run count is {len(rows)}, expected 110")
    run_ids = [str(row.get("run_id") or "") for row in rows]
    if len(set(run_ids)) != 110 or any(not value for value in run_ids):
        raise Clean2RunRegistryError("CLEAN2 run ids are empty or duplicated")
    if [int(row.get("run_order") or 0) for row in rows] != list(range(1, 111)):
        raise Clean2RunRegistryError("CLEAN2 run_order is not contiguous 1..110")
    keys = [effective_config_key(row) for row in rows]
    duplicate_count = len(keys) - len(set(keys))
    if duplicate_count:
        raise Clean2RunRegistryError("CLEAN2 effective process registry contains duplicates")
    if any(row.get("formal") is not True for row in rows):
        raise Clean2RunRegistryError("CLEAN2 registry contains a non-formal row")
    if any(
        not _is_sha256(row.get(field))
        for row in rows
        for field in ("provider_bundle_hash", "runtime_config_hash", "executable_hash")
    ):
        raise Clean2RunRegistryError("CLEAN2 registry contains a malformed SHA-256")
    if [row["structural_method"] for row in rows[:4]] != [
        "single_antenna_EKF",
        "basic_dual_yaw_EKF",
        "strong_dual_yaw_EKF",
        "strong_dual_yaw_EKF",
    ] or [row["ablation_id"] for row in rows[:4]] != ["", "", "AB0000", "AB1111"]:
        raise Clean2RunRegistryError("CLEAN2 C00 structural gate order drifted")
    counts = {
        "C00_canonical_single_basic": 2,
        "C00_factorial": sum(row["case_id"].startswith("C00_") and bool(row["ablation_id"]) for row in rows),
        "C01_C17_canonical_four": sum(
            not row["case_id"].startswith("C00_") and not row["ablation_id"] for row in rows
        ),
        "sentinel_extra_LOO": sum("sentinel_LOO" in str(row["alias_roles"]) for row in rows),
    }
    if counts != {
        "C00_canonical_single_basic": 2,
        "C00_factorial": 16,
        "C01_C17_canonical_four": 68,
        "sentinel_extra_LOO": 24,
    }:
        raise Clean2RunRegistryError(f"CLEAN2 run class counts drifted: {counts}")
    return {
        "schema_version": "paper_rebuild.clean2_run_registry_audit.v1",
        "unique_run_count": 110,
        "duplicate_effective_config_count": 0,
        "counts": counts,
        "passed": True,
    }


def write_run_registry(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> Path:
    validate_run_registry_rows(rows)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REGISTRY_FIELDS))
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for field in ("feature_RD", "feature_SA", "feature_RP", "feature_HV", "formal"):
                encoded[field] = "true" if row[field] is True else "false"
            writer.writerow({field: encoded[field] for field in REGISTRY_FIELDS})
    return destination


def _csv_bool(value: Any, field: str) -> bool:
    normalized = str(value).strip().casefold()
    if normalized not in {"true", "false"}:
        raise Clean2RunRegistryError(f"Registry boolean is invalid: {field}")
    return normalized == "true"


def read_run_registry(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path).resolve(strict=True)
    with source.open("r", encoding="utf-8", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if tuple(raw) != REGISTRY_FIELDS:
            raise Clean2RunRegistryError("CLEAN2 registry columns/order mismatch")
        row: dict[str, Any] = dict(raw)
        row["run_order"] = int(raw["run_order"])
        for field in ("feature_RD", "feature_SA", "feature_RP", "feature_HV", "formal"):
            row[field] = _csv_bool(raw[field], field)
        rows.append(row)
    validate_run_registry_rows(rows)
    return rows


def build_and_write_run_registry(
    *,
    ablation_config: str | Path,
    classic_mapping_config: str | Path,
    provider_bundle_hashes: Mapping[str, str],
    executable_hash: str,
    output_path: str | Path,
) -> list[dict[str, Any]]:
    ablation = load_ablation_catalog(ablation_config)
    classic = load_classic_case_catalog(classic_mapping_config)
    rows = build_run_registry_rows(
        ablation,
        classic,
        provider_bundle_hashes=provider_bundle_hashes,
        executable_hash=executable_hash,
    )
    write_run_registry(output_path, rows)
    return rows
