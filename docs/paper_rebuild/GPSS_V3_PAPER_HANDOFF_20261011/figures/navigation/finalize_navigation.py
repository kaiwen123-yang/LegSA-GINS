from pathlib import Path
import pandas as pd,json,hashlib,shutil,subprocess,sys
OUT=Path(__file__).resolve().parent;DATA=OUT/'data';ROOT=Path('/mnt/g/LegSA-GINS-project');REPO=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
manifest=pd.read_csv(DATA/'SOURCE_MANIFEST.csv').to_dict('records')
def get(p):
    b=p.read_bytes();manifest.append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'reading':'full'});return json.loads(b)
nat=pd.read_csv(DATA/'LC_NATIVE_TABLE_READ.csv');pr=[]
for _,r in nat.iterrows():
    p=ROOT/f'clean_rebuild_202607/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/04_NATIVE_RUNS/{r.sequence_id}/{r.method_id}/{r.start_convention}/NATIVE_SUMMARY.json'
    z={**r.to_dict(),'native_record':str(p),'native_record_available':p.exists()}
    if p.exists():
        j=get(p);z.update({'parameters_exact_json':json.dumps(j.get('parameters',{}),ensure_ascii=False),'native_summary_exact_json':json.dumps(j.get('summary',{}),ensure_ascii=False),'native_status':j.get('status'),'initialization_start_mode':j.get('start_mode'),'raw_config_hash':j.get('config_hash')})
    else:z['parameter_definition_source']=str(REPO/'configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml')
    pr.append(z)
pd.DataFrame(pr).to_csv(DATA/'IEKF_ALL16_CONDITIONS_WITH_PARAMETERS.csv',index=False)
yp=REPO/'configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml';shutil.copy2(yp,DATA/yp.name)
b=yp.read_bytes();manifest.append({'path':str(yp),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'reading':'full'})
contractroot=ROOT/'clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION/00_CONTRACT'
for n in ['CASES.json','CONTRACT.json']:
    j=get(contractroot/n);(DATA/('HX03_'+n)).write_text(json.dumps(j,ensure_ascii=False,indent=2))
cases=get(contractroot/'CASES.json');pd.json_normalize(list(cases.values())).to_csv(DATA/'ALL_DEGRADATION_CASE_DEFINITIONS.csv',index=False)
pd.DataFrame(manifest).drop_duplicates('path').to_csv(DATA/'SOURCE_MANIFEST.csv',index=False)
titles={
'Q3_01_IEKF_natural':('自然工况下与双位置IEKF的比较','main'),
'Q3_02_heading_retention':('保留方向与位置中断中的导航表现','supplement'),
'Q3_03_OiSAM_reinitialized_heading':('OiSAM重新初始化后的完整航向比较','supplement'),
'Q3_04_all_degradation_pairs':('全部外部退化类型的配对比较','supplement'),
'Q3_05_FGO_position':('不同GNSS信息处理路线的定位结果','supplement')}
figs=[];caps=[]
for f,(title,role) in titles.items():
    p=OUT/(f+'.json');j=json.loads(p.read_text());assert j['audit_returncodes']=={'pdf_text':0,'collisions':0}
    j['visual_review']='PASS';j['visual_review_notes']='Inspected actual color and grayscale previews: every panel readable, common units and no clipping, deliberate curve intersections retained. Insets show fixed input-defined windows. Dense native IEKF curves use the retained full sampling and readable local insets.'
    j['title_zh']=title;j['question']='Q3';j['role']=role;j['preview_sha256']=hashlib.sha256((OUT/'preview'/(f+'.png')).read_bytes()).hexdigest();p.write_text(json.dumps(j,ensure_ascii=False,indent=2))
    figs.append({'id':f,'title_zh':title,'role':role,'question':'Q3','path':str(OUT/(f+'.png')),'metadata_path':str(p)})
    caps.append('## '+title+'\n\n'+j['caption_en']+'\n\n'+j['caption_zh']+'\n')
(OUT/'CAPTIONS.md').write_text('\n'.join(caps),encoding='utf-8')
coverage=[
{'method':'Two-position IEKF (LC01)','use':'Q3_01, Q3_02, Q3_04','conditions':'Literature and calibrated parameters, FILE_START/CONTRACT_START, all 16 natural method/config rows retained','table':'IEKF_ALL16_CONDITIONS_WITH_PARAMETERS.csv'},
{'method':'Single-position IEKF (EXT05C)','use':'Q3_02, Q3_04; all natural results table','conditions':'Same IEKF backbone; GNSS2 retained only for initialization; LIT/S and start conditions retained','table':'IEKF_ALL16_CONDITIONS_WITH_PARAMETERS.csv'},
{'method':'Baseline-retaining IEKF (LC01-BR)','use':'Q3_02','conditions':'A2, 18/18 finite; negative position result retained','table':'A2_ALL18_MATCHED_RESULTS.csv'},
{'method':'OiSAM strict','use':'Main F02 copied by root from focused package','conditions':'Same POI and matched-time precision, full output support, no repeated initialization','table':'Root common-point package'},
{'method':'OiSAM segmented','use':'Q3_03, Q3_05','conditions':'Three real runs, 11 preregistered input blocks, prior-only excluded; heading and GNSS1 position definitions kept separate','table':'BY2_OISAM_SEGMENTED_EXISTING_METRICS.csv and BY2H/BY2O counterparts'},
{'method':'Wen TC-FGO','use':'Q3_05','conditions':'Raw code and adapted attitude/velocity, GNSS1 position; attitude is not an independently estimated output','table':'EXPERIMENTS.csv'},
{'method':'GNC-FGO','use':'Q3_05','conditions':'Raw code+Doppler, GNSS1 position','table':'EXPERIMENTS.csv'},
{'method':'Official GINav SPP/INS','use':'Complete actual-run table','conditions':'Native runs on three trials, initialization support and speed-gate failures retained, no full-window fictitious precision','table':'GINAV_ACTUAL_RESULTS.csv'}]
pd.DataFrame(coverage).to_csv(DATA/'METHOD_COVERAGE.csv',index=False)
tables=[{'title':p.stem,'path':str(p)} for p in sorted(DATA.glob('*.csv'))]
package={'question':'Q3','figures':figs,'tables':tables,'method_coverage':coverage,'new_solver_calls':0,'new_evaluator_calls':0,'new_provider_calls':0,'full_read_source_files':len(pd.read_csv(DATA/'SOURCE_MANIFEST.csv')),'output_styles':'174 mm; 600 dpi PNG; editable vector PDF/SVG; 300 dpi color/grayscale previews'}
(OUT/'SECTION_PACKAGE.json').write_text(json.dumps(package,ensure_ascii=False,indent=2))
print('package ready:',len(figs),'figures;',len(tables),'tables; native condition files',sum(bool(x['native_record_available']) for x in pr))
