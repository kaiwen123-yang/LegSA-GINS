"""Fifteen sealed calibrated runs; trace content is read only by archived evaluator children."""
from __future__ import annotations
import copy
from collections.abc import Mapping
import csv
import json
import yaml
from pathlib import Path
from ..manifest import sha256_file
from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_sequence.evaluation_process import evaluate,EVALUATOR_SHA256
from ..clean5_sequence.evaluation_tables import pairwise_rows,segment_rows,PAIRWISE_DEFINITIONS
from ..clean5_parity.evaluation import transform_nav,write_transformed_nav,body_frame_bias,_csv,full_window_segments
from ..clean5_parity.runtime import resolve,write_json
from ..clean5_parity_p04.evaluation import metrics
from ..clean5_parity_p05.evaluation import consistency

DATASETS=('BY2','BY2H','BY2O')
METHODS=('F01','F02','F03','A04','F04')
METRICS=('horizontal_rmse_m','position_3d_rmse_m','up_rmse_m','yaw_rmse_deg','yaw_p95_deg',
         'height_abs_error_over_std_median','north_abs_error_over_std_median','east_abs_error_over_std_median','yaw_abs_error_over_std_median')


def pinned(entry,registry):
    path=resolve(entry['path'],registry)
    # This helper is never permitted for raw reference files.
    if registry.raw_root in path.parents:raise ValueError('Raw payload pin hashing is not allowed in evaluation controller')
    if path.is_symlink() or sha256_file(path)!=entry['sha256']:raise ValueError('Frozen evaluation source changed')
    return path


def trace_metadata(entry,registry,dataset):
    path=resolve(entry['path'],registry)
    if path!=registry.sequences[dataset].trace_path or path.is_symlink() or not path.is_file():raise ValueError('Trace identity/path unavailable')
    if len(entry['sha256'])!=64 or any(x not in '0123456789abcdef' for x in entry['sha256']):raise ValueError('Invalid locked trace hash')
    return path


def identity(job,version,code_commit):
    row={k:job.get(k) for k in ['dataset_id','method_id','run_id','effective_profile','effective_configuration_id','case_id','variant_id','classification','model_sha256','provider_hashes','non_calibrated_parameter_hash','actual_parameter_hash']}
    row.update(evaluator_contract='evaluator_contract_'+version,code_commit=code_commit,data_mode='real_calibrated_raw',
        synthetic_data_used=False,semisynthetic_data_used=False,trace_used_online=False,evaluator_sha256=EVALUATOR_SHA256,
        classification='NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL',source_nav_sha256=job.get('nav_sha256'),source_std_sha256=job.get('std_sha256'),
        source_run_manifest=str(Path(job['output_root'])/'CALIBRATED_RUN_MANIFEST.json') if job.get('output_root') else 'UNAVAILABLE',
        solver_terminal_status=job.get('terminal_status','NOT_EXECUTED'),wrapper_runtime_seconds=job.get('runtime_seconds'),wrapper_exit_code=job.get('exit_code'),
        reference_is_independent_ground_truth=False,reference_velocity_supported=False,no_parameter_selection=True,no_feedback=True)
    row['actual_parameter_hash']=job.get('actual_parameter_hash',job.get('frozen_parameter_hash'))
    row['reference_frozen_parameter_hash']=job.get('reference_frozen_parameter_hash')
    counters=job.get('counters',{})
    if isinstance(counters,Mapping):row.update(counters);row['counter_status']='AVAILABLE'
    else:row['counter_status']=str(counters)
    return row


