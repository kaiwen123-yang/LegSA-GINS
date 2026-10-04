from pathlib import Path
import csv,json,hashlib,datetime
repo=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001');out=Path('/mnt/g/LegSA-GINS-project/修复_20261004');base=repo/'docs/paper_rebuild/V3_STORY_20261004'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=lambda p:list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline='')))
ready=json.loads((base/'FOURTH_BLOCK_READY_RECEIPT.json').read_text())
assert sha(base/'FOURTH_BLOCK_READY_RECEIPT.json')=='d1af4db36b34931d3d72aeda5533def8dc4fe1f3f9f06883dbd98631b5ceea5d'
for p,x in ready['new_file_pins_excluding_self'].items():assert sha(base/p)==x['sha256'] and (base/p).stat().st_size==x['bytes']
for p,h in ready['prior56_file_pins'].items():assert sha(base/p)==h
assets=rows(base/'COMPARISON_SOURCE_ASSET_INDEX.csv');copies=0
for a in assets:
 assert sha(a['actual_path'])==a['sha256_before']==a['sha256_after']
 if a['copied_name']!='PIN_ONLY':assert sha(base/'COMPARISON_SOURCES'/a['copied_name'])==a['sha256_before'];copies+=1
metrics=rows(base/'FROZEN_EXTERNAL_METRICS_OVERVIEW.csv');sources={};checked=0
for r in metrics:
 p=r['exact_source_copy'];sources.setdefault(p,rows(base/p));items=sources[p]
 if r['generation'].startswith('EXT'):
  candidates=[x for x in items if (x['sequence_id'],x['method_id'],x['support'],x['source_row_key'])==(r['sequence_id'],r['internal_method_id'],r['support_role'],r['source_row_key'])]
  pairs=[('sequence_id','sequence_id'),('internal_method_id','method_id'),('support_role','support'),('status','status'),('expected_denominator','paired_epoch_denominator'),('matched_count','scored_count'),('heading_RMSE_deg','rmse_deg')]
 else:
  role=r['source_row_key'].split('/')[0];support=r['support_role'].split(' /')[1]
  candidates=[x for x in items if (x['sequence_id'],x['method_id'],x['support'],x.get('support_role',''))==(r['sequence_id'],r['internal_method_id'],support,role)]
  pairs=[('sequence_id','sequence_id'),('internal_method_id','method_id'),('status','status'),('expected_denominator','expected_epoch_count'),('matched_count','matched_epoch_count'),('H_RMSE_m','horizontal_rmse_m'),('V_RMSE_m','vertical_rmse_m'),('3D_RMSE_m','position_3d_rmse_m'),('heading_RMSE_deg','yaw_rmse_deg')]
 assert len(candidates)==1,(r['generation'],r['source_row_key'])
 for dst,src in pairs:assert r[dst]==candidates[0][src];checked+=1
assert len(assets)==33 and copies==20 and len(metrics)==126 and checked==1008
story=(base/'CURRENT_STORY_INDEX.md').read_text();assert '1.886272/1.933770/2.433815' in story
review={'reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_files':34,'prior_frozen_files_unchanged':56,'source_pins':33,'byte_copies':20,'metric_rows':126,'exact_identity_numeric_token_fields':checked,'new_story_fully_read':True,'final_entry_canonical_yaw_checked':True,'science_or_raw_reference_calls':0,'all_checks_passed':True}
(out/'V3_COMPARISON_STORY_ROOT_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
paths=[(base/p).relative_to(repo).as_posix() for p in ready['new_file_pins_excluding_self']]+[(base/'FOURTH_BLOCK_READY_RECEIPT.json').relative_to(repo).as_posix()]
request={'id':'V3_FULL_COMPARISON_STORY','message':'docs(v3): complete external comparison inventory and evidence boundaries','paths':paths}
(out/'V3_FULL_COMPARISON_STORY_COMMIT_REQUEST.json').write_text(json.dumps(request,indent=2)+'\n')
print(json.dumps(review))
