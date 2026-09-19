"""Package-only continuation from an explicitly pinned completed table seal.

No provider, solver, evaluator, diagnostic or aggregate function is invoked.
The prior source-pin ledger binds consumed inputs to the completed finalizer;
unused retained payloads are not reopened. Differing/partial ZIPs are preserved
by the caller under a recorded attempt name before this exclusive writer runs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import finalize as f


def diagnostic_catalog(output, pins):
    catalog = []
    def add(relative, role):
        path = pins.check(output/relative)
        catalog.append({'member': relative, 'source': str(path),
                        'sha256': pins.values[str(path)], 'role': role})
    for version in f.pack.VERSIONS:
        for relative, role in (
            ('LADDER/'+version+'/UNIQUE_EVALUATION_RESULTS.csv', 'ladder'),
            ('NOISE_GRID/'+version+'/SENSITIVITY_GRID.csv', 'nine_grid'),
            ('SEQUENCES/'+version+'/BODY_FRAME_BIAS.csv', 'body_frame_bias'),
            ('SEQUENCES/'+version+'/WINDOW_SEGMENT_SUMMARY.csv', 'sequence_segments'),
            ('SEQUENCES/'+version+'/CONSISTENCY_ROWS.csv', 'sequence_consistency')):
            add('supplemental/V21/'+relative, role)
    add('supplemental/V21/OLD_H7_REFERENCE_STATUS.json', 'sequence_consistency')
    for dataset in f.diagnostics.DATASETS:
        add('supplemental/SEQUENCE_QUALITY/'+dataset+'.csv', 'sequence_quality')
    add('supplemental/V21/SENSOR_RESIDUALS.csv', 'sensor_residual_validation')
    for name in ('A04_CHECK.json', '10s.csv', '1s.csv', 'first30.csv'):
        add('supplemental/V21/VCHK/'+name, 'vchk_a04')
    for name in ('CHECK.json', 'CHECK.csv'):
        add('supplemental/V21/ROBUSTNESS/'+name, 'robustness')
    return catalog


def restore_pins(source, digest):
    pins = f.Pins()
    pins.add(source, digest, 'completed_finalizer_source_pin_ledger')
    for row in f._json(source):
        path = Path(row['path'])
        if not path.is_absolute() or '..' in path.parts or str(path) != row['path']:
            raise ValueError('Malformed restored source-pin path')
        if not isinstance(row['roles'], list) or not row['roles']:
            raise ValueError('Restored source pin must retain producer roles')
        for role in row['roles']:
            pins._record(path, row['sha256'], role)
    return pins


def run(reg, *, output_zip, source_ledger_sha256, aggregate_seal_sha256, code_commit):
    stage = f.resolve(f.STAGE, reg)
    output = stage/'20_FINALIZE'
    ledger = output/'FINALIZATION_INPUT_PINS.json'
    pins = restore_pins(ledger, source_ledger_sha256)
    seal_path = pins.add(output/'P13_MACHINE_REPORT/AGGREGATE_SEAL.json',
                         aggregate_seal_sha256, 'completed_aggregate_seal')
    seal = f._json(seal_path)
    if seal.get('status') != 'SEALED':
        raise ValueError('Package-only continuation requires a complete aggregate seal')
    def read(path):
        return f._json(pins.check(path))
    summary = read(output/'P13_MACHINE_REPORT/AGGREGATION_SUMMARY.json')
    if (summary['status'] != 'PASS_V21_AGGREGATION_WITH_EXPLICIT_HYPOTHESIS_AVAILABILITY'
            or summary['decision_rule_and_Outcome_changed'] is not False
            or summary['code_commit'] != seal['code_commit']):
        raise ValueError('Completed aggregate identity changed')
    print(json.dumps({'phase': 'PACKAGE_ONLY_PIN_LEDGER_RESTORED', 'pins': len(pins.values)}), flush=True)
    records, evaluations = [read(stage/name) for name in ('FINAL_RUN_RECORDS.json', 'FINAL_EVALUATION_RECORDS.json')]
    down_records, down_evaluations = [read(stage/'DOWNSTREAM'/name)
                                    for name in ('FINAL_RUN_RECORDS.json', 'FINAL_EVALUATION_RECORDS.json')]
    main, down = read(stage/'MAIN_ARCHIVE_CLOSURE.json'), read(stage/'DOWNSTREAM/NATIVE_DIAGNOSTICS_CLOSURE.json')
    current = f.closure_gate(main, down, records, evaluations, down_records, down_evaluations)
    closure = read(output/'FINALIZATION_CLOSURE_GATE.json')
    if any(closure.get(key) != value for key, value in current.items()):
        raise ValueError('Package continuation closure differs from completed finalizer')
    contract_path = reg.code_root/'configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml'
    pins.check(contract_path)
    contract = f.yaml.safe_load(contract_path.read_text())
    contracts = {}
    for key in ('core_contract', 'addendum_contract'):
        spec = contract['frozen_identities'][key]
        path = pins.add(reg.code_root/spec['path'], spec['sha256'], 'unchanged_frozen_contract')
        contracts[key] = f.yaml.safe_load(path.read_text())
    baseline = f.aggregate.load_baseline_indices(contracts['core_contract'], contracts['addendum_contract'], reg)
    for item in baseline['input_pins']:
        if pins.values.get(str(item['path'])) != item['sha256']:
            raise ValueError('Published baseline pin differs from completed finalizer')
    formal_records = records+[dict(row, formal_F01_reused=True) for row in baseline['records'] if row['method_id'] == 'F01']
    formal_evaluations = evaluations+[dict(row, formal_F01_reused=True) for row in baseline['evaluations'] if row['method_id'] == 'F01']
    f.pack.terminal_identity(formal_records, formal_evaluations)
    print(json.dumps({'phase': 'PACKAGE_ONLY_FORMAL_IDENTITIES', 'native': len(formal_records),
                      'evaluation': len(formal_evaluations)}), flush=True)
    evidence = []
    def add(label, path):
        pins.check(path)
        evidence.append({'member': 'evidence/'+label, 'source': str(path), 'sha256': pins.values[str(path)]})
    for label, path in (
        ('SENSOR_MODEL_V21_CONTRACT.yaml', contract_path),
        ('MAIN_ARCHIVE_CLOSURE.json', stage/'MAIN_ARCHIVE_CLOSURE.json'),
        ('DOWNSTREAM_ARCHIVE_CLOSURE.json', stage/'DOWNSTREAM/NATIVE_DIAGNOSTICS_CLOSURE.json'),
        ('FINALIZATION_INPUT_PINS.json', ledger),
        ('F01_DIAGNOSTIC_REUSE.json', output/'F01_DIAGNOSTIC_REUSE.json'),
        ('H7_REFERENCE_AVAILABILITY.json', output/'H7_REFERENCE_AVAILABILITY.json')):
        add(label, path)
    for label in ('p11b', 'p12'):
        add(label+'.json', f.resolve(contract['frozen_identities'][label]['path'], reg))
    for dataset in f.diagnostics.DATASETS:
        add(dataset+'_PROVIDER_VALIDATION.json', stage/'02_BASE_PROVIDERS'/dataset/'PROVIDER_VALIDATION.json')
    old_packages = [Path(path) for path, roles in pins.roles.items() if 'immutable_combined_v2_package_identity' in roles]
    if len(old_packages) != 1 or pins.values[str(old_packages[0])] != f.OLD_PACKAGE_SHA256:
        raise ValueError('Exactly the previously pinned v2 package is required')
    catalog = diagnostic_catalog(output, pins)
    package = f.pack.build_handoff(stage, output_zip, formal_records, formal_evaluations,
        aggregate_root=output, source_pins=pins.values, immutable_package=old_packages[0],
        immutable_package_sha256=f.OLD_PACKAGE_SHA256, diagnostic_members=catalog,
        evidence_members=evidence, evidence_roots=(stage, reg.code_root,
            f.resolve(f.CAL, reg).parent/'CLEAN6_HV_PRIOR_CALIBRATION'), code_commit=code_commit)
    result = {'status': 'PASS_FINALIZED_V21_HANDOFF', 'protocol_id': f.pack.PROTOCOL,
        'code_commit': summary['code_commit'], 'package_code_commit': code_commit,
        'output_root': str(output), 'closure': closure, 'aggregate_status': summary['status'],
        'H7_reference_status': read(output/'H7_REFERENCE_AVAILABILITY.json')['status'],
        'package': package, 'outcome_changed': False, 'new_outcome_created': False,
        'provider_calls': 0, 'native_calls': 0, 'evaluator_calls': 0, 'reference_trace_payload_reads': 0,
        'diagnostic_recomputations': 0, 'aggregate_recomputations': 0,
        'data_mode': 'real_and_controlled_degradation', 'synthetic_data_used': False,
        'semisynthetic_data_used': True, 'trace_used_online': False,
        'package_continuation': {'source_ledger_sha256': source_ledger_sha256,
                                 'aggregate_seal_sha256': aggregate_seal_sha256}}
    f.write_once(output/'FINALIZE_COMPLETE.json', result, pins)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--output-zip', type=Path, required=True)
    parser.add_argument('--source-ledger-sha256', required=True)
    parser.add_argument('--aggregate-seal-sha256', required=True)
    parser.add_argument('--code-commit', required=True)
    args = parser.parse_args(argv)
    result = run(f.registry(args.local_config), output_zip=args.output_zip,
        source_ledger_sha256=args.source_ledger_sha256, aggregate_seal_sha256=args.aggregate_seal_sha256,
        code_commit=args.code_commit)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
