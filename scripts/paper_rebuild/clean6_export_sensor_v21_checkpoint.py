#!/usr/bin/env python3
"""Export closed P-13 checkpoint metadata; never invoke scientific execution.

Only --through-batch 8, 16 and 23 are supported. A bookkeeping inconsistency
refuses this export without changing any scientific status or existing output.
No NAV, STD, error series, provider payload or archive member is opened.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys


SCRIPT = 'scripts/paper_rebuild/clean6_export_sensor_v21_checkpoint.py'
STAGE = 'CLEAN6_SENSOR_MODEL_V21'
MAIN_SCIENTIFIC_COMMIT = '521901f0347e367281abed23b46686b84df86055'
ALGORITHM = 'ALGORITHM_FAILURE_ALL_YAW_REJECTED'
TERMINAL_FIELDS = ('dataset_id', 'case_family', 'degradation_type_id', 'method_id',
                   'effective_profile', 'terminal_status')


class BookkeepingError(ValueError):
    """Export-only refusal; not a new scientific stopping condition."""


def require(condition, message):
    if not condition:
        raise BookkeepingError(message)


def safe_path(value):
    path = Path(value).absolute()
    require('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
            'Metadata/output path must not traverse a symlink or parent component')
    return path


def declared_path(value):
    """Inspect a manifest path lexically, without stat/open of payload files."""
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts, 'Invalid declared absolute member path')
    return path


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value):
    """Compare JSON identities without Python's True == 1 == 1.0 coercion."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def pin_tuple(pin):
    size, sha = pin.get('size_bytes'), pin.get('sha256')
    require(isinstance(size, int) and not isinstance(size, bool) and size >= 0 and
            isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha), 'Invalid metadata file pin')
    return size, sha


class Metadata:
    def __init__(self, roots):
        self.roots = roots
        self.evidence = {}

    def alias(self, value):
        path = safe_path(value)
        for label, root in sorted(self.roots.items(), key=lambda item: -len(str(item[1]))):
            if path.is_relative_to(root):
                suffix = path.relative_to(root).as_posix()
                return label + (('/' + suffix) if suffix != '.' else '')
        raise BookkeepingError('Input path has no authorized root alias')

    def read(self, path, role, batch='', run_id='', *, lines=False, raw=False):
        path = safe_path(path)
        reference = self.alias(path)
        require(path.is_file(), 'Missing metadata: ' + reference)
        payload = path.read_bytes()
        pin = {'path': reference, 'size_bytes': len(payload), 'sha256': digest(payload)}
        if reference in self.evidence:
            prior = self.evidence[reference]
            require(all(prior[k] == pin[k] for k in pin), 'Metadata changed during export: ' + reference)
        else:
            self.evidence[reference] = dict(role=role, batch=batch, run_id=run_id, **pin)
        if raw:
            return payload
        if lines:
            return [json.loads(line) for line in payload.decode('utf-8').splitlines() if line.strip()]
        return json.loads(payload)


def unique_index(rows, keys, label):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        require(key not in result, 'Duplicate identity in ' + label)
        result[key] = row
    return result


def resource_summary(samples):
    """Describe only observed elapsed-time windows; monitor restarts stay split."""
    if not samples:
        return {'resource_status': 'UNAVAILABLE', 'resource_sample_count': 0}
    windows = []
    for row in samples:
        elapsed = row['elapsed_seconds']
        if (not windows or elapsed < windows[-1]['last_elapsed_seconds'] or
                row.get('root_pid') != windows[-1]['root_pid']):
            windows.append({'window': len(windows)+1, 'root_pid': row.get('root_pid'),
                'first_elapsed_seconds': elapsed, 'last_elapsed_seconds': elapsed,
                'sample_count': 0, 'phase_sample_counts': {}})
        window = windows[-1]
        window['last_elapsed_seconds'] = elapsed
        window['sample_count'] += 1
        phase = row.get('phase') or 'between_phases'
        window['phase_sample_counts'][phase] = window['phase_sample_counts'].get(phase, 0)+1
    result = {'resource_status': 'OBSERVED_WINDOWS_ONLY', 'resource_sample_count': len(samples),
        'resource_window_count': len(windows),
        'resource_windows_json': json.dumps(windows, sort_keys=True, separators=(',', ':')),
        'observed_elapsed_span_seconds_sum': sum(w['last_elapsed_seconds']-w['first_elapsed_seconds'] for w in windows),
        'owned_rss_sampled_peak_bytes': max(r['owned_rss_bytes'] for r in samples),
        'host_memory_used_sampled_peak_bytes': max(r['memory_used_bytes'] for r in samples),
        'host_memory_available_sampled_min_bytes': min(r['memory_available_bytes'] for r in samples)}
    for label in ('scratch', 'g'):
        result[label+'_filesystem_used_sampled_peak_bytes'] = max(
            r['filesystem_absolute_bytes'][label]['used_bytes'] for r in samples)
        result[label+'_filesystem_growth_sampled_peak_bytes'] = max(
            r['filesystem_used_growth_bytes'][label] for r in samples)
    return result


