"""Phase-1R validity audit and deterministic validated EXT01/C00 runner.

The native search path consumes only hash-locked RXM-RAWX observations and
source-backed broadcast states.  NAV-HPPOSECEF, RTKLIB relative positioning,
and Fixposition trace are diagnostic-only; trace cannot be opened until the
native output hash freeze exists and has been revalidated.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import shutil
import subprocess
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from legsa_gins.paper_rebuild.manifest import (
    read_hash_lock,
    sha256_file,
    verify_raw_sources,
    write_json_atomic,
)

from .ext01_clambda import (
    body_yaw_from_ned_baseline,
    evaluate_production_objective,
    joint_gls,
    solve_clambda,
    wrap_safe_residual_degrees,
)
from .phase1_runner import (
    RTKLIB_COMMIT,
    RTKLIB_LICENSE_SHA256,
    RTKLIB_REMOTE,
    Phase1Paths,
    Phase1RunnerError,
    _ecef_vector_to_ned,
    _raw_relatives,
    _run_convbin,
    load_paths,
)
from .shared_raw_backend import (
    HALF_CYCLE_CONTRACT,
    DoubleDifferenceStageError,
    RawBackendError,
    RtklibBroadcastProvider,
    SignalIdentity,
    TrackingContinuity,
    build_gps_l1_double_difference_model,
    dd_matrix_condition_diagnostics,
    gps_l1_code_spp,
    gps_l1_epoch_accounting,
    identity_text,
    pair_epochs,
    reconstruct_ubx_stream,
    wavelength_m,
)


PASS_REPAIRED = "PASS_PHASE1R_EXT01_REPAIRED_C00_READY_FOR_NATIVE_COMPARISON"
PASS_VALIDATED = "PASS_PHASE1R_EXT01_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT"
UNSUPPORTED = "UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION"
PHASE1R_CONTRACT = "PHASE1R_VALIDATION_CONTRACT_V1.yaml"
EXPECTED_PAIR_COUNT = 1509
DEFAULT_WORKERS = 16
MAX_WORKERS = 20
LENGTH_M = 0.350
LAMBDA_SEEDS = 8
STRICT_NODE_LIMIT = 1_000_000
# Scientific termination is controlled by the deterministic node bound.  The
# effectively-disabled wall budget cannot make worker scheduling change rows.
STRICT_WALL_BUDGET_SECONDS = 1.0e9
THREAD_ENVIRONMENT = (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"
)

VALIDATED_FILENAMES = {
    "native": "EXT01_C00_VALIDATED_NATIVE_HEADING_RESULTS.csv",
    "failures": "EXT01_C00_VALIDATED_FAILURE_LEDGER.csv",
    "runtime": "EXT01_C00_VALIDATED_RUNTIME.csv",
    "dd": "EXT01_C00_VALIDATED_DD_DIAGNOSTICS.csv",
    "tracking": "EXT01_C00_VALIDATED_TRACKING_DIAGNOSTICS.csv",
    "half_cycle": "EXT01_C00_VALIDATED_HALF_CYCLE_DIAGNOSTICS.csv",
    "search": "EXT01_C00_VALIDATED_SEARCH_CERTIFICATES.csv",
    "proxy": "EXT01_C00_VALIDATED_PROXY_DIAGNOSTICS.csv",
    "summary": "EXT01_C00_VALIDATED_SUMMARY.json",
}

NATIVE_FREEZE_NAMES = ("native", "failures", "runtime", "dd", "tracking", "search")


class Phase1RRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Phase1RPaths:
    base: Phase1Paths
    target_root: Path
    parts_root: Path
    native_freeze: Path
    output_files: dict[str, Path]
    report: Path
    status: Path
    contract: Path
    rnx2rtkp: Path


def _acquire_run_lock(target_root: Path) -> tuple[Path, str]:
    _assert_no_symlink_components(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_components(target_root)
    lock = target_root / "PHASE1R_RUN.lock"
    if lock.is_symlink():
        raise Phase1RRunnerError("Phase-1R run lock is a symlink")
    if lock.exists():
        try:
            prior = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prior = {}
        active = False
        if prior.get("hostname") == platform.node() and isinstance(prior.get("pid"), int):
            try:
                os.kill(int(prior["pid"]), 0)
                active = True
            except (OSError, ProcessLookupError):
                active = False
        if active:
            raise Phase1RRunnerError("another Phase-1R runner owns the target root")
        stale = target_root / f"PHASE1R_RUN.lock.stale.{time.time_ns()}"
        os.replace(lock, stale)
    token = uuid.uuid4().hex
    payload = json.dumps({
        "token": token, "pid": os.getpid(), "hostname": platform.node(),
        "created_unix": time.time(),
    }, sort_keys=True)
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return lock, token


def _release_run_lock(lock: Path, token: str) -> None:
    if not lock.is_file() or lock.is_symlink():
        return
    try:
        payload = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if payload.get("token") == token:
        lock.unlink()


def load_phase1r_paths(config_path: Path) -> Phase1RPaths:
    base = load_paths(config_path)
    target = base.stage_root / "02_EXT01_CLAMBDA/C00_VALIDATED"
    return Phase1RPaths(
        base=base,
        target_root=target,
        parts_root=target / ".epoch_parts",
        native_freeze=target / "PHASE1R_NATIVE_FREEZE.json",
        output_files={name: target / filename for name, filename in VALIDATED_FILENAMES.items()},
        report=base.stage_root / "11_REPORT/PHASE1R_EXT01_C00_VALIDITY_REPORT.md",
        status=base.stage_root / "11_REPORT/PHASE1R_STATUS.json",
        contract=base.code_root / "configs/paper_rebuild/horizontal_literature" / PHASE1R_CONTRACT,
        rnx2rtkp=base.rtklib_root / "app/consapp/rnx2rtkp/gcc/rnx2rtkp",
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, SignalIdentity):
        return identity_text(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    return value


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, np.ndarray)):
        return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv_atomic(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _csv_value(row.get(field)) for field in fields})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _assert_no_symlink_components(path: Path) -> None:
    """Reject an existing symlink in any lexical ancestor or final component."""
    absolute = path.absolute()
    cursor = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        cursor = cursor / component
        if cursor.is_symlink():
            raise Phase1RRunnerError(f"protected path crosses a symlink: {cursor}")


def _assert_contained(path: Path, root: Path) -> None:
    """Require lexical and, when existing, resolved containment without links."""
    _assert_no_symlink_components(root)
    _assert_no_symlink_components(path)
    lexical_root = root.absolute()
    lexical_path = path.absolute()
    try:
        lexical_path.relative_to(lexical_root)
    except ValueError as exc:
        raise Phase1RRunnerError(f"runtime path escapes protected root: {path}") from exc
    if root.exists() and path.exists():
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=True)
        if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
            raise Phase1RRunnerError(f"resolved runtime path escapes protected root: {path}")


def _hash_tree(root: Path) -> dict[str, str]:
    _assert_no_symlink_components(root)
    resolved_root = root.resolve(strict=True)
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise Phase1RRunnerError(f"protected tree contains a symlink: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if resolved_root not in resolved.parents:
            raise Phase1RRunnerError(f"protected tree file escapes root: {path}")
        rows[str(path.relative_to(root))] = sha256_file(path)
    return rows


def _tree_digest(rows: Mapping[str, str]) -> str:
    payload = "".join(f"{name}\0{digest}\n" for name, digest in sorted(rows.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git_lines(root: Path, *arguments: str) -> list[str]:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False, timeout=30
    )
    if result.returncode != 0:
        raise Phase1RRunnerError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.splitlines()


def _external_audit(paths: Phase1RPaths) -> dict[str, Any]:
    base = paths.base
    head = _git_lines(base.rtklib_root, "rev-parse", "HEAD")
    remote = _git_lines(base.rtklib_root, "remote", "get-url", "origin")
    tracked = _git_lines(base.rtklib_root, "status", "--short", "--untracked-files=no")
    status = _git_lines(base.rtklib_root, "status", "--short")
    allowed = {
        "?? app/consapp/convbin/gcc/convbin",
        "?? app/consapp/rnx2rtkp/gcc/rnx2rtkp",
        "?? lib/iers/gcc/iers.a",
    }
    if head != [RTKLIB_COMMIT] or remote != [RTKLIB_REMOTE] or tracked or set(status) != allowed:
        raise Phase1RRunnerError("pinned RTKLIB tree/source status differs from Phase-1R contract")
    license_path = base.rtklib_root / "LICENSE.txt"
    if sha256_file(license_path) != RTKLIB_LICENSE_SHA256:
        raise Phase1RRunnerError("RTKLIB license identity changed")
    required = (base.convbin, base.rtklib_bridge, base.lambda_library, paths.rnx2rtkp)
    if any(not path.is_file() for path in required):
        raise Phase1RRunnerError("a Phase-1R external executable/library is missing")
    bridge_sources = {}
    for name in ("legsa_rtklib_bridge.c", "legsa_rtklib_bridge.h", "Makefile", "README.md"):
        source = base.bridge_root / name
        if not source.is_file():
            raise Phase1RRunnerError(f"missing bridge source {name}")
        bridge_sources[name] = sha256_file(source)
    return {
        "url": RTKLIB_REMOTE,
        "commit": RTKLIB_COMMIT,
        "license": "BSD-2-Clause",
        "license_sha256": RTKLIB_LICENSE_SHA256,
        "tracked_patch": "none",
        "status_short": status,
        "binary_hashes": {
            "convbin": sha256_file(base.convbin),
            "rnx2rtkp": sha256_file(paths.rnx2rtkp),
            "satellite_state_bridge": sha256_file(base.rtklib_bridge),
            "lambda_library": sha256_file(base.lambda_library),
            "iers_archive": sha256_file(base.rtklib_root / "lib/iers/gcc/iers.a"),
        },
        "bridge_source_hashes": bridge_sources,
    }


def _validate_start(paths: Phase1RPaths, resume: bool) -> tuple[dict[str, str], dict[str, str]]:
    base = paths.base
    _assert_no_symlink_components(base.clean_root)
    _assert_contained(base.stage_root, base.clean_root)
    if not base.stage_root.is_dir():
        raise Phase1RRunnerError("immutable Phase-1 stage root is missing")
    original = base.stage_root / "02_EXT01_CLAMBDA/C00"
    required_original = (
        original / "EXT01_C00_NATIVE_HEADING_RESULTS.csv",
        original / "EXT01_C00_FAILURE_LEDGER.csv",
        original / "EXT01_C00_RUNTIME.csv",
    )
    if any(not path.is_file() for path in required_original):
        raise Phase1RRunnerError("immutable Phase-1 C00 output is incomplete")
    if not paths.contract.is_file():
        raise Phase1RRunnerError("Phase-1R tracked contract is missing")
    for protected in (
        original, paths.target_root, paths.parts_root, paths.native_freeze,
        paths.report, paths.status,
    ):
        _assert_contained(protected, base.stage_root)
    for output in paths.output_files.values():
        _assert_contained(output, paths.target_root)
    if paths.target_root.exists() and not resume:
        raise Phase1RRunnerError("validated output root already exists; use --resume")
    if not paths.target_root.exists() and (paths.report.exists() or paths.status.exists()):
        raise Phase1RRunnerError("Phase-1R report/status exists without validated root")
    lock = read_hash_lock(base.raw_hash_lock)
    raw_hashes = verify_raw_sources(base.raw_root, _raw_relatives(base), lock)
    original_hashes = _hash_tree(original)
    return raw_hashes, original_hashes


def _run_fingerprint(paths: Phase1RPaths, raw_hashes: Mapping[str, str],
                     external: Mapping[str, Any]) -> str:
    sources = (
        paths.base.code_root / "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
        paths.base.code_root / "src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
        paths.base.code_root / "src/legsa_gins/paper_rebuild/horizontal_literature/phase1r_runner.py",
        paths.base.code_root / "scripts/paper_rebuild/run_horizontal_literature_phase1r.py",
        paths.contract,
    )
    payload = {
        "raw": dict(raw_hashes),
        "sources": {str(path.relative_to(paths.base.code_root)): sha256_file(path) for path in sources},
        "length_m": LENGTH_M,
        "lambda_seed_count": LAMBDA_SEEDS,
        "node_limit": STRICT_NODE_LIMIT,
        "external_binary_hashes": dict(external["binary_hashes"]),
        "external_bridge_source_hashes": dict(external["bridge_source_hashes"]),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _prepare_inputs(paths: Phase1RPaths, fingerprint: str) -> tuple[Any, Any, tuple[Path, Path], tuple[Path, Path], dict[str, Any]]:
    cache = paths.target_root / ".cache" / fingerprint
    manifest_path = cache / "CACHE_MANIFEST.json"
    _assert_contained(cache, paths.target_root)
    cache.mkdir(parents=True, exist_ok=True)
    _assert_contained(cache, paths.target_root)
    _assert_contained(manifest_path, cache)
    ubx_paths = (cache / "gnss1_reconstructed.ubx", cache / "gnss2_reconstructed.ubx")
    reconstructions = []
    for source, output in zip((paths.base.receiver1_raw, paths.base.receiver2_raw), ubx_paths):
        _assert_contained(output, cache)
        reconstruction = reconstruct_ubx_stream(source)
        digest = hashlib.sha256(reconstruction.stream).hexdigest()
        if output.exists():
            if sha256_file(output) != digest:
                raise Phase1RRunnerError("Linux UBX cache hash mismatch")
        else:
            temporary = output.with_suffix(output.suffix + f".{os.getpid()}.tmp")
            temporary.write_bytes(reconstruction.stream)
            os.replace(temporary, output)
        reconstructions.append(reconstruction)
    observation_paths = (cache / "gnss1_reconstructed.obs", cache / "gnss2_reconstructed.obs")
    navigation_paths = (cache / "gnss1_reconstructed.nav", cache / "gnss2_reconstructed.nav")
    for artifact in (*observation_paths, *navigation_paths):
        _assert_contained(artifact, cache)
    prior_manifest = None
    if manifest_path.is_file():
        prior_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if prior_manifest.get("base_fingerprint") != fingerprint:
            raise Phase1RRunnerError("cache manifest fingerprint mismatch")
    convbin_commands = []
    for ubx, observation, navigation in zip(ubx_paths, observation_paths, navigation_paths):
        if prior_manifest is not None and observation.is_file() and navigation.is_file():
            convbin_commands.append(["CACHE_REUSE", str(ubx)])
            continue
        token = uuid.uuid4().hex
        obs_tmp = cache / f".{observation.name}.{token}.tmp"
        nav_tmp = cache / f".{navigation.name}.{token}.tmp"
        _assert_contained(obs_tmp, cache)
        _assert_contained(nav_tmp, cache)
        try:
            command = _run_convbin(paths.base.convbin, ubx, obs_tmp, nav_tmp)
            expected = (prior_manifest or {}).get("artifact_hashes", {})
            for generated, destination in (
                (obs_tmp, observation), (nav_tmp, navigation),
            ):
                generated_hash = sha256_file(generated)
                expected_hash = expected.get(destination.name)
                if expected_hash is not None and generated_hash != expected_hash:
                    raise Phase1RRunnerError(
                        f"regenerated cache artifact differs from manifest: {destination.name}"
                    )
                if destination.exists():
                    if sha256_file(destination) != generated_hash:
                        raise Phase1RRunnerError(
                            f"unmanifested cache artifact differs from deterministic regeneration: "
                            f"{destination.name}"
                        )
                    generated.unlink()
                else:
                    os.replace(generated, destination)
            convbin_commands.append(command)
        finally:
            for temporary in (obs_tmp, nav_tmp):
                if temporary.exists() and not temporary.is_symlink():
                    temporary.unlink()
    cache_audit = {
        "cache_root": str(cache),
        "parent_process_csv_reads": 2,
        "worker_csv_reads": 0,
        "ubx_hashes": {path.name: sha256_file(path) for path in ubx_paths},
        "observation_hashes": {path.name: sha256_file(path) for path in observation_paths},
        "navigation_hashes": {path.name: sha256_file(path) for path in navigation_paths},
        "convbin_commands": convbin_commands,
    }
    artifact_hashes = {
        **cache_audit["ubx_hashes"],
        **cache_audit["observation_hashes"],
        **cache_audit["navigation_hashes"],
    }
    if prior_manifest is not None:
        if prior_manifest.get("artifact_hashes") != artifact_hashes:
            raise Phase1RRunnerError("cached UBX/OBS/NAV differs from its creation manifest")
    else:
        write_json_atomic(manifest_path, {
            "schema_version": "horizontal_literature.phase1r_cache.v1",
            "base_fingerprint": fingerprint,
            "artifact_hashes": artifact_hashes,
            "raw_csv_read_by_parent_only": True,
            "worker_csv_read_count": 0,
        })
    cache_audit["cache_manifest_sha256"] = sha256_file(manifest_path)
    return reconstructions[0], reconstructions[1], navigation_paths, observation_paths, cache_audit


def _epoch_fingerprint(base_fingerprint: str, cache_audit: Mapping[str, Any]) -> str:
    payload = {
        "base_fingerprint": base_fingerprint,
        "ubx_hashes": cache_audit["ubx_hashes"],
        "observation_hashes": cache_audit["observation_hashes"],
        "navigation_hashes": cache_audit["navigation_hashes"],
        "cache_manifest_sha256": cache_audit["cache_manifest_sha256"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _precompute_spp(pairs: Sequence[tuple[Any, Any]], bridge: Path,
                    navigation_paths: Sequence[Path]) -> tuple[list[list[float] | None], list[str | None]]:
    positions: list[list[float] | None] = []
    failures: list[str | None] = []
    previous: np.ndarray | None = None
    with RtklibBroadcastProvider(bridge, navigation_paths) as provider:
        for receiver1, _receiver2 in pairs:
            try:
                solution = gps_l1_code_spp(receiver1, provider, previous)
                previous = solution.position_ecef_m
                positions.append(previous.tolist())
                failures.append(None)
            except (RawBackendError, ValueError, np.linalg.LinAlgError) as exc:
                positions.append(None)
                failures.append(f"{type(exc).__name__}:{exc}")
    return positions, failures


_WORKER_PAIRS: Sequence[tuple[Any, Any]] = ()
_WORKER_POSITIONS: Sequence[list[float] | None] = ()
_WORKER_SPP_FAILURES: Sequence[str | None] = ()
_WORKER_PROVIDER: RtklibBroadcastProvider | None = None
_WORKER_LAMBDA: Path | None = None


def _set_worker_inputs(pairs: Sequence[tuple[Any, Any]], positions: Sequence[list[float] | None],
                       spp_failures: Sequence[str | None]) -> None:
    global _WORKER_PAIRS, _WORKER_POSITIONS, _WORKER_SPP_FAILURES
    _WORKER_PAIRS = pairs
    _WORKER_POSITIONS = positions
    _WORKER_SPP_FAILURES = spp_failures


def _worker_init(bridge: str, navigation_paths: Sequence[str], lambda_library: str) -> None:
    global _WORKER_PROVIDER, _WORKER_LAMBDA
    for name in THREAD_ENVIRONMENT:
        os.environ[name] = "1"
    _WORKER_PROVIDER = RtklibBroadcastProvider(
        Path(bridge), tuple(Path(path) for path in navigation_paths)
    )
    _WORKER_LAMBDA = Path(lambda_library)


def _empty_condition() -> dict[str, Any]:
    return {field: None for field in (
        "observation_count", "unknown_count", "raw_design_rank", "raw_design_condition",
        "covariance_condition", "raw_normal_rank", "raw_normal_condition",
        "whitened_design_rank", "whitened_design_condition", "whitened_normal_rank",
        "whitened_normal_condition",
    )}


def _model_payload(model: Any, receiver_position: Sequence[float]) -> dict[str, Any]:
    return {
        "observation": model.observation_m.tolist(),
        "ambiguity_design": model.ambiguity_design_m.tolist(),
        "baseline_design": model.baseline_design.tolist(),
        "covariance": model.covariance_m2.tolist(),
        "receiver_position_ecef_m": list(receiver_position),
        "pivot_identity": model.pivot_identity,
        "ambiguity_satellite_identities": [identity_text(item) for item in model.satellites],
    }


def _worker_epoch(index: int) -> dict[str, Any]:
    if _WORKER_PROVIDER is None or _WORKER_LAMBDA is None:
        raise Phase1RRunnerError("worker not initialized")
    receiver1, receiver2 = _WORKER_PAIRS[index]
    started = time.perf_counter()
    accounting = gps_l1_epoch_accounting(receiver1, receiver2)
    counts = accounting.as_counts()
    key = {
        "epoch_index": index,
        "gps_week": receiver1.gps_week,
        "gps_tow_seconds": receiver1.gps_tow_seconds,
    }
    failure_code: str | None = None
    model = None
    solve = None
    condition = _empty_condition()
    result: dict[str, Any] = {
        **key,
        "row_status": "FAILURE",
        "failure_code": None,
        "integer_solution_returned": False,
        "global_optimum_certified": False,
        "ambiguity_acceptance_test_defined": False,
        "ambiguity_accepted": None,
        "integer_solution_availability": False,
        "search_complete": False,
        "baseline_ecef_m": None,
        "baseline_ned_m": None,
        "baseline_length_m": None,
        "baseline_heading_deg": None,
        "body_yaw_deg": None,
        "pivot_identity": None,
        "pivot_changed": False,
        "ambiguity_satellite_identities": [],
        "ambiguity_signal_identities": [],
        "ambiguity_vector": [],
        "receiver_order": "GNSS2_MINUS_GNSS1",
        "dd_sign_convention": "(GNSS2-GNSS1)_SATELLITE_MINUS_PIVOT",
        "phase_convention": HALF_CYCLE_CONTRACT.phase_value_policy,
        "ratio": None,
        "ratio_valid": False,
        "best_total_objective": None,
        "second_total_objective": None,
        "ambiguity_quadratic_term": None,
        "conditional_baseline_constraint_term": None,
        "whitened_code_residual_norm": None,
        "whitened_phase_residual_norm": None,
        "whitened_total_residual_norm": None,
        "code_phase_cross_covariance_zero": None,
        "constraint_error_m": None,
    }
    search = {
        **key,
        "lambda_seed_count_requested": LAMBDA_SEEDS,
        "lambda_seed_count_returned": 0,
        "branch_and_bound_nodes_expanded": 0,
        "integer_leaves_evaluated": 0,
        "unique_integer_candidates_evaluated": 0,
        "frontier_lower_bound_at_termination": None,
        "best_total_objective": None,
        "second_total_objective": None,
        "termination_reason": "NO_FEASIBLE_MODEL",
        "global_optimum_certified": False,
        "runtime_budget_exhausted": False,
        "configured_node_limit": STRICT_NODE_LIMIT,
        "node_limit_exhausted": False,
        "candidate_cap_applied": False,
    }
    payload = None
    try:
        position = _WORKER_POSITIONS[index]
        if position is None:
            raise DoubleDifferenceStageError(
                "SPP_POSITION_UNAVAILABLE",
                _WORKER_SPP_FAILURES[index] or "GPS L1 raw-code SPP unavailable",
                accounting,
            )
        model = build_gps_l1_double_difference_model(
            receiver1, receiver2, _WORKER_PROVIDER, position, previous_pivot=None
        )
        accounting = model.accounting
        counts = accounting.as_counts()
        condition = asdict(dd_matrix_condition_diagnostics(model))
        payload = _model_payload(model, position)
        solve = solve_clambda(
            model.observation_m,
            model.ambiguity_design_m,
            model.baseline_design,
            model.covariance_m2,
            length_m=LENGTH_M,
            lambda_bridge_path=_WORKER_LAMBDA,
            strict=True,
            initial_candidate_count=LAMBDA_SEEDS,
            strict_node_limit=STRICT_NODE_LIMIT,
            timeout_seconds=STRICT_WALL_BUDGET_SECONDS,
        )
        for field in search:
            if hasattr(solve, field):
                search[field] = getattr(solve, field)
        search.update({"epoch_index": index, "gps_week": receiver1.gps_week,
                       "gps_tow_seconds": receiver1.gps_tow_seconds})
        result.update({
            "pivot_identity": model.pivot_identity,
            "ambiguity_satellite_identities": [identity_text(item) for item in model.satellites],
            "ambiguity_signal_identities": list(model.ambiguity_signal_identities),
            "receiver_order": model.receiver_order,
            "dd_sign_convention": model.dd_sign_convention,
            "phase_convention": model.phase_convention,
            "global_optimum_certified": bool(solve.global_optimum_certified),
            "search_complete": bool(solve.global_optimum_certified),
        })
        if not solve.global_optimum_certified or solve.best is None:
            failure_code = solve.failure_code or solve.termination_reason
        else:
            best = solve.best
            baseline_ned = _ecef_vector_to_ned(best.baseline, position)
            evaluation = evaluate_production_objective(
                solve.float_solution,
                best.ambiguity,
                LENGTH_M,
                model.observation_m,
                model.ambiguity_design_m,
                model.baseline_design,
                model.covariance_m2,
                code_observation_count=len(model.satellites),
            )
            result.update({
                "row_status": "NATIVE_INTEGER_RESULT",
                "integer_solution_returned": True,
                "integer_solution_availability": True,
                "ambiguity_vector": best.ambiguity.tolist(),
                "baseline_ecef_m": best.baseline.tolist(),
                "baseline_ned_m": baseline_ned.tolist(),
                "baseline_length_m": float(np.linalg.norm(baseline_ned)),
                "baseline_heading_deg": float(math.degrees(math.atan2(baseline_ned[1], baseline_ned[0]))),
                "body_yaw_deg": body_yaw_from_ned_baseline(baseline_ned),
                "ratio": solve.ratio,
                "ratio_valid": solve.ratio_valid,
                "best_total_objective": best.total_constrained_objective,
                "second_total_objective": (solve.second.total_constrained_objective
                                             if solve.second is not None else None),
                "ambiguity_quadratic_term": evaluation.ambiguity_quadratic_term,
                "conditional_baseline_constraint_term": evaluation.conditional_baseline_constraint_term,
                "whitened_code_residual_norm": evaluation.whitened_code_residual_norm,
                "whitened_phase_residual_norm": evaluation.whitened_phase_residual_norm,
                "whitened_total_residual_norm": evaluation.whitened_total_residual_norm,
                "code_phase_cross_covariance_zero": evaluation.code_phase_cross_covariance_zero,
                "constraint_error_m": best.constraint_error_m,
            })
    except DoubleDifferenceStageError as exc:
        failure_code = exc.code
        if exc.accounting is not None and hasattr(exc.accounting, "as_counts"):
            counts = exc.accounting.as_counts()
    except (RawBackendError, ValueError, np.linalg.LinAlgError) as exc:
        failure_code = "NUMERICAL_FAILURE"
        result["failure_detail"] = f"{type(exc).__name__}:{exc}"
    if failure_code is not None:
        result["failure_code"] = failure_code
    elapsed = time.perf_counter() - started
    runtime = {
        **key,
        "row_status": result["row_status"],
        "failure_code": failure_code,
        "runtime_seconds": elapsed,
        "worker_pid": os.getpid(),
        "branch_and_bound_nodes_expanded": search["branch_and_bound_nodes_expanded"],
        "integer_leaves_evaluated": search["integer_leaves_evaluated"],
    }
    dd = {
        **key,
        "row_status": result["row_status"],
        "failure_code": failure_code,
        **counts,
        **condition,
        "pivot_identity": result["pivot_identity"],
        "ambiguity_dimension": len(result["ambiguity_satellite_identities"]),
        "receiver_order": result["receiver_order"],
        "dd_sign_convention": result["dd_sign_convention"],
        "phase_convention": result["phase_convention"],
    }
    if len(result["ambiguity_satellite_identities"]) != len(result["ambiguity_vector"]):
        if result["integer_solution_returned"]:
            raise Phase1RRunnerError("ambiguity identity/vector alignment failed")
    return {
        "schema_version": "horizontal_literature.phase1r_epoch_part.v1",
        "result": result,
        "runtime": runtime,
        "dd": dd,
        "search": search,
        "model": payload,
    }


def _part_path(parts_root: Path, index: int) -> Path:
    return parts_root / f"epoch_{index:04d}.json"


def _write_part(path: Path, fingerprint: str, part: Mapping[str, Any]) -> None:
    payload = dict(part)
    payload["run_fingerprint"] = fingerprint
    write_json_atomic(path, _jsonable(payload))


def _read_part(path: Path, fingerprint: str, index: int) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("run_fingerprint") != fingerprint
            or payload.get("result", {}).get("epoch_index") != index):
        raise Phase1RRunnerError(f"stale or malformed epoch part: {path.name}")
    return payload


def _run_epoch_parts(paths: Phase1RPaths, fingerprint: str, pairs: Sequence[tuple[Any, Any]],
                     positions: Sequence[list[float] | None], spp_failures: Sequence[str | None],
                     navigation_paths: Sequence[Path], workers: int,
                     indices: Sequence[int] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not 1 <= workers <= MAX_WORKERS:
        raise Phase1RRunnerError(f"workers must be in 1..{MAX_WORKERS}")
    selected = list(range(len(pairs))) if indices is None else list(indices)
    if (len(selected) != len(set(selected))
            or any(index < 0 or index >= len(pairs) for index in selected)):
        raise Phase1RRunnerError("epoch-part selection is duplicate or out of range")
    _assert_contained(paths.parts_root, paths.target_root)
    paths.parts_root.mkdir(parents=True, exist_ok=True)
    _assert_contained(paths.parts_root, paths.target_root)
    completed: dict[int, dict[str, Any]] = {}
    pending = []
    for index in selected:
        part_path = _part_path(paths.parts_root, index)
        _assert_contained(part_path, paths.parts_root)
        if part_path.is_file():
            completed[index] = _read_part(part_path, fingerprint, index)
        else:
            pending.append(index)
    _set_worker_inputs(pairs, positions, spp_failures)
    started = time.perf_counter()
    worker_pids: set[int] = set()
    if pending and workers == 1:
        _worker_init(str(paths.base.rtklib_bridge), [str(path) for path in navigation_paths],
                     str(paths.base.lambda_library))
        for index in pending:
            part = _worker_epoch(index)
            worker_pids.add(int(part["runtime"]["worker_pid"]))
            part_path = _part_path(paths.parts_root, index)
            _assert_contained(part_path, paths.parts_root)
            _write_part(part_path, fingerprint, part)
            completed[index] = part
    elif pending:
        context = mp.get_context("fork")
        with context.Pool(
            processes=workers,
            initializer=_worker_init,
            initargs=(str(paths.base.rtklib_bridge), [str(path) for path in navigation_paths],
                      str(paths.base.lambda_library)),
        ) as pool:
            for part in pool.imap_unordered(_worker_epoch, pending, chunksize=1):
                index = int(part["result"]["epoch_index"])
                worker_pids.add(int(part["runtime"]["worker_pid"]))
                part_path = _part_path(paths.parts_root, index)
                _assert_contained(part_path, paths.parts_root)
                _write_part(part_path, fingerprint, part)
                completed[index] = part
    ordered = [completed[index] for index in sorted(selected)]
    return ordered, {
        "requested_workers": workers,
        "worker_pid_count": len(worker_pids),
        "worker_pids": sorted(worker_pids),
        "resumed_part_count": len(selected) - len(pending),
        "computed_part_count": len(pending),
        "wall_seconds": time.perf_counter() - started,
        "stable_output_order": "ORIGINAL_EXACT_PAIR_INDEX",
    }


def _resource_probe(paths: Phase1RPaths) -> dict[str, Any]:
    memory = subprocess.run(["free", "-b"], text=True, capture_output=True, check=False)
    load = Path("/proc/loadavg").read_text(encoding="ascii").strip()
    temperatures: dict[str, float] = {}
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            temperatures[path.parent.name] = float(path.read_text().strip()) / 1000.0
        except (OSError, ValueError):
            continue
    stat = os.statvfs(paths.base.stage_root)
    start = time.perf_counter()
    read_bytes = 0
    with paths.base.receiver1_raw.open("rb") as stream:
        while read_bytes < 32 * 1024 * 1024:
            block = stream.read(min(4 * 1024 * 1024, 32 * 1024 * 1024 - read_bytes))
            if not block:
                break
            read_bytes += len(block)
    elapsed = max(time.perf_counter() - start, 1e-12)
    return {
        "timestamp_unix": time.time(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count(),
        "loadavg": load,
        "free_b_output": memory.stdout.splitlines(),
        "temperatures_c": temperatures,
        "mnt_g_available_bytes": stat.f_bavail * stat.f_frsize,
        "mnt_g_read_probe_bytes": read_bytes,
        "mnt_g_read_probe_seconds": elapsed,
        "mnt_g_read_probe_mib_per_second": read_bytes / elapsed / (1024.0 * 1024.0),
        "selected_workers": DEFAULT_WORKERS,
        "maximum_workers_not_used": MAX_WORKERS,
        "numerical_thread_environment": {name: os.environ.get(name) for name in THREAD_ENVIRONMENT},
    }


def _scientific_part(part: Mapping[str, Any]) -> dict[str, Any]:
    """Strip scheduling-only fields for the worker-count equality proof."""
    value = json.loads(json.dumps(_jsonable(part), sort_keys=True))
    value.pop("run_fingerprint", None)
    value.get("runtime", {}).pop("runtime_seconds", None)
    value.get("runtime", {}).pop("worker_pid", None)
    return value


def _worker_determinism_audit(
    paths: Phase1RPaths,
    fingerprint: str,
    pairs: Sequence[tuple[Any, Any]],
    positions: Sequence[list[float] | None],
    spp_failures: Sequence[str | None],
    navigation_paths: Sequence[Path],
) -> dict[str, Any]:
    indices = sorted(set([0, 1, 2, 100, 431, 432, 994, len(pairs) - 1]))
    one_paths = replace(paths, parts_root=paths.target_root / ".determinism/workers_1")
    sixteen_paths = replace(paths, parts_root=paths.target_root / ".determinism/workers_16")
    one, one_run = _run_epoch_parts(
        one_paths, fingerprint, pairs, positions, spp_failures, navigation_paths, 1, indices
    )
    sixteen, sixteen_run = _run_epoch_parts(
        sixteen_paths, fingerprint, pairs, positions, spp_failures, navigation_paths, 16, indices
    )
    equal = [_scientific_part(left) == _scientific_part(right)
             for left, right in zip(one, sixteen)]
    return {
        "subset_indices": indices,
        "subset_count": len(indices),
        "workers_1": one_run,
        "workers_16": sixteen_run,
        "row_level_scientific_equality": all(equal),
        "differing_indices": [index for index, same in zip(indices, equal) if not same],
        "worker_failure_count": 0,
    }


def _tracking_rows(
    pairs: Sequence[tuple[Any, Any]], parts: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[tuple[int, int, str], dict[str, Any]]]:
    continuity = TrackingContinuity()
    rows: list[dict[str, Any]] = []
    event_map: dict[tuple[int, int, str], dict[str, Any]] = {}
    previous_pivot: str | None = None
    previous_satellite_set: tuple[str, ...] | None = None
    for index, ((receiver1, receiver2), part) in enumerate(zip(pairs, parts)):
        result = part["result"]
        model = part.get("model")
        pivot = result.get("pivot_identity")
        satellite_set = tuple((model or {}).get("ambiguity_satellite_identities", ()))
        pivot_changed = previous_pivot is not None and pivot is not None and pivot != previous_pivot
        satellite_set_changed = (
            previous_satellite_set is not None and satellite_set != previous_satellite_set
        )
        result["pivot_changed"] = pivot_changed
        part["dd"]["pivot_changed"] = pivot_changed
        if pivot is not None:
            previous_pivot = pivot
        previous_satellite_set = satellite_set
        used = set(satellite_set)
        if pivot is not None:
            used.add(pivot)
        receiver_summaries: dict[int, dict[str, Any]] = {}
        receiver_truth: dict[int, list[dict[str, Any]]] = {}
        for receiver, epoch in ((1, receiver1), (2, receiver2)):
            truth: list[dict[str, Any]] = []
            for measurement in epoch.measurements:
                flags = continuity.update(
                    receiver, epoch, measurement, ambiguity_reinitialized_by_method=True
                )
                identity = identity_text(measurement.identity)
                item = {
                    **measurement.tracking_audit(),
                    "recStat": epoch.receiver_status,
                    "receiver_clock_reset": flags.receiver_clock_reset,
                    "tracking_lock_reset_detected": flags.tracking_lock_reset_detected,
                    "cycle_slip_detected": flags.cycle_slip_detected,
                    "half_cycle_state_changed": flags.half_cycle_state_changed,
                    "carrier_validity_changed": flags.carrier_validity_changed,
                    "time_reversal_detected": flags.time_reversal_detected,
                    "arc_reset_due_to_tracking": flags.arc_reset_due_to_tracking,
                    "used_by_dd": identity in used,
                }
                truth.append(item)
                event_map[(index, receiver, identity)] = item
            gps_l1 = [item for item in truth if item["identity"].split(":")[0::2] == ["0", "0"]]
            # The split predicate above is gnssId==0 and sigId==0; freqId is
            # checked explicitly to avoid silently including GPS L2.
            gps_l1 = [item for item in gps_l1 if item["identity"].split(":")[3] == "0"]
            receiver_truth[receiver] = truth
            receiver_summaries[receiver] = {
                "measurement_count": len(gps_l1),
                "used_carrier_count": sum(item["used_by_dd"] for item in gps_l1),
                "excluded_cp_invalid_count": sum(not item["cpValid"] for item in gps_l1),
                "excluded_half_cycle_unknown_count": sum(
                    item["cpValid"] and not item["halfCyc"] for item in gps_l1
                ),
                "sub_half_cycle_set_count": sum(item["subHalfCyc"] for item in gps_l1),
                "actual_lock_reset_count": sum(
                    item["tracking_lock_reset_detected"] for item in gps_l1
                ),
                "actual_cycle_slip_count": sum(item["cycle_slip_detected"] for item in gps_l1),
                "half_cycle_state_change_count": sum(
                    item["half_cycle_state_changed"] for item in gps_l1
                ),
                "receiver_clock_reset_count": sum(
                    item["receiver_clock_reset"] for item in gps_l1
                ),
            }
        first = receiver_summaries[1]
        second = receiver_summaries[2]
        rows.append({
            "epoch_index": index,
            "gps_week": receiver1.gps_week,
            "gps_tow_seconds": receiver1.gps_tow_seconds,
            "measurement_count_receiver1": first["measurement_count"],
            "measurement_count_receiver2": second["measurement_count"],
            "used_carrier_count": len(used),
            "used_carrier_count_receiver1": first["used_carrier_count"],
            "used_carrier_count_receiver2": second["used_carrier_count"],
            "excluded_cp_invalid_count": (
                first["excluded_cp_invalid_count"] + second["excluded_cp_invalid_count"]
            ),
            "excluded_half_cycle_unknown_count": (
                first["excluded_half_cycle_unknown_count"]
                + second["excluded_half_cycle_unknown_count"]
            ),
            "sub_half_cycle_set_count_receiver1": first["sub_half_cycle_set_count"],
            "sub_half_cycle_set_count_receiver2": second["sub_half_cycle_set_count"],
            "actual_lock_reset_count": (
                first["actual_lock_reset_count"] + second["actual_lock_reset_count"]
            ),
            "actual_cycle_slip_count": (
                first["actual_cycle_slip_count"] + second["actual_cycle_slip_count"]
            ),
            "half_cycle_state_change_count": (
                first["half_cycle_state_change_count"]
                + second["half_cycle_state_change_count"]
            ),
            "receiver_clock_reset_count": (
                first["receiver_clock_reset_count"] + second["receiver_clock_reset_count"]
            ),
            "ambiguity_reinitialized_by_method": True,
            "pivot_changed": pivot_changed,
            "satellite_set_changed": satellite_set_changed,
            "measurement_truth_receiver1": receiver_truth[1],
            "measurement_truth_receiver2": receiver_truth[2],
        })
    return rows, event_map


RESULT_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "row_status", "failure_code",
    "integer_solution_returned", "global_optimum_certified",
    "ambiguity_acceptance_test_defined", "ambiguity_accepted",
    "integer_solution_availability", "search_complete", "baseline_ecef_m",
    "baseline_ned_m", "baseline_length_m", "baseline_heading_deg", "body_yaw_deg",
    "pivot_identity", "pivot_changed", "ambiguity_satellite_identities",
    "ambiguity_signal_identities", "ambiguity_vector", "receiver_order",
    "dd_sign_convention", "phase_convention", "ratio", "ratio_valid",
    "best_total_objective", "second_total_objective", "ambiguity_quadratic_term",
    "conditional_baseline_constraint_term", "whitened_code_residual_norm",
    "whitened_phase_residual_norm", "whitened_total_residual_norm",
    "code_phase_cross_covariance_zero", "constraint_error_m", "failure_detail",
)
FAILURE_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "failure_code",
    "termination_reason", "global_optimum_certified", "runtime_seconds",
)
RUNTIME_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "row_status", "failure_code",
    "runtime_seconds", "worker_pid", "branch_and_bound_nodes_expanded",
    "integer_leaves_evaluated",
)
DD_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "row_status", "failure_code",
    "common_raw_satellite_count", "common_pr_valid_satellite_count",
    "common_cp_valid_satellite_count", "common_pr_cp_valid_satellite_count",
    "common_half_cycle_valid_satellite_count", "common_integer_compatible_satellite_count",
    "common_rtklib_phase_compatible_satellite_count",
    "satellite_state_available_count", "elevation_eligible_satellite_count",
    "dd_eligible_satellite_count", "observation_count", "unknown_count",
    "raw_design_rank", "raw_design_condition", "covariance_condition",
    "raw_normal_rank", "raw_normal_condition", "whitened_design_rank",
    "whitened_design_condition", "whitened_normal_rank", "whitened_normal_condition",
    "pivot_identity", "pivot_changed", "ambiguity_dimension", "receiver_order",
    "dd_sign_convention", "phase_convention",
)
TRACKING_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "measurement_count_receiver1",
    "measurement_count_receiver2", "used_carrier_count", "used_carrier_count_receiver1",
    "used_carrier_count_receiver2", "excluded_cp_invalid_count",
    "excluded_half_cycle_unknown_count", "sub_half_cycle_set_count_receiver1",
    "sub_half_cycle_set_count_receiver2", "actual_lock_reset_count", "actual_cycle_slip_count",
    "half_cycle_state_change_count", "receiver_clock_reset_count",
    "ambiguity_reinitialized_by_method", "pivot_changed", "satellite_set_changed",
    "measurement_truth_receiver1", "measurement_truth_receiver2",
)
SEARCH_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "lambda_seed_count_requested",
    "lambda_seed_count_returned", "branch_and_bound_nodes_expanded",
    "integer_leaves_evaluated", "unique_integer_candidates_evaluated",
    "frontier_lower_bound_at_termination", "best_total_objective",
    "second_total_objective", "termination_reason", "global_optimum_certified",
    "runtime_budget_exhausted", "configured_node_limit", "node_limit_exhausted",
    "candidate_cap_applied",
)


def _write_native_outputs(
    paths: Phase1RPaths,
    parts: Sequence[dict[str, Any]],
    tracking: Sequence[dict[str, Any]],
    fingerprint: str,
    raw_hashes: Mapping[str, str],
    original_hashes: Mapping[str, str],
    worker_audit: Mapping[str, Any],
    determinism: Mapping[str, Any],
    resource_probe: Mapping[str, Any],
) -> dict[str, Any]:
    results = [part["result"] for part in parts]
    runtimes = [part["runtime"] for part in parts]
    dd = [part["dd"] for part in parts]
    search = [part["search"] for part in parts]
    failures = [
        {
            "epoch_index": result["epoch_index"],
            "gps_week": result["gps_week"],
            "gps_tow_seconds": result["gps_tow_seconds"],
            "failure_code": result["failure_code"],
            "termination_reason": search_row["termination_reason"],
            "global_optimum_certified": result["global_optimum_certified"],
            "runtime_seconds": runtime["runtime_seconds"],
        }
        for result, search_row, runtime in zip(results, search, runtimes)
        if not result["integer_solution_returned"]
    ]
    _write_csv_atomic(paths.output_files["native"], results, RESULT_FIELDS)
    _write_csv_atomic(paths.output_files["failures"], failures, FAILURE_FIELDS)
    _write_csv_atomic(paths.output_files["runtime"], runtimes, RUNTIME_FIELDS)
    _write_csv_atomic(paths.output_files["dd"], dd, DD_FIELDS)
    _write_csv_atomic(paths.output_files["tracking"], tracking, TRACKING_FIELDS)
    _write_csv_atomic(paths.output_files["search"], search, SEARCH_FIELDS)
    hashes = {name: sha256_file(paths.output_files[name]) for name in NATIVE_FREEZE_NAMES}
    freeze = {
        "schema_version": "horizontal_literature.phase1r_native_freeze.v1",
        "run_fingerprint": fingerprint,
        "native_hashes": hashes,
        "native_frozen_before_trace_open": True,
        "trace_open_count_at_freeze": 0,
        "raw_source_hashes": dict(raw_hashes),
        "original_c00_hashes": dict(original_hashes),
        "original_c00_tree_digest": _tree_digest(original_hashes),
        "paired_epoch_count": len(parts),
        "native_row_count": len(results),
        "failure_row_count": len(failures),
        "worker_audit": dict(worker_audit),
        "worker_determinism": dict(determinism),
        "resource_probe": dict(resource_probe),
        "canonical541_accessed": False,
        "ext02_ext03_ext04_run": False,
        "classic18_run": False,
    }
    write_json_atomic(paths.native_freeze, _jsonable(freeze))
    return freeze


def _csv_data_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        try:
            next(reader)
        except StopIteration as exc:
            raise Phase1RRunnerError(f"native CSV has no header: {path.name}") from exc
        return sum(1 for _row in reader)


def _validate_native_freeze(
    paths: Phase1RPaths,
    *,
    fingerprint: str | None = None,
    raw_hashes: Mapping[str, str] | None = None,
    original_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    _assert_contained(paths.native_freeze, paths.target_root)
    for output in paths.output_files.values():
        _assert_contained(output, paths.target_root)
    freeze = json.loads(paths.native_freeze.read_text(encoding="utf-8"))
    if set(freeze.get("native_hashes", {})) != set(NATIVE_FREEZE_NAMES):
        raise Phase1RRunnerError("native hash freeze inventory is incomplete")
    for name, digest in freeze.get("native_hashes", {}).items():
        if name not in NATIVE_FREEZE_NAMES or sha256_file(paths.output_files[name]) != digest:
            raise Phase1RRunnerError("native hash freeze revalidation failed before diagnostics")
    if (freeze.get("native_frozen_before_trace_open") is not True
            or freeze.get("trace_open_count_at_freeze") != 0):
        raise Phase1RRunnerError("native freeze does not prove zero pre-freeze trace opens")
    if (freeze.get("paired_epoch_count") != EXPECTED_PAIR_COUNT
            or freeze.get("native_row_count") != EXPECTED_PAIR_COUNT):
        raise Phase1RRunnerError("native freeze does not conserve all paired epochs")
    failure_count = freeze.get("failure_row_count")
    if (not isinstance(failure_count, int)
            or not 0 <= failure_count <= EXPECTED_PAIR_COUNT):
        raise Phase1RRunnerError("native freeze failure-row count is invalid")
    expected_rows = {
        "native": EXPECTED_PAIR_COUNT,
        "failures": failure_count,
        "runtime": EXPECTED_PAIR_COUNT,
        "dd": EXPECTED_PAIR_COUNT,
        "tracking": EXPECTED_PAIR_COUNT,
        "search": EXPECTED_PAIR_COUNT,
    }
    for name, expected in expected_rows.items():
        if _csv_data_row_count(paths.output_files[name]) != expected:
            raise Phase1RRunnerError(f"native freeze row count mismatch: {name}")
    if freeze.get("worker_determinism", {}).get("row_level_scientific_equality") is not True:
        raise Phase1RRunnerError("native freeze lacks worker-count determinism evidence")
    if fingerprint is not None and freeze.get("run_fingerprint") != fingerprint:
        raise Phase1RRunnerError("native freeze run fingerprint differs from current run")
    if raw_hashes is not None and freeze.get("raw_source_hashes") != dict(raw_hashes):
        raise Phase1RRunnerError("native freeze raw-source provenance differs from current run")
    if original_hashes is not None:
        if (freeze.get("original_c00_hashes") != dict(original_hashes)
                or freeze.get("original_c00_tree_digest") != _tree_digest(original_hashes)):
            raise Phase1RRunnerError(
                "native freeze original-C00 provenance differs from current run"
            )
    return freeze


def _nearest_hpposecef(reconstruction: Any, tow_seconds: float) -> tuple[Any, int]:
    target = round(tow_seconds * 1000.0)
    if not reconstruction.nav_hpposecef_epochs:
        raise Phase1RRunnerError("NAV-HPPOSECEF diagnostic stream is absent")
    epoch = min(
        reconstruction.nav_hpposecef_epochs,
        key=lambda item: (abs(item.itow_ms - target), item.itow_ms),
    )
    offset = int(epoch.itow_ms - target)
    if abs(offset) > 10:
        raise Phase1RRunnerError("NAV-HPPOSECEF is not within the fixed 10 ms diagnostic gate")
    return epoch, offset


def _proxy_baselines(reconstruction1: Any, reconstruction2: Any,
                     pairs: Sequence[tuple[Any, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, (receiver1, _receiver2) in enumerate(pairs):
        first, offset1 = _nearest_hpposecef(reconstruction1, receiver1.gps_tow_seconds)
        second, offset2 = _nearest_hpposecef(reconstruction2, receiver1.gps_tow_seconds)
        baseline_ecef = second.position_ecef_m - first.position_ecef_m
        midpoint = (second.position_ecef_m + first.position_ecef_m) * 0.5
        baseline_ned = _ecef_vector_to_ned(baseline_ecef, midpoint)
        rows.append({
            "epoch_index": index,
            "gps_week": receiver1.gps_week,
            "gps_tow_seconds": receiver1.gps_tow_seconds,
            "hpposecef_offset_receiver1_ms": offset1,
            "hpposecef_offset_receiver2_ms": offset2,
            "proxy_baseline_ecef_m": baseline_ecef,
            "proxy_baseline_ned_m": baseline_ned,
            "proxy_length_m": float(np.linalg.norm(baseline_ecef)),
            "proxy_body_yaw_deg": body_yaw_from_ned_baseline(baseline_ned),
            "proxy_midpoint_ecef_m": midpoint,
        })
    return rows


def _fractional_cycle(value: float) -> float:
    return (float(value) + 0.5) % 1.0 - 0.5


def _vector_angle_degrees(first: Sequence[float], second: Sequence[float]) -> float | None:
    left = np.asarray(first, dtype=float)
    right = np.asarray(second, dtype=float)
    norm = float(np.linalg.norm(left) * np.linalg.norm(right))
    if not math.isfinite(norm) or norm <= 0:
        return None
    cosine = float(np.clip(np.dot(left, right) / norm, -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def _measurement_map(epoch: Any) -> dict[str, Any]:
    return {identity_text(measurement.identity): measurement for measurement in epoch.measurements}


def _proxy_objective_diagnostics(
    pairs: Sequence[tuple[Any, Any]],
    parts: Sequence[dict[str, Any]],
    proxies: Sequence[dict[str, Any]],
    event_map: Mapping[tuple[int, int, str], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    proxy_rows: list[dict[str, Any]] = []
    fraction_rows: list[dict[str, Any]] = []
    production_worse_count = 0
    objective_identity_max = 0.0
    production_evaluated_count = 0
    proxy_evaluated_count = 0
    cross_covariance_nonzero_count = 0
    for index, ((receiver1, receiver2), part, proxy) in enumerate(zip(pairs, parts, proxies)):
        result = part["result"]
        model_payload = part.get("model")
        row: dict[str, Any] = {
            **{key: proxy[key] for key in (
                "epoch_index", "gps_week", "gps_tow_seconds",
                "hpposecef_offset_receiver1_ms", "hpposecef_offset_receiver2_ms",
                "proxy_length_m", "proxy_body_yaw_deg",
            )},
            "proxy_baseline_ecef_m": proxy["proxy_baseline_ecef_m"],
            "proxy_baseline_ned_m": proxy["proxy_baseline_ned_m"],
            "native_integer_solution_returned": result["integer_solution_returned"],
            "native_body_yaw_deg": result["body_yaw_deg"],
            "native_minus_proxy_yaw_error_deg": None,
            "native_proxy_vector_angle_deg": None,
            "production_ambiguity_vector": result["ambiguity_vector"],
            "proxy_ambiguity_float": [],
            "proxy_ambiguity_vector": [],
            "production_ambiguity_quadratic_term": None,
            "production_conditional_baseline_constraint_term": None,
            "production_total_constrained_objective": None,
            "production_whitened_code_residual_norm": None,
            "production_whitened_phase_residual_norm": None,
            "proxy_ambiguity_quadratic_term": None,
            "proxy_conditional_baseline_constraint_term": None,
            "proxy_total_constrained_objective": None,
            "proxy_whitened_code_residual_norm": None,
            "proxy_whitened_phase_residual_norm": None,
            "proxy_candidate_beats_production": False,
            "production_objective_identity_error": None,
            "proxy_objective_identity_error": None,
        }
        if result["integer_solution_returned"]:
            row["native_minus_proxy_yaw_error_deg"] = wrap_safe_residual_degrees(
                result["body_yaw_deg"], proxy["proxy_body_yaw_deg"]
            )
            row["native_proxy_vector_angle_deg"] = _vector_angle_degrees(
                result["baseline_ecef_m"], proxy["proxy_baseline_ecef_m"]
            )
        if model_payload is not None:
            observation = np.asarray(model_payload["observation"], dtype=float)
            ambiguity_design = np.asarray(model_payload["ambiguity_design"], dtype=float)
            baseline_design = np.asarray(model_payload["baseline_design"], dtype=float)
            covariance = np.asarray(model_payload["covariance"], dtype=float)
            dimension = ambiguity_design.shape[1]
            diagonal = np.diag(ambiguity_design[dimension:, :])
            proxy_ecef = np.asarray(proxy["proxy_baseline_ecef_m"], dtype=float)
            implied = (
                observation[dimension:] - baseline_design[dimension:, :] @ proxy_ecef
            ) / diagonal
            opposite = (
                observation[dimension:] + baseline_design[dimension:, :] @ proxy_ecef
            ) / diagonal
            proxy_integer = np.rint(implied).astype(np.int64)
            row["proxy_ambiguity_float"] = implied.tolist()
            row["proxy_ambiguity_vector"] = proxy_integer.tolist()
            floating = joint_gls(observation, ambiguity_design, baseline_design, covariance)
            proxy_evaluation = evaluate_production_objective(
                floating, proxy_integer, LENGTH_M, observation, ambiguity_design,
                baseline_design, covariance, code_observation_count=dimension,
            )
            row.update({
                "proxy_ambiguity_quadratic_term": proxy_evaluation.ambiguity_quadratic_term,
                "proxy_conditional_baseline_constraint_term": (
                    proxy_evaluation.conditional_baseline_constraint_term
                ),
                "proxy_total_constrained_objective": proxy_evaluation.total_constrained_objective,
                "proxy_whitened_code_residual_norm": proxy_evaluation.whitened_code_residual_norm,
                "proxy_whitened_phase_residual_norm": proxy_evaluation.whitened_phase_residual_norm,
                "proxy_objective_identity_error": proxy_evaluation.objective_identity_error,
            })
            proxy_evaluated_count += 1
            cross_covariance_nonzero_count += not proxy_evaluation.code_phase_cross_covariance_zero
            objective_identity_max = max(
                objective_identity_max, abs(proxy_evaluation.objective_identity_error)
            )
            if result["integer_solution_returned"]:
                production_integer = np.asarray(result["ambiguity_vector"], dtype=np.int64)
                production_evaluation = evaluate_production_objective(
                    floating, production_integer, LENGTH_M, observation, ambiguity_design,
                    baseline_design, covariance, code_observation_count=dimension,
                )
                row.update({
                    "production_ambiguity_quadratic_term": (
                        production_evaluation.ambiguity_quadratic_term
                    ),
                    "production_conditional_baseline_constraint_term": (
                        production_evaluation.conditional_baseline_constraint_term
                    ),
                    "production_total_constrained_objective": (
                        production_evaluation.total_constrained_objective
                    ),
                    "production_whitened_code_residual_norm": (
                        production_evaluation.whitened_code_residual_norm
                    ),
                    "production_whitened_phase_residual_norm": (
                        production_evaluation.whitened_phase_residual_norm
                    ),
                    "production_objective_identity_error": (
                        production_evaluation.objective_identity_error
                    ),
                })
                production_evaluated_count += 1
                cross_covariance_nonzero_count += (
                    not production_evaluation.code_phase_cross_covariance_zero
                )
                objective_identity_max = max(
                    objective_identity_max, abs(production_evaluation.objective_identity_error)
                )
                if (proxy_evaluation.total_constrained_objective
                        < production_evaluation.total_constrained_objective - 1e-8):
                    row["proxy_candidate_beats_production"] = True
                    production_worse_count += 1
            first = _measurement_map(receiver1)
            second = _measurement_map(receiver2)
            identities = list(model_payload["ambiguity_satellite_identities"])
            for identity, fixed_value, opposite_value in zip(identities, implied, opposite):
                measurement1 = first[identity]
                measurement2 = second[identity]
                event1 = event_map.get((index, 1, identity), {})
                event2 = event_map.get((index, 2, identity), {})
                neighborhood = 0
                for neighbor in (index - 1, index, index + 1):
                    for receiver in (1, 2):
                        neighborhood += bool(event_map.get(
                            (neighbor, receiver, identity), {}
                        ).get("tracking_lock_reset_detected"))
                fraction_rows.append({
                    "epoch_index": index,
                    "gps_week": receiver1.gps_week,
                    "gps_tow_seconds": receiver1.gps_tow_seconds,
                    "satellite_identity": identity,
                    "pivot_identity": model_payload["pivot_identity"],
                    "fractional_dd_fixed_sign_cycles": _fractional_cycle(fixed_value),
                    "fractional_dd_opposite_sign_cycles": _fractional_cycle(opposite_value),
                    "sub_half_cycle_receiver1": measurement1.half_cycle_subtracted,
                    "sub_half_cycle_receiver2": measurement2.half_cycle_subtracted,
                    "half_cycle_valid_receiver1": measurement1.half_cycle_valid,
                    "half_cycle_valid_receiver2": measurement2.half_cycle_valid,
                    "cp_stdev_receiver1": measurement1.cp_std_code,
                    "cp_stdev_receiver2": measurement2.cp_std_code,
                    "locktime_receiver1_ms": measurement1.locktime_ms,
                    "locktime_receiver2_ms": measurement2.locktime_ms,
                    "lock_reset_receiver1": bool(event1.get("tracking_lock_reset_detected")),
                    "lock_reset_receiver2": bool(event2.get("tracking_lock_reset_detected")),
                    "lock_reset_neighborhood_count": neighborhood,
                })
        proxy_rows.append(row)
    return proxy_rows, fraction_rows, {
        "proxy_candidate_evaluated_count": proxy_evaluated_count,
        "production_candidate_evaluated_count": production_evaluated_count,
        "production_worse_than_proxy_candidate_count": production_worse_count,
        "objective_identity_error_max_abs": objective_identity_max,
        "objective_identity_absolute_tolerance": 1.0e-4,
        "objective_identity_crosscheck_passed": objective_identity_max <= 1.0e-4,
        "code_phase_cross_covariance_nonzero_count": cross_covariance_nonzero_count,
        "code_phase_cross_covariance_crosscheck_passed": cross_covariance_nonzero_count == 0,
        "search_objective_crosscheck_passed": (
            production_evaluated_count > 0 and production_worse_count == 0
        ),
    }


def _circular_cycle_statistics(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    if not array.size:
        return {"count": 0, "circular_mean_cycles": None, "circular_std_cycles": None,
                "median_absolute_fractional_cycles": None, "p90_absolute_fractional_cycles": None}
    radians = 2.0 * math.pi * array
    sine = float(np.mean(np.sin(radians)))
    cosine = float(np.mean(np.cos(radians)))
    resultant = min(1.0, math.hypot(sine, cosine))
    return {
        "count": int(array.size),
        "circular_mean_cycles": math.atan2(sine, cosine) / (2.0 * math.pi),
        "circular_std_cycles": math.sqrt(max(0.0, -2.0 * math.log(max(resultant, 1e-15))))
        / (2.0 * math.pi),
        "median_absolute_fractional_cycles": float(np.median(np.abs(array))),
        "p90_absolute_fractional_cycles": float(np.percentile(np.abs(array), 90)),
    }


def _aggregate_half_cycle(fraction_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in fraction_rows:
        key = (
            row["satellite_identity"], row["sub_half_cycle_receiver1"],
            row["sub_half_cycle_receiver2"], row["half_cycle_valid_receiver1"],
            row["half_cycle_valid_receiver2"],
        )
        groups[key].append(row)
    output = []
    for key, rows in sorted(groups.items(), key=lambda item: item[0]):
        fixed = _circular_cycle_statistics([
            float(row["fractional_dd_fixed_sign_cycles"]) for row in rows
        ])
        opposite = _circular_cycle_statistics([
            float(row["fractional_dd_opposite_sign_cycles"]) for row in rows
        ])
        output.append({
            "satellite_identity": key[0],
            "sub_half_cycle_receiver1": key[1],
            "sub_half_cycle_receiver2": key[2],
            "half_cycle_valid_receiver1": key[3],
            "half_cycle_valid_receiver2": key[4],
            **{f"fixed_sign_{name}": value for name, value in fixed.items()},
            **{f"opposite_sign_{name}": value for name, value in opposite.items()},
            "lock_reset_neighborhood_count": sum(
                int(row["lock_reset_neighborhood_count"]) > 0 for row in rows
            ),
            "cp_stdev_receiver1_median": float(np.median([
                int(row["cp_stdev_receiver1"]) for row in rows
            ])),
            "cp_stdev_receiver2_median": float(np.median([
                int(row["cp_stdev_receiver2"]) for row in rows
            ])),
        })
    return output


def _percentiles(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray([float(value) for value in values if math.isfinite(float(value))])
    if not array.size:
        return {"count": 0, "min": None, "p05": None, "median": None, "mean": None,
                "std": None, "p95": None, "p99": None, "max": None}
    return {
        "count": int(array.size),
        "min": float(np.min(array)),
        "p05": float(np.percentile(array, 5)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(np.max(array)),
    }


def _error_statistics(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray([float(value) for value in values if math.isfinite(float(value))])
    if not array.size:
        return {"count": 0, "bias": None, "rmse": None, "mae": None,
                "p95_abs": None, "p99_abs": None, "max_abs": None}
    absolute = np.abs(array)
    return {
        "count": int(array.size),
        "bias": float(np.mean(array)),
        "rmse": float(np.sqrt(np.mean(array * array))),
        "mae": float(np.mean(absolute)),
        "p95_abs": float(np.percentile(absolute, 95)),
        "p99_abs": float(np.percentile(absolute, 99)),
        "max_abs": float(np.max(absolute)),
    }


def _trace_metrics_after_freeze(
    paths: Phase1RPaths,
    pairs: Sequence[tuple[Any, Any]],
    proxy_rows: list[dict[str, Any]],
    *,
    fingerprint: str | None = None,
    raw_hashes: Mapping[str, str] | None = None,
    original_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    _validate_native_freeze(
        paths, fingerprint=fingerprint, raw_hashes=raw_hashes,
        original_hashes=original_hashes,
    )
    trace = paths.base.by2_fix_root / "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"
    if not trace.is_file():
        return {"trace_open_count": 0, "status": "TRACE_NOT_AVAILABLE_POST_NATIVE"}
    lock = read_hash_lock(paths.base.raw_hash_lock)
    relative = str(trace.relative_to(paths.base.raw_root)).replace("\\", "/")
    locked = lock.get(relative)
    if locked is None or sha256_file(trace) != locked.get("sha256"):
        raise Phase1RRunnerError("post-native trace is not bound by the raw hash lock")
    with trace.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"time", "yaw"}.issubset(reader.fieldnames):
            raise Phase1RRunnerError("post-native trace schema lacks time/yaw")
        trace_rows = list(reader)
    times = np.asarray([float(row["time"]) for row in trace_rows], dtype=float)
    yaw_enu = np.asarray([float(row["yaw"]) for row in trace_rows], dtype=float)
    if (not times.size or np.any(~np.isfinite(times)) or np.any(~np.isfinite(yaw_enu))
            or np.any(np.diff(times) <= 0)):
        raise Phase1RRunnerError("post-native trace time/yaw is invalid")
    yaw_unwrapped = np.degrees(np.unwrap(np.radians(yaw_enu)))
    proxy_errors: list[float] = []
    native_errors: list[float] = []
    matched = 0
    for (receiver1, _receiver2), row in zip(pairs, proxy_rows):
        unix_seconds = (
            315_964_800.0 + receiver1.gps_week * 604_800.0
            + receiver1.gps_tow_seconds - receiver1.leap_seconds
        )
        if unix_seconds < times[0] or unix_seconds > times[-1]:
            row["trace_body_yaw_deg"] = None
            row["proxy_minus_trace_yaw_error_deg"] = None
            row["native_minus_trace_yaw_error_deg"] = None
            continue
        reference_enu = float(np.interp(unix_seconds, times, yaw_unwrapped))
        reference_body = (90.0 - reference_enu) % 360.0
        row["trace_body_yaw_deg"] = reference_body
        proxy_error = wrap_safe_residual_degrees(row["proxy_body_yaw_deg"], reference_body)
        row["proxy_minus_trace_yaw_error_deg"] = proxy_error
        proxy_errors.append(proxy_error)
        if row["native_body_yaw_deg"] is not None:
            native_error = wrap_safe_residual_degrees(row["native_body_yaw_deg"], reference_body)
            row["native_minus_trace_yaw_error_deg"] = native_error
            native_errors.append(native_error)
        else:
            row["native_minus_trace_yaw_error_deg"] = None
        matched += 1
    return {
        "status": "POST_NATIVE_DESCRIPTIVE_ONLY",
        "trace_open_count": 2,
        "trace_path": str(trace),
        "trace_sha256": locked["sha256"],
        "trace_row_count": len(trace_rows),
        "matched_proxy_epoch_count": matched,
        "proxy_vs_trace_yaw": _error_statistics(proxy_errors),
        "native_vs_trace_yaw": _error_statistics(native_errors),
        "conversion": "wrap360(90_deg-trace_ENU_yaw)",
        "time_conversion": "GPS_EPOCH+week*604800+tow-leap_seconds",
        "time_offset_search": False,
        "sign_or_frame_search": False,
    }


RTKLIB_DIAGNOSTIC_CONFIG = """\
pos1-posmode       =movingbase
pos1-frequency     =l1
pos1-soltype       =forward
pos1-elmask        =10
pos1-snrmask       =0
pos1-dynamics      =off
pos1-tidecorr      =off
pos1-ionoopt       =brdc
pos1-tropopt       =saas
pos1-sateph        =brdc
pos1-exclsats      =
pos1-navsys        =1
pos2-armode        =instantaneous
pos2-gloarmode     =off
pos2-arthres       =3
pos2-arlockcnt     =0
pos2-arelmask      =0
pos2-aroutcnt      =5
pos2-arminfix      =1
pos2-slipthres     =0.05
pos2-maxage        =1
pos2-rejionno      =30
pos2-niter         =1
pos2-baselen       =0
pos2-basesig       =0
out-solformat      =enu
out-outhead        =on
out-outopt         =on
out-timesys        =gpst
out-timeform       =tow
out-timendec       =3
out-fieldsep       =,
out-solstatic      =all
out-outstat        =off
stats-errratio     =100
stats-errphase     =0.003
stats-errphaseel   =0.003
stats-errphasebl   =0
stats-stdbias      =30
stats-stdiono      =0.03
stats-stdtrop      =0.3
stats-prnaccelh    =1
stats-prnaccelv    =0.1
stats-prnbias      =0.0001
stats-prniono      =0.001
stats-prntrop      =0.0001
stats-clkstab      =5e-12
ant1-postype       =single
ant1-anttype       =*
ant2-postype       =single
ant2-anttype       =*
misc-timeinterp    =on
misc-sbasatsel     =0
file-tracefile     =
"""


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _run_rtklib_diagnostic(
    paths: Phase1RPaths,
    observation_paths: Sequence[Path],
    navigation_paths: Sequence[Path],
    proxies: Sequence[Mapping[str, Any]],
    *,
    fingerprint: str | None = None,
    raw_hashes: Mapping[str, str] | None = None,
    original_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    _validate_native_freeze(
        paths, fingerprint=fingerprint, raw_hashes=raw_hashes,
        original_hashes=original_hashes,
    )
    config = paths.target_root / "RTKLIB_DIAGNOSTIC_GPS_L1.conf"
    output = paths.target_root / "RTKLIB_DIAGNOSTIC_GPS_L1.pos"
    _write_text_atomic(config, RTKLIB_DIAGNOSTIC_CONFIG)
    temporary = output.with_suffix(".pos.tmp")
    command = [
        str(paths.rnx2rtkp), "-k", str(config), "-o", str(temporary),
        str(observation_paths[1]), str(observation_paths[0]),
        str(navigation_paths[0]), str(navigation_paths[1]),
    ]
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=900
    )
    if completed.returncode != 0 or not temporary.is_file():
        raise Phase1RRunnerError(f"RTKLIB diagnostic failed: {completed.stderr.strip()}")
    os.replace(temporary, output)
    rows = []
    for line in output.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("%"):
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) < 7:
            continue
        rows.append({
            "gps_week": int(fields[0]), "gps_tow_seconds": float(fields[1]),
            "east_m": float(fields[2]), "north_m": float(fields[3]),
            "up_m": float(fields[4]), "quality": int(fields[5]),
            "satellite_count": int(fields[6]),
        })
    proxy_by_tow = {round(float(row["gps_tow_seconds"]), 1): row for row in proxies}
    by_quality: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: {"length": [], "angle": []}
    )
    matched = 0
    for row in rows:
        proxy = proxy_by_tow.get(round(row["gps_tow_seconds"], 1))
        if proxy is None:
            continue
        rtklib_ned = np.asarray([row["north_m"], row["east_m"], -row["up_m"]])
        proxy_ned = np.asarray(proxy["proxy_baseline_ned_m"], dtype=float)
        by_quality[row["quality"]]["length"].append(float(np.linalg.norm(rtklib_ned)))
        angle = _vector_angle_degrees(rtklib_ned, proxy_ned)
        if angle is not None:
            by_quality[row["quality"]]["angle"].append(angle)
        matched += 1
    summary = {
        "role": "INDEPENDENT_RAW_DATA_SANITY_CHECK_NOT_EXT01",
        "configuration": RTKLIB_DIAGNOSTIC_CONFIG.splitlines(),
        "command": command,
        "receiver_order": "first_obs_GNSS2_second_obs_GNSS1",
        "baseline_constraint_used": False,
        "output_row_count": len(rows),
        "coverage_of_1509": len(rows) / EXPECTED_PAIR_COUNT,
        "quality_counts": dict(sorted(Counter(row["quality"] for row in rows).items())),
        "matched_proxy_count": matched,
        "quality_statistics": {
            str(quality): {
                "baseline_length_m": _percentiles(values["length"]),
                "vector_angle_to_hpposecef_deg": _percentiles(values["angle"]),
            }
            for quality, values in sorted(by_quality.items())
        },
        "config_sha256": sha256_file(config),
        "output_sha256": sha256_file(output),
        "used_as_ext01_output": False,
        "used_as_solver_input": False,
    }
    write_json_atomic(paths.target_root / "RTKLIB_DIAGNOSTIC_GPS_L1_SUMMARY.json", summary)
    return summary


PROXY_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "hpposecef_offset_receiver1_ms",
    "hpposecef_offset_receiver2_ms", "proxy_baseline_ecef_m", "proxy_baseline_ned_m",
    "proxy_length_m", "proxy_body_yaw_deg", "native_integer_solution_returned",
    "native_body_yaw_deg", "native_minus_proxy_yaw_error_deg",
    "native_proxy_vector_angle_deg", "production_ambiguity_vector",
    "proxy_ambiguity_float", "proxy_ambiguity_vector",
    "production_ambiguity_quadratic_term", "production_conditional_baseline_constraint_term",
    "production_total_constrained_objective", "production_whitened_code_residual_norm",
    "production_whitened_phase_residual_norm", "proxy_ambiguity_quadratic_term",
    "proxy_conditional_baseline_constraint_term", "proxy_total_constrained_objective",
    "proxy_whitened_code_residual_norm", "proxy_whitened_phase_residual_norm",
    "proxy_candidate_beats_production", "production_objective_identity_error",
    "proxy_objective_identity_error", "trace_body_yaw_deg",
    "proxy_minus_trace_yaw_error_deg", "native_minus_trace_yaw_error_deg",
)


def _code_freeze(paths: Phase1RPaths) -> dict[str, Any]:
    root = paths.base.code_root
    commit = _git_lines(root, "rev-parse", "HEAD")[0]
    tracked_diff = subprocess.run(
        ["git", "diff", "--quiet", "--"], cwd=root, check=False
    ).returncode
    staged_diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--"], cwd=root, check=False
    ).returncode
    tracked_status = _git_lines(root, "status", "--short", "--untracked-files=no")
    if tracked_diff != 0 or staged_diff != 0 or tracked_status:
        raise Phase1RRunnerError("Phase-1R code scope is not frozen; refusing real C00")
    sources = (
        root / "src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py",
        root / "src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
        root / "src/legsa_gins/paper_rebuild/horizontal_literature/phase1r_runner.py",
        root / "scripts/paper_rebuild/run_horizontal_literature_phase1r.py",
        paths.contract,
    )
    source_hashes = {str(path.relative_to(root)): sha256_file(path) for path in sources}
    for relative, digest in source_hashes.items():
        blob = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=root, capture_output=True, check=False
        )
        if blob.returncode != 0 or hashlib.sha256(blob.stdout).hexdigest() != digest:
            raise Phase1RRunnerError(f"HEAD does not identify executed source: {relative}")
    return {
        "code_commit": commit,
        "source_hashes": source_hashes,
        "tracked_and_staged_diff_clean": True,
        "untracked_files_are_not_a_runtime_dependency": True,
        "canonical541_files_opened_by_runner": False,
        "canonical541_files_modified_by_runner": False,
    }


def _common_count_summary(dd_rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    values = [int(row[field]) for row in dd_rows]
    return {
        "min": min(values), "mean": sum(values) / len(values), "max": max(values),
        "total": sum(values), "zero_epoch_count": sum(value == 0 for value in values),
    }


def _continuity(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    times = [
        float(row["gps_week"]) * 604800.0 + float(row["gps_tow_seconds"])
        for row in results if row["integer_solution_returned"]
    ]
    gaps = np.diff(np.asarray(times, dtype=float)) if len(times) > 1 else np.asarray([])
    return {
        "integer_solution_epoch_count": len(times),
        "maximum_gap_seconds": float(np.max(gaps)) if gaps.size else None,
        "gap_statistics_seconds": _percentiles(gaps),
    }


def _persistent_fractional_groups(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Flag strong offsets using a pre-trace physical cycle-domain rule.

    The threshold is a diagnostic detection rule, not a calibration: at least
    30 samples, circular scatter <=0.10 cycle, and a mean offset >=0.20 cycle.
    No offset is estimated or applied to the observations or solver output.
    """
    findings = []
    for row in rows:
        count = int(row["fixed_sign_count"])
        mean = row["fixed_sign_circular_mean_cycles"]
        scatter = row["fixed_sign_circular_std_cycles"]
        if (count >= 30 and mean is not None and scatter is not None
                and abs(float(mean)) >= 0.20 and float(scatter) <= 0.10):
            findings.append(dict(row))
    return findings


