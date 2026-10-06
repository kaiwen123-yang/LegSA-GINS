#!/usr/bin/env python3
"""Close the bounded evidence stage from saved small receipts, without execution.

This reads no raw, old error series, new event stream, NAV or STD payload.
It stats only the explicit new evidence paths already indexed by each group.
"""
import argparse
import collections
import csv
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GROUPS = ('C00', 'A1', 'A2', 'D15')
OUTPUTS = {'EVAL_NAV.csv', 'KF_GINS_Navresult.nav', 'KF_GINS_STD.txt',
           'LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv'}
PAPER = {
    'paper_package/gpss_v0/MANUSCRIPT_GPSS_v0.md',
    'paper_package/gpss_v0/manuscript_source.md',
    'paper_package/gpss_v0/SUPPLEMENT_GPSS_v0.md',
    'paper_package/gpss_v0/supplement_source.md',
    'paper_package/gpss_v0/NUMBER_LEDGER.csv',
    'paper_package/gpss_v0/CLAIM_SPECS.json',
    'paper_package/gpss_v0/figures/scripts/assemble_manuscript.py',
}


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def js(path):
    return json.loads(path.read_text())


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).splitlines()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', required=True, type=Path)
    args = parser.parse_args()
    external = Path(js(args.roots)['aliases']['<MECHANISM_ROOT>'])
    queue = rows(HERE / 'DIAGNOSTIC_QUEUE.csv')
    ledger = rows(HERE / 'REPLAY_MANIFEST.csv')
    gates = []

    def check(name, value, evidence):
        gates.append({'check': name, 'passed': bool(value), 'source': evidence})

    planned = {(r['run_id'], v) for r in queue for v in ('original', 'observed')}
    actual = [(r['run_id'], r['variant']) for r in ledger]
    check('queue_and_invocation_slots', len(actual) == len(set(actual)) == 22
          and set(actual) == planned, 'DIAGNOSTIC_QUEUE.csv;REPLAY_MANIFEST.csv')
    check('real_calls_no_retry_all_byte_identical', all(
        r['status'] == 'COMPLETED_BYTE_IDENTICAL' and r['native_calls'] == '1'
        and r['invocation_attempts'] == '1' and r['exit_code'] == '0' for r in ledger),
        'REPLAY_MANIFEST.csv')
    check('ledger_evaluator_zero', all(r['evaluator_calls'] == '0' for r in ledger),
          'REPLAY_MANIFEST.csv')
    details = []
    totals = collections.Counter()
    for group in GROUPS:
        base = HERE / 'groups' / group
        receipt = js(base / 'GROUP_RECEIPT.json')
        identity = rows(base / 'IDENTITY.csv')
        hashes = rows(base / 'OUTPUT_HASH_CHECKS.csv')
        compact = rows(base / 'INNOVATION_COMPACT.csv')
        schedules = rows(base / 'SCHEDULING_COMPACT.csv')
        members = {r['run_id']: r for r in queue if r['group'] == group}
        expected_slots = {(run, v) for run in members for v in ('original', 'observed')}
        saved_slots = [(r['run_id'], r['variant']) for r in identity]
        saved_hashes = [(r['run_id'], r['variant'], r['filename']) for r in hashes]
        expected_hashes = {(run, v, name) for run, v in expected_slots for name in OUTPUTS}
        check(group + ':exact_identity_and_five_file_sets', bool(members)
              and len(saved_slots) == len(expected_slots) and set(saved_slots) == expected_slots
              and len(saved_hashes) == len(expected_hashes) and set(saved_hashes) == expected_hashes
              and all(r['case_id'] == members[r['run_id']]['case_id']
                      and r['method_id'] == members[r['run_id']]['method_id'] for r in identity),
              f'DIAGNOSTIC_QUEUE.csv;groups/{group}/IDENTITY.csv;OUTPUT_HASH_CHECKS.csv')
        check(group + ':identity_access_hashes', all(
            r['status'] == 'COMPLETED_BYTE_IDENTICAL' and r['access_passed'] == 'True'
            and r['scientific_manifest_match'] == 'True' and r['write_outside_slot'] == '0'
            and r['native_exec_count'] == '1' and r['exit_code'] == '0'
            and r['raw_opens'] == '0' and r['reference_candidate_opens'] == '0'
            and r['historical_payload_read'] == 'False' for r in identity)
            and all(r['status'] == 'BYTE_IDENTICAL' and r['baseline_sha256'] == r['replay_sha256']
                    and len(r['replay_sha256']) == 64
                    and set(r['replay_sha256']) <= set('0123456789abcdef') for r in hashes),
            f'groups/{group}/IDENTITY.csv;OUTPUT_HASH_CHECKS.csv')
        group_ledger = [r for r in ledger if r['group'] == group]
        check(group + ':receipt_ledger_totals_and_no_new_evaluation',
              receipt['unique_native_identities'] == len(members)
              and receipt['native_invocations'] == len(expected_slots)
              == sum(int(r['native_calls']) for r in group_ledger)
              and receipt['historical_output_hash_checks'] == 5 * len(members)
              and receipt['observed_output_hash_checks'] == 5 * len(members)
              and all(receipt[k] == 0 for k in ('native_failed', 'hash_mismatches', 'manifest_mismatches',
                      'new_reference_reads', 'new_evaluator_calls', 'new_provider_calls', 'new_performance_evaluations'))
              and receipt['closed_loop_fix_applied'] is False,
              f'REPLAY_MANIFEST.csv;groups/{group}/GROUP_RECEIPT.json')
        count = collections.Counter()
        for item in (r for r in queue if r['group'] == group):
            run = item['run_id']
            innovation = js(HERE / 'analysis' / run / 'SUMMARY.json')
            scheduling = js(base / (run + '_SCHEDULE_RECEIPT.json'))
            counter_checks = rows(base / (run + '_SCHEDULE_COUNTER_CHECKS.csv'))
            count['observer_events'] += innovation['lines_read']
            count['SA_events_validated'] += innovation['validated_SA_events']
            count['manifest_counter_checks'] += len(counter_checks)
            count['SA_failed'] += innovation['failed_SA_events']
            count['SA_unavailable'] += innovation['unavailable_SA_events']
            full_rows = [r for r in schedules if r['run_id'] == run and r['window'] == 'full']
            unique_scheduled = {int(r['actual_gnss_scheduled_events']) for r in full_rows}
            check(run + ':schedule_identity_denominator', len(full_rows) == 6 and len(unique_scheduled) == 1,
                  f'groups/{group}/SCHEDULING_COMPACT.csv full rows')
            count['gnss_update_entries'] += scheduling['event_counts']['GNSS_UPDATE_ENTRY']
            count['gnss_input_identities_scheduled'] += next(iter(unique_scheduled))
            count['gnss_schedule_extra_entries_over_unique_identities'] += (
                scheduling['event_counts']['GNSS_UPDATE_ENTRY'] - next(iter(unique_scheduled)))
            count['repeated_accepted_aux_loaded_rows_within_run'] += sum(
                int(r['repeated_accepted_same_loaded_row']) for r in full_rows)
            check(run + ':complete_stream_and_all_SA_validated',
                  innovation['stream_status'] == 'COMPLETE' and innovation['analysis_status'] == 'VALIDATED'
                  and innovation['all_SA_events_validated'] and scheduling['stream_complete']
                  and innovation['failed_SA_events'] == 0 and innovation['unavailable_SA_events'] == 0
                  and innovation['actual_R_mutated'] is False and innovation['shadow_decision_applied'] is False
                  and innovation['closedloop_not_tested'] is True
                  and all(innovation[k] == 0 for k in ('native_calls', 'evaluator_calls', 'provider_calls',
                          'reference_reads', 'retained_error_series_reads'))
                  and scheduling['rows_read'] == innovation['lines_read']
                  and len(counter_checks) == 6 and all(c['status'] == 'EXACT_EQUAL'
                          and c['recorded_value'] == c['event_accepted_count'] for c in counter_checks)
                  and sum(int(r['SA_events']) for r in compact if r['run_id'] == run)
                  == innovation['validated_SA_events'],
                  f'analysis/{run}/SUMMARY.json;groups/{group}/{run}_SCHEDULE_RECEIPT.json')
        for key in ('Hdx_nonzero', 'nis_changed', 'oim_raw_changed', 'shadow_final_R_changed',
                    'shadow_policy_acceptance_changed', 'lsim_masked', 'oim_cap_masked',
                    'n16_eligible', 'n16_shadow_final_R_changed'):
            count[key] = sum(int(r[key]) for r in compact if r['method_id'] == 'F04')
        source_schedule = [{k: r[k] for k in ('run_id', 'method_id', 'window', 'source',
                           'accepted', 'qualified_but_entry_blocked_events')}
                           for r in schedules if r['window'] in ('full', 'during')]
        missing = []; size_mismatch = []
        for loc in rows(base / 'EVIDENCE_LOCATIONS.csv'):
            prefix = '<MECHANISM_ROOT>/'
            assert loc['path'].startswith(prefix)
            path = external / loc['path'][len(prefix):]
            assert path.resolve().is_relative_to(external.resolve())
            if not path.is_file():
                missing.append(loc['path'])
            elif path.stat().st_size != int(loc['bytes']):
                size_mismatch.append(loc['path'])
            count['indexed_new_evidence_files_stat_checked'] += 1
        check(group + ':indexed_new_evidence_still_present', not missing and not size_mismatch,
              f'groups/{group}/EVIDENCE_LOCATIONS.csv (stat only, no new hash)')
        details.append({'group': group, 'receipt': receipt, 'counts': dict(count),
                        'actual_schedule_counts': source_schedule, 'missing_new_files': missing,
                        'indexed_size_mismatches': size_mismatch})
        totals.update(count)
    baseline = 'b0fdb81f103a5f0e7c7432e5247a9341524c7fa6'
    prefix = str(HERE.relative_to(REPO)) + '/'
    changes = set(git('diff', '--name-only', baseline)) | set(git('ls-files', '--others', '--exclude-standard'))
    unexpected = sorted(p for p in changes if not p.startswith(prefix) and p not in PAPER)
    check('git_change_scope', not unexpected, 'git diff baseline plus untracked nonignored paths')
    display = js(HERE / 'display/CHECK_RECEIPT.json')
    synthetic = js(HERE / 'observer/SYNTHETIC_RECEIPT.json')
    supplemental = js(HERE / 'exposure/D39_WINDOW_VALIDATION_RECEIPT.json')
    wording = js(HERE / 'MECHANISM_WORDING_CHECK_RECEIPT.json')
    document_checks = []
    for row in wording['maintenance_files'] + wording['protected_files']:
        assert row['path'].startswith('<CODE_ROOT>/')
        path = REPO / row['path'][len('<CODE_ROOT>/'):]
        assert path.stat().st_size < 1_000_000
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = row.get('after_sha256', row.get('sha256'))
        document_checks.append({'path': row['path'], 'recorded_sha256': expected,
                                'newly_verified_sha256': digest, 'matches': digest == expected})
    check('M01_wording_receipt_and_current_small_documents', wording['status'] == 'PASS'
          and wording['check_count'] == len(wording['checks']) == 27
          and all(c['status'] == 'PASS' for c in wording['checks'])
          and all(n == 0 for n in wording['process_counts'].values())
          and wording['scientific_source_modified'] is False and wording['new_performance_numbers'] is False
          and all(c['matches'] for c in document_checks), 'MECHANISM_WORDING_CHECK_RECEIPT.json; nine small current documents')
    check('display_receipt', display['failures'] == 0, 'display/CHECK_RECEIPT.json')
    check('synthetic_noninterference_receipt', synthetic['fixture_failures'] == 0
          and not synthetic['failed'], 'observer/SYNTHETIC_RECEIPT.json')
    check('D39_supplemental_receipt_complete_and_old_receipts_unchanged',
          supplemental['status'] == 'COMPLETE' and supplemental['selected_files']
          == supplemental['completed_files'] == supplemental['supplemental_payload_open_attempts'] == 22
          and supplemental['unavailable_files'] == 0 and supplemental['window_rows'] == 66
          and supplemental['available_window_rows'] == 44 and supplemental['empty_intersection_rows'] == 22
          and supplemental['old_main_scan_receipt_unchanged'] and supplemental['old_file_checks_unchanged']
          and all(supplemental[k] == 0 for k in ('solver_calls', 'provider_generator_calls',
                  'original_evaluator_calls', 'controller_calls', 'bootstrap_calls', 'raw_reference_payload_opens',
                  'nav_std_payload_opens', 'd22_payload_opens', 'other_error_series_payload_opens', 'source_writes')),
          'exposure/D39_WINDOW_VALIDATION_RECEIPT.json (existing supplemental read, not a read by this script)')
    result = {
        'scope': 'bounded_replay_identity_and_observation_accounting; not scientific correctness PASS',
        'all_accounting_checks_passed': all(g['passed'] for g in gates), 'checks': gates,
        'real_unique_native_identities': len(queue),
        'real_native_invocations': sum(int(r['native_calls']) for r in ledger),
        'real_invocation_attempts': sum(int(r['invocation_attempts']) for r in ledger),
        'real_native_failures': sum(r['exit_code'] != '0' for r in ledger),
        'real_evaluator_calls': sum(int(r['evaluator_calls']) for r in ledger),
        'provider_generator_calls': sum(g['receipt']['new_provider_calls'] for g in details),
        'native_fixture_processes_separate': synthetic['native_fixture_processes'],
        'fixture_subscenarios': synthetic['fixture_subscenarios'],
        'fixture_failures': synthetic['fixture_failures'], 'fixture_retries': synthetic['fixture_retries'],
        'historical_output_hash_matches': sum(g['receipt']['historical_output_hash_checks'] for g in details),
        'observer_output_hash_matches': sum(g['receipt']['observed_output_hash_checks'] for g in details),
        'new_evaluations_or_fixed_algorithm_RMSE': 0, 'observer_shadow_feedback': False,
        'independent_validation_calculation': True, 'counts': dict(totals), 'groups': details,
        'count_scopes': {
            'observer_events': 'All 11 observed histories; log records, not epochs or independent trials',
            'SA_events_validated': 'All 11 observed histories, including SA-disabled wrapper calls',
            'weight_fields': 'Hdx_nonzero/nis_changed/oim_raw_changed/shadow_final_R_changed/'
                            'shadow_policy_acceptance_changed/lsim_masked/oim_cap_masked/'
                            'n16_eligible/n16_shadow_final_R_changed are F04 only; per-event local shadows',
            'schedule_counts': 'full rows count each native once; during rows are separate views, never added to full',
            'repeated_rows': 'Within a native and source only; physical arrival time remains UNKNOWN',
        },
        'git_baseline': baseline, 'unexpected_changed_paths': unexpected,
        'display_checks_recorded': display['checks'],
        'mechanism_wording_checks_recorded': wording['check_count'],
        'small_current_documents_newly_hash_verified': document_checks,
        'D39_supplemental_receipt': supplemental,
        'read_scope_this_script': 'small saved tables/receipts, nine small documents and exact indexed new file stat; no scientific payload read',
        'data_mode': 'separate_real_and_semisynthetic_replays_with_synthetic_fixture_gate',
        'synthetic_data_used': True, 'semisynthetic_data_used': True,
        'synthetic_scope': 'fixture only; excluded from real replay/performance denominators',
    }
    (HERE / 'FINAL_CHECKS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('all_accounting_checks_passed', 'real_unique_native_identities',
          'real_native_invocations', 'real_native_failures', 'real_evaluator_calls', 'counts')}, ensure_ascii=False))
    return 0 if result['all_accounting_checks_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
