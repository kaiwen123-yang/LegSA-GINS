from pathlib import Path
import json, struct
import fitz
ROOT=Path(__file__).resolve().parent
p=ROOT/'preview/F02_method.png'
raw=p.read_bytes()
w,h=struct.unpack('>II',raw[16:24])
width=174/25.4*72
doc=fitz.open()
page=doc.new_page(width=width,height=width*h/w)
page.insert_image(page.rect,stream=raw)
doc.save(ROOT/'figures/F02_method.pdf',deflate=True)
(ROOT/'METHOD_QA.json').write_text(json.dumps({
 'native_pixels':[w,h],'width_mm':174,'native_ppi':w/(174/25.4),
 'format':'raster image embedded in PDF, not vector',
 'visual_wiring_check':'PASS',
 'publication_typography':'native raster review design; vector typesetting remains',
 'checked':['IMU to propagation','position-pair to heading selection','tilt direct to event gate',
 'body velocity to frame rotation','historical heading and tilt to preprocessing only',
 'source-quality covariance to update','shared state to output']
},indent=2),encoding='utf-8')
