#!/usr/bin/env python3
"""Read retained records for P-09 C5 without invoking scientific processes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import io
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.storage_purge import _read, _absolute_without_links, _parent_fd


def digest(path):
    return hashlib.sha256(_read(path)).hexdigest()


def main():
    if not __debug__:
        raise RuntimeError('Optimized Python is forbidden for P-09 record checks')
    ap = argparse.ArgumentParser()
    ap.add_argument('--clean-root', type=Path, required=True)
    ap.add_argument('--code-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--baseline', type=Path)
    args = ap.parse_args()
    clean, code = args.clean_root, args.code_root
    records = {}

    def safe(path):
        path = _absolute_without_links(path)
        assert (clean/'stages' in path.parents or code in path.parents), str(path)
        assert path.suffix.lower() not in ('.bag', '.fpl'), str(path)
        assert '/data/raw/' not in str(path) and path.name.lower() != 'trace.csv', str(path)
        return path

    def read(path):
        path = safe(path)
        alias = '<CLEAN_ROOT>/'+str(path.relative_to(clean)) if clean in path.parents else '<CODE_ROOT>/'+str(path.relative_to(code))
        if path.suffix == '.json':
            data = json.loads(_read(path))
            count = len(data)
        elif path.suffix == '.csv':
            with io.StringIO(_read(path).decode(), newline='') as f:
                reader = csv.reader(f, strict=True)
                header = next(reader)
                assert header, alias
                count = sum(1 for _ in reader)
            data = None
        else:
            data, count = None, None
        records[alias] = {'sha256': digest(path), 'bytes': path.stat().st_size, 'rows_or_keys': count}
        return data

    # All CLEAN5 aggregate trees, including P02/P03/P04/P05/P07 and CAL versions.
    import os
    aggregate_files = []
    for stage in sorted((clean/'stages').iterdir()):
        if not stage.name.startswith('CLEAN5') or not stage.is_dir() or stage.is_symlink():
            continue
        for parent, dirs, files in os.walk(stage, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(parent)/d).is_symlink()]
            if not any('AGGREGATE' in s for s in Path(parent).relative_to(stage).parts):
                continue
            for name in sorted(files):
                path = Path(parent)/name
                if path.suffix in ('.csv', '.json'):
                    read(path)
                    aggregate_files.append('<CLEAN_ROOT>/'+str(path.relative_to(clean)))
    decision = read(clean/'stages/CLEAN5_DECISION/A04_F04_DECISION_INPUTS.json')
    assert decision['extraction_status'] == 'PASS'
    rule_provenance = None
    for role, source in decision['sources'].items():
        value = source['file']
        if value.startswith('<CLEAN_ROOT>/'):
            path = clean/value.removeprefix('<CLEAN_ROOT>/')
        elif value.startswith('<CODE_ROOT>/'):
            path = code/value.removeprefix('<CODE_ROOT>/')
        else:
            raise ValueError('Unexpected decision source alias: '+value)
        read(path)
        if role == 'rule':
            # The rule explicitly permits filling only the Outcome block.
            # Its decision-input hash pins the pre-outcome Git document.
            baseline_commit = '09caf1e7e6151f18cc25dafad4a7ef5704ae62d2'
            before = subprocess.check_output(['git', 'show', baseline_commit+':'+str(path.relative_to(code))], cwd=code)
            assert hashlib.sha256(before).hexdigest() == source['sha256']
            marker = b'## Outcome (append only, after both sequences are sealed and evaluated)\n\n```text\n'
            def outside_outcome(data):
                assert data.count(marker) == 1
                start = data.index(marker)+len(marker)
                end = data.index(b'```', start)
                return data[:start], data[end:]
            assert outside_outcome(before) == outside_outcome(_read(path)), 'Rule changed outside permitted Outcome'
            rule_provenance = {'status': 'PASS_OUTCOME_ONLY_APPEND', 'baseline_commit': baseline_commit,
                               'frozen_sha256': source['sha256'], 'current_sha256': digest(path)}
        else:
            assert digest(path) == source['sha256'], value
    cal = clean/'stages/CLEAN5_CALIBRATED_SENSOR_MODEL'
    terminal = read(cal/'CALIBRATED_TERMINAL.json')
    assert terminal['status'] == 'COMPLETED' and terminal['run_count'] == 15
    expected = {f'CLEAN5_CALIBRATED_{ds}_{cfg}' for ds in ('BY2', 'BY2H', 'BY2O')
                for cfg in ('F01', 'F02', 'F03', 'A04', 'F04')}
    runs = {p.name for p in (cal/'03_CALIBRATED_RUNS').iterdir() if p.is_dir()}
    assert runs == expected
    for name in sorted(runs):
        run = cal/'03_CALIBRATED_RUNS'/name
        for file in ('RUN_MANIFEST.json', 'CALIBRATED_RUN_MANIFEST.json', 'PORT_INPUT_TIMELINE_SNAPSHOT.json'):
            read(run/file)
        for file in ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt', 'LegSA_PORT_NAV.nav', 'LegSA_PORT_STD.csv'):
            path = run/file
            safe(path)
            assert path.is_file() and not path.is_symlink() and path.stat().st_size > 0
            # Readability, not a new all-payload seal.
            import os
            with _parent_fd(path) as (parent, name):
                fd = os.open(name, os.O_RDONLY|os.O_NOFOLLOW, dir_fd=parent)
                try:
                    assert os.read(fd, 128)
                finally:
                    os.close(fd)
    for rel in ('08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv', '08_AGGREGATE/v3/UNIQUE_EVALUATION_RESULTS.csv'):
        alias = '<CLEAN_ROOT>/'+str((cal/rel).relative_to(clean))
        assert records[alias]['rows_or_keys'] == 15
    result = {'status': 'PASS', 'checks': {'decision_readability': 'PASS',
              'aggregate_readability': 'PASS', 'three_sequence_CAL_readability': 'PASS'},
              'records': records, 'aggregate_file_count': len(aggregate_files),
              'rule_provenance': rule_provenance,
              'CAL_run_count': len(runs), 'solver_invocations': 0,
              'evaluator_invocations': 0, 'raw_content_open_count': 0}
    if args.baseline:
        before = json.loads(_read(args.baseline))
        assert records == before['records'], 'Retained record identity or row count changed'
        result['baseline_sha256'] = digest(args.baseline)
        result['records_identical_to_baseline'] = True
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}))


if __name__ == '__main__':
    main()
