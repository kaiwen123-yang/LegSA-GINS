"""P06 phase isolation, four-observation checkpoints, fifteen runs then evaluation."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import yaml

from ..clean5_sequence.registry import load_registry
from ..clean5_sequence.solver_runner import execution_state
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..clean5_parity.runtime import resolve, write_json, EXE_SHA
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .providers import (FLAGS, INPUT_KEYS, checked, verify_model, source_inputs,
                         checkpoint_inputs, generate_provider, verify_bundle, forbidden_data_path)
from .runtime import run_chain, run_order, verify_seal, seal_evaluation_artifacts

CONTRACT = 'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml'


def online_audit(records, *, registry, allowed_inputs, allowed_outputs):
    allowed = {Path(p).resolve() for p in allowed_inputs}
    roots = [Path(p).resolve() for p in allowed_outputs]
    def within(path, root):
        return path == root or root in path.parents
    forbidden, undeclared, source_metadata = [], [], []
    for record in records:
        for name in ('path', 'lexical_path'):
            path = Path(record.get(name, record['path']))
            protected = within(path, registry.raw_root) or within(path, registry.clean_root)
            # Source files whose names contain trace are code metadata. Raw or
            # clean data never receive this exception, regardless of extension.
            code_metadata = (within(path, registry.code_root) and path.suffix in ('.py', '.pyc', '.md')
                             and not protected)
            if forbidden_data_path(path):
                if code_metadata:
                    source_metadata.append(record)
                else:
                    forbidden.append(record)
            if protected and path.resolve() not in allowed and not any(within(path, r) for r in roots):
                undeclared.append(record)
    scope = write_scope_audit(records, raw_root=registry.raw_root, clean_root=registry.clean_root,
                               allowed_write_roots=roots)
    unique = lambda rows: list({(r['path'], r['flags'], r['return_code']): r for r in rows}.values())
    forbidden, undeclared, source_metadata = map(unique, (forbidden, undeclared, source_metadata))
    counts = {'trace': 0, 'bag': 0, 'fpl': 0}
    for row in forbidden:
        suffixes = [s.lower() for s in Path(row['path']).suffixes]
        counts['bag' if '.bag' in suffixes else 'fpl' if '.fpl' in suffixes else 'trace'] += 1
    return {'pass': bool(records) and not forbidden and not undeclared and scope['pass'],
            'forbidden_open_counts': counts, 'forbidden_open_records': forbidden,
            'undeclared_protected_open_records': undeclared, 'write_scope': scope,
            'code_metadata_name_only_records': source_metadata,
            'raw_trace_source_code_exception': False, 'failed_attempts_audited': True}


def phase_inputs(registry, contract, dataset, provider):
    spec = contract['sequences'][dataset]
    pins = list(spec['raw_inputs'].values())+[spec['raw_lock']]
    if provider:
        pins += [contract['model'], contract['admission'], spec['source_bundle'], spec['original_imu']]
        # This parent only reads an explicitly pinned provider manifest, not raw
        # observations or any reference. The child rechecks every used hash.
        bundle_path = checked(spec['source_bundle'], registry)
        source = json.loads(bundle_path.read_text())
        pins += list(source['variants'][spec['source_variant']]['providers'].values())
    return [resolve(pin['path'], registry) for pin in pins]


def traced_phase(args, registry, contract, stage, dataset, label, phase):
    audit_root = stage/'01_EXECUTION_AUDIT'/dataset/label
    audit_root.mkdir(parents=True, exist_ok=False)
    log = audit_root/'OPENAT.strace'
    command = [shutil.which('strace') or 'strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat,execve',
               '-o', str(log), sys.executable, '-B', str(registry.code_root/'scripts/paper_rebuild/clean5_run_calibrated_chain.py'),
               '--code-root', str(registry.code_root), '--paths-config', str(args.paths_config),
               '--executable', str(args.executable), '--code-freeze-commit', args.code_freeze_commit,
               '--_phase', phase, '--dataset', dataset, '--audit-dir', str(audit_root)]
    expected = phase_inputs(registry, contract, dataset, phase == 'provider')
    outputs = [audit_root]
    if phase == 'provider':
        outputs.append(stage/'02_CALIBRATED_PROVIDERS'/dataset)
    state = execution_state(registry.code_root, args.code_freeze_commit)
    result = run_process_group(command, cwd=registry.code_root, timeout_seconds=1800,
                                timeout_message='P06 input phase timeout', launch_failure_message='P06 input phase launch failed')
    (audit_root/'stdout.log').write_text(result.stdout)
    (audit_root/'stderr.log').write_text(result.stderr)
    audit = online_audit(audited_open_records(log, registry.code_root), registry=registry,
                         allowed_inputs=expected, allowed_outputs=outputs)
    audit.update(exit_code=result.returncode, command=command, strace_sha256=sha256_file(log),
                 outer_code_state_before=state,
                 outer_code_state_unchanged=execution_state(registry.code_root, args.code_freeze_commit) == state)
    audit['pass'] = audit['pass'] and result.returncode == 0 and audit['outer_code_state_unchanged']
    write_json(audit_root/'PHASE_AUDIT.json', audit)
    if not audit['pass']:
        raise RuntimeError(dataset+' '+label+' failed: '+result.stderr[-1600:])
    print(dataset+' '+label+': PASS; raw trace/bag/fpl opens=0', flush=True)
    return audit


def verify_frozen_model_commit(registry, contract):
    path = checked(contract['model'], registry)
    relative = path.relative_to(registry.code_root).as_posix()
    content = subprocess.run(['git', '-C', str(registry.code_root), 'show',
                              contract['model_freeze_commit']+':'+relative], check=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    if hashlib.sha256(content).hexdigest() != contract['model']['sha256']:
        raise ValueError('Model not present byte-exact at published model commit')


def recover_records(stage):
    root = Path(stage)/'03_CALIBRATED_RUNS'
    if not root.exists():
        return []
    records = [json.loads(p.read_text()) for p in root.glob('*/CALIBRATED_RUN_MANIFEST.json')]
    order = [(d, m) for d in ('BY2', 'BY2H', 'BY2O') for m in ('F01', 'F02', 'F03', 'A04', 'F04')]
    return sorted(records, key=lambda r: order.index((r['dataset_id'], r['method_id'])))


def main(argv=None):
    parser = argparse.ArgumentParser()
    for name in ('code-root', 'paths-config', 'executable'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--code-freeze-commit', required=True)
    parser.add_argument('--_phase', choices=['checkpoint', 'provider'])
    parser.add_argument('--dataset', choices=['BY2', 'BY2H', 'BY2O'])
    parser.add_argument('--audit-dir', type=Path)
    args = parser.parse_args(argv)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    registry = load_registry(args.code_root/'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',
                              args.paths_config, require_sources=False)
    registry = replace(registry, code_root=args.code_root.resolve())
    contract_path = registry.code_root/CONTRACT
    contract = yaml.safe_load(contract_path.read_text())
    run_order(contract)
    stage = resolve(contract['stage_root'], registry)
    expected_stage = registry.clean_root/'stages/CLEAN5_CALIBRATED_SENSOR_MODEL'
    if stage != expected_stage or any(p.is_symlink() for p in (stage, *stage.parents)):
        raise ValueError('Unexpected calibrated output root')
    if args._phase:
        if not args.dataset or args.audit_dir is None or stage/'01_EXECUTION_AUDIT' not in args.audit_dir.parents:
            raise ValueError('Input child requires a confined dataset/audit directory')
        # Full git status is intentionally an outer provenance operation. It
        # does not run inside the data-processing strace child.
        if args._phase == 'checkpoint':
            value = checkpoint_inputs(registry=registry, contract=contract, dataset=args.dataset)
        else:
            value = generate_provider(registry=registry, contract=contract, stage_root=stage,
                                        dataset=args.dataset, code_commit=args.code_freeze_commit)
        write_json(args.audit_dir/'CHILD_RETURN.json', value)
        return 0
    state = execution_state(registry.code_root, args.code_freeze_commit)
    if sha256_file(args.executable) != EXE_SHA:
        raise ValueError('Frozen binary mismatch')
    verify_frozen_model_commit(registry, contract)
    model = verify_model(contract, registry)
    if any((stage/name).exists() for name in ('CALIBRATED_STARTED.json', '01_EXECUTION_AUDIT',
                                             '02_CALIBRATED_PROVIDERS', '03_CALIBRATED_RUNS', '04_CALIBRATED_SEAL')):
        raise ValueError('B attempt already exists; no retry or overwrite')
    write_json(stage/'CALIBRATED_STARTED.json', {**FLAGS, 'code_commit': args.code_freeze_commit,
               'code_state': state, 'model_sha256': contract['model']['sha256'],
               'contract_sha256': sha256_file(contract_path), 'planned_runs': 15, 'planned_evaluations': 30,
               'data_mode': 'real_three_sequence_calibrated', 'retry_count': 0})
    audits, bundles, records = {}, {}, []
    try:
        for dataset in contract['dataset_order']:
            audits[dataset] = {}
            for label, phase in [('pre_generation', 'checkpoint'), ('provider_generation', 'provider'),
                                  ('post_generation', 'checkpoint')]:
                audits[dataset][label] = traced_phase(args, registry, contract, stage, dataset, label, phase)
            bundle_path = stage/'02_CALIBRATED_PROVIDERS'/dataset/'CALIBRATED_PROVIDER_BUNDLE.json'
            bundles[dataset] = json.loads(bundle_path.read_text())
            verify_bundle(bundles[dataset])
        for dataset in contract['dataset_order']:
            audits[dataset]['pre_solver'] = traced_phase(args, registry, contract, stage, dataset, 'pre_solver', 'checkpoint')
        records = run_chain(registry=registry, contract=contract, stage_root=stage, bundles=bundles,
                              model=model, executable=args.executable, code_commit=args.code_freeze_commit)
        for dataset in contract['dataset_order']:
            audits[dataset]['post_solver'] = traced_phase(args, registry, contract, stage, dataset, 'post_solver', 'checkpoint')
            verify_bundle(bundles[dataset])
        seal = verify_seal(stage, records)
        if len(records) != 15 or any(r['terminal_status'] != 'COMPLETED' for r in records):
            raise RuntimeError('Fifteen-run completion gate failed; no retry')
        from .evaluation import evaluate_chain
        evaluation = evaluate_chain(registry=registry, contract=contract, stage_root=stage,
                                      records=records, bundles=bundles, code_commit=args.code_freeze_commit)
        if evaluation['status'] != 'COMPLETED':
            raise RuntimeError('Calibrated evaluation not complete')
        verify_seal(stage, records)
        evaluation_seal = seal_evaluation_artifacts(stage, args.code_freeze_commit)
        if execution_state(registry.code_root, args.code_freeze_commit) != state:
            raise RuntimeError('Frozen execution snapshot changed')
        terminal = {**FLAGS, 'status': 'COMPLETED', 'code_commit': args.code_freeze_commit,
                    'model_sha256': contract['model']['sha256'], 'model_freeze_commit': contract['model_freeze_commit'],
                    'data_mode': 'real_three_sequence_calibrated', 'run_count': 15, 'runs': records,
                    'audits': audits, 'seal': seal, 'evaluation': evaluation,
                    'evaluation_artifact_seal': evaluation_seal, 'retry_count': 0}
        write_json(stage/'CALIBRATED_TERMINAL.json', terminal)
        print('P06 B COMPLETED 15/15 runs, 30/30 evaluations', flush=True)
        return 0
    except Exception as exc:
        records = recover_records(stage)
        try:
            from .evaluation import evaluate_failure_tables
            failure_tables = evaluate_failure_tables(registry=registry, contract=contract, stage_root=stage,
                records=records, code_commit=args.code_freeze_commit, reason=str(exc))
        except Exception as report_exc:
            failure_tables = {'status': 'FAILED_FAILURE_TABLE_GENERATION', 'error': str(report_exc)}
        write_json(stage/'CALIBRATED_FAILURE.json', {**FLAGS, 'status': 'FAILED', 'error': str(exc),
                   'runs': records, 'audits': audits, 'failure_tables': failure_tables,
                   'code_commit': args.code_freeze_commit, 'retry_count': 0})
        raise
