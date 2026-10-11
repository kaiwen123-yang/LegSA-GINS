"""Validate the saved figure and record reviewable publishing checks."""
from pathlib import Path
import subprocess,sys,json
import pandas as pd
import fitz
from PIL import Image

root=Path(__file__).resolve().parent
skill=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
name='M_attitude_heading_and_tilt'
commands={
    'source':[str(skill/'validate_figure.py'),str(root/'build_attitude_main.py'),'--json'],
    'pdf_text':[str(skill/'audit_pdf_text.py'),str(root/(name+'.pdf')),'--min-pt','5','--json'],
    'collisions':[str(skill/'audit_figure_collisions.py'),str(root/(name+'.pdf')),'--json-out',str(root/'qa/attitude.collisions.json')]}
codes={}
for label,args in commands.items():
    result=subprocess.run([sys.executable,*args],text=True,capture_output=True)
    codes[label]=result.returncode
    (root/'qa'/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,(label,result.stdout[-3000:])
profile=pd.read_csv(root/'SOURCE_PROFILE.csv')
bounds={'yaw_err_deg':(-20,40),'roll_err_deg':(-5,10),'pitch_err_deg':(-11.5,9)}
for field,limits in bounds.items():
    methods=['F01','F03','F04'] if field=='yaw_err_deg' else ['A05','F04']
    d=profile[(profile.field==field)&profile.method.isin(methods)]
    assert (d.missing==0).all()
    assert (d['min']>=limits[0]).all() and (d['max']<=limits[1]).all()
doc=fitz.open(root/(name+'.pdf'));page=doc[0]
size=[page.rect.width/72*25.4,page.rect.height/72*25.4]
assert abs(size[0]-174)<.01 and abs(size[1]-177)<.01
with Image.open(root/(name+'.png')) as im:
    pixels=im.size;dpi=im.info.get('dpi')
    assert min(dpi)>599
report={'status':'READY_FOR_FIGURE_DISCUSSION','checks':codes,'figure_size_mm':size,
    'png_pixels':pixels,'png_dpi':dpi,'plotted_series_missing_values':0,'main_axis_clipped_samples':0,
    'visual_review':'Color and grayscale inspected; nine panels and all three insets checked.',
    'static_warnings_reviewed':['174/25.4 is parsed incorrectly as 174 inches by the static width heuristic; actual PDF is 174 by 177 mm.','PDF/SVG and 600-dpi PNG supplied for this discussion draft; TIFF is not required for the present task.'],
    'data_changes':False,'new_scientific_runs':0}
(root/'QA_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
meta=json.loads((root/(name+'.json')).read_text())
meta['visual_review']='PASSED_FOR_DISCUSSION';meta['qa_report']='QA_REPORT.json'
(root/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
