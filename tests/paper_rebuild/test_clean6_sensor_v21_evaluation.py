"""Synthetic orchestration tests: zero scientific evaluator/native invocation."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21 import evaluation as e


@pytest.fixture
def scene(tmp_path, monkeypatch):
    reg = SimpleNamespace(clean_root=tmp_path/'clean', raw_root=tmp_path/'raw', code_root=tmp_path/'code')
    stage = reg.clean_root/'stages/CLEAN6_SENSOR_MODEL_V21'
    stage.mkdir(parents=True)
    scratch, output = tmp_path/'scratch', stage/'BATCHES/BATCH_001'
    scratch.mkdir()
    contract = {'stage_root': '<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21',
                'evaluation': {'evaluator': {'sha256': 'a'*64}}}
    records = [{'run_id': f'R{i}', 'dataset_id': dataset, 'case_id': 'C00',
                'terminal_status': 'COMPLETED', 'exit_code': 0, 'nav_sha256': str(i)*64}
               for i, dataset in enumerate(('BY2', 'BY2H', 'BY2O', 'BY2'))]
    calls = []
    def fake(record, version, contract, reg, root, commit):
        calls.append((record['run_id'], version))
        row = {'run_id': record['run_id'], 'evaluator_version': version,
               'dataset_id': record['dataset_id'], 'case_id': record['case_id'],
               'evaluation_status': 'COMPLETED', 'finite_output': True,
               'evaluation_invoked': True, 'evaluator_peak_rss_bytes': 1000,
               'evaluation_runtime_seconds': .1, 'native_nav_sha256': record['nav_sha256'],
               'evaluator_sha256': contract['evaluation']['evaluator']['sha256'],
               'horizontal_rmse_m': 1., 'synthetic_data_used': True, 'data_mode': 'synthetic_test'}
        path = e._original_result(root, record, version)
        path.parent.mkdir(parents=True, exist_ok=False)
        path.write_text(json.dumps(row))
        return row
    monkeypatch.setattr(e, 'one_evaluation', fake)
    monkeypatch.setattr(e, 'machine_state', lambda: {'memory_available_bytes': 100000, 'nproc': 4})
    return SimpleNamespace(reg=reg, stage=stage, scratch=scratch, output=output, contract=contract,
                           records=records, calls=calls, fake=fake)


def run(scene, records=None, output=None, scratch=None):
    return e.evaluate_batch(records or scene.records, scene.contract, scene.reg,
                            scratch or scene.scratch, 'b'*40, output or scene.output, 1000)


def test_six_formal_probes_saved_once_then_resume_does_not_repeat(scene):
    rows, report = run(scene)
    assert len(rows) == 8 and len(scene.calls) == len(set(scene.calls)) == 8
    assert scene.calls[:6] == [(f'R{i}', v) for i in range(3) for v in ('v3', 'v2')]
    pilot = json.loads((scene.stage/'PILOT_GATE.json').read_text())
    assert pilot['completed_probe_count'] == 6 and pilot['evaluator_peak_rss_bytes'] == 1000
    assert {x['dataset_id'] for x in pilot['probes']} == {'BY2', 'BY2H', 'BY2O'}
    assert len(list((scene.output/'EVALUATION_TERMINALS').rglob('*.json'))) == 8
    second, report = run(scene)
    assert second == rows and len(scene.calls) == 8
    assert report['prior_terminal_rows_recovered'] == 8 and report['new_terminal_rows'] == 0


def test_next_batch_needs_no_three_sequence_probe_and_uses_frozen_memory_bound(scene):
    run(scene)
    record = {**scene.records[0], 'run_id': 'LATER'}
    rows, report = run(scene, [record], scene.stage/'BATCHES/BATCH_002', scene.scratch/'later')
    assert len(rows) == 2 and len(scene.calls) == 10
    assert report['evaluator_pool_sizes'] == [2]
    plan = report['wave_plans'][0]
    assert plan['reserved_peak_bytes'] == 3500 and plan['memory_budget_bytes'] == 75000


def test_recover_frozen_completed_row_before_controller_receipt_without_rerun(scene):
    record = scene.records[0]
    scene.fake(record, 'v3', scene.contract, scene.reg, scene.scratch, 'b'*40)
    run(scene)
    assert scene.calls.count(('R0', 'v3')) == 1
    path = e._terminal_path(scene.output, record, 'v3')
    assert json.loads(path.read_text())['recovered_existing_result'] is True


def test_probe_failure_persists_terminal_and_never_retries(scene, monkeypatch):
    def failed(record, version, *args):
        scene.calls.append((record['run_id'], version))
        return {'run_id': record['run_id'], 'evaluator_version': version,
                'evaluation_status': 'FAILED_EVALUATOR', 'evaluation_invoked': True,
                'failure_message': 'synthetic evaluator failed'}
    monkeypatch.setattr(e, 'one_evaluation', failed)
    with pytest.raises(e.ScientificStop) as first:
        run(scene)
    assert first.value.kind == 'EVALUATOR_FAILURE_OR_NONFINITE'
    assert len(scene.calls) == 1
    assert e._terminal_path(scene.output, scene.records[0], 'v3').is_file()
    with pytest.raises(e.ScientificStop):
        run(scene)
    assert len(scene.calls) == 1 and not (scene.stage/'PILOT_GATE.json').exists()


def test_wave_failure_retains_all_launched_results_before_stop(scene, monkeypatch):
    run(scene)
    before = len(scene.calls)
    def mixed(record, version, contract, reg, scratch, commit):
        row = scene.fake(record, version, contract, reg, scratch, commit)
        if version == 'v3':
            row.update(evaluation_status='FAILED_EVALUATOR', failure_message='synthetic failure')
        return row
    monkeypatch.setattr(e, 'one_evaluation', mixed)
    record = {**scene.records[0], 'run_id': 'FAIL_WAVE'}
    output, scratch = scene.stage/'BATCHES/BATCH_FAIL', scene.scratch/'wave'
    with pytest.raises(e.ScientificStop):
        run(scene, [record], output, scratch)
    assert len(scene.calls)-before == 2
    assert len(list((output/'EVALUATION_TERMINALS').rglob('*.json'))) == 2
    with pytest.raises(e.ScientificStop):
        run(scene, [record], output, scratch)
    assert len(scene.calls)-before == 2


def test_nonfinite_metric_saved_as_failed_evidence_and_stops(scene, monkeypatch):
    def bad(record, version, *args):
        return {'run_id': record['run_id'], 'evaluator_version': version,
                'evaluation_status': 'COMPLETED', 'finite_output': True,
                'horizontal_rmse_m': float('nan')}
    monkeypatch.setattr(e, 'one_evaluation', bad)
    with pytest.raises(e.ScientificStop):
        run(scene)
    saved = json.loads(e._terminal_path(scene.output, scene.records[0], 'v3').read_text())['row']
    assert saved['evaluation_status'] == 'FAILED_EVALUATOR' and saved['finite_output'] is False
    assert 'nan' in saved['original_result_repr']


def test_missing_terminal_in_existing_invocation_directory_is_never_reexecuted(scene):
    root = e._original_result(scene.scratch, scene.records[0], 'v3').parent
    root.mkdir(parents=True)
    with pytest.raises(ValueError, match='no terminal'):
        run(scene)
    assert scene.calls == []


def test_unregistered_native_failure_stops_before_evaluation(scene):
    scene.records[0].update(terminal_status='FAILED', exit_code=1)
    with pytest.raises(e.ScientificStop) as error:
        run(scene)
    assert error.value.kind == 'NATIVE_UNREGISTERED_FAILURE' and scene.calls == []


def test_algorithm_failure_is_terminal_slot_without_rss_probe(scene, monkeypatch):
    run(scene)
    record = {**scene.records[0], 'run_id': 'ALGO_FAIL', 'terminal_status': e.ALGORITHM_FAILURE, 'exit_code': 1}
    def skip(record, version, *args):
        return {'run_id': record['run_id'], 'evaluator_version': version,
                'evaluation_status': 'NOT_RUN_ALGORITHM_FAILURE', 'evaluation_invoked': False,
                'evaluator_peak_rss_bytes': None}
    monkeypatch.setattr(e, 'one_evaluation', skip)
    rows, _ = run(scene, [record], scene.stage/'BATCHES/ALGO', scene.scratch/'algo')
    assert len(rows) == 2 and all(not r['evaluation_invoked'] for r in rows)
