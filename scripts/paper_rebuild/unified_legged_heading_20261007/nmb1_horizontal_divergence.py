#!/usr/bin/env python3
"""Read-only NMB1 saved-state divergence and event-cell attribution; no solver/reference."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts/paper_rebuild/carrier_phase')]
import continuous_heading_navigation as nr
from navigation_body_pair import rotations,rms,table


def rows(p):
    with p.open() as f:return list(csv.DictReader(f))


def wrap(x):return (x+180)%360-180


def ned_difference(x,y):
    lat=np.deg2rad(x[:,2]);h=x[:,4];e2=6.6943799901413165e-3;w=1-e2*np.sin(lat)**2
    rn=6378137/np.sqrt(w);rm=6378137*(1-e2)/w**1.5
    return np.column_stack((np.deg2rad(y[:,2]-x[:,2])*(rm+h),np.deg2rad(y[:,3]-x[:,3])*(rn+h)*np.cos(lat),x[:,4]-y[:,4]))


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    old=a.base/'SUPPORT_POSE_NATIVE_NMB1_01';new=a.base/'SUPPORT_POSE_XYZ_NMB1_01'
    roots={'A':old/'NATIVE/NMB1__SDK_NULL','B':old/'NATIVE/NMB1__REPLACE_NULL','XY':old/'NATIVE/NMB1__REPLACE_SUPPORT','XYZ':new/'NATIVE/NMB1__REPLACE_SUPPORT_XYZ'}
    plan=nr.read(old/'PLAN.json');gap=np.array(plan['gap_contract']['position_gap']);pins=[];data={};snapshots=[]
    for arm,root in roots.items():
        files={k:root/name for k,name in [('nav','KF_GINS_Navresult.nav'),('bias','KF_GINS_IMU_ERR.txt'),('std','KF_GINS_STD.txt'),('cov','STATE_COVARIANCE_SUPPORT.csv'),('foot','SUPPORT_POSE_EVENTS.csv'),('body','BODY_VELOCITY_EVENTS.csv'),('heading','HEADING_SOURCE_EVENTS.csv')]}
        pins.extend(nr.pin(f) for f in files.values())
        d={k:np.loadtxt(files[k]) for k in ('nav','bias','std')};d.update({k:rows(files[k]) for k in ('foot','body','heading')})
        d['bias'][:,1:4]*=np.pi/180/3600;d['bias'][:,4:7]*=1e-5;d['std'][:,13:16]*=1e-5
        cov=np.loadtxt(files['cov'],delimiter=',',skiprows=1);d['cov_range']=[float(cov[0,0]),float(cov[-1,0])];d['cov_gap_rows']=int(((cov[:,0]>=gap[0])&(cov[:,0]<=gap[1])).sum())
        errpath=(new/'EVALUATION/REPLACE_SUPPORT_XYZ_ERRORS.csv') if arm=='XYZ' else old/'EVALUATION'/({'A':'SDK_NULL','B':'REPLACE_NULL','XY':'REPLACE_SUPPORT'}[arm]+'_ERRORS.csv')
        pins.append(nr.pin(errpath));d['errors']=np.genfromtxt(errpath,delimiter=',',names=True)
        assert np.array_equal(d['nav'][:,1],d['bias'][:,0]) and np.array_equal(d['nav'][:,1],d['std'][:,0])
        data[arm]=d
    t=data['A']['nav'][:,1];assert all(np.array_equal(t,d['nav'][:,1]) for d in data.values())
    before=int(np.searchsorted(t,gap[0])-1);last=int(np.searchsorted(t,gap[1])-1);index=np.arange(before,last+1);g=(t>=gap[0])&(t<gap[1]);dt=np.diff(t)
    marks=[('ENTRY_PRE',gap[0])]+[(f'GAP_Q{q}',float(gap[0]+q/4*(gap[1]-gap[0]))) for q in (1,2,3)]+[('EXIT_PRE',gap[1])]
    for arm,d in data.items():
        n=d['nav'];b=d['bias'];s=d['std'];e=d['errors'];assert np.array_equal(e['time'],t)
        for name,target in marks:
            i=int(np.searchsorted(t,target)-1)
            snapshots.append(dict(arm=arm,landmark=name,target_s=target,actual_time_s=t[i],
                vn=n[i,5],ve=n[i,6],vd=n[i,7],roll_deg=n[i,8],pitch_deg=n[i,9],yaw_deg=n[i,10],
                ba_x_mps2=b[i,4],ba_y_mps2=b[i,5],ba_z_mps2=b[i,6],
                sigma_pn_m=s[i,1],sigma_pe_m=s[i,2],sigma_vn_mps=s[i,4],sigma_ve_mps=s[i,5],
                sigma_roll_deg=s[i,7],sigma_pitch_deg=s[i,8],sigma_yaw_deg=s[i,9],
                sigma_bax_mps2=s[i,13],sigma_bay_mps2=s[i,14],
                H_error_m=float(np.hypot(e['err_n_m'][i],e['err_e_m'][i])),yaw_error_deg=e['yaw_err_deg'][i]))
    decompositions=[];quarter=[];crossings=[];events=[];eventgroups=[];covlimits={}
    for arm,d in data.items():covlimits[arm]=dict(saved_full_P_rows_in_gap=d['cov_gap_rows'],full_P_only_initial_final_2s=True,diagonal_STD_available_all_IMU=True)
    for ctrl,exp in [('A','B'),('A','XYZ'),('B','XYZ'),('XY','XYZ')]:
        x=data[ctrl]['nav'];y=data[exp]['nav'];Rx=rotations(x[:,8:11]);Ry=rotations(y[:,8:11]);ux=np.einsum('nji,nj->ni',Rx,x[:,5:8]);uy=np.einsum('nji,nj->ni',Ry,y[:,5:8])
        mixed=x[:,8:11].copy();mixed[:,2]=y[:,10];Rmix=rotations(mixed)
        components={'yaw':np.einsum('nij,nj->ni',Rmix-Rx,ux),'roll_pitch':np.einsum('nij,nj->ni',Ry-Rmix,ux),
            'body_horizontal':np.einsum('nij,nj->ni',Ry[:,:,:2],(uy-ux)[:,:2]),'body_vertical_projection':Ry[:,:,2]*(uy-ux)[:,2,None]}
        dv=y[:,5:8]-x[:,5:8];dp=ned_difference(x,y);dyaw=wrap(y[:,10]-x[:,10]);db=data[exp]['bias'][:,4:7]-data[ctrl]['bias'][:,4:7]
        assert np.max(abs(sum(components.values())-dv))<1e-12
        total_integral=np.trapz(dv[index],t[index],axis=0);observed=dp[last]-dp[before]
        for name,v in {**components,'total_delta_velocity':dv}.items():
            integral=np.trapz(v[index],t[index],axis=0)
            decompositions.append(dict(control=ctrl,experimental=exp,component=name,
                horizontal_velocity_rms_mps=rms(np.linalg.norm(v[g,:2],axis=1)),integral_N_m=integral[0],integral_E_m=integral[1],
                integral_H_norm_m=float(np.linalg.norm(integral[:2])),observed_delta_p_change_N_m=observed[0],observed_delta_p_change_E_m=observed[1],
                position_minus_velocity_integral_N_m=(observed-total_integral)[0],position_minus_velocity_integral_E_m=(observed-total_integral)[1]))
        relative=dp-dp[before]
        for threshold in (.1,.5,1.,2.):
            passed=np.flatnonzero(g&(np.linalg.norm(relative[:,:2],axis=1)>=threshold))
            if len(passed):
                i=passed[0];crossings.append(dict(control=ctrl,experimental=exp,threshold_relative_gap_entry_m=threshold,time_s=t[i],elapsed_gap_s=t[i]-gap[0],
                    delta_pn_m=dp[i,0],delta_pe_m=dp[i,1],delta_vn_mps=dv[i,0],delta_ve_mps=dv[i,1],delta_yaw_deg=dyaw[i],
                    delta_roll_deg=y[i,8]-x[i,8],delta_pitch_deg=y[i,9]-x[i,9],delta_bax_mps2=db[i,0],delta_bay_mps2=db[i,1]))
        for q in range(4):
            lo=gap[0]+q/4*(gap[1]-gap[0]);hi=gap[0]+(q+1)/4*(gap[1]-gap[0]);m=(t>=lo)&(t<hi)
            ex=data[ctrl]['errors'];ey=data[exp]['errors'];angle=abs(dyaw[m]);horizontal_body=components['body_horizontal'][m,:2]
            quarter.append(dict(control=ctrl,experimental=exp,quarter=q+1,lo=lo,hi=hi,epochs=int(m.sum()),
                delta_p_horizontal_rms_m=rms(np.linalg.norm(dp[m,:2],axis=1)),delta_v_horizontal_rms_mps=rms(np.linalg.norm(dv[m,:2],axis=1)),
                delta_yaw_rms_deg=rms(dyaw[m]),delta_yaw_max_deg=float(angle.max()),
                yaw_rotation_H_rms_mps=rms(np.linalg.norm(components['yaw'][m,:2],axis=1)),
                body_horizontal_H_rms_mps=rms(np.linalg.norm(horizontal_body,axis=1)),
                body_vertical_projection_H_rms_mps=rms(np.linalg.norm(components['body_vertical_projection'][m,:2],axis=1)),
                delta_bax_mean_mps2=float(db[m,0].mean()),delta_bay_mean_mps2=float(db[m,1].mean()),
                control_H_RMSE_m=rms(np.hypot(ex['err_n_m'][m],ex['err_e_m'][m])),experimental_H_RMSE_m=rms(np.hypot(ey['err_n_m'][m],ey['err_e_m'][m])),
                control_yaw_RMSE_deg=rms(ex['yaw_err_deg'][m]),experimental_yaw_RMSE_deg=rms(ey['yaw_err_deg'][m])))
        # IMU output cells, including propagation. This is NOT a saved EKF factor increment.
        flags=np.zeros(len(t),int)
        def add(records,timekey,bit,select):
            for r in records:
                if select(r):
                    j=int(np.searchsorted(t,float(r[timekey])-5.1e-10))
                    if 0<j<len(t):flags[j]|=bit
        add(data[exp]['foot'],'event_time_s',1,lambda r:r['event_type']=='END' and r['accepted']=='1')
        add(data[ctrl]['body'],'state_time',2,lambda r:r['accepted']=='1')
        add(data[exp]['body'],'state_time',4,lambda r:r['accepted']=='1')
        add(data[exp]['heading'],'time',8,lambda r:r['pvt_present']=='1')
        ddv=np.vstack((np.zeros((1,3)),np.diff(dv,axis=0)));ddp=np.vstack((np.zeros((1,3)),np.diff(dp,axis=0)));ddb=np.vstack((np.zeros((1,3)),np.diff(db,axis=0)))
        dd_body=np.einsum('nji,nj->ni',Rx,ddv)
        for flag in sorted(set(flags[g])):
            m=g&(flags==flag);inds=np.flatnonzero(m)
            label='+'.join(name for bit,name in [(1,'EXP_FOOT_END'),(2,'CTRL_SDK'),(4,'EXP_SDK'),(8,'PVT_ROW')] if flag&bit) or 'NO_TAGGED_UPDATE'
            eventgroups.append(dict(control=ctrl,experimental=exp,cell_kind=label,IMU_cells=len(inds),
                delta_v_increment_N_sum_mps=float(ddv[m,0].sum()),delta_v_increment_E_sum_mps=float(ddv[m,1].sum()),
                delta_v_increment_forward_mean_mps=float(dd_body[m,0].mean()),delta_v_increment_right_mean_mps=float(dd_body[m,1].mean()),
                delta_v_increment_forward_median_mps=float(np.median(dd_body[m,0])),delta_v_increment_right_median_mps=float(np.median(dd_body[m,1])),
                fraction_pair_horizontal_velocity_norm_increased=float(np.mean(np.linalg.norm(dv[inds,:2],axis=1)>np.linalg.norm(dv[inds-1,:2],axis=1))),
                delta_p_increment_N_sum_m=float(ddp[m,0].sum()),delta_p_increment_E_sum_m=float(ddp[m,1].sum()),
                delta_bax_increment_sum_mps2=float(ddb[m,0].sum()),delta_bay_increment_sum_mps2=float(ddb[m,1].sum())))
            if flag:
                for i in inds:
                    events.append(dict(control=ctrl,experimental=exp,time_s=t[i],cell_kind=label,dt_s=t[i]-t[i-1],
                        paired_delta_v_before_N=dv[i-1,0],paired_delta_v_before_E=dv[i-1,1],paired_delta_v_after_N=dv[i,0],paired_delta_v_after_E=dv[i,1],
                        paired_increment_v_N=ddv[i,0],paired_increment_v_E=ddv[i,1],paired_increment_v_forward=dd_body[i,0],paired_increment_v_right=dd_body[i,1],
                        paired_increment_bax=ddb[i,0],paired_increment_bay=ddb[i,1],delta_yaw_deg=dyaw[i]))
    for name,outrows in [('STATE_LANDMARKS.csv',snapshots),('VELOCITY_DECOMPOSITION.csv',decompositions),('FIXED_GAP_QUARTERS.csv',quarter),
                         ('FIRST_DISPLACEMENT_CROSSINGS.csv',crossings),('EVENT_CELL_SUMMARY.csv',eventgroups),('EVENT_CELLS.csv',events)]:table(a.output/name,outrows)
    nr.emit(a.output/'READOUT.json',dict(runner=nr.pin(__file__),input_pins=pins,gap=gap.tolist(),reference_payload_reads=0,native_calls=0,evaluator_calls=0,
        covariance_visibility=covlimits,model='ordered exact velocity decomposition yaw then tilt then body XY and Z; algebraic not causal',
        event_semantics='first IMU output at/after event; 0.51 ns accounts only for 9-decimal NAV print rounding; paired increment includes propagation',
        supersedes_event_mapping='NMB1_HORIZONTAL_DIVERGENCE_01 used 0.1 us tolerance that could move exact raw events before native consumption; non-event decomposition unchanged',
        landmarks=snapshots,decomposition=decompositions,quarters=quarter,crossings=crossings,event_groups=eventgroups))
    print(json.dumps(dict(decomposition=decompositions,quarters=quarter,event_groups=eventgroups,crossings=crossings),indent=2),flush=True)
if __name__=='__main__':main()
