#!/usr/bin/env python3
"""Small group views from saved replay receipts and validated analysis; no execution."""
import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    with path.open('w', newline='') as stream:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(stream, fields, lineterminator='\n'); writer.writeheader(); writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--roots', type=Path, required=True)
    p.add_argument('--group', choices=['C00', 'A1', 'A2', 'D15'], required=True); args = p.parse_args()
    aliases = json.loads(args.roots.read_text())['aliases']; external = Path(aliases['<MECHANISM_ROOT>'])
    queue = [r for r in read_csv(HERE / 'DIAGNOSTIC_QUEUE.csv') if r['group'] == args.group]
    identities = []; hashes = []; innovation = []; schedules = []; locations = []; key_values = []
    for item in queue:
        run = item['run_id']
        for variant in ['original', 'observed']:
            root = external / 'replays' / run / variant
            alias_root = '<MECHANISM_ROOT>/replays/' + run + '/' + variant
            receipt = json.loads((root / 'REPLAY_RECEIPT.json').read_text())
            manifest = read_csv(root / 'MANIFEST_COMPARISON.csv')
            access = json.loads((root / 'ACCESS_REVIEW.json').read_text())
            identities.append({'group': args.group, 'run_id': run, 'case_id': item['case_id'], 'method_id': item['method_id'],
                'variant': variant, 'data_mode': item['data_mode'], 'native_exec_count': receipt['native_exec_count'],
                'exit_code': receipt['exit_code'], 'status': receipt['status'], 'binary_sha256': receipt['binary_sha256'],
                'scientific_manifest_match': receipt['scientific_manifest_match'],
                'manifest_fields_exact': sum(r['status'] == 'EXACT_EQUAL' for r in manifest),
                'manifest_allowed_provenance_differences': sum(r['status'] == 'ALLOWED_PROVENANCE_DIFFERENCE' for r in manifest),
                'access_passed': access['passed'], 'write_outside_slot': len(access['write_outside_slot']),
                'raw_opens': len(access['raw_opens']), 'reference_candidate_opens': len(access['reference_candidate_opens']),
                'source_path': alias_root + '/REPLAY_RECEIPT.json', 'historical_payload_read': False})
            hashes.extend(receipt['output_comparisons'])
            files = ['KF_GINS_Navresult.nav', 'KF_GINS_STD.txt', 'EVAL_NAV.csv', 'LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv',
                     'RUN_MANIFEST.json', 'NATIVE_ACCESS.strace', 'REPLAY_RECEIPT.json', 'ACCESS_REVIEW.json',
                     'MANIFEST_COMPARISON.csv', 'OUTPUT_COMPARISON.csv', 'stdout.log', 'stderr.log']
            if variant == 'observed':
                files.append('observer/events.jsonl')
            for name in files:
                file = root / name
                locations.append({'run_id': run, 'variant': variant, 'path': alias_root + '/' + name,
                                  'bytes': file.stat().st_size if file.exists() else '',
                                  'status': 'RETAINED_NEW_REPLAY_OUTPUT' if file.exists() else 'MISSING',
                                  'old_historical_payload': False, 'uploaded_payload': False})
        schedules.extend(read_csv(HERE / 'groups' / args.group / (run + '_SCHEDULING.csv')))
        small = HERE / 'analysis' / run / 'SUMMARY.json'; report = json.loads(small.read_text())
        selected = {r['event_seq'] for r in read_csv(HERE / 'analysis' / run / 'KEY_SNAPSHOT_INDEX.csv')}
        event_csv = external / 'analysis' / run / 'innovation/SA_EVENT_ANALYSIS.csv'
        with event_csv.open() as stream:
            for row in csv.DictReader(stream):
                if row['event_seq'] in selected:
                    key_values.append({**row, 'derived_table_path': '<MECHANISM_ROOT>/analysis/' + run + '/innovation/SA_EVENT_ANALYSIS.csv'})
        for index, row in enumerate(report['rows']):
            c = row['counts']
            record = {'run_id': run, 'method_id': item['method_id'], 'case_id': item['case_id'], 'source': row['source'],
                      'fixed_window': row['fixed_window'], 'analysis_status': report['analysis_status'],
                      'SA_events': c['SA_EVALUATION_count'], 'validated': c.get('status:VALIDATED_SAME_SNAPSHOT', 0)}
            for key in ['Hdx_nonzero', 'nis_changed', 'oim_raw_changed', 'oim_capped_changed', 'oim_cap_masked', 'lsim_masked',
                        'shadow_final_R_changed', 'shadow_policy_acceptance_changed', 'n16_eligible', 'n16_lsim_changed', 'n16_shadow_final_R_changed']:
                record[key] = c.get(key, 0) if report['all_SA_events_validated'] else 'UNKNOWN_VALIDATION_NOT_COMPLETE'
            record.update(source_path='../../analysis/' + run + '/SUMMARY.json', row_key='/rows/' + str(index),
                          original_counts_json=json.dumps(c, sort_keys=True), actual_R_mutated=False, closedloop_not_tested=True)
            innovation.append(record)
        for sub, files in [('schedule', ['GNSS_CANDIDATE_FUNNEL.csv', 'MEASUREMENT_ATTEMPTS.csv', 'SCHEDULE_WITNESSES.json']),
                           ('innovation', ['SA_EVENT_ANALYSIS.csv', 'KEY_SNAPSHOTS.jsonl', 'SUMMARY.json'])]:
            for name in files:
                file = external / 'analysis' / run / sub / name
                locations.append({'run_id': run, 'variant': 'offline_validation', 'path': '<MECHANISM_ROOT>/analysis/' + run + '/' + sub + '/' + name,
                    'bytes': file.stat().st_size if file.exists() else '', 'status': 'RETAINED_VALIDATION_DERIVATIVE' if file.exists() else 'MISSING',
                    'old_historical_payload': False, 'uploaded_payload': False})
    dest = HERE / 'groups' / args.group
    for name, rows in [('IDENTITY.csv', identities), ('OUTPUT_HASH_CHECKS.csv', hashes), ('SCHEDULING_COMPACT.csv', schedules),
                       ('INNOVATION_COMPACT.csv', innovation), ('EVIDENCE_LOCATIONS.csv', locations), ('KEY_EVENT_VALUES.csv', key_values)]:
        write(dest / name, rows)
    receipt = {'group': args.group, 'unique_native_identities': len(queue),
        'native_invocations': sum(int(r['native_exec_count']) for r in identities),
        'native_failed': sum(int(r['exit_code']) != 0 for r in identities),
        'historical_output_hash_checks': sum(r['variant'] == 'original' for r in hashes),
        'observed_output_hash_checks': sum(r['variant'] == 'observed' for r in hashes),
        'hash_mismatches': sum(r['status'] != 'BYTE_IDENTICAL' for r in hashes),
        'manifest_mismatches': sum(not r['scientific_manifest_match'] for r in identities),
        'new_reference_reads': sum(r['reference_candidate_opens'] for r in identities),
        'new_evaluator_calls': 0, 'new_provider_calls': 0, 'new_performance_evaluations': 0,
        'independent_validation_calculation': True, 'closed_loop_fix_applied': False,
        'data_mode': queue[0]['data_mode'], 'synthetic_data_used': False,
        'semisynthetic_data_used': queue[0]['semisynthetic_data_used'] == 'True'}
    (dest / 'GROUP_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
