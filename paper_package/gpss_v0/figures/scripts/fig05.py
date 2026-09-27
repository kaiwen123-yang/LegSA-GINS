from common import *
plt=plot_setup()
r=readcsv(V/'07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv');summ=readcsv(V/'07_AGGREGATE/CORE_541_SUMMARY_V3.csv')
fig,axs=plt.subplots(1,2,figsize=(174/25.4,3.2));fig.subplots_adjust(left=.09,right=.98,bottom=.19,top=.77,wspace=.30)
for ax,key,label,letter in zip(axs,['yaw_rmse_deg','horizontal_rmse_m'],['Yaw RMSE (°)','Horizontal RMSE (m)'],'ab'):
 for m in ['F02','F03','A04','F04']:
  rr=sorted([x for x in r if x['method_id']==m and x['metric']==key],key=lambda x:float(x['ordered_rank']))
  sr=next(x for x in summ if x['method_id']==m and x['metric']==key)
  ax.step([float(x['value']) for x in rr],[float(x['ecdf']) for x in rr],where='post',color=COLORS[m],ls=STYLES[m],label=f"{m}: n={sr['finite_count']}, failures={sr['algorithm_failure_count']}",lw=1)
 ax.set(xlabel=label,ylabel='ECDF (fraction)',xscale='log',ylim=(0,1.02));panel(ax,letter)
fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',ncol=2,frameon=False,fontsize=7)
finish(fig,'Fig05')
