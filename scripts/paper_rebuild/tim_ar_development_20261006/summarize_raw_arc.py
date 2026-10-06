#!/usr/bin/env python3
"""Derive portable metadata audit delivery and IO receipt; no raw reopening."""
from pathlib import Path
import argparse,csv,json,hashlib,re
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument("--stage",type=Path,required=True);p.add_argument("--trace",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--raw-root",required=True);p.add_argument("--clean-root",required=True);p.add_argument("--code-root",required=True);p.add_argument("--ext-root",required=True);a=p.parse_args()
 receipt=json.loads((a.stage/"RAW_ARC_RECEIPT.json").read_text())
 for n,h in receipt["result_hashes"].items():assert sha(a.stage/n)==h
 opens=[]
 for line in a.trace.read_text().splitlines():
  if not re.search(r"\bopen(?:at)?\(",line) or not re.search(r"= \d+(?:\s|$)",line):continue
  match=re.search(r'"((?:\\x[0-9a-fA-F]{2})*)"',line)
  if match:
   path=bytes.fromhex(match[1].replace("\\x","")).decode("utf-8",errors="replace")
   opens.append((path,"O_RDONLY" in line and "O_RDWR" not in line and "O_WRONLY" not in line))
 refs=[p for p,ro in opens if Path(p).name.startswith("trace_vrtk")]
 rawopens=[(p,ro) for p,ro in opens if p.startswith(a.raw_root.rstrip("/")+"/")]
 assert not refs and all(ro and p in receipt["input_pins"] for p,ro in rawopens)
 io={"passed":True,"reference_opens":len(refs),"raw_readonly_opens":len(rawopens),"raw_paths":sorted(set(p for p,ro in rawopens)),"trace_sha256":sha(a.trace),"scope":"single metadata child, source UBX and CSV hashes only; no estimator/reference"}
 with (a.stage/"IO_AUDIT.json").open("x") as f:json.dump(io,f,indent=2)
 families={}
 with (a.stage/"ALL_SIGNAL_COUNTS.csv").open() as f:
  for r in csv.DictReader(f):
   key=tuple(int(r[k]) for k in ("gnss_id","sig_id","freq_id"));families.setdefault(key,[]).append(r)
 rows=[]
 for key,values in sorted(families.items()):
  row={"gnss_id":key[0],"sig_id":key[1],"freq_id":key[2],"paired_epochs_present":len(values)}
  for k in ("receiver1_signals","receiver2_signals","common_unique_signals","common_cp_valid","common_cp_half_resolved","common_integer_compatible_phase_fields"):
   ns=[int(r[k]) for r in values];row[k+"_min"]=min(ns);row[k+"_max"]=max(ns)
  rows.append(row)
 with (a.out/"RAW_ARC_ALL_SIGNAL_SUMMARY.csv").open("x",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
 for original,new in (("EPOCH_METADATA.csv","RAW_ARC_EPOCH_METADATA.csv"),("ALL_SIGNAL_COUNTS.csv","RAW_ARC_ALL_SIGNAL_COUNTS.csv"),("GPS_L1_TRACKING.csv","RAW_ARC_GPS_L1_TRACKING.csv")):
  with (a.out/new).open("xb") as f:f.write((a.stage/original).read_bytes())
 aliases={"<RAW_ROOT>":a.raw_root,"<CLEAN_ROOT>":a.clean_root,"<CODE_ROOT>":a.code_root,"<EXT_REPRO_ROOT>":a.ext_root,"<TIM_AR_SCRATCH>":str(a.stage.parent)}
 def portable(x):
  if isinstance(x,dict):return {portable(k):portable(v) for k,v in x.items()}
  if isinstance(x,list):return [portable(v) for v in x]
  if isinstance(x,str):
   for k,v in sorted(aliases.items(),key=lambda kv:len(kv[1]),reverse=True):x=x.replace(v,k)
  return x
 result=portable(receipt);result["IO_AUDIT"]=portable(io);result["source_receipt_sha256"]=sha(a.stage/"RAW_ARC_RECEIPT.json");result["summary_script_sha256"]=sha(Path(__file__))
 with (a.out/"RAW_ARC_SUMMARY.json").open("x") as f:json.dump(result,f,indent=2,ensure_ascii=False)
 print(json.dumps(rows,indent=2))
if __name__=="__main__":main()
