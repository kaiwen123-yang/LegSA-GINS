#!/usr/bin/env python3
"""All continuous dual-token support arcs versus first >=100 ms and old END.
Reads saved source only. No provider design, threshold change, time fit or NAV.
"""
from pathlib import Path
import argparse,csv,itertools,json,sys,time
import numpy as np
from nmb1_support_sdk_consistency import emit,sha,table,stats,addvec
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts/paper_rebuild/carrier_phase'))
from continuous_body_motion import rotation_exp
FEET=['FR','FL','RR','RL']


def union_duration(intervals):
    cursor=None;start=None;total=0.
    for a,b in sorted(intervals):
        if start is None:start,cursor=a,b
        elif a<=cursor:cursor=max(cursor,b)
        else:total+=cursor-start;start,cursor=a,b
    if start is not None:total+=cursor-start
    return total


def summarize(rows):
    usable=[r for r in rows if r['dt_s']>0]
    if not usable:return dict(n=len(rows),positive_duration_n=0)
    d=np.array([r['dt_s'] for r in usable]);c=np.array([[r['common_'+ax+'_m'] for ax in 'xyz'] for r in usable]);u=np.array([r['u_sdk_x_m'] for r in usable])
    return dict(n=len(rows),positive_duration_n=len(usable),pair_duration_s=float(d.sum()),
        unique_time_union_s=union_duration([(r['t0_s'],r['t1_s']) for r in usable]),duration_s=stats(d),
        common_axes_m={ax:stats(c[:,k]) for k,ax in enumerate('xyz')},
        common_rate_axes_mps={ax:stats(c[:,k]/d) for k,ax in enumerate('xyz')},
        time_weighted_common_rate_mps={ax:float(c[:,k].sum()/d.sum()) for k,ax in enumerate('xyz')},
        forward_deficit_to_sdk_integral_ratio=float(-c[:,0].sum()/u.sum()) if u.sum()!=0 else None,
        common_x_negative_fraction=float(np.mean(c[:,0]<0)))


