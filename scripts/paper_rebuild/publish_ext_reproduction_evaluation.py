#!/usr/bin/env python3
"""Copy completed small evaluation artifacts for review; never evaluate or solve."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roots', required=True)
    parser.add_argument('--sequence', choices=('BY2', 'BY2H', 'BY2O'), required=True)
    args = parser.parse_args()
    roots = json.loads(Path(args.roots).read_text())['aliases']
    source = Path(roots['<EXT_REPRO_ROOT>']) / 'evaluation' / args.sequence
    receipt = json.loads((source / 'EVALUATION_RECEIPT.json').read_text())
    assert receipt['evaluation_status'] == 'COMPLETED'
    audit = json.loads((source / 'ACCESS_AUDIT.json').read_text())
    assert audit['passed'] and audit['reference_successful_opens'] == 1
    target = (Path(roots['<CODE_ROOT>']) / 'docs/paper_rebuild/hext/EXT_REPRODUCTION'
              / 'evaluation_results' / args.sequence)
    target.mkdir(parents=True, exist_ok=False)
    names = ['RESULT_ROWS.csv', 'COMMON_SUPPORT.csv', 'COMMON_SUPPORT_KEYS.json',
             'HEADING_METRICS.json', 'REUSED_METRICS.json', 'REUSE_LIMITATIONS.json',
             'ERROR_SERIES.csv', 'REUSED_ERROR_SERIES.csv', 'V3_REFERENCE.csv',
             'SOURCE_FILES.csv', 'SPEC.json', 'EVALUATION_RECEIPT.json',
             'CHILD_RECEIPT.json', 'ACCESS_AUDIT.json']
    plot = source / 'figures/attempt_001/PLOT_RECEIPT.json'
    if plot.exists():
        plot_receipt = json.loads(plot.read_text())
        names.append(str(plot.relative_to(source)))
        if plot_receipt['status'] == 'COMPLETED_VISUAL_REVIEW_PENDING':
            names.append('figures/attempt_001/HEADING_COMPARISON.png')
    records = []
    for name in names:
        original = source / name
        payload = original.read_bytes()
        assert len(payload) < 8_000_000, (name, len(payload))
        if original.suffix != '.png':
            text = payload.decode('utf-8')
            assert '/home/' not in text and '/mnt/' not in text, name
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        sha = hashlib.sha256(payload).hexdigest()
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == sha
        records.append({'source_path': f'<EXT_REPRO_ROOT>/evaluation/{args.sequence}/{name}',
                        'public_relative_path': str(destination.relative_to(target)),
                        'bytes': len(payload), 'sha256_newly_verified_copy': sha,
                        'read_depth': 'FULL_PAYLOAD_READ_BYTE_COPY',
                        'visual_review': 'PENDING_SEPARATE_REVIEW' if name.endswith('.png') else 'NOT_APPLICABLE'})
    with (target / 'COPY_RECEIPT.csv').open('x', newline='') as handle:
        writer = csv.DictWriter(handle, list(records[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(records)
    print(json.dumps({'sequence': args.sequence, 'copied_files': len(records),
                      'new_solver_calls': 0, 'new_evaluator_calls': 0, 'reference_opens': 0}))


if __name__ == '__main__':
    main()
