from pathlib import Path
import sys,json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Circle
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'svg.fonttype':'none','pdf.fonttype':42})
W,H=174,82
fig=plt.figure(figsize=(W/25.4,H/25.4),facecolor='white')
ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,W);ax.set_ylim(H,0);ax.axis('off')
def image_panel(path,x,y,w,h):
    im=mpimg.imread(path);ih,iw=im.shape[:2];s=min(w/iw,h/ih);dw,dh=iw*s,ih*s
    ax.imshow(im,extent=(x+(w-dw)/2,x+(w+dw)/2,y+(h+dh)/2,y+(h-dh)/2),zorder=1)
ax.text(3,6,'(a) Experimental platform',va='top',fontsize=8.5)
ax.text(77,6,'(b) Platform illustration',va='top',fontsize=8.5)
ax.text(134,6,'(c) Baseline geometry',va='top',fontsize=8.5)
image_panel(ROOT/'references/platform_original.jpg',3,16,67,54)
image_panel(ROOT/'references/platform_illustration.png',77,16,52,54)
BLUE='#2563EB';INK='#334155'
left,right,by=139,168,32
ax.annotate('',xy=(left,21),xytext=(right,21),arrowprops=dict(arrowstyle='<->',lw=.8,color=INK,shrinkA=0,shrinkB=0))
ax.text((left+right)/2,17,'0.35 m (nominal)',ha='center',fontsize=8,color=INK)
for x in [left,right]:
    ax.plot([x,x],[22.5,28.5],color=INK,lw=.5)
    ax.add_patch(Circle((x,by),1.5,fc='white',ec=BLUE,lw=1.2))
ax.annotate('',xy=(left+2.7,by),xytext=(right-2.7,by),arrowprops=dict(arrowstyle='->',lw=1.4,color=BLUE,shrinkA=0,shrinkB=0))
ax.text(left,38,'$p_2$',ha='center',fontsize=10,color=BLUE)
ax.text(right,38,'$p_1$',ha='center',fontsize=10,color=BLUE)
ax.text(153.5,44,'$b=p_2-p_1$',ha='center',fontsize=9,color=BLUE)
ax.plot([153.5],[64],'o',ms=2.4,color=INK)
ax.annotate('',xy=(153.5,51),xytext=(153.5,64),arrowprops=dict(arrowstyle='->',lw=.8,color=INK))
ax.annotate('',xy=(140,64),xytext=(153.5,64),arrowprops=dict(arrowstyle='->',lw=.8,color=INK))
ax.text(156,52,'$x_b$',fontsize=9,va='center')
ax.text(140,69,'$y_b$',fontsize=9,ha='center')
ax.text(3,77,'Original photograph',fontsize=8,color=INK)
ax.text(77,77,'Illustrative rendering',fontsize=8,color=INK)
ax.text(134,77,'Schematic top view',fontsize=8,color=INK)
fig.canvas.draw()
require_matplotlib_panel_alignment(fig,json_out=str(ROOT/'qa/F01_alignment.json'),strict=True)
fig.savefig(ROOT/'figures/F01_platform.pdf',dpi=600)
fig.savefig(ROOT/'figures/F01_platform.svg',dpi=600)
fig.savefig(ROOT/'figures/F01_platform.png',dpi=600)
fig.savefig(ROOT/'figures/F01_platform.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
fig.savefig(ROOT/'preview/F01_platform.png',dpi=2560/(W/25.4))
(ROOT/'qa/F01_SOURCE.json').write_text(json.dumps({'figure_mm':[W,H],'restored_previous_imagegen_asset':True,'new_image_generation':False,'original_photo_used_full':True,'illustration_width_mm':52,'illustration_native_pixels':[1254,1254],'geometry_text_separated':True,'source_sha256':{n:hashlib.sha256((ROOT/'references'/n).read_bytes()).hexdigest() for n in ['platform_original.jpg','platform_illustration.png']}},indent=2),encoding='utf-8')
