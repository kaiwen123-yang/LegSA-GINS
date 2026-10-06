"""Derive complete all-case paired diagnostic results from sealed saved errors.
Never opens reference trace, invokes solver/evaluator, or changes science artifacts.
"""
from pathlib import Path
import csv,datetime,hashlib,json,math,shutil
import numpy as np
import pandas as pd
STAGE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_20261004T064538Z')
CODE=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
METRICS={'H':'horizontal_err_m','V':'err_u_m','3D':'position_3d_err_m','yaw':'yaw_err_deg'}
DOMAINS=('full','fault','recovery_0_5','recovery_5_10','recovery_10_30','all_post_outage')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def keys(frame):
    time=np.asarray(frame.time,float);key=np.rint(time*1e6).astype(np.int64)
    if len(set(key))!=len(key) or np.any(np.diff(key)<=0):raise ValueError('NONUNIQUE_OR_UNSORTED_MICROSECOND_KEYS')
    return key

def unique_run_ids(rows,expected_count=135):
    ids=[row['run_id'] for row in rows]
    if len(ids)!=expected_count or len(set(ids))!=expected_count:raise ValueError('RUN_COUNT_OR_DUPLICATE_ID')
    return set(ids)

def validate_error_frame(frame,original):
    key=keys(frame)
    if not set(key)<=set(original):raise ValueError('ERROR_SUPPORT_OUTSIDE_ORIGINAL')
    if not np.isfinite(frame[list(METRICS.values())].to_numpy(dtype=float)).all():raise ValueError('NONFINITE_ERROR_FRAME')
    return key

def domain_mask(key,meta,domain):
    start=int(round(meta['outage_start_s']*1e6));end=int(round(meta['outage_end_s']*1e6))
    if domain=='full':return (key>=66000000)&(key<=340000000)
    if domain=='fault':return (key>=start)&(key<end)
    if domain=='all_post_outage':return key>end
    low,high={'recovery_0_5':(0,5),'recovery_5_10':(5,10),'recovery_10_30':(10,30)}[domain]
    return (key>end+low*1000000)&(key<=end+high*1000000)

def rmse(values):
    values=np.asarray(values,float)
    if not len(values):return None
    if not np.isfinite(values).all():raise ValueError('NONFINITE_ERROR')
    return float(np.sqrt(np.mean(np.square(values))))

def endpoint_key(original,meta):
    inside=original[domain_mask(original,meta,'fault')]
    return int(inside[-1]) if len(inside) else None

def paired_frames(left,right,original,meta,domain):
    lk,rk=keys(left),keys(right);l=left.copy();r=right.copy();l.index=lk;r.index=rk
    common=np.intersect1d(lk,rk);common=common[domain_mask(common,meta,domain)]
    expected=int(domain_mask(original,meta,domain).sum())
    return l.loc[common],r.loc[common],common,expected

def save_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)

