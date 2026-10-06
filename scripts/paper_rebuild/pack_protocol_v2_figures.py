#!/usr/bin/env python3
"""Package verified v2 publication exports and the byte-identical v1 archive."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile

EXPECTED_IDS = {f'MFIG{n:02d}' for n in range(23)} | {'SFIG01', 'SFIG02'} | {f'FIG{n:02d}' for n in range(1, 5)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def regular(path):
    path = Path(path).absolute()
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Expected ordinary file without symlink ancestors: '+str(path))
    return path


def members(root):
    root = Path(root).absolute()
    return {p.relative_to(root).as_posix(): regular(p) for p in sorted(root.rglob('*')) if p.is_file()}


def package(args):
    root, old = args.figure_root.absolute(), args.v1_root.absolute()
    output = args.output.absolute()
    if (output.exists() or output.is_symlink() or output.with_suffix('.validation.json').exists()
            or output.is_relative_to(root) or output.is_relative_to(old)):
        raise ValueError('Output must be new and outside the figure roots')
    if any(p.is_symlink() for p in output.parents):
        raise ValueError('Output directory cannot follow a symlink')
    render = json.loads(regular(root/'RENDER_MANIFEST.json').read_text())
    if (render['status'] != 'COMPLETE' or render['visual_review_status'] != 'PASS'
            or render['rendered_count'] != len(EXPECTED_IDS)
            or render['requested_figure_count'] != len(EXPECTED_IDS) or render['failures']):
        raise ValueError('Complete rendering and actual visual review are required')
    source_hash = sha(regular(args.source_package))
    if render['package_sha256'] != source_hash:
        raise ValueError('Render used a different combined scientific package')
    visual = json.loads(regular(root/'VISUAL_REVIEW.json').read_text())
    if visual.get('status') != 'PASS':
        raise ValueError('Visual-review evidence is not PASS')
    reviews = {item['figure_id']: item for item in visual['figures']}
    if len(visual['figures']) != len(EXPECTED_IDS) or set(reviews) != EXPECTED_IDS:
        raise ValueError('Visual-review figure identity coverage mismatch')
    regular(root/'FIGURE_INDEX.md')
    with regular(root/'FIGURE_INDEX.csv').open(newline='') as stream:
        index = list(csv.DictReader(stream))
    if (len(index) != len(EXPECTED_IDS) or {row['figure_id'] for row in index} != EXPECTED_IDS
            or any(row['status'] != 'RENDERED' for row in index)):
        raise ValueError('Figure index coverage mismatch')
    figure_manifests = sorted(root.glob('*/FIGURE_MANIFEST.json'))
    if len(figure_manifests) != render['requested_figure_count']:
        raise ValueError('Figure-manifest coverage mismatch')
    if {path.parent.name for path in figure_manifests} != EXPECTED_IDS:
        raise ValueError('Figure directory identity coverage mismatch')
    for path in figure_manifests:
        figure = json.loads(regular(path).read_text())
        expected_evaluator = ('NOT_APPLICABLE_NATIVE_DIAGNOSTIC'
                              if figure['figure_id'] in {'FIG01', 'FIG03', 'FIG04'} else 'v3')
        if (figure['status'] != 'RENDERED' or figure['package_sha256'] != source_hash
                or figure['proposed_method'] != 'F04' or figure['evaluator'] != expected_evaluator
                or figure['figure_id'] != path.parent.name or not figure['qa']
                or set(figure['outputs']) != {'png', 'pdf', 'svg'}
                or not all(item['pass'] for item in figure['qa'])):
            raise ValueError('Figure provenance or QA mismatch: '+str(path))
        for extension, identity in figure['outputs'].items():
            relative = Path(identity['path'])
            if (relative.is_absolute() or '..' in relative.parts
                    or relative != Path(figure['figure_id'])/(figure['figure_id']+'.'+extension)
                    or regular(root/relative).stat().st_size == 0
                    or sha(regular(root/relative)) != identity['sha256']):
                raise ValueError('Figure export bytes changed: '+str(path))
        review = reviews[figure['figure_id']]
        if review['status'] != 'PASS' or review['png_sha256'] != figure['outputs']['png']['sha256']:
            raise ValueError('Visual review does not match current raster: '+str(path))
    v1 = json.loads(regular(args.v1_audit).read_text())
    old_files = members(old)
    if not old_files or v1['status'] != 'PASS' or set(old_files) != {row['relative_path'] for row in v1['files']}:
        raise ValueError('v1 archive member set changed')
    for identity in v1['files']:
        source = old_files[identity['relative_path']]
        if source.stat().st_size != identity['size_bytes'] or sha(source) != identity['sha256']:
            raise ValueError('v1 figure archive is not byte-identical')
    sources = {'v2/'+name: path for name, path in members(root).items()}
    sources.update({'v1_prereg/'+name: path for name, path in old_files.items()})
    sources['provenance/V1_FIGURE_BYTE_IDENTITY.json'] = regular(args.v1_audit)
    pins = {name: {'sha256': sha(path), 'size_bytes': path.stat().st_size} for name, path in sources.items()}
    manifest = {'schema_version': 'protocol_v2_publication_handoff_v1', 'members': pins,
                'scientific_package_sha256': source_hash, 'figure_count': len(figure_manifests),
                'reissued_count': render['reissued_count'], 'new_count': render['new_count'],
                'supplementary_count': render['supplementary_count'], 'v1_preserved_files': len(old_files),
                'data_mode': render['data_mode'], 'synthetic_data_used': render['synthetic_data_used'],
                'semisynthetic_data_used': render['semisynthetic_data_used'],
                'raw_payload_included': False, 'scientific_execution_performed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sources.items():
            archive.write(path, name)
        archive.writestr('PACKAGE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(pins)+1:
            raise ValueError('Archive CRC or member-count mismatch')
        for name, identity in pins.items():
            payload = archive.read(name)
            if len(payload) != identity['size_bytes'] or hashlib.sha256(payload).hexdigest() != identity['sha256']:
                raise ValueError('Archive member identity mismatch: '+name)
    result = {'status': 'PASS', 'archive': str(output), 'sha256': sha(output),
              'size_bytes': output.stat().st_size, 'members': len(pins)+1,
              'figure_count': len(figure_manifests), 'v1_preserved_files': len(old_files)}
    with output.with_suffix('.validation.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('figure-root', 'v1-root', 'v1-audit', 'source-package', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    print(json.dumps(package(parser.parse_args()), indent=2))


if __name__ == '__main__':
    main()
