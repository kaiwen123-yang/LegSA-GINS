"""P-03 six-run frozen-binary execution; no retry or prior-run mutation."""
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


def run_order(contract):
    result=[]
    for row in contract['p03']['run_order']:
        result.append((row['variant_id'],row['method_id']) if isinstance(row,dict) else tuple(row))
    expected=[(v,m) for v in ('V2i','V2s','V2is') for m in ('F03','A04')]
    if result!=expected:raise ValueError('P03 requires exactly the six preregistered serial runs')
    return result


def verify_bundle(bundle):
    if set(bundle['variants'])!={'V2i','V2s','V2is'}:raise ValueError('P03 provider variants differ')
    for value in bundle['variants'].values():
        if set(value['providers'])!={'imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path'}:
            raise ValueError('P03 provider path roles differ')
        for entry in value['providers'].values():
            path=Path(entry['path'])
            if path.is_symlink() or sha256_file(path)!=entry['sha256']:raise ValueError('P03 provider hash mismatch')


def run_ladder(*,registry,stage_root,contract,provider_bundle,executable,code_commit):
    order=run_order(contract);verify_bundle(provider_bundle)
    stage_root=Path(stage_root);executable=Path(executable)
    if executable.is_symlink() or sha256_file(executable)!=EXE_SHA:raise ValueError('Frozen executable mismatch')
    runs_root=stage_root/'03_PARITY_RUNS';seal_root=stage_root/'04_PARITY_SEAL'
    runs_root.mkdir(exist_ok=False);seal_root.mkdir(exist_ok=False);records=[]
    for variant,method in order:
        run_id=f'CLEAN5_PARITY_{variant}_{method}'
        root=runs_root/run_id;root.mkdir()
        source=contract['frozen_runtime']['original_configs'][method]
        source_path=resolve(source['runtime_config'],registry)
        if sha256_file(source_path)!=source['runtime_config_sha256']: raise RuntimeError('frozen config changed')
        inputs=provider_bundle['variants'][variant]['providers']
        replacements={key:str(value['path'] if isinstance(value,dict) else value) for key,value in inputs.items()}
        replacements.update(NATIVE_IDENTITY,outputpath=str(root),run_id=run_id,run_label=run_id)
        text,diff=bind_config(source_path.read_text(),replacements); cfg=yaml.safe_load(text)
        (root/'PARITY_RUNTIME_CONFIG.yaml').write_text(text)
        expected=expected_counts(cfg)
        record={'variant_id':variant,'provider_family':'CLEAN5_PARITY_'+variant,'method_id':method,'run_id':run_id,'terminal_status':'NOT_STARTED',
                'effective_profile':{'F01':'single_antenna_EKF','F03':'AB0000','A04':'AB1011'}[method],
                'effective_configuration_id':{'F01':'single_antenna_EKF','F03':'AB0000','A04':'AB1011'}[method],
                'output_root':str(root),'dataset_id':'BY2','case_id':'C00_clean_normal','data_mode':'real_by2_raw',
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
        record['command']=command
        write_json(root/'RUN_STARTED.json',record)
        started=time.monotonic()
        result=run_process_group(command,cwd=registry.code_root,timeout_seconds=1800,
                  timeout_message='P03 solver timeout',launch_failure_message='P03 solver launch failed')
        record.update(exit_code=result.returncode,runtime_seconds=time.monotonic()-started)
        (root/'stdout.log').write_text(result.stdout);(root/'stderr.log').write_text(result.stderr)
        record['strace_audit']=audit_solver_openat(log,cwd=registry.code_root,raw_root=registry.raw_root,run_dir=root,clean_root=registry.clean_root)
        record['terminal_status']='COMPLETED' if result.returncode==0 else 'FAILED_NATIVE_SOLVER'
        native_path=root/'RUN_MANIFEST.json'
        if native_path.exists():
            native=json.loads(native_path.read_text());record['native_manifest_sha256']=sha256_file(native_path)
            record['counter_audit']=check_counters(native,cfg,expected)
            record['counters']=record['counter_audit']['actual']
            if not record['counter_audit']['pass']:record['terminal_status']='FAILED_COUNTER_AUDIT'
        else:
            record['counters']='UNAVAILABLE_NATIVE_MANIFEST_NOT_WRITTEN'
            if record['terminal_status']=='COMPLETED':record['terminal_status']='FAILED_NATIVE_MANIFEST_MISSING'
            record['diagnostic_trace_counts']=diagnostic_counts(root)
        if not record['strace_audit']['pass']:record['terminal_status']='FAILED_STRACE_AUDIT'
        if record['terminal_status']=='COMPLETED':
            record.update(validate_run_outputs(root,{'window_contract':{'t_start':66,'t_end':340}}))
            for role,name in [('nav','KF_GINS_Navresult.nav'),('std','KF_GINS_STD.txt')]:
                record[role+'_path']=str(root/name);record[role+'_sha256']=sha256_file(root/name)
        write_json(root/'PARITY_RUN_MANIFEST.json',record);records.append(record)
        print(f'{run_id}: {record["terminal_status"]} exit={result.returncode}',flush=True)
        if record['terminal_status']!='COMPLETED':break
    from ..clean5_parity.scheduling import audit_scheduling
    scheduling_root=seal_root/'SCHEDULING'
    for record in records:
        root=Path(record['output_root'])
        cfg=yaml.safe_load((root/'PARITY_RUNTIME_CONFIG.yaml').read_text())
        record['auxiliary_scheduling_audit']=audit_scheduling(config=cfg,
            output_root=scheduling_root/record['run_id'],native_trace=root/'PORT_GNSS_UPDATE_TRACE.csv')
    hashes={str(p.relative_to(stage_root)):sha256_file(p) for parent in (runs_root,scheduling_root)
            for p in parent.rglob('*') if p.is_file()}
    seal={'status':'SEALED','code_commit':code_commit,'run_count':len(records),
          'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False,
          'completed_count':sum(r['terminal_status']=='COMPLETED' for r in records),
          'files_sha256':hashes,'records':records,'all_native_success':all(r['terminal_status']=='COMPLETED' for r in records)}
    write_json(seal_root/'PARITY_OUTPUT_SEAL.json',seal)
    return records
