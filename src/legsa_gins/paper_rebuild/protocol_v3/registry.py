"""Read-only recovery of the complete, frozen v2.1 scientific cohort."""
from __future__ import annotations

from collections import Counter
import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import yaml

from ..hext.t5a_config_fidelity import decode_echo, compare_effective_echo
from ..hext.t5a_runtime import PROVIDER_KEYS, _pinned, _runtime_mapping
from ..manifest import sha256_file

PROFILES = ('F01','F02','F03','F04','A03','A04','A05','A06','A07','A08','A09')
STAGE = 'CLEAN8_PROTOCOL_V3'
TRANSPORT_KEYS = frozenset((*PROVIDER_KEYS, 'outputpath', 'case_id', 'run_id', 'run_label'))
INPUT_ROLES = {'imupath':'propagation_imu', 'gnsspath':'gnss_position_receiver_velocity_dual_yaw',
    'raw_doppler_factor_path':'raw_doppler_velocity', 'go2_attitude_prior_path':'go2_roll_pitch_weak_prior',
    'go2_horizontal_velocity_prior_path':'go2_horizontal_velocity_weak_prior'}


def reference(path, digest=None):
    path = Path(path)
    return {'path':str(path), 'sha256':digest or sha256_file(path)}


def _rows(path):
    return json.loads(Path(path).read_text())


def _config_root(record, stage):
    root = Path(record['output_root'])
    candidates = [root, stage/'RETAINED_RUNS'/record['run_id']/'solver']
    if record.get('archive_receipt'):
        candidates.insert(0, Path(record['archive_receipt']).parent/'solver')
    for candidate in candidates:
        for filename in ('PROTOCOL_V21_RUNTIME_CONFIG.yaml','PROTOCOL_V2_RUNTIME_CONFIG.yaml'):
            path = candidate/filename
            if path.is_file():
                return candidate, path
    raise RuntimeError('HARD_STOP_V3_FROZEN_CONFIG_MISSING: '+record['run_id'])


def _scientific_bytes(payload):
    return b''.join(line for line in payload.splitlines(keepends=True)
                    if line.split(b':',1)[0].decode().strip() not in TRANSPORT_KEYS)


def derive_expected_echo(target_bytes, donor_bytes, donor_echo):
    """Only path/identity lines may differ; all scientific bytes must match.

    This is an expectation for a historically failed run, not a fabricated
    historical echo. Every new emitted native echo is still checked exactly.
    """
    target, donor = _runtime_mapping(target_bytes), _runtime_mapping(donor_bytes)
    if _scientific_bytes(target_bytes) != _scientific_bytes(donor_bytes):
        raise RuntimeError('HARD_STOP_V3_ECHO_WITNESS_SCIENCE_BYTES')
    changed = {key for key in set(target)|set(donor) if target.get(key)!=donor.get(key)}
    if changed-TRANSPORT_KEYS or set(target)!=set(donor):
        raise RuntimeError('HARD_STOP_V3_ECHO_WITNESS_FIELDS')
    compare_effective_echo(donor_echo, donor_echo, expected_gnsspath=donor['gnsspath'])
    expected = deepcopy(donor_echo)
    for key in ('case_id','run_id','run_label'):
        if donor_echo[key] != donor[key]:
            raise RuntimeError('HARD_STOP_V3_ECHO_WITNESS_METADATA')
        expected[key] = target[key]
    for key, role in INPUT_ROLES.items():
        if role in expected['actual_solver_input_paths']:
            if expected['actual_solver_input_paths'][role] != donor[key]:
                raise RuntimeError('HARD_STOP_V3_ECHO_WITNESS_PROVIDER')
            expected['actual_solver_input_paths'][role] = target[key]
    return expected, {'status':'DERIVED_EXPECTATION_FROM_IDENTICAL_SCIENTIFIC_BYTES',
        'historical_target_echo_available':False, 'changed_keys':sorted(changed),
        'scientific_bytes_sha256':hashlib.sha256(_scientific_bytes(target_bytes)).hexdigest()}


def expected_echo(spec):
    _pinned(**{'path':spec['frozen_echo']['path'], 'expected':spec['frozen_echo']['sha256']})
    echo = decode_echo(Path(spec['frozen_echo']['path']).read_bytes())
    if 'frozen_echo_witness' not in spec:
        return echo, {'status':'DIRECT_FROZEN_ECHO','historical_target_echo_available':True}
    witness = spec['frozen_echo_witness']['config']
    _pinned(witness['path'], witness['sha256'])
    return derive_expected_echo(Path(spec['frozen_config']['path']).read_bytes(),
                                Path(witness['path']).read_bytes(), echo)


