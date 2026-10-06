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
from legsa_gins.paper_rebuild.carrier_phase.causal_anchor import AnchorPolicy, CausalRawCodeAnchor
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
def source_snapshot(code):
 paths=list((code/"src/legsa_gins/paper_rebuild/carrier_phase").glob("*.py"))
 paths += [code/"src/legsa_gins/paper_rebuild/horizontal_literature"/name for name in
   ("shared_raw_backend.py","reproduction_backend.py","ext01_clambda.py")]
 paths.append(Path(__file__))
 return {str(p.relative_to(code)):digest(p) for p in paths}

def checked_navigation_manifest(path,roots,*,start_s,first_epoch_s=None,expected_cutoff=None,expected_lineage=None,allow_empty_navigation=False):
 """Admit an explicitly bounded broadcast prefix, never an inherited full NAV.

 The cutoff describes the latest source-message availability admitted by the
 prefix producer, not an ephemeris TOE/age check. Availability must precede
 both the requested start and every receiver's actual first processed epoch.
 """
 if path is None:raise ValueError("CAUSAL_NAVIGATION_MANIFEST_REQUIRED")
 if not np.isfinite(start_s):raise ValueError("FINITE_START_REQUIRED")
 path=Path(path);manifest=json.loads(path.read_text())
 cutoff=manifest.get("causal_cutoff_relative_s")
 if isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not np.isfinite(cutoff):
  raise ValueError("FINITE_CAUSAL_NAVIGATION_CUTOFF_REQUIRED")
 if expected_cutoff is not None and cutoff!=expected_cutoff:
  raise ValueError("NAVIGATION_SCHEDULE_MANIFEST_CUTOFF_MISMATCH")
 if expected_lineage is not None:
  for key,value in expected_lineage.items():
   if manifest.get(key)!=value:raise ValueError("NAVIGATION_PREFIX_LINEAGE_MISMATCH:"+key)
 if manifest.get("old_full_history_navigation_loaded") is not False:
  raise ValueError("FULL_HISTORY_NAVIGATION_NOT_ALLOWED")
 if cutoff>start_s:raise ValueError("NAVIGATION_PREFIX_AFTER_REQUESTED_START")
 if first_epoch_s is not None:
  if not np.isfinite(first_epoch_s):raise ValueError("FINITE_FIRST_EPOCH_REQUIRED")
  if cutoff>first_epoch_s:raise ValueError("NAVIGATION_PREFIX_AFTER_FIRST_EPOCH")
 entries=manifest.get("navigation")
 if not isinstance(entries,list):raise ValueError("INVALID_NAVIGATION_PREFIX_LIST")
 availability=manifest.get("navigation_availability","AVAILABLE")
 outcomes=manifest.get("conversion_outcomes")
 if outcomes is not None:
  if not isinstance(outcomes,list) or len(outcomes)!=2 or not all(isinstance(x,dict) for x in outcomes):
   raise ValueError("INVALID_PREFIX_CONVERSION_OUTCOMES")
  if {x.get("receiver") for x in outcomes if isinstance(x,dict)}!={1,2}:
   raise ValueError("PREFIX_CONVERSION_RECEIVERS_REQUIRED")
  if any(type(x.get("returncode")) is not int or x["returncode"]!=0
         or type(x.get("navigation_output_present")) is not bool for x in outcomes):
   raise ValueError("PREFIX_CONVERSION_NOT_SUCCESSFUL")
  if {x["receiver"] for x in outcomes if x["navigation_output_present"]} != {
      x.get("receiver") for x in entries if isinstance(x,dict)}:
   raise ValueError("PREFIX_CONVERSION_NAVIGATION_MISMATCH")
 if not entries:
  if not allow_empty_navigation:raise ValueError("NAVIGATION_PREFIX_EMPTY")
  if availability!="NO_NAV_OUTPUT_AT_PREFIX" or outcomes is None:
   raise ValueError("EMPTY_NAVIGATION_EXPLICIT_QUALIFICATION_REQUIRED")
 elif availability!="AVAILABLE":
  raise ValueError("NONEMPTY_NAVIGATION_AVAILABILITY_MISMATCH")
 nav=[]
 for row in entries:
  if not isinstance(row,dict) or not isinstance(row.get("path"),str) or not isinstance(row.get("sha256"),str):
   raise ValueError("INVALID_NAVIGATION_PREFIX_ENTRY")
  item=Path(row["path"]) if Path(row["path"]).is_absolute() else expand(row["path"],roots)
  if item in nav:raise ValueError("DUPLICATE_NAVIGATION_PREFIX_PATH")
  if digest(item)!=row["sha256"]:raise ValueError("explicit navigation identity changed")
  nav.append(item)
 return nav,{"manifest":str(path),"sha256":digest(path),"navigation":entries,
  "causal_cutoff_relative_s":float(cutoff),"requested_start_s":float(start_s),
  "first_processed_rawx_s":None if first_epoch_s is None else float(first_epoch_s),
  "causality_guard":"PREFIX_AVAILABILITY_AT_OR_BEFORE_REQUESTED_AND_ACTUAL_START",
  "inherited_full_history_navigation_opened":False,
  "navigation_availability":availability,"conversion_outcomes":outcomes}


