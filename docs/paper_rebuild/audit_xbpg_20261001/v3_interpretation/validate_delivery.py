#!/usr/bin/env python3
"""Check delivery scope and small indices. Never open source scientific payloads."""
import argparse
import ast
import collections
import csv
import json
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    args = parser.parse_args()
    repo = args.code_root.resolve()
    base = Path('docs/paper_rebuild/audit_xbpg_20261001/v3_interpretation')
    start = 'd9763ea40fd19963a71321c2a6ca930a022c159d'
    scripts = {'scripts/paper_rebuild/' + name for name in [
        'check_v3_retained_series.py', 'interpret_v3_natural.py', 'interpret_v3_core.py',
        'interpret_v3_addendum.py', 'interpret_v3_evidence.py']}
    def git(*arguments):
        return subprocess.run(['git', *arguments], cwd=repo, check=True,
                              text=True, capture_output=True, timeout=60).stdout.strip()
    assert git('branch', '--show-current') == 'audit/code-xbpg-20260105-20261001'
    assert not git('diff', '--cached', '--name-only'), 'Unreviewed staged files exist'
    git('diff', '--check')
    changes = git('diff', '--name-status', start).splitlines()
    assert all(not x.startswith('D\t') for x in changes)
    changed = {line.split('\t', 1)[1] for line in changes}
    untracked = set(git('ls-files', '--others', '--exclude-standard').splitlines())
    paths = changed | untracked
    assert all(p.startswith(str(base) + '/') or p in scripts for p in paths), 'Unexpected delivery path'
    # The receipt is written after this check; do not claim to validate itself.
    paths.discard(str(base / 'FINAL_DELIVERY_CHECKS.json'))
    old_prefix = 'docs/paper_rebuild/audit_xbpg_20261001/'
    old_audit = [p for p in git('ls-tree', '-r', '--name-only', start, old_prefix).splitlines()
                 if '/v3_results/' not in p and '/v3_interpretation/' not in p]
    assert not (set(old_audit) & changed), 'Original audit changed'
    assert not git('diff', start, '--name-only', old_prefix + 'v3_results'), 'Previous result collection changed'
    scanner = repo / 'scripts/paper_rebuild/check_v3_retained_series.py'
    # Compare the small script bytes through Git, without hashing any payload.
    assert not git('diff', '0593770b2b3837012d155254cfc73448d76990b2', '--', str(scanner.relative_to(repo)))
    total_bytes = 0
    py_count = 0
    csv_files = 0
    csv_rows = 0
    markdown_links = 0
    largest = (0, '')
    for name in sorted(paths):
        file = repo / name
        assert file.is_file() and not file.is_symlink(), name
        size = file.stat().st_size
        assert size < 49_000_000, name
        assert file.suffix not in {'.gz', '.zip', '.nav', '.std', '.pdf', '.exe', '.so', '.o'}, name
        total_bytes += size
        largest = max(largest, (size, name))
        content = file.read_text(encoding='utf-8')
        private_patterns = (r'-----BEGIN [^-]*PRIVATE KEY|github_pat_[A-Za-z0-9_]{15,}|'
                            r'gh[pousr]_[A-Za-z0-9]{20,}|/' + r'home/[A-Za-z0-9_.-]+/|/' + r'mnt/[a-z]/')
        assert not re.search(private_patterns, content), name
        if file.suffix == '.py':
            ast.parse(content, filename=name)
            py_count += 1
        if file.suffix == '.csv':
            with file.open(newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                assert reader.fieldnames
                for row in reader:
                    assert None not in row and all(v is not None for v in row.values()), name
                    csv_rows += 1
            csv_files += 1
        if file.suffix == '.md':
            for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', content):
                if target.startswith(('http:', 'https:', '#', '<')):
                    continue
                target = target.split('#', 1)[0]
                if target:
                    assert (file.parent / target).exists(), (name, target)
                    markdown_links += 1
    summary = json.loads((repo / base / 'series_checks/FULL_READ_SUMMARY.json').read_text())
    assert summary['full_read_error_series'] == 2308 and summary['retained_completed_native'] == 1154
    assert summary['rows_all'] == 131266946 and summary['main_scan_count_distribution'] == {'1': 2309}
    assert summary['metric_check_status_counts'] == {
        'MATCH': 381501, 'MATCH_NULL': 332, 'NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS': 20777}
    with (repo / base / 'RETAINED_SERIES_CHECKS.csv').open() as f:
        retained = list(csv.DictReader(f))
    assert len(retained) == len({r['file_id'] for r in retained}) == 2309
    assert collections.Counter(r['payload_kind'] for r in retained) == {'error_series': 2308, 'matched_trajectory': 1}
    assert all(r['main_scan_count'] == '1' and r['eof_receipt'] == 'FULL_STREAM_TO_GZIP_EOF_CRC_CHECKED'
               and r['evidence_depth'] == 'NUMERICALLY_CHECKED_WITHIN_SCOPE' for r in retained)
    receipt = dict(status='DELIVERY_CHECKS_PASSED_WITH_DOCUMENTED_SCIENTIFIC_LIMITS',
        baseline_commit=start, reviewed_parent_commit=git('rev-parse', 'HEAD'),
        tracked_and_visible_untracked_files_checked=len(paths), bytes_checked=total_bytes,
        generated_receipt_excluded_from_own_check=True,
        maximum_file_bytes=largest[0], maximum_file_path=largest[1],
        old_audit_files_unchanged=len(old_audit), previous_result_collection_unchanged=True,
        original_two_large_indices_unchanged=True, scanner_unchanged_since_frozen_commit=True,
        ast_parsed_scripts=py_count, csv_files_parsed=csv_files, csv_data_rows_parsed=csv_rows,
        local_markdown_links_checked=markdown_links, source_payload_opens=0,
        scientific_execution_calls=0, new_bootstrap_calls=0, data_mode='validation_of_existing_results',
        synthetic_data_used=False, semisynthetic_data_used=True, semisynthetic_data_generated=False,
        validation_calculation=True, final_commit_and_push='RECORDED_BY_GIT_AND_TERMINAL_AFTER_THIS_RECEIPT',
        scientific_correctness_certified=False,
        limitations=['D22/D39 local-window collector omissions', '20777 unsupported checks',
            'released fullNAV/STD and error-series not recreated', 'reference independence and real mechanism triggers not established'])
    (repo / base / 'FINAL_DELIVERY_CHECKS.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
