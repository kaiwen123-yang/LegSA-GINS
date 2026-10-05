import csv,hashlib,json
from pathlib import Path
from profile_candidates import OUT,dist,csvsave,save
body=json.loads((OUT/'BODY_FILE_PROFILE.json').read_text());meta=json.loads((OUT/'ZIP_METADATA_PROFILE.json').read_text());raw=json.loads((OUT/'ZIP_RAW_SELECTED_PROFILE.json').read_text());base=json.loads((OUT/'ZIP_BASELINE_SOURCE_PROFILE.json').read_text())
rates=[];pairs=[]
for b in body:
 rates.append(dict(file=b['file'],frames=b['frames'],complete_all_fields=b['complete_expected_fields_rows'],first_t=b['first_t'],last_t=b['last_t'],first_UTC=b['first_utc_interpretation'],last_UTC=b['last_utc_interpretation'],elapsed_s=b['elapsed_s'],mean_observed_rate_Hz=(b['frames']-1)/b['elapsed_s'],median_dt_s=b['positive_dt']['p50'],min_dt_s=b['positive_dt']['min'],max_dt_s=b['positive_dt']['max'],clock_backward=b['backward_clock_rows'],duplicate_time=b['duplicate_timestamp_rows'],gaps_gt_100ms=b['gaps_gt_0p1_n'],quaternion_rpy_assumed_rad_max_component_rmse=max(b['quat_to_rpy_assumed_rad_rmse']['wxyz']),quaternion_xyzw_min_component_rmse=min(b['quat_to_rpy_assumed_rad_rmse']['xyzw']),sha256=b['sha256']))
 for m in meta:
  if not m['member'].endswith('gnss1-status.csv'):continue
  a=m['times']['measurement_header'];overlap=max(0,min(b['last_t'],a['last'])-max(b['first_t'],a['first']));pairs.append(dict(body_file=b['file'],receiver_folder=m['member'].split('/')[0],overlap_s=overlap,body_span_s=b['elapsed_s'],receiver_span_s=a['span'],body_minus_GNSS_first_stamp_s=b['first_t']-a['first'],body_minus_GNSS_last_stamp_s=b['last_t']-a['last'],clock_domain='body_stamp_vs_receiver_status_header; no offset fit',pairing_qualification='TIME_COVERAGE_CANDIDATE_ONLY' if overlap>0 else 'NO_CLOCK_OVERLAP'))
csvsave('BODY_TIME_QUALITY_SUMMARY.csv',rates);csvsave('CANDIDATE_PAIRING_ALL64.csv',pairs);csvsave('CANDIDATE_PAIRING_SELECTED8.csv',[x for x in pairs if x['overlap_s']>0]);assert sum(x['overlap_s']>0 for x in pairs)==8
q=[]
for p in base:
 folder=p['folder'];r1=next(x for x in raw if x['member']==folder+'gnss1-raw.csv');r2=next(x for x in raw if x['member']==folder+'gnss2-raw.csv');g=lambda r:sum(v for k,v in r['PVT_fix_carrier_counts'].items() if k=='(3, True, 2)')
 q.append(dict(receiver_folder=folder.rstrip('/'),GNSS1_PVT=r1['PVT_unique_itow'],GNSS2_PVT=r2['PVT_unique_itow'],GNSS1_fixed_valid=g(r1),GNSS2_fixed_valid=g(r2),HP_exact_itow_pairs=p['HP_exact_itow_pairs'],both_fixed_valid_exact_pairs=p['HP_PVT_exact_both_fixed_valid_pairs'],eligible_length_median_m=p['HP_both_fixed_length_m'].get('p50'),eligible_length_p01_m=p['HP_both_fixed_length_m'].get('p01'),eligible_length_p99_m=p['HP_both_fixed_length_m'].get('p99'),HP_flags_all_zero=all(set(r['HP_flag_counts'])=={'0'}for r in [r1,r2]),RAWX_GNSS1=r1['message_counts'].get('UBX-RXM-RAWX',0),RAWX_GNSS2=r2['message_counts'].get('UBX-RXM-RAWX',0),MON_VER_messages=len(r1['MON_VER'])+len(r2['MON_VER'])))
csvsave('GNSS_QUALITY_BASELINE_SUMMARY.csv',q)
lock=Path('G:/LegSA-GINS-project/clean_rebuild_202607/01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv');register=list(csv.DictReader(lock.open(encoding='utf-8-sig')));bysha={}
for r in register:bysha.setdefault(r['sha256'],[]).append(r)
identity=[dict(kind='body_txt',name=x['file'],sha256=x['sha256'])for x in body]+[dict(kind='ZIP_member_GNSS_raw',name=x['member'],sha256=x['sha256'])for x in raw]
container=json.loads((OUT/'ZIP_CONTAINER_IDENTITY.json').read_text());identity.append(dict(kind='ZIP_container',name=container['path'],sha256=container['sha256']))
hits=[]
for x in identity:
 old=bysha.get(x['sha256'],[])
 if old:
  for r in old:hits.append({**x,'match':True,'historical_relative_path':r['relative_path'],'historical_dataset':r['dataset'],'historical_role':r['role']})
 else:hits.append({**x,'match':False,'historical_relative_path':'','historical_dataset':'','historical_role':''})
csvsave('HISTORICAL_SOURCE_HASH_MATCHES.csv',hits)
small=json.loads((OUT/'ZIP_SMALL_METADATA.json').read_text());save('ZIP_TF_STATIC_SOURCE_TEXT.json',[x for x in small if x['member'].endswith('/tf_static.csv')]);save('ZIP_NTRIP_METADATA_IDENTITY.json',[{k:x[k]for k in ['member','bytes','sha256']}for x in small if x['member'].endswith('/ntrip-info.csv')])
save('DERIVED_PROFILE_SCOPE.json',dict(raw_lock_path=str(lock),raw_lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest(),raw_lock_rows=len(register),source_identity_count=len(identity),hash_matched_identity_count=sum(bool(bysha.get(x['sha256']))for x in identity),pairing_rows64=len(pairs),positive_overlap_pairs8=8,scientific_executions=0,offset_or_alignment_selected=False,reference_errors_calculated=False))
print(json.dumps({'body':rates,'gnss':q,'hashmatches':[(x['name'],x['match'],x['historical_dataset'])for x in hits]},ensure_ascii=False,indent=2))
