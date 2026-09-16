"""Fail-soft H-EXT raw-only probes. No solver, evaluator, or trace access."""
from __future__ import annotations
import csv
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import yaml
from ..horizontal_literature.shared_raw_backend import reconstruct_ubx_stream, ecef_to_geodetic
from ..horizontal_literature.ext05_provider import (
    _imu_only_messages, ImuSample, euler_rpy_deg_to_matrix, calibrate_static_imu,
    local_normal_gravity_mps2, sha256_file, verify_hash_locked_file,
)
from .sequence_paths import load_sequence_paths, alias_path, CALIBRATED_CONTRACT


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as h:
        json.dump(data,h,ensure_ascii=False,indent=2,allow_nan=False)
        h.write('\n')


def stats(a):
    return {'median':float(np.median(a)), 'p95':float(np.percentile(a,95))} if len(a) else None


def relative_position(a,b,window):
    return 'BEFORE' if b < window[0] else 'AFTER' if a > window[1] else 'WITHIN_OR_OVERLAPPING'


def gaps(times, threshold, seq):
    result=[]
    for i in np.flatnonzero(np.diff(times)>threshold):
        a,b=map(float,times[i:i+2]); ar,br=a-seq.base_time,b-seq.base_time
        result.append({'left_index_zero_based':int(i),'right_index_zero_based':int(i+1),
            'start_absolute_s':a,'end_absolute_s':b,'duration_s':b-a,
            'start_relative_s':ar,'end_relative_s':br,'window_position':relative_position(ar,br,seq.window)})
    return result


def observe_gnss(seq, control_pacc):
    streams=[reconstruct_ubx_stream(p,decode_nav_hpposecef_semantics=True) for p in (seq.gnss1_raw,seq.gnss2_raw)]
    reports=[]; first_times=None; first_positions=None; origin=None
    for receiver,stream in enumerate(streams):
        hp=stream.nav_hpposecef_epochs; rx=stream.rawx_epochs
        keys=[e.itow_ms for e in hp]; rawkeys=[int(round(e.gps_tow_seconds*1000)) for e in rx]
        weeks=sorted({e.gps_week for e in rx});leaps=sorted({e.leap_seconds for e in rx})
        if len(weeks)!=1 or len(leaps)!=1: raise ValueError('Ambiguous week/leap; no timing search')
        times=np.asarray([315964800.0+weeks[0]*604800.0+k*1e-3-leaps[0] for k in keys])
        pa=np.asarray([e.position_accuracy_m for e in hp]);threshold=None if control_pacc is None else 3*control_pacc[receiver]
        index_by_key={k:i for i,k in enumerate(keys)}
        raw_offsets=[keys[index_by_key[k+2]]-k for k in rawkeys if k+2 in index_by_key]
        gp=gaps(times,.20001,seq)
        for g in gp:
            i=g['left_index_zero_based'];g.update(start_itow_ms=keys[i],end_itow_ms=keys[i+1],duration_ms=keys[i+1]-keys[i])
        reports.append({'receiver':receiver+1,'hpposecef_epochs':len(hp),'rawx_epochs':len(rx),
            'unique_itow_count':len(set(keys)),'strictly_monotonic':all(b>a for a,b in zip(keys,keys[1:])),
            'itow_interval_histogram_ms':dict(sorted(Counter(np.diff(keys).tolist()).items())),
            'gaps_gt_200ms':gp,'hpposecef_minus_rawx_offsets_ms':sorted(set(raw_offsets)),
            'rawx_paired_plus_2ms_count':len(raw_offsets),'constant_plus_2ms_all_rawx':len(raw_offsets)==len(rx),
            'leading_hpposecef_without_rawx':len(set(keys)-{k+2 for k in rawkeys}),
            'gps_week_set':weeks,'leap_seconds_set':leaps,'pacc_m':stats(pa),
            'pacc_threshold_3x_BY2_median_m':threshold,
            'pacc_epochs_gt_3x_BY2_median':None if threshold is None else int(np.sum(pa>threshold)),
            'pacc_window_m':stats(pa[(times>=seq.base_time+seq.window[0])&(times<=seq.base_time+seq.window[1])]),
            'first_relative_s':float(times[0]-seq.base_time),'last_relative_s':float(times[-1]-seq.base_time)})
        if receiver==0:
            first_times=times;first_positions=np.asarray([e.position_ecef_m for e in hp]);origin=hp[0].position_ecef_m
    common=set(e.itow_ms for e in streams[0].nav_hpposecef_epochs)&set(e.itow_ms for e in streams[1].nav_hpposecef_epochs)
    result={'status':'OBSERVED','receivers':reports,'common_itow_count':len(common),
        'first_gnss1_minus_t_start_s':reports[0]['first_relative_s']-seq.window[0],
        'same_itow_lists':[e.itow_ms for e in streams[0].nav_hpposecef_epochs]==[e.itow_ms for e in streams[1].nav_hpposecef_epochs]}
    return result,(first_times,first_positions,origin)


