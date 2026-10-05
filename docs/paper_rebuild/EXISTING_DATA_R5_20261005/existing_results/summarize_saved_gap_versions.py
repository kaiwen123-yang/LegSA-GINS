"""Summarize saved errors/support for all22 H/O versions. No scientific execution."""
from pathlib import Path
import csv,json,gzip,hashlib,math,argparse,collections
import numpy as np
METRICS=['H','V','3D','yaw']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def writecsv(p,rows):
 with p.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def rmse(a):return float(np.sqrt(np.mean(a*a))) if len(a) else None
def main(repo,stage,out):
 pins={}
 def pin(p):
  p=Path(p);h=sha(p)
  if str(p) in pins:assert pins[str(p)]==h
  pins[str(p)]=h;return p
 spec=json.loads(pin(out/'V07_DOMAIN_SPECIFICATION_BEFORE_REDUCTION.json').read_text())
 plan=json.loads(pin(stage/'PREREGISTRATION.json').read_text())
 with gzip.open(pin(repo/'docs/paper_rebuild/V3_STORY_20261004/TASK_LEDGER.csv.gz'),'rt') as f:tasks=list(csv.DictReader(f))
 with pin(repo/'docs/paper_rebuild/V3_STORY_20261004/NATURAL_METHOD_RESULTS.csv').open() as f:natural=list(csv.DictReader(f))
 natural={(x['sequence_id'],x['internal_method_id']):x for x in natural if x['evaluator_contract']=='evaluator_contract_v3'}
 with pin(stage/'CORRECTED_RESULTS.csv').open() as f:corrected={(x['sequence_id'],x['method_id']):x for x in csv.DictReader(f)}
 with pin('/mnt/g/LegSA-GINS-project/审查_20261003/BASE_PROVIDER_IMU_GAP_DIAGNOSTICS.csv').open(encoding='utf-8-sig') as f:historical=list(csv.DictReader(f))
 selected=[x for x in tasks if x['domain']=='SEQUENCE' and x['sequence_id'] in spec['sequences']]
 assert len(selected)==22 and len({(x['sequence_id'],x['internal_method_id']) for x in selected})==22
 assert all(x['science_freeze']=='7d43b9af26120ed5dde21f53e515386361072ba6' for x in selected)
 domainrows=[];runrows=[];gapprows=[];support_templates={};max_rmse_difference=0.0
 def readerrors(p):
  with gzip.open(pin(p),'rt',encoding='utf-8-sig') as f:a=np.loadtxt(f,delimiter=',',skiprows=1,usecols=(0,4,3,5,8),ndmin=2)
  assert np.isfinite(a).all()
  keys=np.rint(a[:,0]*1e6).astype(np.int64);assert len(np.unique(keys))==len(keys) and np.all(np.diff(keys)>0)
  return keys,a[:,1:]
 def masks(keys,gaps):
  near=np.zeros(len(keys),bool)
  for gap in gaps:near|=(keys>=round((gap['previous_time']-5)*1e6))&(keys<=round((gap['next_time']+30)*1e6))
  return {'FULL':np.ones(len(keys),bool),'NEAR_GAP_UNION':near,'FAR_FROM_GAP':~near}
 for task in sorted(selected,key=lambda x:(x['sequence_id'],x['internal_method_id'])):
  seq=task['sequence_id'];method=task['internal_method_id'];rid='IMUFIX_'+seq+'_'+method
  seqspec=spec['sequences'][seq];gaps=seqspec['gaps'];expected=seqspec['expected_original_output_epochs']
  oldpath=Path(task['v3_error_series_location'])/'error_series.csv.gz'
  newpath=stage/'EVALUATION'/rid/'FROZEN_EVALUATOR/error_series.csv.gz'
  ko,ao=readerrors(oldpath);kn,an=readerrors(newpath)
  assert len(ko)==expected and len(kn)==int(corrected[(seq,method)]['matched_epochs'])
  kc,io,inn=np.intersect1d(ko,kn,assume_unique=True,return_indices=True)
  assert len(kc)==len(kn) and np.array_equal(kn,kc)
  support=pin(stage/'COMBINED'/rid/'SEGMENT_SUPPORT.csv')
  seal=json.loads(pin(stage/'COMBINED'/rid/'OUTPUT_SEAL.json').read_text())
  assert seal['files']['SEGMENT_SUPPORT.csv']==pins[str(support)]
  with support.open() as f:sr=list(csv.DictReader(f))
  sk=np.array([round(float(x['time'])*1e6) for x in sr],dtype=np.int64)
  assert np.array_equal(sk,kn)
  if seq in support_templates:assert np.array_equal(support_templates[seq][0],ko) and np.array_equal(support_templates[seq][1],kn)
  else:support_templates[seq]=(ko,kn)
  oldfields=['horizontal_rmse_m','up_rmse_m','position_3d_rmse_m','yaw_rmse_deg'];newfields=['H_RMSE_m','V_RMSE_m','3D_RMSE_m','yaw_RMSE_deg']
  for k,metric in enumerate(METRICS):
   oldall=rmse(ao[:,k]);newall=rmse(an[:,k]);oldcommon=rmse(ao[io,k]);newcommon=rmse(an[inn,k])
   e=max(abs(oldall-float(natural[(seq,method)][oldfields[k]])),abs(newall-float(corrected[(seq,method)][newfields[k]])))
   max_rmse_difference=max(e,max_rmse_difference);assert e<1e-8,(seq,method,metric,e)
   runrows.append({'sequence_id':seq,'method_id':method,'reader_name':task['paper_reader_name'],'metric':metric,'unit':'deg' if metric=='yaw' else 'm','original_observed_denominator':expected,'original_matched':len(ko),'diagnostic_matched':len(kn),'common_epochs':len(kc),'diagnostic_missing_original_epochs':len(ko)-len(kn),'diagnostic_support_fraction':len(kn)/len(ko),'original_whole_RMSE':oldall,'diagnostic_own_RMSE':newall,'original_on_common_RMSE':oldcommon,'diagnostic_on_common_RMSE':newcommon,'common_delta_diagnostic_minus_original':newcommon-oldcommon,'support_change_original_common_minus_own':oldcommon-oldall,'comparison_type':'compound version and support sensitivity'})
  mo=masks(ko,gaps);mn=masks(kn,gaps);mc=masks(kc,gaps)
  assert mo['NEAR_GAP_UNION'].sum()+mo['FAR_FROM_GAP'].sum()==len(ko)
  dm=[]
  for domain in mo:dm.append((domain,'ALL_INTERNAL_GAPS',mo[domain],mn[domain],mc[domain]))
  for gapindex,gap in enumerate(gaps,1):
   a=round(gap['previous_time']*1e6);b=round(gap['next_time']*1e6)
   funcs={'PRE_5S':lambda k:(k>=a-5000000)&(k<=a),'PHYSICAL_GAP':lambda k:(k>a)&(k<b),'FIRST_POST_GAP_RECORD':lambda k:k==b,'POST_0_5':lambda k:(k>b)&(k<=b+5000000),'POST_5_30':lambda k:(k>b+5000000)&(k<=b+30000000)}
   for domain,func in funcs.items():dm.append((domain,f'G{gapindex:02d}',func(ko),func(kn),func(kc)))
   childid=rid+f'_S{gapindex:02d}';child=json.loads(pin(stage/'NATIVE'/childid/'NATIVE_RESULT.json').read_text())
   assert child['status']=='COMPLETED' and child['segment']['first']==gap['next_time']
   segstart=round(child['segment']['first']*1e6);segend=round(child['segment']['last']*1e6);start=round(child['initialization']['epoch']*1e6)
   oldseg=ko[(ko>=segstart)&(ko<=segend)];newseg=kn[(kn>=segstart)&(kn<=segend)]
   assert len(newseg)==int(child['output_epochs'])
   before=oldseg[oldseg<start];seeds=oldseg[(oldseg>=start)&(oldseg<newseg[0])]
   assert len(seeds)==1 and len(oldseg)-len(newseg)==len(before)+1
   h=[x for x in historical if x['sequence']==seq and x['wholly_inside_formal_window']=='True' and round(float(x['current_time_s'])*1e6)==b];assert len(h)==1
   gapprows.append({'sequence_id':seq,'method_id':method,'gap_id':f'G{gapindex:02d}','previous_time_s':gap['previous_time'],'next_time_s':gap['next_time'],'adjacent_exported_interval_s':gap['next_time']-gap['previous_time'],'measured_current_increment_duration_s':gap['measured_dt'],'physical_missing_duration_s':gap['missing_duration'],'source_row':gap['source_row'],'post_gap_segment_rows_in_original_denominator':len(oldseg),'restart_input_epoch_s':child['initialization']['epoch'],'input_wait_after_segment_start_s':child['initialization']['epoch']-child['segment']['first'],'seed_time_s':seeds[0]/1e6,'first_native_output_time_s':newseg[0]/1e6,'waiting_original_records':len(before),'seed_original_records':1,'actual_segment_output_epochs':len(newseg),'segment_missing_original_epochs':len(before)+1,'restart_yaw_information_added':child['initialization']['yaw_information_added']})
  for domain,gapid,oldmask,newmask,commonmask in dm:
   n0=int(oldmask.sum());n1=int(newmask.sum());nc=int(commonmask.sum());assert nc==n1
   for k,metric in enumerate(METRICS):
    oc=rmse(ao[io[commonmask],k]);dn=rmse(an[inn[commonmask],k])
    domainrows.append({'sequence_id':seq,'method_id':method,'gap_id':gapid,'domain':domain,'metric':metric,'unit':'deg' if metric=='yaw' else 'm','original_measured_domain_denominator':n0,'original_matched':n0,'diagnostic_matched':n1,'common_epochs':nc,'missing_diagnostic_from_original_domain':n0-n1,'status':'AVAILABLE' if nc else 'NO_COMMON_MEASURED_EPOCH','original_own_domain_RMSE':rmse(ao[oldmask,k]),'diagnostic_own_domain_RMSE':rmse(an[newmask,k]),'original_common_domain_RMSE':oc,'diagnostic_common_domain_RMSE':dn,'delta_common_diagnostic_minus_original':dn-oc if nc else None})
  print('SAVED_ERRORS_REDUCED',seq,method,len(ko),len(kn),flush=True)
 assert len(runrows)==88 and len(gapprows)==77 and len(domainrows)==1804, (len(runrows),len(gapprows),len(domainrows))
 for seq in spec['sequences']:
  gs=[x for x in gapprows if x['sequence_id']==seq]
  for method in {x['method_id'] for x in gs}:
   vs=[x for x in gs if x['method_id']==method];assert sum(x['segment_missing_original_epochs'] for x in vs)==int(corrected[(seq,method)]['unmatched_original_epochs'])
 writecsv(out/'GAP22_WHOLE_AND_COMMON_SUPPORT_88.csv',runrows);writecsv(out/'GAP22_FIXED_DOMAINS_1804.csv',domainrows);writecsv(out/'GAP7_ALL22_RESTART_SUPPORT_77.csv',gapprows)
 seqsummary=[]
 for seq in spec['sequences']:
  rr=[x for x in runrows if x['sequence_id']==seq];gs=[x for x in gapprows if x['sequence_id']==seq and x['method_id']=='F04'];template=rr[0]
  seqsummary.append({'sequence_id':seq,'methods':11,'internal_gaps':len(gs),'original_observed_denominator':template['original_observed_denominator'],'diagnostic_matched_per_method':template['diagnostic_matched'],'missing_per_method':template['diagnostic_missing_original_epochs'],'waiting_records_per_method':sum(x['waiting_original_records'] for x in gs),'seed_records_per_method':len(gs),'coverage_fraction':template['diagnostic_support_fraction'],'max_restart_wait_s':max(x['input_wait_after_segment_start_s'] for x in gs),'physical_missing_duration_sum_s':sum(x['physical_missing_duration_s'] for x in gs)})
 writecsv(out/'GAP_SUPPORT_SUMMARY_2.csv',seqsummary)
 rankings=[]
 for seq in spec['sequences']:
  for metric in METRICS:
   for domain in ['FULL','NEAR_GAP_UNION','FAR_FROM_GAP']:
    vv=[x for x in domainrows if x['sequence_id']==seq and x['metric']==metric and x['domain']==domain]
    for field,label in [('original_own_domain_RMSE','original_own'),('original_common_domain_RMSE','original_common'),('diagnostic_common_domain_RMSE','diagnostic_common')]:
     order=sorted(vv,key=lambda x:x[field]);ranks={x['method_id']:n+1 for n,x in enumerate(order)}
     for x in vv:rankings.append({'sequence_id':seq,'metric':metric,'domain':domain,'version_support':label,'method_id':x['method_id'],'rank':ranks[x['method_id']],'RMSE':x[field]})
 writecsv(out/'GAP22_DOMAIN_RANKINGS_792.csv',rankings)
 for p,h in pins.items():assert sha(Path(p))==h,p
 result={'status':'ALL22_MEMBERS_AND7_INTERNAL_GAPS_SAVED_ERROR_ANALYSIS_COMPLETE','source_files':[{'path':p,'sha256':h} for p,h in sorted(pins.items())],'before_after_hashes_equal':True,'members':22,'gaps':7,'gap_method_rows':77,'whole_metric_rows':88,'fixed_domain_rows':1804,'max_full_rmse_reproduction_difference':max_rmse_difference,'old_science_freeze':'7d43b9af26120ed5dde21f53e515386361072ba6','new_binary_sha256':plan['binary_sha256'],'new_version_models':plan['corrected_models'],'new_estimator_calls':0,'new_evaluator_calls':0,'raw_or_reference_opens':0,'interpolated_output_epochs':0,'new_scientific_result_writes':0,'domain_selection_by_error':False}
 (out/'GAP22_REDUCTION.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.repo,a.stage,a.out)