def build_registry(local_config, *, source_pins=None):
    """Read only sealed records/configs; no old Context(), raw data, or outputs."""
    paths = yaml.safe_load(Path(local_config).read_text())['paths']
    clean, code = Path(paths['clean_root']), Path(paths['code_root'])
    root21 = clean/'stages/CLEAN6_SENSOR_MODEL_V21'
    root2 = clean/'stages/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2'
    rootadd = clean/'stages/CLEAN6_ADDENDUM_FAMILIES_A1_A2'
    pinned_sources={p['path']:p['sha256'] for p in (source_pins or [])}
    def read_records(path):
        payload=Path(path).read_bytes()
        if source_pins is not None and pinned_sources.get(str(path))!=hashlib.sha256(payload).hexdigest():
            raise RuntimeError('HARD_STOP_V3_SOURCE_RECORD_PIN: '+str(path))
        return json.loads(payload)
    sources = [(row,root21,root21/'FINAL_RUN_RECORDS.json') for row in read_records(root21/'FINAL_RUN_RECORDS.json')]
    core_files = sorted((root2/'BATCHES').glob('BATCH_*/RUN_RECORDS.json'))
    recovered = root2/'IO_RECOVERY/IO_RECOVERY_20260912/BATCH_008_RECOVERY/RUN_RECORDS.json'
    if not (root2/'BATCHES/BATCH_008/RUN_RECORDS.json').exists():
        core_files.append(recovered)
    recovered14=root2/'IO_RECOVERY/IO_RECOVERY_20260912/BATCH_014_BOOKKEEPING_RECOVERY_001/RECOVERED_RUN_RECORDS.json'
    if not (root2/'BATCHES/BATCH_014/RUN_RECORDS.json').exists():core_files.append(recovered14)
    for path in core_files:
        sources.extend((row,root2,path) for row in read_records(path) if row['method_id']=='F01')
    for path in sorted((rootadd/'BATCHES').glob('BATCH_*/SOLVER_RECORDS.json')):
        sources.extend((row,rootadd,path) for row in read_records(path) if row['method_id']=='F01')
    core_path=code/'configs/paper_rebuild/clean6/CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml'
    add_path=code/'configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml'
    _pinned(core_path,'8c034244cdbd10951c0dc94f0b58cb76a35c9f470249a34542d6e259b364587c')
    _pinned(add_path,'fd11e416a3bd1a67c992a3606de0bb988035cae5c80647efa2091d00614546ec')
    core_contract=yaml.safe_load(core_path.read_text());add_contract=yaml.safe_load(add_path.read_text())
    case_pin=core_contract['sources']['case_registry']
    case_path=Path(case_pin['path'].replace('<CLEAN_ROOT>',str(clean)))
    _pinned(case_path,case_pin['sha256'])
    core_cases=list(csv.DictReader(case_path.open()))
    if [c['case_id'] for c in core_cases]!=core_contract['selection']['selected_case_ids']:
        raise RuntimeError('HARD_STOP_V3_FROZEN_CASE_ORDER')
    expected_meta={c['case_id']:c for c in core_cases+add_contract['case_rows']}
    for record,_,_ in sources:
        case=record['case_id'];meta=record.get('case_meta') or {}
        if case in expected_meta:
            expected=expected_meta[case]
            if case.startswith('D') and (str(meta.get('seed_value'))!=str(expected['seed_value'])
                    or record.get('seed_index')!=expected['seed_index']):
                raise RuntimeError('HARD_STOP_V3_FROZEN_CASE_SEED: '+case)
    specs, donors, payloads, pin_cache = [], {}, {}, {}

    def pin(path, digest=None):
        key=str(path)
        if digest is None:
            digest=pin_cache.setdefault(key,sha256_file(path)) if key not in pin_cache else pin_cache[key]
        return reference(path,digest)
    for record, stage, record_path in sources:
        root, cfg_path = _config_root(record,stage)
        config_ref=pin(cfg_path,record['config_hash'])
        payload=cfg_path.read_bytes()
        if cfg_path.is_symlink() or hashlib.sha256(payload).hexdigest()!=record['config_hash']:
            raise RuntimeError('HARD_STOP_V3_FROZEN_CONFIG_IDENTITY: '+record['run_id'])
        cfg=_runtime_mapping(payload)
        seq=record.get('dataset_id','BY2'); case=record['case_id']; method=record['method_id']
        domain='SEQUENCE' if seq!='BY2' else 'ADDENDUM' if record['run_id'].startswith('ADD_') else 'CORE'
        semi=domain=='ADDENDUM' or case.startswith('D')
        bundle = (root21/'02_CASE_PROVIDERS'/case/'PROVIDER_BUNDLE.json' if semi else
                  root21/'02_BASE_PROVIDERS'/seq/'PROVIDER_BUNDLE.json')
        spec={key:deepcopy(record.get(key)) for key in ('run_id','case_id','case_family','degradation_type_id',
              'seed_index','effective_profile','case_meta','source_registry_row','raw_source_hashes')}
        spec.update(sequence_id=seq,dataset_id=seq,configuration_id=method,method_id=method,domain=domain,
            data_mode='semisynthetic' if semi else 'real_clean', synthetic_data_used=False,
            semisynthetic_data_used=semi, frozen_config=config_ref,
            source_record=pin(record_path), frozen_bundle=pin(bundle),
            frozen_terminal_status=record['terminal_status'],
            frozen_providers={key:pin(cfg[key],record['provider_hashes'][key]) for key in PROVIDER_KEYS},
            evaluation={'window':record['window'],'base_time':record['base_time'],
                        'baseline_median_m':record['baseline_median_m'],'trace':record['trace']},
            frozen_nav=deepcopy(record['output_seal'].get('KF_GINS_Navresult.nav')),
            provider_key=seq+':'+(case if semi or seq=='BY2' else 'C00_clean_normal')+':'+record['provider_hashes']['gnsspath'])
        if 'RUN_MANIFEST.json' in record['output_seal'] and (root/'RUN_MANIFEST.json').is_file():
            spec['frozen_echo']=pin(root/'RUN_MANIFEST.json',record['output_seal']['RUN_MANIFEST.json']['sha256'])
            donors.setdefault(hashlib.sha256(_scientific_bytes(payload)).hexdigest(),spec)
        payloads[spec['run_id']]=payload
        specs.append(spec)
    for spec in specs:
        if 'frozen_echo' not in spec:
            donor=donors.get(hashlib.sha256(_scientific_bytes(payloads[spec['run_id']])).hexdigest())
            if donor is None:
                raise RuntimeError('HARD_STOP_V3_NO_SCIENTIFICALLY_IDENTICAL_ECHO_WITNESS: '+spec['run_id'])
            spec['frozen_echo']=deepcopy(donor['frozen_echo'])
            spec['frozen_echo_witness']={'config':deepcopy(donor['frozen_config']),'run_id':donor['run_id']}
    validate_registry(specs)
    return sorted(specs,key=lambda s:(s['domain']!='CORE',s['case_id']!='C00_clean_normal',s['sequence_id'],s['run_id']))


