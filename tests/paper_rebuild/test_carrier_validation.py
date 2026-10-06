import numpy as np
import pytest
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock,TemporalModelError
from legsa_gins.paper_rebuild.carrier_phase.validation import score_future_epoch

def model():
    h=np.array([[1.,0,0],[0,1.,0],[0,0,1.],[.4,.6,.7]])
    a=np.vstack([np.zeros((4,4)),.19*np.eye(4)])
    b=np.vstack([h,h]);truth=np.array([2,-1,4,3])
    baseline=np.array([.21,-.28,0.])
    q=np.diag([.3**2]*4+[.002**2]*4)
    q[:4,:4]+=.01
    return EpochBlock(2.,a@truth+b@baseline,a,b,q,tuple("abcd")),truth,baseline

def test_correct_fixed_integer_predicts_moving_future_baseline():
    block,n,b=model();score=score_future_epoch(block,dict(zip(block.ambiguity_labels,map(int,n))),decision_time_s=1.,length_m=.35)
    assert score.residual_cost<1e-15
    assert np.linalg.norm(score.baseline_m-b)<1e-9
    assert not score.accepted_integer_measurement

def test_wrong_integer_increases_future_score_without_search():
    block,n,_=model();wrong=n.copy();wrong[0]+=1
    score=score_future_epoch(block,dict(zip(block.ambiguity_labels,map(int,wrong))),decision_time_s=1.,length_m=.35)
    assert score.residual_cost>100

def test_unknown_reset_arc_drops_only_dependent_rows_with_covariance_marginal():
    block,n,_=model();candidate=dict(zip(block.ambiguity_labels,map(int,n)));candidate.pop("d")
    score=score_future_epoch(block,candidate,decision_time_s=1.,length_m=.35)
    assert score.rows_withheld==(7,)
    assert score.unknown_labels==("d",)
    assert score.known_phase_rows==3
    assert score.residual_cost<1e-15

@pytest.mark.parametrize("decision_time",[2.,3.,float("nan")])
def test_future_only(decision_time):
    block,n,_=model()
    with pytest.raises(TemporalModelError,match="future validation"):
        score_future_epoch(block,dict(zip(block.ambiguity_labels,map(int,n))),decision_time_s=decision_time,length_m=.35)

def test_many_reset_arcs_make_result_unavailable():
    block,n,_=model()
    with pytest.raises(TemporalModelError,match="insufficient future phase"):
        score_future_epoch(block,{"a":int(n[0])},decision_time_s=1.,length_m=.35)

def test_noninteger_candidate_rejected():
    block,n,_=model();candidate=dict(zip(block.ambiguity_labels,map(int,n)));candidate["a"]=2.5
    with pytest.raises(TemporalModelError,match="exactly represented integers"):
        score_future_epoch(block,candidate,decision_time_s=1.,length_m=.35)
