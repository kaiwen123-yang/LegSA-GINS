"""One nonzero-residual algebra fixture; synthetic only, no data/native/evaluation."""
from pathlib import Path
import json
import numpy as np

def skew(v):
    x,y,z=v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
def exp(v):
    a=np.linalg.norm(v);K=skew(v)
    return np.eye(3)+np.sin(a)/a*K+(1-np.cos(a))/a**2*(K@K) if a else np.eye(3)
def svd_projector(a):
    u,s,v=np.linalg.svd(a,full_matrices=False)
    q=u[:,s>1e-10]
    return q@q.T
def spectrum(a):return np.linalg.eigvalsh((a+a.T)/2).tolist()

R0=exp(np.array([.19,-.11,.31]));R1=R0@exp(np.array([.06,-.035,.08]));D=R0.T@R1
b1=np.array([.48,.30,.012]);b0=D@b1+np.array([.002,-.001,.003])
L=np.eye(12);L[3:6,0:3]=.2*np.eye(3);L[6:9,0:3]=.12*np.diag([1,2,.5]);L[9:12,3:6]=.17*np.eye(3)
Sigma=1e-4*(L@L.T)
M=np.hstack([-np.eye(3),np.eye(3),D,-D]);W=M@Sigma@M.T
G=R0.T@skew(R1@b1);H=np.hstack([G,-G])
def residual(v):
    return (exp(v[:3])@R0).T@(exp(v[3:])@R1)@b1-b0
eps=1e-6
fd=np.column_stack([(residual(np.eye(6)[i]*eps)-residual(-np.eye(6)[i]*eps))/(2*eps) for i in range(6)])
J=G.T@np.linalg.solve(W,G)
S0=J-J@np.linalg.pinv(J,rcond=1e-12)@J
u=R0@np.array([0.,-1.,0.]);w=R1@b1;w/=np.linalg.norm(w)
t0=np.cross(u,np.array([0.,0.,1.]));t0/=np.linalg.norm(t0);t1=np.cross(u,t0)
Hc=20*np.vstack([t0,t1]);A=Hc.T@Hc
S1=J-J@np.linalg.solve(A+J,J)
whiteG=np.linalg.solve(np.linalg.cholesky(W),G)
B0=np.vstack([Hc,whiteG]);B1=np.vstack([np.zeros((2,3)),-whiteG])
Q,_=np.linalg.qr(B0,mode='reduced')
Sqr=B1.T@(np.eye(5)-Q@Q.T)@B1
S0qr=(-whiteG).T@(np.eye(3)-svd_projector(whiteG))@(-whiteG)
global_rotation=exp(np.array([.2,.13,-.09]))
gauge_f=(global_rotation@R0).T@(global_rotation@R1)@b1-b0-residual(np.zeros(6))
C=np.block([[np.eye(3),-np.eye(3),np.zeros((3,6))],
    [np.zeros((3,6)),np.eye(3),-np.eye(3)]])
Cb=C@Sigma@C.T
Wblocks=Cb[:3,:3]+D@Cb[3:,3:]@D.T-Cb[:3,3:]@D.T-D@Cb[3:,:3]
report=dict(schema='differential_direction.single_algebra_fixture.v1',synthetic_only=True,
    inputs=dict(R0=R0.tolist(),R1=R1.tolist(),b0=b0.tolist(),b1=b1.tolist(),
        endpoint_covariance=Sigma.tolist(),synthetic_anchor_rows=Hc.tolist()),
    checks=dict(nonzero_residual_norm=float(np.linalg.norm(residual(np.zeros(6)))),
        endpoint_covariance_min_eigen=float(np.linalg.eigvalsh(Sigma)[0]),
        full_covariance_block_formula_max_abs=float(np.max(abs(W-Wblocks))),
        physical_jacobian_max_abs=float(np.max(abs(H-fd))),
        common_finite_rotation_residual_max_abs=float(np.max(abs(gauge_f))),
        common_linear_rotation_H_g_max_abs=float(np.max(abs(H@np.vstack([np.eye(3),np.eye(3)])))),
        relative_J_eigen=spectrum(J),relative_weak_axis_residual_norm=float(np.linalg.norm(J@w)),
        unanchored_Schur_max_abs=float(np.max(abs(S0))),
        unanchored_whitened_elimination_max_abs=float(np.max(abs(S0qr))),
        A_plus_J_eigen=spectrum(A+J),anchored_endpoint_Schur_eigen=spectrum(S1),
        Schur_vs_independent_whitened_QR_max_abs=float(np.max(abs(S1-Sqr))),
        anchored_kernel_anchor_weak_norm=float(np.linalg.norm(S1@u)),
        anchored_kernel_foot_weak_norm=float(np.linalg.norm(S1@w)),
        weak_axis_angle_deg=float(np.degrees(np.arccos(abs(u@w))))),
    matrices=dict(W=W.tolist(),J=J.tolist(),A=A.tolist(),endpoint_Schur=S1.tolist()),
    limits=['Synthetic anchor strength is an algebra fixture only, not actual carrier precision.',
        'No native/evaluator/raw/reference or parameter search.',
        'This local information freezes the propagated endpoint covariance; it does not infer orientation from covariance derivatives.'])
c=report['checks']
assert c['physical_jacobian_max_abs']<1e-8
assert c['common_finite_rotation_residual_max_abs']<1e-12
assert c['unanchored_Schur_max_abs']<1e-9 and c['unanchored_whitened_elimination_max_abs']<1e-9
assert c['Schur_vs_independent_whitened_QR_max_abs']<1e-9
assert sum(x>1e-8 for x in c['relative_J_eigen'])==2
assert sum(x>1e-8 for x in c['A_plus_J_eigen'])==3
assert sum(x>1e-8 for x in c['anchored_endpoint_Schur_eigen'])==1
report['status']='PASS_SINGLE_NONEMPTY_ALGEBRA_FIXTURE'
Path(__file__).with_name('CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['checks'],indent=2))
