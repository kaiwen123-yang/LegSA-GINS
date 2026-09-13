"""P-13 bounded phase controller; frozen native/evaluation math stays separate."""
from __future__ import annotations
import argparse
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace
import yaml
from ..clean5_degradation.common import registry, resolve, pinned, read_csv, write_json
from ..clean5_degradation.runtime import checkpoint
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..clean6_canonical_v2.contract import selection
from ..clean6_canonical_v2.resources import solver_workers
from ..clean6_canonical_v2.storage import inventory, cleanup_exact, ResourceMonitor, append_json
from ..clean6_canonical_v2.io_recovery import archive_batch, ScientificStop
from ..clean6_canonical_v2.runner import profile_template
from ..clean6_addendum.runner import make_runs
from ..clean6_addendum.runtime import native_template, finish_evaluation
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .runtime import run_one

CONTRACT = 'configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml'
STAGE = 'CLEAN6_SENSOR_MODEL_V21'


def dump_status(ctx, **updates):
    path = ctx.stage/'STATUS.json'
    prior = json.loads(path.read_text()) if path.exists() else {}
    prior.update(updates, updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(prior, ensure_ascii=False, allow_nan=False, indent=2)+'\n')
    os.replace(temporary, path)


def note(ctx, kind, **details):
    append_json(ctx.stage/'P13_APPENDIX_LEDGER.jsonl', {'kind':kind, **details})


def persist(path, value):
    """Only exact-identical checkpoint reuse is allowed."""
    path=Path(path)
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError('Existing checkpoint differs: '+str(path))
        return
    write_json(path,value)


def context(local_config):
    local = Path(local_config).resolve()
    reg = registry(local)
    path = reg.code_root/CONTRACT
    v21 = yaml.safe_load(path.read_text())
    v2 = yaml.safe_load((reg.code_root/v21['frozen_identities']['core_contract']['path']).read_text())
    addendum = yaml.safe_load((reg.code_root/v21['frozen_identities']['addendum_contract']['path']).read_text())
    paths = yaml.safe_load(local.read_text())['paths']
    stage = reg.clean_root/'stages'/STAGE
    scratch = Path(paths['sensor_model_v21_scratch'])
    if (scratch.is_symlink() or not scratch.is_absolute() or str(scratch).startswith('/mnt/')
            or scratch == reg.code_root or scratch == reg.clean_root):
        raise ValueError('P13 requires its own ext4 scratch alias')
    stage.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    ctx = SimpleNamespace(reg=reg, local=local, paths=paths, contract_path=path, v21=v21,
                          v2=v2, addendum=addendum, stage=stage, scratch=scratch)
    ctx.code_commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=reg.code_root,text=True).strip()
    return ctx


def binary_gate(ctx):
    root = ctx.stage/'01_BINARY_BRIDGE'
    gate = json.loads((root/'BINARY_BRIDGE_RESULT.json').read_text())
    if gate['status'] != 'PASS' or gate['passed_comparisons'] != 44:
        raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE','P13 binary bridge did not pass')
    freeze = json.loads((root/'BINARY_FREEZE.json').read_text())
    for key in ('old_executable','new_executable'):
        if sha256_file(Path(freeze[key]['path'])) != freeze[key]['sha256']:
            raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE','P13 executable identity changed')
    return freeze


def effective_contract(ctx):
    contract = copy.deepcopy(ctx.v2)
    binary = binary_gate(ctx)
    contract.update(protocol_id='SENSOR_MODEL_V2_1', stage_root='<CLEAN_ROOT>/stages/'+STAGE,
                    sensor_model_hash=ctx.v21['sensor_model_group_hash'])
    contract['runtime']['executable'] = binary['new_executable']
    contract['runtime']['binary_guard_code_commit'] = binary['code_commit']
    return contract


