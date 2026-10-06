"""Read-only acceptance of EXISTING result artifacts; no pipeline imports/raw references.
Writes only this comparison review directory. CSV error reduction is independent.
Local paths are explicit evidence locations, not a portable experiment controller.
"""
import csv, gzip, hashlib, json, math, pathlib, datetime, zipfile, collections
R=pathlib.Path(__file__).resolve().parents[4]
D=pathlib.Path(__file__).resolve().parent
G=pathlib.Path('/mnt/g/LegSA-GINS-project')
C=G/'clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON'
X=pathlib.Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/EXT_REPRODUCTION_V2_TECH_RETRY_2_20261004T054256Z')
F=pathlib.Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z')
S=G/'clean_rebuild_202607/stages/FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z'
SEQS=('BY2','BY2H','BY2O');DENH=dict(zip(SEQS,(1370,1350,1885)));DENF=dict(zip(SEQS,(275,271,378)))
pins={};checks=[];numeric=[];index=[];scope=[]
def sha(p):
 p=pathlib.Path(p)
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 v=h.hexdigest();pins[str(p)]={'sha256':v,'bytes':p.stat().st_size};return v
def load(p):sha(p);return json.loads(pathlib.Path(p).read_text())
def rows(p):
 sha(p);op=gzip.open if str(p).endswith('.gz') else open
 with op(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def gate(key,passed,detail=''):checks.append({'check':key,'passed':bool(passed),'detail':detail})
def bind(p,expected,label):gate(label,sha(p)==expected)
def num(key,label,want,vals):
 vals=[float(v) for v in vals if str(v) not in ('','None','nan','NaN') and math.isfinite(float(v))]
 got=math.sqrt(math.fsum(v*v for v in vals)/len(vals)) if vals else None
 want=None if want in (None,'','NaN','nan','UNAVAILABLE') else float(want)
 diff=abs(got-want) if got is not None and want is not None else None
 ok=(got is None and want is None) or (diff is not None and diff<=1e-9)
 numeric.append(dict(identity=key,metric=label,count=len(vals),saved=want,recomputed=got,absolute_difference=diff,passed=ok))
 return len(vals)
def entry(group,seq,method,rid,native,ev,status,expected,matched,code,point,angle,reuse=False,native_ref=0,detail=''):
 index.append(dict(group=group,sequence=seq,method=method,run_id=rid,native_receipt=str(native),native_receipt_sha256=sha(native),evaluation_receipt=str(ev) if ev else '',evaluation_receipt_sha256=sha(ev) if ev else '',status=status,expected_denominator=expected,matched_or_valid=matched,code_commit_or_role=code,position_point=point,angle_definition=angle,native_reference_reads=native_ref,result_reused_in_later_diagnostic=reuse,limit=detail))
def nav_metrics(key,metrics,es,typ='nav'):
 mapping={'horizontal_rmse_m':'horizontal_err_m','up_rmse_m':'err_u_m','vertical_rmse_m':'err_u_m','position_3d_rmse_m':'position_3d_err_m','yaw_rmse_deg':'yaw_err_deg'}
 for k,v in mapping.items():
  if k in metrics and (v in (es[0] if es else {}) or metrics[k] in ('',None)):
   num(key,k,metrics[k],[z.get(v,'') for z in es])
# 12 official moving-base runs. Native/hold/float keep distinct.
for seq in SEQS:
 for var in ('V0','V0E','V1','V2'):
  root=C/'HX07R/RUNS'/f'{seq}_{var}';cmd=load(root/'COMMAND.json');ev=root/'eval/OUTPUT/HEADING_METRICS.json';m=load(ev)['variants']['RTKLIB'];assoc=load(root/'ASSOCIATION_SUMMARY.json');er=rows(root/'eval/OUTPUT/HEADING_ERROR_SERIES_RTKLIB.csv')
  gate(f'RTK.{seq}.{var}.terminal',cmd['returncode']==0 and cmd['status']=='FINISHED')
  gate(f'RTK.{seq}.{var}.denominator',len(er)==DENH[seq]==m['denominator_native_paired_epochs_in_window'])
  for field,label,expected in [('error_valid_deg','valid',m['valid']['rmse_deg']),('error_hold_deg','hold',m['hold_last_valid']['rmse_deg'])]:
   n=num(f'RTK.{seq}.{var}',label,expected,[z[field] for z in er]);gate(f'RTK.{seq}.{var}.{label}.count',n==m['valid']['count'] if label=='valid' else n==m['hold_last_valid']['count'])
  # native fixed+float stats are separate; float saved errors are not in this series.
  audit=next(a for a in load(R/'docs/paper_rebuild/hext/HX07R/HX07R_AUDIT.json')['audits'] if a['run']==f'{seq}_{var}' and a['kind']=='native')
  gate(f'RTK.{seq}.{var}.native_reference_zero',audit['reference_raw_opens']==0 and audit['passed'])
  cfg=pathlib.Path(cmd['argv'][cmd['argv'].index('-k')+1]);sha(cfg)
  entry('RTKLIB_HX07R',seq,'RTKLIB_'+var,f'{seq}_{var}',root/'COMMAND.json',ev,cmd['status'],DENH[seq],m['valid']['count'],'2.4.3_b34@180043ee; official binary/config pins','HEADING_ONLY','lateral baseline projected heading vs fused Euler reference',True,detail='Q1 eligibility / causal hold separate; no integer truth')
# Latest EXT raw9, exact per-run snapshots and output pins (no current-source substitution).
a=load(X/'ALL_NATIVE_VERIFIED_BEFORE_REFERENCE.json')
gate('EXT.all9.native_seal',a['actual_new_native_calls']==9 and a['native_reference_or_forbidden_data_opens']==0)
for seq in SEQS:
 ev=X/'evaluation'/seq/'HEADING_METRICS.json';ms=load(ev);er=rows(X/'evaluation'/seq/'ERROR_SERIES.csv')
 for method in ('EXT01','EXT02','EXT03'):
  root=X/'runs'/f'{seq}__{method}__RAW_REPRO_V2__TECH_RETRY_2';run=load(root/'RUN.json');m=ms[method];part=[z for z in er if z['method_id']==method]
  gate(f'EXT.{seq}.{method}.counts',len(part)==DENH[seq] and run['completed_epochs']==run['planned_paired_epochs'] and sum(run['failure_counts'].values())+run['valid_epochs']==run['completed_epochs'])
  gate(f'EXT.{seq}.{method}.input_contract',not run['trace_used_online'] and not run['per_case_tuning'] and run['gps_l1_spp_earth_rotation_delay']=='iterated_geometric')
  for name,h in run['source_snapshot_hashes'].items():bind(root/'SOURCE_SNAPSHOT'/name,h,f'EXT.{seq}.{method}.snapshot.{name}')
  for name,h in run['outputs'].items():bind(root/name,h['sha256'] if isinstance(h,dict) else h,f'EXT.{seq}.{method}.output.{name}')
  for field,label in [('error_valid_deg','valid'),('error_hold_deg','hold')]:
   stat=m['valid'] if label=='valid' else m['hold_last_valid'];n=num(f'EXT.{seq}.{method}',label,stat['rmse_deg'],[z[field] for z in part]);gate(f'EXT.{seq}.{method}.{label}.count',n==stat['count'])
  entry('EXT_RAW_V2',seq,method,run['run_id'],root/'RUN.json',ev,run['status'],DENH[seq],m['valid']['count'],'0625 BASE_HEAD_ONLY + exact saved overlay13+config','HEADING_ONLY','lateral projected heading +90 vs fused Euler reference',detail='post-result guard3source not retroactively attached; rejected epochs retained')
# Strict9 once-init science; reconstruct own metrics only, common support inherited.
seal=load(F/'ALL_NINE_NATIVE_SEAL.json');gate('FGO.strict.native9.seal',seal['native_count']==9 and seal['reference_payload_opens_all_native']==0 and seal['evaluator_process_count_at_seal']==0)
for seq in SEQS:
 met=rows(F/'evaluation'/seq/'METRICS.csv')
 for method in ('OISAM','WEN_TC','GNC'):
  root=F/'runs'/seq/method/'PAPER_CONTRACT';run=load(root/'RUN.json');m=next(z for z in met if z['method_id']==method and z['support']=='OWN_VALID');er=rows(F/'evaluation'/seq/f'{method}_ERRORS.csv');valid=[z for z in er if z.get('valid','1')=='1']
  for name,h in run['implementation_source_hashes'].items():bind(root/'SOURCE_SNAPSHOT'/name,h,f'FGO.strict.{seq}.{method}.snapshot.{name}')
  for name,h in run['output_hashes'].items():bind(root/name,h['sha256'] if isinstance(h,dict) else h,f'FGO.strict.{seq}.{method}.output.{name}')
  gate(f'FGO.strict.{seq}.{method}.reference_zero',run['reference_payload_reads']==0 and not run['trace_used_online'])
  gate(f'FGO.strict.{seq}.{method}.support',len(valid)==int(m['matched_epoch_count']) and int(m['expected_epoch_count'])==DENF[seq])
  nav_metrics(f'FGO.strict.{seq}.{method}',m,valid)
  entry('FGO_STRICT',seq,method,f'{seq}/{method}/PAPER_CONTRACT',root/'RUN.json',F/'evaluation'/seq/'EVALUATION.json',run['terminal_status'],DENF[seq],len(valid),'0625 BASE_HEAD + exact22 snapshot','MIDPOINT' if method=='OISAM' else 'GNSS1_ANTENNA','own Euler attitude only OISAM; others N/A',method!='OISAM',detail='once A1 init Oi no gap reset; actual invalid/no output retained')
# New3 segmented identities + reused original6. All36 metric rows own/common, primary/secondary.
seal=load(S/'ALL_NATIVE_SEALED.json');gate('FGO.seg.native_seal',seal['new_native_count']==3 and seal['reused_original_full_batch_native_count']==6 and seal['new_native_reference_opens']==0)
for seq in SEQS:
 root=S/'runs'/seq/'OISAM/SEGMENTED_DIAGNOSTIC';run=load(root/'RUN.json');binding=seal['comparison_identities'][seq]['OISAM'];bind(root/'RUN.json',binding['run_json_sha256'],f'FGO.seg.{seq}.run_seal');gate(f'FGO.seg.{seq}.fixed_all_blocks',run['planned_blocks']==run['attempted_blocks']==dict(BY2=1,BY2H=3,BY2O=7)[seq])
 for name,h in run['output_hashes'].items():bind(root/name,h['sha256'] if isinstance(h,dict) else h,f'FGO.seg.{seq}.output.{name}')
 with zipfile.ZipFile(root/'SOURCE_SNAPSHOT.zip') as z:
  for name,h in run['implementation_source_hashes'].items():gate(f'FGO.seg.{seq}.snapshot.{name}',hashlib.sha256(z.read(name)).hexdigest()==h)
 met=rows(S/'evaluation'/seq/'METRICS.csv');ev=load(S/'evaluation'/seq/'EVALUATION.json');access=load(S/'evaluation'/seq/'ACCESS.json');gate(f'FGO.seg.{seq}.offline_only',access['native_calls']==0 and access['actual_reference_payload_opens']==1 and access['all_new_native_sealed_before_open'])
 for role in ('PRIMARY_DYNAMIC_ONLY','SECONDARY_ALL_VALID_POSITION'):
  ers={method:rows(S/'evaluation'/seq/f'{method}_{role}_ERRORS.csv') for method in ('OISAM','WEN_TC','GNC')}
  keys={method:{int(z['expected_second']) for z in er if z['valid']=='1'} for method,er in ers.items()};common=set.intersection(*keys.values());gate(f'FGO.seg.{seq}.{role}.common_keys',sorted(common)==ev['common_nominal_keys'][role])
  for method,er in ers.items():
   for support in ('OWN_VALID','COMMON_THREE_TIME_KEYS'):
    m=next(z for z in met if z['method_id']==method and z['support_role']==role and z['support']==support);selected=[z for z in er if z['valid']=='1' and (support=='OWN_VALID' or int(z['expected_second']) in common)]
    gate(f'FGO.seg.{seq}.{method}.{role}.{support}.count',len(selected)==int(m['matched_epoch_count']) and int(m['expected_epoch_count'])==DENF[seq] and int(m['missing_or_invalid_count'])==DENF[seq]-len(selected))
    if role=='PRIMARY_DYNAMIC_ONLY':gate(f'FGO.seg.{seq}.{method}.{support}.no_prior',not any(z['prior_only']=='1' for z in selected))
    nav_metrics(f'FGO.seg.{seq}.{method}.{role}.{support}',m,selected)
  m=next(z for z in met if z['method_id']=='OISAM' and z['support_role']==role and z['support']=='OWN_VALID')
  entry('FGO_SEGMENTED_'+role,seq,'OISAM',f'{seq}/OISAM/SEGMENTED_DIAGNOSTIC',root/'RUN.json',S/'evaluation'/seq/'EVALUATION.json',run['terminal_status'],DENF[seq],m['matched_epoch_count'],'9d80ef33 + exact872 dependency superset','GNSS1_ANTENNA transported with own Oi attitude','own Euler attitude',detail='new native3 only; 6 W/GNC strict identity reused; all true-gap blocks predeclared; secondary prior-only explicit')
# Original LC01/LIT/S and single-receiver update16 table conditions, preserving failures.
v3=rows(G/'clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/07_AGGREGATE/MAIN_TABLE_V3.csv')
for m in v3:
 if m['method_id'] not in ('LC01','LC01-S','EXT05C','EXT05C-S'):continue
 seq,method,start=m['sequence_id'],m['method_id'],m['start_convention'];notes=json.loads(m['notes']);key=f'LC.{seq}.{method}.{start}'
 native=G/'clean_rebuild_202607/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/04_NATIVE_RUNS'/seq/method/start/'NATIVE_SUMMARY.json'
 # BY2 LIT reused earliest CLEAN5, not regenerated as a CLEAN7 run.
 eroot=pathlib.Path(m['error_series_source'])
 if not eroot.exists():
  old='/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN7_HEXT_EXTERNAL_SEQUENCES/'
  if str(eroot).startswith(old):eroot=G/'clean_rebuild_202607/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES'/str(eroot)[len(old):]
 ev=eroot.parent/'EVALUATION_RESULT.json'
 if native.exists():
  run=load(native);gate(key+'.native_refzero',run['trace_open_count']==0 and not run['trace_used_online']);
  if 'native_sha256' in notes:bind(native,notes['native_sha256'],key+'.native_summary_table_pin')
  ss=run.get('summary',{});gate(key+'.init_same_epoch',ss.get('initial_time_unix_seconds')==ss.get('initial_yaw_source_time_unix_seconds'))
 else:
  native=G/'clean_rebuild_202607/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05A_C00_NATIVE_SUMMARY.json'
  early=load(native);gate(key+'.early_native_refzero',early['trace_open_count']==0 and not early['trace_used_online'])
 error=eroot/'error_series.csv.gz'
 if not error.exists():error=eroot/'error_series.csv'
 if error.exists() and m['evaluation_status']!='NOT_RUN_ALGORITHM_FAILURE':
  er=rows(error);gate(key+'.matched',len(er)==int(m['matched_epoch_count']));mapping={'h_rmse_m':'horizontal_err_m','position_3d_rmse_m':'position_3d_err_m','up_rmse_m':'err_u_m','yaw_rmse_deg':'yaw_err_deg'}
  for field,col in mapping.items():num(key,field,m[field],[z[col] for z in er])
 else:scope.append({'identity':key,'detail':'failed before evaluation' if m['evaluation_status']=='NOT_RUN_ALGORITHM_FAILURE' else 'saved error payload unavailable at mapped location; no invented recalculation','path':str(error)})
 if ev.exists():
  e=load(ev)
  if 'source_sha256' in notes:bind(ev,notes['source_sha256'],key+'.evaluation_table_pin')
 entry('LC01_ORIGINAL_V3_CONDITIONS',seq,method,f'{seq}__{method}__{start}',native,ev if ev.exists() else None,m['evaluation_status'],'OUTPUT_RECORDS',m['matched_epoch_count'],m['code_commit']+' eval; earlier native32a0664 snapshot' if seq=='BY2' and method in ('LC01','EXT05C') else m['code_commit'],'declared midpoint in offline v3','own Euler attitude; C initialized by dual-receiver yaw',True,detail='H geometry FAIL/start variants kept; observed output denominator is not elapsed-time completeness; S development overlap disclosed')
# GINav 3 native: D8 B/O gate prevents accuracy eval; H 2/271.
for seq in SEQS:
 start=dict(BY2='C00',BY2H='CONTRACT_START',BY2O='FILE_START')[seq];root=C/'HX02_FIVE_CATEGORY/RUNS'/f'{seq}__GINAV__NONE__{start}__NA';run=load(root/'native/GINAV_RUN.json');done=load(root/'DONE.json');ev=root/'eval/GINAV_EVALUATION.json';e=load(ev);cov=e['coverage'];bind(root/'native/GINAV_RUN'/pathlib.Path(run['native_pos']).name,run['native_pos_sha256'],f'GINAV.{seq}.native_pos')
 gate(f'GINAV.{seq}.native_return',run['returncode']==0 and run['pass']);a=load(root/'native/NATIVE_ACCESS_AUDIT.json');gate(f'GINAV.{seq}.native_access',a['reference_open_count']==0 and a['old_runtime_input_count']==0 and not a['undeclared_raw_paths'])
 if seq=='BY2H':nav_metrics('GINAV.BY2H.v3',e['v3'],rows(root/'eval/v3/EXACT_EVALUATOR_OUTPUT/error_series.csv'))
 entry('GINAV_HX02',seq,'LC02_GINAV',done['run_id'],root/'native/GINAV_RUN.json',ev,e['evaluation_status'],DENF[seq],cov['nav_rows'],'official bc6b3ab6 + driver/config adapter','IMU_POINT ->declared midpoint offline','INS own Euler',detail='native process complete does not guarantee alignment or full-window support; D8 velocity gate failures preserve unavailable metrics')
# Official6 relative poses and SDK3 input diagnostic, reducing saved H/U/yaw.
for group,rr in [('HARTLEY_OFFICIAL',C/'HX02E_HARTLEY_OFFICIAL/RUNS'),('SDK_INPUT_DIAGNOSTIC',C/'HX05_CLOSEOUT/RUNS')]:
 for root in sorted(rr.iterdir()):
  p=root/'RESULT.json'
  if not p.exists():continue
  a=load(p);m=a['metrics'];seq=a.get('sequence');cfg=a.get('config','LEG_DR');es=next((root/'eval/OUTPUT').glob('RELATIVE_POSE_ERROR_SERIES_*.csv'));er=rows(es);nav_metrics(f'{group}.{root.name}',m,er);gate(f'{group}.{root.name}.scored',len(er)==m['scored_epochs']);nav=root/'NAV.csv'
  if nav.exists():bind(nav,a['nav_sha256'],f'{group}.{root.name}.nav')
  if group=='HARTLEY_OFFICIAL':gate(f'{group}.{root.name}.native_zero',a['native_audit']['reference_opens']==0 and not a['trace_used_online'])
  entry(group,seq,'Hartley_'+cfg if group=='HARTLEY_OFFICIAL' else 'LEG_DR',root.name,p,p,a.get('failure_flag',m['evaluation_status']),m['scored_epochs']+m['unsupported_grid_epochs'],m['scored_epochs'],a['code_commit'],'relative IMU/body point after fixed initial xyz+yaw alignment','own relative attitude' if group=='HARTLEY_OFFICIAL' else 'supplied SDK attitude',detail='relative input/gauge adaptation; no absolute GNSS/INS ranking')
# Older EXT04 module FAR/PAR: actual zero valid, not a zero RMSE.
for seq in SEQS:
 start=dict(BY2='C00',BY2H='CONTRACT_START',BY2O='FILE_START')[seq];root=C/'HX02_FIVE_CATEGORY/RUNS'/f'{seq}__EXT04__LIT__{start}__NA';a=load(root/'DONE.json');gate(f'EXT04.{seq}.retained_zero',all(x['valid']==0 for x in a['heading_tables'].values()));entry('EXT04_OLD_FAR_PAR',seq,'EXT04',a['run_id'],root/'DONE.json',None,a['status'],DENH[seq],0,a['provenance']['code_commit'],'HEADING_MODULE_ONLY','FAR/PAR baseline projected heading',detail='whole INS/misalignment chain absent; older raw backend; 0 accepted is unavailable error, not perfect output')
# Pin inherited tables/evidence, never open a raw trace via a locator.
for rel in ('V3_STORY_20261004/COMPARISON_SOURCE_ASSET_INDEX.csv','FGO_COMPLETE_AUDIT_20261004/COMPLIANCE_MATRIX.csv','hext/EXT_REPRODUCTION/v2_fix/FINAL_EXECUTION_RECEIPT.json','hext/HX07R/HX07R_EXECUTION_COUNTS.json'):
 sha(R/'docs/paper_rebuild'/rel)
def write_csv(name,a):
 with (D/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(a[0]),lineterminator='\n');w.writeheader();w.writerows(a)
write_csv('RUN_EVALUATION_INDEX.csv',index);write_csv('INDEPENDENT_SAVED_ERROR_RMSE_CHECKS.csv',numeric);write_csv('ARTIFACT_IDENTITY_CHECKS.csv',checks)
if scope:write_csv('ARTIFACT_SCOPE_LIMITS.csv',scope)
receipt={'schema':'comparison.existing.readonly.acceptance.v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'native_solver_calls':0,'evaluator_calls':0,'raw_reference_payload_opens':0,'saved_error_payloads_reduced_independently':True,'pipeline_imports':0,'run_conditions_indexed':len(index),'run_conditions_by_group':dict(collections.Counter(x['group'] for x in index)),'identity_checks':len(checks),'identity_failures':[x for x in checks if not x['passed']],'numeric_checks':len(numeric),'numeric_failures':[x for x in numeric if not x['passed']],'max_rmse_difference':max((x['absolute_difference'] or 0 for x in numeric),default=0),'all_performed_checks_passed':all(x['passed'] for x in checks+numeric),'scope_limits':scope,'artifact_pins_before':pins}
# Second actual byte pass across the files this audit read; no current-source vs snapshot claim.
receipt['artifact_pins_after_match']=all(sha(p)==v['sha256'] for p,v in list(pins.items()))
receipt['review_script_sha256']=sha(__file__)
(D/'BLOCK02_ACCEPTANCE_REVIEW.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:receipt[k] for k in ('run_conditions_indexed','run_conditions_by_group','identity_checks','numeric_checks','identity_failures','numeric_failures','max_rmse_difference','all_performed_checks_passed','artifact_pins_after_match','scope_limits')},ensure_ascii=False))
