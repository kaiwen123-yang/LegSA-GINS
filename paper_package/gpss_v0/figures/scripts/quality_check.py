"""Delivery checks only: no scientific recomputation."""
from common import *
import re,collections
from PIL import Image
main=(P/'MANUSCRIPT_GPSS_v0.md').read_text();sup=(P/'SUPPLEMENT_GPSS_v0.md').read_text()
counts={}
for part in re.split(r'^## ',main,flags=re.M)[1:]:
 name=part.splitlines()[0]
 lines=[l for l in part.splitlines()[1:] if not l.startswith(('|','**Fig.','**Table','![','#','\\','P^','S=','z_','v_','a='))]
 counts[name]=len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",'\n'.join(lines)))
body=sum(v for k,v in counts.items() if re.match(r'[1-9] ',k));assert 5000<=body<=5500,(body,counts)
assert 150<=counts['Abstract']<=250,counts['Abstract']
for text in [main,sup]:
 assert not re.search(r'pre-registered|preregistered|hash-locked|sealed|frozen chain|significant|CLEAN\d|HX-|UA-|R5',text,re.I)
 # Disclosure of shared sources, controlled faults and version identity is allowed.
 assert not re.search(r'[\u4e00-\u9fff]',text)
 assert '[[' not in text
for i in range(1,10):assert re.search(r'^## '+str(i)+' ',main,re.M)
for i in range(1,11):assert re.search(r'^## S'+str(i)+' ',sup,re.M)
figs=[]
for name in [f'Fig{i:02d}' for i in range(1,9)]+['SFig01','SFig02']:
 for ext in ['png','pdf','svg']:assert (P/'figures'/f'{name}.{ext}').is_file()
 im=Image.open(P/'figures'/f'{name}.png');assert im.width>=4096;figs.append({'figure':name,'png_width':im.width,'png_height':im.height,'visual_review':'Historical inspection retained; this check validates dimensions only, without a new visual review'})
ledger=list(csv.DictReader((P/'NUMBER_LEDGER_CHECK.csv').open()));assert all(x['status']=='PASS' for x in ledger)
source_ledger=list(csv.DictReader((P/'NUMBER_LEDGER.csv').open()))
assert len({r['claim_id'] for r in source_ledger})==len(source_ledger), 'Duplicate ledger ID'
assert [(r['claim_id'],r['value']) for r in source_ledger]==[(r['claim_id'],r['expected']) for r in ledger], 'Ledger check is stale'
assert len(re.findall(r'^\*\*Fig\. [1-6]\.',main,re.M))==6
assert len(re.findall(r'^\*\*Table [1-4]\.',main,re.M))==4
keywords=main.split('**Keywords:**',1)[1].splitlines()[0].split(';');assert 4<=len(keywords)<=6
all_prose=len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",'\n'.join(l for l in main.splitlines() if not l.startswith(('|','![','\\','#')))))
visual_path=W/'docs/paper_rebuild/PAPER_IDENTITY_20261004/READER_FIGURE_VISUAL_REVIEW.json'
if visual_path.exists():
 for row in json.loads(visual_path.read_text())['figures']:
  im_path=P/'figures'/(row['figure']+'.png')
  if hashlib.sha256(im_path.read_bytes()).hexdigest()==row['png_sha256']:
   next(x for x in figs if x['figure']==row['figure'])['visual_review']='Final reader-name/photo publication raster actually viewed; scope limited to figure presentation'
mp=list(csv.DictReader((P/'FIGURE_MAP.csv').open()));statuses=dict(collections.Counter(x['status'] for x in mp))
for r in mp:
 if r['status']=='COPIED':
  for src in r['source_or_script'].split(';'):
   src=Path(src);dest=P/'figures'/(r['manuscript_figure']+src.suffix);assert hashlib.sha256(src.read_bytes()).digest()==hashlib.sha256(dest.read_bytes()).digest()
qa=[]
for p in (P/'figures').glob('*_QA.json'):
 q=json.loads(p.read_text());assert all(x['pass'] for x in q);qa.append({'figure':p.stem.replace('_QA',''),'passed':len(q),'failed':0})
size=sum(p.stat().st_size for p in P.rglob('*') if p.is_file());assert size<=200*1024*1024,size
assert 'shared GNSS input lineage' in main
assert 'shared dual-yaw initialization' in main
assert 'author-retained' in main.lower() and 'contract-diagnostic' in main.lower() and 'pending' in main.lower()
assert '## S25 ' in sup
assert '1.886' in main.split('## Abstract',1)[1].split('## 1 Introduction',1)[0]
assert json.loads((P/'evidence/RESULT_IDENTITY_MAP.json').read_text())['author_retained_V3']['scientific_source_revision']=='7d43b9af26120ed5dde21f53e515386361072ba6'
primary=json.loads((P/'evidence/original_v3_registry_receipt.json').read_text())
assert primary['registered_tasks']==6468 and primary['native_terminal_counts']=={'COMPLETED':6185,'ALGORITHM_FAILURE_DIVERGED':193,'ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT':90}
assert primary['actual_evaluator_completions']==12370 and primary['not_invoked_algorithm_failure_slots']==566
assert json.loads((P/'evidence/RESULT_IDENTITY_MAP.json').read_text())['author_retained_V3']['native_binary_sha256']=='96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c'
assert all(f'## S{i} ' in sup for i in range(20,24))
assert '## S24 ' in sup
assert not re.search(r'\b(?:F0[1-4]|A0[1-9])\b', main), 'Internal configuration selector in main paper'
assert not re.search(r'\b(?:F0[1-4]|A0[1-9])\b', sup.split('## S24 ',1)[0]), 'Internal selector outside SI reproduction map'
assert 'LegSA-GINS' in main.splitlines()[0]
photo=P/'assets/installation/author_installation_original.jpg'
assert hashlib.sha256(photo.read_bytes()).hexdigest()=='a5aac11a5cde1e99bd31d0342b5e3351d428e92ae5f74ef5547f9a35508cb64b'
assert '[NEED: author-supplied installation photo]' not in main
result={'submission_ready':False,'readiness_boundary':'Original author-retained V3 full matrix is the primary scientific version; later contract-diagnostic natural33/controlled135 and external FGO9/heading9 cohorts have separate roles and identities. Physical acquisition/calibration, author declarations and final submission materials remain pending; formatting/ledger checks do not imply submission readiness.','reader_names_verified':True,'internal_selectors_only_in_supplement_map':True,'author_photo_original_hash_verified':True,'body_word_count':body,'word_count_method':'English alphabetic words including hyphenated compounds; excludes table rows, captions, headings, equations, abstract, declarations and reference list','main_prose_including_abstract_captions_declarations_words':all_prose,'official_word_limit_interpretation':'GPS Solutions says manuscripts about 5000–5500 words without defining exclusions; this body-only count is not a full submission word-count certification.','keywords_count':len(keywords),'current_ledger_exactly_matches_checks':True,'section_word_counts':counts,'ledger_pass':len(ledger),'ledger_fail':0,'figure_status_counts':statuses,'new_figure_qa':sorted(qa,key=lambda x:x['figure']),'raster_review':figs,'package_bytes_at_check':size,'forbidden_terms':0,'copied_original_hash_check_applicable':bool(statuses.get('COPIED',0)),'copied_figure_hashes_match':True}
(P/'FINAL_QA.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
