"""Evaluate six new P-03 outputs twice; copy frozen P-02 numerical evidence."""
from __future__ import annotations
import copy
import json
from pathlib import Path

from ..manifest import sha256_file
from ..clean5_parity.evaluation import (canonical,canonical_headers,EVALUATOR_SHA256,evaluate,
    transform_nav,write_transformed_nav,body_frame_bias,_metrics,_csv,write_json,write_version_tables)
from ..clean5_parity.decomposition import difference, METRICS
from .runtime import resolve,run_order


def append_decomposition(original, rows_by_version, *, selected_variant):
    if selected_variant!='V2is':raise ValueError('P03 selected variant must be preregistered V2is; no metric selection')
    result=copy.deepcopy(original)
    for version,rows in rows_by_version.items():
        index={(r['variant_id'],r['method_id']):r for r in rows}
        if len(index)!=len(rows):raise ValueError('Duplicate decomposition endpoint')
        for method in ('F03','A04'):
            for term,variant in (('imu_handling','V2i'),('accel_scale','V2s'),('combined_imu_handling_and_scale','V2is')):
                delta=difference(f'{term}:{method}:{version}',index.get(('V2',method)),index.get((variant,method)))
                delta['evaluator_contract']='evaluator_contract_'+version;result.append(delta)
        delta=difference('F01_upper:V2F01-EXT05C:'+version,index.get(('V2','F01')),index.get(('EXTERNAL','EXT05C')))
        delta['evaluator_contract']='evaluator_contract_'+version;result.append(delta)
        if version=='v3':
            delta=difference('residual:preregistered_V2isA04-EXT05C:v3',index.get((selected_variant,'A04')),index.get(('EXTERNAL','EXT05C')))
            delta.update(evaluator_contract='evaluator_contract_v3',selected_variant=selected_variant,
                         selection_basis='preregistered V2i applicability; never metrics')
            result.append(delta)
    return result


def assert_frozen_numbers(original, copied):
    if len(original)!=len(copied):raise ValueError('Frozen row count changed')
    for old,new in zip(original,copied):
        if old['run_id']!=new['run_id']:raise ValueError('Frozen row order changed')
        for key,value in old.items():
            if isinstance(value,(int,float)) and new.get(key)!=value:
                raise ValueError('Frozen numeric field changed: '+old['run_id']+'/'+key)


def load_reference(registry,contract):
    root=resolve(contract['p03']['reference_stage_root'],registry)
    path=root/'08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json'
    if path.is_symlink() or sha256_file(path)!=contract['p03']['reference_summary_sha256']:
        raise ValueError('Frozen P02 final summary hash mismatch')
    summary=json.loads(path.read_text())
    for key,relative in (('reference_terminal_sha256','P02_FINAL_TERMINAL.json'),
            ('reference_provider_bundle_sha256','02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json'),
            ('reference_seal_sha256','04_PARITY_SEAL/PARITY_OUTPUT_SEAL_CONTINUED.json')):
        source=root/relative
        if source.is_symlink() or sha256_file(source)!=contract['p03'][key]:raise ValueError('P02 frozen identity mismatch: '+key)
    if summary['status']!='COMPLETED_WITH_V2E_NATIVE_FAILURE':raise ValueError('P02 reference is not final')
    if any(len(summary['rows'][v])!=13 for v in ('v2','v3')):raise ValueError('P02 reference rows differ')
    return summary,{'path':str(path),'sha256':sha256_file(path)}


