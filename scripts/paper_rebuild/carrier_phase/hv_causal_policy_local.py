#!/usr/bin/env python3
"""One registered build and six synthetic policy cases; no real input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback

ROOT=Path(__file__).resolve().parents[3]
D=ROOT/'docs/paper_rebuild/TRUSTED_HEADING_CONTINUATION_20261007'
PLAN=D/'HV_CAUSAL_POLICY_LOCAL_PLAN.json'
STAGE=ROOT.parent.parent/'LegSA-GINS-SCRATCH/TRUSTED_HEADING_CONTINUATION_20261007/HV_CAUSAL_POLICY_LOCAL_ATTEMPT01'

def require(ok,message):
    if not ok:raise RuntimeError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def emit(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--registration-commit',required=True);args=parser.parse_args()
    payload=PLAN.read_bytes();plan=json.loads(payload)
    require(plan['status']=='REGISTERED_READY_SINGLE_EXECUTION','draft plan')
    require(payload==subprocess.check_output(['git','show',args.registration_commit+':'+str(PLAN.relative_to(ROOT))],cwd=ROOT),'plan registration')
    require(len(plan['cases'])==6 and len(set(plan['cases']))==6,'six fixed cases')
    def sources():
        for name,value in plan['source_pins'].items():
            require(sha(ROOT/name)==value,'source changed: '+name)
            require((ROOT/name).read_bytes()==subprocess.check_output(['git','show',args.registration_commit+':'+name],cwd=ROOT),'source registration: '+name)
    sources();require(not STAGE.exists(),'unique attempt no retry');STAGE.mkdir(parents=True)
    emit(STAGE/'REGISTERED_PLAN.json',plan);emit(STAGE/'RESERVATION.json',dict(registration_commit=args.registration_commit,budgets=plan['budgets']))
    build=STAGE/'BUILD';tmp=STAGE/'TMP';tmp.mkdir()
    env={**os.environ,**plan['environment'],'TMPDIR':str(tmp)};calls=[];case_results=[]
    def invoke(name,command,timeout):
        emit(STAGE/(name+'_INVOCATION.json'),dict(command=command,timeout_s=timeout))
        started=time.monotonic();timed=False
        with (STAGE/(name+'_stdout.log')).open('x') as out,(STAGE/(name+'_stderr.log')).open('x') as err:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=out,stderr=err,start_new_session=True)
            try:code=child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
        row=dict(name=name,returncode=code,timeout=timed,elapsed_s=time.monotonic()-started)
        calls.append(row);emit(STAGE/(name+'_EXIT.json'),row);print(json.dumps(row),flush=True)
        require(code==0 and not timed,'first failure: '+name)
    try:
        invoke('01_CONFIGURE',['cmake','-S',str(ROOT/'cpp'),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release'],60)
        invoke('02_BUILD',['cmake','--build',str(build),'--target','legsa_v23_port_core_demo','-j','4'],300)
        harness=STAGE/'native_hv_causal_policy_harness'
        invoke('03_HARNESS_COMPILE',['g++','-std=c++17','-O2','-I'+str(ROOT/'cpp/legsa_v23_port_core/include'),str(ROOT/plan['harness_source']),str(build/'liblegsa_v23_port_core.a'),'-o',str(harness)],60)
        for i,case in enumerate(plan['cases'],4):
            output=STAGE/('CASE_'+case);output.mkdir()
            invoke(f'{i:02d}_{case}',[str(harness),case,str(output)],20)
            evidence=json.loads((STAGE/f'{i:02d}_{case}_stdout.log').read_text().splitlines()[-1])
            require(evidence['case']==case and evidence['status']=='PASS','case identity')
            require({k:evidence[k] for k in plan['case_call_counts'][case]}==plan['case_call_counts'][case],'bounded synthetic case call counts')
            case_results.append(evidence)
        sources()
        result=dict(status='PASS_SIX_SYNTHETIC_CAUSAL_POLICY_CASES',registration_commit=args.registration_commit,passed=6,failed=0,calls=calls,case_results=case_results,source_pins=plan['source_pins'],native_real_calls=0,evaluator_calls=0,real_input_reads=0,automatic_retries=0,actual_arrival_qualified=False,
            binary=dict(path=str(build/'legsa_v23_port_core_demo'),sha256=sha(build/'legsa_v23_port_core_demo'),size_bytes=(build/'legsa_v23_port_core_demo').stat().st_size),
            library=dict(path=str(build/'liblegsa_v23_port_core.a'),sha256=sha(build/'liblegsa_v23_port_core.a')),harness_sha256=sha(harness))
        emit(STAGE/'COMPLETE.json',result);print(result['status'],flush=True)
    except BaseException as exc:
        emit(STAGE/'FAILED.json',dict(error=repr(exc),traceback=traceback.format_exc(),calls=calls,automatic_retries=0));raise

if __name__=='__main__':main()
