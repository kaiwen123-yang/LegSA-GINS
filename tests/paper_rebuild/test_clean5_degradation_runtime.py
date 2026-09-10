"""Synthetic scheduling/counter tests; no solver, evaluator or real-data outputs."""
import csv

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean5_degradation import runtime


SOURCES = ('receiver_position', 'receiver_velocity', 'raw_doppler_velocity',
           'go2_attitude_roll_pitch', 'go2_horizontal_velocity', 'dual_antenna_yaw')


def config(**updates):
    value = {
        'starttime': 0.0, 'endtime': 4.0,
        'enable_receiver_velocity': True, 'enable_dual_yaw': True,
        'enable_raw_doppler': False, 'enable_go2_roll_pitch_prior': False,
        'enable_go2_horizontal_velocity_prior': False, 'enable_source_aware': False,
        'source_aware_reject_extreme': False, 'go2_attitude_prior_sourceaware': True,
        'go2_horizontal_velocity_prior_source_aware_enabled': True,
        **{'source_aware_'+source+'_enabled': True for source in SOURCES},
    }
    value.update(updates)
    return value


def observations(bits, times=None):
    bits = np.asarray(bits, float)
    data = np.zeros((len(bits), 18), float)
    data[:, 0] = times if times is not None else np.arange(len(bits)) + 1.5
    data[:, 15:18] = bits
    imu = np.zeros((5, 7), float)
    imu[:, 0] = np.arange(5)
    return data, imu


def all_auxiliary_config(**updates):
    return config(enable_raw_doppler=True, enable_go2_roll_pitch_prior=True,
                  enable_go2_horizontal_velocity_prior=True, **updates)


def normalized_provider(times=(1.5, 2.5, 3.5), *, static=None, eligible=None):
    return {'enabled': True, 'solver_enabled': True, 'times': np.asarray(times, float),
            'tolerance': .1, 'eligible': np.asarray(eligible if eligible is not None else [True]*len(times), bool),
            'static': list(static if static is not None else [True]*len(times))}


def native_counts(rd=(0, 0), rp=(0, 0), hv=(0, 0), *, yaw_accepted=0, yaw_attempts=None,
                  yaw_downweight=0, sa=0, changed=0):
    attempts = yaw_accepted if yaw_attempts is None else yaw_attempts
    return {'raw_doppler_update_count': rd[0], 'raw_doppler_reject_count': rd[1],
            'go2_attitude_weak_prior_update_count': rp[0], 'go2_attitude_weak_prior_reject_count': rp[1],
            'go2_velocity_prior_update_count': hv[0], 'go2_velocity_prior_reject_count': hv[1],
            'dual_yaw_accepted_count': yaw_accepted, 'source_aware_evaluation_count': sa,
            'source_aware_weight_changed_count': changed,
            'yaw_NORMAL': yaw_accepted-yaw_downweight, 'yaw_DOWNWEIGHT': yaw_downweight,
            'yaw_REJECT': attempts-yaw_accepted}


def expectation(*, sa=False, position=0, velocity=0, yaw_attempts=0,
                rd=(0, 0), rp=(0, 0), hv=(0, 0)):
    result = {'position_update_count': position, 'receiver_velocity_update_count': velocity,
              'dual_yaw_attempt_count': yaw_attempts, 'auxiliary': {}}
    for name, (selected, static_pass) in [('RD', rd), ('RP', rp), ('HV', hv)]:
        result['auxiliary'][name] = {'selected_count': selected, 'static_pass_count': static_pass,
                                    'static_reject_count': selected-static_pass,
                                    'final_acceptance': 'STATE_DEPENDENT' if name == 'RD' and not sa else 'STATIC_GATE_EXACT'}
    return result


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def test_three_invalid_bits_suppress_all_auxiliary_selections(monkeypatch):
    gnss, imu = observations([[0, 0, 0]]*3)
    monkeypatch.setattr(runtime, '_provider', lambda module, cfg: normalized_provider())

    def forbidden_selection(*args, **kwargs):
        pytest.fail('An all-invalid GNSS row must not call an auxiliary selector')

    monkeypatch.setattr(runtime, 'select_last_nearest', forbidden_selection)
    result = runtime.expected_counts(all_auxiliary_config(), gnss, imu)
    assert result['eligible_rows'] == 3
    assert result['gnss_call_count'] == 0
    assert result['position_update_count'] == result['receiver_velocity_update_count'] == result['dual_yaw_attempt_count'] == 0
    assert all(module['selected_count'] == 0 for module in result['auxiliary'].values())


