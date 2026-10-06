#!/usr/bin/env python3
"""Bounded AR qualification: frozen existing DD/C-ILS, optional vertical RP row."""
from pathlib import Path
from dataclasses import replace
import argparse,csv,hashlib,importlib.util,json,math,os,subprocess,time
import re,sys,shutil,signal
import numpy as np
import pandas as pd
from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
from legsa_gins.paper_rebuild.horizontal_literature import reproduction_backend as backend
from legsa_gins.paper_rebuild.horizontal_literature import ext01_clambda as cl
from legsa_gins.paper_rebuild.horizontal_literature.phase2_runner import CompactCacheReader,validate_compact_cache
from legsa_gins.paper_rebuild.horizontal_literature.phase3_runner import _ecef_vector_to_ned
from legsa_gins.paper_rebuild.horizontal_literature.reproduction_prepare import aliases,expand,LIBRARY_PINS
from legsa_gins.paper_rebuild.horizontal_literature.reproduction_runner import jsonable,source_pins
LENGTH=.350
PRIOR_SIGMA=.030
TARGETS=list(range(80,301,20))
REFERENCE="<RAW_ROOT>/BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/vrtk2_a87c6e_2026-03-06-08-00-54_minimal/trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"
REFERENCE_SHA="ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"
FROZEN_EVAL="src/legsa_gins/paper_rebuild/hext/hx02_heading_evaluation.py"
FROZEN_EVAL_SHA="eedb3faf56ccffca222d915c401d3075dc64583ce68a10f08add9f8b705fa994"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def emit(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x") as f:json.dump(jsonable(obj),f,indent=2,ensure_ascii=False,allow_nan=False)
def vertical_row(anchor):
 # Down row of ECEF -> NED, independent of any estimated baseline/heading.
 return np.array([_ecef_vector_to_ned(np.eye(3)[i],anchor)[2] for i in range(3)])
def augment(model,direction,value,sigma=PRIOR_SIGMA):
 y=np.r_[model.observation_m,value];aa=np.vstack([model.ambiguity_design_m,np.zeros((1,len(model.satellites)))])
 bb=np.vstack([model.baseline_design,direction]);q=np.zeros((len(y),len(y)));q[:-1,:-1]=model.covariance_m2;q[-1,-1]=sigma*sigma
 return y,aa,bb,q
def solve(model,library,direction=None,value=None):
 args=(model.observation_m,model.ambiguity_design_m,model.baseline_design,model.covariance_m2)
 if direction is not None:args=augment(model,direction,value)
 return cl.solve_clambda(*args,length_m=LENGTH,lambda_bridge_path=library,strict=True,initial_candidate_count=8,strict_node_limit=1000000,timeout_seconds=60.)
def ready(x):return x is not None and x.global_optimum_certified and x.best is not None
def evidence(solution,model,direction,value):
 if not ready(solution):return {"candidate_available":False,"solver":jsonable(solution)}
 b=solution.best.baseline;n=solution.best.ambiguity;r=model.observation_m-model.baseline_design@b-model.ambiguity_design_m@n
 rw=np.linalg.solve(np.linalg.cholesky(model.covariance_m2),r)
 return {"candidate_available":True,"ambiguity":n.tolist(),"baseline_ecef_m":b.tolist(),"raw_whitened_residual_squared":float(rw@rw),"prior_residual_sigma":float((direction@b-value)/PRIOR_SIGMA),"constrained_objective_ratio_diagnostic":solution.ratio,"ratio_is_risk_calibrated":False,"formal_integer_acceptance_defined":False,"solver":jsonable(solution)}
def context(a):
 roots=aliases(a.roots);info_path=Path(roots["<EXT_REPRO_ROOT>"])/"inputs/BY2/INPUT.json";info=json.loads(info_path.read_text())
 cache=expand(info["cache_root"],roots);nav=[expand(x,roots) for x in info["navigation"]]
 libroot=Path(roots["<EXT_REPRO_BUILD>"])/"lib"
 return roots,info_path,info,cache,nav,libroot
def prepare(a):
 roots,ip,info,cache,nav,libroot=context(a);reader=CompactCacheReader(cache)
 assert len(reader)==info["pair_count"]==1509
 validate_compact_cache(cache,source_fingerprint=info["cache"]["source_fingerprint"],expected_pair_count=1509)
 inputs={str(ip):sha(ip)}
 for p in cache.iterdir():
  if p.is_file():inputs[str(p)]=sha(p)
 for i,p in enumerate(nav,1):assert sha(p)==info["source_files"][f"gnss{i}.nav"]["sha256"];inputs[str(p)]=sha(p)
 for name,d in LIBRARY_PINS.items():assert sha(libroot/name)==d;inputs[str(libroot/name)]=d
 for d in info["raw_hash_locks"].values():
  p=Path(roots["<RAW_ROOT>"])/d["relative_path"];assert sha(p)==d["sha256"];inputs[str(p)]=d["sha256"]
 rp=Path(roots["<CLEAN_ROOT>"])/"stages/CLEAN6_SENSOR_MODEL_V21/02_BASE_PROVIDERS/BY2/GO2_ATTITUDE_PRIOR.csv"
 inputs[str(rp)]=sha(rp);body=Path(roots["<RAW_ROOT>"])/"BY2_BY3/2026-03-06/高层数据/by2.txt"
 inputs[str(body)]=sha(body);assert inputs[str(body)]=="95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278"
 table=pd.read_csv(rp);times=[]
 for i in range(len(reader)):
  e=reader.pair(i)[0];times.append(315964800.+e.gps_week*604800.+e.gps_tow_seconds-e.leap_seconds-info["base_time"])
 rows=[]
 for target in TARGETS:
  i=int(np.searchsorted(times,target));one,two=reader.pair(i);t=times[i];rps=table[table.time<=t];prior=rps.iloc[-1]
  age=t-float(prior.time)
  rows.append({"target_s":target,"epoch_index":i,"gps_week":one.gps_week,"gps_tow_seconds":one.gps_tow_seconds,"time_s":t,"time_unix_s":t+info["base_time"],"raw_pair_exact":(one.gps_week,one.gps_tow_seconds)==(two.gps_week,two.gps_tow_seconds),"raw_accounting":raw.gps_l1_epoch_accounting(one,two).as_counts(),"rp_time_s":float(prior.time),"rp_age_s":age,"rp_available":bool(0<=age<=.02 and prior.source_status=="active"),"roll_rad":float(prior.roll_rad),"pitch_rad":float(prior.pitch_rad),"vertical_prior_m":float(-LENGTH*np.sin(prior.roll_rad)*np.cos(prior.pitch_rad))})
 assert len(set(r["epoch_index"] for r in rows))==12
 assert sha(a.code/FROZEN_EVAL)==FROZEN_EVAL_SHA
 pins=source_pins(a.code);pins[FROZEN_EVAL]=FROZEN_EVAL_SHA;pins["scripts/paper_rebuild/ar_tim_exploration_20261006/experiment.py"]=sha(Path(__file__))
 emit(a.stage/"PLAN.json",{"schema":"ar_tim_qualification.v1","scope":"BY2 12 preselected exact paired RAW epochs; not a navigation rerun","rows":rows,"inputs":inputs,"source_pins":pins,"cache":str(cache),"navigation":list(map(str,nav)),"lambda_library":str(libroot/"librtklib_legsa.so"),"satellite_library":str(libroot/"liblegsa_rtklib_bridge.so"),"base_time":info["base_time"],"baseline_length_m":LENGTH,"prior_sigma_m":PRIOR_SIGMA,"rp":str(rp),"selected_target_seconds":TARGETS,"max_real_spp_calls":12,"max_real_cils_calls":24,"max_seconds_per_cils":60,"max_nodes_per_cils":1000000,"lambda_seed_candidates":8,"absolute_worst_case_search_seconds":1440,"C_rule":"retain B only when A and B globally certified and integer vectors exactly equal; otherwise unresolved","candidate_acceptance_is_calibrated":False,"real_integer_truth_available":False,"online_reference_reads":0,"reference":REFERENCE,"reference_sha256":REFERENCE_SHA,"cold_code_spp_per_epoch":True,"spp_earth_rotation":"iterated_geometric","prior_noise_origin":"Fixed engineering sensitivity scale 0.030m; not calibrated or reference fitted","synthetic_unit_path":str(a.stage.parent/"SYNTHETIC_UNIT_RESULTS.json"),"synthetic_unit_sha256":sha(a.stage.parent/"SYNTHETIC_UNIT_RESULTS.json")})
 print(json.dumps(rows,indent=2))
def change_pivot(model,truth):
 ids=[model.pivot]+list(model.satellites);pivot=ids[1];new=[x for x in ids if x!=pivot];m=len(truth);T=np.zeros((m,m),int)
 for j,sat in enumerate(new):
  if sat!=model.pivot:T[j,model.satellites.index(sat)]=1
  T[j,0]-=1
 transform=np.block([[T,np.zeros_like(T)],[np.zeros_like(T),T]])
 aa=np.zeros_like(model.ambiguity_design_m);aa[m:]=np.eye(m)*raw.wavelength_m(pivot)
 return replace(model,pivot=pivot,satellites=tuple(new),observation_m=transform@model.observation_m,baseline_design=transform@model.baseline_design,ambiguity_design_m=aa,covariance_m2=transform@model.covariance_m2@transform.T),T@truth
def unit(a):
 roots,ip,info,cache,nav,libroot=context(a)
 oracle_path=a.code/"tests/paper_rebuild/test_ext_reproduction_backend.py"
 spec=importlib.util.spec_from_file_location("existing_oracle",oracle_path);oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
 library=libroot/"librtklib_legsa.so";assert sha(library)==LIBRARY_PINS[library.name]
 records=[];tol=2e-5
 for geometry,b in enumerate([np.array([0.,-.35,0.]),np.array([.10,-math.sqrt(.35**2-.1**2),0.])]):
  provider,e1,e2,sd=oracle.problem(b);model,_=backend.build_gps_l1_model(e1,e2,provider,oracle.ANCHOR)
  n=np.array([sd[s.sv_id-1]-sd[model.pivot.sv_id-1] for s in model.satellites]);d=vertical_row(oracle.ANCHOR);true=float(d@b)
  residual=model.observation_m-model.baseline_design@b-model.ambiguity_design_m@n;assert np.max(abs(residual))<tol
  for label,fault in [("nominal",0.),("prior_plus_0p15m",.15),("prior_minus_0p15m",-.15)]:
   aa=solve(model,library);bb=solve(model,library,d,true+fault)
   ra,rb=evidence(aa,model,d,true+fault),evidence(bb,model,d,true+fault)
   agree=ready(aa) and ready(bb) and np.array_equal(aa.best.ambiguity,bb.best.ambiguity)
   assert ready(aa) and np.array_equal(aa.best.ambiguity,n)
   records.append({"geometry":geometry,"case":label,"integer_truth":n.tolist(),"A_correct":bool(ready(aa) and np.array_equal(aa.best.ambiguity,n)),"B_correct":bool(ready(bb) and np.array_equal(bb.best.ambiguity,n)),"C_retained":bool(agree),"C_correct_retained":bool(agree and np.array_equal(bb.best.ambiguity,n)),"C_wrong_retained":bool(agree and not np.array_equal(bb.best.ambiguity,n)),"A":ra,"B":rb})
  swapped,_=backend.build_gps_l1_model(e2,e1,provider,oracle.ANCHOR);ns=np.array([-sd[s.sv_id-1]+sd[swapped.pivot.sv_id-1] for s in swapped.satellites])
  rev=solve(swapped,library);assert ready(rev) and np.array_equal(rev.best.ambiguity,ns) and np.linalg.norm(rev.best.baseline+b)<tol
  rotated,nr=change_pivot(model,n);rot=solve(rotated,library);assert ready(rot) and np.array_equal(rot.best.ambiguity,nr) and np.linalg.norm(rot.best.baseline-b)<tol
  records.extend([{"geometry":geometry,"case":"receiver_exchange","passed":True},{"geometry":geometry,"case":"integer_pivot_transform","passed":True}])
 # A common integer shift cancels under DD; unresolved half-cycle must fail input eligibility.
 provider,e1,e2,sd=oracle.problem(np.array([0.,-.35,0.]))
 shift=replace(e2,measurements=tuple(replace(m,cp_mes_cycles=m.cp_mes_cycles+7) for m in e2.measurements))
 mm,_=backend.build_gps_l1_model(e1,e2,provider,oracle.ANCHOR);ms,_=backend.build_gps_l1_model(e1,shift,provider,oracle.ANCHOR)
 assert np.max(abs(mm.observation_m-ms.observation_m))<1e-7
 records.append({"case":"common_integer_offset_cancels","passed":True})
 bad=replace(e2,measurements=tuple(replace(m,tracking_status=m.tracking_status&~4) for m in e2.measurements))
 rejected=False
 try:backend.build_gps_l1_model(e1,bad,provider,oracle.ANCHOR)
 except raw.RawBackendError:rejected=True
 assert rejected;records.append({"case":"unresolved_halfcycle_rejected","passed":True})
 emit(a.stage/"SYNTHETIC_UNIT_RESULTS.json",{"status":"PASS","data_mode":"synthetic_known_integer","oracle_source_sha256":sha(oracle_path),"library_sha256":sha(library),"cases":len(records),"cils_calls":16,"sigma_d_m":PRIOR_SIGMA,"prior_faults_m":[-.15,.15],"C_is_novel_method":False,"records":records})
 print("UNIT_PASS",len(records),json.dumps([{k:r[k] for k in ("case","geometry","A_correct","B_correct","C_retained") if k in r} for r in records]),flush=True)
def verify(plan,a,inputs=True):
 for p,d in plan["source_pins"].items():assert sha(a.code/p)==d,(p,"source pin")
 if inputs:
  for p,d in plan["inputs"].items():assert sha(p)==d,(p,"input pin")
def real(a):
 plan=json.loads((a.stage/"PLAN.json").read_text());assert a.execution_commit==subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.code,text=True).strip()
 verify(plan,a)
 reader=CompactCacheReader(Path(plan["cache"]));out=a.stage/"REAL";out.mkdir(exist_ok=False);records=[];calls=0;spp_calls=0
 ledger=a.stage/"CALL_LEDGER.jsonl"
 def log(item):
  with ledger.open("a") as f:f.write(json.dumps(item,allow_nan=False)+"\n");f.flush();os.fsync(f.fileno())
 with raw.RtklibBroadcastProvider(Path(plan["satellite_library"]),[Path(p) for p in plan["navigation"]]) as provider:
  for row in plan["rows"]:
   rec={**row,"A":None,"B":None,"C_retained":False,"failure":None}
   first,second=reader.pair(row["epoch_index"])
   try:
    spp_calls+=1;log({"stage":"SPP_START","epoch_index":row["epoch_index"],"spp_call":spp_calls})
    spp=raw.gps_l1_code_spp(first,provider,None,earth_rotation_delay="iterated_geometric")
    anchor=np.asarray(spp.position_ecef_m);model,audit=backend.build_gps_l1_model(first,second,provider,anchor)
    d=vertical_row(anchor);value=row["vertical_prior_m"];rec.update(spp=jsonable(spp),model=jsonable(model),geometry=audit)
    for method in ("A","B"):
     if method=="B" and not row["rp_available"]:rec["B"]={"candidate_available":False,"failure":"RP_UNAVAILABLE"};continue
     calls+=1;t=time.monotonic();log({"stage":"CILS_START","epoch_index":row["epoch_index"],"method":method,"cils_call":calls})
     try:
      solution=solve(model,plan["lambda_library"],None if method=="A" else d,None if method=="A" else value)
      rec[method]=evidence(solution,model,d,value)
      if ready(solution):
       ned=_ecef_vector_to_ned(solution.best.baseline,anchor);rec[method]["baseline_ned_m"]=ned.tolist()
       rec[method]["body_yaw_deg"]=cl.body_yaw_from_ned_baseline(ned)
     except (raw.RawBackendError,ValueError,np.linalg.LinAlgError) as ex:rec[method]={"candidate_available":False,"failure":type(ex).__name__+":"+str(ex)}
     rec[method]["elapsed_s"]=time.monotonic()-t
     log({"stage":"CILS_END","epoch_index":row["epoch_index"],"method":method,"candidate_available":rec[method]["candidate_available"]})
    rec["C_retained"]=bool(rec["A"] and rec["B"] and rec["A"]["candidate_available"] and rec["B"]["candidate_available"] and rec["A"]["ambiguity"]==rec["B"]["ambiguity"])
   except (raw.RawBackendError,ValueError,np.linalg.LinAlgError) as ex:rec["failure"]=type(ex).__name__+":"+str(ex)
   emit(out/("EPOCH_%03d.json"%row["epoch_index"]),rec);records.append(rec);log({"stage":"EPOCH_END","epoch_index":row["epoch_index"],"failure":rec["failure"]})
   print(row["target_s"],"A",bool(rec["A"] and rec["A"].get("candidate_available")),"B",bool(rec["B"] and rec["B"].get("candidate_available")),"C",rec["C_retained"],rec["failure"],flush=True)
 assert calls<=24 and spp_calls==len(records)==12
 verify(plan,a)
 emit(a.stage/"REAL_SEAL.json",{"status":"SEALED","execution_commit":a.execution_commit,"plan_sha256":sha(a.stage/"PLAN.json"),"scheduled_epochs":12,"spp_calls":spp_calls,"cils_calls":calls,"real_integer_correctness":"NA","epochs":records,"call_ledger_sha256":sha(ledger),"record_hashes":{p.name:sha(p) for p in out.glob("*.json")}})
 print("REAL_12_SEALED",flush=True)
