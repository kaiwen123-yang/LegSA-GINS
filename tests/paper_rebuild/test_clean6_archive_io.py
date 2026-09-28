"""Injected I/O-only regressions; temporary synthetic bytes never enter real tables."""
import errno
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean6_canonical_v2 import archive_io, storage


def pin(data):
    return {'expected_sha256': hashlib.sha256(data).hexdigest(), 'expected_size_bytes': len(data)}


@pytest.mark.parametrize('error_number', [errno.ENOMEM, errno.EIO, errno.EAGAIN])
def test_transient_errors_use_initial_plus_three_attempts(tmp_path, monkeypatch, error_number):
    data = b'archive bytes'*100
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'g'/'target'
    original = archive_io._open_output
    calls, delays = [], []
    def faulty(path):
        calls.append(path)
        if len(calls) <= 3:
            raise OSError(error_number, 'injected transient open failure')
        return original(path)
    monkeypatch.setattr(archive_io, '_open_output', faulty)
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert output.read_bytes() == data
    assert result['attempt_count'] == 4 and len(calls) == 4
    assert delays == [2, 4, 8]
    assert result['sha256'] == pin(data)['expected_sha256']


def test_exhaustion_is_pending_preserves_source_and_has_no_final_file(tmp_path, monkeypatch):
    source = tmp_path/'source'; source.write_bytes(b'x')
    output = tmp_path/'g'/'target'
    delays = []
    def fail(_):
        raise OSError(errno.ENOMEM, 'injected exhausted allocation')
    monkeypatch.setattr(archive_io, '_open_output', fail)
    with pytest.raises(archive_io.ArchiveRetryPending) as caught:
        archive_io.stream_copy(source, output, **pin(b'x'), staging_root=tmp_path, sleep=delays.append)
    error = caught.value
    assert (error.errno, error.attempts, error.operation) == (errno.ENOMEM, 4, 'open')
    assert error.staging_root == str(tmp_path)
    assert delays == [2, 4, 8] and not output.exists() and source.read_bytes() == b'x'


class ShortWriter:
    def __init__(self, raw, *, fail=None):
        self.raw, self.fail = raw, fail
        self.failed = False
        self.calls = 0
    @property
    def closed(self): return self.raw.closed
    def fileno(self): return self.raw.fileno()
    def seek(self, offset): return self.raw.seek(offset)
    def write(self, value):
        self.calls += 1
        return self.raw.write(value[:7])
    def flush(self):
        if self.fail == 'flush' and not self.failed:
            self.failed = True
            raise OSError(errno.EIO, 'injected flush error')
        return self.raw.flush()
    def close(self):
        self.raw.close()
        if self.fail == 'close' and not self.failed:
            self.failed = True
            raise OSError(errno.EAGAIN, 'injected close error')


def test_short_writes_are_completed_before_hash_advances(tmp_path, monkeypatch):
    source = tmp_path/'source'; data = bytes(range(256))*5; source.write_bytes(data)
    output = tmp_path/'target'
    original = archive_io._open_output
    writers = []
    def open_short(path):
        wrapped = ShortWriter(original(path)); writers.append(wrapped); return wrapped
    monkeypatch.setattr(archive_io, '_open_output', open_short)
    result = archive_io.stream_copy(source, output, **pin(data), sleep=lambda _: None)
    assert output.read_bytes() == data and writers[0].calls > 1
    assert result['attempt_count'] == 1 and result['sha256'] == pin(data)['expected_sha256']


@pytest.mark.parametrize('failure', ['flush', 'close'])
def test_flush_and_close_failures_retry_without_publishing_partial(tmp_path, monkeypatch, failure):
    data = b'complete compressed member'
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'target'
    original = archive_io._open_output
    calls, delays = [], []
    def failing_once(path):
        calls.append(path)
        return ShortWriter(original(path), fail=failure if len(calls) == 1 else None)
    monkeypatch.setattr(archive_io, '_open_output', failing_once)
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert result['attempt_count'] == 2 and delays == [2]
    assert result['retry_events'][0]['operation'] == failure
    assert output.read_bytes() == data
    assert len(calls) == 1  # only one O_EXCL inode; retries operate on that owned file


