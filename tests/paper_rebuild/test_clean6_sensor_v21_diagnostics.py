"""Synthetic diagnostic tests only; no real provider/solver/evaluator calls."""
import copy
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.clean5_parity_p05.evaluation import consistency
from legsa_gins.paper_rebuild.clean6_sensor_v21 import diagnostics as d
from legsa_gins.paper_rebuild.manifest import sha256_file


def inputs(dataset='BY2', version='v3', method='A04'):
    window = {'BY2': [66, 340], 'BY2H': [413, 683], 'BY2O': [3186, 3563]}[dataset]
    t = np.arange(window[0], window[0] + 3, dtype=float)
    errors = pd.DataFrame({'time': t, 'err_n_m': [1., 4., 30.],
        'err_e_m': [3., 4., 0.], 'err_u_m': [-2., 1., 4.],
        'horizontal_err_m': np.hypot([1., 4., 30.], [3., 4., 0.]),
        'position_3d_err_m': np.sqrt(np.square([1., 4., 30.]) +
                                   np.square([3., 4., 0.]) + np.square([-2., 1., 4.])),
        'yaw_err_deg': [1., 4., 30.]})
    std = np.ones((3, 10)); std[:, 0] = t; std[:, 9] = [1., 10., 2.]
    nav = np.zeros((3, 11)); nav[:, 1] = t; nav[:, 10] = 90.
    case = d.C00 if dataset == 'BY2' else dataset + '_natural'
    identity = dict(run_id=dataset+'_'+method, method_id=method, dataset_id=dataset,
                    case_id=case, effective_profile='test_profile', data_mode='synthetic_test',
                    synthetic_data_used=True, semisynthetic_data_used=False)
    params = {} if dataset != 'BY2O' else {'start_s': 3187., 'end_s': 3187.5,
                                         'secondary_runs': [[3186., 3186.5]]}
    record = {**identity, 'terminal_status': 'COMPLETED', 'window': window,
              'case_meta': {'degradation_parameters_json': json.dumps(params)}}
    row = {**identity, 'effective_configuration_id': 'test_profile',
           'evaluation_status': 'COMPLETED', 'evaluator_version': version,
           'source_row': 'synthetic_only', 'matched_epoch_count': 3,
           'time_start': float(t[0]), 'time_end': float(t[-1]),
           'horizontal_rmse_m': 123., 'position_3d_rmse_m': 456.,
           'up_rmse_m': 789., 'yaw_rmse_deg': 321.}
    return record, row, errors, std, nav


def test_p05_ratio_is_median_of_epoch_ratios_not_calibration_ratio():
    record, row, errors, std, nav = inputs()
    actual = d.sidecars_from_arrays(record, row, errors, std, nav)
    original = consistency(errors, std)
    assert {key: actual['evaluation'][key] for key in original} == original
    assert actual['evaluation']['yaw_abs_error_over_std_median'] == 1.
    assert np.median(abs(errors.yaw_err_deg)) / np.median(std[:, 9]) == 2.
    assert len(actual['consistency_rows']) == 4
    assert actual['evaluation']['v3_std_transport'] == 'UNTRANSPORTED_STD_DIAGNOSTIC_ONLY'
    assert actual['evaluation']['yaw_consistency_status'] == 'UNCHANGED_YAW_STATE_STD'
    assert 'yaw_abs_error_over_std_median' not in row


def test_exact_epoch_rule_keeps_p05_right_tie_and_rejects_interpolation():
    record, row, errors, std, nav = inputs(version='v2')
    step = 2.**-25
    std = std[:2].copy(); std[:, 0] = [66., 66. + 2*step]
    std[:, 9] = [1., 2.]
    errors = errors.iloc[:1].copy(); errors['time'] = 66. + step
    nav = nav[:2].copy(); nav[:, 1] = std[:, 0]
    actual = d.sidecars_from_arrays(record, row, errors, std, nav)
    assert actual['evaluation']['yaw_abs_error_over_std_median'] == .5
    assert actual['evaluation']['consistency_status'] == 'SAME_POINT_STD'
    errors['time'] = 66. + 1e-4
    with pytest.raises(ValueError, match='STD error epochs differ'):
        d.sidecars_from_arrays(record, row, errors, std, nav)


