#!/usr/bin/env python3
"""Detached phase driver with G-resident human-readable progress and heartbeat."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from legsa_gins.paper_rebuild.clean6_canonical_v2.archive_io import retry_io


def utc(): return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--job', type=Path, required=True); args = ap.parse_args()
    job = json.loads(args.job.read_text()); root = Path(job['root']); control = root/'00_CONTROL'
    control.mkdir(parents=True, exist_ok=True)
    state = {'phase':job['phase'],'purge_subphase':None,'status':'RUNNING','started_utc':utc(),
             'completed_batches':8,'total_batches':None,'completed_solver':None,'solver_total':5410,
             'completed_evaluator':None,'evaluator_total':10820,'total_queue_solver':6468,
             'total_queue_evaluator':12936,'completed_all_solver':512,'completed_all_evaluator':1024,
             'failures':0,'current_batch_start':None,'last_10_batches_mean_seconds':None,
             'estimated_completion_utc':None,'latest_pause_or_hard_stop_reason':None,
             'scope':'CORE_NON_F01_PRIMARY_PROGRESS; ALL_FROZEN_DOMAINS_RETAINED', 'controller_pid':os.getpid()}
    stop = threading.Event(); lock = threading.Lock()
    def write(path, data):
        def action():
            with path.open('w') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        retry_io(action, source=path, destination=path, operation='v3r_control_heartbeat')
    def update():
        with lock:
            state['heartbeat_utc']=utc()
            state['scratch_bytes']=int(subprocess.check_output(['du','-s','-B1',job['scratch']],text=True).split()[0])
            for label,mount in [('e_available_bytes','/mnt/e'),('g_available_bytes','/mnt/g')]:
                state[label]=int(subprocess.check_output(['df','-B1','--output=avail',mount],text=True).splitlines()[-1])
            purge=root/'V3R_PURGE'
            if state['phase']=='PURGE':
                for marker,sub in [('PLAN.json','inventoried'),('P4_VERIFIED.json','verified'),('PURGE_RESULT.json','deleted')]:
                    if (purge/marker).exists(): state['purge_subphase']=sub
                journal=purge/'OPERATIONS.jsonl'
                if journal.exists():
                    events=[]
                    for line in journal.read_text().splitlines():
                        try:events.append(json.loads(line))
                        except json.JSONDecodeError:continue
                    actions={e.get('action') for e in events}
                    if 'QUARANTINE_COMPLETE' in actions:state['purge_subphase']='quarantined'
                    if 'VERIFIED' in actions:state['purge_subphase']='verified'
                    if 'PURGE_COMPLETE' in actions:state['purge_subphase']='deleted'
            data=json.dumps(state,ensure_ascii=False,indent=2)+'\n'
            text='\n'.join(f'{key}: {value if value is not None else "UNAVAILABLE"}' for key,value in state.items())+'\n'
            write(control/'STATE.json',data);write(control/'PROGRESS.txt',text)
    def heartbeats():
        while not stop.wait(60): update()
    update(); thread=threading.Thread(target=heartbeats,daemon=True);thread.start()
    try:
        for index,argv in enumerate(job['commands'],1):
            state['current_command']=argv;state['current_batch_start']=utc();update()
            log=control/(job['phase']+'_'+job.get('label','phase')+f'_{index:02d}.log')
            with log.open('a') as output:
                result=subprocess.run(argv,cwd=job['code_root'],stdout=output,stderr=subprocess.STDOUT,check=False,
                                      env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
            if result.returncode:
                raise RuntimeError(f'COMMAND_EXIT_{result.returncode}; log={log}; tail='+log.read_text()[-2000:])
        state['status']='PHASE_COMPLETE';state['completed_utc']=utc()
    except Exception as exc:
        state['status']='HARD_STOP';state['latest_pause_or_hard_stop_reason']=str(exc)
        raise
    finally:
        stop.set();update()
        write(control/(job['phase']+'_'+job.get('label','phase')+'_TERMINAL.json'),json.dumps(state,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
