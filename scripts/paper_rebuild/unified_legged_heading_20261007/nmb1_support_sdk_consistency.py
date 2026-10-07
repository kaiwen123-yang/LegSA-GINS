#!/usr/bin/env python3
"""Signed support-foot / SDK displacement consistency from saved source providers.
No NAV, GNSS, evaluation reference, raw scan, fit, rejection rule or native call.
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, sys, time
from collections import Counter
import numpy as np
from scipy.spatial.transform import Rotation
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/paper_rebuild/carrier_phase'))
from continuous_body_motion import rotation_exp


def emit(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table(path, rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rows)


def stats(values):
    a=np.asarray(values,float)
    if not len(a): return {'n':0}
    return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),
        p05=float(np.quantile(a,.05)),p95=float(np.quantile(a,.95)),
        abs_median=float(np.median(abs(a))),abs_p95=float(np.quantile(abs(a),.95)),
        min=float(a.min()),max=float(a.max()),sum=float(a.sum()),
        positive_fraction=float(np.mean(a>0)),rms=float(np.sqrt(np.mean(a*a))))


def correlation(a,b):
    a,b=np.asarray(a),np.asarray(b)
    if len(a)<2 or np.std(a)==0 or np.std(b)==0:return None
    return float(np.corrcoef(a,b)[0,1])


def vector(row, name):
    return np.array([float(row[name+'_'+axis+'_m']) for axis in 'xyz'])


def addvec(row,name,value,unit='m'):
    row.update({name+'_'+axis+'_'+unit:float(x) for axis,x in zip('xyz',value)})


def run(args):
    begun=time.monotonic();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    provider=Path(args.provider);sdkfile=Path(args.sdk_provider);cache=Path(args.body_cache)
    events=list(csv.DictReader((provider/'SUPPORT_POSE_EVENTS.csv').open()))
    ident={(r['clone_id'],r['event_type']):int(r['native_stamp_ns']) for r in csv.DictReader((provider/'ENDPOINT_RAW_IDENTITY.csv').open())}
    meta=json.loads((provider/'MANIFEST.json').read_text())
    sdk=np.genfromtxt(sdkfile,delimiter=',',names=True)
    vns=np.rint(sdk['time']*1e9).astype(np.int64)
    vel=np.column_stack((sdk['v_forward_mps'],sdk['v_right_mps'],np.zeros(len(sdk))))
    with np.load(cache) as z:
        gns=np.rint(z['times']*1e9).astype(np.int64); gyro=z['gyro_frd'].copy()
    inputpins={str(p):sha(p) for p in [provider/'SUPPORT_POSE_EVENTS.csv',provider/'ENDPOINT_RAW_IDENTITY.csv',provider/'MANIFEST.json',sdkfile,cache]}
    full_cache_checks={}
    mode='SDK_XY_PROVIDER_WITH_Z_ZERO_DIAGNOSTIC'
    if args.full_motion_cache:
        full=Path(args.full_motion_cache);inputpins[str(full)]=sha(full)
        with np.load(full) as z:
            fn=z['native_ns'].copy();fw=z['gyro_frd'].copy();fv=z['velocity_frd'].copy()
        pos=np.searchsorted(fn,vns)
        same=(pos<len(fn)) & (fn[np.minimum(pos,len(fn)-1)]==vns)
        if not same.all():raise ValueError('Full cache missing SDK provider exact timestamps')
        full_cache_checks['SDK_XY_provider_max_abs_mps']=float(abs(fv[pos,:2]-vel[:,:2]).max())
        if full_cache_checks['SDK_XY_provider_max_abs_mps']>1e-12:raise ValueError('Full cache / SDK provider XY differs')
        pos=np.searchsorted(fn,gns); same=(pos<len(fn)) & (fn[np.minimum(pos,len(fn)-1)]==gns)
        full_cache_checks['original_gyro_exact_timestamp_matches']=int(same.sum())
        full_cache_checks['original_gyro_rows']=len(gns)
        full_cache_checks['original_gyro_max_abs_rad_s']=float(abs(fw[pos[same]]-gyro[same]).max())
        if full_cache_checks['original_gyro_max_abs_rad_s']>1e-12:raise ValueError('Full cache / original gyro differs')
        # Integer native ns already contain the inherited -1.1 s mapping.
        gns=fn;vns=fn;gyro=fw;vel=fv;mode='FULL_SAVED_SDK_XYZ_INHERITED_BODY_FRD_HYPOTHESIS'
    window=meta['native_window'];gap=max(meta['longest_position_intervals'],key=lambda x:x['duration_s'])
    gaplo,gaphi=gap['t0_s'],gap['t1_s']
    plan=dict(schema='support_sdk_signed_consistency.v1',input_pins=inputpins,script_sha256=sha(__file__),
        native_window=window,gap_window=[gaplo,gaphi],mode=mode,full_cache_checks=full_cache_checks,
        body_offset_s=-1.1,offset_applied_again=False,point_sigma_m=.01,lever_body_frd_m=[0,0,0],
        model='D01 maps body1 into body0; y_i=r_i0-D01*r_i1; u=integral D0t*v_sdk(t)dt; c_i=y_i-u; common=(c_i+c_j)/2; differential=c_i-c_j',
        integration='causal left-source zero-order hold on union of source timestamps; D right-multiplies exp(gyro*dt)',
        coordinate_claim='inherited SDK body-FRD velocity hypothesis, not independently calibrated',
        velocity_is_truth=False,point_independence_calibrated=False,raw_reads=0,native_calls=0,reference_reads=0,NAV_reads=0,
        additional_gates=0,parameter_fits=0,source_max_gap_s=.05,
        selection='every existing END, including unavailable intervals in denominator; no endpoint or foot reselection',
        fixed_anchor='gyro-only rotation into first available START body frame of each reported window; not NED or truth',
        cumulative='sum only observed nonoverlapping END intervals, not extrapolation over unobserved periods')
    emit(out/'PLAN.json',plan)
    # Prefix rotations allow descriptive signed accumulation into one fixed frame.
    # Exact source NS and recorded gyro only, with no gravity/RP or NAV feedback.
    exp=Rotation.from_rotvec(gyro[:-1]*((gns[1:]-gns[:-1])/1e9)[:,None]).as_matrix()
    prefix=np.empty((len(gns),3,3));prefix[0]=np.eye(3)
    for k in range(len(exp)):prefix[k+1]=prefix[k]@exp[k]
    def orientation(ns):
        k=int(np.searchsorted(gns,ns,side='right')-1)
        return prefix[k]@rotation_exp(gyro[k]*((ns-gns[k])/1e9))
    starts={};rows=[];R0s={};max_algebra=0.
    for e in events:
        if e['event_type']=='START': starts[e['clone_id']]=e;continue
        if e['event_type']!='END':continue
        a=starts[e['clone_id']];n0=ident[(e['clone_id'],'START')];n1=ident[(e['clone_id'],'END')]
        dt=(n1-n0)/1e9;t0=n0/1e9;t1=n1/1e9
        row=dict(clone_id=e['clone_id'],t0_s=t0,t1_s=t1,dt_s=dt,foot_i=e['foot_i'],foot_j=e['foot_j'],
            episode_i=e['episode_i'],episode_j=e['episode_j'],pair=e['foot_i']+'-'+e['foot_j'],
            inside_main_gap=bool(t0>=gaplo and t1<=gaphi),status='UNAVAILABLE')
        rows.append(row)
        if n0<max(gns[0],vns[0]) or n1>min(gns[-1],vns[-1]):
            row['reason']='SAVED_SOURCE_COVERAGE_MISSING';continue
        knots=np.unique(np.concatenate(([n0,n1],gns[(gns>n0)&(gns<n1)],vns[(vns>n0)&(vns<n1)])))
        kg=np.searchsorted(gns,knots[:-1],side='right')-1;kv=np.searchsorted(vns,knots[:-1],side='right')-1
        if max(np.max(knots[1:]-gns[kg]),np.max(knots[1:]-vns[kv]))>50_000_000:
            row['reason']='INHERITED_SOURCE_MAX_AGE_EXCEEDED';continue
        f0=np.array([[float(a['r_'+p+'_body_frd_'+axis+'_m']) for axis in 'xyz'] for p in ['i','j']])
        f1=np.array([[float(e['r_'+p+'_body_frd_'+axis+'_m']) for axis in 'xyz'] for p in ['i','j']])
        D=np.eye(3);u=np.zeros(3);u_xy0=np.zeros(3);Jz=np.zeros(3);leakage_bound_s=0.;speed=0.;abs_speed=0.
        for h,g,v in zip(np.diff(knots)/1e9,kg,kv):
            u+=D@vel[v]*h;u_xy0+=D@np.r_[vel[v,:2],0.]*h
            Jz+=D[:,2]*h;leakage_bound_s+=np.linalg.norm(D[:2,2])*h
            speed+=np.linalg.norm(vel[v,:2])*h;abs_speed+=np.linalg.norm(vel[v])*h
            D=D@rotation_exp(gyro[g]*h)
        yy=f0-f1@D.T;cc=yy-u;common=cc.mean(axis=0);diff=cc[0]-cc[1]
        max_algebra=max(max_algebra,float(abs(diff-((f0[0]-f0[1])-D@(f1[0]-f1[1]))).max()))
        rv=Rotation.from_matrix(D).as_rotvec()*180/np.pi
        row.update(status='AVAILABLE_WORKING_SOURCE_CONFLICT',reason='NO_GATE',source_segments=len(knots)-1,
            rotation_angle_deg=float(np.linalg.norm(rv)),rotation_x_deg=float(rv[0]),rotation_y_deg=float(rv[1]),rotation_z_deg=float(rv[2]),
            sdk_speed_xy_mps=float(speed/dt),sdk_speed_xyz_mps=float(abs_speed/dt),
            common_horizontal_m=float(np.linalg.norm(common[:2])),differential_norm_m=float(np.linalg.norm(diff)),
            common_horizontal_velocity_equivalent_mps=float(np.linalg.norm(common[:2])/dt),
            foot_i_j_horizontal_cosine=float(np.dot(cc[0,:2],cc[1,:2])/(np.linalg.norm(cc[0,:2])*np.linalg.norm(cc[1,:2]))) if np.linalg.norm(cc[0,:2])*np.linalg.norm(cc[1,:2]) else 0.,
            omitted_z_horizontal_leakage_bound_s=float(leakage_bound_s),
            omitted_z_horizontal_displacement_m=float(np.linalg.norm((u-u_xy0)[:2])))
        for key,value in [('y_i',yy[0]),('y_j',yy[1]),('u_sdk',u),('u_sdk_z0',u_xy0),('common',common),('differential',diff),('c_i',cc[0]),('c_j',cc[1])]:addvec(row,key,value)
        addvec(row,'unit_constant_body_z_sensitivity',Jz,'s')
        R0s[e['clone_id']]=orientation(n0)
    available=[r for r in rows if r['status']=='AVAILABLE_WORKING_SOURCE_CONFLICT']
    groups=[];feetout=[];cumulative=[];windowout={}
    def summarize(rr):
        if not rr:return {'n':0}
        dts=np.array([r['dt_s'] for r in rr]);C=np.array([vector(r,'common') for r in rr]);
        DI=np.array([vector(r,'differential') for r in rr]);CI=np.array([vector(r,'c_i') for r in rr]);CJ=np.array([vector(r,'c_j') for r in rr]);
        return dict(n=len(rr),covered_duration_s=float(dts.sum()),
            common_axes_m={ax:stats(C[:,k]) for k,ax in enumerate('xyz')},
            foot_common_displacement_axes_m={ax:stats([(vector(r,'y_i')[k]+vector(r,'y_j')[k])/2 for r in rr]) for k,ax in enumerate('xyz')},
            u_sdk_axes_m={ax:stats([vector(r,'u_sdk')[k] for r in rr]) for k,ax in enumerate('xyz')},
            differential_axes_m={ax:stats(DI[:,k]) for k,ax in enumerate('xyz')},
            equivalent_signed_velocity_mps={ax:float(C[:,k].sum()/dts.sum()) for k,ax in enumerate('xyz')},
            common_horizontal_m=stats([r['common_horizontal_m'] for r in rr]),
            differential_norm_m=stats([r['differential_norm_m'] for r in rr]),
            foot_i_j_horizontal_cosine=stats([r['foot_i_j_horizontal_cosine'] for r in rr]),
            foot_i_j_axis_correlations={ax:correlation(CI[:,k],CJ[:,k]) for k,ax in enumerate('xyz')},
            foot_i_j_same_sign_fractions={ax:float(np.mean(CI[:,k]*CJ[:,k]>0)) for k,ax in enumerate('xyz')},
            feature_correlations={feature:{ax:correlation([r[feature] for r in rr],C[:,k]/dts) for k,ax in enumerate('xyz')} for feature in ['rotation_angle_deg','rotation_x_deg','rotation_y_deg','rotation_z_deg','sdk_speed_xy_mps']},
            u_sdk_and_y_mean_axis_correlations={ax:correlation([vector(r,'u_sdk')[k] for r in rr],[(vector(r,'y_i')[k]+vector(r,'y_j')[k])/2 for r in rr]) for k,ax in enumerate('xyz')},
            omitted_z_horizontal_displacement_m=stats([r['omitted_z_horizontal_displacement_m'] for r in rr]))
    for label,lo,hi in [('FULL',window[0],window[1]),('GAP',gaplo,gaphi)]:
        allr=[r for r in rows if r['t0_s']>=lo and r['t1_s']<=hi];rr=[r for r in allr if r['status']=='AVAILABLE_WORKING_SOURCE_CONFLICT']
        w=summarize(rr);w.update(total_END_denominator=len(allr),unavailable=len(allr)-len(rr),unavailable_reason_counts=dict(Counter(r.get('reason') for r in allr if r not in rr)))
        anchor=R0s[rr[0]['clone_id']];run=np.zeros(3);runbody=np.zeros(3);total=0.;previous_end=-float('inf')
        for r in rr:
            if r['t0_s']<previous_end:raise ValueError('END intervals overlap; cannot sum displacements')
            previous_end=r['t1_s'];inc=anchor.T@R0s[r['clone_id']]@vector(r,'common');run+=inc;runbody+=vector(r,'common');total+=r['dt_s']
            cr=dict(window=label,t1_s=r['t1_s'],clone_id=r['clone_id'],pair=r['pair'],covered_duration_s=total)
            addvec(cr,'cumulative_fixed_anchor',run);addvec(cr,'cumulative_body_components',runbody);addvec(cr,'fixed_anchor_increment',inc);cumulative.append(cr)
        w['cumulative_fixed_anchor_m']={ax:float(run[k]) for k,ax in enumerate('xyz')}
        w['cumulative_fixed_anchor_horizontal_m']=float(np.linalg.norm(run[:2]));w['fixed_anchor_time_s']=rr[0]['t0_s']
        w['covered_fraction_of_window']=float(total/(hi-lo));windowout[label]=w
        def stratum(feature,name,sub,lower=None,upper=None):
            g=dict(window=label,feature=feature,stratum=name,lower=lower,upper=upper,n=len(sub))
            if sub:
                z=summarize(sub);g['covered_duration_s']=z['covered_duration_s']
                for ax in 'xyz':
                    for metric in ['mean','median','p95','abs_p95','sum']:g['common_'+ax+'_'+metric+'_m']=z['common_axes_m'][ax][metric]
                    g['signed_velocity_'+ax+'_mps']=z['equivalent_signed_velocity_mps'][ax]
                g['differential_norm_median_m']=z['differential_norm_m']['median'];g['foot_i_j_cosine_median']=z['foot_i_j_horizontal_cosine']['median']
            groups.append(g)
        for pair in sorted(set(r['pair'] for r in rr)):stratum('pair',pair,[r for r in rr if r['pair']==pair])
        for feature in ['rotation_angle_deg','sdk_speed_xy_mps']:
            edges=np.quantile([r[feature] for r in rr],[0,.25,.5,.75,1])
            for j in range(4):stratum(feature,'Q'+str(j+1),[r for r in rr if edges[j]<=r[feature] and (r[feature]<=edges[j+1] if j==3 else r[feature]<edges[j+1])],float(edges[j]),float(edges[j+1]))
        for sign in [-1,0,1]:stratum('rotation_z_sign',str(sign),[r for r in rr if np.sign(r['rotation_z_deg'])==sign])
        for j in range(4):
            l=lo+(hi-lo)*j/4;h=lo+(hi-lo)*(j+1)/4
            stratum('time_quarter','Q'+str(j+1),[r for r in rr if l<=r['t1_s'] and (r['t1_s']<=h if j==3 else r['t1_s']<h)],l,h)
        for foot in ['FR','FL','RR','RL']:
            ff=[(r,p) for r in rr for p in ['i','j'] if r['foot_'+p]==foot]
            fo=dict(window=label,foot=foot,n=len(ff),covered_duration_s=sum(r['dt_s'] for r,p in ff))
            for k,ax in enumerate('xyz'):
                v=[vector(r,'c_'+p)[k] for r,p in ff]
                if v:
                    for key,val in stats(v).items():fo['c_'+ax+'_'+key+'_m']=val
                    fo['signed_velocity_'+ax+'_mps']=sum(v)/fo['covered_duration_s']
            feetout.append(fo)
    table(out/'INTERVALS.csv',rows);table(out/'DESCRIPTIVE_STRATA.csv',groups);table(out/'FOOT_SPECIFIC.csv',feetout);table(out/'CUMULATIVE.csv',cumulative)
    summary=dict(status='COMPLETE',mode=mode,counts=dict(Counter(r['status'] for r in rows)),windows=windowout,
        lifecycle=dict(Counter(r['event_type'] for r in events)),source_full_cache_checks=full_cache_checks,
        common_differential_algebra_max_abs_m=max_algebra,new_rejections=0,raw_reads=0,NAV_reads=0,reference_reads=0,native_calls=0,
        wall_seconds=time.monotonic()-begun)
    emit(out/'SUMMARY.json',summary)
    print(json.dumps(dict(status=summary['status'],counts=summary['counts'],windows={k:dict(n=v['n'],total_END_denominator=v['total_END_denominator'],common_means_m={a:s['mean'] for a,s in v['common_axes_m'].items()},signed_velocity_mps=v['equivalent_signed_velocity_mps'],cumulative_fixed_anchor_m=v['cumulative_fixed_anchor_m']) for k,v in windowout.items()},wall_seconds=summary['wall_seconds']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['provider','sdk-provider','body-cache','output']:p.add_argument('--'+k,required=True)
    p.add_argument('--full-motion-cache');run(p.parse_args())
