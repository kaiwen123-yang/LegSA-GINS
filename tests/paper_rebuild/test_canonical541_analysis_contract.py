import csv
import gzip
import json

import pytest

from legsa_gins.paper_rebuild.canonical541.analysis import AnalysisError, mechanism_tables
from legsa_gins.paper_rebuild.canonical541.runner import CanonicalRunnerError, validate_terminal_output


def _provider_root(tmp_path):
    root = tmp_path / "providers"
    (root / "FINALIZED" / "D60_seed_00" / "02_PROVIDERS").mkdir(parents=True)
    return root


def _logical():
    return [{
        "logical_id": "L1", "case_id": "D60_seed_00", "method_id": "F04",
        "run_id": "R1", "matrix": "full_algorithm",
    }]


def _write_empty_scheme_trace(runtime):
    with (runtime / "PORT_GNSS_UPDATE_TRACE.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=("gnss_time", "yaw_mode"), lineterminator="\n").writeheader()


def test_mechanism_failure_proof_emits_unknown_not_zero_counts(tmp_path):
    runtime = tmp_path / "run"
    runtime.mkdir()
    (runtime / "CANONICAL541_EXECUTION_PROOF.json").write_text(json.dumps({
        "terminal_status": "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF",
        "failure_type": "explicit_algorithm_state_failure",
        "forbidden_counts": {"fgo": 0, "qm": 0, "qa": 0, "contact": 0},
    }) + "\n", encoding="utf-8")
    source, scheme = mechanism_tables(
        _logical(), [{"run_id": "R1", "output_root": str(runtime),
                      "terminal_status": "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF"}],
        _provider_root(tmp_path),
    )
    assert len(scheme) == 1 and scheme[0]["mechanism_evaluable"] is False
    assert scheme[0]["attempt"] is None
    assert len(source) == 6 and all(row["evaluated_count"] is None for row in source)
    assert all(row["mechanism_status"] == "not_evaluable_algorithm_failure" for row in source)


def test_mechanism_unknown_runtime_source_id_fails_closed(tmp_path):
    runtime = tmp_path / "run"
    runtime.mkdir()
    (runtime / "CANONICAL541_EXECUTION_PROOF.json").write_text(json.dumps({
        "terminal_status": "COMPLETED_EVALUABLE", "forbidden_counts": {},
        "mechanism_evidence": {
            "scheme_c": {"attempt": 0, "normal": 0, "downweight": 0, "reject": 0},
            "source_aware": {"enabled": True, "evaluations": 1},
        },
    }) + "\n", encoding="utf-8")
    _write_empty_scheme_trace(runtime)
    with (runtime / "SOURCE_AWARE_WEIGHT_TRACE.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("time", "source_id", "combined_R_scale", "rejected"), lineterminator="\n")
        writer.writeheader(); writer.writerow({"time": 1, "source_id": "unknown_source", "combined_R_scale": 1, "rejected": 0})
    with pytest.raises(AnalysisError, match="unknown source-aware runtime source_id"):
        mechanism_tables(
            _logical(), [{"run_id": "R1", "output_root": str(runtime),
                          "terminal_status": "COMPLETED_EVALUABLE"}],
            _provider_root(tmp_path),
        )


def test_d40_audit_baseline_is_not_joined_as_solver_yaw_perturbation(tmp_path):
    provider = tmp_path / "providers"
    ledger = provider / "FINALIZED" / "D40_seed_00" / "02_PROVIDERS" / "CASE_PERTURBATION_LEDGER.csv.gz"
    ledger.parent.mkdir(parents=True)
    with gzip.open(ledger, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("source", "row_index", "base_time", "generated_time", "changed_fields"), lineterminator="\n")
        writer.writeheader(); writer.writerow({"source": "dual_yaw", "row_index": 0,
                                                "base_time": 100, "generated_time": 100,
                                                "changed_fields": "baseline_length_m"})
    runtime = tmp_path / "run_d40"; runtime.mkdir()
    (runtime / "CANONICAL541_EXECUTION_PROOF.json").write_text(json.dumps({
        "terminal_status": "COMPLETED_EVALUABLE", "forbidden_counts": {},
        "mechanism_evidence": {
            "scheme_c": {"attempt": 0, "normal": 0, "downweight": 0, "reject": 0},
            "source_aware": {"enabled": True, "evaluations": 1},
        },
    }) + "\n", encoding="utf-8")
    _write_empty_scheme_trace(runtime)
    with (runtime / "SOURCE_AWARE_WEIGHT_TRACE.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("time", "source_id", "combined_R_scale", "rejected"), lineterminator="\n")
        writer.writeheader(); writer.writerow({"time": 100, "source_id": "dual_antenna_yaw", "combined_R_scale": 2, "rejected": 0})
    logical = [{"logical_id": "L40", "case_id": "D40_seed_00", "method_id": "F04",
                "run_id": "R40", "matrix": "full_algorithm"}]
    source, scheme = mechanism_tables(
        logical, [{"run_id": "R40", "output_root": str(runtime),
                   "terminal_status": "COMPLETED_EVALUABLE"}], provider,
    )
    yaw = next(row for row in source if row["source"] == "dual_yaw")
    assert yaw["perturbed_epoch_count"] == 0
    assert yaw["audit_only_perturbed_epoch_count"] == 1
    assert yaw["perturbed_evaluated_count"] == 0
    assert yaw["perturbation_path_status"] == "audit_only_no_active_path"
    assert scheme[0]["perturbed_yaw_epoch_count"] == 0
    assert scheme[0]["audit_only_yaw_epoch_count"] == 1


def test_terminal_failure_proof_requires_finite_first_epoch(tmp_path):
    runtime = tmp_path / "failed_run"; runtime.mkdir()
    proof = {
        "run_id": "RFAIL", "terminal_status": "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF",
        "trace_used_online": False, "solver_read_ledger": {"trace_open_count": 0},
        "executable_hash": "a" * 64, "runtime_config_hash": "b" * 64,
        "method_bound_manifest_hash": "c" * 64, "failure_type": "explicit_algorithm_state_failure",
        "first_failure_epoch": None, "has_partial_state": True,
    }
    (runtime / "CANONICAL541_EXECUTION_PROOF.json").write_text(json.dumps(proof) + "\n", encoding="utf-8")
    row = {"run_id": "RFAIL", "output_root": str(runtime), "executable_hash": "a" * 64,
           "runtime_config_file_hash": "b" * 64, "method_bound_manifest_hash": "c" * 64}
    with pytest.raises(CanonicalRunnerError, match="finite first_failure_epoch"):
        validate_terminal_output(row)
