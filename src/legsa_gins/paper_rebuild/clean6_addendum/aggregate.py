"""Separate addendum inference, using full-rate error series and explicit failures."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
import math
from pathlib import Path

import numpy as np

from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_degradation.common import write_json
from ..clean6_canonical_v2.aggregate import (finite_stats, logical_rows, pairwise_tables, write_csv)
from ..manifest import sha256_file
from ..publication.derived_tables import TIE_EPS, wilcoxon_signed_rank_p


def outage_metrics(path, start, end):
    """Last observed epoch, no interpolation; any nonfinite value invalidates max."""
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    values, times = [], []
    previous = None
    with opener(path, 'rt', newline='') as stream:
        for row in csv.DictReader(stream):
            t = float(row['time'])
            if not math.isfinite(t) or (previous is not None and t <= previous):
                raise ValueError('Unordered or nonfinite full-rate evaluation epochs')
            previous = t
            if start <= t < end:
                times.append(t)
                values.append(float(row['horizontal_err_m']))
    return {'outage_end_horizontal_error_m': values[-1] if values and math.isfinite(values[-1]) else None,
            'outage_end_evaluation_time_s': times[-1] if times else None,
            'max_horizontal_error_in_window_m': max(values) if values and all(map(math.isfinite, values)) else None,
            'outage_matched_epoch_count': len(values), 'outage_start_s': start, 'outage_end_s': end,
            'outage_metric_source_sha256': sha256_file(path), 'outage_metric_source': str(path),
            'outage_metric_endpoint_policy': '[start,end); last matched full-rate evaluation epoch; no interpolation',
            'outage_metric_status': 'AVAILABLE' if values and all(map(math.isfinite, values)) else 'UNAVAILABLE'}


def wilcoxon(values):
    """Exact conditional signs through 20 nonzero differences, ties included."""
    values = np.asarray(values, float)
    if not len(values):
        return None
    if not np.isfinite(values).all():
        raise ValueError('Wilcoxon requires finite paired differences')
    values = values[np.abs(values) > TIE_EPS]
    if not len(values):
        return 1.0
    if len(values) > 20:
        return wilcoxon_signed_rank_p(values)
    absolute = np.abs(values)
    ranks = np.empty(len(values), dtype=int)
    order = np.argsort(absolute)
    left = 0
    while left < len(values):
        right = left+1
        while right < len(values) and absolute[order[right]] == absolute[order[left]]:
            right += 1
        ranks[order[left:right]] = left+1+right  # twice the average 1-based rank
        left = right
    counts = {0: 1}
    for rank in ranks:
        updated = dict(counts)
        for total, count in counts.items():
            updated[total+int(rank)] = updated.get(total+int(rank), 0)+count
        counts = updated
    observed = int(ranks[values > 0].sum())
    low = sum(n for total, n in counts.items() if total <= observed)
    high = sum(n for total, n in counts.items() if total >= observed)
    return min(1.0, 2*min(low, high)/(2**len(values)))


def paired_tables(rows, pairs, metrics, *, n_boot=10000, seed=20260904):
    tables = pairwise_tables(rows, pairs=pairs, metrics=metrics, n_boot=n_boot, seed=seed)
    for summary in tables[1]:
        group = [r['delta_candidate_minus_reference'] for r in tables[0]
                 if r['comparison'] == summary['comparison'] and r['metric_name'] == summary['metric_name']
                 and (summary['scope'] == 'overall' or r['case_family'] == summary['family'])]
        summary['wilcoxon_p'] = wilcoxon(group)
        summary['wilcoxon_approximation'] = 'exact conditional signs with ties for n_nonzero<=20; frozen normal approximation otherwise'
    return tables


def hypothesis_tables(unique, case_lookup, contract, *, n_boot=10000, seed=20260904):
    primary = contract['statistics']['primary_metrics']
    hv, no_hv = contract['hypotheses']['H1']['HV'], contract['hypotheses']['H1']['no_HV']
    pairs = [(a+'_vs_'+b, a, b) for a in hv for b in no_hv]
    tables = paired_tables(unique, pairs, primary, n_boot=n_boot, seed=seed)
    finite = tables[0]
    components = []
    for name, a, b in pairs:
        for metric in primary:
            group = [r for r in finite if r['comparison'] == name and r['metric_name'] == metric and r['case_family'] == 'A1']
            medians = {d: [r['delta_candidate_minus_reference'] for r in group if case_lookup[r['case_id']]['duration_s'] == d]
                       for d in (10, 20, 30)}
            complete = len(group) == 27 and all(len(v) == 9 for v in medians.values())
            median = float(np.median([r['delta_candidate_minus_reference'] for r in group])) if group else None
            dm = {d: float(np.median(v)) if v else None for d, v in medians.items()}
            benefit = median < 0 if complete else None
            trend = dm[30] < dm[20] < dm[10] if complete else None
            components.append({'hypothesis': 'H1', 'comparison': name, 'metric_name': metric, 'finite_count': len(group),
                'median_delta': median, 'median_10s': dm[10], 'median_20s': dm[20], 'median_30s': dm[30],
                'benefit': benefit, 'duration_trend': trend, 'complete': complete})
    passed = [r[k] for r in components for k in ('benefit', 'duration_trend') if r[k] is not None]
    h1 = ('INCOMPLETE' if not all(r['complete'] for r in components) else 'SUPPORTED' if all(passed)
          else 'PARTIALLY_SUPPORTED' if any(passed) else 'NOT_SUPPORTED')
    lookup = {(r['case_family'], case_lookup[r['case_id']]['duration_s'], r['seed_id'], r['comparison'], r['metric_name']): r for r in finite}
    h2_cases = []
    for name, a, b in pairs:
        for duration in (10, 20):
            for seed_id in ('seed_'+str(i).zfill(2) for i in range(9)):
                for metric in primary:
                    one = lookup.get(('A1', duration, seed_id, name, metric))
                    two = lookup.get(('A2', duration, seed_id, name, metric))
                    h2_cases.append({'comparison': name, 'metric_name': metric, 'duration_s': duration,
                        'seed_id': seed_id, 'A1_delta': one['delta_candidate_minus_reference'] if one else None,
                        'A2_delta': two['delta_candidate_minus_reference'] if two else None,
                        'A2_minus_A1_delta': two['delta_candidate_minus_reference']-one['delta_candidate_minus_reference'] if one and two else None,
                        'status': 'AVAILABLE' if one and two else 'INCOMPLETE'})
    h2_summary = []
    for name, a, b in pairs:
        for metric in primary:
            for duration in ('ALL', 10, 20):
                group = [r for r in h2_cases if r['comparison'] == name and r['metric_name'] == metric
                         and (duration == 'ALL' or r['duration_s'] == duration)]
                values = [r['A2_minus_A1_delta'] for r in group if r['status'] == 'AVAILABLE']
                stat = finite_stats(values, n_boot=n_boot, seed=seed)
                stat['wilcoxon_p'] = wilcoxon(values)
                stat['wilcoxon_approximation'] = 'exact conditional signs with ties for n_nonzero<=20; frozen normal approximation otherwise'
                h2_summary.append({'comparison': name, 'metric_name': metric, 'duration_s': duration,
                    'registered_count': len(group), 'complete': len(values) == len(group), **stat})
    primary_h2 = [r for r in h2_summary if r['comparison'] == 'F04_vs_A06' and r['duration_s'] == 'ALL']
    negative = [r['median_delta_candidate_minus_reference'] < 0 for r in primary_h2 if r['complete']]
    h2 = ('INCOMPLETE' if not all(r['complete'] for r in primary_h2) else 'SUPPORTED' if all(negative)
          else 'PARTIALLY_SUPPORTED' if any(negative) else 'NOT_SUPPORTED')
    h3_pairs = [('full_vs_no_Go2', 'F04', 'A07'), ('full_vs_no_RP', 'F04', 'A05'),
                ('full_vs_no_HV', 'F04', 'A06'), ('A04_vs_F03', 'A04', 'F03')]
    h3 = paired_tables([r for r in unique if r['case_family'] == 'A1'], h3_pairs, primary,
                       n_boot=n_boot, seed=seed)[3]
    for row in h3:
        row['duration_s'] = case_lookup[row['case_id']]['duration_s']
        d = row['delta_candidate_minus_reference']
        row['sign'] = 'UNAVAILABLE' if d is None else 'HARM' if d > TIE_EPS else 'BENEFIT' if d < -TIE_EPS else 'TIE'
    harms = [r for r in h3 if r['comparison'] == 'full_vs_no_Go2' and r['sign'] == 'HARM']
    h3_missing = sum(r['sign'] == 'UNAVAILABLE' for r in h3)
    decisions = {'H1': h1, 'H2': h2,
                 'H3': 'OBSERVED_SOME_SEED_HARM' if harms else 'INCOMPLETE' if h3_missing else 'NOT_OBSERVED',
                 'H3_harm_count': len(harms), 'H3_missing_count': h3_missing}
    return {'H1_CROSS_GROUP_PAIRWISE_CASE_LEVEL.csv': tables[0], 'H1_CROSS_GROUP_PAIRWISE_SUMMARY.csv': tables[1],
            'H1_COMPONENT_DECISIONS.csv': components, 'H2_MATCHED_FAMILY_CASE_LEVEL.csv': h2_cases,
            'H2_MATCHED_FAMILY_SUMMARY.csv': h2_summary, 'H3_SEED_SIGNS.csv': h3}, decisions


def aggregate_all(evaluations, records, contract, stage, code_commit, *, n_boot=None):
    """Write only 13_AGGREGATE_ADDENDUM; core aggregate readers are unnecessary."""
    cases = {r['case_id']: r for r in contract['case_rows']}
    expected = {(c, m) for c in cases for m in contract['runtime']['profiles']}
    if len(records) != 495 or {(r['case_id'], r['method_id']) for r in records} != expected:
        raise ValueError('Addendum requires exactly 495 distinct native terminal records')
    stats = contract['statistics']
    n_boot = stats['bootstrap']['resamples'] if n_boot is None else n_boot
    seed = stats['bootstrap']['seed']
    pairs = [(r['comparison'], r['candidate_method_id'], r['reference_method_id']) for r in stats['pair_definitions']]
    metrics = stats['primary_metrics']+stats['secondary_metrics']
    statuses = []
    for version in ('v3', 'v2'):
        unique = sorted([dict(r) for r in evaluations if r['evaluator_version'] == version], key=lambda r: r['run_id'])
        if len(unique) != 495 or {(r['case_id'], r['method_id']) for r in unique} != expected:
            raise ValueError('Addendum evaluation terminal coverage differs from preregistration')
        logical = logical_rows(unique)
        if len(logical) != 585:
            raise ValueError('Addendum logical aliases must close to 585 rows')
        root = Path(stage)/'13_AGGREGATE_ADDENDUM'/version
        root.mkdir(parents=True, exist_ok=False)
        tables = {'UNIQUE_EVALUATION_RESULTS.csv': unique, 'LOGICAL_EVALUATION_RESULTS.csv': logical}
        for name, rows in (('UNIQUE', unique), ('LOGICAL', logical)):
            tables[name+'_METHOD_SUMMARY.csv'] = canonical._summary_rows(rows, ('method_id',), metrics)
        pc, ps, ss, fc, fs = paired_tables(logical, pairs, metrics, n_boot=n_boot, seed=seed)
        for summary in ss:
            matching = [r for r in pc if r['degradation_id'] == summary['degradation_id']
                        and r['comparison'] == summary['comparison'] and r['metric_name'] == summary['metric_name']]
            summary['finite_case_count'] = summary.pop('valid_seed_count')
            summary['distinct_seed_count'] = len({r['seed_id'] for r in matching})
            summary['distinct_duration_count'] = len({cases[r['case_id']]['duration_s'] for r in matching})
        for row in pc+fc:
            row.update(duration_s=cases[row['case_id']]['duration_s'])
            d = row.get('delta_candidate_minus_reference')
            row['sign'] = 'UNAVAILABLE' if d is None else 'HARM' if d > TIE_EPS else 'BENEFIT' if d < -TIE_EPS else 'TIE'
        tables.update({'PAIRWISE_CASE_LEVEL.csv': pc, 'PAIRWISE_SUMMARY.csv': ps,
            'FAILURE_AWARE_PAIRWISE_CASE_LEVEL.csv': fc, 'FAILURE_AWARE_PAIRWISE_SUMMARY.csv': fs,
            'SEED_SUMMARY.csv': ss, 'SEED_SIGNS.csv': fc})
        duration_tables, duration_failure, duration_methods = [], [], []
        for family, duration in sorted({(c['case_family'], c['duration_s']) for c in cases.values()}):
            rows = [r for r in logical if r['case_family'] == family and cases[r['case_id']]['duration_s'] == duration]
            pt = paired_tables(rows, pairs, metrics, n_boot=n_boot, seed=seed)
            for source, target in ((pt[1], duration_tables), (pt[4], duration_failure)):
                target.extend({**r, 'case_family': family, 'duration_s': duration} for r in source if r['scope'] == 'overall')
            duration_methods.extend({**r, 'case_family': family, 'duration_s': duration}
                                    for r in canonical._summary_rows(rows, ('method_id',), metrics))
        tables.update({'PAIRWISE_BY_DURATION.csv': duration_tables,
            'FAILURE_AWARE_PAIRWISE_BY_DURATION.csv': duration_failure, 'METHOD_SUMMARY_BY_DURATION.csv': duration_methods})
        counts = Counter((r['case_family'], cases[r['case_id']]['duration_s'], r['method_id'], r['terminal_status']) for r in records)
        tables['FAILURE_COUNTS.csv'] = [{'case_family': f, 'duration_s': d, 'method_id': m,
                                       'terminal_status': s, 'run_count': n} for (f, d, m, s), n in sorted(counts.items())]
        ht, decisions = hypothesis_tables(unique, cases, contract, n_boot=n_boot, seed=seed)
        tables.update(ht)
        for name, rows in tables.items():
            write_csv(root/name, rows)
        write_json(root/'HYPOTHESIS_DECISIONS.json', decisions)
        write_json(root/'FIELD_DEFINITIONS.json', {**contract['field_definitions'], 'statistics': stats,
                   'label': contract['label'], 'data_roles': contract['data_roles'],
                   'synthetic_fixture_bootstrap_override': n_boot != stats['bootstrap']['resamples']})
        status = {'terminal_status': 'PASS_ADDENDUM_A1_A2_AGGREGATED_WITH_EXPLICIT_TERMINALS',
                  'evaluator_version': version, 'code_commit': code_commit, 'unique_rows': len(unique),
                  'logical_rows': len(logical), 'evaluation_status_counts': dict(Counter(r['evaluation_status'] for r in unique)),
                  'native_status_counts': dict(Counter(r['terminal_status'] for r in records)),
                  'hypotheses': decisions, 'label': contract['label'], **contract['data_roles']}
        write_json(root/'FINAL_EVALUATION_SUMMARY.json', status)
        statuses.append(status)
    return statuses
