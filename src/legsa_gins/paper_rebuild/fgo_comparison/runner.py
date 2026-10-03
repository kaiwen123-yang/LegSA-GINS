"""Bounded FGO native runner. References are denied inside this process."""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import yaml

from .raw_inputs import aliases, dump, portable, sha256

METHODS = {'GNC':'GNC_2022.json', 'WEN_TC':'WEN_TC_2021.json', 'OISAM':'OISAM_2025.json'}


def json_safe(value):
    if isinstance(value, dict): return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)): return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray): return json_safe(value.tolist())
    if isinstance(value, np.generic): return json_safe(value.item())
    if isinstance(value,float) and not np.isfinite(value): return None
    return value


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n')
        w.writeheader(); w.writerows(rows)


def hardware():
    cpu=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),platform.processor())
    return {'cpu':cpu,'logical_cpus':os.cpu_count(),'platform':platform.platform(),
            'python':platform.python_version(),'numpy':np.__version__,
            'threads':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']}}


def deny_reference_access(roots):
    """Audit hook rejects source trace payloads, not trace-named source code."""
    contract=yaml.safe_load((Path(roots['<CODE_ROOT>'])/'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml').read_text())
    denied=[]
    def visit(obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k in ('trace','trace_path') and isinstance(v,dict): v=v.get('path','')
                if k in ('trace','trace_path') and isinstance(v,str):
                    for alias,root in roots.items(): v=v.replace(alias,root)
                    denied.append(str(Path(v).absolute()))
                visit(v)
        elif isinstance(obj,list):
            for item in obj: visit(item)
    visit(contract)
    def hook(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=str(Path(os.fsdecode(args[0])).absolute())
            if p in denied or (p.startswith(roots['<RAW_ROOT>']+'/') and 'trace' in Path(p).name.lower()):
                raise PermissionError('Reference payload is evaluation-only')
    sys.addaudithook(hook)
    return len(denied)


def write_states(out, times, result):
    position=np.asarray(result['position_ecef_m']); n=len(times)
    velocity=np.asarray(result.get('velocity_ecef_mps',np.full((n,3),np.nan)))
    fields=['time_rel_s','x_ecef_m','y_ecef_m','z_ecef_m','vx_ecef_mps','vy_ecef_mps','vz_ecef_mps','valid','status']
    rows=[]
    for k,t in enumerate(times):
        values=[float(t),*position[k],*velocity[k],int(result['valid'][k]),str(result['status'][k])]
        rows.append(dict(zip(fields,values)))
    write_csv(out/'STATES.csv',rows,fields)


def _run_native(roots_path, sequence, method, attempt):
    roots=aliases(roots_path); code=Path(roots['<CODE_ROOT>'])
    denied=deny_reference_access(roots)
    configpath=code/'configs/paper_rebuild/fgo_comparison'/METHODS[method]
    config=json.loads(configpath.read_text())
    names={'GNC':['gnc.py'],'WEN_TC':['wen_tc.py','wen_ahrs.py'],'OISAM':['oisam.py','oisam_inputs.py','ceres_relinearize.py','wen_ahrs.py','wen_tc.py']}[method]
    sources=[code/'src/legsa_gins/paper_rebuild/fgo_comparison'/name for name in ['__init__.py','raw_inputs.py','runner.py',*names]]
    sources=[p for p in sources if p.exists()]
    source_hashes={str(p.relative_to(code)):sha256(p) for p in sources}
    code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=code,text=True).strip()
    config_hash=sha256(configpath)
    out=Path(roots['<FGO_ROOT>'])/'runs'/sequence/method/attempt
    out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    provenance={}
    if method=='OISAM':
        from .oisam_inputs import run_sequence
        result=run_sequence(roots_path,sequence,out,configpath)
        provenance=result
        status=result.get('terminal_status','RECORDED_IN_METHOD_MANIFEST')
    else:
        inp=Path(roots['<FGO_ROOT>'])/'inputs'/sequence
        manifest=json.loads((inp/'INPUT_MANIFEST.json').read_text())
        if manifest['sequence']!=sequence or manifest['data_mode']!='real_raw_reuse': raise ValueError('Raw input scope mismatch')
        forbidden=['synthetic_data_used','semisynthetic_data_used','trace_used_online','receiver_imu_as_body_imu',
                   'final_v23_output_solver_input','LegSA_output_solver_input','per_case_tuning','output_only_correction','epoch_deleted_for_metric']
        if any(manifest[k] is not False for k in forbidden) or manifest['old_runtime_input_count']!=0: raise ValueError('Forbidden input provenance')
        if sha256(inp/'RAW_INPUT.npz')!=manifest['input_sha256']: raise ValueError('Raw graph input identity changed')
        with np.load(inp/'RAW_INPUT.npz',allow_pickle=False) as archive:
            data={k:archive[k] for k in archive.files}
        provenance={k:manifest[k] for k in ['raw_source_hashes','provider_hashes','navigation_hashes','input_sha256','base_time','window_seconds']}
        provenance.update(input_manifest_sha256=sha256(inp/'INPUT_MANIFEST.json'),
                          **{k:manifest[k] for k in ['epoch_count','expected_window_one_hz_slots','missing_one_hz_slots']})
        if method=='GNC':
            from .gnc import solve
            result=solve(data,config)
            np.savez_compressed(out/'WEIGHTS.npz',epoch_index=data['epoch_index'],system=data['system'],
                                weights=result['weights'],residuals=result['residuals'],residuals_m=result['residuals_m'])
            history=result.pop('weight_history')
            arrays={f'{i}_{key}':row[key] for i,row in enumerate(history) for key in ('observation_indices','weights')}
            np.savez_compressed(out/'WEIGHT_HISTORY.npz',**arrays)
            dump(out/'WEIGHT_HISTORY_INDEX.json',json_safe([{k:v for k,v in row.items() if k not in ('observation_indices','weights')} for row in history]))
        else:
            from .wen_ahrs import prepare_ahrs
            from .wen_tc import solve
            ahrs=prepare_ahrs(roots_path,sequence,data['time_rel_s'],config)
            data['pr_sigma_m']=data['pr_sigma_wen_m']
            result=solve(data,ahrs,config)
            dump(out/'AHRS_PROVENANCE.json',json_safe({k:v for k,v in ahrs.items() if not isinstance(v,np.ndarray)}))
            np.savez_compressed(out/'AHRS_INTERVALS.npz',**{k:v for k,v in ahrs.items() if isinstance(v,np.ndarray)})
            provenance['ahrs']=json_safe({k:v for k,v in ahrs.items() if not isinstance(v,np.ndarray)})
        write_states(out,data['time_rel_s'],result)
        np.savez_compressed(out/'STATE_ARRAYS.npz',**{k:v for k,v in result.items() if isinstance(v,np.ndarray)})
        dump(out/'SOLVER.json',json_safe({k:v for k,v in result.items() if not isinstance(v,np.ndarray)}))
        status=result.get('terminal_status','RECORDED_IN_SOLVER')
    elapsed=time.perf_counter()-started
    if source_hashes!={str(p.relative_to(code)):sha256(p) for p in sources} or sha256(configpath)!=config_hash:
        raise ValueError('Scientific source/config changed during run')
    run={'schema':'fgo_comparison.native.v1','sequence':sequence,'method':method,'attempt':attempt,
         'terminal_status':status,'output_root':portable(out,roots),'data_mode':'real_raw_reuse',
         'synthetic_data_used':False,'semisynthetic_data_used':False,'trace_used_online':False,
         'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,'LegSA_output_solver_input':False,
         'per_case_tuning':False,'output_only_correction':False,'epoch_deleted_for_metric':False,'old_runtime_input_count':0,
         'code_commit':code_commit,'config_hash':config_hash,'config_path':portable(configpath,roots),
         'implementation_source_hashes':source_hashes,
         'solver_and_adapter_elapsed_s':elapsed,'hardware':hardware(),'mode':config.get('solve_mode',config.get('solver_mode')),
         'native_process_count':1,'evaluator_process_count':0,'reference_payload_reads':0,
         'reference_paths_denied':denied,'input_provenance':provenance,
         'output_hashes':{p.name:sha256(p) for p in out.iterdir() if p.is_file()}}
    dump(out/'RUN.json',json_safe(run))
    print(json.dumps({'sequence':sequence,'method':method,'status':status,'seconds':elapsed}),flush=True)
    return run


def run_native(roots_path, sequence, method, attempt):
    roots=aliases(roots_path)
    out=Path(roots['<FGO_ROOT>'])/'runs'/sequence/method/attempt
    if out.exists(): raise FileExistsError('Preserve existing attempt: '+str(out))
    started=time.perf_counter()
    try:
        return _run_native(roots_path,sequence,method,attempt)
    except Exception as error:
        out.mkdir(parents=True,exist_ok=True)
        contract=yaml.safe_load((Path(roots['<CODE_ROOT>'])/'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml').read_text())['sequences'][sequence]
        cfg=Path(roots['<CODE_ROOT>'])/'configs/paper_rebuild/fgo_comparison'/METHODS[method]
        failure={'sequence':sequence,'method':method,'attempt':attempt,'terminal_status':'FAILED_EXCEPTION',
                 'failure_type':type(error).__name__,'failure_message':str(error),
                 'window_seconds':contract['window_seconds'],'base_time':contract['base_time'],
                 'expected_window_epochs':int(contract['window_seconds'][1]-contract['window_seconds'][0])+1,
                 'solver_and_adapter_elapsed_s':time.perf_counter()-started,'hardware':hardware(),
                 'data_mode':'real_raw_reuse','synthetic_data_used':False,'semisynthetic_data_used':False,
                 'trace_used_online':False,'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,
                 'LegSA_output_solver_input':False,'per_case_tuning':False,'output_only_correction':False,
                 'epoch_deleted_for_metric':False,'old_runtime_input_count':0,'native_process_count':1,
                 'evaluator_process_count':0,'reference_payload_reads':0,'config_hash':sha256(cfg),
                 'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=roots['<CODE_ROOT>'],text=True).strip()}
        dump(out/'RUN.json',failure)
        (out/'EXCEPTION.log').write_text(traceback.format_exc())
        raise


def summarize_runs(roots_path):
    """Small exact-run ledger and access receipts, reusing the existing parser."""
    from ..clean5_sequence.io_audit import audited_open_records
    roots=aliases(roots_path);root=Path(roots['<FGO_ROOT>']);code=Path(roots['<CODE_ROOT>'])
    final_attempts=json.loads(Path(roots_path).read_text()).get('final_attempts',{m:'MAIN' for m in METHODS})
    rows=[]
    for sequence in ('BY2','BY2H','BY2O'):
        for method in METHODS:
            parent=root/'runs'/sequence/method
            for path in sorted(parent.glob('*/RUN.json')):
                run=json.loads(path.read_text());out=path.parent;attempt=out.name
                states=list(csv.DictReader((out/'STATES.csv').open())) if (out/'STATES.csv').exists() else []
                good=[r for r in states if float(r['valid'])>0 and all(np.isfinite(float(r[k])) for k in ['x_ecef_m','y_ecef_m','z_ecef_m'])]
                log=root/'logs'/f'{method}_{sequence}_{attempt}_OPENAT.strace'
                records=audited_open_records(log,code)
                reference=[r for r in records if r['path'].startswith(roots['<RAW_ROOT>']+'/') and 'trace' in Path(r['path']).name.lower()]
                receipt={'reference_payload_opens':len(reference),'reference_open_records':reference,
                         'openat_log_sha256':sha256(log),'record_count':len(records),'passed':not reference}
                dump(out/'ACCESS.json',receipt)
                if reference: raise ValueError('Unexpected online reference access')
                rows.append({'sequence_id':sequence,'method_id':method,'attempt':attempt,'status':run['terminal_status'],
                             'publication_role':'FINAL' if attempt==final_attempts[method] else 'SUPERSEDED_INITIAL_VELOCITY_POINT_BUG',
                             'total_scheduled_rows':len(states),'total_finite_position_rows':len(good),
                             'first_finite_time_s':good[0]['time_rel_s'] if good else None,
                             'last_finite_time_s':good[-1]['time_rel_s'] if good else None,
                             'solver_and_adapter_elapsed_s':run['solver_and_adapter_elapsed_s'],
                             'native_reference_opens':0,'code_commit':run['code_commit'],'config_hash':run['config_hash'],
                             'cpu':run['hardware']['cpu'],'threads':run['hardware']['threads'].get('OMP_NUM_THREADS'),
                             'solve_mode':run.get('mode'),'run_path':portable(path,roots),'run_manifest_sha256':sha256(path),
                             'states_sha256':sha256(out/'STATES.csv') if states else None,
                             'access_receipt_sha256':sha256(out/'ACCESS.json')})
    write_csv(Path(roots['<FGO_DOCS>'])/'RUNS.csv',rows)
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',required=True);p.add_argument('--sequence',choices=['BY2','BY2H','BY2O'],required=True)
    p.add_argument('--method',choices=METHODS,required=True);p.add_argument('--attempt',default='MAIN')
    args=p.parse_args();run_native(args.roots,args.sequence,args.method,args.attempt)


if __name__=='__main__': main()
