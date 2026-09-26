"""Preregistered signed RMSE differences; unavailable endpoints never substituted."""
from __future__ import annotations
import math

METRICS = ('horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m', 'yaw_rmse_deg')


def difference(term, left, right):
    row = {'term': term, 'left_source_row': left.get('source_row', 'UNAVAILABLE') if left else 'UNAVAILABLE',
           'right_source_row': right.get('source_row', 'UNAVAILABLE') if right else 'UNAVAILABLE',
           'support_policy': 'native support; no resampling or matched-support claim'}
    for metric in METRICS:
        try:
            a, b = float(left[metric]), float(right[metric])
            row[metric] = a-b if math.isfinite(a) and math.isfinite(b) else 'UNAVAILABLE'
        except (TypeError, KeyError, ValueError):
            row[metric] = 'UNAVAILABLE'
    row['status'] = 'AVAILABLE' if all(row[m] != 'UNAVAILABLE' for m in METRICS) else 'UNAVAILABLE'
    for side, source in (('left', left), ('right', right)):
        for field in ('time_start', 'time_end', 'matched_epoch_count'):
            row[f'{side}_{field}'] = source.get(field, 'UNAVAILABLE') if source else 'UNAVAILABLE'
    return row


def build_decomposition(v2, v3):
    idx = {(r['variant_id'], r['method_id']): r for r in v2}
    idx3 = {(r['variant_id'], r['method_id']): r for r in v3}
    rows = []
    for method in ('F01', 'F03', 'A04'):
        for term, a, b in (('time', 'V0', 'V1'), ('rate', 'V1', 'V2')):
            rows.append(difference(f'{term}:{method}', idx.get((a, method)), idx.get((b, method))))
    rows.append(difference('module:V2:A04-F03', idx.get(('V2','A04')), idx.get(('V2','F03'))))
    rows.append(difference('estimator:V2e-EXT05C', idx.get(('V2e','F01')), idx.get(('EXTERNAL','EXT05C'))))
    rows.append(difference('dual_receiver:LC01-EXT05C', idx.get(('EXTERNAL','LC01')), idx.get(('EXTERNAL','EXT05C'))))
    for key, row in idx.items():
        rows.append(difference('measurement_point:'+':'.join(key), row, idx3.get(key)))
    return rows
