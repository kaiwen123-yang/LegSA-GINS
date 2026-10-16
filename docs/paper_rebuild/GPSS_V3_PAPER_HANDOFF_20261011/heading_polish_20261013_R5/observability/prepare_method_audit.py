"""Collect existing route identities and saved metrics, without reevaluation."""
from pathlib import Path
import csv,json,hashlib
import pandas as pd
O=Path(__file__).parent
R=Path('/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001')
ROOT=Path('/mnt/g/LegSA-GINS-project')
rows=[];evidence=[]
for seq,mode in [('BY2','C00'),('BY2H','CONTRACT_START'),('BY2O','FILE_START')]:
    for method in ['OFF-LIT','OFF-DEF','LEG-DR']:
        if method=='LEG-DR':
            path=R/f'docs/paper_rebuild/hext/HX05/LEG_DR/{seq}/RESULT.json'
            family='Contact-kinematic dead reckoning'
            inputs='body gyro; contact foot position/velocity proxies; onboard SDK RPY for frame rotation'
            yaw='Inherited onboard attitude; not estimated by the integration method'
            native=ROOT/f'clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX05_CLOSEOUT/RUNS/{seq}/NAV.csv'
        else:
            run=f'{seq}__HARTLEY_OFFICIAL__{method}__{mode}'
            path=R/f'docs/paper_rebuild/hext/HX02E/RUNS/{run}/RESULT.json'
            family='Official contact-aided InEKF'
            inputs='body gyro/accelerometer; contact flags; foot-position proxy; no onboard attitude input'
            yaw='Estimated internally with no absolute heading measurement'
            native=ROOT/f'clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX02E_HARTLEY_OFFICIAL/RUNS/{run}/NAV.csv'
        result=json.loads(path.read_text());metrics=result['metrics'];alignment=metrics['alignment']
        copied=O/'audit'/f'{seq}_{method}_RESULT.json';copied.write_bytes(path.read_bytes())
        source=O/f'source_data/relative/{seq}_{method}_relative_errors.csv.gz'
        table=pd.read_csv(source)
        assert len(table)==metrics['scored_epochs']
        assert table.horizontal_err_m.notna().all() and table.yaw_err_deg.notna().all()
        rows.append(dict(sequence=seq,configuration=method,algorithm_family=family,
                         primary_or_sensitivity='parameter sensitivity of same InEKF' if method=='OFF-DEF' else 'author-confirmed primary route',
                         source_result=str(path),source_saved_error_csv=str(source),native_nav=str(native),
                         native_nav_sha256=result['nav_sha256'],code_commit=result['code_commit'],
                         official_library_commit='ef16e8a1df72f9272111a488880e3fe9d161f59f' if method!='LEG-DR' else '',
                         input_role=inputs,heading_role=yaw,scored_epochs=metrics['scored_epochs'],
                         unsupported_grid_epochs=metrics['unsupported_grid_epochs'],
                         horizontal_rmse_m=metrics['horizontal_rmse_m'],relative_heading_rmse_deg=metrics['yaw_rmse_deg'],
                         alignment_start_s=alignment['window_seconds'][0],alignment_end_s=alignment['window_seconds'][1],
                         saved_alignment_yaw_deg=alignment['yaw_offset_deg'],saved_alignment_translation=json.dumps(alignment['translation_enu_m']),
                         alignment_rule=alignment['rule'],new_alignment_fit=False))
pd.DataFrame(rows).to_csv(O/'audit/METHOD_IDENTITY_AND_EXISTING_RESULTS.csv',index=False)

def cite(source,needle,after,meaning):
    source=Path(source);lines=source.read_text().splitlines();n=next(i+1 for i,s in enumerate(lines) if needle in s)
    evidence.append(dict(path=str(source),line_start=n,line_end=min(len(lines),n+after),meaning=meaning))
cite(R/'src/legsa_gins/paper_rebuild/hext/hx05_leg_dr.py','def kinematic_velocity',11,'Contact-kinematic velocity formula; no SDK velocity shortcut')
cite(R/'src/legsa_gins/paper_rebuild/hext/hx05_leg_dr.py',"speed = raw",18,'Onboard RPY rotation and integration; saved method uses this additional information')
cite(R/'docs/paper_rebuild/hext/HX02E/HX02E_RESULTS.md','OFF-LIT 使用',1,'OFF-LIT/OFF-DEF are parameter configurations of the same official library')
cite(R/'src/legsa_gins/paper_rebuild/hext/hx02_relative_pose_evaluation.py','ALIGNMENT_RULE =',13,'Saved one-time per-branch initial10s yaw and translation alignment; no refit in plotting')
cite(ROOT/'V3正文精修_20261012_R3/navigation/build_trajectories.py',"S11_native_relative_trajectories",0,'Previous S11 already contained official InEKF settings and LEG-DR, not a second contact EKF')
cite(R/'scripts/paper10g_r2a_lse_distinctness_audit.py','def run_lse02_qekf_kinematic_proxy',45,'Historical QEKF-labelled fixed-gain proxy, not selected by author clarification and not introduced as current EKF baseline')
pd.DataFrame(evidence).to_csv(O/'audit/EVIDENCE_LOCATIONS.csv',index=False)
families=[
 dict(family='H5/H6 reported-IJRR InEKF',kind='earlier single-algorithm gauge check',used='F04 a/b only',relation='one recorded dataset, seven initialization settings'),
 dict(family='Official Hartley contact InEKF',kind='author-confirmed first route',used='F04 c/d and S04: OFF-LIT',relation='OFF-DEF is sensitivity of same library, retained in table'),
 dict(family='Contact-kinematic DR',kind='author-confirmed second route',used='F04 c/d and S04: LEG-DR',relation='Uses onboard attitude; not a separate EKF or validated independent absolute-heading instrument'),
 dict(family='Historical LSE02 QEKF-labelled proxy',kind='historical identity candidate before clarification',used='not plotted',relation='Source/report found; not the user-intended second route; no old numeric promotion'),
]
pd.DataFrame(families).to_csv(O/'audit/IDENTITY_CANDIDATES_AND_FINAL_SELECTION.csv',index=False)
print('Nine saved result identities, six primary method/scene pairs, no evaluation calls.')
