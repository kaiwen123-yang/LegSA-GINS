"""Authorized archive/controller recovery; scientific freezes remain immutable."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

import yaml

from ..clean5_degradation.common import registry, resolve
from ..manifest import sha256_file as _sha256_file
from .storage import ResourceMonitor, machine_state
from .archive_io import retry_io

BASE = 'src/legsa_gins/paper_rebuild/clean6_canonical_v2/'
IO_ALLOWLIST = frozenset((BASE+'runner.py', BASE+'storage.py', BASE+'archive_io.py', BASE+'io_recovery.py',
    'scripts/paper_rebuild/clean6_recover_canonical541_v2_io.py',
    'tests/paper_rebuild/test_clean6_archive_io.py', 'tests/paper_rebuild/test_clean6_io_recovery.py',
    'configs/paper_rebuild/clean6/CANONICAL_541_PROTOCOL_V2_CONTRACT.yaml'))
SCIENTIFIC_COMMIT = '737a0fb5a4a5418500824855b89b0d25af69824a'


def now():
    return datetime.now(timezone.utc).isoformat()


def _read(path, expected_sha256=None):
    value, _ = retry_io(lambda: Path(path).read_bytes(), source=path, destination=path, operation='controller_json_read')
    if expected_sha256 is not None and hashlib.sha256(value).hexdigest() != expected_sha256:
        raise ValueError('Controller metadata bytes differ from pinned independent audit')
    return json.loads(value)


def sha256_file(path):
    digest, _ = retry_io(lambda: _sha256_file(path), source=path, destination=path, operation='controller_file_hash')
    return digest


def _metadata_bytes(path, data, *, append):
    """Replay the same bytes at a captured offset; retries never duplicate rows."""
    path = Path(path)
    retry_io(lambda: path.parent.mkdir(parents=True, exist_ok=True), source=path, destination=path,
             operation='controller_metadata_parent')
    reserved = False
    def reserve():
        nonlocal reserved
        if reserved:
            return path.stat().st_size
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if not append:
                raise
        else:
            reserved = True
            os.close(fd)
        return path.stat().st_size
    offset, _ = retry_io(reserve, source=path, destination=path, operation='controller_metadata_reserve')
    if not append and offset:
        raise ValueError('New controller metadata is not empty')
    def persist():
        with path.open('r+b', buffering=0) as stream:
            stream.seek(offset)
            present = stream.read()
            if len(present) > len(data) or not data.startswith(present):
                raise ValueError('Controller metadata changed outside its owned write')
            stream.seek(offset)
            view = memoryview(data)
            while view:
                written = stream.write(view)
                if not written:
                    raise OSError(5, 'No controller metadata write progress')
                view = view[written:]
            stream.flush()
            os.fsync(stream.fileno())
    retry_io(persist, source=path, destination=path, operation='controller_metadata_write')


def write_json(path, payload):
    _metadata_bytes(path, (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode(), append=False)


def append_json(path, payload):
    _metadata_bytes(path, (json.dumps(payload, ensure_ascii=False, allow_nan=False)+'\n').encode(), append=True)


def _git(code_root, *args):
    return subprocess.check_output(['git', *args], cwd=code_root)


def io_root(stage, identifier):
    if not identifier or Path(identifier).name != identifier or identifier in ('.', '..'):
        raise ValueError('Invalid explicit I/O recovery identity')
    return Path(stage)/'IO_RECOVERY'/identifier


def verify_source_changes(original_pins, actual_pins, allowed):
    """The whitelist permits exact file changes, never missing scientific pins."""
    changed = {}
    for path, digest in original_pins.items():
        actual = actual_pins.get(path)
        if actual is None:
            raise ValueError('Frozen source missing: '+path)
        if actual != digest:
            if path not in allowed:
                raise ValueError('Scientific source changed outside I/O whitelist: '+path)
            changed[path] = {'old_sha256': digest, 'new_sha256': actual}
    for path in allowed-set(original_pins):
        if path in actual_pins:
            changed[path] = {'old_sha256': None, 'new_sha256': actual_pins[path]}
    return changed


def register_io_freeze(contract_path, reg, identifier):
    contract_path = Path(contract_path).resolve()
    current = yaml.safe_load(contract_path.read_text())
    appendix = current.get('io_recovery_authorization', {})
    if appendix.get('io_fix_id') != identifier or appendix.get('scientific_code_commit') != SCIENTIFIC_COMMIT:
        raise ValueError('Missing exact approved I/O authorization')
    allowed = set(appendix['allowed_changed_paths'])
    if not allowed or allowed-IO_ALLOWLIST:
        raise ValueError('I/O authorization exceeds compiled narrow whitelist')
    stage = resolve(current['stage_root'], reg)
    continuation = stage/'RESTARTS'/current['restart_authorization']['restart_id']/'CONTINUATION_FREEZE.json'
    old = _read(continuation)
    if old['code_commit'] != SCIENTIFIC_COMMIT:
        raise ValueError('Scientific continuation identity differs')
    relative = contract_path.relative_to(reg.code_root).as_posix()
    old_bytes = _git(reg.code_root, 'show', SCIENTIFIC_COMMIT+':'+relative)
    if hashlib.sha256(old_bytes).hexdigest() != old['contract_hash']:
        raise ValueError('Original scientific contract hash differs')
    scientific = dict(current)
    scientific.pop('io_recovery_authorization')
    if scientific != yaml.safe_load(old_bytes):
        raise ValueError('I/O appendix changed existing scientific contract semantics')
    # The approved append-only contract is separate from the source whitelist.
    allowed.add(relative)
    head = _git(reg.code_root, 'rev-parse', 'HEAD').decode().strip()
    if _git(reg.code_root, 'diff', '--name-only', 'HEAD').strip():
        raise ValueError('I/O controller and appendix must be committed before freeze')
    if head == SCIENTIFIC_COMMIT or _git(reg.code_root, 'show', 'HEAD:'+relative) != contract_path.read_bytes():
        raise ValueError('Missing separate committed I/O repair')
    actual = {path: sha256_file(reg.code_root/path) for path in set(old['source_sha256'])|allowed
              if (reg.code_root/path).is_file()}
    changed = verify_source_changes(old['source_sha256'], actual, allowed)
    for path in allowed:
        if path in actual and _git(reg.code_root, 'show', 'HEAD:'+path) != (reg.code_root/path).read_bytes():
            raise ValueError('I/O implementation is not committed: '+path)
    target = io_root(stage, identifier)
    target.mkdir(parents=True, exist_ok=True)
    if (target/'IO_FIX_FREEZE.json').exists() or (target/'SCIENTIFIC_CONTRACT.yaml').exists():
        raise ValueError('I/O freeze already exists; preserve its original identity')
    scientific_path = target/'SCIENTIFIC_CONTRACT.yaml'
    with scientific_path.open('xb') as stream:
        stream.write(old_bytes)
    freeze = {'status': 'IO_FIX_FROZEN', 'io_fix_id': identifier, 'io_fix_code_commit': head,
        'scientific_code_commit': SCIENTIFIC_COMMIT, 'scientific_contract_path': str(scientific_path),
        'scientific_contract_sha256': old['contract_hash'], 'continuation_freeze_path': str(continuation),
        'continuation_freeze_sha256': sha256_file(continuation), 'original_source_sha256': old['source_sha256'],
        'source_sha256': actual, 'authorized_path_changes': changed, 'allowed_changed_paths': sorted(allowed),
        'current_contract_path': str(contract_path), 'current_contract_sha256': sha256_file(contract_path),
        'unchanged_frozen_pin_count': sum(p not in changed for p in old['source_sha256']),
        'created_utc': now(), 'solver_evaluator_provider_calls_during_freeze': 0}
    write_json(target/'IO_FIX_FREEZE.json', freeze)
    return freeze


def validate_io_freeze(freeze, reg):
    if freeze['scientific_code_commit'] != SCIENTIFIC_COMMIT:
        raise ValueError('Scientific code identity was replaced by I/O repair identity')
    for path_key, hash_key in (('scientific_contract_path', 'scientific_contract_sha256'),
                              ('current_contract_path', 'current_contract_sha256'),
                              ('continuation_freeze_path', 'continuation_freeze_sha256')):
        if sha256_file(Path(freeze[path_key])) != freeze[hash_key]:
            raise ValueError('I/O or original execution freeze changed: '+path_key)
    for relative, expected in freeze['source_sha256'].items():
        if sha256_file(reg.code_root/relative) != expected:
            raise ValueError('Source changed after I/O freeze: '+relative)
    return True


def load_pending(root):
    path = Path(root)/'ARCHIVE_PENDING_LEDGER.jsonl'
    state = {}
    if path.is_file():
        lines, _ = retry_io(lambda: path.read_text().splitlines(), source=path, destination=path,
                           operation='controller_pending_ledger_read')
        for line in lines:
            event = json.loads(line)
            if event['status'] == 'ARCHIVE_PENDING':
                state[event['run_id']] = event['job']
            elif event['status'] == 'ARCHIVE_RESOLVED':
                state.pop(event['run_id'], None)
    return state


def pending_gate(count, denominator):
    if count < 0 or denominator <= 0 or count > denominator:
        raise ValueError('Invalid unique pending denominator')
    return {'pending_unique_count': count, 'unique_denominator': denominator,
            'pending_fraction': count/denominator, 'status': 'PASS' if count*100 <= denominator else 'STOP_PENDING_OVER_ONE_PERCENT'}


def _relocate(record, evaluations, destination, scratch_batch):
    record, evaluations = copy.deepcopy(record), copy.deepcopy(evaluations)
    destination, scratch_batch = Path(destination), Path(scratch_batch)
    record['scratch_output_root'] = record['output_root']
    record['output_root'] = str(destination/'solver')
    record['archive_receipt'] = str(destination/'ARCHIVE_RECEIPT.json')
    record['archive_status'] = 'ARCHIVE_VERIFIED'
    for row in evaluations:
        version = row['evaluator_version']
        original = scratch_batch/'12_OFFLINE_EVALUATION'/version/record['run_id']
        for key in ('evaluation_output_root', 'source_row', 'error_series_source', 'summary_source'):
            if row.get(key):
                path = Path(row[key])
                if not path.is_relative_to(original):
                    raise ValueError('Evaluation artifact escapes registered scratch run: '+key)
                row[key] = str(destination/version/path.relative_to(original))
        row['output_root'] = str(destination/'solver')
        row['native_run_manifest'] = str(destination/'solver/RUN_MANIFEST.json')
        row['archive_receipt'] = record['archive_receipt']
    return record, evaluations


def _new_attempt(job, context, cycle):
    run_id = job['record']['run_id']
    parent = Path(context['stage'])/'RETAINED_RUNS'/run_id
    index = 1
    while True:
        name = context['io_fix_id']+f'_cycle{cycle:03d}_attempt{index:02d}'
        destination = parent/name
        local = Path(job['scratch_batch'])/'ARCHIVE_STAGING'/name/run_id
        if not destination.exists() and not local.exists():
            return destination, local
        index += 1


def plan_prepared_cleanup(job, receipt, destination, context):
    """Inventory owned derived scratch; these are not historical science pins."""
    from .storage import inventory
    scratch = Path(context['scratch'])
    staging_paths = list(job.get('prepared_attempts', [])) + receipt.get('scratch_archive_roots', [])
    if receipt.get('scratch_archive_root'):
        staging_paths.append(receipt['scratch_archive_root'])
    successful_staging = Path(receipt['scratch_archive_root']) if receipt.get('scratch_archive_root') else None
    plan = []
    for name in dict.fromkeys(staging_paths):
        path = Path(name)
        expected_parent = Path(job['scratch_batch'])/'ARCHIVE_STAGING'
        allowed_names = {job['record']['run_id'], *[job['record']['run_id']+f'.prepare_retry_{i:02d}' for i in (1, 2, 3)]}
        if (path == expected_parent or not path.is_relative_to(expected_parent)
                or not path.is_relative_to(scratch) or path.name not in allowed_names
                or any(p.is_symlink() for p in (path, *path.parents))):
            raise ValueError('Prepared cleanup path is not an owned run attempt')
        if not path.exists():
            continue
        files = inventory(path)
        for relative, pin in files.items():
            receipt_temporary = relative in {f'ARCHIVE_RECEIPT.json.write_attempt_{i:02d}' for i in (1, 2, 3, 4)}
            if relative != 'ARCHIVE_RECEIPT.json' and not receipt_temporary and relative not in receipt['retained_files']:
                raise ValueError('Prepared member is not covered by owned derived member whitelist: '+relative)
            if path == successful_staging and not receipt_temporary:
                if relative == 'ARCHIVE_RECEIPT.json':
                    staged = _read(path/relative)
                    if (staged.get('run_id') != receipt['run_id'] or staged.get('original_files') != receipt['original_files']
                            or {k: v['sha256'] for k, v in staged.get('retained_files', {}).items()}
                            != {k: v['sha256'] for k, v in receipt['retained_files'].items()}):
                        raise ValueError('Successful prepared receipt differs from archive')
                elif pin['sha256'] != receipt['retained_files'][relative]['sha256']:
                    raise ValueError('Successful prepared member differs from archive')
            # A failed gzip close can append a partial-input trailer. The bytes
            # below are registered as temporary derived evidence, never asserted
            # to equal the complete retained output or historical science seal.
            plan.append({'path': str(path/relative), **pin,
                'archive_receipt': str(Path(destination)/'ARCHIVE_RECEIPT.json'),
                'cleanup_role': 'receipt_authorized_owned_derived_staging',
                'inventory_basis': 'current_owned_temporary_bytes_not_historical_science_seal',
                'prepared_attempt_complete': path == successful_staging})
    return plan


def cleanup_prepared(job, receipt, destination, context, output, monitor, *, plan=None):
    plan = plan if plan is not None else plan_prepared_cleanup(job, receipt, destination, context)
    for evidence in plan:
        monitor.assert_healthy()
        member = Path(evidence['path'])
        if (any(p.is_symlink() for p in (member, *member.parents)) or not member.is_file()
                or member.stat().st_size != evidence['size_bytes'] or sha256_file(member) != evidence['sha256']):
            raise ValueError('Prepared member changed before exact cleanup')
        append_json(Path(output)/'CLEANUP_LEDGER.jsonl', {'status': 'DELETE_INTENT', **evidence})
        member.unlink()
        append_json(Path(output)/'CLEANUP_LEDGER.jsonl', {'status': 'DELETED', **evidence})


def _finish_archive(job, receipt, destination, context, output, monitor):
    from .storage import cleanup_exact
    record, evaluations = _relocate(job['record'], job['evaluations'], destination, job['scratch_batch'])
    receipt_path = Path(destination)/'ARCHIVE_RECEIPT.json'
    if receipt.get('status') != 'ARCHIVE_VERIFIED' or receipt.get('run_id') != record['run_id'] or not receipt_path.is_file():
        raise ValueError('Completed receipt required before scratch cleanup')
    resolved = Path(context['root'])/'RESOLVED_RUNS'/record['run_id']
    retry_io(lambda: resolved.mkdir(parents=True, exist_ok=False), source=resolved, destination=resolved,
             operation='controller_resolved_directory_create')
    write_json(resolved/'RUN_RECORD.json', record)
    write_json(resolved/'EVALUATION_RECORDS.json', evaluations)
    write_json(resolved/'RECEIPT_REFERENCE.json', {'path': str(receipt_path), 'sha256': job['_receipt_sha256'],
        'hash_source': job['_receipt_hash_source']})
    # Every original input remains governed by its receipt's exact inventory.
    for role, path in [('solver', Path(job['record']['output_root'])), *[(v, Path(job['scratch_batch'])/'12_OFFLINE_EVALUATION'/v/record['run_id']) for v in ('v3', 'v2')]]:
        monitor.assert_healthy()
        cleanup_exact(path, receipt['original_files'][role], Path(output)/'CLEANUP_LEDGER.jsonl',
                      scratch_root=Path(context['scratch']), archive_verified=receipt)
    cleanup_prepared(job, receipt, destination, context, output, monitor,
                     plan=job.get('_prepared_cleanup_plan'))
    append_json(Path(context['root'])/'ARCHIVE_PENDING_LEDGER.jsonl', {'status': 'ARCHIVE_RESOLVED',
        'run_id': record['run_id'], 'batch': job['batch'], 'archive_receipt': str(receipt_path), 'utc': now()})
    return record, evaluations


def archive_batch(records, evaluations, *, context, scratch_batch, output, batch_number, monitor,
                  existing_receipts=None, audited_original_files=None):
    """Independent G writer pool; only retryable I/O exhaustion becomes pending."""
    from .storage import retain_run
    from .archive_io import ArchiveRetryPending
    started = time.monotonic()
    workers = context.get('write_workers', 6)
    if not 1 <= workers <= 6:
        raise ValueError('G writer pool must be between one and six')
    root, output = Path(context['root']), Path(output)
    existing_receipts = existing_receipts or {}
    by_run = {record['run_id']: [] for record in records}
    if len(by_run) != len(records):
        raise ValueError('Archive registry contains duplicate run identities')
    for row in evaluations:
        by_run[row['run_id']].append(row)
    if any(len(rows) != 2 or {r['evaluator_version'] for r in rows} != {'v3', 'v2'} for rows in by_run.values()):
        raise ValueError('Two existing evaluation terminal rows required per run')
    jobs = [{'record': record, 'evaluations': by_run[record['run_id']], 'scratch_batch': str(scratch_batch),
             'batch': batch_number} for record in records]
    for job in jobs:
        if audited_original_files is not None:
            job['audited_original_files'] = audited_original_files[job['record']['run_id']]
    receipts, destinations, receipt_jobs = {}, {}, {}
    resolved_records, resolved_evaluations = {}, {}
    for job in jobs:
        key = job['record']['run_id']
        if key in existing_receipts:
            entry = existing_receipts[key]
            receipt, destination = entry['receipt'], Path(entry['destination'])
            job['_receipt_sha256'] = entry['prior_receipt_sha256']
            job['_receipt_hash_source'] = 'pinned_independent_input_gate_prior_receipt_sha256'
            for relative, pin in job['record']['output_seal'].items():
                if receipt['original_files']['solver'].get(relative, {}).get('sha256') != pin['sha256']:
                    raise ValueError('Existing receipt/native seal disagree: '+key)
            receipts[key], destinations[key], receipt_jobs[key] = receipt, destination, job
    pending = load_pending(root)
    timings = []

    def attempt(job, round_id):
        destination, local = _new_attempt(job, context, batch_number*10+round_id)
        roots = {v: Path(job['scratch_batch'])/'12_OFFLINE_EVALUATION'/v/job['record']['run_id'] for v in ('v3', 'v2')}
        receipt = retain_run(job['record'], roots, destination,
            archive_code_commit=context['freeze']['io_fix_code_commit'], scratch_archive_root=local,
            retry_delays=(2, 4, 8) if round_id == 0 else ())
        return receipt, destination

    def wave_pass(todo, round_id):
        for offset in range(0, len(todo), workers):
            monitor.assert_healthy()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(attempt, job, round_id): job for job in todo[offset:offset+workers]}
                for future in as_completed(futures):
                    job = futures[future]
                    key = job['record']['run_id']
                    try:
                        receipt, destination = future.result()
                    except ArchiveRetryPending as error:
                        job.setdefault('prepared_attempts', []).extend(getattr(error, 'staging_roots', [])
                            or ([error.staging_root] if error.staging_root else []))
                        pending[key] = job
                        append_json(root/'ARCHIVE_PENDING_LEDGER.jsonl', {'status': 'ARCHIVE_PENDING', 'run_id': key,
                            'batch': job['batch'], 'round': round_id, 'job': job, 'reason': str(error), 'utc': now()})
                        continue
                    monitor.assert_healthy()
                    job['_receipt_sha256'] = sha256_file(Path(receipt['scratch_archive_root'])/'ARCHIVE_RECEIPT.json')
                    job['_receipt_hash_source'] = 'ext4_receipt_bytes_copied_to_G_without_G_hash_reread'
                    pending.pop(key, None)
                    receipts[key], destinations[key], receipt_jobs[key] = receipt, destination, job
                    timings.append(receipt.get('io_timings', receipt.get('timings', {})))
                    append_json(root/'ARCHIVE_IO_LEDGER.jsonl', {'status': 'ARCHIVED', 'run_id': key,
                        'batch': job['batch'], 'cycle_batch': batch_number, 'round': round_id,
                        'destination': str(destination), 'io_timings': timings[-1], 'utc': now()})
                    print('ARCHIVED_IO', key, 'cycle', batch_number, 'round', round_id, flush=True)

    wave_pass([job for job in jobs if job['record']['run_id'] not in existing_receipts], 0)
    # Exactly one batch-end pass, including unresolved earlier-batch archives.
    wave_pass(list(pending.values()), 1)
    current_pending = sum(job['record']['run_id'] in pending for job in jobs)
    gate = pending_gate(current_pending, len(records))
    overall = {'pending_unique_count': len(pending), 'unique_denominator': min(5973, batch_number*256),
               'pending_fraction': len(pending)/min(5973, batch_number*256), 'role': 'record_only_no_stop_gate'}
    result = {'status': 'PASS' if not pending else 'PASS_WITH_ARCHIVE_PENDING', 'batch': batch_number,
        'write_workers': workers, 'archive_wall_seconds': time.monotonic()-started,
        'current_batch_gate': gate, 'cumulative_pending': overall, 'pending_run_ids': sorted(pending),
        'io_timings': timings, 'reused_receipt_count': len(existing_receipts),
        'io_fix_code_commit': context['freeze']['io_fix_code_commit'], 'scientific_code_commit': SCIENTIFIC_COMMIT}
    components = {kind: {'wall_seconds': sum(t.get(kind+'_wall_seconds', 0.) for t in timings),
                        'cpu_seconds': sum(t.get(kind+'_cpu_seconds', 0.) for t in timings)}
                  for kind in ('hash', 'compress', 'copy')}
    result['io_component_totals'] = components
    result['primary_io_cost'] = max(components, key=lambda name: components[name]['wall_seconds']) if timings else 'REUSED_RECEIPTS_ONLY'
    result['io_component_wall_scope'] = 'sum of worker operation wall durations; overlaps across workers'
    write_json(output/'ARCHIVE_IO_RESULT.json', result)
    if gate['status'] != 'PASS':
        raise RuntimeError('Archive pending unique fraction exceeds one percent; retained pending scratch')
    # Preserve the entire batch scene on any archive validation or pending gate
    # failure. No unlink occurs until both archive passes have reached this gate.
    for key, receipt in receipts.items():
        if (receipt.get('status') != 'ARCHIVE_VERIFIED' or receipt.get('run_id') != key
                or not (destinations[key]/'ARCHIVE_RECEIPT.json').is_file()):
            raise ValueError('Archive receipt gate failed before batch cleanup')
        for relative, pin in receipt_jobs[key]['record']['output_seal'].items():
            if receipt['original_files']['solver'].get(relative, {}).get('sha256') != pin['sha256']:
                raise ValueError('Archive original native bytes differ from pre-evaluation seal')
        audited = receipt_jobs[key].get('audited_original_files')
        if audited is not None:
            actual = {role: {name: {k: pin[k] for k in ('sha256', 'size_bytes')} for name, pin in files.items()}
                      for role, files in receipt['original_files'].items()}
            if actual != audited:
                raise ValueError('Recovered archive source bytes differ from approved historical-seal audit')
        receipt_jobs[key]['_prepared_cleanup_plan'] = plan_prepared_cleanup(
            receipt_jobs[key], receipt, destinations[key], context)
    monitor.assert_healthy()
    write_json(output/'PREPARED_CLEANUP_PLAN.json', {key: job['_prepared_cleanup_plan'] for key, job in receipt_jobs.items()})
    write_json(output/'BATCH_ARCHIVE_GATE.json', {'status': 'PASS', 'batch': batch_number,
        'current_batch_pending_gate': gate, 'receipt_run_ids': sorted(receipts), 'pending_run_ids': sorted(pending),
        'receipt_count': len(receipts), 'all_archive_passes_complete_before_cleanup': True})
    for key, receipt in receipts.items():
        row, ev = _finish_archive(receipt_jobs[key], receipt, destinations[key], context, output, monitor)
        resolved_records[key], resolved_evaluations[key] = row, ev
    write_json(output/'CLEANUP_COMPLETE.json', {'status': 'PASS' if not pending else 'PASS_WITH_PENDING_SCRATCH_RETAINED',
        'cleaned_run_ids': sorted(receipts), 'pending_run_ids': sorted(pending)})
    final_records, final_evaluations = [], []
    for job in jobs:
        key = job['record']['run_id']
        final_records.append(resolved_records.get(key, {**job['record'], 'archive_status': 'ARCHIVE_PENDING'}))
        final_evaluations.extend(resolved_evaluations.get(key, job['evaluations']))
    current_receipts = [receipts[j['record']['run_id']] for j in jobs if j['record']['run_id'] in receipts]
    write_json(output/'ARCHIVE_RECEIPTS.json', current_receipts)
    write_json(output/'RUN_RECORDS.json', final_records)
    write_json(output/'EVALUATION_RECORDS.json', final_evaluations)
    return final_records, final_evaluations, current_receipts, result


def verify_recovery_gate(gate_path, expected_sha256, solver_path, evaluation_path):
    if sha256_file(gate_path) != expected_sha256:
        raise ValueError('Read-only recovery audit gate identity changed')
    gate = _read(gate_path)
    required = {'status': 'PASS', 'solver_count': 256, 'evaluation_count': 512,
        'existing_receipt_count': 255, 'missing_run_id': 'RUN_01963',
        'solver_seal_status': 'PASS', 'evaluation_seal_status': 'PASS', 'hash_mismatch_count': 0,
        'current_inventory_is_historical_seal': False, 'missing_prior_evaluation_seals': []}
    if any(gate.get(key) != value for key, value in required.items()):
        raise ValueError('Recovery solver/evaluator seal coverage is not PASS; no archive or cleanup')
    if gate.get('solver_records_sha256') != sha256_file(solver_path) or gate.get('evaluation_records_sha256') != sha256_file(evaluation_path):
        raise ValueError('Recovery records differ from read-only audited inputs')
    rows = gate.get('runs', [])
    if (len(rows) != 256 or len({r['run_id'] for r in rows}) != 256
            or any(r.get('status') != 'PASS' or r.get('evaluation_full_file_seal_missing') for r in rows)):
        raise ValueError('Individual recovery seal coverage is not complete')
    return gate


def recover_archive8(context, reg, gate_path, gate_hash):
    stage, scratch = Path(context['stage']), Path(context['scratch'])
    before = stage/'BATCHES/BATCH_008'
    solver, evaluation = before/'SOLVER_RECORDS_BEFORE_ARCHIVE.json', before/'EVALUATION_RECORDS_BEFORE_ARCHIVE.json'
    gate = verify_recovery_gate(gate_path, gate_hash, solver, evaluation)
    audited = {row['run_id']: row for row in gate['runs']}
    records, evaluations = _read(solver), _read(evaluation)
    if len(records) != 256 or len(evaluations) != 512 or len({r['run_id'] for r in records}) != 256:
        raise ValueError('Batch 8 terminal registry identity mismatch')
    if any(r['terminal_status'] != 'COMPLETED' for r in records) or any(r['evaluation_status'] != 'COMPLETED' for r in evaluations):
        raise ValueError('Batch 8 recovery requires its existing completed science terminals')
    existing = {}
    for record in records:
        path = stage/'RETAINED_RUNS'/record['run_id']/'ARCHIVE_RECEIPT.json'
        if path.is_file():
            digest = audited[record['run_id']].get('prior_receipt_sha256')
            if not digest:
                raise ValueError('Prior receipt has no independent audit identity')
            existing[record['run_id']] = {'receipt': _read(path, digest), 'destination': str(path.parent),
                'prior_receipt_sha256': digest}
    if len(existing) != 255 or set(r['run_id'] for r in records)-set(existing) != {'RUN_01963'}:
        raise ValueError('Expected 255 existing receipts and exact RUN_01963 missing receipt')
    output = Path(context['root'])/'BATCH_008_RECOVERY'
    output.mkdir(parents=True, exist_ok=False)
    with ResourceMonitor(scratch, reg.clean_root, output/'RESOURCE_SAMPLES.jsonl') as monitor:
        monitor.begin_phase('archive_cleanup')
        _, _, receipts, archive = archive_batch(records, evaluations, context=context,
            scratch_batch=scratch/'BATCH_008', output=output, batch_number=8, monitor=monitor, existing_receipts=existing,
            audited_original_files={key: row['current_scratch_inventory'] for key, row in audited.items()})
        phase = monitor.end_phase()
    measurement = monitor.result()
    result = {'status': archive['status'], 'batch': 8, 'run_count': 256, 'evaluation_count': 512,
        'science_execution_status': 'REUSED_EXISTING_COMPLETED_RESULTS', 'solver_calls': 0, 'evaluator_calls': 0,
        'provider_calls': 0, 'archive_receipt_count': len(receipts), 'archive': archive, 'measurements': measurement,
        'archive_phase': phase, 'io_bottleneck': phase['cpu_utilization_fraction'] is not None and phase['cpu_utilization_fraction'] < .40,
        'io_bottleneck_definition': 'archive phase visible-affinity CPU utilization below 40%; no scientific interpretation',
        'scientific_code_commit': SCIENTIFIC_COMMIT, 'io_fix_code_commit': context['freeze']['io_fix_code_commit']}
    write_json(output/'BATCH_RESULT.json', result)
    append_json(Path(context['root'])/'IO_BATCH_LEDGER.jsonl', {'event': 'BATCH_RECOVERED', 'utc': now(), **result})
    return result


def batch_result_path(stage, root, batch):
    recovered = Path(root)/'BATCH_008_RECOVERY/BATCH_RESULT.json'
    return recovered if batch == 8 and recovered.is_file() else Path(stage)/f'BATCHES/BATCH_{batch:03d}/BATCH_RESULT.json'


def next_batch(stage, root, total_batches=24):
    """Require an explicit contiguous prefix; never infer progress by file count."""
    missing = []
    for number in range(1, total_batches+1):
        path = batch_result_path(stage, root, number)
        if not path.exists():
            missing.append(number)
            continue
        row = _read(path)
        if row.get('batch') != number or row.get('status') not in ('PASS', 'PASS_WITH_ARCHIVE_PENDING'):
            raise ValueError('Batch identity/status is not an eligible terminal: '+str(number))
        if missing:
            raise ValueError('Noncontiguous explicit batch sequence; earlier batch missing')
    return missing[0] if missing else total_batches+1


def collect_final_records(stage, root):
    if load_pending(root):
        raise ValueError('Final execution/aggregate requires zero archive pending')
    if next_batch(stage, root) != 25:
        raise ValueError('Final execution requires all explicit batches 1 through 24')
    records, evaluations = {}, {}
    for number in range(1, 25):
        directory = batch_result_path(stage, root, number).parent
        for row in _read(directory/'RUN_RECORDS.json'):
            if row['run_id'] in records:
                raise ValueError('Duplicate completed run identity across batches')
            records[row['run_id']] = row
        for row in _read(directory/'EVALUATION_RECORDS.json'):
            key = (row['run_id'], row['evaluator_version'])
            if key in evaluations:
                raise ValueError('Duplicate evaluation identity across batches')
            evaluations[key] = row
    resolved_root = Path(root)/'RESOLVED_RUNS'
    if resolved_root.is_dir():
        for directory in resolved_root.iterdir():
            row = _read(directory/'RUN_RECORD.json')
            if row['run_id'] not in records:
                raise ValueError('Archive resolution references an unregistered run')
            records[row['run_id']] = row
            for item in _read(directory/'EVALUATION_RECORDS.json'):
                evaluations[(item['run_id'], item['evaluator_version'])] = item
    if len(records) != 5973 or len(evaluations) != 11946:
        raise ValueError('Full unique/evaluator terminal counts do not close')
    for row in records.values():
        receipt = _read(row['archive_receipt'])
        if receipt.get('status') != 'ARCHIVE_VERIFIED' or receipt.get('run_id') != row['run_id']:
            raise ValueError('Final archive receipt unavailable or wrong identity')
    return list(records.values()), list(evaluations.values())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--operation', choices=('freeze-io', 'recover-archive8', 'continue-io'), required=True)
    parser.add_argument('--io-fix-id', required=True)
    parser.add_argument('--input-gate')
    parser.add_argument('--input-gate-sha256')
    parser.add_argument('--write-workers', type=int, default=6)
    parser.add_argument('--stop-after-batch', type=int, default=8)
    args = parser.parse_args(argv)
    args.contract, args.local_config = str(Path(args.contract).resolve()), str(Path(args.local_config).resolve())
    reg = registry(args.local_config)
    current = yaml.safe_load(Path(args.contract).read_text())
    stage = resolve(current['stage_root'], reg)
    root = io_root(stage, args.io_fix_id)
    if args.operation == 'freeze-io':
        print(json.dumps(register_io_freeze(args.contract, reg, args.io_fix_id)), flush=True)
        return 0
    # Audit coverage is checked before any freeze-registration side effect or
    # runtime import. A failed historical seal cannot be repaired by hashing now.
    if args.operation == 'recover-archive8':
        if not args.input_gate or not args.input_gate_sha256:
            raise ValueError('Explicit independent recovery gate path and SHA required')
        before = stage/'BATCHES/BATCH_008'
        verify_recovery_gate(args.input_gate, args.input_gate_sha256,
            before/'SOLVER_RECORDS_BEFORE_ARCHIVE.json', before/'EVALUATION_RECORDS_BEFORE_ARCHIVE.json')
    freeze = _read(root/'IO_FIX_FREEZE.json')
    validate_io_freeze(freeze, reg)
    scratch = Path(yaml.safe_load(Path(args.local_config).read_text())['paths']['canonical541_v2_scratch'])
    original = _read(freeze['continuation_freeze_path'])
    if scratch != Path(original['scratch_root']):
        raise ValueError('I/O recovery cannot relocate frozen scratch')
    from .contract import STAGE_NAME
    if stage.name != STAGE_NAME or not stage.is_relative_to(reg.clean_root):
        raise ValueError('Unexpected protected stage root')
    if any(p.is_symlink() for p in (scratch, *scratch.parents)):
        raise ValueError('Scratch symlink prohibited')
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(scratch)], text=True).strip()
    if filesystem != 'ext4':
        raise ValueError('I/O recovery requires original WSL ext4 scratch')
    context = {'root': str(root), 'stage': str(stage), 'scratch': str(scratch), 'freeze': freeze,
               'io_fix_id': args.io_fix_id, 'write_workers': args.write_workers}
    if not 1 <= args.write_workers <= 6 or not 8 <= args.stop_after_batch <= 24:
        raise ValueError('I/O workers/batch bound exceeds authorization')
    try:
        if args.operation == 'recover-archive8':
            if not args.input_gate or not args.input_gate_sha256:
                raise ValueError('Explicit independent recovery gate path and SHA required')
            recover_archive8(context, reg, args.input_gate, args.input_gate_sha256)
            return 0
        from .contract import load_contract, selection
        from .runner import create_jobs, do_batch
        from .resources import solver_workers
        args.contract = freeze['scientific_contract_path']
        args.io_context = context
        contract = load_contract(args.contract)
        if _read(stage/'PILOT_GATE.json').get('status') != 'PASS':
            raise ValueError('Pilot not PASS; no continuation')
        cases, runs = selection(contract, reg)
        jobs = create_jobs(contract, reg, runs, cases)
        c00 = {r['method_id']: r for r in runs if r['case_id'] == 'C00_clean_normal'}
        start = next_batch(stage, root)
        if start < 9:
            raise ValueError('Batch 8 archive recovery must close before later science batches')
        for number in range(start, args.stop_after_batch+1):
            validate_io_freeze(freeze, reg)
            do_batch(number, jobs[(number-1)*256:number*256], contract, reg, stage, scratch,
                     SCIENTIFIC_COMMIT, args, solver_workers(machine_state()['nproc']), c00)
        if args.stop_after_batch == 24:
            records, evaluations = collect_final_records(stage, root)
            from ..clean5_degradation.runtime import checkpoint
            resolution = {'mode': 'independent_hash_all',
                'human_instruction': 'P-09c based on P-08 preregistered independent pre/post hash-only checkpoints'}
            checkpoint(contract, reg, stage, 'POST_EXECUTION', resolution)
            write_json(root/'FULL_RUN_RECORDS.json', records)
            write_json(root/'FULL_EVALUATION_RECORDS.json', evaluations)
            write_json(stage/'EXECUTION_COMPLETE.json', {'status': 'EXECUTION_COMPLETE_PENDING_AGGREGATE',
                'run_count': len(records), 'evaluation_count': len(evaluations), 'archive_pending_count': 0,
                'code_commit': SCIENTIFIC_COMMIT, 'io_fix_code_commit': freeze['io_fix_code_commit'], 'completed_utc': now()})
        return 0
    except Exception as error:
        # Append-only I/O scope stop; earlier STOPPED.json artifacts are immutable.
        append_json(root/'IO_STOP_LEDGER.jsonl', {'status': 'STOPPED_IO_RECOVERY', 'operation': args.operation,
            'reason': str(error), 'exception': type(error).__name__, 'utc': now(), 'scene_retained': True})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
