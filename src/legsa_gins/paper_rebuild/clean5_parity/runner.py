"""P-02 phase separation, raw checkpoints, serial frozen execution and evaluation."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import yaml
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from ..clean5_sequence.registry import load_registry
from ..clean5_sequence.generation_audit import selected_lock, open_records, audit_records
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..clean5_sequence.solver_runner import raw_checkpoint_worker, execution_state
from .runtime import resolve, write_json, run_ladder, EXE_SHA

def args_parser():
    p=argparse.ArgumentParser()
    p.add_argument('--code-root',required=True,type=Path)
    p.add_argument('--code-freeze-commit',required=True)
    p.add_argument('--paths-config',required=True,type=Path)
    p.add_argument('--executable',required=True,type=Path)
    p.add_argument('--_phase',choices=['checkpoint','providers'])
    p.add_argument('--audit-dir',type=Path)
    p.add_argument('--checkpoint',choices=['pre_run','post_run'])
    return p

def launch(argv,cwd):
    return run_process_group(argv,cwd=cwd,timeout_seconds=1800,
              timeout_message='P02 phase timeout',launch_failure_message='P02 phase failed to start')

def evaluation_gate(evaluation, records):
    """An expected V2e failure never masks an unrelated evaluation failure."""
    needed={r['run_id'] for r in records if r['terminal_status']=='COMPLETED'}
    needed.update(['V0_F01','V0_F03','V0_A04','EXT05C','LC01'])
    actual={(g['version'],g['run_id']):g['status'] for g in evaluation.get('run_gates',[])}
    missing=[f'{version}/{run}' for version in ['v2','v3'] for run in sorted(needed)
             if actual.get((version,run))!='COMPLETED']
    body=evaluation.get('body_frame_bias',{})
    for version in ['v2','v3']:
        available={r['run_id'] for r in body.get(version,[]) if r.get('status')=='AVAILABLE'}
        missing.extend(f'{version}/body/{run}' for run in sorted(needed-available))
    return {'pass':not missing,'missing_or_failed':missing}

def traced_child(args, registry, stage, phase, *, checkpoint=None):
    audit_dir=stage/'01_PARITY_EXECUTION_AUDIT'/phase;audit_dir.mkdir(parents=True,exist_ok=False)
    log=audit_dir/'OPENAT.strace'
    command=[shutil.which('strace') or 'strace','-f','-qq','-yy','-s','4096','-e','trace=openat','-o',str(log),
             sys.executable,'-B',str(registry.code_root/'scripts/paper_rebuild/clean5_run_parity.py'),
             '--code-root',str(registry.code_root),'--code-freeze-commit',args.code_freeze_commit,
             '--paths-config',str(args.paths_config),'--executable',str(args.executable),
             '--_phase','checkpoint' if checkpoint else 'providers','--audit-dir',str(audit_dir)]
    if checkpoint: command+=['--checkpoint',checkpoint]
    completed=launch(command,registry.code_root)
    (audit_dir/'stdout.log').write_text(completed.stdout);(audit_dir/'stderr.log').write_text(completed.stderr)
    print(completed.stdout[-2000:],flush=True)
    expected={registry.raw_root/p for p in selected_lock(registry,registry.sequences['BY2'])['rows']}
    if not checkpoint:
        expected.update(registry.sequences[s].body_path for s in ['BY2H','BY2O'])
    audit=audit_records(open_records(log,registry.code_root),registry.raw_root,expected,checkpoint_phase=bool(checkpoint))
    scope=write_scope_audit(audited_open_records(log,registry.code_root),raw_root=registry.raw_root,
                           allowed_write_roots=[audit_dir,stage/'02_PARITY_PROVIDERS'] if not checkpoint else [audit_dir],
                           clean_root=registry.clean_root)
    audit.update(exit_code=completed.returncode,write_scope=scope,command=command,
                 strace_sha256=sha256_file(log),data_mode='real_by2_raw',synthetic_data_used=False,semisynthetic_data_used=False)
    audit['pass']=audit['pass'] and scope['pass'] and completed.returncode==0
    write_json(audit_dir/'PHASE_AUDIT.json',audit)
    if not audit['pass']:raise RuntimeError(f'{phase} failed: {completed.stderr[-3000:]} {audit.get("failures")}')
    return audit

def main(argv=None):
    args=args_parser().parse_args(argv)
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    os.environ['GIT_OPTIONAL_LOCKS']='0'
    registry=load_registry(args.code_root/'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',args.paths_config)
    registry=replace(registry,code_root=args.code_root.resolve())
    state=execution_state(registry.code_root,args.code_freeze_commit)
    if sha256_file(args.executable)!=EXE_SHA:raise RuntimeError('executable SHA mismatch')
    contract_path=registry.code_root/'configs/paper_rebuild/clean5/CLEAN5_PARITY_CONTRACT.yaml'
    contract=yaml.safe_load(contract_path.read_text())
    if contract.get('contract_version')!=2:raise RuntimeError('P02 requires contract v2')
    stage=resolve(contract['stage_root'],registry)
    if args._phase=='checkpoint':
        raw_checkpoint_worker(registry,registry.sequences['BY2'],args.checkpoint,args.audit_dir)
        return 0
    if args._phase=='providers':
        from .providers import generate_providers
        bundle=generate_providers(registry=registry,stage_root=stage,contract=contract,code_commit=args.code_freeze_commit)
        write_json(stage/'02_PARITY_PROVIDERS'/'PARITY_PROVIDER_BUNDLE.json',bundle)
        print('Provider generation complete',flush=True)
        return 0
    if (stage/'P02_EXECUTION_STARTED.json').exists():raise RuntimeError('P02 already started; no automatic retry')
    write_json(stage/'P02_EXECUTION_STARTED.json',{'state':state,'contract_sha256':sha256_file(contract_path),
                   'code_commit':args.code_freeze_commit,'data_mode':'real_by2_raw','synthetic_data_used':False,
                   'semisynthetic_data_used':False,'solver_limit':8,'v3_authorized':True})
    audits={}
    try:
        audits['pre_generation']=traced_child(args,registry,stage,'pre_generation',checkpoint='pre_run')
        audits['providers']=traced_child(args,registry,stage,'providers')
        audits['post_generation']=traced_child(args,registry,stage,'post_generation',checkpoint='post_run')
        bundle=json.loads((stage/'02_PARITY_PROVIDERS'/'PARITY_PROVIDER_BUNDLE.json').read_text())
        audits['pre_solver']=traced_child(args,registry,stage,'pre_solver',checkpoint='pre_run')
        records=run_ladder(registry=registry,stage_root=stage,contract=contract,provider_bundle=bundle,
                           executable=args.executable,code_commit=args.code_freeze_commit)
        audits['post_solver']=traced_child(args,registry,stage,'post_solver',checkpoint='post_run')
        # Immutable payload and sealed-output checks precede the first reference parse.
        for value in bundle['variants'].values():
            for entry in value['providers'].values():
                if sha256_file(Path(entry['path']))!=entry['sha256']:raise RuntimeError('provider mutation')
        seal=json.loads((stage/'04_PARITY_SEAL'/'PARITY_OUTPUT_SEAL.json').read_text())
        for relative,digest in seal['files_sha256'].items():
            if sha256_file(stage/relative)!=digest:raise RuntimeError('sealed run mutation')
        if len(records)==8 and all(r['terminal_status']=='COMPLETED' for r in records[:7]):
            from .evaluation import evaluate_ladder
            evaluation=evaluate_ladder(registry=registry,stage_root=stage,contract=contract,
                              run_records=records,code_commit=args.code_freeze_commit,baseline_median_m=bundle['baseline_median_m'])
        else:evaluation={'status':'NOT_EXECUTED_PRIOR_RUN_GATE_FAILED'}
        if execution_state(registry.code_root,args.code_freeze_commit)!=state:raise RuntimeError('snapshot mutated')
        gate=evaluation_gate(evaluation,records)
        terminal={'status':'COMPLETE_WITH_V2E_NATIVE_FAILURE' if gate['pass'] and len(records)==8 and records[-1]['terminal_status']=='FAILED_NATIVE_COUNTER_CONTRACT'
                  else 'PASS' if gate['pass'] and len(records)==8 and all(r['terminal_status']=='COMPLETED' for r in records) else 'PARTIAL',
                  'run_count':len(records),'completed_runs':sum(r['terminal_status']=='COMPLETED' for r in records),
                  'runs':records,'evaluation':evaluation,'evaluation_gate':gate,'audits':audits,'code_commit':args.code_freeze_commit,
                  'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False}
        write_json(stage/'P02_TERMINAL.json',terminal)
        print(json.dumps({'terminal':terminal['status'],'runs':len(records),'completed':terminal['completed_runs']}),flush=True)
        return 0 if terminal['status']=='PASS' else 3
    except Exception as exc:
        write_json(stage/'P02_FAILURE.json',{'status':'FAILED','error':repr(exc),'code_commit':args.code_freeze_commit,
                   'audits':audits,'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False})
        raise
