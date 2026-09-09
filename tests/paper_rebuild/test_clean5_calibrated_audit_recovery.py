"""Audit-classification fixtures only; no real calibration or runtime products."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.clean5_calibrated import audit_recovery as recovery


def digest(value):
    return hashlib.sha256(value).hexdigest()


@pytest.fixture
def review_fixture(tmp_path, monkeypatch):
    source, raw, clean = tmp_path/'source', tmp_path/'raw', tmp_path/'clean'
    root = clean/'calibration'
    root.mkdir(parents=True)
    source.mkdir()
    raw.mkdir()
    relative_paths = ['src/trace_first.py', 'src/trace_second.py', 'metadata/trace_note.md']
    blobs = {}
    for index, relative in enumerate(relative_paths):
        path = source/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        blobs[relative] = ('Frozen metadata fixture '+str(index)+'\n').encode()
        path.write_bytes(blobs[relative])
    monkeypatch.setattr(recovery, 'METADATA_PINS', {digest(p.encode()): digest(blobs[p]) for p in relative_paths})
    contract = {'calibration': {'inputs': {'body': {'path': '<RAW_ROOT>/allowed_input.txt', 'sha256': 'f'*64}}}}
    cp = source/recovery.CONTRACT
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(yaml.safe_dump(contract))
    blobs[recovery.CONTRACT] = cp.read_bytes()
    script = source/'scripts/paper_rebuild/clean5_review_calibration_audit.py'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('# audit entry fixture\n')
    log = root/'CALIBRATION_OPENAT.strace'
    prefix = str(source)
    lines = [f'{recovery.METADATA_PID} execve("/usr/bin/git", ["git", "status", "--porcelain=v1", "--untracked-files=all"], 0x0 /* 1 var */) = 0']
    lines += [f'{recovery.METADATA_PID} openat(AT_FDCWD<{prefix}>, "{relative}", O_RDONLY|O_CLOEXEC) = 3<{source/relative}>'
              for relative in relative_paths]
    log.write_text('\n'.join(lines)+'\n')
    artifact = root/'OPAQUE_TABLE.csv'
    artifact.write_text('opaque scientific artifact; do not parse\n')
    model = root/'CLEAN5_CALIBRATED_SENSOR_MODEL.yaml'
    model.write_text('opaque model artifact; do not parse\n')
    child = {'status': 'CALIBRATION_COMPLETE', 'code_commit': recovery.SOURCE_COMMIT,
             'contract_sha256': digest(cp.read_bytes()), 'tables': {artifact.name: digest(artifact.read_bytes())},
             'model_sha256': digest(model.read_bytes()), 'process_source_sha256': {},
             'input_sha256': contract['calibration']['inputs']}
    old_audit = {'exit_code': 0, 'pass': False, 'strace_sha256': digest(log.read_bytes()),
                 'undeclared_protected_open_records': [], 'write_scope': {'pass': True},
                 'forbidden_open_counts': {'trace': 3, 'bag': 0, 'fpl': 0}}
    records = {'CALIBRATION_CHILD_TERMINAL.json': child, 'CALIBRATION_EXECUTION_AUDIT.json': old_audit,
               'CALIBRATION_FAILURE.json': {'status': 'FAILED'}, 'CALIBRATION_STARTED.json': {'status': 'STARTED'}}
    for filename, value in records.items():
        (root/filename).write_text(json.dumps(value))
    monkeypatch.setattr(recovery, 'ORIGINAL_PINS', {name: digest((root/name).read_bytes()) for name in recovery.ORIGINAL_PINS})
    def fake_git(where, *args):
        assert Path(where) == source
        if args == ('rev-parse', 'HEAD'):
            return (recovery.SOURCE_COMMIT+'\n').encode()
        relative = args[1].split(':', 1)[1]
        if args[0] == 'show':
            return blobs[relative]
        if args[0] == 'rev-parse':
            return (hashlib.sha1(blobs[relative]).hexdigest()+'\n').encode()
        raise AssertionError(args)
    monkeypatch.setattr(recovery, '_git', fake_git)
    return dict(calibration_root=root, source_code_root=source, review_code_root=source,
                raw_root=raw, clean_root=clean), relative_paths


def classify_fixture(fixture, extra=()):
    args, _ = fixture
    records = recovery.attributed_open_records(args['calibration_root']/'CALIBRATION_OPENAT.strace', args['source_code_root'])
    kwargs = {k: args[k] for k in ('calibration_root', 'source_code_root', 'raw_root', 'clean_root')}
    return recovery.corrected_classification(records+list(extra), input_paths=[args['raw_root']/'allowed_input.txt'], **kwargs)


def test_exact_three_git_metadata_exceptions(review_fixture):
    audit = classify_fixture(review_fixture)
    assert audit['pass']
    assert len(audit['metadata_exception_records']) == 3
    assert len(audit['legacy_markdown_exception_records']) == 1
    assert audit['forbidden_open_counts'] == {'trace': 0, 'bag': 0, 'fpl': 0}


@pytest.mark.parametrize('changed', ['pid', 'argv', 'executable', 'path', 'write'])
def test_different_owner_command_path_or_write_cannot_be_exempted(review_fixture, changed):
    args, _ = review_fixture
    records = recovery.attributed_open_records(args['calibration_root']/'CALIBRATION_OPENAT.strace', args['source_code_root'])
    if changed == 'pid':
        records[2]['pid'] += 1
    elif changed == 'argv':
        records[2]['successful_exec'] = {'executable': '/usr/bin/git', 'argv': ['git', 'show']}
    elif changed == 'executable':
        records[2]['successful_exec'] = {'executable': '/usr/bin/python3', 'argv': recovery.METADATA_ARGV}
    elif changed == 'path':
        records[2]['path'] = str(args['source_code_root']/'metadata/trace_other.md')
    else:
        records[2]['flags'] = 'O_RDWR|O_CLOEXEC'
    kwargs = {k: args[k] for k in ('calibration_root', 'source_code_root', 'raw_root', 'clean_root')}
    with pytest.raises(ValueError, match='metadata'):
        recovery.corrected_classification(records, input_paths=[], **kwargs)


@pytest.mark.parametrize('name', ['trace_reference.csv', 'trace_reference.csv.gz', 'trace.csv.gz',
                                 'trace_reference.py', 'archive.bag', 'archive.bag.gz', 'archive.fpl', 'archive.fpl.gz'])
def test_raw_data_is_forbidden_even_when_git_opens_it(review_fixture, name):
    args, _ = review_fixture
    path = args['raw_root']/name
    row = {'path': str(path), 'lexical_path': str(path), 'flags': 'O_RDONLY', 'return_code': 3,
           'pid': recovery.METADATA_PID, 'successful_exec': {'executable': '/usr/bin/git', 'argv': recovery.METADATA_ARGV}}
    audit = classify_fixture(review_fixture, [row])
    assert not audit['pass'] and audit['forbidden_open_records'] and audit['undeclared_protected_open_records']


@pytest.mark.parametrize('name', ['CALIBRATION_OPENAT.strace', 'CALIBRATION_CHILD_TERMINAL.json',
                                 'CALIBRATION_EXECUTION_AUDIT.json', 'CALIBRATION_FAILURE.json',
                                 'CLEAN5_CALIBRATED_SENSOR_MODEL.yaml', 'OPAQUE_TABLE.csv'])
def test_any_original_hash_change_fails_without_acceptance(review_fixture, name):
    args, _ = review_fixture
    path = args['calibration_root']/name
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError, match='(pin changed|hash mismatch)'):
        recovery.review_existing(**args)
    assert not (args['calibration_root']/'AUDIT_CLASSIFICATION_REVIEW').exists()


def test_metadata_file_and_frozen_blob_must_match(review_fixture):
    args, relative = review_fixture
    (args['source_code_root']/relative[2]).write_text('Changed metadata content\n')
    with pytest.raises(ValueError, match='file/blob mismatch'):
        recovery.review_existing(**args)


def test_review_never_calls_calibration_or_loader_and_preserves_all_originals(review_fixture, monkeypatch):
    from legsa_gins.paper_rebuild.clean5_calibrated import calibration, calibration_runner
    def forbidden(*args, **kwargs):
        raise AssertionError('No calibration/loader/worker call is permitted during audit review')
    monkeypatch.setattr(calibration, 'calibrate_arrays', forbidden)
    monkeypatch.setattr(calibration_runner, 'calibrate_arrays', forbidden)
    monkeypatch.setattr(calibration_runner, 'load_arrays', forbidden)
    monkeypatch.setattr(calibration_runner, 'worker', forbidden)
    args, _ = review_fixture
    root = args['calibration_root']
    original = {p.name: p.read_bytes() for p in root.iterdir()}
    result = recovery.review_existing(**args)
    assert result['status'] == 'PASS_CORRECTED_AUDIT_NO_RECOMPUTATION'
    assert result['calibration_count'] == 1 and result['calibration_computation_count_this_review'] == 0
    assert {name: (root/name).read_bytes() for name in original} == original
    output = root/'AUDIT_CLASSIFICATION_REVIEW'
    assert {p.name for p in output.iterdir()} == {'CALIBRATION_ACCEPTANCE.json', 'CALIBRATION_AUDIT_CLASSIFICATION_REVIEW.json'}
    with pytest.raises(ValueError, match='output exists'):
        recovery.review_existing(**args)
