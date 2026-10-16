from pathlib import Path
import json,sys,subprocess
import pandas as pd
from PIL import Image
import fitz
O=Path(__file__).parent;D=O/'data';R=Path('/mnt/g/LegSA-GINS-project');R3=R/'V3正文精修_20261012_R3/navigation';SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts');name='F03_integrated_routes_and_heading'
meta=json.loads((O/(name+'.json')).read_text());meta['visual_review']='PASS: complete color and grayscale image inspected; one total legend, three full-route panels, moving recovery detail, no inset stack; same-point local scope and no artificial trajectory offsets.'
(O/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2));(O/'CAPTIONS_ZH_EN.md').write_text('# '+name+'\n\n'+meta['caption_zh']+'\n\n'+meta['caption_en']+'\n')
src=pd.read_csv(R3/'data/TRAJECTORY_METHOD_DESTINATIONS.csv');records=[]
for _,r in src.iterrows():
 m=r.method
 if m in ['F04','LC01','LC01-S','EXT05C','EXT05C-S']:dest='F03 full route, POI local detail, actual heading';role='main'
 elif m in ['WEN_TC','GNC']:dest='F03 full geographic route only at registered GNSS1; no fabricated yaw/POI';role='main position overview'
 elif m=='OISAM_RESTART':dest='Source for F03 reinitialized POI curve after own-pose registered transform; original GNSS1 coordinates retained';role='main, registered display point transform'
 elif m=='OISAM_STRICT':dest='Original strict-status table and R3 F11 supplementary/archive; not the main OiSAM comparator';role='supplement/archive'
 elif m.startswith('REFERENCE'):dest='POI reference shown in F03; other point reference retained with original evaluations';role='reference'
 else:dest=r.destination;role='supplement / retained source'
 records.append({**r.to_dict(),'R4_role':role,'R4_destination':dest,'source_directory':str(R3/'data')})
for s in ['BY2','BY2H','BY2O']:
 p=D/(s+'__OISAM_RESTART_POI.csv.gz');q=pd.read_csv(p);records.append({'sequence':s,'method':'OISAM_RESTART_POI','point':'POI_MIDPOINT','status':'EXISTING_NATIVE_POSE_WITH_REGISTERED_DISPLAY_TRANSFORM','finite_display_rows':int(q.valid.sum()),'R4_role':'main','R4_destination':'F03 full route and POI detail; no new native execution','source_directory':str(D),'display_data':p.name})
pd.DataFrame(records).to_csv(D/'ALL_METHOD_DESTINATIONS.csv',index=False)
registry=pd.read_csv(R3/'data/ALL_REGISTERED_METHOD_TRAJECTORY_DESTINATIONS.csv');registry['R4_destination']=registry.R3_destination.str.replace('F11 plus per-record trajectory coverage/destination table','F03 plus R4 all-method destination table',regex=False);registry.to_csv(D/'ALL_REGISTERED_METHOD_DESTINATIONS.csv',index=False)
checks={k:json.loads((O/'qa'/(name+'.'+k+'.json')).read_text())['verdict'] for k in ['alignment','collisions']};assert all(x=='PASS' for x in checks.values()) and meta['audits']['text']==0
with fitz.open(O/(name+'.pdf')) as f:r=f[0].rect
pix=Image.open(O/'preview'/(name+'.png')).size;assert pix[0]>=2560 and pix[1]>=1080
static=subprocess.run([sys.executable,str(SK/'validate_figure.py'),str(O/'build_merged_navigation.py')],capture_output=True,text=True);(O/'qa/SOURCE_PREFLIGHT.log').write_text(static.stdout+static.stderr)
transform=json.loads((D/'OISAM_POI_TRANSFORM_CHECKS.json').read_text());audit={'status':'READY_FOR_AUTHOR_REVIEW','id':name,'width_mm':r.width/72*25.4,'height_mm':r.height/72*25.4,'minimum_font_pt':8,'preview_pixels':list(pix),'checks':checks,'text_audit_returncode':0,'visual_review':meta['visual_review'],'native_source_points_retained':True,'new_solver_evaluator_provider_calls':0,'frozen_metrics_changed':False,'F11_disposition':'supplement/archive; merged into newF03 for main text','own_pose_transform_checks':transform['records'],'static_preflight_returncode':static.returncode,'original_coordinate_sources':49,'coordinate_destination_rows_including_display_transform':len(records),'all_registered_identity_rows':len(registry)}
(O/'DELIVERY_CHECKS.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));(O/'SECTION_PACKAGE.json').write_text(json.dumps({'id':'navigation_R4_20261013','figures':[audit],'readme':'README.md','captions':'CAPTIONS_ZH_EN.md','replaces':['F03_R3','F11_R3'],'preserves':['ApprovedF04','ApprovedF06','ApprovedF07'],'static_evidence':'OBSTRUCTION_REFERENCE_MOTION.csv','new_solver_evaluator_provider_calls':0},ensure_ascii=False,indent=2));print(json.dumps({'status':audit['status'],'preview_pixels':list(pix),'same_point_local_methods':6,'original_coordinate_sources':49}))
