"""Audit counterexamples for original formal control functions, no real run.

All payloads are synthetic temporary fixtures. Native/evaluator invocations are
zero; no controller main, archive, cleanup, frozen data, or raw data is used.
Strict xfails document expected safeguards missing in the unchanged source.
"""
import json
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21 import aggregate as agg
from legsa_gins.paper_rebuild.clean6_sensor_v21 import binary_bridge as bridge
from legsa_gins.paper_rebuild.clean6_sensor_v21 import controller as control
from legsa_gins.paper_rebuild.clean6_sensor_v21 import evaluation as evaluation
from legsa_gins.paper_rebuild.clean6_sensor_v21 import runtime as runtime
from legsa_gins.paper_rebuild.protocol_v3 import controller as v3control
from legsa_gins.paper_rebuild.protocol_v3 import registry as v3registry


def _row(case="D01_seed_00", value=1., **extra):
    return dict(run_id="FIXTURE_" + case, evaluator_version="v3", dataset_id="BY2",
                case_id=case, method_id="F04", evaluation_status="COMPLETED",
                solver_terminal_status="COMPLETED", finite_output=True,
                case_family="fixture", degradation_id="D01",
                horizontal_rmse_m=value, synthetic_data_used=True,
                data_mode="synthetic_test", **extra)


def _partial_native(tmp_path):
    root = tmp_path / "partial_native"
    root.mkdir()
    # A single finite epoch occurs at 10 s in a requested [0, 100] s window.
    (root / "KF_GINS_Navresult.nav").write_text("10 " + "0 " * 9 + "\n")
    (root / "KF_GINS_STD.txt").write_text("10 " + "1 " * 9 + "\n")
    (root / "RUN_MANIFEST.json").write_text("{}\n")
    return root


@pytest.mark.xfail(strict=True, reason="CTL-01: formal output gate accepts one interior NAV/STD epoch")
@pytest.mark.parametrize("entry", [runtime.validate_run_outputs, bridge.validate_run_outputs])
def test_formal_gate_requires_complete_output_support(tmp_path, entry):
    with pytest.raises(RuntimeError):
        entry(_partial_native(tmp_path), {"window_contract": {"t_start": 0., "t_end": 100.}})


@pytest.mark.xfail(strict=True, reason="CTL-02: cached phase freeze omits source revalidation")
def test_cached_phase_freeze_rejects_drifted_source(tmp_path):
    source = tmp_path / "code/controller.py"
    source.parent.mkdir()
    source.write_text("changed scientific control\n")
    stage = tmp_path / "stage"
    folder = stage / "00_PREREGISTRATION"
    folder.mkdir(parents=True)
    (folder / "F01_AUDIT_CODE_FREEZE.json").write_text(json.dumps({
        "status": "COMMITTED_PUSHED", "code_commit": "a" * 40,
        "source_hashes": {"controller.py": "0" * 64},
    }))
    ctx = SimpleNamespace(stage=stage, reg=SimpleNamespace(code_root=source.parent),
                          code_commit="b" * 40)
    with pytest.raises(ValueError):
        control.phase_freeze(ctx, "F01_AUDIT")


def _identity_fixture():
    record = {"run_id": "FIXTURE", "dataset_id": "BY2", "case_id": "C00",
              "method_id": "F04", "terminal_status": "COMPLETED",
              "output_seal": {"KF_GINS_Navresult.nav": {"sha256": "a" * 64}}}
    row = {"run_id": "FIXTURE", "dataset_id": "BY2", "case_id": "C00",
           "method_id": "F04", "evaluator_version": "v3",
           "evaluator_sha256": "c" * 64, "native_nav_sha256": "a" * 64}
    contract = {"evaluation": {"evaluator": {"sha256": "c" * 64}}}
    return record, row, contract


