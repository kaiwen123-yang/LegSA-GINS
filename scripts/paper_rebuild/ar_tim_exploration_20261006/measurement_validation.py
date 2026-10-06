#!/usr/bin/env python3
"""Synthetic metrology checks only: no raw data, reference, navigation or evaluator.
Independent finite differences and assumed-distribution sensitivity; no calibration.
"""
from pathlib import Path
import argparse,csv,hashlib,json,math,os,platform
import numpy as np
SEED=20261006
N=200000
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def table(p,rows):
 with p.open("x",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
def wrap(x):return (np.asarray(x)+np.pi)%(2*np.pi)-np.pi
def skew(x):
 a,b,c=x;return np.array([[0.,-c,b],[c,0.,-a],[-b,a,0.]])
def exp_so3(x):
 t=np.linalg.norm(x);K=skew(x)
 return np.eye(3)+K+(K@K)/2 if t<1e-10 else np.eye(3)+np.sin(t)/t*K+(1-np.cos(t))/t**2*(K@K)
def Cbn(roll,pitch,yaw):
 cr,sr=np.cos(roll),np.sin(roll);cp,sp=np.cos(pitch),np.sin(pitch);cy,sy=np.cos(yaw),np.sin(yaw)
 return np.array([[cy,-sy,0],[sy,cy,0],[0,0,1.]])@np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])@np.array([[1.,0,0],[0,cr,-sr],[0,sr,cr]])
def heading(b):
 b=np.asarray(b);return wrap(np.arctan2(b[...,1],b[...,0])+np.pi/2)
def g_heading(b):
 n,e,d=b;r2=n*n+e*e
 if r2<=1e-12:raise ValueError("synthetic projection unsupported")
 return np.array([-e,n,0.])/r2
