#!/usr/bin/env python3
"""Inventory and selectively recover the authorized final_v23 archive.

This entrypoint is deliberately recovery-only.  It never executes an archived
program, never uses an archived runtime payload as solver input, and writes only
below the clean recovery/log roots derived from the ignored local path config.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.evidence import verify_by2_raw_22
from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.paths import load_clean_paths


STAGE_ID = "CLEAN1R2_FINAL_V23_ARCHIVE_PARITY_AND_FOUR_METHOD_REEXECUTION"
RECOVERY_DIR = "16_FINAL_V23_ARCHIVE_RECOVERY"
LOG_DIR = "17_LOGS/CLEAN1R2_FINAL_V23_ARCHIVE_RECOVERY"
ARCHIVE_SHA256 = "45953164c53e102a4ce7e99912535b484d60420ef0de20466252446f3d76b716"
RAW_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"

CORE_ROLE_BY_NAME = {
    "process_data.py": "process_data",
    "run_final_mainline.py": "run_final_mainline",
    "final_mainline_config.md": "final_mainline_config",
    "evaluate_nav_trace_kfgins_v2.py": "evaluator",
}

SOLVER_SOURCE_NAMES = frozenset(
    {
        "gi_engine.cpp",
        "gi_engine.cc",
        "gi_engine.h",
        "gi_engine.hpp",
        "options.h",
        "options.hpp",
        "insmech.cpp",
        "insmech.cc",
        "insmech.h",
        "insmech.hpp",
        "file_saver.cpp",
        "file_saver.cc",
        "file_saver.h",
        "file_saver.hpp",
        "filesaver.cpp",
        "filesaver.cc",
        "filesaver.h",
        "filesaver.hpp",
    }
)

PARITY_NAMES = frozenset(
    {
        "test1.imu",
        "test1.gnss",
        "kf_gins_navresult.nav",
        "kf_gins_std.txt",
        "kf_gins_imu_err.txt",
        "error_series.csv",
        "summary.json",
        "case_review.json",
        "case_review.md",
    }
)

SOURCE_LINKED_EXACT_NORMAL_PREFIX = (
    "毕业设计-足式机器人双天线北斗RTK 惯导定位定姿算法研究/毕设数据/"
    "extended_degradation_results/final_v23/single/E001_single_nominal_none/"
)
SOURCE_LINKED_STATIC_NAMES = frozenset({"kf-gins.yaml", "run_meta.json"})
SOURCE_LINKED_PARITY_NAMES = frozenset(
    {
        "input.gnss",
        "KF_GINS_Navresult.nav",
        "KF_GINS_STD.txt",
        "error_series.csv",
        "summary.json",
        "report.txt",
        "run.log",
    }
)
SOURCE_LINKED_CASE_REVIEW_REFERENCES = frozenset(
    {
        "input.gnss",
        "KF_GINS_Navresult.nav",
        "KF_GINS_STD.txt",
        "error_series.csv",
        "summary.json",
    }
)

EXCLUDED_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("V2.4_QUALITY_MANAGER", ("quality_manager", "quality-manager", "v24_", "v2.4")),
    ("V3_FOOT_AWARE", ("foot_aware", "foot-aware", "v30_", "v31_")),
    ("V4", ("v4_tc", "/v4/", "_v4_", "engine_v4")),
    ("QA", ("qa_fallback", "qa-fallback", "qafallback")),
    ("FGO", ("/fgo/", "_fgo", "fgo_", "oig_fgtc", "oigfgtc")),
    (
        "NOISE_INJECTION_OR_DEGRADATION",
        (
            "/v2验证/",
            "ablation",
            "traceyaw",
            "statusyaw",
            "status_yawstd",
            "pos_spike",
            "outlier",
            "outage",
            "noise_inject",
            "injected_noise",
            "inject_noise",
            "injection",
            "semi_physical",
            "semiphysical",
            "semisynthetic",
            "degradation",
            "degraded_",
            "mild_additive",
            "suspicious_only",
            "野值",
            "断联",
            "噪声",
            "tmp_single_antenna_compare/runs/",
            "single_antenna_compare/runs/",
            "attitude_feasibility_sweep",
            "parameter_sweep",
            "/sweeps/",
        ),
    ),
    ("SYNTHETIC", ("synthetic", "simulated_noise")),
    ("RECONSTRUCTED_OR_CHAT_DERIVED", ("/reconstructed/", "_codex_revision_work")),
)

OUTPUT_SUFFIXES = (
    ".nav",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
)
SOURCE_SUFFIXES = (".py", ".cpp", ".cc", ".c", ".hpp", ".h")
CONFIG_SUFFIXES = (".yaml", ".yml", ".conf", ".ini", ".toml")
NESTED_ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz", ".tar.xz")


class RecoveryError(RuntimeError):
    """Fail-closed archive recovery error."""


def _absolute_lexical(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _lexically_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def lstat_no_symlink_chain(
    path: str | Path,
    *,
    role: str,
    must_exist: bool = False,
) -> Path:
    """Walk every existing component with lstat and reject symlinks."""

    candidate = _absolute_lexical(path)
    current = Path(candidate.anchor)
    missing_seen = False
    for component in candidate.parts[1:]:
        current = current / component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            missing_seen = True
            continue
        if missing_seen:
            raise RecoveryError(f"{role} changed while its path chain was inspected")
        if stat.S_ISLNK(metadata.st_mode):
            raise RecoveryError(f"{role} contains a symlink component: {current}")
        if current != candidate and not stat.S_ISDIR(metadata.st_mode):
            raise RecoveryError(f"{role} has a non-directory parent component: {current}")
    if must_exist and missing_seen:
        raise RecoveryError(f"{role} does not exist")
    return candidate


def lstat_confined_path(
    path: str | Path,
    *,
    allowed_root: str | Path,
    role: str,
    must_exist: bool = False,
) -> Path:
    """Reject parent symlinks and prove lexical plus realpath confinement."""

    root = lstat_no_symlink_chain(allowed_root, role=f"{role} allowed root", must_exist=True)
    candidate = lstat_no_symlink_chain(path, role=role, must_exist=must_exist)
    if not _lexically_within(candidate, root):
        raise RecoveryError(f"{role} is lexically outside its allowed root")
    real_root = root.resolve(strict=True)
    nearest = candidate
    while not os.path.lexists(nearest):
        if nearest == nearest.parent:
            raise RecoveryError(f"{role} has no existing confined parent")
        nearest = nearest.parent
    real_nearest = nearest.resolve(strict=True)
    if not _lexically_within(real_nearest, real_root):
        raise RecoveryError(f"{role} realpath escapes its allowed root")
    if os.path.lexists(candidate):
        real_candidate = candidate.resolve(strict=True)
        if not _lexically_within(real_candidate, real_root):
            raise RecoveryError(f"{role} resolved path escapes its allowed root")
    return candidate


def _fsync_directory(path: Path) -> None:
    lstat_no_symlink_chain(path, role="fsync directory", must_exist=True)
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_text(path: Path, text: str) -> None:
    path = lstat_no_symlink_chain(path, role="atomic output", must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    lstat_no_symlink_chain(path.parent, role="atomic output parent", must_exist=True)
    if os.path.lexists(path):
        existing = os.lstat(path)
        if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode):
            raise RecoveryError(f"atomic output destination is not a regular file: {path}")
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def atomic_write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_member_name(name: str) -> tuple[bool, str]:
    """Reject traversal, absolute, drive-qualified, NUL, and backslash paths."""

    if not name:
        return False, "empty_member_name"
    if "\x00" in name:
        return False, "nul_in_member_name"
    if "\\" in name:
        return False, "backslash_in_member_name"
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return False, "absolute_or_drive_member_name"
    raw_parts = name.rstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        return False, "dot_or_empty_member_component"
    pure = PurePosixPath(name.rstrip("/"))
    if pure.is_absolute() or ".." in pure.parts:
        return False, "path_traversal"
    return True, ""


def zipinfo_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def compound_extension(name: str) -> str:
    lowered = name.casefold().rstrip("/")
    for suffix in sorted(NESTED_ARCHIVE_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(suffix):
            return suffix
    return Path(lowered).suffix


def excluded_branch(name: str) -> str:
    lowered = "/" + name.casefold().lstrip("/")
    for label, markers in EXCLUDED_MARKERS:
        if any(marker in lowered for marker in markers):
            return label
    return ""


def historical_performance_root(name: str) -> bool:
    lowered = "/" + name.casefold().lstrip("/")
    return any(
        marker in lowered
        for marker in (
            "/generated_results/",
            "/final_results/",
            "/single_antenna_compare/",
            "/tmp_single_antenna_compare/",
            "/绘图/",
            "/plots/",
            "/figures/",
            "/ppt/",
            "_ppt/",
            "summary_panel",
            "_final_v23_only_audit",
        )
    )


def contract_linked(name: str) -> bool:
    lowered = name.casefold()
    return any(
        marker in lowered
        for marker in ("final_v23", "final-v23", "finalv23", "mainline", "nominal_none", "n4h2d", "n4h4r3")
    )


def exact_normal_runtime_config(name: str) -> bool:
    lowered = name.casefold().replace("\\", "/").lstrip("/")
    archived_runtime = "毕设数据/资料补齐_算法讲解/03_final_yaml/originals/final_v23_runtime.yaml"
    return (
        lowered == "kf-gins/config/kf-gins.yaml"
        or lowered == archived_runtime
        or lowered.endswith("/" + archived_runtime)
    )


def exact_normal_runtime_manifest(name: str) -> bool:
    lowered = name.casefold().replace("\\", "/")
    basename = PurePosixPath(lowered).name
    return "/nominal_none/" in lowered and basename in {
        "run_manifest.json",
        "runtime_manifest.json",
        "run_meta.json",
    }


def source_linked_exact_normal_role(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    if not normalized.startswith(SOURCE_LINKED_EXACT_NORMAL_PREFIX):
        return None
    relative = normalized[len(SOURCE_LINKED_EXACT_NORMAL_PREFIX) :]
    if not relative or "/" in relative:
        return "source_linked_unlisted"
    if relative == "kf-gins.yaml":
        return "source_linked_runtime_config"
    if relative == "run_meta.json":
        return "source_linked_runtime_manifest"
    if relative in SOURCE_LINKED_PARITY_NAMES:
        return "source_linked_parity_reference"
    return "source_linked_unlisted"


def canonical_spec_doc(name: str) -> bool:
    lowered = name.casefold().lstrip("/")
    in_canonical_docs = lowered.startswith("kf-gins/docs/") or "/kf-gins/docs/" in lowered
    basename = PurePosixPath(name).name.casefold()
    source_linked_name = any(marker in basename for marker in ("contract", "config", "protocol", "source"))
    return in_canonical_docs or (contract_linked(name) and source_linked_name)


def canonical_solver_source(name: str) -> bool:
    lowered = "/" + name.casefold().lstrip("/")
    return any(
        marker in lowered
        for marker in (
            "/kf-gins/src/kf-gins/",
            "/kf-gins-baseline/src/kf-gins/",
            "/kf-gins/src/fileio/",
            "/kf-gins-baseline/src/fileio/",
        )
    )


def canonical_archived_parity_input(name: str) -> bool:
    lowered = name.casefold().replace("\\", "/")
    return lowered.endswith(
        (
            "/毕设数据/2026.3.6-测试数据/高层数据/test1.imu",
            "/毕设数据/2026.3.6-测试数据/高层数据/test1.gnss",
        )
    )


def generated_environment_or_build_output(name: str) -> bool:
    lowered = "/" + name.casefold().lstrip("/")
    return any(
        marker in lowered
        for marker in ("/.venv/", "/site-packages/", "/__pycache__/", "/build/")
    )


def candidate_role(info: zipfile.ZipInfo) -> tuple[str, str]:
    name = info.filename
    lowered = name.casefold()
    basename = PurePosixPath(name.rstrip("/")).name.casefold()
    safe, unsafe_reason = safe_member_name(name)
    if not safe:
        return "unsafe_member", unsafe_reason
    if zipinfo_is_symlink(info):
        return "archive_symlink", "symlink member is never extracted"
    if info.is_dir():
        return "directory", "directory metadata"
    source_linked_role = source_linked_exact_normal_role(name)
    if source_linked_role is not None:
        if source_linked_role == "source_linked_unlisted":
            return source_linked_role, "unlisted member under the bounded source-linked prefix"
        return source_linked_role, "exact source-linked clean-normal exception"
    excluded = excluded_branch(name)
    if excluded:
        return "excluded_branch", excluded
    extension = compound_extension(name)
    if extension in NESTED_ARCHIVE_SUFFIXES and (
        basename in {"nominal_none.zip", "绘图验证.zip"}
        or any(
            marker in lowered
            for marker in ("n4h2d", "n4h4r3", "final_v23", "final-v23", "finalv23", "mainline")
        )
    ):
        return "named_reference_archive", "requested named parity/provenance archive"
    if extension in NESTED_ARCHIVE_SUFFIXES:
        return "nested_archive", "nested archive inventory candidate"
    if generated_environment_or_build_output(name):
        return "environment_or_build_output", "generated environment/package/build output is not archive specification"
    if basename in CORE_ROLE_BY_NAME:
        return f"exact_{CORE_ROLE_BY_NAME[basename]}", "required final_v23 core role"
    if basename in SOLVER_SOURCE_NAMES and canonical_solver_source(name):
        return "solver_source_core", "requested solver, mechanization, or writer source"
    if basename == "cmakelists.txt":
        return "build_spec", "build specification"
    if basename in {"packed-refs", "head"} and "/.git/" in lowered:
        return "git_provenance", "embedded Git provenance metadata"
    if "/.git/refs/tags/" in lowered and "final" in basename:
        return "git_provenance", "embedded final freeze tag reference"
    # Historical inputs/outputs must never be promoted to static specification
    # merely because their parent path includes final_v23 or mainline.
    if basename in PARITY_NAMES:
        if (
            "/dataset/" in lowered
            or "/nominal_none/" in lowered
            or canonical_archived_parity_input(name)
        ):
            return "parity_reference", "historical input/output retained only for parity comparison"
        return "historical_result", "historical result not selected as the normal parity reference"
    if exact_normal_runtime_manifest(name):
        return "runtime_manifest", "contract-linked same-run metadata candidate"
    if "manifest" in basename and extension in {".json", ".yaml", ".yml", ".csv", ".txt"}:
        return "non_normal_runtime_manifest", "manifest is outside the exact-normal allowlist"
    if historical_performance_root(name) and extension in {
        ".md",
        ".txt",
        ".json",
        ".csv",
        ".yaml",
        ".yml",
    }:
        if contract_linked(name):
            return "historical_result", "historical performance/audit report retained only as parity reference"
        return "generated_performance_report", "generated performance material denied as active evidence"
    if extension in {".yaml", ".yml", ".conf"} and exact_normal_runtime_config(name):
        return "runtime_config", "contract-linked runtime configuration candidate"
    if basename.startswith("kf-gins") and extension in CONFIG_SUFFIXES:
        return "non_normal_runtime_config", "KF-GINS config is outside the exact-normal allowlist"
    if extension == ".conf":
        return "non_normal_runtime_config", "runtime config is outside the exact-normal allowlist"
    if contract_linked(name) and extension in {".md", ".txt"} and canonical_spec_doc(name):
        return "final_v23_note", "final_v23 or mainline specification note"
    if basename.startswith("readme") and extension in {".md", ".txt"}:
        return "readme", "static documentation"
    if extension in SOURCE_SUFFIXES:
        return "generic_static_source", "static source; not automatically selected as exact final_v23"
    if extension in CONFIG_SUFFIXES:
        return "generic_static_config", "static configuration; not automatically selected"
    if basename in {"summary.json", "case_review.json", "case_review.md", "error_series.csv"}:
        return "historical_result", "historical result retained only as non-active reference"
    if lowered.endswith(OUTPUT_SUFFIXES) or basename in {"kf_gins_std.txt", "kf_gins_imu_err.txt"}:
        return "historical_result", "historical output is denied as active evidence"
    return "other", "not selected for final_v23 contract recovery"


def evidence_classification(role: str) -> tuple[str, str]:
    if role.startswith("exact_") or role in {
        "solver_source_core",
        "build_spec",
        "git_provenance",
        "runtime_config",
        "runtime_manifest",
        "source_linked_runtime_config",
        "source_linked_runtime_manifest",
        "final_v23_note",
        "readme",
        "generic_static_source",
        "generic_static_config",
    }:
        return "MIGRATABLE_STATIC_SPECIFICATION", "static only; selection still requires source identity proof"
    if role in {
        "parity_reference",
        "historical_result",
        "named_reference_archive",
        "source_linked_parity_reference",
    }:
        return "PARITY_REFERENCE_ONLY", "never eligible as fresh solver input or current performance evidence"
    return "DENIED_AS_ACTIVE_EVIDENCE", "not an eligible active-evidence source"


def should_extract(row: Mapping[str, Any]) -> bool:
    role = str(row["candidate_role"])
    size = int(row["member_size"])
    name = str(row["archive_member"])
    lowered = name.casefold()
    if row["safe_member"] is not True or row["symlink_member"] is True:
        return False
    if role.startswith("exact_"):
        return size <= 20 * 1024 * 1024
    if role in {"solver_source_core", "runtime_config", "final_v23_note", "git_provenance"}:
        return size <= 20 * 1024 * 1024
    if role in {
        "source_linked_runtime_config",
        "source_linked_runtime_manifest",
        "source_linked_parity_reference",
    }:
        return size <= 100 * 1024 * 1024
    if role == "build_spec":
        lowered_name = name.casefold().lstrip("/")
        return lowered_name in {"kf-gins/cmakelists.txt", "kf-gins-baseline/cmakelists.txt"}
    if role == "runtime_manifest":
        return size <= 20 * 1024 * 1024 and any(
            marker in lowered for marker in ("final", "mainline", "nominal", "dataset", "runtime", "run")
        )
    if role == "readme":
        return len(PurePosixPath(name).parts) <= 3
    if role == "parity_reference":
        return size <= 5 * 1024 * 1024 * 1024
    if role == "historical_result":
        normalized = "/" + name.casefold().replace("\\", "/").lstrip("/")
        return (
            size <= 100 * 1024 * 1024
            and (normalized.startswith("/nominal_none/") or "/nominal_none/" in normalized)
            and not historical_performance_root(name)
        )
    if role == "named_reference_archive":
        # ZIPs are already copied once, CRC-checked, and recursively inventoried
        # by the nested-archive path.  Avoid a second multi-GB copy here.
        return compound_extension(name) != ".zip" and size <= 40 * 1024 * 1024 * 1024
    return False


def should_recurse_nested_zip(name: str, *, depth: int, main_archive_basename: str) -> bool:
    """Bound recursion to the authorized full snapshot and named contract ZIPs."""

    basename = PurePosixPath(name).name
    if depth == 0:
        return basename == main_archive_basename
    lowered = name.casefold()
    return basename.casefold() in {"nominal_none.zip", "绘图验证.zip"} or any(
        marker in lowered
        for marker in ("n4h2d", "n4h4r3", "final_v23", "final-v23", "finalv23", "mainline")
    )


def copy_zip_member_atomic(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    destination: Path,
    *,
    allowed_root: Path,
) -> tuple[str, int]:
    safe, reason = safe_member_name(info.filename)
    if not safe:
        raise RecoveryError(f"Unsafe archive member cannot be extracted: {reason}: {info.filename!r}")
    if info.is_dir() or zipinfo_is_symlink(info):
        raise RecoveryError(f"Non-regular archive member cannot be extracted: {info.filename!r}")
    destination = lstat_confined_path(
        destination,
        allowed_root=allowed_root,
        role="archive extraction destination",
        must_exist=False,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    lstat_confined_path(
        destination.parent,
        allowed_root=allowed_root,
        role="archive extraction destination parent",
        must_exist=True,
    )
    if os.path.lexists(destination):
        existing = os.lstat(destination)
        if stat.S_ISLNK(existing.st_mode) or not stat.S_ISREG(existing.st_mode):
            raise RecoveryError(f"Recovery destination is not a regular file: {destination}")
    descriptor, temporary = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
    digest = hashlib.sha256()
    copied = 0
    try:
        with os.fdopen(descriptor, "wb") as output, archive.open(info, "r") as source:
            while True:
                chunk = source.read(8 * 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                copied += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        if copied != info.file_size:
            raise RecoveryError(
                f"Extracted size mismatch for {info.filename!r}: expected={info.file_size}, actual={copied}"
            )
        os.chmod(temporary, 0o444)
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return digest.hexdigest(), copied


def container_key(identity: str) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    if identity == "MAIN":
        return "MAIN"
    return f"NESTED_{digest}"


def preferred_candidate(row: Mapping[str, Any]) -> tuple[int, int, str]:
    name = str(row["archive_member"])
    canonical = {
        "KF-GINS/bin/process_data.py",
        "KF-GINS/scripts/run_final_mainline.py",
        "KF-GINS/docs/final_mainline_config.md",
        "KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py",
    }
    return (0 if name in canonical else 1, int(row["depth"]), str(row["qualified_member"]))


def build_source_map(extracted_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    output: list[dict[str, Any]] = []
    markdown = [
        "# FINAL_V23 Archive Source Map",
        "",
        "This is an initial identity map. Distinct content hashes remain unselected until runtime linkage closes the conflict.",
        "",
        "| logical role | candidates | distinct hashes | selected | resolution |",
        "|---|---:|---:|---|---|",
    ]
    for logical_role in ("process_data", "run_final_mainline", "final_mainline_config", "evaluator"):
        role = f"exact_{logical_role}"
        candidates = [dict(row) for row in extracted_rows if row["candidate_role"] == role]
        hashes = {str(row["sha256"]) for row in candidates}
        selected_identity = ""
        resolution = "MISSING_REQUIRED_ROLE"
        selection_reason = "No candidate was recovered"
        if candidates and len(hashes) == 1:
            selected = min(candidates, key=preferred_candidate)
            selected_identity = str(selected["qualified_member"])
            resolution = "UNIQUE_CONTENT_IDENTITY"
            selection_reason = (
                "Only one content hash exists; duplicate containers, if any, are byte-identical. "
                "The canonical shallow path is preferred."
            )
        elif candidates:
            resolution = "UNRESOLVED_DISTINCT_SHA256"
            selection_reason = "Multiple distinct content hashes require runtime/config linkage; none selected"
        conflict_candidates = json.dumps(
            [
                {
                    "qualified_member": row["qualified_member"],
                    "sha256": row["sha256"],
                    "mtime": row["mtime"],
                }
                for row in sorted(candidates, key=lambda item: str(item["qualified_member"]))
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        if not candidates:
            output.append(
                {
                    "logical_role": logical_role,
                    "archive_member": "MISSING",
                    "sha256": "MISSING",
                    "source_type": "MISSING",
                    "selected": False,
                    "selection_reason": selection_reason,
                    "conflict_candidates": conflict_candidates,
                    "conflict_resolution": resolution,
                }
            )
        else:
            for row in sorted(candidates, key=preferred_candidate):
                output.append(
                    {
                        "logical_role": logical_role,
                        "archive_member": row["qualified_member"],
                        "sha256": row["sha256"],
                        "source_type": "archive_static_" + logical_role,
                        "selected": row["qualified_member"] == selected_identity,
                        "selection_reason": selection_reason,
                        "conflict_candidates": conflict_candidates,
                        "conflict_resolution": resolution,
                    }
                )
        markdown.append(
            f"| `{logical_role}` | {len(candidates)} | {len(hashes)} | "
            f"`{selected_identity or 'NONE'}` | `{resolution}` |"
        )
    markdown.extend(
        [
            "",
            "Selected means byte identity is unique for this role. It does not by itself prove same-run runtime linkage.",
            "",
        ]
    )
    return output, "\n".join(markdown)


def selected_extraction_qa(
    extracted_rows: Sequence[Mapping[str, Any]],
    inventory_rows: Sequence[Mapping[str, Any]],
    recovery_root: Path,
) -> dict[str, Any]:
    role_counts = Counter(str(row["candidate_role"]) for row in extracted_rows)
    role_bytes = Counter()
    for row in extracted_rows:
        role_bytes[str(row["candidate_role"])] += int(row["member_size"])
    core_rows = [row for row in extracted_rows if row["candidate_role"] == "solver_source_core"]
    noncanonical_core = [
        str(row["qualified_member"])
        for row in core_rows
        if not canonical_solver_source(str(row["archive_member"]))
    ]
    historical_static_misclassifications = [
        str(row["qualified_member"])
        for row in inventory_rows
        if historical_performance_root(str(row["archive_member"]))
        and row["evidence_classification"] == "MIGRATABLE_STATIC_SPECIFICATION"
        and row["candidate_role"] != "runtime_manifest"
    ]
    misclassified_degradation = [
        str(row["qualified_member"])
        for row in inventory_rows
        if excluded_branch(str(row["archive_member"])) == "NOISE_INJECTION_OR_DEGRADATION"
        and row["evidence_classification"] != "DENIED_AS_ACTIVE_EVIDENCE"
        and source_linked_exact_normal_role(str(row["archive_member"]))
        not in {
            "source_linked_runtime_config",
            "source_linked_runtime_manifest",
            "source_linked_parity_reference",
        }
    ]
    selected_degradation = [
        row
        for row in extracted_rows
        if excluded_branch(str(row["archive_member"])) == "NOISE_INJECTION_OR_DEGRADATION"
    ]
    selected_degradation_exception = [
        row
        for row in selected_degradation
        if source_linked_exact_normal_role(str(row["archive_member"]))
        in {
            "source_linked_runtime_config",
            "source_linked_runtime_manifest",
            "source_linked_parity_reference",
        }
    ]
    unexpected_selected_degradation = [
        str(row["qualified_member"])
        for row in selected_degradation
        if row not in selected_degradation_exception
    ]
    selected_runtime_configs = [
        str(row["archive_member"])
        for row in extracted_rows
        if row["candidate_role"] in {"runtime_config", "source_linked_runtime_config"}
    ]
    unexpected_runtime_configs = [
        name
        for name in selected_runtime_configs
        if not exact_normal_runtime_config(name)
        and source_linked_exact_normal_role(name) != "source_linked_runtime_config"
    ]
    unsafe_extractions = [
        str(row["qualified_member"])
        for row in extracted_rows
        if row.get("safe_member") is not True or row.get("symlink_member") is True
    ]
    v2_validation_configs = [
        row
        for row in inventory_rows
        if "/v2验证/" in ("/" + str(row["archive_member"]).casefold().lstrip("/"))
        and PurePosixPath(str(row["archive_member"])).name.casefold().startswith("kf-gins")
        and compound_extension(str(row["archive_member"])) in CONFIG_SUFFIXES
    ]
    pos_spike_run_meta = [
        row
        for row in inventory_rows
        if "pos_spike" in str(row["archive_member"]).casefold()
        and PurePosixPath(str(row["archive_member"])).name.casefold() == "run_meta.json"
    ]
    source_linked_inventory = [
        row
        for row in inventory_rows
        if str(row["archive_member"]).startswith(SOURCE_LINKED_EXACT_NORMAL_PREFIX)
    ]
    source_linked_inventory_files = [
        row for row in source_linked_inventory if not str(row["archive_member"]).endswith("/")
    ]
    source_linked_selected = [
        row
        for row in extracted_rows
        if str(row["archive_member"]).startswith(SOURCE_LINKED_EXACT_NORMAL_PREFIX)
    ]
    source_linked_expected_names = SOURCE_LINKED_STATIC_NAMES | SOURCE_LINKED_PARITY_NAMES
    source_linked_selected_names = {
        PurePosixPath(str(row["archive_member"])).name for row in source_linked_selected
    }
    source_linked_sibling_selected = [
        str(row["qualified_member"])
        for row in extracted_rows
        if "/extended_degradation_results/" in str(row["archive_member"])
        and not str(row["archive_member"]).startswith(SOURCE_LINKED_EXACT_NORMAL_PREFIX)
    ]
    source_case_review_rows = [
        row
        for row in extracted_rows
        if tuple(
            part.casefold()
            for part in PurePosixPath(str(row["archive_member"])).parts[-3:]
        )
        == ("nominal_none", "09_case_review", "case_review.json")
    ]
    source_link_references: set[str] = set()
    source_case_review_paths: list[str] = []
    source_pattern = re.compile(
        re.escape(SOURCE_LINKED_EXACT_NORMAL_PREFIX) + r"([^\"\s/]+)"
    )
    for row in source_case_review_rows:
        local_relative = str(row["local_relative_path"])
        case_review_path = lstat_confined_path(
            recovery_root / local_relative,
            allowed_root=recovery_root,
            role="selected source-link case review",
            must_exist=True,
        )
        source_case_review_paths.append(local_relative)
        text = case_review_path.read_text(encoding="utf-8", errors="strict")
        source_link_references.update(source_pattern.findall(text))
    source_link_classifications = Counter(
        str(row["evidence_classification"]) for row in source_linked_selected
    )
    source_link_proof_passed = (
        bool(source_case_review_paths)
        and source_link_references == set(SOURCE_LINKED_CASE_REVIEW_REFERENCES)
        and len(source_linked_inventory_files) == len(source_linked_expected_names) == 9
        and len(source_linked_selected) == 9
        and source_linked_selected_names == set(source_linked_expected_names)
        and not source_linked_sibling_selected
        and source_link_classifications["MIGRATABLE_STATIC_SPECIFICATION"] == 2
        and source_link_classifications["PARITY_REFERENCE_ONLY"] == 7
    )
    all_solver_ineligible = all(row["solver_input_eligible"] is False for row in extracted_rows)
    all_not_executable = all(row["executable"] is False for row in extracted_rows)
    passed = (
        all_solver_ineligible
        and all_not_executable
        and not noncanonical_core
        and not historical_static_misclassifications
        and not misclassified_degradation
        and not unexpected_selected_degradation
        and not unexpected_runtime_configs
        and not unsafe_extractions
        and source_link_proof_passed
        and all(row["evidence_classification"] == "DENIED_AS_ACTIVE_EVIDENCE" for row in v2_validation_configs)
        and all(row["evidence_classification"] == "DENIED_AS_ACTIVE_EVIDENCE" for row in pos_spike_run_meta)
    )
    return {
        "schema_version": "clean1r2-final-v23-selected-extraction-qa-v1",
        "selected_file_count": len(extracted_rows),
        "selected_bytes": sum(int(row["member_size"]) for row in extracted_rows),
        "role_counts": dict(sorted(role_counts.items())),
        "role_bytes": dict(sorted(role_bytes.items())),
        "runtime_config_and_conf_count": role_counts.get("runtime_config", 0)
        + role_counts.get("source_linked_runtime_config", 0),
        "parity_reference_file_count": role_counts.get("parity_reference", 0)
        + role_counts.get("historical_result", 0)
        + role_counts.get("source_linked_parity_reference", 0),
        "solver_source_core_count": len(core_rows),
        "noncanonical_solver_source_core": noncanonical_core,
        "historical_performance_static_misclassifications": historical_static_misclassifications,
        "misclassified_degradation": misclassified_degradation,
        "selected_degradation": [
            str(row["qualified_member"]) for row in selected_degradation
        ],
        "selected_degradation_exception": [
            str(row["qualified_member"]) for row in selected_degradation_exception
        ],
        "unexpected_selected_degradation": unexpected_selected_degradation,
        "selected_degradation_exception_exact_prefix": (
            len(selected_degradation_exception) == 9
            and all(
                str(row["archive_member"]).startswith(SOURCE_LINKED_EXACT_NORMAL_PREFIX)
                for row in selected_degradation_exception
            )
        ),
        "selected_runtime_configs": selected_runtime_configs,
        "unexpected_selected_runtime_configs": unexpected_runtime_configs,
        "unsafe_extractions": unsafe_extractions,
        "unsafe_extraction_count": len(unsafe_extractions),
        "v2_validation_config_count": len(v2_validation_configs),
        "v2_validation_config_all_denied": all(
            row["evidence_classification"] == "DENIED_AS_ACTIVE_EVIDENCE"
            for row in v2_validation_configs
        ),
        "pos_spike_run_meta_count": len(pos_spike_run_meta),
        "pos_spike_run_meta_all_denied": all(
            row["evidence_classification"] == "DENIED_AS_ACTIVE_EVIDENCE"
            for row in pos_spike_run_meta
        ),
        "source_link_from_selected_case_review": bool(source_case_review_paths),
        "source_link_case_review_paths": sorted(source_case_review_paths),
        "source_link_prefix": SOURCE_LINKED_EXACT_NORMAL_PREFIX,
        "source_link_prefix_exact": source_link_proof_passed,
        "source_link_referenced_names": sorted(source_link_references),
        "source_link_inventory_file_count": len(source_linked_inventory_files),
        "source_link_selected_file_count": len(source_linked_selected),
        "source_link_selected_names": sorted(source_linked_selected_names),
        "source_link_selected_classification_counts": dict(
            sorted(source_link_classifications.items())
        ),
        "source_link_sibling_case_selected": source_linked_sibling_selected,
        "source_link_performance_values_read": False,
        "all_selected_solver_input_eligible_false": all_solver_ineligible,
        "all_selected_executable_false": all_not_executable,
        "archive_runtime_payloads_are_parity_reference_only": True,
        "source_identity_selection_uses_mtime": False,
        "source_identity_selection_uses_metrics": False,
        "source_identity_conflict_resolution_requires_run_linkage": True,
        "selected_content_hashes_recorded": all(bool(row["sha256"]) for row in extracted_rows),
        "passed": passed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Ignored clean local path YAML")
    parser.add_argument("--archive", required=True, help="Exact human-authorized archive path")
    parser.add_argument("--expected-archive-sha256", default=ARCHIVE_SHA256)
    parser.add_argument("--expected-raw-lock-sha256", default=RAW_LOCK_SHA256)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--max-nested-member-bytes", type=int, default=40 * 1024 * 1024 * 1024)
    parser.add_argument("--max-total-nested-bytes", type=int, default=100 * 1024 * 1024 * 1024)
    return parser.parse_args()


def load_prior_nested_proofs(path: Path, *, allowed_root: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    lstat_confined_path(
        path,
        allowed_root=allowed_root,
        role="prior nested proof",
        must_exist=True,
    )
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        str(row.get("qualified_member", "")): row
        for row in rows
        if str(row.get("nested_sha256", ""))
        and str(row.get("status", "")) in {"INVENTORY_QUEUED", "REUSED_VERIFIED_PRIOR_COPY_INVENTORY_QUEUED"}
    }


def quarantine_selected_root(
    recovery_root: Path,
    *,
    reason: str,
    attempt: str,
    originating_pid: int | None,
) -> Path:
    """Atomically quarantine a superseded selected tree without deleting it."""

    allowed_reasons = {
        "overbroad_old_result_extraction",
        "classification_scope_superseded",
        "reviewer_needs_fix_exact_normal_allowlist",
        "source_linked_exception_superseded",
    }
    if reason not in allowed_reasons:
        raise RecoveryError("Unsupported quarantine reason")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", attempt):
        raise RecoveryError("Unsafe quarantine attempt identifier")
    if originating_pid is not None and originating_pid <= 0:
        raise RecoveryError("Invalid quarantine originating PID")
    pid_label = "UNKNOWN" if originating_pid is None else str(originating_pid)

    recovery_root = lstat_no_symlink_chain(
        recovery_root,
        role="quarantine recovery root",
        must_exist=True,
    )
    source = lstat_confined_path(
        recovery_root / "selected",
        allowed_root=recovery_root,
        role="selected tree to quarantine",
        must_exist=True,
    )
    destination = lstat_confined_path(
        recovery_root
        / f"INTERRUPTED_REVIEWER_SELECTED_DO_NOT_USE_{attempt}_pid{pid_label}",
        allowed_root=recovery_root,
        role="quarantine rename destination",
        must_exist=False,
    )
    if os.path.lexists(destination):
        raise RecoveryError("Quarantine rename destination already exists")

    file_count = 0
    total_bytes = 0
    for current_root, directories, files in os.walk(source, followlinks=False):
        current = lstat_confined_path(
            Path(current_root),
            allowed_root=recovery_root,
            role="quarantine source directory",
            must_exist=True,
        )
        for name in directories:
            lstat_confined_path(
                current / name,
                allowed_root=recovery_root,
                role="quarantine source child directory",
                must_exist=True,
            )
        for name in files:
            candidate = lstat_confined_path(
                current / name,
                allowed_root=recovery_root,
                role="quarantine source file",
                must_exist=True,
            )
            metadata = os.lstat(candidate)
            if not stat.S_ISREG(metadata.st_mode):
                raise RecoveryError("Quarantine source contains a non-regular file")
            file_count += 1
            total_bytes += metadata.st_size

    os.replace(source, destination)
    _fsync_directory(recovery_root)
    lstat_confined_path(
        destination,
        allowed_root=recovery_root,
        role="created quarantine directory",
        must_exist=True,
    )
    atomic_write_json(
        destination / "DO_NOT_USE_EVIDENCE.json",
        {
            "schema_version": "clean1r2-recovery-quarantine-v1",
            "reason": reason,
            "active_evidence": False,
            "solver_input_eligible": False,
            "file_count": file_count,
            "bytes": total_bytes,
            "originating_pid": originating_pid,
            "originating_attempt": attempt,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "final_zip_eligible": False,
            "evidence_manifest_eligible": False,
        },
    )
    return destination


def quarantine_audit(recovery_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for directory in sorted(recovery_root.glob("*SELECTED_DO_NOT_USE_*")):
        lstat_confined_path(
            directory,
            allowed_root=recovery_root,
            role="quarantine directory",
            must_exist=True,
        )
        marker = directory / "DO_NOT_USE_EVIDENCE.json"
        payload: dict[str, Any] = {}
        if marker.is_file():
            lstat_confined_path(
                marker,
                allowed_root=recovery_root,
                role="quarantine marker",
                must_exist=True,
            )
            parsed = json.loads(marker.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        rows.append(
            {
                "relative_path": directory.relative_to(recovery_root).as_posix(),
                "marker_present": marker.is_file(),
                "reason": payload.get("reason", "MISSING"),
                "active_evidence": payload.get("active_evidence", "MISSING"),
                "solver_input_eligible": payload.get("solver_input_eligible", "MISSING"),
                "file_count_at_quarantine": payload.get("file_count", "MISSING"),
                "bytes_at_quarantine": payload.get("bytes", "MISSING"),
                "originating_pid": payload.get("originating_pid", "MISSING"),
                "originating_attempt": payload.get("originating_attempt", "MISSING"),
                "final_zip_eligible": payload.get("final_zip_eligible", "MISSING"),
                "evidence_manifest_eligible": payload.get("evidence_manifest_eligible", "MISSING"),
            }
        )
    passed = all(
        row["marker_present"] is True
        and row["reason"]
        in {
            "overbroad_old_result_extraction",
            "classification_scope_superseded",
            "reviewer_needs_fix_exact_normal_allowlist",
            "source_linked_exception_superseded",
        }
        and row["active_evidence"] is False
        and row["solver_input_eligible"] is False
        and row["final_zip_eligible"] is False
        and row["evidence_manifest_eligible"] is False
        for row in rows
    )
    return {
        "schema_version": "clean1r2-recovery-evidence-contamination-audit-v1",
        "quarantine_count": len(rows),
        "quarantines": rows,
        "selected_root_excludes_quarantine": True,
        "final_zip_must_exclude_quarantine": True,
        "evidence_manifest_must_exclude_quarantine": True,
        "active_evidence_contamination": False if passed else "UNRESOLVED",
        "passed": passed,
    }


def main() -> int:
    args = parse_args()
    paths = load_clean_paths(args.config)
    archive_path = lstat_no_symlink_chain(
        Path(args.archive).expanduser(),
        role="authorized archive",
        must_exist=True,
    )
    archive_metadata = os.lstat(archive_path)
    if not stat.S_ISREG(archive_metadata.st_mode):
        raise RecoveryError("Authorized archive must be a regular non-symlink file")

    clean_root = lstat_no_symlink_chain(
        paths.clean_root,
        role="clean root",
        must_exist=True,
    )
    recovery_root = lstat_confined_path(
        clean_root / RECOVERY_DIR / f"ARCHIVE_{args.expected_archive_sha256[:12]}",
        role="final_v23 archive recovery root",
        allowed_root=clean_root,
    )
    log_root = lstat_confined_path(
        clean_root / LOG_DIR,
        role="final_v23 archive recovery log root",
        allowed_root=clean_root,
    )
    recovery_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    lstat_confined_path(
        recovery_root,
        allowed_root=clean_root,
        role="created final_v23 archive recovery root",
        must_exist=True,
    )
    lstat_confined_path(
        log_root,
        allowed_root=clean_root,
        role="created final_v23 archive recovery log root",
        must_exist=True,
    )
    prior_nested_proofs = load_prior_nested_proofs(
        log_root / "FINAL_V23_NESTED_ARCHIVE_MAP.csv",
        allowed_root=log_root,
    )

    raw_audit = verify_by2_raw_22(
        paths.raw_root,
        paths.raw_hash_lock,
        expected_lock_sha256=args.expected_raw_lock_sha256,
        expected_full_rows=9980,
        expected_by2_rows=22,
        audit_phase="pre_recovery",
    )
    atomic_write_csv(
        log_root / "RAW_PRE_RECOVERY_AUDIT.csv",
        list(raw_audit.rows),
        list(raw_audit.rows[0]),
    )
    atomic_write_json(log_root / "RAW_PRE_RECOVERY_AUDIT.json", raw_audit.summary)

    archive_stat = os.lstat(archive_path)
    actual_archive_sha256 = sha256_file(archive_path)
    if actual_archive_sha256 != args.expected_archive_sha256:
        raise RecoveryError(
            "Authorized archive SHA256 mismatch: "
            f"expected={args.expected_archive_sha256}, actual={actual_archive_sha256}"
        )
    atomic_write_text(
        log_root / "FINAL_V23_ARCHIVE_SHA256.txt",
        (
            f"sha256={actual_archive_sha256}\n"
            f"size_bytes={archive_stat.st_size}\n"
            f"mtime_ns={archive_stat.st_mtime_ns}\n"
            f"wsl_path={archive_path}\n"
        ),
    )

    containers: list[dict[str, Any]] = [
        {
            "identity": "MAIN",
            "path": archive_path,
            "depth": 0,
            "sha256": actual_archive_sha256,
            "parent_qualified_member": "",
        }
    ]
    queue: deque[int] = deque([0])
    seen_nested_hashes: set[str] = set()
    total_nested_bytes = 0
    inventory_rows: list[dict[str, Any]] = []
    nested_rows: list[dict[str, Any]] = []

    while queue:
        container_index = queue.popleft()
        container = containers[container_index]
        with zipfile.ZipFile(container["path"], "r") as archive:
            infos = archive.infolist()
            for member_index, info in enumerate(infos):
                safe, unsafe_reason = safe_member_name(info.filename)
                symlink = zipinfo_is_symlink(info)
                role, role_reason = candidate_role(info)
                classification, classification_reason = evidence_classification(role)
                nested = compound_extension(info.filename) in NESTED_ARCHIVE_SUFFIXES and not info.is_dir()
                qualified = f"{container['identity']}!/{member_index}:{info.filename}"
                try:
                    mtime = datetime(*info.date_time, tzinfo=timezone.utc).isoformat()
                except ValueError:
                    mtime = "INVALID"
                row = {
                    "archive_member": info.filename,
                    "member_size": info.file_size,
                    "compressed_size": info.compress_size,
                    "crc": f"{info.CRC:08x}",
                    "mtime": mtime,
                    "extension": compound_extension(info.filename),
                    "candidate_role": role,
                    "nested_archive": nested,
                    "container": container["identity"],
                    "container_sha256": container["sha256"],
                    "depth": container["depth"],
                    "member_index": member_index,
                    "qualified_member": qualified,
                    "safe_member": safe,
                    "unsafe_reason": unsafe_reason,
                    "symlink_member": symlink,
                    "candidate_role_reason": role_reason,
                    "evidence_classification": classification,
                    "classification_reason": classification_reason,
                    "excluded_branch": excluded_branch(info.filename),
                }
                inventory_rows.append(row)

                if not nested or compound_extension(info.filename) != ".zip":
                    continue
                nested_status = "NOT_RECURSED"
                nested_sha = ""
                local_path = ""
                blocker = ""
                if not should_recurse_nested_zip(
                    info.filename,
                    depth=int(container["depth"]),
                    main_archive_basename=archive_path.name,
                ):
                    nested_status = "SKIPPED_NOT_CANDIDATE"
                elif not safe or symlink or info.is_dir():
                    nested_status = "REJECTED_UNSAFE_MEMBER"
                    blocker = unsafe_reason or "symlink_or_directory"
                elif container["depth"] >= args.max_depth:
                    nested_status = "REJECTED_MAX_DEPTH"
                    blocker = f"max_depth={args.max_depth}"
                elif info.file_size > args.max_nested_member_bytes:
                    nested_status = "REJECTED_SIZE_BOUND"
                    blocker = f"member_size={info.file_size}"
                elif total_nested_bytes + info.file_size > args.max_total_nested_bytes:
                    nested_status = "REJECTED_TOTAL_SIZE_BOUND"
                    blocker = f"prospective_total={total_nested_bytes + info.file_size}"
                else:
                    identity_hash = hashlib.sha256(qualified.encode("utf-8")).hexdigest()[:16]
                    clean_basename = re.sub(r"[^0-9A-Za-z._-]+", "_", PurePosixPath(info.filename).name)
                    destination = (
                        recovery_root
                        / "nested_archives"
                        / f"depth_{container['depth'] + 1}"
                        / f"{identity_hash}__{clean_basename}"
                    )
                    destination = lstat_confined_path(
                        destination,
                        allowed_root=recovery_root,
                        role="nested archive destination",
                        must_exist=False,
                    )
                    prior = prior_nested_proofs.get(qualified)
                    reuse = False
                    if (
                        prior
                        and destination.is_file()
                        and not destination.is_symlink()
                        and destination.stat().st_size == info.file_size
                        and prior.get("local_relative_path") == destination.relative_to(recovery_root).as_posix()
                    ):
                        nested_sha = sha256_file(destination)
                        reuse = nested_sha == prior.get("nested_sha256")
                    if reuse:
                        copied = info.file_size
                    else:
                        nested_sha, copied = copy_zip_member_atomic(
                            archive,
                            info,
                            destination,
                            allowed_root=recovery_root,
                        )
                    total_nested_bytes += copied
                    local_path = destination.relative_to(recovery_root).as_posix()
                    if not zipfile.is_zipfile(destination):
                        nested_status = "REJECTED_INVALID_ZIP"
                        blocker = "zipfile.is_zipfile=false"
                    elif nested_sha in seen_nested_hashes:
                        nested_status = "DUPLICATE_CONTENT_NOT_RECURSED"
                    else:
                        seen_nested_hashes.add(nested_sha)
                        nested_identity = f"{container['identity']}!/{info.filename}"
                        containers.append(
                            {
                                "identity": nested_identity,
                                "path": destination,
                                "depth": int(container["depth"]) + 1,
                                "sha256": nested_sha,
                                "parent_qualified_member": qualified,
                            }
                        )
                        queue.append(len(containers) - 1)
                        nested_status = (
                            "REUSED_VERIFIED_PRIOR_COPY_INVENTORY_QUEUED"
                            if reuse
                            else "INVENTORY_QUEUED"
                        )
                nested_rows.append(
                    {
                        "parent_container": container["identity"],
                        "qualified_member": qualified,
                        "archive_member": info.filename,
                        "member_size": info.file_size,
                        "compressed_size": info.compress_size,
                        "nested_sha256": nested_sha,
                        "local_relative_path": local_path,
                        "status": nested_status,
                        "blocker": blocker,
                    }
                )

    inventory_fields = [
        "archive_member",
        "member_size",
        "compressed_size",
        "crc",
        "mtime",
        "extension",
        "candidate_role",
        "nested_archive",
        "container",
        "container_sha256",
        "depth",
        "member_index",
        "qualified_member",
        "safe_member",
        "unsafe_reason",
        "symlink_member",
        "candidate_role_reason",
        "evidence_classification",
        "classification_reason",
        "excluded_branch",
    ]
    atomic_write_csv(log_root / "FINAL_V23_ARCHIVE_INVENTORY.csv", inventory_rows, inventory_fields)
    atomic_write_json(log_root / "FINAL_V23_ARCHIVE_INVENTORY.json", inventory_rows)
    classification_fields = [
        "container",
        "depth",
        "member_index",
        "archive_member",
        "qualified_member",
        "candidate_role",
        "candidate_role_reason",
        "evidence_classification",
        "classification_reason",
        "excluded_branch",
        "safe_member",
        "symlink_member",
    ]
    atomic_write_csv(
        log_root / "FINAL_V23_ARCHIVE_EVIDENCE_CLASSIFICATION.csv",
        inventory_rows,
        classification_fields,
    )
    nested_fields = [
        "parent_container",
        "qualified_member",
        "archive_member",
        "member_size",
        "compressed_size",
        "nested_sha256",
        "local_relative_path",
        "status",
        "blocker",
    ]
    atomic_write_csv(log_root / "FINAL_V23_NESTED_ARCHIVE_MAP.csv", nested_rows, nested_fields)

    rows_by_container: dict[str, list[dict[str, Any]]] = {}
    for row in inventory_rows:
        if should_extract(row):
            rows_by_container.setdefault(str(row["container"]), []).append(row)
    container_by_identity = {str(container["identity"]): container for container in containers}
    extracted_rows: list[dict[str, Any]] = []
    for identity, selected_rows in sorted(rows_by_container.items()):
        container = container_by_identity[identity]
        key = container_key(identity)
        duplicate_destinations: Counter[str] = Counter()
        with zipfile.ZipFile(container["path"], "r") as archive:
            infos = archive.infolist()
            for row in sorted(selected_rows, key=lambda item: int(item["member_index"])):
                info = infos[int(row["member_index"])]
                pure = PurePosixPath(info.filename)
                relative = Path(*pure.parts)
                destination = recovery_root / "selected" / key / relative
                relative_key = destination.as_posix()
                duplicate_destinations[relative_key] += 1
                if duplicate_destinations[relative_key] > 1:
                    destination = destination.with_name(f"{row['member_index']}__{destination.name}")
                digest, copied = copy_zip_member_atomic(
                    archive,
                    info,
                    destination,
                    allowed_root=recovery_root,
                )
                extracted_rows.append(
                    {
                        "container": identity,
                        "container_sha256": container["sha256"],
                        "depth": container["depth"],
                        "archive_member": info.filename,
                        "qualified_member": row["qualified_member"],
                        "candidate_role": row["candidate_role"],
                        "evidence_classification": row["evidence_classification"],
                        "member_size": copied,
                        "sha256": digest,
                        "mtime": row["mtime"],
                        "local_relative_path": destination.relative_to(recovery_root).as_posix(),
                        "safe_member": row["safe_member"],
                        "symlink_member": row["symlink_member"],
                        "executable": False,
                        "solver_input_eligible": False,
                    }
                )

    extraction_fields = [
        "container",
        "container_sha256",
        "depth",
        "archive_member",
        "qualified_member",
        "candidate_role",
        "evidence_classification",
        "member_size",
        "sha256",
        "mtime",
        "local_relative_path",
        "safe_member",
        "symlink_member",
        "executable",
        "solver_input_eligible",
    ]
    atomic_write_csv(
        log_root / "FINAL_V23_SELECTED_EXTRACTION_MANIFEST.csv",
        extracted_rows,
        extraction_fields,
    )
    atomic_write_json(log_root / "FINAL_V23_SELECTED_EXTRACTION_MANIFEST.json", extracted_rows)

    extraction_qa = selected_extraction_qa(
        extracted_rows,
        inventory_rows,
        recovery_root,
    )
    atomic_write_json(log_root / "FINAL_V23_SELECTED_EXTRACTION_QA.json", extraction_qa)

    source_rows, source_markdown = build_source_map(extracted_rows)
    source_fields = [
        "logical_role",
        "archive_member",
        "sha256",
        "source_type",
        "selected",
        "selection_reason",
        "conflict_candidates",
        "conflict_resolution",
    ]
    atomic_write_csv(log_root / "FINAL_V23_ARCHIVE_SOURCE_MAP.csv", source_rows, source_fields)
    atomic_write_text(log_root / "FINAL_V23_ARCHIVE_SOURCE_MAP.md", source_markdown)

    recovery_quarantine = quarantine_audit(recovery_root)
    atomic_write_json(
        log_root / "FINAL_V23_RECOVERY_EVIDENCE_CONTAMINATION_AUDIT.json",
        recovery_quarantine,
    )

    classification_counts = Counter(str(row["evidence_classification"]) for row in inventory_rows)
    role_counts = Counter(str(row["candidate_role"]) for row in inventory_rows)
    excluded_counts = Counter(str(row["excluded_branch"]) for row in inventory_rows if row["excluded_branch"])
    nested_blockers = [row for row in nested_rows if str(row["status"]).startswith("REJECTED")]
    unresolved_roles = sorted(
        {
            str(row["logical_role"])
            for row in source_rows
            if row["conflict_resolution"] != "UNIQUE_CONTENT_IDENTITY"
        }
    )
    post_archive_sha256 = sha256_file(archive_path)
    post_archive_stat = os.lstat(archive_path)
    archive_inode_unchanged = (
        archive_stat.st_dev == post_archive_stat.st_dev
        and archive_stat.st_ino == post_archive_stat.st_ino
    )
    archive_size_unchanged = archive_stat.st_size == post_archive_stat.st_size
    archive_mtime_unchanged = archive_stat.st_mtime_ns == post_archive_stat.st_mtime_ns
    archive_hash_unchanged = (
        actual_archive_sha256 == post_archive_sha256 == args.expected_archive_sha256
    )
    archive_identity_unchanged = (
        archive_inode_unchanged
        and archive_size_unchanged
        and archive_mtime_unchanged
        and archive_hash_unchanged
    )
    unsafe_archive_members = [
        str(row["qualified_member"])
        for row in inventory_rows
        if row["safe_member"] is not True or row["symlink_member"] is True
    ]
    atomic_write_text(
        log_root / "FINAL_V23_ARCHIVE_SHA256.txt",
        (
            f"pre_sha256={actual_archive_sha256}\n"
            f"post_sha256={post_archive_sha256}\n"
            f"expected_sha256={args.expected_archive_sha256}\n"
            f"size_bytes={post_archive_stat.st_size}\n"
            f"pre_mtime_ns={archive_stat.st_mtime_ns}\n"
            f"post_mtime_ns={post_archive_stat.st_mtime_ns}\n"
            f"archive_identity_unchanged={str(archive_identity_unchanged).lower()}\n"
            f"archive_path={archive_path}\n"
        ),
    )
    summary_passed = (
        not unresolved_roles
        and not nested_blockers
        and recovery_quarantine["passed"]
        and extraction_qa["passed"]
        and raw_audit.summary["passed"]
        and archive_identity_unchanged
        and extraction_qa["unsafe_extraction_count"] == 0
    )
    summary = {
        "schema_version": "clean1r2-final-v23-archive-recovery-v1",
        "stage_id": STAGE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_access": True,
        "archive_sha256_recorded": True,
        "archive_sha256": actual_archive_sha256,
        "archive_post_sha256": post_archive_sha256,
        "archive_size_bytes": archive_stat.st_size,
        "archive_inode_unchanged": archive_inode_unchanged,
        "archive_size_unchanged": archive_size_unchanged,
        "archive_mtime_unchanged": archive_mtime_unchanged,
        "archive_hash_unchanged": archive_hash_unchanged,
        "archive_identity_unchanged": archive_identity_unchanged,
        "main_archive_member_count": sum(row["container"] == "MAIN" for row in inventory_rows),
        "main_archive_file_count": sum(
            row["container"] == "MAIN" and not str(row["archive_member"]).endswith("/")
            for row in inventory_rows
        ),
        "main_archive_directory_count": sum(
            row["container"] == "MAIN" and str(row["archive_member"]).endswith("/")
            for row in inventory_rows
        ),
        "recursive_archive_member_count": len(inventory_rows),
        "recursive_archive_file_count": sum(
            not str(row["archive_member"]).endswith("/") for row in inventory_rows
        ),
        "recursive_archive_directory_count": sum(
            str(row["archive_member"]).endswith("/") for row in inventory_rows
        ),
        "container_count": len(containers),
        "nested_zip_member_count": sum(compound_extension(str(row["archive_member"])) == ".zip" for row in inventory_rows),
        "nested_zip_extracted_bytes": total_nested_bytes,
        "classification_counts": dict(sorted(classification_counts.items())),
        "candidate_role_counts": dict(sorted(role_counts.items())),
        "excluded_branch_counts": dict(sorted(excluded_counts.items())),
        "selected_extraction_count": len(extracted_rows),
        "selected_extraction_qa": extraction_qa,
        "selected_extraction_root": str(recovery_root / "selected"),
        "recovery_root": str(recovery_root),
        "log_root": str(log_root),
        "raw_pre_recovery": raw_audit.summary,
        "source_identity_unique_for_core_four": not unresolved_roles,
        "unresolved_core_roles": unresolved_roles,
        "nested_inventory_blockers": nested_blockers,
        "unsafe_archive_member_count": len(unsafe_archive_members),
        "unsafe_archive_members": unsafe_archive_members,
        "unsafe_extraction_count": extraction_qa["unsafe_extraction_count"],
        "filesystem_symlink_and_confinement_guards_passed": True,
        "recovery_quarantine_audit": recovery_quarantine,
        "quarantined_payloads_excluded_from_selected_extraction": True,
        "quarantined_payloads_final_zip_eligible": False,
        "quarantined_payloads_evidence_manifest_eligible": False,
        "archived_binary_executed": False,
        "archived_runtime_used_as_solver_input": False,
        "archive_modified": not archive_identity_unchanged,
        "passed": summary_passed,
    }
    atomic_write_json(log_root / "FINAL_V23_ARCHIVE_RECOVERY_SUMMARY.json", summary)
    atomic_write_text(
        log_root / "FINAL_V23_ARCHIVE_RECOVERY_COMPLETE.txt",
        (
            f"stage_id={STAGE_ID}\n"
            f"archive_sha256={actual_archive_sha256}\n"
            f"main_members={summary['main_archive_member_count']}\n"
            f"recursive_members={summary['recursive_archive_member_count']}\n"
            f"selected_extractions={len(extracted_rows)}\n"
            f"archive_identity_unchanged={str(archive_identity_unchanged).lower()}\n"
            f"passed={str(summary_passed).lower()}\n"
            f"source_identity_unique_for_core_four={str(not unresolved_roles).lower()}\n"
            f"unresolved_core_roles={','.join(unresolved_roles)}\n"
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
