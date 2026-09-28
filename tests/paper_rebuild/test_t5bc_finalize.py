"""Synthetic final delivery tests; no science subprocesses or raw sources."""
import hashlib
import json
import zipfile
from pathlib import Path
import pytest
from legsa_gins.paper_rebuild.hext import t5bc_finalize as final


def fixture(tmp_path,monkeypatch):
    scratch=tmp_path/'scratch';archive=tmp_path/'archive';handoff=tmp_path/'handoff'
    handoff.mkdir()
    for name in ('01_CALIBRATION','02_IDENTITY_GATE','03_PROVIDER_TABLES','04_NATIVE_C00_SEQ',
                 '05_NATIVE_SUBSET61','06_EVAL','07_AGGREGATE','08_FIGURES','09_HANDOFF'):
        root=scratch/name;root.mkdir(parents=True)
        (root/'SYNTHETIC_FIXTURE.txt').write_text('No real result\n')
    (scratch/'09_HANDOFF/VISUAL_REVIEW.json').write_text('{"status":"PASS","data_mode":"synthetic"}')
    (scratch/'08_FIGURES/T5BC_RENDER_MANIFEST.json').write_text('{"data_mode":"synthetic"}')
    summary={'data_mode':'synthetic','synthetic_data_used':True,'semisynthetic_data_used':False,
             'budget_authorized':{},'budget_reserved':{},'trace_open_count_evaluator':0}
    monkeypatch.setattr(final,'verify_completed',lambda *args:(summary,{}))
    return scratch,archive,handoff


def test_complete_package_streams_member_hash_crc_and_preserves_existing(tmp_path,monkeypatch):
    scratch,archive,handoff=fixture(tmp_path,monkeypatch)
    result=final.package_completed(scratch,archive,handoff,'a'*40)
    zpath=handoff/'t5bc_v3_candidate_pilot_handoff.zip'
    assert result['zip_size_bytes']==zpath.stat().st_size
    assert result['zip_sha256']==hashlib.sha256(zpath.read_bytes()).hexdigest()
    verification=json.loads((scratch/'09_HANDOFF/ZIP_VERIFICATION.json').read_text())
    with zipfile.ZipFile(zpath) as z:
        for item in verification['members']:
            assert hashlib.sha256(z.read(item['name'])).hexdigest()==item['sha256']
            assert f"{z.getinfo(item['name']).CRC:08x}"==item['crc32']
    assert (archive/'FINAL_SUMMARY.json').read_bytes()==(scratch/'FINAL_SUMMARY.json').read_bytes()
    before=zpath.read_bytes()
    with pytest.raises((RuntimeError,FileExistsError)):
        final.package_completed(scratch,archive,handoff,'a'*40)
    assert zpath.read_bytes()==before


def test_package_requires_actual_visual_receipt(tmp_path,monkeypatch):
    scratch,archive,handoff=fixture(tmp_path,monkeypatch)
    (scratch/'09_HANDOFF/VISUAL_REVIEW.json').write_text('{"status":"NOT_PERFORMED"}')
    with pytest.raises(RuntimeError,match='VISUAL_REVIEW_REQUIRED'):
        final.package_completed(scratch,archive,handoff,'a'*40)
    assert not list(handoff.iterdir())
