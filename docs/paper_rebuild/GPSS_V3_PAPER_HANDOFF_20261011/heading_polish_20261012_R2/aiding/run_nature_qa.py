from pathlib import Path
import subprocess,json
P=Path(__file__).resolve().parent
S=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
reports=[]
r=subprocess.run(['python3',str(S/'validate_figure.py'),str(P/'build_heading_first.py'),'--backend','python','--json'],capture_output=True,text=True)
(P/'qa/source_preflight.json').write_text(r.stdout,encoding='utf8')
reports.append({'stage':'source','exit_code':r.returncode})
for name in ['F06_heading_and_tilt','F08_heading_quality_scaling','F10_heading_sensitivity','S_quality_complete_statistics']:
    pdf=P/'figures'/f'{name}.pdf'
    r=subprocess.run(['python3',str(S/'audit_pdf_text.py'),str(pdf),'--min-pt','8','--json'],capture_output=True,text=True)
    (P/'qa'/f'{name}.pdf_text.json').write_text(r.stdout,encoding='utf8')
    reports.append({'figure':name,'stage':'font','exit_code':r.returncode})
    r=subprocess.run(['python3',str(S/'audit_figure_collisions.py'),str(pdf),'--json-out',str(P/'qa'/f'{name}.collisions.json'),'--overlay-pdf',str(P/'qa'/f'{name}.collisions.pdf')],capture_output=True,text=True)
    (P/'qa'/f'{name}.collisions.log').write_text(r.stdout+r.stderr,encoding='utf8')
    reports.append({'figure':name,'stage':'collision','exit_code':r.returncode})
(P/'qa/NATURE_QA_STATUS.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
print(json.dumps(reports,indent=2))