def phase_freeze(ctx, phase):
    """Freeze a bounded gate independently of later main-controller work."""
    folder=ctx.stage/'00_PREREGISTRATION'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(phase+'_CODE_FREEZE.json')
    names=['runtime.py','f01_audit.py','binary_bridge.py','controller.py']
    relatives=['src/legsa_gins/paper_rebuild/clean6_sensor_v21/'+n for n in names]
    relatives+=['scripts/paper_rebuild/clean6_run_sensor_v21.py',CONTRACT]
    if path.exists():
        result=json.loads(path.read_text())
        ctx.code_commit=result['code_commit']
        return result
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/stage/clean3-math-repair'],cwd=ctx.reg.code_root,text=True).split()[0]
    if remote!=ctx.code_commit:raise ValueError('Phase implementation is not pushed')
    for relative in relatives:
        blob=subprocess.check_output(['git','show',ctx.code_commit+':'+relative],cwd=ctx.reg.code_root)
        if blob!=(ctx.reg.code_root/relative).read_bytes():raise ValueError('Uncommitted gate source '+relative)
    result={'status':'COMMITTED_PUSHED','phase':phase,'code_commit':ctx.code_commit,
            'source_hashes':{p:sha256_file(ctx.reg.code_root/p) for p in relatives},
            'data_mode':'execution_metadata_only','synthetic_data_used':False,'semisynthetic_data_used':False}
    write_json(path,result)
    return result


