"""C-04b read-only validation of the immutable C-04 v1 attempt.

No native run is launched. The corrected validator is exercised against the
sealed bytes, with its own strace session and output directory. Superseded
markers are authorized only after all ten revalidation results pass.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import yaml

from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .generation_audit import write_json_exclusive
from .profile_expectations import verify_canonical_patterns
from .registry import load_registry
from .runtime_config import METHODS, CONFIG_FILENAMES
from .solver_runner import (C02_COMMIT, audit_solver_openat, verify_executable,
                            verify_provider_files)
from .solver_seal import validate_output_seal
from .solver_validation import (expected_update_epochs, validate_nav_alignment, validate_clean5_manifest,
    validate_outputpath_only, validate_profile_counters, validate_run_outputs)

C04_RECORD_COMMIT = "8b83642e3692b7bd3752391744ca2c53c6cfb89b"
C04_RECORD_SHA256 = "1fab5709dc654c68952aa6c21c947024e4b71621dbeec4bbe5ad7f350d5787ba"
HUMAN_PROTOCOL_STATEMENT = "无 PTP 跨设备对时；启动时蹬一脚；算法起点 = 蹬脚后 GNSS 与机身 IMU 同时出现运动的时刻；结束 = 去掉末尾若干秒。"
AMENDMENT_REASON = ("The human acquisition protocol requires the kick before the algorithm start; "
    "v1 B-prime does not encode this event order, and BY2O v1 starts about 0.35 s before its kick. "
    "Amendment requested before any CLEAN5 reference-trace unblinding or evaluation.")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).strip()


def _published_source(args, registry):
    root = args.code_root.resolve(strict=True)
    if root != registry.code_root or root != Path(__file__).resolve().parents[4]:
        raise RuntimeError("Revalidation must execute the published active-worktree source")
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_freeze_commit):
        raise RuntimeError("Require full code freeze SHA")
    if any(_git(root, "rev-parse", ref) != args.code_freeze_commit for ref in
           ("HEAD", "refs/remotes/origin/stage/clean3-math-repair")):
        raise RuntimeError("Revalidation code must be committed and pushed first")
    if _git(root, "diff", "HEAD", "--name-only"):
        raise RuntimeError("Tracked source changed after the published code freeze")
    return {"code_freeze_commit": args.code_freeze_commit, "code_root": str(root),
        "tracked_worktree_clean": True,
        "original_untracked_files_preserved": _git(root, "status", "--porcelain=v1", "--untracked-files=all")}


def _record_hashes(root):
    text = subprocess.check_output(["git", "show", C04_RECORD_COMMIT +
        ":docs/paper_rebuild/CLEAN5_SOLVER_RUN_RECORD.md"], cwd=root)
    import hashlib
    if hashlib.sha256(text).hexdigest() != C04_RECORD_SHA256:
        raise RuntimeError("Pinned C-04 record changed")
    return dict(re.findall(r"\| `(<CLEAN_ROOT>/[^`]+)` \| `([0-9a-f]{64})` \|", text.decode()))


def skipped_update_epochs(run_dir, expected_epochs):
    """Report eligible epochs absent from native position-update diagnostics.

    This list never reduces the invariant's expected count. Native stale rows
    also include already-applied observations and are deliberately not counted.
    """
    path = Path(run_dir) / "PORT_GNSS_UPDATE_TRACE.csv"
    if not path.is_file():
        return {"status": "UNAVAILABLE", "reason": "native update diagnostic absent"}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    actual = {float(row["gnss_time"]) for row in rows if row["position_update"] == "1"}
    return {"status": "AVAILABLE", "source": path.name,
        "eligible_but_not_position_updated_epochs": [t for t in expected_epochs if t not in actual],
        "applied_position_epoch_count": len(actual), "changes_expected_count": False}


def revalidate_run(run_dir, contract, rendered_config):
    run_dir = Path(run_dir)
    original = _read(run_dir / "CLEAN5_FORMAL_RUN_MANIFEST.json")
    text = (run_dir / "CLEAN5_RUNTIME_CONFIG.yaml").read_text()
    cfg = yaml.safe_load(text)
    manifest = _read(run_dir / "RUN_MANIFEST.json")
    snapshot_path = run_dir / "PORT_INPUT_TIMELINE_SNAPSHOT.json"
    snapshot = _read(snapshot_path)
    report = {"run_id": original["run_id"], "dataset_id": original["dataset_id"],
        "data_mode": original["data_mode"], "method_id": original["method_id"],
        "effective_profile": original["effective_profile"], "original_terminal_status": original["terminal_status"],
        "original_exit_code": original["exit_code"], "terminal_status": "COMPLETED", "errors": [],
        "synthetic_data_used": False, "semisynthetic_data_used": False,
        "trace_used_online": False, "evaluator_execution_count": 0, "solver_execution_count": 0,
        "native_time_snapshot": {"path": str(snapshot_path), "sha256": sha256_file(snapshot_path)},
        "effective_starttime_source": "PORT_INPUT_TIMELINE_SNAPSHOT.json.effective_starttime",
        "effective_starttime_absent_from_native_run_manifest": "effective_starttime" not in manifest,
        "original_wrapper_sha256": sha256_file(run_dir / "CLEAN5_FORMAL_RUN_MANIFEST.json")}
    validate_outputpath_only(rendered_config, text)
    eligibility = expected_update_epochs(cfg, snapshot, Path(cfg["gnsspath"]))
    report["epoch_eligibility"] = eligibility
    report["effective_starttime"] = eligibility["effective_starttime"]
    report["t_init"] = eligibility["t_init"]
    report["skipped_update_diagnostic"] = skipped_update_epochs(run_dir, eligibility["eligible_epoch_times"])
    for name, operation in (
        ("output_structure", lambda: validate_run_outputs(run_dir, contract)),
        ("native_manifest", lambda: validate_clean5_manifest(manifest, text, contract)),
        ("counters", lambda: validate_profile_counters(cfg["algorithm_id"], manifest, eligibility["expected_update_count"])),
    ):
        try:
            report[name] = operation()
            if name == "output_structure":
                report["nav_alignment"] = validate_nav_alignment(report[name]["nav_time_start"], eligibility)
        except Exception as exc:
            report["errors"].append({"gate": name, "type": type(exc).__name__, "message": str(exc)})
            report["terminal_status"] = getattr(exc, "terminal_status", "technical_failure")
            if hasattr(exc, "counters"):
                report["counters"] = exc.counters
    if original["exit_code"] != 0:
        report["errors"].append({"gate": "exit_code", "message": "original solver did not exit zero"})
        report["terminal_status"] = "technical_failure"
    report["passed"] = not report["errors"]
    return report


def revalidation_worker(args, registry, audit_root, state):
    hashes = _record_hashes(registry.code_root)
    local = yaml.safe_load(args.paths_config.read_text())["paths"]
    canonical = Path(local["canonical541_attempt"]) if "canonical541_attempt" in local else (
        registry.clean_root / "stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800")
    pattern = verify_canonical_patterns(canonical / "13_AGGREGATE/MODULE_ACTION_SUMMARY.csv")
    records = []
    for dataset in ("BY2H", "BY2O"):
        seq = registry.sequences[dataset]
        stage = registry.clean_root / "stages" / seq.stage_id
        checked = {}
        for relative in ("05_OUTPUT_SEAL/OUTPUT_SEAL.json", "05_OUTPUT_SEAL/SEAL_GATE.json",
                         "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json", "03_RUNTIME_CONFIGS/RUNTIME_CONFIG_AUDIT.json"):
            path = stage / relative
            expected = hashes["<CLEAN_ROOT>/" + path.relative_to(registry.clean_root).as_posix()]
            if sha256_file(path) != expected:
                raise RuntimeError("Pinned v1 artifact SHA mismatch: " + str(path))
            checked[relative] = expected
        seal = validate_output_seal(stage / "05_OUTPUT_SEAL/OUTPUT_SEAL.json")
        providers = verify_provider_files(stage / "02_PROVIDER_FREEZE", _read(stage / "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"))
        rel = f"configs/paper_rebuild/clean5/CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
        frozen = subprocess.check_output(["git", "show", C02_COMMIT + ":" + rel], cwd=registry.code_root)
        if (registry.code_root / rel).read_bytes() != frozen:
            raise RuntimeError("v1 revalidation requires unchanged C-02 contract bytes")
        contract = yaml.safe_load(frozen)
        current = []
        for method, profile in METHODS.items():
            run = stage / "04_SOLVER_RUNS" / f"{dataset}_{method}_{profile}"
            current.append(revalidate_run(run, contract, (stage / "03_RUNTIME_CONFIGS" / CONFIG_FILENAMES[method]).read_text()))
        # Revalidation did not touch any sealed bytes, including old terminal flags.
        validate_output_seal(stage / "05_OUTPUT_SEAL/OUTPUT_SEAL.json")
        result = {"dataset_id": dataset, "runs": current, "passed_count": sum(r["passed"] for r in current),
            "original_hashes": checked, "provider_revalidation": providers, "seal_revalidation": seal,
            "human_protocol_statement": HUMAN_PROTOCOL_STATEMENT, "amendment_reason": AMENDMENT_REASON, **state}
        write_json_exclusive(audit_root / f"{dataset}_V1_REVALIDATION.json", result)
        records.extend(current)
        print(f"{dataset} revalidate: {result['passed_count']}/5 PASS", flush=True)
    passed = len(records) == 10 and all(r["passed"] for r in records)
    result = {"status": "PASS" if passed else "FAIL_REVALIDATION_GATE", "passed": passed,
        "expected_run_count": 10, "passed_run_count": sum(r["passed"] for r in records), "runs": records,
        "canonical_c00_module_pattern": pattern, "human_protocol_statement": HUMAN_PROTOCOL_STATEMENT,
        "amendment_reason": AMENDMENT_REASON, "v1_unchanged": True, "superseded_markers_written": False,
        "event_window_computation_count": 0, "v2_contract_written": False,
        "trace_opened": False, "synthetic_data_used": False, "semisynthetic_data_used": False, **state}
    write_json_exclusive(audit_root / "REVALIDATION_RESULT.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("revalidate",), required=True)
    parser.add_argument("--paths-config", type=Path, required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--code-freeze-commit", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--_revalidation-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0")
    registry = load_registry(args.code_root / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml", args.paths_config)
    state = _published_source(args, registry)
    verify_executable(args.executable, registry.code_root)
    root = registry.clean_root / "stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/00_C04B_REVALIDATION_V2"
    if args._revalidation_worker:
        from .probes import forbidden_path_guard
        with forbidden_path_guard(registry.raw_root, set()):
            revalidation_worker(args, registry, root, state)
        return 0
    if not shutil.which("strace"):
        raise RuntimeError("strace required for read-only revalidation")
    root.mkdir(exist_ok=False)
    script = args.code_root / "scripts/paper_rebuild/clean5_run_sequence.py"
    log = root / "REVALIDATION_OPENAT.strace"
    command = ["strace", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(log),
        sys.executable, "-B", str(script), *list(argv or sys.argv[1:]), "--_revalidation-worker"]
    completed = run_process_group(command, cwd=registry.code_root, timeout_seconds=1800,
        timeout_message="Read-only revalidation timed out", launch_failure_message="Cannot launch revalidation")
    for name, text in (("stdout.log", completed.stdout), ("stderr.log", completed.stderr)):
        with (root / name).open("x") as handle:
            handle.write(text)
    audit = audit_solver_openat(log, cwd=registry.code_root, raw_root=registry.raw_root, run_dir=root, clean_root=registry.clean_root)
    write_json_exclusive(root / "REVALIDATION_STRACE_AUDIT.json", audit)
    result = _read(root / "REVALIDATION_RESULT.json") if (root / "REVALIDATION_RESULT.json").is_file() else {}
    passed = (completed.returncode == 0 and audit["pass"] and result.get("passed") is True
        and result.get("expected_run_count") == 10 and result.get("passed_run_count") == 10
        and len(result.get("runs", [])) == 10 and all(r.get("passed") is True for r in result["runs"]))
    if passed:
        for dataset in ("BY2H", "BY2O"):
            stage = registry.clean_root / "stages" / registry.sequences[dataset].stage_id
            for name in ("04_SOLVER_RUNS", "05_OUTPUT_SEAL"):
                write_json_exclusive(stage / name / "SUPERSEDED.json", {
                    "status": "SUPERSEDED_NOT_EVALUATED", "reason": AMENDMENT_REASON,
                    "amended_before_unblinding": True, "trace_opened": False,
                    "human_protocol_statement": HUMAN_PROTOCOL_STATEMENT,
                    "revalidation_result_sha256": sha256_file(root / "REVALIDATION_RESULT.json"), **state})
    gate = {"status": "PASS" if passed else "FAIL_REVALIDATION_GATE", "passed": passed,
        "passed_run_count": result.get("passed_run_count"), "worker_exit_code": completed.returncode,
        "strace_audit": audit, "superseded_markers_written": passed,
        "stop_before_event_window_and_contract_v2": not passed,
        "result_sha256": sha256_file(root / "REVALIDATION_RESULT.json") if result else None, **state}
    write_json_exclusive(root / "REVALIDATION_GATE.json", gate)
    print(completed.stdout, end="")
    print(json.dumps({"gate": gate["status"], "passed_run_count": gate["passed_run_count"],
        "audit_root": str(root), "stderr_tail": completed.stderr[-4000:]}, ensure_ascii=False), flush=True)
    return 0 if passed else 3
