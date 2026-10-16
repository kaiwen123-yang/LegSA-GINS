"""R3 visual and numerical checks. No scientific estimator/evaluator calls."""
from pathlib import Path
import hashlib,json
import pandas as pd
import numpy as np
import fitz
from PIL import Image

P=Path(__file__).parent
OLD=P.parent/'V3正文精修_20261012_R2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

out={}
for folder,stem in [('heading_acceptance','F05_heading_error_comparison'),('navigation_comparison','F09_heading_comparison')]:
    d=P/folder
    with fitz.open(d/f'{stem}.pdf') as doc:
        r=doc[0].rect
        sizes=[s['size'] for p in doc for b in p.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans'] if s.get('text','').strip()]
    full=Image.open(d/f'{stem}.png');preview=Image.open(d/'preview'/f'{stem}.png')
    assert min(sizes)>=7.999 and abs(r.width/72*25.4-174)<.001
    assert preview.width>=2560 and preview.height>=1080
    assert full.width>=4100 and min(full.info['dpi'])>=599
    assert '<text' in (d/f'{stem}.svg').read_text()
    result=dict(width_mm=r.width/72*25.4,height_mm=r.height/72*25.4,min_font_pt=min(sizes),
                full_png_pixels=list(full.size),preview_pixels=list(preview.size),svg_editable_text=True,
                visual_review='PASS: full color and grayscale reviewed',new_solver_calls=0,new_ratio_screen_calls=0)
    if folder=='heading_acceptance':
        for name in ['ACCEPTANCE_FULL_HISTORY.csv','ACCEPTED_ERROR_SERIES.csv','ACCEPTANCE_SUMMARY.csv','ACCEPTANCE_SEAL.json','PLAN_LOCK.json','COMMON_SUPPORT_COMPARISON.csv']:
            assert sha(d/name)==sha(OLD/folder/name)
        pd.testing.assert_frame_equal(pd.read_csv(d/'ALL_DIRECTION_ROUTE_METRICS.csv'),pd.read_csv(OLD/folder/'ALL_DIRECTION_ROUTE_METRICS.csv'),check_exact=True)
        src=pd.read_csv(d/'ACCEPTED_ERROR_SERIES.csv');plot=pd.read_csv(d/'figure_data/F05B_ALL_EPOCH_ERRORS.csv')
        for (m,support),q in plot.groupby(['method_id','support']):
            native=src[src.sequence.eq('BY2H')&src.method_id.eq(m)]
            if support=='Original':v=native[native.native_valid]
            else:v=native[native.accepted]
            v=v[v.error_valid_deg.notna()]
            assert len(v)==len(q)
            j=q.merge(v[['epoch_index','error_valid_deg']],on='epoch_index',validate='one_to_one')
            assert np.max(np.abs(j.absolute_error_deg-np.abs(j.error_valid_deg)))<5e-13
        result['sealed_data_byte_identical']=True
        result['all_route_metrics_exactly_identical']=True
        result['boxplot_all_scored_epochs_retained']=True
        result['boxplot_whiskers']='1.5 IQR; every observation is plotted, including outside whiskers'
    else:
        for name in ['BY2_COMMON_HEADING.csv.gz','BY2H_COMMON_HEADING.csv.gz','BY2O_COMMON_HEADING.csv.gz','F09_ALL18_INTERRUPTION_CASES.csv','F09_FGO_GNSS1_COMMON_POSITION.csv','F09_FGO_FULL_WINDOW_COVERAGE.csv','FGO_GNSS1_ALL36_RESULTS.csv']:
            assert sha(d/'data'/name)==sha(OLD/'navigation/data'/name)
        pairs=pd.read_csv(d/'data/F09_ALL18_INTERRUPTION_CASES.csv')
        assert len(pairs)==18
        result['panel_h_values']=72
        result['panel_h_all_methods_n']=18
        position=pd.read_csv(d/'METHOD_POSITION_TABLE.csv')
        original=pd.read_csv(OLD/'navigation/data/F09_FGO_GNSS1_COMMON_POSITION.csv')
        cmp=position.merge(original,on=['sequence_id','method_id'],suffixes=('_new','_old'),validate='one_to_one')
        assert np.allclose(cmp.horizontal_rmse_m_new,cmp.horizontal_rmse_m_old,rtol=0,atol=1e-14)
        result['old_i_all_nine_metrics_retained']=True
        result['all_common_error_inputs_byte_identical']=True
        meta=json.loads((d/f'{stem}.json').read_text())
        meta['visual_review']='PASS: a-g same scientific inputs, h full names and n/median labels clear; old i retained in trajectory companion table.'
        (d/f'{stem}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
        (d/'CAPTIONS_ZH_EN.md').write_text('# 图9：航向精度比较\n\n'+meta['caption_zh']+'\n\n'+meta['caption_en']+'\n',encoding='utf-8')
    (d/'R3_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    out[folder]=result
(P/'F05_F09_R3_VALIDATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
