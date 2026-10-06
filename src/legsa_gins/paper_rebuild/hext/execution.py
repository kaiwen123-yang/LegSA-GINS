"""H-EXT-02 bounded execution and I/O receipts; never reads a trace payload."""
from __future__ import annotations

import csv
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

from .sequence_paths import load_sequence_paths, alias_path
from .identity_gate import METHODS, first_difference
from ..manifest import sha256_file

CONTRACT = Path('configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml')
ATTEMPT = 'H_EXT_02'


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def stage_roots():
    seq = load_sequence_paths('BY2')
    return seq, seq.hext_scratch / ATTEMPT, seq.output_root


def raw_checkpoint(seq, destination):
    """22 metadata identities; only the evaluator may hash the trace handle."""
    if sha256_file(seq.hash_lock) != seq.hash_lock_sha256:
        raise RuntimeError('HARD_STOP_RAW_LOCK_HASH')
    with seq.hash_lock.open(encoding='utf-8-sig', newline='') as handle:
        locked = list(csv.DictReader(handle))
    prefix = seq.gnss1_raw.parent.relative_to(seq.raw_root).as_posix()
    body = seq.go2_body.relative_to(seq.raw_root).as_posix()
    selected = [row for row in locked if row['relative_path'].startswith(prefix + '/')
                or row['relative_path'] in (prefix + '.bag', prefix + '.fpl', body)]
    if len(selected) != 22:
        raise RuntimeError(f'HARD_STOP_RAW_LOCK_COUNT: {seq.sequence_id} {len(selected)}')
    rows = []
    for row in selected:
        path = seq.raw_root / row['relative_path']
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('HARD_STOP_RAW_MISSING_OR_SYMLINK: ' + row['relative_path'])
        stat = path.stat()
        is_trace = path == seq.trace
        digest = None if is_trace else sha256_file(path)
        passed = stat.st_size == int(row['size_bytes']) and (digest == row['sha256'] if not is_trace else row['sha256'] == seq.trace_sha256)
        rows.append(dict(path=alias_path(path, seq), size_bytes=stat.st_size,
                         mtime_ns=stat.st_mtime_ns, expected_sha256=row['sha256'], sha256=digest,
                         verification='DEFERRED_TO_EVALUATOR_HANDLE' if is_trace else 'PAYLOAD_SHA256', passed=passed))
    payload = dict(sequence_id=seq.sequence_id, file_count=len(rows), payload_hash_count=21,
                   trace_payload_hash_count=0, trace_declared_hash_count=1,
                   passed=all(row['passed'] for row in rows), files=rows)
    write_json(destination, payload)
    if not payload['passed']:
        raise RuntimeError('HARD_STOP_RAW_FILE_HASH')
    return payload


def d4_gate(seq, contract):
    spec = contract['sequences'][seq.sequence_id]
    path = seq.output_root / '01_PROBE' / seq.sequence_id / 'PROBE.json'
    if sha256_file(path) != spec['observation_sha256']:
        raise RuntimeError('HARD_STOP_D4_PROBE_IDENTITY')
    observed = json.loads(path.read_text())
    p1, p2, expected = observed['P1'], observed['P2'], spec['expected']
    checks = {'common': p1['common_itow_count'] == expected['position_epochs'],
              'imu_samples': p2['sample_count'] == expected['imu_samples'],
              'same_itow_lists': p1['same_itow_lists']}
    for rx in p1['receivers']:
        prefix = str(rx['receiver']) + '_'
        checks.update({prefix + key: value for key, value in {
            'position': rx['hpposecef_epochs'] == expected['position_epochs'],
            'rawx': rx['rawx_epochs'] == expected['rawx_epochs'],
            'leading': rx['leading_hpposecef_without_rawx'] == expected['leading_hpposecef_without_rawx'],
            'cadence': rx['itow_interval_histogram_ms'] == {'200': expected['position_epochs'] - 1},
            'plus2': rx['constant_plus_2ms_all_rawx'] and rx['hpposecef_minus_rawx_offsets_ms'] == [2],
            'monotonic': rx['strictly_monotonic'],
            'week': rx['gps_week_set'] == [expected['gps_week']],
            'leap': rx['leap_seconds_set'] == [expected['leap_seconds']],
        }.items()})
    if not all(checks.values()):
        raise RuntimeError('HARD_STOP_D4: ' + json.dumps(checks))
    return dict(sequence_id=seq.sequence_id, passed=True, checks=checks,
                observation_sha256=sha256_file(path), basis='Frozen observation plus fresh raw payload identity; provider rechecks counts')


