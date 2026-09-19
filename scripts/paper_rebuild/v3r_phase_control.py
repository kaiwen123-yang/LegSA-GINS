#!/usr/bin/env python3
"""Detached phase driver with G-resident human-readable progress and heartbeat."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
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


def update_control_metadata(state, job, root):
    """Read independent purge-round and capacity evidence without running work."""
    root = Path(root)
    purge = Path(job.get('purge_plan_dir', root/'V3R_PURGE'))
    state['purge_plan_dir'] = str(purge)
    state['purge_round'] = job.get('purge_round', 'P')
    reconciliation = root/'00_CONTROL/V3R_RECONCILIATION/RECONCILIATION_MANIFEST.json'
    if 'scratch' in job and reconciliation.is_file():
        if '_reconciled_progress' not in job:
            admitted = json.loads(reconciliation.read_text())
            if admitted.get('status') == 'PASS_ARCHIVE_RECONCILIATION':
                specs = json.loads((Path(job['scratch'])/'00_PREREGISTRATION/REGISTRY.json').read_text())
                native = {row['run_id'] for key in ('reused_runs','identity_native_only') for row in admitted[key]}
                evaluations = {(row['run_id'], version) for key in ('reused_runs','identity_native_only')
                               for row in admitted[key] for version in row.get('evaluations',{})}
                groups = {}
                for name, selected in (
                    ('core_non_f01', [s for s in specs if s['domain']=='CORE' and s['method_id']!='F01']),
                    ('core_f01', [s for s in specs if s['domain']=='CORE' and s['method_id']=='F01']),
                    ('extra_sequences', [s for s in specs if s['domain']=='SEQUENCE']),
                    ('addendum_a1_a2', [s for s in specs if s['domain']=='ADDENDUM']),
                    ('total_queue', specs)):
                    ids = {s['run_id'] for s in selected}
                    groups[name] = dict(solver_done=len(native & ids), solver_total=len(ids),
                                        evaluator_done=sum(rid in ids for rid,version in evaluations), evaluator_total=2*len(ids))
                job['_reconciled_progress'] = dict(progress=groups,
                    completed_batches=admitted['completed_batch_count'],
                    total_batches=admitted['completed_batch_count']+(len(specs)-len(admitted['reused_runs'])+21)//22)
        if '_reconciled_progress' in job:
            state.update(job['_reconciled_progress'])
            main, total = state['progress']['core_non_f01'], state['progress']['total_queue']
            state.update(completed_solver=main['solver_done'], completed_evaluator=main['evaluator_done'],
                         completed_all_solver=total['solver_done'], completed_all_evaluator=total['evaluator_done'])
    forecast = Path(job.get('capacity_forecast', root/'00_CONTROL/CAPACITY_FORECAST.json'))
    state['capacity_forecast_source'] = str(forecast)
    try:
        raw = forecast.read_bytes()
        value = json.loads(raw)
        if not isinstance(value, dict): raise ValueError('capacity forecast must be an object')
    except (OSError, ValueError) as exc:
        state.setdefault('capacity_forecast', 'UNAVAILABLE')
        state['capacity_forecast_read_status'] = 'UNAVAILABLE'
        state['capacity_forecast_read_reason'] = str(exc)
    else:
        state['capacity_forecast'] = value
        state['capacity_forecast_sha256'] = hashlib.sha256(raw).hexdigest()
        state['capacity_forecast_read_status'] = 'AVAILABLE'
        state['capacity_forecast_read_reason'] = None
    if state['phase'] != 'PURGE': return
    subphase = 'inventoried' if (purge/'PLAN.json').exists() else None
    journal = purge/'OPERATIONS.jsonl'
    actions = set()
    if journal.exists():
        for line in journal.read_text().splitlines():
            try: actions.add(json.loads(line).get('action'))
            except json.JSONDecodeError: continue
    if 'QUARANTINE_COMPLETE' in actions: subphase = 'quarantined'
    # A fixed-name P4_VERIFIED file may be an interrupted write. Only the
    # durable journal commit establishes verified state.
    if 'VERIFIED' in actions: subphase = 'verified'
    if 'PURGE_COMPLETE' in actions: subphase = 'deleted'
    if 'ROLLBACK_BEGIN' in actions: subphase = 'rolling_back'
    if 'ROLLED_BACK' in actions: subphase = 'rolled_back'
    state['purge_subphase'] = subphase


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
            update_control_metadata(state, job, root)
            data=json.dumps(state,ensure_ascii=False,indent=2)+'\n'
            text='\n'.join(f'{key}: '+(json.dumps(value,ensure_ascii=False,sort_keys=True) if isinstance(value,dict)
                                      else str(value) if value is not None else 'UNAVAILABLE')
                           for key,value in state.items())+'\n'
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
