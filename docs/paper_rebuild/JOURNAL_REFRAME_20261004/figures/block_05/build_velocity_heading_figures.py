"""Plot saved original V3 errors and native update modes; no science execution."""
from pathlib import Path
import sys,json,collections
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from plot_utils import Book,setup,frame,line,sha,np,plt
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
V=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')
book=Book(HERE);setup()
ix=book.json(REPO/'docs/paper_rebuild/v3/uncertainty/UA01_INPUT_SHA256.json')['inputs']
rows=book.rows(V/'07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv')
summary={(r['sequence_id'],r['configuration_id']):r for r in rows}
book.copy('original_natural_velocity_pair_metrics',[summary[(s,m)] for s in ['BY2','BY2H','BY2O'] for m in ['F02','F03']],
 ['run_id','sequence_id','configuration_id','horizontal_rmse_m','yaw_rmse_deg','matched_epoch_count','output_epoch_count'])
windows={'BY2':(66,340),'BY2H':(413,683),'BY2O':(3186,3563)}
datasets={};config_diffs=[]
for seq,(start,end) in windows.items():
 fig,axs=plt.subplots(2,1,figsize=(14,6.5),sharex=True)
 fig.subplots_adjust(left=.12,right=.98,top=.78,bottom=.18,hspace=.26)
 for method,color,label in [('F02','#D55E00','F02: fixed yaw; RV off'),('F03','#0072B2','F03: gated yaw; RV on')]:
  run=f'RUN_0000{method[-1]}' if seq=='BY2' else f'SEQUENCE_{seq}_{method}'
  entry=next(x for x in ix if '/'+run+'/' in x['path'] and '/v3/' in x['path'] and 'error_series' in x['path'])
  erows=book.rows(entry['path'],entry['sha256'])
  d=book.copy(seq+'_'+method+'_full_saved_errors',erows,['time','horizontal_err_m','yaw_err_deg']).apply(__import__('pandas').to_numeric)
  s=summary[(seq,method)];assert len(d)==int(s['matched_epoch_count'])==int(s['output_epoch_count'])
  t=d.time.to_numpy()-start
  for ax,col,rmse in [(axs[0],'horizontal_err_m','horizontal_rmse_m'),(axs[1],'yaw_err_deg','yaw_rmse_deg')]:
   line(ax,t,d[col].to_numpy(),color=color,lw=.72,label=f'{label} | saved RMSE {float(s[rmse]):.3f}'+(' m' if ax is axs[0] else '°'))
  datasets[(seq,method)]=d
  cp=V/'03_NATIVE'/('' if seq=='BY2' else 'V3R_CONTINUATION')/run/'V3_RUNTIME_CONFIG.yaml'
  raw=cp.read_bytes();assert cp.read_bytes()==raw
  book.inputs.append({'path':str(cp),'file_sha256':sha(raw),'bytes':len(raw),'unchanged_after_read':True})
  datasets[(seq,method,'config')]=raw.decode().splitlines()
 effective=[]
 for method in ['F02','F03']:
  run=f'RUN_0000{method[-1]}' if seq=='BY2' else f'SEQUENCE_{seq}_{method}'
  mp=V/'03_NATIVE'/('' if seq=='BY2' else 'V3R_CONTINUATION')/run/'RUN_MANIFEST.json'
  manifest=book.json(mp)
  assert manifest['enable_basic_dual_yaw_baseline']==(method=='F02')
  assert manifest['yaw_scheme_C_enabled']==(method=='F03')
  assert manifest['basic_dual_yaw_fixed_std_deg']==2.933193
  assert (manifest['receiver_velocity_update_count']>0)==(method=='F03')
  effective.append({'method':method,'path':str(mp),'sha256':sha(mp.read_bytes()),**{k:manifest[k] for k in ['algorithm_id','measurement_update_order','enable_basic_dual_yaw_baseline','yaw_scheme_C_enabled','basic_dual_yaw_fixed_std_deg','receiver_velocity_update_count','yaw_NORMAL','yaw_DOWNWEIGHT','yaw_REJECT']}})
 a=datasets[(seq,'F02','config')];b=datasets[(seq,'F03','config')]
 assert len(a)==len(b)
 diffs=[{'line':i+1,'F02':x,'F03':y} for i,(x,y) in enumerate(zip(a,b)) if x!=y]
 assert [x['F02'] for x in diffs if x['F02'].startswith('enable_receiver_velocity:')]==['enable_receiver_velocity: false']
 assert [x['F03'] for x in diffs if x['F03'].startswith('enable_receiver_velocity:')]==['enable_receiver_velocity: true']
 assert all(x['F02'].split(':')[0] in ['run_id','run_label','algorithm_id','outputpath','enable_receiver_velocity','ablation_variant'] for x in diffs)
 config_diffs.append({'sequence':seq,'diffs':diffs,'algorithm_id_is_active_branch':True,'comparison_type':'JOINT_RV_AND_YAW_HANDLING_STRUCTURAL_CHANGE','isolated_receiver_velocity_effect_identifiable':False,'effective_manifest_evidence':effective})
 for ax,ylabel in zip(axs,['Horizontal error (m)','Yaw error (°)']):
  frame(ax);ax.set_ylabel(ylabel);ax.set_xlim(0,end-start)
  metric='horizontal_rmse_m' if ax is axs[0] else 'yaw_rmse_deg';unit='m' if ax is axs[0] else '°'
  ax.set_title(f"Saved RMSE: F02 {float(summary[(seq,'F02')][metric]):.3f} {unit}; F03 {float(summary[(seq,'F03')][metric]):.3f} {unit}",loc='left',fontsize=11,color='#596579',pad=5)
 axs[1].set_xlabel('Elapsed time from formal window start (s)')
 fig.suptitle(seq+' | Joint velocity and heading-handling contrast',fontsize=18,fontweight='bold',y=.985)
 fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.927),ncol=2,fontsize=11.5,frameon=False)
 fig.text(.12,.855,'RV and yaw weighting/gating both change; these curves do not isolate the RV effect.',fontsize=12,color='#596579')
 fig.text(.12,.045,f'Original F02/F03 cohort, common dual-heading initialization; matched/output {len(d)}/{len(d)}. Joint changes are not uniformly beneficial.',fontsize=11,color='#596579')
 book.figure(fig,'R11_'+seq+'_receiver_velocity_toggle','The joint velocity and heading-handling contrast has sequence-dependent outcomes.',
  'Full saved F02/F03 H/yaw curves; F02 uses fixed 2.933193-degree yaw weighting without Scheme-C, while F03 enables RV and quality/residual yaw gating. This is not a single-factor RV contrast. No rescore, smoothing or interpolation.',source_identity='ORIGINAL_V3',all_saved_samples=True,comparison_type='JOINT_RV_AND_YAW_HANDLING_STRUCTURAL_CHANGE',isolated_receiver_velocity_effect_identifiable=False,legacy_filename_locator_only=True)
