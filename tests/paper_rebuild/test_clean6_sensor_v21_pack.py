"""Synthetic-only tests for v2.1 source-pinned publication packaging."""
import csv
import gzip
import hashlib
import io
import json
import zipfile

import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21 import pack as p


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(writer):
    return writer.close({'passed': True, 'protocol_id': p.PROTOCOL})


def test_lossless_full_table_gzip_and_publication_package_reader(tmp_path):
    from legsa_gins.paper_rebuild.publication.protocol_v2_data import Package
    source = tmp_path/'all.csv'
    source.write_bytes(b'time,unfamiliar_metric,another_metric\r\n1,3.140000,NA\r\n2,-0.000000,7\r\n')
    writer = p.PackageWriter(tmp_path/'small.zip', synthetic=True)
    writer.file(source, 'tables/all.csv.gz', sha(source), source_protocol=p.PROTOCOL, compress_csv=True)
    writer.generated_json_gzip('indices/full.json.gz', [{'metric': 'ALL', 'items': [1, 2]}])
    result = close(writer)
    assert result['passed']
    with zipfile.ZipFile(writer.path) as archive:
        assert gzip.decompress(archive.read('tables/all.csv.gz')) == source.read_bytes()
        assert json.loads(gzip.decompress(archive.read('indices/full.json.gz')))[0]['items'] == [1, 2]
    package = Package(writer.path)
    assert list(package.table('tables/all.csv').columns) == ['time', 'unfamiliar_metric', 'another_metric', '_source_csv_row']
    with pytest.raises(FileExistsError):
        p.PackageWriter(writer.path, synthetic=True)


@pytest.mark.parametrize('bom', ['', '\ufeff'])
def test_10hz_uses_time_bins_and_preserves_every_column_and_original_numeric_tokens(tmp_path, bom):
    source = tmp_path/'errors.csv'
    source.write_text(bom+'time,err_n_m,diagnostic_extra\n0.005,1.000000,9\n0.025,2.0,8\n0.099,3.0,7\n0.100,4.000,6\n0.140,5.0,5\n0.201,6.000000,4\n')
    writer = p.PackageWriter(tmp_path/'curves.zip', synthetic=True)
    result = p.display_series(writer, source, 'error/r.csv.gz', sha(source), source_protocol=p.PROTOCOL, run_id='r')
    close(writer)
    assert (result['rows_full'], result['rows_kept']) == (6, 3)
    with zipfile.ZipFile(writer.path) as archive:
        output = gzip.decompress(archive.read('error/r.csv.gz')).decode()
        rows = list(csv.reader(io.StringIO(output)))
        assert rows == [['time', 'err_n_m', 'diagnostic_extra'], ['0.005', '1.000000', '9'],
                        ['0.100', '4.000', '6'], ['0.201', '6.000000', '4']]
        mapping = list(csv.reader(io.StringIO(gzip.decompress(archive.read(result['source_row_map_member'])).decode())))
        assert mapping == [['member_csv_row', 'source_csv_row'], ['2', '2'], ['3', '5'], ['4', '7']]
        source_row = next(r for r in json.loads(archive.read('SUPPLEMENT_SOURCE_MANIFEST.json')) if r['member'] == 'error/r.csv.gz')
        assert source_row['full_metrics_source_sha256'] == sha(source)
        assert 'source_row_stride' not in source_row


@pytest.mark.parametrize('times', ['1,2\n1,3\n', '2,2\n1,3\n', 'NaN,2\n'])
def test_reject_duplicate_reversed_and_nonfinite_display_times(tmp_path, times):
    source = tmp_path/'bad.csv'
    source.write_text('time,error\n'+times)
    writer = p.PackageWriter(tmp_path/'bad.zip', synthetic=True)
    with pytest.raises(ValueError, match='finite and strictly increasing'):
        p.display_series(writer, source, 'bad.csv.gz', sha(source), source_protocol=p.PROTOCOL, run_id='r')
    writer.archive.close()


