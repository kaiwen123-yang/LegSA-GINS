"""P-02 sealed-input evaluation and separate physical-point v3 postprocessing."""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

from ..manifest import sha256_file
from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256, evaluate, write_json
from ..clean5_sequence.offline_eval import canonical_headers
from ..clean5_sequence.evaluation_tables import SEGMENT_FIELDS
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..subprocess_guard import run_process_group
from ..horizontal_literature.shared_raw_backend import ecef_to_geodetic
from .decomposition import METRICS, build_decomposition


def body_to_ned(rpy_deg):
    """Active Rz(yaw) Ry(pitch) Rx(roll), body FRD to navigation NED."""
    r, p, y = np.deg2rad(np.asarray(rpy_deg, dtype=float)).T
    cr,sr,cp,sp,cy,sy = np.cos(r),np.sin(r),np.cos(p),np.sin(p),np.cos(y),np.sin(y)
    return np.stack((cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr,
                     sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr,
                     -sp,cp*sr,cp*cr), axis=-1).reshape((-1,3,3))


def transform_nav(nav, baseline_median_m):
    """Return a new NAV; only LLH columns change under the human physical contract."""
    source = np.asarray(nav, dtype=float)
    if source.ndim != 2 or source.shape[1] < 11 or not np.isfinite(source).all():
        raise ValueError('NAV must be finite with time, LLH and roll/pitch/yaw columns')
    if not math.isfinite(baseline_median_m) or baseline_median_m <= 0:
        raise ValueError('Frozen A1 baseline median must be positive and finite')
    out = source.copy()
    lever = np.array([.03, .03-.5*baseline_median_m, -.30])
    offset = np.einsum('nij,j->ni', body_to_ned(source[:,8:11]), lever)
    lat,lon = np.deg2rad(source[:,2]),np.deg2rad(source[:,3])
    sl,cl,so,co = np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
    radius = 6378137.0/np.sqrt(1-6.6943799901413165e-3*sl*sl)
    xyz = np.column_stack(((radius+source[:,4])*cl*co,(radius+source[:,4])*cl*so,
                          (radius*(1-6.6943799901413165e-3)+source[:,4])*sl))
    north,east,down = offset.T
    xyz += np.column_stack((-sl*co*north-so*east-cl*co*down,
                            -sl*so*north+co*east-cl*so*down,cl*north-sl*down))
    llh = np.asarray([ecef_to_geodetic(p) for p in xyz])
    out[:,2:4] = np.rad2deg(llh[:,:2]); out[:,4] = llh[:,2]
    return out


def body_frame_bias(errors, nav):
    """Yaw-only ENU to forward/right/up, exact NAV epoch match, population std."""
    t = np.asarray(errors['time'], float)
    nt = nav[:,1]
    if not len(t) or not np.isfinite(nt).all() or np.any(np.diff(nt)<=0):
        raise ValueError('Invalid chronological support')
    j = np.searchsorted(nt,t)
    j = np.clip(j,0,len(nt)-1)
    previous = np.maximum(j-1,0)
    j = np.where(np.abs(nt[previous]-t)<np.abs(nt[j]-t),previous,j)
    if np.any(np.abs(nt[j]-t)>1e-7):
        raise ValueError('Error epochs do not match original NAV; interpolation refused')
    yaw = np.deg2rad(nav[j,10]); north=np.asarray(errors['err_n_m'],float); east=np.asarray(errors['err_e_m'],float)
    values = np.column_stack((np.cos(yaw)*north+np.sin(yaw)*east,
                              -np.sin(yaw)*north+np.cos(yaw)*east,np.asarray(errors['err_u_m'],float)))
    if not np.isfinite(values).all():
        raise ValueError('Nonfinite error or attitude; no epoch deletion')
    row={'count':len(t),'time_start':float(t[0]),'time_end':float(t[-1]),'std_ddof':0,
         'rotation':'NAV yaw; forward=cos(yaw)*N+sin(yaw)*E; right=-sin(yaw)*N+cos(yaw)*E',
         'fit_used':False,'further_correction_used':False}
    for k, axis in enumerate(('forward','right','up')):
        row[axis+'_signed_mean_m']=float(values[:,k].mean())
        row[axis+'_standard_deviation_m']=float(values[:,k].std(ddof=0))
    return row