def _terminal_from_evidence(
    determinism: Mapping[str, Any], objective: Mapping[str, Any],
    half_cycle_rows: Sequence[Mapping[str, Any]], rtklib: Mapping[str, Any],
    validation_counts: Mapping[str, int],
) -> tuple[str, list[dict[str, Any]]]:
    required_counts = {
        "native_rows": EXPECTED_PAIR_COUNT,
        "dd_rows": EXPECTED_PAIR_COUNT,
        "search_rows": EXPECTED_PAIR_COUNT,
        "proxy_rows": EXPECTED_PAIR_COUNT,
    }
    if any(validation_counts.get(name) != expected
           for name, expected in required_counts.items()):
        return "BLOCKED_PHASE1R_ROW_CONSERVATION_FAILED", []
    if (validation_counts.get("integer_solution_rows", 0) <= 0
            or validation_counts.get("fractional_dd_rows", 0) <= 0
            or validation_counts.get("rtklib_diagnostic_rows", 0) <= 0):
        return "BLOCKED_PHASE1R_VALIDITY_EVIDENCE_EMPTY", []
    diagnostic_rows = validation_counts.get("rtklib_diagnostic_rows", 0)
    matched_rows = validation_counts.get("rtklib_matched_proxy_rows", 0)
    if matched_rows <= 0 or matched_rows != diagnostic_rows:
        return "BLOCKED_PHASE1R_RTKLIB_DIAGNOSTIC_JOIN_FAILED", []
    if determinism.get("row_level_scientific_equality") is not True:
        return "BLOCKED_PHASE1R_WORKER_NONDETERMINISM", []
    if (objective.get("search_objective_crosscheck_passed") is not True
            or objective.get("objective_identity_crosscheck_passed") is not True
            or objective.get("code_phase_cross_covariance_crosscheck_passed") is not True):
        return "BLOCKED_PHASE1R_SEARCH_OBJECTIVE_CROSSCHECK_FAILED", []
    persistent = _persistent_fractional_groups(half_cycle_rows)
    q1 = rtklib.get("quality_statistics", {}).get("1", {})
    q2 = rtklib.get("quality_statistics", {}).get("2", {})
    diagnostic_incoherent = False
    for quality in (q1, q2):
        length = quality.get("baseline_length_m", {}).get("median")
        angle = quality.get("vector_angle_to_hpposecef_deg", {}).get("median")
        if length is not None and angle is not None and length > 1.0 and angle > 45.0:
            diagnostic_incoherent = True
    if persistent and diagnostic_incoherent:
        return UNSUPPORTED, persistent
    return PASS_VALIDATED, persistent


