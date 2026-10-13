"""R4 Fig8: recorded inconsistency, covariance response and conditional heading benefit."""
from pathlib import Path
import json,shutil,sys,hashlib
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from PIL import Image
from audit_panel_alignment import require_matplotlib_panel_alignment

P=Path(__file__).resolve().parent
OLD=Path('/mnt/g/LegSA-GINS-project/V3正文精修_20261012_R3/aiding')
NATIVE=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/V3R_CONTINUATION')
for k in ['data','tables','figures','preview','qa']:(P/k).mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Liberation Sans','DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,'xtick.direction':'out','ytick.direction':'out','xtick.major.size':2.5,'ytick.major.size':2.5,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False})
BLUE='#2563EB';PURPLE='#8B5CF6';GRAY='#5F6B7A';ORANGE='#E76F51'
QA=[];SOURCES=[]

def table(name):
    src=OLD/'tables'/name;dst=P/'tables'/name
    if src.exists():shutil.copy2(src,dst)
    return pd.read_csv(dst)

core=table('CORE5951.csv');pairs=table('ALL2164_ORIGINAL_ABLATION_PAIRS.csv')
for f in ['FULL_OUTCOME55.csv','ALL_CORE_NONCOMPLETIONS.csv','ALL61_PHYSICAL_INPUT_MAP.csv','F08_ALL_513_PAIRS.csv','F08_D15_ALL_NINE.csv','F08_D38_ALL_NINE.csv','F08_D59_ALL_NINE.csv','F08_THREE_PHYSICAL_CONDITIONS.csv']:
    table(f)

def series(rid):
    src=OLD/'data'/f'{rid}.csv.gz';dst=P/'data'/f'{rid}.csv.gz'
    if src.exists():shutil.copy2(src,dst)
    d=pd.read_csv(dst);assert d.time.is_monotonic_increasing
    SOURCES.append({'run_id':rid,'kind':'retained navigation-error series','path':str(src),'rows':len(d)})
    return d

def trace(rid):
    src=NATIVE/rid/'SOURCE_AWARE_WEIGHT_TRACE.csv.gz';dst=P/'data'/f'{rid}_ACTUAL_SOURCE_TRACE.csv.gz'
    if src.exists():shutil.copy2(src,dst)
    d=pd.read_csv(dst);SOURCES.append({'run_id':rid,'kind':'actual source-weighting log','path':str(src),'rows':len(d)})
    return d

def line(ax,d,field,method):
    t=d.time.to_numpy()-66;y=d[field].to_numpy();keep=(t>=0)&(t<=120);t=t[keep];y=y[keep]
    for idx in np.split(np.arange(len(t)),np.flatnonzero(np.diff(t)>.1)+1):
        if len(idx):ax.plot(t[idx],y[idx],color=BLUE if method=='full' else PURPLE,ls='-' if method=='full' else '--',lw=.85 if method=='full' else .95,zorder=5 if method=='full' else 4,rasterized=True)

def title(ax,letter,text):ax.set_title(f'({letter}) {text}',loc='left',fontweight='bold',pad=8)

