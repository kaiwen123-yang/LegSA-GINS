#!/usr/bin/env python3
"""Reconcile the interrupted V3 archive; release only explicitly inventoried files."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from legsa_gins.paper_rebuild.clean6_canonical_v2.archive_io import retry_io
from legsa_gins.paper_rebuild.clean6_canonical_v2.io_recovery import _metadata_bytes

SCIENCE = '7d43b9af26120ed5dde21f53e515386361072ba6'


def sha(path, compressed=False):
    h = hashlib.sha256()
    with (gzip.open if compressed else open)(path, 'rb') as stream:
        while b := stream.read(8 * 1024 * 1024): h.update(b)
    return h.hexdigest()


def safe(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts: raise ValueError('UNSAFE_PATH')
    for p in (path, *path.parents):
        if p.is_symlink(): raise ValueError('SYMLINK_DENIED')
    return path


def put(path, value):
    path = safe(path); path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if path.exists():
        previous = path.read_bytes()
        if previous == data: return
        if not data.startswith(previous): raise ValueError('EXISTING_RECEIPT_DIFFERS ' + str(path))
    def write():
        with path.open('wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    retry_io(write, source=path, destination=path, operation='v3r_reconcile_metadata_write')
    if path.read_bytes() != data: raise ValueError('METADATA_COPY_DIFFERS')


def pin(path):
    return {'path': str(path), 'sha256': sha(path), 'size_bytes': path.stat().st_size}


def verify_compact(root):
    receipt = json.loads((root/'ARCHIVE_RECEIPT.json').read_text())
    if receipt['status'] != 'ARCHIVE_VERIFIED' or receipt.get('archive_scope') != 'RETAINED_EVIDENCE_ONLY' or receipt['archive_root'] != str(root):
        raise ValueError('COMPACT_RECEIPT_INVALID')
    for row in receipt['files'].values():
        path = safe(root/row['storage_relative_path'])
        if root not in path.parents or path.stat().st_size != row['size_bytes'] or sha(path) != row['sha256']:
            raise ValueError('COMPACT_ARCHIVE_FILE_CHANGED')


def keep(relative, inventory):
    name = Path(relative).name
    if name.endswith('.nav') or 'STD' in name or name.startswith(('EVAL_NAV', 'KF_GINS_IMU_ERR', 'NAV_10HZ')):
        return False
    if relative + '.gz' in inventory: return False
    return True


def verify_slot(root):
    root = safe(root)
    receipt = json.loads((root / 'ARCHIVE_RECEIPT.json').read_text())
    if receipt['status'] != 'ARCHIVE_VERIFIED' or receipt['archive_root'] != str(root):
        raise ValueError('ARCHIVE_RECEIPT_INVALID')
    if 'OUTPUT_SEAL.json' not in receipt['files']: raise ValueError('OUTPUT_SEAL_MISSING')
    seal = json.loads((root/'OUTPUT_SEAL.json').read_text())
    if seal.get('status') != 'SEALED': raise ValueError('OUTPUT_SEAL_NOT_SEALED')
    for relative, digest in seal['files'].items():
        if receipt['files'].get(relative, {}).get('source_sha256') != digest:
            raise ValueError('OUTPUT_SEAL_ARCHIVE_COVERAGE ' + relative)
    for relative, item in receipt['files'].items():
        p = safe(root / item['storage_relative_path'])
        if root not in p.parents: raise ValueError('ARCHIVE_PATH_ESCAPE')
        if p.stat().st_size != item['size_bytes'] or sha(p) != item['sha256']:
            raise ValueError('ARCHIVED_FILE_HASH_OR_SIZE ' + str(p))
        if Path(relative).name in ('KF_GINS_Navresult.nav', 'KF_GINS_STD.txt', 'EVAL_NAV_V3.nav'):
            if sha(p, item['compression'] == 'gzip') != item['source_sha256']:
                raise ValueError('NAV_STD_UNCOMPRESSED_HASH ' + str(p))
    return receipt


def verify_run(native, evaluations, archive):
    rid = native['run_id']; root = archive / '03_NATIVE' / rid
    receipt = verify_slot(root)
    summary = json.loads((root / 'V3_NATIVE_SUMMARY.json').read_text())
    for k in ('run_id', 'status', 'nav_sha256', 'std_sha256', 'native_manifest_sha256'):
        if native.get(k) != summary.get(k): raise ValueError('NATIVE_LEDGER_MISMATCH ' + rid + ' ' + k)
    if sha(root / 'RUN_MANIFEST.json') != native['native_manifest_sha256']:
        raise ValueError('RUN_MANIFEST_HASH ' + rid)
    for name, key in [('KF_GINS_Navresult.nav', 'nav_sha256'), ('KF_GINS_STD.txt', 'std_sha256')]:
        if receipt['files'][name]['source_sha256'] != native[key]: raise ValueError('NAV_STD_LEDGER_HASH')
    if set(evaluations) != {'v3', 'v2'}: raise ValueError('DUAL_EVALUATIONS_MISSING')
    for version, payload in evaluations.items():
        eroot = archive / '04_EVALUATION' / rid / version
        ereceipt = verify_slot(eroot)
        saved = json.loads((eroot / 'EVALUATION_RESULT.json').read_text())
        for k, v in saved.items():
            if payload.get(k) != v: raise ValueError('EVALUATION_LEDGER_MISMATCH ' + rid + ' ' + version + ' ' + k)
        if payload['row']['native_nav_sha256'] != native['nav_sha256'] or payload['row']['std_sha256'] != native['std_sha256']:
            raise ValueError('EVALUATION_INPUT_HASH')
        transform = payload['transform']; row = payload['row']
        if transform['input_sha256'] != native['nav_sha256'] or transform['std_sha256'] != native['std_sha256']:
            raise ValueError('EVALUATION_TRANSFORM_INPUT_HASH')
        expected = native['nav_sha256'] if version == 'v2' else ereceipt['files']['EVAL_NAV_V3.nav']['source_sha256']
        if row['evaluator_nav_sha256'] != expected or transform['output_sha256'] != expected:
            raise ValueError('EVALUATION_TRANSFORM_OUTPUT_HASH')
        capture = json.loads((eroot/'FROZEN_EVALUATOR/EVALUATOR_CAPTURE.json').read_text())
        if any(capture[key] != row[key] for key in ('evaluator_sha256','trace_sha256')):
            raise ValueError('EVALUATOR_CAPTURE_IDENTITY')
        if capture['consistency']['passed'] is not True: raise ValueError('EVALUATOR_CONSISTENCY')
    return rid


def copy_verified(src, dst, expected):
    safe(src); safe(dst); dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if sha(dst) == expected: return
        if dst.stat().st_size >= src.stat().st_size: raise ValueError('EXISTING_G_COPY_DIFFERS ' + str(dst))
        with src.open('rb') as original, dst.open('rb') as partial:
            while block := partial.read(8*1024*1024):
                if original.read(len(block)) != block: raise ValueError('PARTIAL_COPY_DIFFERS')
    def copy():
        with src.open('rb') as r, dst.open('wb') as w:
            shutil.copyfileobj(r, w, 8 * 1024 * 1024); w.flush(); os.fsync(w.fileno())
    retry_io(copy, source=src, destination=dst, operation='v3r_reconcile_copy')
    if sha(dst) != expected: raise ValueError('G_COPY_HASH_FAILED ' + str(dst))


def compact_slot(source, destination):
    original = json.loads((source / 'ARCHIVE_RECEIPT.json').read_text())
    files = {}; omitted = {}
    for relative, item in original['files'].items():
        if relative+'.gz' in original['files'] and keep(relative, {}):
            compressed=original['files'][relative+'.gz']
            src=source/compressed['storage_relative_path']
            if compressed['compression']!='identity' or sha(src,True)!=item['source_sha256']:
                raise ValueError('EXISTING_GZIP_ALIAS_IDENTITY_FAILED')
            copy_verified(src,destination/compressed['storage_relative_path'],compressed['sha256'])
            files[relative]={**item,'storage_relative_path':compressed['storage_relative_path'],
                             'sha256':compressed['sha256'],'size_bytes':compressed['size_bytes'],
                             'compression':'gzip','shared_physical_member':relative+'.gz'}
        elif keep(relative, original['files']):
            copy_verified(source / item['storage_relative_path'], destination / item['storage_relative_path'], item['sha256'])
            files[relative] = item
        else: omitted[relative] = item
    copy_verified(source / 'ARCHIVE_RECEIPT.json', destination / 'ORIGINAL_FULL_ARCHIVE_RECEIPT.json', sha(source / 'ARCHIVE_RECEIPT.json'))
    receipt = dict(status='ARCHIVE_VERIFIED', archive_scope='RETAINED_EVIDENCE_ONLY', archive_root=str(destination), source_root=str(source),
                   files=files, omitted_payload_hashes=omitted, omission_reason='V3_01_R_A3_NAV_STD_NOT_RETAINED')
    put(destination / 'ARCHIVE_RECEIPT.json', receipt)
    return receipt


def exact_release(root, evidence_root, disposition='DELETED_AFTER_G_COPY_VERIFIED'):
    root = safe(root)
    receipt = evidence_root / (root.name + '_RELEASE_INVENTORY.json')
    log = receipt.with_suffix('.jsonl')
    if receipt.exists():
        paths = json.loads(receipt.read_text())
    else:
        paths = []
        if not root.exists(): return
        for parent, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files: safe(Path(parent) / name)
            for name in files:
                p = Path(parent) / name
                paths.append({'path': str(p), 'size_bytes': p.stat().st_size})
        put(receipt, paths)
    events = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    intents = {r['path'] for r in events if r['status'] == 'DELETE_INTENT'}
    for row in paths:
        p = safe(row['path'])
        if not p.exists():
            if str(p) not in intents: raise ValueError('MISSING_RELEASE_FILE_WITHOUT_INTENT')
            continue
        if root not in p.parents or not p.is_file() or p.stat().st_size != row['size_bytes']: raise ValueError('RELEASE_SCOPE_OR_SIZE')
        _metadata_bytes(log,(json.dumps({**row,'status':'DELETE_INTENT'})+'\n').encode(),append=True)
        p.unlink()
        _metadata_bytes(log,(json.dumps({**row,'status':disposition})+'\n').encode(),append=True)
    for parent, dirs, files in os.walk(root, topdown=False):
        Path(parent).rmdir()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--local-config', type=Path, required=True)
    p.add_argument('--execute', action='store_true'); args = p.parse_args()
    import yaml
    paths = yaml.safe_load(args.local_config.read_text())['paths']
    scratch = safe(paths['protocol_v3_scratch']); archive = safe(paths['protocol_v3_archive'])
    root = safe(Path(paths['clean_root']) / 'stages/CLEAN8_PROTOCOL_V3')
    out = root / '00_CONTROL/V3R_RECONCILIATION'; out.mkdir(parents=True,exist_ok=True)
    manifest_path = out / 'RECONCILIATION_MANIFEST.json'
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text())
        if m.get('status') != 'PASS_ARCHIVE_RECONCILIATION' or m.get('science_freeze') != SCIENCE: raise ValueError('BAD_COMPLETION_MANIFEST')
        for r in m['files']:
            if sha(r['path']) != r['sha256']: raise ValueError('COMPLETION_PIN_DIFFERS')
        if archive.exists(): raise ValueError('COMPLETED_ARCHIVE_REAPPEARED')
        print('RECONCILIATION_ALREADY_COMPLETE', flush=True); return
    if args.execute:
        terminal = json.loads((root / 'V3R_PURGE/PURGE_RESULT.json').read_text())
        if terminal.get('status') not in ('PASS', 'PASS_PURGE_COMPLETE', 'PASS_LEDGERED_PURGE_COMPLETE', 'PURGE_COMPLETE', 'DELETED'):
            raise ValueError('PURGE_NOT_PASSED')
    registry = json.loads((scratch / '00_PREREGISTRATION/REGISTRY.json').read_text())
    old_ledgers = [scratch / '00_PREREGISTRATION' / n for n in ('NATIVE_RESERVATIONS.jsonl', 'EVALUATOR_RESERVATIONS.jsonl')]
    original_ledger_pins = dict(zip(('native','evaluator'), (pin(x) for x in old_ledgers)))
    reserved = {json.loads(x)['run_id'] for x in old_ledgers[0].read_text().splitlines()}
    batches = []; reused = []; recovery = []; identity = []
    for number, start in enumerate(range(0, len(registry), 64), 1):
        specs = registry[start:start+64]
        ids = [s['run_id'] for s in specs]
        if not any(rid in reserved for rid in ids): continue
        # Two independently sealed identity natives lie in later sequence batches.
        if all(rid not in reserved or rid.startswith('SEQUENCE_') for rid in ids): continue
        folder = scratch / f'BATCHES/BATCH_{number:03d}'
        batch_out = out / f'BATCH_{number:03d}'
        audit_path = batch_out/'BATCH_AUDIT.json'
        row = {'batch': f'BATCH_{number:03d}', 'run_count': len(ids), 'ledger_status': 'PRESENT', 'verification': 'PASS', 'disposition': 'REUSE', 'reason': ''}
        prior_audit = None
        if audit_path.exists():
            prior_audit=json.loads(audit_path.read_text())
            for pp in prior_audit['ledger_pins']:
                if sha(pp['path']) != pp['sha256']: raise ValueError('BATCH_CHECKPOINT_LEDGER_DRIFT')
            row=prior_audit['row']
        records = []; evals = []
        try:
            records = json.loads((folder / 'RUN_RECORDS.json').read_text())
            evals = json.loads((folder / 'EVALUATION_RECORDS.json').read_text())
            if {r['run_id'] for r in records} != set(ids) or len(evals) != 2*len(ids): raise ValueError('BATCH_LEDGER_COVERAGE')
            emap = {rid: {} for rid in ids}
            for e in evals: emap[e['row']['run_id']][e['row']['evaluator_contract'].rsplit('_', 1)[1]] = e
            if prior_audit is None:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(lambda r: verify_run(r, emap[r['run_id']], archive), records))
        except Exception as exc:
            if prior_audit is not None:
                if prior_audit['row']['verification']=='PASS': raise
                row=prior_audit['row']
            else:
                row.update(ledger_status='MISSING_OR_INCOMPLETE' if not folder.exists() else 'PRESENT', verification='FAIL', disposition='RERUN_ENTIRE_BATCH', reason=str(exc))
        print('RECONCILE', row, flush=True)
        batches.append(row)
        if not args.execute: continue
        batch_out.mkdir(exist_ok=True)
        if not audit_path.exists():
            put(audit_path, {'row':row,'ledger_pins':[pin(f) for f in folder.iterdir() if f.is_file()] if folder.exists() else []})
        if folder.exists():
            for f in folder.iterdir():
                if f.is_file(): copy_verified(f, batch_out / f.name, sha(f))
        if row['verification'] == 'PASS':
            for record in records:
                rid = record['run_id']; destination = root / '03_NATIVE' / rid
                completed=batch_out/'TRANSFERRED'/f'{rid}.json'
                if completed.exists():
                    item=json.loads(completed.read_text())
                    for pp in [item['native_record'],*item['evaluations'].values()]:
                        if sha(pp['path']) != pp['sha256']: raise ValueError('REUSE_CHECKPOINT_PIN_CHANGED')
                    verify_compact(destination)
                    for v in ('v3','v2'):verify_compact(root/'04_EVALUATION'/rid/v)
                    reused.append(item)
                    exact_release(archive/'03_NATIVE'/rid,batch_out/'NATIVE_RELEASE')
                    exact_release(archive/'04_EVALUATION'/rid,batch_out/'EVAL_RELEASE')
                    continue
                receipt = compact_slot(archive / '03_NATIVE' / rid, destination)
                saved = {**record, 'archive_output_root': str(destination), 'archive_receipt': str(destination/'ARCHIVE_RECEIPT.json'), 'payload_retention': 'HASH_ONLY_NAV_STD'}
                saved.pop('resolved_nav_path', None); saved.pop('resolved_std_path', None)
                put(destination / 'V3R_NATIVE_RECORD.json', saved)
                item = {'run_id': rid, 'native_record': pin(destination/'V3R_NATIVE_RECORD.json'), 'evaluations': {}}
                for version, payload in emap[rid].items():
                    ed = root / '04_EVALUATION' / rid / version
                    compact_slot(archive / '04_EVALUATION' / rid / version, ed)
                    value = {**payload, 'archive_output_root': str(ed), 'archive_receipt': str(ed/'ARCHIVE_RECEIPT.json'), 'resolved_error_series_source': str(ed/'FROZEN_EVALUATOR')}
                    put(ed / 'V3R_EVALUATION_RECORD.json', value)
                    item['evaluations'][version] = pin(ed/'V3R_EVALUATION_RECORD.json')
                reused.append(item)
                put(completed,item)
                exact_release(archive/'03_NATIVE'/rid, batch_out/'NATIVE_RELEASE')
                exact_release(archive/'04_EVALUATION'/rid, batch_out/'EVAL_RELEASE')
        else:
            for rid in ids:
                checkpoint=batch_out/'RECOVERY'/f'{rid}.json'
                sr = scratch/'03_NATIVE'/rid/'V3_NATIVE_SUMMARY.json'
                old = next((r for r in records if r['run_id']==rid),{})
                if not old and sr.exists(): old=json.loads(sr.read_text())
                ar=archive/'03_NATIVE'/rid/'V3_NATIVE_SUMMARY.json'
                if not old and ar.exists():old=json.loads(ar.read_text())
                item = {'run_id': rid, 'original_batch': row['batch'], 'reason': row['reason'], 'expected_nav_sha256': old.get('nav_sha256'), 'expected_std_sha256': old.get('std_sha256')}
                if checkpoint.exists():item=json.loads(checkpoint.read_text())
                else:put(checkpoint,item)
                recovery.append(item)
                for kind in ('03_NATIVE', '04_EVALUATION'):
                    src = scratch/kind/rid
                    if src.exists():
                        for parent, dirs, files in os.walk(src):
                            for name in files:
                                f = safe(Path(parent)/name)
                                if f.suffix in ('.json','.yaml','.jsonl') or f.stat().st_size < 1024*1024:
                                    copy_verified(f, batch_out/'INTERRUPTED_EVIDENCE'/kind/rid/f.relative_to(src), sha(f))
                        exact_release(src, batch_out/(kind+'_RELEASE'),'DISCARDED_AUTHORIZED_ENTIRE_BATCH_RERUN')
                    ar=archive/kind/rid
                    if ar.exists():
                        for parent, dirs, files in os.walk(ar):
                            for name in files:
                                f=safe(Path(parent)/name)
                                if f.suffix in ('.json','.yaml','.jsonl') or f.stat().st_size < 1024*1024:
                                    copy_verified(f,batch_out/'INTERRUPTED_ARCHIVE'/kind/rid/f.relative_to(ar),sha(f))
                        exact_release(ar,batch_out/(kind+'_ARCHIVE_RELEASE'),'DISCARDED_AUTHORIZED_ENTIRE_BATCH_RERUN')
    if not args.execute:
        put(out/'AUDIT_ONLY.json', {'batches': batches, 'original_ledger_pins': original_ledger_pins}); return
    # Preserve all original local receipt/history bytes on G, then remove the
    # old per-case metadata trees as well as the already thinned bulk archive.
    for item in reused:
        rid=item['run_id']
        for kind in ('03_NATIVE','04_EVALUATION'):
            source=scratch/kind/rid
            if source.exists():
                for parent, dirs, files in os.walk(source, followlinks=False):
                    for name in dirs+files:safe(Path(parent)/name)
                    for name in files:
                        f=Path(parent)/name
                        if f.suffix not in ('.json','.jsonl','.yaml','.yml'):
                            raise ValueError('UNEXPECTED_RETAINED_OLD_SCRATCH_PAYLOAD '+str(f))
                        copy_verified(f,out/'ORIGINAL_SCRATCH_RECORDS'/kind/rid/f.relative_to(source),sha(f))
            exact_release(source,out/'OLD_SCRATCH_RELEASE'/kind)
    for rid in ('SEQUENCE_BY2H_F01', 'SEQUENCE_BY2O_F01'):
        f = scratch/'03_NATIVE'/rid/'V3_NATIVE_SUMMARY.json'
        record = json.loads(f.read_text())
        for field, name in [('nav_sha256','KF_GINS_Navresult.nav'), ('std_sha256','KF_GINS_STD.txt')]:
            if sha(f.parent/name) != record[field]: raise ValueError('IDENTITY_NATIVE_REUSE_HASH')
        saved = out/'IDENTITY_NATIVE_ONLY'/rid/'V3R_NATIVE_RECORD.json'; put(saved, record)
        identity.append({'run_id':rid, 'native_record':pin(saved), 'evaluations':{}})
    if archive.exists():
        remaining = [p for p in archive.rglob('*') if p.is_file()]
        if remaining: raise ValueError('ARCHIVE_UNRECONCILED_FILES ' + str(len(remaining)))
        for parent, dirs, files in os.walk(archive, topdown=False): Path(parent).rmdir()
    csv_path = out/'ARCHIVE_RECONCILIATION.csv'
    stream=io.StringIO(newline='')
    w = csv.DictWriter(stream, fieldnames=list(batches[0])); w.writeheader(); w.writerows(batches)
    data=stream.getvalue().encode()
    if csv_path.exists():
        if csv_path.read_bytes()!=data:raise ValueError('RECONCILIATION_CSV_CHANGED')
    else:_metadata_bytes(csv_path,data,append=False)
    manifest = {'status':'PASS_ARCHIVE_RECONCILIATION','science_freeze':SCIENCE,
                'data_mode':'storage_provenance_only','synthetic_data_used':False,
                'semisynthetic_data_used':False,'native_invocations':0,'evaluator_invocations':0,
                'files':[pin(csv_path)],'reused_runs':reused,'identity_native_only':identity,
                'recovery_runs':recovery,'original_ledger_pins':original_ledger_pins,'batches':batches,
                'completed_batch_count':sum(r['verification']=='PASS' for r in batches),
                'archive_removed':not archive.exists()}
    put(manifest_path, manifest)
    print('RECONCILIATION_COMPLETE',len(reused),len(recovery),len(identity),flush=True)


if __name__ == '__main__': main()