@pytest.mark.parametrize('yaw_enabled,rv_enabled', [(False, False), (False, True), (True, False), (True, True)])
def test_yaw_valid_row_admits_auxiliary_call_even_without_position_or_yaw_profile(monkeypatch, yaw_enabled, rv_enabled):
    gnss, imu = observations([[0, 0, 1]], [1.5])
    monkeypatch.setattr(runtime, '_provider', lambda module, cfg: normalized_provider([1.5]))
    result = runtime.expected_counts(all_auxiliary_config(enable_dual_yaw=yaw_enabled, enable_receiver_velocity=rv_enabled), gnss, imu)
    assert result['gnss_call_count'] == 1 and result['position_update_count'] == 0
    assert result['receiver_velocity_update_count'] == 0
    assert result['dual_yaw_attempt_count'] == int(yaw_enabled)
    assert {module['selected_count'] for module in result['auxiliary'].values()} == {1}


def test_d46_invalid_nearest_raw_doppler_row_is_a_reject_not_a_skip(tmp_path):
    lineage = {'raw_doppler_backend_id': 'synthetic_backend', 'obs_source_hash': 'a'*64,
               'nav_source_hash': 'b'*64, 'conversion_config_hash': 'c'*64,
               'covariance_policy': 'synthetic_test_policy'}
    rows = [{**lineage, 'time': '1.5', 'valid': '0', 'provider_status': 'controlled_outage', 'sat_count': '10'},
            {**lineage, 'time': '2.5', 'valid': '1', 'provider_status': 'available', 'sat_count': '10'}]
    cfg = config(enable_raw_doppler=True, raw_doppler_factor_path=write_csv(tmp_path/'synthetic_RD.csv', rows),
                 raw_doppler_time_tolerance_sec=.1, raw_doppler_min_sat=6, **lineage)
    gnss, imu = observations([[1, 0, 0]], [1.5])
    expected = runtime.expected_counts(cfg, gnss, imu)
    assert expected['auxiliary']['RD']['selected_count'] == 1
    assert expected['auxiliary']['RD']['static_pass_count'] == 0
    assert expected['auxiliary']['RD']['static_reject_count'] == 1
    assert runtime.check_auxiliary(native_counts(rd=(0, 1)), cfg, expected)['pass'] is True
    skipped = runtime.check_auxiliary(native_counts(rd=(0, 0)), cfg, expected)
    assert skipped['pass'] is False and 'RD_selection_closure' in skipped['failures']


def test_hv_eligibility_is_applied_before_nearest_row_selection(tmp_path):
    rows = [{'time': '1.5', 'update_flag': 'False', 'source_status': 'inactive', 'go2_velocity_truth_claim': 'false'},
            {'time': '1.55', 'update_flag': 'True', 'source_status': 'active', 'go2_velocity_truth_claim': 'false'}]
    cfg = config(enable_go2_horizontal_velocity_prior=True,
                 go2_horizontal_velocity_prior_path=write_csv(tmp_path/'synthetic_HV.csv', rows),
                 go2_velocity_prior_time_tolerance_sec=.1)
    gnss, imu = observations([[0, 0, 1]], [1.5])
    expected = runtime.expected_counts(cfg, gnss, imu)
    assert expected['auxiliary']['HV']['selected_count'] == 1
    assert expected['auxiliary']['HV']['static_pass_count'] == 1
    assert expected['auxiliary']['HV']['static_reject_count'] == 0
    assert runtime.check_auxiliary(native_counts(hv=(1, 0), yaw_attempts=1), cfg, expected)['pass'] is True


