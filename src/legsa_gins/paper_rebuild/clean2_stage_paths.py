"""Exact CLEAN2 stage/output guards resolved from one ignored local config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .paths import (
    CleanPaths,
    PathContractError,
    guard_path,
    is_within,
    legacy_reason,
    load_clean_paths,
    load_yaml_mapping,
)


STAGE_ID = "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18"
SLOT_NAMES: Mapping[str, str] = {
    "authorization": "00_AUTHORIZATION",
    "git_freeze": "01_GIT_FREEZE",
    "protocols": "02_PROTOCOLS",
    "raw_audits": "03_RAW_AUDITS",
    "base_provider": "04_BASE_PROVIDER",
    "case_providers": "05_CASE_PROVIDERS",
    "run_registry": "06_RUN_REGISTRY",
    "formal_runs": "07_FORMAL_RUNS",
    "output_seal": "08_OUTPUT_SEAL",
    "offline_evaluation": "09_OFFLINE_EVALUATION",
    "ablation_analysis": "10_ABLATION_ANALYSIS",
    "classic_analysis": "11_CLASSIC18_ANALYSIS",
    "diagnostic_figures": "12_DIAGNOSTIC_FIGURES",
    "audits": "13_AUDITS",
    "final_evidence": "14_FINAL_EVIDENCE",
}


@dataclass(frozen=True)
class Clean2StagePaths:
    config_path: Path
    clean: CleanPaths
    export_root: Path
    stage_root: Path

    def slot(self, name: str) -> Path:
        try:
            component = SLOT_NAMES[name]
        except KeyError as exc:
            raise PathContractError(f"Unknown CLEAN2 evidence slot: {name}") from exc
        return self.stage_root / component


def _absolute_config_path(raw: object, *, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise PathContractError(f"Local configuration must set paths.{field}")
    path = Path(raw).expanduser()
    if not path.is_absolute() or legacy_reason(path):
        raise PathContractError(f"paths.{field} must be an absolute non-legacy path")
    return path.resolve(strict=False)


def _reject_existing_symlink_chain(path: Path, anchor: Path) -> None:
    if not is_within(path, anchor):
        raise PathContractError("CLEAN2 path escaped its configured anchor")
    relative = path.relative_to(anchor)
    current = anchor
    if current.is_symlink():
        raise PathContractError("CLEAN2 configured anchor is a symlink")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise PathContractError("CLEAN2 stage path crosses a symlink")


def load_clean2_stage_paths(
    config_path: str | Path, *, require_sources: bool = True
) -> Clean2StagePaths:
    """Resolve exact stage/export identities and reject raw/protected-root aliases."""

    config = Path(config_path).expanduser().resolve(strict=True)
    clean = load_clean_paths(config, require_sources=require_sources)
    payload = load_yaml_mapping(config)
    raw_paths = payload.get("paths")
    if not isinstance(raw_paths, Mapping):
        raise PathContractError("Local CLEAN2 config lacks paths mapping")
    for field in (
        "code_root",
        "raw_root",
        "clean_root",
        "provider_root",
        "runtime_root",
        "export_root",
    ):
        raw_value = raw_paths.get(field)
        if isinstance(raw_value, str) and Path(raw_value).expanduser().is_symlink():
            raise PathContractError(f"Configured paths.{field} may not be a symlink")
    export_root = _absolute_config_path(raw_paths.get("export_root"), field="export_root")
    stage_root = (clean.clean_root / "stages" / STAGE_ID).resolve(strict=False)
    expected_provider = stage_root / SLOT_NAMES["base_provider"]
    expected_runtime = stage_root / SLOT_NAMES["formal_runs"]
    if clean.provider_root != expected_provider or clean.runtime_root != expected_runtime:
        raise PathContractError("CLEAN2 local provider/runtime roots do not match the exact stage tree")
    protected = (clean.raw_root, clean.clean_root, clean.code_root)
    if any(
        is_within(export_root, root) or is_within(root, export_root)
        for root in protected
    ):
        raise PathContractError("CLEAN2 export root must be disjoint from raw/clean/code roots")
    _reject_existing_symlink_chain(stage_root, clean.clean_root)
    if export_root.exists() and (export_root.is_symlink() or not export_root.is_dir()):
        raise PathContractError("CLEAN2 export root is not a real directory")
    return Clean2StagePaths(config, clean, export_root, stage_root)


def guard_clean2_stage_path(
    paths: Clean2StagePaths,
    value: str | Path,
    *,
    slot: str,
    role: str,
    exact_name: str | None = None,
    direct_child: bool = False,
    must_exist: bool = False,
    regular_file: bool = False,
) -> Path:
    """Confine a formal read/write target to one named CLEAN2 evidence slot."""

    allowed = paths.slot(slot)
    guarded = guard_path(
        value,
        role=role,
        allowed_root=allowed,
        must_exist=must_exist,
        regular_file=regular_file,
    )
    _reject_existing_symlink_chain(guarded, paths.clean.clean_root)
    if exact_name is not None and guarded != allowed / exact_name:
        raise PathContractError(f"{role} must use exact CLEAN2 evidence filename {exact_name}")
    if direct_child and guarded.parent != allowed:
        raise PathContractError(f"{role} must be a direct child of {allowed.name}")
    if guarded in {
        paths.clean.raw_root,
        paths.clean.clean_root,
        paths.clean.code_root,
        paths.stage_root,
    }:
        raise PathContractError(f"{role} may not target a protected root")
    return guarded


def guard_clean2_export_root(paths: Clean2StagePaths, value: str | Path) -> Path:
    """Require the exact ignored-config export root, never a caller-selected substitute."""

    candidate = Path(value).expanduser().resolve(strict=False)
    if candidate != paths.export_root:
        raise PathContractError("CLEAN2 final export root differs from ignored local config")
    if candidate.is_symlink() or not candidate.is_dir():
        raise PathContractError("CLEAN2 final export root is missing or a symlink")
    return candidate