def _write_report(paths: Phase1RPaths, status: str, summary: Mapping[str, Any]) -> None:
    counts = summary["native_counts"]
    failure_text = ", ".join(
        f"{name}={count}" for name, count in summary["failure_classes"].items()
    ) or "none"
    text = f"""# Phase 1R EXT01 C00 validity report

Terminal status: `{status}`

The previous Phase-1 engineering output under `02_EXT01_CLAMBDA/C00/` was
hash-checked before and after this run and was not overwritten.  This validated
run consumed true hash-locked RXM-RAWX bytes and RTKLIB broadcast satellite
states.  Trace was first opened only after the six native outputs were frozen
and revalidated, solely for descriptive same-source metrics.

## Root cause and repairs

The 432 false zeros were a reporting-order defect: the old runner initialized
the common-raw count to zero and computed it only after SPP and DD construction.
Phase-1R computes provider-independent raw/validity stages first and preserves
them on every later failure.  Tracking events are now separated from the
method's intentional per-epoch ambiguity reinitialization.  `cpMes` is used as
reported; `subHalfCyc` means that the receiver already applied the half-cycle
subtraction, so no second +/-0.5-cycle shift is made.

## Native result

- paired/native rows: {counts['paired_epochs']}/{counts['native_rows']}
- integer solutions returned and globally certified: {counts['integer_solution_returned']}
- no native integer result: {counts['invalid']}
- ambiguity acceptance test defined: false
- failures: {failure_text}
- availability: {counts['integer_solution_availability']:.9f}

The fixed 0.350 m constraint makes successful baseline lengths exactly 0.350 m;
that fact is not used as a stochastic-model validation.

## Scientific audit boundary

The strict search uses RTKLIB decorrelation/seeds only as incumbents, then a
mathematically complete best-first C-LAMBDA branch-and-bound.  A row is called
globally certified only when the remaining frontier lower bound cannot beat the
second-best full constrained objective.  No candidate cap is applied.  No
accepted-fix rate is reported because BY2 supplies no independent true integer
ambiguity vector and no untuned ambiguity acceptance test was defined.

NAV-HPPOSECEF and RTKLIB relative positioning are diagnostic-only.  Neither was
used by the solver, sign selection, time selection, parameter selection, or
output correction.  The post-native trace comparison is same-source and is not
independent truth.

## Reproduction

```bash
cd {paths.base.code_root}
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python3 scripts/paper_rebuild/run_horizontal_literature_phase1r.py \\
  --paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml \\
  --method-id EXT01_CLAMBDA --case-id C00_VALIDATED \\
  --trace-mode post-native-descriptive --workers 16 --resume
```
"""
    _write_text_atomic(paths.report, text)


