#!/usr/bin/env python3
"""Source-only conditional heading sigma: preserve frame-semantic alternatives."""
import argparse, ast, csv, hashlib, io, json, zipfile
from pathlib import Path
import numpy as np


def sha(b): return hashlib.sha256(b).hexdigest()
def skew(v):
    x,y,z=v;return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
def exp(v):
    t=np.linalg.norm(v);W=skew(v)
    return np.eye(3)+(np.sin(t)/t if t else 1.)*W+((1-np.cos(t))/t**2 if t else .5)*W@W
def qmat(q):
    x,y,z,w=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def enu(lat,lon):
    a,b=np.deg2rad([lat,lon]);sa,ca,sb,cb=np.sin(a),np.cos(a),np.sin(b),np.cos(b)
    return np.array([[-sb,cb,0.],[-sa*cb,-sa*sb,ca],[ca*cb,ca*sb,sa]])
def wrap(x):return (x+np.pi)%(2*np.pi)-np.pi
def heading(A,R):
    v=(A@R)[:,0];return np.pi/2-np.arctan2(v[1],v[0])
def jac(A,R):
    U=A@R;v=U[:,0];q=v[0]**2+v[1]**2;g=np.array([-v[1]/q,v[0]/q,0.])
    JL=-g@(-skew(v))@A;JR=-g@(-U@skew([1.,0.,0.]))
    return JL,JR,q

def one_formula_check():
    # One centralized nonzero roll/pitch/yaw, anisotropic covariance check, no scan.
    roll,pitch,yaw=np.deg2rad([13.,-17.,47.]);A=enu(39.9,116.3)
    R=A.T@exp(np.array([0.,0.,yaw]))@exp(np.array([0.,pitch,0.]))@exp(np.array([roll,0.,0.]))
    JL,JR,_=jac(A,R);eps=1e-6;eye=np.eye(3)
    fL=np.array([wrap(heading(A,exp(eps*u)@R)-heading(A,exp(-eps*u)@R))/(2*eps) for u in eye])
    fR=np.array([wrap(heading(A,R@exp(eps*u))-heading(A,R@exp(-eps*u)))/(2*eps) for u in eye])
    B=np.array([[2.,.2,-.3],[0.,1.,.4],[0.,0.,3.]])*1e-2;C=B@B.T;Cb=R.T@C@R
    result=dict(rpy_deg=[13.,-17.,47.],eps_rad=eps,J_heading_left_ECEF=JL.tolist(),J_heading_right_POI=JR.tolist(),finite_difference_left=fL.tolist(),finite_difference_right=fR.tolist(),left_max_abs_error=float(np.max(np.abs(JL-fL))),right_max_abs_error=float(np.max(np.abs(JR-fR))),same_physical_covariance_variance_difference=float(abs(JL@C@JL-JR@Cb@JR)),same_covariance_note='Cb=R^T Ce R must give identical heading variance; alternative B later deliberately reinterprets serialized entries as local, not this equivalent change of basis')
    result['status']='PASS' if max(result['left_max_abs_error'],result['right_max_abs_error'])<1e-8 and result['same_physical_covariance_variance_difference']<1e-12 else 'FAIL'
    assert result['status']=='PASS';return result

def stats(a):
    a=np.asarray(a);return dict(n=len(a),min=float(a.min()),median=float(np.median(a)),p95=float(np.percentile(a,95)),max=float(a.max()),rms=float(np.sqrt(np.mean(a*a))),first=float(a[0]),last=float(a[-1]))
