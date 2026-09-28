"""Synthetic phase-gate tests; no real frozen attempt or source reads."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.clean5_sequence import revalidation as mod


def test_skipped_epochs_never_reduce_expected_count(tmp_path):
    (tmp_path / "PORT_GNSS_UPDATE_TRACE.csv").write_text(
        "gnss_time,position_update\n413.203355000,1\n414.200000000,1\n")
    expected = [411.211805, 412.203561, 413.203355, 414.2]
    result = mod.skipped_update_epochs(tmp_path, expected)
    assert result["eligible_but_not_position_updated_epochs"] == expected[:2]
    assert result["applied_position_epoch_count"] == 2
    assert result["changes_expected_count"] is False
    assert len(expected) == 4


def test_absent_update_diagnostic_is_unavailable(tmp_path):
    assert mod.skipped_update_epochs(tmp_path, [1.0])["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("passed_count,declared_pass,audit_pass,expected_markers", [
    (5, False, True, False), (5, True, True, False),
    (10, True, False, False), (10, True, True, True),
])
def test_superseded_requires_all_ten_and_zero_open_audit(tmp_path, monkeypatch,
        passed_count, declared_pass, audit_pass, expected_markers):
    code, clean = tmp_path / "code", tmp_path / "clean"
    code.mkdir()
    control = clean / "stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY"
    control.mkdir(parents=True)
    seqs = {dataset: SimpleNamespace(stage_id=dataset) for dataset in ("BY2H", "BY2O")}
    preserved = []
    for sequence in seqs.values():
        for name in ("04_SOLVER_RUNS", "05_OUTPUT_SEAL"):
            old = clean / "stages" / sequence.stage_id / name / "old_terminal.json"
            old.parent.mkdir(parents=True)
            old.write_text('{"terminal_status":"counter_mismatch"}\n')
            preserved.append((old, old.read_bytes()))
    registry = SimpleNamespace(code_root=code, clean_root=clean, raw_root=tmp_path / "raw", sequences=seqs)
    monkeypatch.setattr(mod, "load_registry", lambda *_: registry)
    monkeypatch.setattr(mod, "_published_source", lambda *_: {"code_freeze_commit": "a" * 40})
    monkeypatch.setattr(mod, "verify_executable", lambda *_: {})
    monkeypatch.setattr(mod.shutil, "which", lambda *_: "/synthetic/strace")
    monkeypatch.setattr(mod, "audit_solver_openat", lambda *_ , **__: {"pass": audit_pass})
    commands = []
    def fake_process(command, **kwargs):
        commands.append(command)
        result = {"passed": declared_pass, "expected_run_count": 10, "passed_run_count": passed_count,
            "runs": [{"passed": index < passed_count} for index in range(10)]}
        (control / "00_C04B_REVALIDATION_V2/REVALIDATION_RESULT.json").write_text(json.dumps(result))
        return SimpleNamespace(returncode=0, stdout="synthetic revalidation\n", stderr="")
    monkeypatch.setattr(mod, "run_process_group", fake_process)
    args = ["--phase", "revalidate", "--paths-config", str(code / "local.yaml"),
            "--code-root", str(code), "--code-freeze-commit", "a" * 40,
            "--executable", str(code / "frozen")]
    assert mod.main(args) == (0 if expected_markers else 3)
    assert len(commands) == 1 and "--_revalidation-worker" in commands[0]
    for old, content in preserved:
        assert old.read_bytes() == content
        marker = old.parent / "SUPERSEDED.json"
        assert marker.exists() == expected_markers
        if expected_markers:
            value = json.loads(marker.read_text())
            assert value["status"] == "SUPERSEDED_NOT_EVALUATED"
            assert value["amended_before_unblinding"] is True
            assert value["trace_opened"] is False
    gate = json.loads((control / "00_C04B_REVALIDATION_V2/REVALIDATION_GATE.json").read_text())
    assert gate["stop_before_event_window_and_contract_v2"] == (not expected_markers)
    with pytest.raises(FileExistsError):
        mod.main(args)
    assert len(commands) == 1
