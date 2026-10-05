#!/usr/bin/env python3
"""Independent IMU cross-check using only prepared GNSS/heading/IMU inputs."""
from pathlib import Path
import numpy as np,pandas as pd,json
from datetime import datetime,timezone
from profile_nmb_speed_lags import STAGE,OUT,LAGS,sha,interp_valid,corr,MIN_N,MIN_SPAN_S,PEAK_DROP_R

def local_slope(t,y,w):
    z=np.full(len(t),np.nan)
    for i,ti in enumerate(t):
        a=np.searchsorted(t,ti-w/2);b=np.searchsorted(t,ti+w/2,side='right')
        tt=t[a:b]; yy=y[a:b]
        if len(tt)<4 or np.ptp(tt)<.8*w-1e-6 or np.max(np.diff(tt))>.40001: continue
        u=tt-tt.mean();z[i]=np.dot(u,yy-yy.mean())/np.dot(u,u)
    return z

def main():
    files=[STAGE/'INPUTS'/n/f for n in ['NMB1','NMB2'] for f in ['GNSS18.gnss','DUAL_HEADING.csv','IMU8.imu']]
    pins={str(f):sha(f) for f in files}; prof=[]; summaries=[]
    for name in ['NMB1','NMB2']:
        p=STAGE/'INPUTS'/name; imu=np.loadtxt(p/'IMU8.imu');g=np.loadtxt(p/'GNSS18.gnss');h=pd.read_csv(p/'DUAL_HEADING.csv')
        t=imu[:,0];dt=imu[:,7];assert np.all(np.diff(t)>0) and np.all(dt>0)
        assert np.isfinite(imu).all() and np.max(np.diff(t))<.1
        gyro=imu[:,3]/dt; anorm=np.linalg.norm(imu[:,4:7]/dt[:,None],axis=1)
        static_g=float(np.median(anorm[t<t[0]+5]))
        u=np.arange(np.ceil(t[0]/.02)*.02,t[-1],.02)
        gy=np.interp(u,t,gyro); ae=np.abs(np.interp(u,t,anorm)-static_g)
        for w in [2.,1.]:
            n=int(round(w/.02))+1
            gy_s=pd.Series(gy).rolling(n,center=True,min_periods=n).mean().to_numpy()
            ae_s=pd.Series(ae).rolling(n,center=True,min_periods=n).mean().to_numpy()
            ht=h.time.to_numpy(float);hy=np.unwrap(np.deg2rad(h.yaw_deg.to_numpy(float)))
            gv=(g[:,16]==1)&np.isfinite(g[:,[0,7,8]]).all(axis=1)
            gt=g[gv,0];gs=np.hypot(g[gv,7],g[gv,8])
            signals=[('signed_heading_rate_vs_gyro_z',ht,local_slope(ht,hy,w),gy_s),('abs_speed_derivative_vs_abs_accnorm_minus_static_g',gt,np.abs(local_slope(gt,gs,w)),ae_s)]
            for label,qt,x,y in signals:
                validx=np.isfinite(x);qt=qt[validx];x=x[validx]
                ys,support=interp_valid(u,y,np.isfinite(y),qt[:,None]+LAGS[None,:])
                fixed=support.all(axis=1); span=float(np.ptp(qt[fixed])) if fixed.any() else 0.
                rs=[corr(x[fixed],ys[fixed,i]) if span>=MIN_SPAN_S else None for i in range(len(LAGS))]
                for i,lag in enumerate(LAGS):prof.append(dict(sequence=name,signal=label,centered_smoothing_window_s=w,lag_s=float(lag),fixed_common_n=int(fixed.sum()),pearson_r=rs[i]))
                if all(v is not None for v in rs):
                    r=np.array(rs); k=int(np.argmax(r));a=b=k
                    while a>0 and r[a-1]>=r[k]-PEAK_DROP_R:a-=1
                    while b<len(r)-1 and r[b+1]>=r[k]-PEAK_DROP_R:b+=1
                    result=dict(zero_r=float(r[250]),peak_r=float(r[k]),peak_lag_s=float(LAGS[k]),peak_minus_zero_r=float(r[k]-r[250]),peak_width_drop_0p02_s=float(LAGS[b]-LAGS[a]),peak_hits_boundary=bool(k in(0,len(r)-1)),minimum_r=float(r.min()))
                else:result=dict(zero_r=None,peak_r=None,peak_lag_s=None,peak_minus_zero_r=None,peak_width_drop_0p02_s=None,peak_hits_boundary=None,minimum_r=None)
                summaries.append(dict(sequence=name,signal=label,centered_smoothing_window_s=w,input_signal_valid_n=len(x),fixed_common_n=int(fixed.sum()),fixed_common_span_s=span,imu_first_5s_median_accnorm_mps2=static_g,imu_max_timestamp_gap_s=float(np.max(np.diff(t))),**result))
    pd.DataFrame(prof).to_csv(OUT/'IMU_CROSSCHECK_LAG_PROFILE_4008.csv',index=False)
    pd.DataFrame(summaries).to_csv(OUT/'IMU_CROSSCHECK_SUMMARY_8.csv',index=False)
    after={str(f):sha(f) for f in files};assert pins==after
    receipt=dict(scope='READ_ONLY_PREPARED_INPUT_IMU_CROSSCHECK',utc=datetime.now(timezone.utc).isoformat(),lag_definition='corr(GNSS-derived signal(t), IMU-derived signal(t+lag))',lag_grid_s=.02,range_s=[-5,5],imu8_format='timestamp; angular increments xyz rad; specific-force increments xyz m/s; integration duration s. Rates = increments / recorded duration.',heading_source='Existing DUAL_HEADING rows (prepared dual-fixed selection), unwrapped radians, centered local linear slope; no smoothing across GNSS gap >0.40001 s.',speed_source='Existing GNSS18 velocity-valid records, absolute centered local speed slope.',imu_smoothing='Centered 2 s mean primary; 1 s centered mean sensitivity, uniform 0.02 s interpolation within original time bounds only.',gravity_proxy='First 5 s IMU acceleration-norm median; its stationarity is assumed for this proxy, not calibrated gravity.',acceleration_comparability='Absolute acceleration-norm deviation is a gait/vertical-force proxy, not horizontal tangential acceleration. Weak correlation cannot establish timing.',gyro_comparability='Body gyro z approximates heading rate near level; tilt and dual-HP angular noise remain. Signed convention fixed, no best-axis/sign search.',support='Same valid GNSS-derived epochs across all501 lag values; minimum30 epochs/10 s span.',input_pins_before=pins,input_pins_after=after,inputs_unchanged=True,reference_reads=0,native_runs=0,evaluator_runs=0,parameter_or_input_changes=0,results=summaries)
    (OUT/'IMU_CROSSCHECK_DIAGNOSTIC.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
