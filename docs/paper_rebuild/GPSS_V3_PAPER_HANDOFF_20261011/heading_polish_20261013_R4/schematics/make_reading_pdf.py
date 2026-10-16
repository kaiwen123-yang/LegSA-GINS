from pathlib import Path
import fitz,json
ROOT=Path(__file__).resolve().parent
src=fitz.open(ROOT/'figures/F02_method.pdf')
doc=fitz.open()
px_to_pt=src[0].rect.width/1815
def add(title,clip_px,width_mm):
    clip=fitz.Rect(*(v*px_to_pt for v in clip_px))
    content_w=width_mm/25.4*72
    content_h=content_w*clip.height/clip.width
    margin=18;top=33
    page=doc.new_page(width=content_w+2*margin,height=content_h+top+margin)
    page.insert_text((margin,20),title,fontsize=11,fontname='helv')
    page.show_pdf_page(fitz.Rect(margin,top,margin+content_w,top+content_h),src,0,clip=clip)
    return {'title':title,'viewbox_px':clip_px,'content_width_mm':width_mm,'page_mm':[page.rect.width/72*25.4,page.rect.height/72*25.4]}
pages=[add('Figure 2 | Full diagram',[0,0,1815,866],260),add('Figure 2 | Measurement inputs and frame rotation',[28,65,826,795],220),add('Figure 2 | Shared estimator and navigation output',[826,42,1809,806],260)]
doc.save(ROOT/'figures/F02_method_reading.pdf',deflate=True)
(ROOT/'qa/F02_READING_PDF.json').write_text(json.dumps({'source_vector_unchanged':True,'no_image_rasterization':True,'pages':pages},indent=2),encoding='utf-8')
pix=doc[1].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
pix.save(ROOT/'qa/F02_reading_inputs.png')
print({'pages':len(doc),'vector_reading_pdf':str(ROOT/'figures/F02_method_reading.pdf')})
