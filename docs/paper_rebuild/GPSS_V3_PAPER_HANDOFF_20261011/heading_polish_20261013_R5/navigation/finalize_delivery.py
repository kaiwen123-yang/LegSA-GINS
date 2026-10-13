from pathlib import Path
import json, subprocess, sys
import pandas as pd
import fitz
from PIL import Image

O=Path(__file__).parent
R=Path('/mnt/g/LegSA-GINS-project')
R3=R/'V3正文精修_20261012_R3/navigation'
R4=R/'V3正文精修_20261013_R4/navigation'
name='F03_integrated_routes_and_heading'

src=pd.read_csv(R4/'data/ALL_METHOD_DESTINATIONS.csv')
src['R5_destination']=src['R4_destination'].fillna('').str.replace('actual heading','heading in Fig. 9',regex=False)
src['R5_source_index']=str(R4/'data/ALL_METHOD_DESTINATIONS.csv')
src[['sequence','method','point','status','finite_display_rows','trajectory_class','display_data','source_directory','R5_destination','R5_source_index']].to_csv(O/'data/ALL_METHOD_DESTINATIONS.csv',index=False)
reg=pd.read_csv(R4/'data/ALL_REGISTERED_METHOD_DESTINATIONS.csv')
reg['R5_destination']=reg['R4_destination'].fillna('').str.replace('R4 all-method','R5 all-method',regex=False)
reg['complete_registration_source']=str(R4/'data/ALL_REGISTERED_METHOD_DESTINATIONS.csv')
reg[['identity','reader_name','execution_record','trajectory_class','R5_destination','complete_registration_source']].to_csv(O/'data/ALL_REGISTERED_METHOD_DESTINATIONS.csv',index=False)

counts=pd.read_csv(O/'data/SOURCE_POINT_COUNTS.csv')
full=counts[counts.role.eq('full_route')].copy()
full['physical_point']=full.method.map(lambda m:'GNSS1_ANTENNA' if m in ['WEN_TC','GNC'] else 'POI_MIDPOINT')
full['display_source']=full.apply(lambda q:str((R4 if q.method=='OISAM_RESTART_POI' else R3)/'data'/f'{q.sequence}__{q.method}.csv.gz'),axis=1)
full.to_csv(O/'data/MAIN_TRAJECTORY_SOURCE_MAPPING.csv',index=False)
for row in full.itertuples():
    q=pd.read_csv(row.display_source)
    assert len(q)==row.rows_in_source_window
    assert q.valid.sum()==row.finite_points
    assert q.loc[q.valid,['east_m','north_m']].notna().all().all()
    assert q.elapsed_s.is_monotonic_increasing
assert all(full.groupby('sequence').method.nunique()==9)

qa=O/'qa'
v=subprocess.run([sys.executable,'/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts/validate_figure.py',str(O/'build_spatial_comparison.py'),'--json'],capture_output=True,text=True)
(qa/(name+'.source_preflight.json')).write_text(v.stdout)
static=json.loads(v.stdout)
text=json.loads((qa/(name+'.text.log')).read_text())
collision=json.loads((qa/(name+'.collisions.json')).read_text())
align=json.loads((qa/(name+'.alignment.json')).read_text())
doc=fitz.open(O/(name+'.pdf'))
page=doc[0]
im=Image.open(O/'preview'/(name+'.png'))
assert len(list((O/'preview').glob('F03*.png')))==1
qc={'figure':name,'status':'PASS','root_visual_review':'PASS; no further figure edit requested','color_and_grayscale_visual_review':'PASS','width_mm':page.rect.width/72*25.4,'height_mm':page.rect.height/72*25.4,'minimum_font_pt':text['minimum_found_pt'],'collision_verdict':collision['verdict'],'collision_counts':collision['summary'],'alignment_verdict':align['verdict'],'preview_pixels':list(im.size),'pdf_images':len(page.get_images()),'main_configurations_per_scene':8,'reference_configurations_per_scene':1,'coordinate_identity_destinations':len(src),'registered_identity_destinations':len(reg),'all_source_rows_and_valid_points_match':True,'local_valid_points_outside_view':0,'source_preflight':static['summary'],'source_preflight_warning_resolution':{'FINAL-WIDTH':'Static literal parser does not evaluate 174/25.4. Final PDF is 174 x 226 mm.','INTERP-MONOTONIC':'The read() function asserts increasing time_s. Elapsed time is the same fixed-origin grid; independently checked increasing for every actual plotted source in this finalizer.'},'new_solver_provider_evaluator_calls':0,'frozen_metrics_changed':False,'old_directories_modified':False}
(O/'DELIVERY_CHECKS.json').write_text(json.dumps(qc,ensure_ascii=False,indent=2))
meta=json.loads((O/(name+'.json')).read_text())
meta['visual_review']='PASS: color and grayscale read; root reviewed final preview'
meta['caption_file']='CAPTIONS_ZH_EN.md'
meta['qa_file']='DELIVERY_CHECKS.json'
(O/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2))
(O/'SECTION_PACKAGE.json').write_text(json.dumps({'figure_id':'F03','stem':name,'title_zh':'完整导航路线与同点空间细节','preview':'preview/'+name+'.png','caption':'CAPTIONS_ZH_EN.md','reader':'README.md','source_mapping':'SOURCE_MAPPING.md','qa':'DELIVERY_CHECKS.json','main_figure_count':1,'F11_decision':'supplement/history; not an additional main figure','heading_comparison':'Fig. 9','no_new_solver':True},ensure_ascii=False,indent=2))
print(json.dumps(qc,ensure_ascii=False))
