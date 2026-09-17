#!/usr/bin/env python3
"""Package H03 after its result commit, preserving the H02 hard-stop package."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import yaml

from hext02_package import _create_zip, _verify_zip, _exclusive_copy, _write_json, _sha, _git
from legsa_gins.paper_rebuild.hext import continuation
from legsa_gins.paper_rebuild.hext.figures import verify_frozen_v21

RESULT_SUBJECT = 'feat(hext): H-EXT-03 continuation — complete three-sequence external rows, FIG02S and handoff v2'
PREREG_SUBJECT = 'prereg(hext): H-EXT-03 bounded continuation authorization and contract v1.1'
ZIP_NAME = 'hext_three_sequences_handoff_v2.zip'
OLD_SHA = 'efb64041e5add0b8d47542e446ae80abe3e038a9bdc0ee1d9620f4216764cc15'


def package():
    seq, scratch, archive = continuation.stage_roots()
    freeze = continuation.assert_freeze()
    commit1, commit2 = freeze['code_freeze'], _git(seq.code_root, 'rev-parse', 'HEAD')
    if (_git(seq.code_root, 'log', '-1', '--format=%s') != RESULT_SUBJECT
            or _git(seq.code_root, 'show', '-s', '--format=%s', commit1) != PREREG_SUBJECT):
        raise RuntimeError('H03 exact authorization/result commits required')
    _git(seq.code_root, 'merge-base', '--is-ancestor', commit1, commit2)
    if commit1 == commit2 or _git(seq.code_root, 'status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('Distinct result commit and clean tracked worktree required')
    local = yaml.safe_load((seq.code_root / 'configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml').read_text())['paths']
    handoff = Path(local['handoff_root'])
    original = handoff / 'hext_three_sequences_handoff.zip'
    if _sha(original) != OLD_SHA:
        raise RuntimeError('Original hard-stop package changed')
    summary = json.loads((archive / '08_AGGREGATE/FINAL_SUMMARY.json').read_text())
    if summary['status'] != 'COMPLETED_H_EXT_03_AGGREGATION' or summary['code_commit'] != commit1:
        raise RuntimeError('H03 aggregate freeze/completion mismatch')
    for name, expected in summary['files_sha256'].items():
        if _sha(archive / '08_AGGREGATE' / name) != expected:
            raise RuntimeError('Aggregate changed: ' + name)
    budget = json.loads((archive / '03_CONTINUATION/EXECUTION/BUDGET_LEDGER.json').read_text())
    figure = json.loads((archive / '10_FIGURES/HEXT_RENDER_MANIFEST.json').read_text())
    visual = json.loads((archive / '10_FIGURES/FIG02S_VISUAL_QA.json').read_text())
    if (not all(item['pass'] for item in figure['qa']) or visual['status'] != 'PASS'
            or not figure['original_v21_files_byte_unchanged']):
        raise RuntimeError('Figure automatic/visual/frozen QA incomplete')
    verify_frozen_v21(figure['frozen_v21_before'], seq.clean_root / 'stages/CLEAN6_PUBLICATION_FIGURES/figures/v21')
    continuation._verify_preserved(seq, scratch, archive)
    final_check = json.loads((archive / '03_CONTINUATION/FINAL_CHECK.json').read_text())
    if final_check['status'] != 'PASS_H_EXT_03_FINAL_CHECK':
        raise RuntimeError('Final review not complete')
    target = handoff / ZIP_NAME
    receipt_target = handoff / 'hext_three_sequences_handoff_v2.validation.json'
    if target.exists() or receipt_target.exists():
        raise FileExistsError('H03 package/receipt already exists; no overwrite')
    entries = {}

    def add(path, member, root):
        path = Path(path)
        pure = PurePosixPath(member)
        if pure.is_absolute() or '..' in pure.parts or member in entries:
            raise ValueError('Unsafe or duplicate package member')
        if path.is_symlink() or not path.is_file():
            raise ValueError('Not regular nonsymlink evidence: ' + str(path))
        path.resolve().relative_to(root.resolve())
        if (seq.raw_root in path.resolve().parents or path.suffix in ('.bag', '.fpl')
                or path.name.startswith('trace_')):
            raise ValueError('Raw payload forbidden in package')
        entries[member] = path

    for name in ('00_CONFIG_AUDIT', '01_PROBE', '02_BY2_IDENTITY', '03_PREREG', '03_PROVIDER_CACHE',
                 '03_CONTINUATION', '04_NATIVE_RUNS', '04_ACCESS_AUDITS', '05_GEOMETRIC_AUDIT',
                 '06_V3_NAV_INPUTS', '07_OFFLINE_EVALUATION', '08_AGGREGATE',
                 '09_LEGSA_GAP_DIAGNOSTIC', '10_FIGURES', 'RAW_CHECKPOINTS', '99_HARD_STOP'):
        root = archive / name
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError('Required stage evidence missing: ' + name)
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Evidence symlink forbidden')
            if path.is_file():
                add(path, 'STAGE/' + path.relative_to(archive).as_posix(), archive)
    for path in sorted(scratch.iterdir()):
        if path.is_file():
            add(path, 'H03_BOOKKEEPING/' + path.name, scratch)
    docs = {'AGENTS.md', 'docs/paper_rebuild/CONVERSATION_HANDOFF.md',
            'docs/paper_rebuild/HORIZONTAL_THREE_SEQUENCES.md',
            'configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml'}
    docs.update(str(p.relative_to(seq.code_root)) for p in
                (seq.code_root / 'docs/paper_rebuild/hext').glob('*') if p.suffix in ('.md', '.csv'))
    docs.update(str(p.relative_to(seq.code_root)) for p in
                (seq.code_root / 'scripts/paper_rebuild').glob('hext*.py'))
    docs.update(freeze['source_hashes'])
    for relative in sorted(docs):
        _git(seq.code_root, 'ls-files', '--error-unmatch', '--', relative)
        add(seq.code_root / relative, 'REPOSITORY/' + relative, seq.code_root)
    commits = dict(H_EXT_02_authorization='c9e5133d244e0e3ab1e1385f322fbbf5948ee6d5',
                   H_EXT_02_result='d8f1d013b4c1d68ddb1c2400cbfe35ac46cbea57',
                   H_EXT_03_authorization=commit1, H_EXT_03_result=commit2,
                   code_freeze=commit1, result_commit=commit2,
                   original_hard_stop_package_sha256=OLD_SHA)
    completion = dict(status=summary['status'], budget=budget, failure_counts=summary['failure_classification_counts'],
                      frozen_original_figures_unchanged=True, visual_qa='PASS', final_check=final_check,
                      full_delivery_includes_explicit_algorithm_failure_and_unavailable=True)
    build = scratch / '08_HANDOFF'
    build.mkdir(exist_ok=False)
    built_zip = build / ZIP_NAME
    members = _create_zip(built_zip, entries, commits, completion)
    ext4_validation = _verify_zip(built_zip, members)
    continuation.assert_freeze()
    continuation._verify_preserved(seq, scratch, archive)
    copied = _exclusive_copy(built_zip, target)
    g_validation = _verify_zip(target, members)
    if _sha(original) != OLD_SHA:
        raise RuntimeError('Original v1 package changed after packaging')
    receipt = dict(schema_version='hext.handoff.validation.v2', status='PASS_ZIP_SHA_MEMBERS_CRC',
                   package='<HANDOFF_ROOT>/' + ZIP_NAME, sha256=copied['sha256'], bytes=copied['size_bytes'],
                   member_count=len(members), members=members, CRC='PASS', git_commits=commits,
                   ext4_validation=ext4_validation, archived_validation=g_validation,
                   archive_copy_retries=copied['retries'], completion=completion,
                   data_mode='real_external_and_frozen_comparison', synthetic_data_used=False,
                   semisynthetic_data_used=False, native_invocation_count=0, evaluator_invocation_count=0,
                   trace_open_count=0, raw_payload_open_count=0, old_package_preserved=True)
    local_receipt = build / receipt_target.name
    _write_json(local_receipt, receipt)
    _exclusive_copy(local_receipt, receipt_target)
    compact = {k: receipt[k] for k in ('status', 'package', 'sha256', 'bytes', 'member_count', 'CRC', 'git_commits')}
    compact['receipt'] = '<HANDOFF_ROOT>/' + receipt_target.name
    compact['receipt_sha256'] = _sha(receipt_target)
    _write_json(build / 'FINAL_HANDOFF_RECEIPT.json', compact)
    _exclusive_copy(build / 'FINAL_HANDOFF_RECEIPT.json', archive / '03_CONTINUATION/FINAL_HANDOFF_RECEIPT.json')
    return compact


if __name__ == '__main__':
    print(json.dumps(package(), ensure_ascii=False, indent=2))