def write_tables(target,rows,bias,segments):
    target=Path(target);target.mkdir(parents=True,exist_ok=False)
    cases=[];summaries=[]
    for dataset in DATASETS:
        selected=[r for r in rows if r['dataset_id']==dataset]
        if not selected:continue
        pc,ps=pairwise_rows(selected)
        lookup={r['method_id']:r for r in selected}
        for r in pc:
            r.update(dataset_id=dataset,evaluator_contract=selected[0]['evaluator_contract'],
                candidate_source_row=lookup[r['candidate_method_id']]['source_row'],reference_source_row=lookup[r['reference_method_id']]['source_row'])
        for r in ps:r.update(dataset_id=dataset,evaluator_contract=selected[0]['evaluator_contract'])
        cases.extend(pc);summaries.extend(ps)
    available=[r for r in rows if r['evaluation_status']=='COMPLETED']
    tables={'UNIQUE_EVALUATION_RESULTS.csv':rows,'LOGICAL_EVALUATION_RESULTS.csv':rows,
        'PAIRWISE_CASE_LEVEL.csv':cases,'PAIRWISE_SUMMARY.csv':summaries,
        'BODY_FRAME_BIAS.csv':bias,'WINDOW_SEGMENT_SUMMARY.csv':segments}
    for name in ['UNIQUE_METHOD_SUMMARY.csv','LOGICAL_METHOD_SUMMARY.csv']:
        tables[name]=canonical._summary_rows(available,('dataset_id','method_id'),canonical._numeric_fields(available)) if available else []
    tables['MODULE_ACTION_SUMMARY.csv']=canonical._summary_rows(available,('dataset_id','method_id'),[m for m in canonical.MODULE_SCALARS if any(m in r for r in available)]) if available else []
    tables['RUNTIME_SUMMARY.csv']=canonical._summary_rows(rows,('dataset_id','method_id'),['wrapper_runtime_seconds','evaluation_runtime_seconds'])
    tables['METRIC_COVERAGE_REPORT.csv']=canonical._coverage_report(rows)
    for name,rr in tables.items():_csv(target/name,rr)
    write_json(target/'FIELD_DEFINITIONS.json',{'classification':'NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL',
        'pairwise_definitions':PAIRWISE_DEFINITIONS,'logical_registry':'five one-to-one calibrated profile rows; no extra aliases',
        'v3_position_consistency':'ORIGINAL_IMU_STD_DIAGNOSTIC_ONLY; UNTRANSPORTED_STD_DIAGNOSTIC_ONLY',
        'v3_full_covariance':'UNAVAILABLE','yaw_consistency':'UNCHANGED_YAW_STATE_STD','reference_payload_read_role':'archived evaluator child only',
        'outside_occlusion':'outside frozen main window; secondary interval remains included and counted'})


def frozen_sensor_rows(contract,registry):
    """Projection of committed model scalars only; no fitting or arithmetic."""
    entry=contract['model'];model=yaml.safe_load(pinned(entry,registry).read_text());rows=[]
    for axis in model['axis_order']:
        source=model['axes'][axis]
        rows.append({'axis':axis,'status':source['status'],'s':model['s'],'g_local_mps2':model['g_local_mps2'],
            'vrw_mps_sqrt_hour':source['vrw_mps_sqrt_hour'],'abstd_mGal':source['abstd_mGal'],
            'q_m2ps3':source['q_m2ps3'],'c_m2ps2':source['c_m2ps2'],'nonempty_window_count':source['nonempty_window_count'],
            'ols_lag_count':source['ols_lag_count'],'model_source':entry['path'],'model_sha256':entry['sha256'],
            'source_fields':'/axes/'+axis+' plus /s and /g_local_mps2','refit_invoked':False})
    return rows


