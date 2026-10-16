from pathlib import Path
import subprocess,json,hashlib
import fitz
from PIL import Image
P=Path(__file__).resolve().parent;S=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts');name='F08_heading_quality_scaling';reports=[]
r=subprocess.run(['python3',str(S/'validate_figure.py'),str(P/'build_fig8_r6.py'),'--backend','python','--json'],capture_output=True,text=True)
(P/'qa/source_preflight.json').write_text(r.stdout,encoding='utf8');reports.append({'stage':'source','exit_code':r.returncode})
r=subprocess.run(['python3',str(S/'audit_pdf_text.py'),str(P/'figures'/f'{name}.pdf'),'--min-pt','8','--json'],capture_output=True,text=True)
(P/'qa'/f'{name}.pdf_text.json').write_text(r.stdout,encoding='utf8');reports.append({'stage':'font','exit_code':r.returncode})
r=subprocess.run(['python3',str(S/'audit_figure_collisions.py'),str(P/'figures'/f'{name}.pdf'),'--json-out',str(P/'qa'/f'{name}.collisions.json'),'--overlay-pdf',str(P/'qa'/f'{name}.collision_overlay.pdf')],capture_output=True,text=True)
(P/'qa'/f'{name}.collision.log').write_text(r.stdout+r.stderr,encoding='utf8');reports.append({'stage':'collision','exit_code':r.returncode})
(P/'qa/NATURE_QA_STATUS.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
print(json.dumps(reports,indent=2))
if not all(x['exit_code']==0 for x in reports):raise SystemExit(1)
layout=json.loads((P/'qa'/f'{name}.layout.json').read_text());assert not layout['clipped_text'] and layout['minimum_font_pt']>=8
alignment=json.loads((P/'qa'/f'{name}.alignment.json').read_text());assert alignment['verdict']=='PASS'
collision=json.loads((P/'qa'/f'{name}.collisions.json').read_text());assert collision['summary']['fail']==collision['summary']['warn']==0
pointer=json.loads((P/'SOURCE_POINTER.json').read_text())
for entry in pointer['files']:assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
with fitz.open(P/'figures'/f'{name}.pdf') as pdf:
    width=pdf[0].rect.width/72*25.4;height=pdf[0].rect.height/72*25.4
    assert len(pdf)==1 and abs(width-174)<.01 and abs(height-198)<.01
with Image.open(P/'preview'/f'{name}.png') as im:
    assert im.width>=2560 and im.height>=1080;pixels=[im.width,im.height]
with Image.open(P/'figures'/f'{name}.png') as im:assert abs(im.info['dpi'][0]-600)<.1
assert len(list((P/'preview').glob('F08*.png')))==1
out={'status':'PASS','data_reused_from':'R5 one-second summary CSV and original case-metric JSON','data_changed':False,'one_second_statistics_recomputed':False,'source_pointer_hash_checks':len(pointer['files']),'source_sample_counts_and_extrema':pointer['used_summaries'],'layout':layout,'preview_pixels':pixels,'rendered_QA':'1.5pt alignment,8pt PDF text,zero collision FAIL/WARN','new_solver_provider_evaluator_calls':0,'issues':[]}
(P/'qa/FINAL_VALIDATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print('FINAL_VALIDATION PASS')
