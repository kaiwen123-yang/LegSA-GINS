"""All nine noise cells, both point contracts, without ranking or adoption."""
from pathlib import Path
import numpy as np
from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_parity.evaluation import transform_nav,write_transformed_nav,body_frame_bias,_csv
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256,evaluate
from ..clean5_parity_p04.evaluation import metrics
from ..manifest import sha256_file
from .runtime import write_json,resolve,grid_cells


def pinned(pin,registry):
    p=resolve(pin['path'],registry)
    if p.is_symlink() or sha256_file(p)!=pin['sha256']:raise ValueError('Source pin changed: '+str(p))
    return p


def consistency(errors,std):
    t=np.asarray(errors.time,float);st=std[:,0]
    if np.any(np.diff(st)<=0):raise ValueError('Nonmonotonic STD times')
    idx=np.searchsorted(st,t);idx=np.clip(idx,0,len(st)-1)
    prev=np.maximum(idx-1,0);idx=np.where(abs(st[prev]-t)<abs(st[idx]-t),prev,idx)
    if np.any(abs(st[idx]-t)>1e-7):raise ValueError('STD error epochs differ')
    out={}
    for name,col,j in [('height','err_u_m',3),('north','err_n_m',1),('east','err_e_m',2),('yaw','yaw_err_deg',9)]:
        den=std[idx,j];e=np.asarray(errors[col],float)
        valid=np.isfinite(den)&(den>0)&np.isfinite(e)
        out.update({name+'_consistency_total_count':len(e),name+'_consistency_valid_count':int(valid.sum()),name+'_std_nonfinite_count':int((~np.isfinite(den)).sum()),name+'_std_nonpositive_count':int((np.isfinite(den)&(den<=0)).sum()),name+'_error_nonfinite_count':int((~np.isfinite(e)).sum())})
        out[name+'_abs_error_over_std_median']=float(np.median(abs(e)/den)) if valid.all() and len(e) else 'UNAVAILABLE'
    return out


def directional_endpoints(rows):
    """Six preregistered min-to-max comparisons; no outcome-driven choice."""
    out=[]
    for axis,other,values in [('abstd_mGal','vrw_mps_sqrt_hour',[.077,.77,7.7]),('vrw_mps_sqrt_hour','abstd_mGal',[77.8,778.,7780.])]:
        for fixed in values:
            subset=sorted([r for r in rows if r[other]==fixed],key=lambda r:r[axis])
            if len(subset)!=3:raise ValueError('Incomplete sensitivity grid')
            a,b=subset[0],subset[-1]
            row={'varied_parameter':axis,'fixed_parameter':other,'fixed_value':fixed,'from_value':a[axis],'to_value':b[axis],
                 'from_source_row':a['source_row'],'to_source_row':b['source_row'],'evaluator_contract':'evaluator_contract_v2'}
            for key in ['height_abs_error_over_std_median','up_rmse_m','yaw_rmse_deg']:row['from_'+key]=a.get(key,'UNAVAILABLE');row['to_'+key]=b.get(key,'UNAVAILABLE')
            out.append(row)
    return out


