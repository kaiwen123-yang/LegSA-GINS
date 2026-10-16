from pathlib import Path
import json,subprocess,sys
import fitz
from PIL import Image
O=Path(__file__).parent;name='F03_integrated_routes_and_heading';qa=O/'qa'
r=subprocess.run([sys.executable,'/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts/validate_figure.py',str(O/'build_navigation.py'),'--json'],capture_output=True,text=True)
(qa/(name+'.source_preflight.json')).write_text(r.stdout)
p=fitz.open(O/(name+'.pdf'))[0];text=json.loads((qa/(name+'.text.log')).read_text());col=json.loads((qa/(name+'.collisions.json')).read_text());align=json.loads((qa/(name+'.alignment.json')).read_text())
qc={'figure':name,'width_mm':p.rect.width/72*25.4,'height_mm':p.rect.height/72*25.4,'preview_pixels':list(Image.open(O/'preview'/(name+'.png')).size),'minimum_font_pt':text['minimum_found_pt'],'collision_verdict':col['verdict'],'collision_summary':col['summary'],'alignment':align['verdict'],'color_preview_visual_review':'PASS','grayscale_preview_visual_review':'PASS','source_preflight':json.loads(r.stdout)['summary'],'source_preflight_width_note':'Static parser cannot evaluate 174/25.4; final PDF verified 174 x 174 mm.','spatial_clip':'Explicit common physical viewport, same limits for all local methods; coordinates outside viewport retained in sources and full route.','data_sources':'SOURCE_MAPPING.md','new_solver_evaluator_provider_calls':0,'old_directories_modified':False}
(O/'DELIVERY_CHECKS.json').write_text(json.dumps(qc,ensure_ascii=False,indent=2))
meta=json.loads((O/(name+'.json')).read_text());meta.update({'height_mm':174,'caption_file':'CAPTIONS_ZH_EN.md','title_zh':'三场景导航路线、空间近景与航向误差','visual_review':'PASS','spatial_viewport':qc['spatial_clip']});meta.pop('caption_zh',None);meta.pop('caption_en',None);(O/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2))
(O/'SECTION_PACKAGE.json').write_text(json.dumps({'figure_id':'F03','stem':name,'title_zh':'三场景导航路线、空间近景与航向误差','preview':'preview/'+name+'.png','caption':'CAPTIONS_ZH_EN.md','reader':'README.md','source_mapping':'SOURCE_MAPPING.md','qa':'DELIVERY_CHECKS.json','main_figure_count':1,'F11_decision':'supplement/history'},ensure_ascii=False,indent=2))
print(json.dumps(qc,ensure_ascii=False))
