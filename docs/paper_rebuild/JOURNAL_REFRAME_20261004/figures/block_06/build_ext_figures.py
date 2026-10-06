"""Existing EXT V2 accepted errors, native support and frozen metrics only."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from plot_utils import Book,setup,frame,np,plt
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[4]
ROOT=REPO/'docs/paper_rebuild/hext/EXT_REPRODUCTION/v2_fix'
book=Book(HERE);setup();accept=book.json(ROOT/'FINAL_EXECUTION_RECEIPT.json')
assert accept['native_method_sequence_calls_final']==9 and accept['reference_opens_online']==0
allsummary=[]
methods=['EXT01','EXT02','EXT03'];colors=['#0072B2','#D55E00','#009E73'];labels=['Constrained LAMBDA','Constrained WLS','Recursive ambiguity filter']
for seq,start,end,denom in [('BY2',66,340,1370),('BY2H',413,683,1350),('BY2O',3186,3563,1885)]:
 erows=book.rows(ROOT/'evaluation_results'/seq/'ERROR_SERIES.csv');d=book.copy(seq+'_all_methods_all_window_epochs',erows)
 met=book.json(ROOT/'evaluation_results'/seq/'HEADING_METRICS.json')
 fig,axs=plt.subplots(2,1,figsize=(14,6.5),sharex=True,gridspec_kw={'height_ratios':[2.4,1]})
 fig.subplots_adjust(left=.17,right=.98,top=.78,bottom=.17,hspace=.17)
 for i,(method,color,label) in enumerate(zip(methods,colors,labels)):
  dm=d[d.method_id==method];assert len(dm)==denom
  t=dm.t_rel_s.astype(float).to_numpy()-start
  y=__import__('pandas').to_numeric(dm.error_valid_deg,errors='coerce').to_numpy()
  good=(dm.valid=='1').to_numpy() & np.isfinite(y)
  m=met[method];count=m['valid']['count'];assert int(good.sum())==m['valid_epochs_in_window']==count
  idx=np.flatnonzero(good);groups=np.split(idx,np.flatnonzero((np.diff(idx)>1)|(np.diff(t[idx])>.41)|(np.abs(np.diff(y[idx]))>180))+1)
  for k,part in enumerate(groups):
   axs[0].plot(t[part],y[part],color=color,lw=.65,marker='.',ms=1.7,label=(f'{label}: {count}/{denom}, {m["valid"]["rmse_deg"]:.2f}°' if k==0 else None))
  axs[1].hlines(i,0,end-start,color='#D1D6DC',lw=6)
  axs[1].scatter(t[good],np.full(count,i),marker='|',s=90,color=color)
  allsummary.append({'sequence':seq,'method':method,'label':label,'native_valid':str(count),'denominator':str(denom),'rmse_deg':str(m['valid']['rmse_deg']),'run_id':m['native_identity']['run_id']})
 axs[0].set_ylim(-190,190);axs[0].set_yticks([-180,-90,0,90,180]);axs[0].set_ylabel('Projected-heading error (°)')
 axs[1].set_yticks([0,1,2],labels,fontsize=12);axs[1].set_ylim(-.5,2.5);axs[1].set_xlabel('Elapsed time from formal window start (s)')
 for ax in axs:frame(ax);ax.set_xlim(0,end-start)
 fig.suptitle(seq+' | Raw-observation heading: error and native support',fontsize=18,fontweight='bold',y=.985)
 fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.57,.942),ncol=3,fontsize=10.5,frameon=False)
 fig.text(.17,.855,'All saved valid errors; lines break across invalid epochs and angle-wrap jumps.',fontsize=12,color='#596579')
 fig.text(.17,.06,'V2 guardless execution snapshots; no post-result guard rerun. Reference is fused Euler yaw, not independent truth.',fontsize=11,color='#596579')
 fig.text(.17,.029,'Projected lateral-baseline heading is not full body attitude. Different input/algorithm branches prevent a same-input solver ranking.',fontsize=11,color='#596579')
 book.figure(fig,'R13_'+seq+'_raw_heading_error_support','Large errors and missing native outputs persist in the accepted raw-observation implementations.',
  'All native-valid saved heading errors and all original paired-epoch support, not held values. Three V2 methods retain their exact historical source snapshots.',all_invalid_rows_retained=True,no_wrap_jump_connections=True)
book.copy('nine_EXT_V2_saved_metrics',allsummary)
fig,axs=plt.subplots(1,2,figsize=(14,6.5),sharey=True)
fig.subplots_adjust(left=.19,right=.97,top=.85,bottom=.20,wspace=.32)
for i,r in enumerate(allsummary):
 c=colors[methods.index(r['method'])];axs[0].scatter(float(r['rmse_deg']),i,color=c,s=55)
 pct=100*int(r['native_valid'])/int(r['denominator']);axs[1].barh(i,pct,color=c,height=.55)
 axs[1].text(pct+1,i,r['native_valid']+'/'+r['denominator'],va='center',fontsize=11)
axs[0].set_yticks(range(9),[r['sequence']+' | '+r['label'] for r in allsummary],fontsize=11.5);axs[0].invert_yaxis()
axs[0].set_xlim(0,115);axs[0].set_xlabel('Own-support RMSE (°)')
axs[1].set_xlim(0,105);axs[1].set_xlabel('Native-valid availability (%)');axs[1].tick_params(labelleft=False)
for ax in axs:frame(ax)
fig.suptitle('Raw heading | All nine accepted executions',fontsize=18,fontweight='bold',y=.985)
fig.text(.19,.06,'No best-result selection; failed epochs remain in 1370/1350/1885 denominators. RMSE is conditional on actual valid support.',fontsize=11,color='#596579')
fig.text(.19,.029,'Paper-core implementations with stated adaptations; projected heading versus fused Euler reference is an application diagnostic.',fontsize=11,color='#596579')
book.figure(fig,'R14_raw_heading_all_nine_accuracy_coverage','Accuracy must be read alongside available-output coverage.',
 'Nine saved own-support RMSEs and native-valid original paired denominators; no new science calls or metric recalculation.')
book.seal(__file__,accepted_native_identity='RAW_REPRO_V2_TECH_RETRY_2',no_latest_source_rebinding=True)
