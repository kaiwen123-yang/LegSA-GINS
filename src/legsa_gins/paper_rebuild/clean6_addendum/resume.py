"""One bounded BOM bookkeeping continuation; completed science is never repeated."""
from __future__ import annotations

import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import subprocess
import time
import sys

import yaml

from ..clean5_degradation.common import registry, resolve, pinned, read_csv, write_json
from ..clean5_degradation.runtime import checkpoint
from ..clean6_canonical_v2.storage import (inventory, retain_run, ResourceMonitor, append_json, machine_state)
from ..clean6_canonical_v2.resources import choose_evaluator_workers
from ..manifest import sha256_file
from . import runner
from .runtime import evaluate, finish_evaluation
from .aggregate import aggregate_all

ORIGINAL_COMMIT = 'f93cb84c2e67432873362fe00324d1c2c28fd899'
FIRST_RECORDS_SHA = '9ced9cd3ad6c6af3b8d477ca66d32e37a347c5cc92f4ff9944d9e6fff78352ab'
FIRST_EVALUATION_SHA = 'ce198eb660a854a152cb567c75f8e33982c75172658e1c2ac4556692afc1f890'
BASE = 'src/legsa_gins/paper_rebuild/clean6_addendum/'
ALLOWED_CHANGED = {BASE+name for name in ('aggregate.py', 'runtime.py', 'runner.py')}
ERRATUM = 'docs/paper_rebuild/clean6/ADDENDUM_METRIC_WORDING_ERRATUM.md'


