"""Synthetic metadata fixtures only; no native solver/evaluator or real metrics."""
import gzip
import json
from pathlib import Path
import zipfile

import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean6_canonical_v2 import pack as handoff

LABEL = 'sealed post-hoc after archival interruption; content verified against scratch (size+sha256)'


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def metadata_scene(tmp_path):
    stage = tmp_path/'stage'
    root = stage/'IO_RECOVERY'/'test_metadata_only'
    restart = stage/'RESTARTS'/'restart'
    put(restart/'CONTINUATION_FREEZE.json', {'code_commit': 'science', 'original_execution_freeze': {'code_commit': 'original'}})
    put(restart/'SEQUENCE_CONSISTENCY_GATE.json', {'status': 'PASS'})
    put(restart/'STOPPED.json', {'status': 'STOPPED_GATE_FAILURE', 'reason': 'historical archival interruption'})
    (restart/'REVALIDATION_RUNS').mkdir()
    root.mkdir(parents=True)
    scientific = root/'SCIENTIFIC_CONTRACT.yaml'
    scientific.write_text('protocol_id: fixture_protocol_v2\n')
    put(root/'IO_FIX_FREEZE.json', {'status': 'IO_FIX_FROZEN', 'scientific_code_commit': 'science',
        'io_fix_code_commit': 'io_fix', 'scientific_contract_path': str(scientific),
        'scientific_contract_sha256': handoff.sha256_file(scientific),
        'continuation_freeze_path': str(restart/'CONTINUATION_FREEZE.json'),
        'continuation_freeze_sha256': handoff.sha256_file(restart/'CONTINUATION_FREEZE.json')})
    put(stage/'EXECUTION_COMPLETE.json', {'status': 'EXECUTION_COMPLETE_PENDING_AGGREGATE',
        'run_count': 5973, 'evaluation_count': 11946, 'archive_pending_count': 0,
        'code_commit': 'science', 'io_fix_code_commit': 'io_fix'})
    for version in ('v3', 'v2'):
        put(stage/'13_AGGREGATE'/version/'FINAL_EVALUATION_SUMMARY.json', {
            'aggregate_completed': True, 'unique_evaluated': 5951, 'logical_evaluated': 7033,
            'protocol_id': 'fixture_protocol_v2', 'evaluator_version': version})
    rows = [{'run_id': f'R{i:05d}', 'dataset_id': 'BY2' if i < 5951 else ('BY2H' if i < 5962 else 'BY2O'),
             'terminal_status': 'COMPLETED', 'code_commit': 'science', 'horizontal_rmse_m': 123.45}
            for i in range(5973)]
    seal = root/'RUN_01963_POSTHOC_SEAL.json'
    put(seal, {'run_id': rows[0]['run_id'], 'annotation': LABEL, 'historical_full_file_seal_available': False,
               'versions': ['v3', 'v2']})
    rows[0]['posthoc_evaluation_seal'] = {'path': str(seal), 'sha256': handoff.sha256_file(seal),
        'annotation': LABEL, 'historical_full_file_seal_available': False, 'versions': ['v3', 'v2']}
    put(root/'BATCH008_INPUT_ACCEPTANCE.json', {'status': 'ACCEPTED_AUTHORIZED_POSTHOC_SEAL',
                                               'posthoc_evaluation_seal': rows[0]['posthoc_evaluation_seal']})
    put(root/'FULL_RUN_RECORDS.json', rows)
    evaluations = [{**row, 'evaluator_version': version, 'evaluation_status': 'COMPLETED'}
                   for row in rows for version in ('v3', 'v2')]
    put(root/'FULL_EVALUATION_RECORDS.json', evaluations)
    (root/'ARCHIVE_PENDING_LEDGER.jsonl').write_text(
        json.dumps({'status': 'ARCHIVE_PENDING', 'run_id': rows[0]['run_id']})+'\n'+
        json.dumps({'status': 'ARCHIVE_RESOLVED', 'run_id': rows[0]['run_id']})+'\n')
    (stage/'BATCH_LEDGER.notes').write_text(json.dumps({'status': 'BOOKKEEPING_REPAIR', 'historical_files_unchanged': True})+'\n')
    return stage, root, restart


