from pathlib import Path
import csv,json,hashlib,zipfile,math
s=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z');out=Path('/mnt/g/LegSA-GINS-project/修复_20261004/EXT_MEASURAND_DIAGNOSTIC');roots=json.loads((s/'LOCAL_ROOTS.json').read_text())['aliases']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def resolve(v):
 for a,r in sorted(roots.items(),key=lambda x:-len(x[0])):
  if v==a or v.startswith(a+'/'):return Path(r+v[len(a):])
 raise ValueError(v)
seal=json.loads((s/'ALL_NATIVE_SEALED.json').read_text());pr=json.loads((s/'PREREGISTRATION.json').read_text());assert sha(s/'ALL_NATIVE_SEALED.json')=='3af7f0c6d010d83c2ea6763f97189ae702cb761d374cb7410ce9fd51c14423ab'
assert seal['new_native_count']==3 and seal['reused_original_full_batch_native_count']==6 and seal['new_evaluator_count_at_seal']==0 and seal['new_native_reference_opens']==seal['reused_original_native_reference_opens']==0
for name,key in [('PREREGISTRATION.json','protocol_sha256'),('NATIVE_JOURNAL.json','native_journal_sha256'),('BY2_NO_RESTART_CONTROL.json','control_receipt_sha256')]:assert sha(s/name)==seal[key]
assert pr['registered_commit']=='9d80ef33b3a40914cfa92f41835419d62152fa88' and len(pr['execution_source_hashes'])==872
for seq,methods in seal['comparison_identities'].items():
 for method,b in methods.items():
  path=resolve(b['path']);assert sha(path/'RUN.json')==b['run_json_sha256'];run=json.loads((path/'RUN.json').read_text());assert sha(path/'ACCESS.json')==b['access_sha256']
  for n,h in run['output_hashes'].items():assert sha(path/n)==h
  access=json.loads((path/'ACCESS.json').read_text())
  if method=='OISAM':
   assert run['planned_blocks']==run['attempted_blocks']=={'BY2':1,'BY2H':3,'BY2O':7}[seq]
   trace=s/'logs'/(seq+'_NATIVE_OPENAT.strace');assert sha(trace)==access['strace_sha256'];text=trace.read_text()
   for ref in access['reference_paths']:assert ref not in text and Path(ref).name not in text,'REFERENCE path in new native strace'
   assert access['actual_reference_opens']==access['actual_reference_open_attempts']==0
   pins={**run['implementation_source_hashes'],pr['method_config_path']:pr['method_config_sha256'],pr['execution_contract_path']:pr['execution_contract_sha256']}
   with zipfile.ZipFile(path/'SOURCE_SNAPSHOT.zip') as z:
    assert len(z.namelist())==874 and set(z.namelist())==set(pins)
    for n,h in pins.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
  else:assert access['reference_payload_opens']==0 and access['passed'] is True
old=resolve(pr['BY2_control_original']['path']);new=s/'runs/BY2/OISAM/SEGMENTED_DIAGNOSTIC'
a=list(csv.DictReader((old/'STATES.csv').open()));b=list(csv.DictReader((new/'STATES.csv').open()));assert len(a)==len(b)==285
for x,y in zip(a,b):
 for k,v in x.items():
  if k=='status':assert v==y[k]
  else:
   u,w=float(v or 'nan'),float(y[k] or 'nan');assert u==w or (math.isnan(u) and math.isnan(w))
a=[json.loads(x) for x in (old/'SOLVER_EVENTS.jsonl').read_text().splitlines()];b=[json.loads(x) for x in (new/'SOLVER_EVENTS.jsonl').read_text().splitlines()];assert len(a)==len(b)
for x,y in zip(a,b):assert x=={k:y[k] for k in x}
record={'schema':'root.all-native.seal.review.v1','all_required_new_FGO_natives_sealed':True,'reviewed_native_seal_path':str(s/'ALL_NATIVE_SEALED.json'),'reviewed_native_seal_sha256':sha(s/'ALL_NATIVE_SEALED.json'),'new_native_count':3,'reused_original_full_batch_count':6,'reference_opens_new_and_reuse':0,'preregistered_blocks_attempted':{'BY2':1,'BY2H':3,'BY2O':7},'source_snapshot_per_member_checks':3*874,'B_control_rows_independent_exact_checked':285,'original_solver_events_exact_checked':len(a),'new_native_strace_literal_reference_paths_and_basenames_absent':True,'reviewer_raw_reference_reads':0,'reviewer_native_invocations':0,'review_source_sha256':sha(Path(__file__)),'scope':'native identity and access; not a truth/accuracy certificate'}
(out/'ROOT_NATIVE_SEAL_REVIEW.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
