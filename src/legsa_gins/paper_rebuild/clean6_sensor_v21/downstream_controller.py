"""P13 separately frozen downstream execution and exact archival adapter."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from .controller import context,effective_contract,persist,note,dump_status,archive_records
from .downstream import build_jobs,grid_origin_gate
from .runtime import run_one
from .evaluation import evaluate_batch
from .diagnostics import write_run_sidecars
from ..clean6_canonical_v2.storage import ResourceMonitor
from ..clean6_canonical_v2.resources import solver_workers
from ..clean6_canonical_v2.io_recovery import ScientificStop
from ..clean5_sequence.io_audit import audited_open_records,write_scope_audit
from ..clean5_degradation.common import write_json
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group


def freeze_downstream(ctx):
    path=ctx.stage/'DOWNSTREAM/CODE_FREEZE.json'
    if path.exists():
        saved=json.loads(path.read_text())
        for name,digest in saved['source_hashes'].items():
            if sha256_file(ctx.reg.code_root/name)!=digest:raise ValueError('Frozen downstream code changed '+name)
        ctx.code_commit=saved['code_commit']
        return saved
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/stage/clean3-math-repair'],cwd=ctx.reg.code_root,text=True).split()[0]
    if remote!=ctx.code_commit:raise ValueError('Downstream code must be pushed before launch')
    names=['downstream_controller.py','downstream.py','runtime.py','evaluation.py','diagnostics.py','controller.py']
    paths=['src/legsa_gins/paper_rebuild/clean6_sensor_v21/'+name for name in names]
    paths+=['scripts/paper_rebuild/clean6_run_sensor_v21_downstream.py']
    for name in paths:
        if subprocess.check_output(['git','show',ctx.code_commit+':'+name],cwd=ctx.reg.code_root)!=(ctx.reg.code_root/name).read_bytes():
            raise ValueError('Uncommitted downstream source '+name)
    result={'status':'COMMITTED_PUSHED','code_commit':ctx.code_commit,'source_hashes':{name:sha256_file(ctx.reg.code_root/name) for name in paths},
        'data_mode':'execution_metadata_only','synthetic_data_used':False,'semisynthetic_data_used':False}
    persist(path,result)
    return result


def prepare(ctx):
    bases={d:json.loads((ctx.stage/'02_BASE_PROVIDERS'/d/'PROVIDER_BUNDLE.json').read_text()) for d in ('BY2','BY2H','BY2O')}
    return build_jobs(ctx.v21,ctx.v2,ctx.reg,bases,ctx.stage/'DOWNSTREAM',ctx.code_commit)


def run(ctx):
    if json.loads((ctx.stage/'MAIN_ARCHIVE_CLOSURE.json').read_text())['status']!='PASS':raise ValueError('Main chain closure required')
    stage=ctx.stage/'DOWNSTREAM'; stage.mkdir(exist_ok=True)
    freeze_downstream(ctx)
    completed=stage/'NATIVE_DIAGNOSTICS_CLOSURE.json'
    if completed.exists():
        result=json.loads(completed.read_text())
        if result['status']!='PASS':raise ValueError('Existing downstream closure is not successful')
        for name,pin in result['final_index_pins'].items():
            if sha256_file(stage/name)!=pin:raise ValueError('Downstream final index changed')
        return result
    prepared=stage/'DOWNSTREAM_JOB_REGISTRY.json'
    if not prepared.exists():
        audit=stage/'01_PROVIDER_AUDIT';audit.mkdir(exist_ok=True)
        log=audit/'OPENAT.strace'
        command=['env','PYTHONDONTWRITEBYTECODE=1','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1',
            'strace','-f','-qq','-yy','-s','4096','-e','trace=openat','-o',str(log),sys.executable,
            str(ctx.reg.code_root/'scripts/paper_rebuild/clean6_run_sensor_v21_downstream.py'),
            '--local-config',str(ctx.local),'--operation','providers']
        result=run_process_group(command,cwd=ctx.reg.code_root,timeout_seconds=3600,timeout_message='Downstream providers timeout',launch_failure_message='Downstream provider launch failure')
        (audit/'stdout.log').write_text(result.stdout);(audit/'stderr.log').write_text(result.stderr)
        opened=audited_open_records(log,ctx.reg.code_root)
        forbidden=[r for r in opened if Path(r['path']).suffix.lower() in ('.bag','.fpl') or Path(r['path']).name.startswith('trace_')]
        scope=write_scope_audit(opened,raw_root=ctx.reg.raw_root,clean_root=ctx.reg.clean_root,allowed_write_roots=[stage])
        persist(audit/'AUDIT.json',{'exit_code':result.returncode,'forbidden_opens':forbidden,'scope':scope,'strace_sha256':sha256_file(log)})
        if result.returncode or forbidden or not scope['pass']:raise ValueError('Downstream input audit requires bookkeeping repair '+result.stderr[-2000:])
    jobs=json.loads(prepared.read_text())['native_jobs']
    if len(jobs)!=21:raise ValueError('Downstream job count mismatch')
    scratch=ctx.scratch/'DOWNSTREAM/BATCH_001';scratch.mkdir(parents=True,exist_ok=True)
    output=stage/'BATCHES/BATCH_001';output.mkdir(parents=True,exist_ok=True)
    contract=effective_contract(ctx)
    context_io={'stage':stage,'root':stage/'CONTROLLER','scratch':ctx.scratch/'DOWNSTREAM','io_fix_id':'P13',
        'freeze':{'io_fix_code_commit':ctx.code_commit},'write_workers':6,'current_batch_run_count':21}
    context_io['root'].mkdir(exist_ok=True)
    records=[]
    with ResourceMonitor(ctx.scratch,ctx.reg.clean_root,output/'RESOURCE_SAMPLES.jsonl') as monitor:
        monitor.begin_phase('downstream_solver')
        def one(job):
            rid=job['source']['run_id']; cached=output/'NATIVE_TERMINALS'/(rid+'.json')
            if cached.exists():return json.loads(cached.read_text())
            root=scratch/'03_RUNS'/rid
            terminal=root/'P13_RUN_TERMINAL.json'
            if terminal.exists():
                rec=json.loads(terminal.read_text());rec['output_seal']=json.loads((root/'OUTPUT_SEAL.json').read_text())['files']
            else:
                rec=run_one(job['source'],job['bundle'],contract,ctx.reg,root,ctx.code_commit,
                    case_meta=ctx.v2['sequences']['BY2'].get('case_meta') or {},**job['run_kwargs'])
            rec.update(domain='DOWNSTREAM',diagnostic_family=job['diagnostic_family'],variant_id=job['variant_id'],
                input_variant=job['input_variant'],grid_cell=job['grid_cell'])
            if rec['terminal_status'] not in ('COMPLETED','ALGORITHM_FAILURE_ALL_YAW_REJECTED'):
                if rec.get('exit_code') not in (None,0):raise ScientificStop('NATIVE_UNREGISTERED_FAILURE',str(rec))
                if 'non-finite' in rec.get('failure','').lower() or 'nonfinite' in rec.get('failure','').lower():
                    raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE',str(rec))
                raise ValueError('Preserve downstream native scene for validation-only repair '+str(rec))
            persist(cached,rec)
            return rec
        errors=[]
        with ThreadPoolExecutor(max_workers=solver_workers()) as pool:
            for future in as_completed([pool.submit(one,j) for j in jobs]):
                try:records.append(future.result())
                except Exception as error:errors.append(error)
        if errors:raise next((e for e in errors if isinstance(e,ScientificStop)),errors[0])
        records.sort(key=lambda r:r['run_id']);persist(output/'NATIVE_RECORDS.json',records)
        resource=monitor.end_phase()
        gatepath=stage/'GRID_ORIGIN_GATE.json'
        if not gatepath.exists():
            control=next(r for r in records if r['diagnostic_family']=='LADDER' and r['variant_id']=='V2is' and r['method_id']=='A04')
            origin=next(r for r in records if r['diagnostic_family']=='NOISE_GRID' and r['variant_id']=='N00')
            gate=grid_origin_gate(control['output_root'],origin['output_root']);persist(gatepath,gate)
        gate=json.loads(gatepath.read_text())
        if gate['status']!='PASS':
            note(ctx,'DOWNSTREAM_GRID_ORIGIN_NOT_EQUAL',gate=gate,
                disposition='REPORT_ALL_FROZEN_VARIANT_RESULTS_AND_FAILED_NUMERICAL_CHECK_WITHOUT_REDECISION',
                additional_stop_class_created=False)
        monitor.begin_phase('downstream_evaluators')
        pre=output/'EVALUATION_PREARCHIVE.json'
        if pre.exists():rows=json.loads(pre.read_text())
        else:
            rows,stats=evaluate_batch(records,contract,ctx.reg,scratch,ctx.code_commit,output,resource['owned_rss_peak_bytes'],io_context=context_io)
            if not (output/'EVALUATOR_RESOURCES.json').exists():persist(output/'EVALUATOR_RESOURCES.json',stats)
            expanded=[]
            for record in records:
                own=[r for r in rows if r['run_id']==record['run_id']]
                diag=write_run_sidecars(record,own) if record['terminal_status']=='COMPLETED' else {'evaluations':own}
                persist(stage/'DIAGNOSTICS'/(record['run_id']+'.json'),diag)
                for row in diag['evaluations']:
                    row.update(chain='V21',domain='DOWNSTREAM',diagnostic_family=record['diagnostic_family'],variant_id=record['variant_id'],
                        input_variant=record['input_variant'],grid_cell=record['grid_cell'],sensor_model_group_hash=ctx.v21['sensor_model_group_hash'])
                    row['frozen_adapter_source_row']=row['source_row'];row['source_row']=str(Path(row['evaluation_output_root'])/'P13_EVALUATION_RESULT.json')
                    persist(row['source_row'],row);expanded.append(row)
            rows=sorted(expanded,key=lambda r:(r['run_id'],r['evaluator_version']));persist(pre,rows)
        monitor.end_phase()
    # Preserve the main context; archival helper receives the downstream roots.
    from types import SimpleNamespace
    dsctx=SimpleNamespace(**vars(ctx));dsctx.stage=stage;dsctx.scratch=ctx.scratch/'DOWNSTREAM'
    final,rows,archive=archive_records(dsctx,context_io,records,rows,1)
    archive.update(unique_denominator=21,formal_main_unique_denominator=5880)
    if archive['pending_run_ids']:raise ValueError('Downstream archive pending requires continuation')
    persist(stage/'FINAL_RUN_RECORDS.json',final);persist(stage/'FINAL_EVALUATION_RECORDS.json',rows)
    if len(final)!=21 or len({r['run_id'] for r in final})!=21 or len(rows)!=42 or len({(r['run_id'],r['evaluator_version']) for r in rows})!=42:
        raise ValueError('Downstream final identity count mismatch')
    by_run={r['run_id']:r for r in final}
    for row in rows:
        rec=by_run[row['run_id']]
        expected='COMPLETED' if rec['terminal_status']=='COMPLETED' else 'NOT_RUN_ALGORITHM_FAILURE'
        if row['evaluation_status']!=expected or row['evaluator_version'] not in ('v3','v2'):
            raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE','Downstream terminal mismatch')
        if rec.get('archive_status')!='ARCHIVE_VERIFIED' or row['archive_receipt']!=rec['archive_receipt']:
            raise ValueError('Downstream receipt identity mismatch')
    result={'status':'PASS','native_calls':len(final),'evaluator_terminals':len(rows),'verified_archives':len(final),
        'archive':archive,'grid_origin_gate_status':gate['status'],'code_commit':ctx.code_commit,'new_outcome_created':False,
        'final_index_pins':{name:sha256_file(stage/name) for name in ('FINAL_RUN_RECORDS.json','FINAL_EVALUATION_RECORDS.json')}}
    persist(stage/'NATIVE_DIAGNOSTICS_CLOSURE.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config',required=True);parser.add_argument('--operation',choices=('providers','run'),required=True)
    args=parser.parse_args(argv);ctx=context(args.local_config)
    try:
        if args.operation=='providers':freeze_downstream(ctx);result=prepare(ctx)
        else:result=run(ctx)
        print(json.dumps({'status':'RETURNED','operation':args.operation,'code_commit':ctx.code_commit}),flush=True)
    except ScientificStop as error:
        dump_status(ctx,status='SCIENTIFIC_STOP',kind=error.kind,reason=str(error))
        persist(ctx.stage/'STOPPED.json',{'kind':error.kind,'reason':str(error),'code_commit':ctx.code_commit})
        raise
    except Exception as error:
        note(ctx,'DOWNSTREAM_BOOKKEEPING_REPAIR_REQUIRED',error_type=type(error).__name__,reason=str(error));raise

if __name__=='__main__':main()
