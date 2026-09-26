#!/usr/bin/env python3
"""Six fixed official-API runs, existing audited evaluator, no scientific retries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records, write_scope_audit
from legsa_gins.paper_rebuild.hext import hx02_evaluation_process as launcher
from legsa_gins.paper_rebuild.hext.hx02d_reference_free import load_cache, load_raw, ols
from legsa_gins.paper_rebuild.subprocess_guard import run_process_group


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def dump(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with Path(path).open('x') as f:
        f.write(text)


def guards(scratch, official, source_pins):
    free = {m:int(subprocess.check_output(['df','--output=avail','-B1',m]).decode().splitlines()[1])
            for m in ['/mnt/e','/mnt/g']}
    size = sum(p.stat().st_size for p in scratch.rglob('*') if p.is_file())
    assert free['/mnt/e'] >= 40000000000 and free['/mnt/g'] >= 30000000000 and size <= 20000000000, 'HARD_STOP_DISK'
    assert subprocess.check_output(['git','-C',str(official),'status','--porcelain']) == b'', 'HARD_STOP_OFFICIAL_DIRTY'
    assert subprocess.check_output(['git','-C',str(official),'rev-parse','HEAD']).decode().strip() == 'ef16e8a1df72f9272111a488880e3fe9d161f59f', 'HARD_STOP_OFFICIAL_HEAD'
    assert all(sha(official/p)==h for p,h in source_pins.items()), 'HARD_STOP_OFFICIAL_SOURCE'
    return {'available_bytes':free,'scratch_bytes':size}


def sanity(nav, cache, gyro_z, sequence):
    data = np.loadtxt(nav, delimiter=',', skiprows=1, usecols=(0,14,15,16,19), ndmin=2)
    time_ns = cache['t'][:len(data)]
    assert np.array_equal(data[:,0], time_ns.astype(float))
    t = time_ns.astype(float)*1e-9-sequence['base_time']
    lo,hi=sequence['window']
    mask=(t>=lo)&(t<=hi)
    values=data[mask]
    tt=t[mask]
    raw_z=gyro_z[:len(data)][mask]
    if len(tt)<2:
        return {'valid_epochs':len(tt),'yaw_minus_raw_gyro_z_drift_deg_per_min':None,
                'native_path_length_10hz_m':None,'status':'UNAVAILABLE_WINDOW'}
    yaw=np.degrees(np.unwrap(np.radians(values[:,4])))
    integral=np.degrees(np.r_[0,np.cumsum(raw_z[:-1]*np.diff(time_ns[mask])*1e-9)])
    delta=(yaw-yaw[0])-integral
    fit=ols((tt-tt[0])/60,delta)
    # Same 10 Hz closed grid and interpolation support as HX-02D B4.
    grid=lo+np.arange(int(round((hi-lo)*10))+1)*0.1
    grid=grid[(grid>=t[0])&(grid<=t[-1])]
    pos=np.column_stack([np.interp(grid,t,data[:,j]) for j in [1,2,3]])
    path=float(np.linalg.norm(np.diff(pos[:,:2],axis=0),axis=1).sum())
    return {'valid_epochs':int(mask.sum()),'yaw_minus_raw_gyro_z_drift_deg_per_min':fit['slope'],
            'yaw_minus_raw_gyro_z_rms_deg':float(np.sqrt(np.mean(delta**2))),
            'native_path_length_10hz_m':path,'path_grid_epochs':len(grid),
            'yaw_definition':'Unwrapped native FLU/up-world yaw increments minus raw sensor z left-hold integral; evaluation window; OLS per minute',
            'path_definition':'Native IMU-point horizontal path on the supported HX-02 10 Hz window grid'}


def run(a):
    contract=json.loads(a.contract.read_text())
    official=a.external/'hartley/invariant-ekf'
    source_pins=json.loads((a.scratch/'00_CONTROL/OFFICIAL_SOURCE_START.json').read_text())['tracked_files']
    assert (a.scratch/'00_CONTROL/PROTECTED_TREES_START.json').is_file()
    assert all(x['passed'] for x in json.loads((a.scratch/'00_CONTROL/DRIVER_GATES/GATES.json').read_text()))
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.code_root).decode().strip()==a.commit
    assert subprocess.check_output(['git','show','-s','--format=%s',a.commit],cwd=a.code_root).decode().strip()=='prereg(hx02e): official Hartley InEKF on three sequences'
    assert not subprocess.check_output(['git','diff','--name-only'],cwd=a.code_root).strip()
    assert all(sha(a.code_root/p)==h for p,h in contract['source_sha256'].items())
    binary=a.scratch/'BUILD/hx02e_official_driver'
    build=json.loads((a.scratch/'BUILD/BUILD_RECEIPT.json').read_text())
    assert sha(binary)==build['executables']['hx02e_official_driver']
    for rel,h in source_pins.items():
        assert sha(a.scratch/'BUILD/official'/rel)==h
    assert sha(a.scratch/'BUILD/official/lib/libinekf.so')==build['executables']['official/lib/libinekf.so']
    ledger=a.scratch/'00_CONTROL/REAL_CALLS.jsonl'
    assert not ledger.exists()
    count={'legsa_native':0,'legsa_evaluation':0,'official_real_native':0,'relative_pose_evaluation':0,'reference_opens':0}
    outcomes=[]
    def event(x):
        with ledger.open('a') as f:
            f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    inputs=json.loads((a.hx02/'01_INPUT_PINS/INPUT_PINS.json').read_text())
    for seq,sequence in contract['sequences'].items():
        sequence={**sequence,'trace':str(a.raw_root/sequence['trace_relative_path'])}
        provider=a.hx02/'01_INPUT_PINS/HARTLEY'/seq
        manifest=json.loads((provider/'H5_INPUT_CACHE_MANIFEST.json').read_text())
        assert sha(provider/'H5_INPUT_CACHE.bin')==sequence['cache_sha256']
        cache=load_cache(provider/'H5_INPUT_CACHE.bin',manifest)
        pin=inputs['go2'][seq]
        raw_manifest={'raw_sha256':pin['raw']['sha256'],'prefix_interval':[0,pin['prefix_end_exclusive']],
                      'prefix_sha256':pin['prefix_sha256'],'record_count':pin['record_separator_count']}
        raw=load_raw(manifest['source_identity']['source'],raw_manifest)
        index=np.searchsorted(raw['time_ns'],cache['t'])
        assert np.array_equal(raw['time_ns'][index],cache['t'])
        raw_gyro=raw['gyroscope'][index]
        angle=np.radians(-1.0);c,s=np.cos(angle),np.sin(angle)
        sensor_to_body=np.array([[1,0,0],[0,c,-s],[0,s,c]])
        assert np.allclose(raw_gyro@sensor_to_body.T,cache['v'][:,:3],rtol=0,atol=1e-14)
        for cfg in contract['configurations']:
            disk=guards(a.scratch,official,source_pins)
            ident=f'{seq}__HARTLEY_OFFICIAL__{cfg}__{sequence["case"]}'
            directory=a.scratch/'RUNS'/ident
            directory.mkdir(parents=True,exist_ok=False)
            nav=directory/'NAV.csv'
            runtime_config=a.code_root/'configs/paper_rebuild/hext/HX02E'/f'{cfg}.cfg'
            assert sha(runtime_config)==contract['source_sha256'][str(runtime_config.relative_to(a.code_root))]
            argv=['strace','-f','-yy','-s','4096','-e','trace=openat,execve','-o',str(directory/'NATIVE_OPENAT.strace'),
                  str(binary),str(provider/'H5_INPUT_CACHE.bin'),str(runtime_config),str(nav)]
            count['official_real_native']+=1
            event({'state':'NATIVE_INTENT','run':ident,'counts':dict(count),'argv':argv,'disk':disk})
            started=time.monotonic()
            native=run_process_group(argv,cwd=a.code_root,timeout_seconds=600,
                                     timeout_message='ABNORMAL_EXIT timeout; no retry',launch_failure_message='ABNORMAL_EXIT launch failure')
            (directory/'native_stdout.log').write_text(native.stdout)
            (directory/'native_stderr.log').write_text(native.stderr)
            records=audited_open_records(directory/'NATIVE_OPENAT.strace',a.code_root)
            forbidden=[r for r in records if Path(r['path']).name.startswith('trace_vrtk') or Path(r['path']).suffix.lower() in {'.bag','.fpl'} or a.raw_root in Path(r['path']).parents]
            scope=write_scope_audit(records,raw_root=a.raw_root,clean_root=a.clean_root,allowed_write_roots=[directory])
            executed=[m[1] for line in (directory/'NATIVE_OPENAT.strace').read_text().splitlines() if (m:=launcher.EXECVE_RE.search(line))]
            allowed=not forbidden and scope['pass'] and executed==[str(binary)]
            audit={'passed':allowed,'reference_opens':len(forbidden),'write_scope':scope,'execve_programs':executed,
                   'strace_sha256':sha(directory/'NATIVE_OPENAT.strace'),'cache_opens':[r for r in records if r['path']==str(provider/'H5_INPUT_CACHE.bin')]}
            dump(directory/'NATIVE_AUDIT.json',audit)
            assert allowed,'HARD_STOP_NATIVE_ACCESS'
            flag='ALGORITHM_FAILURE_DIVERGED' if native.returncode==20 else 'ABNORMAL_EXIT' if native.returncode else 'COMPLETED' if nav.exists() and nav.stat().st_size>200 else 'NO_OUTPUT'
            outcome={'run_id':ident,'sequence':seq,'config':cfg,'start_mode':sequence['case'],'failure_flag':flag,
                     'returncode':native.returncode,'runtime_seconds':time.monotonic()-started,'code_commit':a.commit,
                     'cache_sha256':sequence['cache_sha256'],'config_sha256':sha(runtime_config),'binary_sha256':sha(binary),
                     'native_audit':audit,'synthetic_input':False,'trace_used_online':False}
            event({'state':'NATIVE_TERMINAL','run':ident,'failure_flag':flag,'returncode':native.returncode})
            if nav.exists() and sum(1 for _ in nav.open())>=3:
                outcome['nav_sha256']=sha(nav)
                outcome['sanity']=sanity(nav,cache,raw_gyro[:,2],sequence)
                spec={k:sequence[k] for k in ['base_time','window','baseline_median_m','trace','trace_sha256']}
                spec.update(sequence_id=seq,branches={cfg:{'nav':str(nav),'nav_sha256':outcome['nav_sha256']}})
                count['relative_pose_evaluation']+=1
                event({'state':'EVALUATOR_INTENT','run':ident,'counts':dict(count)})
                ev=launcher.run_child('RELATIVE_POSE',spec,workdir=directory/'eval',code_root=a.code_root,
                                      raw_root=a.raw_root,clean_root=a.clean_root,trace=Path(sequence['trace']),timeout_seconds=600)
                count['reference_opens']+=ev['audit']['trace_open_count']
                metrics=json.loads((Path(ev['outdir'])/'RELATIVE_POSE_METRICS.json').read_text())['branches'][cfg]
                outcome['metrics']=metrics
                ref=sequence.get('recorded_reference_path_length_m')
                if ref is None:ref=metrics.get('reference_path_length_m')
                length=outcome['sanity'].get('native_path_length_10hz_m')
                outcome['sanity'].update(reference_path_length_m=ref,native_to_reference_path_ratio=None if not ref or length is None else length/ref)
                event({'state':'EVALUATOR_TERMINAL','run':ident,'audit_pass':True,'counts':dict(count)})
            else:
                outcome['metrics']={'evaluation_status':'NOT_EVALUATED_NO_USABLE_OUTPUT'}
                outcome['sanity']={'status':'NOT_AVAILABLE_NO_USABLE_OUTPUT'}
                event({'state':'EVALUATOR_SKIPPED_NO_USABLE_OUTPUT','run':ident})
            dump(directory/'RESULT.json',outcome)
            outcomes.append(outcome)
            print(ident,flag,'native',count['official_real_native'],'evaluation',count['relative_pose_evaluation'],flush=True)
    dump(a.scratch/'00_CONTROL/EXECUTION_COUNTS.json',count)
    dump(a.scratch/'00_CONTROL/RESULTS.json',outcomes)
    guards(a.scratch,official,source_pins)
    assert count['official_real_native']==6 and count['relative_pose_evaluation']<=6
    assert all(sha(a.code_root/p)==h for p,h in contract['source_sha256'].items())


def main():
    def guard(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0]))
            if p.name.startswith('trace_vrtk') or p.suffix.lower() in {'.bag','.fpl'}:
                raise RuntimeError('HARD_STOP_CONTROLLER_REFERENCE_OPEN')
    sys.addaudithook(guard)
    p=argparse.ArgumentParser()
    for name in ['code-root','external','scratch','hx02','raw-root','clean-root','contract']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--commit',required=True)
    a=p.parse_args()
    try:
        run(a)
    except Exception as e:
        dump(a.scratch/'00_CONTROL/HARD_STOP.json',{'exception':type(e).__name__,'reason':str(e),'no_retry':True})
        raise


if __name__=='__main__':
    main()
