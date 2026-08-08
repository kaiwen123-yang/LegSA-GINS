#!/usr/bin/env python3
"""Run the frozen repaired Canonical-541 pipeline under an external tmux/nohup session."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from build_canonical541_manifest import load_local
from legsa_gins.paper_rebuild.canonical541.authorization import STAGE_ID, load_execution_authorization, validate_attempt_root
from legsa_gins.paper_rebuild.manifest import sha256_file


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def _readiness_gate(stage: Path, code_freeze: str, executable: str | Path) -> dict:
    path = stage / "16_AUDITS/COMPACT_READINESS_GATE.json"
    gate = json.loads(path.read_text(encoding="utf-8"))
    if (
        gate.get("passed") is not True
        or gate.get("stage_id") != STAGE_ID
        or gate.get("code_freeze_commit") != code_freeze
        or gate.get("attempt_root") != str(stage)
        or gate.get("executable_sha256") != sha256_file(Path(executable).resolve(strict=True))
        or gate.get("ab0000_parity_passed") is not True
        or gate.get("clean_18_terminal") != 18
        or gate.get("registry_preflight_unique_identities") != 5951
        or gate.get("trace_reads_before_seal") != 0
    ):
        raise SystemExit("compact repaired readiness gate is incomplete")
    artifact_paths = gate.get("artifact_paths")
    artifact_hashes = gate.get("artifact_hashes")
    if not isinstance(artifact_paths, dict) or not isinstance(artifact_hashes, dict):
        raise SystemExit("compact readiness artifact bindings are missing")
    if set(artifact_paths) != set(artifact_hashes) or any(
        sha256_file(Path(str(path)).resolve(strict=True)) != artifact_hashes[name]
        for name, path in artifact_paths.items()
    ):
        raise SystemExit("compact readiness artifact hash drift")
    roots = gate.get("authoritative_roots")
    clean_rows = gate.get("clean18_rows")
    if not isinstance(roots, dict) or not isinstance(clean_rows, list):
        raise SystemExit("compact readiness authoritative root bindings are missing")
    if Path(str(roots.get("attempt", ""))).resolve(strict=True) != stage:
        raise SystemExit("compact readiness attempt binding drift")
    clean_root = Path(str(roots["clean18_output"])).resolve(strict=True)
    for index, row in enumerate(clean_rows, 1):
        profile = str(row.get("effective_profile", ""))
        hashes = row.get("run_root_sha256s")
        run_root = clean_root / f"{index:02d}_{profile}"
        if not isinstance(hashes, dict) or any(
            sha256_file((run_root / name).resolve(strict=True)) != digest
            for name, digest in hashes.items()
        ):
            raise SystemExit("compact readiness clean-18 output hash drift")
    seal_root = Path(str(roots["clean18_seal"])).resolve(strict=True)
    if any(sha256_file((seal_root / name).resolve(strict=True)) != digest
           for name, digest in gate.get("clean18_seal_hashes", {}).items()):
        raise SystemExit("compact readiness clean-18 seal hash drift")
    parity = gate.get("ab0000_numerical_parity", {})
    for name, hashes in parity.items():
        if (sha256_file(Path(str(roots["ab0000_output"])).resolve(strict=True) / name) != hashes.get("current")
                or sha256_file(Path(str(roots["ab0000_anchor"])).resolve(strict=True) / name) != hashes.get("anchor")):
            raise SystemExit("compact readiness AB0000 parity artifact drift")
    return gate


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _acquire_runner_lock(stage: Path, code_freeze: str, *, resume: bool) -> Path:
    stage = validate_attempt_root(stage)
    lock = stage / "runner.lock"
    if lock.exists():
        try:
            previous = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit("runner.lock is unreadable; refusing unsafe takeover") from exc
        if _pid_alive(int(previous.get("pid", -1))):
            raise SystemExit("runner.lock belongs to a live process; refusing duplicate launch")
        if not resume:
            raise SystemExit("dead runner.lock requires explicit --resume")
        if previous.get("stage_id") != STAGE_ID or previous.get("stage_root") != str(stage):
            raise SystemExit("dead runner.lock stage identity mismatch")
        if previous.get("code_freeze_commit") != code_freeze:
            raise SystemExit("dead runner.lock solver freeze mismatch")
        lock.unlink()
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    payload = {
        "pid": os.getpid(), "started_at": _now(), "stage_id": STAGE_ID,
        "stage_root": str(stage), "code_freeze_commit": code_freeze,
    }
    os.write(descriptor, (json.dumps(payload, sort_keys=True) + "\n").encode())
    os.fsync(descriptor); os.close(descriptor)
    return lock


def _release_owned_lock(lock: Path) -> None:
    if not lock.exists():
        return
    payload = json.loads(lock.read_text(encoding="utf-8"))
    if payload.get("pid") == os.getpid():
        lock.unlink()


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--local-config", required=True)
    command.add_argument("--executable", required=True)
    command.add_argument("--code-freeze-commit", required=True)
    command.add_argument("--exact-evaluator", required=True)
    command.add_argument("--origin-stage", required=True)
    command.add_argument("--origin-provider-freeze", required=True)
    command.add_argument("--export-root", required=True)
    command.add_argument("--attempt-id", required=True)
    command.add_argument("--timestamp", required=True)
    command.add_argument("--hard-max-jobs", type=int, default=12)
    command.add_argument("--timeout-seconds", type=int, default=1800)
    command.add_argument("--resume", action="store_true")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    load_execution_authorization(REPO_ROOT)
    if not 1 <= args.hard_max_jobs <= 16:
        raise SystemExit("hard max jobs must be 1..16")
    local = Path(args.local_config).resolve(strict=True)
    paths = load_local(local)
    stage = validate_attempt_root(paths["runtime_root"])
    _readiness_gate(stage, args.code_freeze_commit, args.executable)
    lock = _acquire_runner_lock(stage, args.code_freeze_commit, resume=args.resume)
    session = stage / "RUN_SESSION.json"
    status = stage / "CANONICAL541_STATUS.json"
    env = os.environ.copy()
    env.update({name: "1" for name in (
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    )})
    common = ["--local-config", str(local), "--code-freeze-commit", args.code_freeze_commit]
    commands = [
        [sys.executable, str(REPO_ROOT / "scripts/paper_rebuild/reuse_canonical541_providers.py"),
         "--origin-stage", args.origin_stage, "--origin-freeze", args.origin_provider_freeze,
         "--destination-stage", str(stage), "--provider-root", str(paths["provider_root"]),
         "--new-solver-code-freeze", args.code_freeze_commit],
        [sys.executable, str(REPO_ROOT / "scripts/paper_rebuild/prepare_canonical541_execution.py"),
         *common, "--executable", args.executable, "--prepare-only", "--resume-preparation", "--stop-before-execution"],
        [sys.executable, str(REPO_ROOT / "scripts/paper_rebuild/run_canonical541_full_algorithm.py"),
         *common, "--executable", args.executable, "--hard-max-jobs", str(max(8, args.hard_max_jobs)),
         "--timeout-seconds", str(args.timeout_seconds), "--resume"],
        [sys.executable, str(REPO_ROOT / "scripts/paper_rebuild/run_canonical541_internal_ablation.py"),
         *common, "--executable", args.executable, "--jobs", str(args.hard_max_jobs),
         "--timeout-seconds", str(args.timeout_seconds), "--resume"],
        [sys.executable, str(REPO_ROOT / "scripts/paper_rebuild/evaluate_canonical541.py"),
         "--local-config", str(local), "--exact-evaluator", args.exact_evaluator,
         "--jobs", str(args.hard_max_jobs)],
        [sys.executable, str(REPO_ROOT / "scripts/paper_rebuild/audit_canonical541.py"), "all",
         "--stage-root", str(stage), "--export-root", str(Path(args.export_root).resolve()),
         "--timestamp", args.timestamp, "--attempt-id", args.attempt_id,
         "--local-config", str(local)],
    ]
    regeneration_command = [
        sys.executable, str(REPO_ROOT / "scripts/paper_rebuild/generate_canonical541_providers.py"),
        "--local-config", str(local), "--jobs", str(args.hard_max_jobs),
        "--code-freeze-commit", args.code_freeze_commit, "--executable", args.executable,
    ]
    _atomic_json(session, {"pid": os.getpid(), "stage_id": STAGE_ID, "attempt_root": str(stage), "started_at": _now(),
                           "code_freeze_commit": args.code_freeze_commit, "commands": commands})
    try:
        for index, command in enumerate(commands, start=1):
            _atomic_json(status, {"phase": f"PIPELINE_STEP_{index}_OF_{len(commands)}",
                                  "heartbeat_time": _now(), "running_jobs": args.hard_max_jobs,
                                  "trace_reads_before_seal": 0})
            process = subprocess.Popen(command, cwd=REPO_ROOT, env=env)
            while True:
                try:
                    return_code = process.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    _atomic_json(status, {"phase": f"PIPELINE_STEP_{index}_OF_{len(commands)}",
                                          "heartbeat_time": _now(), "running_jobs": args.hard_max_jobs,
                                          "trace_reads_before_seal": 0, "process_pid": process.pid})
            if index == 1 and return_code == 3:
                # Exit 3 is emitted only after provider bytes/effects or generator/config
                # semantics are proven mismatched. Regeneration is forbidden otherwise.
                subprocess.run(regeneration_command, cwd=REPO_ROOT, env=env, check=True)
                return_code = 0
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, command)
        _atomic_json(status, {"phase": "PIPELINE_COMPLETE", "heartbeat_time": _now(),
                              "running_jobs": 0, "trace_reads_before_seal": 0})
        _atomic_json(stage / "DRAFT_PR_HANDOFF.json", {
            "schema_version": "paper_rebuild.canonical541_draft_pr_handoff.v1",
            "stage_id": STAGE_ID, "code_freeze_commit": args.code_freeze_commit,
            "automatic_github_action_performed": False,
            "draft_pr_requested": True,
            "human_or_supervisor_action_required": True,
            "finalization_report": str(stage / "16_AUDITS/CANONICAL541_FINALIZATION_REPORT.json"),
        })
    finally:
        _release_owned_lock(lock)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
