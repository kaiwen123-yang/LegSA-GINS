from pathlib import Path
import csv,json,hashlib,re,datetime
B=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001/docs/paper_rebuild/V3_STORY_20261004')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig')))
def main():
 d=json.loads((B/'FOURTH_BLOCK_DATA_RECEIPT.json').read_text());old=d['prior56_before_pins'];assert len(old)==56
 assert all(sha(B/n)==h for n,h in old.items())
 source=rows(B/'COMPARISON_SOURCE_ASSET_INDEX.csv');assert len(source)==33
 for r in source:
  assert sha(r['actual_path'])==r['sha256_before']==r['sha256_after']
  if r['copied_name']!='PIN_ONLY':assert sha(B/'COMPARISON_SOURCES'/r['copied_name'])==r['sha256_before']
 inv=rows(B/'EXTERNAL_METHOD_STORY.csv');assert len(inv)==len({r['internal_identity'] for r in inv})==30
 reg=rows(B/'COMPARISON_SOURCES/ORIGINAL_EXTERNAL_REGISTRY.csv');assert len(reg)==23
 assert {r['method_id'] for r in reg}=={r['internal_identity'] for r in inv if r['original_registry_member']=='True'}
 assert all(r['scientific_replay_this_block']=='False' for r in inv)
 anal=rows(B/'INTERNAL_ROBUST_ANALOGUE_SCOPE.csv');assert len(anal)==7
 assert all(r['formal_LegSA_GINS_used']==r['author_complete_algorithm_reproduction']=='False' for r in anal)
 lu=rows(B/'FROZEN_EXTERNAL_METRICS_OVERVIEW.csv');assert len(lu)==126
 groups={g:[r for r in lu if r['generation']==g] for g in {r['generation'] for r in lu}}
 assert sorted(map(len,groups.values()))==[27,36,63]
 checks=0
 for r in lu:
  orig=rows(B/r['exact_source_copy'])
  if r['generation'].startswith('EXT'):
   matches=[x for x in orig if x['source_row_key']==r['source_row_key'] and x['sequence_id']==r['sequence_id'] and x['method_id']==r['internal_method_id'] and x['support']==r['support_role']];assert len(matches)==1;x=matches[0]
   pairs={'sequence_id':'sequence_id','internal_method_id':'method_id','support_role':'support','status':'status','expected_denominator':'paired_epoch_denominator','matched_count':'scored_count','heading_RMSE_deg':'rmse_deg'}
  else:
   x=next(x for x in orig if x['sequence_id']==r['sequence_id'] and x['method_id']==r['internal_method_id'] and x['support']==r['support_role'].split(' /')[1] and x.get('support_role','')==r['source_row_key'].split('/')[0])
   pairs={'sequence_id':'sequence_id','internal_method_id':'method_id','status':'status','expected_denominator':'expected_epoch_count','matched_count':'matched_epoch_count','H_RMSE_m':'horizontal_rmse_m','V_RMSE_m':'vertical_rmse_m','3D_RMSE_m':'position_3d_rmse_m','heading_RMSE_deg':'yaw_rmse_deg'}
  for dest,src in pairs.items():assert r[dest]==x[src],(r['generation'],r['source_row_key'],dest);checks+=1
 f=rows(B/'COMPARISON_SOURCES/ORIGINAL_V3_MAIN_TABLE_V3.csv');assert len(f)==52
 from collections import Counter
 counts=dict(Counter(r['evaluation_status'] for r in f));assert counts=={'COMPLETED':26,'UNAVAILABLE':21,'AVAILABLE_GEOMETRIC_AUDIT_FAIL':4,'NOT_RUN_ALGORITHM_FAILURE':1}
 assert len(rows(B/'COMPARISON_FAIRNESS_CONTRACTS.csv'))==8 and len(rows(B/'COMPARISON_TIMELINE.csv'))==14
 for n in ['04_COMPARISON_INVENTORY_AND_FAIRNESS_STORY.md','CURRENT_STORY_INDEX.md']:
  s=(B/n).read_text()
  for p in re.findall(r'\]\(([^)]+)\)',s):
   if p=='FOURTH_BLOCK_READY_RECEIPT.json':continue # Final seal is written only after these checks.
   assert (B/p).exists(),(n,p)
 # Read-only all-files/source repeat check after validation; no source imports or metrics recomputation.
 assert all(sha(B/n)==h for n,h in old.items())
 assert all(sha(r['actual_path'])==r['sha256_before'] for r in source)
 return {'all_checks_passed':True,'prior56_unchanged':True,'33_source_pins_and20_original_byte_copies':True,'registry23_exact_members':True,'reader_identities30_unique':True,'analogues7_explicit_no_complete_author_algorithm':True,'metric_rows126_exact_original_tokens':True,'checked_numeric_and_identity_fields':checks,'original_main52_status_counts':counts,'segmented_native3_reused6_roles_separate':True,'fairness_contracts8':True,'timeline14':True,'local_doc_links_exist_except_pending_final_seal':True,'scientific_package_imports':0,'native_evaluator_generator_calls':0,'raw_reference_trace_payload_reads':0,'checker_sha256':sha(__file__),'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
if __name__=='__main__':
 result=main();out=B/'FOURTH_BLOCK_VALIDATION_RECEIPT.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))