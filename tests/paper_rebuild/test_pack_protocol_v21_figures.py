"""Synthetic file-identity checks; no scientific figure or data generation."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest


SCRIPTS = Path(__file__).parents[2]/'scripts/paper_rebuild'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('p13_figure_pack', SCRIPTS/'pack_protocol_v21_figures.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path/'figures/v21'
    root.mkdir(parents=True)
    source = tmp_path/'data.zip'
    source.write_bytes(b'SYNTHETIC TEST PACKAGE IDENTITY ONLY')
    source_hash = p.sha(source)
    put(root/'RENDER_MANIFEST.json', dict(status='COMPLETE', visual_review_status='PASS',
        protocol_version='v2.1', failures=[], rendered_count=28, requested_figure_count=28,
        package_sha256=source_hash, reissued_count=8, new_count=20, supplementary_count=2,
        data_mode='synthetic_unit_test', synthetic_data_used=True, semisynthetic_data_used=False))
    reviews = []
    for fid in sorted(p.EXPECTED_IDS):
        folder = root/fid
        folder.mkdir()
        outputs = {}
        for extension in ('png', 'pdf', 'svg'):
            path = folder/(fid+'.'+extension)
            path.write_bytes(('synthetic '+fid+' '+extension).encode())
            outputs[extension] = dict(path=path.relative_to(root).as_posix(), sha256=p.sha(path))
        put(folder/'FIGURE_MANIFEST.json', dict(figure_id=fid, protocol_version='v2.1',
            status='RENDERED', package_sha256=source_hash, proposed_method='F04',
            evaluator='NOT_APPLICABLE_NATIVE_DIAGNOSTIC' if fid in {'FIG01','FIG03','FIG04'} else 'v3',
            qa=[{'pass': True}], outputs=outputs))
        reviews.append(dict(figure_id=fid, status='PASS', png_sha256=outputs['png']['sha256']))
    put(root/'VISUAL_REVIEW.json', dict(status='PASS', figures=reviews))
    (root/'FIGURE_INDEX.md').write_text('# Synthetic v2.1 index\n')
    with (root/'FIGURE_INDEX.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['figure_id', 'protocol_version', 'status'])
        writer.writeheader()
        writer.writerows(dict(figure_id=fid, protocol_version='v2.1', status='RENDERED') for fid in sorted(p.EXPECTED_IDS))
    old = tmp_path/'figures/v2'
    v1 = tmp_path/'figures/v1_prereg'
    (old/'MFIG21').mkdir(parents=True)
    v1.mkdir()
    (v1/'original.svg').write_bytes(b'original v1')
    for extension in ('png', 'pdf', 'svg'):
        (old/'MFIG21'/('MFIG21.'+extension)).write_bytes(('original v2 '+extension).encode())
    preserved = tmp_path/'figures_v2.zip'
    pins = {}
    with zipfile.ZipFile(preserved, 'x') as archive:
        for prefix, folder in [('v2', old), ('v1_prereg', v1)]:
            for relative, path in p.members(folder).items():
                name = prefix+'/'+relative
                pins[name] = dict(sha256=p.sha(path), size_bytes=path.stat().st_size)
                archive.write(path, name)
        archive.writestr('PACKAGE_MANIFEST.json', json.dumps({'members': pins}))
    return SimpleNamespace(figure_root=root, source_package=source, output=tmp_path/'v21.zip',
        preserved_package=preserved, preserved_package_sha256=p.sha(preserved), v1_root=v1, v2_root=old)


def test_package_has_28_figures_and_original_mfig21_preservation_evidence(inputs):
    result = p.package(inputs)
    assert result['figure_count'] == 28 and result['export_count'] == 84
    assert result['preserved_edition_files'] == {'v2': 3, 'v1_prereg': 1}
    with zipfile.ZipFile(inputs.output) as archive:
        assert not any(name.startswith('v21/MFIG21/') for name in archive.namelist())
        evidence = json.loads(archive.read('provenance/PRESERVED_V1_V2_MFIG21.json'))
        assert evidence['status'] == 'PASS'


def test_reject_changed_old_mfig21_without_creating_zip(inputs):
    (inputs.v2_root/'MFIG21/MFIG21.svg').write_bytes(b'changed')
    with pytest.raises(ValueError, match='Preserved edition bytes'):
        p.package(inputs)
    assert not inputs.output.exists()


def test_reject_stale_visual_review_even_with_updated_export_manifest(inputs):
    path = inputs.figure_root/'MFIG20/MFIG20.png'
    path.write_bytes(b'new raster not reviewed')
    manifest_path = path.parent/'FIGURE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['outputs']['png']['sha256'] = p.sha(path)
    put(manifest_path, manifest)
    with pytest.raises(ValueError, match='Raster review'):
        p.package(inputs)
    assert not inputs.output.exists()


def test_reject_protocol_or_evaluator_relabeling(inputs):
    path = inputs.figure_root/'FIG03/FIGURE_MANIFEST.json'
    manifest = json.loads(path.read_text())
    manifest['evaluator'] = 'v3'
    put(path, manifest)
    with pytest.raises(ValueError, match='provenance or QA'):
        p.package(inputs)


def test_preserved_package_requires_its_prior_identity(inputs):
    inputs.preserved_package_sha256 = '0'*64
    with pytest.raises(ValueError, match='Frozen v2 figure package hash'):
        p.package(inputs)


def test_extra_unregistered_export_is_not_silently_packaged(inputs):
    (inputs.figure_root/'extra.png').write_bytes(b'extra')
    with pytest.raises(ValueError, match='exactly 84 registered'):
        p.package(inputs)
    assert not inputs.output.exists()


def test_even_an_empty_mfig21_subtree_is_excluded(inputs):
    (inputs.figure_root/'MFIG21').mkdir()
    with pytest.raises(ValueError, match='no MFIG21 subtree'):
        p.package(inputs)