def _resolve(value, registry):
    text=str(value)
    for key, attr in (('CLEAN_ROOT','clean_root'),('RAW_ROOT','raw_root'),('CODE_ROOT','code_root')):
        text=text.replace('<'+key+'>',str(getattr(registry,attr)))
    return Path(text)


def _metrics(errors, nav, identity, reference_count=None):
    t=np.asarray(errors['time'],float)
    if not len(t) or not np.isfinite(errors.select_dtypes(include='number').to_numpy()).all():
        raise ValueError('Empty/nonfinite evaluated errors')
    row=dict(identity)
    for prefix,unit,col in (('north','m','err_n_m'),('east','m','err_e_m'),('up','m','err_u_m'),
                            ('roll','deg','roll_err_deg'),('pitch','deg','pitch_err_deg'),('yaw','deg','yaw_err_deg')):
        canonical._put_stats(row,prefix,unit,canonical._axis_stats(t,np.asarray(errors[col],float)))
    for prefix,col in (('horizontal','horizontal_err_m'),('position_3d','position_3d_err_m')):
        canonical._put_stats(row,prefix,'m',canonical._norm_stats(t,np.asarray(errors[col],float)))
    count=int(np.sum((nav[:,1]>=66)&(nav[:,1]<=340)))
    row.update(evaluation_status='COMPLETED',finite_output=True,finite_ratio=1.,matched_epoch_count=len(t),
        output_epoch_count=count,unmatched_epoch_count=max(0,count-len(t)),reference_epoch_count=reference_count,
        coverage_ratio=len(t)/count if count else None,time_start=float(t[0]),time_end=float(t[-1]),
        reference_velocity_supported=False,reference_is_independent_ground_truth=False,
        uncertainty_status=('UNAVAILABLE_POINT_TRANSFORM_COVARIANCE_NOT_PROPAGATED' if identity['evaluator_contract'].endswith('v3') else 'ORIGINAL_STD_WHERE_AVAILABLE'))
    return row


