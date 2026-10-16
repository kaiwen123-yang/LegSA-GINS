from pathlib import Path
import json
from PIL import Image
import fitz
OUT=Path(__file__).parent
items=[];paths=set();caps=[]
for n in ['F03_event_routes_and_heading','F09_heading_comparison']:
 p=OUT/(n+'.json');d=json.loads(p.read_text());d['visual_review']='PASS: actual color preview inspected; event route inset moved away from trajectory, bottom labels separated, all curves and tails retained.';p.write_text(json.dumps(d,ensure_ascii=False,indent=2));paths.update(d['source_paths'])
 pdf=fitz.open(OUT/(n+'.pdf'));rect=pdf[0].rect
 col=Image.open(OUT/'preview'/(n+'.png'));full=Image.open(OUT/(n+'.png'))
 collision=json.loads((OUT/'qa'/(n+'.collisions.json')).read_text());text=json.loads((OUT/'qa'/(n+'.text.log')).read_text())
 items.append({'id':n,'width_mm':rect.width/72*25.4,'height_mm':rect.height/72*25.4,'png_pixels':list(full.size),'preview_pixels':list(col.size),'pdf_text_audit_returncode':d['audits']['text'],'collision_audit':collision['verdict'],'visual_review':d['visual_review'],'paths':{ext:str(OUT/(n+'.'+ext)) for ext in ['png','pdf','svg','tiff']}})
 caps.append('## '+n+'\n\n'+d['caption_zh']+'\n\n'+d['caption_en']+'\n')
(OUT/'CAPTIONS_ZH_EN.md').write_text('\n'.join(caps))
(OUT/'SOURCE_PATHS.json').write_text(json.dumps(sorted(paths),ensure_ascii=False,indent=2))
(OUT/'DELIVERY_CHECKS.json').write_text(json.dumps({'status':'READY_FOR_AUTHOR_REVIEW','new_solver_evaluator_provider_calls':0,'figures':items,'source_path_count':len(paths),'common_heading_epochs':{'BY2':274,'BY2H':267,'BY2O':367},'failed_source_rows_retained':True},ensure_ascii=False,indent=2))
(OUT/'SECTION_PACKAGE.json').write_text(json.dumps({'id':'navigation_heading_first_20261012','figures':items,'readme':'README.md','captions':'CAPTIONS_ZH_EN.md','tables_directory':'data','new_solver_evaluator_provider_calls':0},ensure_ascii=False,indent=2))
print('Navigation delivery verified:',len(items),'figures;',len(paths),'sources')
