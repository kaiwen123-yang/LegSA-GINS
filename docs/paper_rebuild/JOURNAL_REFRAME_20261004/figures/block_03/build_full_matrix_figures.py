"""Complete original CORE/ADD distributions and saved paired contrasts, no rescore."""
import sys,csv,collections,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from plot_utils import Book,setup,plt,np,pd,frame
setup();b=Book(HERE)
V=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/07_AGGREGATE')
METHODS=['F04','A03','A04','A05','A06','A07','A08','A09','F01','F02','F03']
NAMES=['Proposed','No raw Doppler','No source weighting','No roll/pitch prior','No body-velocity prior',
       'No robot priors','No weighting + robot priors','No Doppler + robot priors','No online dual heading',
       'Dual heading; receiver velocity off','Dual heading + receiver velocity']
def canvas(title,sharey=True):
    fig,axes=plt.subplots(1,2,figsize=(14,6.5),sharey=sharey)
    fig.subplots_adjust(left=.255,right=.985,top=.86,bottom=.2,wspace=.2)
    fig.suptitle(title,x=.045,ha='left',y=.98,fontsize=18,fontweight='bold')
    return fig,axes
def labels(ax): ax.set_yticks(np.arange(len(METHODS)),NAMES,fontsize=12);ax.set_ylim(len(METHODS)-.5,-.7)

