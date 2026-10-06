"""Authoritatively derive the compact repaired readiness gate."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

from .authorization import RUNTIME_ROLE, STAGE_ID, validate_attempt_root
from .provider_generator import sha256_file
from .runner import FEATURE_FIELDS, module_counters, validate_method_counters
from .full_method_registry import MethodProfile


class ReadinessError(RuntimeError):
    pass


CLEAN18_PROFILES = (
    "single_antenna_EKF", "basic_dual_yaw_EKF",
    *(f"AB{value:04b}" for value in range(16)),
)


def _json(path: str | Path) -> tuple[Path, dict[str, Any]]:
    resolved = Path(path).resolve(strict=True)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadinessError(f"readiness artifact is not an object: {resolved.name}")
    return resolved, payload


def _require_binding(payload: Mapping[str, Any], *, code_freeze: str,
                     executable_sha256: str) -> None:
    if (payload.get("stage_id") != STAGE_ID
            or payload.get("code_freeze_commit") != code_freeze
            or payload.get("executable_sha256") != executable_sha256):
        raise ReadinessError("readiness evidence stage/freeze/executable binding drift")


def _numeric_values(path: Path) -> tuple[float, ...]:
    values: list[float] = []
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "%")):
            continue
        try:
            row = tuple(float(value) for value in stripped.replace(",", " ").split())
        except ValueError as exc:
            raise ReadinessError(f"non-numeric readiness output: {path.name}") from exc
        if not row or not all(math.isfinite(value) for value in row):
            raise ReadinessError(f"empty/non-finite readiness output row: {path.name}")
        values.extend(row)
    if not values:
        raise ReadinessError(f"empty readiness output: {path.name}")
    return tuple(values)


def _expected_flags(profile: str) -> dict[str, bool]:
    if profile == "single_antenna_EKF":
        return {field: field in {"position_update", "receiver_velocity"} for field in FEATURE_FIELDS}
    if profile == "basic_dual_yaw_EKF":
        return {field: field in {"position_update", "dual_yaw"} for field in FEATURE_FIELDS}
    if not (len(profile) == 6 and profile.startswith("AB")
            and set(profile[2:]) <= {"0", "1"}):
        raise ReadinessError(f"unknown clean-18 profile: {profile}")
    rd, sa, rp, hv = (bit == "1" for bit in profile[2:])
    return {
        "position_update": True, "dual_yaw": True, "scheme_c": True,
        "receiver_velocity": True, "raw_doppler": rd,
        "source_aware": sa, "go2_rp": rp, "go2_hv": hv,
    }


def _validate_proof_file_bindings(*, proof: Mapping[str, Any], directory: Path,
                                  counters: Mapping[str, int]) -> None:
    manifest_path = directory / "RUN_MANIFEST.json"
    if proof.get("solver_manifest_sha256") != sha256_file(manifest_path):
        raise ReadinessError("execution proof solver-manifest hash drift")
    if proof.get("module_counters") != dict(counters):
        raise ReadinessError("execution proof counters differ from recomputed manifest counters")
    output_hashes = proof.get("output_hashes_before_proof")
    if not isinstance(output_hashes, Mapping):
        raise ReadinessError("execution proof output hashes are missing")
    for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
        if output_hashes.get(name) != sha256_file(directory / name):
            raise ReadinessError(f"execution proof output hash drift: {name}")


def _validate_clean18(*, output_root: Path, seal_root: Path, code_freeze: str,
                      executable_sha256: str) -> list[dict[str, Any]]:
    runs = output_root.resolve(strict=True)
    seal = seal_root.resolve(strict=True)
    expected_dirs = {f"{index:02d}_{profile}" for index, profile in enumerate(CLEAN18_PROFILES, 1)}
    actual_dirs = {path.name for path in runs.iterdir() if path.is_dir() and not path.name.startswith(".")}
    if actual_dirs != expected_dirs:
        raise ReadinessError("clean-18 output root does not contain the exact 18 identities")
    journal_path = seal / "OUTPUT_SEAL_JOURNAL.json"
    manifest_path = seal / "OUTPUT_HASH_MANIFEST.csv"
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    _require_binding(journal, code_freeze=code_freeze, executable_sha256=executable_sha256)
    if (journal.get("passed") is not True
            or journal.get("unique_formal_runs") != 18
            or journal.get("method_ids") != list(CLEAN18_PROFILES)
            or journal.get("trace_open_count_before_seal") != 0
            or journal.get("all_outputs_sealed_before_trace") is not True
            or journal.get("output_hash_manifest_sha256") != sha256_file(manifest_path)):
        raise ReadinessError("clean-18 output seal contract failed")
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        seal_rows = list(csv.DictReader(handle))
    sealed = {(row.get("algorithm_id"), row.get("relative_path")): row for row in seal_rows}
    if len(sealed) != len(seal_rows) or not seal_rows:
        raise ReadinessError("clean-18 seal is empty or contains duplicates")
    rows: list[dict[str, Any]] = []
    for index, profile_id in enumerate(CLEAN18_PROFILES, 1):
        directory = runs / f"{index:02d}_{profile_id}"
        proof = json.loads((directory / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
        manifest = json.loads((directory / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        _require_binding(proof, code_freeze=code_freeze, executable_sha256=executable_sha256)
        flags = _expected_flags(profile_id)
        expected_algorithm = ({"AB0000": "strong_dual_yaw_EKF", "AB1111": "LegSA_Paper_V1"}
                              .get(profile_id, profile_id))
        if (proof.get("terminal_status") != "COMPLETED_EVALUABLE"
                or proof.get("effective_profile") != profile_id
                or proof.get("effective_flags") != flags
                or proof.get("case_id") != "C00_clean_normal"
                or manifest.get("stage_id") != STAGE_ID
                or manifest.get("port_role") != RUNTIME_ROLE
                or manifest.get("case_id") != "C00_clean_normal"
                or manifest.get("algorithm_id") != expected_algorithm
                or manifest.get("trace_used_online") is not False):
            raise ReadinessError(f"clean-18 identity/terminal drift: {profile_id}")
        profile = MethodProfile(profile_id, profile_id, profile_id, flags)
        try:
            counters = validate_method_counters(profile, manifest)
        except Exception as exc:
            raise ReadinessError(f"clean-18 counter contract failed: {profile_id}") from exc
        _validate_proof_file_bindings(proof=proof, directory=directory, counters=counters)
        for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
            path = directory / name
            _numeric_values(path)
            relative = path.relative_to(runs).as_posix()
            seal_row = sealed.get((profile_id, relative))
            if (seal_row is None or str(seal_row.get("sealed_before_trace", "")).lower() != "true"
                    or seal_row.get("sha256") != sha256_file(path)
                    or int(seal_row.get("size_bytes", -1)) != path.stat().st_size):
                raise ReadinessError(f"clean-18 authoritative seal mismatch: {relative}")
        rows.append({"effective_profile": profile_id, "module_counters": counters,
                     "run_root_sha256s": {
                         name: sha256_file(directory / name)
                         for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "RUN_MANIFEST.json",
                                      "CANONICAL541_EXECUTION_PROOF.json")
                     }})
    return rows


def derive_compact_readiness_gate(
    *, build_artifact: str | Path, test_artifact: str | Path,
    preflight_artifact: str | Path, ab0000_output_root: str | Path,
    ab0000_anchor_root: str | Path, clean18_output_root: str | Path,
    clean18_seal_root: str | Path, attempt_root: str | Path,
    code_freeze_commit: str, executable_sha256: str,
) -> dict[str, Any]:
    attempt = validate_attempt_root(attempt_root)
    artifacts = {name: _json(path) for name, path in {
        "build": build_artifact, "tests": test_artifact, "preflight": preflight_artifact,
    }.items()}
    for _, payload in artifacts.values():
        _require_binding(payload, code_freeze=code_freeze_commit,
                         executable_sha256=executable_sha256)
    build, tests, preflight = (artifacts[name][1] for name in ("build", "tests", "preflight"))
    if not (build.get("passed") is True and build.get("build_type") == "Release"
            and tests.get("passed") is True and int(tests.get("failed", -1)) == 0
            and int(tests.get("paper_rebuild_passed", 0)) > 0
            and preflight.get("passed") is True
            and preflight.get("expected_identity_count") == 5951
            and preflight.get("duplicate_identity_count") == 0
            and preflight.get("missing_identity_count") == 0
            and preflight.get("invalid_algorithm_role_route_count") == 0):
        raise ReadinessError("build/test/preflight authoritative evidence failed")
    current_ab = Path(ab0000_output_root).resolve(strict=True)
    anchor_ab = Path(ab0000_anchor_root).resolve(strict=True)
    ab_proof = json.loads((current_ab / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
    ab_manifest = json.loads((current_ab / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    _require_binding(ab_proof, code_freeze=code_freeze_commit, executable_sha256=executable_sha256)
    if (ab_proof.get("terminal_status") != "COMPLETED_EVALUABLE"
            or ab_proof.get("effective_profile") != "AB0000"
            or ab_proof.get("case_id") != "C00_clean_normal"
            or ab_manifest.get("stage_id") != STAGE_ID or ab_manifest.get("port_role") != RUNTIME_ROLE
            or ab_manifest.get("algorithm_id") != "strong_dual_yaw_EKF"):
        raise ReadinessError("AB0000 authoritative identity/terminal contract failed")
    try:
        ab_counters = validate_method_counters(
            MethodProfile("F03", "strong", "AB0000", _expected_flags("AB0000")), ab_manifest,
        )
    except Exception as exc:
        raise ReadinessError("AB0000 counter contract failed") from exc
    _validate_proof_file_bindings(proof=ab_proof, directory=current_ab, counters=ab_counters)
    parity_hashes: dict[str, dict[str, str]] = {}
    for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
        current, anchor = current_ab / name, anchor_ab / name
        if _numeric_values(current) != _numeric_values(anchor):
            raise ReadinessError(f"AB0000 numerical parity failed: {name}")
        parity_hashes[name] = {"current": sha256_file(current), "anchor": sha256_file(anchor)}
    clean_rows = _validate_clean18(
        output_root=Path(clean18_output_root), seal_root=Path(clean18_seal_root),
        code_freeze=code_freeze_commit, executable_sha256=executable_sha256,
    )
    expected_clean_ab = Path(clean18_output_root).resolve(strict=True) / "03_AB0000"
    if current_ab != expected_clean_ab:
        raise ReadinessError("AB0000 parity output is not the exact clean-18 AB0000 identity")
    roots = {
        "attempt": attempt, "ab0000_output": current_ab, "ab0000_anchor": anchor_ab,
        "clean18_output": Path(clean18_output_root).resolve(strict=True),
        "clean18_seal": Path(clean18_seal_root).resolve(strict=True),
    }
    return {
        "schema_version": "paper_rebuild.canonical541_compact_readiness_gate.v2_authoritative",
        "stage_id": STAGE_ID, "attempt_root": str(attempt),
        "code_freeze_commit": code_freeze_commit, "executable_sha256": executable_sha256,
        "artifact_paths": {name: str(item[0]) for name, item in artifacts.items()},
        "artifact_hashes": {name: sha256_file(item[0]) for name, item in artifacts.items()},
        "authoritative_roots": {name: str(path) for name, path in roots.items()},
        "ab0000_numerical_parity": parity_hashes, "ab0000_parity_passed": True,
        "clean18_profiles": list(CLEAN18_PROFILES), "clean18_rows": clean_rows,
        "clean18_seal_hashes": {
            name: sha256_file(roots["clean18_seal"] / name)
            for name in ("OUTPUT_HASH_MANIFEST.csv", "OUTPUT_SEAL_JOURNAL.json")
        },
        "clean_18_terminal": 18, "trace_reads_before_seal": 0,
        "registry_preflight_unique_identities": 5951, "passed": True,
    }


def write_compact_readiness_gate(output_path: str | Path, payload: Mapping[str, Any]) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ReadinessError("compact readiness gate already exists")
    temporary = output.with_name(f".{output.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, output)
    return output
