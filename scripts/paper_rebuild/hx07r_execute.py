#!/usr/bin/env python3
"""One-shot exact controls, bounded variants, frozen heading children; no retries."""
import collections
import itertools
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

from hx07r_prepare import (W,C,H,OLD,O,R,S,EXT,PATHS,SEQS,VARIANTS,EXPECTED,now,sha,dump,
                           alias,resolve,csvwrite,scope_check,verify_pins,progress)
sys.path.insert(0,str(W/'src'))
from legsa_gins.paper_rebuild.hext import hx02_rtklib as adapter
from legsa_gins.paper_rebuild.hext import hx02_evaluation_process as evaluation
from legsa_gins.paper_rebuild.horizontal_literature.phase3_runner import _parse_rtklib_enu_pos
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records, write_scope_audit

COUNTS={'rnx2rtkp':0,'heading_evaluations':0,'reference_opens':0,'LegSA_solver':0,'LegSA_evaluator':0,'other_external':0}
AUDITS=[]


def checkpoint():
    dump(R/'HX07R_EXECUTION_COUNTS.json',{'actual':COUNTS,'budget':{'rnx2rtkp':12,'heading_evaluations':13,'reference_opens':13},'time':now()})
    dump(R/'HX07R_AUDIT.json',{'audits':AUDITS,'passed':all(a['passed'] for a in AUDITS),'time':now()})


def native_audit(run,executable):
    logfile=run/'NATIVE_OPENAT.strace';records=audited_open_records(logfile,run)
    bad=[r for r in records if (str(r['path']).startswith(PATHS['raw_root']+'/') or
         Path(r['path']).name.startswith('trace_vrtk') or str(r['path']).lower().endswith(('.bag','.fpl')))]
    writes=[r for r in records if any(x in r['flags'] for x in ['O_WRONLY','O_RDWR','O_CREAT','O_TRUNC'])]
    outside=[r for r in writes if not (Path(r['path']).is_relative_to(run) or str(r['path']).startswith('/dev/'))]
    execs=re.findall(r'execve\("([^"]+)"',logfile.read_text())
    audit={'run':run.name,'kind':'native','reference_raw_opens':len(bad),'outside_writes':outside,
           'execve':execs,'passed':not bad and not outside and execs==[str(executable)],'source':alias(logfile)}
    dump(run/'NATIVE_ACCESS_AUDIT.json',audit);AUDITS.append(audit);checkpoint()
    assert audit['passed'],'G4 native access '+run.name


