#!/usr/bin/env python3
"""Describe symmetry of already selected complete covariance snapshots only.

No new thresholds, eigendecomposition, active-block reduction or filter writes.
Does not reopen event payloads or generate scientific runtime outputs.
"""
import argparse
import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_covariances(value, path=''):
    if isinstance(value, dict):
        for key, item in value.items():
            field = path + '/' + key
            if key in ('P_before', 'P_after') and isinstance(item, dict):
                assert item['rows'] == item['cols'] == 21 and len(item['data']) == 441
                yield field, item['data']
            else:
                yield from find_covariances(item, field)


def describe(values):
    finite = sum(math.isfinite(x) for x in values)
    diagonal = [values[21 * i + i] for i in range(21)]
    differences = [(abs(values[21 * i + j] - values[21 * j + i]), i, j)
                   for i in range(21) for j in range(i)]
    asymmetry, row, col = max(differences) if finite == 441 else ('UNKNOWN', 'UNKNOWN', 'UNKNOWN')
    scale_rows = [all(values[21 * i + j] == 0 for j in range(21)) for i in range(15, 21)]
    scale_cols = [all(values[21 * j + i] == 0 for j in range(21)) for i in range(15, 21)]
    return dict(finite_entries=finite, total_entries=441, min_diagonal=min(diagonal),
                nonpositive_diagonal_indices=json.dumps([i for i, x in enumerate(diagonal) if x <= 0]),
                max_absolute_asymmetry=asymmetry, max_row=row, max_col=col,
                scale_rows_all_zero=json.dumps(scale_rows), scale_cols_all_zero=json.dumps(scale_cols),
                symmetry_pass='NOT_CLASSIFIED_NO_NEW_TOLERANCE', positive_definite_pass='NOT_TESTED',
                units='entry-specific covariance units; max is a description with indices, not a common physical norm')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--roots', type=Path, required=True)
    args = parser.parse_args()
    aliases = json.loads(args.roots.read_text())['aliases']
    root = Path(aliases['<VALIDATION_ROOT>']) / 'analysis/event_cache'
    queue = list(csv.DictReader((HERE / 'CANDIDATE_QUEUE.csv').open()))
    pairs = sorted({('BASELINE', r['baseline_run_id']) for r in queue} |
                   {(r['candidate_id'], r['baseline_run_id']) for r in queue})
    assert len(pairs) == 17
    rows = []
    files = []
    for variant, run in pairs:
        directory = root / (variant + '__' + run)
        receipt = json.loads((directory / 'SCAN_RECEIPT.json').read_text())
        assert receipt['stream_status'] == 'COMPLETE' and receipt['analysis_status'] == 'VALIDATED'
        observed_run = run if variant == 'BASELINE' else variant + '__' + run
        assert receipt['run_id'] == observed_run and receipt['candidate_id'] == variant
        seen = set()
        record_count = 0
        with (directory / 'KEY_SNAPSHOTS.jsonl').open() as f:
            for line_no, line in enumerate(f, 1):
                record_count += 1
                record = json.loads(line)
                pointer = record['pointer']
                for field, values in find_covariances(record['original_event']):
                    key = pointer['event_seq'], field
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(dict(candidate_id=variant, run_id=run, category=record['category'],
                        data_mode=receipt['data_mode'], synthetic_data_used=receipt['synthetic_data_used'],
                        semisynthetic_data_used=receipt['semisynthetic_data_used'],
                        snapshot_source='<VALIDATION_ROOT>/analysis/event_cache/' + directory.name + '/KEY_SNAPSHOTS.jsonl',
                        snapshot_line=line_no, observed_run_id=pointer['run_id'],
                        original_source=pointer['source_path'], original_event_seq=pointer['event_seq'],
                        original_event=pointer['event'], original_byte_offset=pointer['byte_offset'],
                        field=field, **describe(values)))
        files.append(dict(candidate_id=variant, run_id=run, key_snapshot_records_read=record_count,
                          unique_complete_P_snapshots=len(seen), event_payload_opens=0))
    out = HERE / 'covariance_supplement'
    out.mkdir(exist_ok=False)
    for name, records in [('KEY_P_SYMMETRY.csv', rows), ('READ_SCOPE.csv', files)]:
        with (out / name).open('w', newline='') as f:
            writer = csv.DictWriter(f, records[0].keys(), lineterminator='\n')
            writer.writeheader()
            writer.writerows(records)
    summary = dict(scope='cached prespecified first-source/first-anomaly snapshots only',
                   data_mode='mixed_index_real_clean_and_semisynthetic',
                   synthetic_data_used=False, semisynthetic_data_used=True,
                   cache_files=len(files), unique_complete_P_snapshots=len(rows),
                   all_441_finite=sum(r['finite_entries'] == 441 for r in rows),
                   max_absolute_asymmetry=max(r['max_absolute_asymmetry'] for r in rows if isinstance(r['max_absolute_asymmetry'], (int, float))),
                   native_calls=0, evaluator_calls=0, event_payload_opens=0, new_validation_calculation=True,
                   symmetry_tolerance_added=False, full_time_series_symmetry_verified=False,
                   full_P_positive_semidefinite_verified=False, original_diagnostic_changed=False)
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
