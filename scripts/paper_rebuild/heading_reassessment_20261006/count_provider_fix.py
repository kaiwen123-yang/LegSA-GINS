#!/usr/bin/env python3
"""Exact-iTOW joins of current natural R5 flags to raw NAV-PVT; never runs solver."""
from pathlib import Path
import argparse,collections,csv,hashlib,json
import numpy as np
from legsa_gins.paper_rebuild.hext import heading_provider as hp
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths,REGISTRY,CALIBRATED_CONTRACT
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(a):
 results=[];pins=[]
 for name in ("BY2","BY2H","BY2O"):
  seq=load_sequence_paths(name,a.local_paths,a.code/REGISTRY,a.code/CALIBRATED_CONTRACT)
  lock={r["relative_path"]:r["sha256"] for r in csv.DictReader(seq.hash_lock.open())}
  flags=[]
  for raw in (seq.gnss1_raw,seq.gnss2_raw):
   expected=lock[raw.relative_to(seq.raw_root).as_posix()];assert sha(raw)==expected
   flags.append(hp.pvt_flags_from_csv_bytes(raw.read_bytes(),expected_sha256=expected))
  provider=a.provider_root/name/"R5.gnss";table=np.loadtxt(provider)
  rows=table[(table[:,0]>seq.window[0])&(table[:,0]<=seq.window[1])]
  for field,column in (("all_provider_epochs",None),("position_valid",15),("receiver_velocity_valid",16),("yaw_valid",17)):
   counts=collections.Counter();total=missing=0
   for row in rows:
    if column is not None and row[column]!=1:continue
    total+=1;key=hp.time_to_itow_ms(str(row[0]),gps_week=2408,base_time=seq.base_time)
    if key not in flags[0] or key not in flags[1]:missing+=1;continue
    states=[(f[key]>>6)&3 for f in flags]
    counts["gnss1_"+str(states[0])]+=1;counts["gnss2_"+str(states[1])]+=1
    counts["both_fixed" if states==[2,2] else "not_both_fixed"]+=1
    counts["gnss1_nonfixed"]+=int(states[0]!=2)
    counts["either_float"]+=int(1 in states)
   results.append({"sequence":name,"source":field,"epochs":total,"missing_pvt_join":missing,"both_fixed":counts["both_fixed"],"not_both_fixed":counts["not_both_fixed"],"gnss1_fixed":counts["gnss1_2"],"gnss1_float":counts["gnss1_1"],"gnss1_no_carrier":counts["gnss1_0"],"gnss1_reserved":counts["gnss1_3"],"gnss2_fixed":counts["gnss2_2"],"gnss2_float":counts["gnss2_1"],"gnss2_no_carrier":counts["gnss2_0"],"either_float":counts["either_float"]})
  pins.append({"sequence":name,"window_start_exclusive":seq.window[0],"window_end_inclusive":seq.window[1],"provider":"<PROTOCOL_V3_PROVIDERS>/"+name+"/R5.gnss","provider_sha256":sha(provider),"raw_gnss1_sha256":sha(seq.gnss1_raw),"raw_gnss2_sha256":sha(seq.gnss2_raw)})
 a.out.mkdir(parents=True,exist_ok=True)
 with (a.out/"PROVIDER_FIX_COUNTS.csv").open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=results[0]);w.writeheader();w.writerows(results)
 with (a.out/"PROVIDER_FIX_COUNTS.json").open("x") as f:json.dump({"raw_only_input_join":True,"reference_reads":0,"native_solver_calls":0,"carrSoln_encoding":{"0":"no carrier solution","1":"FLOAT","2":"FIXED","3":"reserved"},"interpretation":"Validity flags are provider admission, not proof EKF accepted every row. Native state has no FIX label. Main R5 yaw gates both raw PVT carrSoln=2; position and RV retain independent exact-epoch inputs.","pins":pins,"rows":results},f,indent=2)
 print(json.dumps(results,indent=2))
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for k in ("code","local-paths","provider-root","out"):p.add_argument("--"+k,type=Path,required=True)
 run(p.parse_args())