def _external_evaluate(*, evaluator, trace, nav, outdir, registry, settings):
    """Frozen external evaluator argv omits STD; capture/reference-open audit retained."""
    if sha256_file(evaluator)!=EVALUATOR_SHA256:
        raise ValueError('Evaluator identity mismatch')
    outdir.mkdir(parents=True,exist_ok=False)
    config={'evaluator':str(evaluator),'evaluator_sha256':EVALUATOR_SHA256,'trace':str(trace),
            'trace_sha256':settings['trace_sha256'],'window':[66.,340.],'outdir':str(outdir)}
    write_json(outdir/'CAPTURE_CONFIG.json',config)
    env={'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
         'MPLBACKEND':'Agg','MPLCONFIGDIR':str(outdir/'.matplotlib'),'XDG_CACHE_HOME':str(outdir/'.cache'),
         'PYTHONPATH':str(registry.code_root/'scripts/paper_rebuild/clean5_evaluator_observer')+':'+str(registry.code_root/'src'),
         'CLEAN5_EVALUATOR_CAPTURE_CONFIG':str(outdir/'CAPTURE_CONFIG.json')}
    argv=[sys.executable,str(evaluator),'--trace',str(trace),'--nav',str(nav),'--outdir',str(outdir),
          '--base_time',str(settings['base_time']),'--yaw_truth_mode','enu']
    log=outdir/'EVALUATOR_OPENAT.strace'; start=time.monotonic()
    result=run_process_group(['env',*(f'{k}={v}' for k,v in env.items()),'strace','-f','-yy','-s','4096',
        '-e','trace=openat,execve','-o',str(log),*argv],cwd=registry.code_root,timeout_seconds=1800,
        timeout_message='Parity external evaluator timeout; no retry',launch_failure_message='Evaluator launch failure')
    (outdir/'evaluator_stdout.log').write_text(result.stdout);(outdir/'evaluator_stderr.log').write_text(result.stderr)
    records=audited_open_records(log,registry.code_root)
    traces=[r for r in records if Path(r['path'])==trace]
    raw=[r for r in records if registry.raw_root in Path(r['path']).parents]
    scope=write_scope_audit(records,raw_root=registry.raw_root,clean_root=registry.clean_root,allowed_write_roots=[outdir])
    capture=json.loads((outdir/'EVALUATOR_CAPTURE.json').read_text()) if (outdir/'EVALUATOR_CAPTURE.json').exists() else {}
    passed=(result.returncode==0 and len(traces)==len(raw)==1 and traces[0]['return_code']>=0
        and 'O_RDONLY' in traces[0]['flags'] and scope['pass'] and capture.get('trace_sha256')==settings['trace_sha256']
        and capture.get('trace_handle_hash_count')==1 and capture.get('consistency',{}).get('passed') is True
        and not any(r['path'].endswith(('.bag','.fpl')) for r in records))
    audit={'passed':passed,'argv':argv,'exit_code':result.returncode,'trace_open_count':len(traces),
           'raw_open_count':len(raw),'write_scope':scope,'strace_sha256':sha256_file(log),'STD':'OMITTED_AS_FROZEN_EXTERNAL_CONTRACT'}
    write_json(outdir/'EVALUATOR_STRACE_AUDIT.json',audit)
    if not passed: raise RuntimeError('External evaluator audit failed: '+result.stderr[-1200:])
    return {'capture':capture,'audit':audit,'runtime_seconds':time.monotonic()-start}


def _csv(path, rows, prefix=()):
    fields=list(prefix)+[k for row in rows for k in row if k not in prefix]
    fields=list(dict.fromkeys(fields)) or ['status']
    with path.open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:canonical._csv_value(row.get(k)) for k in fields} for row in rows)



def pairwise_tables(rows):
    """Within-variant C00 comparisons; never join profiles across rungs."""
    index={(r['variant_id'],r['method_id']):r for r in rows}
    if len(index)!=len(rows):raise ValueError('Duplicate variant/method result')
    cases,summaries=[],[]
    for variant in dict.fromkeys(r['variant_id'] for r in rows):
        for candidate_id,reference_id in (('F03','F01'),('A04','F01'),('A04','F03')):
            candidate=index.get((variant,candidate_id));reference=index.get((variant,reference_id))
            if candidate is None or reference is None:continue
            for metric in METRICS:
                cv=canonical._float(candidate.get(metric));rv=canonical._float(reference.get(metric))
                available=cv is not None and rv is not None
                delta=cv-rv if available else None
                relative=delta/abs(rv)*100 if available and rv!=0 else None
                base={'variant_id':variant,'comparison':variant+':'+candidate_id+'-'+reference_id,
                      'candidate_method_id':candidate_id,'reference_method_id':reference_id,
                      'metric_name':metric,'candidate_source_row':candidate['source_row'],
                      'reference_source_row':reference['source_row'],'case_id':'C00_clean_normal',
                      'evaluator_contract':candidate['evaluator_contract'],
                      'support_policy':'native support; no matched-support claim',
                      'status':'AVAILABLE' if available else 'UNAVAILABLE'}
                cases.append({**base,'candidate_value':cv,'reference_value':rv,
                              'delta_candidate_minus_reference':delta,'relative_change_percent':relative,
                              'candidate_better':delta < -1e-12 if available else None,
                              'tie':abs(delta)<=1e-12 if available else None})
                summaries.append({**base,'scope':'overall','family':'ALL','paired_sample_count':int(available),
                    'mean_delta_candidate_minus_reference':delta,'median_delta_candidate_minus_reference':delta,
                    'std_delta':0. if available else None,'p10_delta':delta,'p90_delta':delta,
                    'mean_relative_change_percent':relative,'median_relative_change_percent':relative,
                    'win_count':int(delta < -1e-12) if available else None,
                    'tie_count':int(abs(delta)<=1e-12) if available else None,
                    'loss_count':int(delta > 1e-12) if available else None,
                    'win_rate':float(delta < -1e-12) if available else None,
                    'confidence_interval_status':'NOT_AVAILABLE_SINGLE_CASE',
                    'wilcoxon_status':'NOT_AVAILABLE_SINGLE_CASE',
                    'seed_inference_status':'NOT_AVAILABLE_C00_NO_SEEDS',
                    'delta_definition':'candidate_minus_reference'})
    return cases,summaries


