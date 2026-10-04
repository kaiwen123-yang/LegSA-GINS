"""Metadata inventory and integrity index for presentation-only figure blocks."""
from pathlib import Path
import csv,hashlib,json,struct,datetime
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
def sha(b):return hashlib.sha256(b).hexdigest()
def csvout(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
chapters={'block_01':'Natural full-window errors and all 11 configurations','block_02':'Original trajectory and full attitude errors','block_03':'Full CORE failures, paired ablations, long tails and original ADD','block_04':'Moving-base heading accuracy and denominator','block_05':'Isolated receiver velocity and actual heading decisions','block_06':'Accepted raw-observation heading methods','block_07':'FGO position and strict/dynamic/prior support','block_08':'FGO trajectories and own estimated attitude'}
figures=[];block_receipts=[];sources=set();files_checked=0
for block in sorted(HERE.glob('block_*')):
 ready=json.loads((block/'READY_RECEIPT.json').read_text());assert ready['status']=='READY'
 for f in ready['files']:
  p=block/f['path'];assert sha(p.read_bytes())==f['sha256'],p;assert p.stat().st_size==f['bytes'];files_checked+=1
 build=json.loads((block/'BUILD_RECEIPT.json').read_text());assert sha((block/'BUILD_RECEIPT.json').read_bytes())==ready['build_receipt_sha256']
 for src in build['inputs']:sources.add(src['path'])
 for g in build['figures']:
  png=next(x for x in g['exports'] if x['path'].endswith('.png'));p=block/png['path'];b=p.read_bytes();assert sha(b)==png['sha256'];width,height=struct.unpack('>II',b[16:24])
  figures.append({'figure_id':g['id'],'chapter':chapters[block.name],'png_path':str(p.relative_to(REPO)),'png_sha256':png['sha256'],'png_width':width,'png_height':height,'aspect_ratio':width/height,'pdf_path':str((block/(g['id']+'.pdf')).relative_to(REPO)),'svg_path':str((block/(g['id']+'.svg')).relative_to(REPO)),'dominant_claim':g['dominant_claim'],'panel_role':g['panel_role'],'caption':g['caption'],'actual_png_visual_review':'YES_INDIVIDUAL_FINAL','pdf_separate_visual_review':'NOT_PERFORMED','build_receipt_path':str((block/'BUILD_RECEIPT.json').relative_to(REPO)),'block_ready_sha256':sha((block/'READY_RECEIPT.json').read_bytes()),'PPT_usage':'All 32 available; one scientific question per slide, do not mix execution identities'})
 block_receipts.append({'block':block.name,'ready_sha256':sha((block/'READY_RECEIPT.json').read_bytes()),'build_sha256':sha((block/'BUILD_RECEIPT.json').read_bytes()),'figures':len(build['figures'])})
assert len(figures)==32
csvout(HERE/'FIGURE_CATALOG.csv',figures)
# Complete metadata enumeration of these explicitly named retained figure roots;
# no claim that every old image has been visually inspected.
roots=[REPO/'paper_package/gpss_v0/figures',REPO/'docs/paper_rebuild/hext/HX07R',REPO/'docs/paper_rebuild/hext/EXT_REPRODUCTION/v2_fix',REPO/'docs/paper_rebuild/hext/FGO_REPRODUCTION_FIX_20261004',REPO/'docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/publication',Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/08_FIGURES')]
reviewed={str(REPO/'paper_package/gpss_v0/figures'/name):note for name,note in [('Fig03.png','Three sequences compressed into 2x3 error panels; new R01 separates them.'),('Fig05.png','Finite/failure-aware ECDF; useful retained appendix.'),('Fig08.png','Family-wise original degradation RMSE and failure fractions; useful retained appendix.')]}
reviewed[str(REPO/'docs/paper_rebuild/hext/HX07R/SFIG-HX7.png')]='Four different questions are crowded; new R09/R10 separate error and support.'
reviewed[str(REPO/'docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/publication/BY2H_FULL_WINDOW.png')]='Six-panel accepted FGO diagnostic; new R15/R17/R18 separate questions.'
reviewed[str(roots[-1]/'SECOND_CONTINUATION/MFIG00/MFIG00.png')]='Retained BY2 trajectory/error comparison only; must not relabel it as three trajectories.'
assets=[];root_counts=[]
for root in roots:
 selected=[p for p in sorted(root.rglob('*')) if p.is_file() and p.suffix.lower() in ['.png','.pdf','.svg']]
 root_counts.append({'root':str(root),'retained_files':len(selected),'bytes':sum(p.stat().st_size for p in selected),'archive_members_not_enumerated':True})
 for p in selected:
  raw=p.read_bytes();assert p.read_bytes()==raw
  assets.append({'path':str(p),'root':str(root),'bytes':len(raw),'sha256':sha(raw),'format':p.suffix[1:],'actual_individual_visual_review':'YES' if str(p) in reviewed else 'NO_NOT_ASSESSED','visual_fitness_comment':reviewed.get(str(p),'Metadata-only inventory; no visual quality judgment.')})
csvout(HERE/'EXISTING_ASSET_INVENTORY.csv',assets)
j={'status':'CATALOG_READY','time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_figures':32,'individual_final_PNGs_actually_opened':32,'PNG_PDF_SVG_exports':96,'block_files_integrity_checked':files_checked,'unique_input_paths_across_build_receipts':len(sources),'source_inputs_not_reread_by_this_indexer':True,'blocks':block_receipts,'existing_roots':root_counts,'existing_metadata_files':len(assets),'existing_images_actually_reviewed':len(reviewed),'no_solver_calls':True,'no_evaluator_calls':True,'raw_reference_payload_opens':0,'script_sha256':sha(Path(__file__).read_bytes()),'catalog_sha256':sha((HERE/'FIGURE_CATALOG.csv').read_bytes()),'existing_inventory_sha256':sha((HERE/'EXISTING_ASSET_INVENTORY.csv').read_bytes())}
(HERE/'CATALOG_RECEIPT.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:j[k] for k in ['new_figures','unique_input_paths_across_build_receipts','existing_metadata_files','existing_images_actually_reviewed','catalog_sha256']}))