def functions(text):
    return {node.name: ast.get_source_segment(text, node) for node in ast.parse(text).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def validate_allowed_repair(original, new, reg):
    """Check actual source deltas and retain all numerical hypothesis functions."""
    changed = {name for name, old in original['source_sha256'].items()
               if sha256_file(reg.code_root/name) != old}
    if changed-ALLOWED_CHANGED:
        raise ValueError('Continuation changes an unauthorized original scientific source: '+str(sorted(changed-ALLOWED_CHANGED)))
    original_functions = {}
    for name in ('aggregate.py', 'runtime.py', 'runner.py'):
        path = BASE+name
        before = subprocess.check_output(['git', 'show', ORIGINAL_COMMIT+':'+path], cwd=reg.code_root).decode()
        after = (reg.code_root/path).read_text()
        left, right = functions(before), functions(after)
        original_functions[name] = left
        protected = (('wilcoxon', 'paired_tables', 'hypothesis_tables') if name == 'aggregate.py'
                     else ('native_template', 'solve') if name == 'runtime.py'
                     else tuple(set(left)-{'provider_child', 'provider_task', 'main'}))
        for function in protected:
            if left[function] != right[function]:
                raise ValueError('BOM continuation changed protected function '+name+':'+function)
        if name == 'aggregate.py':
            expected = left['outage_metrics'].replace("with opener(path, 'rt', newline='')",
                "with opener(path, 'rt', encoding='utf-8-sig', newline='')")
            if expected != right['outage_metrics']:
                raise ValueError('Outage metric change exceeds UTF-8 BOM decoding')
            old = ast.parse(left['aggregate_all']).body[0]
            current = ast.parse(right['aggregate_all']).body[0]
            def strip_metadata(node):
                for child in ast.walk(node):
                    for field, value in ast.iter_fields(child):
                        if isinstance(value, list):
                            setattr(child, field, [item for item in value if not (
                                isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                                and isinstance(item.value.func, ast.Name) and item.value.func.id == 'write_json'
                                and item.value.args and 'FIELD_DEFINITIONS.json' in ast.unparse(item.value.args[0]))])
                return ast.dump(node, include_attributes=False)
            if strip_metadata(old) != strip_metadata(current):
                raise ValueError('Aggregation changed outside FIELD_DEFINITIONS wording metadata')
    new['original_execution_code_commit'] = ORIGINAL_COMMIT
    new['authorized_changed_original_source_paths'] = sorted(changed)
    new['repair_scope'] = 'UTF-8 BOM decoding; continuation and exclusive evaluator-attempt bookkeeping; field-definition wording only'
    new['numerical_hypothesis_functions_unchanged'] = True


def check_files(root, pins, *, exact=False):
    root = Path(root)
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Symlink in recovered output path')
    if exact:
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        if actual != set(pins):
            raise ValueError('Recovered output member set changed')
    for relative, pin in pins.items():
        part = Path(relative)
        path = root/part
        if (part.is_absolute() or '..' in part.parts or path.is_symlink() or not path.is_file()
                or path.stat().st_size != pin['size_bytes'] or sha256_file(path) != pin['sha256']):
            raise ValueError('Recovered sealed output mismatch: '+str(path))


def recover_scene(contract, reg, stage, scratch, snapshot_path):
    """Read-only closure of the exact stopped scene before any continuation writes."""
    stopped_path = stage/'STOPPED.json'
    stopped = json.loads(stopped_path.read_text())
    if stopped.get('status') != 'STOPPED_GATE_FAILURE' or stopped.get('reason') != "'time'":
        raise ValueError('Continuation is only registered for the observed BOM stop')
    source = stage/'BATCHES/BATCH_001/SOLVER_RECORDS.json'
    if sha256_file(source) != FIRST_RECORDS_SHA:
        raise ValueError('Original 99-record terminal collection changed')
    records = json.loads(source.read_text())
    expected_runs = runner.make_runs(contract, read_csv(pinned(contract['sources']['unique_run_registry'], reg)))
    if (len(records) != 99 or [r['run_id'] for r in records] != [r['run_id'] for r in expected_runs[:99]]
            or any(r['terminal_status'] != 'COMPLETED' or r['code_commit'] != ORIGINAL_COMMIT for r in records)):
        raise ValueError('The 99 completed native identities do not match the stopped scene')
    for record in records:
        root = scratch/'BATCH_001/03_RUNS'/record['run_id']
        if Path(record['output_root']) != root:
            raise ValueError('Recovered native root escapes its registered scratch identity')
        seal = json.loads((root/'OUTPUT_SEAL.json').read_text())
        if seal.get('status') != 'SEALED_BEFORE_EVALUATION' or seal['files'] != record['output_seal']:
            raise ValueError('Original native seal differs from its terminal record')
        check_files(root, seal['files'])
    for case_id in dict.fromkeys(r['case_id'] for r in records):
        provider_root = stage/'02_PROVIDERS'/case_id
        pin = json.loads((stage/'01_PROVIDER_AUDIT'/case_id/'PROVIDER_OUTPUT_SEAL.json').read_text())
        check_files(provider_root, pin['files'], exact=True)
        if json.loads((stage/'01_PROVIDER_AUDIT'/case_id/'PROVIDER_AUDIT.json').read_text())['status'] != 'PASS':
            raise ValueError('Original provider audit is not PASS')
    first_root = scratch/'BATCH_001/12_OFFLINE_EVALUATION/v3/ADD_RUN_00001'
    snapshot_path = Path(snapshot_path)
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise ValueError('Explicit current evaluator snapshot is required')
    snapshot = json.loads(snapshot_path.read_text())
    if (snapshot.get('status') != 'CURRENT_POST_STOP_SNAPSHOT_BEFORE_PARSER_REPAIR'
            or snapshot.get('historical_full_file_derived_seal_available') is not False
            or Path(snapshot['source']) != first_root or len(snapshot['files']) != 13):
        raise ValueError('Current evaluator snapshot identity differs from the original stop')
    pins = {r['relative_path']: r for r in snapshot['files']}
    check_files(first_root, pins, exact=True)
    if sha256_file(first_root/'EVALUATION_RESULT.json') != FIRST_EVALUATION_SHA:
        raise ValueError('First completed evaluator terminal changed')
    first = json.loads((first_root/'EVALUATION_RESULT.json').read_text())
    if (first['evaluation_status'] != 'COMPLETED' or first['evaluation_invoked'] is not True
            or first['run_id'] != records[0]['run_id'] or first['evaluator_version'] != 'v3'):
        raise ValueError('The existing first evaluation is not a completed reusable terminal')
    existing = [p for p in (scratch/'BATCH_001/12_OFFLINE_EVALUATION').glob('*/*') if p.is_dir()]
    if existing != [first_root]:
        raise ValueError('Unexpected extra evaluation attempt; never retry or substitute')
    for number in range(2, 6):
        if (scratch/f'BATCH_{number:03d}').exists() or (stage/f'BATCHES/BATCH_{number:03d}').exists():
            raise ValueError('A future native batch already started; no automatic rerun')
    if (stage/'RETAINED_RUNS').exists() or (stage/'FINAL_STATUS.json').exists():
        raise ValueError('Unexpected archive/completion before this bounded continuation')
    return records, first, snapshot, expected_runs, {'STOPPED.json': sha256_file(stopped_path),
        'RESOURCE_SUMMARY.json': sha256_file(stage/'RESOURCE_SUMMARY.json'),
        'RESOURCE_SAMPLES.jsonl': sha256_file(stage/'RESOURCE_SAMPLES.jsonl'),
        'BATCHES/BATCH_001/SOLVER_RECORDS.json': FIRST_RECORDS_SHA}


def recover_first_batch(records, first, snapshot, contract, reg, stage, scratch, target, freeze, monitor):
    """Complete 197 unstarted evaluator identities; no native or provider call."""
    owned = scratch/'BATCH_001'
    report = target/'BATCHES/BATCH_001'
    report.mkdir(parents=True, exist_ok=False)
    copied = [{**record, 'continuation_code_commit': freeze['code_commit'],
               'original_native_reused': True, 'original_native_code_commit': record['code_commit'],
               'recovery_validation': 'ORIGINAL_FULL_FILE_SEAL_HASH_VERIFIED; no native rerun'} for record in records]
    first = {**first, 'continuation_code_commit': freeze['code_commit'],
             'original_completed_evaluation_reused': True, 'original_evaluation_code_commit': first['code_commit'],
             'historical_full_file_derived_seal_available': False,
             'current_post_stop_snapshot': str(target/'CURRENT_POST_STOP_EVALUATION_SNAPSHOT.json')}
    recovered = finish_evaluation(first, copied[0], contract, freeze['code_commit'])
    # Existing 13 files must remain byte-identical after sidecar-only completion.
    check_files(Path(snapshot['source']), {r['relative_path']: r for r in snapshot['files']})
    evaluations = [recovered]
    write_json(report/'RECOVERED_FIRST_EVALUATION.json', recovered)
    tasks = [(r, version) for r in copied for version in ('v3', 'v2')
             if not (r['run_id'] == 'ADD_RUN_00001' and version == 'v3')]
    write_json(report/'UNSTARTED_EVALUATION_IDENTITIES.json',
               [{'run_id': r['run_id'], 'evaluator_version': v, 'prior_invocation_count': 0} for r, v in tasks])
    if len(tasks) != 197:
        raise ValueError('Exactly 197 first-batch evaluator identities remain unstarted')
    peak = first.get('evaluator_peak_rss_bytes') or 0
    while tasks:
        state = machine_state()
        count = choose_evaluator_workers(state['memory_available_bytes'],
            max(r.get('solver_peak_rss_bytes') or 1 for r in copied), peak, state['nproc']) if peak else 1
        wave, tasks = tasks[:count], tasks[count:]
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [pool.submit(evaluate, r, v, contract, reg, owned, freeze['code_commit']) for r, v in wave]
            for future in as_completed(futures):
                row = future.result()
                evaluations.append(row)
                write_json(report/'EVALUATIONS'/(row['run_id']+'_'+row['evaluator_version']+'.json'), row)
                peak = max(peak, row.get('evaluator_peak_rss_bytes') or 0)
                print('EVALUATION', row['run_id'], row['evaluator_version'], row['evaluation_status'], flush=True)
        if any(r['evaluation_status'] != 'COMPLETED' for r in evaluations):
            raise RuntimeError('New first-batch evaluator failed; preserve scene without retry')
    write_json(report/'SOLVER_RECORDS.json', copied)
    write_json(report/'EVALUATION_RECORDS.json', evaluations)
    receipts = []
    for record in copied:
        roots = {v: owned/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
        receipt = retain_run(record, roots, stage/'RETAINED_RUNS'/record['run_id'],
            archive_code_commit=freeze['code_commit'], scratch_archive_root=owned/'ARCHIVE_STAGING'/record['run_id'])
        receipts.append((record, roots, receipt))
        write_json(report/'ARCHIVE_RECEIPTS'/(record['run_id']+'.json'), receipt)
        print('ARCHIVE', record['run_id'], receipt['status'], flush=True)
        runner.storage_gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl')
    resolved_records, resolved_evaluations = runner.resolve_archived_records(receipts, evaluations)
    write_json(report/'RESOLVED_RUN_RECORDS.json', resolved_records)
    write_json(report/'RESOLVED_EVALUATION_RECORDS.json', resolved_evaluations)
    runner.cleanup_batch(receipts, report, scratch, monitor)
    if inventory(owned):
        raise ValueError('Unexpected first-batch scratch members after exact cleanup')
    write_json(report/'BATCH_COMPLETE.json', {'status': 'COMPLETED', 'native_terminals': 99,
        'evaluation_terminals': 198, 'archive_pending': 0, 'remaining_scratch_files': 0,
        'native_calls_this_continuation_batch': 0, 'new_evaluator_calls': 197,
        'completed_evaluation_reused': 1, 'utc': runner.now()})
    return resolved_records, resolved_evaluations


def resume(args):
    if not args.recovery_snapshot:
        raise ValueError('--recovery-snapshot must identify the preserved current post-stop snapshot')
    contract, reg = runner.load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    original = json.loads((stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json').read_text())
    if original['code_commit'] != ORIGINAL_COMMIT:
        raise ValueError('This continuation only accepts the recorded f93cb84 BOM stop')
    paths = yaml.safe_load(Path(args.local_config).read_text())['paths']
    scratch = Path(paths[contract['scratch_alias']])
    if str(scratch) != original['scratch_root'] or str(stage) != original['stage_root']:
        raise ValueError('Original stage/scratch identity changed')
    continuation_id = args.continuation_id or 'BOM_RECOVERY_'+time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    if not re.fullmatch(r'BOM_RECOVERY_[A-Za-z0-9_]+', continuation_id):
        raise ValueError('Explicit safe BOM recovery identity required')
    target = stage/'CONTINUATIONS'/continuation_id
    if target.exists() or target.is_symlink():
        raise FileExistsError('Continuation already exists; preserve it without overwrite')
    freeze = runner.execution_freeze(args, contract, reg)
    if freeze['contract_hash'] != original['contract_hash']:
        raise ValueError('Preregistered contract changed')
    validate_allowed_repair(original, freeze, reg)
    for pin in (contract['runtime']['executable'], contract['runtime']['model'], contract['evaluation']['evaluator']):
        pinned(pin, reg)
    erratum = reg.code_root/ERRATUM
    if subprocess.check_output(['git', 'show', freeze['code_commit']+':'+ERRATUM], cwd=reg.code_root) != erratum.read_bytes():
        raise ValueError('Metric wording companion must be committed before continuation')
    freeze['source_sha256'][ERRATUM] = sha256_file(erratum)
    records, first, snapshot, runs, preserved = recover_scene(contract, reg, stage, scratch, args.recovery_snapshot)
    freeze.update(original_execution_freeze=original, preserved_prior_records_sha256=preserved,
                  original_native_reused_count=99, original_completed_evaluation_reused_count=1,
                  native_retry_count=0, evaluator_retry_count=0, historical_full_file_derived_seal_available=False,
                  stage_root=str(stage), scratch_root=str(scratch), continuation_root=str(target), **contract['data_roles'])
    target.mkdir(parents=True, exist_ok=False)
    write_json(target/'EXECUTION_FREEZE.json', freeze)
    write_json(target/'CURRENT_POST_STOP_EVALUATION_SNAPSHOT.json', snapshot)
    with (target/'ADDENDUM_METRIC_WORDING_ERRATUM.md').open('xb') as stream:
        stream.write(erratum.read_bytes())
    args.freeze_path = str(target/'EXECUTION_FREEZE.json')
    monitor = ResourceMonitor(scratch, stage, target/'RESOURCE_SAMPLES.jsonl')
    monitor.__enter__()
    started = time.monotonic()
    all_records, evaluations, final = [], [], None
    try:
        monitor.begin_phase('BATCH_001_BOOKKEEPING_CONTINUATION')
        all_records, evaluations = recover_first_batch(records, first, snapshot, contract, reg, stage, scratch, target, freeze, monitor)
        write_json(target/'BATCHES/BATCH_001/RESOURCE_SUMMARY.json', monitor.end_phase())
        append_json(target/'BATCH_LEDGER.jsonl', {'batch': 1, 'native_terminals': 99, 'evaluation_terminals': 198,
                                               'archive_pending': 0, 'utc': runner.now()})
        for number in range(2, 6):
            runner.validate_freeze(freeze, args, reg)
            monitor.begin_phase(f'BATCH_{number:03d}')
            new_records, new_evaluations = runner.run_batch(runs[(number-1)*99:number*99], contract, reg,
                stage, scratch, freeze, args, number, monitor)
            all_records.extend(new_records)
            evaluations.extend(new_evaluations)
            write_json(stage/f'BATCHES/BATCH_{number:03d}/RESOURCE_SUMMARY.json', monitor.end_phase())
            append_json(target/'BATCH_LEDGER.jsonl', {'batch': number, 'native_terminals': len(all_records),
                'evaluation_terminals': len(evaluations), 'archive_pending': 0, 'utc': runner.now()})
        checkpoint(contract, reg, stage, 'POST', {'mode': 'independent_hash_all',
                   'human_instruction': 'P-09d registered post checkpoint following artifact-only BOM continuation'})
        statuses = aggregate_all(evaluations, all_records, contract, stage, freeze['code_commit'])
        for relative, pin in preserved.items():
            if sha256_file(stage/relative) != pin:
                raise ValueError('A preserved pre-continuation record changed: '+relative)
        final = {'terminal_status': 'PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE', 'native_terminal_count': 495,
            'evaluation_terminal_count': 990, 'native_status_counts': dict(Counter(r['terminal_status'] for r in all_records)),
            'evaluation_status_counts': dict(Counter(r['evaluation_status'] for r in evaluations)),
            'native_retry_count': 0, 'evaluator_retry_count': 0, 'core_solver_calls': 0, 'core_evaluator_calls': 0,
            'archive_pending': 0, 'aggregate_statuses': statuses, 'code_commit': freeze['code_commit'],
            'original_code_commit': ORIGINAL_COMMIT, 'original_native_reused_count': 99,
            'original_completed_evaluation_reused_count': 1, 'new_native_calls_this_continuation': 396,
            'contract_hash': freeze['contract_hash'], 'active_execution_freeze': str(target/'EXECUTION_FREEZE.json'),
            'original_execution_freeze': str(stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json'),
            'prior_stop_preserved': True, 'continuation_wall_seconds': time.monotonic()-started,
            'utc': runner.now(), **contract['data_roles']}
    except Exception as error:
        write_json(target/'STOPPED.json', {'status': 'STOPPED_GATE_FAILURE', 'reason': str(error),
            'native_terminal_count_completed_batches': len(all_records), 'evaluation_terminal_count_completed_batches': len(evaluations),
            'scene_retained': True, 'native_retry_count': 0, 'evaluator_retry_count': 0, 'utc': runner.now()})
        raise
    finally:
        monitor.__exit__(*sys.exc_info())
        write_json(target/'RESOURCE_SUMMARY.json', monitor.result())
    seal = {}
    for dirname in ('00_PREREGISTRATION', '01_CHECKPOINTS', '01_PROVIDER_AUDIT', '01_EVALUATION_CALLS',
                    '13_AGGREGATE_ADDENDUM', 'BATCHES', 'CONTINUATIONS'):
        for member in sorted((stage/dirname).rglob('*')):
            if member.is_file():
                seal[member.relative_to(stage).as_posix()] = {'sha256': sha256_file(member), 'size_bytes': member.stat().st_size}
    write_json(stage/'FINAL_RECORD_SEAL.json', {'status': 'SEALED', 'files': seal,
        'code_commit': freeze['code_commit'], 'original_execution_code_commit': ORIGINAL_COMMIT,
        'retained_payload_seals': 'RETAINED_RUNS/*/ARCHIVE_RECEIPT.json',
        'provider_payload_seals': '01_PROVIDER_AUDIT/*/PROVIDER_OUTPUT_SEAL.json'})
    write_json(stage/'FINAL_STATUS.json', final)
    return 0