def _finalize(
    paths: Phase1RPaths,
    config_path: Path,
    raw_hashes: Mapping[str, str],
    original_hashes: Mapping[str, str],
    external: Mapping[str, Any],
    code: Mapping[str, Any],
    cache_audit: Mapping[str, Any],
    reconstructions: tuple[Any, Any],
    pairs: Sequence[tuple[Any, Any]],
    parts: Sequence[dict[str, Any]],
    tracking: Sequence[dict[str, Any]],
    event_map: Mapping[tuple[int, int, str], Mapping[str, Any]],
    observation_paths: Sequence[Path],
    navigation_paths: Sequence[Path],
    native_freeze: Mapping[str, Any],
) -> dict[str, Any]:
    proxies = _proxy_baselines(reconstructions[0], reconstructions[1], pairs)
    proxy_rows, fractional_rows, objective = _proxy_objective_diagnostics(
        pairs, parts, proxies, event_map
    )
    half_cycle_rows = _aggregate_half_cycle(fractional_rows)
    trace = _trace_metrics_after_freeze(
        paths, pairs, proxy_rows,
        fingerprint=str(native_freeze["run_fingerprint"]),
        raw_hashes=raw_hashes, original_hashes=original_hashes,
    )
    rtklib = _run_rtklib_diagnostic(
        paths, observation_paths, navigation_paths, proxies,
        fingerprint=str(native_freeze["run_fingerprint"]),
        raw_hashes=raw_hashes, original_hashes=original_hashes,
    )
    _write_csv_atomic(paths.output_files["proxy"], proxy_rows, PROXY_FIELDS)
    half_fields = sorted({key for row in half_cycle_rows for key in row})
    _write_csv_atomic(paths.output_files["half_cycle"], half_cycle_rows, half_fields)
    fractional_fields = sorted({key for row in fractional_rows for key in row})
    _write_csv_atomic(
        paths.target_root / "EXT01_C00_VALIDATED_FRACTIONAL_DD_ROWS.csv",
        fractional_rows,
        fractional_fields,
    )
    results = [part["result"] for part in parts]
    dd_rows = [part["dd"] for part in parts]
    runtimes = [part["runtime"] for part in parts]
    search_rows = [part["search"] for part in parts]
    integer_count = sum(bool(row["integer_solution_returned"]) for row in results)
    failure_classes = dict(sorted(Counter(
        str(row["failure_code"]) for row in results if not row["integer_solution_returned"]
    ).items()))
    native_proxy_errors = [
        row["native_minus_proxy_yaw_error_deg"] for row in proxy_rows
        if row["native_minus_proxy_yaw_error_deg"] is not None
    ]
    vector_angles = [
        row["native_proxy_vector_angle_deg"] for row in proxy_rows
        if row["native_proxy_vector_angle_deg"] is not None
    ]
    validation_counts = {
        "native_rows": len(results),
        "dd_rows": len(dd_rows),
        "search_rows": len(search_rows),
        "proxy_rows": len(proxy_rows),
        "integer_solution_rows": integer_count,
        "fractional_dd_rows": len(fractional_rows),
        "rtklib_diagnostic_rows": int(rtklib.get("output_row_count", 0)),
        "rtklib_matched_proxy_rows": int(rtklib.get("matched_proxy_count", 0)),
    }
    status, persistent = _terminal_from_evidence(
        native_freeze["worker_determinism"], objective, half_cycle_rows, rtklib,
        validation_counts,
    )
    summary: dict[str, Any] = {
        "schema_version": "horizontal_literature.phase1r_summary.v1",
        "terminal_status": status,
        "method_id": "EXT01_CLAMBDA",
        "case_id": "C00_VALIDATED",
        "data_mode": "real_by2_raw",
        "native_counts": {
            "paired_epochs": len(pairs),
            "native_rows": len(results),
            "integer_solution_returned": integer_count,
            "invalid": len(results) - integer_count,
            "integer_solution_availability": integer_count / len(results),
            "search_complete_rate": sum(
                bool(row["global_optimum_certified"]) for row in search_rows
            ) / len(search_rows),
            "ambiguity_acceptance_test_defined": False,
            "ambiguity_accepted_count": None,
        },
        "failure_classes": failure_classes,
        "validation_row_counts": validation_counts,
        "raw_accounting": {
            field: _common_count_summary(dd_rows, field)
            for field in (
                "common_raw_satellite_count", "common_pr_valid_satellite_count",
                "common_cp_valid_satellite_count", "common_pr_cp_valid_satellite_count",
                "common_half_cycle_valid_satellite_count",
                "common_integer_compatible_satellite_count",
                "common_rtklib_phase_compatible_satellite_count",
                "satellite_state_available_count", "elevation_eligible_satellite_count",
                "dd_eligible_satellite_count",
            )
        },
        "tracking": {
            "ambiguity_reinitialized_by_method_epochs": len(pairs),
            "actual_lock_reset_count": sum(int(row["actual_lock_reset_count"]) for row in tracking),
            "actual_cycle_slip_count": sum(int(row["actual_cycle_slip_count"]) for row in tracking),
            "half_cycle_state_change_count": sum(
                int(row["half_cycle_state_change_count"]) for row in tracking
            ),
            "sub_half_cycle_set_measurement_count_receiver1": sum(
                int(row["sub_half_cycle_set_count_receiver1"]) for row in tracking
            ),
            "sub_half_cycle_set_measurement_count_receiver2": sum(
                int(row["sub_half_cycle_set_count_receiver2"]) for row in tracking
            ),
        },
        "half_cycle_contract": asdict(HALF_CYCLE_CONTRACT),
        "stochastic_model": {
            "pseudorange_sigma_m": "max(0.50,0.01*2^prStdev)",
            "carrier_sigma_cycles": "max(0.004,0.004*cpStdev)",
            "doppler_sigma_hz": "max(0.02,0.002*2^doStdev)",
            "rawx_indicator_units_checked": True,
            "code_phase_cross_covariance_assumption": "ZERO",
            "code_phase_cross_covariance_zero_for_all_integer_rows": all(
                row.get("code_phase_cross_covariance_zero") is True
                for row in results if row["integer_solution_returned"]
            ),
            "shared_pivot_dd_correlations_preserved": True,
            "raw_and_whitened_condition_numbers_in_dd_diagnostics": True,
            "trace_tuned": False,
            "baseline_constraint_used_as_validation": False,
        },
        "fractional_dd": {
            "individual_row_count": len(fractional_rows),
            "group_count": len(half_cycle_rows),
            "persistent_offset_detection_rule": (
                "count>=30 and abs(circular_mean)>=0.20 cycles and circular_std<=0.10 cycles"
            ),
            "persistent_offset_group_count": len(persistent),
            "persistent_offset_groups": persistent,
            "calibration_applied": False,
        },
        "proxy": {
            "length_m": _percentiles(row["proxy_length_m"] for row in proxy_rows),
            "native_minus_proxy_yaw_deg": _error_statistics(native_proxy_errors),
            "native_proxy_vector_angle_deg": _percentiles(vector_angles),
            "role": "DIAGNOSTIC_ONLY_NOT_SOLVER_INPUT",
        },
        "baseline_length_m": _percentiles(
            row["baseline_length_m"] for row in results
            if row["baseline_length_m"] is not None
        ),
        "runtime_seconds": _percentiles(row["runtime_seconds"] for row in runtimes),
        "continuity": _continuity(results),
        "search": {
            "lambda_seed_count_requested": LAMBDA_SEEDS,
            "seed_count_is_candidate_cap": False,
            "candidate_cap_applied_count": sum(
                bool(row["candidate_cap_applied"]) for row in search_rows
            ),
            "global_optimum_certified_count": sum(
                bool(row["global_optimum_certified"]) for row in search_rows
            ),
            "termination_reasons": dict(sorted(Counter(
                str(row["termination_reason"]) for row in search_rows
            ).items())),
            "branch_and_bound_nodes": _percentiles(
                row["branch_and_bound_nodes_expanded"] for row in search_rows
            ),
            "integer_leaves": _percentiles(
                row["integer_leaves_evaluated"] for row in search_rows
            ),
        },
        "objective_crosscheck": objective,
        "trace": trace,
        "rtklib_diagnostic": rtklib,
        "worker_determinism": native_freeze["worker_determinism"],
        "parallel_run": native_freeze["worker_audit"],
        "resource_probe": native_freeze["resource_probe"],
        "raw_source_hashes": dict(raw_hashes),
        "raw_hash_lock_sha256": sha256_file(paths.base.raw_hash_lock),
        "provider": dict(external),
        "cache_audit": dict(cache_audit),
        "code": dict(code),
        "config_hash": sha256_file(config_path),
        "phase1r_contract_sha256": sha256_file(paths.contract),
        "original_c00_tree_digest_before": _tree_digest(original_hashes),
        "native_freeze_sha256": sha256_file(paths.native_freeze),
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "status_baseline_solver_input": False,
        "hpposecef_solver_input": False,
        "rtklib_position_solver_input": False,
        "canonical541_accessed": False,
        "ext02_ext03_ext04_run": False,
        "classic18_run": False,
        "common_backbone_navigation_run": False,
    }
    write_json_atomic(paths.output_files["summary"], _jsonable(summary))
    _write_report(paths, status, summary)
    current_original = _hash_tree(paths.base.stage_root / "02_EXT01_CLAMBDA/C00")
    if current_original != dict(original_hashes):
        raise Phase1RRunnerError("immutable original Phase-1 EXT01/C00 changed during Phase-1R")
    target_hashes = _hash_tree(paths.target_root)
    artifacts = {
        str((paths.target_root / relative).relative_to(paths.base.stage_root)): digest
        for relative, digest in target_hashes.items()
        if Path(relative).name != "PHASE1R_RUN.lock"
    }
    artifacts[str(paths.report.relative_to(paths.base.stage_root))] = sha256_file(paths.report)
    terminal = {
        **summary,
        "output_hashes": artifacts,
        "original_c00_tree_digest_after": _tree_digest(current_original),
        "original_c00_immutable": True,
        "validated_output_root": str(paths.target_root),
        "report_path": str(paths.report),
    }
    write_json_atomic(paths.status, _jsonable(terminal))
    return terminal


