from common import *
import re
plt=plot_setup();r=readcsv(V/'07_AGGREGATE/ADDENDUM_TABLE_V3.csv')
fig,axs=plt.subplots(1,2,figsize=(174/25.4,3.2));fig.subplots_adjust(left=.10,right=.98,bottom=.2,top=.84,wspace=.33)
for ax,typ,letter in zip(axs,['D61','D62'],'ab'):
 for j,m in enumerate(['F03','A04','F04']):
  rr=[x for x in r if x['method_id']==m and x['degradation_type_id']==typ]
  xs=[];ys=[]
  for x in rr:
   duration=re.search(r'(?:duration_|_)(10|20|30)s',x['case_id'])
   if duration is None:
    duration=re.search(r'(10|20|30)',x['case_id'][3:])
   assert duration,x['case_id']
   xs.append(int(duration.group(1))+(j-1)*1.25);ys.append(float(x['horizontal_rmse_m']))
  ax.scatter(xs,ys,s=15,marker=['o','^','D'][j],facecolors='none' if j<2 else COLORS[m],edgecolors=COLORS[m],label=legend_name(m),alpha=.85)
 ax.set(xlabel='Injected interruption (s)',ylabel='Horizontal RMSE (m)',yscale='log');ax.set_xticks([10,20,30] if typ=='D61' else [10,20]);panel(ax,letter)
 ax.text(.5,1.05,'A1: all GNSS off' if typ=='D61' else 'A2: heading retained',ha='center',transform=ax.transAxes,fontsize=8)
fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False,fontsize=7)
finish(fig,'Fig06')
