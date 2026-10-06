#!/usr/bin/env python3
"""Causal foot-pair START/END stream; source-time replay, not calibrated sensing."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, subprocess, sys
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"src"))
from legsa_gins.paper_rebuild.body_velocity import iter_messages, STAMP, ERROR
from legsa_gins.paper_rebuild.horizontal_literature.hartley_h5 import _parse_allowed_record, HartleyH5Error
from legsa_gins.paper_rebuild.horizontal_literature.hartley_h0_h2 import NATIVE_FOOT_ORDER, FROZEN_CONTACT_ON_THRESHOLDS, FROZEN_CONTACT_OFF_THRESHOLDS
from legsa_gins.paper_rebuild.carrier_phase.support_arcs import SupportArcTracker, SupportPolicy, FootForceThreshold, SupportArcError
PLAN_REL="docs/paper_rebuild/TRUSTED_HEADING_20261006/FOOT_PAIR_PROVIDER_PLAN.json"
LOCK_REL="docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json"
EVENT_FIELDS=("event_time_s,available_time_s,event_type,clone_id,source_time_s,endpoint_id,foot_i,foot_j,episode_i,episode_j,d_body_frd_x_m,d_body_frd_y_m,d_body_frd_z_m,reason").split(",")+[f"sigma_{i}{j}" for i in range(6) for j in range(6)]
OP_FIELDS=("opportunity_time_s,first_source_time_s,status,clone_id,foot_i,foot_j").split(",")
PERIOD_NS=200_000_000
AGE_NS=50_000_000
TARGET_NS=100_000_000
MAX_INTERVAL_NS=150_000_000
SIGMA_M=.01

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,v):
    with Path(p).open("x") as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
def expand(value,aliases):
    for a,b in aliases.items():value=value.replace(a,b)
    require("<" not in value,"unresolved path alias")
    return Path(value)

class PairSchedule:
    """Pure source-event machine. Readers supply already qualified support tokens."""
    def __init__(self,sequence,window,event_sink,op_sink):
        self.sequence=sequence
        self.lo,self.hi=(round(t*1e9) for t in window)
        self.q=self.lo
        self.event_sink,self.op_sink=event_sink,op_sink
        self.active=None;self.last_ns=None;self.last_consumed_ns=None
        self.serial=0;self.events=Counter();self.opportunities=Counter()
        self.invalid_pending=False

    def event(self,ns,kind,reason,feet=None,tokens=None,endpoint=None):
        active=self.active
        require(active is not None,"event requires active clone")
        row=dict.fromkeys(EVENT_FIELDS,"")
        row.update(event_time_s=ns*1e-9,available_time_s=ns*1e-9,
                   event_type=kind,clone_id=active["id"],reason=reason)
        if kind in ("START","END"):
            pair=active["pair"];d=feet[pair[0]]-feet[pair[1]]
            row.update(source_time_s=ns*1e-9,endpoint_id=endpoint,
                       foot_i=pair[0],foot_j=pair[1],
                       episode_i=tokens[pair[0]],episode_j=tokens[pair[1]],
                       d_body_frd_x_m=float(d[0]),d_body_frd_y_m=float(d[1]),
                       d_body_frd_z_m=float(d[2]))
            if kind=="END":
                for i in range(6):
                    for j in range(6):row[f"sigma_{i}{j}"]=8*SIGMA_M**2 if i==j else 0.
            self.last_consumed_ns=ns
        self.event_sink(row);self.events[kind]+=1

    def retire(self,ns,reason):
        self.event(ns,"RETIRE",reason)
        self.active=None

    def fault_without_time(self):
        self.invalid_pending=True

    def tick(self,ns,feet,tokens,good):
        require(self.last_ns is None or ns>self.last_ns,"monotonic source needed")
        # A gap/deadline expires causally before this later arrival. No source
        # values from the later row enter the timer event.
        if self.active:
            deadline=min(self.active["start"]+MAX_INTERVAL_NS,
                         self.last_ns+AGE_NS if self.last_ns is not None else self.hi)
            if ns>deadline:
                self.retire(deadline,"SOURCE_GAP_OR_INTERVAL_TIMEOUT")
        did_event=False
        if self.active:
            a=self.active;pair=a["pair"]
            if self.invalid_pending or not good or any(tokens.get(k)!=a["tokens"][k] for k in pair):
                self.retire(ns,"SOURCE_OR_SUPPORT_INVALID")
                did_event=True
            elif ns>=a["start"]+TARGET_NS:
                self.event(ns,"END","CONTINUOUS_EPISODES_WORKING_COVARIANCE",feet,tokens,
                           f"{self.sequence}|{ns}")
                self.active=None;did_event=True
        self.invalid_pending=False
        while self.q<=ns and self.q<self.hi:
            q=self.q;self.q+=PERIOD_NS
            row=dict.fromkeys(OP_FIELDS,"")
            row.update(opportunity_time_s=q*1e-9,first_source_time_s=ns*1e-9)
            eligible=[k for k in NATIVE_FOOT_ORDER if tokens.get(k)]
            if ns>=self.hi:status="NO_SOURCE_WITHIN_WINDOW"
            elif ns-q>AGE_NS:status="FIRST_SOURCE_TOO_LATE"
            elif self.active:status="ACTIVE_INTERVAL"
            elif did_event or ns==self.last_consumed_ns:status="ENDPOINT_OR_EVENT_NOT_REUSED"
            elif not good:status="SOURCE_INVALID"
            elif len(eligible)<2:status="INSUFFICIENT_SUPPORT"
            else:
                pair=tuple(eligible[:2])
                if not np.isfinite(feet[pair[0]]-feet[pair[1]]).all() or np.linalg.norm(feet[pair[0]]-feet[pair[1]])<=1e-9:
                    status="DEGENERATE_PAIR"
                else:
                    self.serial+=1
                    self.active={"id":f"{self.sequence}_PAIR_{self.serial:05d}","start":ns,
                                 "pair":pair,"tokens":{k:tokens[k] for k in pair}}
                    self.event(ns,"START","CAUSAL_CURRENT_SUPPORT",feet,tokens,f"{self.sequence}|{ns}")
                    row.update(clone_id=self.active["id"],foot_i=pair[0],foot_j=pair[1])
                    status="START";did_event=True
            row["status"]=status;self.opportunities[status]+=1;self.op_sink(row)
        self.last_ns=ns

    def finish(self):
        if self.active:
            deadline=min(self.hi,self.active["start"]+MAX_INTERVAL_NS,self.last_ns+AGE_NS)
            self.retire(deadline,"WINDOW_END_OR_SOURCE_TIMEOUT")
        while self.q<self.hi:
            self.op_sink({"opportunity_time_s":self.q*1e-9,"status":"NO_SOURCE_WITHIN_WINDOW"})
            self.opportunities["NO_SOURCE_WITHIN_WINDOW"]+=1;self.q+=PERIOD_NS
        require(sum(self.opportunities.values())==math.ceil((self.hi-self.lo)/PERIOD_NS),"complete opportunity denominator")

def sequence_run(spec,aliases,out):
    name=spec["sequence_id"];lo,hi=spec["full_window_s"]
    raw=expand(spec["raw_files"]["body"]["path"],aliases)
    require(raw.stat().st_size==spec["raw_files"]["body"]["current_size_bytes"],"locked body size changed")
    base=round(spec["base_time_unix_s"]*1e9)
    policy=SupportPolicy(tuple(FootForceThreshold(k,on,off) for k,on,off in
        zip(NATIVE_FOOT_ORDER,FROZEN_CONTACT_ON_THRESHOLDS,FROZEN_CONTACT_OFF_THRESHOLDS)),.0120356083,.05)
    tracker=SupportArcTracker(policy,stream_id="FOOT_PAIR_NATIVE_"+name)
    counts=Counter();last_ns=None;first_ns=None
    with (out/(name+"_EVENTS.csv")).open("x",newline="") as ef,(out/(name+"_OPPORTUNITIES.csv")).open("x",newline="") as of,(out/(name+"_FAULTS.jsonl")).open("x") as ff:
        ew=csv.DictWriter(ef,fieldnames=EVENT_FIELDS,lineterminator="\n");ew.writeheader()
        ow=csv.DictWriter(of,fieldnames=OP_FIELDS,lineterminator="\n");ow.writeheader()
        scheduler=PairSchedule(name,[lo,hi],ew.writerow,ow.writerow)
        def fault(index,ns,reason):
            counts["faults"]+=1
            ff.write(json.dumps({"message_index":index,"time_s":None if ns is None else ns*1e-9,"reason":reason})+"\n")
        for index,message in enumerate(iter_messages(raw),1):
            counts["messages_framed"]+=1
            matches=list(STAMP.finditer(message))
            try:
                require(len(matches)==1,"MISSING_OR_DUPLICATED_TIMESTAMP")
                match=matches[0]
                sec,nsec=int(match[1]),int(match[2]);require(0<=nsec<1_000_000_000,"INVALID_NANOSECOND")
                ns=sec*1_000_000_000+nsec-base
            except ValueError as exc:
                scheduler.fault_without_time()
                try:tracker.update(float("nan"),{},available_time_s=float("nan"))
                except SupportArcError:pass
                fault(index,None,str(exc));continue
            if ns>round(hi*1e9):
                counts["following_timestamp_only"]+=1;break
            if last_ns is not None and ns<=last_ns:
                scheduler.fault_without_time()
                try:tracker.update(ns*1e-9,{},available_time_s=ns*1e-9)
                except SupportArcError:pass
                fault(index,ns,"NONMONOTONIC_SOURCE");continue
            if first_ns is None:first_ns=ns
            reasons=[];forces=None;feet=None
            try:
                stamp,unused_gyro,unused_accel,forces,raw_feet,unused_counter=_parse_allowed_record(message.splitlines(keepends=True),index)
                require(stamp-base==ns,"STAMP_PARSER_DISAGREEMENT")
                points=np.asarray(raw_feet,dtype=float).reshape(4,3)*[1.,-1.,-1.]
                require(np.isfinite(points).all(),"NONFINITE_FOOT")
                feet={k:v for k,v in zip(NATIVE_FOOT_ORDER,points)}
            except (ValueError,HartleyH5Error) as exc:reasons.append("PARSE:"+str(exc))
            errors=ERROR.findall(message)
            try:
                require(len(errors)==1,"ERROR_CODE_MISSING_OR_DUPLICATED")
                require(int(errors[0].strip().split("#",1)[0],0)==0,"SOURCE_ERROR_CODE")
            except ValueError as exc:reasons.append(str(exc))
            good=not reasons
            support=tracker.update(ns*1e-9,{} if forces is None else dict(zip(NATIVE_FOOT_ORDER,forces)),available_time_s=ns*1e-9,source_ok=good)
            if reasons:fault(index,ns,";".join(reasons))
            counts["source_window" if ns>=round(lo*1e9) else "source_prefix"]+=1
            if ns>=round(lo*1e9):
                tokens={k:x.token for k,x in support.by_foot().items() if x.eligible}
                scheduler.tick(ns,feet or {},tokens,good)
            last_ns=ns
        scheduler.finish()
    return {"sequence_id":name,"full_window_s":[lo,hi],"source":spec["raw_files"]["body"],
            "counts":dict(counts),"events":dict(scheduler.events),"opportunities":dict(scheduler.opportunities),
            "source_first_s":None if first_ns is None else first_ns*1e-9,
            "source_last_s":None if last_ns is None else last_ns*1e-9,
            "all_opportunities_retained":True,"reference_reads":0,"navigation_reads":0,
            "position_role":"SDK_FOOT_BODY_PROXY_NOT_ENCODER_FK",
            "source_time_replay_assumption":True,"working_point_sigma_m":SIGMA_M,
            "point_covariance_is_calibrated":False,"imu_independence_proven":False}

def run(a):
    plan=json.loads((ROOT/PLAN_REL).read_text())
    require(plan["status"]=="REGISTERED_READY","provider plan not registered")
    for rel in [PLAN_REL,str(Path(__file__).resolve().relative_to(ROOT))]:
        saved=subprocess.check_output(["git","show",a.registration_commit+":"+rel],cwd=ROOT)
        require(saved==(ROOT/rel).read_bytes(),"registration differs")
    for rel,h in plan["source_pins"].items():require(sha(ROOT/rel)==h,"provider source changed")
    require(sha(ROOT/LOCK_REL)==plan["v3_lock_sha256"],"V3 lock changed")
    aliases=json.loads(Path(a.local_paths).read_text())["aliases"]
    out=Path(a.out).resolve();require(out.is_relative_to(expand("<SCRATCH_ROOT>",aliases).resolve()),"scratch output required")
    out.mkdir(parents=True,exist_ok=False);write_json(out/"PLAN.json",plan)
    result=[]
    try:
        lock=json.loads((ROOT/LOCK_REL).read_text())
        for spec in lock["sequences"]:
            require(spec["sequence_id"] in ("BY2","BY2H","BY2O"),"unregistered sequence")
            rec=sequence_run(spec,aliases,out);result.append(rec)
            print(rec["sequence_id"],rec["events"],rec["opportunities"],flush=True)
        write_json(out/"SUMMARY.json",{"status":"COMPLETE","sequences":result,"native_calls":0,"reference_reads":0,"integer_search":0})
        write_json(out/"COMPLETE.json",{"status":"COMPLETE","files":{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    except BaseException as exc:
        write_json(out/"FAILED.json",{"error":repr(exc),"completed":result});raise

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for n in ("local-paths","out","registration-commit"):p.add_argument("--"+n,required=True)
    run(p.parse_args())
