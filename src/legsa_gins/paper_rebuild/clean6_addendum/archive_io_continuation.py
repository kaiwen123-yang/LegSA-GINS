"""Artifact-only archive continuation and sealed-subtree storage accounting.

The original execution modules remain byte-identical to the BOM repair commit.
Only the controller's storage-accounting callback is installed in this process.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

import yaml

from ..clean5_degradation.common import registry, resolve, pinned, read_csv, write_json
from ..clean5_degradation.runtime import checkpoint
from ..clean6_canonical_v2.storage import inventory, retain_run, ResourceMonitor, append_json
from ..manifest import sha256_file
from . import runner
from .aggregate import aggregate_all
from .resume import ORIGINAL_COMMIT, FIRST_RECORDS_SHA, ERRATUM, check_files

BOM_COMMIT = '3a61d157ef82af4bfb12f3d1f5c6491742da592c'
BOM_RELATIVE = 'CONTINUATIONS/BOM_RECOVERY_20260913'
NEW_CLI = 'scripts/paper_rebuild/clean6_continue_addendum_archive_io.py'
IO_COMPANION = 'docs/paper_rebuild/clean6/ADDENDUM_ARCHIVE_IO_CONTINUATION.md'
TOTAL_KEYS = ('logical_bytes', 'allocated_bytes', 'file_count')


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns, info.st_ctime_ns)


def scan(root, cached=None):
    """Exactly one non-following stat per discovered entry; reject special files.

    Cached roots are closed, sealed subtrees owned by this controller. Their
    payload never changes under the authorized workflow. Root stamps detect
    entry changes immediately; full file-stat reconciliation occurs per batch.
    """
    root, cached = Path(root), cached or {}
    totals = dict.fromkeys(TOTAL_KEYS, 0)
    details, measured, reused = {}, 0, 0

    def visit(directory):
        nonlocal measured, reused
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                info = entry.stat(follow_symlinks=False)
                measured += 1
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError('Symlink in attempt-owned storage: '+str(path))
                if stat.S_ISDIR(info.st_mode):
                    if path in cached:
                        item = cached[path]
                        if stamp(info) != item['root_stamp']:
                            raise ValueError('Closed cached directory changed: '+str(path))
                        for key in TOTAL_KEYS:
                            totals[key] += item['totals'][key]
                        reused += item['totals']['file_count']
                    else:
                        visit(path)
                elif stat.S_ISREG(info.st_mode):
                    part = path.relative_to(root).as_posix()
                    details[part] = (info.st_size, info.st_blocks*512, *stamp(info))
                    totals['logical_bytes'] += info.st_size
                    totals['allocated_bytes'] += info.st_blocks*512
                    totals['file_count'] += 1
                else:
                    raise ValueError('Special file in attempt-owned storage: '+str(path))

    info = root.stat(follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError('Storage root is not a regular directory')
    visit(root)
    return totals, details, {'fresh_stat_count': measured, 'cached_file_count': reused}


class SealedStorageCounter:
    """Cache only explicitly closed provider/archive/prior-report subtrees."""
    def __init__(self, stage, scratch):
        self.stage, self.scratch = Path(stage), Path(scratch)
        self.cached = {}

    def register(self, root, authorization, expected=None):
        root = Path(root)
        if (not root.is_relative_to(self.stage) or root == self.stage
                or any(root == other or root.is_relative_to(other) or other.is_relative_to(root)
                       for other in self.cached)):
            raise ValueError('Unsafe or overlapping immutable storage cache root')
        totals, details, _ = scan(root)
        if expected is not None:
            if set(details) != set(expected):
                raise ValueError('Sealed storage member set differs: '+str(root))
            for name, pin in expected.items():
                if details[name][0] != pin['size_bytes']:
                    raise ValueError('Sealed storage member size differs: '+str(root/name))
                if 'allocated_bytes' in pin and details[name][1] != pin['allocated_bytes']:
                    raise ValueError('Sealed archive allocation differs: '+str(root/name))
        self.cached[root] = {'root_stamp': stamp(root.stat(follow_symlinks=False)),
            'totals': totals, 'details': details, 'authorization': authorization}

    def discover_sealed(self):
        for directory, archive in ((self.stage/'RETAINED_RUNS', True), (self.stage/'02_PROVIDERS', False)):
            if not directory.exists():
                continue
            with os.scandir(directory) as entries:
                for entry in entries:
                    root = Path(entry.path)
                    if root in self.cached:
                        continue
                    info = entry.stat(follow_symlinks=False)
                    if not stat.S_ISDIR(info.st_mode):
                        raise ValueError('Unexpected member in sealed output collection')
                    seal = (root/'ARCHIVE_RECEIPT.json' if archive else
                            self.stage/'01_PROVIDER_AUDIT'/root.name/'PROVIDER_OUTPUT_SEAL.json')
                    if not seal.is_file() or seal.is_symlink():
                        raise ValueError('Unsealed output at a storage phase boundary: '+str(root))
                    payload = json.loads(seal.read_text())
                    if payload.get('status') != ('ARCHIVE_VERIFIED' if archive else 'SEALED'):
                        raise ValueError('Unverified output cannot enter immutable storage cache')
                    expected = dict(payload['retained_files'] if archive else payload['files'])
                    if archive:
                        if Path(payload['archive_root']) != root or payload['run_id'] != root.name:
                            raise ValueError('Archive receipt cache identity mismatch')
                        expected['ARCHIVE_RECEIPT.json'] = {'size_bytes': seal.stat().st_size}
                    self.register(root, {'seal_path': str(seal), 'seal_sha256': sha256_file(seal),
                        'policy': 'immutable published payload; original hash/stream integrity gates retained'}, expected)

    def reconcile(self):
        """Recheck only immutable snapshots; mutable logs may grow concurrently."""
        for root, item in self.cached.items():
            totals, details, _ = scan(root)
            if (totals != item['totals'] or details != item['details']
                    or stamp(root.stat(follow_symlinks=False)) != item['root_stamp']):
                raise ValueError('Immutable storage reconciliation mismatch: '+str(root))
        return {'status': 'PASS', 'reconciled_immutable_roots': len(self.cached),
            'reconciled_immutable_files': sum(v['totals']['file_count'] for v in self.cached.values()),
            'comparison_scope': 'exact immutable file set, size, allocated bytes and stat identity; mutable files measured fresh'}

    def gate(self, contract, stage, scratch, destination, *, reconcile=False):
        if Path(stage) != self.stage or Path(scratch) != self.scratch:
            raise ValueError('Storage callback escaped its registered attempt')
        started = time.monotonic()
        self.discover_sealed()
        verified = self.reconcile() if reconcile else None
        totals = dict.fromkeys(TOTAL_KEYS, 0)
        stats = {'fresh_stat_count': 0, 'cached_file_count': 0}
        for root in (self.stage, self.scratch):
            measured, _, info = scan(root, self.cached)
            for key in TOTAL_KEYS:
                totals[key] += measured[key]
            for key in stats:
                stats[key] += info[key]
        append_json(destination, {'utc': runner.now(), **totals, **stats,
            'accounting_policy': 'single_stat_mutable_scan_plus_explicit_immutable_sealed_subtree_cache',
            'immutable_root_count': len(self.cached), 'reconciliation': verified,
            'wall_seconds': time.monotonic()-started})
        if max(totals['logical_bytes'], totals['allocated_bytes']) >= contract['storage']['peak_limit_bytes']:
            raise ValueError('Attempt-owned storage cap reached; preserve scene')
        return totals


def validate_scene(contract, reg, stage, scratch, snapshot_path):
    """No writes and no execution: classify the exact supervisor-stopped scene."""
    stage, scratch, snapshot_path = Path(stage), Path(scratch), Path(snapshot_path)
    snapshot = json.loads(snapshot_path.read_text())
    required = {'status': 'INTERRUPTED_FOR_BOUNDED_ARCHIVE_IO_ACCOUNTING_REPAIR',
        'controller_pid_absent': True, 'service_main_pid': 0, 'science_children_at_signal': 0,
        'keyboard_interrupt_logged': True, 'resource_summary_written': True,
        'native_terminal_records': 99, 'evaluation_terminal_records': 198,
        'matching_verified_archive_receipts': 54, 'partial_archive_directories': [],
        'cleanup_started': False, 'batch2_started': False, 'stage_root': str(stage)}
    if any(type(snapshot.get(k)) is not type(v) or snapshot[k] != v for k, v in required.items()):
        raise ValueError('Archive continuation stop snapshot does not match the bounded scene')
    check_files(stage, snapshot['files'])
    previous = stage/BOM_RELATIVE
    prior_freeze = json.loads((previous/'EXECUTION_FREEZE.json').read_text())
    if prior_freeze['code_commit'] != BOM_COMMIT:
        raise ValueError('Unexpected prior bookkeeping implementation')
    for relative, digest in prior_freeze['source_sha256'].items():
        if sha256_file(reg.code_root/relative) != digest:
            raise ValueError('Frozen scientific source changed before I/O continuation: '+relative)
    records = json.loads((previous/'BATCHES/BATCH_001/SOLVER_RECORDS.json').read_text())
    evaluations = json.loads((previous/'BATCHES/BATCH_001/EVALUATION_RECORDS.json').read_text())
    runs = runner.make_runs(contract, read_csv(pinned(contract['sources']['unique_run_registry'], reg)))
    if (len(records) != 99 or [r['run_id'] for r in records] != [r['run_id'] for r in runs[:99]]
            or any(r['terminal_status'] != 'COMPLETED' or r['code_commit'] != ORIGINAL_COMMIT for r in records)
            or sha256_file(stage/'BATCHES/BATCH_001/SOLVER_RECORDS.json') != FIRST_RECORDS_SHA):
        raise ValueError('Recovered native terminal identities differ')
    expected = {(r['run_id'], v) for r in records for v in ('v3', 'v2')}
    if (len(evaluations) != 198 or {(r['run_id'], r['evaluator_version']) for r in evaluations} != expected
            or any(r['evaluation_status'] != 'COMPLETED' or not r['evaluation_invoked'] for r in evaluations)):
        raise ValueError('Exactly 198 completed evaluator identities must be reused')
    markers = {(p.stem, p.parent.name) for p in (stage/'01_EVALUATION_CALLS').glob('*/*.json')}
    if markers != expected-{('ADD_RUN_00001', 'v3')}:
        raise ValueError('First-batch evaluator invocation registration differs from the 197 new BOM calls')
    for row in evaluations:
        original = (row['run_id'], row['evaluator_version']) == ('ADD_RUN_00001', 'v3')
        if (row['code_commit'] != (ORIGINAL_COMMIT if original else BOM_COMMIT)
                or row['derived_metrics_code_commit'] != BOM_COMMIT):
            raise ValueError('Original/BOM evaluator provenance changed')
    for record in records:
        root = scratch/'BATCH_001/03_RUNS'/record['run_id']
        if Path(record['output_root']) != root:
            raise ValueError('Native scratch identity changed')
        seal = json.loads((root/'OUTPUT_SEAL.json').read_text())
        if seal['files'] != record['output_seal']:
            raise ValueError('Native seal differs from prior terminal record')
        check_files(root, seal['files'])
    for row in evaluations:
        root = scratch/'BATCH_001/12_OFFLINE_EVALUATION'/row['evaluator_version']/row['run_id']
        if Path(row['evaluation_output_root']) != root:
            raise ValueError('Evaluator scratch identity changed')
        seal = json.loads((root/'EVALUATION_OUTPUT_SEAL.json').read_text())
        if seal.get('status') != 'SEALED_AFTER_DERIVED_METRICS':
            raise ValueError('Evaluation derived completion seal missing')
        check_files(root, seal['files'])
    for case_id in dict.fromkeys(r['case_id'] for r in records):
        root = stage/'02_PROVIDERS'/case_id
        seal = json.loads((stage/'01_PROVIDER_AUDIT'/case_id/'PROVIDER_OUTPUT_SEAL.json').read_text())
        check_files(root, seal['files'], exact=True)
    receipt_dir = previous/'BATCHES/BATCH_001/ARCHIVE_RECEIPTS'
    receipts = {}
    destinations = {p.name: p for p in (stage/'RETAINED_RUNS').iterdir()}
    report_ids = {p.stem for p in receipt_dir.glob('*.json')}
    if set(destinations) != report_ids or len(report_ids) != 54 or not report_ids.issubset({r['run_id'] for r in records}):
        raise ValueError('Partial or unmatched archive destination; do not overwrite or retry')
    for run_id, root in destinations.items():
        receipt = json.loads((root/'ARCHIVE_RECEIPT.json').read_text())
        if receipt != json.loads((receipt_dir/(run_id+'.json')).read_text()):
            raise ValueError('Published/report archive receipts differ')
        if receipt.get('status') != 'ARCHIVE_VERIFIED' or receipt['run_id'] != run_id or Path(receipt['archive_root']) != root:
            raise ValueError('Published archive identity differs')
        pins = dict(receipt['retained_files'])
        pins['ARCHIVE_RECEIPT.json'] = {'sha256': sha256_file(root/'ARCHIVE_RECEIPT.json'),
                                     'size_bytes': (root/'ARCHIVE_RECEIPT.json').stat().st_size}
        check_files(root, pins, exact=True)
        receipts[run_id] = receipt
    if (previous/'BATCHES/BATCH_001/EXACT_CLEANUP_LEDGER.jsonl').exists():
        raise ValueError('Cleanup already started; separate scene recovery required')
    for number in range(2, 6):
        if (scratch/f'BATCH_{number:03d}').exists() or (stage/f'BATCHES/BATCH_{number:03d}').exists():
            raise ValueError('Future scientific batch already started; no automatic repetition')
    if (stage/'FINAL_STATUS.json').exists():
        raise ValueError('Addendum already has a terminal status')
    return records, evaluations, receipts, runs, snapshot, prior_freeze


def complete_archive_batch(records, evaluations, existing, contract, stage, scratch, target, freeze, monitor, counter):
    """Only archive/cleanup: no provider, native, evaluator, or derivative call."""
    report, owned = target/'BATCHES/BATCH_001', scratch/'BATCH_001'
    report.mkdir(parents=True, exist_ok=False)
    write_json(report/'REUSED_SCIENCE_RECORDS.json', {'native_count': 99, 'evaluation_count': 198,
        'native_calls': 0, 'evaluator_calls': 0, 'derived_metric_recomputations': 0,
        'source': '<ADDENDUM_ROOT>/'+BOM_RELATIVE+'/BATCHES/BATCH_001'})
    receipts = []
    for record in records:
        roots = {v: owned/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
        receipt = existing.get(record['run_id'])
        reused = receipt is not None
        if not reused:
            receipt = retain_run(record, roots, stage/'RETAINED_RUNS'/record['run_id'],
                archive_code_commit=freeze['code_commit'], scratch_archive_root=owned/'ARCHIVE_STAGING'/record['run_id'])
        receipts.append((record, roots, receipt))
        write_json(report/'ARCHIVE_RECEIPTS'/(record['run_id']+'.json'), receipt)
        if not reused:
            print('ARCHIVE', record['run_id'], receipt['status'], flush=True)
            counter.gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl')
    counter.gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl', reconcile=True)
    resolved_records, resolved_evaluations = runner.resolve_archived_records(receipts, evaluations)
    write_json(report/'RESOLVED_RUN_RECORDS.json', resolved_records)
    write_json(report/'RESOLVED_EVALUATION_RECORDS.json', resolved_evaluations)
    runner.cleanup_batch(receipts, report, scratch, monitor)
    if inventory(owned):
        raise ValueError('Unexpected first-batch scratch files after exact cleanup')
    counter.gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl', reconcile=True)
    write_json(report/'BATCH_COMPLETE.json', {'status': 'COMPLETED', 'native_terminals': 99,
        'evaluation_terminals': 198, 'archive_pending': 0, 'remaining_scratch_files': 0,
        'native_calls_this_continuation_batch': 0, 'evaluator_calls_this_continuation_batch': 0,
        'derived_metric_recomputations': 0, 'existing_verified_archives_reused': len(existing),
        'new_archives': 99-len(existing), 'utc': runner.now()})
    return resolved_records, resolved_evaluations


def protected_cleanup(counter, contract, stage, scratch, original_cleanup):
    """Reconcile before the unchanged deletion gate for every controller batch."""
    def wrapped(receipts, report, scratch_root, monitor):
        if Path(scratch_root) != Path(scratch):
            raise ValueError('Cleanup callback escaped its registered scratch root')
        counter.gate(contract, stage, scratch, Path(report)/'OWNED_STORAGE_LEDGER.jsonl', reconcile=True)
        return original_cleanup(receipts, report, scratch_root, monitor)
    return wrapped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--interrupt-snapshot', required=True)
    parser.add_argument('--continuation-id', default='ARCHIVE_IO_20260913')
    parser.add_argument('--validate-scene-only', action='store_true')
    args = parser.parse_args(argv)
    args.local_config, args.contract = str(Path(args.local_config).resolve()), str(Path(args.contract).resolve())
    contract, reg = runner.load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    scratch = Path(yaml.safe_load(Path(args.local_config).read_text())['paths'][contract['scratch_alias']])
    records, evaluations, existing, runs, snapshot, prior = validate_scene(
        contract, reg, stage, scratch, args.interrupt_snapshot)
    if args.validate_scene_only:
        print(json.dumps({'status': 'PASS_ARCHIVE_IO_SCENE_VALIDATION', 'native_reused': len(records),
            'evaluations_reused': len(evaluations), 'archives_reused': len(existing),
            'unstarted_archive_count': 99-len(existing), 'native_calls': 0, 'evaluator_calls': 0}))
        return 0
    if not re.fullmatch(r'ARCHIVE_IO_[A-Za-z0-9_]+', args.continuation_id):
        raise ValueError('Safe archive I/O continuation identity required')
    target = stage/'CONTINUATIONS'/args.continuation_id
    if target.exists() or target.is_symlink():
        raise FileExistsError('Archive I/O continuation exists; no overwrite or automatic retry')
    freeze = runner.execution_freeze(args, contract, reg)
    if freeze['contract_hash'] != prior['contract_hash']:
        raise ValueError('Immutable preregistration changed')
    for relative, digest in prior['source_sha256'].items():
        if sha256_file(reg.code_root/relative) != digest:
            raise ValueError('I/O continuation changed a prior scientific source: '+relative)
    for relative in (NEW_CLI, ERRATUM, IO_COMPANION):
        path = reg.code_root/relative
        if subprocess.check_output(['git', 'show', freeze['code_commit']+':'+relative], cwd=reg.code_root) != path.read_bytes():
            raise ValueError('New I/O entry and companion must be committed before execution')
        freeze['source_sha256'][relative] = sha256_file(path)
    for pin in (contract['runtime']['executable'], contract['runtime']['model'], contract['evaluation']['evaluator']):
        pinned(pin, reg)
    freeze.update(original_execution_code_commit=ORIGINAL_COMMIT, prior_bom_code_commit=BOM_COMMIT,
        prior_bom_execution_freeze=prior, original_native_reused_count=99,
        original_completed_evaluation_reused_count=1, historical_full_file_derived_seal_available=False,
        io_native_reused_count=99, io_evaluation_reused_count=198, io_verified_archive_reused_count=len(existing),
        native_retry_count=0, evaluator_retry_count=0, numerical_sources_unchanged_from_bom_commit=True,
        interrupt_snapshot_source=str(Path(args.interrupt_snapshot).resolve()),
        interrupt_snapshot_sha256=sha256_file(args.interrupt_snapshot),
        repair_scope='archive continuation and immutable storage accounting only',
        stage_root=str(stage), scratch_root=str(scratch), continuation_root=str(target), **contract['data_roles'])
    target.mkdir(parents=True, exist_ok=False)
    write_json(target/'EXECUTION_FREEZE.json', freeze)
    write_json(target/'INTERRUPT_SCENE_SNAPSHOT.json', snapshot)
    with (target/Path(IO_COMPANION).name).open('xb') as stream:
        stream.write((reg.code_root/IO_COMPANION).read_bytes())
    for name in ('CURRENT_POST_STOP_EVALUATION_SNAPSHOT.json', 'ADDENDUM_METRIC_WORDING_ERRATUM.md'):
        with (target/name).open('xb') as stream:
            stream.write((stage/BOM_RELATIVE/name).read_bytes())
    args.freeze_path = str(target/'EXECUTION_FREEZE.json')
    counter = SealedStorageCounter(stage, scratch)
    # These histories are closed; all new bookkeeping uses the new target.
    counter.register(stage/BOM_RELATIVE, {'policy': 'closed prior continuation; stop snapshot hash verified'})
    counter.register(stage/'BATCHES/BATCH_001', {'policy': 'closed original native batch; original record seal verified'})
    counter.gate(contract, stage, scratch, target/'OWNED_STORAGE_LEDGER.jsonl', reconcile=True)
    original_gate, original_cleanup = runner.storage_gate, runner.cleanup_batch
    runner.storage_gate = counter.gate
    runner.cleanup_batch = protected_cleanup(counter, contract, stage, scratch, original_cleanup)
    monitor = ResourceMonitor(scratch, stage, target/'RESOURCE_SAMPLES.jsonl')
    monitor.__enter__()
    started, all_records, all_evaluations, final = time.monotonic(), [], [], None
    try:
        monitor.begin_phase('BATCH_001_ARCHIVE_IO_CONTINUATION')
        all_records, all_evaluations = complete_archive_batch(records, evaluations, existing,
            contract, stage, scratch, target, freeze, monitor, counter)
        write_json(target/'BATCHES/BATCH_001/RESOURCE_SUMMARY.json', monitor.end_phase())
        append_json(target/'BATCH_LEDGER.jsonl', {'batch': 1, 'native_terminals': 99,
            'evaluation_terminals': 198, 'archive_pending': 0, 'utc': runner.now()})
        for number in range(2, 6):
            runner.validate_freeze(freeze, args, reg)
            counter.gate(contract, stage, scratch, target/'OWNED_STORAGE_LEDGER.jsonl', reconcile=True)
            monitor.begin_phase(f'BATCH_{number:03d}')
            new_records, new_evaluations = runner.run_batch(runs[(number-1)*99:number*99],
                contract, reg, stage, scratch, freeze, args, number, monitor)
            all_records.extend(new_records)
            all_evaluations.extend(new_evaluations)
            write_json(stage/f'BATCHES/BATCH_{number:03d}/RESOURCE_SUMMARY.json', monitor.end_phase())
            counter.gate(contract, stage, scratch, target/'OWNED_STORAGE_LEDGER.jsonl', reconcile=True)
            append_json(target/'BATCH_LEDGER.jsonl', {'batch': number, 'native_terminals': len(all_records),
                'evaluation_terminals': len(all_evaluations), 'archive_pending': 0, 'utc': runner.now()})
        checkpoint(contract, reg, stage, 'POST', {'mode': 'independent_hash_all',
            'human_instruction': 'P-09d registered post checkpoint after artifact-only archive I/O continuation'})
        statuses = aggregate_all(all_evaluations, all_records, contract, stage, freeze['code_commit'])
        check_files(stage, snapshot['files'])
        for relative, digest in prior['preserved_prior_records_sha256'].items():
            if sha256_file(stage/relative) != digest:
                raise ValueError('Preserved original record changed: '+relative)
        final = {'terminal_status': 'PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE',
            'native_terminal_count': len(all_records), 'evaluation_terminal_count': len(all_evaluations),
            'native_status_counts': dict(Counter(r['terminal_status'] for r in all_records)),
            'evaluation_status_counts': dict(Counter(r['evaluation_status'] for r in all_evaluations)),
            'native_retry_count': 0, 'evaluator_retry_count': 0, 'core_solver_calls': 0, 'core_evaluator_calls': 0,
            'archive_pending': 0, 'aggregate_statuses': statuses, 'code_commit': freeze['code_commit'],
            'original_code_commit': ORIGINAL_COMMIT, 'prior_bom_code_commit': BOM_COMMIT,
            'original_native_reused_count': 99, 'original_completed_evaluation_reused_count': 1,
            'io_native_reused_count': 99, 'io_evaluation_reused_count': 198,
            'io_verified_archive_reused_count': len(existing), 'new_native_calls_this_continuation': 396,
            'new_evaluator_identities_this_continuation': 792, 'contract_hash': freeze['contract_hash'],
            'active_execution_freeze': str(target/'EXECUTION_FREEZE.json'),
            'original_execution_freeze': str(stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json'),
            'prior_stop_preserved': True, 'prior_io_interrupt_preserved': True,
            'continuation_wall_seconds': time.monotonic()-started, 'utc': runner.now(), **contract['data_roles']}
    except Exception as error:
        write_json(target/'STOPPED.json', {'status': 'STOPPED_GATE_FAILURE', 'reason': str(error),
            'native_terminal_count_completed_batches': len(all_records),
            'evaluation_terminal_count_completed_batches': len(all_evaluations), 'scene_retained': True,
            'native_retry_count': 0, 'evaluator_retry_count': 0, 'utc': runner.now()})
        raise
    finally:
        monitor.__exit__(*sys.exc_info())
        write_json(target/'RESOURCE_SUMMARY.json', monitor.result())
        runner.storage_gate = original_gate
        runner.cleanup_batch = original_cleanup
    seal = {}
    for dirname in ('00_PREREGISTRATION', '01_CHECKPOINTS', '01_PROVIDER_AUDIT', '01_EVALUATION_CALLS',
                    '13_AGGREGATE_ADDENDUM', 'BATCHES', 'CONTINUATIONS'):
        for member in sorted((stage/dirname).rglob('*')):
            if member.is_file():
                seal[member.relative_to(stage).as_posix()] = {'sha256': sha256_file(member), 'size_bytes': member.stat().st_size}
    write_json(stage/'FINAL_RECORD_SEAL.json', {'status': 'SEALED', 'files': seal,
        'code_commit': freeze['code_commit'], 'original_execution_code_commit': ORIGINAL_COMMIT,
        'prior_bom_code_commit': BOM_COMMIT, 'retained_payload_seals': 'RETAINED_RUNS/*/ARCHIVE_RECEIPT.json',
        'provider_payload_seals': '01_PROVIDER_AUDIT/*/PROVIDER_OUTPUT_SEAL.json'})
    write_json(stage/'FINAL_STATUS.json', final)
    return 0
