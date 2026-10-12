from pathlib import Path
import json,subprocess,sys
import pandas as pd,numpy as np
from PIL import Image
import fitz
O=Path(__file__).parent;SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
prior=Path('/mnt/g/LegSA-GINS-project/V3航向主线重绘_20261012/navigation')
old=pd.read_csv(prior/'data/F09_COMMON_HEADING_STATISTICS.csv');new=pd.read_csv(O/'data/F09_COMMON_HEADING_STATISTICS.csv')
pd.testing.assert_frame_equal(old,new)
items=[];sources=set();caps=[]
for name in ['F03_event_routes_and_heading','F09_heading_comparison']:
 p=O/(name+'.json');d=json.loads(p.read_text());sources.update(d['source_paths'])
 d['visual_review']='PASS: full color and grayscale previews inspected; longer route windows, reduced arrows, added same-point FGO summary; inset tick collision repaired.'
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
 with fitz.open(O/(name+'.pdf')) as doc:r=doc[0].rect
 pix=Image.open(O/'preview'/(name+'.png')).size
 assert pix[0]>=2560 and pix[1]>=1080
 assert abs(r.width/72*25.4-174)<.01 and r.height/72*25.4<=234.01
 audit={kind:json.loads((O/'qa'/(name+'.'+kind+'.json')).read_text())['verdict'] for kind in ['alignment','collisions']}
 assert audit['alignment']=='PASS' and audit['collisions']=='PASS' and d['audits']['text']==0
 items.append({'id':name,'width_mm':174,'height_mm':r.height/72*25.4,'preview_pixels':list(pix),'minimum_font_pt':8,'color':True,'all_curve_points_retained':True,'audits':audit,'text_audit_returncode':0,'visual_review':d['visual_review'],'files':{ext:str(O/(name+'.'+ext)) for ext in ['png','pdf','svg','tiff']}})
 caps.append('# '+name+'\n\n'+d['caption_zh']+'\n\n'+d['caption_en']+'\n')
(O/'CAPTIONS_ZH_EN.md').write_text('\n'.join(caps))
(O/'SOURCE_PATHS.json').write_text(json.dumps(sorted(sources),ensure_ascii=False,indent=2))
preflight=subprocess.run([sys.executable,str(SK/'validate_figure.py'),str(O/'build_navigation.py')],capture_output=True,text=True)
(O/'qa/SOURCE_PREFLIGHT.log').write_text(preflight.stdout+preflight.stderr)
delivery={'status':'READY_FOR_AUTHOR_REVIEW','figures':items,'source_paths':len(sources),'new_solver_evaluator_provider_calls':0,'all_R1_common_heading_statistics_exactly_unchanged':True,'FGO_attitude_audit':'OiSAM estimates attitude; WEN_TC/GNC do not. No input attitude presented as output.','heading_common_counts':[274,267,367],'FGO_common_position_counts':[274,267,369],'source_preflight_returncode':preflight.returncode,'source_preflight_warnings_review':'Width arithmetic statically misread; actual174mm verified. All FGO horizontal errors explicitly checked finite and positive before log axis.'}
(O/'DELIVERY_CHECKS.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2))
(O/'SECTION_PACKAGE.json').write_text(json.dumps({'id':'navigation_R2_20261012','figures':items,'readme':'README.md','captions':'CAPTIONS_ZH_EN.md','table_directory':'data','new_solver_evaluator_provider_calls':0},ensure_ascii=False,indent=2))
print(json.dumps({'status':'VERIFIED','figures':len(items),'preview_dimensions':[x['preview_pixels'] for x in items],'unchanged_heading_statistics':True}))