def cleanup_summary(meta, controller, number, scratch, originals):
    """Count unique paired deletion events authorized by receipt/cleanup metadata."""
    directories = sorted(controller.glob(f'BATCH_{number:03d}_BOOKKEEPING_RECOVERY_*'))
    ledgers, allowed, closed = [], dict(originals), []
    for directory in directories:
        result_path = directory/'BATCH_RESULT.json'
        if not result_path.is_file():
            continue
        result = meta.read(result_path, 'archive_recovery_result', number)
        require(result['batch'] == number, 'Recovery directory/batch identity mismatch')
        if (directory/'CLEANUP_COMPLETE.json').is_file():
            closed.append(meta.read(directory/'CLEANUP_COMPLETE.json', 'cleanup_completion', number))
        plan_path = directory/'PREPARED_CLEANUP_PLAN.json'
        if plan_path.is_file():
            plan = meta.read(plan_path, 'prepared_cleanup_plan', number)
            for items in plan.values():
                for item in items:
                    path, pin = str(declared_path(item['path'])), pin_tuple(item)
                    if path in allowed:
                        require(allowed[path] == pin, 'Cleanup plan contradicts receipt metadata')
                    allowed[path] = pin
        if (directory/'CLEANUP_LEDGER.jsonl').is_file():
            ledgers.append(directory/'CLEANUP_LEDGER.jsonl')
    if not ledgers or not closed:
        return {'cleanup_status': 'UNAVAILABLE', 'cleanup_reason': 'No paired deletion ledger and completion metadata',
                'cleanup_deleted_files': 'UNAVAILABLE', 'cleanup_deleted_bytes': 'UNAVAILABLE'}
    try:
        require(all(c.get('status') == 'PASS' and c.get('pending_run_ids') == [] for c in closed),
                'Cleanup metadata is not closed')
        intents, deleted = {}, {}
        for path in ledgers:
            for event in meta.read(path, 'exact_cleanup_ledger', number, lines=True):
                if event.get('status') not in ('DELETE_INTENT', 'DELETED'):
                    continue
                member, pin = declared_path(event['path']), pin_tuple(event)
                require(member.is_relative_to(scratch/f'BATCH_{number:03d}'), 'Deletion is outside its owned batch')
                key = str(member)
                require(allowed.get(key) == pin, 'Deletion has no matching receipt/plan metadata pin')
                if event['status'] == 'DELETE_INTENT':
                    require(key not in intents or intents[key] == pin, 'Conflicting deletion intents')
                    intents[key] = pin
                else:
                    require(intents.get(key) == pin, 'Deletion lacks matching preceding intent')
                    require(key not in deleted or deleted[key] == pin, 'Conflicting deletion events')
                    deleted[key] = pin
        require(intents == allowed, 'Deletion intent inventory differs from complete receipt/prepared inventory')
        require(deleted == allowed, 'Deleted inventory differs from complete receipt/prepared inventory')
        return {'cleanup_status': 'PAIRED_LEDGER_AND_RECEIPT_METADATA_VERIFIED',
            'cleanup_deleted_files': len(deleted), 'cleanup_deleted_bytes': sum(pin[0] for pin in deleted.values()),
            'cleanup_authoritative_inventory_files': len(allowed),
            'cleanup_authoritative_inventory_bytes': sum(pin[0] for pin in allowed.values()),
            'cleanup_full_inventory_coverage': 'EXACT_EQUAL_PATH_SIZE_SHA256',
            'cleanup_ledger_count': len(ledgers)}
    except BookkeepingError as error:
        # Optional resource/cleanup accounting must not become a scientific gate.
        return {'cleanup_status': 'UNAVAILABLE', 'cleanup_reason': str(error),
                'cleanup_deleted_files': 'UNAVAILABLE', 'cleanup_deleted_bytes': 'UNAVAILABLE'}


