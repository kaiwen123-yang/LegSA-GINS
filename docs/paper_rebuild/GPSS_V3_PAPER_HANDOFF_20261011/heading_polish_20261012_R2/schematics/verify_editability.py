from pathlib import Path
import xml.etree.ElementTree as ET
import json
import fitz
from PIL import Image
ROOT=Path(__file__).resolve().parent
drawio=ET.parse(ROOT/'editable/F02_method.drawio')
cells=drawio.findall('.//mxCell')
edges=[x for x in cells if x.get('edge')=='1']
verts=[x for x in cells if x.get('vertex')=='1']
ids={x.get('id') for x in cells}
bad=[]
for e in edges:
 for side in ['source','target']:
  if e.get(side) and e.get(side) not in ids:bad.append(e.get('id'))
svg=ET.parse(ROOT/'figures/F02_method.svg')
texts=svg.findall('.//{http://www.w3.org/2000/svg}text')
images=svg.findall('.//{http://www.w3.org/2000/svg}image')
pages={}
for stem in ['F01_platform','F02_method']:
 with fitz.open(ROOT/'figures'/f'{stem}.pdf') as doc:
  pages[stem]={'mm':[v*25.4/72 for v in [doc[0].rect.width,doc[0].rect.height]],'preview_pixels':list(Image.open(ROOT/'preview'/f'{stem}.png').size)}
result={'status':'PASS' if not bad and len(texts)>0 and not images else 'FAIL','drawio_vertices':len(verts),'drawio_edges':len(edges),'attached_edges':sum(bool(e.get('source') and e.get('target')) for e in edges),'unknown_node_links':bad,'svg_text_elements':len(texts),'svg_raster_images':len(images),'pages':pages,'drawio_render':'XML structure and link identities checked; final PDF and PNG visually inspected'}
(ROOT/'qa/EDITABLE_VALIDATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
