"""Synthetic byte/option guards only; no real dataset or binary invocation."""
from copy import deepcopy
from hashlib import sha256
import math

import pytest

from legsa_gins.paper_rebuild.hext import t5bc_config_fidelity as f

FROZEN = (b'# synthetic fixture: preserve spaces and vectors\r\n'
          b'gnsspath: "/synthetic/frozen.gnss"\r\n'
          b'initatt: [0,  0, 90]\r\n'
          b'enable_multi_state_qm: false\r\n'
          b'enable_qa_fallback: false\r\n')
B3 = dict(dual_antenna_measurement_model='baseline3d',
          baseline3d_path='/synthetic/baseline.csv', baseline3d_length_m=.35,
          baseline3d_k_b=2.1)


def echo():
    result = {key: 0 for key in f.STATIC_ECHO_KEYS}
    result['actual_solver_input_paths'] = {f.GNSS_ROLE: '/synthetic/frozen.gnss',
                                          'propagation_imu': '/synthetic/frozen.imu'}
    result['actual_solver_input_roles'] = {'propagation_imu': 'source_backed_propagation'}
    result['source_caps'] = {'dual_antenna_yaw': 10.}
    return result


def test_identity_clone_changes_no_bytes_and_compares_211_options():
    candidate, gate = f.clone_config(FROZEN, expected_sha256=sha256(FROZEN).hexdigest())
    assert candidate == FROZEN and gate['existing_changed_line_count'] == gate['added_line_count'] == 0
    assert f.compare_effective_echo(echo(), echo())['legacy_static_field_count'] == 211


def test_scalar_clone_changes_only_gnsspath_and_preserves_crlf_vectors():
    candidate, gate = f.clone_config(FROZEN, expected_sha256=sha256(FROZEN).hexdigest(),
                                      gnsspath='/synthetic/weighted.gnss')
    assert gate['existing_changed_line_count'] == 1 and gate['added_line_count'] == 0
    assert candidate.replace(b'/synthetic/weighted.gnss', b'/synthetic/frozen.gnss') == FROZEN
    current = echo()
    current['actual_solver_input_paths'][f.GNSS_ROLE] = '/synthetic/weighted.gnss'
    assert f.compare_effective_echo(current, echo(), gnsspath='/synthetic/weighted.gnss')['passed']


def test_b3_appends_only_four_explicit_keys_and_preserves_original_prefix():
    candidate, gate = f.clone_config(FROZEN, expected_sha256=sha256(FROZEN).hexdigest(), baseline3d=B3)
    assert candidate.startswith(FROZEN)
    assert gate['added_line_count'] == 4 and gate['existing_changed_line_count'] == 0
    assert candidate[len(FROZEN):].count(b'\r\n') == 4
    current = echo()
    current.update(B3)
    current['actual_solver_input_paths'][f.B3_ROLE] = B3['baseline3d_path']
    current['actual_solver_input_roles'][f.B3_ROLE] = f.B3_PURPOSE
    assert f.compare_effective_echo(current, echo(), baseline3d=B3)['additional_model_field_count'] == 4
    current['source_caps']['dual_antenna_yaw'] = math.nextafter(10., math.inf)
    with pytest.raises(RuntimeError, match='EFFECTIVE_ECHO'):
        f.compare_effective_echo(current, echo(), baseline3d=B3)


@pytest.mark.parametrize('change', ['spacing', 'duplicate', 'foreign', 'qp', 'gnss'])
def test_independent_byte_gate_rejects_any_undeclared_edit(change):
    candidate, _ = f.clone_config(FROZEN, expected_sha256=sha256(FROZEN).hexdigest(), baseline3d=B3)
    if change == 'spacing': candidate = candidate.replace(b'[0,  0, 90]', b'[0,0,90]')
    elif change == 'duplicate': candidate += b'baseline3d_k_b: 2.1\r\n'
    elif change == 'foreign': candidate += b'yaw_res_hard_deg: 999\r\n'
    elif change == 'qp': candidate = candidate.replace(b'enable_multi_state_qm: false', b'enable_multi_state_qm: true')
    else: candidate = candidate.replace(b'frozen.gnss', b'other.gnss')
    with pytest.raises((RuntimeError, ValueError)):
        f.validate_config_bytes(FROZEN, candidate, baseline3d=B3)


