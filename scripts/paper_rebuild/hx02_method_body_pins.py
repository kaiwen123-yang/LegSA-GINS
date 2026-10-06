#!/usr/bin/env python3
"""HX-02 method-body pins: SHA-256 of every file that must stay byte-identical (read-only).

Covers the five external method modules, hartley_h5.py and every hartley_inekf C++ source,
the whole $EXTERNAL/GINav tree, RTKLIB rnx2rtkp and the two rtklib_bridge shared objects.
With --compare, the new listing is checked item by item against an earlier record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CODE_FILES = tuple('src/legsa_gins/paper_rebuild/horizontal_literature/' + name for name in (
    'ext01_clambda.py', 'ext02_cwls.py', 'ext03_yang2024.py', 'ext04_wu2025.py', 'ext05_pavlasek.py', 'hartley_h5.py'))
CODE_TREES = ('src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf',)
EXTERNAL_TREES = ('GINav',)
EXTERNAL_FILES = ('RTKLIB/app/consapp/rnx2rtkp/gcc/rnx2rtkp', 'rtklib_bridge/lib/liblegsa_rtklib_bridge.so',
                  'rtklib_bridge/lib/librtklib_legsa.so')
RNX2RTKP_SHA256 = '3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def local_path(paths_config: Path, key: str) -> Path:
    for line in paths_config.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith(key + ':'):
            return Path(stripped.split(':', 1)[1].strip())
    raise KeyError(key)


def tree_files(root: Path):
    for item in sorted(root.rglob('*')):
        if item.is_symlink():
            yield item, 'SYMLINK:' + str(item.readlink())
        elif item.is_file() and '__pycache__' not in item.parts:
            yield item, sha256_file(item)


def listing(code_root: Path, external_root: Path) -> dict:
    items = {}
    for rel in CODE_FILES:
        items['$W/' + rel] = sha256_file(code_root / rel)
    for rel in CODE_TREES:
        for item, value in tree_files(code_root / rel):
            items['$W/' + item.relative_to(code_root).as_posix()] = value
    for rel in EXTERNAL_TREES:
        for item, value in tree_files(external_root / rel):
            items['$EXTERNAL/' + item.relative_to(external_root).as_posix()] = value
    for rel in EXTERNAL_FILES:
        items['$EXTERNAL/' + rel] = sha256_file(external_root / rel)
    tree = hashlib.sha256('\n'.join(f'{k}\t{v}' for k, v in sorted(items.items())).encode()).hexdigest()
    return {'items': items, 'item_count': len(items), 'listing_sha256': tree,
            'ginav_file_count': sum(1 for k in items if k.startswith('$EXTERNAL/GINav/')),
            'rnx2rtkp_matches_registered': items['$EXTERNAL/RTKLIB/app/consapp/rnx2rtkp/gcc/rnx2rtkp'] == RNX2RTKP_SHA256}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paths-config', type=Path, required=True)
    parser.add_argument('--external-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--compare', type=Path, help='earlier record to compare with')
    args = parser.parse_args()
    code_root = local_path(args.paths_config, 'code_root')
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'code_root': '$W', 'external_root': '$EXTERNAL'}
    result.update(listing(code_root, args.external_root))
    status = 'PASS' if result['rnx2rtkp_matches_registered'] else 'HARD_STOP'
    if args.compare:
        before = json.loads(args.compare.read_text(encoding='utf-8'))['items']
        changed = sorted(k for k in set(before) | set(result['items']) if before.get(k) != result['items'].get(k))
        result['compare_to'] = args.compare.name
        result['changed_items'] = changed
        if changed:
            status = 'HARD_STOP'
    result['status'] = status
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in result if k != 'items'}, indent=2))
    return 0 if status == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
