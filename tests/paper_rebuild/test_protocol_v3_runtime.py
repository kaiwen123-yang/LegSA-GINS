"""Independent safety and scope regressions; all fixtures are synthetic."""
import concurrent.futures
import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.protocol_v3 import registry, runtime
from legsa_gins.paper_rebuild.hext.t5a_config_fidelity import STATIC_ECHO_KEYS


def test_reservations_are_atomic_and_retries_are_rejected(tmp_path):
    ids=[f'R{i}' for i in range(32)];ledger=tmp_path/'ledger.jsonl'
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        rows=list(pool.map(lambda rid:runtime.reserve_slot(ledger,rid,ids,kind='native'),ids))
    assert sorted(r['ordinal'] for r in rows)==list(range(1,33))
    with pytest.raises(RuntimeError,match='ALREADY_RESERVED'):
        runtime.reserve_slot(ledger,ids[0],ids,kind='native')
    with pytest.raises(PermissionError):runtime.reserve_slot(ledger,'OUTSIDE',ids,kind='native')
    assert len(ledger.read_text().splitlines())==32


def test_witness_rejects_science_even_if_metadata_is_valid():
    donor=b'case_id: D36\nrun_id: OLD\nrun_label: OLD\ngnsspath: /old\nnoise: 1.2\n'
    target=donor.replace(b'D36',b'D37').replace(b'OLD',b'NEW').replace(b'/old',b'/new')
    echo={key:False for key in STATIC_ECHO_KEYS}
    echo.update(case_id='D36',run_id='OLD',run_label='OLD',actual_solver_input_paths={
        'gnss_position_receiver_velocity_dual_yaw':'/old'})
    expected,proof=registry.derive_expected_echo(target,donor,echo)
    assert expected['case_id']=='D37'
    assert proof['historical_target_echo_available'] is False
    with pytest.raises(RuntimeError,match='SCIENCE_BYTES'):
        registry.derive_expected_echo(target.replace(b'1.2',b'1.3'),donor,echo)


def registry_fixture():
    specs=[]
    cases=[('CORE','BY2','C00_clean_normal')]
    cases += [('CORE','BY2',f'D{d:02d}_seed_{i:02d}') for d in range(1,61) for i in range(9)]
    cases += [('SEQUENCE',seq,f'CLEAN5_{seq}_NATURAL') for seq in ('BY2H','BY2O')]
    cases += [('ADDENDUM','BY2',f'D{d:02d}_{dur}s_seed_{i:02d}') for d,ds in ((61,(10,20,30)),(62,(10,20))) for dur in ds for i in range(9)]
    for domain,seq,case in cases:
        for method in registry.PROFILES:
            index=int(case.rsplit('_',1)[1]) if case.startswith('D') else None
            specs.append({'run_id':f'{seq}_{case}_{method}','domain':domain,'case_id':case,
                'sequence_id':seq,'method_id':method,'seed_index':f'seed_{index:02d}' if index is not None else 'none',
                'case_meta':{'seed_value':260306001+index} if index is not None else {}})
    return specs


def test_complete_registry_requires_every_profile_in_every_case():
    specs=registry_fixture()
    assert registry.validate_registry(specs)['unique_runs']==6468
    specs[0]['method_id']='F04'
    with pytest.raises(RuntimeError,match='ALL_ELEVEN'):registry.validate_registry(specs)


def test_registry_rejects_same_count_wrong_case_and_wrong_seed():
    specs=registry_fixture()
    for spec in specs:
        if spec['case_id']=='D01_seed_00':spec['case_id']='D99_seed_00'
    with pytest.raises(RuntimeError,match='EXACT_CASE_IDS'):registry.validate_registry(specs)
    specs=registry_fixture();specs[11]['case_meta']['seed_value']=260306999
    with pytest.raises(RuntimeError,match='EXACT_SEED_VALUE'):registry.validate_registry(specs)


def test_archive_preserves_bytes_and_releases_only_manifest_payload(tmp_path):
    scratch=tmp_path/'scratch';source=scratch/'03_NATIVE/R1';source.mkdir(parents=True)
    payload=b'% native fixture\n1 2 3\n'*100
    (source/'native.nav').write_bytes(payload);(source/'metadata.json').write_text('{"data_mode":"synthetic"}\n')
    (source/'OUTPUT_SEAL.json').write_text('{}')
    archive=tmp_path/'archive/R1'
    receipt=runtime.archive_directory(source,archive,scratch_root=scratch)
    assert receipt['status']=='ARCHIVE_VERIFIED'
    assert receipt['files']['native.nav']['source_sha256']==hashlib.sha256(payload).hexdigest()
    assert not (source/'native.nav').exists()
    assert (source/'metadata.json').exists()
    import gzip
    assert gzip.open(archive/'native.nav.gz','rb').read()==payload
    assert runtime.archive_directory(source,archive,scratch_root=scratch)==receipt
    with pytest.raises(PermissionError):runtime.archive_directory(tmp_path/'outside',tmp_path/'archive2',scratch_root=scratch)


def test_archive_rejects_symlink(tmp_path):
    scratch=tmp_path/'scratch';source=scratch/'03_NATIVE/R1';source.mkdir(parents=True)
    other=tmp_path/'raw';other.write_text('immutable');(source/'linked.nav').symlink_to(other)
    with pytest.raises(ValueError,match='symlink'):runtime.archive_directory(source,tmp_path/'archive',scratch_root=scratch)
    assert other.read_text()=='immutable'


def test_native_hard_stop_drains_started_futures_and_cancels_queue(tmp_path):
    import threading
    import time
    from legsa_gins.paper_rebuild.protocol_v3.controller import Context
    ctx=Context.__new__(Context);ctx.scratch=tmp_path
    lock=threading.Lock();active=[]
    def fake(spec):
        with lock:active.append(spec['run_id'])
        try:
            if spec['run_id']=='R0':
                time.sleep(.02)
                raise RuntimeError('synthetic unclassified failure')
            time.sleep(.08)
            return {'run_id':spec['run_id'],'status':'COMPLETED'}
        finally:
            with lock:active.remove(spec['run_id'])
    ctx._native=fake
    with pytest.raises(RuntimeError,match='synthetic unclassified'):
        ctx.native_batch([{'run_id':f'R{i}'} for i in range(128)],1)
    assert active==[]
    receipt=json.loads((tmp_path/'BATCHES/BATCH_001/HARD_STOP_DRAIN.json').read_text())
    assert receipt['all_started_futures_drained'] is True
    assert receipt['no_evaluator_or_later_batch_launched'] is True
    assert len(receipt['outcomes'])==128
    assert any(r['status']=='CANCELLED_BEFORE_START' for r in receipt['outcomes'])
