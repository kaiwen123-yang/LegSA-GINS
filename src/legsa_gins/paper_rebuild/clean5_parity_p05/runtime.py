"""Nine preregistered noise cells, with unchanged non-grid bytes."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import time
import yaml
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from ..clean5_sequence.runtime_config import frozen_parameter_hash, NATIVE_IDENTITY
from ..clean5_sequence.solver_runner import audit_solver_openat
from ..clean5_sequence.solver_validation import validate_run_outputs
from ..clean5_parity.runtime import (bind_config, expected_counts, check_counters, diagnostic_counts,
                                     EXE_SHA, resolve, write_json)


GRID=[(a,v) for a in (77.8,778.,7780.) for v in (.077,.77,7.7)]

def grid_cells(contract):
    cells=contract['p05']['cells']
    if [(c['abstd_mGal'],c['vrw_mps_sqrt_hour']) for c in cells]!=GRID or len({c['cell_id'] for c in cells})!=9:
        raise ValueError('Exact nine-cell preregistered grid required')
    return cells

def verify_bundle(bundle):
    inputs=bundle['variants']['V2is']['providers']
    if set(inputs)!={'imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path'}:
        raise ValueError('Input roles differ')
    for entry in inputs.values():
        path=Path(entry['path'])
        if path.is_symlink() or sha256_file(path)!=entry['sha256']:raise ValueError('Provider hash mismatch')

def patch_noise(bound, abstd, vrw):
    if (abstd,vrw) not in GRID:raise ValueError('Unregistered noise cell')
    original_lines=bound.splitlines(keepends=True);lines=list(original_lines);changes=[]
    for key,value in [('abstd',abstd),('vrw',vrw)]:
        indices=[i for i,line in enumerate(lines) if line.startswith(key+':')]
        if len(indices)!=1:raise ValueError('Missing/duplicate noise field '+key)
        i=indices[0];old=lines[i];token=format(value,'.12g')
        lines[i]=key+': ['+', '.join([token]*3)+']'+('\n' if old.endswith('\n') else '')
        changes.append({'key':key,'line_index':i,'before':old,'after':lines[i]})
    actual=''.join(lines);restored=list(lines)
    for c in changes:restored[c['line_index']]=c['before']
    restored=''.join(restored)
    if restored!=bound:raise ValueError('Non-grid parameter bytes changed')
    original=yaml.safe_load(bound);parsed=yaml.safe_load(actual)
    if any(parsed[k]!=original[k] for k in original if k not in ('abstd','vrw')):raise ValueError('Non-grid value changed')
    return actual,{'noise_parameter_byte_diff':changes,'non_grid_parameter_hash':frozen_parameter_hash(restored),
        'non_grid_bytes_equal':True,'actual_parameter_hash':frozen_parameter_hash(actual),
        'abstd_mGal':abstd,'vrw_mps_sqrt_hour':vrw,'classification':'SENSITIVITY_NOT_FROZEN',
        'explicit_noise_sensitivity':True,'parameter_sweep':True,'frozen_parameter_contract':False,'parameter_selection_used':False,'no_best_selection':True,'no_feedback':True,'no_adoption':True,
        'initbastd_unchanged':parsed['initbastd']==original['initbastd'],'arw_unchanged':parsed['arw']==original['arw'],
        'gbstd_unchanged':parsed['gbstd']==original['gbstd']}

def run_ladder(*,registry,stage_root,contract,provider_bundle,executable,code_commit):
    order=grid_cells(contract);verify_bundle(provider_bundle)
    dataset="BY2"
    spec=contract['p05']
    stage_root=Path(stage_root);executable=Path(executable)
    if executable.is_symlink() or sha256_file(executable)!=EXE_SHA:raise ValueError('Frozen executable mismatch')
    runs_root=stage_root/'03_PARITY_RUNS';seal_root=stage_root/'04_PARITY_SEAL'
    runs_root.mkdir(exist_ok=False);seal_root.mkdir(exist_ok=False);records=[]
    for cell in order:
        variant=cell['cell_id'];method='A04'
        run_id=f'CLEAN5_PARITY_P05_{variant}_A04'
        root=runs_root/run_id;root.mkdir()
        source=spec['source_config']
        source_path=resolve(source['runtime_config'],registry)
        if sha256_file(source_path)!=source['runtime_config_sha256']: raise RuntimeError('frozen config changed')
        inputs=provider_bundle['variants']['V2is']['providers']
        replacements={key:str(value['path'] if isinstance(value,dict) else value) for key,value in inputs.items()}
        replacements.update(NATIVE_IDENTITY,outputpath=str(root),run_id=run_id,run_label=run_id)
        bound,diff=bind_config(source_path.read_text(),replacements)
        text,noise_audit=patch_noise(bound,cell['abstd_mGal'],cell['vrw_mps_sqrt_hour']);cfg=yaml.safe_load(text)
        (root/'PARITY_RUNTIME_CONFIG.yaml').write_text(text)
        expected=expected_counts(cfg)
        record={'variant_id':variant,'provider_family':'CLEAN5_PARITY_P05_'+variant,'method_id':method,'run_id':run_id,'terminal_status':'NOT_STARTED',
                'effective_profile':{'F01':'single_antenna_EKF','F03':'AB0000','A04':'AB1011'}[method],
                'effective_configuration_id':{'F01':'single_antenna_EKF','F03':'AB0000','A04':'AB1011'}[method],
                'output_root':str(root),'dataset_id':dataset,'case_id':'C00_clean_normal','data_mode':registry.sequences[dataset].data_mode,
                'code_commit':code_commit,'config_hash':hashlib.sha256(text.encode()).hexdigest(),
                'frozen_parameter_hash':frozen_parameter_hash(text),'reference_frozen_parameter_hash':frozen_parameter_hash(source_path.read_text()),
                'parameter_byte_diff':diff,'expected_counters':expected,'native_identity':{k:cfg[k] for k in NATIVE_IDENTITY},
                'provider_hashes':{k:sha256_file(Path(cfg[k])) for k in inputs},
                'raw_source_hashes':provider_bundle.get('raw_source_hashes',{}),
                'executable_sha256':EXE_SHA,'synthetic_data_used':False,'semisynthetic_data_used':False,
                'trace_used_online':False,'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,
                'LegSA_output_solver_input':False,'per_case_tuning':False,'output_only_correction':False,
                'epoch_deleted_for_metric':False,'old_runtime_input_count':0,'retry_count':0}
        log=root/'SOLVER_OPENAT.strace'
        command=[shutil.which('strace') or 'strace','-f','-qq','-yy','-s','4096','-e','trace=openat','-o',str(log),
                 str(executable),'--config',str(root/'PARITY_RUNTIME_CONFIG.yaml'),'--output-dir',str(root),
                 '--debug-update-timeline','--debug-output-dir',str(root),'--debug-max-rows','1000000']
        record.update(noise_audit,input_variant='V2is')
        record['command']=command
        write_json(root/'RUN_STARTED.json',record)
        started=time.monotonic()
        record.update(launch_attempted=True,process_completion_available=False,exit_code=None)
        phase='SUBPROCESS'
        try:
            result=run_process_group(command,cwd=registry.code_root,timeout_seconds=1800,
                      timeout_message='P05 solver timeout',launch_failure_message='P05 solver launch failed')
            record.update(exit_code=result.returncode,process_completion_available=True)
            phase='PROCESS_LOG_WRITE'
            (root/'stdout.log').write_text(result.stdout);(root/'stderr.log').write_text(result.stderr)
            phase='STRACE_AUDIT'
            record['strace_audit']=audit_solver_openat(log,cwd=registry.code_root,raw_root=registry.raw_root,run_dir=root,clean_root=registry.clean_root)
            record['terminal_status']='COMPLETED' if result.returncode==0 else 'FAILED_NATIVE_SOLVER'
            native_path=root/'RUN_MANIFEST.json'
            phase='NATIVE_MANIFEST_AUDIT'
            if native_path.exists():
                native=json.loads(native_path.read_text());record['native_manifest_sha256']=sha256_file(native_path)
                phase='COUNTER_AUDIT'
                record['counter_audit']=check_counters(native,cfg,expected)
                record['counters']=record['counter_audit']['actual']
                if not record['counter_audit']['pass']:record['terminal_status']='FAILED_COUNTER_AUDIT'
            else:
                record['counters']='UNAVAILABLE_NATIVE_MANIFEST_NOT_WRITTEN'
                if record['terminal_status']=='COMPLETED':record['terminal_status']='FAILED_NATIVE_MANIFEST_MISSING'
                phase='DIAGNOSTIC_COUNTER_AUDIT'
                record['diagnostic_trace_counts']=diagnostic_counts(root)
            if not record['strace_audit']['pass']:record['terminal_status']='FAILED_STRACE_AUDIT'
            if record['terminal_status']=='COMPLETED':
                phase='OUTPUT_VALIDATION'
                record.update(validate_run_outputs(root,{'window_contract':{'t_start':spec['window_seconds'][0],'t_end':spec['window_seconds'][1]}}))
                for role,name in [('nav','KF_GINS_Navresult.nav'),('std','KF_GINS_STD.txt')]:
                    record[role+'_path']=str(root/name);record[role+'_sha256']=sha256_file(root/name)
            if record['terminal_status']=='COMPLETED' and cell==order[0] and 'origin_reference' in spec:
                phase='ORIGIN_IDENTITY_GATE'
                import numpy as np
                parity={}
                for role in ['nav','std']:
                    pin=spec['origin_reference'][role];reference=resolve(pin['path'],registry)
                    if sha256_file(reference)!=pin['sha256']:raise ValueError('Origin reference hash changed')
                    actual=Path(record[role+'_path']);a=np.loadtxt(actual);b=np.loadtxt(reference)
                    same=a.shape==b.shape;delta=float(np.max(abs(a-b))) if same else None
                    parity[role]={'byte_equal':sha256_file(actual)==pin['sha256'],'max_abs_delta':delta,'pass':same and delta<=1e-9}
                record['origin_identity_gate']=parity
                if not all(v['pass'] for v in parity.values()):raise ValueError('Origin identity gate failed')
        except Exception as exc:
            record['terminal_status']=f'FAILED_{phase}_EXCEPTION'
            record.setdefault('errors',[]).append({'phase':phase,'exception_type':type(exc).__name__,'message':str(exc)})
        record['runtime_seconds']=time.monotonic()-started
        # Audit each attempted run before advancing. Even failed/partial native runs
        # retain scheduling evidence (or its explicit error) in the immutable seal.
        from ..clean5_parity.scheduling import audit_scheduling
        scheduling_root=seal_root/'SCHEDULING'
        try:
            record['auxiliary_scheduling_audit']=audit_scheduling(config=cfg,
                output_root=scheduling_root/run_id,native_trace=root/'PORT_GNSS_UPDATE_TRACE.csv')
            if record['terminal_status']=='COMPLETED' and record['auxiliary_scheduling_audit'].get('status')!='SCHEDULING_AUDIT_COMPLETE':
                record['terminal_status']='FAILED_SCHEDULING_AUDIT_UNAVAILABLE'
        except Exception as exc:
            record.setdefault('errors',[]).append({'phase':'SCHEDULING_AUDIT','exception_type':type(exc).__name__,'message':str(exc)})
            record['auxiliary_scheduling_audit']={'status':'FAILED_EXCEPTION','pass':False}
            if record['terminal_status']=='COMPLETED':record['terminal_status']='FAILED_SCHEDULING_AUDIT_EXCEPTION'
        write_json(root/'PARITY_RUN_MANIFEST.json',record);records.append(record)
        print(f'{run_id}: {record["terminal_status"]} exit={record["exit_code"]}',flush=True)
        if record['terminal_status']!='COMPLETED':break
    scheduling_root=seal_root/'SCHEDULING'
    hashes={str(p.relative_to(stage_root)):sha256_file(p) for parent in (runs_root,scheduling_root)
            for p in parent.rglob('*') if p.is_file()}
    seal={'status':'SEALED','code_commit':code_commit,'run_count':len(records),
          'data_mode':registry.sequences[dataset].data_mode,'synthetic_data_used':False,'semisynthetic_data_used':False,
          'completed_count':sum(r['terminal_status']=='COMPLETED' for r in records),
          'files_sha256':hashes,'records':records,'all_native_success':all(r['terminal_status']=='COMPLETED' for r in records)}
    write_json(seal_root/'PARITY_OUTPUT_SEAL.json',seal)
    return records