def run_phase1r(
    config_path: Path,
    *,
    method_id: str = "EXT01_CLAMBDA",
    case_id: str = "C00_VALIDATED",
    trace_mode: str = "post-native-descriptive",
    workers: int = DEFAULT_WORKERS,
    resume: bool = False,
) -> dict[str, Any]:
    if method_id != "EXT01_CLAMBDA" or case_id != "C00_VALIDATED":
        raise Phase1RRunnerError("Phase-1R method/case must be EXT01_CLAMBDA/C00_VALIDATED")
    if trace_mode != "post-native-descriptive":
        raise Phase1RRunnerError("trace mode must be literal post-native-descriptive")
    if not 1 <= workers <= MAX_WORKERS:
        raise Phase1RRunnerError(f"workers must be in 1..{MAX_WORKERS}")
    config_path = Path(config_path).resolve(strict=True)
    paths = load_phase1r_paths(config_path)
    raw_hashes, original_hashes = _validate_start(paths, resume)
    code = _code_freeze(paths)
    external = _external_audit(paths)
    base_fingerprint = _run_fingerprint(paths, raw_hashes, external)
    paths.target_root.mkdir(parents=True, exist_ok=True)
    _assert_contained(paths.target_root, paths.base.stage_root)
    run_lock, run_token = _acquire_run_lock(paths.target_root)
    try:
        resource = _resource_probe(paths)
        reconstruction1, reconstruction2, navigation_paths, observation_paths, cache_audit = (
            _prepare_inputs(paths, base_fingerprint)
        )
        fingerprint = _epoch_fingerprint(base_fingerprint, cache_audit)
        pairs, pairing_failures = pair_epochs(
            reconstruction1.rawx_epochs, reconstruction2.rawx_epochs
        )
        if pairing_failures or len(pairs) != EXPECTED_PAIR_COUNT:
            raise Phase1RRunnerError(
                f"exact pairing differs from frozen 1509: pairs={len(pairs)} failures={len(pairing_failures)}"
            )
        independent_counts = [gps_l1_epoch_accounting(*pair).as_counts() for pair in pairs]
        raw_values = [row["common_raw_satellite_count"] for row in independent_counts]
        pr_cp_values = [row["common_pr_cp_valid_satellite_count"] for row in independent_counts]
        half_values = [row["common_half_cycle_valid_satellite_count"] for row in independent_counts]
        if (min(raw_values), sum(raw_values), max(raw_values), sum(value == 0 for value in raw_values)) != (
            5, 12013, 10, 0
        ):
            raise Phase1RRunnerError("independent common-raw count contract mismatch")
        if (min(pr_cp_values), sum(pr_cp_values), max(pr_cp_values)) != (3, 9686, 9):
            raise Phase1RRunnerError("independent PR+CP count contract mismatch")
        if (min(half_values), sum(half_values), max(half_values)) != (2, 6577, 9):
            raise Phase1RRunnerError("independent half-cycle count contract mismatch")
        positions, spp_failures = _precompute_spp(
            pairs, paths.base.rtklib_bridge, navigation_paths
        )
        determinism = _worker_determinism_audit(
            paths, fingerprint, pairs, positions, spp_failures, navigation_paths
        )
        if not determinism["row_level_scientific_equality"]:
            raise Phase1RRunnerError("workers 1 and 16 differ on the deterministic audit subset")
        parts, worker_audit = _run_epoch_parts(
            paths, fingerprint, pairs, positions, spp_failures, navigation_paths, workers
        )
        if len(parts) != EXPECTED_PAIR_COUNT:
            raise Phase1RRunnerError("epoch-part conservation failed")
        tracking, event_map = _tracking_rows(pairs, parts)
        if len(tracking) != EXPECTED_PAIR_COUNT:
            raise Phase1RRunnerError("tracking row conservation failed")
        if paths.native_freeze.is_file():
            native_freeze = _validate_native_freeze(
                paths, fingerprint=fingerprint, raw_hashes=raw_hashes,
                original_hashes=original_hashes,
            )
        else:
            _write_native_outputs(
                paths, parts, tracking, fingerprint, raw_hashes, original_hashes,
                worker_audit, determinism, resource,
            )
            native_freeze = _validate_native_freeze(
                paths, fingerprint=fingerprint, raw_hashes=raw_hashes,
                original_hashes=original_hashes,
            )
        return _finalize(
            paths, config_path, raw_hashes, original_hashes, external, code, cache_audit,
            (reconstruction1, reconstruction2), pairs, parts, tracking, event_map,
            observation_paths, navigation_paths, native_freeze,
        )
    except Exception as exc:
        terminal = {
            "schema_version": "horizontal_literature.phase1r_status.v1",
            "terminal_status": "BLOCKED_PHASE1R_RUNTIME_FAILURE",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "partial_validated_root_preserved": True,
            "resume_command_required": True,
            "trace_used_online": False,
            "canonical541_accessed": False,
            "ext02_ext03_ext04_run": False,
            "classic18_run": False,
            "code": code,
            "raw_source_hashes": dict(raw_hashes),
            "original_c00_tree_digest_before": _tree_digest(original_hashes),
        }
        write_json_atomic(paths.status, _jsonable(terminal))
        return terminal
    finally:
        _release_run_lock(run_lock, run_token)


def terminal_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
