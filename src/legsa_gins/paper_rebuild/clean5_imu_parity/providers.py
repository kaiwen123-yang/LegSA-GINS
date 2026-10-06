"""P03 input-only IMU interventions; all non-IMU V2 inputs remain immutable."""
from __future__ import annotations
from dataclasses import asdict
import hashlib,json,math
from pathlib import Path
import numpy as np
import yaml
from ...input_generation.imu_txt_builder import build_process_data_imu_rows,parse_sportmodestate_text
from ..horizontal_literature.ext05_provider import build_imu_only_provider,calibrate_static_imu
from ..clean5_parity.input_audit import verify_raw
from ..clean5_parity.runtime import resolve,write_json
from ..manifest import sha256_file
from .input_audit import gravity_model

VARIANTS=('V2i','V2s','V2is')
IMU_FIELDS=('dtheta_x','dtheta_y','dtheta_z','dvel_x','dvel_y','dvel_z')


def frozen_token(value, precision):
    # process_data_compat.py:186-190 first writes .12g; the frozen final-input
    # reader then parses float before its .6f/.8f output serialization.
    return format(float(format(value, '.12g')), '.'+str(precision)+'f')


def serialize_baseline(rows):
    return ''.join(frozen_token(r['time'],6)+' '+
                   ' '.join(frozen_token(r[k],8) for k in IMU_FIELDS)+'\n' for r in rows)


def variant_payloads(*,baseline_rows,baseline_text,external_times,external_gyro,external_force,
                     external_bias,scale_factor,base_time):
    """Integrate unrounded forces; retain frozen times and unaffected gyro tokens."""
    if not math.isfinite(scale_factor) or scale_factor<=0:raise ValueError('Invalid scale factor')
    if serialize_baseline(baseline_rows)!=baseline_text:raise ValueError('V2 raw-to-frozen IMU byte reconstruction failed')
    tokens=[line.split() for line in baseline_text.splitlines()]
    times=np.asarray(external_times,float);gyro=np.asarray(external_gyro,float);force=np.asarray(external_force,float)
    if gyro.shape!=force.shape or gyro.shape!=(len(times),3) or not np.isfinite(gyro).all() or not np.isfinite(force).all():
        raise ValueError('Invalid external raw projection')
    dt=np.diff(times)
    if not np.isfinite(times).all() or np.any(dt<=0):raise ValueError('External IMU timeline invalid')
    indices=np.flatnonzero((dt>0)&(dt<=.1))+1
    if len(indices)!=len(tokens):raise ValueError('External/frozen IMU interval count mismatch')
    out={v:[] for v in VARIANTS}
    for row_index,k in enumerate(indices):
        original=tokens[row_index];base=baseline_rows[row_index]
        if len(original)!=7 or original[0]!=frozen_token(times[k]-base_time,6):raise ValueError('IMU timestamp identity mismatch')
        if float(base['dt'])!=float(dt[k-1]):raise ValueError('Raw measured dt disagreement')
        dtheta=(gyro[k-1]-np.asarray(external_bias,float))*dt[k-1]
        dvel=force[k-1]*dt[k-1]
        # V2s scales original unrounded current-sample force before integration.
        # The generator supplies the force before increment serialization.
        current_force=np.asarray(base['_current_specific_force_frd'],float)
        dvel_s=(current_force*scale_factor)*dt[k-1]
        dvel_is=(force[k-1]*scale_factor)*dt[k-1]
        itokens=[original[0]]+[frozen_token(x,8) for x in (*dtheta,*dvel)]
        stokens=original[:4]+[frozen_token(x,8) for x in dvel_s]
        istokens=itokens[:4]+[frozen_token(x,8) for x in dvel_is]
        for v,t in [('V2i',itokens),('V2s',stokens),('V2is',istokens)]:out[v].append(' '.join(t)+'\n')
    payloads={v:''.join(lines) for v,lines in out.items()}
    if any(a.split()[:4]!=b.split()[:4] for a,b in zip(payloads['V2s'].splitlines(),baseline_text.splitlines())):
        raise ValueError('V2s modified timestamp/gyro tokens')
    if any(a.split()[:4]!=b.split()[:4] for a,b in zip(payloads['V2is'].splitlines(),payloads['V2i'].splitlines())):
        raise ValueError('V2is modified V2i timestamp/gyro tokens')
    return payloads,{'frozen_v2_reconstruction_byte_equal':True,'row_count':len(tokens),
        'all_variant_timestamp_tokens_equal_V2':True,'V2s_timestamp_and_gyro_tokens_equal_V2':True,
        'V2is_timestamp_and_gyro_tokens_equal_V2i':True,'skipped_interval_count':len(dt)-len(indices),
        'integration_dt':'raw measured difference, not nominal imudatarate; frozen timestamp tokens retained',
        'serialization':'original .12g intermediate parse, then .6f time and .8f increments',
        'V2i_sampling':'previous external FRD sample and exact 5s input-only gyro mean',
        'scale_applied_to':'unrounded three-axis FRD specific force before multiplication by measured dt'}


def _json_calibration(calibration):
    return {k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in asdict(calibration).items()}


