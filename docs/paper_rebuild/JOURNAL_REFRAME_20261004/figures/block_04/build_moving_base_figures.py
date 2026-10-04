"""RTKLIB saved native-valid error and availability; four fixed conditions, all sequences."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from plot_utils import Book,setup,plt,np,pd,frame
setup();b=Book(HERE)
ROOT=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS')
WINDOWS={'BY2':(66,340,1370),'BY2H':(413,683,1350),'BY2O':(3186,3563,1885)}
VARIANTS=['V0','V0E','V1','V2'];COLORS=['#0072B2','#D55E00','#009E73','#CC79A7']
NAMES=['Original condition','Ephemeris-only change','Expanded constellation','Fix-and-hold condition']

def main():
    summaries=[]
    for seq,(a,z,den) in WINDOWS.items():
        fig,axes=plt.subplots(2,1,figsize=(14,6.5),sharex=True,gridspec_kw={'height_ratios':[2.3,1]})
        fig.subplots_adjust(left=.1,right=.985,top=.78,bottom=.18,hspace=.2)
        fig.suptitle(seq+' | Moving-base errors and actual native-valid support',x=.045,ha='left',y=.98,fontsize=18,fontweight='bold')
        for j,(var,col,name) in enumerate(zip(VARIANTS,COLORS,NAMES)):
            root=ROOT/(seq+'_'+var)/'eval/OUTPUT'
            met=b.json(root/'HEADING_METRICS.json')['variants']['RTKLIB']
            rows=b.rows(root/'HEADING_ERROR_SERIES_RTKLIB.csv');assert len(rows)==den
            d=b.copy(seq+'_'+var+'_full_saved_heading',rows,['epoch_index','t_rel_s','valid','reference_supported','error_valid_deg','hold_available','error_hold_deg','rtklib_q'])
            t=pd.to_numeric(d.t_rel_s).to_numpy()-a;y=pd.to_numeric(d.error_valid_deg,errors='coerce').to_numpy()
            valid=(d.valid=='1').to_numpy()&np.isfinite(y)
            assert sum(valid)==int(met['valid']['count'])==int(met['q1_fixed']['count'])
            label=name+f"  {sum(valid)}/{den}; RMSE {met['valid']['rmse_deg']:.2f}°"
            axes[0].scatter(t[valid],y[valid],color=col,s=12,marker=['o','s','^','D'][j],alpha=.72,label=label)
            axes[1].plot([0,z-a],[3-j]*2,color='#D1D5DB',lw=6,zorder=1)
            axes[1].scatter(t[valid],np.full(sum(valid),3-j),color=col,marker='|',s=85,linewidths=1.5,zorder=3)
            summaries.append({'sequence':seq,'variant':var,'condition':name,'native_valid_count':sum(valid),'paired_epoch_denominator':den,
                              'native_valid_rmse_deg':met['valid']['rmse_deg'],'availability':met['availability'],
                              'hold_rmse_deg':met['hold_last_valid']['rmse_deg'],'hold_scored_count':met['hold_last_valid']['count']})
        axes[0].axhline(0,color='#4B5563',lw=.7);axes[0].set_ylabel('Saved heading error (°)');frame(axes[0])
        axes[0].legend(loc='upper left',bbox_to_anchor=(0,1.48),ncol=2,frameon=False,fontsize=11.5)
        axes[1].set_yticks([3,2,1,0],['Original','Ephemeris change','Constellation change','Fix-and-hold'],fontsize=12)
        axes[1].set_ylim(-.6,3.6);axes[1].set_xlabel('Elapsed time from formal window start (s)');axes[1].set_xlim(0,z-a)
        frame(axes[1]);fig.text(.1,.035,'Colored ticks: newly accepted native fixed solutions. Gray: original paired epoch span; no hold-last filling.\nHeading projection versus Euler reference is an application comparison; Q1 does not prove the integer ambiguities are correct.',fontsize=10.5,color='#4B5563')
        b.figure(fig,'R09_'+seq+'_moving_base_error_and_support','Accuracy must be read together with sparse native-valid support.',
                 'All four preregistered HX07R RTKLIB conditions, every saved formal paired epoch. Native-valid fixed error points only; no lines across missing epochs, no hold interpolation. Fixed counts and original 1370/1350/1885 denominators shown. Shared-GNSS commercial fusion reference; these configuration conditions are not four separate papers.',all_saved_epoch_rows_retained=True)
    # This is a token-only reduction of already saved metric JSON, not new scoring.
    b.copy('all_12_saved_RTKLIB_condition_metrics',summaries)
    fig,axes=plt.subplots(1,2,figsize=(14,6.5),sharey=True)
    fig.subplots_adjust(left=.17,right=.985,top=.87,bottom=.2,wspace=.35)
    fig.suptitle('Moving base | All four conditions, accuracy and denominator side by side',x=.045,ha='left',y=.98,fontsize=18,fontweight='bold')
    yy=np.arange(12)
    for i,r in enumerate(summaries):
        col=COLORS[VARIANTS.index(r['variant'])]
        axes[0].plot([r['native_valid_rmse_deg'],r['hold_rmse_deg']],[i,i],color='#C4CAD2',lw=1)
        axes[0].scatter(r['native_valid_rmse_deg'],i,color=col,s=65,marker='o')
        axes[0].scatter(r['hold_rmse_deg'],i,color='#6B7280',s=50,marker='x')
        axes[1].barh(i,100*r['availability'],height=.65,color=col)
        axes[1].text(100*r['availability']+.3,i,f"{r['native_valid_count']}/{r['paired_epoch_denominator']}",va='center',fontsize=11)
    axes[0].set_yticks(yy,[r['sequence']+' | '+r['variant'] for r in summaries],fontsize=12)
    axes[0].set_ylim(11.7,-.7);axes[0].set_xlabel('Heading RMSE (°)');axes[1].set_xlabel('Native-valid fixed availability (%)')
    axes[1].set_xlim(0,21)
    for ax in axes:frame(ax)
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([],[],color='#0072B2',marker='o',ls='',label='Native-valid fixed epochs'),Line2D([],[],color='#6B7280',marker='x',ls='',label='Hold-last diagnostic; different support')],loc='upper center',bbox_to_anchor=(.65,.93),ncol=2,frameon=False,fontsize=12)
    fig.text(.045,.04,'All 12 conditions retained; native-valid errors and held-value errors have different support. No single best condition selected.\nV0: original; V0E: ephemeris; V1: constellation; V2: fix-and-hold. Holding a stale heading does not create a new valid epoch.',fontsize=11,color='#4B5563')
    b.figure(fig,'R10_moving_base_all_12_accuracy_coverage','The favorable fixed RMSE values can coincide with very low availability.',
             'Token-only display of all 12 saved HX07R metric JSONs: native-valid fixed RMSE, hold-last RMSE and fixed counts/original paired denominators. Hold RMSE denominators are individually retained in adjacent data and are not assumed equal to valid fixed support.')
    b.seal(__file__,registered_conditions=12,original_epoch_denominators=[1370,1350,1885])

if __name__=='__main__':main()
