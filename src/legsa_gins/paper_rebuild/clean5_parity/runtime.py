"""Frozen-binary parity execution with explicit validity counters and output seals."""
from __future__ import annotations
import csv
import hashlib
import json
import re
import shutil
import time
from pathlib import Path
import numpy as np
import yaml
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from ..clean5_sequence.runtime_config import frozen_parameter_hash, NATIVE_IDENTITY
from ..clean5_sequence.solver_runner import audit_solver_openat
from ..clean5_sequence.solver_validation import COUNTER_SOURCES, FORBIDDEN_FLAGS, validate_run_outputs

RUN_ORDER = [('V0-18','A04'),('V1','F01'),('V1','F03'),('V1','A04'),
             ('V2','F01'),('V2','F03'),('V2','A04'),('V2e','F01')]
EXE_SHA = '9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f'
ALLOWED = {'imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path',
           'go2_horizontal_velocity_prior_path','outputpath','stage_id','protocol_id',
           'case_id','data_mode','run_id','run_label'}

def write_json(path, data):
    with Path(path).open('x',encoding='utf-8') as handle:
        json.dump(data,handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write('\n')

def resolve(value, registry):
    return Path(str(value).replace('<CLEAN_ROOT>',str(registry.clean_root))
                .replace('<CODE_ROOT>',str(registry.code_root)).replace('<RAW_ROOT>',str(registry.raw_root)))

def bind_config(original, replacements):
    """Preserve every non-identity/path byte, including initialization and flags."""
    if set(replacements)-ALLOWED:
        raise ValueError('non-authorized parameter override')
    before=yaml.safe_load(original); seen=set(); lines=[]; ledger=[]
    for line in original.splitlines(keepends=True):
        key=line.split(':',1)[0]
        if key in replacements:
            if key in seen: raise ValueError('duplicate replacement key')
            seen.add(key)
            new=key+': '+json.dumps(replacements[key],ensure_ascii=False)+ ('\n' if line.endswith('\n') else '')
            ledger.append({'key':key,'before':line.rstrip('\n'),'after':new.rstrip('\n')})
            lines.append(new)
        else: lines.append(line)
    if seen!=set(replacements): raise ValueError('unknown replacement field')
    result=''.join(lines)
    if frozen_parameter_hash(original)!=frozen_parameter_hash(result):
        raise ValueError('frozen_parameter_hash mismatch')
    after=yaml.safe_load(result)
    if set(before)!=set(after): raise ValueError('runtime fields changed')
    if any(before[k]!=after[k] for k in before if k not in ALLOWED):
        raise ValueError('scientific parameter changed')
    return result,ledger

def expected_counts(cfg):
    gnss=np.loadtxt(cfg['gnsspath'],ndmin=2)
    imu=np.loadtxt(cfg['imupath'],ndmin=2)
    if gnss.shape[1]!=18 or not np.isfinite(gnss).all(): raise ValueError('invalid GNSS18')
    if not np.isin(gnss[:,15:], [0,1]).all(): raise ValueError('invalid validity bits')
    if not np.all(gnss[:,15]==1):raise ValueError('P02 schedule scope requires position_valid=1 on every row')
    if not np.all(np.diff(gnss[:,0])>0): raise ValueError('nonmonotonic GNSS time')
    eligible, schedule = scheduled_gnss_indices(gnss[:,0], imu[:,0], cfg['starttime'], cfg['endtime'])
    selected=gnss[eligible]
    return {**schedule,'eligible_rows':len(selected),
            'position_update_count':int(selected[:,15].sum()),
            'receiver_velocity_update_count':int(selected[:,16].sum()) if cfg['enable_receiver_velocity'] else 0,
            'dual_yaw_attempt_count':int(selected[:,17].sum()) if cfg['enable_dual_yaw'] else 0,
            'eligible_yaw_valid_bits':int(selected[:,17].sum()),
            'eligible_velocity_valid_bits':int(selected[:,16].sum()),
            'source':'Source-only C++ schedule replay; no NAV, counters or reference used'}

def scheduled_gnss_indices(gnss_times, imu_times, start, end):
    """Replay frozen loader/engine scheduling, including endpoint tolerance and refresh.

    port_runtime.cpp:1416,1435,1463,1471; gi_engine.cpp:265,413;
    types.hpp:63 (TIME_ALIGN_ERR=0.001). No state or measurement calculation.
    """
    g=np.asarray(gnss_times,float); it=np.asarray(imu_times,float)
    if not len(it) or not len(g) or not np.isfinite(it).all() or not np.isfinite(g).all():
        raise ValueError('empty/nonfinite scheduling inputs')
    if np.any(np.diff(it)<=0) or np.any(np.diff(g)<=0):raise ValueError('nonmonotonic scheduling inputs')
    ii=int(np.searchsorted(it,start,side='left'))
    if ii==len(it):raise ValueError('no initialization IMU')
    previous=float(it[ii]); initial=previous
    gi=int(np.searchsorted(g,start,side='right')); valid=gi<len(g)
    selected=[]; stopped=None
    for current in it[ii+1:]:
        if end>0 and current>end:
            stopped=float(current);break
        # The runtime advances at most ONE GNSS row per IMU loop.
        if gi<len(g) and g[gi]<previous and gi+1<len(g):
            gi+=1;valid=True
        if valid and (abs(previous-g[gi])<.001 or abs(current-g[gi])<=.001
                      or previous<g[gi]<current):
            selected.append(gi);valid=False
        previous=float(current)
    return np.asarray(selected,dtype=int),{'t_init':initial,'last_processed_imu_time':previous,
            'first_unprocessed_imu_time':stopped,'time_align_error_s':.001,
            'schedule_source':'port_runtime.cpp:1416,1435,1463,1471; gi_engine.cpp:265,413; types.hpp:63'}

def check_counters(native, cfg, expected):
    counters={k:native.get(v) for k,v in COUNTER_SOURCES.items()}
    failures=[]
    for key in ('position_update_count','receiver_velocity_update_count','dual_yaw_attempt_count'):
        if counters[key]!=expected[key]: failures.append(key)
    for key in ('selected_fgo_feedback_update_count','nine_factor_fgo_update_count','qm_count','qa_count','contact_fk_count'):
        if counters[key]!=0: failures.append(key)
    for flag,key in [('enable_raw_doppler','raw_doppler_update_count'),('enable_source_aware','source_aware_evaluation_count'),
                     ('enable_go2_roll_pitch_prior','go2_roll_pitch_update_count'),('enable_go2_horizontal_velocity_prior','go2_horizontal_velocity_update_count')]:
        if not cfg[flag] and counters[key]!=0: failures.append(key)
        if cfg[flag] and (not isinstance(counters[key],int) or counters[key]<=0): failures.append(key)
    if any(native.get(k) is not False for k in FORBIDDEN_FLAGS): failures.append('forbidden_native_flags')
    if any(native.get(k)!=0 for k in ('old_runtime_input_count','legacy_provider_input_count','legacy_row_input_count','legacy_aggregate_input_count')):
        failures.append('forbidden_input_counts')
    return {'pass':not failures,'failures':failures,'expected':expected,'actual':counters}

def compare_identity(run_root, canonical_root):
    rows=[]
    for name in ('KF_GINS_Navresult.nav','KF_GINS_STD.txt'):
        new,old=Path(run_root)/name,Path(canonical_root)/name
        x,y=np.loadtxt(new,ndmin=2),np.loadtxt(old,ndmin=2)
        same_shape=x.shape==y.shape
        delta=float(np.max(np.abs(x-y))) if same_shape else None
        rows.append({'file':name,'actual_sha256':sha256_file(new),'canonical_sha256':sha256_file(old),
                     'byte_equal':new.read_bytes()==old.read_bytes(),'shape_equal':same_shape,
                     'max_absolute_difference':delta,'pass':same_shape and delta<=1e-9})
    return {'status':'PASS' if all(r['pass'] for r in rows) else 'FAIL','files':rows}

def run_ladder(*,registry,stage_root,contract,provider_bundle,executable,code_commit,prior_records=None):
    stage_root=Path(stage_root); executable=Path(executable)
    if sha256_file(executable)!=EXE_SHA: raise RuntimeError('frozen executable mismatch')
    runs_root=stage_root/'03_PARITY_RUNS'; seal_root=stage_root/'04_PARITY_SEAL'
    records=list(prior_records or [])
    if prior_records is None:
        runs_root.mkdir(exist_ok=False);seal_root.mkdir(exist_ok=False)
    else:
        if len(records)!=2 or [(r['variant_id'],r['method_id']) for r in records]!=RUN_ORDER[:2]:
            raise ValueError('Continuation must retain exactly the first two authorized runs')
        if any(r['terminal_status']!='COMPLETED' for r in records):raise ValueError('Prior revalidation failed')
        if {p.name for p in runs_root.iterdir()}!={r['run_id'] for r in records}:raise ValueError('Unexpected prior run directory')
    for variant,method in RUN_ORDER[len(records):]:
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
        record={'variant_id':variant,'method_id':method,'run_id':run_id,'terminal_status':'NOT_STARTED',
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
                  timeout_message='P02 solver timeout',launch_failure_message='P02 solver launch failed')
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
            record['diagnostic_trace_counts']=diagnostic_counts(root)
        if not record['strace_audit']['pass']:record['terminal_status']='FAILED_STRACE_AUDIT'
        if record['terminal_status']=='COMPLETED':
            record.update(validate_run_outputs(root,{'window_contract':{'t_start':66,'t_end':340}}))
            for role,name in [('nav','KF_GINS_Navresult.nav'),('std','KF_GINS_STD.txt')]:
                record[role+'_path']=str(root/name);record[role+'_sha256']=sha256_file(root/name)
        if (variant=='V2e' and result.returncode and record['strace_audit']['pass']
                and record['terminal_status']=='FAILED_NATIVE_SOLVER'
                and 'actual formal module activation counters mismatch' in result.stderr):
            record['terminal_status']='FAILED_NATIVE_COUNTER_CONTRACT'
            record['known_static_gate']='F01 requires RV count > 0; RV validity all zero; frozen guard preserved'
        write_json(root/'PARITY_RUN_MANIFEST.json',record);records.append(record)
        print(f'{run_id}: {record["terminal_status"]} exit={result.returncode}',flush=True)
        if variant=='V0-18':
            gate=compare_identity(root,source_path.parent) if record['terminal_status']=='COMPLETED' else {'status':'FAIL','reason':record['terminal_status']}
            write_json(seal_root/'V0_18_IDENTITY_GATE.json',gate)
            if gate['status']!='PASS':break
        if record['terminal_status']!='COMPLETED' and variant!='V2e':break
    from .scheduling import audit_scheduling
    scheduling_root=seal_root/'SCHEDULING'
    for record in records:
        root=Path(record['output_root'])
        cfg=yaml.safe_load((root/'PARITY_RUNTIME_CONFIG.yaml').read_text())
        record['auxiliary_scheduling_audit']=audit_scheduling(config=cfg,
            output_root=scheduling_root/record['run_id'],native_trace=root/'PORT_GNSS_UPDATE_TRACE.csv')
    hashes={str(p.relative_to(stage_root)):sha256_file(p) for parent in (runs_root,scheduling_root)
            for p in parent.rglob('*') if p.is_file()}
    seal={'status':'SEALED','code_commit':code_commit,'run_count':len(records),
          'completed_count':sum(r['terminal_status']=='COMPLETED' for r in records),
          'files_sha256':hashes,'records':records,'all_native_success':all(r['terminal_status']=='COMPLETED' for r in records)}
    write_json(seal_root/('PARITY_OUTPUT_SEAL_CONTINUED.json' if prior_records is not None else 'PARITY_OUTPUT_SEAL.json'),seal)
    return records

def diagnostic_counts(root):
    path=Path(root)/'PORT_GNSS_UPDATE_TRACE.csv'
    if not path.exists():return {'status':'UNAVAILABLE'}
    with path.open() as f:rows=list(csv.DictReader(f))
    return {'status':'DIAGNOSTIC_ONLY_NATIVE_MANIFEST_UNAVAILABLE','rows':len(rows),
            'source':str(path),'sha256':sha256_file(path),
            **{k:sum(float(r[k]) for r in rows) for k in ('position_update','velocity_update','yaw_update')}}
