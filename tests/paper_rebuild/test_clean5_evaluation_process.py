"""Synthetic observation/audit tests; no real NAV or reference payload is read."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean5_sequence import evaluation_process as process
from legsa_gins.paper_rebuild.clean5_sequence.evaluator_capture import consistency_check

REPO = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def synthetic(tmp_path):
    raw, clean = tmp_path / "raw", tmp_path / "clean"
    raw.mkdir()
    clean.mkdir()
    trace, nav, std = raw / "trace.csv", clean / "NAV.nav", clean / "STD.txt"
    times = np.arange(5, dtype=float)
    lat, lon, alt = 39 + times * 0.000001, 116 + times * 0.000001, 50 + times * 0.01
    yaw_enu = np.array([179, -179, -177, -175, -173], dtype=float)
    pd.DataFrame({"aligned_time": times, "latitude": lat, "longitude": lon,
                  "height": alt, "roll": times * 0, "pitch": times * 0, "yaw": yaw_enu}).to_csv(trace, index=False)
    np.savetxt(nav, np.column_stack([times * 0, times, lat + 1e-8, lon + 1e-8,
                                    alt + 0.002, times * 0, times * 0, times * 0,
                                    times * 0, times * 0, (90 - yaw_enu) % 360 + 0.1]), fmt="%.12f")
    np.savetxt(std, np.column_stack([times, np.ones((5, 9))]), fmt="%.12f")
    return {"trace": trace, "nav": nav, "std": std, "raw_root": raw, "clean_root": clean,
            "trace_sha256": digest(trace), "base_time": 0.0, "window": (0.0, 4.0), "code_root": REPO}


@pytest.fixture
def archived_evaluator():
    value = os.environ.get("LEGSA_EXACT_EVALUATOR")
    if not value:
        pytest.skip("LEGSA_EXACT_EVALUATOR is required for archived-script synthetic subprocess tests")
    path = Path(value)
    assert path.is_file() and digest(path) == process.EVALUATOR_SHA256
    assert shutil.which("strace"), "strace is required for archived evaluator observation tests"
    return path


def test_archived_observer_preserves_summary_and_error_bytes_and_single_reference_open(synthetic, archived_evaluator):
    observed = synthetic["clean_root"] / "observed"
    plain = synthetic["clean_root"] / "plain"
    before = {key: digest(synthetic[key]) for key in ("trace", "nav", "std")}
    captured = process.evaluate(**synthetic, evaluator=archived_evaluator, outdir=observed, instrument=True)
    unobserved = process.evaluate(**synthetic, evaluator=archived_evaluator, outdir=plain, instrument=False)
    for name in ("summary.json", "error_series.csv"):
        assert (observed / name).read_bytes() == (plain / name).read_bytes()
    assert before == {key: digest(synthetic[key]) for key in before}
    assert unobserved["capture"] is None
    state, audit = captured["capture"], captured["audit"]
    assert audit["passed"] and audit["trace_open_count"] == audit["raw_open_count"] == 1
    assert audit["trace_open_records"][0]["pid"] == state["pid"]
    assert state["pid"] != os.getpid()
    assert state["trace_sha256"] == synthetic["trace_sha256"] and state["trace_handle_hash_count"] == 1
    assert state["trace_size_bytes"] == synthetic["trace"].stat().st_size
    assert "before parsing" in state["hash_role"] and state["observation_only"] is True
    assert state["selected_columns"] == {"time": "aligned_time", "lat": "latitude", "lon": "longitude",
                                          "height": "height", "roll": "roll", "pitch": "pitch", "yaw": "yaw"}
    assert state["reference_epoch_count"] == 5 and state["consistency"]["passed"]
    assert state["consistency"]["plotting_module_imported"] is False
    assert state["consistency"]["projection_source_sha256"] == digest(REPO / "src/legsa_gins/paper_rebuild/publication/canonical541_figures.py")
    assert audit["bag_open_count"] == audit["fpl_open_count"] == 0
    assert audit["write_scope"]["pass"] and audit["write_scope"]["raw_write_open_count"] == 0
    assert audit["write_scope"]["write_outside_run_count"] == 0
    assert "CLEAN5_SELECTED_TRACE_COLUMNS" in (observed / "evaluator_stdout.log").read_text()


def test_wrong_reference_hash_refuses_before_parser_or_metrics(synthetic, archived_evaluator):
    out = synthetic["clean_root"] / "bad_hash"
    # Missing required columns would fail load_trace if hashing were not first.
    synthetic["trace"].write_text("deliberately_wrong_header\nnot_a_trace\n")
    with pytest.raises(RuntimeError, match="SHA256 mismatch before evaluator parsing"):
        process.evaluate(**synthetic, evaluator=archived_evaluator, outdir=out)
    assert not (out / "summary.json").exists() and not (out / "error_series.csv").exists()
    assert not (out / "EVALUATOR_CAPTURE.json").exists()
    assert "CLEAN5_SELECTED_TRACE_COLUMNS" not in (out / "evaluator_stdout.log").read_text()
    audit = json.loads((out / "EVALUATOR_STRACE_AUDIT.json").read_text())
    assert not audit["passed"] and audit["trace_open_count"] == 1 and audit["exit_code"] != 0


def test_sitecustomize_install_error_is_fatal_before_user_code(tmp_path):
    config = tmp_path / "broken.json"
    config.write_text("not-json")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": os.pathsep.join(
        [str(REPO / "scripts/paper_rebuild/clean5_evaluator_observer"), str(REPO / "src")]),
        "CLEAN5_EVALUATOR_CAPTURE_CONFIG": str(config), "OPENBLAS_NUM_THREADS": "1"}
    result = subprocess.run([sys.executable, "-B", "-c", "print('USER_CODE_REACHED')"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 125
    assert "USER_CODE_REACHED" not in result.stdout and "JSONDecodeError" in result.stderr


def fake_process(monkeypatch, fixture, out, *, capture_mutation=None, extra_opens=()):
    evaluator = fixture["clean_root"] / "fake_evaluator.py"
    evaluator.write_text("# never executed; fake process tests only\n")
    original_sha = process.sha256_file
    monkeypatch.setattr(process, "sha256_file", lambda p: process.EVALUATOR_SHA256 if Path(p) == evaluator else original_sha(p))

    def run(command, **kwargs):
        trace = fixture["trace"]
        lines = [f'1001 openat(AT_FDCWD, "{trace}", O_RDONLY|O_CLOEXEC) = 3<{trace}>']
        lines.extend(f'1001 openat(AT_FDCWD, "{path}", {flags}) = 4<{path}>' for path, flags in extra_opens)
        (out / "EVALUATOR_OPENAT.strace").write_text("\n".join(lines) + "\n")
        (out / "summary.json").write_text("{}\n")
        (out / "error_series.csv").write_text("time\n0\n1\n")
        state = {"pid": 1001, "trace_sha256": fixture["trace_sha256"], "trace_handle_hash_count": 1,
                 "trace_size_bytes": trace.stat().st_size, "evaluator_sha256": process.EVALUATOR_SHA256,
                 "observation_only": True, "hash_role": "existing evaluator handle; hash then rewind before parsing; zero extra trace opens",
                 "window": list(fixture["window"]), "reference_epoch_count": 5,
                 "selected_columns": {"time": "aligned_time", "lat": "latitude", "lon": "longitude",
                     "height": "height", "roll": "roll", "pitch": "pitch", "yaw": "yaw"},
                 "consistency": {"passed": True, "horizontal_max_m": 0, "up_max_m": 0, "yaw_max_deg": 0}}
        if capture_mutation is not None:
            state = capture_mutation(state)
        if state is not None:
            (out / "EVALUATOR_CAPTURE.json").write_text(json.dumps(state))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(process, "run_process_group", run)
    return evaluator


@pytest.mark.parametrize("mutation", [lambda s: None, lambda s: {},
    lambda s: s | {"trace_sha256": "0" * 64}, lambda s: s | {"pid": 9999},
    lambda s: s | {"trace_handle_hash_count": 2}])
def test_missing_or_forged_capture_fails_and_keeps_audit(monkeypatch, synthetic, mutation):
    out = synthetic["clean_root"] / "forged"
    evaluator = fake_process(monkeypatch, synthetic, out, capture_mutation=mutation)
    with pytest.raises(RuntimeError, match="observation mismatch"):
        process.evaluate(**synthetic, evaluator=evaluator, outdir=out)
    audit = json.loads((out / "EVALUATOR_STRACE_AUDIT.json").read_text())
    assert not audit["passed"]
    assert "trace hash/process observation mismatch" in audit["failures"]


@pytest.mark.parametrize("where,flags,accepted", [("owned", "O_WRONLY|O_CREAT|O_TRUNC", True),
    ("device", "O_RDWR", True), ("other_run", "O_WRONLY|O_CREAT", False),
    ("raw_write", "O_WRONLY", False), ("other_raw", "O_RDONLY", False),
    ("bag", "O_RDONLY", False), ("second_trace", "O_RDONLY", False)])
def test_actual_audit_whitelist_and_single_reference_requirement(monkeypatch, synthetic, where, flags, accepted):
    out = synthetic["clean_root"] / "audit_case"
    path = {"owned": out / "artifact.txt", "device": Path("/dev/null"),
        "other_run": synthetic["clean_root"] / "unrelated" / "artifact.txt",
        "raw_write": synthetic["trace"], "other_raw": synthetic["raw_root"] / "other.csv",
        "bag": synthetic["raw_root"] / "record.bag", "second_trace": synthetic["trace"]}[where]
    evaluator = fake_process(monkeypatch, synthetic, out, extra_opens=[(path, flags)])
    if accepted:
        result = process.evaluate(**synthetic, evaluator=evaluator, outdir=out)
        assert result["audit"]["passed"]
    else:
        with pytest.raises(RuntimeError):
            process.evaluate(**synthetic, evaluator=evaluator, outdir=out)
        assert not json.loads((out / "EVALUATOR_STRACE_AUDIT.json").read_text())["passed"]


@pytest.fixture
def consistency_frames():
    t = np.arange(3, dtype=float)
    reference = pd.DataFrame({"time": t, "lat": [39.] * 3, "lon": [116.] * 3,
                              "alt": [50.] * 3, "yaw": [179., -179., -177.]})
    nav = reference.copy()
    nav["yaw"] = ((90 - reference.yaw) % 360) + 0.1
    nav["alt"] += 0.002
    errors = pd.DataFrame({"time": t, "err_e_m": np.zeros(3), "err_n_m": np.zeros(3),
                           "err_u_m": [0.002] * 3, "yaw_err_deg": [0.1] * 3})
    return nav, errors, reference


def test_independent_consistency_handles_yaw_wrap_and_does_not_mutate(consistency_frames):
    before = tuple(frame.copy(deep=True) for frame in consistency_frames)
    result = consistency_check(*consistency_frames)
    assert result["passed"] and result["matched_epoch_count"] == 3
    assert result["horizontal_max_m"] == 0 and result["up_max_m"] < 1e-12 and result["yaw_max_deg"] < 1e-10
    for old, current in zip(before, consistency_frames):
        pd.testing.assert_frame_equal(old, current)


@pytest.mark.parametrize("column", ["err_e_m", "err_u_m", "yaw_err_deg"])
def test_independent_consistency_records_failure_above_fixed_threshold(consistency_frames, column):
    nav, errors, reference = consistency_frames
    errors.loc[1, column] += 0.0101
    result = consistency_check(nav, errors, reference)
    assert not result["passed"]
    assert result["position_threshold_m"] == result["yaw_threshold_deg"] == 0.01
    assert result["time_offset_applied"] == 0


def test_independent_consistency_rejects_nonfinite_residual(consistency_frames):
    nav, errors, reference = consistency_frames
    errors.loc[1, "err_e_m"] = np.nan
    with pytest.raises(RuntimeError, match="Nonfinite consistency"):
        consistency_check(nav, errors, reference)
