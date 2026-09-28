#!/usr/bin/env python3
"""Package 28 verified v2.1 figures and audit the unchanged v1/v2 editions."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile

from pack_protocol_v2_figures import members, regular, sha

EXPECTED_IDS = ({f'MFIG{n:02d}' for n in range(23)} - {'MFIG21'}
                | {'SFIG01', 'SFIG02'} | {f'FIG{n:02d}' for n in range(1, 5)})


def preserved_editions(args):
    package = regular(args.preserved_package)
    if sha(package) != args.preserved_package_sha256:
        raise ValueError('Frozen v2 figure package hash changed')
    evidence = {'status': 'PASS', 'package_sha256': args.preserved_package_sha256,
                'MFIG21_policy': 'original v2 bytes retained; no v2.1 render', 'editions': {}}
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None or len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError('Frozen figure package CRC or uniqueness failure')
        manifest = json.loads(archive.read('PACKAGE_MANIFEST.json'))['members']
        for prefix, root in [('v2', args.v2_root), ('v1_prereg', args.v1_root)]:
            expected = {name[len(prefix)+1:]: pin for name, pin in manifest.items()
                        if name.startswith(prefix+'/')}
            actual = members(root)
            if not expected or set(expected) != set(actual):
                raise ValueError('Preserved edition member coverage changed: '+prefix)
            for relative, pin in expected.items():
                path = actual[relative]
                if path.stat().st_size != pin['size_bytes'] or sha(path) != pin['sha256']:
                    raise ValueError('Preserved edition bytes changed: '+prefix+'/'+relative)
            evidence['editions'][prefix] = {'file_count': len(expected), 'members': expected}
        v2 = evidence['editions']['v2']['members']
        if not all('MFIG21/MFIG21.'+extension in v2 for extension in ('png', 'pdf', 'svg')):
            raise ValueError('Original MFIG21 export pins absent')
    return evidence


def package(args):
    root = args.figure_root.absolute()
    output = args.output.absolute()
    protected = [root, args.v1_root.absolute(), args.v2_root.absolute()]
    if (output.exists() or output.is_symlink() or output.with_suffix('.validation.json').exists()
            or any(output.is_relative_to(path) for path in protected)
            or any(path.is_symlink() for path in output.parents)):
        raise ValueError('Output must be new, without symlinks, and outside figure roots')
    render = json.loads(regular(root/'RENDER_MANIFEST.json').read_text())
    if (render['status'] != 'COMPLETE' or render['visual_review_status'] != 'PASS'
            or render.get('protocol_version') != 'v2.1' or render['failures']
            or render['rendered_count'] != len(EXPECTED_IDS)
            or render['requested_figure_count'] != len(EXPECTED_IDS)):
        raise ValueError('Complete v2.1 rendering and actual raster review required')
    source_hash = sha(regular(args.source_package))
    if render['package_sha256'] != source_hash:
        raise ValueError('Render scientific package identity changed')
    visual = json.loads(regular(root/'VISUAL_REVIEW.json').read_text())
    reviews = {row['figure_id']: row for row in visual['figures']}
    if (visual['status'] != 'PASS' or len(visual['figures']) != len(EXPECTED_IDS)
            or set(reviews) != EXPECTED_IDS):
        raise ValueError('Visual-review coverage mismatch')
    regular(root/'FIGURE_INDEX.md')
    with regular(root/'FIGURE_INDEX.csv').open(newline='') as stream:
        index = list(csv.DictReader(stream))
    if (len(index) != len(EXPECTED_IDS) or {row['figure_id'] for row in index} != EXPECTED_IDS
            or any(row['status'] != 'RENDERED' or row.get('protocol_version') != 'v2.1' for row in index)):
        raise ValueError('v2.1 figure index coverage mismatch')
    manifests = sorted(root.glob('*/FIGURE_MANIFEST.json'))
    if len(manifests) != len(EXPECTED_IDS) or {p.parent.name for p in manifests} != EXPECTED_IDS:
        raise ValueError('Figure manifest coverage mismatch')
    expected_exports = {f'{fid}/{fid}.{extension}' for fid in EXPECTED_IDS for extension in ('png', 'pdf', 'svg')}
    actual_exports = {relative for relative in members(root) if Path(relative).suffix.lower() in {'.png', '.pdf', '.svg'}}
    if (root/'MFIG21').exists() or actual_exports != expected_exports:
        raise ValueError('Expected exactly 84 registered v2.1 exports and no MFIG21 subtree')
    for path in manifests:
        figure = json.loads(regular(path).read_text())
        fid = figure['figure_id']
        evaluator = 'NOT_APPLICABLE_NATIVE_DIAGNOSTIC' if fid in {'FIG01', 'FIG03', 'FIG04'} else 'v3'
        if (fid != path.parent.name or figure['status'] != 'RENDERED'
                or figure.get('protocol_version') != 'v2.1' or figure['package_sha256'] != source_hash
                or figure['proposed_method'] != 'F04' or figure['evaluator'] != evaluator
                or not figure['qa'] or not all(row['pass'] for row in figure['qa'])
                or set(figure['outputs']) != {'png', 'pdf', 'svg'}):
            raise ValueError('Figure provenance or QA mismatch: '+fid)
        for extension, pin in figure['outputs'].items():
            relative = Path(pin['path'])
            if (relative != Path(fid)/(fid+'.'+extension)
                    or regular(root/relative).stat().st_size == 0
                    or sha(regular(root/relative)) != pin['sha256']):
                raise ValueError('Figure export bytes changed: '+fid)
        if reviews[fid]['status'] != 'PASS' or reviews[fid]['png_sha256'] != figure['outputs']['png']['sha256']:
            raise ValueError('Raster review does not match export: '+fid)
    preservation = preserved_editions(args)
    sources = {'v21/'+name: path for name, path in members(root).items()}
    extra_name = 'provenance/PRESERVED_V1_V2_MFIG21.json'
    extra = (json.dumps(preservation, ensure_ascii=False, indent=2)+'\n').encode()
    pins = {name: {'sha256': sha(path), 'size_bytes': path.stat().st_size} for name, path in sources.items()}
    pins[extra_name] = {'sha256': hashlib.sha256(extra).hexdigest(), 'size_bytes': len(extra)}
    manifest = {'schema_version': 'protocol_v21_publication_handoff_v1', 'protocol_version': 'v2.1',
                'members': pins, 'scientific_package_sha256': source_hash,
                'figure_count': len(manifests), 'export_count': 3*len(manifests),
                'reissued_count': render['reissued_count'], 'new_count': render['new_count'],
                'supplementary_count': render['supplementary_count'],
                'data_mode': render['data_mode'], 'synthetic_data_used': render['synthetic_data_used'],
                'semisynthetic_data_used': render['semisynthetic_data_used'],
                'preserved_figure_package_sha256': args.preserved_package_sha256,
                'MFIG21_rerendered': False, 'raw_payload_included': False,
                'scientific_execution_performed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sources.items():
            archive.write(path, name)
        archive.writestr(extra_name, extra)
        archive.writestr('PACKAGE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    with zipfile.ZipFile(output) as archive:
        if (archive.testzip() is not None or len(archive.namelist()) != len(pins)+1
                or len(set(archive.namelist())) != len(archive.namelist())):
            raise ValueError('Archive CRC, uniqueness or count failure')
        for name, pin in pins.items():
            payload = archive.read(name)
            if len(payload) != pin['size_bytes'] or hashlib.sha256(payload).hexdigest() != pin['sha256']:
                raise ValueError('Archive member identity failure: '+name)
    result = {'status': 'PASS', 'archive': str(output), 'sha256': sha(output),
              'size_bytes': output.stat().st_size, 'members': len(pins)+1,
              'figure_count': len(manifests), 'export_count': 3*len(manifests),
              'preserved_edition_files': {key: row['file_count'] for key, row in preservation['editions'].items()},
              'MFIG21_rerendered': False}
    with output.with_suffix('.validation.json').open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('figure-root', 'source-package', 'output', 'preserved-package', 'v1-root', 'v2-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--preserved-package-sha256', required=True)
    print(json.dumps(package(parser.parse_args()), indent=2))


if __name__ == '__main__':
    main()
