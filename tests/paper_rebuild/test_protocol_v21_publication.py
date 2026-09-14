"""Small synthetic publication checks; no real plot/source execution."""
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.publication import protocol_v21_data as data
from legsa_gins.paper_rebuild.publication import protocol_v21_figures as f
from legsa_gins.paper_rebuild.publication.protocol_v21_render import render
from legsa_gins.paper_rebuild.clean6_sensor_v21 import pack


def roles():
    return pd.DataFrame([
        dict(method_id='F01', case_id='D01_seed00', formal_F01_reused=True,
             synthetic_data_used=False, semisynthetic_data_used=False, trace_used_online=False),
        dict(method_id='A04', case_id='D01_seed00', formal_F01_reused=False,
             synthetic_data_used=False, semisynthetic_data_used=True, trace_used_online=False),
        dict(method_id='A04', case_id='C00_clean_normal', formal_F01_reused=False,
             synthetic_data_used=False, semisynthetic_data_used=False, trace_used_online=False)])


def test_roles_preserve_only_formal_f01_old_flags():
    rows = roles()
    assert data.validate_roles(rows, domain='CORE') == {
        'formal_F01_reused_count': 1, 'new_v21_count': 2, 'controlled_case_rows': 2}
    rows.loc[1, 'semisynthetic_data_used'] = False
    with pytest.raises(ValueError, match='data flags disagree'):
        data.validate_roles(rows, domain='CORE')
    rows = roles(); rows.loc[1, 'formal_F01_reused'] = True
    with pytest.raises(ValueError, match='Only formal F01'):
        data.validate_roles(rows, domain='CORE')


def test_registry_and_output_guard_exclude_immutable_editions(tmp_path):
    assert len(f.FIGURES) == 28
    assert 'MFIG21' not in f.FIGURES
    with pytest.raises(ValueError, match='Unregistered figure'):
        render(tmp_path/'absent.zip', tmp_path/'v21', figures=['MFIG21'])
    with pytest.raises(ValueError, match='immutable'):
        render(tmp_path/'absent.zip', tmp_path/'v2', figures=['MFIG20'])


