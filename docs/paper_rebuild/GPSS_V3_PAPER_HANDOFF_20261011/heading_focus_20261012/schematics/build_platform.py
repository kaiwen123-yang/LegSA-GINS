"""Compose the untouched source photograph, an AI illustration, and native geometry.

No pixel retouching or simulated measurement data. Geometric panel is schematic.
"""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, Circle
import matplotlib.image as mpimg

ROOT = Path(__file__).resolve().parent
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,
                     'pdf.fonttype':42,'svg.fonttype':'none'})
MM=1/25.4
W,H=174,82
fig=plt.figure(figsize=(W*MM,H*MM),facecolor='white')
def panel(x,y,w,h):
    ax=fig.add_axes([x/W,y/H,w/W,h/H]); ax.set_axis_off(); return ax
def label(x,y,s):
    fig.text(x/W,y/H,s,fontsize=8,ha='left',va='top')

# Publication composition only: the original photograph is displayed in full.
label(3,79,'(a) Experimental platform')
photo=panel(3,15,70,56)
photo.imshow(mpimg.imread(ROOT/'assets/platform_original.jpg'))
label(78,79,'(b) Platform illustration')
art=panel(78,17,52,54)
art.imshow(mpimg.imread(ROOT/'assets/platform_illustration.png'))
label(135,79,'(c) Short-baseline\n     geometry')
ax=panel(134,13,38,57)
ax.set_xlim(0,10); ax.set_ylim(0,15); ax.set_aspect('equal')
gray='#505a64'; blue='#0072b2'
for x in (1.45,8.55):
    for y in (4.4,10.5):
        ax.add_patch(Ellipse((x,y),1.2,2.0,facecolor='#e6e9ec',edgecolor=gray,lw=.7))
ax.add_patch(FancyBboxPatch((2.1,3.5),5.8,8.1,boxstyle='round,pad=.12,rounding_size=.55',facecolor='#f1f3f5',edgecolor=gray,lw=.8))
# Abstract antenna geometry: node coordinates are not surveyed lever arms.
for x,t in [(2.35,'$p_2$'),(7.65,'$p_1$')]:
    ax.add_patch(Circle((x,10),.38,fc='white',ec=blue,lw=1.1))
    ax.text(x,11.15,t,ha='center',va='bottom',fontsize=8,color=blue)
ax.annotate('',xy=(2.9,10),xytext=(7.1,10),arrowprops=dict(arrowstyle='->',color=blue,lw=1.3))
ax.text(5,8.85,'$b=p_2-p_1$',ha='center',va='center',fontsize=8,color=blue)
ax.annotate('',xy=(2.35,13),xytext=(7.65,13),arrowprops=dict(arrowstyle='<->',color=gray,lw=.7,shrinkA=0,shrinkB=0))
ax.text(5,13.75,'0.35 m',ha='center',fontsize=8)
ax.text(5,12.0,'nominal',ha='center',fontsize=8,color=gray)
ax.plot([5],[5.5],marker='o',ms=2,color=gray)
ax.annotate('',xy=(5,8),xytext=(5,5.5),arrowprops=dict(arrowstyle='->',color=gray,lw=.9))
ax.annotate('',xy=(2.5,5.5),xytext=(5,5.5),arrowprops=dict(arrowstyle='->',color=gray,lw=.9))
ax.text(5.5,7.65,'$x_b$',fontsize=8)
ax.text(2.5,4.6,'$y_b$',fontsize=8)
fig.text(3/W,8/H,'Real platform',fontsize=8,color=gray)
fig.text(78/W,8/H,'Illustrative rendering',fontsize=8,color=gray)
fig.text(135/W,8/H,'Top view; schematic',fontsize=8,color=gray)

for ext in ('pdf','svg','png','tiff'):
    kwargs={'dpi':600}
    if ext=='tiff': kwargs['pil_kwargs']={'compression':'tiff_lzw'}
    fig.savefig(ROOT/'figures'/f'F01_platform.{ext}',**kwargs)
fig.savefig(ROOT/'preview/F01_platform.png',dpi=300)
renderer=fig.canvas.get_renderer()
overflow=[]
for txt in fig.findobj(matplotlib.text.Text):
    if txt.get_visible() and txt.get_text():
        bb=txt.get_window_extent(renderer)
        if bb.x0<0 or bb.y0<0 or bb.x1>fig.bbox.width or bb.y1>fig.bbox.height:
            overflow.append(txt.get_text())
metrics={'figure_size_mm':[W,H],'min_native_label_pt':8,'text_outside_canvas':overflow,
         'photo_pixels':[1706,1279],'photo_width_mm':70,'photo_native_ppi':1706/(70/25.4),
         'illustration_pixels':[1254,1254],'illustration_width_mm':52,'illustration_native_ppi':1254/(52/25.4),
         'original_photo_displayed_full':True,'geometry':'abstract body-frame geometry, not a surveyed lever-arm drawing'}
(ROOT/'PLATFORM_QA.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
print(json.dumps(metrics,indent=2))