class UnavailableBroadcastProvider:
 """Explicit empty causal snapshot; never fabricates a satellite state."""
 status="NO_NAV_OUTPUT_AT_PREFIX"
 def __init__(self):self.last_qualification={}
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def state(self,identity,*args,**kwargs):
  self.last_qualification[raw.identity_text(identity)]={"status":self.status}
  raise raw.RawBackendError(self.status)


class NavigationReplay:
 """Lazy causal NAV snapshots. Future manifests and NAV bytes stay unopened.

 Schedule metadata may be inspected at construction, but only a selected entry
 at or before the current receiver epoch may open its manifest/NAV payload.
 Every epoch uses one provider snapshot throughout SPP and all DD families.
 """
 def __init__(self,roots,library,*,start_s,manifest=None,schedule=None,allow_empty_navigation=False):
  if (manifest is None)==(schedule is None):
   raise ValueError("EXACTLY_ONE_NAVIGATION_MANIFEST_OR_SCHEDULE_REQUIRED")
  if not np.isfinite(start_s):raise ValueError("FINITE_START_REQUIRED")
  self.roots=roots;self.library=library;self.start_s=float(start_s)
  self.allow_empty_navigation=bool(allow_empty_navigation)
  self.provider=None;self.index=None;self.last_time=None;self.current_audit=None
  self.switches=[];self.qualification={};self.initial_paths=None;self.expected_lineage=None
  self.schedule_registry_sha256=None
  if schedule is None:
   self.initial_paths,audit=checked_navigation_manifest(manifest,roots,start_s=start_s,allow_empty_navigation=self.allow_empty_navigation)
   self.entries=[{"cutoff_relative_s":audit["causal_cutoff_relative_s"],"manifest":str(manifest),"manifest_sha256":audit["sha256"]}]
   self.input_audit=audit
  else:
   schedule=Path(schedule);data=json.loads(schedule.read_text())
   if data.get("schema")!="causal_navigation_schedule.v1":raise ValueError("NAVIGATION_SCHEDULE_SCHEMA")
   if data.get("old_full_history_navigation_loaded") is not False:raise ValueError("FULL_HISTORY_NAVIGATION_NOT_ALLOWED")
   self.schedule_registry_sha256=data.get("registry_sha256")
   entries=data.get("entries")
   if not isinstance(entries,list) or not entries:raise ValueError("EMPTY_NAVIGATION_SCHEDULE")
   self.entries=[]
   for row in entries:
    if not isinstance(row,dict):raise ValueError("INVALID_NAVIGATION_SCHEDULE_ENTRY")
    cutoff=row.get("cutoff_relative_s")
    if isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not np.isfinite(cutoff):
     raise ValueError("FINITE_CAUSAL_NAVIGATION_CUTOFF_REQUIRED")
    if self.entries and cutoff<=self.entries[-1]["cutoff_relative_s"]:raise ValueError("NAVIGATION_SCHEDULE_NOT_STRICTLY_ORDERED")
    if not isinstance(row.get("manifest"),str) or not row["manifest"] or not isinstance(row.get("manifest_sha256"),str):
     raise ValueError("INVALID_NAVIGATION_SCHEDULE_ENTRY")
    item=Path(row["manifest"])
    if not item.is_absolute():
     item=expand(row["manifest"],roots) if row["manifest"].startswith("<") else schedule.parent/item
    self.entries.append({**row,"manifest":str(item)})
   if self.entries[0]["cutoff_relative_s"]>start_s:raise ValueError("NAVIGATION_PREFIX_AFTER_REQUESTED_START")
   self.input_audit={"schedule":str(schedule),"sha256":digest(schedule),"entries":self.entries,
     "requested_start_s":self.start_s,"causality_guard":"LAZY_LATEST_PREFIX_AT_OR_BEFORE_CURRENT_EPOCH",
     "inherited_full_history_navigation_opened":False}

 def __enter__(self):return self
 def __exit__(self,*args):
  if self.provider is not None:
   self._remember_qualification()
   self.provider.__exit__(*args);self.provider=None
  return False
 def bind_inputs(self,registry_sha256,base_time,source_ubx_sha256):
  if "schedule" in self.input_audit:
   if self.schedule_registry_sha256!=registry_sha256:raise ValueError("NAVIGATION_SCHEDULE_REGISTRY_MISMATCH")
   self.expected_lineage={"registry_sha256":registry_sha256,"base_time":base_time,
                          "source_ubx_sha256":source_ubx_sha256}
   self.input_audit["registry_sha256"]=registry_sha256
 def _remember_qualification(self):
  self.qualification[str(self.index)]={"navigation":self.current_audit,
      "last_signal_queries_in_snapshot":dict(self.provider.last_qualification)}
 def advance(self,time_s):
  if not np.isfinite(time_s) or (self.last_time is not None and time_s<=self.last_time):
   raise ValueError("NAVIGATION_EPOCHS_MUST_BE_FINITE_STRICTLY_INCREASING")
  eligible=[i for i,row in enumerate(self.entries) if row["cutoff_relative_s"]<=time_s]
  if not eligible:raise ValueError("NAVIGATION_PREFIX_AFTER_FIRST_EPOCH")
  index=eligible[-1]
  if index!=self.index:
   row=self.entries[index];path=Path(row["manifest"])
   if digest(path)!=row["manifest_sha256"]:raise ValueError("NAVIGATION_SCHEDULE_MANIFEST_IDENTITY_CHANGED")
   paths,audit=checked_navigation_manifest(path,self.roots,start_s=time_s,first_epoch_s=time_s,
       expected_cutoff=row["cutoff_relative_s"],expected_lineage=(None
        if index==0 and row.get("reuse_initial_prefix") is True else self.expected_lineage),
       allow_empty_navigation=self.allow_empty_navigation)
   # Open the new admitted prefix before retiring the old handle. On error the
   # run stops: no silent stale/full-history fallback or future retry occurs.
   replacement=CheckedRtklibProvider(self.library,paths) if paths else UnavailableBroadcastProvider()
   replacement.__enter__()
   if self.provider is not None:
    self._remember_qualification();self.provider.__exit__(None,None,None)
   self.provider=replacement;self.index=index;self.current_audit=audit
   self.switches.append({"epoch_time_s":float(time_s),"schedule_index":index,**audit})
   if "schedule" not in self.input_audit:self.input_audit["first_processed_rawx_s"]=float(time_s)
  self.last_time=float(time_s)
  return self.provider, {"schedule_index":index,"causal_cutoff_relative_s":float(self.entries[index]["cutoff_relative_s"]),
      "manifest":self.current_audit["manifest"],"manifest_sha256":self.current_audit["sha256"],
      "navigation_availability":self.current_audit["navigation_availability"]}


