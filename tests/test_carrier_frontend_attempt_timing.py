"""Controller timing failures, synthetic only; no integer search or raw reads."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/paper_rebuild/carrier_phase"
sys.path.insert(0, str(SCRIPTS))
import integration_frontend as frontend


def test_search_attempt_timer_survives_exception(monkeypatch):
    clock = iter([10., 10.125])
    monkeypatch.setattr(frontend.time, "monotonic", lambda: next(clock))
    record = {"search_called": True}
    def fails():
        raise ValueError("synthetic solver failure")
    with pytest.raises(ValueError, match="synthetic solver failure"):
        frontend.timed_search_call(record, fails)
    assert record == {"search_called": True, "search_attempt_elapsed_s": .125}


def test_successful_attempt_does_not_replace_inner_certificate_clock(monkeypatch):
    clock = iter([10., 10.25])
    monkeypatch.setattr(frontend.time, "monotonic", lambda: next(clock))
    result = SimpleNamespace(certificate=SimpleNamespace(elapsed_s=.2))
    record = {"search_called": True}
    actual = frontend.timed_search_call(record, lambda: result)
    assert actual is result and result.certificate.elapsed_s == .2
    assert record["search_attempt_elapsed_s"] == .25


def test_explicit_preselection_failure_has_no_fake_search_timer(tmp_path, monkeypatch):
    trial = tmp_path/"trial";trial.mkdir()
    plan = {"baseline_length_m": .35, "records": [
        {"time_s": 100.198 + .2*i} for i in range(10)]}
    (trial/"PLAN.json").write_text(json.dumps(plan))
    output = tmp_path/"output"
    monkeypatch.setattr(frontend, "source_snapshot", lambda code: {})
    monkeypatch.setattr(frontend, "revision", lambda code: "synthetic-test")
    def unavailable(*args):
        raise ValueError("synthetic missing selection model")
    monkeypatch.setattr(frontend, "load_model", unavailable)
    args = SimpleNamespace(trial=trial,output=output,partial_max_ambiguities=6,
        starts=[100.],likelihood="original",modes=["partial"],sphere_library=None,
        code=Path(__file__).resolve().parents[1],family="GPS_GAL_BDS_DUAL",nodes=10,timeout=.1)
    frontend.run(args)
    record=json.loads((output/"cases/partial_0100.00.json").read_text())
    assert record["presearch_unavailable"] and not record["search_called"]
    assert "search_attempt_elapsed_s" not in record
    assert not record["measurement"]["valid"]
    assert "search" not in record
    assert json.loads((output/"SUMMARY_0001.json").read_text())["new_search_calls"] == 0
