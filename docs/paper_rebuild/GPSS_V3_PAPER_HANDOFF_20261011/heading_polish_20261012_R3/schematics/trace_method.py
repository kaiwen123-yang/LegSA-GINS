"""Trace the author-selected method figure at its original pixel coordinates.

Text and boxes remain vector objects; icons are black-ink vector contours traced
from the supplied reference. The reference raster is never embedded in the SVG.
"""
from pathlib import Path
import os,json,math,html,base64,hashlib
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from PIL import Image,ImageFont

ROOT=Path(__file__).resolve().parent
FONTDIR=Path('/mnt/c/Windows/Fonts')
fc=ROOT/'qa/fontconfig.xml'
fc.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>/mnt/c/Windows/Fonts</dir><cachedir>/tmp/legsa-font-cache</cachedir></fontconfig>')
os.environ['FONTCONFIG_FILE']=str(fc)
import cairosvg

W,H=1815,866
REF=ROOT/'references/method_author_reference.png'
src=np.asarray(Image.open(REF).convert('RGB'))
assert src.shape[:2]==(H,W)
parts=[];scene=[]
def add(s):parts.append(s)
def box(i,x,y,w,h,gradient,stroke,radius=10,dashed=False):
    scene.append(dict(id=i,kind='box',x=x,y=y,w=w,h=h,gradient=gradient,stroke=stroke,radius=radius,dashed=dashed))
    add(f'<rect id="{i}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="url(#{gradient})" stroke="{stroke}" stroke-width="2.3"'+(' stroke-dasharray="13 7"' if dashed else '')+'/>')
def txt(i,x,y,s,size=26,bold=False,anchor='start',maxwidth=None,italic=False,color='#060606'):
    fontfile='arialbd.ttf' if bold else ('ariali.ttf' if italic else 'arial.ttf')
    font=ImageFont.truetype(str(FONTDIR/fontfile),size*4)
    width=font.getlength(s)/4
    sx=min(1,maxwidth/width) if maxwidth else 1
    scene.append(dict(id=i,kind='text',x=x,y=y,text=s,size=size,bold=bold,italic=italic,anchor=anchor,width=width*sx,scale_x=sx,color=color))
    attrs=f'font-family="Arial" font-size="{size}" font-weight="{700 if bold else 400}" font-style="{"italic" if italic else "normal"}" fill="{color}" text-anchor="{anchor}"'
    if sx<.999:add(f'<g id="{i}" transform="translate({x},{y}) scale({sx:.6f},1)"><text x="0" y="0" {attrs}>{html.escape(s)}</text></g>')
    else:add(f'<text id="{i}" x="{x}" y="{y}" {attrs}>{html.escape(s)}</text>')
def mathtext(i,x,y,segments,size=32,color='#071431',anchor='start'):
    # Ordered normal/subscript runs keep formula text editable.
    spans=[];plain=''
    previous_sub=False
    for s,sub in segments:
        plain+=s
        # Explicit dy is supported by SVG editors and the Cairo PDF renderer.
        dy=size*.22 if sub and not previous_sub else (-size*.22 if previous_sub and not sub else 0)
        spans.append(f'<tspan font-size="{max(19,size*.68) if sub else size}" dy="{dy:.3f}">{html.escape(s)}</tspan>')
        previous_sub=sub
    scene.append(dict(id=i,kind='formula',x=x,y=y,text=plain,segments=segments,size=size,color=color,anchor=anchor))
    add(f'<text id="{i}" x="{x}" y="{y}" font-family="Times New Roman" font-size="{size}" font-style="italic" text-anchor="{anchor}" fill="{color}">'+''.join(spans)+'</text>')
def line(i,pts,width=2.5,dashed=False,arrow=True,both=False,color='#060606'):
    scene.append(dict(id=i,kind='wire',points=pts,width=width,dashed=dashed,arrow=arrow,both=both,color=color))
    p=' '.join(f'{x},{y}' for x,y in pts)
    add(f'<polyline id="{i}" points="{p}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="miter"'+(' stroke-dasharray="10 6"' if dashed else '')+(' marker-end="url(#arrow)"' if arrow else '')+(' marker-start="url(#arrowStart)"' if both else '')+'/>')