def open_paths(path):
 records=[]
 for line in Path(path).read_text().splitlines():
  if not re.search(r"\bopen(?:at)?\(",line) or not re.search(r"= \d+(?:\s|$)",line):continue
  match=re.search(r'"((?:\\x[0-9a-fA-F]{2})*)"',line)
  if match:records.append((bytes.fromhex(match[1].replace("\\x","")).decode("utf-8",errors="replace"),"O_RDONLY" in line and "O_RDWR" not in line and "O_WRONLY" not in line))
 return records
def supervise(a):
 phase=a.child;assert phase in ("real","evaluate");trace=a.stage/(phase.upper()+"_IO.strace");receipt=a.stage/(phase.upper()+"_IO_AUDIT.json")
 assert not trace.exists() and not receipt.exists()
 roots=aliases(a.roots);plan=json.loads((a.stage/"PLAN.json").read_text());verify(plan,a,inputs=phase=="real")
 command=["strace","-f","-qq","-xx","-s","8192","-e","trace=open,openat,execve","-o",str(trace),sys.executable,str(Path(__file__).resolve()),phase,"--code",str(a.code),"--stage",str(a.stage),"--roots",str(a.roots)]
 if a.execution_commit:command+=["--execution-commit",a.execution_commit]
 started=time.monotonic()
 child=subprocess.Popen(command,start_new_session=True)
 try:exitcode=child.wait(timeout=2100)
 except subprocess.TimeoutExpired:
  os.killpg(child.pid,signal.SIGKILL);child.wait();exitcode=124
 paths=open_paths(trace);reference=str(expand(plan["reference"],roots));refs=[ro for p,ro in paths if p==reference]
 rawroot=roots["<RAW_ROOT>"].rstrip("/")+"/";rawpaths=[p for p,ro in paths if p.startswith(rawroot)]
 allowed=set(plan["inputs"]) if phase=="real" else {reference}
 unexpected=sorted(set(p for p in rawpaths if p not in allowed))
 expected=0 if phase=="real" else 1
 passed=exitcode==0 and len(refs)==expected and all(refs) and not unexpected and all(ro for p,ro in paths if p.startswith(rawroot))
 emit(receipt,{"passed":passed,"phase":phase,"exit_code":exitcode,"elapsed_s":time.monotonic()-started,"reference_successful_read_opens":len(refs),"expected_reference_opens":expected,"unexpected_raw_open_paths":unexpected,"all_raw_inputs_readonly":all(ro for p,ro in paths if p.startswith(rawroot)),"strace_sha256":sha(trace)})
 assert passed,(phase,exitcode,len(refs),unexpected)