def test_missing_pin_changed_source_unsafe_member_and_symlink_are_rejected(tmp_path):
    source = tmp_path/'input.csv'
    source.write_text('a\n1\n')
    expected = sha(source)
    source.write_text('a\n2\n')
    writer = p.PackageWriter(tmp_path/'safe.zip', synthetic=True)
    with pytest.raises(ValueError, match='SHA mismatch'):
        writer.file(source, 'input.csv', expected, source_protocol=p.PROTOCOL)
    with pytest.raises(ValueError, match='SHA mismatch'):
        writer.file(source, 'input.csv', None, source_protocol=p.PROTOCOL)
    for unsafe in ('../x', '/x', 'a/../x', 'a\\x', 'C:/x', 'a//x', './x'):
        with pytest.raises(ValueError, match='Unsafe'):
            writer.generated(unsafe, b'bad')
    link = tmp_path/'link.csv'
    link.symlink_to(source)
    with pytest.raises(ValueError, match='regular file'):
        writer.file(link, 'link.csv', sha(source), source_protocol=p.PROTOCOL)
    writer.generated('one.csv', b'one')
    with pytest.raises(ValueError, match='Duplicate'):
        writer.generated('one.csv', b'two')
    writer.archive.close()


def _old_package(tmp_path):
    old = tmp_path/'old.zip'
    curve = gzip.compress(b'time,error\n0.005,1.000\n0.105,2.000\n', mtime=123)
    member = 'error_series_subset/v3/oldF01.csv.gz'
    rows = [{'run_id': 'oldF01', 'method_id': 'F01', 'evaluator_version': 'v3', 'status': 'OK',
             'source_sha256': 'full-scientific-error-sha', 'sample_policy': 'every 20th existing row; no interpolation'}]
    payloads = {'PLOT_GEOMETRY_CONTRACT.json': b'{"physical":true}', member: curve,
        'error_series_subset/SUBSET_MANIFEST.csv': p._csv_bytes(rows),
        'SUPPLEMENT_SOURCE_MANIFEST.json': b'[]', 'forbidden/OLD_METRICS.csv': b'metric\n1\n'}
    manifest = {'members': {name: {'sha256': hashlib.sha256(payload).hexdigest(), 'size_bytes': len(payload)}
                            for name, payload in payloads.items()}}
    with zipfile.ZipFile(old, 'x') as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)
        archive.writestr('PACKAGE_MANIFEST.json', json.dumps(manifest))
    return old, curve


def test_frozen_f01_display_bytes_and_original_row_semantics_reused_only_for_formal_f01(tmp_path):
    old, curve = _old_package(tmp_path)
    writer = p.PackageWriter(tmp_path/'new.zip', synthetic=True)
    with pytest.raises(ValueError, match='whitelist'):
        writer.immutable(old, sha(old), ['forbidden/OLD_METRICS.csv'])
    writer.immutable(old, sha(old), ['PLOT_GEOMETRY_CONTRACT.json'])
    row = {'run_id': 'oldF01', 'method_id': 'F01', 'formal_F01_reused': True, 'evaluator_version': 'v3'}
    result = writer.frozen_f01_curve(row, 'error_series_subset/v3/oldF01.csv.gz', 'full-source-pin')
    assert result['display_projection'] == 'FROZEN_V2_BYTES'
    assert result['source_row_stride'] == 20
    with pytest.raises(ValueError, match='restricted to formal F01'):
        writer.frozen_f01_curve(dict(row, method_id='F04'), 'evil.csv.gz', 'full-source-pin')
    assert writer.frozen_f01_curve(dict(row, run_id='missing'), 'missing.csv.gz', 'pin') is None
    close(writer)
    with zipfile.ZipFile(writer.path) as archive:
        assert archive.read('error_series_subset/v3/oldF01.csv.gz') == curve
        assert 'forbidden/OLD_METRICS.csv' not in archive.namelist()
        original = next(r for r in json.loads(archive.read('SUPPLEMENT_SOURCE_MANIFEST.json')) if r['member'].endswith('oldF01.csv.gz'))
        assert original['original_source_manifest']['sample_policy'].startswith('every 20th')


def test_fake_gzip_content_is_not_accepted(tmp_path):
    source = tmp_path/'fake.csv.gz'
    source.write_bytes(b'not a gzip file')
    writer = p.PackageWriter(tmp_path/'bad.zip', synthetic=True)
    with pytest.raises(gzip.BadGzipFile):
        writer.file(source, 'fake.csv.gz', sha(source), source_protocol=p.PROTOCOL)
    writer.archive.close()


