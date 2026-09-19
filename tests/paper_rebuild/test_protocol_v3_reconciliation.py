"""Storage interruption tests; no solver, evaluator, or real-data output."""
import importlib.util
import gzip
import hashlib
import json
from pathlib import Path

import pytest

SCRIPT=Path(__file__).resolve().parents[2]/'scripts/paper_rebuild/v3r_reconcile_archive.py'
spec=importlib.util.spec_from_file_location('v3r_reconcile_test',SCRIPT)
rec=importlib.util.module_from_spec(spec);spec.loader.exec_module(rec)


def test_release_resumes_original_inventory_after_interruption(tmp_path,monkeypatch):
    root=tmp_path/'slot';root.mkdir();(root/'a').write_bytes(b'a');(root/'b').write_bytes(b'b')
    evidence=tmp_path/'evidence';original=Path.unlink;calls=[]
    def interrupt(path,*a,**kw):
        if path.name=='b':raise OSError('simulated power loss')
        calls.append(path.name);return original(path,*a,**kw)
    monkeypatch.setattr(Path,'unlink',interrupt)
    with pytest.raises(OSError):rec.exact_release(root,evidence)
    inventory=(evidence/'slot_RELEASE_INVENTORY.json').read_bytes()
    monkeypatch.setattr(Path,'unlink',original);rec.exact_release(root,evidence)
    assert not root.exists()
    assert (evidence/'slot_RELEASE_INVENTORY.json').read_bytes()==inventory
    assert calls==['a']


def test_missing_release_file_without_durable_intent_rejected(tmp_path):
    root=tmp_path/'slot';root.mkdir();p=root/'a';p.write_bytes(b'a')
    e=tmp_path/'e';rec.put(e/'slot_RELEASE_INVENTORY.json',[{'path':str(p),'size_bytes':1}]);p.unlink()
    with pytest.raises(ValueError,match='WITHOUT_INTENT'):rec.exact_release(root,e)


def test_partial_copy_retries_only_matching_prefix(tmp_path):
    source=tmp_path/'s';dest=tmp_path/'d';source.write_bytes(b'abcdef');dest.write_bytes(b'abc')
    rec.copy_verified(source,dest,rec.sha(source));assert dest.read_bytes()==source.read_bytes()
    dest.write_bytes(b'bad')
    with pytest.raises(ValueError,match='PARTIAL_COPY_DIFFERS'):rec.copy_verified(source,dest,rec.sha(source))


def test_compact_reuse_checks_retained_payload(tmp_path):
    root=tmp_path/'compact';root.mkdir();p=root/'result.json';p.write_text('{}')
    rec.put(root/'ARCHIVE_RECEIPT.json',{'status':'ARCHIVE_VERIFIED','archive_scope':'RETAINED_EVIDENCE_ONLY','archive_root':str(root),'files':{'result.json':{'storage_relative_path':'result.json','sha256':rec.sha(p),'size_bytes':2}}})
    rec.verify_compact(root);p.write_text('[]')
    with pytest.raises(ValueError,match='COMPACT_ARCHIVE_FILE_CHANGED'):rec.verify_compact(root)


def test_partial_metadata_can_resume_without_changing_existing_record(tmp_path):
    p=tmp_path/'record.json';p.write_text('{\n  "a":')
    rec.put(p,{'a':1});assert json.loads(p.read_text())=={'a':1}
    with pytest.raises(ValueError,match='EXISTING_RECEIPT_DIFFERS'):rec.put(p,{'a':2})


def test_bulk_payload_policy_preserves_evaluation_series(tmp_path):
    assert not rec.keep('KF_GINS_Navresult.nav',{})
    assert not rec.keep('KF_GINS_STD.txt',{})
    assert not rec.keep('EVAL_NAV_V3.nav',{})
    assert rec.keep('FROZEN_EVALUATOR/error_series.csv.gz',{})
    assert rec.keep('MATCHED_TRAJECTORY.csv.gz',{})
    assert not rec.keep('error_series.csv',{'error_series.csv.gz':{}})


def test_compact_gzip_alias_works_with_frozen_reporting_member(tmp_path):
    from legsa_gins.paper_rebuild.protocol_v3.reporting import RuntimeResults, Sources
    source=tmp_path/'source';source.mkdir();dest=tmp_path/'dest'
    plain=b'time,error\n1,2\n';compressed=gzip.compress(plain,mtime=0)
    (source/'error_series.csv.gz').write_bytes(compressed)
    (source/'error_series.csv.lossless.gz').write_bytes(compressed)
    raw_sha=hashlib.sha256(plain).hexdigest();gz_sha=hashlib.sha256(compressed).hexdigest()
    original={'status':'ARCHIVE_VERIFIED','source_root':str(source),'archive_root':str(source),'files':{
        'error_series.csv':{'source_sha256':raw_sha,'source_size_bytes':len(plain),'storage_relative_path':'error_series.csv.lossless.gz','sha256':gz_sha,'size_bytes':len(compressed),'compression':'gzip'},
        'error_series.csv.gz':{'source_sha256':gz_sha,'source_size_bytes':len(compressed),'storage_relative_path':'error_series.csv.gz','sha256':gz_sha,'size_bytes':len(compressed),'compression':'identity'}}}
    rec.put(source/'ARCHIVE_RECEIPT.json',original)
    receipt=rec.compact_slot(source,dest)
    assert not (dest/'error_series.csv.lossless.gz').exists()
    results=RuntimeResults.__new__(RuntimeResults);key=('run','v3')
    results.folders={key:dest};results.seals={key:{'files':{'error_series.csv':raw_sha,'error_series.csv.gz':gz_sha}}}
    results.archives={key:receipt};results.sources=Sources({'clean_root':tmp_path})
    assert results.member(key,'error_series.csv')[0]==plain
    assert gzip.decompress(results.member(key,'error_series.csv.gz')[0])==plain