def run_native(seq,v,data,plan):
    run=O/'RUNS'/f'{seq}_{v}';run.mkdir(parents=True,exist_ok=False)
    executable=EXT/'app/consapp/rnx2rtkp/gcc/rnx2rtkp'
    conf=OLD/f'CONFIGS/{"V0" if v in ["V0","V0E"] else v}.conf'
    nav=[resolve(x) for x in data['nav']] if v=='V0' else [resolve(plan['BRDC'])]
    obs=[resolve(x) for x in data['obs']];pos=run/'solution.pos'
    argv=[str(executable),'-k',str(conf),'-o',str(pos),'-y','2',*data['ts'],str(obs[1]),str(obs[0]),*(str(p) for p in nav)]
    receipt={'sequence':seq,'variant':v,'argv':argv,'original_argv':data['original_argv'],'start':now(),
             'input_sha256':{alias(p):sha(p) for p in [executable,conf,*obs,*nav]},'status':'STARTED',
             'data_mode':'recorded_raw_gnss','synthetic_data_used':False,'semisynthetic_data_used':False}
    dump(run/'COMMAND.json',receipt)
    command=['strace','-f','-yy','-s','4096','-e','trace=openat,execve','-o',str(run/'NATIVE_OPENAT.strace'),*argv]
    env=dict(os.environ)
    for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS']:
        env[key]='1'
    receipt['thread_environment']={k:env[k] for k in env if k.endswith('NUM_THREADS') or k=='VECLIB_MAXIMUM_THREADS'}
    COUNTS['rnx2rtkp']+=1;checkpoint()
    with (run/'stdout.log').open('w') as stdout,(run/'stderr.log').open('w') as stderr:
        proc=subprocess.Popen(command,cwd=run,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:rc=proc.wait(timeout=3600)
        except BaseException:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            receipt.update(end=now(),status='INTERRUPTED');dump(run/'COMMAND.json',receipt)
            raise
    receipt.update(end=now(),returncode=rc,status='FINISHED');dump(run/'COMMAND.json',receipt)
    native_audit(run,executable)
    if rc or not pos.is_file():
        unavailable={'sequence':seq,'variant':v,'status':'NOT_AVAILABLE','returncode':rc,'pos_exists':pos.exists(),
                     'stderr_tail_40':(run/'stderr.log').read_text().splitlines()[-40:]}
        dump(run/'NOT_AVAILABLE.json',unavailable)
        assert v!='V0','G2 V0 native execution failure'
        return run,None
    prepared=json.loads((resolve(data['old_run'])/'native/RTKLIB_PREPARED.json').read_text())
    rows,summary=adapter.heading_table(prepared,pos,18)
    table=run/'HEADING_TABLE.csv';summary['heading_table_sha256']=adapter.write_heading_table(rows,table,extra=('rtklib_q',))
    window=[r for r in rows if data['window'][0]<=float(r['time_unix_s'])-data['base_time']<=data['window'][1]]
    assert len(window)==data['expected'][0],'G2 paired denominator'
    summary['window_paired']=len(window);summary['window_q1']=sum(int(r['valid']) for r in window)
    summary['window_q_counts']={str(q):sum(int(r['rtklib_q'])==q for r in window) for q in [-1,1,2,5]}
    dump(run/'ASSOCIATION_SUMMARY.json',summary)
    progress(f'{seq}/{v} native rc={rc}; Q1={summary["window_q1"]}/{len(window)}; .pos={summary["pos_rows"]}')
    return run,summary


def g2b(run,data):
    old=resolve(data['old_run'])/'native/RTKLIB_UNMODIFIED_MOVING_BASE.pos'
    def lines(p):return [l for l in p.read_text().splitlines() if not l.startswith('%')]
    a,b=lines(old),lines(run/'solution.pos')
    diffs=[{'noncomment_line':i+1,'original':x,'new':y} for i,(x,y) in enumerate(itertools.zip_longest(a,b)) if x!=y]
    def counts(p):return dict(collections.Counter(str(r['quality']) for r in _parse_rtklib_enu_pos(p.read_text())))
    return {'noncomment_original_lines':len(a),'noncomment_new_lines':len(b),'different_lines':len(diffs),
            'first_five':diffs[:5],'original_Q_counts':counts(old),'new_Q_counts':counts(run/'solution.pos'),
            'stop_condition':False}


def evaluate(run,seq,data,heading_table=None):
    old=json.loads((resolve(data['old_run'])/'eval/HEADING/SPEC.json').read_text())
    table=heading_table or run/'HEADING_TABLE.csv'
    spec={k:old[k] for k in ['sequence_id','base_time','window','trace','trace_sha256']}
    spec.update(method_id='RTKLIB',variants=[{'label':'RTKLIB','heading_table':str(table),'heading_table_sha256':sha(table)}])
    COUNTS['heading_evaluations']+=1;checkpoint()
    receipt=evaluation.run_child('HEADING',spec,workdir=run/'eval',code_root=W,
             raw_root=Path(PATHS['raw_root']),clean_root=C,trace=Path(spec['trace']))
    audit=receipt['audit'];COUNTS['reference_opens']+=audit['trace_open_count']
    metrics=json.loads((Path(receipt['outdir'])/'HEADING_METRICS.json').read_text())
    assert metrics['trace_sha256_observed']==spec['trace_sha256'] and metrics['trace_open_count_in_child']==1,'G4 reference identity'
    AUDITS.append({'run':run.name,'kind':'heading_evaluation','passed':audit['passed'],'reference_opens':audit['trace_open_count'],
                   'source':alias(run/'eval/EVALUATOR_STRACE_AUDIT.json')});checkpoint()
    m=metrics['variants']['RTKLIB'];progress(f'{run.name} evaluation: {m["valid_epochs_in_window"]} valid; yaw {m["valid"]["rmse_deg"]}; hold {m["hold_last_valid"]["rmse_deg"]}')
    return m


def execute():
    assert not (O/'EXECUTION_STARTED.json').exists(),'one-shot: EXECUTION_STARTED.json exists'
    assert not (O/'HARD_STOP.json').exists(),'existing hard stop'
    receipt=json.loads((O/'REGISTRATION_RECEIPT.json').read_text())
    from hx07r_prepare import git
    assert receipt['push_returncode']==0 and receipt['remote_head']==receipt['commit']==git('rev-parse','HEAD').strip()
    assert (O/'PROTECTED_METADATA_START.json').is_file(),'G5 no start snapshot'
    verify_pins()
    for p,h in json.loads((O/'SCRIPT_FREEZE.json').read_text()).items():assert sha(resolve(p))==h,'registration code changed'
    dump(O/'EXECUTION_STARTED.json',{'time':now(),'registration_commit':receipt['commit']});checkpoint()
    plan=json.loads((O/'PLAN.json').read_text());gates=[];repro=[];v0=[]
    for seq in SEQS:
        data=plan['sequences'][seq];run,summary=run_native(seq,'V0',data,plan)
        gate={'sequence':seq,'expected':data['expected'][1],'observed':summary['window_q1'],
              'denominator':summary['window_paired'],'passed':summary['window_q1']==data['expected'][1],'G2b':g2b(run,data)}
        gates.append(gate);dump(R/'HX07R_V0_GATE.json',gates)
        assert gate['passed'],'G2 '+json.dumps(gate)
        v0.append((run,seq,data))
    for run,seq,data in v0:
        m=evaluate(run,seq,data);ex=data['expected']
        values={'valid_count':m['valid_epochs_in_window'],'valid_rmse_deg':m['valid']['rmse_deg'],
                'hold_rmse_deg':m['hold_last_valid']['rmse_deg'],'q2_count':m['q2_float']['count'],'q2_rmse_deg':m['q2_float']['errors']['rmse_deg']}
        expected=dict(zip(values,ex[1:]));checks={k:(values[k]==v if k.endswith('count') else abs(values[k]-v)<=1e-5) for k,v in expected.items()}
        item={'sequence':seq,'actual':values,'expected':expected,'checks':checks,'passed':all(checks.values())}
        repro.append(item);dump(R/'HX07R_EVAL_REPRODUCTION.json',repro)
        assert item['passed'],'G3 '+json.dumps(item)
    for v in ['V0E','V1','V2']:
        for seq in SEQS:
            data=plan['sequences'][seq];run,summary=run_native(seq,v,data,plan)
            if summary is not None:evaluate(run,seq,data)
    run=O/'RUNS/BY2_V0convbin';run.mkdir(parents=True,exist_ok=False)
    table=OLD/'RUNS/BY2_V0/HEADING_TABLE.csv'
    expected=json.loads((OLD/'RUNS/BY2_V0/ASSOCIATION_SUMMARY.json').read_text())['heading_table_sha256']
    assert sha(table)==expected,'G1 historical convbin table changed'
    evaluate(run,'BY2',plan['sequences']['BY2'],heading_table=table)
    verify_pins();checkpoint()
    dump(O/'EXECUTION_DONE.json',{'time':now(),'counts':COUNTS,'G2_passed':3,'G3_passed':3})


if __name__=='__main__':
    try:execute()
    except BaseException as exc:
        checkpoint();dump(O/'HARD_STOP.json',{'status':'HARD_STOP_EXECUTION','time':now(),'reason':str(exc),'actual':COUNTS})
        progress('HARD_STOP '+str(exc));raise
