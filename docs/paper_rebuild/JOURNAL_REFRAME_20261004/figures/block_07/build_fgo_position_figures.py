"""Draw sealed FGO saved metrics/errors; never import the evaluator/solver."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from plot_utils import Book,setup,frame,np,plt
HERE=Path(__file__).resolve().parent
S=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z')
book=Book(HERE);setup();complete=book.json(S/'ALL_OFFLINE_COMPLETE.json')
assert complete['all_three_offline_complete'] and complete['native_online_reference_opens']==0 and complete['metric_row_count']==36
pins={s['sequence']:s['output_hashes'] for s in complete['sequences']}
methods=['OISAM','WEN_TC','GNC'];labels=['OiSAM (RTK + IMU)','Wen TC (code + AHRS/IMU)','GNC (code + Doppler)'];colors=['#0072B2','#D55E00','#009E73']
allmetrics=[];byseq={}
for seq,start,end,expected in [('BY2',66,340,275),('BY2H',413,683,271),('BY2O',3186,3563,378)]:
 root=S/'evaluation'/seq
 mr=book.rows(root/'METRICS.csv',pins[seq]['METRICS.csv']);allmetrics+=mr
 own={r['method_id']:r for r in mr if r['support_role']=='PRIMARY_DYNAMIC_ONLY' and r['support']=='OWN_VALID'}
 secondary={r['method_id']:r for r in mr if r['support_role']=='SECONDARY_ALL_VALID_POSITION' and r['support']=='OWN_VALID'};byseq[seq]=(own,secondary)
 fig,axs=plt.subplots(2,1,figsize=(14,6.5),sharex=True)
 fig.subplots_adjust(left=.12,right=.98,top=.78,bottom=.18,hspace=.18)
 for method,label,color in zip(methods,labels,colors):
  name=method+'_PRIMARY_DYNAMIC_ONLY_ERRORS.csv';r=book.rows(root/name,pins[seq][name]);d=book.copy(seq+'_'+method+'_primary_saved_errors',r)
  import pandas as pd
  good=(d.valid=='1') & (d.prior_only=='0') & pd.to_numeric(d.horizontal_err_m,errors='coerce').notna()
  assert int(good.sum())==int(own[method]['matched_epoch_count']) and int(own[method]['expected_epoch_count'])==expected
  d=d.loc[good].copy()
  y=d.horizontal_err_m.astype(float).to_numpy();u=d.err_u_m.astype(float).to_numpy();t=d.time.astype(float).to_numpy()-start
  blocks=d.block_id.fillna('').to_numpy() if 'block_id' in d else np.full(len(d),'FULL_BATCH')
  parts=np.split(np.arange(len(d)),np.flatnonzero((np.diff(t)>1.01)|(blocks[1:]!=blocks[:-1]))+1)
  for k,part in enumerate(parts):
   text=f'{label}: {len(d)}/{expected}' if k==0 else None
   axs[0].plot(t[part],y[part],color=color,lw=.85,marker='.',ms=2,label=text)
   axs[1].plot(t[part],u[part],color=color,lw=.85,marker='.',ms=2)
  if seq=='BY2O' and method=='OISAM':
   diag=(d.native_status=='OK_USABLE_NONLINEAR_ITERATION_LIMIT').to_numpy()
   assert diag.sum()==1 and d.loc[diag,'time'].astype(float).tolist()==[3286.0]
   axs[0].scatter(t[diag],y[diag],marker='x',s=70,lw=1.7,color='#CC79A7',zorder=8)
   axs[0].annotate('3286 s: usable, not converged',xy=(100,y[t==100][0]),xytext=(120,.45),fontsize=11,color='#935784',arrowprops={'arrowstyle':'->','color':'#935784'})
 axs[0].set_yscale('log');axs[0].set_ylabel('H error (m)',fontsize=15)
 axs[1].set_yscale('symlog',linthresh=.1);axs[1].set_ylabel('Up error (m)',fontsize=15);axs[1].axhline(0,color='#7B8590',lw=.6)
 axs[0].text(.99,.99,'log scale',ha='right',va='top',transform=axs[0].transAxes,fontsize=10,color='#596579')
 axs[1].text(.99,.99,'symlog; linear within ±0.1 m',ha='right',va='top',transform=axs[1].transAxes,fontsize=10,color='#596579')
 for ax in axs:frame(ax);ax.set_xlim(0,end-start)
 axs[1].set_xlabel('Elapsed time from formal window start (s)')
 fig.suptitle(seq+' | FGO position errors at the same GNSS1 point',fontsize=18,fontweight='bold',y=.985)
 fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.94),ncol=3,fontsize=10.5,frameon=False)
 fig.text(.12,.855,'Dynamic-only support: no prior-only initialization states; no lines across a gap or block reset.',fontsize=12,color='#596579')
 fig.text(.12,.06,'3 new OiSAM calls + 6 reused Wen/GNC identities. Oi uses its own attitude for point transport; all original denominators remain.',fontsize=11,color='#596579')
 fig.text(.12,.029,'Different sensor layers and information windows: application results cannot rank same-input solvers; reference is not independent truth.',fontsize=11,color='#596579')
 book.figure(fig,'R15_'+seq+'_FGO_position_curves','The three methods have different input layers and distinct position-error scales.',
  'All saved primary dynamic own-support H and signed-Up errors at GNSS1; log/symlog reveal scales without clipping. O3286 nonconvergence remains visible.',all_saved_valid_samples=True,reference_or_native_opens=0)
book.copy('all_36_saved_metrics',allmetrics)
strict_rows=book.rows(HERE.parents[4]/'docs/paper_rebuild/hext/FGO_REPRODUCTION_FIX_20261004/COMPARISON_TABLE.csv','8a1063fe9153cd40660887b9094043caa762840d8c1c76451343254f98747b14')
strict_rows=[r for r in strict_rows if r['method_id']=='OISAM' and r['support']=='OWN_VALID']
book.copy('earlier_strict_Oi_identity_metrics',strict_rows)
strict={r['sequence_id']:int(r['matched_epoch_count']) for r in strict_rows};assert strict=={'BY2':275,'BY2H':0,'BY2O':55}
fig,ax=plt.subplots(figsize=(14,6.1));fig.subplots_adjust(left=.18,right=.73,top=.84,bottom=.20)
rowlabels=[]
for i,(seq,method) in enumerate((s,m) for s in ['BY2','BY2H','BY2O'] for m in methods):
 own,secondary=byseq[seq];m=own[method];n=int(m['matched_epoch_count']);den=int(m['expected_epoch_count']);sec=int(secondary[method]['matched_epoch_count']);color=colors[methods.index(method)]
 ax.barh(i,100*n/den,color=color,height=.54)
 if sec>n:ax.barh(i,100*(sec-n)/den,left=100*n/den,color='#D1D6DC',height=.54,hatch='///',edgecolor='#73808A')
 ax.text(101,i,f'primary {n}/{den}'+(f'; with prior {sec}/{den}' if sec>n else ''),fontsize=11,va='center')
 if method=='OISAM':ax.scatter(100*strict[seq]/den,i,s=80,color='#CC79A7',marker='v',zorder=5,label='Earlier strict Oi identity' if i==0 else None)
 rowlabels.append(seq+' | '+method.replace('WEN_TC','Wen TC').replace('OISAM','OiSAM'))
ax.set_yticks(range(9),rowlabels);ax.invert_yaxis();ax.set_xlim(-1,101);ax.set_xlabel('Matched primary dynamic epochs / registered denominator (%)');frame(ax)
ax.legend(loc='upper left',bbox_to_anchor=(0,1.13),fontsize=12,frameon=False)
fig.suptitle('FGO | Support changes must remain visible',fontsize=18,fontweight='bold',y=.985)
fig.text(.18,.07,'Gray hatching adds prior-only states solely in the secondary position diagnostic. Primary excludes every prior-only seed.',fontsize=11,color='#596579')
fig.text(.18,.035,'Oi H/O use all fixed 3/7 source-continuous blocks; strict H0/O55 identities remain separate. Wen/GNC run once over the original batch.',fontsize=11,color='#596579')
book.figure(fig,'R16_FGO_dynamic_secondary_strict_support','Explicit gap recovery changes available support, not the earlier strict result.',
 'Nine registered full-window denominators; primary dynamic versus secondary prior-inclusive support and separate earlier strict Oi counts. No zero-error replacement for missing output.')
book.seal(__file__,new_Oi_calls=3,reused_Wen_GNC_calls=6,score_recalculation=False,old_strict_results_untouched=True)
