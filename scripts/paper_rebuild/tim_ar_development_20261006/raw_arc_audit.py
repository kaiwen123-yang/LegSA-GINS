#!/usr/bin/env python3
"""Fixed BY2 [80,82] metadata audit. No SPP, C-ILS, navigation, or reference."""
from pathlib import Path
from collections import defaultdict,Counter
from dataclasses import asdict
import argparse,csv,hashlib,json,os,re,subprocess,sys,time
import numpy as np
from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw
from legsa_gins.paper_rebuild.horizontal_literature.reproduction_prepare import aliases,expand
LOW,HIGH,BASE=80.,82.,1772784000.
def digest(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def emit(p,v):
 with Path(p).open("x",encoding="utf-8") as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False)
def writecsv(p,rows):
 if not rows:return
 with Path(p).open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
def identity(i):return raw.identity_text(i)
def ts(e):return 315964800.+e.gps_week*604800.+e.gps_tow_seconds-e.leap_seconds-BASE
def gpsl1(i):return i.gnss_id==0 and i.sig_id==0 and i.freq_id==0
def phasevalid(m):
 try:raw.integer_compatible_carrier_cycles(m);return True
 except raw.RawBackendError:return False
def run(a):
 assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=a.code,text=True).strip()==a.execution_commit
 roots=aliases(a.roots);ip=Path(roots["<EXT_REPRO_ROOT>"])/"inputs/BY2/INPUT.json";info=json.loads(ip.read_text());assert info["base_time"]==BASE
 sourcepins={"scripts/paper_rebuild/tim_ar_development_20261006/raw_arc_audit.py":digest(Path(__file__)),"src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py":digest(a.code/"src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py")}
 receipts={str(ip):digest(ip)};epochs={};decodecounts={}
 for rx in (1,2):
  rp=info["raw_hash_locks"]["gnss%d"%rx];original=Path(roots["<RAW_ROOT>"])/rp["relative_path"];assert digest(original)==rp["sha256"];receipts[str(original)]=rp["sha256"]
  up=info["source_files"]["gnss%d.ubx"%rx];path=expand(up["source"],roots);payload=path.read_bytes();assert hashlib.sha256(payload).hexdigest()==up["sha256"];receipts[str(path)]=up["sha256"]
  subset=[];total=0
  for cls,ident,body in raw.iter_ubx_frames(payload):
   if (cls,ident)!=(2,0x15):continue
   e=raw.decode_rawx(body);total+=1
   if LOW<=ts(e)<=HIGH:subset.append(e)
  epochs[rx]=subset;decodecounts[str(rx)]=total
 # Tracking is evaluated in each receiver's original chronological stream, not a cache with shared timestamps.
 bykey={};events=[];signalstate={};tokens={}
 for rx in (1,2):
  track=raw.TrackingContinuity();groups=defaultdict(list)
  for e in epochs[rx]:
   key=(e.gps_week,e.gps_tow_seconds);groups[key].append(e)
   for m in e.measurements:
    if not gpsl1(m.identity):continue
    flag=track.update(rx,e,m);sid=identity(m.identity);sk=(rx,sid);old=signalstate.get(sk);t=ts(e)
    gap=old is not None and t-old[0]>.21
    arc=1 if old is None else old[1]+int(flag.arc_reset_due_to_tracking or gap)
    signalstate[sk]=(t,arc)
    ev={"receiver":rx,"time_s":t,"gps_week":e.gps_week,"gps_tow_seconds":e.gps_tow_seconds,"signal":sid,"locktime_ms":m.locktime_ms,"cno_dbhz":m.cno_dbhz,"pr_std_code":m.pr_std_code,"cp_std_code":m.cp_std_code,"tracking_status":m.tracking_status,"arc_id":arc,"gap_reset":gap,**asdict(flag)}
    events.append(ev);tokens[(rx,key,sid)]=(arc,flag)
  bykey[rx]=groups
 keys=sorted(set(bykey[1])&set(bykey[2]));pairrows=[];allrows=[];supports=[]
 for key in keys:
  left,right=bykey[1][key],bykey[2][key]
  if len(left)!=1 or len(right)!=1:continue
  e1,e2=left[0],right[0];assert (e1.gps_week,e1.gps_tow_seconds)==(e2.gps_week,e2.gps_tow_seconds)
  g=[]
  for e in (e1,e2):
   gg=defaultdict(list)
   for m in e.measurements:gg[m.identity].append(m)
   g.append(gg)
  common={i for i in set(g[0])&set(g[1]) if len(g[0][i])==len(g[1][i])==1}
  families=sorted({(i.gnss_id,i.sig_id,i.freq_id) for i in set(g[0])|set(g[1])})
  for fam in families:
   ids=[i for i in common if (i.gnss_id,i.sig_id,i.freq_id)==fam]
   allrows.append({"time_s":ts(e1),"gnss_id":fam[0],"sig_id":fam[1],"freq_id":fam[2],"receiver1_signals":sum((i.gnss_id,i.sig_id,i.freq_id)==fam for i in g[0]),"receiver2_signals":sum((i.gnss_id,i.sig_id,i.freq_id)==fam for i in g[1]),"common_unique_signals":len(ids),"common_cp_valid":sum(g[0][i][0].carrier_valid and g[1][i][0].carrier_valid for i in ids),"common_cp_half_resolved":sum(g[0][i][0].carrier_valid and g[1][i][0].carrier_valid and g[0][i][0].half_cycle_valid and g[1][i][0].half_cycle_valid for i in ids),"common_integer_compatible_phase_fields":sum(phasevalid(g[0][i][0]) and phasevalid(g[1][i][0]) for i in ids)})
  eligible=[]
  for i in sorted(common):
   if not gpsl1(i) or not all(raw.strict_raw_tracking_eligible(gg[i][0]) for gg in g):continue
   sid=identity(i);arcs=[tokens[(rx,key,sid)] for rx in (1,2)]
   if any(x[1].receiver_clock_reset or x[1].time_reversal_detected for x in arcs):continue
   eligible.append((sid,arcs[0][0],arcs[1][0]))
  accounting=raw.gps_l1_epoch_accounting(e1,e2).as_counts()
  pairrows.append({"time_s":ts(e1),"gps_week":key[0],"gps_tow_seconds":key[1],"exact_pair":True,**accounting,"strict_gps_l1_common_count":len(eligible),"strict_signals":";".join(t[0] for t in eligible)})
  supports.append((ts(e1),set(eligible)))
 # Enumerate metadata-feasible contiguous subintervals, report inclusion-maximal ones.
 spans=[]
 for i in range(len(supports)):
  common=supports[i][1].copy()
  for j in range(i,len(supports)):
   if j>i and not 0<supports[j][0]-supports[j-1][0]<=.21:break
   common &= supports[j][1]
   if len(common)<4:break
   spans.append((i,j,sorted(common)))
 maximal=[s for s in spans if not any(t[0]<=s[0] and t[1]>=s[1] and (t[0],t[1])!=(s[0],s[1]) for t in spans)]
 intervals=[{"start_s":supports[i][0],"end_s":supports[j][0],"paired_epochs":j-i+1,"duration_s":supports[j][0]-supports[i][0],"common_continuous_signal_count":len(ids),"signals":[x[0] for x in ids],"receiver_arc_tokens":ids,"candidate_metadata_pivot":ids[0][0],"pivot_is_elevation_qualified":False} for i,j,ids in maximal]
 pairing={"receiver1_window_epochs":len(epochs[1]),"receiver2_window_epochs":len(epochs[2]),"exact_unique_pairs":len(pairrows),"unpaired_receiver1_keys":[list(k) for k in sorted(set(bykey[1])-set(bykey[2]))],"unpaired_receiver2_keys":[list(k) for k in sorted(set(bykey[2])-set(bykey[1]))],"duplicate_receiver1_keys":[list(k) for k,v in bykey[1].items() if len(v)>1],"duplicate_receiver2_keys":[list(k) for k,v in bykey[2].items() if len(v)>1]}
 counters={k:sum(bool(r[k]) for r in events) for k in ("tracking_lock_reset_detected","half_cycle_state_changed","carrier_validity_changed","receiver_clock_reset","time_reversal_detected","gap_reset","first_observation","cycle_slip_detected")}
 writecsv(a.stage/"EPOCH_METADATA.csv",pairrows);writecsv(a.stage/"ALL_SIGNAL_COUNTS.csv",allrows);writecsv(a.stage/"GPS_L1_TRACKING.csv",events)
 receipt={"execution_commit":a.execution_commit,"window_s":[LOW,HIGH],"base_time":BASE,"phase":"METADATA_ONLY","SPP_calls":0,"CILS_calls":0,"navigation_calls":0,"reference_reads":0,"source_pins":sourcepins,"input_pins":receipts,"decoded_fullfile_RAWX_counts":decodecounts,"pairing":pairing,"tracking_event_counts":counters,"metadata_feasible_intervals":intervals,"continuous_before_window":"UNKNOWN_LEFT_CENSORED","qualified_geometry":False,"qualified_integer_fix":False,"contains_at_least_10_epoch_metadata_interval":any(x["paired_epochs"]>=10 for x in intervals),"result_hashes":{p.name:digest(p) for p in a.stage.glob("*.csv")}}
 for p,h in sourcepins.items():assert digest(a.code/p)==h
 emit(a.stage/"RAW_ARC_RECEIPT.json",receipt)
 print(json.dumps({"pairing":pairing,"tracking":counters,"intervals":intervals},ensure_ascii=False,indent=2),flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument("--code",type=Path,required=True);p.add_argument("--stage",type=Path,required=True);p.add_argument("--roots",type=Path,required=True);p.add_argument("--execution-commit",required=True);a=p.parse_args();assert os.uname().sysname=="Linux";a.stage.mkdir(parents=True,exist_ok=False);run(a)
if __name__=="__main__":main()
