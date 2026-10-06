#!/usr/bin/env python3
"""Causal-prefix carrier development trial from original independently tagged RAWX."""
from pathlib import Path
from dataclasses import asdict, is_dataclass
from collections import defaultdict, Counter
import argparse, hashlib, json, os, subprocess, time
import numpy as np
from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
from legsa_gins.paper_rebuild.horizontal_literature.reproduction_prepare import aliases, expand
from legsa_gins.paper_rebuild.carrier_phase.observations import from_rawx, EpochKey
from legsa_gins.paper_rebuild.carrier_phase.arcs import ArcConfig, ArcTracker
from legsa_gins.paper_rebuild.carrier_phase.multignss import build_multignss_epoch
from legsa_gins.paper_rebuild.carrier_phase.ephemeris import CheckedRtklibProvider
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock, assemble_epochs
from legsa_gins.paper_rebuild.carrier_phase.solver import solve_temporal

FAMILIES = {
 "GPS_L1": [(0,0,0)],
 "GPS_L1_L2": [(0,0,0),(0,3,0),(0,4,0)],
 "GPS_GAL_BDS_DUAL": [(0,0,0),(0,3,0),(0,4,0),(2,0,0),(2,1,0),
                     (2,5,0),(2,6,0),(3,0,0),(3,1,0),(3,2,0),(3,3,0)],
}
def serial(v):
 if is_dataclass(v): return serial(asdict(v))
 if isinstance(v,np.ndarray): return v.tolist()
 if isinstance(v,np.generic): return v.item()
 if isinstance(v,Path): return str(v)
 if isinstance(v,dict): return {str(k):serial(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)): return [serial(x) for x in v]
 return v
def emit(path,value):
 with Path(path).open("x") as f:json.dump(serial(value),f,indent=2,allow_nan=False)
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def log(path,value):
 text=json.dumps(serial(value),allow_nan=False)
 with path.open("a") as f:f.write(text+"\n");f.flush()
 print(text,flush=True)
