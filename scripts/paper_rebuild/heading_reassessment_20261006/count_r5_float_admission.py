#!/usr/bin/env python3
"""Read-only join of original GNSS1 NAV-PVT to sealed R5 GNSS18 provider.
No navigation solver/evaluator/reference; no recalculated providers or parameters.
"""
from pathlib import Path
import argparse,csv,datetime,hashlib,importlib.util,io,json,os,struct,zipfile
import numpy as np
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
def main(a):
 assert os.uname().sysname=="Linux"
 module=a.code/"scripts/paper_rebuild/heading_reassessment_20261006/audit_raw_inputs.py"
 spec=importlib.util.spec_from_file_location("raw_audit",module);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 plan=json.loads(a.plan.read_text());prior=a.code/"docs/paper_rebuild/TIM_EVIDENCE_20261005/data_and_selection"
 old={r["member"]:r for r in json.loads((prior/"ZIP_RAW_SELECTED_PROFILE.json").read_text())}
 zp=a.raw/"fixpositon数据/vrtk2_a87c6e_2026-01-05-11-16-59_minimal.zip"
 zh=sha(zp);assert zh==json.loads((prior/"ZIP_CONTAINER_IDENTITY.json").read_text())["sha256"]
 base=datetime.datetime(2026,1,5,tzinfo=datetime.timezone.utc).timestamp();rows=[];pins=[]
 with zipfile.ZipFile(zp) as z:
  for seq in ["NMB1","NMB2","NMB3","NMB4"]:
   info=plan["sequences"][seq];name=info["receiver_folder"]+"/gnss1-raw.csv"
   h=m.HashReader(z.open(name));f=io.TextIOWrapper(io.BufferedReader(h),encoding="utf-8",newline="");pv=[]
   for r in csv.DictReader(f):
    if r["name"]!="UBX-NAV-PVT":continue
    p=m.payload(r,1,7);assert len(p)==92
    dt=datetime.datetime(struct.unpack_from("<H",p,4)[0],*p[6:11],tzinfo=datetime.timezone.utc)
    t=dt.timestamp()+struct.unpack_from("<i",p,16)[0]*1e-9-base
    ok=p[20]==3 and bool(p[21]&1);c=(p[21]>>6)&3
    state="INVALID" if not ok else {0:"OTHER_VALID",1:"FLOAT",2:"FIX",3:"RESERVED"}[c]
    pv.append((t,state))
   f.close();assert h.n==z.getinfo(name).file_size and h.h.hexdigest()==old[name]["sha256"]
   source=info["providers"]["GNSS18.gnss"];gp=Path(source["path"]);assert sha(gp)==source["sha256"]
   g=np.loadtxt(gp);pv.sort();t=np.array([v[0] for v in pv]);states=np.array([v[1] for v in pv]);assert len(set(t))==len(t)
   j=np.searchsorted(t,g[:,0]);assert (j<len(t)).all();assert np.array_equal(t[j],g[:,0])
   joined=states[j];w=info["native_window"]
   for domain,mask in [("FULL_GNSS18",np.ones(len(g),dtype=bool)),("NATIVE_WINDOW",(g[:,0]>=w[0])&(g[:,0]<=w[1]))]:
    for state in ["FIX","FLOAT","OTHER_VALID","INVALID","RESERVED"]:
     x=mask&(joined==state)
     rows.append({"sequence":seq,"domain":domain,"gnss1_state":state,"epochs":int(x.sum()),"position_valid":int(np.sum(x&(g[:,15]==1))),"receiver_velocity_valid":int(np.sum(x&(g[:,16]==1))),"yaw_valid":int(np.sum(x&(g[:,17]==1))),"first_time_utc_day_s":float(g[x,0][0]) if x.any() else None,"last_time_utc_day_s":float(g[x,0][-1]) if x.any() else None})
   pins.append({"sequence":seq,"member":name,"member_sha256":h.h.hexdigest(),"GNSS18_path":str(gp),"GNSS18_sha256":source["sha256"],"native_window":w,"provider_rows":len(g),"PVT_rows":len(t),"missing_join":0,"join_time_tolerance_s":0})
   print(seq,[(r["gnss1_state"],r["epochs"],r["position_valid"],r["receiver_velocity_valid"],r["yaw_valid"]) for r in rows if r["sequence"]==seq and r["domain"]=="NATIVE_WINDOW"],flush=True)
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.with_suffix(".csv").open("x",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
 result={"status":"COMPLETE_READ_ONLY_PROVIDER_JOIN","script_sha256":sha(__file__),"decoder_script_sha256":sha(module),"R5_plan_sha256":sha(a.plan),"ZIP_sha256":zh,"selected_members":4,"reference_reads":0,"native_navigation_calls":0,"evaluator_calls":0,"meaning":"Counts are existing GNSS18 provider admission flags inside recorded native start/end, not independently counted final EKF updates or accuracy evidence.","pins":pins,"rows":rows}
 a.out.with_suffix(".json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for k in ["code","raw","plan","out"]:p.add_argument("--"+k,type=Path,required=True)
 main(p.parse_args())
