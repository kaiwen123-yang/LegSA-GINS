"""Frozen P-09c batches: providers, solves, seals, evaluation, archive, cleanup."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

from ..clean5_degradation.common import (FLAGS, registry, pinned, resolve, resolved_pins,
                                        write_json, read_csv)
from ..clean5_degradation.runtime import checkpoint
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .contract import load_contract, selection, verify_preregistration, STAGE_NAME
from .runtime import run_one, profile_template, NUMERICAL_FILES
from .storage import (append_json, inventory, retain_run, cleanup_exact,
                      ResourceMonitor, machine_state)


def now():
    return datetime.now(timezone.utc).isoformat()


def freeze_sources(code_root):
    """Record maintained imports and their tracked bytes at execution freeze."""
    paths = subprocess.check_output(['git', 'ls-files', '-z', 'src/legsa_gins/paper_rebuild',
        'src/legsa_gins/input_generation', 'scripts/paper_rebuild', 'configs/paper_rebuild'], cwd=code_root).decode().split('\0')
    return {p: sha256_file(code_root/p) for p in paths if p.endswith(('.py', '.yaml', '.json'))}


def validate_freeze(freeze, contract_path, reg):
    if sha256_file(contract_path) != freeze['contract_hash']:
        raise ValueError('Contract changed after execution freeze')
    for relative, digest in freeze['source_sha256'].items():
        if sha256_file(reg.code_root/relative) != digest:
            raise ValueError('Frozen source changed: '+relative)


def sequence_bundle(contract, reg, stage, dataset, code_commit):
    """Byte-copy the frozen CAL observations; raw source pins checked once."""
    spec = contract['sequences'][dataset]
    original = json.loads(pinned(spec['calibrated_provider_bundle'], reg).read_text())
    root = stage/'02_SEQUENCE_PROVIDERS'/dataset
    root.mkdir(parents=True, exist_ok=False)
    raw = {}
    for role, pin in spec['raw_inputs'].items():
        source = pinned(pin, reg)
        raw[role] = {'path': str(source), 'sha256': pin['sha256']}
    providers = {}
    for role, pin in spec['providers'].items():
        source = pinned(pin, reg)
        destination = root/source.name
        with source.open('rb') as reader, destination.open('xb') as writer:
            shutil.copyfileobj(reader, writer, 1024*1024)
        if sha256_file(destination) != pin['sha256']:
            raise ValueError('Sequence provider copy changed bytes')
        providers[role] = {**pin, 'path': str(destination)}
    bundle = {**FLAGS, 'providers': providers, 'raw_input_hashes': raw,
              'dataset_id': dataset, 'data_mode': spec['data_mode'], 'code_commit': code_commit,
              'frozen_source_bundle': spec['calibrated_provider_bundle'],
              'source_raw_hashes': original.get('raw_source_hashes'), 'byte_identity': True}
    write_json(root/'PROVIDER_BUNDLE.json', bundle)
    return bundle


def provider_child(args):
    from .providers import generate_one
    contract, reg = load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    freeze = json.loads((stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json').read_text())
    if args.code_commit != freeze['code_commit'] or sha256_file(args.contract) != freeze['contract_hash']:
        raise ValueError('Provider child requires the existing committed execution freeze')
    if args.case_id in ('BY2H', 'BY2O'):
        sequence_bundle(contract, reg, stage, args.case_id, args.code_commit)
    else:
        generate_one(contract, reg, stage, args.case_id, args.code_commit, sha256_file(args.contract))


def provider_task(case_id, contract, reg, stage, code_commit, args):
    root = stage/'01_PROVIDER_AUDIT'/case_id
    root.mkdir(parents=True, exist_ok=False)
    tmp = root/'tmp'
    tmp.mkdir()
    log = root/'PROVIDER_OPENAT.strace'
    command = ['env', 'PYTHONDONTWRITEBYTECODE=1', 'PYTHONPATH='+str(reg.code_root/'src'),
        'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', 'NUMEXPR_NUM_THREADS=1',
        'TMPDIR='+str(tmp), 'MPLCONFIGDIR='+str(tmp), 'XDG_CACHE_HOME='+str(tmp),
        'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat', '-o', str(log),
        sys.executable, str(reg.code_root/'scripts/paper_rebuild/clean6_run_canonical541_v2.py'),
        '--operation', 'provider', '--local-config', args.local_config, '--contract', args.contract,
        '--case-id', case_id, '--code-commit', code_commit]
    started = time.monotonic()
    result = run_process_group(command, cwd=reg.code_root, timeout_seconds=1800,
        timeout_message='P09c provider timeout; no retry', launch_failure_message='P09c provider launch failure')
    (root/'stdout.log').write_text(result.stdout)
    (root/'stderr.log').write_text(result.stderr)
    opened = audited_open_records(log, reg.code_root)
    forbidden = [r for r in opened if Path(r['path']).name.lower().startswith('trace_') or
                 Path(r['path']).suffix.lower() in ('.bag', '.fpl')]
    output = stage/'02_SEQUENCE_PROVIDERS'/case_id if case_id in ('BY2H', 'BY2O') else stage/'02_PROVIDERS'/case_id
    scope = write_scope_audit(opened, raw_root=reg.raw_root, clean_root=reg.clean_root,
                              allowed_write_roots=[root, output])
    raw = [r for r in opened if reg.raw_root in Path(r['path']).parents]
    if case_id in ('BY2H', 'BY2O'):
        allowed_raw = {str(resolve(p['path'], reg)) for p in contract['sequences'][case_id]['raw_inputs'].values()}
    else:
        allowed_raw = set()
    passed = (result.returncode == 0 and not forbidden and scope['pass'] and
              all(r['path'] in allowed_raw and 'O_RDONLY' in r['flags'] and r['return_code'] >= 0 for r in raw))
    audit = {'status': 'PASS' if passed else 'FAIL', 'case_id': case_id, 'exit_code': result.returncode,
             'forbidden_open_count': len(forbidden), 'raw_open_count': len(raw), 'scope': scope,
             'runtime_seconds': time.monotonic()-started, 'strace_sha256': sha256_file(log)}
    write_json(root/'PROVIDER_AUDIT.json', audit)
    if not passed:
        raise RuntimeError('Provider failed; preserve scene: '+case_id+' '+result.stderr[-1200:])
    name = 'PROVIDER_BUNDLE.json'
    bundle = json.loads((output/name).read_text())
    for pin in bundle['providers'].values(): pinned(pin, reg)
    write_json(root/'PROVIDER_OUTPUT_SEAL.json', {'files': inventory(output), 'status': 'SEALED'})
    print('PROVIDER', case_id, 'PASS', flush=True)
    return bundle


def create_jobs(contract, reg, runs, cases):
    case_lookup = {r['case_id']: r for r in cases}
    c00 = [r for r in runs if r['case_id'] == 'C00_clean_normal']
    by_method = {r['method_id']: r for r in c00}
    jobs = [{'source': r, 'dataset': 'BY2', 'case_meta': case_lookup[r['case_id']]} for r in c00]
    for dataset in ('BY2H', 'BY2O'):
        spec = contract['sequences'][dataset]
        for method in contract['runtime']['profiles']:
            row = {**by_method[method], 'run_id': f'SEQUENCE_{dataset}_{method}',
                   'case_id': spec['case_id'], 'case_family': 'natural_sequence',
                   'degradation_type_id': 'CLEAN', 'seed_index': ''}
            jobs.append({'source': row, 'dataset': dataset, 'case_meta': spec['case_meta']})
    jobs.extend({'source': r, 'dataset': 'BY2', 'case_meta': case_lookup[r['case_id']]}
                for r in runs if r['case_id'] != 'C00_clean_normal')
    if len(jobs) != 5973 or len({j['source']['run_id'] for j in jobs}) != 5973:
        raise ValueError('Distinct run registry failed')
    return jobs


def execute_job(job, bundles, contract, reg, scratch_batch, code_commit, c00):
    source, dataset = job['source'], job['dataset']
    template = None
    if dataset != 'BY2':
        originals = contract['sequences'][dataset]['original_configs']
        method = source['method_id']
        pin = originals.get(method, originals['F04'])
        template = pinned({'path': pin['runtime_config'], 'sha256': pin['runtime_config_sha256']}, reg).read_text()
        if method not in originals:
            full = Path(c00['F04']['runtime_config_path']).read_text()
            variant = Path(c00[method]['runtime_config_path']).read_text()
            template, changes = profile_template(template, full, variant)
    bundle = bundles[source['case_id'] if dataset == 'BY2' else dataset]
    result = run_one(source, bundle, contract, reg, scratch_batch/'03_RUNS'/source['run_id'],
                     code_commit, original_text=template, dataset=dataset,
                     sequence_spec=contract['sequences'][dataset], case_meta=job['case_meta'])
    print('SOLVER', dataset, source['run_id'], result['terminal_status'], flush=True)
    return result


def anchor_gate(records, contract):
    lookup = {(r['dataset_id'], r['method_id']): r for r in records}
    refs = [('P07_C00', 'BY2', r) for r in contract['anchors']['C00_profiles']]
    refs += [('P06_CAL', r['dataset_id'], r) for r in contract['sequence_consistency']['references']]
    checks = []
    for origin, dataset, ref in refs:
        row = lookup.get((dataset, ref['method_id']))
        for name, expected in ref['files_sha256'].items():
            actual = row.get('output_seal', {}).get(name, {}).get('sha256') if row else None
            checks.append({'origin': origin, 'dataset_id': dataset, 'method_id': ref['method_id'],
                           'file': name, 'expected_sha256': expected, 'actual_sha256': actual,
                           'byte_equal': actual == expected})
    closed = (len(records) == 33 and len(lookup) == 33 and
              all(r['terminal_status'] == 'COMPLETED' for r in records) and
              len({r['code_commit'] for r in records}) == 1)
    return {'status': 'PASS' if closed and all(c['byte_equal'] for c in checks) else 'FAIL',
            'sequence_runs': len(records), 'all_33_completed_same_freeze': closed,
            'P07_C00_profiles': 11, 'P06_reference_runs': 15,
            'file_comparisons': len(checks), 'matching_files': sum(c['byte_equal'] for c in checks),
            'checks': checks}


def run_group(jobs, pool, bundles, contract, reg, scratch_batch, code_commit, c00):
    futures = [pool.submit(execute_job, job, bundles, contract, reg, scratch_batch, code_commit, c00) for job in jobs]
    records = []
    for future in as_completed(futures): records.append(future.result())
    records.sort(key=lambda r: next(i for i, job in enumerate(jobs) if job['source']['run_id'] == r['run_id']))
    return records


def do_batch(batch_number, jobs, contract, reg, stage, scratch, code_commit, args, workers, c00):
    from .evaluation import one_evaluation
    batch_id = f'BATCH_{batch_number:03d}'
    output = stage/'BATCHES'/batch_id
    output.mkdir(parents=True, exist_ok=False)
    scratch_batch = scratch/batch_id
    scratch_batch.mkdir(parents=True, exist_ok=False)
    append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'BATCH_START', 'batch': batch_number,
        'workers': workers, 'run_count': len(jobs), 'utc': now(), 'code_commit': code_commit})
    all_records, evaluations, receipts = [], [], []
    with ResourceMonitor(scratch, reg.clean_root, output/'RESOURCE_SAMPLES.jsonl') as monitor:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            keys = list(dict.fromkeys(j['source']['case_id'] if j['dataset'] == 'BY2' else j['dataset'] for j in jobs))
            bundles, pending = {}, {}
            for key in keys:
                root = stage/('02_SEQUENCE_PROVIDERS' if key in ('BY2H', 'BY2O') else '02_PROVIDERS')/key
                name = 'PROVIDER_BUNDLE.json'
                if (root/name).is_file():
                    audit = json.loads((stage/'01_PROVIDER_AUDIT'/key/'PROVIDER_AUDIT.json').read_text())
                    if audit['status'] != 'PASS': raise ValueError('Prior provider terminal not PASS')
                    bundles[key] = json.loads((root/name).read_text())
                    for pin in bundles[key]['providers'].values(): pinned(pin, reg)
                else:
                    pending[pool.submit(provider_task, key, contract, reg, stage, code_commit, args)] = key
            for future in as_completed(pending): bundles[pending[future]] = future.result()
            groups = (jobs[:33], jobs[33:]) if batch_number == 1 else (jobs,)
            for index, group in enumerate(groups):
                records = run_group(group, pool, bundles, contract, reg, scratch_batch, code_commit, c00)
                all_records.extend(records)
                write_json(output/f'SOLVER_GROUP_{index}.json', records)
                if batch_number == 1 and index == 0:
                    gate = anchor_gate(records, contract)
                    write_json(stage/'SEQUENCE_CONSISTENCY_GATE.json', gate)
                    if gate['status'] != 'PASS':
                        raise RuntimeError('Sequence/C00 byte gate failed; no remaining pilot solver launched')
                if any(r['terminal_status'] == 'FAILED_TECHNICAL' for r in records):
                    raise RuntimeError('Technical solver failure; batch stopped, no retry or cleanup')
            tasks = [pool.submit(one_evaluation, r, v, contract, reg, scratch_batch, code_commit)
                     for r in all_records for v in ('v3', 'v2')]
            for future in as_completed(tasks):
                row = future.result()
                evaluations.append(row)
                print('EVALUATOR', row['run_id'], row['evaluator_version'], row['evaluation_status'], flush=True)
            write_json(output/'SOLVER_RECORDS_BEFORE_ARCHIVE.json', all_records)
            write_json(output/'EVALUATION_RECORDS_BEFORE_ARCHIVE.json', evaluations)
            permitted = {'PASS', 'COMPLETED', 'SUCCESS', 'NOT_RUN_ALGORITHM_FAILURE'}
            if any(r['evaluation_status'] not in permitted for r in evaluations):
                raise RuntimeError('Evaluation or WGS84 self-check failed; retain full batch scene')
            pending_archive = {}
            for record in all_records:
                roots = {v: scratch_batch/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
                destination = stage/'RETAINED_RUNS'/record['run_id']
                pending_archive[pool.submit(retain_run, record, roots, destination)] = (record, roots)
            archive_pairs = []
            for future in as_completed(pending_archive):
                receipt = future.result()
                record, roots = pending_archive[future]
                receipts.append(receipt)
                archive_pairs.append((record, roots, receipt))
                print('ARCHIVED', record['run_id'], receipt['retained_bytes'], flush=True)
            write_json(output/'ARCHIVE_RECEIPTS.json', receipts)
            for record in all_records:
                destination = stage/'RETAINED_RUNS'/record['run_id']
                record['scratch_output_root'] = record['output_root']
                record['output_root'] = str(destination/'solver')
                record['archive_receipt'] = str(destination/'ARCHIVE_RECEIPT.json')
            for row in evaluations:
                run_id, version = row['run_id'], row['evaluator_version']
                destination = stage/'RETAINED_RUNS'/run_id
                original_eval = scratch_batch/'12_OFFLINE_EVALUATION'/version/run_id
                for key in ('evaluation_output_root', 'source_row', 'error_series_source', 'summary_source'):
                    if row.get(key):
                        path = Path(row[key])
                        if not path.is_relative_to(original_eval):
                            raise ValueError('Evaluation artifact path escapes run: '+key)
                        row[key] = str(destination/version/path.relative_to(original_eval))
                row['output_root'] = str(destination/'solver')
                row['native_run_manifest'] = str(destination/'solver/RUN_MANIFEST.json')
            write_json(output/'RUN_RECORDS.json', all_records)
            write_json(output/'EVALUATION_RECORDS.json', evaluations)
            # Whole-batch archive barrier before the first unlink.
            write_json(output/'BATCH_ARCHIVE_GATE.json', {'status': 'PASS', 'run_count': len(receipts)})
            for record, roots, receipt in archive_pairs:
                for role, root in [('solver', Path(record['scratch_output_root'])), *roots.items()]:
                    cleanup_exact(root, receipt['original_files'][role], output/'CLEANUP_LEDGER.jsonl',
                                  scratch_root=scratch, archive_verified=True)
            write_json(output/'CLEANUP_COMPLETE.json', {'status': 'PASS', 'run_count': len(receipts)})
    measurements = monitor.result()
    result = {'status': 'PASS', 'batch': batch_number, 'workers': workers,
              'run_count': len(all_records), 'evaluation_count': len(evaluations),
              'terminal_counts': {s: sum(r['terminal_status'] == s for r in all_records)
                                  for s in sorted({r['terminal_status'] for r in all_records})},
              'measurements': measurements,
              'run_measurements': [{'run_id': r['run_id'], 'runtime_seconds': r['runtime_seconds'],
                  'solver_seconds': r.get('solver_seconds'), 'solver_output_bytes': r['solver_output_bytes'],
                  'evaluation_seconds': {v: next(e.get('evaluation_runtime_seconds') for e in evaluations
                      if e['run_id'] == r['run_id'] and e['evaluator_version'] == v) for v in ('v3', 'v2')},
                  **{k: next(p[k] for p in receipts if p['run_id'] == r['run_id'])
                     for k in ('source_bytes', 'retained_bytes', 'retained_allocated_bytes')}} for r in all_records]}
    write_json(output/'BATCH_RESULT.json', result)
    append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'BATCH_COMPLETE', 'utc': now(), **result})
    if batch_number == 1:
        fixed = sum(p.stat().st_blocks*512 for sub in ('02_PROVIDERS', '02_SEQUENCE_PROVIDERS', '01_PROVIDER_AUDIT')
                    for p in (stage/sub).rglob('*') if p.is_file())
        peak = 1.15*(max(p['retained_allocated_bytes'] for p in receipts)*5973 +
                     measurements['filesystem_peak_growth_bytes']['scratch'] + fixed*541/max(1, len(keys)))
        passed = peak <= contract['storage']['peak_limit_bytes']
        promote = (measurements['cpu_utilization_fraction'] < .85 and measurements['memory_peak_fraction'] < .5)
        pilot = {'status': 'PASS' if passed else 'STOP_PROJECTED_PEAK',
                 'projected_peak_bytes': math.ceil(peak),
                 'projected_wall_seconds': measurements['wall_seconds']*math.ceil(5973/256),
                 'forecast_kind': 'conditional conservative planning extrapolation; not CI or measured full runtime',
                 'forecast_formula': contract['storage'].get('forecast_formula', '1.15*(max retained allocation*5973 + scratch peak + scaled fixed provider footprint)'),
                 'next_workers': 128 if promote else 64, 'measurements': measurements,
                 'sequence_consistency_gate': 'PASS', 'batch_verification': 'PASS'}
        write_json(stage/'PILOT_GATE.json', pilot)
        print('PILOT_GATE', json.dumps(pilot, ensure_ascii=False), flush=True)
        if not passed: raise RuntimeError('Pilot projected peak exceeds 250 GB; no continuation')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--operation', choices=('start', 'continue', 'provider'), default='start')
    parser.add_argument('--case-id')
    parser.add_argument('--code-commit')
    parser.add_argument('--stop-after-batch', type=int, default=1)
    args = parser.parse_args(argv)
    if args.operation == 'provider':
        provider_child(args)
        return 0
    contract, reg = load_contract(args.contract), registry(args.local_config)
    stage = resolve(contract['stage_root'], reg)
    paths = yaml.safe_load(Path(args.local_config).read_text())['paths']
    scratch = Path(paths['canonical541_v2_scratch'])
    if stage.name != STAGE_NAME or not stage.is_relative_to(reg.clean_root):
        raise ValueError('Unexpected protected stage root')
    if any(p.is_symlink() for p in (scratch, *scratch.parents)):
        raise ValueError('Scratch symlink prohibited')
    parent = next(p for p in (scratch, *scratch.parents) if p.exists())
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(parent)], text=True).strip()
    if filesystem != 'ext4': raise ValueError('Latest amendment requires WSL ext4 scratch')
    cases, runs = selection(contract, reg)
    jobs = create_jobs(contract, reg, runs, cases)
    c00 = {r['method_id']: r for r in runs if r['case_id'] == 'C00_clean_normal'}
    freeze_path = stage/'00_PREREGISTRATION/EXECUTION_FREEZE.json'
    resolution = {'mode': 'independent_hash_all', 'human_instruction': 'P-09c based on P-08 preregistered independent pre/post hash-only checkpoints'}
    if args.operation == 'start':
        freeze = verify_preregistration(Path(args.contract), reg.code_root)
        if stage.exists() or scratch.exists(): raise FileExistsError('Attempt exists; no automatic regeneration/retry')
        if shutil.disk_usage(reg.clean_root).free < 300_000_000_000:
            raise ValueError('G available below 300 GB; stop')
        if shutil.disk_usage(parent).free < 150_000_000_000:
            raise ValueError('Ext4 available below 150 GB; direct G fallback superseded')
        pinned(contract['runtime']['executable'], reg)
        pinned(contract['runtime']['model'], reg)
        pinned(contract['evaluation']['evaluator'], reg)
        pinned(contract['anchors']['C00_reference_seal'], reg)
        pinned(contract['sequence_consistency']['reference_seal'], reg)
        stage.mkdir(parents=True, exist_ok=False)
        scratch.mkdir(parents=True, exist_ok=False)
        freeze.update(source_sha256=freeze_sources(reg.code_root), started_utc=now(),
                      machine=machine_state(), scratch_root=str(scratch), **FLAGS)
        write_json(freeze_path, freeze)
        write_json(stage/'00_PREREGISTRATION/UNIQUE_JOBS.json', jobs)
        checkpoint(contract, reg, stage, 'PRE_EXECUTION', resolution)
        start = 1
    else:
        freeze = json.loads(freeze_path.read_text())
        validate_freeze(freeze, Path(args.contract), reg)
        pilot = json.loads((stage/'PILOT_GATE.json').read_text())
        if pilot['status'] != 'PASS': raise ValueError('Pilot not PASS; no continuation')
        completed = sorted((stage/'BATCHES').glob('BATCH_*/BATCH_RESULT.json'))
        start = len(completed)+1
        if any(json.loads(p.read_text())['status'] != 'PASS' for p in completed):
            raise ValueError('Prior batch not PASS')
    try:
        for number in range(start, min(args.stop_after_batch, math.ceil(len(jobs)/256))+1):
            validate_freeze(freeze, Path(args.contract), reg)
            workers = 64 if number == 1 else json.loads((stage/'PILOT_GATE.json').read_text())['next_workers']
            do_batch(number, jobs[(number-1)*256:number*256], contract, reg, stage, scratch,
                     freeze['code_commit'], args, workers, c00)
        if args.stop_after_batch >= math.ceil(len(jobs)/256):
            checkpoint(contract, reg, stage, 'POST_EXECUTION', resolution)
            write_json(stage/'EXECUTION_COMPLETE.json', {'status': 'EXECUTION_COMPLETE_PENDING_AGGREGATE',
                'run_count': 5973, 'code_commit': freeze['code_commit'], 'completed_utc': now()})
        print('VERIFIED_BATCH_BOUNDARY', min(args.stop_after_batch, math.ceil(len(jobs)/256)), flush=True)
        return 0
    except Exception as exc:
        append_json(stage/'BATCH_LEDGER.jsonl', {'event': 'STOPPED', 'utc': now(), 'exception': type(exc).__name__,
            'reason': str(exc), 'retry_count': 0, 'scene_retained': True})
        write_json(stage/'STOPPED.json', {'status': 'STOPPED_GATE_FAILURE', 'reason': str(exc),
            'retry_count': 0, 'scene_retained': True, 'utc': now()})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