def test_validator_detects_member_tampering_without_relying_on_counts(tmp_path):
    writer = p.PackageWriter(tmp_path/'original.zip', synthetic=True)
    writer.generated('x.csv', b'x\n1\n')
    close(writer)
    changed = tmp_path/'changed.zip'
    with zipfile.ZipFile(writer.path) as old, zipfile.ZipFile(changed, 'x') as new:
        for name in old.namelist():
            new.writestr(name, b'x\n2\n' if name == 'x.csv' else old.read(name))
    with pytest.raises(ValueError, match='identity mismatch'):
        p.validate_archive(changed)


def test_terminal_gate_has_no_small_fixture_override_and_checks_evaluator_finiteness():
    native = {'run_id': 'r', 'case_id': p.C00, 'dataset_id': 'BY2', 'method_id': 'F04',
              'terminal_status': 'COMPLETED'}
    rows = [{'run_id': 'r', 'case_id': p.C00, 'dataset_id': 'BY2', 'method_id': 'F04',
             'evaluator_version': version, 'evaluation_status': 'COMPLETED', 'finite_output': True} for version in p.VERSIONS]
    with pytest.raises(ValueError, match='counts differ'):
        p.terminal_identity([native], rows)
    with pytest.raises(ValueError, match='Nonfinite'):
        p.terminal_identity([native], [dict(r, finite_output=False) for r in rows])
    with pytest.raises(ValueError, match='Duplicate'):
        p.terminal_identity([native, native], rows)
    with pytest.raises(ValueError, match='formal v2 reuse'):
        p.terminal_identity([dict(native, method_id='F01')], [dict(r, method_id='F01') for r in rows])


def test_small_genuine_package_cannot_claim_real_formal_counts(tmp_path):
    writer = p.PackageWriter(tmp_path/'real.zip')
    with pytest.raises(ValueError, match='formal identity counts'):
        close(writer)


def test_full_terminal_accounting_includes_f01_and_by2_c00_once_without_io():
    # In-memory accounting fixture only: this does not enter any real result table.
    cases = [('BY2', p.C00, 'CORE')]+[('BY2', f'D01_fixture_{i}', 'CORE') for i in range(540)]
    cases += [('BY2', f'D61_fixture_{i}', 'ADDENDUM') for i in range(45)]
    cases += [('BY2H', 'BY2H_natural', 'SEQUENCE'), ('BY2O', 'BY2O_natural', 'SEQUENCE')]
    records, evaluations = [], []
    for dataset, case, domain in cases:
        for method in sorted(p.PROFILES):
            row = {'run_id': dataset+'_'+case+'_'+method, 'case_id': case, 'dataset_id': dataset,
                   'method_id': method, 'domain': domain, 'terminal_status': 'COMPLETED',
                   'formal_F01_reused': method == 'F01', 'data_mode': 'real',
                   'synthetic_data_used': False, 'semisynthetic_data_used': domain == 'ADDENDUM',
                   'trace_used_online': False}
            records.append(row)
            evaluations.extend(dict(row, evaluator_version=version, evaluation_status='COMPLETED', finite_output=True) for version in p.VERSIONS)
    assert p.terminal_identity(records, evaluations)['counts'] == p.COUNTS
    evaluations[0]['synthetic_data_used'] = True
    with pytest.raises(ValueError, match='provenance flag'):
        p.terminal_identity(records, evaluations)


def test_native_effective_profile_alias_is_read_without_mutating_sealed_row():
    native = {'method_id': 'A04', 'effective_profile': 'AB1011'}
    assert p.effective_configuration(native) == 'AB1011'
    assert native == {'method_id': 'A04', 'effective_profile': 'AB1011'}
    assert p.effective_configuration({'method_id': 'A04', 'effective_configuration_id': 'AB1011'}) == 'AB1011'
    with pytest.raises(ValueError, match='frozen method registry'):
        p.effective_configuration(dict(native, effective_configuration_id='AB1111'))
