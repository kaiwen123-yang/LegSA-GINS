"""Synthetic byte-preservation and amended-event integrity gates."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml
from legsa_gins.paper_rebuild.clean5_sequence import contract_v2 as contract
from legsa_gins.paper_rebuild.clean5_sequence import runtime_v2 as runtime
from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.clean5_sequence.event_attempt import event_locations

EVENT_COMMIT = "b" * 40

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
        "kick": {"status": "NOT_DETECTED"}, "t_on_g": 10.2, "t_on_b": 10.4,
        "delta_t_onset_ms": None,
        "event_report_relative_path": event_locations(Path("."),EVENT_COMMIT)["event"].as_posix(),
        "event_attempt": event_locations(Path("."),EVENT_COMMIT)["attempt"],
        "onset_censored_b": True, "onset_censored_g": False,
        "body_onset_interval_R1": [8.0,10.4], "gnss_onset_interval_R1": [10.2,10.2],
        "delta_t_onset_interval_ms": [-200.0,2200.0],
        "clock_consistency_gate": {"basis":"full_coverage_xcorr","passed":True,"offset_applied_seconds":0.0},
        "xcorr_gate": {"passed":True,"primary_abs_lag_seconds":0.2,"role":"censored_onset_fallback"},
        "propagation_start_adjustment": {"unadjusted_start":10.0,"first_imu_time_at_or_after_start":12.4,
            "initialization_delay_seconds":2.4,"delay_limit_seconds":1.0,"adjusted":True,
            "adjusted_start":12.0,"rule":"delay >1 s => floor(t_init)"},
        "preserve_internal_dropout": [{"source":"raw_go2","t_start":20.0,"t_end":22.0,
            "preserved_without_interpolation_or_deletion":True}],
        "kick_dropout_hypothesis": {"status":"HYPOTHESIS_ONLY","kick_status":"NOT_DETECTED","used_to_select_window":False},
        "initialization_v2": {"initpos": [4,5,6], "initatt": [0,0,30],
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
        locations = event_locations(stage,EVENT_COMMIT)
        audit = locations["diagnostics"]/"00_AUDIT"; audit.mkdir(parents=True)
        event_path = locations["event"]; event_path.parent.mkdir(parents=True)
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
    (event_locations(runtime.stage_path(registry,"BY2"),EVENT_COMMIT)["diagnostics"]/"B_C_PREPARATION_GATE.json").write_text(json.dumps(joint))
    return registry

@pytest.mark.parametrize("corruption", ["event", "checkpoint", "gate"])
def test_event_chain_rejects_post_gate_mutation(event_gate_fixture, corruption):
    registry = event_gate_fixture
    assert len(runtime.event_inputs(registry,EVENT_COMMIT)) == 3
    stage = runtime.stage_path(registry,"BY2H")
    if corruption == "event":
        path = event_locations(stage,EVENT_COMMIT)["event"]
        data = json.loads(path.read_text()); data["unauthorized"] = True
    else:
        name = "pre_event_CHECKPOINT.json" if corruption == "checkpoint" else "EVENT_PHASE_GATE.json"
        path = event_locations(stage,EVENT_COMMIT)["diagnostics"]/"00_AUDIT"/name
        data = json.loads(path.read_text()); data["changed"] = True
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError, match="differ"):
        runtime.event_inputs(registry,EVENT_COMMIT)


def test_contract_records_censoring_shift_reason_and_report_identity():
    report=event()
    event_sha="d"*64
    text=contract.amend_contract(OLD,report,event_sha,EVENT_COMMIT)
    values=yaml.safe_load(text)
    window=values["window_contract"]
    for key in ("event_report_relative_path","event_attempt","onset_censored_b","onset_censored_g",
                "body_onset_interval_R1","gnss_onset_interval_R1","delta_t_onset_interval_ms",
                "clock_consistency_gate","xcorr_gate","propagation_start_adjustment",
                "preserve_internal_dropout","kick_dropout_hypothesis"):
        assert window[key]==report[key]
    assert window["delta_t_onset_ms"] is None
    assert window["propagation_start_adjustment"]["adjusted"] is True
    assert values["event_window_report_sha256"]==event_sha
    assert values["amendment_code_commit"]==EVENT_COMMIT
    assert "censored-onset fallback and IMU-availability shift" in values["amendment_reason"]
    assert event_sha in values["amendment_reason"]
    prefix,before=contract.sections(OLD)
    new_prefix,after=contract.sections(text)
    assert prefix==new_prefix
    for key in set(before)-contract.EDITED_SECTIONS:
        assert after[key]==before[key]
    assert "  initvel: [0, 0, 0]\n" in after["initialization_contract"]
    assert "  fixed_std: 0.1\n" in after["initialization_contract"]


def test_event_commit_prefix_collision_does_not_bypass_full_identity(event_gate_fixture):
    registry=event_gate_fixture
    other_commit=EVENT_COMMIT[:12]+"c"*28
    assert event_locations(runtime.stage_path(registry,"BY2"),other_commit)==event_locations(runtime.stage_path(registry,"BY2"),EVENT_COMMIT)
    with pytest.raises(RuntimeError,match="Joint event preparation gate"):
        runtime.event_inputs(registry,other_commit)


@pytest.mark.parametrize("mutation", ["old_event_path", "other_commit_path", "gate_full_commit"])
def test_event_commit_path_tamper_rejected_even_when_joint_gate_matches(event_gate_fixture,mutation):
    registry=event_gate_fixture
    stage=runtime.stage_path(registry,"BY2H")
    locations=event_locations(stage,EVENT_COMMIT)
    gate_path=locations["diagnostics"]/"00_AUDIT/EVENT_PHASE_GATE.json"
    gate=json.loads(gate_path.read_text())
    if mutation=="old_event_path":
        gate["event_path"]=str(stage/"01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json")
    elif mutation=="other_commit_path":
        gate["event_path"]=str(event_locations(stage,"c"*40)["event"])
    else:
        gate["code_freeze_commit"]="c"*40
    gate_path.write_text(json.dumps(gate))
    joint_path=event_locations(runtime.stage_path(registry,"BY2"),EVENT_COMMIT)["diagnostics"]/"B_C_PREPARATION_GATE.json"
    joint=json.loads(joint_path.read_text())
    joint["sequence_gates"][1]=gate
    joint_path.write_text(json.dumps(joint))
    with pytest.raises(RuntimeError,match="provenance or bytes differ"):
        runtime.event_inputs(registry,EVENT_COMMIT)
