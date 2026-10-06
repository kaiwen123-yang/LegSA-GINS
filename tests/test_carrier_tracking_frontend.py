"""Causal owner policy and preservation of saved acquisition schema."""
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass
import importlib.util
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts/paper_rebuild/carrier_phase"
sys.path.insert(0,str(SCRIPTS))
# During staging the script is beside this test; installed tests use SCRIPTS.
SCRIPT=Path(__file__).with_name("tracking_frontend.py")
if not SCRIPT.exists(): SCRIPT=SCRIPTS/"tracking_frontend.py"
spec=importlib.util.spec_from_file_location("tracking_frontend_under_test",SCRIPT)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
from legsa_gins.paper_rebuild.carrier_phase.measurement import unavailable_measurement

@dataclass
class Step:
    terminal: bool
    measurement: object
    status: str="test"

class FakeTrack:
    def __init__(self,name,terminal=False):
        self.origin_id=name;self.terminal=terminal;self.calls=[]
    def observe(self,model,*,availability_time_s):
        self.calls.append(("observe",availability_time_s))
        return Step(self.terminal,unavailable_measurement(availability_time_s,"RELEASED" if self.terminal else "TRACK"))
    def missing(self,t,reason):
        self.calls.append(("missing",t))
        return Step(True,unavailable_measurement(t,reason))

def fresh(name,t,valid=True):
    return {"case_id":name,"status":"QUALIFIED" if valid else "REJECTED",
            "measurement":{"valid":valid,"decision_available_time":t}}

def starter(seen):
    def f(record):
        seen.append(record["case_id"])
        return FakeTrack(record["case_id"]),unavailable_measurement(
            record["measurement"]["decision_available_time"],"ORIGIN")
    return f

def test_incumbent_owns_even_release_epoch_no_same_epoch_replacement_or_queue():
    owner=mod.EpochOwner();old=FakeTrack("old",terminal=True);owner.track=old;started=[]
    out,event=owner.advance(2.,object(),[fresh("new",2.)],starter(started))
    assert out.status=="RELEASED" and owner.track is None
    assert event["suppressed_valid_origins"]==["new"] and started==[]
    assert old.calls==[("observe",2.)]
    out,event=owner.advance(2.2,object(),[],starter(started))
    assert event["event"]=="INACTIVE" and started==[]
    with pytest.raises(ValueError,match="exact epoch"):
        owner.advance(2.4,object(),[fresh("new",2.)],starter(started))

def test_initial_output_once_and_origin_never_resurrected():
    owner=mod.EpochOwner();started=[]
    _,event=owner.advance(1.,object(),[fresh("first",1.)],starter(started))
    assert event["event"]=="TRACK_STARTED" and started==["first"]
    owner.track.terminal=True
    _,event=owner.advance(1.2,object(),[],starter(started))
    assert event["event"]=="TRACK_RELEASED"
    with pytest.raises(ValueError,match="resurrected"):
        owner.advance(1.4,object(),[fresh("first",1.4)],starter(started))

def test_missing_model_releases_without_accessing_new_candidate():
    owner=mod.EpochOwner();old=FakeTrack("old");owner.track=old;started=[]
    _,event=owner.advance(1.2,None,[fresh("new",1.2)],starter(started),missing_reason="GAP")
    assert event["event"]=="TRACK_RELEASED" and owner.track is None
    assert old.calls==[("missing",1.2)] and started==[]

def test_rejected_acquisition_does_not_start_and_multiple_fresh_fail_closed():
    owner=mod.EpochOwner();started=[]
    out,event=owner.advance(1.,object(),[fresh("bad",1.,False)],starter(started))
    assert event["event"]=="INACTIVE" and out.status=="REJECTED" and not started
    with pytest.raises(ValueError,match="ambiguous"):
        owner.advance(1.2,object(),[fresh("a",1.2),fresh("b",1.2)],starter(started))

def plan_and_summary():
    rows=[{"time_s":100.198+.2*k} for k in range(20)]
    summary={"attempted_case_ids":["full_0100.00","partial_0100.00","full_0102.00","partial_0102.00"],
             "modes":{"full":{"cases":2},"partial":{"cases":2}}}
    return {"records":rows},summary

def test_schedule_uses_final_future_epoch_and_actual_original_selection_time():
    plan,summary=plan_and_summary()
    result=mod.acquisition_schedule(summary,plan,"partial")
    assert result=={plan["records"][9]["time_s"]:("partial_0100.00",plan["records"][4]["time_s"]),
                    plan["records"][19]["time_s"]:("partial_0102.00",plan["records"][14]["time_s"])}

@pytest.mark.parametrize("kind",["duplicate","order","missing","count"])
def test_schedule_rejects_partial_or_ambiguous_saved_domain(kind):
    plan,summary=plan_and_summary()
    if kind=="duplicate":summary["attempted_case_ids"].append("partial_0100.00")
    if kind=="order":plan["records"][1]=dict(plan["records"][0])
    if kind=="missing":plan["records"].pop()
    if kind=="count":summary["modes"]["partial"]["cases"]=1
    with pytest.raises(ValueError):mod.acquisition_schedule(summary,plan,"partial")

def test_saved_origin_roundtrip_preserves_selected_time_integers_and_bound_diagnosis():
    fixture_path=ROOT/"tests/paper_rebuild/test_carrier_measurement.py"
    fixture_spec=importlib.util.spec_from_file_location("synthetic_measurement_fixture",fixture_path)
    helper=importlib.util.module_from_spec(fixture_spec);fixture_spec.loader.exec_module(helper)
    models,pair,admission,diagnosis=helper.fixture(partial=True)
    measurement=helper.call(models,pair,admission,diagnosis)
    saved=mod.serial({"frozen_candidates":pair,"admission":admission,
                      "phase_diagnosis":diagnosis,"measurement":measurement})
    restored=mod.restored_origin(saved)
    assert mod.serial(restored)==mod.serial((pair,admission,diagnosis,measurement))
    assert [x.fingerprint for x in restored[0]]==[x.fingerprint for x in pair]
    assert helper.call(models,restored[0],restored[1],restored[2])==measurement