def evaluate_ladder(*,registry,stage_root,contract,run_records,code_commit,baseline_median_m):
    stage=Path(stage_root);settings=contract['evaluation'];order=run_order(contract)
    if [(r['variant_id'],r['method_id']) for r in run_records]!=order or any(r['terminal_status']!='COMPLETED' for r in run_records):
        raise ValueError('All six sealed P03 runs must complete before evaluation')
    if settings['v2_sha256']!=EVALUATOR_SHA256 or settings['base_time']!=1772784000 or list(settings['window_seconds'])!=[66.,340.]:
        raise ValueError('Frozen evaluator/time identity mismatch')
    reference,reference_identity=load_reference(registry,contract)
    if reference['baseline_median_m']!=baseline_median_m or reference['trace_sha256']!=settings['trace_sha256']:
        raise ValueError('Frozen baseline/trace identity changed')
    evaluator=resolve(settings['evaluator_path'],registry);trace=registry.sequences['BY2'].trace_path
    out=stage/'08_AGGREGATE';evalroot=stage/'07_OFFLINE_EVALUATION'
    if out.exists() or evalroot.exists():raise FileExistsError('P03 evaluation already attempted; retry forbidden')
    out.mkdir();(out/'v3').mkdir();evalroot.mkdir()
    rows_by_version={v:copy.deepcopy(reference['rows'][v]) for v in ('v2','v3')}
    bias_by_version={v:copy.deepcopy(reference['body_frame_bias'][v]) for v in ('v2','v3')}
    for version in ('v2','v3'):
        for row in rows_by_version[version]:row['p02_source_row']=row.get('source_row');row['result_reused_from_P02']=True
        for row in bias_by_version[version]:row['result_reused_from_P02']=True
    gates=copy.deepcopy(reference['run_gates']);new_gates=[];invocations=0
    for record in run_records:
        root=Path(record['output_root']);navpath=Path(record['nav_path']);stdpath=Path(record['std_path'])
        if sha256_file(navpath)!=record['nav_sha256'] or sha256_file(stdpath)!=record['std_sha256']:
            raise ValueError('Sealed P03 NAV/STD changed')
        nav=canonical._read_numeric_table(navpath).to_numpy(float)
        for version in ('v2','v3'):
            identity={k:record.get(k) for k in ('variant_id','method_id','run_id','terminal_status','effective_profile','effective_configuration_id')}
            identity.update(dataset_id='BY2',case_id='C00_clean_normal',evaluator_contract='evaluator_contract_'+version,
                evaluator_sha256=EVALUATOR_SHA256,code_commit=code_commit,data_mode='real_by2_raw',synthetic_data_used=False,
                semisynthetic_data_used=False,trace_used_online=False,wrapper_runtime_seconds=record.get('runtime_seconds'),
                wrapper_exit_code=record.get('exit_code'),source_row='',evaluation_invoked=False,result_reused_from_P02=False)
            row=dict(identity);br=dict(identity)
            try:
                actual_nav=navpath
                if version=='v3':
                    derived=evalroot/'v3/NAV_INPUTS'/record['run_id'];derived.mkdir(parents=True,exist_ok=False)
                    actual_nav=derived/'EVALUATOR_INPUT.nav'
                    write_transformed_nav(navpath,actual_nav,transform_nav(nav,baseline_median_m))
                    write_json(derived/'TRANSFORM_MANIFEST.json',{'evaluator_contract':'evaluator_contract_v3',
                        'input_nav':str(navpath),'input_sha256':record['nav_sha256'],'output_sha256':sha256_file(actual_nav),
                        'baseline_median_m':baseline_median_m,'lever_frd_m':[.03,.03-.5*baseline_median_m,-.30],
                        'code_commit':code_commit,'data_mode':'real_by2_raw','synthetic_data_used':False,
                        'semisynthetic_data_used':False,'fit_used':False,'further_correction_used':False,
                        'uncertainty_status':'UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED'})
                directory=evalroot/version/'PER_RUN'/record['run_id']
                identity['evaluation_invoked']=True;row['evaluation_invoked']=True;br['evaluation_invoked']=True;invocations+=1
                evaluation=evaluate(evaluator=evaluator,trace=trace,nav=actual_nav,std=stdpath,outdir=directory,
                    base_time=settings['base_time'],window=[66.,340.],trace_sha256=settings['trace_sha256'],
                    code_root=registry.code_root,raw_root=registry.raw_root,clean_root=registry.clean_root)
                capture=evaluation['capture']
                expected={'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}
                if capture.get('selected_columns')!=expected or capture.get('consistency',{}).get('passed') is not True:
                    raise ValueError('Frozen evaluator capture gate failed')
                errors=canonical._read_error_series(directory)
                if version=='v2':
                    row={**canonical._compute_result(record,{},root,directory,capture['reference_epoch_count'],evaluation['runtime_seconds'],True),**identity}
                row=_metrics(errors,nav,row,capture['reference_epoch_count'])
                row.update(error_series_source=str(directory),source_nav_sha256=record['nav_sha256'],
                    evaluator_nav_sha256=sha256_file(actual_nav),evaluation_runtime_seconds=evaluation['runtime_seconds'])
                if version=='v3':row['uncertainty_status']='UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED'
                br.update(body_frame_bias(errors,nav),status='AVAILABLE',error_series_source=str(directory))
            except Exception as exc:
                row={**identity,'evaluation_status':'UNAVAILABLE','unavailable_reason':str(exc),**{m:'UNAVAILABLE' for m in METRICS}}
                br.update(status='UNAVAILABLE',unavailable_reason=str(exc))
            gate={'version':version,'run_id':record['run_id'],'status':row['evaluation_status'],'reason':row.get('unavailable_reason'),'evaluation_invoked':identity['evaluation_invoked']}
            new_gates.append(gate);gates.append(gate);rows_by_version[version].append(row);bias_by_version[version].append(br)
            print(f'P03 {version} {record["run_id"]}: {row["evaluation_status"]}',flush=True)
        if sha256_file(navpath)!=record['nav_sha256'] or sha256_file(stdpath)!=record['std_sha256']:
            raise RuntimeError('Source solver NAV/STD changed during evaluation')
    headers=canonical_headers(resolve(settings['canonical_attempt'],registry))
    for version in ('v2','v3'):
        write_version_tables(target=out if version=='v2' else out/'v3',rows=rows_by_version[version],bias=bias_by_version[version],headers=headers)
        assert_frozen_numbers(reference['rows'][version],rows_by_version[version][:13])
        assert_frozen_numbers(reference['body_frame_bias'][version],bias_by_version[version][:13])
    decomposition=append_decomposition(reference['decomposition'],rows_by_version,selected_variant='V2is')
    _csv(out/'PARITY_DECOMPOSITION.csv',decomposition)
    complete=sum(g['status']=='COMPLETED' for g in new_gates)
    result={'status':'COMPLETED_WITH_P02_V2E_UNAVAILABLE' if complete==12 else 'PARTIAL',
        'code_commit':code_commit,'evaluator_sha256':EVALUATOR_SHA256,'trace_sha256':settings['trace_sha256'],
        'baseline_median_m':baseline_median_m,'reference_summary':reference_identity,'new_evaluation_count':invocations,
        'planned_new_evaluation_count':12,'new_evaluation_gate_count':len(new_gates),
        'new_completed_evaluation_count':complete,'rows':rows_by_version,'body_frame_bias':bias_by_version,
        'run_gates':gates,'new_run_gates':new_gates,'decomposition':decomposition,'original_numeric_fields_unchanged':True,
        'solver_executions_in_evaluation':0,'fit_used':False,'further_correction_used':False,'selected_variant':'V2is',
        'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False}
    write_json(out/'FINAL_EVALUATION_SUMMARY.json',result)
    write_json(out/'v3/FINAL_EVALUATION_SUMMARY.json',{k:v for k,v in result.items() if k not in ('rows','body_frame_bias','decomposition')})
    if sha256_file(Path(reference_identity['path']))!=reference_identity['sha256']:raise RuntimeError('P02 frozen reference changed')
    return result