@pytest.mark.parametrize('sa,policy', [(False, 'STATE_DEPENDENT'), (True, 'STATIC_GATE_EXACT')])
def test_rd_acceptance_policy_follows_sa_switch(monkeypatch, sa, policy):
    gnss, imu = observations([[1, 0, 0]], [1.5])
    monkeypatch.setattr(runtime, '_provider', lambda module, cfg: normalized_provider([1.5]))
    result = runtime.expected_counts(all_auxiliary_config(enable_source_aware=sa), gnss, imu)
    assert result['auxiliary']['RD']['final_acceptance'] == policy
    assert result['auxiliary']['RP']['final_acceptance'] == 'STATIC_GATE_EXACT'
    assert result['auxiliary']['HV']['final_acceptance'] == 'STATIC_GATE_EXACT'


def test_sa_off_rd_allows_state_rejections_but_preserves_selection_bounds():
    cfg = all_auxiliary_config(enable_source_aware=False)
    expected = expectation(rd=(5, 4), rp=(2, 2), hv=(1, 1))
    assert runtime.check_auxiliary(native_counts(rd=(2, 3), rp=(2, 0), hv=(1, 0)), cfg, expected)['pass'] is True
    for rd in [(2, 2), (5, 0), (-1, 6)]:
        audit = runtime.check_auxiliary(native_counts(rd=rd, rp=(2, 0), hv=(1, 0)), cfg, expected)
        assert audit['pass'] is False and 'RD_selection_closure' in audit['failures']


def test_sa_on_nonrejecting_policy_requires_exact_static_rd_acceptance():
    cfg = all_auxiliary_config(enable_source_aware=True)
    expected = expectation(sa=True, position=4, velocity=3, yaw_attempts=5, rd=(5, 4), rp=(2, 2), hv=(1, 1))
    native = native_counts(rd=(4, 1), rp=(2, 0), hv=(1, 0), yaw_accepted=2, yaw_attempts=5, sa=16, changed=9)
    audit = runtime.check_auxiliary(native, cfg, expected)
    assert audit['pass'] is True
    assert audit['source_aware_expected_from_terminal_yaw_acceptance'] == 16
    state_reject = {**native, 'raw_doppler_update_count': 2, 'raw_doppler_reject_count': 3}
    failed = runtime.check_auxiliary(state_reject, cfg, expected)
    assert failed['pass'] is False and 'RD_static_acceptance' in failed['failures']


def test_sa_uses_accepted_yaw_instead_of_yaw_attempts():
    cfg = config(enable_source_aware=True)
    expected = expectation(sa=True, yaw_attempts=5)
    audit = runtime.check_auxiliary(native_counts(yaw_accepted=2, yaw_attempts=5, yaw_downweight=1, sa=2, changed=1), cfg, expected)
    assert audit['pass'] is True
    assert audit['source_aware_expected_from_terminal_yaw_acceptance'] == 2
    wrong = runtime.check_auxiliary(native_counts(yaw_accepted=2, yaw_attempts=5, sa=5, changed=1), cfg, expected)
    assert wrong['pass'] is False and 'SA_source_contribution_closure' in wrong['failures']


def test_sa_respects_source_and_weak_prior_opt_outs():
    cfg = all_auxiliary_config(enable_source_aware=True, source_aware_receiver_position_enabled=False,
                 source_aware_receiver_velocity_enabled=False, go2_attitude_prior_sourceaware=False,
                 source_aware_go2_horizontal_velocity_enabled=False)
    expected = expectation(sa=True, position=4, velocity=3, yaw_attempts=5, rd=(5, 4), rp=(2, 2), hv=(1, 1))
    audit = runtime.check_auxiliary(native_counts(rd=(4, 1), rp=(2, 0), hv=(1, 0), yaw_accepted=2, yaw_attempts=5, sa=6), cfg, expected)
    assert audit['pass'] is True
    assert audit['source_aware_expected_from_terminal_yaw_acceptance'] == 6


