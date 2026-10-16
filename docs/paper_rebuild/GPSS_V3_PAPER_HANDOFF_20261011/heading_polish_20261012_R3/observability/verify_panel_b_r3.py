"""Independently check the known-angle inverse rotation without redrawing Fig4."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
P=Path(__file__).resolve().parent;S=P/'source_data'
runs={int(p.name.split('_')[-1].split('.')[0]):pd.read_csv(p) for p in S.glob('native_initial_yaw_*.csv.gz')}
base=runs[0];bxyz=base[['local_x_m','local_y_m','local_z_m']].to_numpy();saved=pd.read_csv(S/'ALL_NATIVE_ALIGNMENT_RESIDUALS.csv.gz')
rows=[]
for angle,d in sorted(runs.items()):
    assert len(d)==len(base)==63277
    assert np.array_equal(d.timestamp_ns,base.timestamp_ns)
    assert float(d.unwrapped_yaw_deg.iloc[0])==angle
    # Complex multiplication independently implements a known planar inverse rotation.
    rotated=(d.local_x_m.to_numpy()+1j*d.local_y_m.to_numpy())*np.exp(-1j*np.deg2rad(angle))
    q=np.column_stack([rotated.real,rotated.imag,d.local_z_m.to_numpy()])
    residual=np.linalg.norm(q-bxyz,axis=1)
    col=f'yaw_{angle:+04d}_position_difference_m'
    roundtrip=float(np.max(np.abs(residual-saved[col].to_numpy())))
    assert roundtrip<1e-11
    rows.append({'initial_yaw_deg':angle,'native_rows':len(d),'identical_timestamps':True,'initial_position_m':d[['local_x_m','local_y_m','local_z_m']].iloc[0].tolist(),'max_inverse_rotation_difference_m':float(residual.max()),'max_disagreement_with_saved_residual_m':roundtrip})
pd.DataFrame(rows).to_csv(P/'qa/F04b_INDEPENDENT_RECHECK.csv',index=False)
old=P.parent.parent/'V3正文精修_20261012_R2/observability'
matches={}
for ext in ['pdf','svg','png','tiff']:
    name='F04_absolute_direction_relative_motion.'+ext
    matches[ext]=hashlib.sha256((P/name).read_bytes()).hexdigest()==hashlib.sha256((old/name).read_bytes()).hexdigest()
assert all(matches.values())
report={'status':'PASS','method':'Complex rotation z*exp(-i*known_yaw), with unchanged vertical coordinate; no angle fit/translation/scale/time fit','runs':7,'rows_per_run':63277,'all_native_rows':7*63277,'maximum_position_difference_m':max(x['max_inverse_rotation_difference_m'] for x in rows),'maximum_saved_residual_disagreement_m':max(x['max_disagreement_with_saved_residual_m'] for x in rows),'approved_artwork_byte_identical':matches,'what_it_means':'Known global-coordinate rotations leave the estimated relative path equivalent under the same proprioceptive observations. Residual is numerical agreement between rotated runs, not geographical position accuracy.','new_solver_calls':0}
(P/'qa/F04b_R3_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
