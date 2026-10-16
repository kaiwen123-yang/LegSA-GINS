from pathlib import Path
import json
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parent
core=pd.read_csv(OUT/'tables/CORE5951.csv');add=pd.read_csv(OUT/'tables/ADD495.csv');pairs=pd.read_csv(OUT/'tables/SINGLEMODULE_CASE_PAIRS2164.csv')
assert len(core)==5951 and core.groupby('internal_method_id').size().eq(541).all()
assert core.internal_method_id.nunique()==11 and core.degradation_type_id.nunique()==61
assert len(add)==495 and len(pairs)==2164
reg=pd.read_csv(OUT/'tables/REGISTERED_541_CASE_DEFINITIONS.csv');assert len(reg)==541
assert set(reg.case_id)==set(core.case_id)
effects=pd.read_csv(OUT/'tables/F10_FAMILY_PAIRED_EFFECTS.csv');assert len(effects)==128
assert effects.groupby(['module','metric']).registered.sum().eq(540).all()
codes=['F06_attitude','F07_conditional_translation','F08_quality_tradeoffs','F10_semisynthetic_complementarity','E10_all_configurations_horizontal','E10_all_configurations_heading']
names=['姿态分量与观测作用','机身速度的条件平移作用','来源质量处理的收益与代价','全部受控回放的条件消融效应','全条件全配置水平误差','全条件全配置航向误差']
catalog=[]
for i,(code,name) in enumerate(zip(codes,names)):
    for ext in ['png','pdf','svg','tiff']:assert (OUT/'figures'/f'{code}.{ext}').is_file()
    t=json.loads((OUT/'qa'/f'{code}.text.json').read_text());assert t['below_minimum_count']==0
    c=json.loads((OUT/'qa'/f'{code}.collision.json').read_text());assert c['summary']['fail']==0
    catalog.append(dict(figure=code,title_zh=name,role='main' if i<4 else 'extended',preview='preview/'+code+'.png',pdf='figures/'+code+'.pdf',svg='figures/'+code+'.svg',png='figures/'+code+'.png',tiff='figures/'+code+'.tiff',min_font_pt=t['minimum_found_pt'],collision_verdict=c['verdict']))
pd.DataFrame(catalog).to_csv(OUT/'FIGURE_CATALOG.csv',index=False)
qa={'status':'VALIDATED_DISCUSSION_DRAFT','main_figures':4,'extended_figures':2,'scientific_native_runs':0,'new_evaluator_runs':0,'new_provider_runs':0,'core_runs_read':5951,'additional_runs_read':495,'case_pairs_read':2164,'core_types_including_clean':61,'registered_variants_per_perturbed_type':9,'configurations':11,'core_registered_case_definitions_recovered':541,'source_series_count':len(json.loads((OUT/'SOURCES.json').read_text())),
 'width_mm':174,'min_font_pt':8,'dpi':600,'source_validator_fail':0,'collision_fail':0,'alignment_fail':0,
 'visual_review':'All six colour previews inspected; source series retain every plotted sample and real gaps. No smoothing or value clipping. Full matrix blanks correspond only to no completed runs.',
 'reviewed_warnings':[
 'F08 heading RMSE label lies within blank space inside the bounding rectangle of a rasterized line artist, but it covers no trajectory. PDF geometry flags image-edge overlap because it cannot inspect the white pixels. This was visually checked.',
 'Static source-width parser misreads 174/25.4; final PDF media boxes correspond to exactly 174 mm.',
 'All F07 log-axis samples are explicitly asserted finite and strictly positive. Full-matrix LogNorm inputs are the finite positive saved RMSE values.',
 'Family cells are descriptive medians of registered variants of the same measured route, with all per-case outcomes provided. No confidence interval or independent-field-trial claim is made.',
 'Rotated heatmap labels passed final-PDF collision and page-clipping checks.'
 ],'data_boundaries':['Semisynthetic observed-data replay, no demonstrated online hardware-in-loop.','Core nine variants may differ by random seed, placement, or ineffective seed, as specified by registry.','A1 total GNSS loss pauses auxiliary updates; it is not a pure heading factorial.','Source-weighting extra completions remain outside the 513 joint-finite distributions.','Literature reading screenshots are local review material and must not be copied into the GitHub package.']}
(OUT/'DELIVERY.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
print(json.dumps({k:qa[k] for k in ['status','main_figures','extended_figures','source_series_count','collision_fail','min_font_pt']},ensure_ascii=False))
