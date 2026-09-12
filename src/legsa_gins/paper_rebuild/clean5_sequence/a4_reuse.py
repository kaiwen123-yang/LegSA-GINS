"""Reuse the exact sealed A.4 PASS only with unchanged validation dependencies."""
from pathlib import Path
import subprocess
from ..manifest import sha256_file
from .io_audit import audited_open_records
from .revalidation import _read, _record_hashes

VALIDATED_COMMIT = "ebff9aeb3fff2fd5aff7cce39c2f05c96bac7b30"
PINNED_FILES = {
    "REVALIDATION_GATE.json": "de25fca5211cf90060262ef71a66c459e810da008b1312bf68773177326319ff",
    "REVALIDATION_RESULT.json": "e851da021c4b4e3b96868a98ba5c07896e2f94991458d965b265105c0b39047f",
    "REVALIDATION_STRACE_AUDIT.json": "8f2c7d4669f6cff6e97f43c05a0c7ecd5e91da137ef35833ec2427420585628a",
    "REVALIDATION_OPENAT.strace": "73712385fc96be8b0810612df335524f91ad1241407af17b2536a00c1a4ed817",
}
MARKER_SHA256 = "f90d220e41e675e1b45d254adc7925d09743eee545a25af3c24f876ded38798b"
LOCAL_PATHS = "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
LOCAL_PATHS_SHA256 = "074af751f2d1af1456af6f2ab590e1dcb573544d6c7d33a56b591347c2a160e1"
REQUIRED_MODULES = {"clean5_sequence/" + name + ".py" for name in (
    "solver_validation", "profile_expectations", "io_audit", "revalidation", "solver_runner", "solver_seal",
    "runtime_config", "generation_audit", "registry")}
REQUIRED_MODULES.update(name + ".py" for name in (
    "evidence", "manifest", "paths", "subprocess_guard", "final_v23_clean_parity"))


def verify_source_files(root, relative_paths):
    from hashlib import sha256
    identities = {}
    for relative in sorted(relative_paths):
        path = Path(root)/relative
        expected = subprocess.check_output(["git", "show", VALIDATED_COMMIT+":"+relative], cwd=root)
        if path.is_symlink() or path.read_bytes() != expected:
            raise RuntimeError("A.4 validation dependency changed: " + relative)
        identities[relative] = sha256(expected).hexdigest()
    return identities


def reuse_gate(registry, current_commit):
    root = registry.clean_root/"stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/00_C04B_REVALIDATION_V2"
    references = {}
    for name, expected in PINNED_FILES.items():
        path = root/name
        if path.is_symlink() or sha256_file(path) != expected:
            raise RuntimeError("Pinned A.4 evidence changed: " + name)
        references[name] = {"path": str(path), "sha256": expected}
    gate, result = _read(root/"REVALIDATION_GATE.json"), _read(root/"REVALIDATION_RESULT.json")
    from .runtime_config import METHODS
    expected_ids = {f"{ds}_{method}_{profile}" for ds in ("BY2H", "BY2O") for method,profile in METHODS.items()}
    rows = result.get("runs", [])
    if (gate.get("passed") is not True or gate.get("worker_exit_code") != 0
            or gate.get("code_freeze_commit") != VALIDATED_COMMIT or result.get("code_freeze_commit") != VALIDATED_COMMIT
            or result.get("passed") is not True or result.get("passed_run_count") != 10 or len(rows) != 10
            or {row.get("run_id") for row in rows} != expected_ids
            or any(row.get("passed") is not True or row.get("terminal_status") != "COMPLETED" for row in rows)
            or gate.get("strace_audit", {}).get("pass") is not True):
        raise RuntimeError("Pinned A.4 gate is not ten completed PASS results")
    required = {"src/legsa_gins/paper_rebuild/"+name for name in REQUIRED_MODULES}
    verify_source_files(registry.code_root, required)
    original_root = Path(result["code_root"])
    tracked = set(subprocess.check_output(["git","ls-tree","-r","--name-only",VALIDATED_COMMIT],cwd=registry.code_root,text=True).splitlines())
    opened = audited_open_records(root/"REVALIDATION_OPENAT.strace", original_root)
    for row in opened:
        path = Path(row["path"])
        if path.suffix == ".pyc" and original_root in path.parents:
            from importlib.util import source_from_cache
            path = Path(source_from_cache(str(path)))
        if path.suffix in {".py", ".yaml"} and original_root in path.parents:
            relative = path.relative_to(original_root).as_posix()
            if relative == LOCAL_PATHS:
                if sha256_file(registry.code_root/relative) != LOCAL_PATHS_SHA256:
                    raise RuntimeError("A.4 original local paths configuration changed")
            elif relative not in tracked:
                raise RuntimeError("A.4 loaded an untracked project dependency: " + relative)
            else:
                required.add(relative)
    identities = verify_source_files(registry.code_root, required)
    seals, markers = {}, {}
    recorded = _record_hashes(registry.code_root)
    for dataset in ("BY2H", "BY2O"):
        stage = registry.clean_root/"stages"/registry.sequences[dataset].stage_id
        for name in ("OUTPUT_SEAL.json", "SEAL_GATE.json"):
            path = stage/"05_OUTPUT_SEAL"/name
            alias = "<CLEAN_ROOT>/"+path.relative_to(registry.clean_root).as_posix()
            if sha256_file(path) != recorded[alias]:
                raise RuntimeError("Original v1 seal metadata changed")
            seals[alias] = recorded[alias]
        for folder in ("04_SOLVER_RUNS", "05_OUTPUT_SEAL"):
            path = stage/folder/"SUPERSEDED.json"
            if sha256_file(path) != MARKER_SHA256:
                raise RuntimeError("Authorized v1 superseded marker changed")
            markers["<CLEAN_ROOT>/"+path.relative_to(registry.clean_root).as_posix()] = MARKER_SHA256
    return {"passed": True, "status": "PASS_REUSE_UNCHANGED_A4_VALIDATORS", "passed_run_count": 10,
        "validated_code_commit": VALIDATED_COMMIT, "current_event_code_commit": current_commit,
        "references": references, "validation_source_hashes": identities,
        "original_local_paths_sha256": LOCAL_PATHS_SHA256,
        "original_seal_hashes": seals, "superseded_marker_hashes": markers,
        "solver_execution_count": 0, "revalidation_execution_count": 0, "trace_content_read": False}
