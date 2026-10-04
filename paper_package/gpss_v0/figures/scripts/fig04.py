from common import *
plt=plot_setup()
fig,axs=plt.subplots(1,2,figsize=(174/25.4,3));fig.subplots_adjust(left=.09,right=.98,bottom=.21,top=.76,wspace=.35)
methods=['F02','F03','A04','F04','LC01']
for m in ['F04','LC01']:
 d=error_data('BY2O',m);d=d[(d.time>=3369.94)&(d.time<=3411.95)];axs[0].plot(d.time,d.yaw_err_deg,color=COLORS[m],ls=STYLES[m],lw=.65,label=legend_name(m))
axs[0].set(xlabel='Time (s)',ylabel='Yaw error (°)');panel(axs[0],'a')
r=readcsv(V/'07_AGGREGATE/BY2O_SEGMENT_TABLE.csv')
for i,m in enumerate(methods):
 vals=[float(next(x['yaw_rmse_deg'] for x in r if x['method_id']==m and x['segment_id']==s and x['variant'] in ['','PROTOCOL_V3'] and x['evaluator_contract']=='evaluator_contract_v3')) for s in ['occlusion_primary','occlusion_secondary','outside']]
 axs[1].bar([j+(i-2)*.15 for j in range(3)],vals,width=.14,color=COLORS[m],label=legend_name(m),hatch=['//','..','xx','', '\\\\'][i],edgecolor='white',lw=.3)
axs[1].set_xticks(range(3),['Primary','Secondary','Outside']);axs[1].set_ylabel('Yaw RMSE (°)');panel(axs[1],'b')
fig.legend(*axs[1].get_legend_handles_labels(),loc='upper center',ncol=3,frameon=False,fontsize=7)
finish(fig,'Fig04')
