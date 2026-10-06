"""Independent scheduling oracle; no raw models, C-ILS, native or evaluator."""
from pathlib import Path
import importlib.util
import random
import sys
from types import SimpleNamespace as NS
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("latency_review_target",ROOT/"scripts/paper_rebuild/carrier_phase/latency_tracking_frontend.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

def job(cid,ready,duration,validation=None):
    return m.RecordedJob(cid,ready,tuple(validation or [ready+i*.2 for i in range(1,6)]),duration)

def measurement(t,valid=True,status="TEST"):
    return NS(measurement_time=t,decision_available_time=t,valid=valid,status=status)

def unavailable(t,reason):
    return measurement(t,False,reason)

class ToyTrack:
    def __init__(self,oid="toy",terminal_at=None):
        self.origin_id=oid
        self.terminal_at=terminal_at
        self.visited=[]
    def observe(self,model,*,availability_time_s):
        self.visited.append(model.time_s)
        assert availability_time_s==model.time_s
        terminal=model.time_s==self.terminal_at
        return NS(terminal=terminal,measurement=measurement(model.time_s,not terminal,"DEAD" if terminal else "OK"),receipt=None)
    def missing(self,t,reason):
        self.visited.append(t)
        return NS(terminal=True,measurement=measurement(t,False,"MISSING"),receipt=None)

def test_random_serial_schedule_matches_independent_interval_oracle():
    rng=random.Random(884216)
    for _ in range(200):
        jobs=[job(str(i),i*2.,rng.choice([0.,.01,.4,1.,2.,2.000000000001,3.9,11.3,100.])) for i in range(25)]
        free=-float("inf")
        launched=[]
        expected_actions={}
        for j in jobs:
            starts=j.selected_at>=free
            expected_actions[j.case_id]="SEARCH_LAUNCHED" if starts else "BUSY_DROP_NO_QUEUE"
            if starts:
                free=j.selected_at+j.elapsed_s
                launched.append(j)
        raw=[i/5. for i in range(301)]
        expected={}
        for j in launched:
            available=max(j.selected_at+j.elapsed_s,j.validation_times[-1])
            t=next((t for t in raw if t>=available),None)
            if t is not None:expected.setdefault(t,[]).append(j)
        for batch in expected.values():
            batch.sort(key=lambda j:(j.completion,j.selected_at,j.case_id))
        service=m.SerialService()
        by_time={j.selected_at:j for j in jobs}
        actual=[]
        for t in raw:
            if t in by_time:
                rec=service.offer(by_time[t],t)
                assert rec["action"]==expected_actions[by_time[t].case_id]
            arrivals=service.arrivals(t)
            assert [j.case_id for j in arrivals]==[j.case_id for j in expected.get(t,[])]
            actual.extend(j.case_id for j in arrivals)
        assert len(actual)==len(set(actual))
        assert {j.case_id for j in service.pending}=={j.case_id for j in launched}-set(actual)

def test_busy_ends_at_completion_not_at_validation_or_raw_rounding():
    s=m.SerialService()
    first=job("a",0.,.25,[10.,11.,12.,13.,14.])
    assert s.offer(first,0.)["action"]=="SEARCH_LAUNCHED"
    assert s.offer(job("b",.25,.1),.25)["action"]=="SEARCH_LAUNCHED"
    assert s.arrivals(1.)==[]
    assert [x.case_id for x in s.arrivals(1.25)]==["b"]
    assert [x.case_id for x in s.arrivals(14.)]==["a"]

def test_strict_raw_availability_does_not_tolerate_early_publication():
    s=m.SerialService()
    j=job("late",0.,1.+1e-12)
    s.offer(j,0.)
    assert s.arrivals(1.)==[]
    assert s.arrivals(1.2)==[j]

def test_catchup_missing_epoch_kills_origin_before_current_without_resurrection():
    j=job("a",0.,1.5)
    times=list(j.validation_times)+[1.2,1.4,1.6]
    history=[(t,None if t==1.4 else NS(time_s=t),"missing" if t==1.4 else None) for t in times]
    track=ToyTrack()
    record={"measurement":{"valid":True},"status":"QUALIFIED"}
    def start(rec,models):
        assert [x.time_s for x in models]==list(j.validation_times)
        return track,measurement(j.validation_end)
    result=m.catch_up(j,1.6,history,record,start)
    assert result.track is None and result.status=="CATCHUP_DEAD:MISSING"
    assert track.visited==[1.2,1.4]
    assert result.history[-1]["model_time_s"]==1.4
    assert result.history[-1]["processed_at_simulation_time_s"]==1.6
    assert result.history[-1]["action"]=="INTERNAL_CATCHUP_NOT_EXPORTED"

def test_catchup_live_exports_only_current_measurement():
    j=job("a",0.,1.5)
    history=[(t,NS(time_s=t),None) for t in list(j.validation_times)+[1.2,1.4,1.6]]
    track=ToyTrack()
    result=m.catch_up(j,1.6,history,{"measurement":{"valid":True},"status":"QUALIFIED"},
        lambda rec,models:(track,measurement(j.validation_end)))
    assert result.track is track
    assert result.measurement.measurement_time==result.measurement.decision_available_time==1.6
    assert track.visited==[1.2,1.4,1.6]
    assert all(h["processed_at_simulation_time_s"]==1.6 for h in result.history)

def test_catchup_unavailable_result_never_constructs_track():
    j=job("bad",0.,.5)
    def no_start(*args):
        raise AssertionError("unavailable origin must not be reconstructed")
    result=m.catch_up(j,1.,[],{"measurement":{"valid":False},"status":"UNCERTIFIED"},no_start)
    assert result.track is None and result.status.endswith("UNCERTIFIED")

def test_owner_failed_catchup_allows_next_then_permanently_suppresses_remaining():
    owner=m.AvailabilityOwner(unavailable)
    jobs=[job("a",0.,1.),job("b",.1,1.),job("c",.2,1.)]
    calls=[]
    def replay(j,t):
        calls.append(j.case_id)
        if j.case_id=="a":return m.CatchupResult(None,None,"CATCHUP_DEAD",[])
        track=ToyTrack(j.case_id)
        return m.CatchupResult(track,measurement(t),"AVAILABLE_CURRENT_CANDIDATE",[])
    obs,event=owner.advance(2.,NS(time_s=2.),list(reversed(jobs)),replay)
    assert calls==["a","b"] and obs.valid and owner.track.origin_id=="b"
    assert [a["action"] for a in event["arrival_actions"]]==["CATCHUP_DEAD","AVAILABLE_CURRENT_CANDIDATE","SUPPRESSED_AFTER_OWNER_ACQUIRED"]
    with pytest.raises(ValueError,match="resurrected"):
        owner.advance(2.2,NS(time_s=2.2),[jobs[2]],replay)

def test_incumbent_failure_epoch_excludes_even_a_viable_arrival():
    owner=m.AvailabilityOwner(unavailable)
    owner.track=ToyTrack("old",terminal_at=2.)
    def forbidden(*args):raise AssertionError("release epoch cannot transfer ownership")
    obs,event=owner.advance(2.,NS(time_s=2.),[job("new",.5,.2)],forbidden)
    assert not obs.valid and event["event"]=="TRACK_RELEASED" and owner.track is None
    assert event["arrival_actions"][0]["action"]=="SUPPRESSED_OWNER_AT_ENTRY"
    obs,event=owner.advance(2.2,NS(time_s=2.2),[],forbidden)
    assert not obs.valid and event["event"]=="INACTIVE"

@pytest.mark.parametrize("elapsed",[float("nan"),float("inf"),-1.])
def test_unknown_service_time_is_not_zero_cost(elapsed):
    with pytest.raises(ValueError):
        job("bad",0.,elapsed)
