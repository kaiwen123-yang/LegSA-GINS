"""Explicit local-path loading and clean/legacy separation guards."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Mapping


class PathContractError(ValueError):
    """Raised when a path crosses the clean-rebuild contract."""


# Component checks deliberately avoid embedding any machine-specific absolute path.
LEGACY_COMPONENTS = frozenset(
    {
        "运行结果",
        ".legsa_runtime",
        "by2-huitu",
        "by3-huiti",
        "n9b2_full_matrix",
    }
)
LEGACY_SEQUENCES = (
    ("reports", "stages"),
    ("experiments",),
    ("literature_comparisons",),
    ("00_ai_context",),
)
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True)
class CleanPaths:
    """Resolved paths injected by the ignored local YAML file."""

    config_path: Path
    code_root: Path
    raw_root: Path
    by2_fix_root: Path
    by2_go2_body: Path
    clean_root: Path
    provider_root: Path
    runtime_root: Path

    @property
    def raw_hash_lock(self) -> Path:
        return self.clean_root / "01_RAW_HASH_LOCK" / "RAW_FILE_HASH_LOCK.csv"

    @property
    def port_core_exe(self) -> Path:
        return self.code_root / "build" / "cpp" / "legsa_v23_port_core_demo"


def _simple_scalar(text: str) -> Any:
    value = text.strip()
    if not value:
        return {}
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _fallback_yaml_mapping(text: str) -> dict[str, Any]:
    """Parse the small mapping-only subset used by local path configuration."""

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise PathContractError(f"Unsupported local YAML syntax on line {number}")
        key, raw_value = stripped.split(":", 1)
        key = key.strip().strip('"\'')
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise PathContractError(f"Invalid local YAML indentation on line {number}")
        parent = stack[-1][1]
        value = _simple_scalar(raw_value)
        parent[key] = value
        if isinstance(value, dict):
            stack.append((indent, value))
    return root


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """Load a YAML/JSON mapping without path or environment fallbacks."""

    source = Path(path).expanduser()
    if not source.is_file():
        raise PathContractError(f"Explicit local config does not exist: {source}")
    text = source.read_text(encoding="utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError:
            parsed = _fallback_yaml_mapping(text)
        else:
            parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise PathContractError("Local configuration must be a mapping")
    return parsed


def _path_value(mapping: Mapping[str, Any], key: str) -> Path:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip() or value.strip().startswith("<"):
        raise PathContractError(f"Local configuration must set paths.{key}")
    if WINDOWS_ABSOLUTE_RE.match(value.strip()):
        raise PathContractError(f"WSL clean runner cannot consume a Windows path for paths.{key}")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise PathContractError(f"paths.{key} must be absolute in the ignored local config")
    return path.resolve(strict=False)


def is_within(path: str | Path, root: str | Path) -> bool:
    candidate = Path(path).resolve(strict=False)
    anchor = Path(root).resolve(strict=False)
    return candidate == anchor or anchor in candidate.parents


def legacy_reason(path: str | Path) -> str | None:
    """Return the forbidden legacy component/sequence, if one is present."""

    raw = str(path)
    if WINDOWS_ABSOLUTE_RE.match(raw):
        return "windows_absolute_path"
    parts = tuple(part.casefold() for part in PurePath(raw).parts)
    for component in LEGACY_COMPONENTS:
        if component.casefold() in parts:
            return f"legacy_component:{component}"
    for sequence in LEGACY_SEQUENCES:
        folded = tuple(part.casefold() for part in sequence)
        width = len(folded)
        if any(parts[index : index + width] == folded for index in range(len(parts) - width + 1)):
            return "legacy_sequence:" + "/".join(sequence)
    return None


def guard_path(
    path: str | Path,
    *,
    role: str,
    allowed_root: str | Path,
    reject_legacy: bool = True,
    must_exist: bool = False,
    regular_file: bool = False,
) -> Path:
    """Resolve and confine a path, including symlink-target confinement."""

    raw_path = Path(path).expanduser()
    if not raw_path.is_absolute():
        raise PathContractError(f"{role} must be an absolute path from local config")
    if reject_legacy:
        reason = legacy_reason(raw_path)
        if reason:
            raise PathContractError(f"{role} crosses clean legacy denylist: {reason}")
    resolved = raw_path.resolve(strict=False)
    root = Path(allowed_root).expanduser().resolve(strict=False)
    if not is_within(resolved, root):
        raise PathContractError(f"{role} resolves outside its allowed root")
    if must_exist and not resolved.exists():
        raise PathContractError(f"{role} does not exist")
    if regular_file and not resolved.is_file():
        raise PathContractError(f"{role} must be a regular file")
    return resolved


def load_clean_paths(config_path: str | Path, *, require_sources: bool = True) -> CleanPaths:
    """Load all clean paths from one explicit ignored local config."""

    config = Path(config_path).expanduser().resolve(strict=False)
    data = load_yaml_mapping(config)
    raw_mapping = data.get("paths")
    if not isinstance(raw_mapping, Mapping):
        raise PathContractError("Local configuration must contain a paths mapping")

    code_root = _path_value(raw_mapping, "code_root")
    raw_root = _path_value(raw_mapping, "raw_root")
    by2_fix_root = _path_value(raw_mapping, "by2_fix_root")
    by2_go2_body = _path_value(raw_mapping, "by2_go2_body")
    clean_root = _path_value(raw_mapping, "clean_root")
    provider_root = _path_value(raw_mapping, "provider_root")
    runtime_root = _path_value(raw_mapping, "runtime_root")

    if legacy_reason(code_root):
        raise PathContractError("code_root may not be inside a legacy runtime tree")
    if legacy_reason(clean_root):
        raise PathContractError("clean_root crosses the legacy denylist")
    if is_within(clean_root, raw_root) or is_within(raw_root, clean_root):
        raise PathContractError("clean_root and raw_root must be mutually disjoint")
    guard_path(by2_fix_root, role="BY2 fix source", allowed_root=raw_root, must_exist=require_sources)
    guard_path(
        by2_go2_body,
        role="BY2 Go2 body source",
        allowed_root=raw_root,
        must_exist=require_sources,
        regular_file=require_sources,
    )
    guard_path(provider_root, role="clean provider root", allowed_root=clean_root)
    guard_path(runtime_root, role="clean runtime root", allowed_root=clean_root)
    if is_within(provider_root, runtime_root) or is_within(runtime_root, provider_root):
        raise PathContractError("provider_root and runtime_root must be mutually disjoint")
    if provider_root.name == "CLEAN1_BY2_CLEAN_NORMAL_V1" or runtime_root.name == "CLEAN1_BY2_CLEAN_NORMAL_V1":
        if provider_root != clean_root / "04_PROVIDER_FREEZE" / "CLEAN1_BY2_CLEAN_NORMAL_V1":
            raise PathContractError("CLEAN1 provider_root exact suffix mismatch")
        if runtime_root != clean_root / "05_BY2_CLEAN" / "CLEAN1_BY2_CLEAN_NORMAL_V1":
            raise PathContractError("CLEAN1 runtime_root exact suffix mismatch")
    if require_sources:
        if not code_root.is_dir():
            raise PathContractError("paths.code_root is missing")
        if not raw_root.is_dir():
            raise PathContractError("paths.raw_root is missing")
        if not by2_fix_root.is_dir():
            raise PathContractError("paths.by2_fix_root is missing")

    return CleanPaths(
        config_path=config,
        code_root=code_root,
        raw_root=raw_root,
        by2_fix_root=by2_fix_root,
        by2_go2_body=by2_go2_body,
        clean_root=clean_root,
        provider_root=provider_root,
        runtime_root=runtime_root,
    )


def assert_clean1_path_contract(paths: CleanPaths, expected_code_root: str | Path) -> None:
    """Bind every CLEAN1 entrypoint to this exact worktree and frozen root suffixes."""

    # Local import avoids a module-load cycle; the registry is the single exact
    # BY2 relative-path source used by provider and hash-lock validation.
    from .evidence import BY2_BODY_RELATIVE_PATH, BY2_FIX_PREFIX

    expected_code = Path(expected_code_root).resolve(strict=True)
    if paths.code_root != expected_code:
        raise PathContractError("CLEAN1 paths.code_root is not the executing worktree")
    expected_provider = (
        paths.clean_root / "04_PROVIDER_FREEZE" / "CLEAN1_BY2_CLEAN_NORMAL_V1"
    )
    expected_runtime = (
        paths.clean_root / "05_BY2_CLEAN" / "CLEAN1_BY2_CLEAN_NORMAL_V1"
    )
    if paths.provider_root != expected_provider:
        raise PathContractError("CLEAN1 provider_root exact suffix mismatch")
    if paths.runtime_root != expected_runtime:
        raise PathContractError("CLEAN1 runtime_root exact suffix mismatch")
    if paths.by2_fix_root != (paths.raw_root / BY2_FIX_PREFIX).resolve(strict=False):
        raise PathContractError("CLEAN1 by2_fix_root does not match the canonical lock path")
    if paths.by2_go2_body != (paths.raw_root / BY2_BODY_RELATIVE_PATH).resolve(strict=False):
        raise PathContractError("CLEAN1 by2_go2_body does not match the canonical lock path")
