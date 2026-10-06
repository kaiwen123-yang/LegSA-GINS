"""P13 downstream preserves input interventions and lossless source identities."""
import gzip
import hashlib

import pytest

from legsa_gins.paper_rebuild.clean6_sensor_v21.downstream import (
    correct_gnss_text, resolve_error_series, grid_origin_gate, LADDER,
)
from legsa_gins.paper_rebuild.clean5_parity_p05.runtime import patch_noise


@pytest.mark.parametrize('width', [15, 18])
def test_yaw_std_only_preserves_every_other_byte(width):
    prefix = '# frozen header\n\n'
    body = '\t'.join([str(i) for i in range(14)] + ['1.500000'] +
                     (['1', '0', '1'] if width == 18 else [])) + '\r\n'
    result, audit = correct_gnss_text(prefix + body)
    assert result == prefix + body.replace('1.500000', '2.933193')
    assert audit['columns'] == width
    assert audit['validity_unchanged']


@pytest.mark.parametrize('text', ['', ' '.join(['0'] * 17),
                                   ' '.join(['0'] * 15 + ['1', '2', '1'])])
def test_invalid_gnss_cannot_be_reinterpreted(text):
    with pytest.raises(ValueError):
        correct_gnss_text(text)


def test_retained_gzip_requires_original_csv_content_hash(tmp_path):
    payload = b'time,yaw_err_deg\n66.1,0.1\n'
    path = tmp_path / 'error_series.csv'
    with gzip.open(str(path) + '.gz', 'wb') as stream:
        stream.write(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert resolve_error_series(path, expected) == str(path) + '.gz'
    compressed = path.with_suffix('.csv.gz')
    assert resolve_error_series(compressed, hashlib.sha256(compressed.read_bytes()).hexdigest()) == str(compressed)
    with pytest.raises(ValueError, match='identity mismatch'):
        resolve_error_series(path, '0' * 64)


def test_noise_grid_preserves_explicit_initial_bias_and_native_parameters():
    template = ('abstd: [77.8, 77.8, 77.8]\nvrw: [0.077, 0.077, 0.077]\n'
                'initbastd: [77.8, 77.8, 77.8]\narw: [0.985, 0.985, 0.985]\n'
                'gbstd: [9.38, 9.38, 9.38]\nbasic_dual_yaw_fixed_std_deg: 2.933193\n')
    actual, audit = patch_noise(template, 7780, 7.7)
    assert audit['non_grid_bytes_equal']
    assert 'initbastd: [77.8, 77.8, 77.8]' in actual
    assert 'basic_dual_yaw_fixed_std_deg: 2.933193' in actual
    assert actual.count('7780') == 3
    assert LADDER == ('V0', 'V1', 'V2', 'V2i', 'V2s', 'V2is')


def test_grid_origin_compares_current_control_and_detects_change(tmp_path):
    control, origin = tmp_path / 'control', tmp_path / 'origin'
    control.mkdir()
    origin.mkdir()
    for name in ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt'):
        (control / name).write_text('1.0 2.0\n2.0 3.0\n')
        (origin / name).write_text('1 2\n2 3\n')
    check = grid_origin_gate(control, origin)
    assert check['status'] == 'PASS'
    assert not check['pre_correction_output_used']
    (origin / 'KF_GINS_STD.txt').write_text('1 2\n2 3.01\n')
    assert grid_origin_gate(control, origin)['status'] == 'FAIL'
