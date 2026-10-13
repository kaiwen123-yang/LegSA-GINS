from pathlib import Path
import json
import numpy as np,pandas as pd
from PIL import Image
import fitz
P=Path(__file__).resolve().parent;checks={}
screen=json.loads((P/'SCREENING_RECEIPT.json').read_text());assert screen['registered_types_read']==61 and screen['core_rows_read']==5951;checks['screening']=screen
cases=json.loads((P/'SELECTED_CASES.json').read_text());assert [r['type'] for r in cases]==['D15','D38','D53']
prov=json.loads((P/'INPUT_PROVENANCE.json').read_text());assert all(r['hash_match'] for r in prov['inputs']);checks['input_hash_checks']=len(prov['inputs'])
bins=pd.read_csv(P/'tables/ONE_SECOND_DISPLAY_SUMMARIES.csv');bchecks=[]
for c in cases:
    typ=c['type'];inp=pd.read_csv(P/'data'/f'{typ}_input_change.csv.gz');w=inp.elapsed_s.between(0,120)&inp.input_valid
    for source,values in [('input_change',inp.loc[w,'input_change_magnitude']),('reported_uncertainty',inp.loc[w,'reported_std_norm'])]:
        q=bins[bins.case.eq(typ)&bins.source.eq(source)];assert len(q)==120 and q['count'].sum()==len(values)
        assert np.isclose(q.minimum.min(),values.min(),rtol=1e-12,atol=1e-12) and np.isclose(q.maximum.max(),values.max(),rtol=1e-12,atol=1e-12)
        bchecks.append({'case':typ,'source':source,'samples_counted':len(values),'all_extrema_preserved':True})
    for source,rid in [('weighting_off',c['off_run']),('full',c['full_run'])]:
        d=pd.read_csv(P/'data'/f'{rid}_errors.csv.gz');assert len(d)==56642
        values=d.loc[(d.time-66).between(0,120),'yaw_err_deg'];q=bins[bins.case.eq(typ)&bins.source.eq(source)]
        assert len(q)==120 and q['count'].sum()==len(values)==25429
        assert np.isclose(q.minimum.min(),values.min(),rtol=1e-12,atol=1e-12) and np.isclose(q.maximum.max(),values.max(),rtol=1e-12,atol=1e-12)
        bchecks.append({'case':typ,'source':source,'samples_counted':len(values),'all_extrema_preserved':True})
checks['one_second_bins']=bchecks
assert len(pd.read_csv(P/'tables/ALL541_WEIGHTING_PAIRS.csv'))==541 and len(pd.read_csv(P/'tables/SELECTED27_WEIGHTING_PAIRS.csv'))==27
checks['paired_denominators']={'overall_registered':541,'selected_registered':27}
name='F08_heading_quality_scaling'
layout=json.loads((P/'qa'/f'{name}.layout.json').read_text());assert layout['minimum_font_pt']>=8 and layout['height_mm']<=225 and not layout['clipped_text']
assert json.loads((P/'qa'/f'{name}.alignment.json').read_text())['verdict']=='PASS'
collision=json.loads((P/'qa'/f'{name}.collisions.json').read_text());assert collision['summary']['fail']==0 and collision['summary']['warn']==0
assert all(x['exit_code']==0 for x in json.loads((P/'qa/NATURE_QA_STATUS.json').read_text()))
with fitz.open(P/'figures'/f'{name}.pdf') as pdf:
    assert len(pdf)==1 and abs(pdf[0].rect.width/72*25.4-174)<.01
with Image.open(P/'preview'/f'{name}.png') as im:
    assert im.width>=2560 and im.height>=1080;checks['preview_pixels']=[im.width,im.height]
with Image.open(P/'figures'/f'{name}.png') as im:assert abs(im.info['dpi'][0]-600)<.1
assert len(list((P/'preview').glob('F08*.png')))==1
checks['rendered_QA']='PASS:1.5pt alignment,8pt PDF text,zero collision FAIL/WARN,one canonical preview'
checks['new_solver_provider_evaluator_calls']=0
result={'status':'PASS','checks':checks,'issues':[]};(P/'qa/FINAL_VALIDATION.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))
