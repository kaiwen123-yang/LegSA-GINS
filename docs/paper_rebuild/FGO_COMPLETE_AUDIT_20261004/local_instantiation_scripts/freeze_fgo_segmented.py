import argparse,json,pathlib,datetime,sys,subprocess
parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True);args=parser.parse_args();stage=pathlib.Path(args.stage);roots=json.loads((stage/'LOCAL_ROOTS.json').read_text())['aliases'];code=pathlib.Path(roots['<CODE_ROOT>']);sys.path.insert(0,str(code/'src'))
from legsa_gins.paper_rebuild.fgo_comparison.raw_inputs import sha256,dump
from legsa_gins.paper_rebuild.fgo_comparison.evaluation import resolve
assert not (stage/'runs').exists() and not (stage/'evaluation').exists()
p=json.loads((stage/'DRAFT_PREREGISTRATION.json').read_text());assert p['status']=='DRAFT_INPUT_PREPARATION';oldpins=p['execution_source_hashes'];files=sorted((code/'src/legsa_gins').rglob('*.py'))+sorted((code/'src/legsa_gins/paper_rebuild/fgo_comparison').glob('*.cc'))+sorted((code/'src/legsa_gins/paper_rebuild/fgo_comparison').glob('*.c'))
newpins={str(f.relative_to(code)):sha256(f) for f in files}
for name in ('src/legsa_gins/paper_rebuild/fgo_comparison/oisam_inputs.py','src/legsa_gins/datasets/by2/go2_body_state_parser.py'):assert newpins[name]==oldpins[name], 'Original sensor reader changed after input preparation'
assert sha256(code/p['method_config_path'])==p['method_config_sha256'];assert sha256(code/p['execution_contract_path'])==p['execution_contract_sha256']
helper=pathlib.Path('/mnt/g/LegSA-GINS-project/修复_20261004/run_fgo_segmented_native.py')
p.update(status='PREREGISTERED',preregistered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),registered_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=code,text=True).strip(),execution_source_hashes=newpins,native_controller_sha256=sha256(helper),preparation_helper_sha256=sha256(pathlib.Path('/mnt/g/LegSA-GINS-project/修复_20261004/prepare_fgo_segmented.py')),registration_helper_sha256=sha256(__file__),draft_protocol_sha256=sha256(stage/'DRAFT_PREREGISTRATION.json'),source_overlay_changed_since_input_draft=[name for name,h in newpins.items() if oldpins.get(name)!=h],input_sensor_reader_before_final_freeze_unchanged=True,prepare_source_before_after_whole_package_not_claimed=True)
p['reuse_access_sha256']={}
for seq,methods in p['reused_full_batch_identities'].items():
 p['reuse_access_sha256'][seq]={}
 for method,binding in methods.items():
  path=resolve(binding['path'],roots);assert sha256(path/'RUN.json')==binding['run_json_sha256'];access=json.loads((path/'ACCESS.json').read_text());assert access['reference_payload_opens']==0 and access['passed'];p['reuse_access_sha256'][seq][method]=sha256(path/'ACCESS.json')
p['final_test_receipt_sha256']=sha256(pathlib.Path('/mnt/g/LegSA-GINS-project/修复_20261004/FGO_SEGMENTED_FINAL_METADATA_CODE_GATES.json'))
assert not (stage/'PREREGISTRATION.json').exists();dump(stage/'PREREGISTRATION.json',p)
print('PREREGISTERED '+str(stage/'PREREGISTRATION.json')+' source_count='+str(len(newpins))+' native0 evaluator0')
