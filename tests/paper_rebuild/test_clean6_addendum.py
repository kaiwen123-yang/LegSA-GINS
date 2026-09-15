"""Synthetic arithmetic and immutable-provider tests; never invoke real science."""
import csv
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from test_clean5_degradation_providers import inputs
from legsa_gins.paper_rebuild.clean6_addendum.providers import apply_outage, generate_case
from legsa_gins.paper_rebuild.clean6_addendum.aggregate import outage_metrics, wilcoxon, aggregate_all
from legsa_gins.paper_rebuild.clean6_addendum.runner import load_contract, make_runs, cleanup_batch, resolve_archived_records
from legsa_gins.paper_rebuild.clean6_addendum.runtime import native_template
from legsa_gins.paper_rebuild.manifest import sha256_file


CONTRACT = Path(__file__).resolve().parents[2]/'configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml'


@pytest.mark.parametrize('tid,duration', [('D61', 10), ('D61', 20), ('D61', 30), ('D62', 10), ('D62', 20)])
def test_outage_exact_validity_payload_and_sparse_heading(inputs, tmp_path, tid, duration):
    base, _, _ = inputs
    case = {'case_id': f'{tid}_{duration}s_seed_00', 'degradation_type_id': tid, 'duration_s': duration,
            'anchor_time_s': 90., 'seed_index': 'seed_00', 'seed_value': 260306001}
    original = {name: table.canonical_bytes() for name, table in base.bundle.tables.items()}
    generated, rows, _, evidence = apply_outage(base, case)
    before, after = np.asarray(base.gnss_tokens, float), np.asarray(rows, float)
    mask = (before[:, 0] >= 90-duration/2) & (before[:, 0] < 90+duration/2)
    assert np.array_equal(before[:, :15], after[:, :15])
    assert np.array_equal(before[~mask], after[~mask])
    assert np.all(after[mask, 15:17] == 0)
    assert np.all(after[mask, 17] == 0) if tid == 'D61' else np.array_equal(before[:, 17], after[:, 17])
    assert all(base.bundle.tables[name].canonical_bytes() == payload for name, payload in original.items())
    assert generated.tables['go2_rp'].canonical_bytes() == original['go2_rp']
    assert generated.tables['go2_hv'].canonical_bytes() == original['go2_hv']
    assert evidence['status'] == 'PASS'
    output = tmp_path/'output'
    bundle = generate_case(base, case, output, code_commit='a'*40, config_hash='b'*64)
    assert bundle['data_mode'] == 'synthetic_test' and bundle['synthetic_data_used'] is True
    with pytest.raises(FileExistsError):
        generate_case(base, case, output, code_commit='a'*40, config_hash='b'*64)


def test_contract_grid_unique_alias_run_registry():
    contract = load_contract(CONTRACT)
    templates = [{'case_id': 'C00_clean_normal', 'method_id': m, 'effective_profile': p}
                 for m, p in contract['profile_configuration_map'].items()]
    runs = make_runs(contract, templates)
    assert len(runs) == len({r['run_id'] for r in runs}) == 495
    assert len({(r['case_id'], r['method_id']) for r in runs}) == 495
    assert runs[0]['run_id'] == 'ADD_RUN_00001' and runs[-1]['run_id'] == 'ADD_RUN_00495'
    assert runs[0]['native_transport_run_id'] == 'RUN_06001' and runs[-1]['native_transport_run_id'] == 'RUN_06495'
    assert {r['degradation_type_id'] for r in runs} == {'D61', 'D62'}


def test_end_metric_last_half_open_epoch_and_nonfinite(tmp_path):
    path = tmp_path/'error_series.csv.gz'
    with gzip.open(path, 'wt', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['time', 'horizontal_err_m'])
        writer.writeheader()
        writer.writerows([{'time': t, 'horizontal_err_m': h} for t, h in [(1, 5), (2, 8), (3, 2), (4, 99)]])
    result = outage_metrics(path, 2, 4)
    assert result['outage_end_horizontal_error_m'] == 2
    assert result['max_horizontal_error_in_window_m'] == 8
    assert result['outage_end_evaluation_time_s'] == 3 and result['outage_matched_epoch_count'] == 2
    assert outage_metrics(path, 6, 7)['outage_end_horizontal_error_m'] is None
    with gzip.open(path, 'wt') as stream:
        stream.write('time,horizontal_err_m\n2,nan\n3,2\n4,99\n')
    result = outage_metrics(path, 2, 4)
    assert result['outage_end_horizontal_error_m'] == 2 and result['max_horizontal_error_in_window_m'] is None


def test_frozen_evaluator_utf8_bom_header_reads_without_evaluator(tmp_path):
    path = tmp_path/'error_series.csv.gz'
    with gzip.open(path, 'wt', encoding='utf-8-sig') as stream:
        stream.write('time,horizontal_err_m,yaw_err_deg\n1,8,2\n2,3,1\n3,99,0\n')
    with gzip.open(path, 'rb') as stream:
        assert stream.read(8).startswith(b'\xef\xbb\xbftime,')
    metrics = outage_metrics(path, 1, 3)
    assert metrics['outage_end_horizontal_error_m'] == 3
    assert metrics['max_horizontal_error_in_window_m'] == 8
    assert metrics['outage_end_evaluation_time_s'] == 2


