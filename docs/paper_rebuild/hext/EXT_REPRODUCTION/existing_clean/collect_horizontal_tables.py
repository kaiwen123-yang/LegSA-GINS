#!/usr/bin/env python3
"""Read the existing CLEAN4/CLEAN7 registries and explicitly linked small results.

No project import, science entry point, metric calculation, hashing, or payload
decompression. CSV cells and JSON numeric lexemes remain original strings.
"""
import argparse
import csv
import io
import json
import re
from collections import Counter
from pathlib import Path
import zipfile

FIELDS = ('record_id stage record_kind method_id paper implementation_version '
          'sequence_id case_id config_id start_policy input_identity native_status '
          'evaluation_status metric_source source_row_key source_values_json '
          'native_output_paths evaluation_paths figure_paths read_depth retention_status '
          'archive_path archive_member notes').split()
csv.field_size_limit(16_000_000)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--roots', required=True, type=Path)
    args = ap.parse_args()
    config = json.loads(args.roots.read_text())
    aliases = config['aliases']
    code = Path(aliases['<CODE_ROOT>'])
    base = code / 'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_clean'
    copies = base / 'horizontal_sources'
    copies.mkdir(parents=True, exist_ok=True)
    c4 = Path(aliases['<CLEAN_ROOT>']) / 'stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON'
    c7 = c4.parent / 'CLEAN7_HEXT_EXTERNAL_SEQUENCES'
    mapping = sorted(((v.rstrip('/'), k) for k, v in aliases.items()), key=lambda x: -len(x[0]))
    historical_paths = {}
    public, local, readlog, objects, table_rows, paths = [], [], [], {}, {}, set()

    def portable(value):
        text = str(value)
        for actual, alias in mapping:
            text = text.replace(actual, alias)
        # Old reports may mention an optional mirror or Git-admin path outside the
        # current roots file. Keep exact bindings only in the ignored local mirror.
        for token in re.findall(r'/(?:home|mnt)/[^\s\"\x27`<>,)\]]+', text):
            if token not in historical_paths:
                historical_paths[token] = '<HISTORICAL_PATH_%03d>' % (len(historical_paths) + 1)
            text = text.replace(token, historical_paths[token])
        return text

    def resolve(value):
        for actual, alias in mapping:
            value = str(value).replace(alias, actual)
        return Path(value)

    def record(path, kind, values, key='$', depth='FULL_JSON_PARSE', version='', notes='', archive='', member=''):
        identity = values if isinstance(values, dict) else {}
        row = dict.fromkeys(FIELDS, '')
        row.update(record_id='C47_%07d' % (len(public) + 1),
                   stage='CLEAN4' if path.is_relative_to(c4) else 'CLEAN7' if path.is_relative_to(c7) else 'LINKED_SOURCE',
                   record_kind=kind, method_id=identity.get('method_id', identity.get('method', identity.get('configuration_id', 'unknown'))),
                   paper=identity.get('literature_identity', identity.get('reference', 'see method registry')),
                   implementation_version=version or identity.get('evaluator_contract', identity.get('result_identity', 'source version retained')),
                   sequence_id=identity.get('sequence_id', identity.get('dataset_id', 'BY2' if path.is_relative_to(c4) else 'unknown')),
                   case_id=identity.get('case_id', 'C00 / source-specific support'),
                   config_id=identity.get('config', identity.get('configuration_id', identity.get('mode_id', 'unknown'))),
                   start_policy=identity.get('start_convention', identity.get('start_mode', 'unknown')),
                   input_identity=json.dumps({k: identity[k] for k in ('code_commit', 'config_hash', 'raw_hash_lock_sha256', 'source_nav_sha256', 'evaluator_nav_sha256') if k in identity}, ensure_ascii=False),
                   native_status=identity.get('native_status', identity.get('terminal_status', 'unknown')),
                   evaluation_status=identity.get('evaluation_status', identity.get('evaluation', 'unknown')),
                   metric_source=str(path), source_row_key=key,
                   source_values_json=json.dumps(values, ensure_ascii=False, separators=(',', ':')),
                   native_output_paths=identity.get('native_root', identity.get('source_nav', '')),
                   evaluation_paths=identity.get('evaluations', identity.get('error_series_source', '')),
                   figure_paths=identity.get('composite_png', ''), read_depth=depth,
                   retention_status='NOT_FOUND' if not path.exists() else 'EXISTS_NOT_READ' if depth.startswith('STAT_') else 'EXISTS_READ',
                   archive_path=str(archive), archive_member=member, notes=notes)
        for k, v in row.items():
            if not isinstance(v, str):
                row[k] = json.dumps(v, ensure_ascii=False, separators=(',', ':'))
        local.append(row.copy())
        public.append({k: portable(v) for k, v in row.items()})

    def stat(path, reason, version='', extra=None):
        path = Path(path)
        if str(path) in paths:
            return
        paths.add(str(path))
        info = dict(extra or {}, exists=path.is_file(), bytes=str(path.stat().st_size) if path.is_file() else 'unknown')
        record(path, 'PAYLOAD_OR_REFERENCE_LOCATION', info, 'FILE', 'STAT_ONLY_NO_PAYLOAD_OPEN', version, reason)
        readlog.append({'source_path': portable(path), 'read_depth': 'STAT_ONLY_NO_PAYLOAD_OPEN', 'exists': path.is_file()})

    def read(path, version='', notes='', copy=True):
        path = Path(path)
        if str(path) in objects:
            return objects[str(path)]
        if not path.is_file():
            stat(path, 'Explicit source reference not found. ' + notes, version)
            return None
        if not (path.is_relative_to(c4) or path.is_relative_to(c7)):
            stat(path, 'Linked outside this worker stage scope; no payload read. ' + notes, version)
            return None
        paths.add(str(path))
        raw = path.read_text(encoding='utf-8-sig')
        root = c4 if path.is_relative_to(c4) else c7
        rel = str(path.relative_to(root))
        short = ('C4__' if root == c4 else 'C7__') + rel.replace('/', '__')
        dest = copies / short
        if copy:
            dest.write_text(portable(raw), encoding='utf-8')
        info = {'bytes': str(path.stat().st_size), 'source_copy': '<CODE_ROOT>/' + str(dest.relative_to(code)) if copy else 'NOT_COPIED_PAYLOAD_REMAINS_IN_PLACE'}
        if path.suffix == '.csv':
            reader = csv.DictReader(io.StringIO(raw)); headers = reader.fieldnames or []
            data = list(reader)
            objects[str(path)] = data; table_rows[str(path)] = data
            info.update(row_count=str(len(data)), headers=headers)
            record(path, 'SOURCE_TABLE', info, 'ALL_DATA_ROWS_1_BASED', 'FULL_CSV_PARSE', version, notes)
            # Long per-epoch tables remain complete in their original/copy; avoid a
            # second giant JSON-in-CSV representation of those same cells.
            if len(data) <= 2500 and not any(t in path.name for t in ('NATIVE_HEADING', '_RUNTIME.csv', '_DIAGNOSTICS.csv')):
                for i, row in enumerate(data, 1):
                    record(path, 'SOURCE_TABLE_ROW', row, 'data_row=' + str(i), 'FULL_CSV_PARSE', version, notes)
            readlog.append({'source_path': portable(path), 'read_depth': 'FULL_CSV_PARSE', 'row_count': len(data)})
        elif path.suffix == '.json':
            obj = json.loads(raw, parse_float=str, parse_int=str)
            objects[str(path)] = obj
            info.update(top_level_keys=list(obj) if isinstance(obj, dict) else 'LIST', object_count=str(len(obj)))
            record(path, 'SOURCE_JSON', info, '$', 'FULL_JSON_PARSE', version, notes)
            if isinstance(obj, dict) and isinstance(obj.get('row'), dict):
                record(path, 'EXISTING_EVALUATION_RESULT', obj['row'], '$.row', 'FULL_JSON_PARSE', version, notes)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if len(json.dumps(item)) <= 60000:
                        record(path, 'EXISTING_LEDGER_RECORD', item, '$[' + str(i) + ']', 'FULL_JSON_PARSE', version, notes)
            elif isinstance(obj, dict):
                if len(json.dumps(obj)) <= 60000:
                    record(path, 'EXISTING_SUMMARY_RECORD', obj, '$', 'FULL_JSON_PARSE', version, notes)
                else:
                    for k, v in obj.items():
                        if len(json.dumps(v)) <= 50000:
                            record(path, 'SOURCE_JSON_FIELD', {k: v}, '$.' + k, 'FULL_JSON_PARSE', version, notes)
            readlog.append({'source_path': portable(path), 'read_depth': 'FULL_JSON_PARSE'})
        else:
            objects[str(path)] = raw
            info['line_count'] = str(len(raw.splitlines()))
            record(path, 'SOURCE_REPORT', info, 'ALL_LINES', 'FULL_TEXT_READ', version, notes)
            readlog.append({'source_path': portable(path), 'read_depth': 'FULL_TEXT_READ'})
        return objects[str(path)]

    # Existing final directories are the discovery boundary, not the disk root.
    for folder in [c4/'12_FINAL_EVIDENCE_INTEGRATION', c4/'13_HORIZONTAL_CROSS_LAYER_SYNTHESIS']:
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.suffix in {'.csv', '.json', '.md'}:
                read(p, 'CLEAN4_FINAL_INTEGRATION_OR_CROSS_LAYER')

    # Follow the frozen source index; predecessor EXT01/02 are covered separately.
    source_index = objects[str(c4/'13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/01_EVIDENCE_INDEX/FINAL_EVIDENCE_SOURCE_INDEX.csv')]
    for entry in source_index:
        p = resolve(entry['source_path']) / entry['source_file']
        if '/02_EXT01_' in str(p) or '/03_EXT02_' in str(p):
            stat(p, 'Full-read records in EXT01_EXT02_INDEX.csv; not re-opened here.')
        elif p.suffix in {'.csv', '.json', '.md'} and p.is_file() and p.stat().st_size <= 4_000_000:
            read(p, entry.get('evaluation_scope', ''), 'Original source_id=' + entry['source_id'])
        else:
            stat(p, 'Source_id=' + entry['source_id'] + '; no payload reading outside selected result/summary scope.')

    # EXT03 all registered modes, native rows/failures, primary and recovery versions.
    ext3 = c4/'04_EXT03_YANG2024/C00'
    for folder in [ext3, ext3/'POST_NATIVE', ext3/'POST_NATIVE_RECOVERY_RTKLIB_TIME_ASSOCIATION_R1']:
        for p in sorted(folder.iterdir()):
            if not p.is_file():
                continue
            allowed_csv = any(s in p.name for s in ('SUMMARY', 'REGISTRY', 'NATIVE_HEADING_RESULTS', 'FAILURE_LEDGER', '_RUNTIME.csv'))
            if p.suffix == '.json' or (p.suffix == '.csv' and allowed_csv):
                read(p, 'EXT03_PRIMARY' if folder == ext3 else folder.name)
            else:
                stat(p, 'EXT03 detailed epoch/observation payload: position only; summary tables read separately.')
    for name in ['PHASE3_STATUS.json', 'PHASE3_STATUS_PRELIMINARY.json', 'PHASE3_STATUS_RTKLIB_TIME_ASSOCIATION_R1.json',
                 'PHASE3_EXT03_C00_REPORT.md', 'PHASE3_EXT03_C00_PRELIMINARY_REPORT.md',
                 'PHASE3_EXT03_C00_REPORT_RTKLIB_TIME_ASSOCIATION_R1.md']:
        read(c4/'11_REPORT'/name, 'EXT03_OLD_STAGE_REPORT')
    provenance = c4/'11_REPORT/PHASE3_EXT03_C00_NATIVE_SOURCE_PROVENANCE_R2'
    for name in ['RECOVERY_MANIFEST.json', 'SOURCE_RECOVERY_FREEZE.json', 'POST_FREEZE_FILECHANGES.json']:
        read(provenance/name, 'EXT03_FROZEN_SOURCE_PROVENANCE_R2')
    for name in ['phase3_runner.native_frozen.py', 'POST_FREEZE_NATIVE_TO_CURRENT.patch', 'SHA256SUMS']:
        stat(provenance/name, 'Historical source/test entrance only; no implementation audit or execution.')
    for rel in ['src/legsa_gins/paper_rebuild/horizontal_literature/ext03_yang2024.py',
                'src/legsa_gins/paper_rebuild/horizontal_literature/phase3_runner.py',
                'scripts/paper_rebuild/run_horizontal_literature_phase3.py',
                'tests/paper_rebuild/test_horizontal_ext03_yang2024.py']:
        stat(code/rel, 'Current EXT03 source/test entrance; historical identity not newly verified.')

    # Necessary additional small records for the final literature/navigation entries.
    read(c4/'06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05B_C00_MEKF_NOT_IMPLEMENTED.json', 'CLEAN4_UNAVAILABLE_IMPLEMENTATION')
    for rel in ['11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/11_REPORT',
                '11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/coverage_aware_c00',
                '11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/full_duration_c00',
                '08_LC02_YIN2023_RAEKF', '09_LC02_CHANG2021_FSTCKF', '10_LC02_FINAL_CANDIDATE_TRIAGE']:
        folder = c4/rel
        for p in sorted(folder.glob('*')):
            if p.is_file() and p.suffix in {'.csv', '.json', '.md'} and p.stat().st_size < 500_000:
                read(p, 'CLEAN4_LC02_PROVENANCE_AND_FAILED_ATTEMPTS')
    for p in sorted(c4.glob('*RELOCATION_LEDGER.json')):
        read(p, 'CLEAN4_PRESERVED_ATTEMPT_RELOCATION')

    # CLEAN7 old H-EXT results only. T5 candidate/sensitivity roots never accessed.
    for rel in ['08_AGGREGATE', '11_READONLY_CLOSEOUT_H_EXT_04L']:
        for p in sorted((c7/rel).glob('*')):
            if p.is_file() and p.suffix in {'.csv', '.json', '.md'}:
                read(p, 'H_EXT_03' if rel == '08_AGGREGATE' else 'H_EXT_04L')
    for rel in ['03_CONTINUATION/EXECUTION/EXECUTION_RECORDS.json', '03_CONTINUATION/EXECUTION/BUDGET_LEDGER.json',
                '03_CONTINUATION/FINAL_CHECK.json', '03_CONTINUATION/FINAL_HANDOFF_RECEIPT.json',
                'BY2_IDENTITY_ARCHIVE_LEDGER.json', 'IDENTITY_PASS.json', 'FINAL_CHECK.json', 'FINAL_HANDOFF_RECEIPT.json',
                '99_HARD_STOP/NATIVE_EXECUTION_RECORDS.json', '99_HARD_STOP/EVALUATION_LEDGER.csv',
                '99_HARD_STOP/STOP_REPORT.json', '99_HARD_STOP/HARD_STOP_EVALUATE.json',
                '99_HARD_STOP/HARD_STOP_NATIVE.json', '99_HARD_STOP/BOOKKEEPING_CACHE_ADJUDICATION.json',
                '03_PREREG/CODE_FREEZE.json', '03_PREREG/TEST_AND_REVIEW.json']:
        read(c7/rel, 'H_EXT_OLD_HARD_STOP_PRESERVED' if '99_HARD_STOP' in rel else 'H_EXT_NATIVE_AND_CONTINUATION')
    execution = objects[str(c7/'03_CONTINUATION/EXECUTION/EXECUTION_RECORDS.json')]
    for entry in execution:
        folder = resolve(entry['native_root'])
        for name in ['NATIVE_SUMMARY.json', 'NATIVE_FREEZE.json', 'SCIENTIFIC_SUMMARY.json', 'GEOMETRIC_AUDIT.json', 'GAP_EVENTS.json']:
            obj = read(folder/name, 'H_EXT_ORIGINAL_NATIVE')
            if name == 'NATIVE_SUMMARY.json' and obj:
                for name2, sha in obj.get('file_hashes', {}).items():
                    stat(folder/name2, 'Native output payload retained in place; recorded_sha256 only.', extra={'recorded_sha256': sha, 'run_id': entry['run_id']})
    final = objects[str(c7/'08_AGGREGATE/FINAL_SUMMARY.json')]
    for slot_index, entry in enumerate(final['result_sources']):
        record(c7/'08_AGGREGATE/FINAL_SUMMARY.json', 'FINAL_EVALUATION_DISPOSITION', entry,
               '$.result_sources[' + str(slot_index) + ']', 'FULL_JSON_PARSE', 'H_EXT_FINAL_DISPOSITION',
               'Final admission/classification is separate from the original evaluator row status; no source token overwritten.')
        p = resolve(entry['source'])
        obj = read(p, 'H_EXT_EVALUATOR_' + entry['version'], 'Authoritative result_sources terminal, including noninvoked slots. recorded_sha256=' + entry['sha256'])
        for name in ['error_series.csv', 'error_series.csv.gz', 'matched_trajectory.csv', 'MATCHED_TRAJECTORY.csv']:
            q = p.parent/name
            if q.exists():
                stat(q, 'Existing evaluation time series: existence only, no payload read.')
    by2_ledger = objects[str(c7/'BY2_IDENTITY_ARCHIVE_LEDGER.json')]
    for entry in by2_ledger:
        p = c7/'02_BY2_IDENTITY'/entry['path']
        if p.suffix == '.json':
            read(p, 'H_EXT_01_BY2_IDENTITY_REUSED')
        else:
            stat(p, 'Archive ledger is a copy/retention record, not proof of payload read.', extra={'recorded_sha256': entry['sha256'], 'old_status': entry['status']})

    # Figure sources/versions: inspect catalogs and explicit file locations only.
    for rel in ['14_HORIZONTAL_FULL_PLOTTING/PLOT_CATALOG.csv', '14_HORIZONTAL_FULL_PLOTTING/PLOT_QA.csv',
                '14_HORIZONTAL_FULL_PLOTTING/PLOTTING_STATUS.json', '14_HORIZONTAL_FULL_PLOTTING/PLOTTING_SUMMARY.md',
                '14_HORIZONTAL_FULL_PLOTTING/PLOTTING_REFINEMENT_FINAL_SUMMARY.md',
                '14_HORIZONTAL_FULL_PLOTTING/00_PLOT_CONTRACT/PLOT_FAMILY_STATUS.csv',
                '14_HORIZONTAL_FULL_PLOTTING/00_PLOT_CONTRACT/PLOT_REGISTRY.csv']:
        read(c4/rel, 'CLEAN4_FIGURE_CATALOG_NO_NEW_VISUAL_QA')
    catalog = objects[str(c4/'14_HORIZONTAL_FULL_PLOTTING/PLOT_CATALOG.csv')]
    for row in catalog:
        for column in ['composite_png', 'composite_pdf', 'composite_svg', 'panel_png_assets', 'panel_pdf_assets', 'panel_svg_assets']:
            for value in row[column].split(';'):
                if value:
                    p = c4/'14_HORIZONTAL_FULL_PLOTTING'/value
                    stat(p, 'Figure export only; no rendering/raster review; not another experiment.', extra={'plot_id': row['plot_id'], 'source_file': row['source_file'], 'format_column': column})
    for rel in ['10_FIGURES/HEXT_RENDER_MANIFEST.json', '10_FIGURES/FIG02S_VISUAL_QA.json',
                '11_READONLY_CLOSEOUT_H_EXT_04L/figures/HEXT_RENDER_MANIFEST.json']:
        p = c7/rel
        obj = read(p, 'H_EXT_03_FIGURE' if rel.startswith('10_') else 'H_EXT_04L_FIGURE')
        if isinstance(obj, dict):
            manifests = obj.get('figures', {'single': obj})
            for figure, spec in manifests.items():
                for fmt, item in spec.get('outputs', {}).items():
                    value = item.get('path') if isinstance(item, dict) else item
                    if value:
                        stat(p.parent/value, 'Figure format presence only; historical QA retained, not repeated.', extra={'figure_id': figure, 'format': fmt})

    # A known plotting archive: central directory lookup of exact catalog members.
    archive = c4/'14_HORIZONTAL_FULL_PLOTTING.zip'
    if archive.is_file():
        with zipfile.ZipFile(archive) as z:
            infos = {x.filename: x for x in z.infolist()}
            members = [name for name in infos if name.endswith('/PLOT_CATALOG.csv') or name == 'PLOT_CATALOG.csv']
            record(archive, 'ARCHIVE_CENTRAL_DIRECTORY', {'member_count': str(len(infos)), 'catalog_members': members},
                   'ZIP_CENTRAL_DIRECTORY', 'CENTRAL_DIRECTORY_READ_NO_PAYLOADS', 'CLEAN4_PLOT_ARCHIVE',
                   'No extraction, no full archive hash, no figure payload open.', archive=archive)
            for member in members:
                raw = z.read(member).decode('utf-8-sig')
                archived_rows = list(csv.DictReader(io.StringIO(raw)))
                record(archive, 'ARCHIVE_TABLE_MEMBER', {'row_count': str(len(archived_rows)), 'headers': list(archived_rows[0]) if archived_rows else []},
                       'ALL_DATA_ROWS_1_BASED', 'ARCHIVE_MEMBER_FULL_CSV_PARSE', 'CLEAN4_PLOT_ARCHIVE',
                       'Only the specific catalog member read, not all archive content.', archive=archive, member=member)
                (copies/'C4_PLOT_ARCHIVE_CATALOG.csv').write_text(portable(raw), encoding='utf-8')
                readlog.append({'source_path': portable(archive), 'archive_member': member, 'read_depth': 'ARCHIVE_MEMBER_FULL_CSV_PARSE', 'row_count': len(archived_rows)})

    def write_csv(path, rows):
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)

    write_csv(base/'CLEAN4_CLEAN7_INDEX.csv', public)
    mirror = Path(aliases['<EXT_REPRO_ROOT>'])/'existing_clean.local.csv'
    previous = []
    if mirror.exists():
        with mirror.open(newline='', encoding='utf-8') as f:
            previous = [row for row in csv.DictReader(f) if not row['record_id'].startswith('C47_')]
    for actual, alias in historical_paths.items():
        row = dict.fromkeys(FIELDS, '')
        row.update(record_id='C47_LOCAL_ALIAS_' + str(len(local) + 1), record_kind='LOCAL_ONLY_ALIAS_BINDING',
                   metric_source=actual, source_row_key=alias, notes='Unmapped historical report path; not a scientific input or new disk search.')
        local.append(row)
    write_csv(mirror, previous + local)
    # A file initially checked by stat and subsequently parsed has one final depth.
    final_reads = {}
    for entry in readlog:
        key = (entry['source_path'], entry.get('archive_member', ''))
        if key not in final_reads or not entry['read_depth'].startswith('STAT_'):
            final_reads[key] = entry
    readlog = list(final_reads.values())
    receipt = {'scope': 'existing CLEAN4/CLEAN7 horizontal result tables and linked small records; excludes T5 and old inactive performance payloads',
               'data_mode': 'read_only_existing_result_collection', 'synthetic_data_used': False, 'semisynthetic_data_used': False,
               'source_data_roles': 'Original real-data and structural/synthetic-validation roles are retained separately; these booleans describe this collection process, not a relabeling of old sources.',
               'record_count': len(public), 'unique_source_files': len(paths),
               'read_depth_counts': dict(Counter(x['read_depth'] for x in readlog)),
               'csv_data_rows_read': sum(x.get('row_count', 0) for x in readlog),
               'new_native_calls': 0, 'new_provider_calls': 0, 'new_evaluator_calls': 0, 'new_metric_computations': 0,
               'raw_or_reference_payload_opens': 0, 'new_hashes': 0,
               'read_log_count_unit': 'unique files per collector invocation, not lifetime I/O attempt count',
               'reads': readlog}
    (base/'CLEAN4_CLEAN7_READ_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'reads'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