def test_nonretryable_error_stops_without_sleep(tmp_path, monkeypatch):
    source = tmp_path/'source'; source.write_bytes(b'x')
    def denied(_): raise PermissionError(errno.EACCES, 'injected')
    monkeypatch.setattr(archive_io, '_open_output', denied)
    sleeps = []
    with pytest.raises(PermissionError):
        archive_io.stream_copy(source, tmp_path/'target', **pin(b'x'), sleep=sleeps.append)
    assert sleeps == []


def scene(tmp_path):
    source = tmp_path/'scratch'/'batch'/'03_RUNS'/'synthetic'; source.mkdir(parents=True)
    nav = ('1 66.001 30 110 1 0 0 0 1 2 3\n'
           '1 66.099 30 110 1 0 0 0 1 2 3\n'
           '1 66.101 30 110 1 0 0 0 1 2 3\n')
    (source/'KF_GINS_Navresult.nav').write_text(nav)
    (source/'KF_GINS_STD.txt').write_text('66.001 1 2 3\n')
    (source/'RUN_MANIFEST.json').write_text('{}')
    (source/'PORT_GNSS_UPDATE_TRACE.csv').write_text('test\n1\n')
    record = {'output_root': str(source), 'terminal_status': 'COMPLETED', 'run_id': 'synthetic',
              'dataset_id': 'SYNTHETIC_TEST', 'code_commit': 'native', 'synthetic_data_used': True}
    from legsa_gins.paper_rebuild.clean6_canonical_v2.runtime import seal_run
    record['output_seal'] = seal_run(source)
    evaluations = {}
    for version in ('v3', 'v2'):
        root = tmp_path/'scratch'/'batch'/version/'synthetic'; payload = root/'FROZEN_EVALUATOR'; payload.mkdir(parents=True)
        (payload/'summary.json').write_text('{}')
        (payload/'error_series.csv').write_text('t,e\n1,2\n')
        with gzip.open(payload/'error_series.csv.gz', 'wb') as stream: stream.write(b't,e\n1,2\n')
        evaluations[version] = root
    return record, evaluations


def test_retention_stages_on_scratch_never_reads_g_and_publishes_receipt_last(tmp_path, monkeypatch):
    record, evaluations = scene(tmp_path)
    archive = tmp_path/'g'/'run'
    staging = tmp_path/'scratch'/'batch'/'ARCHIVE_STAGING'/'attempt01'
    old_open = Path.open
    writes = []
    def checked_open(path, mode='r', *args, **kwargs):
        if archive in path.parents:
            assert 'r' not in mode, 'archive payload reread is forbidden'
            if 'x' in mode: writes.append(path.name)
        return old_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', checked_open)
    receipt = storage.retain_run(record, evaluations, archive,
                                archive_code_commit='archive_only', scratch_archive_root=staging)
    assert writes[-1] == 'ARCHIVE_RECEIPT.json'
    assert receipt['archive_code_commit'] == 'archive_only'
    assert receipt['copy_block_bytes'] == 8*1024*1024 and receipt['gzip_compresslevel'] == 3
    assert receipt['receipt_published_last'] and receipt['archive_root'] == str(archive)
    monkeypatch.setattr(Path, 'open', old_open)
    saved = json.loads((archive/'ARCHIVE_RECEIPT.json').read_text())
    assert saved == receipt
    wrapper = json.loads((archive/'RUN_MANIFEST.json').read_text())
    assert wrapper['code_commit'] == 'native' and wrapper['archive_code_commit'] == 'archive_only'
    assert gzip.open(archive/'solver/NAV_10HZ.csv.gz', 'rt').read().count('\n') == 3
    assert gzip.open(archive/'solver/PORT_GNSS_UPDATE_TRACE.csv.gz', 'rt').read() == 'test\n1\n'
    assert Path(record['output_root']).joinpath('KF_GINS_Navresult.nav').exists()


