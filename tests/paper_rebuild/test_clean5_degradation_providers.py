"""Synthetic fixture checks; no real providers, solver or evaluator execution."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean5_degradation.providers import (
    DegradationProviderError, INPUT_ROLES, build_base, generate_case,
)
from legsa_gins.paper_rebuild.canonical541 import provider_generator as canonical


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def csv_file(path, rows, fields=None):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path/'synthetic_inputs'
    root.mkdir()
    times = np.arange(330)/5+66
    gnss = []
    a1 = []
    for i, time in enumerate(times):
        yaw_valid = i % 5 == 0
        gnss.append(' '.join([f'{time:.9f}', '39.9848000000', '116.3431000000', '41.800000',
                             '.014', '.014', '.02', '.3', '.1', '0', '.05', '.05', '.05',
                             '1.000000' if yaw_valid else '0.000000', '1.500000', '1', '1', str(int(yaw_valid))])+'\n')
        if yaw_valid:
            a1.append({'time': str(time), 'source_timestamp': str(1000+time-.00014),
                       'body_yaw_ned_deg': '1', 'baseline_n_m': '.006108342',
                       'baseline_e_m': '-.349946693', 'baseline_d_m': '.001',
                       'baseline_length_m': '.350001429', 'physical_in_band': 'True',
                       'source_status': 'active', 'gnss_order': 'GNSS2-GNSS1',
                       'lateral_to_body_offset_deg': '90.0', 'wrap_safe_residual': 'True',
                       'trace_sign_or_offset_selection': 'False'})
    imu = root/'synthetic.imu'
    imu.write_text('66 0 0 0 0 0 0\n')
    gnsspath = root/'synthetic.gnss'
    gnsspath.write_text(''.join(gnss))
    raw = [{'time': f'{t:.9f}', 'vn': '.2', 've': '.1', 'vd': '0', 'std_vn': '.3',
            'std_ve': '.3', 'std_vd': '.3', 'valid': '1', 'provider_status': 'active'} for t in times]
    rp = [{'time': f'{t:.9f}', 'roll_rad': '.01', 'pitch_rad': '.02', 'std_roll_rad': '.03',
           'std_pitch_rad': '.03', 'valid': '1', 'source_status': 'active'} for t in times]
    hv = [{'time': f'{t:.9f}', 'vn': '.2', 've': '.1', 'vd': '0', 'std_vn': '1.5',
           'std_ve': '1.5', 'std_vd': '999', 'update_flag': 'True', 'source_status': 'active'} for t in times]
    metadata = [{'time': f'{t:.9f}', 'source': 'synthetic_fixture', 'trace_used': 'False'} for t in times]
    roles = dict(zip(INPUT_ROLES, [pin(imu), pin(gnsspath),
                pin(csv_file(root/'raw.csv', raw)), pin(csv_file(root/'rp.csv', rp)),
                pin(csv_file(root/'hv.csv', hv))]))
    auxiliary = {'dual_yaw_audit': pin(csv_file(root/'a1.csv', a1)),
                 'source_quality_metadata': pin(csv_file(root/'quality.csv', metadata))}
    base = build_base(roles, auxiliary_roles=auxiliary, base_time_s=1000,
                      data_mode='synthetic_test', synthetic_data_used=True)
    return base, roles, auxiliary


def case(type_id):
    clean = type_id == 'CLEAN'
    return {'case_id': 'C00_clean_normal' if clean else type_id+'_seed_00',
            'degradation_type_id': type_id, 'seed_index': 'none' if clean else 'seed_00',
            'seed_value': '' if clean else 260306001, 'anchor_time_s': 90.0}


def mapping(tmp_path, type_id, base, intervals=None):
    source = tmp_path/('synthetic_evidence_'+type_id)
    source.mkdir()
    c = case(type_id)
    manifest = source/'case.json'
    frozen_base = base.bundle.clone()
    for role in ('gnss_position', 'receiver_velocity'):
        frozen_base.tables[role].rows = frozen_base.tables[role].rows[::5]
    frozen_after, components, _ = canonical.apply_degradation(frozen_base, c)
    manifest.write_text(json.dumps({'case_id': c['case_id'], 'components': components}))
    ledger_rows = canonical.perturbation_ledger_rows(frozen_base, frozen_after, type_id)
    ledger = csv_file(source/'ledger.csv', ledger_rows, ['source', 'row_index', 'base_time', 'generated_time', 'changed_fields'])
    index_pins = []
    for name, bundle in [('before', frozen_base), ('after', frozen_after)]:
        folder = source/name
        folder.mkdir()
        entries = []
        for role, table in bundle.tables.items():
            target = folder/(role+'.csv')
            target.write_bytes(table.canonical_bytes())
            entries.append({'source': role, 'relative_path': target.name, 'storage_mode': 'materialized',
                            'sha256': pin(target)['sha256'], 'semantic_sha256': table.sha256()})
        index = folder/'provider_index.json'
        index.write_text(json.dumps({'case_id': 'C00_clean_normal' if name == 'before' else c['case_id'],
                                     'provider_files': entries}))
        index_pins.append(pin(index))
    return {'degradation_type_id': type_id, 'status': 'CLEAN_REFERENCE' if type_id == 'CLEAN' else 'TRANSFERABLE',
            'mode': 'synthetic_test', 'intervals': intervals or [],
            'frozen_case_manifest': pin(manifest), 'frozen_perturbation_ledger': pin(ledger),
            'frozen_base_provider_index': index_pins[0], 'frozen_case_provider_index': index_pins[1],
            'frozen_clean_root': str(source), 'frozen_components': components,
            'equivalence_rule': 'same registered laws, time support, source scope and deterministic amplitudes'}


def run_case(tmp_path, inputs, type_id, intervals=None):
    return generate_case(inputs[0], case(type_id), mapping(tmp_path, type_id, inputs[0], intervals), tmp_path/'outputs')


def array(result):
    return np.loadtxt(result['providers']['gnsspath']['path'], ndmin=2)


def test_c00_keeps_all_five_original_bytes_and_test_data_label(tmp_path, inputs):
    result = run_case(tmp_path, inputs, 'CLEAN')
    assert result['data_mode'] == 'synthetic_test'
    assert result['synthetic_data_used'] is True
    assert result['controlled_degradation_applied'] is False
    assert result['runtime_contract']['C00_solver_input_byte_identity'] is True
    assert set(result['providers']) == set(INPUT_ROLES)
    for role in INPUT_ROLES:
        assert result['providers'][role]['path'] == inputs[1][role]['path']
        assert result['providers'][role]['sha256'] == inputs[1][role]['sha256']
    assert not list(Path(result['case_root']).glob('*.gnss'))


def test_yaw_noise_only_changes_effective_a1_and_preserves_std(tmp_path, inputs):
    result = run_case(tmp_path, inputs, 'D32')
    before, after = np.asarray(inputs[0].gnss_tokens, float), array(result)
    valid = before[:, 17] == 1
    assert valid.sum() == 66 and len(after) == 330
    assert np.array_equal(before[~valid], after[~valid])
    assert np.array_equal(before[:, 14:], after[:, 14:])
    assert np.array_equal(before[:, :13], after[:, :13])
    assert np.all(before[valid, 13] != after[valid, 13])
    assert result['components'][0]['affected_epoch_count'] == 66


def test_missing_sources_use_independent_validity_bits_without_deletion(tmp_path, inputs):
    result = run_case(tmp_path, inputs, 'D06')
    before, after = np.asarray(inputs[0].gnss_tokens, float), array(result)
    window = (after[:, 0] >= 80) & (after[:, 0] < 100)
    assert len(after) == len(before)
    assert np.array_equal(before[:, :15], after[:, :15])
    assert np.all(after[window, 15:] == 0)
    assert np.array_equal(before[~window], after[~window])
    assert result['runtime_contract']['delete_row_control'].startswith('NOT_APPLICABLE')


def test_d22_four_frozen_epochs_become_four_seconds_at_five_hz(tmp_path, inputs):
    intervals = [{'start_s': 80.205852, 'end_s': 84.205852, 'source_ids': ['gnss_position'], 'frozen_affected_count': 4}]
    result = run_case(tmp_path, inputs, 'D22', intervals)
    before, after = np.asarray(inputs[0].gnss_tokens, float), array(result)
    changed = np.any(before[:, 1:4] != after[:, 1:4], axis=1)
    assert changed.sum() == 20
    assert np.array_equal(before[~changed], after[~changed])
    assert np.array_equal(before[:, 4:], after[:, 4:])
    north = np.deg2rad(after[changed, 1]-before[changed, 1])*6361800
    east = np.deg2rad(after[changed, 2]-before[changed, 2])*4894000
    assert np.allclose(np.hypot(north, east), 8, atol=.03)
    assert np.allclose(abs(after[changed, 3]-before[changed, 3]), 4, atol=1e-4)
    assert result['components'][0]['details']['horizontal_m'] == 8


def test_d39_keeps_frozen_seconds_and_only_disables_a1(tmp_path, inputs):
    intervals = [{'start_s': start, 'end_s': end, 'source_ids': ['dual_yaw'], 'frozen_affected_count': count}
                 for start, end, count in [(72.204517, 74.204517, 2), (82.204872, 84.204872, 2), (99.204539, 102.204539, 3)]]
    result = run_case(tmp_path, inputs, 'D39', intervals)
    before, after = np.asarray(inputs[0].gnss_tokens, float), array(result)
    assert np.array_equal(before[:, :17], after[:, :17])
    assert int(before[:, 17].sum()-after[:, 17].sum()) == 7
    assert np.array_equal(before[before[:, 17] == 0], after[before[:, 17] == 0])


def test_d57_union_preserves_all_independently_shifted_valid_events(tmp_path, inputs):
    result = run_case(tmp_path, inputs, 'D57')
    after = array(result)
    assert len(after) == 330+330+66
    assert np.all(np.diff(after[:, 0]) > 0)
    assert np.sum(after[:, 15:18], axis=0).tolist() == [330, 330, 66]
    assert not np.allclose(np.diff(after[:, 0]), .2)
    for source in ('gnss_position', 'receiver_velocity', 'dual_yaw', 'raw_doppler', 'go2_rp', 'go2_hv'):
        diff = result['diff_summary']['new_chain'][source]
        assert diff['affected_row_count'] == diff['row_count_before']
        assert diff['row_count_before'] == diff['row_count_after']
        assert diff['time_and_row_identity_preserved'] is False
    assert result['runtime_contract']['faulted_timing_union'] is True


@pytest.mark.parametrize('type_id', ['D29', 'D40', 'D55', 'D56'])
def test_metadata_only_cases_preserve_all_solver_inputs(tmp_path, inputs, type_id):
    result = run_case(tmp_path, inputs, type_id)
    assert result['semantics']['no_active_path'] is True
    assert result['audit_payloads']
    for role in INPUT_ROLES:
        assert result['providers'][role]['sha256'] == inputs[1][role]['sha256']
        assert result['providers'][role]['storage_mode'] == 'pinned_unchanged_pointer'


def test_a1_value_mismatch_fails_before_generation(inputs):
    _, roles, auxiliary = inputs
    path = Path(auxiliary['dual_yaw_audit']['path'])
    rows = list(csv.DictReader(path.open()))
    rows[0]['body_yaw_ned_deg'] = '2'
    csv_file(path, rows)
    auxiliary['dual_yaw_audit'] = pin(path)
    with pytest.raises(DegradationProviderError, match='A1 original yaw mismatch'):
        build_base(roles, auxiliary_roles=auxiliary, base_time_s=1000,
                   data_mode='synthetic_test', synthetic_data_used=True)


def test_synthetic_cannot_be_marked_real(inputs):
    _, roles, auxiliary = inputs
    with pytest.raises(DegradationProviderError, match='Synthetic inputs cannot'):
        build_base(roles, auxiliary_roles=auxiliary, base_time_s=1000, synthetic_data_used=True)


def test_forbidden_input_extension_rejected_without_opening(inputs):
    _, roles, auxiliary = inputs
    roles = dict(roles)
    roles['imupath'] = {'path': '/synthetic_fixture/input.bag', 'sha256': '0'*64}
    with pytest.raises(DegradationProviderError, match='Forbidden provider input'):
        build_base(roles, auxiliary_roles=auxiliary, base_time_s=1000,
                   data_mode='synthetic_test', synthetic_data_used=True)


def test_no_overwrite_and_hash_drift_fail_closed(tmp_path, inputs):
    contract = mapping(tmp_path, 'D32', inputs[0])
    result = generate_case(inputs[0], case('D32'), contract, tmp_path/'outputs')
    digest = pin(Path(result['case_root'])/'DEGRADATION_PROVIDER_MANIFEST.json')['sha256']
    with pytest.raises(DegradationProviderError, match='already exists'):
        generate_case(inputs[0], case('D32'), contract, tmp_path/'outputs')
    assert pin(Path(result['case_root'])/'DEGRADATION_PROVIDER_MANIFEST.json')['sha256'] == digest
    Path(inputs[1]['imupath']['path']).write_text('changed fixture\n')
    with pytest.raises(DegradationProviderError, match='hash mismatch'):
        generate_case(inputs[0], case('D32'), contract, tmp_path/'other_outputs')
    assert not (tmp_path/'other_outputs').exists()


def test_not_transferable_fails_before_writing(tmp_path, inputs):
    contract = mapping(tmp_path, 'D57', inputs[0])
    contract['status'] = 'NOT_TRANSFERABLE'
    with pytest.raises(DegradationProviderError, match='not admitted'):
        generate_case(inputs[0], case('D57'), contract, tmp_path/'outputs')
    assert not (tmp_path/'outputs').exists()


def test_frozen_manifest_pointer_is_resolved_only_through_pinned_c00(tmp_path, inputs):
    contract = mapping(tmp_path, 'D32', inputs[0])
    index_path = Path(contract['frozen_case_provider_index']['path'])
    index = json.loads(index_path.read_text())
    entry = next(row for row in index['provider_files'] if row['source'] == 'raw_doppler')
    entry.update(storage_mode='manifest_pointer', pointer_case_id='C00_clean_normal',
                 pointer_source='raw_doppler', pointer_target='', sha256='')
    index_path.write_text(json.dumps(index))
    contract['frozen_case_provider_index'] = pin(index_path)
    result = generate_case(inputs[0], case('D32'), contract, tmp_path/'outputs')
    frozen = result['diff_summary']['frozen_same_case']
    assert frozen['empirical_amplitude_status'] == 'AVAILABLE_FROM_PINNED_SOURCE_TABLES'
    assert frozen['source_diff']['raw_doppler']['affected_row_count'] == 0
    assert frozen['source_member_pins']['raw_doppler']['before'] == frozen['source_member_pins']['raw_doppler']['after']


def test_frozen_member_relative_escape_fails_before_output(tmp_path, inputs):
    contract = mapping(tmp_path, 'D32', inputs[0])
    index_path = Path(contract['frozen_case_provider_index']['path'])
    index = json.loads(index_path.read_text())
    index['provider_files'][0]['relative_path'] = '../before/gnss_position.csv'
    index_path.write_text(json.dumps(index))
    contract['frozen_case_provider_index'] = pin(index_path)
    with pytest.raises(DegradationProviderError, match='relative path escapes'):
        generate_case(inputs[0], case('D32'), contract, tmp_path/'outputs')
    assert not (tmp_path/'outputs').exists()


def test_semantic_gate_rejects_unregistered_component_law(tmp_path, inputs):
    contract = mapping(tmp_path, 'D32', inputs[0])
    contract['frozen_components'][0]['details']['sigma_deg'] = 2.0
    with pytest.raises(DegradationProviderError, match='frozen_component_registration'):
        generate_case(inputs[0], case('D32'), contract, tmp_path/'outputs')
    assert not (tmp_path/'outputs').exists()


def test_semantic_gate_rejects_undeclared_field_change(tmp_path, inputs, monkeypatch):
    contract = mapping(tmp_path, 'D32', inputs[0])
    original = canonical.apply_degradation

    def wrong_field(base, case_row):
        bundle, components, semantics = original(base, case_row)
        bundle.tables['dual_yaw'].rows[0]['yaw_std_deg'] = '9'
        return bundle, components, semantics

    monkeypatch.setattr(canonical, 'apply_degradation', wrong_field)
    with pytest.raises(DegradationProviderError, match='changed_field_scope_dual_yaw'):
        generate_case(inputs[0], case('D32'), contract, tmp_path/'outputs')
    assert not (tmp_path/'outputs').exists()


@pytest.mark.parametrize('type_id', [f'D{i:02d}' for i in range(1, 61)])
def test_all_sixty_frozen_handlers_accept_sparse_a1_gnss18(tmp_path, inputs, type_id):
    intervals = None
    if type_id == 'D22':
        intervals = [{'start_s': 80.205852, 'end_s': 84.205852, 'source_ids': ['gnss_position'], 'frozen_affected_count': 4}]
    elif type_id == 'D39':
        intervals = [{'start_s': start, 'end_s': end, 'source_ids': ['dual_yaw'], 'frozen_affected_count': count}
                     for start, end, count in [(72.204517, 74.204517, 2), (82.204872, 84.204872, 2), (99.204539, 102.204539, 3)]]
    result = run_case(tmp_path, inputs, type_id, intervals)
    output = array(result)
    assert result['data_mode'] == 'synthetic_test'
    assert result['semantic_equivalence']['passed'] is True
    assert result['controlled_degradation_applied'] is True
    assert output.shape[1] == 18 and np.isfinite(output).all()
    assert np.isin(output[:, 15:], (0, 1)).all()
    assert np.all(np.diff(output[:, 0]) > 0)
    if type_id != 'D57':
        before = np.asarray(inputs[0].gnss_tokens, float)
        assert np.array_equal(before[:, 0], output[:, 0])
        assert np.array_equal(before[before[:, 17] == 0, 13:15], output[before[:, 17] == 0, 13:15])
    assert result['diff_summary']['frozen_same_case']['empirical_amplitude_status'] == 'AVAILABLE_FROM_PINNED_SOURCE_TABLES'
