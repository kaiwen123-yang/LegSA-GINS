"""No-retry v3 phase controller; all native gates are reused in the matrix."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import threading

import yaml

from ..hext.sequence_paths import load_sequence_paths, REGISTRY, CALIBRATED_CONTRACT
from ..manifest import sha256_file
from .registry import STAGE, build_registry, validate_registry
from . import runtime


def _resolve(value,paths):
    if isinstance(value,dict):return {k:_resolve(v,paths) for k,v in value.items()}
    if isinstance(value,list):return [_resolve(v,paths) for v in value]
    if isinstance(value,str):
        for k,v in paths.items():value=value.replace('<'+k.upper()+'>',str(v))
    return value


def _persist(path,value):
    path=Path(path)
    if path.exists():
        if json.loads(path.read_text())!=value:raise RuntimeError('HARD_STOP_V3_CHECKPOINT_CHANGED: '+str(path))
    else:runtime.write_json(path,value)
    return value


def freeze_receipt(code,freeze,contract_path):
    """Check pushed code and every tracked clean Python dependency before work."""
    def git(*args):return subprocess.check_output(['git',*args],cwd=code,text=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).strip()
    remote=git('ls-remote','origin','refs/heads/stage/clean3-math-repair').split()
    if git('rev-parse','HEAD')!=freeze or not remote or remote[0]!=freeze:
        raise RuntimeError('HARD_STOP_V3_CODE_FREEZE_NOT_CURRENT_AND_PUSHED')
    names=git('ls-files','src/legsa_gins/paper_rebuild','src/legsa_gins/input_generation','src/legsa_gins/raw_gnss','src/legsa_gins/go2_prior','src/legsa_gins/datasets/by2','scripts/paper_rebuild').splitlines()
    names=[name for name in names if name.endswith('.py')]
    names.append(Path(contract_path).relative_to(code).as_posix())
    names.extend((str(REGISTRY),str(CALIBRATED_CONTRACT)))
    contract=yaml.safe_load(Path(contract_path).read_text())
    for key in ('provider_source_index','report_source_index'):
        if key in contract:
            pin=contract[key];path=code/pin['path']
            runtime.verify_pin({'path':str(path),'sha256':pin['sha256']})
            names.append(pin['path'])
    tracked=git('ls-files').splitlines()
    snapshot=[p for p in tracked if p.startswith(('docs/paper_rebuild/v3/','configs/paper_rebuild/v3/','src/legsa_gins/paper_rebuild/protocol_v3/','scripts/paper_rebuild/v3_','tests/paper_rebuild/test_protocol_v3'))]
    names=sorted(set(names+snapshot))
    sources={}
    for name in names:
        frozen=subprocess.check_output(['git','show',freeze+':'+name],cwd=code)
        path=code/name
        if path.read_bytes()!=frozen:raise RuntimeError('HARD_STOP_V3_SOURCE_NOT_FROZEN: '+name)
        sources[name]=sha256_file(path)
    return {'status':'PASS_PUSHED_CODE_FREEZE','code_freeze':freeze,'remote_commit':remote[0],'source_sha256':sources,'source_snapshot_paths':snapshot}


class Context:
    def __init__(self,local_config,contract_path,code_freeze):
        self.local=Path(local_config).resolve()
        self.paths=yaml.safe_load(self.local.read_text())['paths']
        self.code=Path(self.paths['code_root']);self.clean=Path(self.paths['clean_root'])
        self.scratch=runtime.frozen._safe(self.paths['protocol_v3_scratch'])
        self.archive=self.clean/'stages'/STAGE
        if self.scratch.name!=STAGE or str(self.scratch).startswith('/mnt/') or any(
            runtime.frozen._within(self.scratch,Path(self.paths[k])) for k in ('code_root','clean_root','raw_root')):
            raise ValueError('V3 requires a dedicated ext4 scratch alias')
        self.contract_path=Path(contract_path).resolve();self.code_freeze=code_freeze
        self.contract=_resolve(yaml.safe_load(self.contract_path.read_text()),self.paths)
        self.contract['config_hash']=sha256_file(self.contract_path)
        self.freeze=freeze_receipt(self.code,code_freeze,self.contract_path)
        self.contexts={s:load_sequence_paths(s,local_config=self.local,registry_path=self.code/REGISTRY,
            calibrated_contract_path=self.code/CALIBRATED_CONTRACT) for s in ('BY2','BY2H','BY2O')}
        saved_registry=self.scratch/'00_PREREGISTRATION/REGISTRY.json'
        if saved_registry.exists():
            seal=json.loads((saved_registry.parent/'REGISTRY_FILE_SEAL.json').read_text())
            runtime.verify_pin({'path':str(saved_registry),'sha256':seal['sha256']},cached=False)
            for pin in self.contract['registry_sources']:runtime.verify_pin(pin,cached=False)
            self.specs=json.loads(saved_registry.read_text())
        else:self.specs=build_registry(self.local,source_pins=self.contract['registry_sources'])
        validate_registry(self.specs)
        self.allowed=[s['run_id'] for s in self.specs]
        self.eval_allowed=[r+'__'+v for r in self.allowed for v in ('v3','v2')]
        self.binary=Path(self.contract['frozen']['executable']['path'])
        self.evaluator=Path(self.contract['frozen']['evaluator']['path'])
        for key,digest in [('executable',runtime.BINARY_SHA256),('evaluator',runtime.EVALUATOR_SHA256)]:
            pin=self.contract['frozen'][key]
            if pin['sha256']!=digest:raise RuntimeError('HARD_STOP_V3_FROZEN_'+key.upper()+'_REGISTRATION')
            runtime.verify_pin(pin)
        if (self.scratch/'CONTROLLER_HARD_STOP.json').exists() or (self.scratch/'IDENTITY_HARD_STOP.json').exists():
            raise RuntimeError('HARD_STOP_V3_PERSISTED_CONTROLLER_STOP')
        self.scratch.mkdir(parents=True,exist_ok=True);self.archive.mkdir(parents=True,exist_ok=True)
        self.snapshot_sources()
        _persist(self.scratch/'00_PREREGISTRATION/EXECUTION_FREEZE.json',self.freeze)
        _persist(self.scratch/'00_PREREGISTRATION/REGISTRY.json',self.specs)
        _persist(self.scratch/'00_PREREGISTRATION/REGISTRY_FILE_SEAL.json',{'sha256':sha256_file(saved_registry),'status':'SEALED','run_count':len(self.specs)})
        _persist(self.scratch/'00_PREREGISTRATION/REGISTRY_GATE.json',validate_registry(self.specs))
        self._install_guard()

    def snapshot_sources(self):
        root=self.scratch/'00_PREREGISTRATION/SOURCE_SNAPSHOT'
        files={}
        for relative in self.freeze['source_snapshot_paths']:
            source=self.code/relative;payload=source.read_bytes()
            if sha256_file(source)!=self.freeze['source_sha256'][relative]:
                raise RuntimeError('HARD_STOP_V3_SNAPSHOT_SOURCE_DRIFT')
            target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if target.read_bytes()!=payload:raise RuntimeError('HARD_STOP_V3_EXISTING_SNAPSHOT_DRIFT')
            else:
                with target.open('xb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
            files[relative]={'sha256':self.freeze['source_sha256'][relative],'size_bytes':len(payload)}
        _persist(root/'SOURCE_SNAPSHOT_MANIFEST.json',{'status':'PASS','code_freeze':self.code_freeze,
            'files':files,'local_path_config_included':False,'raw_or_binary_payload_included':False})

    def native_batch(self,batch,number):
        """Cancel unstarted work after failure, drain and seal running work."""
        first_error=None;records=[];outcomes=[]
        with ThreadPoolExecutor(max_workers=64) as pool:
            futures={pool.submit(self._native,s):s for s in batch}
            for future in as_completed(futures):
                spec=futures[future]
                if future.cancelled():
                    outcomes.append({'run_id':spec['run_id'],'status':'CANCELLED_BEFORE_START'})
                    continue
                try:
                    record=future.result();records.append(record)
                    outcomes.append({'run_id':spec['run_id'],'status':record['status']})
                    print('V3_NATIVE',record['run_id'],record['status'],flush=True)
                except Exception as exc:
                    outcomes.append({'run_id':spec['run_id'],'status':'HARD_STOP','error':str(exc)})
                    if first_error is None:
                        first_error=exc
                        for pending in futures:pending.cancel()
        if first_error is not None:
            receipt={'status':'HARD_STOP_RUNNING_INVOCATIONS_DRAINED','batch_number':number,
                'outcomes':outcomes,'all_started_futures_drained':True,
                'no_evaluator_or_later_batch_launched':True,'retry_count':0,
                'completed_records':records,'native_summary_roots':[str(self.scratch/'03_NATIVE'/s['run_id']) for s in batch]}
            _persist(self.scratch/f'BATCHES/BATCH_{number:03d}/HARD_STOP_DRAIN.json',receipt)
            raise first_error
        return records

    def _install_guard(self):
        raw=Path(self.paths['raw_root'])
        self.parent_raw_opens=[]
        def guard(event,args):
            if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
            path=Path(os.fsdecode(args[0])).absolute()
            if runtime.frozen._within(path,raw):self.parent_raw_opens.append(str(path))
            if path.name.lower().startswith('trace_') or path.suffix.lower() in ('.bag','.fpl'):
                raise PermissionError('V3 trace/bag/fpl only in registered evaluator child')
            if runtime.frozen._within(path,raw) and path.name not in ('gnss1-raw.csv','gnss2-raw.csv'):
                raise PermissionError('V3 parent raw source denied: '+str(path))
        import sys
        sys.addaudithook(guard)

    def prepare(self):
        path=self.scratch/'02_PROVIDERS/PROVIDER_REGISTRY.json'
        if path.exists():
            self.providers=json.loads(path.read_text())
        else:
            from .providers import prepare_providers
            self.providers=prepare_providers(self.local,self.specs,self.code_freeze,self.contract)
        gate_result=json.loads((self.scratch/'02_PROVIDERS/GATES_2A_2B.json').read_text())
        gates={gate:({'status':gate_result['gate_'+gate]} if isinstance(gate_result['gate_'+gate],str) else gate_result['gate_'+gate]) for gate in ('2a','2b')}
        for gate,value in gates.items():
            if value.get('status')!='PASS':raise RuntimeError('HARD_STOP_V3_PROVIDER_IDENTITY_GATE_'+gate)
        self.admissions={}
        for spec in self.specs:
            provider=self.providers[spec['provider_key']]
            self.admissions[spec['run_id']]=runtime.prepare_config(spec,provider,
                self.scratch/'02_CONFIGS'/spec['run_id'])
        config_gate={'status':'PASS','phase':'PRELAUNCH_BYTES_AND_211_EXPECTATIONS','configuration_count':len(self.specs),
            'actual_echo_policy':'Each completed native must emit and match all 211 fields; failed native missing echoes remain unavailable'}
        _persist(self.scratch/'02_CONFIGS/CONFIG_GATE.json',config_gate)
        self.gates={**gates,'2c':config_gate}
        audit={'status':'PASS','raw_source_open_count':len(self.parent_raw_opens),
               'raw_source_paths':self.parent_raw_opens,'trace_open_count':0,'bag_fpl_open_count':0,
               'guard':'DENY_PARENT_TRACE_BAG_FPL; ONLY_GNSS1_GNSS2_RAW_SOURCE_OPENS_ALLOWED'}
        audit_path=self.scratch/'02_CONFIGS'/('PARENT_ACCESS_AUDIT_'+str(os.getpid())+'.json')
        _persist(audit_path,audit)
        return self.gates

    def _native(self,spec):
        return runtime.run_native(self.contexts[spec['sequence_id']],spec,self.admissions[spec['run_id']],
            binary=self.binary,output_root=self.scratch/'03_NATIVE'/spec['run_id'],scratch_root=self.scratch,
            code_freeze=self.code_freeze,ledger=self.scratch/'00_PREREGISTRATION/NATIVE_RESERVATIONS.jsonl',
            allowed_run_ids=self.allowed,timeout_seconds=self.contract.get('native_timeout_seconds',1800))

    def identities(self):
        if not hasattr(self,'admissions'):self.prepare()
        runtime.verify_pin(self.contract['frozen']['t5a_nav'],cached=False)
        selected=[s for s in self.specs if s['method_id']=='F01' and
                  (s['case_id']=='C00_clean_normal' or s['domain']=='SEQUENCE')]
        selected += [s for s in self.specs if s['sequence_id']=='BY2' and s['case_id']=='C00_clean_normal' and s['method_id']=='F04']
        if len(selected)!=4:raise RuntimeError('HARD_STOP_V3_IDENTITY_RUN_REGISTRY')
        comparisons=[]
        for spec in selected:
            record=self._native(spec)
            target=spec['frozen_nav'] if spec['method_id']=='F01' else self.contract['frozen']['t5a_nav']
            if record['status']!='COMPLETED':raise RuntimeError('HARD_STOP_V3_IDENTITY_NATIVE_NOT_COMPLETED')
            same=record['nav_sha256']==target['sha256']
            comparisons.append({'run_id':spec['run_id'],'sequence_id':spec['sequence_id'],'configuration_id':spec['method_id'],
                'actual_sha256':record['nav_sha256'],'expected_sha256':target['sha256'],'byte_identical':same,
                'full_NAV':True,'gate':'2d' if spec['method_id']=='F01' else '2e'})
            if not same:
                _persist(self.scratch/'IDENTITY_HARD_STOP.json',{'status':'HARD_STOP','comparisons':comparisons})
                raise RuntimeError('HARD_STOP_V3_FULL_NAV_BYTE_IDENTITY')
        for gate in ('2d','2e'):
            self.gates[gate]={'status':'PASS','comparisons':[r for r in comparisons if r['gate']==gate]}
        return _persist(self.scratch/'IDENTITY_GATES.json',{'status':'PASS','gates':self.gates})

    def _evaluate(self,record,version):
        return runtime.evaluate_native(self.contexts[record['sequence_id']],self.evaluator,record,version,
            output_root=self.scratch/'04_EVALUATION'/record['run_id']/version,scratch_root=self.scratch,
            ledger=self.scratch/'00_PREREGISTRATION/EVALUATOR_RESERVATIONS.jsonl',allowed_run_ids=self.eval_allowed)

    def evaluation_batch(self,records,number):
        first_error=None;results=[];outcomes=[]
        with ThreadPoolExecutor(max_workers=min(32,len(records)*2)) as pool:
            futures={pool.submit(self._evaluate,r,v):(r['run_id'],v) for r in records for v in ('v3','v2')}
            for future in as_completed(futures):
                rid,version=futures[future]
                if future.cancelled():
                    outcomes.append({'run_id':rid,'version':version,'status':'CANCELLED_BEFORE_START'})
                    continue
                try:
                    payload=future.result();results.append(payload)
                    outcomes.append({'run_id':rid,'version':version,'status':payload['row']['evaluation_status']})
                except Exception as exc:
                    outcomes.append({'run_id':rid,'version':version,'status':'HARD_STOP','error':str(exc)})
                    if first_error is None:
                        first_error=exc
                        for pending in futures:pending.cancel()
        if first_error is not None:
            _persist(self.scratch/f'BATCHES/BATCH_{number:03d}/EVALUATOR_HARD_STOP_DRAIN.json',{
                'status':'HARD_STOP_RUNNING_EVALUATORS_DRAINED','outcomes':outcomes,
                'all_started_futures_drained':True,'no_later_batch_launched':True,
                'completed_results':results,'retry_count':0})
            raise first_error
        return results

    def postflight(self):
        """One final complete rehash of unique input providers and frozen code."""
        pins={}
        for spec in self.specs:
            for pin in spec['frozen_providers'].values():pins[(pin['path'],pin['sha256'])]=pin
        for pin in self.providers.values():pins[(pin['path'],pin['sha256'])]={'path':pin['path'],'sha256':pin['sha256']}
        for key in ('executable','evaluator','t5a_nav'):
            pin=self.contract['frozen'][key];pins[(pin['path'],pin['sha256'])]=pin
        verified=[]
        for _,pin in sorted(pins.items()):
            path=runtime.verify_pin(pin,cached=False)
            verified.append({'path':str(path),'sha256':pin['sha256'],'size_bytes':path.stat().st_size})
        for relative,digest in self.freeze['source_sha256'].items():
            runtime.verify_pin({'path':str(self.code/relative),'sha256':digest},cached=False)
        return _persist(self.scratch/'POSTFLIGHT_INPUT_IDENTITIES.json',{
            'status':'PASS','unique_pin_count':len(verified),'pins':verified,
            'code_source_count':len(self.freeze['source_sha256']),
            'binary_sha256':runtime.BINARY_SHA256,'evaluator_sha256':runtime.EVALUATOR_SHA256,
            'raw_payload_rehashed':False,'raw_hash_lock_gate':'PROVIDER_PREPARATION',
            'data_mode':'execution_metadata_only','synthetic_data_used':False,'semisynthetic_data_used':False})

    def matrix(self):
        if not hasattr(self,'admissions'):self.prepare()
        if (self.scratch/'IDENTITY_GATES.json').exists():
            self.gates=json.loads((self.scratch/'IDENTITY_GATES.json').read_text())['gates']
            if any(self.gates[k]['status']!='PASS' for k in ('2a','2b','2c','2d','2e')):raise RuntimeError('HARD_STOP_V3_SAVED_GATE')
        else:self.identities()
        records=[];evaluations=[]
        # Dispatch bounded batches; a hard stop prevents all later batches.
        for number,start in enumerate(range(0,len(self.specs),64),1):
            batch=self.specs[start:start+64]
            batch_records=self.native_batch(batch,number)
            batch_evaluations=self.evaluation_batch(batch_records,number)
            def archive_native(record):
                receipt=runtime.archive_directory(self.scratch/'03_NATIVE'/record['run_id'],self.archive/'03_NATIVE'/record['run_id'],scratch_root=self.scratch)
                return runtime.archived_native(record,receipt)
            def archive_evaluation(payload):
                rid=payload['row']['run_id'];version=payload['row']['evaluator_contract'].rsplit('_',1)[1]
                receipt=runtime.archive_directory(self.scratch/'04_EVALUATION'/rid/version,self.archive/'04_EVALUATION'/rid/version,scratch_root=self.scratch)
                return {**payload,'archive_output_root':receipt['archive_root'],'archive_receipt':str(Path(receipt['archive_root'])/'ARCHIVE_RECEIPT.json'),'resolved_error_series_source':str(Path(receipt['archive_root'])/'FROZEN_EVALUATOR')}
            with ThreadPoolExecutor(max_workers=8) as pool:
                archived_records=list(pool.map(archive_native,batch_records))
                batch_evaluations=list(pool.map(archive_evaluation,batch_evaluations))
            batch_records=sorted(archived_records,key=lambda r:r['run_id'])
            batch_evaluations=sorted(batch_evaluations,key=lambda r:(r['row']['run_id'],r['row']['evaluator_contract']))
            records.extend(batch_records);evaluations.extend(batch_evaluations)
            _persist(self.scratch/f'BATCHES/BATCH_{number:03d}/RUN_RECORDS.json',batch_records)
            _persist(self.scratch/f'BATCHES/BATCH_{number:03d}/EVALUATION_RECORDS.json',batch_evaluations)
            print('V3_PROGRESS',len(records),len(self.specs),'EVALUATIONS',len(evaluations),flush=True)
        if len(records)!=6468 or len(evaluations)!=12936:raise RuntimeError('HARD_STOP_V3_TERMINAL_COUNTS')
        self.postflight()
        self.gates['2c']={**self.gates['2c'],'phase':'COMPLETED_NATIVE_ADMISSION',
            'actual_211_echo_pass_count':sum(r.get('effective_echo_gate',{}).get('passed') is True for r in records),
            'actual_echo_unavailable_classified_failure_count':sum(r.get('effective_echo_gate',{}).get('passed') is None and r['status'].startswith('ALGORITHM_FAILURE_') for r in records),
            'actual_echo_unavailable_not_a_pass':True}
        _persist(self.scratch/'FINAL_IDENTITY_GATES.json',{'status':'PASS','gates':self.gates})
        _persist(self.scratch/'FINAL_RUN_RECORDS.json',sorted(records,key=lambda r:r['run_id']))
        _persist(self.scratch/'FINAL_EVALUATION_RECORDS.json',sorted(evaluations,key=lambda r:(r['row']['run_id'],r['row']['evaluator_contract'])))
        result={'status':'PASS_V3_EXECUTION_COMPLETE','native_terminal_count':len(records),
            'evaluator_terminal_count':len(evaluations),'gate_native_reused':4,'retry_count':0}
        _persist(self.scratch/'STATUS.json',result)
        for name in ('FINAL_RUN_RECORDS.json','FINAL_EVALUATION_RECORDS.json','STATUS.json','IDENTITY_GATES.json','FINAL_IDENTITY_GATES.json','POSTFLIGHT_INPUT_IDENTITIES.json'):
            _persist(self.archive/name,json.loads((self.scratch/name).read_text()))
        return result


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--local-config',required=True);parser.add_argument('--contract',required=True)
    parser.add_argument('--code-freeze',required=True);parser.add_argument('--phase',choices=('prepare','identities','matrix'),required=True)
    args=parser.parse_args(argv)
    ctx=Context(args.local_config,args.contract,args.code_freeze)
    try:result=getattr(ctx,args.phase)()
    except Exception as exc:
        target=ctx.scratch/'CONTROLLER_HARD_STOP.json'
        if not target.exists():runtime.write_json(target,{'status':'HARD_STOP','phase':args.phase,'error':str(exc),'retry_count':0})
        raise
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
