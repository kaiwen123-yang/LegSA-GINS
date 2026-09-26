"""Lossless retention, verified archive copies and exact-file batch cleanup."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import threading
import tempfile
import time

from ..clean5_degradation.common import write_json
from ..manifest import sha256_file
from .resources import process_tree_rss
from .archive_io import ArchiveRetryPending, BLOCK_BYTES, RETRY_DELAYS, RETRY_ERRNOS, retry_io, stream_copy

FULL_NUMERICAL = frozenset(('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt',
    'LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv', 'EVAL_NAV.csv', 'EVAL_NAV_V3.nav'))


def append_json(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps(row, allow_nan=False, ensure_ascii=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def inventory(root):
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in exact-file inventory')
        if path.is_file():
            files[path.relative_to(root).as_posix()] = {
                'size_bytes': path.stat().st_size, 'allocated_bytes': path.stat().st_blocks*512,
                'sha256': sha256_file(path)}
    return files


def gzip_copy(source, destination):
    source_hash = hashlib.sha256()
    with Path(source).open('rb', buffering=BLOCK_BYTES) as reader, Path(destination).open('xb', buffering=BLOCK_BYTES) as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='', compresslevel=3) as writer:
            for block in iter(lambda: reader.read(BLOCK_BYTES), b''):
                writer.write(block)
                source_hash.update(block)
    return source_hash.hexdigest()


def thin_nav(source, destination):
    """First observed row in each absolute 100 ms bin; never interpolate NAV."""
    count = 0
    previous_bin = None
    with Path(source).open() as stream, Path(destination).open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0, compresslevel=3) as target:
            target.write(b'gps_week,time_s,latitude_deg,longitude_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg\n')
            for line in stream:
                if not line.strip() or line.lstrip().startswith(('#', '%')):
                    continue
                fields = line.split()
                if len(fields) != 11:
                    raise ValueError('Expected frozen 11-column native NAV')
                if not all(math.isfinite(float(v)) for v in fields):
                    raise ValueError('Nonfinite NAV during thinning')
                bucket = math.floor(float(fields[1])*10+1e-9)
                if bucket == previous_bin:
                    continue
                if previous_bin is not None and bucket < previous_bin:
                    raise ValueError('NAV time reversed')
                target.write((','.join(fields)+'\n').encode())
                previous_bin = bucket
                count += 1
    return count


def _prepare_retained_run(record, evaluation_roots, destination, *, archive_code_commit, io_timings):
    """Prepare compressed retained members on scratch only; no source deletion."""
    source = Path(record['output_root'])
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    retained = {}
    validation_files = {}
    skipped = []
    sources = [('solver', source)] + [(version, Path(root)) for version, root in evaluation_roots.items()]
    original_files = {}
    posthoc_metadata = {key: record[key] for key in ('posthoc_evaluation_seal',) if key in record}
    def hash_file(path):
        started, cpu_started = time.monotonic(), time.thread_time()
        result = sha256_file(path)
        io_timings['hash_wall_seconds'] += time.monotonic()-started
        io_timings['hash_cpu_seconds'] += time.thread_time()-cpu_started
        return result
    for role, root in sources:
        hash_start, hash_cpu = time.monotonic(), time.thread_time()
        originals = inventory(root)
        io_timings['hash_wall_seconds'] += time.monotonic()-hash_start
        io_timings['hash_cpu_seconds'] += time.thread_time()-hash_cpu
        original_files[role] = originals
        target_root = destination/role
        target_root.mkdir()
        for relative, pin in originals.items():
            path = root/relative
            if path.name in FULL_NUMERICAL or path.name == 'error_series.csv':
                skipped.append({'role': role, 'relative_path': relative, **pin,
                                'reason': 'full_numerical_sealed_then_reduced_or_losslessly_compressed'})
                continue
            # Machine manifests stay directly readable; large timelines/logs are lossless.
            compress = path.suffix not in ('.json', '.yaml', '.yml', '.gz')
            out_relative = relative + ('.gz' if compress else '')
            output = target_root/out_relative
            output.parent.mkdir(parents=True, exist_ok=True)
            if compress:
                compress_start, compress_cpu = time.monotonic(), time.thread_time()
                digest = gzip_copy(path, output)
                io_timings['compress_wall_seconds'] += time.monotonic()-compress_start
                io_timings['compress_cpu_seconds'] += time.thread_time()-compress_cpu
                if digest != pin['sha256']:
                    raise ValueError('Scratch gzip source hash mismatch')
            else:
                with path.open('rb') as reader, output.open('xb') as writer:
                    shutil.copyfileobj(reader, writer, BLOCK_BYTES)
            output_hash = hash_file(output)
            if not compress and output_hash != pin['sha256']:
                raise ValueError('Scratch copy hash mismatch')
            retained[f'{role}/{out_relative}'] = {'sha256': output_hash,
                'size_bytes': output.stat().st_size, 'allocated_bytes': output.stat().st_blocks*512,
                'source_sha256': pin['sha256'], 'compression': 'gzip' if compress else 'identity'}
    # Post-hoc validation sidecars have their own code/config identity. They
    # remain outside original_files, which is the scratch cleanup inventory.
    for label, path_key, hash_keys, filename in (
        ('record', 'validation_record_path', ('validation_record_sha256',), 'VALIDATION_RECORD.json'),
        ('config', 'validation_config_path', ('validation_config_hash', 'validation_config_sha256'), 'VALIDATION_CONFIG.yaml')):
        if not record.get(path_key):
            continue
        path = Path(record[path_key])
        hashes = [record[key] for key in hash_keys if record.get(key)]
        if not hashes or len(set(hashes)) != 1:
            raise ValueError('Missing or contradictory validation sidecar hash: '+label)
        expected = hashes[0]
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)) or hash_file(path) != expected:
            raise ValueError('Validation sidecar differs from sealed identity: '+label)
        output = destination/'validation'/filename
        output.parent.mkdir(exist_ok=True)
        with path.open('rb') as reader, output.open('xb') as writer:
            shutil.copyfileobj(reader, writer, BLOCK_BYTES)
        if hash_file(output) != expected:
            raise ValueError('Archived validation sidecar differs: '+label)
        relative = 'validation/'+filename
        retained[relative] = {'sha256': expected, 'size_bytes': output.stat().st_size,
            'allocated_bytes': output.stat().st_blocks*512, 'source_sha256': expected,
            'compression': 'identity', 'source_role': 'posthoc_validation_not_native_output'}
        validation_files[label] = {'source_path': str(path), 'sha256': expected,
                                   'archive_relative_path': relative, 'original_retained': True}
    if record['terminal_status'] == 'COMPLETED':
        nav = destination/'solver/NAV_10HZ.csv.gz'
        compress_start, compress_cpu = time.monotonic(), time.thread_time()
        rows = thin_nav(source/'KF_GINS_Navresult.nav', nav)
        io_timings['compress_wall_seconds'] += time.monotonic()-compress_start
        io_timings['compress_cpu_seconds'] += time.thread_time()-compress_cpu
        retained['solver/NAV_10HZ.csv.gz'] = {'sha256': hash_file(nav), 'size_bytes': nav.stat().st_size,
            'allocated_bytes': nav.stat().st_blocks*512, 'rows': rows,
            'policy': 'first native row per floor(time_s*10) bin; original tokens; no interpolation'}
        required = ('solver/RUN_MANIFEST.json', 'solver/PORT_GNSS_UPDATE_TRACE.csv.gz',
                    'solver/OUTPUT_SEAL.json', 'solver/NAV_10HZ.csv.gz')
        for rel in required:
            if rel not in retained:
                raise ValueError('Required retained solver member missing: '+rel)
        for version in ('v3', 'v2'):
            if not any(k.startswith(version+'/') and k.endswith('/summary.json') for k in retained):
                raise ValueError('Required summary missing: '+version)
            if not any(k.startswith(version+'/') and k.endswith('/error_series.csv.gz') for k in retained):
                raise ValueError('Required compressed errors missing: '+version)
    receipt = {'status': 'ARCHIVE_VERIFIED', 'run_id': record['run_id'], 'dataset_id': record['dataset_id'],
               **posthoc_metadata,
               'terminal_status': record['terminal_status'], 'original_files': original_files,
               'retained_files': retained, 'sealed_not_retained_full_files': skipped,
               'retained_bytes': sum(p['size_bytes'] for p in retained.values()),
               'retained_allocated_bytes': sum(p['allocated_bytes'] for p in retained.values()),
               'source_bytes': sum(p['size_bytes'] for entries in original_files.values() for p in entries.values())}
    if validation_files:
        receipt['validation_files'] = validation_files
    unavailable = []
    if record['terminal_status'] != 'COMPLETED':
        unavailable = [{'role': role, 'status': 'UNAVAILABLE',
                        'reason': 'NATIVE_WRITEALL_NOT_REACHED; evaluator not invoked; no fabricated data'}
                       for role in ('native_RUN_MANIFEST', 'NAV_10HZ', 'v3_error_series', 'v2_error_series')]
        for version in ('v3', 'v2'):
            summary = destination/version/'summary.json'
            write_json(summary, {'status': 'NOT_RUN_ALGORITHM_FAILURE',
                'method_outcome': record['terminal_status'], 'metrics': None,
                'evaluator_invoked': False, 'native_nav_available': False})
            retained[version+'/summary.json'] = {'sha256': hash_file(summary),
                'size_bytes': summary.stat().st_size, 'allocated_bytes': summary.stat().st_blocks*512}
    wrapper = destination/'RUN_MANIFEST.json'
    write_json(wrapper, {'manifest_role': 'PROTOCOL_V2_ARCHIVE_WRAPPER', **posthoc_metadata,
        'native_manifest_relative_path': 'solver/RUN_MANIFEST.json' if record['terminal_status'] == 'COMPLETED' else None,
        'native_manifest_substituted': False, 'protocol_id': record.get('protocol_id'),
        'code_commit': record.get('code_commit'), 'run_id': record['run_id'],
        'archive_code_commit': archive_code_commit,
        'origin_code_commit': record.get('code_commit'),
        'original_native_code_commit': record.get('original_native_code_commit', record.get('code_commit')),
        'continuation_code_commit': record.get('continuation_code_commit', record.get('code_commit')),
        'original_terminal_status': record.get('original_terminal_status', record['terminal_status']),
        'original_native_reused': bool(record.get('original_native_reused', False)),
        'validation_record_relative_path': validation_files.get('record', {}).get('archive_relative_path'),
        'validation_config_relative_path': validation_files.get('config', {}).get('archive_relative_path'),
        **{key: record[key] for key in ('validation_code_commit', 'validation_record_path',
            'validation_record_sha256', 'validation_config_path', 'validation_config_hash',
            'validation_config_sha256') if key in record},
        'validation_files': validation_files,
        'dataset_id': record['dataset_id'], 'case_id': record.get('case_id'),
        'method_id': record.get('method_id'), 'terminal_status': record['terminal_status'],
        'unavailable_members': unavailable, 'data_mode': record.get('data_mode'),
        'synthetic_data_used': record.get('synthetic_data_used', False),
        'semisynthetic_data_used': record.get('semisynthetic_data_used', False),
        'raw_source_hashes': record.get('raw_source_hashes'), 'provider_hashes': record.get('provider_hashes'),
        'config_hash': record.get('config_hash'), 'trace_used_online': False})
    retained['RUN_MANIFEST.json'] = {'sha256': hash_file(wrapper), 'size_bytes': wrapper.stat().st_size,
                                    'allocated_bytes': wrapper.stat().st_blocks*512}
    receipt['retained_bytes'] = sum(p['size_bytes'] for p in retained.values())
    receipt['retained_allocated_bytes'] = sum(p['allocated_bytes'] for p in retained.values())
    return receipt




def _prepare_receipt_scratch(receipt, staging, destination, *, retry_delays):
    """Retry scratch receipt write/hash/stat in exclusive temporary files only."""
    staging = Path(staging)
    canonical = staging/'ARCHIVE_RECEIPT.json'
    paths = [staging/f'ARCHIVE_RECEIPT.json.write_attempt_{index:02d}'
             for index in range(1, len(retry_delays)+2)]
    receipt['scratch_receipt_attempt_paths'] = list(map(str, paths))
    attempt = 0
    def prepare():
        nonlocal attempt
        path = paths[attempt]
        attempt += 1
        write_json(path, receipt)
        return path, {'sha256': sha256_file(path), 'size_bytes': path.stat().st_size}
    kwargs = {'source': staging, 'destination': destination, 'staging_root': staging,
              'retry_delays': retry_delays}
    (temporary, pin), _ = retry_io(prepare, operation='scratch_receipt_write_hash_stat', **kwargs)
    # This link is strictly on the ext4 scratch filesystem, never DrvFs. It
    # atomically avoids replacing any pre-existing receipt and copies no bytes.
    def publish_scratch():
        try:
            os.link(temporary, canonical)
        except FileExistsError:
            left, right = temporary.stat(), canonical.stat()
            if (left.st_dev, left.st_ino) != (right.st_dev, right.st_ino):
                raise
    retry_io(publish_scratch, operation='scratch_receipt_publish', **kwargs)
    def remove_successful_temporary():
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    retry_io(remove_successful_temporary, operation='scratch_receipt_remove_successful_temp', **kwargs)
    return canonical, pin


def retain_run(record, evaluation_roots, destination, *, archive_code_commit=None, scratch_archive_root=None,
               retry_delays=RETRY_DELAYS):
    """Prepare on ext4 scratch, stream to an exclusive archive, publish receipt last.

    The original signature remains valid. The controller supplies separate
    attempt paths when retrying an incomplete archive; no old partial changes.
    """
    source, destination = Path(record['output_root']), Path(destination)
    def require_new_destination():
        if destination.exists() or destination.is_symlink():
            raise FileExistsError('Archive destination already exists; retain partial scene')
    _, destination_preflight_events = retry_io(require_new_destination, source=source, destination=destination,
        operation='archive_destination_preflight', staging_root=scratch_archive_root, retry_delays=retry_delays)
    if scratch_archive_root is None:
        staging_parent = source.parent.parent/'ARCHIVE_STAGING'
        staging_parent.mkdir(parents=True, exist_ok=True)
        holder = Path(tempfile.mkdtemp(prefix=str(record['run_id'])+'-', dir=staging_parent))
        staging = holder/'payload'
    else:
        staging = Path(scratch_archive_root)
    if staging.is_symlink() or staging.exists() or staging == source or source in staging.parents:
        raise ValueError('Archive staging must be a new scratch directory outside native outputs')
    if destination == staging or destination in staging.parents or staging in destination.parents:
        raise ValueError('Scratch staging and archive destinations must be separate')
    archive_code_commit = archive_code_commit or record.get('archive_code_commit') or record.get('continuation_code_commit', record.get('code_commit'))
    io_timings = {key: 0.0 for key in ('hash_wall_seconds', 'hash_cpu_seconds',
        'compress_wall_seconds', 'compress_cpu_seconds', 'copy_wall_seconds', 'copy_cpu_seconds')}
    started, cpu_started = time.monotonic(), time.thread_time()
    staging_base = staging
    staging_roots, preparation_attempts = [], []
    retry_delays = tuple(retry_delays)
    for prepare_attempt in range(1, len(retry_delays)+2):
        staging = staging_base if prepare_attempt == 1 else staging_base.with_name(
            staging_base.name+f'.prepare_retry_{prepare_attempt-1:02d}')
        staging_roots.append(str(staging))
        attempt_started = time.monotonic()
        try:
            receipt = _prepare_retained_run(record, evaluation_roots, staging,
                archive_code_commit=archive_code_commit, io_timings=io_timings)
            preparation_attempts.append({'attempt': prepare_attempt, 'status': 'COMPLETED',
                'scratch_archive_root': str(staging), 'wall_seconds': time.monotonic()-attempt_started})
            break
        except OSError as error:
            preparation_attempts.append({'attempt': prepare_attempt, 'status': 'FAILED_IO',
                'scratch_archive_root': str(staging), 'errno': error.errno, 'failure': str(error),
                'wall_seconds': time.monotonic()-attempt_started})
            if error.errno not in RETRY_ERRNOS:
                raise
            if prepare_attempt > len(retry_delays):
                pending = ArchiveRetryPending(source=source, destination=destination,
                    operation='scratch_archive_preparation', error=error, attempts=prepare_attempt, staging_root=staging)
                pending.staging_roots = list(staging_roots)
                raise pending from error
            preparation_attempts[-1]['retry_delay_seconds'] = retry_delays[prepare_attempt-1]
            time.sleep(retry_delays[prepare_attempt-1])
    io_timings['scratch_prepare_wall_seconds'] = time.monotonic()-started
    io_timings['scratch_prepare_cpu_seconds'] = time.thread_time()-cpu_started
    receipt_attempt_paths = []
    def archive_operation(function):
        try:
            return function()
        except ArchiveRetryPending as error:
            error.staging_roots = list(staging_roots)
            error.scratch_receipt_attempt_paths = list(receipt_attempt_paths)
            raise
    _, destination_create_events = archive_operation(lambda: retry_io(
        lambda: destination.mkdir(parents=True, exist_ok=False), source=source, destination=destination,
        operation='archive_destination_mkdir', staging_root=staging, retry_delays=retry_delays))
    copy_attempts = []
    for relative, pin in receipt['retained_files'].items():
        result = archive_operation(lambda: stream_copy(staging/relative, destination/relative,
            expected_sha256=pin['sha256'], expected_size_bytes=pin['size_bytes'],
            staging_root=staging, retry_delays=retry_delays))
        io_timings['copy_wall_seconds'] += result['wall_seconds']
        io_timings['copy_cpu_seconds'] += result['cpu_seconds']
        pin['allocated_bytes'] = result['allocated_bytes']
        copy_attempts.append({'relative_path': relative, 'attempt_count': result['attempt_count'],
                              'retry_events': result['retry_events']})
    receipt.update(archive_code_commit=archive_code_commit, archive_root=str(destination),
        destination=str(destination), scratch_archive_root=str(staging),
        scratch_archive_roots=staging_roots, scratch_preparation_attempts=preparation_attempts,
        io_timings=io_timings, archive_copy_attempts=copy_attempts,
        archive_metadata_retry_events=destination_preflight_events+destination_create_events,
        archive_retry_delays_seconds=list(retry_delays),
        retained_allocated_bytes=sum(p['allocated_bytes'] for p in receipt['retained_files'].values()),
        archive_integrity_policy='scratch sha256 equals successfully written stream sha256; flush/close checked; no G payload reread',
        gzip_compresslevel=3, copy_block_bytes=BLOCK_BYTES, receipt_published_last=True,
        io_cpu_measurement_scope='calling thread CPU seconds; summed by controller across archive tasks',
        io_timer_scope='hash: source inventory and scratch sha256; compress: gzip/thinning and source-stream hash; copy: G writes and stream sha256; receipt publication excluded')
    io_timings['pre_receipt_wall_seconds'] = time.monotonic()-started
    io_timings['pre_receipt_cpu_seconds'] = time.thread_time()-cpu_started
    receipt_attempt_paths = [str(staging/f'ARCHIVE_RECEIPT.json.write_attempt_{index:02d}')
                             for index in range(1, len(retry_delays)+2)]
    receipt_path, receipt_pin = archive_operation(lambda: _prepare_receipt_scratch(
        receipt, staging, destination, retry_delays=retry_delays))
    # No successful receipt can exist while a member write is incomplete.
    archive_operation(lambda: stream_copy(receipt_path, destination/'ARCHIVE_RECEIPT.json',
        expected_sha256=receipt_pin['sha256'], expected_size_bytes=receipt_pin['size_bytes'],
        staging_root=staging, retry_delays=retry_delays))
    return receipt


def cleanup_exact(root, files, ledger_path, *, scratch_root, archive_verified):
    """Delete only inventoried regular files inside this owned scratch batch."""
    root, scratch_root = Path(root), Path(scratch_root)
    if not archive_verified or root == scratch_root or not root.is_relative_to(scratch_root):
        raise ValueError('Cleanup needs verified archive and proper owned subdirectory')
    if isinstance(archive_verified, dict):
        if (archive_verified.get('status') != 'ARCHIVE_VERIFIED'
                or files not in archive_verified.get('original_files', {}).values()):
            raise ValueError('Cleanup receipt is invalid or does not cover this exact file inventory')
    for relative, pin in files.items():
        relative = Path(relative)
        path = root/relative
        if relative.is_absolute() or '..' in relative.parts or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Unsafe exact cleanup member')
        if not path.is_file() or path.stat().st_size != pin['size_bytes'] or sha256_file(path) != pin['sha256']:
            raise ValueError('Cleanup member changed since archive')
        append_json(ledger_path, {'status': 'DELETE_INTENT', 'path': str(path), **pin})
        path.unlink()
        append_json(ledger_path, {'status': 'DELETED', 'path': str(path), **pin})
    # Empty directories are left as attempt-owned records; no recursive/glob deletion.


def machine_state():
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        mem[key] = int(value.strip().split()[0])*1024
    times = []
    visible = os.sched_getaffinity(0)
    for line in Path('/proc/stat').read_text().splitlines():
        fields = line.split()
        if fields and fields[0].startswith('cpu') and fields[0][3:].isdigit() and int(fields[0][3:]) in visible:
            v = [int(x) for x in fields[1:9]]
            times.append((sum(v), v[3]+v[4]))
    return {'nproc': len(visible), 'memory_total_bytes': mem['MemTotal'],
            'memory_available_bytes': mem['MemAvailable'],
            'memory_used_bytes': mem['MemTotal']-mem['MemAvailable'],
            'cpu_ticks': sum(x[0] for x in times), 'idle_ticks': sum(x[1] for x in times)}


class ResourceMonitor:
    def __init__(self, scratch, g_root, sample_path, *, sample_interval_seconds=2, root_pid=None):
        self.scratch, self.g_root = Path(scratch), Path(g_root)
        self.sample_path = Path(sample_path)
        if not math.isfinite(sample_interval_seconds) or sample_interval_seconds <= 0:
            raise ValueError('Resource sample interval must be positive and finite')
        self.sample_interval_seconds = sample_interval_seconds
        self.root_pid = os.getpid() if root_pid is None else root_pid
        self.initial = machine_state()
        self.disk_start = {label: dict(zip(('total_bytes', 'used_bytes', 'free_bytes'), shutil.disk_usage(path)))
                           for label, path in (('scratch', scratch), ('g', g_root))}
        self.disk_current = dict(self.disk_start)
        self.free_start = {label: values['free_bytes'] for label, values in self.disk_start.items()}
        self.peak_growth = {'scratch': 0, 'g': 0}
        self.memory_peak = self.initial['memory_used_bytes']
        self.owned_rss_peak = 0
        self.owned_process_count_peak = 0
        self.phases = []
        self.active_phase = None
        self.lock = threading.RLock()
        self.monitor_failure = None
        self.started = time.monotonic()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def sample(self):
        with self.lock:
            self.assert_healthy()
            return self._sample_locked()

    def assert_healthy(self):
        with self.lock:
            if self.monitor_failure is not None:
                raise RuntimeError('Resource monitor failed; preserve scene before cleanup') from self.monitor_failure

    def _sample_locked(self):
        state = machine_state()
        owned = process_tree_rss(self.root_pid)
        self.memory_peak = max(self.memory_peak, state['memory_used_bytes'])
        self.owned_rss_peak = max(self.owned_rss_peak, owned['owned_rss_bytes'])
        self.owned_process_count_peak = max(self.owned_process_count_peak, owned['owned_process_count'])
        self.disk_current = {label: dict(zip(('total_bytes', 'used_bytes', 'free_bytes'), shutil.disk_usage(path)))
                             for label, path in (('scratch', self.scratch), ('g', self.g_root))}
        disk_free = {label: values['free_bytes'] for label, values in self.disk_current.items()}
        growth = {label: max(0, self.free_start[label]-disk_free[label]) for label in disk_free}
        for label in growth: self.peak_growth[label] = max(self.peak_growth[label], growth[label])
        if self.active_phase is not None:
            phase = self.active_phase
            phase['owned_process_tree_peak_rss_bytes'] = max(phase['owned_process_tree_peak_rss_bytes'], owned['owned_rss_bytes'])
            phase['owned_process_count_peak'] = max(phase['owned_process_count_peak'], owned['owned_process_count'])
            phase['memory_peak_bytes'] = max(phase['memory_peak_bytes'], state['memory_used_bytes'])
            phase['minimum_available_memory_bytes'] = min(phase['minimum_available_memory_bytes'], state['memory_available_bytes'])
            phase['sample_count'] += 1
            for label in disk_free:
                phase['filesystem_peak_growth_bytes'][label] = max(phase['filesystem_peak_growth_bytes'][label],
                    phase['_free_start'][label]-disk_free[label])
        append_json(self.sample_path, {'elapsed_seconds': time.monotonic()-self.started, **state,
                                      **owned, 'phase': self.active_phase['phase'] if self.active_phase else None,
                                      'filesystem_used_growth_bytes': growth,
                                      'filesystem_absolute_bytes': self.disk_current,
                                      'filesystem_baseline_bytes': self.disk_start})
        return state, owned, disk_free

    def begin_phase(self, name):
        with self.lock:
            self.assert_healthy()
            if not isinstance(name, str) or not name or self.active_phase is not None:
                raise ValueError('Named resource phase requires the previous phase to be ended')
            state, owned, disk_free = self._sample_locked()
            self.active_phase = {'phase': name, '_started': time.monotonic(), '_initial': state,
                '_free_start': disk_free, 'owned_process_tree_peak_rss_bytes': owned['owned_rss_bytes'],
                'owned_process_count_peak': owned['owned_process_count'], 'memory_peak_bytes': state['memory_used_bytes'],
                'available_memory_at_start_bytes': state['memory_available_bytes'],
                'minimum_available_memory_bytes': state['memory_available_bytes'],
                'filesystem_peak_growth_bytes': {'scratch': 0, 'g': 0}, 'sample_count': 1}

    def end_phase(self):
        with self.lock:
            self.assert_healthy()
            if self.active_phase is None:
                raise ValueError('No active resource phase to end')
            final, _, _ = self._sample_locked()
            phase = self.active_phase
            total = final['cpu_ticks']-phase['_initial']['cpu_ticks']
            idle = final['idle_ticks']-phase['_initial']['idle_ticks']
            result = {k: v for k, v in phase.items() if not k.startswith('_')}
            result.update(wall_seconds=time.monotonic()-phase['_started'],
                owned_rss_peak_bytes=phase['owned_process_tree_peak_rss_bytes'],
                cpu_utilization_fraction=(total-idle)/total if total else None,
                measurement_scope='host affinity CPU and memory; owned controller+descendant summed RSS; disk free-space deltas',
                owned_rss_measurement_scope='sampled sum over process leaders; shared resident pages counted per process',
                sample_interval_seconds=self.sample_interval_seconds)
            self.phases.append(result)
            self.active_phase = None
            return result

    def _loop(self):
        try:
            while not self.stop_event.wait(self.sample_interval_seconds):
                self.sample()
        except Exception as error:
            with self.lock:
                self.monitor_failure = error
                self.stop_event.set()

    def __enter__(self):
        self.sample()
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop_event.set()
        self.thread.join()
        try:
            self.assert_healthy()
            if self.active_phase is not None:
                self.end_phase()
            else:
                self.sample()
            self.assert_healthy()
        except Exception as error:
            with self.lock:
                if self.monitor_failure is None:
                    self.monitor_failure = error
            if not args[0]:
                raise
            # Preserve the operation's original failure while retaining monitor
            # failure state. Neither failure authorizes archive cleanup.
        return False

    def result(self):
        self.assert_healthy()
        final = machine_state()
        total = final['cpu_ticks']-self.initial['cpu_ticks']
        idle = final['idle_ticks']-self.initial['idle_ticks']
        return {'wall_seconds': time.monotonic()-self.started, 'nproc': self.initial['nproc'],
                'available_memory_at_start_bytes': self.initial['memory_available_bytes'],
                'memory_total_bytes': self.initial['memory_total_bytes'],
                'memory_peak_bytes': self.memory_peak,
                'memory_peak_fraction': self.memory_peak/self.initial['memory_total_bytes'],
                'owned_process_tree_peak_rss_bytes': self.owned_rss_peak,
                'owned_rss_peak_bytes': self.owned_rss_peak,
                'owned_process_count_peak': self.owned_process_count_peak,
                'phases': list(self.phases),
                'cpu_utilization_fraction': (total-idle)/total if total else None,
                'filesystem_peak_growth_bytes': dict(self.peak_growth),
                'filesystem_baseline_bytes': self.disk_start,
                'filesystem_current_bytes': self.disk_current,
                'measurement_scope': 'host visible affinity CPU and MemAvailable; filesystem free-space deltas; concurrent activity included',
                'owned_rss_measurement_scope': 'controller and current descendants; summed process RSS; shared mappings counted per process; sampled peak',
                'monitor_status': 'PASS' if self.monitor_failure is None else 'FAILED',
                'sample_interval_seconds': self.sample_interval_seconds}
