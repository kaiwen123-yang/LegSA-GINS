"""Synthetic controller/I/O faults only; no provider, solver, or evaluator."""
import errno
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from legsa_gins.paper_rebuild.clean6_canonical_v2 import io_recovery as io
from legsa_gins.paper_rebuild.clean6_canonical_v2 import storage
from legsa_gins.paper_rebuild.clean6_canonical_v2.archive_io import ArchiveRetryPending
from legsa_gins.paper_rebuild.manifest import sha256_file


class Monitor:
    def assert_healthy(self):
        return None


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def setup_batch(tmp_path, count):
    scratch, stage, root = tmp_path/'scratch', tmp_path/'g', tmp_path/'g/IO_RECOVERY/test'
    batch = scratch/'BATCH_009'
    output = stage/'BATCHES/BATCH_009'
    output.mkdir(parents=True)
    root.mkdir(parents=True)
    records, evaluations = [], []
    for index in range(count):
        run_id = f'RUN_{index:05d}'
        native = batch/'03_RUNS'/run_id
        write(native/'native.json', {'synthetic_test': True, 'run_id': run_id})
        records.append({'run_id': run_id, 'output_root': str(native), 'output_seal': storage.inventory(native),
                        'code_commit': io.SCIENTIFIC_COMMIT, 'terminal_status': 'COMPLETED'})
        for version in ('v3', 'v2'):
            path = batch/'12_OFFLINE_EVALUATION'/version/run_id
            write(path/'summary.json', {'synthetic_test': True})
            evaluations.append({'run_id': run_id, 'evaluator_version': version,
                'evaluation_output_root': str(path), 'summary_source': str(path/'summary.json'),
                'evaluation_status': 'COMPLETED', 'horizontal_rmse_m': 123.456})
    context = {'stage': str(stage), 'scratch': str(scratch), 'root': str(root),
               'io_fix_id': 'test', 'write_workers': 6, 'freeze': {'io_fix_code_commit': 'io-only'}}
    return records, evaluations, context, batch, output


def fake_retain(record, roots, destination, **kwargs):
    receipt = {'status': 'ARCHIVE_VERIFIED', 'run_id': record['run_id'], 'retained_files': {},
        'original_files': {role: storage.inventory(path) for role, path in [('solver', Path(record['output_root'])), *roots.items()]},
        'archive_code_commit': kwargs['archive_code_commit']}
    if kwargs.get('scratch_archive_root'):
        receipt['scratch_archive_root'] = str(kwargs['scratch_archive_root'])
        write(Path(receipt['scratch_archive_root'])/'ARCHIVE_RECEIPT.json', receipt)
    write(destination/'ARCHIVE_RECEIPT.json', receipt)
    return receipt


def exhausted(record, destination, kwargs):
    return ArchiveRetryPending(source=record['output_root'], destination=destination,
        operation='write', error=OSError(errno.ENOMEM, 'injected'), attempts=4,
        staging_root=kwargs['scratch_archive_root'])


def test_frozen_scientific_pins_cannot_be_whitelisted_implicitly():
    old = {'runner.py': 'old', 'evaluator.py': 'scientific', 'other.py': 'fixed'}
    changed = io.verify_source_changes(old, {**old, 'runner.py': 'new', 'io.py': 'new'}, {'runner.py', 'io.py'})
    assert changed == {'runner.py': {'old_sha256': 'old', 'new_sha256': 'new'},
                       'io.py': {'old_sha256': None, 'new_sha256': 'new'}}
    with pytest.raises(ValueError, match='outside I/O whitelist'):
        io.verify_source_changes(old, {**old, 'evaluator.py': 'changed'}, {'runner.py'})
    with pytest.raises(ValueError, match='missing'):
        io.verify_source_changes(old, {'runner.py': 'new', 'evaluator.py': 'scientific'}, {'runner.py'})