def observe_imu(seq, gnss):
    transform=euler_rpy_deg_to_matrix(-1,0,0)@np.diag([1.,-1.,-1.])
    samples=tuple(ImuSample(t,transform@g,transform@a) for t,g,a in _imu_only_messages(seq.go2_body))
    times=np.asarray([s.absolute_time_unix_seconds for s in samples]);dt=np.diff(times)
    gnss_times,positions,origin=gnss;lat,lon,height=ecef_to_geodetic(origin)
    g=local_normal_gravity_mps2(float(np.degrees(lat)),height)
    first=[s for s in samples if s.absolute_time_unix_seconds<=times[0]+5]
    first_times=np.asarray([s.absolute_time_unix_seconds for s in first])
    gm=float(np.median([np.linalg.norm(s.angular_rate_frd_radps) for s in first]));am=float(np.median([np.linalg.norm(s.specific_force_frd_mps2) for s in first]))
    maxgap=float(np.max(np.diff(first_times)));gapbound=max(.1,5*float(np.median(dt)))
    first_pass=bool(first_times[-1]-first_times[0]>=5-2*np.median(dt) and maxgap<=gapbound and gm<.05 and abs(am-g)<=.5)
    cal=calibrate_static_imu(samples,latitude_deg=float(np.degrees(lat)),height_m=height)
    gap_rows=gaps(times,.1,seq)
    for row in gap_rows:
        end=row['end_absolute_s'];sel=np.flatnonzero((gnss_times>=end)&(gnss_times<=end+1))
        if len(sel)>=2:
            rates=np.linalg.norm(np.diff(positions[sel],axis=0),axis=1)/np.diff(gnss_times[sel])
            row['gnss1_position_rate_1s_after']={'sample_count':len(sel),'median_mps':float(np.median(rates)),
                'max_mps':float(np.max(rates)),'net_mps':float(np.linalg.norm(positions[sel[-1]]-positions[sel[0]])/(gnss_times[sel[-1]]-gnss_times[sel[0]])),
                'definition':'adjacent HPPOSECEF ECEF Euclidean difference / actual UTC dt; no interpolation'}
        else: row['gnss1_position_rate_1s_after']={'status':'UNAVAILABLE','sample_count':len(sel)}
    calibration=asdict(cal)
    for k,v in calibration.items():
        if isinstance(v,np.ndarray):calibration[k]=v.tolist()
    return {'status':'OBSERVED','sample_count':len(samples),'dt_median_s':float(np.median(dt)),
        'dt_max_s':float(np.max(dt)),'nonpositive_dt_count':int(np.sum(dt<=0)),
        'first_absolute_s':float(times[0]),'last_absolute_s':float(times[-1]),
        'first_relative_s':float(times[0]-seq.base_time),'gaps_gt_0p1s':gap_rows,
        'first_five_seconds':{'start_absolute_s':float(times[0]),'end_absolute_s':float(times[0]+5),
            'start_relative_s':float(times[0]-seq.base_time),'end_relative_s':float(times[0]+5-seq.base_time),
            'satisfies_frozen_static_criteria':first_pass,'gyro_norm_median_radps':gm,
            'acceleration_norm_median_mps2':am,'local_g_mps2':g,'max_internal_gap_s':maxgap,'gap_bound_s':gapbound},
        'first_satisfying_static_window':calibration,'projection':'timestamp,gyro,accel only; no quaternion/RPY/navigation fields'}


