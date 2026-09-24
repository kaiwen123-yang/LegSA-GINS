"""HX-02 controller: 24 external native runs, registered evaluations, per-batch archive.

Order: batches BY2 -> BY2H -> BY2O; inside a batch EXT01, EXT02, EXT03, EXT04,
RTKLIB, Hartley-S, Hartley-LIT, GINav run one at a time (native concurrency 1,
internal workers <= 16), each preceded by the disk guard and a quiet-machine wait.
Every native process runs under ``strace --seccomp-bpf -f -e trace=openat,execve``;
any opening of a reference trajectory (trace/bag/fpl) by a non-evaluator process
is a hard stop. Reference trajectories are opened only by the registered
evaluator children. LegSA configurations are never solved or evaluated.
Progress lives in $HX02/00_CONTROL (PROGRESS.txt, STATE.json, LEDGER.jsonl);
archived runs are never rerun.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from . import (hx02_convention, hx02_evaluation_process, hx02_ginav, hx02_ginav_nav, hx02_hartley,
               hx02_heading_tables, hx02_params_echo, hx02_rtklib, hx02_sequence)
from .sequence_paths import load_sequence_paths

GB = 1_000_000_000
E_GUARD_BYTES = 40 * GB
G_GUARD_BYTES = 30 * GB
SCRATCH_LIMIT_BYTES = 20 * GB
SEQUENCES = ("BY2", "BY2H", "BY2O")
METHODS = ("EXT01", "EXT02", "EXT03", "EXT04", "RTKLIB", "HARTLEY_S", "HARTLEY_LIT", "GINAV")
METHOD_CONFIG = {"EXT01": "LIT", "EXT02": "LIT", "EXT03": "LIT", "EXT04": "LIT", "RTKLIB": "NONE",
                 "HARTLEY_S": "S", "HARTLEY_LIT": "LIT", "GINAV": "NONE"}
RUNNER_SCRIPTS = {
    "EXT01": ("scripts/paper_rebuild/run_horizontal_literature_phase1r.py", ["--trace-mode", "disabled", "--workers", "16"]),
    "EXT02": ("scripts/paper_rebuild/run_horizontal_literature_phase2.py", ["--mode", "native-only", "--trace-mode", "disabled", "--workers", "16"]),
    "EXT03": ("scripts/paper_rebuild/run_horizontal_literature_phase3.py", ["--mode", "native-only", "--trace-mode", "disabled", "--workers", "16"]),
    "EXT04": ("scripts/paper_rebuild/run_horizontal_literature_phase4.py", ["--mode", "native-only", "--trace-mode", "disabled", "--workers", "16"]),
}
NATIVE_HEADING_CSV = {
    "EXT01": "02_EXT01_CLAMBDA/C00_VALIDATED_R2/EXT01_C00_VALIDATED_NATIVE_HEADING_RESULTS.csv",
    "EXT02": "03_EXT02_CWLS/C00/EXT02_C00_NATIVE_HEADING_RESULTS.csv",
    "EXT03": "04_EXT03_YANG2024/C00/EXT03_C00_NATIVE_HEADING_RESULTS.csv",
    "EXT04": "05_EXT04_WU2025_MODULE/C00/EXT04_C00_NATIVE_HEADING_RESULTS.csv",
}
NATIVE_FREEZE = {
    "EXT01": "02_EXT01_CLAMBDA/C00_VALIDATED_R2/PHASE1R_NATIVE_FREEZE.json",
    "EXT02": "03_EXT02_CWLS/C00/EXT02_C00_NATIVE_FREEZE.json",
    "EXT03": "04_EXT03_YANG2024/C00/EXT03_C00_NATIVE_FREEZE.json",
    "EXT04": "05_EXT04_WU2025_MODULE/C00/EXT04_C00_NATIVE_FREEZE.json",
}
REFERENCE_NAME = re.compile(r"(^trace_|trace_vrtk|\.fpl$|\.bag$)", re.IGNORECASE)
FROZEN_EVALUATOR_REL = "16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py"
FROZEN_EVALUATOR_SHA256 = "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"


class HardStop(RuntimeError):
    """A registered hard-stop condition."""


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hx02_sequence.sha256_file(path)


def write_json(path: Path, payload: Any, *, exclusive: bool = True) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    with path.open("x" if exclusive else "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(text.encode()).hexdigest()


@dataclasses.dataclass(frozen=True)
class Roots:
    code: Path
    clean: Path
    raw: Path
    external: Path
    stage: Path
    scratch: Path
    paths_config: Path
    contract: Mapping[str, Any]

    @property
    def control(self) -> Path:
        return self.stage / "00_CONTROL"

    @property
    def pins(self) -> Path:
        return self.stage / "01_INPUT_PINS"


def load_roots(paths_config: Path = Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml")) -> Roots:
    """Stage root from the contract alias; scratch and external roots from the ignored local keys."""
    local = yaml.safe_load(Path(paths_config).read_text(encoding="utf-8"))["paths"]
    contract = hx02_sequence.load_contract()
    declared = contract["roots"]
    clean = Path(local["clean_root"])
    stage = Path(declared["stage"].replace("<CLEAN_ROOT>", str(clean)))
    scratch = Path(local[declared["scratch_local_key"]])
    if scratch.name != declared["scratch_directory_name"] or str(scratch).startswith("/mnt/"):
        raise HardStop(f"scratch root is not the registered ext4 scratch: {scratch}")
    return Roots(Path(local["code_root"]), clean, Path(local["raw_root"]), Path(local[declared["external_local_key"]]),
                 stage, scratch, Path(paths_config).resolve(), contract)


def contract_sha256() -> str:
    return sha256_file(hx02_sequence.HX02_CONTRACT)


def provenance(seq: hx02_sequence.HX02Sequence, *, code_commit: str, old_runtime_input_count: int | None) -> dict[str, Any]:
    """Required clean-run provenance (AGENTS.md); the count comes from the native open audit."""
    return {"data_mode": seq.data_mode, "synthetic_data_used": False, "semisynthetic_data_used": False,
            "trace_used_online": False, "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False, "per_case_tuning": False, "output_only_correction": False,
            "epoch_deleted_for_metric": False, "old_runtime_input_count": old_runtime_input_count,
            "code_commit": code_commit, "config_hash": contract_sha256(),
            "config_hash_source": hx02_sequence.HX02_CONTRACT.as_posix(),
            "raw_hash_lock": {"path": seq.raw_hash_lock.replace(seq.clean_root, "<CLEAN_ROOT>"),
                              "sha256": seq.raw_hash_lock_sha256}}


def run_id(sequence: str, method: str) -> str:
    case = hx02_sequence.load_contract()["sequences"][sequence]["case"]
    return f"{sequence}__{method}__{METHOD_CONFIG[method]}__{case}__NA"


# --------------------------------------------------------------------------- control
class Control:
    def __init__(self, roots: Roots):
        self.roots = roots
        roots.control.mkdir(parents=True, exist_ok=True)
        self.ledger = roots.control / "LEDGER.jsonl"
        self.state_path = roots.control / "STATE.json"
        self.progress_path = roots.control / "PROGRESS.txt"
        self.state = self._replay()

    def _replay(self) -> dict[str, Any]:
        state: dict[str, Any] = {"runs": {}, "counters": {"native_calls": 0, "evaluator_calls": 0,
                                                          "reference_free_evaluator_calls": 0,
                                                          "legsa_native_calls": 0, "legsa_evaluator_calls": 0}}
        if self.ledger.is_file():
            for line in self.ledger.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("run_id"):
                    state["runs"].setdefault(event["run_id"], {}).update(event.get("state", {}))
                for run, update in event.get("runs_state", {}).items():
                    state["runs"].setdefault(run, {}).update(update)
                for key, value in event.get("counter_increments", {}).items():
                    state["counters"][key] = state["counters"].get(key, 0) + value
        return state

    def event(self, kind: str, *, run: str | None = None, state: Mapping[str, Any] | None = None,
              counters: Mapping[str, int] | None = None, runs_state: Mapping[str, Mapping[str, Any]] | None = None,
              **details: Any) -> None:
        """One ledger line; ``runs_state`` updates several runs atomically (Hartley pair)."""
        payload = {"utc": utc(), "kind": kind, "run_id": run, "state": dict(state or {}),
                   "runs_state": {key: dict(value) for key, value in (runs_state or {}).items()},
                   "counter_increments": dict(counters or {}), **details}
        with self.ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if run:
            self.state["runs"].setdefault(run, {}).update(state or {})
        for key, value in (runs_state or {}).items():
            self.state["runs"].setdefault(key, {}).update(value)
        for key, value in (counters or {}).items():
            self.state["counters"][key] = self.state["counters"].get(key, 0) + value
        write_json(self.state_path, {"updated_utc": utc(), **self.state}, exclusive=False)
        self.progress(f"{kind} {run or ''} {json.dumps(details, default=str)[:300]}")

    def progress(self, message: str) -> None:
        with self.progress_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc()} {message}\n")
            handle.flush()
            os.fsync(handle.fileno())

    def status(self, run: str) -> str:
        return str(self.state["runs"].get(run, {}).get("status", "PENDING"))


def disk_guard(control: Control, roots: Roots, when: str) -> dict[str, Any]:
    def avail(path: str) -> int:
        result = subprocess.run(["df", "--output=avail", "-B1", path], capture_output=True, text=True, check=True)
        return int(result.stdout.split()[-1])
    scratch_bytes = int(subprocess.run(["du", "-sb", str(roots.scratch)], capture_output=True, text=True,
                                       check=False).stdout.split()[0] or 0) if roots.scratch.exists() else 0
    record = {"when": when, "mnt_e_avail_bytes": avail("/mnt/e"), "mnt_g_avail_bytes": avail("/mnt/g"),
              "scratch_bytes": scratch_bytes}
    record["pass"] = (record["mnt_e_avail_bytes"] >= E_GUARD_BYTES and record["mnt_g_avail_bytes"] >= G_GUARD_BYTES
                      and scratch_bytes <= SCRATCH_LIMIT_BYTES)
    control.event("DISK_GUARD", **record)
    if not record["pass"]:
        raise HardStop(f"disk guard below registered line: {record}")
    return record


def quiet_machine(control: Control, max_wait_s: float = 7200.0) -> dict[str, Any]:
    started = time.monotonic()
    while True:
        load1, load5, _ = os.getloadavg()
        if (load1 <= 8.0 and load5 <= 10.0) or time.monotonic() - started > max_wait_s:
            record = {"load1": load1, "load5": load5, "waited_s": time.monotonic() - started,
                      "quiet": load1 <= 8.0 and load5 <= 10.0}
            control.progress(f"QUIET_MACHINE {json.dumps(record)}")
            return record
        time.sleep(30)


# --------------------------------------------------------------------------- native audit
def audit_native_strace(log: Path, roots: Roots, sequence: hx02_sequence.HX02Sequence,
                        declared_raw: Sequence[str]) -> dict[str, Any]:
    opened_reference, raw_opens, programs, clean_opens = [], set(), set(), set()
    pattern = re.compile(r'(openat|execve)\((?:[^,]+,\s*)?"((?:\\.|[^"\\])*)"')
    allowed_clean = (str(roots.clean / "01_RAW_HASH_LOCK") + "/", str(roots.stage) + "/")
    for line in Path(log).read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        path = match.group(2).encode("latin-1", errors="ignore").decode("unicode_escape", errors="ignore")
        path = path.encode("latin-1", errors="ignore").decode("utf-8", errors="replace")
        if match.group(1) == "execve":
            if "= 0" in line or "<unfinished" in line or line.rstrip().endswith("= 0"):
                programs.add(path)
            continue
        name = Path(path).name
        if REFERENCE_NAME.search(name) or path == sequence.trace_path_evaluator_only:
            opened_reference.append(line.strip()[:400])
        if path.startswith(str(roots.raw)):
            raw_opens.add(path)
        failed = re.search(r"= -1 E[A-Z]+", line) is not None
        if (path.startswith(str(roots.clean) + "/") and not failed and "O_DIRECTORY" not in line
                and not path.startswith(allowed_clean)):
            clean_opens.add(path)
    undeclared = sorted(raw_opens - set(declared_raw))
    return {"reference_open_lines": opened_reference, "reference_open_count": len(opened_reference),
            "raw_paths_opened": sorted(raw_opens), "undeclared_raw_paths": undeclared,
            "old_runtime_input_paths": sorted(clean_opens), "old_runtime_input_count": len(clean_opens),
            "old_runtime_input_rule": "files opened under <CLEAN_ROOT> outside 01_RAW_HASH_LOCK/ and the HX-02 stage",
            "executed_programs": sorted(programs), "strace_sha256": sha256_file(log)}


CONTROLLER_STRACE_ENV = "HX02_CONTROLLER_STRACE"
OPENAT_PATH_RE = re.compile(r'openat\((?:[^,]+,\s*)?"((?:\\.|[^"\\])*)"')


def _decoded(raw: str) -> str:
    path = raw.encode("latin-1", errors="ignore").decode("unicode_escape", errors="ignore")
    return path.encode("latin-1", errors="ignore").decode("utf-8", errors="replace")


def controller_self_audit(roots: Roots, when: str, log: str | None = None) -> dict[str, Any]:
    """The controller runs under its own openat audit (strace without -f, so the nested native
    and evaluator audits keep working); any reference opening by the controller is a hard stop."""
    log = log if log is not None else os.environ.get(CONTROLLER_STRACE_ENV)
    if not log or not Path(log).is_file():
        raise HardStop(f"the controller must run under its own openat audit ({CONTROLLER_STRACE_ENV} unset or missing)")
    traces = {hx02_sequence.load_sequence(s, roots.contract).trace_path_evaluator_only for s in SEQUENCES}
    hits, opens = [], 0
    for line in Path(log).read_text(encoding="utf-8", errors="replace").splitlines():
        match = OPENAT_PATH_RE.search(line)
        if not match:
            continue
        opens += 1
        path = _decoded(match.group(1))
        if REFERENCE_NAME.search(Path(path).name) or path in traces:
            hits.append(line.strip()[:300])
    if hits:
        raise HardStop(f"the controller process opened a reference trajectory ({when}): {hits[:3]}")
    return {"when": when, "openat_lines": opens, "reference_open_count": 0, "log": str(log)}


def launch(argv: Sequence[str], *, cwd: Path, run_dir: Path, env_extra: Mapping[str, str], timeout_s: float,
           label: str) -> dict[str, Any]:
    log = run_dir / "native" / f"{label}_OPENAT.strace"
    env = {key: value for key, value in os.environ.items() if key != CONTROLLER_STRACE_ENV}
    env = {**env, "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
           "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "PYTHONPATH": str(cwd / "src"), **env_extra}
    command = ["strace", "--seccomp-bpf", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat,execve",
               "-o", str(log), *argv]
    started = time.monotonic()
    begin = utc()
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, errors="replace",
                                   timeout=timeout_s, check=False)
        returncode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = -9
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")) + \
            f"\nHX02_TIMEOUT after {timeout_s}s; no retry"
    (run_dir / "native" / f"{label}_stdout.log").write_text(stdout, encoding="utf-8")
    (run_dir / "native" / f"{label}_stderr.log").write_text(stderr, encoding="utf-8")
    return {"argv": list(argv), "strace_command_prefix": command[:command.index(argv[0])], "cwd": str(cwd),
            "env_whitelist": {k: env[k] for k in ("PYTHONDONTWRITEBYTECODE", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                                                  "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS", "PYTHONPATH")},
            "start_utc": begin, "end_utc": utc(), "returncode": returncode, "runtime_seconds": time.monotonic() - started,
            "strace_log": str(log), "stdout_tail": stdout[-3000:], "stderr_tail": stderr[-6000:]}


def git_head(code_root: Path) -> str:
    return subprocess.run(["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=code_root, capture_output=True,
                          text=True, check=True).stdout.strip()


def tracked_tree_clean(code_root: Path) -> bool:
    return not subprocess.run(["git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=no"],
                              cwd=code_root, capture_output=True, text=True, check=True).stdout.strip()


# --------------------------------------------------------------------------- per-method native
def sequence_spec(roots: Roots, seq: hx02_sequence.HX02Sequence, method: str, artifact_root: Path,
                  pairing: Mapping[str, Any]) -> dict[str, Any]:
    spec = {
        "sequence_id": seq.sequence_id, "data_mode": seq.data_mode, "raw_root": seq.raw_root, "fix_root": seq.fix_root,
        "gnss1_raw": seq.gnss1_raw, "gnss2_raw": seq.gnss2_raw, "raw_hash_lock": seq.raw_hash_lock,
        "base_time": seq.base_time, "window": list(seq.window), "start_convention": seq.start_convention,
        "native_start_rel_s": seq.native_start_rel_s, "full_pair_count": int(pairing["exact_pairs_full_file"]),
        "selected_pair_count": int(pairing["selected_pairs"]), "artifact_root": str(artifact_root), "method_id": method,
        "leap_seconds": seq.leap_seconds,
    }
    if method == "EXT03":
        spec["variant_ids"] = ["GPS_BDS_DUAL_FREQUENCY__CONSTRAINED__0.010"]
    if method == "EXT04":
        spec["system_modes"] = ["GPS_BDS_DUAL_FREQUENCY"]
        spec["policy_ids"] = ["FAR_ALL_AMBIGUITIES", "EXT04_PAR_DECLARED_POLICY_V1"]
    return spec


def load_pins(roots: Roots) -> dict[str, Any]:
    """Input pins written by ``prepare`` before the code freeze (never recomputed at run time)."""
    registered = roots.contract.get("input_pins_sha256")
    if not registered or sha256_file(roots.pins / "INPUT_PINS.json") != registered:
        raise HardStop("INPUT_PINS.json differs from the pin registered in HX02_CONTRACT_V1")
    return json.loads((roots.pins / "INPUT_PINS.json").read_text(encoding="utf-8"))


def native_ext(roots: Roots, seq: hx02_sequence.HX02Sequence, method: str, run_dir: Path,
               pins: Mapping[str, Any]) -> dict[str, Any]:
    artifact = run_dir / "native" / "ARTIFACT"
    spec = sequence_spec(roots, seq, method, artifact, pins["pairing"][seq.sequence_id])
    spec_sha = hx02_sequence.write_spec(run_dir / "native" / "SEQUENCE_SPEC.json", spec)
    script, extra = RUNNER_SCRIPTS[method]
    argv = [sys.executable, str(roots.code / script), "--paths-config", str(roots.paths_config),
            "--sequence-spec", str(run_dir / "native" / "SEQUENCE_SPEC.json"), *extra]
    result = launch(argv, cwd=roots.code, run_dir=run_dir, env_extra={}, timeout_s=6 * 3600, label="NATIVE")
    result["sequence_spec_sha256"] = spec_sha
    heading_csv = artifact / NATIVE_HEADING_CSV[method]
    freeze = artifact / NATIVE_FREEZE[method]
    result["native_complete"] = heading_csv.is_file() and freeze.is_file()
    result["declared_raw"] = [seq.gnss1_raw, seq.gnss2_raw]
    return result


def native_rtklib(roots: Roots, seq: hx02_sequence.HX02Sequence, run_dir: Path, pins: Mapping[str, Any]) -> dict[str, Any]:
    argv = [sys.executable, "-m", "legsa_gins.paper_rebuild.hext.hx02_native_cli", "rtklib",
            "--sequence", seq.sequence_id, "--run-dir", str(run_dir),
            "--conf", str(roots.pins / "RTKLIB_UNMODIFIED_MOVING_BASE.conf")]
    result = launch(argv, cwd=roots.code, run_dir=run_dir, env_extra={}, timeout_s=2 * 3600, label="NATIVE")
    result["native_complete"] = (run_dir / "native" / "RTKLIB_UNMODIFIED_MOVING_BASE.pos").is_file()
    result["declared_raw"] = [seq.gnss1_raw, seq.gnss2_raw]
    return result


def native_hartley(roots: Roots, seq: hx02_sequence.HX02Sequence, method: str, run_dir: Path,
                   pins: Mapping[str, Any]) -> dict[str, Any]:
    config = "S" if method == "HARTLEY_S" else "LIT"
    hartley_pin = pins["hartley"][seq.sequence_id]
    cache = roots.pins / "HARTLEY" / seq.sequence_id / "H5_INPUT_CACHE.bin"
    if sha256_file(cache) != hartley_pin["cache_sha256"]:
        raise HardStop("pinned Hartley cache changed")
    runner = Path(pins["hartley_runner"]["runner"])
    if sha256_file(runner) != pins["hartley_runner"]["runner_sha256"]:
        raise HardStop("pinned Hartley runner changed")
    local_cache = run_dir / "native" / "provider" / "H5_INPUT_CACHE.bin"
    local_cache.parent.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(cache, local_cache)
    if sha256_file(local_cache) != hartley_pin["cache_sha256"]:
        raise HardStop("Hartley cache copy differs")
    out = run_dir / "native" / "run"
    cfg, config_hash = hx02_hartley.write_config(
        out, config=config, record_count=int(hartley_pin["record_count"]), cache_sha256=hartley_pin["cache_sha256"],
        code_commit=git_head(roots.code), scoped=hx02_hartley.scoped_manifest(roots.code),
        runner_sha256=pins["hartley_runner"]["runner_sha256"])
    argv = [str(runner), str(local_cache), str(cfg), str(out)]
    result = launch(argv, cwd=roots.code, run_dir=run_dir, env_extra={}, timeout_s=2 * 3600, label="NATIVE")
    result.update(config_hash=config_hash, native_complete=(out / "NAV.csv").is_file() and result["returncode"] == 0,
                  declared_raw=[])
    return result


def native_ginav(roots: Roots, seq: hx02_sequence.HX02Sequence, run_dir: Path, pins: Mapping[str, Any]) -> dict[str, Any]:
    argv = [sys.executable, "-m", "legsa_gins.paper_rebuild.hext.hx02_native_cli", "ginav",
            "--sequence", seq.sequence_id, "--run-dir", str(run_dir),
            "--prepared", str(roots.pins / "GINAV" / seq.sequence_id / "GINAV_INPUT_PREPARATION.json"),
            "--pinned-listing", str(roots.control / "METHOD_BODY_SHA256_BEFORE.json"),
            "--external-root", str(roots.external)]
    result = launch(argv, cwd=roots.code, run_dir=run_dir, env_extra={}, timeout_s=2 * 3600, label="NATIVE")
    record = run_dir / "native" / "GINAV_RUN.json"
    ginav = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {}
    result.update(ginav_run=ginav, native_complete=bool(ginav.get("native_pos")), declared_raw=[])
    return result


# --------------------------------------------------------------------------- post-native
EVALUATED_STATUSES = ("COMPLETED", "COMPLETED_ABNORMAL_EXIT")
TERMINAL_RE = re.compile(r'"terminal_status"\s*:\s*"([^"]+)"')


def classify(native: Mapping[str, Any]) -> str:
    """Complete native output is evaluated; a non-zero exit alongside it is kept as a flagged result."""
    if native.get("environment_failure"):
        return "RUN_FAILED_ENVIRONMENT"
    if native.get("native_complete"):
        return "COMPLETED" if native.get("returncode") == 0 else "COMPLETED_ABNORMAL_EXIT"
    if native.get("returncode") == 0:
        return "NO_OUTPUT"
    return "ABNORMAL_EXIT"


def runner_terminal_status(run_dir: Path) -> str | None:
    """Last terminal_status printed by a phase runner (its own validation verdict)."""
    log = run_dir / "native" / "NATIVE_stdout.log"
    found = TERMINAL_RE.findall(log.read_text(encoding="utf-8", errors="replace")) if log.is_file() else []
    return found[-1] if found else None


def output_hashes(run_dir: Path) -> dict[str, Any]:
    files = {}
    for path in sorted((run_dir / "native").rglob("*")):
        if path.is_file() and not path.is_symlink():
            files[path.relative_to(run_dir).as_posix()] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return {"file_count": len(files), "files": files}


def heading_tables(method: str, run_dir: Path, seq: hx02_sequence.HX02Sequence,
                   native: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    out = run_dir / "native" / "HX02_HEADING_TABLES"
    out.mkdir(parents=True, exist_ok=False)
    if method == "RTKLIB":
        prepared = json.loads((run_dir / "native" / "RTKLIB_PREPARED.json").read_text(encoding="utf-8"))
        rows, summary = hx02_rtklib.heading_table(prepared, run_dir / "native" / "RTKLIB_UNMODIFIED_MOVING_BASE.pos",
                                                  seq.leap_seconds)
        write_json(out / "RTKLIB_ASSOCIATION_SUMMARY.json", summary)
        tables = {"RTKLIB": rows}
    else:
        tables = hx02_heading_tables.ADAPTERS[method](run_dir / "native" / "ARTIFACT" / NATIVE_HEADING_CSV[method],
                                                      seq.leap_seconds)
    result = {}
    for label, rows in tables.items():
        path = out / f"HX02_HEADING_TABLE_{label}.csv"
        result[label] = {"path": str(path), "sha256": hx02_heading_tables.write_table(rows, path),
                         "rows": len(rows), "valid": sum(int(r["valid"]) for r in rows)}
    return result


def params_echo(method: str, run_dir: Path, roots: Roots, reference: Mapping[str, Any]) -> dict[str, Any]:
    if method in NATIVE_HEADING_CSV:
        actual = getattr(hx02_params_echo, method.lower())(run_dir / "native" / "ARTIFACT")
        info = hx02_params_echo.file_identities(method, run_dir / "native" / "ARTIFACT")
    elif method == "RTKLIB":
        actual, info = hx02_params_echo.rtklib(run_dir / "native" / "RTKLIB_UNMODIFIED_MOVING_BASE.conf"), {}
    elif method.startswith("HARTLEY"):
        actual, info = hx02_params_echo.hartley(run_dir / "native" / "run" / "NATIVE_SUMMARY.json"), {}
    else:
        config = Path(json.loads((run_dir / "native" / "GINAV_RUN.json").read_text())["config"])
        actual, info = hx02_params_echo.ginav(config), {}
    comparison = hx02_params_echo.compare(actual, reference)
    return {"method": method, "echo": actual, "reference_echo_source": "CLEAN4 BY2 record (01_INPUT_PINS/PARAMS_ECHO_REFERENCE.json)",
            "comparison": comparison, "file_identities_information": info}


# --------------------------------------------------------------------------- evaluation
def sequence_paths_for_eval(roots: Roots, sequence_id: str):
    seq = load_sequence_paths(sequence_id)
    return dataclasses.replace(seq, output_root=roots.stage, hext_scratch=roots.scratch)


def evaluate_heading(control: Control, roots: Roots, seq: hx02_sequence.HX02Sequence, method: str, run_dir: Path,
                     tables: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    spec = {"method_id": method, "sequence_id": seq.sequence_id, "base_time": seq.base_time, "window": list(seq.window),
            "trace": seq.trace_path_evaluator_only, "trace_sha256": seq.trace_sha256,
            "variants": [{"label": label, "heading_table": entry["path"], "heading_table_sha256": entry["sha256"]}
                         for label, entry in tables.items()]}
    control.event("EVALUATOR_LAUNCH", run=run_dir.name, counters={"evaluator_calls": 1}, kind_detail="HEADING")
    try:
        result = hx02_evaluation_process.run_child("HEADING", spec, workdir=run_dir / "eval" / "HEADING",
                                                   code_root=roots.code, raw_root=roots.raw, clean_root=roots.clean,
                                                   trace=Path(seq.trace_path_evaluator_only))
    except hx02_evaluation_process.EvaluationProcessError as exc:
        raise HardStop(f"heading evaluator technical/access failure in {run_dir.name}: {exc}") from exc
    return json.loads((Path(result["outdir"]) / "HEADING_METRICS.json").read_text(encoding="utf-8"))


def evaluate_ginav(control: Control, roots: Roots, seq: hx02_sequence.HX02Sequence, run_dir: Path) -> dict[str, Any]:
    from .external_evaluation import evaluate as frozen_evaluate
    from .t5a_runtime import bounded_lla_native

    from ..horizontal_literature.ginav2021.outputs import OutputContractError

    ginav = json.loads((run_dir / "native" / "GINAV_RUN.json").read_text(encoding="utf-8"))
    nav_dir = run_dir / "native" / "NAV"
    try:
        conversion = hx02_ginav_nav.convert(Path(ginav["native_pos"]), base_time=seq.base_time, window=seq.window,
                                            out_dir=nav_dir)
    except OutputContractError as exc:  # official file without usable rows: a recorded no-output result
        return {"evaluation_status": "NO_OUTPUT_OFFICIAL_SOLUTION_UNUSABLE", "conversion_error": str(exc)}
    write_json(nav_dir / "CONVERSION.json", conversion)
    native_nav = nav_dir / "GINAV_NATIVE_NAV11.nav"
    result: dict[str, Any] = {"conversion": conversion}
    control.event("EVALUATOR_LAUNCH", run=run_dir.name, counters={"reference_free_evaluator_calls": 1},
                  kind_detail="COVERAGE")
    try:
        coverage = hx02_evaluation_process.run_child(
            "COVERAGE", {"sequence_id": seq.sequence_id, "window": list(seq.window), "nav": str(native_nav),
                         "nav_sha256": sha256_file(native_nav)},
            workdir=run_dir / "eval" / "COVERAGE", code_root=roots.code, raw_root=roots.raw, clean_root=roots.clean,
            trace=None)
    except hx02_evaluation_process.EvaluationProcessError as exc:
        raise HardStop(f"coverage child technical/access failure in {run_dir.name}: {exc}") from exc
    result["coverage"] = json.loads((Path(coverage["outdir"]) / "COVERAGE_METRICS.json").read_text())
    window_nav = nav_dir / "GINAV_WINDOW_NAV11.nav"
    if not window_nav.is_file():
        result["evaluation_status"] = "NO_OUTPUT_IN_WINDOW"
        return result
    nav_sha = sha256_file(window_nav)
    gate = bounded_lla_native(window_nav, expected_sha256=nav_sha)
    gate = {**gate, "sealed_evaluator_nav_sha256": nav_sha}
    write_json(run_dir / "eval" / "D8_BOUNDED_GATE.json", gate)
    result["bounded_gate"] = gate
    if gate.get("passed") is not True:
        result["evaluation_status"] = "NOT_RUN_ALGORITHM_FAILURE"
        return result
    evaluator = roots.clean / FROZEN_EVALUATOR_REL
    if sha256_file(evaluator) != FROZEN_EVALUATOR_SHA256:
        raise HardStop("frozen evaluator identity mismatch")
    paths = sequence_paths_for_eval(roots, seq.sequence_id)
    for version in ("v3", "v2"):
        control.event("EVALUATOR_LAUNCH", run=run_dir.name, counters={"evaluator_calls": 1},
                      kind_detail=f"FROZEN_{version}")
        try:
            payload = frozen_evaluate(sequence=paths, evaluator=evaluator, nav=window_nav,
                                      expected_nav_sha256=nav_sha, outdir=run_dir / "eval" / version, version=version,
                                      identity={"method_id": "LC02_GINAV", "run_id": run_dir.name},
                                      nav_input_root=run_dir / "eval" / f"{version}_NAV_INPUT",
                                      consistency_failure_policy="D12_BOUNDED_UNAVAILABLE", bounded_gate=gate)
        except (RuntimeError, ValueError) as exc:
            raise HardStop(f"frozen evaluator technical/identity failure ({version}) in {run_dir.name}: {exc}") from exc
        result[version] = payload["row"]
        result[f"{version}_audit"] = {k: payload["audit"].get(k) for k in
                                      ("passed", "technical_passed", "consistency_passed", "trace_open_count", "failures")}
    result["evaluation_status"] = "EVALUATED"
    return result


def evaluate_hartley(control: Control, roots: Roots, seq: hx02_sequence.HX02Sequence, runs: Mapping[str, Path]) -> dict[str, Any]:
    branches = {}
    for label, run_dir in runs.items():
        nav = run_dir / "native" / "run" / "NAV.csv"
        if nav.is_file():
            branches[label] = {"nav": str(nav), "nav_sha256": sha256_file(nav)}
    if "HARTLEY_S" not in branches:
        return {"evaluation_status": "UNAVAILABLE_PRIMARY_ALIGNMENT_BRANCH_HAS_NO_NAV", "branches": list(branches)}
    spec = {"sequence_id": seq.sequence_id, "base_time": seq.base_time, "window": list(seq.window),
            "baseline_median_m": seq.baseline_median_m, "trace": seq.trace_path_evaluator_only,
            "trace_sha256": seq.trace_sha256, "alignment_branch": "HARTLEY_S", "branches": branches}
    control.event("EVALUATOR_LAUNCH", run=runs["HARTLEY_S"].name, counters={"evaluator_calls": 1},
                  kind_detail="RELATIVE_POSE")
    try:
        result = hx02_evaluation_process.run_child("RELATIVE_POSE", spec,
                                                   workdir=runs["HARTLEY_S"] / "eval" / "RELATIVE_POSE",
                                                   code_root=roots.code, raw_root=roots.raw, clean_root=roots.clean,
                                                   trace=Path(seq.trace_path_evaluator_only))
    except hx02_evaluation_process.EvaluationProcessError as exc:
        raise HardStop(f"relative-pose evaluator technical/access failure: {exc}") from exc
    metrics = json.loads((Path(result["outdir"]) / "RELATIVE_POSE_METRICS.json").read_text(encoding="utf-8"))
    return {"evaluation_status": "EVALUATED", "metrics": metrics}


# --------------------------------------------------------------------------- archive
def archive_run(control: Control, roots: Roots, run_dir: Path) -> dict[str, Any]:
    """Copy one run to $HX02/RUNS with per-file SHA-256 verification, then delete the scratch copy.

    An archive interrupted before its manifest was written is completed in place:
    files already present with the source hash are kept, others are copied again.
    """
    destination = roots.stage / "RUNS" / run_dir.name
    if (destination / "ARCHIVE_MANIFEST.json").exists():
        raise HardStop(f"archive already sealed for a run still in scratch: {destination}")
    if destination.exists():
        control.event("ARCHIVE_RESUMED", run=run_dir.name)
    ledger_rows = []
    for source in sorted(run_dir.rglob("*")):
        if source.is_symlink():
            raise HardStop(f"symlink in run directory: {source}")
        if not source.is_file():
            continue
        target = destination / source.relative_to(run_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256_file(source)
        if target.is_file() and sha256_file(target) == digest:
            ledger_rows.append({"path": source.relative_to(run_dir).as_posix(), "sha256": digest,
                                "bytes": source.stat().st_size, "verified": True})
            continue
        for attempt in range(4):
            try:
                with source.open("rb") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                    dst.flush()
                    os.fsync(dst.fileno())
                if sha256_file(target) != digest:
                    raise OSError("archive SHA-256 mismatch")
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(2)
        ledger_rows.append({"path": source.relative_to(run_dir).as_posix(), "sha256": digest,
                            "bytes": source.stat().st_size, "verified": True})
    extra = sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*")
                   if path.is_file() and path.relative_to(destination).as_posix() not in
                   {row["path"] for row in ledger_rows})
    if extra:
        raise HardStop(f"archive destination holds files absent from the run directory: {extra[:5]}")
    manifest = {"run_id": run_dir.name, "file_count": len(ledger_rows), "bytes": sum(r["bytes"] for r in ledger_rows),
                "files": ledger_rows, "archived_utc": utc()}
    write_json(destination / "ARCHIVE_MANIFEST.json", manifest)
    for row in ledger_rows:
        if sha256_file(destination / row["path"]) != row["sha256"]:
            raise HardStop(f"archived file changed: {row['path']}")
    shutil.rmtree(run_dir)
    control.event("ARCHIVED", run=run_dir.name, state={"status": "ARCHIVED", "archive": str(destination)},
                  file_count=len(ledger_rows), bytes=manifest["bytes"])
    return manifest


# --------------------------------------------------------------------------- one run
def write_done(run_dir: Path, payload: Mapping[str, Any]) -> str:
    """DONE.json carries the provenance block, exit code and runner verdict from COMMAND.json."""
    command = json.loads((run_dir / "COMMAND.json").read_text(encoding="utf-8"))
    return write_json(run_dir / "DONE.json", {
        **payload, "native_classification": command.get("native_classification"),
        "runner_exit_code": command.get("returncode"), "runner_terminal_status": command.get("runner_terminal_status"),
        "provenance": command["provenance"], "utc": utc()})


def execute_native(control: Control, roots: Roots, seq: hx02_sequence.HX02Sequence, method: str,
                   pins: Mapping[str, Any], reference_echo: Mapping[str, Any]) -> dict[str, Any]:
    rid = run_id(seq.sequence_id, method)
    run_dir = roots.scratch / "RUNS" / rid
    if run_dir.exists():
        interrupted = roots.scratch / "INTERRUPTED" / f"{rid}.{int(time.time())}"
        interrupted.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(run_dir), str(interrupted))
        control.event("INTERRUPTED_RUN_PRESERVED", run=rid, preserved=str(interrupted))
    (run_dir / "native").mkdir(parents=True)
    (run_dir / "eval").mkdir()
    quiet = quiet_machine(control)
    control.event("NATIVE_LAUNCH", run=rid, state={"status": "NATIVE_RUNNING"}, counters={"native_calls": 1},
                  method=method, sequence=seq.sequence_id)
    commit = git_head(roots.code)
    try:
        if method in RUNNER_SCRIPTS:
            native = native_ext(roots, seq, method, run_dir, pins)
        elif method == "RTKLIB":
            native = native_rtklib(roots, seq, run_dir, pins)
        elif method.startswith("HARTLEY"):
            native = native_hartley(roots, seq, method, run_dir, pins)
        else:
            native = native_ginav(roots, seq, run_dir, pins)
    except HardStop:
        raise
    except Exception as exc:  # launcher/environment failure before a native result exists
        native = {"returncode": None, "native_complete": False, "environment_failure": True,
                  "error": f"{type(exc).__name__}: {exc}", "declared_raw": []}
    if method == "GINAV":
        ginav_run = native.get("ginav_run", {})
        # MATLAB could not be invoked or never reached the registered harness (no fopen ledger line).
        if "RUN_FAILED_ENVIRONMENT" in str(native.get("stderr_tail", "")) or (
                ginav_run and ginav_run.get("returncode") not in (0, None) and not ginav_run.get("fopen_ledger_lines")):
            native["environment_failure"] = True
    audit = {}
    strace_log = run_dir / "native" / "NATIVE_OPENAT.strace"
    if strace_log.is_file():
        audit = audit_native_strace(strace_log, roots, seq, native.get("declared_raw", []))
        write_json(run_dir / "native" / "NATIVE_ACCESS_AUDIT.json", audit)
    record_provenance = provenance(seq, code_commit=commit, old_runtime_input_count=audit.get("old_runtime_input_count"))
    status = classify(native)
    native["runner_terminal_status"] = runner_terminal_status(run_dir)
    command = {"run_id": rid, "method": method, "sequence": seq.sequence_id, "config": METHOD_CONFIG[method],
               "case": roots.contract["sequences"][seq.sequence_id]["case"], "code_commit": commit,
               "tracked_tree_clean": tracked_tree_clean(roots.code), "quiet_machine": quiet,
               "provenance": record_provenance, "native_classification": status,
               "runner_terminal_status": native["runner_terminal_status"],
               **{k: native.get(k) for k in ("argv", "strace_command_prefix", "cwd", "env_whitelist", "start_utc",
                                             "end_utc", "returncode", "runtime_seconds")}}
    write_json(run_dir / "COMMAND.json", command)
    if audit.get("reference_open_count"):
        raise HardStop(f"non-evaluator process opened a reference trajectory in {rid}: {audit['reference_open_lines'][:3]}")
    if audit.get("old_runtime_input_count"):
        raise HardStop(f"native process opened old runtime material in {rid}: {audit['old_runtime_input_paths'][:3]}")
    if method == "GINAV" and native.get("ginav_run", {}).get("native_pos"):
        ledger = run_dir / "native" / "GINAV_RUN" / "MATLAB_FOPEN_LEDGER.tsv"
        text = ledger.read_text(encoding="utf-8", errors="replace") if ledger.is_file() else ""
        hits = [line for line in text.splitlines() if REFERENCE_NAME.search(Path(line.split("\t")[-1].replace("\\", "/")).name)]
        if hits:
            raise HardStop(f"MATLAB opened a reference-like file in {rid}: {hits[:3]}")
    input_hashes = {"raw_lock": {"path": seq.raw_hash_lock, "sha256": seq.raw_hash_lock_sha256},
                    "raw_opened": audit.get("raw_paths_opened", []), "pins_sha256": sha256_file(roots.pins / "INPUT_PINS.json")}
    write_json(run_dir / "INPUT_HASHES.json", input_hashes)
    write_json(run_dir / "OUTPUT_HASHES.json", output_hashes(run_dir))
    record: dict[str, Any] = {"run_id": rid, "status": status, "native": native, "provenance": record_provenance,
                              "audit_summary": {k: audit.get(k) for k in (
                                  "reference_open_count", "undeclared_raw_paths", "old_runtime_input_count",
                                  "executed_programs")}}
    if status not in EVALUATED_STATUSES:
        failure = {"failure_classification": status, "returncode": native.get("returncode"),
                   "stderr_full_path": str(run_dir / "native" / "NATIVE_stderr.log"),
                   "stderr_tail": native.get("stderr_tail") or native.get("error"), "utc": utc(),
                   "provenance": record_provenance}
        write_json(run_dir / "FAILURE.json", failure)
        control.event("NATIVE_DONE", run=rid, state={"status": status, "native_complete": False})
        return record
    try:
        echo = params_echo(method, run_dir, roots, reference_echo[method])
    except Exception as exc:  # parameters cannot be verified -> registered stop, never skipped
        raise HardStop(f"parameter echo unreadable in {rid}: {type(exc).__name__}: {exc}") from exc
    write_json(run_dir / "PARAMS_ECHO.json", echo)
    if not echo["comparison"]["all_equal"]:
        raise HardStop(f"parameter echo differs from the registered reference in {rid}: {echo['comparison']['differing_items']}")
    control.event("NATIVE_DONE", run=rid, state={"status": "NATIVE_COMPLETED", "native_complete": True,
                                                  "native_classification": status})
    return record


def finish_heading_run(control: Control, roots: Roots, seq: hx02_sequence.HX02Sequence, method: str,
                       proxy: Mapping[int, float]) -> dict[str, Any]:
    rid = run_id(seq.sequence_id, method)
    run_dir = roots.scratch / "RUNS" / rid
    tables = heading_tables(method, run_dir, seq, {})
    diagnostics = {}
    for label, entry in tables.items():
        with open(entry["path"], newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        diagnostics[label] = hx02_convention.diagnose(rows, proxy)
    write_json(run_dir / "eval" / "CONVENTION_DIAGNOSTIC.json", diagnostics)
    if any(item.get("hard_stop") for item in diagnostics.values()):
        raise HardStop(f"convention diagnostic median near +/-90 or 180 deg in {rid}: {diagnostics}")
    metrics = evaluate_heading(control, roots, seq, method, run_dir, tables)
    done = {"run_id": rid, "status": "COMPLETED", "evaluation": "HEADING", "heading_tables": tables,
            "convention_diagnostic": diagnostics}
    write_done(run_dir, done)
    control.event("EVALUATED", run=rid, state={"status": "EVALUATED"})
    return metrics


PARTIAL_EVALUATION_OUTPUTS = ("eval", "DONE.json", "FAILURE.json", "native/HX02_HEADING_TABLES", "native/NAV")


def set_aside_partial_evaluation(control: Control, run_dir: Path) -> None:
    """A run found NATIVE_COMPLETED at controller start was interrupted after its native
    freeze; its partial evaluation outputs move to INTERRUPTED_EVALUATION_<ts>/ and the
    registered evaluation is run again (the native result is never rerun)."""
    stamp = str(int(time.time()))
    moved = []
    for relative in PARTIAL_EVALUATION_OUTPUTS:
        source = run_dir / relative
        if source.exists():
            target = run_dir / f"INTERRUPTED_EVALUATION_{stamp}" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            moved.append(relative)
    (run_dir / "eval").mkdir(exist_ok=True)
    control.event("PARTIAL_EVALUATION_SET_ASIDE", run=run_dir.name, moved=moved)


def run_batch(control: Control, roots: Roots, sequence_id: str, pins: Mapping[str, Any],
              reference_echo: Mapping[str, Any], resumed_native: frozenset[str] = frozenset()) -> None:
    seq = hx02_sequence.load_sequence(sequence_id, roots.contract)
    pending = [m for m in METHODS if control.status(run_id(sequence_id, m)) != "ARCHIVED"]
    if not pending:
        return
    disk_guard(control, roots, f"batch {sequence_id}")
    for method in METHODS:
        rid = run_id(sequence_id, method)
        if rid in resumed_native and control.status(rid) == "NATIVE_COMPLETED":
            set_aside_partial_evaluation(control, roots.scratch / "RUNS" / rid)
    proxy = None
    for method in METHODS:
        rid = run_id(sequence_id, method)
        if control.status(rid) in ("ARCHIVED", "EVALUATED", "FAILED_RECORDED"):
            continue
        run_dir = roots.scratch / "RUNS" / rid
        if control.status(rid) != "NATIVE_COMPLETED":
            record = execute_native(control, roots, seq, method, pins, reference_echo)
            if record["status"] not in EVALUATED_STATUSES:
                write_done(run_dir, {"run_id": rid, "status": record["status"], "evaluation": "NOT_RUN_NATIVE_FAILURE"})
                control.event("FAILURE_RECORDED", run=rid, state={"status": "FAILED_RECORDED", "failure": record["status"]})
                continue
        if method in ("EXT01", "EXT02", "EXT03", "EXT04", "RTKLIB"):
            if proxy is None:
                proxy = hx02_convention.proxy_body_yaw(seq)
            finish_heading_run(control, roots, seq, method, proxy)
        elif method == "GINAV":
            result = evaluate_ginav(control, roots, seq, run_dir)
            write_json(run_dir / "eval" / "GINAV_EVALUATION.json", result)
            write_done(run_dir, {"run_id": rid, "status": "COMPLETED", "evaluation": result.get("evaluation_status")})
            control.event("EVALUATED", run=rid, state={"status": "EVALUATED"})
        control.progress("CONTROLLER_SELF_AUDIT " + json.dumps(controller_self_audit(roots, f"after {rid}")))
    hartley_runs = {m: roots.scratch / "RUNS" / run_id(sequence_id, m) for m in ("HARTLEY_S", "HARTLEY_LIT")}
    states = {m: control.status(run_id(sequence_id, m)) for m in hartley_runs}
    if any(s in ("NATIVE_COMPLETED",) for s in states.values()):
        diverged = {}
        for method, run_dir in hartley_runs.items():
            nav = run_dir / "native" / "run" / "NAV.csv"
            if states[method] == "NATIVE_COMPLETED" and nav.is_file():
                gate = hx02_hartley.divergence_gate(nav)
                write_json(run_dir / "eval" / "DIVERGENCE_GATE.json", gate)
                if not gate["passed"]:
                    diverged[method] = gate
        usable = {m: d for m, d in hartley_runs.items() if states[m] == "NATIVE_COMPLETED" and m not in diverged}
        result = evaluate_hartley(control, roots, seq, usable) if "HARTLEY_S" in usable else {
            "evaluation_status": "UNAVAILABLE_PRIMARY_ALIGNMENT_BRANCH_NOT_USABLE", "diverged": list(diverged)}
        finalized = {}
        for method, run_dir in hartley_runs.items():
            if states[method] != "NATIVE_COMPLETED":
                continue
            status = "ALGORITHM_FAILURE_DIVERGED" if method in diverged else "COMPLETED"
            if method in diverged:
                write_json(run_dir / "FAILURE.json", {"failure_classification": status, "gate": diverged[method]})
            write_json(run_dir / "eval" / "RELATIVE_POSE_RESULT_POINTER.json",
                       {"evaluated_in": str(hartley_runs["HARTLEY_S"] / "eval" / "RELATIVE_POSE"),
                        "evaluation_status": result.get("evaluation_status")})
            write_done(run_dir, {"run_id": run_dir.name, "status": status, "evaluation": result.get("evaluation_status")})
            finalized[run_dir.name] = {"status": "EVALUATED"}
        # both branches become EVALUATED in one ledger line, so a resume never splits the pair
        control.event("EVALUATED_PAIR", runs_state=finalized)
    control.progress("CONTROLLER_SELF_AUDIT " + json.dumps(controller_self_audit(roots, f"before archive {sequence_id}")))
    disk_guard(control, roots, f"archive {sequence_id}")
    for method in METHODS:
        run_dir = roots.scratch / "RUNS" / run_id(sequence_id, method)
        if run_dir.is_dir() and control.status(run_dir.name) != "ARCHIVED":
            archive_run(control, roots, run_dir)


def frozen_code_check(roots: Roots) -> dict[str, str]:
    """Every file in the contract's frozen code list must still carry its registered SHA-256."""
    frozen = roots.contract.get("code_sha256") or {}
    if not frozen:
        raise HardStop("HX02_CONTRACT_V1 lacks the frozen code SHA-256 list")
    drift = sorted(rel for rel, digest in frozen.items() if sha256_file(roots.code / rel) != digest)
    if drift:
        raise HardStop(f"code differs from the frozen contract list: {drift}")
    return dict(frozen)


