#!/usr/bin/env python3
"""Read only the eleven registered V3 objects; never generate inputs or run a solver."""
import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import yaml

TARGETS = [('C00', 'RUN_00003', 'F03'), ('C00', 'RUN_00006', 'A04'),
           ('C00', 'RUN_00004', 'F04'), ('A1', 'ADD_RUN_00102', 'F03'),
           ('A1', 'ADD_RUN_00105', 'A04'), ('A1', 'ADD_RUN_00103', 'F04'),
           ('A2', 'ADD_RUN_00399', 'F03'), ('A2', 'ADD_RUN_00402', 'A04'),
           ('A2', 'ADD_RUN_00400', 'F04'), ('D15', 'RUN_01403', 'A04'),
           ('D15', 'RUN_01401', 'F04')]
CASES = {'C00': 'C00_clean_normal', 'A1': 'D61_20s_seed_00',
         'A2': 'D62_20s_seed_00', 'D15': 'D15_seed_00'}
ROLES = ['imupath', 'gnsspath', 'raw_doppler_factor_path',
         'go2_attitude_prior_path', 'go2_horizontal_velocity_prior_path']
FLAGS = ['enable_receiver_velocity', 'enable_dual_yaw', 'enable_raw_doppler',
         'enable_source_aware', 'enable_go2_roll_pitch_prior', 'enable_go2_horizontal_velocity_prior']
FORBIDDEN = ['trace_used_online', 'receiver_imu_as_body_imu', 'final_v23_output_solver_input',
             'LegSA_output_solver_input', 'per_case_tuning', 'output_only_correction', 'epoch_deleted_for_metric']
BINARY_SHA = '96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c'
GNSS_COLS = ['time', 'latitude', 'longitude', 'height', 'std_n', 'std_e', 'std_d',
             'vn', 've', 'vd', 'std_vn', 'std_ve', 'std_vd', 'yaw_deg', 'yaw_std_deg',
             'position_valid', 'velocity_valid', 'yaw_valid']
IMU_COLS = ['time', 'delta_angle_x', 'delta_angle_y', 'delta_angle_z',
            'delta_velocity_x', 'delta_velocity_y', 'delta_velocity_z']


