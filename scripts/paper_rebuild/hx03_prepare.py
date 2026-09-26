#!/usr/bin/env python3
"""Prepare HX-03 source pins and exact conditional run manifest; no solves."""
from __future__ import annotations
import csv
import json
from pathlib import Path

import yaml

from legsa_gins.paper_rebuild.hext.hx03_injection import CLASSIC, FAMILIES, HEADING, IGNORED, sha, write_json


def main():
    W = Path.cwd()
    local = yaml.safe_load((W / 'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    stages = Path(local['clean_root']) / 'stages'
    stage = stages / 'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'
    config = W / 'configs/paper_rebuild/hext/HX03'
    config.mkdir(exist_ok=False)
    roots = {'W': W, 'STAGES': stages, 'V3': stages / 'CLEAN8_PROTOCOL_V3', 'HX03': stage,
             'SCRATCH': Path(local['hx02_scratch'])}
    def alias(p):
        p = Path(p)
        for k in ('W', 'V3', 'HX03', 'STAGES', 'SCRATCH'):
            if p == roots[k] or roots[k] in p.parents:
                return '$' + k + '/' + str(p.relative_to(roots[k]))
        raise ValueError(p)
    all_pins = {}
    def pin(path, expected=None, role=None):
        digest = sha(path)
        if expected is not None and digest != expected:
            raise ValueError('HARD_STOP_INPUT_SOURCE_PIN: ' + str(path))
        entry = {'path': alias(path), 'sha256': digest}
        all_pins[entry['path']] = digest
        return {**entry, **({'role': role} if role else {})}
    index_path = W / 'configs/paper_rebuild/v3/V3_PROVIDER_SOURCE_INDEX.json'
    pin(index_path, '130f93315d504bd7daddefc7eeabdbbeb10b763011531ade2766a0448a689a0e')
    index = json.loads(index_path.read_text())
    def source_path(text):
        return Path(text.replace('<CLEAN_ROOT>', local['clean_root']))
    manifest_path = stages / 'CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/02_MATRIX_SPEC_LOCK/CANONICAL541_CASE_MANIFEST.csv'
    pin(manifest_path, 'ac58b992a56f3ab05c585973fa6ceef1493d0d5cd6a9f0a9e18dae8edd998cb2')
    with manifest_path.open() as f:
        core = {r['case_id']: r for r in csv.DictReader(f)}
    addendum_path = stages / 'CLEAN6_ADDENDUM_FAMILIES_A1_A2/00_PREREGISTRATION/CASE_REGISTRY.csv'
    pin(addendum_path, 'eb03f2bb5fd16d1b43475a1dff787d48ebb4132bd16b53b9efeae47d7ea719cb')
    add_contract_path = W / 'configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml'
    pin(add_contract_path, 'fd11e416a3bd1a67c992a3606de0bb988035cae5c80647efa2091d00614546ec')
    add_contract = yaml.safe_load(add_contract_path.read_text())
    with addendum_path.open() as f:
        addendum = {r['case_id']: r for r in csv.DictReader(f)}
    declared = {r['case_id']: r for r in add_contract['case_rows']}
    if set(declared) != set(addendum):
        raise ValueError('HARD_STOP_ADDENDUM_CASE_LIST')
    for key, row in addendum.items():
        for name in ('seed_value', 'duration_s', 'outage_start_s', 'outage_end_s'):
            if float(row[name]) != float(declared[key][name]):
                raise ValueError('HARD_STOP_ADDENDUM_CASE_FIELD: ' + key + ':' + name)
    base_pin = pin(source_path(index['base_gnss']['BY2']['path']), index['base_gnss']['BY2']['sha256'], 'base_gnss')
    mapping_pin = pin(roots['V3'] / '07E_UNIFIED_FAILURE/DUAL_YAW_INJECTION_MAPPING.csv', role='heading_mapping_policy')
    cache = stages / 'CLEAN7_HEXT_EXTERNAL_SEQUENCES/02_BY2_IDENTITY/PROVIDER_CACHE'
    cache_pin = pin(cache / 'CACHE_MANIFEST.json')
    for name, value in json.loads((cache / 'CACHE_MANIFEST.json').read_text())['array_hashes'].items():
        pin(cache / name, value)
    cases = {'C00': {'case_id': 'C00', 'type': 'C00', 'family': FAMILIES['C00'], 'seed': 'NA', 'sources': []}}
    selected = [f'{kind}_seed_{seed:02d}' for kind in CLASSIC for seed in range(9)]
    selected += [key for key in addendum if key.startswith('D62_')]
    for key in selected:
        meta = core[key] if key in core else addendum[key]
        kind = meta['degradation_type_id']
        bundle_pin = index['case_bundles'][key]
        bundle_path = source_path(bundle_pin['path'])
        inputs = [pin(bundle_path, bundle_pin['sha256'], 'bundle'), base_pin]
        bundle = json.loads(bundle_path.read_text())
        item = bundle['providers']['gnsspath']
        inputs.append(pin(source_path(item['path']), item['sha256'], 'case_gnss'))
        if kind in HEADING:
            audit = bundle['audit_payloads']['dual_yaw']
            inputs += [pin(source_path(audit['path']), audit['sha256'], 'heading_audit'), mapping_pin]
        cases[key] = {'case_id': key, 'type': kind, 'family': FAMILIES[kind], 'seed': meta['seed_index'],
                      'seed_value': str(meta['seed_value']), 'duration_s': meta['duration_s'],
                      'anchor_time_s': float(meta['anchor_time_s']), 'sources': inputs}
    for key in [p.replace('D62_', 'D61_') for p in selected if p.startswith('D62_')]:
        source = index['case_bundles'][key]
        pin(source_path(source['path']), source['sha256'])
    parameters = pin(W / 'configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml')
    evaluator = Path(local['clean_root']) / '16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py'
    # This executable is source code, never the reference payload.
    evaluator_sha = sha(evaluator)
    from legsa_gins.paper_rebuild.clean5_sequence.evaluation_process import EVALUATOR_SHA256
    if evaluator_sha != EVALUATOR_SHA256:
        raise ValueError('HARD_STOP_EVALUATOR_IDENTITY')
    with (roots['V3'] / '07_AGGREGATE/MAIN_TABLE_V3.csv').open() as f:
        main_rows = list(csv.DictReader(f))
    identity = {method: {key: main_rows[line - 2][key] for key in
        ('source_nav_sha256', 'yaw_rmse_deg', 'evaluator_nav_sha256', 'h_rmse_m', 'up_rmse_m', 'yaw_p95_absolute_deg')}
        for method, line in [('LC01', 17), ('EXT05C', 18)]}
    if round(float(main_rows[2]['yaw_rmse_deg']), 6) != 1.886272:
        raise ValueError('HARD_STOP_F04_TABLE_IDENTITY')
    runs = []
    for method in ('LC01', 'EXT05C', 'LC01-BR'):
        runs.append({'case_id': 'C00', 'method': method, 'family': '身份门', 'type': 'C00', 'seed': 'NA', 'execution': 'IDENTITY_NATIVE', 'run_id': f'BY2__{method}__LIT__C00__NA'})
    for key in selected:
        c = cases[key]
        methods = ('LC01', 'EXT05C', 'LC01-BR') if c['type'] == 'D62' else ('LC01', 'EXT05C')
        for method in methods:
            execution = 'NATIVE'
            if c['type'] in IGNORED and c['seed'] != 'seed_00':
                execution = 'REUSE_C00_AFTER_TYPE_HASH_GATE'
            if c['type'] == 'D05' and c['seed'] != 'seed_00':
                execution = 'REUSE_D03_IF_D05_SEED00_NAV_EQUAL_ELSE_NATIVE'
            runs.append({**{k: c[k] for k in ('case_id', 'family', 'type', 'seed')}, 'method': method,
                'execution': execution, 'run_id': f"BY2__{method}__LIT__{key}__{c['seed']}"})
    write_json(config / 'CASES.json', cases)
    write_json(config / 'INPUT_PINS.json', all_pins)
    with (config / 'RUN_MANIFEST.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(runs[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(runs)
    write_json(config / 'CONTRACT.json', {'schema_version': 'hx03.v1', 'base_cache': cache_pin,
        'parameters': parameters, 'evaluator': '$STAGES/../' + str(evaluator.relative_to(Path(local['clean_root']))),
        'evaluator_sha256': evaluator_sha, 'window': [66, 340], 'base_time': 1772784000.,
        'identity': identity, 'max_native_concurrency': 22, 'idle_wait_limit_s': 600,
        'maximum_matrix_native': 298, 'expected_matrix_native_if_D05_equal': 282,
        'identity_native': 3, 'identity_evaluation': 4, 'matrix_evaluation_versions': ['v3', 'v2'],
        'maximum_total_native': 301, 'maximum_total_evaluation': 580,
        'expected_total_evaluation_if_D05_equal_and_all_outputs': 548,
        'ignored_type_confirmations_evaluation': 'No repeated evaluation; all nine rows use the frozen C00 metrics after NAV identity',
        'failure_thresholds': {'displacement_m': 10000, 'speed_mps': 50, 'height_excursion_m': 1000},
        'D05_policy': 'seed_00 run and compare with D03; reuse seeds01..08 only after same-method exact NAV equality',
        'all_rows_retained': True, 'legsa_native_budget': 0, 'legsa_evaluation_budget': 0})
    print(json.dumps({'cases': len(cases), 'logical_runs_including_identity': len(runs), 'source_pins': len(all_pins), 'config': str(config)}, indent=2))


if __name__ == '__main__':
    main()
