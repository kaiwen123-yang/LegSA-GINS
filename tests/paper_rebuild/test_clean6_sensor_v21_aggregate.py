"""Synthetic P-13 exact-join, failure, hypothesis, and inherited-stat tests."""
import copy

import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21 import aggregate as a


PROFILES = ['F02', 'F03', 'F04', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09']


def row(case='C00_clean_normal', dataset='BY2', method='F04', version='v3', value=3., **extra):
    return {'run_id': dataset+'_'+case+'_'+method, 'case_id': case, 'dataset_id': dataset,
            'method_id': method, 'effective_configuration_id': method, 'evaluator_version': version,
            'evaluation_status': 'COMPLETED', 'solver_terminal_status': 'COMPLETED',
            'case_family': 'clean', 'degradation_id': 'CLEAN', 'seed_id': '',
            'finite_output': True, 'synthetic_data_used': True, 'data_mode': 'synthetic_test',
            'horizontal_rmse_m': value, 'yaw_rmse_deg': value,
            'roll_rmse_deg': value, 'pitch_rmse_deg': value,
            'yaw_abs_error_over_std_median': value,
            'scheme_c_downweight_count': 4, 'scheme_c_reject_count': 2, **extra}


def hypothesis_fixture():
    cases = [{'case_id': f'D62_20s_seed_{i:02d}', 'case_family': 'A2', 'duration_s': 20,
              'seed_index': f'seed_{i:02d}'} for i in range(9)]
    contract = {'scope_and_accounting': {'profiles': ['F04']},
                'hypotheses': {'H7': {'definition': 'new in [1,2] and lower than old'}, 'H9': {'threshold_m': 10.}}}
    old, new = [], []
    for version in ('v3', 'v2'):
        for dataset in a.DATASETS:
            cid = a.C00 if dataset == 'BY2' else dataset+'_NATURAL'
            old.append(row(cid, dataset, version=version))
            new.append(row(cid, dataset, version=version, value=1.5, scheme_c_downweight_count=1, scheme_c_reject_count=0))
        for case in cases:
            old.append(row(case['case_id'], version=version, case_family='A2', degradation_id='D62', duration_s=20))
            new.append(row(case['case_id'], version=version, case_family='A2', degradation_id='D62', duration_s=20,
                           outage_end_horizontal_error_m=9.))
    return a.normalize_rows(old), a.normalize_rows(new), contract, {'case_rows': cases}


def test_normalization_uses_named_counter_aliases_and_does_not_substitute_h7_ratio():
    source = row()
    source.pop('yaw_abs_error_over_std_median')
    source['yaw_calibration_ratio_deg'] = 1.6
    result = a.normalize_rows([source])[0]
    assert result['yaw_DOWNWEIGHT'] == 4 and result['yaw_REJECT'] == 2
    assert result['yaw_DOWNWEIGHT_plus_REJECT'] == 6
    assert 'yaw_abs_error_over_std_median' not in result
    with pytest.raises(ValueError, match='Duplicate evaluation'):
        a.normalize_rows([source, source])


def test_comparison_pairs_exact_cells_and_never_creates_failure_delta():
    old = [row('D05_seed_00', value=10., case_family='outage', degradation_id='D05', duration_s=10),
           row('D05_seed_01', value=100., case_family='outage', degradation_id='D05', duration_s=10)]
    new = [row('D05_seed_00', value=7., case_family='outage', degradation_id='D05', duration_s=10),
           row('D05_seed_01', value=None, case_family='outage', degradation_id='D05', duration_s=10,
               evaluation_status='NOT_RUN_ALGORITHM_FAILURE', solver_terminal_status=a.ALGORITHM_FAILURE)]
    results = a.comparison_tables(old, new, ['F04'], metrics=['horizontal_rmse_m'])
    entry = next(r for r in results if r['scope'] == 'DURATION' and r['statistic'] == 'mean')
    assert (entry['v2_value'], entry['v21_value'], entry['v21_minus_v2']) == (10., 7., -3.)
    assert entry['v2_available_count'] == 2 and entry['v21_available_count'] == 1
    assert entry['paired_finite_count'] == 1 and entry['availability'] == 'PARTIAL'
    assert entry['v21_algorithm_failure_count'] == 1
    failures = a.failure_comparison(old, new, ['F04'])
    assert failures[0]['v2_ALL_YAW_REJECTED'] == 0 and failures[0]['v21_ALL_YAW_REJECTED'] == 1


def test_h7_h11_components_all_reported_with_strict_h9_boundary():
    old, new, contract, add = hypothesis_fixture()
    # Exactly 10 m must fail H9; a finite remainder still supports partial status.
    next(r for r in new if r['case_id'] == add['case_rows'][0]['case_id'] and r['evaluator_version'] == 'v3')['outage_end_horizontal_error_m'] = 10.
    components, summaries = a.hypothesis_tables(old, new, contract, add)
    decisions = {(r['evaluator_version'], r['hypothesis']): r for r in summaries}
    assert decisions[('v3', 'H7')]['decision'] == 'SUPPORTED'
    assert decisions[('v3', 'H8')]['decision'] == 'SUPPORTED'
    assert decisions[('v3', 'H9')]['decision'] == 'PARTIALLY_SUPPORTED'
    assert decisions[('v2', 'H9')]['decision'] == 'SUPPORTED'
    assert decisions[('v3', 'H10')]['component_count'] == 8
    assert decisions[('v3', 'H11')]['decision'] == 'REPORTED_NON_DIRECTIONAL'
    assert len([r for r in components if r['hypothesis'] == 'H9']) == 18


def test_h7_missing_old_ratio_is_incomplete_but_new_ratio_retained():
    old, new, contract, add = hypothesis_fixture()
    old[0].pop('yaw_abs_error_over_std_median')
    components, summaries = a.hypothesis_tables(old, new, contract, add)
    target = next(r for r in components if r['hypothesis'] == 'H7' and r['evaluator_version'] == 'v3' and r['dataset_id'] == 'BY2')
    assert target['decision'] == 'INCOMPLETE' and target['v2_value'] is None and target['v21_value'] == 1.5
    assert next(r for r in summaries if r['hypothesis'] == 'H7' and r['evaluator_version'] == 'v3')['decision'] == 'INCOMPLETE'


def test_h7_requires_both_interval_and_decrease_h8_zero_unchanged():
    old, new, contract, add = hypothesis_fixture()
    old[0]['yaw_abs_error_over_std_median'] = 1.4
    for source in (old[0], new[0]):
        source.update(yaw_DOWNWEIGHT=0, yaw_REJECT=0, yaw_DOWNWEIGHT_plus_REJECT=0)
    components, _ = a.hypothesis_tables(old, new, contract, add)
    chosen = {r['hypothesis']: r for r in components if r['dataset_id'] == 'BY2' and r['evaluator_version'] == 'v3' and r['case_id'] == a.C00}
    assert chosen['H7']['decision'] == 'NOT_SUPPORTED' and chosen['H8']['decision'] == 'UNCHANGED'


def test_failed_cell_h11_remains_nondirectional_missing_and_h9_missing_blocks_joint():
    old, new, contract, add = hypothesis_fixture()
    target = next(r for r in new if r['case_id'] == add['case_rows'][0]['case_id'] and r['evaluator_version'] == 'v3')
    target.update(evaluation_status='NOT_RUN_ALGORITHM_FAILURE', solver_terminal_status=a.ALGORITHM_FAILURE)
    components, summaries = a.hypothesis_tables(old, new, contract, add)
    cell = next(r for r in components if r['hypothesis'] == 'H11' and r['case_id'] == target['case_id'] and r['evaluator_version'] == 'v3')
    assert cell['v21_minus_v2'] is None and cell['decision'] == 'INCOMPLETE' and cell['direction'] == 'NOT_PRESET'
    assert next(r for r in summaries if r['hypothesis'] == 'H9' and r['evaluator_version'] == 'v3')['decision'] == 'INCOMPLETE'


def test_core_tables_keep_inherited_statistics_and_all_logical_aliases():
    methods = ['F01', *PROFILES]
    unique = a.normalize_rows([row(method=m, value=float(i+1)) for i, m in enumerate(methods)])
    records = [{**r, 'terminal_status': 'COMPLETED'} for r in unique]
    tables = a.core_tables(unique, records, n_boot=20)
    assert len(tables['UNIQUE_EVALUATION_RESULTS.csv']) == 11
    assert len(tables['LOGICAL_EVALUATION_RESULTS.csv']) == 13
    names = set(a.v2.AGGREGATE_FILES)-{'FINAL_EVALUATION_SUMMARY.json', 'EVALUATION_AND_AGGREGATE_STATUS.json'}
    assert names <= set(tables)
    pair = next(r for r in tables['PAIRWISE_CASE_LEVEL.csv'] if r['comparison'] == 'full_vs_strong' and r['metric_name'] == 'horizontal_rmse_m')
    f4, f3 = next(r for r in unique if r['method_id'] == 'F04'), next(r for r in unique if r['method_id'] == 'F03')
    assert pair['delta_candidate_minus_reference'] == f4['horizontal_rmse_m']-f3['horizontal_rmse_m']


def test_sequence_single_case_confidence_is_unavailable_and_datasets_separate():
    methods = ['F01', *PROFILES]
    rows = a.normalize_rows([row(a.C00 if d == 'BY2' else d+'_NATURAL', d, method=m) for d in a.DATASETS for m in methods])
    tables = a.sequence_tables(rows)
    assert len(tables['UNIQUE_EVALUATION_RESULTS.csv']) == 33 and len(tables['LOGICAL_EVALUATION_RESULTS.csv']) == 39
    assert all(r['confidence_interval_status'] == 'NOT_AVAILABLE_SINGLE_CASE' for r in tables['PAIRWISE_SUMMARY.csv'])
    assert {r['dataset_id'] for r in tables['PAIRWISE_CASE_LEVEL.csv']} == set(a.DATASETS)


def test_normalize_rejects_failed_or_nonfinite_results_before_statistics():
    with pytest.raises(a.ScientificStop):
        a.normalize_rows([row(finite_output=False)])
    with pytest.raises(a.ScientificStop):
        a.normalize_rows([row(horizontal_rmse_m=float('nan'))])
    with pytest.raises(a.ScientificStop):
        a.normalize_rows([row(evaluation_status='FAILED_EVALUATOR')])
