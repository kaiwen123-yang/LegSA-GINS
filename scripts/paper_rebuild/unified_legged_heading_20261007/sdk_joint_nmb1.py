#!/usr/bin/env python3
"""Matched two-arm NMB1 pilot for a same-state constant SDK discrepancy.
Historical R5 IMU input, original support XYZ and frozen evaluation are retained.
Prepare only after the new binary and math checks have been reviewed externally.
"""
from __future__ import annotations
import argparse,csv,copy,hashlib,io,json,shutil,sys,zipfile
from functools import reduce
from pathlib import Path
import numpy as np
import yaml
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/paper_rebuild/carrier_phase'),str(ROOT/'docs/paper_rebuild/EXISTING_DATA_R5_20261005/new_data')]
import continuous_heading_navigation as nr
import evaluate_new_sequences_0p15 as r5
from navigation_trial import clone_config
from navigation_body_pair import table
ARMS=('REPLACE_NULL','REPLACE_SUPPORT_XYZ')


def prepare(a):
    old=nr.read(a.old_plan);xyz=nr.read(a.xyz_plan)
    oldnull=next(x for x in old['runs'] if x['arm']=='REPLACE_NULL');oldxyz=xyz['runs'][0]
    assert oldnull['providers']['imupath']==oldxyz['providers']['imupath']
    assert oldxyz['arm']=='REPLACE_SUPPORT_XYZ'
    source_binary=nr.pin(a.binary)
    assert source_binary['sha256']=='c42f1609d98fe7d60e96b5e477420393acae3ae544075e48ea9cc28d39ebe327'
    math_check=nr.pin(a.math_check)
    a.output.mkdir(parents=True,exist_ok=False)
    binary=a.output/'BINARY'/a.binary.name;binary.parent.mkdir();shutil.copy2(a.binary,binary)
    assert nr.digest(binary)==source_binary['sha256']
    cfgdir=a.output/'CONFIGS';cfgdir.mkdir();runs=[];old_controls=[]
    for arm,template,sourceplan in [('REPLACE_NULL',oldnull,old),('REPLACE_SUPPORT_XYZ',oldxyz,xyz)]:
        base_template=oldxyz['config'];payload=nr.checked(base_template).read_bytes();prior=yaml.safe_load(payload);rid='NMB1__'+arm
        assert prior['support_pose_observed_axes']=='body0_xyz' and prior['heading_source_policy']=='pvt_priority_fallback'
        assert prior.get('go2_body_velocity_discrepancy_mode','off')=='off'
        fields=dict(run_id=rid,run_label=rid,case_id=rid,outputpath=str(a.output/'NATIVE'/rid),
            support_pose_mode='REPLACE_NULL' if arm=='REPLACE_NULL' else 'REPLACE_SUPPORT',go2_body_velocity_discrepancy_mode='joint_constant')
        content,changes=clone_config(payload,fields);new=yaml.safe_load(content)
        assert {k:v for k,v in prior.items() if k not in fields}=={k:v for k,v in new.items() if k not in fields}
        conf=cfgdir/(rid+'.yaml');conf.write_bytes(content);providers=copy.deepcopy(template['providers'])
        for item in providers.values():nr.checked(item)
        assert new['imupath']==providers['imupath']['path']
        runs.append(dict(run_id=rid,sequence_id='NMB1',arm=arm,config=nr.pin(conf),template=base_template,changes=changes,
            carrier=template['carrier'],carrier_support=template['carrier_support'],providers=providers,window=template['window']))
        source_root=Path(template['config']['path']).parent.parent
        old_controls.append(dict(arm=arm,binary=sourceplan['binary'],config=template['config'],result=nr.pin(source_root/'NATIVE'/rid/'RESULT.json'),
            errors=nr.pin(source_root/'EVALUATION'/(arm+'_ERRORS.csv'))))
    configs=[yaml.safe_load(Path(x['config']['path']).read_text()) for x in runs]
    identities={'run_id','run_label','case_id','outputpath'}
    different_keys=sorted(k for k in set(configs[0])|set(configs[1]) if configs[0].get(k)!=configs[1].get(k) and k not in identities)
    assert different_keys==['support_pose_mode']
    source_files=[ROOT/'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp',ROOT/'cpp/legsa_v23_port_core/src/config/port_config_loader.cpp',ROOT/'cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp']
    for pattern in ['gi_engine.*','*sdk_discrepancy*','*support_pose*','*pose_clone*','*body_velocity*','*options*']:
        source_files+=list((ROOT/'cpp/legsa_v23_port_core').rglob(pattern))
    plan=dict(schema='NMB1.SDK_discrepancy_joint_constant_pilot.v1',status='PREPARED_AWAITING_ROOT_EXECUTION_MESSAGE',runner=nr.pin(__file__),
        binary=nr.pin(binary),source_binary=source_binary,math_check=math_check,source_pins=[nr.pin(p) for p in sorted(set(source_files)) if p.is_file()],
        old_plan=nr.pin(a.old_plan),xyz_plan=nr.pin(a.xyz_plan),old_controls=old_controls,
        sequences=copy.deepcopy(old['sequences']),runs=runs,arms=list(ARMS),evaluator=old['evaluator'],aliases=old['aliases'],
        evaluator_adapter_source=nr.pin(ROOT/'scripts/paper_rebuild/unified_legged_heading_20261007/nominal_frame_nmb1.py'),
        evaluation_adapter='frozen R5 transform/bracket math copied unchanged; two arms with explicit original 80272 matched support check',
        body_provider=old['body_provider'],support_events=old['support_events'],gap_contract=old['gap_contract'],
        old_gap_readout=nr.pin(a.old_plan.parent/'READOUT.json'),old_xyz_readout=nr.pin(a.xyz_plan.parent/'READOUT.json'),
        native_budget=2,evaluator_budget=2,expected_matched_epochs=80272,reference_online=False,
        between_arm_scientific_config_differences=different_keys,
        scientific_change='both arms jointly estimate constant 2D SDK effective source discrepancy in shared navigation state; preserve cross covariance',
        model_status='result-informed effective-source model pilot, not physical SDK calibration or validated generalization',
        historical_IMU_installation='original R5 IMU8 including historical Rx(-1 deg), original gyro mean removal and acc scalar; nominal-frame experiment is not reused',
        first_association='augment b from first valid SDK association once, preserve navigation prior, no ordinary navigation update or duplicate source count',
        process_model='constant b2; no bias random-walk tuning, no phase-dependent parameter or fitted calibration',
        unchanged=['all prior input providers and timestamp mapping','foot XYZ and 1 cm point sigma','SDK replacement intervals and 0.2 s timer','PVT priority fallback and carrier rows','initialization and existing numeric noise parameters','evaluation point transform and bracket'],
        diagnostic_contract=dict(file='SDK_DISCREPANCY_EVENTS.csv',events=['SDK_SEED_NO_NAVIGATION_UPDATE','BODY_HORIZONTAL_VELOCITY','ordinary measurement kinds','FOOT_UPDATE'],
            contents=['time and source identity','b_f and b_r before/after','Pbb00/01/11 after','Pxb and Pbclone Frobenius norms','delta_p_NED/delta_v_NED/delta_phi_NED_left_tangent/delta_ba' ,'actual full-joint SDK/foot innovation vector and NIS'],
            seed_acceptance='BODY_VELOCITY_EVENTS accepted=0; SDK_SEED_NO_NAVIGATION_UPDATE innovation_dimensions=0; seed count one; ordinary SDK update count unchanged',
            columns=['time','source_time','kind','identity','initialized','b_forward_before','b_right_before','b_forward_after','b_right_after','Pbb00','Pbb01','Pbb11','Pxb_frobenius','Pbclone_frobenius','nis','innovation_dimensions']+['innovation_'+str(k) for k in range(6)]+['delta_p_'+k+'_m' for k in ['N','E','D']]+['delta_v_'+k+'_mps' for k in ['N','E','D']]+['delta_phi_'+k+'_rad' for k in ['N','E','D']]+['delta_ba_'+k+'_mps2' for k in ['x','y','z']],
            summary_file='SDK_DISCREPANCY_SUMMARY.json',
            summary_contents=['mode','initialized','seed_count','seed_source_time','seed_identity','final_b_mps','final_Pbb','Qb','N'],
            b_mean_semantics='nominal plus conditional error mean before/after each measurement',
            delta_semantics='change of measurement-conditional error mean mapped to feedback tangent; delta_phi is NED left rotation vector, not Euler difference or exact NAV jump',
            source_time_semantics='SDK: actual source row; FOOT: actual source event; other ordinary kinds: state update time',
            innovation_semantics='actual residual including b minus full H times conditional mean; NIS uses joint P and scaled R',
            count_comparison='verify same source opportunities and replacement timing; first seed does not increment SDK accepted and later source-aware accepts may legitimately change',
            attribution='joint b is effective source difference, not independently identified physical bias; nonzero foot delta_b requires shared cross covariance'),
        comparisons=['new support-minus-null with joint b versus old off-mode support-minus-null','full/gap/recovery/tail navigation metrics unchanged','SDK/foot innovations and source counts','b means/covariance and foot/SDK/ordinary update effects'],
        stop_scope='two native and two frozen evaluations only; no third SDK_NULL arm, no angle/noise/threshold scan')
    nr.emit(a.output/'PLAN.json',plan)
    print(json.dumps(dict(status=plan['status'],plan=nr.pin(a.output/'PLAN.json'),binary=plan['binary'],arms=list(ARMS),providers_unchanged=True),indent=2),flush=True)


