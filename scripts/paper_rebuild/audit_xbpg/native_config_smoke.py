#!/usr/bin/env python3
"""Exercise the real config/file-reader/runtime route using synthetic fixtures.

These two software fixtures test module dispatch, not accuracy, tuning, or any
new real-data fault matrix. Configs retain explicit synthetic provenance.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
import yaml
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--local-config',type=Path,required=True);parser.add_argument('--frozen-binary',type=Path,required=True);parser.add_argument('--expected-sha256',required=True);args=parser.parse_args()
    if sha(args.frozen_binary)!=args.expected_sha256:raise SystemExit('frozen binary mismatch')
    p=yaml.safe_load(args.local_config.read_text())['paths'];scratch=Path(p['audit_scratch'])/'native_config_smoke';scratch.mkdir(parents=True,exist_ok=False)
    output=Path(p['audit_root'])/'native/native_config_smoke';output.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');calls=[];summaries=[]
    imu=scratch/'fixture.imu';lat=math.radians(28);dt=.01;omega=7.292115e-5
    imu.write_text(''.join(f'{1000+k*dt:.9f} {omega*math.cos(lat)*dt:.17g} 0 {-omega*math.sin(lat)*dt:.17g} 0 0 -0.098\n' for k in range(101)))
    times=[1000+k*.1 for k in range(11)]
    rd=scratch/'rd.csv';rp=scratch/'rp.csv';hv=scratch/'hv.csv'
    rd.write_text('time,vn,ve,vd,std_vn,std_ve,std_vd,sat_count,gdop_like,provider_status,quality\n'+''.join(f'{t:.9f},0,0,0,1,1,1,8,1,available,nominal\n' for t in times))
    rp.write_text('time,roll_rad,pitch_rad,std_roll_rad,std_pitch_rad,source_status,quality_flag\n'+''.join(f'{t:.9f},0,0,0.1,0.1,active,nominal\n' for t in times))
    hv.write_text('time,vn,ve,vd,std_vn,std_ve,std_vd,source_status,quality_flag,update_flag,diagnostic_only,go2_velocity_truth_claim,prior_policy\n'+''.join(f'{t:.9f},0,0,0,2,2,999,active,nominal,true,false,false,horizontal\n' for t in times))
    binaries={'current':Path(p['audit_scratch'])/'native_build/legsa_v23_port_core_demo','frozen':args.frozen_binary}
    for label,validity in [('all_channels',1),('all_gnss_invalid_aux_available',0)]:
        gnss=scratch/(label+'.gnss');gnss.write_text(''.join(f'{t:.9f} 28 114 20 1 1 1 0 0 0 1 1 1 0 1 {validity} {validity} {validity}\n' for t in times))
        config=scratch/(label+'.yaml')
        values=dict(data_mode='synthetic',synthetic_data_used='true',semisynthetic_data_used='false',clean1_formal_mode='false',clean_final_v23_parity_mode='true',algorithm_id='LegSA_Paper_V1',starttime='1000',endtime='1001',initpos='[28,114,20]',initvel='[0,0,0]',initatt='[0,0,0]',antlever='[0,0,0]',imupath=imu,gnsspath=gnss,enable_dual_yaw='true',enable_receiver_velocity='true',enable_raw_doppler='true',raw_doppler_factor_path=rd,enable_source_aware='true',source_aware_mode='lsim_oim',source_aware_trace_enabled='true',enable_go2_roll_pitch_prior='true',go2_attitude_prior_path=rp,enable_go2_horizontal_velocity_prior='true',go2_horizontal_velocity_prior_path=hv)
        config.write_text(''.join(f'{k}: {v}\n' for k,v in values.items()))
        for version,binary in binaries.items():
            directory=scratch/(label+'_'+version);command=[str(binary),'--config',str(config),'--output-dir',str(directory),'--debug-update-timeline'];t=time.perf_counter()
            try:
                r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=30);row=dict(label=label,version=version,command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
            except subprocess.TimeoutExpired as e:row=dict(label=label,version=version,command=command,returncode=None,status='TIMEOUT',stdout=str(e.stdout or ''),stderr=str(e.stderr or ''))
            row['elapsed_seconds']=time.perf_counter()-t;calls.append(row);(output/'CALLS.json').write_text(json.dumps(calls,indent=2)+'\n');print(label,version,row['returncode'],flush=True)
            summary=dict(label=label,version=version,returncode=row['returncode'],config_sha256=sha(config),binary_sha256=sha(binary))
            manifest=directory/'RUN_MANIFEST.json'
            if manifest.exists():
                m=json.loads(manifest.read_text());summary['manifest']={k:m.get(k) for k in ['data_mode','synthetic_data_used','semisynthetic_data_used','propagation_count','measurement_update_count','position_update_count','receiver_velocity_update_count','dual_yaw_update_count','raw_doppler_update_count','go2_roll_pitch_update_count','go2_horizontal_velocity_update_count','source_aware_evaluation_count','cov_health_status']}
            nav=directory/'EVAL_NAV.csv'
            if nav.exists():
                with nav.open() as f:rows=list(csv.DictReader(f))
                summary.update(output_rows=len(rows),finite_rows=sum(all(math.isfinite(float(v)) for v in x.values()) for x in rows),first_output_time=rows[0]['time'] if rows else None,last_output_time=rows[-1]['time'] if rows else None)
            summaries.append(summary)
    result=dict(data_mode='synthetic',synthetic_data_used=True,semisynthetic_data_used=False,post_hoc=True,real_data_open_count=0,reference_open_count=0,purpose='real config/file-loader/runtime integration and scheduling; not accuracy',summaries=summaries,calls=calls,comparisons=[])
    for label in ['all_channels','all_gnss_invalid_aux_available']:
        for name in ['LegSA_PORT_NAV.nav','LegSA_PORT_STD.csv','EVAL_NAV.csv']:
            a=scratch/(label+'_current')/name;b=scratch/(label+'_frozen')/name
            result['comparisons'].append(dict(label=label,file=name,byte_identical=a.exists() and b.exists() and a.read_bytes()==b.read_bytes()))
    (output/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
    for row in result['calls']:row.pop('command',None)
    (ROOT/'docs/paper_rebuild/audit_xbpg_20261001/NATIVE_CONFIG_SMOKE.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