def full_window_segments(rows):
    """C00 has no degradation segments; retain the same CLEAN5 segment schema."""
    segments=[]
    for row in rows:
        for metric,prefix,unit,signed in (('horizontal','horizontal','m',False),
                ('position_3d','position_3d','m',False),('up','up','m',True),('yaw','yaw','deg',True)):
            segments.append({**{key:row.get(key) for key in ('run_id','method_id','effective_configuration_id',
                'dataset_id','case_id','variant_id','evaluator_contract','source_row')},
                'segment_id':'full','metric_name':metric,'unit':unit,
                'rmse':row.get(prefix+'_rmse_'+unit),
                'p95_abs':row.get(prefix+('_p95_absolute_' if signed else '_p95_')+unit),
                'max_abs':row.get(prefix+('_max_absolute_' if signed else '_max_')+unit),
                'count':row.get('matched_epoch_count') if row['evaluation_status']=='COMPLETED' else None,
                'signed_mean':row.get(prefix+'_signed_mean_'+unit) if signed else None,
                'time_start':row.get('time_start'),'time_end':row.get('time_end'),
                'sequence_window_start_s':66.,'sequence_window_end_s':340.,
                'degradation_window_start_s':None,'degradation_window_end_s':None,
                'secondary_run_epoch_count':0 if row['evaluation_status']=='COMPLETED' else None,
                'status':row['evaluation_status']})
    return segments


