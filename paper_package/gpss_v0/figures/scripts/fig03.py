from common import *
plt=plot_setup()
fig,axs=plt.subplots(2,3,figsize=(174/25.4,4.5));fig.subplots_adjust(left=.09,right=.985,bottom=.12,top=.88,wspace=.37,hspace=.36)
for col,s in enumerate(['BY2','BY2H','BY2O']):
 for m in ['F04','LC01']:
  d=error_data(s,m)
  for row,key in enumerate(['yaw_err_deg','horizontal_err_m']):
   # Display every retained error sample; no metric calculation or filtering.
   axs[row,col].plot(d.time,d[key],color=COLORS[m],ls=STYLES[m],lw=.55,label=legend_name(m),alpha=.8)
 for row in range(2):
  ax=axs[row,col];panel(ax,chr(97+row*3+col));ax.set_xlabel('Time (s)');ax.set_ylabel('Yaw error (°)' if row==0 else 'Horizontal error (m)')
  if s=='BY2O':
   for a,b in [(3369.94,3411.95),(3495.94,3508.94)]:ax.axvspan(a,b,color='#888888',alpha=.15)
 axs[0,col].text(.5,1.17,s,transform=axs[0,col].transAxes,ha='center',fontsize=8)
fig.legend(*axs[0,0].get_legend_handles_labels(),loc='upper center',ncol=2,frameon=False)
finish(fig,'Fig03')
