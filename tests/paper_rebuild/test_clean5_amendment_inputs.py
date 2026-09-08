"""Synthetic C-04b orchestration tests; no real raw/event/solver execution."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.clean5_sequence import amendment_inputs as amendment
from legsa_gins.paper_rebuild.manifest import sha256_file


def _a4_fixture(tmp_path):
    root=tmp_path/"stages"/amendment.CONTROL_STAGE/"00_C04B_REVALIDATION_V2"
    root.mkdir(parents=True)
    commit="a"*40
    rows=[{"run_id":f"{dataset}_{method}_{profile}","passed":True,"terminal_status":"COMPLETED"}
          for dataset in ("BY2H","BY2O") for method,profile in amendment.METHODS.items()]
    result={"code_freeze_commit":commit,"passed":True,"expected_run_count":10,"passed_run_count":10,"runs":rows}
    result_path=root/"REVALIDATION_RESULT.json"
    result_path.write_text(json.dumps(result))
    gate={"status":"PASS","passed":True,"passed_run_count":10,"worker_exit_code":0,
          "strace_audit":{"pass":True},"code_freeze_commit":commit,"result_sha256":sha256_file(result_path)}
    gate_path=root/"REVALIDATION_GATE.json"
    gate_path.write_text(json.dumps(gate))
    return SimpleNamespace(clean_root=tmp_path),commit,gate_path,result_path,gate,result


def test_event_preparation_requires_complete_current_a4_gate(tmp_path):
    registry,commit,_,_,_,_= _a4_fixture(tmp_path)
    assert amendment.require_revalidation_gate(registry,commit)["passed_run_count"]==10
    with pytest.raises(RuntimeError,match="all ten"):
        amendment.require_revalidation_gate(registry,"b"*40)


@pytest.mark.parametrize("corruption",["failed_run","nine_rows","duplicate_id","result_hash","audit_failure"])
def test_incomplete_or_tampered_a4_gate_is_fail_closed(tmp_path,corruption):
    registry,commit,gate_path,result_path,gate,result=_a4_fixture(tmp_path)
    if corruption=="failed_run":result["runs"][0]["passed"]=False
    elif corruption=="nine_rows":result["runs"].pop()
    elif corruption=="duplicate_id":result["runs"][0]["run_id"]=result["runs"][1]["run_id"]
    elif corruption=="audit_failure":gate["strace_audit"]["pass"]=False
    result_path.write_text(json.dumps(result))
    if corruption!="result_hash":gate["result_sha256"]=sha256_file(result_path)
    else:gate["result_sha256"]="0"*64
    gate_path.write_text(json.dumps(gate))
    with pytest.raises(RuntimeError,match="all ten"):
        amendment.require_revalidation_gate(registry,commit)


def test_initialization_reuses_first_valid_position_and_fixed_a1_transform():
    positions=[{"sys_stamp.secs":100+t,"sys_stamp.nsecs":0,"pos_valid":valid,
                "pos_lat":lat,"pos_lon":2,"pos_height":3}
               for t,valid,lat in [(9,"true",1),(10,"false",100),(11,"true",4),(12,"true",5)]]
    yaw=[{"aligned_time":9.,"yaw_baseline_deg":0.},{"aligned_time":11.5,"yaw_baseline_deg":100.},
         {"aligned_time":12.,"yaw_baseline_deg":90.}]
    result=amendment.select_initialization(positions,yaw,base_time=100,t_start=10)
    assert result["position_epoch_R1"]==11
    assert result["initpos"]==[4.,2.,3.]
    assert result["yaw_epoch_R1"]==11.5
    assert result["initatt"]==[0,0,350.]
    assert result["yaw_wrap180_equivalent_deg"]==-10.
    assert result["initvel"]==[0,0,0]


def test_initialization_missing_source_is_not_substituted():
    with pytest.raises(RuntimeError,match="No valid first"):
        amendment.select_initialization([],[],base_time=0,t_start=10)


def test_initialization_patch_matches_contract_v2_allowed_fields(tmp_path,monkeypatch):
    (tmp_path/"gnss1-status.csv").write_text(
        "sys_stamp.secs,sys_stamp.nsecs,pos_valid,pos_lat,pos_lon,pos_height\n"
        "111,0,true,4,2,3\n")
    monkeypatch.setattr(amendment.providers,"build_a1_dual_diff_yaw_rows",
        lambda *_,**__:([{"aligned_time":11.5,"yaw_baseline_deg":100.}],{"synthetic_test":True}))
    result=amendment.prepare_initialization(SimpleNamespace(fix_root=tmp_path),
        contract={"initialization_contract":{"initvel":[0,0,0],"initatt":[0,0,1]}},
        base_time=100,t_start=10)
    assert set(result)=={"initpos","initatt","position_epoch_R1","yaw_epoch_R1",
        "yaw_ned_deg_0_360","yaw_wrap180_equivalent_deg","source_provenance"}
    assert result["source_provenance"]["provider_files_written"]==0
    assert result["source_provenance"]["physical_a1_row_count"]==1
    assert result["initatt"]==[0,0,350.]


def test_requested_411_413_interval_retains_full_actual_gap():
    gap={"t_start":407.017058,"t_end":413.041069,"duration_seconds":6.024011}
    report={"imu_increment_holes":{"holes":[gap]},"raw_go2_holes":{"holes":[]}}
    event={"candidate_v2_window":{"t_start":414.,"t_end":683.}}
    result=amendment.requested_gap_relation(report,event,"BY2H")
    match=result["source_gaps"]["imu_increment_holes"][0]
    assert match["full_observed_gap"]["t_start"]==407.017058
    assert match["overlap_with_requested_411_413_seconds"]==2.
    assert match["v2_start_at_or_after_gap_end"] is True
    assert result["used_to_adjust_window"] is False


def test_event_audit_allows_only_admitted_raw_reads_and_explicit_writes(tmp_path):
    raw,code,clean=(tmp_path/name for name in ("raw","code","clean"))
    for root in (raw,code,clean):root.mkdir()
    stage=clean/"stage";diag=stage/"06_ALIGNMENT_DIAGNOSTICS"
    diag.mkdir(parents=True)
    body=raw/"body.txt";body.write_text("synthetic")
    seq=SimpleNamespace(body_path=body,fix_root=raw)
    prepared={"stage":stage,"sequence":seq,"lock":{"rows":{}}}
    registry=SimpleNamespace(raw_root=raw,clean_root=clean,code_root=code)
    log=diag/"synthetic.strace"
    log.write_text(f'1 openat(AT_FDCWD, "{body}", O_RDONLY) = 3\n'
                   f'1 openat(AT_FDCWD, "{diag / "diag.json"}", O_WRONLY|O_CREAT, 0666) = 4\n'
                   '1 openat(AT_FDCWD, "/dev/null", O_WRONLY) = 5\n')
    audit=amendment.phase_audit(log,registry=registry,dataset="BY2H",phase="events",prepared=prepared)
    assert audit["pass"] and audit["raw_open_count"]==1
    with log.open("a") as handle:
        handle.write(f'1 openat(AT_FDCWD, "{stage / "02_PROVIDER_FREEZE/changed"}", O_WRONLY|O_CREAT, 0666) = 4\n')
    assert not amendment.phase_audit(log,registry=registry,dataset="BY2H",phase="events",prepared=prepared)["pass"]


def test_event_trace_open_fails_even_when_read_only(tmp_path):
    raw,code,stage=(tmp_path/name for name in ("raw","code","stage"))
    for root in (raw,code,stage):root.mkdir()
    log=stage/"synthetic.strace"
    log.write_text(f'1 openat(AT_FDCWD, "{raw / "trace_synthetic.csv"}", O_RDONLY) = 3\n')
    seq=SimpleNamespace(body_path=raw/"body.txt",fix_root=raw)
    registry=SimpleNamespace(raw_root=raw,clean_root=stage,code_root=code)
    audit=amendment.phase_audit(log,registry=registry,dataset="BY2H",phase="events",
                               prepared={"stage":stage,"sequence":seq,"lock":{"rows":{}}})
    assert not audit["pass"] and audit["forbidden_open_counts"]["trace"]==1


def test_stop_at_first_failed_event_and_do_not_prepare_later_sequences(tmp_path,monkeypatch):
    control=tmp_path/"control"
    (control/"06_ALIGNMENT_DIAGNOSTICS").mkdir(parents=True)
    calls=[]
    def prepare(args,registry,dataset,state,a4):
        calls.append(dataset)
        return {"dataset_id":dataset,"passed":dataset=="BY2"}
    monkeypatch.setattr(amendment,"prepare_sequence",prepare)
    monkeypatch.setattr(amendment,"stage_root",lambda *_:control)
    assert amendment.prepare_all(SimpleNamespace(),SimpleNamespace(),{}, {})==3
    assert calls==["BY2","BY2H"]
    gate=json.loads((control/"06_ALIGNMENT_DIAGNOSTICS/B_C_PREPARATION_GATE.json").read_text())
    assert gate["not_executed_sequences"]==["BY2O"]
    assert gate["contracts_written"]==0


def test_post_checkpoint_runs_after_event_worker_nonzero(tmp_path,monkeypatch):
    stage=tmp_path/"stage";stage.mkdir()
    prepared={"stage":stage,"lock":{},"provenance":{},"provider_checks":{}}
    monkeypatch.setattr(amendment,"metadata_inputs",lambda *_:prepared)
    monkeypatch.setattr(amendment,"validate_checkpoint",lambda *_,**__:None)
    monkeypatch.setattr(amendment,"_published_source",lambda *_:{})
    monkeypatch.setattr(amendment,"verify_executable",lambda *_:{})
    monkeypatch.setattr(amendment,"_read",lambda *_:{"verified_hashes":{}})
    phases=[]
    def phase(args,registry,dataset,phase,prepared):
        phases.append(phase)
        return {"pass":phase!="events","worker_exit_code":2 if phase=="events" else 0}
    monkeypatch.setattr(amendment,"run_phase",phase)
    state={"frozen_executable":{"path":"synthetic"}}
    gate=amendment.prepare_sequence(SimpleNamespace(),SimpleNamespace(code_root=tmp_path),"BY2",state,{})
    assert phases==["pre_event","events","post_event"]
    assert not gate["passed"]
    assert (stage/"06_ALIGNMENT_DIAGNOSTICS/00_AUDIT/EVENT_PHASE_GATE.json").is_file()


def test_failed_motion_gate_still_writes_event_and_diagnostics_without_initialization(tmp_path,monkeypatch):
    stage=tmp_path/"stage";diag=stage/"06_ALIGNMENT_DIAGNOSTICS"
    (diag/"00_AUDIT").mkdir(parents=True)
    (stage/"01_SEQUENCE_CONTRACT").mkdir()
    seq=SimpleNamespace(data_mode="synthetic_test",body_path=tmp_path/"unused-body.txt")
    prepared={"stage":stage,"sequence":seq,"lock":{},"provenance":{},"base_time":0.,
              "contract":{"window_contract":{"t_start":11.,"t_end":40.}},
              "common_coverage":{"first":1.,"last":49.3},"occlusion_window":None,
              "provider_manifest":{"artifacts":{role:{"path":"synthetic-only"} for role in
                  ("gnss_runtime_input","go2_horizontal_velocity_prior","imu_runtime_input")}}}
    monkeypatch.setattr(amendment,"metadata_inputs",lambda *_:prepared)
    monkeypatch.setattr(amendment,"validate_checkpoint",lambda *_,**__:None)
    monkeypatch.setattr(amendment,"_read",lambda *_:{"pass":True})
    speeds={"gnss_times":list(range(50)),"gnss_speeds":[.3 if t>=10 else 0. for t in range(50)],
            "body_times":[i/10 for i in range(501)],"body_speeds":[.3 if i>=150 else 0. for i in range(501)]}
    monkeypatch.setattr(amendment.event_window,"load_speed_inputs",lambda *_:speeds)
    monkeypatch.setattr(amendment.event_window,"detect_kick_report",lambda *_,**__:{"status":"NOT_DETECTED","kick_time_R1":None})
    monkeypatch.setattr(amendment.diagnostics,"read_imu_increment_times",lambda *_:[i/100 for i in range(5001)])
    monkeypatch.setattr(amendment.diagnostics,"read_raw_go2_times",lambda *_,**__:[i/100 for i in range(5001)])
    monkeypatch.setattr(amendment,"prepare_initialization",lambda *_,**__:pytest.fail("Initialization must not run after a failed event gate"))
    result=amendment.event_worker(SimpleNamespace(code_freeze_commit="synthetic"),SimpleNamespace(),"BY2H",{}, {})
    assert result["status"]=="CLOCK_OFFSET_SUSPECTED"
    assert result["initialization_v2"] is None
    event=json.loads((stage/"01_SEQUENCE_CONTRACT/EVENT_WINDOW_V2.json").read_text())
    assert event["ready_for_v2_contract"] is False
    assert (diag/"ALIGNMENT_DIAGNOSTICS.json").is_file()
    assert (diag/"ALIGNMENT_DIAGNOSTICS.md").read_text().splitlines()[0]==amendment.diagnostics.REPORT_FIRST_LINE
