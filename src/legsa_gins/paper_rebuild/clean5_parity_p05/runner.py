"""Frozen detached nine-run sensitivity attempt. No provider generation or retries."""
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
from ..clean5_sequence.solver_runner import execution_state,raw_checkpoint_worker
from ..clean5_parity_p04.runner import validate_seal
from .runtime import resolve,write_json,EXE_SHA,run_ladder,verify_bundle,grid_cells
from .evaluation import pinned,evaluate_grid


def checkpoint(args,registry,stage,name,phase):
    root=stage/'01_EXECUTION_AUDIT'/name;root.mkdir(parents=True,exist_ok=False);log=root/'OPENAT.strace'
    command=[shutil.which('strace') or 'strace','-f','-qq','-yy','-s','4096','-e','trace=openat','-o',str(log),sys.executable,'-B',str(registry.code_root/'scripts/paper_rebuild/clean5_run_parity_p05.py'),'--code-root',str(registry.code_root),'--code-freeze-commit',args.code_freeze_commit,'--paths-config',str(args.paths_config),'--executable',str(args.executable),'--_checkpoint',phase,'--audit-dir',str(root)]
    result=run_process_group(command,cwd=registry.code_root,timeout_seconds=1800,timeout_message='P05 checkpoint timeout',launch_failure_message='P05 checkpoint launch failure')
    (root/'stdout.log').write_text(result.stdout);(root/'stderr.log').write_text(result.stderr)
    audit=audit_records(open_records(log,registry.code_root),registry.raw_root,{registry.raw_root/p for p in selected_lock(registry,registry.sequences['BY2'])['rows']},checkpoint_phase=True)
    scope=write_scope_audit(audited_open_records(log,registry.code_root),raw_root=registry.raw_root,clean_root=registry.clean_root,allowed_write_roots=[root])
    audit.update(write_scope=scope,exit_code=result.returncode,strace_sha256=sha256_file(log));audit['pass']=audit['pass'] and scope['pass'] and result.returncode==0
    write_json(root/'PHASE_AUDIT.json',audit)
    if not audit['pass']:raise RuntimeError('P05 checkpoint failed '+result.stderr[-1000:])
    return audit


def failure_grid(*,stage,contract,records,code_commit,reason):
    """Report every registered cell on failure, without replacing existing evidence."""
    from ..clean5_parity.evaluation import _csv
    stage=Path(stage);seal_path=stage/'04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json'
    record_source='in_memory_records'
    if seal_path.exists():
        records=json.loads(seal_path.read_text())['records'];record_source=str(seal_path)
    lookup={r['variant_id']:r for r in records};written=[];preserved=[]
    metrics=['horizontal_rmse_m','position_3d_rmse_m','up_rmse_m','yaw_rmse_deg','yaw_p95_deg',
             'height_abs_error_over_std_median','north_abs_error_over_std_median','east_abs_error_over_std_median','yaw_abs_error_over_std_median']
    invocations=0
    for version in ['v2','v3']:
        target=stage/'08_AGGREGATE' if version=='v2' else stage/'08_AGGREGATE/v3'
        target.mkdir(parents=True,exist_ok=True);rows=[]
        for cell in grid_cells(contract):
            cid=cell['cell_id'];record=lookup.get(cid);run_id='CLEAN5_PARITY_P05_'+cid+'_A04'
            row={**cell,'variant_id':cid,'run_id':run_id,'method_id':'A04','dataset_id':'BY2','case_id':'C00_clean_normal',
                 'evaluator_contract':'evaluator_contract_'+version,'classification':'SENSITIVITY_NOT_FROZEN',
                 'solver_terminal_status':record['terminal_status'] if record else 'NOT_EXECUTED',
                 'evaluation_status':'UNAVAILABLE','evaluation_invoked':False,'unavailable_reason':reason,
                 'code_commit':code_commit,'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False,
                 'no_best_selection':True,'no_feedback':True,'no_adoption':True,**{k:'UNAVAILABLE' for k in metrics}}
            receipt=stage/'07_OFFLINE_EVALUATION'/version/'RECEIPTS'/run_id/'EVAL_TERMINAL.json'
            if receipt.exists():
                prior=json.loads(receipt.read_text());row.update(prior['row']);row['evaluation_invoked']=prior['evaluator_invoked']
                row['source_evaluation_receipt']=str(receipt);invocations+=int(prior['evaluator_invoked'])
            rows.append(row)
        for name in ['SENSITIVITY_GRID.csv','UNIQUE_EVALUATION_RESULTS.csv']:
            path=target/name
            if path.exists():preserved.append(str(path))
            else:_csv(path,rows);written.append(str(path))
    return {'status':'FAILURE_GRID_RECORDED','cell_count_per_version':9,'record_source':record_source,
            'written_tables':written,'preserved_tables':preserved,'evaluator_invocation_count_from_receipts':invocations}


