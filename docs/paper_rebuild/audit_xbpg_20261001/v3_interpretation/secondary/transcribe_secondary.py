#!/usr/bin/env python3
"""Read explicitly referenced historical/auxiliary CSVs, without executing them.

Only selected string cells and table read receipts are written in this directory.
Large series, reference and runtime payloads are never opened.
"""
import argparse
import collections
import csv
import json
import re
from pathlib import Path


def write(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--group', choices=['legacy', 'sensitivity', 'external'], required=True)
    a = p.parse_args()
    code = a.code_root.resolve()
    out = Path(__file__).resolve().parent
    aliases = json.loads((code / 'configs/paper_rebuild/V3_RESULTS_ROOTS.local.json').read_text())['aliases']
    index = json.loads((code / 'configs/paper_rebuild/v3/V3_REPORT_SOURCE_INDEX.json').read_text())
    sources = []
    def collect(obj):
        if isinstance(obj, dict):
            if 'path' in obj and obj['path'].endswith('.csv'):
                sources.append(obj['path'])
            else:
                for value in obj.values():
                    collect(value)
    if a.group in ['legacy', 'sensitivity']:
        keys = (['frozen_core', 'frozen_addendum', 'frozen_sequences', 'horizontal_tables', 'frozen_by2o_segments']
                if a.group == 'legacy' else ['sensitivity_pilot', 'sensitivity_subset', 'sensitivity_summary'])
        for key in keys:
            collect(index[key])
        if a.group == 'legacy':
            for stem in ['CORE_541', 'SUBSET61', 'ADDENDUM', 'SEQUENCE']:
                sources += [f'<V3_ROOT>/07_AGGREGATE/{stem}_V21_COMPARISON_{v}.csv' for v in ['V3', 'V2']]
            sources.append('<V3_ROOT>/07_AGGREGATE/FAILURE_COMPARISON.csv')
        else:
            for stem in ['T5BCR_REFERENCE_THREE_SEQUENCES', 'T5BCR_REFERENCE_SUBSET61']:
                sources += [f'<V3_ROOT>/07_AGGREGATE/{stem}_{v}.csv' for v in ['V3', 'V2']]
            sources.append('<V3_ROOT>/07_AGGREGATE/T5BCR_REFERENCE_SUBSET61_TAIL_SUMMARY.csv')
    else:
        sources = ['<V3_ROOT>/07_AGGREGATE/MAIN_TABLE_V3.csv',
            '<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv',
            '<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02E_HARTLEY_OFFICIAL/90_AGGREGATE/HARTLEY_OFFICIAL_TABLE.csv',
            '<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/90_AGGREGATE/DEGRADATION_EXTERNAL_TABLE_R2.csv',
            '<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/90_AGGREGATE/DEGRADATION_EXTERNAL_SUMMARY_R2.csv']
        sources += ['<CODE_ROOT>/docs/paper_rebuild/hext/HX05/' + n for n in [
            'EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv', 'EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv',
            'DEGRADATION_MANUSCRIPT.csv', 'BY2O_SEGMENT_TABLE_EXT.csv', 'D43_VELOCITY_NOISE_SUPPLEMENT.csv']]
    reads, cells = [], []
    for source in dict.fromkeys(sources):
        matches = [Path(root + source[len(alias):]) for alias, root in aliases.items()
                   if source.startswith(alias + '/')]
        assert len(matches) == 1, source
        path = matches[0]
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)
        status_fields = [k for k in fields if k in ['status', 'evaluation_status', 'failure_class',
                         'failure_classification', 'v3_status', 'v21_status', 'audit_status_R2']]
        counts = {k: dict(collections.Counter(row[k] for row in rows)) for k in status_fields}
        reads.append(dict(source_path=source, source_selection='V3_REPORT_SOURCE_INDEX or prior confirmed presentation chain',
            read_depth='FULL_TABLE_READ', row_count=len(rows), columns=json.dumps(fields, ensure_ascii=False),
            status_column_counts=json.dumps(counts, ensure_ascii=False, sort_keys=True),
            new_hash_calculation=False, scientific_execution_calls=0))
        for i, row in enumerate(rows, 1):
            name = path.name
            if a.group == 'legacy':
                selected = name.startswith('SEQUENCE_V21_COMPARISON') and row.get('method_id') == 'F04'
                selected |= name == 'FAILURE_COMPARISON.csv'
            elif a.group == 'sensitivity':
                selected = 'REFERENCE_THREE_SEQUENCES' in name or 'TAIL_SUMMARY' in name
                selected |= 'REFERENCE_SUBSET61_V3' in name and (row.get('status') or row.get('evaluation_status')) != 'COMPLETED'
            else:
                selected = name in ['EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv', 'EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv',
                    'DEGRADATION_MANUSCRIPT.csv', 'DEGRADATION_EXTERNAL_SUMMARY_R2.csv']
                selected |= name == 'MAIN_TABLE_V3.csv' and row.get('method_id') not in ['F01', 'F02', 'F03', 'F04', 'A04']
            if not selected:
                continue
            identity = {k: v for k, v in row.items() if k in ['sequence', 'sequence_id', 'dataset_id',
                'method', 'method_id', 'metric', 'metric_name', 'case_id', 'variant', 'config', 'type',
                'seed', 'family', 'domain', 'evaluator_version', 'protocol', 'start_mode', 'start_convention']}
            for column, value in row.items():
                if 'REFERENCE_SUBSET61_V3' in name and column not in {
                    'run_id', 'case_id', 'case_family', 'method_id', 'variant', 'configuration_id',
                    'evaluation_status', 'status', 'failure_classification', 'solver_terminal_status',
                    'technical_failure', 'algorithm_failure', 'output_epoch_count', 'matched_epoch_count',
                    'horizontal_rmse_m', 'h_rmse_m', 'position_3d_rmse_m', 'up_rmse_m', 'yaw_rmse_deg',
                    'yaw_p95_absolute_deg', 'roll_rmse_deg', 'pitch_rmse_deg', 'data_mode',
                    'synthetic_data_used', 'semisynthetic_data_used', 'code_commit', 'evaluator_contract'}:
                    continue
                # The full original remains at source. Do not publish machine-specific metadata.
                if re.search(r'/home/|/mnt/|[A-Za-z]:[\\/]', value):
                    continue
                cells.append(dict(source_path=source, source_row_key=f'data_row_1based:{i}',
                    identity=json.dumps(identity, ensure_ascii=False, sort_keys=True), column=column,
                    source_value=value, operation='UNCHANGED_STRING_TRANSCRIPTION_SELECTED_CELLS'))
    tag = a.group.upper()
    write(out / f'{tag}_INPUTS_READ.csv', reads)
    write(out / f'{tag}_SOURCE_CELLS.csv', cells)
    print(json.dumps(dict(group=a.group, files_read=len(reads), rows_read=sum(r['row_count'] for r in reads),
                          selected_cells=len(cells), scientific_calls=0)))


if __name__ == '__main__':
    main()
