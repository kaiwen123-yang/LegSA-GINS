#!/usr/bin/env python3
"""P-09 reference retention from the specified handoffs; metadata only."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
import sys
import os
from contextlib import contextmanager

import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.storage_purge import _absolute_without_links, _parent_fd, _read


@contextmanager
def safe_zip(path):
    path = _absolute_without_links(path)
    if path.parent != Path.home() or path.name not in ('c541_handoff.zip', 'clean5_handoff.zip', 'clean5_handoff_v2.zip'):
        raise ValueError('Only the three human-specified HOME handoff ZIPs may be opened')
    with _parent_fd(path) as (parent, name):
        fd = os.open(name, os.O_RDONLY|os.O_NOFOLLOW, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            with zipfile.ZipFile(stream) as z:
                yield z


def main():
    if not __debug__:
        raise RuntimeError('Optimized Python is forbidden for P-09 reference checks')
    ap = argparse.ArgumentParser()
    ap.add_argument('--clean-root', type=Path, required=True)
    ap.add_argument('--code-root', type=Path, required=True)
    ap.add_argument('--policy', type=Path, required=True)
    ap.add_argument('--mapping', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    clean, code = args.clean_root.absolute(), args.code_root.absolute()
    home = Path.home()
    policy = yaml.safe_load(_read(args.policy))
    mapping = json.loads(_read(args.mapping))
    f = policy['bulk_deletable']['families']
    canonical = clean/'stages'/f['canonical541_v1']['stage']/f['canonical541_v1']['attempt']
    parity = clean/'stages'/f['clean5_parity_ladder_and_p05']['stage']
    cal = clean/'stages'/'CLEAN5_CALIBRATED_SENSOR_MODEL'
    aliases = {'<CLEAN_ROOT>': clean, '<CODE_ROOT>': code,
               '<HOME>': home, '<USER_HOME>': home}
    required, keep_files, keep_dirs, missing, package_edges = {}, set(), set(), [], []

    def resolve(value):
        for alias, root in aliases.items():
            if value == alias or value.startswith(alias+'/'):
                return root/value[len(alias):].lstrip('/')
        return Path(value).expanduser()

    def portable(p):
        # Specific roots before HOME.
        for alias in ('<CLEAN_ROOT>', '<CODE_ROOT>', '<HOME>'):
            root = aliases[alias]
            if p == root and alias != '<HOME>':
                continue
            if p == root or root in p.parents:
                return alias+'/'+p.relative_to(root).as_posix()
        raise ValueError('Unmapped external reference: '+str(p))

    def add(value, source, recursive=False):
        p = resolve(str(value))
        if not p.is_absolute():
            raise ValueError('Unresolved reference: '+str(value))
        p = _absolute_without_links(p, missing=True)
        key = portable(p)
        kind = 'directory' if p.is_dir() else 'file'
        if not p.exists():
            missing.append({'path': key, 'source': source})
        row = required.setdefault(key, {'path': key, 'kind': kind, 'sources': []})
        if source not in row['sources']:
            row['sources'].append(source)
        if clean in p.parents:
            rel = p.relative_to(clean).as_posix()
            if kind == 'file':
                keep_files.add(rel)
            elif recursive:
                keep_dirs.add(rel)
        return key

    for path in ('AGENTS.md', 'docs/paper_rebuild/CONVERSATION_HANDOFF.md'):
        add(code/path, 'human_C2_document')
    add(canonical, 'AGENTS_section_3')
    # Exact code-block directory and file references in AGENTS section 3.
    agents = _read(code/'AGENTS.md').decode().split('## 3.', 1)[1].split('## 4.', 1)[0]
    for line in agents.splitlines():
        text = line.strip()
        if text.startswith('<CANONICAL541_ATTEMPT>/'):
            add(canonical/text.split('/', 1)[1], 'AGENTS_section_3')
        elif re.match(r'(12_OFFLINE_EVALUATION|13_AGGREGATE)/[^ ]+\.(csv|json)$', text):
            add(canonical/text, 'AGENTS_section_3')
    publication = clean/'stages'/'CLEAN6_PUBLICATION_FIGURES'
    for suffix in ('', '01_CANONICAL541/00_DERIVED_TABLES', '01_CANONICAL541/01_FIGURES_BY2_DRAFT'):
        add(publication/suffix, 'AGENTS_section_3')
    seqfiles = re.findall(r'^08_AGGREGATE/[^\s]+\.(?:csv|json)$', agents, re.M)
    for stage in f['clean5_sequences_v1_v2']['stages']:
        root = clean/'stages'/stage
        add(root, 'AGENTS_section_3_and_handoff_section_6')
        for rel in seqfiles:
            add(root/rel, 'AGENTS_section_3')
        for rel in ('08_AGGREGATE', '07_OFFLINE_EVALUATION/PER_RUN',
                    '02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json', '01_SEQUENCE_CONTRACT',
                    '01_SEQUENCE_CONTRACT/C04B_CONTINUATION_2_ba7d380bb11d/EVENT_WINDOW_V2.json'):
            add(root/rel, 'handoff_section_6')
        if 'BY2O' in stage:
            add(root/'01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json', 'handoff_section_6')
    decision = clean/'stages'/'CLEAN5_DECISION'
    add(decision, 'handoff_section_6')
    add(decision/'A04_F04_DECISION_INPUTS.json', 'AGENTS_section_3')
    for rel in ('', '08_AGGREGATE', '10_IMU_PROCESSING/08_AGGREGATE',
                '11_VERTICAL_DIAGNOSIS', '12_PARITY_GENERALIZATION/08_AGGREGATE',
                '13_NOISE_MODEL_SENSITIVITY/08_AGGREGATE'):
        add(parity/rel, 'handoff_section_6')
    for rel in ('', '00_CALIBRATION', '08_AGGREGATE', '08_AGGREGATE/v3',
                '08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.json',
                '08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.csv'):
        add(cal/rel, 'handoff_section_6', recursive=rel == '')
    for name in ('CLEAN5_STAGE2_CLOSEOUT.md', 'CLEAN5_CALIBRATED_CHAIN_RESULTS.md'):
        add(code/'docs/paper_rebuild'/name, 'handoff_section_6')
    for name in ('clean5_pack_v1.py', 'clean5_pack_v2.py'):
        add(code/'scripts/paper_rebuild'/name, 'handoff_section_6')
    horizontal = clean/'stages'/f['clean4_nonfinal_attempts']['stage']
    add(horizontal/'13_HORIZONTAL_CROSS_LAYER_SYNTHESIS', 'handoff_section_6')
    for row in mapping['required_paths']:
        add(row['path'], row['source'], row.get('recursive_keep', False))

    for value in mapping.get('frozen_source_paths', []):
        path = resolve(value)
        _absolute_without_links(path)
        if not (clean/'stages' in path.parents or code in path.parents):
            raise ValueError('Frozen mapping evidence outside record roots')
        if path.suffix.lower() not in ('.csv', '.json', '.md', '.yaml', '.yml') or '/data/raw/' in str(path):
            raise ValueError('Frozen mapping evidence must be metadata')

    def visit(d, source):
        if isinstance(d, dict):
            for k, value in d.items():
                if k in ('source_path', 'source_alias', 'seal_alias', 'source') and isinstance(value, str):
                    if value.startswith(('/', '<CLEAN_ROOT>', '<CODE_ROOT>', '<USER_HOME>', '<HOME>')):
                        if '#' in value:
                            archive, member = value.split('#', 1)
                            path = resolve(archive)
                            add(path, source)
                            with safe_zip(path) as z:
                                z.getinfo(member)
                            package_edges.append({'source': source, 'archive': portable(path), 'member': member})
                        else:
                            add(value, source)
                else:
                    visit(value, source)
        elif isinstance(d, list):
            for value in d:
                visit(value, source)

    with safe_zip(home/'clean5_handoff.zip') as z:
        v1 = json.loads(z.read('IDENTITY_PROBE.json'))
        bymember = {row['member']: row for row in v1['entries']}
        v1subset = list(csv.DictReader(io.StringIO(z.read('BY2/error_series_subset/SUBSET_MANIFEST.csv').decode())))
    for archive in ('clean5_handoff.zip', 'clean5_handoff_v2.zip'):
        add(home/archive, 'human_C2_package')
        with safe_zip(home/archive) as z:
            for member in ('IDENTITY_PROBE.json', 'STAGE2/IDENTITY_PROBE.json'):
                if member in z.namelist():
                    visit(json.loads(z.read(member)), '<HOME>/'+archive+'#'+member)
    add(home/'c541_handoff.zip', 'human_C2_package')
    generated = {'IDENTITY_PROBE.json', 'HEADERS.json', 'LAYOUT.txt', 'error_series_subset/SUBSET_MANIFEST.csv'}
    navruns = {'single_antenna_EKF': ('08_FULL_ALGORITHM_RUNS', 'RUN_00001'),
               'basic_dual_yaw_EKF': ('08_FULL_ALGORITHM_RUNS', 'RUN_00002'),
               'AB0000': ('08_FULL_ALGORITHM_RUNS', 'RUN_00003'),
               'AB1111': ('08_FULL_ALGORITHM_RUNS', 'RUN_00004'),
               'AB1011': ('10_INTERNAL_ABLATION_RUNS', 'RUN_00006')}
    with safe_zip(home/'c541_handoff.zip') as z:
        subset = list(csv.DictReader(io.StringIO(z.read('error_series_subset/SUBSET_MANIFEST.csv').decode())))
        assert {r['run_id'] for r in subset} == {r['run_id'] for r in v1subset}
        for member in z.namelist():
            origin = '<HOME>/c541_handoff.zip#'+member
            if member in generated or member.endswith('/'):
                package_edges.append({'source': origin, 'role': 'package_generated_metadata_or_directory'})
                continue
            if member.startswith('C00_NAV_'):
                cfg = member.removeprefix('C00_NAV_').removesuffix('.nav.gz')
                parent, run = navruns[cfg]
                p = canonical/parent/run/'KF_GINS_Navresult.nav'
                assert any(row.get('source_path') == str(p) for row in v1['entries'])
                add(p, origin)
            else:
                row = bymember['BY2/'+member]
                add(row['source_path'], origin)

    result = {
        'schema_version': 'clean6.storage_reference_closure.v1',
        'keep_files': sorted(keep_files), 'keep_dirs': sorted(keep_dirs),
        'required_paths': sorted(required.values(), key=lambda r: r['path']),
        'protected_dir_entries': sorted(r['path'].removeprefix('<CLEAN_ROOT>/') for r in required.values()
                                        if r['kind'] == 'directory' and r['path'].startswith('<CLEAN_ROOT>/')),
        'superseded_attempt_dirs': mapping['superseded_attempt_dirs'],
        'clean4_nonfinal_attempt_dirs': mapping['clean4_nonfinal_attempt_dirs'],
        'superseded_evidence': mapping.get('superseded_evidence', {}),
        'seal_sources': mapping.get('seal_sources', []),
        'package_edges': package_edges,
        'unresolved_required_paths': missing,
        'source_documents_sha256': {name: hashlib.sha256(_read(code/name)).hexdigest()
                                    for name in ('AGENTS.md', 'docs/paper_rebuild/CONVERSATION_HANDOFF.md')},
        'frozen_source_sha256': {
            **{portable(resolve(path)): hashlib.sha256(_read(resolve(path))).hexdigest()
               for path in mapping.get('frozen_source_paths', [])},
            **{portable(home/name): hashlib.sha256(_read(home/name)).hexdigest()
               for name in ('c541_handoff.zip', 'clean5_handoff.zip', 'clean5_handoff_v2.zip')},
        },
        'C2_reference_discovery_status': 'PASS' if not missing else 'FAIL',
        'scientific_execution_count': 0, 'raw_content_open_count': 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write('\n')
    print(json.dumps({'required_paths': len(required), 'keep_files': len(keep_files),
                      'keep_dirs': len(keep_dirs), 'missing': missing}))


if __name__ == '__main__':
    main()
