#!/usr/bin/env python3
"""Prepare the complete preregistered 45-case x 3-method repaired replay.
No estimator, evaluator, trace read, provider generation, or metric selection.
"""
from pathlib import Path
import argparse, csv, hashlib, json, re, shutil, subprocess
import numpy as np
import pandas as pd
import yaml
from legsa_gins.paper_rebuild.imu_contract_repair import (
    STAGE, clone_fields, pinned, verify_runtime, write_json)
from legsa_gins.paper_rebuild.hext.sequence_paths import REGISTRY, CALIBRATED_CONTRACT

METHODS={'F04':'AB1111','A03':'AB0111','A06':'AB1110'}
PROTOCOL='V3_CLAIM_SUBSET_EXPLICIT_IMU_DURATION'
CASES={f'{kind}_{duration}s_seed_{seed:02d}' for kind,durations in
       [('D61',(10,20,30)),('D62',(10,20))] for duration in durations for seed in range(9)}
PAIR_FIELDS={'algorithm_id','ablation_variant','run_id','run_label','outputpath'}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def require(condition, reason):
    if not condition:raise ValueError(reason)

def snapshot_sources(code,stage,build):
    """Mirror the parent prepare inventory; identity superset, not execution coverage."""
    paths=list((code/'cpp/legsa_v23_port_core').rglob('*.cpp'))
    paths+=list((code/'cpp/legsa_v23_port_core').rglob('*.hpp'))
    paths+=list((code/'src/legsa_gins').rglob('*.py'))
    paths+=list((code/'scripts/paper_rebuild/v3_evaluator_observer').rglob('*.py'))
    paths += [code/'cpp/CMakeLists.txt',code/REGISTRY,code/CALIBRATED_CONTRACT]
    paths=sorted(set(paths));before={str(p.relative_to(code)):sha(p) for p in paths}
    for relative,digest in build['source_sha256'].items():
        require(before.get(relative)==digest,'BUILD_SOURCE_IDENTITY_CHANGED:'+relative)
    for p in paths:
        require(not p.is_symlink(),'SOURCE_SYMLINK:'+str(p))
        target=stage/'SOURCE_SNAPSHOT'/p.relative_to(code)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        require(sha(target)==before[str(p.relative_to(code))],'SNAPSHOT_COPY_CHANGED')
    after={str(p.relative_to(code)):sha(p) for p in paths}
    require(before==after,'SOURCE_CHANGED_DURING_SNAPSHOT')
    return before

