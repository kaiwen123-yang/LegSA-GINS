"""Generator/Q and frozen-candidate domain tests: no integer search."""
from pathlib import Path
import importlib.util
import hashlib
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
def load(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
f=load("followup_covariance_test","scripts/paper_rebuild/carrier_phase/followup_covariance.py")
r=load("robustness_generator_test","scripts/paper_rebuild/carrier_phase/robustness_trial.py")

def test_seed_exact_registration_and_unique():
    cases=r.cases()
    assert len({f.future_seed(x["case_id"]) for x in cases})==72
    for case in cases:
        expected=int(hashlib.sha256(("CARRIER_JOINT_FUTURE_V1|"+case["case_id"]).encode()).hexdigest()[:16],16)
        assert f.future_seed(case["case_id"])==expected

@pytest.mark.parametrize("linked",[False,True])
def test_ar1_covariance_derived_from_actual_recursion(linked):
    c=f.ar1_coefficients(.8,selection_linked=linked)
    t=.8**np.abs(np.arange(5)[:,None]-np.arange(5)[None,:])
    assert np.allclose(c@c.T,t,atol=1e-15)
    if linked:assert np.allclose(c[:,0],.8**np.arange(1,6))
    else:
        assert c.shape==(5,5)
        assert c[0,0]==1 and np.count_nonzero(c[0])==1

@pytest.mark.parametrize("layer",r.LAYERS)
def test_original_rho_generator_matches_covariance_recipe(layer):
    case=next(x for x in r.cases() if x["layer"]==layer);data=r.design(case)
    true_n=np.asarray(data["truth"]["selection_integer"])
    means=[]
    for k,b in enumerate(data["selection"]):
        means.append(b["A"]@true_n+b["B"]@data["truth"]["selection_baseline_m"][k])
    previous=data["selection"][-1]["y"]-means[-1]
    for k,b in enumerate(data["future"]["CLEAN"]):
        mean=b["A"]@true_n+b["B"]@data["truth"]["conditions"]["CLEAN"]["baseline_m"][k]
        noise=b["y"]-mean
        expected=.8*previous+.6*noise
        actual=data["future"]["TEMPORAL_RHO08"][k]["y"]-mean
        assert np.allclose(actual,expected,atol=2e-14,rtol=1e-13)
        previous=expected

@pytest.mark.parametrize("layer",r.LAYERS)
def test_fresh_future_noise_and_full_Q(layer):
    case=next(x for x in r.cases() if x["layer"]==layer);data=r.design(case)
    q=data["selection"][0]["Q"]
    noise,z,latent=f.independent_future_noise(case["case_id"],q)
    assert np.array_equal(latent[0],z[0])
    assert np.allclose(latent[1:],.8*latent[:-1]+.6*z[1:])
    assert np.array_equal(noise,f.independent_future_noise(case["case_id"],q)[0])
    joint=f.temporal_covariance(q,.8)
    assert np.linalg.eigvalsh(joint)[0]>0
    assert np.array_equal(joint[:len(q),:len(q)],q)
    assert np.allclose(joint[:len(q),len(q):2*len(q)],.8*q)
    c=f.ar1_coefficients(.8,selection_linked=False)
    transform=np.kron(c,np.linalg.cholesky(q))
    assert np.allclose(transform@transform.T,joint,atol=1e-15,rtol=1e-14)

def selected():
    return {"labels":["a","b","c"],"active_labels":["a","b","c"],"selected_at":.8,
            "result":{"certificate":{"global_optimum_certified":True},
                      "best":{"ambiguity":[1,2,3]},"second":{"ambiguity":[2,2,3]}}}
@pytest.mark.parametrize("fault",["duplicate","short","uncertified"])
def test_frozen_pair_rejects_silent_zip_or_unqualified_input(fault):
    s=selected()
    if fault=="duplicate":s["labels"]=["a","a","b"]
    elif fault=="short":s["result"]["best"]["ambiguity"]=[1,2]
    else:s["result"]["certificate"]["global_optimum_certified"]=False
    with pytest.raises(ValueError):f.frozen_pair(s,"unit")

@pytest.mark.parametrize("layer",r.LAYERS)
def test_sensitivity_uses_all_original_signal_columns(layer):
    from legsa_gins.paper_rebuild.carrier_phase.temporal import assemble_epochs
    from legsa_gins.paper_rebuild.carrier_phase.faults import fixed_integer_gls
    from legsa_gins.paper_rebuild.carrier_phase.sensitivity import analyze_phase_fault_sensitivity
    data=r.design(next(x for x in r.cases() if x["layer"]==layer))
    blocks=[f.block(r.serial(b)) for b in data["future"]["CLEAN"]]
    mapping=dict(zip(blocks[0].ambiguity_labels,map(int,data["truth"]["selection_integer"])))
    fit=fixed_integer_gls(assemble_epochs(blocks),mapping)
    fmap=f.persistent_map(blocks)
    result=analyze_phase_fault_sensitivity(fit,fmap)
    expected={"M3":4,"M4":5,"M9_MULTIFREQUENCY":12}[layer]
    assert fmap.matrix.shape==(sum(len(b.y) for b in blocks),expected)
    assert result.family_hypotheses==len(result.scores)==expected
    assert all(h.sd_arc_token for h in fmap.hypotheses)