def run_all(roots: Roots) -> dict[str, Any]:
    control = Control(roots)
    control.event("CONTROLLER_START", code_commit=git_head(roots.code), tracked_tree_clean=tracked_tree_clean(roots.code))
    resumed_native = frozenset(rid for rid, entry in control.state["runs"].items()
                               if entry.get("status") == "NATIVE_COMPLETED")
    try:
        if not tracked_tree_clean(roots.code):
            raise HardStop("tracked worktree is not clean at execution (code freeze violated)")
        pins = load_pins(roots)
        reference_echo = json.loads((roots.pins / "PARAMS_ECHO_REFERENCE.json").read_text(encoding="utf-8"))
        if sha256_file(roots.pins / "PARAMS_ECHO_REFERENCE.json") != pins["params_echo_reference_sha256"]:
            raise HardStop("PARAMS_ECHO_REFERENCE.json differs from its pin")
        control.event("FROZEN_CODE_CHECK", files=len(frozen_code_check(roots)))
        control.event("CONTROLLER_SELF_AUDIT", **controller_self_audit(roots, "controller start"))
        disk_guard(control, roots, "controller start")
        for sequence_id in SEQUENCES:
            run_batch(control, roots, sequence_id, pins, reference_echo, resumed_native)
    except Exception as exc:
        registered = isinstance(exc, HardStop)
        reason = str(exc) if registered else f"CONTROLLER_TECHNICAL_FAILURE {type(exc).__name__}: {exc}"
        stop = roots.stage / "99_HARD_STOP"
        stop.mkdir(parents=True, exist_ok=True)
        write_json(stop / f"HARD_STOP_{int(time.time())}.json", {
            "utc": utc(), "reason": reason, "registered_hard_stop": registered,
            "traceback": traceback.format_exc(), "state": control.state})
        control.event("HARD_STOP", reason=reason)
        raise
    control.event("CONTROLLER_DONE", **controller_self_audit(roots, "controller end"))
    write_json(roots.control / "DONE.json", {"utc": utc(), **control.state}, exclusive=False)
    return control.state


