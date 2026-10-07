#!/usr/bin/env python3
"""Saved-source foot kinematics and support-phase diagnosis, no estimator or truth."""
from pathlib import Path
import argparse,csv,json,sys,time
import numpy as np
from nmb1_support_sdk_consistency import emit,sha,table,stats,correlation,addvec,vector
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts/paper_rebuild/carrier_phase'))
from legsa_gins.paper_rebuild.carrier_phase.support_arcs import SupportArcTracker,SupportPolicy,FootForceThreshold
from continuous_body_motion import rotation_exp
FEET=['FR','FL','RR','RL']


def weighted_stats(a,w):
    a,w=np.asarray(a,float),np.asarray(w,float)
    return dict(n=len(a),time_s=float(w.sum()),mean=float(np.average(a,weights=w)),
        rms=float(np.sqrt(np.average(a*a,weights=w))),median=float(np.median(a)),p95=float(np.quantile(a,.95)),
        abs_p95=float(np.quantile(abs(a),.95)))


def run(args):
    begun=time.monotonic();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    cache=Path(args.cache);prior=Path(args.consistency);provider=Path(args.provider);oldcache=Path(args.old_gyro_cache)
    with np.load(cache) as z:
        ns=z['native_ns'].copy();w=z['gyro_frd'].copy();v=z['velocity_frd'].copy()
        r=z['foot_position_body_frd'].copy();q=z['foot_speed_body_frd'].copy();force=z['foot_force'].copy()
    tt=ns/1e9;dt=np.diff(ns)/1e9;fd=np.diff(r,axis=0)/dt[:,None,None]
    meta=json.loads((provider/'MANIFEST.json').read_text());frozen=meta['frozen']
    src=list(csv.DictReader((prior/'INTERVALS.csv').open()))
    pins={str(p):sha(p) for p in [cache,oldcache,prior/'INTERVALS.csv',prior/'PLAN.json',provider/'MANIFEST.json']}
    emit(out/'PLAN.json',dict(script_sha256=sha(__file__),input_pins=pins,
        model='v_foot=-foot_speed_body-gyro cross foot_position_body; FD variant substitutes source finite difference; lever=0',
        finite_difference='(r[k+1]-r[k])/source_dt, represents interval-average derivative, compared to left and endpoint-average SDK foot_speed',
        frozen=frozen,support_phase='offline normalized time since confirmed stance to first token retirement; descriptive future boundary never online acceptance',
        force_unit='SDK proxy units, not calibrated Newtons',raw_reads=0,reference_reads=0,NAV_reads=0,native_calls=0,
        fits=0,new_gates=0,velocity_is_truth=False,source_frame='inherited body FRD',body_offset_applied_again=False))
    policy=SupportPolicy(tuple(FootForceThreshold(f,on,off) for f,on,off in zip(FEET,frozen['force_on'],frozen['force_off'])),frozen['dwell_s'],frozen['source_max_age_ns']/1e9)
    tr=SupportArcTracker(policy,stream_id='NMB1_SOURCE_DIAGNOSIS')
    tokens=np.zeros((len(ns),4),dtype=np.int64);tokenmap={};episodes={}
    for k,t in enumerate(tt):
        state=tr.update(float(t),dict(zip(FEET,map(float,force[k]))),available_time_s=float(t))
        for j,foot in enumerate(state.feet):
            if foot.token:
                token=tokenmap.setdefault(foot.token,len(tokenmap)+1);tokens[k,j]=token
                if token not in episodes:episodes[token]=dict(foot=FEET[j],start_ns=int(ns[k]),end_ns=None)
            if k and tokens[k-1,j] and tokens[k-1,j]!=tokens[k,j]:episodes[int(tokens[k-1,j])]['end_ns']=int(ns[k])
    # Compare eligibility and actual transition locations to old frozen cache.
    with np.load(oldcache) as z:
        oldns=np.rint(z['times']*1e9).astype(np.int64);olde=z['episodes'].copy()
    pp=np.searchsorted(oldns,ns);matched=(pp<len(oldns)) & (oldns[np.minimum(pp,len(oldns)-1)]==ns)
    commonk=np.flatnonzero(matched);usedlo=min(float(x['t0_s']) for x in src)
    checkk=commonk[tt[commonk]>=usedlo]
    eligible_mismatch=int(np.count_nonzero((tokens[checkk]>0)!=(olde[pp[checkk]]>0)))
    left_transition=(tokens[1:]!=tokens[:-1]);old_transition=np.zeros_like(left_transition)
    k=np.flatnonzero(matched[1:]&matched[:-1]);old_transition[k]=olde[pp[k+1]]!=olde[pp[k]]
    transition_mismatch=int(np.count_nonzero(left_transition[k[tt[k]>=usedlo]]!=old_transition[k[tt[k]>=usedlo]]))
    perfoot=[];pairs=[];segments=[];endpoint_cache_max=0.;continuity_fail=0
    ev={(x['clone_id'],x['event_type']):x for x in csv.DictReader((provider/'SUPPORT_POSE_EVENTS.csv').open())}
    for sr in src:
        n0=round(float(sr['t0_s'])*1e9);n1=round(float(sr['t1_s'])*1e9)
        i=int(np.searchsorted(ns,n0));j=int(np.searchsorted(ns,n1));dur=(n1-n0)/1e9
        if ns[i]!=n0 or ns[j]!=n1:raise ValueError('Exact endpoints missing')
        fs=[FEET.index(sr['foot_i']),FEET.index(sr['foot_j'])]
        D=np.eye(3);u=np.zeros(3);ufsq=np.zeros((2,3));ufdf=np.zeros((2,3));rdotint=np.zeros((2,3));qint=np.zeros((2,3));qavgint=np.zeros((2,3))
        local=[]
        for kk in range(i,j):
            for ff,ffidx in enumerate(fs):
                rot=np.cross(w[kk],r[kk,ffidx]);vfq=-q[kk,ffidx]-rot;vffd=-fd[kk,ffidx]-rot
                cvq=vfq-v[kk];cvfd=vffd-v[kk];qd=fd[kk,ffidx]-q[kk,ffidx];qad=fd[kk,ffidx]-(q[kk,ffidx]+q[kk+1,ffidx])/2
                tok=int(tokens[kk,ffidx]);ep=episodes[tok]
                phase=((int(ns[kk])-ep['start_ns'])/(ep['end_ns']-ep['start_ns'])) if ep['end_ns'] else None
                z=dict(clone_id=sr['clone_id'],inside_main_gap=sr['inside_main_gap'],pair=sr['pair'],foot=FEET[ffidx],
                    time_s=float(tt[kk]),dt_s=float(dt[kk]),force=float(force[kk,ffidx]),
                    force_margin_above_off=float(force[kk,ffidx]-frozen['force_off'][ffidx]),
                    stance_age_s=(int(ns[kk])-ep['start_ns'])/1e9,stance_phase=phase,
                    interval_phase=(int(ns[kk])-n0)/(n1-n0),token=tok,sdk_speed_xy_mps=float(np.linalg.norm(v[kk,:2])))
                for name,val in [('foot_speed',q[kk,ffidx]),('foot_fd',fd[kk,ffidx]),('fd_minus_speed',qd),('fd_minus_avg_speed',qad),('gyro_cross_r',rot),('v_foot_speed',vfq),('v_foot_fd',vffd),('cv_speed',cvq),('cv_fd',cvfd),('sdk_velocity',v[kk])]:addvec(z,name,val,'mps')
                segments.append(z);local.append(z)
                ufsq[ff]+=D@vfq*dt[kk];ufdf[ff]+=D@vffd*dt[kk]
                qint[ff]+=q[kk,ffidx]*dt[kk];qavgint[ff]+=(q[kk,ffidx]+q[kk+1,ffidx])/2*dt[kk]
            u+=D@v[kk]*dt[kk];D=D@rotation_exp(w[kk]*dt[kk])
        yy=r[i,fs]-r[j,fs]@D.T
        pair=dict(clone_id=sr['clone_id'],t0_s=sr['t0_s'],t1_s=sr['t1_s'],dt_s=dur,inside_main_gap=sr['inside_main_gap'],pair=sr['pair'])
        addvec(pair,'endpoint_common',yy.mean(axis=0)-u);addvec(pair,'speed_integral_common',ufsq.mean(axis=0)-u);addvec(pair,'fd_integral_common',ufdf.mean(axis=0)-u)
        addvec(pair,'speed_integral_minus_endpoint',ufsq.mean(axis=0)-yy.mean(axis=0));addvec(pair,'fd_integral_minus_endpoint',ufdf.mean(axis=0)-yy.mean(axis=0))
        pair['force_mean_sdk_units']=float(np.mean(force[i:j,fs]));pair['minimum_force_margin_sdk_units']=float(min((force[i:j,ffidx]-frozen['force_off'][ffidx]).min() for ffidx in fs))
        pairages=[];pairphases=[];endphases=[];close_remaining=[]
        for ff,ffidx in enumerate(fs):
            tok=int(tokens[i,ffidx]);ep=episodes[tok]
            continuous=bool(np.all(tokens[i:j+1,ffidx]==tok) and tok>0)
            continuity_fail+=int(not continuous)
            startage=(n0-ep['start_ns'])/1e9;phase0=(n0-ep['start_ns'])/(ep['end_ns']-ep['start_ns']) if ep['end_ns'] else None
            phase1=(n1-ep['start_ns'])/(ep['end_ns']-ep['start_ns']) if ep['end_ns'] else None
            pairages.append(startage)
            if phase0 is not None:pairphases.append(phase0);endphases.append(phase1);close_remaining.append((ep['end_ns']-n1)/1e9)
            for typ,idx in [('START',i),('END',j)]:
                ee=ev[(sr['clone_id'],typ)];pos=np.array([float(ee['r_'+('i' if ff==0 else 'j')+'_body_frd_'+ax+'_m']) for ax in 'xyz'])
                endpoint_cache_max=max(endpoint_cache_max,float(abs(pos-r[idx,ffidx]).max()))
            pf=dict(clone_id=sr['clone_id'],t0_s=sr['t0_s'],t1_s=sr['t1_s'],dt_s=dur,inside_main_gap=sr['inside_main_gap'],pair=sr['pair'],foot=FEET[ffidx],
                source_samples=j-i,token=tok,source_support_continuous=continuous,stance_start_age_s=startage,
                stance_start_phase=phase0,stance_end_phase=phase1,
                stance_end_remaining_s=(ep['end_ns']-n1)/1e9 if ep['end_ns'] else None,
                force_mean_sdk_units=float(np.mean(force[i:j,ffidx])),force_min_sdk_units=float(np.min(force[i:j+1,ffidx])))
            for name,val in [('r_delta',r[j,ffidx]-r[i,ffidx]),('q_integral',qint[ff]),('q_avg_integral',qavgint[ff]),
                ('q_integral_minus_r_delta',qint[ff]-(r[j,ffidx]-r[i,ffidx])),('q_avg_integral_minus_r_delta',qavgint[ff]-(r[j,ffidx]-r[i,ffidx])),
                ('endpoint_c',yy[ff]-u),('speed_integral_c',ufsq[ff]-u),('fd_integral_c',ufdf[ff]-u),
                ('speed_integral_minus_endpoint',ufsq[ff]-yy[ff]),('fd_integral_minus_endpoint',ufdf[ff]-yy[ff])]:addvec(pf,name,val)
            perfoot.append(pf)
        pair['start_age_min_s']=min(pairages);pair['start_age_mean_s']=float(np.mean(pairages));pair['start_phase_mean']=float(np.mean(pairphases)) if pairphases else None
        pair['end_phase_mean']=float(np.mean(endphases)) if endphases else None;pair['end_remaining_min_s']=min(close_remaining) if close_remaining else None;pairs.append(pair)
    windows={};strata=[]
    def segment_summary(ss):
        weights=[r['dt_s'] for r in ss]
        return dict(n=len(ss),foot_time_s=sum(weights),
            metrics={name:{ax:weighted_stats([r[name+'_'+ax+'_mps'] for r in ss],weights) for ax in 'xyz'} for name in ['fd_minus_speed','fd_minus_avg_speed','v_foot_speed','v_foot_fd','cv_speed','cv_fd','sdk_velocity']},
            fd_speed_correlations={ax:correlation([r['foot_fd_'+ax+'_mps'] for r in ss],[r['foot_speed_'+ax+'_mps'] for r in ss]) for ax in 'xyz'},
            fd_speed_same_sign_fraction={ax:float(np.mean([r['foot_fd_'+ax+'_mps']*r['foot_speed_'+ax+'_mps']>0 for r in ss])) for ax in 'xyz'})
    for label in ['FULL','GAP']:
        pp=[r for r in pairs if label=='FULL' or r['inside_main_gap']=='True'];ff=[r for r in perfoot if label=='FULL' or r['inside_main_gap']=='True'];ss=[r for r in segments if label=='FULL' or r['inside_main_gap']=='True']
        metrics={name:{ax:stats([r[name+'_'+ax+'_m'] for r in pp]) for ax in 'xyz'} for name in ['endpoint_common','speed_integral_common','fd_integral_common','speed_integral_minus_endpoint','fd_integral_minus_endpoint']}
        footmetrics={name:{ax:stats([r[name+'_'+ax+'_m'] for r in ff]) for ax in 'xyz'} for name in ['q_integral_minus_r_delta','q_avg_integral_minus_r_delta']}
        features=['force_mean_sdk_units','minimum_force_margin_sdk_units','start_age_min_s','start_age_mean_s','start_phase_mean','end_phase_mean','end_remaining_min_s']
        corrs={feat:correlation([r[feat] for r in pp if r[feat] is not None],[r['endpoint_common_x_m']/r['dt_s'] for r in pp if r[feat] is not None]) for feat in features}
        windows[label]=dict(intervals=len(pp),foot_intervals=len(ff),segments=segment_summary(ss),pair_metrics=metrics,foot_metrics=footmetrics,
            feature_correlations_to_endpoint_common_x_rate=corrs,
            feature_stats={feat:stats([r[feat] for r in pp if r[feat] is not None]) for feat in features},
            endpoint_delta_and_speed_integral_correlations={ax:correlation([r['r_delta_'+ax+'_m'] for r in ff],[r['q_integral_'+ax+'_m'] for r in ff]) for ax in 'xyz'})
        def segstr(feature,name,sub,lower=None,upper=None):
            if not sub:return
            ww=np.array([r['dt_s'] for r in sub]);d=dict(window=label,level='source_foot_segment',feature=feature,stratum=name,lower=lower,upper=upper,n=len(sub),foot_time_s=float(ww.sum()))
            for name in ['cv_speed','cv_fd','fd_minus_speed','fd_minus_avg_speed']:
                for ax in 'xyz':d[name+'_'+ax+'_time_mean_mps']=float(np.average([r[name+'_'+ax+'_mps'] for r in sub],weights=ww))
            d['force_mean_sdk_units']=float(np.average([r['force'] for r in sub],weights=ww));strata.append(d)
        for feat in ['interval_phase','stance_phase']:
            for l,h in zip([0,.25,.5,.75],[.25,.5,.75,1]):segstr(feat,str(l)+'_'+str(h),[r for r in ss if r[feat] is not None and l<=r[feat]<(h if h<1 else 1.00001)],l,h)
        for feat in features:
            finite=[r for r in pp if r[feat] is not None];edges=np.quantile([r[feat] for r in finite],[0,.25,.5,.75,1])
            for j in range(4):
                sub=[r for r in finite if edges[j]<=r[feat] and (r[feat]<=edges[j+1] if j==3 else r[feat]<edges[j+1])]
                if not sub:continue
                row=dict(window=label,level='pair_interval',feature=feat,stratum='Q'+str(j+1),lower=float(edges[j]),upper=float(edges[j+1]),n=len(sub))
                for ax in 'xyz':row['endpoint_common_'+ax+'_mean_m']=float(np.mean([r['endpoint_common_'+ax+'_m'] for r in sub]))
                strata.append(row)
        for foot in FEET:segstr('foot',foot,[r for r in ss if r['foot']==foot])
    table(out/'PAIR_INTERVALS.csv',pairs);table(out/'FOOT_INTERVALS.csv',perfoot);table(out/'SOURCE_SEGMENTS.csv',segments);table(out/'STRATA.csv',strata)
    table(out/'SUPPORT_EPISODES.csv',[dict(token=k,**v) for k,v in episodes.items()])
    result=dict(status='COMPLETE',windows=windows,source_endpoint_cache_max_abs_m=endpoint_cache_max,
        used_foot_interval_continuity_failures=continuity_fail,old_cache_eligible_mismatch_after_first_used_START=eligible_mismatch,
        old_cache_transition_mismatch_after_first_used_START=transition_mismatch,
        finite_difference_uses_next_source_for_offline_diagnosis=True,new_online_gate=False,
        raw_reads=0,NAV_reads=0,reference_reads=0,native_calls=0,wall_s=time.monotonic()-begun)
    emit(out/'SUMMARY.json',result)
    print(json.dumps(dict(status=result['status'],windows={k:dict(intervals=z['intervals'],endpoint_common_mean_m={ax:z['pair_metrics']['endpoint_common'][ax]['mean'] for ax in 'xyz'},speed_common_mean_m={ax:z['pair_metrics']['speed_integral_common'][ax]['mean'] for ax in 'xyz'},fd_common_mean_m={ax:z['pair_metrics']['fd_integral_common'][ax]['mean'] for ax in 'xyz'}) for k,z in windows.items()},endpoint_cache_error=endpoint_cache_max,continuity_fail=continuity_fail,eligibility_mismatch=eligible_mismatch,transition_mismatch=transition_mismatch,wall_s=result['wall_s']),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['cache','consistency','provider','old-gyro-cache','output']:p.add_argument('--'+k,required=True)
    run(p.parse_args())
