from pathlib import Path
import shutil,os,json,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
PREV=ROOT.parent.parent/'V3正文精修_20261012_R3/schematics'
for d in ['figures','preview','editable','qa']: (ROOT/d).mkdir(exist_ok=True,parents=True)
for src,dst in [('editable/F02_method_traced.svg','editable/F02_method_traced.svg'),('figures/F02_method.pdf','figures/F02_method.pdf'),('figures/F02_method.svg','figures/F02_method.svg'),('figures/F02_method.tiff','figures/F02_method.tiff')]:
    shutil.copyfile(PREV/src,ROOT/dst)
fontconf=ROOT/'qa/fontconfig.xml'
fontconf.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>/mnt/c/Windows/Fonts</dir><cachedir>/tmp/legsa-font-cache</cachedir></fontconfig>')
os.environ['FONTCONFIG_FILE']=str(fontconf)
import cairosvg
from PIL import Image
svg=(ROOT/'editable/F02_method_traced.svg').read_bytes()
spec=[('preview/F02_method.png',3840),('figures/F02_method_4K.png',3840),('figures/F02_method_8K.png',7680)]
sizes={}
for name,width in spec:
    cairosvg.svg2png(bytestring=svg,write_to=str(ROOT/name),output_width=width)
    with Image.open(ROOT/name) as im:sizes[name]=list(im.size)
shutil.copyfile(ROOT/'figures/F02_method_8K.png',ROOT/'figures/F02_method.png')
doc=ET.fromstring(svg)
ns='{http://www.w3.org/2000/svg}'
qa={'reference':'R3 approved SVG','svg_byte_identical':svg==(PREV/'editable/F02_method_traced.svg').read_bytes(),'pdf_byte_identical':(ROOT/'figures/F02_method.pdf').read_bytes()==(PREV/'figures/F02_method.pdf').read_bytes(),'layout_changes':False,'new_image_generation':False,'raster_images_in_svg':len(doc.findall('.//'+ns+'image')),'text_elements_in_svg':len(doc.findall('.//'+ns+'text')),'exports':sizes,'master_sha256':hashlib.sha256(svg).hexdigest()}
(ROOT/'qa/F02_RESOLUTION.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
print(json.dumps(qa,indent=2))