def test_completed_recovery_preserves_history_and_all_metadata_identities(tmp_path):
    stage, root, restart = metadata_scene(tmp_path)
    before = (restart/'STOPPED.json').read_bytes()
    recovery = handoff.recovery_metadata(stage)
    assert recovery['identity']['archive_pending_count'] == 0
    assert len(recovery['runs']) == 5973 and len(recovery['evaluations']) == 11946
    assert all('horizontal_rmse_m' not in row for row in recovery['runs']+recovery['evaluations'])
    target = tmp_path/'package'; target.mkdir()
    identity = handoff.copy_recovery_metadata(recovery, stage, target)
    assert identity['posthoc_evaluation_seals'][0]['annotation'] == LABEL
    assert any(name.endswith('/BATCH_LEDGER.notes') for name in identity['package_members'])
    assert any(name.endswith('/BATCH008_INPUT_ACCEPTANCE.json') for name in identity['package_members'])
    assert len(json.loads(gzip.decompress((target/'recovery_provenance/FULL_RUN_IDENTITIES.json.gz').read_bytes()))) == 5973
    assert (restart/'STOPPED.json').read_bytes() == before


@pytest.mark.parametrize('field,value', [('run_count', 5972), ('evaluation_count', 11945),
                                        ('archive_pending_count', 1), ('status', 'IN_PROGRESS')])
def test_no_incomplete_execution_can_resolve_historical_stop(tmp_path, field, value):
    stage, root, _ = metadata_scene(tmp_path)
    path = stage/'EXECUTION_COMPLETE.json'
    row = json.loads(path.read_text()); row[field] = value; put(path, row)
    with pytest.raises(ValueError, match='Actual full execution'):
        handoff.recovery_metadata(stage)


def test_pending_ledger_overrides_zero_count_claim(tmp_path):
    stage, root, _ = metadata_scene(tmp_path)
    with (root/'ARCHIVE_PENDING_LEDGER.jsonl').open('a') as stream:
        stream.write(json.dumps({'status': 'ARCHIVE_PENDING', 'run_id': 'R00000'})+'\n')
    with pytest.raises(ValueError, match='pending ledger is not empty'):
        handoff.recovery_metadata(stage)


@pytest.mark.parametrize('mutation', ['old_protocol', 'incomplete_aggregate', 'duplicate_identity', 'changed_seal'])
def test_recovery_refuses_wrong_or_missing_provenance(tmp_path, mutation):
    stage, root, _ = metadata_scene(tmp_path)
    if mutation in ('old_protocol', 'incomplete_aggregate'):
        path = stage/'13_AGGREGATE/v3/FINAL_EVALUATION_SUMMARY.json'
        row = json.loads(path.read_text())
        row['protocol_id' if mutation == 'old_protocol' else 'aggregate_completed'] = 'old_v1' if mutation == 'old_protocol' else False
        put(path, row)
    elif mutation == 'duplicate_identity':
        path = root/'FULL_RUN_RECORDS.json'; rows = json.loads(path.read_text()); rows[1]['run_id'] = rows[0]['run_id']; put(path, rows)
    else:
        (root/'RUN_01963_POSTHOC_SEAL.json').write_text('{"changed":true}')
    with pytest.raises(ValueError):
        handoff.recovery_metadata(stage)


def test_pack_full_synthetic_metadata_preserves_historical_stop_and_recovery_probe(tmp_path):
    stage, root, restart = metadata_scene(tmp_path)
    configs = sorted(handoff.CONFIGS)+[f'test_profile_{i}' for i in range(6)]
    rows = []
    source_errors = stage/'retained'/'errors.csv.gz'; source_errors.parent.mkdir()
    with gzip.open(source_errors, 'wt') as stream:
        stream.write(','.join(handoff.SERIES_COLS)+'\n'+','.join(['0']*len(handoff.SERIES_COLS))+'\n')
    for index in range(5951):
        case, config = divmod(index, 11)
        nav_root = stage/'retained'/configs[config]
        if case == 0:
            nav_root.mkdir()
            with gzip.open(nav_root/'NAV_10HZ.csv.gz', 'wt') as stream: stream.write('fixture_only\n')
        rows.append({'run_id': f'R{index:05d}', 'case_id': 'C00_clean_normal' if case == 0 else f'TEST_{case}',
            'method_id': configs[config], 'effective_configuration_id': configs[config],
            'degradation_id': 'CLEAN' if case == 0 else 'SYNTHETIC_TEST_ONLY', 'seed_id': 'test',
            'case_family': 'synthetic_metadata_fixture', 'evaluation_status': 'COMPLETED',
            'yaw_rmse_deg': '0', 'output_root': str(nav_root), 'error_series_source': str(source_errors)})
    for version in ('v3', 'v2'):
        agg = stage/'13_AGGREGATE'/version
        for name in handoff.AGGREGATE_FILES:
            if not (agg/name).exists():
                (agg/name).write_text('{}' if name.endswith('.json') else 'fixture_only\ntrue\n')
        eval_root = stage/'12_OFFLINE_EVALUATION'/version; eval_root.mkdir(parents=True)
        pd.DataFrame(rows).to_csv(eval_root/'UNIQUE_EVALUATION_RESULTS.csv', index=False)
        pd.DataFrame(rows+rows[:1082]).to_csv(eval_root/'LOGICAL_EVALUATION_RESULTS.csv', index=False)
        (eval_root/'EVALUATION_STATUS.json').write_text('{}')
        (eval_root/'EVALUATION_FAILURES.csv').write_text('fixture_only\n')
        (eval_root/'FIELD_DEFINITIONS.md').write_text('Synthetic metadata fixture only.\n')
    historical = (restart/'STOPPED.json').read_bytes()
    output = tmp_path/'handoff.zip'
    result = handoff.pack(stage, output, package_dir=tmp_path/'package')
    assert result['passed'] and result['identity_probe']['io_recovery_identity']['archive_pending_count'] == 0
    with zipfile.ZipFile(output) as archive:
        assert archive.read('found/RESTARTS__restart__STOPPED.json') == historical
        probe = json.loads(archive.read('IDENTITY_PROBE.json'))
        assert probe['restart_identity']['restart_STOPPED_role'] == 'PRESERVED_HISTORICAL_ARCHIVAL_INTERRUPTION'
        assert probe['io_recovery_identity']['resolved_run_count'] == 5973
    assert (restart/'STOPPED.json').read_bytes() == historical