def build_with_pivot_policy(e1,e2,provider,anchor,*,groups,pivots,arc_ids,policy="fixed"):
 """Retain a qualified pivot; reselect only explicit current-pivot failure.

 Rebuilding uses the unchanged group's current qualification/elevation/lock
 policy. No previous integers are transformed or copied to new DD labels.
 """
 if policy not in ("fixed","reselect_when_missing"):raise ValueError("INVALID_PIVOT_POLICY")
 trial_pivots=dict(pivots);initial_error=None
 try:
  model=build_multignss_epoch(e1,e2,provider,anchor,groups=groups,pivots=trial_pivots,arc_ids=arc_ids)
  qualification=model.metadata
 except raw.RawBackendError as exc:
  initial_error=exc;qualification=getattr(exc,"qualification",{})
 missing={tuple(row["group"]) for row in qualification.get("groups",[])
          if row.get("status")=="REQUESTED_PIVOT_UNAVAILABLE"}
 changes=[]
 if policy=="reselect_when_missing" and missing:
  for key in sorted(missing):
   previous=trial_pivots.pop(key)
   changes.append({"group":key,"previous_pivot":raw.identity_text(previous),
      "new_pivot":None,"reason":"PREVIOUS_PIVOT_NOT_CURRENTLY_QUALIFIED",
      "integer_transfer":False})
  try:
   model=build_multignss_epoch(e1,e2,provider,anchor,groups=groups,pivots=trial_pivots,arc_ids=arc_ids)
  except raw.RawBackendError as exc:
   exc.pivot_events=changes;raise
 elif initial_error is not None:raise initial_error
 for group in model.groups:
  for change in changes:
   if tuple(change["group"])==group.key:change["new_pivot"]=raw.identity_text(group.pivot)
  pivots[group.key]=group.pivot
 return model,changes

