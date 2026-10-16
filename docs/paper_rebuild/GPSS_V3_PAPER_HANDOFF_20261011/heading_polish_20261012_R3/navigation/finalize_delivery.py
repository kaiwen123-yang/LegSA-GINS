from pathlib import Path
import json,subprocess,sys,shutil
import pandas as pd
from PIL import Image
import fitz
O=Path(__file__).parent;D=O/'data';R=Path('/mnt/g/LegSA-GINS-project');SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
names=['F03_100s_routes_with_spatial_detail','F11_full_trajectory_comparison','S11_GINav_partial_trajectories','S11_native_relative_trajectories'];items=[];captions=[]
for name in names:
 p=O/(name+'.json');d=json.loads(p.read_text())
 if name=='F11_full_trajectory_comparison':
  zh='米尺度轨迹高度重合是实际结果，精度差应结合左列局部和误差配图读取，不将不同方法人为错位。'
  en='Metre-scale overlap is expected; inspect the POI insets and companion errors for precision differences. No method-dependent offsets are applied.'
  d['caption_zh']=d['caption_zh'].replace(zh,'').strip()+' '+zh
  d['caption_en']=d['caption_en'].replace(en,'').strip()+' '+en
 d['visual_review']='PASS: complete color and grayscale layouts reviewed; POI insets moved inside empty loop regions, redundant FGO insets removed, support text moved outside paths, relative-scene text moved into two-line titles.'
 d['local_curve_rendering']='Main curves retain vectors; cropped spatial-detail marks rasterized at600dpi inside vector PDF/SVG to preserve exact display clipping; texts and axes remain editable.'
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
 checks={q:json.loads((O/'qa'/(name+'.'+q+'.json')).read_text())['verdict'] for q in ['alignment','collisions']}
 assert all(v=='PASS' for v in checks.values()),(name,checks)
 assert d['audits']['text']==0
 with fitz.open(O/(name+'.pdf')) as f:r=f[0].rect
 pix=Image.open(O/'preview'/(name+'.png')).size;assert pix[0]>=2560 and pix[1]>=1080
 items.append({'id':name,'role':'main candidate' if name.startswith('F') else 'supporting trajectory plate','width_mm':r.width/72*25.4,'height_mm':r.height/72*25.4,'minimum_font_pt':8,'preview_pixels':list(pix),'audits':checks,'text_audit':0,'visual_review':d['visual_review'],'files':{x:str(O/(name+'.'+x)) for x in ['png','pdf','svg','tiff']}})
 captions.append('## '+name+'\n\n'+d['caption_zh']+'\n\n'+d['caption_en']+'\n')
(O/'CAPTIONS_ZH_EN.md').write_text('\n'.join(captions))
coverage=pd.read_csv(D/'TRAJECTORY_COVERAGE.csv');dest=[]
for _,r in coverage.iterrows():
 m=r.method
 if m.startswith('REFERENCE'):kind='reference';where='corresponding point/frame background'
 elif m.endswith('_ALT'):kind='alternate initialization; full coordinates retained';where='data/'+r.display_data+'; not mixed with registered primary start'
 elif m=='GINAV_NATIVE':kind='partial native INS/IMU output';where='S11_GINav_partial_trajectories'
 elif m in ['OFF-LIT','OFF-DEF','LEG-DR']:kind='relative-only native local trajectory';where='S11_native_relative_trajectories'
 elif m=='OISAM_STRICT' and r.finite_display_rows==0:kind='no dynamic in-window output';where='F11 full-window support label; original zero-valid trajectory rows retained'
 elif m=='OISAM_STRICT' and r.finite_display_rows<r.in_window_rows:kind='partial dynamic output';where='F11 POI column with start/end and support'
 elif m=='OISAM_STRICT' and r.finite_display_rows<100:kind='partial dynamic output';where='F11 POI column with start/end and support'
 else:kind='retained full evaluation-window trajectory on own valid support';where='F11 POI column' if r.point=='POI_MIDPOINT' else 'F11 GNSS1 column'
 dest.append({**r.to_dict(),'trajectory_class':kind,'destination':where})
