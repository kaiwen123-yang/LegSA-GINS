#!/usr/bin/env python3
"""Join completed EXT result tables and receipts, without solving or evaluating."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def rows(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))


def write_rows(path, values):
    fields = list(dict.fromkeys(k for r in values for k in r))
    with path.open('x', newline='') as handle:
        writer = csv.DictWriter(handle, fields, lineterminator='\n')
        writer.writeheader(); writer.writerows(values)


def windows_mount_path(path):
    parts = path.parts
    if len(parts) >= 3 and parts[1] == 'mnt' and len(parts[2]) == 1:
        return parts[2].upper() + ':\\' + '\\'.join(parts[3:])
    return 'NOT_A_WINDOWS_DRIVE_MOUNT'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', required=True)
    args = parser.parse_args()
    aliases = json.loads(Path(args.roots).read_text())['aliases']
    repo = Path(aliases['<CODE_ROOT>'])
    root = Path(aliases['<EXT_REPRO_ROOT>'])
    base = repo / 'docs/paper_rebuild/hext/EXT_REPRODUCTION'
    tables, common, native, declarations, launches, evaluations, local = [], [], [], [], [], [], []
    for seq in ('BY2', 'BY2H', 'BY2O'):
        evaluation = base / 'evaluation_results' / seq
        receipt = json.loads((evaluation / 'EVALUATION_RECEIPT.json').read_text())
        assert receipt['evaluation_status'] == 'COMPLETED'
        assert receipt['evaluator_child_invocations'] == receipt['actual_reference_open_count'] == 1
        assert receipt['reference_hash_matched']
        assert not json.loads((evaluation / 'REUSE_LIMITATIONS.json').read_text())
        evaluations.append(receipt)
        for source_name, target in (('RESULT_ROWS.csv', tables), ('COMMON_SUPPORT.csv', common)):
            for row in rows(evaluation / source_name):
                item = dict(row)
                item['public_source_path'] = f'<EXT_REPRO_DOCS>/evaluation_results/{seq}/{source_name}'
                item['public_source_row_key'] = ';'.join(f'{k}={row[k]}' for k in (
                    ('method_id', 'support') if source_name == 'RESULT_ROWS.csv' else ('group_id', 'support', 'method_id')))
                item['sequence_id'] = seq
                if source_name == 'RESULT_ROWS.csv':
                    count, denominator = row['available_epoch_count'], row['paired_epoch_denominator']
                    item['availability_fraction'] = str(Decimal(count) / Decimal(denominator)) if count else ''
                    item['derived_field_definition'] = 'availability_fraction = available_epoch_count / paired_epoch_denominator; other original fields copied unchanged'
                target.append(item)
        native += rows(base / 'native_results' / seq / 'NATIVE_SUMMARY.csv')
        for method in ('EXT01', 'EXT02', 'EXT03'):
            run = json.loads((base / 'native_results' / seq / (method + '_RUN.json')).read_text())
            launch_path = root / 'batches' / seq / (method + '.launch.json')
            launch = json.loads(launch_path.read_text())
            assert launch['status'] == 'EXITED' and launch['exit_code'] == 0
            assert run['status'] == 'COMPLETED' and run['attempt'] == 1
            assert run['completed_epochs'] == run['planned_paired_epochs']
            assert run['valid_epochs'] + sum(run['failure_counts'].values()) == run['completed_epochs']
            assert run['new_method_sequence_calls'] == 1 and run['evaluator_calls'] == 0
            assert run['trace_used_online'] is False
            declarations.append(run)
            launches.append({'run_id': run['run_id'], 'status': launch['status'], 'exit_code': launch['exit_code'],
                             'source_path': f'<EXT_REPRO_ROOT>/batches/{seq}/{method}.launch.json'})
            for filename in ('RUN.json', 'HEADING.csv', 'EPOCH_EVIDENCE.jsonl.gz'):
                actual = root / 'runs' / run['run_id'] / filename
                assert actual.is_file()
                local.append({'run_id': run['run_id'], 'kind': filename,
                              'alias': f'<EXT_REPRO_ROOT>/runs/{run["run_id"]}/{filename}',
                              'wsl_path': str(actual),
                              'windows_path': windows_mount_path(actual),
                              'retention': 'PRESENT_NEW_OUTPUT_RETAINED',
                              'hash_status': 'WRITER_RECORDED_NOT_REHASHED_BY_SUMMARY',
                              'recorded_sha256': run.get('outputs', {}).get(filename, {}).get('sha256', '')})
    reference = declarations[0]
    assert all(r['source_hashes'] == reference['source_hashes'] for r in declarations)
    assert all(r['config_hash'] == reference['config_hash'] for r in declarations)
    current_source_checks = {}
    for relative, recorded in reference['source_hashes'].items():
        actual = hashlib.sha256((repo / relative).read_bytes()).hexdigest()
        assert actual == recorded, relative
        current_source_checks[relative] = actual
    assert len(tables) == 63 and len(common) == 450 and len(native) == len(declarations) == 9
    assert len({(r['sequence_id'], r['method_id'], r['support']) for r in tables}) == 63
    write_rows(base / 'COMPARISON_TABLE.csv', tables)
    write_rows(base / 'COMMON_SUPPORT_ALL.csv', common)
    write_rows(base / 'NATIVE_RUN_SUMMARY.csv', native)
    write_rows(root / 'NEW_RESULTS.local.csv', local)
    result = {
        'status': 'COMPLETED_WITH_RETAINED_EPOCH_FAILURES_AND_DECLARED_MODEL_LIMITS',
        'data_mode': 'real_raw', 'synthetic_data_used': False, 'semisynthetic_data_used': False,
        'native_method_sequence_calls': len(declarations), 'native_process_exit_failures': 0,
        'native_technical_retries': 0,
        'full_history_method_epoch_records': sum(r['completed_epochs'] for r in declarations),
        'full_history_valid_method_epoch_records': sum(r['valid_epochs'] for r in declarations),
        'full_history_invalid_method_epoch_records': sum(sum(r['failure_counts'].values()) for r in declarations),
        'call_unit': 'one complete method/sequence entry; epoch solver/library calls and pool workers are not independent experiments',
        'evaluator_child_invocations': sum(r['evaluator_child_invocations'] for r in evaluations),
        'reference_read_opens': sum(r['actual_reference_open_count'] for r in evaluations),
        'evaluator_technical_retries': 0, 'reference_used_online': False,
        'new_v3_or_rtklib_control_runs': 0, 'new_bootstrap_or_parameter_search': 0,
        'new_degradation_runs': 0, 'raw_degradation_comparison': 'NO_SAME_LAYER_REGISTERED_RAWX_CASES',
        'primary_plot_generations': 3, 'plot_only_display_revisions': 2, 'adopted_raster_figures': 3,
        'comparison_rows': len(tables), 'common_support_rows': len(common),
        'summary_calculations': 'counts and availability fractions only; original metric strings copied unchanged',
        'no_new_solver_or_reference_access_by_summary': True,
        'scientific_source_hashes_match_all_nine_runs_and_current_files': current_source_checks,
        'config_hash_all_nine_runs': reference['config_hash'], 'native_launches': launches,
        'tests': 'Synthetic/unit/native-library tests and their retries are separately recorded in the four method/runner receipts and EVALUATION_PROTOCOL.md; not counted as these real calls',
    }
    (base / 'FINAL_EXECUTION_RECEIPT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('native_method_sequence_calls', 'full_history_method_epoch_records',
                     'full_history_valid_method_epoch_records', 'full_history_invalid_method_epoch_records',
                     'evaluator_child_invocations', 'reference_read_opens', 'comparison_rows')}))


if __name__ == '__main__':
    main()
