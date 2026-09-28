"""Temporary archive fixtures only; no production handoff creation."""
import importlib.util
from pathlib import Path
import json
import zipfile
import pytest

SPEC=importlib.util.spec_from_file_location('clean5_pack_v2',Path(__file__).parents[2]/'scripts/paper_rebuild/clean5_pack_v2.py')
p=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(p)


def archive_fixture(tmp_path):
    old=tmp_path/'old.zip'
    with zipfile.ZipFile(old,'x') as z:z.writestr('original.csv','x,all_original_columns\n1,unchanged\n');z.writestr('display.nav','already authorized old member')
    source=tmp_path/'new.csv';source.write_bytes(b'run,metric,additional_scalar\nN00,1.234567890123456,kept\n')
    st=source.stat();sources={'STAGE2/test.csv':{'path':source,'source_alias':'<CLEAN_ROOT>/fixture.csv','sha256':p.digest(source),'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'role':'COPIED_SOURCE_TABLE_OR_METADATA'}}
    return old,source,sources


def test_inherit_bytes_all_columns_hashes_and_no_overwrite(tmp_path):
    old,source,sources=archive_fixture(tmp_path);output=tmp_path/'v2.zip'
    result=p.copy_package(old,output,sources,{},expected_v1_sha=p.digest(old),expected_v1_count=2)
    assert result['status']=='PASS' and result['entry_count']==5
    with zipfile.ZipFile(old) as a,zipfile.ZipFile(output) as b:
        assert all(a.read(name)==b.read(name) for name in a.namelist())
        assert b.read('STAGE2/test.csv')==source.read_bytes()
        probe=json.loads(b.read('STAGE2/IDENTITY_PROBE.json'))
        assert probe['metric_recomputation_count']==probe['solver_invocation_count']==probe['evaluator_invocation_count']==probe['raw_source_open_count']==0
        assert probe['source_scalar_columns_removed']==0 and probe['v1_builder_invoked'] is False
    with pytest.raises(FileExistsError):p.copy_package(old,output,sources,{},expected_v1_sha=p.digest(old),expected_v1_count=2)


def test_reject_changed_source_archive_identity_and_member_collision(tmp_path):
    old,source,sources=archive_fixture(tmp_path)
    with pytest.raises(ValueError,match='identity'):p.copy_package(old,tmp_path/'bad.zip',sources,{},expected_v1_sha='0'*64,expected_v1_count=2)
    with pytest.raises(ValueError,match='replace'):p.copy_package(old,tmp_path/'collision.zip',{'original.csv':next(iter(sources.values()))},{},expected_v1_sha=p.digest(old),expected_v1_count=2)
    source.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):p.copy_package(old,tmp_path/'changed.zip',sources,{},expected_v1_sha=p.digest(old),expected_v1_count=2)


def test_forbidden_trace_exception_is_exact_path_and_hash(tmp_path,monkeypatch):
    path=tmp_path/p.DERIVED_TRACE;path.parent.mkdir(parents=True);path.write_text('diagnostic fixture')
    monkeypatch.setattr(p,'DERIVED_TRACE_SHA',p.digest(path))
    assert p.classify_source(path,tmp_path)=='DERIVED_DIAGNOSTIC_ONLY'
    path.write_text('modified')
    with pytest.raises(ValueError):p.classify_source(path,tmp_path)
    other=path.parent/'trace_raw.csv';other.write_text('forbidden')
    with pytest.raises(ValueError):p.classify_source(other,tmp_path)
    for name in ['x.bag','x.fpl','KF_GINS_Navresult.nav','PARITY.imu']:
        other=path.parent/name;other.write_text('forbidden')
        with pytest.raises(ValueError):p.classify_source(other,tmp_path)


def test_symlink_and_traversal_rejected(tmp_path):
    raw=tmp_path/'raw';raw.write_text('forbidden');link=tmp_path/'link';link.symlink_to(raw)
    with pytest.raises(ValueError):p.safe_path(link,tmp_path)
    for member in ['../raw','/raw','x/../raw','x\\raw','C:/raw']:
        with pytest.raises(ValueError):p.safe_member(member)


def test_selected_existing_seal_hash_is_checked_without_unselected_read(tmp_path):
    base=tmp_path/'stage';seal_dir=base/'04_SEAL';seal_dir.mkdir(parents=True);table=base/'table.csv';table.write_text('value\n1\n')
    seal=seal_dir/'OUTPUT_SEAL.json';seal.write_text(json.dumps({'files_sha256':{'table.csv':p.digest(table),'03_RUNS/forbidden.nav':'a'*64}}))
    entries={name:{'path':path,'sha256':p.digest(path),'source_alias':'<CLEAN_ROOT>/'+name} for name,path in [('table.csv',table),('OUTPUT_SEAL.json',seal)]}
    assert len(p.seal_crosschecks(entries,tmp_path))==1
    entries['table.csv']['sha256']='0'*64
    with pytest.raises(ValueError,match='seal'):p.seal_crosschecks(entries,tmp_path)