def test_explicit_batch_numbers_detect_gap_instead_of_count(tmp_path):
    stage, root = tmp_path/'stage', tmp_path/'io'
    write(stage/'BATCHES/BATCH_001/BATCH_RESULT.json', {'status': 'PASS', 'batch': 1})
    assert io.next_batch(stage, root) == 2
    write(stage/'BATCHES/BATCH_003/BATCH_RESULT.json', {'status': 'PASS', 'batch': 3})
    with pytest.raises(ValueError, match='Noncontiguous'):
        io.next_batch(stage, root)
    write(stage/'BATCHES/BATCH_002/BATCH_RESULT.json', {'status': 'PASS_WITH_ARCHIVE_PENDING', 'batch': 2})
    assert io.next_batch(stage, root) == 4


def test_failure_gate_is_checked_before_loading_freeze_or_touching_archive(tmp_path, monkeypatch):
    stage = tmp_path/'stage'
    gate = tmp_path/'gate.json'
    write(gate, {'status': 'FAIL_MISSING_PRIOR_EVALUATION_FULL_FILE_SEAL'})
    contract = tmp_path/'contract.yaml'; contract.write_text('stage_root: placeholder\n')
    monkeypatch.setattr(io, 'registry', lambda _: SimpleNamespace())
    monkeypatch.setattr(io, 'resolve', lambda *_: stage)
    monkeypatch.setattr(storage, 'retain_run', lambda *_a, **_k: pytest.fail('archive invoked'))
    monkeypatch.setattr(storage, 'cleanup_exact', lambda *_a, **_k: pytest.fail('cleanup invoked'))
    with pytest.raises(ValueError, match='seal coverage is not PASS'):
        io.main(['--local-config', str(tmp_path/'local'), '--contract', str(contract), '--io-fix-id', 'test',
            '--operation', 'recover-archive8', '--input-gate', str(gate), '--input-gate-sha256', sha256_file(gate)])
    assert not stage.exists()


def test_batch_end_is_one_attempt_and_success_preserves_metrics(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 1)
    calls = []
    def retain(record, roots, destination, **kwargs):
        calls.append(kwargs['retry_delays'])
        if len(calls) == 1:
            raise exhausted(record, destination, kwargs)
        return fake_retain(record, roots, destination, **kwargs)
    monkeypatch.setattr(storage, 'retain_run', retain)
    final, ev, receipts, result = io.archive_batch(records, evaluations, context=context,
        scratch_batch=batch, output=output, batch_number=9, monitor=Monitor())
    assert calls == [(2, 4, 8), ()]
    assert result['status'] == 'PASS' and not io.load_pending(context['root'])
    assert final[0]['code_commit'] == io.SCIENTIFIC_COMMIT
    assert [r['horizontal_rmse_m'] for r in ev] == [123.456, 123.456]
    assert all(Path(r['summary_source']).is_relative_to(Path(final[0]['output_root']).parent) for r in ev)
    assert not (Path(records[0]['output_root'])/'native.json').exists()
    assert receipts[0]['archive_code_commit'] == 'io-only'


def test_one_percent_pending_retains_only_pending_scratch(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 100)
    calls = []
    def retain(record, roots, destination, **kwargs):
        if record['run_id'] == 'RUN_00000':
            calls.append(kwargs['retry_delays'])
            raise exhausted(record, destination, kwargs)
        return fake_retain(record, roots, destination, **kwargs)
    monkeypatch.setattr(storage, 'retain_run', retain)
    final, _, receipts, result = io.archive_batch(records, evaluations, context=context,
        scratch_batch=batch, output=output, batch_number=9, monitor=Monitor())
    assert result['status'] == 'PASS_WITH_ARCHIVE_PENDING'
    assert result['current_batch_gate']['pending_fraction'] == .01
    assert calls == [(2, 4, 8), ()] and len(receipts) == 99
    assert final[0]['archive_status'] == 'ARCHIVE_PENDING'
    assert (Path(records[0]['output_root'])/'native.json').exists()
    assert not (Path(records[-1]['output_root'])/'native.json').exists()
    with pytest.raises(ValueError, match='zero archive pending'):
        io.collect_final_records(context['stage'], context['root'])