def frozen_main_references(contract,registry):
    """Copy five complete frozen scalar rows per sequence, preserving original fields."""
    selected=[]
    for dataset in DATASETS:
        ds=contract['sequences'][dataset];entry=ds['frozen_main_table'];path=pinned(entry,registry);matches={}
        with path.open(newline='') as handle:
            reader=csv.DictReader(handle);header=reader.fieldnames;previous=reader.line_num
            if not header or len(header)!=len(set(header)):raise ValueError('Invalid frozen main table header')
            for original in reader:
                first=previous+1;previous=reader.line_num
                if original.get('case_id')!=ds['case_id'] or original.get('method_id') not in METHODS:continue
                method=original['method_id']
                if method in matches:raise ValueError('Duplicate frozen main method')
                if original.get('evaluation_status')!='COMPLETED':raise ValueError('Frozen main result not completed')
                row=dict(original)
                additions={'frozen_reference_dataset_id':dataset,'frozen_reference_evaluator_contract':'evaluator_contract_v2',
                    'frozen_reference_source_row':entry['path']+':'+str(first),'frozen_reference_source_row_end':reader.line_num,
                    'frozen_reference_source_sha256':entry['sha256'],'frozen_reference_reused':True,'calibrated_reference_evaluator_invoked':False}
                if set(additions)&set(original):raise ValueError('Reference provenance field collision')
                row.update(additions);matches[method]=row
        if set(matches)!=set(METHODS):raise ValueError('Frozen main five-profile identity incomplete')
        selected.extend(matches[m] for m in METHODS)
    return selected


def external_references(contract,registry):
    """Frozen scalar rows only, no external NAV or evaluator invocation."""
    spec=contract['external_by2_v3'];source=pinned(spec['results'],registry)
    with source.open(newline='') as handle:table=list(csv.DictReader(handle))
    selected=[]
    for method in ['EXT05C','LC01']:
        candidates=[(i,r) for i,r in enumerate(table,2) if r['method_id']==method and r.get('evaluator_contract')=='evaluator_contract_v3']
        if len(candidates)!=1:raise ValueError('External BY2 v3 identity unavailable')
        line,original=candidates[0];r=copy.deepcopy(original)
        r.update(reference_reused=True,calibrated_evaluator_invoked=False,frozen_results_source=spec['results'],
            frozen_source_row=spec['results']['path']+':'+str(line))
        selected.append(r)
    return selected


