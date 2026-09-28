"""Bounded archive stream writes; hashes cover written bytes without G rereads."""
from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path
import time

BLOCK_BYTES = 8 * 1024 * 1024
RETRY_ERRNOS = frozenset((errno.ENOMEM, errno.EIO, errno.EAGAIN))
RETRY_DELAYS = (2, 4, 8)


class ArchiveRetryPending(RuntimeError):
    """Bounded I/O attempts exhausted; caller retains scene and defers retry."""
    def __init__(self, *, source, destination, operation, error, attempts, staging_root=None):
        self.source = str(source)
        self.destination = str(destination)
        self.operation = operation
        self.errno = getattr(error, 'errno', None)
        self.failure = str(error)
        self.attempts = attempts
        self.staging_root = str(staging_root) if staging_root is not None else None
        self.staging_roots = [self.staging_root] if self.staging_root is not None else []
        super().__init__(f'ARCHIVE_RETRY_PENDING operation={operation} errno={self.errno} '
                         f'attempts={attempts} destination={destination}: {error}')


def retry_io(function, *, source, destination, operation, staging_root=None,
             retry_delays=RETRY_DELAYS, sleep=time.sleep):
    """Apply the same bounded policy to archive metadata and read/write ops."""
    delays = tuple(retry_delays)
    if delays not in (RETRY_DELAYS, ()):
        raise ValueError('Archive retry policy must be (2,4,8) or an explicit single attempt')
    events = []
    for attempt in range(1, len(delays)+2):
        try:
            return function(), events
        except OSError as error:
            if error.errno not in RETRY_ERRNOS:
                raise
            failed_operation = getattr(error, 'archive_operation', operation)
            events.append({'attempt': attempt, 'operation': failed_operation, 'errno': error.errno,
                           'failure': str(error)})
            if attempt > len(delays):
                raise ArchiveRetryPending(source=source, destination=destination,
                    operation=failed_operation, error=error, attempts=attempt, staging_root=staging_root) from error
            events[-1]['retry_delay_seconds'] = delays[attempt-1]
            sleep(delays[attempt-1])
    raise AssertionError('Archive metadata retry loop fell through')


def _open_output(path):
    return Path(path).open('xb', buffering=0)


def _write_all(writer, block):
    view = memoryview(block)
    written = 0
    while written < len(view):
        count = writer.write(view[written:])
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0 or count > len(view)-written:
            raise OSError(errno.EIO, 'Archive short write made no valid progress')
        written += count
    return written


def _require_absent(path):
    if path.exists() or path.is_symlink():
        raise FileExistsError('Archive final destination already exists: '+str(path))


def stream_copy(source, destination, *, expected_sha256, expected_size_bytes,
                staging_root=None, retry_delays=RETRY_DELAYS, sleep=time.sleep):
    """O_EXCL member creation with full scratch replay after durability errors.

    Fixed-offset chunk retries never duplicate SHA input. Any flush/fsync/close
    error restarts the entire stream from the pinned scratch source into the
    same owned inode, followed by a fresh hash, fsync and real close. No G read.
    """
    source, destination = Path(source), Path(destination)
    delays = tuple(retry_delays)
    if delays not in (RETRY_DELAYS, ()):
        raise ValueError('Archive retry policy must be (2,4,8) or an explicit single attempt')
    wall_start, cpu_start = time.monotonic(), time.thread_time()
    events = []
    kwargs = {'source': source, 'destination': destination, 'staging_root': staging_root,
              'retry_delays': delays, 'sleep': sleep}
    def operation(function, name):
        result, errors = retry_io(function, operation=name, **kwargs)
        events.extend(errors)
        return result
    def check_source():
        if source.is_symlink() or not source.is_file():
            raise ValueError('Archive source is missing or a symlink')
    operation(check_source, 'source_preflight')
    def prepare():
        _require_absent(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
    operation(prepare, 'prepare_destination')
    writer = operation(lambda: _open_output(destination), 'open')
    identity = None
    payload_passes = 0
    replay_bytes = 0
    try:
        identity = operation(lambda: os.fstat(writer.fileno()), 'owned_fstat')
        def write_flush_close():
            nonlocal writer, payload_passes, replay_bytes
            phase = 'source_open'
            reader = None
            try:
                if payload_passes:
                    # A writeback failure can concern any earlier block. A
                    # successful second fsync alone is not recovery evidence.
                    if writer is not None and not writer.closed:
                        try:
                            writer.close()
                        except OSError:
                            pass
                    descriptor = operation(lambda: os.open(destination, os.O_WRONLY), 'owned_reopen')
                    try:
                        current = operation(lambda: os.fstat(descriptor), 'owned_reopen_stat')
                        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
                            raise ValueError('Archive replay lost owned inode identity')
                        writer = os.fdopen(descriptor, 'wb', buffering=0)
                    except BaseException:
                        try: os.close(descriptor)
                        except OSError: pass
                        raise
                payload_passes += 1
                digest = hashlib.sha256()
                count = 0
                reader = operation(lambda: source.open('rb', buffering=0), 'source_open')
                while True:
                    offset = count
                    def read_block():
                        # A failed buffered/native read may have advanced its
                        # cursor. Reposition before every read attempt.
                        reader.seek(offset)
                        return reader.read(BLOCK_BYTES)
                    block = operation(read_block, 'read_source')
                    if not block:
                        break
                    def write_block():
                        writer.seek(offset)
                        return _write_all(writer, block)
                    count += operation(write_block, 'write')
                    digest.update(block)
                phase = 'source_close'
                operation(reader.close, 'source_close')
                reader = None
                if count != expected_size_bytes or digest.hexdigest() != expected_sha256:
                    raise ValueError('Archive written-byte size/hash differs from scratch source pin')
                replay_bytes += count
                phase = 'flush'
                writer.flush()
                phase = 'fsync'
                os.fsync(writer.fileno())
                phase = 'close'
                writer.close()
                writer = None
                return digest.hexdigest(), count
            except OSError as error:
                error.archive_operation = phase
                raise
            finally:
                if reader is not None:
                    try: reader.close()
                    except OSError: pass
        (digest, count), durability_events = retry_io(write_flush_close, operation='durable_file_write', **kwargs)
        events.extend(durability_events)
        metadata = operation(destination.stat, 'published_stat')
        if (metadata.st_dev, metadata.st_ino, metadata.st_size) != (identity.st_dev, identity.st_ino, count):
            raise ValueError('Archive final size/inode differs from successfully written owned file')
    except BaseException:
        if writer is not None and not writer.closed:
            try: writer.close()
            except OSError: pass
        raise
    attempts = max((event['attempt']+1 for event in events), default=1)
    return {'sha256': digest, 'size_bytes': count,
            'allocated_bytes': metadata.st_blocks*512,
            'attempt_count': attempts, 'retry_events': events,
            'payload_write_passes': payload_passes, 'complete_payload_bytes_written': replay_bytes,
            'wall_seconds': time.monotonic()-wall_start,
            'cpu_seconds': time.thread_time()-cpu_start,
            'integrity_policy': 'O_EXCL owned inode; pinned scratch whole-file replay on flush/fsync/close errors; fresh stream sha256/fsync/close; no archive reread',
            'block_bytes': BLOCK_BYTES, 'retry_delays': list(delays),
            'failure_member_policy': 'retain incomplete final member in exclusive attempt directory; no successful run receipt'}
