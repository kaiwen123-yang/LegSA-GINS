#!/usr/bin/env python3
"""Select original-V3 tokens and summarize all45 original whole-window ADD cases.
No native estimator, provider, evaluator, raw data or trace is called or read.
"""
import csv, hashlib, json, re, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
STORY=ROOT/'docs/paper_rebuild/V3_STORY_20261004'
OUT=Path(__file__).resolve().parent
ADD=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/07_AGGREGATE/ADDENDUM_TABLE_V3.csv')
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=[STORY/'NATURAL_METHOD_RESULTS.csv', STORY/'SINGLE_MODULE_PAIRED_DIRECTION.csv', STORY/'RESULT_SUMMARIES/FAILURE_COMPARISON.csv', ADD]
pins={str(p):SHA(p) for p in sources}
def read(p):
 with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def write(name,rows):
 with (OUT/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
natural=[r for r in read(sources[0]) if r['evaluator_contract']=='evaluator_contract_v3']
paired=[r for r in read(sources[1]) if r['evaluator_contract']=='evaluator_contract_v3']
assert len(natural)==33 and len({(r['sequence_id'],r['internal_method_id']) for r in natural})==33
assert len(paired)==28 and len({(r['comparison'],r['metric']) for r in paired})==28
write('ORIGINAL_V3_NATURAL_EXACT_33.csv',natural)
write('ORIGINAL_V3_COMPONENT_EFFECTS_EXACT_28.csv',paired)
failed=[r for r in read(sources[2]) if r['domain']=='CORE' and r['protocol']=='v3' and r['evaluator_version']=='v3']
write('ORIGINAL_V3_CORE_OUTCOMES.csv',failed)
rr=read(ADD); assert len(rr)==495 and len({(r['case_id'],r['method_id']) for r in rr})==495
maps={m:{r['case_id']:r for r in rr if r['method_id']==m} for m in ['F04','A06']}
assert len(maps['F04'])==len(maps['A06'])==45 and maps['F04'].keys()==maps['A06'].keys()
for r in rr:
 assert r['code_commit']=='7d43b9af26120ed5dde21f53e515386361072ba6'
 assert r['evaluator_sha256']=='aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da'
 assert r['evaluator_contract']=='evaluator_contract_v3' and r['evaluation_status']=='COMPLETED'
 assert r['data_mode']=='semisynthetic' and r['semisynthetic_data_used']=='True' and r['synthetic_data_used']=='False'
 assert r['matched_epoch_count']=='56642' and r['coverage_ratio']=='1.0'
summary=[]; cases=[]
for deg,duration in [('D61',10),('D61',20),('D61',30),('D62',10),('D62',20)]:
 ids=sorted(c for c in maps['F04'] if re.fullmatch(fr'{deg}_{duration}s_seed_0[0-8]',c));assert len(ids)==9
 f=[float(maps['F04'][c]['horizontal_rmse_m']) for c in ids]
 a=[float(maps['A06'][c]['horizontal_rmse_m']) for c in ids]
 dd=[x-y for x,y in zip(f,a)]
 summary.append(dict(degradation_type=deg,outage_duration_s=duration,registered_pair_count=9,completed_pair_count=9,metric='whole_window_horizontal_rmse_m',full_median_m=statistics.median(f),full_minimum_m=min(f),full_maximum_m=max(f),without_HV_median_m=statistics.median(a),without_HV_minimum_m=min(a),without_HV_maximum_m=max(a),paired_full_minus_without_HV_median_m=statistics.median(dd),paired_full_minus_without_HV_mean_m=statistics.mean(dd),paired_delta_minimum_m=min(dd),paired_delta_maximum_m=max(dd),full_lower_count=sum(x<0 for x in dd),full_higher_count=sum(x>0 for x in dd),tie_count=sum(x==0 for x in dd),evaluation_window_start_s=66,evaluation_window_end_s=340,matched_epochs_per_run=56642,evaluator_contract='evaluator_contract_v3',source_table_sha256=pins[str(ADD)]))
 for c,delta in zip(ids,dd):
  x,y=maps['F04'][c],maps['A06'][c]
  cases.append(dict(case_id=c,degradation_type=deg,outage_duration_s=duration,seed=x['seed_index'],full_run_id=x['run_id'],without_HV_run_id=y['run_id'],full_horizontal_rmse_m=x['horizontal_rmse_m'],without_HV_horizontal_rmse_m=y['horizontal_rmse_m'],paired_delta_m=delta,full_status=x['evaluation_status'],without_HV_status=y['evaluation_status'],full_config_hash=x['config_hash'],without_HV_config_hash=y['config_hash'],full_native_nav_sha256=x['native_nav_sha256'],without_HV_native_nav_sha256=y['native_nav_sha256'],evaluator_contract=x['evaluator_contract'],evaluator_sha256=x['evaluator_sha256'],trace_sha256=x['trace_sha256'],source_table_sha256=pins[str(ADD)]))
assert len(cases)==45
write('ORIGINAL_V3_ADD_HV_WHOLE_WINDOW_BY_DURATION.csv',summary)
write('ORIGINAL_V3_ADD_HV_ALL_45_PAIRED_CASES.csv',cases)
assert pins=={str(p):SHA(p) for p in sources}
(OUT/'EFFECT_SIZE_SOURCE_PINS.json').write_text(json.dumps({'scope':'Original V3 token selections and descriptive whole-window summaries only','scientific_commit':'7d43b9af26120ed5dde21f53e515386361072ba6','scientific_binary_sha256':'96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c','evaluator_sha256':'aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da','original_source_tokens_preserved':True,'new_in_fault_or_endpoint_metrics':False,'paired_delta_definition':'Full minus without-HV per identical case, then median; not difference of marginal medians','all_45_cases_retained':True,'native_provider_evaluator_raw_trace_calls_or_reads':0,'source_hashes_before_after_equal':True,'sources':[{'path':str(p),'sha256':pins[str(p)]} for p in sources]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
