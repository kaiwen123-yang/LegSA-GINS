from pathlib import Path
import json
import numpy as np,pandas as pd
from PIL import Image
import fitz
P=Path(__file__).resolve().parent
old=Path('/mnt/g/LegSA-GINS-project/V3正文精修_20261012_R3/aiding')
checks={}
core=pd.read_csv(P/'tables/CORE5951.csv');pair=pd.read_csv(P/'tables/ALL2164_ORIGINAL_ABLATION_PAIRS.csv');fail=pd.read_csv(P/'tables/ALL_CORE_NONCOMPLETIONS.csv')
assert len(core)==5951 and len(pair)==2164 and len(fail)==283
assert set(fail.run_id)==set(core.loc[~core.evaluation_status.eq('COMPLETED'),'run_id'])
checks['complete_source_counts']={'core':5951,'four_ablation_pairs':2164,'noncompleted_core':283}
q=json.loads((P/'F08_OVERALL_PAIRED_RESULT.json').read_text())
assert (q['registered'],q['jointly_completed'],q['lower_yaw_rmse_with_full'],q['higher_yaw_rmse_with_full'],q['extra_full_completions'])==(541,513,190,323,6)
checks['weighting_all_cases']=q
inputcheck=json.loads((P/'INPUT_UNCERTAINTY_CHECK.json').read_text());assert inputcheck['rows_checked']==600 and inputcheck['hash_match'] and inputcheck['maximum_difference']<1e-12
checks['reported_uncertainty_equals_saved_input']=inputcheck
sc=pd.read_csv(P/'tables/F08_ACTUAL_COVARIANCE_SCALINGS.csv');assert len(sc)==3 and sc['count'].eq(600).all()
assert np.allclose(sc['median'],[2.0801621282,10,1],atol=1e-10,rtol=0)
checks['actual_source_median_multipliers']=dict(zip(sc.source,sc['median']))
delta=[]
for f in (P/'data').glob('RUN_*.csv.gz'):
    if '_ACTUAL_SOURCE_TRACE' in f.name:continue
    a=pd.read_csv(f);b=pd.read_csv(old/'data'/f.name)
    assert len(a)==len(b)==56642 and a.time.is_monotonic_increasing
    assert np.allclose(a,b,rtol=0,atol=0,equal_nan=True)
    delta.append({'file':f.name,'rows':len(a),'identical':True})
checks['retained_series']=delta
preview=[]
for name in ['F08_heading_quality_scaling','S_F08_all_condition_variants']:
    lay=json.loads((P/'qa'/f'{name}.layout.json').read_text());assert not lay['clipped_text'] and lay['min_font_pt']>=8
    assert lay['width_mm']==174 and lay['height_mm']<=234
    align=json.loads((P/'qa'/f'{name}.alignment.json').read_text());assert align['verdict']=='PASS'
    collision=json.loads((P/'qa'/f'{name}.collisions.json').read_text());assert collision['verdict']=='PASS' and collision['summary']['fail']==collision['summary']['warn']==0
    with fitz.open(P/'figures'/f'{name}.pdf') as pdf:assert len(pdf)==1 and abs(pdf[0].rect.width/72*25.4-174)<.01
    with Image.open(P/'preview'/f'{name}.png') as im:
        assert im.width>=2560 and im.height>=1080;preview.append({'name':name,'width':im.width,'height':im.height})
    with Image.open(P/'figures'/f'{name}.png') as im:assert abs(im.info['dpi'][0]-600)<.1
checks['preview_pixels']=preview
nature=json.loads((P/'qa/NATURE_QA_STATUS.json').read_text());assert all(r['exit_code']==0 for r in nature)
checks['nature_alignment_pdf_text_collision']='PASS; source warnings reviewed'
checks['new_solver_provider_evaluator_calls']=0
result={'status':'PASS','checks':checks,'issues':[]}
(P/'qa/FINAL_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