def evaluate_grid(*,registry,contract,stage_root,records,code_commit):
    spec=contract['p05'];stage=Path(stage_root);cells=grid_cells(contract)
    if len(records)!=9 or [r['variant_id'] for r in records]!=[c['cell_id'] for c in cells] or any(r['terminal_status']!='COMPLETED' for r in records):raise ValueError('All nine completed cells required')
    evaluator=pinned(spec['evaluator'],registry);trace=pinned(spec['trace'],registry)
    if sha256_file(evaluator)!=EVALUATOR_SHA256:raise ValueError('Evaluator identity')
    root=stage/'07_OFFLINE_EVALUATION';root.mkdir(exist_ok=False);rows={v:[] for v in ['v2','v3']};bias={v:[] for v in rows};invocations=0;aborted=None
    for job in records:
        navpath=Path(job['nav_path']);stdpath=Path(job['std_path'])
        if sha256_file(navpath)!=job['nav_sha256'] or sha256_file(stdpath)!=job['std_sha256']:raise ValueError('Sealed source mismatch')
        nav=canonical._read_numeric_table(navpath).to_numpy(float);std=canonical._read_numeric_table(stdpath).to_numpy(float)
        for version in rows:
            identity={k:job[k] for k in ['run_id','variant_id','method_id','dataset_id','abstd_mGal','vrw_mps_sqrt_hour','classification','explicit_noise_sensitivity','non_grid_parameter_hash','actual_parameter_hash','no_best_selection','no_feedback','no_adoption','parameter_sweep','frozen_parameter_contract','parameter_selection_used']}
            identity.update(evaluator_contract='evaluator_contract_'+version,code_commit=code_commit,data_mode='real_by2_raw',synthetic_data_used=False,semisynthetic_data_used=False,trace_used_online=False,evaluator_sha256=EVALUATOR_SHA256)
            receipt=root/version/'RECEIPTS'/job['run_id'];receipt.mkdir(parents=True,exist_ok=False)
            write_json(receipt/'EVAL_STARTED.json',{**identity,'evaluator_invocation_count_before':invocations,'prior_failure':aborted})
            before=invocations
            try:
                actual=navpath
                if aborted:raise RuntimeError('NOT_EXECUTED_AFTER_EVALUATION_FAILURE: '+aborted)
                if version=='v3':
                    directory=root/'v3/NAV_INPUTS'/job['run_id'];directory.mkdir(parents=True,exist_ok=False);actual=directory/'EVALUATOR_INPUT.nav'
                    write_transformed_nav(navpath,actual,transform_nav(nav,spec['baseline_median_m']))
                    write_json(directory/'TRANSFORM_MANIFEST.json',{**identity,'source_nav_sha256':job['nav_sha256'],'output_sha256':sha256_file(actual),'baseline_median_m':spec['baseline_median_m'],'lever_frd_m':[.03,.03-spec['baseline_median_m']/2,-.30],'fit_used':False,'further_correction_used':False,'full_covariance':'UNAVAILABLE'})
                directory=root/version/'PER_RUN'/job['run_id'];invocations+=1
                ev=evaluate(evaluator=evaluator,trace=trace,nav=actual,std=stdpath,outdir=directory,base_time=spec['base_time'],window=spec['window_seconds'],trace_sha256=spec['trace']['sha256'],code_root=registry.code_root,raw_root=registry.raw_root,clean_root=registry.clean_root)
                cap=ev['capture']
                if cap.get('consistency',{}).get('passed') is not True or cap.get('selected_columns')!={'time':'time','lat':'lat','lon':'lon','height':'height','roll':'roll','pitch':'pitch','yaw':'yaw'}:raise ValueError('Evaluator capture failure')
                errors=canonical._read_error_series(directory);row=metrics(errors,nav,identity,spec['window_seconds'],cap['reference_epoch_count'])
                row['yaw_p95_deg']=row['yaw_p95_absolute_deg']
                row.update(consistency(errors,std),error_series_source=str(directory),source_nav_sha256=job['nav_sha256'],source_std_sha256=job['std_sha256'],evaluation_invoked=True,
                    consistency_status='SAME_POINT_STD' if version=='v2' else 'ORIGINAL_IMU_STD_DIAGNOSTIC_ONLY',full_covariance_status='NOT_REQUIRED' if version=='v2' else 'UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED',
                    yaw_consistency_status='UNCHANGED_YAW_STATE_STD',v3_std_transport='NOT_APPLICABLE' if version=='v2' else 'UNTRANSPORTED_STD_DIAGNOSTIC_ONLY')
                rows[version].append(row);bias[version].append({**identity,**body_frame_bias(errors,nav)})
                print('P05 EVAL',job['variant_id'],version,'COMPLETED',flush=True)
            except Exception as exc:
                aborted=aborted or str(exc)
                row={**identity,'evaluation_status':'UNAVAILABLE','unavailable_reason':str(exc),**{key:'UNAVAILABLE' for key in ['horizontal_rmse_m','position_3d_rmse_m','up_rmse_m','yaw_rmse_deg','yaw_p95_deg','height_abs_error_over_std_median','north_abs_error_over_std_median','east_abs_error_over_std_median','yaw_abs_error_over_std_median']}}
                rows[version].append(row);bias[version].append({**identity,'status':'UNAVAILABLE','reason':str(exc)})
            write_json(receipt/'EVAL_TERMINAL.json',{'row':rows[version][-1],'evaluator_invoked':invocations>before,'actual_invocation_count':invocations,'completed_rows':rows,'failure':aborted})
        if sha256_file(navpath)!=job['nav_sha256'] or sha256_file(stdpath)!=job['std_sha256']:raise ValueError('Source outputs changed')
    complete=invocations==18 and aborted is None and all(r['evaluation_status']=='COMPLETED' for rr in rows.values() for r in rr)
    for version in rows:
        target=stage/'08_AGGREGATE' if version=='v2' else stage/'08_AGGREGATE/v3';target.mkdir(parents=True,exist_ok=False)
        for i,row in enumerate(rows[version],2):row['source_row']=str(target/'SENSITIVITY_GRID.csv')+':'+str(i)
        _csv(target/'SENSITIVITY_GRID.csv',rows[version]);_csv(target/'UNIQUE_EVALUATION_RESULTS.csv',rows[version]);_csv(target/'BODY_FRAME_BIAS.csv',bias[version])
    endpoints=directional_endpoints(rows['v2']);_csv(stage/'08_AGGREGATE/DIRECTIONAL_ENDPOINTS.csv',endpoints)
    result={'status':'COMPLETED' if complete else 'PARTIAL','first_evaluation_failure':aborted,'classification':'SENSITIVITY_NOT_FROZEN','code_commit':code_commit,'solver_count':9,'evaluator_invocation_count':invocations,'rows':rows,'body_frame_bias':bias,'directional_endpoints':endpoints,'no_best_selection':True,'no_feedback':True,'no_adoption':True,'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False}
    write_json(stage/'08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json',result)
    return result