def native(a):
    plan=nr.read(a.output/'PLAN.json');assert len(plan['runs'])==plan['native_budget']==2
    nr.checked(plan['runner']);nr.checked(plan['binary']);nr.checked(plan['math_check'])
    for run in plan['runs']:
        for item in run['providers'].values():nr.checked(item)
    nr.native(a)


def evaluate(a):
    plan=nr.read(a.output/'PLAN.json');seal=nr.read(a.output/'ALL_NATIVE_SEALED.json')
    assert seal['plan_sha256']==nr.digest(a.output/'PLAN.json')
    assert len(seal['records'])==2 and all(r['online_reference_opens']==0 for r in seal['records'])
    nr.checked(plan['evaluator']);spec=plan['sequences'][0];contract=spec['evaluation']
    out=a.output/'EVALUATION';out.mkdir(exist_ok=False)
    with zipfile.ZipFile(spec['reference']['path']) as archive:payload=archive.read(spec['reference']['member'])
    assert hashlib.sha256(payload).hexdigest()==spec['reference']['sha256']
    raw=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    ref=np.asarray([[float(r[k]) for k in ('time','lat','lon','height','roll','pitch','yaw')] for r in raw])
    ref=ref[np.isfinite(ref).all(axis=1)];ref[:,0]-=spec['base_time_unix_s']
    ref=ref[np.argsort(ref[:,0],kind='stable')];ref=ref[~np.r_[False,np.diff(ref[:,0])==0]]
    xyz=r5.xyz(ref[:,1:4]);lat,lon=np.deg2rad(ref[0,1:3]);sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
    matrix=np.array([[-sl*co,-sl*so,cl],[-so,co,0],[cl*co,cl*so,sl]])
    errors={};rows=[]
    for record in seal['records']:
        assert record['status'] in ('COMPLETED','ALGORITHM_FAILURE_DIVERGED')
        nav=np.loadtxt(nr.checked(record['nav']),comments='%',ndmin=2)
        point=r5.transform_nav(nav,contract['baseline_median_m']);t=point[:,1]
        j=np.clip(np.searchsorted(ref[:,0],t,side='right'),1,len(ref)-1)
        match=(t>=ref[0,0])&(t<=ref[-1,0])&(ref[j,0]-ref[j-1,0]<=contract['reference_bracket_limit_s'])
        tt=t[match];estimated=r5.xyz(point[match,2:5]);truth=np.column_stack([np.interp(tt,ref[:,0],xyz[:,i]) for i in range(3)])
        neu=(estimated-truth)@matrix.T;y=np.interp(tt,ref[:,0],np.unwrap(np.deg2rad(90-ref[:,6])))
        err=np.column_stack((neu,(point[match,10]-np.rad2deg(y)+180)%360-180))
        assert len(tt)==plan['expected_matched_epochs'], 'Evaluation support differs from frozen 80272 epochs'
        errors[record['arm']]=(tt,err,len(nav),record)
        table(out/(record['arm']+'_ERRORS.csv'),[dict(time=t,err_n_m=v[0],err_e_m=v[1],err_u_m=v[2],yaw_err_deg=v[3]) for t,v in zip(tt,err)])
    common=reduce(np.intersect1d,[v[0] for v in errors.values()])
    for arm,(tt,err,n,record) in errors.items():
        identity=dict(sequence='NMB1',method=arm,run_id=record['run_id'],status=record['status'])
        for support,t,e in [('OWN',tt,err),('COMMON_ALL',common,err[np.searchsorted(tt,common)])]:
            row=r5.metric(t,e,contract['expected_observed_epochs'],n,dict(identity,support=support))
            row.update(H_p99_m=float(np.quantile(np.hypot(e[:,0],e[:,1]),.99)),yaw_p99_deg=float(np.quantile(abs(e[:,3]),.99)))
            rows.append(row)
    table(a.output/'METRICS.csv',rows)
    nr.emit(a.output/'EVALUATION_SUMMARY.json',dict(rows=rows,native_seal=nr.pin(a.output/'ALL_NATIVE_SEALED.json'),
        evaluator=plan['evaluator'],adapter=nr.pin(__file__),reference_payload_reads=1,new_reference_evaluation_calls=2,
        reference_is_independent_ground_truth=False,reference_velocity_supported=False,evaluation=contract))
    print(json.dumps(rows,indent=2),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','native','evaluate'])
    for key in ('output','old-plan','xyz-plan','binary','math-check'):p.add_argument('--'+key,type=Path,required=key=='output')
    p.add_argument('--timeout',type=float,default=1200.)
    a=p.parse_args();a.output=a.output.resolve();globals()[a.command](a)

if __name__=='__main__':main()
