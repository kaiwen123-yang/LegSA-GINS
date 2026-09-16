"""Access-boundary tests; synthetic fixtures never enter real-data tables."""
import csv
from pathlib import Path
from types import SimpleNamespace

from legsa_gins.paper_rebuild.hext import execution


def test_raw_checkpoint_never_hashes_trace(tmp_path, monkeypatch):
    raw = tmp_path / 'raw'
    fix = raw / 'receiver'
    fix.mkdir(parents=True)
    names = ['trace.csv'] + [f'sensor{i}.csv' for i in range(18)]
    paths = [fix / name for name in names] + [raw / 'receiver.bag', raw / 'receiver.fpl', raw / 'body.txt']
    for path in paths:
        path.write_text('raw fixture\n')
    lock = tmp_path / 'lock.csv'
    with lock.open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=['relative_path', 'size_bytes', 'sha256'])
        writer.writeheader()
        writer.writerows(dict(relative_path=p.relative_to(raw), size_bytes=p.stat().st_size, sha256='pin') for p in paths)
    trace = fix / 'trace.csv'
    def guarded_hash(path):
        assert Path(path) != trace, 'trace must only be read inside evaluator child'
        return 'pin'
    monkeypatch.setattr(execution, 'sha256_file', guarded_hash)
    seq = SimpleNamespace(sequence_id='FIXTURE', raw_root=raw, clean_root=tmp_path / 'clean', code_root=tmp_path / 'code',
                          hext_scratch=tmp_path / 'scratch', gnss1_raw=fix / 'sensor0.csv', go2_body=raw / 'body.txt',
                          trace=trace, trace_sha256='pin', hash_lock=lock, hash_lock_sha256='pin')
    receipt = execution.raw_checkpoint(seq, tmp_path / 'receipt.json')
    assert receipt['passed'] and receipt['file_count'] == 22
    assert receipt['payload_hash_count'] == 21
    assert receipt['trace_payload_hash_count'] == 0


def test_archive_is_exclusive_and_roundtrip_verified(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'payload').write_bytes(b'unchanged scientific bytes\x00\n')
    dest = tmp_path / 'archive'
    result = execution.archive_batch(source, dest, tmp_path / 'ledger.jsonl', 'fixture')
    assert result['file_count'] == 1 and result['failures'] == result['pending'] == 0
    assert (dest / 'payload').read_bytes() == (source / 'payload').read_bytes()
    import pytest
    with pytest.raises(FileExistsError):
        execution.archive_batch(source, dest, tmp_path / 'ledger.jsonl', 'fixture')
