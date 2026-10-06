"""Pure config/echo fidelity checks; no files, solver, evaluator, or data access.

The independent byte gate and exact frozen-to-new echo gate are hard gates.
A0 configuration-to-echo comparisons are diagnostic: unit conversions can make
frozen native echoes differ from decimal configuration inputs by rounding.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Mapping

import yaml

STATIC_ECHO_KEYS = tuple('''schema_version clean1_formal_mode clean_final_v23_parity_mode stage_id protocol_id case_id run_id data_mode phase port_role paper_performance_claim proposed_factor_claim final_v23_output_solver_input LegSA_output_solver_input trace_solver_input trace_used_online synthetic_data_used semisynthetic_data_used receiver_imu_as_body_imu per_case_tuning output_only_correction bad_epoch_deletion_for_metric epoch_deleted_for_metric old_runtime_input_count legacy_provider_input_count legacy_row_input_count legacy_aggregate_input_count status_fallback_used legacy_provider_used common_initialization common_initialization_dual_yaw_used trace_used_for_initialization method_specific_initialization common_initialization_source propagation_imu_source solver_output_reference_point antlever_m starttime endtime imudatalen imudatarate init_position_geodetic_deg_m init_velocity_ned_mps init_attitude_deg init_gyro_bias_deg_h init_accel_bias_mgal init_gyro_scale_ppm init_accel_scale_ppm init_position_std_m init_velocity_std_mps init_attitude_std_deg init_gyro_bias_std_deg_h init_accel_bias_std_mgal init_gyro_scale_std_ppm init_accel_scale_std_ppm angle_random_walk_deg_sqrt_h velocity_random_walk_mps_sqrt_h gyro_bias_std_deg_h accel_bias_std_mgal gyro_scale_std_ppm accel_scale_std_ppm correlation_time_h common_initialization_covariance_diagonal_internal antlever_config_source evaluation_reference_point_match_established reference_point_compensation_applied algorithm_id measurement_update_order ablation_variant enable_basic_dual_yaw_baseline enable_dual_yaw_update basic_dual_yaw_fixed_std_deg yaw_std_min_deg yaw_std_soft_deg yaw_std_hard_deg yaw_res_soft_deg yaw_res_hard_deg yaw_downweight_scale basic_dual_yaw_residual_sign basic_dual_yaw_H_phi_z disable_source_aware disable_go2 disable_qm disable_raw_doppler disable_fgo_feedback qa_passive_logging_enabled enable_qa_fallback qa_active_mode qa_a1_quality_source qa_a1_relpos_diff_valid_default qa_recovery_max_yaw_correction_deg enable_receiver_velocity_update receiver_velocity_stress_mode receiver_velocity_std_scale receiver_velocity_outage_start_sec receiver_velocity_outage_duration_sec receiver_velocity_additive_noise_std_mps receiver_velocity_additive_noise_seed diagnostic_stress_only diagnostic_only no_outperform_final_v23_claim enable_raw_doppler raw_doppler_solver_enabled raw_doppler_R_scale raw_doppler_time_tolerance_sec raw_doppler_min_sat raw_doppler_residual_gate_mps raw_doppler_mode raw_doppler_backend_lineage_required raw_doppler_backend_source_files raw_doppler_backend_source_hashes helper_executable_hash rtklib_position_solution_used_as_solver_input nav_pvt_velocity_used_as_raw_doppler gnss_velocity_used_as_raw_doppler go2_proprioceptive_joint_factor_enabled go2_proprioceptive_joint_factor_mode go2_proprioceptive_joint_factor_policy go2_proprioceptive_joint_factor_path_role go2_proprioceptive_joint_factor_sequential_equivalent go2_proprioceptive_source_aware_enabled go2_attitude_weak_prior_enabled go2_attitude_prior_sourceaware_enabled go2_attitude_prior_diagnostic_only go2_attitude_prior_std_roll_deg go2_attitude_prior_std_pitch_deg go2_attitude_prior_time_tolerance_sec go2_velocity_prior_diagnostic_enabled go2_horizontal_velocity_prior_enabled go2_velocity_prior_time_tolerance_sec go2_velocity_prior_std_scale go2_horizontal_velocity_prior_std_scale go2_horizontal_velocity_prior_mode go2_horizontal_velocity_adaptive_std_enabled go2_horizontal_velocity_bounded_std_policy go2_horizontal_velocity_strength_policy go2_horizontal_velocity_prior_source_aware_enabled formal_go2_velocity_prior go2_yaw_rate_prior_diagnostic_enabled go2_diagnostic_prior_only go2_readiness_lsim_metadata_enabled go2_readiness_lsim_time_tolerance_sec actual_solver_input_paths actual_solver_input_roles source_aware_weighting_enabled source_aware_policy_version source_aware_policy_branch_id source_aware_use_innovation_covariance source_aware_mode source_aware_max_R_scale source_aware_global_cap source_aware_deadband_normalized source_aware_moderate_normalized source_aware_strong_normalized source_aware_reject_extreme source_aware_no_R_shrink source_aware_trace_enabled source_aware_enable_rolling_innovation_baseline source_aware_rolling_window_size source_aware_rolling_mad_floor source_aware_method_family source_aware_method_k0 source_aware_method_k1 source_aware_method_c source_aware_method_alpha source_aware_method_phi source_aware_method_base_gain source_aware_go2_readiness_lsim_enabled source_aware_go2_readiness_low_scale source_aware_go2_impact_or_rough_scale source_aware_go2_motion_unknown_scale source_aware_go2_in_place_turn_scale source_caps source_aware_source_configs enable_multi_state_qm multi_state_qm_mode multi_state_qm_trace_enabled multi_state_qm_trace_only qm_downweight_threshold qm_reject_threshold qm_hold_enter_count qm_hold_length qm_recovery_count qm_fallback_enter_count qm_fallback_exit_count qm_fallback_max_duration qm_timestamp_gap_hold_sec qm_source_cap qm_global_cap qm_go2_motion_state_influence qm_readiness_influence selected_fgo_feedback no_feedback_fgo active_nine_factor_fgo contact_fk_factor fgo_feedback_enabled fgo_feedback_mode feedback_position_enabled feedback_velocity_enabled feedback_attitude_enabled yaw_scheme_C_enabled clean_input_provenance_label config_policy_evidence_status source_commit run_label lsim_oim multi_state_qm debug_update_timeline_enabled debug_overclose_audit_enabled debug_measurement_copy_guard_enabled debug_covariance_gain_enabled'''.split())

VECTOR_ECHO_FIELDS = {
    'initpos': 'init_position_geodetic_deg_m', 'initvel': 'init_velocity_ned_mps',
    'initatt': 'init_attitude_deg', 'initgyrbias': 'init_gyro_bias_deg_h',
    'initaccbias': 'init_accel_bias_mgal', 'initgyrscale': 'init_gyro_scale_ppm',
    'initaccscale': 'init_accel_scale_ppm', 'initposstd': 'init_position_std_m',
    'initvelstd': 'init_velocity_std_mps', 'initattstd': 'init_attitude_std_deg',
    'initbgstd': 'init_gyro_bias_std_deg_h', 'initbastd': 'init_accel_bias_std_mgal',
    'initsgstd': 'init_gyro_scale_std_ppm', 'initsastd': 'init_accel_scale_std_ppm',
    'arw': 'angle_random_walk_deg_sqrt_h', 'vrw': 'velocity_random_walk_mps_sqrt_h',
    'gbstd': 'gyro_bias_std_deg_h', 'abstd': 'accel_bias_std_mgal',
    'gsstd': 'gyro_scale_std_ppm', 'asstd': 'accel_scale_std_ppm', 'antlever': 'antlever_m',
}
CONFIG_ECHO_ALIASES = {
    'corrtime': 'correlation_time_h', 'enable_dual_yaw': 'enable_dual_yaw_update',
    'enable_receiver_velocity': 'enable_receiver_velocity_update',
    'enable_source_aware': 'source_aware_weighting_enabled',
    'enable_go2_roll_pitch_prior': 'go2_attitude_weak_prior_enabled',
    'enable_go2_horizontal_velocity_prior': 'go2_horizontal_velocity_prior_enabled',
    'go2_attitude_prior_sourceaware': 'go2_attitude_prior_sourceaware_enabled',
    'runtime_role': 'port_role', 'enable_selected_fgo_feedback': 'selected_fgo_feedback',
    'enable_no_feedback_fgo': 'no_feedback_fgo', 'enable_active_nine_factor_fgo': 'active_nine_factor_fgo',
    'enable_contact_fk_factor': 'contact_fk_factor',
}
_GNSS_LINE = re.compile(rb'^([ \t]*gnsspath[ \t]*:[ \t]*)([^\r\n]*)(\r?\n|$)')
_GNSS_ROLE = 'gnss_position_receiver_velocity_dual_yaw'


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def validate_gnsspath_only_bytes(frozen_bytes, candidate_bytes, *, expected_gnsspath=None):
    """Independent exact-one-line gate; construction alone is not its evidence."""
    old, new = frozen_bytes.splitlines(keepends=True), candidate_bytes.splitlines(keepends=True)
    oldkeys = [i for i, line in enumerate(old) if _GNSS_LINE.fullmatch(line)]
    newkeys = [i for i, line in enumerate(new) if _GNSS_LINE.fullmatch(line)]
    changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    if len(old) != len(new) or len(oldkeys) != 1 or oldkeys != newkeys or changed != oldkeys:
        raise RuntimeError('HARD_STOP_T5AR_CONFIG_BYTE_GATE: exactly one gnsspath line must differ')
    index = oldkeys[0]
    left, right = _GNSS_LINE.fullmatch(old[index]), _GNSS_LINE.fullmatch(new[index])
    if left[1] != right[1] or left[3] != right[3]:
        raise RuntimeError('HARD_STOP_T5AR_CONFIG_BYTE_GATE: gnsspath syntax/line ending changed')
    before = b''.join(old[:index] + old[index + 1:])
    after = b''.join(new[:index] + new[index + 1:])
    if before != after:
        raise RuntimeError('HARD_STOP_T5AR_CONFIG_BYTE_GATE: non-gnsspath bytes differ')
    if expected_gnsspath is not None:
        value = yaml.safe_load(new[index]).get('gnsspath')
        if value != expected_gnsspath or flat_string(flat_key_values(candidate_bytes)['gnsspath']) != expected_gnsspath:
            raise RuntimeError('HARD_STOP_T5AR_CONFIG_BYTE_GATE: replacement scalar differs')
    return {'passed': True, 'changed_line_one_based': index + 1, 'changed_line_count': 1,
            'non_gnsspath_bytes_identical': True, 'non_gnsspath_bytes_sha256_before': _sha(before),
            'non_gnsspath_bytes_sha256_after': _sha(after), 'native_scalar_roundtrip_checked': expected_gnsspath is not None}


def flat_key_values(payload):
    """Source model of frozen readKeyValues; a diagnostic, never a binary substitute."""
    result = {}
    for line in payload.decode('utf-8').splitlines():
        line = line.split('#', 1)[0].replace('[', ' ').replace(']', ' ').replace(',', ' ').strip()
        delimiter = line.find('=')
        if delimiter < 0:
            delimiter = line.find(':')
        if delimiter >= 0:
            result[line[:delimiter].strip()] = line[delimiter + 1:].strip()
    return result


def flat_string(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
        value = value[1:-1]
    return value


def decode_echo(payload):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate echo key: ' + key)
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite echo JSON: ' + value)
    value = json.loads(payload, object_pairs_hook=unique, parse_constant=nonfinite)
    if not isinstance(value, dict):
        raise ValueError('echo must be a JSON object')
    return value


def _exact(value, expected):
    if isinstance(value, bool) or isinstance(expected, bool):
        return type(value) is type(expected) and value == expected
    if isinstance(value, (int, float)) and isinstance(expected, (int, float)):
        return math.isfinite(value) and math.isfinite(expected) and value == expected
    if isinstance(value, dict) and isinstance(expected, dict):
        return value.keys() == expected.keys() and all(_exact(value[k], expected[k]) for k in value)
    if isinstance(value, list) and isinstance(expected, list):
        return len(value) == len(expected) and all(_exact(a, b) for a, b in zip(value, expected))
    return type(value) is type(expected) and value == expected


def compare_effective_echo(candidate, frozen, *, expected_gnsspath):
    """Exact recursive equality of all 211 preregistered static echo fields."""
    if not isinstance(candidate, Mapping) or not isinstance(frozen, Mapping):
        raise RuntimeError('HARD_STOP_T5AR_EFFECTIVE_ECHO: missing echo mapping')
    missing = [key for key in STATIC_ECHO_KEYS if key not in candidate or key not in frozen]
    expected = {key: frozen[key] for key in STATIC_ECHO_KEYS if key in frozen}
    paths = dict(expected.get('actual_solver_input_paths', {}))
    if _GNSS_ROLE not in paths:
        missing.append('actual_solver_input_paths.' + _GNSS_ROLE)
    paths[_GNSS_ROLE] = expected_gnsspath
    expected['actual_solver_input_paths'] = paths
    mismatches = [key for key in STATIC_ECHO_KEYS if key in candidate and key in expected
                  and not _exact(candidate[key], expected[key])]
    if missing or mismatches:
        raise RuntimeError('HARD_STOP_T5AR_EFFECTIVE_ECHO: ' + json.dumps({'missing': missing, 'mismatches': mismatches}))
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {'passed': True, 'comparison': 'EXACT_RECURSIVE_JSON_VALUE_EQUALITY_NO_TOLERANCE',
            'static_field_count': len(STATIC_ECHO_KEYS), 'static_fields': list(STATIC_ECHO_KEYS),
            'excluded_echo_fields': sorted((set(candidate) | set(frozen)) - set(STATIC_ECHO_KEYS)),
            'coverage_note': 'Static effective options are compared exactly. Runtime counters, provider results, and update-derived booleans are excluded. Configuration fields not echoed by the frozen binary remain protected by the independent gnsspath-only byte gate.',
            'update_derived_boolean_sources': {
                'raw_doppler': {'source': 'cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:73',
                                'definition': 'raw_doppler_status.update_count > 0'},
                'go2_prior': {'source': 'cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:95',
                              'definition': 'go2_attitude_prior_status.update_count > 0'},
                'fgo': {'source': 'cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:119',
                        'definition': 'fgo_feedback_status.update_count > 0'},
            },
            'permitted_difference': 'actual_solver_input_paths.' + _GNSS_ROLE,
            'expected_gnsspath': expected_gnsspath, 'frozen_static_sha256': _sha(canonical({k: frozen[k] for k in STATIC_ECHO_KEYS})),
            'candidate_static_sha256': _sha(canonical({k: candidate[k] for k in STATIC_ECHO_KEYS}))}


def audit_flat_config(config_bytes):
    """A0 read-only compatibility report; unavailable diagnostics never hard-stop."""
    try:
        config, flat = yaml.safe_load(config_bytes), flat_key_values(config_bytes)
        if not isinstance(config, dict):
            raise ValueError('configuration is not a mapping')
        # safe_load and the native flat parser both retain the last duplicate.
        # Inspect the YAML node list independently so this agreement cannot
        # hide repeated top-level declarations from the report-only A0 audit.
        tree = yaml.compose(config_bytes, Loader=yaml.SafeLoader)
        key_lines = {}
        for key_node, _ in tree.value:
            if isinstance(key_node, yaml.ScalarNode):
                key_lines.setdefault(key_node.value, []).append(key_node.start_mark.line + 1)
        duplicate_keys = [{'config_key': key, 'line_numbers_one_based': lines,
                           'occurrence_count': len(lines)}
                          for key, lines in key_lines.items() if len(lines) > 1]
        rows = []
        for key, value in config.items():
            token = flat.get(key)
            reason = None
            if token is None or not token:
                reason = 'MISSING_OR_EMPTY_NATIVE_FLAT_TOKEN'
            elif key in VECTOR_ECHO_FIELDS:
                try:
                    numbers = [float(item) for item in token.split()]
                    if len(numbers) != 3 or not all(math.isfinite(item) for item in numbers) or numbers != value:
                        reason = 'VECTOR_VALUES_DIFFER_FROM_YAML'
                except (ValueError, TypeError):
                    reason = 'VECTOR_NOT_THREE_INLINE_NUMBERS'
            elif isinstance(value, str) and flat_string(token) != value:
                reason = 'STRING_NORMALIZATION_DIFFERS_FROM_YAML'
            elif isinstance(value, bool) and token.lower() not in ('true', 'false', 'yes', 'no', 'on', 'off', '1', '0'):
                reason = 'BOOLEAN_NOT_NATIVE_LITERAL'
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                try:
                    if not math.isfinite(float(token)) or float(token) != value:
                        reason = 'SCALAR_DIFFERS_FROM_YAML'
                except ValueError:
                    reason = 'SCALAR_NOT_NATIVE_NUMBER'
            rows.append({'config_key': key, 'status': 'COMPATIBLE' if reason is None else 'MISMATCH',
                         'reason': reason, 'native_flat_token': token})
        rows.extend({**duplicate, 'status': 'DUPLICATE_KEY',
                     'reason': 'DUPLICATE_TOP_LEVEL_KEY',
                     'native_flat_token': flat.get(duplicate['config_key'])}
                    for duplicate in duplicate_keys)
        differences = [row for row in rows if row['status'] != 'COMPATIBLE']
        return {'status': 'INCOMPATIBLE' if duplicate_keys else ('COMPATIBLE' if not differences else 'MISMATCH'),
                'compatibility_passed': not differences, 'differences': differences, 'duplicate_keys': duplicate_keys,
                'missing_fields': [row['config_key'] for row in differences if row['reason'] == 'MISSING_OR_EMPTY_NATIVE_FLAT_TOKEN'],
                'vector_field_count': sum(key in config for key in VECTOR_ECHO_FIELDS),
                'report_only': True, 'binary_invoked': False, 'config_sha256': _sha(config_bytes), 'rows': rows}
    except (ValueError, TypeError, UnicodeError, yaml.YAMLError) as error:
        return {'status': 'UNAVAILABLE', 'report_only': True, 'passed': False, 'compatibility_passed': False,
                'differences': [], 'missing_fields': [], 'vector_field_count': 0, 'reason': str(error), 'rows': []}


def _comparison_row(key, echo_key, expected, observed, *, rtol, atol):
    try:
        a = expected if isinstance(expected, list) else [expected]
        b = observed if isinstance(observed, list) else [observed]
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in a + b):
            finite = all(math.isfinite(x) for x in a + b)
            equal = len(a) == len(b) and finite and all(math.isclose(x, y, rel_tol=rtol, abs_tol=atol) for x, y in zip(a, b))
            residuals = [float(y - x) for x, y in zip(a, b)] if finite else []
            ulps = [abs(y - x) / max(math.ulp(float(x)), math.ulp(float(y))) for x, y in zip(a, b)] if finite else []
            return {'config_key': key, 'echo_key': echo_key, 'status': 'MATCH_WITHIN_REPORT_TOLERANCE' if equal else 'MISMATCH',
                    'exact_equal': _exact(expected, observed), 'expected': expected, 'observed': observed,
                    'max_abs_roundtrip_residual': max(map(abs, residuals), default=0.),
                    'max_roundtrip_ulps': max(ulps, default=0.)}
    except (TypeError, ValueError, OverflowError):
        pass
    return {'config_key': key, 'echo_key': echo_key, 'status': 'EXACT_MATCH' if _exact(expected, observed) else 'MISMATCH',
            'expected': expected, 'observed': observed}


def audit_config_to_echo(config_bytes, echo, *, rtol=1e-12, atol=1e-12):
    """A0 represented options and covariance/unit-roundtrip report, not gate b."""
    try:
        config = yaml.safe_load(config_bytes)
        if not isinstance(config, dict) or not isinstance(echo, Mapping):
            raise ValueError('config/echo mapping unavailable')
        flat = flat_key_values(config_bytes)
        rows, represented = [], set()
        mappings = {**VECTOR_ECHO_FIELDS, **CONFIG_ECHO_ALIASES}
        mappings.update({key: key for key in config if key in STATIC_ECHO_KEYS and key not in mappings})
        for key, echo_key in mappings.items():
            if key not in config:
                continue
            represented.add(key)
            if echo_key not in echo:
                rows.append({'config_key': key, 'echo_key': echo_key, 'status': 'UNAVAILABLE', 'reason': 'echo field absent'})
                continue
            expected = config[key]
            if key in ('raw_doppler_backend_source_files', 'raw_doppler_backend_source_hashes'):
                expected = flat_string(flat.get(key, ''))
            rows.append(_comparison_row(key, echo_key, expected, echo[echo_key], rtol=rtol, atol=atol))
        # The 21-dimensional initialization diagonal is an echoed derived option.
        # Position/velocity are SI; attitude is radians, biases rad/s and m/s^2,
        # gyro/accel scales are unitless, each diagonal entry is the squared std.
        covariance_keys = [('initposstd', 1.), ('initvelstd', 1.), ('initattstd', math.pi / 180.),
                           ('initbgstd', math.pi / 180. / 3600.), ('initbastd', 1e-5),
                           ('initsgstd', 1e-6), ('initsastd', 1e-6)]
        if all(key in config and isinstance(config[key], list) and len(config[key]) == 3 for key, _ in covariance_keys):
            covariance = [(float(x) * scale) ** 2 for key, scale in covariance_keys for x in config[key]]
            field = 'common_initialization_covariance_diagonal_internal'
            if field in echo:
                rows.append(_comparison_row('derived_initialization_covariance', field, covariance, echo[field], rtol=rtol, atol=atol))
        differences = [row for row in rows if row['status'] == 'MISMATCH']
        missing = [row['echo_key'] for row in rows if row['status'] == 'UNAVAILABLE']
        return {'status': 'MISMATCH' if differences else 'AVAILABLE',
                'passed': not differences and not missing, 'differences': differences, 'missing_fields': missing,
                'report_only': True, 'hard_gate_b_uses_no_tolerance': True,
                'numeric_roundtrip_relative_tolerance': rtol, 'numeric_roundtrip_absolute_tolerance': atol,
                'vectors_and_unit_conversions': 'degrees/radians, deg/h/rad/s, mGal/m/s2, ppm/unitless, random-walk per hour/second; configuration units restored by native echo',
                'config_sha256': _sha(config_bytes), 'rows': rows,
                'not_directly_represented_config_keys': sorted(set(config) - represented)}
    except (ValueError, TypeError, UnicodeError, yaml.YAMLError) as error:
        return {'status': 'UNAVAILABLE', 'report_only': True, 'passed': False, 'compatibility_passed': False,
                'differences': [], 'missing_fields': [], 'vector_field_count': 0, 'reason': str(error), 'rows': []}
