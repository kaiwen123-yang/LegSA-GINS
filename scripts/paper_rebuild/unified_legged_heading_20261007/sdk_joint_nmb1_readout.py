#!/usr/bin/env python3
"""Read sealed SDK-joint NMB1 outputs only; no solver, evaluation or raw/reference access."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/paper_rebuild/carrier_phase')]
import continuous_heading_navigation as nr
from navigation_body_pair import rotations,rms,table
from nmb1_horizontal_divergence import ned_difference,wrap

def rows(path):
    with path.open() as f:return list(csv.DictReader(f))

def arr(rr,keys):
    return np.array([[float(r[k]) for k in keys] for r in rr],float)

def norm_stats(x,prefix):
    return {prefix+'_RMS':rms(x),prefix+'_median':float(np.median(x)),
            prefix+'_p95':float(np.quantile(x,.95)),prefix+'_max':float(np.max(x))}

def delta(rr,name,axes,suffix):
    return arr(rr,['delta_'+name+'_'+k+suffix for k in axes])

def mechanism(rr):
    b=arr(rr,['b_forward_after','b_right_after'])-arr(rr,['b_forward_before','b_right_before'])
    dp=delta(rr,'p','NED','_m');dv=delta(rr,'v','NED','_mps')
    phi=delta(rr,'phi','NED','_rad');ba=delta(rr,'ba','xyz','_mps2')
    out=dict(events=len(rr),b_change_nonzero=sum(np.linalg.norm(b,axis=1)>1e-14),
        db_forward_mean_mps=float(b[:,0].mean()),db_right_mean_mps=float(b[:,1].mean()),
        db_forward_signed_sum_mps=float(b[:,0].sum()),db_right_signed_sum_mps=float(b[:,1].sum()))
    for x,prefix in [(np.linalg.norm(b,axis=1),'db_norm_mps'),(np.linalg.norm(dp[:,:2],axis=1),'dp_H_m'),
        (abs(dp[:,2]),'dp_D_abs_m'),(np.linalg.norm(dv[:,:2],axis=1),'dv_H_mps'),(abs(dv[:,2]),'dv_D_abs_mps'),
        (np.linalg.norm(phi,axis=1)*180/np.pi,'dphi_left_NED_norm_deg'),
        (np.linalg.norm(ba,axis=1),'dba_norm_mps2')]:
        out.update(norm_stats(x,prefix))
    for j,axis in enumerate(('N','E','D')):
        out['dv_'+axis+'_mean_mps']=float(dv[:,j].mean())
        out['dba_'+('x','y','z')[j]+'_mean_mps2']=float(ba[:,j].mean())
    out['db_forward_positive_fraction']=float(np.mean(b[:,0]>0))
    out['db_right_positive_fraction']=float(np.mean(b[:,1]>0))
    dims=np.array([int(r['innovation_dimensions']) for r in rr])
    if np.all(dims>0):
        inn=arr(rr,['innovation_'+str(k) for k in range(6)])
        inn[np.arange(6)[None,:]>=dims[:,None]]=0
        out.update(norm_stats(np.linalg.norm(inn,axis=1),'innovation_norm'))
        for j in (0,1):
            out['innovation_'+str(j)+'_mean']=float(inn[:,j].mean())
            out['innovation_'+str(j)+'_positive_fraction']=float(np.mean(inn[:,j]>0))
        out['NIS_median']=float(np.median([float(r['nis']) for r in rr]))
        out['NIS_p95']=float(np.quantile([float(r['nis']) for r in rr],.95))
    else:
        out.update({k:None for k in ['innovation_norm_RMS','innovation_norm_median','innovation_norm_p95',
            'innovation_norm_max','innovation_0_mean','innovation_0_positive_fraction','innovation_1_mean','innovation_1_positive_fraction','NIS_median','NIS_p95']})
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--new-stage',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--doc-dir',type=Path)
    a=p.parse_args();base=a.new_stage.parent
    old=base/'SUPPORT_POSE_NATIVE_NMB1_01';xyz=base/'SUPPORT_POSE_XYZ_NMB1_01'
    plan=nr.read(a.new_stage/'PLAN.json');seal=nr.read(a.new_stage/'ALL_NATIVE_SEALED.json')
    evaluation=nr.read(a.new_stage/'EVALUATION_SUMMARY.json')
    assert len(seal['records'])==2 and all(x['online_reference_opens']==0 for x in seal['records'])
    assert seal['plan_sha256']==nr.digest(a.new_stage/'PLAN.json')
    assert evaluation['native_seal']['sha256']==nr.digest(a.new_stage/'ALL_NATIVE_SEALED.json')
    oldplan=nr.read(old/'PLAN.json');oldread=nr.read(old/'READOUT.json')
    gap=np.array(oldplan['gap_contract']['position_gap']);first=oldread['first_consumable_carrier_s']
    end=oldplan['sequences'][0]['full_window_s'][1]
    phases={'FULL_WINDOW':None,'BEFORE_POSITION_GAP':(-np.inf,gap[0]),'POSITION_GAP':tuple(gap),
        'RECOVERY_BEFORE_FIRST_CARRIER':(gap[1],first),'FROM_FIRST_CARRIER':(first,end+1e-6)}
    def masks(t):return {k:np.ones(len(t),bool) if v is None else (t>=v[0])&(t<v[1]) for k,v in phases.items()}
    def selected(rr,key,phase):
        lim=phases[phase]
        return rr if lim is None else [r for r in rr if lim[0]<=float(r[key])<lim[1]]
    specs={'OFF_NULL':(old,'REPLACE_NULL'),'OFF_XYZ':(xyz,'REPLACE_SUPPORT_XYZ'),
        'JOINT_NULL':(a.new_stage,'REPLACE_NULL'),'JOINT_XYZ':(a.new_stage,'REPLACE_SUPPORT_XYZ')}
    pins=[nr.pin(a.new_stage/n) for n in ['PLAN.json','ALL_NATIVE_SEALED.json','EVALUATION_SUMMARY.json']]
    data={};metrics=[];landmarks=[];effects=[];interactions=[];development=[];mechanisms=[];links=[];matched=[]
    foot_quality=[];counts=[]
    for label,(stage,arm) in specs.items():
        root=stage/'NATIVE'/('NMB1__'+arm)
        files={k:root/v for k,v in [('nav','KF_GINS_Navresult.nav'),('bias','KF_GINS_IMU_ERR.txt'),
            ('foot','SUPPORT_POSE_EVENTS.csv'),('body','BODY_VELOCITY_EVENTS.csv'),('heading','HEADING_SOURCE_EVENTS.csv'),
            ('manifest','RUN_MANIFEST.json'),('result','RESULT.json')]}
        files['errors']=stage/'EVALUATION'/(arm+'_ERRORS.csv')
        if label.startswith('JOINT'):
            files.update(diag=root/'SDK_DISCREPANCY_EVENTS.csv',sdk_summary=root/'SDK_DISCREPANCY_SUMMARY.json')
        pins.extend(nr.pin(x) for x in files.values())
        d={k:np.loadtxt(files[k]) for k in ('nav','bias')}
        d.update({k:rows(files[k]) for k in ('foot','body','heading')})
        d.update({k:nr.read(files[k]) for k in ('manifest','result')})
        d['errors']=np.genfromtxt(files['errors'],delimiter=',',names=True)
        d['bias'][:,4:7]*=1e-5;d['rotation']=rotations(d['nav'][:,8:11])
        d['bodyv']=np.einsum('nji,nj->ni',d['rotation'],d['nav'][:,5:8])
        if label.startswith('JOINT'):
            d['diag']=rows(files['diag']);d['sdk_summary']=nr.read(files['sdk_summary'])
        data[label]=d;t=d['nav'][:,1]
        assert np.array_equal(t,d['bias'][:,0]) and np.array_equal(t,d['errors']['time'])
        for phase,m in masks(t).items():
            e=d['errors'][m];h=np.hypot(e['err_n_m'],e['err_e_m'])
            metrics.append(dict(arm=label,stratum=phase,status=d['result']['status'],epochs=int(m.sum()),
                H_RMSE_m=rms(h),H_p99_m=float(np.quantile(h,.99)),Up_RMSE_m=rms(e['err_u_m']),yaw_RMSE_deg=rms(e['yaw_err_deg'])))
            body=selected(d['body'],'state_time',phase);foot=selected(d['foot'],'event_time_s',phase)
            heading=selected(d['heading'],'time',phase)
            counts.append(dict(arm=label,stratum=phase,SDK_tick_opportunities=len(body),
                SDK_source_present=sum(r['source_present']=='1' for r in body),
                SDK_valid=sum(r['valid']=='1' for r in body),SDK_accepted=sum(r['accepted']=='1' for r in body),
                SDK_seed_no_navigation_update=sum(r['reason']=='seed_joint_sdk_discrepancy_no_navigation_update' for r in body),
                SDK_suppressed=sum(r['reason']=='SUPPORT_INTERVAL_SDK_REPLACED' for r in body),
                SDK_other_not_accepted=sum(r['accepted']!='1' and r['reason'] not in
                    ('SUPPORT_INTERVAL_SDK_REPLACED','seed_joint_sdk_discrepancy_no_navigation_update') for r in body),
                foot_START=sum(r['event_type']=='START' for r in foot),foot_END=sum(r['event_type']=='END' for r in foot),
                foot_RETIRE=sum(r['event_type']=='RETIRE' for r in foot),foot_REVOKE=sum(r['event_type']=='REVOKE' for r in foot),
                foot_attempted=sum(r['attempted']=='1' for r in foot),foot_accepted=sum(r['accepted']=='1' for r in foot),
                carrier_attempted=sum(r['carrier_attempted']=='1' for r in heading),
                carrier_accepted=sum(r['carrier_attempted']=='1' and r['accepted']=='1' for r in heading),
                PVT_attempted=sum(r['pvt_attempted']=='1' for r in heading),
                PVT_accepted=sum(r['pvt_attempted']=='1' and r['accepted']=='1' for r in heading)))
            attempted=[r for r in foot if r['attempted']=='1']
            if attempted:
                nis=np.array([float(r['statistic']) for r in attempted])
                foot_quality.append(dict(arm=label,stratum=phase,attempted=len(attempted),
                    accepted=sum(r['accepted']=='1' for r in attempted),NIS_RMS=rms(nis),
                    NIS_median=float(np.median(nis)),NIS_p95=float(np.quantile(nis,.95))))
        marks=[('ENTRY_PRE',gap[0])]+[(f'GAP_Q{q}',gap[0]+q/4*(gap[1]-gap[0])) for q in (1,2,3)]+[
            ('EXIT_PRE',gap[1]),('FIRST_CARRIER_PRE',first),('FINAL',end+1e-6)]
        for name,target in marks:
            i=int(np.searchsorted(t,target)-1);n=d['nav'][i];b=d['bias'][i];u=d['bodyv'][i];e=d['errors'][i]
            landmarks.append(dict(arm=label,landmark=name,time_s=t[i],vn_mps=n[5],ve_mps=n[6],vd_mps=n[7],
                body_forward_mps=u[0],body_right_mps=u[1],body_down_mps=u[2],roll_deg=n[8],pitch_deg=n[9],yaw_deg=n[10],
                ba_x_mps2=b[4],ba_y_mps2=b[5],ba_z_mps2=b[6],H_error_m=float(np.hypot(e['err_n_m'],e['err_e_m'])),
                Up_error_m=e['err_u_m'],yaw_error_deg=e['yaw_err_deg']))
        if 'diag' not in d:continue
        for phase in phases:
            ds=selected(d['diag'],'time',phase)
            for kind in sorted(set(r['kind'] for r in ds)):
                rr=[r for r in ds if r['kind']==kind]
                mechanisms.append(dict(arm=label,stratum=phase,kind=kind,**mechanism(rr)))
        dt=np.array([float(r['time']) for r in d['diag']])
        for name,target in [('SEED',dt[0]+1e-9)]+marks:
            j=int(np.searchsorted(dt,target,side='left')-1);r=d['diag'][j]
            P=np.array([[float(r['Pbb00']),float(r['Pbb01'])],[float(r['Pbb01']),float(r['Pbb11'])]])
            development.append(dict(arm=label,landmark=name,state_time=float(r['time']),kind=r['kind'],
                b_forward_mps=float(r['b_forward_after']),b_right_mps=float(r['b_right_after']),
                Pbb00=P[0,0],Pbb01=P[0,1],Pbb11=P[1,1],std_b_forward_mps=float(np.sqrt(P[0,0])),
                std_b_right_mps=float(np.sqrt(P[1,1])),Pbb_eigen_min=float(np.linalg.eigvalsh(P)[0]),
                Pbb_eigen_max=float(np.linalg.eigvalsh(P)[1]),Pxb_frobenius=float(r['Pxb_frobenius']),
                Pbclone_frobenius=float(r['Pbclone_frobenius'])))
    t=data['OFF_NULL']['nav'][:,1];assert all(np.array_equal(t,d['nav'][:,1]) for d in data.values())
    lever=np.array(oldplan['sequences'][0]['evaluation']['point_transform_lever_body_m'])
    for control,experimental in [('OFF_NULL','OFF_XYZ'),('JOINT_NULL','JOINT_XYZ'),('OFF_NULL','JOINT_NULL'),('OFF_XYZ','JOINT_XYZ')]:
        dx=data[control];dy=data[experimental];x=dx['nav'];y=dy['nav'];Rx=dx['rotation'];Ry=dy['rotation']
        dp=ned_difference(x,y);dv=y[:,5:8]-x[:,5:8];db=dy['bias'][:,4:7]-dx['bias'][:,4:7]
        dvbody=np.einsum('nji,nj->ni',Rx,dv);da=wrap(y[:,8:11]-x[:,8:11])
        dl=np.einsum('nij,j->ni',Ry-Rx,lever)
        for phase,m in masks(t).items():
            row=dict(control=control,experimental=experimental,stratum=phase,epochs=int(m.sum()),
                native_p_H_pair_RMS_m=rms(np.linalg.norm(dp[m,:2],axis=1)),native_p_Up_pair_RMS_m=rms(dp[m,2]),
                native_v_H_pair_RMS_mps=rms(np.linalg.norm(dv[m,:2],axis=1)),native_v_D_pair_RMS_mps=rms(dv[m,2]),
                evaluation_lever_H_pair_RMS_m=rms(np.linalg.norm(dl[m,:2],axis=1)))
            for j,axis in enumerate(('forward','right','down')):
                row['delta_v_control_body_'+axis+'_mean_mps']=float(dvbody[m,j].mean())
                row['delta_v_control_body_'+axis+'_RMS_mps']=rms(dvbody[m,j])
                row['delta_ba_'+axis+'_mean_mps2']=float(db[m,j].mean())
                row['delta_ba_'+axis+'_RMS_mps2']=rms(db[m,j])
            for j,axis in enumerate(('roll','pitch','yaw')):
                row['delta_'+axis+'_mean_deg']=float(da[m,j].mean());row['delta_'+axis+'_RMS_deg']=rms(da[m,j])
            effects.append(row)
    lookup={(r['arm'],r['stratum']):r for r in metrics}
    for phase in phases:
        on,ox,jn,jx=[lookup[(k,phase)] for k in specs]
        for metric in ('H_RMSE_m','H_p99_m','Up_RMSE_m','yaw_RMSE_deg'):
            od=ox[metric]-on[metric];jd=jx[metric]-jn[metric]
            interactions.append(dict(stratum=phase,metric=metric,off_NULL=on[metric],off_XYZ=ox[metric],
                joint_NULL=jn[metric],joint_XYZ=jx[metric],off_XYZ_minus_NULL=od,joint_XYZ_minus_NULL=jd,
                descriptive_difference_of_differences=jd-od))
    jnull={r['identity']:r for r in data['JOINT_NULL']['diag'] if r['kind']=='BODY_HORIZONTAL_VELOCITY'}
    pending=[];ordinary=0
    for r in data['JOINT_XYZ']['diag']:
        if r['kind']=='FOOT_UPDATE':pending.append(r)
        elif r['kind']=='BODY_HORIZONTAL_VELOCITY':
            n=jnull[r['identity']]
            row=dict(time=float(r['time']),source_time=float(r['source_time']),identity=r['identity'],
                pending_accepted_foot_since_previous_SDK=len(pending))
            for k in ['innovation_0','innovation_1','nis','b_forward_before','b_right_before',
                'delta_p_N_m','delta_p_E_m','delta_p_D_m','delta_v_N_mps','delta_v_E_mps','delta_v_D_mps',
                'delta_phi_N_rad','delta_phi_E_rad','delta_phi_D_rad']:
                row['NULL_'+k]=float(n[k]);row['XYZ_'+k]=float(r[k]);row['XYZ_minus_NULL_'+k]=float(r[k])-float(n[k])
            matched.append(row)
            if pending:
                db=arr(pending,['b_forward_after','b_right_after'])-arr(pending,['b_forward_before','b_right_before'])
                links.append(dict(time=float(r['time']),SDK_source_time=float(r['source_time']),SDK_identity=r['identity'],
                    foot_count=len(pending),first_foot_time=float(pending[0]['time']),last_foot_time=float(pending[-1]['time']),
                    foot_ids='|'.join(f['identity'] for f in pending),seconds_after_last_foot=float(r['time'])-float(pending[-1]['time']),
                    other_ordinary_updates_after_first_foot=ordinary,foot_db_forward_sum_mps=float(db[:,0].sum()),
                    foot_db_right_sum_mps=float(db[:,1].sum()),
                    SDK_innovation_forward_mps=float(r['innovation_0']),SDK_innovation_right_mps=float(r['innovation_1']),
                    SDK_NIS=float(r['nis']),SDK_b_forward_before_mps=float(r['b_forward_before']),
                    SDK_b_right_before_mps=float(r['b_right_before']),
                    SDK_dp_H_m=float(np.linalg.norm(delta([r],'p','NE','_m'))),
                    SDK_dv_H_mps=float(np.linalg.norm(delta([r],'v','NE','_mps'))),
                    SDK_dphi_left_NED_norm_deg=float(np.linalg.norm(delta([r],'phi','NED','_rad'))*180/np.pi)))
            pending=[];ordinary=0
        elif pending:ordinary+=1
    tables={'METRICS':metrics,'FOOT_INTERACTION':interactions,'NATIVE_STATE_EFFECT':effects,'STATE_LANDMARKS':landmarks,
        'SOURCE_COUNTS':counts,'FOOT_NIS':foot_quality,'B_DEVELOPMENT':development,'FACTOR_EFFECTS':mechanisms,
        'FOOT_THEN_SDK':links,'MATCHED_SDK_EFFECTS':matched}
    link_summary=[]
    for phase in phases:
        rr=selected(links,'time',phase)
        if not rr:continue
        row=dict(stratum=phase,unique_SDK_events=len(rr),preceding_accepted_foot_events=sum(r['foot_count'] for r in rr),
            links_with_intervening_ordinary_updates=sum(r['other_ordinary_updates_after_first_foot']>0 for r in rr))
        for key in ['seconds_after_last_foot','SDK_dp_H_m','SDK_dv_H_mps','SDK_dphi_left_NED_norm_deg']:
            row.update(norm_stats(np.array([r[key] for r in rr]),key))
        link_summary.append(row)
    tables['FOOT_THEN_SDK_SUMMARY']=link_summary
    a.output.mkdir(parents=True,exist_ok=False)
    for name,rr in tables.items():
        table(a.output/(name+'.csv'),rr)
        if a.doc_dir is not None:table(a.doc_dir/('SDK_JOINT_NMB1_'+name+'.csv'),rr)
    summary=dict(schema='NMB1.SDK_joint_attribution.v1',runner=nr.pin(__file__),input_pins=pins,gap=gap.tolist(),
        first_carrier_s=first,metrics=metrics,interactions=interactions,effects=effects,counts=counts,
        b_development=development,factor_effects=mechanisms,foot_then_sdk_summary=link_summary,
        sdk_summaries={k:d['sdk_summary'] for k,d in data.items() if 'sdk_summary' in d},
        native_calls=0,evaluator_calls=0,raw_reads=0,reference_payload_reads=0,
        old_NULL_binary=oldplan['binary'],old_XYZ_binary=nr.read(xyz/'PLAN.json')['binary'],new_binary=plan['binary'],
        limits=['All arms use historical IMU Rx(-1deg); nominal-frame arms are excluded.',
          'Pair RMSE differences and their differences are descriptive interactions, not additive causal attribution.',
          'No carrier in fixed 163s gap; this pilot does not establish heading-filled navigation recovery.',
          'b is an effective source discrepancy with N=0 working assumption, not identified physical SDK calibration.',
          'No SDK-absent control: source event increments prove actual action, not net value of SDK temporal information.',
          'Seed is association augmentation with no navigation update or innovation sample.',
          'b before/after are conditional nominal plus error means; delta_phi is left NED tangent, not Euler.',
          'Factor increments are conditional mean changes before reset, not exact saved NAV jumps.',
          'Other ordinary source_time is state update time; only SDK and foot carry actual source/event time.',
          'Foot then SDK links may contain other updates; they show chronological shared-state action, not isolated causal b transport.',
          'Velocity quantities are inter-arm state differences, not reference RMSE.',
          'Old controls have different binary identities; preserved off math is source-reviewed, not byte-identical.',
          'Reference is Fixposition-derived and non-independent; readout reads only sealed existing error series.'])
    nr.emit(a.output/'READOUT.json',summary)
    print(json.dumps(dict(output=str(a.output),metrics=metrics,interactions=interactions,foot_then_sdk_summary=link_summary),indent=2),flush=True)

if __name__=='__main__':main()
