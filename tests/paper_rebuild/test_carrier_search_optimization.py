"""Correctness and bounded-cost optimization oracles; no real-data runs."""
from pathlib import Path
import importlib.util
import json
from types import SimpleNamespace

import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase import solver
from legsa_gins.paper_rebuild.carrier_phase.temporal import joint_float

# Reuse independent dense GLS/raw-residual/sphere oracles, not solver helpers.
spec=importlib.util.spec_from_file_location("optimization_oracle",
                                         Path(__file__).with_name("test_carrier_solver_review.py"))
oracle=importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


@pytest.fixture
def library():
    root=Path(__file__).resolve().parents[2]
    config=root/"configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json"
    if not config.exists():pytest.skip("local RTKLIB library config unavailable")
    aliases=json.loads(config.read_text())["aliases"]
    result=Path(aliases["<EXT_REPRO_BUILD>"])/"lib/librtklib_legsa.so"
    if not result.is_file():pytest.skip("pinned RTKLIB library unavailable")
    return result


def test_conditional_seed_mean_covariance_match_constrained_dense_quadratic():
    floating=joint_float(oracle.historical_arc_problem())
    weight=np.linalg.inv(floating.covariance_aa)
    for index in range(3):
        value=4
        free,mean,covariance=solver._condition_integer_coordinate(floating,index,value)
        wff=weight[np.ix_(free,free)]
        expected=floating.ambiguity[free]-np.linalg.solve(wff,weight[free,index])*(value-floating.ambiguity[index])
        np.testing.assert_allclose(mean,expected,atol=1e-10)
        np.testing.assert_allclose(covariance,np.linalg.inv(wff),atol=1e-10)


def test_conditional_integer_seed_moves_correlated_nuisance_instead_of_zeroing_it(library):
    q=np.array([[100.,99.99],[99.99,100.]])
    floating=SimpleNamespace(ambiguity=np.array([.1,.1]),covariance_aa=q)
    free,mean,covariance=solver._condition_integer_coordinate(floating,0,1)
    bridge=solver.RTKLIBLambdaBridge(library)
    seeds=bridge.candidates(mean,covariance,2)
    lifted=np.zeros(2,dtype=int);lifted[0]=1;lifted[free]=seeds[0].ambiguity
    assert tuple(lifted)==(1,1)
    weight=np.linalg.inv(q)
    def cost(n):
        delta=np.asarray(n)-floating.ambiguity
        return delta@weight@delta
    assert cost(lifted)<cost([1,0])/1000


@pytest.mark.parametrize("transform",[np.eye(3,dtype=int),np.array([[1,2,0],[0,1,1],[0,0,1]])])
def test_depth_cache_reuses_factors_and_matches_original_node_formula(transform):
    problem=oracle.historical_arc_problem()
    floating=joint_float(problem)
    reduced=SimpleNamespace(transformation=transform,float_ambiguity=transform.T@floating.ambiguity,
                            covariance=transform.T@floating.covariance_aa@transform)
    cache=solver._BaselineBoundCache(problem,floating,reduced)
    qbb=floating.covariance[3:,3:]
    qbz=floating.covariance_ba@transform
    for depth in range(4):
        first=cache.parameters(depth)
        assert cache.parameters(depth) is first
        for sign in (-1,1):
            indices=np.arange(3-depth,3)
            suffix=np.rint(reduced.float_ambiguity[indices])+sign*.0
            if depth:suffix[0]+=sign
            if depth:
                qss=reduced.covariance[np.ix_(indices,indices)]
                qbs=qbz[:,indices]
                center=floating.baseline+qbs@np.linalg.solve(qss,suffix-reduced.float_ambiguity[indices])
                cov=qbb-qbs@np.linalg.solve(qss,qbs.T)
            else:center,cov=floating.baseline,qbb
            cov=(cov+cov.T)*.5
            cheap=[(np.linalg.norm(center[ss])-problem.lengths[k])**2/np.linalg.eigvalsh(cov[ss,ss])[-1]
                   for k,ss in enumerate(problem.baseline_slices)]
            k=int(np.argmax(cheap));ss=problem.baseline_slices[k]
            exact=solver.constrained_baseline(center[ss],cov[ss,ss],problem.lengths[k]).objective
            expected=2.5+max(max(cheap),exact)
            assert cache(tuple(suffix),2.5)==pytest.approx(expected,rel=1e-10,abs=1e-10)
    assert len(cache.depths)==4


