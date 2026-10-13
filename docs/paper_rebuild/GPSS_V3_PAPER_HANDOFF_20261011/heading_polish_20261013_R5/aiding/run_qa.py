from pathlib import Path
import subprocess,json
P=Path(__file__).resolve().parent
S=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
name='F08_heading_quality_scaling';report=[]
r=subprocess.run(['python3',str(S/'validate_figure.py'),str(P/'build_fig8_r5.py'),'--backend','python','--json'],capture_output=True,text=True)
(P/'qa/source_preflight.json').write_text(r.stdout,encoding='utf8');report.append({'stage':'source','exit_code':r.returncode})
r=subprocess.run(['python3',str(S/'audit_pdf_text.py'),str(P/'figures'/f'{name}.pdf'),'--min-pt','8','--json'],capture_output=True,text=True)
(P/'qa'/f'{name}.pdf_text.json').write_text(r.stdout,encoding='utf8');report.append({'stage':'pdf_font','exit_code':r.returncode})
r=subprocess.run(['python3',str(S/'audit_figure_collisions.py'),str(P/'figures'/f'{name}.pdf'),'--json-out',str(P/'qa'/f'{name}.collisions.json'),'--overlay-pdf',str(P/'qa'/f'{name}.collision_overlay.pdf')],capture_output=True,text=True)
(P/'qa'/f'{name}.collision.log').write_text(r.stdout+r.stderr,encoding='utf8');report.append({'stage':'collision','exit_code':r.returncode})
(P/'qa/NATURE_QA_STATUS.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report,indent=2))