def prepare(a):
 # New preparations require an explicit causal prefix. Historical saved plans
 # remain unchanged and readable; there is deliberately no implicit full-NAV
 # fallback for an integration run.
 roots=aliases(a.roots)
 replay=NavigationReplay(roots,Path(roots["<EXT_REPRO_BUILD>"])/"lib/liblegsa_rtklib_bridge.so",
   start_s=a.start,manifest=getattr(a,"navigation_manifest",None),schedule=getattr(a,"navigation_schedule",None),
   allow_empty_navigation=getattr(a,"allow_empty_navigation",False))
 anchor_policy=AnchorPolicy(max_hold_age_s=getattr(a,"max_anchor_hold_s",0.))
 anchor_state=CausalRawCodeAnchor(anchor_policy)
 pivot_policy=getattr(a,"pivot_policy","fixed")
 if pivot_policy not in ("fixed","reselect_when_missing"):raise ValueError("INVALID_PIVOT_POLICY")
 if not np.isfinite(a.stop) or a.stop<a.start:raise ValueError("INVALID_WINDOW")
 out=a.output;out.mkdir(parents=True,exist_ok=False)
 execution=revision(a.code);source_pins=source_snapshot(a.code)
 ip=Path(roots["<EXT_REPRO_ROOT>"])/"inputs"/a.sequence/"INPUT.json"
 info=json.loads(ip.read_text());base=info["base_time"];libroot=Path(roots["<EXT_REPRO_BUILD>"])/"lib"
 replay.bind_inputs(digest(ip),base,{str(rx):info["source_files"][f"gnss{rx}.ubx"]["sha256"] for rx in (1,2)})
 epochs={};inputs={"registry":str(ip),"registry_sha256":digest(ip),"raw_sources":{}}
 for rx in (1,2):
  source=info["source_files"][f"gnss{rx}.ubx"];p=expand(source["source"],roots)
  payload=p.read_bytes()
  if hashlib.sha256(payload).hexdigest()!=source["sha256"]:raise ValueError("UBX source identity changed")
  values=[raw.decode_rawx(body) for cls,ident,body in raw.iter_ubx_frames(payload) if (cls,ident)==(2,0x15)]
  epochs[rx]=[e for e in values if a.start<=localtime(e,base)<=a.stop]
  inputs["raw_sources"][str(rx)]={"source":source["source"],"sha256":source["sha256"],"full_epochs":len(values),"window_epochs":len(epochs[rx])}
 if not epochs[1] or not epochs[2]:raise ValueError("RAWX_WINDOW_MISSING_RECEIVER")
 first_epoch=min(localtime(e,base) for rx in (1,2) for e in epochs[rx])
 if replay.entries[0]["cutoff_relative_s"]>first_epoch:
  raise ValueError("NAVIGATION_PREFIX_AFTER_FIRST_EPOCH")
 inputs["navigation_override"]=replay.input_audit

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
 records=[];pivots={family:{} for family in FAMILIES};pivot_events=[];ledger=out/"PREPARE_LEDGER.jsonl"
 with replay:
  for key in keys:
   if len(grouped[1][key])!=1 or len(grouped[2][key])!=1:continue
   e1,e2=grouped[1][key][0],grouped[2][key][0];t=localtime(e1,base)
   provider,epoch_navigation=replay.advance(t)
   rec={"time_s":t,"key":key,"families":{},"navigation":epoch_navigation}
   try:
    spp=raw.gps_l1_code_spp(e1,provider,None,earth_rotation_delay="iterated_geometric")
   except (ValueError,raw.RawBackendError,np.linalg.LinAlgError) as exc:
    rec["spp_failure"]=str(exc)
    decision=anchor_state.resolve(t,failure=str(exc))
   else:
    rec["spp"]=spp
    decision=anchor_state.resolve(t,position_ecef_m=spp.position_ecef_m)
   rec["anchor_decision"]={**asdict(decision),"available":decision.available,"held":decision.held}
   if not decision.available:
    records.append(rec);log(ledger,{"time_s":t,"navigation":epoch_navigation,
       "SPP_FAILURE":rec.get("spp_failure"),"anchor_status":decision.status});continue
   anchor=np.asarray(decision.position_ecef_m);rec["anchor_ecef_m"]=anchor
   common=set(events[(1,key)])&set(events[(2,key)])
   arcs={}
   for identity in common:
    one,two=events[(1,key)][identity],events[(2,key)][identity]
    if one.eligible and two.eligible:
     arcs[identity]=json.dumps([one.arc_token,two.arc_token],separators=(",",":"))
   for family,spec in FAMILIES.items():
    try:
     model,changes=build_with_pivot_policy(e1,e2,provider,anchor,groups=spec,
         pivots=pivots[family],arc_ids=arcs,policy=pivot_policy)
     pivot_events.extend({"time_s":t,"family":family,**change} for change in changes)
     filename=f"{family}_{len(records):03d}.npz"
     np.savez_compressed(out/filename,y=model.y,A=model.A,B=model.B,Q=model.Q)
     rec["families"][family]={"status":"BUILT","file":filename,"ambiguity_labels":model.ambiguity_labels,
        "metadata":model.metadata,"groups":[{"key":g.key,"pivot":g.pivot,"satellites":g.satellites} for g in model.groups],
        "rows":len(model.y),"ambiguities":len(model.ambiguity_labels)}
    except (ValueError,raw.RawBackendError,np.linalg.LinAlgError) as exc:
     rec["families"][family]={"status":"UNAVAILABLE","reason":str(exc),"qualification":getattr(exc,"qualification",None)}
     pivot_events.extend({"time_s":t,"family":family,**change} for change in getattr(exc,"pivot_events",[]))
   records.append(rec)
   log(ledger,{"time_s":t,"navigation":epoch_navigation,"anchor_status":decision.status,"families":{k:{"status":v["status"],"rows":v.get("rows"),"ambiguities":v.get("ambiguities"),"reason":v.get("reason")} for k,v in rec["families"].items()}})
 emit(out/"EPHEMERIS_QUALIFICATION.json",replay.qualification if "schedule" in replay.input_audit
      else replay.qualification.get("0",{}).get("last_signal_queries_in_snapshot",{}))
 emit(out/"NAVIGATION_SWITCHES.json",replay.switches)
 emit(out/"PIVOT_EVENTS.json",pivot_events)
 plan={"source_commit":execution,"source_sha256":source_pins,"sequence":a.sequence,"window_s":[a.start,a.stop],
   "base_time":base,"inputs":inputs,"pairing":pairing,"records":records,"lambda_library":str(libroot/"librtklib_legsa.so"),
   "baseline_length_m":a.length,"max_gap_s":a.max_gap,"tdcp_limit_cycles":a.tdcp_limit,
   "pivot_policy":pivot_policy,"anchor_policy":asdict(anchor_policy),
   "allow_empty_navigation":getattr(a,"allow_empty_navigation",False),
   "prefixes":[1,5,10],"families":FAMILIES,"cross_epoch_covariance":"assumed independent",
   "cross_signal_SD_covariance":"RAWX independent SD default; shared pivot DD propagated exactly",
   "real_integer_truth_available":False,"reference_reads":0,"scope":"development; inspection history is declared by the calling trial contract",
   "arc_left_censored":True,"accepted_integer_measurement":False}
 emit(out/"PLAN.json",plan)
 print("PREPARE_COMPLETE",json.dumps(pairing),flush=True)
