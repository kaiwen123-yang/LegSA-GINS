"""Frozen 50-run F01 byte audit, complete lossless retention and exact cleanup.

Formal F01 outputs remain the original v2 outputs. These separate audit runs
use old v2 providers/std and the bridged executable; no evaluator is imported.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

import yaml

from ..clean5_degradation.common import FLAGS, pinned, read_csv, resolve, write_json
from ..clean6_canonical_v2.archive_io import stream_copy, ArchiveRetryPending
from ..clean6_canonical_v2.io_recovery import ScientificStop
from ..clean6_canonical_v2.storage import inventory, gzip_copy, cleanup_exact, append_json
from ..manifest import sha256_file
from .runtime import run_one

FILES = ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt', 'LegSA_PORT_NAV.nav',
         'LegSA_PORT_STD.csv', 'KF_GINS_IMU_ERR.txt', 'EVAL_NAV.csv', 'PORT_GNSS_UPDATE_TRACE.csv')


def selected_samples(spec, runs):
    """Reproduce the output-independent preregistered sample order exactly."""
    f01 = [row for row in runs if row['method_id'] == 'F01']
    clean = [row for row in f01 if row['case_id'] == 'C00_clean_normal']
    degraded = sorted((row for row in f01 if row['case_id'] != 'C00_clean_normal'),
        key=lambda row: hashlib.sha256(('P13_F01|' + row['case_id']).encode()).hexdigest())
    expected = [{key: row[key] for key in ('run_id', 'case_id', 'method_id')}
                for row in clean + degraded[:49]]
    if (len(f01) != 541 or len(clean) != 1 or len(expected) != 50 or
            len({row['run_id'] for row in expected}) != 50 or
            spec['samples'] != expected or spec['extra_audit_solver_runs'] != 50 or
            tuple(spec['compared_files']) != FILES or spec['evaluator_rerun'] is not False):
        raise ValueError('F01 sample/order/file-set contract differs')
    return expected


def compare_seven(actual_root, frozen_record):
    """Compare complete source bytes through the original v2 full-file seals."""
    results = []
    for name in FILES:
        pin = frozen_record['output_seal'][name]
        path = Path(actual_root) / name
        exists = path.is_file() and not path.is_symlink()
        size = path.stat().st_size if exists else None
        digest = sha256_file(path) if exists else None
        results.append({'filename': name, 'reference_sha256': pin['sha256'],
                        'actual_sha256': digest, 'reference_size_bytes': pin['size_bytes'],
                        'actual_size_bytes': size,
                        'byte_identical': digest == pin['sha256'] and size == pin['size_bytes']})
    return {'status': 'PASS' if all(row['byte_identical'] for row in results) else 'FAIL',
            'comparisons': results, 'file_count': 7,
            'reference': 'v2 BATCHES/RUN_RECORDS output_seal full native files',
            'sparse_NAV_used': False, 'formal_F01_output_replaced': False}


def references(ctx, samples):
    """Load only selected v2 run records and exact retained CAL config bytes."""
    old_root = resolve(ctx.v2['stage_root'], ctx.reg)
    selected = {item['run_id']: item for item in samples}
    records = {}
    record_paths = sorted((old_root / 'BATCHES').glob('BATCH_*/RUN_RECORDS.json'))
    # P09c batch 8 interrupted before its original RUN_RECORDS publication.
    # Its authorized I/O continuation retains the same native output seals.
    recovered_batch8 = old_root / 'IO_RECOVERY/IO_RECOVERY_20260912/BATCH_008_RECOVERY/RUN_RECORDS.json'
    if not (old_root / 'BATCHES/BATCH_008/RUN_RECORDS.json').exists() and recovered_batch8.exists():
        record_paths.append(recovered_batch8)
    for path in record_paths:
        rows = json.loads(path.read_text())
        matches = [row for row in rows if row['run_id'] in selected]
        if not matches:
            continue
        source_pin = {'path': str(path), 'sha256': sha256_file(path)}
        for row in matches:
            rid = row['run_id']
            if rid in records:
                raise ValueError('Duplicate F01 reference run in original v2 batch ledgers')
            if (row['method_id'] != 'F01' or row['case_id'] != selected[rid]['case_id'] or
                    row['terminal_status'] != 'COMPLETED' or
                    not set(FILES) <= set(row['output_seal'])):
                raise ValueError('Frozen F01 source identity/seal incomplete')
            archive_receipt = Path(row['archive_receipt'])
            receipt = json.loads(archive_receipt.read_text())
            if receipt['status'] != 'ARCHIVE_VERIFIED':
                raise ValueError('Original F01 archive was not verified')
            cfg_path = archive_receipt.parent / 'solver/PROTOCOL_V2_RUNTIME_CONFIG.yaml'
            text = pinned({'path': str(cfg_path), 'sha256': row['config_hash']}, ctx.reg).read_text()
            cfg = yaml.safe_load(text)
            if cfg['basic_dual_yaw_fixed_std_deg'] != 1.5 or cfg['enable_dual_yaw']:
                raise ValueError('F01 reference is not the frozen std=1.5 profile')
            bundle_path = old_root / '02_PROVIDERS' / row['case_id'] / 'PROVIDER_BUNDLE.json'
            bundle = json.loads(bundle_path.read_text())
            if {key: value['sha256'] for key, value in bundle['providers'].items()} != row['provider_hashes']:
                raise ValueError('Frozen F01 provider bundle differs from v2 native record')
            records[rid] = {'record': row, 'bundle': bundle, 'original_text': text,
                'reference_record_pin': source_pin, 'reference_config_path': str(cfg_path),
                'reference_bundle_pin': {'path': str(bundle_path), 'sha256': sha256_file(bundle_path)}}
    if set(records) != set(selected):
        raise ValueError('Selected F01 full-file seals unavailable: ' + str(set(selected) - set(records)))
    return records


def _verify_receipt(receipt, *, check_payload=False):
    if receipt.get('status') != 'ARCHIVE_VERIFIED' or not receipt.get('all_full_files_retained'):
        raise ValueError('F01 full archive receipt is incomplete')
    root = Path(receipt['archive_root'])
    for relative, pin in receipt['retained_files'].items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size != pin['size_bytes']:
            raise ValueError('F01 archive member missing/changed')
        if check_payload and sha256_file(path) != pin['sha256']:
            raise ValueError('F01 archive hash changed')
    for name in FILES:
        matched = [pin for pin in receipt['retained_files'].values() if pin['source_relative_path'] == name]
        if len(matched) != 1 or matched[0]['source_sha256'] != receipt['original_files']['native'][name]['sha256']:
            raise ValueError('Full F01 comparison file absent from archive')


def archive_full(record, archive_parent, scratch_parent, code_commit):
    """Retain every native file; numerical files are lossless gzip, never thin."""
    source = Path(record['output_root'])
    archive_parent, scratch_parent = Path(archive_parent), Path(scratch_parent)
    archive_parent.mkdir(parents=True, exist_ok=True)
    prior = sorted(archive_parent.glob('ATTEMPT_*/ARCHIVE_RECEIPT.json'))
    if prior:
        receipt = json.loads(prior[-1].read_text())
        _verify_receipt(receipt)
        return receipt
    attempts = [path.name for parent in (archive_parent, scratch_parent)
                for path in parent.glob('ATTEMPT_*')]
    number = max([int(name.rsplit('_', 1)[1]) for name in attempts] or [0]) + 1
    label = f'ATTEMPT_{number:03d}'
    destination, staging = archive_parent / label, scratch_parent / label
    original = inventory(source)
    if not set(FILES) <= set(original):
        raise ValueError('Cannot archive incomplete F01 numerical output')
    staging.mkdir(parents=True, exist_ok=False)
    retained = {}
    for relative, pin in original.items():
        actual = source / relative
        compress = actual.suffix not in ('.json', '.yaml', '.yml', '.gz')
        target_rel = relative + ('.gz' if compress else '')
        target = staging / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if compress:
            if gzip_copy(actual, target) != pin['sha256']:
                raise ValueError('F01 source changed during lossless compression')
        else:
            with actual.open('rb') as reader, target.open('xb') as writer:
                shutil.copyfileobj(reader, writer, 8 * 1024 * 1024)
            if sha256_file(target) != pin['sha256']:
                raise ValueError('F01 source changed during metadata copy')
        retained[target_rel] = {'sha256': sha256_file(target), 'size_bytes': target.stat().st_size,
            'source_sha256': pin['sha256'], 'source_size_bytes': pin['size_bytes'],
            'source_relative_path': relative, 'compression': 'gzip' if compress else 'identity'}
    destination.mkdir(parents=True, exist_ok=False)
    for relative, pin in retained.items():
        result = stream_copy(staging / relative, destination / relative,
            expected_sha256=pin['sha256'], expected_size_bytes=pin['size_bytes'], staging_root=staging)
        pin['write_verification'] = result
    receipt = {**FLAGS, 'data_mode': record.get('data_mode', 'audit_metadata'),
        'semisynthetic_data_used': record.get('semisynthetic_data_used', False),
        'status': 'ARCHIVE_VERIFIED', 'archive_root': str(destination),
        'run_id': record['run_id'], 'archive_code_commit': code_commit,
        'source_root': str(source), 'staging_root': str(staging),
        'all_full_files_retained': True, 'sparse_NAV_created': False,
        'original_files': {'native': original, 'staging': inventory(staging)},
        'retained_files': retained, 'evaluator_invocation_count': 0}
    write_json(destination / 'ARCHIVE_RECEIPT.json', receipt)
    _verify_receipt(receipt)
    return receipt


def cleanup_resume(root, files, ledger_path, *, scratch_root):
    """Resume exact verified-inventory deletion without repeating a solve."""
    root, ledger_path = Path(root), Path(ledger_path)
    known = {}
    if ledger_path.is_file():
        for line in ledger_path.read_text().splitlines():
            entry = json.loads(line)
            known[entry['path']] = entry
    remaining = {}
    for relative, pin in files.items():
        path = root / relative
        if path.is_file() or path.is_symlink():
            remaining[relative] = pin
        else:
            prior = known.get(str(path), {})
            if prior.get('status') not in ('DELETE_INTENT', 'DELETED', 'DELETED_RECOVERED') or prior.get('sha256') != pin['sha256']:
                raise ValueError('Missing F01 scratch file has no exact authorized cleanup record')
            if prior['status'] == 'DELETE_INTENT':
                append_json(ledger_path, {'status': 'DELETED_RECOVERED', 'path': str(path), **pin})
    cleanup_exact(root, remaining, ledger_path, scratch_root=scratch_root, archive_verified=True)


def run_audit(ctx):
    """Run/reuse fifty sealed audits; publish F01_INVARIANCE_GATE on completion."""
    from .controller import effective_contract, dump_status, note
    spec = ctx.v21['scope_and_accounting']['F01']
    runs = read_csv(pinned(ctx.v2['sources']['unique_run_registry'], ctx.reg))
    samples = selected_samples(spec, runs)
    root = ctx.stage / '03_F01_INVARIANCE'
    root.mkdir(parents=True, exist_ok=True)
    gate_path = root / 'F01_INVARIANCE_GATE.json'
    if gate_path.exists():
        result = json.loads(gate_path.read_text())
        if result['status'] != 'PASS':
            raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE', 'Prior F01 invariant gate failed')
        return result
    contract = effective_contract(ctx)
    reference = references(ctx, samples)
    recovered = [rid for rid, ref in reference.items()
                 if '/IO_RECOVERY/' in ref['reference_record_pin']['path']]
    if recovered:
        note(ctx, 'F01_REFERENCE_RECORD_LOCATION', run_ids=recovered,
             reason='P09c batch8 original RUN_RECORDS absent after archival interruption; exact authorized recovery RUN_RECORDS supplies unchanged full native seals')
    scratch = ctx.scratch / 'F01_INVARIANCE'
    results = []
    cache = set()
    for index, sample in enumerate(samples, 1):
        rid = sample['run_id']
        directory = root / 'RUNS' / rid
        directory.mkdir(parents=True, exist_ok=True)
        complete_path = directory / 'RUN_COMPLETE.json'
        if complete_path.exists():
            complete = json.loads(complete_path.read_text())
            if complete['comparison']['status'] != 'PASS':
                raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE', 'Prior F01 byte gate failed')
            _verify_receipt(complete['archive_receipt'])
            results.append(complete)
            continue
        ref = reference[rid]
        for entry in ref['bundle']['providers'].values():
            key = (entry['path'], entry['sha256'])
            if key not in cache:
                pinned(entry, ctx.reg)
                cache.add(key)
        native_root = scratch / rid / 'solver'
        record_path = directory / 'NATIVE_RECORD.json'
        if record_path.exists():
            record = json.loads(record_path.read_text())
        elif (native_root / 'P13_RUN_TERMINAL.json').exists():
            record = json.loads((native_root / 'P13_RUN_TERMINAL.json').read_text())
            seal_path = native_root / 'OUTPUT_SEAL.json'
            if seal_path.exists():
                record['output_seal'] = json.loads(seal_path.read_text())['files']
            write_json(record_path, record)
        elif native_root.exists():
            raise ValueError('Interrupted F01 launch needs terminal-evidence reconciliation; no native repeat')
        else:
            source = copy.deepcopy(ref['record']['source_registry_row'])
            record = run_one(source, ref['bundle'], contract, ctx.reg, native_root, ctx.code_commit,
                original_text=ref['original_text'], dataset='BY2',
                sequence_spec=ctx.v2['sequences']['BY2'], case_meta=ref['record'].get('case_meta'),
                sensor_corrections=False, apply_calibration=True)
            write_json(record_path, record)
        if record.get('exit_code') != 0:
            raise ScientificStop('NATIVE_UNREGISTERED_FAILURE', 'F01 native failure: ' + rid)
        if not record.get('strace_audit', {}).get('pass'):
            raise ValueError('F01 access audit requires evidence reconciliation; preserve native output and do not repeat it')
        comparison_path = directory / 'BYTE_COMPARISON.json'
        if comparison_path.exists():
            comparison = json.loads(comparison_path.read_text())
        else:
            comparison = compare_seven(native_root, ref['record'])
            comparison.update(run_id=rid, case_id=sample['case_id'],
                source_record=ref['reference_record_pin'], source_config_path=ref['reference_config_path'],
                source_bundle=ref['reference_bundle_pin'], executable_sha256=record['executable_sha256'])
            write_json(comparison_path, comparison)
        if comparison['status'] != 'PASS':
            raise ScientificStop('SEQUENCE_OR_C00_BYTE_GATE_FAILURE', 'F01 full-file byte mismatch: ' + rid)
        if record['terminal_status'] != 'COMPLETED':
            note(ctx, 'F01_VALIDATION_MECHANISM', run_id=rid,
                 original_terminal=record['terminal_status'], byte_comparison='PASS_7_FULL_FILES')
        try:
            receipt = archive_full(record, directory / 'ARCHIVE', scratch / rid / 'archive_staging', ctx.code_commit)
        except (OSError, ArchiveRetryPending) as error:
            append_json(root / 'ARCHIVE_FAILURES.jsonl', {'run_id': rid, 'failure': str(error),
                        'failed_runs': 1, 'batch_run_count': 50, 'failure_fraction': 1 / 50})
            raise ScientificStop('BATCH_ARCHIVE_FAILURE_OVER_ONE_PERCENT', str(error)) from error
        _verify_receipt(receipt)
        cleanup_resume(native_root, receipt['original_files']['native'], root / 'CLEANUP_LEDGER.jsonl', scratch_root=ctx.scratch)
        cleanup_resume(receipt['staging_root'], receipt['original_files']['staging'], root / 'CLEANUP_LEDGER.jsonl', scratch_root=ctx.scratch)
        complete = {**FLAGS, 'status': 'PASS', 'run_id': rid, 'case_id': sample['case_id'],
                    'data_mode': record['data_mode'],
                    'semisynthetic_data_used': record.get('semisynthetic_data_used', False),
                    'comparison': comparison, 'archive_receipt': receipt,
                    'native_call_count': 1, 'native_repeat_count': 0, 'evaluator_call_count': 0,
                    'code_commit': ctx.code_commit, 'formal_F01_output_replaced': False,
                    'audit_sensor_corrections_applied': False, 'input_sensor_model': 'V2_STD_1_5'}
        write_json(complete_path, complete)
        results.append(complete)
        dump_status(ctx, phase='F01_INVARIANCE', status='RUNNING', completed_F01_audits=index, total_F01_audits=50)
        print('P13_F01_BYTE_AUDIT', index, '/50', rid, 'PASS_7_FULL_FILES_ARCHIVED_CLEANED', flush=True)
    result = {**FLAGS, 'status': 'PASS', 'data_mode': 'real_and_registered_degradation_audits',
        'semisynthetic_data_used': True,
        'sample_count': 50, 'native_calls': 50, 'native_repeat_calls': 0, 'evaluator_calls': 0,
        'passed_run_count': len(results), 'passed_file_count': 7 * len(results),
        'compared_files': list(FILES), 'sample_rule': spec['sample_rule_requirement'],
        'samples': samples, 'formal_F01_outputs': 'BYTE_EXACT_V2_REUSE',
        'audit_outputs_replace_formal_F01': False, 'sparse_NAV_used': False,
        'all_full_numerical_files_losslessly_archived': True, 'code_commit': ctx.code_commit,
        'run_receipt_hashes': {sample['run_id']: sha256_file(root / 'RUNS' / sample['run_id'] / 'RUN_COMPLETE.json')
                              for sample in samples}}
    write_json(gate_path, result)
    dump_status(ctx, phase='F01_INVARIANCE', status='PASS', completed_F01_audits=50)
    return result
