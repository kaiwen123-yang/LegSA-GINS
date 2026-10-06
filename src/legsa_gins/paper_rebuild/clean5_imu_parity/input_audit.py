"""Hash-locked raw IMU audits. No provider, solver, evaluator or reference reads."""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path
import numpy as np
import yaml
from ...datasets.by2.go2_body_state_parser import parse_go2_body_state_text
from ...input_generation.imu_txt_builder import parse_sportmodestate_text
from ..clean5_parity.input_audit import verify_raw
from ..manifest import sha256_file

NOISE_KEYS = ('arw','vrw','gbstd','abstd','gsstd','asstd','corrtime')
SOURCE_FILES = (
    'src/legsa_gins/datasets/by2/go2_body_state_parser.py',
    'src/legsa_gins/input_generation/imu_txt_builder.py',
    'src/legsa_gins/paper_rebuild/clean5_imu_parity/input_audit.py',
    'cpp/legsa_v23_port_core/src/config/port_config_loader.cpp',
    'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp')


def gravity_model(frozen_initpos):
    """NGA WGS84 defining constants plus AHRS official normal-gravity formula."""
    latitude,longitude,height=map(float,frozen_initpos)
    if not (-90<=latitude<=90) or not all(math.isfinite(x) for x in [latitude,longitude,height]):
        raise ValueError('Invalid frozen geodetic position')
    a=6378137.; inverse_f=298.257223563; gm=3.986004418e14; omega=7.292115e-5
    ge=9.7803253359; k=.00193185265241
    f=1/inverse_f; e2=f*(2-f); b=a*(1-f); m=omega**2*a*a*b/gm
    sin2=math.sin(math.radians(latitude))**2
    g0=ge*(1+k*sin2)/math.sqrt(1-e2*sin2)
    g=g0*(1-2/a*(1+f+m-2*f*sin2)*height+3*height*height/(a*a))
    return {'g_local_mps2':g,'g_ellipsoid_surface_mps2':g0,'frozen_initpos':list(frozen_initpos),
        'height_definition':'ellipsoidal height in metres; frozen initpos[2]',
        'constants':{'a_m':a,'inverse_flattening':inverse_f,'GM_m3ps2':gm,'omega_radps':omega,
                     'ge_mps2':ge,'k':k,'derived_e2':e2,'derived_b_m':b,'derived_m':m},
        'formula':'g0=ge*(1+k*sin(phi)^2)/sqrt(1-e2*sin(phi)^2); g(h)=g0*(1-2/a*(1+f+m-2*f*sin(phi)^2)*h+3*h^2/a^2)',
        'defining_constants_source':'https://earth-info.nga.mil/?action=wgs84&dir=wgs84',
        'formula_source':'https://ahrs.readthedocs.io/en/latest/geodesy/wgs84.html',
        'source_boundary':'NGA defining parameters and AHRS official implementation documentation; NGA registered PDF not downloaded or directly formula-verified'}


def stats(values):
    a=np.asarray(values,dtype=float)
    finite=a[np.isfinite(a)]
    result={'n':len(a),'finite_n':len(finite),'unavailable_n':len(a)-len(finite)}
    if not len(finite):return {**result,'status':'UNAVAILABLE'}
    return {**result,'status':'AVAILABLE','mean':float(finite.mean()),
        'std_population':float(finite.std()),'median':float(np.median(finite)),
        'min':float(finite.min()),'max':float(finite.max()),
        'p05':float(np.quantile(finite,.05)),'p95':float(np.quantile(finite,.95))}


