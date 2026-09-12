"""P-03 detached execution: independent integrity, generation, solver and evaluation phases."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import sys
import yaml
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from ..clean5_sequence.registry import load_registry
from ..clean5_sequence.generation_audit import selected_lock,open_records,audit_records
from ..clean5_sequence.io_audit import audited_open_records,write_scope_audit
from ..clean5_sequence.solver_runner import raw_checkpoint_worker,execution_state
from .runtime import resolve,write_json,run_ladder,run_order,verify_bundle,EXE_SHA


def _args(argv):
    p=argparse.ArgumentParser()
    p.add_argument('--code-root',type=Path,required=True);p.add_argument('--code-freeze-commit',required=True)
    p.add_argument('--paths-config',type=Path,required=True);p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--_phase',choices=['checkpoint','providers']);p.add_argument('--audit-dir',type=Path)
    p.add_argument('--checkpoint',choices=['pre_run','post_run'])
    return p.parse_args(argv)


def traced_child(args,registry,stage,phase,*,checkpoint=None):
    auditdir=stage/'01_EXECUTION_AUDIT'/phase;auditdir.mkdir(parents=True,exist_ok=False)
    log=auditdir/'OPENAT.strace'
    command=[shutil.which('strace') or 'strace','-f','-qq','-yy','-s','4096','-e','trace=openat','-o',str(log),
        sys.executable,'-B',str(registry.code_root/'scripts/paper_rebuild/clean5_run_imu_parity.py'),
        '--code-root',str(registry.code_root),'--code-freeze-commit',args.code_freeze_commit,
        '--paths-config',str(args.paths_config),'--executable',str(args.executable),
        '--_phase','checkpoint' if checkpoint else 'providers','--audit-dir',str(auditdir)]
    if checkpoint:command+=['--checkpoint',checkpoint]
    completed=run_process_group(command,cwd=registry.code_root,timeout_seconds=1800,
        timeout_message='P03 phase timeout; no retry',launch_failure_message='P03 phase launch failed')
    (auditdir/'stdout.log').write_text(completed.stdout);(auditdir/'stderr.log').write_text(completed.stderr)
    expected=({registry.raw_root/p for p in selected_lock(registry,registry.sequences['BY2'])['rows']} if checkpoint else
              {registry.sequences['BY2'].body_path,registry.sequences['BY2'].fix_root/'gnss1-status.csv'})
    audit=audit_records(open_records(log,registry.code_root),registry.raw_root,expected,checkpoint_phase=bool(checkpoint))
    allowed=[auditdir] if checkpoint else [auditdir,stage/'02_PARITY_PROVIDERS',stage/'00_AUDITS']
    scope=write_scope_audit(audited_open_records(log,registry.code_root),raw_root=registry.raw_root,
        allowed_write_roots=allowed,clean_root=registry.clean_root)
    audit.update(exit_code=completed.returncode,write_scope=scope,command=command,strace_sha256=sha256_file(log),
        data_mode='real_by2_raw',synthetic_data_used=False,semisynthetic_data_used=False)
    audit['pass']=audit['pass'] and scope['pass'] and completed.returncode==0
    write_json(auditdir/'PHASE_AUDIT.json',audit)
    if not audit['pass']:raise RuntimeError('P03 '+phase+' failed: '+completed.stderr[-1500:])
    print('P03 '+phase+': PASS',flush=True)
    return audit


def validate_seal(stage,records):
    seal=json.loads((stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json').read_text())
    if seal['records']!=records:raise ValueError('P03 sealed run identities changed')
    for relative,digest in seal['files_sha256'].items():
        rel=Path(relative);path=stage/rel
        if rel.is_absolute() or '..' in rel.parts or path.is_symlink():raise ValueError('Unconfined P03 sealed artifact')
        if sha256_file(path)!=digest:raise ValueError('P03 sealed artifact changed: '+relative)
    return sha256_file(stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json')


def evaluation_gate(evaluation,records):
    expected={(v,r['run_id']) for v in ('v2','v3') for r in records}
    actual={(g['version'],g['run_id']):g['status'] for g in evaluation.get('new_run_gates',[])}
    passed=(len(records)==6 and len(actual)==12 and set(actual)==expected and
            all(status=='COMPLETED' for status in actual.values()) and evaluation.get('original_numeric_fields_unchanged') is True)
    for version in ('v2','v3'):
        available={r['run_id'] for r in evaluation.get('body_frame_bias',{}).get(version,[]) if r.get('status')=='AVAILABLE'}
        passed=passed and {r['run_id'] for r in records}<=available
    return {'pass':passed,'required_new_evaluations':12,'completed_new_evaluations':sum(v=='COMPLETED' for v in actual.values())}


def generate_provider_phase(*,registry,stage,contract,code_commit):
    """Generator owns the sole exclusive bundle write; runner validates the handoff."""
    from .providers import generate_providers
    bundle=generate_providers(registry=registry,stage_root=stage,contract=contract,code_commit=code_commit)
    persisted=json.loads((Path(stage)/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json').read_text())
    if persisted!=bundle:raise ValueError('Generator bundle return/file mismatch')
    return bundle


def main(argv=None):
    args=_args(argv);os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['GIT_OPTIONAL_LOCKS']='0'
    registry=load_registry(args.code_root/'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',args.paths_config)
    registry=replace(registry,code_root=args.code_root.resolve())
    state=execution_state(registry.code_root,args.code_freeze_commit)
    if sha256_file(args.executable)!=EXE_SHA:raise ValueError('P03 frozen executable mismatch')
    contractpath=registry.code_root/'configs/paper_rebuild/clean5/CLEAN5_PARITY_CONTRACT.yaml'
    contract=yaml.safe_load(contractpath.read_text())
    if contract.get('contract_version')!=3:raise ValueError('P03 requires preregistered contract v3')
    run_order(contract);stage=resolve(contract['p03']['stage_root'],registry)
    if args._phase=='checkpoint':
        raw_checkpoint_worker(registry,registry.sequences['BY2'],args.checkpoint,args.audit_dir);return 0
    if args._phase=='providers':
        generate_provider_phase(registry=registry,stage=stage,contract=contract,code_commit=args.code_freeze_commit)
        return 0
    stage.mkdir(parents=True,exist_ok=True)
    if (stage/'P03_EXECUTION_STARTED.json').exists():raise FileExistsError('P03 already attempted; no retry')
    if any((stage/name).exists() for name in ('01_EXECUTION_AUDIT','02_PARITY_PROVIDERS','03_PARITY_RUNS','04_PARITY_SEAL','07_OFFLINE_EVALUATION','08_AGGREGATE')):
        raise FileExistsError('P03 execution outputs already exist')
    from .evaluation import load_reference,evaluate_ladder
    reference,reference_identity=load_reference(registry,contract)
    write_json(stage/'P03_EXECUTION_STARTED.json',{'code_commit':args.code_freeze_commit,'code_state':state,
        'contract_sha256':sha256_file(contractpath),'reference_summary':reference_identity,'run_order':run_order(contract),
        'solver_limit':6,'new_evaluator_limit':12,'retry_count':0,'data_mode':'real_by2_raw','synthetic_data_used':False,
        'semisynthetic_data_used':False})
    audits={};records=[]
    try:
        audits['pre_generation']=traced_child(args,registry,stage,'pre_generation',checkpoint='pre_run')
        audits['providers']=traced_child(args,registry,stage,'providers')
        audits['post_generation']=traced_child(args,registry,stage,'post_generation',checkpoint='post_run')
        bundle=json.loads((stage/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json').read_text());verify_bundle(bundle)
        audits['pre_solver']=traced_child(args,registry,stage,'pre_solver',checkpoint='pre_run')
        records=run_ladder(registry=registry,stage_root=stage,contract=contract,provider_bundle=bundle,
            executable=args.executable,code_commit=args.code_freeze_commit)
        audits['post_solver']=traced_child(args,registry,stage,'post_solver',checkpoint='post_run')
        verify_bundle(bundle);sealhash=validate_seal(stage,records)
        if len(records)==6 and all(r['terminal_status']=='COMPLETED' for r in records):
            evaluation=evaluate_ladder(registry=registry,stage_root=stage,contract=contract,run_records=records,
                code_commit=args.code_freeze_commit,baseline_median_m=bundle['baseline_median_m'])
        else:evaluation={'status':'NOT_EXECUTED_SOLVER_GATE_FAILED'}
        if execution_state(registry.code_root,args.code_freeze_commit)!=state:raise RuntimeError('P03 snapshot changed')
        if sha256_file(Path(reference_identity['path']))!=reference_identity['sha256']:raise RuntimeError('P02 reference changed')
        gate=evaluation_gate(evaluation,records)
        terminal={'status':'COMPLETED_WITH_P02_V2E_UNAVAILABLE' if gate['pass'] else 'PARTIAL',
            'code_commit':args.code_freeze_commit,'run_count':len(records),'completed_runs':sum(r['terminal_status']=='COMPLETED' for r in records),
            'runs':records,'evaluation':evaluation,'evaluation_gate':gate,'audits':audits,'output_seal_sha256':sealhash,
            'reference_summary':reference_identity,'retry_count':0,'data_mode':'real_by2_raw','synthetic_data_used':False,
            'semisynthetic_data_used':False,'selected_variant':'V2is'}
        write_json(stage/'P03_TERMINAL.json',terminal)
        print(json.dumps({'status':terminal['status'],'run_count':len(records),'new_evaluations':gate['completed_new_evaluations']}),flush=True)
        return 0 if gate['pass'] else 3
    except Exception as exc:
        write_json(stage/'P03_FAILURE.json',{'status':'FAILED','error':str(exc),'code_commit':args.code_freeze_commit,
            'completed_run_records':records,'audits':audits,'retry_count':0,'data_mode':'real_by2_raw','synthetic_data_used':False,
            'semisynthetic_data_used':False})
        raise
