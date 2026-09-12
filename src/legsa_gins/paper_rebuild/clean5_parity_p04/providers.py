"""P04 H/O input-only parity providers, with separate pre-freeze raw audits."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import struct
import numpy as np
import yaml
from ...raw_gnss.ubx_raw_binary_rebuilder import iter_ubx_frames, parse_bytes_cell
from ...input_generation.imu_txt_builder import build_process_data_imu_rows, parse_sportmodestate_text
from ...input_generation.imu_txt_builder import euler_rpy_deg_to_matrix as original_rotation, _matvec
from ..clean5_parity.input_audit import csv_rows, decode_receiver, epoch_key, accuracy_audit, verify_raw, stats, stamp
from ..clean5_parity.providers import build_variants
from ..clean5_parity.runtime import resolve, write_json
from ..clean5_imu_parity.providers import serialize_baseline, variant_payloads
from ..clean5_imu_parity.input_audit import gravity_model
from ..horizontal_literature.ext05_provider import (_imu_only_messages, ImuSample,
    euler_rpy_deg_to_matrix as external_rotation, calibrate_static_imu)
from ..manifest import sha256_file
from .rv_remap import POLICY, FOOTNOTE, replay_original_matches, remap_v1

INPUT_KEYS=('imupath','gnsspath','raw_doppler_factor_path','go2_attitude_prior_path','go2_horizontal_velocity_prior_path')
VARIANTS=('V1','V2','V2is')


def alias(path, registry):
    path=Path(path)
    for root,name in [(registry.clean_root,'<CLEAN_ROOT>'),(registry.raw_root,'<RAW_ROOT>'),(registry.code_root,'<CODE_ROOT>')]:
        try:return name+'/'+path.relative_to(root).as_posix()
        except ValueError:pass
    raise ValueError('Source outside registered roots')


def source_spec(path,registry):
    return {'path':alias(path,registry),'sha256':sha256_file(path)}


def checked(spec,registry):
    path=resolve(spec['path'],registry)
    if any(p.is_symlink() for p in (path,*path.parents)) or sha256_file(path)!=spec['sha256']:
        raise ValueError('Pinned source mismatch or symlink: '+str(path))
    return path


def discover_sequence_sources(registry,dataset):
    """Read-only discovery for human preregistration, never generation defaults."""
    if dataset not in ('BY2H','BY2O'):raise ValueError('P04 dataset outside H/O')
    seq=registry.sequences[dataset];root=registry.clean_root/'stages'/seq.stage_id
    configs={}
    for method,profile in [('F01','F01'),('F03','AB0000'),('A04','AB1011')]:
        path=root/'03_RUNTIME_CONFIGS_V2'/(profile+'.yaml')
        configs[method]={'runtime_config':alias(path,registry),'runtime_config_sha256':sha256_file(path)}
    cfg=yaml.safe_load((root/'03_RUNTIME_CONFIGS_V2/AB1011.yaml').read_text())
    manifest_path=root/'02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json';manifest=json.loads(manifest_path.read_text())
    audit_path=root/'03_RUNTIME_CONFIGS_V2/RUNTIME_CONFIG_AUDIT.json';runtime_audit=json.loads(audit_path.read_text())
    if runtime_audit['provider_manifest_sha256']!=sha256_file(manifest_path):raise ValueError('V2/source provider binding mismatch')
    return {'dataset_id':dataset,'data_mode':seq.data_mode,'original_configs':configs,
        'provider_inputs':{k:source_spec(Path(cfg[k]),registry) for k in INPUT_KEYS},
        'provider_manifest':source_spec(manifest_path,registry),
        'a1_gate':source_spec(root/'02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json',registry),
        'a1_baseline_column':'per_epoch.baseline_length_m','a1_epoch_column':'per_epoch.time + base_time',
        'frozen_sequence_contract':source_spec(registry.code_root/'configs/paper_rebuild/clean5'/f'CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml',registry),
        'runtime_config_audit':source_spec(audit_path,registry),
        'frozen_sequence_contract_v2_sha256':runtime_audit['contract_sha256'],
        'base_time':manifest['base_time'],'window_seconds':[cfg['starttime'],cfg['endtime']],
        'v1_rv_policy':'STRICT_FROZEN_VALUES_AND_SAME_ITOW; missing outside window invalid only'}


def gnss_preflight(v0_bytes,status,hp,pvt,base_time,window,*,allow_rv_remap=False):
    lines=v0_bytes.splitlines()
    if len(lines)!=len(status):raise ValueError('Frozen status/GNSS row count mismatch')
    mismatches=[];missing=[]
    for index,(line,s) in enumerate(zip(lines,status)):
        f=line.split();key=epoch_key(s);t=stamp(s,'header.stamp.')-base_time
        if abs(float(f[0])-(stamp(s,'sys_stamp.')-base_time))>1e-6:raise ValueError('Status row lineage mismatch')
        if key not in pvt:
            missing.append({'index':index,'itow_ms':key,'header_time':t,'inside_window':window[0]<=t<=window[1]})
        else:
            actual=[f'{v:.6f}'.encode() for v in pvt[key]['velocity_mps']]
            if f[7:10]!=actual:
                mismatches.append({'index':index,'itow_ms':key,'header_time':t,'sys_time':float(f[0]),
                    'inside_window':window[0]<=t<=window[1],
                    'frozen_RV_tokens':[v.decode() for v in f[7:10]],
                    'same_itow_RV_tokens':[v.decode() for v in actual]})
    acc=accuracy_audit(status,pvt)
    blocked=(bool(mismatches) and not allow_rv_remap) or any(r['inside_window'] for r in missing) or not acc['all_equal_at_status_float32_precision']
    return {'status':'BLOCKED' if blocked else 'PASS','frozen_row_count':len(lines),'status_count':len(status),
        'HP_count':len(hp),'PVT_count':len(pvt),'V1_RV_equal_count':len(lines)-len(missing)-len(mismatches),
        'V1_RV_mismatch_count':len(mismatches),'V1_RV_mismatches':mismatches,
        'V1_missing_same_itow_RV':missing,'status_accuracy':acc,
        'V1_non_time_measurement_bytes_can_remain_equal':not mismatches}


def epoch_inventory(path):
    epochs={name:[] for name in ['UBX-NAV-HPPOSECEF','UBX-NAV-PVT','UBX-NAV-RELPOSNED']}
    for row in csv_rows(path):
        name=row.get('name')
        if name not in epochs:continue
        frames=list(iter_ubx_frames(parse_bytes_cell(row['data'])))
        if len(frames)!=1:raise ValueError('UBX frame invalid')
        frame=frames[0];offset=10 if name!='UBX-NAV-PVT' else 6
        epochs[name].append(struct.unpack_from('<I',frame,offset)[0])
    hp=epochs['UBX-NAV-HPPOSECEF']; hs=set(hp)
    return {'counts':{k:len(v) for k,v in epochs.items()},
        'HP_itow_fraction_ms_counts':{str(k):sum(t%1000==k for t in hp) for k in sorted({t%1000 for t in hp})},
        'HP_interval_ms':stats(np.diff(sorted(hp))),
        'HP_exact_PVT':len(hs&set(epochs['UBX-NAV-PVT'])),
        'HP_exact_RELPOSNED':len(hs&set(epochs['UBX-NAV-RELPOSNED'])),
        'HP_missing_PVT':sorted(hs-set(epochs['UBX-NAV-PVT'])),
        'HP_missing_RELPOSNED':sorted(hs-set(epochs['UBX-NAV-RELPOSNED']))}


def frozen_baseline(gate):
    values=sorted(float(r['baseline_length_m']) for r in gate['per_epoch'])
    if not values or not all(math.isfinite(v) for v in values):raise ValueError('Invalid frozen baseline values')
    legacy_order=values[int(round(.5*(len(values)-1)))]
    if legacy_order!=gate['median_baseline_length_m']:
        raise ValueError('Frozen A1 summary differs from source _percentile semantics')
    return float(np.median(values)), {'standard_median_m':float(np.median(values)),
        'frozen_gate_summary_order_statistic_m':legacy_order,
        'definition':'standard median averages middle two for even n, as P02; frozen gate summary uses round(.5*(n-1)) order statistic',
        'summary_source':'src/legsa_gins/paper_rebuild/providers.py:80-85', 'count':len(values)}


def _prepare(registry,spec,dataset):
    if dataset not in ('BY2H','BY2O') or spec['dataset_id']!=dataset:raise ValueError('Dataset identity mismatch')
    seq=registry.sequences[dataset]
    paths={key:checked(value,registry) for key,value in spec['provider_inputs'].items()}
    manifest=json.loads(checked(spec['provider_manifest'],registry).read_text())
    checked(spec['frozen_sequence_contract'],registry)
    runtime_audit=json.loads(checked(spec['runtime_config_audit'],registry).read_text())
    if runtime_audit['contract_sha256']!=spec['frozen_sequence_contract_v2_sha256']:raise ValueError('C04 V2 contract mismatch')
    for method,source in spec['original_configs'].items():
        checked({'path':source['runtime_config'],'sha256':source['runtime_config_sha256']},registry)
    cfg=yaml.safe_load(resolve(spec['original_configs']['A04']['runtime_config'],registry).read_text())
    if spec['window_seconds']!=[cfg['starttime'],cfg['endtime']] or spec['base_time']!=manifest['base_time']:
        raise ValueError('Frozen window/base mismatch')
    base=spec['base_time'];window=spec['window_seconds']
    raws=[seq.body_path,seq.fix_root/'gnss1-status.csv',seq.fix_root/'gnss1-raw.csv',seq.fix_root/'gnss2-raw.csv']
    raw_sources=verify_raw(registry,seq,raws)
    status=csv_rows(raws[1]);hp,pvt=decode_receiver(raws[2])
    remap_authorized=spec.get('v1_rv_policy')==POLICY
    v0_bytes=paths['gnsspath'].read_bytes()
    gnss=gnss_preflight(v0_bytes,status,hp,pvt,base,window,allow_rv_remap=remap_authorized)
    rv_audit=None;builder_bytes=v0_bytes
    if remap_authorized:
        original_matches=replay_original_matches(raws[1],raws[2],status,pvt,base)
        builder_bytes,rv_audit=remap_v1(v0_bytes,status,pvt,original_matches,base_time=base,window=window)
        rv_audit['source_hashes']=[source_spec(registry.code_root/name,registry) for name in (
            'src/legsa_gins/input_generation/process_data_compat.py',
            'src/legsa_gins/paper_rebuild/ubx_nav_pvt.py',
            'src/legsa_gins/paper_rebuild/final_v23_clean_input.py',
            'src/legsa_gins/paper_rebuild/clean5_parity_p04/rv_remap.py')]
    gate=json.loads(checked(spec['a1_gate'],registry).read_text());a1=gate['per_epoch']
    baseline,baseline_definition=frozen_baseline(gate)
    a1_times=[r['time']+base for r in a1]
    mapped={round(t*1000) for t in a1_times};keys={epoch_key(s) for s in status if round(stamp(s,'header.stamp.')*1000) in mapped}
    print(dataset+': IMU raw byte and calibration audit',flush=True)
    baseline_rows,original_report=build_process_data_imu_rows(seq.body_path,base_time=base)
    baseline_text=paths['imupath'].read_text();reconstructed=serialize_baseline(baseline_rows)
    if reconstructed!=baseline_text:raise ValueError('Frozen sequence IMU byte parity FAILED')
    frames=parse_sportmodestate_text(seq.body_path);rotation=original_rotation(-1,0,0)
    indices=[i for i in range(1,len(frames)) if 0<frames[i]['timestamp']-frames[i-1]['timestamp']<=.1]
    for row,i in zip(baseline_rows,indices):
        a=frames[i]['accelerometer'];row['_current_specific_force_frd']=_matvec(rotation,[a[0],-a[1],-a[2]])
    norms=[math.sqrt(sum(v*v for v in f['accelerometer'])) for f in frames[:1000]]
    if len(norms)!=1000:raise ValueError('Incomplete first 1000 scale interval')
    gravity=gravity_model(cfg['initpos']);mean=float(np.mean(norms));scale=gravity['g_local_mps2']/mean
    transform=external_rotation(-1,0,0)@np.diag([1.,-1.,-1.])
    samples=tuple(ImuSample(t,transform@g,transform@a) for t,g,a in _imu_only_messages(seq.body_path))
    if len(samples)!=len(frames):raise ValueError('External parser count mismatch')
    calibration=calibrate_static_imu(samples,latitude_deg=cfg['initpos'][0],height_m=cfg['initpos'][2])
    cal={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in asdict(calibration).items()}
    imu_payloads,imu_audit=variant_payloads(baseline_rows=baseline_rows,baseline_text=baseline_text,
        external_times=[s.absolute_time_unix_seconds for s in samples],external_gyro=[s.angular_rate_frd_radps for s in samples],
        external_force=[s.specific_force_frd_mps2 for s in samples],external_bias=calibration.gyro_bias_frd_radps,
        scale_factor=scale,base_time=base)
    gnss_payloads=None;build_audit=None
    if gnss['status']=='PASS':
        gnss_payloads,build_audit=build_variants(builder_bytes,status,hp,pvt,base_time=base,window=window,a1_source_times=a1_times)
        if rv_audit is not None:
            build_audit['v1_non_time_measurement_tokens_byte_equal']=rv_audit['non_time_measurement_tokens_byte_equal_to_true_V0']
            build_audit['byte_equality_reference']='true frozen V0, not in-memory RV-remapped builder argument'
            build_audit['v1_RV_remap']=rv_audit
            build_audit['time_term_footnote']=FOOTNOTE
    audit={'dataset_id':dataset,'data_mode':seq.data_mode,'synthetic_data_used':False,'semisynthetic_data_used':False,
        'trace_used_online':False,'receiver_imu_as_body_imu':False,'final_v23_output_solver_input':False,'LegSA_output_solver_input':False,
        'per_case_tuning':False,'output_only_correction':False,'epoch_deleted_for_metric':False,'old_runtime_input_count':0,
        'provider_file_generations':0,'solver_invocations':0,'evaluator_invocations':0,'raw_source_hashes':raw_sources,
        'source_specs':spec,'gnss':gnss,'gnss_provider_audit':build_audit,
        'v1_RV_remap':rv_audit,'rv_remap_audit':rv_audit,'time_term_footnote':FOOTNOTE if remap_authorized else None,
        'epoch_inventory':{name:epoch_inventory(seq.fix_root/(name+'-raw.csv')) for name in ['gnss1','gnss2']},
        'baseline_median_m':baseline,'half_baseline_m':baseline/2,'baseline_definition':baseline_definition,'frozen_A1_count':len(a1),
        'A1_status_mapped_count':len(keys),'A1_HP_mapped_count':len(keys&set(hp)),
        'A1_missing_HP_keys':sorted(keys-set(hp)),'A1_source':spec['a1_gate'],
        'baseline_IMU_byte_equal':True,'baseline_IMU_sha256':sha256_file(paths['imupath']),
        'baseline_IMU_in_memory_sha256':hashlib.sha256(reconstructed.encode()).hexdigest(),
        'baseline_IMU_report':original_report,'imu_variant_audit':imu_audit,'gravity_spec':gravity,
        'g_local_mps2':gravity['g_local_mps2'],'mean_norm_first1000_mps2':mean,'s':scale,
        'external_5s_calibration':cal,'external_original_runner_text':'UNAVAILABLE; previous ZOH maintained-source intervention only',
        'status':'BLOCKED_V1_RV_CONFLICT' if gnss['status']!='PASS' else 'PASS_INPUT_GATES'}
    return audit,gnss_payloads,imu_payloads['V2is']


def _guard_stage(registry,stage_root):
    stage=Path(stage_root)
    expected=registry.clean_root/'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/12_PARITY_GENERALIZATION'
    if stage!=expected or any(p.is_symlink() for p in (stage,*stage.parents)):
        raise ValueError('Outside authorized P04 stage')
    return stage


def preflight(*,registry,stage_root,source_specification,dataset,code_commit):
    stage=_guard_stage(registry,stage_root)
    filename=('P04B_'+dataset+'_RV_REMAP_PREFLIGHT.json') if source_specification.get('v1_rv_policy')==POLICY else dataset+'_PROVIDER_PREFLIGHT.json'
    if (stage/'00_PREFLIGHT'/filename).exists():
        raise FileExistsError('Existing provider preflight is immutable')
    audit,_,_=_prepare(registry,source_specification,dataset)
    audit['code_commit']=code_commit;audit['provider_source_sha256']=sha256_file(Path(__file__))
    out=Path(stage_root)/'00_PREFLIGHT';out.mkdir(parents=True,exist_ok=True)
    write_json(out/filename,audit)
    return audit


def _counts(payload,window):
    rows=np.asarray([[float(v) for v in line.split()] for line in payload.splitlines()])
    out={}
    for label,sel in [('full',rows),('closed_window',rows[(rows[:,0]>=window[0])&(rows[:,0]<=window[1])])]:
        out[label]={'rows':len(sel),'position_valid':int(sel[:,15].sum()),'velocity_valid':int(sel[:,16].sum()),'yaw_valid':int(sel[:,17].sum())}
    return out


def generate_providers(*,registry,stage_root,contract,code_commit,dataset):
    stage=_guard_stage(registry,stage_root);p04=contract['p04'];spec=p04['sequences'][dataset]
    if p04.get('execution_ready') is not True or spec.get('execution_ready') is not True:
        raise ValueError('P04 preregistered source execution gate is not ready')
    if stage!=resolve(p04['stage_root'],registry) or any(p.is_symlink() for p in (stage,*stage.parents)):
        raise ValueError('P04 output root mismatch')
    audit,gnss,imu=_prepare(registry,spec,dataset)
    if audit['status']!='PASS_INPUT_GATES':raise ValueError('P04 preflight blocked: '+dataset)
    if 'scale_calibration' not in spec or spec['scale_calibration']['s']!=audit['s'] or spec['scale_calibration']['g_local_mps2']!=audit['g_local_mps2']:
        raise ValueError('Scale differs from preregistration')
    output=stage/dataset/'02_PARITY_PROVIDERS';output.mkdir(parents=True,exist_ok=False)
    common={k:audit[k] for k in ('dataset_id','data_mode','synthetic_data_used','semisynthetic_data_used','trace_used_online',
        'receiver_imu_as_body_imu','final_v23_output_solver_input','LegSA_output_solver_input','per_case_tuning','output_only_correction',
        'epoch_deleted_for_metric','old_runtime_input_count','raw_source_hashes','baseline_median_m')}
    common.update(v1_RV_remap=audit['v1_RV_remap'],rv_remap_audit=audit['rv_remap_audit'],time_term_footnote=audit['time_term_footnote'],code_commit=code_commit,config_hash=hashlib.sha256(json.dumps(p04,sort_keys=True).encode()).hexdigest())
    variants={}
    for variant in VARIANTS:
        root=output/variant;root.mkdir()
        inputs={k:{'path':str(checked(v,registry)),'sha256':v['sha256']} for k,v in spec['provider_inputs'].items()}
        if variant!='V2is':
            gp=root/'PARITY.gnss'
            with gp.open('xb') as f:f.write(gnss[variant])
            inputs['gnsspath']={'path':str(gp),'sha256':sha256_file(gp)}
        else:
            inputs['gnsspath']=dict(variants['V2']['providers']['gnsspath'])
            ip=root/'PARITY_IMU.imu'
            with ip.open('x') as f:f.write(imu)
            inputs['imupath']={'path':str(ip),'sha256':sha256_file(ip)}
        v={**common,'variant_id':variant,'provider_family':f'CLEAN5_PARITY_P04_{dataset}_{variant}',
            'providers':inputs,'counts':_counts(gnss['V2' if variant=='V2is' else variant],spec['window_seconds'])}
        write_json(root/'PROVIDER_MANIFEST.json',v);variants[variant]=v
    audit={**audit,'phase':'provider_generation','provider_file_generations':3,
           'generated_payloads':'V1 GNSS18, V2 GNSS18, V2is IMU; V2is reuses V2 GNSS18',
           'code_commit':code_commit}
    bundle={**common,'variants':variants,'audit':audit}
    write_json(output/'PROVIDER_AUDIT.json',audit)
    write_json(output/'PARITY_PROVIDER_BUNDLE.json',bundle)
    return bundle
