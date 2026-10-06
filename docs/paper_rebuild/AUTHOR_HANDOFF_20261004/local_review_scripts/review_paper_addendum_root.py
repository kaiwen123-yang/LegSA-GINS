from pathlib import Path
import csv,json,hashlib,subprocess,re,datetime
repo=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001');out=Path('/mnt/g/LegSA-GINS-project/修复_20261004');base=repo/'docs/paper_rebuild/PAPER_IDENTITY_20261004';pkg=repo/'paper_package/gpss_v0'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=lambda p:list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline='')))
receipt=base/'ACCEPTED_EXTERNAL_ADDENDUM_FINAL_RECEIPT.json';assert sha(receipt)=='5f0fe3b0a085d259d55a55ae0b6b93299666d10f7994e853fe5f911103f749e4'
f=json.loads(receipt.read_text());inv=json.loads((base/'ACCEPTED_EXTERNAL_ADDENDUM_INVARIANCE.json').read_text());pre=json.loads((base/'ACCEPTED_EXTERNAL_ADDENDUM_PRE_CHANGE.json').read_text())
for x in f['files']:assert sha(repo/x['path'])==x['sha256'] and (repo/x['path']).stat().st_size==x['bytes']
for p,x in inv['protected_prior_files'].items():assert sha(repo/p)==x['sha256']
for x in f['upstream_accepted_evidence_byte_copies']:assert sha(pkg/'evidence'/x['copy'])==sha(x['source'])==x['sha256']
old={x['claim_id']:x for x in pre['ledger']};new={x['claim_id']:x for x in rows(pkg/'NUMBER_LEDGER.csv')}
keys=['value','unit','source_path','source_locator','derivation','check_mode']
assert len(old)==204 and len(new)==219
for k,r in old.items():assert all(r[x]==new[k][x] for x in keys),k
checks=rows(pkg/'NUMBER_LEDGER_CHECK.csv');assert len(checks)==219 and all(x['status']=='PASS' for x in checks)
source=rows(pkg/'evidence/fgo_segmented_primary_own.csv');table=rows(pkg/'tables/S26_later_fgo_dynamic_support.csv');n=0
for row in table:
 method='OISAM' if row['Method'].startswith('OiSAM') else ('WEN_TC' if row['Method'].startswith('Wen') else 'GNC')
 a=[x for x in source if x['sequence_id']==row['Sequence'] and x['method_id']==method];assert len(a)==1;a=a[0]
 assert row['Own dynamic support']==a['matched_epoch_count']+'/'+a['expected_epoch_count'];n+=2
 for dest,key in [('H RMSE (m)','horizontal_rmse_m'),('V RMSE (m)','vertical_rmse_m'),('3D RMSE (m)','position_3d_rmse_m'),('Yaw RMSE (deg)','yaw_rmse_deg')]:
  if a[key]=='':assert row[dest]=='NA'
  else:assert row[dest]==format(float(a[key]),'.6f');n+=1
assert n==48 and len(table)==9
oldtext=subprocess.check_output(['git','-C',str(repo),'show','98d2e9d717953901be0ffbdf29e69ca105e1ff5e:paper_package/gpss_v0/MANUSCRIPT_GPSS_v0.md'],text=True)
newtext=(pkg/'MANUSCRIPT_GPSS_v0.md').read_text()
def section(s,start,end):
 lines=s.splitlines();a=next(i for i,l in enumerate(lines) if re.match(r'^#+\s*'+start,l));z=next(i for i,l in enumerate(lines[a+1:],a+1) if re.match(r'^#+\s*'+end,l));return '\n'.join(lines[a:z])
assert section(oldtext,'Abstract','1 Introduction')==section(newtext,'Abstract','1 Introduction')
assert section(oldtext,r'6\.1',r'6\.6')==section(newtext,r'6\.1',r'6\.6')
qa=json.loads((pkg/'FINAL_QA.json').read_text());assert qa['body_word_count']==5303 and qa['ledger_pass']==219 and qa['ledger_fail']==0
review={'reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_modified_frozen_files':34,'protected_files_byte_exact':len(inv['protected_prior_files']),'original204_numeric_bindings_unchanged':True,'checks_PASS':219,'copy_sources_byte_exact':12,'new_table_display_numeric_fields_exact':48,'abstract_primary6_1_to6_5_text_exact':True,'generated_S26_fully_read':True,'submission_ready':False,'science_source_or_native_evaluator_calls':0,'all_checks_passed':True}
(out/'PAPER_EXTERNAL_ADDENDUM_ROOT_REVIEW.json').write_text(json.dumps(review,indent=2)+'\n')
paths=(base/'ACCEPTED_EXTERNAL_ADDENDUM_COMMIT_PATHS.txt').read_text().splitlines();assert len(paths)==34 and set(paths)=={x['path'] for x in f['files']}|{receipt.relative_to(repo).as_posix()}
request={'id':'PAPER_ACCEPTED_EXTERNAL_ADDENDUM','message':'docs(paper): bind accepted FGO and heading diagnostics without replacing V3','paths':paths}
(out/'PAPER_EXTERNAL_ADDENDUM_COMMIT_REQUEST.json').write_text(json.dumps(request,indent=2)+'\n')
print(json.dumps(review))
