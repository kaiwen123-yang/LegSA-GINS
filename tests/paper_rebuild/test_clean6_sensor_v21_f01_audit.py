"""Frozen F01 sample membership, full-file comparison and resumable retention."""
import gzip
import hashlib
import json

import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21.f01_audit import (
    FILES, selected_samples, compare_seven, archive_full, cleanup_resume,
)
from legsa_gins.paper_rebuild.clean6_canonical_v2.storage import inventory, append_json


def _samples():
    rows = [{'run_id': 'R000', 'case_id': 'C00_clean_normal', 'method_id': 'F01'}]
    rows += [{'run_id': f'R{i:03d}', 'case_id': f'D{i:03d}', 'method_id': 'F01'} for i in range(1, 541)]
    order = [rows[0]] + sorted(rows[1:], key=lambda r: hashlib.sha256(('P13_F01|' + r['case_id']).encode()).hexdigest())[:49]
    spec = {'samples': order, 'extra_audit_solver_runs': 50,
            'compared_files': list(FILES), 'evaluator_rerun': False}
    return rows, spec


def test_sample_membership_and_order_are_mechanical():
    rows, spec = _samples()
    assert selected_samples(spec, list(reversed(rows))) == spec['samples']
    spec['samples'][1], spec['samples'][2] = spec['samples'][2], spec['samples'][1]
    with pytest.raises(ValueError, match='contract differs'):
        selected_samples(spec, rows)


def _outputs(root):
    root.mkdir(parents=True)
    for index, name in enumerate(FILES):
        (root / name).write_text(f'full-rate native content {index}\nsecond unthinned row\n')
    (root / 'RUN_MANIFEST.json').write_text('{}\n')
    return {'run_id': 'RUN_TEST', 'output_root': str(root), 'output_seal': inventory(root)}


def test_full_seven_hash_gate_detects_unsampled_rows(tmp_path):
    record = _outputs(tmp_path / 'native')
    assert compare_seven(record['output_root'], record)['status'] == 'PASS'
    target = tmp_path / 'native/KF_GINS_Navresult.nav'
    target.write_text(target.read_text().replace('second unthinned row', 'modified intermediate row'))
    result = compare_seven(record['output_root'], record)
    assert result['status'] == 'FAIL'
    assert not result['sparse_NAV_used']


def test_archive_retains_all_full_files_and_reuses_receipt(tmp_path):
    record = _outputs(tmp_path / 'scratch/native')
    receipt = archive_full(record, tmp_path / 'archive', tmp_path / 'scratch/staging', 'unit-test')
    assert receipt['all_full_files_retained']
    assert not receipt['sparse_NAV_created']
    for name in FILES:
        target = tmp_path / 'archive/ATTEMPT_001' / (name + '.gz')
        with gzip.open(target, 'rb') as stream:
            assert hashlib.sha256(stream.read()).hexdigest() == record['output_seal'][name]['sha256']
    assert archive_full(record, tmp_path / 'archive', tmp_path / 'scratch/staging', 'unit-test') == receipt


def test_cleanup_resumes_after_unlink_before_checkpoint(tmp_path):
    scratch = tmp_path / 'scratch'
    root = scratch / 'owned'
    root.mkdir(parents=True)
    (root / 'a').write_text('a')
    (root / 'b').write_text('b')
    pins = inventory(root)
    ledger = tmp_path / 'cleanup.jsonl'
    append_json(ledger, {'status': 'DELETE_INTENT', 'path': str(root / 'a'), **pins['a']})
    (root / 'a').unlink()
    cleanup_resume(root, pins, ledger, scratch_root=scratch)
    assert not any(root.iterdir())
    assert any(json.loads(line)['status'] == 'DELETED_RECOVERED' for line in ledger.read_text().splitlines())
    cleanup_resume(root, pins, ledger, scratch_root=scratch)


def test_cleanup_rejects_unexplained_missing_file(tmp_path):
    root = tmp_path / 'scratch/owned'
    root.mkdir(parents=True)
    (root / 'a').write_text('a')
    pins = inventory(root)
    (root / 'a').unlink()
    with pytest.raises(ValueError, match='no exact authorized cleanup record'):
        cleanup_resume(root, pins, tmp_path / 'ledger', scratch_root=tmp_path / 'scratch')
