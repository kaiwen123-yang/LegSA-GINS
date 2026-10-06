#!/usr/bin/env python3
"""Read existing CLEAN4 EXT01/EXT02 records; never execute scientific code.

Only explicit report/native directories are inspected. Large diagnostic CSVs
stay in place and are registered as metadata-only. JSON numeric tokens and CSV
cells are copied as source strings, without metric calculation or re-hashing.
"""
import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path

FIELDS = ('record_id stage record_kind method_id paper implementation_version '
          'sequence_id case_id config_id start_policy input_identity native_status '
          'evaluation_status metric_source source_row_key source_values_json '
          'native_output_paths evaluation_paths figure_paths read_depth retention_status '
          'archive_path archive_member notes').split()
csv.field_size_limit(16_000_000)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--roots', type=Path, required=True)
    args = ap.parse_args()
    roots = json.loads(args.roots.read_text())['aliases']
    code = Path(roots['<CODE_ROOT>'])
    stage = Path(roots['<CLEAN_ROOT>']) / 'stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON'
    out = code / 'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_clean'
    copies = out / 'ext01_ext02_sources'
    copies.mkdir(parents=True, exist_ok=True)
    pairs = sorted(((v.rstrip('/'), k) for k, v in roots.items()), key=lambda x: -len(x[0]))

    def portable(text):
        for physical, alias in pairs:
            text = text.replace(physical, alias)
        return text

    rows, local_rows, reads, loaded = [], [], [], {}
    papers = {'EXT01': 'Teunissen C-LAMBDA; original registry identity retained',
              'EXT02': 'Liu et al. 2022 CWLS; DOI 10.1109/TIM.2022.3193412'}

    def record(path, method, version, kind, values, key, depth, notes='', native='', evaluation=''):
        row = dict.fromkeys(FIELDS, '')
        row.update(record_id='C4_RAW_%06d' % (len(rows) + 1), stage=stage.name,
                   record_kind=kind, method_id=method, paper=papers[method],
                   implementation_version=version, sequence_id='BY2', case_id='C00',
                   config_id='see source contract/config_hash', start_policy='SOURCE_NATIVE_EPOCH_SUPPORT',
                   input_identity='recorded raw/provider hashes in source summary; not rehashed',
                   native_status=native or 'see source terminal/status fields',
                   evaluation_status=evaluation or 'POST_NATIVE_DESCRIPTIVE_DIAGNOSTICS',
                   metric_source=str(path), source_row_key=key,
                   source_values_json=json.dumps(values, ensure_ascii=False, separators=(',', ':')),
                   native_output_paths=str(path.parent) if '/11_REPORT/' not in str(path) else '',
                   read_depth=depth, retention_status='EXISTS_READABLE' if path.exists() else 'NOT_FOUND',
                   notes=notes)
        local_rows.append(row.copy())
        rows.append({k: portable(v) for k, v in row.items()})

    json_specs = [
        ('11_REPORT/PHASE1_STATUS.json', 'EXT01', 'PHASE1_EARLY_SUPERSEDED'),
        ('11_REPORT/PHASE1R_STATUS.json', 'EXT01', 'PHASE1R_R1_BLOCKED_PRESERVED'),
        ('11_REPORT/PHASE1R_R2_STATUS.json', 'EXT01', 'PHASE1R_R2'),
        ('02_EXT01_CLAMBDA/C00_VALIDATED_R2/EXT01_C00_VALIDATED_SUMMARY.json', 'EXT01', 'PHASE1R_R2'),
        ('02_EXT01_CLAMBDA/C00_VALIDATED_R2/PHASE1R_NATIVE_FREEZE.json', 'EXT01', 'PHASE1R_R2'),
        ('02_EXT01_CLAMBDA/C00_VALIDATED_R2/RTKLIB_DIAGNOSTIC_GPS_L1_SUMMARY.json', 'EXT01', 'PHASE1R_R2_DIAGNOSTIC_ONLY'),
        ('03_EXT02_CWLS/C00/ATTEMPT_IDENTITY.json', 'EXT02', 'PHASE2_NATIVE'),
        ('03_EXT02_CWLS/C00/EXT02_C00_NATIVE_FREEZE.json', 'EXT02', 'PHASE2_NATIVE'),
        ('03_EXT02_CWLS/C00/EXT02_C00_NATIVE_SUMMARY.json', 'EXT02', 'PHASE2_NATIVE'),
        ('03_EXT02_CWLS/C00/EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json', 'EXT02', 'PHASE2_PRIMARY_POST_PRESERVED'),
        ('03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1/EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json', 'EXT02', 'PHASE2_PROXY_TIME_ASSOCIATION_R1'),
        ('03_EXT02_CWLS/C00/RESOURCE_DETERMINISM_PROBE.json', 'EXT02', 'PHASE2_NATIVE'),
        ('11_REPORT/PHASE2_STATUS.json', 'EXT02', 'PHASE2_CURRENT_AMENDED_PRIMARY'),
        ('11_REPORT/PHASE2_STATUS_PROXY_TIME_ASSOCIATION_R1.json', 'EXT02', 'PHASE2_PROXY_TIME_ASSOCIATION_R1'),
    ]
    for rel, method, version in json_specs:
        p = stage / rel
        raw = p.read_text(encoding='utf-8-sig')
        obj = json.loads(raw, parse_float=str, parse_int=str)
        loaded[rel] = obj
        destination = copies / (rel.replace('/', '__'))
        destination.write_text(portable(raw), encoding='utf-8')
        record(p, method, version, 'FILE', {'bytes': str(p.stat().st_size), 'top_level_keys': list(obj),
              'portable_copy': '<CODE_ROOT>/' + str(destination.relative_to(code))}, '$', 'FULL_JSON_PARSE',
              'All JSON read. Copy changes path prefixes only. Hash fields are recorded, not newly verified.',
              obj.get('terminal_status', ''), obj.get('evaluation', ''))
        reads.append({'source_path': portable(str(p)), 'read_depth': 'FULL_JSON_PARSE', 'top_level_keys': len(obj)})
        # Top-level values preserve every original leaf (including numeric token text).
        for key, value in obj.items():
            if key in {'output_hashes', 'raw_source_hashes', 'prior_primary_post_inventory', 'runtime_source_hashes',
                       'native_runtime_source_hashes', 'post_native_runtime_source_hashes'}:
                # Exact complete maps remain available in the path-normalized source copy.
                continue
            if len(json.dumps(value, ensure_ascii=False)) > 60_000:
                # Large provenance maps remain complete in the source copy; keep the
                # browser index usable with ordinary CSV field limits.
                continue
            record(p, method, version, 'SOURCE_JSON_FIELD', {key: value}, '$.' + key,
                   'FULL_JSON_PARSE', 'Numbers are lexical source tokens; no recomputation.', obj.get('terminal_status', ''))

    directories = [
        ('02_EXT01_CLAMBDA/C00_VALIDATED_R2', 'EXT01', 'PHASE1R_R2'),
        ('03_EXT02_CWLS/C00', 'EXT02', 'PHASE2_NATIVE_OR_PRIMARY_POST'),
        ('03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1', 'EXT02', 'PHASE2_PROXY_TIME_ASSOCIATION_R1'),
    ]
    for rel, method, version in directories:
        for p in sorted((stage / rel).glob('*.csv')):
            size = p.stat().st_size
            if size > 2_000_000:
                record(p, method, version, 'LARGE_DIAGNOSTIC_PAYLOAD', {'bytes': str(size)}, 'FILE',
                       'STAT_ONLY_NO_PAYLOAD_OPEN', 'Presence is not full reading; no new hash or metric.')
                reads.append({'source_path': portable(str(p)), 'read_depth': 'STAT_ONLY_NO_PAYLOAD_OPEN', 'bytes': size})
                continue
            raw = p.read_text(encoding='utf-8-sig')
            parsed = csv.DictReader(io.StringIO(raw))
            headers = parsed.fieldnames
            source_rows = list(parsed)
            counts = {}
            for col in ('failure_code', 'status', 'native_status', 'solution_status', 'search_status', 'success'):
                if col in headers:
                    counts[col] = dict(Counter(row[col] for row in source_rows))
            destination = copies / (str(p.relative_to(stage)).replace('/', '__'))
            # Native per-epoch results and all failures are small necessary result tables.
            # Other detailed diagnostics stay in place after full reading.
            copy = any(s in p.name for s in ('NATIVE_HEADING_RESULTS', 'FAILURE_LEDGER', 'HALF_CYCLE_DIAGNOSTICS'))
            values = {'bytes': str(size), 'row_count': str(len(source_rows)), 'headers': headers,
                      'original_status_token_counts': counts}
            if copy:
                destination.write_text(portable(raw), encoding='utf-8')
                values['portable_copy'] = '<CODE_ROOT>/' + str(destination.relative_to(code))
            record(p, method, version, 'EXISTING_RESULT_TABLE', values, 'ALL_DATA_ROWS_1_BASED', 'FULL_CSV_PARSE',
                   'Full CSV cells read; counts only, no performance recalculation. The file is epoch-level, not a count of native processes.')
            reads.append({'source_path': portable(str(p)), 'read_depth': 'FULL_CSV_PARSE', 'row_count': len(source_rows), 'headers': headers})

    reports = [
        ('11_REPORT/PHASE1R_R2_EXT01_C00_VALIDITY_REPORT.md', 'EXT01', 'PHASE1R_R2'),
        ('11_REPORT/PHASE1R_EXT01_C00_VALIDITY_REPORT.md', 'EXT01', 'PHASE1R_R1_BLOCKED_PRESERVED'),
        ('11_REPORT/PHASE2_EXT02_C00_REPORT_PROXY_TIME_ASSOCIATION_R1.md', 'EXT02', 'PHASE2_PROXY_TIME_ASSOCIATION_R1'),
    ]
    for rel, method, version in reports:
        p = stage / rel
        raw = p.read_text(encoding='utf-8-sig')
        destination = copies / rel.replace('/', '__')
        destination.write_text(portable(raw), encoding='utf-8')
        record(p, method, version, 'HISTORICAL_REPORT', {'line_count': str(len(raw.splitlines())),
               'portable_copy': '<CODE_ROOT>/' + str(destination.relative_to(code))}, 'ALL_LINES', 'FULL_TEXT_READ',
               'Original conclusion retained as historical diagnosis, not a fresh implementation audit.')
        reads.append({'source_path': portable(str(p)), 'read_depth': 'FULL_TEXT_READ'})

    # Only resolve source/test entrances already named in the historical registry and reports.
    entrypoints = [
        ('EXT01', 'src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py'),
        ('EXT01', 'src/legsa_gins/paper_rebuild/horizontal_literature/phase1r_runner.py'),
        ('EXT01', 'scripts/paper_rebuild/run_horizontal_literature_phase1r.py'),
        ('EXT01', 'configs/paper_rebuild/horizontal_literature/PHASE1R_VALIDATION_CONTRACT_V2.yaml'),
        ('EXT02', 'src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py'),
        ('EXT02', 'src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py'),
        ('EXT02', 'scripts/paper_rebuild/run_horizontal_literature_phase2.py'),
        ('EXT02', 'configs/paper_rebuild/horizontal_literature/PHASE2_EXT02_CWLS_CONTRACT_V1.yaml'),
        ('EXT01', 'tests/paper_rebuild/test_horizontal_ext01_clambda.py'),
        ('EXT02', 'tests/paper_rebuild/test_horizontal_ext02_cwls.py'),
        ('EXT02', 'tests/paper_rebuild/test_horizontal_phase2_c00.py'),
    ]
    for method, rel in entrypoints:
        p = code / rel
        record(p, method, 'CURRENT_SOURCE_ENTRY_ONLY_NOT_FROZEN_IDENTITY', 'SOURCE_ENTRY',
               {'exists': p.is_file(), 'bytes': str(p.stat().st_size) if p.is_file() else 'unknown'},
               'FILE', 'STAT_ONLY_NO_IMPLEMENTATION_AUDIT',
               'Entrance only. Never imported, executed, hashed, or asserted equal to historical native source.',
               'NOT_EXECUTED_THIS_COLLECTION', 'NOT_EVALUATED_THIS_COLLECTION')

    def write_csv(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
            w.writeheader()
            w.writerows(data)

    write_csv(out / 'EXT01_EXT02_INDEX.csv', rows)
    local = Path(roots['<EXT_REPRO_ROOT>']) / 'existing_clean.local.csv'
    previous = []
    if local.exists():
        with local.open(newline='', encoding='utf-8') as f:
            previous = [row for row in csv.DictReader(f) if not row['record_id'].startswith('C4_RAW_')]
    write_csv(local, previous + local_rows)
    receipt = {'scope': 'CLEAN4 EXT01 R2 and EXT02 proxy recovery with preserved predecessor summaries',
               'record_count': len(rows), 'read_depth_counts': dict(Counter(x['read_depth'] for x in reads)),
               'csv_data_rows_actually_parsed': sum(x.get('row_count', 0) for x in reads),
               'new_native_calls': 0, 'new_evaluator_calls': 0, 'new_provider_calls': 0,
               'raw_or_reference_payload_opens': 0, 'new_hashes': 0,
               'source_values_policy': 'CSV strings and JSON lexical numeric tokens, path alias substitution only',
               'reads': reads}
    (out / 'EXT01_EXT02_READ_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'reads'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
