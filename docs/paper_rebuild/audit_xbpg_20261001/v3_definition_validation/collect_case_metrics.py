#!/usr/bin/env python3
"""Lossless small-source transcription plus explicit decimal pair subtraction.

Reads only this round's committed singleton metrics, support and call ledgers.
No runtime inputs, error series, reference, native or evaluator is opened.
"""
import csv
import json
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ['horizontal_rmse_m', 'up_rmse_m', 'yaw_rmse_deg',
          'roll_rmse_deg', 'pitch_rmse_deg']


def read_json(path):
    return json.loads(path.read_text(), parse_float=Decimal)


def main():
    queue = list(csv.DictReader((HERE / 'CANDIDATE_QUEUE.csv').open()))
    assert len(queue) == 10 and len({r['slot_id'] for r in queue}) == 10
    native = {r['slot_id']: r for r in csv.DictReader((HERE / 'RUN_MANIFEST.csv').open())}
    rows = []
    support_rows = []
    for q in queue:
        candidate, run = q['candidate_id'], q['baseline_run_id']
        bdir = HERE / 'evaluation/results/BASELINE' / run
        cdir = HERE / 'evaluation/results' / candidate / run
        pair = read_json(cdir / 'COMMON_SUPPORT.json')
        assert pair['pairing'] == 'EXACT_TIMESTAMP_NO_INTERPOLATION'
        paths = [(bdir / 'FULL_METRICS.json', cdir / 'FULL_METRICS.json')]
        if q['group'] in ['A1', 'A2']:
            paths.append((bdir / 'FIXED_WINDOW_METRICS.json', cdir / 'FIXED_WINDOW_METRICS.json'))
        for bp, cp in paths:
            bvalue, cvalue = read_json(bp), read_json(cp)
            if isinstance(bvalue, dict):
                bvalue, cvalue = [bvalue], [cvalue]
            bd = {r.get('window', 'full'): r for r in bvalue}
            cd = {r.get('window', 'full'): r for r in cvalue}
            assert bd.keys() == cd.keys()
            for window, b in bd.items():
                c = cd[window]
                for name in ['run_id', 'case_id', 'method_id', 'sequence_id', 'data_mode',
                             'synthetic_data_used', 'semisynthetic_data_used', 'evaluator_contract']:
                    assert b[name] == c[name], (q['slot_id'], name)
                assert b['run_id'] == run and b['case_id'] == q['case_id']
                # Full exact support plus identical fixed boundary implies the same subset.
                # Never infer common support just from equal row counts or envelopes.
                common = pair['common_count'] if window == 'full' else 'UNKNOWN'
                if window != 'full' and pair['identical_support']:
                    for key in ['window_start', 'window_end', 'end_inclusive', 'matched_epoch_count',
                                'time_start', 'time_end']:
                        assert b[key] == c[key], (q['slot_id'], window, key)
                    common = c['matched_epoch_count']
                identity = dict(slot_id=q['slot_id'], candidate_id=candidate, baseline_run_id=run,
                                case_id=q['case_id'], group=q['group'], method_id=q['method_id'],
                                data_mode=q['data_mode'], synthetic_data_used=q['synthetic_data_used'],
                                semisynthetic_data_used=q['semisynthetic_data_used'], window=window,
                                native_status=native[q['slot_id']]['status'],
                                baseline_evaluation_status=b['evaluation_status'],
                                candidate_evaluation_status=c['evaluation_status'],
                                baseline_count=b['matched_epoch_count'], candidate_count=c['matched_epoch_count'],
                                common_count=common, baseline_source=str(bp.relative_to(HERE)),
                                candidate_source=str(cp.relative_to(HERE)),
                                row_key='run_id=' + run + ';window=' + window)
                support_rows.append({**identity,
                    'nominal_start': c['sequence_window_start_s'], 'nominal_end': c['sequence_window_end_s'],
                    'end_inclusive': c.get('end_inclusive', True),
                    'actual_first': c['time_start'], 'actual_last': c['time_end'],
                    'reference_epoch_count': 'UNKNOWN' if c['reference_epoch_count'] is None else c['reference_epoch_count'],
                    'support_basis': 'exact full timestamp intersection' if window == 'full' else
                                     'identical full timestamp support intersected with the same fixed window',
                    'source_key': '/matched_epoch_count;/time_start;/time_end;/reference_epoch_count'})
                for field in FIELDS:
                    bv, cv = b[field], c[field]
                    with localcontext() as ctx:
                        ctx.prec = 50
                        delta = cv - bv
                    rows.append({**identity, 'field': field, 'unit': 'deg' if field.endswith('_deg') else 'm',
                                 'baseline_source_value': bv, 'candidate_source_value': cv,
                                 'candidate_minus_baseline': delta,
                                 'calculation': 'Decimal subtraction of recorded JSON scalars; no new evaluation'})
    assert len(support_rows) == 22 and len(rows) == 110
    for name, data in [('CASE_METRICS.csv', rows), ('CASE_SUPPORT.csv', support_rows)]:
        with (HERE / name).open('w', newline='') as f:
            writer = csv.DictWriter(f, list(data[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(data)
    print(json.dumps({'planned_combinations': len(queue), 'case_windows': len(support_rows),
                      'metric_pairs': len(rows), 'native_calls': 0, 'evaluator_calls': 0,
                      'reference_reads': 0, 'new_validation_calculation': 'paired scalar subtraction only'}))


if __name__ == '__main__':
    main()