def test_sa_changed_count_must_fit_evaluation_count():
    cfg = config(enable_source_aware=True)
    expected = expectation(sa=True, yaw_attempts=5)
    for changed in [-1, 3]:
        audit = runtime.check_auxiliary(native_counts(yaw_accepted=2, yaw_attempts=5, sa=2, changed=changed), cfg, expected)
        assert audit['pass'] is False and 'SA_source_contribution_closure' in audit['failures']


@pytest.mark.parametrize('accepted', ['MISSING', 6])
def test_sa_cannot_close_against_missing_or_impossible_yaw_acceptance(accepted):
    cfg = config(enable_source_aware=True)
    expected = expectation(sa=True, yaw_attempts=5)
    native = native_counts(yaw_accepted=0 if accepted == 'MISSING' else accepted, yaw_attempts=5,
                           sa=0 if accepted == 'MISSING' else accepted)
    if accepted == 'MISSING':
        native.pop('dual_yaw_accepted_count')
    assert runtime.check_auxiliary(native, cfg, expected)['pass'] is False


@pytest.mark.parametrize('field', ['dual_yaw_accepted_count', 'yaw_NORMAL', 'yaw_DOWNWEIGHT', 'yaw_REJECT'])
@pytest.mark.parametrize('invalid', [None, -1, .5])
def test_every_native_yaw_partition_field_is_required_nonnegative_integer(field, invalid):
    native = native_counts(yaw_accepted=2, yaw_attempts=5, yaw_downweight=1)
    native[field] = invalid
    result = runtime.check_auxiliary(native, config(), expectation(yaw_attempts=5))
    assert result['pass'] is False and 'yaw_missing_or_invalid_terminal_count' in result['failures']


def test_native_yaw_accepted_and_attempt_partitions_must_both_close():
    expected = expectation(yaw_attempts=5)
    good = native_counts(yaw_accepted=2, yaw_attempts=5, yaw_downweight=1)
    assert runtime.check_auxiliary(good, config(), expected)['pass'] is True
    for change in [{'yaw_NORMAL': 0}, {'yaw_REJECT': 2}, {'dual_yaw_accepted_count': 3}]:
        audit = runtime.check_auxiliary({**good, **change}, config(), expected)
        assert audit['pass'] is False and 'yaw_terminal_partition_closure' in audit['failures']


def test_extreme_sa_rejection_policy_is_outside_frozen_contract():
    with pytest.raises(ValueError, match='nonrejecting SA policy changed'):
        runtime.check_auxiliary(native_counts(), config(source_aware_reject_extreme=True), expectation())


