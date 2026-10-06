"""Build and verify the public candidate evidence bundle; no estimator/evaluator."""
import csv,hashlib,json,re,subprocess,datetime
from pathlib import Path
from profile_candidates import OUT,ROOT,ZIP,BODY,csvsave,save,sha
body=json.loads((OUT/'BODY_FILE_PROFILE.json').read_text());meta=json.loads((OUT/'ZIP_METADATA_PROFILE.json').read_text());raw=json.loads((OUT/'ZIP_RAW_SELECTED_PROFILE.json').read_text());tfs=json.loads((OUT/'ZIP_FRAME_GRAPH_PROFILE.json').read_text());small=json.loads((OUT/'ZIP_SMALL_METADATA.json').read_text());userio=json.loads((OUT/'ZIP_USERIO_METADATA_PROFILE.json').read_text())
save('BODY_FILE_PROFILE_PUBLIC.json',[{k:v for k,v in x.items()if k!='terminal_prefix'}for x in body])
save('ZIP_USERIO_METADATA_SUMMARY.json',[{k:v for k,v in x.items()if k!='TF_messages'}|{'TF_checked_messages':sum(x['TF_messages'].values())}for x in userio])
end=json.loads((OUT/'BODY_EOF_COMPLETENESS.json').read_text());csvsave('BODY_EOF_COMPLETENESS_SUMMARY.csv',[dict(file=x['file'],last512bytes_sha256=x['last512bytes_sha256'],last_data_frame_terminated=x['file']=='nmb2.txt',last_message_incomplete=x['file']!='nmb2.txt',classification='Complete final data frame then Ctrl-C' if x['file']=='nmb2.txt' else 'Unterminated final data message; do not complete missing characters/fields')for x in end])
pairs=list(csv.DictReader((OUT/'CANDIDATE_PAIRING_SELECTED8.csv').open(encoding='utf-8')));quality=list(csv.DictReader((OUT/'GNSS_QUALITY_BASELINE_SUMMARY.csv').open(encoding='utf-8')))
rows=[]
for pair in pairs:
 q=next(x for x in quality if x['receiver_folder']==pair['receiver_folder']);b=next(x for x in body if x['file']==pair['body_file']);fixed=int(q['both_fixed_valid_exact_pairs'])
 rows.append(dict(candidate_body=pair['body_file'],receiver_folder=pair['receiver_folder'],unique_acquisition_time_match=True,original_clock_overlap_s=pair['overlap_s'],body_IMU='Available; variable real dt; EOF admission required',body_SDK_attitude='Available; wxyz/rad internal consistency; mounting/gauge not calibrated',body_SDK_velocity='Available; frame/POI/internal uncertainty not established by field name',dual_RAWX_and_SFRBX='Present; checked length/checksum; ephemeris coverage not solved',GNSS_PVT_and_HP='Present; quality masks retained',both_fixed_valid_HP_pairs=fixed,A1_frozen_rule='PARTIAL_QUALITY_SUPPORT' if fixed else 'NO_FIXED_SUPPORT_IN_WHOLE_RECORD',absolute_yaw_initialization='Pending chosen frozen admissible epoch' if fixed else 'No A1 fixed-qualified initialization; must preregister unavailable/alternative identity',HV_heading_dependency='Conditional on admissible heading and interface convention' if fixed else 'No frozen A1 support; do not fill commercial yaw',receiver_IMU='Available around202Hz; separate physical sensor',commercial_fused_reference='Present; no independent truth or numerical U proven',actual_POI_VRTK='Recorded identity TF; applicable only these8 acquisitions',GNSS1_GNSS2_body_IMU_levers='Not in these TF messages; nominal CAD/author facts to be linked',body_large_gap_count=b['gaps_gt_0p1_n'],raw_hash_history='Already registered XB_PG; disjoint formalMarch6 source',scene_and_development_role='Author confirmation needed; no new/unseen-site inference',performance_eligibility='CANDIDATE_ONLY_PENDING_PREREG; no new performance row',value='Parameter-transfer/heading-availability validation candidate' if fixed else 'Natural difficult-GNSS/A1-unavailability mechanism candidate'))
