"""Synthetic byte-preservation and amended-event integrity gates."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from legsa_gins.paper_rebuild.clean5_sequence import contract_v2 as contract
from legsa_gins.paper_rebuild.clean5_sequence import runtime_v2 as runtime
from legsa_gins.paper_rebuild.manifest import sha256_file

OLD = """# Synthetic contract
identity:
  dataset_id: BY2H
window_contract:
  rule: B_prime
  t_start: 10.0
  t_end: 40.0
initialization_contract:
  initvel: [0, 0, 0]
  initatt: [0, 0, 20]
  initpos: [1, 2, 3]
  fixed_std: 0.1
unchanged_section:
  quoted: 'preserve byte spelling' # preserve comment
"""

def event():
    return {"ready_for_v2_contract": True, "dataset_id": "BY2H",
        "v2_window": {"t_start": 12.0, "t_end": 40.0}, "constants": {"speed_threshold_mps": 0.15},
        "kick": {"status": "NOT_DETECTED"}, "t_on_g": 12.2, "t_on_b": 12.4,
        "delta_t_onset_ms": -200.0, "initialization_v2": {"initpos": [4,5,6], "initatt": [0,0,30],
            "position_epoch_R1": 12.3, "yaw_epoch_R1": 12.4, "yaw_ned_deg_0_360": 30,
            "yaw_wrap180_equivalent_deg": 30, "source_provenance": {"provider_files_written": 0}}}

def test_amendment_preserves_every_other_section_byte_exact():
    text = contract.amend_contract(OLD, event(), "a"*64, "b"*40)
    assert contract.validate_amendment(OLD, text)["passed"]
    _, before = contract.sections(OLD)
    _, after = contract.sections(text)
    assert before["unchanged_section"] == after["unchanged_section"]
    values = yaml.safe_load(text)
    assert values["initialization_contract"]["initpos"] == [4,5,6]
    assert values["initialization_contract"]["fixed_std"] == .1
    assert values["window_contract"]["v1_to_v2"]["t_start"] == {"v1":10., "v2":12.}
    with pytest.raises(ValueError, match="byte change"):
        contract.validate_amendment(OLD, text.replace("preserve comment", "modified comment"))

def test_failed_event_or_extra_initialization_parameter_cannot_amend():
    report = event(); report["ready_for_v2_contract"] = False
    with pytest.raises(ValueError, match="gate PASS"):
        contract.amend_contract(OLD, report, "a"*64, "b"*40)
    report = event(); report["initialization_v2"]["fixed_std"] = .2
    with pytest.raises(ValueError, match="unauthorized"):
        contract.amend_contract(OLD, report, "a"*64, "b"*40)

@pytest.fixture
def event_gate_fixture(tmp_path, monkeypatch):
    registry = SimpleNamespace(clean_root=tmp_path, sequences={ds:SimpleNamespace(stage_id=ds) for ds in ("BY2","BY2H","BY2O")})
    monkeypatch.setattr(runtime, "selected_lock", lambda *args: {})
    monkeypatch.setattr(runtime, "validate_checkpoint", lambda *args, **kwargs: None)
    gates = []
    for ds in ("BY2","BY2H","BY2O"):
        stage = runtime.stage_path(registry, ds)
        audit = stage/"06_ALIGNMENT_DIAGNOSTICS/00_AUDIT"; audit.mkdir(parents=True)
        event_path = stage/"01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json"; event_path.parent.mkdir()
        event_path.write_text(json.dumps({"dataset_id":ds,"ready_for_v2_contract":True}))
        checkpoint = {"verified_hashes":{"synthetic":"a"*64}}
        for phase in ("pre_event","post_event"):
            (audit/(phase+"_CHECKPOINT.json")).write_text(json.dumps(checkpoint))
        gate = {"passed":True,"dataset_id":ds,"code_freeze_commit":"b"*40,
            "event_path":str(event_path),"event_sha256":sha256_file(event_path),
            "pre_checkpoint":checkpoint,"post_checkpoint":checkpoint,
            **{phase+"_strace":{"pass":True} for phase in ("pre_event","event","post_event")}}
        (audit/"EVENT_PHASE_GATE.json").write_text(json.dumps(gate)); gates.append(gate)
    order = ["BY2","BY2H","BY2O"]
    joint = {"passed":True,"ready_for_contract_amendment":True,"sequence_order":order,
        "sequences_completed":order,"sequence_gates":gates,"code_freeze_commit":"b"*40}
    (runtime.stage_path(registry,"BY2")/"06_ALIGNMENT_DIAGNOSTICS/B_C_PREPARATION_GATE.json").write_text(json.dumps(joint))
    return registry

@pytest.mark.parametrize("corruption", ["event", "checkpoint", "gate"])
def test_event_chain_rejects_post_gate_mutation(event_gate_fixture, corruption):
    registry = event_gate_fixture
    assert len(runtime.event_inputs(registry)) == 3
    stage = runtime.stage_path(registry,"BY2H")
    if corruption == "event":
        path = stage/"01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json"
        data = json.loads(path.read_text()); data["unauthorized"] = True
    else:
        name = "pre_event_CHECKPOINT.json" if corruption == "checkpoint" else "EVENT_PHASE_GATE.json"
        path = stage/"06_ALIGNMENT_DIAGNOSTICS/00_AUDIT"/name
        data = json.loads(path.read_text()); data["changed"] = True
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError, match="differ"):
        runtime.event_inputs(registry)