def identity_fixture(*, auxiliary=True):
    """Handwritten native serialization example; paths are inert fixture strings."""
    paths = {'imupath': '/synthetic_fixture/current.imu', 'gnsspath': '/synthetic_fixture/case.gnss',
             'raw_doppler_factor_path': '/synthetic_fixture/rd.csv',
             'go2_attitude_prior_path': '/synthetic_fixture/rp.csv',
             'go2_horizontal_velocity_prior_path': '/synthetic_fixture/hv.csv'}
    cfg = config(stage_id='FIXTURE_STAGE', protocol_id='FIXTURE_PROTOCOL',
                 case_id='D22_seed_00', run_id='RUN_FIXTURE_00006', data_mode='synthetic_test',
                 algorithm_id='fixture_source_backed_EKF', runtime_role='fixture_runtime',
                 enable_raw_doppler=auxiliary, enable_go2_roll_pitch_prior=auxiliary,
                 enable_go2_horizontal_velocity_prior=auxiliary, **paths)
    source = {'case_id': 'D22_seed_00', 'run_id': 'RUN_FIXTURE_00006', 'scheme_c': 'True',
              'dual_yaw': 'True', 'receiver_velocity': 'True', 'source_aware': 'False',
              'raw_doppler': str(auxiliary), 'go2_rp': str(auxiliary), 'go2_hv': str(auxiliary)}
    native = {
        'stage_id': 'FIXTURE_STAGE', 'phase': 'FIXTURE_STAGE', 'protocol_id': 'FIXTURE_PROTOCOL',
        'case_id': 'D22_seed_00', 'run_id': 'RUN_FIXTURE_00006', 'data_mode': 'synthetic_test',
        'algorithm_id': 'fixture_source_backed_EKF', 'port_role': 'fixture_runtime',
        'clean_final_v23_parity_mode': True, 'yaw_scheme_C_enabled': True,
        'enable_dual_yaw_update': True, 'enable_receiver_velocity_update': True,
        'enable_raw_doppler': auxiliary, 'source_aware_weighting_enabled': False,
        'go2_attitude_weak_prior_enabled': auxiliary, 'go2_horizontal_velocity_prior_enabled': auxiliary,
        'go2_body_state_not_truth': True, 'go2_position_truth_claim': False,
        'go2_velocity_truth_claim': False, 'go2_yaw_truth_claim': False, 'go2_contact_truth_claim': False,
        'actual_solver_input_paths': {'propagation_imu': paths['imupath'],
                                     'gnss_position_receiver_velocity_dual_yaw': paths['gnsspath']},
        'actual_solver_input_roles': {'propagation_imu': 'source_backed_propagation',
                                     'gnss_position_receiver_velocity_dual_yaw': 'validity_gated_measurements'},
    }
    if auxiliary:
        native['actual_solver_input_paths'].update({
            'raw_doppler_velocity': paths['raw_doppler_factor_path'],
            'go2_roll_pitch_weak_prior': paths['go2_attitude_prior_path'],
            'go2_horizontal_velocity_weak_prior': paths['go2_horizontal_velocity_prior_path']})
        native['actual_solver_input_roles'].update({
            'raw_doppler_velocity': 'source_backed_auxiliary_velocity',
            'go2_roll_pitch_weak_prior': 'weak_prior_not_truth',
            'go2_horizontal_velocity_weak_prior': 'horizontal_weak_prior_not_truth'})
    bundle = {'providers': {key: {'path': value} for key, value in paths.items()}}
    return native, cfg, source, bundle


@pytest.mark.parametrize('auxiliary', [False, True])
def test_native_identity_accepts_exact_enabled_input_roles(auxiliary):
    native, cfg, source, bundle = identity_fixture(auxiliary=auxiliary)
    result = runtime.validate_identity(native, cfg, source, bundle)
    assert result['passed'] is True
    assert len(result['actual_solver_input_paths']) == (5 if auxiliary else 2)
    # Disabled module providers remain pinned in the bundle but are absent from native inputs.
    assert len(bundle['providers']) == 5


@pytest.mark.parametrize('field', ['case_id', 'run_id'])
def test_native_identity_rejects_wrong_native_case_or_run(field):
    native, cfg, source, bundle = identity_fixture()
    native[field] = 'WRONG_FIXTURE_ID'
    with pytest.raises(ValueError, match=field):
        runtime.validate_identity(native, cfg, source, bundle)


@pytest.mark.parametrize('field', ['case_id', 'run_id'])
def test_native_identity_rejects_registry_case_or_run_disagreement(field):
    native, cfg, source, bundle = identity_fixture()
    source[field] = 'WRONG_REGISTERED_ID'
    with pytest.raises(ValueError, match='registry_case_run_identity'):
        runtime.validate_identity(native, cfg, source, bundle)


@pytest.mark.parametrize('field', ['enable_raw_doppler', 'enable_dual_yaw_update',
                                  'go2_attitude_weak_prior_enabled', 'go2_horizontal_velocity_prior_enabled'])
def test_native_identity_rejects_wrong_native_profile_toggle(field):
    native, cfg, source, bundle = identity_fixture()
    native[field] = False
    with pytest.raises(ValueError, match=field):
        runtime.validate_identity(native, cfg, source, bundle)


