"""Raw-only feasibility check; neither truth validation nor a solver provider.

Sample first timestamped message per 0.2 s, choose two highest force feet, compare
no-slip kinematic proxy to two explicit SDK velocity frame hypotheses.
No GNSS/trace, frame tuning, contact threshold fitting, or estimator output.
"""
from pathlib import Path
import argparse, csv, json, sys
import numpy as np
import yaml
from legsa_gins.datasets.by2.go2_body_state_parser import _message_to_row

def rows(path):
    block=[]
    with Path(path).open(encoding='utf-8',errors='ignore') as f:
        for line in f:
            if line.strip()=='---':
                yield block;block=[]
            else:block.append(line.rstrip('\n'))
        if block:yield block

def run(paths, out):
    results=[]
    for seq,key,start,end in [('BY2','by2_go2_body',1772784066.,1772784340.),('BY2H','by2h_go2_body',1772784413.,1772784683.),('BY2O','by2o_go2_body',1772783586.,1772783963.)]:
        all_blocks=0; sampled=0; complete=0; last=-np.inf; records=[]
        for block in rows(paths[key]):
            all_blocks+=1
            # Read timestamp cheaply before invoking the diagnostic parser.
            sec=ns=None
            for line in block:
                s=line.strip()
                if s.startswith('sec:'):sec=float(s.split(':',1)[1])
                elif s.startswith('nanosec:'):ns=float(s.split(':',1)[1])
                if sec is not None and ns is not None:break
            if sec is None or ns is None:continue
            t=sec+ns*1e-9
            if not start<=t<=end or t-last<0.2:continue
            last=t;sampled+=1; d=_message_to_row(block)
            keys=['gyro_x','gyro_y','gyro_z','roll_rad','pitch_rad','yaw_rad']+[f'go2_velocity_{i}' for i in range(3)]+[f'foot_force_{i}' for i in range(4)]+[f'foot_position_body_{i}' for i in range(12)]+[f'foot_speed_body_{i}' for i in range(12)]
            if any(d[k] is None or not np.isfinite(d[k]) for k in keys):continue
            complete+=1
            w=np.array([d[k] for k in ['gyro_x','gyro_y','gyro_z']])
            v=np.array([d[f'go2_velocity_{i}'] for i in range(3)])
            feet=np.array([d[f'foot_position_body_{i}'] for i in range(12)]).reshape(4,3)
            fd=np.array([d[f'foot_speed_body_{i}'] for i in range(12)]).reshape(4,3)
            force=np.array([d[f'foot_force_{i}'] for i in range(4)])
            ids=np.argsort(force,kind='stable')[-2:]
            proxy=-fd-np.cross(w,feet)
            vp=proxy[ids].mean(axis=0)
            roll,pitch,yaw=[d[k] for k in ['roll_rad','pitch_rad','yaw_rad']]
            cr,sr=np.cos(roll),np.sin(roll);cp,sp=np.cos(pitch),np.sin(pitch);cy,sy=np.cos(yaw),np.sin(yaw)
            R=np.array([[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],[sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]])
            records.append([t,np.linalg.norm(vp[:2]-v[:2]),np.linalg.norm(vp[:2]-(R.T@v)[:2]),np.linalg.norm(proxy[ids[0],:2]-proxy[ids[1],:2]),np.linalg.norm(v[:2]),np.all(force[ids]>0),np.count_nonzero(fd),np.count_nonzero(feet)])
        a=np.array(records)
        q={'sequence':seq,'source_config_key':key,'window_start_unix':start,'window_end_unix':end,'message_blocks_total':all_blocks,'selected_5hz_records':sampled,'finite_all_required_fields':complete,'sample_period_min_s':float(np.diff(a[:,0]).min()),'sample_max_gap_s':float(np.diff(a[:,0]).max()),'sdk_speed_horizontal_p50_mps':float(np.median(a[:,4])),'body_hypothesis_proxy_difference_median_mps':float(np.median(a[:,1])),'odom_hypothesis_proxy_difference_median_mps':float(np.median(a[:,2])),'two_feet_disagreement_median_mps':float(np.median(a[:,3])),'two_feet_disagreement_p95_mps':float(np.quantile(a[:,3],.95)),'both_selected_forces_positive_fraction':float(a[:,5].mean()),'nonzero_foot_speed_fraction':float((a[:,6]>0).mean()),'nonzero_foot_position_fraction':float((a[:,7]>0).mean())}
        results.append(q);print(json.dumps(q),flush=True)
    out.mkdir(parents=True,exist_ok=True)
    with (out/'LEG_INPUT_FEASIBILITY.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=results[0]);w.writeheader();w.writerows(results)
    (out/'LEG_INPUT_FEASIBILITY.json').write_text(json.dumps({'diagnostic_only':True,'data_mode':'real_raw_input_only','synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False,'gnss_data_read':False,'raw_immutable':True,'sampling':'first timestamp after >=0.2s since last; fixed main-sequence windows','contact_proxy':'top two foot_force values; diagnostic hypothesis, not validated contact classification','formula':'v_body=-foot_speed_body-gyro cross foot_position_body','gyro_bias_removed':False,'frame_identified':False,'independent_velocity_truth':False,'rows':results},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--local-paths',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    run(yaml.safe_load(Path(a.local_paths).read_text())['paths'],Path(a.out))