def generate_providers(*,registry,stage_root,contract,code_commit):
    stage=Path(stage_root);spec=contract['p03'];reference=resolve(spec['reference_stage_root'],registry)
    if stage!=resolve(spec['stage_root'],registry) or stage.parent!=reference:raise ValueError('P03 output root mismatch')
    if any(p.is_symlink() for p in (stage,*stage.parents)):raise ValueError('Symlink output root')
    source_bundle=reference/'02_PARITY_PROVIDERS/PARITY_PROVIDER_BUNDLE.json'
    if sha256_file(source_bundle)!=spec['reference_provider_bundle_sha256']:raise ValueError('P02 bundle changed')
    frozen=json.loads(source_bundle.read_text());inputs=frozen['variants']['V2']['providers']
    for item in inputs.values():
        if sha256_file(item['path'])!=item['sha256']:raise ValueError('P02 V2 provider changed')
    for rel,digest in spec['shared_source_sha256'].items():
        if sha256_file(registry.code_root/rel)!=digest:raise ValueError('Preprocessing source changed: '+rel)
    cfg_path=resolve(contract['frozen_runtime']['original_configs']['A04']['runtime_config'],registry)
    if sha256_file(cfg_path)!=contract['frozen_runtime']['original_configs']['A04']['runtime_config_sha256']:
        raise ValueError('Frozen A04 config changed')
    cfg=yaml.safe_load(cfg_path.read_text());body=registry.sequences['BY2'].body_path
    raw_sources=verify_raw(registry,registry.sequences['BY2'],[body])
    baseline_rows,baseline_audit=build_process_data_imu_rows(body,base_time=contract['evaluation']['base_time'])
    frames=parse_sportmodestate_text(body)
    # Import the same maintained transform to reproduce original arithmetic order.
    from ...input_generation.imu_txt_builder import euler_rpy_deg_to_matrix,_matvec
    rotation=euler_rpy_deg_to_matrix(-1,0,0)
    indices=[i for i in range(1,len(frames)) if 0<frames[i]['timestamp']-frames[i-1]['timestamp']<=.1]
    if len(indices)!=len(baseline_rows):raise ValueError('Original builder interval mapping mismatch')
    for row,i in zip(baseline_rows,indices):
        a=frames[i]['accelerometer'];row['_current_specific_force_frd']=_matvec(rotation,[a[0],-a[1],-a[2]])
    gravity=gravity_model(cfg['initpos'])
    norms=[math.sqrt(sum(x*x for x in f['accelerometer'])) for f in frames[:1000]]
    if len(norms)!=1000:raise ValueError('Scale calibration requires first 1000 frames')
    mean_norm=float(np.asarray(norms).mean());scale=gravity['g_local_mps2']/mean_norm
    if scale!=spec['scale_calibration']['s'] or gravity['g_local_mps2']!=spec['scale_calibration']['g_local_mps2']:
        raise ValueError('Preregistered input scale changed')
    external_spec=spec['external_preprocessing'];summary_path=resolve(external_spec['native_summary'],registry)
    if sha256_file(summary_path)!=external_spec['native_summary_sha256']:raise ValueError('Frozen calibration summary changed')
    native=json.loads(summary_path.read_text());origin=native['provider']['position']['fixed_ned_origin_geodetic_deg_m']
    external_samples,external_audit,_=build_imu_only_provider(body,raw_root=registry.raw_root,
                by2_hash_lock=registry.clean_root/'01_RAW_HASH_LOCK/BY2_HASH_LOCK.csv')
    calibration=calibrate_static_imu(external_samples,latitude_deg=origin[0],height_m=origin[2])
    cal=_json_calibration(calibration)
    if cal!=native['provider']['calibration']:raise ValueError('Raw 5s calibration differs from frozen external summary')
    payloads,comparison=variant_payloads(baseline_rows=baseline_rows,
        baseline_text=Path(inputs['imupath']['path']).read_text(),
        external_times=[r.absolute_time_unix_seconds for r in external_samples],
        external_gyro=[r.angular_rate_frd_radps for r in external_samples],
        external_force=[r.specific_force_frd_mps2 for r in external_samples],
        external_bias=calibration.gyro_bias_frd_radps,scale_factor=scale,base_time=contract['evaluation']['base_time'])
    output=stage/'02_PARITY_PROVIDERS';output.mkdir(exist_ok=False)
    base={'data_mode':'real_by2_raw','synthetic_data_used':False,'semisynthetic_data_used':False,
        'trace_used_online':False,'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,
        'LegSA_output_solver_input':False,'per_case_tuning':False,'output_only_correction':False,
        'epoch_deleted_for_metric':False,'old_runtime_input_count':0,'code_commit':code_commit,
        'config_hash':hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest(),
        'raw_source_hashes':raw_sources,'baseline_median_m':frozen['baseline_median_m'],
        'V2_inputs_sha256':{k:v['sha256'] for k,v in inputs.items()},'shared_source_sha256':spec['shared_source_sha256']}
    audit={**comparison,'frozen_builder_report':baseline_audit,'external_provider_report':external_audit,
        'external_calibration_reproduced_exactly':True,'external_calibration':cal,'s':scale,
        'g_local_mps2':gravity['g_local_mps2'],'mean_norm_first_1000_mps2':mean_norm,
        'calibration_role':'input-only sensor calibration, same role as existing first-1000 gyro zero-bias',
        'exact_frozen_runner_text':external_spec['exact_frozen_runner_text'],
        'external_full_mechanization_reproduced':False}
    variants={}
    for variant,text in payloads.items():
        root=output/variant;root.mkdir();path=root/'PARITY_IMU.imu'
        with path.open('x') as f:f.write(text)
        providers={k:dict(v) for k,v in inputs.items()}
        providers['imupath']={'path':str(path),'sha256':sha256_file(path),'row_count':comparison['row_count']}
        variants[variant]={'variant_id':variant,'provider_family':'CLEAN5_PARITY_'+variant,'providers':providers}
        write_json(root/'PROVIDER_MANIFEST.json',{**base,**variants[variant],'audit':audit})
    bundle={**base,'variants':variants,'audit':audit}
    write_json(output/'IMU_PROVIDER_AUDIT.json',{**base,**audit})
    write_json(output/'PARITY_PROVIDER_BUNDLE.json',bundle)
    return bundle
