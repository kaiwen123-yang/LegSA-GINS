"""Protocol v3 scalar native execution and frozen, child-only offline evaluation."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import threading
import time

import numpy as np

from ..hext import t5a_runtime as frozen
from ..hext.t5a_config_fidelity import compare_effective_echo, decode_echo
from ..hext.t5bc_runtime import classify_heading_failure
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .registry import expected_echo
from .evaluation_process import evaluate

BINARY_SHA256=frozen.BINARY_SHA256
EVALUATOR_SHA256=frozen.EVALUATOR_SHA256
write_json=frozen._write
_PIN_LOCK=threading.Lock()
_CHECKED={}


def verify_pin(pin, *, cached=False):
    path=frozen._safe(pin['path'])
    key=(str(path),pin['sha256'])
    with _PIN_LOCK:
        stat=path.stat(); identity=(stat.st_size,stat.st_mtime_ns,stat.st_ino)
        if not cached or _CHECKED.get(key)!=identity:
            frozen._pinned(path,pin['sha256'])
            _CHECKED[key]=identity
    return path


def reserve_slot(path, run_id, allowed_run_ids, *, kind):
    """A reservation is consumed even when launch or collection fails."""
    allowed=set(allowed_run_ids)
    if run_id not in allowed or kind not in ('native','evaluator'):
        raise PermissionError('HARD_STOP_V3_UNREGISTERED_RESERVATION')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+',encoding='utf-8') as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        stream.seek(0);rows=[json.loads(line) for line in stream if line.strip()]
        if (any(r['kind']!=kind or r['run_id'] not in allowed for r in rows)
                or len({r['run_id'] for r in rows})!=len(rows)):
            raise RuntimeError('HARD_STOP_V3_RESERVATION_SCOPE')
        if any(r['run_id']==run_id for r in rows):
            raise RuntimeError('HARD_STOP_V3_ALREADY_RESERVED_NO_RETRY')
        if len(rows)>=len(allowed):raise RuntimeError('HARD_STOP_V3_BUDGET')
        row={'run_id':run_id,'kind':kind,'ordinal':len(rows)+1,'budget':len(allowed),
             'status':'RESERVED_BEFORE_LAUNCH','retry_count':0}
        stream.write(json.dumps(row)+'\n');stream.flush();os.fsync(stream.fileno())
    return row


def prepare_config(spec, provider, output):
    source=verify_pin(spec['frozen_config'],cached=True)
    for pin in spec['frozen_providers'].values():verify_pin(pin,cached=True)
    verify_pin(provider,cached=True)
    if provider.get('byte_gate',{}).get('passed') is not True:
        raise RuntimeError('HARD_STOP_V3_PROVIDER_GATE_REQUIRED')
    cloned, gate=frozen.clone_runtime_config(source.read_bytes(),
        expected_sha256=spec['frozen_config']['sha256'],gnsspath=provider['path'])
    echo,witness=expected_echo(spec)
    # Check completeness of all 211 expected static fields before launch.
    config=frozen._runtime_mapping(cloned)
    coverage=compare_effective_echo(echo,echo,expected_gnsspath=echo['actual_solver_input_paths']['gnss_position_receiver_velocity_dual_yaw'])
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    path=root/'V3_RUNTIME_CONFIG.yaml'
    if path.exists():
        if path.read_bytes()!=cloned:raise RuntimeError('HARD_STOP_V3_PREPARED_CONFIG_CHANGED')
    else:
        with path.open('xb') as stream:stream.write(cloned);stream.flush();os.fsync(stream.fileno())
    receipt={'run_id':spec['run_id'],'config':{'path':str(path),'sha256':hashlib.sha256(cloned).hexdigest()},
        'byte_gate':gate,'expected_echo_gate':coverage,'echo_witness':witness,
        'actual_native_echo_status':'PENDING_NATIVE_EXECUTION','prepared_gnss':provider}
    target=root/'CONFIG_ADMISSION.json'
    if target.exists():
        if json.loads(target.read_text())!=receipt:raise RuntimeError('HARD_STOP_V3_CONFIG_ADMISSION_CHANGED')
    else:write_json(target,receipt)
    return receipt


def seal_native(root,record,started):
    root=Path(root)
    record.update(runtime_seconds=time.monotonic()-started,
        trace_open_count=record.get('access_audit',{}).get('trace_open_count','UNAVAILABLE'))
    files={p.relative_to(root).as_posix():sha256_file(p) for p in sorted(root.rglob('*')) if p.is_file()}
    write_json(root/'OUTPUT_SEAL.json',{'status':'SEALED','files':files,'same_native_invocation':True})
    record['file_hashes']={**files,'OUTPUT_SEAL.json':sha256_file(root/'OUTPUT_SEAL.json')}
    for role,name in [('nav','KF_GINS_Navresult.nav'),('std','KF_GINS_STD.txt')]:
        if name in files:record.update({role+'_path':str(root/name),role+'_sha256':files[name]})
    write_json(root/'V3_NATIVE_SUMMARY.json',record)
    return record


def load_native(root):
    root=Path(root)
    record=json.loads((root/'V3_NATIVE_SUMMARY.json').read_text())
    archive=root/'ARCHIVE_RECEIPT.json'
    if archive.exists():
        receipt=json.loads(archive.read_text())
        for item in receipt['files'].values():verify_pin({'path':str(Path(receipt['archive_root'])/item['storage_relative_path']),'sha256':item['sha256']},cached=True)
        record=archived_native(record,receipt)
    else:
        for name,digest in record['file_hashes'].items():verify_pin({'path':str(root/name),'sha256':digest},cached=True)
    if record['status']=='HARD_STOP':raise RuntimeError('HARD_STOP_V3_PERSISTED_NATIVE_STOP')
    return record


def run_native(sequence, spec, admission, *, binary, output_root, scratch_root, code_freeze,
               ledger, allowed_run_ids, timeout_seconds=1800):
    root=Path(output_root)
    if root.exists():return load_native(root)
    verify_pin({'path':str(binary),'sha256':BINARY_SHA256},cached=True)
    for pin in spec['frozen_providers'].values():verify_pin(pin,cached=True)
    verify_pin(admission['prepared_gnss'],cached=True)
    config_bytes=verify_pin(admission['config'],cached=True).read_bytes()
    config=frozen._runtime_mapping(config_bytes)
    root.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    record={**frozen.FLAGS,**{k:spec.get(k) for k in ('run_id','method_id','configuration_id','case_id','case_family',
        'degradation_type_id','seed_index','effective_profile','case_meta','source_registry_row','sequence_id','dataset_id',
        'domain','data_mode','synthetic_data_used','semisynthetic_data_used','raw_source_hashes')},
        'protocol_id':'PROTOCOL_V3','code_commit':code_freeze,'config_hash':admission['config']['sha256'],
        'config_byte_gate':admission['byte_gate'],'echo_witness':admission['echo_witness'],
        'provider_hashes':{**{k:p['sha256'] for k,p in spec['frozen_providers'].items()},'gnsspath':admission['prepared_gnss']['sha256']},
        'native_config_flags_retained':{k:config.get(k) for k in frozen.FLAGS},
        'frozen_outputpath_retained':config['outputpath'],'output_root':str(root),
        'executable_sha256':BINARY_SHA256,'retry_count':0,'native_invocation_count':0}
    try:
        path=root/'V3_RUNTIME_CONFIG.yaml'
        with path.open('xb') as stream:stream.write(config_bytes);stream.flush();os.fsync(stream.fileno())
        write_json(root/'LAUNCH_RESERVATION.json',reserve_slot(ledger,spec['run_id'],allowed_run_ids,kind='native'))
        record['native_invocation_count']=1
        argv=frozen.native_argv(binary,path,root);log=root/'NATIVE_OPENAT.strace'
        command=['env','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1',
                 'strace','-f','-qq','-yy','-s','4096','-e','trace=openat,execve','-o',str(log),*argv]
        write_json(root/'RUN_STARTED.json',{**record,'native_argv':argv})
        result=run_process_group(command,cwd=sequence.code_root,timeout_seconds=timeout_seconds,
            timeout_message='V3 native timeout; no retry',launch_failure_message='V3 native launch failure; no retry')
        (root/'stdout.log').write_text(result.stdout);(root/'stderr.log').write_text(result.stderr)
        record['exit_code']=result.returncode
        record['access_audit']=frozen.audit_native_access(log,sequence,root,config,Path(binary),scratch_root)
        if record['access_audit']['passed'] is not True:raise RuntimeError('HARD_STOP_V3_NATIVE_ACCESS_AUDIT')
        manifest=root/'RUN_MANIFEST.json'
        if manifest.exists():
            native=decode_echo(manifest.read_bytes());expected,_=expected_echo(spec)
            record['effective_echo_gate']=compare_effective_echo(native,expected,expected_gnsspath=config['gnsspath'])
            record['native_manifest_sha256']=sha256_file(manifest)
            record['native_counters']={k:v for k,v in native.items() if any(t in k for t in ('count','accept','reject','touch'))}
        else:record['effective_echo_gate']={'status':'UNAVAILABLE_NOT_EMITTED','passed':None,'static_field_count':211}
        if result.returncode:
            failed_nav=root/'KF_GINS_Navresult.nav';failed_bound=None
            if failed_nav.is_file():
                try:failed_bound=frozen.bounded_lla_native(failed_nav,expected_sha256=sha256_file(failed_nav))
                except (ValueError,OSError):pass
            if failed_bound is not None and failed_bound['failure_classification']=='ALGORITHM_FAILURE_DIVERGED':
                record.update(status='ALGORITHM_FAILURE_DIVERGED',bounded_gate=failed_bound,
                    failure_classification='ALGORITHM_FAILURE_DIVERGED',std_nav_alignment='NOT_ADMITTED_ALGORITHM_FAILURE')
            else:
                classification=classify_heading_failure(root,config,variant='R5')
                reason='FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch'
                if result.stderr.strip() not in (reason,'legsa_v23_port_core_demo failed: '+reason):
                    classification['passed']=False
                if classification.get('passed') is not True:raise RuntimeError('HARD_STOP_V3_UNCLASSIFIABLE_NATIVE_FAILURE')
                record.update(status=classification['classification'],failure_classification=classification)
        else:
            if record['effective_echo_gate'].get('passed') is not True:raise RuntimeError('HARD_STOP_V3_SUCCESS_WITHOUT_211_ECHO')
            nav=root/'KF_GINS_Navresult.nav';std=root/'KF_GINS_STD.txt'
            gate=frozen.bounded_lla_native(nav,expected_sha256=sha256_file(nav));record['bounded_gate']=gate
            if gate['passed']:
                nr,_=frozen.read_native_numeric(nav,columns=11);sr,_=frozen.read_native_numeric(std)
                if (len(nr)!=len(sr) or sr.shape[1]<10 or not np.isfinite(sr).all()
                    or not np.array_equal(nr[:,1],sr[:,0]) or np.any(np.diff(nr[:,1])<=0)
                    or nr[0,1]<sequence.window[0] or nr[-1,1]>sequence.window[1]):
                    raise RuntimeError('HARD_STOP_V3_NATIVE_STD_NAV_SUPPORT')
            record.update(status='COMPLETED' if gate['passed'] else 'ALGORITHM_FAILURE_DIVERGED',
                          failure_classification=gate['failure_classification'])
        record['terminal_status']=record['status']
        record['evaluator_status']='PENDING' if record['status']=='COMPLETED' else 'NOT_RUN_ALGORITHM_FAILURE'
        if path.read_bytes()!=config_bytes:raise RuntimeError('HARD_STOP_V3_CONFIG_DRIFT')
        verify_pin(admission['prepared_gnss'],cached=True)
        return seal_native(root,record,started)
    except Exception as exc:
        record.update(status='HARD_STOP',terminal_status='HARD_STOP',error_type=type(exc).__name__,error=str(exc))
        write_json(root/'HARD_STOP.json',record)
        if not (root/'OUTPUT_SEAL.json').exists():seal_native(root,record,started)
        raise


def evaluate_native(sequence,evaluator,record,version,*,output_root,scratch_root,ledger,allowed_run_ids):
    """Same frozen transform/evaluator/metric code, with the v3 slot ledger."""
    root=Path(output_root)
    if root.exists():
        payload=json.loads((root/'EVALUATION_RESULT.json').read_text())
        archive=root/'ARCHIVE_RECEIPT.json'
        if archive.exists():
            receipt=json.loads(archive.read_text())
            for item in receipt['files'].values():verify_pin({'path':str(Path(receipt['archive_root'])/item['storage_relative_path']),'sha256':item['sha256']},cached=True)
            payload.update(archive_output_root=receipt['archive_root'],archive_receipt=str(Path(receipt['archive_root'])/'ARCHIVE_RECEIPT.json'),resolved_error_series_source=str(Path(receipt['archive_root'])/'FROZEN_EVALUATOR'))
        else:
            seal=json.loads((root/'OUTPUT_SEAL.json').read_text())
            for rel,digest in seal['files'].items():verify_pin({'path':str(root/rel),'sha256':digest},cached=True)
        return payload
    identity={k:record.get(k) for k in ('run_id','method_id','configuration_id','case_id','case_family','degradation_type_id',
        'seed_index','effective_profile','sequence_id','dataset_id','domain','data_mode','synthetic_data_used',
        'semisynthetic_data_used','code_commit','provider_hashes','raw_source_hashes','config_hash')}
    identity.update(evaluator_contract='evaluator_contract_'+version,trace_used_online=False,retry_count=0)
    root.mkdir(parents=True,exist_ok=False)
    if record['status']!='COMPLETED':
        payload={'row':{**identity,'status':'NOT_RUN_ALGORITHM_FAILURE','evaluation_status':'NOT_RUN_ALGORITHM_FAILURE',
            'failure_classification':record['status'],'metrics_admitted':False,'evaluation_invoked':False},'audit':{},'transform':{}}
    else:
        nav=verify_pin({'path':record['nav_path'],'sha256':record['nav_sha256']},cached=True)
        std=verify_pin({'path':record['std_path'],'sha256':record['std_sha256']},cached=True)
        verify_pin({'path':str(evaluator),'sha256':EVALUATOR_SHA256},cached=True)
        bounded=record['bounded_gate']
        if bounded.get('passed') is not True or bounded['source_nav_sha256']!=record['nav_sha256']:
            raise RuntimeError('HARD_STOP_V3_D12_NATIVE_BOUND')
        original=frozen.canonical._read_numeric_table(nav).to_numpy(float);window=frozen._support(original,sequence.window)
        actual=nav
        transform={'evaluator_contract':'evaluator_contract_'+version,'input_sha256':record['nav_sha256'],
            'STD':'SAME_V3_NATIVE_STD_UNMODIFIED','std_sha256':record['std_sha256'],'std_transformed':False,
            'fit_used':False,'further_correction_used':False}
        if version=='v3':
            actual=root/'EVAL_NAV_V3.nav'
            frozen.write_transformed_nav(nav,actual,frozen.transform_nav(original,sequence.baseline_median_m))
            transform.update(changed_columns_zero_based=[2,3,4],baseline_median_m=sequence.baseline_median_m,
                lever_frd_m=[.03,.03-sequence.baseline_median_m/2,-.30],uncertainty_status='UNTRANSPORTED_STD_DIAGNOSTIC_ONLY')
        elif version=='v2':transform.update(changed_columns_zero_based=[],uncertainty_status='DIAGONAL_ONLY_NOT_FULL_NEES')
        else:raise ValueError('Unregistered evaluator version')
        transform['output_sha256']=sha256_file(actual)
        rid=record['run_id']+'__'+version
        write_json(root/'LAUNCH_RESERVATION.json',reserve_slot(ledger,rid,allowed_run_ids,kind='evaluator'))
        try:
            result=evaluate(evaluator=evaluator,trace=sequence.trace,nav=actual,std=std,
                outdir=root/'FROZEN_EVALUATOR',base_time=sequence.base_time,window=window,
                trace_sha256=sequence.trace_sha256,code_root=sequence.code_root,raw_root=sequence.raw_root,
                clean_root=sequence.clean_root,instrument=True,consistency_policy=frozen.POLICY,measure_resources=True,
                export_matched_truth=(record['sequence_id']=='BY2' and record['case_id']=='C00_clean_normal' and record['method_id']=='F04' and version=='v3'))
            audit,capture=frozen._capture(result,sequence)
            identity.update(evaluator_sha256=EVALUATOR_SHA256,source_nav_sha256=record['nav_sha256'],
                native_nav_sha256=record['nav_sha256'],evaluator_nav_sha256=transform['output_sha256'],
                std_sha256=record['std_sha256'],trace_sha256=sequence.trace_sha256,base_time=sequence.base_time,
                evaluation_invoked=True,uncertainty_status=transform['uncertainty_status'])
            if not capture['consistency']['passed']:
                row={**identity,'status':'UNAVAILABLE_EVALUATION_FAILED','evaluation_status':'UNAVAILABLE_EVALUATION_FAILED',
                     'failure_classification':'UNAVAILABLE_EVALUATION_FAILED','metrics_admitted':False,
                     'reason':'D12 frozen evaluator consistency failed; no retry'};bias={}
            else:
                errors=frozen.canonical._read_error_series(Path(result['outdir']))
                times=np.asarray(errors['time'],float)
                if not len(times) or not np.isfinite(times).all() or np.any(np.diff(times)<=0) or np.any((times<window[0])|(times>window[1])):
                    raise RuntimeError('HARD_STOP_V3_EVALUATOR_SUPPORT')
                row=frozen.window_metrics(errors,original,identity,window,capture.get('reference_epoch_count'))
                row.update(status='COMPLETED',evaluation_status='COMPLETED',failure_classification='NONE',metrics_admitted=True)
                bias={**identity,**frozen.body_frame_bias(errors,original),'status':'AVAILABLE'}
            row.update(evaluation_runtime_seconds=result['runtime_seconds'],error_series_source=result['outdir'],
                sequence_window_start_s=window[0],sequence_window_end_s=window[1],native_output_root=record['output_root'])
            payload={'row':row,'audit':audit,'transform':transform,'body_frame_bias':bias}
        except Exception as exc:
            write_json(root/'HARD_STOP.json',{'status':'HARD_STOP','run_id':rid,'error':str(exc),'retry_count':0})
            raise
        finally:
            verify_pin({'path':str(evaluator),'sha256':EVALUATOR_SHA256},cached=True)
            verify_pin({'path':str(nav),'sha256':record['nav_sha256']},cached=True)
            verify_pin({'path':str(std),'sha256':record['std_sha256']},cached=True)
            verify_pin({'path':str(actual),'sha256':transform['output_sha256']},cached=True)
    write_json(root/'EVALUATION_RESULT.json',payload)
    write_json(root/'OUTPUT_SEAL.json',{'status':'SEALED','files':{p.relative_to(root).as_posix():sha256_file(p)
               for p in root.rglob('*') if p.is_file()}})
    return payload


def archive_directory(source, destination, *, scratch_root):
    """Lossless copy, SHA/size/CRC verification, then exact-file scratch release.

    The source manifest is captured before any deletion. Only files created in
    this task's native/evaluator slot can be removed; directories remain.
    """
    import gzip
    import shutil
    source=frozen._safe(source);destination=frozen._safe(destination);scratch=frozen._safe(scratch_root)
    if not any(parent in source.parents for parent in (scratch/'03_NATIVE',scratch/'04_EVALUATION')):
        raise PermissionError('HARD_STOP_V3_ARCHIVE_SOURCE_SCOPE')
    if (source/'ARCHIVE_RECEIPT.json').exists():
        receipt=json.loads((source/'ARCHIVE_RECEIPT.json').read_text())
        if receipt['archive_root']!=str(destination):raise RuntimeError('HARD_STOP_V3_ARCHIVE_TARGET_CHANGED')
        for item in receipt['files'].values():
            verify_pin({'path':str(destination/item['storage_relative_path']),'sha256':item['sha256']},cached=True)
        return receipt
    if destination.exists():raise FileExistsError('Incomplete archive retained; no blind overwrite')
    inventory={}
    for path in sorted(source.rglob('*')):
        frozen._safe(path)
        if path.is_file():inventory[path.relative_to(source).as_posix()]={'source_sha256':sha256_file(path),'source_size_bytes':path.stat().st_size}
    destination.mkdir(parents=True,exist_ok=False)
    files={}
    for relative,item in inventory.items():
        path=source/relative
        compress=path.suffix not in ('.json','.yaml','.yml','.gz','.png','.pdf','.svg')
        stored=(relative+('.lossless.gz' if relative+'.gz' in inventory else '.gz')) if compress else relative
        target=destination/stored;target.parent.mkdir(parents=True,exist_ok=True)
        if compress:
            with path.open('rb') as reader,target.open('xb') as output:
                with gzip.GzipFile(filename='',mode='wb',fileobj=output,compresslevel=6,mtime=0) as writer:
                    shutil.copyfileobj(reader,writer,8*1024*1024)
                output.flush();os.fsync(output.fileno())
        else:
            with path.open('rb') as reader,target.open('xb') as writer:
                shutil.copyfileobj(reader,writer,8*1024*1024);writer.flush();os.fsync(writer.fileno())
        digest=hashlib.sha256();size=0
        opener=gzip.open if compress else open
        with opener(target,'rb') as stream:
            while chunk:=stream.read(8*1024*1024):digest.update(chunk);size+=len(chunk)
        if digest.hexdigest()!=item['source_sha256'] or size!=item['source_size_bytes']:
            raise RuntimeError('HARD_STOP_V3_ARCHIVE_UNCOMPRESSED_IDENTITY')
        files[relative]={**item,'storage_relative_path':stored,'sha256':sha256_file(target),
                         'size_bytes':target.stat().st_size,'compression':'gzip' if compress else 'identity'}
    receipt={'status':'ARCHIVE_VERIFIED','source_root':str(source),'archive_root':str(destination),'files':files}
    write_json(destination/'ARCHIVE_RECEIPT.json',receipt)
    write_json(source/'ARCHIVE_RECEIPT.json',receipt)
    # Only the exact verified runtime payload list is releasable. Small metadata
    # remains available so resume can resolve original reservations and seals.
    ledger=source/'SCRATCH_RELEASE.jsonl'
    with ledger.open('x') as stream:
        for relative,item in files.items():
            path=frozen._safe(source/relative)
            if path.suffix in ('.json','.yaml','.yml'):continue
            if source not in path.parents or sha256_file(path)!=item['source_sha256']:
                raise RuntimeError('HARD_STOP_V3_SCRATCH_RELEASE_IDENTITY')
            path.unlink()
            stream.write(json.dumps({'relative_path':relative,'sha256':item['source_sha256'],'status':'DELETED_VERIFIED_SCRATCH_COPY'})+'\n')
            stream.flush();os.fsync(stream.fileno())
    return receipt


def archived_native(record,receipt):
    result={**record,'archive_output_root':receipt['archive_root'],
        'archive_receipt':str(Path(receipt['archive_root'])/'ARCHIVE_RECEIPT.json')}
    for role,name in [('nav','KF_GINS_Navresult.nav'),('std','KF_GINS_STD.txt')]:
        if name in receipt['files']:
            result['resolved_'+role+'_path']=str(Path(receipt['archive_root'])/receipt['files'][name]['storage_relative_path'])
    return result
