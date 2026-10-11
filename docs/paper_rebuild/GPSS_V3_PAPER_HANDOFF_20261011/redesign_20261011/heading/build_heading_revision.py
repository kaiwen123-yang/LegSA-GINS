"""Read archived results and create publication figures; no solver/evaluator calls."""
from pathlib import Path
import sys,json,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
O=Path(__file__).parent
SK=Path('/mnt/c/Users/ykw/.codex/skills/nature-figure/scripts')
sys.path.insert(0,str(SK))
from audit_panel_alignment import require_matplotlib_panel_alignment
for sub in ['preview','qa','source_data']: (O/sub).mkdir(exist_ok=True)
SRC=Path('/mnt/g/LegSA-GINS-project/V3论文组图_20261008/focused_20261011/robot/source_data')
PROFILE=[]
def read(p,**kw):
 d=pd.read_csv(p,**kw);PROFILE.append({'path':str(p),'rows':len(d),'columns':list(d),'missing':{k:int(v) for k,v in d.isna().sum().items() if v},'sha256':hashlib.sha256(p.read_bytes()).hexdigest()});return d
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans','Arial','Helvetica'],'font.size':8.5,'axes.labelsize':9,'axes.titlesize':9,'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'xtick.labelsize':8,'ytick.labelsize':8,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'legend.frameon':False})
def save(fig,name,axes,notes):
 fig.canvas.draw()
 require_matplotlib_panel_alignment(fig,axes=axes,json_out=str(O/'qa'/f'{name}.alignment.json'),overlay_svg=str(O/'qa'/f'{name}.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(O/f'{name}.pdf',dpi=600)
 fig.savefig(O/f'{name}.svg',dpi=600)
 fig.savefig(O/f'{name}.png',dpi=600)
 fig.savefig(O/f'{name}.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
 fig.savefig(O/'preview'/f'{name}.png',dpi=300)
 (O/f'{name}.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2)+'\n')
 plt.close(fig)
def fig4():
 runs={int(p.stem.split('_')[-1].split('.')[0]):read(p) for p in SRC.glob('native_initial_yaw_*.csv.gz')}
 spec=read(SRC/'observability_spectrum_plotted.csv');eq=read(SRC/'gauge_equivalence_summary.csv');wins=read(SRC/'input_selected_windows.csv');rank=read(SRC/'observability_rank_all_thresholds.csv')
 col={-150:'#B8B8B8',-100:'#D55E00',-50:'#B8B8B8',0:'#0072B2',50:'#B8B8B8',100:'#009E73',150:'#B8B8B8'}
 ls={-150:':',-100:'--',-50:'-.',0:'-',50:(0,(3,1,1,1)),100:'-.',150:(0,(6,2))}
 fig,axs=plt.subplots(2,2,figsize=(174/25.4,149/25.4))
 fig.subplots_adjust(left=.105,right=.97,bottom=.115,top=.835,wspace=.37,hspace=.54)
 a,b,c,d=axs.flat
 titles=['Different global directions','Same path after one rotation','Same change in heading','Unresolved global freedoms']
 for ax,letter,title in zip(axs.flat,'abcd',titles):ax.set_title(f'({letter}) {title}',loc='left',pad=8);ax.tick_params(length=3)
 maxdiff=0
 anchor=runs[0][['local_x_m','local_y_m']].to_numpy()
 # All seven saved trajectories are plotted; alignment removes only the known initial yaw.
 for yaw,f in sorted(runs.items()):
  p=f[['local_x_m','local_y_m']].to_numpy();ang=np.deg2rad(yaw);rot=np.array([[np.cos(ang),np.sin(ang)],[-np.sin(ang),np.cos(ang)]]);q=p@rot.T
  maxdiff=max(maxdiff,float(np.linalg.norm(q-anchor,axis=1).max()))
  main=yaw in [-100,0,100];lw=1.05 if main else .6;zo=4 if main else 1
  a.plot(*p.T,color=col[yaw],ls=ls[yaw],lw=lw,zorder=zo,rasterized=True)
  b.plot(*q.T,color=col[yaw],ls=ls[yaw],lw=lw,zorder=zo,rasterized=True)
  a.plot(*p[-1],marker='o',ms=3,color=col[yaw],zorder=zo)
 for ax in [a,b]:
  box=ax.get_position();ratio=(box.width*174)/(box.height*149)
  ax.set(xlim=(-145*ratio,145*ratio),ylim=(-145,145),xlabel='Local x (m)',ylabel='Local y (m)');ax.set_xticks([-100,0,100]);ax.set_yticks([-100,0,100]);ax.plot(0,0,'k*',ms=6,zorder=10)
 b.text(.98,.05,'7 paths overlap',transform=b.transAxes,ha='right',va='bottom',color='#0072B2',fontsize=8.5)
 fig.text(.54,.897,'Remove each initial yaw',ha='center',fontsize=8.5,color='#333333')
 arrow=FancyArrowPatch((.435,.884),(.645,.884),transform=fig.transFigure,arrowstyle='-|>',mutation_scale=10,color='#555555',lw=.9);fig.add_artist(arrow)
 w=wins[wins.window_id.eq('WIN003')].iloc[0];lo=int(w.start_row);hi=int(w.end_row)+1
 for yaw,f in sorted(runs.items()):
  t=f.elapsed_s.to_numpy()[lo:hi];v=f.unwrapped_yaw_deg.to_numpy()[lo:hi];c.plot(t-t[0],v-v[0],color=col[yaw],ls=ls[yaw],lw=1.2 if yaw==0 else .8,zorder=5 if yaw==0 else 2)
 c.set(xlim=(-.005,.225),ylim=(-.15,4.4),xlabel='Time in selected interval (s)',ylabel='Heading change (deg)');c.set_xticks([0,.1,.2]);c.set_yticks([0,2,4]);c.text(.04,.91,'Same IMU + foot-contact inputs',transform=c.transAxes,fontsize=8.1)
 # Compact rank result replaces the difficult singular-spectrum panel. All spectra remain source data.
 counts=[]
 for wid,g in spec.groupby('window'):
  ncontact=int(g.contact_count.iloc[0]);n=int((g.sigma_over_sigma_max<1e-9).sum());counts.append({'window':wid,'contacts':ncontact,'unresolved':n,'state_dimension':len(g)})
 for i,r in enumerate(counts):d.vlines(i,0,r['unresolved'],color='#D8D8D8',lw=3);d.plot(i,r['unresolved'],'o' if r['contacts']==4 else 's',mfc='white',mec='#333333',ms=6,mew=1)
 d.set(xlim=(-.6,4.6),ylim=(0,5.25),ylabel='Unresolved dimensions',xlabel='Preselected contact interval');d.set_xticks(range(5),['1','2','3','4','5']);d.set_yticks([0,2,4]);d.axhline(4,color='#999999',ls=':',lw=.65,zorder=0)
 d.text(.5,.92,'3 translations + 1 global yaw',ha='center',transform=d.transAxes,fontsize=8.2)
 d.legend(handles=[Line2D([],[],marker='o',mfc='white',color='#333333',ls='',label='4 contacts'),Line2D([],[],marker='s',mfc='white',color='#333333',ls='',label='2 contacts')],loc='upper center',bbox_to_anchor=(.5,-.27),ncol=2,fontsize=8,columnspacing=.8)
 fig.legend(handles=[Line2D([],[],color=col[y],ls=ls[y],lw=1.2,label=f'{y:+d}°' if y else '0°') for y in [-100,0,100]]+[Line2D([],[],color='#B8B8B8',lw=.8,label='Other four initial yaws')],loc='upper center',bbox_to_anchor=(.53,.99),ncol=4,columnspacing=.9,title='Identical IMU/contact inputs; different initial headings',title_fontsize=8.5)
 notes={'claim':'The same proprioceptive inputs determine equivalent relative motion in different global headings.','native_runs':7,'native_rows':sum(len(f) for f in runs.values()),'alignment':'Remove exactly the known initial z rotation; no scale, translation, temporal, or fitted-yaw alignment.','max_display_horizontal_difference_m':maxdiff,'window':'WIN003 chosen from inputs in previous experiment; all 43 rows retained','rank_threshold':1e-9,'rank_counts':counts,'all_spectra_preserved':True,'new_scientific_calls':0,'figure_width_mm':174,'figure_height_mm':149}
 pd.DataFrame(counts).to_csv(O/'source_data/F4_rank_counts.csv',index=False);spec.to_csv(O/'source_data/F4_full_spectrum.csv',index=False);eq.to_csv(O/'source_data/F4_equivalence.csv',index=False)
 save(fig,'F4_relative_motion_global_heading',list(axs.flat),notes)
def fig5():
 R=Path('/mnt/g/LegSA-GINS-project/V3五问题论文组图_20261011/heading');own=read(O/'source_data/INPUT_HEADING_SUMMARY.csv');far=read(R/'tables/FAR_PAR_ALL_THREE_TRIALS.csv')
 seqs=['BY2','BY2H','BY2O'];names=['Nominal walking','Large body motion','Antenna obstruction'];dur=[274,270,377];start=[66,413,3186]
 styles={'V0':('#D55E00','s','RTKLIB default'),'V0E':('#D55E00','o','RTKLIB + BRDC'),'V1':('#D55E00','^','RTKLIB + constellations'),'V2':('#D55E00','v','RTKLIB fix-and-hold'),'EXT01':('#009E73','D','C-LAMBDA'),'EXT02':('#8B5A99','P','C-WLS'),'EXT03':('#555555','X','DD-KF')}
 fig,axs=plt.subplots(2,3,figsize=(174/25.4,160/25.4),gridspec_kw={'height_ratios':[1.45,1]})
 fig.subplots_adjust(left=.115,right=.97,bottom=.105,top=.745,wspace=.32,hspace=.66)
 summary=[];support=[]
 for j,(seq,name) in enumerate(zip(seqs,names)):
  ax=axs[0,j];z=own[own.sequence.eq(seq)].iloc[0]
  ax.plot([z.coverage_percent,z.accepted_coverage_percent],[z.rmse_deg,z.accepted_rmse_deg],color='#0072B2',lw=1)
  ax.scatter(z.coverage_percent,z.rmse_deg,s=43,facecolors='white',edgecolors='#0072B2',marker='o',lw=1.2,zorder=8)
  ax.scatter(z.accepted_coverage_percent,z.accepted_rmse_deg,s=68,color='#0072B2',marker='*',lw=.7,zorder=9)
  summary.extend([{'sequence':seq,'method':'Position-derived input','rmse_deg':z.rmse_deg,'available':int(z.available),'denominator':int(z.denominator),'coverage_percent':z.coverage_percent,'scored':int(z.scored),'level':'input-valid direction'},{'sequence':seq,'method':'Used heading observations','rmse_deg':z.accepted_rmse_deg,'available':int(z.accepted),'denominator':int(z.denominator),'coverage_percent':z.accepted_coverage_percent,'scored':int(z.accepted_scored),'level':'input direction selected by native update, not posterior'}])
  raw=read(R/f'data/{seq}_all_methods_all_window_epochs.csv.gz');rtk={}
  for key,(color,marker,label) in styles.items():
   if key.startswith('V'):data=read(R/f'data/{seq}_{key}_full_saved_heading.csv.gz');rtk[key]=data
   else:data=raw[raw.method_id.eq(key)]
   valid=data.valid.eq(1);err=data.loc[valid,'error_valid_deg'].dropna();n=int(valid.sum());cov=100*n/len(data);rmse=float(np.sqrt(np.mean(err**2)))
   ax.scatter(cov,rmse,s=32,marker=marker,edgecolor=color,facecolor='white' if key.startswith('V') else color,lw=1,zorder=5)
   summary.append({'sequence':seq,'method':label,'rmse_deg':rmse,'available':n,'denominator':len(data),'coverage_percent':cov,'scored':len(err),'level':'RTKLIB fixed output' if key.startswith('V') else ('directional candidate, no acceptance test' if key in ['EXT01','EXT02'] else 'valid DD-KF output')})
  ax.set(xlim=(-4,106),ylim=(1.5,160),yscale='log',xlabel='New-output coverage (%)');ax.set_xticks([0,50,100]);ax.set_yticks([2,5,20,100],[2,5,20,100]);ax.minorticks_off();ax.grid(axis='y',color='#E5E5E5',lw=.45);ax.set_title(f'({chr(97+j)}) {name}',loc='left',pad=9)
  ax.set_ylabel('Heading RMSE (deg)' if j==0 else '')
  # Three information layers on their actual native timestamps.
  bx=axs[1,j];inp=read(O/f'source_data/{seq}_input_heading_figure_match.csv.gz');v0=rtk['V0'];times=[inp.loc[inp.input_heading_valid,'elapsed_s'],inp.loc[inp.accepted,'elapsed_s'],v0.loc[v0.valid.eq(1),'t_rel_s']-start[j]];cc=['#9DB8C9','#0072B2','#D55E00'];labels=['Input','Used','RTKLIB']
  for k,(tt,c) in enumerate(zip(times,cc)):
   y=2-k;bx.plot([0,dur[j]],[y,y],color='#E6E6E6',lw=6,zorder=0);bx.scatter(tt,np.full(len(tt),y),marker='|',s=31,lw=.7,color=c)
  bx.set(xlim=(0,dur[j]),ylim=(-.65,2.7),xlabel='Time (s)');bx.set_yticks([2,1,0],labels if j==0 else ['','','']);bx.set_xticks([0,100,200] if j<2 else [0,150,300]);bx.set_title(f'({chr(100+j)}) Direction availability',loc='left',pad=9)
  bx.text(.98,.93,f"{int(z.accepted)}/{int(z.denominator)} used",transform=bx.transAxes,ha='right',fontsize=8,color='#0072B2')
  fr=far[far.sequence.eq(seq)]
  for _,f in fr.iterrows():summary.append({'sequence':seq,'method':'FAR' if f.policy_identity=='FAR_ALL_AMBIGUITIES' else 'PAR','rmse_deg':np.nan,'available':0,'denominator':int(f.expected_row_count),'coverage_percent':0.,'scored':0,'level':'accepted solution; full native recorded domain'})
 handles=[Line2D([],[],marker='o',mfc='white',mec='#0072B2',ls='',ms=6,label='Proposed: input heading'),Line2D([],[],marker='*',color='#0072B2',ls='',ms=8,label='Proposed: used heading')]
 handles += [Line2D([],[],marker=m,mfc='white' if k.startswith('V') else c,mec=c,ls='',ms=5.5,label=l) for k,(c,m,l) in styles.items()]
 fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,.992),ncol=3,fontsize=8,columnspacing=1,handletextpad=.5,labelspacing=.75)
 fig.text(.53,.79,'FAR and PAR: no accepted solution in all three trials; heading error N/A',ha='center',fontsize=8,color='#555555')
 pd.DataFrame(summary).to_csv(O/'source_data/F5_ALL_DIRECTION_ROUTES.csv',index=False)
 notes={'claim':'Position-derived direction and native quality selection achieve a different accuracy-availability balance than the tested direct dual-antenna processing routes.','no_posterior_yaw_in_figure':True,'all_rtklib_configurations':list(styles)[:4],'raw_methods':list(styles)[4:],'FAR_PAR':'Zero accepted in all original runs; own full native domains 1509/1423/2231, RMSE NA. They cannot be assigned an artificial error at y=0.','observation_statistics':'New figure-layer derived statistics; see INPUT_HEADING_MATCH_PROTOCOL.json. Saved external errors unchanged.','selection':'Used heading error is conditional on the native estimator decision; it is a selected observation diagnostic, not stand-alone external AR integer fixing.','fairness':'Same real recordings/formal windows but different processing inputs, validity tests, native timestamp grids and reference-supported error counts. Full joint support was not imposed.','new_solver_evaluator_provider_calls':0,'figure_width_mm':174,'figure_height_mm':160}
 save(fig,'F5_heading_accuracy_availability',list(axs.flat),notes)
if __name__=='__main__':
 fig4();fig5();(O/'SOURCE_PROFILE.json').write_text(json.dumps(PROFILE,ensure_ascii=False,indent=2))