def test_invalid_denominator_preserves_p05_unavailable_and_counts():
    record, row, errors, std, nav = inputs()
    std[1, 9] = 0.
    result = d.sidecars_from_arrays(record, row, errors, std, nav)
    assert result['evaluation']['yaw_abs_error_over_std_median'] == 'UNAVAILABLE'
    assert result['evaluation']['yaw_consistency_valid_count'] == 2
    assert result['evaluation']['yaw_std_nonpositive_count'] == 1
    assert result['consistency_rows'][-1]['status'] == 'UNAVAILABLE'


def test_by2_full_segments_copy_original_statistics_and_body_uses_native_yaw():
    record, row, errors, std, nav = inputs()
    result = d.sidecars_from_arrays(record, row, errors, std, nav)
    assert len(result['segment_rows']) == 4
    assert result['segment_rows'][0]['rmse'] == 123.
    body = result['body_rows'][0]
    assert body['forward_signed_mean_m'] == pytest.approx(errors.err_e_m.mean())
    assert body['right_signed_mean_m'] == pytest.approx(-errors.err_n_m.mean())
    assert body['forward_standard_deviation_m'] == pytest.approx(errors.err_e_m.std(ddof=0))
    assert body['std_ddof'] == 0


@pytest.mark.parametrize('dataset,count', [('BY2H', 4), ('BY2O', 20)])
def test_sequence_segments_keep_secondary_epochs(dataset, count):
    result = d.sidecars_from_arrays(*inputs(dataset))
    assert len(result['segment_rows']) == count
    if dataset == 'BY2O':
        horizontal = {r['segment_id']: r for r in result['segment_rows'] if r['metric_name'] == 'horizontal'}
        assert horizontal['full']['count'] == 3
        assert horizontal['outside']['count'] == 2
        assert horizontal['outside']['secondary_run_epoch_count'] == 1
        assert horizontal['during']['count'] == 1


def test_nonfinite_errors_and_identity_mismatch_are_rejected():
    record, row, errors, std, nav = inputs()
    errors.loc[1, 'err_n_m'] = np.nan
    with pytest.raises(ValueError, match='Nonfinite'):
        d.sidecars_from_arrays(record, row, errors, std, nav)
    row['method_id'] = 'F03'
    with pytest.raises(ValueError, match='identity differs'):
        d.sidecars_from_arrays(record, row, errors, std, nav)


def materialize(tmp_path, method='A04'):
    record, row, errors, std, nav = inputs(method=method)
    native = tmp_path / 'native'; native.mkdir()
    output = tmp_path / 'evaluation'; (output / 'FROZEN_EVALUATOR').mkdir(parents=True)
    np.savetxt(native / 'KF_GINS_STD.txt', std)
    np.savetxt(native / 'KF_GINS_Navresult.nav', nav)
    error_path = output / 'FROZEN_EVALUATOR/error_series.csv.gz'
    errors.to_csv(error_path, index=False, compression='gzip')
    record['output_root'] = str(native)
    record['output_seal'] = {p.name: {'sha256': sha256_file(p), 'size_bytes': p.stat().st_size}
                             for p in native.iterdir()}
    row.update(evaluation_output_root=str(output), error_series_source=str(error_path),
               std_sha256=sha256_file(native / 'KF_GINS_STD.txt'),
               native_nav_sha256=sha256_file(native / 'KF_GINS_Navresult.nav'))
    return record, row


