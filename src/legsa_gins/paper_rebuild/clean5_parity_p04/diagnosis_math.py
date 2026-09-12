"""Preregistered descriptive diagnostics; no evaluator or filter execution."""
from __future__ import annotations
import numpy as np
import pandas as pd


def correlation(x,y):
    x,y=np.asarray(x,float),np.asarray(y,float);m=np.isfinite(x)&np.isfinite(y)
    return {'n':int(m.sum()),'excluded_nonfinite':int((~m).sum()),'r':float(np.corrcoef(x[m],y[m])[0,1]) if m.sum()>2 and np.std(x[m])>0 and np.std(y[m])>0 else 'UNAVAILABLE'}


def spectrum(t,x):
    t,x=np.asarray(t,float),np.asarray(x,float)
    if len(t)<4 or np.any(np.diff(t)<=0) or not np.isfinite(x).all():raise ValueError('Invalid spectrum support')
    dt=float(np.median(np.diff(t)));grid=np.arange(t[0],t[-1]+dt*.01,dt);y=np.interp(grid,t,x);y-=y.mean();n=len(y)
    size=1<<(2*n-1).bit_length();power=np.fft.rfft(y,size);acf=np.fft.irfft(power*power.conj(),size)[:n]
    acf=acf/acf[0] if acf[0]>0 else np.full(n,np.nan)
    crossings=np.flatnonzero(acf[1:]<=0)+1
    first=float((crossings[0]-1+acf[crossings[0]-1]/(acf[crossings[0]-1]-acf[crossings[0]]))*dt) if len(crossings) else 'UNAVAILABLE'
    fft_power=np.abs(np.fft.rfft(y*np.hanning(n)))**2;freq=np.fft.rfftfreq(n,dt)
    peaks=[k for k in range(1,len(freq)-1) if fft_power[k]>fft_power[k-1] and fft_power[k]>=fft_power[k+1]]
    peaks=sorted(peaks,key=lambda k:(-fft_power[k],k))[:5]
    top=[{'frequency_hz':float(freq[k]),'period_s':float(1/freq[k]),'hann_power':float(fft_power[k])} for k in peaks]
    return {'first_acf_zero_s':first,'dominant_period_s':top[0]['period_s'] if top else 'UNAVAILABLE','fft_top5':top,
        'uniform_dt_s':dt,'uniform_count':n,'native_count':len(t),'native_max_gap_s':float(np.diff(t).max()),
        'diagnostic_interpolated_count':int(sum(np.min(np.abs(t[max(0,np.searchsorted(t,z)-1):min(len(t),np.searchsorted(t,z)+1)]-z))>1e-9 for z in grid))},pd.DataFrame({'lag_s':np.arange(n)*dt,'acf':acf}),pd.DataFrame({'frequency_hz':freq,'hann_power':fft_power})


def bands(t,x):
    t,x=np.asarray(t,float),np.asarray(x,float);lo=np.searchsorted(t,t-5,side='left');hi=np.searchsorted(t,t+5,side='right')
    sums=np.r_[0,np.cumsum(x)];slow=(sums[hi]-sums[lo])/(hi-lo);fast=x-slow
    vs,vf,vt=map(float,(np.var(slow),np.var(fast),np.var(x)));cov=float(np.mean((slow-slow.mean())*(fast-fast.mean())))
    return {'slow_std':vs**.5,'fast_std':vf**.5,'total_std':vt**.5,'slow_variance':vs,'fast_variance':vf,'total_variance':vt,
        'sum_variances':vs+vf,'two_covariance':2*cov,'variance_closure_error':vs+vf+2*cov-vt,'slow_variance_fraction':vs/vt if vt else 'UNAVAILABLE',
        'partial_edge_count':int(((t-5<t[0])|(t+5>t[-1])).sum())},slow,fast


def phase_bins(t,x,updates):
    t,x,u=np.asarray(t,float),np.asarray(x,float),np.unique(np.asarray(updates,float));j=np.searchsorted(u,t,side='right')-1
    valid=(j>=0)&(j<len(u)-1);jv=j[valid];phase=(t[valid]-u[jv])/(u[jv+1]-u[jv]);bins=np.minimum((phase*10).astype(int),9)
    result=[]
    for k in range(10):
        vals=np.abs(x[valid][bins==k]);result.append({'phase_bin':k,'phase_start':k/10,'phase_end':(k+1)/10,'count':len(vals),'mean_abs_err_u_m':float(vals.mean()) if len(vals) else None})
    means=[r['mean_abs_err_u_m'] for r in result];complete=all(v is not None for v in means)
    return {'status':'AVAILABLE' if complete else 'UNAVAILABLE','outside_complete_update_intervals':int((~valid).sum()),
        'range_over_error_std':float(np.ptp(means)/np.std(x)) if complete and np.std(x)>0 else 'UNAVAILABLE',
        'phase_trend_r':correlation(np.arange(10)+.5,means)['r'] if complete else 'UNAVAILABLE'},result


def consistency(error,std):
    e,s=np.asarray(error,float),np.asarray(std,float);valid=np.isfinite(e)&np.isfinite(s)&(s>0);r=np.abs(e[valid])/s[valid]
    return {'n':len(e),'valid_n':int(valid.sum()),'nonfinite_error_count':int((~np.isfinite(e)).sum()),'nonfinite_std_count':int((~np.isfinite(s)).sum()),
        'nonpositive_std_count':int((np.isfinite(s)&(s<=0)).sum()),'median_abs_error_over_std':float(np.median(r)) if len(r) else 'UNAVAILABLE',
        'p95_abs_error_over_std':float(np.quantile(r,.95)) if len(r) else 'UNAVAILABLE','fraction_above_3sigma':float(np.mean(r>3)) if len(r) else 'UNAVAILABLE',
        'median_std':float(np.median(s[valid])) if len(r) else 'UNAVAILABLE','error_rmse':float(np.sqrt(np.mean(e[valid]**2))) if len(r) else 'UNAVAILABLE'}


def classify(*,overconfident,phase,coupling,slow_fraction,pvt_noise):
    if overconfident:return 'FILTER_OVERCONFIDENT'
    if isinstance(phase.get('range_over_error_std'),(int,float)) and phase['range_over_error_std']>=.5 and phase['phase_trend_r']>=.7:return 'UPDATE_SAWTOOTH'
    if any(isinstance(coupling.get(k),(int,float)) and abs(coupling[k])>=.5 for k in ['roll','pitch']):return 'ATTITUDE_COUPLED'
    if isinstance(slow_fraction,(int,float)) and slow_fraction>=.5:return 'SLOW_WANDER'
    if isinstance(coupling.get('nav_up'),(int,float)) and abs(coupling['nav_up'])>=.5 and isinstance(pvt_noise,(int,float)) and pvt_noise>=.1:return 'MEASUREMENT_NOISE'
    return 'UNDETERMINED'