mode_rows=book.rows(V/'03_NATIVE/RUN_00004/PORT_GNSS_UPDATE_TRACE.csv.gz')
md=book.copy('BY2_all_1369_native_heading_update_modes',mode_rows)
counts=dict(collections.Counter(md.yaw_mode));assert counts=={'NORMAL':1225,'DOWNWEIGHT':123,'REJECT':21};assert set(md.yaw_residual_deg)=={''}
# Saved original Proposed error curve, copied directly without interpolation.
entry=next(x for x in ix if '/RUN_00004/' in x['path'] and '/v3/' in x['path'] and 'error_series' in x['path'])
d=book.copy('BY2_Proposed_yaw_errors',book.rows(entry['path'],entry['sha256']),['time','yaw_err_deg']).apply(__import__('pandas').to_numeric)
fig,axs=plt.subplots(2,1,figsize=(14,6.5),sharex=True,gridspec_kw={'height_ratios':[2,1]})
fig.subplots_adjust(left=.13,right=.98,top=.85,bottom=.18,hspace=.14)
line(axs[0],d.time.to_numpy()-66,d.yaw_err_deg.to_numpy(),color='#0072B2',lw=.8)
axs[0].set_ylabel('Proposed yaw error (°)')
for i,(mode,color) in enumerate([('NORMAL','#009E73'),('DOWNWEIGHT','#E69F00'),('REJECT','#D55E00')]):
 t=md.loc[md.yaw_mode==mode,'gnss_time'].astype(float).to_numpy()-66
 axs[1].scatter(t,np.full(len(t),i),marker='|',s=115,color=color,label=mode)
axs[1].set_yticks([0,1,2],['Normal 1225','Downweight 123','Reject 21']);axs[1].set_ylim(-.5,2.5)
for ax in axs:frame(ax);ax.set_xlim(0,274)
axs[1].set_xlabel('Elapsed time from formal window start (s)')
fig.suptitle('BY2 | Actual heading-update decisions',fontsize=18,fontweight='bold',y=.985)
fig.text(.13,.065,'All 1369 native GNSS update events; acceptance is an algorithm decision, not a truth-quality label.',fontsize=11,color='#596579')
fig.text(.13,.033,'The saved yaw innovation field is empty: no reconstructed threshold curve or invented residual is plotted.',fontsize=11,color='#596579')
book.figure(fig,'R12_BY2_native_heading_decisions','Normal/downweight/reject decisions occurred in the original native run.',
 '1369 saved categorical native decisions alongside all saved Proposed yaw errors; no inferred innovation or causal attribution.')
(HERE/'CONFIG_DIFF_EVIDENCE.json').write_text(json.dumps(config_diffs,ensure_ascii=False,indent=2)+'\n')
# SVG text whitespace normalization only; no coordinate/data changes.
for record in book.figures:
 for export in record['exports']:
  if export['path'].endswith('.svg'):
   sp=HERE/export['path'];sp.write_text('\n'.join(s.rstrip() for s in sp.read_text().splitlines())+'\n')
   export.update(sha256=sha(sp.read_bytes()),bytes=sp.stat().st_size)
book.seal(__file__,heading_native_event_counts=counts,original_evaluation_identity_preserved=True,editorial_rv_confounding_correction=True,no_isolated_RV_causal_claim=True)