def parse_with_temperature(path):
    """Existing raw parser exposes temperature; assert wrapper value identity."""
    original=parse_go2_body_state_text(path)
    maintained=parse_sportmodestate_text(path)
    extended=[]
    for index,r in enumerate(original):
        keys=['stamp_sec','stamp_nanosec','gyro_x','gyro_y','gyro_z','acc_x','acc_y','acc_z']
        if any(r.get(k) is None or not math.isfinite(float(r[k])) for k in keys):continue
        value={'stamp_sec':int(r['stamp_sec']),'stamp_nanosec':int(r['stamp_nanosec']),
            'timestamp':int(r['stamp_sec'])+int(r['stamp_nanosec'])*1e-9,
            'gyroscope':[float(r[k]) for k in ['gyro_x','gyro_y','gyro_z']],
            'accelerometer':[float(r[k]) for k in ['acc_x','acc_y','acc_z']]}
        extended.append((value,r.get('temperature'),index))
    if [r[0] for r in extended]!=maintained:
        raise ValueError('Temperature parser/wrapper per-frame exact identity failed')
    if len(extended)<1000:
        raise ValueError('Fewer than 1000 complete IMU frames')
    frames=[]
    t0=extended[0][0]['stamp_sec']*10**9+extended[0][0]['stamp_nanosec']
    for index,(r,temp,source_index) in enumerate(extended):
        ns=r['stamp_sec']*10**9+r['stamp_nanosec']
        frames.append({'frame_index':index,'raw_message_index':source_index,
            'timestamp_ns':ns,'timestamp':r['timestamp'],'time':(ns-t0)*1e-9,
            'norm_mps2':math.sqrt(sum(x*x for x in r['accelerometer'])),
            'imu_state.temperature':float(temp) if temp is not None and math.isfinite(float(temp)) else None,
            'gyro_norm_radps':math.sqrt(sum(x*x for x in r['gyroscope']))})
    return frames,{'parser_identity_exact':True,'fields_asserted':['timestamp','accelerometer','gyroscope'],
        'raw_parsed_messages':len(original),'retained_complete_frames':len(frames),
        'incomplete_messages':len(original)-len(frames),
        'temperature_parser':'existing parse_go2_body_state_text: imu_state.temperature',
        'no_new_parser':True,'maintained_parser_changed':False}


def scale_from_frames(frames,g_local):
    if len(frames)<1000 or not math.isfinite(g_local) or g_local<=0:raise ValueError('Invalid scale inputs')
    first=stats([r['norm_mps2'] for r in frames[:1000]])
    return {'g_local_mps2':g_local,'mean_norm_first_1000_mps2':first['mean'],
        's':g_local/first['mean'],'first_1000_norm_stats':first,
        'definition':'s = g_local / mean(norm(a_i), i=0..999); not norm(mean(a_i))',
        'selection':'fixed first 1000 complete BY2 frames; no results-based selection'}


def compute_scale_factor(body_path,g_local):
    """Reusable B3 recomputation API; caller verifies raw lock before this read."""
    frames,identity=parse_with_temperature(body_path)
    return {**scale_from_frames(frames,g_local),'parser_identity':identity,
        'body_sha256':sha256_file(body_path)}


def dt_audit(frames,g_local):
    ns=np.asarray([r['timestamp_ns'] for r in frames],dtype=np.int64)
    dt=np.diff(ns).astype(float)*1e-9
    if np.any(dt<0):raise ValueError('Raw frame time decreases')
    median=float(np.median(dt));jitter=dt-median
    return {'timestamp_basis':'exact integer stamp.sec*1e9+stamp.nanosec differences',
        'dt_seconds':stats(dt),'median_dt_seconds':median,
        'absolute_deviation_gt_1ms_count':int(np.sum(np.abs(jitter)>.001)),
        'absolute_deviation_gt_1ms_fraction':float(np.mean(np.abs(jitter)>.001)),
        'nonpositive_dt_count':int(np.sum(dt<=0)),
        'equivalent_dv_signed_mps':stats(g_local*jitter),
        'equivalent_dv_absolute_mps':stats(np.abs(g_local*jitter)),
        'equivalent_dv_rms_mps':float(np.sqrt(np.mean((g_local*jitter)**2))),
        'formula':'delta_dt_i=dt_i-median(dt); equivalent_delta_v_i=g_local*delta_dt_i',
        'interpretation':'timestamp jitter magnitude proxy, not independent physical sensor noise',
        'g_local_mps2':g_local}


