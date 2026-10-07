#!/usr/bin/env python3
"""Same saved ENDs: SDK position, foot/RPY and velocity/RPY; no fitted scale/time."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/paper_rebuild/carrier_phase')]
import continuous_heading_navigation as nr
from navigation_body_pair import table


def rows(p):
    with p.open() as f:return list(csv.DictReader(f))


def summary(v):
    a=np.asarray(v);return dict(n=len(a),mean=float(a.mean()),rms=float(np.sqrt(np.mean(a*a))),
        median=float(np.median(a)),p95=float(np.quantile(a,.95)),abs_p95=float(np.quantile(abs(a),.95)),
        negative_fraction=float(np.mean(a<0)),min=float(a.min()),max=float(a.max()))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    cache=a.base/'NMB1_SDK_INTERNAL_FRAME_01/NMB1_FULL_SOURCE_MOTION.npz';provider=a.base/'SUPPORT_POSE_PROVIDER_NMB1_01'
    prior=a.base/'NMB1_SUPPORT_SDK_CONSISTENCY_01/INTERVALS.csv'
    z=np.load(cache);ns=z['native_ns'];Q=Rotation.from_euler('xyz',z['rpy_flu']).as_matrix()@np.diag([1,-1,-1]);v=z['velocity_frd'];pos=z['position_sdk']
    events=rows(provider/'SUPPORT_POSE_EVENTS.csv');ident=rows(provider/'ENDPOINT_RAW_IDENTITY.csv')
    ids={(r['clone_id'],r['event_type']):int(r['native_stamp_ns']) for r in ident};old={r['clone_id']:r for r in rows(prior)}
    starts={};out=[];endpoint_errors=[];pins=[nr.pin(p) for p in [cache,provider/'SUPPORT_POSE_EVENTS.csv',provider/'ENDPOINT_RAW_IDENTITY.csv',prior]]
    feet={'FR':0,'FL':1,'RR':2,'RL':3}
    for e in events:
        if e['event_type']=='START':starts[e['clone_id']]=e;continue
        if e['event_type']!='END':continue
        start=starts[e['clone_id']];n0=ids[e['clone_id'],'START'];n1=ids[e['clone_id'],'END'];i,j=np.searchsorted(ns,[n0,n1])
        assert ns[i]==n0 and ns[j]==n1
        f0=np.array([[float(start[f'r_{k}_body_frd_{c}_m']) for c in 'xyz'] for k in ['i','j']]);f1=np.array([[float(e[f'r_{k}_body_frd_{c}_m']) for c in 'xyz'] for k in ['i','j']])
        for k,key in enumerate(['i','j']):
            endpoint_errors.extend((float(abs(f0[k]-z['foot_position_body_frd'][i,feet[start['foot_'+key]]]).max()),
                                    float(abs(f1[k]-z['foot_position_body_frd'][j,feet[e['foot_'+key]]]).max())))
        D=Q[i].T@Q[j];foot=(f0-f1@D.T).mean(axis=0);pdisp=Q[i].T@(pos[j]-pos[i])
        velocity=Q[i].T@np.sum(np.einsum('nij,nj->ni',Q[i:j],v[i:j])*(np.diff(ns[i:j+1])*1e-9)[:,None],axis=0)
        r=old[e['clone_id']];Dg=Rotation.from_rotvec(np.deg2rad([float(r['rotation_'+c+'_deg']) for c in 'xyz'])).as_matrix()
        rot_error=np.rad2deg(Rotation.from_matrix(Dg.T@D).as_rotvec())
        gyro_foot=np.array([(float(r['y_i_'+c+'_m'])+float(r['y_j_'+c+'_m']))/2 for c in 'xyz'])
        common=np.array([float(r['common_'+c+'_m']) for c in 'xyz']);rv=np.deg2rad([float(r['rotation_'+c+'_deg']) for c in 'xyz'])
        J=np.eye(3)-Dg;axis=rv/np.linalg.norm(rv)
        row=dict(clone_id=e['clone_id'],t0_s=n0*1e-9,t1_s=n1*1e-9,dt_s=(n1-n0)*1e-9,
            inside_main_gap=r['inside_main_gap']=='True',source_segments=j-i,pair=e['foot_i']+'-'+e['foot_j'],
            relative_rotation_disagreement_deg=float(np.linalg.norm(rot_error)),
            gyro_lever_necessary_norm_for_x_m=float(abs(common[0])/np.linalg.norm(J[0])),
            gyro_lever_necessary_norm_for_full_m=float(np.linalg.norm(common)/(2*np.sin(np.linalg.norm(rv)/2))),
            common_projection_on_rotation_axis_m=float(axis@common))
        for label,value in [('foot_RPY',foot),('position',pdisp),('velocity_RPY',velocity),('foot_minus_position',foot-pdisp),
                            ('velocity_minus_position',velocity-pdisp),('foot_minus_velocity',foot-velocity),('foot_RPY_minus_gyro',foot-gyro_foot)]:
            row.update({label+'_'+ax+'_m':float(val) for ax,val in zip('xyz',value)})
        out.append(row)
    endpoints=[r for r in events if r['event_type'] in ('START','END')]
    timing=dict(endpoint_rows=len(endpoints),event_minus_source_max_s=max(abs(float(r['event_time_s'])-float(r['source_time_s'])) for r in endpoints),
        event_minus_available_max_s=max(abs(float(r['event_time_s'])-float(r['available_time_s'])) for r in endpoints),
        integer_ns_identity_mismatches=sum(round(float(r['event_time_s'])*1e9)!=ids[r['clone_id'],r['event_type']] for r in endpoints),
        full_cache_vs_provider_point_max_abs_m=max(endpoint_errors))
    for name,root in [('XY',a.base/'SUPPORT_POSE_NATIVE_NMB1_01/NATIVE/NMB1__REPLACE_SUPPORT'),('XYZ',a.base/'SUPPORT_POSE_XYZ_NMB1_01/NATIVE/NMB1__REPLACE_SUPPORT_XYZ')]:
        path=root/'SUPPORT_POSE_EVENTS.csv';pins.append(nr.pin(path));native=rows(path)
        timing[name+'_native_event_rows']=len(native);timing[name+'_native_event_minus_state_max_s']=max(abs(float(r['event_time_s'])-float(r['state_time_s'])) for r in native)
    windows={};metrics=[]
    for name,rr in [('FULL',out),('GAP',[r for r in out if r['inside_main_gap']])]:
        sums={};ww=dict(n=len(rr),dt_s=summary([r['dt_s'] for r in rr]),rotation_disagreement_deg=summary([r['relative_rotation_disagreement_deg'] for r in rr]),
            necessary_lever_x_norm_m=summary([r['gyro_lever_necessary_norm_for_x_m'] for r in rr]),
            necessary_lever_full_norm_m=summary([r['gyro_lever_necessary_norm_for_full_m'] for r in rr]),
            unexplainable_pure_lever_rotation_axis_component_m=summary([r['common_projection_on_rotation_axis_m'] for r in rr]))
        for label in ['foot_RPY','position','velocity_RPY','foot_minus_position','velocity_minus_position','foot_minus_velocity','foot_RPY_minus_gyro']:
            for ax in 'xyz':
                values=[r[label+'_'+ax+'_m'] for r in rr];ss=summary(values);metrics.append(dict(window=name,quantity=label,axis=ax,**ss))
                if ax=='x':sums[label]=sum(values)
        ww.update(foot_to_position_forward_ratio=sums['foot_RPY']/sums['position'],velocity_to_position_forward_ratio=sums['velocity_RPY']/sums['position'],
            foot_to_velocity_forward_ratio=sums['foot_RPY']/sums['velocity_RPY'])
        windows[name]=ww
    table(a.output/'INTERVALS.csv',out);table(a.output/'THREE_SOURCE_METRICS.csv',metrics)
    nr.emit(a.output/'SUMMARY.json',dict(runner=nr.pin(__file__),input_pins=pins,windows=windows,timing=timing,
        raw_reads=0,NAV_reads=0,reference_reads=0,native_calls=0,evaluator_calls=0,
        integration='left ZOH on every same-source integer-ns sample, SDK raw RPY rotations, exact saved END endpoints',
        frame='all vectors expressed in START body FRD after mapping through SDK world; SDK world is not NED truth',
        no_scale_or_time_fit=True,position_is_not_truth=True,
        lever_bounds='necessary per-interval lever norms, not fitted lever; pure-lever component perpendicular to rotation axis'))
    print(json.dumps(dict(windows=windows,timing=timing),indent=2),flush=True)
if __name__=='__main__':main()