def archive_batch(source, destination, ledger_path, batch):
    """New destination only; retry only ENOMEM/EIO, never rerun science."""
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Archive symlink refused')
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256_file(path)
        retry = 0
        while True:
            try:
                with path.open('rb') as src, target.open('xb' if retry == 0 else 'wb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                    dst.flush()
                    os.fsync(dst.fileno())
                if sha256_file(target) != digest:
                    raise RuntimeError('HARD_STOP_ARCHIVE_HASH')
                break
            except OSError as exc:
                if exc.errno not in (errno.ENOMEM, errno.EIO) or retry >= 3:
                    raise
                retry += 1
                time.sleep(retry)
        row = dict(batch=batch, relative_path=relative.as_posix(), size_bytes=path.stat().st_size,
                   sha256=digest, retries=retry, status='VERIFIED')
        rows.append(row)
        Path(ledger_path).parent.mkdir(parents=True, exist_ok=True)
        with Path(ledger_path).open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    return dict(batch=batch, file_count=len(rows), bytes=sum(row['size_bytes'] for row in rows),
                retries=sum(row['retries'] for row in rows), failures=0, pending=0)


def preflight():
    seq, scratch, _ = stage_roots()
    out = scratch / '03_PREREG' / 'PREFLIGHT'
    out.mkdir(parents=True, exist_ok=False)
    contract = yaml.safe_load((seq.code_root / CONTRACT).read_text())
    from .probe import dependencies
    deps = dependencies(seq)
    # dependencies() reads only explicitly frozen evaluator/table/NAV/manifest.
    bad = [name for name, row in deps.items() if isinstance(row, dict) and row.get('matches') is False]
    v2 = seq.clean_root / 'stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/13_AGGREGATE_SEQUENCES/v2/UNIQUE_EVALUATION_RESULTS.csv'
    if sha256_file(v2) != '6c5a165eaf68bf762cbc803466b4496a5b522dba968785115db9d0338990044d':
        bad.append('v21_sequences_v2')
    write_json(out / 'DEPENDENCIES.json', deps)
    if bad:
        raise RuntimeError('HARD_STOP_FROZEN_IDENTITY: ' + ','.join(bad))
    gates = []
    for name in ('BY2', 'BY2H', 'BY2O'):
        current = load_sequence_paths(name)
        raw_checkpoint(current, out / (name + '_RAW_PRE.json'))
        gates.append(d4_gate(current, contract))
    write_json(out / 'D4_GATE.json', gates)
    return {'status': 'PASS_PREFLIGHT', 'D4': gates}


def identity_recheck():
    seq, scratch, _ = stage_roots()
    output_name = 'H_EXT_02_BY2_IDENTITY'
    native_root = seq.hext_scratch / output_name
    out = scratch / '03_PREREG' / 'BY2_IDENTITY_RECHECK'
    out.mkdir(parents=True, exist_ok=False)
    if native_root.exists():
        raise FileExistsError(native_root)
    target = seq.clean_root / 'stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/00_PARITY_TARGET_AND_AUDITS/A_TARGET_EXTRACTION.json'
    if sha256_file(target) != '63ad6db8a65aafb3730cdcb4342dcd0b3ba1fad88784719ba920755dca169790':
        raise RuntimeError('HARD_STOP_FROZEN_TARGET_HASH')
    targets = json.loads(target.read_text())['methods']
    env = dict(os.environ, PYTHONPATH='src', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    lines = []
    commands = [('CACHE', ['--mode', 'prepare-cache'])] + [
        (name, ['--mode', 'run', '--configuration', name, '--start-mode', 'FILE_START', '--identity-only',
                '--output-relative', output_name + '/' + method]) for name, method in METHODS.items()]
    for label, options in commands:
        log = out / (label + '_OPENAT.strace')
        command = ['strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat,execve', '-o', str(log),
                   sys.executable, 'scripts/paper_rebuild/hext02_native.py', '--sequence', 'BY2',
                   '--cache-relative', output_name + '/CACHE', *options]
        with (out / (label + '_STDOUT.log')).open('x') as handle:
            completed = subprocess.run(command, cwd=seq.code_root, env=env, stdout=handle, stderr=subprocess.STDOUT)
        lines.extend(log.read_text().splitlines())
        if completed.returncode:
            write_json(out / 'IDENTITY_FAILURE.json', dict(exit_code=completed.returncode, command_label=label))
            raise RuntimeError('HARD_STOP_IDENTITY_NATIVE_FAILURE')
    names = [load_sequence_paths(name).trace.name for name in ('BY2', 'BY2H', 'BY2O')]
    forbidden = [line for line in lines if 'openat(' in line and (any(name in line for name in names) or '.bag"' in line or '.fpl"' in line)]
    rows = {}
    for name, method in METHODS.items():
        actual = native_root / method / 'EXACT_EVALUATOR_INPUT.nav'
        expected = seq.clean_root / 'stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/POST_NATIVE_TRACE_EVALUATION' / method / 'EXACT_EVALUATOR_INPUT.nav'
        digest = sha256_file(actual)
        difference = first_difference(actual, expected) if expected.is_file() else None
        rows[name] = dict(expected_sha256=targets[name]['continuity']['evaluator_nav_sha256'],
                          actual_sha256=digest, byte_equal=None if not expected.is_file() else difference is None,
                          first_difference=difference)
    passed = not forbidden and all(row['expected_sha256'] == row['actual_sha256'] and row['byte_equal'] is not False for row in rows.values())
    receipt = dict(status='PASS_BY2_BYTE_IDENTITY' if passed else 'IDENTITY_FAILURE', methods=rows,
                   native_invocation_count=2, evaluator_invocation_count=0, trace_open_count=len(forbidden),
                   native_process_exit=completed.returncode, separate_prereg_validation_budget=True)
    write_json(out / ('IDENTITY_PASS.json' if passed else 'IDENTITY_FAILURE.json'), receipt)
    if not passed:
        raise RuntimeError('HARD_STOP_BY2_IDENTITY_MISMATCH')
    return receipt


def freeze_receipt():
    seq, scratch, archive = stage_roots()
    out = scratch / '03_PREREG'
    identity = json.loads((out / 'BY2_IDENTITY_RECHECK/IDENTITY_PASS.json').read_text())
    if identity['status'] != 'PASS_BY2_BYTE_IDENTITY':
        raise RuntimeError('BY2 prereg identity not passed')
    subject = subprocess.check_output(['git', 'log', '-1', '--format=%s'], cwd=seq.code_root, text=True).strip()
    if subject != 'prereg(hext): H-EXT-02 authorized contract and code freeze':
        raise RuntimeError('Expected preregistration commit before comparison execution')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=seq.code_root, text=True).strip()
    paths = [*sorted((seq.code_root / 'src/legsa_gins/paper_rebuild/hext').glob('*.py')),
             seq.code_root / CONTRACT, seq.code_root / 'scripts/paper_rebuild/hext02_native.py',
             seq.code_root / 'scripts/paper_rebuild/hext02_execute.py',
             seq.code_root / 'src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py',
             seq.code_root / 'src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py']
    from ..horizontal_literature.phase5_runner import AUDITED_SNAPSHOT_PATHS
    paths.extend(AUDITED_SNAPSHOT_PATHS)
    paths.extend((seq.code_root / 'scripts/paper_rebuild/clean5_evaluator_observer').glob('*.py'))
    paths.extend(seq.code_root / relative for relative in (
        'src/legsa_gins/paper_rebuild/clean5_parity/evaluation.py',
        'src/legsa_gins/paper_rebuild/clean5_parity_p04/evaluation.py',
        'src/legsa_gins/paper_rebuild/clean5_sequence/evaluation_process.py',
        'configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml',
        'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml',
        'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml'))
    hashes = {p.relative_to(seq.code_root).as_posix(): sha256_file(p) for p in paths}
    shutil.copyfile(seq.code_root / CONTRACT, out / CONTRACT.name)
    result = dict(code_freeze=commit, contract_sha256=sha256_file(seq.code_root / CONTRACT),
                  source_hashes=hashes, identity=identity, native_budget=14, evaluator_budget=28,
                  prereg_validation_native=2, scientific_code_edits_after_freeze=False)
    write_json(out / 'CODE_FREEZE.json', result)
    archive_batch(out, archive / '03_PREREG', scratch / 'ARCHIVE_LEDGER.jsonl', '03_PREREG')
    return result


def assert_freeze():
    seq, scratch, _ = stage_roots()
    freeze = json.loads((scratch / '03_PREREG/CODE_FREEZE.json').read_text())
    for relative, expected in freeze['source_hashes'].items():
        if sha256_file(seq.code_root / relative) != expected:
            raise RuntimeError('HARD_STOP_SCIENTIFIC_CODE_DRIFT: ' + relative)
    return freeze


def _journal(scratch, entry):
    with (scratch / 'EXECUTION_JOURNAL.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def _native_command(seq, scratch, label, options):
    from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
    log_root = scratch / '04_ACCESS_AUDITS'
    log_root.mkdir(exist_ok=True)
    log = log_root / (label + '.strace')
    if log.exists():
        raise RuntimeError('Native invocation already attempted; no automatic retry')
    command = ['strace', '-f', '-qq', '-yy', '-s', '4096', '-e', 'trace=openat,execve', '-o', str(log),
               sys.executable, 'scripts/paper_rebuild/hext02_native.py', '--sequence', seq.sequence_id, *options]
    env = dict(os.environ, PYTHONPATH='src', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    with (log_root / (label + '.stdout.log')).open('x') as handle:
        completed = subprocess.run(command, cwd=seq.code_root, env=env, stdout=handle, stderr=subprocess.STDOUT)
    records = audited_open_records(log, seq.code_root)
    traces = {load_sequence_paths(name).trace for name in ('BY2', 'BY2H', 'BY2O')}
    forbidden = [row for row in records if Path(row['path']) in traces or Path(row['path']).suffix.lower() in ('.bag', '.fpl')]
    scope = write_scope_audit(records, raw_root=seq.raw_root, clean_root=seq.clean_root, allowed_write_roots=[scratch])
    result = dict(exit_code=completed.returncode, passed=completed.returncode == 0 and not forbidden and scope['pass'],
                  trace_bag_fpl_open_count=len(forbidden), forbidden_opens=forbidden,
                  write_scope=scope, strace_sha256=sha256_file(log))
    write_json(log_root / (label + '.json'), result)
    if not result['passed']:
        raise RuntimeError('HARD_STOP_NATIVE_OR_ACCESS_FAILURE: ' + label)
    return result


def run_native_matrix():
    seq, scratch, archive = stage_roots()
    freeze = assert_freeze()
    contract = yaml.safe_load((seq.code_root / CONTRACT).read_text())
    records = []
    ledger = scratch / 'ARCHIVE_LEDGER.jsonl'
    for name in ('BY2', 'BY2H', 'BY2O'):
        current = load_sequence_paths(name)
        raw_checkpoint(current, scratch / 'RAW_CHECKPOINTS' / (name + '_PRE_NATIVE.json'))
        cache_relative = ATTEMPT + '/03_PROVIDER_CACHE/' + name
        _native_command(current, scratch, name + '__CACHE', ['--mode', 'prepare-cache', '--cache-relative', cache_relative])
        cache = json.loads((seq.hext_scratch / cache_relative / 'CACHE_MANIFEST.json').read_text())
        primary = 'FILE_START' if cache['first_five_seconds_static_audit']['passed'] else 'CONTRACT_START'
        scheduled = [r for r in contract['run_matrix'] if r['sequence_id'] == name]
        if primary == 'CONTRACT_START':
            scheduled = [dict(r, start_mode='CONTRACT_START', run_id=f"{name}__{r['configuration_id']}__CONTRACT_START") for r in scheduled]
            scheduled = list({r['run_id']: r for r in scheduled}.values())
        for specification in scheduled:
            assert_freeze()
            run_id = specification['run_id']
            config, start = specification['configuration_id'], specification['start_mode']
            relative = Path('04_NATIVE_RUNS') / name / config / start
            _journal(scratch, dict(event='NATIVE_LAUNCH', run_id=run_id, code_commit=freeze['code_freeze']))
            _native_command(current, scratch, run_id, ['--mode', 'run', '--cache-relative', cache_relative,
                            '--output-relative', (Path(ATTEMPT) / relative).as_posix(), '--configuration', config, '--start-mode', start])
            native_summary = json.loads((scratch / relative / 'NATIVE_SUMMARY.json').read_text())
            write_json(scratch / '05_GEOMETRIC_AUDIT' / (run_id + '.json'),
                       dict(run_id=run_id, **native_summary['geometric_audit']))
            record = {**specification, 'primary_start_mode': primary,
                      'native_root': str(archive / relative),
                      'native_summary_path': str(archive / relative / 'NATIVE_SUMMARY.json'),
                      'gap_log_path': str(archive / relative / 'GAP_EVENTS.json'), 'evaluations': {}}
            archive_batch(scratch / relative, archive / relative, ledger, run_id)
            records.append(record)
            _journal(scratch, dict(event='NATIVE_COMPLETED_ARCHIVED', run_id=run_id))
            print('NATIVE_COMPLETED', run_id, flush=True)
        raw_checkpoint(current, scratch / 'RAW_CHECKPOINTS' / (name + '_POST_NATIVE.json'))
    if len(records) > contract['budget']['native']:
        raise RuntimeError('Native budget overrun')
    write_json(scratch / 'NATIVE_EXECUTION_RECORDS.json', records)
    for name in ('03_PROVIDER_CACHE', '04_ACCESS_AUDITS', '05_GEOMETRIC_AUDIT', 'RAW_CHECKPOINTS'):
        archive_batch(scratch / name, archive / name, ledger, name)
    return records


def run_evaluation_matrix():
    from .external_evaluation import evaluate
    seq, scratch, archive = stage_roots()
    freeze = assert_freeze()
    records = json.loads((scratch / 'NATIVE_EXECUTION_RECORDS.json').read_text())
    calibrated = yaml.safe_load((seq.code_root / 'configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml').read_text())
    evaluator = Path(calibrated['evaluator']['path'].replace('<CLEAN_ROOT>', str(seq.clean_root)))
    count = 0
    for record in records:
        current = load_sequence_paths(record['sequence_id'])
        nav = Path(record['native_root']) / 'EXACT_EVALUATOR_INPUT.nav'
        native_summary = json.loads(Path(record['native_summary_path']).read_text())
        sealed_nav_sha256 = native_summary['file_hashes']['EXACT_EVALUATOR_INPUT.nav']
        for version in ('v3', 'v2'):
            assert_freeze()
            run_id = record['run_id']
            relative = Path('07_OFFLINE_EVALUATION') / version / run_id
            v3_relative = Path('06_V3_NAV_INPUTS') / run_id
            identity = dict(sequence_id=current.sequence_id, method_id=record['configuration_id'],
                            run_id=run_id, code_commit=freeze['code_freeze'], start_convention=record['start_mode'])
            _journal(scratch, dict(event='EVALUATOR_LAUNCH', run_id=run_id, version=version))
            result = evaluate(sequence=current, evaluator=evaluator, nav=nav, expected_nav_sha256=sealed_nav_sha256,
                              outdir=scratch / relative, version=version, identity=identity,
                              nav_input_root=scratch / v3_relative if version == 'v3' else None)
            count += 1
            archive_batch(scratch / relative, archive / relative, scratch / 'ARCHIVE_LEDGER.jsonl', run_id + '_' + version)
            if version == 'v3':
                archive_batch(scratch / v3_relative, archive / v3_relative, scratch / 'ARCHIVE_LEDGER.jsonl', run_id + '_V3_INPUT')
            record['evaluations'][version] = str(archive / relative / 'EVALUATION_RESULT.json')
            _journal(scratch, dict(event='EVALUATOR_COMPLETED_ARCHIVED', run_id=run_id, version=version,
                                   trace_open_count=result['audit']['trace_open_count']))
            print('EVALUATOR_COMPLETED', run_id, version, flush=True)
    write_json(scratch / 'EXECUTION_RECORDS.json', records)
    for name in ('BY2', 'BY2H', 'BY2O'):
        raw_checkpoint(load_sequence_paths(name), scratch / 'EVALUATION_RAW_CHECKPOINTS' / (name + '_POST.json'))
    archive_batch(scratch / 'EVALUATION_RAW_CHECKPOINTS', archive / 'EVALUATION_RAW_CHECKPOINTS', scratch / 'ARCHIVE_LEDGER.jsonl', 'EVAL_RAW_POST')
    return dict(native=len(records), evaluator=count, records=records)


def aggregate_results():
    from .aggregate import aggregate_stage
    from .legsa_gap_diagnostic import run_legsa_gap_diagnostic
    seq, scratch, archive = stage_roots()
    freeze = assert_freeze()
    records = json.loads((scratch / 'EXECUTION_RECORDS.json').read_text())
    ledger = dict(native_actual=len(records), evaluator_actual=sum(len(r['evaluations']) for r in records),
                  native_budget=14, evaluator_budget=28, prereg_identity_native=2, prereg_identity_evaluator=0)
    summary = aggregate_stage(sequences={n: load_sequence_paths(n) for n in ('BY2', 'BY2H', 'BY2O')},
                              records=records, output_root=scratch / '08_AGGREGATE',
                              code_commit=freeze['code_freeze'], budget_ledger=ledger)
    run_legsa_gap_diagnostic(stage_root=scratch, code_commit=freeze['code_freeze'])
    for name in ('08_AGGREGATE', '09_LEGSA_GAP_DIAGNOSTIC'):
        archive_batch(scratch / name, archive / name, scratch / 'ARCHIVE_LEDGER.jsonl', name)
    return summary


def render_results():
    from .figures import render_fig02s
    seq, scratch, archive = stage_roots()
    freeze = assert_freeze()
    result = render_fig02s(main_table=archive / '08_AGGREGATE/HORIZONTAL_TABLE_V3_THREE_SEQUENCES.csv',
                          summary_path=archive / '08_AGGREGATE/FINAL_SUMMARY.json', runtime_root=scratch,
                          publication_root=seq.clean_root / 'stages/CLEAN6_PUBLICATION_FIGURES', code_commit=freeze['code_freeze'],
                          frozen_before=json.loads((scratch / '03_PREREG/PREFLIGHT/FROZEN_FIGURES_PRE.json').read_text()))
    archive_batch(scratch / '10_FIGURES', archive / '10_FIGURES', scratch / 'ARCHIVE_LEDGER.jsonl', '10_FIGURES')
    return result
