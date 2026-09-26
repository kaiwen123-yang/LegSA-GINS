"""Five bounded 99-run addendum batches; no core execution or core aggregation."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

from ..clean5_degradation.common import registry, resolve, pinned, resolved_pins, read_csv, write_json, write_csv
from ..clean5_degradation.providers import build_base
from ..clean5_degradation.runtime import checkpoint
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..clean6_canonical_v2.resources import solver_workers, choose_evaluator_workers
from ..clean6_canonical_v2.storage import (inventory, retain_run, cleanup_exact, append_json,
                                         ResourceMonitor, machine_state)
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .providers import generate_case, STAGE_NAME, SOURCES, DURATIONS


def now():
    return datetime.now(timezone.utc).isoformat()


def load_contract(path):
    contract = yaml.safe_load(Path(path).read_text())
    if (contract['schema_version'] != 'paper_rebuild.clean6.addendum_a1_a2.v1'
            or contract['stage_root'] != '<CLEAN_ROOT>/stages/'+STAGE_NAME
            or contract['runtime']['solver_limit'] != 495 or contract['execution']['solver_workers'] != 22
            or contract['execution']['batch_size'] != 99):
        raise ValueError('Addendum identity/count/resource contract mismatch')
    cases = contract['case_rows']
    expected = {(tid, d, 'seed_'+str(i).zfill(2)) for tid in DURATIONS for d in DURATIONS[tid] for i in range(9)}
    if len(cases) != 45 or {(c['degradation_type_id'], c['duration_s'], c['seed_index']) for c in cases} != expected:
        raise ValueError('Addendum case grid must be exactly 45 distinct family/duration/seed identities')
    if len({c['case_id'] for c in cases}) != 45 or len(contract['runtime']['profiles']) != 11:
        raise ValueError('Duplicate case or missing method identity')
    from ..canonical541.provider_generator import _interval
    anchors = {a['seed_index']: a for a in contract['anchors']['rows']}
    for case in cases:
        anchor = anchors[case['seed_index']]
        if (float(anchor['anchor_time_s']) != case['anchor_time_s'] or int(anchor['seed_value']) != case['seed_value']
                or tuple(case['sources']) != SOURCES[case['degradation_type_id']]
                or _interval(case, case['duration_s']) != (case['outage_start_s'], case['outage_end_s'])):
            raise ValueError('Case differs from its registered canonical seed/anchor/outage')
    return contract


def make_runs(contract, frozen_rows):
    templates = {r['method_id']: r for r in frozen_rows if r['case_id'] == 'C00_clean_normal'}
    if set(templates) != set(contract['runtime']['profiles']):
        raise ValueError('Eleven frozen C00 method templates required')
    runs = []
    for case in contract['case_rows']:
        for method in contract['runtime']['profiles']:
            source = dict(templates[method])
            if source['effective_profile'] != contract['profile_configuration_map'][method]:
                raise ValueError('Frozen effective method profile changed')
            source.update(run_id='ADD_RUN_'+str(len(runs)+1).zfill(5), run_order=len(runs),
                          **{k: case[k] for k in ('case_id', 'case_family', 'degradation_type_id', 'seed_index')})
            source.update(native_transport_run_id='RUN_'+str(6001+len(runs)).zfill(5),
                          native_transport_case_id='D01_'+case['seed_index'],
                          native_transport_data_mode='real_base_controlled_degradation',
                          native_case_token_has_scientific_meaning=False)
            runs.append(source)
    return runs


def execution_freeze(args, contract, reg):
    def git(*tokens):
        return subprocess.check_output(['git', *tokens], cwd=reg.code_root)
    path = Path(args.contract)
    rel = path.relative_to(reg.code_root).as_posix()
    head = git('rev-parse', 'HEAD').decode().strip()
    prereg = git('log', '-1', '--format=%H', '--', rel).decode().strip()
    if prereg == head or git('show', 'HEAD:'+rel) != path.read_bytes():
        raise ValueError('Preregistration must be committed before the separate code commit')
    subprocess.run(['git', 'merge-base', '--is-ancestor', prereg, head], cwd=reg.code_root, check=True)
    upstream = git('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}').decode().strip()
    branch = upstream.split('/', 1)[1]
    remote = upstream.split('/', 1)[0]
    observed = git('ls-remote', remote, 'refs/heads/'+branch).decode().split()
    if not observed or observed[0] != head:
        raise ValueError('Current implementation must be pushed before provider generation')
    candidates = git('ls-files', '-z', 'src/legsa_gins/paper_rebuild', 'src/legsa_gins/input_generation',
                     'scripts/paper_rebuild/clean6_run_addendum_a1_a2.py').decode().split('\0')
    source_hashes = {}
    for name in candidates:
        if not name.endswith('.py') or '/publication/' in name and not name.endswith('/derived_tables.py'):
            continue
        # Packaging and document tools are not imported by the execution path.
        if name.endswith(('/clean6_canonical_v2/pack.py', '/clean6_canonical_v2/addendum_pack.py')):
            continue
        source = reg.code_root/name
        if git('show', 'HEAD:'+name) != source.read_bytes():
            raise ValueError('Uncommitted imported scientific source: '+name)
        source_hashes[name] = sha256_file(source)
    own = sorted((reg.code_root/'src/legsa_gins/paper_rebuild/clean6_addendum').glob('*.py'))
    if not own or any(p.relative_to(reg.code_root).as_posix() not in source_hashes for p in own):
        raise ValueError('Addendum implementation has untracked files')
    companion = 'docs/paper_rebuild/clean6/ADDENDUM_NATIVE_IDENTITY_TRANSPORT.md'
    if git('show', 'HEAD:'+companion) != (reg.code_root/companion).read_bytes():
        raise ValueError('Native transport companion must be committed with implementation')
    source_hashes[companion] = sha256_file(reg.code_root/companion)
    return {'code_commit': head, 'contract_commit': prereg, 'contract_hash': sha256_file(path),
            'source_sha256': source_hashes, 'remote_commit': observed[0], 'utc': now()}


def validate_freeze(freeze, args, reg):
    if sha256_file(args.contract) != freeze['contract_hash']:
        raise ValueError('Frozen addendum contract changed')
    for relative, digest in freeze['source_sha256'].items():
        if sha256_file(reg.code_root/relative) != digest:
            raise ValueError('Frozen scientific source changed: '+relative)


def provider_child(args):
    contract, reg = load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    freeze_path = Path(args.freeze_path) if getattr(args, 'freeze_path', None) else stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json'
    if not freeze_path.is_relative_to(stage) or freeze_path.is_symlink():
        raise ValueError('Provider freeze must be an existing record inside this stage')
    freeze = json.loads(freeze_path.read_text())
    validate_freeze(freeze, args, reg)
    if args.code_commit != freeze['code_commit']:
        raise ValueError('Provider code commit differs from execution freeze')
    case = next(c for c in contract['case_rows'] if c['case_id'] == args.case_id)
    for pin in contract['sources']['frozen_injection_library']:
        pinned(pin, reg)
    raw = {r['relative_path']: r['sha256'] for r in read_csv(pinned(contract['sources']['raw_lock'], reg)) if r['dataset'] == 'BY2'}
    if len(raw) != 22:
        raise ValueError('Raw input lineage requires the registered 22 BY2 members')
    base = build_base(resolved_pins(contract['providers']['roles'], reg),
        auxiliary_roles=resolved_pins(contract['providers']['auxiliary_roles'], reg),
        base_time_s=contract['evaluation']['base_time'], raw_input_hashes=raw)
    generate_case(base, case, stage/'02_PROVIDERS', code_commit=freeze['code_commit'], config_hash=freeze['contract_hash'])


def provider_task(case, contract, reg, stage, freeze, args):
    root = stage/'01_PROVIDER_AUDIT'/case['case_id']
    root.mkdir(parents=True, exist_ok=False)
    temporary = root/'tmp'
    temporary.mkdir()
    log = root/'PROVIDER_OPENAT.strace'
    command = ['env', 'PYTHONDONTWRITEBYTECODE=1', 'PYTHONPATH='+str(reg.code_root/'src'),
        *[k+'='+v for k, v in contract['execution']['single_thread_environment'].items()],
        'TMPDIR='+str(temporary), 'MPLCONFIGDIR='+str(temporary), 'XDG_CACHE_HOME='+str(temporary),
        'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat', '-o', str(log),
        sys.executable, str(reg.code_root/'scripts/paper_rebuild/clean6_run_addendum_a1_a2.py'),
        '--operation', 'provider', '--local-config', args.local_config, '--contract', args.contract,
        '--case-id', case['case_id'], '--code-commit', freeze['code_commit']]
    if getattr(args, 'freeze_path', None):
        command.extend(['--freeze-path', args.freeze_path])
    result = run_process_group(command, cwd=reg.code_root, timeout_seconds=1800,
        timeout_message='Addendum provider timeout; no retry', launch_failure_message='Addendum provider launch failed')
    (root/'stdout.log').write_text(result.stdout)
    (root/'stderr.log').write_text(result.stderr)
    opened = audited_open_records(log, reg.code_root)
    forbidden = [r for r in opened if Path(r['path']).name.lower().startswith('trace_')
                 or Path(r['path']).suffix.lower() in ('.bag', '.fpl', '.trace')]
    raw = [r for r in opened if reg.raw_root in Path(r['path']).parents]
    output = stage/'02_PROVIDERS'/case['case_id']
    scope = write_scope_audit(opened, raw_root=reg.raw_root, clean_root=reg.clean_root, allowed_write_roots=[root, output])
    passed = result.returncode == 0 and not forbidden and not raw and scope['pass']
    audit = {'status': 'PASS' if passed else 'FAIL', 'case_id': case['case_id'], 'exit_code': result.returncode,
             'forbidden_open_count': len(forbidden), 'raw_open_count': len(raw), 'scope': scope,
             'strace_sha256': sha256_file(log)}
    write_json(root/'PROVIDER_AUDIT.json', audit)
    if not passed:
        raise RuntimeError('Provider audit failed; preserve scene: '+case['case_id']+' '+result.stderr[-1500:])
    bundle = json.loads((output/'PROVIDER_BUNDLE.json').read_text())
    for pin in bundle['providers'].values():
        pinned(pin, reg)
    write_json(root/'PROVIDER_OUTPUT_SEAL.json', {'status': 'SEALED', 'files': inventory(output)})
    print('PROVIDER', case['case_id'], 'PASS', flush=True)
    return bundle


def owned_sizes(*roots):
    files = [p for root in roots for p in root.rglob('*') if p.is_file()]
    if any(p.is_symlink() for p in files):
        raise ValueError('Symlink in attempt-owned storage')
    return {'logical_bytes': sum(p.stat().st_size for p in files),
            'allocated_bytes': sum(p.stat().st_blocks*512 for p in files), 'file_count': len(files)}


def storage_gate(contract, stage, scratch, destination):
    sizes = owned_sizes(stage, scratch)
    append_json(destination, {'utc': now(), **sizes})
    if max(sizes['logical_bytes'], sizes['allocated_bytes']) >= contract['storage']['peak_limit_bytes']:
        raise ValueError('Attempt-owned storage cap reached; preserve scene')
    return sizes


def cleanup_batch(receipts, report, scratch, monitor):
    """Complete archive gate precedes the first exact-file deletion."""
    if not receipts or any(receipt['status'] != 'ARCHIVE_VERIFIED' for _, _, receipt in receipts):
        raise RuntimeError('Whole-batch archive gate failed; no scratch unlink')
    write_json(report/'BATCH_ARCHIVE_GATE.json', {'status': 'PASS', 'runs': len(receipts),
        'all_archive_receipts_verified_before_first_unlink': True})
    monitor.assert_healthy()
    cleanup_log = report/'EXACT_CLEANUP_LEDGER.jsonl'
    for record, roots, receipt in receipts:
        for role, path in [('solver', Path(record['output_root'])), *roots.items()]:
            cleanup_exact(path, receipt['original_files'][role], cleanup_log, scratch_root=scratch, archive_verified=receipt)
        for staging in receipt['scratch_archive_roots']:
            folder = Path(staging)
            files = inventory(folder)
            write_json(report/'STAGING_INVENTORIES'/(folder.name+'.json'),
                       {'root': str(folder), 'files': files, 'archive_root': receipt['archive_root'],
                        'archive_status': receipt['status']})
            cleanup_exact(folder, files, cleanup_log, scratch_root=scratch, archive_verified=True)


def resolve_archived_records(receipts, evaluations):
    """Keep exact scratch provenance while resolving live archived evidence paths."""
    records, rows = [], []
    by_run = {record['run_id']: (record, roots, receipt) for record, roots, receipt in receipts}
    for record, roots, receipt in receipts:
        destination = Path(receipt['archive_root'])
        records.append({**record, 'scratch_output_root': record['output_root'],
            'output_root': str(destination/'solver'), 'archive_receipt': str(destination/'ARCHIVE_RECEIPT.json')})
    for original in evaluations:
        row = dict(original)
        record, roots, receipt = by_run[row['run_id']]
        destination, version = Path(receipt['archive_root']), row['evaluator_version']
        root = roots[version]
        for key in ('evaluation_output_root', 'source_row', 'error_series_source', 'summary_source', 'outage_metric_source'):
            if row.get(key):
                path = Path(row[key])
                if not path.is_relative_to(root):
                    raise ValueError('Evaluation artifact escaped its exact run root: '+key)
                row['scratch_'+key] = row[key]
                row[key] = str(destination/version/path.relative_to(root))
                if key != 'evaluation_output_root' and not Path(row[key]).is_file():
                    raise ValueError('Required retained evaluation source is missing: '+key)
        row['scratch_native_run_manifest'] = row.get('native_run_manifest')
        row['native_run_manifest'] = str(destination/'solver/RUN_MANIFEST.json') if record['terminal_status'] == 'COMPLETED' else None
        row['output_root'] = str(destination/'solver')
        row['archive_receipt'] = str(destination/'ARCHIVE_RECEIPT.json')
        rows.append(row)
    return records, rows


def run_batch(batch_runs, contract, reg, stage, scratch, freeze, args, batch_no, monitor):
    from .runtime import solve, evaluate
    owned = scratch/('BATCH_'+str(batch_no).zfill(3))
    owned.mkdir(parents=True, exist_ok=False)
    report = stage/'BATCHES'/owned.name
    report.mkdir(parents=True, exist_ok=False)
    cases = {c['case_id']: c for c in contract['case_rows']}
    bundles = {}
    for case_id in dict.fromkeys(r['case_id'] for r in batch_runs):
        bundles[case_id] = provider_task(cases[case_id], contract, reg, stage, freeze, args)
    monitor.assert_healthy()
    storage_gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl')
    records = []
    with ThreadPoolExecutor(max_workers=solver_workers()) as pool:
        futures = {pool.submit(solve, row, bundles[row['case_id']], cases[row['case_id']], contract, reg,
                              owned/'03_RUNS'/row['run_id'], freeze['code_commit']): row for row in batch_runs}
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            write_json(report/'TERMINALS'/(record['run_id']+'.json'), record)
            print('SOLVER', record['run_id'], record['terminal_status'], flush=True)
    records.sort(key=lambda r: r['run_id'])
    write_json(report/'SOLVER_RECORDS.json', records)
    storage_gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl')
    if any(r['terminal_status'] not in ('COMPLETED', 'ALGORITHM_FAILURE_ALL_YAW_REJECTED') for r in records):
        raise RuntimeError('Technical native failure; batch retained without retry or cleanup')
    evaluations, peak = [], 0
    tasks = [(r, v) for r in records for v in ('v3', 'v2')]
    while tasks:
        if peak:
            state = machine_state()
            count = choose_evaluator_workers(state['memory_available_bytes'],
                max(r.get('solver_peak_rss_bytes') or 1 for r in records), peak, state['nproc'])
        else:
            count = 1  # first actual registered evaluation measures RSS; no probe rerun
        wave, tasks = tasks[:count], tasks[count:]
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [pool.submit(evaluate, r, v, contract, reg, owned, freeze['code_commit']) for r, v in wave]
            for future in as_completed(futures):
                row = future.result()
                evaluations.append(row)
                write_json(report/'EVALUATIONS'/(row['run_id']+'_'+row['evaluator_version']+'.json'), row)
                peak = max(peak, row.get('evaluator_peak_rss_bytes') or 0)
                print('EVALUATION', row['run_id'], row['evaluator_version'], row['evaluation_status'], flush=True)
        if any(r['evaluation_status'] not in ('COMPLETED', 'NOT_RUN_ALGORITHM_FAILURE') for r in evaluations):
            raise RuntimeError('Evaluation failure; preserve native/evaluation outputs, no retry')
    write_json(report/'EVALUATION_RECORDS.json', evaluations)
    storage_gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl')
    receipts = []
    for record in records:
        roots = {v: owned/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
        receipt = retain_run(record, roots, stage/'RETAINED_RUNS'/record['run_id'],
            archive_code_commit=freeze['code_commit'], scratch_archive_root=owned/'ARCHIVE_STAGING'/record['run_id'])
        receipts.append((record, roots, receipt))
        write_json(report/'ARCHIVE_RECEIPTS'/(record['run_id']+'.json'), receipt)
        print('ARCHIVE', record['run_id'], receipt['status'], flush=True)
        storage_gate(contract, stage, scratch, report/'OWNED_STORAGE_LEDGER.jsonl')
    resolved_records, resolved_evaluations = resolve_archived_records(receipts, evaluations)
    write_json(report/'RESOLVED_RUN_RECORDS.json', resolved_records)
    write_json(report/'RESOLVED_EVALUATION_RECORDS.json', resolved_evaluations)
    cleanup_batch(receipts, report, scratch, monitor)
    remaining = inventory(owned)
    if remaining:
        raise ValueError('Unexpected scratch members after exact batch cleanup')
    write_json(report/'BATCH_COMPLETE.json', {'status': 'COMPLETED', 'native_terminals': len(records),
        'evaluation_terminals': len(evaluations), 'archive_pending': 0, 'remaining_scratch_files': 0,
        'native_status_counts': dict(Counter(r['terminal_status'] for r in records)), 'utc': now()})
    return resolved_records, resolved_evaluations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--operation', choices=('start', 'provider', 'resume'), default='start')
    parser.add_argument('--case-id')
    parser.add_argument('--code-commit')
    parser.add_argument('--freeze-path')
    parser.add_argument('--continuation-id')
    parser.add_argument('--recovery-snapshot')
    args = parser.parse_args(argv)
    args.local_config, args.contract = str(Path(args.local_config).resolve()), str(Path(args.contract).resolve())
    if args.operation == 'provider':
        provider_child(args)
        return 0
    if args.operation == 'resume':
        from .resume import resume
        return resume(args)
    contract, reg = load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    paths = yaml.safe_load(Path(args.local_config).read_text())['paths']
    scratch = Path(paths[contract['scratch_alias']])
    if not scratch.is_absolute() or any(p.is_symlink() for p in (scratch, *scratch.parents)):
        raise ValueError('Owned scratch requires absolute path without symlinks')
    if stage.exists() or scratch.exists():
        raise FileExistsError('Addendum attempt exists; no automatic overwrite, retry, or regeneration')
    if scratch == reg.clean_root or scratch.is_relative_to(reg.raw_root) or reg.raw_root.is_relative_to(scratch):
        raise ValueError('Scratch overlaps a protected input root')
    parent = next(p for p in scratch.parents if p.exists())
    if subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(parent)], text=True).strip() != 'ext4':
        raise ValueError('Addendum scratch must use WSL ext4')
    if (shutil.disk_usage(reg.clean_root).free < contract['storage']['G_required_free_bytes_before_any_generation']
            or shutil.disk_usage(parent).free < contract['storage']['scratch_required_free_bytes']):
        raise ValueError('Registered free-space gate failed')
    freeze = execution_freeze(args, contract, reg)
    for pin in (contract['core_contract'], contract['runtime']['executable'], contract['runtime']['model'],
                contract['evaluation']['evaluator'], contract['anchors']['policy'], contract['anchors']['manifest'],
                contract['sources']['base_provider_bundle']):
        pinned(pin, reg)
    runs = make_runs(contract, read_csv(pinned(contract['sources']['unique_run_registry'], reg)))
    stage.mkdir(parents=True, exist_ok=False)
    scratch.mkdir(parents=True, exist_ok=False)
    freeze.update(stage_root=str(stage), scratch_root=str(scratch), **contract['data_roles'])
    write_json(stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json', freeze)
    with (stage/'00_PREREGISTRATION/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml').open('xb') as stream:
        stream.write(Path(args.contract).read_bytes())
    with (stage/'00_PREREGISTRATION/ADDENDUM_NATIVE_IDENTITY_TRANSPORT.md').open('xb') as stream:
        stream.write((reg.code_root/'docs/paper_rebuild/clean6/ADDENDUM_NATIVE_IDENTITY_TRANSPORT.md').read_bytes())
    write_csv(stage/'00_PREREGISTRATION/CASE_REGISTRY.csv', contract['case_rows'])
    write_csv(stage/'00_PREREGISTRATION/UNIQUE_RUN_REGISTRY.csv', runs)
    write_csv(stage/'00_PREREGISTRATION/NATIVE_IDENTITY_MAPPING.csv', [{k: row[k] for k in
        ('run_id', 'case_id', 'method_id', 'seed_index', 'effective_profile', 'native_transport_run_id',
         'native_transport_case_id', 'native_transport_data_mode', 'native_case_token_has_scientific_meaning',
         'runtime_config_path', 'runtime_config_file_hash')} for row in runs])
    resolution = {'mode': 'independent_hash_all', 'human_instruction': 'P-09d checkpoints and ledger same as P-09c'}
    started = time.monotonic()
    records, evaluations = [], []
    final_status = None
    monitor = ResourceMonitor(scratch, stage, stage/'RESOURCE_SAMPLES.jsonl')
    monitor.__enter__()
    try:
        checkpoint(contract, reg, stage, 'PRE', resolution)
        for number, first in enumerate(range(0, len(runs), 99), 1):
            validate_freeze(freeze, args, reg)
            monitor.begin_phase('BATCH_'+str(number).zfill(3))
            batch_records, batch_evaluations = run_batch(runs[first:first+99], contract, reg, stage, scratch, freeze, args, number, monitor)
            write_json(stage/'BATCHES'/('BATCH_'+str(number).zfill(3))/'RESOURCE_SUMMARY.json', monitor.end_phase())
            records.extend(batch_records)
            evaluations.extend(batch_evaluations)
            append_json(stage/'BATCH_LEDGER.jsonl', {'batch': number, 'native_terminals': len(records),
                        'evaluation_terminals': len(evaluations), 'archive_pending': 0, 'utc': now()})
        checkpoint(contract, reg, stage, 'POST', resolution)
        from .aggregate import aggregate_all
        statuses = aggregate_all(evaluations, records, contract, stage, freeze['code_commit'])
        seal = {}
        for root in ('00_PREREGISTRATION', '01_CHECKPOINTS', '01_PROVIDER_AUDIT', '13_AGGREGATE_ADDENDUM', 'BATCHES'):
            for member in sorted((stage/root).rglob('*')):
                if member.is_file():
                    seal[member.relative_to(stage).as_posix()] = {'sha256': sha256_file(member), 'size_bytes': member.stat().st_size}
        write_json(stage/'FINAL_RECORD_SEAL.json', {'status': 'SEALED', 'files': seal,
            'code_commit': freeze['code_commit'], 'retained_payload_seals': 'RETAINED_RUNS/*/ARCHIVE_RECEIPT.json',
            'provider_payload_seals': '01_PROVIDER_AUDIT/*/PROVIDER_OUTPUT_SEAL.json'})
        final_status = {'terminal_status': 'PASS_ADDENDUM_FAMILIES_A1_A2_COMPLETE',
            'native_terminal_count': len(records), 'evaluation_terminal_count': len(evaluations),
            'native_status_counts': dict(Counter(r['terminal_status'] for r in records)),
            'evaluation_status_counts': dict(Counter(r['evaluation_status'] for r in evaluations)),
            'native_retry_count': 0, 'evaluator_retry_count': 0, 'core_solver_calls': 0, 'core_evaluator_calls': 0,
            'archive_pending': 0, 'aggregate_statuses': statuses, 'code_commit': freeze['code_commit'],
            'contract_hash': freeze['contract_hash'], 'total_wall_seconds': time.monotonic()-started,
            'utc': now(), **contract['data_roles']}
    except Exception as error:
        write_json(stage/'STOPPED.json', {'status': 'STOPPED_GATE_FAILURE', 'reason': str(error),
            'native_terminal_count_completed_batches': len(records), 'evaluation_terminal_count_completed_batches': len(evaluations),
            'scene_retained': True, 'native_retry_count': 0, 'evaluator_retry_count': 0, 'utc': now()})
        raise
    finally:
        monitor.__exit__(*sys.exc_info())
        write_json(stage/'RESOURCE_SUMMARY.json', monitor.result())
    write_json(stage/'FINAL_STATUS.json', final_status)
    return 0
