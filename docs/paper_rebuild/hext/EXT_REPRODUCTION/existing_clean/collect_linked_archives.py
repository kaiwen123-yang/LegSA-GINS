#!/usr/bin/env python3
"""Read only explicit small members of the three already referenced handoffs."""
import argparse
import csv
import io
import json
from pathlib import Path
import zipfile

FIELDS = ('record_id stage record_kind method_id paper implementation_version '
          'sequence_id case_id config_id start_policy input_identity native_status '
          'evaluation_status metric_source source_row_key source_values_json '
          'native_output_paths evaluation_paths figure_paths read_depth retention_status '
          'archive_path archive_member notes').split()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--roots', type=Path, required=True)
    args = p.parse_args()
    roots = json.loads(args.roots.read_text())['aliases']
    code = Path(roots['<CODE_ROOT>'])
    out = code/'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_clean'
    copies = out/'archive_sources'
    copies.mkdir(exist_ok=True)
    mirror = Path(roots['<EXT_REPRO_ROOT>'])/'existing_clean.local.csv'
    csv.field_size_limit(16_000_000)
    old = list(csv.DictReader(mirror.open())) if mirror.exists() else []
    mapping = [(v.rstrip('/'), k) for k, v in roots.items()]
    mapping.extend((r['metric_source'], r['source_row_key']) for r in old if r['record_kind']=='LOCAL_ONLY_ALIAS_BINDING')
    mapping.sort(key=lambda x: -len(x[0]))

    def portable(s):
        for actual, alias in mapping:
            s = s.replace(actual, alias)
        return s

    selections = {
        'hext_three_sequences_handoff.zip': [
            'STAGE/99_HARD_STOP/EVALUATION_LEDGER.csv',
            'STAGE/99_HARD_STOP/NATIVE_EXECUTION_RECORDS.json',
            'STAGE/99_HARD_STOP/STOP_REPORT.json'],
        'hext_three_sequences_handoff_v2.zip': [
            'STAGE/03_CONTINUATION/EXECUTION/EXECUTION_RECORDS.json',
            'STAGE/08_AGGREGATE/FINAL_SUMMARY.json',
            'STAGE/08_AGGREGATE/HORIZONTAL_TABLE_V2_THREE_SEQUENCES.csv',
            'STAGE/08_AGGREGATE/HORIZONTAL_TABLE_V3_THREE_SEQUENCES.csv',
            'STAGE/08_AGGREGATE/SOURCE_RESOLUTION.json',
            'STAGE/99_HARD_STOP/EVALUATION_LEDGER.csv',
            'STAGE/99_HARD_STOP/NATIVE_EXECUTION_RECORDS.json',
            'STAGE/99_HARD_STOP/STOP_REPORT.json'],
        'c541_v21_handoff.zip': ['sequence_error_series_subset/SUBSET_MANIFEST.csv'],
    }
    rows, locals_, receipts = [], [], []
    for filename, members in selections.items():
        archive = Path(roots['<HANDOFF_ROOT>'])/filename
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            receipt = {'archive_path': portable(str(archive)), 'size_bytes': archive.stat().st_size,
                       'central_directory_member_count': len(names), 'members_read': []}
            for member in members:
                info = z.getinfo(member)
                if info.file_size > 400_000:
                    raise ValueError('Explicit small-member limit exceeded: ' + member)
                raw = z.read(member).decode('utf-8-sig')
                is_csv = member.endswith('.csv')
                obj = list(csv.DictReader(io.StringIO(raw))) if is_csv else json.loads(raw, parse_float=str, parse_int=str)
                copy = copies/(filename.replace('.zip','')+'__'+member.replace('/','__'))
                copy.write_text(portable(raw), encoding='utf-8')
                values = {'uncompressed_bytes': str(info.file_size), 'row_count' if is_csv else 'object_count': str(len(obj)),
                          'portable_copy': '<CODE_ROOT>/'+str(copy.relative_to(code)),
                          'zip_member_crc_check': 'performed_by_zipfile_read', 'sha256': 'NOT_NEWLY_HASHED'}
                row = dict.fromkeys(FIELDS,'')
                row.update(record_id='C47_ARCH_%04d'%(len(rows)+1), stage='CLEAN7_LINKED_ARCHIVE',
                           record_kind='ARCHIVE_SMALL_SOURCE_TABLE' if is_csv else 'ARCHIVE_SMALL_SOURCE_RECORD',
                           implementation_version=filename, method_id='see source identities', sequence_id='see source identities',
                           native_status='HISTORICAL_RECORDED_NOT_EXECUTED_THIS_COLLECTION',
                           evaluation_status='HISTORICAL_RECORDED_NOT_EVALUATED_THIS_COLLECTION', metric_source=str(archive),
                           source_row_key='ALL_DATA_ROWS_1_BASED' if is_csv else '$', source_values_json=json.dumps(values,ensure_ascii=False),
                           read_depth='ARCHIVE_MEMBER_FULL_CSV_PARSE' if is_csv else 'ARCHIVE_MEMBER_FULL_JSON_PARSE',
                           retention_status='ARCHIVE_MEMBER_EXISTS_AND_READ', archive_path=str(archive), archive_member=member,
                           notes='Only this explicit member read; no raw/reference/error-series payload, extraction, or archive-wide hash.')
                locals_.append(row.copy());rows.append({k:portable(v) for k,v in row.items()})
                receipt['members_read'].append({'member':member,'data_rows' if is_csv else 'top_level_items':len(obj)})
                if filename=='c541_v21_handoff.zip':
                    receipt['subset_manifest_headers']=list(obj[0]) if obj else []
                    # Keep the manifest as provenance; do not open any listed series.
                    receipt['series_payload_reads']=0
            receipts.append(receipt)
    def write(path,data):
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(data)
    write(out/'LINKED_ARCHIVE_INDEX.csv',rows)
    write(mirror,[r for r in old if not r['record_id'].startswith('C47_ARCH_')]+locals_)
    result={'archive_count':len(receipts),'explicit_members_read':len(rows),'new_native_calls':0,'new_evaluator_calls':0,
            'data_mode':'read_only_existing_archive_member_collection','synthetic_data_used':False,'semisynthetic_data_used':False,
            'new_provider_calls':0,'raw_or_reference_payload_opens':0,'error_series_payload_reads':0,'new_sha256':0,
            'archives':receipts}
    (out/'LINKED_ARCHIVE_READ_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='archives'}))


if __name__=='__main__':
    main()
