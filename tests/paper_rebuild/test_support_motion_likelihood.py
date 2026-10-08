"""Small exact covariance oracle for the sparse joint restricted likelihood."""
import math
import numpy as np
from scipy import linalg
import gtsam
from gtsam.symbol_shorthand import X

from legsa_gins.paper_rebuild.joint_navigation.support_motion_likelihood import (
    MotionParameters, prepare_support_motion_likelihood,
    evaluate_support_motion_likelihood, integrated_ou_transition, _skew)
from legsa_gins.paper_rebuild.joint_navigation.window import key_ordering


def _problem(off_chart=False):
    graph, values = gtsam.NonlinearFactorGraph(), gtsam.Values()
    times = [0., .07, .23, .6]
    poses = [gtsam.Pose3(gtsam.Rot3.Rz(.08*i), np.array([.04*i, -.02*i, .01*i]))
             for i in range(len(times))]
    graph.push_back(gtsam.PriorFactorPose3(X(0), poses[0],
                    gtsam.noiseModel.Isotropic.Sigma(6,.04)))
    events=[]
    for i,(time,pose) in enumerate(zip(times,poses)):
        values.insert(X(i),pose)
        if i:
            graph.push_back(gtsam.BetweenFactorPose3(X(i-1),X(i),poses[i-1].between(pose),
                gtsam.noiseModel.Isotropic.Sigma(6,.015)))
        feet=[]
        for foot in range(2):
            contact=np.array([.3,(-1)**foot*.2,.4])
            measured=pose.transformTo(contact)+np.array([.003*i*i,.001*foot*i,-.002*i])
            feet.append(dict(arc_id='arc'+str(foot),point_body=measured,
                             foot_id=foot,support_eligible=True))
        events.append(dict(time_s=time,feet=feet))
    # Separate process groups share the same correlated navigation posterior.
    policy=[dict(group_id='g'+str(i),arc_ids=['arc'+str(i)],mode='finite_common_motion') for i in range(2)]
    if off_chart:
        values.update(X(1),poses[1].retract(np.array([.003,-.002,.004,.008,-.005,.002])))
    problem=prepare_support_motion_likelihood(graph,values,events,policy=policy,
        source_scope=dict(foot_factors_consumed=0,reference_reads=0,original_factors_only=True))
    return problem,graph,values


def _dense(problem,graph,values,parameters,*,discard_cross_time=False):
    pose_keys=sorted(values.keys())
    information,eta=graph.linearize(values).hessian(key_ordering(pose_keys))
    nav_cov=linalg.inv(information)
    nav_mean=linalg.solve(information,eta,assume_a='pos')
    if discard_cross_time:
        nav_cov=linalg.block_diag(*[nav_cov[j:j+6,j:j+6] for j in range(0,len(nav_cov),6)])
    arcs=sorted(problem.contact_origins)
    count=len(problem.foot_rows)
    h=np.zeros((3*count,len(information)))
    design=np.zeros((3*count,3*len(arcs)))
    y=np.zeros(3*count)
    q=np.zeros((3*count,3*count))
    birth={}
    for row in problem.foot_rows:
        group=problem.arc_groups[row['arc']]
        birth[group]=min(birth.get(group,math.inf),row['time_s'])
    for i,row in enumerate(problem.foot_rows):
        sl=slice(3*i,3*i+3)
        r=row['rotation']; relative=r.T@(problem.contact_origins[row['arc']]-row['position'])
        key_index=pose_keys.index(row['pose_key'])
        h[sl,6*key_index:6*key_index+6]=np.column_stack((_skew(relative),-np.eye(3)))
        arc_index=arcs.index(row['arc'])
        design[sl,3*arc_index:3*arc_index+3]=r.T
        y[sl]=row['measured']-relative
        for j,other in enumerate(problem.foot_rows):
            sr=slice(3*j,3*j+3)
            if row['arc']==other['arc']:
                q[sl,sr]+=np.eye(3)*problem.foot_sigma_m**2*math.exp(-abs(row['time_s']-other['time_s'])/problem.foot_tau_s)
            group=problem.arc_groups[row['arc']]
            if group==problem.arc_groups[other['arc']]:
                t,u=sorted([row['time_s']-birth[group],other['time_s']-birth[group]])
                tau=parameters.tau_s
                variance=parameters.velocity_sigma_mps**2*(2*tau*t-tau*tau*(1-math.exp(-t/tau))
                    -tau*tau*(math.exp(-(u-t)/tau)-math.exp(-u/tau)))
                q[sl,sr]+=variance*r.T@other['rotation']
    covariance=q+h@nav_cov@h.T
    chol=linalg.cholesky(covariance,lower=True)
    yw=linalg.solve_triangular(chol,y-h@nav_mean,lower=True)
    aw=linalg.solve_triangular(chol,design,lower=True)
    orth,tri=linalg.qr(aw,mode='economic')
    residual=yw-orth@(orth.T@yw)
    return float(residual@residual+2*np.log(np.diag(chol)).sum()
        +2*np.log(np.abs(np.diag(tri))).sum()+(len(y)-len(arcs)*3)*math.log(2*math.pi))


def test_sparse_integral_matches_full_cross_time_dense_reml():
    for off_chart in (False,True):
        problem,graph,values=_problem(off_chart)
        for parameters in [MotionParameters(0.,.2),MotionParameters(.04,.11),MotionParameters(.13,.7)]:
            sparse=evaluate_support_motion_likelihood(problem,parameters)['restricted_objective']
            dense=_dense(problem,graph,values,parameters)
            np.testing.assert_allclose(sparse,dense,rtol=1e-9,atol=2e-9)
    # The oracle really distinguishes the forbidden independent-time shortcut.
    parameters=MotionParameters(.04,.11)
    assert abs(_dense(problem,graph,values,parameters)-_dense(problem,graph,values,parameters,discard_cross_time=True)) > .01


def test_integrated_ou_small_dt_and_semigroup():
    f1,q1=integrated_ou_transition(1e-7,.8,.04)
    assert np.linalg.eigvalsh(q1)[0]>0
    np.testing.assert_allclose(q1[0,0],.04**2*2/(3*.8)*1e-21,rtol=1e-6)
    f2,q2=integrated_ou_transition(.2,.8,.04)
    f3,q3=integrated_ou_transition(.2000001,.8,.04)
    np.testing.assert_allclose(f3,f2@f1,rtol=1e-12,atol=1e-14)
    np.testing.assert_allclose(q3,f2@q1@f2.T+q2,rtol=1e-10,atol=1e-15)
