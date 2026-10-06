"""Pure mock causal scheduling tests; no CILS, navigation or real measurements."""
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/"scripts/paper_rebuild/carrier_phase/latency_tracking_frontend.py"
spec = importlib.util.spec_from_file_location("latency_tracking_frontend_test_module",SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

@dataclass
class Measurement:
    measurement_time: float
    decision_available_time: float
    valid: bool
    status: str

def measurement(t, valid=True, status="PASS"):
    return Measurement(t,t,valid,status)

def unavailable(t,reason):
    return measurement(t,False,reason)

class FakeTrack:
    def __init__(self,name):
        self.origin_id=name
        self.calls=[]
        self.dead=False
    def observe(self,model,*,availability_time_s):
        assert not self.dead
        assert availability_time_s==model.time_s
        self.calls.append(("observe",model.time_s))
        self.dead=bool(getattr(model,"fail",False))
        return SimpleNamespace(terminal=self.dead,measurement=measurement(
            model.time_s,not self.dead,"RELEASED_TEST" if self.dead else "PASS"),receipt=None)
    def missing(self,t,reason):
        assert not self.dead
        self.calls.append(("missing",t))
        self.dead=True
        return SimpleNamespace(terminal=True,measurement=unavailable(t,"RELEASED_"+reason),receipt=None)

def job(name="a",selected=0.,elapsed=.1):
    return mod.RecordedJob(name,selected,tuple(selected+i*.2 for i in range(1,6)),elapsed)

def history(times,fail=None,missing=None):
    return [(t,None if t==missing else SimpleNamespace(time_s=t,fail=t==fail),
             "MODEL_MISSING" if t==missing else None) for t in times]

def record():
    return {"status":"QUALIFIED","measurement":{"valid":True},"frozen_N":[2,-3],"selected_at":0.}

def starter_sink(sink):
    def start(rec,models):
        sink["original_times"]=[m.time_s for m in models]
        sink["track"]=FakeTrack("origin")
        return sink["track"],measurement(models[-1].time_s)
    return start


def test_busy_drop_no_queue_and_exact_finish_boundary():
    worker=mod.SerialService()
    assert worker.offer(job("first",0,2),0)["action"]=="SEARCH_LAUNCHED"
    assert worker.offer(job("dropped",1,10),1)["action"]=="BUSY_DROP_NO_QUEUE"
    assert worker.offer(job("boundary",2,.1),2)["action"]=="SEARCH_LAUNCHED"
    assert [j.case_id for j in worker.arrivals(2)]==["first"]
    assert [j.case_id for j in worker.arrivals(3)]==["boundary"]
    assert worker.arrivals(100)==[]
    with pytest.raises(ValueError,match="repeated"):
        worker.offer(job("dropped",1,10),1)


def test_worker_free_on_completion_not_on_validation_or_raw_arrival():
    worker=mod.SerialService()
    first=job("first",0,.35)
    worker.offer(first,0)
    assert worker.arrivals(.4)==[]
    assert worker.offer(job("next",.5,.01),.5)["action"]=="SEARCH_LAUNCHED"
    assert worker.busy_until==.51
    assert [j.case_id for j in worker.arrivals(1)]==["first"]


def test_launch_ignores_result_status_and_rejected_job_consumes_cost():
    class PoisonJob(mod.RecordedJob):
        @property
        def valid(self): raise AssertionError("must not inspect validity")
        @property
        def status(self): raise AssertionError("must not inspect outcome")
    first=PoisonJob("uncertified",0,job().validation_times,3.)
    worker=mod.SerialService()
    assert worker.offer(first,0)["action"]=="SEARCH_LAUNCHED"
    assert worker.offer(job("next",2,.01),2)["action"]=="BUSY_DROP_NO_QUEUE"
    owner=mod.AvailabilityOwner(unavailable)
    seen=[]
    def reject(j,t):
        seen.append(j.case_id)
        return mod.CatchupResult(None,None,"ORIGINAL_RESULT_UNAVAILABLE:UNCERTIFIED",[])
    result,event=owner.advance(3,None,worker.arrivals(3),reject)
    assert not result.valid and seen==["uncertified"] and worker.busy_until==3


def test_not_before_completion_and_validation_and_no_end_clipping():
    worker=mod.SerialService()
    slow=job("slow",0,30)
    worker.offer(slow,0)
    assert worker.arrivals(10)==[] and worker.pending==[slow]
    assert worker.busy_until==30 and slow.available_after==30
    with pytest.raises(ValueError,match="before"):
        mod.AvailabilityOwner(unavailable).advance(1,None,[slow],None)


@pytest.mark.parametrize("elapsed",[-1.,float("nan"),float("inf")])
def test_bad_elapsed_is_never_zero_substituted(elapsed):
    with pytest.raises(ValueError):
        job(elapsed=elapsed)

def test_missing_elapsed_is_an_error():
    with pytest.raises(TypeError):
        mod.RecordedJob("missing",0.,job().validation_times)


def test_arrival_sort_completion_then_selected_at():
    owner=mod.AvailabilityOwner(unavailable)
    early=job("first",0,1.2)
    later=job("second",.2,1.)
    seen=[]
    def reject(j,t):
        seen.append(j.case_id)
        return mod.CatchupResult(None,None,"CATCHUP_DEAD",[])
    owner.advance(2,None,[later,early],reject)
    assert seen==["first","second"]


def test_late_alive_replays_history_and_exports_only_current_without_mutating_origin():
    j=job(elapsed=1.5)
    rec=record()
    before=json.dumps(rec,sort_keys=True)
    sink={}
    h=history([.2,.4,.6000000000000001,.8,1.,1.2,1.4,1.6])
    result=mod.catch_up(j,1.6,h,rec,starter_sink(sink))
    assert result.track is sink["track"]
    assert sink["track"].calls==[("observe",1.2),("observe",1.4),("observe",1.6)]
    assert result.measurement.measurement_time==result.measurement.decision_available_time==1.6
    assert json.dumps(rec,sort_keys=True)==before
    assert all(x["processed_at_simulation_time_s"]==1.6 for x in result.history)
    assert all("NOT_EXPORTED" in x["action"] for x in result.history)
    assert sink["original_times"]==list(j.validation_times)


@pytest.mark.parametrize("missing",[False,True])
def test_dead_during_catchup_stops_before_current_and_cannot_resurrect(missing):
    j=job(elapsed=1.5)
    h=history([.2,.4,.6000000000000001,.8,1.,1.2,1.4,1.6],
              fail=None if missing else 1.2,missing=1.2 if missing else None)
    sink={}
    result=mod.catch_up(j,1.6,h,record(),starter_sink(sink))
    assert result.track is None and result.status.startswith("CATCHUP_DEAD")
    assert sink["track"].calls==[("missing" if missing else "observe",1.2)]
    owner=mod.AvailabilityOwner(unavailable)
    _,event=owner.advance(1.6,None,[j],lambda j,t:result)
    assert owner.track is None and event["event"]=="INACTIVE"
    with pytest.raises(ValueError,match="resurrected"):
        owner.advance(1.8,None,[j],lambda j,t:result)


def test_catchup_may_not_read_future_history():
    sink={}
    with pytest.raises(ValueError,match="observed"):
        mod.catch_up(job(),1.,history([.2,.4,.6000000000000001,.8,1.,1.2]),record(),starter_sink(sink))
    assert sink=={}


def test_owner_failure_epoch_suppresses_arrival_without_invoking_catchup():
    owner=mod.AvailabilityOwner(unavailable)
    owner.track=FakeTrack("incumbent")
    fresh=job("new")
    def forbidden(*args): raise AssertionError("must suppress before catch-up")
    out,event=owner.advance(1.2,SimpleNamespace(time_s=1.2,fail=True),[fresh],forbidden)
    assert not out.valid and owner.track is None
    assert event["event"]=="TRACK_RELEASED"
    assert event["arrival_actions"]==[{"case_id":"new","action":"SUPPRESSED_OWNER_AT_ENTRY"}]
    assert owner.advance(1.4,None,[],forbidden)[1]["event"]=="INACTIVE"


def test_multiple_arrivals_dead_first_then_live_suppresses_remaining():
    owner=mod.AvailabilityOwner(unavailable)
    jobs=[job("first",0,1.),job("second",.1,1.),job("third",.2,1.)]
    seen=[]
    def replay(j,t):
        seen.append(j.case_id)
        if j.case_id=="first":
            return mod.CatchupResult(None,None,"CATCHUP_DEAD",[])
        return mod.CatchupResult(FakeTrack(j.case_id),measurement(t),"AVAILABLE_CURRENT_CANDIDATE",[])
    out,event=owner.advance(2,None,list(reversed(jobs)),replay)
    assert out.valid and seen==["first","second"] and owner.track.origin_id=="second"
    assert event["arrival_actions"][-1]=={"case_id":"third","action":"SUPPRESSED_AFTER_OWNER_ACQUIRED"}
    with pytest.raises(ValueError,match="resurrected"):
        owner.advance(2.2,None,[jobs[2]],replay)


def test_owner_rejects_backdated_final_export():
    owner=mod.AvailabilityOwner(unavailable)
    def bad(j,t):
        return mod.CatchupResult(FakeTrack("old"),measurement(1.),"AVAILABLE_CURRENT_CANDIDATE",[])
    with pytest.raises(ValueError,match="historical"):
        owner.advance(1.2,None,[job()],bad)
