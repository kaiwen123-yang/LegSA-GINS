"""Synthetic scheduling checks; no provider, solver, evaluator or real metrics."""
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.clean6_canonical_v2 import runner, evaluation


def setup_evaluations(monkeypatch, tmp_path, evaluator):
    stage = tmp_path/'stage'
    stage.mkdir()
    output = tmp_path/'batch'
    output.mkdir()
    monkeypatch.setattr(runner, 'resolve', lambda *args: stage)
    monkeypatch.setattr(runner, 'machine_state', lambda: {'nproc': 4, 'memory_available_bytes': 10000})
    monkeypatch.setattr(evaluation, 'one_evaluation', evaluator)
    records = [{'run_id': str(i), 'dataset_id': dataset, 'terminal_status': 'COMPLETED'}
               for i, dataset in enumerate(('BY2', 'BY2H', 'BY2O', 'BY2', 'BY2'))]
    return records, output


def test_rss_probes_are_registered_evaluations_and_never_repeated(monkeypatch, tmp_path):
    calls = []
    def evaluate(record, version, *args):
        calls.append((record['run_id'], version))
        return {'run_id': record['run_id'], 'evaluator_version': version,
                'evaluation_status': 'COMPLETED', 'evaluator_peak_rss_bytes': 1000,
                'evaluation_runtime_seconds': .1}
    records, output = setup_evaluations(monkeypatch, tmp_path, evaluate)
    results, plan = runner.evaluate_batch(records, {'stage_root': 'unused'}, SimpleNamespace(),
                                          tmp_path, 'synthetic', output, 1000)
    assert len(results) == len(calls) == len(set(calls)) == 10
    assert calls[:6] == [(str(i), v) for i in range(3) for v in ('v3', 'v2')]
    assert plan['evaluator_pool_sizes'] == [2]
    assert all(p['reserved_peak_bytes'] <= p['memory_budget_bytes'] for p in plan['wave_plans'])


def test_failed_probe_stops_without_later_evaluation_or_retry(monkeypatch, tmp_path):
    calls = []
    def evaluate(record, version, *args):
        calls.append((record['run_id'], version))
        return {'run_id': record['run_id'], 'evaluator_version': version, 'evaluation_status': 'FAILED_EVALUATOR'}
    records, output = setup_evaluations(monkeypatch, tmp_path, evaluate)
    with pytest.raises(RuntimeError, match='probe failed'):
        runner.evaluate_batch(records, {'stage_root': 'unused'}, SimpleNamespace(), tmp_path, 'synthetic', output, 1000)
    assert calls == [('0', 'v3')]


def test_measured_wave_budget_violation_preserves_scene_and_stops(monkeypatch, tmp_path):
    calls = []
    def evaluate(record, version, *args):
        calls.append((record['run_id'], version))
        return {'run_id': record['run_id'], 'evaluator_version': version, 'evaluation_status': 'COMPLETED',
                'evaluator_peak_rss_bytes': 1000 if int(record['run_id']) < 3 else 5000,
                'evaluation_runtime_seconds': .1}
    records, output = setup_evaluations(monkeypatch, tmp_path, evaluate)
    with pytest.raises(RuntimeError, match='exceeded registered 75%'):
        runner.evaluate_batch(records, {'stage_root': 'unused'}, SimpleNamespace(), tmp_path, 'synthetic', output, 1000)
    assert len(calls) == len(set(calls)) == 8
    assert (output/'EVALUATION_WAVE_0001.json').is_file()
