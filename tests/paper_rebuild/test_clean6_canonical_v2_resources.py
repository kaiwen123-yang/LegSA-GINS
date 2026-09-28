"""Resource-policy tests use short infrastructure children, never scientific data."""
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import time

import pytest

from legsa_gins.paper_rebuild.clean6_canonical_v2.resources import (
    choose_evaluator_workers, process_tree_rss, read_process_resources,
    resource_command, solver_workers,
)
from legsa_gins.paper_rebuild.clean6_canonical_v2.storage import ResourceMonitor
from legsa_gins.paper_rebuild.manifest import sha256_file


def test_native_rss_wall_and_nonzero_exit_are_measured(tmp_path):
    output = tmp_path / "PROCESS_RESOURCES.txt"
    command = [sys.executable, "-c", "import time; x=bytearray(16*1024*1024); time.sleep(.06); raise SystemExit(7)"]
    completed = subprocess.run(resource_command(command, output), capture_output=True, text=True, timeout=5)
    assert completed.returncode == 7
    record = read_process_resources(output)
    assert record["status"] == "AVAILABLE"
    assert record["exit_code"] == 7
    assert record["peak_rss_bytes"] >= 16*1024*1024
    assert record["wall_seconds"] >= .05
    assert record["user_cpu_seconds"] >= 0
    assert record["system_cpu_seconds"] >= 0
    with pytest.raises(ValueError, match="fresh"):
        resource_command(command, output)


def test_resource_records_fail_closed_when_missing_truncated_or_nonfinite(tmp_path):
    output = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        read_process_resources(output)
    for text in ("", "P09C_RESOURCE_V1\nwall_seconds=1\n",
                 "P09C_RESOURCE_V1\nwall_seconds=nan\nuser_cpu_seconds=0\nsystem_cpu_seconds=0\nmax_rss_kib=1\nexit_code=0\n",
                 "P09C_RESOURCE_V1\nwall_seconds=0\nuser_cpu_seconds=0\nsystem_cpu_seconds=0\nmax_rss_kib=0\nexit_code=0\n"):
        output.write_text(text)
        with pytest.raises(ValueError):
            read_process_resources(output)


def test_pool_formula_reserves_two_cpus_and_measured_memory():
    assert solver_workers(24) == 22
    assert solver_workers(128) == 22
    assert solver_workers(3) == 1
    assert choose_evaluator_workers(1000, 150, 80, 24) == 6
    assert choose_evaluator_workers(1000, 151, 80, 24) == 5
    assert choose_evaluator_workers(1000, 150, 80, 4) == 2
    assert choose_evaluator_workers(1_000_000, 1, 1, 128) == 22
    with pytest.raises(ValueError, match="No evaluator slot"):
        choose_evaluator_workers(1000, 651, 80, 24)
    for invalid in (0, None, float("nan"), True):
        with pytest.raises(ValueError, match="positive measured"):
            choose_evaluator_workers(1000, 100, invalid, 24)
    with pytest.raises(ValueError, match="three visible"):
        solver_workers(2)