def test_nonuniform_row_map_and_f01_old_stride_remain_distinct(tmp_path):
    newcurve = b'time,error\n1,2\n2,3\n'
    oldcurve = b'time,error\n1,4\n2,5\n'
    mapping = gzip.compress(b'member_csv_row,source_csv_row\n2,3\n3,47\n')
    supplements = [dict(member='new.csv', source_row_map_member='new.source_rows.csv.gz'),
                   dict(member='f01.csv', source_row_first=2, source_row_stride=20,
                        source_protocol='F01_V2_BYTE_REUSE', display_projection='FROZEN_V2_BYTES')]
    contents = {'IDENTITY_PROBE.json': b'{"passed":true}', 'new.csv': newcurve, 'f01.csv': oldcurve,
        'new.source_rows.csv.gz': mapping, 'SUPPLEMENT_SOURCE_MANIFEST.json': json.dumps(supplements).encode()}
    manifest = {'members': {name: dict(size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                             for name, payload in contents.items()}}
    path = tmp_path/'test.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('PACKAGE_MANIFEST.json', json.dumps(manifest))
        for name, payload in contents.items():
            archive.writestr(name, payload)
    package = data.Package(path)
    for name in ('new.csv', 'f01.csv'):
        rows = package.table(name)
        package.use(rows[rows.time == 2])
    sources = {row['package_member']: row for row in package.sources()}
    assert sources['new.csv']['original_source_rows'] == [47]
    assert sources['f01.csv']['original_source_rows'] == [22]
    assert sources['new.source_rows.csv.gz']['csv_rows_including_header'] == [3]
    package.zip.close()


class Tables:
    def __init__(self, tables):
        self.tables, self.reads = tables, []

    def table(self, name):
        self.reads.append(name)
        if name not in self.tables:
            raise AssertionError('Unexpected source read: ' + name)
        return self.tables[name].copy()

    def use(self, frame):
        return frame


def test_zero_new_failures_never_opens_old_native_timeline():
    core = pd.DataFrame([dict(profile=method, evaluation_status='COMPLETED') for method in f.ALL])
    bundle = SimpleNamespace(core=lambda _: core, p=Tables({}), notes=[])
    figure, caption = f.mfig14(bundle)
    assert 'No pre-correction failure timeline is reused' in caption
    assert not bundle.p.reads
    assert bundle.notes[0]['new_F04_failure_count'] == 0
    assert any('Not applicable' in text.get_text() for ax in figure.axes for text in ax.texts)
    plt.close(figure)


def failure_package(tmp_path, *, missing_f04=False, recovered_case=False):
    """Exercise the real manifest writer/ZIP reader using synthetic native files."""
    records, pins = [], {}
    cases = [('D04_new_failure', 'CORE'), ('A00_addendum_failure', 'ADDENDUM')]
    if missing_f04:
        cases.append(('D07_other_available', 'CORE'))
    if recovered_case:
        cases.append(('D00_recovered_case', 'CORE'))
    for case, domain in cases:
        for method in ('F02', 'F04'):
            run = case+'_'+method
            root = tmp_path/'new_stage'/run
            record = {'run_id': run, 'dataset_id': 'BY2', 'case_id': case, 'method_id': method,
                      'effective_profile': pack.CONFIG[method], 'domain': domain,
                      'terminal_status': pack.FAILURE if method == 'F04' else 'COMPLETED',
                      'output_root': str(root), 'formal_F01_reused': False}
            records.append(record)
            if missing_f04 and case == 'D04_new_failure' and method == 'F04':
                continue
            root.mkdir(parents=True)
            source = root/'PORT_GNSS_UPDATE_TRACE.csv.gz'
            modes = ('NORMAL', 'NORMAL') if method == 'F02' else ('REJECT', 'REJECT')
            source.write_bytes(gzip.compress(('gnss_time,yaw_mode,yaw_update\n1,'+modes[0]+',1\n2,'+modes[1]+',1\n').encode()))
            pins[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
    writer = pack.PackageWriter(tmp_path/'synthetic_failure.zip', synthetic=True)
    inventory = pack.package_failure_series(writer, tmp_path/'new_stage', records, pins)
    writer.close({'passed': True, 'protocol_id': pack.PROTOCOL, 'synthetic_test_only': True})
    core = pd.DataFrame([{**r, 'profile': r['method_id'], 'effective_configuration_id': r['effective_profile'],
                          'evaluation_status': 'COMPLETED' if r['terminal_status'] == 'COMPLETED' else 'NOT_RUN_ALGORITHM_FAILURE'}
                         for r in records if r['domain'] == 'CORE'])
    if recovered_case:
        # A stale older timeline must never override the current CORE terminal.
        core.loc[core.case_id == 'D00_recovered_case', 'evaluation_status'] = 'COMPLETED'
    bundle = SimpleNamespace(core=lambda _: core.copy(), p=data.Package(writer.path), notes=[],
                             disclose=lambda *_args: None)
    return bundle, inventory


def test_nonzero_core_failure_runs_end_to_end_with_mixed_domain_inventory(tmp_path):
    bundle, inventory = failure_package(tmp_path)
    assert {r['domain'] for r in inventory} == {'CORE', 'ADDENDUM'}
    assert all({'terminal_status', 'evaluation_status', 'source_protocol'} <= set(r) for r in inventory)
    figure, caption = f.mfig14(bundle)
    assert caption.startswith('D04_new_failure: first new v2.1 CORE')
    assert 'Residual fields are empty' not in caption
    note = bundle.notes[0]
    assert note['selected_run_ids'] == ['D04_new_failure_F02', 'D04_new_failure_F04']
    used = {r['package_member'] for r in bundle.p.sources()}
    assert any('D04_new_failure_F04' in name for name in used)
    assert not any('A00_addendum_failure' in name for name in used)
    assert len(figure.axes[1].lines) == 4
    assert np.array_equal(figure.axes[1].lines[-1].get_ydata(), [1, 2])
    plt.close(figure)
    bundle.p.zip.close()


def test_recovered_old_case_cannot_select_a_failure_timeline(tmp_path):
    bundle, _ = failure_package(tmp_path, recovered_case=True)
    figure, caption = f.mfig14(bundle)
    assert caption.startswith('D04_new_failure:')
    assert not any('D00_recovered_case' in r['package_member'] for r in bundle.p.sources())
    plt.close(figure)
    bundle.p.zip.close()


@pytest.mark.parametrize('location', ['row', 'member'])
def test_old_f02_source_is_rejected_even_when_case_identity_matches(tmp_path, location):
    bundle, _ = failure_package(tmp_path)
    if location == 'row':
        name = 'supplemental/FAILURE_SERIES/SERIES_MANIFEST.csv'
        bundle.p.table(name)
        frame = bundle.p.cache[name]
        mask = (frame.case_id == 'D04_new_failure') & (frame.method_id == 'F02')
        frame.loc[mask, 'source_protocol'] = 'F01_V2_BYTE_REUSE'
    else:
        name = 'supplemental/FAILURE_SERIES/D04_new_failure_F02.csv.gz'
        bundle.p.manifest['members'][name]['source_protocol'] = 'IMMUTABLE_PRE_CORRECTION'
    with pytest.raises(data.EvidenceUnavailable, match='new v2.1'):
        f.mfig14(bundle)
    bundle.p.zip.close()


def test_missing_first_core_failure_trace_stays_unavailable_without_another_case(tmp_path):
    bundle, inventory = failure_package(tmp_path, missing_f04=True)
    item = next(r for r in inventory if r['run_id'] == 'D04_new_failure_F04')
    assert item['status'] == 'UNAVAILABLE' and item['evaluation_status'] == 'NOT_RUN_ALGORITHM_FAILURE'
    figure, caption = f.mfig14(bundle)
    assert 'D04_new_failure' in caption and 'UNAVAILABLE for F04' in caption
    assert bundle.notes[0]['native_trace_unavailable_methods'] == ['F04']
    assert not any(r['package_member'].endswith('.csv.gz') for r in bundle.p.sources())
    assert any('UNAVAILABLE' in text.get_text() for ax in figure.axes for text in ax.texts)
    plt.close(figure)
    bundle.p.zip.close()


def test_ladder_uses_twelve_new_by2_rows_and_preserves_variant_order():
    table = pd.DataFrame([dict(variant_id=variant, method_id=method, dataset_id='BY2',
        evaluator_version='v3', evaluation_status='COMPLETED',
        horizontal_rmse_m=i+1., up_rmse_m=i+2., yaw_rmse_deg=i+3.)
        for i, variant in enumerate(f.VARIANTS) for method in ('F03', 'A04')])
    bundle = SimpleNamespace(p=Tables({data.LADDER: table}))
    figure, caption = f.mfig17(bundle)
    assert len(figure.axes) == 3
    assert [tick.get_text() for tick in figure.axes[0].get_xticklabels()] == f.VARIANTS
    assert bundle.p.reads == [data.LADDER]
    plt.close(figure)
    table.loc[0, 'dataset_id'] = 'BY2H'
    with pytest.raises(data.EvidenceUnavailable, match='twelve completed BY2'):
        f.mfig17(bundle)


def residual_table():
    rows = []
    for dataset in ('BY2', 'BY2H', 'BY2O'):
        for stage, value in [('before', 1.), ('v21_final', .2)]:
            rows.append(dict(dataset_id=dataset, sensor='HV', axis='horizontal', statistic='sigma_HV_mps',
                             correction_stage=stage, value=value, unit='m/s', n=99))
    for dataset, window in [('BY2', 'first_1000'), ('BY2H', 'first_1000'),
                            ('BY2O', 'first_1000'), ('BY2O', 'BY2O_standing')]:
        for axis in ('roll', 'pitch'):
            for stage, value in [('before', 2.), ('v21_final', -.4)]:
                rows.append(dict(dataset_id=dataset, sensor='RP', axis=axis, statistic='mean',
                    correction_stage=stage, value=value, unit='deg', window_id=window,
                    window_start_s=1., window_end_s=2., n=1000))
    return pd.DataFrame(rows)


def test_residual_pairing_keeps_final_scale_and_every_static_window():
    table = residual_table()
    _, paired = f.residual_pairs(table, 'RP', 'pitch', 'mean')
    assert list(zip(paired.dataset_id, paired.window_id))[-2:] == [('BY2O', 'first_1000'), ('BY2O', 'BY2O_standing')]
    assert len(paired) == 4
    table.loc[(table.sensor == 'HV') & (table.correction_stage == 'v21_final'), 'correction_stage'] = 'inverse_scaled'
    with pytest.raises(data.EvidenceUnavailable, match='before/final'):
        f.residual_pairs(table, 'HV', 'horizontal', 'sigma_HV_mps')


def test_residuals_reject_mismatched_window_support():
    table = residual_table()
    table.loc[(table.sensor == 'RP') & (table.dataset_id == 'BY2') &
              (table.correction_stage == 'v21_final'), 'n'] = 999
    with pytest.raises(data.EvidenceUnavailable, match='Missing or nonfinite'):
        f.residual_pairs(table, 'RP', 'roll', 'mean')


def test_mfig20_has_three_unchanged_imu_and_three_residual_panels():
    samples = pd.DataFrame([dict(axis=axis, lag_s=lag, variance_m2ps2=.1+lag*.2)
                           for axis in ('north', 'east', 'up') for lag in (1., 2.)])
    parameters = pd.DataFrame([dict(axis=axis, q_m2ps3=.2, c_m2ps2=.1) for axis in ('north', 'east', 'up')])
    bundle = SimpleNamespace(p=Tables({f.old.CAL+'00_CALIBRATION/LAG_VARIANCE_FIT.csv': samples,
        f.old.CAL+'00_CALIBRATION/CALIBRATED_PARAMETERS.csv': parameters, data.RESIDUALS: residual_table()}))
    figure, caption = f.mfig20(bundle)
    assert len(figure.axes) == 6
    assert len(figure.axes[-1].get_xticklabels()) == 4
    assert 'no regression is refitted' in caption
    plt.close(figure)


def test_mfig22_selects_new_comparison_fields_all_ten_methods():
    table = pd.DataFrame([dict(method_id=method, metric_name=metric, evaluator_version='v3',
        dataset_id='BY2', domain='CORE', scope='ALL', statistic='median',
        v2_value=2., v21_value=1., v21_minus_v2=-1., paired_finite_count=541,
        registered_case_count=541) for method in f.NEW_METHODS
        for metric in ('horizontal_rmse_m', 'yaw_rmse_deg')])
    bundle = SimpleNamespace(p=Tables({data.COMPARISON: table}))
    figure, caption = f.mfig22(bundle)
    assert all(len(ax.get_yticklabels()) == 10 for ax in figure.axes)
    assert all('n=541/541' in tick.get_text() for tick in figure.axes[0].get_yticklabels())
    assert bundle.p.reads == [data.COMPARISON]
    assert 'no direction of change is interpreted' in caption
    plt.close(figure)


def test_quality_sigma_is_validated_and_caption_corrected(monkeypatch):
    tables = {'supplemental/SEQUENCE_QUALITY/'+dataset+'.csv': pd.DataFrame({'yaw_std_deg': [2.933193]})
              for dataset in ('BY2', 'BY2H', 'BY2O')}
    bundle = SimpleNamespace(p=Tables(tables))
    monkeypatch.setattr(f.old, 'mfig16', lambda _: (None, 'constant 1.5° yaw sigma'))
    _, caption = f.mfig16(bundle)
    assert 'constant 2.933193°' in caption and '3.0°' in caption
    tables['supplemental/SEQUENCE_QUALITY/BY2.csv']['yaw_std_deg'] = 1.5
    with pytest.raises(data.EvidenceUnavailable, match='v2.1 yaw sigma'):
        f.mfig16(bundle)
