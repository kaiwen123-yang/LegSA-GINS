#!/usr/bin/env python3
"""Read explicitly identified HX input manifests; never read input payload bodies."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

FIELDS = 'record_id,stage,record_kind,method_id,paper,implementation_version,sequence_id,case_id,config_id,start_policy,input_identity,native_status,evaluation_status,metric_source,source_row_key,source_values_json,native_output_paths,evaluation_paths,figure_paths,read_depth,retention_status,archive_path,archive_member,notes'.split(',')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roots', type=Path, required=True)
    args = ap.parse_args()
    aliases = json.loads(args.roots.read_text())['aliases']
    root = Path(aliases['<CLEAN_ROOT>']) / 'stages/CLEAN9_EXTERNAL_COMPARISON'
    out = Path(aliases['<CODE_ROOT>']) / 'docs/paper_rebuild/hext/EXT_REPRODUCTION/existing_hx'
    pairs = [('BY2', 'C00'), ('BY2H', 'CONTRACT_START'), ('BY2O', 'FILE_START')]
    rows, meta_receipts = [], {}

    def alias(value):
        text = str(value)
        for raw, key in sorted(((v, k) for k, v in aliases.items()), key=lambda x: len(x[0]), reverse=True):
            text = text.replace(raw, key)
        return text

    def load(path):
        raw = path.read_bytes()
        meta_receipts[alias(path)] = {'read_depth': 'FULL_RECORD_READ', 'bytes': len(raw), 'newly_verified_sha256': hashlib.sha256(raw).hexdigest()}
        return json.loads(raw, parse_float=str, parse_int=str)

    def add(stage, seq, method, config, path, source, pointer, values, depth, note):
        path = Path(path)
        body = {'current_path': alias(path), 'exists': path.is_file(), 'current_bytes': path.stat().st_size if path.is_file() else None, **values}
        r = {k: 'unknown' for k in FIELDS}
        r.update(record_id='INPUT-' + hashlib.sha256((alias(path)+'|'+pointer).encode()).hexdigest()[:20], stage=stage, record_kind='INPUT_LOCATION', method_id=method, sequence_id=seq, case_id=dict(pairs).get(seq, 'unknown'), start_policy={'BY2': 'FILE_START', 'BY2H': 'CONTRACT_START', 'BY2O': 'FILE_START'}.get(seq, 'unknown'), config_id=config, input_identity=alias(path), native_status='NO_NEW_CALL', evaluation_status='NO_NEW_CALL', metric_source=alias(source), source_row_key=pointer, source_values_json=alias(json.dumps(body, ensure_ascii=False, separators=(',', ':'))), native_output_paths='[]', evaluation_paths='[]', figure_paths='[]', read_depth=depth, retention_status='PRESENT_READ' if depth == 'FULL_RECORD_READ' and path.is_file() else ('PRESENT_METADATA_ONLY' if path.is_file() else 'EXPECTED_NOT_FOUND'), archive_path='', archive_member='', notes=note)
        rows.append(r)

    pins_path = root / 'HX02_FIVE_CATEGORY/01_INPUT_PINS/INPUT_PINS.json'
    pins = load(pins_path)
    for seq, mode in pairs:
        run = root / 'HX02_FIVE_CATEGORY/RUNS' / (seq+'__RTKLIB__NONE__'+mode+'__NA')
        hp = run / 'OUTPUT_HASHES.json'
        hashes = load(hp)['files']
        prep_path = run / 'native/RTKLIB_PREPARED.json'
        prep = load(prep_path)
        for name in ('gnss1', 'gnss2'):
            for ext in ('ubx', 'obs', 'nav'):
                rel = 'native/SOURCE_BACKEND/'+name+'.'+ext
                item = hashes[rel]
                add('HX02', seq, 'RTKLIB', 'NONE', run/rel, hp, '#/files/'+rel.replace('/', '~1'), {'recorded_hash_entry': item, 'recorded_full_pairs': prep['full_pairs'], 'recorded_selected_pair_count': len(prep['selected_pairs']), 'native_start_mode': mode, 'recorded_hash_also_in': alias(prep_path)+'#/files/'+name if ext != 'ubx' else 'unknown', 'newly_verified_payload_hash': 'NOT_COMPUTED'}, 'METADATA_ONLY', 'UBX and RINEX are retained reconstructions from the original hash-locked raw CSV. The complete file is distinct from later native start selection. No body read or new hash.')
        for role, v in prep['raw_inputs'].items():
            p = Path(aliases['<RAW_ROOT>']) / v['relative_path']
            add('HX02', seq, 'SHARED_RAW', 'ORIGINAL_RAW_CSV', p, prep_path, '#/raw_inputs/'+role, {'recorded_input': v, 'newly_verified_payload_hash': 'NOT_COMPUTED'}, 'METADATA_ONLY', 'Original raw CSV. Stat only; recorded hash copied from the existing preparation receipt.')
        for method in ('EXT02', 'EXT03', 'EXT04'):
            run = root / 'HX02_FIVE_CATEGORY/RUNS' / (seq+'__'+method+'__LIT__'+mode+'__NA')
            hp = run/'OUTPUT_HASHES.json'
            hashes = load(hp)['files']
            keys = [k for k in hashes if k.endswith('COMPACT_CACHE/CACHE_MANIFEST.json')]
            assert len(keys) == 1, (seq, method, keys)
            cp = run / keys[0]
            cache = load(cp)
            support = {k: cache[k] for k in ('schema_version', 'pair_count', 'pairing_failure_count', 'exact_pairing_tolerance_seconds', 'source_fingerprint') if k in cache}
            support['original_index_order_count'] = len(cache.get('original_index_order', []))
            add('HX02', seq, method, 'LIT', cp, cp, '#', {'cache_metadata': support, 'recorded_manifest_pin': hashes[keys[0]], 'files': cache['files'], 'native_start_mode': mode, 'full_raw_count': prep['full_pairs'], 'full_file_support': str(cache['pair_count']) == str(prep['full_pairs'])}, 'FULL_RECORD_READ', 'Compact metadata fully read; arrays only stat. BY2H 1423 is CONTRACT_START, not full-file 1483. No new compact cache generated.')
            for role, item in cache['files'].items():
                add('HX02', seq, method, 'LIT', cp.parent/item['filename'], cp, '#/files/'+role, {'recorded_array': item, 'recorded_pair_count': cache['pair_count'], 'native_start_mode': mode, 'newly_verified_payload_hash': 'NOT_COMPUTED'}, 'METADATA_ONLY', 'Retained NumPy compact array; original hash only, no payload/header read. Equal recorded pins across methods do not assert new verification.')
    # V0/V0E retain onboard nav, V1/V2 use the explicitly recorded broadcast nav.
    for seq, _ in pairs:
        for variant in ('V0', 'V0E', 'V1', 'V2'):
            cp = root/'HX07R/RUNS'/(seq+'_'+variant)/'COMMAND.json'
            cmd = load(cp)
            for key, sha in cmd['input_sha256'].items():
                if not key.endswith(('.obs', '.nav', '.rnx')):
                    continue
                value = key
                for macro, raw in aliases.items():
                    value = value.replace(macro, raw)
                add('HX07R', seq, 'RTKLIB', variant, Path(value), cp, '#/input_sha256/'+key.replace('~', '~0').replace('/', '~1'), {'recorded_sha256': sha, 'variant': variant, 'newly_verified_payload_hash': 'NOT_COMPUTED'}, 'METADATA_ONLY', 'Exact input pin recorded by this HX07R native command. V0 and V0E retain onboard navigation; V1/V2 use the separate broadcast navigation file.')
    lp = Path(aliases['<HX02_EXTERNAL_ROOT>'])/'rtklib_bridge/lib/librtklib_legsa.so'
    add('HX02', 'ALL', 'LAMBDA_LIBRARY', 'FROZEN_BINARY', lp, pins_path, '#/external_binaries/lambda_library', {'recorded_sha256': pins['external_binaries']['lambda_library'], 'path_source': '<CODE_ROOT>/configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml:horizontal_literature_lambda_library', 'newly_verified_payload_hash': 'NOT_COMPUTED'}, 'METADATA_ONLY', 'Existing lambda shared-library pin and local path. Binary stat only; no loading or hashing.')
    target = out/'INPUT_LOCATIONS.csv'
    with target.open('w', newline='') as f:
        w=csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n'); w.writeheader(); w.writerows(rows)
    receipt = {'data_mode': 'existing_real_data_input_metadata', 'synthetic_data_used': False, 'semisynthetic_data_used': False, 'new_native_calls': 0, 'new_evaluator_calls': 0, 'new_provider_calls': 0, 'payload_body_reads': 0, 'input_payload_hashes_newly_verified': 0, 'record_rows': len(rows), 'missing': [r['input_identity'] for r in rows if r['retention_status']=='EXPECTED_NOT_FOUND'], 'metadata_files_read': meta_receipts, 'compact_full_pair_count_claim': {'BY2': 1509, 'BY2H': 'NO_FULL_1483_CACHE_LOCATED_WITHIN_HX02_RECORDED_POINTERS; retained CONTRACT_START=1423', 'BY2O': 2231}, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'INPUT_LOCATION_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'rows': len(rows), 'metadata_reads': len(meta_receipts), 'missing': len(receipt['missing']), 'bytes': target.stat().st_size}))

if __name__ == '__main__':
    main()