def sliding_windows(frames,width=10.,step=1.):
    times=np.asarray([r['time'] for r in frames]);last=float(times[-1]);out=[]
    if width<=0 or step<=0:raise ValueError('Invalid window schedule')
    # Complete windows plus each scheduled terminal partial window, explicitly
    # classified; never silently drop a message due to a window statistic.
    for start in np.arange(0,last+1e-12,step):
        end=float(start+width);full=end<=last
        selected=[frames[i] for i in np.flatnonzero((times>=start)&(times<end))]
        norms=stats([r['norm_mps2'] for r in selected]);temp=stats([r['imu_state.temperature'] if r['imu_state.temperature'] is not None else math.nan for r in selected])
        row={'window_start':float(start),'nominal_window_end':end,'available_end':min(end,last),
            'window_status':'FULL' if full else 'PARTIAL_TERMINAL','frame_count':len(selected)}
        for prefix,values in [('norm_mps2',norms),('temperature',temp)]:
            row.update({prefix+'_'+k:v for k,v in values.items()})
        out.append(row)
    return out


def temperature_audit(frames):
    present=[r for r in frames if r['imu_state.temperature'] is not None]
    temp=np.asarray([r['imu_state.temperature'] for r in present],float)
    norm=np.asarray([r['norm_mps2'] for r in present],float)
    correlation=float(np.corrcoef(temp,norm)[0,1]) if len(temp)>1 and temp.std()>0 and norm.std()>0 else None
    return {'temperature':stats([r['imu_state.temperature'] if r['imu_state.temperature'] is not None else math.nan for r in frames]),
        'pearson_temperature_vs_norm':correlation,
        'correlation_status':'AVAILABLE' if correlation is not None else 'UNAVAILABLE_CONSTANT_OR_MISSING',
        'interpretation':'observed variation only; movement norm changes alone do not identify scale or temperature causation',
        'temperature_source_field':'imu_state.temperature','temperature_units':'raw reported unit; no conversion'}


def noise_audit(config_path):
    text=Path(config_path).read_text();cfg=yaml.safe_load(text)
    tokens={k:next(line for line in text.splitlines() if line.startswith(k+':')) for k in NOISE_KEYS}
    scales={'arw':math.pi/180/60,'vrw':1/60,'gbstd':math.pi/180/3600,
            'abstd':1e-5,'gsstd':1e-6,'asstd':1e-6}
    converted={k:[float(x)*scales[k] for x in cfg[k]] for k in scales}
    tau=float(cfg['corrtime'])*3600; sigma=converted['abstd'][0]
    if tau<=0 or sigma<=0:raise ValueError('Invalid frozen OU prior')
    times=[]
    for t in [1.,10.,274.]:
        times.append({'T_seconds':t,'free_delta_v_mps':.3*t,'free_delta_p_m':.15*t*t,
            'OU_mean_decay':math.exp(-t/tau),'OU_variance_if_initial_bias_fixed_zero':sigma*sigma*(1-math.exp(-2*t/tau)),
            'OU_mean_bias_if_initial_0p3_mps2':.3*math.exp(-t/tau)})
    return {'frozen_config_sha256':sha256_file(config_path),'parameter_tokens':tokens,
        'converted_values':converted,'unit_multipliers':scales,'corrtime_seconds':tau,
        'arw_units':'deg/sqrt(hour) -> rad/sqrt(s)','vrw_units':'m/s/sqrt(hour) -> m/s/sqrt(s)',
        'gbstd_units':'deg/hour -> rad/s','abstd_units':'mGal -> m/s2',
        'gsstd_asstd_units':'ppm -> dimensionless','corrtime_units':'hour -> second',
        'bias_0p3_over_ab_sigma':.3/sigma,'ab_stationary_sigma_mps2':sigma,
        'P_a_stationary_m2ps4':sigma*sigma,'Qc_a_m2ps5':2*sigma*sigma/tau,
        'OU_formulas':'db=-b/tau dt + sqrt(2*sigma^2/tau)dW; E[b(T)|b0]=b0 exp(-T/tau); P(T)=sigma^2+(P0-sigma^2)exp(-2T/tau)',
        'theory_times':times,'free_integration_formulas':'delta_v=0.3*T; delta_p=0.15*T^2, without filter/gravity/attitude feedback',
        'native_discretization':'Phi=I+F*dt; Qd trapezoid. Exact OU exponentials above are theoretical prior quantities, not native exact discretization.',
        'scale_prior_policy':'Frozen initial scale std and scale driving std are zero; zero scale covariance/driving noise does not absorb a scale error.',
        'source_locations':{'unit_conversion':'cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:564-581',
            'initial_covariance':'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:53-56,766-769',
            'Qc':'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:772-782',
            'F_Phi_Qd':'cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:808-825'}}


