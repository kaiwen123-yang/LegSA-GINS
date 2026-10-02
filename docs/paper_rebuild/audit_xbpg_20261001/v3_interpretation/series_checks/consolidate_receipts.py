#!/usr/bin/env python3
"""Consolidate scanner receipts only; never reopen a retained scientific payload."""
import collections
import csv
import json
from pathlib import Path


def rows(path):
    with path.open(newline='', encoding='utf-8') as f:
        yield from csv.DictReader(f)


def write(path, data):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, list(data[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'SCAN_MANIFEST.json').read_text())
    entries = {r['file_id']: r for r in manifest['entries']}
    assert len(entries) == 2309
    files, groups, totals = [], [], collections.Counter()
    unsupported = collections.defaultdict(lambda: {'count': 0, 'files': set()})
    for group in manifest['group_order']:
        directory = root / group
        receipt = json.loads((directory / 'RECEIPT.json').read_text())
        assert receipt['preparation_commit'] == '0593770b2b3837012d155254cfc73448d76990b2'
        assert receipt['script_sha256'] == '655c230b1813cc737efd9f33dd5746c0c7e61768cfd60a12b149c56ee9b7c0cd'
        assert receipt['scan_manifest_sha256'] == '51dda2a4390f97af6e9a5fcfc11f9f019c81a79bd94b1c79bf25e19a148a482c'
        current = list(rows(directory / 'FILE_CHECKS.csv'))
        assert len(current) == receipt['expected_files']
        per_file = collections.defaultdict(collections.Counter)
        for row in rows(directory / 'METRIC_CHECKS.csv'):
            per_file[row['file_id']][row['status']] += 1
            totals[row['status']] += 1
            if row['status'] == 'NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS':
                key = row['payload_kind'], row['metric'], row['reason']
                unsupported[key]['count'] += 1
                unsupported[key]['files'].add(row['file_id'])
        for row in current:
            expected = entries[row['file_id']]
            assert row['source_path'] == expected['source_path']
            counts = per_file[row['file_id']]
            assert dict(counts) == json.loads(row['metric_status_counts'])
            row['metric_checks_csv'] = f'series_checks/{group}/METRIC_CHECKS.csv'
            row['window_checks_csv'] = f'series_checks/{group}/WINDOW_SUMMARY.csv'
            row['field_quality_csv'] = f'series_checks/{group}/FIELD_QUALITY.csv'
            row['group_receipt'] = f'series_checks/{group}/RECEIPT.json'
            row['matched_numeric_cells'] = counts['MATCH']
            row['matched_null_cells'] = counts['MATCH_NULL']
            row['unsupported_cells'] = counts['NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS']
            row['difference_cells'] = counts['DIFFERENCE']
            row['evidence_depth'] = ('NUMERICALLY_CHECKED_WITHIN_SCOPE'
                if row['read_depth'] == 'FULL_PAYLOAD_READ' and counts['MATCH'] > 0 else row['read_depth'])
            row['original_metric_reproduction_scope'] = 'RETAINED_FIELDS_AND_MATCHED_SUPPORT_ONLY'
            row['native_reproduction_performed'] = False
            files.append(row)
        counts = collections.Counter()
        for counter in per_file.values():
            counts.update(counter)
        assert dict(counts) == receipt['metric_check_status_counts']
        groups.append(dict(group=group, files=len(current),
            error_series=sum(r['payload_kind'] == 'error_series' for r in current),
            matched_trajectory=sum(r['payload_kind'] != 'error_series' for r in current),
            completed_files=receipt['completed_files'], incomplete_files=receipt['unreadable_or_incomplete_files'],
            rows=receipt['uncompressed_row_count_fully_read'], main_reads=receipt['new_full_stream_reads'],
            counts=json.dumps(dict(counts), sort_keys=True),
            receipt=f'series_checks/{group}/RECEIPT.json'))
    assert len(files) == len(entries) == len({r['file_id'] for r in files})
    assert {r['file_id'] for r in files} == set(entries)
    errors = [r for r in files if r['payload_kind'] == 'error_series']
    matched = [r for r in files if r['payload_kind'] != 'error_series']
    assert len(errors) == 2308 and len(matched) == 1
    native = {(r['run_id'], r['sequence_id'], r['case_id'], r['method_id']) for r in errors}
    assert len(native) == 1154
    write(root.parent / 'RETAINED_SERIES_CHECKS.csv', files)
    write(root / 'GROUP_READ_SUMMARY.csv', groups)
    limitations = [dict(payload_kind=key[0], metric=key[1],
                         reason=('Not calculated under the frozen scan scope; matched export lacks error/projection or roll/pitch fields; this is not a user prohibition on independent arithmetic'
                                 if key[0] == 'matched_trajectory' else key[2]),
                         original_scanner_reason_literal=key[2],
                         check_rows=value['count'], files=len(value['files']))
                   for key, value in sorted(unsupported.items())]
    write(root / 'UNSUPPORTED_METRICS.csv', limitations)
    summary = dict(expected_error_series=2308, full_read_error_series=sum(r['read_depth'] == 'FULL_PAYLOAD_READ' for r in errors),
        error_series_with_numeric_check=sum(r['matched_numeric_cells'] > 0 for r in errors),
        retained_completed_native=len(native), evaluator_counts=dict(collections.Counter(r['evaluator_version'] for r in errors)),
        matched_trajectory_files=len(matched), matched_trajectory_full_read=sum(r['read_depth'] == 'FULL_PAYLOAD_READ' for r in matched),
        rows_all=sum(int(r['row_count'] or 0) for r in files), rows_error_series=sum(int(r['row_count'] or 0) for r in errors),
        compressed_bytes=sum(int(r['compressed_size_bytes'] or 0) for r in files),
        metric_check_status_counts=dict(totals),
        eof_receipts=dict(collections.Counter(r['eof_receipt'] for r in files)),
        full_read_counts=dict(collections.Counter(r['read_depth'] for r in files)),
        main_scan_count_distribution=dict(collections.Counter(r['main_scan_count'] for r in files)),
        sha256_status_counts=dict(collections.Counter(r['sha256_status'] for r in files)),
        nonfinite_cells=sum(int(r['nonfinite_cell_count'] or 0) for r in files),
        duplicate_timestamps=sum(int(r['duplicate_timestamp_count'] or 0) for r in files),
        backward_timestamps=sum(int(r['backward_timestamp_count'] or 0) for r in files),
        data_mode='validation_of_existing_real_and_semisynthetic_results',
        synthetic_data_used=False, semisynthetic_data_used=True, semisynthetic_data_generated=False,
        validation_calculation=True, payload_opens_by_consolidator=0,
        solver_calls=0, provider_generator_calls=0, original_evaluator_calls=0, controller_calls=0,
        bootstrap_calls=0, raw_reference_opens=0, nav_std_payload_opens=0, source_series_writes=0,
        scope_limit='Each file partially numerically reproducible; not native/input replay or scientific correctness certification',
        known_window_omissions='D22_seed_00 and D39_seed_00; see WINDOW_LIMITATIONS.csv; no second payload pass',
        retention_baseline='Prior collection: 10062 released error-series, 566 not generated, 6378 NAV and 6378 STD released; not re-inventoried here')
    (root / 'FULL_READ_SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