def events(seq, imu):
    if seq.sequence_id=='BY2':
        # Same BY2 control pin is explicitly contained in both sequence contracts.
        d=yaml.safe_load((seq.code_root/'configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml').read_text())
        kick=d['window_contract']['constants']['by2_control']['kick_time_lower_bound'];status='DETECTED_FROZEN_CONTROL'
        onsets=None
    else:
        d=yaml.safe_load((seq.code_root/f'configs/paper_rebuild/clean5/CLEAN5_{seq.sequence_id}_SEQUENCE_CONTRACT.yaml').read_text())
        win=d['window_contract'];kick=win['kick']['kick_time_R1'];status=win['kick']['status']
        onsets={k:win.get(k) for k in ('t_on_g','t_on_b','kick_dropout_hypothesis')}
    first=imu['first_five_seconds']
    return {'imu_file_start_absolute_s':imu['first_absolute_s'],'first_five_seconds':first,
        'kick_status':status,'kick_relative_s':kick,'kick_absolute_s':None if kick is None else seq.base_time+kick,
        'sequence_start_relative_s':seq.window[0],'sequence_start_absolute_s':seq.base_time+seq.window[0],
        'contains_detected_kick':None if kick is None else first['start_relative_s']<=kick<=first['end_relative_s'],
        'kick_judgement':'UNDETERMINED_NO_DETECTED_KICK' if kick is None else ('YES' if first['start_relative_s']<=kick<=first['end_relative_s'] else 'NO'),
        'frozen_onset_metadata':onsets}


def observe_receiver_status(seq):
    """Keep 1 Hz status float counts distinct from 5 Hz pAcc thresholds."""
    path=seq.gnss2_raw.parent/'gnss2-status.csv'
    source=verify_hash_locked_file(path,raw_root=seq.raw_root,hash_lock=seq.hash_lock)
    with path.open(encoding='utf-8-sig',newline='') as h: rows=list(csv.DictReader(h))
    selected=[r for r in rows if int(r['fix_type'])==7]
    return {'source':source,'epoch_count':len(rows),
        'fix_type_histogram':dict(Counter(r['fix_type'] for r in rows)),
        'float_fix_type_7_count':len(selected),
        'float_relative_sys_stamp_s':[int(r['sys_stamp.secs'])+int(r['sys_stamp.nsecs'])*1e-9-seq.base_time for r in selected],
        'comparison_note':'Status epochs and HPPOSECEF pAcc threshold epochs have different cadence and definitions; counts are not required equal.'}


def dependencies(seq):
    d=yaml.safe_load((seq.code_root/CALIBRATED_CONTRACT).read_text())
    root=seq.clean_root
    targets={'evaluator':(Path(d['evaluator']['path'].replace('<CLEAN_ROOT>',str(root))),d['evaluator']['sha256']),
        'v21_sequences_v3':(root/'stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/13_AGGREGATE_SEQUENCES/v3/UNIQUE_EVALUATION_RESULTS.csv','e26dfcd830d6c711ffbb7debd68293fbf7b7ea28240e16bce582381b61ea6a0b'),
        'figure_render':(root/'stages/CLEAN6_PUBLICATION_FIGURES/figures/v21/RENDER_MANIFEST.json','800df76ad82b68e3fca7aded30081f6d1ad01241175978baf440c9e0f290dd4e'),
        'parity_target':(root/'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/00_PARITY_TARGET_AND_AUDITS/A_TARGET_EXTRACTION.json','63ad6db8a65aafb3730cdcb4342dcd0b3ba1fad88784719ba920755dca169790')}
    result={}
    for role,(p,pin) in targets.items():
        exists=p.is_file();digest=sha256_file(p) if exists else None
        result[role]={'path':alias_path(p,seq),'exists':exists,'expected_sha256':pin,'sha256':digest,'matches':digest==pin}
    target=targets['parity_target'][0]
    if target.is_file():
        doc=json.loads(target.read_text());result['external_frozen_navs']={}
        for method in ('LC01','EXT05C'):
            record=doc['methods'][method]
            result['external_frozen_navs'][method]={'continuity':record['continuity']}
        # Bounded filename enumeration; NAV only, never trace.
        ext=root/'stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER'
        result['clean4_exact_navs']=[{'path':alias_path(p,seq),'exists':True,'sha256':sha256_file(p)} for p in sorted(ext.rglob('EXACT_EVALUATOR_INPUT.nav'))]
    result['sequence_metadata']={'base_time':seq.base_time,'window':seq.window,'baseline_median_m':seq.baseline_median_m,
        'trace_path':alias_path(seq.trace,seq),'trace_sha256':seq.trace_sha256,'trace_verification':'DECLARED_METADATA_ONLY_NOT_OPENED_OR_HASHED'}
    return result


