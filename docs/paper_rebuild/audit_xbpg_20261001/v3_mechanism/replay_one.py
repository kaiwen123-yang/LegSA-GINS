#!/usr/bin/env python3
"""Bounded single-slot replay. Never imports the historical runner or Context."""
import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

HERE = Path(__file__).resolve().parent
FIELDS = ['slot_id', 'group', 'run_id', 'case_id', 'method_id', 'variant',
          'data_mode', 'synthetic_data_used', 'semisynthetic_data_used', 'status',
          'invocation_attempts', 'native_calls', 'evaluator_calls', 'started_utc', 'finished_utc', 'exit_code',
          'binary_sha256', 'config_sha256', 'output_root', 'receipt', 'reason']


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields=None):
    # Only this new derived ledger is replaced; original artifacts are read-only.
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fields or list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve(text, aliases):
    for key in sorted(aliases, key=len, reverse=True):
        if text == key or text.startswith(key + '/'):
            return Path(aliases[key] + text[len(key):])
    raise ValueError('unmapped alias: ' + text)


def alias(text, aliases):
    value = str(text)
    for key, root in sorted(aliases.items(), key=lambda x: len(x[1]), reverse=True):
        value = value.replace(root, key)
    return value


def audit_access(path, out, binary, aliases):
    records = []; violations = []; native = 0; raw = []; reference = []
    for line in path.read_text(errors='replace').splitlines():
        if 'execve(' in line and str(binary) in line and '= 0' in line:
            native += 1
        if 'openat(' not in line:
            continue
        match = re.search(r'openat\([^,]+, "((?:[^"\\]|\\.)*)", ([^)]+)\)\s+=\s+(-?\d+)', line)
        if not match or int(match[3]) < 0:
            continue
        value, flags = match[1], match[2]
        rec = {'path': alias(value, aliases), 'flags': flags}
        records.append(rec)
        if any(x in flags for x in ['O_WRONLY', 'O_RDWR', 'O_CREAT', 'O_TRUNC']):
            if not (value.startswith(str(out) + '/') or value in ['/dev/null']):
                violations.append(rec)
        elif value.startswith(aliases['<RAW_ROOT>'] + '/'):
            raw.append(rec)
        # This supplements exact input paths; do not mistake source filenames for runtime opens.
        elif re.search(r'(?i)(reference|trace[-_]?reference|\.fpl$|\.bag$)', value):
            reference.append(rec)
    return {'native_exec_count': native, 'write_outside_slot': violations,
            'raw_opens': raw, 'reference_candidate_opens': reference,
            'successful_open_records': records,
            'passed': native == 1 and not violations and not raw and not reference}


def compare_outputs(out, run, variant, aliases):
    comparisons = []
    for rec in read_csv(HERE / 'HISTORICAL_OUTPUT_HASHES.csv'):
        if rec['run_id'] != run:
            continue
        file = out / rec['filename']
        current = sha(file) if file.is_file() else ''
        baseline = rec['recorded_sha256']
        source = rec['recorded_source']
        if variant == 'observed':
            sibling = out.parent / 'original' / rec['filename']
            baseline = sha(sibling) if sibling.is_file() else ''
            source = alias(sibling, aliases)
        comparisons.append({'run_id': run, 'variant': variant, 'filename': rec['filename'],
                            'comparison_source': source, 'baseline_sha256': baseline,
                            'replay_sha256': current, 'bytes': file.stat().st_size if file.exists() else '',
                            'status': 'BYTE_IDENTICAL' if current and current == baseline else 'BYTE_MISMATCH_OR_MISSING',
                            'old_payload_read': False})
    write_csv(out / 'OUTPUT_COMPARISON.csv', comparisons)
    return comparisons


def compare_manifest(out, old, aliases):
    baseline = json.loads(old.read_text())
    current = json.loads((out / 'RUN_MANIFEST.json').read_text())
    # This explicit provenance field may differ for a new build. No counter/flag exception.
    allowed = {'source_commit'}
    rows = []
    for key in sorted(set(baseline) | set(current)):
        same = key in baseline and key in current and baseline[key] == current[key]
        rows.append({'field': key, 'baseline': alias(json.dumps(baseline.get(key), sort_keys=True), aliases),
                     'replay': alias(json.dumps(current.get(key), sort_keys=True), aliases),
                     'status': 'EXACT_EQUAL' if same else 'ALLOWED_PROVENANCE_DIFFERENCE' if key in allowed else 'MISMATCH'})
    write_csv(out / 'MANIFEST_COMPARISON.csv', rows)
    return all(x['status'] != 'MISMATCH' for x in rows)