def main(argv=None):
    p=argparse.ArgumentParser()
    for name in ['code-root','paths-config','executable']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--code-freeze-commit',required=True);p.add_argument('--_checkpoint',choices=['pre_run','post_run']);p.add_argument('--audit-dir',type=Path)
    args=p.parse_args(argv);os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['GIT_OPTIONAL_LOCKS']='0'
    registry=load_registry(args.code_root/'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',args.paths_config);registry=replace(registry,code_root=args.code_root.resolve())
    state=execution_state(registry.code_root,args.code_freeze_commit)
    if sha256_file(args.executable)!=EXE_SHA:raise ValueError('Binary mismatch')
    contract_path=registry.code_root/'configs/paper_rebuild/clean5/CLEAN5_PARITY_P05_CONTRACT.yaml';contract=yaml.safe_load(contract_path.read_text());spec=contract['p05'];grid_cells(contract)
    if spec['executable_sha256']!=EXE_SHA:raise ValueError('Contract binary identity mismatch')
    if args._checkpoint:raw_checkpoint_worker(registry,registry.sequences['BY2'],args._checkpoint,args.audit_dir);return 0
    stage=resolve(spec['stage_root'],registry)
    expected=registry.clean_root/'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/13_NOISE_MODEL_SENSITIVITY'
    if stage!=expected or stage.is_symlink():raise ValueError('Unauthorized P05 stage path')
    stage.mkdir(parents=True,exist_ok=False)
    write_json(stage/'P05_STARTED.json',{'code_commit':args.code_freeze_commit,'code_state':state,'contract_sha256':sha256_file(contract_path),'classification':'SENSITIVITY_NOT_FROZEN','planned_runs':9,'planned_evaluations':18,'retry_count':0})
    records=[];audits={}
    try:
        bundle=json.loads(pinned(spec['provider_bundle'],registry).read_text());verify_bundle(bundle)
        for pin in spec['source_pins']+[spec['evaluator'],spec['trace'],spec['provider_bundle']]:pinned(pin,registry)
        if bundle['baseline_median_m']!=spec['baseline_median_m']:raise ValueError('Baseline changed')
        audits['pre_solver']=checkpoint(args,registry,stage,'pre_solver','pre_run')
        records=run_ladder(registry=registry,stage_root=stage,contract=contract,provider_bundle=bundle,executable=args.executable,code_commit=args.code_freeze_commit)
        audits['post_solver']=checkpoint(args,registry,stage,'post_solver','post_run');verify_bundle(bundle);seal=validate_seal(stage,records)
        if len(records)!=9 or any(r['terminal_status']!='COMPLETED' for r in records):raise RuntimeError('Sensitivity solve gate failed; no retry')
        if len({r['non_grid_parameter_hash'] for r in records})!=1:raise ValueError('Non-grid hash changed')
        parity=records[0]['origin_identity_gate']
        write_json(stage/'04_PARITY_SEAL/ORIGIN_IDENTITY_GATE.json',parity)
        evaluation=evaluate_grid(registry=registry,contract=contract,stage_root=stage,records=records,code_commit=args.code_freeze_commit)
        if evaluation['status']!='COMPLETED':raise RuntimeError('P05 evaluation incomplete; all cells recorded')
        for pin in spec['source_pins']+[spec['evaluator'],spec['trace'],spec['provider_bundle']]:pinned(pin,registry)
        if execution_state(registry.code_root,args.code_freeze_commit)!=state:raise ValueError('Snapshot changed')
        terminal={'status':'COMPLETED','classification':'SENSITIVITY_NOT_FROZEN','code_commit':args.code_freeze_commit,'run_count':len(records),'runs':records,'audits':audits,'seal':seal,'origin_identity_gate':parity,'evaluation':evaluation,'retry_count':0,'no_best_selection':True,'no_feedback':True,'no_adoption':True,'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False}
        write_json(stage/'P05_TERMINAL.json',terminal);print('P05 COMPLETED 9/9 runs, 18/18 evaluations',flush=True);return 0
    except Exception as exc:
        try:failure_report=failure_grid(stage=stage,contract=contract,records=records,code_commit=args.code_freeze_commit,reason=str(exc))
        except Exception as reporting_exc:failure_report={'status':'FAILURE_GRID_WRITE_FAILED','error':str(reporting_exc)}
        write_json(stage/'P05_FAILURE.json',{'status':'FAILED','error':str(exc),'runs':records,'audits':audits,'failure_grid':failure_report,'retry_count':0,'code_commit':args.code_freeze_commit});raise
