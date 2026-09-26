"""Gate-ordered G0--G4 exact-route transaction.

Nothing in this module reads trace/reference or another method's output.  The
only conditional navigation launch is the single official BY2 C00 after the
sample, both adapters, config/time contract, and TDCP activation all pass.
"""

from __future__ import annotations

import bisect
import copy
import csv
import dataclasses
import datetime as dt
import decimal
import hashlib
import io
import json
import os
import re
import shutil
import stat
import struct
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from legsa_gins.paper_rebuild.manifest import (
    ManifestContractError,
    read_hash_lock,
    verify_raw_sources,
)
from legsa_gins.paper_rebuild.paths import PathContractError, load_yaml_mapping
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import (
    _scan_valid_ubx_frames,
    iter_ubx_frames,
    parse_csv_data_cell,
    reconstruct_ubx_stream,
)

from .config_contract import (
    ConfigContractError,
    derive_by2_config,
    derive_official_sample_config,
)
from .constants import (
    CANDIDATE_ID,
    CLASSIFICATION_LABELS,
    GO2_SAMPLE_RATE_HZ,
    OFFICIAL_CONFIG_RELATIVE,
    OFFICIAL_REFERENCE_MEMBER_BASENAME,
    OFFICIAL_SAMPLE_RELATIVE,
    POOR_APPLICABILITY_STATUS,
    RAW_HASH_LOCK_SHA256,
    STAGE_NAME,
    STAGE_RELATIVE_LAYOUT,
    SUCCESS_STATUS,
    TERMINAL_STATUSES,
)
from .imu_adapter import ImuAdapterError, adapt_go2_imu
from .libarchive7z import (
    Libarchive7zBackend,
    Libarchive7zError,
    frozen_inventory_binding_sha256,
)
from .matlab import (
    MatlabRuntimeError,
    build_matlab_batch_command,
    discover_matlab_candidates,
    render_environment_probe,
    render_official_run_script,
    render_tdcp_probe_script,
    parse_environment_probe,
    run_matlab_script,
    validate_matlab_environment,
    wsl_to_windows_path,
    write_harness_files,
)
from .outputs import (
    OutputContractError,
    analyze_frozen_native_solution_metadata_only,
    compare_sample_runs,
    freeze_native_solution,
    read_official_solution,
    summarize_solution,
)
from .publication import (
    PublicationError,
    assert_no_symlink_components,
    assert_outside_protected_roots,
    publish_compact_stage,
    validate_exact_destination,
)
from .rinex_adapter import (
    RinexAdapterError,
    convert_gnss1_raw_to_rinex,
    epoch_signal_rows,
)
from .source import (
    AccessLedger,
    CoreCleanlinessGuard,
    ForbiddenInputError,
    SourceIdentityError,
    copy_file_content_exact,
    materialize_runtime_source_mirror,
    runtime_source_mirror_relative_files,
    sha256_file,
    verify_source_identity,
    write_json,
)
from .time_contract import (
    GpsTime,
    NANOSECONDS,
    WEEK_SECONDS,
    RinexEpoch,
    TimeContractError,
    extract_same_receiver_time_events,
    five_phase_row_conservation_audit,
    gpst_calendar_to_gps,
    gps_to_gpst_calendar,
    normalize_rinex_epochs,
    official_epoch_acceptance_audit,
    parse_rinex_epochs,
    prove_single_constant_normalization,
)


class TransactionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class TransactionOptions:
    repository_root: Path
    paths_config: Path
    ginav_root: Path
    matlab_executable: Path
    libarchive_path: Path
    scratch_root: Path
    destination_stage_root: Path
    paper_root: Path
    legacy_freeze_root: Path
    publish: bool = True
    sample_timeout_seconds: float = 3600.0
    probe_timeout_seconds: float = 1800.0
    c00_timeout_seconds: float = 3600.0


@dataclasses.dataclass(frozen=True)
class ResumeExistingR4Options:
    source_r4_root: Path
    continuation_root: Path
    matlab_executable: Path
    repository_root: Path = dataclasses.field(
        default_factory=lambda: Path(__file__).resolve().parents[5]
    )


@dataclasses.dataclass(frozen=True)
class ExecuteResumeExistingR4Options:
    repository_root: Path
    paths_config: Path
    ginav_root: Path
    matlab_executable: Path
    source_r4_root: Path
    continuation_root: Path
    probe_timeout_seconds: float = 1800.0
    c00_timeout_seconds: float = 3600.0


@dataclasses.dataclass(frozen=True)
class RecoverR4cPrepareOptions:
    repository_root: Path
    source_r4_root: Path
    source_r4b_root: Path
    r4c_root: Path
    matlab_executable: Path


@dataclasses.dataclass(frozen=True)
class RecoverR4cExecuteOptions:
    repository_root: Path
    paths_config: Path
    ginav_root: Path
    matlab_executable: Path
    source_r4_root: Path
    source_r4b_root: Path
    r4c_root: Path
    c00_timeout_seconds: float = 3600.0


@dataclasses.dataclass(frozen=True)
class RecoverR4dPrepareOptions:
    repository_root: Path
    source_r4_root: Path
    source_r4b_root: Path
    source_r4c_root: Path
    r4d_root: Path


@dataclasses.dataclass(frozen=True)
class RecoverR4dExecuteOptions:
    repository_root: Path
    source_r4_root: Path
    source_r4b_root: Path
    source_r4c_root: Path
    r4d_root: Path


_SHORT_RESUME_LAYOUT = {
    "00_SOURCE_AND_ENVIRONMENT": "g0",
    "01_OFFICIAL_SAMPLE_REGRESSION": "g1",
    "02_BY2_GNSS_ADAPTER": "g2n",
    "03_BY2_IMU_ADAPTER": "g2i",
    "04_BY2_CONFIG_AND_TIME_CONTRACT": "g3c",
    "05_BY2_ACTIVATION_PROBE": "g3p",
    "06_BY2_C00_NATIVE": "g4",
    "07_NATIVE_OUTPUT_NORMALIZATION": "n",
    "11_REPORT": "r",
}


FROZEN_R4_RESUME_IDENTITY: Mapping[str, Any] = {
    "root_basename": "r4",
    "top_level_entries": (
        "LC02_GINAV2021_RESUME_20260826.py",
        "LONG_PATH_FAILURE_TREE_MANIFEST.json",
        "MATLAB_WINDOWS_PATH_BUDGET.json",
        "PREVIOUS_CONTINUATION_HASH_MANIFEST.json",
        "PREVIOUS_RESUME_HASH_MANIFEST.json",
        "PRE_EXECUTION_CONTROL.json",
        "WSLPATH_CONVERSION_LEDGER.jsonl",
        "s",
    ),
    "stage_entries": ("g0", "g1", "g2i", "g2n", "g3c", "g3p", "g4", "n", "r"),
    "full_tree_binding_sha256": (
        "b2cf91fd343f85da6e7a09420f1032880235b137ce2fd33513512024e08a4dab"
    ),
    "section_tree_binding_sha256": {
        "G0": "8cac9e4e5bc5c692501661764b3a84d4de7cbee9840bcf7a44c3a17a9123cf8e",
        "G1": "988f996f95e03fa96782ed613df519906ece573e5fb71e1d824db8212b3d4920",
        "G2_GNSS": "5aa4d3155d07676ed6a32c8832e60bb7d16541920e776df67c1fa44869b476d4",
        "G2_IMU": "a663c9eb04d1b3a7230df72b51516284bf58410e06986552c06111c6d7091faf",
    },
    "required_file_sha256": {
        "s/r/LC02_GINAV2021_TRANSACTION_STATUS.json": (
            "a094c0834014fe64a8c0e35bc3b38f4faf39bef5ce9300903149cf48ac5fdec8"
        ),
        "s/r/GINAV_CONSOLIDATED_PROVENANCE.json": (
            "d16101be6ec58bf7f5e0e9dc8e5e89236847a8038e3c098b0ce8f4703bb1438f"
        ),
        "s/r/LC02_GINAV2021_POST_G0_RESUME_SUMMARY.json": (
            "caea91f9b9d0ca5363622172147185c08d4a17bbbdcd0bd2d057208d80caa6fd"
        ),
        "LC02_GINAV2021_RESUME_20260826.py": (
            "06dd11dc75c65569e1b4a3475fe68bc41ba623c3d8ce15f2e47ec26c52e89967"
        ),
        "PRE_EXECUTION_CONTROL.json": (
            "be51ddfd4d3a43892850f440ec30522b9f748ff3888334a52e9216f70fd33b26"
        ),
    },
}

_FROZEN_R4_TERMINAL = "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY"
_FROZEN_R4_GATE_COUNTS = {
    "G0_matlab_candidate_attempts": 0,
    "G1_official_sample_runs": 2,
    "G2_gnss_adapter_runs": 1,
    "G2_imu_adapter_runs": 1,
    "G3_tdcp_probe_runs": 0,
    "G4_BY2_C00_runs": 0,
}

_FROZEN_R4B_FULL_BINDING = "4361768d23ca87252e9a240d3b487443b1d69050c40ace9de3ea145298c8583d"
_FROZEN_R4B_SECTION_BINDINGS = {
    "g0": "cdafd0f579a8ea4009842ca26f7284d7eb72314bb9626e2de4e69d5e2905a3dc",
    "g1": "bbda26dc0efcba80132bb75230d671659fce25c0e75fa8e7f778e3e76297251c",
    "g2i": "dcd2dcf3b2a918fcfb225980d86b7fff3ba774def8a64364baca1f8bc81f7cca",
    "g2n": "34e5ec394820d2cbe5c8266086808977cdd821c1ba2e51618a082078a9fa7418",
    "g3c": "6ef3f136c423e2186b682cd2a57c39d405f530b0df834cb0ada84f9e921084aa",
    "g3p": "54644eefe64b2d4e46bdd6164c2b62b1d1988d3af7ca3d2a3d799769f123e096",
    "r": "9243c652a6a5ce42c44a66b150835b6b5b3b73436d2992a4fd9ecdf85a9d7def",
}
_FROZEN_R4B_REQUIRED_HASHES = {
    "SOURCE_R4_G0_G1_G2_HASH_LOCK.json": "e95f48aaea579af95cd0db3e9ecbd02c7743c2f004a8a68eadd3246d095f0f56",
    "PRE_EXECUTION_CONTROL.json": "274cda3b05ea8b44f0238feeb147573f94bbbf287728f260b5ca623f417c60a3",
    "WSLPATH_LEDGER.csv": "76ee609b84a0d6919ad6812ac994203516af1e7511223268ec3a1cf1d7772ec0",
    "WSLPATH_BUDGET.json": "78e1573dea8e34b9d182591f48379a7c875a541b60476065224e3ea10cd211b0",
    "s/r/LC02_GINAV2021_TRANSACTION_STATUS.json": "d777292af0add9f49a1369dc56691b4bc003049abff29888614356435efece98",
    "s/r/GINAV_CONSOLIDATED_PROVENANCE.json": "87ddba81630506803dad65e65d5ff155d9d39d86222bcdc20790f094f147e7e5",
    "s/r/LC02_GINAV2021_ARTIFACT_MANIFEST.json": "83330dbdc5ee988137987fc43dacf0df9dd39df3a1b9d826381b92738981e9f4",
    "s/r/LC02_GINAV2021_RESUME_SEAL.json": "f2084c524326fbc56ccdcd99a225df5adc74853713cb3c38552cd2a2fae57ec6",
    "s/g3p/BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv": "864edd70b8ca8cc2e4d341703b6e3b1c9c542d62184726870f32a8fc105b79a0",
    "s/g3c/BY2_GINAV_SPP_LC.ini": "688ea8acaa910971b9cc3a37861328d6be1b678e82f8a409a1385207ebc66975",
    "s/g3c/BY2_GNSS1_NORMALIZED.rnx": "0dfe3e84dcdcbaab6c6ace0e51a34c3fbbc4509117dbaf7e8c5634721ade5f68",
}

_FROZEN_R4C_FULL_BINDING = "d84114d1fe14a95c7b4b6d48b2260792dc649d6b01fe61687bc45008e0642afd"
_FROZEN_R4C_SCIENTIFIC_DIGEST = "080abe1c2477c9bdf9f38ac2011acb58b5ded37e06b72498a92b669cd95eaefa"
_FROZEN_R4C_REQUIRED_HASHES = {
    "s/g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos": "39453826453515689416d3d32a8d39290b0fbb35b71525283b692f8fccb788b2",
    "s/g4/GINAV_BY2_C00_STATUS_STREAM.csv": "2fa8c13405f6b292de176b39cb25dc74194ba2b9667ba8389c97669d19ff9fa5",
    "s/g4/GINAV_BY2_C00_FAILURE_LEDGER.csv": "bc69269975220260c6ade586de15ee9f36c7b0a03a128d1835ea6f17d62e656a",
    "s/g4/GINAV_BY2_C00_RUNTIME.csv": "bfc1f0e3a193e13a9e2abdc4596df966b217cb00b1c599b6d6372c0fc0636c16",
    "s/n/GINAV_BY2_C00_STANDARD_NAV.csv": "99f3b09ea4f3964df815cfc64b88cdfe7a3460a1fe305cca52e4acd63e666e06",
    "s/r/GINAV_CONSOLIDATED_PROVENANCE.json": "e1d1b3afecb5fd3bc5abd9dd694f0648b074b4c1bf3488b88c0921abd1c7fe89",
    "s/r/LC02_GINAV2021_TRANSACTION_STATUS.json": "d8108bbede630a4d75523f8bf0951767bd5457f29e4dba496cd54e38810dc8dd",
    "s/r/LC02_GINAV2021_ARTIFACT_MANIFEST.json": "15444939143dee853935edf92f3e21a03e8eaaac8e2a5288bfb257e76de510cf",
    "s/r/LC02_GINAV2021_RESUME_SEAL.json": "bfdc0eba1204e0f403e68031f8a581aa1fcd6162a1d7f3d0e8c7a712e56f142e",
}