def main():
    parser=argparse.ArgumentParser()
    for field in ('stage','code','prior-v3','natural-stage','build-receipt','binary'):
        parser.add_argument('--'+field,required=True)
    parser.add_argument('--physical-free-bytes',type=int,required=True)
    parser.add_argument('--volume-receipt',required=True)
    args=parser.parse_args();stage=Path(args.stage);code=Path(args.code);prior=Path(args.prior_v3)
    require(args.physical_free_bytes>=40*1024**3,'ACTUAL_G_PHYSICAL_FREE_BELOW_40GIB')
    require(args.physical_free_bytes>30*1024**3+20*1024**3,'INSUFFICIENT_PREREGISTERED_30GIB_BUDGET_PLUS_20GIB_HEADROOM')
    require(not stage.exists(),'EXCLUSIVE_NEW_STAGE_REQUIRED')
    volume=json.loads(Path(args.volume_receipt).read_text(encoding='utf-8-sig'))
    require(volume['DriveLetter']=='G' and volume['SizeRemaining']==args.physical_free_bytes,'HOST_VOLUME_RECEIPT_MISMATCH')
    require(str(stage).startswith('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_'),'G_STAGE_STORAGE_REQUIRED')
    original_registry=prior/'00_PREREGISTRATION/REGISTRY.json'
    registry_sha=sha(original_registry);registry=json.loads(original_registry.read_text())
    specs=[r for r in registry if r.get('domain')=='ADDENDUM' and
           r.get('case_id') in CASES and r.get('method_id') in METHODS and r.get('sequence_id')=='BY2']
    require(len(specs)==135 and {(r['case_id'],r['method_id']) for r in specs}==
            {(c,m) for c in CASES for m in METHODS},'EXACT_45_CASES_X_3_METHODS_REQUIRED')
    require(all(r['data_mode']=='semisynthetic' and r['semisynthetic_data_used'] is True and
                r['synthetic_data_used'] is False for r in specs),'REGISTRY_CONTROLLED_IDENTITY_REQUIRED')
    natural_plan_path=Path(args.natural_stage)/'PREREGISTRATION.json'
    natural_plan=json.loads(natural_plan_path.read_text());seq=natural_plan['sequences']['BY2']
    natural_seal=json.loads((Path(args.natural_stage)/'ALL_NATIVE_SEALED.json').read_text())
    require(natural_seal['status']=='SEALED' and natural_seal['preregistration_sha256']==sha(natural_plan_path),
            'SEALED_NATURAL_IMU_REUSE_REQUIRED')
    require(len(seq['segments'])==1 and not seq['gaps'] and seq['expected_original_output_epochs']==56642,
            'BY2_NO_GAP_NO_ADDED_REINITIALIZATION_REQUIRED')
    require(seq['segments'][0]['rows']==56643,'EXPECTED_BY2_IMU_ROWS')
    imu_pin=seq['segments'][0];pinned(imu_pin)
    build=json.loads(Path(args.build_receipt).read_text())
    require(build['status']=='NATIVE_BUILD_SOURCE_IDENTITY_VERIFIED','BUILD_RECEIPT_REQUIRED')
    require(sha(args.binary)==build['binary_sha256'],'BINARY_BUILD_IDENTITY_MISMATCH')
    source_info_flags=('trace_used_online','trace_used_for_initialization','receiver_imu_as_body_imu',
                       'synthetic_data_used','per_case_tuning','epoch_deleted_for_metric',
                       'go2_position_truth_claim','go2_velocity_truth_claim','go2_yaw_truth_claim')
    configs={};admissions={};providers={};all_pins={};case_rows=[];pair_rows=[];mask_rows=[]
    for spec in sorted(specs,key=lambda s:(s['case_id'],s['method_id'])):
        rid=spec['run_id'];admission_path=prior/'02_CONFIGS'/rid/'CONFIG_ADMISSION.json'
        admission=json.loads(admission_path.read_text());admissions[rid]=admission
        payload=pinned(admission['config']).read_bytes();cfg=yaml.safe_load(payload);configs[rid]=(payload,cfg)
        require(spec['effective_profile']==METHODS[spec['method_id']],'METHOD_PROFILE_MISMATCH')
        allowed_algorithms=({'LegSA_Paper_V1','AB1111'} if spec['method_id']=='F04' else {METHODS[spec['method_id']]})
        require(cfg['algorithm_id'] in allowed_algorithms and cfg['ablation_variant']==METHODS[spec['method_id']], 'CFG_ALGORITHM_TO_METHOD_BINDING_INVALID')
        require(all(cfg.get(k) is False for k in source_info_flags),'FORBIDDEN_INFO_FLAG_PRESENT:'+rid)
        require(cfg['imudatalen']==7 and cfg['starttime']==66.0 and cfg['endtime']==340.0,'OLD_IMU_WINDOW_MISMATCH')
        require(cfg['semisynthetic_data_used'] is False,'OLD_TRANSPORT_FLAG_EXPECTATION_CHANGED')
        require(spec['frozen_providers']['imupath']==seq['legacy_imu'],'CASE_IMU_CHANGED')
        require(spec['raw_source_hashes']['body']==seq['raw_body_sha256'],'CASE_RAW_BODY_CHANGED')
        actual={**spec['frozen_providers'],'gnsspath':admission['prepared_gnss']};providers[rid]=actual
        for role,pin in actual.items():
            require(cfg[role]==pin['path'],'CONFIG_PROVIDER_PATH_MISMATCH:'+rid+':'+role)
            old=all_pins.setdefault(pin['path'],pin['sha256']);require(old==pin['sha256'],'PIN_CONFLICT')
        all_pins[str(admission_path)]=sha(admission_path)
        all_pins[admission['config']['path']]=admission['config']['sha256']
        all_pins[spec['frozen_providers']['gnsspath']['path']]=spec['frozen_providers']['gnsspath']['sha256']
    for path,digest in all_pins.items():pinned({'path':path,'sha256':digest})
    by_key={(s['case_id'],s['method_id']):s for s in specs}
    for case in sorted(CASES):
        full=by_key[case,'F04'];full_cfg=configs[full['run_id']][1];meta=full['case_meta']
        require(meta['case_id']==case and meta['window_start_s']==66 and meta['window_end_s']==340,'CASE_METADATA_INVALID')
        start,end=meta['outage_start_s'],meta['outage_end_s']
        require(66<=start<end<=340 and abs(end-start-meta['duration_s'])<1e-8,'OUTAGE_INTERVAL_INVALID')
        expected_sources=['gnss_position','receiver_velocity','raw_doppler']+(['dual_yaw'] if case.startswith('D61') else [])
        require(meta['sources']==expected_sources,'FAULT_SOURCE_SCOPE_MISMATCH')
        for method,flag in [('A03','enable_raw_doppler'),('A06','enable_go2_horizontal_velocity_prior')]:
            other=by_key[case,method];other_cfg=configs[other['run_id']][1]
            require(other['case_meta']==meta and other['raw_source_hashes']==full['raw_source_hashes'],'PAIR_CASE_IDENTITY_MISMATCH')
            require(providers[other['run_id']]==providers[full['run_id']],'PAIR_PROVIDER_MISMATCH')
            diff={k for k in set(full_cfg)|set(other_cfg) if full_cfg.get(k)!=other_cfg.get(k)}
            require(diff<=PAIR_FIELDS|{flag} and flag in diff,'PAIR_NOT_SINGLE_VARIABLE:'+case+':'+method+':'+str(diff))
            require(full_cfg[flag] is True and other_cfg[flag] is False,'PAIR_FACTOR_FLAGS_INVALID')
            pair_rows.append({'case_id':case,'full_source_run':full['run_id'],'ablation_source_run':other['run_id'],
                              'ablation_method':method,'only_scientific_field_changed':flag,
                              'all_different_fields_json':json.dumps(sorted(diff)),'providers_identical':True})
        prepared=np.loadtxt(admissions[full['run_id']]['prepared_gnss']['path'],ndmin=2)
        frozen=np.loadtxt(full['frozen_providers']['gnsspath']['path'],ndmin=2)
        require(prepared.shape==frozen.shape and prepared.shape[1]==18,'GNSS_SHAPE_MISMATCH')
        retained=[c for c in range(18) if c not in (13,17)]
        require(np.array_equal(prepared[:,retained],frozen[:,retained]),'NON_YAW_GNSS_BYTES_OR_VALUES_CHANGED')
        inside=(prepared[:,0]>=start)&(prepared[:,0]<end)
        require(inside.any() and np.all(prepared[inside,15:17]==0),'OUTAGE_POSITION_RV_NOT_DISABLED')
        if case.startswith('D61'):require(np.all(prepared[inside,17]==0),'D61_HEADING_NOT_DISABLED')
        doppler=pd.read_csv(full['frozen_providers']['raw_doppler_factor_path']['path'])
        rd_inside=(doppler.time>=start)&(doppler.time<end)
        require(rd_inside.any() and (doppler.loc[rd_inside,'valid']==0).all(),'OUTAGE_RD_NOT_DISABLED')
        mask_rows.append({'case_id':case,'gnss_rows':len(prepared),'gnss_outage_rows':int(inside.sum()),
            'doppler_rows':len(doppler),'doppler_outage_rows':int(rd_inside.sum()),
            'position_rv_disabled':True,'raw_doppler_disabled':True,
            'dual_yaw_disabled':case.startswith('D61'),'non_yaw_GNSS_unchanged':True,
            'IMU_intervention':False,'new_position_or_yaw_information_added':False})
        case_rows.append({k:meta[k] for k in ('case_id','degradation_type_id','seed_index','seed_value',
                                             'anchor_time_s','duration_s','outage_start_s','outage_end_s')})
    stage.mkdir(parents=True,exist_ok=False)
    snapshot=snapshot_sources(code,stage,build)
    shutil.copyfile(args.binary,stage/'SOLVER');(stage/'SOLVER').chmod(0o755)
    shutil.copyfile(args.build_receipt,stage/'BUILD_RECEIPT.json')
    imu_target=stage/'INPUTS/BY2/IMU8_SEGMENT_00.imu';imu_target.parent.mkdir(parents=True)
    shutil.copyfile(pinned(imu_pin),imu_target);require(sha(imu_target)==imu_pin['sha256'],'IMU8_COPY_MISMATCH')
    segment={**imu_pin,'path':str(imu_target)};new_seq={**seq,'segments':[segment]}
    runs=[]
    for spec in sorted(specs,key=lambda s:(s['case_id'],list(METHODS).index(s['method_id']))):
        rid='IMUFIX_CLAIM_'+spec['case_id']+'_'+spec['method_id'];child_id=rid+'_S00'
        fields={'stage_id':STAGE,'protocol_id':PROTOCOL,'case_id':spec['case_id'],'data_mode':'semisynthetic',
            'semisynthetic_data_used':True,'run_id':child_id,'run_label':child_id,'imupath':str(imu_target),
            'imudatalen':8,'endtime':segment['last'],'outputpath':str(stage/'NATIVE'/child_id),
            'runtime_role':'imu_v3_corrected_controlled_replay_solver'}
        payload,changes=clone_fields(configs[spec['run_id']][0],fields)
        config=stage/'CONFIGS'/f'{child_id}.yaml';config.parent.mkdir(exist_ok=True);config.write_bytes(payload)
        initialization={'kind':'UNCHANGED_V3_COMMON_INITIALIZATION','yaw_information_added':False,
                        'position_information_added':False,'gap_reinitialization_count':0}
        runs.append({'run_id':rid,'source_run_id':spec['run_id'],'case_id':spec['case_id'],
            'case_meta':spec['case_meta'],'method_id':spec['method_id'],'sequence_id':'BY2',
            'source_config':admissions[spec['run_id']]['config'],'providers':providers[spec['run_id']],
            'children':[{'run_id':child_id,'config':{'path':str(config),'sha256':sha(config)},
                'config_changes':changes,'initialization':initialization,'segment':segment,'status':'PREPARED'}],
            'data_mode':'semisynthetic','semisynthetic_data_used':True,'synthetic_data_used':False,
            'trace_used_online':False,'new_position_or_yaw_information_added':False})
    analysis={'scope':'All45cases and all3methods fixed before corrected results; exploratory paired replay after old results known',
        'primary_pairs':[{'candidate':'F04','reference':'A03','quantity':'RAW_DOPPLER off only; RV retained'},
                         {'candidate':'F04','reference':'A06','quantity':'SDK horizontal velocity off only'}],
        'domains':['full_original_66_340_support','fault_halfopen_start_inclusive_end_exclusive',
                   'outage_end_last_actual_inside_epoch','recovery_0_5s','recovery_5_10s','recovery_10_30s',
                   'all_post_outage_t_strictly_greater_than_end'],
        'common_epochs':'Exact saved time microsecond keys; intersection fixed separately per pair/domain; no interpolation',
        'failure_denominator':'Original 56642 IMU output epochs remains full-window denominator; report native/matched counts and any failed/unavailable cases',
        'comparison_sign':'F04 minus ablation; negative RMSE means lower diagnostic error',
        'statistics':'Report every pair, improvement/tie/worsening and anchor-block summaries; nine repeated placement anchors are not 45 independent samples; no confirmatory p claim',
        'reference':'Commercial shared-GNSS visual inertial fusion; independent truth and point/covariance equivalence unresolved',
        'not_revalidated':'Full6468 matrix; all20 HV contrasts; full-go2-off H3; no same-input external-method ranking'}
    plan={'schema':'imu_v3_claim_subset.v1','stage':STAGE,'protocol_id':PROTOCOL,
        'base_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=code,text=True).strip(),
        'base_head_role':'BASE_ONLY; actual source snapshot and binary hashes identify runtime',
        'source_snapshot_scope':'Whole legsa_gins Python package plus native port/build/config and observer sources; identity superset, not executed coverage',
        'source_snapshot_sha256':snapshot,'binary_sha256':sha(stage/'SOLVER'),
        'build_receipt_sha256':sha(stage/'BUILD_RECEIPT.json'),
        'native_configurations':135,'all_native_seals_required_before_any_reference_read':True,
        'host_volume_free_bytes_at_prepare':args.physical_free_bytes,'predeclared_storage_budget_bytes':30*1024**3,
        'host_volume_measurement':'Actual Windows G Get-Volume supplied by launcher; WSL df not physical evidence',
        'host_volume_receipt':volume,'physical_storage':'G exFAT; code/build and original sealed IMU8 stay on WSL ext4',
        'old_results_overwritten':False,'fault_matrix_replayed':True,'full6468_matrix_replayed':False,
        'old_registry':{'path':str(original_registry),'sha256':registry_sha},
        'natural_IMU_reuse':{'preregistration_path':str(natural_plan_path),'sha256':sha(natural_plan_path),'segment':imu_pin},
        'original_provider_and_config_pins':all_pins,'sequences':{'BY2':new_seq},'runs':runs,
        'data_mode':'semisynthetic','semisynthetic_data_used':True,'synthetic_data_used':False,
        'new_position_or_yaw_information_added':False,'analysis_preregistration':analysis}
    write_json(stage/'PREREGISTRATION.json',plan)
    for name,rows in [('CASE_INVENTORY.csv',case_rows),('PAIR_SINGLE_VARIABLE_AUDIT.csv',pair_rows),('OUTAGE_MASK_AUDIT.csv',mask_rows)]:
        with (stage/name).open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_json(stage/'PREPARE_AUDIT.json',{'status':'ALL_45_CASES_X_3_CONFIGS_PREPARED_WITH_EXACT_SINGLE_VARIABLE_PAIRS',
        'native_estimator_invocations':0,'evaluator_invocations':0,'trace_reads':0,'case_count':45,
        'configuration_count':135,'pair_count':90,'provider_pin_count':len(all_pins),
        'source_inventory_count':len(snapshot),'old_transport_semisynthetic_false_explicitly_corrected':True,
        'prepare_helper':{'path':str(Path(__file__).resolve()),'sha256':sha(__file__)}})
    require(sha(original_registry)==registry_sha,'REGISTRY_CHANGED_DURING_PREPARE')
    for path,digest in all_pins.items():pinned({'path':path,'sha256':digest})
    verify_runtime(stage,code,plan)
    print(json.dumps({'status':'PREPARED','stage':str(stage),'configurations':135,'cases':45,'native_estimator_invocations':0}))

if __name__=='__main__':main()
