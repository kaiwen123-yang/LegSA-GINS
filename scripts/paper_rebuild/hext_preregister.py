#!/usr/bin/env python3
"""Materialize the H-EXT draft from observations; no scientific execution."""
from pathlib import Path
import json
import yaml
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths,alias_path
from legsa_gins.paper_rebuild.horizontal_literature.ext05_provider import sha256_file

s=load_sequence_paths('BY2');records={}
for name in ('BY2','BY2H','BY2O'):
 p=load_sequence_paths(name);probe=json.loads((s.output_root/'01_PROBE'/name/'PROBE.json').read_text())
 r=probe['P1']['receivers'][0]
 records[name]={'role':'SHARED_PARAMETER_VARIANTS_ONLY' if name=='BY2' else 'LITERATURE_AND_SHARED_PARAMETER_VARIANTS',
  'window':list(p.window),'base_time':p.base_time,'trace':alias_path(p.trace,p),'trace_sha256':p.trace_sha256,
  'trace_hash_verification':'DECLARED_METADATA_ONLY_NO_TRACE_ACCESS_IN_H_EXT_01',
  'baseline_median_m':p.baseline_median_m,'hash_lock':alias_path(p.hash_lock,p),
  'hash_lock_sha256':p.hash_lock_sha256,'hash_lock_note':p.hash_lock_note,
  'expected':{'status':'OBSERVED_PENDING_HUMAN_CONFIRMATION','position_epochs':r['hpposecef_epochs'],
   'rawx_epochs':r['rawx_epochs'],'imu_samples':probe['P2']['sample_count'],
   'gps_week':r['gps_week_set'][0],'leap_seconds':r['leap_seconds_set'][0],
   'cadence_ms':200,'hpposecef_minus_rawx_ms':2,'leading_hpposecef_without_rawx':r['leading_hpposecef_without_rawx']},
  'observation_source':alias_path(s.output_root/'01_PROBE'/name/'PROBE.json',s),
  'observation_sha256':sha256_file(s.output_root/'01_PROBE'/name/'PROBE.json'),
  'imu_gaps':probe['P2']['gaps_gt_0p1s']}
phase=Path('configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml')
model=Path('configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml')
audit=s.output_root/'00_CONFIG_AUDIT/CONFIG_AUDIT_OBSERVATIONS.json'
payload={'schema_version':'hext.external_sequences.contract.v1','task':'H-EXT-02_PROPOSAL_FROM_H-EXT-01',
 'status':'DRAFT_PENDING_HUMAN_AUTHORIZATION','execution_authorized':False,
 'frozen_main_chain':'PROTOCOL_V2.1_UNCHANGED_EXTERNAL_COMPARISON_ROWS_ONLY',
 'sequence_registry':'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',
 'local_path_config':'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml','sequences':records,
 'literature_parameter_inheritance':{'path':str(phase),'sha256':sha256_file(phase),'mode':'EXACT_MAPPING_DEEPCOPY_NO_METHOD_SPECIFIC_CHANGES'},
 'methods':[
 {'id':'LC01','native_method':'EXT05A_PAVLASEK_TWO_RECEIVER_IEKF','parameters':'LITERATURE_DEFAULT','role':'EXTERNAL_COMPARISON'},
 {'id':'EXT05C','native_method':'EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF','parameters':'LITERATURE_DEFAULT','role':'SINGLE_RECEIVER_DIAGNOSTIC'},
 {'id':'LC01-S','native_method':'EXT05A_PAVLASEK_TWO_RECEIVER_IEKF','parameters':'SHARED_PARAMETERS','role':'EXTERNAL_COMPARISON'},
 {'id':'EXT05C-S','native_method':'EXT05C_PAVLASEK_SINGLE_RECEIVER_IEKF','parameters':'SHARED_PARAMETERS','role':'SINGLE_RECEIVER_DIAGNOSTIC'}],
 'shared_parameters':{'implementation':'src/legsa_gins/paper_rebuild/hext/parameters.py',
 'sensor_model':str(model),'sensor_model_sha256':sha256_file(model),'audit':'docs/paper_rebuild/hext/H_EXT_CONFIG_PARITY_AUDIT.md','audit_items':['A4','A5','A6','A10'],
 'gyro_psd_rad2_s':{'default':[4e-4,4e-4,3.24e-4],'variant_formula':'(frozen_arw[axis] * pi / 180 / 60)^2','arw_deg_sqrt_h':[.985,.985,.985]},
 'accel_psd_m2_s3':{'default':[.0289,.0225,.0576],'variant':'sensor_model.q','validation':'q[axis] == (vrw[axis]/60)^2, rtol=1e-13'},
 'accel_scale':{'default':1.,'variant':1.0308398903907543,'placement':'All three unrounded FRD force axes after FLU->FRD and installation, before integration; frozen literature previous-sample propagation retained'},
 'imu_gap_policy':{'default':'frozen_filter_raise','variant':'mirror_legsa_drop','implementation':'INTERFACE_ONLY_NOT_IMPLEMENTED',
 'decision_stage':'H-EXT-02','A10_facts':'Frozen BY2H increments 407.017058->413.041069 (6.024011 s) straddle initialization with no left NAV; inside-window 414.905067->415.081079 (0.176012 s) uses retained timestamp dt and NAV changes. Raw 4.740005970001221 s gap is not a demonstrated 4.7 s NAV step.',
 'gap_table':'sequences.*.imu_gaps'},
 'unchanged':['No bias state','Initial covariance','pAcc squared R construction and correlated stacked R','Static calibration criterion','Geometry audit thresholds','Lever/baseline/install constants','Process noise injection structure']},
 'budget':{'native':10,'native_definition':'BY2H/BY2O x 4 + BY2 x 2 shared-parameter variants',
 'evaluator':20,'evaluator_definition':'v3 primary + v2 parallel for each new native','concurrency_max':20,'numerical_threads_per_worker':1,
 'H_EXT_01_identity_runs_excluded':2},
 'report_rules':{'main_tables':'All three sequences show literature and S rows; BY2 literature rows remain frozen P-07 values.',
 'main_text_selection':'Use the version with smaller BY2 C00 v3 yaw RMSE for all three sequences, uniformly. The other version appears completely in supplementary material; neither version may be omitted.',
 'selector_method_pair':'LC01 versus LC01-S; EXT05C pair remains diagnostic','equal_yaw_rmse':'HUMAN_DECISION_REQUIRED_NO_UNREGISTERED_TIE_BREAK',
 'missing_yaw_rmse':'HUMAN_DECISION_REQUIRED_NO_SUBSTITUTION','version_selection_is_post_result_declared_rule':True},
 'archive':{'scratch_key':'hext_scratch','scratch_filesystem':'ext4','destination':'<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/',
 'retry_errno':['ENOMEM','EIO'],'retries':3,'scope':'archive I/O only; never scientific reruns','ledger':'One row/checkpoint per batch/file; SHA-256 verify before complete; preserve scratch on failures.'},
 'required_human_decisions':['H-EXT-02 gap mechanism','BY2O pAcc inflation annotation (52 HPPOSECEF threshold epochs vs 57 status float epochs)','Observed expected counts confirmation','Draft execution authorization'],
 'no_parameter_search':True,'no_timing_sign_offset_search':True,'no_main_chain_change':True}
Path('configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml').write_text(yaml.safe_dump(payload,allow_unicode=True,sort_keys=False),encoding='utf-8')
print('DRAFT_PENDING_HUMAN_AUTHORIZATION')