# --------------------------------------------------------------------------- input pins (before the code freeze)
CLEAN4_REL = "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
PREPARE_SOURCES = tuple("src/legsa_gins/paper_rebuild/" + rel for rel in (
    "hext/hx02_sequence.py", "hext/hx02_hartley.py", "hext/hx02_ginav.py", "hext/hx02_params_echo.py",
    "horizontal_literature/ginav2021/imu_adapter.py",
    "horizontal_literature/hartley_h5.py", "horizontal_literature/shared_raw_backend.py"))
CLEAN4_HARTLEY = {"S": "07_LSE01_HARTLEY_CONTACT_INEKF/08_BY2_NATIVE/01_PRIMARY_GO2_ALLAN_EQ61_FK10MM/NATIVE_SUMMARY.json",
                  "LIT": "07_LSE01_HARTLEY_CONTACT_INEKF/08_BY2_NATIVE/04_PAPER_PROCESS_REGRESSION/NATIVE_SUMMARY.json"}
CLEAN4_GINAV_CONFIG = "11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4b/s/g3c/BY2_GINAV_SPP_LC.ini"
CLEAN4_RTKLIB_CONF = "04_EXT03_YANG2024/C00/POST_NATIVE/RTKLIB_UNMODIFIED_MOVING_BASE.conf"