def test_optimized_selected_classes_equal_independent_exhaustive_raw_residual_oracle(library):
    problem=oracle.historical_arc_problem()
    expected=oracle.independent_active_class_pair(problem,(2,1))
    result=solver.solve_temporal(problem,library,distinct_ambiguity_labels=("NEW","SHARED"),
                                  node_limit=10000,timeout_s=10)
    assert result.global_optimum_certified
    assert result.certificate.conditional_seed_ils_calls==4
    assert result.certificate.conditional_seed_candidates_evaluated>0
    assert result.certificate.bound_cache_depths<=problem.ambiguity_count+1
    assert result.certificate.certificate_scope=="two_best_selected_integer_classes"
    for actual,want in zip((result.best,result.second),expected):
        assert tuple(actual.ambiguity)==want[1]
        assert actual.ambiguity.shape==(3,)  # historical integer remains profiled
        assert actual.full_residual_cost==pytest.approx(want[0],abs=1e-8)
        np.testing.assert_allclose(actual.baselines,want[2],atol=1e-7)


def test_full_class_search_does_not_incur_conditional_seed_calls(library):
    problem=oracle.problem_fixture()
    result=solver.solve_temporal(problem,library,timeout_s=10)
    expected=oracle.exhaustive_global_pair(problem)
    assert result.global_optimum_certified
    assert result.certificate.conditional_seed_ils_calls==0
    for actual,want in zip((result.best,result.second),expected):
        assert tuple(actual.ambiguity)==want[1]
        assert actual.full_residual_cost==pytest.approx(want[0],abs=1e-8)


def test_timeout_during_optional_conditioning_cannot_certify(monkeypatch,library):
    elapsed={"time":0.}
    original=solver.RTKLIBLambdaBridge
    class Bridge(original):
        def candidates(self,mean,covariance,count):
            result=super().candidates(mean,covariance,count)
            if len(mean)<3:elapsed["time"]=100.
            return result
    monkeypatch.setattr(solver,"RTKLIBLambdaBridge",Bridge)
    monkeypatch.setattr(solver.time,"monotonic",lambda:elapsed["time"])
    result=solver.solve_temporal(oracle.historical_arc_problem(),library,
                                distinct_ambiguity_labels=("NEW","SHARED"),timeout_s=10)
    assert not result.global_optimum_certified and not result.candidate_available
    assert result.certificate.termination_reason=="TIMEOUT_DURING_CONDITIONAL_SEED_EVALUATION"


def test_optional_seed_failure_does_not_change_exact_profiled_solution(monkeypatch,library):
    original=solver.RTKLIBLambdaBridge
    class Bridge(original):
        def candidates(self,mean,covariance,count):
            if len(mean)<3:raise solver.LambdaBridgeError("unit-test optional seed failure")
            return super().candidates(mean,covariance,count)
    monkeypatch.setattr(solver,"RTKLIBLambdaBridge",Bridge)
    problem=oracle.historical_arc_problem()
    result=solver.solve_temporal(problem,library,distinct_ambiguity_labels=("NEW","SHARED"),timeout_s=10)
    expected=oracle.independent_active_class_pair(problem,(2,1))
    assert result.global_optimum_certified
    assert result.certificate.conditional_seed_failures==4
    for actual,want in zip((result.best,result.second),expected):
        assert tuple(actual.ambiguity)==want[1]
        assert actual.full_residual_cost==pytest.approx(want[0],abs=1e-8)
