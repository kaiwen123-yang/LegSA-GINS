#!/usr/bin/env python3
"""Build + pure synthetic fixture only. Reads no scientific input/config file.
CMake configuration and frozen-library build are explicit prerequisites recorded in BUILD_RECEIPT.
No retry/overwrite: a previous synthetic output directory blocks the entire command list.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute',action='store_true',required=True)
    args=ap.parse_args()
    code=Path(__file__).resolve().parents[5]
    local=json.loads((code/'configs/paper_rebuild/V3_MECHANISM_ROOTS.local.json').read_text())
    base=Path(local['aliases']['<MECHANISM_BUILD_ROOT>'])
    fixture=Path(__file__).with_name('synthetic_fixture.cpp')
    logs=base/'build_logs';logs.mkdir(exist_ok=True)
    runroot=base/'synthetic_fixture_v1'
    if runroot.exists():
        raise SystemExit('Existing synthetic_fixture_v1: refusal; no automatic retry')
    runroot.mkdir()
    commands=[('build_observed_final',['cmake','--build',str(base/'build_observed'),'--target','legsa_v23_port_core_demo','-j','2'],False)]
    for kind,build in [('frozen','build_frozen_fixture'),('observed','build_observed')]:
        commands.append(('compile_fixture_'+kind,['/usr/bin/g++','-O3','-DNDEBUG','-std=c++17','-I',str(base/('source_'+kind)/'cpp/legsa_v23_port_core/include'),str(fixture),str(base/build/'liblegsa_v23_port_core.a'),'-o',str(runroot/('fixture_'+kind))],False))
    for condition,binary,mode in [('frozen','frozen','observer_off'),('observed_off','observed','observer_off'),('observed_on','observed','observer_on')]:
        commands.append(('synthetic_native_'+condition,[str(runroot/('fixture_'+binary)),str(runroot/condition),mode],True))
    receipt=logs/'COMMANDS.json'
    records=json.loads(receipt.read_text()) if receipt.exists() else []
    env=os.environ.copy()
    for key in ('LEGSA_V3_OBSERVER_DIR','LEGSA_V3_OBSERVER_RUN_ID'):env.pop(key,None)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    for label,argv,is_native in commands:
        idx=len(records)+1
        record={'command_id':idx,'label':label,'argv':argv,'started_unix':time.time(),'status':'STARTED','synthetic_native_process':is_native,'real_native_process':False,'log':str(logs/f'{idx:02d}_{label}.log')}
        records.append(record);receipt.write_text(json.dumps(records,indent=2)+'\n')
        print('START',idx,label,flush=True)
        with open(record['log'],'x') as f:
            result=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,env=env)
        record.update(exit_code=result.returncode,ended_unix=time.time(),status='COMPLETED' if result.returncode==0 else 'FAILED')
        receipt.write_text(json.dumps(records,indent=2)+'\n');print('END',idx,label,result.returncode,flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)

if __name__=='__main__':main()