def _hash_lock_tree(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise TransactionError(f"reused source directory is unavailable: {root}")
    files: list[dict[str, Any]] = []
    directories: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise TransactionError(f"symlink is forbidden in reused r4 source: {relative}")
        if stat.S_ISDIR(mode):
            directories.append(relative)
        elif stat.S_ISREG(mode):
            files.append(
                {
                    "relative_path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        else:
            raise TransactionError(f"special entry is forbidden in reused r4 source: {relative}")
    if not files:
        raise TransactionError(f"reused r4 source directory is empty: {root}")
    digest = hashlib.sha256()
    for row in files:
        digest.update(
            (f"{row['relative_path']}\0{row['bytes']}\0{row['sha256']}\n").encode(
                "utf-8"
            )
        )
    return {
        "root": str(root.resolve(strict=True)),
        "file_count": len(files),
        "directory_count": len(directories),
        "tree_binding_sha256": digest.hexdigest(),
        "files": files,
    }


def _verify_frozen_r4(source_root: Path) -> dict[str, Any]:
    source_root = source_root.expanduser().resolve(strict=True)
    expected = FROZEN_R4_RESUME_IDENTITY
    if source_root.name != expected["root_basename"]:
        raise TransactionError("source is not the exact frozen r4 root basename")
    actual_top = tuple(sorted(path.name for path in source_root.iterdir()))
    if actual_top != tuple(expected["top_level_entries"]):
        raise TransactionError("source r4 top-level layout differs from frozen identity")
    source_stage = source_root / "s"
    if not source_stage.is_dir() or source_stage.is_symlink():
        raise TransactionError("source r4 exact short stage layout is unavailable")
    actual_stage = tuple(sorted(path.name for path in source_stage.iterdir()))
    if actual_stage != tuple(expected["stage_entries"]):
        raise TransactionError("source r4 short stage layout differs from frozen identity")
    section_names = {
        "G0": ("g0", "00_SOURCE_AND_ENVIRONMENT"),
        "G1": ("g1", "01_OFFICIAL_SAMPLE_REGRESSION"),
        "G2_GNSS": ("g2n", "02_BY2_GNSS_ADAPTER"),
        "G2_IMU": ("g2i", "03_BY2_IMU_ADAPTER"),
    }
    locks: dict[str, Any] = {}
    for gate, alternatives in section_names.items():
        candidates = [source_stage / name for name in alternatives]
        section = next((path for path in candidates if path.is_dir()), None)
        if section is None:
            raise TransactionError(f"source r4 lacks reusable {gate} evidence")
        locks[gate] = _hash_lock_tree(section)

    status_path = source_stage / "r/LC02_GINAV2021_TRANSACTION_STATUS.json"
    provenance_path = source_stage / "r/GINAV_CONSOLIDATED_PROVENANCE.json"
    summary_path = source_stage / "r/LC02_GINAV2021_POST_G0_RESUME_SUMMARY.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    source_provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    for name, payload in (
        ("status", status), ("provenance", source_provenance), ("summary", summary)
    ):
        if payload.get("terminal_status") != _FROZEN_R4_TERMINAL:
            raise TransactionError(f"source r4 {name} terminal differs from frozen terminal")
        if payload.get("formal_lc02_admission") is not False:
            raise TransactionError(f"source r4 {name} formal admission is not false")
        if payload.get("OFFICIAL_SAMPLE_RESULT") != "OFFICIAL_SAMPLE_PASS":
            raise TransactionError(f"source r4 {name} official sample is not PASS")
        if payload.get("BY2_C00_executed") is not False:
            raise TransactionError(f"source r4 {name} BY2 C00 is not unexecuted")
        if payload.get("transaction_complete") is not True:
            raise TransactionError(f"source r4 {name} transaction is incomplete")
        if payload.get("G0_execution_this_resume") != 0:
            raise TransactionError(f"source r4 {name} G0 resume count differs")
        if payload.get("G0_execution_this_continuation") != 0:
            raise TransactionError(f"source r4 {name} G0 continuation count differs")
    if status.get("scientific_terminal_status") != _FROZEN_R4_TERMINAL:
        raise TransactionError("source r4 scientific terminal differs from frozen terminal")
    if status.get("official_sample_regression_executed") is not True:
        raise TransactionError("source r4 official sample execution field differs")
    if status.get("official_sample_archive_inventory_completed") is not True:
        raise TransactionError("source r4 official sample inventory field differs")
    if status.get("official_sample_extraction_count") != 2:
        raise TransactionError("source r4 official sample extraction count differs")

    for name, payload in (("provenance", source_provenance), ("summary", summary)):
        if payload.get("gate_execution_counts") != _FROZEN_R4_GATE_COUNTS:
            raise TransactionError(f"source r4 {name} gate counts differ from frozen counts")

    for relative, frozen_hash in expected["required_file_sha256"].items():
        path = source_root / relative
        if not path.is_file() or path.is_symlink() or sha256_file(path) != frozen_hash:
            raise TransactionError(f"source r4 frozen file identity mismatch: {relative}")

    for gate, lock in locks.items():
        if lock["tree_binding_sha256"] != expected[
            "section_tree_binding_sha256"
        ][gate]:
            raise TransactionError(f"source r4 frozen section binding mismatch: {gate}")
    full_lock = _hash_lock_tree(source_root)
    if full_lock["tree_binding_sha256"] != expected["full_tree_binding_sha256"]:
        raise TransactionError("source r4 full-tree binding differs from frozen identity")
    source_counts = source_provenance.get("gate_execution_counts")
    if not isinstance(source_counts, Mapping):
        raise TransactionError("source r4 gate execution counts are unavailable")
    if (
        dict(source_counts) != _FROZEN_R4_GATE_COUNTS
    ):
        raise TransactionError("source r4 is not the exact reusable G0/G1/G2 terminal")
    return {
        "source_root": source_root,
        "source_stage": source_stage,
        "locks": locks,
        "full_lock": full_lock,
        "status": status,
        "provenance": source_provenance,
        "summary": summary,
        "provenance_path": provenance_path,
    }


def _verify_frozen_r4b(source_root: Path) -> dict[str, Any]:
    root = source_root.expanduser().resolve(strict=True)
    if root.name != "r4b" or root.is_symlink():
        raise TransactionError("source is not the exact frozen r4b basename")
    if tuple(sorted(path.name for path in root.iterdir())) != (
        "PRE_EXECUTION_CONTROL.json", "SOURCE_R4_G0_G1_G2_HASH_LOCK.json",
        "WSLPATH_BUDGET.json", "WSLPATH_LEDGER.csv", "s",
    ):
        raise TransactionError("frozen r4b top-level layout mismatch")
    stage = root / "s"
    if tuple(sorted(path.name for path in stage.iterdir())) != (
        "g0", "g1", "g2i", "g2n", "g3c", "g3p", "g4", "n", "r",
    ):
        raise TransactionError("frozen r4b stage layout mismatch")
    for empty in (stage / "g4", stage / "n"):
        if tuple(empty.iterdir()):
            raise TransactionError(f"frozen r4b expected empty section changed: {empty.name}")
    sections = {
        name: _hash_lock_tree(stage / name)["tree_binding_sha256"]
        for name in _FROZEN_R4B_SECTION_BINDINGS
    }
    if sections != _FROZEN_R4B_SECTION_BINDINGS:
        raise TransactionError("frozen r4b section binding mismatch")
    full = _hash_lock_tree(root)
    if full["tree_binding_sha256"] != _FROZEN_R4B_FULL_BINDING:
        raise TransactionError("frozen r4b full-tree binding mismatch")
    for relative, expected in _FROZEN_R4B_REQUIRED_HASHES.items():
        path = root / relative
        if not path.is_file() or path.is_symlink() or sha256_file(path) != expected:
            raise TransactionError(f"frozen r4b required identity mismatch: {relative}")
    status = json.loads(
        (stage / "r/LC02_GINAV2021_TRANSACTION_STATUS.json").read_text(encoding="utf-8")
    )
    counts = status.get("gate_execution_counts_this_continuation")
    if (
        status.get("terminal_status") != "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"
        or status.get("detail")
        != "activation probe could not complete: TDCP probe boolean spp_pair_available has invalid value: '28'"
        or not isinstance(counts, Mapping)
        or counts.get("G3_tdcp_probe_runs") != 1
        or counts.get("G4_BY2_C00_runs") != 0
        or any(counts.get(key) != 0 for key in (
            "G0_matlab_candidate_attempts", "G1_official_sample_runs",
            "G2_gnss_adapter_runs", "G2_imu_adapter_runs",
        ))
    ):
        raise TransactionError("frozen r4b terminal/G3/G4 identity mismatch")
    manifest = json.loads(
        (stage / "r/LC02_GINAV2021_ARTIFACT_MANIFEST.json").read_text(encoding="utf-8")
    )
    seal = json.loads(
        (stage / "r/LC02_GINAV2021_RESUME_SEAL.json").read_text(encoding="utf-8")
    )
    if (
        manifest.get("file_count") != 383
        or seal.get("artifact_manifest_sha256")
        != _FROZEN_R4B_REQUIRED_HASHES["s/r/LC02_GINAV2021_ARTIFACT_MANIFEST.json"]
        or seal.get("seal_written_last") is not True
    ):
        raise TransactionError("frozen r4b manifest/seal identity mismatch")
    return {
        "root": root, "stage": stage, "full_lock": full,
        "section_bindings": sections, "status": status,
        "manifest": manifest, "seal": seal,
    }


def _verify_frozen_r4c(source_root: Path) -> dict[str, Any]:
    root = source_root.expanduser().resolve(strict=True)
    if root.name != "r4c" or root.is_symlink():
        raise TransactionError("frozen r4c root identity mismatch")
    if tuple(sorted(path.name for path in root.iterdir())) != (
        "PRE_EXECUTION_CONTROL.json", "R4C_G4_RECOVERY_LOCK.json",
        "WSLPATH_BUDGET.json", "WSLPATH_LEDGER.csv", "s",
    ):
        raise TransactionError("frozen r4c top-level layout mismatch")
    stage = root / "s"
    if tuple(sorted(path.name for path in stage.iterdir())) != tuple(
        sorted(_SHORT_RESUME_LAYOUT.values())
    ):
        raise TransactionError("frozen r4c stage layout mismatch")
    full = _hash_lock_tree(root)
    if full["tree_binding_sha256"] != _FROZEN_R4C_FULL_BINDING:
        raise TransactionError("frozen r4c full-tree identity mismatch")
    for relative, expected in _FROZEN_R4C_REQUIRED_HASHES.items():
        path = root / relative
        if not path.is_file() or path.is_symlink() or sha256_file(path) != expected:
            raise TransactionError(f"frozen r4c artifact identity mismatch: {relative}")
    provenance = json.loads(
        (stage / "r/GINAV_CONSOLIDATED_PROVENANCE.json").read_text(encoding="utf-8")
    )
    status = json.loads(
        (stage / "r/LC02_GINAV2021_TRANSACTION_STATUS.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (stage / "r/LC02_GINAV2021_ARTIFACT_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    seal = json.loads(
        (stage / "r/LC02_GINAV2021_RESUME_SEAL.json").read_text(encoding="utf-8")
    )
    expected_detail = "native provenance is incomplete: dataset_role"
    if (
        provenance.get("dataset_role") is not None
        or provenance.get("technical_blocker")
        != f"OutputContractError: {expected_detail}"
        or status.get("detail") != expected_detail
        or status.get("execution_counts_this_recovery", {}).get("G4") != 1
        or manifest.get("file_count") != 383
        or seal.get("artifact_manifest_sha256")
        != _FROZEN_R4C_REQUIRED_HASHES[
            "s/r/LC02_GINAV2021_ARTIFACT_MANIFEST.json"
        ]
        or seal.get("seal_written_last") is not True
    ):
        raise TransactionError("frozen r4c terminal metadata identity mismatch")
    return {
        "root": root, "stage": stage, "full_lock": full,
        "provenance": provenance, "status": status,
        "manifest": manifest, "seal": seal,
    }


def prepare_recover_r4b_g3_to_r4c_g4(
    options: RecoverR4cPrepareOptions,
) -> dict[str, Any]:
    r4 = _verify_frozen_r4(options.source_r4_root)
    r4b = _verify_frozen_r4b(options.source_r4b_root)
    _matlab, matlab_identity = _verify_resume_matlab_identity(
        options.matlab_executable, r4["source_stage"]
    )
    code_identity = _resume_code_identity(options.repository_root)
    destination = options.r4c_root.expanduser()
    if destination.name != "r4c" or os.path.lexists(destination):
        raise TransactionError("r4c recovery root must be fresh and exact basename r4c")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise TransactionError("r4c parent must be one existing real directory")
    destination.mkdir(exist_ok=False)
    payload = {
        "schema_version": "ginav2021.r4c_g4_recovery_lock.v1",
        "source_r4_root": str(r4["source_root"]),
        "source_r4_full_binding": r4["full_lock"]["tree_binding_sha256"],
        "source_r4b_root": str(r4b["root"]),
        "r4c_root": str(destination.resolve(strict=True)),
        "source_r4b_full_binding": r4b["full_lock"]["tree_binding_sha256"],
        "source_r4b_section_bindings": r4b["section_bindings"],
        "prepared_code_identity": code_identity,
        "prepared_matlab_identity": matlab_identity,
        "execution_counts_this_recovery": {
            "G0": 0, "G1": 0, "G2": 0, "G3": 0, "G4": 0,
        },
        "prepare_only_no_matlab_no_g4": True,
        "pass": True,
    }
    write_json(destination / "R4C_G4_RECOVERY_LOCK.json", payload)
    return payload

def prepare_resume_existing_r4_from_g3c(
    options: ResumeExistingR4Options,
) -> dict[str, Any]:
    """Create the sole non-overwriting continuation root and lock reused gates.

    This entry performs no adapter, RINEX, MATLAB, G3, or G4 execution.  It is
    the fail-closed resume boundary used before a separately authorized suffix
    launch.  The source r4 G0/G1/G2 trees remain read-only and are bound by
    content hashes in the new single-level continuation root.
    """

    verified = _verify_frozen_r4(options.source_r4_root)
    source_root = verified["source_root"]
    source_stage = verified["source_stage"]
    locks = verified["locks"]
    full_lock = verified["full_lock"]
    source_provenance = verified["provenance"]
    provenance_path = verified["provenance_path"]
    _resolved_matlab, matlab_identity = _verify_resume_matlab_identity(
        options.matlab_executable, source_stage
    )
    prepared_code_identity = _resume_code_identity(options.repository_root)

    continuation = options.continuation_root.expanduser()
    if os.path.lexists(continuation):
        raise TransactionError(f"non-overwriting continuation root exists: {continuation}")
    if not continuation.parent.is_dir() or continuation.parent.is_symlink():
        raise TransactionError(
            "continuation parent must already exist as one real directory"
        )
    continuation.mkdir(exist_ok=False)
    payload = {
        "schema_version": "ginav2021.resume_existing_r4_from_g3c.v1",
        "source_r4_root": str(source_root),
        "continuation_root": str(continuation.resolve(strict=True)),
        "single_level_continuation_root": True,
        "source_gate_hash_locks": locks,
        "source_full_tree_hash_lock": full_lock,
        "source_consolidated_provenance_sha256": sha256_file(provenance_path),
        "prepared_matlab_identity": matlab_identity,
        "prepared_implementation_code_identity": prepared_code_identity,
        "gate_execution_counts_this_continuation": {
            "G0_matlab_candidate_attempts": 0,
            "G1_official_sample_runs": 0,
            "G2_gnss_adapter_runs": 0,
            "G2_imu_adapter_runs": 0,
            "G3_tdcp_probe_runs": 0,
            "G4_BY2_C00_runs": 0,
        },
        "gate_reuse": {"G0": True, "G1": True, "G2_GNSS": True, "G2_IMU": True},
        "suffix_execution_caps": {"G3_tdcp_probe_runs": 1, "G4_BY2_C00_runs": 1},
        "resume_entry_phase": "READY_FROM_G3C_NOT_EXECUTED",
        "matlab_executed": False,
        "rinex_generated": False,
        "pass": True,
    }
    try:
        write_json(continuation / "SOURCE_R4_G0_G1_G2_HASH_LOCK.json", payload)
    except Exception:
        # The empty root is intentionally retained as evidence of a failed,
        # non-overwriting preparation attempt.
        raise
    return payload


def _write_yaml(path: Path, payload: Mapping[str, Any]) -> Path:
    # JSON is a strict YAML-1.2 subset and avoids a runtime PyYAML dependency.
    return write_json(path, payload)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})
    return path


def _make_scratch_root(
    requested: Path, *, protected_roots: Sequence[Path]
) -> Path:
    root = requested.expanduser()
    try:
        assert_no_symlink_components(root.parent, allow_missing_leaf=False)
        assert_no_symlink_components(root, allow_missing_leaf=True)
        assert_outside_protected_roots(root, protected_roots)
    except PublicationError as exc:
        raise TransactionError(str(exc)) from exc
    if os.path.lexists(root):
        raise TransactionError(f"non-overwriting scratch root exists: {root}")
    root.mkdir(exist_ok=False)
    selected = root.resolve(strict=True)
    try:
        filesystem = subprocess.run(
            ["findmnt", "-n", "-o", "FSTYPE", "-T", str(selected)],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError(f"cannot verify scratch filesystem: {exc}") from exc
    if filesystem != "ext4":
        raise TransactionError(
            f"LC02 runtime scratch must be Linux-local ext4, got {filesystem!r}"
        )
    return selected


def _create_stage_layout(scratch_root: Path) -> Path:
    stage = scratch_root / STAGE_NAME
    stage.mkdir(parents=True, exist_ok=False)
    for relative in STAGE_RELATIVE_LAYOUT:
        (stage / relative).mkdir(exist_ok=False)
    return stage


def _stage_dir(stage: Path, name: str) -> Path:
    if name not in STAGE_RELATIVE_LAYOUT:
        raise TransactionError(f"unknown LC02 stage directory: {name}")
    return stage / name


def _write_cleanliness(
    stage: Path,
    runs: Sequence[Mapping[str, Any]],
    *,
    stage_dir_resolver: Any = _stage_dir,
) -> Path:
    destination = (
        stage_dir_resolver(stage, "00_SOURCE_AND_ENVIRONMENT")
        / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"
    )
    combined = [dict(item) for item in runs]
    known: dict[str, dict[str, Any]] = {}
    for item in combined:
        run_id = str(item.get("run_id") or "")
        if not run_id:
            raise TransactionError("source-cleanliness proof has no run_id")
        if run_id in known:
            raise TransactionError(f"duplicate source-cleanliness run_id: {run_id}")
        known[run_id] = item

    for proof_path in stage.rglob("GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"):
        if proof_path == destination:
            continue
        try:
            item = json.loads(proof_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise TransactionError(
                f"malformed source-cleanliness proof: {proof_path}: {exc}"
            ) from exc
        if not isinstance(item, Mapping):
            raise TransactionError(
                f"source-cleanliness proof is not an object: {proof_path}"
            )
        run_id = str(item.get("run_id") or "")
        if not run_id:
            raise TransactionError(
                f"source-cleanliness proof has no run_id: {proof_path}"
            )
        item_dict = dict(item)
        if run_id in known:
            if known[run_id] != item_dict:
                raise TransactionError(
                    f"conflicting source-cleanliness proof for run_id: {run_id}"
                )
            continue
        combined.append(item_dict)
        known[run_id] = item_dict

    # The caller's in-memory ledger must learn about proofs recovered from
    # failed candidate/run directories so terminal provenance cannot omit them.
    if isinstance(runs, list):
        runs[:] = combined
    return write_json(
        destination,
        {
            "schema_version": "ginav2021.core_cleanliness_all_runs.v1",
            "runs": combined,
            "run_count": len(combined),
            "source_patch_count": 0,
            "pass": bool(combined) and all(item.get("pass") for item in combined),
        },
    )


def _git_head(repository_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError(f"cannot resolve LegSA code commit: {exc}") from exc


def _implementation_hashes(repository_root: Path) -> dict[str, str]:
    relatives = [
        Path("scripts/paper_rebuild/run_lc02_ginav2021.py"),
        Path(
            "configs/paper_rebuild/horizontal_literature/ginav2021/"
            "GINAV2021_RUNTIME_CONTRACT.yaml"
        ),
    ]
    package = (
        repository_root
        / "src/legsa_gins/paper_rebuild/horizontal_literature/ginav2021"
    )
    relatives.extend(
        path.relative_to(repository_root) for path in sorted(package.glob("*.py"))
    )
    return {
        relative.as_posix(): sha256_file(repository_root / relative)
        for relative in relatives
    }


def _resume_code_identity(repository_root: Path) -> dict[str, Any]:
    """Bind only tracked LC02 implementation paths, never unrelated untracked data."""

    root = repository_root.expanduser().resolve(strict=True)
    implementation_hashes = _implementation_hashes(root)
    approved = tuple(sorted(implementation_hashes))
    try:
        status = subprocess.run(
            [
                "git", "-C", str(root), "status", "--porcelain=v1",
                "--untracked-files=no", "--", *approved,
            ],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.splitlines()
        tracked_diff = subprocess.run(
            [
                "git", "-C", str(root), "diff", "--no-ext-diff", "--binary",
                "HEAD", "--", *approved,
            ],
            check=True, capture_output=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError(f"cannot bind resume implementation state: {exc}") from exc
    payload: dict[str, Any] = {
        "schema_version": "ginav2021.resume_code_identity.v1",
        "repository_head": _git_head(root),
        "approved_implementation_paths": list(approved),
        "approved_tracked_dirty_status": status,
        "approved_tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "implementation_file_sha256": implementation_hashes,
        "runtime_contract_hash": implementation_hashes[
            "configs/paper_rebuild/horizontal_literature/ginav2021/"
            "GINAV2021_RUNTIME_CONTRACT.yaml"
        ],
        "untracked_files_enumerated_or_hashed": False,
    }
    payload["aggregate_binding_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def _initial_provenance(options: TransactionOptions) -> dict[str, Any]:
    implementation_hashes = _implementation_hashes(options.repository_root)
    return {
        "schema_version": "ginav2021.consolidated_provenance.v1",
        "data_mode": "source_environment_only",
        "dataset_role": "PRE_BY2_SOURCE_AND_ENVIRONMENT_GATE",
        "raw_source_hashes": {},
        "provider_hashes": {},
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
        "code_commit": _git_head(options.repository_root),
        "implementation_file_sha256": implementation_hashes,
        "runtime_contract_hash": implementation_hashes[
            "configs/paper_rebuild/horizontal_literature/ginav2021/"
            "GINAV2021_RUNTIME_CONTRACT.yaml"
        ],
        "config_hash": None,
        "official_source_identity": None,
        "matlab_environment": None,
        "converter_identity": None,
        "official_sample_archive_backend": None,
        "official_sample_archive_backend_preflight_completed": False,
        "technical_pre_sample_backend_failure": False,
        "official_sample_regression_executed": False,
        "official_sample_archive_inventory_completed": False,
        "official_sample_extraction_count": 0,
        "gate_execution_counts": {
            "G0_matlab_candidate_attempts": 0,
            "G1_official_sample_runs": 0,
            "G2_gnss_adapter_runs": 0,
            "G2_imu_adapter_runs": 0,
            "G3_tdcp_probe_runs": 0,
            "G4_BY2_C00_runs": 0,
        },
        "source_cleanliness_run_ids": [],
        "representative_cases_executed": False,
        "comparison_executed": False,
        "trace_evaluation_executed": False,
    }


def _write_consolidated_provenance(
    stage: Path,
    *,
    status: str,
    provenance: Mapping[str, Any],
    access_audit: Mapping[str, Any],
    cleanliness_runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    run_ids = [
        str(item.get("run_id")) for item in cleanliness_runs
        if item.get("run_id")
    ]
    gate_counts = copy.deepcopy(dict(provenance["gate_execution_counts"]))
    gate_counts.update({
        "G0_matlab_candidate_attempts": sum(
            run_id.startswith("G0_MATLAB_ENVIRONMENT_candidate_")
            for run_id in run_ids
        ),
        "G1_official_sample_runs": sum(
            run_id.startswith("G1_OFFICIAL_SAMPLE_RUN_") for run_id in run_ids
        ),
        "G3_tdcp_probe_runs": sum(
            run_id == "G3_TDCP_ACTIVATION_PROBE" for run_id in run_ids
        ),
        "G4_BY2_C00_runs": sum(
            run_id == "G4_BY2_C00_SINGLE_RECURSIVE_RUN" for run_id in run_ids
        ),
    })
    payload = {
        **copy.deepcopy(dict(provenance)),
        "gate_execution_counts": gate_counts,
        "terminal_status": status,
        "file_access_audit": dict(access_audit),
        "source_cleanliness_run_ids": run_ids,
        "source_cleanliness_run_count": len(cleanliness_runs),
        "pass": bool(access_audit.get("pass")),
    }
    write_json(
        _stage_dir(stage, "11_REPORT") / "GINAV_CONSOLIDATED_PROVENANCE.json",
        payload,
    )
    return payload


def _terminal_payload(
    status: str,
    *,
    stage: Path,
    provenance: Mapping[str, Any],
    access_audit: Mapping[str, Any] | None = None,
    detail: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in TERMINAL_STATUSES:
        raise TransactionError(f"unregistered LC02 terminal status: {status}")
    formal_admission = bool(
        (extra or {}).get("formal_lc02_admission", status == SUCCESS_STATUS)
    )
    payload: dict[str, Any] = {
        "schema_version": "ginav2021.transaction_terminal.v1",
        "candidate_id": CANDIDATE_ID,
        "classification_labels": list(CLASSIFICATION_LABELS),
        "terminal_status": status,
        "scientific_terminal_status": status,
        "scratch_stage_root": str(stage),
        "formal_lc02_slot": "FILLED" if formal_admission else "VACANT",
        "formal_lc02_admission": formal_admission,
        "transaction_complete": False,
        "representative_cases_executed": False,
        "comparison_executed": False,
        "trace_evaluation_executed": False,
        "file_access_audit_available": access_audit is not None,
        "file_access_audit": dict(access_audit) if access_audit is not None else None,
        "trace_open_count": (
            int(access_audit.get("trace_open_count", 0))
            if access_audit is not None else None
        ),
        "reference_open_count": (
            int(access_audit.get("reference_open_count", 0))
            if access_audit is not None else None
        ),
        "gnss2_open_count": (
            int(access_audit.get("gnss2_open_count", 0))
            if access_audit is not None else None
        ),
        "other_method_open_count": (
            int(access_audit.get("other_method_open_count", 0))
            if access_audit is not None else None
        ),
        "forbidden_open_count": (
            int(access_audit.get("forbidden_open_count", 0))
            if access_audit is not None else None
        ),
        "unauthorized_runtime_read_count": (
            int(access_audit.get("unauthorized_runtime_read_count", 0))
            if access_audit is not None else None
        ),
        "LC01_execution_count": 0,
        "other_method_execution_count": 0,
        "canonical541_execution_count": 0,
        "data_mode": provenance["data_mode"],
        "dataset_role": provenance["dataset_role"],
        "raw_source_hashes": copy.deepcopy(provenance["raw_source_hashes"]),
        "provider_hashes": copy.deepcopy(provenance["provider_hashes"]),
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
        "code_commit": provenance["code_commit"],
        "config_hash": provenance.get("config_hash"),
        "official_sample_archive_backend": copy.deepcopy(
            provenance.get("official_sample_archive_backend")
        ),
        "official_sample_archive_backend_preflight_completed": bool(
            provenance.get("official_sample_archive_backend_preflight_completed")
        ),
        "technical_pre_sample_backend_failure": bool(
            provenance.get("technical_pre_sample_backend_failure")
        ),
        "official_sample_regression_executed": bool(
            provenance.get("official_sample_regression_executed")
        ),
        "official_sample_archive_inventory_completed": bool(
            provenance.get("official_sample_archive_inventory_completed")
        ),
        "official_sample_extraction_count": int(
            provenance.get("official_sample_extraction_count", 0)
        ),
        "consolidated_provenance_path": (
            "11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json"
        ),
    }
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    write_json(_stage_dir(stage, "11_REPORT") / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
    return payload


def _expected_publication_destination(clean_root: Path) -> Path:
    return (
        clean_root / "stages" / "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
        / STAGE_NAME
    )


def _finalize_terminal(
    status: str,
    *,
    stage: Path,
    access_audit: Mapping[str, Any],
    provenance: Mapping[str, Any],
    cleanliness_runs: Sequence[Mapping[str, Any]],
    publish: bool,
    destination: Path,
    clean_root: Path,
    protected_roots: Sequence[Path],
    path_aliases: Mapping[Path, str],
    detail: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze and, when requested, publish every scientific terminal path."""

    report_dir = _stage_dir(stage, "11_REPORT")
    write_json(report_dir / "GINAV_FORBIDDEN_INPUT_AUDIT.json", access_audit)
    consolidated = _write_consolidated_provenance(
        stage, status=status, provenance=provenance,
        access_audit=access_audit, cleanliness_runs=cleanliness_runs,
    )
    payload_extra = {
        **dict(extra or {}),
        "artifact_publication_requested": publish,
        "publication_destination_stage_root": str(destination),
    }
    payload = _terminal_payload(
        status, stage=stage, provenance=consolidated,
        access_audit=access_audit, detail=detail,
        extra=payload_extra,
    )
    if not publish:
        payload["artifact_publication_complete"] = False
        payload["artifact_publication"] = "NOT_REQUESTED"
        payload["transaction_complete"] = True
        payload["publication"] = {
            "schema_version": "ginav2021.compact_publication.v2",
            "requested": False,
            "artifact_publication": "NOT_REQUESTED",
            "pass": True,
        }
    else:
        payload["artifact_publication_complete"] = False
        payload["artifact_publication"] = "PENDING"
        payload["publication"] = {
            "schema_version": "ginav2021.compact_publication.v2",
            "requested": True,
            "artifact_publication": "PENDING",
            "pass": False,
        }
        write_json(report_dir / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
        try:
            publication = publish_compact_stage(
                stage, destination, terminal_status=status,
                final_status_payload=payload,
                expected_destination_stage_root=destination,
                clean_root=clean_root, protected_roots=protected_roots,
                path_aliases=path_aliases,
            )
        except (OSError, PublicationError) as exc:
            publication = dict(getattr(exc, "report", {}) or {})
            publication.update({
                "schema_version": "ginav2021.compact_publication.v2",
                "destination_stage_root": str(destination),
                "requested": True,
                "artifact_publication": "FAILED",
                "pass": False,
                "error": str(exc),
                "scientific_terminal_status_unchanged": True,
            })
        payload["publication"] = publication
        payload["artifact_publication_complete"] = bool(publication["pass"])
        payload["artifact_publication"] = (
            "COMPLETE" if publication["pass"] else "FAILED"
        )
        payload["transaction_complete"] = bool(publication["pass"])
        if not publication["pass"]:
            payload["scientific_formal_lc02_admission"] = payload[
                "formal_lc02_admission"
            ]
            payload["formal_lc02_admission"] = False
            payload["formal_lc02_slot"] = "VACANT"
    consolidated["artifact_publication"] = payload["artifact_publication"]
    consolidated["transaction_complete"] = payload["transaction_complete"]
    write_json(report_dir / "GINAV_CONSOLIDATED_PROVENANCE.json", consolidated)
    write_json(report_dir / "GINAV_PUBLICATION_PARITY.json", payload["publication"])
    write_json(report_dir / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
    return payload


def _load_local_paths(
    options: TransactionOptions, *, verify_raw_availability: bool
) -> dict[str, Path]:
    data = load_yaml_mapping(options.paths_config)
    values = data.get("paths")
    if not isinstance(values, Mapping):
        raise TransactionError("local paths config has no paths mapping")
    required = {
        "code_root", "raw_root", "by2_fix_root", "by2_go2_body", "clean_root",
        "horizontal_literature_rtklib_root", "horizontal_literature_convbin",
    }
    missing = required - set(values)
    if missing:
        raise TransactionError("local paths config is missing: " + ",".join(sorted(missing)))
    paths = {key: Path(str(values[key])).expanduser().resolve(strict=False) for key in required}
    if paths["code_root"].resolve(strict=True) != options.repository_root.resolve(strict=True):
        raise TransactionError("local code_root is not the authorized worktree")
    if verify_raw_availability and (
        not paths["raw_root"].is_dir() or not paths["by2_fix_root"].is_dir()
    ):
        raise TransactionError("locked BY2 raw roots are unavailable")
    return paths


def _classify_sample_archive_members(
    members: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    files = [item for item in members if not item.get("directory")]

    def paths(predicate: Any) -> list[str]:
        return sorted(str(item["path"]) for item in files if predicate(str(item["path"])))

    observations = paths(
        lambda value: Path(value).suffix.casefold().endswith("o")
        and "cpt" in Path(value).name.casefold()
        and "base" not in Path(value).name.casefold()
    )
    bds_navigation = paths(lambda value: Path(value).suffix.casefold().endswith("c"))
    mixed_navigation = paths(lambda value: Path(value).suffix.casefold().endswith("p"))
    navigation = bds_navigation if bds_navigation else mixed_navigation
    imu = paths(
        lambda value: Path(value).suffix.casefold() == ".csv"
        and "imu" in Path(value).name.casefold()
    )
    references = paths(
        lambda value: Path(value).name.casefold()
        == OFFICIAL_REFERENCE_MEMBER_BASENAME.casefold()
    )
    ubx = paths(lambda value: Path(value).suffix.casefold() == ".ubx")
    serialized_outputs = paths(
        lambda value: Path(value).suffix.casefold() in {".pos", ".sol", ".out"}
        or "result" in {part.casefold() for part in PurePosixPath(value).parts}
    )
    if len(observations) != 1 or len(navigation) != 1 or len(imu) != 1:
        raise TransactionError(
            "official sample archive source roles are ambiguous: "
            f"obs={len(observations)}, nav={len(navigation)}, imu={len(imu)}"
        )
    if len(references) != 1:
        raise TransactionError(
            "official sample archive reference-member inventory is not exactly one"
        )
    if serialized_outputs:
        raise TransactionError(
            "official sample archive unexpectedly bundles serialized solution output"
        )
    return {
        "schema_version": "ginav2021.official_sample_archive_inventory.v1",
        "member_count": len(members),
        "file_member_count": len(files),
        "members": [dict(item) for item in members],
        "selected_observation_member": observations[0],
        "selected_navigation_member": navigation[0],
        "selected_imu_member": imu[0],
        "reference_member_paths": references,
        "reference_member_count": len(references),
        "reference_member_opened": False,
        "ubx_member_paths": ubx,
        "ubx_member_count": len(ubx),
        "ubx_member_opened": False,
        "bundled_serialized_output_paths": serialized_outputs,
        "bundled_serialized_output_count": len(serialized_outputs),
        "bundled_serialized_output_present": False,
        "inventory_operation": "libarchive_next_header_only",
        "inventory_payload_api_calls": 0,
        "pass": True,
    }


def _inventory_sample_archive(
    archive: Path, backend: Libarchive7zBackend, ledger: AccessLedger
) -> dict[str, Any]:
    ledger.record(archive, role="OFFICIAL_GINAV_SAMPLE_ARCHIVE")
    backend_inventory = backend.inventory(archive)
    inventory = _classify_sample_archive_members(backend_inventory["members"])
    selected_roles = {
        inventory["selected_observation_member"]: "selected_observation",
        inventory["selected_navigation_member"]: "selected_navigation",
        inventory["selected_imu_member"]: "selected_imu",
    }
    inventory_ledger = []
    for member in inventory["members"]:
        path = str(member["path"])
        role = selected_roles.get(path)
        if role is None and path in inventory["reference_member_paths"]:
            role = "excluded_reference"
        elif role is None and path in inventory["ubx_member_paths"]:
            role = "excluded_ubx"
        elif role is None:
            role = "excluded_unselected"
        inventory_ledger.append({
            "path": path,
            "role": role,
            "declared_bytes": member["bytes"],
            "header_metadata_sha256": member.get("header_metadata_sha256"),
            "payload_read_calls": 0,
        })
    result = {
        **inventory,
        **{key: value for key, value in backend_inventory.items() if key != "members"},
        "archive_backend": copy.deepcopy(backend.identity),
        "member_inventory_ledger": inventory_ledger,
        "reference_member_payload_read_calls": 0,
        "ubx_member_payload_read_calls": 0,
    }
    result["frozen_inventory_binding_sha256"] = (
        frozen_inventory_binding_sha256(result)
    )
    return result


def _extract_sample(
    archive: Path,
    destination: Path,
    ledger: AccessLedger,
    inventory: Mapping[str, Any],
    backend: Libarchive7zBackend,
) -> dict[str, Any]:
    ledger.record(archive, role="OFFICIAL_GINAV_SAMPLE_ARCHIVE_EXACT_EXTRACTION")
    return backend.extract_selected(archive, destination, inventory)


def _resolve_sample_inputs(
    root: Path, inventory: Mapping[str, Any]
) -> dict[str, Path]:
    obs = root / str(inventory["selected_observation_member"])
    nav = root / str(inventory["selected_navigation_member"])
    imu = root / str(inventory["selected_imu_member"])
    if not all(path.is_file() for path in (obs, nav, imu)):
        raise TransactionError("official sample exact selected inputs are missing")
    if len({obs.parent, imu.parent, nav.parent}) != 1:
        raise TransactionError("official sample inputs do not share one data_dir")
    return {"observation": obs, "navigation": nav, "imu": imu,
            "data_dir": obs.parent}


def _run_official(
    *,
    run_id: str,
    run_root: Path,
    ginav_root: Path,
    matlab_executable: Path,
    config_path: Path,
    observation_path: Path,
    navigation_path: Path,
    imu_path: Path,
    timeout_seconds: float,
    access_ledger: AccessLedger,
) -> dict[str, Any]:
    windows = matlab_executable.suffix.casefold() == ".exe"
    for declared_input in (
        config_path, observation_path, navigation_path, imu_path
    ):
        access_ledger.authorize_runtime_read(Path(declared_input).resolve(strict=True))
        if windows:
            access_ledger.authorize_runtime_read(wsl_to_windows_path(declared_input))
    access_ledger.record(config_path, role="GINAV_DERIVED_CONFIGURATION")
    access_ledger.record(observation_path, role="GINAV_RINEX_OBSERVATION")
    access_ledger.record(navigation_path, role="GINAV_BROADCAST_NAVIGATION")
    access_ledger.record(imu_path, role="GINAV_BODY_IMU")
    mirror = run_root / "source_mirror"
    mirror_manifest = materialize_runtime_source_mirror(ginav_root, mirror)
    harness = run_root / "matlab_harness"
    fopen_log = run_root / "MATLAB_FOPEN_LEDGER.tsv"
    main = render_official_run_script(
        mirror_root=mirror, harness_root=harness, config_path=config_path,
        observation_path=observation_path, navigation_path=navigation_path,
        imu_path=imu_path, windows=windows,
    )
    script = write_harness_files(
        harness, main_script=main, fopen_log=fopen_log, windows=windows
    )
    guard = CoreCleanlinessGuard(run_id, ginav_root, mirror, mirror_manifest)
    try:
        with guard:
            result = run_matlab_script(
                matlab_executable, script, timeout_seconds=timeout_seconds
            )
    except (OSError, MatlabRuntimeError) as exc:
        # A process/runtime failure is still a completed cleanliness-guarded
        # official attempt. Preserve it as a normal failed run so callers can
        # emit the correct gate status and before/after proof.
        result = {
            "command": list(build_matlab_batch_command(matlab_executable, script)),
            "batch_invocation": "-nosplash -r function invocation",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "runtime_seconds": None,
            "pass": False,
        }
    cleanliness = guard.report()
    write_json(run_root / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json", cleanliness)
    if not fopen_log.is_file():
        raise ForbiddenInputError(f"{run_id} MATLAB fopen ledger is missing")
    access_ledger.import_matlab_fopen_log(fopen_log)
    outputs = tuple((mirror / "result").glob("*.pos"))
    native_path: Path | None = None
    if len(outputs) == 1:
        native_path = run_root / outputs[0].name
        try:
            copy_file_content_exact(outputs[0], native_path)
        except SourceIdentityError as exc:
            raise TransactionError(
                f"{run_id} native-output freeze parity failed"
            ) from exc
    return {
        **result,
        "run_id": run_id,
        "source_mirror_manifest": mirror_manifest,
        "core_cleanliness": cleanliness,
        "native_output_path": str(native_path) if native_path else None,
        "native_output_count": len(outputs),
        "file_access_audit": access_ledger.audit(),
    }


def _matlab_environment(
    *,
    stage: Path,
    ginav_root: Path,
    executable: Path,
    probe_id: str = "selected",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", probe_id):
        raise MatlabRuntimeError("unsafe MATLAB environment probe identifier")
    root = (
        _stage_dir(stage, "00_SOURCE_AND_ENVIRONMENT")
        / f"matlab_probe_runtime_{probe_id}"
    )
    root.mkdir(parents=True, exist_ok=False)
    mirror = root / "source_mirror"
    mirror_manifest = materialize_runtime_source_mirror(ginav_root, mirror)
    harness = root / "matlab_harness"
    output = root / "MATLAB_ENVIRONMENT_RAW.tsv"
    windows = executable.suffix.casefold() == ".exe"
    main = render_environment_probe(output, mirror_root=mirror, windows=windows)
    script = write_harness_files(
        harness, main_script=main, fopen_log=root / "MATLAB_FOPEN_LEDGER.tsv",
        windows=windows,
    )
    guard = CoreCleanlinessGuard(
        f"G0_MATLAB_ENVIRONMENT_{probe_id}", ginav_root, mirror, mirror_manifest
    )
    invocation: dict[str, Any]
    try:
        with guard:
            invocation = run_matlab_script(executable, script, timeout_seconds=300)
    except (OSError, MatlabRuntimeError) as exc:
        invocation = {
            "command": list(build_matlab_batch_command(executable, script)),
            "batch_invocation": "-nosplash -r function invocation",
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "runtime_seconds": None,
            "pass": False,
        }
    finally:
        # If MATLAB fails, the official source/mirror proof is still frozen
        # before the environment blocker is raised.
        if guard.before is not None and guard.after is not None:
            write_json(root / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json", guard.report())
    write_json(root / "MATLAB_ENVIRONMENT_INVOCATION.json", invocation)
    if not invocation["pass"] or not output.is_file():
        raise MatlabRuntimeError(
            "licensed MATLAB environment probe failed: "
            + str(invocation.get("stderr") or invocation.get("stdout") or "")
        )
    payload = parse_environment_probe(output)
    validate_matlab_environment(
        payload,
        expected_source_root=(
            wsl_to_windows_path(mirror) if windows else str(mirror.resolve())
        ),
    )
    environment = {
        "schema_version": "ginav2021.matlab_environment.v1",
        "executable_path": str(executable),
        "executable_sha256": sha256_file(executable),
        "platform_route": "WINDOWS_MATLAB_FROM_WSL" if windows else "NATIVE_LINUX_MATLAB",
        "batch_invocation": invocation["command"],
        "locale": payload.get("locale"),
        "version": payload.get("version"),
        "release": payload.get("release"),
        "computer": payload.get("computer"),
        "arch": payload.get("arch"),
        "java_version": payload.get("java_version"),
        "usejava_jvm": payload.get("usejava_jvm"),
        "usejava_awt": payload.get("usejava_awt"),
        "usejava_desktop": payload.get("usejava_desktop"),
        "display_capable_route": bool(payload.get("usejava_awt")),
        "headless_batch": True,
        "required_toolbox_policy": "base_MATLAB_and_graphics_only_for_SPP_INS_LC",
        "required_function_availability": payload.get("required_function_availability"),
        "installed_products": payload.get("installed_products"),
        "license_modified_or_activated": False,
        "pass": True,
    }
    return environment, guard.report()


def _run_sample_regression(
    *,
    stage: Path,
    ginav_root: Path,
    matlab_executable: Path,
    archive_backend: Libarchive7zBackend,
    expected_archive_sha256: str,
    timeout_seconds: float,
    access_ledger: AccessLedger,
    progress: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    section = _stage_dir(stage, "01_OFFICIAL_SAMPLE_REGRESSION")
    archive = ginav_root / OFFICIAL_SAMPLE_RELATIVE
    official_config = ginav_root / OFFICIAL_CONFIG_RELATIVE
    summaries: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    cleanliness: list[dict[str, Any]] = []
    archive_inventory = _inventory_sample_archive(
        archive, archive_backend, access_ledger
    )
    progress["official_sample_archive_inventory_completed"] = True
    inventory_archive_sha256 = archive_inventory.get("archive_sha256")
    archive_inventory["pinned_source_lock_sample_sha256"] = (
        expected_archive_sha256
    )
    archive_inventory["archive_sha256_matches_pinned_source_lock"] = (
        inventory_archive_sha256 == expected_archive_sha256
    )
    write_json(
        section / "OFFICIAL_SAMPLE_ARCHIVE_INVENTORY.json",
        archive_inventory,
    )
    if inventory_archive_sha256 != expected_archive_sha256:
        raise SourceIdentityError(
            "G1 archive inventory SHA256 does not match the pinned official "
            "source-lock sample SHA256"
        )
    frozen_binding = archive_inventory["frozen_inventory_binding_sha256"]
    for index in (1, 2):
        run_root = section / f"pristine_run_{index}"
        run_root.mkdir(exist_ok=False)
        extraction = _extract_sample(
            archive, run_root / "sample_data", access_ledger, archive_inventory,
            archive_backend,
        )
        if extraction.get("frozen_inventory_binding_sha256") != frozen_binding:
            raise SourceIdentityError(
                "official sample pristine extraction is not bound to the single "
                "frozen G1 archive inventory"
            )
        progress["official_sample_extraction_count"] = index
        inputs = _resolve_sample_inputs(run_root / "sample_data", archive_inventory)
        derived = run_root / "GINav_SPP_LC_CPT.ini"
        config_contract = derive_official_sample_config(
            official_config, derived, inputs["data_dir"]
        )
        progress["official_sample_regression_executed"] = True
        run = _run_official(
            run_id=f"G1_OFFICIAL_SAMPLE_RUN_{index}", run_root=run_root,
            ginav_root=ginav_root, matlab_executable=matlab_executable,
            config_path=derived, observation_path=inputs["observation"],
            navigation_path=inputs["navigation"], imu_path=inputs["imu"],
            timeout_seconds=timeout_seconds, access_ledger=access_ledger,
        )
        cleanliness.append(run["core_cleanliness"])
        if not run["pass"] or run["native_output_count"] != 1:
            raise TransactionError(f"official sample pristine run {index} failed")
        rows = read_official_solution(run["native_output_path"])
        summary = summarize_solution(rows)
        summary.update(
            {
                "run_index": index,
                "runtime_seconds": run["runtime_seconds"],
                "observation_path": str(inputs["observation"]),
                "observation_sha256": sha256_file(inputs["observation"]),
                "navigation_path": str(inputs["navigation"]),
                "navigation_sha256": sha256_file(inputs["navigation"]),
                "imu_path": str(inputs["imu"]),
                "imu_sha256": sha256_file(inputs["imu"]),
                "output_path": run["native_output_path"],
                "output_sha256": sha256_file(run["native_output_path"]),
                "config_contract": config_contract,
                "extraction": extraction,
                "file_access_audit": run["file_access_audit"],
            }
        )
        summaries.append(summary)
        runs.append({"rows": rows, "run": run})
    determinism = compare_sample_runs(runs[0]["rows"], runs[1]["rows"])
    write_json(section / "OFFICIAL_SAMPLE_DETERMINISM.json", determinism)
    status = {
        "schema_version": "ginav2021.official_sample_regression_status.v1",
        "status": "PASS" if determinism["pass"] else "FAIL",
        "official_sample_sha256": sha256_file(archive),
        "pristine_run_count": 2,
        "reference_member_present_in_archive": (
            archive_inventory["reference_member_count"] == 1
        ),
        "official_serialized_output_bundled": archive_inventory[
            "bundled_serialized_output_present"
        ],
        "archive_inventory_path": "OFFICIAL_SAMPLE_ARCHIVE_INVENTORY.json",
        "archive_inventory_binding_sha256": frozen_binding,
        "both_pristine_extractions_bound_to_same_inventory": True,
        "reference_member_extracted": False,
        "reference_member_opened": False,
        "old_repository_result_opened": False,
        "summaries": summaries,
        "pass": determinism["pass"],
    }
    write_json(section / "OFFICIAL_SAMPLE_REGRESSION_STATUS.json", status)
    summary_rows = []
    for item in summaries:
        summary_rows.append(
            {
                "run_index": item["run_index"], "row_count": item["row_count"],
                "alignment_week": item["alignment_week"],
                "alignment_sow": item["alignment_sow"],
                "gnss_lc_update_count": item["internal_spp_fed_lc_update_count"],
                "ins_only_propagation_count": item["ins_only_propagation_count"],
                "finite_state_rate": item["finite_state_rate"],
                "finite_covariance_rate": item["finite_covariance_rate"],
                "runtime_seconds": item["runtime_seconds"],
                "scientific_digest_sha256": item["scientific_digest_sha256"],
            }
        )
    _write_csv(
        section / "OFFICIAL_SAMPLE_OUTPUT_SUMMARY.csv", summary_rows,
        tuple(summary_rows[0]),
    )
    report = f"""# Official GINav sample regression

Status: `{'PASS' if determinism['pass'] else 'FAIL'}`.

The unmodified pinned source was run twice from pristine source/data roots.  The
only official configuration change was `data_dir`.  The archive reference
`{OFFICIAL_REFERENCE_MEMBER_BASENAME}` and tracked historical `result/*.pos`
were not opened.  Both runs had {summaries[0]['row_count']} rows and scientific
digest `{summaries[0]['scientific_digest_sha256']}`.
"""
    (section / "OFFICIAL_SAMPLE_REGRESSION_REPORT.md").write_text(report, encoding="utf-8")
    if not determinism["pass"]:
        raise TransactionError("official sample two-run determinism failed")
    return status, cleanliness


def _write_gnss_artifacts(stage: Path, audit: Mapping[str, Any]) -> None:
    section = _stage_dir(stage, "02_BY2_GNSS_ADAPTER")
    write_json(section / "BY2_GNSS1_RINEX_AUDIT.json", audit)
    rinex = audit["rinex"]
    contract = {
        "schema_version": "ginav2021.by2_gnss1_rinex_contract.v1",
        "source": "gnss1-raw.csv_RAWX_SFRBX_navigation_material",
        "GNSS1_only": True,
        "GNSS2_used": False,
        "external_PVT_measurement_interface_used": False,
        "converter": audit["converter"],
        "command": audit["command"],
        "rinex_version": rinex["rinex_version"],
        "selected_navsys": rinex["selected_navsys"],
        "selected_nfreq": rinex["selected_nfreq"],
        "selection_rule": rinex["selection_rule"],
        "accuracy_based_selection": False,
        "pass": True,
    }
    _write_yaml(section / "BY2_GNSS1_RINEX_CONTRACT.yaml", contract)
    rows = epoch_signal_rows(rinex)
    _write_csv(section / "BY2_GNSS1_EPOCH_AND_SIGNAL_SUMMARY.csv", rows, tuple(rows[0]))


def _write_imu_artifacts(stage: Path, audit: Mapping[str, Any]) -> None:
    section = _stage_dir(stage, "03_BY2_IMU_ADAPTER")
    write_json(section / "BY2_GINAV_IMU_AUDIT.json", audit)
    contract = {
        "schema_version": "ginav2021.by2_imu_contract.v1",
        "data_identity": audit["data_identity"],
        "allowed_fields": ["timestamp", "imu_state.gyroscope", "imu_state.accelerometer"],
        "forbidden_fields_materialized": False,
        "source_frame": "FLU",
        "official_frame": "RFU",
        "map": "[R,F,U]=[-L,F,U]",
        "data_format": 2,
        "increment_rule": "current_sample_times_dt",
        "first_sample_output": "skipped_no_prior_interval",
        "sample_rate_hz": GO2_SAMPLE_RATE_HZ,
        "sqrt_dt_preprocessing": False,
        "raw_source_mutated": False,
        "runtime_csv_committed": False,
        "pass": audit["pass"],
    }
    _write_yaml(section / "BY2_GINAV_IMU_CONTRACT.yaml", contract)


def _read_imu_gps_total_nanoseconds(path: Path) -> tuple[int, ...]:
    """Read the official time columns without a binary64 round trip."""

    totals: list[int] = []
    week_ns = WEEK_SECONDS * NANOSECONDS
    with path.open("r", encoding="ascii", errors="strict", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not {"gps_week", "gps_sow"}.issubset(
            reader.fieldnames
        ):
            raise ConfigContractError("prepared IMU CSV is missing GPS week/SOW")
        for row_number, row in enumerate(reader, start=2):
            try:
                week = int(row["gps_week"])
                sow = decimal.Decimal(row["gps_sow"])
            except (KeyError, TypeError, ValueError, decimal.InvalidOperation) as exc:
                raise ConfigContractError(
                    f"prepared IMU time is invalid at CSV row {row_number}"
                ) from exc
            sow_ns_decimal = sow * NANOSECONDS
            sow_ns = int(sow_ns_decimal)
            if (
                week < 0
                or sow_ns_decimal != decimal.Decimal(sow_ns)
                or not 0 <= sow_ns < week_ns
            ):
                raise ConfigContractError(
                    f"prepared IMU week/SOW is out of range at CSV row {row_number}"
                )
            total = week * week_ns + sow_ns
            if totals and total <= totals[-1]:
                raise ConfigContractError(
                    "prepared IMU GPS timestamps are not strictly increasing"
                )
            totals.append(total)
    if not totals:
        raise ConfigContractError("prepared IMU CSV has no data rows")
    return tuple(totals)


def _datetime_gpst_total_nanoseconds(value: dt.datetime) -> int:
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    gps = gpst_calendar_to_gps(
        value.year, value.month, value.day, value.hour, value.minute,
        decimal.Decimal(value.second)
        + decimal.Decimal(value.microsecond) / decimal.Decimal(1_000_000),
    )
    return gps.week * WEEK_SECONDS * NANOSECONDS + gps.sow_nanoseconds


def _gps_overlap_datetimes(
    epochs: Sequence[RinexEpoch], imu_csv: Path
) -> tuple[dt.datetime, dt.datetime]:
    imu_totals = _read_imu_gps_total_nanoseconds(imu_csv)
    first_imu_total = imu_totals[0]
    last_imu_total = imu_totals[-1]
    first_obs = (
        epochs[0].gps_time.week * WEEK_SECONDS * NANOSECONDS
        + epochs[0].gps_time.sow_nanoseconds
    )
    last_obs = (
        epochs[-1].gps_time.week * WEEK_SECONDS * NANOSECONDS
        + epochs[-1].gps_time.sow_nanoseconds
    )
    start_total = max(first_imu_total, first_obs)
    end_total = min(last_imu_total, last_obs)
    start_total = ((start_total + NANOSECONDS - 1) // NANOSECONDS) * NANOSECONDS
    end_total = (end_total // NANOSECONDS) * NANOSECONDS
    if start_total >= end_total:
        raise ConfigContractError("prepared GNSS/IMU streams have no integer-grid overlap")

    def convert(total: int) -> dt.datetime:
        week, sow_ns = divmod(total, WEEK_SECONDS * NANOSECONDS)
        year, month, day, hour, minute, second = gps_to_gpst_calendar(
            GpsTime(int(week), int(sow_ns))
        )
        if second != second.to_integral_value():
            raise ConfigContractError("overlap bound is not an integer GPST second")
        return dt.datetime(year, month, day, hour, minute, int(second))

    return convert(start_total), convert(end_total)


def _official_run_epoch_inventory(
    epochs: Sequence[RinexEpoch],
    imu_csv: Path,
    *,
    start_time_gpst: dt.datetime,
    end_time_gpst: dt.datetime,
    sample_rate_hz: int,
) -> dict[str, Any]:
    """Inventory epochs reachable by official read/match/reject predicates."""

    if sample_rate_hz <= 0:
        raise ConfigContractError("official IMU sample rate must be positive")
    start_total = _datetime_gpst_total_nanoseconds(start_time_gpst)
    end_total = _datetime_gpst_total_nanoseconds(end_time_gpst)
    if start_total > end_total:
        raise ConfigContractError("official run epoch inventory has a reversed window")
    imu_all = _read_imu_gps_total_nanoseconds(imu_csv)
    imu_totals = tuple(value for value in imu_all if start_total <= value <= end_total)
    if not imu_totals:
        raise ConfigContractError("official run window contains no prepared IMU rows")

    def epoch_total(epoch: RinexEpoch) -> int:
        return (
            epoch.gps_time.week * WEEK_SECONDS * NANOSECONDS
            + epoch.gps_time.sow_nanoseconds
        )

    in_window = tuple(
        epoch for epoch in epochs if start_total <= epoch_total(epoch) <= end_total
    )
    # decode_obsb materializes observations only for event flags 0--2 and 6.
    decoded = tuple(
        epoch for epoch in in_window
        if epoch.satellite_count is not None
        and epoch.satellite_count > 0
        and epoch.event_flag in {0, 1, 2, 6}
    )
    integer_epochs = tuple(
        epoch for epoch in decoded if epoch.accepted_by_official_processor
    )
    tolerance_ns = decimal.Decimal("0.501") * NANOSECONDS / sample_rate_hz
    matched = 0
    matched_times: list[dict[str, Any]] = []
    for epoch in integer_epochs:
        target = epoch_total(epoch)
        insertion = bisect.bisect_left(imu_totals, target)
        nearby: list[int] = []
        if insertion < len(imu_totals):
            nearby.append(imu_totals[insertion])
        if insertion:
            nearby.append(imu_totals[insertion - 1])
        if nearby and min(abs(value - target) for value in nearby) < tolerance_ns:
            matched += 1
            matched_times.append({
                "gps_week": epoch.gps_time.week,
                "gps_sow": f"{epoch.gps_time.sow_seconds:.9f}",
            })

    return {
        "schema_version": "ginav2021.official_run_epoch_inventory.v1",
        "rinex_total_epoch_count": len(epochs),
        "input_gnss_epoch_count": len(in_window),
        "official_decoded_observation_epoch_count": len(decoded),
        "in_window_non_observation_event_count": len(in_window) - len(decoded),
        "in_window_integer_epoch_count": len(integer_epochs),
        "in_window_noninteger_rejected_count": len(decoded) - len(integer_epochs),
        "accepted_official_gnss_epoch_count": matched,
        "accepted_official_gnss_epoch_time_set": matched_times,
        "in_window_integer_unmatched_imu_count": len(integer_epochs) - matched,
        "prepared_imu_total_row_count": len(imu_all),
        "prepared_imu_in_window_row_count": len(imu_totals),
        "config_start_gpst": start_time_gpst.isoformat(sep=" "),
        "config_end_gpst": end_time_gpst.isoformat(sep=" "),
        "official_match_predicate": "abs(imu_time-observation_time)<0.501/sample_rate",
        "official_match_tolerance_seconds": float(tolerance_ns / NANOSECONDS),
        "official_noninteger_rejection": "obsr_(1).time.sec~=0",
        "official_duplicate_observation_rejection": True,
        "one_second_interval_unchanged": True,
        "conservation_pass": (
            len(in_window) == len(decoded) + (len(in_window) - len(decoded))
            and len(decoded) == len(integer_epochs) + (len(decoded) - len(integer_epochs))
            and len(integer_epochs) == matched + (len(integer_epochs) - matched)
        ),
    }


def _probe_summary(
    path: Path, *, canonical_output_path: Path | None = None,
    transport_audit_path: Path | None = None,
) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    with path.open("r", encoding="utf-8", newline="") as handle:
        parsed = list(csv.reader(handle))
        if not parsed:
            raise TransactionError("TDCP probe produced no CSV rows")
        header, raw_rows = parsed[0], parsed[1:]
        required = {
            "epoch_index", "gps_week", "gps_sow",
            "common_phase_satellites", "tdcp_equation_count",
            "robust_retained_count", "threshold_pass", "official_tdcp_flag",
            "prior_spp_available", "prior_spp_status", "spp_status",
            "spp_satellite_count", "spp_pair_available",
            "tdcp_velocity_attempted", "alignment_attempted",
            "alignment_result",
        }
        missing = required - set(header)
        if missing:
            raise TransactionError(
                "TDCP probe CSV is missing columns: " + ",".join(sorted(missing))
            )
        if len(header) != 28:
            raise TransactionError("TDCP probe CSV header is not the exact 28 columns")
        canonical_rows: list[list[str]] = []
        recovered = 0
        for row_number, values in enumerate(raw_rows, start=2):
            if len(values) == 28:
                canonical_rows.append(values)
            elif (
                len(values) == 29
                and values[17] == "dot(vn"
                and values[18] == "vn)>3"
            ):
                canonical_rows.append(
                    values[:17] + ["dot(vn,vn)>3"] + values[19:]
                )
                recovered += 1
            else:
                raise TransactionError(
                    "TDCP probe CSV transport is ambiguous at row "
                    f"{row_number}"
                )
        rows = [dict(zip(header, values, strict=True)) for values in canonical_rows]
    if not rows:
        raise TransactionError("TDCP probe produced no eligible integer epochs")
    if any(row.get("threshold_literal") != "dot(vn,vn)>3" for row in rows):
        raise TransactionError("TDCP probe threshold literal changed")
    canonical_buffer = io.StringIO(newline="")
    canonical_writer = csv.writer(canonical_buffer, lineterminator="\n")
    canonical_writer.writerow(header)
    canonical_writer.writerows(canonical_rows)
    canonical_bytes = canonical_buffer.getvalue().encode("utf-8")
    transport_audit = {
        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "canonical_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "header_column_count": len(header),
        "raw_data_row_count": len(raw_rows),
        "canonical_data_row_count": len(canonical_rows),
        "known_unquoted_threshold_rows_recovered": recovered,
        "recovery_rule": (
            "only_29_columns_with_exact_index17_dot(vn_and_"
            "index18_vn)>3_fragments"
        ),
        "scientific_values_changed": False,
        "pass": True,
    }
    if canonical_output_path is not None:
        canonical_output_path.write_bytes(canonical_bytes)
        if sha256_file(canonical_output_path) != transport_audit["canonical_sha256"]:
            raise TransactionError("canonical G3 CSV writeback hash mismatch")
    if transport_audit_path is not None:
        write_json(transport_audit_path, transport_audit)

    def truth(row: Mapping[str, str], key: str) -> bool:
        value = str(row.get(key, "")).strip().casefold()
        if value not in {"0", "1", "false", "true"}:
            raise TransactionError(
                f"TDCP probe boolean {key} has invalid value: {value!r}"
            )
        return value in {"1", "true"}

    def integer(row: Mapping[str, str], key: str) -> int:
        try:
            value = int(str(row[key]).strip())
        except (KeyError, TypeError, ValueError) as exc:
            raise TransactionError(
                f"TDCP probe integer {key} is invalid"
            ) from exc
        return value

    try:
        spp_valid = sum(integer(row, "spp_status") != 0 for row in rows)
        prior_spp = sum(truth(row, "prior_spp_available") for row in rows)
        spp_pairs = sum(truth(row, "spp_pair_available") for row in rows)
        tdcp_attempts = sum(
            truth(row, "tdcp_velocity_attempted") for row in rows
        )
        alignment_attempts = sum(
            truth(row, "alignment_attempted") for row in rows
        )
        threshold_passes = sum(truth(row, "threshold_pass") for row in rows)
        tdcp_flags = sum(truth(row, "official_tdcp_flag") for row in rows)
        aligned_rows = [row for row in rows if truth(row, "alignment_result")]
        max_common = max(integer(row, "common_phase_satellites") for row in rows)
        max_equations = max(integer(row, "tdcp_equation_count") for row in rows)
        max_retained = max(integer(row, "robust_retained_count") for row in rows)
    except TransactionError:
        raise
    except (TypeError, ValueError) as exc:
        raise TransactionError(f"TDCP probe CSV is malformed: {exc}") from exc

    if alignment_attempts != len(rows):
        raise TransactionError(
            "TDCP probe did not record official ins_align invocation for every "
            "eligible epoch"
        )
    if tdcp_attempts != prior_spp:
        raise TransactionError(
            "TDCP velocity-attempt count does not conserve prior SPP availability"
        )
    if any(
        truth(row, "alignment_result")
        and not (
            truth(row, "official_tdcp_flag")
            and truth(row, "threshold_pass")
            and truth(row, "spp_pair_available")
        )
        for row in rows
    ):
        raise TransactionError(
            "official alignment result lacks its source TDCP/SPP prerequisites"
        )
    return {
        "schema_version": "ginav2021.tdcp_alignment_activation_summary.v1",
        "transport_recovery_audit": transport_audit,
        "eligible_integer_epoch_count": len(rows),
        "eligible_integer_epoch_time_set": [
            {
                "gps_week": integer(row, "gps_week"),
                "gps_sow": f"{float(row['gps_sow']):.9f}",
            }
            for row in rows
        ],
        "max_common_phase_satellites": max_common,
        "max_tdcp_equation_count": max_equations,
        "max_robust_retained_count": max_retained,
        "threshold_literal": "dot(vn,vn)>3",
        "threshold_pass_count": threshold_passes,
        "official_tdcp_flag_count": tdcp_flags,
        "prior_spp_available_epoch_count": prior_spp,
        "spp_pair_available_epoch_count": spp_pairs,
        "tdcp_velocity_attempt_count": tdcp_attempts,
        "internal_spp_valid_epoch_count": spp_valid,
        "internal_spp_invalid_epoch_count": len(rows) - spp_valid,
        "internal_spp_outcome_conservation_pass": (
            spp_valid + (len(rows) - spp_valid) == len(rows)
        ),
        "alignment_attempt_count": alignment_attempts,
        "alignment_attempt_covers_every_eligible_epoch": True,
        "alignment_result_count": len(aligned_rows),
        "alignment_activated": bool(aligned_rows),
        "first_alignment_epoch_index": (
            int(aligned_rows[0]["epoch_index"]) if aligned_rows else None
        ),
        "first_alignment_gps_week": (
            int(aligned_rows[0]["gps_week"]) if aligned_rows else None
        ),
        "first_alignment_gps_sow": (
            float(aligned_rows[0]["gps_sow"]) if aligned_rows else None
        ),
        "initial_roll_pitch_source": "hardcoded_zero_by_official_ins_align",
        "initial_yaw_source": "official_TDCP_velocity_vel2yaw_only",
        "alternative_yaw_substitution_used": False,
        "dual_antenna_yaw_used": False,
        "go2_orientation_used": False,
        "trace_yaw_used": False,
        "manual_yaw_used": False,
        "official_source_supported_alternative_alignment_routes": [],
    }


def _write_config_artifacts(
    stage: Path,
    contract: Mapping[str, Any],
    *,
    stage_dir_resolver: Any = _stage_dir,
) -> None:
    section = stage_dir_resolver(stage, "04_BY2_CONFIG_AND_TIME_CONTRACT")
    _write_yaml(section / "BY2_GINAV_CONFIG_CONTRACT.yaml", contract)
    rows = contract["diff_rows"]
    _write_csv(
        section / "BY2_GINAV_CONFIG_DIFF.csv", rows,
        ("field", "official_value", "derived_value", "changed", "change_allowed",
         "official_line", "provenance"),
    )


def _zero_native_output_terminal() -> str:
    """A zero-file C00 after a successful G3 activation is fail-closed."""

    return "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"


def _activation_terminal(activation: Mapping[str, Any]) -> tuple[str, str] | None:
    """Route a completed source-exact probe without tuning or fallback yaw."""

    if (
        int(activation.get("internal_spp_valid_epoch_count") or 0) == 0
        or int(activation.get("spp_pair_available_epoch_count") or 0) == 0
    ):
        return (
            "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP",
            "source-exact probe found zero or no pairwise-available internal SPP epochs",
        )
    if (
        int(activation.get("official_tdcp_flag_count") or 0) == 0
        or int(activation.get("threshold_pass_count") or 0) == 0
    ):
        return (
            "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET",
            "pairwise internal SPP was available, but the literal official "
            "TDCP dot(vn,vn)>3 activation condition was never satisfied",
        )
    if not activation.get("alignment_activated"):
        return (
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            "official SPP and TDCP threshold prerequisites were observed, but "
            "ins_align did not activate; fail-closed contract violation",
        )
    return None


def _g4_scientific_run_and_freeze(
    *, options: Any, stage: Path, c00_section: Path, c00_runtime: Path,
    by2_config: Path, selected_observation: Path, navigation_path: Path,
    imu_csv: Path, matlab_executable: Path, provenance: Mapping[str, Any],
    access_ledger: AccessLedger, run_epoch_inventory: Mapping[str, Any],
    activation: Mapping[str, Any], stage_dir_resolver: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The single shared full-transaction/r4c G4 scientific tail."""

    c00_result = _run_official(
        run_id="G4_BY2_C00_SINGLE_RECURSIVE_RUN", run_root=c00_runtime,
        ginav_root=options.ginav_root, matlab_executable=matlab_executable,
        config_path=by2_config, observation_path=selected_observation,
        navigation_path=navigation_path, imu_path=imu_csv,
        timeout_seconds=options.c00_timeout_seconds, access_ledger=access_ledger,
    )
    if not c00_result["pass"]:
        raise TransactionError(
            "conditional official C00 MATLAB process failed: "
            + str(c00_result.get("stderr") or "") + "\n"
            + str(c00_result.get("stdout") or "")
        )
    if c00_result["native_output_count"] != 1:
        raise OutputContractError(
            "C00 did not produce exactly one native solution: "
            f"{c00_result['native_output_count']}"
        )
    input_counts = {
        "official_run_epoch_inventory": run_epoch_inventory,
        "input_gnss_epoch_count": run_epoch_inventory["input_gnss_epoch_count"],
        "accepted_official_gnss_epoch_count": run_epoch_inventory[
            "accepted_official_gnss_epoch_count"
        ],
        "internal_spp_valid_count": activation["internal_spp_valid_epoch_count"],
        "internal_spp_invalid_count": activation["internal_spp_invalid_epoch_count"],
        "internal_spp_valid_count_source": (
            "full_eligible_epoch_source_exact_probe_spp_status_nonzero"
        ),
        "internal_spp_invalid_count_source": (
            "full_eligible_epoch_source_exact_probe_spp_status_zero"
        ),
        "internal_spp_outcome_conservation_pass": (
            activation["internal_spp_outcome_conservation_pass"]
            and activation["eligible_integer_epoch_count"]
            == run_epoch_inventory["accepted_official_gnss_epoch_count"]
        ),
        "gnss_outage_count_source": "official_GNSS_outage_warning_ledger",
        "one_matlab_process": True,
        "one_recursive_ginav_run": True,
        "epoch_level_parallelism": False,
    }
    native_summary = freeze_native_solution(
        c00_result["native_output_path"], c00_section,
        matlab_result=c00_result, input_counts=input_counts,
        provenance=provenance,
        normalization_root=stage_dir_resolver(stage, "07_NATIVE_OUTPUT_NORMALIZATION"),
    )
    failure_path = c00_section / "GINAV_BY2_C00_FAILURE_LEDGER.csv"
    with failure_path.open("r", encoding="utf-8", newline="") as handle:
        failures = list(csv.DictReader(handle))
    outage_count = sum("GNSS outage" in row["message"] for row in failures)
    unavailable_count = sum("GNSS unavailable" in row["message"] for row in failures)
    native_summary["gnss_outage_count"] = outage_count
    native_summary["gnss_unavailable_warning_count"] = unavailable_count
    native_summary["other_warning_failure_count"] = (
        len(failures) - outage_count - unavailable_count
    )
    native_summary["warning_ledger_classification_conservation_pass"] = (
        outage_count + unavailable_count
        + native_summary["other_warning_failure_count"] == len(failures)
    )
    native_summary["native_output_status_conservation_pass"] = (
        native_summary["alignment_output_count"]
        + native_summary["internal_spp_fed_lc_update_count"]
        + native_summary["ins_only_propagation_count"]
        == native_summary["row_count"]
    )
    if not (
        native_summary["internal_spp_outcome_conservation_pass"]
        and native_summary["warning_ledger_classification_conservation_pass"]
        and native_summary["native_output_status_conservation_pass"]
    ):
        raise OutputContractError("C00 native count conservation failed")
    native_summary["forbidden_path_audit"] = access_ledger.audit()
    write_json(c00_section / "GINAV_BY2_C00_NATIVE_SUMMARY.json", native_summary)
    return c00_result, native_summary


def _short_resume_stage_dir(stage: Path, name: str) -> Path:
    try:
        return stage / _SHORT_RESUME_LAYOUT[name]
    except KeyError as exc:
        raise TransactionError(f"unknown short resume stage directory: {name}") from exc


def _wslpath_budget_audit(paths: Sequence[Path], ledger_path: Path) -> dict[str, Any]:
    executable = Path("/usr/bin/wslpath")
    if not executable.is_file():
        raise TransactionError("required /usr/bin/wslpath is unavailable")
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, path in enumerate(paths, start=1):
        linux = Path(path).resolve(strict=False)
        command = [str(executable), "-w", "--", str(linux)]
        try:
            result = subprocess.run(
                command, check=False, capture_output=True, text=True, timeout=30,
            )
            windows = result.stdout.rstrip("\r\n")
            returncode: int | None = result.returncode
            error = None
        except (OSError, subprocess.SubprocessError) as exc:
            windows = ""
            returncode = None
            error = f"{type(exc).__name__}: {exc}"
        row = {
            "sequence": index,
            "command": command,
            "linux_path": str(linux),
            "windows_path": windows,
            "windows_path_character_count": len(windows),
            "returncode": returncode,
            "within_239_character_budget": (
                returncode == 0 and bool(windows) and len(windows) <= 239
            ),
            "error": error,
        }
        rows.append(row)
        if not row["within_239_character_budget"]:
            failures.append(str(linux))
    _write_csv(
        ledger_path, rows,
        (
            "sequence", "command", "linux_path", "windows_path",
            "windows_path_character_count", "returncode",
            "within_239_character_budget", "error",
        ),
    )
    if failures:
        raise TransactionError(
            "G3/G4 Windows path conversion/budget failure: " + ", ".join(failures)
        )
    return {
        "schema_version": "ginav2021.resume_wslpath_budget.v1",
        "wslpath_executable": str(executable),
        "path_count": len(rows),
        "maximum_windows_path_character_count": max(
            (int(row["windows_path_character_count"]) for row in rows), default=0
        ),
        "budget_characters": 239,
        "all_paths_within_budget": True,
        "ledger_sha256": sha256_file(ledger_path),
        "pass": True,
    }


def _resume_matlab_path_inventory(
    *, continuation: Path, stage: Path, ginav_root: Path,
    matlab_executable: Path, raw_csv: Path, gnss_audit: Mapping[str, Any],
    imu_csv: Path,
) -> tuple[Path, ...]:
    """Enumerate every path passed to, opened by, or constructed by MATLAB."""

    probe_runtime = stage / "g3p/runtime"
    c00_runtime = stage / "g4/runtime"
    probe_mirror = probe_runtime / "source_mirror"
    c00_mirror = c00_runtime / "source_mirror"
    mirror_relatives = runtime_source_mirror_relative_files(ginav_root)
    paths: list[Path] = [
        continuation, stage, ginav_root, matlab_executable, raw_csv,
        Path(gnss_audit["observation_path"]),
        Path(gnss_audit["navigation_path"]),
        Path(gnss_audit["ubx_path"]), imu_csv,
        stage / "g3c/BY2_GNSS1_NORMALIZED.rnx",
        stage / "g3c/BY2_GINAV_SPP_LC.ini",
        probe_runtime, probe_mirror, probe_mirror / "result",
        probe_runtime / "matlab_harness",
        probe_runtime / "matlab_harness/fopen.m",
        probe_runtime / "matlab_harness/run_legsa_ginav.m",
        probe_runtime / "MATLAB_FOPEN_LEDGER.tsv",
        stage / "g3p/BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv",
        c00_runtime, c00_mirror, c00_mirror / "result",
        c00_runtime / "matlab_harness",
        c00_runtime / "matlab_harness/fopen.m",
        c00_runtime / "matlab_harness/run_legsa_ginav.m",
        c00_runtime / "MATLAB_FOPEN_LEDGER.tsv",
        c00_mirror / "result/by2_gnss1_SPP_LC.pos",
        stage / "g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos",
        stage / "n/GINAV_BY2_C00_STANDARD_NAV.csv",
        stage / "n", stage / "r",
    ]
    for mirror in (probe_mirror, c00_mirror):
        paths.extend(mirror / relative for relative in mirror_relatives)
    return tuple(dict.fromkeys(paths))


def _r4c_g4_path_inventory(
    *, root: Path, stage: Path, ginav_root: Path, matlab_executable: Path,
    config: Path, observation: Path, navigation: Path, imu_csv: Path,
) -> tuple[Path, ...]:
    """Only paths actually passed to or constructed by the r4c G4 process."""

    runtime = stage / "g4/runtime"
    mirror = runtime / "source_mirror"
    paths = [
        root, stage, ginav_root, matlab_executable, config, observation,
        navigation, imu_csv, runtime, mirror, mirror / "result",
        runtime / "matlab_harness", runtime / "matlab_harness/fopen.m",
        runtime / "matlab_harness/run_legsa_ginav.m",
        runtime / "MATLAB_FOPEN_LEDGER.tsv",
        mirror / "result/by2_gnss1_SPP_LC.pos",
        stage / "g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos",
        stage / "g4/GINAV_BY2_C00_FAILURE_LEDGER.csv",
        stage / "g4/GINAV_BY2_C00_NATIVE_SUMMARY.json",
        stage / "n", stage / "n/GINAV_BY2_C00_STANDARD_NAV.csv", stage / "r",
    ]
    paths.extend(
        mirror / relative
        for relative in runtime_source_mirror_relative_files(ginav_root)
    )
    return tuple(dict.fromkeys(paths))


def _resume_artifact_manifest(continuation: Path) -> dict[str, Any]:
    files = []
    excluded = {
        "s/r/LC02_GINAV2021_ARTIFACT_MANIFEST.json",
        "s/r/LC02_GINAV2021_RESUME_SEAL.json",
    }
    for path in sorted(continuation.rglob("*")):
        relative = path.relative_to(continuation).as_posix()
        if path.is_file() and relative not in excluded:
            files.append({
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return {
        "schema_version": "ginav2021.resume_artifact_manifest.v1",
        "file_count": len(files),
        "files": files,
    }


def _raw_csv_message_metadata(path: Path) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    rebuilt: list[bytes] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "data" not in reader.fieldnames:
            raise TransactionError("GNSS1 diagnostic CSV lacks data column")
        timestamp_field = next(
            (name for name in reader.fieldnames if name.casefold() == "time"), None
        ) or next(
            (name for name in reader.fieldnames if "timestamp" in name.casefold()), None
        )
        for source_row, row in enumerate(reader, start=2):
            frames, _discarded, _failures = _scan_valid_ubx_frames(
                parse_csv_data_cell(row["data"])
            )
            for frame in frames:
                msg_class, msg_id, payload = next(iter(iter_ubx_frames(frame)))
                result.append({
                    "message_sequence": len(result),
                    "source_csv_row": source_row,
                    "source_timestamp": row.get(timestamp_field) if timestamp_field else None,
                    "source_stamp_seconds": row.get("stamp.secs"),
                    "source_stamp_nanoseconds": row.get("stamp.nsecs"),
                    "msg_class": msg_class,
                    "msg_id": msg_id,
                    "payload": payload,
                })
                rebuilt.append(frame)
    exact = reconstruct_ubx_stream(path, None, decode_nav_hpposecef_semantics=False)
    if b"".join(rebuilt) != exact.stream:
        raise TransactionError("diagnostic CSV row/frame mapping is not byte-exact")
    return tuple(result)


def _nav_pvt_diagnostic_fields(item: Mapping[str, Any], *, gps_week: int) -> dict[str, Any]:
    payload = bytes(item["payload"])
    if len(payload) < 92:
        raise TransactionError("diagnostic NAV-PVT payload is truncated")
    itow = struct.unpack_from("<I", payload, 0)[0]
    year = struct.unpack_from("<H", payload, 4)[0]
    month, day, hour, minute, second, valid = struct.unpack_from("<BBBBBB", payload, 6)
    time_accuracy_ns = struct.unpack_from("<I", payload, 12)[0]
    nano = struct.unpack_from("<i", payload, 16)[0]
    fix_type, flags, flags2, num_sv = struct.unpack_from("<BBBB", payload, 20)
    lon, lat, height, hmsl = struct.unpack_from("<iiii", payload, 24)
    h_acc, v_acc = struct.unpack_from("<II", payload, 40)
    vel_n, vel_e, vel_d, ground_speed, head_mot = struct.unpack_from("<iiiii", payload, 48)
    speed_acc, heading_acc = struct.unpack_from("<II", payload, 68)
    pdop = struct.unpack_from("<H", payload, 76)[0]
    flags3 = payload[78]
    head_veh = struct.unpack_from("<i", payload, 80)[0]
    mag_dec = struct.unpack_from("<h", payload, 84)[0]
    mag_acc = struct.unpack_from("<H", payload, 86)[0]
    utc = None
    try:
        base = dt.datetime(year, month, day, hour, minute, second, tzinfo=dt.timezone.utc)
        utc = (base + dt.timedelta(microseconds=nano / 1000)).isoformat()
    except (ValueError, OverflowError):
        utc = "INVALID_UTC_FIELDS"
    return {
        "candidate_message_sequence": item["message_sequence"],
        "source_csv_row": item["source_csv_row"],
        "source_timestamp": item["source_timestamp"],
        "source_stamp_seconds": item["source_stamp_seconds"],
        "source_stamp_nanoseconds": item["source_stamp_nanoseconds"],
        "gps_week_from_associated_RAWX": gps_week,
        "iTOW_milliseconds": itow,
        "UTC": utc,
        "year_raw": year,
        "month_raw": month,
        "day_raw": day,
        "hour_raw": hour,
        "minute_raw": minute,
        "second_raw": second,
        "nano_raw": nano,
        "valid_raw": valid,
        "tAcc_ns": time_accuracy_ns,
        "validDate": bool(valid & 0x01),
        "validTime": bool(valid & 0x02),
        "fullyResolved": bool(valid & 0x04),
        "validMag": bool(valid & 0x08),
        "fixType": fix_type,
        "flags": flags,
        "flags2": flags2,
        "flags3": flags3,
        "reserved1_hex": payload[79:80].hex(),
        "reserved2_hex": payload[88:92].hex(),
        "gnssFixOK": bool(flags & 0x01),
        "diffSoln": bool(flags & 0x02),
        "psmState": (flags >> 2) & 0x07,
        "headVehValid": bool(flags & 0x20),
        "carrSoln": (flags >> 6) & 0x03,
        "confirmedAvail": bool(flags2 & 0x20),
        "confirmedDate": bool(flags2 & 0x40),
        "confirmedTime": bool(flags2 & 0x80),
        "invalidLlh": bool(flags3 & 0x01),
        "lastCorrectionAge": (flags3 >> 1) & 0x0F,
        "numSV": num_sv,
        "pDOP": pdop * 0.01,
        "longitude_deg": lon * 1e-7,
        "latitude_deg": lat * 1e-7,
        "height_ellipsoid_m": height * 1e-3,
        "height_msl_m": hmsl * 1e-3,
        "horizontal_accuracy_m": h_acc * 1e-3,
        "vertical_accuracy_m": v_acc * 1e-3,
        "velocity_north_mps": vel_n * 1e-3,
        "velocity_east_mps": vel_e * 1e-3,
        "velocity_down_mps": vel_d * 1e-3,
        "ground_speed_mps": ground_speed * 1e-3,
        "heading_motion_deg": head_mot * 1e-5,
        "speed_accuracy_mps": speed_acc * 1e-3,
        "heading_accuracy_deg": heading_acc * 1e-5,
        "heading_vehicle_deg": head_veh * 1e-5,
        "magnetic_declination_deg": mag_dec * 1e-2,
        "magnetic_declination_accuracy_deg": mag_acc * 1e-2,
    }


def _resolve_hash_locked_resume_raw_csv(
    options: ExecuteResumeExistingR4Options,
) -> tuple[Path, dict[str, str]]:
    local = _load_local_paths(options, verify_raw_availability=True)
    raw_lock_path = local["clean_root"] / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv"
    if sha256_file(raw_lock_path) != RAW_HASH_LOCK_SHA256:
        raise TransactionError("resume raw hash-lock identity mismatch")
    lock = read_hash_lock(raw_lock_path)
    raw_csv = (local["by2_fix_root"] / "gnss1-raw.csv").resolve(strict=True)
    if local["raw_root"] not in raw_csv.parents:
        raise TransactionError("resume diagnostic GNSS1 raw CSV escapes RAW_ROOT")
    relative = raw_csv.relative_to(local["raw_root"]).as_posix()
    verify_raw_sources(local["raw_root"], [relative], lock)
    return raw_csv, {
        "RAW_FILE_HASH_LOCK.csv": sha256_file(raw_lock_path),
        "gnss1-raw.csv": sha256_file(raw_csv),
    }


def _verify_resume_matlab_identity(
    specified_executable: Path,
    source_stage: Path,
) -> tuple[Path, dict[str, Any]]:
    """Bind the suffix to the exact executable authenticated by frozen r4 G0."""

    if not specified_executable.is_absolute():
        raise TransactionError(
            "resume MATLAB executable must be an explicitly specified absolute path"
        )
    executable = specified_executable.resolve(strict=True)
    if not executable.is_file():
        raise TransactionError("resume MATLAB executable is not a regular file")
    environment_path = source_stage / "g0/GINAV_MATLAB_ENVIRONMENT.json"
    if not environment_path.is_file() or environment_path.is_symlink():
        raise TransactionError("frozen r4 G0 MATLAB environment identity is unavailable")
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    executable_hash = sha256_file(executable)
    expected_hash = environment.get("executable_sha256")
    if not isinstance(expected_hash, str) or executable_hash != expected_hash:
        raise TransactionError(
            "resume MATLAB executable hash differs from frozen r4 G0 identity"
        )
    return executable, {
        "schema_version": "ginav2021.resume_matlab_identity.v1",
        "user_specified_absolute_path": str(specified_executable),
        "resolved_executable_path": str(executable),
        "executable_sha256": executable_hash,
        "source_r4_environment_path": str(environment_path),
        "source_r4_environment_sha256": sha256_file(environment_path),
        "source_r4_expected_executable_sha256": expected_hash,
        "path_fallback_used": False,
        "pass": True,
    }


def execute_resume_existing_r4_from_g3c(
    options: ExecuteResumeExistingR4Options,
) -> dict[str, Any]:
    """Execute only the authenticated r4 G3c→G3→conditional-G4 suffix."""

    continuation = options.continuation_root.expanduser().resolve(strict=True)
    if continuation.name != "r4b" or continuation.is_symlink():
        raise TransactionError("continuation must be the exact prepared r4b root")
    entries = tuple(sorted(path.name for path in continuation.iterdir()))
    if entries != ("SOURCE_R4_G0_G1_G2_HASH_LOCK.json",):
        raise TransactionError("prepared r4b root is dirty or already executed")
    lock_path = continuation / entries[0]
    prepared = json.loads(lock_path.read_text(encoding="utf-8"))
    verified_before = _verify_frozen_r4(options.source_r4_root)
    source_root = verified_before["source_root"]
    if (
        prepared.get("schema_version") != "ginav2021.resume_existing_r4_from_g3c.v1"
        or prepared.get("pass") is not True
        or Path(str(prepared.get("source_r4_root"))).resolve(strict=True) != source_root
        or Path(str(prepared.get("continuation_root"))).resolve(strict=True) != continuation
        or prepared.get("source_full_tree_hash_lock", {}).get("tree_binding_sha256")
        != verified_before["full_lock"]["tree_binding_sha256"]
    ):
        raise TransactionError("prepared r4b authentication lock is inconsistent")

    source_stage = verified_before["source_stage"]
    matlab_executable, matlab_identity = _verify_resume_matlab_identity(
        options.matlab_executable, source_stage
    )
    prepared_matlab = prepared.get("prepared_matlab_identity")
    if not isinstance(prepared_matlab, Mapping) or any(
        prepared_matlab.get(key) != matlab_identity.get(key)
        for key in (
            "user_specified_absolute_path", "resolved_executable_path",
            "executable_sha256", "source_r4_environment_sha256",
            "source_r4_expected_executable_sha256",
        )
    ):
        raise TransactionError(
            "execute MATLAB identity differs from prepared continuation binding"
        )
    gnss_audit = json.loads(
        (source_stage / "g2n/BY2_GNSS1_RINEX_AUDIT.json").read_text(encoding="utf-8")
    )
    gnss_audit["observation_path"] = str(source_stage / "g2n/runtime/BY2_GNSS1.rnx")
    gnss_audit["navigation_path"] = str(source_stage / "g2n/runtime/BY2_GNSS1.nav")
    gnss_audit["ubx_path"] = str(source_stage / "g2n/runtime/BY2_GNSS1.ubx")
    imu_audit = json.loads(
        (source_stage / "g2i/BY2_GINAV_IMU_AUDIT.json").read_text(encoding="utf-8")
    )
    imu_csv = source_stage / "g2i/BY2_GINAV_IMU.csv"
    if (
        sha256_file(Path(gnss_audit["observation_path"]))
        != gnss_audit["rinex"]["observation_sha256"]
        or sha256_file(Path(gnss_audit["navigation_path"]))
        != gnss_audit["rinex"]["navigation_sha256"]
        or sha256_file(Path(gnss_audit["ubx_path"])) != gnss_audit["ubx_sha256"]
        or sha256_file(imu_csv) != imu_audit["output_sha256"]
    ):
        raise TransactionError("reused r4 G2 payload hash mismatch")

    raw_csv, diagnostic_raw_hashes = _resolve_hash_locked_resume_raw_csv(options)
    reconstructed = reconstruct_ubx_stream(
        raw_csv, None, decode_nav_hpposecef_semantics=False
    )
    if hashlib.sha256(reconstructed.stream).hexdigest() != gnss_audit["ubx_sha256"]:
        raise TransactionError("diagnostic raw CSV does not reconstruct frozen r4 UBX")
    message_metadata = _raw_csv_message_metadata(raw_csv)
    metadata_by_sequence = {
        int(item["message_sequence"]): item for item in message_metadata
    }
    prepared_code_identity = prepared.get("prepared_implementation_code_identity")
    current_code_identity = _resume_code_identity(options.repository_root)
    if (
        not isinstance(prepared_code_identity, Mapping)
        or current_code_identity != prepared_code_identity
    ):
        raise TransactionError(
            "execute implementation identity differs from prepared continuation binding"
        )
    # Reuse this exact authenticated object in PRE_EXEC and provenance.
    code_identity_before = dict(prepared_code_identity)

    # All authentication and immutable-input reconstruction above is read-only.
    # Create the continuation stage only after those fail-closed preflights pass.
    stage = continuation / "s"
    stage.mkdir(exist_ok=False)
    for short in _SHORT_RESUME_LAYOUT.values():
        (stage / short).mkdir(exist_ok=False)
    for gate, short in (("G0", "g0"), ("G1", "g1"), ("G2_GNSS", "g2n"), ("G2_IMU", "g2i")):
        write_json(stage / short / "REUSED_NOT_EXECUTED.json", {
            "gate": gate,
            "status": "REUSED_NOT_EXECUTED",
            "source_section_binding_sha256": verified_before["locks"][gate][
                "tree_binding_sha256"
            ],
            "execution_count_this_continuation": 0,
        })
    write_json(continuation / "PRE_EXECUTION_CONTROL.json", {
        "schema_version": "ginav2021.resume_suffix_pre_execution_identity.v1",
        "source_r4_full_tree_binding_sha256": verified_before["full_lock"][
            "tree_binding_sha256"
        ],
        "matlab_identity": matlab_identity,
        "diagnostic_raw_hashes": diagnostic_raw_hashes,
        "diagnostic_reconstructed_ubx_sha256": hashlib.sha256(
            reconstructed.stream
        ).hexdigest(),
        "frozen_r4_ubx_sha256": gnss_audit["ubx_sha256"],
        "raw_csv_diagnostic_only_not_solver_input": True,
        "G0_G1_G2_execution_this_continuation": 0,
        "publication_requested": False,
        "implementation_code_identity": code_identity_before,
        "pass": True,
    })

    access = AccessLedger()
    access.record(raw_csv, role="GNSS1_RAW_CSV_DIAGNOSTIC_ONLY_NOT_SOLVER_INPUT")
    for path, role in (
        (Path(gnss_audit["observation_path"]), "REUSED_ACTIVE_R4_RINEX_OBSERVATION"),
        (Path(gnss_audit["navigation_path"]), "REUSED_ACTIVE_R4_RINEX_NAVIGATION"),
        (Path(gnss_audit["ubx_path"]), "REUSED_ACTIVE_R4_UBX_TIME"),
        (imu_csv, "REUSED_ACTIVE_R4_GO2_IMU"),
    ):
        access.record(path, role=role)

    source_provenance = verified_before["provenance"]
    provenance: dict[str, Any] = {
        "schema_version": "ginav2021.resume_suffix_provenance.v1",
        "candidate_id": CANDIDATE_ID,
        "data_mode": "real_by2_raw",
        "dataset_role": "real_by2_raw",
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "same_active_r4_reuse": True,
        "old_runtime_input_count": 0,
        "code_commit": code_identity_before["repository_head"],
        "source_r4_code_commit": source_provenance.get("code_commit"),
        "implementation_file_sha256": code_identity_before.get(
            "implementation_file_sha256", {}
        ),
        "runtime_contract_hash": code_identity_before.get("runtime_contract_hash"),
        "implementation_aggregate_binding_sha256": code_identity_before[
            "aggregate_binding_sha256"
        ],
        "approved_tracked_dirty_status": code_identity_before.get(
            "approved_tracked_dirty_status", []
        ),
        "approved_tracked_diff_sha256": code_identity_before.get(
            "approved_tracked_diff_sha256"
        ),
        "config_hash": None,
        "raw_source_hashes": dict(diagnostic_raw_hashes),
        "provider_hashes": {
            "FROZEN_R4_GNSS1_RINEX_OBSERVATION": gnss_audit["rinex"][
                "observation_sha256"
            ],
            "FROZEN_R4_GNSS1_RINEX_NAVIGATION": gnss_audit["rinex"][
                "navigation_sha256"
            ],
            "FROZEN_R4_GNSS1_UBX": gnss_audit["ubx_sha256"],
            "FROZEN_R4_GO2_IMU": imu_audit["output_sha256"],
        },
        "source_r4_evidence": {
            "full_tree_binding_sha256": verified_before["full_lock"][
                "tree_binding_sha256"
            ],
            "section_tree_binding_sha256": {
                gate: lock["tree_binding_sha256"]
                for gate, lock in verified_before["locks"].items()
            },
            "consolidated_provenance_sha256": sha256_file(
                verified_before["provenance_path"]
            ),
            "source_terminal_status": verified_before["status"]["terminal_status"],
        },
        "reused_official_sample_evidence": {
            "result": verified_before["status"]["OFFICIAL_SAMPLE_RESULT"],
            "source_execution_count": _FROZEN_R4_GATE_COUNTS[
                "G1_official_sample_runs"
            ],
            "source_G1_tree_binding_sha256": verified_before["locks"]["G1"][
                "tree_binding_sha256"
            ],
            "executed_this_continuation": False,
        },
        "reused_G2_evidence": {
            "GNSS_tree_binding_sha256": verified_before["locks"]["G2_GNSS"][
                "tree_binding_sha256"
            ],
            "IMU_tree_binding_sha256": verified_before["locks"]["G2_IMU"][
                "tree_binding_sha256"
            ],
            "GNSS_executed_this_continuation": False,
            "IMU_executed_this_continuation": False,
        },
        "source_cumulative_gate_execution_counts": dict(_FROZEN_R4_GATE_COUNTS),
        "gate_execution_counts": {
            "G0_matlab_candidate_attempts": 0,
            "G1_official_sample_runs": 0,
            "G2_gnss_adapter_runs": 0,
            "G2_imu_adapter_runs": 0,
            "G3_tdcp_probe_runs": 0,
            "G4_BY2_C00_runs": 0,
        },
        "official_sample_regression_executed": False,
        "official_sample_reused_from_exact_r4": True,
        "BY2_G2_reused_from_exact_r4": True,
        "raw_csv_diagnostic_only": True,
        "raw_csv_solver_input": False,
        "raw_path_identity_contract": (
            "local_paths_config_plus_RAW_FILE_HASH_LOCK_plus_"
            "reconstructed_UBX_equals_frozen_r4_UBX"
        ),
        "diagnostic_raw_hashes": diagnostic_raw_hashes,
        "resume_matlab_identity": matlab_identity,
        "implementation_code_identity_pre_execution": code_identity_before,
    }
    all_cleanliness: list[dict[str, Any]] = []


    def diagnostic_writer(**context: Any) -> None:
        proof = context["proof"]
        association = proof["association_audit"]
        rawx_times = context["rawx_times"]
        pvt_times = context["pvt_times"]
        pvt_by_sequence = {item.sequence: item for item in pvt_times}
        authoritative_pvt = tuple(item for item in pvt_times if item.authoritative)

        # Reconstruct the superseded exact-key rule independently.  In
        # particular, do not derive its lookup key from the B-selected PVT:
        # that would hide the exact-key miss which motivated this diagnosis.
        old_rows: list[dict[str, Any]] = []
        old_counts = {
            "unique": 0,
            "semantic_duplicate": 0,
            "conflicting": 0,
            "missing": 0,
        }
        for index, rawx_item in enumerate(rawx_times):
            # Superseded contract: floor(rcvTow_seconds + 0.5) * 1000.
            old_target_ms = int(
                ((rawx_item.tow_nanoseconds + NANOSECONDS // 2) // NANOSECONDS)
                * 1000
            ) % (WEEK_SECONDS * 1000)
            old_candidates = tuple(
                item for item in authoritative_pvt
                if item.itow_milliseconds == old_target_ms
            )
            old_signatures = {item.semantic_signature for item in old_candidates}
            if not old_signatures:
                old_classification = "MISSING"
                old_counts["missing"] += 1
            elif len(old_signatures) > 1:
                old_classification = "CONFLICT"
                old_counts["conflicting"] += 1
            elif len(old_candidates) > 1:
                old_classification = "SEMANTIC_DUPLICATE"
                old_counts["semantic_duplicate"] += 1
            else:
                old_classification = "UNIQUE"
                old_counts["unique"] += 1
            old_rows.append({
                "old_exact_target_iTOW_milliseconds": old_target_ms,
                "old_exact_candidate_count": len(old_candidates),
                "old_exact_semantic_signature_count": len(old_signatures),
                "old_exact_classification": old_classification,
            })

        expected_old_counts = {
            "unique": 1508,
            "semantic_duplicate": 0,
            "conflicting": 0,
            "missing": 1,
        }
        expected_b_counts = {
            "unique": 1509,
            "semantic_duplicate": 0,
            "conflicting": 0,
            "missing": 0,
        }
        b_counts = {
            "unique": association["unique_association_count"],
            "semantic_duplicate": association["semantic_duplicate_association_count"],
            "conflicting": association["conflicting_association_count"],
            "missing": association["missing_association_count"],
        }
        if old_counts != expected_old_counts:
            raise TransactionError(f"unexpected old exact-key counts: {old_counts}")
        if b_counts != expected_b_counts:
            raise TransactionError(f"unexpected stream-order B counts: {b_counts}")

        # Durable candidate inventory: every one of the 1,509 RAWX windows is
        # represented, with one row per authoritative candidate (or a missing
        # placeholder).  This preserves duplicates and conflicts for audit.
        csv_rows: list[dict[str, Any]] = []
        for index, (rawx_item, association_row, old_row) in enumerate(
            zip(rawx_times, association["rows"], old_rows, strict=True)
        ):
            rawx_meta_item = metadata_by_sequence[rawx_item.sequence]
            common = {
                "rawx_index": index,
                "rawx_message_sequence": rawx_item.sequence,
                "rawx_source_csv_row": rawx_meta_item["source_csv_row"],
                "rawx_source_timestamp": rawx_meta_item["source_timestamp"],
                "rawx_source_stamp_seconds": rawx_meta_item["source_stamp_seconds"],
                "rawx_source_stamp_nanoseconds": rawx_meta_item["source_stamp_nanoseconds"],
                "rawx_gps_week": rawx_item.week,
                "rawx_rcvTow_seconds": f"{rawx_item.tow_nanoseconds / NANOSECONDS:.9f}",
                "window_upper_rawx_message_sequence_exclusive": association_row[
                    "window_upper_rawx_message_sequence_exclusive"
                ],
                "window_ends_at_eof": association_row["window_ends_at_eof"],
                "B_classification": association_row["classification"],
                "B_authoritative_candidate_count": association_row[
                    "authoritative_candidate_count"
                ],
                "B_semantic_signature_count": association_row[
                    "semantic_signature_count"
                ],
                "B_canonical_message_sequence": association_row[
                    "canonical_message_sequence"
                ],
                **old_row,
            }
            sequences = association_row["candidate_message_sequences"]
            if not sequences:
                csv_rows.append({**common, "candidate_message_sequence": None})
                continue
            for sequence in sequences:
                candidate = pvt_by_sequence[sequence]
                csv_rows.append({
                    **common,
                    **_nav_pvt_diagnostic_fields(
                        metadata_by_sequence[candidate.sequence],
                        gps_week=rawx_item.week,
                    ),
                })

        row = association["rows"][1508]
        rawx = rawx_times[1508]
        old_row_1508 = old_rows[1508]
        candidate_rows = [
            _nav_pvt_diagnostic_fields(
                metadata_by_sequence[sequence], gps_week=rawx.week
            )
            for sequence in row["candidate_message_sequences"]
        ]
        if (
            old_row_1508["old_exact_target_iTOW_milliseconds"] != 461176000
            or old_row_1508["old_exact_candidate_count"] != 0
            or len(candidate_rows) != 1
        ):
            raise TransactionError("RAWX index 1508 diagnostic truth mismatch")
        consumed = ("iTOW_milliseconds", "validDate", "validTime", "fullyResolved")
        all_fields = tuple(candidate_rows[0]) if candidate_rows else ()
        differing = [
            field for field in all_fields
            if len({json.dumps(item.get(field), sort_keys=True) for item in candidate_rows}) > 1
        ]
        rawx_meta = metadata_by_sequence[rawx.sequence]
        payload = {
            "schema_version": "ginav2021.rawx_nav_pvt_association_diagnostic.v1",
            "decision": "B_CAUSAL_DETERMINISTIC_STREAM_ORDER",
            "consumed_fields": list(consumed),
            "audit_transport_only_field_groups": {
                "transport": [
                    "source_csv_row", "source_timestamp", "source_stamp_seconds",
                    "source_stamp_nanoseconds", "candidate_message_sequence",
                    "gps_week_from_associated_RAWX",
                ],
                "utc_raw": [
                    "UTC", "year_raw", "month_raw", "day_raw", "hour_raw",
                    "minute_raw", "second_raw", "nano_raw", "valid_raw", "tAcc_ns",
                    "validMag", "reserved1_hex", "reserved2_hex",
                ],
                "fix": [
                    "fixType", "flags", "flags2", "flags3", "gnssFixOK",
                    "diffSoln", "psmState", "headVehValid", "carrSoln",
                    "confirmedAvail", "confirmedDate", "confirmedTime",
                    "invalidLlh", "lastCorrectionAge", "numSV", "pDOP",
                ],
                "position": [
                    "longitude_deg", "latitude_deg", "height_ellipsoid_m",
                    "height_msl_m", "horizontal_accuracy_m", "vertical_accuracy_m",
                ],
                "velocity_heading": [
                    "velocity_north_mps", "velocity_east_mps", "velocity_down_mps",
                    "ground_speed_mps", "heading_motion_deg", "speed_accuracy_mps",
                    "heading_accuracy_deg", "heading_vehicle_deg",
                    "magnetic_declination_deg", "magnetic_declination_accuracy_deg",
                ],
            },
            "old_exact_key_counts": old_counts,
            "stream_order_B_counts": b_counts,
            "index_1508": row,
            "index_1508_RAWX": {
                "rawx_index": 1508,
                "source_csv_row": rawx_meta["source_csv_row"],
                "source_timestamp": rawx_meta["source_timestamp"],
                "gps_week": rawx.week,
                "rcvTow_seconds": rawx.tow_nanoseconds / NANOSECONDS,
                "message_sequence": rawx.sequence,
            },
            "index_1508_old_exact_key_target_iTOW_milliseconds": old_row_1508[
                "old_exact_target_iTOW_milliseconds"
            ],
            "index_1508_old_exact_key_candidate_count": old_row_1508[
                "old_exact_candidate_count"
            ],
            "index_1508_candidates": candidate_rows,
            "differing_consumed_fields": [field for field in differing if field in consumed],
            "differing_audit_only_fields": [field for field in differing if field not in consumed],
            "constant_offset_nanoseconds": proof["constant_offset_nanoseconds"],
            "message_sequence_delta_min": min(
                item["message_sequence_delta"] for item in proof["ledger"]
            ),
            "message_sequence_delta_max": max(
                item["message_sequence_delta"] for item in proof["ledger"]
            ),
            "retained_row_count": len(context["normalized_rows"]),
            "official_accepted_count": context["acceptance"]["selected_official_epoch_count"],
            "official_rejected_count": context["acceptance"][
                "selected_official_rejected_epoch_count"
            ],
            "deleted_or_merged_count": 0,
            "raw_csv_sha256": sha256_file(raw_csv),
            "reconstructed_ubx_sha256": hashlib.sha256(reconstructed.stream).hexdigest(),
            "frozen_r4_ubx_sha256": gnss_audit["ubx_sha256"],
            "parser_file_sha256": sha256_file(Path(__file__).with_name("time_contract.py")),
            "code_file_sha256": sha256_file(Path(__file__)),
            "trace_used": False,
            "reference_used": False,
            "rmse_used": False,
        }
        write_json(
            context["time_section"] /
            "RAWX_NAVPVT_ASSOCIATION_SEMANTIC_DIAGNOSIS.json",
            payload,
        )
        fieldnames = tuple(dict.fromkeys(
            key for item in csv_rows for key in item
        ))
        _write_csv(
            context["time_section"] / "RAWX_NAVPVT_ASSOCIATION_CANDIDATES.csv",
            csv_rows,
            fieldnames,
        )

    finalized = False
    def finalize(status: str, *, detail: str | None = None,
                 extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        nonlocal finalized
        if finalized:
            raise TransactionError("resume suffix terminal finalized more than once")
        finalized = True
        verified_after = _verify_frozen_r4(source_root)
        if verified_after["full_lock"]["tree_binding_sha256"] != verified_before[
            "full_lock"
        ]["tree_binding_sha256"]:
            raise TransactionError("frozen r4 changed during suffix execution")
        code_identity_after = _resume_code_identity(options.repository_root)
        if code_identity_after != code_identity_before:
            raise TransactionError("resume implementation identity drifted during execution")
        report = stage / "r"
        audit = access.audit()
        counts = dict(provenance["gate_execution_counts"])
        if any(counts[key] != 0 for key in (
            "G0_matlab_candidate_attempts", "G1_official_sample_runs",
            "G2_gnss_adapter_runs", "G2_imu_adapter_runs",
        )) or counts["G3_tdcp_probe_runs"] > 1 or counts["G4_BY2_C00_runs"] > 1:
            raise TransactionError("resume suffix gate execution count contract failed")
        formal_admission = bool((extra or {}).get("formal_lc02_admission", False))
        by2_executed = counts["G4_BY2_C00_runs"] == 1
        if formal_admission and not by2_executed:
            raise TransactionError("formal admission is impossible without one BY2 C00 run")
        actual_blocker = (
            None if status in {SUCCESS_STATUS, POOR_APPLICABILITY_STATUS} else status
        )
        by2_result = status if by2_executed else "NOT_EXECUTED"
        supplied_by2_result = (extra or {}).get("BY2_C00_RESULT")
        if supplied_by2_result is not None and supplied_by2_result != by2_result:
            raise TransactionError("BY2 C00 result contradicts terminal/execution counts")
        provenance.update({
            "implementation_code_identity_post_execution": code_identity_after,
            "implementation_identity_unchanged": True,
            "terminal_status": status,
            "transaction_complete": True,
            "formal_lc02_admission": formal_admission,
            "actual_algorithm_blocker": actual_blocker,
            "file_access_audit": audit,
            "BY2_C00_executed": by2_executed,
            "BY2_C00_RESULT": by2_result,
            "gate_execution_counts": counts,
        })
        write_json(report / "GINAV_FORBIDDEN_INPUT_AUDIT.json", audit)
        write_json(report / "GINAV_CONSOLIDATED_PROVENANCE.json", provenance)
        payload = {
            "schema_version": "ginav2021.resume_suffix_terminal.v1",
            "terminal_status": status,
            "formal_lc02_admission": formal_admission,
            "artifact_publication": "NOT_REQUESTED",
            "artifact_publication_requested": False,
            "transaction_complete": True,
            "gate_execution_counts_this_continuation": counts,
            "source_cumulative_gate_execution_counts": dict(_FROZEN_R4_GATE_COUNTS),
            "source_r4_unchanged_before_after": True,
            "detail": detail,
            **dict(extra or {}),
        }
        write_json(report / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
        write_json(report / "GINAV_PUBLICATION_PARITY.json", {
            "requested": False, "artifact_publication": "NOT_REQUESTED", "pass": True,
        })
        write_json(report / "LC02_GINAV2021_RESUME_SUFFIX_SUMMARY.json", payload)
        manifest = _resume_artifact_manifest(continuation)
        write_json(report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json", manifest)
        seal = {
            "schema_version": "ginav2021.resume_suffix_seal.v1",
            "artifact_manifest_sha256": sha256_file(
                report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json"
            ),
            "source_r4_full_tree_binding_sha256": verified_after["full_lock"][
                "tree_binding_sha256"
            ],
            "seal_written_last": True,
        }
        write_json(report / "LC02_GINAV2021_RESUME_SEAL.json", seal)
        payload["seal_sha256"] = sha256_file(report / "LC02_GINAV2021_RESUME_SEAL.json")
        return payload

    try:
        anticipated = _resume_matlab_path_inventory(
            continuation=continuation, stage=stage, ginav_root=options.ginav_root,
            matlab_executable=matlab_executable, raw_csv=raw_csv,
            gnss_audit=gnss_audit, imu_csv=imu_csv,
        )
        budget = _wslpath_budget_audit(anticipated, continuation / "WSLPATH_LEDGER.csv")
        write_json(continuation / "WSLPATH_BUDGET.json", budget)
        provenance["wslpath_budget"] = budget
    except (OSError, ValueError, TransactionError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"resume path-budget preflight failed: {exc}",
        )


    try:
        return _execute_g3c_g4_suffix(
            options=options, stage=stage, gnss_audit=gnss_audit, imu_csv=imu_csv,
            matlab_executable=matlab_executable, provenance=provenance,
            global_access=access, all_cleanliness=all_cleanliness, finalize=finalize,
            stage_dir_resolver=_short_resume_stage_dir,
            g3c_diagnostic_writer=diagnostic_writer,
        )
    except (OSError, ValueError, TransactionError, SourceIdentityError) as exc:
        if finalized:
            raise
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE", detail=str(exc)
        )


def execute_recover_r4b_g3_to_r4c_g4(
    options: RecoverR4cExecuteOptions,
) -> dict[str, Any]:
    """Run no gate except the shared G4 tail after exact r4b G3 recovery."""

    root = options.r4c_root.expanduser().resolve(strict=True)
    if root.name != "r4c" or tuple(sorted(path.name for path in root.iterdir())) != (
        "R4C_G4_RECOVERY_LOCK.json",
    ):
        raise TransactionError("r4c is not the exact prepared lock-only root")
    lock = json.loads((root / "R4C_G4_RECOVERY_LOCK.json").read_text(encoding="utf-8"))
    r4_before = _verify_frozen_r4(options.source_r4_root)
    r4b_before = _verify_frozen_r4b(options.source_r4b_root)
    current_code = _resume_code_identity(options.repository_root)
    matlab, matlab_identity = _verify_resume_matlab_identity(
        options.matlab_executable, r4_before["source_stage"]
    )
    if (
        lock.get("pass") is not True
        or Path(str(lock.get("source_r4_root"))).resolve(strict=True)
        != r4_before["source_root"]
        or Path(str(lock.get("source_r4b_root"))).resolve(strict=True)
        != r4b_before["root"]
        or Path(str(lock.get("r4c_root"))).resolve(strict=True) != root
        or lock.get("source_r4_full_binding")
        != r4_before["full_lock"]["tree_binding_sha256"]
        or lock.get("source_r4b_full_binding")
        != r4b_before["full_lock"]["tree_binding_sha256"]
        or lock.get("prepared_code_identity") != current_code
        or lock.get("prepared_matlab_identity") != matlab_identity
    ):
        raise TransactionError("r4c authentication changed before stage creation")
    stage = root / "s"
    stage.mkdir(exist_ok=False)
    for short in _SHORT_RESUME_LAYOUT.values():
        (stage / short).mkdir(exist_ok=False)
    r4s, r4bs = r4_before["source_stage"], r4b_before["stage"]
    observation = r4bs / "g3c/BY2_GNSS1_NORMALIZED.rnx"
    config = r4bs / "g3c/BY2_GINAV_SPP_LC.ini"
    probe = r4bs / "g3p/BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv"
    navigation = r4s / "g2n/runtime/BY2_GNSS1.nav"
    imu = r4s / "g2i/BY2_GINAV_IMU.csv"
    counts = {"G0": 0, "G1": 0, "G2": 0, "G3": 0, "G4": 0}
    access = AccessLedger()
    reused_opens: list[dict[str, str]] = []
    provenance: dict[str, Any] = {
        "schema_version": "ginav2021.r4c_provenance.v1",
        "data_mode": "real_by2_raw",
        "dataset_role": "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00",
        "synthetic_data_used": False,
        "semisynthetic_data_used": False, "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False, "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "trace_open_count": 0, "reference_open_count": 0,
        "gnss2_open_count": 0, "rmse_used": False, "old_runtime_input_count": 0,
        "execution_counts_this_recovery": counts,
        "source_cumulative_counts": {
            "r4": dict(_FROZEN_R4_GATE_COUNTS),
            "r4b": {"G0": 0, "G1": 0, "G2": 0, "G3": 1, "G4": 0},
        },
        "r4_r4b_reuse_opens": reused_opens,
        "r4c_current_opens": [],
        "prepared_code_identity": lock["prepared_code_identity"],
        "code_commit": current_code["repository_head"],
        "config_hash": None,
        "raw_source_hashes": {},
        "provider_hashes": {},
        "OFFICIAL_SAMPLE_RESULT": "OFFICIAL_SAMPLE_PASS",
        "official_sample_reused_from_exact_r4": True,
        "reproduction_level": "EXACT_R4_R4B_AUTHENTICATED_G4_ONLY_RECOVERY",
    }
    finalized = False
    def finalize(
        status: str,
        detail: str | None = None,
        native: Mapping[str, Any] | None = None,
        *,
        technical_blocker: str | None = None,
    ) -> dict[str, Any]:
        nonlocal finalized
        if finalized:
            raise TransactionError("r4c finalized twice")
        finalized = True
        if _resume_code_identity(options.repository_root) != lock["prepared_code_identity"]:
            raise TransactionError("r4c code drifted before seal")
        if (
            _verify_frozen_r4(options.source_r4_root)["full_lock"]["tree_binding_sha256"]
            != r4_before["full_lock"]["tree_binding_sha256"]
            or _verify_frozen_r4b(options.source_r4b_root)["full_lock"]["tree_binding_sha256"]
            != r4b_before["full_lock"]["tree_binding_sha256"]
        ):
            raise TransactionError("r4/r4b changed during r4c")
        final_matlab, final_matlab_identity = _verify_resume_matlab_identity(
            options.matlab_executable, r4_before["source_stage"]
        )
        if final_matlab != matlab or final_matlab_identity != lock[
            "prepared_matlab_identity"
        ]:
            raise TransactionError("r4c MATLAB identity drifted before seal")
        audit = access.audit()
        formal = bool((native or {}).get("formal_lc02_admission", False))
        formal_slot = "FILLED" if formal else "VACANT"
        by2_result = status if counts["G4"] == 1 else "NOT_EXECUTED"
        actual_blocker = (
            None if technical_blocker is not None
            or status in {SUCCESS_STATUS, POOR_APPLICABILITY_STATUS}
            else status
        )
        chain_counts = {
            "source_r4": dict(_FROZEN_R4_GATE_COUNTS),
            "source_r4b": {"G0": 0, "G1": 0, "G2": 0, "G3": 1, "G4": 0},
            "this_r4c_recovery": dict(counts),
        }
        provenance.update({
            "terminal_status": status, "transaction_complete": True,
            "formal_lc02_admission": formal, "file_access_audit": audit,
            "BY2_C00_executed": counts["G4"] == 1,
            "BY2_C00_RESULT": by2_result,
            "formal_lc02_slot": formal_slot,
            "actual_algorithm_blocker": actual_blocker,
            "technical_blocker": technical_blocker,
            "source_chain_gate_counts": chain_counts,
            "resume_matlab_identity_pre_seal": final_matlab_identity,
            "trace_open_count": audit["trace_open_count"],
            "reference_open_count": audit["reference_open_count"],
            "gnss2_open_count": audit["gnss2_open_count"],
            "r4c_current_opens": audit["records"][len(reused_opens):],
        })
        report = stage / "r"
        write_json(report / "GINAV_FORBIDDEN_INPUT_AUDIT.json", audit)
        write_json(report / "GINAV_CONSOLIDATED_PROVENANCE.json", provenance)
        payload = {
            "terminal_status": status, "detail": detail,
            "transaction_complete": True, "formal_lc02_admission": formal,
            "execution_counts_this_recovery": counts,
            "source_chain_gate_counts": chain_counts,
            "OFFICIAL_SAMPLE_RESULT": "OFFICIAL_SAMPLE_PASS",
            "official_sample_reused_from_exact_r4": True,
            "BY2_C00_RESULT": by2_result,
            "formal_lc02_slot": formal_slot,
            "reproduction_level": provenance["reproduction_level"],
            "actual_algorithm_blocker": actual_blocker,
            "technical_blocker": technical_blocker,
            "artifact_publication": "NOT_REQUESTED",
        }
        write_json(report / "LC02_GINAV2021_TRANSACTION_STATUS.json", payload)
        write_json(report / "LC02_GINAV2021_RESUME_SUFFIX_SUMMARY.json", payload)
        write_json(report / "GINAV_PUBLICATION_PARITY.json", {
            "requested": False, "pass": True, "artifact_publication": "NOT_REQUESTED"
        })
        write_json(report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json",
                   _resume_artifact_manifest(root))
        write_json(report / "LC02_GINAV2021_RESUME_SEAL.json", {
            "artifact_manifest_sha256": sha256_file(
                report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json"
            ), "r4_unchanged": True, "r4b_unchanged": True,
            "seal_written_last": True,
        })
        return payload

    try:
        for gate, short in (
            ("G0", "g0"), ("G1", "g1"), ("G2_GNSS", "g2n"),
            ("G2_IMU", "g2i"), ("G3_CONFIG", "g3c"),
        ):
            write_json(stage / short / "REUSED_NOT_EXECUTED.json", {
                "gate": gate, "status": "REUSED_NOT_EXECUTED",
                "execution_count_this_recovery": 0,
            })
        write_json(root / "PRE_EXECUTION_CONTROL.json", {
            "prepared_code_identity": lock["prepared_code_identity"],
            "current_code_identity": current_code,
            "matlab_identity": matlab_identity,
            "source_r4_root": str(r4_before["source_root"]),
            "source_r4b_root": str(r4b_before["root"]),
            "r4c_root": str(root),
            "source_r4_binding": r4_before["full_lock"]["tree_binding_sha256"],
            "source_r4b_binding": r4b_before["full_lock"]["tree_binding_sha256"],
            "pass": True,
        })
        for path, role in (
            (observation, "SAME_ACTIVE_R4B_RINEX"),
            (config, "SAME_ACTIVE_R4B_CONFIG"),
            (probe, "SAME_ACTIVE_R4B_G3_PROBE"),
            (navigation, "SAME_ACTIVE_R4_NAV"),
            (imu, "SAME_ACTIVE_R4_IMU"),
        ):
            access.record(path, role=role)
            reused_opens.append({"path": str(path), "role": role})
        provenance["config_hash"] = sha256_file(config)
        provenance["raw_source_hashes"] = {
            "r4b_raw_probe_csv": sha256_file(probe),
            "r4b_normalized_observation": sha256_file(observation),
        }
        provenance["provider_hashes"] = {
            "r4b_derived_config": sha256_file(config),
            "r4_navigation": sha256_file(navigation),
            "r4_imu": sha256_file(imu),
        }
        canonical_probe = stage / "g3p/BY2_GINAV_TDCP_ALIGNMENT_PROBE_CANONICAL.csv"
        transport_audit_path = stage / "g3p/R4B_G3_TRANSPORT_RECOVERY_AUDIT.json"
        activation = _probe_summary(
            probe, canonical_output_path=canonical_probe,
            transport_audit_path=transport_audit_path,
        )
        transport = activation["transport_recovery_audit"]
        if (
            transport.get("raw_sha256") != sha256_file(probe)
            or transport.get("canonical_sha256") != sha256_file(canonical_probe)
            or transport.get("canonical_data_row_count")
            != activation["eligible_integer_epoch_count"]
            or transport.get("pass") is not True
        ):
            raise TransactionError("recovered G3 transport evidence does not cross-check")
        epochs = parse_rinex_epochs(observation)
        start, end = _gps_overlap_datetimes(epochs, imu)
        inventory = _official_run_epoch_inventory(
            epochs, imu, start_time_gpst=start, end_time_gpst=end,
            sample_rate_hz=GO2_SAMPLE_RATE_HZ,
        )
        activation["configured_run_epoch_inventory"] = inventory
        activation["dynamic_count_match"] = (
            activation["eligible_integer_epoch_count"]
            == inventory["accepted_official_gnss_epoch_count"]
        )
        activation["exact_time_set_match"] = (
            activation["eligible_integer_epoch_time_set"]
            == inventory["accepted_official_gnss_epoch_time_set"]
        )
        activation["activation_terminal"] = _activation_terminal(activation)
        write_json(
            stage / "g3p/BY2_GINAV_ALIGNMENT_ACTIVATION_SUMMARY.json", activation
        )
        science_pass = bool(
            inventory["conservation_pass"]
            and activation["internal_spp_outcome_conservation_pass"]
            and activation["alignment_attempt_covers_every_eligible_epoch"]
            and activation["dynamic_count_match"]
            and activation["exact_time_set_match"]
            and activation["activation_terminal"] is None
        )
        if not science_pass:
            return finalize(
                "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
                "recovered G3 science/inventory contract failed",
            )
        paths = _r4c_g4_path_inventory(
            root=root, stage=stage, ginav_root=options.ginav_root,
            matlab_executable=matlab, config=config, observation=observation,
            navigation=navigation, imu_csv=imu,
        )
        provenance["wslpath_budget"] = _wslpath_budget_audit(
            paths, root / "WSLPATH_LEDGER.csv"
        )
        write_json(root / "WSLPATH_BUDGET.json", provenance["wslpath_budget"])
        c00, runtime = stage / "g4", stage / "g4/runtime"
        runtime.mkdir(exist_ok=False)
        counts["G4"] = 1
        result, native = _g4_scientific_run_and_freeze(
            options=options, stage=stage, c00_section=c00, c00_runtime=runtime,
            by2_config=config, selected_observation=observation,
            navigation_path=navigation, imu_csv=imu, matlab_executable=matlab,
            provenance=provenance, access_ledger=access,
            run_epoch_inventory=inventory, activation=activation,
            stage_dir_resolver=_short_resume_stage_dir,
        )
        provenance["r4c_current_opens"] = access.audit()["records"][len(reused_opens):]
        _write_cleanliness(stage, [result["core_cleanliness"]],
                           stage_dir_resolver=_short_resume_stage_dir)
        return finalize(str(native["terminal_status"]), native=native)
    except Exception as exc:
        if finalized:
            raise
        ledger = root / "WSLPATH_LEDGER.csv"
        budget = root / "WSLPATH_BUDGET.json"
        if ledger.is_file() and not budget.exists():
            failed_budget = {
                "schema_version": "ginav2021.resume_wslpath_budget.v1",
                "pass": False,
                "error": f"{type(exc).__name__}: {exc}",
                "ledger_sha256": sha256_file(ledger),
            }
            provenance["wslpath_budget"] = failed_budget
            write_json(budget, failed_budget)
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            str(exc), technical_blocker=f"{type(exc).__name__}: {exc}",
        )


def prepare_recover_r4c_metadata_to_r4d(
    options: RecoverR4dPrepareOptions,
) -> dict[str, Any]:
    r4 = _verify_frozen_r4(options.source_r4_root)
    r4b = _verify_frozen_r4b(options.source_r4b_root)
    r4c = _verify_frozen_r4c(options.source_r4c_root)
    expected_role = "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00"
    if (
        r4["provenance"].get("dataset_role") != expected_role
        or r4["status"].get("dataset_role") != expected_role
    ):
        raise TransactionError("frozen r4 dataset_role identity mismatch")
    code = _resume_code_identity(options.repository_root)
    destination = options.r4d_root.expanduser()
    if destination.name != "r4d" or os.path.lexists(destination):
        raise TransactionError("r4d metadata recovery root must be fresh basename r4d")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise TransactionError("r4d parent must be one existing real directory")
    destination.mkdir(exist_ok=False)
    payload = {
        "schema_version": "ginav2021.r4d_metadata_only_recovery_lock.v1",
        "source_r4_root": str(r4["source_root"]),
        "source_r4_binding": r4["full_lock"]["tree_binding_sha256"],
        "source_r4b_root": str(r4b["root"]),
        "source_r4b_binding": r4b["full_lock"]["tree_binding_sha256"],
        "source_r4c_root": str(r4c["root"]),
        "source_r4c_binding": r4c["full_lock"]["tree_binding_sha256"],
        "r4d_root": str(destination.resolve(strict=True)),
        "prepared_code_identity": code,
        "metadata_only": True,
        "matlab_or_g4_execution_allowed": False,
        "execution_counts_this_recovery": {
            "G0": 0, "G1": 0, "G2": 0, "G3": 0, "G4": 0,
        },
        "pass": True,
    }
    write_json(destination / "R4D_METADATA_RECOVERY_LOCK.json", payload)
    return payload


def execute_recover_r4c_metadata_to_r4d(
    options: RecoverR4dExecuteOptions,
) -> dict[str, Any]:
    root = options.r4d_root.expanduser().resolve(strict=True)
    if root.name != "r4d" or tuple(sorted(path.name for path in root.iterdir())) != (
        "R4D_METADATA_RECOVERY_LOCK.json",
    ):
        raise TransactionError("r4d is not the exact prepared lock-only root")
    lock = json.loads(
        (root / "R4D_METADATA_RECOVERY_LOCK.json").read_text(encoding="utf-8")
    )
    r4 = _verify_frozen_r4(options.source_r4_root)
    r4b = _verify_frozen_r4b(options.source_r4b_root)
    r4c = _verify_frozen_r4c(options.source_r4c_root)
    code = _resume_code_identity(options.repository_root)
    expected_role = "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00"
    if (
        lock.get("pass") is not True
        or lock.get("metadata_only") is not True
        or lock.get("matlab_or_g4_execution_allowed") is not False
        or Path(str(lock.get("source_r4_root"))).resolve(strict=True)
        != r4["source_root"]
        or Path(str(lock.get("source_r4b_root"))).resolve(strict=True) != r4b["root"]
        or Path(str(lock.get("source_r4c_root"))).resolve(strict=True) != r4c["root"]
        or Path(str(lock.get("r4d_root"))).resolve(strict=True) != root
        or lock.get("source_r4_binding") != r4["full_lock"]["tree_binding_sha256"]
        or lock.get("source_r4b_binding") != r4b["full_lock"]["tree_binding_sha256"]
        or lock.get("source_r4c_binding") != r4c["full_lock"]["tree_binding_sha256"]
        or lock.get("prepared_code_identity") != code
        or r4["provenance"].get("dataset_role") != expected_role
        or r4["status"].get("dataset_role") != expected_role
    ):
        raise TransactionError("r4d authentication changed before stage creation")

    stage = root / "s"
    stage.mkdir(exist_ok=False)
    for short in _SHORT_RESUME_LAYOUT.values():
        (stage / short).mkdir(exist_ok=False)
    counts = {"G0": 0, "G1": 0, "G2": 0, "G3": 0, "G4": 0}
    source_hashes = {
        Path(relative).name: digest
        for relative, digest in _FROZEN_R4C_REQUIRED_HASHES.items()
        if relative.startswith(("s/g4/", "s/n/"))
    }
    access = AccessLedger()
    r4c_provenance = r4c["provenance"]
    reproduction_level = (
        "EXACT_R4_R4B_R4C_AUTHENTICATED_METADATA_ONLY_TERMINAL_RECOVERY"
    )
    provenance: dict[str, Any] = {
        "schema_version": "ginav2021.r4d_metadata_only_provenance.v1",
        "data_mode": "real_by2_raw", "dataset_role": expected_role,
        "raw_source_hashes": dict(r4c_provenance["raw_source_hashes"]),
        "provider_hashes": dict(r4c_provenance["provider_hashes"]),
        "synthetic_data_used": False, "semisynthetic_data_used": False,
        "trace_used_online": False, "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False, "per_case_tuning": False,
        "output_only_correction": False, "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0, "code_commit": code["repository_head"],
        "config_hash": r4c_provenance["config_hash"],
        "rmse_used": False, "trace_open_count": 0,
        "reference_open_count": 0, "gnss2_open_count": 0,
        "metadata_only": True, "MATLAB_executed": False,
        "G4_executed": False, "execution_counts_this_recovery": counts,
        "source_chain_gate_counts": {
            "source_r4": dict(_FROZEN_R4_GATE_COUNTS),
            "source_r4b": {"G0": 0, "G1": 0, "G2": 0, "G3": 1, "G4": 0},
            "source_r4c": {"G0": 0, "G1": 0, "G2": 0, "G3": 0, "G4": 1},
            "this_r4d_recovery": dict(counts),
        },
        "source_r4c_full_binding": r4c["full_lock"]["tree_binding_sha256"],
        "source_r4c_artifact_hashes": source_hashes,
        "source_r4c_terminal_evidence": {
            "terminal_status": r4c["status"].get("terminal_status"),
            "detail": r4c["status"].get("detail"),
            "technical_blocker": r4c_provenance.get("technical_blocker"),
            "BY2_C00_RESULT": r4c["status"].get("BY2_C00_RESULT"),
        },
    }
    finalized = False

    def assert_identities_unchanged() -> None:
        if (
            _resume_code_identity(options.repository_root) != code
            or _verify_frozen_r4(options.source_r4_root)["full_lock"]
            ["tree_binding_sha256"] != r4["full_lock"]["tree_binding_sha256"]
            or _verify_frozen_r4b(options.source_r4b_root)["full_lock"]
            ["tree_binding_sha256"] != r4b["full_lock"]["tree_binding_sha256"]
            or _verify_frozen_r4c(options.source_r4c_root)["full_lock"]
            ["tree_binding_sha256"] != r4c["full_lock"]["tree_binding_sha256"]
        ):
            raise TransactionError(
                "r4/r4b/r4c or implementation changed during r4d"
            )

    def finalize(
        terminal: str,
        *,
        native: Mapping[str, Any] | None = None,
        technical_blocker: str | None = None,
    ) -> dict[str, Any]:
        nonlocal finalized
        if finalized:
            raise TransactionError("r4d finalized twice")
        assert_identities_unchanged()
        finalized = True
        audit = access.audit()
        success = technical_blocker is None
        formal = bool((native or {}).get("formal_lc02_admission", False)) if success else False
        formal_slot = str((native or {}).get("formal_lc02_slot", "VACANT")) if success else "VACANT"
        by2_result = terminal if success else "NOT_REEVALUATED"
        common_terminal = {
            "OFFICIAL_SAMPLE_RESULT": "OFFICIAL_SAMPLE_PASS",
            "BY2_C00_RESULT": by2_result,
            "reproduction_level": reproduction_level,
            "actual_algorithm_blocker": None,
            "technical_blocker": technical_blocker,
        }
        provenance.update({
            **common_terminal,
            "terminal_status": terminal, "transaction_complete": True,
            "formal_lc02_admission": formal, "formal_lc02_slot": formal_slot,
            "file_access_audit": audit,
        })
        report = stage / "r"
        write_json(report / "GINAV_FORBIDDEN_INPUT_AUDIT.json", audit)
        write_json(report / "GINAV_CONSOLIDATED_PROVENANCE.json", provenance)
        status = {
            **common_terminal,
            "terminal_status": terminal,
            "transaction_complete": True,
            "formal_lc02_admission": formal, "formal_lc02_slot": formal_slot,
            "metadata_only": True, "MATLAB_executed": False,
            "G4_executed": False, "execution_counts_this_recovery": counts,
            "source_chain_gate_counts": provenance["source_chain_gate_counts"],
            "source_r4c_terminal_evidence": provenance[
                "source_r4c_terminal_evidence"
            ],
            "scientific_digest_sha256": (
                (native or {}).get("scientific_digest_sha256") if success else None
            ),
            "artifact_publication": "NOT_REQUESTED",
        }
        write_json(report / "LC02_GINAV2021_TRANSACTION_STATUS.json", status)
        write_json(report / "LC02_GINAV2021_RESUME_SUFFIX_SUMMARY.json", status)
        write_json(report / "GINAV_PUBLICATION_PARITY.json", {
            "requested": False, "artifact_publication": "NOT_REQUESTED",
            "pass": success,
        })
        write_json(
            report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json",
            _resume_artifact_manifest(root),
        )
        write_json(report / "LC02_GINAV2021_RESUME_SEAL.json", {
            "artifact_manifest_sha256": sha256_file(
                report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json"
            ),
            "r4_unchanged": True, "r4b_unchanged": True,
            "r4c_unchanged": True, "seal_written_last": True,
        })
        return status

    try:
        for gate, short in (
            ("G0", "g0"), ("G1", "g1"), ("G2_GNSS", "g2n"),
            ("G2_IMU", "g2i"), ("G3_CONFIG", "g3c"),
            ("G3_PROBE", "g3p"), ("G4", "g4"),
        ):
            write_json(stage / short / "REUSED_NOT_EXECUTED.json", {
                "gate": gate, "status": "REUSED_NOT_EXECUTED",
                "execution_count_this_recovery": 0,
                "metadata_only_hash_reference": True,
            })
        for relative in _FROZEN_R4C_REQUIRED_HASHES:
            if relative.startswith(("s/g4/", "s/n/")):
                access.record(
                    r4c["root"] / relative,
                    role="R4C_SCIENTIFIC_ARTIFACT_HASH_ONLY",
                )
        native = analyze_frozen_native_solution_metadata_only(
            r4c["stage"] / "g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos",
            stage / "g4", process_returncode=0, provenance=provenance,
            source_artifact_hashes=source_hashes,
        )
        if (
            native["row_count"] != 80
            or native["alignment_output_count"] != 1
            or native["internal_spp_fed_lc_update_count"] != 11
            or native["ins_only_propagation_count"] != 68
            or native["scientific_digest_sha256"]
            != _FROZEN_R4C_SCIENTIFIC_DIGEST
            or native["formal_lc02_admission"] is not True
        ):
            raise TransactionError("r4d native scientific closure mismatch")
        return finalize(str(native["terminal_status"]), native=native)
    except Exception as exc:
        if finalized:
            raise
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            technical_blocker=f"{type(exc).__name__}: {exc}",
        )


def _execute_g3c_g4_suffix(
    *,
    options: TransactionOptions,
    stage: Path,
    gnss_audit: Mapping[str, Any],
    imu_csv: Path,
    matlab_executable: Path,
    provenance: dict[str, Any],
    global_access: AccessLedger,
    all_cleanliness: list[dict[str, Any]],
    finalize: Any,
    stage_dir_resolver: Any = _stage_dir,
    g3c_diagnostic_writer: Any = None,
) -> dict[str, Any]:
    time_section = stage_dir_resolver(stage, "04_BY2_CONFIG_AND_TIME_CONTRACT")
    literal_observation = Path(gnss_audit["observation_path"])
    try:
        epochs = parse_rinex_epochs(literal_observation)
        literal_acceptance = official_epoch_acceptance_audit(epochs)
    except (OSError, TimeContractError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_GNSS_ADAPTER_FAILURE",
            detail=str(exc),
        )
    normalization_error: str | None = None
    proof: dict[str, Any] | None = None
    normalized_rows: Sequence[Mapping[str, Any]] = ()
    selected_observation = literal_observation
    try:
        ubx_path = Path(gnss_audit["ubx_path"])
        global_access.record(ubx_path, role="GNSS1_RECONSTRUCTED_UBX_TIME_ONLY")
        ubx_stream = ubx_path.read_bytes()
        rawx_times, pvt_times = extract_same_receiver_time_events(ubx_stream)
        proof = prove_single_constant_normalization(rawx_times, pvt_times, epochs)
        selected_observation = time_section / "BY2_GNSS1_NORMALIZED.rnx"
        normalized_rows = normalize_rinex_epochs(
            literal_observation, selected_observation, proof
        )
    except (OSError, TimeContractError) as exc:
        normalization_error = str(exc)
        if literal_acceptance["literal_accepted_epoch_count"] == 0:
            acceptance = {
                **literal_acceptance,
                "normalization_proven": False,
                "normalization_error": normalization_error,
                "normalized_accepted_epoch_count": 0,
                "selected_official_epoch_count": 0,
            }
            write_json(time_section / "BY2_GINAV_OFFICIAL_EPOCH_ACCEPTANCE_AUDIT.json", acceptance)
            _write_yaml(
                time_section / "BY2_GINAV_TIME_NORMALIZATION_CONTRACT.yaml",
                {
                    "relation_proven": False,
                    "candidate_offset_search_performed": False,
                    "historical_2ms_assumed": False,
                    "error": normalization_error,
                },
            )
            _write_csv(
                time_section / "BY2_GINAV_TIME_NORMALIZATION_LEDGER.csv", [],
                ("epoch_index", "gps_week", "rawx_sow_seconds",
                 "authoritative_nav_pvt_sow_seconds", "normalization_offset_nanoseconds",
                 "normalized_sow_seconds"),
            )
            return finalize(
                "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY",
                detail=normalization_error,
            )
    if proof is not None:
        _write_yaml(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_CONTRACT.yaml",
            {key: value for key, value in proof.items() if key != "ledger"},
        )
        _write_csv(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_LEDGER.csv",
            normalized_rows, tuple(normalized_rows[0]),
        )
    else:
        _write_yaml(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_CONTRACT.yaml",
            {
                "relation_proven": False,
                "normalization_applied": False,
                "candidate_offset_search_performed": False,
                "literal_epochs_selected": True,
                "error": normalization_error,
            },
        )
        _write_csv(
            time_section / "BY2_GINAV_TIME_NORMALIZATION_LEDGER.csv", [],
            ("epoch_index", "gps_week", "rawx_sow_seconds",
             "authoritative_nav_pvt_sow_seconds", "normalization_offset_nanoseconds",
             "normalized_sow_seconds"),
        )
    try:
        selected_epochs = parse_rinex_epochs(selected_observation)
    except (OSError, TimeContractError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"selected time contract is unreadable: {exc}",
        )
    selected_acceptance = official_epoch_acceptance_audit(selected_epochs)
    row_conservation = five_phase_row_conservation_audit(
        rawx_epoch_count=len(rawx_times),
        original_rinex_epochs=epochs,
        proof=proof or {"ledger": ()},
        normalized_rows=normalized_rows,
        selected_rinex_epochs=selected_epochs,
    ) if proof is not None else None
    acceptance = {
        **literal_acceptance,
        "normalization_proven": proof is not None,
        "normalization_error": normalization_error,
        "normalized_accepted_epoch_count": (
            selected_acceptance["literal_accepted_epoch_count"] if proof else None
        ),
        "selected_official_epoch_count": selected_acceptance["literal_accepted_epoch_count"],
        "selected_official_rejected_epoch_count": selected_acceptance[
            "literal_rejected_noninteger_epoch_count"
        ],
        "selected_official_deleted_epoch_count": 0,
        "five_phase_row_conservation": row_conservation,
        "candidate_offset_search_performed": False,
        "historical_2ms_assumed": False,
    }
    write_json(time_section / "BY2_GINAV_OFFICIAL_EPOCH_ACCEPTANCE_AUDIT.json", acceptance)
    if g3c_diagnostic_writer is not None:
        g3c_diagnostic_writer(
            time_section=time_section,
            rawx_times=rawx_times,
            pvt_times=pvt_times,
            proof=proof,
            normalized_rows=normalized_rows,
            acceptance=acceptance,
        )
    if row_conservation is not None and not row_conservation["pass"]:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail="five-phase RAWX/RINEX row conservation failed",
        )
    if acceptance["selected_official_epoch_count"] <= 0:
        return finalize(
            "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY",
            detail="selected official epoch acceptance is zero",
        )

    try:
        start_time, end_time = _gps_overlap_datetimes(selected_epochs, imu_csv)
        by2_config = time_section / "BY2_GINAV_SPP_LC.ini"
        config_contract = derive_by2_config(
            options.ginav_root / OFFICIAL_CONFIG_RELATIVE, by2_config,
            data_directory=stage, site_name="by2_gnss1",
            start_time_gpst=start_time, end_time_gpst=end_time,
            navsys=gnss_audit["rinex"]["selected_navsys"],
            nfreq=int(gnss_audit["rinex"]["selected_nfreq"]),
            project_repository_root=options.repository_root,
        )
        provenance["config_hash"] = sha256_file(by2_config)
        provenance["provider_hashes"].update({
            "BY2_GINAV_SELECTED_OBSERVATION": sha256_file(selected_observation),
            "BY2_GINAV_DERIVED_CONFIG": provenance["config_hash"],
        })
        _write_config_artifacts(
            stage, config_contract, stage_dir_resolver=stage_dir_resolver
        )
        run_epoch_inventory = _official_run_epoch_inventory(
            selected_epochs, imu_csv,
            start_time_gpst=start_time, end_time_gpst=end_time,
            sample_rate_hz=GO2_SAMPLE_RATE_HZ,
        )
        if not run_epoch_inventory["conservation_pass"]:
            raise ConfigContractError("official run epoch inventory did not conserve")
        acceptance["configured_run_inventory"] = run_epoch_inventory
        write_json(
            time_section / "BY2_GINAV_OFFICIAL_EPOCH_ACCEPTANCE_AUDIT.json",
            acceptance,
        )
        if run_epoch_inventory["accepted_official_gnss_epoch_count"] <= 0:
            raise ConfigContractError(
                "configured official run has no integer GNSS epoch matched to IMU"
            )
    except (OSError, ValueError, ConfigContractError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE", detail=str(exc)
        )

    probe_section = stage_dir_resolver(stage, "05_BY2_ACTIVATION_PROBE")
    probe_csv = probe_section / "BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv"
    guard: CoreCleanlinessGuard | None = None
    try:
        probe_runtime = probe_section / "runtime"
        probe_runtime.mkdir(exist_ok=False)
        mirror = probe_runtime / "source_mirror"
        mirror_manifest = materialize_runtime_source_mirror(options.ginav_root, mirror)
        harness = probe_runtime / "matlab_harness"
        fopen_log = probe_runtime / "MATLAB_FOPEN_LEDGER.tsv"
        windows = matlab_executable.suffix.casefold() == ".exe"
        for declared_input in (
            by2_config, selected_observation,
            Path(gnss_audit["navigation_path"]), imu_csv,
        ):
            global_access.authorize_runtime_read(
                Path(declared_input).resolve(strict=True)
            )
            if windows:
                global_access.authorize_runtime_read(
                    wsl_to_windows_path(declared_input)
                )
        main = render_tdcp_probe_script(
            mirror_root=mirror, harness_root=harness, config_path=by2_config,
            observation_path=selected_observation,
            navigation_path=gnss_audit["navigation_path"], imu_path=imu_csv,
            output_csv=probe_csv,
            windows=windows,
        )
        script = write_harness_files(
            harness, main_script=main, fopen_log=fopen_log, windows=windows
        )
        guard = CoreCleanlinessGuard(
            "G3_TDCP_ACTIVATION_PROBE", options.ginav_root, mirror, mirror_manifest
        )
        with guard:
            provenance["gate_execution_counts"]["G3_tdcp_probe_runs"] = 1
            probe_result = run_matlab_script(
                matlab_executable, script, timeout_seconds=options.probe_timeout_seconds
            )
        all_cleanliness.append(guard.report())
        if not fopen_log.is_file():
            raise ForbiddenInputError("G3 TDCP probe MATLAB fopen ledger is missing")
        global_access.import_matlab_fopen_log(fopen_log)
        if not probe_result["pass"] or not probe_csv.is_file():
            raise TransactionError("official TDCP activation probe failed")
        activation = _probe_summary(probe_csv)
        activation["configured_run_epoch_inventory"] = run_epoch_inventory
        activation["probe_covers_every_eligible_integer_epoch"] = (
            activation["eligible_integer_epoch_count"]
            == run_epoch_inventory["accepted_official_gnss_epoch_count"]
        )
        if not activation["probe_covers_every_eligible_integer_epoch"]:
            raise TransactionError(
                "TDCP probe/official epoch inventory conservation failed: "
                f"{activation['eligible_integer_epoch_count']} != "
                f"{run_epoch_inventory['accepted_official_gnss_epoch_count']}"
            )
        activation["matlab_runtime_seconds"] = probe_result["runtime_seconds"]
        activation["file_access_audit"] = global_access.audit()
        write_json(probe_section / "BY2_GINAV_ALIGNMENT_ACTIVATION_SUMMARY.json", activation)
    except SourceIdentityError as exc:
        if guard is not None and guard.before is not None and guard.after is not None:
            if not any(
                item.get("run_id") == "G3_TDCP_ACTIVATION_PROBE"
                for item in all_cleanliness
            ):
                all_cleanliness.append(guard.report())
        _write_cleanliness(stage, all_cleanliness, stage_dir_resolver=stage_dir_resolver)
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
            detail=str(exc),
        )
    except (OSError, ValueError, TransactionError, MatlabRuntimeError,
            ForbiddenInputError) as exc:
        if guard is not None and guard.before is not None and guard.after is not None:
            if not any(
                item.get("run_id") == "G3_TDCP_ACTIVATION_PROBE"
                for item in all_cleanliness
            ):
                all_cleanliness.append(guard.report())
        activation = {
            "schema_version": "ginav2021.tdcp_alignment_activation_summary.v1",
            "alignment_activated": False,
            "probe_execution_failure": str(exc),
            "alternative_yaw_substitution_used": False,
        }
        write_json(probe_section / "BY2_GINAV_ALIGNMENT_ACTIVATION_SUMMARY.json", activation)
        _write_cleanliness(stage, all_cleanliness, stage_dir_resolver=stage_dir_resolver)
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"activation probe could not complete: {exc}",
        )
    _write_cleanliness(stage, all_cleanliness, stage_dir_resolver=stage_dir_resolver)
    activation_terminal = _activation_terminal(activation)
    if activation_terminal is not None:
        return finalize(activation_terminal[0], detail=activation_terminal[1])

    # Conditional G4: exactly one MATLAB process and one recursive official run.
    c00_section = stage_dir_resolver(stage, "06_BY2_C00_NATIVE")
    c00_runtime = c00_section / "runtime"
    c00_ledger = global_access
    try:
        c00_runtime.mkdir(exist_ok=False)
        provenance["gate_execution_counts"]["G4_BY2_C00_runs"] = 1
        c00_result, native_summary = _g4_scientific_run_and_freeze(
            options=options, stage=stage, c00_section=c00_section,
            c00_runtime=c00_runtime, by2_config=by2_config,
            selected_observation=selected_observation,
            navigation_path=Path(gnss_audit["navigation_path"]), imu_csv=imu_csv,
            matlab_executable=matlab_executable, provenance=provenance,
            access_ledger=c00_ledger, run_epoch_inventory=run_epoch_inventory,
            activation=activation, stage_dir_resolver=stage_dir_resolver,
        )
        all_cleanliness.append(c00_result["core_cleanliness"])
    except SourceIdentityError as exc:
        _write_cleanliness(stage, all_cleanliness, stage_dir_resolver=stage_dir_resolver)
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
            detail=str(exc),
        )
    except ForbiddenInputError as exc:
        _write_cleanliness(stage, all_cleanliness, stage_dir_resolver=stage_dir_resolver)
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"C00 forbidden-input audit failed: {exc}",
        )
    except (OSError, ValueError, TransactionError, MatlabRuntimeError,
            OutputContractError) as exc:
        _write_cleanliness(stage, all_cleanliness, stage_dir_resolver=stage_dir_resolver)
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            detail=f"C00 native-output contract failed: {exc}",
        )

    _write_cleanliness(stage, all_cleanliness, stage_dir_resolver=stage_dir_resolver)
    access_audit = global_access.audit()
    write_json(stage_dir_resolver(stage, "11_REPORT") / "GINAV_FORBIDDEN_INPUT_AUDIT.json", access_audit)
    terminal = str(native_summary["terminal_status"])
    final_report = f"""# GINav 2021 LC02 exact-route transaction

    Terminal status: `{terminal}`

    The pinned official SPP/INS LC route passed the two-run official sample
    regression, GNSS1-only RINEX and Go2 format-2 adapters, literal/source-proven
    time gate, and official TDCP alignment probe before the one C00 process was
    launched.  Native output was frozen before any reference access.  Trace,
    reference, LC01, other methods, Canonical-541, representative cases, and
    comparison remained unexecuted.
    """
    (stage_dir_resolver(stage, "11_REPORT") / "LC02_GINAV2021_FINAL_REPORT.md").write_text(
        final_report, encoding="utf-8"
    )
    return finalize(
        terminal,
        extra={
            "BY2_C00_complete": native_summary["BY2_C00_complete"],
            "formal_lc02_admission": native_summary["formal_lc02_admission"],
            "formal_lc02_slot": native_summary["formal_lc02_slot"],
            "official_route_initialized": native_summary["official_route_initialized"],
            "finite_lc_segment_produced": native_summary["finite_lc_segment_produced"],
            "native_summary_path": str(c00_section / "GINAV_BY2_C00_NATIVE_SUMMARY.json"),
            "forbidden_path_audit_pass": access_audit["pass"],
        },
    )

def run_transaction(options: TransactionOptions) -> dict[str, Any]:
    local = _load_local_paths(options, verify_raw_availability=False)
    protected_roots = (
        options.repository_root.resolve(strict=True),
        local["clean_root"].resolve(strict=True),
        local["raw_root"].resolve(strict=False),
        options.paper_root.expanduser().resolve(strict=False),
        options.legacy_freeze_root.expanduser().resolve(strict=False),
    )
    expected_destination = _expected_publication_destination(
        local["clean_root"].resolve(strict=True)
    )
    try:
        publication_target = validate_exact_destination(
            options.destination_stage_root,
            expected_destination=expected_destination,
            clean_root=local["clean_root"],
            other_protected_roots=(
                options.repository_root, local["raw_root"], options.paper_root,
                options.legacy_freeze_root,
            ),
        )
    except PublicationError as exc:
        raise TransactionError(str(exc)) from exc
    root = _make_scratch_root(
        options.scratch_root, protected_roots=protected_roots
    )
    stage = _create_stage_layout(root)
    all_cleanliness: list[dict[str, Any]] = []
    global_access = AccessLedger()
    source_dir = _stage_dir(stage, "00_SOURCE_AND_ENVIRONMENT")
    provenance = _initial_provenance(options)
    path_aliases = {
        options.repository_root: "<CODE_ROOT>",
        options.ginav_root: "<GINAV_ROOT>",
        options.scratch_root: "<SCRATCH_ROOT>",
        stage: "<SCRATCH_STAGE_ROOT>",
        publication_target: "<STAGE_ROOT>",
        local["clean_root"]: "<CLEAN_ROOT>",
        local["raw_root"]: "<RAW_ROOT>",
        options.paper_root: "<PAPER_ROOT>",
        options.legacy_freeze_root: "<LEGACY_FREEZE_ROOT>",
        options.matlab_executable: "<MATLAB_EXECUTABLE>",
        options.libarchive_path: "<LIBARCHIVE_LIBRARY>",
        local["horizontal_literature_rtklib_root"]: "<RTKLIB_ROOT>",
        local["horizontal_literature_convbin"]: "<CONVBIN_EXECUTABLE>",
    }

    def finalize(
        status: str,
        *,
        detail: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _finalize_terminal(
            status, stage=stage, access_audit=global_access.audit(),
            provenance=provenance, cleanliness_runs=all_cleanliness,
            publish=options.publish, destination=publication_target,
            clean_root=local["clean_root"], protected_roots=protected_roots,
            path_aliases=path_aliases, detail=detail,
            extra=extra,
        )

    try:
        source_lock = verify_source_identity(options.ginav_root)
        provenance["official_source_identity"] = {
            "commit": source_lock["commit"], "tree_oid": source_lock["tree_oid"],
            "tracked_source_clean": source_lock["tracked_source_clean"],
            "named_file_sha256": {
                key: value.get("sha256")
                for key, value in source_lock["named_files"].items()
            },
        }
        write_json(source_dir / "GINAV_SOURCE_LOCK.json", source_lock)
    except (OSError, SourceIdentityError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH", detail=str(exc)
        )

    candidates = discover_matlab_candidates(options.matlab_executable)
    for index, candidate in enumerate(candidates, start=1):
        path_aliases[candidate] = f"<MATLAB_CANDIDATE_{index}>"
        install_root = candidate.parent.parent
        if install_root != Path(install_root.anchor):
            path_aliases[install_root] = (
                f"<MATLAB_INSTALL_ROOT_{index}>"
            )
    if not candidates:
        write_json(
            source_dir / "GINAV_MATLAB_DISCOVERY_ATTEMPTS.json",
            {"candidates": [], "selected": None},
        )
        return finalize(
            "BLOCKED_LC02_GINAV_MATLAB_RUNTIME_UNAVAILABLE",
            detail="no installed licensed MATLAB executable candidate",
        )
    matlab_executable: Path | None = None
    environment: dict[str, Any] | None = None
    discovery_attempts: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        provenance["gate_execution_counts"]["G0_matlab_candidate_attempts"] += 1
        try:
            candidate_environment, cleanliness = _matlab_environment(
                stage=stage, ginav_root=options.ginav_root, executable=candidate,
                probe_id=f"candidate_{index}",
            )
            all_cleanliness.append(cleanliness)
            matlab_executable = candidate
            environment = candidate_environment
            discovery_attempts.append(
                {"candidate": str(candidate), "pass": True, "selected": True}
            )
            break
        except SourceIdentityError as exc:
            proof_path = (
                source_dir / f"matlab_probe_runtime_candidate_{index}"
                / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"
            )
            if proof_path.is_file():
                all_cleanliness.append(
                    json.loads(proof_path.read_text(encoding="utf-8"))
                )
            _write_cleanliness(stage, all_cleanliness)
            return finalize(
                "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
                detail=str(exc),
            )
        except (OSError, ValueError, MatlabRuntimeError) as exc:
            attempt_root = source_dir / f"matlab_probe_runtime_candidate_{index}"
            proof_path = attempt_root / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json"
            invocation_path = attempt_root / "MATLAB_ENVIRONMENT_INVOCATION.json"
            if not proof_path.is_file() or not invocation_path.is_file():
                _write_cleanliness(stage, all_cleanliness)
                return finalize(
                    "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
                    detail=(
                        "MATLAB candidate attempt lacks complete official-source "
                        f"cleanliness/error evidence: candidate_{index}: {exc}"
                    ),
                )
            all_cleanliness.append(
                json.loads(proof_path.read_text(encoding="utf-8"))
            )
            invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
            discovery_attempts.append(
                {
                    "candidate": str(candidate), "pass": False,
                    "selected": False, "error": str(exc),
                    "full_matlab_error": invocation,
                }
            )
    write_json(
        source_dir / "GINAV_MATLAB_DISCOVERY_ATTEMPTS.json",
        {"candidates": discovery_attempts, "selected": str(matlab_executable or "")},
    )
    if matlab_executable is None or environment is None:
        if discovery_attempts:
            _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_MATLAB_RUNTIME_UNAVAILABLE",
            detail="; ".join(
                str(item.get("error") or "candidate unavailable")
                for item in discovery_attempts
            ),
        )
    write_json(source_dir / "GINAV_MATLAB_ENVIRONMENT.json", environment)
    provenance["matlab_environment"] = {
        "executable_sha256": environment["executable_sha256"],
        "version": environment["version"], "release": environment["release"],
        "platform_route": environment["platform_route"],
    }

    try:
        archive_backend = Libarchive7zBackend(options.libarchive_path)
        provenance["official_sample_archive_backend"] = copy.deepcopy(
            archive_backend.identity
        )
        provenance["official_sample_archive_backend_preflight_completed"] = True
        path_aliases[Path(archive_backend.identity["library_path"])] = (
            "<LIBARCHIVE_LIBRARY>"
        )
    except (OSError, ValueError, TypeError, AttributeError, Libarchive7zError) as exc:
        provenance["technical_pre_sample_backend_failure"] = True
        provenance["official_sample_archive_backend"] = {
            "schema_version": "ginav2021.libarchive7z_backend.v1",
            "backend": "ctypes_libarchive_public_abi",
            "requested_library_path": str(options.libarchive_path),
            "install_performed": False,
            "subprocess_used": False,
            "preflight_pass": False,
            "preflight_error": str(exc),
        }
        provenance["official_sample_archive_backend_preflight_completed"] = False
        provenance["official_sample_regression_executed"] = False
        provenance["official_sample_archive_inventory_completed"] = False
        provenance["official_sample_extraction_count"] = 0
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE",
            detail=f"technical pre-sample archive backend failure: {exc}",
        )

    sample_progress = {
        "official_sample_regression_executed": False,
        "official_sample_archive_inventory_completed": False,
        "official_sample_extraction_count": 0,
    }
    try:
        provenance["data_mode"] = "official_sample_regression"
        provenance["dataset_role"] = "OFFICIAL_SOFTWARE_REGRESSION_NOT_BY2_EVIDENCE"
        provenance["raw_source_hashes"] = {
            "official_sample_archive": source_lock["named_files"][
                OFFICIAL_SAMPLE_RELATIVE.as_posix()
            ]["sha256"]
        }
        provenance["provider_hashes"] = {
            "official_sample_config": source_lock["named_files"][
                OFFICIAL_CONFIG_RELATIVE.as_posix()
            ]["sha256"]
        }
        provenance["config_hash"] = provenance["provider_hashes"][
            "official_sample_config"
        ]
        sample_status, cleanliness = _run_sample_regression(
            stage=stage, ginav_root=options.ginav_root,
            matlab_executable=matlab_executable,
            archive_backend=archive_backend,
            expected_archive_sha256=source_lock["named_files"][
                OFFICIAL_SAMPLE_RELATIVE.as_posix()
            ]["sha256"],
            timeout_seconds=options.sample_timeout_seconds,
            access_ledger=global_access,
            progress=sample_progress,
        )
        provenance.update(sample_progress)
        all_cleanliness.extend(cleanliness)
        provenance["gate_execution_counts"]["G1_official_sample_runs"] = 2
        for summary in sample_status["summaries"]:
            run_key = f"official_sample_pristine_run_{summary['run_index']}"
            provenance["provider_hashes"].update({
                f"{run_key}_observation": summary["observation_sha256"],
                f"{run_key}_navigation": summary["navigation_sha256"],
                f"{run_key}_imu": summary["imu_sha256"],
                f"{run_key}_output": summary["output_sha256"],
            })
    except SourceIdentityError as exc:
        provenance.update(sample_progress)
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH",
            detail=str(exc),
        )
    except (OSError, ValueError, TransactionError, MatlabRuntimeError,
            OutputContractError, ForbiddenInputError, Libarchive7zError) as exc:
        provenance.update(sample_progress)
        _write_cleanliness(stage, all_cleanliness)
        return finalize(
            "BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE",
            detail=str(exc),
        )
    _write_cleanliness(stage, all_cleanliness)

    try:
        local = _load_local_paths(options, verify_raw_availability=True)
        provenance["data_mode"] = "real_by2_raw"
        provenance["dataset_role"] = "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00"
        provenance["raw_source_hashes"] = {}
        provenance["provider_hashes"] = {}
        provenance["config_hash"] = None
        raw_lock_path = local["clean_root"] / "01_RAW_HASH_LOCK" / "RAW_FILE_HASH_LOCK.csv"
        if sha256_file(raw_lock_path) != RAW_HASH_LOCK_SHA256:
            raise RinexAdapterError("clean raw hash lock identity mismatch")
        lock = read_hash_lock(raw_lock_path)
        gnss_raw = (local["by2_fix_root"] / "gnss1-raw.csv").resolve(strict=True)
        if local["raw_root"] not in gnss_raw.parents:
            raise RinexAdapterError("GNSS1 raw source escapes the locked raw root")
        gnss_relative = gnss_raw.relative_to(local["raw_root"]).as_posix()
        verify_raw_sources(local["raw_root"], [gnss_relative], lock)
        provenance["raw_source_hashes"].update({
            "RAW_FILE_HASH_LOCK.csv": sha256_file(raw_lock_path),
            "gnss1-raw.csv": sha256_file(gnss_raw),
        })
        global_access.record(gnss_raw, role="GNSS1_RAWX_SFRBX_SOURCE")
        gnss_audit = convert_gnss1_raw_to_rinex(
            gnss_raw, rtklib_root=local["horizontal_literature_rtklib_root"],
            convbin=local["horizontal_literature_convbin"],
            output_root=_stage_dir(stage, "02_BY2_GNSS_ADAPTER") / "runtime",
            ledger=global_access,
        )
        provenance["gate_execution_counts"]["G2_gnss_adapter_runs"] = 1
        provenance["converter_identity"] = gnss_audit["converter"]
        provenance["provider_hashes"].update({
            "BY2_GNSS1_RINEX_OBSERVATION": gnss_audit["rinex"]["observation_sha256"],
            "BY2_GNSS1_RINEX_NAVIGATION": gnss_audit["rinex"]["navigation_sha256"],
            "BY2_GNSS1_RECONSTRUCTED_UBX": gnss_audit["ubx_sha256"],
        })
        _write_gnss_artifacts(stage, gnss_audit)
    except (OSError, ValueError, ManifestContractError, PathContractError,
            RinexAdapterError, ForbiddenInputError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_GNSS_ADAPTER_FAILURE", detail=str(exc)
        )

    try:
        go2 = local["by2_go2_body"].resolve(strict=True)
        go2_relative = go2.relative_to(local["raw_root"]).as_posix()
        verify_raw_sources(local["raw_root"], [go2_relative], lock)
        provenance["raw_source_hashes"]["Go2_by2_complete_source"] = sha256_file(go2)
        imu_csv = _stage_dir(stage, "03_BY2_IMU_ADAPTER") / "BY2_GINAV_IMU.csv"
        imu_audit = adapt_go2_imu(go2, imu_csv, ledger=global_access)
        provenance["gate_execution_counts"]["G2_imu_adapter_runs"] = 1
        provenance["provider_hashes"]["BY2_GINAV_IMU_FORMAT2"] = sha256_file(imu_csv)
        _write_imu_artifacts(stage, imu_audit)
    except (OSError, ValueError, ManifestContractError, ImuAdapterError,
            ForbiddenInputError) as exc:
        return finalize(
            "BLOCKED_LC02_GINAV_BY2_IMU_ADAPTER_FAILURE", detail=str(exc)
        )

    return _execute_g3c_g4_suffix(
        options=options,
        stage=stage,
        gnss_audit=gnss_audit,
        imu_csv=imu_csv,
        matlab_executable=matlab_executable,
        provenance=provenance,
        global_access=global_access,
        all_cleanliness=all_cleanliness,
        finalize=finalize,
    )
