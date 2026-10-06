#!/usr/bin/env python3
"""Raw-only body-z feasibility; no solver, GNSS, reference, fitting or calibration."""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json
import numpy as np
import yaml
from legsa_gins.datasets.by2.go2_body_state_parser import _message_to_row

def run(a):
    spec=importlib.util.spec_from_file_location("raw_inspect",a.code/"scripts/paper_rebuild/research_audit_20261006/inspect_leg_inputs.py")
    lib=importlib.util.module_from_spec(spec);spec.loader.exec_module(lib)
    paths=yaml.safe_load(a.local_paths.read_text())["paths"]
    results=[]
    for seq,key,start,end in [('BY2','by2_go2_body',1772784066.,1772784340.),('BY2H','by2h_go2_body',1772784413.,1772784683.),('BY2O','by2o_go2_body',1772783586.,1772783963.)]:
        path=Path(paths[key]);records=[];last=-np.inf
        for block in lib.rows(path):
            sec=ns=None
            for line in block:
                s=line.strip()
                if s.startswith('sec:'):sec=float(s.split(':',1)[1])
                elif s.startswith('nanosec:'):ns=float(s.split(':',1)[1])
                if sec is not None and ns is not None:break
            if sec is None or ns is None:continue
            t=sec+ns*1e-9
            if not start<=t<=end or t-last<.2:continue
            last=t;d=_message_to_row(block)
            keys=['gyro_x','gyro_y','gyro_z']+[f'go2_velocity_{i}' for i in range(3)]+[f'foot_force_{i}' for i in range(4)]+[f'foot_position_body_{i}' for i in range(12)]+[f'foot_speed_body_{i}' for i in range(12)]
            if any(d[k] is None or not np.isfinite(d[k]) for k in keys):raise ValueError("nonfinite required field")
            w=np.array([d[k] for k in ['gyro_x','gyro_y','gyro_z']])
            v=np.array([d[f'go2_velocity_{i}'] for i in range(3)])
            feet=np.array([d[f'foot_position_body_{i}'] for i in range(12)]).reshape(4,3)
            fd=np.array([d[f'foot_speed_body_{i}'] for i in range(12)]).reshape(4,3)
            forces=np.array([d[f'foot_force_{i}'] for i in range(4)])
            ids=np.argsort(forces,kind='stable')[-2:]
            proxy=-fd-np.cross(w,feet);vp=proxy[ids].mean(axis=0)
            records.append([t,v[2],vp[2],proxy[ids[0],2]-proxy[ids[1],2],int(np.all(forces[ids]>0)),d.get('error_code')])
        b=np.array(records,dtype=float);delta=b[:,2]-b[:,1]
        q={"sequence":seq,"source_config_key":key,"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"samples":len(b),"sdk_z_nonzero_fraction":float(np.mean(b[:,1]!=0)),"sdk_z_mean_mps":float(np.mean(b[:,1])),"sdk_z_std_mps":float(np.std(b[:,1])),"sdk_z_abs_p95_mps":float(np.quantile(abs(b[:,1]),.95)),"proxy_minus_sdk_z_mean_mps":float(np.mean(delta)),"proxy_minus_sdk_z_abs_median_mps":float(np.median(abs(delta))),"proxy_minus_sdk_z_abs_p95_mps":float(np.quantile(abs(delta),.95)),"proxy_sdk_z_correlation":float(np.corrcoef(b[:,1],b[:,2])[0,1]),"two_feet_z_difference_abs_median_mps":float(np.median(abs(b[:,3]))),"two_feet_z_difference_abs_p95_mps":float(np.quantile(abs(b[:,3]),.95)),"both_forces_positive_fraction":float(np.mean(b[:,4]))}
        results.append(q);print(json.dumps(q),flush=True)
    a.out.mkdir(parents=True,exist_ok=True)
    with (a.out/"VERTICAL_INPUT_CHECK.csv").open("x",newline="") as f:
        w=csv.DictWriter(f,fieldnames=results[0]);w.writeheader();w.writerows(results)
    with (a.out/"VERTICAL_INPUT_CHECK.json").open("x") as f:json.dump({"raw_only":True,"trace_reads":0,"gnss_reads":0,"solver_runs":0,"reference_tuning":False,"body_velocity_frame_independently_calibrated":False,"contact_proxy_validated":False,"calibration_claim":False,"sampling":"same fixed three main windows and >=0.2 s cadence as prior raw-only check; top two forces, no threshold fitting","formula":"v_proxy=-foot_speed_body-gyro cross foot_position_body","rows":results},f,indent=2)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--code",type=Path,required=True);p.add_argument("--local-paths",type=Path,required=True);p.add_argument("--out",type=Path,required=True);run(p.parse_args())
