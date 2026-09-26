#!/usr/bin/env python3
"""HX-03 family batches with durable, no-retry reservations and audited children."""
from __future__ import annotations

import builtins
import io
import os
from pathlib import Path

# Applies to controller threads as well as the main thread. Evaluators run in
# separate interpreters; their only trace read is audited by the HX-02 launcher.
def deny_reference_open(original):
    def checked(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            name = os.fsdecode(file).lower()
            if 'trace_vrtk' in Path(name).name or name.endswith(('.bag', '.fpl')):
                raise RuntimeError('HARD_STOP_CONTROLLER_REFERENCE_OPEN_ATTEMPT: ' + name)
        return original(file, *args, **kwargs)
    return checked
builtins.open = deny_reference_open(builtins.open)
io.open = deny_reference_open(io.open)

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import replace
from datetime import datetime, timezone
import gzip
import hashlib
import json
import shutil
import signal
import subprocess
import sys
import threading
import time

import numpy as np
import yaml

from legsa_gins.paper_rebuild.hext import external_evaluation as ext
from legsa_gins.paper_rebuild.hext import hx02_evaluation_process as launcher
from legsa_gins.paper_rebuild.hext.hx03_injection import materialize, sha, write_json, resolve, IGNORED
from legsa_gins.paper_rebuild.hext.sequence_paths import load_sequence_paths
from legsa_gins.paper_rebuild.clean5_sequence.io_audit import audited_open_records, write_scope_audit
from legsa_gins.paper_rebuild.canonical541 import offline_eval_aggregate as canonical


class HardStop(RuntimeError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


class Controller:
    def __init__(self, W):
        self.W = W
        local = yaml.safe_load((W / 'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
        self.stages = Path(local['clean_root']) / 'stages'
        self.stage = self.stages / 'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'
        self.scratch = Path(local['hx02_scratch']) / 'HX03'
        self.control = self.stage / '00_CONTROL'
        self.config = W / 'configs/paper_rebuild/hext/HX03'
        self.contract = json.loads((self.config / 'CONTRACT.json').read_text())
        self.cases = json.loads((self.config / 'CASES.json').read_text())
        import csv
        with (self.config / 'RUN_MANIFEST.csv').open() as f:
            self.runs = list(csv.DictReader(f))
        self.roots = {'W': W, 'STAGES': self.stages, 'V3': self.stages / 'CLEAN8_PROTOCOL_V3',
                      'HX03': self.stage, 'SCRATCH': Path(local['hx02_scratch'])}
        self.seq = replace(load_sequence_paths('BY2'), hext_scratch=self.scratch, output_root=self.stage)
        self.base_cache = resolve(self.contract['base_cache']['path'], self.roots).parent
        self.parameters = resolve(self.contract['parameters']['path'], self.roots)
        self.evaluator = resolve(self.contract['evaluator'], self.roots)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.processes = {}
        self.events = []
        self.ledger_path = self.control / 'LEDGER.jsonl'
        if self.ledger_path.exists():
            self.events = [json.loads(line) for line in self.ledger_path.read_text().splitlines()]
        self.scratch.mkdir(parents=True, exist_ok=True)
        launcher.REGISTERED_CHILDREN['HX03_FROZEN'] = 'legsa_gins.paper_rebuild.hext.hx03_evaluation'

    def event(self, event, **data):
        with self.lock:
            if event == 'NATIVE_RESERVED' and self.counts()['external_native'] >= self.contract['maximum_total_native']:
                raise HardStop('NATIVE_BUDGET_EXHAUSTED')
            if event == 'EVALUATOR_RESERVED' and self.counts()['external_evaluation'] >= self.contract['maximum_total_evaluation']:
                raise HardStop('EVALUATOR_BUDGET_EXHAUSTED')
            row = {'utc': utc(), 'event': event, **data}
            with self.ledger_path.open('a') as f:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n'); f.flush(); os.fsync(f.fileno())
            self.events.append(row)

    def counts(self):
        with self.lock:
            return {'legsa_native': 0, 'legsa_evaluation': 0,
                'external_native': sum(e['event'] == 'NATIVE_RESERVED' for e in self.events),
                'external_evaluation': sum(e['event'] == 'EVALUATOR_RESERVED' for e in self.events),
                'archived_runs': sum(e['event'] == 'ARCHIVED' for e in self.events),
                'native_retries': 0, 'evaluator_retries': 0}

    def progress(self, status, family=None):
        row = {'utc': utc(), 'status': status, 'family': family, **self.counts(), 'active_native_pids': list(self.processes)}
        for name, text in [('STATE.json', json.dumps(row, ensure_ascii=False, indent=2) + '\n'),
                           ('PROGRESS.txt', json.dumps(row, ensure_ascii=False) + '\n')]:
            (self.control / name).write_text(text)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    def guard(self):
        avail = {}
        for path, minimum in [('/mnt/e', 40_000_000_000), ('/mnt/g', 30_000_000_000)]:
            avail[path] = int(subprocess.check_output(['df', '-B1', '--output=avail', path], text=True).splitlines()[-1])
            if avail[path] < minimum:
                raise HardStop('DF_GUARD: ' + path)
        size = sum(p.stat().st_size for p in self.scratch.rglob('*') if p.is_file())
        if size > 20_000_000_000:
            raise HardStop('SCRATCH_LIMIT')
        self.event('DISK_GUARD', available_bytes=avail, scratch_bytes=size)

    def verify_freeze(self):
        for rel, expected in json.loads((self.config / 'CODE_PINS.json').read_text()).items():
            if sha(self.W / rel) != expected:
                raise HardStop('CODE_FREEZE: ' + rel)
        receipt = json.loads((self.control / 'CODE_FREEZE.json').read_text())
        result = subprocess.run(['git', 'merge-base', '--is-ancestor', receipt['commit'], 'HEAD'], cwd=self.W)
        if result.returncode:
            raise HardStop('CODE_FREEZE_NOT_ANCESTOR')
        for item in (self.contract['base_cache'], self.contract['parameters']):
            if sha(resolve(item['path'], self.roots)) != item['sha256']:
                raise HardStop('BASE_CACHE_OR_PARAMETERS_CHANGED')

    def source_result(self, run_id):
        p = self.stage / 'RUNS' / run_id / 'RESULT.json'
        if not p.exists():
            p = self.scratch / 'RUNS' / run_id / 'RESULT.json'
        return json.loads(p.read_text())

    def identity_id(self, method):
        return f'BY2__{method}__LIT__C00__NA'

    def completed(self, run):
        return any(e['event'] == 'ARCHIVED' and e['run_id'] == run['run_id'] for e in self.events)

    def alias_source(self, run):
        execution = run['execution']
        if execution == 'REUSE_C00_AFTER_TYPE_HASH_GATE':
            confirm = next(r for r in self.runs if r['type'] == run['type'] and r['method'] == run['method'] and r['seed'] == 'seed_00')
            a = self.source_result(confirm['run_id'])
            base = self.source_result(self.identity_id(run['method']))
            if a['source_nav_sha256'] != base['source_nav_sha256']:
                raise HardStop('C00_EQUIVALENT_TYPE_HASH: ' + confirm['run_id'])
            return confirm['run_id'], '输入与 C00 相同（哈希核实）'
        if execution.startswith('REUSE_D03_IF'):
            d03 = f"BY2__{run['method']}__LIT__D03_seed_00__seed_00"
            d05 = f"BY2__{run['method']}__LIT__D05_seed_00__seed_00"
            a, b = self.source_result(d03), self.source_result(d05)
            if a['source_nav_sha256'] == b['source_nav_sha256'] and a['source_nav_sha256']:
                return f"BY2__{run['method']}__LIT__D03_{run['seed']}__{run['seed']}", 'D05 与 D03 映射相同；seed_00 NAV 哈希一致后复用同种子 D03'
        return None

    def evaluate(self, run, rd, native_result):
        nav = rd / 'native/EXACT_EVALUATOR_INPUT.nav'
        if not nav.is_file():
            return {}
        failure = native_result.get('failure')
        if failure and failure['failure_class'] != 'ALGORITHM_FAILURE_DIVERGED':
            return {}
        results = {}
        for version in ('v3', 'v2'):
            if self.stop.is_set():
                raise HardStop('CANCELLED_AFTER_HARD_STOP')
            transform_dir = rd / 'eval' / (version + '_NAV_INPUT')
            actual, original, transform = ext.prepare_evaluator_nav(sequence=self.seq, nav=nav, outdir=transform_dir, version=version)
            self.event('EVALUATOR_RESERVED', run_id=run['run_id'], version=version, role='PRE_FAILURE' if failure else 'FULL')
            spec = {'evaluator': str(self.evaluator), 'trace': str(self.seq.trace), 'trace_sha256': self.seq.trace_sha256,
                    'nav': str(actual), 'base_time': self.seq.base_time, 'window': list(self.seq.window)}
            child = launcher.run_child('HX03_FROZEN', spec, workdir=rd / 'eval' / version,
                code_root=self.W, raw_root=self.seq.raw_root, clean_root=self.seq.clean_root,
                trace=self.seq.trace, timeout_seconds=600)
            out = Path(child['outdir'])
            capture = json.loads((out / 'EVALUATOR_CAPTURE.json').read_text())
            failures = ext._capture_identity_failures(capture, self.seq, child['audit']['trace_open_records'])
            if failures:
                raise HardStop('; '.join(failures))
            identity = {'method_id': run['method'], 'case_id': run['case_id'],
                        'evaluator_contract': 'evaluator_contract_' + version, 'sequence_id': 'BY2',
                        'source_nav_sha256': sha(nav), 'evaluator_nav_sha256': sha(actual),
                        'status': 'PRE_FAILURE' if failure else 'COMPLETED'}
            if not capture['consistency']['passed']:
                row = {**identity, 'status': 'UNAVAILABLE_EVALUATION_FAILED', 'metrics_admitted': False,
                       'reason': 'D12 bounded NAV; frozen consistency observation failed; no retry'}
            else:
                errors = canonical._read_error_series(out)
                row = ext.metrics(errors, original, identity, window=self.seq.window,
                                  reference_count=capture.get('reference_epoch_count'))
            results[version] = row
            write_json(rd / 'eval' / version / 'EVALUATION_RESULT.json', {'row': row, 'transform': transform,
                'capture': capture, 'audit': child['audit']})
            self.event('EVALUATOR_COMPLETED', run_id=run['run_id'], version=version,
                       trace_open_count=child['audit']['trace_open_count'], trace_sha256=capture['trace_sha256'])
        return results

    def audit_native(self, rd):
        log = rd / 'NATIVE_OPENAT.strace'
        records = audited_open_records(log, self.W) if log.is_file() else []
        forbidden = [r for r in records if 'trace_vrtk' in Path(r['path']).name or r['path'].endswith(('.bag', '.fpl'))]
        scope = write_scope_audit(records, raw_root=self.seq.raw_root, clean_root=self.seq.clean_root, allowed_write_roots=[rd])
        result = {'passed': not forbidden and scope['pass'], 'reference_opens': len(forbidden),
                  'forbidden': forbidden, 'write_scope': scope, 'strace_sha256': sha(log) if log.is_file() else None}
        write_json(rd / 'NATIVE_AUDIT.json', result)
        if not result['passed']:
            raise HardStop('NATIVE_ACCESS_AUDIT: ' + rd.name)
        return result

    def one(self, run):
        if self.completed(run):
            return self.source_result(run['run_id'])
        rd = self.scratch / 'RUNS' / run['run_id']
        if (rd / 'RESULT.json').is_file():
            return json.loads((rd / 'RESULT.json').read_text())
        if any(e['event'] == 'NATIVE_RESERVED' and e['run_id'] == run['run_id'] for e in self.events):
            raise HardStop('INCOMPLETE_RESERVED_RUN_NO_RETRY: ' + run['run_id'])
        if rd.exists():
            # An interrupted reservation is terminal; never rerun its solve or
            # evaluator. Preserve files for explicit follow-up audit.
            raise HardStop('INCOMPLETE_RESERVED_RUN_REQUIRES_TERMINAL_AUDIT: ' + run['run_id'])
        if self.stop.is_set():
            raise HardStop('CANCELLED_AFTER_HARD_STOP')
        alias = self.alias_source(run)
        rd.mkdir(parents=True)
        spec = self.cases[run['case_id']]
        if alias:
            source_id, note = alias
            source = self.source_result(source_id)
            write_json(rd / 'COMMAND.json', {'invoked': False, 'reuse_source_run_id': source_id})
            write_json(rd / 'PARAMS_ECHO.json', {'config': 'LIT', 'source_run_id': source_id})
            write_json(rd / 'INPUT_HASHES.json', {'injection_spec_sha256': hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(), 'sources': spec['sources']})
            write_json(rd / 'native/ALIAS.json', {'source_run_id': source_id, 'source_nav_sha256': source['source_nav_sha256']})
            write_json(rd / 'eval/ALIAS.json', {'source_run_id': source_id})
            result = {**source, **run, 'input_identity_note': note, 'reused': True,
                      'reuse_source_run_id': source_id, 'source_run_dir': '$HX03/RUNS/' + source_id}
        else:
            inputs = materialize(self.base_cache, rd / 'CACHE', spec, run['method'], self.roots)
            write_json(rd / 'INPUT_HASHES.json', {**inputs, 'sources': spec['sources']})
            params = yaml.safe_load(self.parameters.read_text())
            write_json(rd / 'PARAMS_ECHO.json', {'config': 'LIT', 'parameter_source_sha256': sha(self.parameters),
                'noise': params['process_noise_psd_paper_experiment'], 'initial_std': {'attitude_deg': 60, 'velocity_mps': .1, 'position_m': .1},
                'accel_scale': 1, 'method_label': '改动过的 LC01' if run['method'] == 'LC01-BR' else run['method']})
            argv = [sys.executable, '-m', 'legsa_gins.paper_rebuild.hext.hx03_native', '--cache', str(rd / 'CACHE'),
                    '--output', str(rd / 'native'), '--method', run['method'], '--parameters', str(self.parameters), '--trace-mode', 'disabled']
            command = ['strace', '-f', '-yy', '-s', '4096', '-e', 'trace=openat,execve', '-o', str(rd / 'NATIVE_OPENAT.strace'), *argv]
            environment_whitelist = launcher.child_environment(self.W, rd / 'native')
            assert all(environment_whitelist[key] == '1' for key in
                       ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'))
            write_json(rd / 'COMMAND.json', {'argv': command, 'cwd': '$W', 'trace_mode': 'disabled',
                'environment_whitelist': environment_whitelist, 'native_wait_limit_s': 600})
            self.event('NATIVE_RESERVED', run_id=run['run_id'])
            environment = {**os.environ, **environment_whitelist}
            with (rd / 'native_stdout.log').open('x') as stdout, (rd / 'native_stderr.log').open('x') as stderr:
                started = time.monotonic()
                proc = subprocess.Popen(command, cwd=self.W, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
                with self.lock:
                    self.processes[proc.pid] = proc
                self.event('NATIVE_PID', run_id=run['run_id'], pid=proc.pid)
                try:
                    rc = proc.wait(timeout=600)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try: proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL); proc.wait()
                    rc = 124
                finally:
                    with self.lock:
                        self.processes.pop(proc.pid, None)
            timing = {'wall_seconds': time.monotonic() - started, 'returncode': rc,
                      'native_wait_limit_s': 600, 'clock': 'time.monotonic; Popen through wait'}
            write_json(rd / 'NATIVE_TIMING.json', timing)
            self.event('NATIVE_COMPLETED', run_id=run['run_id'], **timing)
            self.audit_native(rd)
            p = rd / 'native/NATIVE_RESULT.json'
            native = json.loads(p.read_text()) if p.is_file() else {'status': 'FAILED', 'failure': {
                'failure_class': 'RUN_FAILED_ENVIRONMENT' if rc == 124 else ('ABNORMAL_EXIT' if rc else 'NO_OUTPUT'),
                'message': 'native result absent; complete stderr retained'}}
            native['returncode'] = rc
            nav = rd / 'native/EXACT_EVALUATOR_INPUT.nav'
            if run['case_id'] == 'C00':
                expected = self.contract['identity']['LC01' if run['method'] == 'LC01-BR' else run['method']]['source_nav_sha256']
                if not nav.is_file() or sha(nav) != expected:
                    write_json(rd / 'HASH_GATE_FAILURE.json', {'expected': expected, 'observed': sha(nav) if nav.is_file() else None})
                    raise HardStop('IDENTITY_NATIVE_HASH_FAILED: ' + run['run_id'])
            if run['type'] in IGNORED:
                expected = self.contract['identity'][run['method']]
                if not nav.is_file() or sha(nav) != expected['source_nav_sha256']:
                    raise HardStop('C00_EQUIVALENT_TYPE_HASH: ' + run['run_id'])
                base = self.source_result(self.identity_id(run['method']))
                evaluations = json.loads(json.dumps(base['evaluations']))
                evaluations['v3'].update(yaw_rmse_deg=float(expected['yaw_rmse_deg']),
                    horizontal_rmse_m=float(expected['h_rmse_m']), up_rmse_m=float(expected['up_rmse_m']),
                    yaw_p95_absolute_deg=float(expected['yaw_p95_absolute_deg']))
                write_json(rd / 'eval/ALIAS.json', {'source': '$V3/07_AGGREGATE/MAIN_TABLE_V3.csv',
                    'v3_source_line': 17 if run['method'] == 'LC01' else 18,
                    'v2_source_run': self.identity_id(run['method'])})
            else:
                evaluations = self.evaluate(run, rd, native) if run['method'] != 'LC01-BR' or run['case_id'] != 'C00' else {}
            nav = rd / 'native/EXACT_EVALUATOR_INPUT.nav'
            failure = native.get('failure')
            result = {**run, 'source_run_dir': '$HX03/RUNS/' + run['run_id'], 'reused': False,
                      'native': native, 'evaluations': evaluations,
                      'failure_class': failure['failure_class'] if failure else 'NONE',
                      'source_nav_sha256': sha(nav) if nav.is_file() else None, 'input_identity_note': ''}
            if run['method'] == 'LC01-BR':
                result['input_identity_note'] = '改动过的 LC01；仅 A2 补充行；故障窗仅相对量测更新'
            if run['type'] == 'D62' and run['method'] == 'LC01':
                result['input_identity_note'] = '窗内两台无效；与同种子同时长 A1 输入相同，另列 A1 等价行'
            if run['type'] == 'D31':
                result['input_identity_note'] = 'LC01 一台无效跳过整次更新；EXT05C 更新不读取 p2'
            if run['type'] == 'D57':
                result['input_identity_note'] = '仅两台位置历元移动；v3 LegSA 有效航向为 0，暴露不同'
            if run['type'] in IGNORED or (run['type'] == 'D31' and run['method'] == 'EXT05C'):
                expected = self.contract['identity'][run['method']]['source_nav_sha256']
                if result['source_nav_sha256'] != expected:
                    write_json(rd / 'HASH_GATE_FAILURE.json', {'expected': expected, 'observed': result['source_nav_sha256']})
                    raise HardStop('C00_EQUIVALENT_TYPE_HASH: ' + run['run_id'])
                result['input_identity_note'] = '输入与 C00 相同（哈希核实）' if run['type'] in IGNORED else 'p2 无效不影响 EXT05C 更新；NAV 与 C00 哈希一致'
        write_json(rd / 'RESULT.json', result)
        write_json(rd / ('DONE.json' if result['failure_class'] == 'NONE' else 'FAILURE.json'),
                   {'status': result['failure_class'], 'source': 'RESULT.json', 'stderr': 'native_stderr.log'})
        self.event('RUN_TERMINAL', run_id=run['run_id'], failure_class=result['failure_class'], reused=result['reused'])
        return result

    def archive(self, run):
        if self.completed(run):
            return
        source = self.scratch / 'RUNS' / run['run_id']
        destination = self.stage / 'RUNS' / run['run_id']
        hashes = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob('*')) if p.is_file() and p.name != 'OUTPUT_HASHES.json'}
        hash_path = source / 'OUTPUT_HASHES.json'
        if not hash_path.exists():
            write_json(hash_path, hashes)
        hashes['OUTPUT_HASHES.json'] = sha(hash_path)
        destination.mkdir(parents=True, exist_ok=True)
        for rel, digest in hashes.items():
            src, dst = source / rel, destination / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if sha(dst) != digest:
                    raise HardStop('ARCHIVE_EXISTING_HASH: ' + str(dst))
                continue
            with src.open('rb') as inp, dst.open('xb') as out:
                shutil.copyfileobj(inp, out, 1 << 20); out.flush(); os.fsync(out.fileno())
            if sha(dst) != digest:
                raise HardStop('ARCHIVE_COPY_HASH: ' + str(dst))
        self.event('ARCHIVED', run_id=run['run_id'], file_count=len(hashes), bytes=sum((destination / p).stat().st_size for p in hashes), output_hashes_sha256=hashes['OUTPUT_HASHES.json'])
        shutil.rmtree(source)
        self.event('SCRATCH_RELEASED', run_id=run['run_id'])

    def batch(self, family, runs):
        self.guard(); self.verify_freeze(); self.progress('RUNNING', family)
        pending_runs = [r for r in runs if not self.completed(r)]
        try:
            with ThreadPoolExecutor(max_workers=22) as executor:
                pending = {executor.submit(self.one, r): r for r in pending_runs}
                while pending:
                    done, _ = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
                    for future in done:
                        try:
                            future.result()
                        except BaseException:
                            self.stop.set()
                            with self.lock:
                                for pid in list(self.processes):
                                    try: os.killpg(pid, signal.SIGTERM)
                                    except ProcessLookupError: pass
                            for other in pending:
                                other.cancel()
                            raise
                        pending.pop(future)
                    self.progress('RUNNING', family)
                    if done:
                        self.guard()
        except BaseException:
            self.stop.set()
            with self.lock:
                for pid in list(self.processes):
                    try: os.killpg(pid, signal.SIGTERM)
                    except ProcessLookupError: pass
            raise
        self.progress('ARCHIVING', family)
        for r in runs:
            self.archive(r)
        self.event('FAMILY_COMPLETE', family=family)

    def identity_gate(self):
        result = {}
        for method in ('LC01', 'EXT05C'):
            row = self.source_result(self.identity_id(method))
            expected = self.contract['identity'][method]
            yaw = row.get('evaluations', {}).get('v3', {}).get('yaw_rmse_deg')
            digits = 9 if method == 'LC01' else 6
            passed = (row['source_nav_sha256'] == expected['source_nav_sha256'] and yaw is not None
                      and round(float(yaw), digits) == round(float(expected['yaw_rmse_deg']), digits))
            result[method] = {'passed': passed, 'expected': expected, 'observed_nav': row['source_nav_sha256'], 'observed_yaw': yaw}
        br = self.source_result(self.identity_id('LC01-BR'))
        result['LC01-BR_no_fault'] = {'passed': br['source_nav_sha256'] == self.contract['identity']['LC01']['source_nav_sha256'], 'observed_nav': br['source_nav_sha256']}
        path = self.control / 'IDENTITY_GATE.json'
        if not path.exists():
            write_json(path, result)
        if not all(row['passed'] for row in result.values()):
            raise HardStop('IDENTITY_GATE_FAILED')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--identity-only', action='store_true')
    args = parser.parse_args()
    c = Controller(Path.cwd())
    try:
        c.verify_freeze()
        identities = [r for r in c.runs if r['case_id'] == 'C00']
        c.batch('身份门', identities)
        c.identity_gate()
        if args.identity_only:
            c.progress('PASS_IDENTITY_GATE'); return
        families = list(dict.fromkeys(r['family'] for r in c.runs if r['case_id'] != 'C00'))
        for family in families:
            runs = [r for r in c.runs if r['family'] == family]
            # Seed-00 confirmations precede dependent reuse rows; D03 family
            # precedes D05 in the frozen family order.
            for label, group in [('native_and_confirmations', [r for r in runs if not r['execution'].startswith('REUSE')]),
                                 ('conditional_and_aliases', [r for r in runs if r['execution'].startswith('REUSE')])]:
                if group:
                    c.batch(family + ':' + label, group)
        c.progress('PASS_MATRIX_COMPLETE')
        write_json(c.control / 'EXECUTION_COUNTS.json', c.counts())
    except BaseException as exc:
        import traceback
        traceback.print_exc()
        c.event('HARD_STOP', error=type(exc).__name__, message=str(exc))
        c.progress('HARD_STOP')
        path = c.control / 'HARD_STOP.json'
        if not path.exists():
            write_json(path, {'utc': utc(), 'error': type(exc).__name__, 'message': str(exc), **c.counts()})
        raise


if __name__ == '__main__':
    main()