def main():
    plan=json.loads((STAGE/'PREREGISTRATION.json').read_text())
    native=json.loads((STAGE/'ALL_NATIVE_SEALED.json').read_text())
    complete=json.loads((STAGE/'CONTROLLER_COMPLETE.json').read_text())
    detail=json.loads((STAGE/'PAIRED_ANALYSIS_DETAIL_PREREGISTRATION.json').read_text())
    external=Path(__file__).resolve().parent
    launch=json.loads((STAGE/'CONTROLLER_LAUNCH.json').read_text())
    prepare=json.loads((STAGE/'PREPARE_AUDIT.json').read_text())
    admission=json.loads((STAGE/'ALL_135_NATIVE_LOADER_ADMISSION.json').read_text())
    controller=external/'run_claim_subset.py';prep_helper=external/'prepare_claim_subset.py';loader_helper=external/'verify_claim_subset_admission.py'
    assert Path(launch['controller']).resolve()==controller and sha(controller)==launch['controller_sha256']
    assert launch['preregistration_sha256']==sha(STAGE/'PREREGISTRATION.json')
    assert Path(prepare['prepare_helper']['path']).resolve()==prep_helper and sha(prep_helper)==prepare['prepare_helper']['sha256']
    assert sha(loader_helper)==admission['helper_sha256'] and admission['preregistration_sha256']==sha(STAGE/'PREREGISTRATION.json')
    control_pins={str(p):sha(p) for p in [controller,prep_helper,loader_helper,STAGE/'CONTROLLER_LAUNCH.json',
        STAGE/'CONTROLLER_COMPLETE.json',STAGE/'PREPARE_AUDIT.json',STAGE/'ALL_135_NATIVE_LOADER_ADMISSION.json',
        STAGE/'PREREGISTRATION.json',STAGE/'PAIRED_ANALYSIS_DETAIL_PREREGISTRATION.json',STAGE/'HV_AVAILABILITY_PREREGISTRATION.json']}
    prepared_pins={}
    for run in plan['runs']:
        assert len(run['children'])==1
        for child in run['children']:
            for pin in (child['config'],child['segment']):
                old=prepared_pins.setdefault(pin['path'],pin['sha256']);assert old==pin['sha256']
    for segment in plan['sequences']['BY2']['segments']:
        old=prepared_pins.setdefault(segment['path'],segment['sha256']);assert old==segment['sha256']
    for path,digest in prepared_pins.items():assert sha(path)==digest
    assert complete['status']=='ALL_135_NATIVE_AND_OFFLINE_COMPLETED'
    aggregate_before=sha(STAGE/'CORRECTED_RESULTS.json');native_before=sha(STAGE/'ALL_NATIVE_SEALED.json')
    assert complete['results_sha256']==aggregate_before and complete['native_seal_sha256']==native_before
    assert native['preregistration_sha256']==sha(STAGE/'PREREGISTRATION.json')==detail['preregistration_sha256']
    assert unique_run_ids(plan['runs'])==unique_run_ids(native['runs'])
    expected={r['run_id']:r for r in plan['runs']};assert len(expected)==135
    assert {r['run_id'] for r in native['runs']}==set(expected)
    for relative,digest in plan['source_snapshot_sha256'].items():
        assert sha(CODE/relative)==sha(STAGE/'SOURCE_SNAPSHOT'/relative)==digest
    for path,digest in plan['original_provider_and_config_pins'].items():assert sha(path)==digest
    assert sha(STAGE/'SOLVER')==plan['binary_sha256']
    for run in native['runs']:
        for child in run['children']:
            assert child['status']=='COMPLETED' and child['trace_open_count']==0 and child['bag_fpl_open_count']==0
            root=Path(child['output_root']);seal=json.loads((root/'OUTPUT_SEAL.json').read_text())
            for name,digest in seal['files'].items():assert sha(root/name)==digest
        root=STAGE/'COMBINED'/run['run_id'];seal=json.loads((root/'OUTPUT_SEAL.json').read_text())
        for name,digest in seal['files'].items():assert sha(root/name)==digest
    target=STAGE/'PUBLICATION';target.mkdir(exist_ok=False)
    original=np.loadtxt(plan['sequences']['BY2']['segments'][0]['path'],ndmin=2)[:,0][1:]
    original=np.rint(original*1e6).astype(np.int64);assert len(original)==56642 and np.all(np.diff(original)>0)
    frames={};own=[];identity=[];recompute=[];access=[];audits=[];native_rows=[]
    for run in native['runs']:
        child=run['children'][0];health=child['covariance_health']
        native_rows.append({'run_id':run['run_id'],'case_id':run['case_id'],'method_id':run['method_id'],
            'data_mode':'semisynthetic','semisynthetic_data_used':True,'synthetic_data_used':False,
            'status':run['status'],'output_epochs':run['output_epochs'],'original_denominator':56642,
            'native_trace_open_count':run['trace_open_count'],'gap_restart_count':run['gap_restart_count'],
            'wrapper_runtime_seconds':child['runtime_seconds'],'runtime_scope':'Includes strace, source/input verification and covariance checks; not online worst latency',
            'saved_full_P_epochs':health['saved_full_P_epochs'],'min_active_15_eigenvalue':health['min_active_15_eigenvalue'],
            'active15_PSD_at_saved_boundaries':health['active_15_PSD_at_recorded_boundaries'],
            'frozen_scale_blocks_exact_zero':health['frozen_scale_blocks_exactly_zero']})
    raw_aggregate=json.loads((STAGE/'CORRECTED_RESULTS.json').read_text())
    assert unique_run_ids(raw_aggregate)==set(expected)
    recorded={r['run_id']:r for r in raw_aggregate}
    assert set(recorded)==set(expected)
    for rid,run in expected.items():
        root=STAGE/'EVALUATION'/rid
        result_before=sha(root/'EVALUATION_RESULT.json')
        error_before=sha(root/'FROZEN_EVALUATOR/error_series.csv') if (root/'FROZEN_EVALUATOR/error_series.csv').exists() else None
        result=json.loads((root/'EVALUATION_RESULT.json').read_text())
        row=result['row'];transport=result['transport'];audit=transport['audit'];capture=transport['capture']
        assert recorded[rid]==row
        accepted=row['status']=='COMPLETED_SEGMENTED'
        assert row['run_id']==rid and row['method_id']==run['method_id'] and row['sequence_id']=='BY2'
        if accepted:
            assert audit['passed'] is True and capture['consistency']['passed'] is True
            assert audit['trace_open_count']==1 and audit['bag_open_count']==audit['fpl_open_count']==0
            assert capture['trace_sha256']==plan['sequences']['BY2']['trace_sha256']
            assert capture['trace_handle_hash_count']==1
        else:assert row['status'].startswith('UNAVAILABLE_')
        identity.append({**row,'case_id':run['case_id'],'degradation_type_id':run['case_meta']['degradation_type_id'],
            'duration_s':run['case_meta']['duration_s'],'seed_index':run['case_meta']['seed_index'],
            'data_mode':'semisynthetic','semisynthetic_data_used':True,'synthetic_data_used':False,
            'source_run_id':run['source_run_id'],'protocol_id':plan['protocol_id'],
            'stage_path':str(STAGE),'reference_quantity':'Commercial fused Euler attitude; native origin position transformed by frozen V3 recipe',
            'independent_accuracy_claim':False,'uncertainty_transport_established':False})
        access.append({'run_id':rid,'case_id':run['case_id'],'native_trace_open_count':0,
            'offline_trace_open_count':audit['trace_open_count'],'trace_handle_hash_count':capture['trace_handle_hash_count'],
            'offline_access_passed':audit['passed'],'consistency_passed':capture['consistency']['passed']})
        frame=(pd.read_csv(root/'FROZEN_EVALUATOR/error_series.csv') if accepted else pd.DataFrame(columns=['time',*METRICS.values()]))
        k=validate_error_frame(frame,original)
        if accepted:assert len(frame)==row['matched_epochs']
        frames[rid]=frame
        for metric,column in (METRICS.items() if accepted else []):
            value=rmse(frame[column]);key={'H':'H_RMSE_m','V':'V_RMSE_m','3D':'3D_RMSE_m','yaw':'yaw_RMSE_deg'}[metric]
            diff=abs(value-row[key]);assert diff<1e-10
            recompute.append({'run_id':rid,'metric':metric,'recorded':row[key],'recomputed':value,'abs_difference':diff})
        for domain in DOMAINS:
            used=frame.loc[domain_mask(k,run['case_meta'],domain)];count=int(domain_mask(original,run['case_meta'],domain).sum())
            summary={'run_id':rid,'case_id':run['case_id'],'method_id':run['method_id'],'domain':domain,
                'original_measured_epoch_denominator':count,'matched_epochs':len(used),'unmatched_original_epochs':count-len(used),
                'support_fraction':len(used)/count if count else None,'status':('COMPLETED' if len(used) else 'EMPTY_DOMAIN') if accepted else 'UNAVAILABLE_ADMISSION_FAILED'}
            for metric,column in METRICS.items():summary[metric+'_RMSE']=rmse(used[column])
            own.append(summary)
        audits.append({'run_id':rid,'error_series_sha256':error_before,
                       'evaluation_result_sha256':result_before})
    by_key={(r['case_id'],r['method_id']):r for r in plan['runs']};paired=[]
    for case in sorted({r['case_id'] for r in plan['runs']}):
        full=by_key[case,'F04'];meta=full['case_meta'];left=frames[full['run_id']]
        for method in ('A03','A06'):
            other=by_key[case,method];right=frames[other['run_id']]
            for domain in DOMAINS:
                l,r,common,count=paired_frames(left,right,original,meta,domain)
                for metric,column in METRICS.items():
                    a,b=rmse(l[column]),rmse(r[column]);delta=a-b if a is not None and b is not None else None
                    paired.append({'case_id':case,'family':meta['degradation_type_id'],'duration_s':meta['duration_s'],
                        'seed_index':meta['seed_index'],'anchor_time_s':meta['anchor_time_s'],'ablation_method':method,
                        'domain':domain,'metric':metric,'unit':'deg' if metric=='yaw' else 'm',
                        'full_value':a,'ablation_value':b,'delta_full_minus_ablation':delta,
                        'common_epochs':len(common),'original_measured_epoch_denominator':count,
                        'missing_common_epochs':count-len(common),'endpoint_key_us':None,
                        'outcome':'UNAVAILABLE' if delta is None else 'TIE' if abs(delta)<=1e-12 else 'IMPROVED' if delta<0 else 'WORSENED',
                        'status':'COMPLETED' if len(common) else 'EMPTY_COMMON_DOMAIN',
                        'HV_interpretation':'No ongoing HV provider within D61 outage; carried state/covariance and recovery' if case.startswith('D61') else 'HV conditional on retained A1 GNSS heading'})
            endkey=endpoint_key(original,meta);li=left.copy();ri=right.copy();li.index=keys(left);ri.index=keys(right)
            available=endkey is not None and endkey in li.index and endkey in ri.index
            for metric,column in METRICS.items():
                a=abs(float(li.loc[endkey,column])) if available else None
                b=abs(float(ri.loc[endkey,column])) if available else None;delta=a-b if available else None
                paired.append({'case_id':case,'family':meta['degradation_type_id'],'duration_s':meta['duration_s'],
                    'seed_index':meta['seed_index'],'anchor_time_s':meta['anchor_time_s'],'ablation_method':method,
                    'domain':'outage_end','metric':metric,'unit':'deg' if metric=='yaw' else 'm',
                    'full_value':a,'ablation_value':b,'delta_full_minus_ablation':delta,'common_epochs':int(available),
                    'original_measured_epoch_denominator':1,'missing_common_epochs':int(not available),'endpoint_key_us':endkey,
                    'outcome':'UNAVAILABLE' if not available else 'TIE' if abs(delta)<=1e-12 else 'IMPROVED' if delta<0 else 'WORSENED',
                    'status':'COMPLETED' if available else 'UNAVAILABLE_EXACT_END_EPOCH',
                    'HV_interpretation':'No ongoing HV provider within D61 outage; carried state/covariance and recovery' if case.startswith('D61') else 'HV conditional on retained A1 GNSS heading'})
    assert len(paired)==45*2*7*4
    groups=[];table=pd.DataFrame(paired)
    for key,group in table.groupby(['family','duration_s','ablation_method','domain','metric'],sort=True):
        values=group.delta_full_minus_ablation.dropna().to_numpy(float)
        groups.append({**dict(zip(['family','duration_s','ablation_method','domain','metric'],key)),
            'placement_blocks':9,'expected_cases':len(group),'available_cases':len(values),
            'improved':int((group.outcome=='IMPROVED').sum()),'tie':int((group.outcome=='TIE').sum()),
            'worsened':int((group.outcome=='WORSENED').sum()),'unavailable':int((group.outcome=='UNAVAILABLE').sum()),
            'mean_of_placement_RMSE_or_endpoint_deltas':float(np.mean(values)) if len(values) else None,
            'median_of_placement_deltas':float(np.median(values)) if len(values) else None,
            'min_delta':float(np.min(values)) if len(values) else None,'max_delta':float(np.max(values)) if len(values) else None,
            'independent_trials_claim':False,'post_outcome_case_exclusion':False})
    for name,rows in [('FULL_135_RESULTS.csv',identity),('OWN_SUPPORT_DOMAINS.csv',own),
        ('PAIRED_ALL_90_CASES_DOMAINS.csv',paired),('PLACEMENT_BLOCK_SUMMARY.csv',groups),
        ('INDEPENDENT_RECOMPUTATION.csv',recompute),('REFERENCE_ACCESS_AUDIT.csv',access),('NATIVE_RUN_SUMMARY.csv',native_rows)]:save_csv(target/name,rows)
    # Complete an actual second check after all arithmetic and table writes.
    for relative,digest in plan['source_snapshot_sha256'].items():
        assert sha(CODE/relative)==sha(STAGE/'SOURCE_SNAPSHOT'/relative)==digest
    for path,digest in plan['original_provider_and_config_pins'].items():assert sha(path)==digest
    assert sha(STAGE/'SOLVER')==plan['binary_sha256']
    for path,digest in prepared_pins.items():assert sha(path)==digest
    for path,digest in control_pins.items():assert sha(path)==digest
    assert sha(STAGE/'CORRECTED_RESULTS.json')==aggregate_before
    assert sha(STAGE/'ALL_NATIVE_SEALED.json')==native_before
    for item in audits:
        root=STAGE/'EVALUATION'/item['run_id']
        assert sha(root/'EVALUATION_RESULT.json')==item['evaluation_result_sha256']
        if item['error_series_sha256'] is not None:assert sha(root/'FROZEN_EVALUATOR/error_series.csv')==item['error_series_sha256']
    receipt={'status':'ALL_135_SEALED_SAVED_ERROR_REDUCTION_VERIFIED' if all(r['status']=='COMPLETED_SEGMENTED' for r in identity) else 'ALL_135_REDUCTION_WITH_UNAVAILABLE_CASES_RETAINED',
        'accepted_cases':sum(r['status']=='COMPLETED_SEGMENTED' for r in identity),
        'unavailable_cases':sum(r['status']!='COMPLETED_SEGMENTED' for r in identity),'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'configurations':135,'cases':45,'single_variable_pairs':90,'paired_metric_domain_rows':len(paired),
        'all_pair_rows_retained_including_worse':True,'native_reference_opens':0,'offline_reference_opens':sum(r['offline_trace_open_count'] for r in access),
        'reference_reads_by_reducer':0,'solver_or_evaluator_calls_by_reducer':0,
        'full_window_original_denominator':56642,'max_recomputation_difference':max((r['abs_difference'] for r in recompute),default=None),
        'preregistration_sha256':sha(STAGE/'PREREGISTRATION.json'),'native_seal_sha256':sha(STAGE/'ALL_NATIVE_SEALED.json'),
        'evaluation_file_pins':audits,'reducer_sha256':sha(__file__),
        'control_and_prepare_helper_pins_before_after':control_pins,
        'new_IMU8_and_child_config_pins_before_after':prepared_pins,
        'duplicate_native_or_aggregate_ids':0,
        'publication_csv_sha256':{p.name:sha(p) for p in target.glob('*.csv')},
        'source_identity_superset_count':len(plan['source_snapshot_sha256']),
        'all_current_and_saved_science_sources_match':True,'all_original_provider_config_pins_match':True,
        'source_provider_snapshot_rechecked_before_and_after_reduction':True,
        'evaluation_inputs_and_aggregate_rechecked_before_and_after_reduction':True,
        'aggregate_row_exactly_matches_individual_evaluation_result':True,
        'limitations':['Shared GNSS commercial fused reference, independent truth unresolved','Reference point and covariance transport unresolved',
                       'D61 no ongoing valid HV; independent RP scheduling absent when GNSS invalid','D62 HV depends on retained A1 GNSS heading',
                       'Multiple native numerical fixes changed; no single repair causal attribution','Nine placements reused; exploratory after historical outcomes known',
                       'Only45x3 subset revalidated; full6468 and full H1/H3 matrix not replayed']}
    with (target/'REDUCTION_RECEIPT.json').open('x') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps({k:receipt[k] for k in ('status','configurations','cases','paired_metric_domain_rows','offline_reference_opens','max_recomputation_difference')}))

if __name__=='__main__':main()
