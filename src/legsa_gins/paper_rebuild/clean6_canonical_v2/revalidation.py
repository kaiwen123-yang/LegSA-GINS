"""Human-authorized P-09c metadata repair; no provider, solver or evaluator call."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import yaml

from ..clean5_degradation.common import pinned, resolve, write_json
from ..clean5_degradation.runtime import (
    expected_counts, check_auxiliary, validate_identity, validate_input_opens)
from ..clean5_parity.runtime import check_counters
from ..clean5_sequence.solver_runner import audit_solver_openat
from ..clean5_sequence.solver_validation import validate_run_outputs
from ..manifest import sha256_file
from .runtime import append_sequence_runtime_role


def verify_original_seal(record):
    """Rehash every original file before deriving any new validation evidence."""
    root = Path(record['output_root'])
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Original run root missing or symlink')
    seal_path = root/'OUTPUT_SEAL.json'
    if seal_path.is_symlink():
        raise ValueError('Original seal is a symlink')
    seal = json.loads(seal_path.read_text())
    if seal.get('status') != 'SEALED_BEFORE_EVALUATION' or seal.get('files') != record.get('output_seal'):
        raise ValueError('Original output seal differs from retained run record')
    if not seal['files']:
        raise ValueError('Original output seal is empty')
    for relative, metadata in seal['files'].items():
        member = Path(relative)
        path = root/member
        if (member.is_absolute() or '..' in member.parts or any(p.is_symlink() for p in (path, *path.parents))
                or not path.is_file() or path.stat().st_size != metadata['size_bytes']
                or sha256_file(path) != metadata['sha256']):
            raise ValueError('Original sealed file changed: '+relative)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != seal_path}
    if actual != set(seal['files']):
        raise ValueError('Original sealed file membership changed')
    terminal = json.loads((root/'P09C_RUN_TERMINAL.json').read_text())
    if terminal != {k: v for k, v in record.items() if k not in ('output_seal', 'solver_output_bytes')}:
        raise ValueError('Retained record differs from sealed original terminal')
    return {'passed': True, 'file_count': len(seal['files']),
            'bytes_checked': sum(v['size_bytes'] for v in seal['files'].values()),
            'original_output_seal_path': str(seal_path),
            'original_output_seal_sha256': sha256_file(seal_path)}


def _enabled_paths(config):
    result = {'propagation_imu': config['imupath'], 'gnss': config['gnsspath']}
    for flag, key in (('enable_raw_doppler', 'raw_doppler_factor_path'),
                      ('enable_go2_roll_pitch_prior', 'go2_attitude_prior_path'),
                      ('enable_go2_horizontal_velocity_prior', 'go2_horizontal_velocity_prior_path')):
        if config[flag]:
            result[key] = config[key]
    return result


def _bundle_from_config(config, hashes):
    return {'providers': {key: {'path': config[key], 'sha256': digest}
                          for key, digest in hashes.items()}}


def _native_source(record, config):
    return {**record['source_registry_row'], 'run_id': config['run_id'], 'case_id': config['case_id']}


def revalidate_existing(records, contract, reg, output_root, validation_code_commit):
    """Return 33 records; only 22 failed wrappers receive new validation results.

    Writes exclusively below output_root/REVALIDATION_RUNS and an exclusive
    REVALIDATED_RECORDS.json. Original native code/config/seal identities stay
    unchanged. Failure retains its derived record then raises; no auto retry.
    """
    restart = contract['restart_authorization']
    profiles = set(contract['runtime']['profiles'])
    expected = {(dataset, method) for dataset in ('BY2', 'BY2H', 'BY2O') for method in profiles}
    if (len(records) != 33 or {(r['dataset_id'], r['method_id']) for r in records} != expected
            or {r['code_commit'] for r in records} != {restart['original_execution_code_commit']}
            or not validation_code_commit):
        raise ValueError('Restart requires exactly the original 33 runs at one native freeze')
    for row in records:
        if row.get('exit_code') != 0 or row.get('retry_count') != 0:
            raise ValueError('Only original sealed exit-zero runs may be reused')
        if row['dataset_id'] == 'BY2':
            if row['terminal_status'] != 'COMPLETED':
                raise ValueError('Original BY2 C00 terminal changed')
        elif (row['terminal_status'], row.get('failure_type'), row.get('failure')) != (
                'FAILED_TECHNICAL', 'KeyError', "'runtime_role'"):
            raise ValueError('Revalidation scope is only the 22 missing-runtime-role failures')
    output_root = Path(output_root)
    stage = resolve(contract['stage_root'], reg)
    if (stage not in output_root.parents or output_root.is_symlink()
            or any(Path(r['output_root']) == output_root or Path(r['output_root']) in output_root.parents for r in records)):
        raise ValueError('Revalidation output must be a separate child of the protocol stage')
    # No new output is created before all 33 seals have passed.
    seal_audits = {r['run_id']: verify_original_seal(r) for r in records}
    root = output_root/'REVALIDATION_RUNS'
    root.mkdir(parents=True, exist_ok=False)
    results = []
    for original in records:
        record = copy.deepcopy(original)
        record.update(validation_code_commit=validation_code_commit,
                      continuation_code_commit=validation_code_commit, original_native_reused=True,
                      original_native_code_commit=original['code_commit'], native_rerun_count=0,
                      original_terminal_status=original['terminal_status'],
                      original_seal_revalidation=seal_audits[original['run_id']])
        if original['dataset_id'] == 'BY2':
            record['validation_status'] = 'ORIGINAL_COMPLETED_SEAL_VERIFIED'
            results.append(record)
            continue
        started = time.monotonic()
        native_root = Path(original['output_root'])
        destination = root/original['run_id']
        destination.mkdir()
        cfg_path = native_root/'PROTOCOL_V2_RUNTIME_CONFIG.yaml'
        record_path = destination/'REVALIDATED_RUN_RECORD.json'
        record['validation_record_path'] = str(record_path)
        try:
            text = cfg_path.read_text()
            if hashlib.sha256(text.encode()).hexdigest() != original['config_hash']:
                raise ValueError('Original runtime config hash changed')
            derived, transport = append_sequence_runtime_role(text, restart['sequence_runtime_role'])
            derived_path = destination/'VALIDATION_RUNTIME_CONFIG.yaml'
            with derived_path.open('x') as stream:
                stream.write(derived)
            config = yaml.safe_load(derived)
            record.update(validation_config_path=str(derived_path), validation_config_hash=sha256_file(derived_path),
                          original_config_path=str(cfg_path), runtime_role_transport_audit=transport)
            bundle = _bundle_from_config(config, original['provider_hashes'])
            for pin in bundle['providers'].values():
                pinned(pin, reg)
            native = json.loads((native_root/'RUN_MANIFEST.json').read_text())
            record['native_identity_audit'] = validate_identity(native, config, _native_source(original, config), bundle)
            imu = np.loadtxt(config['imupath'], ndmin=2)
            gnss = np.loadtxt(config['gnsspath'], ndmin=2)
            expected_counts_now = expected_counts(config, gnss, imu)
            if expected_counts_now != original['expected_counters']:
                raise ValueError('Original input-derived expected counters changed')
            record['counter_audit'] = check_counters(native, config, expected_counts_now)
            record['auxiliary_counter_audit'] = check_auxiliary(native, config, expected_counts_now)
            if not record['counter_audit']['pass'] or not record['auxiliary_counter_audit']['pass']:
                raise ValueError('Revalidated input-derived runtime counters failed')
            record['counters'] = record['counter_audit']['actual']
            log = native_root/'SOLVER_OPENAT.strace'
            record['strace_audit'] = audit_solver_openat(log, cwd=reg.code_root, raw_root=reg.raw_root,
                                                       clean_root=reg.clean_root, run_dir=native_root)
            if not record['strace_audit']['pass']:
                raise ValueError('Original solver strace audit failed')
            # The native process opened the original config, never the new metadata-only file.
            record['input_open_audit'] = validate_input_opens(log, _enabled_paths(config), reg, native_root, cfg_path)
            record['output_validation'] = validate_run_outputs(native_root, {'window_contract': {
                't_start': config['starttime'], 't_end': config['endtime']}})
            record.update(terminal_status='COMPLETED', validation_status='PASS',
                          original_failure_type=record.pop('failure_type'), original_failure=record.pop('failure'))
        except Exception as error:
            record.update(terminal_status='FAILED_TECHNICAL', validation_status='FAIL',
                          validation_failure_type=type(error).__name__, validation_failure=str(error))
            record['validation_seconds'] = time.monotonic()-started
            write_json(record_path, record)
            raise ValueError('Sequence revalidation failed; retained scene: '+original['run_id']+': '+str(error)) from error
        record['validation_seconds'] = time.monotonic()-started
        write_json(record_path, record)
        record['validation_record_sha256'] = sha256_file(record_path)
        results.append(record)
    write_json(output_root/'REVALIDATED_RECORDS.json', results)
    return results


def real_manifest_regression(contract, reg, current_records):
    """Read-only 15 P-06 wrapper/native pairs plus the 22 retained native pairs."""
    seal_path = pinned(contract['sequence_consistency']['reference_seal'], reg)
    seal = json.loads(seal_path.read_text())
    p06_root = seal_path.parent.parent
    role = contract['restart_authorization']['sequence_runtime_role']
    source_rows = {r['method_id']: r['source_registry_row'] for r in current_records if r['dataset_id'] == 'BY2'}
    results = []
    p06 = seal['records']
    if len(p06) != 15:
        raise ValueError('Real-manifest regression requires all 15 P06 CAL runs')
    for row in p06:
        root = Path(row['output_root'])
        paths = [root/name for name in ('CALIBRATED_RUN_MANIFEST.json', 'RUN_MANIFEST.json', 'CALIBRATED_RUNTIME_CONFIG.yaml')]
        for path in paths:
            if path.is_symlink() or sha256_file(path) != seal['files_sha256'][path.relative_to(p06_root).as_posix()]:
                raise ValueError('P06 real manifest/config pin changed')
        wrapper, native = (json.loads(p.read_text()) for p in paths[:2])
        config = yaml.safe_load(paths[2].read_text())
        if (wrapper != row or wrapper['native_manifest_sha256'] != sha256_file(paths[1])
                or wrapper['config_hash'] != sha256_file(paths[2]) or native['port_role'] != role):
            raise ValueError('P06 wrapper-to-native role/config lineage failed')
        previous_role = config.get('runtime_role')
        # P06 BY2 has a stale config role that the frozen binary overrode; only
        # this in-memory validator input carries the wrapper-pinned native role.
        config = {**config, 'runtime_role': role}
        source = {**source_rows[row['method_id']], 'case_id': config['case_id'], 'run_id': config['run_id']}
        audit = validate_identity(native, config, source, _bundle_from_config(config, wrapper['provider_hashes']))
        results.append({'origin': 'P06', 'dataset_id': row['dataset_id'], 'method_id': row['method_id'],
                        'passed': audit['passed'], 'original_config_runtime_role': previous_role,
                        'validation_transport_runtime_role': role, 'native_manifest_sha256': wrapper['native_manifest_sha256']})
    current = [r for r in current_records if r['dataset_id'] in ('BY2H', 'BY2O')]
    if len(current) != 22:
        raise ValueError('Real-manifest regression requires all 22 retained sequence runs')
    for row in current:
        root = Path(row['output_root'])
        for name in ('RUN_MANIFEST.json', 'P09C_RUN_TERMINAL.json', 'PROTOCOL_V2_RUNTIME_CONFIG.yaml'):
            if sha256_file(root/name) != row['output_seal'][name]['sha256']:
                raise ValueError('P09c retained real manifest/config pin changed')
        native = json.loads((root/'RUN_MANIFEST.json').read_text())
        text = (root/'PROTOCOL_V2_RUNTIME_CONFIG.yaml').read_text()
        config = yaml.safe_load(append_sequence_runtime_role(text, role)[0])
        audit = validate_identity(native, config, _native_source(row, config), _bundle_from_config(config, row['provider_hashes']))
        results.append({'origin': 'P09c', 'dataset_id': row['dataset_id'], 'method_id': row['method_id'],
                        'passed': audit['passed'], 'native_manifest_sha256': sha256_file(root/'RUN_MANIFEST.json')})
    return {'status': 'PASS', 'read_only': True, 'P06_count': 15, 'P09c_count': 22,
            'passed_count': sum(r['passed'] for r in results), 'records': results}