def test_completed_evaluation_sidecar_recovery_never_invokes_evaluator(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean6_addendum import runtime
    contract = load_contract(CONTRACT)
    folder = tmp_path/'existing_evaluation'
    errors = folder/'FROZEN_EVALUATOR/error_series.csv.gz'
    errors.parent.mkdir(parents=True)
    with gzip.open(errors, 'wt', encoding='utf-8-sig') as stream:
        stream.write('time,horizontal_err_m\n1,8\n2,3\n3,99\n')
    old_hash = sha256_file(errors)
    original = folder/'EVALUATION_RESULT.json'
    original.write_text('{"synthetic_fixture":true}')
    original_bytes = original.read_bytes()
    def prohibited(*a, **kw):
        raise AssertionError('Completed evaluator must not be called again')
    monkeypatch.setattr(runtime, 'one_evaluation', prohibited)
    row = {'evaluation_status': 'COMPLETED', 'evaluation_output_root': str(folder), 'error_series_source': str(errors),
           'code_commit': 'a'*40, 'evaluator_version': 'v3', 'run_id': 'ADD_RUN_00001',
           'original_completed_evaluation_reused': True, 'historical_full_file_derived_seal_available': False}
    record = {'duration_s': 2, 'case_meta': {'outage_start_s': 1, 'outage_end_s': 3}}
    finished = runtime.finish_evaluation(row, record, contract, 'b'*40)
    assert finished['code_commit'] == 'a'*40 and finished['derived_metrics_code_commit'] == 'b'*40
    assert finished['outage_end_horizontal_error_m'] == 3
    assert sha256_file(errors) == old_hash and original.read_bytes() == original_bytes
    assert json.loads((folder/'EVALUATION_OUTPUT_SEAL.json').read_text())['historical_full_file_derived_seal_available'] is False
    with pytest.raises(FileExistsError):
        runtime.finish_evaluation(row, record, contract, 'b'*40)


def test_exclusive_evaluator_attempt_marker_prevents_repeat_after_interruption(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean6_addendum import runtime
    from types import SimpleNamespace
    contract = {'stage_root': str(tmp_path/'stage')}
    reg = SimpleNamespace(code_root=tmp_path, clean_root=tmp_path, raw_root=tmp_path/'raw')
    calls = []
    def interrupted(*a, **kw):
        calls.append(1)
        raise RuntimeError('synthetic interrupted first attempt')
    monkeypatch.setattr(runtime, 'one_evaluation', interrupted)
    record = {'run_id': 'ADD_RUN_00001', 'code_commit': 'a'*40, 'terminal_status': 'COMPLETED'}
    with pytest.raises(RuntimeError, match='synthetic interrupted'):
        runtime.evaluate(record, 'v3', contract, reg, tmp_path/'scratch', 'b'*40)
    with pytest.raises(FileExistsError):
        runtime.evaluate(record, 'v3', contract, reg, tmp_path/'scratch', 'b'*40)
    assert calls == [1]


def test_exact_wilcoxon_small_n_ties_and_zero():
    assert wilcoxon([1]*9) == pytest.approx(2/512)
    assert wilcoxon([1, -1]) == 1
    assert wilcoxon([0, 1e-13]) == 1
    assert wilcoxon([]) is None
    assert wilcoxon([1, 2, 3]) == .25


def test_all_archives_gate_precedes_first_deletion(tmp_path, monkeypatch):
    from legsa_gins.paper_rebuild.clean6_addendum import runner
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(runner, 'cleanup_exact', lambda *a, **kw: calls.append(a))
    receipts = [({}, {}, {'status': 'ARCHIVE_VERIFIED'}), ({}, {}, {'status': 'FAILED_IO'})]
    with pytest.raises(RuntimeError, match='Whole-batch'):
        cleanup_batch(receipts, tmp_path/'report', tmp_path/'scratch', SimpleNamespace(assert_healthy=lambda: None))
    assert not calls and not (tmp_path/'report').exists()


def test_archive_resolution_retains_scratch_provenance(tmp_path):
    source, archive = tmp_path/'scratch', tmp_path/'archive'
    original = source/'eval'/'v3'
    (archive/'v3'/'FROZEN_EVALUATOR').mkdir(parents=True)
    (archive/'v3'/'EVALUATION_RESULT.json').write_text('{}')
    (archive/'v3'/'FROZEN_EVALUATOR'/'error_series.csv.gz').write_bytes(b'synthetic')
    record = {'run_id': 'ADD_RUN_00001', 'output_root': str(source/'solver'), 'terminal_status': 'COMPLETED'}
    row = {'run_id': record['run_id'], 'evaluator_version': 'v3', 'evaluation_output_root': str(original),
           'source_row': str(original/'EVALUATION_RESULT.json'),
           'error_series_source': str(original/'FROZEN_EVALUATOR/error_series.csv.gz'),
           'outage_metric_source': str(original/'FROZEN_EVALUATOR/error_series.csv.gz')}
    records, rows = resolve_archived_records([(record, {'v3': original}, {'archive_root': str(archive)})], [row])
    assert records[0]['output_root'] == str(archive/'solver')
    assert rows[0]['outage_metric_source'] == str(archive/'v3/FROZEN_EVALUATOR/error_series.csv.gz')
    assert rows[0]['scratch_outage_metric_source'] == row['outage_metric_source']
    assert record['output_root'] == str(source/'solver')


def test_native_transport_retains_closed_loader_tokens_and_maps_outer_identity(tmp_path):
    template = tmp_path/'native.yaml'
    template.write_text('run_id: RUN_00001\nrun_label: RUN_00001\ncase_id: C00_clean_normal\ndata_mode: real_clean\nvrw: [1,2,3]\nstage_id: FROZEN\n')
    original = template.read_bytes()
    source = {'runtime_config_path': str(template), 'runtime_config_file_hash': sha256_file(template),
              'run_id': 'ADD_RUN_00001', 'case_id': 'D61_10s_seed_00'}
    text, audit = native_template(source)
    assert 'vrw: [1,2,3]\nstage_id: FROZEN\n' in text
    assert template.read_bytes() == original and audit['scientific_changes'] == []
    assert audit['native_identity']['run_id'] == 'RUN_06001'
    assert audit['native_identity']['case_id'] == 'D01_seed_00'
    assert audit['native_identity']['data_mode'] == 'real_base_controlled_degradation'
    assert audit['outer_identity']['run_id'] == 'ADD_RUN_00001'
    assert audit['outer_identity']['data_mode'] == 'semisynthetic'
    assert audit['C00_execution_or_evidence_claim'] is False
    assert audit['native_case_token_has_scientific_meaning'] is False


def test_native_loader_source_requires_compatibility_tokens():
    source = CONTRACT.parents[3]/'cpp/legsa_v23_port_core/src/config/port_config_loader.cpp'
    text = source.read_text()
    assert 'run_id.size() != 9 || run_id.substr(0, 4) != "RUN_"' in text
    assert 'degradation >= 1 && degradation <= 60 && seed >= 0 && seed <= 8' in text
    assert '? options.data_mode == "real_clean"' in text


def test_separate_full_addendum_tables_and_failure_awareness(tmp_path):
    contract = load_contract(CONTRACT)
    metrics = contract['statistics']['primary_metrics']+contract['statistics']['secondary_metrics']
    records, evaluations = [], []
    for case in contract['case_rows']:
        for method, profile in contract['profile_configuration_map'].items():
            failed = case['case_id'] == 'D61_10s_seed_00' and method == 'F04'
            record = {'run_id': 'ADD_RUN_'+str(len(records)+1).zfill(5), 'case_id': case['case_id'],
                'method_id': method, 'case_family': case['case_family'], 'effective_configuration_id': profile,
                'degradation_id': case['degradation_type_id'], 'seed_id': case['seed_index'],
                'terminal_status': 'ALGORITHM_FAILURE_ALL_YAW_REJECTED' if failed else 'COMPLETED'}
            records.append(record)
            for version in ('v3', 'v2'):
                evaluations.append({**record, 'evaluator_version': version,
                    'solver_terminal_status': record['terminal_status'], 'algorithm_failure': failed,
                    'technical_failure': False, 'evaluation_status': 'NOT_RUN_ALGORITHM_FAILURE' if failed else 'COMPLETED',
                    **{m: None if failed else 2. if method == 'F04' else 1. for m in metrics}})
    statuses = aggregate_all(evaluations, records, contract, tmp_path, 'a'*40, n_boot=20)
    assert all(r['unique_rows'] == 495 and r['logical_rows'] == 585 for r in statuses)
    assert not (tmp_path/'13_AGGREGATE').exists()
    root = tmp_path/'13_AGGREGATE_ADDENDUM'/'v3'
    with (root/'FAILURE_AWARE_PAIRWISE_CASE_LEVEL.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    failures = [r for r in rows if r['case_id'] == 'D61_10s_seed_00' and r['comparison'] == 'full_vs_no_HV']
    assert len(failures) == len(metrics) and all(r['pair_status'] == 'CANDIDATE_LOSS_ALGORITHM_FAILURE' for r in failures)
    assert json.loads((root/'HYPOTHESIS_DECISIONS.json').read_text())['H1'] == 'INCOMPLETE'
    with (root/'PAIRWISE_BY_DURATION.csv').open() as stream:
        duration = list(csv.DictReader(stream))
    assert {int(r['total_case_count']) for r in duration} == {9}
    with (root/'SEED_SUMMARY.csv').open() as stream:
        seeds = list(csv.DictReader(stream))
    assert max(int(r['distinct_seed_count']) for r in seeds) == 9
    assert max(int(r['finite_case_count']) for r in seeds) == 27
