"""Single default BY2 pair, traced and compared; never retries a native solve."""
from __future__ import annotations
import errno
from itertools import zip_longest
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from .sequence_paths import load_sequence_paths,alias_path
from .probe import write_json
from ..horizontal_literature.ext05_provider import sha256_file


METHODS={'LC01':'EXT05A_PAVLASEK_TWO_RECEIVER_IEKF','EXT05C':'EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF'}


def first_difference(actual:Path,expected:Path):
    with actual.open('rb') as a, expected.open('rb') as b:
        for number,(left,right) in enumerate(zip_longest(a,b),1):
            if left != right:
                def values(line):
                    if line is None:return None
                    tokens=line.decode('utf-8',errors='replace').strip().split()
                    try:return [float(x) for x in tokens]
                    except ValueError:return tokens
                return {'line_1based':number,'actual_line':None if left is None else left.decode('utf-8',errors='replace'),
                        'expected_line':None if right is None else right.decode('utf-8',errors='replace'),
                        'actual_values':values(left),'expected_values':values(right)}
    return None


def archive(source:Path,destination:Path,seq):
    """At most three ENOMEM/EIO copy retries, with a checkpoint per file."""
    destination.mkdir(parents=True,exist_ok=False);ledger=[]
    for item in sorted(source.rglob('*')):
        if item.is_symlink():raise ValueError('No symlink archive entries')
        if not item.is_file():continue
        relative=item.relative_to(source);target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        expected=sha256_file(item);attempt=0
        while True:
            try:
                # New output only; failed partial copies in this new archive may
                # be overwritten by the specifically authorized I/O retry.
                with item.open('rb') as src,target.open('wb' if attempt else 'xb') as dst:
                    shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
                if sha256_file(target)!=expected:raise IOError('Archive SHA-256 mismatch')
                break
            except OSError as exc:
                if exc.errno not in (errno.ENOMEM,errno.EIO) or attempt>=3:raise
                attempt+=1;time.sleep(min(attempt,3))
        ledger.append({'batch':'H_EXT_01_BY2_IDENTITY','path':relative.as_posix(),'size_bytes':item.stat().st_size,
                       'sha256':expected,'archive_retries':attempt,'status':'VERIFIED'})
        (seq.output_root/'BY2_IDENTITY_ARCHIVE_LEDGER.json').write_text(json.dumps(ledger,indent=2)+'\n')
    return {'file_count':len(ledger),'bytes':sum(r['size_bytes'] for r in ledger),'retry_count':sum(r['archive_retries'] for r in ledger),
            'pending':0,'scratch_retained':True}


def run_identity():
    seq=load_sequence_paths('BY2');scratch=seq.hext_scratch/'H_EXT_01_BY2_IDENTITY'
    if scratch.exists() or (seq.output_root/'02_BY2_IDENTITY').exists():
        raise FileExistsError('Identity attempt already exists; never auto retry')
    if sha256_file(seq.hash_lock)!=seq.hash_lock_sha256:raise ValueError('Control raw lock identity mismatch')
    target=seq.clean_root/'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/00_PARITY_TARGET_AND_AUDITS/A_TARGET_EXTRACTION.json'
    target_sha=sha256_file(target)
    if target_sha!='63ad6db8a65aafb3730cdcb4342dcd0b3ba1fad88784719ba920755dca169790':raise ValueError('Frozen target identity mismatch')
    targets=json.loads(target.read_text())['methods']
    log=seq.hext_scratch/'IDENTITY_NATIVE_OPENAT.strace'
    stdout=seq.hext_scratch/'IDENTITY_NATIVE_STDOUT.log'
    if log.exists() or stdout.exists():raise FileExistsError('Identity launch log already exists')
    command=['strace','-f','-qq','-yy','-s','4096','-e','trace=openat,execve','-o',str(log),
             sys.executable,'scripts/paper_rebuild/hext_native.py','--sequence','BY2','--workers','2']
    env=dict(os.environ,PYTHONPATH='src',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    started=time.monotonic()
    with stdout.open('x') as handle:
        completed=subprocess.run(command,cwd=seq.code_root,env=env,stdout=handle,stderr=subprocess.STDOUT)
    lines=log.read_text().splitlines()
    trace_names=[load_sequence_paths(name).trace.name for name in ('BY2','BY2H','BY2O')]
    forbidden=[line for line in lines if 'openat(' in line and any(name in line for name in trace_names)]
    eval_exec=[line for line in lines if 'execve(' in line and 'evaluate_nav_trace_kfgins_v2.py' in line]
    receipt={'native_process_exit':completed.returncode,'elapsed_seconds':time.monotonic()-started,
             'trace_open_count':len(forbidden),'evaluator_invocation_count':len(eval_exec),'trace_open_records':forbidden,
             'strace_sha256':sha256_file(log),'target_sha256':target_sha,'default_only':True,'native_budget':2,
             'performance_table_admission':False,'methods':{}}
    summary_path=scratch/'NATIVE_SUMMARY.json'
    if not summary_path.is_file():
        receipt['status']='IDENTITY_UNAVAILABLE_NATIVE_TECHNICAL_FAILURE'
        write_json(seq.output_root/'IDENTITY_UNAVAILABLE.json',receipt)
        return receipt
    summary=json.loads(summary_path.read_text());receipt['native_invocation_count']=summary['native_invocation_count']
    mismatch=False
    for name,method in METHODS.items():
        actual=scratch/method/'EXACT_EVALUATOR_INPUT.nav'
        expected=seq.clean_root/'stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION'/method/'EXACT_EVALUATOR_INPUT.nav'
        pin=targets[name]['continuity']['evaluator_nav_sha256'];digest=sha256_file(actual)
        diff=first_difference(actual,expected) if expected.is_file() else None
        equal=digest==pin and (not expected.is_file() or diff is None)
        row={'method_id':method,'expected_sha256':pin,'actual_sha256':digest,'hash_equal':digest==pin,
             'original_nav_exists':expected.is_file(),'byte_equal':None if not expected.is_file() else diff is None,
             'first_difference':diff,'actual':alias_path(actual,seq),'original':alias_path(expected,seq),
             'output_epoch_count':summary['adapters'][method]['output_epoch_count']}
        receipt['methods'][name]=row;mismatch|=not equal
    receipt['status']='IDENTITY_FAILURE' if mismatch else 'PASS_BY2_BYTE_IDENTITY'
    receipt['native_trace_audit']='PASS' if not forbidden and not eval_exec else 'FAIL'
    write_json(scratch/('IDENTITY_FAILURE.json' if mismatch else 'IDENTITY_PASS.json'),receipt)
    shutil.copyfile(log,scratch/'NATIVE_OPENAT.strace');shutil.copyfile(stdout,scratch/'NATIVE_STDOUT.log')
    receipt['archive']=archive(scratch,seq.output_root/'02_BY2_IDENTITY',seq)
    write_json(seq.output_root/('IDENTITY_FAILURE.json' if mismatch else 'IDENTITY_PASS.json'),receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)
    return receipt
