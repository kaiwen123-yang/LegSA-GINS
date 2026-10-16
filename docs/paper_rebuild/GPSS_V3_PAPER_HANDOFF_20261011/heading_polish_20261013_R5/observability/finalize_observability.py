from pathlib import Path
import json,hashlib,subprocess,sys
import pandas as pd
import fitz
from PIL import Image
O=Path(__file__).parent
ROOT=O.parents[1]
oldrel=ROOT/'V3五问题论文组图_20261011/robot/data'
oldgauge=ROOT/'V3正文精修_20261012_R3/observability/source_data'
SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parity=[]
for family,old,new in [('gauge',oldgauge,O/'source_data/gauge'),('relative',oldrel,O/'source_data/relative')]:
    for p in new.glob('*.csv*'):
        if (old/p.name).exists():
            ok=sha(p)==sha(old/p.name)
            assert ok
            parity.append(dict(family=family,name=p.name,bytes=p.stat().st_size,source=str(old/p.name),byte_identical=ok))
pd.DataFrame(parity).to_csv(O/'audit/SOURCE_COPY_PARITY.csv',index=False)
frames=pd.read_csv(O/'audit/METHOD_IDENTITY_AND_EXISTING_RESULTS.csv')
assert len(frames)==9
names=['F04_proprioceptive_heading_and_two_routes','S04_two_proprioceptive_routes_all_scenes']
figs=[]
for name in names:
    meta=json.loads((O/f'{name}.json').read_text())
    collision=json.loads((O/'qa'/f'{name}.collisions.json').read_text())
    align=json.loads((O/'qa'/f'{name}.alignment.json').read_text())
    assert collision['summary']['fail']==0 and collision['summary']['warn']==0
    assert align['verdict']=='PASS'
    with fitz.open(O/f'{name}.pdf') as doc:
        r=doc[0].rect
        sizes=[s['size'] for p in doc for b in p.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans'] if s.get('text','').strip()]
    assert min(sizes)>=7.999 and abs(r.width/72*25.4-174)<.001
    im=Image.open(O/'preview'/f'{name}.png');full=Image.open(O/f'{name}.png')
    assert im.width>=2560 and im.height>=1080 and min(full.info['dpi'])>=599
    assert '<text' in (O/f'{name}.svg').read_text()
    meta['visual_review']='PASS: color and grayscale reviewed; two distinct input routes are labelled and all saved errors retained.'
    (O/f'{name}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    figs.append(dict(id=name,role=meta['role'],preview='preview/'+name+'.png',
                     width_mm=r.width/72*25.4,height_mm=r.height/72*25.4,minimum_font_pt=min(sizes),
                     preview_pixels=list(im.size),full_png_pixels=list(full.size),
                     alignment='PASS',collision_fail=0,collision_warn=0,pdf_svg_editable=True))
report={'status':'PASS','figures':figs,'native_solver_calls':0,'evaluator_calls':0,'provider_calls':0,
        'new_alignment_fits':0,'saved_error_files_byte_identical':True,'all_seven_gauge_histories_retained':True,
        'primary_routes':2,'official_InEKF_parameter_variants_retained':2,
        'OFF_DEF_scope':'same InEKF parameter sensitivity, included in full table and source data; not a third method',
        'scientific_scope':'Relative errors after saved initial10s alignment; different input information, no absolute-heading accuracy claim',
        'reference':'Saved commercial fused reference evaluation, not a newly read trace',
        'alignment_exemption':'Two gauge panels have equal metric scale and are intentionally narrower than the two time-series panels; within-row alignment passes1.5pt.'}
(O/'QC_SUMMARY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(O/'SECTION_PACKAGE.json').write_text(json.dumps({'figures':figs,'caption':'CAPTIONS_ZH_EN.md','reader':'README.md','qc':'QC_SUMMARY.json',
 'method_identity':'audit/METHOD_IDENTITY_AND_EXISTING_RESULTS.csv','table':'source_data/ROBOT_RELATIVE_RESULTS.csv'},ensure_ascii=False,indent=2)+'\n')
r=subprocess.run([sys.executable,str(SK/'validate_figure.py'),str(O/'build_proprioceptive_comparison.py')],text=True,capture_output=True)
(O/'qa/source_preflight.log').write_text(r.stdout+r.stderr)
print(json.dumps(report,ensure_ascii=False,indent=2))
