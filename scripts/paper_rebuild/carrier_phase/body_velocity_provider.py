#!/usr/bin/env python3
"""Build a body-FRD xy provider from a dataset-qualified raw high-level log."""
import argparse,csv,hashlib,json,os
from collections import Counter
from pathlib import Path
from legsa_gins.paper_rebuild.body_velocity import FIELDS,iter_messages,parse_sample

def run(a):
    if os.uname().sysname!="Linux":raise RuntimeError("run in Ubuntu WSL")
    if a.output.exists():raise ValueError("preserve existing provider")
    a.output.mkdir(parents=True)
    counts=Counter(); previous=None; first=None; last=None
    path=a.output/"BODY_VELOCITY.csv"
    with path.open("x",newline="") as stream:
        out=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator="\n");out.writeheader()
        for message in iter_messages(a.raw):
            sample=parse_sample(message,base_time_s=a.base_time,input_frame=a.input_frame)
            if previous is not None and sample.time<=previous:
                raise ValueError("raw timestamp duplicate or order violation")
            previous=sample.time
            if sample.time<a.start or sample.time>a.end:continue
            out.writerow(sample.csv_row(a.std)); counts[sample.reason]+=1
            if first is None:first=sample.time
            last=sample.time
    if first is None:raise ValueError("no raw samples in requested scope")
    manifest={"raw_source":str(a.raw),"raw_bytes":a.raw.stat().st_size,
       "provider":str(path),"provider_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
       "base_time":a.base_time,"window":[a.start,a.end],"first_time":first,"last_time":last,
       "counts":dict(counts),"source_frame":a.input_frame,"output_frame":"body_frd",
       "frame_evidence":str(a.frame_evidence),"std_xy_mps":a.std,"scale":1.,
       "covariance_status":"fixed engineering working model; not calibrated probability",
       "source_point_to_IMU_lever_arm":"assumed zero; physical point uncertainty unresolved",
       "GNSS_read_count":0,"reference_read_count":0,"attitude_rotation_used":False,
       "interpolation_used":False,"raw_failure_rows_retained":True}
    (a.output/"MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("raw","output","frame-evidence"):p.add_argument("--"+key,type=Path,required=True)
    p.add_argument("--input-frame",choices=["dataset_supported_body_flu"],required=True)
    for key in ("base-time","start","end","std"):p.add_argument("--"+key,type=float,required=True)
    run(p.parse_args())
