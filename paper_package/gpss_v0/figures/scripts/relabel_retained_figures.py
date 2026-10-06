"""Relabel retained publication SVGs; no metric or estimator execution."""
from common import *
import xml.etree.ElementTree as ET,re
try:import cairosvg
except ImportError:
 sys.path.insert(0,str(P/'figures/_build/cairo'));import cairosvg
from PIL import Image
ROOT=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX05_CLOSEOUT/90_MANUSCRIPT')
SOURCES={'Fig07':ROOT/'FIG02S.svg','Fig08':ROOT/'FIG02D.svg','SFig01':ROOT/'SFIG-HX.svg','SFig02':V/'08_FIGURES/SFIG01/SFIG01.svg'}
NAMES={'EXT01':'GNSS compass','EXT02':'Wrapped LS','EXT03':'Baseline KF','EXT04 FAR':'Wu full AR','EXT04 PAR':'Wu partial AR','EXT05C':'1-RX update IEKF','LC01':'Two-RX IEKF','F01':'GNSS/INS','F02':'Basic heading','F03':'Gated heading','A04':'No weighting','F04':'LegSA-GINS','F02 reference':'Basic heading','F04 reference':'LegSA-GINS','LEG-DR':'SDK dead reckoning','Official LIT':'Author, literature','Official DEF':'Author, default','Port S':'Port, calibrated IMU','Port LIT':'Port, literature'}
def protected_geometry(root):
 def walk(e,in_legend=False):
  in_legend=in_legend or e.get('id')=='legend_1'
  if e.get('id')!='publication_background' and not in_legend and e.tag.rsplit('}',1)[-1] in ['path','use','image','line','circle','rect','polygon','polyline','ellipse']:
   yield (e.tag,tuple(sorted(e.attrib.items())))
  for c in e:yield from walk(c,in_legend)
 return list(walk(root))
def render():
 results=[]
 for name,source in SOURCES.items():
  original=record(source).read_bytes();root=ET.fromstring(original);protected=protected_geometry(root);labels=[]
  for e in root.iter():
   if e.tag.endswith('}text') and e.text in NAMES:
    old=e.text;e.text=NAMES[old];labels.append({'before':old,'after':e.text})
    if name=='SFig02':e.set('transform','translate(0 20) '+e.get('transform',''))
  legend=next((e for e in root.iter() if e.get('id')=='legend_1'),None)
  if legend is not None and name in ['Fig08','SFig01']:
   pairs=list(zip(list(legend)[::2],list(legend)[1::2]));slots=([-15,90,205,295] if name=='Fig08' else [-15,-15,145,145,300])
   assert len(pairs)==len(slots)
   for (mark,text),target in zip(pairs,slots):
    element=next(e for e in text.iter() if e.tag.endswith('}text'));delta=target-float(element.get('x'))
    mark.set('transform',f'translate({delta} 0)');text.set('transform',f'translate({delta} 0)')
  x,y,width,height=map(float,root.get('viewBox').split());left=55 if name!='SFig02' else 0;top=15 if name!='SFig02' else 0;bottom=25 if name=='SFig02' else 0
  root.set('viewBox',f'{x-left} {y-top} {width+left} {height+top+bottom}');root.set('width',f'{width+left}pt');root.set('height',f'{height+top+bottom}pt')
  background=ET.Element('{http://www.w3.org/2000/svg}rect',{'id':'publication_background','x':str(x-left),'y':str(y-top),'width':str(width+left),'height':str(height+top+bottom),'fill':'white'})
  root.insert(0,background)
  assert protected_geometry(root)==protected,'Plotted geometry or embedded image changed'
  ET.register_namespace('','http://www.w3.org/2000/svg');ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
  payload=ET.tostring(root,encoding='utf-8',xml_declaration=True)
  payload=('\n'.join(line.rstrip() for line in payload.decode('utf-8').splitlines())+'\n').encode('utf-8');svg=P/'figures'/f'{name}.svg';svg.write_bytes(payload)
  cairosvg.svg2png(bytestring=payload,write_to=str(svg.with_suffix('.png')),output_width=4098,background_color='white');cairosvg.svg2pdf(bytestring=payload,write_to=str(svg.with_suffix('.pdf')),background_color='white')
  im=Image.open(svg.with_suffix('.png'));dims=im.size;im.thumbnail((1400,1600));im.save(P/'figures/_build'/f'{name}_reader_preview.png')
  results.append({'figure':name,'source':str(source),'original_svg_sha256':hashlib.sha256(original).hexdigest(),'new_svg_sha256':hashlib.sha256(payload).hexdigest(),'labels':labels,'plotted_geometry_and_embedded_images_unchanged':True,'layout_changes':'Expanded white publication canvas; legend placement; SFig02 tick text displaced below data. Numeric text and data marks unchanged.','renderer':'CairoSVG '+cairosvg.__version__,'png_dimensions':dims})
  print(name,len(labels),'reader labels; protected plot geometry unchanged')
 dest=W/'docs/paper_rebuild/PAPER_IDENTITY_20261004/COPIED_FIGURE_READER_LABELS.json';dest.write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':render()
