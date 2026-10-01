#!/usr/bin/env python3
"""Bounded follow-up native tests; no real inputs or reference files opened."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import yaml

ROOT = Path(__file__).resolve().parents[3]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-config', type=Path, required=True)
    args = parser.parse_args()
    paths = yaml.safe_load(args.local_config.read_text())['paths']
    scratch = Path(paths['audit_scratch']) / 'native_additional'
    output = Path(paths['audit_root']) / 'native/native_additional'
    scratch.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    calls = []
    def run(label, command):
        start=time.perf_counter()
        try:
            process=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            row=dict(label=label,command=command,returncode=process.returncode,stdout=process.stdout,stderr=process.stderr)
        except subprocess.TimeoutExpired as exc:
            row=dict(label=label,command=command,returncode=None,status='TIMEOUT',stdout=str(exc.stdout or ''),stderr=str(exc.stderr or ''))
        row['elapsed_seconds']=time.perf_counter()-start
        calls.append(row)
        (output/'CALLS.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2)+'\n')
        print(label,row['returncode'],flush=True)
        return row
    build=Path(paths['audit_scratch'])/'native_build'
    capture=Path(paths['audit_scratch'])/'native_initial/gi_engine_capture_only.cpp'
    source=ROOT/'tests/paper_rebuild/audit_xbpg/native_additional.cpp'
    executable=scratch/'native_additional'
    result=run('compile',['g++','-std=c++17','-O2','-I',str(ROOT/'cpp/legsa_v23_port_core/include'),str(source),str(capture),str(build/'liblegsa_v23_port_core.a'),'-o',str(executable)])
    if result['returncode']!=0:
        raise SystemExit('compile failed; receipt retained')
    for mode in ['position_steps','async_lever','hv_sentinel','consistency','saver','missing_provider']:
        run(mode,[str(executable),mode,str(scratch/mode)])
    result=dict(data_mode='synthetic',synthetic_data_used=True,semisynthetic_data_used=False,real_data_open_count=0,reference_open_count=0,post_hoc=True,
        test_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        native_binary_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        instrumentation='same capture-only scratch engine as initial experiment',calls=calls)
    (output/'RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for row in result['calls']:row.pop('command',None)
    (ROOT/'docs/paper_rebuild/audit_xbpg_20261001/NATIVE_EXTRA_RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