def test_native_identity_checks_profile_against_registry_even_if_config_and_native_agree():
    native, cfg, source, bundle = identity_fixture()
    cfg['enable_source_aware'] = True
    native['source_aware_weighting_enabled'] = True
    with pytest.raises(ValueError, match='registry_profile_enable_source_aware'):
        runtime.validate_identity(native, cfg, source, bundle)


@pytest.mark.parametrize('wrong_side', ['native', 'registry'])
def test_native_identity_rejects_wrong_scheme_c(wrong_side):
    native, cfg, source, bundle = identity_fixture()
    if wrong_side == 'native':
        native['yaw_scheme_C_enabled'] = False
    else:
        source['scheme_c'] = 'False'
    with pytest.raises(ValueError, match='yaw_scheme_C_enabled'):
        runtime.validate_identity(native, cfg, source, bundle)


@pytest.mark.parametrize('role', ['raw_doppler_velocity', 'go2_roll_pitch_weak_prior',
                                 'go2_horizontal_velocity_weak_prior'])
@pytest.mark.parametrize('container', ['actual_solver_input_paths', 'actual_solver_input_roles'])
def test_native_identity_rejects_missing_enabled_input_role(role, container):
    native, cfg, source, bundle = identity_fixture()
    native[container].pop(role)
    with pytest.raises(ValueError, match='native_input_role_set'):
        runtime.validate_identity(native, cfg, source, bundle)


def test_native_identity_rejects_unexpected_input_role():
    native, cfg, source, bundle = identity_fixture()
    native['actual_solver_input_paths']['unexpected_observation'] = '/synthetic_fixture/extra.csv'
    native['actual_solver_input_roles']['unexpected_observation'] = 'undeclared_input'
    with pytest.raises(ValueError, match='native_input_role_set'):
        runtime.validate_identity(native, cfg, source, bundle)


@pytest.mark.parametrize('wrong_side', ['native', 'config', 'bundle'])
def test_native_identity_requires_path_agreement_with_config_and_selected_bundle(wrong_side):
    native, cfg, source, bundle = identity_fixture()
    wrong = '/synthetic_fixture/wrong_case.gnss'
    if wrong_side == 'native':
        native['actual_solver_input_paths']['gnss_position_receiver_velocity_dual_yaw'] = wrong
    elif wrong_side == 'config':
        cfg['gnsspath'] = wrong
    else:
        bundle['providers']['gnsspath']['path'] = wrong
    with pytest.raises(ValueError, match='native_input_gnss_position_receiver_velocity_dual_yaw'):
        runtime.validate_identity(native, cfg, source, bundle)


@pytest.mark.parametrize('role', ['propagation_imu', 'raw_doppler_velocity', 'go2_roll_pitch_weak_prior',
                                 'go2_horizontal_velocity_weak_prior'])
def test_native_identity_rejects_wrong_input_purpose(role):
    native, cfg, source, bundle = identity_fixture()
    native['actual_solver_input_roles'][role] = 'incorrect_semantic_role'
    with pytest.raises(ValueError, match='native_input_'+role):
        runtime.validate_identity(native, cfg, source, bundle)


def test_native_identity_rejects_disabled_auxiliary_role_that_was_actually_opened():
    native, cfg, source, bundle = identity_fixture(auxiliary=False)
    native['actual_solver_input_paths']['raw_doppler_velocity'] = cfg['raw_doppler_factor_path']
    native['actual_solver_input_roles']['raw_doppler_velocity'] = 'source_backed_auxiliary_velocity'
    with pytest.raises(ValueError, match='native_input_role_set'):
        runtime.validate_identity(native, cfg, source, bundle)


def test_native_identity_requires_boolean_native_flags_not_integer_aliases():
    native, cfg, source, bundle = identity_fixture()
    native['enable_raw_doppler'] = 1
    with pytest.raises(ValueError, match='enable_raw_doppler'):
        runtime.validate_identity(native, cfg, source, bundle)
