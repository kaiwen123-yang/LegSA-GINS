#!/usr/bin/env python3
"""Source-only stance/swing foot-speed semantics; no alignment fit or calibration."""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
from nmb1_support_sdk_consistency import emit,sha,table,stats,correlation
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from legsa_gins.paper_rebuild.carrier_phase.support_arcs import SupportArcTracker,SupportPolicy,FootForceThreshold
FEET=['FR','FL','RR','RL']


def wstats(x,w):
    return dict(n=len(x),foot_time_s=float(w.sum()),mean=float(np.average(x,weights=w)),rms=float(np.sqrt(np.average(x*x,weights=w))),
        median=float(np.median(x)),abs_p95=float(np.quantile(abs(x),.95)),integral=float(np.dot(x,w)))


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False);cache=Path(args.cache);man=Path(args.manifest)
    meta=json.loads(man.read_text());fp=meta['frozen'];lo,hi=meta['native_window'];gap=max(meta['longest_position_intervals'],key=lambda x:x['duration_s']);glo,ghi=gap['t0_s'],gap['t1_s']
    with np.load(cache) as z:
        ns=z['native_ns'].copy();q=z['foot_speed_body_frd'].copy();r=z['foot_position_body_frd'].copy();w=z['gyro_frd'].copy();v=z['velocity_frd'].copy();f=z['foot_force'].copy()
    t=ns/1e9;dt=np.diff(ns)/1e9;fd=np.diff(r,axis=0)/dt[:,None,None];avgq=(q[:-1]+q[1:])/2
    policy=SupportPolicy(tuple(FootForceThreshold(k,on,off) for k,on,off in zip(FEET,fp['force_on'],fp['force_off'])),fp['dwell_s'],fp['source_max_age_ns']/1e9)
    tr=SupportArcTracker(policy,stream_id='SOURCE_SEMANTICS');state=np.zeros((len(ns),4),dtype=int);tokens=np.zeros_like(state);tm={}
    for k,t0 in enumerate(t):
        s=tr.update(float(t0),dict(zip(FEET,map(float,f[k]))),available_time_s=float(t0))
        for j,foot in enumerate(s.feet):
            state[k,j]=2 if foot.eligible else (1 if foot.state=='SWING' else 0)
            if foot.token:tokens[k,j]=tm.setdefault(foot.token,len(tm)+1)
    stance=(state[:-1]==2)&(state[1:]==2)&(tokens[:-1]==tokens[1:]);swing=(state[:-1]==1)&(state[1:]==1);transition=~(stance|swing)
    rot=np.cross(w[:-1,None,:],r[:-1]);vfq=-q[:-1]-rot;vffd=-fd-rot;contactq=v[:,None,:][:-1]+rot+q[:-1]
    weights=np.broadcast_to(dt[:,None],stance.shape)
    emit(out/'PLAN.json',dict(script_sha256=sha(__file__),cache=dict(path=str(cache),sha256=sha(cache)),manifest=dict(path=str(man),sha256=sha(man)),
        states='confirmed frozen STANCE continuous token / confirmed SWING at both segment endpoints / all other transitions kept',
        relation='q is tested against (r_next-r)/dt and q+gyro_cross_r+SDK_velocity; q not presumed independent or accurate',
        raw_reads=0,NAV_reads=0,reference_reads=0,native_calls=0,time_scan=False,calibration_fit=False,changes_adopted=False))
    summaries={};counts=[]
    for name,a,b in [('FULL',lo,hi),('GAP',glo,ghi)]:
        active=(t[:-1]>=a)&(t[1:]<=b);groups={}
        for st,mask0 in [('ALL',np.ones_like(stance)),('STANCE',stance),('SWING',swing),('TRANSITION',transition)]:
            mask=mask0&active[:,None];wt=weights[mask]
            z=dict(source_foot_segments=int(mask.sum()),foot_time_s=float(wt.sum()),axes={})
            for j,ax in enumerate('xyz'):
                dq=fd[:,:,j][mask];qq=q[:-1,:,j][mask];aa=avgq[:,:,j][mask]
                z['axes'][ax]=dict(fd=wstats(dq,wt),q=wstats(qq,wt),fd_minus_q=wstats(dq-qq,wt),fd_minus_avgq=wstats(dq-aa,wt),
                    fd_q_correlation=correlation(dq,qq),same_sign_fraction=float(np.mean(dq*qq>0)),
                    q_to_fd_rms_ratio=float(np.sqrt(np.average(qq*qq,weights=wt)/np.average(dq*dq,weights=wt))),
                    foot_velocity_from_q_minus_sdk=wstats((vfq[:,:,j]-v[:-1,None,j])[mask],wt),
                    foot_velocity_from_fd_minus_sdk=wstats((vffd[:,:,j]-v[:-1,None,j])[mask],wt))
            norms=np.linalg.norm(contactq,axis=2)[mask]
            z['literal_q_equals_minus_sdk_minus_omega_cross_r_check']=dict(residual_norm_mps=stats(norms),exact_zero_count=int(np.count_nonzero(norms==0)),
                description='nonzero rejects literal sample identity; does not establish source independence')
            groups[st]=z
            for j,foot in enumerate(FEET):
                m=mask[:,j];ww=dt[m]
                row=dict(window=name,state=st,foot=foot,n=int(m.sum()),time_s=float(ww.sum()))
                for l,ax in enumerate('xyz'):
                    row['integral_q_minus_delta_r_'+ax+'_m']=float(np.dot(q[:-1,j,l][m]-fd[:,j,l][m],ww))
                    row['fd_q_correlation_'+ax]=correlation(fd[:,j,l][m],q[:-1,j,l][m])
                counts.append(row)
        # Equal mean of simultaneously eligible feet is a diagnostic identity
        # probe, not a new velocity estimator or adopted weighing rule.
        kk=active&(stance.sum(axis=1)>=2);meanvf=np.sum(vfq*stance[:,:,None],axis=1)/np.maximum(stance.sum(axis=1),1)[:,None]
        e=meanvf[kk]-v[:-1][kk]
        groups['simultaneous_stance_mean_vs_SDK']=dict(n=int(kk.sum()),duration_s=float(dt[kk].sum()),norm_mps=stats(np.linalg.norm(e,axis=1)),
            axes_mps={ax:wstats(e[:,j],dt[kk]) for j,ax in enumerate('xyz')},
            independence='source sharing cannot be resolved from numeric disagreement or agreement')
        summaries[name]=groups
    table(out/'STATE_FOOT_CLOSURE.csv',counts)
    emit(out/'SUMMARY.json',dict(status='COMPLETE',windows=summaries,raw_reads=0,NAV_reads=0,reference_reads=0,native_calls=0,new_gates=0))
    print(json.dumps({n:{st:dict(n=z['source_foot_segments'],fd_minus_q_mean_mps={ax:a['fd_minus_q']['mean'] for ax,a in z['axes'].items()},correlation={ax:a['fd_q_correlation'] for ax,a in z['axes'].items()},literal_identity_norm_median=z['literal_q_equals_minus_sdk_minus_omega_cross_r_check']['residual_norm_mps']['median']) for st,z in gg.items() if 'axes' in z} for n,gg in summaries.items()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['cache','manifest','output']:p.add_argument('--'+k,required=True)
    run(p.parse_args())