def localtime(e,base):return 315964800.+e.gps_week*604800.+e.gps_tow_seconds-e.leap_seconds-base
def revision(code): return subprocess.check_output(["git","rev-parse","HEAD"],cwd=code,text=True).strip()
def prepare(a):
 out=a.output;out.mkdir(parents=True,exist_ok=False)
 roots=aliases(a.roots);ip=Path(roots["<EXT_REPRO_ROOT>"])/"inputs"/a.sequence/"INPUT.json"
 info=json.loads(ip.read_text());base=info["base_time"];libroot=Path(roots["<EXT_REPRO_BUILD>"])/"lib"
 nav=[expand(x,roots) for x in info["navigation"]]
 epochs={};inputs={"registry":str(ip),"registry_sha256":digest(ip),"raw_sources":{}}
 for rx in (1,2):
  source=info["source_files"][f"gnss{rx}.ubx"];p=expand(source["source"],roots)
  payload=p.read_bytes()
  if hashlib.sha256(payload).hexdigest()!=source["sha256"]:raise ValueError("UBX source identity changed")
  values=[raw.decode_rawx(body) for cls,ident,body in raw.iter_ubx_frames(payload) if (cls,ident)==(2,0x15)]
  epochs[rx]=[e for e in values if a.start<=localtime(e,base)<=a.stop]
  inputs["raw_sources"][str(rx)]={"source":source["source"],"sha256":source["sha256"],"full_epochs":len(values),"window_epochs":len(epochs[rx])}
 for rx,p in enumerate(nav,1):
  if digest(p)!=info["source_files"][f"gnss{rx}.nav"]["sha256"]:raise ValueError("navigation source changed")
 # Each receiver is processed independently; exact pairing happens afterwards.
 grouped={};events={};all_events=[];adapter_rejections=[]
 for rx in (1,2):
  groups=defaultdict(list);tracker=ArcTracker(ArcConfig(a.max_gap,a.tdcp_limit))
  for e in epochs[rx]:
   key=(e.gps_week,e.gps_tow_seconds);groups[key].append(e)
   obs=[]
   for m in e.measurements:
    try:obs.append(from_rawx(str(rx),e,m))
    except (ValueError,raw.RawBackendError) as exc:adapter_rejections.append({"rx":rx,"time_s":localtime(e,base),"signal":raw.identity_text(m.identity),"reason":str(exc)})
   ev=tracker.update_epoch(str(rx),EpochKey(*key),obs,receiver_clock_reset=bool(e.receiver_status&2))
   events[(rx,key)]={x.signal:x for x in ev}
   for x in ev:
    all_events.append({"rx":rx,"time_s":localtime(e,base),"signal":raw.identity_text(x.signal),
       "arc_token":x.arc_token,"eligible":x.eligible,"continued":x.continued,
       "metadata_continuous":x.metadata_continuous,"temporal_link_qualified":x.temporal_link_qualified,
       "reasons":x.reasons,"tdcp":x.tdcp})
  grouped[rx]=groups
 keys=sorted(set(grouped[1])&set(grouped[2]))
 pairing={"unique_pairs":sum(len(grouped[1][k])==len(grouped[2][k])==1 for k in keys),
    "unpaired_rx1":len(set(grouped[1])-set(grouped[2])),"unpaired_rx2":len(set(grouped[2])-set(grouped[1])),
    "duplicate_rx1":sum(len(v)>1 for v in grouped[1].values()),"duplicate_rx2":sum(len(v)>1 for v in grouped[2].values())}
 emit(out/"ARC_EVENTS.json",all_events)
 emit(out/"ADAPTER_REJECTIONS.json",adapter_rejections)
 records=[];pivots={family:{} for family in FAMILIES};ledger=out/"PREPARE_LEDGER.jsonl"
 with CheckedRtklibProvider(libroot/"liblegsa_rtklib_bridge.so",nav) as provider:
  for key in keys:
   if len(grouped[1][key])!=1 or len(grouped[2][key])!=1:continue
   e1,e2=grouped[1][key][0],grouped[2][key][0];t=localtime(e1,base)
   rec={"time_s":t,"key":key,"families":{}}
   try:
    spp=raw.gps_l1_code_spp(e1,provider,None,earth_rotation_delay="iterated_geometric")
    anchor=np.asarray(spp.position_ecef_m);rec["anchor_ecef_m"]=anchor;rec["spp"]=spp
   except (ValueError,raw.RawBackendError,np.linalg.LinAlgError) as exc:
    rec["spp_failure"]=str(exc);records.append(rec);log(ledger,{"time_s":t,"SPP_FAILURE":str(exc)});continue
   common=set(events[(1,key)])&set(events[(2,key)])
   arcs={}
   for identity in common:
    one,two=events[(1,key)][identity],events[(2,key)][identity]
    if one.eligible and two.eligible:
     arcs[identity]=json.dumps([one.arc_token,two.arc_token],separators=(",",":"))
   for family,spec in FAMILIES.items():
    try:
     model=build_multignss_epoch(e1,e2,provider,anchor,groups=spec,pivots=pivots[family],arc_ids=arcs)
     for group in model.groups:pivots[family].setdefault(group.key,group.pivot)
     filename=f"{family}_{len(records):03d}.npz"
     np.savez_compressed(out/filename,y=model.y,A=model.A,B=model.B,Q=model.Q)
     rec["families"][family]={"status":"BUILT","file":filename,"ambiguity_labels":model.ambiguity_labels,
        "metadata":model.metadata,"groups":[{"key":g.key,"pivot":g.pivot,"satellites":g.satellites} for g in model.groups],
        "rows":len(model.y),"ambiguities":len(model.ambiguity_labels)}
    except (ValueError,raw.RawBackendError,np.linalg.LinAlgError) as exc:
     rec["families"][family]={"status":"UNAVAILABLE","reason":str(exc),"qualification":getattr(exc,"qualification",None)}
   records.append(rec)
   log(ledger,{"time_s":t,"families":{k:{"status":v["status"],"rows":v.get("rows"),"ambiguities":v.get("ambiguities"),"reason":v.get("reason")} for k,v in rec["families"].items()}})
 emit(out/"EPHEMERIS_QUALIFICATION.json",provider.last_qualification)
 plan={"source_commit":revision(a.code),"sequence":a.sequence,"window_s":[a.start,a.stop],
   "base_time":base,"inputs":inputs,"pairing":pairing,"records":records,"lambda_library":str(libroot/"librtklib_legsa.so"),
   "baseline_length_m":a.length,"max_gap_s":a.max_gap,"tdcp_limit_cycles":a.tdcp_limit,
   "prefixes":[1,5,10],"families":FAMILIES,"cross_epoch_covariance":"assumed independent",
   "cross_signal_SD_covariance":"RAWX independent SD default; shared pivot DD propagated exactly",
   "real_integer_truth_available":False,"reference_reads":0,"scope":"development, previously inspected window",
   "arc_left_censored":True,"accepted_integer_measurement":False}
 emit(out/"PLAN.json",plan)
 print("PREPARE_COMPLETE",json.dumps(pairing),flush=True)
