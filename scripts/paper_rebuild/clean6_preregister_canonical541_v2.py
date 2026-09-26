#!/usr/bin/env python3
"""Create P-09c preregistration from immutable specifications and output seals.

No provider, solver, evaluator, raw reference, NAV or STD payload is opened.
Only the new contract is written; the supervisor must commit it before execution.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import yaml

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE/'src'))
from legsa_gins.paper_rebuild.clean5_degradation.common import registry, resolve, pinned, read_csv
from legsa_gins.paper_rebuild.manifest import sha256_file

STAGE = 'CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2'
P07 = 'configs/paper_rebuild/clean5/CLEAN5_DEGRADATION_SUBSET_CONTRACT.yaml'
P06 = 'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml'
TARGET = 'configs/paper_rebuild/clean6/CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml'


def alias_path(path, reg):
    path = Path(path)
    for name in ('CODE_ROOT', 'CLEAN_ROOT', 'RAW_ROOT'):
        root = getattr(reg, name.lower())
        if path.is_relative_to(root):
            return '<'+name+'>/'+path.relative_to(root).as_posix()
    raise ValueError('Unregistered local path')


def pin(path, reg):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix in ('.bag', '.fpl', '.nav') or path.name.startswith('trace_'):
        raise ValueError('Illegal preregistration input: '+str(path))
    return {'path': alias_path(path, reg), 'sha256': sha256_file(path)}


def portable(value, reg):
    if isinstance(value, dict):
        return {k: portable(v, reg) for k, v in value.items()}
    if isinstance(value, list):
        return [portable(v, reg) for v in value]
    if isinstance(value, str) and value.startswith('/'):
        return alias_path(value, reg)
    return value


def burst_intervals(path, type_id):
    source = 'gnss_position' if type_id == 'D22' else 'dual_yaw'
    with gzip.open(path, 'rt', newline='') as stream:
        rows = sorted((r for r in csv.DictReader(stream) if r['source'] == source), key=lambda r: int(r['row_index']))
    groups = []
    for row in rows:
        if not groups or int(row['row_index']) != int(groups[-1][-1]['row_index'])+1:
            groups.append([])
        groups[-1].append(row)
    if len(groups) != (1 if type_id == 'D22' else 3):
        raise ValueError('Frozen burst groups do not close '+str(path))
    return [{'start_s': float(g[0]['base_time']), 'end_s': float(g[0]['base_time'])+len(g),
             'source_ids': [source], 'frozen_affected_count': len(g)} for g in groups]


def build(reg):
    p07 = yaml.safe_load((CODE/P07).read_text())
    p06 = yaml.safe_load((CODE/P06).read_text())
    cases = read_csv(pinned(p07['sources']['case_registry'], reg))
    runs = read_csv(pinned(p07['sources']['unique_run_registry'], reg))
    templates = {r['degradation_type_id']: r for r in p07['providers']['mapping']}
    c00 = templates['CLEAN']
    provider_root = resolve(c00['frozen_case_manifest']['path'], reg).parents[2]
    ready = {r['case_id']: r for r in read_csv(pinned(p07['sources']['provider_ready'], reg))}
    def mapping(case):
        cid, tid = case['case_id'], case['degradation_type_id']
        result = deepcopy(templates[tid]); result['case_id'] = cid
        result['parameters'] = json.loads(case['degradation_parameters_json'])
        members = {'frozen_case_provider_index': '02_PROVIDERS/provider_index.json',
                   'frozen_case_manifest': '00_CASE_SPEC/case_spec_dump.json',
                   'frozen_provider_generation_log': '02_PROVIDERS/provider_generation_log.json',
                   'frozen_perturbation_ledger': '02_PROVIDERS/CASE_PERTURBATION_LEDGER.csv.gz'}
        for key, relative in members.items():
            result[key] = pin(provider_root/cid/relative, reg)
        if result['frozen_case_provider_index']['sha256'] != ready[cid]['storage_index_sha256']:
            raise ValueError('Frozen ready/index identity mismatch '+cid)
        spec = json.loads((provider_root/cid/members['frozen_case_manifest']).read_text())
        if spec['case_id'] != cid or spec['degradation_parameters_json'] != case['degradation_parameters_json']:
            raise ValueError('Frozen case specification mismatch '+cid)
        result['frozen_components'] = json.loads((provider_root/cid/members['frozen_provider_generation_log']).read_text())['components']
        if tid in ('D22', 'D39'):
            result['intervals'] = burst_intervals(provider_root/cid/members['frozen_perturbation_ledger'], tid)
        if cid in p07['selection']['selected_case_ids'] and result != templates[tid]:
            raise ValueError('Expanded seed00 mapping differs from P07 '+cid)
        return result
    with ThreadPoolExecutor(max_workers=16) as pool:
        mappings = list(pool.map(mapping, cases))
    contract = {k: deepcopy(p07[k]) for k in ('sources','providers','runtime','evaluation','statistics','prohibitions','data_roles')}
    contract.update(schema_version='paper_rebuild.clean6.canonical541_protocol_v2.v1',
                    task='P-09c', protocol_id='Canonical-541_protocol_v2_CAL',
                    stage_root='<CLEAN_ROOT>/stages/'+STAGE,
                    authorization={'date': '2026-09-11', 'human_task': 'P-09c plus pilot and ext4/provider-pool/128-worker amendments',
                                   'provider_generation_requires_committed_contract': True,
                                   'separate_later_code_commit_required': True,
                                   'start_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=CODE,text=True).strip()},
                    selection={'rule': 'All frozen Canonical 541 cases in exact registry order; no selection or exclusions',
                               'registered_case_count': 541, 'selected_case_count': 541, 'excluded_case_count': 0,
                               'NOT_TRANSFERABLE': [], 'selected_case_ids': [r['case_id'] for r in cases]})
    contract['sources']['p07_contract'] = pin(CODE/P07, reg)
    contract['sources']['p06_contract'] = pin(CODE/P06, reg)
    contract['sources']['logical_evaluation_results'] = deepcopy(p06['sequences']['BY2']['frozen_main_table'])
    contract['sources']['p08_plan'] = pin(CODE/'docs/paper_rebuild/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2_PLAN.md',reg)
    attempt = resolve(p07['sources']['case_registry']['path'],reg).parents[1]
    anchor_file = attempt/'03_SEEDS_AND_ANCHORS/CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv'
    contract['sources']['anchor_manifest'] = pin(anchor_file, reg)
    contract['sources']['logical_alias_registry'] = pin(attempt/'07_FULL_ALGORITHM_REGISTRY/CANONICAL541_LOGICAL_ALIAS_REGISTRY.csv',reg)
    contract['providers'].update(mapping=mappings, input_families=[STAGE], generation='one case per independently traced subprocess; same worker pool as solver/evaluator; no nested process pool')
    model = yaml.safe_load(pinned(contract['runtime']['model'],reg).read_text())
    contract['runtime'].update(chains={'CAL': contract['runtime']['chains']['CAL']},
        run_id_rule='Preserve every frozen Canonical RUN id; BY2 C00 runs also satisfy 11 sequence gate entries; H/O extras use SEQUENCE_<dataset>_<method>',
        run_count_per_chain=5951, solver_limit=5973, matrix_solver_limit=5951,
        sequence_gate_run_count=33, sequence_extra_unique_runs=22, jobs=64,
        parallel_source='P09c explicit 64 then conditional 128, shared pool, ext4 scratch',
        failed_runs='No retry; algorithm failures counted as method failures; technical failures distinct; batch verification failure stops with scene retained',
        frozen_calibration_values={k:model[k] for k in ('s','vrw','abstd')},
        native_identity_policy='Frozen native stage/role retained; outer protocol identity explicit in manifest; case and method identities preserved',
        allowed_scientific_diff_CAL=['vrw','abstd'], retry_count=0)
    contract['runtime'].pop('allowed_scientific_diff_V2S',None)
    contract['evaluation'].update(new_solver_evaluation_limit=11946,matrix_evaluation_identities=11902,
        unique_rows_per_version=5951, logical_rows_per_version=7033, primary_version='v3',
        self_check={'reference_support':'full jointly cleaned reference support; actual evaluated NAV',
                    'coordinates':'WGS84 geodetic ECEF to ENU with reference LLH anchor',
                    'failure':'EVALUATION_SUSPECT is a batch gate failure; stop and preserve outputs',
                    'trace_reads':'only evaluator child (plus separately traced authorized raw hash checkpoints)'})
    p07sealpath = reg.clean_root/'stages/CLEAN5_DEGSUBSET_BY2/04_SEAL/SOLVER_OUTPUT_SEAL.json'
    p06root = reg.clean_root/'stages/CLEAN5_CALIBRATED_SENSOR_MODEL'
    p06sealpath = p06root/'04_CALIBRATED_SEAL/CALIBRATED_OUTPUT_SEAL.json'
    p07seal = json.loads(p07sealpath.read_text()); p06seal = json.loads(p06sealpath.read_text())
    # Numerical stream identity is exact bytes. Manifests/configs contain new protocol/run paths and are separately audited.
    streams = ['LegSA_PORT_NAV.nav','LegSA_PORT_STD.csv','EVAL_NAV.csv','KF_GINS_Navresult.nav','KF_GINS_STD.txt','KF_GINS_IMU_ERR.txt',
               'PORT_GNSS_UPDATE_TRACE.csv']
    c00runs = [r for r in runs if r['case_id']=='C00_clean_normal']
    c00anchors = []
    for row in c00runs:
        prefix='03_RUNS/CLEAN5_DEGSUBSET_CAL/'+row['run_id']+'/'
        c00anchors.append({'run_id':row['run_id'],'method_id':row['method_id'],
                           'files_sha256':{f:p07seal['files_sha256'][prefix+f] for f in streams}})
    contract['anchors']={'seed_selection_policy':'Frozen nine rows; PCG64 sorted named component substreams; half-open windows, shift then clip; no reselection',
                        'seed_anchor_rows':read_csv(anchor_file),'C00_reference_seal':pin(p07sealpath,reg),
                        'C00_profiles':c00anchors,'C00_gate':'11/11 exact numerical-stream sha256 equality to P07 CAL C00; any difference stops'}
    sequences = {}
    refs=[]
    keep=('dataset_id','data_mode','base_time','window_seconds','case_id','case_meta','raw_inputs','raw_lock','original_configs','frozen_sequence_contract',
          'baseline_median_m','trace','v3_lever_frd_m','occlusion_window')
    for dataset, spec in p06['sequences'].items():
        seq={k:deepcopy(v) for k,v in spec.items() if k in keep}
        bundle_path=p06root/'02_CALIBRATED_PROVIDERS'/dataset/'CALIBRATED_PROVIDER_BUNDLE.json'
        bundle=json.loads(bundle_path.read_text())
        seq['calibrated_provider_bundle']=pin(bundle_path,reg)
        seq['providers']=portable(bundle['variants']['V2s']['providers'],reg)
        sequences[dataset]=seq
        for method in p06['run_profiles']:
            rid='CLEAN5_CALIBRATED_'+dataset+'_'+method; prefix='03_CALIBRATED_RUNS/'+rid+'/'
            refs.append({'dataset_id':dataset,'method_id':method,'reference_run_id':rid,
                         'files_sha256':{f:p06seal['files_sha256'][prefix+f] for f in streams}})
    contract['sequences']=sequences
    contract['sequence_consistency']={'datasets':['BY2','BY2H','BY2O'],'profiles':contract['runtime']['profiles'],
        'run_count':33,'distinct_extra_runs':22,'same_code_freeze':True,'required_before_batch_2':True,
        'reference_seal':pin(p06sealpath,reg),'reference_profiles':p06['run_profiles'],'reference_count':15,'references':refs,
        'equality':'all frozen numerical output streams byte-identical; manifests/config transport identities audited separately; any difference stops',
        'extra_profile_construction':'For each H/O sequence, keep frozen F04 template bytes and replace only canonical method identity and module flag lines that differ between BY2 F04 and each A03/A05/A06/A07/A08/A09 template; apply same frozen vrw/abstd; all other science/window/base/geometry unchanged',
        'BY2_C00_reuse':'The 11 matrix C00 runs are the BY2 consistency runs; never duplicated'}
    contract['execution']={'worker_pool_shared':True,'initial_workers':64,'maximum_workers':128,'batch_size':256,
        'pilot_batch':1,'pilot_includes_sequence_gate':True,'pilot_count':256,
        'initial_gate_barrier':'Complete 33 consistency solves and all seven-file P06/P07 byte comparisons before launching remaining pilot solves; any mismatch stops',
        'batch_order':'33 consistency runs first (including 11 BY2 matrix C00), then frozen Canonical run order excluding completed C00; 5973 distinct runs total',
        'per_worker_isolation':['strace session','TMPDIR','MPLCONFIGDIR','XDG_CACHE_HOME'],
        'single_thread_environment':{k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')},
        'phase_order':['case providers','solve','full-file sha256 seal','v3/v2 evaluation','10Hz thinning and compression','archive to G','verify archive and retained pack','ledger exact-file NAV/STD deletion','release scratch'],
        'batch_failure':'stop on any verification failure, preserve scene; no regeneration/retry',
        'pilot_required_measurements':['nproc','affinity CPU count','available memory bytes','CPU utilization fraction of allowed CPUs','memory peak bytes/fraction of physical MemTotal; record MemAvailable at start separately','per-run solve/evaluate seconds','per-run full/retained output bytes','64-worker batch wall seconds','scratch peak bytes','G peak bytes','full duration extrapolation','full peak extrapolation'],
        'pilot_continue_gate':'projected peak bytes <=250000000000 AND sequence consistency PASS AND batch verification PASS',
        'worker_promotion':{'from_batch':2,'workers':128,'conditions_all':{'pilot_CPU_utilization_lt':0.85,'pilot_memory_peak_fraction_lt':0.50},'otherwise_workers':64},
        'ledger':'BATCH_LEDGER.jsonl','commit_push_every_batches':8}
    contract['storage']={'G_required_free_bytes_before_any_generation':300000000000,
        'scratch_required_free_bytes':150000000000,'scratch_filesystem':'WSL ext4 only; local alias in ignored config',
        'direct_G_fallback':False,'latest_amendment_supersedes_initial_fallback':True,
        'peak_limit_bytes':250000000000,
        'pilot_peak_forecast':'1.15*(max observed per-run retained allocated bytes*5973 + measured batch scratch peak + fixed/provider retained footprint); batch size remains256',
        'pilot_duration_forecast':'first batch wall seconds*ceil(5973/256); linear estimate, not a confidence interval',
        'peak_scope':'combined attempt-owned scratch plus G retained outputs; record physical and logical bytes separately',
        'per_run_permanent':['RUN_MANIFEST.json','summary.json (v3,v2)','error_series.csv.gz (v3,v2)','NAV_10HZ.csv.gz','PORT_GNSS_UPDATE_TRACE.csv.gz','OUTPUT_SEAL full-file sha256 entries including deleted NAV/STD'],
        'delete_only_after':'batch evaluation, thinning/compression, archive and pack verification completed; exact owned regular-file ledger; no symlinks or roots',
        'deletion_scope':'complete NAV/STD plus attempt-owned scratch after verified archive; preserve ledger and seals forever',
        'automatic_regeneration':False}
    contract['gates']={'case_closure':541,'unique_matrix_runs':5951,'logical_matrix_rows':7033,'family_handlers':60,
        'source_ledger':'541x8 frozen provenance entries retained; new IMU/GNSS18 bindings separate',
        'clean18':'NOT_APPLICABLE_11_UNIQUE_AUTHORIZED_CONFIGURATIONS; no claim of old 18-config gate PASS',
        'readiness_equivalence':'11-profile identity/route/counter checks plus P07 CAL C00 exact outputs and P06 15-run exact outputs, current infrastructure tests; no seven extra configs',
        'provider_common':['source pins','case identity','seed replay','finite monotonic input','affected/unaffected source and field scope','original valid opportunity counts','no trace/raw writes','no old runtime input'],
        'D22_D39':'all nine seed ledgers converted to frozen equal-duration half-open windows',
        'D54':'seed00-03 scale1.5/dropout0; seed04-07 scale1/dropout0.5; seed08 scale1.5/dropout0.5; exact valid selection count and retained scale',
        'D56':'even/odd/seed08 metadata branches frozen; solver inputs unchanged',
        'D57':'six independently shifted sources, stable original-row identity, irregular union, exact event conservation, no grid snapping',
        'schedule':'replay C++ IMU/GNSS scheduler and independent column15/16/17 validity counts; no held A1 updates',
        'failure_classification':'Complete processing plus enabled yaw and positive attempts all rejected => ALGORITHM_FAILURE_ALL_YAW_REJECTED; no NAV => NOT_RUN_ALGORITHM_FAILURE; technical errors distinct'}
    stats=contract['statistics']
    for k in ('four_columns','frozen_column_version','evaluation_version_reporting','decision_versions','decision','decision_filename','missing_pairs'):
        stats.pop(k,None)
    stats.update(frozen_comparison='Canonical v1 full frozen v2 tables versus protocol v2 full, each evaluator v3/v2 separate',
                 maintained='same strict median sign and same strict side of 0.5 win rate as v1; exact zero/0.5 => not maintained; missing pairs => INCOMPLETE',
                 bootstrap={'unit':'paired case','statistic':'median paired delta plus original Canonical publication mean delta',
                            'resamples':10000,'seed':20260904,'interval':'percentile 2.5,97.5 numpy linear; same draws for mean and median',
                            'source':'publication/derived_tables.py bootstrap_mean_ci; median is explicitly preregistered extension'},
                 wilcoxon={'source':'publication/derived_tables.py wilcoxon_signed_rank_p','alternative':'two-sided',
                           'zero_rule':'abs(delta)<=1e-12 removed','rank_ties':'average', 'approximation':'normal with tie and continuity correction','n_nonzero_less_than_10':'UNAVAILABLE'},
                 failure_aware={'one_algorithm_failure':'successful method wins','both_algorithm_failure':'failure tie, both methods failure count incremented',
                                'technical_missing':'separate missing denominator, never fabricated metrics','finite_metric_statistics':'both-success finite pairs only',
                                'rate_denominator':'both available terminal methods including algorithm failure ties; technical/not-started excluded and explicitly counted'},
                 add_key_pairs=[{'comparison':'A04_vs_F03','candidate_method_id':'A04','reference_method_id':'F03'},
                                {'comparison':'A04_vs_F02','candidate_method_id':'A04','reference_method_id':'F02'},
                                {'comparison':'F04_vs_F02','candidate_method_id':'F04','reference_method_id':'F02'},
                                {'comparison':'F04_vs_F01','candidate_method_id':'F04','reference_method_id':'F01'},
                                {'comparison':'A04_vs_F01','candidate_method_id':'A04','reference_method_id':'F01'}])
    contract['outputs']={'aggregate_order':['UNIQUE_METHOD_SUMMARY.csv','LOGICAL_METHOD_SUMMARY.csv','CASE_SUMMARY.csv','DEGRADATION_TYPE_SUMMARY.csv','FAMILY_SUMMARY.csv','PAIRWISE_CASE_LEVEL.csv','PAIRWISE_SUMMARY.csv','SEED_SUMMARY.csv','RECOVERY_SUMMARY.csv','UNCERTAINTY_CALIBRATION_SUMMARY.csv','MODULE_ACTION_SUMMARY.csv','RUNTIME_SUMMARY.csv','METRIC_COVERAGE_REPORT.csv','FINAL_EVALUATION_SUMMARY.json','EVALUATION_AND_AGGREGATE_STATUS.json'],
                        'evaluation_tables':['UNIQUE_EVALUATION_RESULTS.csv','LOGICAL_EVALUATION_RESULTS.csv'],
                        'additional':['FAILURE_AWARE_PAIRWISE_SUMMARY.csv','FAILURE_COUNTS_BY_FAMILY_CONFIG.csv','ALL_YAW_REJECTED_BY_FAMILY.csv','V1_V2_PAIRWISE_COMPARISON.csv'],
                        'version_roots':['12_OFFLINE_EVALUATION/<v3|v2>','13_AGGREGATE/<v3|v2>'],
                        'handoff_script':'scripts/paper_rebuild/c541_pack_v3.py','handoff_destination':'<USER_HOME>/c541_v2_handoff.zip',
                        'handoff_contents':'same structure as c541_pack_v2; aggregate tables, whitelisted columns, C00 10Hz NAV, thinned error sequences, identity probes',
                        'report':'terminal family x config counts; ALL_YAW_REJECTED family counts; consistency and C00 gates; key pair median/CI/win; v1-v2 maintained/flipped lists; measured seconds and peak bytes; zip sha256 and commits; no interpretation'}
    contract['records']={'commit_push_order':['contract','code','batch records every 8 batches','aggregate and handoff'],
                         'AGENTS_sections':[3,7,11,18],'handoff_sections':[2,3,6],
                         'manuscript_protocol':'v2 after completed gates; v1 retained as preregistration record',
                         'decision_rule_file_change':False,'main_chain_v1_change':False,'Outcome_change':False}
    return contract


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config',required=True)
    parser.add_argument('--output',default=str(CODE/TARGET))
    args=parser.parse_args(); reg=registry(args.local_config)
    if reg.code_root!=CODE: raise ValueError('Wrong worktree')
    output=Path(args.output)
    if output!=CODE/TARGET: raise ValueError('Only approved contract destination is writable')
    contract=build(reg)
    payload=yaml.safe_dump(contract,allow_unicode=True,sort_keys=False,width=120)
    if any(x in payload for x in (str(reg.code_root),str(reg.clean_root),str(reg.raw_root))):
        raise ValueError('Local path leaked into preregistration')
    with output.open('x',encoding='utf-8') as stream: stream.write(payload)
    print(json.dumps({'status':'PREREGISTRATION_CREATED_NO_PROVIDER_GENERATED','cases':len(contract['providers']['mapping']),
                      'sha256':sha256_file(output),'bytes':output.stat().st_size}))

if __name__=='__main__': main()
