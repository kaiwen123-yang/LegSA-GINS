"""Fifteen serial frozen-binary runs, changing only calibrated vrw and abstd."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import time
import yaml

from ..clean5_parity.runtime import (bind_config, expected_counts, check_counters,
                                     diagnostic_counts, EXE_SHA, resolve, write_json, ALLOWED)
from ..clean5_sequence.runtime_config import METHODS, NATIVE_IDENTITY, frozen_parameter_hash
from ..clean5_sequence.solver_runner import audit_solver_openat
from ..clean5_sequence.solver_validation import validate_run_outputs
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .providers import FLAGS, verify_bundle, checked


def run_order(contract):
    if contract['dataset_order'] != ['BY2', 'BY2H', 'BY2O'] or contract['run_profiles'] != list(METHODS):
        raise ValueError('Calibrated chain must use all fifteen registered identities in order')
    return [(d, m) for d in contract['dataset_order'] for m in contract['run_profiles']]


def patch_calibrated_config(original, replacements, model, *, model_sha256, model_commit):
    """Restore every changed line and prove equality to the original config bytes."""
    bound, _ = bind_config(original, replacements)
    lines = bound.splitlines(keepends=True)
    for key in ('vrw', 'abstd'):
        indexes = [i for i, line in enumerate(lines) if line.startswith(key+':')]
        if len(indexes) != 1 or len(model[key]) != 3:
            raise ValueError('Missing/duplicate calibrated vector '+key)
        index = indexes[0]
        newline = '\n' if lines[index].endswith('\n') else ''
        lines[index] = key+': '+json.dumps(model[key], allow_nan=False)+newline
    text = ''.join(lines)
    before, after = yaml.safe_load(original), yaml.safe_load(text)
    if set(before) != set(after):
        raise ValueError('Config key set changed')
    permitted = set(ALLOWED) | {'vrw', 'abstd'}
    changed_keys = [k for k in before if before[k] != after[k]]
    if set(changed_keys)-permitted:
        raise ValueError('Unauthorized calibrated parameter change')
    if set(k for k in changed_keys if k not in ALLOWED) != {'vrw', 'abstd'}:
        raise ValueError('Expected exactly vrw and abstd scientific differences')
    if any(after[k] != before[k] for k in ('initbastd', 'arw', 'gbstd', 'corrtime')):
        raise ValueError('Explicit initial bias/gyro noise/correlation time changed')
    old_lines = original.splitlines(keepends=True)
    if len(old_lines) != len(lines):
        raise ValueError('Runtime config line count changed')
    ledger = []
    restored = list(lines)
    for i, (old, new) in enumerate(zip(old_lines, lines)):
        if old != new:
            key = old.split(':', 1)[0]
            if key not in permitted or new.split(':', 1)[0] != key:
                raise ValueError('Unauthorized config byte difference')
            ledger.append({'key': key, 'line_index': i, 'before': old, 'after': new,
                           'scientific_parameter': key in ('vrw', 'abstd')})
            restored[i] = old
    if ''.join(restored) != original:
        raise ValueError('Complete reverse byte restoration failed')
    return text, {'parameter_byte_diff': ledger, 'changed_keys': sorted(changed_keys),
                  'scientific_parameter_changed_keys': ['abstd', 'vrw'],
                  'all_non_noise_non_transport_bytes_equal': True, 'full_reverse_byte_identity': True,
                  'frozen_parameter_hash': frozen_parameter_hash(text),
                  'reference_frozen_parameter_hash': frozen_parameter_hash(original),
                  'non_calibrated_parameter_hash': frozen_parameter_hash(''.join(restored)),
                  'model_sha256': model_sha256, 'model_freeze_commit': model_commit,
                  'vrw': model['vrw'], 'abstd': model['abstd'], 's': model['s'],
                  'initbastd_unchanged': True, 'arw_unchanged': True, 'gbstd_unchanged': True,
                  'corrtime_unchanged': True, 'parameter_sweep': False, 'per_sequence_refit': False}


def seal_outputs(stage, records, code_commit):
    stage = Path(stage)
    seal_root = stage/'04_CALIBRATED_SEAL'
    hashes = {str(p.relative_to(stage)): sha256_file(p)
              for parent in (stage/'03_CALIBRATED_RUNS', seal_root/'SCHEDULING')
              if parent.exists() for p in parent.rglob('*') if p.is_file()}
    seal = {**FLAGS, 'status': 'SEALED', 'code_commit': code_commit,
            'run_count': len(records), 'completed_count': sum(r['terminal_status'] == 'COMPLETED' for r in records),
            'all_native_success': len(records) == 15 and all(r['terminal_status'] == 'COMPLETED' for r in records),
            'data_mode': 'real_three_sequence_calibrated', 'files_sha256': hashes, 'records': records}
    write_json(seal_root/'CALIBRATED_OUTPUT_SEAL.json', seal)
    return seal


def verify_seal(stage, records):
    stage = Path(stage)
    path = stage/'04_CALIBRATED_SEAL/CALIBRATED_OUTPUT_SEAL.json'
    seal = json.loads(path.read_text())
    if seal['records'] != records:
        raise ValueError('Calibrated seal/records mismatch')
    for relative, expected in seal['files_sha256'].items():
        member = Path(relative)
        if member.is_absolute() or '..' in member.parts or (stage/member).is_symlink() or sha256_file(stage/member) != expected:
            raise ValueError('Calibrated sealed artifact changed')
    return {'path': str(path), 'sha256': sha256_file(path), 'file_count': len(seal['files_sha256'])}


def seal_evaluation_artifacts(stage, code_commit):
    """Freeze completed evaluator outputs and aggregates separately from solver outputs."""
    stage = Path(stage)
    roots = [stage/'07_OFFLINE_EVALUATION', stage/'08_AGGREGATE']
    roots += [stage/d/'08_AGGREGATE' for d in ('BY2', 'BY2H', 'BY2O')]
    if any(not root.is_dir() or root.is_symlink() for root in roots):
        raise ValueError('Missing evaluator/aggregate scope for final sealing')
    if not (stage/'08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.json').is_file():
        raise ValueError('Robustness result is missing before final sealing')
    hashes = {}
    for root in roots:
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink in evaluation artifact scope')
            if path.is_file():
                hashes[path.relative_to(stage).as_posix()] = sha256_file(path)
    payload = {**FLAGS, 'status': 'SEALED', 'code_commit': code_commit,
               'data_mode': 'real_three_sequence_calibrated', 'files_sha256': hashes,
               'file_count': len(hashes), 'scope': [r.relative_to(stage).as_posix() for r in roots],
               'solver_output_seal_unchanged': True, 'trace_input_included': False}
    path = stage/'04_CALIBRATED_SEAL/EVALUATION_ARTIFACT_SEAL.json'
    write_json(path, payload)
    for relative, digest in hashes.items():
        if sha256_file(stage/relative) != digest:
            raise ValueError('Evaluation artifact changed during sealing')
    return {'path': str(path), 'sha256': sha256_file(path), 'file_count': len(hashes)}


def run_chain(*, registry, contract, stage_root, bundles, model, executable, code_commit):
    stage = Path(stage_root)
    executable = Path(executable)
    if executable.is_symlink() or sha256_file(executable) != EXE_SHA:
        raise ValueError('Frozen binary mismatch')
    runs_root = stage/'03_CALIBRATED_RUNS'
    seal_root = stage/'04_CALIBRATED_SEAL'
    runs_root.mkdir(exist_ok=False)
    seal_root.mkdir(exist_ok=False)
    records = []
    for dataset, method in run_order(contract):
        spec = contract['sequences'][dataset]
        run_id = 'CLEAN5_CALIBRATED_'+dataset+'_'+method
        root = runs_root/run_id
        root.mkdir()
        record = {**FLAGS, 'run_id': run_id, 'method_id': method, 'variant_id': 'V2s',
                  'provider_family': 'CLEAN5_CALIBRATED_'+dataset,
                  'classification': 'NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL',
                  'effective_profile': METHODS[method], 'effective_configuration_id': METHODS[method],
                  'dataset_id': dataset, 'data_mode': registry.sequences[dataset].data_mode,
                  'case_id': 'C00_clean_normal' if dataset == 'BY2' else 'CLEAN5_'+dataset+'_NATURAL',
                  'output_root': str(root), 'code_commit': code_commit, 'executable_sha256': EXE_SHA,
                  'model_sha256': contract['model']['sha256'], 'model_freeze_commit': contract['model_freeze_commit'],
                  'terminal_status': 'NOT_STARTED', 'launch_attempted': False,
                  'process_completion_available': False, 'exit_code': None, 'retry_count': 0}
        started = time.monotonic()
        phase = 'CONFIG_PREPARATION'
        cfg = None
        try:
            bundle = bundles[dataset]
            verify_bundle(bundle)
            original_pin = spec['original_configs'][method]
            original_path = checked({'path': original_pin['runtime_config'],
                                     'sha256': original_pin['runtime_config_sha256']}, registry)
            original = original_path.read_text()
            inputs = bundle['variants']['V2s']['providers']
            replacements = {k: v['path'] for k, v in inputs.items()}
            replacements.update(NATIVE_IDENTITY, outputpath=str(root), run_id=run_id, run_label=run_id)
            text, parameter_audit = patch_calibrated_config(original, replacements, model,
                model_sha256=contract['model']['sha256'], model_commit=contract['model_freeze_commit'])
            cfg = yaml.safe_load(text)
            if [cfg['starttime'], cfg['endtime']] != spec['window_seconds']:
                raise ValueError('Frozen sequence window mismatch')
            record.update(parameter_audit, config_hash=hashlib.sha256(text.encode()).hexdigest(),
                          raw_source_hashes=bundle['raw_source_hashes'],
                          provider_hashes={k: v['sha256'] for k, v in inputs.items()},
                          native_identity={k: cfg[k] for k in NATIVE_IDENTITY})
            with (root/'CALIBRATED_RUNTIME_CONFIG.yaml').open('x') as stream:
                stream.write(text)
            record['expected_counters'] = expected_counts(cfg)
            log = root/'SOLVER_OPENAT.strace'
            command = [shutil.which('strace') or 'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat',
                       '-o', str(log), str(executable), '--config', str(root/'CALIBRATED_RUNTIME_CONFIG.yaml'),
                       '--output-dir', str(root), '--debug-update-timeline', '--debug-output-dir', str(root),
                       '--debug-max-rows', '1000000']
            record['command'] = command
            write_json(root/'RUN_STARTED.json', record)
            phase = 'SUBPROCESS'
            record['launch_attempted'] = True
            result = run_process_group(command, cwd=registry.code_root, timeout_seconds=1800,
                                        timeout_message='P06 solver timeout', launch_failure_message='P06 solver launch failed')
            record.update(exit_code=result.returncode, process_completion_available=True)
            (root/'stdout.log').write_text(result.stdout)
            (root/'stderr.log').write_text(result.stderr)
            phase = 'STRACE_AUDIT'
            record['strace_audit'] = audit_solver_openat(log, cwd=registry.code_root, raw_root=registry.raw_root,
                                                        clean_root=registry.clean_root, run_dir=root)
            record['terminal_status'] = 'COMPLETED' if result.returncode == 0 else 'FAILED_NATIVE_SOLVER'
            phase = 'COUNTER_AUDIT'
            native_path = root/'RUN_MANIFEST.json'
            if native_path.exists():
                native = json.loads(native_path.read_text())
                record['native_manifest_sha256'] = sha256_file(native_path)
                record['counter_audit'] = check_counters(native, cfg, record['expected_counters'])
                record['counters'] = record['counter_audit']['actual']
                if not record['counter_audit']['pass']:
                    record['terminal_status'] = 'FAILED_COUNTER_AUDIT'
            else:
                record['counters'] = 'UNAVAILABLE_NATIVE_MANIFEST_NOT_WRITTEN'
                record['diagnostic_trace_counts'] = diagnostic_counts(root)
                if record['terminal_status'] == 'COMPLETED':
                    record['terminal_status'] = 'FAILED_NATIVE_MANIFEST_MISSING'
            if not record['strace_audit']['pass']:
                record['terminal_status'] = 'FAILED_STRACE_AUDIT'
            if record['terminal_status'] == 'COMPLETED':
                phase = 'OUTPUT_VALIDATION'
                record.update(validate_run_outputs(root, {'window_contract': {
                    't_start': spec['window_seconds'][0], 't_end': spec['window_seconds'][1]}}))
                for role, filename in [('nav', 'KF_GINS_Navresult.nav'), ('std', 'KF_GINS_STD.txt')]:
                    record[role+'_path'] = str(root/filename)
                    record[role+'_sha256'] = sha256_file(root/filename)
        except Exception as exc:
            record['terminal_status'] = 'FAILED_'+phase+'_EXCEPTION'
            record.setdefault('errors', []).append({'phase': phase, 'exception_type': type(exc).__name__, 'message': str(exc)})
        record['runtime_seconds'] = time.monotonic()-started
        if cfg is not None:
            from ..clean5_parity.scheduling import audit_scheduling
            try:
                record['auxiliary_scheduling_audit'] = audit_scheduling(config=cfg,
                    output_root=seal_root/'SCHEDULING'/run_id, native_trace=root/'PORT_GNSS_UPDATE_TRACE.csv')
                if (record['terminal_status'] == 'COMPLETED'
                        and record['auxiliary_scheduling_audit'].get('status') != 'SCHEDULING_AUDIT_COMPLETE'):
                    record['terminal_status'] = 'FAILED_SCHEDULING_AUDIT_UNAVAILABLE'
            except Exception as exc:
                record['auxiliary_scheduling_audit'] = {'status': 'FAILED_EXCEPTION', 'message': str(exc)}
                if record['terminal_status'] == 'COMPLETED':
                    record['terminal_status'] = 'FAILED_SCHEDULING_AUDIT_EXCEPTION'
        write_json(root/'CALIBRATED_RUN_MANIFEST.json', record)
        records.append(record)
        print(run_id+': '+record['terminal_status'], flush=True)
        if record['terminal_status'] != 'COMPLETED':
            break
    seal_outputs(stage, records, code_commit)
    return records
