#!/usr/bin/env python3
"""One bounded resume after a successful cache's Git-index metadata audit stop.

No scientific implementation is changed or retried. The original failed scope
audit remains intact; GIT_OPTIONAL_LOCKS=0 prevents later Git index refreshes.
"""
import json
import os
from pathlib import Path

os.environ['GIT_OPTIONAL_LOCKS'] = '0'
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'

import yaml
from legsa_gins.paper_rebuild.hext import execution as io
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths
from legsa_gins.paper_rebuild.horizontal_literature.phase5_runner import _load_cache


def main():
    seq, scratch, archive = io.stage_roots()
    freeze = io.assert_freeze()
    before = json.loads((scratch / '04_ACCESS_AUDITS/BY2__CACHE.json').read_text())
    outside = before['write_scope']['outside_run_write_open_records']
    if (before['exit_code'] != 0 or before['trace_bag_fpl_open_count'] != 0 or len(outside) != 1
            or not outside[0]['path'].endswith('/.git/worktrees/clean3-math-repair/index.lock')
            or before['write_scope']['raw_write_open_count'] != 0
            or before['write_scope']['clean_root_outside_run_write_count'] != 0):
        raise RuntimeError('Resume is limited to the recorded Git index metadata refresh')
    if (scratch / 'EXECUTION_JOURNAL.jsonl').exists():
        raise RuntimeError('This resume admits zero previously launched comparison natives')
    _arrays, cache_manifest = _load_cache(scratch / '03_PROVIDER_CACHE/BY2')
    if cache_manifest['code_commit'] != freeze['code_freeze']:
        raise RuntimeError('Cache code freeze mismatch')
    io.write_json(scratch / 'BOOKKEEPING_CACHE_ADJUDICATION.json', dict(
        status='ACCEPTED_GIT_INDEX_METADATA_REFRESH_ONLY', authorization='H-EXT-02 section 5 bookkeeping self-adjudication',
        original_audit_passed=False, original_receipt_retained=True, provider_exit=0,
        native_calls_before_resume=0, evaluator_calls_before_resume=0, scientific_code_changed=False,
        cache_regenerated=False, environment_addition={'GIT_OPTIONAL_LOCKS':'0'}, outside_record=outside[0]))
    contract = yaml.safe_load((seq.code_root / io.CONTRACT).read_text())
    records, ledger = [], scratch / 'ARCHIVE_LEDGER.jsonl'
    for name in ('BY2', 'BY2H', 'BY2O'):
        current = load_sequence_paths(name)
        cache_relative = io.ATTEMPT + '/03_PROVIDER_CACHE/' + name
        if name != 'BY2':
            io.raw_checkpoint(current, scratch / 'RAW_CHECKPOINTS' / (name + '_PRE_NATIVE.json'))
            io._native_command(current, scratch, name + '__CACHE', ['--mode', 'prepare-cache', '--cache-relative', cache_relative])
        cache = json.loads((seq.hext_scratch / cache_relative / 'CACHE_MANIFEST.json').read_text())
        primary = 'FILE_START' if cache['first_five_seconds_static_audit']['passed'] else 'CONTRACT_START'
        scheduled = [r for r in contract['run_matrix'] if r['sequence_id'] == name]
        if primary == 'CONTRACT_START':
            scheduled = [dict(r, start_mode='CONTRACT_START', run_id=f"{name}__{r['configuration_id']}__CONTRACT_START") for r in scheduled]
            scheduled = list({r['run_id']: r for r in scheduled}.values())
        for spec in scheduled:
            io.assert_freeze()
            run_id, config, start = spec['run_id'], spec['configuration_id'], spec['start_mode']
            relative = Path('04_NATIVE_RUNS') / name / config / start
            io._journal(scratch, dict(event='NATIVE_LAUNCH', run_id=run_id, code_commit=freeze['code_freeze']))
            io._native_command(current, scratch, run_id, ['--mode', 'run', '--cache-relative', cache_relative,
                               '--output-relative', (Path(io.ATTEMPT) / relative).as_posix(), '--configuration', config, '--start-mode', start])
            summary = json.loads((scratch / relative / 'NATIVE_SUMMARY.json').read_text())
            io.write_json(scratch / '05_GEOMETRIC_AUDIT' / (run_id + '.json'), dict(run_id=run_id, **summary['geometric_audit']))
            record = {**spec, 'primary_start_mode': primary, 'native_root': str(archive / relative),
                      'native_summary_path': str(archive / relative / 'NATIVE_SUMMARY.json'),
                      'gap_log_path': str(archive / relative / 'GAP_EVENTS.json'), 'evaluations': {}}
            io.archive_batch(scratch / relative, archive / relative, ledger, run_id)
            records.append(record)
            io._journal(scratch, dict(event='NATIVE_COMPLETED_ARCHIVED', run_id=run_id))
            print('NATIVE_COMPLETED', run_id, flush=True)
        io.raw_checkpoint(current, scratch / 'RAW_CHECKPOINTS' / (name + '_POST_NATIVE.json'))
    if len(records) > contract['budget']['native']:
        raise RuntimeError('Native budget overrun')
    io.write_json(scratch / 'NATIVE_EXECUTION_RECORDS.json', records)
    for name in ('03_PROVIDER_CACHE', '04_ACCESS_AUDITS', '05_GEOMETRIC_AUDIT', 'RAW_CHECKPOINTS'):
        io.archive_batch(scratch / name, archive / name, ledger, name)
    print(json.dumps(dict(status='NATIVE_MATRIX_COMPLETED', count=len(records))))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        _, scratch, _ = io.stage_roots()
        io.write_json(scratch / 'HARD_STOP_NATIVE_RESUME.json', dict(status='HARD_STOP', error_type=type(exc).__name__, error=str(exc)))
        raise
