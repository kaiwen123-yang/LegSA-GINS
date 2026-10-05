#!/usr/bin/env python3
"""Read-only velocity-magnitude lag diagnostic; never reads a reference or updates inputs."""
from pathlib import Path
import hashlib, json, csv
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

ROOT = Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
STAGE = Path('/mnt/g/LegSA-GINS-project/新数据实验_20261005/STAGE_R5_NMB_XB')
OUT = Path(__file__).resolve().parent
BODY_SUMMARY = ROOT/'docs/paper_rebuild/TIM_EVIDENCE_20261005/data_and_selection/BODY_TIME_QUALITY_SUMMARY.csv'
LAGS = np.round(np.arange(-250,251)*.02, 2)
MIN_N, MIN_SPAN_S, MAX_BRACKET_S = 30, 10., .1
PEAK_DROP_R = .02

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def corr(x,y):
    if len(x)<MIN_N or np.std(x)<1e-8 or np.std(y)<1e-8: return None
    return float(np.corrcoef(x,y)[0,1])

def interp_valid(t,y,valid,q):
    """Only adjacent original valid rows; no extrapolation or invalid-row crossing."""
    right=np.searchsorted(t,q,side='left')
    exact=(right<len(t)) & (t[np.minimum(right,len(t)-1)]==q)
    left=np.maximum(right-1,0); rr=np.minimum(right,len(t)-1)
    supported=(right>0)&(right<len(t))&valid[left]&valid[rr]&((t[rr]-t[left])<=MAX_BRACKET_S)
    vals=y[left]+(y[rr]-y[left])*(q-t[left])/np.maximum(t[rr]-t[left],1e-30)
    supported=np.where(exact,valid[rr],supported)
    vals=np.where(exact,y[rr],vals)
    return vals,supported

def utc(t):
    return (datetime(2026,1,5,tzinfo=timezone.utc)+timedelta(seconds=float(t))).isoformat()

