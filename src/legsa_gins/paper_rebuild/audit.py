"""Evidence-bounded audit for one clean runtime and optional export package."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .manifest import (
    git_code_state,
    read_hash_lock,
    sha256_file,
    validate_run_manifest,
    verify_raw_sources,
)
from .paths import CleanPaths, guard_path, legacy_reason


LOCAL_POSIX_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|mnt|media)/[^\s'\"`]+")
LOCAL_WINDOWS_RE = re.compile(r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/][^\r\n'\"`]+")
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".toml", ".log"}


def _row(check: str, passed: bool, details: str = "") -> dict[str, str]:
    return {"check": check, "status": "PASS" if passed else "FAIL", "details": details}


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain an object")
    return payload


def _iter_export_text(root: Path) -> Iterable[tuple[str, str]]:
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix.casefold() in TEXT_SUFFIXES:
            yield relative, path.read_text(encoding="utf-8", errors="replace")
        elif path.suffix.casefold() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if Path(info.filename).suffix.casefold() in TEXT_SUFFIXES:
                        yield f"{relative}!{info.filename}", archive.read(info).decode("utf-8", errors="replace")


def audit_clean_runtime(
    paths: CleanPaths,
    runtime_dir: str | Path,
    *,
    export_root: str | Path | None = None,
) -> list[dict[str, str]]:
    runtime = guard_path(runtime_dir, role="clean runtime audit target", allowed_root=paths.clean_root, must_exist=True)
    rows: list[dict[str, str]] = []
    required = [
        "RUN_MANIFEST.json",
        "LegSA_PORT_NAV.nav",
        "LegSA_PORT_STD.csv",
        "EVAL_NAV.csv",
        "source_role.json",
        "provider_lineage.json",
        "eval_metrics.json",
        "terminal_status.txt",
    ]
    missing = [name for name in required if not (runtime / name).is_file() or (runtime / name).stat().st_size == 0]
    rows.append(_row("required_runtime_files", not missing, ",".join(missing)))
    if missing and "RUN_MANIFEST.json" in missing:
        return rows

    try:
        manifest = _json(runtime / "RUN_MANIFEST.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        rows.append(_row("run_manifest_parse", False, str(exc)))
        return rows
    issues = validate_run_manifest(manifest, require_pass=True)
    rows.append(_row("run_manifest_contract", not issues, ";".join(issues)))

    try:
        lock = read_hash_lock(paths.raw_hash_lock)
        verified = verify_raw_sources(paths.raw_root, manifest.get("raw_source_hashes", {}).keys(), lock)
        raw_match = verified == manifest.get("raw_source_hashes")
        rows.append(_row("raw_hash_lock_match", raw_match, "" if raw_match else "manifest/hash-lock mismatch"))
    except Exception as exc:  # noqa: BLE001 - audit must report all independent failures.
        rows.append(_row("raw_hash_lock_match", False, str(exc)))

    provider_relpaths = manifest.get("provider_relpaths")
    provider_hashes = manifest.get("provider_hashes")
    provider_issues: list[str] = []
    if not isinstance(provider_relpaths, dict) or not isinstance(provider_hashes, dict):
        provider_issues.append("provider mappings missing")
    else:
        for role, relative in provider_relpaths.items():
            try:
                candidate = guard_path(
                    paths.provider_root / str(relative),
                    role=f"provider {role}",
                    allowed_root=paths.clean_root,
                    must_exist=True,
                    regular_file=True,
                )
                if sha256_file(candidate) != provider_hashes.get(role):
                    provider_issues.append(f"hash_mismatch:{role}")
            except Exception as exc:  # noqa: BLE001
                provider_issues.append(f"{role}:{exc}")
    rows.append(_row("provider_hash_lineage", not provider_issues, ";".join(provider_issues)))

    config_path = runtime / "runtime_config" / "CLEAN_RUNTIME_CONFIG.yaml"
    dependency_issues: list[str] = []
    if not config_path.is_file():
        dependency_issues.append("runtime config missing")
    else:
        for number, line in enumerate(config_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            reason = legacy_reason(line)
            if reason:
                dependency_issues.append(f"line_{number}:{reason}")
    rows.append(_row("legacy_runtime_dependency", not dependency_issues, ";".join(dependency_issues)))

    config_hash_ok = config_path.is_file() and sha256_file(config_path) == manifest.get("config_hash")
    rows.append(_row("runtime_config_hash", config_hash_ok, "exact runtime config SHA256"))

    provenance_issues: list[str] = []
    try:
        input_manifest = _json(paths.provider_root / "CLEAN_INPUT_MANIFEST.json")
        lineage = _json(runtime / "provider_lineage.json")
        commit, dirty = git_code_state(paths.code_root)
        expected_commit = input_manifest.get("generator_code_commit")
        expected_generation_hash = input_manifest.get("generator_config_hash")
        expected_local_hash = sha256_file(paths.config_path)
        checks = {
            "active_commit": manifest.get("code_commit") == commit,
            "active_worktree_clean": dirty is False and manifest.get("code_worktree_dirty_at_run") is False,
            "provider_commit": expected_commit == commit == manifest.get("provider_generator_commit"),
            "provider_clean": input_manifest.get("generator_worktree_dirty") is False
            and lineage.get("generator_worktree_dirty") is False,
            "generation_config_hash": expected_generation_hash
            == manifest.get("provider_generation_config_hash")
            == lineage.get("generator_config_hash"),
            "local_config_hash": input_manifest.get("local_path_config_hash")
            == manifest.get("local_path_config_hash")
            == lineage.get("local_path_config_hash")
            == expected_local_hash,
        }
        provenance_issues.extend(name for name, passed in checks.items() if not passed)
    except Exception as exc:  # noqa: BLE001 - audit records all provenance failures.
        provenance_issues.append(str(exc))
    rows.append(_row("reproducible_code_provider_provenance", not provenance_issues, ";".join(provenance_issues)))

    try:
        metrics = _json(runtime / "eval_metrics.json")
        metrics_ok = (
            metrics.get("metric_namespace") == "clean_smoke_runtime_health_not_paper_performance"
            and metrics.get("paper_performance_claim") is False
            and int(metrics.get("eval_nav_row_count") or 0) > 0
        )
        rows.append(_row("smoke_metrics_namespace", metrics_ok, "runtime health only"))
    except Exception as exc:  # noqa: BLE001
        rows.append(_row("smoke_metrics_namespace", False, str(exc)))

    status_path = runtime / "terminal_status.txt"
    if status_path.is_file():
        status_text = status_path.read_text(encoding="utf-8", errors="replace").strip()
        rows.append(_row("terminal_status", status_text == "PASS", status_text))
    else:
        rows.append(_row("terminal_status", False, "terminal_status.txt missing"))

    if export_root is not None:
        export = guard_path(export_root, role="clean export audit target", allowed_root=paths.clean_root, must_exist=True)
        leaks: list[str] = []
        for relative, text in _iter_export_text(export):
            if LOCAL_POSIX_RE.search(text) or LOCAL_WINDOWS_RE.search(text):
                leaks.append(relative)
        rows.append(_row("export_local_path_leak", not leaks, ",".join(leaks[:50])))
    return rows


def audit_passed(rows: Iterable[dict[str, str]]) -> bool:
    return all(row.get("status") == "PASS" for row in rows)
