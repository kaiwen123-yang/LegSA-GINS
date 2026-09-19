"""P-13 minimal native guard freeze and C00 old/new executable byte bridge.

No provider generation or evaluator call is present. CAL template scientific
bytes are retained; only the five provider paths and output directory are bound.
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
from pathlib import Path
import subprocess
import time

import yaml

from ..clean5_degradation.common import FLAGS, registry, write_json
from ..clean5_degradation.runtime import validate_input_opens
from ..clean5_parity.runtime import bind_config
from ..clean5_sequence.runtime_config import frozen_parameter_hash
from ..clean5_sequence.solver_runner import audit_solver_openat
from ..clean5_sequence.solver_validation import validate_run_outputs
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group

OLD_SHA256 = '9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f'
BASE_COMMIT = 'a01ceb931049f84af8c900b39e4cf01c52f627c6'
NATIVE_SOURCE = 'cpp/legsa_v23_port_core/src/config/port_config_loader.cpp'
V2_STAGE = 'CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2'
V21_STAGE = 'CLEAN6_SENSOR_MODEL_V21'
PROFILES = ('F01', 'F02', 'F03', 'F04', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09')
FILES = ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt', 'LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv')
PATH_KEYS = ('imupath', 'gnsspath', 'raw_doppler_factor_path',
             'go2_attitude_prior_path', 'go2_horizontal_velocity_prior_path')
GUARD_OLD = '    if (std::fabs(options.basic_dual_yaw_fixed_std_deg - 1.5) > 1.0e-12) {'
GUARD_NEW = ('    if (std::fabs(options.basic_dual_yaw_fixed_std_deg - 1.5) > 1.0e-12 &&\n'
             '        std::fabs(options.basic_dual_yaw_fixed_std_deg - 2.933193) > 1.0e-12) {')


def _git(reg, *args):
    return subprocess.check_output(['git', *args], cwd=reg.code_root)


def _code_gate(reg, code_commit):
    if _git(reg, 'rev-parse', 'HEAD').decode().strip() != code_commit:
        raise ValueError('P13 code commit differs from HEAD')
    for rel in (NATIVE_SOURCE, 'src/legsa_gins/paper_rebuild/clean6_sensor_v21/binary_bridge.py',
                'scripts/paper_rebuild/clean6_v21_binary_bridge.py',
                'configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml'):
        if _git(reg, 'show', code_commit + ':' + rel) != (reg.code_root / rel).read_bytes():
            raise ValueError('P13 bridge input source is not committed: ' + rel)
    original = _git(reg, 'show', BASE_COMMIT + ':' + NATIVE_SOURCE).decode()
    changed = _git(reg, 'diff', '--name-only', BASE_COMMIT, '--', 'cpp').decode().splitlines()
    if (changed != [NATIVE_SOURCE] or original.count(GUARD_OLD) != 1 or
            (reg.code_root / NATIVE_SOURCE).read_text() != original.replace(GUARD_OLD, GUARD_NEW)):
        raise ValueError('Native diff is not exactly the authorized F02 guard addition')
    return {'code_commit': code_commit, 'base_commit': BASE_COMMIT,
            'native_changed_files': changed,
            'native_source_sha256': sha256_file(reg.code_root / NATIVE_SOURCE),
            'native_diff': _git(reg, 'diff', BASE_COMMIT, '--', 'cpp').decode()}


def _cache(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line or line.startswith(('#', '//')) or '=' not in line:
            continue
        name, value = line.split('=', 1)
        result[name.split(':', 1)[0]] = value
    return result


def _pin(path, expected):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
        raise ValueError('Frozen file identity mismatch: ' + str(path))
    return {'path': str(path), 'sha256': expected, 'size_bytes': path.stat().st_size}


def build_record(reg, code_commit):
    """Record an actual post-commit configure/build and freeze both binaries."""
    code = _code_gate(reg, code_commit)
    root = reg.clean_root / 'stages' / V21_STAGE / '01_BINARY_BRIDGE'
    root.mkdir(parents=True, exist_ok=True)
    freeze_path = root / 'BINARY_FREEZE.json'
    if freeze_path.exists():
        prior = json.loads(freeze_path.read_text())
        for entry in (prior['old_executable'], prior['new_executable']):
            _pin(entry['path'], entry['sha256'])
        return prior
    old = reg.code_root / 'build/canonical541_cpp/legsa_v23_port_core_demo'
    new_build = reg.code_root / 'build/p13_v21_cpp'
    old_pin = _pin(old, OLD_SHA256)
    old_cache = _cache(old.parent / 'CMakeCache.txt')
    flags = ('CMAKE_BUILD_TYPE', 'CMAKE_CXX_COMPILER', 'CMAKE_CXX_FLAGS',
             'CMAKE_CXX_FLAGS_RELEASE', 'CMAKE_EXE_LINKER_FLAGS',
             'CMAKE_EXE_LINKER_FLAGS_RELEASE', 'CMAKE_GENERATOR')
    if old_cache['CMAKE_BUILD_TYPE'] != 'Release':
        raise ValueError('Old build is not the frozen Release configuration')
    configure = ['cmake', '-S', str(reg.code_root / 'cpp'), '-B', str(new_build),
                 '-G', old_cache['CMAKE_GENERATOR']]
    configure += ['-D' + key + '=' + old_cache[key] for key in flags if key != 'CMAKE_GENERATOR']
    commands = [configure, ['cmake', '--build', str(new_build), '--target',
                           'legsa_v23_port_core_demo', '--parallel', '8']]
    records = []
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=reg.code_root, text=True, capture_output=True)
        record = {'command': command, 'exit_code': result.returncode,
                  'stdout': result.stdout, 'stderr': result.stderr}
        write_json(root / ('BUILD_COMMAND_' + str(index) + '.json'), record)
        records.append(record)
        if result.returncode:
            raise RuntimeError('P13 Release configure/build failed')
    new_cache = _cache(new_build / 'CMakeCache.txt')
    if any(old_cache[key] != new_cache[key] for key in flags):
        raise ValueError('New Release flags differ from old build')
    new = new_build / 'legsa_v23_port_core_demo'
    payload = {**FLAGS, **code, 'status': 'FROZEN_PENDING_BINARY_BRIDGE',
               'data_mode': 'build_metadata_only', 'provider_calls': 0,
               'solver_calls': 0, 'evaluator_calls': 0,
               'old_executable': _pin(old, OLD_SHA256),
               'new_executable': _pin(new, sha256_file(new)),
               'build_flags': {key: new_cache[key] for key in flags},
               'build_commands': records, 'old_binary_preserved': _pin(old, OLD_SHA256) == old_pin,
               'allowed_yaw_std_deg': [1.5, 2.933193], 'guard_tolerance': 1e-12,
               'scheme_c_soft_threshold_deg': 3.0, 'scheme_c_threshold_changed': False,
               'new_std_below_scheme_c_soft_threshold': 2.933193 < 3.0}
    write_json(freeze_path, payload)
    return payload


def _one(reg, code_commit, root, source, original, bundle, executable):
    root.mkdir(parents=True, exist_ok=False)
    text, diff = bind_config(original, {**{key: bundle['providers'][key]['path'] for key in PATH_KEYS},
                                        'outputpath': str(root)})
    cfg = yaml.safe_load(text)
    cfg_path = root / 'P13_BINARY_BRIDGE_CONFIG.yaml'
    cfg_path.write_text(text)
    log = root / 'SOLVER_OPENAT.strace'
    tmp = root / 'tmp'
    tmp.mkdir()
    native_command = [executable['path'], '--config', str(cfg_path), '--output-dir', str(root),
                      '--debug-update-timeline', '--debug-output-dir', str(root),
                      '--debug-max-rows', '1000000']
    command = ['env', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1',
               'NUMEXPR_NUM_THREADS=1', 'TMPDIR=' + str(tmp),
               'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat', '-o', str(log),
               *native_command]
    record = {**FLAGS, 'data_mode': 'real_clean', 'code_commit': code_commit,
              'run_id': cfg['run_id'], 'method_id': source['method_id'], 'case_id': cfg['case_id'],
              'chain': 'CAL_STD_1_5_BINARY_BRIDGE', 'executable': executable,
              'config_hash': hashlib.sha256(text.encode()).hexdigest(),
              'frozen_parameter_hash': frozen_parameter_hash(text), 'config_path_only_diff': diff,
              'raw_source_hashes': bundle['raw_input_hashes'],
              'provider_hashes': {key: entry['sha256'] for key, entry in bundle['providers'].items()},
              'command': command, 'terminal_status': 'RUNNING', 'retry_count': 0}
    write_json(root / 'RUN_STARTED.json', record)
    started = time.monotonic()
    try:
        _pin(executable['path'], executable['sha256'])
        result = run_process_group(command, cwd=reg.code_root, timeout_seconds=1800,
            timeout_message='P13 binary bridge timeout; no retry',
            launch_failure_message='P13 binary bridge native launch failed; no retry')
        record.update(exit_code=result.returncode, elapsed_seconds=time.monotonic() - started)
        (root / 'stdout.log').write_text(result.stdout)
        (root / 'stderr.log').write_text(result.stderr)
        record['strace_audit'] = audit_solver_openat(log, cwd=reg.code_root, raw_root=reg.raw_root,
                                                    clean_root=reg.clean_root, run_dir=root)
        if not record['strace_audit']['pass']:
            raise ValueError('Binary bridge solver file-access audit failed')
        enabled = {'imupath': cfg['imupath'], 'gnsspath': cfg['gnsspath']}
        for flag, key in [('enable_raw_doppler', 'raw_doppler_factor_path'),
                          ('enable_go2_roll_pitch_prior', 'go2_attitude_prior_path'),
                          ('enable_go2_horizontal_velocity_prior', 'go2_horizontal_velocity_prior_path')]:
            if cfg[flag]:
                enabled[key] = cfg[key]
        record['input_open_audit'] = validate_input_opens(log, enabled, reg, root, cfg_path)
        if result.returncode:
            raise RuntimeError('P13 binary bridge native solver failed')
        record['output_validation'] = validate_run_outputs(root, {'window_contract': {
            't_start': cfg['starttime'], 't_end': cfg['endtime']}})
        record['files'] = {name: _pin(root / name, sha256_file(root / name)) for name in FILES}
        record['terminal_status'] = 'COMPLETED'
    except Exception as error:
        record.update(terminal_status='FAILED_BINARY_BRIDGE', failure_type=type(error).__name__,
                      failure=str(error), elapsed_seconds=time.monotonic() - started)
        write_json(root / 'BRIDGE_RUN_TERMINAL.json', record)
        raise
    write_json(root / 'BRIDGE_RUN_TERMINAL.json', record)
    return record


def bridge(reg, code_commit):
    _code_gate(reg, code_commit)
    root = reg.clean_root / 'stages' / V21_STAGE / '01_BINARY_BRIDGE'
    freeze = json.loads((root / 'BINARY_FREEZE.json').read_text())
    for name in ('old_executable', 'new_executable'):
        _pin(freeze[name]['path'], freeze[name]['sha256'])
    v2 = reg.clean_root / 'stages' / V2_STAGE
    bundle_path = v2 / '02_PROVIDERS/C00_clean_normal/PROVIDER_BUNDLE.json'
    bundle = json.loads(bundle_path.read_text())
    if bundle['case_id'] != 'C00_clean_normal' or set(bundle['providers']) != set(PATH_KEYS):
        raise ValueError('Old C00 CAL bundle identity changed')
    for entry in bundle['providers'].values():
        _pin(entry['path'], entry['sha256'])
    templates = []
    for index, method in enumerate(PROFILES, 1):
        retained = v2 / 'RETAINED_RUNS' / f'RUN_{index:05d}' / 'solver'
        path = retained / 'PROTOCOL_V2_RUNTIME_CONFIG.yaml'
        source = json.loads((retained / 'P09C_RUN_TERMINAL.json').read_text())
        text = path.read_text()
        cfg = yaml.safe_load(text)
        if (source['method_id'] != method or source['terminal_status'] != 'COMPLETED' or
                cfg['case_id'] != 'C00_clean_normal' or cfg['basic_dual_yaw_fixed_std_deg'] != 1.5 or
                cfg['yaw_std_soft_deg'] != 3 or cfg['yaw_std_hard_deg'] != 6 or
                source['provider_hashes'] != {key: value['sha256'] for key, value in bundle['providers'].items()}):
            raise ValueError('Old C00 CAL profile/input identity changed: ' + method)
        _pin(path, source['config_hash'])
        templates.append((source, text))
    payload = {**FLAGS, 'data_mode': 'real_clean', 'code_commit': code_commit,
               'case_id': 'C00_clean_normal', 'status': 'RUNNING', 'solver_calls': 0,
               'provider_calls': 0, 'evaluator_calls': 0, 'comparisons': [],
               'binary_freeze_sha256': sha256_file(root / 'BINARY_FREEZE.json'),
               'provider_bundle_sha256': sha256_file(bundle_path), 'retry_count': 0}
    write_json(root / 'BRIDGE_STARTED.json', payload)
    try:
        for source, original in templates:
            method = source['method_id']
            records = {}
            for label in ('old', 'new'):
                payload['solver_calls'] += 1
                records[label] = _one(reg, code_commit, root / method / label, source, original,
                                      bundle, freeze[label + '_executable'])
                print('P13_BINARY_BRIDGE', method, label, 'COMPLETED', payload['solver_calls'], '/22', flush=True)
            comparisons = [{'method_id': method, 'filename': name,
                            'old_sha256': records['old']['files'][name]['sha256'],
                            'new_sha256': records['new']['files'][name]['sha256'],
                            'byte_identical': filecmp.cmp(root / method / 'old' / name,
                                                          root / method / 'new' / name, shallow=False)}
                           for name in FILES]
            payload['comparisons'].extend(comparisons)
            write_json(root / method / 'BYTE_COMPARISON.json', {'comparisons': comparisons})
            if not all(item['byte_identical'] for item in comparisons):
                raise ValueError('P13 binary identity bridge NAV/STD byte mismatch: ' + method)
        for entry in bundle['providers'].values():
            _pin(entry['path'], entry['sha256'])
        for name in ('old_executable', 'new_executable'):
            _pin(freeze[name]['path'], freeze[name]['sha256'])
        payload.update(status='PASS', passed_comparisons=len(payload['comparisons']),
                       expected_comparisons=44, expected_native_calls=22,
                       native_calls_complete=payload['solver_calls'] == 22)
    except Exception as error:
        payload.update(status='FAILED_BINARY_BRIDGE', failure_type=type(error).__name__, failure=str(error))
        write_json(root / 'BINARY_BRIDGE_RESULT.json', payload)
        raise
    write_json(root / 'BINARY_BRIDGE_RESULT.json', payload)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--operation', choices=('build-record', 'bridge'), required=True)
    parser.add_argument('--code-commit', required=True)
    args = parser.parse_args(argv)
    reg = registry(args.local_config)
    result = (build_record if args.operation == 'build-record' else bridge)(reg, args.code_commit)
    print(json.dumps({'operation': args.operation, 'status': result['status'],
                      'solver_calls': result.get('solver_calls', 0)}, sort_keys=True), flush=True)
    return 0