def main():
    files=[BODY_SUMMARY]+[STAGE/'INPUTS'/n/f for n in ['NMB1','NMB2','NMB3','NMB4'] for f in ['GNSS18.gnss','GO2_HV.csv']]
    before={str(p):sha(p) for p in files}
    body={r['file']:r for r in csv.DictReader(BODY_SUMMARY.open())}
    profiles=[]; summaries=[]
    for name in ['NMB1','NMB2','NMB3','NMB4']:
        g=np.loadtxt(STAGE/'INPUTS'/name/'GNSS18.gnss')
        h=pd.read_csv(STAGE/'INPUTS'/name/'GO2_HV.csv')
        gt=g[:,0]; ht=h.time.to_numpy(float)
        assert np.all(np.diff(gt)>0) and np.all(np.diff(ht)>0), 'Non-increasing input timestamps'
        gv=(g[:,16]==1)&np.isfinite(g[:,[0,7,8]]).all(axis=1)
        hv=(h.valid.to_numpy()==1)&h.update_flag.astype(str).str.lower().isin(['true','1']).to_numpy()&np.isfinite(h[['time','vn','ve']].to_numpy(float)).all(axis=1)
        gs=np.hypot(g[:,7],g[:,8]); hs=np.hypot(h.vn.to_numpy(float),h.ve.to_numpy(float))
        t=gt[gv]; x=gs[gv]
        q=t[:,None]+LAGS[None,:]
        ys,supported=interp_valid(ht,hs,hv,q)
        fixed=supported.all(axis=1)
        span=float(np.ptp(t[fixed])) if fixed.any() else 0.
        informative=fixed.sum()>=MIN_N and span>=MIN_SPAN_S
        rs=[corr(x[fixed],ys[fixed,i]) if informative else None for i in range(len(LAGS))]
        varying=[corr(x[supported[:,i]],ys[supported[:,i],i]) for i in range(len(LAGS))]
        for i,lag in enumerate(LAGS):
            profiles.append(dict(sequence=name,lag_s=float(lag),fixed_common_n=int(fixed.sum()),available_n=int(supported[:,i].sum()),pearson_r_fixed_support=rs[i],pearson_r_available_support_secondary=varying[i]))
        zero=250
        if all(r is not None for r in rs):
            rr=np.array(rs); peak=int(np.argmax(rr)); a=b=peak
            while a>0 and rr[a-1]>=rr[peak]-PEAK_DROP_R: a-=1
            while b<len(rr)-1 and rr[b+1]>=rr[peak]-PEAK_DROP_R: b+=1
            width=float(LAGS[b]-LAGS[a]); dynamic_range=float(rr.max()-rr.min())
            flat=bool(dynamic_range<.02 or width>=8.)
            peakdata=dict(peak_lag_s=float(LAGS[peak]),peak_r=float(rr[peak]),zero_r=float(rr[zero]),peak_minus_zero_r=float(rr[peak]-rr[zero]),peak_width_drop_0p02_s=width,peak_left_s=float(LAGS[a]),peak_right_s=float(LAGS[b]),full_profile_r_range=dynamic_range,flat_by_declared_rule=flat,peak_hits_search_boundary=bool(peak in (0,len(rr)-1)))
        else:
            peakdata=dict(peak_lag_s=None,peak_r=None,zero_r=rs[zero],peak_minus_zero_r=None,peak_width_drop_0p02_s=None,peak_left_s=None,peak_right_s=None,full_profile_r_range=None,flat_by_declared_rule=None,peak_hits_search_boundary=None)
        raw=body[name.lower()+'.txt']; rawstart=float(raw['first_t'])%86400.; rawend=float(raw['last_t'])%86400.
        commonstart=max(gt[0],ht[0]); commonend=min(gt[-1],ht[-1])
        sums=dict(sequence=name,gnss_total_n=len(g),gnss_velocity_valid_n=int(gv.sum()),hv_total_n=len(h),hv_valid_update_n=int(hv.sum()),gnss_start_s=float(gt[0]),gnss_end_s=float(gt[-1]),body_derived_hv_start_s=float(ht[0]),body_derived_hv_end_s=float(ht[-1]),raw_body_start_s=rawstart,raw_body_end_s=rawend,common_start_s=float(commonstart),common_end_s=float(commonend),common_span_s=float(max(0,commonend-commonstart)),gnss_start_utc=utc(gt[0]),gnss_end_utc=utc(gt[-1]),body_derived_hv_start_utc=utc(ht[0]),body_derived_hv_end_utc=utc(ht[-1]),common_start_utc=utc(commonstart),common_end_utc=utc(commonend),zero_available_n=int(supported[:,zero].sum()),fixed_common_n=int(fixed.sum()),fixed_common_span_s=span,gnss_speed_std_mps=float(np.std(x[fixed])) if fixed.any() else None,hv_zero_speed_std_mps=float(np.std(ys[fixed,zero])) if fixed.any() else None,**peakdata)
        summaries.append(sums)
    pd.DataFrame(profiles).to_csv(OUT/'LAG_PROFILE_ALL_2004.csv',index=False)
    pd.DataFrame(summaries).to_csv(OUT/'TIMING_SUMMARY_4.csv',index=False)
    after={str(p):sha(p) for p in files}; assert before==after
    receipt=dict(scope='READ_ONLY_PREPARED_INPUT_MACHINE_DIAGNOSTIC',utc=datetime.now(timezone.utc).isoformat(),lag_definition='corr(GNSS horizontal speed at t, HV horizontal speed at t+lag); positive lag means HV pattern is later on its recorded timestamp axis',grid_s=.02,search_range_s=[-5,5],primary_support='Same GNSS velocity-valid epochs at every one of 501 lags; linear HV interpolation on adjacent valid/update rows only',gnss_velocity_valid_column_zero_based=16,gnss_vn_ve_columns_zero_based=[7,8],minimum_common_n=MIN_N,minimum_span_s=MIN_SPAN_S,max_hv_interpolation_bracket_s=MAX_BRACKET_S,peak_width='Connected interval containing maximum with r >= max(r)-0.02',flat_rule='full-search max(r)-min(r)<0.02 OR connected peak width>=8 s; descriptive, not a statistical significance test',source_input_pins_before=before,source_input_pins_after=after,source_inputs_unchanged=True,reference_reads=0,native_runs=0,evaluator_runs=0,applied_time_offset_changes=0,results=summaries)
    (OUT/'TIMING_DIAGNOSTIC.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summaries,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__': main()