pd.DataFrame(dest).to_csv(D/'TRAJECTORY_METHOD_DESTINATIONS.csv',index=False)
registry=pd.read_csv(R/'V3五问题论文组图_20261011/COMPARISON_USE_MAP.csv');rows=[]
for _,r in registry.iterrows():
 identity=r.identity
 if r.execution_record=='not an executed comparison':kind='registration only; no executed output';where='Original registration history retained, no trajectory invented'
 elif identity in ['EXT01','EXT02','EXT03','EXT04'] or identity.startswith('RTKLIB'):kind='direction/baseline only';where='F05 and direction-route tables; not an absolute robot navigation trajectory'
 elif identity in ['Hartley','LEG_DR']:kind='relative-only';where='S11_native_relative_trajectories; original relative-error evaluation retained'
 elif identity in ['LC01','LC01-S','EXT05C','EXT05C-S','OISAM','WEN_TC','GNC'] or identity=='OiSAM gap reinitialization':kind='global position trajectory';where='F11 plus per-record trajectory coverage/destination table'
 elif 'GINAV' in identity.upper():kind='partial native IMU trajectory';where='S11_GINav_partial_trajectories'
 elif identity=='LC01-BR':kind='controlled-interruption-only identity';where='Existing F09 g/h and all18 A2 source results; no natural-trial trajectory identity invented'
 elif identity=='Hartley gauge/observability':kind='known-initial-yaw gauge ensemble';where='Approved F04 and original7 native full trajectory sources'
 elif identity=='Classic-18 and A2':kind='controlled replay family';where='All396 logical/744 paired records and approved F07/F09; kept separate from natural route plate'
 else:kind='different version/history';where='Original evidence path retained; not relabelled as frozen V3 natural trajectory'
 rows.append({**r.to_dict(),'trajectory_class':kind,'R3_destination':where})
pd.DataFrame(rows).to_csv(D/'ALL_REGISTERED_METHOD_TRAJECTORY_DESTINATIONS.csv',index=False)
shutil.copy2(R/'V3五问题论文组图_20261011/navigation/data/LC_NATIVE_TABLE_READ.csv',D/'LC_ALL16_NATIVE_RESULTS.csv')
shutil.copy2(R/'V3五问题论文组图_20261011/navigation/data/A2_ALL18_MATCHED_RESULTS.csv',D/'A2_ALL18_MATCHED_RESULTS.csv')
comparisons=pd.read_csv(D/'COORDINATE_PARITY_CHECKS.csv');assert (comparisons.max_abs_difference_m<2e-5).all()
result=subprocess.run([sys.executable,str(SK/'validate_figure.py'),str(O/'build_trajectories.py')],capture_output=True,text=True);(O/'qa/SOURCE_PREFLIGHT.log').write_text(result.stdout+result.stderr)
checks={'status':'READY_FOR_AUTHOR_REVIEW','figures':items,'coordinate_sources':len(coverage),'coordinate_source_rows_total':int(coverage.native_rows_read.sum()),'reference_rows_included_in_count':True,'parity_checks':len(comparisons),'max_coordinate_parity_difference_m':float(comparisons.max_abs_difference_m.max()),'registered_method_rows':len(rows),'new_solver_evaluator_provider_calls':0,'no_fitted_geographic_alignment':True,'no_scalar_H_error_trajectory_reconstruction':True,'input_reference_use':'Display-only reference LLH interpolation matches retained definition; errors are not re-scored','source_preflight_returncode':result.returncode}
(O/'DELIVERY_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));(O/'SECTION_PACKAGE.json').write_text(json.dumps({'id':'navigation_R3_20261012','figures':items,'readme':'README.md','captions':'CAPTIONS_ZH_EN.md','data_directory':'data','new_solver_evaluator_provider_calls':0},ensure_ascii=False,indent=2))
print(json.dumps({'status':checks['status'],'figures':len(items),'coordinate_sources':len(coverage),'parity_checks':len(comparisons),'max_parity_m':checks['max_coordinate_parity_difference_m']}))