def evaluate_chain(*,registry,contract,stage_root,records,bundles,code_commit):
    stage=Path(stage_root)
    expected=[(d,m) for d in DATASETS for m in METHODS]
    if len(records)!=15 or [(r['dataset_id'],r['method_id']) for r in records]!=expected or any(r['terminal_status']!='COMPLETED' for r in records):raise ValueError('Exactly fifteen completed sealed runs required')
    evaluator=pinned(contract['evaluator'],registry)
    if contract['evaluator']['sha256']!=EVALUATOR_SHA256:raise ValueError('Evaluator identity mismatch')
    sensor_rows=frozen_sensor_rows(contract,registry)
    frozen_main=frozen_main_references(contract,registry)
    externals=external_references(contract,registry)
    root=stage/'07_OFFLINE_EVALUATION';root.mkdir(parents=True,exist_ok=False)
    rows={v:[] for v in ['v2','v3']};bias={v:[] for v in rows};segments={v:[] for v in rows};invocations=0;aborted=None
    for job in records:
        dataset=job['dataset_id'];ds=contract['sequences'][dataset];window=ds['window_seconds'];wd={'t_start':window[0],'t_end':window[1]}
        trace=trace_metadata(ds['trace'],registry,dataset);baseline=float(ds['baseline_median_m'])
        if baseline!=float(bundles[dataset]['baseline_median_m']):raise ValueError('Frozen baseline identity mismatch')
        navpath=Path(job['nav_path']);stdpath=Path(job['std_path'])
        if sha256_file(navpath)!=job['nav_sha256'] or sha256_file(stdpath)!=job['std_sha256']:raise ValueError('Sealed NAV/STD changed')
        nav=canonical._read_numeric_table(navpath).to_numpy(float);std=canonical._read_numeric_table(stdpath).to_numpy(float)
        for version in rows:
            base=identity(job,version,code_commit);before=invocations;receipt=root/version/'RECEIPTS'/job['run_id'];receipt.mkdir(parents=True,exist_ok=False)
            write_json(receipt/'EVAL_STARTED.json',{**base,'invocation_count_before':invocations,'prior_failure':aborted})
            try:
                if aborted:raise RuntimeError('NOT_EXECUTED_AFTER_EVALUATION_FAILURE: '+aborted)
                actual=navpath
                if version=='v3':
                    directory=root/'v3/NAV_INPUTS'/job['run_id'];directory.mkdir(parents=True,exist_ok=False);actual=directory/'EVALUATOR_INPUT.nav'
                    write_transformed_nav(navpath,actual,transform_nav(nav,baseline))
                    write_json(directory/'TRANSFORM_MANIFEST.json',{**base,'input_sha256':job['nav_sha256'],'output_sha256':sha256_file(actual),'baseline_median_m':baseline,
                        'lever_frd_m':[.03,.03-baseline/2,-.30],'fit_used':False,'further_correction_used':False,'full_covariance':'UNAVAILABLE'})
                directory=root/version/'PER_RUN'/job['run_id'];invocations+=1
                if invocations>30:raise ValueError('Evaluator invocation limit')
                result=evaluate(evaluator=evaluator,trace=trace,nav=actual,std=stdpath,outdir=directory,base_time=ds['base_time'],window=window,
                    trace_sha256=ds['trace']['sha256'],code_root=registry.code_root,raw_root=registry.raw_root,clean_root=registry.clean_root)
                capture=result['capture']
                if capture.get('selected_columns')!={'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'} or capture.get('consistency',{}).get('passed') is not True:raise ValueError('Evaluator capture gate failure')
                errors=canonical._read_error_series(directory);row=metrics(errors,nav,base,window,capture['reference_epoch_count'])
                row.update(consistency(errors,std),evaluation_invoked=True,evaluation_runtime_seconds=result['runtime_seconds'],error_series_source=str(directory),
                    yaw_p95_deg=row['yaw_p95_absolute_deg'],consistency_status='SAME_POINT_STD' if version=='v2' else 'ORIGINAL_IMU_STD_DIAGNOSTIC_ONLY',
                    v3_std_transport='NOT_APPLICABLE' if version=='v2' else 'UNTRANSPORTED_STD_DIAGNOSTIC_ONLY',yaw_consistency_status='UNCHANGED_YAW_STATE_STD')
                br={**base,**body_frame_bias(errors,nav),'status':'AVAILABLE'}
                if dataset=='BY2':sr=full_window_segments([row])
                else:sr=segment_rows(errors,registry=job,dataset_id=dataset,window=wd,case_meta=ds['case_meta'])
                segments[version].extend({**r,'evaluator_contract':'evaluator_contract_'+version} for r in sr)
            except Exception as exc:
                aborted=aborted or str(exc);row={**base,'evaluation_status':'UNAVAILABLE','unavailable_reason':str(exc),'evaluation_invoked':invocations>before,**{k:'UNAVAILABLE' for k in METRICS}};br={**base,'status':'UNAVAILABLE','reason':str(exc)}
            rows[version].append(row);bias[version].append(br)
            write_json(receipt/'EVAL_TERMINAL.json',{'row':row,'body_frame_bias':br,'evaluator_invoked':invocations>before,'actual_invocation_count':invocations,'failure':aborted})
            print('CALIBRATED EVAL',dataset,job['method_id'],version,row['evaluation_status'],flush=True)
        if sha256_file(navpath)!=job['nav_sha256'] or sha256_file(stdpath)!=job['std_sha256']:raise ValueError('Source NAV/STD changed during evaluation')
    for version in rows:
        target=stage/'08_AGGREGATE' if version=='v2' else stage/'08_AGGREGATE/v3'
        for i,r in enumerate(rows[version],2):r['source_row']=str(target/'UNIQUE_EVALUATION_RESULTS.csv')+':'+str(i)
        for i,r in enumerate(segments[version],2):r['source_row']=str(target/'WINDOW_SEGMENT_SUMMARY.csv')+':'+str(i)
        for b in bias[version]:b['source_row']=next(r['source_row'] for r in rows[version] if r['run_id']==b['run_id'])
        write_tables(target,rows[version],bias[version],segments[version])
        for dataset in DATASETS:
            target=stage/dataset/'08_AGGREGATE' if version=='v2' else stage/dataset/'08_AGGREGATE/v3'
            write_tables(target,[r for r in rows[version] if r['dataset_id']==dataset],[r for r in bias[version] if r['dataset_id']==dataset],[r for r in segments[version] if r['dataset_id']==dataset])
    _csv(stage/'08_AGGREGATE/v3/EXTERNAL_BY2_V3_REFERENCE.csv',externals)
    _csv(stage/'08_AGGREGATE/FROZEN_MAIN_REFERENCE.csv',frozen_main)
    _csv(stage/'08_AGGREGATE/FROZEN_SENSOR_MODEL.csv',sensor_rows)
    if frozen_main_references(contract,registry)!=frozen_main or external_references(contract,registry)!=externals:raise ValueError('Frozen reference rows changed')
    complete=invocations==30 and aborted is None
    summary={'status':'COMPLETED' if complete else 'PARTIAL','classification':'NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL','code_commit':code_commit,
        'new_solver_count':15,'evaluator_invocation_count':invocations,'planned_evaluator_invocation_count':30,'rows':rows,'body_frame_bias':bias,'segments':segments,'external_by2_v3':externals,
        'frozen_main_reference':frozen_main,'first_evaluation_failure':aborted,'trace_read_role':'archived_evaluator_child_only','controller_trace_payload_reads':0,'data_mode':'real_calibrated_raw',
        'synthetic_data_used':False,'semisynthetic_data_used':False,'no_parameter_selection':True,'no_feedback':True}
    write_json(stage/'08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json',summary)
    if complete:
        from .robustness import robustness_check
        summary['robustness']=robustness_check(registry=registry,contract=contract,stage_root=stage)
    return summary


