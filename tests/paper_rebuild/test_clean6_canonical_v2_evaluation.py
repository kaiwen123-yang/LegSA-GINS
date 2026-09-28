"""Pure/fixture verification; no raw data or scientific execution."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean6_canonical_v2.evaluation import (
    ALGORITHM_FAILURE, one_evaluation, wgs84_consistency_check,
)
from legsa_gins.paper_rebuild.manifest import sha256_file


def frames():
    # Equator/Greenwich, exactly radial +2 m. Full-support yaw crosses wrap.
    reference = pd.DataFrame({"time": [-100., 100.], "lat": [0., 0.], "lon": [0., 0.],
                              "alt": [0., 0.], "roll": [0., 0.], "pitch": [0., 0.], "yaw": [179., -179.]})
    nav = pd.DataFrame({"time": [0., 10.], "lat": [0., 0.], "lon": [0., 0.],
                        "alt": [2., 2.], "roll": [0., 0.], "pitch": [0., 0.], "yaw": [270., 270.]})
    errors = pd.DataFrame({"time": [0., 10.], "err_e_m": [0., 0.], "err_n_m": [0., 0.],
                           "err_u_m": [2., 2.], "yaw_err_deg": [0., .1]})
    return nav, errors, reference


def test_wgs84_actual_nav_full_support_wrap():
    nav, errors, reference = frames()
    result = wgs84_consistency_check(nav, errors, reference)
    assert result["passed"] is True
    assert result["horizontal_max_m"] == 0
    assert result["up_max_m"] == 0
    assert result["yaw_max_deg"] < 1e-12
    # Neither reference endpoint is within the old +-1 s cropped window.
    assert result["reference_cleaned_epoch_count"] == 2


def test_wrong_nav_point_fails_consistency():
    nav, errors, reference = frames()
    nav["alt"] = 0
    result = wgs84_consistency_check(nav, errors, reference)
    assert result["passed"] is False
    assert result["up_max_m"] == 2


def test_wrong_epochs_and_nonfinite_fail_without_row_deletion():
    nav, errors, reference = frames()
    errors.loc[0, "time"] = .001
    with pytest.raises(ValueError, match="epochs differ"):
        wgs84_consistency_check(nav, errors, reference)
    nav, errors, reference = frames()
    reference.loc[0, "roll"] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        wgs84_consistency_check(nav, errors, reference)


def test_algorithm_failure_never_evaluates(tmp_path, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Failed solver must not invoke evaluator")
    monkeypatch.setattr("legsa_gins.paper_rebuild.clean6_canonical_v2.evaluation.evaluate", forbidden)
    record = {"run_id": "R1", "case_id": "D60_seed_00", "method_id": "F03", "dataset_id": "BY2",
              "output_root": str(tmp_path / "native_missing"), "terminal_status": ALGORITHM_FAILURE}
    result = one_evaluation(record, "v3", {}, SimpleNamespace(), tmp_path, "test")
    assert result["evaluation_status"] == "NOT_RUN_ALGORITHM_FAILURE"
    assert result["algorithm_failure"] is True
    assert result["technical_failure"] is False
    assert result["evaluation_invoked"] is False
    assert "horizontal_rmse_m" not in result
    assert not (tmp_path / "native_missing").exists()


def test_unsealed_output_is_technical_failure_without_evaluation(tmp_path, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Unsealed solver must not invoke evaluator")
    monkeypatch.setattr("legsa_gins.paper_rebuild.clean6_canonical_v2.evaluation.evaluate", forbidden)
    native = tmp_path / "native"
    native.mkdir()
    (native / "OUTPUT_SEAL.json").write_text(json.dumps({"status": "NOT_SEALED", "files": {}}))
    record = {"run_id": "R2", "case_id": "C00_clean_normal", "method_id": "F03", "dataset_id": "BY2",
              "output_root": str(native), "terminal_status": "COMPLETED"}
    result = one_evaluation(record, "v2", {"evaluation": {}}, SimpleNamespace(), tmp_path, "test")
    assert result["evaluation_status"] == "FAILED_EVALUATOR"
    assert result["evaluation_invoked"] is False
    assert "sealed" in result["failure_message"]


def test_frozen_case_meta_reaches_event_statistics(tmp_path, monkeypatch):
    native = tmp_path / "native"
    native.mkdir()
    nav = np.zeros((3, 11))
    nav[:, 1] = [66., 67., 68.]
    nav[:, 2] = 35.
    nav[:, 3] = 115.
    np.savetxt(native / "KF_GINS_Navresult.nav", nav)
    std = np.ones((3, 10))
    std[:, 0] = nav[:, 1]
    np.savetxt(native / "KF_GINS_STD.txt", std)
    (native / "RUN_MANIFEST.json").write_text("{}")
    files = {p.name: {"sha256": sha256_file(p), "size_bytes": p.stat().st_size} for p in native.iterdir()}
    (native / "OUTPUT_SEAL.json").write_text(json.dumps({"status": "SEALED_BEFORE_EVALUATION", "files": files}))
    def fixture_evaluator(**kwargs):
        output = kwargs["outdir"]
        output.mkdir()
        errors = pd.DataFrame({"time": [66., 67., 68.], "err_n_m": [1., 2., 3.], "err_e_m": [0., 0., 0.],
            "err_u_m": [0., 0., 0.], "horizontal_err_m": [1., 2., 3.], "position_3d_err_m": [1., 2., 3.],
            "roll_err_deg": [0., 0., 0.], "pitch_err_deg": [0., 0., 0.], "yaw_err_deg": [0., 0., 0.]})
        errors.to_csv(output / "error_series.csv", index=False)
        return {"capture": {"reference_epoch_count": 3, "consistency": {"passed": True}}, "runtime_seconds": .1, "audit": {}}
    monkeypatch.setattr("legsa_gins.paper_rebuild.clean6_canonical_v2.evaluation.evaluate", fixture_evaluator)
    record = {"run_id": "R3", "case_id": "D58_seed_00", "method_id": "F03", "dataset_id": "BY2",
              "output_root": str(native), "terminal_status": "COMPLETED", "output_seal": files,
              "case_meta": {"anchor_time_s": 67., "degradation_parameters_json": '{"duration_s": 0.5}'}}
    from legsa_gins.paper_rebuild.clean5_sequence.evaluation_process import EVALUATOR_SHA256
    contract = {"evaluation": {"window": [66., 340.], "base_time": 0.,
                "trace": {"path": str(tmp_path / "never_opened_trace"), "sha256": "a"*64},
                "evaluator": {"path": str(tmp_path / "never_executed"), "sha256": EVALUATOR_SHA256}}}
    reg = SimpleNamespace(code_root=tmp_path, raw_root=tmp_path / "raw", clean_root=tmp_path)
    result = one_evaluation(record, "v2", contract, reg, tmp_path, "fixture")
    assert result["evaluation_status"] == "COMPLETED"
    assert result["degradation_window_start_s"] == 67.
    assert result["degradation_window_end_s"] == 67.5
    assert result["fault_window_horizontal_rmse_m"] == 2.
    assert result["post_window_horizontal_rmse_m"] == 3.
