"""Eight sealed generalization runs; eighteen bounded evaluator invocations."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import numpy as np
from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_parity.evaluation import transform_nav,write_transformed_nav,body_frame_bias,_csv,pairwise_tables,full_window_segments
from ..clean5_parity.decomposition import METRICS,difference
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256,evaluate
from ..clean5_sequence.evaluation_tables import segment_rows,compute_sequence_result
from ..manifest import sha256_file
from .diagnosis import pinned,resolve,write_json

LADDER=(('V0','A04'),('V1','A04'),('V2','A04'),('V2is','A04'),('V2is','F03'))


def metrics(errors,nav,identity,window,reference_count):
    t=np.asarray(errors.time,float);row=dict(identity)
    if not len(t) or not np.isfinite(errors.to_numpy(float)).all():raise ValueError('Invalid evaluated errors')
    for prefix,unit,col in [('north','m','err_n_m'),('east','m','err_e_m'),('up','m','err_u_m'),('roll','deg','roll_err_deg'),('pitch','deg','pitch_err_deg'),('yaw','deg','yaw_err_deg')]:
        canonical._put_stats(row,prefix,unit,canonical._axis_stats(t,np.asarray(errors[col],float)))
    for prefix,col in [('horizontal','horizontal_err_m'),('position_3d','position_3d_err_m')]:canonical._put_stats(row,prefix,'m',canonical._norm_stats(t,np.asarray(errors[col],float)))
    count=int(np.sum((nav[:,1]>=window[0])&(nav[:,1]<=window[1])))
    row.update(evaluation_status='COMPLETED',matched_epoch_count=len(t),output_epoch_count=count,unmatched_epoch_count=max(0,count-len(t)),coverage_ratio=len(t)/count if count else None,
        reference_epoch_count=reference_count,time_start=float(t[0]),time_end=float(t[-1]),sequence_window_start_s=window[0],sequence_window_end_s=window[1],
        reference_velocity_supported=False,reference_is_independent_ground_truth=False,finite_output=True,finite_ratio=1.)
    return row


def reused_frozen_row(original,identity,source_row):
    """Retain frozen scalar evidence, adding only parity identity/provenance."""
    row={**identity,**original}
    for k in ['run_id','variant_id','dataset_id','evaluator_contract']:
        row[k]=identity[k]
    row.update(result_reused_from_frozen=True,original_source_row=source_row,
               p04_code_commit=identity['code_commit'],p04_evaluation_invoked=False)
    changed=[k for k,v in original.items() if k not in ['run_id','variant_id','dataset_id','evaluator_contract'] and row.get(k)!=v]
    if changed:raise ValueError('Frozen original fields changed: '+','.join(changed))
    row['original_frozen_fields_preserved']=True
    return row


def decomposition(rows,confounds=None):
    lookup={(r['dataset_id'],v,r['variant_id'],r['method_id']):r for v,rr in rows.items() for r in rr};primary=[];versions=[]
    for d in ['BY2','BY2H','BY2O']:
        def term(name,left,right,version=None):
            a=lookup[(d,*left)];b=lookup[(d,*right)];r=difference(name,a,b);r.update(dataset_id=d,left_evaluator_contract='evaluator_contract_'+left[0],right_evaluator_contract='evaluator_contract_'+right[0],decomposition_scope='primary_cross_version' if version is None else 'same_version',evaluator_contract='MIXED_EXPLICIT' if left[0]!=right[0] else 'evaluator_contract_'+left[0])
            if confounds and d in confounds:r['input_exception_confounds']=confounds[d]
            if name=='time':r['time_term_footnote']='时标项含 RV 同历元重配'
            return r
        primary.extend([term('time',('v2','V0','A04'),('v2','V1','A04')),term('rate_point_IMU',('v2','V1','A04'),('v3','V2is','A04')),term('module',('v3','V2is','A04'),('v3','V2is','F03'))])
        for v in ['v2','v3']:
            versions.extend([term('time',(v,'V0','A04'),(v,'V1','A04'),v),term('rate_IMU_same_point_contract',(v,'V1','A04'),(v,'V2is','A04'),v),term('module',(v,'V2is','A04'),(v,'V2is','F03'),v)])
    return primary,versions


def write_tables(target,rows,bias,segments,headers):
    target=Path(target);target.mkdir(parents=True,exist_ok=False);available=[r for r in rows if r['evaluation_status']=='COMPLETED']
    tables={'UNIQUE_EVALUATION_RESULTS.csv':rows,'LOGICAL_EVALUATION_RESULTS.csv':rows}
    for name in ['UNIQUE_METHOD_SUMMARY.csv','LOGICAL_METHOD_SUMMARY.csv']:tables[name]=canonical._summary_rows(available,('dataset_id','variant_id','method_id'),canonical._numeric_fields(available)) if available else []
    cases=[];summaries=[]
    for d in sorted({r['dataset_id'] for r in rows}):
        subset=[r for r in rows if r['dataset_id']==d];pc,ps=pairwise_tables(subset)
        if len({r['case_id'] for r in subset})!=1 or len({r['evaluator_contract'] for r in subset})!=1:raise ValueError('Pairwise mixed case/evaluator identity')
        for r in pc+ps:
            r.update(dataset_id=d,case_id=subset[0]['case_id'],sequence_window_start_s=subset[0].get('sequence_window_start_s'),sequence_window_end_s=subset[0].get('sequence_window_end_s'))
            if d!='BY2' and 'seed_inference_status' in r:r['seed_inference_status']='NOT_AVAILABLE_NATURAL_SEQUENCE_NO_SEEDS'
        cases.extend(pc);summaries.extend(ps)
    tables['PAIRWISE_CASE_LEVEL.csv']=cases;tables['PAIRWISE_SUMMARY.csv']=summaries
    tables['MODULE_ACTION_SUMMARY.csv']=canonical._summary_rows(available,('dataset_id','variant_id','method_id'),[m for m in canonical.MODULE_SCALARS if any(m in r for r in available)]) if available else []
    tables['RUNTIME_SUMMARY.csv']=canonical._summary_rows(rows,('dataset_id','variant_id','method_id'),['solver_runtime_seconds','wrapper_runtime_seconds','evaluation_runtime_seconds'])
    tables['METRIC_COVERAGE_REPORT.csv']=canonical._coverage_report(rows)
    for name,table in tables.items():_csv(target/name,table,headers.get(name,[]))
    _csv(target/'BODY_FRAME_BIAS.csv',bias);_csv(target/'WINDOW_SEGMENT_SUMMARY.csv',segments)
    write_json(target/'FIELD_DEFINITIONS.json',{'statistics':'unchanged Canonical axis/norm helpers','window_policy':'each frozen sequence contract; no BY2 hardcoded denominators','pairwise_policy':'same dataset, variant and evaluator contract','v3_uncertainty':'UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED','reference_velocity_supported':False,'no_epoch_deletion':True})


def evaluate_generalization(registry,contract,stage_root,records,code_commit,bundles):
    spec=contract['p04'];stage=Path(stage_root)
    expected={(d,v,m) for d in ['BY2H','BY2O'] for v,m in LADDER[1:]}
    if len(records)!=8 or {(r['dataset_id'],r['variant_id'],r['method_id']) for r in records}!=expected or any(r['terminal_status']!='COMPLETED' for r in records):raise ValueError('All eight unique sealed runs required')
    evaluator=pinned(spec['evaluator'],registry)
    if spec['evaluator']['sha256']!=EVALUATOR_SHA256:raise ValueError('Wrong frozen evaluator')
    by2_path=pinned(spec['reference_by2_summary'],registry);by2=json.loads(by2_path.read_text())
    rows={v:[] for v in ['v2','v3']};bias={v:[] for v in rows};segments={v:[] for v in rows};gates=[];references=[];invocations=0;raw_v0=[]
    for v in rows:
        for variant,method in LADDER:
            item=next(r for r in by2['rows'][v] if (r['variant_id'],r['method_id'])==(variant,method));row=copy.deepcopy(item);row.update(result_reused_from_P03=True,original_source_row=item.get('source_row'));rows[v].append(row)
            b=copy.deepcopy(next(r for r in by2['body_frame_bias'][v] if (r['variant_id'],r['method_id'])==(variant,method)));b['result_reused_from_P03']=True;b['p04_evaluation_invoked']=False;bias[v].append(b)
    for version in rows:segments[version].extend(full_window_segments(rows[version]))
    for d in ['BY2H','BY2O']:
        ds=spec['sequences'][d];ref=ds['reference'];window=list(map(float,ds['window_seconds']));wd={'t_start':window[0],'t_end':window[1]};reference_paths=[ref[k] for k in ['summary','results','logical_registry']]+[ref['V0_A04'][k] for k in ['nav','std','manifest']]+ref['V0_A04']['error_files']
        for pin in reference_paths:pinned(pin,registry)
        references.extend(reference_paths);summary=json.loads(pinned(ref['summary'],registry).read_text())
        if summary.get('terminal_status')!='PASS_SEQUENCE_EVALUATION_AND_AGGREGATE' or summary['window']!=wd or summary['evaluator_sha256']!=EVALUATOR_SHA256:raise ValueError('Reference sequence summary/window mismatch')
        table,_=canonical._read_csv(pinned(ref['results'],registry));original=next(r for r in table if r['method_id']=='A04');logical=next(r for r in canonical._read_csv(pinned(ref['logical_registry'],registry))[0] if r['method_id']=='A04');raw_v0.append({'dataset_id':d,'source':ref['results'],'original_fields':copy.deepcopy(original)})
        case_meta=dict(logical);v0spec=ref['V0_A04'];v0={'dataset_id':d,'variant_id':'V0','method_id':'A04','run_id':d+'_V0_A04','terminal_status':'COMPLETED','output_root':str(pinned(v0spec['nav'],registry).parent),
            'nav_path':str(pinned(v0spec['nav'],registry)),'nav_sha256':v0spec['nav']['sha256'],'std_path':str(pinned(v0spec['std'],registry)),'std_sha256':v0spec['std']['sha256'],'case_id':logical['case_id'],'effective_profile':logical['effective_profile']}
        jobs=[v0]+[next(r for r in records if (r['dataset_id'],r['variant_id'],r['method_id'])==(d,v,m)) for v,m in LADDER[1:]]
        evalroot=stage/d/'07_OFFLINE_EVALUATION';evalroot.mkdir(parents=True,exist_ok=False)
        baseline=float(ds['baseline_median_m'])
        if float(bundles[d]['baseline_median_m'])!=baseline:raise ValueError('Bundle/preregistered baseline changed')
        for job in jobs:
            navpath=Path(job['nav_path']);stdpath=Path(job['std_path'])
            if sha256_file(navpath)!=job['nav_sha256'] or sha256_file(stdpath)!=job['std_sha256']:raise ValueError('Sealed NAV/STD hash mismatch')
            nav=canonical._read_numeric_table(navpath).to_numpy(float)
            for version in ['v2','v3']:
                identity={k:job.get(k) for k in ['dataset_id','variant_id','method_id','run_id','effective_profile']};identity.update(case_id=logical['case_id'],effective_configuration_id=job.get('effective_profile'),evaluator_contract='evaluator_contract_'+version,
                    evaluator_sha256=EVALUATOR_SHA256,code_commit=code_commit,data_mode=registry.sequences[d].data_mode,synthetic_data_used=False,semisynthetic_data_used=False,trace_used_online=False,
                    source_nav_sha256=job['nav_sha256'],source_row='',original_source_row='',evaluation_invoked=False,result_reused_from_frozen=False,wrapper_runtime_seconds=job.get('runtime_seconds'),wrapper_exit_code=job.get('exit_code'))
                row=dict(identity);br=dict(identity);invoked=False
                try:
                    if job['variant_id']=='V0' and version=='v2':
                        row=reused_frozen_row(original,identity,str(pinned(ref['results'],registry))+':'+str(table.index(original)+2))
                        errors=canonical._read_error_series(resolve(v0spec['error_dir'],registry));row['error_series_source']=v0spec['error_dir'];br['result_reused_from_frozen']=True
                    else:
                        actual=navpath
                        if version=='v3':
                            directory=evalroot/'v3/NAV_INPUTS'/job['run_id'];directory.mkdir(parents=True,exist_ok=False);actual=directory/'EVALUATOR_INPUT.nav';write_transformed_nav(navpath,actual,transform_nav(nav,baseline))
                            write_json(directory/'TRANSFORM_MANIFEST.json',{'input_sha256':job['nav_sha256'],'output_sha256':sha256_file(actual),'baseline_median_m':baseline,'lever_frd_m':[.03,.03-baseline/2,-.30],
                                'evaluator_contract':'evaluator_contract_v3','code_commit':code_commit,'data_mode':registry.sequences[d].data_mode,'synthetic_data_used':False,'semisynthetic_data_used':False,'fit_used':False,'further_correction_used':False,'uncertainty_status':'UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED'})
                        directory=evalroot/version/'PER_RUN'/job['run_id'];invocations+=1;invoked=True
                        if invocations>18:raise ValueError('P04 evaluator invocation limit exceeded')
                        ev=evaluate(evaluator=evaluator,trace=registry.sequences[d].trace_path,nav=actual,std=stdpath,outdir=directory,base_time=ds['base_time'],window=window,trace_sha256=summary['trace_sha256'],code_root=registry.code_root,raw_root=registry.raw_root,clean_root=registry.clean_root)
                        capture=ev['capture']
                        if capture.get('selected_columns')!={'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'} or capture.get('consistency',{}).get('passed') is not True:raise ValueError('Evaluator capture gate failed')
                        errors=canonical._read_error_series(directory);row=metrics(errors,nav,{**identity,'evaluation_invoked':True},window,capture['reference_epoch_count']);row.update(error_series_source=str(directory),evaluator_nav_sha256=sha256_file(actual),evaluation_runtime_seconds=ev['runtime_seconds'])
                        if version=='v2':
                            native=compute_sequence_result({**logical,**job},case_meta,job['output_root'],directory,window=wd,reference_epoch_count=capture['reference_epoch_count'],evaluation_runtime=ev['runtime_seconds'],evaluation_invoked=True,wrapper_runtime_seconds=job.get('runtime_seconds'),wrapper_exit_code=job.get('exit_code'))
                            row={**native,**row}
                        else:row['uncertainty_status']='UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED'
                    br.update(body_frame_bias(errors,nav),status='AVAILABLE',error_series_source=row['error_series_source'])
                    sr=segment_rows(errors,registry={**logical,**job},dataset_id=d,window=wd,case_meta=case_meta)
                    segments[version].extend({**r,'variant_id':job['variant_id'],'evaluator_contract':'evaluator_contract_'+version} for r in sr)
                except Exception as exc:
                    row={**identity,'evaluation_invoked':invoked,'evaluation_status':'UNAVAILABLE','unavailable_reason':str(exc),**{k:'UNAVAILABLE' for k in METRICS}};br.update(status='UNAVAILABLE',unavailable_reason=str(exc))
                br.update(evaluation_invoked=invoked,p04_evaluation_invoked=invoked)
                rows[version].append(row);bias[version].append(br);gates.append({'dataset_id':d,'variant_id':job['variant_id'],'method_id':job['method_id'],'version':version,'status':row['evaluation_status'],'evaluation_invoked':invoked,'reason':row.get('unavailable_reason')})
                print('P04 EVAL',d,job['variant_id'],job['method_id'],version,row['evaluation_status'],flush=True)
            if sha256_file(navpath)!=job['nav_sha256'] or sha256_file(stdpath)!=job['std_sha256']:raise ValueError('Source NAV/STD changed during evaluation')
    # Assign final global row references before making decomposition or partition tables.
    for version in rows:
        target=stage/'08_AGGREGATE' if version=='v2' else stage/'08_AGGREGATE/v3'
        for i,row in enumerate(rows[version],2):
            row['frozen_source_row']=row.get('original_source_row') or row.get('source_row');row['source_row']=str(target/'UNIQUE_EVALUATION_RESULTS.csv')+':'+str(i)
        for b in bias[version]:
            b['source_row']=next(r['source_row'] for r in rows[version] if (r['dataset_id'],r['variant_id'],r['method_id'])==(b['dataset_id'],b['variant_id'],b['method_id']))
        for d in ['BY2H','BY2O']:
            subset=[r for r in rows[version] if r['dataset_id']==d];bs=[r for r in bias[version] if r['dataset_id']==d];ss=[r for r in segments[version] if r['dataset_id']==d]
            path=stage/d/'08_AGGREGATE' if version=='v2' else stage/d/'08_AGGREGATE/v3';write_tables(path,subset,bs,ss,{})
        write_tables(target,rows[version],bias[version],segments[version],{})
    confounds={d:spec['sequences'][d].get('decomposition_confound','NONE') for d in ['BY2H','BY2O']};primary,byversion=decomposition(rows,confounds)
    _csv(stage/'08_AGGREGATE/PARITY_GENERALIZATION.csv',primary);_csv(stage/'08_AGGREGATE/PARITY_DECOMPOSITION_BY_VERSION.csv',byversion)
    remap_rows=[]
    for dataset,bundle in bundles.items():
        remap=bundle['rv_remap_audit']
        remap_rows.extend({'dataset_id':dataset,**r} for r in remap['changed_rows'])
    _csv(stage/'08_AGGREGATE/RV_REASSIGNMENT_ROWS.csv',remap_rows)
    write_json(stage/'08_AGGREGATE/FROZEN_V0_ORIGINAL_FIELDS.json',raw_v0)
    complete=all(g['status']=='COMPLETED' for g in gates) and invocations==18
    result={'status':'COMPLETED' if complete else 'PARTIAL','code_commit':code_commit,'new_solver_count':8,'evaluator_invocation_count':invocations,'planned_evaluator_invocation_count':18,
        'run_gates':gates,'rows':rows,'body_frame_bias':bias,'segments':segments,'generalization':primary,'decomposition_by_version':byversion,'rv_reassignment_rows':remap_rows,'time_term_footnote':'时标项含 RV 同历元重配','data_mode':'real_raw_multisequence','synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False,'fit_used':False,'epoch_deleted_for_metric':False,'reference_velocity_supported':False}
    write_json(stage/'08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json',result)
    write_json(stage/'08_AGGREGATE/v3/FINAL_EVALUATION_SUMMARY.json',{'status':result['status'],'code_commit':code_commit,'evaluator_contract':'evaluator_contract_v3','rows':rows['v3'],'body_frame_bias':bias['v3'],'full_summary':'../FINAL_EVALUATION_SUMMARY.json'})
    for d in ['BY2H','BY2O']:
        selected_gates=[g for g in gates if g['dataset_id']==d]
        index={'status':'COMPLETED' if all(g['status']=='COMPLETED' for g in selected_gates) else 'PARTIAL','dataset_id':d,'code_commit':code_commit,
            'window_seconds':spec['sequences'][d]['window_seconds'],'base_time':spec['sequences'][d]['base_time'],'evaluator_sha256':EVALUATOR_SHA256,
            'new_solver_count':4,'evaluator_invocation_count':sum(g['evaluation_invoked'] for g in selected_gates),'run_gates':selected_gates,
            'rows':{v:[r for r in rows[v] if r['dataset_id']==d] for v in rows},'body_frame_bias':{v:[r for r in bias[v] if r['dataset_id']==d] for v in bias},
            'global_summary':'../../08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json','data_mode':registry.sequences[d].data_mode,'synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False}
        write_json(stage/d/'08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json',index)
        write_json(stage/d/'08_AGGREGATE/v3/FINAL_EVALUATION_SUMMARY.json',{'status':index['status'],'dataset_id':d,'code_commit':code_commit,'evaluator_contract':'evaluator_contract_v3','rows':index['rows']['v3'],'body_frame_bias':index['body_frame_bias']['v3'],'full_summary':'../FINAL_EVALUATION_SUMMARY.json'})
    for pin in references+[spec['reference_by2_summary']]:pinned(pin,registry)
    return result