def icon(i,crop,threshold=103):
    x0,y0,x1,y1=crop
    arr=src[y0:y1,x0:x1]
    black=(np.max(arr,axis=2)<threshold).astype(np.uint8)*255
    contours,hierarchy=cv2.findContours(black,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    ds=[]
    for c in contours:
        if cv2.contourArea(c)<1.3:continue
        c=cv2.approxPolyDP(c,.25,True).reshape(-1,2)
        ds.append('M'+' L'.join(f'{x+x0:.2f},{y+y0:.2f}' for x,y in c)+' Z')
    d=' '.join(ds)
    add(f'<path id="{i}" d="{d}" fill="#050505" fill-rule="evenodd"/>')
    scene.append(dict(id=i,kind='icon',x=x0,y=y0,w=x1-x0,h=y1-y0,path=d,contours=len(ds)))

add(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="174mm" height="{174*H/W:.6f}mm" viewBox="0 0 {W} {H}">')
add('''<defs>
<linearGradient id="gray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f0f3f6"/><stop offset="1" stop-color="#e7edf1"/></linearGradient>
<linearGradient id="blue" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9f5ff"/><stop offset="1" stop-color="#dceffc"/></linearGradient>
<linearGradient id="green" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#edf8ee"/><stop offset="1" stop-color="#e5f1e9"/></linearGradient>
<linearGradient id="orange" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff4e9"/><stop offset="1" stop-color="#ffe5d3"/></linearGradient>
<linearGradient id="sharedFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f0f8fe"/><stop offset="1" stop-color="#edf6fc"/></linearGradient>
<linearGradient id="whitegray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#f3f6f8"/></linearGradient>
<marker id="arrow" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#050505"/></marker>
<marker id="arrowStart" viewBox="0 0 10 10" refX="9.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#050505"/></marker>
</defs><rect width="1816" height="866" fill="white"/>''')

# Node frames match the supplied reference bounding boxes.
box('shared',830,58,575,742,'sharedFill','#39556f',15,True)
box('imu',43,81,442,155,'gray','#39516a')
box('gnss',44,259,443,178,'blue','#172589')
box('robot',43,477,444,170,'green','#0d7045')
box('propagation',945,118,417,107,'gray','#3f5570')
box('state',965,277,397,112,'blue','#087aff')
box('update',969,453,398,135,'blue','#087aff')
box('quality',924,659,453,114,'orange','#ff7100')
box('output',1473,224,319,231,'green','#0d7045')
box('frame',542,535,168,73,'whitegray','#3f5570')
box('preprocessing',501,658,250,74,'whitegray','#3f5570',12,True)

# Wires follow the reference. Only the body-velocity inlet is locally elbowed
# onto y=568, matching the frame outlet; the frame box remains in place.
line('imu_to_propagation',[(485,157),(941,157)])
line('propagation_to_state',[(1154,225),(1154,272)])
line('state_to_output',[(1362,331),(1468,331)])
line('state_update',[(1163,399),(1163,446)],both=True)
line('position_to_gate',[(487,324),(868,324),(868,456)])
line('heading_to_gate',[(454,403),(808,403),(808,478),(845,478)])
line('tilt_to_gate',[(487,502),(864,502)])
line('velocity_to_frame',[(418,606),(517,606),(517,568),(537,568)])
line('frame_to_gate',[(710,568),(868,568),(868,499)])
line('gate_to_update',[(888,478),(964,478)])
line('history_to_frame',[(626,658),(626,613)],dashed=True)
line('quality_metadata',[(807,779),(807,718),(919,718)],dashed=True)
line('innovation_to_weighting',[(1121,588),(1121,654)])
line('weighting_to_update',[(1248,659),(1248,594)])
add('<polygon id="gate" points="867,458 887,478 867,498 847,478" fill="#f0f2f2" stroke="#111" stroke-width="2.5"/>')
scene.append(dict(id='gate',kind='diamond',x=847,y=458,w=40,h=40,fill='#f0f2f2'))

# The black icon strokes are traced from exactly the same supplied image.
icon('imu_icon',(72,135,161,222))
icon('antenna_left',(61,326,114,392))
icon('antenna_right',(178,326,232,392))
line('baseline_icon',[(108,381),(184,381)],width=2.5,dashed=True,arrow=False)
mathtext('baseline_label',139,408,[('Δr',False)],25,color='#050505')
icon('robot_icon',(58,534,222,645))
icon('output_axes_icon',(1550,318,1737,449))

# Text uses original anchors, line breaks and visual widths.
txt('imu_title',68,121,'Body MEMS IMU',34,True,maxwidth=300)
txt('imu_rate',260,169,'Angular rate /',26,maxwidth=184)
txt('imu_accel',260,200,'acceleration',26,maxwidth=170)
txt('gnss_title',60,301,'Dual-antenna GNSS',34,True,maxwidth=401)
txt('gnss_position',245,347,'Receiver position/velocity',26,maxwidth=232)
txt('gnss_doppler',245,377,'Raw-Doppler velocity',26,maxwidth=225)
txt('gnss_pair_label',245,408,'Position pair',26,maxwidth=126)
mathtext('gnss_pair_symbols',374,408,[('(p',False),('1',True),(', p',False),('2',True),(')',False)],25,color='#050505')
txt('robot_title',60,518,'Robot motion observations',34,True,maxwidth=414)
txt('robot_tilt',260,569,'Roll / pitch',27,maxwidth=170)
txt('robot_velocity',260,614,'Body velocity',27,maxwidth=148)
txt('shared_title',1157,100,'Shared-state GNSS/INS',36,True,'middle',493)
txt('prop_title',1152,160,'Inertial propagation',32,True,'middle',362)
txt('prop_body',1152,197,'State / covariance prediction',26,False,'middle',382)
mathtext('state_formula',1022,324,[('x = (R, p, v, b',False),('g',True),(', b',False),('a',True),(')',False)],37)
mathtext('state_covariance',1156,373,[('P',False)],36,anchor='middle')
txt('update_title',1168,496,'Observation update',32,True,'middle',350)
txt('update_body_1',1168,538,'Incorporate GNSS and',27,False,'middle',330)
txt('update_body_2',1168,570,'motion observations',27,False,'middle',305)
txt('quality_title',1151,701,'Source quality + innovation',32,True,'middle',407)
mathtext('quality_formula',951,750,[('R',False),('s',True),(' = λ',False),('s',True),(' R',False),('0,s',True)],32,color='#050505')
mathtext('quality_bounds',1168,750,[('1 ≤ λ',False),('s',True),(' ≤ λ',False),('max,s',True)],32,color='#050505')
txt('output_title',1633,267,'Navigation solution',32,True,'middle',289)
txt('output_body',1633,304,'Attitude · Velocity · Position',25,False,'middle',291)
txt('pv_path_1',523,282,'Position / velocity',26,maxwidth=259)
txt('pv_path_2',523,312,'and raw-Doppler',26,maxwidth=239)
mathtext('heading_construction',545,386,[('p',False),('2',True),(' − p',False),('1',True),(' → heading',False)],30,color='#050505')
txt('heading_selection',505,432,'Direction validity / innovation',25,maxwidth=289)
txt('tilt_path_label',562,488,'Tilt observations',25,maxwidth=221)
txt('valid_event_label',873,437,'Valid GNSS event',24,maxwidth=195)
txt('frame_1',626,568,'Frame',26,False,'middle',118)
txt('frame_2',626,597,'rotation',26,False,'middle',138)
txt('history_1',626,689,'Heading + tilt',25,False,'middle',220)
txt('history_2',626,719,'used in preprocessing',24,False,'middle',236)
txt('innovation_label',990,632,'Innovation',25,maxwidth=128)
mathtext('source_covariance',1264,632,[('R',False),('s',True)],29,color='#050505')
txt('quality_metadata_label',600,786,'Measurement quality',25,maxwidth=190)
add('</svg>')

svg='\n'.join(parts)
svg_path=ROOT/'editable/F02_method_traced.svg';svg_path.write_text(svg,encoding='utf-8')
(ROOT/'figures/F02_method.svg').write_text(svg,encoding='utf-8')
cairosvg.svg2pdf(bytestring=svg.encode(),write_to=str(ROOT/'figures/F02_method.pdf'))
cairosvg.svg2png(bytestring=svg.encode(),write_to=str(ROOT/'preview/F02_method.png'),output_width=2560)
cairosvg.svg2png(bytestring=svg.encode(),write_to=str(ROOT/'figures/F02_method.png'),output_width=round(174/25.4*600))
with Image.open(ROOT/'figures/F02_method.png') as im:
    im.convert('RGB').save(ROOT/'figures/F02_method.tiff',compression='tiff_lzw',dpi=(600,600))
    im.save(ROOT/'figures/F02_method.png',dpi=(600,600))
(ROOT/'editable/F02_scene.json').write_text(json.dumps(dict(width=W,height=H,objects=scene),ensure_ascii=False,indent=2),encoding='utf-8')

# Native draw.io text/frames/connectors plus vector icons. Same geometry as SVG.
def export_drawio():
    mx=ET.Element('mxfile',host='app.diagrams.net',type='device')
    d=ET.SubElement(mx,'diagram',id='legsa-author-trace',name='Author figure traced')
    g=ET.SubElement(d,'mxGraphModel',grid='1',gridSize='10',page='1',pageWidth=str(W),pageHeight=str(H))
    root=ET.SubElement(g,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
    fills={'gray':('#f0f3f6','#e7edf1'),'blue':('#e9f5ff','#dceffc'),'green':('#edf8ee','#e5f1e9'),'orange':('#fff4e9','#ffe5d3'),'sharedFill':('#f0f8fe','#edf6fc'),'whitegray':('#fff','#f3f6f8')}
    for o in scene:
        typ=o['kind'];oid=o['id']
        if typ in ['box','diamond']:
            color1,color2=fills.get(o.get('gradient'),(o.get('fill','#fff'),o.get('fill','#fff')))
            style=f'shape={"rhombus" if typ=="diamond" else "rectangle"};rounded=1;arcSize=10;fillColor={color1};gradientColor={color2};gradientDirection=south;strokeColor={o.get("stroke","#111")};strokeWidth=2.3;dashed={int(o.get("dashed",False))};'
            c=ET.SubElement(root,'mxCell',id=oid,style=style,value='',vertex='1',parent='1')
            ET.SubElement(c,'mxGeometry',x=str(o['x']),y=str(o['y']),width=str(o['w']),height=str(o['h']),attrib={'as':'geometry'})
        elif typ in ['text','formula']:
            s=o['text'];sz=o['size'];width=o.get('width',len(s)*sz*.48)+4
            anchor=o.get('anchor','start');x=o['x']-width/2 if anchor=='middle' else o['x']
            # Match the condensed raster text by using a text box with the same
            # width; each label remains editable, unlike the embedded reference.
            style=f'text;html=0;whiteSpace=wrap;overflow=visible;align={"center" if anchor=="middle" else "left"};verticalAlign=middle;fontFamily=Arial;fontSize={sz};fontStyle={int(o.get("bold",False))+(2 if typ=="formula" or o.get("italic") else 0)};fontColor={o.get("color","#050505")};spacing=0;'
            c=ET.SubElement(root,'mxCell',id=oid,value=s,style=style,vertex='1',parent='1')
            ET.SubElement(c,'mxGeometry',x=str(x),y=str(o['y']-sz*.88),width=str(width),height=str(sz*1.12),attrib={'as':'geometry'})
        elif typ=='icon':
            icon_svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{o["x"]} {o["y"]} {o["w"]} {o["h"]}"><path d="{o["path"]}" fill="#050505" fill-rule="evenodd"/></svg>'
            encoded=base64.b64encode(icon_svg.encode()).decode()
            style='shape=image;imageAspect=0;image=data:image/svg+xml,'+encoded+';'
            c=ET.SubElement(root,'mxCell',id=oid,value='',style=style,vertex='1',parent='1')
            ET.SubElement(c,'mxGeometry',x=str(o['x']),y=str(o['y']),width=str(o['w']),height=str(o['h']),attrib={'as':'geometry'})
        else:
            style=f'edgeStyle=none;rounded=0;endArrow={"block" if o["arrow"] else "none"};startArrow={"block" if o["both"] else "none"};strokeColor={o["color"]};strokeWidth={o["width"]};dashed={int(o["dashed"])};'
            c=ET.SubElement(root,'mxCell',id=oid,edge='1',parent='1',style=style)
            geom=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
            for nm,pt in [('sourcePoint',o['points'][0]),('targetPoint',o['points'][-1])]:ET.SubElement(geom,'mxPoint',x=str(pt[0]),y=str(pt[1]),attrib={'as':nm})
            if len(o['points'])>2:
                arr=ET.SubElement(geom,'Array',attrib={'as':'points'})
                for x,y in o['points'][1:-1]:ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
    ET.indent(mx,space='  ')
    ET.ElementTree(mx).write(ROOT/'editable/F02_method_traced.drawio',encoding='utf-8',xml_declaration=True)
export_drawio()

qa=dict(reference_sha256=hashlib.sha256(REF.read_bytes()).hexdigest(),reference_pixels=[W,H],native_vector=True,raster_images_in_svg=0,scene_objects=len(scene),frames=sum(o['kind']=='box' for o in scene),text_objects=sum(o['kind'] in ['text','formula'] for o in scene),traced_icons=sum(o['kind']=='icon' for o in scene),deliberate_difference='Body-velocity inlet elbowed to y=568; native font substitution and few-pixel formula/label clearances; all major node positions preserve reference.',figure_mm=[174,174*H/W],preview_pixels=list(Image.open(ROOT/'preview/F02_method.png').size))
(ROOT/'qa/F02_TRACE_PROVENANCE.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
print(json.dumps(qa,indent=2))
