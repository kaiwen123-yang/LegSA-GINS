"""Plot already saved FGO GNSS1 trajectories/yaw; no new reference access."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from plot_utils import Book,setup,frame,np,plt
import pandas as pd
HERE=Path(__file__).resolve().parent
S=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z')
book=Book(HERE);setup();complete=book.json(S/'ALL_OFFLINE_COMPLETE.json')
assert complete['all_three_offline_complete'] and complete['native_online_reference_opens']==0
pins={s['sequence']:s['output_hashes'] for s in complete['sequences']}
methods=['OISAM','WEN_TC','GNC'];colors=['#0072B2','#D55E00','#009E73'];labels=['OiSAM: RTK + IMU','Wen TC: code + AHRS/IMU','GNC: code + Doppler']
yawdata={};metadata={}
def local_ne(d,anchor,prefix=''):
 lat,lon,h=anchor;la,lo=np.deg2rad([lat,lon]);a=6378137.;e2=6.6943799901413165e-3;n=a/np.sqrt(1-e2*np.sin(la)**2)
 x0=np.array([(n+h)*np.cos(la)*np.cos(lo),(n+h)*np.cos(la)*np.sin(lo),(n*(1-e2)+h)*np.sin(la)])
 xyz=np.array([d[prefix+k].astype(float).to_numpy() for k in ['x_ecef_m','y_ecef_m','z_ecef_m']]).T-x0
 north=np.array([-np.sin(la)*np.cos(lo),-np.sin(la)*np.sin(lo),np.cos(la)])
 east=np.array([-np.sin(lo),np.cos(lo),0.])
 return xyz@east,xyz@north
def partition(t,blocks=None):
 cuts=np.diff(t)>1.01
 if blocks is not None:cuts |= blocks[1:]!=blocks[:-1]
 return np.split(np.arange(len(t)),np.flatnonzero(cuts)+1)
for seq,start,end,expected in [('BY2',66,340,275),('BY2H',413,683,271),('BY2O',3186,3563,378)]:
 root=S/'evaluation'/seq
 j=book.json(root/'EVALUATION.json');assert book.inputs[-1]['file_sha256']==pins[seq]['EVALUATION.json']
 anchor=j['anchor_llh_deg_m'];metadata[seq]={'anchor_llh_deg_m':anchor,'frame':'fixed WGS84 East/North display, not trajectory alignment','reference_clean_epoch_count':j['reference_clean_epoch_count']}
 mr=book.rows(root/'METRICS.csv',pins[seq]['METRICS.csv']);own={r['method_id']:r for r in mr if r['support_role']=='PRIMARY_DYNAMIC_ONLY' and r['support']=='OWN_VALID'}
 fig,ax=plt.subplots(figsize=(14,5.8));fig.subplots_adjust(left=.11,right=.98,top=.79,bottom=.20)
 for method,color,label in zip(methods,colors,labels):
  name=method+'_PRIMARY_DYNAMIC_ONLY_TRAJECTORY.csv';d=book.copy(seq+'_'+method+'_saved_GNSS1_trajectory',book.rows(root/name,pins[seq][name]))
  if method=='OISAM':
   assert len(d)==expected
   re,rn=local_ne(d,anchor,'truth_');ax.plot(re,rn,color='#333333',lw=1.1,ls='--',label='Saved fused reference',zorder=1)
   ax.scatter([re[0],re[-1]],[rn[0],rn[-1]],color='#333333',s=35,marker='s',zorder=4)
   name=method+'_PRIMARY_DYNAMIC_ONLY_ERRORS.csv';er=book.copy(seq+'_Oi_all_saved_yaw_and_status',book.rows(root/name,pins[seq][name]))
   yawdata[seq]=(er,own[method],start,end)
   block_by_time=dict(zip(er.time,er.block_id))
  good=(d.valid=='1')&(d.prior_only=='0')&pd.to_numeric(d.x_ecef_m,errors='coerce').notna();d=d.loc[good].copy()
  assert len(d)==int(own[method]['matched_epoch_count'])
  e,n=local_ne(d,anchor);t=d.time.astype(float).to_numpy()
  blocks=np.array([block_by_time[x] for x in d.time]) if method=='OISAM' else None
  for k,part in enumerate(partition(t,blocks)):
   ax.plot(e[part],n[part],color=color,lw=.9,marker='.',ms=1.9,label=(f'{label} ({len(d)}/{expected})' if k==0 else None),zorder=2)
 ax.set_xlabel('East (m)');ax.set_ylabel('North (m)');ax.set_aspect('equal',adjustable='box');frame(ax)
 fig.suptitle(seq+' | Saved FGO trajectories at GNSS1',fontsize=18,fontweight='bold',y=.985)
 fig.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.94),ncol=4,fontsize=10.5,frameon=False)
 fig.text(.11,.855,'All saved dynamic-valid positions; equal metre scales; no rotation, translation, scale fitting or new interpolation.',fontsize=12,color='#596579')
 fig.text(.11,.07,'Oi uses its estimated attitude for GNSS1 transport; gaps and block resets are not connected. Fused reference is not independent truth.',fontsize=11,color='#596579')
 fig.text(.11,.035,'Later engineering diagnostic: 3 new Oi calls, 6 reused Wen/GNC identities. These are not original V3 midpoint trajectories or same-input rankings.',fontsize=11,color='#596579')
 book.figure(fig,'R17_'+seq+'_FGO_GNSS1_trajectory','The saved outputs follow distinct trajectories and have unequal input layers.',
  'Fixed saved anchor ECEF to East/North display only; all primary dynamic samples retain original support and block gaps. Reference path comes from saved matched XYZ columns.',equal_aspect=True,alignment_fitting=False,new_interpolation=False)
fig,axs=plt.subplots(3,1,figsize=(14,6.2))
fig.subplots_adjust(left=.12,right=.98,top=.80,bottom=.20,hspace=.65)
for ax,(seq,(d,m,start,end)) in zip(axs,yawdata.items()):
 good=(d.valid=='1')&(d.prior_only=='0')&pd.to_numeric(d.yaw_err_deg,errors='coerce').notna();d=d.loc[good].copy()
 t=d.time.astype(float).to_numpy()-start;y=d.yaw_err_deg.astype(float).to_numpy();blocks=d.block_id.to_numpy()
 for part in partition(t,blocks):ax.plot(t[part],y[part],color='#0072B2',lw=.85,marker='.',ms=2)
 ax.axhline(0,color='#7B8590',lw=.6);frame(ax);ax.set_xlim(0,end-start);ax.set_ylabel(seq,fontsize=14);ax.tick_params(axis='x',labelsize=12)
 ax.set_title(f'{len(d)}/{m["expected_epoch_count"]}; saved RMSE {float(m["yaw_rmse_deg"]):.3f}°',fontsize=11,loc='left',pad=4)
 if seq=='BY2O':
  idx=(d.native_status=='OK_USABLE_NONLINEAR_ITERATION_LIMIT').to_numpy();assert idx.sum()==1
  ax.scatter(t[idx],y[idx],s=65,marker='x',color='#CC79A7',zorder=5)
axs[-1].set_xlabel('Elapsed time from each formal window start (s)')
fig.suptitle('OiSAM | Only its own estimated yaw is scored',fontsize=18,fontweight='bold',y=.985)
fig.text(.12,.867,'Yaw error in degrees; dynamic-only support. Wen TC/GNC provide no independently estimated attitude result.',fontsize=12,color='#596579')
fig.text(.12,.065,'All saved yaw errors; no prior-only seeds, gap bridges or smoothing. O3286 marker retains usable but nonconverged status.',fontsize=11,color='#596579')
fig.text(.12,.032,'Oi uses 1/3/7 predeclared source-continuous blocks, not a single uninterrupted H/O run. Different inputs prevent same-input ranking.',fontsize=11,color='#596579')
book.figure(fig,'R18_Oi_own_estimated_yaw','Only OiSAM estimates an attitude state in this comparison.',
 'Full saved dynamic yaw errors for all three later Oi runs, each on its own formal-window clock; no Wen/GNC proxy yaw or reference-fed attitude score.')
book.seal(__file__,display_coordinate_metadata=metadata,no_original_V3_trajectory_substitution=True,new_Oi_calls=3,reused_Wen_GNC_calls=6)
