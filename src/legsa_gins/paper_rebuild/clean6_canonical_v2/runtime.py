"""P-09c frozen native execution and input-derived failure classification."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import yaml

from ..clean5_calibrated.runtime import patch_calibrated_config
from ..clean5_degradation.common import FLAGS, pinned, resolve, write_json
from ..clean5_degradation.runtime import (expected_counts, check_auxiliary,
                                         validate_identity, validate_input_opens)
from ..clean5_parity.runtime import check_counters, bind_config
from ..clean5_sequence.runtime_config import NATIVE_IDENTITY
from ..clean5_sequence.solver_runner import audit_solver_openat
from ..clean5_sequence.solver_validation import validate_run_outputs
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group

PROTOCOL = 'CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2'
NUMERICAL_FILES = ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt',
                   'LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv',
                   'KF_GINS_IMU_ERR.txt', 'EVAL_NAV.csv',
                   'PORT_GNSS_UPDATE_TRACE.csv')
PROFILE_KEYS = frozenset(('algorithm_id', 'ablation_variant', 'enable_dual_yaw',
    'enable_receiver_velocity', 'enable_raw_doppler', 'enable_source_aware',
    'enable_go2_roll_pitch_prior', 'enable_go2_horizontal_velocity_prior'))


def csv_rows(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def profile_template(sequence_full, canonical_full, canonical_method):
    """Transfer only frozen profile differences, preserving sequence bytes."""
    full, method = yaml.safe_load(canonical_full), yaml.safe_load(canonical_method)
    differences = {k for k in full if full[k] != method[k]}
    transport = {'outputpath', 'run_id', 'run_label'}
    if differences - PROFILE_KEYS - transport:
        raise ValueError('Unexpected Canonical profile differences')
    tokens = {line.split(':', 1)[0]: line for line in canonical_method.splitlines(keepends=True)}
    changed = differences & PROFILE_KEYS
    result = ''.join(tokens[line.split(':', 1)[0]] if line.split(':', 1)[0] in changed else line
                     for line in sequence_full.splitlines(keepends=True))
    before, after = yaml.safe_load(sequence_full), yaml.safe_load(result)
    if set(before) != set(after) or any(before[k] != after[k] for k in before if k not in changed):
        raise ValueError('Sequence template changed outside registered profile fields')
    return result, sorted(changed)


def classify_all_yaw_rejected(root, cfg, expected, imu):
    """Positive evidence of complete processing; never classify from exit alone."""
    root = Path(root)
    report = {'passed': False, 'classification': 'FAILED_TECHNICAL'}
    if not cfg['enable_dual_yaw'] or expected['dual_yaw_attempt_count'] <= 0:
        return report
    update_path, loop_path = root/'PORT_GNSS_UPDATE_TRACE.csv', root/'PORT_RUNTIME_LOOP_TRACE.csv'
    if not update_path.is_file() or not loop_path.is_file():
        return report
    updates, loops = csv_rows(update_path), csv_rows(loop_path)
    attempts = [r for r in updates if int(r['yaw_update']) > 0]
    initial = int(np.searchsorted(imu[:, 0], cfg['starttime'], side='left'))
    processed = imu[initial+1:]
    processed = processed[processed[:, 0] <= cfg['endtime']]
    complete = (len(loops) == len(processed) > 0 and
                all(int(r['loop_index']) == i for i, r in enumerate(loops)) and
                abs(float(loops[-1]['timestamp_after_process']) - expected['last_processed_imu_time']) <= 0.00051)
    counts = {key: sum(int(r[field]) for r in updates) for key, field in (
        ('position_update_count', 'position_update'),
        ('receiver_velocity_update_count', 'velocity_update'),
        ('dual_yaw_attempt_count', 'yaw_update'))}
    # Frozen update trace logs native velocity attempts even when RV is disabled;
    # this classification only applies to the enabled robust-yaw profiles.
    counters_equal = all(counts[k] == expected[k] for k in counts)
    yaw_rejected = (len(attempts) == expected['dual_yaw_attempt_count'] and
                    all(int(r['yaw_update']) == 1 and r['yaw_mode'] == 'REJECT' for r in attempts))
    stderr = (root/'stderr.log').read_text()
    native_reason = ('FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch'
                     in stderr)
    passed = complete and counters_equal and yaw_rejected and native_reason
    return {**report, 'passed': passed,
            'classification': 'ALGORITHM_FAILURE_ALL_YAW_REJECTED' if passed else 'FAILED_TECHNICAL',
            'full_window_processed': complete, 'loop_rows': len(loops),
            'expected_loop_rows': len(processed), 'counters': counts,
            'yaw_accepted_count': 0 if yaw_rejected else None,
            'all_attempts_rejected': yaw_rejected, 'native_contract_error': native_reason,
            'final_native_manifest_available': (root/'RUN_MANIFEST.json').is_file(),
            'update_trace_sha256': sha256_file(update_path), 'loop_trace_sha256': sha256_file(loop_path)}


def seal_run(root):
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in run seal')
        if path.is_file():
            if path.name == 'OUTPUT_SEAL.json':
                raise FileExistsError('Run already sealed; no automatic retry')
            files[path.relative_to(root).as_posix()] = {'sha256': sha256_file(path), 'size_bytes': path.stat().st_size}
    write_json(root/'OUTPUT_SEAL.json', {'status': 'SEALED_BEFORE_EVALUATION', 'files': files})
    return files


def run_one(source, bundle, contract, reg, run_root, code_commit, *, original_text=None,
            dataset='BY2', sequence_spec=None, case_meta=None):
    root = Path(run_root)
    root.mkdir(parents=True, exist_ok=False)
    spec = sequence_spec or {'window_seconds': contract['evaluation']['window'],
                            'base_time': contract['evaluation']['base_time'],
                            'baseline_median_m': contract['evaluation']['v3_baseline_median_m'],
                            'trace': contract['evaluation']['trace']}
    inputs = bundle['providers']
    record = {**FLAGS, 'protocol_id': PROTOCOL, 'chain': 'CAL', 'dataset_id': dataset,
              'run_id': source['run_id'], 'method_id': source['method_id'],
              'case_id': source['case_id'], 'case_family': source.get('case_family', 'natural_sequence'),
              'degradation_type_id': source.get('degradation_type_id', 'CLEAN'),
              'seed_index': source.get('seed_index', ''), 'effective_profile': source['effective_profile'],
              'source_registry_row': source, 'case_meta': case_meta,
              'output_root': str(root), 'code_commit': code_commit,
              'data_mode': 'real_base_controlled_degradation' if source['case_id'].startswith('D') else 'real_clean',
              'controlled_degradation_applied': source['case_id'].startswith('D'),
              'raw_source_hashes': bundle.get('raw_input_hashes', bundle.get('raw_source_hashes')),
              'provider_hashes': {k: v['sha256'] for k, v in inputs.items()},
              'retry_count': 0, 'launch_attempted': False, 'terminal_status': 'NOT_STARTED',
              'window': spec['window_seconds'], 'base_time': spec['base_time'],
              'baseline_median_m': spec['baseline_median_m'], 'trace': spec['trace']}
    started = time.monotonic()
    cfg = None
    try:
        if original_text is None:
            original_path = Path(source['runtime_config_path'])
            if sha256_file(original_path) != source['runtime_config_file_hash']:
                raise ValueError('Frozen runtime template changed')
            original_text = original_path.read_text()
        model = yaml.safe_load(pinned(contract['runtime']['model'], reg).read_text())
        replacements = {k: v['path'] for k, v in inputs.items()}
        replacements['outputpath'] = str(root)
        if dataset != 'BY2':
            replacements.update(NATIVE_IDENTITY, run_id=source['run_id'], run_label=source['run_id'])
        text, diff = patch_calibrated_config(original_text, replacements, model,
            model_sha256=contract['runtime']['model']['sha256'],
            model_commit=contract['runtime']['model_freeze_commit'])
        cfg = yaml.safe_load(text)
        if [cfg['starttime'], cfg['endtime']] != spec['window_seconds']:
            raise ValueError('Frozen sequence window changed')
        cfg_path = root/'PROTOCOL_V2_RUNTIME_CONFIG.yaml'
        cfg_path.write_text(text)
        record.update(config_hash=hashlib.sha256(text.encode()).hexdigest(), config_byte_diff=diff,
                      native_identity={k: cfg[k] for k in ('stage_id', 'protocol_id', 'run_id', 'case_id', 'data_mode')},
                      executable_sha256=contract['runtime']['executable']['sha256'],
                      scientific_solver_commit=contract['runtime']['scientific_solver_commit'])
        imu = np.loadtxt(inputs['imupath']['path'], ndmin=2)
        gnss = np.loadtxt(inputs['gnsspath']['path'], ndmin=2)
        expected = expected_counts(cfg, gnss, imu)
        record['expected_counters'] = expected
        tmp = root/'tmp'
        tmp.mkdir()
        log = root/'SOLVER_OPENAT.strace'
        command = ['env', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1',
            'NUMEXPR_NUM_THREADS=1', 'TMPDIR='+str(tmp),
            'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat', '-o', str(log),
            str(resolve(contract['runtime']['executable']['path'], reg)), '--config', str(cfg_path),
            '--output-dir', str(root), '--debug-update-timeline', '--debug-output-dir', str(root),
            '--debug-max-rows', '1000000']
        record.update(command=command, launch_attempted=True)
        write_json(root/'RUN_STARTED.json', record)
        solve_start = time.monotonic()
        result = run_process_group(command, cwd=reg.code_root, timeout_seconds=contract['runtime']['timeout_s'],
            timeout_message='P09c solver timeout; no retry', launch_failure_message='P09c launch failure; no retry')
        record.update(solver_seconds=time.monotonic()-solve_start, exit_code=result.returncode)
        (root/'stdout.log').write_text(result.stdout)
        (root/'stderr.log').write_text(result.stderr)
        record['strace_audit'] = audit_solver_openat(log, cwd=reg.code_root, raw_root=reg.raw_root,
                                                   clean_root=reg.clean_root, run_dir=root)
        if not record['strace_audit']['pass']:
            raise ValueError('Solver open audit failed')
        # Input identity is checked even when the frozen executable aborts before writeAll.
        enabled = {'propagation_imu': cfg['imupath'], 'gnss': cfg['gnsspath']}
        for flag, key in [('enable_raw_doppler', 'raw_doppler_factor_path'),
                          ('enable_go2_roll_pitch_prior', 'go2_attitude_prior_path'),
                          ('enable_go2_horizontal_velocity_prior', 'go2_horizontal_velocity_prior_path')]:
            if cfg[flag]: enabled[key] = cfg[key]
        record['input_open_audit'] = validate_input_opens(log, enabled, reg, root, cfg_path)
        if result.returncode != 0:
            classification = classify_all_yaw_rejected(root, cfg, expected, imu)
            record['failure_classification'] = classification
            if not classification['passed']:
                raise RuntimeError('FAILED_NATIVE_SOLVER_UNCLASSIFIED')
            record['terminal_status'] = classification['classification']
            record['native_manifest_status'] = 'UNAVAILABLE_NATIVE_WRITEALL_NOT_REACHED'
        else:
            native = json.loads((root/'RUN_MANIFEST.json').read_text())
            native_source = {**source, 'case_id': cfg['case_id'], 'run_id': cfg['run_id']}
            record['native_identity_audit'] = validate_identity(native, cfg, native_source, bundle)
            record['counter_audit'] = check_counters(native, cfg, expected)
            record['auxiliary_counter_audit'] = check_auxiliary(native, cfg, expected)
            if not record['counter_audit']['pass'] or not record['auxiliary_counter_audit']['pass']:
                raise ValueError('Input-derived runtime counters failed')
            record['counters'] = record['counter_audit']['actual']
            record['output_validation'] = validate_run_outputs(root, {'window_contract': {
                't_start': cfg['starttime'], 't_end': cfg['endtime']}})
            record['terminal_status'] = 'COMPLETED'
    except Exception as error:
        record.update(terminal_status='FAILED_TECHNICAL', failure_type=type(error).__name__, failure=str(error))
    record['runtime_seconds'] = time.monotonic()-started
    write_json(root/'P09C_RUN_TERMINAL.json', record)
    record['output_seal'] = seal_run(root)
    record['solver_output_bytes'] = sum(v['size_bytes'] for v in record['output_seal'].values())
    return record
