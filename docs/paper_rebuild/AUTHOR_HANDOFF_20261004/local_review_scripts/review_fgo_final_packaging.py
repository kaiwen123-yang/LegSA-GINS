from pathlib import Path
import hashlib,json,subprocess,datetime
repo=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
out=Path('/mnt/g/LegSA-GINS-project/修复_20261004')
base=repo/'docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS'
index=json.loads((base/'DELIVERY_FILE_INDEX.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(base/'RESULTS_AND_LIMITATIONS.md')=='178565ef92f362e8e4ef1d92223af09bc912d8c32ac74f6bfc38004248e425dc'
assert sha(base/'DELIVERY_FILE_INDEX.json')=='c6523d8226550f2b96f282bc8bfe50883cad8f7349a6e171e5bee463669ad9b1'
files=index['all_files_except_this_index']
for row in files:
 p=base/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],row['path']
for row in index['byte_identical_copies']:
 p=base/row['path'];s=Path(row['source_path']);assert sha(p)==sha(s)==row['sha256'],row['path']
actual={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
assert actual=={r['path'] for r in files}|{'DELIVERY_FILE_INDEX.json'}
assert len(actual)==50 and len(index['byte_identical_copies'])==47, len(index['byte_identical_copies'])
review={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Final packaging review; earlier root independent arithmetic/physical-point and visual reviews reused','files':len(actual),'exact_source_copies':len(index['byte_identical_copies']),'all_hashes_and_sizes_match':True,'new_science_invocations':0,'report_fully_read':True,'source_release_sha256':index['source_freeze_release_sha256']}
(out/'FGO_SEGMENTED_FINAL_PACKAGING_ROOT_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
paths=[(base/r).relative_to(repo).as_posix() for r in sorted(actual)]
request={'id':'FGO_SEGMENTED_FINAL_RESULTS','message':'docs(fgo): publish segmented comparison results and complete failure ledger','paths':paths,'force_paths':[p for p in paths if Path(p).suffix in {'.png','.pdf','.npz'}]}
(out/'FGO_SEGMENTED_FINAL_RESULTS_COMMIT_REQUEST.json').write_text(json.dumps(request,indent=2)+'\n')
print(json.dumps(review))
