from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import struct

import pytest

from legsa_gins.paper_rebuild.horizontal_literature.ginav2021 import transaction as transaction_module
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.config_contract import (
    allan_psd_mapping,
    derive_by2_config,
    lever_frd_to_rfu,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.constants import (
    LEVER_FRD_M,
    LEVER_RFU_M,
    OFFICIAL_CONFIG_RELATIVE,
    OFFICIAL_POS_COLUMNS,
    POOR_APPLICABILITY_STATUS,
    STANDARD_NAV_COLUMNS,
    STAGE_NAME,
    SUCCESS_STATUS,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.outputs import (
    OfficialSolutionRow,
    OutputContractError,
    analyze_frozen_native_solution_metadata_only,
    formal_admission,
    freeze_native_solution,
    standard_nav_row,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.publication import (
    FINAL_STATUS_RELATIVE,
    PARITY_RELATIVE,
    PublicationError,
    _guarded_atomic_rename,
    _json_bytes,
    _publication_temporary_root,
    _replace_aliases,
    _sanitized_bytes,
    compact_artifact_paths,
    publish_compact_stage,
    validate_exact_destination,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.source import (
    AccessLedger,
    ForbiddenInputError,
)
from legsa_gins.paper_rebuild.horizontal_literature.ginav2021.transaction import (
    ExecuteResumeExistingR4Options,
    RecoverR4cExecuteOptions,
    RecoverR4cPrepareOptions,
    RecoverR4dExecuteOptions,
    RecoverR4dPrepareOptions,
    ResumeExistingR4Options,
    TransactionError,
    _activation_terminal,
    _create_stage_layout,
    _finalize_terminal,
    _hash_lock_tree,
    _wslpath_budget_audit,
    _make_scratch_root,
    _write_cleanliness,
    _zero_native_output_terminal,
    prepare_resume_existing_r4_from_g3c,
    execute_resume_existing_r4_from_g3c,
    execute_recover_r4b_g3_to_r4c_g4,
    execute_recover_r4c_metadata_to_r4d,
    prepare_recover_r4b_g3_to_r4c_g4,
    prepare_recover_r4c_metadata_to_r4d,
)


REPOSITORY = Path(__file__).resolve().parents[2]
TDCP_TERMINAL = "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET"
R4_TERMINAL = "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY"
R4_COUNTS = {
    "G0_matlab_candidate_attempts": 0,
    "G1_official_sample_runs": 2,
    "G2_gnss_adapter_runs": 1,
    "G2_imu_adapter_runs": 1,
    "G3_tdcp_probe_runs": 0,
    "G4_BY2_C00_runs": 0,
}


def _fixture_code_identity() -> dict[str, object]:
    return {
        "repository_head": "h" * 40,
        "approved_tracked_diff_sha256": "d" * 64,
        "aggregate_binding_sha256": "a" * 64,
        "untracked_files_enumerated_or_hashed": False,
    }


def _write_json_fixture(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _r4_fixture(tmp_path: Path) -> Path:
    source = tmp_path / "r4"
    stage = source / "s"
    for name in ("g0", "g1", "g2i", "g2n", "g3c", "g3p", "g4", "n", "r"):
        (stage / name).mkdir(parents=True)
    for name in ("g0", "g1", "g2n", "g2i"):
        _write_json_fixture(stage / name / "evidence.json", {"gate": name})
    matlab = tmp_path / "matlab.exe"
    matlab.write_bytes(b"licensed-matlab-fixture")
    _write_json_fixture(stage / "g0/GINAV_MATLAB_ENVIRONMENT.json", {
        "executable_sha256": hashlib.sha256(matlab.read_bytes()).hexdigest(),
    })
    provenance_path = stage / "r/GINAV_CONSOLIDATED_PROVENANCE.json"
    _write_json_fixture(provenance_path, {"fixture": "source-r4-provenance"})
    common: dict[str, object] = {
        "terminal_status": R4_TERMINAL,
        "formal_lc02_admission": False,
        "OFFICIAL_SAMPLE_RESULT": "OFFICIAL_SAMPLE_PASS",
        "BY2_C00_executed": False,
        "transaction_complete": True,
        "G0_execution_this_resume": 0,
        "G0_execution_this_continuation": 0,
    }
    status = {
        **common,
        "scientific_terminal_status": R4_TERMINAL,
        "official_sample_regression_executed": True,
        "official_sample_archive_inventory_completed": True,
        "official_sample_extraction_count": 2,
    }
    _write_json_fixture(stage / "r/LC02_GINAV2021_TRANSACTION_STATUS.json", status)
    _write_json_fixture(
        stage / "r/GINAV_CONSOLIDATED_PROVENANCE.json",
        {**common, "gate_execution_counts": R4_COUNTS},
    )
    _write_json_fixture(
        stage / "r/LC02_GINAV2021_POST_G0_RESUME_SUMMARY.json",
        {**common, "gate_execution_counts": R4_COUNTS},
    )
    for name in (
        "LC02_GINAV2021_RESUME_20260826.py",
        "LONG_PATH_FAILURE_TREE_MANIFEST.json",
        "MATLAB_WINDOWS_PATH_BUDGET.json",
        "PREVIOUS_CONTINUATION_HASH_MANIFEST.json",
        "PREVIOUS_RESUME_HASH_MANIFEST.json",
        "PRE_EXECUTION_CONTROL.json",
        "WSLPATH_CONVERSION_LEDGER.jsonl",
    ):
        (source / name).write_text(f"fixture:{name}\n", encoding="utf-8")
    return source


def _fixture_frozen_identity(source: Path) -> dict[str, object]:
    section_paths = {
        "G0": source / "s/g0",
        "G1": source / "s/g1",
        "G2_GNSS": source / "s/g2n",
        "G2_IMU": source / "s/g2i",
    }
    required = (
        "s/r/LC02_GINAV2021_TRANSACTION_STATUS.json",
        "s/r/GINAV_CONSOLIDATED_PROVENANCE.json",
        "s/r/LC02_GINAV2021_POST_G0_RESUME_SUMMARY.json",
        "LC02_GINAV2021_RESUME_20260826.py",
        "PRE_EXECUTION_CONTROL.json",
    )
    return {
        "root_basename": "r4",
        "top_level_entries": tuple(sorted(path.name for path in source.iterdir())),
        "stage_entries": tuple(sorted(path.name for path in (source / "s").iterdir())),
        "full_tree_binding_sha256": _hash_lock_tree(source)["tree_binding_sha256"],
        "section_tree_binding_sha256": {
            gate: _hash_lock_tree(path)["tree_binding_sha256"]
            for gate, path in section_paths.items()
        },
        "required_file_sha256": {
            relative: hashlib.sha256((source / relative).read_bytes()).hexdigest()
            for relative in required
        },
    }


def test_resume_existing_r4_hash_locks_reuse_and_never_executes_g0_g1_g2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _r4_fixture(tmp_path)
    continuation = tmp_path / "r5"
    with pytest.raises(TransactionError, match="frozen file identity mismatch"):
        prepare_resume_existing_r4_from_g3c(
            ResumeExistingR4Options(source, continuation, tmp_path / "matlab.exe")
        )
    assert not continuation.exists()
    monkeypatch.setattr(
        transaction_module, "FROZEN_R4_RESUME_IDENTITY",
        _fixture_frozen_identity(source),
    )
    payload = prepare_resume_existing_r4_from_g3c(
        ResumeExistingR4Options(source, continuation, tmp_path / "matlab.exe")
    )
    counts = payload["gate_execution_counts_this_continuation"]
    assert counts["G0_matlab_candidate_attempts"] == 0
    assert counts["G1_official_sample_runs"] == 0
    assert counts["G2_gnss_adapter_runs"] == 0
    assert counts["G2_imu_adapter_runs"] == 0
    assert counts["G3_tdcp_probe_runs"] <= 1
    assert counts["G4_BY2_C00_runs"] <= 1
    assert payload["gate_reuse"] == {
        "G0": True, "G1": True, "G2_GNSS": True, "G2_IMU": True
    }
    assert payload["suffix_execution_caps"] == {
        "G3_tdcp_probe_runs": 1, "G4_BY2_C00_runs": 1
    }
    assert payload["resume_entry_phase"] == "READY_FROM_G3C_NOT_EXECUTED"
    assert payload["prepared_implementation_code_identity"] == (
        transaction_module._resume_code_identity(REPOSITORY)
    )
    assert [path.name for path in continuation.iterdir()] == [
        "SOURCE_R4_G0_G1_G2_HASH_LOCK.json"
    ]
    with pytest.raises(TransactionError, match="non-overwriting"):
        prepare_resume_existing_r4_from_g3c(
            ResumeExistingR4Options(source, continuation, tmp_path / "matlab.exe")
        )


def test_resume_existing_r4_rejects_one_byte_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _r4_fixture(tmp_path)
    monkeypatch.setattr(
        transaction_module, "FROZEN_R4_RESUME_IDENTITY",
        _fixture_frozen_identity(source),
    )
    (source / "s/g2i/evidence.json").write_bytes(b"one-byte-drift\n")
    with pytest.raises(TransactionError, match="section binding mismatch"):
        prepare_resume_existing_r4_from_g3c(
            ResumeExistingR4Options(source, tmp_path / "r5", tmp_path / "matlab.exe")
        )


@pytest.mark.parametrize(
    ("target", "mutation", "message"),
    (
        ("terminal", "WRONG_TERMINAL", "terminal differs"),
        ("G0_matlab_candidate_attempts", 1, "gate counts differ"),
        ("G3_tdcp_probe_runs", 1, "gate counts differ"),
    ),
)
def test_resume_existing_r4_rejects_wrong_terminal_g0_or_g3_even_if_rebound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    mutation: object,
    message: str,
) -> None:
    source = _r4_fixture(tmp_path)
    if target == "terminal":
        for name in (
            "LC02_GINAV2021_TRANSACTION_STATUS.json",
            "GINAV_CONSOLIDATED_PROVENANCE.json",
            "LC02_GINAV2021_POST_G0_RESUME_SUMMARY.json",
        ):
            path = source / "s/r" / name
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["terminal_status"] = mutation
            if "scientific_terminal_status" in payload:
                payload["scientific_terminal_status"] = mutation
            _write_json_fixture(path, payload)
    else:
        for name in (
            "GINAV_CONSOLIDATED_PROVENANCE.json",
            "LC02_GINAV2021_POST_G0_RESUME_SUMMARY.json",
        ):
            path = source / "s/r" / name
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["gate_execution_counts"][target] = mutation
            _write_json_fixture(path, payload)
    monkeypatch.setattr(
        transaction_module, "FROZEN_R4_RESUME_IDENTITY",
        _fixture_frozen_identity(source),
    )
    with pytest.raises(TransactionError, match=message):
        prepare_resume_existing_r4_from_g3c(
            ResumeExistingR4Options(source, tmp_path / "r5", tmp_path / "matlab.exe")
        )


def _executor_fixture(tmp_path: Path) -> tuple[ExecuteResumeExistingR4Options, dict[str, object]]:
    source = tmp_path / "r4"
    stage = source / "s"
    (stage / "g0").mkdir(parents=True)
    (stage / "g2n/runtime").mkdir(parents=True)
    (stage / "g2i").mkdir()
    (stage / "r").mkdir()
    obs = stage / "g2n/runtime/BY2_GNSS1.rnx"
    nav = stage / "g2n/runtime/BY2_GNSS1.nav"
    ubx = stage / "g2n/runtime/BY2_GNSS1.ubx"
    imu = stage / "g2i/BY2_GINAV_IMU.csv"
    for path, value in ((obs, b"obs"), (nav, b"nav"), (ubx, b"ubx"), (imu, b"imu")):
        path.write_bytes(value)
    gnss = {
        "rinex": {
            "observation_sha256": hashlib.sha256(b"obs").hexdigest(),
            "navigation_sha256": hashlib.sha256(b"nav").hexdigest(),
        },
        "ubx_sha256": hashlib.sha256(b"ubx").hexdigest(),
    }
    _write_json_fixture(stage / "g2n/BY2_GNSS1_RINEX_AUDIT.json", gnss)
    _write_json_fixture(stage / "g2i/BY2_GINAV_IMU_AUDIT.json", {
        "output_sha256": hashlib.sha256(b"imu").hexdigest()
    })
    matlab = tmp_path / "matlab.exe"
    matlab.write_bytes(b"licensed-matlab-fixture")
    _write_json_fixture(stage / "g0/GINAV_MATLAB_ENVIRONMENT.json", {
        "executable_sha256": hashlib.sha256(matlab.read_bytes()).hexdigest(),
    })
    provenance_path = stage / "r/GINAV_CONSOLIDATED_PROVENANCE.json"
    _write_json_fixture(provenance_path, {"fixture": "source-r4-provenance"})
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    (raw_root / "gnss1-raw.csv").write_text("data\n", encoding="ascii")
    continuation = tmp_path / "r4b"
    continuation.mkdir()
    prepared = {
        "schema_version": "ginav2021.resume_existing_r4_from_g3c.v1",
        "pass": True,
        "source_r4_root": str(source),
        "continuation_root": str(continuation),
        "source_full_tree_hash_lock": {"tree_binding_sha256": "frozen"},
        "prepared_matlab_identity": {
            "user_specified_absolute_path": str(matlab),
            "resolved_executable_path": str(matlab.resolve()),
            "executable_sha256": hashlib.sha256(matlab.read_bytes()).hexdigest(),
            "source_r4_environment_sha256": hashlib.sha256(
                (stage / "g0/GINAV_MATLAB_ENVIRONMENT.json").read_bytes()
            ).hexdigest(),
            "source_r4_expected_executable_sha256": hashlib.sha256(
                matlab.read_bytes()
            ).hexdigest(),
        },
        "prepared_implementation_code_identity": _fixture_code_identity(),
    }
    _write_json_fixture(
        continuation / "SOURCE_R4_G0_G1_G2_HASH_LOCK.json", prepared
    )
    verified: dict[str, object] = {
        "source_root": source,
        "source_stage": stage,
        "locks": {
            key: {"tree_binding_sha256": key.lower()}
            for key in ("G0", "G1", "G2_GNSS", "G2_IMU")
        },
        "full_lock": {"tree_binding_sha256": "frozen"},
        "status": {
            "terminal_status": R4_TERMINAL,
            "OFFICIAL_SAMPLE_RESULT": "OFFICIAL_SAMPLE_PASS",
        },
        "provenance_path": provenance_path,
        "provenance": {
            "code_commit": "c" * 40,
            "raw_source_hashes": {},
            "provider_hashes": {},
            "synthetic_data_used": False,
            "semisynthetic_data_used": False,
            "trace_used_online": False,
            "terminal_status": "POISONED_OLD_TERMINAL",
            "formal_lc02_admission": True,
            "transaction_complete": True,
            "file_access_audit": {"old": True},
            "BY2_C00_executed": True,
        },
    }
    options = ExecuteResumeExistingR4Options(
        repository_root=tmp_path,
        paths_config=tmp_path / "paths.yaml",
        ginav_root=tmp_path / "ginav",
        matlab_executable=matlab,
        source_r4_root=source,
        continuation_root=continuation,
    )
    verified["raw_root"] = raw_root
    return options, verified


def _mock_executor_preflight(
    monkeypatch: pytest.MonkeyPatch,
    verified: dict[str, object],
) -> None:
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4", lambda _path: verified)
    monkeypatch.setattr(
        transaction_module, "_resolve_hash_locked_resume_raw_csv",
        lambda _options: (
            verified["raw_root"] / "gnss1-raw.csv",
            {"RAW_FILE_HASH_LOCK.csv": "lock", "gnss1-raw.csv": "raw"},
        ),
    )
    reconstructed = type("Reconstructed", (), {"stream": b"ubx"})()
    monkeypatch.setattr(
        transaction_module, "reconstruct_ubx_stream",
        lambda *_args, **_kwargs: reconstructed,
    )
    monkeypatch.setattr(transaction_module, "_raw_csv_message_metadata", lambda _path: ())
    monkeypatch.setattr(
        transaction_module, "runtime_source_mirror_relative_files",
        lambda _root: ("src/main_func/exepos.m", "src/read_file/decode_cfg.m"),
    )
    monkeypatch.setattr(
        transaction_module, "_resume_code_identity",
        lambda _root: _fixture_code_identity(),
    )
    def budget(paths: object, ledger: Path) -> dict[str, object]:
        ledger.write_text("sequence,windows_path_character_count\n1,100\n", encoding="utf-8")
        return {
            "pass": True, "all_paths_within_budget": True,
            "path_count": len(tuple(paths)), "maximum_windows_path_character_count": 100,
        }
    monkeypatch.setattr(transaction_module, "_wslpath_budget_audit", budget)
    for forbidden in ("convert_gnss1_raw_to_rinex", "adapt_go2_imu", "_run_sample_regression"):
        monkeypatch.setattr(
            transaction_module, forbidden,
            lambda *_args, _name=forbidden, **_kwargs: pytest.fail(
                f"forbidden G0/G1/G2 call: {_name}"
            ),
        )


@pytest.mark.parametrize("g4", (0, 1))
def test_execute_resume_calls_no_g0_g2_and_g3_stop_or_single_g4_is_sealed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    g4: int,
) -> None:
    options, verified = _executor_fixture(tmp_path)
    _mock_executor_preflight(monkeypatch, verified)

    def suffix(**kwargs: object) -> dict[str, object]:
        provenance = kwargs["provenance"]
        provenance["gate_execution_counts"]["G3_tdcp_probe_runs"] = 1
        provenance["gate_execution_counts"]["G4_BY2_C00_runs"] = g4
        status = SUCCESS_STATUS if g4 else TDCP_TERMINAL
        return kwargs["finalize"](
            status, extra={"formal_lc02_admission": bool(g4)}
        )

    monkeypatch.setattr(transaction_module, "_execute_g3c_g4_suffix", suffix)
    payload = execute_resume_existing_r4_from_g3c(options)
    counts = payload["gate_execution_counts_this_continuation"]
    assert [counts[key] for key in (
        "G0_matlab_candidate_attempts", "G1_official_sample_runs",
        "G2_gnss_adapter_runs", "G2_imu_adapter_runs",
    )] == [0, 0, 0, 0]
    assert counts["G3_tdcp_probe_runs"] == 1
    assert counts["G4_BY2_C00_runs"] == g4
    report = options.continuation_root / "s/r"
    pre_execution = json.loads(
        (
            options.continuation_root / "PRE_EXECUTION_CONTROL.json"
        ).read_text(encoding="utf-8")
    )
    assert pre_execution["matlab_identity"]["pass"] is True
    assert pre_execution["matlab_identity"]["path_fallback_used"] is False
    assert pre_execution["diagnostic_reconstructed_ubx_sha256"] == hashlib.sha256(
        b"ubx"
    ).hexdigest()
    prepared_lock = json.loads(
        (
            options.continuation_root / "SOURCE_R4_G0_G1_G2_HASH_LOCK.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        prepared_lock["prepared_implementation_code_identity"]
        == pre_execution["implementation_code_identity"]
    )
    assert (report / "LC02_GINAV2021_RESUME_SEAL.json").is_file()
    manifest = json.loads(
        (report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json").read_text()
    )
    relative_paths = {row["relative_path"] for row in manifest["files"]}
    assert {
        "SOURCE_R4_G0_G1_G2_HASH_LOCK.json", "PRE_EXECUTION_CONTROL.json",
        "WSLPATH_LEDGER.csv", "WSLPATH_BUDGET.json",
    } <= relative_paths
    assert all(not path.endswith("RESUME_SEAL.json") for path in relative_paths)
    assert "s/r/LC02_GINAV2021_ARTIFACT_MANIFEST.json" not in relative_paths
    fresh_provenance = json.loads(
        (report / "GINAV_CONSOLIDATED_PROVENANCE.json").read_text(encoding="utf-8")
    )
    assert fresh_provenance["terminal_status"] != "POISONED_OLD_TERMINAL"
    assert fresh_provenance["file_access_audit"] != {"old": True}
    assert fresh_provenance["source_r4_evidence"]["source_terminal_status"] == R4_TERMINAL
    assert fresh_provenance["old_runtime_input_count"] == 0
    assert fresh_provenance["terminal_status"] == (
        SUCCESS_STATUS if g4 else TDCP_TERMINAL
    )
    assert fresh_provenance["transaction_complete"] is True
    assert fresh_provenance["formal_lc02_admission"] is bool(g4)
    assert fresh_provenance["BY2_C00_executed"] is bool(g4)
    assert fresh_provenance["BY2_C00_RESULT"] == (
        SUCCESS_STATUS if g4 else "NOT_EXECUTED"
    )
    assert fresh_provenance["actual_algorithm_blocker"] == (
        None if g4 else TDCP_TERMINAL
    )
    assert fresh_provenance["file_access_audit"]["forbidden_open_count"] == 0
    assert fresh_provenance["implementation_identity_unchanged"] is True
    assert (
        fresh_provenance["implementation_code_identity_pre_execution"]
        == fresh_provenance["implementation_code_identity_post_execution"]
    )


def test_execute_resume_rejects_dirty_or_hash_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, verified = _executor_fixture(tmp_path)
    (options.continuation_root / "dirty").write_text("x", encoding="ascii")
    with pytest.raises(TransactionError, match="dirty or already executed"):
        execute_resume_existing_r4_from_g3c(options)
    (options.continuation_root / "dirty").unlink()
    _mock_executor_preflight(monkeypatch, verified)
    calls = 0
    def verify(_path: Path) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return verified
        changed = dict(verified)
        changed["full_lock"] = {"tree_binding_sha256": "drift"}
        return changed
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4", verify)
    monkeypatch.setattr(
        transaction_module, "_execute_g3c_g4_suffix",
        lambda **kwargs: kwargs["finalize"](TDCP_TERMINAL),
    )
    with pytest.raises(TransactionError, match="changed during suffix"):
        execute_resume_existing_r4_from_g3c(options)


def test_execute_resume_rejects_pre_post_implementation_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, verified = _executor_fixture(tmp_path)
    _mock_executor_preflight(monkeypatch, verified)
    calls = 0
    def identity(_root: Path) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _fixture_code_identity()
        return {**_fixture_code_identity(), "aggregate_binding_sha256": "after"}
    monkeypatch.setattr(transaction_module, "_resume_code_identity", identity)
    monkeypatch.setattr(
        transaction_module, "_execute_g3c_g4_suffix",
        lambda **kwargs: kwargs["finalize"](TDCP_TERMINAL),
    )
    with pytest.raises(TransactionError, match="implementation identity drifted"):
        execute_resume_existing_r4_from_g3c(options)
    assert not (
        options.continuation_root / "s/r/LC02_GINAV2021_RESUME_SEAL.json"
    ).exists()


def test_execute_resume_rejects_drift_since_prepare_before_stage_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, verified = _executor_fixture(tmp_path)
    _mock_executor_preflight(monkeypatch, verified)
    monkeypatch.setattr(
        transaction_module, "_resume_code_identity",
        lambda _root: {
            **_fixture_code_identity(), "approved_tracked_diff_sha256": "changed"
        },
    )
    with pytest.raises(TransactionError, match="differs from prepared continuation"):
        execute_resume_existing_r4_from_g3c(options)
    assert not (options.continuation_root / "s").exists()
    assert not (options.continuation_root / "PRE_EXECUTION_CONTROL.json").exists()


def test_wslpath_budget_rejects_240_characters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(
        transaction_module.subprocess, "run",
        lambda *_args, **_kwargs: type(
            "Result", (), {"stdout": "X" * 240 + "\n", "returncode": 0}
        )(),
    )
    with pytest.raises(TransactionError, match="budget failure"):
        _wslpath_budget_audit((tmp_path / "input",), tmp_path / "ledger.csv")
    rows = list(csv.DictReader((tmp_path / "ledger.csv").open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["windows_path_character_count"] == "240"
    assert rows[0]["within_239_character_budget"] == "False"


def test_resume_matlab_path_inventory_covers_both_full_mirrors_and_harnesses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    longest = "src/" + "deep/" * 20 + "longest_tracked_algorithm_file.m"
    monkeypatch.setattr(
        transaction_module, "runtime_source_mirror_relative_files",
        lambda _root: ("src/main_func/exepos.m", longest),
    )
    stage = tmp_path / "r4b/s"
    paths = transaction_module._resume_matlab_path_inventory(
        continuation=tmp_path / "r4b", stage=stage,
        ginav_root=tmp_path / "ginav", matlab_executable=tmp_path / "matlab.exe",
        raw_csv=tmp_path / "gnss1-raw.csv",
        gnss_audit={
            "observation_path": tmp_path / "obs.rnx",
            "navigation_path": tmp_path / "nav.rnx",
            "ubx_path": tmp_path / "raw.ubx",
        },
        imu_csv=tmp_path / "imu.csv",
    )
    assert stage / "g3p/runtime/source_mirror" / longest in paths
    assert stage / "g4/runtime/source_mirror" / longest in paths
    for gate in ("g3p", "g4"):
        assert stage / gate / "runtime/matlab_harness/fopen.m" in paths
        assert stage / gate / "runtime/matlab_harness/run_legsa_ginav.m" in paths
    longest_inventory_item = max(paths, key=lambda path: len(str(path)))
    assert longest_inventory_item.as_posix().endswith(longest)


def test_resume_code_identity_binds_only_tracked_implementation_paths() -> None:
    first = transaction_module._resume_code_identity(REPOSITORY)
    second = transaction_module._resume_code_identity(REPOSITORY)
    assert first == second
    assert first["repository_head"]
    assert first["approved_tracked_diff_sha256"]
    assert first["aggregate_binding_sha256"]
    assert first["untracked_files_enumerated_or_hashed"] is False
    assert (
        "scripts/paper_rebuild/run_lc02_ginav2021.py"
        in first["implementation_file_sha256"]
    )
    assert first["runtime_contract_hash"] == first["implementation_file_sha256"][
        "configs/paper_rebuild/horizontal_literature/ginav2021/"
        "GINAV2021_RUNTIME_CONTRACT.yaml"
    ]


def _mock_r4c_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, Path, Path]:
    r4, r4b = tmp_path / "r4", tmp_path / "r4b"
    r4s, r4bs = r4 / "s", r4b / "s"
    for path in (
        r4s / "g0", r4s / "g2n/runtime", r4s / "g2i",
        r4bs / "g3c", r4bs / "g3p",
    ):
        path.mkdir(parents=True, exist_ok=True)
    for path in (
        r4s / "g2n/runtime/BY2_GNSS1.nav",
        r4s / "g2n/runtime/BY2_GNSS1.ubx",
        r4s / "g2i/BY2_GINAV_IMU.csv",
        r4bs / "g3c/BY2_GNSS1_NORMALIZED.rnx",
        r4bs / "g3c/BY2_GINAV_SPP_LC.ini",
        r4bs / "g3p/BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv",
    ):
        path.write_text("fixture\n", encoding="utf-8")
    matlab = tmp_path / "matlab.exe"
    matlab.write_bytes(b"matlab")
    r4_verified = {
        "source_root": r4, "source_stage": r4s,
        "full_lock": {"tree_binding_sha256": "r4-binding"},
    }
    r4b_verified = {
        "root": r4b, "stage": r4bs,
        "full_lock": {"tree_binding_sha256": "r4b-binding"},
        "section_bindings": {"g3p": "probe"},
    }
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4", lambda _p: r4_verified)
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4b", lambda _p: r4b_verified)
    monkeypatch.setattr(
        transaction_module, "_verify_resume_matlab_identity",
        lambda _m, _s: (matlab, {"executable_sha256": "matlab-hash"}),
    )
    monkeypatch.setattr(
        transaction_module, "_resume_code_identity", lambda _p: _fixture_code_identity()
    )
    return r4, r4b, matlab, r4s


@pytest.mark.parametrize(
    ("science_pass", "native_status", "g4_fails"),
    (
        (True, SUCCESS_STATUS, False),
        (True, POOR_APPLICABILITY_STATUS, False),
        (True, SUCCESS_STATUS, True),
        (False, SUCCESS_STATUS, False),
    ),
)
def test_r4c_prepare_is_lock_only_and_execute_is_g4_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    science_pass: bool, native_status: str, g4_fails: bool,
) -> None:
    r4, r4b, matlab, _r4s = _mock_r4c_sources(tmp_path, monkeypatch)
    r4c = tmp_path / "r4c"
    prepared = prepare_recover_r4b_g3_to_r4c_g4(
        RecoverR4cPrepareOptions(tmp_path, r4, r4b, r4c, matlab)
    )
    assert prepared["prepare_only_no_matlab_no_g4"] is True
    assert tuple(path.name for path in r4c.iterdir()) == ("R4C_G4_RECOVERY_LOCK.json",)
    activation = {
        "eligible_integer_epoch_count": 2,
        "eligible_integer_epoch_time_set": [
            {"gps_week": 1, "gps_sow": "1.000000000"},
            {"gps_week": 1, "gps_sow": "2.000000000"},
        ],
        "internal_spp_valid_epoch_count": 2,
        "internal_spp_invalid_epoch_count": 0,
        "internal_spp_outcome_conservation_pass": True,
        "alignment_attempt_covers_every_eligible_epoch": True,
        "alignment_activated": True,
        "spp_pair_available_epoch_count": 1,
        "official_tdcp_flag_count": 1,
        "threshold_pass_count": 1,
    }
    inventory = {
        "accepted_official_gnss_epoch_count": 2 if science_pass else 1,
        "accepted_official_gnss_epoch_time_set": (
            activation["eligible_integer_epoch_time_set"]
            if science_pass else activation["eligible_integer_epoch_time_set"][:1]
        ),
        "input_gnss_epoch_count": 2, "conservation_pass": True,
    }
    def probe_summary(
        source: Path, *, canonical_output_path: Path,
        transport_audit_path: Path,
    ) -> dict[str, object]:
        canonical_output_path.write_text("canonical\n", encoding="utf-8")
        transport = {
            "raw_sha256": transaction_module.sha256_file(source),
            "canonical_sha256": transaction_module.sha256_file(canonical_output_path),
            "canonical_data_row_count": 2,
            "pass": True,
        }
        _write_json_fixture(transport_audit_path, transport)
        return {**activation, "transport_recovery_audit": transport}
    monkeypatch.setattr(transaction_module, "_probe_summary", probe_summary)
    monkeypatch.setattr(transaction_module, "parse_rinex_epochs", lambda _p: (object(),))
    monkeypatch.setattr(
        transaction_module, "_gps_overlap_datetimes",
        lambda *_a: (dt.datetime(2026, 1, 1), dt.datetime(2026, 1, 2)),
    )
    monkeypatch.setattr(
        transaction_module, "_official_run_epoch_inventory", lambda *_a, **_k: inventory
    )
    monkeypatch.setattr(transaction_module, "_r4c_g4_path_inventory", lambda **_k: ())
    def budget(_p: object, ledger: Path) -> dict[str, object]:
        ledger.write_text("ok\n", encoding="utf-8")
        return {"pass": True, "maximum_windows_path_character_count": 100}
    monkeypatch.setattr(transaction_module, "_wslpath_budget_audit", budget)
    monkeypatch.setattr(transaction_module, "_write_cleanliness", lambda *_a, **_k: None)
    calls = 0
    def g4(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal calls
        calls += 1
        if g4_fails:
            access_ledger = kwargs["access_ledger"]
            assert isinstance(access_ledger, AccessLedger)
            access_ledger.record(
                tmp_path / "r4c-current-output",
                role="R4C_CURRENT_G4_OUTPUT",
            )
            raise TransactionError("mock G4 runtime failure")
        return (
            {"core_cleanliness": {"pass": True}},
            {
                "terminal_status": native_status,
                "formal_lc02_admission": True,
                "formal_lc02_slot": "FILLED",
            },
        )
    monkeypatch.setattr(transaction_module, "_g4_scientific_run_and_freeze", g4)
    payload = execute_recover_r4b_g3_to_r4c_g4(
        RecoverR4cExecuteOptions(
            tmp_path, tmp_path / "paths", tmp_path / "ginav", matlab,
            r4, r4b, r4c,
        )
    )
    assert calls == (1 if science_pass else 0)
    assert payload["execution_counts_this_recovery"] == {
        "G0": 0, "G1": 0, "G2": 0, "G3": 0,
        "G4": 1 if science_pass else 0,
    }
    assert payload["OFFICIAL_SAMPLE_RESULT"] == "OFFICIAL_SAMPLE_PASS"
    assert payload["BY2_C00_RESULT"] == (
        (
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"
            if g4_fails else native_status
        ) if science_pass else "NOT_EXECUTED"
    )
    if g4_fails:
        assert payload["technical_blocker"] == (
            "TransactionError: mock G4 runtime failure"
        )
    else:
        assert payload["technical_blocker"] is None
    if science_pass and not g4_fails:
        assert payload["actual_algorithm_blocker"] is None
    elif g4_fails:
        assert payload["actual_algorithm_blocker"] is None
    else:
        assert payload["actual_algorithm_blocker"] == payload["terminal_status"]
    assert payload["formal_lc02_slot"] == (
        "FILLED" if science_pass and not g4_fails else "VACANT"
    )
    assert (r4c / "s/g3p/BY2_GINAV_TDCP_ALIGNMENT_PROBE_CANONICAL.csv").is_file()
    assert (r4c / "s/g3p/R4B_G3_TRANSPORT_RECOVERY_AUDIT.json").is_file()
    assert (r4c / "s/g3p/BY2_GINAV_ALIGNMENT_ACTIVATION_SUMMARY.json").is_file()
    assert (r4c / "s/r/LC02_GINAV2021_RESUME_SEAL.json").is_file()
    manifest = json.loads(
        (r4c / "s/r/LC02_GINAV2021_ARTIFACT_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_paths = {row["relative_path"] for row in manifest["files"]}
    assert {"R4C_G4_RECOVERY_LOCK.json", "PRE_EXECUTION_CONTROL.json"} <= manifest_paths
    if science_pass:
        assert {"WSLPATH_LEDGER.csv", "WSLPATH_BUDGET.json"} <= manifest_paths
        saved = json.loads(
            (r4c / "s/r/GINAV_CONSOLIDATED_PROVENANCE.json").read_text(
                encoding="utf-8"
            )
        )
        assert saved["terminal_status"] == (
            "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"
            if g4_fails else native_status
        )
        assert saved["actual_algorithm_blocker"] is None
        assert saved["formal_lc02_slot"] == ("VACANT" if g4_fails else "FILLED")
        assert saved["trace_open_count"] == 0
        assert saved["reference_open_count"] == 0
        assert saved["gnss2_open_count"] == 0
        assert len(saved["r4c_current_opens"]) == (1 if g4_fails else 0)
        if g4_fails:
            assert saved["r4c_current_opens"][0]["role"] == "R4C_CURRENT_G4_OUTPUT"


def test_frozen_production_r4b_exact_identity_and_recovered_g3_evidence() -> None:
    root = Path(
        "/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/"
        "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/"
        "11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4b"
    )
    if not root.is_dir():
        pytest.skip("frozen production r4b is unavailable")
    verified = transaction_module._verify_frozen_r4b(root)
    assert verified["full_lock"]["tree_binding_sha256"] == (
        "4361768d23ca87252e9a240d3b487443b1d69050c40ace9de3ea145298c8583d"
    )
    activation = transaction_module._probe_summary(
        root / "s/g3p/BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv"
    )
    assert activation["eligible_integer_epoch_count"] == 116
    assert activation["transport_recovery_audit"][
        "known_unquoted_threshold_rows_recovered"
    ] == 116
    assert transaction_module._activation_terminal(activation) is None


@pytest.mark.parametrize("drift", ("code", "r4b", "source_path"))
def test_r4c_rejects_tamper_before_stage_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str,
) -> None:
    r4, r4b, matlab, _ = _mock_r4c_sources(tmp_path, monkeypatch)
    r4c = tmp_path / "r4c"
    prepare_recover_r4b_g3_to_r4c_g4(
        RecoverR4cPrepareOptions(tmp_path, r4, r4b, r4c, matlab)
    )
    if drift == "code":
        monkeypatch.setattr(
            transaction_module, "_resume_code_identity",
            lambda _p: {**_fixture_code_identity(), "aggregate_binding_sha256": "drift"},
        )
    elif drift == "r4b":
        monkeypatch.setattr(
            transaction_module, "_verify_frozen_r4b",
            lambda _p: {
                "root": r4b, "stage": r4b / "s",
                "full_lock": {"tree_binding_sha256": "drift"},
                "section_bindings": {"g3p": "probe"},
            },
        )
    else:
        alternate = tmp_path / "same-content-different-r4"
        alternate.mkdir()
        lock_path = r4c / "R4C_G4_RECOVERY_LOCK.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["source_r4_root"] = str(alternate)
        _write_json_fixture(lock_path, lock)
    with pytest.raises(TransactionError, match="authentication changed"):
        execute_recover_r4b_g3_to_r4c_g4(
            RecoverR4cExecuteOptions(
                tmp_path, tmp_path / "paths", tmp_path / "ginav", matlab,
                r4, r4b, r4c,
            )
        )
    assert not (r4c / "s").exists()


def test_r4c_parser_failure_is_sealed_technical_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    r4, r4b, matlab, _ = _mock_r4c_sources(tmp_path, monkeypatch)
    r4c = tmp_path / "r4c"
    prepare_recover_r4b_g3_to_r4c_g4(
        RecoverR4cPrepareOptions(tmp_path, r4, r4b, r4c, matlab)
    )
    monkeypatch.setattr(
        transaction_module, "_probe_summary",
        lambda *_a, **_k: (_ for _ in ()).throw(TransactionError("parser rejected")),
    )
    payload = execute_recover_r4b_g3_to_r4c_g4(
        RecoverR4cExecuteOptions(
            tmp_path, tmp_path / "paths", tmp_path / "ginav", matlab,
            r4, r4b, r4c,
        )
    )
    assert payload["execution_counts_this_recovery"]["G4"] == 0
    assert payload["actual_algorithm_blocker"] is None
    assert payload["technical_blocker"] == "TransactionError: parser rejected"
    assert (r4c / "s/r/LC02_GINAV2021_RESUME_SEAL.json").is_file()


def test_r4c_path_budget_failure_is_sealed_before_g4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    r4, r4b, matlab, _ = _mock_r4c_sources(tmp_path, monkeypatch)
    r4c = tmp_path / "r4c"
    prepare_recover_r4b_g3_to_r4c_g4(
        RecoverR4cPrepareOptions(tmp_path, r4, r4b, r4c, matlab)
    )
    times = [{"gps_week": 1, "gps_sow": "1.000000000"}]
    activation = {
        "eligible_integer_epoch_count": 1,
        "eligible_integer_epoch_time_set": times,
        "internal_spp_valid_epoch_count": 1,
        "internal_spp_invalid_epoch_count": 0,
        "internal_spp_outcome_conservation_pass": True,
        "alignment_attempt_covers_every_eligible_epoch": True,
        "alignment_activated": True,
        "spp_pair_available_epoch_count": 1,
        "official_tdcp_flag_count": 1,
        "threshold_pass_count": 1,
    }
    def probe_summary(
        source: Path, *, canonical_output_path: Path,
        transport_audit_path: Path,
    ) -> dict[str, object]:
        canonical_output_path.write_text("canonical\n", encoding="utf-8")
        transport = {
            "raw_sha256": transaction_module.sha256_file(source),
            "canonical_sha256": transaction_module.sha256_file(canonical_output_path),
            "canonical_data_row_count": 1, "pass": True,
        }
        _write_json_fixture(transport_audit_path, transport)
        return {**activation, "transport_recovery_audit": transport}
    monkeypatch.setattr(transaction_module, "_probe_summary", probe_summary)
    monkeypatch.setattr(transaction_module, "parse_rinex_epochs", lambda _p: (object(),))
    monkeypatch.setattr(
        transaction_module, "_gps_overlap_datetimes",
        lambda *_a: (dt.datetime(2026, 1, 1), dt.datetime(2026, 1, 2)),
    )
    monkeypatch.setattr(
        transaction_module, "_official_run_epoch_inventory",
        lambda *_a, **_k: {
            "accepted_official_gnss_epoch_count": 1,
            "accepted_official_gnss_epoch_time_set": times,
            "input_gnss_epoch_count": 1, "conservation_pass": True,
        },
    )
    monkeypatch.setattr(transaction_module, "_r4c_g4_path_inventory", lambda **_k: ())
    monkeypatch.setattr(
        transaction_module, "_wslpath_budget_audit",
        lambda *_a, **_k: (_ for _ in ()).throw(TransactionError("path too long")),
    )
    g4_calls = 0
    def forbidden_g4(**_kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal g4_calls
        g4_calls += 1
        raise AssertionError("G4 must not run")
    monkeypatch.setattr(transaction_module, "_g4_scientific_run_and_freeze", forbidden_g4)
    payload = execute_recover_r4b_g3_to_r4c_g4(
        RecoverR4cExecuteOptions(
            tmp_path, tmp_path / "paths", tmp_path / "ginav", matlab,
            r4, r4b, r4c,
        )
    )
    assert g4_calls == 0
    assert payload["execution_counts_this_recovery"]["G4"] == 0
    assert payload["technical_blocker"] == "TransactionError: path too long"
    assert (r4c / "s/r/LC02_GINAV2021_RESUME_SEAL.json").is_file()


def test_r4c_matlab_identity_drift_before_seal_fails_without_false_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    r4, r4b, matlab, _ = _mock_r4c_sources(tmp_path, monkeypatch)
    r4c = tmp_path / "r4c"
    prepare_recover_r4b_g3_to_r4c_g4(
        RecoverR4cPrepareOptions(tmp_path, r4, r4b, r4c, matlab)
    )
    calls = 0
    def matlab_identity(_m: Path, _s: Path) -> tuple[Path, dict[str, str]]:
        nonlocal calls
        calls += 1
        identity = {"executable_sha256": "matlab-hash"}
        if calls > 1:
            identity = {"executable_sha256": "drift"}
        return matlab, identity
    monkeypatch.setattr(transaction_module, "_verify_resume_matlab_identity", matlab_identity)
    monkeypatch.setattr(
        transaction_module, "_probe_summary",
        lambda *_a, **_k: (_ for _ in ()).throw(TransactionError("stop before G4")),
    )
    with pytest.raises(TransactionError, match="MATLAB identity drifted"):
        execute_recover_r4b_g3_to_r4c_g4(
            RecoverR4cExecuteOptions(
                tmp_path, tmp_path / "paths", tmp_path / "ginav", matlab,
                r4, r4b, r4c,
            )
        )
    assert not (r4c / "s/r/LC02_GINAV2021_RESUME_SEAL.json").exists()


def test_r4c_path_inventory_is_g4_only_and_includes_full_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        transaction_module, "runtime_source_mirror_relative_files",
        lambda _root: (Path("src/a.m"), Path("src/sub/b.m")),
    )
    root, stage, ginav = tmp_path / "r4c", tmp_path / "r4c/s", tmp_path / "ginav"
    paths = transaction_module._r4c_g4_path_inventory(
        root=root, stage=stage, ginav_root=ginav,
        matlab_executable=tmp_path / "matlab.exe", config=tmp_path / "config.ini",
        observation=tmp_path / "obs.rnx", navigation=tmp_path / "nav.nav",
        imu_csv=tmp_path / "imu.csv",
    )
    assert stage / "g4/runtime/source_mirror/src/a.m" in paths
    assert stage / "g4/runtime/source_mirror/src/sub/b.m" in paths
    assert stage / "g4/runtime/matlab_harness/run_legsa_ginav.m" in paths
    assert stage / "g4/GINAV_BY2_C00_NATIVE_SUMMARY.json" in paths
    assert all("g3p/runtime" not in str(path) for path in paths)


def _mock_r4d_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[RecoverR4dPrepareOptions, RecoverR4dExecuteOptions, dict[str, object]]:
    r4, r4b, r4c, r4d = (
        tmp_path / "r4", tmp_path / "r4b", tmp_path / "r4c", tmp_path / "r4d"
    )
    r4.mkdir()
    r4b.mkdir()
    (r4c / "s/g4").mkdir(parents=True)
    (r4c / "s/n").mkdir(parents=True)
    native = r4c / "s/g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos"
    rows = []
    for index in range(80):
        values = list(_finite_q5_row().values)
        values[1] = float(index)
        values[5] = 5 if 1 <= index <= 11 else 3
        rows.append(" ".join(format(value, ".12g") for value in values))
    native.write_text("\n".join(rows) + "\n", encoding="utf-8")
    for relative in (
        "s/g4/GINAV_BY2_C00_STATUS_STREAM.csv",
        "s/g4/GINAV_BY2_C00_FAILURE_LEDGER.csv",
        "s/g4/GINAV_BY2_C00_RUNTIME.csv",
        "s/n/GINAV_BY2_C00_STANDARD_NAV.csv",
    ):
        path = r4c / relative
        path.write_text(relative + "\n", encoding="utf-8")
    hashes = {
        relative: transaction_module.sha256_file(r4c / relative)
        for relative in (
            "s/g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos",
            "s/g4/GINAV_BY2_C00_STATUS_STREAM.csv",
            "s/g4/GINAV_BY2_C00_FAILURE_LEDGER.csv",
            "s/g4/GINAV_BY2_C00_RUNTIME.csv",
            "s/n/GINAV_BY2_C00_STANDARD_NAV.csv",
        )
    }
    monkeypatch.setattr(transaction_module, "_FROZEN_R4C_REQUIRED_HASHES", hashes)
    native_summary = transaction_module.summarize_solution(
        transaction_module.read_official_solution(native)
    )
    monkeypatch.setattr(
        transaction_module, "_FROZEN_R4C_SCIENTIFIC_DIGEST",
        native_summary["scientific_digest_sha256"],
    )
    role = "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00"
    verified_r4 = {
        "source_root": r4, "source_stage": r4 / "s",
        "full_lock": {"tree_binding_sha256": "r4-binding"},
        "provenance": {"dataset_role": role},
        "status": {"dataset_role": role},
    }
    verified_r4b = {
        "root": r4b, "stage": r4b / "s",
        "full_lock": {"tree_binding_sha256": "r4b-binding"},
    }
    verified_r4c = {
        "root": r4c, "stage": r4c / "s",
        "full_lock": {"tree_binding_sha256": "r4c-binding"},
        "provenance": {
            "raw_source_hashes": {"raw": "a" * 64},
            "provider_hashes": {"provider": "b" * 64},
            "config_hash": "c" * 64,
            "technical_blocker": "OutputContractError: old dataset_role blocker",
        },
        "status": {
            "terminal_status": "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
            "detail": "old dataset_role blocker",
            "BY2_C00_RESULT": "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE",
        },
    }
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4", lambda _p: verified_r4)
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4b", lambda _p: verified_r4b)
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4c", lambda _p: verified_r4c)
    monkeypatch.setattr(
        transaction_module, "_resume_code_identity", lambda _p: _fixture_code_identity()
    )
    for forbidden in (
        "_run_official", "_g4_scientific_run_and_freeze",
        "convert_gnss1_raw_to_rinex", "adapt_go2_imu",
    ):
        monkeypatch.setattr(
            transaction_module, forbidden,
            lambda *_a, _name=forbidden, **_k: pytest.fail(
                f"metadata-only r4d called forbidden execution: {_name}"
            ),
        )
    prepare = RecoverR4dPrepareOptions(tmp_path, r4, r4b, r4c, r4d)
    execute = RecoverR4dExecuteOptions(tmp_path, r4, r4b, r4c, r4d)
    return prepare, execute, {
        "r4": verified_r4, "r4b": verified_r4b, "r4c": verified_r4c,
        "hashes": hashes, "native": native,
    }


def test_r4d_metadata_only_closes_native_without_any_gate_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_options, execute_options, fixture = _mock_r4d_sources(
        tmp_path, monkeypatch
    )
    prepared = prepare_recover_r4c_metadata_to_r4d(prepare_options)
    assert prepared["metadata_only"] is True
    assert prepared["matlab_or_g4_execution_allowed"] is False
    payload = execute_recover_r4c_metadata_to_r4d(execute_options)
    assert payload["terminal_status"] == SUCCESS_STATUS
    assert payload["execution_counts_this_recovery"] == {
        "G0": 0, "G1": 0, "G2": 0, "G3": 0, "G4": 0,
    }
    assert payload["source_chain_gate_counts"]["source_r4c"]["G4"] == 1
    report = execute_options.r4d_root / "s/r"
    summary = json.loads(
        (execute_options.r4d_root / "s/g4/GINAV_BY2_C00_NATIVE_SUMMARY.json")
        .read_text(encoding="utf-8")
    )
    assert summary["dataset_role"] == "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00"
    assert summary["native_row_conservation"] == {
        "row_count": 80, "alignment_output_count": 1,
        "internal_spp_fed_lc_update_count": 11,
        "ins_only_propagation_count": 68, "pass": True,
    }
    assert summary["formal_lc02_admission"] is True
    assert summary["scientific_digest_sha256"] == (
        transaction_module._FROZEN_R4C_SCIENTIFIC_DIGEST
    )
    assert summary["source_artifact_hashes"] == {
        Path(relative).name: digest
        for relative, digest in fixture["hashes"].items()
    }
    assert not (execute_options.r4d_root / "s/g4/GINAV_BY2_C00_NATIVE_SOLUTION.pos").exists()
    provenance = json.loads(
        (report / "GINAV_CONSOLIDATED_PROVENANCE.json").read_text(encoding="utf-8")
    )
    assert provenance["output_only_correction"] is False
    assert provenance["trace_used_online"] is False
    assert provenance["trace_open_count"] == 0
    assert provenance["reference_open_count"] == 0
    assert provenance["rmse_used"] is False
    status = json.loads(
        (report / "LC02_GINAV2021_TRANSACTION_STATUS.json").read_text(
            encoding="utf-8"
        )
    )
    resume_summary = json.loads(
        (report / "LC02_GINAV2021_RESUME_SUFFIX_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    required_terminal = {
        "OFFICIAL_SAMPLE_RESULT": "OFFICIAL_SAMPLE_PASS",
        "BY2_C00_RESULT": SUCCESS_STATUS,
        "reproduction_level": (
            "EXACT_R4_R4B_R4C_AUTHENTICATED_METADATA_ONLY_TERMINAL_RECOVERY"
        ),
        "actual_algorithm_blocker": None,
        "technical_blocker": None,
    }
    for document in (status, resume_summary, provenance):
        assert {key: document[key] for key in required_terminal} == required_terminal
        assert document["source_r4c_terminal_evidence"]["detail"] == (
            "old dataset_role blocker"
        )
    manifest = json.loads(
        (report / "LC02_GINAV2021_ARTIFACT_MANIFEST.json").read_text(encoding="utf-8")
    )
    manifest_paths = {row["relative_path"] for row in manifest["files"]}
    assert "R4D_METADATA_RECOVERY_LOCK.json" in manifest_paths
    assert "s/r/LC02_GINAV2021_RESUME_SEAL.json" not in manifest_paths
    seal = json.loads(
        (report / "LC02_GINAV2021_RESUME_SEAL.json").read_text(encoding="utf-8")
    )
    assert seal["r4_unchanged"] and seal["r4b_unchanged"] and seal["r4c_unchanged"]
    assert seal["seal_written_last"] is True


def test_r4d_rejects_dataset_role_conflict_and_source_tamper_before_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_options, execute_options, fixture = _mock_r4d_sources(
        tmp_path, monkeypatch
    )
    fixture["r4"]["status"]["dataset_role"] = "CONFLICT"
    with pytest.raises(TransactionError, match="dataset_role"):
        prepare_recover_r4c_metadata_to_r4d(prepare_options)
    fixture["r4"]["status"]["dataset_role"] = (
        "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00"
    )
    prepare_recover_r4c_metadata_to_r4d(prepare_options)
    fixture["r4c"]["full_lock"] = {"tree_binding_sha256": "tampered"}
    with pytest.raises(TransactionError, match="authentication changed"):
        execute_recover_r4c_metadata_to_r4d(execute_options)
    assert not (execute_options.r4d_root / "s").exists()


@pytest.mark.parametrize("failure", ("analyzer", "closure"))
def test_r4d_poststage_scientific_failure_is_sealed_technical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    prepare_options, execute_options, _fixture = _mock_r4d_sources(
        tmp_path, monkeypatch
    )
    prepare_recover_r4c_metadata_to_r4d(prepare_options)
    original = transaction_module.analyze_frozen_native_solution_metadata_only
    if failure == "analyzer":
        def fail_analyzer(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise OutputContractError("mock analyzer failure")
        monkeypatch.setattr(
            transaction_module,
            "analyze_frozen_native_solution_metadata_only",
            fail_analyzer,
        )
        expected = "OutputContractError: mock analyzer failure"
    else:
        def fail_closure(*args: object, **kwargs: object) -> dict[str, object]:
            result = original(*args, **kwargs)
            return {**result, "row_count": 79}
        monkeypatch.setattr(
            transaction_module,
            "analyze_frozen_native_solution_metadata_only",
            fail_closure,
        )
        expected = "TransactionError: r4d native scientific closure mismatch"
    payload = execute_recover_r4c_metadata_to_r4d(execute_options)
    assert payload["terminal_status"] == (
        "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"
    )
    assert payload["BY2_C00_RESULT"] == "NOT_REEVALUATED"
    assert payload["technical_blocker"] == expected
    assert payload["execution_counts_this_recovery"] == {
        "G0": 0, "G1": 0, "G2": 0, "G3": 0, "G4": 0,
    }
    report = execute_options.r4d_root / "s/r"
    assert (report / "LC02_GINAV2021_RESUME_SEAL.json").is_file()
    provenance = json.loads(
        (report / "GINAV_CONSOLIDATED_PROVENANCE.json").read_text(encoding="utf-8")
    )
    for document in (payload, provenance):
        assert document["OFFICIAL_SAMPLE_RESULT"] == "OFFICIAL_SAMPLE_PASS"
        assert document["BY2_C00_RESULT"] == "NOT_REEVALUATED"
        assert document["actual_algorithm_blocker"] is None
        assert document["technical_blocker"] == expected


def test_r4d_preseal_identity_drift_writes_no_false_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_options, execute_options, fixture = _mock_r4d_sources(
        tmp_path, monkeypatch
    )
    prepare_recover_r4c_metadata_to_r4d(prepare_options)
    calls = 0
    def verify_r4c(_path: Path) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return fixture["r4c"]
        return {
            **fixture["r4c"],
            "full_lock": {"tree_binding_sha256": "identity-drift"},
        }
    monkeypatch.setattr(transaction_module, "_verify_frozen_r4c", verify_r4c)
    with pytest.raises(TransactionError, match="changed during r4d"):
        execute_recover_r4c_metadata_to_r4d(execute_options)
    assert not (
        execute_options.r4d_root / "s/r/LC02_GINAV2021_RESUME_SEAL.json"
    ).exists()


def test_frozen_production_r4c_exact_identity_for_r4d_metadata_recovery() -> None:
    root = Path(
        "/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/"
        "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/"
        "11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4c"
    )
    if not root.is_dir():
        pytest.skip("frozen production r4c is unavailable")
    verified = transaction_module._verify_frozen_r4c(root)
    assert verified["full_lock"]["tree_binding_sha256"] == (
        "d84114d1fe14a95c7b4b6d48b2260792dc649d6b01fe61687bc45008e0642afd"
    )
    assert verified["manifest"]["file_count"] == 383
    assert verified["status"]["execution_counts_this_recovery"]["G4"] == 1
    assert verified["provenance"].get("dataset_role") is None


def test_execute_resume_rejects_matlab_hash_before_stage_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, verified = _executor_fixture(tmp_path)
    _mock_executor_preflight(monkeypatch, verified)
    options.matlab_executable.write_bytes(b"one-byte-drift")
    with pytest.raises(TransactionError, match="MATLAB executable hash differs"):
        execute_resume_existing_r4_from_g3c(options)
    assert not (options.continuation_root / "s").exists()


def test_execute_resume_rejects_matlab_path_not_bound_by_prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, verified = _executor_fixture(tmp_path)
    _mock_executor_preflight(monkeypatch, verified)
    lock = options.continuation_root / "SOURCE_R4_G0_G1_G2_HASH_LOCK.json"
    prepared = json.loads(lock.read_text(encoding="utf-8"))
    prepared["prepared_matlab_identity"]["user_specified_absolute_path"] = str(
        tmp_path / "different-matlab.exe"
    )
    _write_json_fixture(lock, prepared)
    with pytest.raises(TransactionError, match="differs from prepared"):
        execute_resume_existing_r4_from_g3c(options)
    assert not (options.continuation_root / "s").exists()


def test_resume_matlab_identity_rejects_relative_path_without_path_fallback(
    tmp_path: Path,
) -> None:
    with pytest.raises(TransactionError, match="explicitly specified absolute path"):
        transaction_module._verify_resume_matlab_identity(
            Path("matlab"), tmp_path / "s"
        )


def test_nav_pvt_diagnostic_fields_are_complete_and_consumed_bits_are_explicit() -> None:
    payload = bytearray(92)
    struct.pack_into("<I", payload, 0, 461176002)
    struct.pack_into("<HBBBBBB", payload, 4, 2026, 8, 26, 12, 34, 56, 0x0F)
    struct.pack_into("<I", payload, 12, 987654)
    struct.pack_into("<i", payload, 16, 123456789)
    struct.pack_into("<BBBB", payload, 20, 3, 0xE3, 0xE0, 17)
    struct.pack_into("<iiii", payload, 24, 123456789, -234567890, 12345, 11000)
    struct.pack_into("<II", payload, 40, 1200, 2300)
    struct.pack_into("<iiiii", payload, 48, 1000, -2000, 3000, 4000, 123456)
    struct.pack_into("<II", payload, 68, 500, 23456)
    struct.pack_into("<H", payload, 76, 145)
    payload[78] = 0x0B
    payload[79] = 0xA5
    struct.pack_into("<i", payload, 80, -345678)
    struct.pack_into("<hH", payload, 84, -123, 45)
    payload[88:92] = b"\x01\x02\x03\x04"
    fields = transaction_module._nav_pvt_diagnostic_fields({
        "payload": bytes(payload), "message_sequence": 99, "source_csv_row": 42,
        "source_timestamp": "stamp", "source_stamp_seconds": "1",
        "source_stamp_nanoseconds": "2",
    }, gps_week=2434)
    required = {
        "candidate_message_sequence", "source_csv_row", "source_timestamp",
        "gps_week_from_associated_RAWX", "iTOW_milliseconds", "UTC",
        "year_raw", "month_raw", "day_raw", "hour_raw", "minute_raw",
        "second_raw", "nano_raw", "valid_raw", "tAcc_ns", "reserved1_hex",
        "reserved2_hex", "validDate", "validTime",
        "fullyResolved", "flags", "flags2", "flags3", "fixType", "gnssFixOK",
        "diffSoln", "carrSoln", "pDOP", "longitude_deg", "latitude_deg",
        "height_ellipsoid_m", "height_msl_m", "horizontal_accuracy_m",
        "vertical_accuracy_m", "velocity_north_mps", "velocity_east_mps",
        "velocity_down_mps", "ground_speed_mps", "speed_accuracy_mps",
        "heading_motion_deg", "heading_accuracy_deg", "heading_vehicle_deg",
    }
    assert required <= fields.keys()
    assert fields["validDate"] and fields["validTime"] and fields["fullyResolved"]
    assert fields["gnssFixOK"] and fields["diffSoln"] and fields["carrSoln"] == 3
    assert fields["tAcc_ns"] == 987654
    assert fields["reserved1_hex"] == "a5"
    assert fields["reserved2_hex"] == "01020304"


def test_resume_diagnostic_locks_old_key_truth_full_inventory_and_filenames() -> None:
    source = (
        REPOSITORY
        / "src/legsa_gins/paper_rebuild/horizontal_literature/ginav2021/transaction.py"
    ).read_text(encoding="utf-8")
    assert "floor(rcvTow_seconds + 0.5) * 1000" in source
    assert '"unique": 1508' in source
    assert '"semantic_duplicate": 0' in source
    assert '"conflicting": 0' in source
    assert '"missing": 1' in source
    assert "old_exact_target_iTOW_milliseconds\"] != 461176000" in source
    assert "old_exact_candidate_count\"] != 0" in source
    assert "for index, (rawx_item, association_row, old_row) in enumerate(" in source
    assert "RAWX_NAVPVT_ASSOCIATION_SEMANTIC_DIAGNOSIS.json" in source
    assert "RAWX_NAVPVT_ASSOCIATION_CANDIDATES.csv" in source
    assert "RAWX_NAV_PVT_ASSOCIATION_DIAGNOSTIC.json" not in source
    assert "RAWX_1508_NAV_PVT_CANDIDATES.csv" not in source


def _official_root() -> Path:
    value = os.environ.get("LEGSAGINS_GINAV_ROOT")
    if not value:
        pytest.skip("LEGSAGINS_GINAV_ROOT is required for pinned-config tests")
    return Path(value).expanduser().resolve(strict=True)


def _provenance() -> dict[str, object]:
    return {
        "schema_version": "ginav2021.consolidated_provenance.v1",
        "data_mode": "real_by2_raw",
        "dataset_role": "REAL_BY2_NATIVE_INPUT_ADAPTER_AND_C00",
        "raw_source_hashes": {"raw": "a" * 64},
        "provider_hashes": {"provider": "b" * 64},
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
        "code_commit": "c" * 40,
        "config_hash": "d" * 64,
        "gate_execution_counts": {
            "G0_matlab_candidate_attempts": 1,
            "G1_official_sample_runs": 2,
            "G2_gnss_adapter_runs": 1,
            "G2_imu_adapter_runs": 1,
            "G3_tdcp_probe_runs": 1,
            "G4_BY2_C00_runs": 0,
        },
    }


def _clean_audit() -> dict[str, object]:
    return {
        "pass": True,
        "trace_open_count": 0,
        "reference_open_count": 0,
        "gnss2_open_count": 0,
        "other_method_open_count": 0,
        "forbidden_open_count": 0,
        "unauthorized_runtime_read_count": 0,
        "records": [],
    }


def _publication_roots(tmp_path: Path) -> dict[str, Path]:
    roots = {
        name: tmp_path / name
        for name in ("scratch", "clean", "raw", "code", "paper", "legacy")
    }
    for root in roots.values():
        root.mkdir()
    stage = _create_stage_layout(roots["scratch"])
    parent = (
        roots["clean"] / "stages"
        / "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
    )
    parent.mkdir(parents=True)
    roots["stage"] = stage
    roots["destination"] = parent / STAGE_NAME
    return roots


def _write_minimum_publication_evidence(
    stage: Path, *, terminal: str = TDCP_TERMINAL
) -> dict[str, object]:
    status = {
        "terminal_status": terminal,
        "scientific_terminal_status": terminal,
        "artifact_publication": "PENDING",
        "transaction_complete": False,
        "scratch_stage_root": str(stage),
    }
    (stage / FINAL_STATUS_RELATIVE).write_text(
        json.dumps(status) + "\n", encoding="utf-8"
    )
    (stage / "11_REPORT/GINAV_FORBIDDEN_INPUT_AUDIT.json").write_text(
        json.dumps(_clean_audit()) + "\n", encoding="utf-8"
    )
    (stage / "11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json").write_text(
        json.dumps(_provenance()) + "\n", encoding="utf-8"
    )
    return status


def test_by2_config_allowlist_lever_and_allan_psd(tmp_path: Path) -> None:
    data = tmp_path / "runtime"
    data.mkdir()
    destination = tmp_path / "BY2.ini"
    contract = derive_by2_config(
        _official_root() / OFFICIAL_CONFIG_RELATIVE,
        destination,
        data_directory=data,
        site_name="by2_gnss1",
        start_time_gpst=dt.datetime(2022, 1, 1, 0, 0, 0),
        end_time_gpst=dt.datetime(2022, 1, 1, 0, 2, 0),
        navsys="G",
        nfreq=1,
        project_repository_root=REPOSITORY,
    )
    assert set(contract["actual_changed_fields"]).issubset(
        set(contract["allowed_change_fields"])
    )
    assert contract["gnss_mode"] == 1 and contract["ins_mode"] == 1
    assert contract["official_robust_path_unchanged"] is True
    assert contract["initial_state_uncertainties_unchanged"] is True
    assert contract["imu_data_format"] == 2
    assert lever_frd_to_rfu(LEVER_FRD_M) == LEVER_RFU_M
    assert contract["lever"]["quality"] == "ROUGH_ENGINEERING_LEVER"
    assert contract["lever"]["trace_tuned"] is False
    allan = allan_psd_mapping(REPOSITORY)
    assert allan["mapping_rule"] == "square_each_continuous_ASD_exactly_once"
    assert allan["sqrt_dt_preprocessing"] is False
    assert allan["user_thesis_opened_by_this_route"] is False
    assert len(allan["project_parameter_source_hashes_verified"]) == 2


def _finite_q5_row() -> OfficialSolutionRow:
    values = [0.0] * len(OFFICIAL_POS_COLUMNS)
    values[0] = 2200
    values[1] = 100.0
    values[2:5] = [4_000_000.0, 1_000_000.0, 4_800_000.0]
    values[5] = 5
    values[6] = 8
    values[7:13] = [1.0] * 6
    values[15:18] = [1.0, 2.0, 3.0]
    values[18:24] = [0.1] * 6
    values[24:27] = [1.0, 2.0, 3.0]
    values[27:33] = [0.2] * 6
    return OfficialSolutionRow(tuple(values))


def test_standard_output_schema_is_source_and_frame_derived() -> None:
    row = standard_nav_row(_finite_q5_row())
    assert tuple(row) == STANDARD_NAV_COLUMNS
    assert row["status_name"] == "SPP"
    assert row["lc_update"] is True
    assert row["velocity_north_ned_mps"] == row["velocity_north_mps"]
    assert row["velocity_down_ned_mps"] == -row["velocity_up_mps"]


def test_formal_admission_routes_no_q5_all_nonfinite_and_finite_q5() -> None:
    no_q5 = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 0,
            "finite_state_rate": 1.0,
            "finite_covariance_rate": 1.0,
            "finite_lc_update_count": 0,
        },
        process_returncode=0,
    )
    assert no_q5["terminal_status"] == (
        "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP"
    )

    all_nonfinite = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 2,
            "finite_state_rate": 0.0,
            "finite_covariance_rate": 0.0,
            "finite_lc_update_count": 0,
        },
        process_returncode=0,
    )
    assert all_nonfinite["terminal_status"] == POOR_APPLICABILITY_STATUS
    assert all_nonfinite["formal_lc02_admission"] is False
    assert all_nonfinite["BY2_C00_complete"] is True

    admitted = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 2,
            "finite_state_rate": 1.0,
            "finite_covariance_rate": 1.0,
            "finite_lc_update_count": 1,
        },
        process_returncode=0,
    )
    assert admitted["terminal_status"] == SUCCESS_STATUS
    assert admitted["formal_lc02_admission"] is True

    partial = formal_admission(
        {
            "row_count": 10,
            "internal_spp_fed_lc_update_count": 2,
            "finite_state_rate": 0.9,
            "finite_covariance_rate": 1.0,
            "finite_lc_update_count": 1,
        },
        process_returncode=0,
    )
    assert partial["terminal_status"] == POOR_APPLICABILITY_STATUS
    assert partial["formal_lc02_admission"] is True


def test_formal_admission_rejects_nonzero_process_returncode() -> None:
    with pytest.raises(OutputContractError, match="zero MATLAB process"):
        formal_admission(
            {
                "row_count": 1,
                "internal_spp_fed_lc_update_count": 1,
                "finite_state_rate": 1.0,
                "finite_covariance_rate": 1.0,
                "finite_lc_update_count": 1,
            },
            process_returncode=1,
        )


def test_native_summary_and_freeze_carry_required_provenance(tmp_path: Path) -> None:
    native = tmp_path / "source.pos"
    native.write_text(
        " ".join(format(value, ".12g") for value in _finite_q5_row().values) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "native"
    normalized = tmp_path / "normalized"
    summary = freeze_native_solution(
        native,
        output,
        matlab_result={
            "returncode": 0,
            "runtime_seconds": 1.0,
            "stdout": "",
            "stderr": "",
        },
        input_counts={"input_gnss_epoch_count": 1},
        provenance=_provenance(),
        normalization_root=normalized,
    )
    freeze = json.loads(
        (output / "GINAV_BY2_C00_NATIVE_FREEZE.json").read_text(encoding="utf-8")
    )
    for payload in (summary, freeze):
        assert payload["data_mode"] == "real_by2_raw"
        assert payload["synthetic_data_used"] is False
        assert payload["trace_used_online"] is False
        assert payload["old_runtime_input_count"] == 0
        assert payload["code_commit"] == "c" * 40
        assert payload["config_hash"] == "d" * 64


def test_native_provenance_is_validated_before_any_freeze_output(tmp_path: Path) -> None:
    native = tmp_path / "source.pos"
    native.write_text(
        " ".join(format(value, ".12g") for value in _finite_q5_row().values) + "\n",
        encoding="utf-8",
    )
    provenance = _provenance()
    del provenance["dataset_role"]
    output, normalized = tmp_path / "native", tmp_path / "normalized"
    with pytest.raises(OutputContractError, match="dataset_role"):
        freeze_native_solution(
            native, output,
            matlab_result={"returncode": 0, "stdout": "", "stderr": ""},
            input_counts={}, provenance=provenance,
            normalization_root=normalized,
        )
    assert not output.exists()
    assert not normalized.exists()


def test_zero_native_output_after_g3_is_fail_closed() -> None:
    assert _zero_native_output_terminal() == (
        "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"
    )


def test_activation_terminal_routing_is_source_literal_and_fail_closed() -> None:
    base = {
        "internal_spp_valid_epoch_count": 2,
        "spp_pair_available_epoch_count": 1,
        "official_tdcp_flag_count": 1,
        "threshold_pass_count": 1,
        "alignment_activated": True,
    }
    assert _activation_terminal(base) is None
    assert _activation_terminal(
        {**base, "spp_pair_available_epoch_count": 0}
    )[0] == "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP"
    assert _activation_terminal(
        {**base, "threshold_pass_count": 0}
    )[0] == "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET"
    assert _activation_terminal(
        {**base, "alignment_activated": False}
    )[0] == "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE"


def test_forbidden_path_audit_rejects_other_methods_and_reference(tmp_path: Path) -> None:
    ledger = AccessLedger()
    for name in ("GNSS2.csv", "trace.csv", "Canonical-541.csv", "LC01.pos"):
        with pytest.raises(ForbiddenInputError):
            ledger.record(tmp_path / name, role="candidate_input")
    assert not ledger.records


def test_compact_publication_is_exact_self_contained_and_path_aliased(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    stage = roots["stage"]
    status = _write_minimum_publication_evidence(stage)
    runtime = stage / "01_OFFICIAL_SAMPLE_REGRESSION/pristine_run_1/sample_data"
    runtime.mkdir(parents=True)
    (runtime / "sample.19o").write_text("runtime", encoding="ascii")

    selected = compact_artifact_paths(stage, terminal_status=TDCP_TERMINAL)
    assert {path.relative_to(stage) for path in selected} == {
        FINAL_STATUS_RELATIVE,
        Path("11_REPORT/GINAV_FORBIDDEN_INPUT_AUDIT.json"),
        Path("11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json"),
    }
    report = publish_compact_stage(
        stage,
        roots["destination"],
        terminal_status=TDCP_TERMINAL,
        final_status_payload=status,
        expected_destination_stage_root=roots["destination"],
        clean_root=roots["clean"],
        protected_roots=(
            roots["code"], roots["clean"], roots["raw"], roots["paper"],
            roots["legacy"],
        ),
        path_aliases={tmp_path: "<TEST_ROOT>"},
    )
    assert report["pass"] is True
    destination = roots["destination"]
    assert not (destination / "01_OFFICIAL_SAMPLE_REGRESSION/pristine_run_1").exists()
    published_status = json.loads(
        (destination / FINAL_STATUS_RELATIVE).read_text(encoding="utf-8")
    )
    assert published_status["artifact_publication"] == "COMPLETE"
    assert published_status["transaction_complete"] is True
    published_provenance = json.loads(
        (destination / "11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json")
        .read_text(encoding="utf-8")
    )
    assert published_provenance["artifact_publication"] == "COMPLETE"
    assert published_provenance["transaction_complete"] is True
    parity = json.loads((destination / PARITY_RELATIVE).read_text(encoding="utf-8"))
    paths = {row["relative_path"] for row in parity["files"]}
    assert FINAL_STATUS_RELATIVE.as_posix() in paths
    assert PARITY_RELATIVE.as_posix() not in paths
    for row in parity["files"]:
        content = (destination / row["relative_path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == row["prepared_destination_sha256"]
    published_text = "".join(
        path.read_text(encoding="utf-8")
        for path in destination.rglob("*") if path.is_file()
    )
    assert str(tmp_path) not in published_text


def test_attempt_specific_publication_preserves_legacy_partial_sentinel(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    stage = roots["stage"]
    status = _write_minimum_publication_evidence(stage)
    legacy_partial = roots["destination"].with_name(STAGE_NAME + ".partial")
    legacy_partial.mkdir()
    sentinel = legacy_partial / "ATTEMPT1_SENTINEL.bin"
    sentinel.write_bytes(b"immutable-attempt-1-partial\x00\xff")
    sentinel_before = hashlib.sha256(sentinel.read_bytes()).hexdigest()
    temporary, identity = _publication_temporary_root(
        roots["destination"], stage
    )

    assert temporary != legacy_partial
    assert temporary.parent == roots["destination"].parent
    assert temporary.name.endswith(identity[:16])
    report = publish_compact_stage(
        stage,
        roots["destination"],
        terminal_status=TDCP_TERMINAL,
        final_status_payload=status,
        expected_destination_stage_root=roots["destination"],
        clean_root=roots["clean"],
        protected_roots=(
            roots["code"], roots["clean"], roots["raw"], roots["paper"],
            roots["legacy"],
        ),
        path_aliases={tmp_path: "<TEST_ROOT>"},
    )

    assert report["pass"] is True
    assert report["publication_temporary_identity_sha256"] == identity
    assert roots["destination"].is_dir()
    assert not temporary.exists()
    assert sentinel.read_bytes() == b"immutable-attempt-1-partial\x00\xff"
    assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == sentinel_before


def test_publication_rejects_unallowlisted_evidence_and_source_symlinks(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    stage = roots["stage"]
    _write_minimum_publication_evidence(stage)
    unknown = stage / "11_REPORT/REPORT.json"
    unknown.write_text("{}\n", encoding="utf-8")
    with pytest.raises(PublicationError, match="not allowlisted"):
        compact_artifact_paths(stage, terminal_status=TDCP_TERMINAL)
    unknown.unlink()

    target = tmp_path / "outside.json"
    target.write_text("{}\n", encoding="utf-8")
    link = stage / "00_SOURCE_AND_ENVIRONMENT/GINAV_SOURCE_LOCK.json"
    link.symlink_to(target)
    with pytest.raises(PublicationError, match="symlink"):
        compact_artifact_paths(stage, terminal_status=TDCP_TERMINAL)


def test_publication_rejects_dangling_destination_symlink(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    stage = roots["stage"]
    status = _write_minimum_publication_evidence(stage)
    protected_leaf = roots["destination"]
    protected_leaf.symlink_to(tmp_path / "missing-target")
    with pytest.raises(PublicationError, match="destination|symlink|partial"):
        publish_compact_stage(
            stage,
            roots["destination"],
            terminal_status=TDCP_TERMINAL,
            final_status_payload=status,
            expected_destination_stage_root=roots["destination"],
            clean_root=roots["clean"],
            protected_roots=(
                roots["code"], roots["clean"], roots["raw"], roots["paper"],
                roots["legacy"],
            ),
            path_aliases={tmp_path: "<TEST_ROOT>"},
        )


def test_destination_identity_and_protected_source_are_fail_closed(
    tmp_path: Path,
) -> None:
    roots = _publication_roots(tmp_path)
    wrong = roots["destination"].with_name("wrong")
    with pytest.raises(PublicationError, match="exact authorized stage"):
        validate_exact_destination(
            wrong,
            expected_destination=roots["destination"],
            clean_root=roots["clean"],
            other_protected_roots=(
                roots["code"], roots["raw"], roots["paper"], roots["legacy"]
            ),
        )

    protected_stage = _create_stage_layout(roots["code"])
    status = _write_minimum_publication_evidence(protected_stage)
    with pytest.raises(PublicationError, match="inside protected root"):
        publish_compact_stage(
            protected_stage,
            roots["destination"],
            terminal_status=TDCP_TERMINAL,
            final_status_payload=status,
            expected_destination_stage_root=roots["destination"],
            clean_root=roots["clean"],
            protected_roots=(
                roots["code"], roots["clean"], roots["raw"], roots["paper"],
                roots["legacy"],
            ),
            path_aliases={tmp_path: "<TEST_ROOT>"},
        )

    raw_stage = _create_stage_layout(roots["raw"])
    raw_status = _write_minimum_publication_evidence(raw_stage)
    with pytest.raises(PublicationError, match="inside protected root"):
        publish_compact_stage(
            raw_stage,
            roots["destination"],
            terminal_status=TDCP_TERMINAL,
            final_status_payload=raw_status,
            expected_destination_stage_root=roots["destination"],
            clean_root=roots["clean"],
            protected_roots=(
                roots["code"], roots["clean"], roots["raw"], roots["paper"],
                roots["legacy"],
            ),
            path_aliases={tmp_path: "<TEST_ROOT>"},
        )


def test_scratch_rejects_protected_root_and_symlinked_ancestor(
    tmp_path: Path,
) -> None:
    protected = tmp_path / "code"
    protected.mkdir()
    with pytest.raises(TransactionError, match="inside protected root"):
        _make_scratch_root(
            protected / "runtime", protected_roots=(protected,)
        )

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    with pytest.raises(TransactionError, match="inside protected root"):
        _make_scratch_root(
            raw_root / "runtime", protected_roots=(protected, raw_root)
        )

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(TransactionError, match="symlinked path component"):
        _make_scratch_root(
            linked_parent / "runtime", protected_roots=(protected,)
        )


def test_destination_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    clean = tmp_path / "real-clean"
    clean.mkdir()
    linked_clean = tmp_path / "linked-clean"
    linked_clean.symlink_to(clean, target_is_directory=True)
    destination = (
        linked_clean / "stages"
        / "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON" / STAGE_NAME
    )
    with pytest.raises(PublicationError, match="symlinked path component"):
        validate_exact_destination(
            destination,
            expected_destination=destination,
            clean_root=linked_clean,
            other_protected_roots=(),
        )


def test_guarded_atomic_fallback_never_overwrites_existing_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "prepared"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "new").write_text("new", encoding="ascii")
    (destination / "old").write_text("old", encoding="ascii")
    with pytest.raises(PublicationError, match="existing destination"):
        _guarded_atomic_rename(source, destination)
    assert (source / "new").read_text(encoding="ascii") == "new"
    assert (destination / "old").read_text(encoding="ascii") == "old"
    assert not (tmp_path / ".destination.publish.lock").exists()


def test_publication_aliases_drive_and_wsl_path_forms(tmp_path: Path) -> None:
    mounted = Path("/") / "mnt" / "q" / "evidence"
    assert _replace_aliases(
        "Q:\\evidence\\status.json", {mounted: "<STAGE_ROOT>"}
    ) == "<STAGE_ROOT>\\status.json"
    linux_path = tmp_path / "evidence"
    windows_unc = (
        "\\\\wsl.localhost\\TestDistribution"
        + str(linux_path).replace("/", "\\")
        + "\\status.json"
    )
    assert _replace_aliases(
        windows_unc, {linux_path: "<SCRATCH_ROOT>"}
    ) == "<SCRATCH_ROOT>\\status.json"


def test_json_publication_recursively_sanitizes_decoded_string_values(
    tmp_path: Path,
) -> None:
    linux_root = tmp_path / "scratch"
    mounted_root = Path("/mnt/q/evidence")
    windows_unc = (
        "\\\\wsl.localhost\\TestDistribution"
        + str(linux_root).replace("/", "\\")
    )
    payload = {
        "candidate": {
            "full_matlab_error": {
                "command": [
                    "matlab.exe",
                    "try,addpath('" + windows_unc
                    + "\\00_SOURCE_AND_ENVIRONMENT\\harness');exit(0);",
                ],
                "nested": [
                    {"drive_path": "Q:\\evidence\\status.json"},
                    {"linux_path": str(linux_root / "status.json")},
                ],
                "key_paths": {
                    str(linux_root / "linux-key"): "linux",
                    "Q:\\evidence\\drive-key": "drive",
                },
            }
        }
    }
    aliases = {
        linux_root: "<SCRATCH_ROOT>",
        mounted_root: "<STAGE_ROOT>",
    }
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    source_bytes, changed = _sanitized_bytes(source, aliases)
    generated_bytes = _json_bytes(payload, aliases)
    assert changed is True
    assert source_bytes == generated_bytes
    decoded = json.loads(source_bytes.decode("utf-8"))
    command = decoded["candidate"]["full_matlab_error"]["command"][1]
    assert (
        "<SCRATCH_ROOT>\\00_SOURCE_AND_ENVIRONMENT\\harness" in command
    )
    assert decoded["candidate"]["full_matlab_error"]["nested"] == [
        {"drive_path": "<STAGE_ROOT>\\status.json"},
        {"linux_path": "<SCRATCH_ROOT>/status.json"},
    ]
    assert decoded["candidate"]["full_matlab_error"]["key_paths"] == {
        "<SCRATCH_ROOT>/linux-key": "linux",
        "<STAGE_ROOT>\\drive-key": "drive",
    }
    assert "wsl.localhost" not in source_bytes.decode("utf-8").casefold()

    unaliased = tmp_path / "unaliased.json"
    unaliased.write_text(
        json.dumps({"nested": [{"path": "/home/not-authorized/input"}]}),
        encoding="utf-8",
    )
    with pytest.raises(PublicationError, match="unaliased machine-local path"):
        _sanitized_bytes(unaliased, aliases)
    with pytest.raises(PublicationError, match="unaliased machine-local path"):
        _json_bytes({"path": "/home/not-authorized/input"}, aliases)

    unaliased_key = tmp_path / "unaliased-key.json"
    unaliased_key.write_text(
        json.dumps({"nested": [{"/home/not-authorized/key": "value"}]}),
        encoding="utf-8",
    )
    with pytest.raises(PublicationError, match="unaliased machine-local path"):
        _sanitized_bytes(unaliased_key, aliases)
    with pytest.raises(PublicationError, match="unaliased machine-local path"):
        _json_bytes({"/home/not-authorized/key": "value"}, aliases)

    collision = {
        str(linux_root / "same-key"): "source path",
        "<SCRATCH_ROOT>/same-key": "existing alias",
    }
    collision_source = tmp_path / "collision.json"
    collision_source.write_text(json.dumps(collision), encoding="utf-8")
    with pytest.raises(PublicationError, match="key collision"):
        _sanitized_bytes(collision_source, aliases)
    with pytest.raises(PublicationError, match="key collision"):
        _json_bytes(collision, aliases)


def test_cleanliness_aggregate_recovers_failed_candidate_proof(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    stage = _create_stage_layout(scratch)
    candidate = stage / "00_SOURCE_AND_ENVIRONMENT/matlab_probe_runtime_candidate_1"
    candidate.mkdir()
    proof = {
        "schema_version": "ginav2021.core_cleanliness_before_after.v1",
        "run_id": "G0_MATLAB_ENVIRONMENT_candidate_1",
        "pass": True,
    }
    (candidate / "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json").write_text(
        json.dumps(proof) + "\n", encoding="utf-8"
    )
    runs: list[dict[str, object]] = []
    aggregate_path = _write_cleanliness(stage, runs)
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert runs == [proof]
    assert aggregate["run_count"] == 1
    assert aggregate["runs"][0]["run_id"].endswith("candidate_1")


def test_publication_failure_preserves_allowed_terminal_and_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = _publication_roots(tmp_path)

    def fail_rename(source: Path, destination: Path) -> None:
        raise PublicationError("injected guarded publication failure")

    monkeypatch.setattr(
        "legsa_gins.paper_rebuild.horizontal_literature.ginav2021.publication."
        "_atomic_rename_noreplace",
        fail_rename,
    )
    payload = _finalize_terminal(
        SUCCESS_STATUS,
        stage=roots["stage"],
        access_audit=_clean_audit(),
        provenance=_provenance(),
        cleanliness_runs=(),
        publish=True,
        destination=roots["destination"],
        clean_root=roots["clean"],
        protected_roots=(
            roots["code"], roots["clean"], roots["raw"], roots["paper"],
            roots["legacy"],
        ),
        path_aliases={tmp_path: "<TEST_ROOT>"},
        detail="bounded test terminal",
        extra={"formal_lc02_admission": True},
    )
    assert payload["terminal_status"] == SUCCESS_STATUS
    assert payload["scientific_terminal_status"] == SUCCESS_STATUS
    assert payload["artifact_publication"] == "FAILED"
    assert payload["transaction_complete"] is False
    assert payload["scientific_formal_lc02_admission"] is True
    assert payload["formal_lc02_admission"] is False
    assert payload["formal_lc02_slot"] == "VACANT"
    assert not roots["destination"].exists()
    assert payload["publication"]["copied_file_count"] == 3
    assert len(payload["publication"]["files"]) == 3
    assert payload["publication"]["partial_exists"] is True
    for key in (
        "data_mode", "raw_source_hashes", "provider_hashes",
        "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
        "receiver_imu_as_body_imu", "final_v23_output_solver_input",
        "LegSA_output_solver_input", "per_case_tuning",
        "output_only_correction", "epoch_deleted_for_metric",
        "old_runtime_input_count", "code_commit", "config_hash",
    ):
        assert key in payload