def save(fig,name):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=P/'qa'/f'{name}.alignment.json',strict=True,tolerance_pt=1.5,gutter_tolerance_pt=1.5)
    ren=fig.canvas.get_renderer();bbox=fig.bbox;texts=[t for t in fig.findobj(Text) if t.get_visible() and t.get_text()]
    clipped=[]
    for t in texts:
        b=t.get_window_extent(ren)
        if b.x0<bbox.x0-2 or b.x1>bbox.x1+2 or b.y0<bbox.y0-2 or b.y1>bbox.y1+2:clipped.append(t.get_text())
    q={'figure':name,'width_mm':fig.get_figwidth()*25.4,'height_mm':fig.get_figheight()*25.4,'min_font_pt':min(t.get_fontsize() for t in texts),'clipped_text':clipped,'data_smoothing':False,'nav_series_resampling':False}
    (P/'qa'/f'{name}.layout.json').write_text(json.dumps(q,indent=2),encoding='utf8');QA.append(q)
    fig.savefig(P/'figures'/f'{name}.pdf',dpi=600,facecolor='white')
    fig.savefig(P/'figures'/f'{name}.svg',dpi=600,facecolor='white')
    fig.savefig(P/'figures'/f'{name}.png',dpi=600,facecolor='white')
    fig.savefig(P/'figures'/f'{name}.tiff',dpi=600,facecolor='white',pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(P/'preview'/f'{name}.png',dpi=450,facecolor='white')
    Image.open(P/'preview'/f'{name}.png').convert('L').save(P/'preview'/f'{name}_gray.png')
    plt.close(fig);print('SAVED',name,flush=True)

def main_figure():
    full=series('RUN_01401');off=series('RUN_01403');tr=trace('RUN_01401');x=tr[(tr.time-66>=0)&(tr.time-66<=120)]
    # Read the other two retained condition logs to preserve the earlier evidence and its overlap.
    trace('RUN_03678');trace('RUN_05757')
    pos=x[x.source_id.eq('receiver_position')].copy();pos['reported_std_norm_m']=np.sqrt(pos.base_R_trace)
    runtime=NATIVE/'RUN_01401'
    config=runtime/'V3_RUNTIME_CONFIG.yaml'
    if config.exists():
        gnss=Path(next(t for t in config.read_text().splitlines() if t.startswith('gnsspath:')).split('"')[1])
        expected=json.loads((runtime/'V3_NATIVE_SUMMARY.json').read_text())['provider_hashes']['gnsspath']
        actual=hashlib.sha256(gnss.read_bytes()).hexdigest();assert actual==expected
        shutil.copy2(gnss,P/'data/D15_ORIGINAL_GNSS18.gnss')
    else:gnss=P/'data/D15_ORIGINAL_GNSS18.gnss';expected=actual=None
    inp=pd.read_csv(gnss,sep=r'\s+',header=None)
    nom=pd.DataFrame({'time_key':inp[0].round(6),'reported_variance_trace':(inp[[4,5,6]]**2).sum(axis=1)})
    chk=pos.assign(time_key=pos.time.round(6)).merge(nom,on='time_key',how='left',validate='one_to_one')
    assert chk.reported_variance_trace.notna().all()
    assert np.allclose(chk.base_R_trace,chk.reported_variance_trace,atol=1e-12,rtol=1e-12)
    (P/'INPUT_UNCERTAINTY_CHECK.json').write_text(json.dumps({'rows_checked':len(chk),'provider_columns_0based':[4,5,6],'quantity':'sum of squared reported position std fields equals actual base_R_trace','maximum_difference':float(abs(chk.base_R_trace-chk.reported_variance_trace).max()),'original_provider':str(gnss),'provider_sha256':actual,'recorded_sha256':expected,'hash_match':actual==expected if actual else None,'new_provider_calls':0},indent=2),encoding='utf8')
    pos[['time','residual_norm','base_R_trace','reported_std_norm_m','combined_R_scale']].to_csv(P/'tables/F08_POSITION_DIAGNOSTIC_0_120.csv',index=False)
    fig=plt.figure(figsize=(174/25.4,150/25.4));gs=fig.add_gridspec(2,2,height_ratios=[.78,1.2],left=.105,right=.98,bottom=.145,top=.86,wspace=.42,hspace=.59)
    a=fig.add_subplot(gs[0,0]);b=fig.add_subplot(gs[0,1]);c=fig.add_subplot(gs[1,:])
    a.plot(pos.time-66,pos.residual_norm,color=GRAY,lw=.7,rasterized=True)
    a.plot(pos.time-66,pos.reported_std_norm_m,color=ORANGE,ls='--',lw=1.1,rasterized=True)
    a.set(xlim=(0,120),ylim=(0,31),xlabel='Time (s)',ylabel='Distance (m)');a.set_xticks([0,60,120]);a.set_yticks([0,10,20,30]);a.set_title('(a) Position disagrees with prediction',loc='left',fontweight='bold',pad=22)
    a.text(.5,1.025,'Added position noise: σH = 3 m; σV = 5 m',transform=a.transAxes,ha='center',va='bottom',fontsize=8)
    a.text(.5,-.34,f'Dashed: reported std norm ≈ {pos.reported_std_norm_m.median():.3f} m',transform=a.transAxes,ha='center',va='top',fontsize=8,color=ORANGE)
    scales=[]
    for i,(source,label) in enumerate([('receiver_position','Position'),('go2_horizontal_velocity','Body velocity'),('dual_antenna_yaw','Heading')]):
        v=x.loc[x.source_id.eq(source),'combined_R_scale'].to_numpy();assert len(v)>0 and (v>=1).all()
        mi,q1,md,q3,ma=np.quantile(v,[0,.25,.5,.75,1])
        b.plot([mi,ma],[i,i],color=GRAY,lw=.7)
        b.plot([q1,q3],[i,i],color=GRAY,lw=4,solid_capstyle='butt')
        b.scatter(md,i,color=BLUE,s=29,zorder=4)
        b.annotate(f'×{md:.1f}',(md,i),xytext=(8,7) if source=='dual_antenna_yaw' else (0,7),textcoords='offset points',ha='left' if source=='dual_antenna_yaw' else 'center',va='bottom',fontsize=8,color=BLUE)
        scales.append({'source':source,'display_label':label,'start_elapsed_s':0,'end_elapsed_s':120,'count':len(v),'minimum':mi,'q25':q1,'median':md,'q75':q3,'maximum':ma})
    b.axvline(1,color='#B4BAC1',ls=':',lw=.65,zorder=0)
    b.set(xlim=(0,11.5),ylim=(2.5,-.65),xlabel='Covariance multiplier (×)');b.set_xticks([1,5,10]);b.set_yticks([0,1,2],['Position','Body velocity','Heading']);b.set_title('(b) Adjust each source\'s covariance',loc='left',fontweight='bold',pad=22)
    b.text(.50,1.025,'Larger covariance → lower relative influence',transform=b.transAxes,ha='center',va='bottom',fontsize=8)
    pd.DataFrame(scales).to_csv(P/'tables/F08_ACTUAL_COVARIANCE_SCALINGS.csv',index=False)
    line(c,off,'yaw_err_deg','off');line(c,full,'yaw_err_deg','full');c.axhline(0,color='#A7ADB4',ls=':',lw=.6,zorder=0)
    c.set(xlim=(0,120),ylim=(-15,170),xlabel='Time (s)',ylabel='Heading error (deg)');c.set_xticks([0,30,60,90,120]);c.set_yticks([0,50,100,150]);title(c,'c','Effect on heading in the same replay')
    c.legend(handles=[Line2D([],[],color=PURPLE,ls='--',lw=1.1,label='Without source weighting'),Line2D([],[],color=BLUE,lw=1.1,label='LegSA-GINS')],loc='upper right',handlelength=2.5,fontsize=8)
    c.text(.97,.65,'Whole-window heading RMSE\n29.80° → 2.70°',transform=c.transAxes,ha='right',va='top',fontsize=8.5)
    fig.text(.55,.042,'Weighting off → full, over 274 s: horizontal RMSE 3.17 → 3.56 m.',ha='center',fontsize=8)
    fig.text(.55,.016,'The heading benefit in this replay carries a positioning cost.',ha='center',fontsize=8)
    save(fig,'F08_heading_quality_scaling')

def support_all_conditions():
    fig,axs=plt.subplots(1,3,figsize=(174/25.4,86/25.4));fig.subplots_adjust(left=.105,right=.98,bottom=.24,top=.79,wspace=.38)
    fig.legend(handles=[Line2D([],[],color=PURPLE,marker='o',mfc='white',lw=0,label='Without source weighting'),Line2D([],[],color=BLUE,marker='o',lw=0,label='LegSA-GINS')],loc='upper center',bbox_to_anchor=(.55,.995),ncol=2,fontsize=8)
    for j,(typ,name) in enumerate([('D15','Position noise'),('D38','Heading uncertainty'),('D59','Position / velocity conflict')]):
        d=core[core.degradation_type_id.eq(typ)&core.internal_method_id.isin(['A04','F04'])];ax=axs[j]
        for i,seed in enumerate(sorted(d.seed_index.unique())):
            s=d[d.seed_index.eq(seed)].set_index('internal_method_id');v=[s.loc['A04','yaw_rmse_deg'],s.loc['F04','yaw_rmse_deg']]
            if np.isfinite(v).all():ax.plot([i-.12,i+.12],v,color='#ADB5BD',lw=.65)
            if np.isfinite(v[0]):ax.scatter(i-.12,v[0],s=20,edgecolor=PURPLE,facecolor='white',lw=.9)
            if np.isfinite(v[1]):ax.scatter(i+.12,v[1],s=20,color=BLUE)
        ax.set(xlim=(-.6,8.6),ylim=(0,None),xlabel='Replay variant');ax.set_xticks([0,2,4,6,8],['1','3','5','7','9']);title(ax,chr(97+j),name)
        if j==0:ax.set_ylabel('Whole-window yaw RMSE (deg)')
    fig.text(.55,.05,'All nine registered variants per condition; missing numerical points denote native divergence.',ha='center',fontsize=8)
    save(fig,'S_F08_all_condition_variants')

def full_support():
    # Copy existing complete time histories and all513 distribution artwork, without replacing their source data.
    for name in ['S_F08_full_heading_histories','S_quality_complete_statistics']:
        for ext in ['pdf','svg','png','tiff']:
            src=OLD/'figures'/f'{name}.{ext}'
            if src.exists():shutil.copy2(src,P/'figures'/src.name)
        for suffix in ['.png','_gray.png']:
            src=OLD/'preview'/f'{name}{suffix}'
            if src.exists():shutil.copy2(src,P/'preview'/src.name)
    for rid in ['RUN_03678','RUN_03680','RUN_05757','RUN_05759']:series(rid)
    p=pairs[pairs.module.eq('SA')];joint=p[p.joint_finite];g=joint.ablation_yaw_rmse_deg-joint.candidate_yaw_rmse_deg
    assert len(p)==541 and len(joint)==513
    summary={'registered':541,'jointly_completed':513,'lower_yaw_rmse_with_full':int((g>0).sum()),'higher_yaw_rmse_with_full':int((g<0).sum()),'median_reduction_deg':float(g.median()),'worst_increase_deg':float(-g.min()),'extra_full_completions':int((p.candidate_status.eq('COMPLETED')&~p.ablation_status.eq('COMPLETED')).sum()),'both_noncompleted':int((~p.candidate_status.eq('COMPLETED')&~p.ablation_status.eq('COMPLETED')).sum()),'definition':'reduction = weighting-off RMSE minus full RMSE; positive favours full','interpretation':'conditional robustness benefit with tail gains, not uniform typical precision improvement'}
    (P/'F08_OVERALL_PAIRED_RESULT.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    p.to_csv(P/'tables/F08_ALL541_WEIGHTING_COMPARISONS.csv',index=False)
    joint.assign(yaw_RMSE_reduction_deg=g).to_csv(P/'tables/F08_ALL513_COMPLETED_PAIRS.csv',index=False)
    return summary

if __name__=='__main__':
    main_figure();support_all_conditions();summary=full_support()
    (P/'SOURCE_MANIFEST.json').write_text(json.dumps(SOURCES,ensure_ascii=False,indent=2),encoding='utf8')
    (P/'qa/DELIVERY.json').write_text(json.dumps({'figures':QA,'new_solver_provider_evaluator_calls':0,'new_figure_layer_summaries':'Medians, IQRs and ranges of existing source covariance logs over0–120s; no navigation re-evaluation','full_results':summary},ensure_ascii=False,indent=2),encoding='utf8')
