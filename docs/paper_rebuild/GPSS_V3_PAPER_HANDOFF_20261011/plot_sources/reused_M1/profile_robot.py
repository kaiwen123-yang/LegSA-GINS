from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
ROOT=Path('/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/07_LSE01_HARTLEY_CONTACT_INEKF')
OUT=Path(__file__).parent
SOURCES=[]
def read_csv(path):
    raw=path.read_bytes()
    df=pd.read_csv(path)
    SOURCES.append({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(df),'columns':list(df),'missing':{k:int(v) for k,v in df.isna().sum().items() if v}})
    return df
def load():
    runs={}
    files=[ROOT/'08_BY2_NATIVE/01_PRIMARY_GO2_ALLAN_EQ61_FK10MM/NAV.csv']+sorted((ROOT/'09_GAUGE_ENSEMBLE').glob('*/NAV.csv'))
    for p in files:
        df=read_csv(p)
        psi=np.rad2deg(np.unwrap(np.arctan2(df.r10,df.r00)))
        yaw0=int(round(psi[0]))
        runs[yaw0]={'frame':df,'psi':psi,'t':(df.timestamp_ns.to_numpy()-df.timestamp_ns.iloc[0])/1e9,'path':str(p)}
    spec=read_csv(ROOT/'10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_SINGULAR_VALUES_R1.csv')
    rank=read_csv(ROOT/'10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_RANK_SENSITIVITY_R1.csv')
    win=read_csv(ROOT/'10_OBSERVABILITY_R1/00_WINDOW_REUSE/H6_OBSERVABILITY_WINDOW_SELECTION.csv')
    eq=read_csv(ROOT/'09_GAUGE_ENSEMBLE_R1_FULL_PRECISION_CONTACT/09_EQUIVALENCE/H6R_GAUGE_EQUIVALENCE_SUMMARY.csv')
    nulpath=ROOT/'10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY_R1.json'
    null=json.loads(nulpath.read_text())
    SOURCES.append({'path':str(nulpath),'sha256':hashlib.sha256(nulpath.read_bytes()).hexdigest(),'read_depth':'full JSON'})
    anchor=runs[0]
    records=[]
    for yaw,r in sorted(runs.items()):
        d=r['frame']; p=d[['px','py','pz']].to_numpy()
        assert len(d)==63277
        assert np.array_equal(d.timestamp_ns,anchor['frame'].timestamp_ns)
        assert np.isfinite(d.select_dtypes('number').to_numpy()).all()
        angle=np.deg2rad(yaw)
        inv=np.array([[np.cos(angle),np.sin(angle),0],[-np.sin(angle),np.cos(angle),0],[0,0,1]])
        aligned=p@inv.T
        records.append({'initial_euler_yaw_deg':yaw,'rows':len(d),'duration_s':float(r['t'][-1]),'xyz_min':p.min(axis=0).tolist(),'xyz_max':p.max(axis=0).tolist(),'heading_range': [float(r['psi'].min()),float(r['psi'].max())],'inverse_rotation_position_max_m':float(np.linalg.norm(aligned-anchor['frame'][['px','py','pz']].to_numpy(),axis=1).max()),'relative_yaw_difference_max_deg':float(np.abs((r['psi']-r['psi'][0])-(anchor['psi']-anchor['psi'][0])).max())})
    tables=[]
    for keys,g in spec.groupby(['model','normalization','window_id']):
        arr=g.singular_value.to_numpy()
        tables.append({'model':keys[0],'normalization':keys[1],'window':keys[2],'count':len(g),'min':float(arr.min()),'max':float(arr.max()),'smallest5_relative':(np.sort(arr)[:5]/arr.max()).tolist()})
    profile={'full_reads':SOURCES,'native_runs':records,'spectra':tables,'rank_rows':rank.to_dict('records'),'windows':win.to_dict('records'),'nullspace_summary':null,'equivalence_max_position_m':float(eq.position_difference_m_max.max()),'equivalence_max_relative_yaw_rad':float(eq.relative_yaw_increment_difference_rad_max.max()),'native_points_read':sum(len(r['frame']) for r in runs.values()),'solver_calls':0,'evaluator_calls':0,'provider_calls':0}
    (OUT/'FULL_RESULT_PROFILE.json').write_text(json.dumps(profile,indent=2,ensure_ascii=False))
    print(json.dumps({k:profile[k] for k in ('native_runs','spectra','equivalence_max_position_m','equivalence_max_relative_yaw_rad','native_points_read')},indent=2))
    return runs,spec,rank,win,eq,profile
if __name__=='__main__':load()
