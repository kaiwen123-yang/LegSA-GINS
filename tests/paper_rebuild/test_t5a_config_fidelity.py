"""Synthetic config/native-echo fidelity tests; never invoke native processes."""
from copy import deepcopy
from hashlib import sha256
import json
import math

import pytest
import yaml

from legsa_gins.paper_rebuild.hext import t5a_config_fidelity as fidelity
from legsa_gins.paper_rebuild.hext.t5a_runtime import clone_runtime_config


def echo_fixture():
    echo = {key: 0 for key in fidelity.STATIC_ECHO_KEYS}
    echo['schema_version'] = 'legsa-v23-port-core-run-manifest-v2'
    echo['actual_solver_input_paths'] = {'gnss_position_receiver_velocity_dual_yaw': '/synthetic/old.gnss',
                                         'propagation_imu': '/synthetic/unchanged.imu'}
    echo['actual_solver_input_roles'] = {'propagation_imu': 'source_backed_propagation'}
    echo['init_position_geodetic_deg_m'] = [39., 116.34312609000001, 41.]
    echo['source_caps'] = {'receiver_position': 5., 'dual_antenna_yaw': 10.}
    echo['source_aware_source_configs'] = {'receiver_position': {'enabled': True, 'lsim_enabled': True}}
    return echo


def test_hard_echo_has_all_211_static_fields_and_only_gnss_path_exception():
    assert len(fidelity.STATIC_ECHO_KEYS) == len(set(fidelity.STATIC_ECHO_KEYS)) == 211
    frozen = echo_fixture()
    new = deepcopy(frozen)
    new['actual_solver_input_paths']['gnss_position_receiver_velocity_dual_yaw'] = '/synthetic/new.gnss'
    new['position_update_count'] = 123  # Dynamic counters are deliberately outside static gate b.
    gate = fidelity.compare_effective_echo(new, frozen, expected_gnsspath='/synthetic/new.gnss')
    assert gate['passed'] and gate['static_field_count'] == 211
    assert 'NO_TOLERANCE' in gate['comparison']
    assert frozen['actual_solver_input_paths']['gnss_position_receiver_velocity_dual_yaw'] == '/synthetic/old.gnss'


@pytest.mark.parametrize('change', ['ulp', 'aux_path', 'source_cap', 'nested_flag', 'missing', 'nonfinite', 'wrong_gnss'])
def test_hard_echo_rejects_any_static_difference_without_tolerance(change):
    frozen = echo_fixture()
    new = deepcopy(frozen)
    new['actual_solver_input_paths']['gnss_position_receiver_velocity_dual_yaw'] = '/synthetic/new.gnss'
    if change == 'ulp':
        new['init_position_geodetic_deg_m'][1] = math.nextafter(frozen['init_position_geodetic_deg_m'][1], math.inf)
    elif change == 'aux_path':
        new['actual_solver_input_paths']['propagation_imu'] = '/synthetic/wrong.imu'
    elif change == 'source_cap':
        new['source_caps']['dual_antenna_yaw'] = 11.
    elif change == 'nested_flag':
        new['source_aware_source_configs']['receiver_position']['enabled'] = 1
    elif change == 'missing':
        del new['init_position_geodetic_deg_m']
    elif change == 'nonfinite':
        new['init_position_geodetic_deg_m'][0] = float('nan')
    else:
        new['actual_solver_input_paths']['gnss_position_receiver_velocity_dual_yaw'] = '/synthetic/wrong.gnss'
    with pytest.raises(RuntimeError, match='HARD_STOP_T5AR_EFFECTIVE_ECHO'):
        fidelity.compare_effective_echo(new, frozen, expected_gnsspath='/synthetic/new.gnss')


