#!/usr/bin/env python3
"""Aggregate and render the frozen H03 continuation without running estimators."""
import argparse
import json
import os
from pathlib import Path
import shutil

os.environ['GIT_OPTIONAL_LOCKS'] = '0'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'

from legsa_gins.paper_rebuild.hext import continuation, execution
from legsa_gins.paper_rebuild.hext.aggregate import aggregate_stage
from legsa_gins.paper_rebuild.hext.figures import render_fig02s
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths
from legsa_gins.paper_rebuild.manifest import sha256_file


def aggregate():
    seq, scratch, archive = continuation.stage_roots()
    freeze = continuation.assert_freeze()
    continuation._verify_preserved(seq, scratch, archive)
    sources_root = scratch / '09_LEGSA_GAP_DIAGNOSTIC/H_EXT_03'
    sources = json.loads((sources_root / 'SOURCE_RESOLUTION.json').read_text())
    records = json.loads((scratch / 'EXECUTION_RECORDS.json').read_text())
    budget = json.loads((scratch / '03_CONTINUATION/EXECUTION/BUDGET_LEDGER.json').read_text())
    out = scratch / '08_AGGREGATE'
    summary = aggregate_stage(sequences={s: load_sequence_paths(s) for s in ('BY2', 'BY2H', 'BY2O')},
        records=records, output_root=out, code_commit=freeze['code_freeze'], budget_ledger=budget,
        continuation_v11=True, frozen_error_sources=sources['frozen_error_sources'])
    for origin in (scratch / '03_CONTINUATION/PREREG/BOUNDED_OUTPUT_GATE.csv',
                   scratch / '03_CONTINUATION/PREREG/D8_RETROSPECTIVE.json',
                   sources_root / 'SOURCE_RESOLUTION.json',
                   sources_root / 'LEGSA_GAP_DIAGNOSTIC.csv', sources_root / 'LEGSA_GAP_DIAGNOSTIC.json'):
        with origin.open('rb') as source, (out / origin.name).open('xb') as target:
            shutil.copyfileobj(source, target)
        if sha256_file(origin) != sha256_file(out / origin.name):
            raise RuntimeError('Diagnostic-copy hash mismatch')
    summary.update(source_resolution_sha256=sha256_file(sources_root / 'SOURCE_RESOLUTION.json'),
                   native_outputs_modified=False, historical_failed_evaluation_modified=False,
                   original_hard_stop_package_sha256=continuation.V1_ZIP_SHA256,
                   readonly_frozen_exact_window_segments=True,
                   trace_open_count_new=budget['evaluator_actual'],
                   retrospective_D8=json.loads((out / 'D8_RETROSPECTIVE.json').read_text()))
    summary['files_sha256'] = {p.name: sha256_file(p) for p in sorted(out.iterdir())
                               if p.is_file() and p.name != 'FINAL_SUMMARY.json'}
    # This newly generated, unarchived summary is sealed only after the whole bundle is assembled.
    (out / 'FINAL_SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2,
                                                    allow_nan=False) + '\n')
    execution.archive_batch(out, archive / '08_AGGREGATE', scratch / 'ARCHIVE_LEDGER.jsonl', 'H03_AGGREGATE')
    execution.archive_batch(sources_root, archive / '09_LEGSA_GAP_DIAGNOSTIC/H_EXT_03',
                            scratch / 'ARCHIVE_LEDGER.jsonl', 'H03_READONLY_SOURCES')
    return summary


def figures():
    seq, scratch, archive = continuation.stage_roots()
    freeze = continuation.assert_freeze()
    result = render_fig02s(main_table=archive / '08_AGGREGATE/HORIZONTAL_TABLE_V3_THREE_SEQUENCES.csv',
        summary_path=archive / '08_AGGREGATE/FINAL_SUMMARY.json', runtime_root=scratch,
        publication_root=seq.clean_root / 'stages/CLEAN6_PUBLICATION_FIGURES',
        code_commit=freeze['code_freeze'],
        frozen_before=json.loads((scratch / '03_CONTINUATION/PREREG/FROZEN_FIGURES_PRE.json').read_text()))
    execution.archive_batch(scratch / '10_FIGURES', archive / '10_FIGURES',
                            scratch / 'ARCHIVE_LEDGER.jsonl', 'H03_FIGURES')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('aggregate', 'figures'))
    action = parser.parse_args().action
    result = {'aggregate': aggregate, 'figures': figures}[action]()
    print(json.dumps({k: v for k, v in result.items() if k in
        ('status', 'row_counts', 'budget_ledger', 'failure_classification_counts', 'original_v21_files_byte_unchanged')},
        ensure_ascii=False, indent=2))
