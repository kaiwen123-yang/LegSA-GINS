import numpy as np
from scipy import linalg
from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode, DdArcRelation
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock
from legsa_gins.paper_rebuild.joint_navigation.source_noise_likelihood import (
    NoiseParameters, prepare_source_noise_likelihood, evaluate_source_noise_likelihood,
    dense_source_noise_likelihood, assemble_source_noise_covariance)


def _pivot_slip_blocks():
    rng = np.random.default_rng(23)
    sources = [f"0:{i}:0:0" for i in range(1,5)]
    geometry = np.vstack((np.eye(3), np.zeros(3)))
    integers = np.array([12,25,-8,3])
    blocks = []
    for epoch, time_s in enumerate((0.0,0.2,0.4,0.6)):
        pivot = 3 if epoch == 0 else 2
        targets = [i for i in range(4) if i != pivot]
        incidence = np.zeros((3,4))
        labels = []
        for j,target in enumerate(targets):
            incidence[j,target], incidence[j,pivot] = 1,-1
            labels.append(DdArcRelation(SdArcNode(sources[target], "new" if target == 0 and epoch >= 2 else "old"),
                SdArcNode(sources[pivot], "old")).label)
        baseline = np.array([0.2+epoch*.01,-0.1,0.3])
        b = incidence @ geometry
        a = np.vstack((np.zeros((3,3)),0.19*np.eye(3)))
        n = integers.copy(); n[0] += int(epoch >= 2)
        y = np.r_[b @ baseline, b @ baseline + .19*incidence@n] + rng.normal(size=6)*.004
        q = linalg.block_diag(.1**2*(incidence@incidence.T), .003**2*(incidence@incidence.T))
        blocks.append(EpochBlock(time_s,y,a,np.vstack((b,b)),q,tuple(labels)))
    return blocks


def test_pivot_change_and_integer_slip_keep_physical_beta_source():
    blocks = _pivot_slip_blocks()
    problem = prepare_source_noise_likelihood(blocks)
    assert problem.integer_rank == 4  # three initial relations plus actual new integer arc
    assert problem.physical_source_signals == tuple(f"0:{i}:0:0" for i in range(1,5))  # no fifth beta at slip
    assert problem.degrees_of_freedom == 8
    for parameters in (NoiseParameters(),NoiseParameters(.005,.01,.8)):
        fast = evaluate_source_noise_likelihood(problem,parameters)
        dense = dense_source_noise_likelihood(problem,parameters)
        for name in ("residual_cost","covariance_log_determinant",
                     "integer_information_log_determinant","restricted_objective"):
            np.testing.assert_allclose(getattr(fast,name),getattr(dense,name),atol=1e-8,rtol=1e-10)


def test_raw_covariance_components_match_fixed_contrast_likelihood():
    blocks = _pivot_slip_blocks()
    problem = prepare_source_noise_likelihood(blocks)
    parameters = NoiseParameters(.005,.01,.8)
    covariance = assemble_source_noise_covariance(blocks,parameters)
    transforms=[]
    for block in blocks:
        chol=linalg.cholesky(block.Q,lower=True)
        inverse=linalg.solve_triangular(chol,np.eye(len(block.y)),lower=True)
        q,_=linalg.qr(inverse@block.B,mode="full")
        transforms.append(q[:,3:].T@inverse)
    transform=linalg.block_diag(*transforms)
    h=np.vstack([epoch.source_design for epoch in problem.epochs])
    times=np.concatenate([np.full(len(epoch.rhs),epoch.time_s) for epoch in problem.epochs])
    white=linalg.block_diag(*[parameters.white_sd_sigma_m**2*(epoch.source_design@epoch.source_design.T)
                             for epoch in problem.epochs])
    beta=parameters.beta_sd_sigma_m**2*np.exp(-abs(times[:,None]-times[None,:])/parameters.tau_s)*(h@h.T)
    np.testing.assert_allclose(transform@covariance.original@transform.T,np.eye(len(h)),atol=1e-11)
    np.testing.assert_allclose(transform@covariance.white@transform.T,white,atol=1e-11)
    np.testing.assert_allclose(transform@covariance.beta@transform.T,beta,atol=1e-11)
    np.testing.assert_allclose(transform@covariance.total@transform.T,np.eye(len(h))+white+beta,atol=1e-11)
    assert len(covariance.source_signals)==4
    for incidence in covariance.source_incidence:
        assert np.count_nonzero(incidence[:3])==0
    # Cross-slip beta covariance survives the change of integer coordinate.
    assert np.linalg.norm(covariance.beta[covariance.row_slices[0],covariance.row_slices[2]])>0