def assert_committed(repo, paths):
    for path in paths:
        rel = str(path.relative_to(repo))
        committed = subprocess.run(['git', 'show', 'HEAD:' + rel], cwd=repo, check=True, capture_output=True).stdout
        if committed != path.read_bytes():
            raise RuntimeError('preregistration or runner differs from committed HEAD: ' + rel)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', type=Path, required=True)
    parser.add_argument('--initialize-ledger', action='store_true')
    parser.add_argument('--run-id')
    parser.add_argument('--variant', choices=['original', 'observed'])
    args = parser.parse_args()
    queue = read_csv(HERE / 'DIAGNOSTIC_QUEUE.csv')
    ledger = HERE / 'REPLAY_MANIFEST.csv'
    if args.initialize_ledger:
        if ledger.exists():
            raise RuntimeError('ledger already exists; never reset it')
        rows = []
        for item in queue:
            for variant in ['original', 'observed']:
                row = dict.fromkeys(FIELDS, '')
                row.update({k: item[k] for k in ['group', 'run_id', 'case_id', 'method_id', 'data_mode', 'synthetic_data_used', 'semisynthetic_data_used']})
                row.update(slot_id=item['run_id'] + '__' + variant, variant=variant,
                           status='PLANNED', invocation_attempts=0, native_calls=0, evaluator_calls=0,
                           output_root='<MECHANISM_ROOT>/replays/' + item['run_id'] + '/' + variant)
                rows.append(row)
        write_csv(ledger, rows, FIELDS)
        return
    if not args.run_id or not args.variant:
        parser.error('one explicit --run-id and --variant required; no batch mode')
    roots = json.loads(args.roots.read_text()); aliases = roots['aliases']
    repo = Path(aliases['<CODE_ROOT>'])
    lock = open(Path(aliases['<MECHANISM_BUILD_ROOT>']) / 'REPLAY.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # held through native exit and final ledger write
    assert_committed(repo, [HERE / name for name in ['MECHANISM_PROTOCOL.md', 'DIAGNOSTIC_QUEUE.csv',
                      'INPUT_QUALIFICATION.json', 'INPUT_USES.csv', 'QUALIFIED_INPUTS.csv',
                      'INPUT_STAT_CHECKPOINT.csv', 'HISTORICAL_OUTPUT_HASHES.csv', 'replay_one.py']])
    item = next(x for x in queue if x['run_id'] == args.run_id)
    assert item['input_status'] == 'QUALIFIED_PINNED_INPUTS'
    rows = read_csv(ledger)
    row = next(x for x in rows if x['run_id'] == args.run_id and x['variant'] == args.variant)
    if row['status'] != 'PLANNED' or sum(int(x['invocation_attempts']) for x in rows) >= 22:
        raise RuntimeError('slot already attempted or bounded queue exhausted')
    config = resolve(item['config_source'], aliases)
    if sha(config) != item['verified_config_sha256']:
        raise RuntimeError('original configuration changed')
    # Payload hashes were verified once in qualification; check identities, not a second full scan.
    qualified = {x['input_id']: x for x in read_csv(HERE / 'QUALIFIED_INPUTS.csv')}
    checkpoint = {x['input_id']: x for x in read_csv(HERE / 'INPUT_STAT_CHECKPOINT.csv')}
    for use in read_csv(HERE / 'INPUT_USES.csv'):
        if use['run_id'] == args.run_id:
            path = resolve(use['source_path'], aliases)
            if not path.is_file() or path.stat().st_size != int(qualified[use['input_id']]['bytes']):
                raise RuntimeError('qualified input missing or size changed: ' + use['source_path'])
            current = path.stat(); before = checkpoint[use['input_id']]
            if any(getattr(current, key) != int(before[key]) for key in ['st_dev', 'st_ino', 'st_mtime_ns']):
                raise RuntimeError('input metadata identity changed after checkpoint: ' + use['source_path'])
    binary = Path(aliases['<FROZEN_BINARY>' if args.variant == 'original' else '<OBSERVED_BINARY>'])
    binary_hash = sha(binary)
    if args.variant == 'original' and binary_hash != item['executable_sha256']:
        raise RuntimeError('frozen binary pin mismatch')
    if args.variant == 'observed':
        gate = json.loads((HERE / 'observer' / 'READY.json').read_text())
        assert_committed(repo, [HERE / 'observer' / 'READY.json'])
        if gate['binary_sha256'] != binary_hash or not gate['synthetic_noninterference_passed']:
            raise RuntimeError('observational binary not qualified')
        prior = next(x for x in rows if x['run_id'] == args.run_id and x['variant'] == 'original')
        if prior['status'] != 'COMPLETED_BYTE_IDENTICAL':
            raise RuntimeError('historical replay identity not established; no automatic follow-on')
    tracer = shutil.which('strace')
    if not tracer:
        raise RuntimeError('strace unavailable; no native invocation')
    expected = '<MECHANISM_ROOT>/replays/' + args.run_id + '/' + args.variant
    if row['output_root'] != expected:
        raise RuntimeError('ledger output root differs from bounded slot')
    out = resolve(expected, aliases)
    protected_root = Path(aliases['<MECHANISM_ROOT>']).resolve()
    if protected_root not in out.resolve().parents or any(p.is_symlink() for p in [out, *out.parents]):
        raise RuntimeError('output containment or symlink gate failed')
    out.mkdir(parents=True, exist_ok=False)  # exclusive reservation: never reuse an old output slot
    observer = out / 'observer'
    env = os.environ.copy(); env.pop('LEGSA_V3_OBSERVER_DIR', None)
    env.update({name: '1' for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']})
    if args.variant == 'observed':
        observer.mkdir()
        env['LEGSA_V3_OBSERVER_DIR'] = str(observer)
    argv = [str(binary), '--config', str(config), '--output-dir', str(out),
            '--debug-update-timeline', '--debug-output-dir', str(out), '--debug-max-rows', '1000000']
    trace = out / 'NATIVE_ACCESS.strace'
    command = [tracer, '-f', '-s', '4096', '-e', 'trace=openat,execve', '-o', str(trace)] + argv
    row.update(status='STARTED', invocation_attempts='1', native_calls='UNKNOWN', started_utc=now(), binary_sha256=binary_hash,
               config_sha256=item['verified_config_sha256'], receipt=row['output_root'] + '/REPLAY_RECEIPT.json')
    write_csv(ledger, rows, FIELDS)
    receipt = {'slot_id': row['slot_id'], 'data_mode': item['data_mode'],
               'synthetic_data_used': item['synthetic_data_used'] == 'True',
               'semisynthetic_data_used': item['semisynthetic_data_used'] == 'True',
               'observation_origin': 'replay_observed' if args.variant == 'observed' else 'new_frozen_binary_replay',
               'protocol_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
               'argv': [alias(x, aliases) for x in argv], 'started_utc': row['started_utc'],
               'binary_sha256': binary_hash, 'config_sha256': row['config_sha256'],
               'provider_generator_calls': 0, 'evaluator_calls': 0, 'retry_count': 0}
    (out / 'REPLAY_STARTED.json').write_text(json.dumps(receipt, indent=2) + '\n')
    try:
        with (out / 'stdout.log').open('wb') as stdout, (out / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=out, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                returncode = process.wait(timeout=1800)
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait()
                raise
        row['exit_code'] = str(returncode)
        comparisons = compare_outputs(out, args.run_id, args.variant, aliases)
        access = audit_access(trace, out, binary, aliases)
        row['native_calls'] = str(access['native_exec_count'])
        (out / 'ACCESS_REVIEW.json').write_text(json.dumps(access, indent=2) + '\n')
        old = config.parent / 'RUN_MANIFEST.json' if args.variant == 'original' else out.parent / 'original' / 'RUN_MANIFEST.json'
        manifest_match = compare_manifest(out, old, aliases) if (out / 'RUN_MANIFEST.json').exists() else False
        all_match = all(x['status'] == 'BYTE_IDENTICAL' for x in comparisons) and len(comparisons) == 5
        row['status'] = ('COMPLETED_BYTE_IDENTICAL' if all_match and access['passed'] and manifest_match else
                         'COMPLETED_REVIEW_REQUIRED') if returncode == 0 else 'NATIVE_FAILED'
        receipt.update(exit_code=returncode, output_comparisons=comparisons, scientific_manifest_match=manifest_match,
                       access_passed=access['passed'], native_exec_count=access['native_exec_count'])
        receipt['history_identity_status' if args.variant == 'original' else 'observer_identity_status'] = (
            'BYTE_IDENTICAL' if all_match else 'HISTORICAL_IDENTITY_NOT_ESTABLISHED' if args.variant == 'original'
            else 'OBSERVER_BYTE_IDENTITY_NOT_ESTABLISHED')
    except BaseException as exc:
        row.update(status='TECHNICAL_FAILURE_RETAINED', reason=type(exc).__name__ + ': ' + alias(str(exc), aliases))
        receipt['exception'] = row['reason']
        raise
    finally:
        if row['native_calls'] == 'UNKNOWN' and trace.exists():
            row['native_calls'] = str(audit_access(trace, out, binary, aliases)['native_exec_count'])
        row['finished_utc'] = now(); receipt.update(status=row['status'], finished_utc=row['finished_utc'])
        receipt['native_exec_count'] = row['native_calls']
        (out / 'REPLAY_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
        write_csv(ledger, rows, FIELDS)
        print(json.dumps({k: row[k] for k in ['slot_id', 'status', 'native_calls', 'exit_code', 'output_root']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
