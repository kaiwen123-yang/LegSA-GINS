"""Synthetic pre-execution choices and immutable-path gates, no native calls."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.hext import t5bc_preparation as prep


def reports():
    return {sequence: {'sequence_id': sequence, 'primary_method': 'INSTALLED_GYRO_Z', 'reports': [
        {'lag_ms': 1000, 'status': 'AVAILABLE', 'z': {'k': value, 'sigma_deg': value * 2}},
        {'lag_ms': 200, 'status': 'AVAILABLE', 'euler': {'k': 99., 'sigma_deg': 99.}}]}
            for sequence, value in zip(('BY2', 'BY2H', 'BY2O'), (1., 2., 3.))}


def test_calibration_application_is_explicit_and_primary_lag_is_not_selected_by_value():
    source = reports()
    before = copy.deepcopy(source)
    for choice in (None, '', 'BEST', 'FALLBACK_TO_0P2S', 'SEQUENCE_SPECIFIC'):
        with pytest.raises(ValueError, match='Explicit R5sigma'):
            prep.select_scalar_calibration(source, sigma_application=choice)
    unified = prep.select_scalar_calibration(source, sigma_application='BY2_UNIFIED')
    assert [row['k'] for row in unified.values()] == [1., 1., 1.]
    assert [row['sigma_deg'] for row in unified.values()] == [2., 2., 2.]
    assert source == before


@pytest.mark.parametrize('change', ['missing', 'wrong_identity', 'unavailable_primary', 'duplicate_lag'])
def test_no_fallback_or_silent_cross_sequence_substitution(change):
    source = reports()
    if change == 'missing':
        del source['BY2O']
    elif change == 'wrong_identity':
        source['BY2H']['sequence_id'] = 'BY2'
    elif change == 'unavailable_primary':
        source['BY2']['reports'][0]['status'] = 'UNAVAILABLE_INSUFFICIENT_PAIRS'
    else:
        source['BY2H']['reports'].append(source['BY2H']['reports'][0])
    with pytest.raises(ValueError):
        prep.select_scalar_calibration(source, sigma_application='BY2_UNIFIED')


def test_hash_and_root_gates_precede_input_use(tmp_path):
    allowed = tmp_path / 'clean'
    allowed.mkdir()
    original = allowed / 'provider'
    original.write_bytes(b'original')
    ref = {'path': str(original), 'sha256': hashlib.sha256(b'original').hexdigest()}
    assert prep._reference(ref, allowed) == original
    original.write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='INPUT_IDENTITY'):
        prep._reference(ref, allowed)
    with pytest.raises(ValueError, match='outside'):
        prep._reference(ref, tmp_path / 'different')
    symlink = allowed / 'link'
    symlink.symlink_to(original)
    with pytest.raises(ValueError, match='symlinks'):
        prep._reference({**ref, 'path': str(symlink)}, allowed)


def test_provider_unresolved_selection_fails_before_any_input_or_output(tmp_path):
    scratch = tmp_path / prep.STAGE
    sequence = SimpleNamespace(sequence_id='BY2', clean_root=tmp_path / 'clean',
                               raw_root=tmp_path / 'raw', code_root=tmp_path / 'code')
    output = scratch / '03_PROVIDER_TABLES/BY2'
    with pytest.raises(ValueError, match='Unresolved'):
        prep.write_provider_bundle(sequence, {'sequence_id': 'BY2'}, {},
            frozen_gnss={'path': '/must/not/be/opened', 'sha256': '0'*64},
            r5_reference={'path': '/must/not/be/opened', 'sha256': '0'*64},
            output_root=output, scratch_root=scratch, data_mode='real_raw',
            f04_yaw_std_min_deg=1.5)
    assert not scratch.exists()


def test_original_output_and_unregistered_slot_are_preserved(tmp_path):
    scratch = tmp_path / prep.STAGE
    output = scratch / '01_CALIBRATION/BY2/SCALAR'
    output.mkdir(parents=True)
    sentinel = output / 'original'
    sentinel.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        prep._output(output, scratch, '01_CALIBRATION/BY2/SCALAR')
    with pytest.raises(ValueError, match='exact T5bc'):
        prep._output(tmp_path / 'outside', scratch, '01_CALIBRATION/BY2/SCALAR')
    assert sentinel.read_bytes() == b'preserve'


def test_secondary_sequence_unavailable_is_reported_not_used_as_fallback():
    source=reports()
    source['BY2H']['reports'][0]['status']='UNAVAILABLE_INSUFFICIENT_PAIRS'
    selected=prep.select_scalar_calibration(source)
    assert all(r['k']==1. and r['sigma_deg']==2. and r['baseline_m']==.35 for r in selected.values())
    vectors={s:dict(sequence_id=s,user_denominator_factor=6,reports=[
        dict(lag_ms=1000,status='AVAILABLE' if s=='BY2' else 'UNAVAILABLE',k_b=.7)]) for s in source}
    assert all(r['k_b']==.7 for r in prep.select_vector_calibration(vectors).values())


def test_bundle_manifest_source_pins_and_all_four_variants(tmp_path):
    from test_t5bc_provider import table, inputs, reference, sha, BASE
    scratch=tmp_path/prep.STAGE; clean=tmp_path/'clean'; clean.mkdir()
    base,data=table(),inputs(); data.pop('k'); data.pop('sigma_deg'); data.pop('baseline_m')
    frozen=clean/'frozen.txt'; frozen.write_bytes(base)
    r5=clean/'R5.txt'; r5.write_bytes(reference(base,data))
    sequence=SimpleNamespace(sequence_id='BY2',clean_root=clean,raw_root=tmp_path/'raw',
        code_root=tmp_path/'code',base_time=BASE,window=(10.,10.4))
    refs,manifest=prep.write_provider_bundle(sequence,dict(sequence_id='BY2',**data),
        prep.select_scalar_calibration(reports())['BY2'],
        frozen_gnss=dict(path=str(frozen),sha256=sha(base)),
        r5_reference=dict(path=str(r5),sha256=sha(r5.read_bytes())),
        output_root=scratch/'03_PROVIDER_TABLES/BY2',scratch_root=scratch,
        data_mode='synthetic',f04_yaw_std_min_deg=1.5)
    assert set(refs)=={'R5','R5W','R5SIGMA','B3','B3_GNSS','prepared_raw_manifest'}
    prepared=json.loads(open(refs['prepared_raw_manifest']['path']).read())
    assert prepared['baseline_m']==.35 and prepared['source_sha256']==sha(base)
    assert prepared['pinned_r5_source']==dict(path=str(r5),sha256=sha(r5.read_bytes()))
    assert prepared['synthetic_data_used'] is True
    assert len(prepared['rows'])==3 and all(r['raw_valid'] for r in prepared['rows'])
    assert all({'time_token','itow_ms','raw_yaw_token','std_R5W_token','std_R5SIGMA_token',
        'raw_valid','b_n','b_e','b_d','pAcc1','pAcc2'} <= set(r) for r in prepared['rows'])
    assert json.loads(open(manifest['path']).read())['prepared_raw_manifest']==refs['prepared_raw_manifest']


def test_only_c00_subset_accepts_real_clean_before_input_read(tmp_path):
    sequence=SimpleNamespace(sequence_id='BY2',clean_root=tmp_path/'clean',raw_root=tmp_path/'raw',code_root=tmp_path/'code')
    scratch=tmp_path/prep.STAGE
    with pytest.raises(ValueError,match='Only the frozen C00'):
        prep.write_provider_bundle(sequence,dict(sequence_id='BY2'),{},frozen_gnss={},r5_reference={},
            scratch_root=scratch,output_root=scratch/'03_PROVIDER_TABLES/SUBSET61/D01_seed_00',
            data_mode='real_clean',subset_case_id='D01_seed_00',f04_yaw_std_min_deg=1.5)
    with pytest.raises(ValueError,match='Unresolved'):
        prep.write_provider_bundle(sequence,dict(sequence_id='BY2'),{},frozen_gnss={},r5_reference={},
            scratch_root=scratch,output_root=scratch/'03_PROVIDER_TABLES/SUBSET61/C00_clean_normal',
            data_mode='real_clean',subset_case_id='C00_clean_normal',f04_yaw_std_min_deg=1.5)
    assert not scratch.exists()


@pytest.mark.parametrize('protected', ['raw_root', 'clean_root', 'code_root'])
@pytest.mark.parametrize('entrypoint', ['decode', 'calibrate', 'vector', 'providers'])
def test_all_preparation_entrypoints_reject_protected_scratch_before_io(tmp_path, protected, entrypoint):
    sequence = SimpleNamespace(sequence_id='BY2', clean_root=tmp_path / 'clean',
                               raw_root=tmp_path / 'raw', code_root=tmp_path / 'code')
    scratch = getattr(sequence, protected) / prep.STAGE
    with pytest.raises(ValueError, match='outside protected roots'):
        if entrypoint == 'decode':
            prep.decode_observations(sequence, scratch_root=scratch,
                                     output_root=scratch / '01_CALIBRATION/BY2/RAW_OBSERVATIONS')
        elif entrypoint == 'calibrate':
            prep.calibrate_scalar(sequence, {'sequence_id': 'BY2'}, imu_reference={}, rp_reference={},
                scratch_root=scratch, output_root=scratch / '01_CALIBRATION/BY2/SCALAR',
                denominator_policy='PAIR_ENDPOINTS_WITH_MULTIPLICITY')
        elif entrypoint == 'vector':
            prep.calibrate_vector(sequence, {'sequence_id': 'BY2'}, imu_reference={}, rp_reference={},
                scratch_root=scratch, output_root=scratch / '01_CALIBRATION/BY2/VECTOR')
        else:
            prep.write_provider_bundle(sequence, {'sequence_id': 'BY2'}, {}, frozen_gnss={}, r5_reference={},
                output_root=scratch / '03_PROVIDER_TABLES/BY2', scratch_root=scratch, data_mode='real_raw',
                f04_yaw_std_min_deg=1.5)
    assert not scratch.exists()