def test_over_one_percent_stops_after_single_batch_end_attempt(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 1)
    calls = []
    def retain(record, roots, destination, **kwargs):
        calls.append(kwargs['retry_delays'])
        raise exhausted(record, destination, kwargs)
    monkeypatch.setattr(storage, 'retain_run', retain)
    with pytest.raises(RuntimeError, match='exceeds one percent'):
        io.archive_batch(records, evaluations, context=context, scratch_batch=batch, output=output,
                         batch_number=9, monitor=Monitor())
    assert calls == [(2, 4, 8), ()]
    assert (Path(records[0]['output_root'])/'native.json').exists()
    assert len(io.load_pending(context['root'])) == 1


def test_existing_receipt_is_reused_byte_for_byte_without_repacking(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 1)
    record = records[0]
    destination = Path(context['stage'])/'RETAINED_RUNS'/record['run_id']
    roots = {v: batch/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
    receipt = fake_retain(record, roots, destination, archive_code_commit='old')
    original = (destination/'ARCHIVE_RECEIPT.json').read_bytes()
    monkeypatch.setattr(storage, 'retain_run', lambda *_a, **_k: pytest.fail('valid receipt repacked'))
    _, _, _, result = io.archive_batch(records, evaluations, context=context, scratch_batch=batch,
        output=output, batch_number=8, monitor=Monitor(), existing_receipts={record['run_id']:
            {'receipt': receipt, 'destination': str(destination),
             'prior_receipt_sha256': sha256_file(destination/'ARCHIVE_RECEIPT.json')}})
    assert result['reused_receipt_count'] == 1
    assert (destination/'ARCHIVE_RECEIPT.json').read_bytes() == original


def test_staging_cleanup_requires_receipt_members_and_preserves_unknown(tmp_path):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 1)
    prepared = batch/'ARCHIVE_STAGING/attempt'/records[0]['run_id']
    write(prepared/'member.json', {'test': True})
    receipt = {'run_id': records[0]['run_id'], 'original_files': {}, 'scratch_archive_root': str(prepared),
               'retained_files': storage.inventory(prepared)}
    job = {'record': records[0], 'scratch_batch': str(batch)}
    write(prepared/'unknown.json', {'unknown': True})
    with pytest.raises(ValueError, match='not covered'):
        io.cleanup_prepared(job, receipt, tmp_path/'g/archive', context, output, Monitor())
    assert (prepared/'member.json').exists() and (prepared/'unknown.json').exists()


def test_partial_preparation_cleanup_matches_archived_prefix_and_is_exact(tmp_path):
    records, _, context, batch, output = setup_batch(tmp_path, 1)
    partial = batch/'ARCHIVE_STAGING/attempt'/records[0]['run_id']
    complete = partial.with_name(partial.name+'.prepare_retry_01')
    write(complete/'member.json', {'payload': 'complete'})
    partial.mkdir(parents=True)
    (partial/'member.json').write_bytes((complete/'member.json').read_bytes()[:5])
    receipt = {'run_id': records[0]['run_id'], 'original_files': {}, 'scratch_archive_root': str(complete),
        'scratch_archive_roots': [str(partial), str(complete)], 'retained_files': storage.inventory(complete)}
    job = {'record': records[0], 'scratch_batch': str(batch)}
    io.cleanup_prepared(job, receipt, tmp_path/'g/archive', context, output, Monitor())
    assert not (partial/'member.json').exists() and not (complete/'member.json').exists()
    events = [json.loads(s) for s in (output/'CLEANUP_LEDGER.jsonl').read_text().splitlines()]
    assert [e['status'] for e in events] == ['DELETE_INTENT', 'DELETED']*2
    assert all(e['sha256'] and e['cleanup_role'] == 'receipt_authorized_owned_derived_staging' for e in events)


def test_pending_threshold_is_per_batch_and_exact():
    assert io.pending_gate(2, 256)['status'] == 'PASS'
    assert io.pending_gate(3, 256)['status'].startswith('STOP')
    assert io.pending_gate(0, 85)['status'] == 'PASS'
    assert io.pending_gate(1, 85)['status'].startswith('STOP')


