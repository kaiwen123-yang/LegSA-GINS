"""Six pure synthetic source/scheduler checks; no registered body or NAV reads."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("foot_pair_provider_local", ROOT/"scripts/paper_rebuild/carrier_phase/foot_pair_provider.py")
provider=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=provider
spec.loader.exec_module(provider)
NS=1_000_000_000

def feet():
    # Physical FR/FL/RR/RL points already in body FRD for scheduler-only calls.
    return dict(zip(("FR","FL","RR","RL"),np.array([[.2,.15,.4],[.2,-.15,.4],[-.2,.15,.4],[-.2,-.15,.4]])))

def tokens(suffix="a"):
    return {name:name+"-"+suffix for name in feet()}

def schedule(window=(0.,.6)):
    events,opportunities=[],[]
    return provider.PairSchedule("SYNTH",window,events.append,opportunities.append),events,opportunities

def tick(s,t,*,good=True,tok=None):
    s.tick(round(t*NS),feet(),tokens() if tok is None else tok,good)

def message(t,*,error=0,force=100.,duplicate_stamp=False):
    # A synthetic ROS-text message at base=1000; never copy actual raw content.
    total=1000*NS+round(t*NS)
    sec,ns=divmod(total,NS)
    stamp=f"stamp:\n  sec: {sec}\n  nanosec: {ns}\n"
    return stamp+(stamp if duplicate_stamp else "")+(
        f"error_code: {error}\n"
        "imu_state:\n"
        "  gyroscope: [0.0, 0.0, 0.0]\n"
        "  accelerometer: [0.0, 0.0, 9.81]\n"
        # These deliberately undecodable fields must be lexically skipped.
        "  rpy: NOT_A_NUMERIC_ARRAY\n"
        "velocity: NOT_A_NUMERIC_ARRAY\n"
        "foot_speed_body: NOT_A_NUMERIC_ARRAY\n"
        f"foot_force: [{force}, {force}, {force}, {force}]\n"
        "foot_position_body: [0.2, -0.15, -0.4, 0.2, 0.15, -0.4, -0.2, -0.15, -0.4, -0.2, 0.15, -0.4]\n")

def run_stream(tmp_path,messages,window=(0.,.4)):
    raw=tmp_path/"synthetic_body.txt"
    raw.write_text("---\n".join(messages))
    out=tmp_path/"output";out.mkdir()
    spec={"sequence_id":"SYNTH","full_window_s":list(window),"base_time_unix_s":1000,
          "raw_files":{"body":{"path":"<SYNTH_ROOT>/synthetic_body.txt","current_size_bytes":raw.stat().st_size}}}
    summary=provider.sequence_run(spec,{"<SYNTH_ROOT>":str(tmp_path)},out)
    def table(name):
        with (out/("SYNTH_"+name+".csv")).open() as stream:
            return list(csv.DictReader(stream))
    faults=[json.loads(x) for x in (out/"SYNTH_FAULTS.jsonl").read_text().splitlines()]
    return summary,table("EVENTS"),table("OPPORTUNITIES"),faults

def test_first_actual_source_and_start_does_not_look_at_future():
    a,ea,oa=schedule()
    b,eb,ob=schedule()
    for s in (a,b):
        tick(s,.017);tick(s,.047);tick(s,.077)
    assert ea==eb and ea[0]["event_time_s"]==pytest.approx(.017)
    assert (ea[0]["foot_i"],ea[0]["foot_j"])==("FR","FL")
    assert oa[0]["opportunity_time_s"]==0.
    # Same prefix, mutually incompatible futures; START is already immutable.
    tick(a,.107);tick(a,.117)
    changed=tokens();changed.pop("FL")
    tick(b,.107,tok=changed);tick(b,.117,tok=tokens("new"))
    assert ea[0]==eb[0]
    assert [e["event_type"] for e in ea]==["START","END"]
    assert [e["event_type"] for e in eb]==["START","RETIRE"]

def test_end_is_once_and_endpoint_time_is_never_reused():
    s,events,ops=schedule()
    for t in (.003,.033,.063,.093,.103,.133,.163,.193,.203,.233,.263,.293,.303):
        tick(s,t)
    assert [e["event_type"] for e in events]==["START","END","START","END"]
    endpoint=[e["endpoint_id"] for e in events]
    assert len(endpoint)==len(set(endpoint))
    assert [e["event_time_s"] for e in events]==pytest.approx([.003,.103,.203,.303])
    assert len({e["clone_id"] for e in events})==2
    with pytest.raises(ValueError,match="monotonic"):
        tick(s,.303)
    with pytest.raises(ValueError,match="monotonic"):
        tick(s,.302)

def test_causal_gap_timer_and_window_terminal_cleanup():
    s,events,ops=schedule()
    tick(s,.003);tick(s,.033)
    # No later foot values can repair the already expired source interval.
    tick(s,.103)
    assert events[1]["event_type"]=="RETIRE"
    assert events[1]["event_time_s"]==pytest.approx(.083)
    assert events[1]["source_time_s"]==""
    assert events[1]["event_time_s"]<.103
    s2,e2,o2=schedule((0.,.25))
    tick(s2,.217)
    s2.finish()
    assert [e["event_type"] for e in e2]==["START","RETIRE"]
    assert e2[-1]["event_time_s"]==pytest.approx(.25)
    assert e2[-1]["reason"]=="WINDOW_END_OR_SOURCE_TIMEOUT"
    # This is a requested cleanup event, not simulated IMU propagation.
    assert e2[-1]["source_time_s"]=="" and all(e["event_type"]!="END" for e in e2)

def test_prefix_frame_schema_and_arbitrary_cross_covariance_bound(tmp_path):
    times=(-.04,-.02,.003,.033,.063,.093,.103,.133,.163,.193,.203,.233,.263,.293,.303,.333,.363,.393,.403)
    summary,events,ops,faults=run_stream(tmp_path,[message(t) for t in times])
    assert summary["counts"]["source_prefix"]==2
    assert summary["counts"]["following_timestamp_only"]==1
    assert not faults and len(ops)==2
    assert float(events[0]["event_time_s"])==pytest.approx(.003)
    assert len(events[0])==50 and set(events[0])==set(provider.EVENT_FIELDS)
    assert [float(events[0]["d_body_frd_"+a+"_m"]) for a in "xyz"]==pytest.approx([0.,.3,0.])
    assert all(events[0][f"sigma_{i}{j}"]=="" for i in range(6) for j in range(6))
    end=next(e for e in events if e["event_type"]=="END")
    q=np.array([[float(end[f"sigma_{i}{j}"]) for j in range(6)] for i in range(6)])
    assert np.array_equal(q,np.eye(6)*.0008)
    rotation=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
    l=np.column_stack((np.eye(3),-rotation))
    assert np.array_equal(l@q@l.T,np.eye(3)*.0016)
    assert summary["point_covariance_is_calibrated"] is False
    assert summary["imu_independence_proven"] is False

def test_bad_timestamp_and_duplicate_stamp_retire_old_support(tmp_path):
    records=[message(t) for t in (-.04,-.02,.003,.033)]
    records+=["missing_stamp: true\n",message(.032),message(.05,duplicate_stamp=True)]
    records += [message(t) for t in (.063,.093,.123,.153,.183,.203,.233,.263,.293,.303,.333,.363,.393,.403)]
    summary,events,ops,faults=run_stream(tmp_path,records)
    assert len(faults)==3
    assert sum("MISSING_OR_DUPLICATED_TIMESTAMP" in f["reason"] for f in faults)==2
    assert sum("NONMONOTONIC_SOURCE" in f["reason"] for f in faults)==1
    starts=[e for e in events if e["event_type"]=="START"]
    assert len(starts)==2
    assert starts[0]["episode_i"]!=starts[1]["episode_i"]
    first_id=starts[0]["clone_id"]
    assert [e["event_type"] for e in events if e["clone_id"]==first_id]==["START","RETIRE"]
    assert len(ops)==2 and summary["all_opportunities_retained"]

def test_complete_opportunity_denominator_and_source_error(tmp_path):
    s,events,ops=schedule((0.,.8))
    tick(s,.003,good=False,tok={})
    tick(s,.203,tok={})
    tick(s,.457)
    s.finish()
    assert [x["status"] for x in ops]==["SOURCE_INVALID","INSUFFICIENT_SUPPORT","FIRST_SOURCE_TOO_LATE","NO_SOURCE_WITHIN_WINDOW"]
    assert len(ops)==4 and not events
    records=[message(t) for t in (-.04,-.02,.003,.033)]
    records += [message(.063,error=1)]
    records += [message(t) for t in (.093,.123,.153,.183,.203,.233,.263,.293,.303,.333,.363,.393,.403)]
    summary,events,ops,faults=run_stream(tmp_path,records)
    assert len(faults)==1 and "SOURCE_ERROR_CODE" in faults[0]["reason"]
    first_id=events[0]["clone_id"]
    assert [e["event_type"] for e in events if e["clone_id"]==first_id]==["START","RETIRE"]
    assert len(ops)==2
