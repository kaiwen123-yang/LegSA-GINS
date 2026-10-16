"""Offline gate first; saved-error evaluation only after the mask is sealed.

Commands:
  python3 run_acceptance.py mask --registered-commit <sha>
  python3 run_acceptance.py evaluate
No native navigation, carrier solver, provider, or reference-reader is imported.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_EVEN

from acceptance import decide

OUT = Path(__file__).parent
RUNS = Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/EXT_REPRODUCTION_V2_TECH_RETRY_2_20261004T054256Z/runs')
CODE = Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
EVAL = CODE / 'docs/paper_rebuild/hext/EXT_REPRODUCTION/v2_fix/evaluation_results'
OLD_PLOT_DATA = Path('/mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011/heading/data')
EXPECTED = {'BY2': (1509, 1370), 'BY2H': (1483, 1350), 'BY2O': (2231, 1885)}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save_json(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def key_us(value):
    return int((Decimal(str(value)) * 1000000).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))


def mask(commit):
    assert commit and len(commit) >= 7, 'pre-registration commit required'
    assert not (OUT/'ACCEPTANCE_SEAL.json').exists(), 'do not overwrite a sealed acceptance result'
    plan = json.loads((OUT/'PLAN_LOCK.json').read_text())
    rows, receipts = [], []
    for seq, (nexpected, _) in EXPECTED.items():
        for method in ('EXT01', 'EXT02'):
            run = RUNS / f'{seq}__{method}__RAW_REPRO_V2__TECH_RETRY_2'
            metadata = json.loads((run/'RUN.json').read_text())
            assert metadata['status'] == 'COMPLETED'
            assert metadata['completed_epochs'] == nexpected
            evidence = run/'EPOCH_EVIDENCE.jsonl.gz'
            expected_hash = metadata['outputs'][evidence.name]['sha256']
            assert sha(evidence) == expected_hash
            group = []
            with gzip.open(evidence, 'rt') as f:
                for line in f:
                    record = json.loads(line)
                    d = decide(record, plan['ratio_threshold'])
                    row = dict(sequence=seq, method_id=method, run_id=metadata['run_id'],
                               epoch_index=record['epoch_index'], time_unix_s=record['time_unix_s'],
                               time_key_us=key_us(record['time_unix_s']),
                               native_valid=bool(record['valid']), native_yaw_deg=record.get('body_yaw_deg'),
                               native_solution_state=record.get('solution_state'),
                               native_failure_code=record.get('failure_code'), **d.row())
                    group.append(row)
            assert len(group) == nexpected
            assert [r['epoch_index'] for r in group] == list(range(nexpected))
            assert len({r['time_key_us'] for r in group}) == nexpected
            assert all(not r['accepted'] or r['native_valid'] for r in group)
            assert sum(r['native_valid'] for r in group) == metadata['valid_epochs']
            rows += group
            receipts.append(dict(sequence=seq, method_id=method, source=str(evidence),
                                 source_sha256=expected_hash, source_run_sha256=sha(run/'RUN.json'),
                                 original_epochs=len(group), native_valid=sum(r['native_valid'] for r in group),
                                 accepted=sum(r['accepted'] for r in group),
                                 decision_states=dict(Counter(r['acceptance_state'] for r in group))))
    assert len(rows) == 10446
    path = OUT/'ACCEPTANCE_FULL_HISTORY.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    seal = dict(schema='heading.acceptance.mask_seal.v1', utc=datetime.now(timezone.utc).isoformat(),
                registered_commit=commit, plan_sha256=sha(OUT/'PLAN_LOCK.json'),
                gate_source_sha256=sha(OUT/'acceptance.py'), runner_source_sha256=sha(Path(__file__)),
                acceptance_csv_sha256=sha(path), reference_or_error_series_opened=False,
                raw_solver_calls=0, v3_calls=0, epochs=10446, runs=receipts)
    save_json(OUT/'ACCEPTANCE_SEAL.json', seal)
    print(json.dumps({'mask_sealed': True, 'epochs': len(rows), 'runs': receipts}, ensure_ascii=False))


def evaluate():
    import numpy as np
    import pandas as pd
    seal = json.loads((OUT/'ACCEPTANCE_SEAL.json').read_text())
    assert sha(OUT/'ACCEPTANCE_FULL_HISTORY.csv') == seal['acceptance_csv_sha256']
    assert sha(OUT/'PLAN_LOCK.json') == seal['plan_sha256']
    masks = pd.read_csv(OUT/'ACCEPTANCE_FULL_HISTORY.csv')
    all_errors, summaries, pair_rows, source_rows = [], [], [], []

    def metrics(errors):
        errors = np.asarray(errors, dtype=float)
        errors = errors[np.isfinite(errors)]
        return dict(scored=len(errors), rmse_deg=float(np.sqrt(np.mean(errors**2))) if len(errors) else None,
                    mae_deg=float(np.mean(np.abs(errors))) if len(errors) else None,
                    p95_abs_deg=float(np.percentile(np.abs(errors), 95)) if len(errors) else None,
                    max_abs_deg=float(np.max(np.abs(errors))) if len(errors) else None)

    for seq, (_, full_window) in EXPECTED.items():
        error_path = EVAL / seq / 'ERROR_SERIES.csv'
        old = pd.read_csv(error_path)
        source_rows.append(dict(sequence=seq, source=str(error_path), sha256=sha(error_path)))
        series = {}
        for method in ('EXT01', 'EXT02'):
            data = old[old.method_id.eq(method)].copy()
            assert len(data) == full_window and not data.epoch_index.duplicated().any()
            mask_rows = masks[masks.sequence.eq(seq) & masks.method_id.eq(method)]
            joined = data.merge(mask_rows.drop(columns=['method_id']), on='epoch_index',
                                how='left', validate='one_to_one', suffixes=('', '_mask'))
            assert joined.accepted.notna().all()
            assert np.max(np.abs(joined.time_unix_s - joined.time_unix_s_mask)) <= 1e-6
            assert np.array_equal(joined.valid.eq(1).to_numpy(), joined.native_valid.to_numpy())
            assert np.array_equal(joined.time_key_us.to_numpy(), joined.time_key_us_mask.to_numpy())
            joined['error_accepted_deg'] = joined.error_valid_deg.where(joined.accepted)
            joined['accepted_yaw_deg'] = joined.native_body_yaw_deg.where(joined.accepted)
            joined['screen_label'] = 'project-added ratio screen (>=3)'
            joined['known_correct_integer'] = False
            keep = ['sequence', 'method_id', 'epoch_index', 'time_key_us', 'time_unix_s', 't_rel_s',
                    'native_valid', 'accepted', 'acceptance_state', 'native_failure_code',
                    'best_cost', 'second_cost', 'ratio', 'distinct_hypotheses',
                    'native_body_yaw_deg', 'accepted_yaw_deg', 'reference_supported',
                    'error_valid_deg', 'error_accepted_deg', 'reference_yaw_ned_deg', 'screen_label']
            all_errors.append(joined[keep])
            for support in ('native', 'project_ratio3'):
                active = joined.native_valid if support == 'native' else joined.accepted
                summaries.append(dict(sequence=seq, method_id=method, support=support,
                                      full_window_epochs=full_window, outputs=int(active.sum()),
                                      coverage_percent=100*float(active.sum())/full_window,
                                      **metrics(joined.loc[active, 'error_valid_deg']),
                                      acceptance_rule='none' if support == 'native' else 'second/best >= 3',
                                      original_failure_count=int((~joined.native_valid).sum()),
                                      screen_withheld_count=int((joined.native_valid & ~joined.accepted).sum())))
            series[method+'_screen'] = joined.loc[joined.accepted & joined.reference_supported.eq(1),
                                                  ['time_key_us','error_valid_deg']].dropna()
            series[method+'_native'] = joined.loc[joined.native_valid & joined.reference_supported.eq(1),
                                                  ['time_key_us','error_valid_deg']].dropna()
        ext03 = old[old.method_id.eq('EXT03')]
        series['EXT03_native'] = ext03.loc[ext03.valid.eq(1) & ext03.reference_supported.eq(1),
                                           ['time_key_us','error_valid_deg']].dropna()
        series['EXT03_ratio3'] = ext03.loc[ext03.error_ratio_fixed_deg.notna(),
                                           ['time_key_us','error_ratio_fixed_deg']].rename(columns={'error_ratio_fixed_deg':'error_valid_deg'})
        for variant in ('V0','V0E','V1','V2'):
            p = OLD_PLOT_DATA/f'{seq}_{variant}_full_saved_heading.csv.gz'
            df = pd.read_csv(p)
            if 'time_key_us' not in df:
                # Compact frozen RTKLIB plotting source preserves absolute
                # relative-to-base seconds, not a Unix timestamp column.
                base = 1772780400 if seq == 'BY2O' else 1772784000
                df['time_key_us'] = df.t_rel_s.map(lambda t: base*1000000 + key_us(t))
            series['RTKLIB_'+variant] = df.loc[df.valid.eq(1),['time_key_us','error_valid_deg']].dropna()
            source_rows.append(dict(sequence=seq, source=str(p), sha256=sha(p)))
        pairs = [('EXT01_screen','EXT02_screen')]
        for a in ('EXT01_screen','EXT02_screen'):
            pairs += [(a, b) for b in ('EXT03_native','EXT03_ratio3','RTKLIB_V0','RTKLIB_V0E','RTKLIB_V1','RTKLIB_V2')]
        for a, b in pairs:
            common = series[a].merge(series[b], on='time_key_us', how='inner',
                                     suffixes=('_a','_b'), validate='one_to_one')
            for member, column in ((a,'error_valid_deg_a'),(b,'error_valid_deg_b')):
                pair_rows.append(dict(sequence=seq, comparison=f'{a}__{b}', method=member,
                                      full_window_epochs=full_window, common_epochs=len(common),
                                      **metrics(common[column])))
    out = pd.concat(all_errors, ignore_index=True)
    assert len(out) == 9210
    out.to_csv(OUT/'ACCEPTED_ERROR_SERIES.csv', index=False)
    pd.DataFrame(summaries).to_csv(OUT/'ACCEPTANCE_SUMMARY.csv', index=False)
    pd.DataFrame(pair_rows).to_csv(OUT/'COMMON_SUPPORT_COMPARISON.csv', index=False)
    pd.DataFrame(source_rows).to_csv(OUT/'EVALUATION_SOURCES.csv', index=False)
    counts = out.groupby(['sequence','method_id','acceptance_state'], dropna=False).size().reset_index(name='count')
    counts.to_csv(OUT/'WINDOW_DECISION_COUNTS.csv', index=False)
    save_json(OUT/'EVALUATION_RECEIPT.json', dict(
        schema='heading.acceptance.saved_error_evaluation.v1', utc=datetime.now(timezone.utc).isoformat(),
        acceptance_seal_sha256=sha(OUT/'ACCEPTANCE_SEAL.json'), errors=9210,
        acceptance_mask_unchanged=sha(OUT/'ACCEPTANCE_FULL_HISTORY.csv')==seal['acceptance_csv_sha256'],
        summary_rows=len(summaries), common_support_rows=len(pair_rows), raw_reference_reads=0,
        native_solver_calls=0, old_evaluator_calls=0, source_error_series_reused=True,
        timestamp_matching='native epoch_index + identical microsecond time_key, one-to-one',
        tuning=False, integer_correctness_established=False,
        observation='Projected lateral-baseline heading versus saved commercial fused Euler-yaw reference',
        outputs={p.name:sha(p) for p in [OUT/'ACCEPTED_ERROR_SERIES.csv', OUT/'ACCEPTANCE_SUMMARY.csv', OUT/'COMMON_SUPPORT_COMPARISON.csv']}))
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['mask','evaluate'])
    p.add_argument('--registered-commit')
    args = p.parse_args()
    if args.mode == 'mask':
        mask(args.registered_commit)
    else:
        evaluate()