def test_any_archive_validation_failure_preserves_whole_batch_scratch(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 2)
    def retain(record, roots, destination, **kwargs):
        if record['run_id'] == 'RUN_00001':
            raise ValueError('Injected hash mismatch')
        return fake_retain(record, roots, destination, **kwargs)
    monkeypatch.setattr(storage, 'retain_run', retain)
    with pytest.raises(ValueError, match='hash mismatch'):
        io.archive_batch(records, evaluations, context=context, scratch_batch=batch,
            output=output, batch_number=8, monitor=Monitor())
    assert all((Path(record['output_root'])/'native.json').exists() for record in records)
    assert not (output/'CLEANUP_LEDGER.jsonl').exists()
    assert not (output/'BATCH_ARCHIVE_GATE.json').exists()


def test_existing_receipts_not_cleaned_when_missing_run_stays_pending(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 2)
    record = records[0]
    destination = Path(context['stage'])/'RETAINED_RUNS'/record['run_id']
    roots = {v: batch/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
    receipt = fake_retain(record, roots, destination, archive_code_commit='old')
    def retain(record, roots, destination, **kwargs):
        raise exhausted(record, destination, kwargs)
    monkeypatch.setattr(storage, 'retain_run', retain)
    with pytest.raises(RuntimeError, match='one percent'):
        io.archive_batch(records, evaluations, context=context, scratch_batch=batch,
            output=output, batch_number=8, monitor=Monitor(), existing_receipts={record['run_id']:
                {'receipt': receipt, 'destination': str(destination),
                 'prior_receipt_sha256': sha256_file(destination/'ARCHIVE_RECEIPT.json')}})
    assert all((Path(record['output_root'])/'native.json').exists() for record in records)
    assert not (output/'CLEANUP_LEDGER.jsonl').exists()


def test_control_ledger_retry_never_duplicates_append(tmp_path, monkeypatch):
    path = tmp_path/'ledger.jsonl'
    io.append_json(path, {'first': 1})
    calls = []
    real_fsync = io.os.fsync
    def flaky_fsync(fd):
        calls.append(fd)
        if len(calls) == 1:
            raise OSError(errno.EIO, 'injected fsync after complete write')
        real_fsync(fd)
    from legsa_gins.paper_rebuild.clean6_canonical_v2 import archive_io
    monkeypatch.setattr(io.os, 'fsync', flaky_fsync)
    monkeypatch.setattr(io, 'retry_io', lambda function, **kwargs: archive_io.retry_io(
        function, **kwargs, sleep=lambda _: None))
    io.append_json(path, {'second': 2})
    assert [json.loads(line) for line in path.read_text().splitlines()] == [{'first': 1}, {'second': 2}]
    assert len(calls) == 2


def test_new_control_record_does_not_overwrite_previous_attempt(tmp_path):
    path = tmp_path/'record.json'
    io.write_json(path, {'original': True})
    with pytest.raises(FileExistsError):
        io.write_json(path, {'replacement': True})
    assert json.loads(path.read_text()) == {'original': True}


def test_real_partial_gzip_trailer_is_cleaned_after_preparation_retry(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 1)
    record = records[0]
    record.update(terminal_status='ALGORITHM_FAILURE_ALL_YAW_REJECTED', dataset_id='SYNTHETIC_INFRA_TEST')
    for row in evaluations:
        original = Path(row['summary_source'])
        renamed = original.with_name('EVALUATION_RESULT.json')
        original.rename(renamed)
        row['summary_source'] = str(renamed)
    source = Path(record['output_root'])/'payload.log'
    source.write_bytes(bytes(range(128))*3)
    record['output_seal'] = storage.inventory(Path(record['output_root']))
    original_open = Path.open
    injected = []
    partial_bytes = []
    class FaultyReader:
        def __init__(self, raw): self.raw, self.calls = raw, 0
        def __enter__(self): return self
        def __exit__(self, *args): self.raw.close()
        def read(self, size):
            self.calls += 1
            if self.calls == 2:
                injected.append(True)
                raise OSError(errno.ENOMEM, 'injected source read after one gzip block')
            return self.raw.read(size)
    def open_with_one_read_fault(path, *args, **kwargs):
        raw = original_open(path, *args, **kwargs)
        if path == source and kwargs.get('buffering') == 64 and not injected:
            return FaultyReader(raw)
        return raw
    monkeypatch.setattr(Path, 'open', open_with_one_read_fault)
    monkeypatch.setattr(storage, 'BLOCK_BYTES', 64)
    monkeypatch.setattr(storage.time, 'sleep', lambda _: None)
    original_plan = io.plan_prepared_cleanup
    def capture_plan(job, receipt, destination, context):
        failed, success = map(Path, receipt['scratch_archive_roots'])
        bad = (failed/'solver/payload.log.gz').read_bytes()
        good = (success/'solver/payload.log.gz').read_bytes()
        partial_bytes.append(bad)
        assert bad != good[:len(bad)]  # partial-input gzip CRC/ISIZE trailer
        return original_plan(job, receipt, destination, context)
    monkeypatch.setattr(io, 'plan_prepared_cleanup', capture_plan)
    _, _, receipts, result = io.archive_batch(records, evaluations, context=context,
        scratch_batch=batch, output=output, batch_number=9, monitor=Monitor())
    assert result['status'] == 'PASS' and len(injected) == 1 and partial_bytes
    assert len(receipts[0]['scratch_archive_roots']) == 2
    for path in receipts[0]['scratch_archive_roots']:
        assert not list(Path(path).rglob('*.*'))
    assert not source.exists()
    assert (output/'BATCH_ARCHIVE_GATE.json').is_file()
    assert (output/'PREPARED_CLEANUP_PLAN.json').is_file()


def test_bad_staging_plan_fails_before_any_native_cleanup(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 1)
    def retain(record, roots, destination, **kwargs):
        receipt = fake_retain(record, roots, destination, **kwargs)
        write(Path(receipt['scratch_archive_root'])/'unregistered.json', {'keep': True})
        return receipt
    monkeypatch.setattr(storage, 'retain_run', retain)
    with pytest.raises(ValueError, match='whitelist'):
        io.archive_batch(records, evaluations, context=context, scratch_batch=batch,
            output=output, batch_number=9, monitor=Monitor())
    assert (Path(records[0]['output_root'])/'native.json').exists()
    assert not (output/'CLEANUP_LEDGER.jsonl').exists()
    assert not (output/'BATCH_ARCHIVE_GATE.json').exists()


def posthoc_fixture(tmp_path):
    solver, evaluator = tmp_path/'solver.json', tmp_path/'evaluator.json'
    write(solver, []); write(evaluator, [])
    rows = [{'run_id': f'R{i}', 'status': 'PASS', 'evaluation_full_file_seal_missing': []} for i in range(255)]
    files = {v: {'summary.json': {'sha256': 'synthetic_metadata_pin', 'size_bytes': 1}} for v in ('v3', 'v2')}
    rows.append({'run_id': 'RUN_01963', 'status': 'MISSING_PRIOR_SEAL', 'evaluation_full_file_seal_missing': ['v3/summary.json', 'v2/summary.json'],
                 'current_scratch_inventory': files})
    old = {'status': 'FAIL_MISSING_PRIOR_EVALUATION_FULL_FILE_SEAL', 'solver_count': 256, 'evaluation_count': 512,
        'solver_records_sha256': sha256_file(solver), 'evaluation_records_sha256': sha256_file(evaluator),
        'existing_receipt_count': 255, 'missing_run_id': 'RUN_01963', 'solver_seal_status': 'PASS',
        'hash_mismatch_count': 0, 'current_inventory_is_historical_seal': False, 'evaluation_seal_status': 'UNAVAILABLE_FOR_RUN_01963',
        'missing_prior_evaluation_seals': [{'run_id': 'RUN_01963', 'files': ['v3/summary.json', 'v2/summary.json']}], 'runs': rows}
    old_path = tmp_path/'old.json'; write(old_path, old)
    old_pin = {'path': str(old_path), 'sha256': sha256_file(old_path)}
    decision = {'approved': True, 'posthoc_evaluation_seal_run_id': 'RUN_01963',
                'posthoc_evaluation_versions': ['v3', 'v2'], 'posthoc_seal_annotation': io.POSTHOC_LABEL}
    contract = tmp_path/'contract.yaml'
    contract.write_text(yaml.safe_dump({'io_recovery_authorization': {'human_decision_20260912': decision}}))
    seal = tmp_path/'seal.json'
    write(seal, {'status': 'SEALED_POST_HOC_AFTER_ARCHIVAL_INTERRUPTION', 'run_id': 'RUN_01963',
        'annotation': io.POSTHOC_LABEL, 'historical_full_file_seal_available': False, 'versions': ['v3', 'v2'],
        'files': files, 'original_audit': old_pin})
    acceptance = copy.deepcopy(old)
    acceptance.update(status='ACCEPTED_AUTHORIZED_POSTHOC_SEAL', evaluation_seal_status='ACCEPTED_AUTHORIZED_POSTHOC_SEAL',
        original_audit=old_pin, posthoc_evaluation_seal={'path': str(seal), 'sha256': sha256_file(seal),
            'run_id': 'RUN_01963', 'versions': ['v3', 'v2'], 'annotation': io.POSTHOC_LABEL, 'historical_full_file_seal_available': False},
        human_authorization={'contract_path': str(contract), 'contract_sha256': sha256_file(contract),
                             'decision_key': 'io_recovery_authorization.human_decision_20260912'})
    path = tmp_path/'accepted.json'; write(path, acceptance)
    return path, solver, evaluator, decision, old


def test_authorized_posthoc_acceptance_preserves_original_gap(tmp_path):
    path, solver, evaluator, decision, original = posthoc_fixture(tmp_path)
    result = io.verify_recovery_gate(path, sha256_file(path), solver, evaluator, authorization=decision)
    assert result['status'] == 'ACCEPTED_AUTHORIZED_POSTHOC_SEAL'
    assert result['missing_prior_evaluation_seals'] == original['missing_prior_evaluation_seals']
    assert result['runs'] == original['runs']
    assert result['posthoc_evaluation_seal']['historical_full_file_seal_available'] is False
    with pytest.raises(ValueError, match='Explicit approved'):
        io.verify_recovery_gate(path, sha256_file(path), solver, evaluator)
    altered = json.loads(path.read_text()); altered['missing_prior_evaluation_seals'] = []
    write(path, altered)
    with pytest.raises(ValueError, match='concealed'):
        io.verify_recovery_gate(path, sha256_file(path), solver, evaluator, authorization=decision)


def test_only_registered_scientific_stop_categories_are_stops():
    for kind in io.SCIENTIFIC_STOP_KINDS:
        assert io.classify_controller_failure(io.ScientificStop(kind, 'evidence'))['status'] == 'SCIENTIFIC_STOP'
    for error in (FileNotFoundError('seal metadata missing'), KeyError('runtime_seconds'), ValueError('path map'), RuntimeError('RSS')):
        assert io.classify_controller_failure(error)['status'] == 'BOOKKEEPING_REPAIR'
    with pytest.raises(io.ScientificStop, match='nonzero'):
        io.check_science_terminals([{'run_id': 'r', 'exit_code': 134, 'terminal_status': 'FAILED_TECHNICAL'}])
    io.check_science_terminals([{'run_id': 'r', 'exit_code': 134, 'terminal_status': 'ALGORITHM_FAILURE_ALL_YAW_REJECTED'}])
    with pytest.raises(io.ScientificStop, match='nonfinite'):
        io.check_science_terminals([], [{'run_id': 'r', 'evaluation_status': 'COMPLETED', 'horizontal_rmse_m': float('nan')}])
    with pytest.raises(io.ScientificStop, match='failed'):
        io.check_science_terminals([], [{'run_id': 'r', 'evaluation_status': 'FAILED_EVALUATOR', 'evaluation_invoked': True,
                                        'evaluator_process_resources': {'exit_code': 1}}])


def test_native_exit_zero_wrapper_repair_preserves_native_bytes(tmp_path):
    native = tmp_path/'scratch/native'
    for name in ('RUN_MANIFEST.json', 'KF_GINS_Navresult.nav', 'KF_GINS_STD.txt'):
        write(native/name, {'synthetic_infrastructure': True})
    before = storage.inventory(native)
    record = {'run_id': 'r', 'output_root': str(native), 'exit_code': 0,
              'terminal_status': 'FAILED_TECHNICAL', 'failure': 'missing progress metadata'}
    repaired = io.repair_native_record(record, tmp_path/'stage', before_evaluation=True)
    assert repaired['terminal_status'] == 'COMPLETED' and repaired['original_terminal_status'] == 'FAILED_TECHNICAL'
    assert repaired['runtime_seconds'] is None and repaired['runtime_measurement_status'] == 'UNAVAILABLE'
    for name, pin in before.items():
        assert sha256_file(native/name) == pin['sha256']
    assert json.loads((native/'OUTPUT_SEAL.json').read_text())['status'] == 'SEALED_BEFORE_EVALUATION'
    assert (tmp_path/'stage/BATCH_LEDGER.notes').is_file()


def test_exact_wave_group_recovery_uses_no_scientific_calls(tmp_path, monkeypatch):
    records, evaluations, context, batch, output = setup_batch(tmp_path, 2)
    write(output/'SOLVER_GROUP_0.json', records)
    write(output/'EVALUATION_WAVE_0001.json', evaluations[:2])
    for row in evaluations[2:]:
        write(Path(row['evaluation_output_root'])/'EVALUATION_RESULT.json', row)
    from legsa_gins.paper_rebuild.clean6_canonical_v2 import runner, evaluation
    monkeypatch.setattr(runner, 'run_group', lambda *_a, **_k: pytest.fail('solver repeated'))
    monkeypatch.setattr(evaluation, 'one_evaluation', lambda *_a, **_k: pytest.fail('evaluator repeated'))
    recovered, rows = io.load_existing_batch_terminals(context['stage'], context['scratch'], 9,
        expected_run_ids=[r['run_id'] for r in records])
    assert [r['run_id'] for r in recovered] == [r['run_id'] for r in records]
    assert len(rows) == 4 and all(r['horizontal_rmse_m'] == 123.456 for r in rows)


def test_bookkeeping_note_is_also_in_main_batch_ledger_notes_field(tmp_path):
    io.bookkeeping_note(tmp_path, 'restore_path_map', 'restored existing metadata', batch=8, run_id='RUN_01963')
    detail = json.loads((tmp_path/'BATCH_LEDGER.notes').read_text())
    event = json.loads((tmp_path/'BATCH_LEDGER.jsonl').read_text())
    assert event['event'] == 'BOOKKEEPING_REPAIRED'
    assert event['notes'] == [detail]
    assert event['batch'] == 8 and event['run_id'] == 'RUN_01963'
    assert detail['scientific_code_commit'] == io.SCIENTIFIC_COMMIT


def test_evaluator_exit_zero_then_wrapper_keyerror_is_bookkeeping_only():
    row = {'run_id': 'r', 'evaluation_status': 'FAILED_EVALUATOR', 'evaluation_invoked': True,
           'evaluator_process_resources': {'exit_code': 0}, 'failure_type': 'KeyError', 'failure_message': 'runtime_seconds'}
    before = copy.deepcopy(row)
    io.check_science_terminals([], [row])
    assert row == before and row['evaluation_status'] == 'FAILED_EVALUATOR'
    row.pop('evaluator_process_resources')
    io.check_science_terminals([], [row])  # missing evidence does not fabricate success


@pytest.mark.parametrize('evidence', [{'evaluator_process_resources': {'exit_code': 2}},
                                     {'evaluator_audit': {'exit_code': 137}},
                                     {'failure_type': 'RuntimeError', 'failure_message': 'evaluator_returncode=1; stderr tail: failed'}])
def test_evaluator_actual_nonzero_is_scientific_stop(evidence):
    with pytest.raises(io.ScientificStop) as caught:
        io.check_science_terminals([], [{'run_id': 'r', 'evaluation_invoked': True,
            'evaluation_status': 'FAILED_EVALUATOR', **evidence}])
    assert caught.value.kind == 'EVALUATOR_FAILURE_OR_NONFINITE'


def test_evaluator_nonfinite_remains_scientific_even_with_success_exit():
    with pytest.raises(io.ScientificStop):
        io.check_science_terminals([], [{'run_id': 'r', 'evaluation_status': 'FAILED_EVALUATOR',
            'evaluation_invoked': True, 'evaluator_process_resources': {'exit_code': 0}, 'failure_message': 'Nonfinite evaluator output'}])


@pytest.mark.parametrize('remove_all_native,completion_recorded,partial_resolution',
                         [(False, True, False), (True, True, False), (False, False, True)])
def test_receipt_cleanup_recovery_never_rearchives_partial_sources(tmp_path, monkeypatch,
        remove_all_native, completion_recorded, partial_resolution):
    records, evaluations, context, batch, original_output = setup_batch(tmp_path, 1)
    record = records[0]
    native = Path(record['output_root'])
    write(native/'extra.json', {'synthetic_extra': True})
    record['output_seal'] = storage.inventory(native)
    destination = Path(context['stage'])/'RETAINED_RUNS'/record['run_id']/'successful_attempt'
    staged = batch/'ARCHIVE_STAGING/successful_attempt'/record['run_id']
    roots = {v: batch/'12_OFFLINE_EVALUATION'/v/record['run_id'] for v in ('v3', 'v2')}
    receipt = fake_retain(record, roots, destination, archive_code_commit='io-only', scratch_archive_root=staged)
    write(staged/'member.json', {'synthetic_staging': True})
    receipt['retained_files'] = {'member.json': storage.inventory(staged)['member.json']}
    receipt['scratch_archive_roots'] = [str(staged)]
    write(staged/'ARCHIVE_RECEIPT.json', receipt)
    write(destination/'ARCHIVE_RECEIPT.json', receipt)
    job = {'record': record, 'evaluations': evaluations, 'scratch_batch': str(batch), 'batch': 9}
    plan = io.plan_prepared_cleanup(job, receipt, destination, context)
    write(original_output/'PREPARED_CLEANUP_PLAN.json', {record['run_id']: plan})
    final, rows = io._relocate(record, evaluations, destination, batch)
    resolved = Path(context['root'])/'RESOLVED_RUNS'/record['run_id']
    write(resolved/'RUN_RECORD.json', final)
    kept = (resolved/'RUN_RECORD.json').read_bytes()
    if not partial_resolution:
        write(resolved/'EVALUATION_RECORDS.json', rows)
        write(resolved/'RECEIPT_REFERENCE.json', {'path': str(destination/'ARCHIVE_RECEIPT.json'),
                                               'sha256': sha256_file(destination/'ARCHIVE_RECEIPT.json')})
    io.append_json(Path(context['root'])/'ARCHIVE_IO_LEDGER.jsonl', {'status': 'ARCHIVED',
        'run_id': record['run_id'], 'destination': str(destination), 'batch': 9})
    io.append_json(Path(context['root'])/'ARCHIVE_PENDING_LEDGER.jsonl', {'status': 'ARCHIVE_PENDING',
        'run_id': record['run_id'], 'job': job})
    names = list(receipt['original_files']['solver']) if remove_all_native else ['native.json']
    for name in names:
        pin = receipt['original_files']['solver'][name]
        io.append_json(original_output/'CLEANUP_LEDGER.jsonl', {'status': 'DELETE_INTENT', 'path': str(native/name), **pin})
        (native/name).unlink()
        if completion_recorded:
            io.append_json(original_output/'CLEANUP_LEDGER.jsonl', {'status': 'DELETED', 'path': str(native/name), **pin})
    monkeypatch.setattr(storage, 'retain_run', lambda *_a, **_k: pytest.fail('verified archive repeated'))
    reg = SimpleNamespace(clean_root=Path(context['stage']))
    result = io.recover_archive_batch(context, reg, 9, records=records, evaluations=evaluations)
    assert result['status'] == 'PASS' and result['solver_calls'] == result['evaluator_calls'] == 0
    assert not list(native.rglob('*.*'))
    assert all(not list(path.rglob('*.*')) for path in roots.values())
    assert not list(staged.rglob('*.*')) and not io.load_pending(context['root'])
    assert (resolved/'RUN_RECORD.json').read_bytes() == kept
    assert (resolved/'EVALUATION_RECORDS.json').is_file() and (resolved/'RECEIPT_REFERENCE.json').is_file()
    second = io.recover_archive_batch(context, reg, 9, records=records, evaluations=evaluations)
    assert second['status'] == 'PASS'
    second_output = Path(second['run_records_path']).parent
    assert not (second_output/'CLEANUP_LEDGER.jsonl').exists()  # already reconciled, no duplicate delete