@pytest.mark.xfail(strict=True, reason="CTL-03: row identity does not compare NAV hash with output_seal")
def test_recovered_evaluator_requires_the_sealed_native_nav():
    record, row, contract = _identity_fixture()
    row["native_nav_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        evaluation._validate_identity(record, "v3", row, contract)


@pytest.mark.xfail(strict=True, reason="CTL-03: method/evaluator identity can be omitted or disagree")
@pytest.mark.parametrize("change", ["wrong_method", "missing_evaluator", "missing_native_nav"])
def test_recovered_evaluator_requires_complete_scientific_identity(change):
    record, row, contract = _identity_fixture()
    if change == "wrong_method":
        row["method_id"] = "F03"
    else:
        row.pop("evaluator_sha256" if change == "missing_evaluator" else "native_nav_sha256")
    with pytest.raises(ValueError):
        evaluation._validate_identity(record, "v3", row, contract)


@pytest.mark.xfail(strict=True, reason="CTL-04: wrapper exception is mislabeled actual evaluator invocation")
def test_prelaunch_wrapper_exception_is_not_a_child_invocation(tmp_path, monkeypatch):
    calls = []
    def prelaunch_failure(*args):
        calls.append("adapter entered; no evaluator process launched")
        raise ValueError("fixture failed before launching any child")
    monkeypatch.setattr(evaluation, "one_evaluation", prelaunch_failure)
    row = evaluation._call({"run_id": "FIXTURE"}, "v3", {}, None, tmp_path, "fixture")
    assert len(calls) == 1
    assert row["evaluation_invoked"] is False


@pytest.mark.xfail(strict=True, reason="CTL-05: failed status overwrites contradictory native terminal")
def test_aggregate_rejects_contradictory_native_and_evaluation_status():
    source = _row()
    source["evaluation_status"] = "NOT_RUN_ALGORITHM_FAILURE"
    with pytest.raises(agg.ScientificStop):
        agg.normalize_rows([source])


@pytest.mark.xfail(strict=True, reason="CTL-06: nonfinite text metric stays COMPLETED and becomes unavailable")
@pytest.mark.parametrize("text", ["nan", "inf", "-inf"])
def test_aggregate_rejects_nonfinite_text_metrics(text):
    with pytest.raises(agg.ScientificStop):
        agg.normalize_rows([_row(value=text)])


@pytest.mark.xfail(strict=True, reason="CTL-07: duplicate local profile template ignores extra/missing target field")
def test_local_profile_template_requires_requested_flag_to_exist():
    sequence = "vrw: 1.0\n"
    full = "vrw: 1.0\nenable_raw_doppler: true\n"
    method = "vrw: 1.0\nenable_raw_doppler: false\n"
    with pytest.raises(ValueError):
        runtime.profile_template(sequence, full, method)


def test_unmodified_bytes_and_explicit_sensor_parameter_ledger():
    original = ("imupath: old\nvrw: 1e-3\nabstd: [2, 2, 2]\n"
                "arw: 7e-2 # retained scientific bytes\n"
                "basic_dual_yaw_fixed_std_deg: 1.5\n")
    text, ledger = runtime.patch_config(original, {"imupath": "fixture/中文.txt"},
                                        {"vrw": .02, "abstd": [3, 3, 3]})
    assert "arw: 7e-2 # retained scientific bytes\n" in text
    assert ledger["scientific_parameter_changed_keys"] == ["abstd", "basic_dual_yaw_fixed_std_deg", "vrw"]
    assert "2.933193" in text
    with pytest.raises(ValueError):
        runtime.patch_config(original, {}, {}, parameter_overrides={"arw": 3})


def test_role_append_is_prefix_preserving_and_rejects_change():
    text = "vrw: 1e-3 # retained\n"
    result, audit = runtime.append_sequence_runtime_role(text, "fixture_role")
    assert result.startswith(text) and audit["original_bytes_preserved_as_prefix"]
    with pytest.raises(ValueError):
        runtime.append_sequence_runtime_role(result, "different_role")


def test_all_yaw_failure_requires_full_loop_and_counter_evidence(tmp_path):
    (tmp_path / "PORT_GNSS_UPDATE_TRACE.csv").write_text(
        "yaw_update,yaw_mode,position_update,velocity_update\n1,REJECT,1,1\n")
    (tmp_path / "PORT_RUNTIME_LOOP_TRACE.csv").write_text(
        "loop_index,timestamp_after_process\n0,1\n1,2\n")
    (tmp_path / "stderr.log").write_text("error prefix: FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: "
                                         "actual formal module activation counters mismatch\n")
    cfg = {"enable_dual_yaw": True, "starttime": 0., "endtime": 2.}
    expected = {"dual_yaw_attempt_count": 1, "position_update_count": 1,
                "receiver_velocity_update_count": 1, "last_processed_imu_time": 2.}
    imu = np.array([[0.], [1.], [2.]])
    assert runtime.classify_all_yaw_rejected(tmp_path, cfg, expected, imu)["passed"]
    (tmp_path / "PORT_RUNTIME_LOOP_TRACE.csv").write_text("loop_index,timestamp_after_process\n0,1\n")
    assert not runtime.classify_all_yaw_rejected(tmp_path, cfg, expected, imu)["passed"]


def test_comparison_preserves_failure_denominator_and_exact_pairs():
    old = [_row("D01_seed_00", 10.), _row("D01_seed_01", 100.)]
    failed = _row("D01_seed_01", None)
    failed.update(evaluation_status="NOT_RUN_ALGORITHM_FAILURE",
                  solver_terminal_status=agg.ALGORITHM_FAILURE)
    new = [_row("D01_seed_00", 7.), failed]
    result = agg.comparison_tables(old, new, ["F04"], metrics=["horizontal_rmse_m"])
    row = next(r for r in result if r["scope"] == "ALL" and r["statistic"] == "mean")
    assert (row["registered_case_count"], row["paired_finite_count"]) == (2, 1)
    assert (row["v2_value"], row["v21_value"], row["v21_minus_v2"]) == (10., 7., -3.)
    assert row["availability"] == "PARTIAL" and row["v21_algorithm_failure_count"] == 1


def test_native_batch_drains_started_work_before_failure_receipt(tmp_path):
    # Bypass all real Context initialization; substitute a purely synthetic task.
    ctx = object.__new__(v3control.Context)
    ctx.scratch = tmp_path
    barrier = Barrier(2)
    def fake_native(spec):
        barrier.wait(timeout=2)
        if spec["run_id"] == "FAIL":
            raise ValueError("synthetic hard stop")
        return {"run_id": spec["run_id"], "status": "COMPLETED"}
    ctx._native = fake_native
    with pytest.raises(ValueError, match="synthetic hard stop"):
        ctx.native_batch([{"run_id": "FAIL"}, {"run_id": "PASS"}], 1)
    receipt = json.loads((tmp_path / "BATCHES/BATCH_001/HARD_STOP_DRAIN.json").read_text())
    assert receipt["all_started_futures_drained"]
    assert len(receipt["outcomes"]) == 2 and receipt["completed_records"][0]["run_id"] == "PASS"


def test_registry_transport_filter_retains_scientific_tokens():
    one = b"gnsspath: first\nyaw_std: 1e-3 # unchanged\nrun_id: one\n"
    two = b"gnsspath: second\nyaw_std: 1e-3 # unchanged\nrun_id: two\n"
    assert v3registry._scientific_bytes(one) == v3registry._scientific_bytes(two)
    assert v3registry._scientific_bytes(one) != v3registry._scientific_bytes(two.replace(b"1e-3", b"0.001"))


def test_binary_pin_rejects_bad_digest_and_symlink(tmp_path):
    path = tmp_path / "fixture_binary"
    path.write_bytes(b"not an executable; identity-only fixture")
    with pytest.raises(ValueError):
        bridge._pin(path, "0" * 64)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        bridge._pin(link, bridge.sha256_file(path))
