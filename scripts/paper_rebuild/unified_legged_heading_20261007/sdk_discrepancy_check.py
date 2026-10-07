#!/usr/bin/env python3
"""One bounded synthetic joint-state check against an independent free-nuisance QR oracle."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[3]
def pin(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 cpp=ROOT/'cpp/legsa_v23_port_core';source=ROOT/'tests/paper_rebuild/native_sdk_discrepancy_harness.cpp'
 binary=a.output/'sdk_discrepancy_harness';library=a.build/'liblegsa_v23_port_core.a'
 command=['g++','-std=c++17','-O2','-I',str(cpp/'include'),str(source),str(library),'-o',str(binary)]
 built=subprocess.run(command,capture_output=True,text=True);(a.output/'BUILD.log').write_text(built.stdout+built.stderr);built.check_returncode()
 run=subprocess.run([str(binary),str(a.output)],capture_output=True,text=True)
 (a.output/'NATIVE.json').write_text(run.stdout);(a.output/'NATIVE.stderr').write_text(run.stderr);run.check_returncode()
 d=json.loads(run.stdout);P=np.array(d['prior']['P']);mu=np.array(d['prior']['mean']);H1=np.c_[np.array(d['H1']),-np.eye(2)]
 A=[np.c_[np.linalg.solve(np.linalg.cholesky(P),np.eye(21)),np.zeros((21,2))]]
 z=[np.linalg.solve(np.linalg.cholesky(P),mu)]
 for H,R,residual in [(H1,d['R1'],[0.,0.]),(d['anchor_H'],d['anchor_R'],d['anchor_z']),(d['H2'],d['R2'],d['z2'])]:
  L=np.linalg.cholesky(R);A.append(np.linalg.solve(L,H));z.append(np.linalg.solve(L,residual))
 A=np.vstack(A);z=np.concatenate(z);Q,U=np.linalg.qr(A,mode='reduced');truth=np.linalg.solve(U,Q.T@z)
 Ui=np.linalg.solve(U,np.eye(23));truthP=Ui@Ui.T
 actual=np.array(d['posterior']['mean']);actualP=np.array(d['posterior']['P'])
 np.testing.assert_allclose(actual,truth,atol=2e-14,rtol=2e-12);np.testing.assert_allclose(actualP,truthP,atol=2e-14,rtol=2e-12)
 seedP=np.array(d['seed']['P']);np.testing.assert_array_equal(seedP[:21,:21],P)
 np.testing.assert_array_equal(np.array(d['seed']['mean'])[:21],mu)
 # SDK likelihood retains the velocity/discrepancy translation gauge.
 gauge=np.zeros((23,2));gauge[3:5]=np.eye(2);gauge[21:23]=np.array(d['H1'])@gauge[:21]
 np.testing.assert_allclose(H1@gauge,0,atol=0)
 # Independent finite-rotation reset Jacobian, including every current-b-clone cross block.
 before=np.array(d['reset_before']['P']);m=np.array(d['reset_before']['mean']);G=np.eye(29)
 for start in (6,26):
  v=m[start:start+3];step=1e-7
  for j in range(3):
   perturb=np.eye(3)[j]*step
   plus=(Rotation.from_rotvec(v+perturb)*Rotation.from_rotvec(-v)).as_rotvec()
   minus=(Rotation.from_rotvec(v-perturb)*Rotation.from_rotvec(-v)).as_rotvec()
   G[start:start+3,start+j]=(plus-minus)/(2*step)
 resetP=G@before@G.T
 np.testing.assert_allclose(d['reset_after']['P'],resetP,atol=1e-10,rtol=2e-8)
 np.testing.assert_array_equal(d['reset_after']['mean'],np.zeros(29))
 assert d['pass_native_chain'] and d['seed_old27_marginal_max_change']==0 and d['START_23_to_29_exact']
 result=dict(status='PASS',synthetic_only=True,checks=1,native_solver_runs=0,reference_reads=0,
  oracle='First SDK correlated initialization, independent anchor and second SDK equal QR batch with improper flat b prior',
  QR_mean_max_abs=float(abs(actual-truth).max()),QR_covariance_max_abs=float(abs(actualP-truthP).max()),
  reset_independent_jacobian_max_abs=float(abs(np.array(d['reset_after']['P'])-resetP).max()),
  evidence={k:d[k] for k in ['seed_old27_marginal_max_change','seed_no_SA_evaluation','START_23_to_29_exact','propagation_max_abs',
    'retire_23_marginal_max_change','replay_full23_P_max_difference','replay_b_max_difference','replay_v_difference','pre_revoke_b_difference','replay_carrier_acceptances']},
  source=pin(source),check_script=pin(Path(__file__)),library=pin(library),harness=pin(binary),navigation_binary=pin(a.build/'legsa_v23_port_core_demo'))
 (a.output/'CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
