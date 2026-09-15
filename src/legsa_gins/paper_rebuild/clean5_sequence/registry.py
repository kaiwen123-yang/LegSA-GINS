"""CLEAN5 sequence identities and confined paths from an explicit local YAML."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from ..evidence import BY2_BODY_RELATIVE_PATH, BY2_FIX_PREFIX, BY2_TRACE_NAME
from ..paths import PathContractError, guard_path, is_within, legacy_reason, load_yaml_mapping

STAGE_IDS = {
    "BY2": "CLEAN5_BY2_CONTROL_PROBES",
    "BY2H": "CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE",
    "BY2O": "CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE",
}
DATA_MODES = {"BY2": "real_by2_raw", "BY2H": "real_by2h_raw", "BY2O": "real_by2o_raw"}


@dataclass(frozen=True)
class Sequence:
    dataset_id: str
    stage_id: str
    fix_prefix: str
    trace_name: str
    go2_body: str
    role: str
    data_mode: str
    fix_root: Path
    body_path: Path
    trace_path: Path
    probe_dir: Path


@dataclass(frozen=True)
class BundleRegistry:
    raw_root: Path
    clean_root: Path
    code_root: Path
    sequences: dict[str, Sequence]


def _relative(value: object, role: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise PathContractError(f"{role} must be a raw-root-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise PathContractError(f"{role} must be a normalized relative path without parent traversal")
    if legacy_reason(value):
        raise PathContractError(f"{role} crosses the clean legacy denylist")
    return value


def _absolute(value: object, role: str) -> Path:
    if not isinstance(value, str) or not value.strip() or value.startswith("<"):
        raise PathContractError(f"{role} needs an explicit absolute local path")
    if "\\" in value or ":" in value or not Path(value).is_absolute() or ".." in Path(value).parts:
        raise PathContractError(f"{role} must be an absolute POSIX path without parent traversal")
    if legacy_reason(value):
        raise PathContractError(f"{role} crosses the clean legacy denylist")
    path = Path(value)
    resolved = guard_path(path, role=role, allowed_root=path)
    if legacy_reason(resolved):
        raise PathContractError(f"{role} resolves into the clean legacy denylist")
    return resolved


def load_registry(registry_path: str | Path, local_config_path: str | Path,
                  require_sources: bool = True) -> BundleRegistry:
    """Resolve registered inputs without reading raw files or changing CleanPaths."""
    document = load_yaml_mapping(registry_path)
    local = load_yaml_mapping(local_config_path).get("paths")
    records = document.get("sequences")
    if not isinstance(local, Mapping) or not isinstance(records, Mapping):
        raise PathContractError("registry sequences and local paths must be mappings")
    if set(records) != set(STAGE_IDS):
        raise PathContractError("CLEAN5 registry must contain BY2 control, BY2H and BY2O exactly")
    roots = {key: _absolute(local.get(key), f"paths.{key}") for key in ("raw_root", "clean_root", "code_root")}
    raw_root, clean_root, code_root = (roots[key] for key in ("raw_root", "clean_root", "code_root"))
    if is_within(clean_root, raw_root) or is_within(raw_root, clean_root):
        raise PathContractError("clean_root and raw_root must be mutually disjoint")
    if require_sources and (not raw_root.is_dir() or not code_root.is_dir()):
        raise PathContractError("raw_root and code_root must exist")
    sequences = {}
    for dataset, record in records.items():
        fields = {"dataset_id", "stage_id", "fix_prefix", "trace_name", "go2_body", "role", "data_mode"}
        if not isinstance(record, Mapping) or set(record) != fields:
            raise PathContractError(f"{dataset}: registry fields differ from the sequence contract")
        if record["dataset_id"] != dataset or record["stage_id"] != STAGE_IDS[dataset] or record["data_mode"] != DATA_MODES[dataset]:
            raise PathContractError(f"{dataset}: identity, stage or data mode mismatch")
        if not isinstance(record["role"], str) or not record["role"] or (dataset == "BY2" and record["role"] != "control"):
            raise PathContractError(f"{dataset}: invalid role")
        fix_prefix = _relative(record["fix_prefix"], f"{dataset}.fix_prefix")
        body_relative = _relative(record["go2_body"], f"{dataset}.go2_body")
        trace_name = _relative(record["trace_name"], f"{dataset}.trace_name")
        if "/" in trace_name or not trace_name.startswith("trace_") or not trace_name.endswith(".csv"):
            raise PathContractError(f"{dataset}: trace_name must be a trace CSV basename")
        if dataset == "BY2" and (fix_prefix, body_relative, trace_name) != (BY2_FIX_PREFIX, BY2_BODY_RELATIVE_PATH, BY2_TRACE_NAME):
            raise PathContractError("BY2 control must retain evidence.py source identities")
        resolved_inputs = []
        for suffix, relative in (("fix_root", fix_prefix), ("go2_body", body_relative)):
            key = f"{dataset.lower()}_{suffix}"
            supplied = _absolute(local.get(key), f"paths.{key}")
            expected = guard_path(raw_root / relative, role=f"{dataset}.{suffix}", allowed_root=raw_root,
                                  must_exist=require_sources, regular_file=require_sources and suffix == "go2_body")
            supplied = guard_path(supplied, role=f"paths.{key}", allowed_root=raw_root,
                                  must_exist=require_sources, regular_file=require_sources and suffix == "go2_body")
            if legacy_reason(expected) or supplied != expected:
                raise PathContractError(f"paths.{key} differs from its registered raw-relative identity")
            resolved_inputs.append(supplied)
        fix_root, body_path = resolved_inputs
        if require_sources and not fix_root.is_dir():
            raise PathContractError(f"{dataset}.fix_root is not a directory")
        trace_path = guard_path(fix_root / trace_name, role=f"{dataset}.trace", allowed_root=raw_root,
                                must_exist=require_sources, regular_file=require_sources)
        stage_root = clean_root / "stages" / record["stage_id"]
        probe_dir = stage_root if dataset == "BY2" else stage_root / "00_RAW_INVENTORY_AND_PROBES"
        probe_dir = guard_path(probe_dir, role=f"{dataset}.probe_dir", allowed_root=clean_root)
        sequences[dataset] = Sequence(dataset, record["stage_id"], fix_prefix, trace_name, body_relative,
                                      record["role"], record["data_mode"], fix_root, body_path, trace_path, probe_dir)
    return BundleRegistry(raw_root, clean_root, code_root, sequences)
