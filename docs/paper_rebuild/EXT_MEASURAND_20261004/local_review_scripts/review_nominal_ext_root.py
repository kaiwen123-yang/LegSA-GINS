from pathlib import Path
import json,csv,hashlib,math,shutil
s=Path('/mnt/g/LegSA-GINS-project/修复_20261004/EXT_MEASURAND_DIAGNOSTIC');r=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001');d=r/'docs/paper_rebuild/EXT_MEASURAND_20261004'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open()))
def rmse(v):return math.sqrt(math.fsum(x*x for x in v)/len(v))
def wrap(v):return (v+180)%360-180
reg=json.loads((s/'PREREGISTRATION.json').read_text());rr=json.loads((s/'RESULT_RECEIPT.json').read_text());assert sha(s/'PREREGISTRATION.json')==rr['preregistration_sha256']==sha(d/'PREREGISTRATION.json');assert sha(s/'SUMMARY.csv')==rr['summary_sha256'];assert sha(s/'DERIVED_ERRORS.csv')==rr['derived_errors_sha256'];assert sha(s/'ROOT_NATIVE_SEAL_REVIEW.json')==rr['native_seal_review_sha256']
summaries=rows(s/'SUMMARY.csv');derived=rows(s/'DERIVED_ERRORS.csv');assert len(summaries)==9 and len(derived)==7689
old={};old_pins=0
for e in reg['entries']:
 for stem in ('spec','errors','metrics'):assert sha(Path(e[stem+'_path']))==e[stem+'_sha256'];old_pins+=1
 for x in rows(Path(e['errors_path'])):
  if x['valid']=='1' and x['reference_supported']=='1':old[(e['sequence'],x['method_id'],x['time_key_us'])]=x
assert len(old)==7689 and len(set((x['sequence'],x['method'],x['time_key_us']) for x in derived))==7689
for x in derived:
 y=old[(x['sequence'],x['method'],x['time_key_us'])];e=wrap(float(y['native_body_yaw_deg'])-float(y['reference_yaw_ned_deg']));assert e==float(x['old_error_deg']);assert x['nominal_projection_supported']=='True'
 assert abs(wrap(float(x['nominal_projected_error_deg'])-wrap(e-float(x['nominal_quantity_delta_deg']))))<1e-12
mx=0.;checks=0
for x in summaries:
 group=[y for y in derived if y['sequence']==x['sequence'] and y['method']==x['method']];assert len(group)==int(x['original_scored_count'])==int(x['nominal_projected_scored_count']);assert int(x['nominal_undefined_count'])==0
 for field,col in [('old_Euler_RMSE_deg','old_error_deg'),('nominal_projected_RMSE_deg','nominal_projected_error_deg'),('quantity_delta_RMSE_deg','nominal_quantity_delta_deg')]:
  diff=abs(rmse([float(y[col]) for y in group])-float(x[field]));assert diff<1e-10;mx=max(mx,diff);checks+=1
 assert abs(max(abs(float(y['nominal_quantity_delta_deg'])) for y in group)-float(x['quantity_delta_max_abs_deg']))<1e-12;checks+=1
 assert abs(min(float(y['reference_horizontal_projection_ratio_squared']) for y in group)-float(x['minimum_reference_projection_ratio_squared']))<1e-12;checks+=1
trace=(s/'OFFLINE_OPENAT.strace').read_text();opens={}
for e in reg['entries']:
 name=Path(e['trace_alias']).name;matches=[line for line in trace.splitlines() if name in line and 'openat(' in line];assert len(matches)==1 and '= -1' not in matches[0];opens[e['sequence']]=len(matches)
report={'schema':'root.EXT.nominal.measurand.saved-result.review.v1','all_checks_passed':True,'same_original_scored_key_checks':len(derived),'independent_summary_fields_checked':checks,'max_statistic_difference_deg':mx,'old_bound_file_pins_unchanged':old_pins,'old_Euler_error_max_diff_deg':rr['old_error_max_diff_deg'],'old_Euler_RMSE_max_diff_deg':rr['old_rmse_max_diff_deg'],'nominal_projection_unsupported_count':0,'actual_strace_reference_opens':opens,'actual_strace_sha256':sha(s/'OFFLINE_OPENAT.strace'),'nominal_quantity_max_abs_delta_deg':max(float(x['quantity_delta_max_abs_deg']) for x in summaries),'nominal_quantity_RMSE_range_deg':[min(float(x['quantity_delta_RMSE_deg']) for x in summaries),max(float(x['quantity_delta_RMSE_deg']) for x in summaries)],'maximum_nominal_vs_Euler_RMSE_change_deg':max(abs(float(x['old_Euler_RMSE_deg'])-float(x['nominal_projected_RMSE_deg'])) for x in summaries),'preregistration_sha256':sha(s/'PREREGISTRATION.json'),'result_receipt_sha256':sha(s/'RESULT_RECEIPT.json'),'review_source_sha256':sha(Path(__file__)),'review_reference_payload_reads':0,'new_native_invocations':0,'old_files_written':0,'interpretation':'Nominal tilt quantity difference cannot explain retained64-104deg errors; actual mount/antenna-order calibration remains unknown, no universal unsuitability or same-input ranking claim'}
(s/'ROOT_OFFLINE_RESULT_REVIEW.json').write_text(json.dumps(report,indent=2)+'\n')
for name in ('SUMMARY.csv','RESULT_RECEIPT.json','ROOT_NATIVE_SEAL_REVIEW.json','ROOT_OFFLINE_RESULT_REVIEW.json'):assert not (d/name).exists();shutil.copyfile(s/name,d/name)
print(json.dumps(report))