def table(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-audit',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();src=Path(a.source_audit);out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    old=json.loads((src/'PLAN.json').read_text());oldsum=json.loads((src/'SUMMARY.json').read_text());seq=old['sequence'];ref=seq['reference'];pre=ref['member'].rsplit('/',1)[0];member=pre+'/user_io-out-poi_odometry.csv'
    cache=list(csv.DictReader((src/'SOURCE_EPOCHS.csv').open()));strows=list(csv.DictReader((src/'STATUS_INTERVALS.csv').open()));window=old['windows'];windows=dict(FULL=window['FULL'],GAP=window['GAP'],RECOVERY=[window['GAP'][1],window['FULL'][1]])
    formula=one_formula_check();(out/'FORMULA_CHECK.json').write_text(json.dumps(formula,indent=2))
    with zipfile.ZipFile(ref['path']) as z: payload=z.read(member)
    assert sha(payload)==old['input_pins'][member]['sha256']
    od=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))));assert len(od)==len(cache)
    ns=np.array([int(x['header.stamp.secs'])*10**9+int(x['header.stamp.nsecs']) for x in od],dtype=np.int64)
    native_ns=ns-int(seq['base_time_unix_s'])*10**9;t=np.array([float(x['measurement_utc_day_s']) for x in cache]);joinerr=np.max(np.abs(native_ns.astype(float)/1e9-t));assert joinerr<3e-7
    assert np.all(np.diff(ns)>0)
    q=np.array([[float(x['pose.pose.orientation.'+k]) for k in ['x','y','z','w']] for x in od]);cov=np.array([ast.literal_eval(x['pose.covariance']) for x in od]).reshape(-1,6,6)
    Cs=cov[:,3:,3:];rot=np.array([qmat(x) for x in q]);As=np.array([enu(float(x['lat']),float(x['lon'])) for x in cache])
    field=np.array([float(x['ypr_var_x_recorded']) for x in cache]);reported=np.deg2rad([float(x['yaw_ENU_deg']) for x in cache])
    vA=[];vB=[];yaw=[];den=[];jL=[];jR=[];same=[]
    for A,R,C in zip(As,rot,Cs):
        JL,JR,rr=jac(A,R);vA.append(JL@C@JL);vB.append(JR@C@JR);yaw.append(np.pi/2-heading(A,R));den.append(rr);jL.append(JL);jR.append(JR);same.append(JL@C@JL-JR@(R.T@C@R)@JR)
    va=np.array(vA);vb=np.array(vB);sa=np.degrees(np.sqrt(va));sb=np.degrees(np.sqrt(vb));ydiff=np.rad2deg(wrap(np.array(yaw)-reported));den=np.array(den)
    assert np.all(va>=0) and np.all(vb>=0)
    np.savez_compressed(out/'ORIENTATION_SOURCE_CACHE.npz',header_unix_ns=ns,source_native_ns=native_ns,quaternion_xyzw=q,pose_covariance_ECEF_recorded=cov,R_ECEF_POI=rot,R_ENU_ECEF=As,heading_jacobian_left_ECEF=np.array(jL),heading_jacobian_right_POI=np.array(jR),sigma_heading_A_deg=sa,sigma_heading_B_deg=sb)
    rows=[]
    for i,(cc,oo) in enumerate(zip(cache,od)):
        rows.append(dict(source_unique_index=i,original_geodetic_row=cc['source_row'],measurement_unix_ns=int(ns[i]),measurement_day_s=t[i],source_yaw_ENU_deg=cc['yaw_ENU_deg'],quaternion_yaw_ENU_deg=float(np.degrees(yaw[i])),heading_NED_deg=float(np.degrees(wrap(np.pi/2-yaw[i]))),heading_sigma_A_ECEF_fixed_axis_deg=float(sa[i]),heading_sigma_B_POI_local_axis_deg=float(sb[i]),B_minus_A_sigma_deg=float(sb[i]-sa[i]),legacy_ypr_var_x=float(field[i]),forward_horizontal_norm_sq=float(den[i])))
    summary=dict(source_member=member,source_rows=len(od),one_zip_member_read=1,NAV_reads=0,native=0,evaluator=0,formula_check=formula,semantic_decision='A is the published ROS/Fixposition fixed-reference-axis contract; historical fpl/ROS exporter identity is not established. B is a serialized-covariance local-axis sensitivity hypothesis, not a second transformation of A.',coordinate_convention=dict(quaternion='R_ECEF_POI, verified against cached geodetic yaw',A='C_serialized = Cov(delta_theta_ECEF); Rtrue=Exp(delta_theta_ECEF) R',B='C_serialized = Cov(delta_theta_POI); Rtrue=R Exp(delta_theta_POI)',conditional='reported local latitude/longitude fixed; excludes POI-to-body installation and calibrated true-error claims'),lineage=dict(max_cached_header_time_difference_s=float(joinerr),frames=dict((k,sum(x['header.frame_id']==k for x in od)) for k in set(x['header.frame_id'] for x in od)),children=dict((k,sum(x['child_frame_id']==k for x in od)) for k in set(x['child_frame_id'] for x in od)),max_quaternion_vs_recorded_yaw_deg=float(np.max(np.abs(ydiff))),same_physical_covariance_left_right_variance_max_abs=float(np.max(np.abs(same))),minimum_heading_horizontal_norm_sq=float(den.min())),windows={})
    metrics=[]
    for name,(lo,hi) in windows.items():
        m=(t>=lo)&(t<=hi);z=dict(bounds_day_s=[lo,hi],n=int(m.sum()),sigma_A_deg=stats(sa[m]),sigma_B_deg=stats(sb[m]),B_minus_A_deg=stats(sb[m]-sa[m]),B_over_A=stats(sb[m]/sa[m]),source_status_intervals=[x for x in strows if x['field'] in ['fusion_gnss1','fusion_gnss2','baseline_status'] and float(x['last_arrival_day_s'])>=lo and float(x['first_arrival_day_s'])<=hi])
        z['legacy_field_diagnostic']=dict(raw_x_vs_A_variance_deg2_max_abs=float(np.max(np.abs(field[m]-sa[m]**2))),raw_x_vs_A_std_deg_max_abs=float(np.max(np.abs(field[m]-sa[m]))),raw_x_vs_B_variance_deg2_max_abs=float(np.max(np.abs(field[m]-sb[m]**2))),raw_x_vs_B_std_deg_max_abs=float(np.max(np.abs(field[m]-sb[m]))),interpretation='no fitted factor/offset; numerical coincidence does not certify hidden exporter or true uncertainty')
        summary['windows'][name]=z
        for label,vals in [('A_ECEF_fixed_axis',sa[m]),('B_POI_local_axis_hypothesis',sb[m])]:metrics.append(dict(window=name,hypothesis=label,**stats(vals)))
    jump=[r for r in rows if 40935.5<=r['measurement_day_s']<=40935.9];summary['previously_identified_position_correction_heading_rows']=jump
    summary['readout_boundary']='No selected quality mask, time shift fit, yaw bias correction, installation calibration, or new evaluation. Existing results unchanged.'
    pins={str(src/n):sha((src/n).read_bytes()) for n in ['PLAN.json','SUMMARY.json','SOURCE_EPOCHS.csv','STATUS_INTERVALS.csv']};pins[member]=sha(payload)
    (out/'PLAN.json').write_text(json.dumps(dict(script_path=str(Path(__file__)),script_sha256=sha(Path(__file__).read_bytes()),input_pins=pins,windows=windows,one_missing_input='NMB1 poi_odometry only, existing cache lacks quaternion and full covariance',interpretations=summary['coordinate_convention']),indent=2))
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2));table(out/'HEADING_EPOCHS.csv',rows);table(out/'HEADING_SIGMA_SUMMARY.csv',metrics)
    print(json.dumps(dict(lineage=summary['lineage'],windows={k:{f:v[f] for f in ['n','sigma_A_deg','sigma_B_deg','B_over_A','legacy_field_diagnostic']} for k,v in summary['windows'].items()},formula_status=formula['status']),indent=2))
if __name__=='__main__':main()