def test_failed_member_never_publishes_valid_receipt_or_cleans_sources(tmp_path, monkeypatch):
    record, evaluations = scene(tmp_path)
    archive = tmp_path/'g'/'run'; staging = tmp_path/'scratch'/'new_staging'
    def fail(source, destination, **kwargs):
        raise archive_io.ArchiveRetryPending(source=source, destination=destination, operation='write',
            error=OSError(errno.EIO, 'injected'), attempts=4, staging_root=kwargs['staging_root'])
    monkeypatch.setattr(storage, 'stream_copy', fail)
    with pytest.raises(archive_io.ArchiveRetryPending):
        storage.retain_run(record, evaluations, archive, scratch_archive_root=staging)
    assert staging.is_dir() and archive.is_dir()
    assert not (archive/'ARCHIVE_RECEIPT.json').exists()
    assert Path(record['output_root']).joinpath('KF_GINS_Navresult.nav').exists()


def test_postpublish_stat_transient_retries_metadata_without_rewriting_payload(tmp_path, monkeypatch):
    data = b'one published stream'
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'target'
    old_stat, old_open = Path.stat, archive_io._open_output
    stats, opens, delays = [], [], []
    def stat_fail_after_publish(path, *args, **kwargs):
        if path == output:
            try:
                metadata = old_stat(path, *args, **kwargs)
            except FileNotFoundError:
                raise
            stats.append(path)
            if len(stats) <= 3:
                raise OSError(errno.EIO, 'injected published stat error')
            return metadata
        return old_stat(path, *args, **kwargs)
    def count_open(path): opens.append(path); return old_open(path)
    monkeypatch.setattr(Path, 'stat', stat_fail_after_publish)
    monkeypatch.setattr(archive_io, '_open_output', count_open)
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert len(opens) == 1 and len(stats) == 4 and delays == [2, 4, 8]
    assert result['retry_events'][-1]['operation'] == 'published_stat'
    monkeypatch.setattr(Path, 'stat', old_stat)
    assert output.read_bytes() == data


def test_g_mkdir_transient_uses_same_bounded_policy(tmp_path, monkeypatch):
    data = b'mkdir'
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'g'/'target'
    old_mkdir = Path.mkdir
    calls, delays = [], []
    def injected(path, *args, **kwargs):
        if path == output.parent:
            calls.append(path)
            if len(calls) <= 3:
                raise OSError(errno.ENOMEM, 'injected directory creation allocation')
        return old_mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', injected)
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert output.read_bytes() == data and delays == [2, 4, 8] and len(calls) == 4
    assert result['retry_events'][0]['operation'] == 'prepare_destination'


def test_explicit_final_round_has_no_backoff_retry(tmp_path, monkeypatch):
    source = tmp_path/'source'; source.write_bytes(b'x')
    def fail(_): raise OSError(errno.EIO, 'injected final-round error')
    monkeypatch.setattr(archive_io, '_open_output', fail)
    delays = []
    with pytest.raises(archive_io.ArchiveRetryPending) as caught:
        archive_io.stream_copy(source, tmp_path/'target', **pin(b'x'), retry_delays=(), sleep=delays.append)
    assert caught.value.attempts == 1 and delays == []


def test_dict_cleanup_receipt_must_cover_exact_inventory(tmp_path):
    scratch = tmp_path/'scratch'; run = scratch/'run'; run.mkdir(parents=True)
    (run/'file').write_bytes(b'keep')
    files = storage.inventory(run)
    with pytest.raises(ValueError, match='receipt is invalid'):
        storage.cleanup_exact(run, files, tmp_path/'ledger', scratch_root=scratch,
            archive_verified={'status': 'ARCHIVE_VERIFIED', 'original_files': {'solver': {}}})
    assert (run/'file').exists()


def test_exclusive_open_publish_race_preserves_existing_target(tmp_path, monkeypatch):
    source = tmp_path/'source'; source.write_bytes(b'new archive bytes')
    output = tmp_path/'target'
    old_open = archive_io._open_output
    def competing_open(path):
        path.write_bytes(b'existing other bytes')
        return old_open(path)
    monkeypatch.setattr(archive_io, '_open_output', competing_open)
    with pytest.raises(FileExistsError):
        archive_io.stream_copy(source, output, **pin(source.read_bytes()), sleep=lambda _: None)
    assert output.read_bytes() == b'existing other bytes'