def test_owned_descendants_and_phase_peak_are_recorded(tmp_path):
    grandchild = "import time; x=bytearray(32*1024*1024); print('ready',flush=True); time.sleep(10)"
    parent = ("import subprocess,sys,time; x=bytearray(16*1024*1024); "
              "subprocess.Popen([sys.executable,'-c',"+repr(grandchild)+"]); time.sleep(10)")
    process = subprocess.Popen([sys.executable, "-c", parent], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        assert select.select([process.stdout], [], [], 3)[0]
        assert process.stdout.readline().strip() == "ready"
        observed = process_tree_rss(process.pid)
        assert observed["owned_process_count"] == 2
        assert observed["owned_rss_bytes"] >= 48*1024*1024
        path = tmp_path / "samples.jsonl"
        with ResourceMonitor(tmp_path, tmp_path, path, root_pid=process.pid, sample_interval_seconds=.02) as monitor:
            monitor.begin_phase("solver")
            time.sleep(.06)
            phase = monitor.end_phase()
            assert phase["phase"] == "solver"
            assert phase["owned_process_tree_peak_rss_bytes"] >= 48*1024*1024
            assert phase["owned_process_count_peak"] == 2
            assert phase["sample_count"] >= 3
            with pytest.raises(ValueError, match="No active"):
                monitor.end_phase()
            monitor.begin_phase("evaluation")
            monitor.end_phase()
        result = monitor.result()
        assert result["owned_process_tree_peak_rss_bytes"] >= phase["owned_process_tree_peak_rss_bytes"]
        assert [p["phase"] for p in result["phases"]] == ["solver", "evaluation"]
        assert result["monitor_status"] == "PASS"
        samples = [json.loads(line) for line in path.read_text().splitlines()]
        assert any(s["phase"] == "solver" and s["owned_process_count"] == 2 for s in samples)
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.communicate(timeout=3)


@pytest.mark.skipif(shutil.which("strace") is None, reason="strace unavailable for infrastructure fixture")
def test_failed_evaluator_child_retains_real_rss_and_wall(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean5_sequence import evaluation_process
    evaluator = tmp_path / "infrastructure_fixture.py"
    evaluator.write_text("import time\nx=bytearray(4*1024*1024)\ntime.sleep(.04)\nraise SystemExit(7)\n")
    monkeypatch.setattr(evaluation_process, "EVALUATOR_SHA256", sha256_file(evaluator))
    raw = tmp_path / "synthetic_inputs"
    raw.mkdir()
    trace = raw / "trace.csv"
    nav, std = tmp_path / "NAV.fixture", tmp_path / "STD.fixture"
    for path in (trace, nav, std):
        path.write_text("synthetic infrastructure fixture; never scientific evidence\n")
    output = tmp_path / "out"
    with pytest.raises(RuntimeError, match="evaluator_returncode=7"):
        evaluation_process.evaluate(evaluator=evaluator, trace=trace, nav=nav, std=std, outdir=output,
            base_time=0, window=[0, 1], trace_sha256=sha256_file(trace), code_root=tmp_path,
            raw_root=raw, clean_root=tmp_path, instrument=False,
            consistency_policy="canonical_v2_wgs84_full_support", measure_resources=True)
    measurement = json.loads((output / "EVALUATOR_RESOURCE_MEASUREMENT.json").read_text())
    assert measurement["status"] == "AVAILABLE"
    assert measurement["exit_code"] == 7
    assert measurement["peak_rss_bytes"] >= 4*1024*1024
    assert measurement["evaluation_runtime_seconds"] >= .04
    assert not (output / "summary.json").exists()


def test_resource_measurement_cannot_change_legacy_default_policy(tmp_path):
    from legsa_gins.paper_rebuild.clean5_sequence.evaluation_process import evaluate
    with pytest.raises(ValueError, match="only enabled"):
        evaluate(evaluator="unopened", trace="unopened", nav="unopened", std="unopened",
                 outdir=tmp_path / "not_created", base_time=0, window=[0, 1],
                 trace_sha256="0"*64, code_root=tmp_path, raw_root=tmp_path, clean_root=tmp_path,
                 measure_resources=True)
    assert not (tmp_path / "not_created").exists()


def test_failed_evaluation_row_preserves_measurement_and_native_identity(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean6_canonical_v2 import evaluation
    native = tmp_path / "native"
    native.mkdir()
    (native / "KF_GINS_Navresult.nav").write_text("0 0 35 115 0 0 0 0 0 0 0\n0 1 35 115 0 0 0 0 0 0 0\n")
    (native / "KF_GINS_STD.txt").write_text("synthetic fixture; not consumed\n")
    (native / "RUN_MANIFEST.json").write_text("{}")
    files = {p.name: {"sha256": sha256_file(p), "size_bytes": p.stat().st_size} for p in native.iterdir()}
    (native / "OUTPUT_SEAL.json").write_text(json.dumps({"status": "SEALED_BEFORE_EVALUATION", "files": files}))
    measurement = {"status": "AVAILABLE", "peak_rss_bytes": 123456, "evaluation_runtime_seconds": 1.25}
    def failed_fixture(**kwargs):
        kwargs["outdir"].mkdir()
        (kwargs["outdir"] / "EVALUATOR_RESOURCE_MEASUREMENT.json").write_text(json.dumps(measurement))
        raise RuntimeError("infrastructure fixture failure after child measured")
    monkeypatch.setattr(evaluation, "evaluate", failed_fixture)
    record = {"run_id": "fixture", "case_id": "C00_clean_normal", "method_id": "F03", "dataset_id": "SYNTHETIC_TEST",
        "output_root": str(native), "terminal_status": "COMPLETED", "output_seal": files,
        "code_commit": "original_native", "validation_code_commit": "validation_fix",
        "validation_config_hash": "1"*64, "original_native_reused": True}
    contract = {"evaluation": {"window": [0., 1.], "base_time": 0.,
        "trace": {"path": str(tmp_path / "unopened"), "sha256": "0"*64},
        "evaluator": {"path": str(tmp_path / "unexecuted"), "sha256": evaluation.EVALUATOR_SHA256}}}
    from types import SimpleNamespace
    reg = SimpleNamespace(code_root=tmp_path, raw_root=tmp_path / "raw", clean_root=tmp_path)
    result = evaluation.one_evaluation(record, "v2", contract, reg, tmp_path, "new_evaluation")
    assert result["evaluation_status"] == "FAILED_EVALUATOR"
    assert result["evaluator_peak_rss_bytes"] == 123456
    assert result["evaluation_runtime_seconds"] == 1.25
    assert result["evaluator_resource_status"] == "AVAILABLE"
    assert result["native_execution_code_commit"] == "original_native"
    assert result["code_commit"] == "new_evaluation"
    assert result["validation_code_commit"] == "validation_fix"
    assert result["original_native_reused"] is True


def test_validation_sidecars_archived_without_becoming_cleanup_inputs(tmp_path):
    import gzip
    from legsa_gins.paper_rebuild.clean6_canonical_v2.storage import retain_run
    native = tmp_path / "scratch" / "run"
    native.mkdir(parents=True)
    (native / "KF_GINS_Navresult.nav").write_text("0 0 35 115 0 0 0 0 0 0 0\n0 1 35 115 0 0 0 0 0 0 0\n")
    for name in ("RUN_MANIFEST.json", "OUTPUT_SEAL.json"):
        (native / name).write_text("{}")
    (native / "PORT_GNSS_UPDATE_TRACE.csv").write_text("fixture\n")
    original_stage = tmp_path / "original_stage"
    original_stage.mkdir()
    validation = original_stage / "validation.json"
    config = original_stage / "config.yaml"
    validation.write_text('{"status":"VALIDATED_EXISTING_NATIVE_OUTPUT"}')
    config.write_text("fixture: never_scientific\n")
    record = {"output_root": str(native), "terminal_status": "COMPLETED", "run_id": "fixture", "dataset_id": "SYNTHETIC_TEST",
        "code_commit": "original_native", "validation_code_commit": "validation_fix", "continuation_code_commit": "continuation",
        "original_terminal_status": "FAILED_TECHNICAL", "original_native_reused": True,
        "validation_record_path": str(validation), "validation_record_sha256": sha256_file(validation),
        "validation_config_path": str(config), "validation_config_hash": sha256_file(config)}
    roots = {}
    for version in ("v3", "v2"):
        root = tmp_path / version
        evaluator = root / "FROZEN_EVALUATOR"
        evaluator.mkdir(parents=True)
        (evaluator / "summary.json").write_text("{}")
        with gzip.open(evaluator / "error_series.csv.gz", "wb") as stream:
            stream.write(b"synthetic fixture\n")
        roots[version] = root
    archive = tmp_path / "archive"
    receipt = retain_run(record, roots, archive)
    assert validation.is_file() and config.is_file()
    assert (archive / "validation/VALIDATION_RECORD.json").read_bytes() == validation.read_bytes()
    assert (archive / "validation/VALIDATION_CONFIG.yaml").read_bytes() == config.read_bytes()
    assert set(receipt["original_files"]) == {"solver", "v3", "v2"}
    assert all("validation" not in name.lower() for files in receipt["original_files"].values() for name in files)
    wrapper = json.loads((archive / "RUN_MANIFEST.json").read_text())
    assert wrapper["original_native_code_commit"] == "original_native"
    assert wrapper["continuation_code_commit"] == "continuation"
    assert wrapper["validation_code_commit"] == "validation_fix"
    assert wrapper["original_terminal_status"] == "FAILED_TECHNICAL"
    assert wrapper["validation_record_relative_path"] == "validation/VALIDATION_RECORD.json"
    assert wrapper["validation_record_sha256"] == sha256_file(validation)


def test_sampler_failure_blocks_phase_result_and_preserves_original_exception(tmp_path):
    with pytest.raises(LookupError, match="original operation failure"):
        with ResourceMonitor(tmp_path, tmp_path, tmp_path / "samples.jsonl") as monitor:
            monitor.begin_phase("solver")
            monitor.monitor_failure = OSError("simulated sampling failure")
            for boundary in (monitor.assert_healthy, monitor.end_phase, monitor.result):
                with pytest.raises(RuntimeError, match="preserve scene") as caught:
                    boundary()
                assert isinstance(caught.value.__cause__, OSError)
            with pytest.raises(RuntimeError, match="preserve scene"):
                monitor.begin_phase("evaluation")
            raise LookupError("original operation failure")