def validate_registry(specs):
    if len(specs)!=6468 or len({s['run_id'] for s in specs})!=6468:
        raise RuntimeError('HARD_STOP_V3_REGISTRY_UNIQUE_RUN_COUNT: '+str(len(specs)))
    if Counter(s['domain'] for s in specs)!=Counter(CORE=5951,SEQUENCE=22,ADDENDUM=495):
        raise RuntimeError('HARD_STOP_V3_REGISTRY_DOMAIN_COUNT')
    groups={}
    for s in specs:
        groups.setdefault((s['sequence_id'],s['case_id']),[]).append(s['method_id'])
    if len(groups)!=588 or any(Counter(v)!=Counter(PROFILES) for v in groups.values()):
        raise RuntimeError('HARD_STOP_V3_REGISTRY_ALL_ELEVEN_PROFILES')
    expected_core={'C00_clean_normal'}|{f'D{d:02d}_seed_{i:02d}' for d in range(1,61) for i in range(9)}
    expected_add={f'D{d:02d}_{duration}s_seed_{i:02d}' for d,durations in ((61,(10,20,30)),(62,(10,20))) for duration in durations for i in range(9)}
    if {s['case_id'] for s in specs if s['domain']=='CORE'}!=expected_core or {s['case_id'] for s in specs if s['domain']=='ADDENDUM'}!=expected_add:
        raise RuntimeError('HARD_STOP_V3_EXACT_CASE_IDS')
    expected_seq={('BY2H','CLEAN5_BY2H_NATURAL'),('BY2O','CLEAN5_BY2O_NATURAL')}
    if {(s['sequence_id'],s['case_id']) for s in specs if s['domain']=='SEQUENCE'}!=expected_seq:
        raise RuntimeError('HARD_STOP_V3_EXACT_SEQUENCE_IDS')
    for s in specs:
        if s['domain'] in ('CORE','ADDENDUM') and s['case_id'].startswith('D'):
            index=int(s['case_id'].rsplit('_',1)[1]);meta=s.get('case_meta') or {}
            if s.get('seed_index')!=f'seed_{index:02d}' or str(meta.get('seed_value'))!=str(260306001+index):
                raise RuntimeError('HARD_STOP_V3_EXACT_SEED_VALUE')
    return {'status':'PASS','unique_runs':6468,'core_cases':541,'addendum_cases':45,'sequence_c00_rows':33}
