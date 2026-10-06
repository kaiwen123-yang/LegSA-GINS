#!/usr/bin/env python3
"""One-shot HX-07 execution; V0 gate precedes all evaluations and V1/V2."""
import os
import sys
from pathlib import Path
import csv
import json
import math
import subprocess
import datetime
import re

from hx07_prepare import W, C, H, D, O, R, S, EXT, PATHS, sha, dump, alias, resolve

# Reject accidental raw/reference access in the controller, including imports.
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0]); name = Path(p).name.lower()
        if p.startswith(PATHS['raw_root'] + '/') or name.endswith(('.bag','.fpl')) or name.startswith('trace_vrtk'):
            raise RuntimeError('HX07 controller reference/raw read denied: ' + p)
sys.addaudithook(guard)
sys.path.insert(0, str(W/'src'))
from legsa_gins.paper_rebuild.hext import hx02_rtklib as adapter
from legsa_gins.paper_rebuild.hext import hx02_evaluation_process as evaluation
from legsa_gins.paper_rebuild.horizontal_literature.phase3_runner import _parse_rtklib_enu_pos


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_csv(p, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with p.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def verify():
    pins = json.loads((R/'HX07_INPUT_SHA256.json').read_text())
    for p, info in pins.items():
        assert sha(resolve(p)) == info['sha256'], p
    b = json.loads((O/'PREFLIGHT.json').read_text())['baseline']
    assert all(sha(W/p) == h for p,h in b.items()), 'baseline changed'
    source = json.loads((O/'RTKLIB_SOURCE_SHA256.json').read_text())
    assert all(sha(EXT/p) == h for p,h in source.items()), 'RTKLIB source changed'
    return {'input_pins':len(pins),'baseline':len(b),'rtklib_source':len(source)}


def run_native(seq, variant, data, plan):
    run = O/'RUNS'/f'{seq}_{variant}'; run.mkdir(parents=True, exist_ok=False)
    conf = O/f'CONFIGS/{variant}.conf'; pos = run/'solution.pos'
    nav = data['nav_v0'] if variant == 'V0' else [plan['external_nav']]
    argv = [str(resolve(plan['executable'])), '-k',str(conf),'-o',str(pos),'-y','1',
            *data['start_argv'],str(resolve(data['obs'][1])),str(resolve(data['obs'][0])),
            *(str(resolve(p)) for p in nav)]
    command = ['strace','-f','-yy','-s','4096','-e','trace=openat,execve','-o',str(run/'NATIVE_OPENAT.strace'),*argv]
    receipt = {'sequence':seq,'variant':variant,'argv':argv,'start':now(),'config_sha256':sha(conf),
               'executable_sha256':sha(resolve(plan['executable'])),'status':'STARTED'}
    dump(run/'COMMAND.json',receipt)
    env = dict(os.environ, OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    with (run/'stdout.log').open('w') as stdout, (run/'stderr.log').open('w') as stderr:
        result = subprocess.run(command, cwd=run, env=env, stdout=stdout, stderr=stderr, timeout=3600)
    receipt.update(end=now(),returncode=result.returncode,status='FINISHED');dump(run/'COMMAND.json',receipt)
    log = (run/'NATIVE_OPENAT.strace').read_text()
    forbidden = [l for l in log.splitlines() if 'openat(' in l and (PATHS['raw_root'] in l or 'trace_vrtk' in l or '.bag"' in l or '.fpl"' in l)]
    execs = re.findall(r'execve\("([^"]+)"', log)
    writes = [l for l in log.splitlines() if 'openat(' in l and any(x in l for x in ['O_WRONLY','O_RDWR'])]
    # Native input/output paths are absolute; only task-run output writes are allowed.
    outside = [l for l in writes if str(run) not in l and '"/dev/' not in l]
    audit = {'reference_raw_opens':len(forbidden),'execve':execs,'outside_writes':outside,
             'passed':not forbidden and not outside and execs==[str(resolve(plan['executable']))]}
    dump(run/'NATIVE_ACCESS_AUDIT.json',audit)
    assert audit['passed'], audit
    assert result.returncode == 0 and pos.is_file(), receipt
    old = resolve(data['hx02_run'])
    prepared = json.loads((old/'native/RTKLIB_PREPARED.json').read_text())
    rows, summary = adapter.heading_table(prepared, pos, 18)
    table = run/'HEADING_TABLE.csv'
    table_sha = adapter.write_heading_table(rows, table, extra=('rtklib_q',))
    window = [r for r in rows if data['window'][0] <= float(r['time_unix_s'])-data['base_time'] <= data['window'][1]]
    assert len(window) == data['paired_denominator'], (seq,len(window))
    fixed = sum(int(r['valid']) for r in window)
    summary.update(window_paired=len(window), window_q1=fixed,
                   window_q_counts={str(q):sum(int(r['rtklib_q'])==q for r in window) for q in [-1,1,2,5]},
                   heading_table_sha256=table_sha)
    dump(run/'ASSOCIATION_SUMMARY.json',summary)
    print(f'{seq} {variant}: Q1={fixed}/{len(window)}; pos rows={summary["pos_rows"]}',flush=True)
    return run, summary


def evaluate(run, seq, data):
    old_spec = json.loads((resolve(data['hx02_run'])/'eval/HEADING/SPEC.json').read_text())
    table = run/'HEADING_TABLE.csv'
    spec = {k: old_spec[k] for k in ['sequence_id','base_time','window','trace','trace_sha256']}
    spec.update(method_id='RTKLIB',variants=[{'label':'RTKLIB','heading_table':str(table),'heading_table_sha256':sha(table)}])
    receipt = evaluation.run_child('HEADING', spec, workdir=run/'eval',code_root=W,
                                  raw_root=Path(PATHS['raw_root']),clean_root=C,trace=Path(spec['trace']))
    return receipt


def main():
    assert not (O/'EXECUTION_STARTED.json').exists(), 'one-shot execution already started'
    assert not S.exists(), 'scratch already exists'
    verified = verify()
    head = subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD'],text=True).strip()
    reg = json.loads((O/'REGISTRATION_RECEIPT.json').read_text())
    assert head == reg['commit'] and reg['push_returncode']==0, 'registration not pushed'
    dump(O/'EXECUTION_STARTED.json',{'time':now(),'head':head,'verified':verified})
    plan = json.loads((O/'PLAN.json').read_text()); gates=[]; runs=[]
    # An immediate failed V0 stops every later run and all reference evaluations.
    for variant in ['V0','V1','V2']:
        for seq,data in plan['sequences'].items():
            # PLAN JSON is sorted; use explicit sequence order below in registration.
            if seq not in ['BY2','BY2H','BY2O']:
                raise RuntimeError(seq)
            run, summary = run_native(seq,variant,data,plan);runs.append((run,seq,data))
            if variant == 'V0':
                actual=summary['window_q1'];expected=data['expected_v0_fixed']
                gate={'sequence':seq,'expected':expected,'observed':actual,'difference':actual-expected,
                      'tolerance_epochs':2,'passed':abs(actual-expected)<=2}
                gates.append(gate);dump(O/'V0_GATE.json',gates)
                if not gate['passed']:
                    stop={'status':'HARD_STOP_V0_REPRODUCTION','time':now(),'gate':gate,
                          'rnx2rtkp_calls':len(runs),'heading_evaluator_calls':0,'reference_opens':0,
                          'LegSA_solver_calls':0,'LegSA_evaluator_calls':0,'other_external_calls':0}
                    dump(O/'HARD_STOP.json',stop)
                    print(json.dumps(stop,ensure_ascii=False),flush=True)
                    return 2
        if variant == 'V0':
            for run,seq,data in runs:
                evaluate(run,seq,data)
        else:
            for run,seq,data in runs[-3:]:
                evaluate(run,seq,data)
    dump(O/'EXECUTION_DONE.json',{'time':now(),'native_calls':len(runs),'heading_evaluator_calls':len(runs),'verified':verify()})
    return 0


if __name__ == '__main__':
    sys.exit(main())
