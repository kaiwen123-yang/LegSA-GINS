"""Fail-closed cross-stage reuse contract for frozen Canonical-541 providers."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .authorization import STAGE_ID
from .authorization import validate_attempt_root
from .provider_generator import sha256_file


GENERATOR_PATHS = (
    "src/legsa_gins/paper_rebuild/canonical541/matrix_spec.py",
    "src/legsa_gins/paper_rebuild/canonical541/case_manifest.py",
    "src/legsa_gins/paper_rebuild/canonical541/provider_generator.py",
    "src/legsa_gins/paper_rebuild/canonical541/effect_validation.py",
    "src/legsa_gins/paper_rebuild/canonical541/seed_anchor.py",
    "scripts/paper_rebuild/generate_canonical541_providers.py",
)
EXPECTED_CASE_IDS = (
    "C00_clean_normal",
    *(f"D{degradation:02d}_seed_{seed:02d}" for degradation in range(1, 61) for seed in range(9)),
)
EXPECTED_SOURCE_IDS = (
    "gnss_position", "receiver_velocity", "dual_yaw", "combined_gnss",
    "raw_doppler", "go2_rp", "go2_hv", "source_quality_metadata",
)
CONFIG_PATHS = (
    "configs/paper_rebuild/canonical_by2_degradation_541.yaml",
    "configs/paper_rebuild/canonical_by2_effect_validation.yaml",
    "configs/paper_rebuild/canonical_by2_seed_anchor_policy.yaml",
)
READY_FILES = (
    "CANONICAL541_PROVIDER_READY_MANIFEST.csv",
    "CANONICAL541_EFFECT_VALIDATION_RESULTS.csv",
    "EFFECT_VALIDATION_DETAIL_TABLE.csv",
    "EFFECT_VALIDATION_FAILURES.csv",
    "COMPONENT_VALIDATION_TABLE.csv",
    "PROVIDER_SHA256_MANIFEST.csv",
    "PROVIDER_GATE.json",
)


class ProviderReuseError(RuntimeError):
    pass


def tracked_provider_hashes(repo_root: str | Path) -> tuple[dict[str, str], dict[str, str]]:
    repo = Path(repo_root).resolve(strict=True)
    return (
        {path: sha256_file(repo / path) for path in GENERATOR_PATHS},
        {path: sha256_file(repo / path) for path in CONFIG_PATHS},
    )


def git_object_provider_hashes(repo_root: str | Path, commit: str) -> tuple[dict[str, str], dict[str, str]]:
    """Hash provider semantics directly from the old immutable Git object."""

    repo = Path(repo_root).resolve(strict=True)
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ProviderReuseError("origin provider freeze is not a full Git SHA")
    def hashes(paths: tuple[str, ...]) -> dict[str, str]:
        output: dict[str, str] = {}
        for relative in paths:
            completed = subprocess.run(
                ["git", "show", f"{commit}:{relative}"], cwd=repo,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            if completed.returncode != 0:
                raise ProviderReuseError(f"origin Git object lacks provider semantic path: {relative}")
            output[relative] = hashlib.sha256(completed.stdout).hexdigest()
        return output
    return hashes(GENERATOR_PATHS), hashes(CONFIG_PATHS)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _row_hash(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(row), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def decide_provider_reuse(
    *, repo_root: str | Path, origin_stage: str | Path,
    origin_freeze_path: str | Path, new_solver_code_freeze: str,
    provider_root: str | Path,
) -> dict[str, Any]:
    origin = Path(origin_stage).resolve(strict=True)
    freeze_path = Path(origin_freeze_path).resolve(strict=True)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    generator_hashes, config_hashes = tracked_provider_hashes(repo_root)
    origin_commit = str(freeze.get("code_freeze_commit") or freeze.get("provider_code_freeze_commit") or "")
    origin_generator_hashes, origin_config_hashes = git_object_provider_hashes(repo_root, origin_commit)
    ready = origin / "06_PROVIDER_READY"
    gate = json.loads((ready / "PROVIDER_GATE.json").read_text(encoding="utf-8"))
    finalized_provider_root = Path(str(gate.get("finalized_provider_root", ""))).resolve(strict=True)
    expected_finalized_root = (origin / "05_PROVIDER_GENERATION/FINALIZED").resolve(strict=True)
    local_provider_root = Path(provider_root).resolve(strict=True)
    local_finalized_root = (local_provider_root / "FINALIZED").resolve(strict=True)
    provider_root_bound = (
        local_provider_root == (origin / "05_PROVIDER_GENERATION").resolve(strict=True)
        and local_finalized_root == finalized_provider_root == expected_finalized_root
    )
    ready_rows = _rows(ready / "CANONICAL541_PROVIDER_READY_MANIFEST.csv")
    effect_rows = _rows(ready / "CANONICAL541_EFFECT_VALIDATION_RESULTS.csv")
    sha_rows = _rows(ready / "PROVIDER_SHA256_MANIFEST.csv")
    ready_case_ids = tuple(str(row.get("case_id", "")) for row in ready_rows)
    effect_case_ids = tuple(str(row.get("case_id", "")) for row in effect_rows)
    provider_pairs = tuple(
        (str(row.get("case_id", "")), str(row.get("source", ""))) for row in sha_rows
    )
    expected_pairs = {
        (case_id, source) for case_id in EXPECTED_CASE_IDS for source in EXPECTED_SOURCE_IDS
    }
    identity_closure = (
        ready_case_ids == EXPECTED_CASE_IDS
        and effect_case_ids == EXPECTED_CASE_IDS
        and len(provider_pairs) == len(set(provider_pairs)) == 541 * 8
        and set(provider_pairs) == expected_pairs
    )
    provider_bytes_valid = True
    byte_cache: dict[Path, tuple[int, str]] = {}
    for row in sha_rows:
        try:
            payload_path = Path(str(row["resolved_path"])).resolve(strict=True)
            cached = byte_cache.get(payload_path)
            if cached is None:
                cached = (payload_path.stat().st_size, sha256_file(payload_path))
                byte_cache[payload_path] = cached
            provider_bytes_valid = provider_bytes_valid and cached[1] == row.get("sha256")
            provider_bytes_valid = provider_bytes_valid and cached[0] == int(row["size_bytes"])
        except (KeyError, OSError, ValueError):
            provider_bytes_valid = False
            break
    semantics_match = (
        origin_generator_hashes == generator_hashes
        and origin_config_hashes == config_hashes
        and ("provider_generator_hashes" not in freeze
             or freeze.get("provider_generator_hashes") == origin_generator_hashes)
        and ("provider_config_hashes" not in freeze
             or freeze.get("provider_config_hashes") == origin_config_hashes)
    )
    closure = (
        gate.get("passed") is True and gate.get("provider_generation") == 541
        and gate.get("effect_validation") == 541 and gate.get("provider_ready") == 541
        and gate.get("raw_mutation") == 0 and gate.get("trace_open_count") == 0
        and len(ready_rows) == 541 and len(effect_rows) == 541 and len(sha_rows) == 541 * 8
        and provider_root_bound
        and identity_closure
        and provider_bytes_valid
        and all(str(row.get("provider_ready", "")).lower() == "true" for row in ready_rows)
        and all(str(row.get("passed", "")).lower() == "true" for row in effect_rows)
    )
    reuse = semantics_match and closure
    return {
        "schema_version": "paper_rebuild.canonical541_cross_stage_provider_reuse.v1",
        "origin_stage": str(origin),
        "origin_provider_code_freeze": origin_commit,
        "origin_freeze_sha256": sha256_file(freeze_path),
        "provider_generator_hashes": generator_hashes,
        "provider_config_hashes": config_hashes,
        "origin_git_object_provider_generator_hashes": origin_generator_hashes,
        "origin_git_object_provider_config_hashes": origin_config_hashes,
        "origin_finalized_provider_root": str(finalized_provider_root),
        "local_provider_root": str(local_provider_root),
        "local_finalized_provider_root": str(local_finalized_root),
        "provider_root_exact_binding": provider_root_bound,
        "canonical_case_source_identity_closure": identity_closure,
        "canonical_case_count": len(set(ready_case_ids)),
        "canonical_case_source_pair_count": len(set(provider_pairs)),
        "provider_payload_row_hashes": [_row_hash(row) for row in sha_rows],
        "provider_ready_row_hashes": [_row_hash(row) for row in ready_rows],
        "effect_validation_row_hashes": [_row_hash(row) for row in effect_rows],
        "ready_file_hashes": {name: sha256_file(ready / name) for name in READY_FILES},
        "new_stage_id": STAGE_ID,
        "new_solver_code_freeze": new_solver_code_freeze,
        "solver_only_change_proof": semantics_match,
        "provider_generation_semantics_unchanged": semantics_match,
        "provider_bytes_and_effects_valid": closure,
        "reuse_541_providers": reuse,
        "regeneration_required": not reuse,
        "decision": "REUSE" if reuse else "PROVEN_MISMATCH_REGENERATE",
        "trace_online": False,
        "passed": reuse,
    }


def materialize_provider_reuse(
    *, decision: Mapping[str, Any], origin_stage: str | Path, destination_stage: str | Path,
) -> Path:
    if decision.get("reuse_541_providers") is not True or decision.get("regeneration_required") is not False:
        raise ProviderReuseError("provider mismatch proven; regeneration is required")
    origin_ready = Path(origin_stage).resolve(strict=True) / "06_PROVIDER_READY"
    destination = validate_attempt_root(destination_stage) / "06_PROVIDER_READY"
    destination.mkdir(parents=True, exist_ok=True)
    for name in READY_FILES:
        source = origin_ready / name
        target = destination / name
        raw = source.read_bytes()
        if target.exists():
            if target.read_bytes() != raw:
                raise ProviderReuseError(f"existing reused provider registry drift: {name}")
            continue
        temporary = target.with_name(f".{name}.tmp_{os.getpid()}")
        with temporary.open("xb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target)
    manifest = destination / "CROSS_STAGE_PROVIDER_REUSE_MANIFEST.json"
    raw = json.dumps(dict(decision), indent=2, sort_keys=True) + "\n"
    if manifest.exists():
        if manifest.read_text(encoding="utf-8") != raw:
            raise ProviderReuseError("cross-stage provider reuse manifest drift")
    else:
        temporary = manifest.with_name(f".{manifest.name}.tmp_{os.getpid()}")
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, manifest)
    return manifest


def persist_provider_reuse_decision(*, decision: Mapping[str, Any], destination_stage: str | Path) -> Path:
    """Persist REUSE or a proven mismatch before any later pipeline action."""

    attempt = validate_attempt_root(destination_stage)
    destination = attempt / "06_PROVIDER_READY"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "CROSS_STAGE_PROVIDER_REUSE_DECISION.json"
    payload = {**dict(decision), "destination_attempt_root": str(attempt)}
    raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != raw:
            raise ProviderReuseError("stage-owned provider reuse decision drift")
        return path
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    return path