def test_write_reuses_pinned_sidecars_and_does_not_mutate_evaluator(tmp_path, monkeypatch):
    record, row = materialize(tmp_path)
    before = copy.deepcopy(row)
    result = d.write_run_sidecars(record, [row])
    target = Path(row['evaluation_output_root']) / 'P13_DIAGNOSTICS'
    assert {p.name for p in target.iterdir()} == {
        'DIAGNOSTIC_ROWS.json', 'DIAGNOSTIC_MANIFEST.json', 'CONSISTENCY_ROWS.csv',
        'WINDOW_SEGMENT_SUMMARY.csv', 'BODY_FRAME_BIAS.csv'}
    assert row == before
    monkeypatch.setattr(d, 'sidecars_from_arrays', lambda *a: pytest.fail('recomputed completed sidecars'))
    reused = d.write_run_sidecars(record, [row])
    assert reused == result
    row['horizontal_rmse_m'] += 1
    with pytest.raises(ValueError, match='source identity differs'):
        d.write_run_sidecars(record, [row])


def test_write_rejects_seal_change_before_statistics(tmp_path):
    record, row = materialize(tmp_path)
    (Path(record['output_root']) / 'KF_GINS_STD.txt').write_text('changed')
    with pytest.raises(ValueError, match='hash differs'):
        d.write_run_sidecars(record, [row])


def old_sources(tmp_path, method='A04', retained=True):
    record, row = materialize(tmp_path, method=method)
    archive = tmp_path / 'archive'; archive.mkdir()
    errors = archive / 'v3/FROZEN_EVALUATOR/error_series.csv.gz'; errors.parent.mkdir(parents=True)
    errors.write_bytes(Path(row['error_series_source']).read_bytes())
    receipt_path = archive / 'ARCHIVE_RECEIPT.json'
    receipt_path.write_text(json.dumps({'status': 'ARCHIVE_VERIFIED', 'retained_files': {
        'v3/FROZEN_EVALUATOR/error_series.csv.gz': {'sha256': sha256_file(errors)}}}))
    record['archive_receipt'] = str(receipt_path)
    calibrated = tmp_path / 'calibrated'
    if retained:
        std = calibrated / ('03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2_' + method) / 'KF_GINS_STD.txt'
        std.parent.mkdir(parents=True)
        std.write_bytes((Path(record['output_root']) / 'KF_GINS_STD.txt').read_bytes())
    return record, row, calibrated


def test_old_h7_uses_exact_v2_errors_and_full_p06_std_hash(tmp_path):
    record, row, calibrated = old_sources(tmp_path)
    row['yaw_calibration_ratio_deg'] = 999.
    actual = d.old_h7_rows([record], [row], calibrated_root=calibrated)
    assert actual['evaluations'][0]['yaw_abs_error_over_std_median'] == 1.
    assert actual['evaluations'][0]['h7_reference_status'] == 'AVAILABLE_EXACT_V2_FULL_STD'
    assert not actual['evaluations'][0]['scalar_substitution_used']
    assert not actual['missing']
    path = calibrated / '03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2_A04/KF_GINS_STD.txt'
    path.write_text('wrong native STD')
    with pytest.raises(ValueError, match='does not match v2 output seal'):
        d.old_h7_rows([record], [row], calibrated_root=calibrated)


def test_old_h7_missing_std_is_incomplete_never_uses_calibration_or_3sigma(tmp_path):
    record, row, calibrated = old_sources(tmp_path, method='A03', retained=False)
    row['yaw_calibration_ratio_deg'] = 999.
    actual = d.old_h7_rows([record], [row], calibrated_root=calibrated)
    assert actual['evaluations'][0]['yaw_abs_error_over_std_median'] == 'UNAVAILABLE'
    assert actual['evaluations'][0]['h7_reference_status'] == 'INCOMPLETE'
    assert 'no calibration-ratio or interpolated-3sigma substitution' in actual['missing'][0]['reason']
    assert len(actual['consistency_rows']) == 4


def test_old_h7_archived_error_hash_mismatch_is_not_silently_replaced(tmp_path):
    record, row, calibrated = old_sources(tmp_path)
    error = Path(record['archive_receipt']).parent / 'v3/FROZEN_EVALUATOR/error_series.csv.gz'
    with gzip.open(error, 'wt') as stream:
        stream.write('time,yaw_err_deg\n66,99\n')
    with pytest.raises(ValueError, match='hash differs'):
        d.old_h7_rows([record], [row], calibrated_root=calibrated)
