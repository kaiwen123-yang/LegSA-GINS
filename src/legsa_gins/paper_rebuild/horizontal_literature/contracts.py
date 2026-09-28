"""Fail-closed loaders for the Phase 1 horizontal-literature contracts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Phase1Contract:
    baseline_length_m: float
    methods: tuple[str, ...]
    cases: tuple[str, ...]
    trace_mode: str = "disabled"


def _mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"contract is not a mapping: {path}")
    return value


def load_phase1_contract(config_dir: Path) -> Phase1Contract:
    methods_doc = _mapping(config_dir / "EXTERNAL_METHOD_CONTRACTS_V1.yaml")
    schema_doc = _mapping(config_dir / "STANDARD_HEADING_STREAM_SCHEMA_V1.yaml")
    if methods_doc.get("schema_version") != "horizontal_literature.external_methods.v1":
        raise ContractError("unsupported external-method contract schema")
    if schema_doc.get("schema_version") != "horizontal_literature.heading_stream.v1":
        raise ContractError("unsupported heading-stream schema")
    methods = tuple(methods_doc.get("enabled_methods", ()))
    cases = tuple(methods_doc.get("enabled_cases", ()))
    if methods != ("EXT01_CLAMBDA",) or cases != ("C00",):
        raise ContractError("Phase 1 must enable exactly EXT01_CLAMBDA/C00")
    ext = methods_doc.get("methods", {}).get("EXT01_CLAMBDA", {})
    physical = ext.get("physical_transform", {})
    expected = {
        "gnss1": "right", "gnss2": "left", "baseline": "GNSS2_MINUS_GNSS1",
        "body_axis": "+Y_left", "frame": "NED", "body_yaw": "wrap(beta + 90 deg)",
    }
    if any(physical.get(k) != v for k, v in expected.items()) or not physical.get("wrap_safe"):
        raise ContractError("physical antenna/frame transform is not locked")
    length = float(ext.get("baseline_length_m", -1.0))
    if length != 0.350:
        raise ContractError("baseline length must be exactly 0.350 m")
    if methods_doc.get("evaluation") != "NOT_EVALUATED":
        raise ContractError("Phase 1 evaluation must remain NOT_EVALUATED")
    return Phase1Contract(length, methods, cases)


def load_compatibility(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1 or rows[0] != {
        "case_id": "C00", "method_id": "EXT01_CLAMBDA", "enabled": "true",
        "data_mode": "real_by2_raw", "trace_mode": "disabled",
        "evaluation_status": "NOT_EVALUATED",
    }:
        raise ContractError("compatibility registry is not the locked Phase 1 row")
    return rows


def required_manifest_fields(config_dir: Path) -> frozenset[str]:
    doc = _mapping(config_dir / "EXTERNAL_METHOD_CONTRACTS_V1.yaml")
    fields = doc.get("manifest_required_fields")
    if not isinstance(fields, list) or not all(isinstance(x, str) for x in fields):
        raise ContractError("manifest_required_fields must be a string list")
    return frozenset(fields)
