#!/usr/bin/env python3
"""New native counterexamples for alternate targets; no previous test rerun."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import yaml

ROOT=Path(__file__).resolve().parents[3]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--local-config',type=Path,required=True)
    args=parser.parse_args()
    paths=yaml.safe_load(args.local_config.read_text())['paths']
    scratch=Path(paths['audit_scratch'])/'native_other'
    output=Path(paths['audit_root'])/'native/native_other'
    scratch.mkdir(parents=True,exist_ok=False)
    output.mkdir(parents=True,exist_ok=False)
    build=Path(paths['audit_scratch'])/'native_build'
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    source=ROOT/'tests/paper_rebuild/audit_xbpg/native_other.cpp'
    executable=scratch/'native_other'
    # Reuse existing target objects: the production functions remain unchanged.
    objects=sorted((build/'CMakeFiles/legsa_gins.dir/src').rglob('*.cpp.o'))
    calls=[]
    def call(label,command):
        start=time.perf_counter()
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
        calls.append(dict(label=label,command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,elapsed_seconds=time.perf_counter()-start))
        (output/'CALLS.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2)+'\n')
        print(label,result.returncode,flush=True)
        return result.returncode
    compile_command=['g++','-std=c++17','-O2','-I',str(ROOT/'cpp/include'),'-I',str(ROOT/'cpp/legsa_v23_core/include'),str(source),*[str(p) for p in objects],str(build/'liblegsa_v23_core.a'),'-o',str(executable)]
    if call('compile',compile_command)==0:
        call('counterexamples',[str(executable)])
    receipt=dict(data_mode='synthetic',synthetic_data_used=True,semisynthetic_data_used=False,post_hoc=True,real_data_open_count=0,reference_open_count=0,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),test_binary_sha256=hashlib.sha256(executable.read_bytes()).hexdigest() if executable.exists() else None,calls=calls)
    (output/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    for row in receipt['calls']:row.pop('command',None)
    shared=json.dumps(receipt,ensure_ascii=False,indent=2)
    for literal,alias in [(str(ROOT),'<CODE_ROOT>'),(paths['audit_scratch'],'<AUDIT_SCRATCH>'),(paths['audit_root'],'<AUDIT_ROOT>')]:
        shared=shared.replace(literal,alias)
    (ROOT/'docs/paper_rebuild/audit_xbpg_20261001/NATIVE_OTHER_RESULTS.json').write_text(shared+'\n')

if __name__=='__main__':main()