def solve(a):
 plan=json.loads((a.output/"PLAN.json").read_text());dest=a.output/("SOLVE_ACTIVE" if a.active_classes else "SOLVE");dest.mkdir(exist_ok=False)
 execution=revision(a.code);source_pins=source_snapshot(a.code)
 results=[];ledger=dest/"LEDGER.jsonl"
 for family in (a.families or plan["families"]):
  for count in (a.prefixes or plan["prefixes"]):
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
    kwargs={"distinct_ambiguity_labels":blocks[-1].ambiguity_labels} if a.active_classes else {}
    result=solve_temporal(problem,plan["lambda_library"],node_limit=a.nodes,timeout_s=a.timeout,**kwargs)
    rec.update(status="CERTIFIED_CANDIDATE" if result.global_optimum_certified else "UNCERTIFIED",
        certificate=result.certificate,best=result.best,second=result.second,
        float_residual_cost=result.float_solution.residual_objective,
        float_condition_number=result.float_solution.condition_number,
        accepted_integer_measurement=False,ambiguity_labels=problem.ambiguity_labels)
   except (ValueError,raw.RawBackendError,np.linalg.LinAlgError) as exc:rec["failure"]=type(exc).__name__+":"+str(exc)
   emit(dest/f"{family}_{count:02d}.json",rec);results.append(rec)
   log(ledger,{"event":"SOLVE_END","family":family,"prefix_epochs":count,"status":rec["status"],"failure":rec.get("failure"),
      "certificate":rec.get("certificate")})
 emit(dest/"RESULTS.json",{"execution_commit":execution,"source_sha256":source_pins,"active_classes":a.active_classes,"node_limit":a.nodes,"timeout_s":a.timeout,"records":results,"reference_reads":0,"real_integer_truth_available":False})