def evaluate_ladder(*, registry, stage_root, contract, run_records, code_commit, baseline_median_m):
    stage=Path(stage_root); settings=contract['evaluation']
    if settings['v2_sha256']!=EVALUATOR_SHA256 or list(settings['window_seconds'])!=[66.,340.] or settings['base_time']!=1772784000:
        raise ValueError('Frozen evaluator/time contract mismatch')
    evaluator=_resolve(settings['evaluator_path'],registry)
    trace=_resolve(settings.get('trace_path',registry.sequences['BY2'].trace_path),registry)
    p01=json.loads((stage/'00_PARITY_TARGET_AND_AUDITS/A_TARGET_EXTRACTION.json').read_text())
    records=[dict(r) for r in run_records]
    for method, item in p01['canonical_v0'].items():
        records.append({'variant_id':'V0','method_id':method,'run_id':'V0_'+method,'terminal_status':'COMPLETED',
            'effective_profile':item['row'].get('effective_configuration_id'),
            'effective_configuration_id':item['row'].get('effective_configuration_id'),
            'output_root':str(Path(item['configuration_path']).parent),'frozen_row':item['row'],
            'source_row':f"{item['logical_source_table']}:{item['logical_source_line']}",
            'frozen_eval_dir':str(canonical._complete_eval_dir(Path(item['logical_source_table']).parent,item['run_id']) or Path(item['logical_source_table']).parent/item['run_id'])})
    for method,item in p01['methods'].items():
        directory=Path(item['source_table']).parent/item['method_id']
        records.append({'variant_id':'EXTERNAL','method_id':method,'run_id':method,'terminal_status':'COMPLETED',
            'effective_profile':item['method_id'],'effective_configuration_id':item['method_id'],
            'nav_path':str(directory/'EXACT_EVALUATOR_INPUT.nav'),'nav_sha256':item['continuity']['evaluator_nav_sha256'],
            'frozen_eval_dir':str(directory/'EXACT_EVALUATOR_OUTPUT'),'source_row':f"{item['source_table']}:{item['source_line_1based']}",
            'frozen_metrics':item['frozen_metrics']})
    out=stage/'08_AGGREGATE'; evalroot=stage/'07_OFFLINE_EVALUATION'
    if out.exists() or evalroot.exists(): raise FileExistsError('Existing parity evaluation; retry refused')
    out.mkdir();(out/'v3').mkdir();evalroot.mkdir()
    rows_by_version={}; bias_by_version={}; gates=[]
    for version in ('v2','v3'):
        rows=[];bias=[]
        for record in records:
            identity={k:record.get(k) for k in ('variant_id','method_id','run_id','terminal_status','effective_profile','effective_configuration_id')}
            identity.update(dataset_id='BY2',case_id='C00_clean_normal',evaluator_contract='evaluator_contract_'+version,
                evaluator_sha256=EVALUATOR_SHA256,code_commit=code_commit,data_mode='real_by2_raw',synthetic_data_used=False,
                semisynthetic_data_used=False,trace_used_online=False,source_row=record.get('source_row',''),
                evaluation_invoked=False,wrapper_runtime_seconds=record.get('runtime_seconds'),
                wrapper_exit_code=record.get('exit_code'),wrapper_runtime_source='sealed parity run record' if 'runtime_seconds' in record else 'UNAVAILABLE')
            row=dict(identity); br=dict(identity)
            try:
                if record['terminal_status'] not in ('COMPLETED','PASS'):
                    raise ValueError('Solver unavailable: '+record['terminal_status'])
                root=Path(record.get('output_root','.')); navpath=Path(record.get('nav_path',root/'KF_GINS_Navresult.nav'))
                if navpath.is_symlink() or not navpath.is_file():raise ValueError('NAV missing or symlink')
                source_hash=sha256_file(navpath)
                if record.get('nav_sha256') and record['nav_sha256']!=source_hash: raise ValueError('Sealed NAV hash changed')
                nav=canonical._read_numeric_table(navpath).to_numpy(float)
                actual_nav=navpath
                if version=='v3':
                    transformed=transform_nav(nav,baseline_median_m)
                    derived=evalroot/'v3'/'NAV_INPUTS'/record['run_id'];derived.mkdir(parents=True,exist_ok=False)
                    actual_nav=derived/'EVALUATOR_INPUT.nav'
                    # Preserve every non-position token byte; write LLH with roundtrip precision.
                    lines=navpath.read_text().splitlines(); numeric=[line for line in lines if line.strip() and not line.lstrip().startswith('#')]
                    if len(numeric)!=len(transformed): raise ValueError('NAV row parser disagreement')
                    with actual_nav.open('x') as handle:
                        for original,changed in zip(numeric,transformed):
                            tokens=original.split();tokens[2:5]=[format(x,'.17g') for x in changed[2:5]]
                            handle.write(' '.join(tokens)+'\n')
                    write_json(derived/'TRANSFORM_MANIFEST.json',{'evaluator_contract':'evaluator_contract_v3',
                        'input_nav':str(navpath),'input_sha256':source_hash,'output_sha256':sha256_file(actual_nav),
                        'baseline_median_m':baseline_median_m,'lever_frd_m':[.03,.03-.5*baseline_median_m,-.30],
                        'attitude_columns_zero_based':[8,9,10],'fit_used':False,'code_commit':code_commit,
                        'source_nav_unchanged':sha256_file(navpath)==source_hash})
                frozen=version=='v2' and record.get('frozen_eval_dir')
                if frozen:
                    evaluation_dir=Path(record['frozen_eval_dir']); capture={};runtime=None
                else:
                    evaluation_dir=evalroot/version/'PER_RUN'/record['run_id']
                    if record['variant_id']=='EXTERNAL':
                        result=_external_evaluate(evaluator=evaluator,trace=trace,nav=actual_nav,outdir=evaluation_dir,registry=registry,settings=settings)
                    else:
                        std=Path(record.get('std_path',root/'KF_GINS_STD.txt'))
                        if record.get('std_sha256') and sha256_file(std)!=record['std_sha256']: raise ValueError('Sealed STD hash changed')
                        result=evaluate(evaluator=evaluator,trace=trace,nav=actual_nav,std=std,outdir=evaluation_dir,
                            base_time=settings['base_time'],window=[66.,340.],trace_sha256=settings['trace_sha256'],
                            code_root=registry.code_root,raw_root=registry.raw_root,clean_root=registry.clean_root)
                    capture=result['capture'];runtime=result['runtime_seconds']
                    if capture.get('consistency',{}).get('passed') is not True:raise ValueError('Evaluator capture consistency failed')
                    expected_columns={'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}
                    if capture.get('selected_columns')!=expected_columns:raise ValueError('Frozen reference columns mismatch')
                    row['evaluation_invoked']=True
                errors=canonical._read_error_series(evaluation_dir)
                if version=='v2' and not frozen and (root/'RUN_MANIFEST.json').is_file():
                    native=canonical._compute_result({**identity,'effective_profile':record.get('effective_profile')},{},root,evaluation_dir,capture['reference_epoch_count'],runtime,True)
                    row={**native,**row}
                row=_metrics(errors,nav,row,capture.get('reference_epoch_count'))
                if frozen and record.get('frozen_row'):
                    for metric in METRICS:
                        if abs(float(row[metric])-float(record['frozen_row'][metric]))>1e-10:raise ValueError('Frozen metric mismatch '+metric)
                    row={**record['frozen_row'],**row}
                    row['reference_epoch_count']=record['frozen_row']['reference_epoch_count']
                if frozen and record.get('frozen_metrics'):
                    for metric,key in zip(METRICS,('horizontal_m_rmse','position_3d_m_rmse','up_m_rmse','yaw_deg_rmse')):
                        if abs(float(row[metric])-float(record['frozen_metrics'][key]))>1e-10:raise ValueError('External frozen metric mismatch')
                row.update(evaluation_runtime_seconds=runtime,error_series_source=str(evaluation_dir),source_nav_sha256=source_hash,
                           evaluator_nav_sha256=sha256_file(actual_nav))
                br.update(body_frame_bias(errors,nav),status='AVAILABLE',error_series_source=str(evaluation_dir))
                if sha256_file(navpath)!=source_hash:raise ValueError('Source NAV mutated')
            except Exception as exc:
                row={**identity,'evaluation_status':'UNAVAILABLE','unavailable_reason':str(exc),**{m:'UNAVAILABLE' for m in METRICS}}
                br.update(status='UNAVAILABLE',unavailable_reason=str(exc))
            rows.append(row);bias.append(br)
            gates.append({'version':version,'run_id':record['run_id'],'status':row['evaluation_status'],'reason':row.get('unavailable_reason')})
            print(f"Parity {version} {record['run_id']}: {row['evaluation_status']}",flush=True)
        target=out if version=='v2' else out/'v3'
        attempt=_resolve(settings['canonical_attempt'],registry);headers=canonical_headers(attempt)
        for n,row in enumerate(rows,2):row['result_source_row']=str(target/'UNIQUE_EVALUATION_RESULTS.csv')+':'+str(n)
        # Every row retains explicit original-source reference in addition to this table's identity.
        for row in rows:
            row['frozen_source_row']=row.get('source_row');row['source_row']=row['result_source_row']
        tables={'UNIQUE_EVALUATION_RESULTS.csv':rows,'LOGICAL_EVALUATION_RESULTS.csv':rows}
        available=[r for r in rows if r['evaluation_status']=='COMPLETED']
        for name in ('UNIQUE_METHOD_SUMMARY.csv','LOGICAL_METHOD_SUMMARY.csv'):
            tables[name]=canonical._summary_rows(available,('variant_id','method_id'),canonical._numeric_fields(available)) if available else []
        tables['PAIRWISE_CASE_LEVEL.csv'],tables['PAIRWISE_SUMMARY.csv']=pairwise_tables(rows)
        tables['MODULE_ACTION_SUMMARY.csv']=canonical._summary_rows(available,('variant_id','method_id'),[m for m in canonical.MODULE_SCALARS if any(m in r for r in available)]) if available else []
        tables['RUNTIME_SUMMARY.csv']=canonical._summary_rows(rows,('variant_id','method_id'),['solver_runtime_seconds','wrapper_runtime_seconds','evaluation_runtime_seconds']) if rows else []
        tables['METRIC_COVERAGE_REPORT.csv']=canonical._coverage_report(rows)
        for coverage in tables['METRIC_COVERAGE_REPORT.csv']:
            if coverage['metric_name'] in METRICS:
                coverage['source_fields']='exact frozen evaluator error_series.csv; Canonical unchanged statistics'
        for name,table in tables.items():_csv(target/name,table,headers[name])
        _csv(target/'BODY_FRAME_BIAS.csv',bias)
        _csv(target/'WINDOW_SEGMENT_SUMMARY.csv',full_window_segments(rows),SEGMENT_FIELDS)
        write_json(target/'FIELD_DEFINITIONS.json',{'schema_version':'paper_rebuild.clean5.parity.evaluation_fields.v2',
            'original_statistics_source':'canonical541.offline_eval_aggregate unchanged axis/norm helpers',
            'window':[66.,340.],'segment_policy':'C00 full only; no degradation or secondary windows',
            'pairwise_policy':'Within identical variant and evaluator contract only; F03-F01,A04-F01,A04-F03',
            'pairwise_metrics':list(METRICS),'unavailable_policy':'No endpoint substitution; missing remains UNAVAILABLE',
            'runtime_policy':'Native solver_runtime_seconds preserved; sealed wrapper runtime recorded separately, never substituted',
            'body_frame_policy':'Own NAV yaw exact-epoch rotation; population standard deviation ddof=0',
            'covariance_policy':'v3 position uncertainty not propagated; no v3 transformed consistency claim',
            'statistical_inference':'UNAVAILABLE_SINGLE_C00_CASE'})
        rows_by_version[version]=rows;bias_by_version[version]=bias
    decomposition=build_decomposition(rows_by_version['v2'],rows_by_version['v3'])
    _csv(out/'PARITY_DECOMPOSITION.csv',decomposition)
    metadata={'status':'COMPLETED_WITH_UNAVAILABLE' if any(g['status']!='COMPLETED' for g in gates) else 'COMPLETED',
              'code_commit':code_commit,'evaluator_sha256':EVALUATOR_SHA256,'trace_sha256':settings['trace_sha256'],
              'baseline_median_m':baseline_median_m,'run_gates':gates,'rows':rows_by_version,'body_frame_bias':bias_by_version,
              'decomposition':decomposition,'solver_executions_in_evaluation':0,'fit_used':False,'further_correction_used':False}
    write_json(out/'FINAL_EVALUATION_SUMMARY.json',metadata)
    write_json(out/'v3/FINAL_EVALUATION_SUMMARY.json',{k:v for k,v in metadata.items() if k not in ('rows','body_frame_bias','decomposition')})
    return metadata
