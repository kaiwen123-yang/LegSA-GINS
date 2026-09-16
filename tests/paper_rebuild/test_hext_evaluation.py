"""Offline adapter contract tests: no solver, evaluator or trace payload access."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.hext import external_evaluation as evaluation


def _sequence(tmp_path):
    return SimpleNamespace(
        sequence_id="BY2O", trace=tmp_path / "raw" / "registry_trace.csv",
        trace_sha256="4" * 64, base_time=1772780400.0, window=(3186.0, 3563.0),
        baseline_median_m=0.35013463864843675,
    )


def test_external_argv_uses_sequence_trace_and_base_time_omits_std(tmp_path, monkeypatch):
    sequence = _sequence(tmp_path)
    monkeypatch.setattr(evaluation, "run_process_group", lambda *a, **k: pytest.fail("No evaluator invocation"))
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("No file opens for request construction"))
    argv = evaluation.evaluator_argv(sequence=sequence, evaluator=tmp_path / "evaluator.py",
                                     nav=tmp_path / "sealed.nav", outdir=tmp_path / "future")
    assert "--std" not in argv
    assert argv[argv.index("--trace") + 1] == str(sequence.trace)
    assert argv[argv.index("--base_time") + 1] == "1772780400.0"
    assert argv[-2:] == ["--yaw_truth_mode", "enu"]
    config = evaluation.capture_config(sequence=sequence, evaluator=tmp_path / "evaluator.py", outdir=tmp_path / "future")
    assert config["window"] == [3186.0, 3563.0]
    assert config["trace_sha256"] == sequence.trace_sha256
    assert config["STD"] == "OMITTED_AS_FROZEN_EXTERNAL_CONTRACT"


def _errors(times):
    return pd.DataFrame({"time": times, **{name: np.ones(len(times)) for name in (
        "err_n_m", "err_e_m", "err_u_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg",
        "horizontal_err_m", "position_3d_err_m",
    )}})


def test_external_metrics_denominator_uses_sequence_window():
    nav = np.zeros((5, 11))
    nav[:, 1] = [66, 340, 413, 500, 683]
    row = evaluation.metrics(_errors([413.0, 683.0]), nav,
        {"evaluator_contract": "evaluator_contract_v3"}, window=(413.0, 683.0), reference_count=4)
    assert row["output_epoch_count"] == 3
    assert row["matched_epoch_count"] == 2
    assert row["coverage_ratio"] == 2 / 3
    assert row["sequence_window_start_s"] == 413.0
    assert row["sequence_window_end_s"] == 683.0
    assert row["STD"] == evaluation.STD_POLICY
    with pytest.raises(ValueError, match="no epoch deletion"):
        evaluation.metrics(_errors([412.9, 500.0]), nav, {}, window=(413.0, 683.0))


def test_v3_uses_frozen_transform_and_preserves_nonposition_tokens(tmp_path):
    sequence = _sequence(tmp_path)
    nav = tmp_path / "native.nav"
    lines = ["% index time lat_deg lon_deg height_m vn ve vd roll pitch yaw",
             "11 3186 30 120 10 0 0 0 1 2 3", "12 3563 30 120 10 0 0 0 2 3 4"]
    nav.write_text("\n".join(lines) + "\n", encoding="utf-8")
    source_bytes = nav.read_bytes()
    actual, original, manifest = evaluation.prepare_evaluator_nav(sequence=sequence, nav=nav,
        outdir=tmp_path / "v3", version="v3")
    transformed = evaluation.canonical._read_numeric_table(actual).to_numpy(float)
    np.testing.assert_allclose(transformed[:, 2:5], evaluation.transform_nav(original, sequence.baseline_median_m)[:, 2:5])
    assert manifest["lever_frd_m"] == [0.03, 0.03 - 0.5 * sequence.baseline_median_m, -0.30]
    retained = [0, 1, 5, 6, 7, 8, 9, 10]
    for before, after in zip(lines[1:], actual.read_text().splitlines()):
        assert [before.split()[k] for k in retained] == [after.split()[k] for k in retained]
    assert nav.read_bytes() == source_bytes
    actual_v2, _, _ = evaluation.prepare_evaluator_nav(sequence=sequence, nav=nav,
        outdir=tmp_path / "unused_v2", version="v2")
    assert actual_v2 == nav
    assert not (tmp_path / "unused_v2").exists()


def test_body_frame_bias_is_reused_without_new_definition():
    from legsa_gins.paper_rebuild.clean5_parity.evaluation import body_frame_bias
    assert evaluation.body_frame_bias is body_frame_bias