def test_nested_batch8_result_rows_cannot_bypass_frozen_metric_whitelist(tmp_path):
    stage, root, _ = metadata_scene(tmp_path)
    nested = root/'BATCH_008_RECOVERY'/'EVALUATION_RECORDS.json'
    put(nested, [{'run_id': 'R00000', 'evaluator_version': 'v3', 'evaluation_status': 'COMPLETED',
                  'horizontal_rmse_m': 987.0, 'unapproved_velocity_metric': 123456.0,
                  'source_row': '/scratch/same-row-different-copy-location'}])
    put(root/'RECOVERED_RUN_RECORDS.json', [{'run_id': 'R00000', 'code_commit': 'science',
                                           'unapproved_velocity_metric': 555.0}])
    recovery = handoff.recovery_metadata(stage)
    assert nested not in recovery['members']
    target = tmp_path/'package'; target.mkdir()
    identity = handoff.copy_recovery_metadata(recovery, stage, target)
    assert not (target/'recovery_provenance'/nested.relative_to(stage)).exists()
    assert any(row['source'] == nested.relative_to(stage).as_posix() and row['sha256'] == handoff.sha256_file(nested)
               for row in identity['row_projection_sources'])
    for row in identity['row_projection_sources']:
        content = gzip.decompress((target/row['package_member']).read_bytes())
        assert b'unapproved_velocity_metric' not in content and b'horizontal_rmse_m' not in content
    assert any(row['rows'][0].get('run_id') == 'R00000' for row in recovery['row_projections'] if row['rows'])


@pytest.mark.parametrize('status', ['IN_PROGRESS', 'FAILED_EVALUATOR', 'NOT_RUN_ALGORITHM_FAILURE'])
def test_single_inconsistent_evaluation_terminal_blocks_handoff(tmp_path, status):
    stage, root, _ = metadata_scene(tmp_path)
    path = root/'FULL_EVALUATION_RECORDS.json'; rows = json.loads(path.read_text())
    rows[0]['evaluation_status'] = status; put(path, rows)
    with pytest.raises(ValueError, match='terminal pair'):
        handoff.recovery_metadata(stage)


def test_single_technical_native_failure_is_not_full_evaluable_completion(tmp_path):
    stage, root, _ = metadata_scene(tmp_path)
    path = root/'FULL_RUN_RECORDS.json'; rows = json.loads(path.read_text())
    rows[0]['terminal_status'] = 'FAILED_TECHNICAL'; put(path, rows)
    with pytest.raises(ValueError, match='Unsupported or unfinished native'):
        handoff.recovery_metadata(stage)


def test_algorithm_failure_requires_both_explicit_not_run_evaluator_terminals(tmp_path):
    stage, root, _ = metadata_scene(tmp_path)
    path = root/'FULL_RUN_RECORDS.json'; rows = json.loads(path.read_text())
    rows[0]['terminal_status'] = 'ALGORITHM_FAILURE_ALL_YAW_REJECTED'; put(path, rows)
    eval_path = root/'FULL_EVALUATION_RECORDS.json'; evaluations = json.loads(eval_path.read_text())
    for row in evaluations:
        if row['run_id'] == rows[0]['run_id']: row['evaluation_status'] = 'NOT_RUN_ALGORITHM_FAILURE'
    put(eval_path, evaluations)
    assert handoff.recovery_metadata(stage)['identity']['resolved_evaluation_count'] == 11946
