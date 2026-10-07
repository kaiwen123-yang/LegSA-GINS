#!/usr/bin/env python3
"""Two-arm nominal body-FRD diagnostic: undo historical Rx(-1 deg) in IMU8 only.
Not a proven installation correction, calibration fit or new algorithm.
"""
from __future__ import annotations
import argparse,csv,copy,hashlib,io,json,math,shutil,sys,zipfile
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
BINARY_SHA='0a69a7181eca853b5864793d09a7adb7d618f925eab1ba4b2ff4410f4dbdaa29'


def prepare(a):
    old=nr.read(a.old_plan);xyz=nr.read(a.xyz_plan)
    oldnull=next(x for x in old['runs'] if x['arm']=='REPLACE_NULL');oldxyz=xyz['runs'][0]
    imu_source=nr.checked(oldnull['providers']['imupath']);assert oldnull['providers']['imupath']==oldxyz['providers']['imupath']
    binary_source=nr.checked(xyz['binary']);assert nr.digest(binary_source)==BINARY_SHA
    a.output.mkdir(parents=True,exist_ok=False)
    inputs=a.output/'INPUTS';inputs.mkdir();imu=inputs/'IMU8_NOMINAL_BODY_FRD.imu'
    angle=math.radians(1.);c,s=math.cos(angle),math.sin(angle);R=np.array([[1.,0.,0.],[0.,c,-s],[0.,s,c]])
    lines=[];before=[];after=[];token_errors=0
    for line in imu_source.read_text().splitlines():
        fields=line.split()
        if len(fields)!=8:raise ValueError('IMU8 must have exactly eight numeric fields')
        row=np.array(list(map(float,fields)));out=row.copy();out[1:4]=R@row[1:4];out[4:7]=R@row[4:7]
        new=fields.copy()
        # Preserve original time, dt and both x component tokens exactly.
        for k in (2,3,5,6):new[k]=format(out[k],'.17g')
        token_errors+=sum(new[k]!=fields[k] for k in (0,1,4,7))
        lines.append(' '.join(new));before.append(row);after.append(np.array(list(map(float,new))))
    imu.write_text('\n'.join(lines)+'\n');before=np.array(before);after=np.array(after)
    recover=after.copy();recover[:,1:4]=after[:,1:4]@R;recover[:,4:7]=after[:,4:7]@R
    transform=dict(original=oldnull['providers']['imupath'],nominal=nr.pin(imu),matrix_left_column_vector=R.tolist(),angle_x_deg=1.,
        rows=len(before),time_and_dt_numeric_equal=bool(np.array_equal(before[:,[0,7]],after[:,[0,7]])),preserved_token_mismatches=token_errors,
        x_columns_numeric_equal=bool(np.array_equal(before[:,[1,4]],after[:,[1,4]])),
        inverse_max_abs_increment_error=float(abs(recover[:,1:7]-before[:,1:7]).max()),
        norm_preservation_max_abs=float(max(abs(np.linalg.norm(after[:,1:4],axis=1)-np.linalg.norm(before[:,1:4],axis=1)).max(),abs(np.linalg.norm(after[:,4:7],axis=1)-np.linalg.norm(before[:,4:7],axis=1)).max())),
        first_time=float(before[0,0]),last_time=float(before[-1,0]),
        raw_gyro_mean_removal='inherited untouched; linear inverse rotation of already corrected increments',
        accelerometer_scalar='inherited untouched; no reintegration or rescaling',
        time_contract='original IMU8 timestamp and explicit dt tokens retained exactly')
    assert transform['time_and_dt_numeric_equal'] and transform['x_columns_numeric_equal'] and token_errors==0
    nr.emit(a.output/'IMU_TRANSFORM.json',transform)
    binary=a.output/'BINARY'/binary_source.name;binary.parent.mkdir();shutil.copy2(binary_source,binary);assert nr.digest(binary)==BINARY_SHA
    cfgdir=a.output/'CONFIGS';cfgdir.mkdir();runs=[];old_controls=[]
    for arm,template,sourceplan in [('REPLACE_NULL',oldnull,old),('REPLACE_SUPPORT_XYZ',oldxyz,xyz)]:
        base_template=oldxyz['config']
        payload=nr.checked(base_template).read_bytes();prior=yaml.safe_load(payload);rid='NMB1__'+arm
        fields=dict(run_id=rid,run_label=rid,case_id=rid,outputpath=str(a.output/'NATIVE'/rid),imupath=str(imu),support_pose_mode='REPLACE_NULL' if arm=='REPLACE_NULL' else 'REPLACE_SUPPORT')
        content,changes=clone_config(payload,fields);new=yaml.safe_load(content)
        assert {k:v for k,v in prior.items() if k not in fields}=={k:v for k,v in new.items() if k not in fields}
        conf=cfgdir/(rid+'.yaml');conf.write_bytes(content);providers=copy.deepcopy(template['providers']);providers['imupath']=nr.pin(imu)
        for item in providers.values():nr.checked(item)
        runs.append(dict(run_id=rid,sequence_id='NMB1',arm=arm,config=nr.pin(conf),template=base_template,changes=changes,
            carrier=template['carrier'],carrier_support=template['carrier_support'],providers=providers,window=template['window']))
        root=Path(template['config']['path']).parent.parent
        old_controls.append(dict(arm=arm,binary=sourceplan['binary'],config=template['config'],result=nr.pin(root/'NATIVE'/rid/'RESULT.json'),
            errors=nr.pin(root/'EVALUATION'/(arm+'_ERRORS.csv'))))
    configs=[yaml.safe_load(Path(x['config']['path']).read_text()) for x in runs]
    identities={'run_id','run_label','case_id','outputpath'}
    different_keys=[k for k in set(configs[0])|set(configs[1]) if configs[0].get(k)!=configs[1].get(k) and k not in identities]
    assert different_keys==['support_pose_mode']
    specs=copy.deepcopy(old['sequences']);specs[0]['runtime_provider_pins']['imupath']=nr.pin(imu)
    plan=dict(schema='NMB1.nominal_frame_common_state_diagnostic.v1',status='PREPARED_AWAITING_ROOT_EXECUTION_MESSAGE',runner=nr.pin(__file__),
        binary=nr.pin(binary),source_binary=xyz['binary'],binary_source_pins=xyz['source_pins'],
        old_plan=nr.pin(a.old_plan),xyz_plan=nr.pin(a.xyz_plan),old_controls=old_controls,
        sequences=specs,runs=runs,arms=list(ARMS),evaluator=old['evaluator'],aliases=old['aliases'],
        evaluation_adapter='copied frozen nmb1_support_pose_navigation evaluate math; two arms and explicit old 80272 support check only',
        evaluator_adapter_source=nr.pin(ROOT/'scripts/paper_rebuild/unified_legged_heading_20261007/nmb1_support_pose_navigation.py'),
        body_provider=old['body_provider'],support_events=old['support_events'],gap_contract=old['gap_contract'],
        old_gap_readout=nr.pin(a.old_plan.parent/'READOUT.json'),old_xyz_readout=nr.pin(a.xyz_plan.parent/'READOUT.json'),
        native_budget=2,evaluator_budget=2,between_arm_scientific_config_differences=different_keys,expected_matched_epochs=80272,reference_online=False,
        model_status='result-informed installation-assumption diagnosis; not a proven bug fix, calibration or new algorithm',
        sole_measurement_change='every saved R5 IMU8 dtheta and dvel left-multiplied by Rx(+1 deg), undoing historical Rx(-1 deg)',
        frozen_unchanged=['source timestamps and dt','raw gyro mean removal','accelerometer scalar','all non-IMU providers','initialization','numerical noises and prior std','SDK suppression schedule','foot covariance and NIS','source policy','carrier inputs','evaluation math and lever'],
        frame_hypothesis='raw SDK IMU, foot points, RP and body velocity share nominal body FRD; URDF nominal rpy zero does not independently calibrate physical installation',
        covariance_limit='unchanged numerical diagonal noises control this working model; not claimed to be full covariance coordinate equivalence',
        scientific_limit='pure Rx change preserves forward component and cannot resolve source-only approximately 6 percent forward displacement conflict',
        comparison='new support-minus-null effect in nominal frame versus old support-minus-null effect; no predeclared gain claim',
        imu_transform=nr.pin(a.output/'IMU_TRANSFORM.json'))
    nr.emit(a.output/'PLAN.json',plan)
    print(json.dumps(dict(status=plan['status'],plan=nr.pin(a.output/'PLAN.json'),binary=plan['binary'],imu_transform=transform,arms=list(ARMS)),indent=2),flush=True)


def native(a):
    plan=nr.read(a.output/'PLAN.json');assert len(plan['runs'])==plan['native_budget']==2
    nr.checked(plan['runner']);nr.checked(plan['binary']);nr.checked(plan['imu_transform'])
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
    for key in ('output','old-plan','xyz-plan'):p.add_argument('--'+key,type=Path,required=key=='output')
    p.add_argument('--timeout',type=float,default=1200.)
    a=p.parse_args();a.output=a.output.resolve();globals()[a.command](a)

if __name__=='__main__':main()
