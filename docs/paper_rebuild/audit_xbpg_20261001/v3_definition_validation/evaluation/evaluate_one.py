#!/usr/bin/env python3
"""One explicitly selected frozen-v3 evaluation. No Context, controller, solver or retry."""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
CODE=HERE.parents[4]
WINDOW=(66.,340.)
BASE_TIME=1772784000.
BASELINE_LENGTH=0.356191491865984
POLICY='canonical_v2_wgs84_full_support'
TRACE_SHA='ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c'
EVALUATOR_SHA='aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da'
BASELINE_BINARY_SHA='96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c'
SELECTED={k:k for k in ('time','lat','lon','height','roll','pitch','yaw')}


def now():return datetime.now(timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def no_symlink(path):
    path=Path(path)
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('symlink refused: '+str(path))
    return path
def resolve(value,roots):
    for alias,root in roots.items():
        if value==alias:return no_symlink(Path(root))
        if value.startswith(alias+'/'):
            suffix=value[len(alias)+1:]
            if '..' in Path(suffix).parts:raise ValueError('parent traversal refused')
            return no_symlink(Path(root)/suffix)
    raise ValueError('registered alias required: '+value)
def portable(value,roots):
    if isinstance(value,dict):return {k:portable(v,roots) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [portable(v,roots) for v in value]
    if isinstance(value,Path):value=str(value)
    if isinstance(value,str):
        for alias,root in sorted(roots.items(),key=lambda x:len(x[1]),reverse=True):value=value.replace(root,alias)
    if hasattr(value,'item'):return value.item()
    return value
def write_json(path,value,exclusive=True):
    with Path(path).open('x' if exclusive else 'w') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def write_csv(path,rows):
    if not rows:return
    with Path(path).open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def save_manifest(rows):
    tmp=HERE/'EVAL_MANIFEST.csv.tmp'
    write_csv(tmp,rows);os.replace(tmp,HERE/'EVAL_MANIFEST.csv')


def field_check(field,recorded,new,kind):
    result=dict(column=field,source_value=recorded,check_value=new,difference=None,tolerance=None,status='MISMATCH')
    if recorded is None or new is None:
        result['status']='MATCH_NULL' if recorded is None and new is None else 'MISSING_VALUE'
    elif kind=='exact':
        result['tolerance']=0
        result['status']='MATCH' if type(recorded)==type(new) and recorded==new else 'MISMATCH'
    else:
        a,b=float(recorded),float(new)
        if not math.isfinite(a) or not math.isfinite(b):result['status']='NONFINITE_NOT_COMPARABLE'
        else:
            tolerance=1e-9 if kind=='time' else 1e-10+1e-10*abs(a)
            result.update(difference=b-a,tolerance=tolerance,status='MATCH' if abs(b-a)<=tolerance else 'MISMATCH')
    return result


def gate_result(result):
    audit=result.get('audit') or {};capture=result.get('capture') or {};d12=capture.get('consistency') or {}
    checks={
      'audit_passed':audit.get('passed') is True,
      'exit_zero':audit.get('exit_code')==0,
      'one_reference_open':audit.get('trace_open_count')==1,
      'one_raw_reference_only':audit.get('raw_open_count')==1,
      'instrumented_child_role':audit.get('instrumented') is True and audit.get('trace_read_role')=='archived_evaluator_child_only',
      'no_bag_fpl':audit.get('bag_open_count')==0 and audit.get('fpl_open_count')==0,
      'write_scope':audit.get('write_scope',{}).get('pass') is True,
      'same_handle_hash':capture.get('trace_handle_hash_count')==1 and capture.get('trace_sha256')==TRACE_SHA,
      'capture_evaluator_identity':capture.get('evaluator_sha256')==EVALUATOR_SHA,
      'selected_columns':capture.get('selected_columns')==SELECTED,
      'fixed_window':capture.get('window')==list(WINDOW),
      'D12_passed':d12.get('passed') is True,
      'D12_policy':d12.get('policy')==POLICY,
      'D12_fixed_thresholds':d12.get('position_threshold_m')==.01 and d12.get('yaw_threshold_deg')==.01,
      'D12_no_offset':d12.get('time_offset_applied')==0,
      'D12_observation_only':d12.get('observation_only') is True,
      'resources_available':(result.get('process_resources') or audit.get('process_resources') or {}).get('status')=='AVAILABLE',
    }
    return checks


def actual_child_count(path,evaluator):
    if not path.exists():return 'UNKNOWN'
    count=0
    for line in path.open(errors='replace'):
        match=re.search(r'execve\("([^"\n]+)"',line)
        if match and Path(match.group(1)).name.startswith('python') and '"'+str(evaluator)+'"' in line and re.search(r'= 0\s*$',line):count+=1
    return count


def verify_committed(commit,variant):
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('full preparation commit required')
    paths=[Path(__file__),HERE/'FROZEN_PINS.json',HERE/'BASELINE_EXPECTATIONS.json',HERE.parent/'CANDIDATE_QUEUE.csv',HERE.parent/'V3_DEFINITION_DECISIONS.md']
    if variant!='BASELINE':paths.append(HERE.parent/'candidates'/variant/'READY.json')
    for path in paths:
        rel=str(path.relative_to(CODE))
        done=subprocess.run(['git','show',commit+':'+rel],cwd=CODE,capture_output=True)
        if done.returncode or done.stdout!=path.read_bytes():raise ValueError('preparation commit does not bind current file: '+rel)


def native_gate(native,item,variant,ready=None,ready_sha256=None):
    name='REPLAY_RECEIPT.json' if variant=='BASELINE' else 'CANDIDATE_RECEIPT.json'
    receipt=json.loads(no_symlink(native/name).read_text())
    expected='COMPLETED_BYTE_IDENTICAL' if variant=='BASELINE' else 'COMPLETED'
    if receipt.get('status')!=expected or receipt.get('exit_code')!=0 or receipt.get('access_passed') is not True or str(receipt.get('native_exec_count'))!='1':
        raise ValueError('native terminal/access gate not closed: '+str(receipt.get('status')))
    if receipt.get('config_sha256')!=item['original_config_sha256']:raise ValueError('native original config pin mismatch')
    if variant!='BASELINE' and (receipt.get('candidate_id')!=variant or receipt.get('baseline_run_id')!=item['baseline_run_id']):
        raise ValueError('candidate native identity mismatch')
    if variant=='BASELINE':
        if receipt.get('binary_sha256')!=BASELINE_BINARY_SHA:raise ValueError('baseline frozen binary identity mismatch')
    else:
        if not isinstance(ready,dict) or ready.get('candidate_id')!=variant or ready.get('native_tests_passed') is not True:
            raise ValueError('candidate committed READY/native-test gate not closed')
        if receipt.get('binary_sha256')!=ready.get('binary_sha256') or not re.fullmatch('[0-9a-f]{64}',str(ready.get('binary_sha256'))):
            raise ValueError('candidate binary pin differs from committed READY')
        if not ready_sha256 or receipt.get('ready_sha256')!=ready_sha256:raise ValueError('candidate native READY receipt pin mismatch')
        role_checks=receipt.get('data_role_manifest_check')
        if not isinstance(role_checks,dict) or len(role_checks)!=99 or not all(isinstance(v,dict) and v.get('present') is True and v.get('same') is True for v in role_checks.values()):
            raise ValueError('candidate 99-field fixed data-role manifest gate not closed')
    key='output_comparisons' if variant=='BASELINE' else 'output_hashes'
    pin_key='replay_sha256' if variant=='BASELINE' else 'candidate_sha256'
    pins={r['filename']:r[pin_key] for r in receipt[key]}
    return receipt,pins


def validate_manifest(queue,manifest,slot_id):
    by_run={r['baseline_run_id']:r for r in queue}
    expected={'BASELINE__'+rid:('BASELINE',item) for rid,item in by_run.items()}
    expected.update({r['candidate_id']+'__'+r['baseline_run_id']:(r['candidate_id'],r) for r in queue})
    if len(queue)!=10 or len(by_run)!=7 or len(expected)!=17 or len(manifest)!=17 or {r['slot_id'] for r in manifest}!=set(expected):
        raise ValueError('manifest is not the complete unique 7 baseline / 10 candidate slot set')
    for row in manifest:
        variant,item=expected[row['slot_id']]
        wanted={'candidate_id':variant,'run_id':item['baseline_run_id'],'case_id':item['case_id'],'group':item['group'],
            'method_id':item['method_id'],'data_mode':item['data_mode'],'synthetic_data_used':item['synthetic_data_used'],
            'semisynthetic_data_used':item['semisynthetic_data_used'],
            'output_root':'<VALIDATION_ROOT>/evaluations/'+variant+'/'+item['baseline_run_id']}
        if any(str(row.get(k))!=str(v) for k,v in wanted.items()):raise ValueError('manifest identity changed: '+row['slot_id'])
    chosen=next(r for r in manifest if r['slot_id']==slot_id)
    if chosen.get('status')!='PLANNED_NOT_INVOKED' or str(chosen.get('evaluator_invocation_attempts'))!='0' or str(chosen.get('evaluator_child_execs'))!='0':
        raise ValueError('slot has prior status/attempt/child evidence; no retry')
    return chosen


def numeric_diagnostics(np,nav,std):
    rows=[]
    for name,array in [('native_NAV',nav),('native_STD_untransported',std)]:
        for j in range(array.shape[1]):
            values=array[:,j];finite=np.isfinite(values)
            rows.append(dict(table=name,column_zero_based=j,count=len(values),finite_count=int(finite.sum()),nonfinite_count=int((~finite).sum()),
                first_value=float(values[0]) if finite[0] else None,last_value=float(values[-1]) if finite[-1] else None,
                minimum=float(values.min()) if finite.all() else None,maximum=float(values.max()) if finite.all() else None,
                role='NAV own velocity; no velocity truth/RMSE' if name=='native_NAV' and j in (5,6,7) else 'native state/support diagnostic'))
    return rows


def window_views(metrics,errors,nav,identity,group):
    if group not in {'A1','A2'}:return []
    views=[]
    for label,lo,hi,closed in [('before',66.,196.2,False),('fault',196.2,216.2,False),('after',216.2,340.,True)]:
        mask=(errors.time>=lo)&((errors.time<=hi) if closed else (errors.time<hi))
        nav_mask=(nav[:,1]>=lo)&((nav[:,1]<=hi) if closed else (nav[:,1]<hi))
        row=dict(identity,window=label,window_start=lo,window_end=hi,end_inclusive=closed,new_validation_calculation=True,reference_count_scope='UNKNOWN_FOR_THIS_SEGMENT; no extra trace read')
        if mask.any():row=metrics(errors.loc[mask],nav[nav_mask],row,(lo,hi),None)
        else:row.update(evaluation_status='EMPTY_SUPPORT',matched_epoch_count=0)
        views.append(row)
    return views


def run_one(args):
    roots=json.loads((CODE/'configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json').read_text())['aliases']
    verify_committed(args.preparation_commit,args.candidate_id)
    queue=list(csv.DictReader((HERE.parent/'CANDIDATE_QUEUE.csv').open()))
    chosen=[r for r in queue if r['baseline_run_id']==args.run_id and (args.candidate_id=='BASELINE' or r['candidate_id']==args.candidate_id)]
    if not chosen:raise ValueError('identity is not in frozen 7 baseline / 10 candidate queue')
    item=chosen[0];slot_id=args.candidate_id+'__'+args.run_id
    root=resolve('<VALIDATION_ROOT>/evaluations',roots);root.mkdir(exist_ok=True)
    lock=no_symlink(root/'.single_evaluator.lock')
    with lock.open('a') as lockfile:
        fcntl.flock(lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest=list(csv.DictReader((HERE/'EVAL_MANIFEST.csv').open()))
        entry=validate_manifest(queue,manifest,slot_id)
        out=no_symlink(root/args.candidate_id/args.run_id)
        shared=no_symlink(HERE/'results'/args.candidate_id/args.run_id)
        if shared.exists():raise ValueError('shared slot already exists; no retry')
        out.mkdir(parents=True,exist_ok=False)
        shared.mkdir(parents=True,exist_ok=False)
        receipt=dict(slot_id=slot_id,candidate_id=args.candidate_id,run_id=args.run_id,case_id=item['case_id'],method_id=item['method_id'],
            status='STARTED',started_utc=now(),preparation_commit=args.preparation_commit,evaluator_invocation_attempts=0,evaluator_child_execs=0,
            reference_child_opens=0,parent_reference_payload_reads=0,native_calls=0,retries=0,
            output_root=portable(out,roots),data_mode=item['data_mode'],synthetic_data_used=item['synthetic_data_used']=='True',semisynthetic_data_used=item['semisynthetic_data_used']=='True')
        write_json(out/'STARTED.json',receipt);entry['status']='STARTED';save_manifest(manifest)
        evaluator=resolve('<FROZEN_EVALUATOR>',roots);frozen=out/'FROZEN_EVALUATOR'
        try:
            for pin in json.loads((HERE/'FROZEN_PINS.json').read_text())['files']:
                if sha(resolve(pin['path'],roots))!=pin['sha256']:raise ValueError('frozen small source/evaluator hash mismatch: '+pin['path'])
            trace=resolve('<V3_REFERENCE>',roots)
            trace_stat=trace.stat()  # no trace body open/hash in the parent
            receipt['reference_stat_bytes']=trace_stat.st_size
            native=resolve(item['baseline_outputs'] if args.candidate_id=='BASELINE' else item['candidate_outputs'],roots)
            ready_path=no_symlink(HERE.parent/'candidates'/args.candidate_id/'READY.json') if args.candidate_id!='BASELINE' else None
            ready=json.loads(ready_path.read_text()) if ready_path else None
            native_receipt,native_pins=native_gate(native,item,args.candidate_id,ready,sha(ready_path) if ready_path else None)
            receipt['native_receipt_path']=portable(native/('REPLAY_RECEIPT.json' if args.candidate_id=='BASELINE' else 'CANDIDATE_RECEIPT.json'),roots)
            nav_path=no_symlink(native/'KF_GINS_Navresult.nav');std_path=no_symlink(native/'KF_GINS_STD.txt')
            nh,sh=sha(nav_path),sha(std_path)
            if nh!=native_pins[nav_path.name] or sh!=native_pins[std_path.name]:raise ValueError('native NAV/STD receipt pin mismatch')
            expected=json.loads((HERE/'BASELINE_EXPECTATIONS.json').read_text())[args.run_id]
            if sha(resolve(expected['source_path'],roots))!=expected['source_json_sha256'] or sha(resolve(expected['capture_source_path'],roots))!=expected['capture_source_sha256']:
                raise ValueError('old result/capture metadata no longer matches prepared source pin')
            if args.candidate_id=='BASELINE' and (nh!=expected['native_nav_sha256'] or sh!=expected['std_sha256']):raise ValueError('historical native NAV/STD identity mismatch')
            sys.dont_write_bytecode=True
            for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
            sys.path.insert(0,str(CODE/'src'))
            import numpy as np
            from legsa_gins.paper_rebuild.protocol_v3.evaluation_process import evaluate
            from legsa_gins.paper_rebuild.clean5_parity.evaluation import transform_nav,write_transformed_nav
            from legsa_gins.paper_rebuild.canonical541.offline_eval_aggregate import _read_numeric_table,_read_error_series
            from legsa_gins.paper_rebuild.clean5_parity_p04.evaluation import metrics
            original=_read_numeric_table(nav_path).to_numpy(float)
            std=_read_numeric_table(std_path).to_numpy(float)
            if len(original)==0 or len(std)==0:raise ValueError('empty NAV/STD')
            write_csv(shared/'NATIVE_NUMERIC_DIAGNOSTICS.csv',numeric_diagnostics(np,original,std))
            if not np.isfinite(original).all() or not np.isfinite(std).all():raise ValueError('nonfinite native NAV/STD; no row deletion')
            if np.any(np.diff(original[:,1])<=0) or np.any(original[:,1]<66) or np.any(original[:,1]>340):raise ValueError('native NAV time support invalid')
            converted=out/'EVAL_NAV_V3.nav'
            write_transformed_nav(nav_path,converted,transform_nav(original,BASELINE_LENGTH))
            eh=sha(converted)
            receipt.update(native_nav_sha256=nh,std_sha256=sh,evaluator_nav_sha256=eh,v3_lever_frd_m=[.03,-.148095745932992,-.30],uncertainty_status='UNTRANSPORTED_STD_DIAGNOSTIC_ONLY')
            if args.candidate_id=='BASELINE' and eh!=expected['evaluator_nav_sha256']:raise ValueError('baseline converted NAV hash mismatch; evaluator not called')
            receipt['evaluator_invocation_attempts']=1;receipt['evaluator_child_execs']='UNKNOWN'
            write_json(out/'BEFORE_EVALUATOR_CALL.json',receipt)
            entry.update(evaluator_invocation_attempts=1,evaluator_child_execs='UNKNOWN');save_manifest(manifest)
            result=evaluate(evaluator=evaluator,trace=trace,nav=converted,std=std_path,outdir=frozen,base_time=BASE_TIME,window=WINDOW,
                trace_sha256=TRACE_SHA,code_root=CODE,raw_root=resolve('<RAW_ROOT>',roots),clean_root=resolve('<CLEAN_ROOT>',roots),
                instrument=True,consistency_policy=POLICY,measure_resources=True,export_matched_truth=False)
            receipt['reference_child_opens']=result['audit']['trace_open_count']
            gates=gate_result(result);write_json(shared/'EVALUATOR_GATES.json',gates)
            if not all(gates.values()):raise ValueError('frozen evaluator gate failed: '+','.join(k for k,v in gates.items() if not v))
            errors=_read_error_series(frozen)
            if not len(errors) or not np.isfinite(errors.to_numpy(float)).all() or np.any(np.diff(errors.time.to_numpy(float))<=0):raise ValueError('nonfinite/unordered evaluated errors')
            if int(result['capture']['consistency']['matched_epoch_count'])!=len(errors):raise ValueError('capture/error matched count mismatch')
            identity=dict(run_id=args.run_id,candidate_id=args.candidate_id,case_id=item['case_id'],method_id=item['method_id'],sequence_id='BY2',evaluator_contract='evaluator_contract_v3',
                data_mode=item['data_mode'],synthetic_data_used=receipt['synthetic_data_used'],semisynthetic_data_used=receipt['semisynthetic_data_used'],
                metric_source_commit='7d43b9af26120ed5dde21f53e515386361072ba6',new_validation_calculation=True)
            row=metrics(errors,original,identity,WINDOW,result['capture']['reference_epoch_count'])
            row.update(native_nav_sha256=nh,evaluator_nav_sha256=eh,std_sha256=sh,reference_cleaned_epoch_count=result['capture']['consistency']['reference_cleaned_epoch_count'],
                source_path=portable(frozen/('error_series.csv' if (frozen/'error_series.csv').is_file() else 'error_series.csv.gz'),roots),uncertainty_status='UNTRANSPORTED_STD_DIAGNOSTIC_ONLY')
            write_json(out/'FULL_METRICS.json',row);write_json(shared/'FULL_METRICS.json',row)
            windows=window_views(metrics,errors,original,identity,item['group'])
            if windows:write_json(shared/'FIXED_WINDOW_METRICS.json',windows)
            if args.candidate_id=='BASELINE':
                checks=[]
                for field,spec in expected['columns'].items():
                    check=field_check(field,spec['source_value'],row.get(field),spec['comparison_kind'])
                    check.update(source_path=expected['source_path'],row_key=spec['row_key']);checks.append(check)
                check=field_check('reference_cleaned_epoch_count',expected['reference_cleaned_epoch_count'],row['reference_cleaned_epoch_count'],'exact')
                check.update(source_path=expected['capture_source_path'],row_key='#/consistency/reference_cleaned_epoch_count');checks.append(check)
                write_csv(shared/'BASELINE_FIELD_CHECKS.csv',checks)
                passed=all(r['status'] in {'MATCH','MATCH_NULL'} for r in checks)
                receipt['baseline_gate']='PASS' if passed else 'FAILED_OLD_NEW_COMPARISON'
                receipt['status']='COMPLETED_BASELINE_GATE_PASS' if passed else 'BASELINE_COMPARISON_FAILED_RETAINED'
            else:
                base_out=root/'BASELINE'/args.run_id
                base_receipt=json.loads((base_out/'EVALUATION_RECEIPT.json').read_text()) if (base_out/'EVALUATION_RECEIPT.json').exists() else {}
                receipt['baseline_gate']=base_receipt.get('baseline_gate','NOT_AVAILABLE')
                receipt['status']='COMPLETED_CANDIDATE_BASELINE_NOT_CLOSED'
                if receipt['baseline_gate']=='PASS' and base_receipt.get('status')=='COMPLETED_BASELINE_GATE_PASS' and base_receipt.get('evaluator_child_execs')==1:
                    base_errors=_read_error_series(base_out/'FROZEN_EVALUATOR')
                    bt=base_errors.time.to_numpy(float);ct=errors.time.to_numpy(float)
                    common=np.intersect1d(bt,ct,assume_unique=True)
                    same=np.array_equal(bt,ct)
                    support=dict(pairing='EXACT_TIMESTAMP_NO_INTERPOLATION',baseline_count=len(bt),candidate_count=len(ct),common_count=len(common),identical_support=same)
                    write_json(shared/'COMMON_SUPPORT.json',support)
                    base_row=json.loads((base_out/'FULL_METRICS.json').read_text())
                    differences=[]
                    for field in expected['columns']:
                        a,b=base_row.get(field),row.get(field)
                        number=isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool)
                        differences.append(dict(column=field,baseline_value=a,candidate_value=b,difference=b-a if same and number else None,
                            comparison_status='SAME_SUPPORT' if same else 'DIFFERENT_SUPPORT_NO_DIRECT_DELTA',
                            baseline_source=portable(base_out/'FULL_METRICS.json',roots),candidate_source=portable(out/'FULL_METRICS.json',roots)))
                    write_csv(shared/'CANDIDATE_BASELINE_FIELDS.csv',differences)
                    receipt['status']='COMPLETED_CANDIDATE_COMPARABLE' if same else 'COMPLETED_DIFFERENT_SUPPORT_REQUIRES_COMMON_METRICS'
        except BaseException as exc:
            receipt.update(status='FAILED_RETAINED_NO_RETRY',failure_type=type(exc).__name__,reason=portable(str(exc),roots))
        finally:
            if receipt['evaluator_invocation_attempts']:
                try:receipt['evaluator_child_execs']=actual_child_count(frozen/'EVALUATOR_OPENAT.strace',evaluator)
                except (OSError,ValueError) as exc:
                    receipt['evaluator_child_execs']='UNKNOWN';receipt['exec_accounting_error']=portable(str(exc),roots)
                try:
                    audit_file=frozen/'EVALUATOR_STRACE_AUDIT.json'
                    receipt['reference_child_opens']=json.loads(audit_file.read_text()).get('trace_open_count','UNKNOWN') if audit_file.exists() else 'UNKNOWN'
                except (OSError,ValueError) as exc:
                    receipt['reference_child_opens']='UNKNOWN';receipt['reference_accounting_error']=portable(str(exc),roots)
            receipt['finished_utc']=now()
            if receipt['status'].startswith('COMPLETED') and receipt['evaluator_child_execs']!=1:
                receipt.update(status='FAILED_EXEC_ACCOUNTING_RETAINED',reason='evaluator actual child execution count is not one')
                if args.candidate_id=='BASELINE':receipt['baseline_gate']='FAILED_EXEC_ACCOUNTING'
            for key in ['status','evaluator_invocation_attempts','evaluator_child_execs','reference_child_opens','baseline_gate','reason']:
                entry[key]=receipt.get(key,entry.get(key,''))
            write_json(out/'EVALUATION_RECEIPT.json',portable(receipt,roots))
            write_json(shared/'EVALUATION_RECEIPT.json',portable(receipt,roots));save_manifest(manifest)
        print(json.dumps(portable(receipt,roots)))
        return 0 if receipt['status'].startswith('COMPLETED') else 1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate-id',choices=['BASELINE','N12_ONLY','N16_ONLY','N09_RP_ONLY'],required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--preparation-commit',required=True)
    a=p.parse_args();return run_one(a)


if __name__=='__main__':raise SystemExit(main())
