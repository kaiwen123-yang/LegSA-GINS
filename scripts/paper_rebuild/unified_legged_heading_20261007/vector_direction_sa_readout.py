#!/usr/bin/env python3
"""Read the sealed vector-direction SA pair; never run native or evaluation."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np


def read(p): return json.loads(Path(p).read_text())
def pin(p):
    p=Path(p)
    return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def checked(item):
    assert pin(item['path'])['sha256']==item['sha256'],item['path']
    return Path(item['path'])
def rows(p):
    with Path(p).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def emit(p,j): Path(p).write_text(json.dumps(j,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def table(p,data):
    if not data:return
    keys=list(dict.fromkeys(k for r in data for k in r))
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(data)
def val(r,k,default=0):return float(r.get(k) or default)
def rms(a):return float(np.sqrt(np.mean(np.asarray(a)**2))) if len(a) else None
def quant(a,q):return float(np.quantile(a,q)) if len(a) else None
def stats(a):
    a=np.asarray(a,dtype=float);a=a[np.isfinite(a)]
    return dict(n=len(a),mean=float(np.mean(a)) if len(a) else None,median=quant(a,.5),p95=quant(a,.95),p99=quant(a,.99),max=float(max(a)) if len(a) else None,rms=rms(a))
def counts(data,key):return dict(Counter(r[key] for r in data))
def rotations(rpy):
    r,p,y=np.deg2rad(rpy).T
    cr,sr,cp,sp,cy,sy=np.cos(r),np.sin(r),np.cos(p),np.sin(p),np.cos(y),np.sin(y)
    a=np.empty((len(r),3,3))
    a[:,0,:]=np.array([cp*cy,sr*sp*cy-cr*sy,cr*sp*cy+sr*sy]).T
    a[:,1,:]=np.array([cp*sy,sr*sp*sy+cr*cy,cr*sp*sy-sr*cy]).T
    a[:,2,:]=np.array([-sp,sr*cp,cr*cp]).T
    return a

def ecef_and_ned(n):
    lat,lon=np.deg2rad(n[:,1:3]).T;h=n[:,3]
    sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
    e2=6.6943799901413165e-3;v=6378137/np.sqrt(1-e2*sl**2)
    xyz=np.column_stack(((v+h)*cl*co,(v+h)*cl*so,(v*(1-e2)+h)*sl))
    A=np.empty((len(n),3,3))
    A[:,0,:]=np.array([-sl*co,-sl*so,cl]).T
    A[:,1,:]=np.array([-so,co,np.zeros(len(n))]).T
    A[:,2,:]=np.array([-cl*co,-cl*so,-sl]).T
    return xyz,A

def nearest(t,q):
    t=np.asarray(t);q=np.asarray(q);idx=np.minimum(np.searchsorted(t,q),len(t)-1)
    prev=np.maximum(idx-1,0);return np.where(abs(t[prev]-q)<abs(t[idx]-q),prev,idx)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',type=Path,required=True)
    ap.add_argument('--docs',type=Path,required=True)
    a=ap.parse_args();stage=a.stage.resolve();plan=read(stage/'PLAN.json')
    # A readout is allowed only after both sealed stages, without opening reference payloads.
    native_seal=read(stage/'ALL_NATIVE_SEALED.json');eval_seal=read(stage/'EVALUATION_COMPLETE.json')
    assert native_seal['plan_sha256']==eval_seal['plan_sha256']==pin(stage/'PLAN.json')['sha256']
    maskfile=checked(plan['scenario_masks']);m=np.load(maskfile,allow_pickle=False)
    mt=m['BY2O_times'];masks={k[5:]:m[k] for k in m.files if k.startswith('BY2O_') and k!='BY2O_times'}
    full=rows(checked(plan['full_carrier']));rolling=rows(checked(plan['carrier']))
    pt=np.array([val(r,'measurement_time') for r in rolling]);ft=np.array([val(r,'measurement_time') for r in full])
    assert np.array_equal(pt,ft)
    classes=np.array(['FULL_VALID' if val(f,'valid') and val(r,'valid') else 'PARTIAL_VALID' if val(r,'valid') else 'FULL_ONLY_UNUSED' if val(f,'valid') else 'ROLLING_INVALID' for f,r in zip(full,rolling)])
    def classification(t):
        i=int(nearest(pt,[t])[0]);return str(classes[i]) if abs(pt[i]-t)<1e-6 else 'NO_PROVIDER_SLOT'
    def eventmask(data,timekey,mask):
        t=np.array([val(r,timekey) for r in data]);ix=nearest(mt,t)
        # Existing masks live on rounded native output keys; association is diagnostic, not event-state reconstruction.
        return [r for r,yes in zip(data,mask[ix]&(t>=3186.)&(t<=3563.)) if yes]
    out=stage/'READOUT';out.mkdir(exist_ok=True)
    inputs=[pin(stage/'PLAN.json'),pin(maskfile),plan['carrier'],plan['full_carrier']]
    arms={};metrics=[];source_summary=[];carrier_summary=[];event_summary=[];sa_records=[];carrier_records=[]
    for run in plan['runs']:
        arm=run['arm'];child=checked(run['child_plan']).parent;rid=run['run_id'];native=child/'NATIVE'/rid
        result=read(native/'RESULT.json');assert result['status']=='COMPLETED'
        assert result['online_reference_opens']==0
        ev=child/'EVALUATION'/rid/'FROZEN_EVALUATOR'
        er=np.genfromtxt(ev/'error_series.csv',delimiter=',',names=True,encoding='utf-8-sig')
        n=np.loadtxt(native/'LegSA_PORT_NAV.nav');kf=np.loadtxt(native/'KF_GINS_Navresult.nav');bias=np.loadtxt(native/'KF_GINS_IMU_ERR.txt')
        assert len(n)==len(kf)==len(bias)==len(mt)
        assert np.array_equal(kf[:,1],mt) and np.array_equal(er['time'],mt) and np.array_equal(bias[:,0],mt)
        sa=rows(native/'SOURCE_AWARE_WEIGHT_TRACE.csv');car=rows(native/'BASELINE3D_DIAGNOSTICS.csv')
        body=rows(native/'BODY_VELOCITY_EVENTS.csv');foot=rows(native/'SUPPORT_POSE_EVENTS.csv')
        manifest=read(native/'RUN_MANIFEST.json');summary=read(ev/'summary.json')
        for r in sa:
            r['provider_class']=classification(val(r,'time')) if r['source_id']=='dual_antenna_yaw' else 'OTHER_SOURCE'
            sa_records.append(dict(arm=arm,**r))
        for r in car:
            r['provider_class']=classification(val(r,'measurement_time',val(r,'time')))
            carrier_records.append(dict(arm=arm,**r))
        for name,mask in masks.items():
            e=er[mask];h=e['horizontal_err_m'];yaw=abs(e['yaw_err_deg'])
            metrics.append(dict(arm=arm,stratum=name,native_epochs=int(mask.sum()),evaluation_epochs=len(e),
                horizontal_rmse_m=rms(h),horizontal_p95_m=quant(h,.95),horizontal_p99_m=quant(h,.99),horizontal_max_m=quant(h,1),
                up_rmse_m=rms(e['err_u_m']),position_3d_rmse_m=rms(e['position_3d_err_m']),yaw_rmse_deg=rms(yaw),yaw_p95_deg=quant(yaw,.95),yaw_p99_deg=quant(yaw,.99),yaw_max_deg=quant(yaw,1),
                roll_rmse_deg=rms(e['roll_err_deg']),pitch_rmse_deg=rms(e['pitch_err_deg']),coverage_ratio=len(e)/int(mask.sum()) if mask.any() else None))
            ss=eventmask(sa,'time',mask)
            for source in sorted(set(r['source_id'] for r in sa)):
                sr=[r for r in ss if r['source_id']==source]
                for cl in sorted(set(r['provider_class'] for r in sa if r['source_id']==source)):
                    z=[r for r in sr if r['provider_class']==cl]
                    source_summary.append(dict(arm=arm,stratum=name,source=source,provider_class=cl,rows=len(z),accepted=sum(val(r,'accepted') for r in z),rejected=sum(val(r,'rejected') for r in z),
                        lsim_histogram=json.dumps(counts(z,'lsim_R_scale'),sort_keys=True),oim_histogram=json.dumps(counts(z,'oim_R_scale'),sort_keys=True),combined_histogram=json.dumps(counts(z,'combined_R_scale'),sort_keys=True),reason_histogram=json.dumps(counts(z,'reason_codes'),sort_keys=True),
                        scalar_yaw_not_applicable_rows=sum('NOT_APPLICABLE' in r['metadata_summary'] for r in z),
                        median_nis=quant([val(r,'nis') for r in z],.5),p95_nis=quant([val(r,'nis') for r in z],.95)))
            for kind,data,tk,ak in [('BODY',body,'state_time','accepted'),('FOOT',foot,'event_time_s','accepted')]:
                z=eventmask(data,tk,mask)
                event_summary.append(dict(arm=arm,stratum=name,kind=kind,event_rows=len(z),accepted=sum(val(r,ak) for r in z),reason_histogram=json.dumps(counts(z,'reason'),sort_keys=True),
                    foot_event_type_histogram=json.dumps(counts(z,'event_type'),sort_keys=True) if kind=='FOOT' else '',
                    foot_attempted=sum(val(r,'attempted') for r in z) if kind=='FOOT' else None))
        for cl in list(dict.fromkeys(classes.tolist()))+['NO_PROVIDER_SLOT']:
            z=[r for r in car if r['provider_class']==cl]
            carrier_summary.append(dict(arm=arm,provider_class=cl,fixed_provider_rows=int(sum(classes==cl)),diagnostic_rows=len(z),
                present=sum(val(r,'present') for r in z),valid=sum(val(r,'valid') for r in z),attempted=sum(val(r,'attempt') for r in z),accepted=sum(val(r,'accepted') for r in z),rejected=sum(val(r,'rejected') for r in z),
                accepted_unique_measurement_epochs=len(set(r['measurement_time'] for r in z if val(r,'accepted'))),reason_histogram=json.dumps(counts(z,'reason'),sort_keys=True)))
        arms[arm]=dict(n=n,bias=bias,er=er,sa=sa,car=car,body=body,foot=foot,manifest=manifest,summary=summary,result=result,replay=read(native/'SUPPORT_POSE_REPLAY_SUMMARY.json'))
        for fname in ['LegSA_PORT_NAV.nav','KF_GINS_Navresult.nav','KF_GINS_IMU_ERR.txt','RUN_MANIFEST.json','SOURCE_AWARE_WEIGHT_TRACE.csv','BASELINE3D_DIAGNOSTICS.csv','BODY_VELOCITY_EVENTS.csv','SUPPORT_POSE_EVENTS.csv','RESULT.json']:
            inputs.append(pin(native/fname))
        inputs.extend([pin(ev/'error_series.csv'),pin(ev/'summary.json'),run['binary']])
    x,y=arms['LEGACY'],arms['VECTOR'];nx,ny=x['n'],y['n']
    assert np.array_equal(nx[:,0],ny[:,0])
    px,Ax=ecef_and_ned(nx);py,Ay=ecef_and_ned(ny);Rx,Ry=rotations(nx[:,7:10]),rotations(ny[:,7:10])
    dp=np.einsum('nij,nj->ni',Ax,py-px)
    vy_e=np.einsum('nji,nj->ni',Ay,ny[:,4:7]);dv=np.einsum('nij,nj->ni',Ax,vy_e)-nx[:,4:7]
    lever=np.array(plan['sequences'][0]['evaluation']['position_lever_frd_m'])
    lx=np.einsum('nji,nj->ni',Ax,np.einsum('nij,j->ni',Rx,lever));ly=np.einsum('nji,nj->ni',Ay,np.einsum('nij,j->ni',Ry,lever))
    dl=np.einsum('nij,nj->ni',Ax,ly-lx)
    # Evaluation N/E are in its fixed reference-origin local frame. Report closure as a coordinate/rounding diagnostic.
    de=np.column_stack([y['er']['err_n_m']-x['er']['err_n_m'],y['er']['err_e_m']-x['er']['err_e_m'],x['er']['err_u_m']-y['er']['err_u_m']])
    drpy=(ny[:,7:10]-nx[:,7:10]+180)%360-180
    cross=np.einsum('nji,njk->nik',Rx,Ry)
    angle=np.rad2deg(np.arccos(np.clip((np.trace(cross,axis1=1,axis2=2)-1)/2,-1,1)))
    db=y['bias'][:,1:]-x['bias'][:,1:]
    effects=[]
    for name,mask in masks.items():
        effects.append(dict(stratum=name,epochs=int(mask.sum()),native_position_horizontal_rms_m=rms(np.linalg.norm(dp[mask,:2],axis=1)),native_position_3d_rms_m=rms(np.linalg.norm(dp[mask],axis=1)),native_position_horizontal_p99_m=quant(np.linalg.norm(dp[mask,:2],axis=1),.99),
            native_velocity_horizontal_rms_mps=rms(np.linalg.norm(dv[mask,:2],axis=1)),native_velocity_3d_rms_mps=rms(np.linalg.norm(dv[mask],axis=1)),
            attitude_rotation_angle_rms_deg=rms(angle[mask]),roll_pair_rms_deg=rms(drpy[mask,0]),pitch_pair_rms_deg=rms(drpy[mask,1]),yaw_pair_rms_deg=rms(drpy[mask,2]),
            gyro_bias_pair_rms_dph=rms(np.linalg.norm(db[mask,:3],axis=1)),accel_bias_pair_rms_mps2=rms(np.linalg.norm(db[mask,3:6]*1e-5,axis=1)),
            evaluation_lever_horizontal_rms_m=rms(np.linalg.norm(dl[mask,:2],axis=1)),evaluation_position_error_pair_horizontal_rms_m=rms(np.linalg.norm(de[mask,:2],axis=1)),
            native_plus_lever_horizontal_rms_m=rms(np.linalg.norm((dp+dl)[mask,:2],axis=1)),evaluation_minus_native_plus_lever_3d_rms_m=rms(np.linalg.norm((de-dp-dl)[mask],axis=1))))
    def sa_index(data):return {(r['source_id'],round(val(r,'time'),7)):r for r in data}
    sx,sy=sa_index(x['sa']),sa_index(y['sa']);paired=[]
    for key in sorted(sx.keys()|sy.keys(),key=lambda q:(q[1],q[0])):
        u,v=sx.get(key),sy.get(key)
        paired.append(dict(source=key[0],time_s=key[1],provider_class=(u or v)['provider_class'],legacy_present=u is not None,vector_present=v is not None,
            legacy_lsim=val(u,'lsim_R_scale') if u else None,vector_lsim=val(v,'lsim_R_scale') if v else None,legacy_oim=val(u,'oim_R_scale') if u else None,vector_oim=val(v,'oim_R_scale') if v else None,
            legacy_combined=val(u,'combined_R_scale') if u else None,vector_combined=val(v,'combined_R_scale') if v else None,legacy_reason=u['reason_codes'] if u else '',vector_reason=v['reason_codes'] if v else ''))
    affected=[r for r in paired if r['source']=='dual_antenna_yaw' and r['legacy_present'] and r['vector_present'] and r['legacy_lsim']!=r['vector_lsim']]
    first=affected[0] if affected else None
    changed=np.any(nx[:,1:]!=ny[:,1:],axis=1)|np.any(db!=0,axis=1)
    firstidx=int(np.flatnonzero(changed)[0]) if changed.any() else None
    onset=dict(first_paired_carrier_lsim_change=first,first_saved_state_difference_time_s=float(nx[firstidx,0]) if firstidx is not None else None,
        first_saved_state_difference_index=firstidx,identical_saved_state_rows_before_first_difference=firstidx,
        first_state_minus_first_carrier_s=float(nx[firstidx,0]-first['time_s']) if first is not None and firstidx is not None else None,
        definition='First exact difference at saved native precision; no significance threshold. First carrier LSIM change is paired actual SA consumption, independently provider-classified.',
        initial_state_and_bias_equal=bool(np.array_equal(nx[0],ny[0]) and np.array_equal(x['bias'][0],y['bias'][0])))
    if firstidx is not None:
        onset['first_difference_p_NED_m']=dp[firstidx].tolist();onset['first_difference_v_NED_mps']=dv[firstidx].tolist();onset['first_difference_rpy_deg']=drpy[firstidx].tolist()
    diagnostics={k:{z:v[z] for z in ['manifest','summary','result','replay']} for k,v in arms.items()}
    result=dict(schema='vector_direction_sa_readout.v1',plan=pin(stage/'PLAN.json'),runner=pin(__file__),input_pins=inputs,
        fixed_provider_counts=dict(Counter(classes.tolist())),fixed_mask_counts={k:int(v.sum()) for k,v in masks.items()},metrics=metrics,state_effects=effects,onset=onset,diagnostics=diagnostics,
        semantics=dict(reference_relative_not_true_accuracy=True,reference_payload_read=False,new_native_or_evaluation_calls=0,
            classification='Existing FULL.valid and ROLLING.valid only; no post-acceptance selection',
            SA_denominator='Only actual source-aware evaluations; hard carrier NIS may reject before SA',
            state_pair='VECTOR minus LEGACY; state difference is not reference accuracy',
            bias_units='KF_GINS_IMU_ERR gyro deg/h, accel mGal converted by 1e-5 to m/s2; scales ppm',
            event_masks='Closest original rounded native output time, input-defined masks; not an exact single-update jump',
            lever='Source-frozen assumed body lever, not an independently certified POI installation; evaluation frame differs slightly from instantaneous legacy NED'))
    products={'METRICS.csv':metrics,'STATE_EFFECT.csv':effects,'SOURCE_AWARE_SUMMARY.csv':source_summary,'CARRIER_SUMMARY.csv':carrier_summary,'BODY_FOOT_SUMMARY.csv':event_summary,'PAIRED_SA.csv':paired,'SOURCE_AWARE_ROWS.csv':sa_records,'CARRIER_ROWS.csv':carrier_records}
    for name,data in products.items():table(out/name,data)
    emit(out/'READOUT.json',result)
    # Keep the complete machine products in scratch, compact all-strata metrics/effects beside the report.
    a.docs.mkdir(exist_ok=True,parents=True)
    for name,data in [('VECTOR_DIRECTION_SA_METRICS.csv',metrics),('VECTOR_DIRECTION_SA_STATE_EFFECT.csv',effects),('VECTOR_DIRECTION_SA_CARRIER_COUNTS.csv',carrier_summary)]:table(a.docs/name,data)
    fullrows={r['arm']:r for r in metrics if r['stratum']=='full_window'}
    text=['# 向量方向 SA：BY2O 匹配读出','',
          '两臂仅改变 external 3D carrier 的 scalar yaw std 适用性；共用原足端 XY、SDK off、噪声与输入。以下为既有参考下的相对评价，不能当独立真值精度。原生与评价各两次已封存；本脚本没有运行求解器/评价器，也未读取参考 payload。','',
          '| arm | N | H RMSE m | Up RMSE m | yaw RMSE deg | H p99 m | yaw p99 deg |','|---|---:|---:|---:|---:|---:|---:|']
    for k,r in fullrows.items():text.append(f"| {k} | {r['evaluation_epochs']} | {r['horizontal_rmse_m']:.9f} | {r['up_rmse_m']:.9f} | {r['yaw_rmse_deg']:.9f} | {r['horizontal_p99_m']:.9f} | {r['yaw_p99_deg']:.9f} |")
    text+=['','所有原场景分母与指标保留在 `VECTOR_DIRECTION_SA_METRICS.csv`；场景重叠，不作为独立样本相加。包括极小/空分段，不按本轮误差或接受结果删点。','',
           '## 机制与实际共同状态','',f"固定供给分母：`{dict(Counter(classes.tolist()))}`。actual carrier 与 SA 分母分别统计，前级 NIS 拒绝不冒充 SA 拒绝。",'',
           '首次差异：', '```json',json.dumps(onset,ensure_ascii=False,indent=2),'```','',
           '完整 SA 权重/理由、carrier 接受、foot/SDK 及其他源计数位于 scratch READOUT；输出保存两个 RUN_MANIFEST 与 evaluator summary 全字段。原生 R/v/p/IMU bias 的逐场景差及评价杆臂项另表；共同状态差只能证明作用路径，不能自行证明精度改善。','',
           '## 限定与复现','',
           '本窗足端模型仍为原 XY；本次不声称解决 NMB1 共同平移的来源矛盾。scalar 不适用不是取消原向量 covariance、hard NIS、OIM 或 source cap。自然事件与现有 mask 全部保留，支持弧普通结束及零撤销不能认证故障重放。',
           '',f"Plan SHA256 `{pin(stage/'PLAN.json')['sha256']}`；读出 `{out/'READOUT.json'}`。",
           'SDK/foot 事件场景归属取原输出时刻最近键；不是精确事件前后状态。评价杆臂沿用旧假定 POI，未独立认证。',
           '本文数表由只读脚本产生；最终净收益判断同时看 H、Up、heading 与 tail，不以更小创新或某一分段改善替代。','']
    (a.docs/'VECTOR_DIRECTION_SA_BY2O_READOUT.md').write_text('\n'.join(text))
    print(json.dumps(dict(readout=str(out/'READOUT.json'),whole_window_metrics=fullrows,onset=onset,state_effect=effects[0]),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