def run(args):
    begun=time.monotonic();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    cache=Path(args.cache);episodesfile=Path(args.episodes);prior=Path(args.consistency);man=Path(args.manifest)
    with np.load(cache) as z:ns=z['native_ns'].copy();r=z['foot_position_body_frd'].copy();v=z['velocity_frd'].copy();w=z['gyro_frd'].copy()
    ep=list(csv.DictReader(episodesfile.open()));meta=json.loads(man.read_text());win=meta['native_window'];gap=max(meta['longest_position_intervals'],key=lambda z:z['duration_s'])
    arcs=[]
    for fa,fb in itertools.combinations(FEET,2):
        aa=sorted([e for e in ep if e['foot']==fa],key=lambda z:int(z['start_ns']));bb=sorted([e for e in ep if e['foot']==fb],key=lambda z:int(z['start_ns']))
        i=j=0
        while i<len(aa) and j<len(bb):
            a,b=aa[i],bb[j];ea=int(a['end_ns']) if a['end_ns'] else int(ns[-1])+1;eb=int(b['end_ns']) if b['end_ns'] else int(ns[-1])+1
            start=max(int(a['start_ns']),int(b['start_ns']));close=min(ea,eb)
            if start<close:arcs.append(dict(foot_i=fa,foot_j=fb,pair=fa+'-'+fb,token_i=a['token'],token_j=b['token'],start_ns=start,close_ns=close,source_right_censored=not a['end_ns'] and not b['end_ns']))
            if ea<=eb:i+=1
            if eb<=ea:j+=1
    arcs.sort(key=lambda z:(z['start_ns'],z['pair']));allrows=[]
    def measurement(i,j,fs):
        dur=(int(ns[j])-int(ns[i]))/1e9;D=np.eye(3);u=np.zeros(3)
        for k in range(i,j):
            h=(int(ns[k+1])-int(ns[k]))/1e9;u+=D@v[k]*h;D=D@rotation_exp(w[k]*h)
        yy=r[i,fs]-r[j,fs]@D.T
        ans=dict(t0_s=float(ns[i]/1e9),t1_s=float(ns[j]/1e9),dt_s=dur,source_segments=j-i)
        for name,val in [('common',yy.mean(axis=0)-u),('differential',yy[0]-yy[1]),('u_sdk',u),('foot_common',yy.mean(axis=0))]:addvec(ans,name,val)
        return ans
    windows={}
    old=list(csv.DictReader((prior/'INTERVALS.csv').open()))
    emit(out/'PLAN.json',dict(script_sha256=sha(__file__),input_pins={str(p):sha(p) for p in [cache,episodesfile,man,prior/'INTERVALS.csv']},
        arc='maximal intersection of two frozen confirmed support-token lifetimes, all six foot pairs; first eligible through last eligible source',
        endpoint='last source strictly before first token retirement, never first invalid source',
        short_arcs='all retained, zero-duration single-source arcs counted separately',
        prefix='first source at or after arc start+100ms if still eligible; no footpoint interpolation',
        scope='complete arcs and boundary-censored arcs counted separately for FULL and GAP',
        pair_time='all pairs included; overlap under >2 eligible feet is reported via separate unique union duration',
        gyro='same causal left ZOH',raw_reads=0,NAV_reads=0,reference_reads=0,native_calls=0,threshold_changes=0,new_provider=False))
    strata=[]
    for label,lo,hi in [('FULL',win[0],win[1]),('GAP',gap['t0_s'],gap['t1_s'])]:
        ln=int(np.ceil(lo*1e9));hn=int(np.floor(hi*1e9));rr=[];prefixes=[]
        for ai,a in enumerate(arcs):
            if a['close_ns']<=ln or a['start_ns']>hn:continue
            i=int(np.searchsorted(ns,max(a['start_ns'],ln)));j=int(np.searchsorted(ns,min(a['close_ns'],hn+1)))-1
            if j<i:continue
            left=a['start_ns']<ln;right=a['source_right_censored'] or a['close_ns']>hn
            base=dict(window=label,arc_id='ARC_%05d'%ai,pair=a['pair'],foot_i=a['foot_i'],foot_j=a['foot_j'],token_i=a['token_i'],token_j=a['token_j'],
                scope='COMPLETE' if not left and not right else 'BOUNDARY_CENSORED',left_censored=left,right_censored=right,
                first_token_retirement_s=a['close_ns']/1e9 if not a['source_right_censored'] else None)
            fs=[FEET.index(a['foot_i']),FEET.index(a['foot_j'])];row=dict(base,kind='WHOLE_AVAILABLE_ARC',**measurement(i,j,fs))
            row['shorter_than_100ms']=bool(int(ns[j])-int(ns[i])<100000000);rr.append(row);allrows.append(row)
            target=int(np.searchsorted(ns,int(ns[i])+100000000))
            if target<=j:
                pre=dict(base,kind='FIRST_AT_LEAST_100MS',**measurement(i,target,fs));prefixes.append(pre);allrows.append(pre)
        complete=[x for x in rr if x['scope']=='COMPLETE'];short=[x for x in complete if x['shorter_than_100ms']];long=[x for x in complete if not x['shorter_than_100ms']]
        cp=[x for x in prefixes if x['scope']=='COMPLETE'];censored=[x for x in rr if x['scope']!='COMPLETE']
        oldr=[]
        for x in old:
            if float(x['t0_s'])>=lo and float(x['t1_s'])<=hi:
                y={key:float(x[key]) for key in ['t0_s','t1_s','dt_s','u_sdk_x_m']+['common_'+ax+'_m' for ax in 'xyz']};oldr.append(y)
        windows[label]=dict(all_intersecting_arcs=len(rr),complete_arc_count=len(complete),complete_shorter_than_100ms_count=len(short),
            complete_single_source_zero_duration_count=sum(x['dt_s']==0 for x in complete),complete_at_least_100ms_count=len(long),boundary_censored_count=len(censored),
            all_complete_arcs=summarize(complete),complete_short_arcs=summarize(short),matched_long_whole_arcs=summarize(long),
            matched_long_first_100ms=summarize(cp),boundary_censored_available=summarize(censored),original_END=summarize(oldr))
        for kind,rows in [('ALL_COMPLETE',complete),('SHORT_COMPLETE',short),('MATCHED_LONG_WHOLE',long),('MATCHED_LONG_FIRST100',cp)]:
            for pair in sorted(set(x['pair'] for x in rows)):
                z=summarize([x for x in rows if x['pair']==pair]);row=dict(window=label,kind=kind,pair=pair,n=z['n'],positive_duration_n=z.get('positive_duration_n',0))
                if z.get('positive_duration_n'):
                    row['pair_duration_s']=z['pair_duration_s'];row['signed_common_x_rate_mps']=z['time_weighted_common_rate_mps']['x'];row['forward_deficit_ratio']=z['forward_deficit_to_sdk_integral_ratio']
                strata.append(row)
    table(out/'ARCS_AND_PREFIXES.csv',allrows);table(out/'PAIR_STRATA.csv',strata)
    result=dict(status='COMPLETE',windows=windows,raw_reads=0,NAV_reads=0,reference_reads=0,native_calls=0,wall_s=time.monotonic()-begun)
    emit(out/'SUMMARY.json',result)
    print(json.dumps({k:{'counts':{f:z[f] for f in ['all_intersecting_arcs','complete_arc_count','complete_shorter_than_100ms_count','complete_at_least_100ms_count','boundary_censored_count']},'rates':{f:dict(n=z[f]['n'],duration_s=z[f].get('pair_duration_s'),x_mps=z[f].get('time_weighted_common_rate_mps',{}).get('x'),deficit=z[f].get('forward_deficit_to_sdk_integral_ratio')) for f in ['all_complete_arcs','complete_short_arcs','matched_long_whole_arcs','matched_long_first_100ms','original_END']}} for k,z in windows.items()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['cache','episodes','consistency','manifest','output']:p.add_argument('--'+k,required=True)
    run(p.parse_args())
