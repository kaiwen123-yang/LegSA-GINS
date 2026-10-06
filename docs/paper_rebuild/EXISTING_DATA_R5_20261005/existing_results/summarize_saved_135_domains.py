"""Read only saved135 domain tables; no estimator, evaluator or raw reference access."""
from pathlib import Path
import csv,json,statistics,hashlib,collections,math,argparse

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writecsv(path,rows):
 with path.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def main(repo,out):
 s=repo/'docs/paper_rebuild/v3/IMU_CLAIM_SUBSET_20261004'
 names=['PAIRED_ALL_90_CASES_DOMAINS.csv','PLACEMENT_BLOCK_SUMMARY.csv','IMU_CLAIM_ACCEPTED_FAULT_SOURCE_COUNTS.csv','REDUCTION_RECEIPT.json','IMU_CLAIM_135_FINAL_DELIVERY_RECEIPT.json']
 before={n:sha(s/n) for n in names}
 receipt=json.loads((s/'REDUCTION_RECEIPT.json').read_text())
 for n in names[:2]:assert receipt['publication_csv_sha256'][n]==before[n],n
 with (s/names[0]).open() as f:pairs=list(csv.DictReader(f))
 with (s/names[1]).open() as f:published=list(csv.DictReader(f))
 with (s/names[2]).open() as f:accepted=list(csv.DictReader(f))
 assert len(pairs)==2520 and len(published)==280 and len(accepted)==135
 assert len({(x['case_id'],x['ablation_method'],x['domain'],x['metric']) for x in pairs})==2520
 assert len({x['case_id'] for x in pairs})==45
 groups=collections.defaultdict(list)
 for x in pairs:
  assert x['status']=='COMPLETED' and int(x['missing_common_epochs'])==0 and int(x['common_epochs'])==int(x['original_measured_epoch_denominator'])
  assert math.isclose(float(x['full_value'])-float(x['ablation_value']),float(x['delta_full_minus_ablation']),abs_tol=1e-12)
  groups[(x['family'],int(x['duration_s']),x['ablation_method'],x['domain'],x['metric'])].append(x)
 rows=[];errors=[]
 pub={(x['family'],int(x['duration_s']),x['ablation_method'],x['domain'],x['metric']):x for x in published}
 for k,v in sorted(groups.items()):
  assert len(v)==9 and len({x['seed_index'] for x in v})==9
  a=[float(x['full_value']) for x in v];b=[float(x['ablation_value']) for x in v];d=[float(x['delta_full_minus_ablation']) for x in v]
  row=dict(zip(['family','duration_s','ablation_method_id','domain','metric'],k));row.update({'comparison_reader_name':'Proposed minus '+('no raw Doppler' if k[2]=='A03' else 'no robot horizontal velocity'),'unit':v[0]['unit'],'placements':9,'available':9,'unavailable':0,'proposed_mean':statistics.fmean(a),'proposed_median':statistics.median(a),'ablation_mean':statistics.fmean(b),'ablation_median':statistics.median(b),'mean_paired_delta':statistics.fmean(d),'median_paired_delta':statistics.median(d),'min_paired_delta':min(d),'max_paired_delta':max(d),'improved':sum(x<0 for x in d),'tie':sum(x==0 for x in d),'worsened':sum(x>0 for x in d),'min_original_domain_epochs':min(int(x['original_measured_epoch_denominator']) for x in v),'max_original_domain_epochs':max(int(x['original_measured_epoch_denominator']) for x in v),'missing_common_epochs':0,'value_definition':'exact last in-fault absolute error' if k[3]=='outage_end' else 'domain RMSE','scientific_version':'IMU135_DIAGNOSTIC_20261004_NOT_ORIGINAL_V3'})
  original=pub[k]
  for newkey,oldkey in [('mean_paired_delta','mean_of_placement_RMSE_or_endpoint_deltas'),('median_paired_delta','median_of_placement_deltas'),('min_paired_delta','min_delta'),('max_paired_delta','max_delta')]:errors.append(abs(row[newkey]-float(original[oldkey])))
  assert all(row[z]==int(original[z]) for z in ['improved','tie','worsened','unavailable'])
  rows.append(row)
 assert len(rows)==280 and max(errors)<1e-12
 source_rows=[]
 for (family,duration,method),vs in __import__('itertools').groupby(sorted(accepted,key=lambda x:(x['family'],int(x['duration_s']),x['method_id'])),key=lambda x:(x['family'],int(x['duration_s']),x['method_id'])):
  vs=list(vs);assert len(vs)==9
  for source in ['receiver_position','receiver_velocity','dual_antenna_yaw','raw_doppler_velocity','go2_attitude_roll_pitch','go2_horizontal_velocity']:
   a=[int(x[source+'_fault_accepted']) for x in vs];ev=[int(x[source+'_fault_evaluated']) for x in vs]
   source_rows.append({'family':family,'duration_s':duration,'method_id':method,'source':source,'placements':9,'min_fault_evaluated':min(ev),'max_fault_evaluated':max(ev),'min_fault_accepted':min(a),'max_fault_accepted':max(a),'total_fault_accepted':sum(a),'event_time_basis':'GNSS event time via shared update_index'})
 writecsv(out/'DIAGNOSTIC135_ALL_FIXED_DOMAINS_280.csv',rows)
 writecsv(out/'DIAGNOSTIC135_HV_H_OUTAGE_RECOVERY_25.csv',[x for x in rows if x['ablation_method_id']=='A06' and x['metric']=='H' and x['domain'] in ['fault','outage_end','recovery_0_5','recovery_5_10','recovery_10_30']])
 writecsv(out/'DIAGNOSTIC135_ACTUAL_FAULT_UPDATES_90.csv',source_rows)
 after={n:sha(s/n) for n in names};assert before==after
 result={'status':'SAVED_FIXED_DOMAIN_NUMBERS_VERIFIED','source_files':[{'path':str(s/n),'sha256':before[n]} for n in names],'source_before_after_equal':True,'pair_rows':2520,'groups':280,'accepted_event_members':135,'max_summary_recomputation_difference':max(errors),'new_estimator_calls':0,'new_evaluator_calls':0,'new_provider_calls':0,'raw_or_reference_opens':0,'new_science_writes':0,'scientific_version':'IMU135_DIAGNOSTIC_20261004_NOT_ORIGINAL_V3'}
 (out/'DIAGNOSTIC135_REDUCTION.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.repo,a.out)