def evaluate_failure_tables(*,registry,contract,stage_root,records,code_commit,reason):
    """Early-gate failures still report all 15 identities; existing tables are immutable."""
    stage=Path(stage_root);lookup={(r['dataset_id'],r['method_id']):r for r in records};files=[]
    for version in ['v2','v3']:
        rows=[]
        for dataset in DATASETS:
            for method in METHODS:
                job=lookup.get((dataset,method),{'dataset_id':dataset,'method_id':method,'run_id':f'CLEAN5_CALIBRATED_{dataset}_{method}','case_id':'C00_clean_normal' if dataset=='BY2' else f'CLEAN5_{dataset}_NATURAL'})
                r={**identity(job,version,code_commit),'evaluation_status':'UNAVAILABLE','evaluation_invoked':False,'unavailable_reason':reason,**{k:'UNAVAILABLE' for k in METRICS}}
                receipt=stage/'07_OFFLINE_EVALUATION'/version/'RECEIPTS'/job['run_id']/'EVAL_TERMINAL.json'
                if receipt.exists():r.update(json.loads(receipt.read_text())['row'])
                rows.append(r)
        for dataset in [None,*DATASETS]:
            target=(stage/dataset if dataset else stage)/'08_AGGREGATE'
            if version=='v3':target=target/'v3'
            target.mkdir(parents=True,exist_ok=True)
            for name in ['UNIQUE_EVALUATION_RESULTS.csv','LOGICAL_EVALUATION_RESULTS.csv']:
                path=target/name
                if not path.exists():_csv(path,[r for r in rows if dataset is None or r['dataset_id']==dataset]);files.append(str(path))
    return {'status':'FAILURE_IDENTITIES_RECORDED','written_tables':files,'planned_run_count':15,'planned_evaluation_count':30}