@pytest.mark.parametrize('bad', [b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'])
def test_echo_decode_is_strict(bad):
    with pytest.raises(ValueError):
        fidelity.decode_echo(bad)


def test_independent_byte_gate_catches_semantically_equal_reserialization():
    frozen = b'gnsspath: "/synthetic/old.gnss"\ninitpos: [39, 116, 41]\n# preserve comment bytes\n'
    candidate = b'gnsspath: "/synthetic/new.gnss"\ninitpos: [39,116,41]\n# preserve comment bytes\n'
    assert yaml.safe_load(frozen)['initpos'] == yaml.safe_load(candidate)['initpos']
    with pytest.raises(RuntimeError, match='CONFIG_BYTE_GATE'):
        fidelity.validate_gnsspath_only_bytes(frozen, candidate, expected_gnsspath='/synthetic/new.gnss')
    good, gate = clone_runtime_config(frozen, expected_sha256=sha256(frozen).hexdigest(), gnsspath='/synthetic/new.gnss')
    assert gate['independent_byte_gate']['passed']
    assert gate['canonical_field_hash_role'] == 'SECONDARY_ONLY'
    assert good.splitlines(keepends=True)[1:] == frozen.splitlines(keepends=True)[1:]


@pytest.mark.parametrize('candidate', [b'gnsspath: old\n', b'gnsspath: new\ngnsspath: other\n', b'gnsspath: new\r\n'])
def test_independent_byte_gate_requires_single_change_and_same_newline(candidate):
    with pytest.raises(RuntimeError, match='CONFIG_BYTE_GATE'):
        fidelity.validate_gnsspath_only_bytes(b'gnsspath: old\n', candidate)


def test_a0_reports_block_serialization_incompatibility_without_raising():
    frozen = b'gnsspath: old\ninitpos: [39,116,41]\nraw_doppler_backend_source_files: ["synthetic"]\n'
    good = fidelity.audit_flat_config(frozen)
    assert good['compatibility_passed'] and good['vector_field_count'] == 1
    block = yaml.safe_dump(yaml.safe_load(frozen)).encode()
    report = fidelity.audit_flat_config(block)
    assert report['report_only'] and not report['compatibility_passed']
    assert set(report['missing_fields']) == {'initpos', 'raw_doppler_backend_source_files'}
    assert fidelity.audit_flat_config(b'[invalid')['status'] == 'UNAVAILABLE'


def test_a0_roundtrip_tolerance_never_weakens_hard_echo_equality():
    config = b'initpos: [39, 116.34312609, 41]\n'
    frozen = echo_fixture()
    report = fidelity.audit_config_to_echo(config, frozen)
    row = next(row for row in report['rows'] if row['config_key'] == 'initpos')
    assert row['status'] == 'MATCH_WITHIN_REPORT_TOLERANCE' and not row['exact_equal']
    assert row['max_roundtrip_ulps'] == 1
    assert report['report_only'] and report['hard_gate_b_uses_no_tolerance']
    new = deepcopy(frozen)
    new['init_position_geodetic_deg_m'][1] = 116.34312609
    with pytest.raises(RuntimeError, match='EFFECTIVE_ECHO'):
        fidelity.compare_effective_echo(new, frozen, expected_gnsspath='/synthetic/old.gnss')


def test_a0_derived_covariance_converts_units_and_is_report_only():
    config = {key: [1., 2., 3.] for key in ('initposstd','initvelstd','initattstd','initbgstd','initbastd','initsgstd','initsastd')}
    scales = [1., 1., math.pi/180., math.pi/180./3600., 1e-5, 1e-6, 1e-6]
    echo = {fidelity.VECTOR_ECHO_FIELDS[key]: value for key, value in config.items()}
    echo['common_initialization_covariance_diagonal_internal'] = [(x * scale) ** 2 for scale in scales for x in (1.,2.,3.)]
    report = fidelity.audit_config_to_echo(yaml.safe_dump(config).encode(), echo)
    assert report['passed'] and report['report_only']
    row = next(row for row in report['rows'] if row['config_key'] == 'derived_initialization_covariance')
    assert row['max_abs_roundtrip_residual'] == 0.


@pytest.mark.parametrize('second_line', [b'initvel: [1, 2, 3]', b'"initvel": [4, 5, 6]'])
def test_a0_reports_duplicate_top_level_keys_with_all_line_numbers(second_line):
    payload = b'gnsspath: old\ninitvel: [1, 2, 3]\n# preserve physical line numbers\n' + second_line + b'\n'
    report = fidelity.audit_flat_config(payload)
    assert report['status'] == 'INCOMPATIBLE'
    assert report['report_only'] and not report['compatibility_passed']
    assert report['duplicate_keys'] == [{'config_key': 'initvel', 'line_numbers_one_based': [2, 4],
                                         'occurrence_count': 2}]
    duplicate = next(row for row in report['differences'] if row['status'] == 'DUPLICATE_KEY')
    assert duplicate['reason'] == 'DUPLICATE_TOP_LEVEL_KEY'
    assert duplicate['line_numbers_one_based'] == [2, 4]
    assert report['binary_invoked'] is False


def test_echo_receipt_discloses_runtime_exclusions_and_static_debug_coverage():
    frozen = echo_fixture()
    new = deepcopy(frozen)
    for key in ('raw_doppler', 'go2_prior', 'fgo'):
        frozen[key] = False
        new[key] = True
    new['position_update_count'] = 7
    gate = fidelity.compare_effective_echo(new, frozen, expected_gnsspath='/synthetic/old.gnss')
    assert set(gate['excluded_echo_fields']) == {'raw_doppler', 'go2_prior', 'fgo', 'position_update_count'}
    assert set(gate['update_derived_boolean_sources']) == {'raw_doppler', 'go2_prior', 'fgo'}
    assert 'byte gate' in gate['coverage_note']
    assert all('update_count > 0' in entry['definition'] for entry in gate['update_derived_boolean_sources'].values())
    for key in ('lsim_oim', 'multi_state_qm', 'debug_update_timeline_enabled',
                'debug_overclose_audit_enabled', 'debug_measurement_copy_guard_enabled',
                'debug_covariance_gain_enabled'):
        changed = deepcopy(new)
        changed[key] = 1
        with pytest.raises(RuntimeError, match='EFFECTIVE_ECHO'):
            fidelity.compare_effective_echo(changed, frozen, expected_gnsspath='/synthetic/old.gnss')
