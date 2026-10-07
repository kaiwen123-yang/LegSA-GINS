#!/usr/bin/env python3
"""Read-only reference/source audit. No NAV, standard route, evaluator or solver."""
import argparse, ast, csv, hashlib, io, json, zipfile
from collections import Counter
from pathlib import Path
import numpy as np


def sha(b): return hashlib.sha256(b).hexdigest()
def stats(a):
    a=np.asarray(a,dtype=float).ravel(); f=a[np.isfinite(a)]
    return dict(n=len(a),finite_n=len(f),min=float(f.min()) if len(f) else None,median=float(np.median(f)) if len(f) else None,p95=float(np.percentile(f,95)) if len(f) else None,max=float(f.max()) if len(f) else None)
def arr(rows,fields): return np.array([[float(r[k]) for k in fields] for r in rows])
def tm(rows): return arr(rows,['header.stamp.secs','header.stamp.nsecs']) @ np.array([1.,1e-9])
def writecsv(p,rows):
    if not rows:return
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--existing-status',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    planpath=Path(a.plan);plan=json.loads(planpath.read_text());seq=plan['sequences'][0];ref=seq['reference'];pre=ref['member'].rsplit('/',1)[0]+'/';base=seq['base_time_unix_s'];windows=dict(FULL=seq['full_window_s'],GAP=plan['gap_contract']['position_gap'])
    inputs={str(planpath):sha(planpath.read_bytes()),str(Path(a.existing_status)):sha(Path(a.existing_status).read_bytes())};schemas=[]
    with zipfile.ZipFile(ref['path']) as z:
        def read(n):
            b=z.read(n);inputs[n]=dict(sha256=sha(b),bytes=len(b));return list(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))))
        tr=read(ref['member']);assert inputs[ref['member']]['sha256']==ref['sha256']
        ge=read(pre+'user_io-out-poi_geodetic.csv');od=read(pre+'user_io-out-poi_odometry.csv');st=read(pre+'user_io-out-odom_status.csv')
        gn=[read(pre+'gnss%d-status.csv'%i) for i in [1,2]]
        folders=sorted({n.split('/')[0] for n in z.namelist() if n.endswith('user_io-out-poi_geodetic.csv')})
        for f in folders:
            for suffix in ['trace_'+f+'.csv','user_io-out-poi_geodetic.csv','user_io-out-poi_odometry.csv','user_io-out-odom_status.csv']:
                n=f+'/'+suffix
                with z.open(n) as ff:header=next(csv.reader(io.TextIOWrapper(ff,encoding='utf-8-sig')))
                schemas.append(dict(folder=f,member=n,bytes=z.getinfo(n).file_size,columns=json.dumps(header)))
    assert len(tr)==len(ge)
    tf=['lat','lon','height','yaw','pitch','roll'];gf=['p.vector3.x','p.vector3.y','p.vector3.z','ypr.vector3.x','ypr.vector3.y','ypr.vector3.z']
    va=arr(tr,tf);vg=arr(ge,gf);ta=arr(tr,['time'])[:,0];ga=arr(ge,['Time'])[:,0];gt=tm(ge);ot=tm(od);sa=arr(st,['Time'])[:,0];ss=tm(st)
    # Preserve input-order identity before taking one representative per equal source epoch.
    unique,idx,cnt=np.unique(gt,return_index=True,return_counts=True);order=np.argsort(idx);idx=idx[order];cnt=cnt[order]
    dupmax=0.
    for t in np.unique(gt):
        q=vg[gt==t];dupmax=max(dupmax,float(np.max(np.abs(q-q[0]))))
    pv=arr(ge,['p_var.vector3.x','p_var.vector3.y','p_var.vector3.z']);yv=arr(ge,['ypr_var.vector3.x','ypr_var.vector3.y','ypr_var.vector3.z'])
    cov=np.array([ast.literal_eval(r['pose.covariance']) for r in od]).reshape(-1,6,6);eig=np.linalg.eigvalsh((cov+cov.transpose(0,2,1))/2)
    op=np.array([np.sqrt(max(0.,np.linalg.eigvalsh(c[:3,:3])[-1])) for c in cov]);oa=np.array([np.degrees(np.sqrt(max(0.,np.linalg.eigvalsh(c[3:,3:])[-1]))) for c in cov])
    ecef=arr(od,['pose.pose.position.x','pose.pose.position.y','pose.pose.position.z']);dt=np.diff(ot);step=np.linalg.norm(np.diff(ecef,axis=0),axis=1)
    quat=arr(od,['pose.pose.orientation.x','pose.pose.orientation.y','pose.pose.orientation.z','pose.pose.orientation.w'])
    wraps=(np.diff(vg[idx,3])+180)%360-180;gdt=np.diff(gt[idx])
    epochs=[]
    for k,i in enumerate(idx):
        epochs.append(dict(source_row=int(i),measurement_utc_day_s=float(gt[i]-base),trace_arrival_utc_day_s=float(ta[i]-base),arrival_minus_measurement_s=float(ta[i]-gt[i]),multiplicity=int(cnt[k]),lat=vg[i,0],lon=vg[i,1],height=vg[i,2],yaw_ENU_deg=vg[i,3],position_var_E_m2=pv[i,0],position_var_N_m2=pv[i,1],position_var_U_m2=pv[i,2],horizontal_rms_sigma_m=float(np.sqrt(pv[i,0]+pv[i,1])),up_sigma_m=float(np.sqrt(pv[i,2])),ypr_var_x_recorded=yv[i,0],ypr_var_y_recorded=yv[i,1],ypr_var_z_recorded=yv[i,2]))
    keys=['init_status','fusion_imu','fusion_gnss1','fusion_gnss2','fusion_cam1','fusion_ws','imu_status','imu_noise','gnss1_status','gnss2_status','baseline_status','cam1_status']
    segments=[]
    # Intervals show reported status on its own arrival axis, not synchronized pose truth flags.
    for key in keys:
        values=[r[key] for r in st];cuts=[0]+[i for i in range(1,len(st)) if values[i]!=values[i-1]]+[len(st)]
        for lo,hi in zip(cuts[:-1],cuts[1:]):segments.append(dict(field=key,value=values[lo],first_arrival_day_s=float(sa[lo]-base),last_arrival_day_s=float(sa[hi-1]-base),first_header_day_s=float(ss[lo]-base),last_header_day_s=float(ss[hi-1]-base),rows=hi-lo))
    summary=dict(reference=ref,windows={},lineage=dict(rows=len(tr),columns=tf,payload_max_abs_differences=dict(zip(tf,np.max(np.abs(va-vg),axis=0).tolist())),trace_minus_geodetic_arrival_s=stats(ta-ga),unique_measurement_epochs=len(idx),measurement_multiplicity=dict(Counter(map(int,cnt))),duplicate_payload_max_abs_difference=dupmax,arrival_minus_measurement_s=stats(ta-gt),trace_input_nonmonotone_n=int(np.sum(np.diff(ta)<=0)),measurement_input_backwards_n=int(np.sum(np.diff(gt)<0)),trace_finite_row_n=int(np.isfinite(va).all(axis=1).sum())),covariance=dict(frame_counts=dict(Counter(r['header.frame_id'] for r in od)),child_counts=dict(Counter(r['child_frame_id'] for r in od)),finite_matrices=int(np.isfinite(cov).all(axis=(1,2)).sum()),rows=len(cov),maximum_asymmetry=float(np.max(np.abs(cov-cov.transpose(0,2,1)))),minimum_eigenvalue=float(eig.min()),negative_diagonal_n=int(np.sum(np.diagonal(cov,axis1=1,axis2=2)<0)),max_quaternion_norm_error=float(np.max(np.abs(np.linalg.norm(quat,axis=1)-1)))),semantics=dict(orientation_covariance='angle-axis rad^2; principal sigma is not Euler yaw sigma',geodetic_ypr_var='raw recorded field values; export producer/units not independently established; no square-root-as-yaw-sigma claim',time='trace arrival time; source pose header available; no offset fitted or adopted',status='ODOMSTATUS internal fusion logic; arrival and header windows both retained, not certified epochwise truth-quality mask'))
    statusrows=[];uncrows=[]
    for name,(lo,hi) in windows.items():
        m=(ta-base>=lo)&(ta-base<=hi);u=(gt[idx]-base>=lo)&(gt[idx]-base<=hi);au=(ta[idx]-base>=lo)&(ta[idx]-base<=hi);om=(ot-base>=lo)&(ot-base<=hi);tmid=(ot[1:]-base>=lo)&(ot[1:]-base<=hi);ym=(gt[idx][1:]-base>=lo)&(gt[idx][1:]-base<=hi)
        row=dict(trace_rows=int(m.sum()),unique_epochs_on_header_axis=int(u.sum()),unique_epochs_on_arrival_axis=int(au.sum()),trace_arrival_dt_s=stats(np.diff(ta[m])),source_measurement_dt_s=stats(np.diff(gt[idx][u])),trace_brackets_gt_frozen_0p15_n=int(np.sum(np.diff(ta[m])>.15)),source_intervals_gt_0p15_n=int(np.sum(np.diff(gt[idx][u])>.15)),arrival_minus_measurement_s=stats((ta-gt)[m]),horizontal_rms_sigma_m=stats(np.sqrt((pv[idx,0]+pv[idx,1])[u])),up_sigma_m=stats(np.sqrt(pv[idx,2][u])),reported_ypr_var_x=stats(yv[idx,0][u]),reported_ypr_var_y=stats(yv[idx,1][u]),reported_ypr_var_z=stats(yv[idx,2][u]),orientation_principal_sigma_deg=stats(oa[om]),position_principal_sigma_m=stats(op[om]),ecef_step_m=stats(step[tmid]),wrapped_yaw_step_deg=stats(np.abs(wraps[ym])),status={},gnss={})
        for label,taxis in [('arrival',sa),('header',ss)]:
            mm=(taxis-base>=lo)&(taxis-base<=hi);rr=[v for v,q in zip(st,mm) if q];row['status'][label]=dict(n=len(rr),fields={k:dict(Counter(v[k] for v in rr)) for k in keys})
            for k in keys:
                for value,n in row['status'][label]['fields'][k].items():statusrows.append(dict(window=name,clock=label,field=k,value=value,count=n,denominator=len(rr)))
        for nr,g in enumerate(gn,1):
            t=arr(g,['Time'])[:,0]-base;mm=(t>=lo)&(t<=hi);rr=[v for v,q in zip(g,mm) if q];row['gnss'][str(nr)]=dict(n=len(rr),fields={k:dict(Counter(v[k] for v in rr)) for k in ['msg_valid','pos_valid','fix_ok','fix_type','time_gps_ok']})
        summary['windows'][name]=row
        for k in ['horizontal_rms_sigma_m','up_sigma_m','position_principal_sigma_m','orientation_principal_sigma_deg','arrival_minus_measurement_s','ecef_step_m','wrapped_yaw_step_deg']:
            uncrows.append(dict(window=name,quantity=k,**row[k]))
    top=np.argsort(step)[-12:][::-1];summary['largest_source_position_steps']=[dict(t0=float(ot[i]-base),t1=float(ot[i+1]-base),dt_s=float(dt[i]),step_m=float(step[i]),sigma_max_before_m=float(op[i]),sigma_max_after_m=float(op[i+1])) for i in top]
    existing=json.loads(Path(a.existing_status).read_text());overview=[]
    for nr,e in enumerate(existing):
        c=e['status_field_counts'];n=e['odom_status_rows'];overview.append(dict(sequence=('NMB'+str(nr+1)) if nr<4 else ('XB'+str(nr-3)),folder=e['folder'],rows=n,globally_initialized=c.get('init_status',{}).get('2',0),camera_used=c.get('fusion_cam1',{}).get('1',0),imu_degraded=c.get('fusion_imu',{}).get('2',0),gnss1_not_used=c.get('fusion_gnss1',{}).get('0',0),gnss1_degraded=c.get('fusion_gnss1',{}).get('2',0),gnss2_not_used=c.get('fusion_gnss2',{}).get('0',0),gnss2_degraded=c.get('fusion_gnss2',{}).get('2',0),baseline_failing=c.get('baseline_status',{}).get('2',0),baseline_unavailable=c.get('baseline_status',{}).get('1',0),firmware=e['firmware_version']))
    summary['scope']=dict(native=0,evaluator=0,NAV_reads=0,standard_route_reads=0,raw_GNSS_payload_reads=0,status_overview='reused hash-pinned existing all-eight source audit; not new full scan')
    (out/'PLAN.json').write_text(json.dumps(dict(script=str(Path(__file__)),script_sha256=sha(Path(__file__).read_bytes()),input_pins=inputs,sequence=seq,windows=windows),ensure_ascii=False,indent=2))
    (out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    for fn,rows in [('SOURCE_EPOCHS.csv',epochs),('STATUS_COUNTS.csv',statusrows),('STATUS_INTERVALS.csv',segments),('UNCERTAINTY_TIME_SUMMARY.csv',uncrows),('EIGHT_SEQUENCE_STATUS_OVERVIEW.csv',overview),('SCHEMA_INVENTORY.csv',schemas)]:writecsv(out/fn,rows)
    print(json.dumps(dict(lineage=summary['lineage'],covariance=summary['covariance'],windows={k:{x:v[x] for x in ['trace_rows','unique_epochs_on_header_axis','trace_brackets_gt_frozen_0p15_n','source_intervals_gt_0p15_n','horizontal_rms_sigma_m','up_sigma_m','orientation_principal_sigma_deg','arrival_minus_measurement_s']} for k,v in summary['windows'].items()}),indent=2))
if __name__=='__main__':main()
