"""One-shot CLEAN3R4 clean-18 runtime gate without evaluator access."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from .authorization import (
    PROTOCOL_ID, RUNTIME_ROLE, STAGE_ID, load_execution_authorization,
    validate_attempt_root,
)
from .execution_plan import validate_code_freeze_gate
from .full_method_registry import FEATURE_FIELDS, FULL_METHODS, MethodProfile
from .provider_generator import ProviderBundle, sha256_file
from .readiness import CLEAN18_PROFILES, _validate_clean18
from .runner import (
    actual_rendered_runtime_config_sha256, build_runtime_config,
    materialize_method_bound_inputs, run_unique_execution,
    scientific_runtime_config_hash,
)
from ..manifest import git_code_state


CASE_ID = "C00_clean_normal"
READINESS_DIRECTORY = "01_COMPACT_READINESS_RUN"
CLEAN18_OUTPUT_DIRECTORY = "CLEAN18_OUTPUTS"
CLEAN18_SEAL_DIRECTORY = "CLEAN18_SEAL"
STRONG_ANCHOR_RELATIVE = (
    "stages/CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME/"
    "06_FORMAL_RUNS/03_AB0000"
)
THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
}


class CompactReadinessRunError(RuntimeError):
    pass


def clean18_profiles() -> tuple[MethodProfile, ...]:
    """Return the exact two baselines plus all sixteen RD/SA/RP/HV profiles."""

    profiles: list[MethodProfile] = [FULL_METHODS[0], FULL_METHODS[1]]
    for value in range(16):
        effective = f"AB{value:04b}"
        bits = effective[2:]
        flags = {
            "position_update": True, "dual_yaw": True, "scheme_c": True,
            "receiver_velocity": True, "raw_doppler": bits[0] == "1",
            "source_aware": bits[1] == "1", "go2_rp": bits[2] == "1",
            "go2_hv": bits[3] == "1",
        }
        method_id, name = {
            "AB0000": ("F03", "strong_dual_yaw_EKF"),
            "AB1111": ("F04", "LegSA_Paper_V1"),
        }.get(effective, (f"CLEAN18_{effective}", effective))
        profiles.append(MethodProfile(method_id, name, effective, flags))
    if tuple(profile.effective_profile for profile in profiles) != CLEAN18_PROFILES:
        raise AssertionError("internal clean-18 profile order drift")
    if len({profile.signature for profile in profiles}) != 18:
        raise AssertionError("clean-18 effective flags are not unique")
    return tuple(profiles)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    return path


def _acquire_lock(attempt: Path, code_freeze: str, executable_sha256: str) -> Path:
    lock = attempt / "compact_readiness_runner.lock"
    payload = {
        "pid": os.getpid(), "stage_id": STAGE_ID, "attempt_root": str(attempt),
        "code_freeze_commit": code_freeze, "executable_sha256": executable_sha256,
    }
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise CompactReadinessRunError("compact readiness runner lock already exists") from exc
    try:
        os.write(descriptor, (json.dumps(payload, sort_keys=True) + "\n").encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return lock


def _release_lock(lock: Path) -> None:
    if not lock.is_file():
        return
    payload = json.loads(lock.read_text(encoding="utf-8"))
    if payload.get("pid") == os.getpid():
        lock.unlink()


def _rewrite_method_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def _numeric_bytes_equal(left: Path, right: Path) -> bool:
    # The frozen contract requires exact output bytes; parsing is left to the
    # authoritative readiness validator, which additionally rejects non-finite data.
    return left.read_bytes() == right.read_bytes()


def _seal_clean18(*, output_root: Path, seal_root: Path, code_freeze: str,
                  executable_sha256: str, local_config_sha256: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, profile in enumerate(clean18_profiles(), 1):
        directory = output_root / f"{index:02d}_{profile.effective_profile}"
        for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "RUN_MANIFEST.json",
                     "CANONICAL541_EXECUTION_PROOF.json"):
            path = (directory / name).resolve(strict=True)
            rows.append({
                "algorithm_id": profile.effective_profile,
                "relative_path": path.relative_to(output_root).as_posix(),
                "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                "sealed_before_trace": True,
            })
    seal_root.mkdir(parents=True, exist_ok=False)
    manifest = seal_root / "OUTPUT_HASH_MANIFEST.csv"
    with manifest.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
        handle.flush(); os.fsync(handle.fileno())
    journal = {
        "schema_version": "paper_rebuild.canonical541_clean18_output_seal.v1",
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": CASE_ID,
        "runtime_role": RUNTIME_ROLE, "code_freeze_commit": code_freeze,
        "executable_sha256": executable_sha256,
        "local_config_sha256": local_config_sha256,
        "unique_formal_runs": 18, "method_ids": list(CLEAN18_PROFILES),
        "sealed_file_count": len(rows), "trace_open_count_before_seal": 0,
        "all_outputs_sealed_before_trace": True,
        "output_hash_manifest_sha256": sha256_file(manifest), "passed": True,
    }
    _atomic_json(seal_root / "OUTPUT_SEAL_JOURNAL.json", journal)
    return journal


def validate_compact_readiness_seal(
    *, output_root: str | Path, seal_root: str | Path, code_freeze: str,
    executable_sha256: str, local_config_sha256: str,
) -> dict[str, Any]:
    """Recompute the exact 72-file adapter seal without trusting its journal."""

    output = Path(output_root).resolve(strict=True)
    seal = Path(seal_root).resolve(strict=True)
    manifest_path = (seal / "OUTPUT_HASH_MANIFEST.csv").resolve(strict=True)
    journal_path = (seal / "OUTPUT_SEAL_JOURNAL.json").resolve(strict=True)
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    expected = {
        (profile, f"{index:02d}_{profile}/{name}")
        for index, profile in enumerate(CLEAN18_PROFILES, 1)
        for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "RUN_MANIFEST.json",
                     "CANONICAL541_EXECUTION_PROOF.json")
    }
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle); rows = list(reader)
    required_fields = {"algorithm_id", "relative_path", "size_bytes", "sha256", "sealed_before_trace"}
    pairs = [(str(row.get("algorithm_id", "")), str(row.get("relative_path", ""))) for row in rows]
    if (set(reader.fieldnames or ()) != required_fields or len(rows) != 72
            or len(set(pairs)) != 72 or set(pairs) != expected):
        raise CompactReadinessRunError("compact readiness seal path set is not exact 72-file closure")
    for row in rows:
        try:
            path = (output / str(row["relative_path"])).resolve(strict=True)
        except FileNotFoundError as exc:
            raise CompactReadinessRunError(
                f"compact readiness sealed file missing: {row['relative_path']}"
            ) from exc
        try:
            path.relative_to(output)
        except ValueError as exc:
            raise CompactReadinessRunError("sealed path escapes clean-18 output root") from exc
        if (str(row.get("sealed_before_trace", "")).lower() != "true"
                or int(row.get("size_bytes", -1)) != path.stat().st_size
                or row.get("sha256") != sha256_file(path)):
            raise CompactReadinessRunError(f"compact readiness sealed file drift: {row['relative_path']}")
    required_journal = {
        "schema_version": "paper_rebuild.canonical541_clean18_output_seal.v1",
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": CASE_ID,
        "runtime_role": RUNTIME_ROLE, "code_freeze_commit": code_freeze,
        "executable_sha256": executable_sha256,
        "local_config_sha256": local_config_sha256,
        "unique_formal_runs": 18, "method_ids": list(CLEAN18_PROFILES),
        "sealed_file_count": 72, "trace_open_count_before_seal": 0,
        "all_outputs_sealed_before_trace": True,
        "output_hash_manifest_sha256": sha256_file(manifest_path), "passed": True,
    }
    if any(journal.get(key) != value for key, value in required_journal.items()):
        raise CompactReadinessRunError("compact readiness seal journal binding drift")
    return {
        **journal, "output_hash_manifest_path": str(manifest_path),
        "output_seal_journal_path": str(journal_path),
        "output_seal_journal_sha256": sha256_file(journal_path),
    }


def _validate_resume(*, readiness_root: Path, attempt: Path, code_freeze: str,
                     executable_sha256: str, local_config_sha256: str,
                     anchor: Path) -> dict[str, Any]:
    output = readiness_root / CLEAN18_OUTPUT_DIRECTORY
    seal = readiness_root / CLEAN18_SEAL_DIRECTORY
    journal = validate_compact_readiness_seal(
        output_root=output, seal_root=seal, code_freeze=code_freeze,
        executable_sha256=executable_sha256, local_config_sha256=local_config_sha256,
    )
    rows = _validate_clean18(output_root=output, seal_root=seal, code_freeze=code_freeze,
                             executable_sha256=executable_sha256)
    ab = output / "03_AB0000"
    for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
        if not _numeric_bytes_equal(ab / name, anchor / name):
            raise CompactReadinessRunError(f"sealed AB0000 parity drift: {name}")
    report = json.loads((readiness_root / "COMPACT_READINESS_RUN_REPORT.json").read_text(encoding="utf-8"))
    journal_payload = json.loads(
        Path(journal["output_seal_journal_path"]).read_text(encoding="utf-8")
    )
    required_report = {
        "schema_version": "paper_rebuild.canonical541_compact_readiness_run.v1",
        "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": CASE_ID,
        "runtime_role": RUNTIME_ROLE, "attempt_root": str(attempt),
        "code_freeze_commit": code_freeze, "executable_sha256": executable_sha256,
        "local_config_sha256": local_config_sha256,
        "clean18_terminal": 18, "clean18_profiles": list(CLEAN18_PROFILES),
        "clean18_flags": {
            profile.effective_profile: dict(profile.flags)
            for profile in clean18_profiles()
        },
        "logical_aliases": {"AB1111": ["F04", "A01"], "AB0000": ["F03", "A02"]},
        "trace_reads_before_seal": 0, "technical_retries": 0,
        "metric_driven_rerun": False, "per_case_tuning": False,
        "output_root": str(output), "seal_root": str(seal),
        "seal": journal_payload,
        "seal_manifest_sha256": journal["output_hash_manifest_sha256"],
        "seal_journal_sha256": journal["output_seal_journal_sha256"], "passed": True,
    }
    if any(report.get(key) != value for key, value in required_report.items()):
        raise CompactReadinessRunError("sealed compact readiness report binding drift")
    if (report.get("stage_id") != STAGE_ID or report.get("attempt_root") != str(attempt)
            or report.get("code_freeze_commit") != code_freeze
            or report.get("executable_sha256") != executable_sha256
            or report.get("passed") is not True or len(rows) != 18):
        raise CompactReadinessRunError("sealed compact readiness report binding drift")
    return report


def execute_compact_readiness(
    *, repo_root: str | Path, local_config: str | Path, paths: Mapping[str, Path],
    attempt_root: str | Path, executable: str | Path, code_freeze_commit: str,
    base: ProviderBundle, timeout_seconds: int = 1800, resume: bool = False,
    executor: Callable[..., Mapping[str, Any]] = run_unique_execution,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve(strict=True)
    local = Path(local_config).resolve(strict=True)
    authorization = load_execution_authorization(repo)
    if (authorization.get("stage_id") != STAGE_ID
            or authorization.get("protocol_id") != PROTOCOL_ID
            or authorization.get("runtime_role") != RUNTIME_ROLE):
        raise CompactReadinessRunError("tracked compact readiness authorization identity drift")
    attempt = validate_attempt_root(attempt_root)
    configured_attempt = validate_attempt_root(paths["runtime_root"])
    binary = Path(executable).resolve(strict=True)
    commit, dirty = git_code_state(repo)
    executable_hash = sha256_file(binary); local_hash = sha256_file(local)
    if dirty or commit != code_freeze_commit:
        raise CompactReadinessRunError("compact readiness requires exact clean code freeze")
    if attempt != configured_attempt:
        raise CompactReadinessRunError("attempt root differs from ignored local config")
    if repo != Path(paths["code_root"]).resolve(strict=True):
        raise CompactReadinessRunError("local config code_root differs from active repository")
    freeze_gate = validate_code_freeze_gate(
        stage_root=attempt, executable=binary, code_freeze_commit=code_freeze_commit,
    )
    try:
        frozen_executable_value = Path(str(freeze_gate["executable_path"]))
        if not frozen_executable_value.is_absolute():
            raise CompactReadinessRunError(
                "code-freeze gate executable path is not absolute"
            )
        frozen_executable = frozen_executable_value.resolve(strict=True)
    except (KeyError, FileNotFoundError) as exc:
        raise CompactReadinessRunError(
            "code-freeze gate lacks the exact executable path binding"
        ) from exc
    if frozen_executable != binary:
        raise CompactReadinessRunError("code-freeze executable path binding drift")
    anchor = (Path(paths["clean_root"]).resolve(strict=True) / STRONG_ANCHOR_RELATIVE).resolve(strict=True)
    readiness_root = attempt / READINESS_DIRECTORY
    if readiness_root.exists():
        if resume:
            return _validate_resume(readiness_root=readiness_root, attempt=attempt,
                                    code_freeze=code_freeze_commit,
                                    executable_sha256=executable_hash,
                                    local_config_sha256=local_hash, anchor=anchor)
        raise CompactReadinessRunError("compact readiness output already exists; explicit valid --resume required")
    lock = _acquire_lock(attempt, code_freeze_commit, executable_hash)
    for name, value in THREAD_ENVIRONMENT.items():
        os.environ[name] = value
    try:
        readiness_root.mkdir(parents=False, exist_ok=False)
        output_root = readiness_root / CLEAN18_OUTPUT_DIRECTORY
        output_root.mkdir()
        method_root = readiness_root / "METHOD_BOUND"
        shared_gnss = readiness_root / "SHARED_GNSS_BY_HASH"
        clean_manifest = (Path(paths["base_provider_root"]) /
                          "FINAL_V23_CLEAN_CLEAN2R2A/FINAL_V23_CLEAN_INPUT_MANIFEST.json").resolve(strict=True)
        auxiliary_manifest = (Path(paths["base_provider_root"]) /
                              "FRESH_AUXILIARIES_CLEAN2R2A/CLEAN1R2R1_AUXILIARY_MANIFEST.json").resolve(strict=True)
        provider_protocol = (repo / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml").resolve(strict=True)
        profiles = clean18_profiles()
        by_effective = {profile.effective_profile: profile for profile in profiles}
        execution_order = ("AB0000", *(name for name in CLEAN18_PROFILES if name != "AB0000"))
        proofs: dict[str, Mapping[str, Any]] = {}
        for effective in execution_order:
            profile = by_effective[effective]
            index = CLEAN18_PROFILES.index(effective) + 1
            method_directory = method_root / effective
            manifest_payload = materialize_method_bound_inputs(
                base=base, case_bundle=base, profile=profile,
                output_root=method_directory,
                case_provider_paths={
                    source: Path(base.original_provider_paths[source])
                    for source in ("raw_doppler", "go2_rp", "go2_hv")
                },
                shared_gnss_root=shared_gnss,
            )
            run_root = output_root / f"{index:02d}_{effective}"
            run_root.mkdir()
            run_id = f"CLEAN3R4_READINESS_{index:02d}_{effective}"
            config_text = build_runtime_config(
                profile=profile, clean_input_manifest=clean_manifest,
                auxiliary_manifest=auxiliary_manifest, provider_protocol=provider_protocol,
                method_bound_manifest=manifest_payload, output_dir=run_root,
                case_id=CASE_ID, run_id=run_id,
            )
            rendered_hash = actual_rendered_runtime_config_sha256(config_text)
            manifest_payload.update({
                "stage_id": STAGE_ID, "attempt_root": str(attempt),
                "solver_code_freeze_commit": code_freeze_commit,
                "executable_sha256": executable_hash,
                "local_path_config_sha256": local_hash,
                "actual_rendered_runtime_config_sha256": rendered_hash,
            })
            method_manifest = method_directory / "METHOD_BOUND_INPUT_MANIFEST.json"
            _rewrite_method_manifest(method_manifest, manifest_payload)
            config = run_root / "CANONICAL541_RUNTIME_CONFIG.yaml"
            config.write_text(config_text, encoding="utf-8")
            proof = dict(executor(
                executable=binary, runtime_config=config, method_bound_manifest=method_manifest,
                output_root=run_root, profile=profile, case_id=CASE_ID, run_id=run_id,
                raw_root=paths["raw_root"], clean_root=paths["clean_root"], repo_root=repo,
                expected_executable_hash=executable_hash,
                expected_runtime_config_hash=sha256_file(config),
                expected_scientific_config_hash=scientific_runtime_config_hash(config_text),
                expected_method_bound_manifest_hash=sha256_file(method_manifest),
                timeout_seconds=timeout_seconds,
            ))
            if proof.get("terminal_status") != "COMPLETED_EVALUABLE":
                raise CompactReadinessRunError(f"clean readiness profile is not evaluable: {effective}")
            ledger = proof.get("solver_read_ledger")
            if not isinstance(ledger, Mapping) or ledger.get("trace_open_count") != 0:
                raise CompactReadinessRunError(f"reference trace opened before seal: {effective}")
            proof.update({
                "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": CASE_ID,
                "runtime_role": RUNTIME_ROLE, "code_freeze_commit": code_freeze_commit,
                "executable_sha256": executable_hash, "local_config_sha256": local_hash,
                "metric_driven_rerun": False, "per_case_tuning": False,
            })
            proof_bytes = (json.dumps(proof, indent=2, sort_keys=True) + "\n").encode()
            (run_root / "CANONICAL541_EXECUTION_PROOF.json").write_bytes(proof_bytes)
            (run_root / "CANONICAL541_FORMAL_RUN_MANIFEST.json").write_bytes(proof_bytes)
            proofs[effective] = proof
            if effective == "AB0000":
                for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt"):
                    if not _numeric_bytes_equal(run_root / name, anchor / name):
                        raise CompactReadinessRunError(f"AB0000 strong-anchor parity failed: {name}")
        _seal_clean18(
            output_root=output_root, seal_root=readiness_root / CLEAN18_SEAL_DIRECTORY,
            code_freeze=code_freeze_commit, executable_sha256=executable_hash,
            local_config_sha256=local_hash,
        )
        seal = validate_compact_readiness_seal(
            output_root=output_root, seal_root=readiness_root / CLEAN18_SEAL_DIRECTORY,
            code_freeze=code_freeze_commit, executable_sha256=executable_hash,
            local_config_sha256=local_hash,
        )
        rows = _validate_clean18(
            output_root=output_root, seal_root=readiness_root / CLEAN18_SEAL_DIRECTORY,
            code_freeze=code_freeze_commit, executable_sha256=executable_hash,
        )
        ab_root = output_root / "03_AB0000"
        seal_journal = json.loads(
            Path(seal["output_seal_journal_path"]).read_text(encoding="utf-8")
        )
        sa_counters = [proof.get("module_counters", {}) for effective, proof in proofs.items()
                       if by_effective[effective].flags["source_aware"]]
        sa_evaluations = sum(int(row.get("source_aware_evaluation_count", 0)) for row in sa_counters)
        sa_changes = sum(int(row.get("source_aware_weight_changed_count", 0)) for row in sa_counters)
        report = {
            "schema_version": "paper_rebuild.canonical541_compact_readiness_run.v1",
            "stage_id": STAGE_ID, "protocol_id": PROTOCOL_ID, "case_id": CASE_ID,
            "runtime_role": RUNTIME_ROLE, "attempt_root": str(attempt),
            "code_freeze_commit": code_freeze_commit, "executable_sha256": executable_hash,
            "local_config_sha256": local_hash, "clean18_terminal": len(rows),
            "clean18_profiles": list(CLEAN18_PROFILES),
            "clean18_flags": {
                profile.effective_profile: dict(profile.flags) for profile in profiles
            },
            "logical_aliases": {"AB1111": ["F04", "A01"], "AB0000": ["F03", "A02"]},
            "ab0000_parity": {
                name: {"current": sha256_file(ab_root / name), "anchor": sha256_file(anchor / name),
                       "byte_identical": True}
                for name in ("KF_GINS_Navresult.nav", "KF_GINS_STD.txt")
            },
            "trace_reads_before_seal": 0, "technical_retries": 0,
            "metric_driven_rerun": False, "per_case_tuning": False,
            "report_only_metrics": {
                "source_aware_evaluation_count": sa_evaluations,
                "source_aware_weight_changed_count": sa_changes,
                "source_aware_change_rate": (sa_changes / sa_evaluations if sa_evaluations else 0.0),
                "full_minus_strong": "NOT_EVALUATED_WITHOUT_OFFLINE_REFERENCE",
                "factorial_effects": "NOT_EVALUATED_WITHOUT_OFFLINE_REFERENCE",
            },
            "output_root": str(output_root), "seal_root": str(readiness_root / CLEAN18_SEAL_DIRECTORY),
            "seal": seal_journal,
            "seal_manifest_sha256": seal["output_hash_manifest_sha256"],
            "seal_journal_sha256": seal["output_seal_journal_sha256"], "passed": True,
        }
        _atomic_json(readiness_root / "COMPACT_READINESS_RUN_REPORT.json", report)
        return report
    finally:
        _release_lock(lock)
