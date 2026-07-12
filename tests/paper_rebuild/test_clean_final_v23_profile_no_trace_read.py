import inspect

from legsa_gins.paper_rebuild import final_v23_clean_input as builder
from legsa_gins.paper_rebuild.evidence import BY2_RAW_RELATIVE_PATHS, BY2_TRACE_RELATIVE_PATH


def test_clean_generator_has_no_trace_parameter_or_actual_read_role() -> None:
    parameters = inspect.signature(builder.generate_final_v23_clean_input).parameters
    source = inspect.getsource(builder.generate_final_v23_clean_input)

    assert all("trace" not in name.casefold() for name in parameters)
    assert BY2_TRACE_RELATIVE_PATH not in builder.ACTUAL_SOURCE_ROLES
    assert "verify_by2_raw_22" not in source
    assert "yaw_source_mode=\"status\"" in source
    assert "yaw_noise_std_deg=0.0" in source


def test_outer_raw_checkpoint_marks_trace_as_integrity_only() -> None:
    source = inspect.getsource(builder.validate_raw_checkpoint)
    assert "outer_raw_integrity_hash_audit_only" in source
    assert "trace_provider_or_solver_input" in source


def test_outer_checkpoint_binds_22_but_generation_ledger_binds_only_four() -> None:
    hashes = {
        relative: f"{index + 1:064x}"
        for index, relative in enumerate(BY2_RAW_RELATIVE_PATHS)
    }
    lock = {
        relative: {"sha256": digest, "dataset": "BY2"}
        for relative, digest in hashes.items()
    }
    checkpoint = {
        "schema_version": "paper_rebuild.final_v23_external_raw_checkpoint.v1",
        "audit_phase": "pre_generation",
        "raw_hash_lock_sha256": builder.EXPECTED_RAW_LOCK_SHA256,
        "expected": 22,
        "verified": 22,
        "missing": 0,
        "mismatch": 0,
        "symlink_escape": 0,
        "raw_mutation": 0,
        "passed": True,
        "verified_hashes": hashes,
        "trace_read_role": "outer_raw_integrity_hash_audit_only",
        "trace_provider_or_solver_input": False,
    }

    verified = builder.validate_raw_checkpoint(
        checkpoint,
        phase="pre_generation",
        lock=lock,
        expected_lock_sha256=builder.EXPECTED_RAW_LOCK_SHA256,
    )
    actual_hashes = {
        relative: hashes[relative] for relative in builder.ACTUAL_SOURCE_ROLES
    }
    ledger = builder.build_source_ledger(actual_hashes)

    assert len(verified) == 22
    assert len(ledger) == 4
    assert all(row["expected_sha256"] == row["actual_sha256"] == row["sha256"] for row in ledger)
    assert BY2_TRACE_RELATIVE_PATH in verified
    assert BY2_TRACE_RELATIVE_PATH not in {row["relative_path"] for row in ledger}


def test_final_manifest_requires_actual_file_open_audit_seal() -> None:
    seal_source = inspect.getsource(builder.seal_clean_input_file_open_audit)
    validation_source = inspect.getsource(builder.validate_clean_input_manifest)
    assert "parse_strace_openat_paths" in seal_source
    assert "unexpected_raw_root_relative_paths" in seal_source
    assert "trace_open_count" in seal_source
    assert 'payload.get("file_open_audit_sealed") is not True' in validation_source
