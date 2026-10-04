"""Original saved matched trajectory and three-axis attitude error charts."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from plot_utils import Book,setup,plt,np,pd,frame,line
setup();b=Book(HERE)
V=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3')
WINDOWS={'BY2':(66,340),'BY2H':(413,683),'BY2O':(3186,3563)}

def xyz(lat,lon,h):
    a=6378137.;e2=6.6943799901413165e-3
    lat=np.deg2rad(lat);lon=np.deg2rad(lon);n=a/np.sqrt(1-e2*np.sin(lat)**2)
    return np.column_stack(((n+h)*np.cos(lat)*np.cos(lon),(n+h)*np.cos(lat)*np.sin(lon),(n*(1-e2)+h)*np.sin(lat)))

def main():
    p=V/'04_EVALUATION/RUN_00004/v3/FROZEN_EVALUATOR/MATCHED_TRAJECTORY.csv.gz'
    manifest=b.json(p.parent/'MATCHED_TRAJECTORY_MANIFEST.json')
    rows=b.rows(p,manifest['csv_sha256']);d=b.copy('BY2_original_matched_trajectory',rows).apply(pd.to_numeric)
    assert len(d)==56642
    anchor=d.loc[0,['truth_latitude_deg','truth_longitude_deg','truth_height_m']].to_numpy(float)
    lat,lon=np.deg2rad(anchor[:2]);c=np.array([[-np.sin(lon),np.cos(lon),0],[-np.sin(lat)*np.cos(lon),-np.sin(lat)*np.sin(lon),np.cos(lat)]])
    x0=xyz(*[np.array([x]) for x in anchor])[0]
    q={}
    for key in ['truth','estimate']:
        llh=d[[key+'_latitude_deg',key+'_longitude_deg',key+'_height_m']].to_numpy()
        q[key]=(xyz(llh[:,0],llh[:,1],llh[:,2])-x0)@c.T
    fig,ax=plt.subplots(figsize=(14,6.5));fig.subplots_adjust(left=.09,right=.77,top=.9,bottom=.17)
    fig.suptitle('BY2 | Original full-window trajectory',x=.06,ha='left',y=.98,fontweight='bold',fontsize=18)
    parts=np.split(np.arange(len(d)),np.flatnonzero(np.diff(d.time)>.1)+1)
    for key,col,style,label in [('truth','#4B5563','-','Commercial fusion reference'),('estimate','#0072B2','--','Proposed')]:
        for i,part in enumerate(parts): ax.plot(q[key][part,0],q[key][part,1],color=col,lw=2.1 if key=='truth' else 1.5,ls=style,label=label if i==0 else None)
    ax.scatter(*q['truth'][0],s=110,color='#009E73',marker='o',zorder=6)
    ax.scatter(*q['truth'][-1],s=120,color='#D55E00',marker='X',zorder=6)
    ax.set_aspect('equal',adjustable='box');ax.set_xlabel('East from fixed display anchor (m)');ax.set_ylabel('North from fixed display anchor (m)');frame(ax)
    ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),frameon=False,fontsize=12)
    fig.text(.795,.57,'56,642 / 56,642\nmatched / output epochs\n\n66–340 s formal window\n\nGreen: first saved point\nOrange: last saved point',fontsize=13,va='top',color='#374151')
    fig.text(.06,.035,'Declared dual-antenna midpoint; fixed WGS84 display projection, no trajectory alignment or fit.\nThe shared-GNSS commercial reference is not independent ground truth.',fontsize=11,color='#4B5563')
    b.figure(fig,'R03_BY2_original_trajectory','The original saved trajectory follows the route over the full formal window.',
             'All 56642 saved matched trajectory rows; estimate and commercial fusion reference shown at the original declared midpoint. Fixed display anchor is the first saved reference LLH; WGS84 ECEF then East/North projection is a coordinate display, not alignment or new evaluation. Gaps >0.1s are not joined.',display_anchor_llh=anchor.tolist(),all_rows_drawn=True)
    for seq,(a,z) in WINDOWS.items():
        rows=b.rows(HERE.parent/'block_01/data'/f'{seq}_F04_errors.csv.gz')
        d=b.copy(seq+'_Proposed_attitude_errors',rows,['time','roll_err_deg','pitch_err_deg','yaw_err_deg']).apply(pd.to_numeric)
        fig,axes=plt.subplots(3,1,figsize=(14,6.5),sharex=True)
        fig.subplots_adjust(left=.09,right=.985,top=.9,bottom=.23,hspace=.18)
        fig.suptitle(seq+' | Full-window attitude error',x=.09,ha='left',y=.985,fontweight='bold',fontsize=18)
        for ax,key,label,col in zip(axes,['roll_err_deg','pitch_err_deg','yaw_err_deg'],['Roll error (°)','Pitch error (°)','Yaw error (°)'],['#0072B2','#009E73','#D55E00']):
            line(ax,d.time.to_numpy()-a,d[key].to_numpy(),lw=.65,color=col)
            ax.set_ylabel(label);ax.axhline(0,color='#6B7280',lw=.6);frame(ax);ax.set_xlim(0,z-a)
        axes[-1].set_xlabel('Elapsed time from formal window start (s)')
        fig.text(.1,.065,f'Proposed | {len(d):,}/{len(d):,} saved matched/output epochs | original evaluator v3',fontsize=12,color='#374151')
        fig.text(.1,.02,'Attitude relative to shared-GNSS commercial fusion reference; all retained samples, no smoothing or new scoring.',fontsize=10.5,color='#4B5563')
        b.figure(fig,'R04_'+seq+'_attitude_errors','All three attitude components and adverse excursions remain visible.',
                 'Original F04 saved evaluator v3 roll/pitch/yaw errors. All formal-window rows, unchanged values; display splits at actual time gaps >0.1s. Matched/output count is not nominal-grid or physical-time coverage.',all_rows_drawn=True)
    b.seal(__file__,original_V3_only=True,unavailable_original_H_O_matched_trajectory='Not reconstructed; their original NAV/matched trajectory payloads were not retained.')

if __name__=='__main__':main()