def evaluate(a):
 plan=json.loads((a.stage/"PLAN.json").read_text());verify(plan,a,inputs=False)
 seal=json.loads((a.stage/"REAL_SEAL.json").read_text());audit=json.loads((a.stage/"REAL_IO_AUDIT.json").read_text())
 assert audit["passed"] and audit["reference_successful_read_opens"]==0
 assert sha(a.stage/"PLAN.json")==seal["plan_sha256"]
 assert sha(a.stage/"CALL_LEDGER.jsonl")==seal["call_ledger_sha256"]
 for name,digest in seal["record_hashes"].items():assert sha(a.stage/"REAL"/name)==digest
 from legsa_gins.paper_rebuild.hext.hx02_heading_evaluation import reference_yaw_ned
 roots=aliases(a.roots)
 # Exactly one read-only open, only after all twelve scheduled records are sealed.
 payload=expand(plan["reference"],roots).read_bytes();assert hashlib.sha256(payload).hexdigest()==plan["reference_sha256"]
 truth=reference_yaw_ned(payload,[r["time_unix_s"] for r in seal["epochs"]]);del payload
 rows=[];summary={}
 for rec,ref in zip(seal["epochs"],truth):
  for method in ("A","B","C"):
   candidate=rec["B"] if method=="C" and rec["C_retained"] else rec.get(method)
   available=bool(candidate and candidate.get("candidate_available") and candidate.get("body_yaw_deg") is not None)
   yaw=candidate["body_yaw_deg"] if available else None
   error=float((yaw-ref+180)%360-180) if available and np.isfinite(ref) else None
   rows.append({"method":method,"target_s":rec["target_s"],"time_s":rec["time_s"],"time_unix_s":rec["time_unix_s"],"epoch_index":rec["epoch_index"],"candidate_available":available,"body_yaw_deg":yaw,"reference_yaw_ned_deg":float(ref) if np.isfinite(ref) else None,"signed_yaw_error_deg":error,"integer_correctness":"NA","formal_integer_acceptance_defined":False,"epoch_failure":rec["failure"]})
 def stats(values):
  return {"count":len(values),"rmse_deg":float(np.sqrt(np.mean(np.square(values)))) if values else None,"mae_deg":float(np.mean(np.abs(values))) if values else None,"max_absolute_deg":float(np.max(np.abs(values))) if values else None}
 common=set.intersection(*[{r["epoch_index"] for r in rows if r["method"]==m and r["signed_yaw_error_deg"] is not None} for m in ("A","B")])
 for m in ("A","B","C"):
  mr=[r for r in rows if r["method"]==m];summary[m]={"scheduled":12,"native_candidate_count":sum(r["candidate_available"] for r in mr),"own_support":stats([r["signed_yaw_error_deg"] for r in mr if r["signed_yaw_error_deg"] is not None]),"common_AB_support":stats([r["signed_yaw_error_deg"] for r in mr if r["epoch_index"] in common and r["signed_yaw_error_deg"] is not None])}
 with (a.stage/"REAL_EVALUATION.csv").open("x",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
 emit(a.stage/"EVALUATION_SEAL.json",{"real_seal_sha256":sha(a.stage/"REAL_SEAL.json"),"reference_sha256":plan["reference_sha256"],"reference_read_opens_expected":1,"evaluator_source_sha256":FROZEN_EVAL_SHA,"new_runner_sha256":sha(Path(__file__)),"csv_sha256":sha(a.stage/"REAL_EVALUATION.csv"),"common_AB_epoch_indices":sorted(common),"summary":summary,"integer_truth":"UNAVAILABLE","interpretation":"Shared GNSS commercial reference consistency only; no risk calibration, no integer FIX validation."})
 print(json.dumps(summary,indent=2),flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","unit","real","evaluate","supervise"])
 for k in ("code","stage","roots"):p.add_argument("--"+k,type=Path,required=True)
 p.add_argument("--execution-commit");p.add_argument("--child",choices=["real","evaluate"]);a=p.parse_args();assert os.uname().sysname=="Linux";a.stage.mkdir(parents=True,exist_ok=True);globals()[a.phase](a)
if __name__=="__main__":main()