def main(a):
 assert os.uname().sysname=="Linux"
 a.out.mkdir(parents=True,exist_ok=False)
 parameters={"data_mode":"synthetic","seed":SEED,"bit_generator":"PCG64","samples_per_Gaussian_case":N,
 "L_m":[.35,.70],"receiver_axis_std_m":.01,"receiver_correlation_cases":[0.,.75,-.5],
 "roll_cases_deg":[0.,60.,89.],"pitch_cases_deg":[0.],"linear_regime_MC_relative_std_tolerance":.03,
 "FD_step":1e-7,"FD_max_error_tolerance":2e-6,"physical_baseline_band_m":[.2,.6],
 "timing_example_velocity_mps":[0.,.5,0.],"timing_example_offsets_s":[.007,.008,.02],
 "wrong_fixed_sensitivity_probability":.01,"wrong_fixed_bias_deg":20.,"conditional_angular_std_deg":1.,
 "targets_standard_uncertainty_deg":[1.,.5],"parameters_chosen_without_reference":True,
 "parameters_calibrated":False,"raw_reads":0,"reference_reads":0,"native_navigation_calls":0,"evaluator_calls":0}
 dump(a.out/"PARAMETERS.json",parameters)
 rng=np.random.Generator(np.random.PCG64(SEED))
 fd=[];tilt=[];eps=parameters["FD_step"]
 angles=[(0.,0.,0.),(15.,10.,37.),(-20.,12.,-110.),(45.,-20.,179.9),(85.,2.,-179.9)]
 for i,(rd,pd,yd) in enumerate(angles):
  r,p,y=np.deg2rad([rd,pd,yd]);C=Cbn(r,p,y);b=C@np.array([0.,-.35,0.]);g=g_heading(b)
  numeric=np.array([float(wrap(heading(b+eps*np.eye(3)[j])-heading(b-eps*np.eye(3)[j])))/(2*eps) for j in range(3)])
  # Actual residual convention: prediction(C_nominal)-observation(Exp(dphi) C_nominal).
  H=g@skew(b)
  nH=np.array([-float(wrap(heading(exp_so3(eps*np.eye(3)[j])@b)-heading(exp_so3(-eps*np.eye(3)[j])@b)))/(2*eps) for j in range(3)])
  error=max(float(abs(g-numeric).max()),float(abs(H-nH).max()))
  assert error<parameters["FD_max_error_tolerance"]
  fd.append({"case":i,"roll_deg":rd,"pitch_deg":pd,"yaw_deg":yd,"position_jacobian_max_abs_error":float(abs(g-numeric).max()),"residual_phi_jacobian_max_abs_error":float(abs(H-nH).max()),"passed":True})
  closed=float(wrap(y+math.atan2(-math.sin(p)*math.sin(r),math.cos(r))))
  assert abs(float(wrap(heading(b)-closed)))<1e-12
  tilt.append({"roll_deg":rd,"pitch_deg":pd,"Euler_yaw_deg":yd,"projected_lateral_heading_deg":float(np.rad2deg(heading(b))),"projected_minus_Euler_deg":float(np.rad2deg(wrap(heading(b)-y))),"horizontal_projection_m":float(np.linalg.norm(b[:2]))})
 # Cardinal signs, ENU conversion, wrapping and antenna order.
 for yd in [0.,90.,-90.,179.9,-179.9]:
  b=Cbn(0.,0.,np.deg2rad(yd))@np.array([0.,-.35,0.])
  assert abs(float(wrap(heading(b)-np.deg2rad(yd))))<1e-12
  enu=wrap(np.pi/2-heading(b));assert abs(float(wrap(enu-np.deg2rad(90-yd))))<1e-12
  assert abs(abs(float(wrap(heading(-b)-heading(b))))-np.pi)<1e-12
 table(a.out/"JACOBIAN_CHECKS.csv",fd);table(a.out/"TILT_MODEL.csv",tilt)
 rows=[]
 cases=[("rho_zero",.35,0.,0.),("rho_positive",.35,0.,.75),("rho_negative",.35,0.,-.5),("double_length",.70,0.,0.),("roll60",.35,60.,0.),("near_vertical",.35,89.,0.)]
 for name,L,rd,rho in cases:
  b=Cbn(np.deg2rad(rd),0.,np.deg2rad(31.))@np.array([0.,-L,0.]);g=g_heading(b)
  s=.01;U=s*s*np.block([[np.eye(3),rho*np.eye(3)],[rho*np.eye(3),np.eye(3)]])
  assert np.linalg.eigvalsh(U).min()>0
  D=np.hstack([-np.eye(3),np.eye(3)]);Ub=D@U@D.T
  analytical=float(np.sqrt(g@Ub@g))
  z=rng.standard_normal((N,6))@np.linalg.cholesky(U).T;err=z[:,3:]-z[:,:3]
  angular=wrap(heading(b+err)-heading(b));mc=float(np.sqrt(np.mean(angular**2)))
  rnorm=float(np.linalg.norm(b[:2]));ratio=float(np.sqrt(2*(1-rho))*s/rnorm)
  relative=abs(mc/analytical-1);test=name!="near_vertical"
  if test:assert relative<.03
  rows.append({"case":name,"N":N,"baseline_length_m":L,"roll_deg":rd,"horizontal_projection_m":rnorm,"receiver_axis_std_m":s,"receiver_cross_correlation":rho,"perpendicular_difference_std_m":float(np.sqrt(2*(1-rho))*s),"noise_to_projection_ratio":ratio,"linear_std_deg":float(np.rad2deg(analytical)),"MC_wrapped_RMS_deg":float(np.rad2deg(mc)),"relative_MC_vs_linear":relative,"linear_agreement_asserted":test,"MC_measured_length_gate_fraction":float(np.mean((np.linalg.norm(b+err,axis=1)>=.2)&(np.linalg.norm(b+err,axis=1)<=.6)))})
 table(a.out/"GAUSSIAN_PROPAGATION.csv",rows)
 # Physical timing offset illustration, not an interpretation of raw RAWX clock labels.
 b=np.array([.35,0.,0.]);v=np.array([0.,.5,0.]);timing=[]
 for dt in [.007,.008,.02]:
  exact=float(wrap(heading(b+v*dt)-heading(b)));linear=float(g_heading(b)@v*dt)
  timing.append({"assumed_physical_offset_s":dt,"perpendicular_velocity_mps":.5,"projection_m":.35,"linear_heading_error_deg":float(np.rad2deg(linear)),"exact_heading_error_deg":float(np.rad2deg(exact)),"inferred_from_RAWX_clock_label":False})
 # Joint antenna time sensitivity d b / d[tau1,tau2]=[-v1,+v2].
 C=Cbn(.2,-.1,.6);ell1=np.array([.03,.175,-.3]);ell2=np.array([.03,-.175,-.3]);omega=np.array([.1,-.2,.4]);vI=np.array([.3,.1,.05])
 b=C@(ell2-ell1);Jt=np.column_stack([-(vI+C@np.cross(omega,ell1)),vI+C@np.cross(omega,ell2)])
 def async_b(t1,t2):return vI*t2+C@exp_so3(omega*t2)@ell2-vI*t1-C@exp_so3(omega*t1)@ell1
 nt=np.column_stack([(async_b(eps,0)-async_b(-eps,0))/(2*eps),(async_b(0,eps)-async_b(0,-eps))/(2*eps)])
 assert float(abs(nt-Jt).max())<2e-8
 table(a.out/"TIMING_SENSITIVITY.csv",timing)
 targets=[{"projection_m":.35,"target_standard_uncertainty_deg":deg,"allowed_perpendicular_difference_std_mm_one_term":.35*np.deg2rad(deg)*1000,"one_term_small_angle_only":True,"real_sensor_calibration":False} for deg in [1.,.5]]
 table(a.out/"ANGLE_TARGET_BUDGET.csv",targets)
 wrong=rng.random(N)<.01;error_deg=rng.normal(0.,1.,N)+wrong*20.
 measured=.35*np.column_stack([np.cos(np.deg2rad(error_deg)),np.sin(np.deg2rad(error_deg)),np.zeros(N)])
 length=np.linalg.norm(measured,axis=1);mse_theory=1+.01*20**2
 mixture={"data_mode":"synthetic","N":N,"wrong_probability_assumed":.01,"wrong_count":int(wrong.sum()),"wrong_bias_assumed_deg":20.,"conditional_std_assumed_deg":1.,"MC_RMS_deg":float(np.sqrt(np.mean(error_deg**2))),"mixture_RMS_formula_deg":math.sqrt(mse_theory),"MC_abs_error_gt_10deg_fraction":float(np.mean(abs(error_deg)>10)),"MC_within_1p96deg_fraction":float(np.mean(abs(error_deg)<=1.96)),"length_min_m":float(length.min()),"length_max_m":float(length.max()),"length_gate_pass_fraction":float(np.mean((length>=.2)&(length<=.6))),"is_real_AR_wrong_fix_estimate":False}
 assert mixture["length_gate_pass_fraction"]==1. and abs(mixture["MC_RMS_deg"]/math.sqrt(mse_theory)-1)<.04
 dump(a.out/"WRONG_FIX_MIXTURE.json",mixture)
 src=["cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp","cpp/legsa_v23_port_core/src/fileio/gnss_file_loader.cpp","src/legsa_gins/paper_rebuild/final_v23_clean_input.py","src/legsa_gins/paper_rebuild/providers.py","src/legsa_gins/paper_rebuild/clean5_parity/providers.py","src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py","docs/paper_rebuild/TIM_EVIDENCE_20261005/sdk_and_metrology/INPUT_UNCERTAINTY_BUDGET.csv","docs/paper_rebuild/TIM_EVIDENCE_20261005/sdk_and_metrology/MINIMAL_VALIDATION_PROTOCOL.md"]
 result={"status":"PASS_SYNTHETIC_FORMULA_CHECKS_NOT_CALIBRATION","script_sha256":sha(__file__),"parameters_sha256":sha(a.out/"PARAMETERS.json"),"environment":{"platform":platform.platform(),"python":platform.python_version(),"numpy":np.__version__},"source_pins":{n:sha(a.code/n) for n in src},"max_heading_Jacobian_abs_error":max(x["position_jacobian_max_abs_error"] for x in fd),"max_residual_phi_Jacobian_abs_error":max(x["residual_phi_jacobian_max_abs_error"] for x in fd),"async_vector_Jacobian_max_abs_error":float(abs(nt-Jt).max()),"cardinal_ENU_order_wrap_checks":15,"tilt_closed_form_checks":5,"linear_MC_cases_passed":5,"nonlinear_boundary_cases_reported_not_forced_to_pass":1,"simulation_processes":1,"samples_per_case":N,"raw_reference_native_evaluator_calls":[0,0,0,0],"output_pins":{p.name:sha(p) for p in a.out.iterdir() if p.is_file()}}
 dump(a.out/"VALIDATION_MANIFEST.json",result)
 print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--code",type=Path,required=True);p.add_argument("--out",type=Path,required=True);main(p.parse_args())
