#!/usr/bin/env python3
"""Read saved NMB1 nominal-frame matched pair; no native, evaluator or raw reads."""
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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--new-stage',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();base=a.new_stage.parent
    old=base/'SUPPORT_POSE_NATIVE_NMB1_01';xyz=base/'SUPPORT_POSE_XYZ_NMB1_01'
    plan=nr.read(a.new_stage/'PLAN.json');seal=nr.read(a.new_stage/'ALL_NATIVE_SEALED.json')
    evaluation=nr.read(a.new_stage/'EVALUATION_SUMMARY.json')
    oldplan=nr.read(old/'PLAN.json');oldread=nr.read(old/'READOUT.json')
    assert len(seal['records'])==2 and all(x['online_reference_opens']==0 for x in seal['records'])
    gap=np.array(oldplan['gap_contract']['position_gap']);first=oldread['first_consumable_carrier_s']
    end=oldplan['sequences'][0]['full_window_s'][1]
    phases={'FULL_WINDOW':None,'BEFORE_POSITION_GAP':(-np.inf,gap[0]),'POSITION_GAP':tuple(gap),
            'RECOVERY_BEFORE_FIRST_CARRIER':(gap[1],first),'FROM_FIRST_CARRIER':(first,end+1e-6)}
    def masks(t):return {k:np.ones(len(t),bool) if lim is None else (t>=lim[0])&(t<lim[1]) for k,lim in phases.items()}
    specs={'OLD_NULL':(old,'REPLACE_NULL'),'OLD_XYZ':(xyz,'REPLACE_SUPPORT_XYZ'),
           'NOMINAL_NULL':(a.new_stage,'REPLACE_NULL'),'NOMINAL_XYZ':(a.new_stage,'REPLACE_SUPPORT_XYZ')}
    pins=[nr.pin(a.new_stage/'PLAN.json'),nr.pin(a.new_stage/'ALL_NATIVE_SEALED.json'),nr.pin(a.new_stage/'EVALUATION_SUMMARY.json')]
    data={};metrics=[];landmarks=[];effects=[];events=[];interactions=[];decomposition=[]
    for label,(stage,arm) in specs.items():
        root=stage/'NATIVE'/('NMB1__'+arm)
        files={k:root/v for k,v in [('nav','KF_GINS_Navresult.nav'),('bias','KF_GINS_IMU_ERR.txt'),
               ('foot','SUPPORT_POSE_EVENTS.csv'),('body','BODY_VELOCITY_EVENTS.csv'),('heading','HEADING_SOURCE_EVENTS.csv')]}
        files['errors']=stage/'EVALUATION'/(arm+'_ERRORS.csv');files['result']=root/'RESULT.json'
        pins.extend(nr.pin(x) for x in files.values())
        d={k:np.loadtxt(files[k]) for k in ('nav','bias')}
        d.update({k:rows(files[k]) for k in ('foot','body','heading')})
        d['errors']=np.genfromtxt(files['errors'],delimiter=',',names=True);d['result']=nr.read(files['result'])
        d['bias'][:,4:7]*=1e-5;d['rotation']=rotations(d['nav'][:,8:11])
        d['bodyv']=np.einsum('nji,nj->ni',d['rotation'],d['nav'][:,5:8]);data[label]=d
        t=d['nav'][:,1];assert np.array_equal(t,d['bias'][:,0]) and np.array_equal(t,d['errors']['time'])
        bm=masks(np.array([float(x['state_time']) for x in d['body']]))
        fm=masks(np.array([float(x['event_time_s']) for x in d['foot']]))
        for name,m in masks(t).items():
            e=d['errors'][m];h=np.hypot(e['err_n_m'],e['err_e_m'])
            foot=[x for x,z in zip(d['foot'],fm[name]) if z];body=[x for x,z in zip(d['body'],bm[name]) if z]
            metrics.append(dict(arm=label,stratum=name,status=d['result']['status'],epochs=int(m.sum()),
                H_RMSE_m=rms(h),H_p99_m=float(np.quantile(h,.99)),Up_RMSE_m=rms(e['err_u_m']),yaw_RMSE_deg=rms(e['yaw_err_deg']),
                body_events=len(body),body_accepted=sum(x['accepted']=='1' for x in body),
                foot_END=sum(x['event_type']=='END' for x in foot),foot_attempted=sum(x['attempted']=='1' for x in foot),foot_accepted=sum(x['accepted']=='1' for x in foot)))
        marks=[('ENTRY_PRE',gap[0])]+[(f'GAP_Q{q}',gap[0]+q/4*(gap[1]-gap[0])) for q in (1,2,3)]+[('EXIT_PRE',gap[1])]
        for name,target in marks:
            i=int(np.searchsorted(t,target)-1);n=d['nav'][i];b=d['bias'][i];u=d['bodyv'][i];e=d['errors'][i]
            landmarks.append(dict(arm=label,landmark=name,time_s=t[i],vn_mps=n[5],ve_mps=n[6],vd_mps=n[7],
                body_forward_mps=u[0],body_right_mps=u[1],body_down_mps=u[2],roll_deg=n[8],pitch_deg=n[9],yaw_deg=n[10],
                ba_x_mps2=b[4],ba_y_mps2=b[5],ba_z_mps2=b[6],H_error_m=float(np.hypot(e['err_n_m'],e['err_e_m'])),
                Up_error_m=e['err_u_m'],yaw_error_deg=e['yaw_err_deg']))
    t=data['OLD_NULL']['nav'][:,1];assert all(np.array_equal(t,d['nav'][:,1]) for d in data.values())
    pairs=[('OLD_NULL','OLD_XYZ'),('NOMINAL_NULL','NOMINAL_XYZ'),('OLD_NULL','NOMINAL_NULL'),('OLD_XYZ','NOMINAL_XYZ')]
    lever=np.array(oldplan['sequences'][0]['evaluation']['point_transform_lever_body_m'])
    for control,experimental in pairs:
        dx=data[control];dy=data[experimental];x=dx['nav'];y=dy['nav'];Rx=dx['rotation'];Ry=dy['rotation']
        dp=ned_difference(x,y);dv=y[:,5:8]-x[:,5:8];db=dy['bias'][:,4:7]-dx['bias'][:,4:7]
        dbv=dy['bodyv']-dx['bodyv'];dvbody=np.einsum('nji,nj->ni',Rx,dv);da=wrap(y[:,8:11]-x[:,8:11])
        dl=np.einsum('nij,j->ni',Ry-Rx,lever)
        for name,m in masks(t).items():
            row=dict(control=control,experimental=experimental,stratum=name,epochs=int(m.sum()),
                native_p_H_pair_RMS_m=rms(np.linalg.norm(dp[m,:2],axis=1)),native_p_Up_pair_RMS_m=rms(dp[m,2]),
                native_v_H_pair_RMS_mps=rms(np.linalg.norm(dv[m,:2],axis=1)),native_v_down_pair_RMS_mps=rms(dv[m,2]),
                evaluation_lever_H_pair_RMS_m=rms(np.linalg.norm(dl[m,:2],axis=1)))
            for j,axis in enumerate(('forward','right','down')):
                row['delta_v_projected_control_body_'+axis+'_mean_mps']=float(dvbody[m,j].mean())
                row['delta_v_projected_control_body_'+axis+'_RMS_mps']=rms(dvbody[m,j])
                row['delta_own_body_v_'+axis+'_RMS_mps']=rms(dbv[m,j])
                row['delta_ba_'+axis+'_mean_mps2']=float(db[m,j].mean())
                row['delta_ba_'+axis+'_RMS_mps2']=rms(db[m,j])
            for j,axis in enumerate(('roll','pitch','yaw')):
                row['delta_'+axis+'_mean_deg']=float(da[m,j].mean());row['delta_'+axis+'_RMS_deg']=rms(da[m,j])
            effects.append(row)
        if control not in ('OLD_NULL','NOMINAL_NULL') or experimental not in ('OLD_XYZ','NOMINAL_XYZ'):continue
        g=(t>=gap[0])&(t<gap[1]);flags=np.zeros(len(t),int)
        for records,key,bit,condition in [(dy['foot'],'event_time_s',1,lambda r:r['event_type']=='END' and r['accepted']=='1'),
                (dx['body'],'state_time',2,lambda r:r['accepted']=='1'),(dy['body'],'state_time',4,lambda r:r['accepted']=='1'),
                (dy['heading'],'time',8,lambda r:r['pvt_present']=='1')]:
            for r in records:
                if condition(r):
                    j=int(np.searchsorted(t,float(r[key])-5.1e-10))
                    if 0<j<len(t):flags[j]|=bit
        ddv=np.vstack((np.zeros((1,3)),np.diff(dv,axis=0)));ddb=np.vstack((np.zeros((1,3)),np.diff(db,axis=0)))
        ddvb=np.einsum('nji,nj->ni',Rx,ddv)
        for flag in sorted(set(flags[g])):
            m=g&(flags==flag);ii=np.flatnonzero(m)
            label='+'.join(s for b,s in [(1,'XYZ_FOOT_END'),(2,'NULL_SDK'),(4,'XYZ_SDK'),(8,'PVT_ROW')] if flag&b) or 'NO_TAGGED_UPDATE'
            row=dict(control=control,experimental=experimental,cell_kind=label,IMU_cells=int(m.sum()),
                fraction_pair_H_velocity_norm_increased=float(np.mean(np.linalg.norm(dv[ii,:2],axis=1)>np.linalg.norm(dv[ii-1,:2],axis=1))))
            for j,axis in enumerate(('forward','right','down')):
                row['pair_v_increment_'+axis+'_mean_mps']=float(ddvb[m,j].mean())
                row['pair_v_increment_'+axis+'_median_mps']=float(np.median(ddvb[m,j]))
                row['pair_ba_increment_'+axis+'_sum_mps2']=float(ddb[m,j].sum())
            events.append(row)
        mix=x[:,8:11].copy();mix[:,2]=y[:,10];Rm=rotations(mix);u=dx['bodyv']
        parts={'yaw':np.einsum('nij,nj->ni',Rm-Rx,u),'tilt':np.einsum('nij,nj->ni',Ry-Rm,u),
            'own_body_xy':np.einsum('nij,nj->ni',Ry[:,:,:2],dbv[:,:2]),'own_body_z_projection':Ry[:,:,2]*dbv[:,2,None]}
        assert np.max(abs(sum(parts.values())-dv))<1e-12
        for k,v in {**parts,'total':dv}.items():decomposition.append(dict(control=control,experimental=experimental,component=k,
            gap_H_velocity_pair_RMS_mps=rms(np.linalg.norm(v[g,:2],axis=1))))
    lookup={(r['arm'],r['stratum']):r for r in metrics}
    for phase in phases:
        oldb,oldx,newb,newx=[lookup[(k,phase)] for k in specs]
        for metric in ('H_RMSE_m','H_p99_m','Up_RMSE_m','yaw_RMSE_deg'):
            olddelta=oldx[metric]-oldb[metric];newdelta=newx[metric]-newb[metric]
            interactions.append(dict(stratum=phase,metric=metric,old_NULL=oldb[metric],old_XYZ=oldx[metric],
                nominal_NULL=newb[metric],nominal_XYZ=newx[metric],old_XYZ_minus_NULL=olddelta,
                nominal_XYZ_minus_NULL=newdelta,difference_of_differences=newdelta-olddelta))
    a.output.mkdir(parents=True,exist_ok=False)
    for name,rr in [('METRICS.csv',metrics),('FOOT_INTERACTION.csv',interactions),('NATIVE_STATE_EFFECT.csv',effects),
            ('STATE_LANDMARKS.csv',landmarks),('EVENT_CELL_SUMMARY.csv',events),('GAP_VELOCITY_DECOMPOSITION.csv',decomposition)]:table(a.output/name,rr)
    summary=dict(schema='NMB1.nominal_frame_readout.v1',runner=nr.pin(__file__),input_pins=pins,
        gap=gap.tolist(),first_carrier_s=first,metrics=metrics,interactions=interactions,effects=effects,
        landmarks=landmarks,event_groups=events,velocity_decomposition=decomposition,
        native_calls=0,evaluator_calls=0,raw_reads=0,reference_payload_reads=0,
        caveats=['Historical -1deg physical calibration unverified; this is a model diagnosis, not confirmed bug correction.',
                 'No carrier within gap. Source-only forward foot/SDK conflict is unchanged.',
                 'Bias numbers are native software-body state components, not a new sensor calibration.',
                 'Event cells include propagation and are not exact saved factor increments.',
                 'Velocity differences are inter-arm state differences; no reference velocity RMSE.',
                 'Old NULL uses earlier binary; default active math is preserved, binary identity is not equal.'],
        old_NULL_binary=oldplan['binary'],old_XYZ_binary=nr.read(xyz/'PLAN.json')['binary'],new_binary=plan['binary'])
    nr.emit(a.output/'READOUT.json',summary)
    print(json.dumps(dict(metrics=metrics,interactions=interactions),indent=2),flush=True)

if __name__=='__main__':main()
