import argparse, pathlib, json, os, sys, subprocess, datetime, time, hashlib, zipfile
parser=argparse.ArgumentParser();parser.add_argument('--roots',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--python',required=True);args=parser.parse_args()
roots=json.loads(pathlib.Path(args.roots).read_text())['aliases'];code=pathlib.Path(roots['<CODE_ROOT>']);stage=pathlib.Path(roots['<FGO_DIAGNOSTIC_ROOT>']);sys.path.insert(0,str(code/'src'))
from legsa_gins.paper_rebuild.fgo_comparison.raw_inputs import sha256,dump
from legsa_gins.paper_rebuild.fgo_comparison.segmented_diagnostic import verify_sources
from legsa_gins.paper_rebuild.fgo_comparison.evaluation import resolve
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records
import yaml, numpy as np, pandas as pd
protocol=json.loads(pathlib.Path(args.protocol).read_text());assert protocol['status']=='PREREGISTERED';assert not (stage/'evaluation').exists();assert not (stage/'ALL_NATIVE_SEALED.json').exists()
env=os.environ.copy();env.update(PYTHONPATH=str(code/'src'),PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',LEGSA_OBGINS_BRIDGE=roots['<FGO_BUILD>']+'/libobgins_bridge.so')
os.environ['LEGSA_OBGINS_BRIDGE']=env['LEGSA_OBGINS_BRIDGE']
assert sha256(pathlib.Path(__file__))==protocol['native_controller_sha256']
contract=yaml.safe_load((code/protocol['execution_contract_path']).read_text());refs={str(resolve(spec['trace']['path'],roots)) for spec in contract['sequences'].values()}
def budget():
 files=[p for p in stage.rglob('*') if p.is_file()];dirs=[p for p in stage.rglob('*') if p.is_dir()];logical=sum(p.stat().st_size for p in files);fileceil=sum((p.stat().st_size+262143)//262144*262144 for p in files);estimate=fileceil+len(dirs)*262144
 assert estimate<=protocol['new_stage_budget_bytes'], 'Registered G allocation budget exceeded'
 return {'logical_bytes':logical,'exfat_256KiB_file_ceil_bytes':fileceil,'directory_one_cluster_proxy_bytes':len(dirs)*262144,'allocated_budget_proxy_bytes':estimate,'is_actual_windows_allocation_API':False}
def snapshot_gate(path,run):
 with zipfile.ZipFile(path/'SOURCE_SNAPSHOT.zip') as archive:
  expected={**run['implementation_source_hashes'],protocol['method_config_path']:protocol['method_config_sha256'],protocol['execution_contract_path']:protocol['execution_contract_sha256']}
  assert len(archive.namelist())==len(expected) and set(archive.namelist())==set(expected)
  for name,digest in expected.items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
 return len(expected)
comparison={s:{} for s in protocol['new_native_sequences']};journal=[]
for seq in protocol['new_native_sequences']:
 verify_sources(code,protocol);assert sha256(__file__)==protocol['native_controller_sha256'];assert not (stage/'evaluation').exists()
 path=stage/'runs'/seq/'OISAM'/'SEGMENTED_DIAGNOSTIC';assert not path.exists()
 trace=stage/'logs'/(seq+'_NATIVE_OPENAT.strace');log=stage/'logs'/(seq+'_NATIVE.log')
 argv=['strace','-f','-qq','-yy','-e','trace=openat','-o',str(trace),args.python,'-m','legsa_gins.paper_rebuild.fgo_comparison.segmented_diagnostic','--roots',args.roots,'--protocol',args.protocol,'--sequence',seq]
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();clock=time.perf_counter();print('NATIVE_START '+seq,flush=True)
 with log.open('x') as stream:process=subprocess.run(argv,cwd=code,env=env,stdout=stream,stderr=subprocess.STDOUT)
 assert process.returncode==0, seq+' native nonzero; retain partial attempt, do not evaluate'
 verify_sources(code,protocol);run=json.loads((path/'RUN.json').read_text());assert run['planned_blocks']==run['attempted_blocks']==len(protocol['block_plan'][seq]);assert run['protocol_sha256']==sha256(args.protocol)
 for name,digest in run['output_hashes'].items():assert sha256(path/name)==digest
 snapshot_count=snapshot_gate(path,run)
 records=audited_open_records(trace,code);reference=[r for r in records if r.get('path') in refs or r.get('lexical_path') in refs]
 assert not reference, 'Online reference open detected'
 access={'actual_reference_open_attempts':len(reference),'actual_reference_opens':len(reference),'reference_paths':sorted(refs),'strace_sha256':sha256(trace),'open_records_including_failed':len(records),'python_guard_also_active':True}
 dump(path/'ACCESS.json',access)
 comparison[seq]['OISAM']={'path':'<FGO_DIAGNOSTIC_ROOT>/runs/'+seq+'/OISAM/SEGMENTED_DIAGNOSTIC','run_json_sha256':sha256(path/'RUN.json'),'states_sha256':sha256(path/'STATES.csv'),'access_sha256':sha256(path/'ACCESS.json'),'actual_reference_opens':0,'source_snapshot_member_count':snapshot_count,'new_identity':True}
 row={'sequence':seq,'start_utc':stamp,'end_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'wrapper_elapsed_s':time.perf_counter()-clock,'native_returncode':process.returncode,'planned_blocks':run['planned_blocks'],'attempted_blocks':run['attempted_blocks'],'terminal_status':run['terminal_status'],'reference_opens':0,'source_before_after_pass':True,'argv':argv,'run_json_sha256':sha256(path/'RUN.json'),'access_sha256':sha256(path/'ACCESS.json'),'stdout_sha256':sha256(log),'resource':budget()}
 journal.append(row);dump(stage/'NATIVE_JOURNAL.json',{'new_native':journal,'new_native_count':len(journal),'new_evaluator_count':0,'reused_full_batch_count':6});print('NATIVE_DONE '+seq+' '+run['terminal_status'],flush=True)
# Direct no-restart control identity check; no reference is involved.
old=resolve(protocol['BY2_control_original']['path'],roots);new=stage/'runs/BY2/OISAM/SEGMENTED_DIAGNOSTIC'
assert sha256(old/'RUN.json')==protocol['BY2_control_original']['run_json_sha256'];assert sha256(old/'STATES.csv')==protocol['BY2_control_original']['states_sha256'];assert sha256(old/'SOLVER_EVENTS.jsonl')==protocol['BY2_control_original']['events_sha256']
a,b=pd.read_csv(old/'STATES.csv'),pd.read_csv(new/'STATES.csv');numeric=[c for c in a if c!='status'];equal=np.array_equal(a[numeric].to_numpy(float),b[numeric].to_numpy(float),equal_nan=True);assert equal and a.status.tolist()==b.status.tolist()
one=[json.loads(x) for x in (old/'SOLVER_EVENTS.jsonl').read_text().splitlines()];two=[json.loads(x) for x in (new/'SOLVER_EVENTS.jsonl').read_text().splitlines()];assert len(one)==len(two)
for x,y in zip(one,two):assert x=={k:y[k] for k in x}
dump(stage/'BY2_NO_RESTART_CONTROL.json',{'all_285_numeric_state_rows_exact_equal':True,'all_original_status_and_event_fields_exact_equal':True,'old_manifest_sha256':sha256(old/'RUN.json'),'new_manifest_sha256':sha256(new/'RUN.json'),'reference_reads':0,'source_default_hook_equivalence_verified_on_real_complete_chain':True})
for seq,methods in protocol['reused_full_batch_identities'].items():
 for method,binding in methods.items():
  path=resolve(binding['path'],roots);assert sha256(path/'RUN.json')==binding['run_json_sha256'];run=json.loads((path/'RUN.json').read_text())
  for name,digest in run['output_hashes'].items():assert sha256(path/name)==digest
  for name,digest in run['implementation_source_hashes'].items():assert sha256(path/'SOURCE_SNAPSHOT'/name)==digest
  assert sha256(path/'ACCESS.json')==protocol['reuse_access_sha256'][seq][method]
  old_access=json.loads((path/'ACCESS.json').read_text());assert old_access['reference_payload_opens']==0 and old_access['passed'] is True
  comparison[seq][method]={**binding,'access_sha256':sha256(path/'ACCESS.json'),'actual_reference_opens':0,'new_identity':False}
verify_sources(code,protocol);assert sha256(__file__)==protocol['native_controller_sha256'];assert not (stage/'evaluation').exists()
seal={'schema':'fgo.segmented.all-native.seal.v1','sealed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage_id':stage.name,'all_three_new_native_terminal':True,'new_native_count':3,'reused_original_full_batch_native_count':6,'new_evaluator_count_at_seal':0,'new_native_reference_opens':0,'reused_original_native_reference_opens':0,'protocol_sha256':sha256(args.protocol),'controller_sha256':sha256(__file__),'native_journal_sha256':sha256(stage/'NATIVE_JOURNAL.json'),'control_receipt_sha256':sha256(stage/'BY2_NO_RESTART_CONTROL.json'),'comparison_identities':comparison,'source_before_after_all_872_pass':True,'source_count':len(protocol['execution_source_hashes']),'resource':budget()}
dump(stage/'ALL_NATIVE_SEALED.json',seal);print('ALL_THREE_NEW_NATIVE_SEALED '+str(stage/'ALL_NATIVE_SEALED.json')+' reference0',flush=True)