def csv_text(rows, fields=None):
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def prepare(stage_root, code_root, through_batch):
    """Read closed small metadata and return four text outputs, without writing."""
    stage, code = safe_path(stage_root), safe_path(code_root)
    require(through_batch in (8, 16, 23), 'Registered checkpoints are batches 8, 16 and 23')
    require(stage.name == STAGE and stage.parent.name == 'stages', 'Unexpected P-13 stage root')
    clean, controller = stage.parent.parent, stage/'CONTROLLER'
    meta = Metadata({'<CLEAN_ROOT>': clean, '<CODE_ROOT>': code})
    status = meta.read(stage/'STATUS.json', 'controller_status')
    expected = 'MAIN_BATCHES_TERMINAL' if through_batch == 23 else 'CHECKPOINT_READY'
    require(status.get('status') == expected, 'Requested checkpoint is not ready; no output written')
    require(status.get('completed_main_runs', -1) >= min(through_batch*256, 5880), 'Checkpoint count is incomplete')
    freeze = meta.read(stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json', 'main_scientific_execution_freeze')
    require(freeze.get('code_commit') == MAIN_SCIENTIFIC_COMMIT, 'Execution freeze differs from the registered P13 main chain')
    pending = {}
    pending_path = controller/'ARCHIVE_PENDING_LEDGER.jsonl'
    for event in meta.read(pending_path, 'pending_state_ledger', lines=True):
        if event['status'] == 'ARCHIVE_PENDING':
            pending[event['run_id']] = event
        elif event['status'] == 'ARCHIVE_RESOLVED':
            pending.pop(event['run_id'], None)
    require(not pending, 'Archive ledger has pending work; export needs bookkeeping closure')
    source = meta.read(code/SCRIPT, 'exporter_source_sha256_not_commit', raw=True)
    require(source == Path(__file__).read_bytes(), 'Invoked exporter differs from code-root source')
    batch_rows, terminal_counts, all_runs = [], Counter(), set()
    scratch = None
    for number in range(1, through_batch+1):
        folder = stage/'BATCHES'/f'BATCH_{number:03d}'
        complete = meta.read(folder/'BATCH_COMPLETE.json', 'batch_complete', number)
        require(complete.get('status') == 'PASS' and complete.get('batch') == number, 'Batch completion is not PASS')
        records = meta.read(folder/'RUN_RECORDS.json', 'batch_native_records', number)
        evaluations = meta.read(folder/'EVALUATION_RECORDS.json', 'batch_evaluation_records', number)
        native = unique_index(records, ('run_id',), 'batch native records')
        ev = unique_index(evaluations, ('run_id', 'evaluator_version'), 'batch evaluations')
        require(len(records) == (248 if number == 23 else 256), 'Unexpected registered batch run count')
        require(set(ev) == {(r['run_id'], v) for r in records for v in ('v3', 'v2')}, 'Evaluator identity coverage differs')
        require(not (all_runs & set(native)), 'Run identity occurs in two batches')
        all_runs.update(native)
        archive = complete['archive']
        require(archive.get('status') == 'PASS' and archive.get('pending_run_ids') == [] and
                archive.get('current_batch_gate', {}).get('status') == 'PASS' and
                archive['current_batch_gate'].get('pending_unique_count') == 0,
                'Batch archive metadata is not closed')
        require(archive.get('v21_scientific_code_commit') == complete['code_commit'] == freeze['code_commit'],
                'Batch/archive scientific code identities differ from the main execution freeze')
        require(archive.get('inherited_archival_report_scientific_commit_is_pre_correction') is True,
                'Inherited v2 archival identity must be explicitly labeled pre-correction')
        originals, statuses, calls, solver_commits, modes = {}, Counter(), [], set(), Counter()
        for record in records:
            run_id = record['run_id']
            require(record.get('code_commit') == freeze['code_commit'], 'Native record execution commit differs from the main freeze: '+run_id)
            require(record['terminal_status'] in ('COMPLETED', ALGORITHM), 'Unexpected native terminal in bookkeeping input')
            resolved = controller/'RESOLVED_RUNS'/run_id
            resolved_record = meta.read(resolved/'RUN_RECORD.json', 'independent_resolved_native', number, run_id)
            require(canonical_json(resolved_record) == canonical_json(record),
                    'Batch native record differs from independent resolved record: '+run_id)
            original_evaluations = meta.read(resolved/'EVALUATION_RECORDS.json', 'independent_resolved_evaluations', number, run_id)
            own = [ev[(run_id, v)] for v in ('v3', 'v2')]
            original_index = unique_index(original_evaluations, ('run_id', 'evaluator_version'), 'resolved evaluations')
            require(set(original_index) == {(run_id, v) for v in ('v3', 'v2')} and
                    all(canonical_json(original_index[(run_id, v)]) == canonical_json(ev[(run_id, v)]) for v in ('v3', 'v2')),
                    'Batch evaluations differ from independent resolved records: '+run_id)
            reference = meta.read(resolved/'RECEIPT_REFERENCE.json', 'independent_receipt_reference', number, run_id)
            require(reference['path'] == record['archive_receipt'] and record.get('archive_status') == 'ARCHIVE_VERIFIED',
                    'Independent receipt path/archive status differs: '+run_id)
            receipt_path = safe_path(reference['path'])
            require(receipt_path.is_relative_to(stage/'RETAINED_RUNS'/run_id), 'Receipt escapes its retained run')
            receipt = meta.read(receipt_path, 'verified_receipt_full_metadata', number, run_id)
            require(meta.evidence[meta.alias(receipt_path)]['sha256'] == reference['sha256'], 'Complete receipt metadata SHA mismatch: '+run_id)
            require(receipt.get('status') == 'ARCHIVE_VERIFIED' and receipt.get('run_id') == run_id and
                    receipt.get('dataset_id') == record['dataset_id'] and receipt.get('terminal_status') == record['terminal_status'],
                    'Receipt native identity differs: '+run_id)
            for name, pin in record['output_seal'].items():
                require(pin_tuple(receipt['original_files']['solver'][name]) == pin_tuple(pin), 'Native seal/receipt metadata mismatch: '+run_id)
            expected_eval = 'COMPLETED' if record['terminal_status'] == 'COMPLETED' else 'NOT_RUN_ALGORITHM_FAILURE'
            require(all(row.get('archive_receipt') == reference['path'] and row['evaluation_status'] == expected_eval for row in own),
                    'Evaluator terminal/receipt reference differs: '+run_id)
            original_root = declared_path(record['scratch_output_root'])
            candidates = [p.parent for p in original_root.parents if p.name == f'BATCH_{number:03d}']
            require(len(candidates) == 1, 'Scratch path has no unique batch root')
            require(scratch in (None, candidates[0]), 'Run scratch roots differ')
            scratch = candidates[0]
            meta.roots['<SCRATCH_ROOT>'] = scratch
            for role, files in receipt['original_files'].items():
                require(role in ('solver', 'v3', 'v2'), 'Unexpected receipt source role')
                root = original_root if role == 'solver' else scratch/f'BATCH_{number:03d}'/'12_OFFLINE_EVALUATION'/role/run_id
                for relative, pin in files.items():
                    path = declared_path(root/relative)
                    require(path.is_relative_to(root), 'Receipt relative member escapes role root')
                    originals[str(path)] = pin_tuple(pin)
            terminal_counts[tuple(record[key] for key in TERMINAL_FIELDS)] += 1
            statuses[record['terminal_status']] += 1
            modes[record['data_mode']] += 1
            solver_commits.add(record.get('scientific_solver_commit', 'UNAVAILABLE'))
            calls.append(record.get('retry_count'))
        require((complete['runs'], complete['completed'], complete['algorithm_failures'], complete['evaluator_terminals']) ==
                (len(records), statuses['COMPLETED'], statuses[ALGORITHM], len(evaluations)), 'Batch summary/counts differ from original rows')
        samples = meta.read(folder/'RESOURCES.jsonl', 'batch_resource_sampling_windows', number, lines=True)
        row = {'batch': number, 'batch_status': complete['status'], 'native_terminals': len(records),
            'native_COMPLETED': statuses['COMPLETED'], 'native_ALL_YAW_REJECTED': statuses[ALGORITHM],
            **{v+'_'+s: sum(r['evaluator_version'] == v and r['evaluation_status'] == s for r in evaluations)
               for v in ('v3', 'v2') for s in ('COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE')},
            'solver_repeat_calls_recorded': sum(calls) if all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in calls) else 'UNAVAILABLE',
            'evaluator_repeat_calls_recorded': complete['resources'].get('evaluator_repeat_calls', 'UNAVAILABLE'),
            'prior_evaluator_terminal_rows_recovered': complete['resources'].get('prior_terminal_rows_recovered', 'UNAVAILABLE'),
            'archive_write_workers': archive.get('write_workers', 'UNAVAILABLE'),
            'archive_status': archive['status'], 'archive_verified_receipts': len(records),
            'archive_pending': 0, 'archive_current_batch_gate': archive['current_batch_gate']['status'],
            'archive_wall_seconds': archive.get('archive_wall_seconds', 'UNAVAILABLE'),
            'batch_scientific_code_commit': complete['code_commit'],
            'archive_v21_scientific_code_commit': archive['v21_scientific_code_commit'],
            'archive_inherited_pre_correction_scientific_code_commit': archive.get('scientific_code_commit', 'UNAVAILABLE'),
            'preserved_mathematical_solver_commits': ';'.join(sorted(solver_commits)),
            'input_data_mode_counts_json': json.dumps(modes, sort_keys=True),
            **resource_summary(samples), **cleanup_summary(meta, controller, number, scratch, originals)}
        batch_rows.append(row)
    terminal_rows = [dict(zip(TERMINAL_FIELDS, key), run_count=count) for key, count in sorted(terminal_counts.items())]
    require(len(all_runs) == min(through_batch*256, 5880), 'Checkpoint unique-run closure differs')
    # A progressing controller cannot be mislabeled as the checked checkpoint.
    require(canonical_json(meta.read(stage/'STATUS.json', 'controller_status')) == canonical_json(status),
            'Controller advanced during bookkeeping export')
    stem = f'docs/paper_rebuild/clean6/P13_THROUGH_BATCH{through_batch:03d}'
    outputs = {stem+'_BATCHES.csv': csv_text(batch_rows),
        stem+'_TERMINALS.csv': csv_text(terminal_rows, (*TERMINAL_FIELDS, 'run_count')),
        stem+'_EVIDENCE.csv': csv_text(sorted(meta.evidence.values(), key=lambda r: r['path']),
                                     ('role', 'batch', 'run_id', 'path', 'size_bytes', 'sha256'))}
    scientific = sorted({r['batch_scientific_code_commit'] for r in batch_rows})
    lines = [f'# P-13 v2.1 checkpoint through batch {through_batch:03d}', '',
        f"Controller status: `{status['status']}`. Closed batches: {through_batch}. Native terminals: {len(all_runs)}; evaluator terminals: {len(all_runs)*2}.",
        'Data mode: `execution_metadata_only`; synthetic_data_used=false; semisynthetic_data_used=false. Input data-mode counts are disclosed per batch; this export contains no performance measurements.',
        f"Scientific execution commits (BATCH_COMPLETE.code_commit): `{';'.join(scientific)}`; each batch, archive v21 identity and native record is bound to `<CLEAN_ROOT>/stages/{STAGE}/00_PREREGISTRATION/EXECUTION_FREEZE.json` and its independently listed metadata SHA-256.",
        f'Exporter source: `<CODE_ROOT>/{SCRIPT}`; SHA-256 `{digest(source)}`. No exporter Git commit is inferred.', '',
        '| Batch | Native COMPLETED | ALL_YAW_REJECTED | v3 completed / not run | v2 completed / not run | Archive workers | Receipt count | Archive gate |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    lines += [f"| {r['batch']:03d} | {r['native_COMPLETED']} | {r['native_ALL_YAW_REJECTED']} | {r['v3_COMPLETED']} / {r['v3_NOT_RUN_ALGORITHM_FAILURE']} | {r['v2_COMPLETED']} / {r['v2_NOT_RUN_ALGORITHM_FAILURE']} | {r['archive_write_workers']} | {r['archive_verified_receipts']} | {r['archive_current_batch_gate']} |" for r in batch_rows]
    lines += ['', 'Every batch RUN_RECORD equals its independent CONTROLLER/RESOLVED_RUNS record by canonical JSON (sorted keys, compact separators), preserving bool/int/float scalar identities. Evaluations use the same canonical JSON comparison after indexing by run_id/evaluator_version. Every receipt reference matches the complete receipt metadata SHA-256 and ARCHIVE_VERIFIED identity; native file pins are compared as metadata only. Current pending archive work: 0.',
        'The v21_scientific_code_commit is recorded separately from the inherited pre-correction archive scientific_code_commit. scientific_solver_commit remains the preserved mathematical-source identity; it is not asserted equal to the v2.1 execution commit.',
        'Repeat-call counts are the recorded native retry_count sum and evaluator_repeat_calls field, not an inference from duplicate-free result rows. Recovered evaluator terminals are not new calls.',
        'Resource figures cover only RESOURCES.jsonl observed elapsed-time windows; monitor restarts form separate windows. RSS is sampled summed process RSS, including shared pages per process; host memory/filesystem samples include concurrent activity. No whole-run peak or missing interval is inferred.',
        'Cleanup counts require both the deduplicated DELETE_INTENT inventory and DELETED inventory to equal the complete receipt-original plus prepared-plan inventory by path, size and SHA-256, with each deletion preceded by a matching intent. No deleted payload is reopened. Missing, incomplete or contradictory optional cleanup evidence is marked UNAVAILABLE.',
        'An export inconsistency is a bookkeeping issue. This script invokes no provider, solver or evaluator, changes no scientific status, and creates no additional scientific stopping condition.', '',
        'Files: ' + ', '.join('`<CODE_ROOT>/'+name+'`' for name in outputs), '']
    outputs[stem+'.md'] = '\n'.join(lines)
    for text in outputs.values():
        require(not re.search(r'(?<![A-Za-z0-9_])/(?:mnt|home|tmp|media|run)/', text), 'Unaliased local path in tracked export')
    return outputs


def publish(code_root, outputs):
    """Preflight all destinations; equal bytes may be reused, differing bytes stay."""
    code = safe_path(code_root)
    staged = []
    for relative, text in outputs.items():
        require(re.fullmatch(r'docs/paper_rebuild/clean6/P13_THROUGH_BATCH(?:008|016|023)(?:_(?:BATCHES|TERMINALS|EVIDENCE)\.csv|\.md)', relative),
                'Output is outside the four checkpoint filenames')
        path, payload = safe_path(code/relative), text.encode('utf-8')
        require(path.is_relative_to(code), 'Output escapes code root')
        require(not path.exists() or (path.is_file() and path.read_bytes() == payload),
                'Existing checkpoint differs; refusing overwrite: <CODE_ROOT>/'+relative)
        staged.append((path, payload))
    created, reused = [], []
    for path, payload in staged:
        relative = '<CODE_ROOT>/'+path.relative_to(code).as_posix()
        if path.exists():
            reused.append(relative)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(payload)
        created.append(relative)
    return {'status': 'EXPORTED_CLOSED_P13_CHECKPOINT_METADATA', 'created': created, 'reused_identical': reused,
            'provider_calls': 0, 'solver_calls': 0, 'evaluator_calls': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-root', required=True)
    parser.add_argument('--code-root', required=True)
    parser.add_argument('--through-batch', type=int, choices=(8, 16, 23), required=True)
    args = parser.parse_args(argv)
    try:
        outputs = prepare(args.stage_root, args.code_root, args.through_batch)
        print(json.dumps(publish(args.code_root, outputs), sort_keys=True))
    except (BookkeepingError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'BOOKKEEPING_EXPORT_NOT_WRITTEN_OR_INCOMPLETE',
            'scientific_state_changed': False, 'error': str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
