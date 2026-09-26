"""Explicit HX-02E gates on synthetic inputs; never opens a reference trajectory.

Run this file with --driver, --config-dir and --scratch to execute the four gates.
No real-data execution is initiated by pytest collection.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

import numpy as np


def synthetic_cache(path, duration, omega):
    dt = 0.004
    count = int(round(duration / dt)) + 1
    first = 1_000_000_000
    last = first + (count-1)*4_000_000
    header = struct.pack('<16sIIIIQqq32s32s32s104x', b'LEGS_H5_CACHE', 1, 256, 192, count,
                         0, first, last, bytes(32), bytes(32), bytes(32))
    feet = np.array([[0.2,0.15,-0.3],[0.2,-0.15,-0.3],[-0.2,0.15,-0.3],[-0.2,-0.15,-0.3]])
    with path.open('xb') as f:
        f.write(header)
        for i in range(count):
            angle = omega*i*dt
            c, s = np.cos(angle), np.sin(angle)
            rotation = np.array([[c,-s,0],[s,c,0],[0,0,1]])
            body_feet = feet @ rotation
            vals = [0,0,omega,0,0,9.81,50,50,50,50,*body_feet.ravel()]
            f.write(struct.pack('<q22dBBBB4x', first+i*4_000_000,*vals,15,15 if i==0 else 0,0,0))
    return count


def execute_gates(driver, config_dir, scratch):
    scratch.mkdir(exist_ok=False)
    results = []
    for cfg in ['OFF-LIT','OFF-DEF']:
        for name, duration, omega in [('STATIC',300.0,0.0),('YAW',60.0,0.1)]:
            run = scratch / f'{cfg}_{name}'
            run.mkdir()
            cache = run / 'INPUT.bin'
            count = synthetic_cache(cache, duration, omega)
            nav = run / 'NAV.csv'
            log = run / 'OPENAT.strace'
            argv = ['strace','-f','-yy','-s','4096','-e','trace=openat,execve','-o',str(log),str(driver),
                    str(cache),str(config_dir / f'{cfg}.cfg'),str(nav)]
            with (run / 'stdout.log').open('x') as out, (run / 'stderr.log').open('x') as err:
                done = subprocess.run(argv, stdout=out, stderr=err, env={**os.environ,'OMP_NUM_THREADS':'1'},timeout=600)
            result = {'configuration':cfg,'case':name,'duration_s':duration,'angular_rate_rad_s':omega,
                      'expected_rows':count,'exit_code':done.returncode,'argv':argv,'synthetic_input':True}
            if done.returncode == 0:
                data = np.loadtxt(nav,delimiter=',',skiprows=1,usecols=(0,14,15,16,19),ndmin=2)
                t=(data[:,0]-data[0,0])*1e-9
                yaw=np.degrees(np.unwrap(np.radians(data[:,4])))
                yaw-=yaw[0]
                err=yaw-np.degrees(omega*t)
                result.update(output_rows=len(data),position_max_norm_m=float(np.linalg.norm(data[:,1:4],axis=1).max()),
                              yaw_integral_max_abs_difference_deg=float(np.abs(err).max()),
                              nav_sha256=hashlib.sha256(nav.read_bytes()).hexdigest(),
                              input_sha256=hashlib.sha256(cache.read_bytes()).hexdigest())
                result['passed']=bool(len(data)==count and np.isfinite(data).all() and np.abs(err).max()<0.1
                                      and (name!='STATIC' or result['position_max_norm_m']<0.05))
            else:
                result['passed']=False
            (run / 'GATE.json').write_text(json.dumps(result,indent=2)+'\n')
            results.append(result)
            (scratch / 'GATES.json').write_text(json.dumps(results,indent=2)+'\n')
            print(cfg,name,'PASS' if result['passed'] else 'HARD_STOP',flush=True)
            if not result['passed']:
                raise RuntimeError('HX-02E driver gate failed: stop without repair or retry')
    return results


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--driver',type=Path,required=True)
    p.add_argument('--config-dir',type=Path,required=True)
    p.add_argument('--scratch',type=Path,required=True)
    a=p.parse_args()
    execute_gates(a.driver,a.config_dir,a.scratch)
