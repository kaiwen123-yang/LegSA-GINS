"""Bounded natural-sequence correction. Frozen V3 artifacts remain immutable.

CLI paths are explicit machine-local arguments. The parent never reads trace;
the frozen evaluator runs only after all registered native outputs are sealed.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

import numpy as np
import pandas as pd
import yaml

from .imu_time_contract import read_raw_duration_contract, continuous_segments, write_segment
from .manifest import sha256_file
from .hext.sequence_paths import load_sequence_paths, REGISTRY, CALIBRATED_CONTRACT
from .clean5_parity.evaluation import transform_nav, write_transformed_nav, body_to_ned
from .horizontal_literature.shared_raw_backend import ecef_to_geodetic
from .protocol_v3.evaluation_process import evaluate, EVALUATOR_SHA256
from .subprocess_guard import run_process_group
from .clean5_sequence.io_audit import audited_open_records

METHODS = {'F01','F02','F03','F04','A03','A04','A05','A06','A07','A08','A09'}
STAGE = 'IMU_V3_TIME_CONTRACT_FIX_20261004'


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def pinned(pin):
    path = Path(pin['path'])
    if path.is_symlink() or sha256_file(path) != pin['sha256']:
        raise ValueError('CORRECTION_INPUT_PIN_CHANGED:'+str(path))
    return path


def verify_runtime(stage, code, plan):
    pinned({'path':str(stage/'SOLVER'),'sha256':plan['binary_sha256']})
    for relative,digest in plan['source_snapshot_sha256'].items():
        pinned({'path':str(code/relative),'sha256':digest})
        pinned({'path':str(stage/'SOURCE_SNAPSHOT'/relative),'sha256':digest})


def imu_position_from_antenna(llh_deg_m, attitude_deg, lever_body_m):
    lat,lon=np.deg2rad(np.asarray(llh_deg_m,float)[:2]);height=float(llh_deg_m[2])
    sl,cl,so,co=np.sin(lat),np.cos(lat),np.sin(lon),np.cos(lon)
    radius=6378137./np.sqrt(1.-6.6943799901413165e-3*sl*sl)
    xyz=np.array([(radius+height)*cl*co,(radius+height)*cl*so,
                  (radius*(1.-6.6943799901413165e-3)+height)*sl])
    north,east,down=body_to_ned(np.asarray([attitude_deg]))[0]@np.asarray(lever_body_m)
    xyz-=np.array([-sl*co*north-so*east-cl*co*down,
                  -sl*so*north+co*east-cl*so*down,cl*north-sl*down])
    llh=ecef_to_geodetic(xyz)
    return [float(np.rad2deg(llh[0])),float(np.rad2deg(llh[1])),float(llh[2])]


def body_digest(spec, seq):
    value = spec['raw_source_hashes'].get('body')
    if value is None:
        value = spec['raw_source_hashes'].get(seq.go2_body.relative_to(seq.raw_root).as_posix())
    if isinstance(value, dict):
        if Path(value['path']) != seq.go2_body: raise ValueError('BODY_ROLE_PATH_MISMATCH')
        value = value['sha256']
    if not isinstance(value,str) or len(value)!=64: raise ValueError('BODY_ROLE_PIN_MISSING')
    return value


def clone_fields(payload, fields):
    """Replace only declared complete value lines, preserving all other bytes."""
    lines = payload.splitlines(keepends=True); changes = []
    for key, value in fields.items():
        pattern = re.compile(rb'^([ \t]*'+key.encode()+rb'[ \t]*:[ \t]*)([^\r\n]*)(\r?\n|$)')
        matches = [(i, pattern.fullmatch(line)) for i,line in enumerate(lines) if pattern.fullmatch(line)]
        if len(matches) != 1: raise ValueError('CONFIG_FIELD_NOT_UNIQUE:'+key)
        i, match = matches[0]
        token = json.dumps(value) if isinstance(value, (str,list,bool)) else str(value)
        before = lines[i]; lines[i] = match[1]+token.encode()+match[3]
        changes.append({'field':key,'line':i+1,'before':before.decode().rstrip(),'after':lines[i].decode().rstrip()})
    result = b''.join(lines)
    old = payload.splitlines(keepends=True); new = result.splitlines(keepends=True)
    indices = {r['line']-1 for r in changes}
    if any(a != b for i,(a,b) in enumerate(zip(old,new)) if i not in indices):
        raise ValueError('CONFIG_NONAUTHORIZED_BYTES_CHANGED')
    return result+b'imu_gap_policy: STOP_AND_REINITIALIZE\n', changes


def prepare(args):
    stage, code, prior = Path(args.stage), Path(args.code), Path(args.prior_v3)
    if args.physical_free_bytes is None or args.physical_free_bytes < 5*1024**3:
        raise RuntimeError('ACTUAL_HOST_VOLUME_FREE_BYTES_REQUIRED')
    if shutil.disk_usage(stage.parent).free < 5*1024**3:
        raise RuntimeError('INSUFFICIENT_CORRECTION_STORAGE')
    if not Path(args.local_config).is_file():raise ValueError('LOCAL_PATH_CONFIG_MISSING')
    stage.mkdir(parents=True, exist_ok=False)
    original = json.loads((prior/'00_PREREGISTRATION/REGISTRY.json').read_text())
    specs = [r for r in original if r['method_id'] in METHODS and
             ((r['sequence_id']=='BY2' and r['case_id']=='C00_clean_normal') or
              r['domain']=='SEQUENCE')]
    if len(specs)!=33 or len({(s['sequence_id'],s['method_id']) for s in specs})!=33:
        raise ValueError('CORRECTION_EXPECTED_33_NATURAL_CONFIGURATIONS')
    snapshot = {}; source = list((code/'cpp/legsa_v23_port_core').rglob('*.cpp')) + list((code/'cpp/legsa_v23_port_core').rglob('*.hpp'))
    python_sources=['imu_time_contract.py','imu_contract_repair.py','manifest.py','evidence.py',
                    'subprocess_guard.py','hext/sequence_paths.py','clean5_parity/evaluation.py',
                    'protocol_v3/evaluation_process.py','clean5_sequence/io_audit.py',
                    'horizontal_literature/shared_raw_backend.py','clean5_sequence/evaluator_capture.py',
                    'clean6_canonical_v2/evaluation.py']
    source += [code/'src/legsa_gins/paper_rebuild'/name for name in python_sources]
    source += [code/'src/legsa_gins/input_generation/imu_txt_builder.py',
               code/'src/legsa_gins/datasets/by2/go2_body_state_parser.py',code/'cpp/CMakeLists.txt',
               code/REGISTRY,code/CALIBRATED_CONTRACT]
    source += list((code/'scripts/paper_rebuild/v3_evaluator_observer').rglob('*.py'))
    build=json.loads(Path(args.build_receipt).read_text())
    if build['status']!='NATIVE_BUILD_SOURCE_IDENTITY_VERIFIED':raise ValueError('BUILD_RECEIPT_REQUIRED')
    for relative,digest in build['source_sha256'].items():
        pinned({'path':str(code/relative),'sha256':digest})
    # Snapshot the entire small Python package to close dynamic observer/import
    # dependencies too. This is a source-identity superset, not executed coverage.
    source += list((code/'src/legsa_gins').rglob('*.py'))
    source=sorted(set(source))
    for path in source:
        relative = path.relative_to(code); target = stage/'SOURCE_SNAPSHOT'/relative
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(path.read_bytes())
        snapshot[str(relative)] = sha256_file(target)
    binary = Path(args.binary)
    if sha256_file(binary)!=build['binary_sha256']:raise ValueError('BINARY_BUILD_IDENTITY_MISMATCH')
    shutil.copyfile(binary, stage/'SOLVER'); (stage/'SOLVER').chmod(0o755)
    shutil.copyfile(args.build_receipt,stage/'BUILD_RECEIPT.json')
    sequences = {}; runs = []
    for name in ('BY2','BY2H','BY2O'):
        seq = load_sequence_paths(name, Path(args.local_config), code/REGISTRY, code/CALIBRATED_CONTRACT)
        spec = next(s for s in specs if s['sequence_id']==name and s['method_id']=='F04')
        raw_digest = body_digest(spec,seq)
        if any(body_digest(s,seq)!=raw_digest for s in specs if s['sequence_id']==name):
            raise ValueError('METHODS_DISAGREE_ON_BODY_SOURCE')
        if sha256_file(seq.go2_body) != raw_digest:
            raise ValueError('RAW_BODY_PIN_CHANGED')
        imu = pinned(spec['frozen_providers']['imupath'])
        rows, builder = read_raw_duration_contract(seq.go2_body, imu, base_time=seq.base_time)
        segments, gaps = continuous_segments(rows, start=seq.window[0], end=seq.window[1])
        paths = []
        for index, segment in enumerate(segments):
            path = stage/'INPUTS'/name/f'IMU8_SEGMENT_{index:02d}.imu'
            write_segment(path, segment)
            paths.append({'path':str(path),'sha256':sha256_file(path),'rows':len(segment),
                          'first':segment[0]['time'],'last':segment[-1]['time']})
        sequences[name] = {'window':list(seq.window),'baseline_median_m':seq.baseline_median_m,
            'raw_root':str(seq.raw_root),'base_time':seq.base_time,'raw_body_path':str(seq.go2_body),'raw_body_sha256':raw_digest,
            'legacy_imu':spec['frozen_providers']['imupath'],'measured_rows':len(rows),'builder':builder,
            'segments':paths,'gaps':gaps,'expected_original_output_epochs':sum(len(s) for s in segments)-1,
            'missing_motion_reconstructed':False, 'gap_policy':'STOP_AND_REINITIALIZE',
            'trace_path':str(seq.trace),'trace_sha256':seq.trace_sha256}
    for spec in specs:
        admission = json.loads((prior/'02_CONFIGS'/spec['run_id']/'CONFIG_ADMISSION.json').read_text())
        original_config = pinned(admission['config']).read_bytes()
        cfg = yaml.safe_load(original_config)
        providers = {**spec['frozen_providers'], 'gnsspath':admission['prepared_gnss']}
        for pin in providers.values(): pinned(pin)
        gnss = np.loadtxt(cfg['gnsspath'], ndmin=2)
        if gnss.shape[1] != 18: raise ValueError('EXPECTED_V3_GNSS18')
        seq = sequences[spec['sequence_id']]
        children = []
        rid = 'IMUFIX_'+spec['sequence_id']+'_'+spec['method_id']
        for index, segment in enumerate(seq['segments']):
            child_id = rid+f'_S{index:02d}'
            fields = {'stage_id':STAGE,'protocol_id':'V3_NATURAL_SEQUENCE_EXPLICIT_IMU_DURATION',
                'case_id':'IMU_V3_NATURAL_SEQUENCE','run_id':child_id,'run_label':child_id,
                'imupath':segment['path'],'imudatalen':8,'endtime':segment['last'],
                'outputpath':str(stage/'NATIVE'/child_id)}
            initialization = {'kind':'UNCHANGED_V3_COMMON_INITIALIZATION','yaw_information_added':False}
            if index:
                candidates = gnss[(gnss[:,0]>=segment['first']) & (gnss[:,0]<segment['last']) &
                                  (gnss[:,15]==1) & (gnss[:,17]==1)]
                if not len(candidates):
                    children.append({'run_id':child_id,'status':'NO_OUTPUT_NO_VALID_REINITIALIZATION',
                                     'segment':segment,'native_invoked':False}); continue
                obs = candidates[0]
                attitude=[0,0,float(obs[13])]
                position=imu_position_from_antenna(obs[1:4],attitude,cfg['antlever'])
                fields.update(starttime=float(obs[0]),initpos=position,initvel=[0,0,0],
                              initatt=[0,0,float(obs[13])],initgyrbias=[0,0,0],initaccbias=[0,0,0],
                              common_initialization_source='INPUT_ONLY_GAP_RESTART_V3_INITIALIZATION_RECIPE')
                initialization = {'kind':'INPUT_ONLY_GNSS_POSITION_AND_DUAL_YAW_RESTART',
                    'epoch':float(obs[0]),'source':'GNSS18_POSITION_VALID_AND_YAW_VALID',
                    'yaw_information_added':True,'velocity':'ZERO_V3_RECIPE','roll_pitch':'ZERO_V3_RECIPE',
                    'position_point':'IMU_ORIGIN; inverse declared V3 GNSS1 lever with zero roll/pitch',
                    'antenna_position_deg_m':obs[1:4].tolist(),'imu_position_deg_m':position,
                    'declared_lever_body_m':cfg['antlever'],'calibration_verified':False,
                    'trace_used':False}
            transformed, changes = clone_fields(original_config,fields)
            path = stage/'CONFIGS'/f'{child_id}.yaml';path.parent.mkdir(exist_ok=True)
            path.write_bytes(transformed)
            children.append({'run_id':child_id,'config':{'path':str(path),'sha256':sha256_file(path)},
                             'config_changes':changes,'initialization':initialization,
                             'segment':segment,'status':'PREPARED'})
        runs.append({'run_id':rid,'source_run_id':spec['run_id'],'method_id':spec['method_id'],
            'sequence_id':spec['sequence_id'],'source_config':admission['config'],
            'providers':providers,'children':children,'data_mode':'real_clean','trace_used_online':False})
    write_json(stage/'PREREGISTRATION.json', {'schema':'imu_v3_time_correction.v1','stage':STAGE,
        'base_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=code,text=True).strip(),
        'base_head_role':'BASE_ONLY; actual working source snapshot and binary hashes identify runtime',
        'source_snapshot_scope':'whole legsa_gins Python package plus native port/build/config sources; identity superset, not executed line coverage',
        'source_snapshot_sha256':snapshot,'binary_sha256':sha256_file(stage/'SOLVER'),
        'old_results_overwritten':False,'fault_matrix_replayed':False,'native_configurations':33,
        'host_volume_free_bytes_at_prepare':args.physical_free_bytes,
        'host_volume_measurement':'Windows Get-Volume E supplied by launch parent; WSL virtual df is insufficient',
        'build_receipt_sha256':sha256_file(stage/'BUILD_RECEIPT.json'),
        'corrected_models':['measured_duration','conditional_NIS','active_H2_std','compensated_angular_rate_and_velocity_jacobian','tilted_lateral_baseline_projection'],
        'causal_gap_effect_claim':False,'sequences':sequences,'runs':runs})
    verify_runtime(stage,code,json.loads((stage/'PREREGISTRATION.json').read_text()))
    print(json.dumps({'status':'PREPARED','stage':str(stage),'configurations':33,
        'gaps':{name:len(seq['gaps']) for name,seq in sequences.items()},
        'native_children':sum(c['status']=='PREPARED' for r in runs for c in r['children'])}))


def run_native(args):
    stage = Path(args.stage); plan = json.loads((stage/'PREREGISTRATION.json').read_text())
    verify_runtime(stage,Path(args.code),plan)
    all_records = []; started = time.monotonic()
    # Every invocation consumes its exclusive directory. No overwrite or retry.
    for run in plan['runs']:
        for pin in run['providers'].values():pinned(pin)
        records = []; arrays = {'nav':[],'std':[]}; support = []
        for child in run['children']:
            if child['status'] != 'PREPARED': records.append(child); continue
            path = pinned(child['config']); pinned(child['segment'])
            root = stage/'NATIVE'/child['run_id'];root.mkdir(parents=True,exist_ok=False)
            argv = ['strace','-f','-qq','-s','4096','-e','trace=openat,execve','-o',str(root/'OPENAT.strace'),
                    str(stage/'SOLVER'),'--config',str(path),'--output-dir',str(root)]
            write_json(root/'LAUNCH.json', {'argv':argv,'config':child['config'],'segment':child['segment'],
                       'source_snapshot':plan['source_snapshot_sha256'],'initialization':child['initialization']})
            t = time.monotonic()
            verify_runtime(stage,Path(args.code),plan)
            result = run_process_group(argv,cwd=Path(args.code),timeout_seconds=1800,
                                       timeout_message='corrected native timeout; no retry',
                                       launch_failure_message='corrected native launch failed; no retry')
            (root/'stdout.log').write_text(result.stdout);(root/'stderr.log').write_text(result.stderr)
            verify_runtime(stage,Path(args.code),plan)
            for pin in run['providers'].values():pinned(pin)
            opened=audited_open_records(root/'OPENAT.strace',Path(args.code))
            trace_paths={v['trace_path'] for v in plan['sequences'].values()}
            trace_count=sum(r['path'] in trace_paths for r in opened)
            bag_fpl_count=sum(r['path'].endswith(('.bag','.fpl')) for r in opened)
            allowed={pin['path'] for pin in run['providers'].values()}|{str(path),child['segment']['path']}
            raw_roots={Path(v['raw_root']) for v in plan['sequences'].values()}
            raw_violations=[r['path'] for r in opened if any(v in Path(r['path']).parents for v in raw_roots) and r['path'] not in allowed]
            record = {**child,'exit_code':result.returncode,'runtime_seconds':time.monotonic()-t,
                      'trace_open_count':trace_count,'bag_fpl_open_count':bag_fpl_count,
                      'unexpected_raw_opens':raw_violations,'output_root':str(root), 'native_invoked':True}
            if result.returncode or trace_count or bag_fpl_count or raw_violations: record['status']='FAILED_NATIVE_OR_ACCESS_AUDIT'
            else:
                nav = np.loadtxt(root/'KF_GINS_Navresult.nav',ndmin=2,comments='%')
                std = np.loadtxt(root/'KF_GINS_STD.txt',ndmin=2,comments='%')
                if len(nav)!=len(std) or not np.isfinite(nav).all() or not np.isfinite(std).all() or not np.array_equal(nav[:,1],std[:,0]):
                    raise ValueError('CORRECTED_NATIVE_SUPPORT_INVALID')
                record['status']='COMPLETED'; record['output_epochs']=len(nav)
                arrays['nav'].append(nav);arrays['std'].append(std)
                support += [{'time':float(t),'segment_id':child['run_id']} for t in nav[:,1]]
                saved=np.loadtxt(root/'STATE_COVARIANCE_SUPPORT.csv',delimiter=',',skiprows=1,ndmin=2)
                cov=saved[:,16:].reshape(-1,21,21)
                indices=np.clip(np.searchsorted(nav[:,1],saved[:,0]),0,len(nav)-1)
                previous=np.maximum(0,indices-1)
                matched_distances=np.minimum(np.abs(nav[indices,1]-saved[:,0]),np.abs(nav[previous,1]-saved[:,0]))
                if np.any(matched_distances>1.1e-6):raise ValueError('SAVED_STATE_COVARIANCE_SUPPORT_NOT_IN_NAV')
                scale = np.maximum(1.,np.max(np.abs(cov),axis=(1,2)))
                asym = np.max(np.abs(cov-cov.transpose(0,2,1)),axis=(1,2))
                eigen = np.linalg.eigvalsh((cov[:,:15,:15]+cov[:,:15,:15].transpose(0,2,1))*.5)
                health = {'saved_full_P_epochs':len(cov),'all_finite':bool(np.isfinite(cov).all()),
                    'max_relative_asymmetry':float(np.max(asym/scale)),
                    'min_active_15_eigenvalue':float(np.min(eigen)),
                    'active_15_PSD_at_recorded_boundaries':bool(np.all(eigen[:,0]>=-1e-10*scale)),
                    'frozen_scale_blocks_exactly_zero':bool(np.all(cov[:,15:,:]==0) and np.all(cov[:,:,15:]==0))}
                record['covariance_health']=health
                if not health['all_finite'] or not health['active_15_PSD_at_recorded_boundaries'] or not health['frozen_scale_blocks_exactly_zero'] or health['max_relative_asymmetry']>1e-8:
                    raise ValueError('CORRECTED_NATIVE_COVARIANCE_UNHEALTHY')
            write_json(root/'OUTPUT_SEAL.json',{'status':'SEALED','files':{p.name:sha256_file(p) for p in root.iterdir() if p.is_file()}})
            write_json(root/'NATIVE_RESULT.json',record);records.append(record)
            print(child['run_id'], record['status'], flush=True)
            if record['status']!='COMPLETED': raise RuntimeError('native failure preserved; stop, no retry')
        combined = stage/'COMBINED'/run['run_id'];combined.mkdir(parents=True,exist_ok=False)
        for key, name in [('nav','KF_GINS_Navresult.nav'),('std','KF_GINS_STD.txt')]:
            if arrays[key]:
                array = np.concatenate(arrays[key]); times = array[:,1 if key=='nav' else 0]
                if np.any(np.diff(times)<=0): raise ValueError('SEGMENT_OUTPUT_TIMES_OVERLAP')
                np.savetxt(combined/name,array,fmt='%.17g')
        with (combined/'SEGMENT_SUPPORT.csv').open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['time','segment_id']);writer.writeheader();writer.writerows(support)
        record = {**run,'children':records,'status':'COMPLETED_SEGMENTED' if support else 'NO_OUTPUT',
            'output_epochs':len(support),'expected_original_output_epochs':plan['sequences'][run['sequence_id']]['expected_original_output_epochs'],
            'gap_restart_count':sum(c.get('initialization',{}).get('yaw_information_added',False) for c in records if c.get('native_invoked')),
            'trace_open_count':sum(c.get('trace_open_count',0) for c in records),
            'position_point_transform':'FROZEN_V3_DIAGNOSTIC; untransported STD, point uncertainty unresolved'}
        write_json(combined/'OUTPUT_SEAL.json',{'status':'SEALED','files':{p.name:sha256_file(p) for p in combined.iterdir() if p.is_file()}})
        all_records.append(record)
    verify_runtime(stage,Path(args.code),plan)
    write_json(stage/'ALL_NATIVE_SEALED.json',{'status':'SEALED',
        'preregistration_sha256':sha256_file(stage/'PREREGISTRATION.json'),'binary_sha256':plan['binary_sha256'],'runtime_seconds':time.monotonic()-started,'runs':all_records})


def evaluate_all(args):
    stage=Path(args.stage);plan=json.loads((stage/'PREREGISTRATION.json').read_text())
    native=json.loads((stage/'ALL_NATIVE_SEALED.json').read_text());results=[]
    verify_runtime(stage,Path(args.code),plan)
    pinned({'path':args.evaluator,'sha256':EVALUATOR_SHA256})
    count=plan['native_configurations']
    if count not in (33,135) or len(plan['runs'])!=count or native['status']!='SEALED' or len(native['runs'])!=count:
        raise ValueError('ALL_NATIVE_SEAL_REQUIRED')
    if native['preregistration_sha256']!=sha256_file(stage/'PREREGISTRATION.json') or native['binary_sha256']!=plan['binary_sha256']:raise ValueError('NATIVE_PLAN_IDENTITY_MISMATCH')
    expected={r['run_id']:r for r in plan['runs']}
    if set(r['run_id'] for r in native['runs'])!=set(expected):raise ValueError('NATIVE_RUN_SET_MISMATCH')
    for actual in native['runs']:
        original=expected[actual['run_id']]
        if any(actual[key]!=original[key] for key in ('sequence_id','method_id','source_run_id','providers')):raise ValueError('NATIVE_RUN_IDENTITY_MISMATCH')
        if set(c['run_id'] for c in actual['children'])!=set(c['run_id'] for c in original['children']):raise ValueError('NATIVE_CHILD_SET_MISMATCH')
        if any(c.get('status')!='COMPLETED' for c in actual['children'] if c.get('native_invoked')):raise ValueError('NATIVE_INCOMPLETE_CHILD')
    for run in native['runs']:
        for child in run['children']:
            if not child.get('native_invoked'):continue
            childroot=Path(child['output_root']);childseal=json.loads((childroot/'OUTPUT_SEAL.json').read_text())
            for name,digest in childseal['files'].items():pinned({'path':str(childroot/name),'sha256':digest})
        seq=plan['sequences'][run['sequence_id']];combined=stage/'COMBINED'/run['run_id']
        seal=json.loads((combined/'OUTPUT_SEAL.json').read_text())
        for name,digest in seal['files'].items(): pinned({'path':str(combined/name),'sha256':digest})
        if not run['output_epochs']: results.append({'run_id':run['run_id'],'status':'NO_OUTPUT'});continue
        nav=combined/'KF_GINS_Navresult.nav';std=combined/'KF_GINS_STD.txt'
        array=pd.read_csv(nav,sep=r'\s+',header=None,engine='python').to_numpy(float)
        root=stage/'EVALUATION'/run['run_id'];root.mkdir(parents=True,exist_ok=False)
        target=root/'EVAL_NAV_V3.nav';write_transformed_nav(nav,target,transform_nav(array,seq['baseline_median_m']))
        result=evaluate(evaluator=Path(args.evaluator),trace=Path(seq['trace_path']),nav=target,std=std,
            outdir=root/'FROZEN_EVALUATOR',base_time=seq['base_time'],window=seq['window'],
            trace_sha256=seq['trace_sha256'],code_root=Path(args.code),raw_root=Path(args.raw_root),
            clean_root=Path(args.clean_root),instrument=True,consistency_policy='canonical_v2_wgs84_full_support')
        if result['audit'].get('passed') is not True or result['capture']['consistency'].get('passed') is not True:
            unavailable={'run_id':run['run_id'],'sequence_id':run['sequence_id'],'method_id':run['method_id'],
                         'status':'UNAVAILABLE_FROZEN_EVALUATOR_CONSISTENCY_GATED',
                         'reason':'Frozen V3 consistency admission failed; numeric metrics not admitted',
                         'expected_original_output_epochs':run['expected_original_output_epochs'],
                         'actual_native_output_epochs':run['output_epochs']}
            write_json(root/'EVALUATION_RESULT.json',{'row':unavailable,'transport':result});results.append(unavailable)
            print('evaluation unavailable',run['run_id'],flush=True);continue
        errors=pd.read_csv(root/'FROZEN_EVALUATOR/error_series.csv')
        row={'run_id':run['run_id'],'sequence_id':run['sequence_id'],'method_id':run['method_id'],
             'status':'COMPLETED_SEGMENTED','reference':'COMMERCIAL_SHARED_GNSS_VISUAL_INERTIAL_FUSION',
             'expected_original_output_epochs':run['expected_original_output_epochs'],
             'actual_native_output_epochs':run['output_epochs'],'matched_epochs':len(errors),
             'coverage_fraction':len(errors)/run['expected_original_output_epochs'],
             'gap_restart_count':run['gap_restart_count'],'trace_open_count_online':run['trace_open_count'],
             'native_support_fraction':run['output_epochs']/run['expected_original_output_epochs'],
             'unmatched_original_epochs':run['expected_original_output_epochs']-len(errors),
             'missing_motion_reconstructed':False,'causal_gap_effect_claim':False}
        for column,key in [('horizontal_err_m','H_RMSE_m'),('err_u_m','V_RMSE_m'),
                           ('position_3d_err_m','3D_RMSE_m'),('yaw_err_deg','yaw_RMSE_deg')]:
            values=np.asarray(errors[column],float)
            row[key]=float(np.sqrt(np.mean(np.square(values)))) if len(values) else None
        write_json(root/'EVALUATION_RESULT.json',{'row':row,'transport':result});results.append(row)
        print('evaluated',run['run_id'],len(errors),flush=True)
    write_json(stage/'CORRECTED_RESULTS.json',results)
    pd.DataFrame(results).to_csv(stage/'CORRECTED_RESULTS.csv',index=False)
    verify_runtime(stage,Path(args.code),plan)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','native','evaluate'])
    for key in ['stage','code','prior-v3','binary','local-config','evaluator','raw-root','clean-root','build-receipt']:
        p.add_argument('--'+key,required=key in ('stage','code'))
    p.add_argument('--physical-free-bytes',type=int)
    args=p.parse_args();{'prepare':prepare,'native':run_native,'evaluate':evaluate_all}[args.phase](args)


if __name__=='__main__': main()
