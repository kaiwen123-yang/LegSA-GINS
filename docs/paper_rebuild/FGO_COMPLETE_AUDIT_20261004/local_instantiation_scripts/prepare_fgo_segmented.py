from pathlib import Path
import argparse, json, datetime, sys, hashlib, subprocess
parser=argparse.ArgumentParser();parser.add_argument('--code',required=True);parser.add_argument('--old-roots',required=True);parser.add_argument('--output-parent',required=True);args=parser.parse_args()
code=Path(args.code);sys.path.insert(0,str(code/'src'))
from legsa_gins.paper_rebuild.fgo_comparison.raw_inputs import sha256,dump,portable
from legsa_gins.paper_rebuild.fgo_comparison.runner import deny_reference_access
from legsa_gins.paper_rebuild.fgo_comparison.oisam_inputs import read_sequence
from legsa_gins.paper_rebuild.fgo_comparison.segmented_diagnostic import partition_intervals
old=json.loads(Path(args.old_roots).read_text());roots=old['aliases'];deny_reference_access(roots)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');stage=Path(args.output_parent)/('FGO_SEGMENTED_DIAGNOSTIC_'+stamp);stage.mkdir(exist_ok=False);(stage/'logs').mkdir()
roots={**roots,'<FGO_DIAGNOSTIC_ROOT>':str(stage)}
method='configs/paper_rebuild/fgo_comparison/OISAM_PAPER_CONTRACT_20261004.json';contract='configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml';cfg=json.loads((code/method).read_text())
rootpath=stage/'LOCAL_ROOTS.json';dump(rootpath,{'aliases':roots})
blocks,metadata={},{}
for seq in ('BY2','BY2H','BY2O'):
 print('READ_INPUT '+seq,flush=True);data=read_sequence(rootpath,seq,cfg);blocks[seq],assignment=partition_intervals(data.imu_intervals,data.nodes,cfg['maximum_imu_interval_s']);metadata[seq]=data.metadata
 print('INPUT_DONE '+seq+' blocks='+str(len(blocks[seq]))+' nodes='+str(len(data.nodes)),flush=True)
assert {s:len(v) for s,v in blocks.items()}=={'BY2':1,'BY2H':3,'BY2O':7}
files=sorted((code/'src/legsa_gins').rglob('*.py'))+sorted((code/'src/legsa_gins/paper_rebuild/fgo_comparison').glob('*.cc'))+sorted((code/'src/legsa_gins/paper_rebuild/fgo_comparison').glob('*.c'))
pins={str(p.relative_to(code)):sha256(p) for p in files}
reused={}
for seq in blocks:
 reused[seq]={}
 for method_id in ('WEN_TC','GNC'):
  path=Path(old['aliases']['<FGO_ROOT>'])/'runs'/seq/method_id/'PAPER_CONTRACT';run=json.loads((path/'RUN.json').read_text())
  for name,digest in run['output_hashes'].items():assert sha256(path/name)==digest
  for name,digest in run['implementation_source_hashes'].items():assert sha256(path/'SOURCE_SNAPSHOT'/name)==digest
  reused[seq][method_id]={'path':portable(path,roots),'run_json_sha256':sha256(path/'RUN.json'),'states_sha256':sha256(path/'STATES.csv'),'native_reference_opens':0,'original_source_hashes':run['implementation_source_hashes'],'old_identity_not_relabelled_as_new_source':True}
control=Path(old['aliases']['<FGO_ROOT>'])/'runs/BY2/OISAM/PAPER_CONTRACT'
bridge=Path(roots['<FGO_BUILD>'])/'libobgins_bridge.so'
protocol={'schema':'fgo.segmented.preregistration.v1','status':'DRAFT_INPUT_PREPARATION','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage_id':stage.name,'baseline_commit_at_preparation':subprocess.check_output(['git','rev-parse','HEAD'],cwd=code,text=True).strip(),'execution_source_hashes':pins,'source_identity_scope':'entire Python package plus FGO C/C++ identity superset, not a claim all files execute','method_config_path':method,'method_config_sha256':sha256(code/method),'execution_contract_path':contract,'execution_contract_sha256':sha256(code/contract),'bridge_sha256':sha256(bridge),'bridge_build_receipt_sha256':sha256(bridge.with_suffix('.build.json')),'new_native_sequences':['BY2','BY2H','BY2O'],'new_native_count':3,'reused_full_batch_native_count':6,'block_plan':blocks,'input_metadata':metadata,'reused_full_batch_identities':reused,'BY2_control_original':{'path':portable(control,roots),'run_json_sha256':sha256(control/'RUN.json'),'states_sha256':sha256(control/'STATES.csv'),'events_sha256':sha256(control/'SOLVER_EVENTS.jsonl')},'BY2_control_comparison':{'all_state_numeric_columns':'exact array_equal with equal_nan; no reference scores','status_and_all_original_solver_event_fields':'exact equality ignoring added block/history metadata','fail_gate':'any changed numeric or original event field prevents offline evaluation until cause review'},'target_epoch_diagnostics':{'BY2O':3286.0},'lever_imu_to_gnss1_frd_m':cfg['lever_imu_to_gnss1_frd_m'],'block_failure_policy':'ALL_PREDECLARED_BLOCKS_ATTEMPTED; no within-block numerical or input-driven reset; later starts only at pre-existing source gaps','primary_support':'PRIMARY_DYNAMIC_ONLY excludes every successful INITIALIZED prior-only row, keeps denominator','secondary_support':'SECONDARY_ALL_VALID_POSITION includes valid prior rows explicitly','formal_denominators':{'BY2':275,'BY2H':271,'BY2O':378},'comparison_physical_point':'GNSS1_ANTENNA using OWN Oi attitude/lever, same GNSS1 reference','common_nominal_key_tolerance_s':.005,'output_interpolation':False,'reference_read_rule':'all three new native plus six reused identities sealed before first offline reference open','new_stage_budget_bytes':256*1024**2,'E_incremental_budget_bytes':64*1024**2,'no_performance_or_reference_tuning':True,'initialization_role':'one A1 sensor prior per independently preregistered real-gap block, each exact input/timestamp logged','singleton_policy':'attempt/init logged, prior-only excluded from primary dynamical support','strict_prior_results_unchanged':True}
dump(stage/'DRAFT_PREREGISTRATION.json',protocol)
dump(Path(args.output_parent)/'FGO_SEGMENTED_CURRENT_PREPARATION.json',{'stage':str(stage),'roots_path':str(rootpath),'draft_protocol':str(stage/'DRAFT_PREREGISTRATION.json'),'source_count':len(pins),'blocks':{s:len(v) for s,v in blocks.items()},'native_count':0,'evaluator_count':0})
print('PREPARED '+str(stage)+' source_count='+str(len(pins)),flush=True)
