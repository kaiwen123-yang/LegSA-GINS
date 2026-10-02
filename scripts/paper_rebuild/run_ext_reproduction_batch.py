#!/usr/bin/env python3
"""Launch exactly the three registered methods for one sequence, with receipts.

This has no resume, deletion, parameter selection, or historical controller.
Each child retains one complete raw history and its own output directory.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',required=True)
    p.add_argument('--config',required=True);p.add_argument('--sequence',required=True,choices=['BY2','BY2H','BY2O'])
    a=p.parse_args();roots=json.loads(Path(a.roots).read_text())['aliases']
    dest=Path(roots['<EXT_REPRO_ROOT>'])/'batches'/a.sequence;dest.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,PYTHONPATH=str(Path(roots['<CODE_ROOT>'])/'src'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    jobs=[]
    for method in ('EXT01','EXT02','EXT03'):
        trace=dest/(method+'.openat');log=(dest/(method+'.log')).open('xb')
        command=['strace','-f','-qq','-e','trace=openat','-o',str(trace),sys.executable,'-m',
                 'legsa_gins.paper_rebuild.horizontal_literature.reproduction_runner',
                 '--roots',str(Path(a.roots).resolve()),'--config',str(Path(a.config).resolve()),
                 '--sequence',a.sequence,'--method',method]
        receipt={'method':method,'sequence':a.sequence,'start_unix':time.time(),'status':'STARTING',
                 'command':command,'data_mode':'real_raw','synthetic_data_used':False,'semisynthetic_data_used':False}
        path=dest/(method+'.launch.json');path.write_text(json.dumps(receipt,indent=2)+'\n')
        child=subprocess.Popen(command,env=env,cwd=roots['<CODE_ROOT>'],stdout=log,stderr=subprocess.STDOUT)
        receipt.update(pid=child.pid,status='RUNNING');path.write_text(json.dumps(receipt,indent=2)+'\n')
        jobs.append((child,log,path,receipt))
    while jobs:
        for job in list(jobs):
            child,log,path,receipt=job
            code=child.poll()
            if code is not None:
                log.close();receipt.update(exit_code=code,end_unix=time.time(),status='EXITED')
                path.write_text(json.dumps(receipt,indent=2)+'\n');jobs.remove(job)
                print(json.dumps({k:receipt[k] for k in ('sequence','method','exit_code')}),flush=True)
        if jobs:time.sleep(2)

if __name__=='__main__':main()
