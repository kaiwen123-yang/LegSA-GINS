from pathlib import Path
import json
import fitz
from PIL import Image
O=Path(__file__).parent;n='F04_absolute_direction_relative_motion';p=O/(n+'.json');d=json.loads(p.read_text())
d['visual_review']='PASS: color and grayscale viewed; glyphs, arrow-label overlap, transformation-arrow crossing and residual annotation fixed; same metric scales verified.'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
(O/'CAPTIONS_ZH_EN.md').write_text('# '+n+'\n\n'+d['caption_zh']+'\n\n'+d['caption_en']+'\n')
r=fitz.open(O/(n+'.pdf'))[0].rect
item={'id':n,'width_mm':r.width/72*25.4,'height_mm':r.height/72*25.4,'png_pixels':list(Image.open(O/(n+'.png')).size),'formats':['png','pdf','svg','tiff'],'text_audit':d['audits']['text'],'collision_audit':d['audits']['collisions'],'visual_review':d['visual_review'],'source_native_rows':d['native_rows_total'],'new_solver_evaluator_provider_calls':0}
(O/'DELIVERY_CHECKS.json').write_text(json.dumps({'status':'READY_FOR_AUTHOR_REVIEW','figure':item},ensure_ascii=False,indent=2))
(O/'SECTION_PACKAGE.json').write_text(json.dumps({'id':'observability_heading_first_20261012','figures':[item],'readme':'README.md','captions':'CAPTIONS_ZH_EN.md','tables_directory':'source_data','new_solver_evaluator_provider_calls':0},ensure_ascii=False,indent=2))
print(item)