def solve(a):
 plan=json.loads((a.output/"PLAN.json").read_text());dest=a.output/"SOLVE";dest.mkdir(exist_ok=False)
 results=[];ledger=dest/"LEDGER.jsonl"
 for family in plan["families"]:
  for count in plan["prefixes"]:
   rec={"family":family,"prefix_epochs":count,"endpoint_time_s":None,"status":"UNAVAILABLE"}
   rows=plan["records"][:count]
   try:
    if len(rows)!=count:raise ValueError("PREFIX_EPOCHS_MISSING")
    blocks=[]
    for row in rows:
     entry=row["families"].get(family,{})
     if entry.get("status")!="BUILT":raise ValueError("PREFIX_CONTAINS_UNAVAILABLE_EPOCH")
     with np.load(a.output/entry["file"]) as z:
      blocks.append(EpochBlock(row["time_s"],z["y"],z["A"],z["B"],z["Q"],tuple(entry["ambiguity_labels"])))
    problem=assemble_epochs(blocks,plan["baseline_length_m"]);rec["endpoint_time_s"]=rows[-1]["time_s"]
    rec.update(ambiguities=problem.ambiguity_count,observations=len(problem.y),baseline_epochs=problem.epoch_count,
       requested_groups=plan["families"][family],actual_group_keys_by_epoch=[[g["key"] for g in row["families"][family]["groups"]] for row in rows])
    log(ledger,{**rec,"event":"SOLVE_START"})
    result=solve_temporal(problem,plan["lambda_library"],node_limit=a.nodes,timeout_s=a.timeout)
    rec.update(status="CERTIFIED_CANDIDATE" if result.global_optimum_certified else "UNCERTIFIED",
        certificate=result.certificate,best=result.best,second=result.second,
        float_residual_cost=result.float_solution.residual_objective,
        float_condition_number=result.float_solution.condition_number,
        accepted_integer_measurement=False,ambiguity_labels=problem.ambiguity_labels)
   except (ValueError,raw.RawBackendError,np.linalg.LinAlgError) as exc:rec["failure"]=type(exc).__name__+":"+str(exc)
   emit(dest/f"{family}_{count:02d}.json",rec);results.append(rec)
   log(ledger,{"event":"SOLVE_END","family":family,"prefix_epochs":count,"status":rec["status"],"failure":rec.get("failure"),
      "certificate":rec.get("certificate")})
 emit(dest/"RESULTS.json",{"execution_commit":revision(a.code),"node_limit":a.nodes,"timeout_s":a.timeout,"records":results,"reference_reads":0,"real_integer_truth_available":False})
def main():
 p=argparse.ArgumentParser();p.add_argument("mode",choices=["prepare","solve"])
 p.add_argument("--code",type=Path,default=Path(__file__).resolve().parents[3]);p.add_argument("--roots",type=Path)
 p.add_argument("--output",type=Path,required=True);p.add_argument("--sequence",default="BY2")
 p.add_argument("--start",type=float,default=80.);p.add_argument("--stop",type=float,default=82.)
 p.add_argument("--length",type=float,default=.350);p.add_argument("--max-gap",type=float,default=.21)
 p.add_argument("--tdcp-limit",type=float,default=.5);p.add_argument("--nodes",type=int,default=100000);p.add_argument("--timeout",type=float,default=60.)
 a=p.parse_args()
 if os.uname().sysname!="Linux":raise RuntimeError("algorithm trial must run in Ubuntu WSL")
 (prepare if a.mode=="prepare" else solve)(a)
if __name__=="__main__":main()
