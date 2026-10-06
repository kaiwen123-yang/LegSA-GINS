"""Read-only identity verification for HX-03R-1; writes only its own receipt."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

S = Path(__file__).resolve().parent
W = Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair')
EXTERNAL = Path('/home/kaiwen/research/LegSA-GINS-EXTERNAL')
STAGES = Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages')
V3 = STAGES / 'CLEAN8_PROTOCOL_V3'
HX03 = STAGES / 'CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION'
NEW = HX03 / '95_D12_DIAGNOSIS'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20), b''):
            h.update(block)
    return h.hexdigest()

def resolve(k):
    return Path(k.replace('$HX03', str(HX03)).replace('$V3', str(V3)).replace('$W', str(W)).replace('$EXTERNAL', str(EXTERNAL)))

p = json.loads((NEW / 'PREREQUISITE_CHECK.json').read_text())
baseline = V3 / '00_CONTROL/FIGURE_CLOSEOUT_SECOND_CONTINUATION/BASELINE.json'
expected = json.loads(baseline.read_text())['files_sha256']
assert sha(baseline).startswith('7830a1a5')
assert p['sealed_files_sha256'] == expected
now = {str(f.relative_to(V3)):sha(f) for d in ('07_AGGREGATE','07C_FAILURE_FAMILY_CONFIG','07D_CLASSIFICATION_PROVENANCE') for f in (V3/d).rglob('*') if f.is_file()}
assert now == expected and len(now) == 65
methods = {k:sha(resolve(k)) for k in p['method_body_items']}
assert methods == p['method_body_items'] and len(methods) == 423
untracked = {k:sha(W/k) for k in p['unrelated_untracked_sha256']}
assert untracked == p['unrelated_untracked_sha256'] and len(untracked) == 29
inputs = json.loads((S/'INPUT_HASHES.json').read_text())
for k,v in inputs.items():
    assert sha(resolve(k)) == v, k
old = json.loads((S/'HX03_EXISTING_METADATA_BEFORE.json').read_text())
after = {}
for root, dirs, files in os.walk(HX03):
    if Path(root) == HX03:
        dirs.remove('95_D12_DIAGNOSIS')
    for name in files:
        f = Path(root)/name
        st = f.stat()
        after[str(f.relative_to(HX03))] = [st.st_size, st.st_mtime_ns]
assert after == old
disk = {str(m):os.statvfs(m).f_bavail*os.statvfs(m).f_frsize for m in ('/mnt/e','/mnt/g')}
assert disk['/mnt/e'] >= 40_000_000_000 and disk['/mnt/g'] >= 30_000_000_000
sources = ['src/legsa_gins/paper_rebuild/clean5_sequence/evaluator_capture.py',
           'src/legsa_gins/paper_rebuild/publication/canonical541_figures.py',
           'src/legsa_gins/paper_rebuild/clean6_canonical_v2/evaluation.py',
           'src/legsa_gins/paper_rebuild/hext/external_evaluation.py',
           'src/legsa_gins/paper_rebuild/hext/continuation.py',
           'src/legsa_gins/paper_rebuild/hext/hx03_evaluation.py',
           'scripts/paper_rebuild/hx03_execute.py',
           'configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml',
           'docs/paper_rebuild/CLEAN5_OFFLINE_EVALUATION_RECORD.md',
           'docs/paper_rebuild/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2_PLAN.md',
           'docs/paper_rebuild/hext/H_EXT_02_CONTINUATION_AUTHORIZATION.md']
hashes = {'$W/'+x:sha(W/x) for x in sources}
ev = Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py')
hashes[str(ev)] = sha(ev)
assert hashes[str(ev)] == 'aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da'
(S/'SOURCE_CODE_HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
r = {'utc':datetime.now(timezone.utc).isoformat(), 'passed':True,
     'baseline_source':str(baseline), 'baseline_sha256':sha(baseline),
     'sealed_start_matched':p['sealed_matched'], 'sealed_before_commit_matched':len(now),
     'sealed_csv_before_commit_matched':sum(k.endswith('.csv') for k in now),
     'sealed_files_sha256':now, 'method_body_before_commit_matched':len(methods), 'method_body_items':methods,
     'unrelated_untracked_matched':len(untracked), 'read_input_hashes_unchanged':len(inputs),
     'hx03_existing_files_metadata_unchanged':len(after),
     'hx03_preservation_evidence':'existing file inventory, byte sizes and mtime_ns unchanged; SHA256 for all diagnostic inputs; no full native-payload content read',
     'disk_available_bytes':disk,'native_calls':0,'evaluator_calls':0,'reference_opens':0}
(S/'FINAL_VERIFICATION.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in r.items() if k not in ('sealed_files_sha256','method_body_items')},ensure_ascii=False,indent=2))
