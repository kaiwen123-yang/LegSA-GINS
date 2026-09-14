"""Temporary synthetic documents; no workspace documentation is modified."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.clean6_sensor_v21 import docs as d


AGENTS_TEXT = ('# Rules\n\n## 1. First\nuntouched one\n\n'
    '## 7. Internal method identities\n\nOriginal v2 0.098336 and Outcome FAIL.\n\n'
    '## 7A. Preserved detail\nold 7A 1.2345678\n\n'
    '## 11. Generalization\nold count 5973 and Outcome A04\n\n'
    '## 12. Figures\nold 29 unchanged\n\n'
    '## 18. Current next actions\nold v2 zip 123456\n')
METHOD_TEXT = '# Protocol v2 method statement\n\nExact old number: -0.013646; Outcome unchanged.\n'


def test_section_update_retains_old_bytes_and_all_unauthorized_sections():
    blocks = {7: 'new seven', 11: 'new eleven', 18: 'new eighteen'}
    result = d.update_agents(AGENTS_TEXT, blocks)
    assert d.update_agents(result, blocks) == result
    for unchanged in ('## 1. First\nuntouched one\n\n',
                      '## 7A. Preserved detail\nold 7A 1.2345678\n\n',
                      '## 12. Figures\nold 29 unchanged\n\n',
                      '\nOriginal v2 0.098336 and Outcome FAIL.\n\n',
                      'old count 5973 and Outcome A04\n\n', 'old v2 zip 123456\n'):
        assert unchanged in result
    assert result.count('pre-correction — original section') == 3
    with pytest.raises(ValueError, match='Only the three'):
        d.update_agents(AGENTS_TEXT, {7: 'not enough'})


def test_method_append_is_idempotent_and_preserves_original_numeric_record():
    result = d.update_method(METHOD_TEXT, '## v2.1\nnew current evidence')
    assert METHOD_TEXT in result
    assert d.update_method(result, '## v2.1\nnew current evidence') == result
    updated = d.update_method(result, '## v2.1\nnew current evidence and figure hash')
    assert METHOD_TEXT in updated
    assert updated.count('P13_METHOD_PRE_CORRECTION_BEGIN') == 1
    assert updated.count('figure hash') == 1


def test_original_crlf_bytes_remain_in_preserved_sections():
    original = AGENTS_TEXT.replace('\n', '\r\n')
    result = d.update_agents(original, {7: 'seven', 11: 'eleven', 18: 'eighteen'})
    assert 'Original v2 0.098336 and Outcome FAIL.\r\n\r\n' in result
    assert '## 7A. Preserved detail\r\nold 7A 1.2345678\r\n\r\n' in result
    method = METHOD_TEXT.replace('\n', '\r\n')
    assert method in d.update_method(method, 'new v2.1')


def test_change_tables_project_sealed_tokens_and_keep_unavailable_pairs():
    base = dict(evaluator_version='v3', dataset_id='BY2', method_id='A04',
                degradation_id='', duration_s='', registered_case_count='1',
                paired_finite_count='1', availability='AVAILABLE',
                v2_value='0.10000000000000001', v21_value='0.20000000000000004',
                v21_minus_v2='0.10000000000000003')
    case = dict(base, scope='CASE', statistic='value', metric_name='horizontal_rmse_m',
                family_or_case='C00_clean_normal', _csv_row='42')
    outage = dict(base, scope='DURATION', statistic='median', degradation_id='D62',
                  duration_s='20', metric_name='outage_end_horizontal_error_m',
                  v2_value='', v21_value='', v21_minus_v2='', paired_finite_count='0',
                  availability='UNAVAILABLE', _csv_row='84')
    excluded = dict(case, evaluator_version='v2', v2_value='EXCLUDED_PARALLEL_TOKEN')
    injected_case = dict(case, family_or_case='D05_injected_case', v2_value='EXCLUDED_INJECTED_CASE_TOKEN')
    other_sequence = dict(case, dataset_id='BY2H', family_or_case='BY2H_natural', v2_value='INCLUDED_BY2H_TOKEN')
    text = d._changes([case, outage, excluded, injected_case, other_sequence])
    for token in ('0.10000000000000001', '0.20000000000000004',
                  '0.10000000000000003', 'C00_clean_normal', 'UNAVAILABLE',
                  'outage_end_horizontal_error_m', '| 42 |', '| 84 |'):
        assert token in text
    assert 'EXCLUDED_PARALLEL_TOKEN' not in text
    assert 'EXCLUDED_INJECTED_CASE_TOKEN' not in text
    assert 'INCLUDED_BY2H_TOKEN' in text


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    fields = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode()


def fixture(tmp_path):
    code, clean, handoff = (tmp_path / name for name in ('code', 'clean', 'handoff'))
    for path in (code, clean, handoff):
        path.mkdir()
    (code / 'AGENTS.md').write_text(AGENTS_TEXT)
    method = code / d.METHOD; method.parent.mkdir(parents=True); method.write_text(METHOD_TEXT)
    output = clean / '20_FINALIZE'; output.mkdir()
    pins = {}
    def put(role, value, path=None):
        path = path or (output / (role + ('.csv' if role in d.CSV_ROLES else '.json')))
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = value if isinstance(value, bytes) else csv_bytes(value) if role in d.CSV_ROLES else json.dumps(value).encode()
        path.write_bytes(payload)
        pins[role] = {'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest()}
        return path
    put('package', b'synthetic-only ZIP identity fixture', handoff / 'c541_v21_handoff.zip')
    put('contract', yaml.safe_dump({'sensor_model_requested': {
        'go2_hv': {'formula': 'registered formula'},
        'go2_rp': {'frozen_static_pitch_residual_means_deg': [2.028821, 2.212328, -4.296193],
                   'corrected_static_pitch_residual_means_deg': [-.444112, -.420844, -.412029]},
        'dual_yaw': {'evidence': 'BY2 proxy; BY2O check.'}},
        'unchanged_model_and_p12_limits': {'gyro_scale': {'z_slopes': [.991971, .944907, 1.036122],
                                                       'correction_applied': False},
                                         'arw_deg_sqrt_h': [.985]*3, 'gbstd_deg_h': [9.38]*3}}).encode(),
        code / 'configs/paper_rebuild/SENSOR_MODEL_V21_CONTRACT.yaml')
    put('main', dict(status='PASS', native_terminals=5880, evaluator_terminals=11760, verified_receipts=5880, pending=0))
    put('downstream', dict(status='PASS', native_calls=21, evaluator_terminals=42, verified_archives=21,
                          archive={'pending_run_ids': []}, grid_origin_gate_status='PASS'))
    put('binary_freeze', dict(old_binary_preserved=True, scheme_c_threshold_changed=False,
                             old_executable={'sha256': 'a'*64}, new_executable={'sha256': 'b'*64}))
    put('bridge', dict(status='PASS', passed_comparisons=44, binary_freeze_sha256=pins['binary_freeze']['sha256']))
    put('f01', dict(status='PASS', sample_count=50, passed_run_count=50, passed_file_count=350,
                    audit_outputs_replace_formal_F01=False))
    for dataset in d.DATASETS:
        token = dict(status='PASS', all_non_yaw_std_tokens_equal=True, nominal_yaw_std_all_2_933193=True)
        put('provider_' + dataset, dict(status='PASS_HV_RP_REPRODUCTION', passed=True,
            maximum_absolute_difference=1.1102230246251565e-16, compared_numeric_statistics=500,
            unchanged_IMU_RD={'IMU': {'passed': True}, 'RD': {'passed': True}},
            GNSS15=token, GNSS18=token, HV_final_scaled={'sigma_HV_mps': .13}))
    for version in ('v3', 'v2'):
        put('sequence_' + version, [dict(dataset_id=dataset, method_id=method, evaluator_version=version,
            case_id='C00_clean_normal' if dataset == 'BY2' else dataset + '_natural',
            evaluation_status='COMPLETED', horizontal_rmse_m='0.1234500000000001',
            position_3d_rmse_m='0.2', up_rmse_m='.03', yaw_rmse_deg='1.4', roll_rmse_deg='.3', pitch_rmse_deg='.4')
            for dataset in d.DATASETS for method in ('F01', *d.PROFILES)])
    comparisons = []
    for version in ('v3', 'v2'):
        for method in d.PROFILES:
            for dataset in d.DATASETS:
                for metric in ('horizontal_rmse_m', 'position_3d_rmse_m', 'up_rmse_m', 'yaw_rmse_deg', 'roll_rmse_deg', 'pitch_rmse_deg'):
                    comparisons.append(dict(evaluator_version=version, dataset_id=dataset, method_id=method,
                        scope='CASE', statistic='value', metric_name=metric,
                        family_or_case='C00_clean_normal' if dataset == 'BY2' else dataset+'_natural'))
            for degradation in ('D05', 'D06', 'D61', 'D62'):
                for metric in ('horizontal_rmse_m', 'up_rmse_m', 'yaw_rmse_deg'):
                    comparisons.append(dict(evaluator_version=version, dataset_id='BY2', method_id=method,
                        scope='DEGRADATION', statistic='median', metric_name=metric, degradation_id=degradation))
            for degradation, duration in (('D61', 10), ('D61', 20), ('D61', 30), ('D62', 10), ('D62', 20)):
                comparisons.append(dict(evaluator_version=version, dataset_id='BY2', method_id=method,
                    scope='DURATION', statistic='median', metric_name='outage_end_horizontal_error_m',
                    degradation_id=degradation, duration_s=duration))
    put('comparison', comparisons)
    put('hypotheses', [dict(evaluator_version=version, method_id=method, hypothesis=hypothesis,
                            decision='INCOMPLETE' if hypothesis == 'H7' else 'REPORTED_NON_DIRECTIONAL')
                       for version in ('v3', 'v2') for method in d.PROFILES for hypothesis in d.HYPOTHESES])
    put('consistency', [dict(evaluator_version=version, dataset_id=dataset, method_id=method,
                            v2_value='UNAVAILABLE', v21_value='1.5', v21_minus_v2='', decision='INCOMPLETE')
                       for version in ('v3', 'v2') for dataset in d.DATASETS for method in d.PROFILES])
    put('failures', [dict(evaluator_version=version, domain=domain, case_family=domain.lower(), method_id=method,
                          registered_cases=n, v2_completed=n-1, v21_completed=n,
                          v2_ALL_YAW_REJECTED=1, v21_ALL_YAW_REJECTED=0, v2_missing=0, v21_missing=0)
                     for version in ('v3', 'v2') for domain, n in (('CORE', 541), ('ADDENDUM', 45), ('SEQUENCE', 2))
                     for method in d.PROFILES])
    aggregate_status = 'PASS_V21_AGGREGATION_WITH_EXPLICIT_HYPOTHESIS_AVAILABILITY'
    put('aggregate_summary', dict(status=aggregate_status, decision_rule_and_Outcome_changed=False))
    put('aggregate_seal', dict(status='SEALED', files_sha256={
        Path(pins[role]['path']).relative_to(output).as_posix(): pins[role]['sha256']
        for role in d.CSV_ROLES | {'aggregate_summary'}}))
    put('finalize', dict(status='PASS_FINALIZED_V21_HANDOFF', aggregate_status=aggregate_status,
        outcome_changed=False, new_outcome_created=False, output_root=str(output), code_commit='c'*40,
        closure=dict(status='PASS', main_native=5880, main_evaluations=11760, downstream_native=21, downstream_evaluations=42),
        package=dict(passed=True, sha256=pins['package']['sha256'], identity_probe={'counts': d.COUNTS})))
    return code, dict(clean_root=clean, handoff_root=handoff, pins=pins,
                     data_package_sha256=pins['package']['sha256'], code_commit='d'*40)


def test_prepare_reads_sealed_tokens_but_does_not_write_docs(tmp_path):
    code, kwargs = fixture(tmp_path)
    prepared = d.prepare_documents(code, **kwargs)
    assert (code / d.AGENTS).read_text() == AGENTS_TEXT
    assert not (code / d.REPORT).exists()
    assert set(prepared['documents']) == {d.AGENTS, d.METHOD, d.REPORT}
    assert '0.1234500000000001' in prepared['documents'][d.AGENTS]
    assert 'INCOMPLETE' in prepared['documents'][d.REPORT]
    assert '图形交付：PENDING' in prepared['documents'][d.REPORT]
    assert '/tmp/' not in prepared['documents'][d.REPORT]
    result = d.apply_documents(code, prepared)
    assert result['status'] == 'APPLIED_VALIDATED_P13_DOCUMENTS'
    second = d.prepare_documents(code, **kwargs)
    assert second['documents'] == prepared['documents']
    assert d.apply_documents(code, second)['changed'] == []


def test_closure_and_package_gates_cannot_publish_partial_completion(tmp_path):
    code, kwargs = fixture(tmp_path)
    roots = {'<CODE_ROOT>': code, '<CLEAN_ROOT>': kwargs['clean_root'], '<HANDOFF_ROOT>': kwargs['handoff_root']}
    evidence = d.load_evidence(kwargs['pins'], roots)
    for role, key, value in [('finalize', 'status', 'PASS_FINALIZED_TABLES_PENDING_PACKAGE'),
                             ('main', 'pending', 1), ('downstream', 'verified_archives', 20),
                             ('f01', 'passed_file_count', 349)]:
        changed = copy.deepcopy(evidence); changed['objects'][role][key] = value
        with pytest.raises(ValueError):
            d.validate_evidence(changed, data_package_sha256=kwargs['data_package_sha256'], code_commit=kwargs['code_commit'])
    with pytest.raises(ValueError, match='Package byte identity'):
        d.validate_evidence(evidence, data_package_sha256='f'*64, code_commit=kwargs['code_commit'])


def test_hash_changes_and_unsealed_table_are_rejected(tmp_path):
    code, kwargs = fixture(tmp_path)
    table = Path(kwargs['pins']['sequence_v3']['path'])
    table.write_text(table.read_text().replace('0.1234500000000001', '0.1'))
    with pytest.raises(ValueError, match='hash differs'):
        d.prepare_documents(code, **kwargs)
    kwargs['pins']['sequence_v3']['sha256'] = hashlib.sha256(table.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='aggregate seal'):
        d.prepare_documents(code, **kwargs)


def test_apply_preflights_all_files_before_any_document_write(tmp_path):
    code, kwargs = fixture(tmp_path)
    prepared = d.prepare_documents(code, **kwargs)
    (code / d.METHOD).write_text(METHOD_TEXT + '\nUser edit preserved.\n')
    with pytest.raises(ValueError, match='changed after preparation'):
        d.apply_documents(code, prepared)
    assert (code / d.AGENTS).read_text() == AGENTS_TEXT
    assert not (code / d.REPORT).exists()


def test_figures_cannot_be_claimed_complete_without_all_pins(tmp_path):
    code, kwargs = fixture(tmp_path)
    with pytest.raises(ValueError, match='Figure completion requires'):
        d.prepare_documents(code, require_figures=True, **kwargs)


@pytest.mark.parametrize('status', ['FAIL', 'UNAVAILABLE'])
def test_grid_diagnostic_does_not_add_a_fifth_scientific_stop(tmp_path, status):
    code, kwargs = fixture(tmp_path)
    pin = kwargs['pins']['downstream']; path = Path(pin['path'])
    payload = json.loads(path.read_text()); payload['grid_origin_gate_status'] = status
    path.write_text(json.dumps(payload)); pin['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    prepared = d.prepare_documents(code, **kwargs)
    assert '九格原点诊断 `' + status + '`' in prepared['documents'][d.REPORT]
    assert '九格原点门 PASS' not in prepared['documents'][d.REPORT]


def test_later_closed_figure_delivery_updates_only_owned_markers(tmp_path):
    code, kwargs = fixture(tmp_path)
    d.apply_documents(code, d.prepare_documents(code, **kwargs))
    before = (code / d.AGENTS).read_text()
    def add(role, path, value):
        payload = value if isinstance(value, bytes) else json.dumps(value).encode()
        path.write_bytes(payload)
        kwargs['pins'][role] = {'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest()}
    add('figure_package', kwargs['handoff_root']/'figures_v21_handoff.zip', b'synthetic figure ZIP')
    add('figure_validation', kwargs['handoff_root']/'figures_v21_handoff.validation.json',
        dict(status='PASS', figure_count=28, export_count=84, sha256=kwargs['pins']['figure_package']['sha256']))
    add('figure_render', kwargs['clean_root']/'RENDER_MANIFEST.json', dict(status='COMPLETE',
        protocol_version='v2.1', rendered_count=28, requested_figure_count=28, visual_review_status='PASS',
        failures=[], package_sha256=kwargs['data_package_sha256']))
    prepared = d.prepare_documents(code, require_figures=True, **kwargs)
    assert d.FIGURES in prepared['documents']
    assert '图形交付：PENDING' not in prepared['documents'][d.REPORT]
    assert '28 图、84 PNG/PDF/SVG' in prepared['documents'][d.REPORT]
    assert METHOD_TEXT in prepared['documents'][d.METHOD]
    assert prepared['documents'][d.AGENTS].count('P13_PRE_CORRECTION_SECTION_7_BEGIN') == 1
    assert 'old 7A 1.2345678' in before and 'old 7A 1.2345678' in prepared['documents'][d.AGENTS]
    add('figure_validation', kwargs['handoff_root']/'figures_v21_handoff.validation.json',
        dict(status='PASS', figure_count=28, export_count=83, sha256=kwargs['pins']['figure_package']['sha256']))
    with pytest.raises(ValueError, match='Figure delivery'):
        d.prepare_documents(code, require_figures=True, **kwargs)
