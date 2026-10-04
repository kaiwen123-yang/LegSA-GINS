"""Read existing V3 records/configs only; write a new story ledger, never execute science."""
from pathlib import Path
import collections,csv,datetime,hashlib,json,math,sys
import yaml
import argparse
_parser=argparse.ArgumentParser(__doc__)
_parser.add_argument('--code-root',type=Path,required=True)
_parser.add_argument('--v3-root',type=Path,required=True)
_parser.add_argument('--registered-scratch-root',type=Path,required=True)
_args=_parser.parse_args()
CODE=_args.code_root.resolve()
STAGE=_args.v3_root.resolve()
SCRATCH=_args.registered_scratch_root.resolve()
OUT=CODE/'docs/paper_rebuild/V3_STORY_20261004'
assert OUT.parent==CODE/'docs/paper_rebuild'
OUT.mkdir(exist_ok=True)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def cell(v):return canonical(v) if isinstance(v,(dict,list)) else '' if v is None else v
def csvwrite(name,rows,fields=None):
    rows=list(rows)
    if fields is None:fields=list(rows[0])
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='raise');w.writeheader();w.writerows({k:cell(r.get(k)) for k in fields} for r in rows)
    return len(rows)
def jwrite(name,d):(OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def unique(rows,key):
    result={key(x):x for x in rows};assert len(result)==len(rows),(len(result),len(rows));return result
sources=[SCRATCH/'00_PREREGISTRATION/REGISTRY.json',SCRATCH/'00_PREREGISTRATION/REGISTRY_FILE_SEAL.json',STAGE/'FINAL_RUN_RECORDS.json',STAGE/'FINAL_EVALUATION_RECORDS.json',STAGE/'STATUS.json',STAGE/'07_AGGREGATE/AGGREGATE_MANIFEST.json']
pins_before={str(p):sha(p) for p in sources}
status=json.loads((STAGE/'STATUS.json').read_text())
assert pins_before[str(STAGE/'FINAL_RUN_RECORDS.json')]==status['final_run_records_sha256']
assert pins_before[str(STAGE/'FINAL_EVALUATION_RECORDS.json')]==status['final_evaluation_records_sha256']
reg=json.loads((SCRATCH/'00_PREREGISTRATION/REGISTRY.json').read_text())
reg_seal=json.loads((SCRATCH/'00_PREREGISTRATION/REGISTRY_FILE_SEAL.json').read_text())
assert len(reg)==6468 and pins_before[str(SCRATCH/'00_PREREGISTRATION/REGISTRY.json')]==reg_seal['sha256']
regmap=unique(reg,lambda x:x['run_id'])
assert collections.Counter(x['domain'] for x in reg)=={'CORE':5951,'ADDENDUM':495,'SEQUENCE':22}
fullruns=json.loads((STAGE/'FINAL_RUN_RECORDS.json').read_text())
runs=unique(fullruns,lambda x:x['run_id']);assert set(runs)==set(regmap)
# Retain complete result metadata as source; compact only the derived ledger.
evals=json.loads((STAGE/'FINAL_EVALUATION_RECORDS.json').read_text())
evalmap=unique(evals,lambda x:(x['row']['run_id'],x['row']['evaluator_contract']))
expected={(rid,'evaluator_contract_'+v) for rid in regmap for v in ('v3','v2')}
assert len(evals)==12936 and set(evalmap)==expected
native_counts=collections.Counter(x['status'] for x in fullruns)
assert native_counts=={'COMPLETED':6185,'ALGORITHM_FAILURE_DIVERGED':193,'ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT':90}
eval_counts=collections.Counter(x['row']['evaluation_status'] for x in evals)
assert eval_counts=={'COMPLETED':12370,'NOT_RUN_ALGORITHM_FAILURE':566}
assert all(x['code_commit']=='7d43b9af26120ed5dde21f53e515386361072ba6' for x in fullruns)
assert all(x['trace_open_count']==0 and x['retry_count']==0 for x in fullruns)
print('REGISTRY_AND_TERMINALS_PASS',flush=True)
manifest=json.loads((STAGE/'07_AGGREGATE/AGGREGATE_MANIFEST.json').read_text())
aggregate_index=[]
for name,pin in manifest['files_sha256'].items():
    p=STAGE/'07_AGGREGATE'/name;actual=sha(p);assert actual==pin,(name,pin,actual)
    n=fields=None
    if p.suffix=='.csv':
        with p.open() as f:
            rr=csv.DictReader(f);fields=rr.fieldnames;n=sum(1 for _ in rr)
    aggregate_index.append({'relative_path':name,'actual_path':str(p),'sha256':actual,'bytes':p.stat().st_size,'data_rows':n,'column_count':len(fields) if fields else None,'columns_json':fields,'read_mode':'FULL_STRUCTURED_MACHINE_READ_AND_HASH; semantic review separately recorded'})
csvwrite('AGGREGATE_SOURCE_INDEX.csv',aggregate_index)
metric_prefix=('north_','east_','up_','roll_','pitch_','yaw_','horizontal_','position_3d_')
metric_keys=[k for k in evals[0]['row'] if k.startswith(metric_prefix)]
path_remapped={'error_series_source','native_output_root'}
row_checks=0;scalar_checks=0;metric_checks=0;alias_rows=[];tablemaps={}
def same(a,b):
    if a is None:return b in ('','None','null')
    if isinstance(a,(dict,list)):
        try:return canonical(a)==canonical(json.loads(b))
        except (ValueError,TypeError):return False
    if isinstance(a,bool):return str(b).lower()==str(a).lower()
    if isinstance(a,(int,float)):
        try:return float(a)==float(b) or math.isnan(float(a)) and math.isnan(float(b))
        except (ValueError,TypeError):return False
    return str(a)==b
for v in ('V3','V2'):
    contract='evaluator_contract_'+v.lower();seen={}
    for domain,name,count in (('CORE','CORE_541_TABLE_'+v+'.csv',5951),('ADDENDUM','ADDENDUM_TABLE_'+v+'.csv',495),('SEQUENCE','SEQUENCE_TABLE_'+v+'.csv',33)):
        p=STAGE/'07_AGGREGATE'/name
        with p.open() as f:
            reader=csv.DictReader(f);rows=list(reader)
        assert len(rows)==count
        for line,t in enumerate(rows,start=2):
            rid=t['run_id'];key=(rid,contract);e=evalmap[key];row=e['row']
            if domain=='SEQUENCE' and t.get('sequence_c00_alias','').lower()=='true':
                assert regmap[rid]['domain']=='CORE' and regmap[rid]['case_id']=='C00_clean_normal'
                alias_rows.append({'source_table':name,'source_line':line,'run_id':rid,'method_id':t['method_id'],'sequence_id':t['sequence_id'],'actual_registered_domain':regmap[rid]['domain'],'role':'alias of CORE C00; zero extra native/evaluator calls'})
            else:
                assert rid not in seen;seen[rid]=t
                assert regmap[rid]['domain']==domain
            for k,a in row.items():
                if k in path_remapped or k not in t:continue
                if domain=='SEQUENCE' and t.get('sequence_c00_alias','').lower()=='true' and k=='domain':
                    assert a=='CORE' and t[k]=='SEQUENCE';continue
                assert same(a,t[k]),(rid,contract,k,a,t[k])
                scalar_checks+=1
                if k in metric_keys:metric_checks+=1
            row_checks+=1
            tablemaps.setdefault(key,{'path':str(p),'line':line,'row':t})
    assert set(seen)==set(regmap)
assert len(alias_rows)==22
csvwrite('SEQUENCE_C00_ALIAS_LEDGER.csv',alias_rows)
print('AGGREGATE53_AND_ALL_NUMERIC_FIELDS_PASS',row_checks,scalar_checks,flush=True)
features=('enable_dual_yaw','enable_receiver_velocity','enable_raw_doppler','enable_source_aware','enable_go2_roll_pitch_prior','enable_go2_horizontal_velocity_prior')
module_names=('Raw Doppler','source-aware weighting','Go2 roll/pitch prior','Go2 horizontal-velocity prior')
def reader_name(method,cfg):
    if method=='F04':return 'LegSA-GINS'
    if method=='F01':return 'GNSS/INS EKF (no online dual-heading update)'
    if method=='F02':return 'Position-and-dual-heading EKF (receiver-velocity update disabled)'
    if method=='F03':return 'Position/velocity-and-dual-heading EKF'
    off=[n for k,n in zip(features[2:],module_names) if not cfg[k]]
    return 'LegSA-GINS without '+', '.join(off)
config_models={};config_unique=collections.defaultdict(set);config_missing=collections.Counter();task_rows=[];method_rows={};cases={};config_pins={}
identity_fields={'run_id','run_label','case_id','protocol_id','stage_id','data_mode','outputpath','gnsspath','imupath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path'}
for index,rid in enumerate(sorted(regmap),1):
    r=regmap[rid];n=runs[rid];native_root=Path(n['archive_output_root'])
    cfgpath=native_root/'V3_RUNTIME_CONFIG.yaml';cfgbytes=cfgpath.read_bytes();cfgpin=hashlib.sha256(cfgbytes).hexdigest()
    assert cfgpin==n['config_hash'],(rid,cfgpin,n['config_hash'])
    config_pins[str(cfgpath)]=cfgpin;cfg=yaml.safe_load(cfgbytes)
    assert isinstance(cfg,dict)
    for k,val in cfg.items():config_unique[k].add(canonical(val))
    model={k:v for k,v in cfg.items() if k not in identity_fields}
    modelpin=hashlib.sha256(canonical(model).encode()).hexdigest();model_id='MODEL_'+modelpin[:16]
    config_models.setdefault(model_id,{'sha256':modelpin,'values':model,'example_run_id':rid,'source_config_path':str(cfgpath)})
    flags={k:cfg[k] for k in features}
    mid=r['method_id'];name=reader_name(mid,cfg)
    meth={'internal_method_id':mid,'paper_reader_name':name,'effective_profile':r['effective_profile'],**flags,'common_initialization_dual_yaw_used':cfg.get('common_initialization_dual_yaw_used'),'physical_native_run_count':0}
    if mid in method_rows:
        for k in flags:assert method_rows[mid][k]==flags[k]
    else:method_rows[mid]=meth
    method_rows[mid]['physical_native_run_count']+=1
    casekey=(r['sequence_id'],r['domain'],r['case_id']);case={'sequence_id':r['sequence_id'],'domain':r['domain'],'case_id':r['case_id'],'case_family':r['case_family'],'degradation_type_id':r['degradation_type_id'],'seed_index':r['seed_index'],'data_mode':r['data_mode'],'synthetic_data_used':r['synthetic_data_used'],'semisynthetic_data_used':r['semisynthetic_data_used'],'case_meta_json':r['case_meta'],'method_count':0}
    if casekey not in cases:cases[casekey]=case
    cases[casekey]['method_count']+=1
    er3=evalmap[(rid,'evaluator_contract_v3')];er2=evalmap[(rid,'evaluator_contract_v2')]
    row={'run_id':rid,'paper_reader_name':name,'internal_method_id':mid,'effective_profile':r['effective_profile'],'configuration_id':r['configuration_id'],'sequence_id':r['sequence_id'],'domain':r['domain'],'case_id':r['case_id'],'case_family':r['case_family'],'degradation_type_id':r['degradation_type_id'],'seed_index':r['seed_index'],'data_mode':r['data_mode'],'synthetic_data_used':r['synthetic_data_used'],'semisynthetic_data_used':r['semisynthetic_data_used'],'native_status':n['status'],'failure_classification':n['failure_classification'],'native_exit_code':n['exit_code'],'science_freeze':n['code_commit'],'binary_sha256':n['executable_sha256'],'runtime_seconds':n['runtime_seconds'],'native_trace_open_count':n['trace_open_count'],'native_retry_count':n['retry_count'],'native_invocation_count':n['native_invocation_count'],'registered_frozen_config_path':r['frozen_config']['path'],'registered_frozen_config_sha256':r['frozen_config']['sha256'],'actual_v3_retained_config_path':str(cfgpath),'actual_v3_config_sha256':cfgpin,'actual_config_field_count':len(cfg),'config_model_id':model_id,'config_identity_fields_json':{k:cfg.get(k) for k in sorted(identity_fields)},'config_semisynthetic_flag_as_preserved':cfg.get('semisynthetic_data_used'),'config_case_id_as_preserved':cfg.get('case_id'),'native_archive_root':str(native_root),'native_archive_receipt':n['archive_receipt'],'native_nav_sha256':n.get('nav_sha256'),'native_std_sha256':n.get('std_sha256'),'native_nav_payload_retained':(native_root/'KF_GINS_Navresult.nav').is_file(),'native_std_payload_retained':(native_root/'KF_GINS_STD.txt').is_file(),'provider_hashes_json':n['provider_hashes'],'evaluation_window_json':r['evaluation']['window'],'evaluator_reference_sha256_only':r['evaluation']['trace']['sha256'],'v3_evaluation_status':er3['row']['evaluation_status'],'v2_evaluation_status':er2['row']['evaluation_status'],'v3_evaluation_archive_root':er3.get('archive_output_root'),'v2_evaluation_archive_root':er2.get('archive_output_root'),'v3_error_series_location':er3.get('resolved_error_series_source'),'v2_error_series_location':er2.get('resolved_error_series_source')}
    task_rows.append(row)
    if index%1000==0:print('CONFIGS_PARSED_AND_HASHED',index,flush=True)
assert len(cases)==588 and all(c['method_count']==11 for c in cases.values())
csvwrite('TASK_LEDGER.csv',task_rows)
csvwrite('CASE_LEDGER.csv',sorted(cases.values(),key=lambda c:(c['domain'],c['sequence_id'],c['case_id'])))
csvwrite('METHOD_READER_NAME_MAP.csv',sorted(method_rows.values(),key=lambda m:m['internal_method_id']))
jwrite('CONFIG_MODEL_FACTORS.json',config_models)
csvwrite('CONFIG_FIELD_DISTRIBUTIONS.csv',[{'field':k,'distinct_preserved_value_count':len(v),'full_sorted_value_set_sha256':hashlib.sha256(canonical(sorted(v)).encode()).hexdigest(),'first_preserved_value':sorted(v)[0],'last_preserved_value':sorted(v)[-1],'all_config_payloads_read':6468} for k,v in sorted(config_unique.items())])
metric_identity=['run_id','paper_reader_name','internal_method_id','sequence_id','domain','case_id','case_family','degradation_type_id','seed_index','data_mode','evaluator_contract','evaluation_status','metrics_admitted','evaluation_invoked','failure_classification']
support_fields=['matched_epoch_count','output_epoch_count','unmatched_epoch_count','coverage_ratio','reference_epoch_count','time_start','time_end','finite_output','finite_ratio','reference_velocity_supported','reference_is_independent_ground_truth','uncertainty_status','evaluator_sha256','native_nav_sha256','evaluator_nav_sha256','std_sha256','config_hash','trace_sha256']
metric_rows=[];admitted_scalar_count=0;max_h_square_residual=0.0;max_3d_square_residual=0.0
for rid,contract in sorted(evalmap):
    e=evalmap[(rid,contract)];row=e['row'];r=regmap[rid];n=runs[rid]
    if row['evaluation_status']=='COMPLETED':
        assert row.get('evaluation_invoked') and e['audit']['trace_open_count']==1 and e['audit']['passed']
        for k in metric_keys:
            assert k in row and row[k] is not None and math.isfinite(float(row[k])),(rid,k,row.get(k));admitted_scalar_count+=1
        hr=float(row['horizontal_rmse_m'])**2-(float(row['north_rmse_m'])**2+float(row['east_rmse_m'])**2)
        dr=float(row['position_3d_rmse_m'])**2-(float(row['horizontal_rmse_m'])**2+float(row['up_rmse_m'])**2)
        max_h_square_residual=max(max_h_square_residual,abs(hr));max_3d_square_residual=max(max_3d_square_residual,abs(dr))
        assert abs(hr)<=1e-10*max(1.0,float(row['horizontal_rmse_m'])**2)
        assert abs(dr)<=1e-10*max(1.0,float(row['position_3d_rmse_m'])**2)
    else:
        assert not row['metrics_admitted'] and not row['evaluation_invoked']
        assert all(row.get(k) is None for k in metric_keys)
    out={k:row.get(k) for k in metric_identity+support_fields+metric_keys}
    out.update(paper_reader_name=method_rows[r['method_id']]['paper_reader_name'],internal_method_id=r['method_id'],registered_table_path=tablemaps[(rid,contract)]['path'],registered_table_line=tablemaps[(rid,contract)]['line'],final_evaluation_record_archive_root=e.get('archive_output_root'),full_original_metrics_role='VERBATIM_EXISTING_RESULT; no evaluator invoked')
    metric_rows.append(out)
csvwrite('METRIC_LEDGER.csv',metric_rows)
counterkeys=sorted(set().union(*(n.get('native_counters',{}).keys() for n in fullruns)))
csvwrite('NATIVE_ACTION_LEDGER.csv',[{'run_id':n['run_id'],'internal_method_id':n['method_id'],'paper_reader_name':method_rows[n['method_id']]['paper_reader_name'],'sequence_id':n['sequence_id'],'domain':n['domain'],'case_id':n['case_id'],'native_status':n['status'],**{k:n.get('native_counters',{}).get(k) for k in counterkeys}} for n in sorted(fullruns,key=lambda n:n['run_id'])])
# Only metadata hashes: reference path is never opened or hashed here.
pins_after={str(p):sha(p) for p in sources};assert pins_before==pins_after
for name,pin in manifest['files_sha256'].items():assert sha(STAGE/'07_AGGREGATE'/name)==pin
for p,pin in config_pins.items():assert sha(p)==pin
configpinsetsha=hashlib.sha256(canonical(config_pins).encode()).hexdigest()
outputs={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in OUT.iterdir() if p.is_file() and p.suffix in ('.csv','.json')}
receipt={'schema':'v3_story_full_task_metric_read.v1','captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_checks_passed':True,'scope':'ORIGINAL_PROTOCOL_V3_ALL6468; not corrected33/135 and no new science execution','formal_paper_method_name':'LegSA-GINS','internal_name_mapping':'F04 = LegSA_Paper_V1 / AB1111; internal IDs remain evidence keys','registered_tasks':6468,'registered_domain_counts':dict(collections.Counter(r['domain'] for r in reg)),'unique_physical_configurations':11,'core_case_count':541,'addendum_case_count':45,'additional_natural_sequence_count':2,'case_sequence_domain_cells':len(cases),'native_terminal_counts':dict(native_counts),'evaluator_terminal_slots':12936,'actual_evaluator_completions':12370,'not_invoked_algorithm_failure_slots':566,'original_unique_evaluator_contracts':['evaluator_contract_v3','evaluator_contract_v2'],'aggregate_manifest_bound_files_verified':len(aggregate_index),'aggregate_source_row_checks':row_checks,'full_original_scalar_field_equality_checks':scalar_checks,'metric_field_equality_checks':metric_checks,'metric_scalar_field_count':len(metric_keys),'finite_admitted_metric_scalars_checked':admitted_scalar_count,'sequence_coreC00_alias_rows_both_contracts':len(alias_rows),'actual_archived_config_payloads_read_and_parsed':len(config_pins),'actual_archived_config_hashes_match_original_native_record':True,'config_model_factors_count':len(config_models),'config_pinset_sha256':configpinsetsha,'input_pins_before':pins_before,'input_pins_after':pins_after,'all_aggregate_file_pins_before_after_unchanged':True,'all_archived_config_pins_before_after_unchanged':True,'max_horizontal_rmse_square_identity_residual_m2':max_h_square_residual,'max_3d_rmse_square_identity_residual_m2':max_3d_square_residual,'new_native_calls':0,'new_evaluator_calls':0,'new_provider_generation_calls':0,'raw_or_reference_payload_reads':0,'old_scientific_file_writes':0,'output_files':outputs,'read_scope_note':'All task/result/config objects machine traversed; this is not manual everyword semantic reading or new mathematical validation of estimator. Actual semantic contexts appear in READ_COVERAGE.csv.','historical_storage_note':'Payload existence flags are observed only; intentionally released NAV/STD/most CORE error series stay released. Hash-bound final results/configs/records are not reconstructed.'}
jwrite('REGISTRY_VALIDATION_RECEIPT.json',receipt)
print(json.dumps({'output':str(OUT),'all_checks_passed':True,'native_tasks':6468,'metric_rows':len(metric_rows),'metric_scalar_fields':len(metric_keys),'config_payloads':len(config_pins),'model_factors':len(config_models),'logical_bytes':sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()),'receipt_sha256':sha(OUT/'REGISTRY_VALIDATION_RECEIPT.json')},ensure_ascii=False),flush=True)