def freeze(ctx):
    root = ctx.stage/'00_PREREGISTRATION'
    root.mkdir(parents=True,exist_ok=True)
    path = root/'EXECUTION_FREEZE.json'
    if path.exists():
        result = json.loads(path.read_text())
        if result['contract_hash'] != sha256_file(ctx.contract_path):
            raise ValueError('Execution contract changed')
        for relative,digest in result['source_hashes'].items():
            if sha256_file(ctx.reg.code_root/relative) != digest:
                raise ValueError('Frozen execution source changed '+relative)
        ctx.code_commit = result['code_commit']
        return result
    remote = subprocess.check_output(['git','ls-remote','origin','refs/heads/stage/clean3-math-repair'],cwd=ctx.reg.code_root,text=True).split()[0]
    if remote != ctx.code_commit:
        raise ValueError('Implementation must be pushed before provider/runtime freeze')
    files = subprocess.check_output(['git','ls-files','-z','src/legsa_gins/paper_rebuild',
        'scripts/paper_rebuild','src/legsa_gins/input_generation','src/legsa_gins/go2_prior','src/legsa_gins/datasets/by2'],cwd=ctx.reg.code_root,text=True).split('\0')
    sources = {p:sha256_file(ctx.reg.code_root/p) for p in files if p.endswith('.py')
               and '/publication/' not in p and '/horizontal_literature/' not in p}
    for relative in sources:
        blob=subprocess.check_output(['git','show',ctx.code_commit+':'+relative],cwd=ctx.reg.code_root)
        import hashlib
        if hashlib.sha256(blob).hexdigest()!=sources[relative]:
            raise ValueError('Uncommitted execution source '+relative)
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','src/legsa_gins/paper_rebuild/clean6_sensor_v21'],cwd=ctx.reg.code_root,text=True).strip()
    if untracked:raise ValueError('Untracked execution modules must be committed before freeze: '+untracked)
    result = {'status':'COMMITTED_PUSHED_EXECUTION_FREEZE','code_commit':ctx.code_commit,
              'remote_commit':remote,'contract_hash':sha256_file(ctx.contract_path),
              'sensor_model_group_hash':ctx.v21['sensor_model_group_hash'],'source_hashes':sources,
              'binary_gate':binary_gate(ctx),'data_mode':'execution_metadata_only',
              'synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False}
    write_json(path,result)
    return result


def raw_checkpoint(ctx,name):
    path = ctx.stage/'01_CHECKPOINTS'/name/'CHECKPOINT_RESULT.json'
    if path.exists():
        result=json.loads(path.read_text())
        if result.get('passed_count')==22:return result
    return checkpoint(ctx.v2,ctx.reg,ctx.stage,name,{'mode':'independent_hash_all',
        'human_instruction':'P13 execution uses the same P09c separately traced pre/post raw hash checkpoints.'})


def provider_task(ctx, output, *, case=None, base_bundle=None):
    key = case['case_id'] if case else 'THREE_BASE_SEQUENCES'
    audit = ctx.stage/'01_PROVIDER_AUDIT'/key
    if case and (output/key/'PROVIDER_BUNDLE.json').exists():
        bundle=json.loads((output/key/'PROVIDER_BUNDLE.json').read_text())
        for entry in bundle['providers'].values():
            if sha256_file(Path(entry['path'])) != entry['sha256']:
                raise ValueError('Existing provider seal differs: '+key)
        return bundle
    audit.mkdir(parents=True,exist_ok=True)
    log = audit/'PROVIDER_OPENAT.strace'
    command = ['env','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',
        'MKL_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1','strace','-f','-qq','-yy','-s','4096',
        '-e','trace=openat','-o',str(log),sys.executable,
        str(ctx.reg.code_root/'scripts/paper_rebuild/clean6_v21_providers.py'),
        '--contract',str(ctx.contract_path),'--v2-contract',str(ctx.reg.code_root/ctx.v21['frozen_identities']['core_contract']['path']),
        '--local-config',str(ctx.local),'--output',str(output),'--code-commit',ctx.code_commit]
    if case:
        command += ['--case-id',key,'--base-bundle',str(base_bundle),
                    '--addendum-contract',str(ctx.reg.code_root/ctx.v21['frozen_identities']['addendum_contract']['path'])]
    start=time.monotonic()
    completed=run_process_group(command,cwd=ctx.reg.code_root,timeout_seconds=7200,
        timeout_message='P13 provider computation timeout',launch_failure_message='P13 provider launch error')
    (audit/'stdout.log').write_text(completed.stdout)
    (audit/'stderr.log').write_text(completed.stderr)
    opened=audited_open_records(log,ctx.reg.code_root)
    forbidden=[r for r in opened if Path(r['path']).name.lower().startswith('trace_') or Path(r['path']).suffix.lower() in ('.bag','.fpl')]
    scope=write_scope_audit(opened,raw_root=ctx.reg.raw_root,clean_root=ctx.reg.clean_root,allowed_write_roots=[audit,output])
    result={'exit_code':completed.returncode,'seconds':time.monotonic()-start,'command':command,
            'forbidden_opens':forbidden,'scope':scope,'strace_sha256':sha256_file(log)}
    write_json(audit/'PROVIDER_ACCESS_AUDIT.json',result)
    if completed.returncode:
        if 'ReproductionGateFailure' in completed.stderr:
            raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE',completed.stderr[-3000:])
        raise ValueError('Provider validation mechanism needs adaptation: '+completed.stderr[-3000:])
    if forbidden or not scope['pass']:
        raise ValueError('Provider access scope requires correction; preserve all evidence')
    if case:
        return json.loads((output/key/'PROVIDER_BUNDLE.json').read_text())
    return {d:json.loads((output/d/'PROVIDER_BUNDLE.json').read_text()) for d in ('BY2','BY2H','BY2O')}


def bases(ctx):
    freeze(ctx)
    raw_checkpoint(ctx,'PRE')
    output=ctx.stage/'02_BASE_PROVIDERS'
    if (output/'BASE_PROVIDER_GATES.json').exists():
        gate=json.loads((output/'BASE_PROVIDER_GATES.json').read_text())
        if gate['status']!='PASS_THREE_SEQUENCE_PROVIDER_GATES':
            raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE','Base reproduction gate did not pass')
        return {d:json.loads((output/d/'PROVIDER_BUNDLE.json').read_text()) for d in ('BY2','BY2H','BY2O')}
    dump_status(ctx,phase='BASE_PROVIDER_REPRODUCTION',status='RUNNING')
    result=provider_task(ctx,output)
    dump_status(ctx,phase='BASE_PROVIDER_REPRODUCTION',status='PASS',datasets=3)
    return result


def build_jobs(ctx):
    cases,runs=selection(ctx.v2,ctx.reg)
    c00={r['method_id']:r for r in runs if r['case_id']=='C00_clean_normal'}
    allowed=set(ctx.v21['scope_and_accounting']['profiles'])
    case_by={r['case_id']:r for r in cases}
    jobs=[{'source':r,'dataset':'BY2','case_meta':case_by[r['case_id']],'domain':'CORE'}
          for r in runs if r['method_id'] in allowed and r['case_id']=='C00_clean_normal']
    for dataset in ('BY2H','BY2O'):
        spec=ctx.v2['sequences'][dataset]
        for method in ctx.v21['scope_and_accounting']['profiles']:
            source={**c00[method],'run_id':f'SEQUENCE_{dataset}_{method}','case_id':spec['case_id'],
                    'case_family':'natural_sequence','degradation_type_id':'CLEAN','seed_index':''}
            jobs.append({'source':source,'dataset':dataset,'case_meta':spec['case_meta'],'domain':'SEQUENCE'})
    jobs += [{'source':r,'dataset':'BY2','case_meta':case_by[r['case_id']],'domain':'CORE'}
             for r in runs if r['method_id'] in allowed and r['case_id']!='C00_clean_normal']
    additions=make_runs(ctx.addendum,runs)
    add_cases={r['case_id']:r for r in ctx.addendum['case_rows']}
    jobs += [{'source':r,'dataset':'BY2','case_meta':add_cases[r['case_id']],'domain':'ADDENDUM'}
             for r in additions if r['method_id'] in allowed]
    if len(jobs)!=5880 or len({j['source']['run_id'] for j in jobs})!=5880:
        raise ValueError('P13 unique run registry mismatch')
    return jobs,c00


def template_for(ctx,job,c00):
    source,dataset=job['source'],job['dataset']
    if job['domain']=='ADDENDUM':
        text,transport=native_template(source)
        return text,transport
    if dataset=='BY2':return None,None
    originals=ctx.v2['sequences'][dataset]['original_configs']
    method=source['method_id']
    pin=originals.get(method,originals['F04'])
    text=pinned({'path':pin['runtime_config'],'sha256':pin['runtime_config_sha256']},ctx.reg).read_text()
    if method not in originals:
        text,_=profile_template(text,Path(c00['F04']['runtime_config_path']).read_text(),Path(c00[method]['runtime_config_path']).read_text())
    return text,None


def execute(ctx,job,bundle,contract,scratch_batch,c00):
    source,dataset=job['source'],job['dataset']
    text,transport=template_for(ctx,job,c00)
    meta=dict(job['case_meta'])
    if job['domain']=='ADDENDUM':
        meta['degradation_parameters_json']=json.dumps({'start_s':meta['outage_start_s'],'end_s':meta['outage_end_s'],'duration_s':meta['duration_s']})
    root=scratch_batch/'03_RUNS'/source['run_id']
    if (root/'P13_RUN_TERMINAL.json').exists():
        record=json.loads((root/'P13_RUN_TERMINAL.json').read_text())
        seal=json.loads((root/'OUTPUT_SEAL.json').read_text())['files']
        for name,pin in seal.items():
            if sha256_file(root/name)!=pin['sha256']:
                raise ValueError('Native checkpoint bytes changed: '+source['run_id']+'/'+name)
        record.update(output_seal=seal,solver_output_bytes=sum(v['size_bytes'] for v in seal.values()))
    else:
        if root.exists():
            raise ValueError('Existing incomplete native scene requires validation-only recovery: '+str(root))
        record=run_one(source,bundle,contract,ctx.reg,root,ctx.code_commit,
            original_text=text,dataset=dataset,sequence_spec=ctx.v2['sequences'][dataset],case_meta=meta)
    record['domain']=job['domain']
    if transport:record.update(native_template_transport=transport,duration_s=meta['duration_s'])
    for item in record.get('bookkeeping_notes',[]):note(ctx,'NATIVE_VALIDATION_ADAPTATION',run_id=record['run_id'],detail=item)
    if record['terminal_status'] not in ('COMPLETED','ALGORITHM_FAILURE_ALL_YAW_REJECTED'):
        if record.get('exit_code') not in (None,0):
            raise ScientificStop('NATIVE_UNREGISTERED_FAILURE',str(record))
        if 'non-finite' in record.get('failure','').lower() or 'nonfinite' in record.get('failure','').lower():
            raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE',str(record))
        raise ValueError('Retain native output for validation-only repair: '+str(record.get('failure')))
    print('P13_SOLVER',record['run_id'],record['terminal_status'],flush=True)
    return record


def run_batches(ctx,through):
    from .evaluation import evaluate_batch
    freeze(ctx)
    contract=effective_contract(ctx)
    base=bases(ctx)
    gate=json.loads((ctx.stage/'03_F01_INVARIANCE/F01_INVARIANCE_GATE.json').read_text())
    if gate['status']!='PASS':raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE','F01 gate failed')
    jobs,c00=build_jobs(ctx)
    workers=solver_workers()
    context_io={'stage':ctx.stage,'root':ctx.stage/'CONTROLLER','scratch':ctx.scratch,
        'io_fix_id':'P13','freeze':{'io_fix_code_commit':ctx.code_commit},'write_workers':6}
    context_io['root'].mkdir(exist_ok=True)
    total=math.ceil(len(jobs)/256)
    for number in range(1,min(through,total)+1):
        output=ctx.stage/'BATCHES'/f'BATCH_{number:03d}'
        if (output/'BATCH_COMPLETE.json').exists():continue
        batch=jobs[(number-1)*256:number*256]
        scratch=ctx.scratch/f'BATCH_{number:03d}'
        output.mkdir(parents=True,exist_ok=True);scratch.mkdir(parents=True,exist_ok=True)
        dump_status(ctx,status='RUNNING',phase='MAIN_BATCH',batch=number,total_batches=total,
                    completed_main_runs=(number-1)*256,main_run_total=5880)
        with ResourceMonitor(ctx.scratch,ctx.reg.clean_root,output/'RESOURCES.jsonl') as monitor:
            monitor.begin_phase('providers')
            bundles={}
            for job in batch:
                key=job['source']['case_id'] if job['dataset']=='BY2' else job['dataset']
                if key in bundles:continue
                if key=='C00_clean_normal':bundles[key]=base['BY2']
                elif key in base:bundles[key]=base[key]
                else:
                    bundles[key]=provider_task(ctx,ctx.stage/'02_CASE_PROVIDERS',case=job['case_meta'],base_bundle=ctx.stage/'02_BASE_PROVIDERS/BY2/PROVIDER_BUNDLE.json')
            monitor.end_phase();monitor.begin_phase('solver')
            records=[]
            for offset in range(0,len(batch),workers):
                wave=batch[offset:offset+workers]
                errors=[]
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures=[pool.submit(execute,ctx,j,bundles[j['source']['case_id'] if j['dataset']=='BY2' else j['dataset']],contract,scratch,c00) for j in wave]
                    for future in as_completed(futures):
                        try:
                            record=future.result();records.append(record)
                            persist(output/'NATIVE_TERMINALS'/f"{record['run_id']}.json",record)
                        except Exception as error:errors.append(error)
                if errors:
                    raise next((e for e in errors if isinstance(e,ScientificStop)),errors[0])
            solve_resource=monitor.end_phase()
            records.sort(key=lambda r:next(i for i,j in enumerate(batch) if j['source']['run_id']==r['run_id']))
            persist(output/'NATIVE_RECORDS.json',records)
            monitor.begin_phase('evaluators')
            rows,resources=evaluate_batch(records,contract,ctx.reg,scratch,ctx.code_commit,output,
                solve_resource['owned_rss_peak_bytes'],io_context=context_io)
            for row in rows:
                record=next(r for r in records if r['run_id']==row['run_id'])
                row.update(domain=record['domain'],sensor_model_group_hash=ctx.v21['sensor_model_group_hash'],
                           semisynthetic_data_used=record['data_mode']=='semisynthetic',data_mode=record['data_mode'])
                if row['evaluation_status'] not in ('COMPLETED','NOT_RUN_ALGORITHM_FAILURE'):
                    raise ScientificStop('EVALUATOR_FAILURE_OR_NONFINITE',str(row))
                if record['domain']=='ADDENDUM':
                    patched=finish_evaluation(row,record,{'data_roles':{'data_mode':'semisynthetic','synthetic_data_used':False,'semisynthetic_data_used':True}},ctx.code_commit)
                    row.update(patched)
            rows.sort(key=lambda r:(r['run_id'],r['evaluator_version']))
            monitor.end_phase();persist(output/'EVALUATION_PREARCHIVE.json',rows)
            monitor.begin_phase('archive_and_exact_cleanup')
            context_io['current_batch_run_count']=len(batch)
            records,rows,receipts,archive=archive_batch(records,rows,context=context_io,
                scratch_batch=scratch,output=output,batch_number=number,monitor=monitor)
            archive.update(v21_scientific_code_commit=ctx.code_commit,unique_denominator=len(jobs))
            monitor.end_phase()
        summary={'status':'PASS','batch':number,'runs':len(records),'completed':sum(r['terminal_status']=='COMPLETED' for r in records),
            'algorithm_failures':sum(r['terminal_status']=='ALGORITHM_FAILURE_ALL_YAW_REJECTED' for r in records),
            'evaluator_terminals':len(rows),'archive':archive,'resources':resources,'code_commit':ctx.code_commit}
        write_json(output/'BATCH_COMPLETE.json',summary)
        append_json(ctx.stage/'BATCH_LEDGER.jsonl',summary)
        print('P13_BATCH_COMPLETE',number,len(records),'pending',archive['pending_run_ids'],flush=True)
    dump_status(ctx,status='CHECKPOINT_READY' if through<total else 'MAIN_BATCHES_TERMINAL',
                completed_main_runs=min(through*256,len(jobs)),phase='BATCH_CHECKPOINT')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local-config',required=True)
    p.add_argument('--operation',choices=('freeze','bases','f01','checkpoint','run','status'),required=True)
    p.add_argument('--checkpoint-name',default='PRE')
    p.add_argument('--through-batch',type=int,default=24)
    args=p.parse_args(argv)
    ctx=context(args.local_config)
    try:
        if args.operation=='freeze':result=freeze(ctx)
        elif args.operation=='bases':result=bases(ctx)
        elif args.operation=='f01':
            from .f01_audit import run_audit
            phase_freeze(ctx,'F01_AUDIT')
            result=run_audit(ctx)
        elif args.operation=='checkpoint':result=raw_checkpoint(ctx,args.checkpoint_name)
        elif args.operation=='run':result=run_batches(ctx,args.through_batch)
        else:result=json.loads((ctx.stage/'STATUS.json').read_text())
        print(json.dumps({'operation':args.operation,'status':'RETURNED','code_commit':ctx.code_commit}),flush=True)
    except ScientificStop as error:
        dump_status(ctx,status='SCIENTIFIC_STOP',kind=error.kind,reason=str(error))
        write_json(ctx.stage/'STOPPED.json',{'kind':error.kind,'reason':str(error),'code_commit':ctx.code_commit})
        raise
    except Exception as error:
        note(ctx,'BOOKKEEPING_REPAIR_REQUIRED',error_type=type(error).__name__,reason=str(error))
        dump_status(ctx,status='BOOKKEEPING_REPAIR_REQUIRED',reason=str(error))
        raise

if __name__=='__main__':main()
