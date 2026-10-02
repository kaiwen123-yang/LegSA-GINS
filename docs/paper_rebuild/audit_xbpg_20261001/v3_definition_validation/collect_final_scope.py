#!/usr/bin/env python3
"""Close this fixed queue from small receipts only; never open event/NAV inputs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(path.read_text())


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', type=Path, required=True)
    args = parser.parse_args()
    targets = [HERE / 'EVENT_READ_SUMMARY.csv', HERE / 'CALL_ACCOUNTING.json']
    if any(path.exists() for path in targets):
        raise ValueError('REFUSE_EXISTING_CLOSEOUT')
    aliases = read_json(args.roots)['aliases']
    root = Path(aliases['<VALIDATION_ROOT>'])
    queue = read_csv(HERE / 'CANDIDATE_QUEUE.csv')
    native = read_csv(HERE / 'RUN_MANIFEST.csv')
    assert len(queue) == len(native) == 10
    assert {r['slot_id'] for r in queue} == {r['slot_id'] for r in native}
    assert len({r['slot_id'] for r in native}) == 10
    assert all(r['status'] == 'COMPLETED' and r['native_attempts'] == r['native_calls'] == '1'
               and r['exit_code'] == '0' for r in native)
    baselines = {r['baseline_run_id'] for r in queue}
    assert len(baselines) == 7
    slots = sorted({'BASELINE__' + rid for rid in baselines} | {r['slot_id'] for r in queue})
    analyzer_hash = hashlib.sha256((HERE / 'event_analysis/analyze_events.py').read_bytes()).hexdigest()
    rows = []
    for slot in slots:
        receipt_path = root / 'analysis/event_cache' / slot / 'SCAN_RECEIPT.json'
        data = read_json(receipt_path)
        assert data['stream_status'] == 'COMPLETE' and data['analysis_status'] == 'VALIDATED'
        assert data['physical_eof_reached'] and data['complete_valid_stream']
        assert data['complete_payload_scan_count'] == data['event_payload_opens_this_call'] == 1
        assert data['hash_scope'] == 'FULL_STABLE_FILE'
        assert data['source_sha256'] == data['bytes_read_sha256']
        assert data['analyzer_sha256'] == analyzer_hash
        assert set(data['sa_validation_counts']) == {'VALIDATED'}
        baseline = slot.startswith('BASELINE__')
        expected_id = slot.split('__', 1)[1] if baseline else slot
        assert data['run_id'] == expected_id
        assert len(data['covariance']) == 1
        coverage, covariance = next(iter(data['covariance'].items()))
        assert covariance['status_counts'] == {'NONPOSITIVE_DIAGONAL': covariance['count']}
        rows.append(dict(
            slot_id=slot, candidate_id=data['candidate_id'], run_id=data['run_id'],
            group=data['group'], data_mode=data['data_mode'],
            synthetic_data_used=data['synthetic_data_used'],
            semisynthetic_data_used=data['semisynthetic_data_used'],
            source_path=data['source_path'], recorded_scan_sha256=data['source_sha256'],
            hash_verified_by='original single full scan; not rehashed by closeout',
            receipt_path='<VALIDATION_ROOT>/analysis/event_cache/' + slot + '/SCAN_RECEIPT.json',
            read_depth='FULL_PAYLOAD_READ_AND_SA_CHECKED_WITHIN_SCOPE',
            complete_payload_scans=data['complete_payload_scan_count'], events=data['events_read'],
            bytes=data['bytes_read'], sa_checked=data['sa_validation_counts']['VALIDATED'],
            stream_status=data['stream_status'], formula_status=data['analysis_status'],
            covariance_coverage=coverage, covariance_reports=covariance['count'],
            covariance_status='NONPOSITIVE_DIAGONAL', normalized_symmetry='NOT_TESTED',
            normalized_cholesky='NOT_TESTED', analyzer_sha256=analyzer_hash,
            closeout_event_payload_opens=0))
    comparisons = []
    for item in queue:
        p = HERE / 'event_analysis/summaries' / item['slot_id'] / 'SUMMARY.json'
        data = read_json(p)
        assert data['analysis_status'] == 'VALIDATED'
        assert data['candidate_run_id'] == item['slot_id']
        assert data['baseline_run_id'] == item['baseline_run_id']
        correction = ''
        if item['group'] == 'A1':
            extra = read_json(p.parent / 'A1_JOIN_VALIDATION_RECEIPT.json')
            assert extra['original_summary_preserved'] and extra['original_analyzer_modified'] is False
            assert extra['rows'] == extra['corrected_unique_attempts'] == extra['corrected_actual_accepted'] == 100
            assert extra['original_reported_attempts'] == 80
            correction = str((p.parent / 'A1_JOIN_VALIDATION_RECEIPT.json').relative_to(HERE))
        comparisons.append(dict(slot_id=item['slot_id'], stream_formula_comparison='VALIDATED',
            original_RP_opportunity_join='CORRECTED_IN_SUPPLEMENT' if correction else 'NO_SUPPLEMENT_REQUIRED',
            correction_receipt=correction))
    evaluations = read_json(HERE / 'evaluation/EVALUATION_FINAL_COUNTS.json')
    assert evaluations['slots'] == evaluations['actual_evaluator_children'] == evaluations['reference_child_opens'] == 17
    assert evaluations['baseline_original_field_checks'] == evaluations['baseline_original_field_matches'] == 1001
    assert evaluations['failure_slots'] == evaluations['unstarted_slots'] == evaluations['unknown_counter_slots'] == 0
    fixtures = [
        ('common/TEST_RECEIPT.json', 'native_fixture_processes'),
        ('candidates/N12_ONLY/TEST_RECEIPT.json', 'new_native_fixture_processes'),
        ('candidates/N16_ONLY/FIXTURE_RECEIPT.json', 'native_fixture_process_count'),
        ('candidates/N09_RP_ONLY/FIXTURE_RECEIPT.json', 'synthetic_native_processes')]
    fixture_rows = [dict(receipt=path, processes=read_json(HERE / path)[field]) for path, field in fixtures]
    assert sum(row['processes'] for row in fixture_rows) == 9
    result = dict(
        status='REGISTERED_QUEUE_CLOSED_WITH_EXPLICIT_LIMITS',
        data_mode='mixed_index_of_real_clean_semisynthetic_and_separately_labelled_synthetic_fixtures',
        synthetic_data_used=True, semisynthetic_data_used=True,
        synthetic_scope='9 fixture processes only; no synthetic fixture result enters real/semisynthetic metrics',
        planned_candidate_combinations=10, unique_baseline_case_method_identities=7,
        condition_groups=['C00', 'A1_20s_seed_00', 'A2_20s_seed_00', 'D15_seed_00'],
        underlying_natural_recordings=1,
        actual_candidate_native_calls=sum(int(row['native_calls']) for row in native),
        new_baseline_native_calls=0, real_native_failures=0, real_native_retries=0,
        synthetic_native_fixture_processes=9, fixture_receipts=fixture_rows,
        evaluator_children=17, baseline_evaluator_children=7, candidate_evaluator_children=10,
        evaluator_reference_opens=17, evaluator_failures=0, evaluator_retries=0,
        provider_generation_calls=0, historical_controller_calls=0, bootstrap_calls=0,
        new_original_matrix_calls=0, online_reference_reads=0,
        baseline_metric_support_matches=1001, baseline_metric_support_checks=1001,
        baseline_match_scope='7 new frozen-v3 evaluations against original records; 55+55 prior replay output hashes reused separately',
        unique_event_streams=len(rows), complete_event_scans=sum(r['complete_payload_scans'] for r in rows),
        event_rows_read=sum(r['events'] for r in rows), event_bytes_read=sum(r['bytes'] for r in rows),
        event_SA_checks=sum(r['sa_checked'] for r in rows),
        covariance_reports_baseline=sum(r['covariance_reports'] for r in rows if r['candidate_id'] == 'BASELINE'),
        covariance_reports_candidate=sum(r['covariance_reports'] for r in rows if r['candidate_id'] != 'BASELINE'),
        covariance_limit='all reports hit original zero scale diagonals; normalized symmetry/Cholesky not tested; separate raw key-snapshot supplement is not whole-stream PSD proof',
        comparisons=comparisons,
        closeout_event_payload_reads=0, closeout_NAV_STD_reads=0,
        old_2308_retained_error_series_reads=0,
        new_validation_calculations_performed=True,
        calculation_scope='candidate closed-loop frozen evaluation; fixed-window metrics; event snapshot/R/state arithmetic; exact recorded scalar subtraction; no bootstrap',
        technical_incidents_source='TECHNICAL_INCIDENTS.csv',
        science_manifests=['RUN_MANIFEST.csv', 'evaluation/EVAL_MANIFEST.csv'],
        no_automatic_followup=True)
    with targets[0].open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    with targets[1].open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({k: result[k] for k in ['actual_candidate_native_calls', 'synthetic_native_fixture_processes',
        'evaluator_children', 'unique_event_streams', 'event_rows_read', 'event_bytes_read', 'event_SA_checks',
        'covariance_reports_baseline', 'covariance_reports_candidate']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
