"""Synthetic tests for immutable A4 reuse; no real inputs are read."""
import subprocess
import pytest
from legsa_gins.paper_rebuild.clean5_sequence import a4_reuse
from legsa_gins.paper_rebuild.clean5_sequence.event_attempt import event_locations


def test_a4_changed_source_refuses_reuse(tmp_path,monkeypatch):
    path = tmp_path/"validator.py"
    path.write_bytes(b"old valid source\n")
    monkeypatch.setattr(subprocess,"check_output",lambda *args,**kwargs:b"old valid source\n")
    assert a4_reuse.verify_source_files(tmp_path,{"validator.py"})
    path.write_bytes(b"changed counter rule\n")
    with pytest.raises(RuntimeError,match="validation dependency changed"):
        a4_reuse.verify_source_files(tmp_path,{"validator.py"})


def test_event_attempt_identity_is_full_commit_and_non_overlapping(tmp_path):
    first = event_locations(tmp_path,"a"*40)
    second = event_locations(tmp_path,"b"*40)
    assert first["event"] != second["event"]
    assert first["diagnostics"] != second["diagnostics"]
    assert first["event"].parent != tmp_path/"01_SEQUENCE_CONTRACT"
    for bad in ("../escape","a"*12,"a"*39+"/"):
        with pytest.raises(ValueError,match="full committed"):
            event_locations(tmp_path,bad)


def test_tampered_pinned_a4_gate_is_rejected_before_dependency_use(tmp_path):
    from types import SimpleNamespace
    root = tmp_path/"stages/CLEAN5_BY2_CONTROL_PROVIDER_PARITY/00_C04B_REVALIDATION_V2"
    root.mkdir(parents=True)
    (root/"REVALIDATION_GATE.json").write_text('{"passed":true}')
    with pytest.raises(RuntimeError,match="Pinned A.4 evidence changed"):
        a4_reuse.reuse_gate(SimpleNamespace(clean_root=tmp_path),"b"*40)