def test_partial_chunk_write_retry_uses_same_offset_and_hashes_once(tmp_path, monkeypatch):
    data = bytes(range(128))*5
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'target'
    old_open = archive_io._open_output
    class MidChunkFailure(ShortWriter):
        def write(self, value):
            if self.calls == 1 and not self.failed:
                self.failed = True
                raise OSError(errno.EIO, 'injected after seven successful bytes')
            return super().write(value)
    monkeypatch.setattr(archive_io, '_open_output', lambda path: MidChunkFailure(old_open(path)))
    delays = []
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert delays == [2] and result['attempt_count'] == 2
    assert output.read_bytes() == data and result['sha256'] == pin(data)['expected_sha256']


def test_close_recovery_requires_owned_inode_fsync_and_real_close(tmp_path, monkeypatch):
    source = tmp_path/'source'; source.write_bytes(b'closed inode')
    output = tmp_path/'target'
    old_open, old_reopen, old_fsync = archive_io._open_output, archive_io.os.open, archive_io.os.fsync
    calls = {'reopen': 0, 'fsync': 0}
    monkeypatch.setattr(archive_io, '_open_output', lambda path: ShortWriter(old_open(path), fail='close'))
    def count_reopen(*args, **kwargs): calls['reopen'] += 1; return old_reopen(*args, **kwargs)
    def count_fsync(*args, **kwargs): calls['fsync'] += 1; return old_fsync(*args, **kwargs)
    monkeypatch.setattr(archive_io.os, 'open', count_reopen)
    monkeypatch.setattr(archive_io.os, 'fsync', count_fsync)
    result = archive_io.stream_copy(source, output, **pin(b'closed inode'), sleep=lambda _: None)
    assert calls == {'reopen': 1, 'fsync': 2}
    assert result['attempt_count'] == 2 and output.read_bytes() == b'closed inode'
    assert result['payload_write_passes'] == 2
    assert result['complete_payload_bytes_written'] == 2*len(b'closed inode')


def test_close_recovery_exhaustion_remains_pending_with_member_preserved(tmp_path, monkeypatch):
    source = tmp_path/'source'; source.write_bytes(b'preserved pending bytes')
    output = tmp_path/'target'
    old_open, old_fsync = archive_io._open_output, archive_io.os.fsync
    monkeypatch.setattr(archive_io, '_open_output', lambda path: ShortWriter(old_open(path), fail='close'))
    count = 0
    def fail_recovery_fsync(descriptor):
        nonlocal count
        count += 1
        if count > 1: raise OSError(errno.EIO, 'injected recovery fsync failure')
        return old_fsync(descriptor)
    monkeypatch.setattr(archive_io.os, 'fsync', fail_recovery_fsync)
    delays = []
    with pytest.raises(archive_io.ArchiveRetryPending) as caught:
        archive_io.stream_copy(source, output, **pin(b'preserved pending bytes'), sleep=delays.append)
    assert caught.value.operation == 'fsync' and caught.value.attempts == 4
    assert delays == [2, 4, 8] and output.read_bytes() == b'preserved pending bytes'


def test_scratch_preparation_retry_uses_new_owned_directory(tmp_path, monkeypatch):
    record, evaluations = scene(tmp_path)
    archive = tmp_path/'g'/'run'; staging = tmp_path/'scratch'/'prepared'
    old_prepare = storage._prepare_retained_run
    calls, delays = [], []
    def fail_preparation_once(record_arg, roots, target, **kwargs):
        calls.append(target)
        if len(calls) == 1:
            target.mkdir(parents=True)
            (target/'partial').write_bytes(b'kept partial preparation')
            raise OSError(errno.ENOMEM, 'injected scratch archive preparation allocation')
        return old_prepare(record_arg, roots, target, **kwargs)
    monkeypatch.setattr(storage, '_prepare_retained_run', fail_preparation_once)
    monkeypatch.setattr(storage.time, 'sleep', delays.append)
    receipt = storage.retain_run(record, evaluations, archive, scratch_archive_root=staging)
    assert delays == [2] and len(calls) == 2
    assert receipt['scratch_archive_roots'] == [str(staging), str(staging.with_name('prepared.prepare_retry_01'))]
    assert (staging/'partial').read_bytes() == b'kept partial preparation'
    assert receipt['scratch_archive_root'] == str(calls[1])
    assert len(receipt['scratch_preparation_attempts']) == 2


