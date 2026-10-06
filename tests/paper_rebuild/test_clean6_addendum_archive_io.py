"""Storage accounting and zero-repeat archive continuation invariants."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.clean6_addendum import archive_io_continuation as io
from legsa_gins.paper_rebuild.clean6_addendum import runner, runtime
from legsa_gins.paper_rebuild.clean6_canonical_v2.storage import inventory


def test_single_stat_scan_matches_old_accounting_and_rejects_symlink(tmp_path):
    root = tmp_path/'stage'
    (root/'nested').mkdir(parents=True)
    (root/'one').write_bytes(b'a'*1025)
    (root/'nested/two').write_bytes(b'b'*4097)
    totals, details, counts = io.scan(root)
    assert totals == runner.owned_sizes(root)
    assert counts == {'fresh_stat_count': 3, 'cached_file_count': 0}
    assert set(details) == {'one', 'nested/two'}
    (root/'link').symlink_to(root/'one')
    with pytest.raises(ValueError, match='Symlink'):
        io.scan(root)


def test_immutable_cache_skips_payload_but_measures_mutable_and_cleaned_scratch(tmp_path):
    stage, scratch = tmp_path/'stage', tmp_path/'scratch'
    closed = stage/'closed'
    (closed/'nested').mkdir(parents=True)
    scratch.mkdir()
    (closed/'nested/payload').write_bytes(b'a'*8193)
    (stage/'live.jsonl').write_bytes(b'first\n')
    (scratch/'temporary').write_bytes(b'local')
    counter = io.SealedStorageCounter(stage, scratch)
    counter.register(closed, {'policy': 'synthetic closed test fixture'})
    expected = runner.owned_sizes(stage, scratch)
    got = dict.fromkeys(io.TOTAL_KEYS, 0)
    for root in (stage, scratch):
        values, _, counts = io.scan(root, counter.cached)
        for key in got:
            got[key] += values[key]
        if root == stage:
            assert counts['cached_file_count'] == 1
            assert counts['fresh_stat_count'] == 2
    assert got == expected
    (stage/'live.jsonl').write_bytes(b'first\nsecond\n')
    (scratch/'temporary').unlink()
    contract = {'storage': {'peak_limit_bytes': 250_000_000_000}}
    before_ledger = runner.owned_sizes(stage, scratch)
    result = counter.gate(contract, stage, scratch, tmp_path/'ledger.jsonl', reconcile=True)
    assert result == before_ledger
    assert counter.reconcile()['reconciled_immutable_files'] == 1


def test_sealed_cache_detects_root_changes_and_inplace_change_on_reconciliation(tmp_path):
    stage, scratch = tmp_path/'stage', tmp_path/'scratch'
    closed = stage/'closed'
    (closed/'nested').mkdir(parents=True)
    scratch.mkdir()
    payload = closed/'nested/file'
    payload.write_bytes(b'a')
    counter = io.SealedStorageCounter(stage, scratch)
    counter.register(closed, {'policy': 'synthetic closed test fixture'})
    payload.write_bytes(b'changed without changing top directory')
    with pytest.raises(ValueError, match='reconciliation mismatch'):
        counter.reconcile()
    (closed/'new').write_bytes(b'root changed')
    prior = counter.cached[closed]['root_stamp']
    os.utime(closed, ns=(prior[3]+1_000_000_000, prior[3]+1_000_000_000))
    with pytest.raises(ValueError, match='Closed cached directory changed'):
        io.scan(stage, counter.cached)


def test_archive_receipt_is_counted_and_storage_cap_is_not_weakened(tmp_path):
    stage, scratch = tmp_path/'stage', tmp_path/'scratch'
    root = stage/'RETAINED_RUNS/ADD_RUN_00001'
    root.mkdir(parents=True)
    scratch.mkdir()
    (root/'data').write_bytes(b'a'*4097)
    receipt = {'status': 'ARCHIVE_VERIFIED', 'run_id': root.name, 'archive_root': str(root),
               'retained_files': inventory(root)}
    (root/'ARCHIVE_RECEIPT.json').write_text(json.dumps(receipt))
    counter = io.SealedStorageCounter(stage, scratch)
    counter.discover_sealed()
    assert counter.cached[root]['totals'] == runner.owned_sizes(root)
    assert counter.cached[root]['totals']['file_count'] == 2
    totals = runner.owned_sizes(stage, scratch)
    contract = {'storage': {'peak_limit_bytes': max(totals['logical_bytes'], totals['allocated_bytes'])}}
    with pytest.raises(ValueError, match='storage cap reached'):
        counter.gate(contract, stage, scratch, tmp_path/'ledger.jsonl')
    partial = stage/'RETAINED_RUNS/ADD_RUN_00002'
    partial.mkdir()
    (partial/'data').write_text('incomplete')
    with pytest.raises(ValueError, match='Unsealed output'):
        counter.discover_sealed()


def test_archive_continuation_reuses_54_receipts_without_science_or_derivation(tmp_path, monkeypatch):
    stage, scratch, target = tmp_path/'stage', tmp_path/'scratch', tmp_path/'continuation'
    records = [{'run_id': 'ADD_RUN_'+str(i+1).zfill(5)} for i in range(99)]
    evaluations = [{'run_id': r['run_id'], 'evaluator_version': version}
                   for r in records for version in ('v3', 'v2')]
    existing = {r['run_id']: {'status': 'ARCHIVE_VERIFIED', 'run_id': r['run_id']}
                for r in records[:54]}
    calls = []

    def forbidden(*args, **kwargs):
        raise AssertionError('No completed science or derived metrics may be repeated')

    for module, names in ((runtime, ('solve', 'evaluate', 'finish_evaluation')),
                          (runner, ('provider_task', 'provider_child'))):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)

    def retain(record, roots, destination, **kwargs):
        assert record['run_id'] not in existing
        calls.append(('archive', record['run_id']))
        return {'status': 'ARCHIVE_VERIFIED', 'run_id': record['run_id']}

    def resolve(receipts, rows):
        assert len(receipts) == 99 and rows == evaluations
        assert all(receipts[i][2] is existing[records[i]['run_id']] for i in range(54))
        return records, rows

    monkeypatch.setattr(io, 'retain_run', retain)
    monkeypatch.setattr(runner, 'resolve_archived_records', resolve)
    monkeypatch.setattr(runner, 'cleanup_batch', lambda *a: calls.append(('cleanup', len(a[0]))))
    monkeypatch.setattr(io, 'inventory', lambda root: {})
    counter = SimpleNamespace(gate=lambda *a, **kw: None)
    output = io.complete_archive_batch(records, evaluations, existing, {}, stage, scratch, target,
                                      {'code_commit': 'new'}, object(), counter)
    assert output == (records, evaluations)
    assert len(calls) == 46 and calls[-1] == ('cleanup', 99)
    assert [value for kind, value in calls[:-1]] == [r['run_id'] for r in records[54:]]
    result = json.loads((target/'BATCHES/BATCH_001/BATCH_COMPLETE.json').read_text())
    assert result['native_calls_this_continuation_batch'] == 0
    assert result['evaluator_calls_this_continuation_batch'] == 0
    assert result['derived_metric_recomputations'] == 0
    assert result['existing_verified_archives_reused'] == 54 and result['new_archives'] == 45


def test_future_batch_cleanup_cannot_precede_cache_reconciliation(tmp_path):
    calls = []
    def gate(*args, **kwargs):
        assert kwargs['reconcile'] is True
        calls.append('reconcile')
    def cleanup(*args):
        calls.append('original_exact_cleanup')
    wrapped = io.protected_cleanup(SimpleNamespace(gate=gate), {}, tmp_path/'stage', tmp_path/'scratch', cleanup)
    wrapped([], tmp_path/'report', tmp_path/'scratch', object())
    assert calls == ['reconcile', 'original_exact_cleanup']
    def failure(*args, **kwargs):
        raise ValueError('immutable snapshot changed')
    blocked = io.protected_cleanup(SimpleNamespace(gate=failure), {}, tmp_path/'stage', tmp_path/'scratch', cleanup)
    with pytest.raises(ValueError, match='immutable snapshot changed'):
        blocked([], tmp_path/'report', tmp_path/'scratch', object())
    assert calls == ['reconcile', 'original_exact_cleanup']
