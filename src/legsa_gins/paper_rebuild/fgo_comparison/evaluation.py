"""Offline adapter for actual FGO output; no solver is imported or invoked.

Reuse the frozen evaluator's reference reader, WGS84 functions, angle wrapping
and Canonical statistics. Position-only output has no fabricated attitude.
Reference interpolation is the existing contract; method output is never
interpolated. Every missing/invalid output remains in the denominator.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import pandas as pd
import yaml

from ..canonical541.offline_eval_aggregate import _axis_stats, _norm_stats
from ..clean5_parity.evaluation import body_to_ned, transform_nav
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256
from ..horizontal_literature.shared_raw_backend import ecef_to_geodetic
from .raw_inputs import aliases, dump, portable, sha256
from .runner import json_safe, write_csv

EVALUATOR='<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py'


def resolve(value,roots):
    for alias,root in roots.items(): value=str(value).replace(alias,root)
    return Path(value)


def evaluator_module(roots):
    path=resolve(EVALUATOR,roots)
    if sha256(path)!=EVALUATOR_SHA256: raise ValueError('Frozen evaluator identity mismatch')
    spec=importlib.util.spec_from_file_location('frozen_fgo_evaluator',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def ned_to_ecef(lat_deg,lon_deg):
    lat,lon=np.deg2rad(lat_deg),np.deg2rad(lon_deg)
    sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
    return np.stack((-sl*co,-so,-cl*co,-sl*so,co,-cl*so,cl,np.zeros_like(cl),-sl),axis=-1).reshape((-1,3,3))


def reference_at(module,gt,times,baseline,point):
    """Frozen reference interpolation; legal physical-point shift only."""
    t=np.asarray(times);tt=gt.time.to_numpy()
    llh=np.column_stack([np.interp(t,tt,gt[k]) for k in ('lat','lon','alt')])
    rpy=np.column_stack([np.interp(t,tt,gt[k]) for k in ('roll','pitch')]+[
        (90-np.rad2deg(np.interp(t,tt,np.unwrap(np.deg2rad(gt.yaw)))))%360])
    xyz=np.column_stack(module.lla_to_ecef(*llh.T))
    if point=='GNSS1_ANTENNA':
        offset=np.einsum('nij,njk,k->ni',ned_to_ecef(llh[:,0],llh[:,1]),body_to_ned(rpy),np.array([0.,baseline/2,0.]))
        xyz=xyz+offset
    elif point!='POI_MIDPOINT': raise ValueError('Unknown output point')
    return llh,rpy,xyz


def output_at_poi(position,rpy,times,baseline):
    """Call the existing v3 transform on actual IMU states/attitudes only."""
    llh=np.asarray([ecef_to_geodetic(x) for x in position]);llh[:,:2]=np.rad2deg(llh[:,:2])
    nav=np.zeros((len(position),11));nav[:,1]=times;nav[:,2:5]=llh;nav[:,8:11]=rpy
    corrected=transform_nav(nav,baseline)
    la,lo,h=np.deg2rad(corrected[:,2]),np.deg2rad(corrected[:,3]),corrected[:,4]
    rn=6378137/np.sqrt(1-6.6943799901413165e-3*np.sin(la)**2)
    return np.column_stack(((rn+h)*np.cos(la)*np.cos(lo),(rn+h)*np.cos(la)*np.sin(lo),(rn*(1-6.6943799901413165e-3)+h)*np.sin(la)))


def statistics(errors):
    row={}
    for name,col,unit,is_norm in [('horizontal','horizontal_err_m','m',True),('vertical','err_u_m','m',False),
            ('position_3d','position_3d_err_m','m',True),('roll','roll_err_deg','deg',False),
            ('pitch','pitch_err_deg','deg',False),('yaw','yaw_err_deg','deg',False)]:
        if col not in errors: continue
        stats=(_norm_stats if is_norm else _axis_stats)(np.asarray(errors['time']),np.asarray(errors[col]))
        for key in ('rmse','p50' if is_norm else 'p50_absolute','p95' if is_norm else 'p95_absolute','max' if is_norm else 'max_absolute'):
            outkey=key.replace('_absolute','')
            row[f'{name}_{outkey}_{unit}']=stats[key]
    return row


def score_method(module,gt,states,spec,method,run):
    start,end=spec['window_seconds'];baseline=spec['baseline_median_m']
    point='POI_MIDPOINT' if method=='OISAM' else 'GNSS1_ANTENNA'
    expected=int(end-start)+1
    states=states.loc[(states.time_rel_s>=start)&(states.time_rel_s<=end)].copy()
    t=states.time_rel_s.to_numpy(float)
    if not np.isfinite(t).all() or np.any(np.diff(t)<=0) or len(set(np.rint(t).astype(int)))!=len(t):
        raise ValueError('FGO output epochs must be finite, unique 1Hz nodes in time order')
    if len(t)>expected: raise ValueError('Actual output exceeds registered 1Hz denominator')
    xyz=states[['x_ecef_m','y_ecef_m','z_ecef_m']].to_numpy(float)
    finite=np.isfinite(xyz).all(axis=1)&(states.valid.to_numpy(float)>0)
    attitude=method=='OISAM'
    if attitude:
        rpy=states[['roll_deg','pitch_deg','yaw_deg']].to_numpy(float)
        finite &=np.isfinite(rpy).all(axis=1)
        if finite.any(): xyz[finite]=output_at_poi(xyz[finite],rpy[finite],t[finite],baseline)
    support=finite&(t>=gt.time.min())&(t<=gt.time.max())
    llh,trpy,truth=reference_at(module,gt,t,baseline,point)
    valid_indices=np.flatnonzero(support)
    # The archived evaluator anchors ENU at its first matched reference epoch.
    origin=llh[valid_indices[0]] if len(valid_indices) else np.array([0.,0.,0.])
    d=xyz-truth
    rotation=ned_to_ecef(np.array([origin[0]]),np.array([origin[1]]))[0].T
    ned=d@rotation.T
    error=pd.DataFrame({'time':t,'err_n_m':ned[:,0],'err_e_m':ned[:,1],'err_u_m':-ned[:,2],
                        'horizontal_err_m':np.linalg.norm(ned[:,:2],axis=1),'position_3d_err_m':np.linalg.norm(ned,axis=1)})
    for key in error.columns[1:]: error.loc[~support,key]=np.nan
    if attitude:
        for j,axis in enumerate(('roll','pitch','yaw')):
            error[axis+'_err_deg']=module.wrap_deg(rpy[:,j]-trpy[:,j]);error.loc[~support,axis+'_err_deg']=np.nan
    error['valid']=support.astype(int);error['native_status']=states.status.to_numpy()
    finite_times=t[support]
    row={'sequence_id':spec['dataset_id'],'method_id':method,'support':'OWN_VALID','status':run['terminal_status'],
         'physical_point':point,'input_layer':'GNSS_POSITION_BODY_IMU' if attitude else 'RAW_CODE_EXTERNAL_AHRS_IMU' if method=='WEN_TC' else 'RAW_CODE_DOPPLER',
         'base_time':spec['base_time'],'window_start_s':start,'window_end_s':end,
         'expected_epoch_count':expected,'actual_epoch_count':len(t),'finite_epoch_count':int(finite.sum()),
         'matched_epoch_count':int(support.sum()),'missing_or_invalid_count':expected-int(support.sum()),
         'reference_epoch_count':int(((gt.time>=start)&(gt.time<=end)).sum()),
         'coverage_fraction':int(support.sum())/expected,'first_output_s':float(finite_times[0]) if len(finite_times) else None,
         'last_output_s':float(finite_times[-1]) if len(finite_times) else None,
         'maximum_gap_with_window_edges_s':float(np.max(np.diff(np.r_[start,finite_times,end]))),
         'state_status_counts':json.dumps(states.status.value_counts().to_dict(),sort_keys=True),
         'solver_and_adapter_elapsed_s':run.get('solver_and_adapter_elapsed_s'),
         'solve_mode':run.get('mode'),'attitude_is_estimated':attitude,
         'old_result_reused':False,**statistics(error)}
    trajectory=pd.DataFrame({'time':t,'x_ecef_m':xyz[:,0],'y_ecef_m':xyz[:,1],'z_ecef_m':xyz[:,2],
                             'truth_x_ecef_m':truth[:,0],'truth_y_ecef_m':truth[:,1],'truth_z_ecef_m':truth[:,2],
                             'valid':support.astype(int)})
    trajectory.loc[~support,['x_ecef_m','y_ecef_m','z_ecef_m']]=np.nan
    return row,error,trajectory


def common_time_rows(rows,errors):
    """Nearest nominal second, fixed 5 ms gate; never interpolate estimates."""
    lookup={}
    for method,df in errors.items():
        times=df.time.to_numpy();keys=np.rint(times).astype(int)
        valid=(df.valid.to_numpy()>0)&(np.abs(times-keys)<=.005)
        if len(set(keys[valid]))!=sum(valid): raise ValueError('Duplicate common-support epoch')
        lookup[method]={int(keys[i]):i for i in np.flatnonzero(valid)}
    common=sorted(set.intersection(*(set(x) for x in lookup.values()))) if lookup else []
    result=[]
    for row in rows:
        method=row['method_id'];df=errors[method].iloc[[lookup[method][k] for k in common]]
        selected_times=df.time.to_numpy(float)
        result.append({**row,**statistics(df),'support':'COMMON_THREE_NEW_METHODS_TIME_ONLY',
                       'matched_epoch_count':len(common),'coverage_fraction':len(common)/row['expected_epoch_count'],
                       'own_matched_epoch_count':row['matched_epoch_count'],'finite_epoch_count':len(common),
                       'first_output_s':float(selected_times[0]) if len(selected_times) else None,
                       'last_output_s':float(selected_times[-1]) if len(selected_times) else None,
                       'maximum_gap_with_window_edges_s':float(np.max(np.diff(np.r_[row['window_start_s'],selected_times,row['window_end_s']]))),
                       'missing_or_invalid_count':row['expected_epoch_count']-len(common),
                       'common_time_tolerance_s':.005,'comparison_boundary':'different inputs and physical points; application comparison'})
    return result


def evaluation_directory(roots,sequence):
    base=Path(roots.get('<FGO_EVALUATION_ROOT>',str(Path(roots['<FGO_ROOT>'])/'evaluation')))
    return Path(roots.get(f'<FGO_EVALUATION_{sequence}>',str(base/sequence)))


def evaluate_sequence(roots_path,sequence,attempts,access_log=None):
    roots=aliases(roots_path);root=Path(roots['<FGO_ROOT>']);code=Path(roots['<CODE_ROOT>'])
    started=time.perf_counter()
    code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=code,text=True).strip()
    spec=yaml.safe_load((code/'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml').read_text())['sequences'][sequence]
    out=evaluation_directory(roots,sequence);out.mkdir(parents=True,exist_ok=False)
    # All native outputs are sealed before any reference is opened.
    native={}
    for method,attempt in attempts.items():
        path=root/'runs'/sequence/method/attempt
        run=json.loads((path/'RUN.json').read_text())
        for name,digest in run.get('output_hashes',{}).items():
            if sha256(path/name)!=digest: raise ValueError('Native output seal changed')
        if (path/'STATES.csv').exists(): states=pd.read_csv(path/'STATES.csv')
        else:
            columns=['time_rel_s','x_ecef_m','y_ecef_m','z_ecef_m','valid','status']
            if method=='OISAM':columns+=['roll_deg','pitch_deg','yaw_deg']
            states=pd.DataFrame(columns=columns)
        native[method]=(run,states,path)
    module=evaluator_module(roots);reference=resolve(spec['trace']['path'],roots)
    # One physical read handle per sequence, hash from the same bytes.
    with reference.open('rb') as handle: payload=handle.read()
    digest=hashlib.sha256(payload).hexdigest()
    if digest!=spec['trace']['sha256']: raise ValueError('Reference pin mismatch')
    gt=module.load_trace(BytesIO(payload),spec['base_time']);del payload
    if np.any(np.diff(gt.time)<0): raise ValueError('Reference time not ordered')
    rows=[];errors={}
    for method,(run,states,path) in native.items():
        row,error,trajectory=score_method(module,gt,states,spec,method,run)
        row.update(source_path=portable(path/'RUN.json',roots),error_path=portable(out/(method+'_ERRORS.csv'),roots))
        error.to_csv(out/(method+'_ERRORS.csv'),index=False,lineterminator='\n')
        trajectory.to_csv(out/(method+'_TRAJECTORY.csv'),index=False,lineterminator='\n')
        rows.append(row);errors[method]=error
    common=common_time_rows(rows,errors)
    selected=gt.loc[(gt.time>=spec['window_seconds'][0])&(gt.time<=spec['window_seconds'][1])]
    for point in ('POI_MIDPOINT','GNSS1_ANTENNA'):
        llh,rpy,xyz=reference_at(module,gt,selected.time.to_numpy(),spec['baseline_median_m'],point)
        pd.DataFrame(dict(time=selected.time.to_numpy(),x_ecef_m=xyz[:,0],y_ecef_m=xyz[:,1],z_ecef_m=xyz[:,2])).to_csv(out/('TRUTH_'+point+'.csv'),index=False,lineterminator='\n')
    write_csv(out/'METRICS.csv',rows+common)
    dump(out/'EVALUATION.json',json_safe({'sequence':sequence,'rows':rows+common,'native_attempts':attempts,'reference_sha256':digest,
        'code_commit':code_commit,'config_hash':sha256(code/'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml'),
        'evaluation_source_hash':sha256(Path(__file__)),
        'access_log':portable(resolve(access_log,roots),roots) if access_log else None,
        'native_manifest_hashes':{m:sha256(p/'RUN.json') for m,(_,_,p) in native.items()},
        'evaluation_elapsed_s':time.perf_counter()-started,
        'reference_read_count':1,'evaluator_child_count':1,'evaluator_sha256':EVALUATOR_SHA256,
        'output_interpolation':False,'reference_interpolation':'frozen linear LLH/RP; unwrap yaw; ENU yaw to NED',
        'physical_point_rule':'OiSAM IMU-to-POI existing transform; GNSS-only reference POI-to-GNSS1',
        'reference_maximum_interval_s':float(np.max(np.diff(gt.time))),
        'data_mode':'real_raw_reuse','synthetic_data_used':False,'semisynthetic_data_used':False,
        'trace_used_online':False,'epoch_deleted_for_metric':False,'per_case_tuning':False,'output_only_correction':False,
        'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,'LegSA_output_solver_input':False,
        'old_runtime_input_count':0} ))
    return rows+common


def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',required=True);p.add_argument('--sequence',required=True,choices=['BY2','BY2H','BY2O'])
    p.add_argument('--gnc-attempt',default='MAIN');p.add_argument('--wen-attempt',default='MAIN');p.add_argument('--oisam-attempt',default='MAIN')
    p.add_argument('--access-log',help='Actual enclosing strace output; provenance only')
    a=p.parse_args();rows=evaluate_sequence(a.roots,a.sequence,{'GNC':a.gnc_attempt,'WEN_TC':a.wen_attempt,'OISAM':a.oisam_attempt},a.access_log)
    print(json.dumps(json_safe(rows)))


if __name__=='__main__':main()