def main():
    rows=b.rows(V/'CORE_541_SUMMARY_V3.csv');b.copy('CORE_541_all_77_summary_rows',rows)
    fig,axes=canvas('Original CORE | Typical error, tail error, and failures for all 11 configurations')
    for ax,key,xlabel in zip(axes,['horizontal_rmse_m','yaw_rmse_deg'],['Horizontal RMSE (m)','Yaw RMSE (°)']):
        for i,m in enumerate(METHODS):
            r=next(x for x in rows if x['method_id']==m and x['metric']==key)
            xs=[float(r[k]) for k in ['median','p95','maximum']]
            ax.plot(xs,[i]*3,color='#ADB5BF',lw=1.6,zorder=1)
            for value,marker,color in zip(xs,['o','s','|'],['#0072B2','#D55E00','#374151']):
                ax.scatter(value,i,marker=marker,color=color,s=70 if marker!='|' else 180,zorder=3)
        ax.set_xscale('log');ax.set_xlabel(xlabel);frame(ax)
    den=[next(r for r in rows if r['method_id']==m and r['metric']=='horizontal_rmse_m') for m in METHODS]
    axes[0].set_yticks(np.arange(len(METHODS)),[n+f"  [{r['finite_count']}/541]" for n,r in zip(NAMES,den)],fontsize=12)
    axes[0].set_ylim(len(METHODS)-.5,-.7)
    from matplotlib.lines import Line2D
    legend=[Line2D([],[],color=c,marker=m,ls='',markersize=8,label=l) for m,c,l in [('o','#0072B2','Median'),('s','#D55E00','95th percentile'),('|','#374151','Maximum')]]
    fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.66,.93),ncol=3,frameon=False,fontsize=13)
    fig.text(.045,.055,'541 registered cases per configuration; finite-support fractions are printed beside labels. Log scales retain every saved tail endpoint.\nThese are across-case RMSE summaries, not within-run error percentiles or independent natural field trials.',fontsize=11,color='#4B5563')
    b.figure(fig,'R05_CORE_all_11_error_tails','The original full matrix has substantial tails and incomplete finite support.',
             'All 11 configurations, each 541 registered cases, use existing median/p95/maximum RMSE summary tokens. Missing/failed cases are not inserted at zero; complete failure types shown separately in R07.')

    pairrows=b.rows(V/'PAIRWISE_CASE_LEVEL_V3.csv')
    comps=['full_vs_no_RD','full_vs_no_SA','full_vs_no_RP','full_vs_no_HV'];pnames=['Raw Doppler','Source weighting','Roll/pitch prior','Body-velocity prior']
    selected=[r for r in pairrows if r['comparison'] in comps and r['metric_name'] in ['horizontal_rmse_m','yaw_rmse_deg']]
    b.copy('all_saved_single_module_pairs',selected)
    summaries=b.rows(V/'PAIRWISE_SUMMARY_V3.csv');selected_summary=[r for r in summaries if r['comparison'] in comps and r['scope']=='overall' and r['metric_name'] in ['horizontal_rmse_m','yaw_rmse_deg']];b.copy('saved_overall_pair_summary',selected_summary)
    fig,axes=canvas('Original CORE | Every common-finite single-module contrast')
    fig.subplots_adjust(left=.16,right=.985,top=.86,bottom=.22,wspace=.27)
    for ax,key,xlabel,linthresh in zip(axes,['horizontal_rmse_m','yaw_rmse_deg'],['Δ horizontal RMSE (m)','Δ yaw RMSE (°)'],[.001,.01]):
        ticks=[]
        for i,(comp,name) in enumerate(zip(comps,pnames)):
            rr=sorted([r for r in selected if r['comparison']==comp and r['metric_name']==key],key=lambda r:r['case_id'])
            sr=next(r for r in selected_summary if r['comparison']==comp and r['metric_name']==key)
            assert len(rr)==int(sr['paired_sample_count'])
            # Deterministic vertical display offsets only; horizontal delta is exact saved token.
            offsets=((np.arange(len(rr))%19)-9)*.018
            ax.scatter([float(r['delta_candidate_minus_reference']) for r in rr],i+offsets,s=11,alpha=.38,color='#0072B2',edgecolors='none',zorder=2)
            ax.scatter(float(sr['median_delta_candidate_minus_reference']),i,s=110,marker='D',color='#D55E00',zorder=4)
            ticks.append(name+f'  {len(rr)}/541')
        ax.axvline(0,color='#374151',lw=1);ax.set_xscale('symlog',linthresh=linthresh)
        ax.set_xlabel(xlabel);ax.set_yticks(range(4),ticks,fontsize=13);ax.set_ylim(3.65,-.65);frame(ax)
        if key=='horizontal_rmse_m': ax.set_xticks([-1,-.01,0,.01,1],['−1','−0.01','0','0.01','1'])
        else: ax.set_xticks([-100,-1,-.01,0,.01,1],['−100','−1','−0.01','0','0.01','1'])
    axes[1].tick_params(labelleft=False)
    fig.text(.16,.065,'Δ = Proposed − the corresponding one-module-off configuration. Negative favors Proposed; positive favors the ablation.\nAll saved paired points shown; diamonds: saved paired median. Symmetric-log axes resolve small effects without deleting large ones.',fontsize=11,color='#4B5563')
    b.figure(fig,'R06_CORE_single_module_paired_contrasts','Single-module effects have heterogeneous magnitudes and adverse cases.',
             'All common-finite original case-level pairs for 4 exact one-toggle comparisons × 2 metrics; nonfinite excluded by existing pair ledger, 541 original registered denominator retained. Only deterministic vertical jitter; no bootstrap, significance calculation, or paired-set recomputation. Diamonds are saved medians.')

    core=b.rows(V/'CORE_541_TABLE_V3.csv');b.copy('all_5951_original_run_statuses',core,['run_id','method_id','case_id','status','failure_classification','matched_epoch_count','output_epoch_count'])
    assert len(core)==5951
    counts=[]
    for m in METHODS:
        rs=[r for r in core if r['method_id']==m];assert len(rs)==541
        c=collections.Counter(r['failure_classification'] for r in rs)
        assert set(c)<=set(['NONE','ALGORITHM_FAILURE_DIVERGED','ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT'])
        assert all((r['status']=='COMPLETED')==(r['failure_classification']=='NONE') for r in rs)
        counts.append([c[s] for s in ['NONE','ALGORITHM_FAILURE_DIVERGED','ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT']])
    fig,ax=plt.subplots(figsize=(14,6.5));fig.subplots_adjust(left=.27,right=.985,top=.86,bottom=.17)
    fig.suptitle('Original CORE | All 5,951 native outcomes',x=.045,ha='left',y=.98,fontsize=18,fontweight='bold')
    left=np.zeros(11);colors=['#0072B2','#D55E00','#CC79A7'];labs=['Completed','Diverged','No valid heading input']
    for j,(c,l) in enumerate(zip(colors,labs)):
        vals=np.array(counts)[:,j];ax.barh(range(11),vals,left=left,height=.67,color=c,label=l)
        for i,(value,start) in enumerate(zip(vals,left)):
            if value>=20: ax.text(start+value/2,i,str(value),ha='center',va='center',color='white',fontsize=11)
        left+=vals
    labels(ax);ax.set_xlim(0,560);ax.set_xlabel('Native runs (541 registered per configuration)');frame(ax)
    ax.legend(loc='upper left',bbox_to_anchor=(0,1.14),ncol=3,frameon=False,fontsize=13)
    for i,c in enumerate(counts):ax.text(544,i,f'{c[1]+c[2]} failed',fontsize=11,va='center',color='#374151')
    fig.text(.045,.035,'All registered cases, including clean control and nine placements for D01–D60. Original terminal labels retained; failure is never error zero.',fontsize=11,color='#4B5563')
    b.figure(fig,'R07_CORE_all_5951_outcomes','Every original registered run and failure remains in the evidence denominator.',
             'Exact counts of authoritative original failure_classification tokens for all 5951 rows, including NONE/COMPLETED. Aggregate status NOT_RUN_ALGORITHM_FAILURE is the skipped evaluation status and is not silently relabeled as a finite outcome. No relabeling based on metrics; source table retains run identity and formal matched/output counts.')

    add=b.rows(V/'ADDENDUM_TABLE_V3.csv');assert len(add)==495
    b.copy('all_original_495_ADD_runs',add,['run_id','method_id','case_id','degradation_type_id','seed_index','horizontal_rmse_m','yaw_rmse_deg','status','matched_epoch_count','output_epoch_count'])
    assert all(r['status']=='COMPLETED' for r in add)
    fig,axes=canvas('Original ADD | Entirely lost GNSS inputs versus retained heading')
    fig.subplots_adjust(top=.80)
    for ax,typ,title in zip(axes,['D61','D62'],['D61: full registered GNSS outage','D62: registered heading retained']):
        for i,m in enumerate(METHODS):
            rr=[r for r in add if r['method_id']==m and r['degradation_type_id']==typ]
            assert len(rr)==(27 if typ=='D61' else 18)
            for duration,color,marker in [(10,'#0072B2','o'),(20,'#D55E00','s'),(30,'#009E73','^')]:
                rs=[r for r in rr if f'_{duration}s_' in r['case_id']]
                if not rs:continue
                assert len(rs)==9
                ys=i+(np.arange(9)-4)*.035+({10:-.18,20:0,30:.18}[duration])
                ax.scatter([float(r['horizontal_rmse_m']) for r in rs],ys,color=color,marker=marker,s=29,alpha=.8)
        ax.set_xscale('log');ax.set_xlabel('Whole-window horizontal RMSE (m)');ax.set_title(title,fontsize=15);labels(ax);frame(ax)
    legend=[Line2D([],[],color=c,marker=m,ls='',markersize=7,label=f'{d} s; all nine placements') for d,c,m in [(10,'#0072B2','o'),(20,'#D55E00','s'),(30,'#009E73','^')]]
    fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.66,.94),ncol=3,frameon=False,fontsize=12)
    fig.text(.045,.05,'All 495 original runs completed: D61 27 × 11; D62 18 × 11. All 45 registered conditions shown; no best-placement selection.\nThese are original protocol providers and whole-window metrics, not the later corrected 135-case diagnostic or an independent field experiment.',fontsize=11,color='#4B5563')
    b.figure(fig,'R08_ADD_all_45_conditions','Retained heading and total registered GNSS loss have markedly different application outcomes.',
             'Every original ADD case and all 11 configurations; D61 durations10/20/30s with9placements, D62 durations10/20s with9placements. Existing whole-window RMSE values; all output/matched counts retained in adjacent CSV. No causal claim about an unavailable exact raw-GNSS fault stream; original provider definition and common initialization apply.')
    b.seal(__file__,all_original_CORE_count=5951,all_original_ADD_count=495,registered_CORE_per_configuration=541)

if __name__=='__main__':main()
