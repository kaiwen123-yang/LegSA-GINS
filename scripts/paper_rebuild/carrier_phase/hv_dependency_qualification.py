#!/usr/bin/env python3
"""Registered synthetic qualification then one preparation pass over six inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from hv_dependency_prepare import prepare_bytes


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def emit(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--registration-commit', required=True)
    args = parser.parse_args()
    plan_path = (ROOT / args.plan).resolve()
    payload = plan_path.read_bytes()
    plan = json.loads(payload)
    require(plan['status'] == 'REGISTERED_READY_SINGLE_EXECUTION', 'registered state')
    require(payload == subprocess.check_output(['git','show',args.registration_commit+':'+str(plan_path.relative_to(ROOT))], cwd=ROOT), 'registered plan')
    require(plan['budgets']['harness_processes'] == len(plan['cases']) == 8, 'eight fixed native cases')
    for relative, pin in plan['source_pins'].items():
        source = (ROOT / relative).read_bytes()
        require(digest(source) == pin, 'source identity: '+relative)
        require(source == subprocess.check_output(['git','show',args.registration_commit+':'+relative], cwd=ROOT), 'registered source: '+relative)
    require(all(plan['source_pins'].get(k) == v for k, v in plan['preparation_source_pins'].items()), 'verified preparation source subset')
    def expand(value):
        for name, replacement in plan['aliases'].items():
            value = value.replace(name, replacement)
        require('<' not in value, 'unresolved alias')
        return Path(value).resolve()
    stage = expand(plan['stage'])
    require(stage.parent == ROOT.parent.parent / 'LegSA-GINS-SCRATCH/TRUSTED_HEADING_CONTINUATION_20261007' and not stage.exists(), 'new bounded stage')
    stage.mkdir()
    emit(stage/'REGISTERED_PLAN.json', plan)
    emit(stage/'RESERVATION.json', dict(registration_commit=args.registration_commit,budgets=plan['budgets']))
    env = {**os.environ, **plan['environment'], 'PYTHONPATH':str(ROOT/'src')}
    env.pop('PYTEST_ADDOPTS', None); env.pop('PYTEST_PLUGINS', None)
    tmp = stage/'TMP'; tmp.mkdir(); env['TMPDIR'] = str(tmp)
    calls, reads, attempts, cases, providers = [], [], [], [], []
    def invoke(name, command, timeout):
        emit(stage/(name+'_INVOCATION.json'),dict(command=command,timeout_s=timeout))
        started=time.monotonic(); timed=False
        with (stage/(name+'_stdout.log')).open('x') as out, (stage/(name+'_stderr.log')).open('x') as err:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=out,stderr=err,start_new_session=True)
            try: code=child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed=True; os.killpg(child.pid,signal.SIGKILL); code=child.wait()
        row=dict(name=name,returncode=code,timeout=timed,elapsed_s=time.monotonic()-started)
        calls.append(row); emit(stage/(name+'_EXIT.json'),row); print(json.dumps(row),flush=True)
        require(code==0 and not timed, 'first failure: '+name)
    def read_once(pin, role):
        path=expand(pin['path'])
        require(all(x['path'] != str(path) for x in attempts), 'input opened twice')
        record=dict(role=role,path=str(path),expected_bytes=pin['size_bytes'],bytes_read=0)
        attempts.append(record)
        require(path.stat().st_size==pin['size_bytes'], 'input size before read')
        with path.open('rb') as stream: data=stream.read(pin['size_bytes']+1)
        record['bytes_read']=len(data)
        require(len(data)==pin['size_bytes'], 'bounded input read size')
        return data
    try:
        invoke('01_PYTEST',[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',plan['python_test'],'--junitxml='+str(stage/'PYTEST.xml')],60)
        suites=ET.parse(stage/'PYTEST.xml').getroot().findall('.//testsuite')
        require(sum(int(s.get('tests','0')) for s in suites)==plan['budgets']['python_cases'] and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped')), 'fixed Python test count')
        build=stage/'BUILD'
        invoke('02_CONFIGURE',['cmake','-S',str(ROOT/'cpp'),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release'],60)
        invoke('03_BUILD',['cmake','--build',str(build),'--target','legsa_v23_port_core_demo','-j','4'],300)
        harness=stage/'native_hv_dependency_policy_harness'
        invoke('04_HARNESS_COMPILE',['g++','-std=c++17','-O2','-I'+str(ROOT/'cpp/legsa_v23_port_core/include'),str(ROOT/plan['harness_source']),str(build/'liblegsa_v23_port_core.a'),'-o',str(harness)],60)
        for i, case in enumerate(plan['cases'],5):
            output=stage/('CASE_'+case); output.mkdir()
            name=f'{i:02d}_{case}'
            invoke(name,[str(harness),case,str(output)],20)
            evidence=json.loads((stage/(name+'_stdout.log')).read_text().splitlines()[-1])
            require(evidence['case']==case and evidence['status']=='PASS', 'native case result')
            require({k:evidence[k] for k in plan['case_call_counts'][case]}==plan['case_call_counts'][case], 'bounded case call counts')
            cases.append(evidence)
        # No scientific payload is opened until every local case has passed.
        require(len(plan['sequences'])==3 and sum(s[k]['size_bytes'] for s in plan['sequences'] for k in ('hv','gnss'))==67191365, 'six input budget')
        for spec in plan['sequences']:
            sid=spec['sequence_id']
            hv=read_once(spec['hv'],sid+':hv'); gnss=read_once(spec['gnss'],sid+':gnss')
            # This pure function verifies each already-read byte buffer hash once.
            output, manifest=prepare_bytes(hv,gnss,hv_pin=spec['hv'],gnss_pin=spec['gnss'],source_pins=plan['preparation_source_pins'],plan_pin=dict(path=args.plan,sha256=digest(payload)),expected_rows=spec['provider_rows'],expected_helper_calls=spec['helper_calls'],sequence_id=sid)
            dest=stage/'PROVIDERS'/sid; dest.mkdir(parents=True)
            path=dest/'GO2_HORIZONTAL_VELOCITY_PRIOR.csv'
            with path.open('xb') as stream: stream.write(output)
            emit(dest/'MANIFEST.json',manifest)
            providers.append(dict(sequence_id=sid,path=str(path),manifest=manifest))
            reads.extend(dict(role=sid+':'+k,**spec[k],physical_read_passes=1) for k in ('hv','gnss'))
            print(sid,'FULL_PROVIDER_PREPARED',flush=True)
            del hv,gnss,output
        require(len(reads)==6 and sum(x['size_bytes'] for x in reads)==67191365,'six once-read input receipts')
        binary=build/'legsa_v23_port_core_demo'
        result=dict(status='PASS_LOCAL_AND_FULL_DEPENDENCY_METADATA_PREPARATION',registration_commit=args.registration_commit,calls=calls,case_results=cases,python_cases=plan['budgets']['python_cases'],native_cases=8,providers=providers,input_reads=reads,source_pins=plan['source_pins'],binary=dict(path=str(binary),sha256=digest(binary.read_bytes()),size_bytes=binary.stat().st_size),harness_sha256=digest(harness.read_bytes()),native_real_calls=0,evaluator_calls=0,actual_arrival_qualified=False,velocity_recomputed=False,automatic_retries=0)
        emit(stage/'COMPLETE.json',result)
        print(result['status'],flush=True)
    except BaseException as exc:
        emit(stage/'FAILED.json',dict(error=repr(exc),traceback=traceback.format_exc(),calls=calls,input_attempts=attempts,successful_input_reads=reads,providers_completed=providers,automatic_retries=0))
        raise


if __name__=='__main__':
    main()