def copy_verified(source: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(source)
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
        dst.flush()
        os.fsync(dst.fileno())
    if sha256_file(target) != digest:
        raise HardStop(f"pin copy differs: {target}")
    return digest


def prepare(roots: Roots) -> dict[str, Any]:
    """Input pins before the code-freeze commit: no solver, no evaluator, no reference."""
    pins_dir = roots.pins
    if (pins_dir / "INPUT_PINS.json").exists():
        raise HardStop("input pins already exist; never overwritten")
    prep = roots.scratch / "PREP"
    clean4 = roots.clean / CLEAN4_REL
    pins: dict[str, Any] = {"utc": utc(), "code_commit_at_prepare": git_head(roots.code), "pairing": {}, "go2": {},
                            "hartley": {}, "ginav": {}, "trace_sha256_registered": {},
                            "prepare_source_sha256": {rel: sha256_file(roots.code / rel) for rel in PREPARE_SOURCES}}
    for sequence_id in SEQUENCES:
        seq = hx02_sequence.load_sequence(sequence_id, roots.contract)
        pins["pairing"][sequence_id] = hx02_sequence.pairing_inventory(seq)
        if not pins["pairing"][sequence_id]["matches_registered_rawx_epochs"]:
            raise HardStop(f"{sequence_id} exact pairing differs from the registered RAWX epoch count")
        pins["go2"][sequence_id] = hx02_sequence.go2_prefix_inventory(seq)
        pins["trace_sha256_registered"][sequence_id] = {"path_alias": seq.trace_path_evaluator_only.replace(seq.raw_root, "<RAW_ROOT>"),
                                                        "sha256": seq.trace_sha256, "opened_by_prepare": False}
    build = hx02_hartley.build_runner(roots.code, roots.scratch / "BUILD" / "hartley_h5_runner")
    pins["hartley_runner"] = {"runner": build["runner"], "runner_sha256": build["runner_sha256"],
                              "pinned_copy_sha256": copy_verified(Path(build["runner"]), pins_dir / "HARTLEY" / "hartley_h5_runner"),
                              "build_logs": build["build_logs"]}
    for sequence_id in SEQUENCES:
        seq = hx02_sequence.load_sequence(sequence_id, roots.contract)
        manifest = hx02_hartley.build_cache(seq, pins["go2"][sequence_id], prep / "HARTLEY" / sequence_id)
        for name in ("H5_INPUT_CACHE.bin", "H5_INPUT_CONTACT_EVENT_LEDGER.jsonl", "H5_INPUT_CACHE_MANIFEST.json"):
            copy_verified(prep / "HARTLEY" / sequence_id / name, pins_dir / "HARTLEY" / sequence_id / name)
        pins["hartley"][sequence_id] = {k: manifest[k] for k in (
            "cache_sha256", "record_count", "first_timestamp_ns", "last_timestamp_ns", "event_ledger_sha256",
            "start_convention", "dt_seconds", "gaps_gt_0p1_s", "initial_add_event_count",
            "frozen_transition_event_count_excluding_initial_add")}
    template = pins_dir / "GINAV" / "BY2_GINAV_SPP_LC.ini"
    copy_verified(clean4 / CLEAN4_GINAV_CONFIG, template)
    local = yaml.safe_load(roots.paths_config.read_text(encoding="utf-8"))["paths"]
    for sequence_id in SEQUENCES:
        seq = hx02_sequence.load_sequence(sequence_id, roots.contract)
        work = prep / "GINAV" / sequence_id
        final = pins_dir / "GINAV" / sequence_id
        summary = hx02_ginav.prepare_inputs(seq, go2_inventory=pins["go2"][sequence_id], root=work,
                                            rtklib_root=Path(local["horizontal_literature_rtklib_root"]),
                                            convbin=Path(local["horizontal_literature_convbin"]), template=template,
                                            data_dir=final)
        copied = {}
        for source in sorted(work.rglob("*")):
            if source.is_file() and source.suffix != ".ubx":
                copied[source.relative_to(work).as_posix()] = copy_verified(source, final / source.relative_to(work))
        text = json.dumps(summary, sort_keys=True, default=str).replace(str(work), str(final))
        pinned = json.loads(text)
        (final / "GINAV_INPUT_PREPARATION.json").unlink()
        write_json(final / "GINAV_INPUT_PREPARATION.json", pinned)
        pins["ginav"][sequence_id] = {"files": copied, "config_sha256": pinned["config"]["config_sha256"],
                                      "replaced": pinned["config"]["replaced"], "overlap": pinned["overlap"],
                                      "unified_diff": pinned["config"]["unified_diff"]}
    pins["rtklib_conf_sha256"] = copy_verified(clean4 / CLEAN4_RTKLIB_CONF, pins_dir / "RTKLIB_UNMODIFIED_MOVING_BASE.conf")
    reference = {method: getattr(hx02_params_echo, method.lower())(clean4) for method in ("EXT01", "EXT02", "EXT03", "EXT04")}
    reference["HARTLEY_S"] = hx02_params_echo.hartley(clean4 / CLEAN4_HARTLEY["S"])
    reference["HARTLEY_LIT"] = hx02_params_echo.hartley(clean4 / CLEAN4_HARTLEY["LIT"])
    reference["GINAV"] = hx02_params_echo.ginav(template)
    reference["RTKLIB"] = hx02_params_echo.rtklib(pins_dir / "RTKLIB_UNMODIFIED_MOVING_BASE.conf")
    pins["params_echo_reference_sha256"] = write_json(pins_dir / "PARAMS_ECHO_REFERENCE.json", reference)
    evaluator = roots.clean / FROZEN_EVALUATOR_REL
    pins["frozen_evaluator"] = {"path_alias": "<CLEAN_ROOT>/" + FROZEN_EVALUATOR_REL, "sha256": sha256_file(evaluator)}
    if pins["frozen_evaluator"]["sha256"] != FROZEN_EVALUATOR_SHA256:
        raise HardStop("frozen evaluator identity mismatch")
    matlab = hx02_ginav.matlab_executable(roots.paths_config)
    pins["matlab"] = {"local_key": hx02_ginav.MATLAB_LOCAL_KEY, "path": str(matlab), "sha256": sha256_file(matlab)}
    if pins["matlab"]["sha256"] != hx02_ginav.MATLAB_SHA256:
        raise HardStop("MATLAB executable identity mismatch")
    pins["external_binaries"] = {name: sha256_file(Path(local[key])) for name, key in (
        ("convbin", "horizontal_literature_convbin"), ("rtklib_bridge", "horizontal_literature_rtklib_bridge"),
        ("lambda_library", "horizontal_literature_lambda_library"))}
    pins["external_binaries"]["rnx2rtkp"] = sha256_file(Path(local["horizontal_literature_rtklib_root"]) / "app/consapp/rnx2rtkp/gcc/rnx2rtkp")
    write_json(pins_dir / "INPUT_PINS.json", pins)
    return pins