@pytest.mark.parametrize('method', ['exists', 'is_symlink', 'mkdir'])
def test_retain_outer_g_metadata_transients_use_bounded_retry(tmp_path, monkeypatch, method):
    record, evaluations = scene(tmp_path)
    archive = tmp_path/'g'/'run'; staging = tmp_path/'scratch'/'staging'
    old_method, old_retry = getattr(Path, method), storage.retry_io
    calls, delays = [], []
    def failing_metadata(path, *args, **kwargs):
        if path == archive:
            calls.append(path)
            if len(calls) <= 3: raise OSError(errno.EAGAIN, 'injected outer archive metadata error')
        return old_method(path, *args, **kwargs)
    def fast_retry(function, **kwargs):
        kwargs['sleep'] = delays.append
        return old_retry(function, **kwargs)
    monkeypatch.setattr(Path, method, failing_metadata)
    monkeypatch.setattr(storage, 'retry_io', fast_retry)
    receipt = storage.retain_run(record, evaluations, archive, scratch_archive_root=staging)
    assert receipt['status'] == 'ARCHIVE_VERIFIED' and delays == [2, 4, 8]
    assert len(receipt['archive_metadata_retry_events']) == 3


def test_fsync_eio_rewrites_entire_owned_file_and_repairs_lost_prior_bytes(tmp_path, monkeypatch):
    data = b'full pinned scratch payload'*100
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'target'
    old_fsync = archive_io.os.fsync
    sync_calls, delays = [], []
    def lost_writeback(descriptor):
        sync_calls.append(descriptor)
        if len(sync_calls) == 1:
            archive_io.os.pwrite(descriptor, b'LOST_WRITEBACK', 0)
            raise OSError(errno.EIO, 'injected writeback loss after earlier writes')
        return old_fsync(descriptor)
    monkeypatch.setattr(archive_io.os, 'fsync', lost_writeback)
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert result['payload_write_passes'] == 2
    assert result['complete_payload_bytes_written'] == 2*len(data)
    assert output.read_bytes() == data and delays == [2] and len(sync_calls) == 2


def test_source_read_retry_rewinds_after_reader_advanced_before_error(tmp_path, monkeypatch):
    data = b'pinned source, same exact byte order'*100
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'target'
    old_open = Path.open
    class AdvancingReader:
        def __init__(self, raw): self.raw, self.failed = raw, False
        def seek(self, offset): return self.raw.seek(offset)
        def close(self): return self.raw.close()
        def read(self, size):
            block = self.raw.read(size)
            if not self.failed:
                self.failed = True
                raise OSError(errno.EIO, 'injected source read advanced then failed')
            return block
    def source_open(path, mode='r', *args, **kwargs):
        result = old_open(path, mode, *args, **kwargs)
        return AdvancingReader(result) if path == source and mode == 'rb' else result
    monkeypatch.setattr(Path, 'open', source_open)
    delays = []
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert result['payload_write_passes'] == 1 and delays == [2]
    monkeypatch.setattr(Path, 'open', old_open)
    assert output.read_bytes() == data


@pytest.mark.parametrize('method', ['stat', 'open'])
def test_source_initial_metadata_and_open_retry(tmp_path, monkeypatch, method):
    data = b'retry source metadata/open'
    source = tmp_path/'source'; source.write_bytes(data)
    output = tmp_path/'target'
    old_method = getattr(Path, method)
    calls, delays = [], []
    def failing_source(path, *args, **kwargs):
        if path == source:
            calls.append(path)
            if len(calls) <= 3: raise OSError(errno.ENOMEM, 'injected source '+method)
        return old_method(path, *args, **kwargs)
    monkeypatch.setattr(Path, method, failing_source)
    result = archive_io.stream_copy(source, output, **pin(data), sleep=delays.append)
    assert output.read_bytes() == data and delays == [2, 4, 8]
    assert result['payload_write_passes'] == 1


