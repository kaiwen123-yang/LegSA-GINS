from common import *
plt=plot_setup()
from matplotlib.patches import FancyBboxPatch
for p in ['configs/paper_rebuild/methods.yaml','cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp','cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp']:record(W/p)
fig,ax=plt.subplots(figsize=(174/25.4,4.3));fig.subplots_adjust(left=.02,right=.98,bottom=.03,top=.97);ax.set(xlim=(0,10),ylim=(0,9));ax.axis('off')
def box(x,y,w,h,text,color='#EEEEEE'):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.10',facecolor=color,edgecolor='#555555'));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=8)
def arrow(a,b):ax.annotate('',b,a,arrowprops=dict(arrowstyle='->',lw=1))
box(.2,7.3,2.3,1,'Go2 body IMU');box(3.1,7.3,3,1,'Inertial propagation');box(7,7.3,2.6,1,'Navigation state\nand covariance')
arrow((2.6,7.8),(3,7.8));arrow((6.2,7.8),(6.9,7.8))
box(.2,5.4,2.3,1.1,'GNSS position\nReceiver velocity')
box(.2,3.4,2.3,1.2,'Dual-receiver\npositions + status')
box(3.1,3.4,3,1.2,'Exact epoch pairing\nBoth receivers fixed\nWrap-safe residual gate','#DCEEF7')
arrow((2.6,4),(3,4))
box(.2,.25,5.9,2.2,'Velocity-aiding redundancy layer\nRaw Doppler-derived velocity\nLeg horizontal velocity + roll/pitch prior','#F8EAD4')
box(7,3.5,2.6,2,'Measurement\nupdates');box(7,.4,2.6,1.8,'Source-aware\nmetadata and\ninnovation weighting','#F1E2ED')
arrow((6.2,4),(6.9,4));arrow((2.6,5.95),(7,5.25));arrow((6.2,1.35),(6.9,1.35));arrow((8.3,2.3),(8.3,3.4));arrow((8.3,5.6),(8.3,7.2))
ax.text(3.6,2.75,'Go2 attitude and kinematic inputs',ha='center',fontsize=7)
finish(fig,'Fig02','DRAWN_SCHEMATIC')
