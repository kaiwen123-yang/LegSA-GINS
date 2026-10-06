"""Opt-in scalar backend: synthetic sphere/search cases only, no real CILS."""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import numpy as np
import pytest

from legsa_gins.paper_rebuild.carrier_phase import solver, partial
from legsa_gins.paper_rebuild.carrier_phase.native_sphere import (
    ABI_VERSION, KERNEL_VERSION, NativeSphereBackend, NativeSphereError,
)
from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import BaselineSphereMetric, CLambdaError
from test_carrier_solver_review import (
    problem_fixture, fake_lambda_bridge, historical_arc_problem, independent_active_class_pair,
)

@pytest.fixture(scope="module")
def sphere_library(tmp_path_factory):
    if not shutil.which("g++"):
        pytest.skip("explicit native-backend tests require the optional C++ compiler")
    root=Path(__file__).resolve().parents[2]
    script=root/"scripts/paper_rebuild/carrier_phase/build_native_sphere.py"
    spec=importlib.util.spec_from_file_location("sphere_builder",script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.build(tmp_path_factory.mktemp("sphere_build"))


def assert_same(actual, expected, length):
    np.testing.assert_allclose(actual.baseline,expected.baseline,rtol=0.,atol=1e-10*max(1.,length))
    assert actual.objective==pytest.approx(expected.objective,rel=1e-10,abs=1e-10)
    assert actual.hard_case==expected.hard_case
    assert actual.constraint_error_m<1e-9


def test_native_random_spd_cached_sphere_matches_python(sphere_library):
    backend=NativeSphereBackend(sphere_library)
    rng=np.random.default_rng(2026100618)
    for _ in range(128):
        u,_=np.linalg.qr(rng.normal(size=(3,3)))
        q=u@np.diag(10.**rng.uniform(-6,4,size=3))@u.T
        c=rng.normal(size=3);length=float(rng.uniform(.05,2.))
        native=backend.from_covariance(q);python=BaselineSphereMetric.from_covariance(q)
        for multiplier in (.001,1.,10.):
            assert_same(native.solve(multiplier*c,length),python.solve(multiplier*c,length),length)


@pytest.mark.parametrize("q", [np.eye(3),np.diag([.25,1.,4.]),np.diag([1.,1.+1e-12,.5])])
def test_native_hard_and_signed_near_pole_keep_original_semantics(sphere_library,q):
    python=BaselineSphereMetric.from_covariance(q);native=NativeSphereBackend(sphere_library).from_covariance(q)
    for tiny in (0.,-1e-12,1e-12,-1e-30,1e-30):
        c=np.zeros(3);c[np.argmax(np.diag(q))]=tiny
        actual=native.solve(c,.35);expected=python.solve(c,.35)
        assert_same(actual,expected,.35)
        if tiny:
            assert not actual.hard_case
            assert np.sign(actual.baseline[np.argmax(np.diag(q))])==np.sign(tiny)
        else:assert actual.hard_case


@pytest.mark.parametrize("exponent", [100,250,300])
def test_native_does_not_hide_original_300_iteration_near_pole_failure(sphere_library,exponent):
    q=np.diag([.25,1.,4.]);c=np.array([0.,0.,10.**(-exponent)])
    for metric in (BaselineSphereMetric.from_covariance(q),NativeSphereBackend(sphere_library).from_covariance(q)):
        with pytest.raises(CLambdaError,match="sphere root failed constraint tolerance"):
            metric.solve(c,.35)


def test_backend_identity_matches_build_manifest_and_artifact(sphere_library):
    backend=NativeSphereBackend(sphere_library)
    manifest=json.loads(sphere_library.with_name("BUILD_MANIFEST.json").read_text())
    assert backend.library_sha256==manifest["library_sha256"]==hashlib.sha256(sphere_library.read_bytes()).hexdigest()
    assert backend.abi_version==ABI_VERSION==manifest["abi_version"]
    assert backend.kernel_version==KERNEL_VERSION==manifest["kernel_version"]
    assert "-fno-fast-math" in manifest["command"]
    assert "-ffp-contract=off" in manifest["command"]


def test_explicit_missing_library_fails_closed(tmp_path):
    with pytest.raises(NativeSphereError,match="cannot load explicitly requested"):
        NativeSphereBackend(tmp_path/"missing.so")


@pytest.mark.parametrize("abi,version", [(0,b"delta_bisection_3d_v1"),(1,b"wrong_kernel"),(1,None)])
def test_incompatible_abi_or_kernel_is_rejected(monkeypatch,sphere_library,abi,version):
    class Function:
        def __init__(self,value):self.value=value
        def __call__(self):return self.value
    wrong=SimpleNamespace(legsa_sphere_abi_version=Function(abi),legsa_sphere_kernel_version=Function(version))
    monkeypatch.setattr(ctypes,"CDLL",lambda _:wrong)
    with pytest.raises(NativeSphereError,match="ABI/kernel version mismatch"):
        NativeSphereBackend(sphere_library)


def test_missing_native_symbols_rejected(monkeypatch,sphere_library):
    monkeypatch.setattr(ctypes,"CDLL",lambda _:SimpleNamespace())
    with pytest.raises(NativeSphereError,match="ABI/kernel version mismatch"):
        NativeSphereBackend(sphere_library)


@pytest.mark.parametrize("center,length", [([0.,0.],.35),([np.nan,0.,0.],.35),([np.inf,0.,0.],.35),([0.,0.,0.],0.),([0.,0.,0.],np.inf)])
def test_native_input_validation_matches_public_kernel(sphere_library,center,length):
    for metric in (BaselineSphereMetric.from_covariance(np.eye(3)),NativeSphereBackend(sphere_library).from_covariance(np.eye(3))):
        with pytest.raises(CLambdaError,match="invalid constrained-baseline inputs"):
            metric.solve(center,length)


@pytest.mark.parametrize("status,match", [(1,"failed to bracket"),(2,"unresolved constrained"),(3,"invalid constrained"),(99,"invalid status")])
def test_native_failure_codes_cannot_manufacture_result(monkeypatch,sphere_library,status,match):
    backend=NativeSphereBackend(sphere_library)
    monkeypatch.setattr(backend,"_root",lambda *args:status)
    with pytest.raises(CLambdaError,match=match):
        backend.from_covariance(np.eye(3)).solve([.2,.1,0.],.35)


def test_nonfinite_success_payload_fails_closed(monkeypatch,sphere_library):
    backend=NativeSphereBackend(sphere_library)
    def corrupted(eigen,c,length,tol,out,hard,iterations):
        for k in range(4):out[k]=float("nan")
        return 0
    monkeypatch.setattr(backend,"_root",corrupted)
    with pytest.raises(NativeSphereError,match="invalid result"):
        backend.from_covariance(np.eye(3)).solve([.2,.1,0.],.35)


def test_default_solver_never_loads_native_backend(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError("default loaded optional sphere library")
    monkeypatch.setattr(solver,"NativeSphereBackend",forbidden)
    monkeypatch.setattr(solver,"RTKLIBLambdaBridge",fake_lambda_bridge(np.eye(2,dtype=int)))
    result=solver.solve_temporal(problem_fixture(),"NO_NATIVE_LAMBDA",initial_candidates=2,timeout_s=10)
    assert result.global_optimum_certified
    assert result.certificate.sphere_backend=="python"
    assert result.certificate.sphere_library_sha256 is None


@pytest.mark.parametrize("transform",[np.eye(2,dtype=int),np.array([[1,2],[0,1]])])
def test_native_exact_search_pair_matches_python_with_both_factories_used(monkeypatch,sphere_library,transform):
    monkeypatch.setattr(solver,"RTKLIBLambdaBridge",fake_lambda_bridge(transform))
    problem=problem_fixture()
    python=solver.solve_temporal(problem,"NO_NATIVE_LAMBDA",initial_candidates=2,timeout_s=10)
    counts={"factors":0,"calls":0}
    original=NativeSphereBackend.from_covariance
    def observed(self,q):
        result=original(self,q);counts["factors"]+=1
        method=result.solve
        def solve(*args,**kwargs):counts["calls"]+=1;return method(*args,**kwargs)
        result.solve=solve
        return result
    monkeypatch.setattr(NativeSphereBackend,"from_covariance",observed)
    native=solver.solve_temporal(problem,"NO_NATIVE_LAMBDA",initial_candidates=2,timeout_s=10,sphere_library=sphere_library)
    assert native.global_optimum_certified and python.global_optimum_certified
    for actual,expected in zip((native.best,native.second),(python.best,python.second)):
        np.testing.assert_array_equal(actual.ambiguity,expected.ambiguity)
        np.testing.assert_allclose(actual.baselines,expected.baselines,atol=1e-10,rtol=0.)
        assert actual.full_residual_cost==pytest.approx(expected.full_residual_cost,rel=1e-10,abs=1e-10)
    cert=native.certificate
    assert cert.sphere_backend=="native_scalar" and cert.sphere_abi_version==1
    assert cert.sphere_library_sha256==hashlib.sha256(sphere_library.read_bytes()).hexdigest()
    assert counts["factors"]==cert.sphere_metric_factorizations
    assert counts["calls"]==cert.bound_sphere_evaluations+cert.candidate_sphere_evaluations
    assert cert.bound_sphere_evaluations>0 and cert.candidate_sphere_evaluations>0


def test_native_selected_class_matches_independent_exhaustive_oracle(monkeypatch,sphere_library):
    problem=historical_arc_problem()
    transform=np.array([[1,2,0],[0,1,1],[0,0,1]])
    class Bridge:
        def __init__(self,_):pass
        def candidates(self,mean,covariance,count):
            if len(mean)!=3:raise solver.LambdaBridgeError("no optional seed in oracle")
            return [SimpleNamespace(ambiguity=np.array([1,-1,3])),SimpleNamespace(ambiguity=np.array([3,-1,3]))]
        def decorrelate(self,mean,covariance):
            return SimpleNamespace(transformation=transform,float_ambiguity=transform.T@mean,covariance=transform.T@covariance@transform)
    monkeypatch.setattr(solver,"RTKLIBLambdaBridge",Bridge)
    expected=independent_active_class_pair(problem,(2,1))
    native=solver.solve_temporal(problem,"NO_NATIVE_LAMBDA",initial_candidates=2,timeout_s=10,
        distinct_ambiguity_labels=("NEW","SHARED"),sphere_library=sphere_library)
    assert native.global_optimum_certified
    assert native.certificate.certificate_scope=="two_best_selected_integer_classes"
    for actual,want in zip((native.best,native.second),expected):
        assert tuple(actual.ambiguity)==want[1]
        assert actual.full_residual_cost==pytest.approx(want[0],abs=1e-8)


@pytest.mark.parametrize("library",[None,"explicit_optional_sphere.so"])
def test_partial_forwards_backend_without_changing_registered_search(monkeypatch,library):
    plan=SimpleNamespace(problem=object(),selection=SimpleNamespace(ready=True,selected_labels=("a","b")))
    result=object()
    def solve(problem,lambda_library,**kwargs):
        assert problem is plan.problem and lambda_library=="lambda.so"
        assert kwargs["sphere_library"]==library
        assert kwargs["distinct_ambiguity_labels"]==("a","b")
        return result
    monkeypatch.setattr(partial,"solve_temporal",solve)
    assert partial.solve_partial(plan,"lambda.so",sphere_library=library) is result