@pytest.mark.parametrize('operation', ['write', 'hash', 'stat'])
def test_scratch_receipt_preparation_retries_with_exclusive_attempts(tmp_path, monkeypatch, operation):
    record, evaluations = scene(tmp_path)
    archive = tmp_path/'g'/'run'; staging = tmp_path/'scratch'/'receipt_staging'
    old_write, old_hash, old_stat, old_retry = storage.write_json, storage.sha256_file, Path.stat, storage.retry_io
    failed, delays = [], []
    def is_receipt(path): return 'ARCHIVE_RECEIPT.json.write_attempt_' in Path(path).name
    def write_fault(path, value):
        if operation == 'write' and is_receipt(path) and not failed:
            failed.append(path)
            Path(path).write_bytes(b'{"partial":')
            raise OSError(errno.EIO, 'injected receipt scratch write')
        return old_write(path, value)
    def hash_fault(path):
        if operation == 'hash' and is_receipt(path) and not failed:
            failed.append(path)
            raise OSError(errno.ENOMEM, 'injected receipt scratch hash')
        return old_hash(path)
    def stat_fault(path, *args, **kwargs):
        if operation == 'stat' and is_receipt(path) and not failed:
            failed.append(path)
            raise OSError(errno.EAGAIN, 'injected receipt scratch stat')
        return old_stat(path, *args, **kwargs)
    def fast_retry(function, **kwargs):
        kwargs['sleep'] = delays.append
        return old_retry(function, **kwargs)
    monkeypatch.setattr(storage, 'write_json', write_fault)
    monkeypatch.setattr(storage, 'sha256_file', hash_fault)
    monkeypatch.setattr(Path, 'stat', stat_fault)
    monkeypatch.setattr(storage, 'retry_io', fast_retry)
    receipt = storage.retain_run(record, evaluations, archive, scratch_archive_root=staging)
    assert delays == [2] and len(failed) == 1 and Path(failed[0]).exists()
    assert receipt['scratch_receipt_attempt_paths'] == [str(staging/f'ARCHIVE_RECEIPT.json.write_attempt_{i:02d}') for i in range(1, 5)]
    assert json.loads((archive/'ARCHIVE_RECEIPT.json').read_text()) == receipt


def test_posthoc_evaluation_seal_annotation_passes_unchanged_to_permanent_metadata(tmp_path):
    record, evaluations = scene(tmp_path)
    source = Path(record['output_root'])
    native_before = storage.inventory(source)
    evaluation_before = {version: storage.inventory(root) for version, root in evaluations.items()}
    sidecar = tmp_path/'IO_RECOVERY'/'POSTHOC_EVALUATION_SEAL.json'
    sidecar.parent.mkdir()
    sidecar.write_text('{"synthetic_test_sidecar":true}\n')
    record['posthoc_evaluation_seal'] = {
        'path': str(sidecar), 'sha256': storage.sha256_file(sidecar),
        'annotation': 'sealed post-hoc after archival interruption; content verified against scratch (size+sha256)',
        'historical_full_file_seal_available': False, 'versions': ['v3', 'v2']}
    record_before = json.loads(json.dumps(record))
    archive = tmp_path/'g'/'run'
    receipt = storage.retain_run(record, evaluations, archive, archive_code_commit='archive_only',
                                scratch_archive_root=tmp_path/'scratch'/'posthoc_staging')
    stored_receipt = json.loads((archive/'ARCHIVE_RECEIPT.json').read_text())
    stored_manifest = json.loads((archive/'RUN_MANIFEST.json').read_text())
    for item in (receipt, stored_receipt, stored_manifest):
        assert item['posthoc_evaluation_seal'] == record_before['posthoc_evaluation_seal']
    assert record == record_before and storage.inventory(source) == native_before
    assert {version: storage.inventory(root) for version, root in evaluations.items()} == evaluation_before
    assert sidecar.exists() and storage.sha256_file(sidecar) == record['posthoc_evaluation_seal']['sha256']