def _write_json(path,data):
    with Path(path).open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')


def _write_csv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def run_input_audits(*,registry,stage_root,frozen_config,gravity_spec,code_git_base):
    """Generate only B_* audit files. gravity_spec must supply source-backed g."""
    stage=Path(stage_root).resolve()
    if stage.parent!=registry.clean_root.resolve()/'stages' or stage.name!='CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF':
        raise ValueError('Outside authorized P03 stage')
    out=stage/'10_IMU_PROCESSING/00_AUDITS';out.mkdir(parents=True,exist_ok=True)
    if list(out.glob('B_*')):raise FileExistsError('B audit outputs already exist; no overwrite')
    g=float(gravity_spec['g_local_mps2']);cfg=yaml.safe_load(Path(frozen_config).read_text())
    if list(cfg['initpos'])!=list(gravity_spec['frozen_initpos']):raise ValueError('Gravity/frozen initpos mismatch')
    common={'data_mode':'real_raw_input_audit','synthetic_data_used':False,'semisynthetic_data_used':False,
        'trace_used_online':False,'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,
        'LegSA_output_solver_input':False,'per_case_tuning':False,'output_only_correction':False,
        'epoch_deleted_for_metric':False,'old_runtime_input_count':0,'provider_generations':0,'solver_invocations':0,
        'evaluator_invocations':0,'code_git_base':code_git_base,
        'source_hashes':{p:sha256_file(registry.code_root/p) for p in SOURCE_FILES},
        'gravity_spec':gravity_spec,'frozen_config_sha256':sha256_file(frozen_config)}
    result={**common,'sequences':{}}
    for name,seq in registry.sequences.items():
        print(f'P03 B input audit {name}: raw lock and parse',flush=True)
        source=verify_raw(registry,seq,[seq.body_path]);frames,identity=parse_with_temperature(seq.body_path)
        windows=sliding_windows(frames)
        item={'data_mode':seq.data_mode,'raw_sources':source,'parser_identity':identity,
            'B1':dt_audit(frames,g),'B2':{'norm_full':stats([r['norm_mps2'] for r in frames]),
                'temperature':temperature_audit(frames),'full_windows':sum(r['window_status']=='FULL' for r in windows),
                'partial_terminal_windows':sum(r['window_status']=='PARTIAL_TERMINAL' for r in windows),
                'window_width_seconds':10,'window_step_seconds':1,'window_interval':'[start,start+10)',
                'no_stationarity_selection':True},'first_1000':scale_from_frames(frames,g)['first_1000_norm_stats']}
        if name=='BY2':result['B3']=scale_from_frames(frames,g)
        _write_csv(out/f'B_{name}_FRAMES.csv',frames)
        _write_csv(out/f'B_{name}_TEMPERATURE.csv',[{k:r[k] for k in ['frame_index','timestamp_ns','time','imu_state.temperature']} for r in frames])
        _write_csv(out/f'B_{name}_WINDOWS_10S.csv',windows)
        _write_json(out/f'B_{name}_AUDIT.json',{**common,**item})
        result['sequences'][name]=item
    result['B4']=noise_audit(frozen_config)
    _write_json(out/'B_INPUT_AUDIT.json',result)
    _write_json(out/'B_SCALE_FACTOR.json',{**common,**result['B3']})
    return result
