#!/usr/bin/env python3
"""HX-03R-2: audited reevaluation of retained external outputs, never native runs."""
from __future__ import annotations

import builtins
import io
import os
from pathlib import Path

def deny_reference(original):
    def checked(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            name = os.fsdecode(file)
            if '/data/raw/' in name or 'trace_vrtk' in Path(name).name or name.endswith(('.bag','.fpl')):
                raise RuntimeError('HARD_STOP_CONTROLLER_REFERENCE_OPEN: '+name)
        return original(file,*args,**kwargs)
    return checked
builtins.open=deny_reference(builtins.open)
io.open=deny_reference(io.open)

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
import shutil
import subprocess
import threading
import time

import yaml
from legsa_gins.paper_rebuild.hext import hx02_evaluation_process as launcher
from legsa_gins.paper_rebuild.hext import external_evaluation as ext
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths
from legsa_gins.paper_rebuild.canonical541 import offline_eval_aggregate as canonical


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    with Path(path).open('x') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n')


def utc():
    return datetime.now(timezone.utc).isoformat()


def science_identity(old_summary, old_errors, new_summary, new_errors):
    result={'summary_json':{'R1':old_summary,'R2':sha(new_summary)},
            'error_series_csv':{'R1':old_errors,'R2':sha(new_errors)}}
    result['passed']=all(v['R1']==v['R2'] for k,v in result.items() if k!='passed')
    return result


def numeric_identity(old, new):
    # Preserve all old numeric scientific statistics, including coverage/counts.
    keys=sorted(k for k,v in old.items() if isinstance(v,(int,float)) and not isinstance(v,bool))
    old_values={k:old[k] for k in keys}
    new_values={k:new.get(k) for k in keys}
    encode=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return {'fields':keys,'field_count':len(keys),'passed':encode(old_values)==encode(new_values),
            'R1_sha256':hashlib.sha256(encode(old_values)).hexdigest(),
            'R2_sha256':hashlib.sha256(encode(new_values)).hexdigest(),
            'differences':{k:{'R1':old[k],'R2':new.get(k)} for k in keys if old[k]!=new.get(k)}}


class Controller:
    def __init__(self,W):
        self.W=W
        local=yaml.safe_load((W/'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
        self.stages=Path(local['clean_root'])/'stages'
        self.root=self.stages/'CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL'
        self.scratch=Path(local['hx02_scratch'])/'HX03R2'
        self.control=self.root/'00_CONTROL'
        self.slots=json.loads((self.control/'EVALUATION_SLOTS_R2.json').read_text())
        self.seq=load_sequence_paths('BY2')
        self.lock=threading.RLock()
        self.stop=threading.Event()
        self.ledger=self.control/'LEDGER_R2.jsonl'
        self.events=[json.loads(x) for x in self.ledger.read_text().splitlines()] if self.ledger.exists() else []
        launcher.REGISTERED_CHILDREN['HX03R2_FROZEN']='legsa_gins.paper_rebuild.hext.hx03r2_observer'
        self.phase=''

    def event(self,event,**data):
        with self.lock:
            row={'utc':utc(),'event':event,**data}
            with self.ledger.open('a') as f:
                f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
            self.events.append(row)

    def progress(self,status):
        with self.lock:
            row={'utc':utc(),'status':status,'phase':self.phase,'native_calls':0,'legsa_native':0,'legsa_evaluation':0,
                'external_evaluation':self.call_count(),
                'launch_attempts':sum(e['event']=='RESERVED' for e in self.events),
                'preexec_launch_failures':sum(e['event']=='PREEXEC_NOT_STARTED' for e in self.events),
                'archived_evaluation_slots':sum(e['event']=='ARCHIVED' for e in self.events),
                'reference_opens_verified':sum(e.get('trace_open_count',0) for e in self.events if e['event']=='ARCHIVED'),
                'retries':0}
            (self.control/'STATE_R2.json').write_text(json.dumps(row,indent=2)+'\n')
            (self.control/'PROGRESS_R2.txt').write_text(json.dumps(row)+'\n')
            print(json.dumps(row),flush=True)

    def call_count(self):
        return sum(e['event']=='RESERVED' for e in self.events)-sum(e['event']=='PREEXEC_NOT_STARTED' for e in self.events)

    def guard(self):
        available={p:int(subprocess.check_output(['df','-B1','--output=avail',p],text=True).splitlines()[-1]) for p in ('/mnt/e','/mnt/g')}
        if available['/mnt/e']<40_000_000_000 or available['/mnt/g']<30_000_000_000:
            raise RuntimeError('HARD_STOP_DF_GUARD')
        size=sum(p.stat().st_size for p in self.scratch.rglob('*') if p.is_file())
        if size>20_000_000_000:
            raise RuntimeError('HARD_STOP_SCRATCH_LIMIT')
        self.event('DISK_GUARD',available_bytes=available,scratch_bytes=size)

    def verify_code(self):
        pins=json.loads((self.control/'CODE_PINS_R2.json').read_text())
        for rel,value in pins.items():
            if sha(self.W/rel)!=value:
                raise RuntimeError('HARD_STOP_CODE_PIN: '+rel)
        if self.phase=='matrix':
            frozen=json.loads((self.control/'CODE_FREEZE_R2.json').read_text())
            subprocess.run(['git','merge-base','--is-ancestor',frozen['commit'],'HEAD'],cwd=self.W,check=True)

    def archived(self,slot):
        return self.root/'RUNS'/slot['run_id']/(slot['version']+'_R2')

    def execute(self,slot,validation):
        sid=slot['slot_id']
        with self.lock:
            prior=[e for e in self.events if e.get('slot_id')==sid]
            if any(e['event']=='ARCHIVED' for e in prior):
                dest=self.archived(slot)
                receipt=json.loads((dest/'ARCHIVE_RECEIPT_R2.json').read_text())
                for name,value in receipt['files_sha256'].items():
                    if sha(dest/name)!=value:
                        raise RuntimeError('HARD_STOP_ARCHIVE_IDENTITY')
                return json.loads((dest/'RESULT_R2.json').read_text())
            if sum(e['event']=='RESERVED' for e in prior)>sum(e['event']=='PREEXEC_NOT_STARTED' for e in prior):
                raise RuntimeError('HARD_STOP_RESERVED_SLOT_NOT_RETRIED: '+sid)
        if self.stop.is_set():
            return None
        ep=Path(slot['old_eval_dir'])
        old_record=json.loads((ep/'EVALUATION_RESULT.json').read_text())
        if sha(ep/'EVALUATION_RESULT.json')!=slot['old_evaluation_result_sha256']:
            raise RuntimeError('HARD_STOP_R1_RECORD_IDENTITY')
        if sha(slot['nav'])!=slot['nav_sha256'] or sha(slot['native_nav'])!=slot['native_nav_sha256']:
            raise RuntimeError('HARD_STOP_NATIVE_OUTPUT_IDENTITY')
        if sha(ep/'OUTPUT/summary.json')!=slot['old_summary_sha256'] or sha(ep/'OUTPUT/error_series.csv')!=slot['old_error_series_sha256']:
            raise RuntimeError('HARD_STOP_R1_SCIENTIFIC_OUTPUT_IDENTITY')
        work=self.scratch/'RUNS'/sid
        spec={k:slot[k] for k in ('evaluator','trace','trace_sha256','nav','nav_sha256','base_time','window')}
        with self.lock:
            if self.call_count()>=492:
                raise RuntimeError('HARD_STOP_EVALUATION_BUDGET')
            if self.stop.is_set():return None
            self.event('RESERVED',slot_id=sid,validation=validation,run_id=slot['run_id'],version=slot['version'])
        try:
            child=launcher.run_child('HX03R2_FROZEN',spec,workdir=work,code_root=self.W,
                raw_root=self.seq.raw_root,clean_root=self.seq.clean_root,trace=self.seq.trace,timeout_seconds=600)
            out=Path(child['outdir'])
            capture=json.loads((out/'EVALUATOR_CAPTURE.json').read_text())
            failures=ext._capture_identity_failures(capture,self.seq,child['audit']['trace_open_records'])
            if failures:raise RuntimeError('HARD_STOP_REFERENCE_IDENTITY: '+';'.join(failures))
            identity=science_identity(slot['old_summary_sha256'],slot['old_error_series_sha256'],out/'summary.json',out/'error_series.csv')
            write(work/'SCIENTIFIC_IDENTITY_R2.json',identity)
            if not identity['passed']:raise RuntimeError('HARD_STOP_FROZEN_OUTPUT_BYTES_DIFFER')
            detail=json.loads((out/'AUDIT_DETAIL_R2.json').read_text())
            if validation and not detail['validation_position_passed']:
                raise RuntimeError('HARD_STOP_OBSERVER_VALIDATION_ABOVE_1e-9_M')
            original=canonical._read_numeric_table(Path(slot['native_nav'])).to_numpy(float)
            old=old_record['row']
            record_identity={k:old[k] for k in ('case_id','evaluator_contract','evaluator_nav_sha256','method_id','sequence_id','source_nav_sha256')}
            record_identity['status']='PRE_FAILURE' if slot['role']=='PRE_FAILURE' else 'COMPLETED'
            errors=canonical._read_error_series(out)
            scientific=ext.metrics(errors,original,record_identity,window=tuple(slot['window']),reference_count=capture['reference_epoch_count'])
            numeric=numeric_identity(old,scientific) if slot['old_audit_passed'] else {'passed':True,'field_count':0,'reason':'R1 unavailable has no admitted scientific metrics; frozen file identity remains mandatory'}
            if not numeric['passed']:raise RuntimeError('HARD_STOP_R1_AVAILABLE_SCIENTIFIC_METRICS_DIFFER: '+str(numeric['differences']))
            passed=capture['consistency']['passed']
            row={**scientific,'metrics_admitted':True} if passed else {**record_identity,'status':'UNAVAILABLE_EVALUATION_FAILED','metrics_admitted':False}
            result={'slot_id':sid,'run_id':slot['run_id'],'version':slot['version'],'case_id':slot['case_id'],
                'method':slot['method'],'family':slot['family'],'type':slot['type'],'role':slot['role'],
                'native_failure_class':slot['native_failure_class'],'audit_status_R1':'PASS' if slot['old_audit_passed'] else 'FAIL',
                'audit_status_R2':'PASS' if passed else 'FAIL','observer_discrepancy_R2':capture['consistency'],
                'scientific_identity':identity,'old_available_metrics_identity':numeric,'row':row,
                'R1_record_source':str(ep/'EVALUATION_RESULT.json'),'R1_record_sha256':slot['old_evaluation_result_sha256'],
                'validation':validation,'trace_open_count':child['audit']['trace_open_count'],
                'trace_sha256':capture['trace_sha256'],'runtime_seconds':child['runtime_seconds'],
                'residuals_sha256':detail['residuals_sha256'],'native_calls':0}
            write(work/'RESULT_R2.json',result)
            if sha(slot['nav'])!=slot['nav_sha256'] or sha(slot['native_nav'])!=slot['native_nav_sha256']:
                raise RuntimeError('HARD_STOP_NATIVE_CHANGED_DURING_EVALUATION')
            self.archive(slot,work)
            self.event('ARCHIVED',slot_id=sid,trace_open_count=1,validation=validation,
                runtime_seconds=child['runtime_seconds'],audit_status_R2=result['audit_status_R2'])
            self.progress('RUNNING')
            return result
        except BaseException as exc:
            self.stop.set()
            self.event('HARD_STOP',slot_id=sid,message=str(exc))
            raise

    def archive(self,slot,work):
        dest=self.archived(slot)
        dest.mkdir(parents=True,exist_ok=False)
        mapping={
            'SPEC.json':'SPEC_R2.json','EVALUATOR_OPENAT.strace':'EVALUATOR_OPENAT_R2.strace.gz',
            'EVALUATOR_STRACE_AUDIT.json':'EVALUATOR_STRACE_AUDIT_R2.json',
            'evaluator_stdout.log':'evaluator_stdout_R2.log','evaluator_stderr.log':'evaluator_stderr_R2.log',
            'SCIENTIFIC_IDENTITY_R2.json':'SCIENTIFIC_IDENTITY_R2.json','RESULT_R2.json':'RESULT_R2.json',
            'OUTPUT/CAPTURE_CONFIG_R2.json':'CAPTURE_CONFIG_R2.json',
            'OUTPUT/EVALUATOR_CAPTURE.json':'EVALUATOR_CAPTURE_R2.json',
            'OUTPUT/summary.json':'summary_R2.json','OUTPUT/error_series.csv':'error_series_R2.csv.gz',
            'OUTPUT/AUDIT_DETAIL_R2.json':'AUDIT_DETAIL_R2.json','OUTPUT/AUDIT_RESIDUALS_R2.csv.gz':'AUDIT_RESIDUALS_R2.csv.gz'}
        hashes={};uncompressed={}
        for old,new in mapping.items():
            source=work/old;target=dest/new
            if new.endswith('.gz') and not old.endswith('.gz'):
                # Compress in scratch first; verify the exact source bytes after decompression.
                packed=work/(new+'.tmp')
                with source.open('rb') as f,packed.open('xb') as raw:
                    with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0,compresslevel=6) as g:
                        shutil.copyfileobj(f,g)
                expected=sha(source);shutil.copyfile(packed,target)
                if sha(packed)!=sha(target):raise RuntimeError('HARD_STOP_ARCHIVE_COPY_HASH')
                digest=hashlib.sha256()
                with gzip.open(target,'rb') as f:
                    for chunk in iter(lambda:f.read(1<<20),b''):digest.update(chunk)
                if digest.hexdigest()!=expected:raise RuntimeError('HARD_STOP_COMPRESSED_BYTES_IDENTITY')
                uncompressed[new]=expected
            else:
                shutil.copyfile(source,target)
                if sha(source)!=sha(target):raise RuntimeError('HARD_STOP_ARCHIVE_COPY_HASH')
            hashes[new]=sha(target)
        write(dest/'ARCHIVE_RECEIPT_R2.json',{'files_sha256':hashes,'uncompressed_sha256':uncompressed,'verified':True})
        self.event('SCRATCH_DELETE_INTENT',slot_id=slot['slot_id'],path=str(work))
        shutil.rmtree(work)
        self.event('SCRATCH_DELETED',slot_id=slot['slot_id'])

    def run(self,phase,workers):
        self.phase=phase
        self.verify_code();self.guard()
        validation=[s for s in self.slots if s['case_id']=='C00' or
            (s['version']=='v3' and ((s['method']=='LC01' and s['case_id']=='D04_seed_00') or
                                   (s['method']=='EXT05C' and s['case_id']=='D62_20s_seed_00')))]
        if len(validation)!=6:raise RuntimeError('HARD_STOP_VALIDATION_SCOPE')
        if phase=='validation':
            results=[self.execute(s,True) for s in validation]
            write(self.control/'VALIDATION_RESULTS_R2.json',{'passed':True,'slots':results,'count':len(results),
                'counts_in_total_492':True,'maximum_position_discrepancy_m':max(max(r['observer_discrepancy_R2']['horizontal_max_m'],r['observer_discrepancy_R2']['up_max_m']) for r in results)})
        else:
            if not json.loads((self.control/'VALIDATION_RESULTS_R2.json').read_text())['passed']:
                raise RuntimeError('HARD_STOP_VALIDATION_REQUIRED')
            done={e['slot_id'] for e in self.events if e['event']=='ARCHIVED'}
            pending=[s for s in self.slots if s['slot_id'] not in done]
            for family in dict.fromkeys(s['family'] for s in pending):
                group=[s for s in pending if s['family']==family]
                self.guard();self.verify_code();self.event('FAMILY_BEGIN',family=family,slots=len(group))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures=[pool.submit(self.execute,s,False) for s in group]
                    for future in as_completed(futures):future.result()
                self.event('FAMILY_END',family=family,slots=len(group))
        self.progress('VALIDATION_PASSED' if phase=='validation' else 'MATRIX_COMPLETE')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=('validation','matrix'),required=True)
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args()
    if not 1<=args.workers<=8:raise ValueError('Audit worker count outside 1..8')
    c=Controller(Path.cwd())
    try:c.run(args.phase,args.workers)
    except BaseException as exc:
        c.progress('HARD_STOP')
        path=c.control/'HARD_STOP_R2.json'
        if not path.exists():write(path,{'utc':utc(),'message':str(exc),'native_calls':0})
        raise


if __name__=='__main__':main()