csvsave('CANDIDATE_USABILITY_MATRIX.csv',rows)
coverage=[]
for x in body:coverage.append(dict(source=str(BODY/x['file']),bytes=x['bytes'],sha256=x['sha256'],rows_or_frames=x['frames'],scope='FULL_BYTE_STREAM_MACHINE_PROFILE',interpreted='timestamp/numeric/list fields; EOF and repeated values; no manual everyline claim'))
unique={}
for x in meta+raw+tfs+small+userio:unique[x['member']]=x
for member,x in unique.items():
 if '/gnss' in member and member.endswith('-raw.csv'):kind='All byte hash; message counts; PVT/HP/RAWX/SFRBX fields/checksum; no estimator'
 elif member.endswith('/userio-raw.csv'):kind='All byte hash; message names and TF metadata/checksum; odometry payload not decoded for alignment'
 elif member.endswith('/tf.csv'):kind='All byte hash and frame graph identities; dynamic pose not used for alignment'
 elif member.endswith('/tf_static.csv'):kind='All small metadata read; frame graph; no measured robot/antenna extrinsic inferred'
 elif member.endswith('/ntrip-info.csv'):kind='Small metadata hashed; public output only identity; no full source text published'
 else:kind='All byte hash; selected time/status/quality fields and schema; not complete semantic interpretation'
 coverage.append(dict(source='ZIP_MEMBER:'+member,bytes=x['bytes'],sha256=x['sha256'],rows_or_frames=x.get('rows','metadata_or_raw_messages'),scope='COMPLETE_SELECTED_MEMBER_MACHINE_STREAM',interpreted=kind))
assert len(unique)==80
coverage +=[dict(source='ZIP_HEADER_AND_MEMBER_DIRECTORY',bytes=ZIP.stat().st_size,sha256=sha(ZIP),rows_or_frames=176,scope='CONTAINER_HASH_AND_DIRECTORY',interpreted='168 file members listed;80 selected filemembers streamed;88 other filemembers not fully read'),dict(source='first trace member selected preview',bytes=1800,sha256='',rows_or_frames='header/fewrows',scope='SELECTED_FORMAT_PREVIEW_ONLY',interpreted='No errors/offset selection; not full reference read'),dict(source='first POI odometry CSV',bytes='first header/row',sha256='',rows_or_frames=1,scope='SELECTED_SCHEMA_PREVIEW_ONLY',interpreted='frame_id ECEF and child POI; no reference alignment'),dict(source='two preexisting KF outputtxt EOF512 each',bytes=1024,sha256='',rows_or_frames='two selected tails',scope='INCIDENTAL_READ_SCOPE_DECLARED',interpreted='Initial broad EOF glob then restricted to exact8; no old metrics entered new results')]
csvsave('CANDIDATE_READ_COVERAGE.csv',coverage)
actual=json.loads((OUT/'SELECTION_SOURCE_PINS.json').read_text())
formal=[]
for q in actual['source_files']:
 if q['path'].endswith('V3_RUNTIME_CONFIG.yaml'):
  text=Path(q['path'].replace('/mnt/g/','G:/')).read_text(encoding='utf-8'); hashes=re.findall(r'[a-f0-9]{64}',text);formal+=hashes
save('FORMAL_V3_SOURCE_DISJOINTNESS.json',dict(candidate_GNSS_raw_hashes=[x['sha256']for x in raw],actual_formal_config_hash_tokens_examined=len(formal),overlap_with_formal_config_hash_tokens=sorted(set(formal)&{x['sha256']for x in raw}),different_dates_are_not_independent_validation=True,qualification='Exact candidate GNSS raw hashes not present in frozenMarch6 actual3 configs; does not prove research use absent'))
# Keep scientific source / old result pins unchanged across the profiling work.
for q in actual['source_files']:
 path=q['path'];p=Path(path.replace('/mnt/g/','G:/')) if path.startswith('/mnt/g/')else Path('\\\\wsl.localhost\\Ubuntu-22.04'+path.replace('/','\\'))
 assert sha(p)==q['sha256'],path
newinput=[]
for b in body:
 p=BODY/b['file'];digest=sha(p);assert digest==b['sha256'];newinput.append(dict(path=str(p),bytes=p.stat().st_size,sha256=digest))
container=json.loads((OUT/'ZIP_CONTAINER_IDENTITY.json').read_text());assert sha(ZIP)==container['sha256'];newinput.append(dict(path=str(ZIP),bytes=ZIP.stat().st_size,sha256=container['sha256']))
save('CANDIDATE_INPUT_FINAL_HASH_RECHECK.json',dict(inputs=newinput,all_match_original_full_stream=True,individual8_body_and16_GNSS_raw_hashes_match_prior_catalog=True,ZIP_container_catalog_match=False,old_selection_source_pins_unchanged=True,scientific_executions=0))
print('FINAL_INPUT_HASHES_PASS',len(newinput),'selected ZIP members',len(unique))
