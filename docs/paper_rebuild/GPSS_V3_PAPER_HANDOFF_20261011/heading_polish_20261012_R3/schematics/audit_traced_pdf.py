"""Check the Cairo PDF with actual transformed span geometry.

The generic tool associates a multi-line Cairo texttrace union with a single
line, yielding false inter-line overlaps. Its Tf scanner sees the unit font
used with a scaled Tm, rather than the rendered point size. Preserve that raw
audit and check actual transformed line boxes independently here.
"""
from pathlib import Path
import json,sys
import fitz
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
import audit_figure_collisions as audit
path=ROOT/'figures/F02_method.pdf'
pages=audit.extract_pdf_geometry(path)
font_sizes=[]
with fitz.open(path) as doc:
    for page,geom in zip(doc,pages):
        texts=[]
        for b in page.get_text('dict')['blocks']:
            for line in b.get('lines',[]):
                spans=[s for s in line.get('spans',[]) if s['text'].strip()]
                if not spans:continue
                font_sizes.extend(s['size'] for s in spans)
                bbox=audit.union_rects(tuple(s['bbox']) for s in spans)
                texts.append(audit.TextBox(index=len(texts),text=''.join(s['text'] for s in spans),bbox=bbox))
        geom.texts=texts
    result=audit.audit_geometries(pages)
    result['font_check']={'min_transformed_span_pt':min(font_sizes),'required_pt':5,'pass':min(font_sizes)>=5}
    result['source_pdf_dimensions_mm']=[doc[0].rect.width*25.4/72,doc[0].rect.height*25.4/72]
result['reason_for_span_geometry']='Cairo puts multiple spatially separated text lines into one texttrace; line spans carry actual distinct boxes. Font Tm scaling makes static Tf=1 invalid as a rendered-size measure.'
(ROOT/'qa/F02_TRANSFORM_AWARE_QA.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(audit.render_text(result))
print(result['font_check'])
