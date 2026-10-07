#!/usr/bin/env python3
"""Audit saved baseline3D LSIM consumption and final NMB1 partial supply.
Reads existing providers/diagnostics only; no raw, NAV, reference or estimator.
"""
from pathlib import Path
from collections import Counter
import argparse, csv, gzip, hashlib, json, math, time
import numpy as np

O = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(p):
    with p.open() as f:
        return list(csv.DictReader(f))


def jsonwrite(p, v):
    p.write_text(json.dumps(v, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def csvwrite(p, rr):
    fields=list(dict.fromkeys(k for r in rr for k in r))
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rr)


def stats(a):
    x=np.asarray(a,float)
    return dict(n=len(x),min=float(x.min()),median=float(np.median(x)),
                p95=float(np.quantile(x,.95)),max=float(x.max()))


def key(t):
    return round(float(t), 6)


def bucket(deg):
    return 6 if deg>30 else 2 if deg>15 else 1


def geometry(h,R):
    j=np.array([-h[1],h[0],0.])
    hh=float(h[0]**2+h[1]**2)
    g=j/hh
    return dict(metadata_proxy_deg=math.sqrt(R[0,0])/.35*180/math.pi,
        azimuth_delta_deg=math.sqrt(g@R@g)*180/math.pi,
        yaw_fixed_others_deg=1/math.sqrt(j@np.linalg.solve(R,j))*180/math.pi,
        horizontal_projection_m=math.sqrt(hh)),j,g


def run(args):
    begun=time.monotonic();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    B=Path(args.continuous_root);U=Path(args.unified_root)
    pins={}
    def read(p):
        pins[str(p)]=sha(p)
        return rows(p)
    allrows=[];counts=[];counterexamples=[]
    stages=[(s,s,B/'NAVIGATION_PARTIAL_FULL_WINDOW_01/NATIVE'/(s+'__MOTION')) for s in ['BY2','BY2H','BY2O']]
    stages.append(('BY2O_FOOT','BY2O',U/'SUPPORT_POSE_NATIVE_BY2O_01/NATIVE/BY2O__REPLACE_SUPPORT'))
    for label,seq,stage in stages:
        full=read(B/'PARTIAL_FULL_WINDOW_01'/seq/'FULL.csv')
        rolling=read(B/'PARTIAL_FULL_WINDOW_01'/seq/'MOTION.csv')
        fmap={key(r['measurement_time']):r for r in full}
        partial={key(r['measurement_time']) for r in rolling if r['valid']=='1' and fmap[key(r['measurement_time'])]['valid']=='0'}
        diag=read(stage/'BASELINE3D_DIAGNOSTICS.csv')
        sa=read(stage/'SOURCE_AWARE_WEIGHT_TRACE.csv')
        samap={key(r['time']):r for r in sa if r['source_id']=='dual_antenna_yaw'}
        attempted=[r for r in diag if r['attempt']=='1']
        for kind in ['FULL','PARTIAL']:
            aa=[r for r in attempted if (key(r['time']) in partial)==(kind=='PARTIAL')]
            accepted=[r for r in aa if r['accepted']=='1']
            ss=[samap[key(r['time'])] for r in accepted]
            count=dict(stage=label,kind=kind,attempted=len(aa),accepted=len(accepted),
                rejected=len(aa)-len(accepted),LSIM_1=sum(float(r['lsim_R_scale'])==1 for r in ss),
                LSIM_2=sum(float(r['lsim_R_scale'])==2 for r in ss),
                LSIM_6=sum(float(r['lsim_R_scale'])==6 for r in ss),
                LSIM_other=sum(float(r['lsim_R_scale']) not in [1,2,6] for r in ss),
                reason_counts_json=json.dumps(dict(Counter(r['reason_codes'] for r in ss)),sort_keys=True))
            counts.append(count)
            for d in accepted:
                t=float(d['time']);s=samap[key(t)]
                h=np.array([float(d['h_'+a+'_m']) for a in 'ned'])
                R=np.array([[float(d['R_'+a+b]) for b in 'ned'] for a in 'ned'])
                v,j,g=geometry(h,R);vrot,_,_=geometry(O@h,O@R@O.T)
                eig,V=np.linalg.eigh(R)
                r=dict(stage=label,kind=kind,time_s=t,accepted=True,
                    sa_combined_R_scale=float(s['combined_R_scale']),LSIM_R_scale=float(s['lsim_R_scale']),
                    OIM_R_scale=float(s['oim_R_scale']),qa_R_scale=float(d['qa_R_scale']),
                    hard_nis=float(d['nis_actual_innovation']),reason_codes=s['reason_codes'],
                    old_std_bucket=bucket(v['metadata_proxy_deg']),
                    rotated_std_bucket=bucket(vrot['metadata_proxy_deg']),
                    rotation_bucket_changed=bucket(v['metadata_proxy_deg'])!=bucket(vrot['metadata_proxy_deg']),
                    azimuth_bucket_descriptive_only=bucket(v['azimuth_delta_deg']),
                    fixed_others_bucket_descriptive_only=bucket(v['yaw_fixed_others_deg']),
                    rotated_proxy_deg=vrot['metadata_proxy_deg'],
                    rotated_azimuth_delta_deg=vrot['azimuth_delta_deg'],
                    rotated_yaw_fixed_others_deg=vrot['yaw_fixed_others_deg'],
                    covariance_condition=float(eig[-1]/eig[0]),**v)
                for a,x in zip('ned',h):r['h_'+a+'_m']=float(x)
                for i,a in enumerate('ned'):
                    for k,b in enumerate('ned'):r['R_'+a+b+'_m2']=float(R[i,k])
                contributions=dict(Rnn=eig*V[0,:]**2,
                    azimuth_variance=eig*(V.T@g)**2,
                    yaw_fixed_information=(V.T@j)**2/eig)
                for i,x in enumerate(eig):
                    r['covariance_eigen'+str(i)+'_m2']=float(x)
                    for name,a in contributions.items():r[name+'_eigen'+str(i)]=float(a[i])
                allrows.append(r)
                if label!='BY2O_FOOT' and kind=='PARTIAL' and r['rotation_bucket_changed']:
                    counterexamples.append(r)
    primary=[r for r in allrows if r['stage']!='BY2O_FOOT']
    pp=[r for r in primary if r['kind']=='PARTIAL']
    ff=[r for r in primary if r['kind']=='FULL']
    assert len(pp)==302 and len(ff)==638 and len(counterexamples)==23

    base=B/'TRANSFER_FINAL_PARTIAL_01/NMB1'
    slots=read(base/'SLOTS.csv')
    ids={int(r['index']) for r in slots if r['rolling_partial_added']=='True'}
    rawp=base/'PROVIDER_DETAILS.jsonl.gz';pins[str(rawp)]=sha(rawp)
    with gzip.open(rawp,'rt') as f:
        details=[json.loads(s) for s in f]
    details=[d for d in details if d['index'] in ids and d['policy']=='rolling']
    native=U/'SUPPORT_SDK_JOINT_NMB1_01/NATIVE/NMB1__REPLACE_SUPPORT_XYZ/HEADING_SOURCE_EVENTS.csv'
    ev={key(r['time']):r for r in read(native)}
    gnssp=Path(args.gnss18);pins[str(gnssp)]=sha(gnssp);gnss=np.loadtxt(gnssp)
    actual={key(r['measurement_time']):r for r in read(B/'NAVIGATION_NMB1_01/PROVIDERS/NMB1/CARRIER.csv')}
    final={key(r['measurement_time']):r for r in read(base/'MOTION.csv')}
    nmb=[]
    for d in details:
        c=d['consumed_likelihood'];e=ev[key(d['time_s'])]
        src=float(e['pvt_source_time']);ix=int(np.searchsorted(gnss[:,0],src))
        assert abs(gnss[ix,0]-src)<1e-7
        eig=np.linalg.eigvalsh(d['raw_covariance_m2'])
        r=dict(index=d['index'],time_s=d['time_s'],source_fingerprint=d['source_fingerprint'],
            common_origins_json=json.dumps(d['common_origins']),status=d['status'],
            shared_integer_count=len(d['qualified_shared_integer_items']),
            shared_integer_items_json=json.dumps(d['qualified_shared_integer_items']),
            retained_rows_json=json.dumps(d['retained_rows']),
            phase_rank=c['partial_quality']['phase_rank'],
            joint_components=c['joint_components'],joint_enclosing_width_deg=c['joint_enclosing_width_deg'],
            directed_components=len(c['directed_components']),
            directed_enclosing_width_deg=c['directed_enclosing_width_deg'],
            joint_cover_json=c['joint_cover_components_json'],
            directed_cover_json=json.dumps(c['directed_components']),
            raw_covariance_eigen0_m2=float(eig[0]),raw_covariance_eigen1_m2=float(eig[1]),raw_covariance_eigen2_m2=float(eig[2]),
            final_partial_provider_valid=final[key(d['time_s'])]['valid'],
            actual_native_provider_valid=actual[key(d['time_s'])]['valid'],
            pvt_source_time=src,pvt_age_s=float(e['pvt_age_s']),pvt_source_valid=e['pvt_source_valid'],
            pvt_yaw_std_deg=float(gnss[ix,14]),pvt_yaw_valid=int(gnss[ix,17]),
            actual_carrier_attempted=e['carrier_attempted'],actual_carrier_reason=e['carrier_reason'],
            final_provider_also_PVT_covered=e['pvt_source_valid']=='1' and float(e['pvt_age_s'])<=.21,
            covariance_cross_with_PVT_available=False,increment_beyond_PVT_identified=False)
        nmb.append(r)
    assert len(nmb)==8 and all(r['final_provider_also_PVT_covered'] for r in nmb)
    summaries={}
    for label in ['BY2','BY2H','BY2O','BY2O_FOOT']:
        rr=[r for r in allrows if r['stage']==label and r['kind']=='PARTIAL']
        summaries[label]=dict(n=len(rr),statistics={k:stats([r[k] for r in rr]) for k in [
            'metadata_proxy_deg','azimuth_delta_deg','yaw_fixed_others_deg','horizontal_projection_m','covariance_condition']},
            rotated_bucket_changed=sum(r['rotation_bucket_changed'] for r in rr),
            LSIM_counts=dict(Counter(r['LSIM_R_scale'] for r in rr)),
            azimuth_buckets_descriptive_only=dict(Counter(r['azimuth_bucket_descriptive_only'] for r in rr)),
            fixed_others_buckets_descriptive_only=dict(Counter(r['fixed_others_bucket_descriptive_only'] for r in rr)))
    summary=dict(status='READ_ONLY_AUDIT_COMPLETE',schema='direction_vector_lsim_audit.v1',
        script_sha256=sha(Path(__file__)),primary_FULL_accepted=len(ff),primary_PARTIAL_accepted=len(pp),
        primary_PARTIAL_LSIM_counts=dict(Counter(r['LSIM_R_scale'] for r in pp)),
        primary_FULL_LSIM_counts=dict(Counter(r['LSIM_R_scale'] for r in ff)),
        primary_PARTIAL_rotation_counterexamples=len(counterexamples),
        all_accepted_samples_retained=True,partition='FULL valid at time versus rolling added; no reference/error selection',
        azimuth_rotation_max_abs_deg=max(abs(r['azimuth_delta_deg']-r['rotated_azimuth_delta_deg']) for r in pp),
        fixed_others_rotation_max_abs_deg=max(abs(r['yaw_fixed_others_deg']-r['rotated_yaw_fixed_others_deg']) for r in pp),
        stage_summaries=summaries,NMB_final_added=8,NMB_final_added_PVT_covered=8,
        NMB_final_added_joint_component_counts=dict(Counter(r['joint_components'] for r in nmb)),
        NMB_final_added_directed_component_counts=dict(Counter(r['directed_components'] for r in nmb)),
        NMB_final_added_actual_attempts=sum(int(r['actual_carrier_attempted']) for r in nmb),
        input_pins=pins,native_calls=0,evaluator_calls=0,raw_reads=0,NAV_reads=0,reference_reads=0,
        counterexample='pure coordinate 90deg N/E rotation hnew=O h,Rnew=O R O^T; preserves both physical local quantities, changes legacy proxy bucket',
        no_replacement_sigma_selected=True,no_PVT_disabled=True,no_independence_assumed=True,
        wall_s=time.monotonic()-begun)
    csvwrite(out/'ACCEPTED_GEOMETRY.csv',allrows)
    csvwrite(out/'STAGE_COUNTS.csv',counts)
    csvwrite(out/'ROTATION_COUNTEREXAMPLES.csv',counterexamples)
    csvwrite(out/'NMB1_FINAL_EIGHT_PARTIAL.csv',nmb)
    jsonwrite(out/'SUMMARY.json',summary)
    jsonwrite(out/'OUTPUT_SEAL.json',dict(files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()},
        script_sha256=summary['script_sha256'],input_pins=pins))
    print(json.dumps({k:summary[k] for k in ['status','primary_FULL_accepted','primary_PARTIAL_accepted',
        'primary_PARTIAL_LSIM_counts','primary_FULL_LSIM_counts','primary_PARTIAL_rotation_counterexamples',
        'NMB_final_added','NMB_final_added_PVT_covered','NMB_final_added_directed_component_counts','wall_s']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for argument_name in ['continuous-root','unified-root','gnss18','output']:
        p.add_argument('--'+argument_name,required=True)
    run(p.parse_args())