def main():
 p=argparse.ArgumentParser();p.add_argument("mode",choices=["prepare","solve"])
 p.add_argument("--code",type=Path,default=Path(__file__).resolve().parents[3]);p.add_argument("--roots",type=Path)
 p.add_argument("--output",type=Path,required=True);p.add_argument("--sequence",default="BY2")
 p.add_argument("--start",type=float,default=80.);p.add_argument("--stop",type=float,default=82.)
 p.add_argument("--length",type=float,default=.350);p.add_argument("--max-gap",type=float,default=.21)
 nav=p.add_mutually_exclusive_group()
 nav.add_argument("--navigation-manifest",type=Path);nav.add_argument("--navigation-schedule",type=Path)
 p.add_argument("--allow-empty-navigation",action="store_true")
 p.add_argument("--pivot-policy",choices=["fixed","reselect_when_missing"],default="fixed")
 p.add_argument("--max-anchor-hold-s",type=float,default=0.)
 p.add_argument("--active-classes",action="store_true")
 p.add_argument("--prefixes",nargs="+",type=int);p.add_argument("--families",nargs="+",choices=list(FAMILIES))
 p.add_argument("--tdcp-limit",type=float,default=.5);p.add_argument("--nodes",type=int,default=100000);p.add_argument("--timeout",type=float,default=60.)
 a=p.parse_args()
 if os.uname().sysname!="Linux":raise RuntimeError("algorithm trial must run in Ubuntu WSL")
 (prepare if a.mode=="prepare" else solve)(a)
if __name__=="__main__":main()
