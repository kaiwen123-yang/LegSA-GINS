"""Synthetic protocol infrastructure checks; never real result evidence."""
import csv
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.clean6_canonical_v2.runtime import (
    classify_all_yaw_rejected, profile_template, seal_run)
from legsa_gins.paper_rebuild.clean6_canonical_v2.storage import (
    cleanup_exact, inventory, retain_run, thin_nav)


def test_profile_transfer_preserves_sequence_bytes_and_rejects_noise_change():
    sequence = 'initpos: [4, 5, 6]\nvrw: [1, 2, 3]\nalgorithm_id: Full\nenable_raw_doppler: true\n'
    full = sequence.replace('[4, 5, 6]', '[7, 8, 9]')
    variant = full.replace('Full', 'AB0111').replace('true', 'false')
    result, fields = profile_template(sequence, full, variant)
    assert result == sequence.replace('Full', 'AB0111').replace('true', 'false')
    assert fields == ['algorithm_id', 'enable_raw_doppler']
    with pytest.raises(ValueError):
        profile_template(sequence, full, variant.replace('[1, 2, 3]', '[9, 9, 9]'))


def rejection_scene(root, *, truncate=False, accepted=False):
    root.mkdir()
    (root/'stderr.log').write_text('FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch')
    (root/'PORT_GNSS_UPDATE_TRACE.csv').write_text(
        'position_update,velocity_update,yaw_update,yaw_mode\n1,1,1,REJECT\n1,1,1,'+
        ('NORMAL' if accepted else 'REJECT')+'\n')
    (root/'PORT_RUNTIME_LOOP_TRACE.csv').write_text('loop_index,timestamp_after_process\n0,1\n'+('' if truncate else '1,2\n'))
    return root


@pytest.mark.parametrize('truncate,accepted,passed', [(False,False,True),(True,False,False),(False,True,False)])
def test_all_yaw_failure_needs_full_window_and_every_rejection(tmp_path, truncate, accepted, passed):
    root = rejection_scene(tmp_path/'run', truncate=truncate, accepted=accepted)
    cfg = {'enable_dual_yaw': True, 'starttime': 0., 'endtime': 2.}
    expected = {'dual_yaw_attempt_count': 2, 'position_update_count': 2,
                'receiver_velocity_update_count': 2, 'last_processed_imu_time': 2.}
    assert classify_all_yaw_rejected(root,cfg,expected,np.array([[0.],[1.],[2.]]))['passed'] is passed


def test_exact_cleanup_refuses_changed_files_and_preserves_unlisted(tmp_path):
    scratch = tmp_path/'scratch'; root=scratch/'batch'/'run'; root.mkdir(parents=True)
    data=root/'NAV.nav'; data.write_bytes(b'original')
    pins=inventory(root)
    keep=root/'unlisted'; keep.write_bytes(b'keep')
    data.write_bytes(b'changed')
    with pytest.raises(ValueError): cleanup_exact(root,pins,tmp_path/'ledger',scratch_root=scratch,archive_verified=True)
    assert data.exists() and keep.exists()
    data.write_bytes(b'original')
    cleanup_exact(root,pins,tmp_path/'ledger',scratch_root=scratch,archive_verified=True)
    assert not data.exists() and keep.read_bytes()==b'keep'
    with pytest.raises(ValueError): cleanup_exact(scratch,{},tmp_path/'ledger',scratch_root=scratch,archive_verified=True)


def test_archive_retains_full_hashes_and_lossless_errors_before_cleanup(tmp_path):
    source=tmp_path/'scratch'/'batch'/'run'; source.mkdir(parents=True)
    nav='1 66.001 30 110 1 0 0 0 1 2 3\n1 66.099 30 110 1 0 0 0 1 2 3\n1 66.101 30 110 1 0 0 0 1 2 3\n'
    (source/'KF_GINS_Navresult.nav').write_text(nav)
    (source/'KF_GINS_STD.txt').write_text('66.001 1 2 3\n')
    (source/'RUN_MANIFEST.json').write_text('{}')
    (source/'PORT_GNSS_UPDATE_TRACE.csv').write_text('test\n1\n')
    record={'output_root':str(source),'terminal_status':'COMPLETED','run_id':'test','dataset_id':'SYNTHETIC_TEST'}
    record['output_seal']=seal_run(source)
    evaluations={}
    for version in ('v3','v2'):
        root=tmp_path/version; path=root/'FROZEN_EVALUATOR'; path.mkdir(parents=True)
        (path/'summary.json').write_text('{}')
        (path/'error_series.csv').write_text('t,e\n1,2\n')
        with gzip.open(path/'error_series.csv.gz','wb') as f:f.write(b't,e\n1,2\n')
        evaluations[version]=root
    destination=tmp_path/'archive'/'test'
    receipt=retain_run(record,evaluations,destination)
    assert source.joinpath('KF_GINS_Navresult.nav').exists()
    assert not (destination/'solver/KF_GINS_Navresult.nav').exists()
    assert receipt['original_files']['solver']['KF_GINS_Navresult.nav']['sha256']==record['output_seal']['KF_GINS_Navresult.nav']['sha256']
    assert gzip.open(destination/'solver/NAV_10HZ.csv.gz','rt').read().count('\n')==3
    assert json.loads((destination/'RUN_MANIFEST.json').read_text())['manifest_role']=='PROTOCOL_V2_ARCHIVE_WRAPPER'


def test_thinning_keeps_tokens_and_rejects_nonfinite(tmp_path):
    source=tmp_path/'nav'; source.write_text('1 66.001 NaN 1 1 0 0 0 1 2 3\n')
    with pytest.raises(ValueError): thin_nav(source,tmp_path/'nav.gz')
