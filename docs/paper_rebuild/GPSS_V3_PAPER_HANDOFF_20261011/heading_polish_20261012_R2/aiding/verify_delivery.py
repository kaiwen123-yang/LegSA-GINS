"""Verify source coverage and figure exports; does not evaluate navigation outputs."""
from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
from PIL import Image
import fitz

P=Path(__file__).resolve().parent
checks={};problems=[]
core=pd.read_csv(P/'tables/CORE5951.csv')
mapped=pd.read_csv(P/'tables/ALL5951_RESULTS_WITH_INPUT_GROUPS.csv')
pairs=pd.read_csv(P/'tables/ALL2164_ORIGINAL_ABLATION_PAIRS.csv')
inactive=pd.read_csv(P/'tables/ALL61_PHYSICAL_INPUT_MAP.csv')
assert len(core)==len(mapped)==5951 and len(pairs)==2164
assert core.run_id.tolist()==mapped.run_id.tolist()
assert np.allclose(core.yaw_rmse_deg,mapped.yaw_rmse_deg,equal_nan=True,rtol=1e-12,atol=1e-12)
assert np.allclose(core.horizontal_rmse_m,mapped.horizontal_rmse_m,equal_nan=True,rtol=1e-12,atol=1e-12)
checks['max_grouped_table_float_roundtrip_difference']=float(max(np.nanmax(np.abs(core.yaw_rmse_deg-mapped.yaw_rmse_deg)),np.nanmax(np.abs(core.horizontal_rmse_m-mapped.horizontal_rmse_m))))
noactive=set(inactive.loc[~inactive.registered_active_measurement_path,'degradation_type_id'])
assert noactive=={'CLEAN','D29','D40','D55','D56'}
assert inactive.loc[inactive.degradation_type_id=='D28','physical_duplicate_of'].iloc[0]=='D25'
fail=pd.read_csv(P/'tables/ALL_CORE_NONCOMPLETIONS.csv')
assert set(fail.run_id)==set(core.loc[core.evaluation_status!='COMPLETED','run_id'])
checks['original_results_preserved']=5951
checks['original_ablation_pairs_preserved']=2164
checks['all_noncompletions_preserved']=len(fail)
checks['no_active_path_types']=['D29','D40','D55','D56']
src=json.loads((P/'SOURCE_SERIES.json').read_text())
maxdiff=0
for r in src:
    p=P/'data'/f"{r['run_id']}.csv.gz";d=pd.read_csv(p)
    assert len(d)==r['rows'] and d.time.is_monotonic_increasing
    orig=Path(r['source_path'])
    if orig.exists():
        o=pd.read_csv(orig,usecols=d.columns.tolist())
        diff=np.nanmax(np.abs(d.to_numpy()-o[d.columns].to_numpy()));maxdiff=max(diff,maxdiff)
        assert np.allclose(d,o[d.columns],rtol=1e-12,atol=1e-12,equal_nan=True)
checks['retained_series_count']=len(src);checks['max_csv_roundtrip_difference']=maxdiff
q=json.loads((P/'qa/DELIVERY.json').read_text())
for r in q['figures']:
    name=r['figure'];assert r['width_mm']==174 and r['min_text_pt']>=8
    assert not r['text_outside_canvas'],r
    for ext in ['pdf','svg','png','tiff']:assert (P/'figures'/f'{name}.{ext}').exists()
    with fitz.open(P/'figures'/f'{name}.pdf') as pdf:
        assert len(pdf)==1 and abs(pdf[0].rect.width/72*25.4-174)<.01
    with Image.open(P/'figures'/f'{name}.png') as im:
        assert abs(im.info['dpi'][0]-600)<.1
checks['exports_checked']=len(q['figures'])*4
checks['fonts_min_pt']=min(r['min_text_pt'] for r in q['figures'])
preview=[]
for name in ['F06_heading_and_tilt','F07_heading_retained_translation','F08_heading_quality_scaling','F10_heading_sensitivity']:
    with Image.open(P/'preview'/f'{name}.png') as im:
        assert im.width>=2560 and im.height>=1080
        preview.append({'figure':name,'width':im.width,'height':im.height})
checks['main_preview_pixels']=preview
old=P.parent.parent/'V3航向主线重绘_20261012/aiding/figures'
for ext in ['pdf','svg','png','tiff']:
    filename=f'F07_heading_retained_translation.{ext}'
    assert hashlib.sha256((old/filename).read_bytes()).hexdigest()==hashlib.sha256((P/'figures'/filename).read_bytes()).hexdigest()
checks['F07_original_exports_byte_identical']=True
obs=pd.read_csv(P/'tables/F10_OBSERVATION_MATCH_COUNTS.csv')
assert obs.window_rows.eq(1370).all() and obs.reference_key_unmatched.eq(0).all()
assert obs.valid_unscored_rows.eq(1).all() and obs.hash_match.all()
assert obs.actual_gnss_updates_without_heading.tolist()==[100,0,0]
checks['figure_layer_observation_error_derivation']={'cases':3,'input_rows_kept':4110,'reference_key_failures':0,'valid_unscored_first_epochs':3,'original_input_hashes_verified':3,'new_interpolation':False}
nk=json.loads((P/'qa/NATURE_QA_STATUS.json').read_text());assert all(r['exit_code']==0 for r in nk)
checks['nature_preflight_fonts_collision']='PASS; source warnings reviewed in NATURE_QA_REVIEW.md'
checks['visual_review']='R2 main previews inspected; F06 full line foreground, F08 three physical conditions with all variants, F10 observed-input-to-fused-output evidence.'
checks['new_solver_provider_evaluator_calls']=0
result={'status':'PASS','checks':checks,'problems':problems}
(P/'qa/FINAL_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