@pytest.mark.parametrize('key,value', [('baseline3d_k_b', 0.), ('baseline3d_k_b', True),
    ('baseline3d_length_m', float('nan')), ('baseline3d_path', '/synthetic/a#b'),
    ('baseline3d_path', '/synthetic/a=b'), ('baseline3d_path', '/synthetic/a,b')])
def test_model_values_must_roundtrip_and_never_get_silent_defaults(key, value):
    model = {**B3, key: value}
    with pytest.raises(ValueError):
        f.clone_config(FROZEN, expected_sha256=sha256(FROZEN).hexdigest(), baseline3d=model)


def test_hash_and_model_activation_are_hard_guards():
    with pytest.raises(RuntimeError, match='CONFIG_HASH'):
        f.clone_config(FROZEN, expected_sha256='0' * 64)
    candidate = echo()
    candidate['dual_antenna_measurement_model'] = 'baseline3d'
    with pytest.raises(RuntimeError, match='EFFECTIVE_ECHO'):
        f.compare_effective_echo(candidate, echo())


def test_missing_static_echo_field_is_never_assumed_equal():
    candidate = echo()
    del candidate['yaw_std_min_deg']
    with pytest.raises(RuntimeError, match='yaw_std_min_deg'):
        f.compare_effective_echo(candidate, echo())


def test_b3_changes_one_gnss_line_and_four_keys_with_both_echo_roles():
    path = '/synthetic/B3/scalar_disabled.gnss'
    candidate, gate = f.clone_config(FROZEN, expected_sha256=sha256(FROZEN).hexdigest(),
                                      gnsspath=path, baseline3d=B3)
    assert gate['existing_changed_line_count'] == 1 and gate['added_line_count'] == 4
    assert candidate.split(b'dual_antenna_measurement_model:')[0].replace(path.encode(), b'/synthetic/frozen.gnss') == FROZEN
    current = echo(); current.update(B3)
    current['actual_solver_input_paths'].update({f.GNSS_ROLE: path, f.B3_ROLE: B3['baseline3d_path']})
    current['actual_solver_input_roles'][f.B3_ROLE] = f.B3_PURPOSE
    assert f.compare_effective_echo(current, echo(), gnsspath=path, baseline3d=B3)['passed']


def test_d37_derived_echo_requires_exactly_five_metadata_path_lines():
    donor = FROZEN + b'case_id: D36_seed_00\r\nrun_id: RUN_03480\r\nrun_label: D36_F04\r\noutputpath: /old/D36\r\n'
    target = donor.replace(b'D36', b'D37').replace(b'RUN_03480', b'RUN_D37').replace(b'frozen.gnss', b'D37.gnss')
    donor_echo = echo()
    donor_echo.update(case_id='D36_seed_00', run_id='RUN_03480', run_label='D36_F04')
    derived, receipt = f.derive_expected_echo_from_witness(target, donor, donor_echo, changed_keys=f.WITNESS_CHANGED_KEYS)
    assert receipt['status'] == 'DERIVED_EXPECTED_OPTIONS_FROM_BYTE_IDENTICAL_CONFIG'
    assert derived['case_id'] == 'D37_seed_00' and derived['run_id'] == 'RUN_D37'
    assert derived['actual_solver_input_paths'][f.GNSS_ROLE] == '/synthetic/D37.gnss'
    assert donor_echo['case_id'] == 'D36_seed_00'
    with pytest.raises(RuntimeError, match='NON_METADATA_BYTES'):
        f.derive_expected_echo_from_witness(target.replace(b'[0,  0, 90]', b'[0, 0, 90]'), donor, donor_echo,
                                            changed_keys=f.WITNESS_CHANGED_KEYS)
