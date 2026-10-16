"""Scientific figure assembly and editable vector diagram, approved by the author.

Platform images are viewport crops of a single untouched photograph.
No generative image asset is used in this revision.
"""
from pathlib import Path
import json, math, hashlib, sys
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle, Polygon, FancyArrowPatch
from matplotlib.path import Path as MplPath

ROOT=Path(__file__).resolve().parent
SKILL=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SKILL))
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','svg.hashsalt':'legsa-r2'})
BLUE='#2563EB'; INK='#334155'; CORAL='#E76F51'; TEAL='#009E9A'

def save(fig,stem,alignment=True):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=str(ROOT/'qa'/f'{stem}.alignment.json'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    fig.savefig(ROOT/'figures'/f'{stem}.pdf',dpi=600)
    fig.savefig(ROOT/'figures'/f'{stem}.svg',dpi=600)
    fig.savefig(ROOT/'figures'/f'{stem}.png',dpi=600)
    fig.savefig(ROOT/'figures'/f'{stem}.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    width,height=fig.get_size_inches()
    preview_dpi=max(2560/width,1080/height)
    fig.savefig(ROOT/'preview'/f'{stem}.png',dpi=preview_dpi)
    return {'width_mm':width*25.4,'height_mm':height*25.4,'preview_pixels':[round(width*preview_dpi),round(height*preview_dpi)],'publication_dpi':600}

def platform():
    W,H=174,78
    fig=plt.figure(figsize=(W/25.4,H/25.4),facecolor='white')
    # One assembly canvas: photo viewports and geometry do not have comparable axes.
    ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,W);ax.set_ylim(H,0);ax.axis('off')
    photo=mpimg.imread(ROOT/'assets/platform_original.jpg')
    def viewport(x,y,w,h,crop):
        x0,y0,x1,y1=crop
        sub=photo[y0:y1,x0:x1]
        ch,cw=sub.shape[:2]
        scale=min(w/cw,h/ch);dw,dh=cw*scale,ch*scale
        # Only cropping and uniform display scaling. Original pixel values unchanged.
        ax.imshow(sub,extent=(x+(w-dw)/2,x+(w+dw)/2,y+(h+dh)/2,y+(h-dh)/2),interpolation='antialiased',zorder=1)
    ax.text(3,5,'(a) Experimental platform',fontsize=8.5,va='top')
    ax.text(66,5,'(b) Sensor installation',fontsize=8.5,va='top')
    ax.text(124,5,'(c) Baseline geometry',fontsize=8.5,va='top')
    crop_full=(520,270,1410,1190)
    crop_mount=(890,345,1235,640)
    viewport(3,13,57,58,crop_full)
    viewport(66,18,49,45,crop_mount)
    # Two visible cylindrical antenna assemblies identified as a pair, without
    # asserting which receiver ID belongs to which object in this photograph.
    ax.text(90.5,15,'Dual-antenna assembly',ha='center',fontsize=8,color=INK)
    # Schematic coordinates are abstract, not a survey of lever arms.
    xL,xR,yB=129,166,31
    ax.annotate('',xy=(xL,20),xytext=(xR,20),arrowprops=dict(arrowstyle='<->',lw=.8,color=INK,shrinkA=0,shrinkB=0))
    ax.text((xL+xR)/2,16,'0.35 m (nominal)',ha='center',fontsize=8,color=INK)
    for x in (xL,xR):ax.plot([x,x],[21.5,27.3],color=INK,lw=.55)
    ax.add_patch(Circle((xL,yB),1.55,fc='white',ec=BLUE,lw=1.2,zorder=3))
    ax.add_patch(Circle((xR,yB),1.55,fc='white',ec=BLUE,lw=1.2,zorder=3))
    ax.annotate('',xy=(xL+2.7,yB),xytext=(xR-2.7,yB),arrowprops=dict(arrowstyle='->',lw=1.6,color=BLUE,shrinkA=0,shrinkB=0))
    ax.text(xL,37,'$p_2$',ha='center',fontsize=10,color=BLUE)
    ax.text(xR,37,'$p_1$',ha='center',fontsize=10,color=BLUE)
    ax.text(147.5,42,'$b=p_2-p_1$',ha='center',fontsize=9,color=BLUE)
    origin=(148,61)
    ax.plot(*origin,'o',ms=2.4,color=INK)
    ax.annotate('',xy=(148,49),xytext=origin,arrowprops=dict(arrowstyle='->',lw=.85,color=INK))
    ax.annotate('',xy=(135,61),xytext=origin,arrowprops=dict(arrowstyle='->',lw=.85,color=INK))
    ax.text(151,50,'$x_b$',fontsize=9,va='center')
    ax.text(134,66,'$y_b$',fontsize=9,ha='center')
    ax.text(90.5,69,'Same photograph; detail',ha='center',fontsize=8,color=INK)
    ax.text(147.5,73,'Schematic top view',ha='center',fontsize=8,color=INK)
    qa=save(fig,'F01_platform')
    qa.update(original_photo_sha256=hashlib.sha256((ROOT/'assets/platform_original.jpg').read_bytes()).hexdigest(),full_platform_crop_xyxy=crop_full,installation_crop_xyxy=crop_mount,brightness_contrast_adjustment=False,ai_image_asset_used=False,minimum_nominal_font_pt=8,geometry_is_abstract=True)
    (ROOT/'qa/F01_SOURCE_AND_LAYOUT.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
    plt.close(fig)

def method():
    W,H=174,126
    fig=plt.figure(figsize=(W/25.4,H/25.4),facecolor='white')
    ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,W);ax.set_ylim(H,0);ax.axis('off')
    objects=[]
    def box(i,x,y,w,h,fill,stroke=INK,rounded=True,dashed=False):
        obj=dict(id=i,kind='box',x=x,y=y,w=w,h=h,fill=fill,stroke=stroke,rounded=rounded,dashed=dashed)
        objects.append(obj)
        if rounded: patch=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0,rounding_size=1.2',fc=fill,ec=stroke,lw=.8,linestyle=(0,(4,3)) if dashed else '-',zorder=1)
        else:patch=Rectangle((x,y),w,h,fc=fill,ec=stroke,lw=.8,zorder=1)
        ax.add_patch(patch)
    def text(i,x,y,s,size=8,bold=False,color=INK,plain=None):
        objects.append(dict(id=i,kind='text',x=x,y=y,text=plain or s,size=size,bold=bold,color=color))
        ax.text(x,y,s,fontsize=size,ha='center',va='center',weight='bold' if bold else 'normal',color=color,zorder=4,linespacing=1.25)
    def wire(i,pts,color=INK,width=.85,dashed=False,arrow=True,both=False):
        objects.append(dict(id=i,kind='wire',points=pts,color=color,width=width,dashed=dashed,arrow=arrow,both=both))
        if len(pts)>2:ax.plot([p[0] for p in pts[:-1]],[p[1] for p in pts[:-1]],color=color,lw=width,ls='--' if dashed else '-',zorder=2)
        if arrow:
            ax.add_patch(FancyArrowPatch(pts[-2],pts[-1],arrowstyle='<->' if both else '-|>',mutation_scale=9,lw=width,color=color,linestyle='--' if dashed else '-',shrinkA=0,shrinkB=0,zorder=2))
        else:ax.plot([p[0] for p in pts[-2:]],[p[1] for p in pts[-2:]],color=color,lw=width,ls='--' if dashed else '-',zorder=2)

    box('shared',89,2,56,122,'#F7FAFF',BLUE,dashed=True)
    text('shared_title',117,6.5,'Shared-state GNSS/INS',9,True)
    box('imu',3,10,39,20,'#F1F5F9')
    text('imu_title',22.5,15.5,'Body MEMS IMU',9,True)
    text('imu_measurement',22.5,23.5,'Angular rate\nAcceleration',8)
    box('gnss',3,39,39,29,'#EBF3FF',BLUE)
    text('gnss_title',22.5,44.5,'Dual-antenna GNSS',9,True)
    text('gnss_pv',22.5,53,'Position / velocity\nRaw-Doppler velocity',8)
    text('gnss_pair',22.5,63,'Position pair $(p_1,p_2)$',8,plain='Position pair (p₁, p₂)')
    box('robot',3,85,39,27,'#EAF8F5',TEAL)
    text('robot_title',22.5,91,'Robot observations',9,True)
    text('robot_tilt',22.5,99,'Roll / pitch',8)
    text('robot_velocity',22.5,107,'Body velocity',8)
    box('propagation',94,14,46,17,'#F1F5F9')
    text('prop_title',117,19,'Inertial propagation',9,True)
    text('prop_body',117,26,'State / covariance prediction',8)
    box('state',94,42,46,17,'#E8F1FF',BLUE)
    text('state_vector',117,47.5,'$x=(R,p,v,b_g,b_a)$',10,plain='x = (R, p, v, b_g, b_a)')
    text('state_cov',117,54.5,'$P$',10,plain='P')
    box('update',94,68,46,21,'#E8F1FF',BLUE)
    text('update_title',117,73,'Observation update',9,True)
    text('update_body',117,82,'GNSS and motion\nobservations',8)
    box('quality',94,99,46,22,'#FFF0E9',CORAL)
    text('quality_title',117,104,'Source quality\nand innovation',8.4,True)
    text('quality_formula',117,112,'$R_s=\lambda_sR_{0,s}$',10,plain='Rₛ = λₛ R₀,ₛ')
    text('bound',117,118.4,'$1\leq\lambda_s\leq\lambda_{\max,s}$',8.5,plain='1 ≤ λₛ ≤ λmax,s')
    box('output',150,43,22,32,'#EAF8F5',TEAL)
    text('output_title',161,48.5,'Output',9,True)
    text('output_body',161,61,'Attitude\nVelocity\nPosition',8)
    box('frame',55,101,23,13,'#F1F5F9')
    text('frame_text',66.5,107.5,'Frame\nrotation',8.5)
    gate=[(84,75),(87,78),(84,81),(81,78)]
    ax.add_patch(Polygon(gate,fc='white',ec=INK,lw=.9,zorder=3))
    objects.append(dict(id='gate',kind='diamond',x=81,y=75,w=6,h=6,fill='white',stroke=INK))
    text('gate_text',79,67.5,'Valid\nGNSS\nevent',8)
    wire('imu_to_propagation',[(42,22.5),(94,22.5)])
    wire('propagation_to_state',[(117,31),(117,42)])
    wire('state_update',[(117,59),(117,68)],both=True)
    wire('state_to_output',[(140,50.5),(150,50.5)])
    wire('gnss_pv_to_gate',[(42,51),(84,51),(84,75)])
    text('gnss_pv_label',63,46.5,'Position / velocity\nand raw Doppler',8)
    wire('heading_to_gate',[(42,63),(74,63),(74,78),(81,78)],color=BLUE,width=1.05)
    text('heading_construction',58,58.5,'$p_2-p_1$ to heading',8,color=BLUE,plain='p₂ − p₁ to heading')
    text('heading_selection',57.5,71,'Validity + innovation',8,color=BLUE)
    wire('tilt_to_gate',[(42,99),(48,99),(48,88),(84,88)],color=TEAL,arrow=False)
    text('tilt_label',64,84.5,'Tilt observations',8,color=TEAL)
    wire('body_velocity_to_frame',[(42,107.5),(55,107.5)],color=TEAL)
    wire('frame_to_gate',[(78,107.5),(84,107.5),(84,81)],color=TEAL)
    wire('gate_to_update',[(87,78),(94,78)],width=1.0)
    wire('preprocess_to_frame',[(66.5,118),(66.5,114)],dashed=True)
    text('preprocess',62.5,122,'Historical heading + tilt\nused in preprocessing',8)
    wire('update_innovation',[(104,89),(104,99)])
    text('innovation_label',114,95,'Innovation',8)
    wire('covariance_to_update',[(131,99),(131,89)])
    text('covariance_label',135.5,95,'$R_s$',9,plain='Rₛ')
    qa=save(fig,'F02_method')
    qa.update(vector=True,editable_text=True,native_shapes=len(objects),frame_input_y=107.5,frame_output_y=107.5,graph_edges=[o['id'] for o in objects if o['kind']=='wire'],minimum_nominal_font_pt=8)
    (ROOT/'qa/F02_EDITABILITY.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
    (ROOT/'editable/F02_scene.json').write_text(json.dumps({'width_mm':W,'height_mm':H,'objects':objects},ensure_ascii=False,indent=2),encoding='utf-8')
    drawio(objects,W,H)
    plt.close(fig)

def drawio(objects,W,H):
    SCALE=6.0
    mx=ET.Element('mxfile',host='app.diagrams.net',type='device')
    diagram=ET.SubElement(mx,'diagram',id='legsa-v3-r2',name='Figure 2 editable')
    graph=ET.SubElement(diagram,'mxGraphModel',dx='1200',dy='850',grid='1',gridSize='6',page='1',pageWidth=str(W*SCALE),pageHeight=str(H*SCALE),math='0')
    root=ET.SubElement(graph,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
    object_by_id={o['id']:o for o in objects}
    text_parent={
        'shared_title':'shared','imu_title':'imu','imu_measurement':'imu',
        'gnss_title':'gnss','gnss_pv':'gnss','gnss_pair':'gnss',
        'robot_title':'robot','robot_tilt':'robot','robot_velocity':'robot',
        'prop_title':'propagation','prop_body':'propagation',
        'state_vector':'state','state_cov':'state','update_title':'update','update_body':'update',
        'quality_title':'quality','quality_formula':'quality','bound':'quality',
        'output_title':'output','output_body':'output','frame_text':'frame',
    }
    for o in objects:
        kind=o['kind'];id=o['id']
        if kind in ('box','diamond'):
            shape='rhombus' if kind=='diamond' else 'rectangle'
            style=f'shape={shape};rounded={int(o.get("rounded",False))};arcSize=10;whiteSpace=wrap;html=0;fillColor={o["fill"]};strokeColor={o["stroke"]};strokeWidth=1.6;dashed={int(o.get("dashed",False))};'
            cell=ET.SubElement(root,'mxCell',id=id,value='',style=style,vertex='1',parent='1')
            ET.SubElement(cell,'mxGeometry',x=str(o['x']*SCALE),y=str(o['y']*SCALE),width=str(o['w']*SCALE),height=str(o['h']*SCALE),attrib={'as':'geometry'})
        elif kind=='text':
            # Individual text objects preserve editable wording and formatting.
            nlines=o['text'].count('\n')+1
            width=max(18,min(56,max(len(s) for s in o['text'].splitlines())*o['size']*.18))
            height=nlines*o['size']*.48+1
            px=o['size']*25.4/72*SCALE
            style=f'text;html=0;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontFamily=Arial;fontSize={px:.2f};fontColor={o["color"]};fontStyle={int(o["bold"])};spacing=0;'
            parent_id=text_parent.get(id,'1')
            px0=object_by_id[parent_id]['x'] if parent_id!='1' else 0
            py0=object_by_id[parent_id]['y'] if parent_id!='1' else 0
            cell=ET.SubElement(root,'mxCell',id=id,value=o['text'],style=style,vertex='1',parent=parent_id)
            ET.SubElement(cell,'mxGeometry',x=str((o['x']-width/2-px0)*SCALE),y=str((o['y']-height/2-py0)*SCALE),width=str(width*SCALE),height=str(height*SCALE),attrib={'as':'geometry'})
        else:
            style=f'edgeStyle=none;rounded=0;html=0;endArrow={"block" if o["arrow"] else "none"};endFill=1;startArrow={"block" if o["both"] else "none"};strokeColor={o["color"]};strokeWidth={o["width"]*2.1};dashed={int(o["dashed"])};'
            connections={
                'imu_to_propagation':('imu','propagation',1,.625,0,.5),
                'propagation_to_state':('propagation','state',.5,1,.5,0),
                'state_update':('state','update',.5,1,.5,0),
                'state_to_output':('state','output',1,.5,0,.234375),
                'gnss_pv_to_gate':('gnss','gate',1,12/29,.5,0),
                'heading_to_gate':('gnss','gate',1,24/29,0,.5),
                'body_velocity_to_frame':('robot','frame',1,22.5/27,0,.5),
                'frame_to_gate':('frame','gate',1,.5,.5,1),
                'gate_to_update':('gate','update',1,.5,0,10/21),
                'update_innovation':('update','quality',10/46,1,10/46,0),
                'covariance_to_update':('quality','update',37/46,0,37/46,1),
            }
            attrs={}
            if id in connections:
                source,target,ex,ey,ix,iy=connections[id]
                attrs={'source':source,'target':target}
                style+=f'exitX={ex};exitY={ey};entryX={ix};entryY={iy};exitPerimeter=0;entryPerimeter=0;'
            cell=ET.SubElement(root,'mxCell',id=id,style=style,edge='1',parent='1',**attrs)
            geom=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
            for role,pt in [('sourcePoint',o['points'][0]),('targetPoint',o['points'][-1])]:ET.SubElement(geom,'mxPoint',x=str(pt[0]*SCALE),y=str(pt[1]*SCALE),attrib={'as':role})
            if len(o['points'])>2:
                arr=ET.SubElement(geom,'Array',attrib={'as':'points'})
                for pt in o['points'][1:-1]:ET.SubElement(arr,'mxPoint',x=str(pt[0]*SCALE),y=str(pt[1]*SCALE))
    ET.indent(mx,space='  ')
    ET.ElementTree(mx).write(ROOT/'editable/F02_method.drawio',encoding='utf-8',xml_declaration=True)

if __name__=='__main__':
    platform();method()
    print('Created F01 platform and F02 editable method figures')
