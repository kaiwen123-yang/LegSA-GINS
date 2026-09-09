"""Detached P04 phases; diagnosis never invokes a solver or evaluator."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
import re
from pathlib import Path
import shutil
import sys
import yaml
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from ..clean5_sequence.registry import load_registry
from ..clean5_sequence.generation_audit import selected_lock, open_records, audit_records
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..clean5_sequence.solver_runner import raw_checkpoint_worker, execution_state
from .runtime import resolve, write_json, run_order, run_ladder, verify_bundle, EXE_SHA


def args_for(argv):
    p=argparse.ArgumentParser()
    p.add_argument('--code-root',type=Path,required=True)
    p.add_argument('--code-freeze-commit',required=True)
    p.add_argument('--paths-config',type=Path,required=True)
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--phase',choices=['all','diagnosis','generalization'],default='all')
    p.add_argument('--_phase',choices=['checkpoint','providers','diagnosis'])
    p.add_argument('--dataset',choices=['BY2H','BY2O'])
    p.add_argument('--checkpoint',choices=['pre_run','post_run'])
    p.add_argument('--audit-dir',type=Path)
    return p.parse_args(argv)


def command_args(args, registry):
    return [sys.executable,'-B',str(registry.code_root/'scripts/paper_rebuild/clean5_run_parity_p04.py'),
        '--code-root',str(registry.code_root),'--code-freeze-commit',args.code_freeze_commit,
        '--paths-config',str(args.paths_config),'--executable',str(args.executable)]


def forbidden_diagnostic_executions(lines):
    """Inspect executed programs/entry scripts, not a binary passed as metadata."""
    forbidden=[]
    for line in lines:
        match=re.search(r'execve\("([^"\\]+)", \[(.*?)\]',line)
        if not match:continue
        program=Path(match[1]).name
        argv=re.findall(r'"([^"\\]*)"',match[2])
        entry=next((arg for arg in argv[1:] if not arg.startswith('-')), '') if program.startswith('python') else ''
        if program=='legsa_v23_port_core_demo' or 'evaluate_nav_trace_kfgins' in program or 'evaluate_nav_trace_kfgins' in Path(entry).name:
            forbidden.append(line)
    return forbidden


def traced_child(args,registry,stage,dataset,phase,checkpoint=None):
    auditdir=stage/dataset/'01_EXECUTION_AUDIT'/phase
    auditdir.mkdir(parents=True,exist_ok=False);log=auditdir/'OPENAT.strace'
    cmd=[shutil.which('strace') or 'strace','-f','-qq','-yy','-s','4096','-e','trace=openat','-o',str(log),
         *command_args(args,registry),'--_phase','checkpoint' if checkpoint else 'providers',
         '--dataset',dataset,'--audit-dir',str(auditdir)]
    if checkpoint:cmd+=['--checkpoint',checkpoint]
    result=run_process_group(cmd,cwd=registry.code_root,timeout_seconds=1800,
        timeout_message='P04 phase timeout; no retry',launch_failure_message='P04 phase launch failed')
    (auditdir/'stdout.log').write_text(result.stdout);(auditdir/'stderr.log').write_text(result.stderr)
    seq=registry.sequences[dataset]
    expected=({registry.raw_root/p for p in selected_lock(registry,seq)['rows']} if checkpoint else
              {seq.body_path,*[seq.fix_root/name for name in
               ('gnss1-status.csv','gnss2-status.csv','gnss1-raw.csv','gnss2-raw.csv')]})
    audit=audit_records(open_records(log,registry.code_root),registry.raw_root,expected,checkpoint_phase=bool(checkpoint))
    scope=write_scope_audit(audited_open_records(log,registry.code_root),raw_root=registry.raw_root,
        allowed_write_roots=[auditdir] if checkpoint else [auditdir,stage/dataset/'02_PARITY_PROVIDERS'],
        clean_root=registry.clean_root)
    audit.update(exit_code=result.returncode,write_scope=scope,command=cmd,strace_sha256=sha256_file(log),
        dataset_id=dataset,data_mode=seq.data_mode,synthetic_data_used=False,semisynthetic_data_used=False)
    audit['pass']=audit['pass'] and scope['pass'] and result.returncode==0
    write_json(auditdir/'PHASE_AUDIT.json',audit)
    if not audit['pass']:raise RuntimeError(dataset+' '+phase+' failed: '+result.stderr[-1800:])
    print('P04 '+dataset+' '+phase+': PASS',flush=True)
    return audit


def traced_diagnosis(args,registry,contract):
    root=resolve(contract['p04']['diagnosis_root'],registry)
    directory=root/'00_EXECUTION_AUDIT';directory.mkdir(parents=True,exist_ok=False)
    log=directory/'DIAGNOSIS_OPENAT.strace'
    cmd=[shutil.which('strace') or 'strace','-f','-qq','-yy','-s','4096','-e','trace=openat,execve',
         '-o',str(log),*command_args(args,registry),'--_phase','diagnosis','--audit-dir',str(directory)]
    result=run_process_group(cmd,cwd=registry.code_root,timeout_seconds=1800,
        timeout_message='Read-only diagnosis timeout; no retry',launch_failure_message='Diagnosis launch failed')
    (directory/'stdout.log').write_text(result.stdout);(directory/'stderr.log').write_text(result.stderr)
    records=audited_open_records(log,registry.code_root);seq=registry.sequences['BY2']
    allowed_raw={seq.body_path,seq.trace_path,seq.fix_root/'gnss1-raw.csv',seq.fix_root/'gnss1-status.csv'}
    raw=[r for r in records if registry.raw_root in Path(r['path']).parents]
    bad=[r for r in raw if Path(r['path']) not in allowed_raw or r['return_code']<0 or 'O_RDONLY' not in r['flags']]
    scope=write_scope_audit(records,raw_root=registry.raw_root,clean_root=registry.clean_root,allowed_write_roots=[root])
    forbidden_exec=forbidden_diagnostic_executions(log.read_text().splitlines())
    audit={'pass':result.returncode==0 and not bad and scope['pass'] and not forbidden_exec,
        'exit_code':result.returncode,'write_scope':scope,'unexpected_raw_opens':bad,
        'raw_opens':raw,'solver_invocations':0 if not forbidden_exec else 'UNAVAILABLE',
        'evaluator_invocations':0 if not forbidden_exec else 'UNAVAILABLE','forbidden_exec':forbidden_exec,
        'data_mode':'real_by2_offline_diagnosis','synthetic_data_used':False,'semisynthetic_data_used':False,
        'trace_role':'offline diagnosis only; no output feeds providers or solvers','strace_sha256':sha256_file(log)}
    write_json(directory/'DIAGNOSIS_EXECUTION_AUDIT.json',audit)
    if not audit['pass']:raise RuntimeError('P04 diagnosis failed: '+result.stderr[-1800:])
    print('P04 read-only diagnosis: PASS (zero solver/evaluator)',flush=True)
    return json.loads((directory/'DIAGNOSIS_RETURN.json').read_text()),audit


def validate_seal(stage,records):
    path=stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json';seal=json.loads(path.read_text())
    if seal['records']!=records:raise ValueError('P04 seal run identity differs')
    for rel,digest in seal['files_sha256'].items():
        p=Path(rel)
        if p.is_absolute() or '..' in p.parts or (stage/p).is_symlink() or sha256_file(stage/p)!=digest:
            raise ValueError('P04 sealed artifact changed: '+rel)
    return {'path':str(path),'sha256':sha256_file(path),'file_count':len(seal['files_sha256'])}


def main(argv=None):
    args=args_for(argv);os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['GIT_OPTIONAL_LOCKS']='0'
    registry=load_registry(args.code_root/'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',args.paths_config)
    registry=replace(registry,code_root=args.code_root.resolve())
    state=execution_state(registry.code_root,args.code_freeze_commit)
    if sha256_file(args.executable)!=EXE_SHA:raise ValueError('P04 executable identity mismatch')
    path=registry.code_root/'configs/paper_rebuild/clean5/CLEAN5_PARITY_P04_CONTRACT.yaml'
    contract=yaml.safe_load(path.read_text());spec=contract['p04'];run_order(contract)
    stage=resolve(spec['stage_root'],registry);diagnosis_root=resolve(spec['diagnosis_root'],registry)
    if args._phase=='checkpoint':
        raw_checkpoint_worker(registry,registry.sequences[args.dataset],args.checkpoint,args.audit_dir);return 0
    if args._phase=='providers':
        if spec.get('execution_ready') is not True or spec['sequences'][args.dataset].get('execution_ready') is not True:
            raise ValueError('P04 source execution gate is not ready')
        from .providers import generate_providers
        bundle=generate_providers(registry=registry,stage_root=stage,contract=contract,
                                  code_commit=args.code_freeze_commit,dataset=args.dataset)
        persisted=json.loads((stage/args.dataset/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json').read_text())
        if bundle!=persisted:raise ValueError('Provider bundle handoff mismatch')
        return 0
    if args._phase=='diagnosis':
        from .diagnosis import run_diagnosis
        result=run_diagnosis(registry=registry,contract=contract,output_root=diagnosis_root,code_commit=args.code_freeze_commit)
        write_json(args.audit_dir/'DIAGNOSIS_RETURN.json',result);return 0
    stage.mkdir(parents=True,exist_ok=True)
    if args.phase in ('all','generalization') and spec.get('execution_ready') is not True:
        raise ValueError('Preregistered P04 source gates/clarifications are not ready')
    start=stage/('P04_'+args.phase.upper()+'_STARTED.json')
    write_json(start,{'code_commit':args.code_freeze_commit,'code_state':state,'contract_sha256':sha256_file(path),
        'data_mode':'real_three_sequence_parity','synthetic_data_used':False,'semisynthetic_data_used':False,
        'run_order':run_order(contract),'phase':args.phase,'solver_limit':8,'evaluator_limit':18,'retry_count':0})
    audits={};records=[];bundles={};seals={};diagnosis=None
    try:
        if args.phase in ('all','diagnosis'):diagnosis,audits['diagnosis']=traced_diagnosis(args,registry,contract)
        if args.phase in ('all','generalization'):
            for dataset in ('BY2H','BY2O'):
                audits[dataset]={}
                for phase,checkpoint in [('pre_generation','pre_run'),('providers',None),('post_generation','post_run')]:
                    audits[dataset][phase]=traced_child(args,registry,stage,dataset,phase,checkpoint)
                bundles[dataset]=json.loads((stage/dataset/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json').read_text())
                verify_bundle(bundles[dataset])
            for dataset in ('BY2H','BY2O'):
                audits[dataset]['pre_solver']=traced_child(args,registry,stage,dataset,'pre_solver','pre_run')
                current=run_ladder(registry=registry,stage_root=stage/dataset,contract=contract,
                    provider_bundle=bundles[dataset],executable=args.executable,code_commit=args.code_freeze_commit,dataset=dataset)
                records.extend(current)
                audits[dataset]['post_solver']=traced_child(args,registry,stage,dataset,'post_solver','post_run')
                verify_bundle(bundles[dataset]);seals[dataset]=validate_seal(stage/dataset,current)
                if len(current)!=4 or any(r['terminal_status']!='COMPLETED' for r in current):
                    raise RuntimeError('P04 solver gate failed; remaining runs not executed')
            from .evaluation import evaluate_generalization
            evaluation=evaluate_generalization(registry=registry,contract=contract,stage_root=stage,
                records=records,code_commit=args.code_freeze_commit,bundles=bundles)
        else:evaluation={'status':'NOT_EXECUTED_DIAGNOSIS_ONLY'}
        if execution_state(registry.code_root,args.code_freeze_commit)!=state:raise RuntimeError('Snapshot changed')
        status=('COMPLETED' if args.phase=='diagnosis' or evaluation.get('status')=='COMPLETED' else 'PARTIAL')
        terminal={'status':status,'phase':args.phase,'code_commit':args.code_freeze_commit,'run_count':len(records),
            'runs':records,'seals':seals,'audits':audits,'diagnosis':diagnosis,'evaluation':evaluation,'retry_count':0,
            'data_mode':'real_three_sequence_parity','synthetic_data_used':False,'semisynthetic_data_used':False,
            'V2n_solver_invocations':0}
        write_json((diagnosis_root/'P04_DIAGNOSIS_TERMINAL.json') if args.phase=='diagnosis' else (stage/'P04_TERMINAL.json'),terminal)
        print(json.dumps({'status':status,'runs':len(records),'phase':args.phase}),flush=True)
        return 0 if status=='COMPLETED' else 3
    except Exception as exc:
        write_json(stage/'P04_FAILURE.json',{'status':'FAILED','error':str(exc),'runs':records,'audits':audits,
            'code_commit':args.code_freeze_commit,'retry_count':0,'data_mode':'real_three_sequence_parity',
            'synthetic_data_used':False,'semisynthetic_data_used':False})
        raise
