"""Synthetic-only H03 gate/classification tests; no raw/native/evaluator execution."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.hext import continuation as c
from legsa_gins.paper_rebuild.hext import external_evaluation as e
from legsa_gins.paper_rebuild.manifest import sha256_file


def _native(tmp_path, changes=()):
    rows = [{"method_id": "SYNTHETIC_TEST", "absolute_time_unix_seconds": 1000 + i,
             "time_seconds": i, "north_m": 100., "east_m": 200., "down_m": -10.,
             "vn_mps": 0., "ve_mps": 0., "vd_mps": 0., "roll_deg": 0.,
             "pitch_deg": 0., "yaw_ned_deg": 0., "P_left_0_0": 1.,
             "covariance_coordinate": "test", "covariance_state_order": "test"} for i in range(3)]
    for index, delta in changes:
        rows[index].update(delta)
    path = tmp_path / "NAV.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_d8_uses_original_frame_origin_and_vector_norm_boundary(tmp_path):
    nav = _native(tmp_path, [(1, {"north_m": 6100., "east_m": 8200., "vn_mps": 30., "ve_mps": 40.})])
    result = c.bounded_native_output(nav, expected_sha256=sha256_file(nav))
    assert result["passed"]
    assert result["max_position_displacement_m"] == 10000
    assert result["max_speed_mps"] == 50
    assert result["row_count"] == 3


@pytest.mark.parametrize("delta,reason", [
    ({"north_m": 10100.01}, "position_displacement_m"),
    ({"vn_mps": 40., "ve_mps": 40.}, "speed_mps"),
    ({"down_m": 990.01}, "height_displacement_m"),
    ({"P_left_0_0": float("nan")}, "NONFINITE_NUMERIC_NATIVE_ROW"),
])
def test_d8_first_violation_includes_fullrate_source_line_time_hash(tmp_path, delta, reason):
    nav = _native(tmp_path, [(1, delta)])
    digest = sha256_file(nav)
    result = c.bounded_native_output(nav, expected_sha256=digest)
    assert not result["passed"]
    assert result["native_status"] == "ALGORITHM_FAILURE_DIVERGED"
    assert result["source_nav_sha256"] == digest
    first = result["first_violation"]
    assert (first["data_row_one_based"], first["csv_line_one_based"], first["time_seconds"]) == (2, 3, 1.)
    assert reason in first["reasons"]
    json.dumps(result, allow_nan=False)
    assert sha256_file(nav) == digest


def test_d8_nonfinite_initial_position_and_empty_rejected(tmp_path):
    nav = _native(tmp_path, [(0, {"north_m": float("inf")})])
    result = c.bounded_native_output(nav, expected_sha256=sha256_file(nav))
    assert not result["passed"]
    json.dumps(result, allow_nan=False)
    nav.write_text(nav.read_text().splitlines()[0] + "\n")
    result = c.bounded_native_output(nav, expected_sha256=sha256_file(nav))
    assert not result["passed"] and result["row_count"] == 0


def test_d8_identity_failure_precedes_payload_use(tmp_path):
    nav = _native(tmp_path)
    with pytest.raises(RuntimeError, match="IDENTITY_MISMATCH"):
        c.bounded_native_output(nav, expected_sha256="0" * 64)


def test_launch_reservation_spends_slot_before_call_and_never_retries(tmp_path):
    ledger = tmp_path / "launch.jsonl"
    allowed = {(f"RUN{i}", "v3") for i in range(12)}
    c.reserve_evaluator_slot(ledger, run_id="RUN0", version="v3", allowed_slots=allowed)
    with pytest.raises(RuntimeError, match="ALREADY_ATTEMPTED"):
        c.reserve_evaluator_slot(ledger, run_id="RUN0", version="v3", allowed_slots=allowed)
    for i in range(1, 11):
        c.reserve_evaluator_slot(ledger, run_id=f"RUN{i}", version="v3", allowed_slots=allowed)
    with pytest.raises(RuntimeError, match="BUDGET"):
        c.reserve_evaluator_slot(ledger, run_id="RUN11", version="v3", allowed_slots=allowed)
    with pytest.raises(RuntimeError, match="ORIGINAL_UNUSED"):
        c.reserve_evaluator_slot(ledger, run_id="OLD_FAILED", version="v3", allowed_slots=allowed)
    assert len(ledger.read_text().splitlines()) == 11


def test_continuation_scope_matches_exact_registered_unused_slots():
    ledger = {(f"RUN{i}", "v3"): {"status": "NOT_RUN_HARD_STOP"} for i in range(11)}
    contract = {"schema_version": "hext.external_sequences.contract.v1.1", "task": "H-EXT-03",
                "authorization": "H-EXT-03 prompt 2026-09-16", "execution_authorized": True,
                "budget": {"native": 0, "evaluator": 11}, "continuation_remaining_slots": [
                    {"run_id": key[0], "version": key[1]} for key in ledger]}
    assert c.validate_continuation_authorization(contract, ledger) == set(ledger)
    contract["budget"]["native"] = 1
    with pytest.raises(RuntimeError, match="AUTHORIZATION_OR_SLOT_SCOPE"):
        c.validate_continuation_authorization(contract, ledger)
    contract["budget"]["native"] = 0
    contract["continuation_remaining_slots"][0]["run_id"] = "PREVIOUSLY_FAILED"
    with pytest.raises(RuntimeError, match="AUTHORIZATION_OR_SLOT_SCOPE"):
        c.validate_continuation_authorization(contract, ledger)


def test_d7_preserves_failed_history_without_admitting_metrics_or_trace(tmp_path):
    record = {"sequence_id": "BY2H", "configuration_id": "EXT05C-S", "run_id": "RUN", "start_mode": "FILE_START"}
    gate = {"sealed_evaluator_nav_sha256": "d" * 64, "passed": False}
    history = {"status": "FAILED_EVALUATOR_CONSISTENCY", "source": "original/v3", "source_sha256": "a" * 64}
    result = c._classification_payload(record, "v3", gate, history, "code")
    assert result["row"]["evaluation_status"] == "NOT_RUN_ALGORITHM_FAILURE"
    assert result["row"]["historical_evaluation_status"] == "FAILED_EVALUATOR_CONSISTENCY"
    assert result["row"]["evaluation_invoked"] is False
    assert result["audit"]["trace_open_count"] == 0
    assert not any("rmse" in field for field in result["row"])


def _capture():
    return {"trace_sha256": "4" * 64, "trace_handle_hash_count": 1,
            "selected_columns": e.SELECTED_COLUMNS, "pid": 123, "consistency": {"passed": False}}


def test_d12_false_consistency_is_separate_from_identity_failure():
    sequence = SimpleNamespace(trace_sha256="4" * 64)
    capture = _capture()
    assert e._capture_identity_failures(capture, sequence, [{"pid": 123}]) == []
    capture["trace_sha256"] = "5" * 64
    assert e._capture_identity_failures(capture, sequence, [{"pid": 123}])
    for malformed in (0, 1, None, "false"):
        capture = _capture()
        capture["consistency"]["passed"] = malformed
        assert e._capture_identity_failures(capture, sequence, [{"pid": 123}])


def _evaluate_fixture(tmp_path):
    nav = tmp_path / "test.nav"
    nav.write_text("% synthetic fixture\n1 1 30 120 10 0 0 0 0 0 0\n2 2 30 120 10 0 0 0 0 0 0\n")
    evaluator = tmp_path / "evaluator"
    evaluator.write_text("test only, never executed\n")
    seq = SimpleNamespace(sequence_id="TEST", window=(1, 2), base_time=1000.,
                          output_root=tmp_path / "archive", hext_scratch=tmp_path,
                          trace_sha256="4" * 64)
    return nav, evaluator, seq


def test_d12_bounded_false_consistency_returns_unavailable_without_metrics(tmp_path, monkeypatch):
    nav, evaluator, seq = _evaluate_fixture(tmp_path)
    monkeypatch.setattr(e, "EVALUATOR_SHA256", sha256_file(evaluator))
    monkeypatch.setattr(e, "_evaluate_process", lambda **kw: {
        "capture": _capture(), "audit": {"passed": False, "technical_passed": True,
        "consistency_passed": False, "trace_open_count": 1}, "runtime_seconds": .1,
        "outdir": str(kw["outdir"])})
    monkeypatch.setattr(e.canonical, "_read_error_series", lambda *a: pytest.fail("Failed consistency must not admit errors"))
    result = e.evaluate(sequence=seq, evaluator=evaluator, nav=nav, expected_nav_sha256=sha256_file(nav),
        outdir=tmp_path / "eval", version="v2", identity={}, consistency_failure_policy="D12_BOUNDED_UNAVAILABLE",
        bounded_gate={"passed": True, "sealed_evaluator_nav_sha256": sha256_file(nav)})
    assert result["row"]["evaluation_status"] == "UNAVAILABLE_EVALUATION_FAILED"
    assert result["audit"]["passed"] is False
    assert result["row"]["evaluation_invoked"] is True
    assert not any("rmse" in field for field in result["row"])


def test_d12_soft_path_requires_native_bound_identity_and_propagates_technical_failure(tmp_path, monkeypatch):
    nav, evaluator, seq = _evaluate_fixture(tmp_path)
    kw = dict(sequence=seq, evaluator=evaluator, nav=nav, expected_nav_sha256=sha256_file(nav),
        outdir=tmp_path / "eval", version="v2", identity={}, consistency_failure_policy="D12_BOUNDED_UNAVAILABLE")
    monkeypatch.setattr(e, "_evaluate_process", lambda **args: pytest.fail("No evaluator without D8"))
    with pytest.raises(ValueError, match="D8 gate"):
        e.evaluate(**kw)
    with pytest.raises(ValueError, match="D8 gate"):
        e.evaluate(**kw, bounded_gate={"passed": True, "sealed_evaluator_nav_sha256": "0" * 64})
    def technical_failure(**args):
        raise RuntimeError("evaluator_returncode=1")
    monkeypatch.setattr(e, "_evaluate_process", technical_failure)
    with pytest.raises(RuntimeError, match="returncode"):
        e.evaluate(**kw, bounded_gate={"passed": True, "sealed_evaluator_nav_sha256": sha256_file(nav)})
