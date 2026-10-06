"""Design-only invariants. No CILS, raw files, or reference files are opened."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

path=Path(__file__).resolve().parents[1]/"scripts/paper_rebuild/carrier_phase/robustness_trial.py"
spec=importlib.util.spec_from_file_location("robustness_trial_design",path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def case(layer="M3"): return next(x for x in module.cases() if x["layer"]==layer)
def test_budget_unique_splits_and_seeds():
    rows=module.cases()
    assert len(rows)==72 and len({r["seed"] for r in rows})==72
    assert sum(r["split"]=="CALIBRATION" for r in rows)==24
    assert sum(r["split"]=="HELDOUT" for r in rows)==48
    assert len(module.CONDITIONS)==7
    assert module.protocol()["admission_policy"]["threshold_adjustment"].startswith("Forbidden")

@pytest.mark.parametrize("layer",module.LAYERS)
def test_dynamic_baseline_geometry_covariance_and_units(layer):
    d=module.design(case(layer));b=d["selection"][0];m=d["metadata"]["dd_count"]
    assert np.linalg.matrix_rank(b["B"])==3
    assert np.linalg.eigvalsh(b["Q"])[0]>0
    assert np.allclose(b["Q"],b["Q"].T)
    assert np.allclose(np.diag(b["Q"])[m:],4*module.PHASE_SIGMA_M**2)
    truth=d["truth"]
    assert np.allclose(np.linalg.norm(truth["selection_baseline_m"],axis=1),.35)
    assert np.linalg.norm(truth["selection_baseline_m"][0]-truth["selection_baseline_m"][-1])>.04
    assert [x["time_s"] for x in d["selection"]]==[0.,.2,.4,.6000000000000001,.8]
    assert all(x["time_s"]>.8 for blocks in d["future"].values() for x in blocks)
    if layer=="M9_MULTIFREQUENCY":
        assert b["A"][m,0]!=b["A"][m+3,3]
        assert b["Q"][m,m+3]!=0
        assert b["Q"][m,m+1]==pytest.approx(2*module.PHASE_SIGMA_M**2)
        assert b["Q"][m,m+3]==pytest.approx(4*.35*module.PHASE_SIGMA_M**2)

@pytest.mark.parametrize("layer",module.LAYERS)
def test_single_and_pivot_fault_directions_and_integer_truth(layer):
    d=module.design(case(layer));m=d["metadata"]["dd_count"];j=d["metadata"]["fault_target_column"]
    clean=d["future"]["CLEAN"][0];lam=clean["A"][m+j,j]
    target=d["future"]["TARGET_QUARTER"][0]["y"]-clean["y"]
    expected=np.zeros(2*m);expected[m+j]=.25*lam
    assert np.allclose(target,expected,atol=1e-14)
    pivot=d["future"]["PIVOT_QUARTER"][0]["y"]-clean["y"]
    expected=np.zeros(2*m);per=4 if layer=="M4" else 3
    expected[m+j:m+j+per]=-.25*lam
    assert np.allclose(pivot,expected,atol=1e-14)
    assert np.all(d["truth"]["conditions"]["TARGET_QUARTER"]["integer_by_epoch"]==d["truth"]["selection_integer"])
    slip=d["truth"]["conditions"]["UNDETECTED_SLIP"]
    assert not slip["model_truth_representable_across_selection_and_future"]
    assert np.all(slip["integer_by_epoch"][:,j]==d["truth"]["selection_integer"][j]+1)

@pytest.mark.parametrize("layer",module.LAYERS)
def test_paired_noise_support_and_truth_separation(layer):
    row=case(layer);d=module.design(row);again=module.design(row)
    assert module.serial(d)==module.serial(again)
    for a,b in zip(d["future"]["CLEAN"],d["future"]["TEMPORAL_RHO08"]):
        assert np.array_equal(a["Q"],b["Q"]) and not np.array_equal(a["y"],b["y"])
    for b in d["future"]["INSUFFICIENT_SUPPORT"]:
        assert sum(np.any(b["A"]!=0,axis=1))==2
        assert len(b["y"])==4
        assert all(len(t["direction_m_per_cycle"])==4 for t in b["metadata"]["phase_templates"])
    for b in d["selection"]:
        assert "truth" not in b and not any("truth" in key or key.startswith("true_") for key in b["metadata"])
    b=d["future"]["CLEAN"][0];m=d["metadata"]["dd_count"]
    pivot=next(x for x in b["metadata"]["phase_templates"] if x["kind"]=="PIVOT")
    assert np.count_nonzero(pivot["direction_m_per_cycle"])==(4 if layer=="M4" else 3)
    assert np.all(np.asarray(pivot["direction_m_per_cycle"])[m:]<=0)

def test_plan_directory_is_exclusive_and_truth_not_selection(tmp_path):
    out=tmp_path/"prep";p=module.prepare(out)
    import json
    s=json.loads((out/p["cases"][0]["selection_inputs_file"]).read_text())
    assert set(s)=={"case","blocks","metadata"}
    assert "truth" not in s and len(s["blocks"])==5
    assert (out/"truth").exists()
    with pytest.raises(FileExistsError): module.prepare(out)


@pytest.mark.parametrize("layer",module.LAYERS)
def test_persistent_fault_map_and_admission_api_without_search(layer):
    from legsa_gins.paper_rebuild.carrier_phase.admission import (
        FrozenCandidate,AdmissionConfig,CausalAdmissionSession)
    d=module.design(case(layer))
    blocks=[module.from_block(b) for b in d["future"]["PIVOT_QUARTER"]]
    labels=tuple(d["selection"][0]["ambiguity_labels"])
    integers=dict(zip(labels,map(int,d["truth"]["selection_integer"])))
    diag=module.persistent_fault_diagnostic(blocks,integers)
    assert diag["fixed_integer_gls"]["rank"]==15
    assert diag["diagnosis"].tested_hypotheses==sum(len(g["target_ids"])+1 for g in d["selection"][0]["metadata"]["groups"])
    alt=dict(integers);alt[labels[0]]+=1
    primary=FrozenCandidate.from_mapping("primary",.8,integers,labels,"unit")
    competitor=FrozenCandidate.from_mapping("competitor",.8,alt,labels,"unit")
    session=CausalAdmissionSession(primary,competitor,AdmissionConfig())
    for b in blocks:session.observe(b)
    result=session.finalize()
    assert len(result.epochs)==5
    assert result.primary.length_bound_df==15
    assert result.primary.residual_df==sum(len(b.y)-3 for b in blocks)
    assert result.accepted_integer_measurement is False and result.false_fix_probability is None

def test_singular_support_never_becomes_shadow_accepted():
    from legsa_gins.paper_rebuild.carrier_phase.admission import (
        FrozenCandidate,AdmissionConfig,CausalAdmissionSession)
    d=module.design(case("M9_MULTIFREQUENCY"));labels=tuple(d["selection"][0]["ambiguity_labels"])
    integers=dict(zip(labels,map(int,d["truth"]["selection_integer"])))
    alt=dict(integers);alt[labels[0]]+=1
    session=CausalAdmissionSession(FrozenCandidate.from_mapping("p",.8,integers,labels,"unit"),
                                   FrozenCandidate.from_mapping("q",.8,alt,labels,"unit"),AdmissionConfig())
    blocks=[module.from_block(b) for b in d["future"]["INSUFFICIENT_SUPPORT"]]
    for b in blocks:session.observe(b)
    result=session.finalize()
    assert not result.shadow_accepted
    assert result.status.startswith("UNRESOLVED")
    assert module.persistent_fault_diagnostic(blocks,integers)["fixed_integer_gls"]["rank"]<15
