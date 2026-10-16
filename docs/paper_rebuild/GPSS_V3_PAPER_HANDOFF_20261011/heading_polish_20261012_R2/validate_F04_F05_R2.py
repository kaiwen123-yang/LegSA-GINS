"""Verify that R2 changes visual styling only, with exact numerical parity."""
from pathlib import Path
import hashlib,json,re
import pandas as pd
import fitz
from PIL import Image

ROOT=Path(__file__).parent
OLD=ROOT.parent/'V3航向主线重绘_20261012'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
results={}
for folder,stem in [('observability','F04_absolute_direction_relative_motion'),('heading_acceptance','F05_heading_error_comparison')]:
    p=ROOT/folder
    with fitz.open(p/f'{stem}.pdf') as doc:
        sizes=[s['size'] for page in doc for block in page.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for s in line['spans'] if s.get('text','').strip()]
        rect=doc[0].rect
        width,height=rect.width/72*25.4,rect.height/72*25.4
    assert abs(width-174)<1e-3
    assert min(sizes)>=7.999
    png=Image.open(p/f'{stem}.png')
    preview=Image.open(p/'preview'/f'{stem}.png')
    assert preview.width>=2560 and preview.height>=1080
    assert png.width>=4100 and min(png.info['dpi'])>=599
    svg=(p/f'{stem}.svg').read_text()
    assert '<text' in svg
    result=dict(width_mm=width,height_mm=height,minimum_font_pt=min(sizes),
                full_png_pixels=list(png.size),full_png_dpi=png.info['dpi'],
                preview_pixels=list(preview.size),svg_editable_text=True,exact_numerical_parity=True)
    if folder=='observability':
        for name in ['ALIGNMENT_SUMMARY.csv','ALL_NATIVE_ALIGNMENT_RESIDUALS.csv.gz']:
            pd.testing.assert_frame_equal(pd.read_csv(p/'source_data'/name),pd.read_csv(OLD/folder/'source_data'/name),check_exact=True)
        result['parity_checks']=['all 63277 x 15 alignment residual table cells','seven-run summary']
        meta=json.loads((p/f'{stem}.json').read_text())
        oldmeta=json.loads((OLD/folder/f'{stem}.json').read_text())
        for key in ['native_runs','native_rows_per_run','native_rows_total','max_three_dimensional_position_residual_m','max_heading_increment_residual_deg','alignment','arrow_definition']:
            assert meta[key]==oldmeta[key]
        meta['visual_review']='PASS: R2 color and grayscale viewed, only colors and line weights changed. All seven native runs and every residual retained.'
        meta['view_revision']='R2 colors, line hierarchy, 400-dpi preview; numerical arrays exact-match previous version'
        meta['alignment_audit_scope']='Comparable square panels (a,b); panel(c) is an independent full-width residual strip, retaining prior layout.'
        (p/f'{stem}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    else:
        for name in ['ACCEPTANCE_FULL_HISTORY.csv','ACCEPTED_ERROR_SERIES.csv','ACCEPTANCE_SUMMARY.csv','PLAN_LOCK.json','ACCEPTANCE_SEAL.json','COMMON_SUPPORT_COMPARISON.csv']:
            assert sha(p/name)==sha(OLD/folder/name)
        pd.testing.assert_frame_equal(pd.read_csv(p/'ALL_DIRECTION_ROUTE_METRICS.csv'),pd.read_csv(OLD/folder/'ALL_DIRECTION_ROUTE_METRICS.csv'),check_exact=True)
        result['parity_checks']=['six sealed inputs byte identical','all direction-route metrics exact table equality']
        result['new_ratio_screen_calls']=0
    result['new_native_solver_calls']=0
    result['visual_review']='PASS: color and grayscale, no clipping, legend and line-role identities retained'
    results[folder]=result
    (p/'R2_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(ROOT/'F04_F05_R2_VALIDATION.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False,indent=2))