def run_probe():
    results={};control=None
    for name in ('BY2','BY2H','BY2O'):
        seq=load_sequence_paths(name);dest=seq.output_root/'01_PROBE'/name
        if (dest/'PROBE.json').exists():raise FileExistsError(dest/'PROBE.json')
        out={'sequence':name,'data_mode':f'real_{name.lower()}_raw','synthetic_data_used':False,
             'semisynthetic_data_used':False,'solver_invocation_count':0,'evaluator_invocation_count':0,
             'trace_open_count':0,'trace_hash_count':0,'fail_soft_errors':[]}
        def attempt(key,fn):
            try: out[key]=fn();return out[key]
            except Exception as exc:
                out[key]={'status':'UNAVAILABLE','error':f'{type(exc).__name__}: {exc}'}
                out['fail_soft_errors'].append(key);return None
        gnss=None
        try:
            out['P1'],gnss=observe_gnss(seq,control)
            if name=='BY2':
                control=[r['pacc_m']['median'] for r in out['P1']['receivers']]
                for i,r in enumerate(out['P1']['receivers']):
                    r['pacc_threshold_3x_BY2_median_m']=control[i]*3
                    # Filled on the same raw observation by a bounded second P1 pass.
                out['P1'],gnss=observe_gnss(seq,control)
        except Exception as exc:
            out['P1']={'status':'UNAVAILABLE','error':f'{type(exc).__name__}: {exc}'};out['fail_soft_errors'].append('P1')
        imu=attempt('P2',lambda:observe_imu(seq,gnss)) if gnss else None
        if imu:attempt('P6',lambda:events(seq,imu))
        def lock_check():
            clean5=seq.clean_root/'01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK_CLEAN5.csv'
            rows=list(csv.DictReader(clean5.open(encoding='utf-8-sig')))
            return {'clean5_row_count':len(rows),'clean5_sha256':sha256_file(clean5),
                'clean5_expected_sha256':'faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67',
                'selected_lock':alias_path(seq.hash_lock,seq),'selection_note':seq.hash_lock_note,
                'files':[verify_hash_locked_file(p,raw_root=seq.raw_root,hash_lock=seq.hash_lock) for p in (seq.gnss1_raw,seq.gnss2_raw,seq.go2_body)]}
        attempt('P4',lock_check);attempt('P5',lambda:dependencies(seq))
        attempt('P1_status_supplement',lambda:observe_receiver_status(seq))
        if name=='BY2' and out.get('P1',{}).get('status')=='OBSERVED' and imu:
            rs=out['P1']['receivers'];checks={'hp1510':all(r['hpposecef_epochs']==1510 for r in rs),'rawx1509':all(r['rawx_epochs']==1509 for r in rs),
                'imu63278':imu['sample_count']==63278,'week2408_leap18':all(r['gps_week_set']==[2408] and r['leap_seconds_set']==[18] for r in rs),
                'all200ms':all(r['itow_interval_histogram_ms']=={200:1509} for r in rs),'plus2ms':all(r['constant_plus_2ms_all_rawx'] for r in rs)}
            out['P3']={'checks':checks,'passed':all(checks.values())}
        out['status']='OBSERVED_WITH_UNAVAILABLE_ITEMS' if out['fail_soft_errors'] else 'OBSERVED'
        write_json(dest/'PROBE.json',out)
        with (dest/'PROBE.md').open('x') as h:h.write('# '+name+' read-only probe\n\n```json\n'+json.dumps(out,ensure_ascii=False,indent=2)+'\n```\n')
        results[name]=out
        print(name, out['status'], 'P1/P2 complete',flush=True)
    return results