def write_csv(path, rows):
    assert rows, path
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def quality(payload, role):
    text = payload.decode('utf-8-sig')
    if role in ['imupath', 'gnsspath']:
        fields = IMU_COLS if role == 'imupath' else GNSS_COLS
        data = [dict(zip(fields, line.split())) for line in text.splitlines()
                if line.strip() and not line.startswith('#')]
        malformed = sum(len(line.split()) != len(fields) for line in text.splitlines()
                        if line.strip() and not line.startswith('#'))
    else:
        reader = csv.DictReader(io.StringIO(text))
        fields = reader.fieldnames
        data = list(reader)
        malformed = sum(None in r or any(v is None for v in r.values()) for r in data)
    times = [float(r['time']) for r in data]
    stats = dict(rows=len(data), columns=';'.join(fields), malformed_rows=malformed,
                 first_time=times[0], last_time=times[-1], time_unit='seconds_in_original_provider_domain',
                 duplicate_adjacent_times=sum(a == b for a, b in zip(times, times[1:])),
                 backward_times=sum(a > b for a, b in zip(times, times[1:])))
    cells = []
    numeric = {'time', 'roll_rad', 'pitch_rad', 'std_roll_rad', 'std_pitch_rad', 'vn', 've', 'vd',
               'std_vn', 'std_ve', 'std_vd', 'sat_count', *GNSS_COLS, *IMU_COLS}
    required = {'raw_doppler_factor_path': ['time', 'vn', 've', 'vd', 'std_vn', 'std_ve', 'std_vd', 'valid'],
                'go2_attitude_prior_path': ['time', 'roll_rad', 'pitch_rad', 'std_roll_rad', 'std_pitch_rad', 'source_status'],
                'go2_horizontal_velocity_prior_path': ['time', 'vn', 've', 'vd', 'std_vn', 'std_ve', 'std_vd', 'source_status', 'update_flag']}
    stats['required_columns_absent'] = ';'.join(x for x in required.get(role, fields) if x not in fields)
    for field in fields:
        values = [r.get(field) for r in data]
        missing = sum(x in [None, ''] for x in values)
        nonfinite = invalid = 0
        if field in numeric:
            for v in values:
                if v in [None, '']:
                    continue
                try:
                    nonfinite += not math.isfinite(float(v))
                except ValueError:
                    invalid += 1
        enum = dict(collections.Counter(values)) if field in ['source_status', 'update_flag', 'valid', 'position_valid', 'velocity_valid', 'yaw_valid', 'a1_heading_valid', 'go2_source_valid', 'provider_status', 'quality_flag', 'std_vd'] else {}
        if len(enum) > 20:
            enum = {'distinct_values': len(enum)}
        cells.append(dict(field=field, missing=missing, numeric_required=field in numeric,
                          nonfinite=nonfinite, nonnumeric=invalid, values=json.dumps(enum, sort_keys=True)))
    stats['invalid_numeric_cells'] = sum(r['nonfinite'] + r['nonnumeric'] for r in cells)
    stats['required_missing_cells'] = sum(r['missing'] for r in cells if r['field'] in required.get(role, fields))
    return stats, cells


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--roots', type=Path, required=True)
    args = ap.parse_args()
    config = json.loads(args.roots.read_text())
    aliases = config['aliases']
    repo = Path(aliases['<CODE_ROOT>'])
    out = repo / 'docs/paper_rebuild/audit_xbpg_20261001/v3_mechanism'
    receipt = out / 'INPUT_QUALIFICATION.json'
    assert not receipt.exists(), 'Already qualified; reuse receipt instead of rehashing payloads'
    def alias(value):
        s = str(value)
        for key, root in sorted(aliases.items(), key=lambda pair: -len(pair[1])):
            s = s.replace(root, key)
        return s
    binary = Path(aliases['<FROZEN_BINARY>'])
    binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    inputs, uses, fields, queue, seals, old_logs = [], [], [], [], [], []
    cache = {}
    for group, run, method in TARGETS:
        native = Path(aliases['<V3_ROOT>']) / '03_NATIVE'
        native = native / (run if group == 'C00' else 'V3R_CONTINUATION/' + run)
        summary = json.loads((native / 'V3_NATIVE_SUMMARY.json').read_text())
        seal = json.loads((native / 'OUTPUT_SEAL.json').read_text())
        cfg_path = native / 'V3_RUNTIME_CONFIG.yaml'
        cfg_bytes = cfg_path.read_bytes()
        cfg = yaml.safe_load(cfg_bytes)
        assert summary['run_id'] == run and summary['method_id'] == method
        assert summary['case_id'] == CASES[group] and summary['sequence_id'] == 'BY2'
        assert all(cfg[k] is False for k in FORBIDDEN) and cfg['old_runtime_input_count'] == 0
        config_sha = hashlib.sha256(cfg_bytes).hexdigest()
        flags = {k: cfg[k] for k in FLAGS}
        ok = config_sha == summary['config_hash'] and binary_sha == BINARY_SHA == summary['executable_sha256']
        for role in ROLES:
            path = Path(cfg[role])
            if str(path) not in cache:
                if path.is_file():
                    data = path.read_bytes()
                    observed = hashlib.sha256(data).hexdigest()
                    stats, cell_stats = quality(data, role)
                    identity = dict(input_id='I%03d' % (len(inputs) + 1), source_path=alias(path),
                                    role=role, observed_sha256=observed, bytes=len(data),
                                    read_depth='FULL_PAYLOAD_READ', payload_hash_reads=1, **stats)
                    fields.extend(dict(input_id=identity['input_id'], source_path=alias(path), **r) for r in cell_stats)
                else:
                    identity = dict(input_id='I%03d' % (len(inputs) + 1), source_path=alias(path), role=role,
                                    observed_sha256='', bytes=0, read_depth='EXPECTED_INPUT_NOT_FOUND', payload_hash_reads=0,
                                    **{k: 'unknown' for k in ['rows', 'columns', 'malformed_rows', 'first_time', 'last_time',
                                    'time_unit', 'duplicate_adjacent_times', 'backward_times', 'required_columns_absent',
                                    'invalid_numeric_cells', 'required_missing_cells']})
                cache[str(path)] = identity
                inputs.append(identity)
            identity = cache[str(path)]
            expected = summary['provider_hashes'][role]
            matched = identity['observed_sha256'] == expected
            ok = ok and matched
            uses.append(dict(run_id=run, case_id=CASES[group], method_id=method, input_id=identity['input_id'],
                             role=role, source_path=alias(path), recorded_sha256=expected,
                             newly_verified_sha256=identity['observed_sha256'], hash_status='MATCH' if matched else 'MISMATCH_OR_MISSING',
                             pin_source=alias(native / 'V3_NATIVE_SUMMARY.json'), pin_pointer='/provider_hashes/' + role))
        for name, value in seal['files'].items():
            if name in ['KF_GINS_Navresult.nav', 'KF_GINS_STD.txt', 'LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv', 'EVAL_NAV.csv']:
                seals.append(dict(run_id=run, filename=name, recorded_sha256=value,
                                  recorded_source=alias(native / 'OUTPUT_SEAL.json'),
                                  historic_payload_status='RELEASED_BY_ORIGINAL_POLICY_NOT_REOPENED', newly_verified_sha256=''))
        for stem in ['SOURCE_AWARE_WEIGHT_TRACE.csv', 'PORT_RUNTIME_LOOP_TRACE.csv', 'PORT_GNSS_UPDATE_TRACE.csv', 'PORT_SKIPPED_GNSS_TRACE.csv']:
            path = native / stem
            if not path.exists():
                path = native / (stem + '.gz')
            if path.exists():
                opener = gzip.open if path.suffix == '.gz' else open
                with opener(path, 'rt') as f:
                    header = f.readline().strip()
                old_logs.append(dict(run_id=run, source_path=alias(path), read_depth='HEADER_READ',
                                     columns=header, missing_for_current_question='same-event H/dx/P/baseR/full decision and pre-entry opportunity fields'))
        queue.append(dict(group=group, sequence='BY2', case_id=CASES[group], seed=summary['seed_index'],
                          method_id=method, run_id=run, native_status=summary['status'],
                          data_mode=summary['data_mode'], synthetic_data_used=summary['synthetic_data_used'],
                          semisynthetic_data_used=summary['semisynthetic_data_used'],
                          source_commit='ca73cb1fb48a020fd2a450d79e520562c34eeb24',
                          runner_commit=summary['code_commit'], executable_sha256=binary_sha,
                          config_source=alias(cfg_path), recorded_config_sha256=summary['config_hash'],
                          verified_config_sha256=config_sha, config_status='MATCH' if config_sha == summary['config_hash'] else 'MISMATCH',
                          starttime=cfg['starttime'], endtime=cfg['endtime'], full_range_preserved=True,
                          initialization_source=cfg['common_initialization_source'], scientific_flags=json.dumps(flags, sort_keys=True),
                          input_status='QUALIFIED_PINNED_INPUTS' if ok else 'BLOCKED_IDENTITY',
                          planned_original_calls=1, planned_observed_calls=1,
                          replay_reason='missing event snapshots; same-method output identity and disabled/enabled path controls',
                          historical_native_summary=alias(native / 'V3_NATIVE_SUMMARY.json')))
    for name, rows in [('QUALIFIED_INPUTS.csv', inputs), ('INPUT_USES.csv', uses), ('INPUT_FIELD_QUALITY.csv', fields),
                       ('DIAGNOSTIC_QUEUE.csv', queue), ('HISTORICAL_OUTPUT_HASHES.csv', seals), ('EXISTING_LOG_SCOPE.csv', old_logs)]:
        write_csv(out / name, rows)
    result = dict(stage_id=config['stage_id'], native_identities=len(queue), unique_input_files=len(inputs),
                  input_uses=len(uses), hash_match_uses=sum(r['hash_status'] == 'MATCH' for r in uses),
                  qualified_native=sum(r['input_status'] == 'QUALIFIED_PINNED_INPUTS' for r in queue),
                  frozen_binary_sha256=binary_sha, frozen_binary_match=binary_sha == BINARY_SHA,
                  science_calls=0, provider_generator_calls=0, raw_reference_opens=0, data_mode='diagnostic_replay_preparation',
                  synthetic_data_used=False, semisynthetic_data_used=True, new_semisynthetic_data_generated=False,
                  raw_generation_chain_reexecuted=False, provider_identity_level='LIVE_PAYLOAD_TO_FORMAL_RECORDED_PIN',
                  semantic_review='separate INPUT_LINEAGE.md; hash alone does not prove generation',
                  original_payloads_modified=False)
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
