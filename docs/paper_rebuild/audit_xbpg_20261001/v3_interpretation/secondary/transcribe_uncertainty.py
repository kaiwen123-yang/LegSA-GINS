#!/usr/bin/env python3
"""Read existing small uncertainty tables and preserve selected source cells.

No scientific calculation, sampling, payload reads or project module imports.
"""
import argparse
import csv
import json
from pathlib import Path


def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    args = parser.parse_args()
    code = args.code_root.resolve()
    out = Path(__file__).resolve().parent
    uncertainty = code / 'docs/paper_rebuild/v3/uncertainty'
    roots = json.loads((code / 'configs/paper_rebuild/V3_RESULTS_ROOTS.local.json').read_text())['aliases']
    reads, cells = [], []
    files = [(p, '<CODE_ROOT>/docs/paper_rebuild/v3/uncertainty/' + p.name)
             for p in sorted(uncertainty.glob('*.csv'))]
    files += [(Path(roots['<V3_ROOT>']) / '07_AGGREGATE' / name,
               '<V3_ROOT>/07_AGGREGATE/' + name)
              for name in ['PAIRWISE_SUMMARY_V3.csv', 'PAIRWISE_SUMMARY_V2.csv']]
    selected_names = {'UA01_PAIRED_OVERALL.csv', 'UNC_FAST_COMPONENT_RANGE.csv'}
    for path, source in files:
        with path.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)
        reads.append(dict(source_path=source, read_depth='FULL_TABLE_READ', rows=len(rows),
                          columns=json.dumps(fields, ensure_ascii=False), hashes='NOT_NEWLY_VERIFIED'))
        for i, row in enumerate(rows, 1):
            select = path.name in selected_names
            select |= path.name == 'UA01_DISTRIBUTION_QUANTILES.csv' and row['method'] in ['F04', 'F03', 'A04', 'F01']
            select |= path.name in ['UA01_C00_PAIRED_SERIES.csv', 'UNC_DISTINGUISHABILITY.csv'] and (
                row.get('pair', row.get('pair_A_minus_B')) in ['LC01-F04', 'LC01-S-F04', 'F04-F02'])
            select |= path.name in ['UA01_C00_SERIES_STATS.csv', 'UNC_YAW_DECOMPOSITION.csv'] and row['method'] == 'F04'
            # Preserve complete overall rows; column names differ between the two table systems.
            select |= path.name.startswith('PAIRWISE_SUMMARY') and any(v == 'overall' for v in row.values())
            if not select:
                continue
            identity = {k: v for k, v in row.items() if k in ['sequence', 'method', 'metric', 'metric_name', 'pair',
                'pair_A_minus_B', 'segment', 'series', 'comparison', 'scope', 'family']}
            for column, value in row.items():
                cells.append(dict(source_path=source, source_row_key=f'data_row_1based:{i}',
                    identity=json.dumps(identity, ensure_ascii=False, sort_keys=True),
                    column=column, source_value=value, operation='UNCHANGED_STRING_TRANSCRIPTION'))
    write(out / 'UNCERTAINTY_INPUTS_READ.csv', reads)
    write(out / 'UNCERTAINTY_SOURCE_CELLS.csv', cells)
    print(json.dumps(dict(files_read=len(reads), rows_read=sum(r['rows'] for r in reads),
                          cells_transcribed=len(cells), new_bootstrap_calls=0)))


if __name__ == '__main__':
    main()
